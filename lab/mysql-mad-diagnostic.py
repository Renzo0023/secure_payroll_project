#!/usr/bin/env python3
"""Test read-only MAD diagnostics and a prepared schema-only patch on fresh private schemas."""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import secrets
import sys
from mysql_instance import PrivateInstance
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source-private-dir',required=True);args=parser.parse_args()
    count=0
    def check(ok,name):
        nonlocal count
        if not ok:raise RuntimeError('MAD lab assertion: '+name)
        count+=1
    with PrivateInstance(args.source_private_dir) as instance:
        audit=(ROOT/'database/audit/mad-readonly.sql').read_text()
        patch=(ROOT/'database/patches/002_mad_schema_guarded.sql').read_text()
        routines_before=instance.sql("SELECT ROUTINE_NAME,SHA2(ROUTINE_DEFINITION,256),DEFINER,SECURITY_TYPE FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='secure_payroll' ORDER BY ROUTINE_NAME;")
        grants_before=instance.sql("SHOW GRANTS FOR 'svc_php'@'localhost'; SHOW GRANTS FOR 'compensation_owner'@'localhost';")
        current=instance.sql(audit)
        check('MAD_ORIGINAL_VALIDATOR\t2\t2' in current,'existing fully MAD lab matches original validator')
        spec=importlib.util.spec_from_file_location('payroll_admin',ROOT/'bin/payroll-admin.py')
        admin=importlib.util.module_from_spec(spec);spec.loader.exec_module(admin)
        admin.mysql=instance.sql
        output=io.StringIO()
        with contextlib.redirect_stdout(output):admin.diagnose_mad()
        check('MAD_AMOUNTS_CURRENCY_SHA256 ' in output.getvalue(),'actual diagnostic command produces read-only fingerprint')
        def fixture(states):
            schema='mad_diagnostic_'+secrets.token_hex(4)
            instance.sql(f'CREATE DATABASE {schema} CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs;')
            for table,constraint,state in zip(['compensation_requests','salary_conditions'],['ck_cr_amount','ck_sc_amount'],states):
                modern=state=='mad';dtype='VARCHAR(3)' if state=='unknown' else ('CHAR(3)' if modern else 'CHAR(2)')
                default='MAD' if modern else 'UM'
                expression="currency IN ('MAD','UM')" if modern else "currency='UM'"
                instance.sql(f"CREATE TABLE {schema}.{table}(id BIGINT UNSIGNED PRIMARY KEY,request_id BIGINT UNSIGNED,monthly_amount DECIMAL(12,2) NOT NULL,currency {dtype} NOT NULL DEFAULT '{default}',CONSTRAINT {constraint} CHECK(monthly_amount>0 AND {expression})) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_as_cs;")
                instance.sql(f"INSERT INTO {schema}.{table} VALUES(1,1,12345.67,'UM'),(2,2,0.01,'UM');")
            return schema
        def fingerprint(schema):
            # Stream representation includes identifiers, exact decimals and recorded currencies.
            data=instance.sql('SELECT JSON_ARRAY(id,request_id,CAST(monthly_amount AS CHAR),currency) FROM '+schema+'.compensation_requests ORDER BY id; SELECT JSON_ARRAY(id,request_id,CAST(monthly_amount AS CHAR),currency) FROM '+schema+'.salary_conditions ORDER BY id;')
            return hashlib.sha256(data.encode()).hexdigest()
        def apply(schema,authorized=True):
            return instance.sql(('SET @mad_schema_repair_authorized=1;\n' if authorized else 'SET @mad_schema_repair_authorized=0;\n')+patch.replace('secure_payroll',schema))
        legacy=fixture(['legacy','legacy']);before=fingerprint(legacy)
        report=instance.sql(audit.replace('secure_payroll',legacy))
        check('MAD_ORIGINAL_VALIDATOR\t0\t2' in report,'legacy fails exact original predicate')
        check(report.count('FAIL length != 3')==2 and report.count('FAIL default != MAD or NULL')==2,'legacy failure details identify both attributes')
        try:apply(legacy,False)
        except RuntimeError:check(True,'explicit repair authorization mandatory')
        else:check(False,'unauthorized patch ran')
        check(fingerprint(legacy)==before,'refused patch leaves all values unchanged')
        apply(legacy)
        check(fingerprint(legacy)==before,'legacy UM identifiers/amounts/currencies preserved')
        check('MAD_ORIGINAL_VALIDATOR\t2\t2' in instance.sql(audit.replace('secure_payroll',legacy)),'metadata repaired')
        definitions=instance.sql(f'SHOW CREATE TABLE {legacy}.compensation_requests; SHOW CREATE TABLE {legacy}.salary_conditions;')
        repeated=apply(legacy)
        check(repeated.count('already correct; no ALTER')==2,'idempotent second application skips both ALTERs')
        check(instance.sql(f'SHOW CREATE TABLE {legacy}.compensation_requests; SHOW CREATE TABLE {legacy}.salary_conditions;')==definitions,'repeat preserves definitions')
        check(fingerprint(legacy)==before,'repeat preserves data')
        partial=fixture(['mad','legacy']);before=fingerprint(partial)
        report=instance.sql(audit.replace('secure_payroll',partial))
        check('MAD_ORIGINAL_VALIDATOR\t1\t2' in report,'partial metadata identified')
        check(apply(partial).count('already correct; no ALTER')==1,'only incomplete table altered')
        check(fingerprint(partial)==before,'partial repair preserves all existing UM values')
        unknown=fixture(['legacy','unknown'])
        before=instance.sql(f'SHOW CREATE TABLE {unknown}.compensation_requests;')
        try:apply(unknown)
        except RuntimeError:check(True,'unexpected schema refused')
        else:check(False,'unexpected schema accepted')
        check(instance.sql(f'SHOW CREATE TABLE {unknown}.compensation_requests;')==before,'global guard refuses before first ALTER')
        check(instance.sql("SELECT ROUTINE_NAME,SHA2(ROUTINE_DEFINITION,256),DEFINER,SECURITY_TYPE FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='secure_payroll' ORDER BY ROUTINE_NAME;")==routines_before,'existing lab routines unchanged')
        check(instance.sql("SHOW GRANTS FOR 'svc_php'@'localhost'; SHOW GRANTS FOR 'compensation_owner'@'localhost';")==grants_before,'existing lab privileges unchanged')
        result=instance.private/('mad-diagnostic-result-'+secrets.token_hex(4)+'.json')
        result.write_text(json.dumps({'checks':count,'main_instance_connected':False,'private_directory':str(instance.private),
            'new_schemas':[legacy,partial,unknown],'schema_patch_sha256':hashlib.sha256(patch.encode()).hexdigest()},indent=2)+'\n')
        print(f'{count} MAD diagnostic/schema-patch checks passed. New fixture schemas retained; main instance never connected.')
        print('Private source: '+str(instance.private))
    return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except (RuntimeError,OSError) as error:
        print(str(error),file=sys.stderr);raise SystemExit(1)
