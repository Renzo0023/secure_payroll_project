# Notice historique — état antérieur au guide de collaboration

Ce texte est conservé pour traçabilité. Pour une installation neuve, suivre le README de la racine et bin/init-local.py. Ne pas utiliser les anciennes commandes install/activate sur une base existante.

# Secure Employee & Payroll Management System

**Démonstration opérationnelle sur la principale, 6 novembre 2026 :**
SecurePayroll répond sur **http://127.0.0.1:8080**. Les six comptes sont fonctionnels,
`employee.demo` est lié à Nadia et le bulletin n°1 est publié à **11 200,00 MAD**,
avec paiement fictif enregistré et solde **0,00 MAD**. Les pages autorisées ont été
vérifiées en FR/EN : **64 contrôles HTTP/base sur la principale**, puis **24 contrôles
isolés** de restauration et de formulaires paiement/correction. Les propriétaires
et privilèges MySQL dédiés ont été vérifiés ; aucune migration n’a été rejouée.

Pour présenter et récupérer une seule fois les nouveaux mots de passe dans votre
terminal : [DEMO-PRESENTATION.md](DEMO-PRESENTATION.md). Aucun mot de passe
n’est conservé dans le code ou les rapports. Le serveur existant reste en service.
Ne relancer aucun installateur ou script d’activation sur cette base déjà installée.

Les rapports antérieurs sont conservés : [finalisation en laboratoire](FINALIZATION-VALIDATION-2026-11-06.md),
[laboratoire Paie](LAB-VALIDATION-2026-11-04.md),
[référence administrative](FINALIZATION.md), [règles de paie](PAYROLL.md).

Les sections de missions antérieures ci-dessous conservent leur contexte historique.

## Application web — mission 04

**RH avancé (mission 05A)** : départements, postes, affectations, contrats et
historique sont implémentés en FR/EN. Voir [docs/ADVANCED-HR.md](ADVANCED-HR.md)
pour l’activation des nouvelles migrations, permissions et droits, sans rejouer
les tables/comptes déjà opérationnels. Aucun salaire n’est modifiable dans ce module.
La revue 05B prépare un propriétaire MySQL verrouillé pour les neuf nouveaux objets :
[procédure d’activation locale](ADVANCED-HR-ACTIVATION.md). Les objets s’exécutent
sous ses droits dédiés et svc_php n’écrit pas directement dans les historiques.

**Premier accès RH (mission 04B)** : suivre [docs/LOCAL-DEMO.md](LOCAL-DEMO.md).
L’installateur prépare svc_php et rh.demo avec saisie confidentielle, après
validation explicite dans votre terminal. Aucun secret prédéfini n’est fourni.

L’interface est bilingue FR/EN : français par défaut, sélecteur sur la connexion
et dans l’en-tête, préférence conservée en session sans déconnexion. Les textes
sont centralisés dans `lang/fr.php` et `lang/en.php`. Voir
[docs/I18N.md](I18N.md) pour la convention obligatoire des futures interfaces.

La première version web inclut la connexion réelle par PDO/Argon2id, les sessions
et CSRF, les tableaux de bord selon les rôles actifs et les fiches employés.
Les responsables RH habilités disposent d’un annuaire, d’une recherche paginée,
de l’ajout et de la modification du prénom/nom. Les autres utilisateurs consultent
leur propre fiche. Aucun compte de démonstration ni connexion fictive n’est fourni.

Voir [docs/WEB-SETUP.md](WEB-SETUP.md) pour les opérations MySQL à faire
valider et l’environnement privé nécessaire. Le nouveau seed
`database/seeds/002_hr_permissions.sql` est préparé **mais non exécuté**.

```sh
php -S 127.0.0.1:8080 -t public public/index.php
```

Interface locale : **http://127.0.0.1:8080/login**. Le formulaire est consultable
sans MySQL ; l’authentification et les pages privées nécessitent un vrai compte,
les tables installées et les variables DB_* configurées. Le fichier .env n’est
pas chargé automatiquement. Le port 8000 peut également être choisi s’il est libre.

Le point d’entrée public/index.php route vers app/Web/Controller.php. Les services
sont répartis dans app/Auth/, app/Security/ et app/HR/, les vues dans app/Views/,
les styles et interactions dans public/assets/. L’autoload PHP est fourni par le
bootstrap existant, sans framework ou dépendance supplémentaire.

Les sections suivantes conservent l’historique et les instructions des premières
missions ; leur ancienne page d’accueil minimale a été remplacée par l’application.

Projet académique ciblant Ubuntu, PHP 8.5, Apache et MySQL 8.4.
Le projet fournit un socle PHP sans framework et un module de connexion PDO
MySQL utilisable explicitement. Aucune base, table ou identité SQL n’est créée.

## Structure

```text
app/                  Initialisation et futurs modules applicatifs
  bootstrap.php       Fuseau UTC, erreurs et journalisation
config/               Future configuration (sans secrets versionnés)
database/
  migrations/         Futures migrations versionnées
  seeds/              Futures données de référence non sensibles
public/
  index.php           Point d’entrée HTTP unique
storage/
  logs/               Journaux locaux, ignorés par Git
tests/                Futurs tests automatisés
```

Seul `public/` doit être exposé au serveur HTTP. Les domaines prévus sont RH,
Paie, Finance, IAM et Audit. Les six rôles prévus sont Employee, HR Manager,
Payroll Manager, Finance Manager, Application Administrator et Security Auditor.
Les modules métier, le RBAC, le moindre privilège et l’audit métier seront développés
dans les missions suivantes ; aucun contrôle d’accès métier n’est encore implémenté.

## Développement local

Depuis la racine, avec PHP 8.5 disponible :

```sh
php -v
php -S 127.0.0.1:8000 -t public public/index.php
```

Ouvrir <http://127.0.0.1:8000/>. Le routeur explicite permet de renvoyer une
réponse 404 pour tout chemin autre que `/`. Arrêter le serveur avec `Ctrl+C`.
Le serveur intégré est réservé au développement local. Aucune installation de
paquet ni modification d’Apache ou du système n’est nécessaire pour cette étape.
Le routage Apache sera traité dans une mission de déploiement distincte.

Le processus PHP doit pouvoir écrire dans `storage/logs/`. Les erreurs PHP sont
masquées au navigateur et la journalisation cible `storage/logs/application.log`.
Les exceptions non interceptées produisent une réponse 500 générique ; seuls leur
type et leur emplacement sont journalisés, sans message ni arguments. Les erreurs
fatales relèvent du journal natif PHP et peuvent contenir des détails techniques.
Ne pas placer de secrets dans le code, les URL ou les messages d’erreur. Ce journal
technique ne constitue pas encore un journal d’audit métier. Les erreurs survenant
avant l’exécution du bootstrap dépendent de la configuration PHP du serveur.

## Vérifications manuelles

```sh
php -l app/bootstrap.php
php -l public/index.php
curl -i http://127.0.0.1:8000/
curl -i http://127.0.0.1:8000/inconnu
```

Résultats attendus : aucune erreur de syntaxe, statut HTTP 200 pour `/` et 404
pour `/inconnu`. Aucun accès MySQL n’est requis.

## Prochaines étapes

Définir la matrice des permissions et les frontières des modules, puis préparer
les migrations et les identités SQL à privilèges minimaux
dans une mission dédiée. Ajouter ensuite l’authentification, le RBAC et l’audit
avec leurs tests, avant les fonctionnalités RH et Paie.

## Module PDO MySQL (mission 02)

`app/Database/Connection.php` expose `App\Database\Connection::connect()` et
`validateConfiguration()`. Charger explicitement ce fichier après le bootstrap
pour l’utiliser ; la page d’accueil ne charge pas ce module et n’ouvre aucune
connexion. Chaque appel à `connect()` crée une connexion PDO non persistante.
Le module utilise `utf8mb4`, les exceptions PDO, le retour associatif par défaut
et les requêtes préparées natives.

`config/database.php`, situé hors de `public/`, lit exclusivement `DB_HOST`,
`DB_PORT`, `DB_NAME`, `DB_USER` et `DB_PASSWORD` dans l’environnement du processus
PHP. Les cinq valeurs sont obligatoires et non vides. Le port doit être compris
entre 1 et 65535. Le nom de base accepte lettres ASCII, chiffres, `_` et `-` ;
les champs intégrés au DSN sont restreints pour empêcher l’ajout de paramètres.
La validation ne prouve ni la disponibilité du serveur ni la validité du compte.

`.env.example` contient uniquement des valeurs illustratives et un mot de passe
vide. Aucun fichier `.env` n’est chargé automatiquement : fournir les variables
par un mécanisme privé d’environnement. Pour un usage local, on peut copier
l’exemple vers `.env`, le compléter en privé et l’exporter dans un shell de
confiance avant de lancer PHP. Un fichier ainsi sourcé doit avoir une syntaxe
shell valide (valeurs correctement citées) ; il exécute du code shell.
Ne jamais saisir de véritables secrets dans une commande conservée dans
l’historique. `.env` et ses variantes sont déjà ignorés, sauf `.env.example`.
Ne jamais ajouter de secret à `config/database.php` ou à un autre fichier suivi.

Vérifier la configuration sans aucun accès réseau :

```sh
php tests/database-config.php
```

Code de sortie : 0 si valide, 1 sinon. Aucune valeur n’est affichée.
Le futur test de connexion est réservé au CLI et exige une option explicite.
À exécuter uniquement après configuration réelle des identifiants et préparation
du serveur dans une autre mission :

```sh
php tests/database-connect.php --connect
```

Il ouvre une connexion et exécute uniquement `SELECT 1`, sans modification de
données. Sans l’option, il sort avec le code 2 sans connexion. En cas d’échec,
il sort avec le code 1 et un message générique. Les scripts refusent l’exécution
HTTP. Les exceptions du pilote ne sont ni affichées ni chaînées ; conserver la
gestion d’erreurs du bootstrap pour toute future utilisation HTTP et ne jamais
afficher ou journaliser un dump de configuration ou une trace d’exception.

## Première migration — mission 03B (préparée, non exécutée)

La base existante cible est `secure_payroll`, sous MySQL 8.4.11. Les exemples de
noms de base de la mission 02 sont illustratifs : utiliser `DB_NAME=secure_payroll`
dans l’environnement privé. Ne pas utiliser `root` comme `DB_USER`. La configuration
PHP et la page d’accueil restent inchangées. Aucun compte SQL ni privilège n’est
créé par les fichiers de cette mission.

### Scripts et conception

- `database/migrations/001_create_identity_and_rbac.sql` : six tables InnoDB,
  `utf8mb4_0900_as_cs` (comparaisons sensibles à la casse et aux accents), clés
  primaires et étrangères, unicité et contraintes CHECK nommées.
- `database/seeds/001_application_roles.sql` : les six rôles applicatifs, sans
  utilisateur, mot de passe, permission ou attribution. Il insère les codes absents
  et conserve les identifiants et libellés existants. Une anti-jointure directe
  compare les couples code/libellé octet par octet ; une collision incohérente
  fait échouer l’insertion sur UNIQUE/CHECK, sans être ignorée. La contrainte
  `ck_roles_canonical` ferme le catalogue aux six couples prévus : le seed réussi
  donne exactement six rôles. Ajouter un rôle nécessitera une nouvelle migration.
  Il est idempotent en exécution séquentielle, sans `INSERT IGNORE` ni `REPLACE`.
- `tests/database-structure.php` : vérification CLI en lecture seule de la
  structure et des six rôles ; aucune migration n’y est exécutée.

`employees.employee_number` est unique et immuable, comme l’identifiant technique.
Les employés ne peuvent pas être supprimés par DELETE : utiliser `archived_at`.
Cela réserve définitivement les matricules, y compris après départ. Les matricules
sont sensibles à la casse : l’application devra imposer une convention de saisie.
Les noms ne sont pas uniques. Les données RH et Paie restent hors périmètre.

Un employé peut avoir zéro ou un compte ; chaque compte appartient à exactement
un employé. Le compte ne peut être réaffecté ni supprimé : utiliser `disabled_at`.
Le login est unique et sensible à la casse. `password_hash` stocke uniquement un
format PHC Argon2id version 19. Le CHECK rejette le texte ordinaire et les autres
formats ; il ne prouve pas la validité cryptographique d’une empreinte. Le futur
code PHP devra utiliser `password_hash($password, PASSWORD_ARGON2ID)` et
`password_verify()`, ainsi qu’une politique de coût et de renouvellement adaptée.
Aucune empreinte ni aucun compte applicatif n’est fourni ici.

`role_permissions` utilise une clé primaire composée, sans doublon de couple.
La matrice de permissions n’est pas encore définie : le seed n’accorde aucun accès.
Les rôles applicatifs sont des données, distinctes des comptes et rôles MySQL.

`role_assignments` conserve une ligne par attribution, avec bénéficiaire, rôle,
date d’octroi, début de validité, expiration facultative, motif obligatoire et
auteur facultatif. Un auteur NULL est réservé à une future procédure contrôlée
d’initialisation, justifiée dans le motif ; aucune telle attribution n’est créée.
Le début doit être postérieur ou égal à l’octroi et l’expiration strictement
postérieure au début. Toutes les dates sont des DATETIME(6). Les triggers d’octroi
et de révocation exigent une session MySQL explicitement `+00:00`. `granted_at`
doit correspondre à `CURRENT_TIMESTAMP(6)` de l’instruction courante : fournir
une ancienne date d’octroi pour contourner le CHECK n’est plus accepté.
Pour un octroi immédiat, omettre `granted_at` et `valid_from` : leurs deux défauts
`CURRENT_TIMESTAMP(6)` utilisent le même instant SQL, sans décalage réseau/PHP.
Pour un octroi planifié, omettre `granted_at` et fournir un `valid_from` futur.
Ne pas calculer l’instant immédiat dans PHP ou dans une instruction SQL antérieure.
Ne pas tronquer les microsecondes avec `CURRENT_TIMESTAMP` sans `(6)`.

Une attribution peut seulement être mise à jour pour sa première révocation :
date, compte auteur et motif obligatoires, date postérieure ou égale à l’octroi.
Utiliser `revoked_at = CURRENT_TIMESTAMP(6)` dans l’UPDATE de révocation ; les
révocations rétroactives ou planifiées sont refusées. Une nouvelle attribution
ne peut pas être insérée déjà révoquée. La révocation peut annuler un octroi avant
son début de validité. Ensuite, toute modification effective est refusée ; les
UPDATE strictement identiques sont autorisés et ne constituent pas une deuxième
révocation. Pour prolonger ou corriger un octroi, le révoquer et
créer une nouvelle ligne. Les DELETE sont bloqués. L’unicité
`(account_id, role_id, valid_from)` empêche les octrois au même instant, mais
n’interdit pas les périodes qui se chevauchent : cette politique nécessitera
une vérification transactionnelle et des verrous dans le futur service IAM.

Un futur contrôle d’accès devra exiger un employé non archivé, un compte non
désactivé et au moins une attribution telle que `valid_from <= instant_utc`,
`expires_at IS NULL OR instant_utc < expires_at`, et
`revoked_at IS NULL OR instant_utc < revoked_at`. Les dates de fin sont exclusives.
Il ne suffit pas qu’une ligne d’attribution existe pour autoriser un accès.

Toutes les FK utilisent `ON DELETE RESTRICT ON UPDATE RESTRICT`, sans cascade.
Sept triggers protègent les identités et l’historique. La cohérence de l’auteur de
révocation passe par les triggers car MySQL restreint les CHECK sur les colonnes
participant aux actions référentielles. Ces protections couvrent les opérations
DML ordinaires ; elles ne constituent pas un audit inviolable face à un compte
capable de supprimer les triggers, de faire TRUNCATE ou de modifier le schéma.
La séparation des comptes de migration et d’exécution reste nécessaire.

### Ordre d’exécution futur — aucune commande ci-dessous n’a été exécutée

1. Relire la migration et contrôler que les six tables et les sept triggers ne
   sont pas déjà présents. Confirmer la cible et prévoir une sauvegarde privée
   si la base contient déjà des données. Utiliser un compte de migration existant
   habilité, distinct du compte applicatif, avec une configuration client privée.
2. Appliquer la migration 001 une seule fois avec le client `mysql` :

   ```sh
   mysql --database=secure_payroll --show-warnings < database/migrations/001_create_identity_and_rbac.sql
   ```

   Le compte et la connexion doivent être sélectionnés par une configuration
   client privée préexistante ; cette commande ne lit pas les variables DB_* de
   PHP. Ne pas utiliser `--force`. Le fichier contient `USE secure_payroll` et des
   commandes `DELIMITER` pour le client mysql ; ne pas l’envoyer en bloc à PDO.
   L’exécutant doit déjà être habilité à créer les tables et triggers. Aucun
   `DEFINER` explicite n’est inscrit dans le fichier.
3. Après succès complet, appliquer le seed :

   ```sh
   mysql --database=secure_payroll --show-warnings < database/seeds/001_application_roles.sql
   ```

4. Avec les cinq variables DB_* définies en privé et un compte non-root ayant
   la visibilité nécessaire sur les métadonnées et les rôles, lancer :

   ```sh
   php tests/database-config.php
   php tests/database-structure.php --verify
   ```

Le vérificateur contrôle moteurs/collations, liste des colonnes, nullabilité,
types des identifiants et de l’empreinte, clés primaires/uniques, sept FK avec
RESTRICT, douze CHECK actifs, sept triggers BEFORE et les six rôles exacts. Il
vérifie aussi les DATETIME(6) et les deux défauts d’attribution immédiate. Il
contrôle la présence des CHECK et des triggers, pas l’équivalence complète de
leurs expressions : compléter la revue avec SHOW CREATE TABLE et SHOW CREATE
TRIGGER dans un contexte privé, puis des tests comportementaux sur une base de
test distincte autorisée. Il ne lit aucune donnée d’employé ou de compte.
Codes de sortie : 0 succès, 1 échec/écart, 2 option absente (aucune connexion).

Le DDL MySQL entraîne des commits implicites : une erreur en milieu de fichier
peut laisser une migration partiellement appliquée. Il n’y a ni rollback
automatique, ni script destructif de retour arrière, ni moteur de suivi des
migrations pour cette étape. Consigner manuellement la version appliquée ; en cas
d’échec, examiner l’état avant une reprise ciblée, sans relancer aveuglément le
fichier et sans supprimer les objets existants. Le SQL est préparé pour MySQL
8.4.11 mais n’a pas été validé par exécution sur le serveur.

Références : [CHECK MySQL 8.4](https://dev.mysql.com/doc/refman/8.4/en/create-table-check-constraints.html)
et [clés étrangères MySQL 8.4](https://dev.mysql.com/doc/refman/8.4/en/create-table-foreign-keys.html).

## Revue avant première exécution : tests et limites

Les fichiers SQL 001 ont été corrigés sur place parce qu’ils n’ont encore jamais
été appliqués. Aucun changement n’a été exécuté dans MySQL. Si une version 001
était déjà appliquée ailleurs, ces corrections exigeraient une nouvelle migration.

Contrôles hors connexion, sans lecture de configuration privée :

```sh
php tests/sql-static.php
find app config public tests -name '*.php' -exec php -l {} \;
```

Le test statique contrôle les six relations, les douze CHECK, les clés, les sept
triggers, les comparaisons exactes du seed, les règles temporelles et la présence
des scénarios d’intégrité. Il ne remplace pas le parseur ou le moteur MySQL.
Les tests d’intégrité sont préparés dans `tests/database-integrity.php` et décrits
dans [tests/INTEGRITY.md](../tests/INTEGRITY.md). Ils ne sont pas exécutés pour cette
mission. Ils ciblent exclusivement une base de test distincte, vide et préexistante,
jamais `secure_payroll`, et annulent leur transaction après les essais.

Les règles suivantes **ne sont pas encore garanties** par le schéma : incompatibilités
entre rôles, interdiction de l’auto-attribution, approbations indépendantes,
habilitation de l’auteur, refus d’attribution à un compte désactivé ou à un employé
archivé, et absence de chevauchements de périodes. Les FK prouvent seulement
l’existence des comptes. `granted_by_account_id` reste nullable pour une future
initialisation contrôlée ; aucun mécanisme d’approbation n’est implémenté ici.
Un futur service IAM devra appliquer ces politiques dans des transactions adaptées
à la concurrence. Le contrôle d’accès devra refuser les comptes désactivés même si
leurs attributions restent conservées. Les changements de permissions d’un rôle
ne sont pas historisés par `role_permissions` à ce stade.

Revue des sept triggers :

| Trigger | Interdictions | Opérations légitimes conservées / limites |
| --- | --- | --- |
| `employees_preserve_identity` | Changer id, matricule ou date de création | Modifier les noms, archiver ; une désarchivation reste possible |
| `employees_prevent_delete` | Tout DELETE d’employé | Archivage conservant le matricule ; nettoyage physique volontairement bloqué |
| `accounts_preserve_identity` | Changer id, employé lié ou date de création | Modifier login/empreinte, désactiver ou réactiver ; pas d’historique de ces changements |
| `accounts_prevent_delete` | Tout DELETE de compte | Désactivation ; aucun effacement physique ordinaire |
| `assignments_validate_insert` | Octroi horodaté hors instant SQL UTC, insertion déjà révoquée | Octroi immédiat ou futur ; pas de vérification métier de l’auteur/bénéficiaire |
| `assignments_preserve_history` | Modifier les données d’octroi, antidater/planifier une révocation, révoquer à nouveau ou annuler une révocation | Première révocation et UPDATE sans changement, y compris après révocation ; prolongation via nouvelle attribution |
| `assignments_prevent_delete` | Tout DELETE d’attribution | Conserver les octrois expirés/révoqués ; pas de purge ordinaire |

Les corrections de matricule, réaffectations de compte, modifications d’un octroi
ou imports historiques ne sont pas des mises à jour ordinaires autorisées. Une
éventuelle procédure exceptionnelle devra être conçue et auditée séparément.
`REPLACE` et les upserts modifiant les identités/l’historique peuvent déclencher
ces interdictions ; ne pas les employer comme raccourcis de maintenance.

Ces triggers ne protègent pas contre DROP/ALTER/TRUNCATE, la suppression de triggers,
la désactivation administrative de contrôles, une restauration ou un accès direct
aux fichiers. L’horodatage repose sur l’horloge SQL : une session autorisée à
surcharger son `timestamp`, ou un administrateur modifiant l’horloge serveur, peut
en altérer la signification. Le futur service ne devra exposer ni SQL arbitraire
ni surcharge d’horloge. Les defaults ne sont pas un mécanisme d’authentification.
Les rôles peuvent encore être supprimés s’ils ne sont pas référencés ; le seed
les réinsère. Le compte d’exécution devra donc être privé des écritures directes
sur le catalogue des rôles. Aucun privilège n’est modifié par cette mission.

Référence temporelle : [fonctions date/heure MySQL 8.4](https://dev.mysql.com/doc/refman/8.4/en/date-and-time-functions.html)
(instant courant stable pendant une instruction et ses triggers).

### Mission 06A — rémunérations RH / Finance

Le module bilingue propose les demandes salariales RH, les décisions Finance indépendantes et l'historique des conditions approuvées. Les tables et `finance.demo` sont déjà présents sur l’installation actuelle ; ne pas relancer leur création. La documentation d’installation neuve reste disponible, après revue : consulter [docs/COMPENSATION.md](COMPENSATION.md). Ne rejouer aucune migration RH précédente.

La devise de référence financière est le dirham marocain **MAD**, avec deux décimales et stockage `DECIMAL(12,2)`. La mise à jour indépendante et la préservation des historiques sont décrites dans [docs/CURRENCY-MAD.md](CURRENCY-MAD.md).

## État de la finalisation autonome

Le suivi courant et les limites de validation sont consignés dans
[docs/PROGRESS.md](PROGRESS.md). La Mission 06A nécessite toujours une
vérification réelle de l'installation avec accès autorisé. Les travaux indépendants
ajoutent un [calculateur de paie testé](PAYROLL.md), un
[laboratoire pédagogique hors connexion](../lab/README.md) et une
[procédure de récupération](RECOVERY.md). Ces éléments ne constituent pas
encore un module de paie et de bulletins opérationnel.
