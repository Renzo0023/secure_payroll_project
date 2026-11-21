# 14 — Inventaire des routes HTTP

> Analyse documentaire du 11 novembre 2026. Le code est la référence de l’implémentation ; les résultats historiques ne sont pas une nouvelle exécution. Aucune migration, donnée métier, attribution, permission ou fonctionnalité n’a été modifiée pendant cette mission. État actuel de MySQL : **Non vérifié** (absence de variables de connexion dans cette session).

Les paramètres `{id}` désignent un entier positif de 1 à 18 chiffres dans le routeur. Ils ne constituent jamais une autorisation. Toutes les écritures passent par POST et CSRF. Aucun endpoint JSON/API REST distinct n’est défini.

| Méthode | Route | Contrôleur | Action | Permission requise | Résultat | Données |
|---|---|---|---|---|---|---|
| GET | / | Controller | run | Public | 303 vers /login ou /dashboard | Session |
| GET | /login | Controller | run | Public | Formulaire ou 303 si connecté | Session |
| POST | /login | Controller | run / AuthService::login | CSRF ; compte actif | 303 succès ; 401 refus ; 429 limite ; 503 indisponibilité | accounts, employees |
| POST | /logout | Controller | run / Session::clear | CSRF | 303 /login | Session, journal |
| POST | /language | Controller | run | Public + CSRF | 303 vers chemin autorisé ; 422 langue invalide | Session, lang/fr.php, lang/en.php |
| GET | /dashboard | Controller | run | Authentifié | 200 tableau de bord | Identité, rôles, permissions |
| GET | /employees | Controller | run / EmployeeRepository::listing | employees.read | 200 liste paginée | employees |
| GET | /employees/new | Controller | run / EmployeeRepository::create | employees.create | Formulaire ; POST 303 ou 409/422 | employees |
| POST | /employees/new | Controller | run / EmployeeRepository::create | employees.create | Formulaire ; POST 303 ou 409/422 | employees |
| GET | /employees/{id} | Controller | run / EmployeeRepository::find | employees.read OU id = salarié connecté | 200 fiche ; 403/404 | employees |
| GET | /employees/{id}/edit | Controller | run / EmployeeRepository::update | employees.update | Formulaire ; POST 303 ou 409/422 | employees |
| POST | /employees/{id}/edit | Controller | run / EmployeeRepository::update | employees.update | Formulaire ; POST 303 ou 409/422 | employees |
| GET | /departments | AdvancedHRController | handle / catalogue | departments.read | 200 catalogue consultable | departments |
| GET | /positions | AdvancedHRController | handle / catalogue | positions.read | 200 catalogue consultable | positions |
| GET | /contracts | AdvancedHRController | handle / listing | contracts.read | 200 historique paginé | employment_contracts, employees |
| GET | /employees/{id}/contracts | AdvancedHRController | handle / listing | contracts.read | 200 historique du salarié | employment_contracts, employees |
| GET | /contracts/new | AdvancedHRController | handle / create | contracts.create | Formulaire ; POST 303 ou erreur métier | employment_contracts, employees, hr_create_contract |
| POST | /contracts/new | AdvancedHRController | handle / create | contracts.create | Formulaire ; POST 303 ou erreur métier | employment_contracts, employees, hr_create_contract |
| GET | /contracts/{id} | AdvancedHRController | handle / find | contracts.read | 200 détail | employment_contracts |
| POST | /contracts/{id}/close | AdvancedHRController | handle / close | contracts.close ET contracts.read | 303 ou 409/422 | employment_contracts ; hr_close_contract |
| GET | /assignments | AdvancedHRController | handle / listing | assignments.read | 200 historique paginé | employee_assignments, employees |
| GET | /employees/{id}/assignments | AdvancedHRController | handle / listing | assignments.read | 200 historique du salarié | employee_assignments, employees |
| GET | /assignments/new | AdvancedHRController | handle / create | assignments.create | Formulaire ; POST 303 ou erreur métier | employee_assignments, employees, departments, positions ; hr_create_assignment |
| POST | /assignments/new | AdvancedHRController | handle / create | assignments.create | Formulaire ; POST 303 ou erreur métier | employee_assignments, employees, departments, positions ; hr_create_assignment |
| GET | /assignments/{id} | AdvancedHRController | handle / find | assignments.read | 200 détail | employee_assignments |
| POST | /assignments/{id}/close | AdvancedHRController | handle / close | assignments.close ET assignments.read | 303 ou 409/422 | employee_assignments ; hr_close_assignment |
| GET | /compensation | CompensationController | handle | compensation.read | 200 liste paginée | compensation_requests, compensation_decisions, salary_conditions, employment_contracts, employees |
| GET | /compensation/employees | CompensationController | handle | compensation.read | 200 liste paginée | compensation_requests, compensation_decisions, salary_conditions, employment_contracts, employees |
| GET | /compensation/pending | CompensationController | handle | compensation.read | 200 liste paginée | compensation_requests, compensation_decisions, salary_conditions, employment_contracts, employees |
| GET | /compensation/history | CompensationController | handle | compensation.read | 200 liste paginée | compensation_requests, compensation_decisions, salary_conditions, employment_contracts, employees |
| GET | /compensation/new | CompensationController | handle / submit | compensation.read ET compensation.submit | Formulaire ; POST 303 ou 409/422/503 | compensation_submit ; compensation_requests, compensation_history |
| POST | /compensation/new | CompensationController | handle / submit | compensation.read ET compensation.submit | Formulaire ; POST 303 ou 409/422/503 | compensation_submit ; compensation_requests, compensation_history |
| GET | /compensation/{id} | CompensationController | handle / find / events | compensation.read | 200 détail, décision et événements | compensation_requests, compensation_decisions, compensation_history, employees, employment_contracts |
| POST | /compensation/{id}/decision | CompensationController | handle / decide | compensation.read ET compensation.decide ; indépendance | 303 ou 403/409/422 | compensation_decide ; compensation_decisions, salary_conditions, compensation_history |
| GET | /payroll | PayrollController | handle / overview | payroll.read OU payslip.self | 200 espace Paie ou bulletins personnels | payroll_overview |
| POST | /payroll/periods | PayrollController | handle / createPeriod | payroll.period.create | 303 ou 403/409/422/503 | Repository::createPeriod ; procédures payroll_* |
| POST | /payroll/inputs | PayrollController | handle / submitInput | payroll.input.submit | 303 ou 403/409/422/503 | Repository::submitInput ; procédures payroll_* |
| POST | /payroll/inputs/{id}/decision | PayrollController | handle / decideInput | payroll.input.decide | 303 ou 403/409/422/503 | Repository::decideInput ; procédures payroll_* |
| POST | /payroll/calculate | PayrollController | handle / calculate | payroll.calculate | 303 ou 403/409/422/503 | Repository::calculate ; procédures payroll_* |
| GET | /payslips/{id} | PayrollController | handle / detail | payroll.read OU payslip.self + propriété/publication SQL | 200 bulletin ; 404 inaccessible | payslip_detail |
| POST | /payslips/{id}/transition | PayrollController | handle / transition | payslip.verify / payslip.decide / payslip.publish selon event | 303 ou erreur métier | payslip_transition ; payslip_events, payroll_approvals |
| GET | /payslips/{id}/settlement | SettlementController | handle / settlement ou settle | GET payroll.read OU payslip.self ; POST permission selon action | SETTLEMENT_ENABLED=1 ; 200/303 ou erreur | settlement_detail / settlement_command ; tables settlement/corrections/recovery |
| POST | /payslips/{id}/settlement | SettlementController | handle / settlement ou settle | GET payroll.read OU payslip.self ; POST permission selon action | SETTLEMENT_ENABLED=1 ; 200/303 ou erreur | settlement_detail / settlement_command ; tables settlement/corrections/recovery |
| GET | /iam | IAMController | handle / overview | iam.read | IAM_ENABLED=1 ; 200 ou 404/403 | iam_overview ; accounts, roles, role_assignments |
| POST | /iam/grant | IAMController | handle / grant | iam.grant | IAM_ENABLED=1 ; 303 ou erreur | iam_grant ; role_assignments |
| POST | /iam/{id}/revoke | IAMController | handle / revoke | iam.revoke | IAM_ENABLED=1 ; 303 ou erreur | iam_revoke ; role_assignments |
| GET, HEAD | /assets/app.css ; /assets/app.js | public/index.php | Liste blanche | Public | 200 ressource ; autre méthode 405 | Fichiers assets |

## Ordre et erreurs

`Controller::run` vérifie route connue, méthode autorisée puis CSRF avant l’authentification des pages privées. Une route inconnue retourne 404 ; une méthode non admise retourne 405 avec Allow ; un CSRF absent/invalide retourne 403. `/` et les succès POST redirigent en 303. Sans session, les pages privées redirigent vers `/login`. L’indisponibilité générale est transformée en 503 ; le gestionnaire global du bootstrap produit 500 pour une exception hors traitement.

Sources : [app/Web/Controller.php](../../app/Web/Controller.php), [app/Web/AdvancedHRController.php](../../app/Web/AdvancedHRController.php), [app/Web/CompensationController.php](../../app/Web/CompensationController.php), [app/Web/PayrollController.php](../../app/Web/PayrollController.php), [app/Web/SettlementController.php](../../app/Web/SettlementController.php), [app/Web/IAMController.php](../../app/Web/IAMController.php).
