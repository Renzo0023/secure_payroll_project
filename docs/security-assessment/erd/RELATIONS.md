# Inventaire des relations (clés étrangères)

> Fichier **généré** par `python3 bin/generate-erd.py` depuis `database/migrations/*.sql`. Ne pas modifier à la main.

**28 tables, 68 clés étrangères** : 34 structurelles et 34 de traçabilité (auteur d'une action, omises de la vue globale).

Cardinalité « parent → enfant » : `1` le parent est obligatoire ; `0..1` la clé étrangère accepte NULL (avec une clé composite, MySQL ne contrôle pas la référence dès qu'une composante est NULL) ; côté enfant, `0..1` quand les colonnes de la clé étrangère contiennent une clé primaire ou unique de l'enfant.

| Table enfant | Colonnes | Table parente (colonnes) | Cardinalité | Nature |
|---|---|---|---|---|
| `employee_personal_data` | `employee_id` | `employees`(`id`) | 1 → 0..1 | Structurelle |
| `employee_personal_data` | `created_by` | `accounts`(`id`) | 1 → 0..N | Traçabilité |
| `employee_personal_data` | `updated_by` | `accounts`(`id`) | 0..1 → 0..N | Traçabilité |
| `accounts` | `employee_id` | `employees`(`id`) | 1 → 0..1 | Structurelle |
| `role_permissions` | `role_id` | `roles`(`id`) | 1 → 0..N | Structurelle |
| `role_permissions` | `permission_id` | `permissions`(`id`) | 1 → 0..N | Structurelle |
| `role_assignments` | `account_id` | `accounts`(`id`) | 1 → 0..N | Structurelle |
| `role_assignments` | `role_id` | `roles`(`id`) | 1 → 0..N | Structurelle |
| `role_assignments` | `granted_by_account_id` | `accounts`(`id`) | 0..1 → 0..N | Traçabilité |
| `role_assignments` | `revoked_by_account_id` | `accounts`(`id`) | 0..1 → 0..N | Traçabilité |
| `account_invitations` | `account_id` | `accounts`(`id`) | 1 → 0..N | Structurelle |
| `account_invitations` | `issued_by_account_id` | `accounts`(`id`) | 1 → 0..N | Traçabilité |
| `employee_assignments` | `employee_id` | `employees`(`id`) | 1 → 0..N | Structurelle |
| `employee_assignments` | `department_id` | `departments`(`id`) | 1 → 0..N | Structurelle |
| `employee_assignments` | `position_id` | `positions`(`id`) | 1 → 0..N | Structurelle |
| `employee_assignments` | `created_by` | `accounts`(`id`) | 1 → 0..N | Traçabilité |
| `employee_assignments` | `closed_by` | `accounts`(`id`) | 0..1 → 0..N | Traçabilité |
| `employment_contracts` | `employee_id` | `employees`(`id`) | 1 → 0..N | Structurelle |
| `employment_contracts` | `created_by` | `accounts`(`id`) | 1 → 0..N | Traçabilité |
| `employment_contracts` | `closed_by` | `accounts`(`id`) | 0..1 → 0..N | Traçabilité |
| `compensation_requests` | `employee_id` | `employees`(`id`) | 1 → 0..N | Structurelle |
| `compensation_requests` | `contract_id` | `employment_contracts`(`id`) | 1 → 0..N | Structurelle |
| `compensation_requests` | `requested_by` | `accounts`(`id`) | 1 → 0..N | Traçabilité |
| `compensation_requests` | `requester_employee_id` | `employees`(`id`) | 1 → 0..N | Traçabilité |
| `compensation_decisions` | `request_id` | `compensation_requests`(`id`) | 1 → 0..1 | Structurelle |
| `compensation_decisions` | `decided_by` | `accounts`(`id`) | 1 → 0..N | Traçabilité |
| `compensation_decisions` | `approver_employee_id` | `employees`(`id`) | 1 → 0..N | Traçabilité |
| `salary_conditions` | `employee_id` | `employees`(`id`) | 1 → 0..N | Structurelle |
| `salary_conditions` | `contract_id` | `employment_contracts`(`id`) | 1 → 0..N | Structurelle |
| `salary_conditions` | `request_id, decision_id` | `compensation_decisions`(`request_id, id`) | 1 → 0..1 | Structurelle |
| `compensation_history` | `request_id` | `compensation_requests`(`id`) | 1 → 0..N | Structurelle |
| `compensation_history` | `actor_id` | `accounts`(`id`) | 1 → 0..N | Traçabilité |
| `payroll_periods` | `created_by` | `accounts`(`id`) | 1 → 0..N | Traçabilité |
| `payroll_periods` | `creator_employee_id` | `employees`(`id`) | 1 → 0..N | Traçabilité |
| `payroll_inputs` | `period_id` | `payroll_periods`(`id`) | 1 → 0..N | Structurelle |
| `payroll_inputs` | `employee_id` | `employees`(`id`) | 1 → 0..N | Structurelle |
| `payroll_inputs` | `created_by` | `accounts`(`id`) | 1 → 0..N | Traçabilité |
| `payroll_inputs` | `creator_employee_id` | `employees`(`id`) | 1 → 0..N | Traçabilité |
| `payroll_input_decisions` | `input_id` | `payroll_inputs`(`id`) | 1 → 0..1 | Structurelle |
| `payroll_input_decisions` | `decided_by` | `accounts`(`id`) | 1 → 0..N | Traçabilité |
| `payroll_input_decisions` | `approver_employee_id` | `employees`(`id`) | 1 → 0..N | Traçabilité |
| `payroll_calculations` | `period_id` | `payroll_periods`(`id`) | 1 → 0..N | Structurelle |
| `payroll_calculations` | `employee_id` | `employees`(`id`) | 1 → 0..N | Structurelle |
| `payroll_calculations` | `prepared_by` | `accounts`(`id`) | 1 → 0..N | Traçabilité |
| `payroll_calculations` | `preparer_employee_id` | `employees`(`id`) | 1 → 0..N | Traçabilité |
| `payslip_events` | `calculation_id` | `payroll_calculations`(`id`) | 1 → 0..N | Structurelle |
| `payslip_events` | `actor_id` | `accounts`(`id`) | 1 → 0..N | Traçabilité |
| `payslip_events` | `actor_employee_id` | `employees`(`id`) | 1 → 0..N | Traçabilité |
| `payroll_approvals` | `calculation_id, period_id, employee_id` | `payroll_calculations`(`id, period_id, employee_id`) | 1 → 0..1 | Structurelle |
| `payslip_corrections` | `calculation_id` | `payroll_calculations`(`id`) | 1 → 0..N | Structurelle |
| `payslip_corrections` | `parent_id, calculation_id` | `payslip_corrections`(`id, calculation_id`) | 0..1 → 0..N | Structurelle |
| `payslip_corrections` | `prepared_by` | `accounts`(`id`) | 1 → 0..N | Traçabilité |
| `payslip_corrections` | `preparer_employee_id` | `employees`(`id`) | 1 → 0..N | Traçabilité |
| `correction_events` | `correction_id` | `payslip_corrections`(`id`) | 1 → 0..N | Structurelle |
| `correction_events` | `actor_id` | `accounts`(`id`) | 1 → 0..N | Traçabilité |
| `correction_events` | `actor_employee_id` | `employees`(`id`) | 1 → 0..N | Traçabilité |
| `recovery_requests` | `calculation_id` | `payroll_calculations`(`id`) | 1 → 0..N | Structurelle |
| `recovery_requests` | `correction_id, calculation_id` | `payslip_corrections`(`id, calculation_id`) | 0..1 → 0..N | Structurelle |
| `recovery_requests` | `requested_by` | `accounts`(`id`) | 1 → 0..N | Traçabilité |
| `recovery_requests` | `requester_employee_id` | `employees`(`id`) | 1 → 0..N | Traçabilité |
| `recovery_events` | `request_id` | `recovery_requests`(`id`) | 1 → 0..N | Structurelle |
| `recovery_events` | `actor_id` | `accounts`(`id`) | 1 → 0..N | Traçabilité |
| `recovery_events` | `actor_employee_id` | `employees`(`id`) | 1 → 0..N | Traçabilité |
| `settlement_ledger` | `calculation_id` | `payroll_calculations`(`id`) | 1 → 0..N | Structurelle |
| `settlement_ledger` | `correction_id, calculation_id` | `payslip_corrections`(`id, calculation_id`) | 0..1 → 0..N | Structurelle |
| `settlement_ledger` | `recovery_id` | `recovery_requests`(`id`) | 0..1 → 0..1 | Structurelle |
| `settlement_ledger` | `actor_id` | `accounts`(`id`) | 1 → 0..N | Traçabilité |
| `settlement_ledger` | `actor_employee_id` | `employees`(`id`) | 1 → 0..N | Traçabilité |
