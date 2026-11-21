# Démarrage RH local — mission 04B

## Commandes minimales après revue

```sh
cd ~/projects/database-security
sudo python3 bin/local-demo.py install --apply
python3 bin/local-demo.py check
python3 bin/local-demo.py serve
```

Ne pas lancer la dernière commande avant succès du contrôle et arrêt du précédent
serveur de développement sur le port 8080 (Ctrl+C dans son terminal).
Installation uniquement une fois ; check et serve sont réutilisables sans sudo.
L’option `--lang en` est disponible pour les messages CLI anglais.

## Ce que fait l’installation

Le script exige `--apply`, un accès administratif local explicite par sudo et
une confirmation de cible en saisissant `secure_payroll`. Il utilise le client
mysql en mode batch sur le socket local, avec l’identité administrative locale.
**PHP ne se connecte jamais comme root** : il sert uniquement à calculer Argon2id
pendant l’installation. Le serveur et le contrôle PDO sont lancés sans sudo,
avec svc_php. Aucun réglage Apache/PHP/MySQL système n’est modifié.

Il vérifie d’abord les six tables InnoDB, le rôle HR Manager existant et l’absence
de svc_php, rh.demo et DEMO-HR-001. Tout compte svc_php existant, quel que soit son
hôte, entraîne un arrêt sans altération des comptes/grants existants. Des rôles
MySQL obligatoires entraînent aussi un arrêt pour revue de leur périmètre.

L’opérateur saisit deux mots de passe distincts, chacun deux fois :

1. Mot de passe SQL de svc_php : utilisé par le processus PHP pour accéder à MySQL.
2. Mot de passe web de rh.demo : utilisé exclusivement dans le formulaire de connexion.

Ils doivent avoir au moins 12 caractères, sans caractères de contrôle. La saisie
est masquée et exige un terminal interactif. Aucun secret n’est passé dans les
arguments de commande, affiché, ajouté à l’historique ou écrit dans un fichier.
Le mot de passe web passe à password_hash(..., PASSWORD_ARGON2ID) par un pipe privé,
jamais par un argument PHP. Seule son empreinte est insérée dans accounts.
Les messages MySQL bruts sont masqués pour ne pas réafficher une requête sensible.

L’installation applique le **seul seed 002** ; il contient exactement les codes
employees.read, employees.create et employees.update utilisés par le contrôleur.
Elle vérifie ensuite leurs liens au rôle hr_manager. Le seed 002 existant a été
examiné et ne nécessite pas de modification pour ce parcours. La migration 001
et le seed des six rôles ne sont jamais exécutés.

Elle crée svc_php@localhost et applique database/setup/svc_php_grants.sql. Elle
crée ensuite, dans une transaction, l’employé fictif Demo RH, matricule DEMO-HR-001,
son compte rh.demo et une attribution immédiate du rôle HR Manager. granted_at et
valid_from utilisent le même CURRENT_TIMESTAMP(6) dans la même instruction UTC.
L’auteur d’attribution est NULL uniquement pour cette initialisation explicitement
autorisée ; le motif d’initialisation est enregistré. Aucun workflow d’approbation
ou nouveau rôle n’est ajouté.

Les DCL CREATE USER / GRANT ne sont pas annulables avec la transaction métier.
Si une étape ultérieure échoue, les opérations précédentes peuvent rester validées.
Le script s’arrête, n’efface rien et refuse une nouvelle exécution en présence de
collisions. Faire examiner l’état par le responsable MySQL avant une reprise ciblée ;
aucun DROP USER, suppression ou réinitialisation de mot de passe n’est automatisé.

## Privilèges de svc_php

| Relation | Lecture | Écriture |
| --- | --- | --- |
| employees | Toutes les colonnes existantes, recherche, COUNT et détail | INSERT employee_number/first_name/last_name ; UPDATE first_name/last_name |
| accounts | id, employee_id, login, password_hash, disabled_at | Aucune |
| roles | id, code, name | Aucune |
| permissions | id, code | Aucune |
| role_permissions | role_id, permission_id | Aucune |
| role_assignments | account_id, role_id, valid_from, expires_at, revoked_at | Aucune |

Aucun privilège global, DDL, DELETE, GRANT OPTION, privilège sur mysql.* ou sur une
autre base ; aucun droit de création/modification de compte ou d’attribution de rôle.
Les triggers existants s’exécutent avec leur DEFINER existant : ses droits doivent
être valides, aucun nouveau droit TRIGGER n’est accordé au compte applicatif.

## Raccordement et contrôle

check et serve demandent le mot de passe SQL sans l’enregistrer. Ils construisent
uniquement dans l’environnement du processus : DB_HOST=localhost, DB_PORT=3306,
DB_NAME=secure_payroll, DB_USER=svc_php, DB_PASSWORD=saisie confidentielle. Le fichier
.env n’est ni créé ni chargé. Le mot de passe reste dans la mémoire/environnement
du processus pendant sa durée de vie ; ne pas afficher son environnement.

check demande aussi le mot de passe web de rh.demo. Il utilise la classe PDO,
AuthService et EmployeeRepository existants pour vérifier une authentification
réelle, les trois permissions RH, l’annuaire et la fiche. La session du contrôle
est isolée dans un répertoire temporaire privé puis détruite ; aucun cookie ou
raccourci d’authentification web n’est créé. Il ne crée pas d’autre employé.

Le serveur démarre ensuite sur **http://127.0.0.1:8080/login**. Dans le navigateur :

1. Saisir rh.demo et le mot de passe web choisi.
2. Ouvrir le tableau de bord RH puis Employés.
3. Ajouter un employé avec un autre matricule unique.
4. Après validation, la fiche créée s’ouvre directement et figure dans l’annuaire.

Les interfaces restent bilingues FR/EN. Les logins SQL et web sont distincts.
Le limiteur web conserve cinq tentatives par IP en quinze minutes ; le contrôle
CLI ne consomme pas ce quota. En cas de quota atteint, attendre son expiration.

## État de validation et blocages possibles

Les fichiers sont préparés et les contrôles de syntaxe sont effectués hors
connexion. **L’installation administrative et le parcours MySQL réel ne sont pas
exécutés par l’assistant.** L’opérateur doit valider puis lancer les commandes.
L’accès administratif local par socket doit être disponible ; sinon faire
exécuter la préparation par le responsable MySQL, sans fournir ses secrets.

Un port 8080 occupé impose d’arrêter l’ancien serveur, pas de le tuer automatiquement.
Un compte/matricule déjà présent, un mot de passe refusé par la politique MySQL,
un schéma différent ou un DEFINER invalide nécessitent une revue ciblée. Le code
d’erreur numérique est fourni sans secret ; aucune migration n’est rejouée.

Références : [privilèges par colonne](https://dev.mysql.com/doc/refman/8.4/en/grant.html)
et [mots de passe et journaux MySQL](https://dev.mysql.com/doc/refman/8.4/en/password-logging.html).
Les commandes CREATE USER sont normalement réécrites par MySQL dans ses journaux ;
ne pas utiliser un environnement de diagnostic configuré pour enregistrer le SQL
brut avec --log-raw lors de cette préparation confidentielle.
