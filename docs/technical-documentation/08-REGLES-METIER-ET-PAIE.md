# 08 — Règles métier et traitement de la paie

> Sources analysées au 11 novembre 2026 ; aucune attaque, écriture MySQL ou nouvelle recette fonctionnelle n’a été exécutée pendant cette mission.

## Identité et cycle de vie salarié

Le matricule identifie durablement un employé ; la création renseigne matricule, prénom et nom. L’édition web ne modifie que les deux noms. L’archivage est modélisé dans employees.archived_at et bloque l’authentification ainsi que plusieurs opérations métier, mais aucune route web d’archivage n’est exposée. La suppression est interdite par trigger. Un salarié peut exister sans compte ; la création RH ne crée pas automatiquement son accès web.

Les affectations fixent département et poste sur une période inclusive. Les contrats fixent référence, type et période, sans rémunération. permanent est sans ends_on ; fixed_term/internship imposent une fin. Les sources initiales sont immuables ; une clôture ajoute closed_on/closed_at/closed_by. effective_ends_on=COALESCE(closed_on,ends_on). Les périodes d’une même catégorie ne se chevauchent pas pour un salarié ; deux périodes adjacentes doivent donc commencer le lendemain de la fin inclusive.

## Tableau de traçabilité des règles

| Règle | PHP qui la porte / la relaie | SQL / contrainte | Erreurs et sécurité |
|---|---|---|---|
| Matricule stable et unique | Controller, EmployeeRepository, employeeErrors | uq_employees_number, employees_preserve_identity | Doublon 1062→409 ; employees.create/update |
| Noms non vides et bornés | employeeErrors | ck_employees_names et VARCHAR(100) | 422 ; contrôle Unicode et caractères de contrôle |
| Contrat cohérent et non chevauchant | AdvancedHRController, PeriodValidation, PeriodRepository | hr_create_contract, ck_ec_type/dates, verrou employees | HR_DATES, HR_CONTRACT_TYPE, HR_OVERLAP ; contracts.create |
| Affectation valide et référentiels actifs | mêmes composants RH | hr_create_assignment, FK et garde des catalogues | HR_REFERENCE, HR_EMPLOYEE, HR_OVERLAP |
| Clôture unique sans casser salaire approuvé | AdvancedHRController::handle | hr_close_contract/assignment, ec/ea_preserve_history, ec_salary_coverage | HR_ALREADY_CLOSED, COMP_CONTRACT_COVERAGE |
| Proposition salariale positive, justifiée | CompensationValidation, CompensationController | compensation_submit, ck_cr_amount/reason | COMP_INVALID ; RH + compensation.submit |
| Initiale au début de contrat ; révisions au premier du mois | Validation de date et appel repository | compensation_check_period | COMP_COVERAGE, COMP_EFFECTIVE_DATE ; relecture à la décision |
| Approbation indépendante et unique | CompensationController, AuthService | compensation_decide, uq_cd_request | COMP_SELF_APPROVAL, COMP_ALREADY_DECIDED, COMP_STALE |
| Nouvelles opérations MAD | Money, referenceCurrencyReady | migration 006, routines MAD, payroll_build | COMP_CURRENCY_REVIEW, PAY_SALARY |
| Mois unique et plafonds explicites non négatifs | PayrollController, Validation | payroll_period_create, uq_pp_month, ck_pp_caps | PAY_INVALID, 1062 ; Finance |
| Élément dans le mois avec motif | Validation::input | payroll_input_submit, ck_pi_dates/amount/reason | PAY_INVALID, PAY_FROZEN ; RH |
| Décision élément indépendante, plafonds cumulés | PayrollController | payroll_input_decide, uq_pid_input | PAY_FORBIDDEN, PAY_DECIDED, PAY_CAP |
| Suspensions couvertes et non chevauchantes | Validation, Calendar de référence | payroll_input_decide, payroll_build | PAY_COVERAGE, PAY_OVERLAP |
| Aucun élément en attente au calcul | Repository::calculate | payroll_build | PAY_PENDING ; décision ou rejet préalable requis |
| Chaque jour contractuel a une source approuvée MAD | Calendar et Calculator de référence | payroll_build avec jointures demandes/décisions | PAY_SALARY, PAY_COVERAGE |
| Prorata calendaire et arrondi global | Calculator::calculate | payroll_build ROUND(...,2) | Pas de flottant PHP ; DECIMAL SQL |
| Net non négatif | Calculator, Validation des corrections | ck_pc_amounts, CHECK corrections, payroll_build | PAY_NET / PAY_INVALID |
| Nouvelle version avant gel | Repository::calculate | payroll_calculate, uq_pc_version | PAY_FROZEN ; bénéficiaire exclu |
| Vérification/approbation de la dernière source courante | PayrollController, payslip.php | payslip_transition, payroll_build, hash SHA2 | PAY_STALE, PAY_STATE |
| Une seule approbation par salarié/mois | Repository::transition | payroll_approvals UNIQUE(period_id,employee_id) | PAY_FROZEN, 1062 ; Finance distincte |
| Publication après approbation | PayrollController | payslip_transition | PAY_STATE ; Paie |
| Consultation propre publiée | AuthService, PayrollController | payslip_detail / payroll_overview | PAY_NOT_FOUND ; Employee |
| Correction complète et motivée | SettlementController | settlement_command, CHECK corrections | PAY_CAP, PAY_STATE, PAY_STALE |
| Paiement fictif intégral calculé côté SQL | SettlementController::handle | settlement_command, settlement_ledger | Solde positif, référence unique, Paie distincte de Finance |
| Trop-perçu sans retenue automatique | SettlementController | recovery_requests/events et ledger | Demande Paie, décision Finance, reçu Paie |
| Historique conservé | Repositories et vues | Triggers no_update/no_delete, FK et événements | COMP_IMMUTABLE / PAY_IMMUTABLE |

## Chaîne salariale et conditions versionnées

RH ne fixe pas directement un salaire applicable. `compensation_submit` produit une demande et un événement submitted. La première condition d’un contrat doit prendre effet à starts_on. Les suivantes doivent prendre effet au premier jour d’un mois et après la dernière condition ; le montant peut changer sans réécrire les versions anciennes. Une demande en attente n’est pas une condition salariale.

Finance décide approved/rejected en étant une personne différente du demandeur et de la bénéficiaire. La décision est unique. Une approbation revalide le contrat, le type initial/révision et la devise, ajoute salary_conditions puis l’événement ; un rejet n’ajoute aucune condition. Les anciennes valeurs UM sont conservées et peuvent bloquer une nouvelle demande/révision qui nécessite une revue ; elles ne deviennent jamais MAD en changeant un libellé d’interface.

La fin d’une condition est dérivée de la date suivante moins un jour, bornée par la fin effective du contrat. Le salaire d’un jour est la condition la plus récente de ce contrat dont effective_on≤jour. Une condition concernant un autre contrat n’est pas interchangeable.

## Périodes, ajustements, plafonds et suspensions

Finance crée un mois par son premier jour et renseigne deux plafonds absolus en MAD : bonus_cap et deduction_cap. Aucun taux automatique ni plafond réglementaire marocain n’est codé. Zéro est admis : cela interdit les éléments positifs de la catégorie. La période et ses plafonds sont immuables dans le schéma livré.

RH soumet bonus/deduction avec amount>0, ou paid_leave/unpaid_leave avec amount=0 et une période incluse dans le mois. Pour les primes/retenues, les dates sont conservées dans l’instantané mais le montant approuvé est additionné une fois, sans multiplication par le nombre de jours. Finance approuve/rejette indépendamment. L’approbation cumule les éléments déjà approuvés et refuse le dépassement de plafond. Deux suspensions approuvées ne peuvent couvrir le même jour ; chaque jour de suspension doit relever d’un contrat unique.

Un jour non rémunéré contribue zéro à la base. Un jour de suspension rémunérée conserve sa fraction de salaire. Un jour hors contrat n’entre pas au calendrier de salaire ; une suspension hors contrat est une erreur. Un élément encore pending empêche le calcul, même si l’opérateur souhaiterait l’ignorer. Après approbation du mois/employé, les nouveaux éléments et décisions sont gelés par les procédures de paie.

## Algorithme exact calendar-days-v1

Pour un mois de N jours calendaires, chaque jour couvert par un contrat doit disposer d’une unique condition salariale MAD approuvée. La procédure contrôle aussi la cohérence des identités, du montant, de la devise et de la décision favorable dans les tables de rémunération.

```text
numérateur = somme(salaire mensuel applicable à chaque jour rémunéré)
base = ARRONDI(numérateur / N, 2 décimales)
primes = somme des bonus approuvés du mois/employé
retenues = somme des deduction approuvées du mois/employé
brut = base + primes
net = brut - retenues
```

Les bornes de jour sont inclusives ; week-ends et jours fériés ne sont pas exclus. Les mois de 28, 29, 30 et 31 jours ont leur diviseur propre. Le numérateur est sommé avant un arrondi unique au centime. SQL utilise DECIMAL/ROUND ; le calculateur PHP indépendant utilise des centimes entiers, intdiv et un ajustement demi-supérieur pour les montants positifs. PHP 64 bits est exigé par Calculator. Le total brut ne peut dépasser 9 999 999 999,99 et les retenues ne peuvent dépasser le brut.

### Exemples dérivés des règles et preuves

| Situation | Calcul | Résultat | Statut de l’exemple |
|---|---|---|---|
| Nadia : 12 000 MAD, contrat du 3 au 30 novembre | 12 000 × 28/30 | Base/brut/net 11 200,00 MAD si aucune prime/retenue | Attesté par demo-verification.json |
| Même mois avec deux jours non payés, bonus 300, retenue 100 | 12 000 × 26/30 ; brut=10 400+300 ; net=10 700−100 | Base 10 400,00 ; brut 10 700,00 ; net 10 600,00 | Campagne isolée du 04/11 ; scénario distinct de Nadia principale |
| Mois 31 jours, un jour payé à 100 MAD/mois | 100/31=3,225806… | Base 3,23 MAD | Illustration arithmétique, non exécutée ici |
| Deux primes proposées de 300 avec plafond 500 | 300+300>500 | Une seule approbation concurrente possible dans le test | Attesté par payroll-races et rapport isolé |
| Correction publiée portant net de 11 200 à 11 500 après paiement 11 200 | 11 500−11 200 | Complément fictif 300,00 MAD | Illustration de règle, aucune écriture créée |
| Correction publiée portant net de 11 200 à 11 000 après paiement 11 200 | 11 000−11 200 | Solde −200 ; demande puis reçu de restitution 200 | Illustration de règle, aucune correction de Nadia réalisée ici |

## Préparation, vérification, décision et publication

`payroll_calculate` est le chemin réellement appelé par le web ; il verrouille le salarié, exige Paie et refuse de calculer sa propre paie. Il appelle payroll_build, attribue MAX(version_no)+1 et insère les totaux, snapshot JSON, algorithme et SHA256 des sources. Le calculateur PHP n’est pas appelé par cette procédure ni par PayrollController ; il permet une comparaison indépendante dans les tests.

Avant approbation, de nouveaux calculs créent des versions. La vérification porte sur la dernière version et reconstruit les sources. Finance ne décide qu’après verified et doit être différente de la personne préparatrice et bénéficiaire ; une approbation reconstruit encore les sources et vérifie hash et montants. Une approbation remplit payroll_approvals, unique sur salarié/mois. Un rejet est un événement conservé ; une autre version peut être préparée tant qu’aucune approbation ne gèle le couple.

La publication exige une approbation enregistrée. Elle ajoute un événement published et rend le bulletin accessible à l’employé propriétaire. La dernière version publiée n’est pas nécessairement le plus grand id de tous les brouillons dans chaque contexte : les procédures filtrent explicitement publication et racine. Aucune édition du bulletin approuvé n’est exposée.

## Corrections après publication

Une correction est une version exceptionnelle de **montants complets de remplacement**, pas un delta ni un recalcul automatique du calendrier original. Paie soumet base/bonus/deduction motivés ; SQL dérive brut/net et réapplique les plafonds. Le calendrier original reste conservé dans le calcul racine. La correction doit être vérifiée, décidée par Finance indépendante puis publiée avant de modifier le net effectif utilisé pour le solde.

`expected` identifie la correction publiée que l’opérateur a vue, ou 0 pour le bulletin original. `target` identifie l’objet de transition, et peut valoir 0 pour les actions sans cible particulière. Une version attendue périmée produit PAY_STALE. La procédure refuse une nouvelle correction lorsqu’une correction ou restitution incompatible est encore ouverte. Elle conserve un parent nullable de même racine et un numéro de révision croissant.

## Paiement et remboursement fictifs

Le net effectif est celui de la dernière correction publiée, sinon du bulletin original. Le registre additionne les paiements et soustrait les restitutions :

```text
cumul net versé = somme(payment.amount) - somme(recovery.amount)
solde = net effectif - cumul net versé
```

Finance enregistre un paiement correspondant à **tout le solde positif**, calculé en SQL. Le navigateur ne décide pas ce montant. Le bénéficiaire et le préparateur ne peuvent être le payeur. Une correction en examen bloque le règlement de l’ancienne situation. Le verrou employé, la relecture du solde et la référence unique empêchent deux commandes de payer le même dû, même avec des références distinctes.

Si le solde est négatif, Paie demande la restitution du trop-perçu ; Finance l’approuve/rejette indépendamment du demandeur/préparateur ; Paie enregistre ensuite le reçu avec référence. Le reçu est unique par recovery_id et ne peut dépasser le trop-perçu encore réel. Aucune retenue automatique sur une autre paie et aucun prélèvement bancaire ne sont implémentés.

Sources : `app/Payroll/{Repository,Calculator,Calendar,Validation}.php`, `app/Web/{PayrollController,SettlementController,CompensationController,AdvancedHRController}.php`, migrations 002–010 et routines MAD corrigées. Le détail intégral des branches SQL est au chapitre 06.
