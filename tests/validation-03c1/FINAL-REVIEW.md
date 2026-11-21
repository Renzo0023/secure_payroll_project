# Dernière revue du lanceur — exécution non autorisée à ce stade

Cette revue remplace les instructions d’accès administratif du rapport précédent.
Aucune commande SQL, sudo ou Git n’a été lancée. `--run` n’a pas été lancé.
Aucune base, donnée, identité SQL ou configuration système n’a été modifiée.

## Versions à examiner

Les trois sources suivantes sont conservées strictement inchangées :

- `database/migrations/001_create_identity_and_rbac.sql` ;
- `database/seeds/001_application_roles.sql` ;
- `tests/database-integrity.php`.

`tests/validation-03c1/validate.py` est corrigé. Il génère des copies isolées dans
`generated/`, dont `database-integrity.php` est la version adaptée à examiner avant
la campagne 03C-1. La source originale reste dédiée à `secure_payroll_test_integrity`
et n’est pas lancée directement par cette campagne. Aucune adaptation de cible n’a
été appliquée aux migrations originales. Les empreintes des quatre sources sont
enregistrées dans `generated/sources.sha256` ; elles identifient les sources sans
prétendre fournir une protection cryptographique contre un administrateur.

## Résultats et messages OK

Le générateur ne préfixe plus un scénario par un message de réussite du scénario
précédent. Il enregistre les blocs terminés, identifie séparément les préparations
d’employé, d’empreinte, d’acteur et de rôles, puis affiche les messages individuels
seulement après réussite de tous les blocs et du ROLLBACK. Un retour false ou une
exception au rollback empêche l’affichage de tous les OK. Les retours à la ligne
sont de vrais retours à la ligne, pas les caractères littéraux `\\n`.
Si un scénario échoue, son nom est signalé, sans message PDO brut. Les codes MySQL
attendus sont contrôlés : une erreur de connexion ou de syntaxe ne vaut pas succès.
Les tests hors connexion du reporting utilisent un objet factice, jamais MySQL.

## Audit des écritures de database-integrity.php

| Écriture | Périmètre et raison |
| --- | --- |
| INSERT du seed / variante avec libellé incohérent | Table roles uniquement ; vérification de l’idempotence, du rôle manquant et des collisions |
| DELETE d’un rôle non référencé | Retrait de security_auditor dans la transaction pour vérifier sa réinsertion ; le rollback restaure l’identifiant initial |
| INSERT d’employés et de comptes | Fixtures TEST-001 / TEST-002, login de test, empreinte Argon2id éphémère en mémoire |
| UPDATE / DELETE d’employés | Échecs attendus sur matricule/suppression ; changements légitimes des noms et de l’archivage |
| UPDATE / DELETE de comptes | Échecs attendus sur réaffectation/suppression ; changements légitimes de login et d’état |
| INSERT / UPDATE / DELETE d’attributions | Tests de dates, octroi immédiat, première révocation, immutabilité et suppressions interdites |
| SET SESSION | Fuseau UTC, test non UTC puis retour UTC, mode strict ; aucune variable globale changée |
| START TRANSACTION / ROLLBACK via PDO | Toutes les écritures de données du test sont annulées, succès comme échec normal |

Toutes les tables des DML sont non qualifiées et appartiennent à la connexion
contrôlée. Le seed est extrait comme une seule instruction INSERT : ni USE ni
COMMIT du fichier ne sont exécutés par le test. Aucun ALTER, DROP, TRUNCATE,
CREATE USER, GRANT, écriture de fichier SQL ou commande système n’est présent dans
le test d’intégrité. Les appels `exec` sont des méthodes PDO, pas la fonction PHP
d’exécution système. Les backticks du SELECT COUNT citent un identifiant SQL ;
ils ne constituent pas une commande shell PHP.

La copie exige cinq tables sans données applicatives et six rôles préalablement
contrôlés par le lanceur. Le lanceur refuse une base déjà existante avant création.
Les essais ne doivent pas être concurrents avec d’autres écritures. ROLLBACK ne
restaure pas les compteurs AUTO_INCREMENT et le DDL de migration n’est pas annulé.
Aucune purge finale, suppression de base ou nettoyage des données existantes
n’est programmé.

## Isolation et privilèges : root n’est plus utilisé

Le lanceur et le helper PHP refusent root système. Le helper refuse DB_USER=root,
une identité CURRENT_USER root, tout rôle actif et tout GRANT de rôle. Il ne
sélectionne aucune base avant le contrôle des droits. Après contrôle, il sélectionne
uniquement `secure_payroll_validation_03b` et revérifie DATABASE(). Les requêtes
multiples PDO sont désactivées. Le client mysql commence dans information_schema,
puis utilise uniquement la copie SQL adaptée.

Les grants acceptés sont exclusivement USAGE global, puis la liste ci-dessous
au niveau du seul schéma de validation. Tout droit global supplémentaire, autre
base, droit de routine/table hors du modèle, GRANT OPTION, PROXY, DROP, ALTER,
FILE, SUPER ou rôle est refusé. La politique est volontairement conservatrice :
un format de grant inconnu provoque un arrêt, jamais une autorisation implicite.
Les jokers `_` et `%` non échappés sont refusés lorsque partial_revokes est OFF ;
sinon ces caractères sont interprétés littéralement par MySQL. Aucun compte ou
privilège n’est créé/modifié par le lanceur.

| Droits requis sur le seul schéma cible | Justification |
| --- | --- |
| CREATE | Créer la base absente et les six tables |
| TRIGGER | Créer les sept triggers et contrôler leurs métadonnées |
| REFERENCES | Créer les clés étrangères |
| SELECT | Contrôles de structure, de valeurs et des fixtures |
| INSERT, UPDATE, DELETE | Seed et scénarios d’intégrité, dont les refus attendus et le rôle temporairement manquant |

CREATE et TRIGGER concernent la phase migration ; les scénarios de données n’en
ont pas eux-mêmes besoin. Le compte unique retenu est limité au seul schéma pour
la campagne entière. Aucun privilège système root n’est indispensable à ces
opérations si un compte MySQL approprié existe déjà.

**Exception à examiner avant la campagne :** si le journal binaire est actif et
`log_bin_trust_function_creators=0`, MySQL peut exiger SUPER pour CREATE TRIGGER.
Le lanceur détectera cette condition et s’arrêtera avant CREATE DATABASE. Il
n’accordera pas SUPER, ne changera pas la variable et ne relancera rien avec root.
Une décision DBA séparée serait alors nécessaire pour la seule phase DDL dans
un environnement approprié ; les tests PHP doivent rester sans privilèges globaux.
Le lanceur actuel ne prétend donc pas pouvoir fonctionner dans cette configuration
sans une décision préalable du relecteur.

L’isolation suppose les privilèges constatés stables et les fichiers relus inchangés
pendant la campagne. Un administrateur capable de changer grants, triggers ou
fichiers reste hors de cette garantie. Le compte n’a aucun droit d’écriture sur
secure_payroll ou une autre base utilisateur ; information_schema est consulté
en lecture seule. Le test original reste inchangé et ses gardes d’origine ne
remplacent pas ce contrôle de privilèges : utiliser les copies via le lanceur.

## Environnement futur, sans secret dans le dépôt

Aucune de ces préconditions n’a été configurée ou testée sur le serveur dans cette
revue. Pour une future exécution autorisée uniquement :

- Utilisateur système ordinaire ; aucune invocation sudo.
- Variables DB_* privées pour un compte non-root : DB_HOST=localhost,
  DB_NAME=secure_payroll_validation_03b, et les autres valeurs configurées hors Git.
- Profil client mysql privé préexistant nommé secure_payroll_validation_03b,
  pour exactement le même compte sur le même serveur. Le lanceur compare
  CURRENT_USER et server_uuid entre PDO et le client avant toute écriture.
- Compte limité aux droits du tableau ; aucun compte permanent n’est créé ici.
- Politique de création des triggers compatible, comme expliqué ci-dessus.

Le helper réutilise la lecture des variables et la validation de configuration,
sans modifier config/database.php. Il n’écrit aucun fichier d’identifiants.
Le client reçoit un nom de profil, jamais un mot de passe en argument ; les
variables DB_PASSWORD et MYSQL_PWD sont retirées de son environnement. Aucun
message PDO brut, traceback de connexion ou empreinte de mot de passe n’est
affiché. Le lanceur transmet uniquement les codes d’erreur du client mysql.

## Six couples exacts du seed

| Code | Libellé |
| --- | --- |
| employee | Employee |
| hr_manager | HR Manager |
| payroll_manager | Payroll Manager |
| finance_manager | Finance Manager |
| application_administrator | Application Administrator |
| security_auditor | Security Auditor |

Le générateur compare les six couples source à cette liste exacte, avec refus
des doublons et de tout couple supplémentaire/manquant. Après chaque seed futur,
le lanceur vérifiera codes/libellés, unicité des identifiants et nombre de lignes ;
la deuxième exécution devra aussi conserver les mêmes identifiants. La contrainte
ck_roles_canonical de la migration et l’anti-jointure exacte du seed restent inchangées.

## Contrôles exécutés pendant cette revue

- Sept tests unitaires du lanceur réussis, sans connexion ni commande mysql.
  Ils couvrent notamment les couples source et les snapshots invalides, les
  précontrôles, les cibles des copies, le reporting avec rollback simulé
  réussi/refusé/exception, l’audit des DML et la politique de grants sur chaînes.
- Deux exemples de grants limités admis et sept cas dangereux/incomplets refusés
  par le helper testé sans créer de PDO.
- 93 contrôles statiques SQL réussis.
- Syntaxe PHP valide pour les 13 fichiers, copies et helpers compris.
- Préparation des copies et vérification de leurs cibles, sans --run.

Le SQL n’a pas été parsé/exécuté par MySQL. Les connexions réelles, grants réels,
triggers, cas d’intégrité et privilèges minimaux restent à valider après revue.
L’application de la migration à secure_payroll n’est toujours pas validée.
Les limites IAM (incompatibilités, approbations indépendantes, comptes désactivés,
chevauchements et concurrence) restent celles documentées précédemment.

Références : [GRANT MySQL 8.4](https://dev.mysql.com/doc/refman/8.4/en/grant.html),
[CREATE TRIGGER MySQL 8.4](https://dev.mysql.com/doc/refman/8.4/en/create-trigger.html).
