# Phase 1 — Inventaire des actifs critiques

> Livrable de la phase 1 (« Critical database assets », « Data owners », « Authorized users »).
> État de référence : migrations `001` à `012`, installation par `bin/init-local.py`, soit **26 tables, 24 procédures, 44 triggers**.
> Chaque affirmation renvoie à un fichier du dépôt. Les niveaux de classification sont définis dans [02-CLASSIFICATION-DES-DONNEES.md](02-CLASSIFICATION-DES-DONNEES.md).

## 1. Méthode

Un **actif** est tout élément dont la compromission de la confidentialité (C), de l'intégrité (I) ou de la disponibilité (A) nuit à l'organisation ou aux salariés. L'inventaire ne se limite pas aux tables : il couvre aussi les objets de sécurité de la base, les comptes, les secrets, les journaux, les sauvegardes et l'infrastructure qui les porte. Les actifs hors tables sont les plus souvent oubliés et sont pourtant des copies complètes des données.

La **criticité** retient l'impact le plus grave parmi C, I et A :

| Criticité | Signification |
|---|---|
| **Critique** | Compromission entraînant une fraude financière, une usurpation d'identité, une prise de contrôle du système ou une atteinte grave aux salariés |
| **Élevée** | Atteinte importante à la vie privée, à la traçabilité ou au fonctionnement de la paie |
| **Modérée** | Gêne opérationnelle ou fuite d'information interne exploitable par un attaquant |
| **Faible** | Impact négligeable |

La colonne « Dimension dominante » indique la propriété dont la perte est la plus grave. L'analyse CIA détaillée fait l'objet d'un livrable distinct.

## 2. Rôles de responsabilité

Trois notions distinctes sont utilisées. Elles ne doivent pas être confondues.

| Notion | Définition | Dans SecurePayroll |
|---|---|---|
| **Propriétaire des données** (*data owner*) | Fonction métier responsable de la donnée : elle décide de sa finalité, de qui y accède et de sa durée de conservation | Direction RH, Direction financière, Responsable paie, RSSI (voir § 3) |
| **Dépositaire** (*custodian*) | Fonction technique qui stocke, sauvegarde et protège la donnée sans décider de son usage | DBA / exploitant de l'instance MySQL |
| **Personne concernée** (*data subject*) | Salarié auquel la donnée se rapporte ; il dispose d'un droit d'accès et de rectification (loi marocaine n° 09-08) | Chaque salarié de `employees` |
| Compte MySQL `*_owner` | Compte **technique** verrouillé, qui fournit le contexte de droits (`DEFINER`) des procédures stockées | `hr_module_owner`, `compensation_owner`, `payroll_owner`, `settlement_owner`, `iam_owner` (`database/setup/*_owner.sql`). **Ce ne sont pas des propriétaires de données.** |

## 3. Propriétaires des données

| Propriétaire métier | Rôle applicatif qui agit pour lui | Domaine de données |
|---|---|---|
| **Direction des ressources humaines** | `hr_manager` | Identité des salariés, données personnelles, contrats, affectations, référentiels départements/postes, propositions salariales |
| **Direction financière** | `finance_manager` | Décisions salariales, conditions salariales approuvées, périodes et plafonds de paie, décisions sur les éléments variables, registre des paiements |
| **Responsable de la paie** | `payroll_manager` | Calculs de paie, bulletins et leur cycle de vie, corrections, demandes de restitution |
| **RSSI** (fonction organisationnelle, sans rôle applicatif dédié) | `application_administrator` (attributions), `security_auditor` (contrôle) | Comptes, rôles, permissions, attributions, journaux de sécurité |
| **DBA / exploitant** (dépositaire de tous les actifs) | Aucun : accès hors application | Instance MySQL, sauvegardes, secrets, configuration |

## 4. Utilisateurs autorisés

| Utilisateur | Type | Accès légitime | Source |
|---|---|---|---|
| Responsable RH (`hr.demo`) | Humain, application | Annuaire, contrats, affectations, propositions salariales, saisie des éléments variables | `database/seeds/002…008`, `app/Auth/AuthService.php::can` |
| Responsable Finance (`finance.demo`) | Humain, application | Décisions salariales, périodes, approbations, paiements fictifs | idem |
| Gestionnaire de paie (`payroll.demo`) | Humain, application | Calcul, vérification, publication, corrections | idem |
| Salarié (`employee.demo`) | Humain, application | Ses **propres** bulletins publiés et leur règlement | idem ; contrôle propriétaire dans `payslip_detail` |
| Administrateur applicatif (`admin.demo`) | Humain, application | Octroi et révocation des rôles **d'autrui** | `011_iam_operations.sql` |
| Auditeur (`audit.demo`) | Humain, application | Lecture de la paie et de l'historique IAM, sans action | idem |
| `svc_php@localhost` | Compte de service MySQL | Connexion PDO de l'application ; droits listés au § 5.2 | `database/setup/svc_php_grants.sql` et `*_grants.sql` |
| Comptes `*_owner@localhost` | Comptes techniques verrouillés | Aucun login ; contexte d'exécution des procédures | `database/setup/*_owner.sql` (`ACCOUNT LOCK`) |
| `root@localhost` de l'instance privée | Administrateur MySQL | Installation et maintenance uniquement, par socket | `bin/init-local.py` (mot de passe dans `.local/admin.json`) |
| Compte de sauvegarde dédié | Compte technique | Export `mysqldump` ; doit préexister, refusé s'il s'agit de `root` ou `svc_php` | `bin/backup.py`, `docs/RECOVERY.md` |

La matrice détaillée rôle × permission figure dans `docs/technical-documentation/TABLEAU-ROLES-ET-PERMISSIONS.md`. Elle sera reprise et justifiée en phase 2.

## 5. Inventaire

### 5.1 Données (tables)

Les 26 tables sont regroupées en ensembles de données. Le niveau de classification, colonne par colonne, est donné dans le livrable 02.

| ID | Ensemble de données | Tables | Propriétaire | Criticité | Dimension dominante | Justification |
|---|---|---|---|---|---|---|
| D-01 | **Données personnelles des salariés** | `employee_personal_data` | Direction RH | **Critique** | C + I | Pièce d'identité, CNSS et RIB permettent l'usurpation d'identité et la fraude sociale. La **modification du RIB** détourne le salaire : c'est la fraude à la paie la plus classique. |
| D-02 | **Rémunérations** | `compensation_requests`, `compensation_decisions`, `salary_conditions`, `compensation_history` | Direction financière | **Critique** | C + I | Les salaires individuels sont l'information la plus convoitée en interne. Une condition salariale altérée fausse toutes les paies suivantes. |
| D-03 | **Calcul et bulletins de paie** | `payroll_periods`, `payroll_inputs`, `payroll_input_decisions`, `payroll_calculations`, `payslip_events`, `payroll_approvals` | Responsable paie | **Critique** | I + C | Les montants brut et net déterminent ce qui est versé. `payroll_calculations.snapshot` **recopie le salaire mensuel jour par jour** : c'est une seconde copie des données de D-02. |
| D-04 | **Règlements et corrections** | `settlement_ledger`, `payslip_corrections`, `correction_events`, `recovery_requests`, `recovery_events` | Direction financière / Responsable paie | **Critique** | I | Registre des sommes versées et restituées. Une écriture falsifiée ou supprimée est une fraude directe. |
| D-05 | **Identifiants d'authentification** | `accounts` | RSSI | **Critique** | C + I | `password_hash` (Argon2id) peut être attaqué hors ligne en cas de fuite. Un compte modifié ou réactivé permet l'usurpation. |
| D-06 | **Contrôle d'accès (RBAC)** | `roles`, `permissions`, `role_permissions`, `role_assignments` | RSSI | **Critique** | I | Une attribution de rôle ajoutée ou prolongée constitue une **élévation de privilèges** ; elle contourne tous les autres contrôles. |
| D-07 | **Identité et parcours professionnel** | `employees`, `employment_contracts`, `employee_assignments` | Direction RH | **Élevée** | C + I | Données à caractère personnel : noms, matricule, type et dates de contrat, départ. Le matricule est la clé de jointure vers les salaires. |
| D-08 | **Référentiels** | `departments`, `positions` | Direction RH | **Modérée** | I | Peu confidentiels ; une altération perturbe les affectations. |

### 5.2 Objets de sécurité de la base

Ces objets **sont** les contrôles. Leur altération désactive la protection des données de § 5.1.

| ID | Actif | Emplacement | Criticité | Dimension dominante | Justification |
|---|---|---|---|---|---|
| S-01 | **24 procédures stockées** (`SQL SECURITY DEFINER`) | `database/migrations/003, 005, 006, 008, 010, 011`, `database/patches/001, 003` | **Critique** | I | Elles portent les règles métier : séparation des tâches, interdiction de l'auto-approbation, plafonds, contrôle du propriétaire d'un bulletin. Une procédure remplacée contourne tout. |
| S-02 | **44 triggers** d'immutabilité et de validation | migrations `001` à `012` | **Critique** | I | Ils rendent les historiques et le registre non modifiables par DML ordinaire. Ils ne résistent pas à un compte disposant de `TRIGGER` ou de DDL. |
| S-03 | **Privilèges MySQL** (`GRANT`) | `database/setup/*_grants.sql` | **Critique** | C + I | Ils définissent ce que le compte de service peut lire et écrire. Un `GRANT` excessif ouvre l'accès direct aux tables. |
| S-04 | **Compte de service `svc_php`** | `database/setup/svc_php_grants.sql`, `compensation_grants.sql`, `advanced_hr_grants.sql`, `payroll_grants.sql`, `settlement_grants.sql`, `iam_grants.sql` | **Critique** | C + I | Compte **partagé** par toutes les sessions web. Il lit directement `employees`, `accounts.password_hash`, les quatre tables de rémunération et les tables RH. Sa compromission expose D-02, D-05 et D-07, et permet d'appeler les procédures au nom de n'importe quel acteur (limite documentée dans `07-SECURITE-RBAC-IAM.md`). Il n'a **aucun** accès à D-01. |
| S-05 | Comptes `*_owner` (DEFINER) | `database/setup/*_owner.sql` | Élevée | I | Verrouillés et sans mot de passe utilisable. Les déverrouiller donnerait les droits d'écriture des modules. |
| S-06 | Compte `root` de l'instance | `.local/admin.json` | **Critique** | C + I + A | Contrôle total : données, droits, triggers, arrêt du serveur. |

### 5.3 Secrets

| ID | Actif | Emplacement | Contenu | Criticité | Justification |
|---|---|---|---|---|---|
| K-01 | Mot de passe `root` MySQL | `.local/admin.json` (fichier 0600, répertoire 0700) | Secret en clair | **Critique** | Équivaut à S-06. |
| K-02 | Configuration de l'application | `.local/application.json` | Mot de passe de `svc_php` **en clair**, chemin du socket | **Critique** | Équivaut à S-04. Lu par `bin/init-local.py serve` et transmis à PHP par variables d'environnement. |
| K-03 | Mots de passe initiaux | `.local/credentials.json` | Mots de passe **en clair** des six comptes web et de `svc_php` | **Critique** | Conservés pour la démonstration (`init-local.py credentials`). C'est une copie en clair de ce que D-05 protège par hachage : point à traiter en phase 9. |
| K-04 | Fichiers de session PHP | `.local/runtime/sess_*` (via `APP_RUNTIME_DIR`, `app/Security/Session.php`) | `account_id`, jeton CSRF | Élevée | Le vol d'un fichier de session permet de prendre la place d'un utilisateur connecté, sans mot de passe. |

### 5.4 Journaux

| ID | Actif | Emplacement | Contenu | Criticité | Dimension dominante | Justification |
|---|---|---|---|---|---|---|
| L-01 | Journal applicatif | `.local/runtime/application.log` (`app/bootstrap.php`, `app/Web/helpers.php::auditEvent`) | Événements JSON : connexions, échecs, refus d'accès, actions métier, avec `actor_id`, `employee_id`, `resource_id` ; erreurs techniques | Élevée | I + A | Seule trace des connexions et des refus. Un journal effacé ou altéré empêche toute investigation (phase 10). Il n'est ni signé ni centralisé. |
| L-02 | Journal d'erreurs MySQL | `.local/mysql.log`, `.local/initialize.log` | Démarrages, arrêts, erreurs serveur | Modérée | I | Utile pour la chronologie d'un incident. |
| L-03 | État du limiteur de connexion | `.local/runtime/login-address-<sha256(IP)>.json` et `login-account-<sha256(identifiant)>.json` (`app/Security/LoginLimiter.php`) | Compteurs de tentatives par adresse et par identifiant (phase 3) | Modérée | I | Supprimer ces fichiers réinitialise la protection contre la force brute. |
| L-04 | Historiques métier en base | `compensation_history`, `payslip_events`, `correction_events`, `recovery_events`, colonnes d'octroi et de révocation de `role_assignments` | Qui, quoi, quand pour chaque décision | **Critique** | I | Piste d'audit des décisions financières. Comptés dans D-02 à D-06, mais cités ici pour leur rôle probatoire. |

### 5.5 Sauvegardes

| ID | Actif | Emplacement | Contenu | Criticité | Dimension dominante | Justification |
|---|---|---|---|---|---|---|
| B-01 | Exports `mysqldump` | Répertoire choisi par l'opérateur (`bin/backup.py --directory`), hors dépôt | **Copie complète de la base**, D-01 à D-08 compris, routines et triggers, en clair | **Critique** | C + A | Un export volé expose toutes les données d'un coup, sans passer par aucun contrôle d'accès. C'est aussi le seul moyen de reprise après perte (phase 8). |
| B-02 | Copies des journaux et manifeste SHA-256 | Même répertoire | Copies de L-01, empreintes | Élevée | I | Le manifeste permet de vérifier qu'une sauvegarde n'a pas été altérée. |

### 5.6 Infrastructure et code

| ID | Actif | Emplacement | Criticité | Dimension dominante | Justification |
|---|---|---|---|---|---|
| I-01 | Répertoire de données InnoDB | `.local/data/` | **Critique** | C + A | Fichiers de la base **non chiffrés au repos** (aucune option de chiffrement InnoDB dans le lanceur). Leur copie équivaut à B-01. |
| I-02 | Serveur MySQL 8.4 privé | Processus `mysqld`, socket `.local/mysql.sock` | **Critique** | A | Sans réseau (`--skip-networking`, `--mysqlx=OFF`, port 0) : seule la machine locale y accède. Son arrêt bloque toute la paie. |
| I-03 | Serveur web PHP | `php -S 127.0.0.1:8080` lancé par `init-local.py serve` | Élevée | A + C | Unique point d'entrée des utilisateurs, en HTTP local, sans TLS. |
| I-04 | Code source et scripts SQL | Dépôt Git privé (`app/`, `public/`, `database/`, `bin/`) | Élevée | I | Une migration ou une procédure modifiée dans le dépôt serait installée avec ses failles. Contrôlé par `bin/audit-secrets.py` pour les secrets, pas pour l'intégrité. |
| I-05 | Machine virtuelle Ubuntu | Poste du collaborateur | **Critique** | C + I + A | Héberge tous les actifs ci-dessus. Son compte utilisateur peut lire `.local/` sans aucune authentification MySQL. |

## 6. Constats à reporter dans les phases suivantes

Ces constats découlent directement de l'inventaire. Ils ne sont pas corrigés ici.

1. **Plusieurs copies des mêmes données critiques**, chacune protégée différemment : les salaires se trouvent dans D-02, dans `snapshot` (D-03), dans B-01 et dans I-01. Protéger une seule copie ne suffit pas. *Concerne les phases 6 et 8.*
2. **Secrets en clair** dans `.local/` (K-01 à K-03), uniquement protégés par les permissions de fichiers. *Phase 9.*
3. **Compte de service partagé et trop large** (S-04) : il lit directement les salaires et les empreintes de mots de passe. *Phases 2 et 9.*
4. **Aucune donnée chiffrée au repos ou en transit** : D-01 est en clair dans I-01 et B-01, et le HTTP local n'est pas chiffré. *Phase 6.*
5. **Journal applicatif non protégé et incomplet** : pas d'identifiant dans les échecs de connexion, pas de trace des lectures de données sensibles. *Phase 7.*
6. **Aucune donnée en base n'est publique** : toute fuite de la base est au minimum une fuite d'information interne.
