# Laboratoire pédagogique hors connexion

Les extensions de finalisation ont une nouvelle campagne documentée dans
[le rapport](../docs/FINALIZATION-VALIDATION-2026-11-06.md) : paiements,
corrections, compléments, trop-perçus, IAM, tests HTTP FR/EN et concurrence réelle.
Pour une **nouvelle** instance complète Paie + Settlement :

```bash
python3 lab/mysql-validate.py --initialize-isolated --with-settlement
```

Après arrêt de cette instance, `lab/mysql-iam.py --source-private-dir CHEMIN_PRIVE`
installe les seuls nouveaux objets IAM, puis exécute les tests. Les migrations
ne sont pas rejouées en cas de collision. Les scénarios consomment leurs fixtures :
utiliser un nouveau datadir pour une nouvelle campagne complète.
`lab/mysql-final-recovery.py --source-private-dir CHEMIN_PRIVE` teste la sauvegarde
du lanceur administratif puis restaure tous les modules dans un nouveau datadir
privé sous `/var/tmp`, sur disque. Tous les artefacts précédents sont conservés.

```sh
python3 lab/demonstrate.py
```

Les données sont entièrement fictives. Le script ouvre uniquement SQLite `:memory:`.
Il n'écoute aucun port, ne lit aucun identifiant et ne se connecte jamais à MySQL.
L'état disparaît à la fermeture du processus. Aucun journal existant n'est touché.
Les requêtes volontairement vulnérables sont confinées à ce script CLI hors de
`public/`, sans import dans l'application.

Six scénarios exécutent des assertions avant/après : injection SQL face aux paramètres
liés, IDOR face au filtre propriétaire, action Finance face au rôle serveur, rôle
falsifié face au rôle enregistré, altération de montant face à un trigger immuable,
et droits excessifs face à un ensemble de privilèges minimaux.

Les deux derniers contrôles d'autorisation simples et le scénario de privilèges
sont des modèles pédagogiques. Ils ne prouvent pas la résistance de l'application
PHP ni le comportement de MySQL. Le laboratoire ne remplace pas des tests intégrés
avec les six comptes, les procédures et les accès concurrents.

Le laboratoire MySQL réel ci-dessous utilise une instance et un datadir distincts,
un socket privé et des comptes propres, sans aucun port MySQL ouvert. Les créations
de comptes et GRANT ont été explicitement autorisées pour ce seul laboratoire.

## Validation MySQL isolée préparée

Nouvelle campagne du 6 novembre : voir
[le rapport](../docs/LAB-VALIDATION-2026-11-06.md). Pour le socle identité/RBAC seul :

```bash
python3 lab/mysql-integrity.py --initialize-isolated
```

Ce lanceur crée sa propre instance et le schéma `secure_payroll_test_integrity`,
exécute les assertions avec un compte non-root, vérifie les tables vides après
rollback et conserve `integrity-result.json`. Il ne demande aucune identité
principale. Exécuter ces lanceurs dans un environnement qui permet le cycle de
vie des processus MySQL ; le confinement de l’agent a bloqué deux initialiseurs
le 6 novembre, tandis que la même campagne hors confinement a réussi.

Après autorisation explicite de créer les comptes et privilèges de l'instance de
test, comme utilisateur Ubuntu habituel, sans sudo :

```bash
python3 lab/mysql-validate.py --initialize-isolated
```

Le lanceur demande `ISOLATED`, crée un répertoire privé 0700 dans `/tmp`, initialise
un nouveau datadir, démarre son propre mysqld avec `--skip-networking --mysqlx=OFF`
et utilise exclusivement son socket privé. Il vérifie le datadir et l'absence de
réseau avant de charger la moindre table. Il ne lit aucune donnée, configuration
client ou identité de l'instance principale. Les migrations historiques sont
exécutées uniquement dans ce nouveau datadir vide, jamais sur la base installée.

Les comptes de service et propriétaires ne sont créés que dans cette instance.
Les secrets de test sont aléatoires en mémoire ; aucune connexion applicative root
n'est utilisée. Le client d'administration root est limité au socket privé pour
le bootstrap. Les scénarios PHP utilisent uniquement svc_php.

`tests/payroll-mysql.php` vérifie le parcours RH → Finance avec MAD, les calculs,
primes/retenues/suspensions, plafonds, versions obsolètes, vérification, rejet,
approbation et publication distincte, IDOR, lecture auditeur et refus des écritures
directes/helpers par le service. Il compare les résultats financiers SQL au
calculateur PHP indépendant. Ces tests ont été exécutés après autorisation : 35 contrôles SQL, 58 HTTP
authentifiés et 18 de concurrence/privilèges/intégrité ont réussi. Voir
[le rapport](../docs/LAB-VALIDATION-2026-11-04.md).

Le lanceur arrête uniquement le processus qu'il a créé. Il conserve le datadir et
les journaux pour examen, sans nettoyage ni effacement. Une nouvelle exécution
crée un autre répertoire ; elle ne reprend pas une installation partielle.


## Exercices complémentaires réellement exécutés

Les commandes suivantes redémarrent seulement un datadir de laboratoire arrêté,
créé par le lanceur précédent. Elles refusent les chemins extérieurs au préfixe
privé et n’utilisent aucun socket ou port principal :

```bash
python3 lab/mysql-recovery.py --source-private-dir /tmp/securepayroll-mysql-5g9p67gy
python3 lab/mysql-attacks.py --source-private-dir /tmp/securepayroll-mysql-5g9p67gy
python3 lab/mysql-security.py --source-private-dir /tmp/securepayroll-mysql-ymqcl2b_
```

Résultats obtenus : 32 contrôles de sauvegarde/restauration dans deux instances,
22 contrôles MySQL avant/après pour six scénarios et 18 refus métier/sécurité.
Les chemins ci-dessus désignent les artefacts conservés de la session ; pour une
nouvelle campagne, utiliser un nouveau datadir et ses fixtures, sans réinitialiser
ou supprimer l’ancien. Certains scénarios consomment leurs fixtures en approuvant
des demandes ; ne pas les rejouer aveuglément sur le même jeu déjà traité.

Les vulnérabilités pédagogiques sont limitées à un schéma `attack_training_*` du
serveur privé. Les changements de rôle et de montant de la démonstration sont
annulés par transaction, puis les droits excessifs du compte pédagogique sont
révoqués. La correction utilise des paramètres liés, un filtre propriétaire et
un accès EXECUTE dédié. La procédure pédagogique représente un unique employé
fictif fixé côté serveur ; elle n'est pas un mécanisme d'identité de production.
Aucune route web vulnérable n'est créée.

`DB_SOCKET` dirige le serveur PHP de test vers le socket MySQL privé ;
`APP_RUNTIME_DIR` conserve ses sessions, logs et compteurs séparément. Les sept
connexions couvrent les six rôles et les deux employés. Le coût Argon2id et les
protections CSRF restent actifs. Après cinq échecs, la sixième tentative est
limitée, tandis que les connexions réussies n'épuisent plus le quota d'échecs.
