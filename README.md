# SecurePayroll

Application académique de gestion des employés et de simulation de paie pour le module **Database Security** : PHP/PDO, MySQL 8.4, HTML/CSS/JavaScript, interface français/anglais, devise MAD. Aucun Docker, aucun paiement bancaire réel.

Chaque collaborateur utilise **ses données, son instance MySQL et ses mots de passe**. L’installation crée un MySQL privé dans `.local/`, uniquement par socket Unix. Elle ne se connecte jamais au MySQL système ou à une base existante et n’expose aucun port MySQL.

## Prérequis

- Linux, Python **3.10+**, PHP **8.1+** en 64 bits avec `pdo_mysql`, sessions et `PASSWORD_ARGON2ID`.
- **MySQL Community Server 8.4**, exécutables `mysql` et `mysqld` (`/usr/sbin/mysqld` est également détecté). MariaDB n’est pas compatible.
- Git et un compte Linux ordinaire. **Ne pas exécuter l’initialisation avec sudo.** L’installation des logiciels système relève de l’administrateur du poste.
- Aucun Composer, npm ou service cloud requis. Windows natif et macOS ne sont pas testés.

Sur un poste Ubuntu/Debian neuf, les dépendances PHP peuvent être installées par l’administrateur :

```bash
sudo apt update
sudo apt install git python3 php-cli php-mysql
```

Pour MySQL, sélectionner la série **8.4 LTS** dans le [guide officiel du dépôt APT MySQL](https://dev.mysql.com/doc/mysql-apt-repo-quick-guide/en/) avant d’installer `mysql-server`. Ne pas remplacer ou mettre à niveau une installation MySQL existante à l’aveugle. Si MySQL 8.4 est déjà disponible, aucune installation ni modification du service système n’est nécessaire pour ce projet. Les commandes d’installation de paquets ci-dessus concernent le poste du collaborateur et n’ont pas été exécutées sur la VM d’origine. Référence PHP : [installation des paquets PHP et MySQL sur Debian/Ubuntu](https://www.php.net/manual/en/install.unix.debian.php).

Vérifier les logiciels après leur installation :

```bash
php -v
php -m
php -r 'echo defined("PASSWORD_ARGON2ID") ? "Argon2id disponible\n" : "Argon2id absent\n";'
mysql --version
/usr/sbin/mysqld --no-defaults --version
python3 --version
```

Les versions effectivement testées figurent dans [le rapport d’installation](docs/COLLABORATION-VALIDATION.md).

## Installation locale

Le dépôt est public ; le cloner directement suffit. Aucune donnée MySQL ni aucun secret n'y figure : chaque personne génère sa propre instance locale et ses propres mots de passe.

```bash
git clone https://github.com/Renzo0023/secure_payroll_project.git
cd secure_payroll_project
python3 bin/init-local.py
```

Le dépôt de référence est **https://github.com/Renzo0023/secure_payroll_project** et le dossier du projet s'appelle **`secure_payroll_project`**. Toutes les commandes de ce guide se lancent depuis la racine de ce dossier ; les chemins relatifs (`.local/`, `bin/`, `tests/`…) y sont rattachés. Le chemin complet du clone ne doit contenir ni espace ni caractère spécial (voir « Dépannage »).

```text
secure_payroll_project/
├── app/            backend PHP (contrôleurs, dépôts, sécurité, vues)
├── public/         point d'entrée web (index.php) et assets CSS/JS
├── lang/           traductions fr / en
├── config/         configuration générique (lue depuis les variables DB_*)
├── database/       migrations, seeds, setup (rôles et GRANT), patches, audits
├── bin/            installateur init-local.py et scripts d'exploitation
├── tests/          recettes hors connexion et sur instance jetable
├── lab/            laboratoire (injection SQL, démonstrations isolées)
├── docs/           évaluation de sécurité, documentation technique, guides
├── storage/logs/   répertoire vide versionné (journaux hors Git)
└── .local/         instance MySQL privée et secrets, créés à l'installation, jamais versionnés
```

L’initialisation prend quelques minutes. Elle refuse un `.local/` déjà présent, initialise un datadir neuf, démarre MySQL **sans réseau**, confirme le datadir, la version et le port zéro, puis réutilise les migrations, seeds et GRANT existants. Elle installe **28 tables, 31 procédures, 53 triggers, 31 permissions et six rôles applicatifs**, remplace les privilèges directs du service PDO par **12 rôles MySQL** (`database/setup/app_roles.sql`, `operator_roles.sql`, `onboarding_grants.sql`), crée les comptes locaux, les trois comptes d’exploitation MySQL et le jeu fictif, puis arrête son propre serveur en conservant les données.

Par défaut, elle génère un mot de passe neuf et différent pour chacun des six comptes web et pour le service PDO. Aucun secret de la VM d’origine n’est utilisé. Pour choisir personnellement ces sept mots de passe, avec saisie masquée et confirmation, utiliser à la **première installation** :

```bash
python3 bin/init-local.py --interactive-passwords
```

Chaque mot de passe choisi doit comporter au moins 12 caractères et être distinct des autres. La configuration et les secrets sont stockés en fichiers 0600 dans `.local/`, répertoire 0700 exclu de Git. L’administration privée de cette nouvelle instance utilise également un secret aléatoire distinct.

## Identifiants et démarrage

```bash
python3 bin/init-local.py credentials
python3 bin/init-local.py serve
```

Ouvrir **http://127.0.0.1:8080/login**. `credentials` affiche les nouveaux secrets **dans un terminal seulement** ; ne pas rediriger sa sortie ni la publier.

| Identifiant fictif | Rôle | Usage |
|---|---|---|
| `hr.demo` | Responsable RH | Employés, contrats, affectations, rémunérations |
| `finance.demo` | Responsable Finance | Approbations, périodes/plafonds et paiements fictifs |
| `payroll.demo` | Gestionnaire de paie | Calcul, vérification, publication, corrections |
| `employee.demo` | Employé | Nadia TRAORE, ses bulletins publiés et leur règlement |
| `admin.demo` | Administrateur applicatif | Octroi et révocation des rôles d’autrui |
| `audit.demo` | Auditeur | Lecture de la paie et de l’historique IAM |

Ces noms sont des identifiants fictifs publics ; **aucun mot de passe par défaut n’est partagé**. `svc_php` est le service PDO, pas un login web : il détient un rôle MySQL par rôle applicatif et n’active, à chaque requête, que ceux de l’utilisateur connecté (`SET ROLE`).

`credentials` affiche aussi les comptes MySQL d’exploitation, utilisables avec `mysql --socket=.local/mysql.sock` : `dba_ops` (maintenance du schéma), `backup_ops` (sauvegarde, lecture seule) et `audit_ops` (traces, sans montant ni donnée personnelle). Voir la [matrice de contrôle d’accès](docs/security-assessment/06-MATRICE-DE-CONTROLE-D-ACCES.md).

Le lanceur lit `.local/application.json`, puis transmet la configuration privée via les variables `DB_*` déjà utilisées par le code. Settlement et IAM sont activés localement. `.env.example` reste un modèle sans secret ; les fichiers `.env` ne sont pas chargés automatiquement.

## Redémarrer et arrêter

```bash
python3 bin/init-local.py status
python3 bin/init-local.py start
python3 bin/init-local.py serve --port 8081
python3 bin/init-local.py stop
```

`start` ne rejoue aucune migration. `serve` démarre ce MySQL si nécessaire et lance PHP sur la boucle locale. **Ctrl+C arrête PHP uniquement** ; `stop` arrête proprement le MySQL privé. Les données restent conservées. Ne pas lancer deux serveurs HTTP sur le même port.

**Mise à niveau.** Une instance installée avant l'embauche se met à niveau sans perte avec `python3 bin/init-local.py upgrade` (une seule fois par évolution, comptes et données conservés). Les invitations envoyées aux nouveaux salariés se lisent, dans un terminal, avec `python3 bin/init-local.py outbox`.

Le lanceur ne charge ni configuration MySQL système, ni profil client habituel, ni secrets `DB_PASSWORD`/`MYSQL_PWD` hérités. Chaque collaborateur peut utiliser `secure_payroll` sans partager la moindre donnée avec les autres, grâce à son instance privée.

## Jeu fictif et première paie

Le seed [009_collaboration_demo.sql](database/seeds/009_collaboration_demo.sql), réservé à l’instance neuve, crée par les procédures existantes :

- Nadia TRAORE, matricule `EMP-2026-001` ; département IT et poste SOFTWARE_ENGINEER.
- Contrat permanent `CDI-EMP-2026-001-01`, début le **3 novembre 2026**.
- Salaire mensuel de **12 000,00 MAD**, proposé par RH et approuvé par Finance.
- Novembre 2026 avec plafonds de primes **3 300,00 MAD** et de retenues **560,00 MAD**.

Le seed [010_employee_personal_data_demo.sql](database/seeds/010_employee_personal_data_demo.sql) renseigne les données personnelles **entièrement fictives** des six salariés dans `employee_personal_data` ([migration 012](database/migrations/012_employee_personal_data.sql)) : pièce d’identité, CNSS, date de naissance, situation familiale, coordonnées et RIB. Ces données sont dans une table 1:1 séparée d’`employees`, car le compte `svc_php` lit toute la table `employees`. Les champs les plus sensibles (pièce d’identité, CNSS, RIB) sont **chiffrés au repos en AES‑256‑GCM** ([migration 015](database/migrations/015_personal_data_encryption.sql)), accompagnés d’un **index aveugle** HMAC‑SHA256 pour la recherche par égalité ; les deux clés sont conservées **hors de la base et hors du dépôt**, dans `.local/runtime/keys/` (fichiers 0600). L’accès passe uniquement par des procédures dédiées, selon le rôle, et reste sous contrôle de format (CHECK). Les valeurs sont construites pour ne correspondre à aucune personne réelle : préfixe `ZZ`, code banque `999`, domaine `example.com`. Le détail figure dans la fiche [protection des données sensibles](docs/security-assessment/11-PROTECTION-DONNEES-SENSIBLES.md).

**Aucun bulletin ni paiement n’est préfabriqué.** Paie calcule novembre depuis `/payroll` : **12 000 × 28 / 30 = 11 200,00 MAD**, sans prime ni retenue. Paie vérifie ; Finance approuve ; Paie publie ; Nadia consulte ; Finance peut enregistrer le paiement fictif. Déconnecter le rôle courant avant d’en changer.

Ces données ne proviennent pas d’un dump de la VM. Les six identités opérationnelles sont distinctes, les rôles sont séparés et les historiques restent immuables.

## Tests

Tests rapides hors connexion :

```bash
php tests/sql-static.php
php tests/compensation-unit.php
php tests/payroll-calculator.php
php tests/payroll-calendar.php
php tests/payroll-web-unit.php
php tests/database-roles-unit.php
php tests/login-limiter.php
php tests/access-history-unit.php
php tests/onboarding-unit.php
php tests/secure-coding-static.php
php tests/field-cipher-unit.php
python3 bin/generate-erd.py --check
```

Recette réelle du nouvel installateur :

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tests/local-install.py
```

Elle crée une **autre instance neuve dans `/tmp/securepayroll-install-*`**, applique le schéma et vérifie les données personnelles (six lignes fictives, service PHP sans accès, CHECK, modification tracée, suppression refusée), les rôles MySQL (aucun privilège direct du service, `SET ROLE`, `SHOW GRANTS`, `REVOKE`, comptes d’exploitation, sauvegarde avec le seul rôle `sp_backup`, matrice complète des rôles × 22 procédures × 16 tables), les six connexions HTTP, l'embauche par la RH (compte, invitation privée, rôle Employé tracé) et l'activation obligatoire par changement du mot de passe temporaire, le verrouillage d’un compte après cinq échecs sans blocage des autres et la journalisation des échecs, le refus d’une injection SQL sur « Mes accès » et du drapeau de laboratoire hors laboratoire, les pages, droits, prorata, publication et paiement fictif, le refus de réinitialisation, les secrets distincts, l’arrêt/redémarrage et la persistance. Elle conserve ses artefacts privés et arrête son serveur en fin de recette. **Ne jamais la modifier pour cibler une base existante.** Les autres tests de `tests/` et `lab/` gardent leurs propres préconditions et ne font pas partie du démarrage quotidien.

Les phases de durcissement et d'exploitation disposent de leurs propres recettes rejouables, chacune sur une instance jetable isolée :

```bash
python3 tests/privilege_matrix.py          # matrice de moindre privilège par rôle
python3 tests/backup-recovery.py           # sauvegarde chiffrée + restauration vérifiée (19 contrôles)
python3 tests/hardening-audit.py           # durcissement, onze zones (28 contrôles)
python3 tests/incident-investigation.py    # investigation d'un incident simulé (16 contrôles)
```

Avec `local-install.py` (151 contrôles), cela porte à **214 contrôles automatisés** (complétés par la matrice de privilèges) la preuve rejouable de l'authentification, de l'autorisation, du moindre privilège, du chiffrement, de l'audit, de la sauvegarde, du durcissement et de la capacité d'enquête.

## Laboratoire d'injection SQL (phases 4 et 5)

La page « Mes accès » de l'application (`.local/`) est **sécurisée** : requête préparée, validation serveur, erreurs neutres. La version **volontairement vulnérable** n'existe que dans un laboratoire jetable, isolé par quatre conditions (drapeau explicite, serveur `php -S`, répertoire `/tmp/securepayroll-lab-*`, fichier présent). Elle ne peut donc **jamais** se charger dans `.local/`.

### Campagne automatique (preuve « avant / après »)

```bash
python3 lab/sqli-campaign.py            # 7 scénarios, ~6 min, 23 contrôles PASS
python3 lab/sqli-campaign.py --sqlmap   # + sqlmap sur « avant » et « après », 26 contrôles
```

La campagne crée une instance **neuve** sous `/tmp/securepayroll-lab-*` (jamais `.local/`), se connecte avec le compte le moins privilégié (`employee.demo`) et rejoue une saisie légitime et huit charges d'injection en croisant le code (vulnérable ou corrigé) et les privilèges MySQL. Elle affiche un tableau comparatif, écrit son rapport dans `/tmp/securepayroll-lab-*/sqli-campaign.json` (mode 0600) et vérifie par `CHECKSUM TABLE` qu'aucune donnée n'a été modifiée. Chaque exécution laisse une instance d'environ 190 Mo : réutilisez-la avec `--instance` plutôt que d'en recréer une.

### Démonstration au navigateur

```bash
# Réutiliser l'instance créée ci-dessus (son chemin est affiché par la campagne) :
python3 lab/sqli-campaign.py --instance /tmp/securepayroll-lab-XXXX/mysql --serve A
```

La commande affiche l'URL (`http://127.0.0.1:8090/login`) et le mot de passe de `employee.demo` de cette instance. Se connecter, ouvrir **« Mes accès »**, puis déposer une charge dans l'URL : `/my-access?since=<charge>`. En mode vulnérable, un bandeau rouge **LABORATOIRE** rappelle la variante active.

Changer la lettre après `--serve` pour comparer les configurations : **A** (avant correction), **E** (requête préparée seule), **F** (validation seule), **G** (erreurs génériques seules), **B** (moindre privilège seul), **C** / **D** (corrigé). `Ctrl+C` arrête le serveur PHP ; MySQL reste actif pour le scénario suivant.

Le guide détaillé — charges exactes et effet observé de chaque contrôle — est dans [docs/security-assessment/10-REMEDIATION-INJECTION.md](docs/security-assessment/10-REMEDIATION-INJECTION.md).

### Nettoyage

```bash
python3 bin/init-local.py stop --directory /tmp/securepayroll-lab-XXXX/mysql
rm -rf /tmp/securepayroll-lab-XXXX     # après avoir vérifié le chemin
```

Les instances de laboratoire sont indépendantes de `.local/`. Elles s'accumulent sous `/tmp` si on ne les supprime pas ; pensez à vérifier l'espace disque (`df -h /`) avant une série de campagnes.

## Publication et fichiers privés

Sont partagés : frontend, backend, configuration générique, migrations, procédures, triggers, permissions, jeux fictifs, scripts, tests et documentation.

Sont exclus : **tout `.local/`**, `.env` sauf le modèle, clés et profils MySQL, tout le contenu privé de `storage/` sauf le répertoire vide des logs, sauvegardes/dumps, caches Python et sorties générées des anciens tests. Les scripts SQL de structure sous `database/` sont conservés. Le `.gitignore` ne retire pas un secret déjà commité : contrôler aussi l’historique.

Avant chaque publication :

```bash
python3 bin/audit-secrets.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/secret-audit.py
git status --short
git diff --cached --stat
```

L’audit contrôle les fichiers publiables, l’index et tous les objets Git sans afficher les valeurs suspectes ; il échoue lorsqu’un point reste à examiner. Ses huit tests de non-régression utilisent un dépôt Git temporaire et des secrets synthétiques, jamais des identifiants opérateur. Il ne remplace pas la revue humaine. **Ne pas pousser si l’audit échoue ; ne pas forcer de push.**

## Dépannage sans suppression

- `.local/` déjà présent : utiliser `start` ou `serve`. Une installation incomplète est conservée ; aucune suppression ni réapplication automatique.
- Erreur 503 sur toutes les pages après la mise à jour de la phase 2 : l’instance `.local/` date d’avant les rôles MySQL. La conserver sous un autre nom et en installer une neuve (nouveaux mots de passe, jeu fictif remis à zéro) : `python3 bin/init-local.py stop && mv .local .local.avant-phase2 && python3 bin/init-local.py init`.
- Lire en privé `.local/initialize.log`, `.local/mysql.log` et `.local/runtime/application.log`. Ne jamais partager `admin.json`, `application.json`, `credentials.json` ou `operators.json`.
- MySQL absent/autre version : installer MySQL 8.4, pas MariaDB.
- « mysqld ne peut pas écrire… (AppArmor probable) » : sur Ubuntu, le profil AppArmor `/usr/sbin/mysqld` limite le serveur à `/var/lib/mysql` et `/tmp`. Le refus est visible avec `journalctl -k | grep 'apparmor="DENIED".*mysqld'`. L’administrateur du poste autorise alors **uniquement** le répertoire privé du clone, dans le fichier local prévu par le profil, puis recharge celui-ci (commande à lancer depuis la racine `secure_payroll_project/`, car elle utilise `$PWD`) :

  ```bash
  printf '  %s/ rw,\n  %s/** rwk,\n' "$PWD/.local" "$PWD/.local" | sudo tee -a /etc/apparmor.d/local/usr.sbin.mysqld
  sudo apparmor_parser -r /etc/apparmor.d/usr.sbin.mysqld
  ```

  Ne pas désactiver AppArmor ni passer le profil en mode `complain`. Le `.local/` de l’essai refusé ne contient que des secrets jamais utilisés, sans datadir : après vérification (`ls -la .local`), le supprimer, puis relancer `python3 bin/init-local.py`.
- Chemin trop long ou avec espaces : choisir un clone à chemin court, ou un répertoire privé **neuf** via `--directory /CHEMIN/COURT`. Réutiliser cette option pour toutes les commandes ; ne jamais choisir un datadir existant.
- Ne pas importer un dump, lancer les anciennes commandes `activate-*` ou désactiver des triggers pour contourner un échec.

## Documentation et collaboration

- Évaluation de sécurité, phase 1 : [inventaire des actifs](docs/security-assessment/01-INVENTAIRE-DES-ACTIFS.md), [classification des données](docs/security-assessment/02-CLASSIFICATION-DES-DONNEES.md), [analyse CIA](docs/security-assessment/03-ANALYSE-CIA.md), [modèle de menace](docs/security-assessment/04-MODELE-DE-MENACE.md) et [ERD](docs/security-assessment/05-ERD.md) généré depuis les migrations par `bin/generate-erd.py`. Leur synthèse forme les [sections 5 à 7 du rapport d'évaluation](docs/security-assessment/RAPPORT-SECTIONS-05-07.md).
- Évaluation de sécurité, phase 2 : [utilisateurs, rôles MySQL et matrice de contrôle d’accès](docs/security-assessment/06-MATRICE-DE-CONTROLE-D-ACCES.md), synthétisés dans les [sections 9 et 10 du rapport](docs/security-assessment/RAPPORT-SECTIONS-09-10.md).
- Évaluation de sécurité, phase 3 : [authentification](docs/security-assessment/07-AUTHENTIFICATION.md) (limiteur par compte et par adresse, journalisation des échecs, [démonstration du stockage des mots de passe](lab/password-storage-demo.php)), synthétisée dans la [section 8 du rapport](docs/security-assessment/RAPPORT-SECTION-08.md).
- Évaluation de sécurité, phase 4 : [analyse de vulnérabilité contrôlée](docs/security-assessment/08-ANALYSE-DE-VULNERABILITE.md) (injection SQL sur « Mes accès », composant vulnérable confiné au laboratoire, campagne `python3 lab/sqli-campaign.py`), synthétisée dans la [section 11 du rapport](docs/security-assessment/RAPPORT-SECTION-11.md).
- Évaluation de sécurité, phase 5 : [remédiation de l'injection SQL et codage sécurisé](docs/security-assessment/10-REMEDIATION-INJECTION.md) (requêtes préparées, validation serveur, gestion d'erreur sûre, moindre privilège ; preuve « avant / après » avec `sqlmap`, variantes à contrôle unique, guide de démonstration au navigateur, garde-fou `tests/secure-coding-static.php`), synthétisée dans la [section 12 du rapport](docs/security-assessment/RAPPORT-SECTION-12.md).
- Évaluation de sécurité, phase 6 : [protection des données sensibles](docs/security-assessment/11-PROTECTION-DONNEES-SENSIBLES.md) (chiffrement AES‑256‑GCM au repos, index aveugle HMAC‑SHA256, clés hors base et hors dépôt).
- Évaluation de sécurité, phase 7 : [journalisation et audit](docs/security-assessment/12-JOURNALISATION-ET-AUDIT.md) (piste centrale en ajout seul, double source application/déclencheurs, détection de signaux suspects).
- Évaluation de sécurité, phase 8 : [sauvegarde et restauration](docs/security-assessment/13-SAUVEGARDE-ET-RESTAURATION.md) (sauvegarde chiffrée par compte dédié, exercice de reprise vérifié, `python3 tests/backup-recovery.py`).
- Évaluation de sécurité, phase 9 : [durcissement de la base](docs/security-assessment/14-DURCISSEMENT.md) (socket‑only, opérations fichiers désactivées, comptes et permissions durcis ; audit avant/après par `python3 tests/hardening-audit.py`).
- Évaluation de sécurité, phase 10 : [investigation d'incident](docs/security-assessment/15-INVESTIGATION-INCIDENT.md) (scénario rejoué avec les mécanismes réels, chronologie et sept questions ; `python3 tests/incident-investigation.py`) et [bilan final de sécurité](docs/security-assessment/16-BILAN-FINAL.md).
- Rapport d'évaluation complet (livrable 3) : généré en français et en anglais par `python3 docs/security-assessment/build-report-fr.py` et `build-report-en.py` (HTML → LibreOffice → `.docx`, captures et schémas embarqués ; nécessite `soffice` et `python3-pil`).
- Embauche et activation des comptes : [création par la RH, invitation, mot de passe temporaire et changement obligatoire](docs/security-assessment/09-EMBAUCHE-ET-ACTIVATION.md), avec la matrice du besoin d'en connaître (la RH n'accède pas au RIB).
- [Documentation technique complète](docs/technical-documentation/README.md) : analyse historique du 11 novembre ; le présent guide ajoute l’installation indépendante du 15 novembre.
- [Validation du nouvel installateur](docs/COLLABORATION-VALIDATION.md).
- [Audit et périmètre de publication](docs/PUBLICATION.md).
- [Ancien README conservé](docs/README-HISTORIQUE.md) : traçabilité, pas le parcours d’installation collaborative.

Le dépôt est **public** : il ne contient que du code, de la configuration générique, des scripts, des tests, des jeux fictifs et de la documentation. **Aucune donnée MySQL, aucun secret ni aucune donnée personnelle réelle n’y est partagé** — chaque personne génère sa propre instance locale. Chaque modification doit préserver les autorisations et l’intégrité, puis être testée isolément.
