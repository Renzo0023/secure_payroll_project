# Tableau récapitulatif des rôles et permissions

Matrice prévue par les seeds ; état courant installé Non vérifié. Voir le chapitre 15 pour les restrictions et la matrice complète.

| Rôle canonique | Nom français | Permissions déclarées |
|---|---|---|
| employee | Employé | `payslip.self` |
| hr_manager | RH | `employees.read`, `employees.create`, `employees.update`, `departments.read`, `positions.read`, `assignments.read`, `assignments.create`, `assignments.close`, `contracts.read`, `contracts.create`, `contracts.close`, `compensation.read`, `compensation.submit`, `payroll.read`, `payroll.input.submit` |
| payroll_manager | Paie | `payroll.read`, `payroll.calculate`, `payslip.verify`, `payslip.publish`, `payslip.correct`, `payroll.recovery.request`, `payroll.recovery.receive` |
| finance_manager | Finance | `compensation.read`, `compensation.decide`, `payroll.read`, `payroll.period.create`, `payroll.input.decide`, `payslip.decide`, `payroll.payment`, `payroll.recovery.decide` |
| application_administrator | Admin | `iam.read`, `iam.grant`, `iam.revoke` |
| security_auditor | Audit | `payroll.read`, `iam.read` |
