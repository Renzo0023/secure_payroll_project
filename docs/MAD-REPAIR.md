# Correction ciblée MAD sur une installation existante

Ne rejouer aucune migration. Ne lancer aucune installation de module dans cette
intervention. Les fichiers 002 et 003 constituent un seul correctif à exécuter
par `bin/mad-repair.py`, jamais séparément sur la principale.

Le schéma accepte MAD pour les nouvelles écritures et UM pour conserver les
historiques. `compensation_submit` écrit MAD ; `compensation_decide` approuve
uniquement MAD et en copie la devise. `compensation_check_period` refuse une
révision implicite d'un ancien salaire UM. Les corps, signatures et propriétaires
existants sont vérifiés avant remplacement ; un corps personnalisé est refusé.
Les privilèges de procédure supprimés par DROP sont restitués exactement depuis
le relevé initial, sans attribution de nouveaux droits. Les autres procédures,
triggers, permissions RBAC, montants et lignes historiques sont comparés avant/après.

Les vues PHP de rémunération lisent la devise de chaque ligne ; Money conserve
UM à l'affichage. Aucun changement PHP financier n'est nécessaire.

## Commandes Ubuntu avant toute autorisation de modification

Arrêter le serveur de l'application (Ctrl+C dans son terminal) et suspendre tous
les autres producteurs d'écritures et de DDL. Garder cette maintenance jusqu'à la
fin des contrôles. Dans le même terminal pour les commandes suivantes :

```bash
cd /home/projets/projects/database-security
sudo python3 bin/mad-repair.py inspect
umask 077
mad_backup_dir="$PWD/storage/mad-repair-$(date -u +%Y%m%dT%H%M%SZ)"
sudo python3 bin/mad-repair.py prepare --directory "$mad_backup_dir" --maintenance-confirmed
python3 bin/mad-repair.py rehearse --directory "$mad_backup_dir"
```

Arrêter la séquence dès qu'une commande échoue. `inspect` affiche les comptages
exacts et la reconnaissance des trois routines. `prepare` ne modifie pas MySQL :
il réalise un dump cohérent InnoDB incluant routines, triggers et événements,
avec SHA256 et relevé des droits dans un nouveau répertoire privé. Le répertoire
est rendu à l'utilisateur sudo appelant pour permettre le test sans sudo.

`rehearse` initialise une instance MySQL 8.4 privée sans réseau dans /var/tmp,
restaure ce dump, recrée les comptes propriétaires verrouillés et leurs droits
dans cette copie seulement, compare les données et définitions, puis y applique
le correctif complet. Le reçu `restoration-verified.json` atteste le test de
restauration et du correctif sur cette sauvegarde précise. La copie est arrêtée
à la sortie et ses fichiers conservés. Aucun compte système MySQL n'est restauré
sur la principale. Conserver le répertoire de sauvegarde sur un support durable.

## Application après autorisation explicite seulement

Présenter les résultats précédents et demander l'autorisation de modifier la
principale. Une fois cette autorisation donnée, exécuter :

```bash
sudo python3 bin/mad-repair.py apply --directory "$mad_backup_dir" --maintenance-confirmed
sudo python3 bin/payroll-admin.py diagnose-mad
sudo python3 bin/payroll-admin.py inspect
```

Le lanceur demande de saisir exactement `REPAIR-MAD secure_payroll`. Il refuse
si le reçu manque, si les fichiers ont changé ou si l'état, les données ou les
droits ont changé depuis la sauvegarde. Il compare après correction les
empreintes des quatre tables financières et leurs comptages. L'objectif final
est le succès de `inspect`, y compris les CHECK et les trois routines MAD.
Aucun module Paie/Bulletins/Paiements/IAM n'est installé par ces commandes.

## Restauration et arrêt sur erreur

Les ALTER et DROP/CREATE font des commits implicites : ROLLBACK ne suffit pas.
Si une étape échoue, conserver maintenance, sauvegarde et état intermédiaire ;
ne pas relancer une migration ou importer le dump sur la principale. Un import
complet contient des DROP TABLE et nécessite une autorisation distincte ; il
pourrait supprimer des écritures ultérieures. Le chemin de restauration testé
est `rehearse` ci-dessus, vers une nouvelle instance isolée. Le dump ne sauvegarde
pas les comptes MySQL globaux : leurs droits utiles sont relevés dans plan.json.
Toute récupération de la principale doit être préparée depuis ce relevé et
autorisée séparément après examen de l'étape qui a échoué.

## Campagne représentative reproductible

```bash
python3 lab/mysql-mad-repair.py
php tests/compensation-unit.php
```

Le laboratoire crée une installation fictive 001–005 dans une nouvelle instance,
sans rejouer ces migrations sur la principale. Il conserve une demande UM en
attente et un salaire UM approuvé, sauvegarde/restaure, applique le correctif,
vérifie une nouvelle demande et une approbation Finance MAD, les refus RBAC,
l'immutabilité, la conservation des historiques et un deuxième passage sans
modification. Ces résultats ne remplacent pas la restauration du dump réel.

Validation du 6 novembre 2026 : 22 contrôles de correctif/sauvegarde/restauration,
8 contrôles PHP du parcours UM, 19 du parcours MAD et 45 contrôles PHP hors SQL
réussis. La commande `inspect` complète a réussi sur la copie, avec 0/6 tables
Paie ; le retrait d'un CHECK dans la copie a bien fait échouer son prérequis.
Résultat conservé dans
`/var/tmp/securepayroll-mysql-ju0a3n94/mad-repair-result.json`.
Les comptages fictifs avant correction étaient 2 demandes et 1 condition salariale.
Ils ne sont pas ceux de la principale : son accès sudo exige ici une saisie
interactive indisponible à l'agent. Aucun DDL principal, aucune installation et
aucune commande Git n'ont été exécutés. La sauvegarde réelle et son essai de
restauration restent donc à effectuer avec les commandes ci-dessus.
