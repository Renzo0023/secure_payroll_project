#!/usr/bin/env python3
"""Démonstration locale : préparation administrative explicite, vérification et serveur."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import warnings

ROOT = Path(__file__).resolve().parents[1]
MESSAGES = {}
LANGUAGE = 'fr'


def t(key, **values):
    text = MESSAGES['setup.' + key]
    for name, value in values.items():
        text = text.replace(':' + name, str(value))
    return text


def secret(key):
    if not sys.stdin.isatty():
        raise RuntimeError(t('terminal'))
    warnings.simplefilter('error', getpass.GetPassWarning)
    return getpass.getpass(t(key))


def confirmed_secret(key):
    value = secret(key)
    if not value.strip() or len(value) < 12 or len(value.encode()) > 4096 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise RuntimeError(t('password_policy'))
    if value != secret('confirm_password'):
        raise RuntimeError(t('password_mismatch'))
    return value


def quote(value):
    # Toutes les sessions administratives utilisent NO_BACKSLASH_ESCAPES.
    return "'" + value.replace("'", "''") + "'"


def mysql(sql):
    environment = {k: v for k, v in os.environ.items() if k not in {'MYSQL_PWD', 'DB_PASSWORD'}}
    result = subprocess.run(
        ['mysql', '--no-defaults', '--no-login-paths', '--protocol=socket', '--user=root',
         '--database=secure_payroll', '--default-character-set=utf8mb4', '--batch',
         '--raw', '--skip-column-names', '--binary-mode'],
        input="SET SESSION sql_mode='STRICT_ALL_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,NO_BACKSLASH_ESCAPES'; SET SESSION time_zone='+00:00';\n" + sql,
        text=True, capture_output=True, env=environment)
    if result.returncode:
        codes = re.findall(r'ERROR (\d+)', result.stderr)
        raise RuntimeError(t('mysql_error', code=','.join(codes) or '?'))
    # Ne jamais afficher les requêtes, stderr brut, secrets ou empreintes.
    return result.stdout.strip()


def install(apply):
    if not apply:
        raise RuntimeError(t('apply_required'))
    if os.geteuid() != 0:
        raise RuntimeError(t('admin_required'))
    tables = mysql("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='secure_payroll' AND TABLE_NAME IN ('employees','accounts','roles','permissions','role_permissions','role_assignments') AND ENGINE='InnoDB' ORDER BY TABLE_NAME;")
    if tables.splitlines() != ['accounts', 'employees', 'permissions', 'role_assignments', 'role_permissions', 'roles']:
        raise RuntimeError(t('schema_missing'))
    if mysql("SELECT COUNT(*) FROM mysql.user WHERE User='svc_php';") != '0':
        raise RuntimeError(t('svc_exists'))
    if mysql("SELECT @@global.mandatory_roles;") not in ['', 'NONE']:
        raise RuntimeError(t('mandatory_roles'))
    if mysql("SELECT COUNT(*) FROM roles WHERE code='hr_manager' AND name='HR Manager';") != '1':
        raise RuntimeError(t('role_missing'))
    if mysql("SELECT (SELECT COUNT(*) FROM employees WHERE employee_number='DEMO-HR-001') + (SELECT COUNT(*) FROM accounts WHERE login='rh.demo');") != '0':
        raise RuntimeError(t('demo_exists'))
    print(t('plan'), flush=True)
    if input(t('confirm_target')).strip() != 'secure_payroll':
        raise RuntimeError(t('cancelled'))
    service_password = confirmed_secret('service_password')
    hr_password = confirmed_secret('hr_password')
    if service_password == hr_password:
        raise RuntimeError(t('password_distinct'))
    hash_process = subprocess.run(
        ['php', '-d', 'display_errors=0', '-d', 'log_errors=0', '-d', 'zend.exception_ignore_args=1',
         '-r', '$p=stream_get_contents(STDIN); echo password_hash($p, PASSWORD_ARGON2ID);'],
        input=hr_password, text=True, capture_output=True)
    del hr_password
    password_hash = hash_process.stdout
    if hash_process.returncode or not re.fullmatch(r'\$argon2id\$v=19\$m=\d+,t=\d+,p=\d+\$[A-Za-z0-9+/]+\$[A-Za-z0-9+/]+', password_hash):
        raise RuntimeError(t('argon_failed'))
    # Aucun rejeu de migration et aucune recréation des six rôles.
    mysql((ROOT / 'database/seeds/002_hr_permissions.sql').read_text())
    if mysql("SELECT COUNT(DISTINCT p.code) FROM roles r JOIN role_permissions rp ON rp.role_id=r.id JOIN permissions p ON p.id=rp.permission_id WHERE r.code='hr_manager' AND p.code IN ('employees.read','employees.create','employees.update');") != '3':
        raise RuntimeError(t('permissions_missing'))
    mysql("CREATE USER 'svc_php'@'localhost' IDENTIFIED BY " + quote(service_password) + ';\n'
          + (ROOT / 'database/setup/svc_php_grants.sql').read_text())
    del service_password
    mysql("""START TRANSACTION;
SET @demo_role_id=NULL;
SELECT id INTO @demo_role_id FROM roles WHERE code='hr_manager' FOR UPDATE;
INSERT INTO employees (employee_number, first_name, last_name) VALUES ('DEMO-HR-001','Demo','RH');
SET @demo_employee_id=LAST_INSERT_ID();
INSERT INTO accounts (employee_id, login, password_hash) VALUES (@demo_employee_id,'rh.demo',""" + quote(password_hash) + """);
SET @demo_account_id=LAST_INSERT_ID();
INSERT INTO role_assignments (account_id, role_id, granted_at, valid_from, grant_reason)
VALUES (@demo_account_id,@demo_role_id,CURRENT_TIMESTAMP(6),CURRENT_TIMESTAMP(6),'Local demonstration bootstrap authorized by terminal operator');
COMMIT;""")
    del password_hash
    print(t('installed'), flush=True)


def environment():
    if os.geteuid() == 0:
        raise RuntimeError(t('normal_user'))
    password = secret('service_password')
    if not password:
        raise RuntimeError(t('password_policy'))
    return dict(os.environ, DB_HOST='localhost', DB_PORT='3306', DB_NAME='secure_payroll',
                DB_USER='svc_php', DB_PASSWORD=password)


def check_service_grants(grants):
    """Refus conservateur de droits globaux, rôles SQL, DML historique ou DDL."""
    tables = {'employees', 'accounts', 'roles', 'permissions', 'role_permissions',
              'role_assignments', 'departments', 'positions', 'employee_assignments', 'employment_contracts',
              'compensation_requests', 'compensation_decisions', 'salary_conditions', 'compensation_history'}
    routines = {'hr_create_assignment', 'hr_close_assignment', 'hr_create_contract', 'hr_close_contract',
                'compensation_submit', 'compensation_decide', 'payroll_period_create', 'payroll_input_submit',
                'payroll_input_decide', 'payroll_calculate', 'payslip_transition', 'payroll_overview', 'payslip_detail'}
    employee_columns = {'INSERT': {'employee_number', 'first_name', 'last_name'},
                        'UPDATE': {'first_name', 'last_name'}}
    if not grants.strip():
        raise RuntimeError(t('hr_service_rights'))
    for line in grants.splitlines():
        if 'WITH GRANT OPTION' in line:
            raise RuntimeError(t('hr_service_rights'))
        if re.fullmatch(r'GRANT USAGE ON \*\.\* TO .+', line):
            continue
        routine = re.fullmatch(r'GRANT EXECUTE ON PROCEDURE `secure_payroll`\.`([^`]+)` TO .+', line)
        if routine and routine[1] in routines:
            continue
        table = re.fullmatch(r'GRANT (.+) ON `secure_payroll`\.`([^`]+)` TO .+', line)
        if not table or table[2] not in tables:
            raise RuntimeError(t('hr_service_rights'))
        for privilege in re.split(r',\s*(?![^()]*\))', table[1]):
            match = re.fullmatch(r'(SELECT|INSERT|UPDATE)(?:\s*\(([^()]*)\))?', privilege)
            if not match:
                raise RuntimeError(t('hr_service_rights'))
            if match[1] == 'SELECT':
                continue
            columns = {column.strip().strip('`') for column in (match[2] or '').split(',')}
            if table[2] != 'employees' or not columns <= employee_columns[match[1]] or '' in columns:
                raise RuntimeError(t('hr_service_rights'))


def activate_hr(apply, with_demo_catalogues):
    if not apply:
        raise RuntimeError(t('apply_required'))
    if os.geteuid() != 0:
        raise RuntimeError(t('admin_required'))
    if mysql("SELECT COUNT(*) FROM mysql.user WHERE User='svc_php' AND Host='localhost';") != '1':
        raise RuntimeError(t('hr_service_missing'))
    if mysql("SELECT @@global.mandatory_roles;") not in ['', 'NONE']:
        raise RuntimeError(t('mandatory_roles'))
    check_service_grants(mysql("SHOW GRANTS FOR 'svc_php'@'localhost';"))
    collision = mysql("""SELECT
        (SELECT COUNT(*) FROM mysql.user WHERE User='hr_module_owner') +
        (SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='secure_payroll'
            AND TABLE_NAME IN ('departments','positions','employee_assignments','employment_contracts')) +
        (SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='secure_payroll'
            AND ROUTINE_NAME IN ('hr_assert_permission','hr_create_assignment','hr_close_assignment','hr_create_contract','hr_close_contract')) +
        (SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA='secure_payroll'
            AND TRIGGER_NAME IN ('ea_no_delete','ec_no_delete','ea_preserve_history','ec_preserve_history'));""")
    if collision != '0':
        raise RuntimeError(t('hr_collision'))
    if mysql("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='secure_payroll' AND ENGINE='InnoDB' AND TABLE_NAME IN ('employees','accounts','roles','permissions','role_permissions','role_assignments');") != '6':
        raise RuntimeError(t('schema_missing'))
    if mysql("SELECT COUNT(*) FROM roles WHERE code='hr_manager' AND name='HR Manager';") != '1':
        raise RuntimeError(t('role_missing'))
    paths = ['database/setup/advanced_hr_owner.sql',
             'database/migrations/002_advanced_hr.sql', 'database/migrations/003_hr_period_operations.sql',
             'database/setup/advanced_hr_owner_grants.sql', 'database/seeds/003_advanced_hr_permissions.sql',
             'database/setup/advanced_hr_grants.sql']
    if with_demo_catalogues:
        paths.append('database/seeds/004_hr_reference_demo.sql')
    scripts = [(path, (ROOT / path).read_text()) for path in paths]
    for path, sql in scripts:
        if '/migrations/' in path:
            expected = 4 if path.endswith('002_advanced_hr.sql') else 5
            if sql.count("CREATE DEFINER = 'hr_module_owner'@'localhost'") != expected:
                raise RuntimeError(t('hr_owner_invalid'))
    print(t('hr_plan'), flush=True)
    for path, _ in scripts:
        print('  ' + path, flush=True)
    if input(t('confirm_target')).strip() != 'secure_payroll':
        raise RuntimeError(t('cancelled'))
    for path, sql in scripts:
        mysql(sql)
        print(t('hr_file_applied', file=path), flush=True)
    if mysql("SELECT account_locked FROM mysql.user WHERE User='hr_module_owner' AND Host='localhost';") != 'Y':
        raise RuntimeError(t('hr_owner_invalid'))
    if mysql("SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='secure_payroll' AND ROUTINE_NAME IN ('hr_assert_permission','hr_create_assignment','hr_close_assignment','hr_create_contract','hr_close_contract') AND DEFINER='hr_module_owner@localhost' AND SECURITY_TYPE='DEFINER';") != '5':
        raise RuntimeError(t('hr_owner_invalid'))
    if mysql("SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA='secure_payroll' AND TRIGGER_NAME IN ('ea_no_delete','ec_no_delete','ea_preserve_history','ec_preserve_history') AND DEFINER='hr_module_owner@localhost';") != '4':
        raise RuntimeError(t('hr_owner_invalid'))
    check_service_grants(mysql("SHOW GRANTS FOR 'svc_php'@'localhost';"))
    if mysql("SELECT COUNT(DISTINCT p.code) FROM roles r JOIN role_permissions rp ON rp.role_id=r.id JOIN permissions p ON p.id=rp.permission_id WHERE r.code='hr_manager' AND p.code IN ('departments.read','positions.read','assignments.read','assignments.create','assignments.close','contracts.read','contracts.create','contracts.close');") != '8':
        raise RuntimeError(t('hr_permissions_missing'))
    print(t('hr_activated'), flush=True)



def require_compensation_admin(apply):
    if not apply:
        raise RuntimeError(t('apply_required'))
    if os.geteuid() != 0:
        raise RuntimeError(t('admin_required'))
    if mysql("SELECT @@global.mandatory_roles;") not in ['', 'NONE']:
        raise RuntimeError(t('mandatory_roles'))
    if mysql("SELECT COUNT(*) FROM mysql.user WHERE User='svc_php' AND Host='localhost';") != '1':
        raise RuntimeError(t('hr_service_missing'))
    check_service_grants(mysql("SHOW GRANTS FOR 'svc_php'@'localhost';"))


def verify_compensation():
    if mysql("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='secure_payroll' AND TABLE_NAME IN ('compensation_requests','salary_conditions') AND COLUMN_NAME='currency' AND COLUMN_DEFAULT='MAD' AND CHARACTER_MAXIMUM_LENGTH=3;") != '2':
        raise RuntimeError(t('comp_invalid'))
    if mysql("SELECT account_locked FROM mysql.user WHERE User='compensation_owner' AND Host='localhost';") != 'Y':
        raise RuntimeError(t('comp_invalid'))
    if mysql("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='secure_payroll' AND TABLE_NAME IN ('compensation_requests','compensation_decisions','salary_conditions','compensation_history') AND ENGINE='InnoDB' AND TABLE_COLLATION='utf8mb4_0900_as_cs';") != '4':
        raise RuntimeError(t('comp_invalid'))
    if mysql("SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='secure_payroll' AND ROUTINE_NAME IN ('compensation_assert_permission','compensation_check_period','compensation_submit','compensation_decide') AND DEFINER='compensation_owner@localhost' AND SECURITY_TYPE='DEFINER';") != '4':
        raise RuntimeError(t('comp_invalid'))
    if mysql("SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA='secure_payroll' AND TRIGGER_NAME IN ('cr_no_update','cr_no_delete','cd_no_update','cd_no_delete','sc_no_update','sc_no_delete','ch_no_update','ch_no_delete','ec_salary_coverage') AND DEFINER='compensation_owner@localhost';") != '9':
        raise RuntimeError(t('comp_invalid'))
    if mysql("SELECT COUNT(*) FROM information_schema.PARAMETERS WHERE SPECIFIC_SCHEMA='secure_payroll' AND SPECIFIC_NAME='compensation_assert_permission' AND PARAMETER_NAME='p_permission' AND COLLATION_NAME='utf8mb4_0900_as_cs';") != '1':
        raise RuntimeError(t('comp_invalid'))
    if mysql("SELECT COUNT(*) FROM roles r JOIN role_permissions rp ON rp.role_id=r.id JOIN permissions p ON p.id=rp.permission_id WHERE (r.code='hr_manager' AND p.code IN ('compensation.read','compensation.submit')) OR (r.code='finance_manager' AND p.code IN ('compensation.read','compensation.decide'));") != '4':
        raise RuntimeError(t('comp_invalid'))
    check_service_grants(mysql("SHOW GRANTS FOR 'svc_php'@'localhost';"))


def activate_compensation(apply):
    require_compensation_admin(apply)
    if mysql("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='secure_payroll' AND ENGINE='InnoDB' AND TABLE_NAME IN ('employees','accounts','roles','permissions','role_permissions','role_assignments','departments','positions','employee_assignments','employment_contracts');") != '10':
        raise RuntimeError(t('comp_missing'))
    if mysql("SELECT COUNT(*) FROM roles WHERE (code='hr_manager' AND name='HR Manager') OR (code='finance_manager' AND name='Finance Manager');") != '2':
        raise RuntimeError(t('comp_missing'))
    if mysql("SELECT COUNT(*) FROM information_schema.PARAMETERS WHERE SPECIFIC_SCHEMA='secure_payroll' AND SPECIFIC_NAME='hr_assert_permission' AND PARAMETER_NAME='p_permission' AND COLLATION_NAME='utf8mb4_0900_as_cs';") != '1':
        raise RuntimeError(t('comp_missing'))
    if mysql("""SELECT (SELECT COUNT(*) FROM mysql.user WHERE User='compensation_owner') +
        (SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='secure_payroll' AND TABLE_NAME IN ('compensation_requests','compensation_decisions','salary_conditions','compensation_history')) +
        (SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='secure_payroll' AND ROUTINE_NAME IN ('compensation_assert_permission','compensation_check_period','compensation_submit','compensation_decide')) +
        (SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA='secure_payroll' AND TRIGGER_NAME IN ('cr_no_update','cr_no_delete','cd_no_update','cd_no_delete','sc_no_update','sc_no_delete','ch_no_update','ch_no_delete','ec_salary_coverage'));""") != '0':
        raise RuntimeError(t('comp_collision'))
    paths = ['database/setup/compensation_owner.sql', 'database/migrations/004_compensation.sql',
             'database/migrations/005_compensation_operations.sql', 'database/migrations/006_mad_currency.sql',
             'database/setup/compensation_owner_grants.sql',
             'database/seeds/005_compensation_permissions.sql', 'database/setup/compensation_grants.sql']
    scripts = [(path, (ROOT / path).read_text()) for path in paths]
    for path, sql in scripts:
        if '/migrations/' in path and sql.count("CREATE DEFINER = 'compensation_owner'@'localhost'") != ({'004_compensation.sql': 9, '005_compensation_operations.sql': 4, '006_mad_currency.sql': 3}[Path(path).name]):
            raise RuntimeError(t('comp_invalid'))
    print(t('comp_plan'), flush=True)
    for path, _ in scripts:
        print('  ' + path, flush=True)
    if input(t('confirm_target')).strip() != 'secure_payroll':
        raise RuntimeError(t('cancelled'))
    for path, sql in scripts:
        mysql(sql)
        print(t('hr_file_applied', file=path), flush=True)
    verify_compensation()
    print(t('comp_activated'), flush=True)


def create_finance_demo(apply):
    require_compensation_admin(apply)
    verify_compensation()
    if mysql("SELECT COUNT(*) FROM roles WHERE code='finance_manager' AND name='Finance Manager';") != '1':
        raise RuntimeError(t('role_missing'))
    if mysql("SELECT (SELECT COUNT(*) FROM employees WHERE employee_number='DEMO-FIN-001') + (SELECT COUNT(*) FROM accounts WHERE login='finance.demo');") != '0':
        raise RuntimeError(t('finance_exists'))
    print(t('finance_plan'), flush=True)
    if input(t('confirm_target')).strip() != 'secure_payroll':
        raise RuntimeError(t('cancelled'))
    password = confirmed_secret('finance_password')
    process = subprocess.run(['php', '-d', 'display_errors=0', '-d', 'log_errors=0',
        '-d', 'zend.exception_ignore_args=1', '-r',
        '$p=stream_get_contents(STDIN); echo password_hash($p, PASSWORD_ARGON2ID);'],
        input=password, text=True, capture_output=True)
    del password
    password_hash = process.stdout
    if process.returncode or not re.fullmatch(r'\$argon2id\$v=19\$m=\d+,t=\d+,p=\d+\$[A-Za-z0-9+/]+\$[A-Za-z0-9+/]+', password_hash):
        raise RuntimeError(t('argon_failed'))
    # Nouvelle personne exclusivement : aucune réutilisation d'un compte RH.
    mysql("""START TRANSACTION;
SET @finance_role_id=NULL;
SELECT id INTO @finance_role_id FROM roles WHERE code='finance_manager' AND name='Finance Manager' FOR UPDATE;
INSERT INTO employees(employee_number,first_name,last_name) VALUES('DEMO-FIN-001','Demo','Finance');
SET @finance_person=LAST_INSERT_ID();
INSERT INTO accounts(employee_id,login,password_hash) VALUES(@finance_person,'finance.demo',""" + quote(password_hash) + """);
SET @finance_account=LAST_INSERT_ID();
INSERT INTO role_assignments(account_id,role_id,granted_at,valid_from,grant_reason)
VALUES(@finance_account,@finance_role_id,CURRENT_TIMESTAMP(6),CURRENT_TIMESTAMP(6),'Authorized local Finance demonstration bootstrap');
COMMIT;""")
    del password_hash
    # Contrôle exécuté après COMMIT avant tout message de succès.
    if mysql("""SELECT COUNT(*) FROM accounts a JOIN employees e ON e.id=a.employee_id
        JOIN role_assignments ra ON ra.account_id=a.id JOIN roles r ON r.id=ra.role_id
        WHERE a.login='finance.demo' AND e.employee_number='DEMO-FIN-001' AND r.code='finance_manager'
        AND a.disabled_at IS NULL AND e.archived_at IS NULL AND ra.valid_from<=UTC_TIMESTAMP(6)
        AND (ra.expires_at IS NULL OR ra.expires_at>UTC_TIMESTAMP(6)) AND ra.revoked_at IS NULL;""") != '1':
        raise RuntimeError(t('comp_invalid'))
    print(t('finance_created'), flush=True)


def main():
    global MESSAGES, LANGUAGE
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['install', 'check', 'serve', 'activate-hr', 'activate-compensation', 'create-finance-demo'])
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--lang', choices=['fr', 'en'], default='fr')
    parser.add_argument('--with-demo-catalogues', action='store_true')
    args = parser.parse_args()
    LANGUAGE = args.lang
    result = subprocess.run(['php', '-r', 'echo json_encode(require $argv[1], JSON_THROW_ON_ERROR);',
                             str(ROOT / 'lang' / (LANGUAGE + '.php'))], capture_output=True, text=True)
    if result.returncode:
        sys.exit(1)
    MESSAGES = json.loads(result.stdout)
    os.chdir(ROOT)
    if args.action == 'install':
        install(args.apply)
    elif args.action == 'activate-compensation':
        activate_compensation(args.apply)
    elif args.action == 'create-finance-demo':
        create_finance_demo(args.apply)
    elif args.action == 'activate-hr':
        activate_hr(args.apply, args.with_demo_catalogues)
    else:
        env = environment()
        if args.action == 'check':
            hr_password = secret('hr_password')
            result = subprocess.run(['php', 'bin/check-demo.php'], env=env,
                                    input=json.dumps({'password': hr_password, 'language': LANGUAGE}), text=True)
            sys.exit(result.returncode)
        print(t('serving'), flush=True)
        os.execvpe('php', ['php', '-S', '127.0.0.1:8080', '-t', 'public', 'public/index.php'], env)


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print(t('cancelled') if MESSAGES else '', file=sys.stderr)
        sys.exit(1)
    except Exception:
        print(t('unexpected') if MESSAGES else '', file=sys.stderr)
        sys.exit(1)
