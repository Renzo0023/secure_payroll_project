# 03 — Frontend et pages

> Périmètre : analyse des sources au 11 novembre 2026. Les attestations de tests sont datées ; aucune campagne fonctionnelle n’a été relancée. Installation MySQL actuelle : **Non vérifié**.

## Tableau récapitulatif des interfaces réellement routées

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

Le rôle associé à chaque permission est fixé dans le chapitre 15. Les droits RH correspondent à HR Manager ; compensation.read à RH/Finance ; payroll.read à RH/Paie/Finance/Audit ; payslip.self à Employee ; iam.read à Admin/Audit. L’accès à sa fiche et au tableau de bord est ouvert à tout compte authentifié actif, même sans rôle.

## Connexion — `/login`

**Objectif et affichage :** Formulaire ou 303 si connecté. Connexion ; afficher/masquer le mot de passe ; changement FR/EN.

**Accès :** Public. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/login.php](../../app/Views/login.php) ; [app/Web/Controller.php](../../app/Web/Controller.php) (`run`).

**Données et SQL :** Session. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** login (HTML 190 caractères ; PHP 760 octets), password (4096 octets maximum), csrf.

**Validations :** Tous obligatoires ; password_verify Argon2id ; cinq réservations échouées/IP/900 s.

**Interactions :** Connexion ; afficher/masquer le mot de passe ; changement FR/EN.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** Aucune inscription, récupération ni changement de mot de passe web.

## Tableau de bord — `/dashboard`

**Objectif et affichage :** 200 tableau de bord. Cartes des rôles actifs ; profil ; liens de module ; déconnexion et langue dans l’en-tête.

**Accès :** Authentifié. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/dashboard.php](../../app/Views/dashboard.php) ; [app/Web/Controller.php](../../app/Web/Controller.php) (`run`).

**Données et SQL :** Identité, rôles, permissions. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** Aucun formulaire métier.

**Validations :** Session relue ; liens conditionnés par can().

**Interactions :** Cartes des rôles actifs ; profil ; liens de module ; déconnexion et langue dans l’en-tête.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** Pas de statistiques financières agrégées ; certaines cartes de repli annoncent une capacité à venir.

## Annuaire — `/employees`

**Objectif et affichage :** 200 liste paginée. Recherche, précédent/suivant, ouvrir la fiche, créer selon droit.

**Accès :** employees.read. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/employees.php](../../app/Views/employees.php) ; [app/Web/Controller.php](../../app/Web/Controller.php) (`run / EmployeeRepository::listing`).

**Données et SQL :** employees. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** GET q, page.

**Validations :** q ≤ 400 octets sinon filtre vidé ; page entière 1–1 000 000 ; recherche LIKE littérale avec échappement de !/%/_.

**Interactions :** Recherche, précédent/suivant, ouvrir la fiche, créer selon droit.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** 20 lignes/page ; pas de suppression ni export.

## Création d’un employé — `/employees/new`

**Objectif et affichage :** Formulaire ; POST 303 ou 409/422. Enregistrer, annuler ; erreurs par champ ; matricule readonly en édition.

**Accès :** employees.create. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/employee-form.php](../../app/Views/employee-form.php) ; [app/Web/Controller.php](../../app/Web/Controller.php) (`run / EmployeeRepository::create`).

**Données et SQL :** employees. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** Création : employee_number, first_name, last_name ; modification : first_name, last_name et version cachée ; csrf.

**Validations :** Matricule 1–32 caractères Unicode, noms 1–100 ; trim, UTF-8 valide et caractères de contrôle refusés. Doublon : 409. Version HMAC et UPDATE conditionnel.

**Interactions :** Enregistrer, annuler ; erreurs par champ ; matricule readonly en édition.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** Matricule immuable ; archivage et compte non modifiables ici.

## Fiche employé / profil personnel — `/employees/{id}`

**Objectif et affichage :** 200 fiche ; 403/404. Identité, matricule, dates, état d’archivage ; liens modifier, contrats, affectations, salaire selon droits.

**Accès :** employees.read OU id = salarié connecté. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/employee.php](../../app/Views/employee.php) ; [app/Web/Controller.php](../../app/Web/Controller.php) (`run / EmployeeRepository::find`).

**Données et SQL :** employees. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** Aucun champ métier éditable.

**Validations :** Pour un non-RH, id doit être exactement user.employee_id.

**Interactions :** Identité, matricule, dates, état d’archivage ; liens modifier, contrats, affectations, salaire selon droits.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** Profil de consultation ; pas de changement du compte ni mot de passe.

## Modification d’identité — `/employees/{id}/edit`

**Objectif et affichage :** Formulaire ; POST 303 ou 409/422. Enregistrer, annuler ; erreurs par champ ; matricule readonly en édition.

**Accès :** employees.update. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/employee-form.php](../../app/Views/employee-form.php) ; [app/Web/Controller.php](../../app/Web/Controller.php) (`run / EmployeeRepository::update`).

**Données et SQL :** employees. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** Création : employee_number, first_name, last_name ; modification : first_name, last_name et version cachée ; csrf.

**Validations :** Matricule 1–32 caractères Unicode, noms 1–100 ; trim, UTF-8 valide et caractères de contrôle refusés. Doublon : 409. Version HMAC et UPDATE conditionnel.

**Interactions :** Enregistrer, annuler ; erreurs par champ ; matricule readonly en édition.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** Matricule immuable ; archivage et compte non modifiables ici.

## Départements — `/departments`

**Objectif et affichage :** 200 catalogue consultable. Code, libellé dans la langue choisie et état d’archivage.

**Accès :** departments.read. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/hr-catalogue.php](../../app/Views/hr-catalogue.php) ; [app/Web/AdvancedHRController.php](../../app/Web/AdvancedHRController.php) (`handle / catalogue`).

**Données et SQL :** departments. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** Aucun formulaire.

**Validations :** Rôle RH et permission departments.read ou positions.read.

**Interactions :** Code, libellé dans la langue choisie et état d’archivage.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** Consultation seulement ; aucun POST de création/modification de catalogue.

## Postes — `/positions`

**Objectif et affichage :** 200 catalogue consultable. Code, libellé dans la langue choisie et état d’archivage.

**Accès :** positions.read. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/hr-catalogue.php](../../app/Views/hr-catalogue.php) ; [app/Web/AdvancedHRController.php](../../app/Web/AdvancedHRController.php) (`handle / catalogue`).

**Données et SQL :** positions. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** Aucun formulaire.

**Validations :** Rôle RH et permission departments.read ou positions.read.

**Interactions :** Code, libellé dans la langue choisie et état d’archivage.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** Consultation seulement ; aucun POST de création/modification de catalogue.

## Liste des contracts — `/contracts`

**Objectif et affichage :** 200 historique paginé. Historique, état calculé courant/prévu/terminé ; ouvrir un détail, créer selon permission.

**Accès :** contracts.read. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/hr-period-list.php](../../app/Views/hr-period-list.php) ; [app/Web/AdvancedHRController.php](../../app/Web/AdvancedHRController.php) (`handle / listing`).

**Données et SQL :** employment_contracts, employees. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** GET page ; employee_id facultatif selon route.

**Validations :** Identifiant salarié positif ; existence vérifiée si filtre actif ; permission de lecture requise.

**Interactions :** Historique, état calculé courant/prévu/terminé ; ouvrir un détail, créer selon permission.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** 20 lignes/page ; une vue partagée pour contrats et affectations.

## Historique individuel des contracts — `/employees/{id}/contracts`

**Objectif et affichage :** 200 historique du salarié. Historique, état calculé courant/prévu/terminé ; ouvrir un détail, créer selon permission.

**Accès :** contracts.read. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/hr-period-list.php](../../app/Views/hr-period-list.php) ; [app/Web/AdvancedHRController.php](../../app/Web/AdvancedHRController.php) (`handle / listing`).

**Données et SQL :** employment_contracts, employees. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** GET page ; employee_id facultatif selon route.

**Validations :** Identifiant salarié positif ; existence vérifiée si filtre actif ; permission de lecture requise.

**Interactions :** Historique, état calculé courant/prévu/terminé ; ouvrir un détail, créer selon permission.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** 20 lignes/page ; une vue partagée pour contrats et affectations.

## Création contracts — `/contracts/new`

**Objectif et affichage :** Formulaire ; POST 303 ou erreur métier. Créer, annuler ; préremplissage depuis la fiche ; choix de catalogues traduits.

**Accès :** contracts.create. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/hr-period-form.php](../../app/Views/hr-period-form.php) ; [app/Web/AdvancedHRController.php](../../app/Web/AdvancedHRController.php) (`handle / create`).

**Données et SQL :** employment_contracts, employees, hr_create_contract. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** employee_number ; starts_on ; ends_on facultatif ; contrat : reference, contract_type ; affectation : department_id, position_id ; csrf.

**Validations :** Dates ISO réelles ≥ 1900 ; fin ≥ début ; permanent sans fin ; fixed_term/internship avec fin ; référence 1–64 ; salarié actif ; catalogues actifs ; absence de chevauchement SQL.

**Interactions :** Créer, annuler ; préremplissage depuis la fiche ; choix de catalogues traduits.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** Aucun salaire dans le contrat ; pas d’édition arbitraire d’une période enregistrée.

## Détail contracts — `/contracts/{id}`

**Objectif et affichage :** 200 détail. Afficher dates/auteurs et fin effective ; clôturer ; historique salarié et liste.

**Accès :** contracts.read. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/hr-period-detail.php](../../app/Views/hr-period-detail.php) ; [app/Web/AdvancedHRController.php](../../app/Web/AdvancedHRController.php) (`handle / find`).

**Données et SQL :** employment_contracts. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** closed_on et csrf si clôture autorisée.

**Validations :** Date entre starts_on et ends_on prévue si présente ; clôture unique ; garde SQL de couverture salariale pour contrat.

**Interactions :** Afficher dates/auteurs et fin effective ; clôturer ; historique salarié et liste.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** Clôture irréversible par ce workflow ; pas de suppression.

## Liste des assignments — `/assignments`

**Objectif et affichage :** 200 historique paginé. Historique, état calculé courant/prévu/terminé ; ouvrir un détail, créer selon permission.

**Accès :** assignments.read. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/hr-period-list.php](../../app/Views/hr-period-list.php) ; [app/Web/AdvancedHRController.php](../../app/Web/AdvancedHRController.php) (`handle / listing`).

**Données et SQL :** employee_assignments, employees. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** GET page ; employee_id facultatif selon route.

**Validations :** Identifiant salarié positif ; existence vérifiée si filtre actif ; permission de lecture requise.

**Interactions :** Historique, état calculé courant/prévu/terminé ; ouvrir un détail, créer selon permission.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** 20 lignes/page ; une vue partagée pour contrats et affectations.

## Historique individuel des assignments — `/employees/{id}/assignments`

**Objectif et affichage :** 200 historique du salarié. Historique, état calculé courant/prévu/terminé ; ouvrir un détail, créer selon permission.

**Accès :** assignments.read. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/hr-period-list.php](../../app/Views/hr-period-list.php) ; [app/Web/AdvancedHRController.php](../../app/Web/AdvancedHRController.php) (`handle / listing`).

**Données et SQL :** employee_assignments, employees. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** GET page ; employee_id facultatif selon route.

**Validations :** Identifiant salarié positif ; existence vérifiée si filtre actif ; permission de lecture requise.

**Interactions :** Historique, état calculé courant/prévu/terminé ; ouvrir un détail, créer selon permission.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** 20 lignes/page ; une vue partagée pour contrats et affectations.

## Création assignments — `/assignments/new`

**Objectif et affichage :** Formulaire ; POST 303 ou erreur métier. Créer, annuler ; préremplissage depuis la fiche ; choix de catalogues traduits.

**Accès :** assignments.create. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/hr-period-form.php](../../app/Views/hr-period-form.php) ; [app/Web/AdvancedHRController.php](../../app/Web/AdvancedHRController.php) (`handle / create`).

**Données et SQL :** employee_assignments, employees, departments, positions ; hr_create_assignment. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** employee_number ; starts_on ; ends_on facultatif ; contrat : reference, contract_type ; affectation : department_id, position_id ; csrf.

**Validations :** Dates ISO réelles ≥ 1900 ; fin ≥ début ; permanent sans fin ; fixed_term/internship avec fin ; référence 1–64 ; salarié actif ; catalogues actifs ; absence de chevauchement SQL.

**Interactions :** Créer, annuler ; préremplissage depuis la fiche ; choix de catalogues traduits.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** Aucun salaire dans le contrat ; pas d’édition arbitraire d’une période enregistrée.

## Détail assignments — `/assignments/{id}`

**Objectif et affichage :** 200 détail. Afficher dates/auteurs et fin effective ; clôturer ; historique salarié et liste.

**Accès :** assignments.read. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/hr-period-detail.php](../../app/Views/hr-period-detail.php) ; [app/Web/AdvancedHRController.php](../../app/Web/AdvancedHRController.php) (`handle / find`).

**Données et SQL :** employee_assignments. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** closed_on et csrf si clôture autorisée.

**Validations :** Date entre starts_on et ends_on prévue si présente ; clôture unique ; garde SQL de couverture salariale pour contrat.

**Interactions :** Afficher dates/auteurs et fin effective ; clôturer ; historique salarié et liste.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** Clôture irréversible par ce workflow ; pas de suppression.

## Demandes salariales — `/compensation`

**Objectif et affichage :** 200 liste paginée. Onglets demandes, sous contrat, attente, historique ; ouverture de détail et nouvelle proposition si droit.

**Accès :** compensation.read. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/compensation-list.php](../../app/Views/compensation-list.php) ; [app/Web/CompensationController.php](../../app/Web/CompensationController.php) (`handle`).

**Données et SQL :** compensation_requests, compensation_decisions, salary_conditions, employment_contracts, employees. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** GET page ; status pour /compensation ; employee_id pour /history.

**Validations :** Statut limité à vide/pending/approved/rejected ; page entière ; contrôle compensation.read.

**Interactions :** Onglets demandes, sous contrat, attente, historique ; ouverture de détail et nouvelle proposition si droit.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** 20 lignes/page ; employés sous contrat signifie lignes de contrats, pas nécessairement salariés distincts ; pas d’accès employee à cet historique global.

## Employés sous contrat — `/compensation/employees`

**Objectif et affichage :** 200 liste paginée. Onglets demandes, sous contrat, attente, historique ; ouverture de détail et nouvelle proposition si droit.

**Accès :** compensation.read. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/compensation-list.php](../../app/Views/compensation-list.php) ; [app/Web/CompensationController.php](../../app/Web/CompensationController.php) (`handle`).

**Données et SQL :** compensation_requests, compensation_decisions, salary_conditions, employment_contracts, employees. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** GET page ; status pour /compensation ; employee_id pour /history.

**Validations :** Statut limité à vide/pending/approved/rejected ; page entière ; contrôle compensation.read.

**Interactions :** Onglets demandes, sous contrat, attente, historique ; ouverture de détail et nouvelle proposition si droit.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** 20 lignes/page ; employés sous contrat signifie lignes de contrats, pas nécessairement salariés distincts ; pas d’accès employee à cet historique global.

## Approbations Finance en attente — `/compensation/pending`

**Objectif et affichage :** 200 liste paginée. Onglets demandes, sous contrat, attente, historique ; ouverture de détail et nouvelle proposition si droit.

**Accès :** compensation.read. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/compensation-list.php](../../app/Views/compensation-list.php) ; [app/Web/CompensationController.php](../../app/Web/CompensationController.php) (`handle`).

**Données et SQL :** compensation_requests, compensation_decisions, salary_conditions, employment_contracts, employees. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** GET page ; status pour /compensation ; employee_id pour /history.

**Validations :** Statut limité à vide/pending/approved/rejected ; page entière ; contrôle compensation.read.

**Interactions :** Onglets demandes, sous contrat, attente, historique ; ouverture de détail et nouvelle proposition si droit.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** 20 lignes/page ; employés sous contrat signifie lignes de contrats, pas nécessairement salariés distincts ; pas d’accès employee à cet historique global.

## Historique des conditions salariales — `/compensation/history`

**Objectif et affichage :** 200 liste paginée. Onglets demandes, sous contrat, attente, historique ; ouverture de détail et nouvelle proposition si droit.

**Accès :** compensation.read. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/compensation-list.php](../../app/Views/compensation-list.php) ; [app/Web/CompensationController.php](../../app/Web/CompensationController.php) (`handle`).

**Données et SQL :** compensation_requests, compensation_decisions, salary_conditions, employment_contracts, employees. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** GET page ; status pour /compensation ; employee_id pour /history.

**Validations :** Statut limité à vide/pending/approved/rejected ; page entière ; contrôle compensation.read.

**Interactions :** Onglets demandes, sous contrat, attente, historique ; ouverture de détail et nouvelle proposition si droit.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** 20 lignes/page ; employés sous contrat signifie lignes de contrats, pas nécessairement salariés distincts ; pas d’accès employee à cet historique global.

## Proposition salariale — `/compensation/new`

**Objectif et affichage :** Formulaire ; POST 303 ou 409/422/503. Soumettre ou annuler ; erreurs traduites ; informations de règle de date.

**Accès :** compensation.read ET compensation.submit. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/compensation-form.php](../../app/Views/compensation-form.php) ; [app/Web/CompensationController.php](../../app/Web/CompensationController.php) (`handle / submit`).

**Données et SQL :** compensation_submit ; compensation_requests, compensation_history. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** employee_number, reference, monthly_amount, effective_on, justification, csrf.

**Validations :** Montant positif : 1–10 chiffres entiers, 1–2 décimales facultatives, virgule/point admis ; justification Unicode 1–2000 ; dates valides ; couple contrat/salarié réel ; schéma devise prêt.

**Interactions :** Soumettre ou annuler ; erreurs traduites ; informations de règle de date.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** Initiale à la date de début du contrat ; révision au premier jour d’un mois et après la dernière version ; UM bloque les nouvelles décisions favorables.

## Détail de demande salariale — `/compensation/{id}`

**Objectif et affichage :** 200 détail, décision et événements. Demande, montant, contrat, identité des acteurs, décision et événements ; approuver/rejeter si autorisé.

**Accès :** compensation.read. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/compensation-detail.php](../../app/Views/compensation-detail.php) ; [app/Web/CompensationController.php](../../app/Web/CompensationController.php) (`handle / find / events`).

**Données et SQL :** compensation_requests, compensation_decisions, compensation_history, employees, employment_contracts. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** decision=approved/rejected, reason 1–2000, csrf selon Finance.

**Validations :** Décideur distinct du demandeur et bénéficiaire au niveau employee_id ; décision unique ; nouvelle vérification des sources SQL.

**Interactions :** Demande, montant, contrat, identité des acteurs, décision et événements ; approuver/rejeter si autorisé.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** Une demande décidée ne se réécrit pas ; un rejet est conservé.

## Paie / espace employé — `/payroll`

**Objectif et affichage :** 200 espace Paie ou bulletins personnels. Créer période, proposer prime/retenue/suspension, décider, calculer, consulter bulletin ; listes de mois et de calculs ; pagination.

**Accès :** payroll.read OU payslip.self. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/payroll.php](../../app/Views/payroll.php) ; [app/Web/PayrollController.php](../../app/Web/PayrollController.php) (`handle / overview`).

**Données et SQL :** payroll_overview. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** Finance : month, bonus_cap, deduction_cap, reason ; RH : period_id, employee_id, kind, amount, starts_on, ends_on, reason ; Paie : period_id, employee_id ; Finance décision : decision, reason ; csrf dans chaque POST.

**Validations :** Mois ISO valide ; plafonds ≥ 0 explicites ; identifiants positifs ; kind bonus/deduction/paid_leave/unpaid_leave ; montant positif pour argent et zéro pour suspension ; bornes inclusives dans le mois ; motif 1–2000.

**Interactions :** Créer période, proposer prime/retenue/suspension, décider, calculer, consulter bulletin ; listes de mois et de calculs ; pagination.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** Employee ne reçoit ni mois de sélection ni autres salariés ni ajustements ; seulement ses bulletins publiés. 120 mois, 500 salariés de sélection et 50 entrées/calculs par page côté SQL.

## Bulletin de salaire — `/payslips/{id}`

**Objectif et affichage :** 200 bulletin ; 404 inaccessible. Base/primes/retenues/brut/net, mois/version, calendrier journalier, événements et versions ; vérifier, approuver/rejeter, publier ; ouvrir règlement si publié et activé.

**Accès :** payroll.read OU payslip.self + propriété/publication SQL. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/payslip.php](../../app/Views/payslip.php) ; [app/Web/PayrollController.php](../../app/Web/PayrollController.php) (`handle / detail`).

**Données et SQL :** payslip_detail. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** event=verified/approved/rejected/published, reason et csrf selon état/droit.

**Validations :** État requis, bénéficiaire exclu, Finance distinct du préparateur, version courante et recalcul de fraîcheur avant vérification/approbation.

**Interactions :** Base/primes/retenues/brut/net, mois/version, calendrier journalier, événements et versions ; vérifier, approuver/rejeter, publier ; ouvrir règlement si publié et activé.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** Bulletin HTML ; aucune route PDF de bulletin ; un salarié ne voit que ses versions publiées.

## Règlements, corrections et remboursements — `/payslips/{id}/settlement`

**Objectif et affichage :** SETTLEMENT_ENABLED=1 ; 200/303 ou erreur. Solde, net effectif, corrections et événements, registre financier, demandes/reçus ; boutons conditionnés par état, propriété et droits.

**Accès :** GET payroll.read OU payslip.self ; POST permission selon action. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/settlement.php](../../app/Views/settlement.php) ; [app/Web/SettlementController.php](../../app/Web/SettlementController.php) (`handle / settlement ou settle`).

**Données et SQL :** settlement_detail / settlement_command ; tables settlement/corrections/recovery. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** action, expected, target, reason ; correct : base, bonus, deduction ; pay/recover_receive : reference ; csrf.

**Validations :** expected=0 pour bulletin initial ; target=0 admis sans objet ciblé ; référence [A-Za-z0-9_-]{8,64} ; montants validés pour correction uniquement ; SQL calcule montant payable/remboursable.

**Interactions :** Solde, net effectif, corrections et événements, registre financier, demandes/reçus ; boutons conditionnés par état, propriété et droits.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** SETTLEMENT_ENABLED=1 requis ; simulation intégrale du solde, aucun virement ni paiement partiel choisi librement ; aucune correction de Nadia attestée sur la principale.

## Administration IAM / audit des rôles — `/iam`

**Objectif et affichage :** IAM_ENABLED=1 ; 200 ou 404/403. Choisir compte/rôle et octroyer ; historique avec motifs, dates/auteurs ; révoquer une attribution non déjà révoquée.

**Accès :** iam.read. Les contrôles serveur précèdent le rendu ; masquer un lien ne suffit pas à autoriser une action.

**Vue / contrôleur :** [app/Views/iam.php](../../app/Views/iam.php) ; [app/Web/IAMController.php](../../app/Web/IAMController.php) (`handle / overview`).

**Données et SQL :** iam_overview ; accounts, roles, role_assignments. Les appels SQL exacts et leurs contrôles figurent au chapitre 06.

**Champs :** Octroi : account, role, reason ; révocation : reason ; csrf ; GET page.

**Validations :** Rôle dans les six codes canoniques ; compte actif d’une autre personne ; motif 1–255 ; pas de doublon ni cumul opérationnel, y compris attribution future conflictuelle.

**Interactions :** Choisir compte/rôle et octroyer ; historique avec motifs, dates/auteurs ; révoquer une attribution non déjà révoquée.

**Sécurité :** session pour les pages privées, autorisation serveur, échappement `h()` des valeurs dynamiques et CSRF pour chaque POST ; contrôle SQL supplémentaire pour les commandes historisées.

**Limites :** IAM_ENABLED=1 ; 500 comptes au maximum dans la sélection, 50 attributions/page ; pas de création de comptes, programmation ni expiration personnalisée dans le formulaire.

## Composants partagés et erreurs

`header.php` fournit sidebar, navigation conditionnelle, fil d’Ariane, avatar textuel, rôles, sélection de langue et déconnexion POST. `footer.php` ferme le contenu et affiche le pied de page. `language-switch.php` construit le formulaire FR/EN avec csrf et return_to ; `compensation-nav.php` expose les onglets ; `payroll-select.php` réutilise les sélecteurs de salarié et de période. Ces fichiers ne sont pas des pages routées séparément.

`error.php` est utilisé pour 403/404/405/409/422/503 selon la branche. Les erreurs métier sont traduites ; les exceptions SQL inconnues deviennent une indisponibilité générique. Les succès transitent par une clé flash en session, consommée à la requête suivante. Le bootstrap peut produire une réponse texte 500 hors traitement normal. Aucun écran de trace SQL n’est exposé.

## Design et ergonomie

`public/assets/app.css` définit vert principal #17634f, vert profond #103e34, menthe #e9f3ed, fond #f5f7f4, encre #192e2c, gris #6e7d79 et bordures #e3e9e5. Les messages d’erreur emploient des tons rouges, les confirmations des verts, les attentes des jaunes. Les composants comprennent cartes arrondies, badges, tableaux défilants, grilles de formulaires et boutons primary/secondary. La connexion est organisée en panneau de présentation et panneau de saisie.

La pile typographique est Inter, ui-sans-serif, system-ui puis polices système ; taille de base 14 px. La navigation latérale fixe mesure 245 px, puis 220 px à un seuil intermédiaire. Des media queries à 1500, 1100, 760, 700 et 480 px adaptent espacements, grilles, navigation, compte et tableaux. Sous 760 px, le menu latéral devient escamotable, les formulaires passent à une colonne et le bouton menu l’ouvre. Les tableaux disposent d’un défilement horizontal. Ces comportements sont constatés dans le CSS ; aucune nouvelle recette visuelle multi-écrans n’a été exécutée.

Les formulaires utilisent labels, required, maxlength, types date/month, inputmode decimal, messages par champ et aria-invalid/aria-describedby selon vue. `app.js` personnalise seulement les champs manquants pour les formulaires marqués, permet d’afficher le mot de passe et ouvre/ferme le menu (Échap compris). Il n’effectue aucun calcul financier ni appel réseau AJAX. Les attributs ARIA et prefers-reduced-motion améliorent l’usage ; la conformité WCAG exhaustive reste Non vérifié.

## Bilinguisme et protections côté navigateur

`Translator::locale` accepte uniquement fr/en, français par défaut. `Translator::text` cherche une clé dans la langue puis dans le français et enfin `common.unavailable`. Les paramètres sont remplacés par strtr, puis les vues les échappent. La langue est stockée en session ; `/language` n’est pas un GET, contrôle CSRF et liste blanche du chemin de retour. Les dates techniques restent UTC. Money produit par exemple « 12 000,00 MAD » en français et « 12,000.00 MAD » en anglais, sans conversion monétaire.

La CSP refuse par défaut toutes les sources puis autorise CSS/JS/images/formulaires de même origine ; elle interdit frames et base URI. `h()` utilise ENT_QUOTES | ENT_SUBSTITUTE en UTF-8. Le JavaScript local passe par textContent pour le bouton du mot de passe. Les formulaires natifs ne remplacent pas les validations PHP et SQL. Source : `public/index.php`, `helpers.php`, `Translator.php`, `Money.php`, CSS/JS et vues citées.
