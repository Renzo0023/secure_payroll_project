#!/usr/bin/env python3
"""Install NEW IAM objects and test them only in a stopped, private lab instance."""
import argparse
import importlib.util
import os
from pathlib import Path
import re
import secrets
import subprocess
from mysql_instance import PrivateInstance
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source-private-dir',required=True)
    parser.add_argument('--resume-tests',action='store_true',help='Do not install/replay any object; verify already installed objects then run unconsumed fixtures')
    args=parser.parse_args()
    with PrivateInstance(args.source_private_dir) as instance:
        password=secrets.token_urlsafe(32);application=secrets.token_urlsafe(32)
        hashed=subprocess.run(['php','-r','echo password_hash(stream_get_contents(STDIN),PASSWORD_ARGON2ID);'],input=application,text=True,capture_output=True,check=True).stdout
        if not re.fullmatch(r'\$argon2id\$v=19\$m=\d+,t=\d+,p=\d+\$[A-Za-z0-9+/]+\$[A-Za-z0-9+/]+',hashed):raise RuntimeError('Fixture hash failed')
        # Fresh extension only: any object collision is a hard stop, never a replay.
        if not args.resume_tests:
            if instance.sql("SELECT COUNT(*) FROM mysql.user WHERE User='iam_owner';")!='0':raise RuntimeError('IAM owner already exists; refuse replay')
            for path in ['database/setup/iam_owner.sql','database/migrations/011_iam_operations.sql','database/setup/iam_owner_grants.sql','database/seeds/008_iam_permissions.sql','database/setup/iam_grants.sql']:
                instance.sql((ROOT/path).read_text());print('Private IAM applied '+path,flush=True)
        instance.sql("ALTER USER 'svc_php'@'localhost' IDENTIFIED BY '"+password+"'; UPDATE secure_payroll.accounts SET password_hash='"+hashed+"' WHERE login REGEXP '^lab[1-7]$' OR login IN ('iam-target','iam-future','iam-disabled','iam-archived','iam-expired');")
        env=instance.env.copy();env.update(PAYROLL_TEST_SOCKET=str(instance.socket),PAYROLL_TEST_DATADIR=str(instance.data),PAYROLL_TEST_PASSWORD=password,PAYROLL_TEST_APP_PASSWORD=application)
        for label in ['TARGET','FUTURE','DISABLED','ARCHIVED','EXPIRED']:
            if args.resume_tests:
                ids=instance.sql(f"SELECT id FROM secure_payroll.accounts WHERE login='iam-{label.lower()}';")
                if not ids.isdigit():raise RuntimeError('Missing retained fixture')
            else:
                ids=instance.sql(f"USE secure_payroll; INSERT INTO employees(employee_number,first_name,last_name) VALUES('IAM-{label}','Fictional','Identity'); SET @person=LAST_INSERT_ID(); INSERT INTO accounts(employee_id,login,password_hash) VALUES(@person,'iam-{label.lower()}','{hashed}'); SELECT LAST_INSERT_ID();")
            env['IAM_TEST_'+label]=ids
        if not args.resume_tests:
            instance.sql("USE secure_payroll; INSERT INTO role_assignments(account_id,role_id,valid_from,grant_reason) SELECT "+env['IAM_TEST_FUTURE']+",id,UTC_TIMESTAMP(6)+INTERVAL 1 DAY,'Future fictional role' FROM roles WHERE code='finance_manager'; UPDATE accounts SET disabled_at=UTC_TIMESTAMP(6) WHERE id="+env['IAM_TEST_DISABLED']+"; UPDATE employees e JOIN accounts a ON a.employee_id=e.id SET e.archived_at=UTC_TIMESTAMP(6) WHERE a.id="+env['IAM_TEST_ARCHIVED']+"; INSERT INTO role_assignments(account_id,role_id,expires_at,grant_reason) SELECT "+env['IAM_TEST_EXPIRED']+",id,UTC_TIMESTAMP(6)+INTERVAL 1 MICROSECOND,'Expired fictional role' FROM roles WHERE code='finance_manager';")
        spec=importlib.util.spec_from_file_location('finalize_admin',ROOT/'bin/finalize-admin.py');admin=importlib.util.module_from_spec(spec);spec.loader.exec_module(admin)
        admin.admin.mysql=lambda statement:instance.sql('USE secure_payroll;\n'+statement)
        for module in admin.MODULES.values():admin.verify(module)
        for command in [['php',str(ROOT/'tests/iam-mysql.php'),'--isolated'],['python3',str(ROOT/'tests/iam-http.py')],['python3',str(ROOT/'tests/iam-races.py')]]:
            result=subprocess.run(command,env=env)
            if result.returncode:return result.returncode
    return 0
if __name__=='__main__':raise SystemExit(main())
