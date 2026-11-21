# Tableau récapitulatif des tables

> Analyse documentaire du 11 novembre 2026. Le code est la référence de l’implémentation ; les résultats historiques ne sont pas une nouvelle exécution. Aucune migration, donnée métier, attribution, permission ou fonctionnalité n’a été modifiée pendant cette mission. État actuel de MySQL : **Non vérifié** (absence de variables de connexion dans cette session).

| Table | Objectif | Colonnes | Source |
|---|---|---:|---|
| employees | Identité stable des salariés ; matricule permanent, noms et archivage logique. | 6 | [database/migrations/001_create_identity_and_rbac.sql](../../database/migrations/001_create_identity_and_rbac.sql) |
| accounts | Compte de connexion rattaché à un salarié ; identifiant, empreinte Argon2id et désactivation. | 6 | [database/migrations/001_create_identity_and_rbac.sql](../../database/migrations/001_create_identity_and_rbac.sql) |
| roles | Catalogue fermé des six rôles applicatifs canoniques. | 3 | [database/migrations/001_create_identity_and_rbac.sql](../../database/migrations/001_create_identity_and_rbac.sql) |
| permissions | Catalogue des capacités métier nommées. | 3 | [database/migrations/001_create_identity_and_rbac.sql](../../database/migrations/001_create_identity_and_rbac.sql) |
| role_permissions | Association N:N entre rôles et permissions. | 2 | [database/migrations/001_create_identity_and_rbac.sql](../../database/migrations/001_create_identity_and_rbac.sql) |
| role_assignments | Attributions temporelles des rôles aux comptes, octroi et révocation traçables. | 11 | [database/migrations/001_create_identity_and_rbac.sql](../../database/migrations/001_create_identity_and_rbac.sql) |
| departments | Catalogue bilingue des départements ; archivage logique. | 5 | [database/migrations/002_advanced_hr.sql](../../database/migrations/002_advanced_hr.sql) |
| positions | Catalogue bilingue des métiers réutilisables entre départements. | 5 | [database/migrations/002_advanced_hr.sql](../../database/migrations/002_advanced_hr.sql) |
| employee_assignments | Périodes datées d’affectation d’un employé à un département et un poste. | 12 | [database/migrations/002_advanced_hr.sql](../../database/migrations/002_advanced_hr.sql) |
| employment_contracts | Contrats administratifs datés ; aucun salaire dans cette table. | 12 | [database/migrations/002_advanced_hr.sql](../../database/migrations/002_advanced_hr.sql) |
| compensation_requests | Propositions initiales ou révisions salariales RH, conservées sans modification. | 11 | [database/migrations/004_compensation.sql](../../database/migrations/004_compensation.sql) |
| compensation_decisions | Décision Finance unique pour chaque demande salariale. | 7 | [database/migrations/004_compensation.sql](../../database/migrations/004_compensation.sql) |
| salary_conditions | Versions des salaires approuvés, liées à la demande et à la décision. | 9 | [database/migrations/004_compensation.sql](../../database/migrations/004_compensation.sql) |
| compensation_history | Événements submitted/approved/rejected des demandes salariales. | 5 | [database/migrations/004_compensation.sql](../../database/migrations/004_compensation.sql) |
| payroll_periods | Mois de paie et plafonds absolus de primes/retenues explicités par Finance. | 8 | [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql) |
| payroll_inputs | Primes, retenues et suspensions payées ou non payées proposées par RH. | 11 | [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql) |
| payroll_input_decisions | Décision Finance unique sur chaque élément de paie. | 7 | [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql) |
| payroll_calculations | Versions immuables de calcul, montants et instantané JSON des sources. | 16 | [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql) |
| payslip_events | Transitions motivées de vérification, décision et publication du bulletin. | 7 | [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql) |
| payroll_approvals | Ancrage de l’unique calcul approuvé pour un salarié et un mois. | 3 | [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql) |
| payslip_corrections | Versions exceptionnelles de remplacement des montants d’un bulletin publié. | 14 | [database/migrations/009_settlement.sql](../../database/migrations/009_settlement.sql) |
| correction_events | Vérification, décision et publication des corrections. | 7 | [database/migrations/009_settlement.sql](../../database/migrations/009_settlement.sql) |
| recovery_requests | Demandes de restitution d’un trop-perçu fictif. | 8 | [database/migrations/009_settlement.sql](../../database/migrations/009_settlement.sql) |
| recovery_events | Approbation, rejet et réception des restitutions. | 7 | [database/migrations/009_settlement.sql](../../database/migrations/009_settlement.sql) |
| settlement_ledger | Écritures immuables des paiements et remboursements fictifs avec référence unique. | 12 | [database/migrations/009_settlement.sql](../../database/migrations/009_settlement.sql) |
