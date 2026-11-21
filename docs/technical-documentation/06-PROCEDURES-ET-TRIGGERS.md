# 06 — Procédures stockées et triggers

> Analyse des sources au 11 novembre 2026. Schéma installé actuellement : **Non vérifié**. Les déclarations SQL et les attestations historiques sont distinguées.

## Convention d’inventaire

Les 24 noms distincts sont reconstruits en prenant la dernière définition versionnée par migration puis les correctifs ciblés. Pour hr_assert_permission, le patch 001 précise la collation. Pour les trois routines MAD, le patch 003 reprend la migration 006. Cela décrit la version attendue, pas l’application effective des correctifs sur un serveur. Toutes les procédures inventoriées déclarent SQL SECURITY DEFINER. Les helpers ne sont pas des commandes publiques du service.

| Procédure | Objectif | Source de définition retenue |
|---|---|---|
| hr_assert_permission | Exiger un compte et salarié actifs, le rôle RH, la permission demandée et une attribution valide. | [database/patches/001_fix_hr_assert_permission_collation.sql](../../database/patches/001_fix_hr_assert_permission_collation.sql) |
| hr_create_assignment | Créer une affectation datée sans chevauchement après verrou du salarié et validation des catalogues actifs. | [database/migrations/003_hr_period_operations.sql](../../database/migrations/003_hr_period_operations.sql) |
| hr_close_assignment | Clôturer une affectation une seule fois sans modifier son identité ni ses bornes initiales. | [database/migrations/003_hr_period_operations.sql](../../database/migrations/003_hr_period_operations.sql) |
| hr_create_contract | Créer un contrat administratif cohérent et non chevauchant pour un salarié actif. | [database/migrations/003_hr_period_operations.sql](../../database/migrations/003_hr_period_operations.sql) |
| hr_close_contract | Clôturer un contrat sans suppression ; la garde ec_salary_coverage protège les conditions approuvées. | [database/migrations/003_hr_period_operations.sql](../../database/migrations/003_hr_period_operations.sql) |
| compensation_assert_permission | Exiger identité active, rôle et permission, sans cumul RH/Finance au niveau personne. | [database/migrations/005_compensation_operations.sql](../../database/migrations/005_compensation_operations.sql) |
| compensation_check_period | Déterminer initial/revision, contrôler couverture du contrat, progression temporelle et absence de salaire UM bloquant. | [database/patches/003_mad_compensation_routines.sql](../../database/patches/003_mad_compensation_routines.sql) |
| compensation_submit | Créer demande MAD et événement submitted atomiquement, à partir du contrat verrouillé. | [database/patches/003_mad_compensation_routines.sql](../../database/patches/003_mad_compensation_routines.sql) |
| compensation_decide | Décider indépendamment une demande une seule fois ; une approbation ajoute une salary_condition MAD et l’événement. | [database/patches/003_mad_compensation_routines.sql](../../database/patches/003_mad_compensation_routines.sql) |
| payroll_assert | Assertion RBAC de référence : activité, permission, rôle et incompatibilités opérationnelles sous lectures courantes. | [database/migrations/008_payroll_operations.sql](../../database/migrations/008_payroll_operations.sql) |
| payroll_period_create | Créer un mois unique avec plafonds explicites et motif Finance. | [database/migrations/008_payroll_operations.sql](../../database/migrations/008_payroll_operations.sql) |
| payroll_input_submit | Soumettre un ajustement ou une suspension dans le mois, avant gel par approbation. | [database/migrations/008_payroll_operations.sql](../../database/migrations/008_payroll_operations.sql) |
| payroll_input_decide | Décider un élément indépendamment ; contrôler plafonds cumulés, couverture et chevauchements des suspensions. | [database/migrations/008_payroll_operations.sql](../../database/migrations/008_payroll_operations.sql) |
| payroll_build | Construire le calendrier approuvé, les totaux et le JSON de preuve ; refuser attente, manque de salaire ou net invalide. | [database/migrations/008_payroll_operations.sql](../../database/migrations/008_payroll_operations.sql) |
| payroll_calculate | Préparer une nouvelle version immuable de bulletin et son empreinte de sources. | [database/migrations/008_payroll_operations.sql](../../database/migrations/008_payroll_operations.sql) |
| payslip_transition | Vérifier, décider puis publier selon états, indépendance, dernière version et fraîcheur des sources. | [database/migrations/008_payroll_operations.sql](../../database/migrations/008_payroll_operations.sql) |
| payroll_read_assert | Déterminer accès personnel ou personnel habilité, puis réutiliser payroll_assert. | [database/migrations/008_payroll_operations.sql](../../database/migrations/008_payroll_operations.sql) |
| payroll_overview | Fournir mois, salariés de sélection, éléments et calculs avec filtrage personnel des bulletins publiés. | [database/migrations/008_payroll_operations.sql](../../database/migrations/008_payroll_operations.sql) |
| payslip_detail | Fournir bulletin, événements et versions ; accès personnel limité à ses bulletins publiés. | [database/migrations/008_payroll_operations.sql](../../database/migrations/008_payroll_operations.sql) |
| settlement_command | Traiter corrections, transitions, paiement du solde et restitution par une commande transactionnelle à version attendue. | [database/migrations/010_settlement_operations.sql](../../database/migrations/010_settlement_operations.sql) |
| settlement_detail | Lire de façon cohérente le net effectif, le solde et les historiques accessibles de règlement. | [database/migrations/010_settlement_operations.sql](../../database/migrations/010_settlement_operations.sql) |
| iam_overview | Lire les comptes sans empreinte, les rôles et les attributions avec permission Admin/Audit. | [database/migrations/011_iam_operations.sql](../../database/migrations/011_iam_operations.sql) |
| iam_grant | Octroyer un rôle à une autre personne active sans doublon ni cumul opérationnel, y compris futur. | [database/migrations/011_iam_operations.sql](../../database/migrations/011_iam_operations.sql) |
| iam_revoke | Révoquer une attribution d’autrui une seule fois en conservant toutes les données d’octroi. | [database/migrations/011_iam_operations.sql](../../database/migrations/011_iam_operations.sql) |

## Procédure `hr_assert_permission`

**Source :** [database/patches/001_fix_hr_assert_permission_collation.sql](../../database/patches/001_fix_hr_assert_permission_collation.sql). **DEFINER déclaré :** `'hr_module_owner'@'localhost'`.

**Objectif :** Exiger un compte et salarié actifs, le rôle RH, la permission demandée et une attribution valide.

### Paramètres et modes

```sql
hr_assert_permission(
    IN p_actor BIGINT UNSIGNED,
    IN p_permission VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs
)
```

**Tables directement référencées :** employees, accounts, roles, permissions, role_permissions, role_assignments.

**Appels imbriqués :** Aucun.

**Permissions métier visibles :** Paramètre dynamique ou assertion héritée de l’appelant ; voir définition. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** aucune ouverture autonome ; helper/lecture exécuté dans le contexte de son appelant. Pas de clause de verrouillage explicite directe dans le corps ; les helpers peuvent en prendre.

**Effets persistants directs :** Aucune écriture de table directe.

**Erreurs SIGNAL explicites :** `HR_FORBIDDEN`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER = 'hr_module_owner'@'localhost' PROCEDURE secure_payroll.hr_assert_permission(
    IN p_actor BIGINT UNSIGNED,
    IN p_permission VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs
)
SQL SECURITY DEFINER
READS SQL DATA
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM accounts a JOIN employees e ON e.id=a.employee_id
        JOIN role_assignments ra ON ra.account_id=a.id JOIN roles r ON r.id=ra.role_id
        JOIN role_permissions rp ON rp.role_id=r.id JOIN permissions p ON p.id=rp.permission_id
        WHERE a.id=p_actor AND a.disabled_at IS NULL AND e.archived_at IS NULL
        AND r.code='hr_manager' AND p.code=p_permission AND ra.valid_from <= UTC_TIMESTAMP(6)
        AND (ra.expires_at IS NULL OR ra.expires_at > UTC_TIMESTAMP(6))
        AND (ra.revoked_at IS NULL OR ra.revoked_at > UTC_TIMESTAMP(6))
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='HR_FORBIDDEN';
    END IF;
END$$
```

## Procédure `hr_create_assignment`

**Source :** [database/migrations/003_hr_period_operations.sql](../../database/migrations/003_hr_period_operations.sql). **DEFINER déclaré :** `'hr_module_owner'@'localhost'`.

**Objectif :** Créer une affectation datée sans chevauchement après verrou du salarié et validation des catalogues actifs.

### Paramètres et modes

```sql
hr_create_assignment(IN p_employee BIGINT UNSIGNED, IN p_department BIGINT UNSIGNED, IN p_position BIGINT UNSIGNED,
    IN p_start DATE, IN p_end DATE, IN p_actor BIGINT UNSIGNED)
```

**Tables directement référencées :** employees, departments, positions, employee_assignments.

**Appels imbriqués :** hr_assert_permission.

**Permissions métier visibles :** assignments.create. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** transaction explicite avec COMMIT ; isolation courante de la session non remplacée dans cette routine. Handler SQLEXCEPTION : ROLLBACK puis RESIGNAL. Verrou(s) FOR UPDATE et/ou FOR SHARE présent(s).

**Effets persistants directs :** INSERT dans employee_assignments. 

**Erreurs SIGNAL explicites :** `HR_DATES`, `HR_EMPLOYEE`, `HR_OVERLAP`, `HR_REFERENCE`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER = 'hr_module_owner'@'localhost' PROCEDURE hr_create_assignment(IN p_employee BIGINT UNSIGNED, IN p_department BIGINT UNSIGNED, IN p_position BIGINT UNSIGNED,
    IN p_start DATE, IN p_end DATE, IN p_actor BIGINT UNSIGNED)
SQL SECURITY DEFINER
MODIFIES SQL DATA
BEGIN
    DECLARE v_employee BIGINT UNSIGNED DEFAULT NULL;
    DECLARE v_conflict BIGINT UNSIGNED DEFAULT NULL;
    DECLARE v_created BIGINT UNSIGNED;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
    START TRANSACTION;
    CALL hr_assert_permission(p_actor, 'assignments.create');
    IF p_start IS NULL OR p_start < '1900-01-01' OR (p_end IS NOT NULL AND p_end < p_start) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='HR_DATES';
    END IF;
    BEGIN
        DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_employee=NULL;
        SELECT id INTO v_employee FROM employees WHERE id=p_employee AND archived_at IS NULL FOR UPDATE;
    END;
    IF v_employee IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='HR_EMPLOYEE';
    END IF;
    BEGIN
        DECLARE v_department BIGINT UNSIGNED DEFAULT NULL;
        DECLARE v_position BIGINT UNSIGNED DEFAULT NULL;
        DECLARE CONTINUE HANDLER FOR NOT FOUND BEGIN END;
        SELECT id INTO v_department FROM departments WHERE id=p_department AND archived_at IS NULL FOR SHARE;
        SELECT id INTO v_position FROM positions WHERE id=p_position AND archived_at IS NULL FOR SHARE;
        IF v_department IS NULL OR v_position IS NULL THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='HR_REFERENCE';
        END IF;
    END;
    
    BEGIN
        DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_conflict=NULL;
        SELECT id INTO v_conflict FROM employee_assignments
        WHERE employee_id=p_employee AND starts_on <= COALESCE(p_end,'9999-12-31')
        AND (effective_ends_on IS NULL OR effective_ends_on >= p_start)
        ORDER BY starts_on LIMIT 1 FOR UPDATE;
    END;
    IF v_conflict IS NOT NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='HR_OVERLAP';
    END IF;
    INSERT INTO employee_assignments (employee_id,department_id,position_id,starts_on,ends_on,created_by,created_at)
    VALUES (p_employee,p_department,p_position,p_start,p_end,p_actor,UTC_TIMESTAMP(6));
    SET v_created=LAST_INSERT_ID();
    COMMIT;
    SELECT v_created AS id;
END$$
```

## Procédure `hr_close_assignment`

**Source :** [database/migrations/003_hr_period_operations.sql](../../database/migrations/003_hr_period_operations.sql). **DEFINER déclaré :** `'hr_module_owner'@'localhost'`.

**Objectif :** Clôturer une affectation une seule fois sans modifier son identité ni ses bornes initiales.

### Paramètres et modes

```sql
hr_close_assignment(IN p_id BIGINT UNSIGNED, IN p_end DATE, IN p_actor BIGINT UNSIGNED)
```

**Tables directement référencées :** employees, employee_assignments.

**Appels imbriqués :** hr_assert_permission.

**Permissions métier visibles :** assignments.close. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** transaction explicite avec COMMIT ; isolation courante de la session non remplacée dans cette routine. Handler SQLEXCEPTION : ROLLBACK puis RESIGNAL. Verrou(s) FOR UPDATE et/ou FOR SHARE présent(s).

**Effets persistants directs :** UPDATE dans employee_assignments.

**Erreurs SIGNAL explicites :** `HR_ALREADY_CLOSED`, `HR_DATES`, `HR_NOT_FOUND`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER = 'hr_module_owner'@'localhost' PROCEDURE hr_close_assignment(IN p_id BIGINT UNSIGNED, IN p_end DATE, IN p_actor BIGINT UNSIGNED)
SQL SECURITY DEFINER
MODIFIES SQL DATA
BEGIN
    DECLARE v_employee BIGINT UNSIGNED DEFAULT NULL;
    DECLARE v_parent BIGINT UNSIGNED DEFAULT NULL;
    DECLARE v_start DATE;
    DECLARE v_end DATE;
    DECLARE v_closed DATE;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
    START TRANSACTION;
    CALL hr_assert_permission(p_actor, 'assignments.close');
    
    BEGIN
        DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_employee=NULL;
        SELECT employee_id INTO v_employee FROM employee_assignments WHERE id=p_id;
    END;
    IF v_employee IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='HR_NOT_FOUND';
    END IF;
    SELECT id INTO v_parent FROM employees WHERE id=v_employee FOR UPDATE;
    
    SELECT starts_on,ends_on,closed_on INTO v_start,v_end,v_closed
        FROM employee_assignments WHERE id=p_id FOR UPDATE;
    IF v_closed IS NOT NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='HR_ALREADY_CLOSED';
    END IF;
    IF p_end IS NULL OR p_end < v_start OR (v_end IS NOT NULL AND p_end > v_end) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='HR_DATES';
    END IF;
    UPDATE employee_assignments SET closed_on=p_end,closed_at=UTC_TIMESTAMP(6),closed_by=p_actor WHERE id=p_id;
    COMMIT;
END$$
```

## Procédure `hr_create_contract`

**Source :** [database/migrations/003_hr_period_operations.sql](../../database/migrations/003_hr_period_operations.sql). **DEFINER déclaré :** `'hr_module_owner'@'localhost'`.

**Objectif :** Créer un contrat administratif cohérent et non chevauchant pour un salarié actif.

### Paramètres et modes

```sql
hr_create_contract(IN p_employee BIGINT UNSIGNED, IN p_reference VARCHAR(64), IN p_type VARCHAR(16),
    IN p_start DATE, IN p_end DATE, IN p_actor BIGINT UNSIGNED)
```

**Tables directement référencées :** employees, employment_contracts.

**Appels imbriqués :** hr_assert_permission.

**Permissions métier visibles :** contracts.create. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** transaction explicite avec COMMIT ; isolation courante de la session non remplacée dans cette routine. Handler SQLEXCEPTION : ROLLBACK puis RESIGNAL. Verrou(s) FOR UPDATE et/ou FOR SHARE présent(s).

**Effets persistants directs :** INSERT dans employment_contracts. 

**Erreurs SIGNAL explicites :** `HR_CONTRACT_TYPE`, `HR_DATES`, `HR_EMPLOYEE`, `HR_OVERLAP`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER = 'hr_module_owner'@'localhost' PROCEDURE hr_create_contract(IN p_employee BIGINT UNSIGNED, IN p_reference VARCHAR(64), IN p_type VARCHAR(16),
    IN p_start DATE, IN p_end DATE, IN p_actor BIGINT UNSIGNED)
SQL SECURITY DEFINER
MODIFIES SQL DATA
BEGIN
    DECLARE v_employee BIGINT UNSIGNED DEFAULT NULL;
    DECLARE v_conflict BIGINT UNSIGNED DEFAULT NULL;
    DECLARE v_created BIGINT UNSIGNED;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
    START TRANSACTION;
    CALL hr_assert_permission(p_actor, 'contracts.create');
    IF p_start IS NULL OR p_start < '1900-01-01' OR (p_end IS NOT NULL AND p_end < p_start) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='HR_DATES';
    END IF;
    BEGIN
        DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_employee=NULL;
        SELECT id INTO v_employee FROM employees WHERE id=p_employee AND archived_at IS NULL FOR UPDATE;
    END;
    IF v_employee IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='HR_EMPLOYEE';
    END IF;
    IF p_type IS NULL OR p_type NOT IN ('permanent','fixed_term','internship')
        OR (p_type='permanent' AND p_end IS NOT NULL)
        OR (p_type IN ('fixed_term','internship') AND p_end IS NULL)
        OR p_reference IS NULL OR CHAR_LENGTH(TRIM(p_reference))=0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='HR_CONTRACT_TYPE';
    END IF;
    
    BEGIN
        DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_conflict=NULL;
        SELECT id INTO v_conflict FROM employment_contracts
        WHERE employee_id=p_employee AND starts_on <= COALESCE(p_end,'9999-12-31')
        AND (effective_ends_on IS NULL OR effective_ends_on >= p_start)
        ORDER BY starts_on LIMIT 1 FOR UPDATE;
    END;
    IF v_conflict IS NOT NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='HR_OVERLAP';
    END IF;
    INSERT INTO employment_contracts (employee_id,reference,contract_type,starts_on,ends_on,created_by,created_at)
    VALUES (p_employee,p_reference,p_type,p_start,p_end,p_actor,UTC_TIMESTAMP(6));
    SET v_created=LAST_INSERT_ID();
    COMMIT;
    SELECT v_created AS id;
END$$
```

## Procédure `hr_close_contract`

**Source :** [database/migrations/003_hr_period_operations.sql](../../database/migrations/003_hr_period_operations.sql). **DEFINER déclaré :** `'hr_module_owner'@'localhost'`.

**Objectif :** Clôturer un contrat sans suppression ; la garde ec_salary_coverage protège les conditions approuvées.

### Paramètres et modes

```sql
hr_close_contract(IN p_id BIGINT UNSIGNED, IN p_end DATE, IN p_actor BIGINT UNSIGNED)
```

**Tables directement référencées :** employees, employment_contracts.

**Appels imbriqués :** hr_assert_permission.

**Permissions métier visibles :** contracts.close. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** transaction explicite avec COMMIT ; isolation courante de la session non remplacée dans cette routine. Handler SQLEXCEPTION : ROLLBACK puis RESIGNAL. Verrou(s) FOR UPDATE et/ou FOR SHARE présent(s).

**Effets persistants directs :** UPDATE dans employment_contracts.

**Erreurs SIGNAL explicites :** `HR_ALREADY_CLOSED`, `HR_DATES`, `HR_NOT_FOUND`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER = 'hr_module_owner'@'localhost' PROCEDURE hr_close_contract(IN p_id BIGINT UNSIGNED, IN p_end DATE, IN p_actor BIGINT UNSIGNED)
SQL SECURITY DEFINER
MODIFIES SQL DATA
BEGIN
    DECLARE v_employee BIGINT UNSIGNED DEFAULT NULL;
    DECLARE v_parent BIGINT UNSIGNED DEFAULT NULL;
    DECLARE v_start DATE;
    DECLARE v_end DATE;
    DECLARE v_closed DATE;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
    START TRANSACTION;
    CALL hr_assert_permission(p_actor, 'contracts.close');
    
    BEGIN
        DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_employee=NULL;
        SELECT employee_id INTO v_employee FROM employment_contracts WHERE id=p_id;
    END;
    IF v_employee IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='HR_NOT_FOUND';
    END IF;
    SELECT id INTO v_parent FROM employees WHERE id=v_employee FOR UPDATE;
    
    SELECT starts_on,ends_on,closed_on INTO v_start,v_end,v_closed
        FROM employment_contracts WHERE id=p_id FOR UPDATE;
    IF v_closed IS NOT NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='HR_ALREADY_CLOSED';
    END IF;
    IF p_end IS NULL OR p_end < v_start OR (v_end IS NOT NULL AND p_end > v_end) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='HR_DATES';
    END IF;
    UPDATE employment_contracts SET closed_on=p_end,closed_at=UTC_TIMESTAMP(6),closed_by=p_actor WHERE id=p_id;
    COMMIT;
END$$
```

## Procédure `compensation_assert_permission`

**Source :** [database/migrations/005_compensation_operations.sql](../../database/migrations/005_compensation_operations.sql). **DEFINER déclaré :** `'compensation_owner'@'localhost'`.

**Objectif :** Exiger identité active, rôle et permission, sans cumul RH/Finance au niveau personne.

### Paramètres et modes

```sql
compensation_assert_permission(
 IN p_actor BIGINT UNSIGNED,
 IN p_permission VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_role VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 OUT p_person BIGINT UNSIGNED)
```

**Tables directement référencées :** employees, accounts, roles, permissions, role_permissions, role_assignments.

**Appels imbriqués :** Aucun.

**Permissions métier visibles :** Paramètre dynamique ou assertion héritée de l’appelant ; voir définition. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** aucune ouverture autonome ; helper/lecture exécuté dans le contexte de son appelant. Verrou(s) FOR UPDATE et/ou FOR SHARE présent(s).

**Effets persistants directs :** Aucune écriture de table directe.

**Erreurs SIGNAL explicites :** `COMP_FORBIDDEN`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER = 'compensation_owner'@'localhost' PROCEDURE compensation_assert_permission(
 IN p_actor BIGINT UNSIGNED,
 IN p_permission VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_role VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 OUT p_person BIGINT UNSIGNED)
SQL SECURITY DEFINER READS SQL DATA
BEGIN
 DECLARE v_grant BIGINT UNSIGNED DEFAULT NULL;
 DECLARE v_conflict BIGINT UNSIGNED DEFAULT NULL;
 DECLARE CONTINUE HANDLER FOR NOT FOUND BEGIN END;
 SET p_person=NULL;
 SELECT a.employee_id INTO p_person FROM accounts a JOIN employees e ON e.id=a.employee_id
 WHERE a.id=p_actor AND a.disabled_at IS NULL AND e.archived_at IS NULL FOR SHARE;
 
 SELECT ra.account_id INTO v_grant FROM role_assignments ra JOIN roles r ON r.id=ra.role_id
 JOIN role_permissions rp ON rp.role_id=r.id JOIN permissions p ON p.id=rp.permission_id
 WHERE ra.account_id=p_actor AND r.code=p_role AND p.code=p_permission
 AND ra.valid_from<=UTC_TIMESTAMP(6) AND (ra.expires_at IS NULL OR ra.expires_at>UTC_TIMESTAMP(6))
 AND (ra.revoked_at IS NULL OR ra.revoked_at>UTC_TIMESTAMP(6)) LIMIT 1 FOR SHARE;
 
 SELECT a.id INTO v_conflict FROM accounts a JOIN role_assignments ra ON ra.account_id=a.id JOIN roles r ON r.id=ra.role_id
 WHERE a.employee_id=p_person AND r.code IN ('hr_manager','finance_manager') AND r.code<>p_role
 AND ra.valid_from<=UTC_TIMESTAMP(6) AND (ra.expires_at IS NULL OR ra.expires_at>UTC_TIMESTAMP(6))
 AND (ra.revoked_at IS NULL OR ra.revoked_at>UTC_TIMESTAMP(6)) LIMIT 1 FOR SHARE;
 IF p_person IS NULL OR v_grant IS NULL OR v_conflict IS NOT NULL THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_FORBIDDEN';
 END IF;
END$$
```

## Procédure `compensation_check_period`

**Source :** [database/patches/003_mad_compensation_routines.sql](../../database/patches/003_mad_compensation_routines.sql). **DEFINER déclaré :** `'compensation_owner'@'localhost'`.

**Objectif :** Déterminer initial/revision, contrôler couverture du contrat, progression temporelle et absence de salaire UM bloquant.

### Paramètres et modes

```sql
compensation_check_period(
 IN p_contract BIGINT UNSIGNED, IN p_employee BIGINT UNSIGNED, IN p_effective DATE,
 OUT p_kind VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs)
```

**Tables directement référencées :** employment_contracts, salary_conditions.

**Appels imbriqués :** Aucun.

**Permissions métier visibles :** Paramètre dynamique ou assertion héritée de l’appelant ; voir définition. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** aucune ouverture autonome ; helper/lecture exécuté dans le contexte de son appelant. Verrou(s) FOR UPDATE et/ou FOR SHARE présent(s).

**Effets persistants directs :** Aucune écriture de table directe.

**Erreurs SIGNAL explicites :** `COMP_COVERAGE`, `COMP_CURRENCY_REVIEW`, `COMP_EFFECTIVE_DATE`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER = 'compensation_owner'@'localhost' PROCEDURE compensation_check_period(
 IN p_contract BIGINT UNSIGNED, IN p_employee BIGINT UNSIGNED, IN p_effective DATE,
 OUT p_kind VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs)
SQL SECURITY DEFINER READS SQL DATA
BEGIN
 DECLARE v_start DATE DEFAULT NULL;
 DECLARE v_end DATE;
 DECLARE v_latest DATE DEFAULT NULL;
 DECLARE v_currency CHAR(3) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs;
 BEGIN
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_start=NULL;
  SELECT starts_on,effective_ends_on INTO v_start,v_end FROM employment_contracts
  WHERE id=p_contract AND employee_id=p_employee FOR SHARE;
 END;
 IF v_start IS NULL OR p_effective IS NULL OR p_effective<v_start OR (v_end IS NOT NULL AND p_effective>v_end) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_COVERAGE';
 END IF;
 BEGIN
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_latest=NULL;
  SELECT effective_on,currency INTO v_latest,v_currency FROM salary_conditions WHERE contract_id=p_contract
  ORDER BY effective_on DESC LIMIT 1 FOR SHARE;
 END;
 IF v_latest IS NOT NULL AND v_currency<>'MAD' THEN
  
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_CURRENCY_REVIEW';
 END IF;
 SET p_kind=IF(v_latest IS NULL,'initial','revision');
 IF (v_latest IS NULL AND p_effective<>v_start)
 OR (v_latest IS NOT NULL AND (DAYOFMONTH(p_effective)<>1 OR p_effective<=v_latest)) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_EFFECTIVE_DATE';
 END IF;
END$$
```

## Procédure `compensation_submit`

**Source :** [database/patches/003_mad_compensation_routines.sql](../../database/patches/003_mad_compensation_routines.sql). **DEFINER déclaré :** `'compensation_owner'@'localhost'`.

**Objectif :** Créer demande MAD et événement submitted atomiquement, à partir du contrat verrouillé.

### Paramètres et modes

```sql
compensation_submit(
 IN p_employee BIGINT UNSIGNED, IN p_contract BIGINT UNSIGNED, IN p_amount DECIMAL(12,2),
 IN p_effective DATE, IN p_justification VARCHAR(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_actor BIGINT UNSIGNED)
```

**Tables directement référencées :** employees, compensation_requests, compensation_history.

**Appels imbriqués :** compensation_assert_permission, compensation_check_period.

**Permissions métier visibles :** compensation.submit. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** transaction explicite avec COMMIT ; isolation courante de la session non remplacée dans cette routine. Handler SQLEXCEPTION : ROLLBACK puis RESIGNAL. Verrou(s) FOR UPDATE et/ou FOR SHARE présent(s).

**Effets persistants directs :** INSERT dans compensation_history, compensation_requests. 

**Erreurs SIGNAL explicites :** `COMP_INVALID`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER = 'compensation_owner'@'localhost' PROCEDURE compensation_submit(
 IN p_employee BIGINT UNSIGNED, IN p_contract BIGINT UNSIGNED, IN p_amount DECIMAL(12,2),
 IN p_effective DATE, IN p_justification VARCHAR(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_actor BIGINT UNSIGNED)
SQL SECURITY DEFINER MODIFIES SQL DATA
BEGIN
 DECLARE v_parent BIGINT UNSIGNED DEFAULT NULL;
 DECLARE v_person BIGINT UNSIGNED;
 DECLARE v_kind VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs;
 DECLARE v_id BIGINT UNSIGNED;
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 START TRANSACTION;
 
 SELECT id INTO v_parent FROM employees WHERE id=p_employee AND archived_at IS NULL FOR UPDATE;
 CALL compensation_assert_permission(p_actor,'compensation.submit','hr_manager',v_person);
 IF v_parent IS NULL OR p_amount IS NULL OR p_amount<=0 OR p_justification IS NULL
 OR CHAR_LENGTH(TRIM(p_justification))=0 THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_INVALID';
 END IF;
 CALL compensation_check_period(p_contract,p_employee,p_effective,v_kind);
 INSERT INTO compensation_requests(employee_id,contract_id,request_kind,monthly_amount,currency,
  effective_on,justification,requested_by,requester_employee_id,requested_at)
 VALUES(p_employee,p_contract,v_kind,p_amount,'MAD',p_effective,TRIM(p_justification),p_actor,v_person,UTC_TIMESTAMP(6));
 SET v_id=LAST_INSERT_ID();
 INSERT INTO compensation_history(request_id,event_type,actor_id,occurred_at)
 VALUES(v_id,'submitted',p_actor,UTC_TIMESTAMP(6));
 COMMIT;
 SELECT v_id AS id;
END$$
```

## Procédure `compensation_decide`

**Source :** [database/patches/003_mad_compensation_routines.sql](../../database/patches/003_mad_compensation_routines.sql). **DEFINER déclaré :** `'compensation_owner'@'localhost'`.

**Objectif :** Décider indépendamment une demande une seule fois ; une approbation ajoute une salary_condition MAD et l’événement.

### Paramètres et modes

```sql
compensation_decide(
 IN p_request BIGINT UNSIGNED,
 IN p_decision VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_reason VARCHAR(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_actor BIGINT UNSIGNED)
```

**Tables directement référencées :** employees, compensation_requests, compensation_decisions, salary_conditions, compensation_history.

**Appels imbriqués :** compensation_assert_permission, compensation_check_period.

**Permissions métier visibles :** compensation.decide. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** transaction explicite avec COMMIT ; isolation courante de la session non remplacée dans cette routine. Handler SQLEXCEPTION : ROLLBACK puis RESIGNAL. Verrou(s) FOR UPDATE et/ou FOR SHARE présent(s).

**Effets persistants directs :** INSERT dans compensation_decisions, compensation_history, salary_conditions. 

**Erreurs SIGNAL explicites :** `COMP_ALREADY_DECIDED`, `COMP_CURRENCY_REVIEW`, `COMP_INVALID`, `COMP_NOT_FOUND`, `COMP_SELF_APPROVAL`, `COMP_STALE`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER = 'compensation_owner'@'localhost' PROCEDURE compensation_decide(
 IN p_request BIGINT UNSIGNED,
 IN p_decision VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_reason VARCHAR(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_actor BIGINT UNSIGNED)
SQL SECURITY DEFINER MODIFIES SQL DATA
BEGIN
 DECLARE v_employee BIGINT UNSIGNED DEFAULT NULL;
 DECLARE v_parent BIGINT UNSIGNED DEFAULT NULL;
 DECLARE v_contract BIGINT UNSIGNED;
 DECLARE v_requester BIGINT UNSIGNED;
 DECLARE v_person BIGINT UNSIGNED;
 DECLARE v_amount DECIMAL(12,2);
 DECLARE v_currency CHAR(3) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs;
 DECLARE v_effective DATE;
 DECLARE v_kind VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs;
 DECLARE v_current_kind VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs;
 DECLARE v_existing BIGINT UNSIGNED DEFAULT NULL;
 DECLARE v_decision BIGINT UNSIGNED;
 DECLARE v_archived DATETIME(6);
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 START TRANSACTION;
 SELECT employee_id INTO v_employee FROM compensation_requests WHERE id=p_request;
 IF v_employee IS NULL THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_NOT_FOUND';
 END IF;
 SELECT id,archived_at INTO v_parent,v_archived FROM employees WHERE id=v_employee FOR UPDATE;
 CALL compensation_assert_permission(p_actor,'compensation.decide','finance_manager',v_person);
 IF v_parent IS NULL OR (p_decision='approved' AND v_archived IS NOT NULL) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_INVALID';
 END IF;
 SELECT contract_id,requester_employee_id,monthly_amount,effective_on,request_kind,currency
 INTO v_contract,v_requester,v_amount,v_effective,v_kind,v_currency FROM compensation_requests WHERE id=p_request FOR SHARE;
 IF v_person=v_requester OR v_person=v_employee THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_SELF_APPROVAL';
 END IF;
 IF p_decision IS NULL OR p_decision NOT IN ('approved','rejected') OR p_reason IS NULL OR CHAR_LENGTH(TRIM(p_reason))=0 THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_INVALID';
 END IF;
 BEGIN
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_existing=NULL;
  SELECT id INTO v_existing FROM compensation_decisions WHERE request_id=p_request FOR SHARE;
 END;
 IF v_existing IS NOT NULL THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_ALREADY_DECIDED';
 END IF;
 IF p_decision='approved' THEN
  IF v_currency<>'MAD' THEN
   SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_CURRENCY_REVIEW';
  END IF;
  CALL compensation_check_period(v_contract,v_employee,v_effective,v_current_kind);
  IF v_current_kind<>v_kind THEN
   SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_STALE';
  END IF;
 END IF;
 INSERT INTO compensation_decisions(request_id,decision,reason,decided_by,approver_employee_id,decided_at)
 VALUES(p_request,p_decision,TRIM(p_reason),p_actor,v_person,UTC_TIMESTAMP(6));
 SET v_decision=LAST_INSERT_ID();
 IF p_decision='approved' THEN
  INSERT INTO salary_conditions(employee_id,contract_id,request_id,decision_id,monthly_amount,currency,effective_on,recorded_at)
  VALUES(v_employee,v_contract,p_request,v_decision,v_amount,v_currency,v_effective,UTC_TIMESTAMP(6));
 END IF;
 INSERT INTO compensation_history(request_id,event_type,actor_id,occurred_at)
 VALUES(p_request,p_decision,p_actor,UTC_TIMESTAMP(6));
 COMMIT;
 SELECT v_decision AS id;
END$$
```

## Procédure `payroll_assert`

**Source :** [database/migrations/008_payroll_operations.sql](../../database/migrations/008_payroll_operations.sql). **DEFINER déclaré :** `'payroll_owner'@'localhost'`.

**Objectif :** Assertion RBAC de référence : activité, permission, rôle et incompatibilités opérationnelles sous lectures courantes.

### Paramètres et modes

```sql
payroll_assert(
 IN p_actor BIGINT UNSIGNED,
 IN p_permission VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_role VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 OUT p_person BIGINT UNSIGNED)
```

**Tables directement référencées :** employees, accounts, roles, permissions, role_permissions, role_assignments.

**Appels imbriqués :** Aucun.

**Permissions métier visibles :** Paramètre dynamique ou assertion héritée de l’appelant ; voir définition. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** aucune ouverture autonome ; helper/lecture exécuté dans le contexte de son appelant. Verrou(s) FOR UPDATE et/ou FOR SHARE présent(s).

**Effets persistants directs :** Aucune écriture de table directe.

**Erreurs SIGNAL explicites :** `PAY_FORBIDDEN`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER='payroll_owner'@'localhost' PROCEDURE payroll_assert(
 IN p_actor BIGINT UNSIGNED,
 IN p_permission VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_role VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 OUT p_person BIGINT UNSIGNED)
SQL SECURITY DEFINER READS SQL DATA
BEGIN
 DECLARE v_grant BIGINT UNSIGNED DEFAULT NULL;
 DECLARE v_conflict BIGINT UNSIGNED DEFAULT NULL;
 DECLARE CONTINUE HANDLER FOR NOT FOUND BEGIN END;
 SET p_person=NULL;
 SELECT a.employee_id INTO p_person FROM accounts a JOIN employees e ON e.id=a.employee_id
 WHERE a.id=p_actor AND a.disabled_at IS NULL AND e.archived_at IS NULL FOR SHARE;
 SELECT ra.account_id INTO v_grant FROM role_assignments ra JOIN roles r ON r.id=ra.role_id
 JOIN role_permissions rp ON rp.role_id=r.id JOIN permissions p ON p.id=rp.permission_id
 WHERE ra.account_id=p_actor AND r.code=p_role AND p.code=p_permission
 AND ra.valid_from<=UTC_TIMESTAMP(6) AND (ra.expires_at IS NULL OR ra.expires_at>UTC_TIMESTAMP(6))
 AND (ra.revoked_at IS NULL OR ra.revoked_at>UTC_TIMESTAMP(6)) LIMIT 1 FOR SHARE;
 IF p_role<>'employee' THEN
  SELECT a.id INTO v_conflict FROM accounts a JOIN role_assignments ra ON ra.account_id=a.id
  JOIN roles r ON r.id=ra.role_id WHERE a.employee_id=p_person
  AND r.code IN ('hr_manager','payroll_manager','finance_manager','application_administrator','security_auditor')
  AND r.code<>p_role AND ra.valid_from<=UTC_TIMESTAMP(6)
  AND (ra.expires_at IS NULL OR ra.expires_at>UTC_TIMESTAMP(6))
  AND (ra.revoked_at IS NULL OR ra.revoked_at>UTC_TIMESTAMP(6)) LIMIT 1 FOR SHARE;
 END IF;
 IF p_person IS NULL OR v_grant IS NULL OR v_conflict IS NOT NULL THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_FORBIDDEN';
 END IF;
END$$
```

## Procédure `payroll_period_create`

**Source :** [database/migrations/008_payroll_operations.sql](../../database/migrations/008_payroll_operations.sql). **DEFINER déclaré :** `'payroll_owner'@'localhost'`.

**Objectif :** Créer un mois unique avec plafonds explicites et motif Finance.

### Paramètres et modes

```sql
payroll_period_create(
 IN p_month DATE, IN p_bonus_cap DECIMAL(12,2), IN p_deduction_cap DECIMAL(12,2),
 IN p_reason VARCHAR(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_actor BIGINT UNSIGNED)
```

**Tables directement référencées :** payroll_periods.

**Appels imbriqués :** payroll_assert.

**Permissions métier visibles :** payroll.period.create. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** transaction explicite avec COMMIT ; isolation courante de la session non remplacée dans cette routine. Handler SQLEXCEPTION : ROLLBACK puis RESIGNAL. Pas de clause de verrouillage explicite directe dans le corps ; les helpers peuvent en prendre.

**Effets persistants directs :** INSERT dans payroll_periods. 

**Erreurs SIGNAL explicites :** `PAY_INVALID`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER='payroll_owner'@'localhost' PROCEDURE payroll_period_create(
 IN p_month DATE, IN p_bonus_cap DECIMAL(12,2), IN p_deduction_cap DECIMAL(12,2),
 IN p_reason VARCHAR(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_actor BIGINT UNSIGNED)
SQL SECURITY DEFINER MODIFIES SQL DATA
BEGIN
 DECLARE v_person BIGINT UNSIGNED;
 DECLARE v_id BIGINT UNSIGNED;
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 START TRANSACTION;
 CALL payroll_assert(p_actor,'payroll.period.create','finance_manager',v_person);
 IF p_month IS NULL OR p_month<'1900-01-01' OR DAYOFMONTH(p_month)<>1
 OR p_bonus_cap IS NULL OR p_bonus_cap<0 OR p_deduction_cap IS NULL OR p_deduction_cap<0
 OR p_reason IS NULL OR CHAR_LENGTH(TRIM(p_reason))=0 THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_INVALID';
 END IF;
 INSERT INTO payroll_periods(month_start,bonus_cap,deduction_cap,reason,created_by,creator_employee_id)
 VALUES(p_month,p_bonus_cap,p_deduction_cap,TRIM(p_reason),p_actor,v_person);
 SET v_id=LAST_INSERT_ID();
 COMMIT;
 SELECT v_id AS id;
END$$
```

## Procédure `payroll_input_submit`

**Source :** [database/migrations/008_payroll_operations.sql](../../database/migrations/008_payroll_operations.sql). **DEFINER déclaré :** `'payroll_owner'@'localhost'`.

**Objectif :** Soumettre un ajustement ou une suspension dans le mois, avant gel par approbation.

### Paramètres et modes

```sql
payroll_input_submit(
 IN p_period BIGINT UNSIGNED, IN p_employee BIGINT UNSIGNED,
 IN p_kind VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_amount DECIMAL(12,2), IN p_start DATE, IN p_end DATE,
 IN p_reason VARCHAR(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_actor BIGINT UNSIGNED)
```

**Tables directement référencées :** employees, payroll_periods, payroll_inputs, payroll_approvals.

**Appels imbriqués :** payroll_assert.

**Permissions métier visibles :** payroll.input.submit. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** transaction explicite avec COMMIT ; isolation READ COMMITTED explicitement demandée. Handler SQLEXCEPTION : ROLLBACK puis RESIGNAL. Verrou(s) FOR UPDATE et/ou FOR SHARE présent(s).

**Effets persistants directs :** INSERT dans payroll_inputs. 

**Erreurs SIGNAL explicites :** `PAY_FROZEN`, `PAY_INVALID`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER='payroll_owner'@'localhost' PROCEDURE payroll_input_submit(
 IN p_period BIGINT UNSIGNED, IN p_employee BIGINT UNSIGNED,
 IN p_kind VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_amount DECIMAL(12,2), IN p_start DATE, IN p_end DATE,
 IN p_reason VARCHAR(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_actor BIGINT UNSIGNED)
SQL SECURITY DEFINER MODIFIES SQL DATA
BEGIN
 DECLARE v_person BIGINT UNSIGNED;
 DECLARE v_parent BIGINT UNSIGNED DEFAULT NULL;
 DECLARE v_month DATE DEFAULT NULL;
 DECLARE v_id BIGINT UNSIGNED;
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
 START TRANSACTION;
 SELECT id INTO v_parent FROM employees WHERE id=p_employee AND archived_at IS NULL FOR UPDATE;
 CALL payroll_assert(p_actor,'payroll.input.submit','hr_manager',v_person);
 SELECT month_start INTO v_month FROM payroll_periods WHERE id=p_period;
 IF v_parent IS NULL OR v_month IS NULL OR p_start IS NULL OR p_end IS NULL
 OR p_start<v_month OR p_end>LAST_DAY(v_month) OR p_end<p_start
 OR p_reason IS NULL OR CHAR_LENGTH(TRIM(p_reason))=0 OR p_kind IS NULL OR p_amount IS NULL
 OR NOT ((p_kind IN ('bonus','deduction') AND p_amount>0) OR (p_kind IN ('paid_leave','unpaid_leave') AND p_amount=0)) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_INVALID';
 END IF;
 IF EXISTS(SELECT 1 FROM payroll_approvals WHERE employee_id=p_employee AND period_id=p_period) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_FROZEN';
 END IF;
 INSERT INTO payroll_inputs(period_id,employee_id,kind,amount,starts_on,ends_on,reason,created_by,creator_employee_id)
 VALUES(p_period,p_employee,p_kind,p_amount,p_start,p_end,TRIM(p_reason),p_actor,v_person);
 SET v_id=LAST_INSERT_ID();
 COMMIT;
 SELECT v_id AS id;
END$$
```

## Procédure `payroll_input_decide`

**Source :** [database/migrations/008_payroll_operations.sql](../../database/migrations/008_payroll_operations.sql). **DEFINER déclaré :** `'payroll_owner'@'localhost'`.

**Objectif :** Décider un élément indépendamment ; contrôler plafonds cumulés, couverture et chevauchements des suspensions.

### Paramètres et modes

```sql
payroll_input_decide(
 IN p_input BIGINT UNSIGNED,
 IN p_decision VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_reason VARCHAR(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_actor BIGINT UNSIGNED)
```

**Tables directement référencées :** employees, employment_contracts, payroll_periods, payroll_inputs, payroll_input_decisions, payroll_approvals.

**Appels imbriqués :** payroll_assert.

**Permissions métier visibles :** payroll.input.decide. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** transaction explicite avec COMMIT ; isolation READ COMMITTED explicitement demandée. Handler SQLEXCEPTION : ROLLBACK puis RESIGNAL. Verrou(s) FOR UPDATE et/ou FOR SHARE présent(s).

**Effets persistants directs :** INSERT dans payroll_input_decisions. 

**Erreurs SIGNAL explicites :** `PAY_CAP`, `PAY_COVERAGE`, `PAY_DECIDED`, `PAY_FORBIDDEN`, `PAY_FROZEN`, `PAY_OVERLAP`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER='payroll_owner'@'localhost' PROCEDURE payroll_input_decide(
 IN p_input BIGINT UNSIGNED,
 IN p_decision VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_reason VARCHAR(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_actor BIGINT UNSIGNED)
SQL SECURITY DEFINER MODIFIES SQL DATA
BEGIN
 DECLARE v_employee BIGINT UNSIGNED DEFAULT NULL;
 DECLARE v_period BIGINT UNSIGNED;
 DECLARE v_creator BIGINT UNSIGNED;
 DECLARE v_person BIGINT UNSIGNED;
 DECLARE v_parent BIGINT UNSIGNED;
 DECLARE v_id BIGINT UNSIGNED;
 DECLARE v_bonus DECIMAL(20,2);
 DECLARE v_deduction DECIMAL(20,2);
 DECLARE v_day DATE;
 DECLARE v_end DATE;
 DECLARE v_kind VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs;
 DECLARE v_coverage INT;
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
 START TRANSACTION;
 SELECT employee_id,period_id,creator_employee_id INTO v_employee,v_period,v_creator FROM payroll_inputs WHERE id=p_input;
 SELECT id INTO v_parent FROM employees WHERE id=v_employee AND archived_at IS NULL FOR UPDATE;
 CALL payroll_assert(p_actor,'payroll.input.decide','finance_manager',v_person);
 IF v_employee IS NULL OR v_parent IS NULL OR v_person IN (v_employee,v_creator)
 OR p_decision IS NULL OR p_decision NOT IN ('approved','rejected')
 OR p_reason IS NULL OR CHAR_LENGTH(TRIM(p_reason))=0 THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_FORBIDDEN';
 END IF;
 IF EXISTS(SELECT 1 FROM payroll_input_decisions WHERE input_id=p_input) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_DECIDED';
 END IF;
 IF EXISTS(SELECT 1 FROM payroll_approvals WHERE employee_id=v_employee AND period_id=v_period) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_FROZEN';
 END IF;
 IF p_decision='approved' THEN
  SELECT kind,starts_on,ends_on INTO v_kind,v_day,v_end FROM payroll_inputs WHERE id=p_input;
  IF v_kind IN ('paid_leave','unpaid_leave') THEN
   coverage_loop: LOOP
    SELECT COUNT(*) INTO v_coverage FROM employment_contracts WHERE employee_id=v_employee
     AND starts_on<=v_day AND (effective_ends_on IS NULL OR effective_ends_on>=v_day);
    IF v_coverage<>1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_COVERAGE'; END IF;
    IF v_day=v_end THEN LEAVE coverage_loop; END IF;
    SET v_day=DATE_ADD(v_day,INTERVAL 1 DAY);
   END LOOP;
  END IF;
  SELECT COALESCE(SUM(IF(i.kind='bonus',i.amount,0)),0),COALESCE(SUM(IF(i.kind='deduction',i.amount,0)),0)
   INTO v_bonus,v_deduction FROM payroll_inputs i LEFT JOIN payroll_input_decisions d ON d.input_id=i.id
   WHERE i.employee_id=v_employee AND i.period_id=v_period AND (d.decision='approved' OR i.id=p_input);
  IF EXISTS(SELECT 1 FROM payroll_periods WHERE id=v_period AND (v_bonus>bonus_cap OR v_deduction>deduction_cap)) THEN
   SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_CAP';
  END IF;
  IF EXISTS(SELECT 1 FROM payroll_inputs i JOIN payroll_inputs n ON n.id=p_input
   JOIN payroll_input_decisions d ON d.input_id=i.id AND d.decision='approved'
   WHERE n.kind IN ('paid_leave','unpaid_leave') AND i.kind IN ('paid_leave','unpaid_leave')
   AND i.employee_id=v_employee AND i.period_id=v_period AND i.starts_on<=n.ends_on AND i.ends_on>=n.starts_on) THEN
   SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_OVERLAP';
  END IF;
 END IF;
 INSERT INTO payroll_input_decisions(input_id,decision,reason,decided_by,approver_employee_id)
 VALUES(p_input,p_decision,TRIM(p_reason),p_actor,v_person);
 SET v_id=LAST_INSERT_ID();
 COMMIT;
 SELECT v_id AS id;
END$$
```

## Procédure `payroll_build`

**Source :** [database/migrations/008_payroll_operations.sql](../../database/migrations/008_payroll_operations.sql). **DEFINER déclaré :** `'payroll_owner'@'localhost'`.

**Objectif :** Construire le calendrier approuvé, les totaux et le JSON de preuve ; refuser attente, manque de salaire ou net invalide.

### Paramètres et modes

```sql
payroll_build(
 IN p_period BIGINT UNSIGNED, IN p_employee BIGINT UNSIGNED,
 OUT p_base DECIMAL(12,2), OUT p_bonus DECIMAL(12,2), OUT p_deduction DECIMAL(12,2), OUT p_snapshot JSON)
```

**Tables directement référencées :** employment_contracts, compensation_requests, compensation_decisions, salary_conditions, payroll_periods, payroll_inputs, payroll_input_decisions.

**Appels imbriqués :** Aucun.

**Permissions métier visibles :** Paramètre dynamique ou assertion héritée de l’appelant ; voir définition. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** aucune ouverture autonome ; helper/lecture exécuté dans le contexte de son appelant. Pas de clause de verrouillage explicite directe dans le corps ; les helpers peuvent en prendre.

**Effets persistants directs :** Aucune écriture de table directe.

**Erreurs SIGNAL explicites :** `PAY_CAP`, `PAY_COVERAGE`, `PAY_INVALID`, `PAY_NET`, `PAY_OVERLAP`, `PAY_PENDING`, `PAY_SALARY`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER='payroll_owner'@'localhost' PROCEDURE payroll_build(
 IN p_period BIGINT UNSIGNED, IN p_employee BIGINT UNSIGNED,
 OUT p_base DECIMAL(12,2), OUT p_bonus DECIMAL(12,2), OUT p_deduction DECIMAL(12,2), OUT p_snapshot JSON)
SQL SECURITY DEFINER READS SQL DATA
BEGIN
 DECLARE v_month DATE DEFAULT NULL;
 DECLARE v_day DATE;
 DECLARE v_contract BIGINT UNSIGNED;
 DECLARE v_condition BIGINT UNSIGNED;
 DECLARE v_count INT;
 DECLARE v_days INT DEFAULT 0;
 DECLARE v_amount DECIMAL(12,2);
 DECLARE v_numerator DECIMAL(24,2) DEFAULT 0;
 DECLARE v_currency CHAR(3) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs;
 DECLARE v_bonus_cap DECIMAL(12,2);
 DECLARE v_deduction_cap DECIMAL(12,2);
 DECLARE v_total_bonus DECIMAL(20,2);
 DECLARE v_total_deduction DECIMAL(20,2);
 DECLARE v_unpaid INT;
 DECLARE v_pending INT;
 DECLARE v_input BIGINT UNSIGNED DEFAULT 0;
 DECLARE v_next BIGINT UNSIGNED;
 DECLARE v_inputs JSON;
 DECLARE v_calendar JSON;
 DECLARE v_row JSON;
 DECLARE v_good INT;
 SELECT month_start,bonus_cap,deduction_cap INTO v_month,v_bonus_cap,v_deduction_cap FROM payroll_periods WHERE id=p_period;
 IF v_month IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_INVALID'; END IF;
 SELECT COUNT(*) INTO v_pending FROM payroll_inputs i LEFT JOIN payroll_input_decisions d ON d.input_id=i.id
 WHERE i.period_id=p_period AND i.employee_id=p_employee AND d.id IS NULL;
 IF v_pending>0 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_PENDING'; END IF;
 SET v_day=v_month;
 SET v_calendar=JSON_ARRAY();
 SET v_inputs=JSON_ARRAY();
 calendar_loop: WHILE v_day<=LAST_DAY(v_month) DO
  SELECT COUNT(*),MAX(id) INTO v_count,v_contract FROM employment_contracts
   WHERE employee_id=p_employee AND starts_on<=v_day AND (effective_ends_on IS NULL OR effective_ends_on>=v_day);
  SELECT COUNT(*),COALESCE(SUM(i.kind='unpaid_leave'),0) INTO v_good,v_unpaid FROM payroll_inputs i
   JOIN payroll_input_decisions d ON d.input_id=i.id AND d.decision='approved'
   WHERE i.period_id=p_period AND i.employee_id=p_employee AND i.kind IN ('paid_leave','unpaid_leave')
   AND i.starts_on<=v_day AND i.ends_on>=v_day;
  IF v_count>1 OR v_good>1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_OVERLAP'; END IF;
  IF v_count=0 AND v_good>0 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_COVERAGE'; END IF;
  IF v_count=1 THEN
   SET v_condition=NULL;
   SELECT id,monthly_amount,currency INTO v_condition,v_amount,v_currency FROM salary_conditions
    WHERE contract_id=v_contract AND employee_id=p_employee AND effective_on<=v_day
    ORDER BY effective_on DESC LIMIT 1;
   IF v_condition IS NULL OR v_currency<>'MAD' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_SALARY'; END IF;
   SELECT COUNT(*) INTO v_good FROM salary_conditions s
    JOIN compensation_decisions d ON d.id=s.decision_id AND d.request_id=s.request_id AND d.decision='approved'
     AND d.approver_employee_id<>s.employee_id
    JOIN compensation_requests q ON q.id=s.request_id AND q.employee_id=s.employee_id AND q.contract_id=s.contract_id
     AND q.monthly_amount=s.monthly_amount AND q.currency=s.currency AND q.effective_on=s.effective_on
     AND q.requester_employee_id<>d.approver_employee_id
    WHERE s.id=v_condition;
   IF v_good<>1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_SALARY'; END IF;
   SET v_days=v_days+1;
   IF v_unpaid=0 THEN SET v_numerator=v_numerator+v_amount; END IF;
   SELECT JSON_OBJECT('date',v_day,'contract_id',v_contract,'starts_on',starts_on,'ends_on',effective_ends_on,
     'salary_condition_id',v_condition,'monthly_amount',CAST(v_amount AS CHAR),'paid',IF(v_unpaid=0,1,0)) INTO v_row
    FROM employment_contracts WHERE id=v_contract;
   SET v_calendar=JSON_ARRAY_APPEND(v_calendar,'$',v_row);
  END IF;
  IF v_day=LAST_DAY(v_month) THEN LEAVE calendar_loop; END IF;
  SET v_day=DATE_ADD(v_day,INTERVAL 1 DAY);
 END WHILE;
 IF v_days=0 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_COVERAGE'; END IF;
 SELECT COALESCE(SUM(IF(i.kind='bonus',i.amount,0)),0),COALESCE(SUM(IF(i.kind='deduction',i.amount,0)),0)
  INTO v_total_bonus,v_total_deduction FROM payroll_inputs i JOIN payroll_input_decisions d ON d.input_id=i.id AND d.decision='approved'
  WHERE i.period_id=p_period AND i.employee_id=p_employee;
 IF v_total_bonus>v_bonus_cap OR v_total_deduction>v_deduction_cap THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_CAP'; END IF;
 IF v_total_bonus>9999999999.99 OR v_total_deduction>9999999999.99 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_INVALID'; END IF;
 SET p_base=ROUND(v_numerator/DAYOFMONTH(LAST_DAY(v_month)),2);
 SET p_bonus=v_total_bonus;
 SET p_deduction=v_total_deduction;
 IF p_base+p_bonus>9999999999.99 OR p_deduction>p_base+p_bonus THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_NET'; END IF;
 input_loop: LOOP
  SELECT MIN(i.id) INTO v_next FROM payroll_inputs i JOIN payroll_input_decisions d ON d.input_id=i.id AND d.decision='approved'
   WHERE i.period_id=p_period AND i.employee_id=p_employee AND i.id>v_input;
  IF v_next IS NULL THEN LEAVE input_loop; END IF;
  SELECT JSON_OBJECT('id',i.id,'decision_id',d.id,'kind',i.kind,'amount',CAST(i.amount AS CHAR),
   'starts_on',i.starts_on,'ends_on',i.ends_on) INTO v_row
   FROM payroll_inputs i JOIN payroll_input_decisions d ON d.input_id=i.id WHERE i.id=v_next;
  SET v_inputs=JSON_ARRAY_APPEND(v_inputs,'$',v_row);
  SET v_input=v_next;
 END LOOP;
 SET p_snapshot=JSON_OBJECT('algorithm','calendar-days-v1','month',DATE_FORMAT(v_month,'%Y-%m'),
  'employee_id',p_employee,'currency','MAD','bonus_cap',CAST(v_bonus_cap AS CHAR),
  'deduction_cap',CAST(v_deduction_cap AS CHAR),'days',v_calendar,'inputs',v_inputs);
END$$
```

## Procédure `payroll_calculate`

**Source :** [database/migrations/008_payroll_operations.sql](../../database/migrations/008_payroll_operations.sql). **DEFINER déclaré :** `'payroll_owner'@'localhost'`.

**Objectif :** Préparer une nouvelle version immuable de bulletin et son empreinte de sources.

### Paramètres et modes

```sql
payroll_calculate(
 IN p_period BIGINT UNSIGNED, IN p_employee BIGINT UNSIGNED, IN p_actor BIGINT UNSIGNED)
```

**Tables directement référencées :** employees, payroll_calculations, payroll_approvals.

**Appels imbriqués :** payroll_assert, payroll_build.

**Permissions métier visibles :** payroll.calculate. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** transaction explicite avec COMMIT ; isolation READ COMMITTED explicitement demandée. Handler SQLEXCEPTION : ROLLBACK puis RESIGNAL. Verrou(s) FOR UPDATE et/ou FOR SHARE présent(s).

**Effets persistants directs :** INSERT dans payroll_calculations. 

**Erreurs SIGNAL explicites :** `PAY_FORBIDDEN`, `PAY_FROZEN`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER='payroll_owner'@'localhost' PROCEDURE payroll_calculate(
 IN p_period BIGINT UNSIGNED, IN p_employee BIGINT UNSIGNED, IN p_actor BIGINT UNSIGNED)
SQL SECURITY DEFINER MODIFIES SQL DATA
BEGIN
 DECLARE v_person BIGINT UNSIGNED;
 DECLARE v_parent BIGINT UNSIGNED DEFAULT NULL;
 DECLARE v_version INT UNSIGNED;
 DECLARE v_base DECIMAL(12,2);
 DECLARE v_bonus DECIMAL(12,2);
 DECLARE v_deduction DECIMAL(12,2);
 DECLARE v_snapshot JSON;
 DECLARE v_id BIGINT UNSIGNED;
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
 START TRANSACTION;
 SELECT id INTO v_parent FROM employees WHERE id=p_employee AND archived_at IS NULL FOR UPDATE;
 CALL payroll_assert(p_actor,'payroll.calculate','payroll_manager',v_person);
 IF v_parent IS NULL OR v_person=p_employee THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_FORBIDDEN'; END IF;
 IF EXISTS(SELECT 1 FROM payroll_approvals WHERE period_id=p_period AND employee_id=p_employee) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_FROZEN';
 END IF;
 CALL payroll_build(p_period,p_employee,v_base,v_bonus,v_deduction,v_snapshot);
 SELECT COALESCE(MAX(version_no),0)+1 INTO v_version FROM payroll_calculations WHERE period_id=p_period AND employee_id=p_employee;
 INSERT INTO payroll_calculations(period_id,employee_id,version_no,algorithm,base_amount,bonus_amount,deduction_amount,
  gross_amount,net_amount,snapshot,source_hash,prepared_by,preparer_employee_id)
 VALUES(p_period,p_employee,v_version,'calendar-days-v1',v_base,v_bonus,v_deduction,v_base+v_bonus,v_base+v_bonus-v_deduction,
  v_snapshot,SHA2(CAST(v_snapshot AS CHAR),256),p_actor,v_person);
 SET v_id=LAST_INSERT_ID();
 COMMIT;
 SELECT v_id AS id;
END$$
```

## Procédure `payslip_transition`

**Source :** [database/migrations/008_payroll_operations.sql](../../database/migrations/008_payroll_operations.sql). **DEFINER déclaré :** `'payroll_owner'@'localhost'`.

**Objectif :** Vérifier, décider puis publier selon états, indépendance, dernière version et fraîcheur des sources.

### Paramètres et modes

```sql
payslip_transition(
 IN p_calculation BIGINT UNSIGNED,
 IN p_event VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_reason VARCHAR(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_actor BIGINT UNSIGNED)
```

**Tables directement référencées :** employees, payroll_calculations, payslip_events, payroll_approvals.

**Appels imbriqués :** payroll_assert, payroll_build.

**Permissions métier visibles :** payslip.decide, payslip.publish, payslip.verify. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** transaction explicite avec COMMIT ; isolation READ COMMITTED explicitement demandée. Handler SQLEXCEPTION : ROLLBACK puis RESIGNAL. Verrou(s) FOR UPDATE et/ou FOR SHARE présent(s).

**Effets persistants directs :** INSERT dans payroll_approvals, payslip_events. 

**Erreurs SIGNAL explicites :** `PAY_FORBIDDEN`, `PAY_FROZEN`, `PAY_INVALID`, `PAY_STALE`, `PAY_STATE`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER='payroll_owner'@'localhost' PROCEDURE payslip_transition(
 IN p_calculation BIGINT UNSIGNED,
 IN p_event VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_reason VARCHAR(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_actor BIGINT UNSIGNED)
SQL SECURITY DEFINER MODIFIES SQL DATA
BEGIN
 DECLARE v_employee BIGINT UNSIGNED DEFAULT NULL;
 DECLARE v_period BIGINT UNSIGNED;
 DECLARE v_preparer BIGINT UNSIGNED;
 DECLARE v_person BIGINT UNSIGNED;
 DECLARE v_parent BIGINT UNSIGNED DEFAULT NULL;
 DECLARE v_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin;
 DECLARE v_snapshot JSON;
 DECLARE v_base DECIMAL(12,2);
 DECLARE v_bonus DECIMAL(12,2);
 DECLARE v_deduction DECIMAL(12,2);
 DECLARE v_id BIGINT UNSIGNED;
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
 START TRANSACTION;
 SELECT employee_id,period_id,preparer_employee_id,source_hash INTO v_employee,v_period,v_preparer,v_hash
  FROM payroll_calculations WHERE id=p_calculation;
 SELECT id INTO v_parent FROM employees WHERE id=v_employee AND archived_at IS NULL FOR UPDATE;
 IF p_event IN ('approved','rejected') THEN
  CALL payroll_assert(p_actor,'payslip.decide','finance_manager',v_person);
 ELSEIF p_event IN ('verified','published') THEN
  CALL payroll_assert(p_actor,IF(p_event='verified','payslip.verify','payslip.publish'),'payroll_manager',v_person);
 ELSE SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_INVALID';
 END IF;
 IF v_employee IS NULL OR v_parent IS NULL OR v_person=v_employee
 OR p_reason IS NULL OR CHAR_LENGTH(TRIM(p_reason))=0
 OR (p_event IN ('approved','rejected') AND v_person=v_preparer) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_FORBIDDEN';
 END IF;
 IF p_event='published' THEN
  IF NOT EXISTS(SELECT 1 FROM payroll_approvals WHERE calculation_id=p_calculation) THEN
   SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_STATE';
  END IF;
 ELSE
  IF EXISTS(SELECT 1 FROM payroll_approvals WHERE employee_id=v_employee AND period_id=v_period)
   OR EXISTS(SELECT 1 FROM payslip_events WHERE calculation_id=p_calculation AND event_type IN ('approved','rejected')) THEN
   SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_FROZEN';
  END IF;
  IF p_calculation<>(SELECT id FROM payroll_calculations WHERE employee_id=v_employee AND period_id=v_period ORDER BY version_no DESC LIMIT 1) THEN
   SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_STALE';
  END IF;
  IF p_event IN ('approved','rejected') AND NOT EXISTS(SELECT 1 FROM payslip_events WHERE calculation_id=p_calculation AND event_type='verified') THEN
   SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_STATE';
  END IF;
  IF p_event IN ('verified','approved') THEN
   CALL payroll_build(v_period,v_employee,v_base,v_bonus,v_deduction,v_snapshot);
   IF SHA2(CAST(v_snapshot AS CHAR),256)<>v_hash OR NOT EXISTS(SELECT 1 FROM payroll_calculations
    WHERE id=p_calculation AND base_amount=v_base AND bonus_amount=v_bonus AND deduction_amount=v_deduction
     AND gross_amount=v_base+v_bonus AND net_amount=v_base+v_bonus-v_deduction) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_STALE';
   END IF;
  END IF;
 END IF;
 INSERT INTO payslip_events(calculation_id,event_type,reason,actor_id,actor_employee_id)
 VALUES(p_calculation,p_event,TRIM(p_reason),p_actor,v_person);
 SET v_id=LAST_INSERT_ID();
 IF p_event='approved' THEN
  INSERT INTO payroll_approvals(calculation_id,period_id,employee_id) VALUES(p_calculation,v_period,v_employee);
 END IF;
 COMMIT;
 SELECT v_id AS id;
END$$
```

## Procédure `payroll_read_assert`

**Source :** [database/migrations/008_payroll_operations.sql](../../database/migrations/008_payroll_operations.sql). **DEFINER déclaré :** `'payroll_owner'@'localhost'`.

**Objectif :** Déterminer accès personnel ou personnel habilité, puis réutiliser payroll_assert.

### Paramètres et modes

```sql
payroll_read_assert(
 IN p_actor BIGINT UNSIGNED, OUT p_person BIGINT UNSIGNED, OUT p_staff BOOLEAN)
```

**Tables directement référencées :** roles, role_assignments.

**Appels imbriqués :** payroll_assert.

**Permissions métier visibles :** payroll.read, payslip.self. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** aucune ouverture autonome ; helper/lecture exécuté dans le contexte de son appelant. Pas de clause de verrouillage explicite directe dans le corps ; les helpers peuvent en prendre.

**Effets persistants directs :** Aucune écriture de table directe.

**Erreurs SIGNAL explicites :** Pas de SIGNAL propre ; erreurs propagées des helpers/SQL. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER='payroll_owner'@'localhost' PROCEDURE payroll_read_assert(
 IN p_actor BIGINT UNSIGNED, OUT p_person BIGINT UNSIGNED, OUT p_staff BOOLEAN)
SQL SECURITY DEFINER READS SQL DATA
BEGIN
 DECLARE v_role VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs DEFAULT NULL;
 SELECT MIN(r.code) INTO v_role FROM role_assignments ra JOIN roles r ON r.id=ra.role_id
 WHERE ra.account_id=p_actor AND r.code IN ('hr_manager','payroll_manager','finance_manager','security_auditor')
 AND ra.valid_from<=UTC_TIMESTAMP(6) AND (ra.expires_at IS NULL OR ra.expires_at>UTC_TIMESTAMP(6))
 AND (ra.revoked_at IS NULL OR ra.revoked_at>UTC_TIMESTAMP(6));
 SET p_staff=(v_role IS NOT NULL);
 CALL payroll_assert(p_actor,IF(p_staff,'payroll.read','payslip.self'),COALESCE(v_role,'employee'),p_person);
END$$
```

## Procédure `payroll_overview`

**Source :** [database/migrations/008_payroll_operations.sql](../../database/migrations/008_payroll_operations.sql). **DEFINER déclaré :** `'payroll_owner'@'localhost'`.

**Objectif :** Fournir mois, salariés de sélection, éléments et calculs avec filtrage personnel des bulletins publiés.

### Paramètres et modes

```sql
payroll_overview(
 IN p_actor BIGINT UNSIGNED, IN p_page INT UNSIGNED)
```

**Tables directement référencées :** employees, payroll_periods, payroll_inputs, payroll_input_decisions, payroll_calculations, payslip_events.

**Appels imbriqués :** payroll_read_assert.

**Permissions métier visibles :** Paramètre dynamique ou assertion héritée de l’appelant ; voir définition. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** aucune ouverture autonome ; helper/lecture exécuté dans le contexte de son appelant. Pas de clause de verrouillage explicite directe dans le corps ; les helpers peuvent en prendre.

**Effets persistants directs :** Aucune écriture de table directe.

**Erreurs SIGNAL explicites :** `PAY_INVALID`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER='payroll_owner'@'localhost' PROCEDURE payroll_overview(
 IN p_actor BIGINT UNSIGNED, IN p_page INT UNSIGNED)
SQL SECURITY DEFINER READS SQL DATA
BEGIN
 DECLARE v_person BIGINT UNSIGNED;
 DECLARE v_staff BOOLEAN;
 DECLARE v_offset INT UNSIGNED;
 CALL payroll_read_assert(p_actor,v_person,v_staff);
 IF p_page IS NULL OR p_page<1 OR p_page>1000000 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_INVALID'; END IF;
 SET v_offset=(p_page-1)*50;
 SELECT * FROM payroll_periods WHERE v_staff ORDER BY month_start DESC LIMIT 120;
 SELECT id,employee_number,first_name,last_name FROM employees WHERE v_staff AND archived_at IS NULL ORDER BY employee_number LIMIT 500;
 SELECT i.*,e.employee_number,COALESCE(d.decision,'pending') AS status,d.reason AS decision_reason
 FROM payroll_inputs i JOIN employees e ON e.id=i.employee_id LEFT JOIN payroll_input_decisions d ON d.input_id=i.id
 WHERE v_staff ORDER BY i.id DESC LIMIT 50 OFFSET v_offset;
 SELECT c.id,c.period_id,c.employee_id,c.version_no,c.currency,c.base_amount,c.bonus_amount,c.deduction_amount,
 c.gross_amount,c.net_amount,c.prepared_at,p.month_start,e.employee_number,e.first_name,e.last_name,
 COALESCE((SELECT event_type FROM payslip_events WHERE calculation_id=c.id ORDER BY id DESC LIMIT 1),'prepared') AS status
 FROM payroll_calculations c JOIN payroll_periods p ON p.id=c.period_id JOIN employees e ON e.id=c.employee_id
 WHERE v_staff OR (c.employee_id=v_person AND EXISTS(SELECT 1 FROM payslip_events WHERE calculation_id=c.id AND event_type='published'))
 ORDER BY c.id DESC LIMIT 50 OFFSET v_offset;
END$$
```

## Procédure `payslip_detail`

**Source :** [database/migrations/008_payroll_operations.sql](../../database/migrations/008_payroll_operations.sql). **DEFINER déclaré :** `'payroll_owner'@'localhost'`.

**Objectif :** Fournir bulletin, événements et versions ; accès personnel limité à ses bulletins publiés.

### Paramètres et modes

```sql
payslip_detail(
 IN p_calculation BIGINT UNSIGNED, IN p_actor BIGINT UNSIGNED)
```

**Tables directement référencées :** employees, payroll_periods, payroll_calculations, payslip_events.

**Appels imbriqués :** payroll_read_assert.

**Permissions métier visibles :** Paramètre dynamique ou assertion héritée de l’appelant ; voir définition. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** aucune ouverture autonome ; helper/lecture exécuté dans le contexte de son appelant. Pas de clause de verrouillage explicite directe dans le corps ; les helpers peuvent en prendre.

**Effets persistants directs :** Aucune écriture de table directe.

**Erreurs SIGNAL explicites :** `PAY_NOT_FOUND`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER='payroll_owner'@'localhost' PROCEDURE payslip_detail(
 IN p_calculation BIGINT UNSIGNED, IN p_actor BIGINT UNSIGNED)
SQL SECURITY DEFINER READS SQL DATA
BEGIN
 DECLARE v_person BIGINT UNSIGNED;
 DECLARE v_staff BOOLEAN;
 CALL payroll_read_assert(p_actor,v_person,v_staff);
 IF NOT EXISTS(SELECT 1 FROM payroll_calculations c WHERE c.id=p_calculation AND
  (v_staff OR (c.employee_id=v_person AND EXISTS(SELECT 1 FROM payslip_events WHERE calculation_id=c.id AND event_type='published')))) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_NOT_FOUND';
 END IF;
 SELECT c.*,p.month_start,e.employee_number,e.first_name,e.last_name,
 COALESCE((SELECT event_type FROM payslip_events WHERE calculation_id=c.id ORDER BY id DESC LIMIT 1),'prepared') AS status
 FROM payroll_calculations c JOIN payroll_periods p ON p.id=c.period_id JOIN employees e ON e.id=c.employee_id
 WHERE c.id=p_calculation;
 SELECT event_type,reason,actor_id,actor_employee_id,occurred_at FROM payslip_events WHERE calculation_id=p_calculation ORDER BY id;
 SELECT c.id,c.version_no,c.prepared_at,c.net_amount,c.currency FROM payroll_calculations c
 JOIN payroll_calculations original ON original.id=p_calculation AND c.employee_id=original.employee_id AND c.period_id=original.period_id
 WHERE v_staff OR EXISTS(SELECT 1 FROM payslip_events WHERE calculation_id=c.id AND event_type='published') ORDER BY c.version_no;
END$$
```

## Procédure `settlement_command`

**Source :** [database/migrations/010_settlement_operations.sql](../../database/migrations/010_settlement_operations.sql). **DEFINER déclaré :** `'settlement_owner'@'localhost'`.

**Objectif :** Traiter corrections, transitions, paiement du solde et restitution par une commande transactionnelle à version attendue.

### Paramètres et modes

```sql
settlement_command(
 IN p_root BIGINT UNSIGNED,
 IN p_action VARCHAR(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_target BIGINT UNSIGNED, IN p_expected BIGINT UNSIGNED,
 IN p_base DECIMAL(12,2), IN p_bonus DECIMAL(12,2), IN p_deduction DECIMAL(12,2),
 IN p_reference VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_reason VARCHAR(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_actor BIGINT UNSIGNED)
```

**Tables directement référencées :** employees, payroll_periods, payroll_calculations, payslip_events, payslip_corrections, correction_events, recovery_requests, recovery_events, settlement_ledger.

**Appels imbriqués :** payroll_assert.

**Permissions métier visibles :** payroll.payment, payroll.recovery.decide, payroll.recovery.receive, payroll.recovery.request, payslip.correct, payslip.decide, payslip.publish, payslip.verify. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** transaction explicite avec COMMIT ; isolation READ COMMITTED explicitement demandée. Handler SQLEXCEPTION : ROLLBACK puis RESIGNAL. Verrou(s) FOR UPDATE et/ou FOR SHARE présent(s).

**Effets persistants directs :** INSERT dans correction_events, payslip_corrections, recovery_events, recovery_requests, settlement_ledger. 

**Erreurs SIGNAL explicites :** `PAY_CAP`, `PAY_FORBIDDEN`, `PAY_INVALID`, `PAY_NOT_FOUND`, `PAY_STALE`, `PAY_STATE`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER='settlement_owner'@'localhost' PROCEDURE settlement_command(
 IN p_root BIGINT UNSIGNED,
 IN p_action VARCHAR(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_target BIGINT UNSIGNED, IN p_expected BIGINT UNSIGNED,
 IN p_base DECIMAL(12,2), IN p_bonus DECIMAL(12,2), IN p_deduction DECIMAL(12,2),
 IN p_reference VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_reason VARCHAR(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_actor BIGINT UNSIGNED)
SQL SECURITY DEFINER MODIFIES SQL DATA
BEGIN
 DECLARE v_employee BIGINT UNSIGNED DEFAULT NULL;
 DECLARE v_parent BIGINT UNSIGNED DEFAULT NULL;
 DECLARE v_person BIGINT UNSIGNED;
 DECLARE v_preparer BIGINT UNSIGNED;
 DECLARE v_current BIGINT UNSIGNED DEFAULT 0;
 DECLARE v_revision INT UNSIGNED;
 DECLARE v_net DECIMAL(20,2);
 DECLARE v_balance DECIMAL(20,2);
 DECLARE v_amount DECIMAL(12,2);
 DECLARE v_requester BIGINT UNSIGNED;
 DECLARE v_id BIGINT UNSIGNED;
 DECLARE v_state VARCHAR(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs;
 DECLARE v_permission VARCHAR(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs;
 DECLARE v_role VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs;
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
 START TRANSACTION;
 SET v_permission=CASE p_action WHEN 'correct' THEN 'payslip.correct'
 WHEN 'verified' THEN 'payslip.verify' WHEN 'approved' THEN 'payslip.decide'
 WHEN 'rejected' THEN 'payslip.decide' WHEN 'published' THEN 'payslip.publish'
 WHEN 'pay' THEN 'payroll.payment' WHEN 'recover_request' THEN 'payroll.recovery.request'
 WHEN 'recover_approve' THEN 'payroll.recovery.decide' WHEN 'recover_reject' THEN 'payroll.recovery.decide'
 WHEN 'recover_receive' THEN 'payroll.recovery.receive' ELSE NULL END;
 IF v_permission IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_INVALID'; END IF;
 SET v_role=IF(p_action IN ('approved','rejected','pay','recover_approve','recover_reject'),'finance_manager','payroll_manager');
 SELECT employee_id,preparer_employee_id INTO v_employee,v_preparer FROM payroll_calculations WHERE id=p_root;
 SELECT id INTO v_parent FROM employees WHERE id=v_employee AND archived_at IS NULL FOR UPDATE;
 CALL payroll_assert(p_actor,v_permission,v_role,v_person);
 IF v_parent IS NULL OR NOT EXISTS(SELECT 1 FROM payslip_events WHERE calculation_id=p_root AND event_type='published') THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_NOT_FOUND';
 END IF;
 IF v_person=v_employee THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_FORBIDDEN'; END IF;
 IF p_reason IS NULL OR CHAR_LENGTH(TRIM(p_reason)) NOT BETWEEN 1 AND 2000 THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_INVALID';
 END IF;
 SELECT COALESCE(MAX(c.id),0) INTO v_current FROM payslip_corrections c
 JOIN correction_events e ON e.correction_id=c.id AND e.event_type='published' WHERE c.calculation_id=p_root;
 SELECT net_amount INTO v_net FROM payroll_calculations WHERE id=p_root;
 IF v_current<>0 THEN
  SELECT net_amount,preparer_employee_id INTO v_net,v_preparer FROM payslip_corrections WHERE id=v_current;
 END IF;
 SELECT v_net-COALESCE(SUM(IF(entry_type='payment',amount,-amount)),0) INTO v_balance
 FROM settlement_ledger WHERE calculation_id=p_root;
 IF p_expected IS NULL OR p_expected<>v_current THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_STALE'; END IF;
 IF p_action='correct' THEN
  IF EXISTS(SELECT 1 FROM payslip_corrections c WHERE c.calculation_id=p_root
   AND NOT EXISTS(SELECT 1 FROM correction_events e WHERE e.correction_id=c.id AND e.event_type IN ('published','rejected')))
   OR EXISTS(SELECT 1 FROM recovery_requests r WHERE r.calculation_id=p_root
   AND NOT EXISTS(SELECT 1 FROM recovery_events e WHERE e.request_id=r.id AND e.event_type IN ('received','rejected'))) THEN
   SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_STATE';
  END IF;
  IF p_base IS NULL OR p_bonus IS NULL OR p_deduction IS NULL OR p_base<0 OR p_bonus<0 OR p_deduction<0
   OR p_base+p_bonus>9999999999.99 OR p_base+p_bonus-p_deduction<0 THEN
   SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_INVALID';
  END IF;
  IF EXISTS(SELECT 1 FROM payroll_calculations c JOIN payroll_periods p ON p.id=c.period_id
    WHERE c.id=p_root AND (p_bonus>p.bonus_cap OR p_deduction>p.deduction_cap)) THEN
   SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_CAP';
  END IF;
  
  
  SELECT COALESCE(MAX(revision),0)+1 INTO v_revision FROM payslip_corrections WHERE calculation_id=p_root;
  INSERT INTO payslip_corrections(calculation_id,parent_id,revision,base_amount,bonus_amount,deduction_amount,gross_amount,net_amount,reason,prepared_by,preparer_employee_id)
  VALUES(p_root,NULLIF(v_current,0),v_revision,p_base,p_bonus,p_deduction,p_base+p_bonus,p_base+p_bonus-p_deduction,TRIM(p_reason),p_actor,v_person);
  SET v_id=LAST_INSERT_ID();
 ELSEIF p_action IN ('verified','approved','rejected','published') THEN
  SET v_state=NULL;
  SELECT c.preparer_employee_id,COALESCE((SELECT event_type FROM correction_events WHERE correction_id=c.id ORDER BY id DESC LIMIT 1),'prepared')
  INTO v_preparer,v_state FROM payslip_corrections c
  WHERE c.id=p_target AND c.calculation_id=p_root AND COALESCE(c.parent_id,0)=v_current;
  IF v_state IS NULL OR NOT ((p_action='verified' AND v_state='prepared')
    OR (p_action IN ('approved','rejected') AND v_state='verified') OR (p_action='published' AND v_state='approved')) THEN
   SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_STATE';
  END IF;
  IF p_action IN ('approved','rejected') AND v_person=v_preparer THEN
   SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_FORBIDDEN';
  END IF;
  INSERT INTO correction_events(correction_id,event_type,reason,actor_id,actor_employee_id)
  VALUES(p_target,p_action,TRIM(p_reason),p_actor,v_person);
  SET v_id=LAST_INSERT_ID();
 ELSE
  
  IF EXISTS(SELECT 1 FROM payslip_corrections c WHERE c.calculation_id=p_root
   AND NOT EXISTS(SELECT 1 FROM correction_events e WHERE e.correction_id=c.id AND e.event_type IN ('published','rejected'))) THEN
   SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_STATE';
  END IF;
  IF p_action IN ('pay','recover_receive') AND (p_reference IS NULL OR NOT REGEXP_LIKE(p_reference,'^[A-Za-z0-9_-]{8,64}$','c')) THEN
   SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_INVALID';
  END IF;
  IF p_action='pay' THEN
   IF v_person=v_preparer THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_FORBIDDEN'; END IF;
   IF v_balance<=0 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_STATE'; END IF;
   INSERT INTO settlement_ledger(calculation_id,correction_id,entry_type,amount,reference,reason,actor_id,actor_employee_id)
   VALUES(p_root,NULLIF(v_current,0),'payment',v_balance,p_reference,TRIM(p_reason),p_actor,v_person);
   SET v_id=LAST_INSERT_ID();
  ELSEIF p_action='recover_request' THEN
   IF v_balance>=0 OR EXISTS(SELECT 1 FROM recovery_requests r WHERE r.calculation_id=p_root
     AND NOT EXISTS(SELECT 1 FROM recovery_events e WHERE e.request_id=r.id AND e.event_type IN ('received','rejected'))) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_STATE';
   END IF;
   INSERT INTO recovery_requests(calculation_id,correction_id,amount,reason,requested_by,requester_employee_id)
   VALUES(p_root,NULLIF(v_current,0),-v_balance,TRIM(p_reason),p_actor,v_person);
   SET v_id=LAST_INSERT_ID();
  ELSE
   SET v_state=NULL;
   SELECT r.amount,r.requester_employee_id,COALESCE((SELECT event_type FROM recovery_events WHERE request_id=r.id ORDER BY id DESC LIMIT 1),'pending')
   INTO v_amount,v_requester,v_state FROM recovery_requests r
   WHERE r.id=p_target AND r.calculation_id=p_root AND COALESCE(r.correction_id,0)=v_current;
   IF v_state IS NULL OR NOT ((p_action IN ('recover_approve','recover_reject') AND v_state='pending')
     OR (p_action='recover_receive' AND v_state='approved')) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_STATE';
   END IF;
   IF p_action IN ('recover_approve','recover_reject') AND v_person IN (v_requester,v_preparer) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_FORBIDDEN';
   END IF;
   IF p_action='recover_receive' THEN
    IF v_balance>=0 OR v_amount> -v_balance THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_STATE'; END IF;
    INSERT INTO settlement_ledger(calculation_id,correction_id,recovery_id,entry_type,amount,reference,reason,actor_id,actor_employee_id)
    VALUES(p_root,NULLIF(v_current,0),p_target,'recovery',v_amount,p_reference,TRIM(p_reason),p_actor,v_person);
   END IF;
   INSERT INTO recovery_events(request_id,event_type,reason,actor_id,actor_employee_id)
   VALUES(p_target,CASE p_action WHEN 'recover_approve' THEN 'approved' WHEN 'recover_reject' THEN 'rejected' ELSE 'received' END,TRIM(p_reason),p_actor,v_person);
   SET v_id=LAST_INSERT_ID();
  END IF;
 END IF;
 COMMIT;
 SELECT v_id AS id;
END$$
```

## Procédure `settlement_detail`

**Source :** [database/migrations/010_settlement_operations.sql](../../database/migrations/010_settlement_operations.sql). **DEFINER déclaré :** `'settlement_owner'@'localhost'`.

**Objectif :** Lire de façon cohérente le net effectif, le solde et les historiques accessibles de règlement.

### Paramètres et modes

```sql
settlement_detail(IN p_root BIGINT UNSIGNED, IN p_actor BIGINT UNSIGNED)
```

**Tables directement référencées :** employees, payroll_calculations, payslip_events, payslip_corrections, correction_events, recovery_requests, recovery_events, settlement_ledger.

**Appels imbriqués :** payroll_read_assert.

**Permissions métier visibles :** Paramètre dynamique ou assertion héritée de l’appelant ; voir définition. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** transaction explicite avec COMMIT ; isolation courante de la session non remplacée dans cette routine. Handler SQLEXCEPTION : ROLLBACK puis RESIGNAL. Verrou(s) FOR UPDATE et/ou FOR SHARE présent(s).

**Effets persistants directs :** Aucune écriture de table directe.

**Erreurs SIGNAL explicites :** `PAY_NOT_FOUND`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER='settlement_owner'@'localhost' PROCEDURE settlement_detail(IN p_root BIGINT UNSIGNED, IN p_actor BIGINT UNSIGNED)
SQL SECURITY DEFINER READS SQL DATA
BEGIN
 DECLARE v_person BIGINT UNSIGNED;
 DECLARE v_staff BOOLEAN;
 DECLARE v_employee BIGINT UNSIGNED DEFAULT NULL;
 DECLARE v_parent BIGINT UNSIGNED;
 DECLARE v_current BIGINT UNSIGNED DEFAULT 0;
 DECLARE v_net DECIMAL(12,2);
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 START TRANSACTION;
 SELECT employee_id INTO v_employee FROM payroll_calculations WHERE id=p_root;
 SELECT id INTO v_parent FROM employees WHERE id=v_employee FOR SHARE;
 CALL payroll_read_assert(p_actor,v_person,v_staff);
 IF v_employee IS NULL OR (NOT v_staff AND v_person<>v_employee)
  OR NOT EXISTS(SELECT 1 FROM payslip_events WHERE calculation_id=p_root AND event_type='published') THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_NOT_FOUND';
 END IF;
 SELECT COALESCE(MAX(c.id),0) INTO v_current FROM payslip_corrections c
 JOIN correction_events e ON e.correction_id=c.id AND e.event_type='published' WHERE c.calculation_id=p_root;
 SELECT net_amount INTO v_net FROM payroll_calculations WHERE id=p_root;
 IF v_current<>0 THEN SELECT net_amount INTO v_net FROM payslip_corrections WHERE id=v_current; END IF;
 SELECT p_root AS calculation_id,v_employee AS employee_id,v_current AS current_correction_id,v_net AS net_amount,
 v_net-COALESCE(SUM(IF(entry_type='payment',amount,-amount)),0) AS balance,'MAD' AS currency
 FROM settlement_ledger WHERE calculation_id=p_root;
 SELECT c.*,COALESCE((SELECT event_type FROM correction_events WHERE correction_id=c.id ORDER BY id DESC LIMIT 1),'prepared') AS status
 FROM payslip_corrections c WHERE c.calculation_id=p_root AND (v_staff OR EXISTS(SELECT 1 FROM correction_events WHERE correction_id=c.id AND event_type='published')) ORDER BY c.revision;
 SELECT e.* FROM correction_events e JOIN payslip_corrections c ON c.id=e.correction_id
 WHERE c.calculation_id=p_root AND (v_staff OR EXISTS(SELECT 1 FROM correction_events WHERE correction_id=c.id AND event_type='published')) ORDER BY e.id;
 SELECT * FROM settlement_ledger WHERE calculation_id=p_root ORDER BY id;
 SELECT r.*,COALESCE((SELECT event_type FROM recovery_events WHERE request_id=r.id ORDER BY id DESC LIMIT 1),'pending') AS status
 FROM recovery_requests r WHERE r.calculation_id=p_root AND (v_staff OR EXISTS(SELECT 1 FROM recovery_events WHERE request_id=r.id AND event_type='received')) ORDER BY r.id;
 SELECT e.* FROM recovery_events e JOIN recovery_requests r ON r.id=e.request_id WHERE r.calculation_id=p_root AND v_staff ORDER BY e.id;
 COMMIT;
END$$
```

## Procédure `iam_overview`

**Source :** [database/migrations/011_iam_operations.sql](../../database/migrations/011_iam_operations.sql). **DEFINER déclaré :** `'iam_owner'@'localhost'`.

**Objectif :** Lire les comptes sans empreinte, les rôles et les attributions avec permission Admin/Audit.

### Paramètres et modes

```sql
iam_overview(IN p_actor BIGINT UNSIGNED, IN p_page INT UNSIGNED)
```

**Tables directement référencées :** employees, accounts, roles, role_assignments.

**Appels imbriqués :** payroll_assert.

**Permissions métier visibles :** iam.read. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** aucune ouverture autonome ; helper/lecture exécuté dans le contexte de son appelant. Pas de clause de verrouillage explicite directe dans le corps ; les helpers peuvent en prendre.

**Effets persistants directs :** Aucune écriture de table directe.

**Erreurs SIGNAL explicites :** `IAM_INVALID`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER='iam_owner'@'localhost' PROCEDURE iam_overview(IN p_actor BIGINT UNSIGNED, IN p_page INT UNSIGNED)
SQL SECURITY DEFINER READS SQL DATA
BEGIN
 DECLARE v_person BIGINT UNSIGNED;
 DECLARE v_offset INT UNSIGNED;
 DECLARE v_role VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs;
 SET v_role=IF(EXISTS(SELECT 1 FROM accounts a JOIN role_assignments ra ON ra.account_id=a.id JOIN roles r ON r.id=ra.role_id
  WHERE a.id=p_actor AND r.code='application_administrator' AND ra.valid_from<=UTC_TIMESTAMP(6)
  AND (ra.expires_at IS NULL OR ra.expires_at>UTC_TIMESTAMP(6)) AND ra.revoked_at IS NULL),'application_administrator','security_auditor');
 CALL payroll_assert(p_actor,'iam.read',v_role,v_person);
 IF p_page IS NULL OR p_page<1 OR p_page>1000000 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='IAM_INVALID'; END IF;
 SET v_offset=(p_page-1)*50;
 SELECT a.id,a.employee_id,a.login,a.disabled_at,e.employee_number,e.archived_at FROM accounts a JOIN employees e ON e.id=a.employee_id ORDER BY a.id LIMIT 500;
 SELECT id,code,name FROM roles ORDER BY id;
 SELECT ra.*,a.login,r.code FROM role_assignments ra JOIN accounts a ON a.id=ra.account_id JOIN roles r ON r.id=ra.role_id ORDER BY ra.id DESC LIMIT 50 OFFSET v_offset;
END$$
```

## Procédure `iam_grant`

**Source :** [database/migrations/011_iam_operations.sql](../../database/migrations/011_iam_operations.sql). **DEFINER déclaré :** `'iam_owner'@'localhost'`.

**Objectif :** Octroyer un rôle à une autre personne active sans doublon ni cumul opérationnel, y compris futur.

### Paramètres et modes

```sql
iam_grant(
 IN p_account BIGINT UNSIGNED,
 IN p_role VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_reason VARCHAR(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_actor BIGINT UNSIGNED)
```

**Tables directement référencées :** employees, accounts, roles, role_assignments.

**Appels imbriqués :** payroll_assert.

**Permissions métier visibles :** iam.grant. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** transaction explicite avec COMMIT ; isolation READ COMMITTED explicitement demandée. Handler SQLEXCEPTION : ROLLBACK puis RESIGNAL. Verrou(s) FOR UPDATE et/ou FOR SHARE présent(s).

**Effets persistants directs :** INSERT dans role_assignments. 

**Erreurs SIGNAL explicites :** `IAM_CONFLICT`, `IAM_FORBIDDEN`, `IAM_INVALID`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER='iam_owner'@'localhost' PROCEDURE iam_grant(
 IN p_account BIGINT UNSIGNED,
 IN p_role VARCHAR(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_reason VARCHAR(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_actor BIGINT UNSIGNED)
SQL SECURITY DEFINER MODIFIES SQL DATA
BEGIN
 DECLARE v_employee BIGINT UNSIGNED DEFAULT NULL;
 DECLARE v_parent BIGINT UNSIGNED DEFAULT NULL;
 DECLARE v_person BIGINT UNSIGNED;
 DECLARE v_role BIGINT UNSIGNED DEFAULT NULL;
 DECLARE v_active BIGINT UNSIGNED DEFAULT NULL;
 DECLARE v_id BIGINT UNSIGNED;
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
 START TRANSACTION;
 SELECT employee_id INTO v_employee FROM accounts WHERE id=p_account;
 SELECT id INTO v_parent FROM employees WHERE id=v_employee AND archived_at IS NULL FOR UPDATE;
 CALL payroll_assert(p_actor,'iam.grant','application_administrator',v_person);
 SELECT id INTO v_role FROM roles WHERE code=p_role;
 IF v_employee=v_person THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='IAM_FORBIDDEN'; END IF;
 IF v_parent IS NULL OR v_role IS NULL OR NOT EXISTS(SELECT 1 FROM accounts WHERE id=p_account AND disabled_at IS NULL)
  OR p_reason IS NULL OR CHAR_LENGTH(TRIM(p_reason)) NOT BETWEEN 1 AND 255 THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='IAM_INVALID';
 END IF;
 
 SELECT employee_id INTO v_active FROM accounts WHERE id=p_account AND disabled_at IS NULL FOR SHARE;
 IF v_active IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='IAM_INVALID'; END IF;
 
 IF EXISTS(SELECT 1 FROM accounts a JOIN role_assignments ra ON ra.account_id=a.id JOIN roles r ON r.id=ra.role_id
  WHERE a.employee_id=v_employee AND (ra.expires_at IS NULL OR ra.expires_at>UTC_TIMESTAMP(6))
  AND (ra.revoked_at IS NULL OR ra.revoked_at>UTC_TIMESTAMP(6))
  AND (r.code=p_role OR (r.code<>'employee' AND p_role<>'employee'))) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='IAM_CONFLICT';
 END IF;
 INSERT INTO role_assignments(account_id,role_id,granted_by_account_id,grant_reason)
 VALUES(p_account,v_role,p_actor,TRIM(p_reason));
 SET v_id=LAST_INSERT_ID();
 COMMIT;
 SELECT v_id AS id;
END$$
```

## Procédure `iam_revoke`

**Source :** [database/migrations/011_iam_operations.sql](../../database/migrations/011_iam_operations.sql). **DEFINER déclaré :** `'iam_owner'@'localhost'`.

**Objectif :** Révoquer une attribution d’autrui une seule fois en conservant toutes les données d’octroi.

### Paramètres et modes

```sql
iam_revoke(
 IN p_assignment BIGINT UNSIGNED,
 IN p_reason VARCHAR(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_actor BIGINT UNSIGNED)
```

**Tables directement référencées :** employees, accounts, role_assignments.

**Appels imbriqués :** payroll_assert.

**Permissions métier visibles :** iam.revoke. Le compte appelant doit disposer de EXECUTE ; `svc_php` ne reçoit que les points d’entrée publics déclarés dans setup/*_grants.sql. Le DEFINER doit posséder ses droits d’objets et de routines imbriquées.

**Transaction :** transaction explicite avec COMMIT ; isolation READ COMMITTED explicitement demandée. Handler SQLEXCEPTION : ROLLBACK puis RESIGNAL. Verrou(s) FOR UPDATE et/ou FOR SHARE présent(s).

**Effets persistants directs :** UPDATE dans role_assignments.

**Erreurs SIGNAL explicites :** `IAM_FORBIDDEN`, `IAM_INVALID`, `IAM_STATE`. Les erreurs SQL natives (unicité/FK, deadlock ou timeout) restent possibles et sont propagées.

### Définition exacte pour contrôle des branches et de la sécurité

```sql
CREATE DEFINER='iam_owner'@'localhost' PROCEDURE iam_revoke(
 IN p_assignment BIGINT UNSIGNED,
 IN p_reason VARCHAR(2000) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs,
 IN p_actor BIGINT UNSIGNED)
SQL SECURITY DEFINER MODIFIES SQL DATA
BEGIN
 DECLARE v_employee BIGINT UNSIGNED DEFAULT NULL;
 DECLARE v_parent BIGINT UNSIGNED;
 DECLARE v_person BIGINT UNSIGNED;
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
 START TRANSACTION;
 SELECT a.employee_id INTO v_employee FROM accounts a JOIN role_assignments ra ON ra.account_id=a.id WHERE ra.id=p_assignment;
 SELECT id INTO v_parent FROM employees WHERE id=v_employee FOR UPDATE;
 CALL payroll_assert(p_actor,'iam.revoke','application_administrator',v_person);
 IF v_employee=v_person THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='IAM_FORBIDDEN'; END IF;
 IF v_employee IS NULL OR p_reason IS NULL OR CHAR_LENGTH(TRIM(p_reason)) NOT BETWEEN 1 AND 255 THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='IAM_INVALID';
 END IF;
 UPDATE role_assignments SET revoked_at=CURRENT_TIMESTAMP(6),revoked_by_account_id=p_actor,revocation_reason=TRIM(p_reason)
 WHERE id=p_assignment AND revoked_at IS NULL;
 IF ROW_COUNT()<>1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='IAM_STATE'; END IF;
 COMMIT;
 SELECT p_assignment AS id;
END$$
```

## Triggers : inventaire et portée

Les 42 triggers sont tous BEFORE, par ligne. Aucun trigger AFTER n’est déclaré. Les triggers financiers refusent tout UPDATE/DELETE, même si une écriture propose la même valeur ; les triggers identité et attribution examinent les différences et autorisent certaines transitions précises. Les créations d’événements ne sont pas générées par des triggers : les procédures les insèrent dans la même transaction que l’opération.

Le mécanisme ne rend pas les données inviolables contre un administrateur ayant DROP TRIGGER, ALTER ou des droits de restauration. Les permissions DDL doivent rester séparées du compte web ; une empreinte SHA256 de snapshot ne constitue pas un journal signé externe.

| Trigger | Table | Moment | Événement | Source |
|---|---|---|---|---|
| employees_preserve_identity | employees | BEFORE | UPDATE | [database/migrations/001_create_identity_and_rbac.sql](../../database/migrations/001_create_identity_and_rbac.sql) |
| employees_prevent_delete | employees | BEFORE | DELETE | [database/migrations/001_create_identity_and_rbac.sql](../../database/migrations/001_create_identity_and_rbac.sql) |
| accounts_preserve_identity | accounts | BEFORE | UPDATE | [database/migrations/001_create_identity_and_rbac.sql](../../database/migrations/001_create_identity_and_rbac.sql) |
| accounts_prevent_delete | accounts | BEFORE | DELETE | [database/migrations/001_create_identity_and_rbac.sql](../../database/migrations/001_create_identity_and_rbac.sql) |
| assignments_validate_insert | role_assignments | BEFORE | INSERT | [database/migrations/001_create_identity_and_rbac.sql](../../database/migrations/001_create_identity_and_rbac.sql) |
| assignments_preserve_history | role_assignments | BEFORE | UPDATE | [database/migrations/001_create_identity_and_rbac.sql](../../database/migrations/001_create_identity_and_rbac.sql) |
| assignments_prevent_delete | role_assignments | BEFORE | DELETE | [database/migrations/001_create_identity_and_rbac.sql](../../database/migrations/001_create_identity_and_rbac.sql) |
| ea_no_delete | employee_assignments | BEFORE | DELETE | [database/migrations/002_advanced_hr.sql](../../database/migrations/002_advanced_hr.sql) |
| ec_no_delete | employment_contracts | BEFORE | DELETE | [database/migrations/002_advanced_hr.sql](../../database/migrations/002_advanced_hr.sql) |
| ea_preserve_history | employee_assignments | BEFORE | UPDATE | [database/migrations/002_advanced_hr.sql](../../database/migrations/002_advanced_hr.sql) |
| ec_preserve_history | employment_contracts | BEFORE | UPDATE | [database/migrations/002_advanced_hr.sql](../../database/migrations/002_advanced_hr.sql) |
| cr_no_update | compensation_requests | BEFORE | UPDATE | [database/migrations/004_compensation.sql](../../database/migrations/004_compensation.sql) |
| cr_no_delete | compensation_requests | BEFORE | DELETE | [database/migrations/004_compensation.sql](../../database/migrations/004_compensation.sql) |
| cd_no_update | compensation_decisions | BEFORE | UPDATE | [database/migrations/004_compensation.sql](../../database/migrations/004_compensation.sql) |
| cd_no_delete | compensation_decisions | BEFORE | DELETE | [database/migrations/004_compensation.sql](../../database/migrations/004_compensation.sql) |
| sc_no_update | salary_conditions | BEFORE | UPDATE | [database/migrations/004_compensation.sql](../../database/migrations/004_compensation.sql) |
| sc_no_delete | salary_conditions | BEFORE | DELETE | [database/migrations/004_compensation.sql](../../database/migrations/004_compensation.sql) |
| ch_no_update | compensation_history | BEFORE | UPDATE | [database/migrations/004_compensation.sql](../../database/migrations/004_compensation.sql) |
| ch_no_delete | compensation_history | BEFORE | DELETE | [database/migrations/004_compensation.sql](../../database/migrations/004_compensation.sql) |
| ec_salary_coverage | employment_contracts | BEFORE | UPDATE | [database/migrations/004_compensation.sql](../../database/migrations/004_compensation.sql) |
| payroll_periods_no_update | payroll_periods | BEFORE | UPDATE | [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql) |
| payroll_periods_no_delete | payroll_periods | BEFORE | DELETE | [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql) |
| payroll_inputs_no_update | payroll_inputs | BEFORE | UPDATE | [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql) |
| payroll_inputs_no_delete | payroll_inputs | BEFORE | DELETE | [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql) |
| payroll_input_decisions_no_update | payroll_input_decisions | BEFORE | UPDATE | [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql) |
| payroll_input_decisions_no_delete | payroll_input_decisions | BEFORE | DELETE | [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql) |
| payroll_calculations_no_update | payroll_calculations | BEFORE | UPDATE | [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql) |
| payroll_calculations_no_delete | payroll_calculations | BEFORE | DELETE | [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql) |
| payslip_events_no_update | payslip_events | BEFORE | UPDATE | [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql) |
| payslip_events_no_delete | payslip_events | BEFORE | DELETE | [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql) |
| payroll_approvals_no_update | payroll_approvals | BEFORE | UPDATE | [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql) |
| payroll_approvals_no_delete | payroll_approvals | BEFORE | DELETE | [database/migrations/007_payroll.sql](../../database/migrations/007_payroll.sql) |
| payslip_corrections_no_update | payslip_corrections | BEFORE | UPDATE | [database/migrations/009_settlement.sql](../../database/migrations/009_settlement.sql) |
| payslip_corrections_no_delete | payslip_corrections | BEFORE | DELETE | [database/migrations/009_settlement.sql](../../database/migrations/009_settlement.sql) |
| correction_events_no_update | correction_events | BEFORE | UPDATE | [database/migrations/009_settlement.sql](../../database/migrations/009_settlement.sql) |
| correction_events_no_delete | correction_events | BEFORE | DELETE | [database/migrations/009_settlement.sql](../../database/migrations/009_settlement.sql) |
| recovery_requests_no_update | recovery_requests | BEFORE | UPDATE | [database/migrations/009_settlement.sql](../../database/migrations/009_settlement.sql) |
| recovery_requests_no_delete | recovery_requests | BEFORE | DELETE | [database/migrations/009_settlement.sql](../../database/migrations/009_settlement.sql) |
| recovery_events_no_update | recovery_events | BEFORE | UPDATE | [database/migrations/009_settlement.sql](../../database/migrations/009_settlement.sql) |
| recovery_events_no_delete | recovery_events | BEFORE | DELETE | [database/migrations/009_settlement.sql](../../database/migrations/009_settlement.sql) |
| settlement_ledger_no_update | settlement_ledger | BEFORE | UPDATE | [database/migrations/009_settlement.sql](../../database/migrations/009_settlement.sql) |
| settlement_ledger_no_delete | settlement_ledger | BEFORE | DELETE | [database/migrations/009_settlement.sql](../../database/migrations/009_settlement.sql) |

### `employees_preserve_identity`

**Déclenchement :** BEFORE UPDATE ON employees, pour chaque ligne. **Contexte déclaré :** Créateur de la migration (non fixé dans le SQL).

**Comportement / objectif :** Examen conditionnel des anciennes/nouvelles valeurs ; refus des mutations interdites. Les conditions exactes sont reproduites ci-dessous.

```sql
CREATE TRIGGER employees_preserve_identity BEFORE UPDATE ON employees FOR EACH ROW
BEGIN
    IF NOT (NEW.id <=> OLD.id)
        OR NOT (CAST(NEW.employee_number AS BINARY) <=> CAST(OLD.employee_number AS BINARY))
        OR NOT (NEW.created_at <=> OLD.created_at) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Employee identity is immutable';
    END IF;
END$$
```

### `employees_prevent_delete`

**Déclenchement :** BEFORE DELETE ON employees, pour chaque ligne. **Contexte déclaré :** Créateur de la migration (non fixé dans le SQL).

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE TRIGGER employees_prevent_delete BEFORE DELETE ON employees FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Archive employees instead of deleting them';
END$$
```

### `accounts_preserve_identity`

**Déclenchement :** BEFORE UPDATE ON accounts, pour chaque ligne. **Contexte déclaré :** Créateur de la migration (non fixé dans le SQL).

**Comportement / objectif :** Examen conditionnel des anciennes/nouvelles valeurs ; refus des mutations interdites. Les conditions exactes sont reproduites ci-dessous.

```sql
CREATE TRIGGER accounts_preserve_identity BEFORE UPDATE ON accounts FOR EACH ROW
BEGIN
    IF NOT (NEW.id <=> OLD.id) OR NOT (NEW.employee_id <=> OLD.employee_id)
        OR NOT (NEW.created_at <=> OLD.created_at) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Account identity is immutable';
    END IF;
END$$
```

### `accounts_prevent_delete`

**Déclenchement :** BEFORE DELETE ON accounts, pour chaque ligne. **Contexte déclaré :** Créateur de la migration (non fixé dans le SQL).

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE TRIGGER accounts_prevent_delete BEFORE DELETE ON accounts FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Disable accounts instead of deleting them';
END$$
```

### `assignments_validate_insert`

**Déclenchement :** BEFORE INSERT ON role_assignments, pour chaque ligne. **Contexte déclaré :** Créateur de la migration (non fixé dans le SQL).

**Comportement / objectif :** Examen conditionnel des anciennes/nouvelles valeurs ; refus des mutations interdites. Les conditions exactes sont reproduites ci-dessous.

```sql
CREATE TRIGGER assignments_validate_insert BEFORE INSERT ON role_assignments FOR EACH ROW
BEGIN
    IF @@session.time_zone <> '+00:00'
        OR NOT (NEW.granted_at <=> CURRENT_TIMESTAMP(6)) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Grant time must be the current SQL instant in UTC';
    END IF;
    IF NEW.revoked_at IS NOT NULL OR NEW.revoked_by_account_id IS NOT NULL
        OR NEW.revocation_reason IS NOT NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'New assignments cannot already be revoked';
    END IF;
END$$
```

### `assignments_preserve_history`

**Déclenchement :** BEFORE UPDATE ON role_assignments, pour chaque ligne. **Contexte déclaré :** Créateur de la migration (non fixé dans le SQL).

**Comportement / objectif :** Examen conditionnel des anciennes/nouvelles valeurs ; refus des mutations interdites. Les conditions exactes sont reproduites ci-dessous.

```sql
CREATE TRIGGER assignments_preserve_history BEFORE UPDATE ON role_assignments FOR EACH ROW
BEGIN
    IF NOT (NEW.id <=> OLD.id) OR NOT (NEW.account_id <=> OLD.account_id) OR NOT (NEW.role_id <=> OLD.role_id)
        OR NOT (NEW.granted_by_account_id <=> OLD.granted_by_account_id)
        OR NOT (NEW.granted_at <=> OLD.granted_at) OR NOT (NEW.valid_from <=> OLD.valid_from)
        OR NOT (NEW.expires_at <=> OLD.expires_at)
        OR NOT (CAST(NEW.grant_reason AS BINARY) <=> CAST(OLD.grant_reason AS BINARY)) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Assignment grant data is immutable';
    END IF;
    
    IF NOT (NEW.revoked_at <=> OLD.revoked_at)
        OR NOT (NEW.revoked_by_account_id <=> OLD.revoked_by_account_id)
        OR NOT (CAST(NEW.revocation_reason AS BINARY) <=> CAST(OLD.revocation_reason AS BINARY)) THEN
        IF OLD.revoked_at IS NOT NULL OR NEW.revoked_at IS NULL
            OR NEW.revoked_by_account_id IS NULL OR @@session.time_zone <> '+00:00'
            OR NOT (NEW.revoked_at <=> CURRENT_TIMESTAMP(6)) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Only a first revocation at the current SQL instant is allowed';
        END IF;
    END IF;
END$$
```

### `assignments_prevent_delete`

**Déclenchement :** BEFORE DELETE ON role_assignments, pour chaque ligne. **Contexte déclaré :** Créateur de la migration (non fixé dans le SQL).

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE TRIGGER assignments_prevent_delete BEFORE DELETE ON role_assignments FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Role assignment history cannot be deleted';
END$$
```

### `ea_no_delete`

**Déclenchement :** BEFORE DELETE ON employee_assignments, pour chaque ligne. **Contexte déclaré :** 'hr_module_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER = 'hr_module_owner'@'localhost' TRIGGER ea_no_delete BEFORE DELETE ON employee_assignments FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'HR_HISTORY_IMMUTABLE';
END$$
```

### `ec_no_delete`

**Déclenchement :** BEFORE DELETE ON employment_contracts, pour chaque ligne. **Contexte déclaré :** 'hr_module_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER = 'hr_module_owner'@'localhost' TRIGGER ec_no_delete BEFORE DELETE ON employment_contracts FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'HR_HISTORY_IMMUTABLE';
END$$
```

### `ea_preserve_history`

**Déclenchement :** BEFORE UPDATE ON employee_assignments, pour chaque ligne. **Contexte déclaré :** 'hr_module_owner'@'localhost'.

**Comportement / objectif :** Examen conditionnel des anciennes/nouvelles valeurs ; refus des mutations interdites. Les conditions exactes sont reproduites ci-dessous.

```sql
CREATE DEFINER = 'hr_module_owner'@'localhost' TRIGGER ea_preserve_history BEFORE UPDATE ON employee_assignments FOR EACH ROW
BEGIN
    IF NOT (NEW.id <=> OLD.id) OR NOT (NEW.employee_id <=> OLD.employee_id)
        OR NOT (NEW.department_id <=> OLD.department_id) OR NOT (NEW.position_id <=> OLD.position_id)
        OR NOT (NEW.starts_on <=> OLD.starts_on) OR NOT (NEW.ends_on <=> OLD.ends_on)
        OR NOT (NEW.created_at <=> OLD.created_at) OR NOT (NEW.created_by <=> OLD.created_by) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'HR_HISTORY_IMMUTABLE';
    END IF;
    IF NOT (NEW.closed_on <=> OLD.closed_on) OR NOT (NEW.closed_at <=> OLD.closed_at)
        OR NOT (NEW.closed_by <=> OLD.closed_by) THEN
        IF OLD.closed_on IS NOT NULL OR NEW.closed_on IS NULL OR NEW.closed_at IS NULL OR NEW.closed_by IS NULL THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'HR_ALREADY_CLOSED';
        END IF;
    END IF;
END$$
```

### `ec_preserve_history`

**Déclenchement :** BEFORE UPDATE ON employment_contracts, pour chaque ligne. **Contexte déclaré :** 'hr_module_owner'@'localhost'.

**Comportement / objectif :** Examen conditionnel des anciennes/nouvelles valeurs ; refus des mutations interdites. Les conditions exactes sont reproduites ci-dessous.

```sql
CREATE DEFINER = 'hr_module_owner'@'localhost' TRIGGER ec_preserve_history BEFORE UPDATE ON employment_contracts FOR EACH ROW
BEGIN
    IF NOT (NEW.id <=> OLD.id) OR NOT (NEW.employee_id <=> OLD.employee_id)
        OR NOT (CAST(NEW.reference AS BINARY) <=> CAST(OLD.reference AS BINARY))
        OR NOT (CAST(NEW.contract_type AS BINARY) <=> CAST(OLD.contract_type AS BINARY))
        OR NOT (NEW.starts_on <=> OLD.starts_on) OR NOT (NEW.ends_on <=> OLD.ends_on)
        OR NOT (NEW.created_at <=> OLD.created_at) OR NOT (NEW.created_by <=> OLD.created_by) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'HR_HISTORY_IMMUTABLE';
    END IF;
    IF NOT (NEW.closed_on <=> OLD.closed_on) OR NOT (NEW.closed_at <=> OLD.closed_at)
        OR NOT (NEW.closed_by <=> OLD.closed_by) THEN
        IF OLD.closed_on IS NOT NULL OR NEW.closed_on IS NULL OR NEW.closed_at IS NULL OR NEW.closed_by IS NULL THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'HR_ALREADY_CLOSED';
        END IF;
    END IF;
END$$
```

### `cr_no_update`

**Déclenchement :** BEFORE UPDATE ON compensation_requests, pour chaque ligne. **Contexte déclaré :** 'compensation_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER = 'compensation_owner'@'localhost' TRIGGER cr_no_update BEFORE UPDATE ON compensation_requests FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_IMMUTABLE';
END$$
```

### `cr_no_delete`

**Déclenchement :** BEFORE DELETE ON compensation_requests, pour chaque ligne. **Contexte déclaré :** 'compensation_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER = 'compensation_owner'@'localhost' TRIGGER cr_no_delete BEFORE DELETE ON compensation_requests FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_IMMUTABLE';
END$$
```

### `cd_no_update`

**Déclenchement :** BEFORE UPDATE ON compensation_decisions, pour chaque ligne. **Contexte déclaré :** 'compensation_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER = 'compensation_owner'@'localhost' TRIGGER cd_no_update BEFORE UPDATE ON compensation_decisions FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_IMMUTABLE';
END$$
```

### `cd_no_delete`

**Déclenchement :** BEFORE DELETE ON compensation_decisions, pour chaque ligne. **Contexte déclaré :** 'compensation_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER = 'compensation_owner'@'localhost' TRIGGER cd_no_delete BEFORE DELETE ON compensation_decisions FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_IMMUTABLE';
END$$
```

### `sc_no_update`

**Déclenchement :** BEFORE UPDATE ON salary_conditions, pour chaque ligne. **Contexte déclaré :** 'compensation_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER = 'compensation_owner'@'localhost' TRIGGER sc_no_update BEFORE UPDATE ON salary_conditions FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_IMMUTABLE';
END$$
```

### `sc_no_delete`

**Déclenchement :** BEFORE DELETE ON salary_conditions, pour chaque ligne. **Contexte déclaré :** 'compensation_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER = 'compensation_owner'@'localhost' TRIGGER sc_no_delete BEFORE DELETE ON salary_conditions FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_IMMUTABLE';
END$$
```

### `ch_no_update`

**Déclenchement :** BEFORE UPDATE ON compensation_history, pour chaque ligne. **Contexte déclaré :** 'compensation_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER = 'compensation_owner'@'localhost' TRIGGER ch_no_update BEFORE UPDATE ON compensation_history FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_IMMUTABLE';
END$$
```

### `ch_no_delete`

**Déclenchement :** BEFORE DELETE ON compensation_history, pour chaque ligne. **Contexte déclaré :** 'compensation_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER = 'compensation_owner'@'localhost' TRIGGER ch_no_delete BEFORE DELETE ON compensation_history FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_IMMUTABLE';
END$$
```

### `ec_salary_coverage`

**Déclenchement :** BEFORE UPDATE ON employment_contracts, pour chaque ligne. **Contexte déclaré :** 'compensation_owner'@'localhost'.

**Comportement / objectif :** Examen conditionnel des anciennes/nouvelles valeurs ; refus des mutations interdites. Les conditions exactes sont reproduites ci-dessous.

```sql
CREATE DEFINER = 'compensation_owner'@'localhost' TRIGGER ec_salary_coverage BEFORE UPDATE ON employment_contracts FOR EACH ROW
BEGIN
 DECLARE v_condition BIGINT UNSIGNED DEFAULT NULL;
 IF NOT (NEW.closed_on <=> OLD.closed_on) AND NEW.closed_on IS NOT NULL THEN
  BEGIN
   DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_condition=NULL;
   
   SELECT id INTO v_condition FROM salary_conditions
   WHERE contract_id=OLD.id AND effective_on>NEW.closed_on LIMIT 1 FOR SHARE;
  END;
  IF v_condition IS NOT NULL THEN
   SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='COMP_CONTRACT_COVERAGE';
  END IF;
 END IF;
END$$
```

### `payroll_periods_no_update`

**Déclenchement :** BEFORE UPDATE ON payroll_periods, pour chaque ligne. **Contexte déclaré :** 'payroll_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='payroll_owner'@'localhost' TRIGGER payroll_periods_no_update BEFORE UPDATE ON payroll_periods FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE';
END$$
```

### `payroll_periods_no_delete`

**Déclenchement :** BEFORE DELETE ON payroll_periods, pour chaque ligne. **Contexte déclaré :** 'payroll_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='payroll_owner'@'localhost' TRIGGER payroll_periods_no_delete BEFORE DELETE ON payroll_periods FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE';
END$$
```

### `payroll_inputs_no_update`

**Déclenchement :** BEFORE UPDATE ON payroll_inputs, pour chaque ligne. **Contexte déclaré :** 'payroll_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='payroll_owner'@'localhost' TRIGGER payroll_inputs_no_update BEFORE UPDATE ON payroll_inputs FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE';
END$$
```

### `payroll_inputs_no_delete`

**Déclenchement :** BEFORE DELETE ON payroll_inputs, pour chaque ligne. **Contexte déclaré :** 'payroll_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='payroll_owner'@'localhost' TRIGGER payroll_inputs_no_delete BEFORE DELETE ON payroll_inputs FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE';
END$$
```

### `payroll_input_decisions_no_update`

**Déclenchement :** BEFORE UPDATE ON payroll_input_decisions, pour chaque ligne. **Contexte déclaré :** 'payroll_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='payroll_owner'@'localhost' TRIGGER payroll_input_decisions_no_update BEFORE UPDATE ON payroll_input_decisions FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE';
END$$
```

### `payroll_input_decisions_no_delete`

**Déclenchement :** BEFORE DELETE ON payroll_input_decisions, pour chaque ligne. **Contexte déclaré :** 'payroll_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='payroll_owner'@'localhost' TRIGGER payroll_input_decisions_no_delete BEFORE DELETE ON payroll_input_decisions FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE';
END$$
```

### `payroll_calculations_no_update`

**Déclenchement :** BEFORE UPDATE ON payroll_calculations, pour chaque ligne. **Contexte déclaré :** 'payroll_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='payroll_owner'@'localhost' TRIGGER payroll_calculations_no_update BEFORE UPDATE ON payroll_calculations FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE';
END$$
```

### `payroll_calculations_no_delete`

**Déclenchement :** BEFORE DELETE ON payroll_calculations, pour chaque ligne. **Contexte déclaré :** 'payroll_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='payroll_owner'@'localhost' TRIGGER payroll_calculations_no_delete BEFORE DELETE ON payroll_calculations FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE';
END$$
```

### `payslip_events_no_update`

**Déclenchement :** BEFORE UPDATE ON payslip_events, pour chaque ligne. **Contexte déclaré :** 'payroll_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='payroll_owner'@'localhost' TRIGGER payslip_events_no_update BEFORE UPDATE ON payslip_events FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE';
END$$
```

### `payslip_events_no_delete`

**Déclenchement :** BEFORE DELETE ON payslip_events, pour chaque ligne. **Contexte déclaré :** 'payroll_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='payroll_owner'@'localhost' TRIGGER payslip_events_no_delete BEFORE DELETE ON payslip_events FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE';
END$$
```

### `payroll_approvals_no_update`

**Déclenchement :** BEFORE UPDATE ON payroll_approvals, pour chaque ligne. **Contexte déclaré :** 'payroll_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='payroll_owner'@'localhost' TRIGGER payroll_approvals_no_update BEFORE UPDATE ON payroll_approvals FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE';
END$$
```

### `payroll_approvals_no_delete`

**Déclenchement :** BEFORE DELETE ON payroll_approvals, pour chaque ligne. **Contexte déclaré :** 'payroll_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='payroll_owner'@'localhost' TRIGGER payroll_approvals_no_delete BEFORE DELETE ON payroll_approvals FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE';
END$$
```

### `payslip_corrections_no_update`

**Déclenchement :** BEFORE UPDATE ON payslip_corrections, pour chaque ligne. **Contexte déclaré :** 'settlement_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='settlement_owner'@'localhost' TRIGGER payslip_corrections_no_update BEFORE UPDATE ON payslip_corrections FOR EACH ROW BEGIN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE'; END$$
```

### `payslip_corrections_no_delete`

**Déclenchement :** BEFORE DELETE ON payslip_corrections, pour chaque ligne. **Contexte déclaré :** 'settlement_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='settlement_owner'@'localhost' TRIGGER payslip_corrections_no_delete BEFORE DELETE ON payslip_corrections FOR EACH ROW BEGIN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE'; END$$
```

### `correction_events_no_update`

**Déclenchement :** BEFORE UPDATE ON correction_events, pour chaque ligne. **Contexte déclaré :** 'settlement_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='settlement_owner'@'localhost' TRIGGER correction_events_no_update BEFORE UPDATE ON correction_events FOR EACH ROW BEGIN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE'; END$$
```

### `correction_events_no_delete`

**Déclenchement :** BEFORE DELETE ON correction_events, pour chaque ligne. **Contexte déclaré :** 'settlement_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='settlement_owner'@'localhost' TRIGGER correction_events_no_delete BEFORE DELETE ON correction_events FOR EACH ROW BEGIN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE'; END$$
```

### `recovery_requests_no_update`

**Déclenchement :** BEFORE UPDATE ON recovery_requests, pour chaque ligne. **Contexte déclaré :** 'settlement_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='settlement_owner'@'localhost' TRIGGER recovery_requests_no_update BEFORE UPDATE ON recovery_requests FOR EACH ROW BEGIN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE'; END$$
```

### `recovery_requests_no_delete`

**Déclenchement :** BEFORE DELETE ON recovery_requests, pour chaque ligne. **Contexte déclaré :** 'settlement_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='settlement_owner'@'localhost' TRIGGER recovery_requests_no_delete BEFORE DELETE ON recovery_requests FOR EACH ROW BEGIN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE'; END$$
```

### `recovery_events_no_update`

**Déclenchement :** BEFORE UPDATE ON recovery_events, pour chaque ligne. **Contexte déclaré :** 'settlement_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='settlement_owner'@'localhost' TRIGGER recovery_events_no_update BEFORE UPDATE ON recovery_events FOR EACH ROW BEGIN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE'; END$$
```

### `recovery_events_no_delete`

**Déclenchement :** BEFORE DELETE ON recovery_events, pour chaque ligne. **Contexte déclaré :** 'settlement_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='settlement_owner'@'localhost' TRIGGER recovery_events_no_delete BEFORE DELETE ON recovery_events FOR EACH ROW BEGIN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE'; END$$
```

### `settlement_ledger_no_update`

**Déclenchement :** BEFORE UPDATE ON settlement_ledger, pour chaque ligne. **Contexte déclaré :** 'settlement_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='settlement_owner'@'localhost' TRIGGER settlement_ledger_no_update BEFORE UPDATE ON settlement_ledger FOR EACH ROW BEGIN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE'; END$$
```

### `settlement_ledger_no_delete`

**Déclenchement :** BEFORE DELETE ON settlement_ledger, pour chaque ligne. **Contexte déclaré :** 'settlement_owner'@'localhost'.

**Comportement / objectif :** Refus inconditionnel de l’opération avec SIGNAL ; conservation append-only.

```sql
CREATE DEFINER='settlement_owner'@'localhost' TRIGGER settlement_ledger_no_delete BEFORE DELETE ON settlement_ledger FOR EACH ROW BEGIN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PAY_IMMUTABLE'; END$$
```

## Lecture fonctionnelle des protections historiques

`employees_preserve_identity` interdit de changer id/matricule/created_at ; la suppression est interdite séparément. `accounts_preserve_identity` protège id/employee_id/created_at, sans interdire les changements légitimes de login, empreinte ou désactivation par un opérateur autorisé. `assignments_validate_insert` exige l’instant SQL UTC courant et refuse une attribution déjà révoquée ; `assignments_preserve_history` ne permet qu’une première révocation correctement horodatée et conserve les données d’octroi. Un UPDATE strictement identique peut rester autorisé pour ce dernier trigger.

`ea_preserve_history` et `ec_preserve_history` figent les attributs d’origine et permettent une première clôture renseignée ; `ec_salary_coverage` bloque une clôture qui rendrait une date salariale approuvée extérieure au contrat. Les dates admissibles de clôture sont aussi contrôlées par CHECK et procédures.

Les tables compensation, payroll et settlement sont protégées par les paires no_update/no_delete. Le workflow s’exprime donc par ajout de versions, décisions et événements. L’unicité des décisions et des événements complète l’immutabilité ; l’absence de DML direct pour svc_php empêche de contourner le workflow simplement par une autre requête du service.
