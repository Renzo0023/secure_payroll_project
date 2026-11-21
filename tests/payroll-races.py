#!/usr/bin/env python3
"""Real lock/contention checks in an explicitly isolated MySQL instance."""
import concurrent.futures
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def main():
    private_socket=os.environ.get('PAYROLL_TEST_SOCKET','')
    if not re.fullmatch(r'/tmp/securepayroll-mysql-[A-Za-z0-9_-]+/mysql.sock',private_socket):
        raise RuntimeError('Private socket required.')
    directory=Path(private_socket).parent/'data'
    base=['mysql','--no-defaults','--no-login-paths','--protocol=socket','--socket='+private_socket,
          '--batch','--raw','--skip-column-names','--unbuffered','--connect-timeout=3']
    cleanenv={k:v for k,v in os.environ.items() if k not in {'MYSQL_PWD','DB_PASSWORD'}}
    def run(statement,service=False):
        env=cleanenv.copy()
        if service:env['MYSQL_PWD']=os.environ['PAYROLL_TEST_PASSWORD']
        return subprocess.run([*base,'--user='+('svc_php' if service else 'root')],
                              input="SET SESSION time_zone='+00:00'; USE secure_payroll;\n"+statement,
                              text=True,capture_output=True,env=env,timeout=20)
    def sql(statement,service=False):
        result=run(statement,service)
        if result.returncode:
            code=','.join(re.findall(r'ERROR (\d+)',result.stderr)) or '?'
            raise RuntimeError('Private race check SQL error '+code)
        return result.stdout.strip()
    count=0
    def check(ok,name):
        nonlocal count
        if not ok:raise RuntimeError('Race/integrity check failed: '+name)
        count+=1
    check(Path(sql('SELECT @@datadir;')).resolve()==directory.resolve(),'private datadir')
    check(sql('SELECT @@skip_networking;')=='1','network disabled')
    spec=importlib.util.spec_from_file_location('payroll_admin',ROOT/'bin/payroll-admin.py')
    admin=importlib.util.module_from_spec(spec);spec.loader.exec_module(admin)
    admin.validate_owner_grants(sql("SHOW GRANTS FOR 'payroll_owner'@'localhost';"))
    check(True,'actual owner exact least privileges')
    check(sql("SELECT COUNT(*) FROM mysql.user WHERE User IN ('hr_module_owner','compensation_owner','payroll_owner') AND account_locked='Y';")=='3','all owner accounts locked')
    for statement in ["UPDATE payroll_calculations SET net_amount=net_amount WHERE id=3;",
                      "UPDATE payslip_events SET reason=reason WHERE calculation_id=3;",
                      "UPDATE salary_conditions SET monthly_amount=monthly_amount WHERE employee_id=4;"]:
        result=run(statement)
        check(result.returncode!=0 and ('PAY_IMMUTABLE' in result.stderr or 'COMP_IMMUTABLE' in result.stderr),'immutable financial history with privileged DML')
    check(sql("SELECT COUNT(*) FROM payslip_events WHERE calculation_id=3 AND event_type IN ('verified','approved','published');")=='3','approval/publication audit trail')
    period=int(sql("CALL payroll_period_create('2026-12-01',500.00,500.00,'Isolated concurrency policy',2);",True))
    first=int(sql(f"CALL payroll_input_submit({period},5,'bonus',300.00,'2026-12-01','2026-12-31','Race A',1);",True))
    second=int(sql(f"CALL payroll_input_submit({period},5,'bonus',300.00,'2026-12-01','2026-12-31','Race B',1);",True))

    def contend(statements):
        # A control transaction holds the same parent lock until both real sessions wait.
        control=subprocess.Popen([*base,'--user=root'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL,text=True,env=cleanenv)
        executor=concurrent.futures.ThreadPoolExecutor(max_workers=2)
        try:
            control.stdin.write("USE secure_payroll; START TRANSACTION; SELECT id FROM employees WHERE id=5 FOR UPDATE; SELECT 'LOCKED';\n")
            control.stdin.flush()
            while control.stdout.readline().strip()!='LOCKED':
                if control.poll() is not None:raise RuntimeError('Private control transaction failed.')
            futures=[executor.submit(run,statement,True) for statement in statements]
            deadline=time.monotonic()+5
            waiting=False
            while time.monotonic()<deadline:
                if int(sql("SELECT COUNT(*) FROM information_schema.INNODB_TRX WHERE trx_state='LOCK WAIT';"))>=2:
                    waiting=True;break
                time.sleep(.05)
            check(waiting,'two concurrent sessions observed waiting for parent lock')
            control.stdin.write('COMMIT;\n');control.stdin.flush()
            return [future.result(timeout=15) for future in futures]
        finally:
            try:control.communicate('ROLLBACK;\n',timeout=5)
            except (BrokenPipeError,subprocess.TimeoutExpired):pass
            executor.shutdown(wait=True)

    results=contend([f"CALL payroll_input_decide({first},'approved','Race Finance A',2);",
                     f"CALL payroll_input_decide({second},'approved','Race Finance B',2);"])
    check(sum(result.returncode==0 for result in results)==1,'concurrent cap approves only one input')
    failures=[result.stderr for result in results if result.returncode]
    check(len(failures)==1 and 'PAY_CAP' in failures[0],'second approval blocked by cumulative cap')
    check(sql(f"SELECT SUM(i.amount) FROM payroll_inputs i JOIN payroll_input_decisions d ON d.input_id=i.id AND d.decision='approved' WHERE i.period_id={period} AND i.employee_id=5;")=='300.00','approved sum remains under cap')
    undecided=int(sql(f"SELECT i.id FROM payroll_inputs i LEFT JOIN payroll_input_decisions d ON d.input_id=i.id WHERE i.period_id={period} AND d.id IS NULL;"))
    sql(f"CALL payroll_input_decide({undecided},'rejected','Cap race resolved',2);",True)
    results=contend([f'CALL payroll_calculate({period},5,3);',f'CALL payroll_calculate({period},5,3);'])
    check(all(result.returncode==0 for result in results),'concurrent calculations both serialize successfully')
    check(sql(f"SELECT GROUP_CONCAT(version_no ORDER BY version_no) FROM payroll_calculations WHERE period_id={period} AND employee_id=5;")=='1,2','unique ordered calculation versions')
    latest=int(sql(f'SELECT MAX(id) FROM payroll_calculations WHERE period_id={period} AND employee_id=5;'))
    sql(f"CALL payslip_transition({latest},'verified','Race verification',3);",True)
    results=contend([f"CALL payslip_transition({latest},'approved','Race Finance A',2);",
                     f"CALL payslip_transition({latest},'approved','Race Finance B',2);"])
    check(sum(result.returncode==0 for result in results)==1,'single approval under real concurrent decisions')
    check(sql(f'SELECT COUNT(*) FROM payroll_approvals WHERE period_id={period} AND employee_id=5;')=='1','single approved payslip per month')
    print(f'{count} real isolated concurrency, privilege and integrity checks passed.')
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (RuntimeError,OSError,subprocess.TimeoutExpired) as error:
        print(str(error) if isinstance(error,RuntimeError) else 'Private concurrency verification unavailable.',file=sys.stderr)
        sys.exit(1)
