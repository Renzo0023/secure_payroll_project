#!/usr/bin/env python3
"""Observe competing fictional payments and recovery receipts in actual LOCK WAIT."""
import concurrent.futures
import os
from pathlib import Path
import re
import subprocess
import time

def main():
    sock=os.environ.get('PAYROLL_TEST_SOCKET','')
    if not re.fullmatch(r'/tmp/securepayroll-mysql-[A-Za-z0-9_-]+/mysql.sock',sock):raise RuntimeError('Private socket required')
    base=['mysql','--no-defaults','--no-login-paths','--protocol=socket','--socket='+sock,'--batch','--raw','--skip-column-names','--unbuffered']
    clean={k:v for k,v in os.environ.items() if k not in {'MYSQL_PWD','DB_PASSWORD'}}
    def run(statement,service=False):
        env=clean.copy()
        if service:env['MYSQL_PWD']=os.environ['PAYROLL_TEST_PASSWORD']
        return subprocess.run([*base,'--user='+('svc_php' if service else 'root')],input="SET SESSION time_zone='+00:00'; USE secure_payroll;\n"+statement,text=True,capture_output=True,env=env,timeout=30)
    def sql(statement,service=False):
        result=run(statement,service)
        if result.returncode:raise RuntimeError('Private settlement SQL failed: '+','.join(re.findall(r'ERROR (\d+)',result.stderr)))
        return result.stdout.strip()
    count=0
    def check(ok,name):
        nonlocal count
        if not ok:raise RuntimeError('Settlement race failure: '+name)
        count+=1
    check(Path(sql('SELECT @@datadir;')).resolve()==(Path(sock).parent/'data').resolve(),'private datadir')
    check(sql('SELECT @@skip_networking;')=='1','no network')
    def command(action,target=0,expected=0,base_amount='NULL',ref='',actor=3):
        return f"CALL settlement_command(3,'{action}',{target},{expected},{base_amount},300,100,'{ref}','Private concurrency fixture',{actor});"
    def publish(base_amount):
        current=int(sql("SELECT COALESCE(MAX(c.id),0) FROM payslip_corrections c JOIN correction_events e ON e.correction_id=c.id AND e.event_type='published' WHERE c.calculation_id=3;"))
        target=int(sql(command('correct',expected=current,base_amount=base_amount),True))
        for action,actor in [('verified',3),('approved',2),('published',3)]:sql(command(action,target,current,actor=actor),True)
        return target
    def contend(statements):
        control=subprocess.Popen([*base,'--user=root'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,env=clean)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            try:
                control.stdin.write("USE secure_payroll; START TRANSACTION; SELECT id FROM employees WHERE id=4 FOR UPDATE; SELECT 'LOCKED';\n");control.stdin.flush()
                while control.stdout.readline().strip()!='LOCKED':
                    if control.poll() is not None:raise RuntimeError('Control lock failed')
                futures=[executor.submit(run,s,True) for s in statements]
                deadline=time.monotonic()+8;waiting=False
                while time.monotonic()<deadline:
                    if int(sql("SELECT COUNT(*) FROM information_schema.INNODB_TRX WHERE trx_state='LOCK WAIT';"))>=2:waiting=True;break
                    time.sleep(.05)
                check(waiting,'both sessions observed waiting')
                control.stdin.write('COMMIT;\n');control.stdin.flush()
                return [future.result(timeout=25) for future in futures]
            finally:
                try:control.communicate('ROLLBACK;\n',timeout=5)
                except (BrokenPipeError,subprocess.TimeoutExpired):pass
    current=publish('10900.00')
    results=contend([command('pay',expected=current,ref='RACE-PAYMENT-001',actor=2),command('pay',expected=current,ref='RACE-PAYMENT-002',actor=2)])
    check(sum(r.returncode==0 for r in results)==1,'only one payment')
    check(any('PAY_STATE' in r.stderr for r in results if r.returncode),'losing payment has business refusal')
    check(sql(f"SELECT COUNT(*),SUM(amount) FROM settlement_ledger WHERE correction_id={current} AND entry_type='payment';")=='1\t400.00','exact supplementary balance paid once')
    current=publish('10600.00')
    request=int(sql(command('recover_request',expected=current),True))
    sql(command('recover_approve',request,current,actor=2),True)
    results=contend([command('recover_receive',request,current,ref='RACE-RECEIPT-001'),command('recover_receive',request,current,ref='RACE-RECEIPT-002')])
    check(sum(r.returncode==0 for r in results)==1,'one recovery receipt')
    check(any('PAY_STATE' in r.stderr for r in results if r.returncode),'losing receipt has business refusal')
    check(sql(f'SELECT COUNT(*),SUM(amount) FROM settlement_ledger WHERE recovery_id={request};')=='1\t300.00','exact recovery received once')
    for table in ['payslip_corrections','correction_events','recovery_requests','recovery_events','settlement_ledger']:
        result=run(f'UPDATE {table} SET id=id;')
        check(result.returncode!=0 and 'PAY_IMMUTABLE' in result.stderr,'privileged immutability '+table)
    check(sql("SELECT account_locked FROM mysql.user WHERE User='settlement_owner' AND Host='localhost';")=='Y','owner locked')
    grants=sql("SHOW GRANTS FOR 'settlement_owner'@'localhost';")
    check('GRANT OPTION' not in grants and 'password_hash' not in grants and ' ON `secure_payroll`.*' not in grants,'no schema grants or credentials')
    check(sql('SELECT net_amount FROM payroll_calculations WHERE id=3;')=='10600.00','original unchanged')
    print(f'{count} isolated settlement concurrency and integrity checks passed.')
    return 0
if __name__=='__main__':raise SystemExit(main())
