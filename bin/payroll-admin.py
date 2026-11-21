#!/usr/bin/env python3
"""Explicit DBA operations for NEW payroll objects; never installs compensation."""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
TABLES = ('payroll_periods', 'payroll_inputs', 'payroll_input_decisions', 'payroll_calculations', 'payslip_events', 'payroll_approvals')
PUBLIC = ('payroll_period_create', 'payroll_input_submit', 'payroll_input_decide', 'payroll_calculate', 'payslip_transition', 'payroll_overview', 'payslip_detail')
INTERNAL = ('payroll_assert', 'payroll_build', 'payroll_read_assert')
FILES = ('database/setup/payroll_owner.sql', 'database/migrations/007_payroll.sql',
         'database/migrations/008_payroll_operations.sql', 'database/setup/payroll_owner_grants.sql',
         'database/seeds/006_payroll_permissions.sql', 'database/setup/payroll_grants.sql')


def mysql(sql):
    env = {k: v for k, v in os.environ.items() if k not in {'MYSQL_PWD', 'DB_PASSWORD'}}
    result = subprocess.run(['mysql', '--no-defaults', '--no-login-paths', '--protocol=socket', '--user=root',
                             '--database=secure_payroll', '--default-character-set=utf8mb4', '--batch',
                             '--raw', '--skip-column-names', '--binary-mode'],
                            input="SET SESSION time_zone='+00:00'; SET SESSION sql_mode='STRICT_ALL_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,NO_BACKSLASH_ESCAPES';\n" + sql,
                            text=True, capture_output=True, env=env)
    if result.returncode:
        codes = ','.join(re.findall(r'ERROR (\d+)', result.stderr)) or '?'
        raise RuntimeError('MySQL error codes: ' + codes + '. Stop; no automatic replay or cleanup.')
    return result.stdout.strip()


def quote(value):
    return "'" + value.replace("'", "''") + "'"


def names(values):
    return ','.join(quote(value) for value in values)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def service_grants():
    tables = {'employees', 'accounts', 'roles', 'permissions', 'role_permissions', 'role_assignments',
              'departments', 'positions', 'employee_assignments', 'employment_contracts',
              'compensation_requests', 'compensation_decisions', 'compensation_history', 'salary_conditions'}
    routines = set(PUBLIC) | {'hr_create_assignment', 'hr_close_assignment', 'hr_create_contract',
                             'hr_close_contract', 'compensation_submit', 'compensation_decide',
                             'settlement_command', 'settlement_detail', 'iam_overview', 'iam_grant', 'iam_revoke'}
    grants = mysql("SHOW GRANTS FOR 'svc_php'@'localhost';")
    for line in grants.splitlines():
        require('WITH GRANT OPTION' not in line, 'Service must not delegate privileges.')
        if re.fullmatch(r'GRANT USAGE ON \*\.\* TO .+', line):
            continue
        routine = re.fullmatch(r'GRANT EXECUTE ON PROCEDURE `secure_payroll`\.`([^`]+)` TO .+', line)
        if routine and routine[1] in routines:
            continue
        table = re.fullmatch(r'GRANT (.+) ON `secure_payroll`\.`([^`]+)` TO .+', line)
        require(table and table[2] in tables, 'Unexpected service privilege or inherited role.')
        for privilege in re.split(r',\s*(?![^()]*\))', table[1]):
            match = re.fullmatch(r'(SELECT|INSERT|UPDATE)(?:\s*\(([^()]*)\))?', privilege)
            require(match is not None, 'Unexpected service table privilege.')
            if match[1] == 'SELECT':
                continue
            columns = {col.strip().strip('`') for col in (match[2] or '').split(',')}
            allowed = {'INSERT': {'employee_number', 'first_name', 'last_name'}, 'UPDATE': {'first_name', 'last_name'}}
            require(table[2] == 'employees' and '' not in columns and columns <= allowed[match[1]], 'Excessive service DML.')
    require(mysql("SELECT COUNT(*) FROM mysql.proxies_priv WHERE User='svc_php';") == '0', 'Unexpected service proxy privilege.')


def prerequisites():
    require(mysql('SELECT VERSION();').startswith('8.4.'), 'This installer targets MySQL 8.4 only.')
    require(mysql('SELECT @@global.mandatory_roles;') in ('', 'NONE'), 'Review mandatory roles first.')
    require(mysql("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='secure_payroll' AND TABLE_NAME IN ('employees','accounts','roles','permissions','role_permissions','role_assignments','employment_contracts','compensation_requests','compensation_decisions','compensation_history','salary_conditions') AND ENGINE='InnoDB';") == '11', 'Installed identity/HR/compensation tables required.')
    mad_matches = mysql("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='secure_payroll' AND TABLE_NAME IN ('compensation_requests','salary_conditions') AND COLUMN_NAME='currency' AND CHARACTER_MAXIMUM_LENGTH=3 AND COLUMN_DEFAULT='MAD';")
    if mad_matches != '2':
        print('MAD original validator: ' + mad_matches + '/2 matching columns.', flush=True)
        print(mysql("SELECT n.table_name,COALESCE(c.COLUMN_TYPE,'MISSING'),COALESCE(c.COLUMN_DEFAULT,'NULL'),IF(c.CHARACTER_MAXIMUM_LENGTH=3,'length OK','length FAIL'),IF(c.COLUMN_DEFAULT='MAD','default OK','default FAIL') FROM (SELECT 'compensation_requests' AS table_name UNION ALL SELECT 'salary_conditions') n LEFT JOIN information_schema.COLUMNS c ON c.TABLE_SCHEMA='secure_payroll' AND c.TABLE_NAME=n.table_name AND c.COLUMN_NAME='currency';"), flush=True)
        raise RuntimeError('MAD schema not confirmed. Do not automatically replay migration 006. Run diagnose-mad for read-only details.')
    require(mysql("SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='secure_payroll' AND ROUTINE_NAME IN ('compensation_submit','compensation_decide') AND DEFINER='compensation_owner@localhost' AND SECURITY_TYPE='DEFINER' AND LOCATE(CHAR(39,77,65,68,39),ROUTINE_DEFINITION)>0;") == '2', 'MAD public compensation routines not confirmed; inspect partial installation without replay.')
    require(mysql("SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='secure_payroll' AND ROUTINE_NAME='compensation_check_period' AND DEFINER='compensation_owner@localhost' AND SECURITY_TYPE='DEFINER' AND LOCATE('COMP_CURRENCY_REVIEW',ROUTINE_DEFINITION)>0 AND LOCATE(CHAR(39,77,65,68,39),ROUTINE_DEFINITION)>0;") == '1', 'MAD period helper not confirmed; legacy UM salaries must not be reinterpreted.')
    require(mysql("SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS tc JOIN information_schema.CHECK_CONSTRAINTS cc ON cc.CONSTRAINT_SCHEMA=tc.CONSTRAINT_SCHEMA AND cc.CONSTRAINT_NAME=tc.CONSTRAINT_NAME WHERE tc.TABLE_SCHEMA='secure_payroll' AND tc.CONSTRAINT_TYPE='CHECK' AND tc.ENFORCED='YES' AND ((tc.TABLE_NAME='compensation_requests' AND tc.CONSTRAINT_NAME='ck_cr_amount') OR (tc.TABLE_NAME='salary_conditions' AND tc.CONSTRAINT_NAME='ck_sc_amount')) AND LOWER(REGEXP_REPLACE(REPLACE(REPLACE(cc.CHECK_CLAUSE,CHAR(92),''),'_utf8mb4',''),'[[:space:]`()]+',''))='monthly_amount>0andcurrencyin''mad'',''um''';") == '2', 'MAD amount/currency CHECK constraints not confirmed; no installation allowed.')
    require(mysql("SELECT COUNT(*) FROM accounts WHERE login='finance.demo' AND disabled_at IS NULL;") == '1', 'Existing Finance demo account required; no bootstrap will be replayed.')
    require(mysql("SELECT COUNT(*) FROM roles WHERE code IN ('employee','hr_manager','payroll_manager','finance_manager','application_administrator','security_auditor');") == '6', 'Six existing roles required.')
    service_grants()


def validate_owner_grants(grants):
    """Require the exact dedicated privilege set, including column restrictions."""
    expected = {
        'employees': {'SELECT': {'id','employee_number','first_name','last_name','archived_at'}, 'UPDATE': {'id'}},
        'accounts': {'SELECT': {'id','employee_id','disabled_at'}},
        'roles': {'SELECT': {'id','code'}},
        'permissions': {'SELECT': {'id','code'}},
        'role_permissions': {'SELECT': {'role_id','permission_id'}},
        'role_assignments': {'SELECT': {'account_id','role_id','valid_from','expires_at','revoked_at'}},
        'employment_contracts': {'SELECT': {'id','employee_id','starts_on','effective_ends_on'}},
        'salary_conditions': {'SELECT': {'id','employee_id','contract_id','request_id','decision_id','monthly_amount','currency','effective_on'}},
        'compensation_requests': {'SELECT': {'id','employee_id','contract_id','monthly_amount','currency','effective_on','requester_employee_id'}},
        'compensation_decisions': {'SELECT': {'id','request_id','decision','approver_employee_id'}},
    }
    for table in TABLES:
        expected[table] = {'SELECT': None, 'INSERT': None, 'TRIGGER': None}
    actual = {}
    routines = set()
    for line in grants.splitlines():
        require('WITH GRANT OPTION' not in line, 'Owner must not delegate privileges.')
        if re.fullmatch(r'GRANT USAGE ON \*\.\* TO .+', line):
            continue
        routine = re.fullmatch(r'GRANT EXECUTE ON PROCEDURE `secure_payroll`\.`([^`]+)` TO .+', line)
        if routine:
            require(routine[1] in PUBLIC + INTERNAL, 'Unexpected owner routine privilege.')
            routines.add(routine[1])
            continue
        table = re.fullmatch(r'GRANT (.+) ON `secure_payroll`\.`([^`]+)` TO .+', line)
        require(table and table[2] in expected, 'Unexpected owner privilege, schema scope or inherited role.')
        privileges = actual.setdefault(table[2], {})
        for privilege in re.split(r',\s*(?![^()]*\))', table[1]):
            match = re.fullmatch(r'(SELECT|INSERT|UPDATE|TRIGGER)(?:\s*\(([^()]*)\))?', privilege)
            require(match is not None, 'Unexpected owner table privilege.')
            columns = None if match[2] is None else {column.strip().strip('`') for column in match[2].split(',')}
            require(match[1] in expected[table[2]] and columns == expected[table[2]][match[1]],
                    'Owner column/table privilege differs from the dedicated allowlist.')
            privileges[match[1]] = columns
    require(actual == expected and routines == set(PUBLIC + INTERNAL), 'Owner required grants incomplete.')


def verify():
    require(mysql("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='secure_payroll' AND TABLE_NAME IN (" + names(TABLES) + ") AND ENGINE='InnoDB' AND TABLE_COLLATION='utf8mb4_0900_as_cs';") == '6', 'Payroll tables incomplete.')
    require(mysql("SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='secure_payroll' AND ROUTINE_NAME IN (" + names(PUBLIC + INTERNAL) + ") AND DEFINER='payroll_owner@localhost' AND SECURITY_TYPE='DEFINER';") == '10', 'Payroll routines incomplete.')
    require(mysql("SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA='secure_payroll' AND EVENT_OBJECT_TABLE IN (" + names(TABLES) + ") AND DEFINER='payroll_owner@localhost';") == '12', 'Immutability triggers incomplete.')
    require(mysql("SELECT account_locked FROM mysql.user WHERE User='payroll_owner' AND Host='localhost';") == 'Y', 'Owner must be locked.')
    service_grants()
    validate_owner_grants(mysql("SHOW GRANTS FOR 'payroll_owner'@'localhost';"))
    require(mysql("SELECT COUNT(*) FROM mysql.proxies_priv WHERE User='payroll_owner';") == '0', 'Unexpected owner proxy privilege.')
    print('Payroll structure/definers/lock/service grants verified. Business workflow NOT tested.')


def backup_before_install(private_socket=None):
    """Consistent InnoDB snapshot; the operator must keep application/DDL quiescent."""
    require(mysql("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='secure_payroll' AND TABLE_TYPE='BASE TABLE' AND ENGINE<>'InnoDB';") == '0',
            'Non-InnoDB tables detected; arrange a DBA backup before installation.')
    private = Path(tempfile.mkdtemp(prefix='securepayroll-preinstall-', dir='/var/tmp'))
    os.chmod(private, 0o700)
    dump = private / 'database.partial.sql'
    env = {k: v for k, v in os.environ.items() if k not in {'MYSQL_PWD', 'DB_PASSWORD'}}
    endpoint = []
    if private_socket is not None:
        require(re.fullmatch(r'/tmp/securepayroll-mysql-[A-Za-z0-9_-]+/mysql.sock', private_socket) is not None,
                'Only an explicit private laboratory socket is allowed for a backup rehearsal.')
        require(Path(mysql('SELECT @@datadir;')).resolve() == (Path(private_socket).parent / 'data').resolve(),
                'Private backup datadir mismatch.')
        endpoint = ['--socket=' + private_socket]
    with dump.open('xb') as output:
        os.chmod(dump, 0o600)
        result = subprocess.run(['mysqldump', '--no-defaults', '--no-login-paths', '--protocol=socket', '--user=root', *endpoint,
                                 '--single-transaction', '--quick', '--routines', '--triggers', '--events',
                                 '--hex-blob', '--no-tablespaces', '--set-gtid-purged=OFF', '--databases', 'secure_payroll'],
                                stdout=output, stderr=subprocess.PIPE, env=env)
        output.flush()
        os.fsync(output.fileno())
    require(result.returncode == 0 and dump.stat().st_size > 0,
            'Backup failed; partial artifact retained at ' + str(private) + '. No migration applied.')
    dump.rename(private / 'database.sql')
    digest = hashlib.sha256()
    with (private / 'database.sql').open('rb') as incoming:
        for block in iter(lambda: incoming.read(1024 * 1024), b''):
            digest.update(block)
    manifest = {'created_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'database': 'secure_payroll', 'sha256': digest.hexdigest(),
                'bytes': (private / 'database.sql').stat().st_size,
                'consistent_snapshot': True, 'restoration_tested': False,
                'files_to_apply': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in FILES}}
    with (private / 'manifest.json').open('x') as output:
        os.chmod(private / 'manifest.json', 0o600)
        json.dump(manifest, output, indent=2)
        output.flush()
        os.fsync(output.fileno())
    print('Preinstallation snapshot retained at ' + str(private), flush=True)
    return private


def assert_uninstalled():
    collisions = mysql("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='secure_payroll' AND TABLE_NAME IN (" + names(TABLES) + ");")
    require(collisions == '0', 'Payroll table already present. Refuse replay; inspect partial/existing installation.')
    require(mysql("SELECT COUNT(*) FROM mysql.user WHERE User='payroll_owner';") == '0', 'Owner already exists; refuse replay.')
    require(mysql("SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='secure_payroll' AND ROUTINE_NAME IN (" + names(PUBLIC + INTERNAL) + ");") == '0', 'Routine collision; refuse replay.')
    trigger_names = tuple(table + '_no_' + op for table in TABLES for op in ('update', 'delete'))
    require(mysql("SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA='secure_payroll' AND TRIGGER_NAME IN (" + names(trigger_names) + ");") == '0', 'Trigger collision; refuse replay.')


def install():
    prerequisites()
    assert_uninstalled()
    scripts = [(path, (ROOT / path).read_text()) for path in FILES]
    print('NEW payroll objects only; no compensation installation or account recreation.')
    for path, script in scripts:
        print(path + '  SHA256 ' + hashlib.sha256(script.encode()).hexdigest())
    require(input('With application writes and DDL stopped, type secure_payroll to authorize snapshot then NEW DDL and GRANT: ').strip() == 'secure_payroll', 'Cancelled.')
    backup_before_install()
    # Repeat the read-only preflight after the dump; no historical migration replay.
    prerequisites()
    assert_uninstalled()
    require(all((ROOT / path).read_text() == script for path, script in scripts), 'Installation files changed during backup; no migration applied.')
    for path, script in scripts:
        mysql(script)
        print('Applied ' + path, flush=True)
    verify()


def demo(role):
    prerequisites()
    verify()
    identities = {'payroll_manager': ('payroll.demo', 'DEMO-PAY-001', 'Payroll'),
                  'employee': ('employee.demo', 'DEMO-EMP-001', 'Employee'),
                  'security_auditor': ('audit.demo', 'DEMO-AUD-001', 'Audit'),
                  'application_administrator': ('admin.demo', 'DEMO-ADM-001', 'Admin')}
    login, number, surname = identities[role]
    require(mysql('SELECT (SELECT COUNT(*) FROM accounts WHERE login=' + quote(login) + ') + (SELECT COUNT(*) FROM employees WHERE employee_number=' + quote(number) + ');') == '0', 'Demo identity already exists. No overwrite.')
    require(input(f'Create ONLY fictional {login} with role {role}? Type secure_payroll: ').strip() == 'secure_payroll', 'Cancelled.')
    password = getpass.getpass('New password (12+ characters): ')
    require(len(password) >= 12 and '\x00' not in password, 'Password policy not satisfied.')
    require(password == getpass.getpass('Confirm password: '), 'Password mismatch.')
    process = subprocess.run(['php', '-d', 'display_errors=0', '-d', 'log_errors=0', '-d', 'zend.exception_ignore_args=1', '-r',
                              '$p=stream_get_contents(STDIN); echo password_hash($p,PASSWORD_ARGON2ID);'],
                             input=password, text=True, capture_output=True)
    del password
    encoded = process.stdout
    require(process.returncode == 0 and re.fullmatch(r'\$argon2id\$v=19\$m=\d+,t=\d+,p=\d+\$[A-Za-z0-9+/]+\$[A-Za-z0-9+/]+', encoded), 'Hash generation failed.')
    mysql("START TRANSACTION; INSERT INTO employees(employee_number,first_name,last_name) VALUES(" + quote(number) + ",'Demo'," + quote(surname) + "); SET @demo_person=LAST_INSERT_ID(); INSERT INTO accounts(employee_id,login,password_hash) VALUES(@demo_person," + quote(login) + ',' + quote(encoded) + "); SET @demo_account=LAST_INSERT_ID(); INSERT INTO role_assignments(account_id,role_id,grant_reason) SELECT @demo_account,id,'Authorized fictional local demonstration bootstrap' FROM roles WHERE code=" + quote(role) + '; COMMIT;')
    del encoded
    print('Created ' + login + '. No existing account changed.')


DEMO_ROLES = {'rh.demo': 'hr_manager', 'finance.demo': 'finance_manager',
              'payroll.demo': 'payroll_manager', 'employee.demo': 'employee',
              'admin.demo': 'application_administrator', 'audit.demo': 'security_auditor'}


def demo_inventory():
    """Public identity metadata only; never return a password hash."""
    people = [json.loads(row) for row in mysql("SELECT JSON_OBJECT('id',e.id,'number',e.employee_number,'archived',e.archived_at,'login',a.login,'account_id',a.id,'disabled',a.disabled_at) FROM employees e LEFT JOIN accounts a ON a.employee_id=e.id WHERE e.employee_number='EMP-2026-001' OR a.login IN (" + names(DEMO_ROLES) + ") ORDER BY e.id;").splitlines()]
    assignments = [json.loads(row) for row in mysql("SELECT JSON_OBJECT('login',a.login,'role',r.code) FROM accounts a JOIN role_assignments ra ON ra.account_id=a.id JOIN roles r ON r.id=ra.role_id WHERE (a.login IN (" + names(DEMO_ROLES) + ") OR a.employee_id=(SELECT id FROM employees WHERE employee_number='EMP-2026-001')) AND ra.valid_from<=UTC_TIMESTAMP(6) AND (ra.expires_at IS NULL OR ra.expires_at>UTC_TIMESTAMP(6)) AND (ra.revoked_at IS NULL OR ra.revoked_at>UTC_TIMESTAMP(6)) ORDER BY a.login,r.code;").splitlines()]
    nadia = next((p for p in people if p['number']=='EMP-2026-001'), None)
    require(nadia is not None and nadia['archived'] is None, 'Active Nadia EMP-2026-001 required; no employee will be recreated.')
    employee_login = nadia['login'] or 'employee.demo'
    require(employee_login not in {'rh.demo','finance.demo','payroll.demo','admin.demo','audit.demo'}, 'Nadia cannot share a staff identity; no reassignment allowed.')
    existing_employee = next((p for p in people if p['login']=='employee.demo'), None)
    require(existing_employee is None or existing_employee['id']==nadia['id'], 'employee.demo belongs to another immutable identity; no reassignment or duplicate allowed.')
    expected = {**DEMO_ROLES}
    if employee_login!='employee.demo':
        del expected['employee.demo'];expected[employee_login]='employee'
    for login, role in expected.items():
        person = next((p for p in people if p['login']==login), None)
        if person:
            require(person['disabled'] is None and person['archived'] is None, 'Inactive existing demo identity: '+login)
            require({a['role'] for a in assignments if a['login']==login}=={role}, 'Existing role mismatch/conflict: '+login+'; no role will be silently changed.')
    present=[p['id'] for p in people if p['login'] in expected]
    require(len(present)==len(set(present)), 'Demo identities must remain distinct.')
    return {'people':people,'roles':assignments,'employee_login':employee_login,
            'missing':[login for login in expected if not any(p['login']==login for p in people)]}


def provision_demo(hashes):
    """Only missing accounts; Argon2id hashes arrive over stdin, no clear secrets."""
    prerequisites();verify()
    state=demo_inventory()
    require('rh.demo' not in state['missing'] and 'finance.demo' not in state['missing'], 'Existing RH/Finance identities required.')
    require(isinstance(hashes,dict) and set(hashes)==set(state['missing']), 'Account inventory changed; no account created.')
    for encoded in hashes.values():
        require(isinstance(encoded,str) and re.fullmatch(r'\$argon2id\$v=19\$m=\d+,t=\d+,p=\d+\$[A-Za-z0-9+/]+\$[A-Za-z0-9+/]+',encoded), 'Invalid Argon2id hash.')
    if not hashes:return state
    backup_before_install()
    require(demo_inventory()==state,'Account inventory changed during backup; no account created.')
    sql=['START TRANSACTION;']
    for login,encoded in hashes.items():
        role=DEMO_ROLES[login]
        if login=='employee.demo':
            sql.append("SELECT id INTO @demo_person FROM employees WHERE employee_number='EMP-2026-001' AND archived_at IS NULL FOR UPDATE;")
        else:
            number,surname={'payroll.demo':('DEMO-PAY-001','Payroll'),'admin.demo':('DEMO-ADM-001','Admin'),'audit.demo':('DEMO-AUD-001','Audit')}[login]
            # Existing unassociated identities are not reused or overwritten.
            sql.append('INSERT INTO employees(employee_number,first_name,last_name) VALUES('+quote(number)+",'Demo',"+quote(surname)+'); SET @demo_person=LAST_INSERT_ID();')
        sql.append('INSERT INTO accounts(employee_id,login,password_hash) VALUES(@demo_person,'+quote(login)+','+quote(encoded)+'); SET @demo_account=LAST_INSERT_ID();')
        sql.append("INSERT INTO role_assignments(account_id,role_id,grant_reason) SELECT @demo_account,id,'Authorized academic presentation account provisioning' FROM roles WHERE code="+quote(role)+';')
    sql.append('COMMIT;')
    mysql('\n'.join(sql))
    result=demo_inventory();require(not result['missing'],'Account provisioning incomplete; inspect without overwriting.')
    return result


def diagnose_mad():
    print(mysql((ROOT / 'database/audit/mad-readonly.sql').read_text()), flush=True)
    financial_rows = mysql("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY; SELECT payload FROM (SELECT 'compensation_requests' AS table_name,id,JSON_ARRAY('compensation_requests',id,CAST(monthly_amount AS CHAR),currency) AS payload FROM secure_payroll.compensation_requests UNION ALL SELECT 'salary_conditions',id,JSON_ARRAY('salary_conditions',id,CAST(monthly_amount AS CHAR),currency) FROM secure_payroll.salary_conditions) financial_snapshot ORDER BY table_name,id; COMMIT;")
    print('MAD_AMOUNTS_CURRENCY_SHA256 ' + hashlib.sha256(financial_rows.encode()).hexdigest(), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['inspect', 'diagnose-mad', 'install', 'create-demo', 'demo-inventory', 'provision-demo'])
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--role', choices=['payroll_manager', 'employee', 'security_auditor', 'application_administrator'])
    args = parser.parse_args()
    require(os.geteuid() == 0, 'DBA operation requires explicit interactive sudo; nothing executed.')
    if args.command=='demo-inventory':
        print(json.dumps(demo_inventory()));return
    if args.command=='provision-demo':
        require(args.apply,'--apply required; no account created.')
        print(json.dumps(provision_demo(json.load(sys.stdin))));return
    if args.command == 'diagnose-mad':
        diagnose_mad()
        return
    if args.command == 'inspect':
        print('Existing migration-object inventory (read only):')
        print(mysql("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='secure_payroll' ORDER BY TABLE_NAME;"))
        print(mysql("SELECT ROUTINE_NAME,DEFINER,SECURITY_TYPE FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='secure_payroll' ORDER BY ROUTINE_NAME;"))
        prerequisites()
        count = mysql("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='secure_payroll' AND TABLE_NAME IN (" + names(TABLES) + ');')
        print('Confirmed installed compensation tables, Finance identity and MAD columns. Payroll tables: ' + count + '/6.')
        if count == '6':
            verify()
    else:
        require(args.apply and sys.stdin.isatty(), '--apply and an interactive terminal are required.')
        if args.command == 'install':
            install()
        else:
            require(args.role is not None, '--role is required.')
            demo(args.role)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, EOFError, KeyboardInterrupt) as error:
        if isinstance(error, RuntimeError):
            print(str(error), file=sys.stderr)
        else:
            print('Operation interrupted/unavailable. Inspect existing state before retrying.', file=sys.stderr)
        sys.exit(1)
