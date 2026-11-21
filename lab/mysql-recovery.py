#!/usr/bin/env python3
"""Backup and restore rehearsal restricted to authorized private laboratory instances."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

from mysql_instance import PrivateInstance
ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-private-dir',required=True)
    args=parser.parse_args()
    count=0
    def check(ok,name):
        nonlocal count
        if not ok:raise RuntimeError('Recovery check failed: '+name)
        count+=1
    with PrivateInstance(args.source_private_dir) as source:
        print('Recovery source private instance: '+str(source.private),flush=True)
        account='lab_backup_'+secrets.token_hex(4)
        password=secrets.token_urlsafe(32)
        source.sql("CREATE USER '"+account+"'@'localhost' IDENTIFIED BY '"+password+"'; GRANT SELECT,SHOW VIEW,TRIGGER,EVENT ON secure_payroll.* TO '"+account+"'@'localhost'; GRANT SHOW_ROUTINE ON *.* TO '"+account+"'@'localhost';")
        backups=source.private/('backup-'+secrets.token_hex(4));backups.mkdir(mode=0o700)
        # HTTP campaigns retain a separate runtime per run. Never fall back to
        # project logs, which may belong to the main application.
        runtimes=[path for path in source.private.glob('web-runtime*')
                  if path.is_dir() and not path.is_symlink()
                  and (path/'application.log').is_file()]
        if not runtimes:
            raise RuntimeError('No retained private HTTP application log; run the HTTP campaign first.')
        logs=max(runtimes,key=lambda path: path.stat().st_mtime)
        result=subprocess.run(['python3',str(ROOT/'bin/backup.py'),'--user',account,'--password-stdin',
                               '--socket',str(source.socket),'--directory',str(backups),'--logs-directory',str(logs)],
                              input=password,text=True,env=source.env)
        del password
        check(result.returncode==0,'dedicated account real backup script')
        exported=list(backups.iterdir())
        check(len(exported)==1,'unique export directory')
        backup=exported[0]
        check((backup/'EXPORT_COMPLETE').is_file(),'export success marker')
        manifest=json.loads((backup/'manifest.json').read_text())
        for name,details in manifest['files'].items():
            check(hashlib.sha256((backup/name).read_bytes()).hexdigest()==details['sha256'],'export file checksum')
        check('application.log' in manifest['files'],'security log copy retained')
        tables=source.sql("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='secure_payroll' ORDER BY TABLE_NAME;").splitlines()
        totals=source.sql('SELECT COUNT(*),SUM(net_amount) FROM secure_payroll.payroll_calculations;')
        counts={table:source.sql('SELECT COUNT(*) FROM secure_payroll.`'+table+'`;') for table in tables}
        with PrivateInstance() as restore:
            print('Recovery destination private instance: '+str(restore.private),flush=True)
            restore.sql("CREATE USER 'hr_module_owner'@'localhost' IDENTIFIED WITH caching_sha2_password AS '' ACCOUNT LOCK; CREATE USER 'compensation_owner'@'localhost' IDENTIFIED WITH caching_sha2_password AS '' ACCOUNT LOCK; CREATE USER 'payroll_owner'@'localhost' IDENTIFIED WITH caching_sha2_password AS '' ACCOUNT LOCK;")
            imported=subprocess.run(restore.client(),stdin=(backup/'database.sql').open('r'),stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,env=restore.env)
            check(imported.returncode==0,'full schema/data/routines/triggers restored')
            for table in tables:
                check(restore.sql('SELECT COUNT(*) FROM secure_payroll.`'+table+'`;')==counts[table],'restored table '+table)
            check(restore.sql('SELECT COUNT(*),SUM(net_amount) FROM secure_payroll.payroll_calculations;')==totals,'financial totals after restore')
            check(restore.sql("SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='secure_payroll';")==source.sql("SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='secure_payroll';"),'restored routines')
            check(restore.sql("SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA='secure_payroll';")==source.sql("SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA='secure_payroll';"),'restored triggers')
            restore_password=secrets.token_urlsafe(32)
            restore.sql("CREATE USER 'svc_php'@'localhost' IDENTIFIED BY '"+restore_password+"';")
            for file in ['svc_php_grants','advanced_hr_owner_grants','advanced_hr_grants','compensation_owner_grants','compensation_grants','payroll_owner_grants','payroll_grants']:
                restore.sql((ROOT/'database/setup'/(file+'.sql')).read_text())
            env=restore.env.copy();env.update(MYSQL_PWD=restore_password)
            app=subprocess.run(restore.client('svc_php'),input="SET SESSION time_zone='+00:00'; CALL secure_payroll.payslip_detail(3,4);",text=True,capture_output=True,env=env)
            check(app.returncode==0,'non-root employee read after restore')
            env.pop('MYSQL_PWD')
            protected=subprocess.run(restore.client(),input='USE secure_payroll; UPDATE payroll_calculations SET net_amount=net_amount WHERE id=3;',text=True,capture_output=True,env=restore.env)
            check(protected.returncode!=0 and 'PAY_IMMUTABLE' in protected.stderr,'immutable payroll restored')
            record={'source_private_directory':str(source.private),'restored_private_directory':str(restore.private),
                    'backup_directory':str(backup),'checks':count,'primary_instance_connected':False}
            (source.private/'recovery-result.json').write_text(json.dumps(record,indent=2));os.chmod(source.private/'recovery-result.json',0o600)
        print(f'{count} real isolated backup/restore checks passed. Both instances shut down, artifacts retained.')
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (RuntimeError,OSError,subprocess.TimeoutExpired) as error:
        print(str(error) if isinstance(error,RuntimeError) else 'Private recovery rehearsal stopped; artifacts retained.',file=sys.stderr)
        sys.exit(1)
