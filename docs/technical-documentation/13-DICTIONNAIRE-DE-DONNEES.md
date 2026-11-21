# 13 — Dictionnaire complet des données

> Analyse documentaire du 11 novembre 2026. Le code est la référence de l’implémentation ; les résultats historiques ne sont pas une nouvelle exécution. Aucune migration, donnée métier, attribution, permission ou fonctionnalité n’a été modifiée pendant cette mission. État actuel de MySQL : **Non vérifié** (absence de variables de connexion dans cette session).

Les chemins cités sont relatifs à la racine du projet. Les liens des chapitres renvoient aux sources locales. Les inventaires SQL décrivent le schéma final attendu d’après les migrations et correctifs, sans prétendre remplacer un SHOW CREATE sur l’instance actuelle.

**25 tables déclarées**. Les colonnes de devise des deux tables de rémunération sont présentées après migration 006 : CHAR(3), défaut MAD, CHECK acceptant MAD/UM. La définition initiale 004 utilisait CHAR(2)/UM. Les autres définitions ci-dessous sont celles des CREATE TABLE. Les index de support de FK créés implicitement par InnoDB ne sont pas nommés dans les sources : leurs noms effectifs restent Non vérifié.

## employees

Identité stable des salariés ; matricule permanent, noms et archivage logique.

Source : [database/migrations/001_create_identity_and_rbac.sql](../../database/migrations/001_create_identity_and_rbac.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT | Identifiant technique de la ligne. |
| employee_number | VARCHAR(32) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Matricule métier permanent. |
| first_name | VARCHAR(100) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Prénom. |
| last_name | VARCHAR(100) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Nom de famille. |
| created_at | DATETIME(6) | NOT NULL | DEFAULT CURRENT_TIMESTAMP(6) | Instant de création, précision microseconde. |
| archived_at | DATETIME(6) | NULL autorisé | NULL | Instant d’archivage logique, NULL si non archivé. |

### Clés, contraintes et index déclarés

```sql
PRIMARY KEY (id);
CONSTRAINT uq_employees_number UNIQUE (employee_number);
CONSTRAINT ck_employees_number CHECK (
        CHAR_LENGTH(TRIM(employee_number)) > 0 AND employee_number = TRIM(employee_number)
    );
CONSTRAINT ck_employees_names CHECK (
        CHAR_LENGTH(TRIM(first_name)) > 0 AND CHAR_LENGTH(TRIM(last_name)) > 0
    );
CONSTRAINT ck_employees_archive CHECK (archived_at IS NULL OR archived_at >= created_at);
```

**Triggers associés :** `employees_preserve_identity`, `employees_prevent_delete`.

**Procédures avec référence directe :** `hr_assert_permission`, `hr_create_assignment`, `hr_close_assignment`, `hr_create_contract`, `hr_close_contract`, `compensation_assert_permission`, `compensation_submit`, `compensation_decide`, `payroll_assert`, `payroll_input_submit`, `payroll_input_decide`, `payroll_calculate`, `payslip_transition`, `payroll_overview`, `payslip_detail`, `settlement_command`, `settlement_detail`, `iam_overview`, `iam_grant`, `iam_revoke`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** accounts(employee_id), compensation_decisions(approver_employee_id), compensation_requests(employee_id), compensation_requests(requester_employee_id), correction_events(actor_employee_id), employee_assignments(employee_id), employment_contracts(employee_id), payroll_calculations(employee_id), payroll_calculations(preparer_employee_id), payroll_input_decisions(approver_employee_id), payroll_inputs(creator_employee_id), payroll_inputs(employee_id), payroll_periods(creator_employee_id), payslip_corrections(preparer_employee_id), payslip_events(actor_employee_id), recovery_events(actor_employee_id), recovery_requests(requester_employee_id), salary_conditions(employee_id), settlement_ledger(actor_employee_id).

**Sensibilité :** Identité, décisions et/ou montants salariaux confidentiels ; accès limité selon RBAC.

## accounts

Compte de connexion rattaché à un salarié ; identifiant, empreinte Argon2id et désactivation.

Source : [database/migrations/001_create_identity_and_rbac.sql](../../database/migrations/001_create_identity_and_rbac.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT | Identifiant technique de la ligne. |
| employee_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Salarié concerné ; vérifier la FK ci-dessous. |
| login | VARCHAR(190) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Identifiant de connexion. |
| password_hash | VARCHAR(255) | NOT NULL | COLLATE utf8mb4_bin | Empreinte PHC Argon2id ; donnée d’authentification sensible. |
| created_at | DATETIME(6) | NOT NULL | DEFAULT CURRENT_TIMESTAMP(6) | Instant de création, précision microseconde. |
| disabled_at | DATETIME(6) | NULL autorisé | NULL | Instant de désactivation du compte. |

### Clés, contraintes et index déclarés

```sql
PRIMARY KEY (id);
CONSTRAINT uq_accounts_employee UNIQUE (employee_id);
CONSTRAINT uq_accounts_login UNIQUE (login);
CONSTRAINT fk_accounts_employee FOREIGN KEY (employee_id) REFERENCES employees (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT ck_accounts_login CHECK (
        CHAR_LENGTH(TRIM(login)) > 0 AND login = TRIM(login)
    );
CONSTRAINT ck_accounts_argon2id CHECK (
        REGEXP_LIKE(password_hash,
            '^[$]argon2id[$]v=19[$]m=[1-9][0-9]*,t=[1-9][0-9]*,p=[1-9][0-9]*[$][A-Za-z0-9+/]{16,}[$][A-Za-z0-9+/]{32,}$', 'c')
    );
CONSTRAINT ck_accounts_disabled CHECK (disabled_at IS NULL OR disabled_at >= created_at);
```

**Triggers associés :** `accounts_preserve_identity`, `accounts_prevent_delete`.

**Procédures avec référence directe :** `hr_assert_permission`, `compensation_assert_permission`, `payroll_assert`, `iam_overview`, `iam_grant`, `iam_revoke`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** compensation_decisions(decided_by), compensation_history(actor_id), compensation_requests(requested_by), correction_events(actor_id), employee_assignments(closed_by), employee_assignments(created_by), employment_contracts(closed_by), employment_contracts(created_by), payroll_calculations(prepared_by), payroll_input_decisions(decided_by), payroll_inputs(created_by), payroll_periods(created_by), payslip_corrections(prepared_by), payslip_events(actor_id), recovery_events(actor_id), recovery_requests(requested_by), role_assignments(account_id), role_assignments(granted_by_account_id), role_assignments(revoked_by_account_id), settlement_ledger(actor_id).

**Sensibilité :** Données d’authentification et identité.

## roles

Catalogue fermé des six rôles applicatifs canoniques.

Source : [database/migrations/001_create_identity_and_rbac.sql](../../database/migrations/001_create_identity_and_rbac.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT | Identifiant technique de la ligne. |
| code | VARCHAR(64) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Code stable du catalogue. |
| name | VARCHAR(100) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Nom canonique du rôle. |

### Clés, contraintes et index déclarés

```sql
PRIMARY KEY (id);
CONSTRAINT uq_roles_code UNIQUE (code);
CONSTRAINT uq_roles_name UNIQUE (name);
CONSTRAINT ck_roles_text CHECK (CHAR_LENGTH(TRIM(code)) > 0 AND CHAR_LENGTH(TRIM(name)) > 0);
CONSTRAINT ck_roles_canonical CHECK (
        (CAST(code AS BINARY) = CAST('employee' AS BINARY) AND CAST(name AS BINARY) = CAST('Employee' AS BINARY))
        OR (CAST(code AS BINARY) = CAST('hr_manager' AS BINARY) AND CAST(name AS BINARY) = CAST('HR Manager' AS BINARY))
        OR (CAST(code AS BINARY) = CAST('payroll_manager' AS BINARY) AND CAST(name AS BINARY) = CAST('Payroll Manager' AS BINARY))
        OR (CAST(code AS BINARY) = CAST('finance_manager' AS BINARY) AND CAST(name AS BINARY) = CAST('Finance Manager' AS BINARY))
        OR (CAST(code AS BINARY) = CAST('application_administrator' AS BINARY) AND CAST(name AS BINARY) = CAST('Application Administrator' AS BINARY))
        OR (CAST(code AS BINARY) = CAST('security_auditor' AS BINARY) AND CAST(name AS BINARY) = CAST('Security Auditor' AS BINARY))
    );
```

**Triggers associés :** Aucun déclaré.

**Procédures avec référence directe :** `hr_assert_permission`, `compensation_assert_permission`, `payroll_assert`, `payroll_read_assert`, `iam_overview`, `iam_grant`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** role_assignments(role_id), role_permissions(role_id).

**Sensibilité :** Catalogue de référence ou de sécurité ; les associations révèlent la politique d’accès.

## permissions

Catalogue des capacités métier nommées.

Source : [database/migrations/001_create_identity_and_rbac.sql](../../database/migrations/001_create_identity_and_rbac.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT | Identifiant technique de la ligne. |
| code | VARCHAR(100) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Code stable du catalogue. |
| description | VARCHAR(255) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Description de permission. |

### Clés, contraintes et index déclarés

```sql
PRIMARY KEY (id);
CONSTRAINT uq_permissions_code UNIQUE (code);
CONSTRAINT ck_permissions_text CHECK (
        CHAR_LENGTH(TRIM(code)) > 0 AND CHAR_LENGTH(TRIM(description)) > 0
    );
```

**Triggers associés :** Aucun déclaré.

**Procédures avec référence directe :** `hr_assert_permission`, `compensation_assert_permission`, `payroll_assert`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** role_permissions(permission_id).

**Sensibilité :** Catalogue de référence ou de sécurité ; les associations révèlent la politique d’accès.

## role_permissions

Association N:N entre rôles et permissions.

Source : [database/migrations/001_create_identity_and_rbac.sql](../../database/migrations/001_create_identity_and_rbac.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| role_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| permission_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |

### Clés, contraintes et index déclarés

```sql
PRIMARY KEY (role_id, permission_id);
CONSTRAINT fk_role_permissions_role FOREIGN KEY (role_id) REFERENCES roles (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT fk_role_permissions_permission FOREIGN KEY (permission_id) REFERENCES permissions (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;
```

**Triggers associés :** Aucun déclaré.

**Procédures avec référence directe :** `hr_assert_permission`, `compensation_assert_permission`, `payroll_assert`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** Aucune FK entrante déclarée.

**Sensibilité :** Catalogue de référence ou de sécurité ; les associations révèlent la politique d’accès.

## role_assignments

Attributions temporelles des rôles aux comptes, octroi et révocation traçables.

Source : [database/migrations/001_create_identity_and_rbac.sql](../../database/migrations/001_create_identity_and_rbac.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT | Identifiant technique de la ligne. |
| account_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Compte destinataire de l’attribution. |
| role_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| granted_by_account_id | BIGINT UNSIGNED | NULL autorisé | NULL | Compte auteur de l’opération correspondante ; relation ci-dessous. |
| granted_at | DATETIME(6) | NOT NULL | DEFAULT CURRENT_TIMESTAMP(6) | Instant SQL d’octroi. |
| valid_from | DATETIME(6) | NOT NULL | DEFAULT CURRENT_TIMESTAMP(6) | Début de validité du rôle. |
| expires_at | DATETIME(6) | NULL autorisé | NULL | Expiration optionnelle stricte. |
| grant_reason | VARCHAR(255) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Motif d’octroi conservé. |
| revoked_at | DATETIME(6) | NULL autorisé | NULL | Instant de première révocation. |
| revoked_by_account_id | BIGINT UNSIGNED | NULL autorisé | NULL | Compte auteur de l’opération correspondante ; relation ci-dessous. |
| revocation_reason | VARCHAR(255) | NULL autorisé | NULL | Motif de révocation. |

### Clés, contraintes et index déclarés

```sql
PRIMARY KEY (id);
KEY ix_assignments_access (account_id, role_id, valid_from, expires_at, revoked_at);
CONSTRAINT uq_assignments_start UNIQUE (account_id, role_id, valid_from);
CONSTRAINT fk_assignments_account FOREIGN KEY (account_id) REFERENCES accounts (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT fk_assignments_role FOREIGN KEY (role_id) REFERENCES roles (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT fk_assignments_grantor FOREIGN KEY (granted_by_account_id) REFERENCES accounts (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT fk_assignments_revoker FOREIGN KEY (revoked_by_account_id) REFERENCES accounts (id)
        ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT ck_assignments_validity CHECK (
        valid_from >= granted_at AND (expires_at IS NULL OR expires_at > valid_from)
    );
CONSTRAINT ck_assignments_grant_reason CHECK (CHAR_LENGTH(TRIM(grant_reason)) > 0);
CONSTRAINT ck_assignments_revocation CHECK (
        (revoked_at IS NULL AND revocation_reason IS NULL)
        OR (revoked_at IS NOT NULL AND revoked_at >= granted_at
            AND revocation_reason IS NOT NULL
            AND CHAR_LENGTH(TRIM(revocation_reason)) > 0)
    );
```

**Triggers associés :** `assignments_validate_insert`, `assignments_preserve_history`, `assignments_prevent_delete`.

**Procédures avec référence directe :** `hr_assert_permission`, `compensation_assert_permission`, `payroll_assert`, `payroll_read_assert`, `iam_overview`, `iam_grant`, `iam_revoke`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** Aucune FK entrante déclarée.

**Sensibilité :** Identité, décisions et/ou montants salariaux confidentiels ; accès limité selon RBAC.

## departments

Catalogue bilingue des départements ; archivage logique.

Source : [database/migrations/002_advanced_hr.sql](../../database/migrations/002_advanced_hr.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT PRIMARY KEY | Identifiant technique de la ligne. |
| code | VARCHAR(32) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Code stable du catalogue. |
| name_fr | VARCHAR(120) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Libellé français. |
| name_en | VARCHAR(120) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Libellé anglais. |
| archived_at | DATETIME(6) | NULL autorisé | NULL | Instant d’archivage logique, NULL si non archivé. |

### Clés, contraintes et index déclarés

```sql
CONSTRAINT uq_departments_code UNIQUE (code);
CONSTRAINT ck_departments_text CHECK (CHAR_LENGTH(TRIM(code)) > 0
        AND CHAR_LENGTH(TRIM(name_fr)) > 0 AND CHAR_LENGTH(TRIM(name_en)) > 0);
id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY;
```

**Triggers associés :** Aucun déclaré.

**Procédures avec référence directe :** `hr_create_assignment`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** employee_assignments(department_id).

**Sensibilité :** Catalogue de référence ou de sécurité ; les associations révèlent la politique d’accès.

## positions

Catalogue bilingue des métiers réutilisables entre départements.

Source : [database/migrations/002_advanced_hr.sql](../../database/migrations/002_advanced_hr.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT PRIMARY KEY | Identifiant technique de la ligne. |
| code | VARCHAR(32) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Code stable du catalogue. |
| name_fr | VARCHAR(120) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Libellé français. |
| name_en | VARCHAR(120) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Libellé anglais. |
| archived_at | DATETIME(6) | NULL autorisé | NULL | Instant d’archivage logique, NULL si non archivé. |

### Clés, contraintes et index déclarés

```sql
CONSTRAINT uq_positions_code UNIQUE (code);
CONSTRAINT ck_positions_text CHECK (CHAR_LENGTH(TRIM(code)) > 0
        AND CHAR_LENGTH(TRIM(name_fr)) > 0 AND CHAR_LENGTH(TRIM(name_en)) > 0);
id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY;
```

**Triggers associés :** Aucun déclaré.

**Procédures avec référence directe :** `hr_create_assignment`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** employee_assignments(position_id).

**Sensibilité :** Catalogue de référence ou de sécurité ; les associations révèlent la politique d’accès.

## employee_assignments

Périodes datées d’affectation d’un employé à un département et un poste.

Source : [database/migrations/002_advanced_hr.sql](../../database/migrations/002_advanced_hr.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT PRIMARY KEY | Identifiant technique de la ligne. |
| employee_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Salarié concerné ; vérifier la FK ci-dessous. |
| department_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| position_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| starts_on | DATE | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Début inclusif de période. |
| ends_on | DATE | NULL autorisé | NULL | Fin prévue inclusive ; NULL lorsque le schéma permet une durée ouverte. |
| closed_on | DATE | NULL autorisé | NULL | Fin effective fixée lors de la clôture. |
| effective_ends_on | DATE | Générée (NULL possible) | GENERATED ALWAYS AS (COALESCE(closed_on, ends_on)) STORED | Colonne générée : COALESCE(closed_on, ends_on). |
| created_at | DATETIME(6) | NOT NULL | DEFAULT CURRENT_TIMESTAMP(6) | Instant de création, précision microseconde. |
| created_by | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Compte auteur de l’opération correspondante ; relation ci-dessous. |
| closed_at | DATETIME(6) | NULL autorisé | NULL | Instant technique de clôture. |
| closed_by | BIGINT UNSIGNED | NULL autorisé | NULL | Compte auteur de l’opération correspondante ; relation ci-dessous. |

### Clés, contraintes et index déclarés

```sql
KEY ix_employee_assignments_period (employee_id, starts_on, effective_ends_on);
CONSTRAINT fk_ea_employee FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT fk_ea_department FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT fk_ea_position FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT fk_ea_creator FOREIGN KEY (created_by) REFERENCES accounts(id) ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT fk_ea_closer FOREIGN KEY (closed_by) REFERENCES accounts(id) ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT ck_ea_dates CHECK (starts_on >= '1900-01-01' AND (ends_on IS NULL OR ends_on >= starts_on)
        AND (closed_on IS NULL OR (closed_on >= starts_on AND (ends_on IS NULL OR closed_on <= ends_on))));
CONSTRAINT ck_ea_closure CHECK ((closed_on IS NULL AND closed_at IS NULL)
        OR (closed_on IS NOT NULL AND closed_at IS NOT NULL AND closed_at >= created_at));
id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY;
```

**Triggers associés :** `ea_no_delete`, `ea_preserve_history`.

**Procédures avec référence directe :** `hr_create_assignment`, `hr_close_assignment`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** Aucune FK entrante déclarée.

**Sensibilité :** Identité, décisions et/ou montants salariaux confidentiels ; accès limité selon RBAC.

## employment_contracts

Contrats administratifs datés ; aucun salaire dans cette table.

Source : [database/migrations/002_advanced_hr.sql](../../database/migrations/002_advanced_hr.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT PRIMARY KEY | Identifiant technique de la ligne. |
| employee_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Salarié concerné ; vérifier la FK ci-dessous. |
| reference | VARCHAR(64) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence métier (contrat ou règlement selon table). |
| contract_type | VARCHAR(16) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | permanent, fixed_term ou internship. |
| starts_on | DATE | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Début inclusif de période. |
| ends_on | DATE | NULL autorisé | NULL | Fin prévue inclusive ; NULL lorsque le schéma permet une durée ouverte. |
| closed_on | DATE | NULL autorisé | NULL | Fin effective fixée lors de la clôture. |
| effective_ends_on | DATE | Générée (NULL possible) | GENERATED ALWAYS AS (COALESCE(closed_on, ends_on)) STORED | Colonne générée : COALESCE(closed_on, ends_on). |
| created_at | DATETIME(6) | NOT NULL | DEFAULT CURRENT_TIMESTAMP(6) | Instant de création, précision microseconde. |
| created_by | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Compte auteur de l’opération correspondante ; relation ci-dessous. |
| closed_at | DATETIME(6) | NULL autorisé | NULL | Instant technique de clôture. |
| closed_by | BIGINT UNSIGNED | NULL autorisé | NULL | Compte auteur de l’opération correspondante ; relation ci-dessous. |

### Clés, contraintes et index déclarés

```sql
CONSTRAINT uq_contracts_reference UNIQUE (reference);
KEY ix_contracts_period (employee_id, starts_on, effective_ends_on);
CONSTRAINT fk_ec_employee FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT fk_ec_creator FOREIGN KEY (created_by) REFERENCES accounts(id) ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT fk_ec_closer FOREIGN KEY (closed_by) REFERENCES accounts(id) ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT ck_ec_reference CHECK (CHAR_LENGTH(TRIM(reference)) > 0 AND reference = TRIM(reference));
CONSTRAINT ck_ec_type CHECK ((contract_type = 'permanent' AND ends_on IS NULL)
        OR (contract_type IN ('fixed_term', 'internship') AND ends_on IS NOT NULL));
CONSTRAINT ck_ec_dates CHECK (starts_on >= '1900-01-01' AND (ends_on IS NULL OR ends_on >= starts_on)
        AND (closed_on IS NULL OR (closed_on >= starts_on AND (ends_on IS NULL OR closed_on <= ends_on))));
CONSTRAINT ck_ec_closure CHECK ((closed_on IS NULL AND closed_at IS NULL)
        OR (closed_on IS NOT NULL AND closed_at IS NOT NULL AND closed_at >= created_at));
id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY;
```

**Triggers associés :** `ec_no_delete`, `ec_preserve_history`, `ec_salary_coverage`.

**Procédures avec référence directe :** `hr_create_contract`, `hr_close_contract`, `compensation_check_period`, `payroll_input_decide`, `payroll_build`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** compensation_requests(contract_id), salary_conditions(contract_id).

**Sensibilité :** Identité, décisions et/ou montants salariaux confidentiels ; accès limité selon RBAC.

## compensation_requests

Propositions initiales ou révisions salariales RH, conservées sans modification.

Source : [database/migrations/004_compensation.sql](../../database/migrations/004_compensation.sql). Évolution de devise : [database/migrations/006_mad_currency.sql](../../database/migrations/006_mad_currency.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT PRIMARY KEY | Identifiant technique de la ligne. |
| employee_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Salarié concerné ; vérifier la FK ci-dessous. |
| contract_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| request_kind | VARCHAR(16) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | initial ou revision. |
| monthly_amount | DECIMAL(12,2) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Salaire mensuel de référence, sans flottant. |
| currency | CHAR(3) | NOT NULL | DEFAULT 'MAD' | Devise ; MAD pour les nouvelles opérations, UM historique uniquement en rémunération. |
| effective_on | DATE | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Date d’effet inclusive de la condition ou de la demande. |
| justification | VARCHAR(2000) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Justification RH obligatoire. |
| requested_by | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Compte auteur de l’opération correspondante ; relation ci-dessous. |
| requester_employee_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Identité de la personne agissante conservée pour la séparation des tâches. |
| requested_at | DATETIME(6) | NOT NULL | DEFAULT CURRENT_TIMESTAMP(6) | Horodatage technique de l’événement correspondant. |

### Clés, contraintes et index déclarés

```sql
KEY ix_cr_employee (employee_id,effective_on);
CONSTRAINT fk_cr_employee FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT fk_cr_contract FOREIGN KEY (contract_id) REFERENCES employment_contracts(id) ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT fk_cr_requester FOREIGN KEY (requested_by) REFERENCES accounts(id) ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT fk_cr_person FOREIGN KEY (requester_employee_id) REFERENCES employees(id) ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT ck_cr_amount CHECK (monthly_amount > 0 AND currency IN ('MAD','UM'));
CONSTRAINT ck_cr_kind CHECK (request_kind IN ('initial','revision'));
CONSTRAINT ck_cr_date CHECK (effective_on >= '1900-01-01' AND (request_kind='initial' OR DAYOFMONTH(effective_on)=1));
CONSTRAINT ck_cr_reason CHECK (CHAR_LENGTH(TRIM(justification)) BETWEEN 1 AND 2000);
id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY;
```

**Triggers associés :** `cr_no_update`, `cr_no_delete`.

**Procédures avec référence directe :** `compensation_submit`, `compensation_decide`, `payroll_build`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** compensation_decisions(request_id), compensation_history(request_id).

**Sensibilité :** Identité, décisions et/ou montants salariaux confidentiels ; accès limité selon RBAC.

## compensation_decisions

Décision Finance unique pour chaque demande salariale.

Source : [database/migrations/004_compensation.sql](../../database/migrations/004_compensation.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT PRIMARY KEY | Identifiant technique de la ligne. |
| request_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| decision | VARCHAR(16) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | approved ou rejected. |
| reason | VARCHAR(2000) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Motif obligatoire de l’opération. |
| decided_by | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Compte auteur de l’opération correspondante ; relation ci-dessous. |
| approver_employee_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Identité de la personne agissante conservée pour la séparation des tâches. |
| decided_at | DATETIME(6) | NOT NULL | DEFAULT CURRENT_TIMESTAMP(6) | Horodatage technique de l’événement correspondant. |

### Clés, contraintes et index déclarés

```sql
CONSTRAINT uq_cd_request UNIQUE (request_id);
CONSTRAINT uq_cd_request_id UNIQUE (request_id,id);
CONSTRAINT fk_cd_request FOREIGN KEY (request_id) REFERENCES compensation_requests(id) ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT fk_cd_actor FOREIGN KEY (decided_by) REFERENCES accounts(id) ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT fk_cd_person FOREIGN KEY (approver_employee_id) REFERENCES employees(id) ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT ck_cd_decision CHECK (decision IN ('approved','rejected'));
CONSTRAINT ck_cd_reason CHECK (CHAR_LENGTH(TRIM(reason)) BETWEEN 1 AND 2000);
id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY;
```

**Triggers associés :** `cd_no_update`, `cd_no_delete`.

**Procédures avec référence directe :** `compensation_decide`, `payroll_build`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** salary_conditions(request_id,decision_id).

**Sensibilité :** Identité, décisions et/ou montants salariaux confidentiels ; accès limité selon RBAC.

## salary_conditions

Versions des salaires approuvés, liées à la demande et à la décision.

Source : [database/migrations/004_compensation.sql](../../database/migrations/004_compensation.sql). Évolution de devise : [database/migrations/006_mad_currency.sql](../../database/migrations/006_mad_currency.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT PRIMARY KEY | Identifiant technique de la ligne. |
| employee_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Salarié concerné ; vérifier la FK ci-dessous. |
| contract_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| request_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| decision_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| monthly_amount | DECIMAL(12,2) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Salaire mensuel de référence, sans flottant. |
| currency | CHAR(3) | NOT NULL | DEFAULT 'MAD' | Devise ; MAD pour les nouvelles opérations, UM historique uniquement en rémunération. |
| effective_on | DATE | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Date d’effet inclusive de la condition ou de la demande. |
| recorded_at | DATETIME(6) | NOT NULL | DEFAULT CURRENT_TIMESTAMP(6) | Horodatage technique de l’événement correspondant. |

### Clés, contraintes et index déclarés

```sql
CONSTRAINT uq_sc_request UNIQUE (request_id);
CONSTRAINT uq_sc_employee_date UNIQUE (employee_id,effective_on);
KEY ix_sc_contract_date (contract_id,effective_on);
CONSTRAINT fk_sc_employee FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT fk_sc_contract FOREIGN KEY (contract_id) REFERENCES employment_contracts(id) ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT fk_sc_decision FOREIGN KEY (request_id,decision_id) REFERENCES compensation_decisions(request_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT ck_sc_amount CHECK (monthly_amount>0 AND currency IN ('MAD','UM'));
CONSTRAINT ck_sc_date CHECK (effective_on >= '1900-01-01');
id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY;
```

**Triggers associés :** `sc_no_update`, `sc_no_delete`.

**Procédures avec référence directe :** `compensation_check_period`, `compensation_decide`, `payroll_build`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** Aucune FK entrante déclarée.

**Sensibilité :** Identité, décisions et/ou montants salariaux confidentiels ; accès limité selon RBAC.

## compensation_history

Événements submitted/approved/rejected des demandes salariales.

Source : [database/migrations/004_compensation.sql](../../database/migrations/004_compensation.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT PRIMARY KEY | Identifiant technique de la ligne. |
| request_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| event_type | VARCHAR(16) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Événement du workflow, valeurs limitées par CHECK. |
| actor_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Compte auteur de l’opération correspondante ; relation ci-dessous. |
| occurred_at | DATETIME(6) | NOT NULL | DEFAULT CURRENT_TIMESTAMP(6) | Horodatage technique de l’événement correspondant. |

### Clés, contraintes et index déclarés

```sql
CONSTRAINT uq_ch_event UNIQUE (request_id,event_type);
CONSTRAINT fk_ch_request FOREIGN KEY (request_id) REFERENCES compensation_requests(id) ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT fk_ch_actor FOREIGN KEY (actor_id) REFERENCES accounts(id) ON DELETE RESTRICT ON UPDATE RESTRICT;
CONSTRAINT ck_ch_event CHECK (event_type IN ('submitted','approved','rejected'));
id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY;
```

**Triggers associés :** `ch_no_update`, `ch_no_delete`.

**Procédures avec référence directe :** `compensation_submit`, `compensation_decide`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** Aucune FK entrante déclarée.

**Sensibilité :** Identité, décisions et/ou montants salariaux confidentiels ; accès limité selon RBAC.

## payroll_periods

Mois de paie et plafonds absolus de primes/retenues explicités par Finance.

Source : [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT PRIMARY KEY | Identifiant technique de la ligne. |
| month_start | DATE | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Premier jour du mois de paie. |
| bonus_cap | DECIMAL(12,2) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Plafond absolu mensuel de primes en MAD. |
| deduction_cap | DECIMAL(12,2) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Plafond absolu mensuel de retenues en MAD. |
| reason | VARCHAR(2000) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Motif obligatoire de l’opération. |
| created_by | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Compte auteur de l’opération correspondante ; relation ci-dessous. |
| creator_employee_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Identité de la personne agissante conservée pour la séparation des tâches. |
| created_at | DATETIME(6) | NOT NULL | DEFAULT CURRENT_TIMESTAMP(6) | Instant de création, précision microseconde. |

### Clés, contraintes et index déclarés

```sql
UNIQUE KEY uq_pp_month(month_start);
CONSTRAINT fk_pp_actor FOREIGN KEY(created_by) REFERENCES accounts(id);
CONSTRAINT fk_pp_person FOREIGN KEY(creator_employee_id) REFERENCES employees(id);
CONSTRAINT ck_pp_month CHECK(month_start>='1900-01-01' AND DAYOFMONTH(month_start)=1);
CONSTRAINT ck_pp_caps CHECK(bonus_cap>=0 AND deduction_cap>=0);
CONSTRAINT ck_pp_reason CHECK(CHAR_LENGTH(TRIM(reason)) BETWEEN 1 AND 2000);
id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY;
```

**Triggers associés :** `payroll_periods_no_update`, `payroll_periods_no_delete`.

**Procédures avec référence directe :** `payroll_period_create`, `payroll_input_submit`, `payroll_input_decide`, `payroll_build`, `payroll_overview`, `payslip_detail`, `settlement_command`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** payroll_calculations(period_id), payroll_inputs(period_id).

**Sensibilité :** Identité, décisions et/ou montants salariaux confidentiels ; accès limité selon RBAC.

## payroll_inputs

Primes, retenues et suspensions payées ou non payées proposées par RH.

Source : [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT PRIMARY KEY | Identifiant technique de la ligne. |
| period_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| employee_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Salarié concerné ; vérifier la FK ci-dessous. |
| kind | VARCHAR(16) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | bonus, deduction, paid_leave ou unpaid_leave. |
| amount | DECIMAL(12,2) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Montant selon nature ; zéro pour les suspensions de payroll_inputs. |
| starts_on | DATE | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Début inclusif de période. |
| ends_on | DATE | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Fin prévue inclusive ; NULL lorsque le schéma permet une durée ouverte. |
| reason | VARCHAR(2000) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Motif obligatoire de l’opération. |
| created_by | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Compte auteur de l’opération correspondante ; relation ci-dessous. |
| creator_employee_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Identité de la personne agissante conservée pour la séparation des tâches. |
| created_at | DATETIME(6) | NOT NULL | DEFAULT CURRENT_TIMESTAMP(6) | Instant de création, précision microseconde. |

### Clés, contraintes et index déclarés

```sql
KEY ix_pi_employee(period_id,employee_id);
CONSTRAINT fk_pi_period FOREIGN KEY(period_id) REFERENCES payroll_periods(id);
CONSTRAINT fk_pi_employee FOREIGN KEY(employee_id) REFERENCES employees(id);
CONSTRAINT fk_pi_actor FOREIGN KEY(created_by) REFERENCES accounts(id);
CONSTRAINT fk_pi_person FOREIGN KEY(creator_employee_id) REFERENCES employees(id);
CONSTRAINT ck_pi_dates CHECK(starts_on>='1900-01-01' AND ends_on>=starts_on);
CONSTRAINT ck_pi_amount CHECK((kind IN ('bonus','deduction') AND amount>0) OR (kind IN ('paid_leave','unpaid_leave') AND amount=0));
CONSTRAINT ck_pi_reason CHECK(CHAR_LENGTH(TRIM(reason)) BETWEEN 1 AND 2000);
id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY;
```

**Triggers associés :** `payroll_inputs_no_update`, `payroll_inputs_no_delete`.

**Procédures avec référence directe :** `payroll_input_submit`, `payroll_input_decide`, `payroll_build`, `payroll_overview`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** payroll_input_decisions(input_id).

**Sensibilité :** Identité, décisions et/ou montants salariaux confidentiels ; accès limité selon RBAC.

## payroll_input_decisions

Décision Finance unique sur chaque élément de paie.

Source : [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT PRIMARY KEY | Identifiant technique de la ligne. |
| input_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| decision | VARCHAR(16) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | approved ou rejected. |
| reason | VARCHAR(2000) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Motif obligatoire de l’opération. |
| decided_by | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Compte auteur de l’opération correspondante ; relation ci-dessous. |
| approver_employee_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Identité de la personne agissante conservée pour la séparation des tâches. |
| decided_at | DATETIME(6) | NOT NULL | DEFAULT CURRENT_TIMESTAMP(6) | Horodatage technique de l’événement correspondant. |

### Clés, contraintes et index déclarés

```sql
UNIQUE KEY uq_pid_input(input_id);
CONSTRAINT fk_pid_input FOREIGN KEY(input_id) REFERENCES payroll_inputs(id);
CONSTRAINT fk_pid_actor FOREIGN KEY(decided_by) REFERENCES accounts(id);
CONSTRAINT fk_pid_person FOREIGN KEY(approver_employee_id) REFERENCES employees(id);
CONSTRAINT ck_pid_decision CHECK(decision IN ('approved','rejected'));
CONSTRAINT ck_pid_reason CHECK(CHAR_LENGTH(TRIM(reason)) BETWEEN 1 AND 2000);
id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY;
```

**Triggers associés :** `payroll_input_decisions_no_update`, `payroll_input_decisions_no_delete`.

**Procédures avec référence directe :** `payroll_input_decide`, `payroll_build`, `payroll_overview`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** Aucune FK entrante déclarée.

**Sensibilité :** Identité, décisions et/ou montants salariaux confidentiels ; accès limité selon RBAC.

## payroll_calculations

Versions immuables de calcul, montants et instantané JSON des sources.

Source : [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT PRIMARY KEY | Identifiant technique de la ligne. |
| period_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| employee_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Salarié concerné ; vérifier la FK ci-dessous. |
| version_no | INT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Numéro de version de calcul pour le salarié et le mois. |
| algorithm | VARCHAR(40) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Version de l’algorithme calendar-days-v1. |
| currency | CHAR(3) | NOT NULL | DEFAULT 'MAD' | Devise ; MAD pour les nouvelles opérations, UM historique uniquement en rémunération. |
| base_amount | DECIMAL(12,2) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Base proratisée ou montant complet corrigé. |
| bonus_amount | DECIMAL(12,2) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Total des primes approuvées ou montant corrigé. |
| deduction_amount | DECIMAL(12,2) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Total des retenues approuvées ou montant corrigé. |
| gross_amount | DECIMAL(12,2) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Base + primes. |
| net_amount | DECIMAL(12,2) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Brut − retenues, non négatif. |
| snapshot | JSON | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Instantané JSON des sources de calcul ; données salariales sensibles. |
| source_hash | CHAR(64) | NOT NULL | CHARACTER SET ascii COLLATE ascii_bin | SHA-256 du JSON ; détection de divergence des sources, sans signature externe. |
| prepared_by | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Compte auteur de l’opération correspondante ; relation ci-dessous. |
| preparer_employee_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Identité de la personne agissante conservée pour la séparation des tâches. |
| prepared_at | DATETIME(6) | NOT NULL | DEFAULT CURRENT_TIMESTAMP(6) | Horodatage technique de l’événement correspondant. |

### Clés, contraintes et index déclarés

```sql
UNIQUE KEY uq_pc_version(period_id,employee_id,version_no);
UNIQUE KEY uq_pc_identity(id,period_id,employee_id);
CONSTRAINT fk_pc_period FOREIGN KEY(period_id) REFERENCES payroll_periods(id);
CONSTRAINT fk_pc_employee FOREIGN KEY(employee_id) REFERENCES employees(id);
CONSTRAINT fk_pc_actor FOREIGN KEY(prepared_by) REFERENCES accounts(id);
CONSTRAINT fk_pc_person FOREIGN KEY(preparer_employee_id) REFERENCES employees(id);
CONSTRAINT ck_pc_amounts CHECK(currency='MAD' AND base_amount>=0 AND bonus_amount>=0 AND deduction_amount>=0 AND gross_amount=base_amount+bonus_amount AND net_amount=gross_amount-deduction_amount AND net_amount>=0);
CONSTRAINT ck_pc_version CHECK(version_no>0 AND algorithm='calendar-days-v1');
id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY;
```

**Triggers associés :** `payroll_calculations_no_update`, `payroll_calculations_no_delete`.

**Procédures avec référence directe :** `payroll_calculate`, `payslip_transition`, `payroll_overview`, `payslip_detail`, `settlement_command`, `settlement_detail`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** payroll_approvals(calculation_id,period_id,employee_id), payslip_corrections(calculation_id), payslip_events(calculation_id), recovery_requests(calculation_id), settlement_ledger(calculation_id).

**Sensibilité :** Identité, décisions et/ou montants salariaux confidentiels ; accès limité selon RBAC.

## payslip_events

Transitions motivées de vérification, décision et publication du bulletin.

Source : [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT PRIMARY KEY | Identifiant technique de la ligne. |
| calculation_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| event_type | VARCHAR(16) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Événement du workflow, valeurs limitées par CHECK. |
| reason | VARCHAR(2000) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Motif obligatoire de l’opération. |
| actor_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Compte auteur de l’opération correspondante ; relation ci-dessous. |
| actor_employee_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Identité de la personne agissante conservée pour la séparation des tâches. |
| occurred_at | DATETIME(6) | NOT NULL | DEFAULT CURRENT_TIMESTAMP(6) | Horodatage technique de l’événement correspondant. |

### Clés, contraintes et index déclarés

```sql
UNIQUE KEY uq_pe_event(calculation_id,event_type);
CONSTRAINT fk_pe_calc FOREIGN KEY(calculation_id) REFERENCES payroll_calculations(id);
CONSTRAINT fk_pe_actor FOREIGN KEY(actor_id) REFERENCES accounts(id);
CONSTRAINT fk_pe_person FOREIGN KEY(actor_employee_id) REFERENCES employees(id);
CONSTRAINT ck_pe_type CHECK(event_type IN ('verified','approved','rejected','published'));
CONSTRAINT ck_pe_reason CHECK(CHAR_LENGTH(TRIM(reason)) BETWEEN 1 AND 2000);
id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY;
```

**Triggers associés :** `payslip_events_no_update`, `payslip_events_no_delete`.

**Procédures avec référence directe :** `payslip_transition`, `payroll_overview`, `payslip_detail`, `settlement_command`, `settlement_detail`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** Aucune FK entrante déclarée.

**Sensibilité :** Identité, décisions et/ou montants salariaux confidentiels ; accès limité selon RBAC.

## payroll_approvals

Ancrage de l’unique calcul approuvé pour un salarié et un mois.

Source : [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| calculation_id | BIGINT UNSIGNED | NOT NULL | PRIMARY KEY | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| period_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| employee_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Salarié concerné ; vérifier la FK ci-dessous. |

### Clés, contraintes et index déclarés

```sql
UNIQUE KEY uq_pa_employee_month(period_id,employee_id);
CONSTRAINT fk_pa_calc FOREIGN KEY(calculation_id,period_id,employee_id) REFERENCES payroll_calculations(id,period_id,employee_id);
calculation_id BIGINT UNSIGNED NOT NULL PRIMARY KEY;
```

**Triggers associés :** `payroll_approvals_no_update`, `payroll_approvals_no_delete`.

**Procédures avec référence directe :** `payroll_input_submit`, `payroll_input_decide`, `payroll_calculate`, `payslip_transition`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** Aucune FK entrante déclarée.

**Sensibilité :** Identité, décisions et/ou montants salariaux confidentiels ; accès limité selon RBAC.

## payslip_corrections

Versions exceptionnelles de remplacement des montants d’un bulletin publié.

Source : [database/migrations/009_settlement.sql](../../database/migrations/009_settlement.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT PRIMARY KEY | Identifiant technique de la ligne. |
| calculation_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| parent_id | BIGINT UNSIGNED | NULL autorisé | NULL | Correction publiée précédente ; FK composée conservant la même racine. |
| revision | INT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Numéro de correction pour le calcul racine. |
| base_amount | DECIMAL(12,2) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Base proratisée ou montant complet corrigé. |
| bonus_amount | DECIMAL(12,2) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Total des primes approuvées ou montant corrigé. |
| deduction_amount | DECIMAL(12,2) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Total des retenues approuvées ou montant corrigé. |
| gross_amount | DECIMAL(12,2) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Base + primes. |
| net_amount | DECIMAL(12,2) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Brut − retenues, non négatif. |
| currency | CHAR(3) | NOT NULL | DEFAULT 'MAD' | Devise ; MAD pour les nouvelles opérations, UM historique uniquement en rémunération. |
| reason | VARCHAR(2000) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Motif obligatoire de l’opération. |
| prepared_by | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Compte auteur de l’opération correspondante ; relation ci-dessous. |
| preparer_employee_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Identité de la personne agissante conservée pour la séparation des tâches. |
| prepared_at | DATETIME(6) | NOT NULL | DEFAULT CURRENT_TIMESTAMP(6) | Horodatage technique de l’événement correspondant. |

### Clés, contraintes et index déclarés

```sql
UNIQUE KEY uq_correction_revision(calculation_id,revision);
UNIQUE KEY uq_correction_root(id,calculation_id);
FOREIGN KEY(calculation_id) REFERENCES payroll_calculations(id);
FOREIGN KEY(parent_id,calculation_id) REFERENCES payslip_corrections(id,calculation_id);
FOREIGN KEY(prepared_by) REFERENCES accounts(id);
FOREIGN KEY(preparer_employee_id) REFERENCES employees(id);
CHECK(revision>0 AND currency='MAD' AND base_amount>=0 AND bonus_amount>=0 AND deduction_amount>=0 AND gross_amount=base_amount+bonus_amount AND net_amount=gross_amount-deduction_amount AND net_amount>=0);
CHECK(CHAR_LENGTH(TRIM(reason)) BETWEEN 1 AND 2000);
id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY;
```

**Triggers associés :** `payslip_corrections_no_update`, `payslip_corrections_no_delete`.

**Procédures avec référence directe :** `settlement_command`, `settlement_detail`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** correction_events(correction_id), payslip_corrections(parent_id,calculation_id), recovery_requests(correction_id,calculation_id), settlement_ledger(correction_id,calculation_id).

**Sensibilité :** Identité, décisions et/ou montants salariaux confidentiels ; accès limité selon RBAC.

## correction_events

Vérification, décision et publication des corrections.

Source : [database/migrations/009_settlement.sql](../../database/migrations/009_settlement.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT PRIMARY KEY | Identifiant technique de la ligne. |
| correction_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| event_type | VARCHAR(16) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Événement du workflow, valeurs limitées par CHECK. |
| reason | VARCHAR(2000) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Motif obligatoire de l’opération. |
| actor_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Compte auteur de l’opération correspondante ; relation ci-dessous. |
| actor_employee_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Identité de la personne agissante conservée pour la séparation des tâches. |
| occurred_at | DATETIME(6) | NOT NULL | DEFAULT CURRENT_TIMESTAMP(6) | Horodatage technique de l’événement correspondant. |

### Clés, contraintes et index déclarés

```sql
UNIQUE KEY uq_correction_event(correction_id,event_type);
FOREIGN KEY(correction_id) REFERENCES payslip_corrections(id);
FOREIGN KEY(actor_id) REFERENCES accounts(id);
FOREIGN KEY(actor_employee_id) REFERENCES employees(id);
CHECK(event_type IN ('verified','approved','rejected','published'));
CHECK(CHAR_LENGTH(TRIM(reason)) BETWEEN 1 AND 2000);
id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY;
```

**Triggers associés :** `correction_events_no_update`, `correction_events_no_delete`.

**Procédures avec référence directe :** `settlement_command`, `settlement_detail`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** Aucune FK entrante déclarée.

**Sensibilité :** Identité, décisions et/ou montants salariaux confidentiels ; accès limité selon RBAC.

## recovery_requests

Demandes de restitution d’un trop-perçu fictif.

Source : [database/migrations/009_settlement.sql](../../database/migrations/009_settlement.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT PRIMARY KEY | Identifiant technique de la ligne. |
| calculation_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| correction_id | BIGINT UNSIGNED | NULL autorisé | NULL | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| amount | DECIMAL(12,2) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Montant selon nature ; zéro pour les suspensions de payroll_inputs. |
| reason | VARCHAR(2000) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Motif obligatoire de l’opération. |
| requested_by | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Compte auteur de l’opération correspondante ; relation ci-dessous. |
| requester_employee_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Identité de la personne agissante conservée pour la séparation des tâches. |
| requested_at | DATETIME(6) | NOT NULL | DEFAULT CURRENT_TIMESTAMP(6) | Horodatage technique de l’événement correspondant. |

### Clés, contraintes et index déclarés

```sql
FOREIGN KEY(calculation_id) REFERENCES payroll_calculations(id);
FOREIGN KEY(correction_id,calculation_id) REFERENCES payslip_corrections(id,calculation_id);
FOREIGN KEY(requested_by) REFERENCES accounts(id);
FOREIGN KEY(requester_employee_id) REFERENCES employees(id);
CHECK(amount>0);
CHECK(CHAR_LENGTH(TRIM(reason)) BETWEEN 1 AND 2000);
id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY;
```

**Triggers associés :** `recovery_requests_no_update`, `recovery_requests_no_delete`.

**Procédures avec référence directe :** `settlement_command`, `settlement_detail`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** recovery_events(request_id), settlement_ledger(recovery_id).

**Sensibilité :** Identité, décisions et/ou montants salariaux confidentiels ; accès limité selon RBAC.

## recovery_events

Approbation, rejet et réception des restitutions.

Source : [database/migrations/009_settlement.sql](../../database/migrations/009_settlement.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT PRIMARY KEY | Identifiant technique de la ligne. |
| request_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| event_type | VARCHAR(16) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Événement du workflow, valeurs limitées par CHECK. |
| reason | VARCHAR(2000) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Motif obligatoire de l’opération. |
| actor_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Compte auteur de l’opération correspondante ; relation ci-dessous. |
| actor_employee_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Identité de la personne agissante conservée pour la séparation des tâches. |
| occurred_at | DATETIME(6) | NOT NULL | DEFAULT CURRENT_TIMESTAMP(6) | Horodatage technique de l’événement correspondant. |

### Clés, contraintes et index déclarés

```sql
UNIQUE KEY uq_recovery_event(request_id,event_type);
FOREIGN KEY(request_id) REFERENCES recovery_requests(id);
FOREIGN KEY(actor_id) REFERENCES accounts(id);
FOREIGN KEY(actor_employee_id) REFERENCES employees(id);
CHECK(event_type IN ('approved','rejected','received'));
CHECK(CHAR_LENGTH(TRIM(reason)) BETWEEN 1 AND 2000);
id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY;
```

**Triggers associés :** `recovery_events_no_update`, `recovery_events_no_delete`.

**Procédures avec référence directe :** `settlement_command`, `settlement_detail`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** Aucune FK entrante déclarée.

**Sensibilité :** Identité, décisions et/ou montants salariaux confidentiels ; accès limité selon RBAC.

## settlement_ledger

Écritures immuables des paiements et remboursements fictifs avec référence unique.

Source : [database/migrations/009_settlement.sql](../../database/migrations/009_settlement.sql).

| Colonne | Type SQL | Nullabilité | Défaut / génération / attributs | Sens |
|---|---|---|---|---|
| id | BIGINT UNSIGNED | NOT NULL | AUTO_INCREMENT PRIMARY KEY | Identifiant technique de la ligne. |
| calculation_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| correction_id | BIGINT UNSIGNED | NULL autorisé | NULL | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| recovery_id | BIGINT UNSIGNED | NULL autorisé | NULL | Référence à l’objet métier correspondant ; définition exacte dans les clés étrangères. |
| entry_type | VARCHAR(16) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | payment ou recovery. |
| amount | DECIMAL(12,2) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Montant selon nature ; zéro pour les suspensions de payroll_inputs. |
| currency | CHAR(3) | NOT NULL | DEFAULT 'MAD' | Devise ; MAD pour les nouvelles opérations, UM historique uniquement en rémunération. |
| reference | VARCHAR(64) | NOT NULL | CHARACTER SET ascii COLLATE ascii_bin | Référence métier (contrat ou règlement selon table). |
| reason | VARCHAR(2000) | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Motif obligatoire de l’opération. |
| actor_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Compte auteur de l’opération correspondante ; relation ci-dessous. |
| actor_employee_id | BIGINT UNSIGNED | NOT NULL | Aucun défaut explicite ; NULL implicite si nullable | Identité de la personne agissante conservée pour la séparation des tâches. |
| occurred_at | DATETIME(6) | NOT NULL | DEFAULT CURRENT_TIMESTAMP(6) | Horodatage technique de l’événement correspondant. |

### Clés, contraintes et index déclarés

```sql
UNIQUE KEY uq_settlement_reference(reference);
UNIQUE KEY uq_recovery_receipt(recovery_id);
FOREIGN KEY(calculation_id) REFERENCES payroll_calculations(id);
FOREIGN KEY(correction_id,calculation_id) REFERENCES payslip_corrections(id,calculation_id);
FOREIGN KEY(recovery_id) REFERENCES recovery_requests(id);
FOREIGN KEY(actor_id) REFERENCES accounts(id);
FOREIGN KEY(actor_employee_id) REFERENCES employees(id);
CHECK(amount>0 AND currency='MAD');
CHECK((entry_type='payment' AND recovery_id IS NULL) OR (entry_type='recovery' AND recovery_id IS NOT NULL));
CHECK(CHAR_LENGTH(reference) BETWEEN 8 AND 64);
CHECK(CHAR_LENGTH(TRIM(reason)) BETWEEN 1 AND 2000);
id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY;
```

**Triggers associés :** `settlement_ledger_no_update`, `settlement_ledger_no_delete`.

**Procédures avec référence directe :** `settlement_command`, `settlement_detail`. Les appels imbriqués peuvent consulter d’autres tables via les assertions RBAC.

**Références entrantes :** Aucune FK entrante déclarée.

**Sensibilité :** Identité, décisions et/ou montants salariaux confidentiels ; accès limité selon RBAC.
