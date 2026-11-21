# 07 — Sécurité, RBAC et IAM

> Sources analysées au 11 novembre 2026 ; aucune attaque, écriture MySQL ou nouvelle recette fonctionnelle n’a été exécutée pendant cette mission.

## Authentification

`AuthService::login(login, password)` prépare une recherche de compte avec jointure employees, exige `disabled_at IS NULL` et `archived_at IS NULL`, puis utilise `password_verify`. Une empreinte Argon2id de remplacement indépendante de tout compte permet d’effectuer un travail cryptographique même lorsque le login n’existe pas. Le résultat n’est accepté que si password_get_info annonce argon2id. Les mots de passe en clair ne sont pas stockés dans accounts ; `ck_accounts_argon2id` vérifie le format PHC, tandis que la validation cryptographique reste en PHP.

Les scripts de provisioning produisent des empreintes avec PASSWORD_ARGON2ID (`bin/local-demo.py`, `bin/payroll-admin.py`, `bin/demo-finalize.py`). Aucun formulaire de création de compte ou réinitialisation n’existe. Aucun mécanisme de MFA ni de réhachage automatique après connexion n’est présent. Les coûts de l’empreinte de remplacement sont visibles dans le code ; ils ne permettent pas d’affirmer que toutes les empreintes réelles ont les mêmes paramètres.

Le contrôleur limite login à 760 octets et password à 4096 ; le formulaire affiche maxlength=190 pour login. Une erreur de connexion reste générique (401) ; une indisponibilité renvoie 503. Le code ne renvoie pas « compte inexistant » et ne révèle pas les messages PDO.

## Limitation des tentatives

`LoginLimiter::allow` utilise REMOTE_ADDR, sans faire confiance à X-Forwarded-For. Un fichier nommé par SHA256 de l’adresse conserve until/count, protégé par flock(LOCK_EX). La fenêtre dure 900 secondes et contient cinq réservations. À partir de la sixième, le serveur répond 429 et Retry-After: 900. Le compteur est initialisé sous umask 0077.

`LoginLimiter::succeeded` retire uniquement la réservation de la requête réussie si la fenêtre correspond encore ; il ne remet pas à zéro les échecs des autres requêtes. Cela corrige l’affirmation ancienne de WEB-SETUP selon laquelle les succès consommeraient durablement le quota. Le limiteur est local à l’hôte/répertoire et partagé par les utilisateurs derrière une même IP ; il n’est pas distribué et ne constitue pas une protection volumétrique réseau.

## Sessions et cookies

`Session::start` active strict_mode/use_only_cookies, désactive trans_sid et utilise secure_payroll_session. Le cookie est de session (lifetime=0), path=/, HttpOnly et SameSite=Lax. Secure est activé uniquement si `$_SERVER['HTTPS']` existe et n’est pas off ; le HTTP local de démonstration n’active donc pas ce drapeau.

Un compte authentifié expire après plus de 1200 secondes d’inactivité ou 28800 secondes depuis la connexion. L’identifiant est régénéré toutes les 900 secondes et après signIn/clear. signIn vide l’état précédent, conserve la langue et génère un nouveau CSRF ; clear retire l’identité, conserve la langue et crée un nouvel identifiant/jeton, sans détruire toute possibilité de session anonyme. Les autorisations ne sont pas conservées comme vérité en session : elles sont relues à chaque requête privée.

`Runtime::directory` choisit par défaut storage/logs ; si APP_RUNTIME_DIR est fourni, il doit être absolu, existant, accessible en écriture, privé et appartenir au processus. Le chemin des sessions n’est changé vers ce répertoire que lorsque cette option est configurée ; autrement le gestionnaire de sessions PHP conserve son chemin système. Les permissions système effectives n’ont pas été certifiées par cette analyse.

## CSRF et navigateur

Le jeton provient de random_bytes(32), encodé en hexadécimal. `validCsrf` exige une chaîne et compare via hash_equals. `Controller::run` le vérifie pour tous les POST connus, y compris login, langue et déconnexion. Aucun changement métier par GET n’est routé. SameSite est une protection supplémentaire, pas un remplacement du jeton.

`public/index.php` pose X-Content-Type-Options: nosniff, Referrer-Policy: no-referrer et Cache-Control: no-store. Sa CSP est `default-src 'none'; style-src 'self'; script-src 'self'; img-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'`. Les valeurs sont échappées par `h()` avec ENT_QUOTES|ENT_SUBSTITUTE ; les fichiers CSS/JS sont locaux. Ces mécanismes réduisent XSS, framing et fuite via référent, sans constituer une preuve d’absence absolue de XSS.

## RBAC temporel et séparation des tâches

`roles` contient exactement six couples canoniques protégés par CHECK ; `permissions` porte les codes et `role_permissions` leur association N:N. `role_assignments` conserve auteurs, motifs, octroi, début de validité, expiration et révocation. Une attribution est utilisée si valid_from≤UTC_TIMESTAMP(6), expires_at absent ou futur, revoked_at absent ou futur. L’horloge SQL est donc une dépendance de sécurité.

`AuthService::currentUser` relit compte/salarié actifs puis rôles et permissions à chaque requête. `can` combine permission, rôle attendu et conflits : les modules paie/IAM refusent le cumul de plusieurs rôles parmi RH, Paie, Finance, Admin et Audit ; payslip.self conserve son cas particulier. La rémunération utilise la matrice historique RH/Finance. Les autorisations RH générales exigent RH sans reprendre toutes les restrictions de la paie.

`iam_grant` prend un verrou exclusif sur le salarié cible, exige application_administrator/iam.grant et interdit d’agir sur sa propre personne. Il refuse cible inactive, rôle inexistant, motif vide ou >255, rôle identique encore valide, et cumul de rôles opérationnels existants ou planifiés. Employee peut coexister avec un rôle opérationnel. Le rôle et les comptes soumis sont des cibles, jamais l’identité de l’acteur. L’octroi produit une nouvelle attribution à l’instant SQL.

`iam_revoke` exige iam.revoke, interdit la personne propre et réalise un UPDATE uniquement si revoked_at est NULL. ROW_COUNT doit valoir 1 ; les triggers conservent l’octroi et n’acceptent qu’une première révocation au moment SQL courant. Les sessions déjà ouvertes perdent les droits au prochain rechargement de currentUser ; aucun cache persistant de permission n’est utilisé. L’IAM ne gère pas les expirations planifiées dans l’interface, même si le schéma les supporte.

## Comptes et privilèges MySQL

| Compte / contexte déclaré | Rôle SQL | Limites pertinentes | Sources |
|---|---|---|---|
| svc_php@localhost | Connexion PDO du serveur web | SELECT limités, INSERT identité et UPDATE noms, EXECUTE publics ; pas de root/DDL/GRANT OPTION | svc_php_grants.sql et *_grants.sql |
| hr_module_owner@localhost | DEFINER des périodes RH | Propriétaire verrouillé ; DML borné sur périodes et lectures nécessaires | advanced_hr_owner*.sql |
| compensation_owner@localhost | DEFINER rémunération | Propriétaire verrouillé ; écritures des quatre historiques par routines | compensation_owner*.sql |
| payroll_owner@localhost | DEFINER paie | Propriétaire verrouillé ; droits explicites par colonnes/tables et helpers | payroll_owner*.sql |
| settlement_owner@localhost | DEFINER corrections/règlements | Propriétaire verrouillé ; dépend des assertions Paie | settlement_owner*.sql |
| iam_owner@localhost | DEFINER attributions | Propriétaire verrouillé ; lecture RBAC et écriture limitée des attributions | iam_owner*.sql |
| Compte de sauvegarde dédié | Export par bin/backup.py | Doit préexister ; le script refuse root, svc_php et certains propriétaires | bin/backup.py |
| Opérateur de maintenance | DDL et installation distincts | N’est pas la connexion de l’application ; droits effectifs actuels Non vérifié | bin/*-admin.py |

Les tables Paie/Settlement ne sont ni lisibles ni modifiables directement par svc_php d’après les GRANT versionnés : la lecture passe aussi par procédures à périmètre acteur. À l’inverse, svc_php dispose de SELECT directs sur les données de rémunération et RH, ainsi que d’un SELECT de password_hash nécessaire au login. Il ne faut pas décrire ces domaines comme exclusivement accessibles par procédure.

SQL SECURITY DEFINER n’autorise pas le compte verrouillé à se connecter : il fournit un contexte de droits à la routine. L’appelant doit avoir EXECUTE et le DEFINER les droits d’objet et d’appels imbriqués. Supprimer/recréer une procédure peut supprimer les droits spécifiques de routine ; les scripts de maintenance doivent les comparer et les rétablir strictement.

## Menaces et mécanismes réels

| Menace | Protection constatée | Portée / limite |
|---|---|---|
| Injection SQL | prepare/execute natifs ; DSN validé ; table/langue choisies par listes fermées ; OFFSET calculé depuis entier | Ne vaut pas audit exhaustif de tous les scripts administratifs |
| IDOR/BOLA identité | Comparaison id au employee_id de session hors employees.read | RH dispose légitimement d’une lecture transversale |
| IDOR/BOLA bulletins | payslip_detail/payroll_overview vérifient personne et événement published | Les permissions restent requises ; un numéro valide seul ne suffit pas |
| Accès horizontal règlement | settlement_detail exige bulletin publié et propriétaire si non-staff ; filtre les brouillons de correction | Staff habilité dispose d’un accès transversal |
| Élévation de privilèges | Rôle + permission relus, séparation IAM, refus d’auto-octroi et incompatibilités | Admin peut attribuer un rôle puissant à une autre personne ; pas de double validation IAM |
| Auto-approbation | Comparaison des employee_id de demandeur/préparateur, approbateur et bénéficiaire | Identités opérationnelles distinctes requises |
| CSRF | Jeton de session sur tous les POST, hash_equals, SameSite | XSS de même origine peut compromettre des actions ; CSP/échappement nécessaires |
| Altération financière | DECIMAL, CHECK, FK composées, append-only, aucun DML direct service | Un administrateur DDL reste capable de changer les protections |
| Paiement double | Verrou employé, relecture du solde, version attendue, référence unique | Fictif ; aucune garantie d’idempotence chez un prestataire bancaire absent |
| Sources périmées | Recalcul et comparaison du snapshot/hash avant verified/approved | SHA256 non signé ; pas de preuve indépendante d’un administrateur hostile |
| Fuite d’erreur | Messages génériques, absence de trace/DSN/arguments, logs techniques minimisés | Protéger aussi les fichiers, dumps et accès système |

## Frontière de confiance à expliquer au jury

Les procédures reçoivent p_actor comme paramètre. Dans l’application, ce paramètre provient de la session authentifiée. Le compte MySQL svc_php est partagé par les requêtes et n’est pas lié à un utilisateur web individuel par CURRENT_USER. Par lecture du code, une compromission complète de ce compte ou du serveur PHP pourrait donc permettre de soumettre l’identifiant d’un autre acteur autorisé aux routines publiques. Les assertions vérifient les droits de l’identité fournie ; elles ne prouvent pas cryptographiquement qui l’a fournie. Il s’agit d’une limite déduite de l’architecture, non d’une attaque exécutée.

Les triggers préservent l’historique contre les DML interdits ; ils ne constituent pas une piste d’audit hors base, signée ou résistante à un DBA malveillant. L’application ne chiffre pas elle-même les montants en colonnes et ne démontre pas de chiffrement disque/TLS MySQL actuel. Le périmètre local réduit l’exposition réseau, sans dispenser de protéger la VM, les backups et les comptes système.

Sources principales : `AuthService.php`, `Session.php`, `LoginLimiter.php`, `Runtime.php`, `helpers.php`, `public/index.php`, migrations 001/003/005/006/008/010/011 et tous les GRANT de database/setup. L’état réel des comptes et droits reste Non vérifié dans cette mission ; la recette historique administrative figure dans demo-verification.json.

## Annexe — droits d’objets déclarés, sans exécution

Ces instructions sont reproduites comme pièces de justification ; elles ne sont pas une procédure à appliquer sur l’existant. Les fichiers de création de comptes ne sont pas inclus dans cette annexe.

### advanced_hr_grants.sql

Source : [database/setup/advanced_hr_grants.sql](../../database/setup/advanced_hr_grants.sql).

```sql
-- Droits ADDITIONNELS pour le svc_php@localhost existant, après validation.
-- Aucune écriture directe sur les nouveaux catalogues ou historiques.
-- À appliquer APRÈS advanced_hr_owner_grants.sql. Aucun EXECUTE sur le helper.
-- Les neuf objets déclarent hr_module_owner@localhost comme DEFINER, jamais svc_php.
GRANT SELECT ON secure_payroll.departments TO 'svc_php'@'localhost';
GRANT SELECT ON secure_payroll.positions TO 'svc_php'@'localhost';
GRANT SELECT ON secure_payroll.employee_assignments TO 'svc_php'@'localhost';
GRANT SELECT ON secure_payroll.employment_contracts TO 'svc_php'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.hr_create_assignment TO 'svc_php'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.hr_close_assignment TO 'svc_php'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.hr_create_contract TO 'svc_php'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.hr_close_contract TO 'svc_php'@'localhost';
```

### advanced_hr_owner_grants.sql

Source : [database/setup/advanced_hr_owner_grants.sql](../../database/setup/advanced_hr_owner_grants.sql).

```sql
-- Après création des tables ET procédures 002/003 ; propriétaire neuf et verrouillé.
-- Aucun droit global, GRANT OPTION, CREATE/ALTER/DROP, DELETE ou autre base.
GRANT SELECT (id, archived_at) ON secure_payroll.employees TO 'hr_module_owner'@'localhost';
-- Nécessaire au SELECT FOR UPDATE de la ligne parent sous MySQL 8.4.
-- Les procédures ne font aucun UPDATE employees. Le trigger 001 protège aussi id.
GRANT UPDATE (id) ON secure_payroll.employees TO 'hr_module_owner'@'localhost';
GRANT SELECT (id, employee_id, disabled_at) ON secure_payroll.accounts TO 'hr_module_owner'@'localhost';
GRANT SELECT (id, code) ON secure_payroll.roles TO 'hr_module_owner'@'localhost';
GRANT SELECT (id, code) ON secure_payroll.permissions TO 'hr_module_owner'@'localhost';
GRANT SELECT (role_id, permission_id) ON secure_payroll.role_permissions TO 'hr_module_owner'@'localhost';
GRANT SELECT (account_id, role_id, valid_from, expires_at, revoked_at)
    ON secure_payroll.role_assignments TO 'hr_module_owner'@'localhost';
GRANT SELECT (id, archived_at) ON secure_payroll.departments TO 'hr_module_owner'@'localhost';
GRANT SELECT (id, archived_at) ON secure_payroll.positions TO 'hr_module_owner'@'localhost';
GRANT SELECT ON secure_payroll.employee_assignments TO 'hr_module_owner'@'localhost';
GRANT SELECT ON secure_payroll.employment_contracts TO 'hr_module_owner'@'localhost';
GRANT INSERT (employee_id, department_id, position_id, starts_on, ends_on, created_by, created_at)
    ON secure_payroll.employee_assignments TO 'hr_module_owner'@'localhost';
GRANT INSERT (employee_id, reference, contract_type, starts_on, ends_on, created_by, created_at)
    ON secure_payroll.employment_contracts TO 'hr_module_owner'@'localhost';
GRANT UPDATE (closed_on, closed_at, closed_by)
    ON secure_payroll.employee_assignments TO 'hr_module_owner'@'localhost';
GRANT UPDATE (closed_on, closed_at, closed_by)
    ON secure_payroll.employment_contracts TO 'hr_module_owner'@'localhost';
-- TRIGGER est vérifié à l’activation, même pour les triggers qui refusent un DELETE.
GRANT TRIGGER ON secure_payroll.employee_assignments TO 'hr_module_owner'@'localhost';
GRANT TRIGGER ON secure_payroll.employment_contracts TO 'hr_module_owner'@'localhost';
-- Le DEFINER doit avoir EXECUTE sur ses routines, y compris le helper imbriqué.
GRANT EXECUTE ON PROCEDURE secure_payroll.hr_assert_permission TO 'hr_module_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.hr_create_assignment TO 'hr_module_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.hr_close_assignment TO 'hr_module_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.hr_create_contract TO 'hr_module_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.hr_close_contract TO 'hr_module_owner'@'localhost';
```

### compensation_grants.sql

Source : [database/setup/compensation_grants.sql](../../database/setup/compensation_grants.sql).

```sql
-- Aucun INSERT/UPDATE/DELETE direct sur les quatre tables financières.
GRANT SELECT ON secure_payroll.compensation_requests TO 'svc_php'@'localhost';
GRANT SELECT ON secure_payroll.compensation_decisions TO 'svc_php'@'localhost';
GRANT SELECT ON secure_payroll.salary_conditions TO 'svc_php'@'localhost';
GRANT SELECT ON secure_payroll.compensation_history TO 'svc_php'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.compensation_submit TO 'svc_php'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.compensation_decide TO 'svc_php'@'localhost';
```

### compensation_owner_grants.sql

Source : [database/setup/compensation_owner_grants.sql](../../database/setup/compensation_owner_grants.sql).

```sql
-- Propriétaire neuf verrouillé. Aucun privilège global ou autre base.
GRANT SELECT (id,archived_at) ON secure_payroll.employees TO 'compensation_owner'@'localhost';
-- Exigence MySQL 8.4 pour FOR UPDATE ; les routines ne modifient jamais employees.
GRANT UPDATE (id) ON secure_payroll.employees TO 'compensation_owner'@'localhost';
GRANT SELECT (id,employee_id,disabled_at) ON secure_payroll.accounts TO 'compensation_owner'@'localhost';
GRANT SELECT (id,code) ON secure_payroll.roles TO 'compensation_owner'@'localhost';
GRANT SELECT (id,code) ON secure_payroll.permissions TO 'compensation_owner'@'localhost';
GRANT SELECT (role_id,permission_id) ON secure_payroll.role_permissions TO 'compensation_owner'@'localhost';
GRANT SELECT (account_id,role_id,valid_from,expires_at,revoked_at) ON secure_payroll.role_assignments TO 'compensation_owner'@'localhost';
GRANT SELECT (id,employee_id,starts_on,effective_ends_on,closed_on) ON secure_payroll.employment_contracts TO 'compensation_owner'@'localhost';
GRANT TRIGGER ON secure_payroll.employment_contracts TO 'compensation_owner'@'localhost';
GRANT SELECT,INSERT,TRIGGER ON secure_payroll.compensation_requests TO 'compensation_owner'@'localhost';
GRANT SELECT,INSERT,TRIGGER ON secure_payroll.compensation_decisions TO 'compensation_owner'@'localhost';
GRANT SELECT,INSERT,TRIGGER ON secure_payroll.salary_conditions TO 'compensation_owner'@'localhost';
GRANT SELECT,INSERT,TRIGGER ON secure_payroll.compensation_history TO 'compensation_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.compensation_assert_permission TO 'compensation_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.compensation_check_period TO 'compensation_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.compensation_submit TO 'compensation_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.compensation_decide TO 'compensation_owner'@'localhost';
```

### iam_grants.sql

Source : [database/setup/iam_grants.sql](../../database/setup/iam_grants.sql).

```sql
GRANT EXECUTE ON PROCEDURE secure_payroll.iam_overview TO 'svc_php'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.iam_grant TO 'svc_php'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.iam_revoke TO 'svc_php'@'localhost';
```

### iam_owner_grants.sql

Source : [database/setup/iam_owner_grants.sql](../../database/setup/iam_owner_grants.sql).

```sql
GRANT SELECT(id,employee_number,archived_at),UPDATE(id) ON secure_payroll.employees TO 'iam_owner'@'localhost';
GRANT SELECT(id,employee_id,login,disabled_at) ON secure_payroll.accounts TO 'iam_owner'@'localhost';
GRANT SELECT(id,code,name) ON secure_payroll.roles TO 'iam_owner'@'localhost';
GRANT SELECT,INSERT(account_id,role_id,granted_by_account_id,grant_reason),UPDATE(revoked_at,revoked_by_account_id,revocation_reason) ON secure_payroll.role_assignments TO 'iam_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.payroll_assert TO 'iam_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.iam_overview TO 'iam_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.iam_grant TO 'iam_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.iam_revoke TO 'iam_owner'@'localhost';
```

### payroll_grants.sql

Source : [database/setup/payroll_grants.sql](../../database/setup/payroll_grants.sql).

```sql
-- Service can only call public operations. No SELECT or DML on new tables.
GRANT EXECUTE ON PROCEDURE secure_payroll.payroll_period_create TO 'svc_php'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.payroll_input_submit TO 'svc_php'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.payroll_input_decide TO 'svc_php'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.payroll_calculate TO 'svc_php'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.payslip_transition TO 'svc_php'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.payroll_overview TO 'svc_php'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.payslip_detail TO 'svc_php'@'localhost';
```

### payroll_owner_grants.sql

Source : [database/setup/payroll_owner_grants.sql](../../database/setup/payroll_owner_grants.sql).

```sql
-- Dedicated locked owner; no global privileges, GRANT OPTION or direct financial UPDATE.
GRANT SELECT (id,employee_number,first_name,last_name,archived_at),UPDATE(id) ON secure_payroll.employees TO 'payroll_owner'@'localhost';
GRANT SELECT (id,employee_id,disabled_at) ON secure_payroll.accounts TO 'payroll_owner'@'localhost';
GRANT SELECT (id,code) ON secure_payroll.roles TO 'payroll_owner'@'localhost';
GRANT SELECT (id,code) ON secure_payroll.permissions TO 'payroll_owner'@'localhost';
GRANT SELECT (role_id,permission_id) ON secure_payroll.role_permissions TO 'payroll_owner'@'localhost';
GRANT SELECT (account_id,role_id,valid_from,expires_at,revoked_at) ON secure_payroll.role_assignments TO 'payroll_owner'@'localhost';
GRANT SELECT (id,employee_id,starts_on,effective_ends_on) ON secure_payroll.employment_contracts TO 'payroll_owner'@'localhost';
GRANT SELECT (id,employee_id,contract_id,request_id,decision_id,monthly_amount,currency,effective_on) ON secure_payroll.salary_conditions TO 'payroll_owner'@'localhost';
GRANT SELECT (id,employee_id,contract_id,monthly_amount,currency,effective_on,requester_employee_id) ON secure_payroll.compensation_requests TO 'payroll_owner'@'localhost';
GRANT SELECT (id,request_id,decision,approver_employee_id) ON secure_payroll.compensation_decisions TO 'payroll_owner'@'localhost';
GRANT SELECT,INSERT,TRIGGER ON secure_payroll.payroll_periods TO 'payroll_owner'@'localhost';
GRANT SELECT,INSERT,TRIGGER ON secure_payroll.payroll_inputs TO 'payroll_owner'@'localhost';
GRANT SELECT,INSERT,TRIGGER ON secure_payroll.payroll_input_decisions TO 'payroll_owner'@'localhost';
GRANT SELECT,INSERT,TRIGGER ON secure_payroll.payroll_calculations TO 'payroll_owner'@'localhost';
GRANT SELECT,INSERT,TRIGGER ON secure_payroll.payslip_events TO 'payroll_owner'@'localhost';
GRANT SELECT,INSERT,TRIGGER ON secure_payroll.payroll_approvals TO 'payroll_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.payroll_assert TO 'payroll_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.payroll_period_create TO 'payroll_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.payroll_input_submit TO 'payroll_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.payroll_input_decide TO 'payroll_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.payroll_build TO 'payroll_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.payroll_calculate TO 'payroll_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.payslip_transition TO 'payroll_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.payroll_read_assert TO 'payroll_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.payroll_overview TO 'payroll_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.payslip_detail TO 'payroll_owner'@'localhost';
```

### settlement_grants.sql

Source : [database/setup/settlement_grants.sql](../../database/setup/settlement_grants.sql).

```sql
GRANT EXECUTE ON PROCEDURE secure_payroll.settlement_command TO 'svc_php'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.settlement_detail TO 'svc_php'@'localhost';
```

### settlement_owner_grants.sql

Source : [database/setup/settlement_owner_grants.sql](../../database/setup/settlement_owner_grants.sql).

```sql
GRANT SELECT(id,archived_at),UPDATE(id) ON secure_payroll.employees TO 'settlement_owner'@'localhost';
GRANT SELECT ON secure_payroll.payroll_calculations TO 'settlement_owner'@'localhost';
GRANT SELECT ON secure_payroll.payroll_periods TO 'settlement_owner'@'localhost';
GRANT SELECT ON secure_payroll.payslip_events TO 'settlement_owner'@'localhost';
GRANT SELECT,INSERT,TRIGGER ON secure_payroll.payslip_corrections TO 'settlement_owner'@'localhost';
GRANT SELECT,INSERT,TRIGGER ON secure_payroll.correction_events TO 'settlement_owner'@'localhost';
GRANT SELECT,INSERT,TRIGGER ON secure_payroll.recovery_requests TO 'settlement_owner'@'localhost';
GRANT SELECT,INSERT,TRIGGER ON secure_payroll.recovery_events TO 'settlement_owner'@'localhost';
GRANT SELECT,INSERT,TRIGGER ON secure_payroll.settlement_ledger TO 'settlement_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.payroll_assert TO 'settlement_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.payroll_read_assert TO 'settlement_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.settlement_command TO 'settlement_owner'@'localhost';
GRANT EXECUTE ON PROCEDURE secure_payroll.settlement_detail TO 'settlement_owner'@'localhost';
```

### svc_php_grants.sql

Source : [database/setup/svc_php_grants.sql](../../database/setup/svc_php_grants.sql).

```sql
-- À appliquer uniquement après validation, au compte NOUVEAU svc_php@localhost.
-- Ce fichier ne crée pas de compte et ne contient aucun secret.
-- Aucun privilège global, aucun droit sur une autre base, aucun GRANT OPTION.
GRANT SELECT ON secure_payroll.employees TO 'svc_php'@'localhost';
GRANT SELECT (id, employee_id, login, password_hash, disabled_at)
    ON secure_payroll.accounts TO 'svc_php'@'localhost';
GRANT SELECT (id, code, name) ON secure_payroll.roles TO 'svc_php'@'localhost';
GRANT SELECT (id, code) ON secure_payroll.permissions TO 'svc_php'@'localhost';
GRANT SELECT (role_id, permission_id)
    ON secure_payroll.role_permissions TO 'svc_php'@'localhost';
GRANT SELECT (account_id, role_id, valid_from, expires_at, revoked_at)
    ON secure_payroll.role_assignments TO 'svc_php'@'localhost';
GRANT INSERT (employee_number, first_name, last_name)
    ON secure_payroll.employees TO 'svc_php'@'localhost';
GRANT UPDATE (first_name, last_name)
    ON secure_payroll.employees TO 'svc_php'@'localhost';
```
