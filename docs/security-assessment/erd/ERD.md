# ERD de SecurePayroll

> Fichier **généré** par `python3 bin/generate-erd.py` depuis `database/migrations/*.sql`. Ne pas modifier à la main. Les diagrammes s'affichent sur GitHub et dans l'aperçu Markdown de VS Code ; les sources `.mmd` sont à côté de ce fichier.

Notation : `PK` clé primaire, `FK` clé étrangère, `UK` membre d'une contrainte d'unicité ; `"NULL"` colonne facultative ; `"RESTREINT"` donnée du niveau le plus sensible (voir `02-CLASSIFICATION-DES-DONNEES.md`) ; `"auteur → accounts"` clé étrangère de traçabilité, signalée sans trait pour la lisibilité (liste complète dans `RELATIONS.md`). Liens : `||` exactement un, `|o` zéro ou un, `o{` zéro ou plusieurs.

## vue globale (relations structurelles)

Source : [`ERD-00-GLOBAL.mmd`](ERD-00-GLOBAL.mmd)

```mermaid
---
title: SecurePayroll — vue globale (relations structurelles)
config:
  er:
    layoutDirection: LR
---
erDiagram
    employees {
        bigint id PK
    }
    employee_personal_data {
        bigint employee_id PK
    }
    accounts {
        bigint id PK
    }
    roles {
        bigint id PK
    }
    permissions {
        bigint id PK
    }
    role_permissions {
        bigint role_id PK
        bigint permission_id PK
    }
    role_assignments {
        bigint id PK
    }
    account_invitations {
        bigint id PK
    }
    departments {
        bigint id PK
    }
    positions {
        bigint id PK
    }
    employee_assignments {
        bigint id PK
    }
    employment_contracts {
        bigint id PK
    }
    compensation_requests {
        bigint id PK
    }
    compensation_decisions {
        bigint id PK
    }
    salary_conditions {
        bigint id PK
    }
    compensation_history {
        bigint id PK
    }
    payroll_periods {
        bigint id PK
    }
    payroll_inputs {
        bigint id PK
    }
    payroll_input_decisions {
        bigint id PK
    }
    payroll_calculations {
        bigint id PK
    }
    payslip_events {
        bigint id PK
    }
    payroll_approvals {
        bigint calculation_id PK
    }
    payslip_corrections {
        bigint id PK
    }
    correction_events {
        bigint id PK
    }
    recovery_requests {
        bigint id PK
    }
    recovery_events {
        bigint id PK
    }
    settlement_ledger {
        bigint id PK
    }
    employees ||--o| employee_personal_data : "employee_id"
    employees ||--o| accounts : "employee_id"
    roles ||--o{ role_permissions : "role_id"
    permissions ||--o{ role_permissions : "permission_id"
    accounts ||--o{ role_assignments : "account_id"
    roles ||--o{ role_assignments : "role_id"
    accounts ||--o{ account_invitations : "account_id"
    employees ||--o{ employee_assignments : "employee_id"
    departments ||--o{ employee_assignments : "department_id"
    positions ||--o{ employee_assignments : "position_id"
    employees ||--o{ employment_contracts : "employee_id"
    employees ||--o{ compensation_requests : "employee_id"
    employment_contracts ||--o{ compensation_requests : "contract_id"
    compensation_requests ||--o| compensation_decisions : "request_id"
    employees ||--o{ salary_conditions : "employee_id"
    employment_contracts ||--o{ salary_conditions : "contract_id"
    compensation_decisions ||--o| salary_conditions : "request_id, decision_id"
    compensation_requests ||--o{ compensation_history : "request_id"
    payroll_periods ||--o{ payroll_inputs : "period_id"
    employees ||--o{ payroll_inputs : "employee_id"
    payroll_inputs ||--o| payroll_input_decisions : "input_id"
    payroll_periods ||--o{ payroll_calculations : "period_id"
    employees ||--o{ payroll_calculations : "employee_id"
    payroll_calculations ||--o{ payslip_events : "calculation_id"
    payroll_calculations ||--o| payroll_approvals : "calculation_id, period_id, employee_id"
    payroll_calculations ||--o{ payslip_corrections : "calculation_id"
    payslip_corrections |o--o{ payslip_corrections : "parent_id, calculation_id"
    payslip_corrections ||--o{ correction_events : "correction_id"
    payroll_calculations ||--o{ recovery_requests : "calculation_id"
    payslip_corrections |o--o{ recovery_requests : "correction_id, calculation_id"
    recovery_requests ||--o{ recovery_events : "request_id"
    payroll_calculations ||--o{ settlement_ledger : "calculation_id"
    payslip_corrections |o--o{ settlement_ledger : "correction_id, calculation_id"
    recovery_requests |o--o| settlement_ledger : "recovery_id"
```

## Identité, données personnelles et RBAC

Source : [`ERD-01-IDENTITE-RBAC.mmd`](ERD-01-IDENTITE-RBAC.mmd)

```mermaid
---
title: SecurePayroll — Identité, données personnelles et RBAC
---
erDiagram
    employees {
        bigint id PK
        varchar(32) employee_number UK
        varchar(100) first_name
        varchar(100) last_name
        datetime(6) created_at
        datetime(6) archived_at "NULL"
    }
    employee_personal_data {
        bigint employee_id PK, FK
        varchar(16) id_document_type UK
        varchar(12) id_document_number UK "RESTREINT"
        char(9) cnss_number UK "NULL · RESTREINT"
        date birth_date
        varchar(16) marital_status
        tinyint dependent_children
        varchar(254) personal_email
        varchar(13) personal_phone
        varchar(255) address_line
        varchar(100) city
        char(5) postal_code
        varchar(100) bank_name
        char(24) rib UK "RESTREINT"
        bigint created_by FK "auteur → accounts"
        datetime(6) created_at
        bigint updated_by FK "NULL · auteur → accounts"
        datetime(6) updated_at "NULL"
    }
    accounts {
        bigint id PK
        bigint employee_id FK, UK
        varchar(190) login UK
        varchar(255) password_hash "RESTREINT"
        datetime(6) created_at
        datetime(6) disabled_at "NULL"
        boolean password_change_required
        datetime(6) temporary_password_expires_at "NULL"
        datetime(6) password_changed_at "NULL"
    }
    roles {
        bigint id PK
        varchar(64) code UK
        varchar(100) name UK
    }
    permissions {
        bigint id PK
        varchar(100) code UK
        varchar(255) description
    }
    role_permissions {
        bigint role_id PK, FK
        bigint permission_id PK, FK
    }
    role_assignments {
        bigint id PK
        bigint account_id FK, UK
        bigint role_id FK, UK
        bigint granted_by_account_id FK "NULL · auteur → accounts"
        datetime(6) granted_at
        datetime(6) valid_from UK
        datetime(6) expires_at "NULL"
        varchar(255) grant_reason
        datetime(6) revoked_at "NULL"
        bigint revoked_by_account_id FK "NULL · auteur → accounts"
        varchar(255) revocation_reason "NULL"
    }
    account_invitations {
        bigint id PK
        bigint account_id FK
        varchar(254) personal_email
        bigint issued_by_account_id FK "auteur → accounts"
        datetime(6) issued_at
        datetime(6) expires_at
    }
    employees ||--o| employee_personal_data : "employee_id"
    employees ||--o| accounts : "employee_id"
    roles ||--o{ role_permissions : "role_id"
    permissions ||--o{ role_permissions : "permission_id"
    accounts ||--o{ role_assignments : "account_id"
    roles ||--o{ role_assignments : "role_id"
    accounts ||--o{ account_invitations : "account_id"
```

## Organisation RH

Source : [`ERD-02-ORGANISATION-RH.mmd`](ERD-02-ORGANISATION-RH.mmd)

```mermaid
---
title: SecurePayroll — Organisation RH
---
erDiagram
    departments {
        bigint id PK
        varchar(32) code UK
        varchar(120) name_fr
        varchar(120) name_en
        datetime(6) archived_at "NULL"
    }
    positions {
        bigint id PK
        varchar(32) code UK
        varchar(120) name_fr
        varchar(120) name_en
        datetime(6) archived_at "NULL"
    }
    employee_assignments {
        bigint id PK
        bigint employee_id FK
        bigint department_id FK
        bigint position_id FK
        date starts_on
        date ends_on "NULL"
        date closed_on "NULL"
        date effective_ends_on "calculée · NULL"
        datetime(6) created_at
        bigint created_by FK "auteur → accounts"
        datetime(6) closed_at "NULL"
        bigint closed_by FK "NULL · auteur → accounts"
    }
    employment_contracts {
        bigint id PK
        bigint employee_id FK
        varchar(64) reference UK
        varchar(16) contract_type
        date starts_on
        date ends_on "NULL"
        date closed_on "NULL"
        date effective_ends_on "calculée · NULL"
        datetime(6) created_at
        bigint created_by FK "auteur → accounts"
        datetime(6) closed_at "NULL"
        bigint closed_by FK "NULL · auteur → accounts"
    }
    employees {
        bigint id PK "autre domaine"
    }
    employees ||--o{ employee_assignments : "employee_id"
    departments ||--o{ employee_assignments : "department_id"
    positions ||--o{ employee_assignments : "position_id"
    employees ||--o{ employment_contracts : "employee_id"
```

## Rémunération

Source : [`ERD-03-REMUNERATION.mmd`](ERD-03-REMUNERATION.mmd)

```mermaid
---
title: SecurePayroll — Rémunération
---
erDiagram
    compensation_requests {
        bigint id PK
        bigint employee_id FK
        bigint contract_id FK
        varchar(16) request_kind
        decimal monthly_amount "RESTREINT"
        char(3) currency
        date effective_on
        varchar(2000) justification
        bigint requested_by FK "auteur → accounts"
        bigint requester_employee_id FK "auteur → employees"
        datetime(6) requested_at
    }
    compensation_decisions {
        bigint id PK
        bigint request_id FK, UK
        varchar(16) decision
        varchar(2000) reason
        bigint decided_by FK "auteur → accounts"
        bigint approver_employee_id FK "auteur → employees"
        datetime(6) decided_at
    }
    salary_conditions {
        bigint id PK
        bigint employee_id FK, UK
        bigint contract_id FK
        bigint request_id FK, UK
        bigint decision_id FK
        decimal monthly_amount "RESTREINT"
        char(3) currency
        date effective_on UK
        datetime(6) recorded_at
    }
    compensation_history {
        bigint id PK
        bigint request_id FK, UK
        varchar(16) event_type UK
        bigint actor_id FK "auteur → accounts"
        datetime(6) occurred_at
    }
    employees {
        bigint id PK "autre domaine"
    }
    employment_contracts {
        bigint id PK "autre domaine"
    }
    employees ||--o{ compensation_requests : "employee_id"
    employment_contracts ||--o{ compensation_requests : "contract_id"
    compensation_requests ||--o| compensation_decisions : "request_id"
    employees ||--o{ salary_conditions : "employee_id"
    employment_contracts ||--o{ salary_conditions : "contract_id"
    compensation_decisions ||--o| salary_conditions : "request_id, decision_id"
    compensation_requests ||--o{ compensation_history : "request_id"
```

## Paie et bulletins

Source : [`ERD-04-PAIE.mmd`](ERD-04-PAIE.mmd)

```mermaid
---
title: SecurePayroll — Paie et bulletins
---
erDiagram
    payroll_periods {
        bigint id PK
        date month_start UK
        decimal bonus_cap
        decimal deduction_cap
        varchar(2000) reason
        bigint created_by FK "auteur → accounts"
        bigint creator_employee_id FK "auteur → employees"
        datetime(6) created_at
    }
    payroll_inputs {
        bigint id PK
        bigint period_id FK
        bigint employee_id FK
        varchar(16) kind
        decimal amount "RESTREINT"
        date starts_on
        date ends_on
        varchar(2000) reason
        bigint created_by FK "auteur → accounts"
        bigint creator_employee_id FK "auteur → employees"
        datetime(6) created_at
    }
    payroll_input_decisions {
        bigint id PK
        bigint input_id FK, UK
        varchar(16) decision
        varchar(2000) reason
        bigint decided_by FK "auteur → accounts"
        bigint approver_employee_id FK "auteur → employees"
        datetime(6) decided_at
    }
    payroll_calculations {
        bigint id PK
        bigint period_id FK, UK
        bigint employee_id FK, UK
        int version_no UK
        varchar(40) algorithm
        char(3) currency
        decimal base_amount "RESTREINT"
        decimal bonus_amount "RESTREINT"
        decimal deduction_amount "RESTREINT"
        decimal gross_amount "RESTREINT"
        decimal net_amount "RESTREINT"
        json snapshot "RESTREINT"
        char(64) source_hash
        bigint prepared_by FK "auteur → accounts"
        bigint preparer_employee_id FK "auteur → employees"
        datetime(6) prepared_at
    }
    payslip_events {
        bigint id PK
        bigint calculation_id FK, UK
        varchar(16) event_type UK
        varchar(2000) reason
        bigint actor_id FK "auteur → accounts"
        bigint actor_employee_id FK "auteur → employees"
        datetime(6) occurred_at
    }
    payroll_approvals {
        bigint calculation_id PK, FK
        bigint period_id FK, UK
        bigint employee_id FK, UK
    }
    employees {
        bigint id PK "autre domaine"
    }
    payroll_periods ||--o{ payroll_inputs : "period_id"
    employees ||--o{ payroll_inputs : "employee_id"
    payroll_inputs ||--o| payroll_input_decisions : "input_id"
    payroll_periods ||--o{ payroll_calculations : "period_id"
    employees ||--o{ payroll_calculations : "employee_id"
    payroll_calculations ||--o{ payslip_events : "calculation_id"
    payroll_calculations ||--o| payroll_approvals : "calculation_id, period_id, employee_id"
```

## Règlements et corrections

Source : [`ERD-05-REGLEMENTS.mmd`](ERD-05-REGLEMENTS.mmd)

```mermaid
---
title: SecurePayroll — Règlements et corrections
---
erDiagram
    payslip_corrections {
        bigint id PK
        bigint calculation_id FK, UK
        bigint parent_id FK "NULL"
        int revision UK
        decimal base_amount "RESTREINT"
        decimal bonus_amount "RESTREINT"
        decimal deduction_amount "RESTREINT"
        decimal gross_amount "RESTREINT"
        decimal net_amount "RESTREINT"
        char(3) currency
        varchar(2000) reason
        bigint prepared_by FK "auteur → accounts"
        bigint preparer_employee_id FK "auteur → employees"
        datetime(6) prepared_at
    }
    correction_events {
        bigint id PK
        bigint correction_id FK, UK
        varchar(16) event_type UK
        varchar(2000) reason
        bigint actor_id FK "auteur → accounts"
        bigint actor_employee_id FK "auteur → employees"
        datetime(6) occurred_at
    }
    recovery_requests {
        bigint id PK
        bigint calculation_id FK
        bigint correction_id FK "NULL"
        decimal amount "RESTREINT"
        varchar(2000) reason
        bigint requested_by FK "auteur → accounts"
        bigint requester_employee_id FK "auteur → employees"
        datetime(6) requested_at
    }
    recovery_events {
        bigint id PK
        bigint request_id FK, UK
        varchar(16) event_type UK
        varchar(2000) reason
        bigint actor_id FK "auteur → accounts"
        bigint actor_employee_id FK "auteur → employees"
        datetime(6) occurred_at
    }
    settlement_ledger {
        bigint id PK
        bigint calculation_id FK
        bigint correction_id FK "NULL"
        bigint recovery_id FK, UK "NULL"
        varchar(16) entry_type
        decimal amount "RESTREINT"
        char(3) currency
        varchar(64) reference UK
        varchar(2000) reason
        bigint actor_id FK "auteur → accounts"
        bigint actor_employee_id FK "auteur → employees"
        datetime(6) occurred_at
    }
    payroll_calculations {
        bigint id PK "autre domaine"
    }
    payroll_calculations ||--o{ payslip_corrections : "calculation_id"
    payslip_corrections |o--o{ payslip_corrections : "parent_id, calculation_id"
    payslip_corrections ||--o{ correction_events : "correction_id"
    payroll_calculations ||--o{ recovery_requests : "calculation_id"
    payslip_corrections |o--o{ recovery_requests : "correction_id, calculation_id"
    recovery_requests ||--o{ recovery_events : "request_id"
    payroll_calculations ||--o{ settlement_ledger : "calculation_id"
    payslip_corrections |o--o{ settlement_ledger : "correction_id, calculation_id"
    recovery_requests |o--o| settlement_ledger : "recovery_id"
```
