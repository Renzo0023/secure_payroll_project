# 15 — Inventaire des rôles et permissions

> Analyse documentaire du 11 novembre 2026. Le code est la référence de l’implémentation ; les résultats historiques ne sont pas une nouvelle exécution. Aucune migration, donnée métier, attribution, permission ou fonctionnalité n’a été modifiée pendant cette mission. État actuel de MySQL : **Non vérifié** (absence de variables de connexion dans cette session).

Le catalogue contient **31 permissions déclarées** et six rôles. La matrice ci-dessous traduit les seeds 002, 003, 005, 006, 007 et 008 ; elle ne certifie pas les attributions actuellement installées. « Oui » suppose également un compte/salarié actif, une attribution temporellement valide et les contrôles complémentaires d’AuthService::can et des procédures.

| Permission | Employee | HR Manager | Payroll Manager | Finance Manager | Application Administrator | Security Auditor | Description déclarée | Source |
|---|---|---|---|---|---|---|---|---|
| employees.read | — | Oui | — | — | — | — | Consulter les fiches des employés | [database/seeds/002_hr_permissions.sql](../../database/seeds/002_hr_permissions.sql) |
| employees.create | — | Oui | — | — | — | — | Créer une fiche employé | [database/seeds/002_hr_permissions.sql](../../database/seeds/002_hr_permissions.sql) |
| employees.update | — | Oui | — | — | — | — | Modifier le prénom et le nom d’un employé | [database/seeds/002_hr_permissions.sql](../../database/seeds/002_hr_permissions.sql) |
| departments.read | — | Oui | — | — | — | — | Consulter les départements | [database/seeds/003_advanced_hr_permissions.sql](../../database/seeds/003_advanced_hr_permissions.sql) |
| positions.read | — | Oui | — | — | — | — | Consulter les postes | [database/seeds/003_advanced_hr_permissions.sql](../../database/seeds/003_advanced_hr_permissions.sql) |
| assignments.read | — | Oui | — | — | — | — | Consulter les affectations | [database/seeds/003_advanced_hr_permissions.sql](../../database/seeds/003_advanced_hr_permissions.sql) |
| assignments.create | — | Oui | — | — | — | — | Enregistrer une affectation | [database/seeds/003_advanced_hr_permissions.sql](../../database/seeds/003_advanced_hr_permissions.sql) |
| assignments.close | — | Oui | — | — | — | — | Clôturer une affectation sans supprimer son historique | [database/seeds/003_advanced_hr_permissions.sql](../../database/seeds/003_advanced_hr_permissions.sql) |
| contracts.read | — | Oui | — | — | — | — | Consulter les contrats administratifs sans rémunération | [database/seeds/003_advanced_hr_permissions.sql](../../database/seeds/003_advanced_hr_permissions.sql) |
| contracts.create | — | Oui | — | — | — | — | Créer un contrat administratif sans rémunération | [database/seeds/003_advanced_hr_permissions.sql](../../database/seeds/003_advanced_hr_permissions.sql) |
| contracts.close | — | Oui | — | — | — | — | Clôturer un contrat administratif | [database/seeds/003_advanced_hr_permissions.sql](../../database/seeds/003_advanced_hr_permissions.sql) |
| compensation.read | — | Oui | — | Oui | — | — | Consulter les demandes et historiques salariaux | [database/seeds/005_compensation_permissions.sql](../../database/seeds/005_compensation_permissions.sql) |
| compensation.submit | — | Oui | — | — | — | — | Soumettre une demande salariale RH | [database/seeds/005_compensation_permissions.sql](../../database/seeds/005_compensation_permissions.sql) |
| compensation.decide | — | — | — | Oui | — | — | Approuver ou rejeter une demande salariale Finance | [database/seeds/005_compensation_permissions.sql](../../database/seeds/005_compensation_permissions.sql) |
| payroll.read | — | Oui | Oui | Oui | — | Oui | Read payroll data | [database/seeds/006_payroll_permissions.sql](../../database/seeds/006_payroll_permissions.sql) |
| payroll.period.create | — | — | — | Oui | — | — | Create payroll periods with explicit caps | [database/seeds/006_payroll_permissions.sql](../../database/seeds/006_payroll_permissions.sql) |
| payroll.input.submit | — | Oui | — | — | — | — | Submit payroll adjustments and suspensions | [database/seeds/006_payroll_permissions.sql](../../database/seeds/006_payroll_permissions.sql) |
| payroll.input.decide | — | — | — | Oui | — | — | Independently decide payroll inputs | [database/seeds/006_payroll_permissions.sql](../../database/seeds/006_payroll_permissions.sql) |
| payroll.calculate | — | — | Oui | — | — | — | Prepare immutable payroll versions | [database/seeds/006_payroll_permissions.sql](../../database/seeds/006_payroll_permissions.sql) |
| payslip.verify | — | — | Oui | — | — | — | Verify current payroll amounts | [database/seeds/006_payroll_permissions.sql](../../database/seeds/006_payroll_permissions.sql) |
| payslip.decide | — | — | — | Oui | — | — | Independently approve or reject payslips | [database/seeds/006_payroll_permissions.sql](../../database/seeds/006_payroll_permissions.sql) |
| payslip.publish | — | — | Oui | — | — | — | Publish approved payslips | [database/seeds/006_payroll_permissions.sql](../../database/seeds/006_payroll_permissions.sql) |
| payslip.self | Oui | — | — | — | — | — | Read own published payslips | [database/seeds/006_payroll_permissions.sql](../../database/seeds/006_payroll_permissions.sql) |
| payslip.correct | — | — | Oui | — | — | — | Prepare reasoned immutable correction versions | [database/seeds/007_settlement_permissions.sql](../../database/seeds/007_settlement_permissions.sql) |
| payroll.payment | — | — | — | Oui | — | — | Record fictional payment of the outstanding published balance | [database/seeds/007_settlement_permissions.sql](../../database/seeds/007_settlement_permissions.sql) |
| payroll.recovery.request | — | — | Oui | — | — | — | Request controlled fictional overpayment recovery | [database/seeds/007_settlement_permissions.sql](../../database/seeds/007_settlement_permissions.sql) |
| payroll.recovery.decide | — | — | — | Oui | — | — | Independently decide overpayment recovery | [database/seeds/007_settlement_permissions.sql](../../database/seeds/007_settlement_permissions.sql) |
| payroll.recovery.receive | — | — | Oui | — | — | — | Record fictional receipt after independent approval | [database/seeds/007_settlement_permissions.sql](../../database/seeds/007_settlement_permissions.sql) |
| iam.read | — | — | — | — | Oui | Oui | Read role assignment audit without credentials | [database/seeds/008_iam_permissions.sql](../../database/seeds/008_iam_permissions.sql) |
| iam.grant | — | — | — | — | Oui | — | Grant roles to other active employees with separation of duties | [database/seeds/008_iam_permissions.sql](../../database/seeds/008_iam_permissions.sql) |
| iam.revoke | — | — | — | — | Oui | — | Revoke another employee role preserving history | [database/seeds/008_iam_permissions.sql](../../database/seeds/008_iam_permissions.sql) |

## Sémantique des six rôles

- `employee` : fiche personnelle accessible par identité ; `payslip.self` permet les bulletins personnels publiés et leur règlement consultable. La fiche personnelle ne requiert pas de permission nommée distincte.
- `hr_manager` : identité des employés, consultation des catalogues, contrats et affectations, propositions salariales et éléments de paie.
- `payroll_manager` : préparation, vérification, publication, corrections motivées et gestion opérationnelle des restitutions.
- `finance_manager` : décisions salariales et de paie, création des mois/plafonds, paiements fictifs et décision de remboursement.
- `application_administrator` : consultation, attribution et révocation IAM ; aucun droit financier implicite.
- `security_auditor` : lecture de la paie et de l’historique IAM ; aucune écriture financière ou IAM.

Le rôle employee peut coexister avec un rôle opérationnel unique. Les cinq autres rôles sont mutuellement incompatibles dans les nouveaux octrois `iam_grant`. Les contrôles de paie/IAM refusent également les cumuls opérationnels déjà présents. Pour la rémunération, le contrôle de conflit historique vise RH/Finance. Le contrôle RH simple exige le rôle RH et la permission sans appliquer cette matrice globale.

L’auto-attribution et l’auto-révocation sont refusées au niveau de la personne SQL. L’interface n’expose ni création de permissions ni édition de la matrice rôle-permission. Source : `AuthService::can`, `iam_grant`, `iam_revoke`, migrations 001/008/011.
