#!/usr/bin/env python3
"""Additional real business-integrity refusals in an authorized private instance only."""
import argparse
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
        if not ok:raise RuntimeError('Isolated security check failed: '+name)
        count+=1
    with PrivateInstance(args.source_private_dir) as instance:
        password=secrets.token_urlsafe(32)
        instance.sql("ALTER USER 'svc_php'@'localhost' IDENTIFIED BY '"+password+"';")
        env=instance.env.copy();env['MYSQL_PWD']=password
        def call(statement):
            return subprocess.run(instance.client('svc_php'),input="SET SESSION time_zone='+00:00'; USE secure_payroll;\n"+statement,
                                  text=True,capture_output=True,env=env,timeout=15)
        def public(statement):
            result=call(statement)
            if result.returncode:raise RuntimeError('Private public procedure unexpectedly failed; no driver message printed.')
            return result.stdout.strip()
        def denied(statement,token):
            result=call(statement)
            check(result.returncode!=0 and token in result.stderr,token)
        prefix='LAB-SEC-'+secrets.token_hex(4)
        def person(label):
            return int(instance.sql(f"USE secure_payroll; INSERT INTO employees(employee_number,first_name,last_name) VALUES('{prefix}-{label}','Fictional','Security'); SELECT LAST_INSERT_ID();"))
        def contract(employee):
            return int(public(f"CALL hr_create_contract({employee},'{prefix}-{employee}','permanent','2026-11-03',NULL,1);"))
        def request(employee,contract_id,amount='12000.00'):
            return int(public(f"CALL compensation_submit({employee},{contract_id},{amount},'2026-11-03','Private security fixture',1);"))
        finance_contract=contract(2)
        own_request=request(2,finance_contract)
        denied(f"CALL compensation_decide({own_request},'approved','Own salary forbidden',2);",'COMP_SELF_APPROVAL')
        period=int(instance.sql("SELECT id FROM secure_payroll.payroll_periods WHERE month_start='2026-11-01';"))
        denied(f'CALL payroll_calculate({period},3,3);','PAY_FORBIDDEN')
        own_input=int(public(f"CALL payroll_input_submit({period},2,'bonus',10.00,'2026-11-01','2026-11-30','Own Finance input',1);"))
        denied(f"CALL payroll_input_decide({own_input},'approved','Own beneficiary forbidden',2);",'PAY_FORBIDDEN')
        missing=person('MISSING');missing_contract=contract(missing)
        denied(f'CALL payroll_calculate({period},{missing},3);','PAY_SALARY')
        pending=request(missing,missing_contract)
        denied(f'CALL payroll_calculate({period},{missing},3);','PAY_SALARY')
        public(f"CALL compensation_decide({pending},'rejected','No approved salary created',2);")
        denied(f'CALL payroll_calculate({period},{missing},3);','PAY_SALARY')
        outside=int(public(f"CALL payroll_input_submit({period},{missing},'paid_leave',0,'2026-11-01','2026-11-02','Outside contract',1);"))
        denied(f"CALL payroll_input_decide({outside},'approved','Invalid coverage',2);",'PAY_COVERAGE')
        public(f"CALL payroll_input_decide({outside},'rejected','Coverage rejected',2);")
        legacy=person('UM');legacy_contract=contract(legacy)
        instance.sql(f"""USE secure_payroll; START TRANSACTION;
            INSERT INTO compensation_requests(employee_id,contract_id,request_kind,monthly_amount,currency,effective_on,justification,requested_by,requester_employee_id)
            VALUES({legacy},{legacy_contract},'initial',12000.00,'UM','2026-11-03','Historical fictional UM fixture',1,1);
            SET @req=LAST_INSERT_ID();
            INSERT INTO compensation_decisions(request_id,decision,reason,decided_by,approver_employee_id)
            VALUES(@req,'approved','Historical independent approval',2,2); SET @dec=LAST_INSERT_ID();
            INSERT INTO salary_conditions(employee_id,contract_id,request_id,decision_id,monthly_amount,currency,effective_on)
            VALUES({legacy},{legacy_contract},@req,@dec,12000.00,'UM','2026-11-03');
            INSERT INTO compensation_history(request_id,event_type,actor_id) VALUES(@req,'submitted',1),(@req,'approved',2);
            COMMIT;""")
        denied(f'CALL payroll_calculate({period},{legacy},3);','PAY_SALARY')
        denied(f"CALL compensation_submit({legacy},{legacy_contract},12000,'2026-12-01','No implicit conversion',1);",'COMP_CURRENCY_REVIEW')
        check(instance.sql(f"SELECT CONCAT(monthly_amount,' ',currency) FROM secure_payroll.salary_conditions WHERE employee_id={legacy};")=='12000.00 UM','UM amount and currency preserved')
        low=person('LOW');low_contract=contract(low);low_request=request(low,low_contract,'1.00')
        public(f"CALL compensation_decide({low_request},'approved','Low fictional salary approved',2);")
        reduction=int(public(f"CALL payroll_input_submit({period},{low},'deduction',10.00,'2026-11-01','2026-11-30','Negative net test',1);"))
        public(f"CALL payroll_input_decide({reduction},'approved','Within explicit cap',2);")
        denied(f'CALL payroll_calculate({period},{low},3);','PAY_NET')
        check(instance.sql(f'SELECT COUNT(*) FROM secure_payroll.payroll_calculations WHERE employee_id={low};')=='0','failed calculation leaves no version')
        assignment=int(instance.sql("USE secure_payroll; INSERT INTO role_assignments(account_id,role_id,grant_reason) SELECT 1,id,'Private incompatible-role test' FROM roles WHERE code='finance_manager'; SELECT LAST_INSERT_ID();"))
        denied('CALL payroll_overview(1,1);','PAY_FORBIDDEN')
        denied(f"CALL compensation_submit({missing},{missing_contract},12000,'2026-11-03','Conflict test',1);",'COMP_FORBIDDEN')
        instance.sql(f"USE secure_payroll; UPDATE role_assignments SET revoked_at=CURRENT_TIMESTAMP(6),revoked_by_account_id=7,revocation_reason='End of private role conflict test' WHERE id={assignment};")
        check(call('CALL payroll_overview(1,1);').returncode==0,'revoked incompatible role no longer authorizes/blocks')
        future=int(instance.sql("USE secure_payroll; INSERT INTO role_assignments(account_id,role_id,valid_from,expires_at,grant_reason) SELECT 1,id,DATE_ADD(CURRENT_TIMESTAMP(6),INTERVAL 1 DAY),DATE_ADD(CURRENT_TIMESTAMP(6),INTERVAL 2 DAY),'Private future role test' FROM roles WHERE code='finance_manager'; SELECT LAST_INSERT_ID();"))
        check(call('CALL payroll_overview(1,1);').returncode==0,'future role grants no active authority or conflict')
        instance.sql(f"USE secure_payroll; UPDATE role_assignments SET revoked_at=CURRENT_TIMESTAMP(6),revoked_by_account_id=7,revocation_reason='End of private future role test' WHERE id={future};")
        instance.sql('UPDATE secure_payroll.accounts SET disabled_at=UTC_TIMESTAMP(6) WHERE id=6;')
        denied('CALL payroll_overview(6,1);','PAY_FORBIDDEN')
        instance.sql('UPDATE secure_payroll.accounts SET disabled_at=NULL WHERE id=6;')
        check(call('CALL payroll_overview(6,1);').returncode==0,'re-enabled lab auditor retains intended read')
        report=instance.private/'security-result.json'
        report.write_text(json.dumps({'checks':count,'private_directory':str(instance.private),'primary_instance_connected':False},indent=2));os.chmod(report,0o600)
        print(f'{count} additional real MySQL business-integrity and security checks passed.')
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (RuntimeError,OSError,subprocess.TimeoutExpired) as error:
        print(str(error) if isinstance(error,RuntimeError) else 'Private security verification stopped; artifacts retained.',file=sys.stderr)
        sys.exit(1)
