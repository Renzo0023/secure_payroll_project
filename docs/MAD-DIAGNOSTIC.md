# Diagnostic du prérequis MAD — intégration finale

## Ce qui est établi

L’erreur signalée vient exactement du COUNT sur `information_schema.COLUMNS`
dans `bin/payroll-admin.py`, avant le contrôle des corps de procédures.
Il doit compter **deux** lignes répondant simultanément à :

- schéma `secure_payroll` ;
- table `compensation_requests` ou `salary_conditions` ;
- colonne `currency` présente ;
- `CHARACTER_MAXIMUM_LENGTH = 3` ;
- `COLUMN_DEFAULT = 'MAD'`.

Le message reçu établit que ce COUNT diffère de 2. Il ne précise pas quelle table,
longueur ou valeur par défaut échoue. Des lignes financières historiques en UM
**ne font pas échouer ce contrôle** : il porte sur les métadonnées uniquement.
Un défaut MAD ne transforme pas les valeurs UM déjà enregistrées.

La migration 004 définit les deux colonnes en CHAR(2), défaut UM, avec les CHECK
`ck_cr_amount` / `ck_sc_amount` limitant la devise à UM. La migration 006 les passe
en CHAR(3), défaut MAD, autorise MAD et UM dans ces CHECK, puis recrée trois
procédures et restaure des EXECUTE. Elle n’effectue aucun UPDATE financier.
**Elle n’est pas rejouée**, notamment parce que les suppressions/recréations de
procédures et les GRANT sont exclus du périmètre actuel.

Aucun défaut logique du prédicat d’origine n’a été démontré. Il reconnaît bien
les états MAD complets du laboratoire. Sa limite confirmée est un message trop
sommaire, corrigé : l’inspection imprime désormais le nombre de correspondances
et les résultats longueur/défaut pour chacune des deux tables, sans assouplir le
prérequis ni déclencher de correction.

## Lecture réelle principale : intervention DBA requise

La tentative directe en lecture seule sur le socket principal a été refusée :
`ERROR 1698 (28000): Access denied for user 'root'@'localhost'`.
Le confinement avait d’abord refusé l’accès au socket ; la tentative autorisée
hors confinement a confirmé le refus d’authentification. Aucun sudo ni contournement
n’a été tenté, aucune donnée principale n’a été lue avec succès ou modifiée.

Dans le terminal où l’authentification sudo de l’opérateur fonctionne :

```bash
sudo python3 bin/payroll-admin.py diagnose-mad
```

La commande exécute uniquement `database/audit/mad-readonly.sql` et un calcul
d’empreinte en lecture seule. Elle ne dépend pas de la réussite du prérequis MAD,
ne lance aucune migration et ne lit aucun secret d’authentification.

La sortie comporte : identité/version/socket/datadir du serveur, résultat exact du
COUNT original, présence/type/longueur/NULL/défaut et HEX du défaut, charset/collation,
types DECIMAL, tous les CHECK et leur état ENFORCED, définitions des trois routines,
inventaire des triggers, comptes et totaux par devise, anomalies de devise/montant,
incohérences demande/salaire et SHOW CREATE TABLE des deux tables.
La dernière ligne `MAD_AMOUNTS_CURRENCY_SHA256` résume, dans l’ordre table/id,
les identifiants, montants décimaux exacts et devises enregistrées, sans afficher
les lignes individuelles. Pour une comparaison avant/après, arrêter les écritures
et le DDL pendant les deux relevés.

Transmettre la sortie de diagnostic, sans secret. **L’état principal ne peut pas
encore être classé absent/partiel/erroné sans cette sortie.**

## Interprétation après réception

| Colonnes et CHECK | Procédures | Conclusion sur l’état observé |
|---|---|---|
| Deux CHAR(2), défaut UM, CHECK UM | Corps de 005 écrivant UM | État legacy compatible avec 006 non appliquée ; aucun journal ne prouve son historique d’exécution |
| Une table cible et l’autre legacy | Quelconques | Transition des tables partielle ; ne pas rejouer 006 |
| Deux CHAR(3), défaut MAD, CHECK MAD/UM | Un ou plusieurs corps anciens/absents | Transition de routines incomplète ; corriger les colonnes ne suffira pas |
| Deux CHAR(3), défaut MAD, CHECK MAD/UM | Corps MAD complets | Prérequis de colonnes attendu à 2 ; si l’erreur persiste, comparer l’identité du serveur, les valeurs exactes et les deux sorties |
| Définition différente, CHECK manquant/non appliqué ou données inattendues | Quelconques | État personnalisé/inattendu ; diagnostic ciblé DBA avant toute correction |

La présence de UM dans les données ne prouve jamais, à elle seule, une migration
absente : la préservation des historiques UM est explicitement requise.

Le contrôle suivant du lanceur vérifie aussi les trois routines MAD et les deux
CHECK appliqués. Le correctif de schéma seul ne suffit pas. Utiliser désormais
la [procédure complète MAD-REPAIR.md](MAD-REPAIR.md) : sauvegarde, restauration
isolée, remplacement ciblé des trois routines et restitution exacte des droits.
Ne pas exécuter directement 002 ou 003 sur la principale et ne pas rejouer 006.

## Validation limitée au laboratoire

18 contrôles MySQL réels ont réussi dans de nouveaux schémas fictifs d’une
instance privée, sans connexion à la principale :

- diagnostic complet et empreinte de lecture seule ;
- état entièrement MAD : COUNT original 2/2 ;
- état legacy : COUNT 0/2 et quatre échecs longueur/défaut identifiés ;
- état partiel : COUNT 1/2, une seule table corrigée ;
- refus sans autorisation et refus d’une structure inattendue avant le premier ALTER ;
- conservation exacte par SHA256 des identifiants, décimaux et devises UM ;
- seconde exécution sans ALTER ni changement de définition/données ;
- définitions des routines et privilèges existants inchangés.

L’essai a aussi pris en compte l’échappement des quotes présent dans CHECK_CLAUSE
renvoyé par MySQL ; il ne s’agit pas d’une preuve de défaut du validateur principal.
Les 12 contrôles hors connexion des frontières de GRANT Paie et la compilation
Python des deux fichiers concernés passent également.

Preuve conservée :
`/var/tmp/securepayroll-mysql-ga9l9i9k/mad-diagnostic-result-fe30c7f7.json`.
Les schémas fictifs sont conservés ; l’instance privée est arrêtée, socket absent.
Aucune installation Paie/Bulletins, aucune suppression principale, aucun changement
de privilège principal et aucune commande Git n’ont été effectués.
