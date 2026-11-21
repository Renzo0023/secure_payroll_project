#!/usr/bin/env python3
"""Create and validate a NEW private MySQL instance only after explicit authorization."""
import argparse
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--initialize-isolated', action='store_true')
    parser.add_argument('--with-settlement', action='store_true', help='Also install and test NEW correction/payment objects in this fresh laboratory')
    args = parser.parse_args()
    if not args.initialize_isolated:
        parser.error('--initialize-isolated is required; no connection made')
    if os.geteuid() == 0:
        parser.error('Run as regular OS user; never sudo this laboratory')
    if input('Authorize NEW private datadir, test accounts and GRANT; no main-instance connection? Type ISOLATED: ').strip() != 'ISOLATED':
        return 2
    private = Path(tempfile.mkdtemp(prefix='securepayroll-mysql-', dir='/tmp'))
    os.chmod(private, 0o700)
    data = private / 'data'
    socket = private / 'mysql.sock'
    cleanenv = {k:v for k,v in os.environ.items() if k not in {'MYSQL_PWD','DB_PASSWORD'}}
    print('Isolated artifacts retained at ' + str(private), flush=True)
    result = subprocess.run(['/usr/sbin/mysqld', '--no-defaults', '--initialize-insecure', '--datadir='+str(data),
                             '--log-error='+str(private/'initialize.log')], capture_output=True, env=cleanenv)
    if result.returncode:
        raise RuntimeError('Private initialization failed. Review private initialize.log; nothing cleaned up.')
    server = subprocess.Popen(['/usr/sbin/mysqld','--no-defaults','--datadir='+str(data),
                               '--socket='+str(socket),'--pid-file='+str(private/'server.pid'),
                               '--skip-networking','--mysqlx=OFF','--log-error='+str(private/'server.log'),
                               '--innodb-buffer-pool-size=64M'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=cleanenv)
    try:
        def sql(statement):
            # Every administrative client uses ONLY the private socket, never defaults or TCP.
            command = ['mysql','--no-defaults','--no-login-paths','--protocol=socket','--socket='+str(socket),
                       '--user=root','--default-character-set=utf8mb4','--batch','--raw','--skip-column-names','--binary-mode']
            result = subprocess.run(command,input="SET SESSION time_zone='+00:00'; SET NAMES utf8mb4 COLLATE utf8mb4_0900_as_cs;\n"+statement,
                                    text=True,capture_output=True,env=cleanenv)
            if result.returncode:
                codes=','.join(re.findall(r'ERROR (\d+)',result.stderr)) or '?'
                # Only numeric error diagnostics, never SQL text or credentials.
                raise RuntimeError('Private MySQL error '+codes)
            return result.stdout.strip()
        deadline=time.monotonic()+45
        while not socket.exists():
            if server.poll() is not None or time.monotonic()>deadline:
                raise RuntimeError('Private MySQL did not start. Review private server.log.')
            time.sleep(0.2)
        if Path(sql('SELECT @@datadir;')).resolve()!=data.resolve() or sql('SELECT @@skip_networking;')!='1':
            raise RuntimeError('Isolation proof failed; no schema will be loaded.')
        if not sql('SELECT VERSION();').startswith('8.4.'):
            raise RuntimeError('MySQL 8.4 required.')
        service_password=secrets.token_urlsafe(32)
        sql("CREATE DATABASE secure_payroll CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs; CREATE USER 'svc_php'@'localhost' IDENTIFIED BY '"+service_password+"'; CREATE USER 'hr_module_owner'@'localhost' IDENTIFIED WITH caching_sha2_password AS '' ACCOUNT LOCK; CREATE USER 'compensation_owner'@'localhost' IDENTIFIED WITH caching_sha2_password AS '' ACCOUNT LOCK;")
        paths=['database/migrations/001_create_identity_and_rbac.sql','database/seeds/001_application_roles.sql',
               'database/migrations/002_advanced_hr.sql','database/migrations/003_hr_period_operations.sql',
               'database/patches/001_fix_hr_assert_permission_collation.sql',
               'database/migrations/004_compensation.sql','database/migrations/005_compensation_operations.sql',
               'database/migrations/006_mad_currency.sql','database/setup/svc_php_grants.sql',
               'database/setup/advanced_hr_owner_grants.sql','database/setup/advanced_hr_grants.sql',
               'database/setup/compensation_owner_grants.sql','database/setup/compensation_grants.sql',
               'database/seeds/002_hr_permissions.sql','database/seeds/003_advanced_hr_permissions.sql',
               'database/seeds/005_compensation_permissions.sql','database/setup/payroll_owner.sql',
               'database/migrations/007_payroll.sql','database/migrations/008_payroll_operations.sql',
               'database/setup/payroll_owner_grants.sql','database/seeds/006_payroll_permissions.sql',
               'database/setup/payroll_grants.sql']
        for path in paths:
            sql((ROOT/path).read_text())
            print('Private instance applied '+path,flush=True)
        random_password=secrets.token_urlsafe(32)
        hashed=subprocess.run(['php','-d','display_errors=0','-d','log_errors=0','-r',
                               'echo password_hash(stream_get_contents(STDIN),PASSWORD_ARGON2ID);'],
                              input=random_password,text=True,capture_output=True,check=True).stdout
        if not re.fullmatch(r'\$argon2id\$v=19\$m=\d+,t=\d+,p=\d+\$[A-Za-z0-9+/]+\$[A-Za-z0-9+/]+',hashed):
            raise RuntimeError('Private fictional fixture hashing failed.')
        roles=['hr_manager','finance_manager','payroll_manager','employee','employee','security_auditor','application_administrator']
        fixtures='USE secure_payroll; START TRANSACTION;'
        for i,role in enumerate(roles,1):
            fixtures+=f"INSERT INTO employees(employee_number,first_name,last_name) VALUES('LAB-{i:03d}','Fictional','Person{i}'); INSERT INTO accounts(employee_id,login,password_hash) VALUES({i},'lab{i}','{hashed}'); INSERT INTO role_assignments(account_id,role_id,grant_reason) SELECT {i},id,'Authorized isolated fictional fixture' FROM roles WHERE code='{role}';"
        fixtures+='COMMIT;'
        sql(fixtures)
        del fixtures,hashed
        env=cleanenv.copy()
        env.update(PAYROLL_TEST_SOCKET=str(socket),PAYROLL_TEST_DATADIR=str(data),PAYROLL_TEST_PASSWORD=service_password)
        test=subprocess.run(['php',str(ROOT/'tests/payroll-mysql.php'),'--isolated'],env=env)
        if test.returncode:
            return test.returncode
        webenv=env.copy()
        webenv.update(PAYROLL_TEST_APP_PASSWORD=random_password)
        webtest=subprocess.run(['python3',str(ROOT/'tests/payroll-http-live.py')],env=webenv)
        if webtest.returncode:
            return webtest.returncode
        races=subprocess.run(['python3',str(ROOT/'tests/payroll-races.py')],env=env)
        if races.returncode:
            return races.returncode
        if args.with_settlement:
            for path in ['database/setup/settlement_owner.sql','database/migrations/009_settlement.sql',
                         'database/migrations/010_settlement_operations.sql','database/setup/settlement_owner_grants.sql',
                         'database/seeds/007_settlement_permissions.sql','database/setup/settlement_grants.sql']:
                sql((ROOT/path).read_text())
                print('Private instance applied '+path,flush=True)
            settlement=subprocess.run(['php',str(ROOT/'tests/settlement-mysql.php'),'--isolated'],env=env)
            if settlement.returncode:
                return settlement.returncode
            settlement_web=subprocess.run(['python3',str(ROOT/'tests/settlement-http.py')],env=webenv)
            if settlement_web.returncode:
                return settlement_web.returncode
            settlement_races=subprocess.run(['python3',str(ROOT/'tests/settlement-races.py')],env=env)
            if settlement_races.returncode:
                return settlement_races.returncode
        del service_password,random_password
        return races.returncode
    finally:
        # Stop only the process started here. Keep all data and logs for review.
        try:
            sql('SHUTDOWN;')
        except (RuntimeError,OSError):
            print('Private SQL shutdown unavailable; retained PID requires review.',file=sys.stderr)
        try:
            server.wait(timeout=30)
        except subprocess.TimeoutExpired:
            print('Private server is still stopping. Inspect PID in retained directory; no force kill.',file=sys.stderr)


if __name__=='__main__':
    try:
        sys.exit(main())
    except (RuntimeError,OSError,EOFError,KeyboardInterrupt) as error:
        if isinstance(error,RuntimeError):
            print(str(error),file=sys.stderr)
        print('Isolated validation stopped. Retained artifacts need review; main MySQL was never targeted.',file=sys.stderr)
        sys.exit(1)
