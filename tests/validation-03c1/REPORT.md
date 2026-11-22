# Mission 03C-1 — préparation terminée, validation MySQL bloquée

> **Historique de la première préparation.** La dernière revue et les préconditions
> définitives figurent dans [FINAL-REVIEW.md](FINAL-REVIEW.md). Le lanceur refuse
> désormais root système et MySQL, exige des droits limités au schéma de validation
> et un profil client privé préexistant. L’ancien chemin administratif est supprimé.

## Résultat constaté

L’authentification administrative locale n’a pas pu être effectuée depuis cette
session. La commande non interactive, après sortie du bac à sable, a répondu :

```text
sudo: interactive authentication is required
```

La première tentative dans le bac à sable avait été refusée par le drapeau
`no new privileges`. Aucun mot de passe n’a été demandé par le code, affiché ou
enregistré. Aucune requête n’a atteint MySQL via ces tentatives.

**Existence de `secure_payroll_validation_03b` : inconnue.** Aucune base n’a été
créée, modifiée, nettoyée ou supprimée. La base principale n’a pas été sélectionnée.
Le client installé annonce 8.4.11 ; la version effective du serveur n’a pas été
interrogée. PHP CLI annonce 8.5.4, avec pdo_mysql et POSIX disponibles.

## Fichiers préparés

- `validate.py` : préparation hors connexion par défaut ; `--run` active les
  opérations MySQL autorisées pour cette mission, après vérification de la cible.
- `admin-connection.php` : nom historique du harnais désormais non-root ; voir la
  dernière revue pour sa politique de privilèges et ses variables privées.
- `generated/001_create_identity_and_rbac.sql` et
  `generated/001_application_roles.sql` : copies dont seul le USE est adapté.
- `generated/database-structure.php` et `generated/database-integrity.php` : copies
  des tests adaptées à la cible et au harnais administratif isolé.
- `generated/sources.sha256` : empreintes des quatre sources pour traçabilité.

Les migrations originales, les tests originaux et `config/database.php` sont
inchangés. Les fichiers SQL originaux contiennent `USE secure_payroll` et ne
doivent pas être utilisés directement pour cette campagne. Le vérificateur
structurel original exige la base principale ; le test d’intégrité original
exige `secure_payroll_test_integrity` et des tables vides : leur utilisation
directe ne convient donc pas à la mission 03C-1.

Les copies remplacent exclusivement ces gardes et la connexion, conservent les
assertions d’intégrité et utilisent le seed adapté. Le catalogue de rôles étant
déjà alimenté par les deux exécutions complètes du seed, la copie du test exige
que les cinq autres tables soient vides, et vérifie six rôles existants au lieu
de six nouvelles insertions. Le lanceur vérifie les rôles canoniques avant ce
test, puis leurs identifiants et libellés après son ROLLBACK. Les essais de
retrait/réinsertion d’un rôle se font uniquement dans cette transaction annulée.

## Contrôles effectivement exécutés hors connexion

| Contrôle | Résultat |
| --- | --- |
| Examen des six fichiers demandés et de la classe PDO | Effectué |
| `python3 tests/validation-03c1/validate.py --prepare` | Réussi, copies générées |
| Vérification des USE des deux copies SQL et absence de référence SQL exécutable à la base principale | Réussie |
| `php tests/sql-static.php` | 93 contrôles réussis |
| `php -l` sur les fichiers PHP, copies et harnais inclus | 12 fichiers valides |

Ces résultats ne constituent pas une validation de syntaxe SQL par MySQL.

## Résultats MySQL : non exécutés

| Élément | Attendu d’après les fichiers | Constat serveur |
| --- | --- | --- |
| Tables | employees, accounts, roles, permissions, role_permissions, role_assignments | Non vérifié |
| Moteur / collation | Six InnoDB / utf8mb4_0900_as_cs | Non vérifié |
| Clés primaires | 6 | Non vérifié |
| Contraintes UNIQUE hors PK | 7 | Non vérifié |
| Clés étrangères RESTRICT | 7 | Non vérifié |
| CHECK actifs | 12 | Non vérifié |
| Total des contraintes de table | 32 | Non vérifié |
| Triggers BEFORE | 7 | Non vérifié |
| Premier seed | Six couples canoniques | Non exécuté |
| Deuxième seed | Six couples et mêmes identifiants | Non exécuté |

| Test d’intégrité | État |
| --- | --- |
| Matricule dupliqué refusé | Non exécuté |
| Modification du matricule refusée | Non exécuté |
| Suppression d’employé refusée | Non exécuté |
| Empreinte invalide refusée / Argon2id éphémère acceptée | Non exécuté |
| Attribution planifiée valide | Non exécuté |
| Attribution immédiate, égalité granted_at / valid_from | Non exécuté |
| Attribution rétroactive, expiration invalide, insertion pré-révoquée refusées | Non exécuté |
| Première révocation acceptée / révocation future refusée | Non exécuté |
| Deuxième révocation refusée | Non exécuté |
| Modification et annulation d’une attribution révoquée refusées | Non exécuté |
| UPDATE sans changement après révocation accepté | Non exécuté |
| Noms, archivage, login, désactivation/réactivation légitimes acceptés | Non exécuté |
| Réaffectation/suppression du compte et suppression d’attribution refusées | Non exécuté |
| Session non UTC refusée | Non exécuté |
| Seed : rôle manquant, collision incohérente, septième rôle refusé | Non exécuté |

Aucune erreur MySQL n’a été observée : aucune exécution SQL n’a eu lieu.
Le lanceur affichera les erreurs du client mysql et les codes des exceptions
PDO, sans mot de passe ni empreinte d’authentification. Les réussites individuelles
ne seront affichées qu’après exécution des scénarios correspondants.

## Commande future — après revue des nouvelles préconditions

Depuis le projet, avec l’environnement privé et le profil client préexistant
décrits dans FINAL-REVIEW.md, sous un utilisateur ordinaire :

```sh
cd secure_payroll_project
python3 tests/validation-03c1/validate.py --run
```

Cette commande n’est pas exécutée dans la dernière revue. Elle ne lit pas de
mot de passe interactif et ne crée aucun compte ou profil client. Si les
préconditions ne sont pas remplies, elle s’arrête sans élévation de privilèges.

Le lanceur :

1. Régénère et contrôle les copies, puis vérifie la version serveur.
2. Interroge uniquement l’existence de la base de validation et s’arrête si elle
   existe, sans la réutiliser ni la supprimer.
3. Crée la base si absente, sans `IF NOT EXISTS`, puis applique la migration adaptée.
4. Exécute deux fois le seed adapté et compare les identifiants/codes/libellés.
5. Affiche tables, moteurs, collations, nombres de contraintes et sept triggers.
6. Exécute le vérificateur structurel adapté et les scénarios d’intégrité, puis
   vérifie les six rôles conservés et l’absence de données d’essai résiduelles.

À la première erreur, il s’arrête et conserve la base dans son état pour analyse.
Il ne faut pas le relancer aveuglément : il refusera une base déjà créée, même
partiellement. Aucun DROP, TRUNCATE, purge finale ou compte MySQL n’est créé.
Les compteurs AUTO_INCREMENT peuvent avancer malgré le ROLLBACK des tests.
Ne pas utiliser cette base simultanément depuis une autre session d’écriture.

## Conclusion et limites

**L’application à `secure_payroll` n’est pas encore validée.** Il faut d’abord
exécuter la commande manuelle, examiner ses résultats et corriger toute erreur
réellement constatée. Aucune correction de migration supplémentaire n’est
affirmée nécessaire ou inutile en l’absence de cette exécution.

La campagne administrative ne valide pas le fonctionnement sous les futurs
comptes à privilèges minimaux. Les incompatibilités de rôles, approbations
indépendantes, attributions aux comptes désactivés, chevauchements et concurrence
restent hors des garanties actuelles. Les limites face aux privilèges DDL,
à la suppression des triggers et à la surcharge de l’horloge SQL subsistent.
