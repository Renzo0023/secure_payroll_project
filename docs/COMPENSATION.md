# Mission 06A — rémunérations installées

**État confirmé par l’utilisateur le 4 novembre 2026 :** les quatre tables de
rémunération et le compte `finance.demo` existent dans `secure_payroll`. Ne pas
relancer `activate-compensation` ni `create-finance-demo`. Le parcours RH → Finance
et la configuration MAD restent à vérifier réellement. Le parcours RH → Finance en MAD a été testé avec succès dans une instance
indépendante ; cela ne remplace pas la vérification de l’installation principale.
Voir [le rapport](LAB-VALIDATION-2026-11-04.md). Les instructions
d’installation ci-dessous sont conservées pour une installation neuve uniquement.

Le code web est livré ; les objets MySQL sont présents sur cette installation selon la vérification de l’utilisateur.
Ne rejouer aucune migration 001, 002 ou 003. Conserver la correction 05C déjà appliquée.
Ne pas relancer `install` ou `activate-hr` pour cette mission.

## Fichiers et ordre d'installation

Le lanceur existant `bin/local-demo.py` applique, après contrôles et confirmation :

1. `database/setup/compensation_owner.sql` : nouveau propriétaire verrouillé, mot de passe aléatoire dont la sortie est capturée et jamais affichée.
2. `database/migrations/004_compensation.sql` : quatre tables InnoDB, utf8mb4_0900_as_cs, contraintes, huit triggers interdisant UPDATE/DELETE et un contrôle de couverture salariale sur la clôture des contrats.
3. `database/migrations/005_compensation_operations.sql` : quatre procédures avec DEFINER explicite `compensation_owner@localhost`, SQL SECURITY DEFINER et paramètres textuels à collation explicite.
4. `database/migrations/006_mad_currency.sql` : passage à MAD pour les nouvelles données, sans convertir les historiques UM.
5. `database/setup/compensation_owner_grants.sql` : droits du propriétaire.
6. `database/seeds/005_compensation_permissions.sql` : permissions et associations idempotentes des rôles existants.
7. `database/setup/compensation_grants.sql` : droits limités de svc_php.

Après revue et validation de ces fichiers, arrêter le serveur PHP dans son terminal avec Ctrl+C, puis :

```bash
cd ~/projects/database-security
sudo python3 bin/local-demo.py activate-compensation --apply
```

Saisir `secure_payroll` lorsque la cible est demandée. Cette commande est une opération administrative **manuelle** : accès local MySQL root par socket uniquement pour installer les objets, DEFINER et GRANT. Aucun mot de passe root n'est transmis. Si l'installation locale n'autorise pas cette authentification, demander au DBA d'exécuter les sept fichiers dans l'ordre avec son compte d'administration ; ne pas changer la connexion PHP.

Le lanceur exige les dix tables RH existantes, les rôles RH/Finance canoniques, le correctif de collation de `hr_assert_permission` et des droits svc_php dans le périmètre prévu. Il refuse tout objet de rémunération ou propriétaire homonyme existant, sans suppression ni remplacement. Il vérifie ensuite tables, collations, propriétaires, verrouillage, routines, triggers et permissions. Le DDL MySQL n'est pas transactionnel globalement : après échec partiel, arrêter et demander une reprise ciblée ; ne rien supprimer et ne pas relancer aveuglément.

## Compte Finance distinct

Après activation, dans un terminal interactif :

```bash
sudo python3 bin/local-demo.py create-finance-demo --apply
```

Confirmer la cible puis saisir et confirmer **confidentiellement** un nouveau mot de passe (minimum 12 caractères). Le script emploie `password_hash(..., PASSWORD_ARGON2ID)` par entrée standard privée du processus PHP, sans fichier, argument de commande ni sortie contenant le mot de passe ou son empreinte.

Une transaction crée uniquement :

- la nouvelle personne fictive `DEMO-FIN-001`, Demo Finance ;
- son compte applicatif `finance.demo` ;
- une attribution immédiate du rôle existant Finance Manager.

Aucun compte MySQL de connexion supplémentaire, aucun rôle Finance sur `rh.demo`, aucune modification d'un employé existant. Les collisions de login ou matricule interrompent l'opération. Ne réutiliser aucun compte RH pour Finance. Cette opération de bootstrap est administrative et explicite ; l'application n'a pas de privilège d'attribution de rôles.

## Démarrage et démonstration navigateur

Dans le terminal de l'utilisateur Ubuntu habituel, sans sudo :

```bash
python3 bin/local-demo.py serve
```

Saisir le mot de passe MySQL existant de svc_php, conservé dans l'environnement du processus serveur, sans l'inscrire dans un fichier ou la ligne de commande. L'application reste sur **http://127.0.0.1:8080/login**. Si le serveur est déjà démarré avec les bonnes variables DB_*, les nouveaux fichiers sont utilisables directement ; arrêter l'ancien serveur avant d'en lancer un second sur le même port.

1. Se connecter avec `rh.demo` et son mot de passe existant.
2. Menu **Rémunérations → Employés avec contrat** : trouver Nadia Traoré, `EMP-2026-001`, contrat `CDI-EMP-2026-001-01`. Les données et ce contrat doivent déjà exister ; aucun seed de cette mission ne les crée ou ne les modifie.
3. Choisir **Proposer un salaire**. Pour ce salaire initial : **12000,00 MAD**, date **2026-11-03**, justification explicite. Vérifier matricule et contrat puis **Soumettre à Finance**. La demande apparaît en attente ; aucune condition salariale n'est encore enregistrée.
4. Se déconnecter puis se connecter avec `finance.demo` et le mot de passe saisi au terminal.
5. **Approbations Finance → Consulter** : contrôler employée, contrat, montant, date et demandeur. Saisir une justification puis **Approuver cette demande**. Le bouton de rejet est une décision distincte ; un rejet exige également une justification.
6. La fiche montre la décision, le décideur et les événements horodatés UTC. **Historique salarial** présente la condition approuvée et sa période. Reconnexion RH : la même décision est consultable. Le sélecteur FR/EN conserve la session.
7. Pour une révision, créer une autre demande avec une date au premier jour d'un mois, strictement postérieure à la dernière date approuvée du contrat. La précédente version demeure consultable.

Une double soumission peut produire deux demandes en attente, mais les deux ne peuvent pas créer une condition contradictoire : la seconde approbation est refusée et Finance peut rejeter explicitement la demande devenue obsolète. Après une interruption réseau, consulter la fiche avant de réessayer : le COMMIT peut déjà avoir réussi.

## Modèle et garanties

`compensation_requests` conserve montant DECIMAL(12,2), MAD pour les nouvelles données, date, contrat, justification et identité du demandeur, y compris son employee_id. Le statut est dérivé de l'absence ou de la présence de `compensation_decisions`, sans UPDATE caché de la demande.

`compensation_decisions` contient une seule décision irrévocable par demande (UNIQUE), avec justification et identité personnelle du décideur. `salary_conditions` contient une version immuable par approbation et une contrainte UNIQUE(employee_id,effective_on). `compensation_history` enregistre dans la même transaction soumission/approbation/rejet. Aucun historique n'est supprimé en cascade.

Les périodes salariales sont dérivées des points de changement : fin inclusive = veille de la prochaine condition du même contrat, bornée par la fin effective du contrat. Aucun UPDATE de l'ancien salaire pour enregistrer une révision. L'initial doit correspondre au début du contrat, même au milieu du mois ; une révision doit commencer un premier du mois et avancer la chronologie. Les rétroactivités supplémentaires et corrections d'un salaire approuvé exigeraient un futur workflow explicite ; cette version n'en fournit pas. Une première demande au début d'un contrat antérieur à aujourd'hui reste autorisée pour initialiser l'historique de démonstration.

Soumission et décision prennent le même verrou parent employees que les opérations RH, puis effectuent des lectures courantes FOR SHARE des contrats, conditions et décisions. Elles recontrôlent RBAC et incompatibilités par personne, la couverture contractuelle et l'état salarial à l'approbation. La décision, la condition éventuelle et l'événement sont atomiques. Les deadlocks/timeouts donnent une réponse de conflit à examiner avant nouvelle tentative, sans retry automatique. Aucun contrat existant n'est modifié par l'installation ; le nouveau trigger refuse seulement une clôture future qui rendrait invalide une date salariale déjà approuvée, y compris sous REPEATABLE READ.

Finance ne peut ni traiter la demande d'une autre identité de sa propre personne, ni décider son propre salaire. Une attribution active RH + Finance sur une même personne bloque l'accès au module côté PHP et ses commandes côté SQL. Les autres rôles n'y ont aucun accès. Les attributions expirées/révoquées ne donnent pas d'autorisation. Les attributions incompatibles actives sont prises en compte même sur un autre compte désactivé, pour éviter de contourner la séparation par une simple bascule de compte. Les autres incompatibilités organisationnelles (Paie/Audit, etc.) restent à définir dans les missions correspondantes.

## Permissions et séparation MySQL

| Permission | HR Manager | Finance Manager |
|---|---|---|
| compensation.read | Oui | Oui |
| compensation.submit | Oui | Non |
| compensation.decide | Non | Oui |

La lecture est globale à ce module pour ces deux rôles autorisés : demandes, décisions, montants et historique. Elle n'est pas limitée au seul demandeur ; aucun libre-service salarial pour les autres employés dans cette mission.

svc_php reçoit SELECT sur les quatre tables, EXECUTE uniquement sur `compensation_submit` et `compensation_decide`. Aucun INSERT, UPDATE, DELETE, DDL ou droit d'attribution de rôle. Le propriétaire verrouillé reçoit SELECT sur les colonnes d'identité/RBAC nécessaires (sans login ni empreinte), SELECT contrat, INSERT/SELECT et TRIGGER sur les quatre nouvelles tables, EXECUTE sur ses quatre routines, et TRIGGER sur employment_contracts. UPDATE(id) employees sert exclusivement au verrou FOR UPDATE, sans UPDATE exécuté sur les employés. Les triggers existants protègent également leur identifiant.

Ce droit de verrouillage est une exigence [MySQL 8.4 FOR UPDATE](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html). Le [verrouillage d'un compte propriétaire](https://dev.mysql.com/doc/refman/8.4/en/account-locking.html) interdit sa connexion sans empêcher ses objets DEFINER de fonctionner.

Le compte MySQL de service est partagé par les sessions web : l'identité métier provient exclusivement de la session PHP, jamais du POST. Une compromission de svc_php permettrait d'invoquer une procédure avec un autre actor_id : les contrôles PHP et la confidentialité du secret de service font partie de cette frontière de confiance existante. Le module ne prétend pas résister à la compromission du serveur applicatif, aux administrateurs SQL capables de changer les triggers/routines ou au DDL qui contourne les protections DML. Les décisions sont conservées en base mais ne constituent pas un journal externe inviolable. Le journal applicatif n'enregistre que l'événement et les identifiants techniques, jamais les montants, justifications, mots de passe ou requêtes.

## Vérifications et éléments non activés

Les vérifications réalisées hors connexion sont détaillées dans le compte rendu de livraison : syntaxe PHP/Python, concordance FR/EN, validations monétaires, matrice d'autorisation, rendu des vues et cohérence des objets SQL. Aucune validation syntaxique par le serveur MySQL ni écriture SQL n'a été effectuée sans autorisation.

Après l'activation autorisée, il reste à exécuter le parcours réel, un rejet, une double décision, un refus de date hors contrat et les scénarios concurrents avec deux sessions MySQL. Aucune réussite de ces tests MySQL n'est annoncée avant exécution.

Les primes/retenues, calcul mensuel, bulletins, paiements, rétractation d'une décision, corrections administratives de salaires et audit externe sont hors Mission 06A. Les quatre tables et les routines restent à activer avant de pouvoir soumettre une première demande réelle. Aucun mot de passe Finance n'existe avant le bootstrap interactif.

## Inventaire de livraison

Créés :

- `app/Compensation/CompensationRepository.php`, `CompensationValidation.php` ;
- `app/Web/CompensationController.php` ;
- `app/Views/compensation-nav.php`, `compensation-form.php`, `compensation-list.php`, `compensation-detail.php` ;
- `database/migrations/004_compensation.sql`, `005_compensation_operations.sql`, `006_mad_currency.sql` ;
- `database/seeds/005_compensation_permissions.sql` ;
- `database/setup/compensation_owner.sql`, `compensation_owner_grants.sql`, `compensation_grants.sql` ;
- `docs/COMPENSATION.md`.

Modifiés :

- `app/Auth/AuthService.php` : permissions Finance et contrôle du cumul par personne ;
- `app/Web/Controller.php`, `helpers.php` : routage et conservation de langue ;
- `app/Web/AdvancedHRController.php` : traduction du refus de clôture incompatible avec un salaire approuvé ;
- `app/Views/header.php`, `dashboard.php`, `employee.php` : navigation autorisée et historique depuis la fiche employé ;
- `lang/fr.php`, `lang/en.php` : nouveaux textes centralisés ;
- `public/assets/app.css`, `app.js` : tableaux adaptatifs, statuts, formulaires et validation localisée des zones de texte ;
- `bin/local-demo.py` : activation explicite, contrôles de droits et bootstrap Finance ;
- `README.md` : lien d'activation.

Contrôles effectivement exécutés avant activation : syntaxe de 37 fichiers PHP sans erreur ; syntaxe Python et aide CLI ; 100 vérifications essentielles hors connexion (montants, textes, six rôles, cumul, routes et traductions) ; 14 rendus FR/EN sur données de test échappées ; 8 exercices du véritable point d'entrée sans compte (redirections anonymes, CSRF, méthode et chemin refusés) ; vérification de la liste des privilèges permis/refusés et des gardes `--apply` ; cohérence statique des quatre tables, neuf triggers, quatre procédures et de leurs transactions/collations. Ces exercices ne remplacent pas les tests MySQL réels. Le contrôle JavaScript par `node --check` n'a pas pu être effectué car Node.js n'est pas installé ; aucun paquet n'a été installé.

## Devise officielle MAD

La devise de référence est désormais le dirham marocain (MAD). Les nouvelles demandes utilisent MAD et les historiques affichent la devise réellement enregistrée, avec deux décimales. Les migrations 004/005 sont conservées comme étapes historiques, suivies de 006 ; ne pas les rejouer sur une installation existante. Voir [CURRENCY-MAD.md](CURRENCY-MAD.md) pour la mise à jour d’un module déjà installé et le traitement des anciens enregistrements UM. Les futurs bulletins devront utiliser la devise de leur donnée source et le formateur `App\Finance\Money`, sans réétiquetage ni conversion automatique.
