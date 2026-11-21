# Phase 2 — Utilisateurs, rôles et matrice de contrôle d'accès

> Livrable de la phase 2 : catégories d'utilisateurs, matrice de contrôle d'accès, utilisateurs, rôles et privilèges MySQL, démonstration du moindre privilège.
> Sources : `database/setup/app_roles.sql`, `database/setup/operator_roles.sql`, `app/Database/SessionRoles.php`, `bin/init-local.py`.
> Preuves : `tests/local-install.py` (94 contrôles, dont la matrice de `tests/privilege_matrix.py`) et `tests/database-roles-unit.php` (23 contrôles).

## 1. Le problème corrigé

Jusqu'à la phase 1, toute l'application se connectait avec **un seul compte MySQL**, `svc_php`, qui détenait l'**union** des privilèges de tous les rôles métier. Le contrôle d'accès reposait donc entièrement sur le PHP (`AuthService::can`). Une erreur de code ou une injection SQL dans une page ouverte à un simple salarié s'exécutait avec des droits suffisants pour lire tous les salaires et toutes les empreintes de mots de passe : c'était l'écart **E1** et la menace **T-10**.

**Principe retenu** : le contrôle d'accès est appliqué **deux fois**, par l'application **et** par MySQL.
- Chaque rôle applicatif a désormais un **rôle MySQL** équivalent.
- `svc_php` détient tous ces rôles, mais **n'en active aucun d'office**.
- À chaque requête, l'application active uniquement les rôles de l'utilisateur authentifié (`SET ROLE`).
- Les procédures stockées continuent, en plus, de vérifier le rôle de l'acteur.

## 2. Catégories d'utilisateurs

| Catégorie | Compte(s) | Type | Rôle MySQL | Accès |
|---|---|---|---|---|
| Salarié | `employee.demo` | Personne, application | `sp_employee` | Ses bulletins publiés et leur règlement |
| Responsable RH | `hr.demo` | Personne, application | `sp_hr_manager` | Identité, contrats, affectations, propositions salariales, éléments variables |
| Responsable Finance | `finance.demo` | Personne, application | `sp_finance_manager` | Décisions salariales, périodes, approbations, paiements |
| Gestionnaire de paie | `payroll.demo` | Personne, application | `sp_payroll_manager` | Calcul, vérification, publication, corrections |
| Administrateur applicatif | `admin.demo` | Personne, application | `sp_application_administrator` | Attribution et révocation des rôles d'autrui |
| Auditeur de sécurité | `audit.demo` | Personne, application | `sp_security_auditor` | Lecture de l'IAM et de la paie, sans action |
| **Compte de service** | `svc_php@localhost` | Technique | Les 8 rôles `sp_*` ci-dessus et ci-dessous, aucun actif d'office sauf `sp_session` | Connexion PDO de l'application |
| **Administrateur de base (DBA)** | `dba_ops@localhost` | Personne, SQL | `sp_dba` | Maintenance du schéma ; ni comptes ni droits |
| **Opérateur de sauvegarde** | `backup_ops@localhost` | Technique, SQL | `sp_backup` | Export `mysqldump`, lecture seule |
| **Auditeur SQL** | `audit_ops@localhost` | Personne, SQL | `sp_db_auditor` | Traces et historiques, sans aucune donnée Restreint |
| Propriétaires des procédures | `hr_module_owner`, `compensation_owner`, `payroll_owner`, `settlement_owner`, `iam_owner` | Technique, **verrouillé** | Privilèges directs | Contexte `DEFINER` ; aucune connexion possible |
| Administrateur MySQL | `root@localhost` | Personne | Tous | Installation, comptes et rôles uniquement ; socket local |

Les mots de passe des comptes d'exploitation sont générés à l'installation et conservés dans `.local/operators.json` (mode 0600). Ils s'affichent avec `python3 bin/init-local.py credentials`.

## 3. Matrice de contrôle d'accès — niveau application

Permissions enregistrées dans `role_permissions` (31) et vérifiées par `AuthService::can`. ● = autorisé.

| Domaine | Permission | Salarié | RH | Finance | Paie | Admin | Auditeur |
|---|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Identité | `employees.read` / `.create` / `.update` | | ● | | | | |
| Référentiels | `departments.read`, `positions.read` | | ● | | | | |
| Contrats | `contracts.read` / `.create` / `.close` | | ● | | | | |
| Affectations | `assignments.read` / `.create` / `.close` | | ● | | | | |
| Rémunération | `compensation.read` | | ● | ● | | | |
| | `compensation.submit` | | ● | | | | |
| | `compensation.decide` | | | ● | | | |
| Paie | `payroll.read` | | ● | ● | ● | | ● |
| | `payroll.period.create`, `payroll.input.decide` | | | ● | | | |
| | `payroll.input.submit` | | ● | | | | |
| | `payroll.calculate` | | | | ● | | |
| Bulletins | `payslip.verify`, `payslip.publish`, `payslip.correct` | | | | ● | | |
| | `payslip.decide` (approuver ou rejeter) | | | ● | | | |
| | `payslip.self` (ses bulletins publiés) | ● | | | | | |
| Règlements | `payroll.payment`, `payroll.recovery.decide` | | | ● | | | |
| | `payroll.recovery.request`, `payroll.recovery.receive` | | | | ● | | |
| IAM | `iam.read` | | | | | ● | ● |
| | `iam.grant`, `iam.revoke` | | | | | ● | |

**Séparation des tâches**, imposée en plus de la matrice :
- un même salarié ne peut pas cumuler deux rôles parmi RH, Finance, Paie, Admin et Auditeur (`payroll_conflict`) ;
- personne ne décide de sa propre rémunération (`COMP_SELF_APPROVAL`) ;
- le préparateur d'un bulletin ne l'approuve pas (`PAY_FORBIDDEN`) ;
- un administrateur ne s'attribue pas de rôle à lui-même (`IAM_FORBIDDEN`).

## 4. Matrice de contrôle d'accès — niveau base de données

### 4.1 Architecture

```text
 Requête HTTP ──► AuthService::currentUser()      sous sp_session (rôle par défaut)
                 │  relit le compte et ses rôles applicatifs actifs
                 ▼
                 SessionRoles::activate()          SET ROLE 'sp_session','sp_<rôle>'…
                 ▼
                 Contrôleur ──► SELECT / CALL      MySQL vérifie les privilèges du rôle actif
                                                   ──► la procédure vérifie p_actor (2e niveau)

 POST /login ──► SessionRoles::duringLogin()       SET ROLE 'sp_login' → lecture de l'empreinte
                                                   → SET ROLE DEFAULT
```

- `sp_session`, actif à chaque requête, relit le compte et ses attributions. Il ne donne **jamais** accès à `password_hash`. Depuis l'embauche (document 09), il lit aussi `login`, `password_change_required` et `password_changed_at`. Un compte dont le mot de passe temporaire n'a pas encore été changé n'a **que** ce rôle actif.
- `sp_login` est le **seul** rôle qui lit `password_hash`. Il n'est actif que pendant la requête de connexion, ou pendant la vérification du mot de passe actuel avant un changement.
- `sp_password` n'exécute que `account_change_password`. Il est actif le temps de cet appel seulement (`SessionRoles::duringPasswordChange`).
- Les noms de rôles passés à `SET ROLE` viennent d'une **liste fermée** dans le code, jamais d'une donnée reçue. En cas de cumul interdit, seul `sp_employee` reste activable.

### 4.2 Procédures stockées (EXECUTE)

Vérifiée par `tests/privilege_matrix.py`. ● = exécutable ; sinon MySQL refuse avec l'erreur **1370**.

| Procédure | Salarié | RH | Finance | Paie | Admin | Auditeur |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| `payroll_overview`, `payslip_detail`, `settlement_detail` | ● | ● | ● | ● | | ● |
| `hr_create_contract`, `hr_close_contract`, `hr_create_assignment`, `hr_close_assignment` | | ● | | | | |
| `compensation_submit` | | ● | | | | |
| `payroll_input_submit` | | ● | | | | |
| `compensation_decide` | | | ● | | | |
| `payroll_period_create`, `payroll_input_decide` | | | ● | | | |
| `payslip_transition`, `settlement_command` | | | ● | ● | | |
| `payroll_calculate` | | | | ● | | |
| `iam_overview` | | | | | ● | ● |
| `iam_grant`, `iam_revoke` | | | | | ● | |
| `account_onboard` (embauche : salarié, compte, invitation, rôle Employé) | | ● | | | | |

`account_change_password` n'est exécutable par aucun de ces six rôles : seulement par `sp_password` (voir 4.1).

`payslip_transition` et `settlement_command` sont accessibles à Finance **et** à Paie, car elles regroupent plusieurs actions. La procédure applique ensuite la répartition fine : Paie vérifie et publie, Finance approuve et paie.

### 4.3 Tables (lecture et écriture directes)

| Table | Salarié | RH | Finance | Paie | Admin | Auditeur |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| `employees`, `roles`, `permissions`, `role_permissions` ; colonnes non sensibles d'`accounts` et de `role_assignments` | L | L | L | L | L | L |
| `employees` (UPDATE du nom et du prénom ; la création passe par `account_onboard`) | | É | | | | |
| `departments`, `positions`, `employee_assignments` | | L | | | | |
| `employment_contracts` | | L | L | | | |
| `compensation_requests`, `compensation_decisions`, `salary_conditions`, `compensation_history` | | L | L | | | |
| `employee_personal_data`, `account_invitations` (e-mail personnel), `payroll_inputs`, `payroll_calculations`, `payslip_corrections`, `recovery_requests`, `settlement_ledger` | — | — | — | — | — | — |

L = lecture ; É = écriture ; — = aucun accès direct, quel que soit le rôle. Ces dernières données ne sont accessibles **qu'au travers des procédures**.

`accounts.password_hash` n'est lisible par **aucun** de ces rôles : seulement par `sp_login`, pendant la requête de connexion.

### 4.4 Comptes d'exploitation

| Rôle | Privilèges | Refus vérifiés | Justification |
|---|---|---|---|
| `sp_dba` | `ALL PRIVILEGES ON secure_payroll.*` ; aucun privilège global ; pas de `GRANT OPTION` | `CREATE USER` (1227), `GRANT` (1142), lecture de `mysql.user` (1142) | Le DBA maintient le schéma mais ne gère ni les comptes ni les droits, réservés à `root`. Sans `SET_USER_ID`, il ne peut pas créer une procédure au nom d'un compte propriétaire. |
| `sp_backup` | `SELECT, SHOW VIEW, TRIGGER, EVENT, LOCK TABLES` sur le schéma, `SHOW_ROUTINE` global | Toute écriture (1142) | Exactement ce qu'exige `bin/backup.py`. La recette réalise une sauvegarde complète avec ce seul rôle. |
| `sp_db_auditor` | Lecture des historiques, des attributions et du registre **sans** la colonne `amount` ; colonnes d'`accounts` **sans** `password_hash` | `settlement_ledger.amount` (1143), `employee_personal_data` (1142), `password_hash` (1143) | L'investigation (phase 10) exige de savoir qui a fait quoi, pas de voir les montants. |

**Politique des comptes.**
- `dba_ops` et `audit_ops` : verrouillés pendant 1 jour après **5 échecs** de connexion (`FAILED_LOGIN_ATTEMPTS 5 PASSWORD_LOCK_TIME 1`), mot de passe expirant après **90 jours**.
- `backup_ops` et `svc_php` n'ont **pas** de verrouillage. Un tiers pourrait sinon bloquer la sauvegarde ou toute l'application en tapant de faux mots de passe : c'est l'arbitrage disponibilité contre confidentialité de la menace T-18.

## 5. Démonstration des concepts exigés

| Concept | Où | Preuve (`tests/local-install.py`) |
|---|---|---|
| **CREATE USER** | `bin/init-local.py` : `svc_php`, `dba_ops`, `backup_ops`, `audit_ops` (avec politique de mot de passe) ; `database/setup/*_owner.sql` : 5 propriétaires verrouillés | « Trois comptes d'exploitation, mots de passe distincts » ; « Comptes humains : expiration à 90 jours, verrouillage après 5 échecs » |
| **CREATE ROLE** | `app_roles.sql` (8 rôles), `operator_roles.sql` (3 rôles), `onboarding_grants.sql` (`sp_password`) | L'installateur vérifie la présence des 12 rôles (`assert_roles`) |
| **GRANT** (privilèges) | `GRANT … TO 'sp_…'`, au niveau table, colonne et procédure | Matrice des 6 rôles applicatifs et de `sp_password` : 20 procédures et 15 tables |
| **GRANT** (rôle à un compte) et **SET DEFAULT ROLE** | `GRANT 'sp_session', … TO 'svc_php'@'localhost'` ; `SET DEFAULT ROLE 'sp_session'` | « Rôle actif par défaut : sp_session seul » |
| **Activation de rôle** | `SET ROLE` à chaque requête (`SessionRoles.php`) | « Rôle Salarié : salaires illisibles en base » ; « Rôle RH : lecture des conditions salariales autorisée » ; « Rôle non accordé impossible à activer » (3530) |
| **REVOKE** (privilèges) | `REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'svc_php'@'localhost'` en tête d'`app_roles.sql` | « SHOW GRANTS svc_php : aucun privilège direct, neuf rôles accordés » ; contrôle de l'installateur sur `mysql.tables_priv`, `columns_priv`, `procs_priv` et `db` |
| **REVOKE** (rôle) | `REVOKE 'sp_db_auditor' FROM 'audit_ops'@'localhost'` | « REVOKE du rôle : schéma inaccessible dès la session suivante » (1044), puis « Rôle réattribué et actif » |
| **SHOW GRANTS** | `SHOW GRANTS FOR` (droits déclarés), `SHOW GRANTS` dans la session (droits effectifs), `SHOW GRANTS … USING` (droits d'une combinaison de rôles) | « SHOW GRANTS ... USING : privilèges effectifs du Salarié » |
| **Test des privilèges** | `tests/privilege_matrix.py` : chaque rôle × 20 procédures × 15 tables, sans aucune modification de données | 7 contrôles de matrice et « Matrice vérifiée sans aucune modification de données » |

**Différence importante pour la soutenance.** Pour `svc_php` :
- `SHOW GRANTS FOR 'svc_php'@'localhost'`, exécuté par root, n'affiche que `USAGE` et la liste des 8 rôles : ce sont les droits **déclarés** ;
- `SHOW GRANTS;`, exécuté dans la session de `svc_php`, affiche en plus les privilèges de `sp_session`, le rôle **actif** : ce sont les droits **effectifs**.

Extrait réel :

```text
mysql> SHOW GRANTS FOR 'svc_php'@'localhost' USING 'sp_session','sp_employee';
GRANT USAGE ON *.* TO `svc_php`@`localhost`
GRANT SELECT (`disabled_at`, `employee_id`, `id`) ON `secure_payroll`.`accounts` TO `svc_php`@`localhost`
GRANT SELECT ON `secure_payroll`.`employees` TO `svc_php`@`localhost`
GRANT SELECT (`code`, `id`) ON `secure_payroll`.`permissions` TO `svc_php`@`localhost`
GRANT SELECT (`account_id`, `expires_at`, `revoked_at`, `role_id`, `valid_from`) ON `secure_payroll`.`role_assignments` TO `svc_php`@`localhost`
GRANT SELECT (`permission_id`, `role_id`) ON `secure_payroll`.`role_permissions` TO `svc_php`@`localhost`
GRANT SELECT (`code`, `id`, `name`) ON `secure_payroll`.`roles` TO `svc_php`@`localhost`
GRANT EXECUTE ON PROCEDURE `secure_payroll`.`payroll_overview` TO `svc_php`@`localhost`
GRANT EXECUTE ON PROCEDURE `secure_payroll`.`payslip_detail` TO `svc_php`@`localhost`
GRANT EXECUTE ON PROCEDURE `secure_payroll`.`settlement_detail` TO `svc_php`@`localhost`
GRANT `sp_application_administrator`@`%`,…,`sp_session`@`%` TO `svc_php`@`localhost`
```

Aucune ligne ne mentionne `salary_conditions` ni `password_hash` : une requête de session Salarié ne peut techniquement pas les lire.

### Démonstration manuelle (jury)

L'instance doit être démarrée (`python3 bin/init-local.py start`). Les mots de passe s'affichent avec `python3 bin/init-local.py credentials`.

```bash
S=.local/mysql.sock
# 1. Droits déclarés et effectifs
mysql --socket=$S -u root -p -e "SHOW GRANTS FOR 'svc_php'@'localhost';"
mysql --socket=$S -u root -p -e "SHOW GRANTS FOR 'svc_php'@'localhost' USING 'sp_session','sp_employee';"
# 2. Même compte, rôle Salarié puis RH : refus (1142) puis accès
mysql --socket=$S -u svc_php -p secure_payroll -e "SET ROLE 'sp_session','sp_employee'; SELECT COUNT(*) FROM salary_conditions;"
mysql --socket=$S -u svc_php -p secure_payroll -e "SET ROLE 'sp_session','sp_hr_manager'; SELECT COUNT(*) FROM salary_conditions;"
# 3. Auditeur SQL : traces lisibles, montants illisibles (1143)
mysql --socket=$S -u audit_ops -p secure_payroll -e "SELECT event_type, occurred_at FROM payslip_events;"
mysql --socket=$S -u audit_ops -p secure_payroll -e "SELECT amount FROM settlement_ledger;"
# 4. REVOKE puis GRANT d'un rôle
mysql --socket=$S -u root -p -e "REVOKE 'sp_db_auditor' FROM 'audit_ops'@'localhost';"
mysql --socket=$S -u audit_ops -p secure_payroll -e "SELECT 1;"        # refusé (1044)
mysql --socket=$S -u root -p -e "GRANT 'sp_db_auditor' TO 'audit_ops'@'localhost'; SET DEFAULT ROLE 'sp_db_auditor' TO 'audit_ops'@'localhost';"
```

## 6. Moindre privilège : avant et après

| Situation | Avant (phase 1) | Après (phase 2) |
|---|---|---|
| Requête d'une session Salarié | Pouvait lire `salary_conditions`, `compensation_requests`, `password_hash` | Ne peut exécuter que 3 procédures de lecture, filtrées par l'acteur |
| Requête d'une session Auditeur ou Paie | Mêmes droits que RH et Finance | Aucune lecture directe des tables de rémunération |
| Empreintes de mots de passe | Lisibles par toute requête | Lisibles **uniquement** sous `sp_login`, pendant la connexion |
| Droits déclarés de `svc_php` | 34 instructions `GRANT` directes (tables, colonnes, procédures) | `USAGE` et 8 rôles |
| Exploitation de la base | `root` pour tout : installation, sauvegarde, investigation | Un compte et un rôle par tâche ; `root` réservé aux comptes et aux droits |

**Écart E1 : corrigé** pour toutes les sessions applicatives sauf RH et Finance, qui doivent lire les rémunérations par conception (`compensation.read`).

**Ce qui est réduit** : l'impact d'une injection SQL ou d'une erreur de code (T-05). Une instruction exécutée dans une page n'opère qu'avec les droits du rôle de l'utilisateur connecté, et une injection ne peut pas changer de rôle : `SET ROLE` est une instruction distincte, et les requêtes préparées natives (`ATTR_EMULATE_PREPARES=false`) n'en exécutent qu'une à la fois.

**Ce qui n'est pas réduit** : le vol du mot de passe de `svc_php` (T-03, T-10). Ce secret permet d'activer tous les rôles accordés au compte (§ 7).

## 7. Limites et risques résiduels

| Limite | Conséquence | Traitement |
|---|---|---|
| `svc_php` détient tous les rôles : **qui vole son mot de passe** peut tous les activer | Le gain porte sur les injections et les erreurs de code, pas sur le vol du secret (T-03) | Protection du secret, phase 9 |
| MySQL ne vérifie pas que les rôles activés et `p_actor` correspondent à l'utilisateur web réel | Le PHP reste dans la base de confiance | Inhérent à un compte de service partagé ; les procédures revérifient l'acteur |
| `sp_session` lit toute la table `employees`, et pas seulement la ligne de l'utilisateur | Un salarié peut lire, en base, les noms et matricules de ses collègues (Confidentiel) ; ni montant ni identifiant officiel | Les droits MySQL ne filtrent pas les lignes. Une procédure de lecture dédiée est possible, mais elle a été jugée disproportionnée. |
| Le DBA lit et modifie toutes les données du schéma | Risque interne accepté (T-14) | Détection par journalisation, phase 7 |
| Les 5 comptes propriétaires gardent des privilèges directs | Sans effet : ils sont verrouillés et ne servent que de contexte `DEFINER` | Accepté |
| Les fichiers historiques `*_grants.sql` accordent encore des droits directs, révoqués ensuite par `app_roles.sql` | Une installation qui omettrait `app_roles.sql` serait dans l'état de la phase 1 | L'installateur refuse de terminer si `svc_php` garde un privilège direct (`assert_roles`) |
| `employee_personal_data` n'a encore **aucun** accès applicatif | Protégée par l'absence d'accès, pas encore par une procédure dédiée | Lecture et modification du RIB par procédure avec double validation (T-08), phases 6 et 7 |

## 8. Reproduire

```bash
php tests/database-roles-unit.php                         # sélection des rôles, sans connexion
PYTHONDONTWRITEBYTECODE=1 python3 tests/local-install.py  # instance neuve : 94 contrôles
```

**Instance locale existante (`.local/`).** Elle a été installée avant la phase 2 et ne contient pas les rôles MySQL. Le nouveau code PHP y répondrait par une erreur 503. Il faut la réinstaller, ce qui produit de nouveaux mots de passe et remet les données de démonstration à zéro :

```bash
python3 bin/init-local.py stop
mv .local .local.avant-phase2      # conserver l'ancienne instance, ne rien supprimer
python3 bin/init-local.py init
```
