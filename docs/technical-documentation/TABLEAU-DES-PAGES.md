# Tableau récapitulatif des pages

> Routes constatées dans le code ; rôles conditionnés par leurs permissions et l’absence de conflits.

| Page | Route | Description | Rôles autorisés | Contrôleur | Données utilisées |
|---|---|---|---|---|---|
| Connexion | /login | Vue login | Public | Controller | Session |
| Tableau de bord | /dashboard | Vue dashboard | Tout compte actif authentifié | Controller | Identité, rôles, permissions |
| Annuaire | /employees | Vue employees | RH | Controller | employees |
| Création d’un employé | /employees/new | Vue employee-form | RH | Controller | employees |
| Fiche employé / profil personnel | /employees/{id} | Vue employee | RH ; tout compte actif pour sa propre fiche | Controller | employees |
| Modification d’identité | /employees/{id}/edit | Vue employee-form | RH | Controller | employees |
| Départements | /departments | Vue hr-catalogue | RH | AdvancedHRController | departments |
| Postes | /positions | Vue hr-catalogue | RH | AdvancedHRController | positions |
| Liste des contracts | /contracts | Vue hr-period-list | RH | AdvancedHRController | employment_contracts, employees |
| Historique individuel des contracts | /employees/{id}/contracts | Vue hr-period-list | RH | AdvancedHRController | employment_contracts, employees |
| Création contracts | /contracts/new | Vue hr-period-form | RH | AdvancedHRController | employment_contracts, employees, hr_create_contract |
| Détail contracts | /contracts/{id} | Vue hr-period-detail | RH | AdvancedHRController | employment_contracts |
| Liste des assignments | /assignments | Vue hr-period-list | RH | AdvancedHRController | employee_assignments, employees |
| Historique individuel des assignments | /employees/{id}/assignments | Vue hr-period-list | RH | AdvancedHRController | employee_assignments, employees |
| Création assignments | /assignments/new | Vue hr-period-form | RH | AdvancedHRController | employee_assignments, employees, departments, positions ; hr_create_assignment |
| Détail assignments | /assignments/{id} | Vue hr-period-detail | RH | AdvancedHRController | employee_assignments |
| Demandes salariales | /compensation | Vue compensation-list | RH, Finance | CompensationController | compensation_requests, compensation_decisions, salary_conditions, employment_contracts, employees |
| Employés sous contrat | /compensation/employees | Vue compensation-list | RH, Finance | CompensationController | compensation_requests, compensation_decisions, salary_conditions, employment_contracts, employees |
| Approbations Finance en attente | /compensation/pending | Vue compensation-list | RH, Finance | CompensationController | compensation_requests, compensation_decisions, salary_conditions, employment_contracts, employees |
| Historique des conditions salariales | /compensation/history | Vue compensation-list | RH, Finance | CompensationController | compensation_requests, compensation_decisions, salary_conditions, employment_contracts, employees |
| Proposition salariale | /compensation/new | Vue compensation-form | RH, Finance | CompensationController | compensation_submit ; compensation_requests, compensation_history |
| Détail de demande salariale | /compensation/{id} | Vue compensation-detail | RH, Finance | CompensationController | compensation_requests, compensation_decisions, compensation_history, employees, employment_contracts |
| Paie / espace employé | /payroll | Vue payroll | RH, Paie, Finance, Audit, Employé | PayrollController | payroll_overview |
| Bulletin de salaire | /payslips/{id} | Vue payslip | RH, Paie, Finance, Audit ; Employé pour son bulletin publié | PayrollController | payslip_detail |
| Règlements, corrections et remboursements | /payslips/{id}/settlement | Vue settlement | RH, Paie, Finance, Audit ; Employé pour son bulletin publié | SettlementController | settlement_detail / settlement_command ; tables settlement/corrections/recovery |
| Administration IAM / audit des rôles | /iam | Vue iam | Admin, Audit | IAMController | iam_overview ; accounts, roles, role_assignments |
