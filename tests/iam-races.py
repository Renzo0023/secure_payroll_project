#!/usr/bin/env python3
"""Competing IAM grants and revocations on one private employee lock."""
import concurrent.futures
import os
from pathlib import Path
import re
import subprocess
import time

def main():
    sock=os.environ.get('PAYROLL_TEST_SOCKET','')
    if not re.fullmatch(r'/tmp/securepayroll-mysql-[A-Za-z0-9_-]+/mysql.sock',sock):raise RuntimeError('Private socket required')
    target=int(os.environ['IAM_TEST_TARGET'])
    base=['mysql','--no-defaults','--no-login-paths','--protocol=socket','--socket='+sock,'--batch','--raw','--skip-column-names','--unbuffered']
    clean={k:v for k,v in os.environ.items() if k not in {'MYSQL_PWD','DB_PASSWORD'}}
    def run(statement,service=False):
        env=clean.copy()
        if service:env['MYSQL_PWD']=os.environ['PAYROLL_TEST_PASSWORD']
        return subprocess.run([*base,'--user='+('svc_php' if service else 'root')],input="SET SESSION time_zone='+00:00'; USE secure_payroll;\n"+statement,text=True,capture_output=True,env=env,timeout=30)
    def sql(statement):
        result=run(statement)
        if result.returncode:raise RuntimeError('Private IAM race SQL failure')
        return result.stdout.strip()
    count=0
    def check(ok,name):
        nonlocal count
        if not ok:raise RuntimeError('IAM race failed: '+name)
        count+=1
    check(Path(sql('SELECT @@datadir;')).resolve()==(Path(sock).parent/'data').resolve(),'private datadir')
    check(sql('SELECT @@skip_networking;')=='1','no network')
    person=int(sql(f'SELECT employee_id FROM accounts WHERE id={target};'))
    def contend(statements):
        control=subprocess.Popen([*base,'--user=root'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,env=clean)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            try:
                control.stdin.write(f"USE secure_payroll; START TRANSACTION; SELECT id FROM employees WHERE id={person} FOR UPDATE; SELECT 'LOCKED';\n");control.stdin.flush()
                while control.stdout.readline().strip()!='LOCKED':
                    if control.poll() is not None:raise RuntimeError('Control lock failed')
                futures=[executor.submit(run,s,True) for s in statements];deadline=time.monotonic()+8;waiting=False
                while time.monotonic()<deadline:
                    if int(sql("SELECT COUNT(*) FROM information_schema.INNODB_TRX WHERE trx_state='LOCK WAIT';"))>=2:waiting=True;break
                    time.sleep(.05)
                check(waiting,'two grants/revocations in LOCK WAIT')
                control.stdin.write('COMMIT;\n');control.stdin.flush()
                return [future.result(timeout=25) for future in futures]
            finally:
                try:control.communicate('ROLLBACK;\n',timeout=5)
                except (BrokenPipeError,subprocess.TimeoutExpired):pass
    results=contend([f"CALL iam_grant({target},'hr_manager','Race HR grant',7);",f"CALL iam_grant({target},'finance_manager','Race Finance grant',7);"])
    check(sum(r.returncode==0 for r in results)==1,'one incompatible grant succeeds')
    check(any('IAM_CONFLICT' in r.stderr for r in results if r.returncode),'other grant denied by conflict')
    assignment=int(sql(f"SELECT MAX(ra.id) FROM role_assignments ra JOIN roles r ON r.id=ra.role_id WHERE ra.account_id={target} AND ra.revoked_at IS NULL AND r.code<>'employee';"))
    results=contend([f"CALL iam_revoke({assignment},'Race revoke A',7);",f"CALL iam_revoke({assignment},'Race revoke B',7);"])
    check(sum(r.returncode==0 for r in results)==1,'one revocation succeeds')
    check(any('IAM_STATE' in r.stderr for r in results if r.returncode),'other revocation denied')
    check(sql(f'SELECT revoked_by_account_id FROM role_assignments WHERE id={assignment};')=='7','revocation actor retained')
    print(f'{count} isolated IAM concurrency checks passed.')
    return 0
if __name__=='__main__':raise SystemExit(main())
