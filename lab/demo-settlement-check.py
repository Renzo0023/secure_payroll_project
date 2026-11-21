#!/usr/bin/env python3
"""Restore a pre-demo dump and exercise actual settlement forms on a NEW isolated server."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from mysql_instance import PrivateInstance
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from private_http import Client

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--dump',type=Path,required=True);args=parser.parse_args()
    if os.geteuid()==0:raise RuntimeError('Use regular OS user; private instance only.')
    if not args.dump.is_file() or args.dump.stat().st_mode&0o077:raise RuntimeError('Private dump required.')
    count=0
    def check(ok,label):
        nonlocal count
        if not ok:raise RuntimeError('Isolated form check: '+label)
        count+=1
    with PrivateInstance(temporary_root='/var/tmp') as instance:
        service=secrets.token_urlsafe(32);application=secrets.token_urlsafe(32)
        instance.sql("CREATE USER 'svc_php'@'localhost' IDENTIFIED BY '"+service+"';")
        for owner in ['hr_module_owner','compensation_owner','payroll_owner','settlement_owner','iam_owner']:
            instance.sql("CREATE USER '"+owner+"'@'localhost' IDENTIFIED WITH caching_sha2_password AS '' ACCOUNT LOCK;")
        with args.dump.open() as dump:
            restore=subprocess.run(instance.client(),stdin=dump,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        check(restore.returncode==0,'exact pre-demo dump restores')
        for name in ['svc_php_grants','advanced_hr_owner_grants','advanced_hr_grants','compensation_owner_grants','compensation_grants','payroll_owner_grants','payroll_grants','settlement_owner_grants','settlement_grants','iam_owner_grants','iam_grants']:
            instance.sql((ROOT/'database/setup'/str(name+'.sql')).read_text())
        hashed=subprocess.run(['php','-d','display_errors=0','-d','log_errors=0','-r','echo password_hash(stream_get_contents(STDIN),PASSWORD_ARGON2ID);'],input=application,text=True,capture_output=True,check=True).stdout
        instance.sql("USE secure_payroll; UPDATE accounts SET password_hash='"+hashed+"' WHERE login='finance.demo'; INSERT INTO employees(employee_number,first_name,last_name) VALUES('PRIVATE-DEMO-PAY','Private','Payroll'); SET @p=LAST_INSERT_ID(); INSERT INTO accounts(employee_id,login,password_hash) VALUES(@p,'private.payroll','"+hashed+"'); SET @a=LAST_INSERT_ID(); INSERT INTO role_assignments(account_id,role_id,grant_reason) SELECT @a,id,'Isolated form fixture' FROM roles WHERE code='payroll_manager'; SELECT id INTO @p FROM employees WHERE employee_number='EMP-2026-001'; INSERT INTO accounts(employee_id,login,password_hash) VALUES(@p,'private.employee','"+hashed+"'); SET @a=LAST_INSERT_ID(); INSERT INTO role_assignments(account_id,role_id,grant_reason) SELECT @a,id,'Isolated form fixture' FROM roles WHERE code='employee';")
        runtime=instance.private/'http';runtime.mkdir(mode=0o700)
        with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        env=instance.env.copy();env.update(DB_HOST='localhost',DB_PORT='3306',DB_NAME='secure_payroll',DB_USER='svc_php',DB_PASSWORD=service,DB_SOCKET=str(instance.socket),APP_RUNTIME_DIR=str(runtime),SETTLEMENT_ENABLED='1',IAM_ENABLED='1')
        with (runtime/'server.log').open('w') as log:
            server=subprocess.Popen(['php','-S','127.0.0.1:'+str(port),'-t','public','public/index.php'],cwd=ROOT,env=env,stdout=log,stderr=log)
            try:
                base='http://127.0.0.1:'+str(port);payroll=Client(base);finance=Client(base);employee=Client(base)
                deadline=time.monotonic()+20
                while True:
                    try:
                        if payroll.request('/login')[0]==200:break
                    except OSError:pass
                    if time.monotonic()>deadline:raise RuntimeError('Private web unavailable')
                    time.sleep(.1)
                for client,login in [(payroll,'private.payroll'),(finance,'finance.demo'),(employee,'private.employee')]:
                    check(client.request('/login')[0]==200,'login form')
                    check(client.post('/login',login=login,password=application)[0]==303,'private real login '+login)
                    check(client.request('/payroll')[0]==200,'refresh authenticated CSRF')
                employee_id=instance.sql("SELECT id FROM secure_payroll.employees WHERE employee_number='EMP-2026-001';")
                period=instance.sql("SELECT id FROM secure_payroll.payroll_periods WHERE month_start='2026-11-01';")
                status,headers,_=payroll.post('/payroll/calculate',employee_id=employee_id,period_id=period)
                check(status==303,'calculate via HTTP');path=headers['Location']
                for actor,event in [(payroll,'verified'),(finance,'approved'),(payroll,'published')]:
                    actor.request(path);check(actor.post(path+'/transition',event=event,reason='Private form regression')[0]==303,event)
                path+='/settlement'
                finance.request(path)
                check(finance.post(path,action='pay',target='0',expected='0',reference='PRIVATE-FORM-PAY-001',reason='Private form target zero')[0]==303,'payment with actual hidden target=0')
                payroll.request(path)
                check(payroll.post(path,action='correct',target='0',expected='0',base='11100.00',bonus='0.00',deduction='0.00',reason='Private correction target zero')[0]==303,'correction with actual hidden target=0')
                correction=instance.sql('SELECT MAX(id) FROM secure_payroll.payslip_corrections;')
                for actor,action in [(payroll,'verified'),(finance,'approved'),(payroll,'published')]:
                    actor.request(path);check(actor.post(path,action=action,target=correction,expected='0',reason='Private correction workflow')[0]==303,'correction '+action)
                employee.request(path)
                for language in ['fr','en']:
                    employee.post('/language',language=language,return_to=path)
                    status,headers,body=employee.request(path)
                    check(status==200 and '<html lang="'+language+'">' in body,'employee published correction '+language)
                # Offensive/invalid scenarios stay on this isolated server.
                check(payroll.request(path,{'csrf':'invalid','action':'correct','target':'0','expected':correction,'reason':'Private CSRF'})[0]==403,'CSRF refusal isolated')
                check(finance.post(path,action='pay',target='0',expected='0',reference='PRIVATE-FORM-STALE',reason='Private stale state')[0]==409,'stale state refusal isolated')
                check(instance.sql('SELECT COUNT(*) FROM secure_payroll.settlement_ledger;')=='1','no duplicate payment after correction')
                result={'passed':True,'checks':count,'primary_connected':False,'restored_dump_sha256':hashlib.sha256(args.dump.read_bytes()).hexdigest(),'private_directory':str(instance.private),'payment_target_zero':True,'correction_target_zero':True,'correction_published':True}
                (instance.private/'demo-settlement-result.json').write_text(json.dumps(result,indent=2))
                print(json.dumps(result),flush=True)
            finally:server.terminate();server.wait(timeout=30)
    return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,RuntimeError,KeyError) as error:
        print(str(error) if isinstance(error,RuntimeError) else 'Private form verification stopped; artifacts retained.',file=sys.stderr);raise SystemExit(1)
