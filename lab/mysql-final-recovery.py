#!/usr/bin/env python3
"""Exercise the administrative preinstall backup with all new modules in private instances."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import secrets
import subprocess
from mysql_instance import PrivateInstance
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source-private-dir',required=True);args=parser.parse_args()
    count=0
    def check(ok,name):
        nonlocal count
        if not ok:raise RuntimeError('Final recovery failed: '+name)
        count+=1
    spec=importlib.util.spec_from_file_location('finalize_admin',ROOT/'bin/finalize-admin.py');admin=importlib.util.module_from_spec(spec);spec.loader.exec_module(admin)
    with PrivateInstance(args.source_private_dir) as source:
        admin.admin.mysql=lambda statement:source.sql('USE secure_payroll;\n'+statement)
        admin.admin.FILES=tuple(path for module in admin.MODULES.values() for path in module['files'])
        for module in admin.MODULES.values():admin.verify(module)
        backup=admin.admin.backup_before_install(str(source.socket))
        manifest=json.loads((backup/'manifest.json').read_text())
        check(hashlib.sha256((backup/'database.sql').read_bytes()).hexdigest()==manifest['sha256'],'backup hash')
        check(manifest['consistent_snapshot'] and not manifest['restoration_tested'],'honest backup metadata')
        tables=source.sql("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='secure_payroll' ORDER BY TABLE_NAME;").splitlines()
        counts={table:source.sql('SELECT COUNT(*) FROM secure_payroll.`'+table+'`;') for table in tables}
        totals=source.sql("SELECT entry_type,SUM(amount) FROM secure_payroll.settlement_ledger GROUP BY entry_type ORDER BY entry_type;")
        # /tmp is a small tmpfs on this VM; preserve every previous artifact and
        # place this new restoration on the disk-backed temporary filesystem.
        with PrivateInstance(temporary_root='/var/tmp') as restore:
            print('Final restoration private directory: '+str(restore.private),flush=True)
            for owner in ['hr_module_owner','compensation_owner','payroll_owner','settlement_owner','iam_owner']:
                restore.sql("CREATE USER '"+owner+"'@'localhost' IDENTIFIED WITH caching_sha2_password AS '' ACCOUNT LOCK;")
            with (backup/'database.sql').open('r') as incoming:
                imported=subprocess.run(restore.client(),stdin=incoming,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,env=restore.env)
            check(imported.returncode==0,'full final dump restored')
            for table in tables:check(restore.sql('SELECT COUNT(*) FROM secure_payroll.`'+table+'`;')==counts[table],'row count '+table)
            check(restore.sql("SELECT entry_type,SUM(amount) FROM secure_payroll.settlement_ledger GROUP BY entry_type ORDER BY entry_type;")==totals,'payment and recovery totals')
            password=secrets.token_urlsafe(32)
            restore.sql("CREATE USER 'svc_php'@'localhost' IDENTIFIED BY '"+password+"';")
            for name in ['svc_php_grants','advanced_hr_owner_grants','advanced_hr_grants','compensation_owner_grants','compensation_grants','payroll_owner_grants','payroll_grants','settlement_owner_grants','settlement_grants','iam_owner_grants','iam_grants']:
                restore.sql((ROOT/'database/setup'/(name+'.sql')).read_text())
            admin.admin.mysql=lambda statement:restore.sql('USE secure_payroll;\n'+statement)
            for module in admin.MODULES.values():admin.verify(module);check(True,'restored owner and service grants')
            env=restore.env.copy();env['MYSQL_PWD']=password
            for statement in ['CALL secure_payroll.settlement_detail(3,4);','CALL secure_payroll.iam_overview(7,1);']:
                result=subprocess.run(restore.client('svc_php'),input=statement,text=True,capture_output=True,env=env)
                check(result.returncode==0,'restored non-root read')
            for table in ['payslip_corrections','settlement_ledger']:
                result=subprocess.run(restore.client(),input=f'UPDATE secure_payroll.{table} SET id=id;',text=True,capture_output=True,env=restore.env)
                check(result.returncode!=0 and 'PAY_IMMUTABLE' in result.stderr,'restored immutability')
            record={'checks':count,'source_private_directory':str(source.private),'restore_private_directory':str(restore.private),'backup':str(backup),'main_instance_connected':False}
            target=source.private/('final-recovery-'+secrets.token_hex(4)+'.json');target.write_text(json.dumps(record,indent=2)+'\n')
        print(f'{count} final-module backup/restore checks passed; both private servers stopped on exit.')
    return 0
if __name__=='__main__':raise SystemExit(main())
