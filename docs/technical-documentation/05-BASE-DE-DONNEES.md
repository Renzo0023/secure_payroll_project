# 05 — Conception et inventaire MySQL

> Analyse des sources au 11 novembre 2026. Schéma installé actuellement : **Non vérifié**. Les déclarations SQL et les attestations historiques sont distinguées.

## Périmètre et preuve

Le schéma versionné comprend 25 tables après migrations 001–011, 24 procédures distinctes et 42 triggers. Les campagnes isolées et la recette principale du 6 novembre sont des preuves historiques. Le schéma effectivement présent au 11 novembre n’a pas été interrogé : aucune variable DB_* ou MYSQL_* de connexion n’est disponible, aucun accès administratif supplémentaire n’a été demandé. Une table installée hors migrations ne peut donc être exclue. L’inventaire ci-dessous est exhaustif pour les sources, sans se présenter comme un relevé live.

## Tables déclarées

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

## Modèle relationnel et cardinalités

`employees` est le pivot d’identité, `accounts.employee_id` est unique : un salarié peut avoir zéro ou un compte, chaque compte référence exactement un salarié. Le code de défense recherche pourtant les conflits sur toutes les identités de compte d’une personne ; cette défense anticipative ne signifie pas que plusieurs comptes par salarié sont autorisés par le schéma actuel.

Les comptes et rôles sont associés N:N à travers `role_assignments`, avec une temporalité et un historique d’octroi/révocation. Les rôles et permissions sont associés N:N via `role_permissions` à clé primaire composée. Un employé possède plusieurs périodes contractuelles et affectations dans le temps ; les procédures interdisent leur chevauchement pour une même catégorie.

Les départements et postes sont indépendants. `employee_assignments` référence les deux ; aucune FK ne rattache directement un poste à un département. Il ne faut donc pas dessiner de relation supplémentaire `positions.department_id`.

Une demande salariale concerne un employé et un contrat ; elle peut avoir zéro ou une décision grâce à UNIQUE(request_id). Une condition approuvée référence la paire (request_id, decision_id) de la décision et ne peut partager son request_id avec une autre condition. La cohérence entre montant, bénéficiaire, décision approved et contrat est renforcée par les procédures : une FK ne valide pas à elle seule toutes ces égalités métier.

Un mois de paie est unique par month_start. Pour un salarié et un mois, plusieurs calculs versionnés sont possibles avant approbation. `payroll_approvals` impose une seule approbation pour le couple période/employé ; sa FK composée prouve que le calcul correspond au bon couple. Les corrections possèdent une racine calculation_id et un parent de même racine via une FK composée ; ce parent peut être NULL pour la première correction. Les reçus possèdent une référence de registre unique et un recovery_id unique lorsqu’il est renseigné.

## Intégrité physique et logique

Toutes les tables sont déclarées InnoDB en utf8mb4_0900_as_cs ; une comparaison applicative peut être encore plus stricte grâce à CAST AS BINARY. Les identifiants sont majoritairement BIGINT UNSIGNED, les montants DECIMAL(12,2), les jours DATE, les instants DATETIME(6). Les dates techniques sont traitées en UTC.

Les PK et UNIQUE empêchent les doublons structurants ; les FK bloquent les références inexistantes et les suppressions de parents référencés. Lorsque ON DELETE/UPDATE n’est pas explicitement écrit, le comportement restrictif InnoDB s’applique ; aucune cascade métier n’est définie. Les CHECK encadrent montants, états, bornes, motifs, devise et identités canoniques. Le détail exact de chaque expression est dans le dictionnaire, avec les index déclarés.

Les clés étrangères peuvent entraîner des index de support créés implicitement par InnoDB. Leur nom physique ne doit pas être inventé : seul SHOW INDEX sur le serveur confirmerait ces noms. Les noms de contraintes FK/CHECK non explicités dans la migration 009 sont générés par MySQL ; leurs expressions sont reproduites, pas leurs noms supposés.

`effective_ends_on` est une colonne générée stockée dans les deux tables de périodes RH. Les conditions salariales n’ont pas de colonne de fin : leur fin est dérivée de la prochaine date d’effet moins un jour et de la fin effective du contrat (`CompensationRepository::history`). La protection contre chevauchements dépend de verrous et procédures, pas d’une contrainte SQL d’exclusion inexistante dans ces fichiers.

## Normalisation et dénormalisations justifiées

Les catalogues de rôles/permissions et départements/postes évitent les libellés répétés dans chaque opération. Les tables d’association matérialisent les N:N. La séparation demande/décision/condition évite de transformer une proposition en salaire applicable par simple changement d’état.

Les colonnes actor_employee_id, requester_employee_id et approver_employee_id conservent une identité de personne à côté de l’identifiant de compte pour la séparation des tâches et la traçabilité. Les calculs conservent simultanément les totaux et un snapshot JSON : c’est une dénormalisation d’historisation volontaire. Les contraintes assurent gross=base+bonus et net=gross−deduction, tandis que le recalcul SQL compare la fraîcheur des sources avant approbation. Il ne s’agit pas d’une preuve formelle de troisième forme normale de toute la base.

## Historique de la devise et patches

La migration 004 utilisait UM en CHAR(2). La migration 006 élargit à CHAR(3), change le défaut à MAD et autorise UM/MAD pour préserver l’existant, puis remplace trois routines. Le patch 002 est une réparation de schéma gardée ; le patch 003 reprend les routines MAD. Le patch 001 corrige la collation du paramètre de hr_assert_permission et rétablit son EXECUTE au propriétaire après DROP/CREATE. Ces scripts ne doivent jamais être rejoués comme une chaîne automatique sur une installation inconnue.

## Diagrammes

Les fichiers `ENTITE-ASSOCIATION.mmd` et `RELATIONS-MYSQL.mmd` contiennent toutes les FK extraites des CREATE TABLE. Le diagramme EA distingue une référence parent obligatoire d’une référence composite rendue optionnelle par une composante NULL. Les contraintes de workflow ne deviennent pas des relations supplémentaires. La version PDF inclut des planches graphiques regroupées par domaine ; la liste FK et le fichier Mermaid complet restent la référence pour les liens entre domaines.

## Inspection future en lecture seule

Les commandes ci-dessous sont préparées uniquement. Elles utilisent un profil de lecture existant nommé ici LECTURE_EXISTANTE, à remplacer par un profil déjà autorisé ; aucune création de profil ni authentification administrative n’est exécutée.

```bash
mysql --login-path=LECTURE_EXISTANTE --database=secure_payroll --batch --execute="SELECT VERSION(), CURRENT_USER(), DATABASE(), @@session.time_zone; SHOW FULL TABLES; SHOW GRANTS FOR CURRENT_USER;"
```

Pour les détails (lecture seule), exécuter les requêtes de `INSPECTION-MYSQL-LECTURE-SEULE.sql`. SHOW CREATE TABLE et SHOW CREATE PROCEDURE/TRIGGER doivent compléter le relevé, car certaines définitions peuvent être masquées par les privilèges. L’accès à mysql.user et aux droits d’autres comptes peut exiger un opérateur administratif : justifié pour confirmer ACCOUNT LOCK, DEFINER et moindre privilège, sans élargir les droits de l’application.

La preuve actuelle disponible est `storage/logs/demo-verification.json` : elle atteste les propriétaires/droits et quatre comptes de lignes de rémunération au 06/11, mais ne contient pas un dump détaillé du schéma. Le dictionnaire du chapitre 13 reste un dictionnaire de sources.
