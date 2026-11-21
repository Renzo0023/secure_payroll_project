# 09 — Scénario fonctionnel Nadia TRAORE

> Sources analysées au 11 novembre 2026 ; aucune attaque, écriture MySQL ou nouvelle recette fonctionnelle n’a été exécutée pendant cette mission.

## Référence et précaution de présentation

Le scénario concerne **Nadia TRAORE**, matricule **EMP-2026-001**, contrat **CDI-EMP-2026-001-01**, CDI à partir du **03/11/2026**, salaire approuvé **12 000,00 MAD**, mois **novembre 2026**. Le calcul de référence couvre les 28 jours inclusifs du 3 au 30 sur 30 jours calendaires : **11 200,00 MAD**. Aucun compte secret n’est reproduit.

`docs/DEMO-PRESENTATION.md` et `storage/logs/demo-verification.json` attestent qu’au 06/11/2026 le bulletin `/payslips/1` était déjà publié et réglé fictivement. Le profil de Nadia était `/employees/2`. Ces numéros proviennent d’une installation précise : les résoudre par matricule/référence sur une autre installation plutôt que supposer les mêmes IDs. L’état actuel reste Non vérifié.

Les étapes de création ci-dessous expliquent le parcours implémenté ; elles ne sont pas des actions à rejouer sur la principale. Pour une soutenance, montrer les données et historiques existants. Ne pas fabriquer une deuxième demande, période ou écriture de règlement pour rejouer le récit.

## Étapes et acteurs

| Étape | Acteur / rôle | Page et action | Contrôleur / repository | Tables et procédures | Protections | Résultat attendu / preuve |
|---|---|---|---|---|---|---|
| 1. Identité | RH / hr_manager | GET puis POST /employees/new : matricule, Nadia, TRAORE | Controller / EmployeeRepository::create | employees | CSRF, employees.create, unicité matricule, noms valides | Fiche stable ; la création historique n’est pas relancée |
| 2. Contrat | RH | /contracts/new : référence CDI, permanent, 2026-11-03, fin vide | AdvancedHRController / PeriodRepository::create | hr_create_contract ; employees, employment_contracts | Permission, salarié actif, verrou parent, pas de chevauchement, type/date | Contrat CDI sans montant salarial |
| 3. Proposition | RH | /compensation/new : salarié/contrat, 12000, date 2026-11-03, justification | CompensationController / CompensationRepository::submit | compensation_submit ; compensation_requests/history | Schéma MAD prêt, contrat correspondant, initiale au début, montant exact | Demande pending et événement submitted |
| 4. Décision salaire | Finance / finance_manager | /compensation/{demande} puis POST /decision, approved et motif | CompensationController / decide | compensation_decide ; compensation_decisions, salary_conditions, history | Acteur distinct RH/Nadia, unicité, couverture et devise relues | Condition approuvée de 12 000,00 MAD |
| 5. Période | Finance | /payroll : month=2026-11, bonus_cap=3300, deduction_cap=560 et motif ; POST /payroll/periods | PayrollController / createPeriod | payroll_period_create ; payroll_periods | Finance, mois unique, plafonds non négatifs explicites | Novembre 2026 créé ; plafonds ne sont pas des retenues |
| 6. Calcul | Paie / payroll_manager | /payroll : choisir période/Nadia ; POST /payroll/calculate | PayrollController / Repository::calculate | payroll_calculate→payroll_build ; contrats, salaire, décisions, éléments, calculs | Paie distincte de Nadia, verrou, salaire approuvé MAD, pas de pending, absence de gel | Version de calcul ; base=brut=net=11200, primes=retenues=0 |
| 7. Vérification | Paie | /payslips/{calcul} : calendrier, montants ; POST /transition event=verified + motif | PayrollController / transition | payslip_transition ; payroll_build, payslip_events | Dernière version, sources recalculées/hash identique, bénéficiaire exclue | Événement verified |
| 8. Approbation bulletin | Finance | Même bulletin : POST event=approved et motif | PayrollController / transition | payslip_events, payroll_approvals | verified requis, Finance distincte du préparateur/Nadia, fraîcheur, approbation unique | Événement approved ; couple mois/salarié gelé |
| 9. Publication | Paie | Même bulletin : POST event=published et motif | PayrollController / transition | payslip_transition ; payslip_events | Approbation obligatoire, payslip.publish, CSRF | Bulletin publié |
| 10. Consultation | Nadia / employee | /payroll puis /payslips/{calcul} | PayrollController / overview/detail | payroll_overview / payslip_detail | payslip.self, personne propriétaire, published ; SQL filtre | Bulletin visible sans boutons d’écriture |
| 11. Paiement fictif | Finance | /payslips/{calcul}/settlement : action=pay, expected=0, target=0, référence et motif | SettlementController / Repository::settle | settlement_command ; settlement_ledger | Module activé, Finance indépendante, solde SQL, verrou, référence unique | Écriture payment de 11200 ; aucun virement |
| 12. Solde et historique | Nadia ; Finance/Paie/Audit selon droits | /payslips/{calcul}/settlement | SettlementController / settlement | settlement_detail ; registre et événements | Bulletin propre publié pour Nadia ; lecture staff autorisée | Net 11200, cumul versé 11200, solde 0 ; historique conservé |

## Explication chiffrée pour le jury

Novembre compte 30 jours. Le 3 novembre est inclus : 30−3+1=28 jours. La base est ROUND(12000×28/30,2)=11200,00 MAD. Sans élément de prime ou retenue approuvé, brut=11200 et net=11200. Les plafonds **3300** et **560** ne sont ni des cotisations ni des ajustements automatiques : ils bornent des montants qui seraient proposés et approuvés séparément.

Le calendrier du bulletin montre chaque jour couvert et sa source salariale. Les événements de la recette attestent verified par la personne Paie, approved par Finance et published par Paie, à quelques instants distincts le 06/11/2026. L’empreinte des quatre tables de rémunération est annoncée inchangée avant/après la préparation de paie ; leurs comptes de lignes sont 1 demande, 1 décision, 2 événements et 1 condition.

Le registre historique contient un payment de 11 200,00 MAD, référence **DEMO-NADIA-202611-1**. Le solde nul fait disparaître le bouton de paiement dans la vue. L’absence de bouton est une commodité : la procédure refuse également un second paiement lorsque le solde n’est plus positif.

## État réellement attesté et limites

Le rapport JSON contient 64 libellés de contrôle et passed=true, horodaté 2026-11-06T19:39:59Z. Il atteste les connexions des six rôles, pages FR/EN, publication, consultation personnelle et règlement fictif. Les étapes initiales d’identité/contrat/salaire existaient déjà avant cette finalisation : leur création n’est pas présentée comme un nouveau test de cette campagne.

Les corrections et remboursements sont expliqués au chapitre 08 et validés historiquement dans le laboratoire. Aucune correction de Nadia n’est annoncée sur la principale. Une régression isolée de 24 contrôles, après restauration d’un dump, a exercé paiement et correction avec les champs target=0 réellement rendus par les formulaires.

Pendant la soutenance, déconnecter chaque rôle avant le suivant ; les onglets d’un même profil navigateur partagent la session. Une fenêtre privée peut isoler une seconde session. Montrer ensuite IAM avec Admin, puis Audit en lecture, sans modifier les attributions préparées.
