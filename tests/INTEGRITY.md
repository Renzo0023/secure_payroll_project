# Tests d’intégrité du socle — validation en laboratoire isolé

Le 6 novembre 2026, `python3 lab/mysql-integrity.py --initialize-isolated` a
réellement exécuté les tests sur MySQL 8.4.11 dans un datadir neuf, sans réseau,
avec un compte non-root limité au schéma de test. Les **33 assertions ont réussi**.
Les six tables sont vides après ROLLBACK, vérification faite par le lanceur.
Le résultat est conservé dans
`/tmp/securepayroll-mysql-ngwaym9u/integrity-result.json`. Aucune connexion à
l’instance principale n’a été effectuée. Le lanceur crée automatiquement le
schéma vide et adapte uniquement le `USE` d’une copie en mémoire de la migration.
Il conserve données et journaux et arrête son propre serveur par SQL SHUTDOWN.

Les instructions historiques ci-dessous décrivent les préconditions du test PHP
direct ; le lanceur isolé les prépare désormais sans installation principale.

`sql-static.php` fonctionne hors connexion. `database-integrity.php` est un
test d’écriture transactionnel, pas une migration.

## Préconditions pour une future campagne autorisée

Un opérateur devra préparer séparément une base **vide**, nommée exactement
`secure_payroll_test_integrity`, sur MySQL 8.4.11, avec les six tables et sept
triggers de la migration corrigée. Il faudra adapter le `USE` d’une copie de la
migration exclusivement à cette base ; le script de test ne prépare aucun schéma.
Ne jamais utiliser directement la migration qui contient `USE secure_payroll` pour
préparer cette base de test. Aucune préparation de ce type n’est effectuée ici.

Configurer les cinq variables DB_* en privé pour cette base, avec un compte non-root
autorisé à lire et à écrire les données de test. Pas d’autre session d’écriture
sur cette base pendant les essais. Les six tables doivent être InnoDB et vides,
y compris `roles`. Les rôles sont créés par le scénario du seed, pas avant.

Commande PHP appelée par le lanceur sur sa seule instance privée :

```sh
php tests/database-integrity.php --run --confirm-test-database
```

Sans les options exactes ou avec un autre DB_NAME, le script sort avant connexion.
Il vérifie le nom renvoyé par MySQL et refuse un schéma déjà peuplé. La session
utilise UTC et le mode strict. Il ne crée aucun compte ni objet SQL. Pour tester
le seed réel sans changer de base ou commettre la transaction, il extrait uniquement
son instruction INSERT ; il n’exécute ni le USE, ni le START TRANSACTION, ni le COMMIT
du fichier. La vérification de l’enveloppe complète par le client mysql reste à
effectuer séparément dans un environnement de test autorisé.

## Scénarios et résultats attendus

| Scénario | Résultat attendu |
| --- | --- |
| Premier seed sur catalogue vide | Six rôles insérés |
| Nouvelle exécution du seed | Zéro insertion, mêmes identifiants et libellés |
| Seed après retrait d’un rôle non référencé | Seul le rôle absent est inséré |
| Seed dont la source contient un libellé incohérent | Erreur UNIQUE/CHECK, aucun écrasement |
| Septième rôle | Rejet par le CHECK du catalogue fermé |
| Matricule dupliqué | Erreur UNIQUE |
| Modification d’un matricule existant | Erreur du trigger |
| Suppression d’un employé | Erreur du trigger |
| Modification du nom et archivage/désarchivage | Acceptés |
| Compte avec empreinte invalide | Erreur CHECK |
| Compte avec empreinte Argon2id éphémère générée en mémoire | Accepté |
| Réaffectation ou suppression d’un compte | Erreur du trigger |
| Changement de login, désactivation/réactivation | Acceptés |
| Attribution valide, planifiée, avec expiration | Acceptée |
| Attribution immédiate sans dates explicites | Acceptée, granted_at = valid_from à la microseconde |
| Octroi antidaté, même avec valid_from antidaté | Erreur du trigger |
| valid_from antérieur à l’octroi courant | Erreur CHECK |
| Expiration égale au début | Erreur CHECK |
| Insertion déjà révoquée | Erreur du trigger |
| Révocation future | Erreur du trigger |
| Première révocation avec acteur et motif | Acceptée, y compris avant valid_from |
| Deuxième révocation avec changement effectif | Erreur du trigger |
| Modification d’une attribution révoquée | Erreur du trigger |
| Annulation d’une révocation | Erreur du trigger |
| UPDATE strictement identique après révocation | Accepté, données inchangées |
| DELETE d’attribution ou prolongation en place | Erreur du trigger |
| Attribution depuis une session non UTC | Erreur du trigger |

Les échecs attendus vérifient le code MySQL : 1062 pour UNIQUE, 3819 pour CHECK,
1644 pour SIGNAL. Une erreur de syntaxe, de connexion ou de privilège n’est pas
considérée comme un rejet métier réussi. Les détails PDO et les valeurs
d’authentification ne sont pas affichés.

Les données de test sont annulées par ROLLBACK, au succès comme à l’échec normal.
Les compteurs AUTO_INCREMENT peuvent avancer malgré l’annulation : ces tests ne
sont donc jamais destinés à la base réelle. Les messages de succès n’attestent
que les assertions effectivement exécutées. Un contrôle textuel ne prouve ni la
compatibilité SQL, ni le comportement des triggers.

Restent à tester séparément : concurrence du seed et des octrois, périodes qui se
chevauchent, bascules d’expiration à la microseconde, comportement du client mysql
sur erreur et protections avec les futurs comptes à privilèges minimaux. Les règles
d’incompatibilité de rôles, d’approbation indépendante et d’interdiction d’octroi à
un compte désactivé ne sont pas implémentées ; aucun test ne prétend les garantir.
