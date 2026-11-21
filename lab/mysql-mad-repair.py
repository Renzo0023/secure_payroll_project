#!/usr/bin/env python3
"""Fresh 001-005 laboratory, historical UM fixtures, exact backup restoration and targeted MAD repair."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from unittest import mock
from mysql_instance import PrivateInstance
ROOT=Path(__file__).resolve().parents[1]

def main():
 spec=importlib.util.spec_from_file_location('mad_repair',ROOT/'bin/mad-repair.py');repair=importlib.util.module_from_spec(spec);spec.loader.exec_module(repair)
 count=0
 def check(ok,label):
  nonlocal count
  if not ok:raise RuntimeError('MAD repair assertion: '+label)
  count+=1
 with PrivateInstance(temporary_root='/var/tmp') as instance:
  print('Fresh representative legacy instance: '+str(instance.private),flush=True)
  db=repair.Client(str(instance.socket));service=secrets.token_urlsafe(32)
  db.sql("CREATE DATABASE secure_payroll CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs; CREATE USER 'svc_php'@'localhost' IDENTIFIED BY '"+service+"'; CREATE USER 'hr_module_owner'@'localhost' IDENTIFIED WITH caching_sha2_password AS '' ACCOUNT LOCK; CREATE USER 'compensation_owner'@'localhost' IDENTIFIED WITH caching_sha2_password AS '' ACCOUNT LOCK;")
  for path in ['database/migrations/001_create_identity_and_rbac.sql','database/seeds/001_application_roles.sql','database/migrations/002_advanced_hr.sql','database/migrations/003_hr_period_operations.sql','database/patches/001_fix_hr_assert_permission_collation.sql','database/migrations/004_compensation.sql','database/migrations/005_compensation_operations.sql','database/setup/svc_php_grants.sql','database/setup/advanced_hr_owner_grants.sql','database/setup/advanced_hr_grants.sql','database/setup/compensation_owner_grants.sql','database/setup/compensation_grants.sql','database/seeds/002_hr_permissions.sql','database/seeds/003_advanced_hr_permissions.sql','database/seeds/005_compensation_permissions.sql']:
   db.sql((ROOT/path).read_text())
  password=secrets.token_urlsafe(32)
  hashed=subprocess.run(['php','-r','echo password_hash(stream_get_contents(STDIN),PASSWORD_ARGON2ID);'],input=password,text=True,capture_output=True,check=True).stdout
  require_hash=re.fullmatch(r'\$argon2id\$v=19\$m=\d+,t=\d+,p=\d+\$[A-Za-z0-9+/]+\$[A-Za-z0-9+/]+',hashed)
  check(bool(require_hash),'fixture password hash')
  for i,role in enumerate(['hr_manager','finance_manager','employee','employee','employee','payroll_manager','security_auditor','application_administrator'],1):
   login={1:'rh.demo',2:'finance.demo'}.get(i,'lab'+str(i))
   db.sql(f"USE secure_payroll; INSERT INTO employees(employee_number,first_name,last_name) VALUES('MAD-LEGACY-{i}','Fictional','Person'); INSERT INTO accounts(employee_id,login,password_hash) VALUES({i},'{login}','{hashed}'); INSERT INTO role_assignments(account_id,role_id,grant_reason) SELECT {i},id,'Private legacy fixture' FROM roles WHERE code='{role}';")
  env=instance.env.copy();env.update(MAD_TEST_SOCKET=str(instance.socket),MAD_TEST_PASSWORD=service)
  result=subprocess.run(['php',str(ROOT/'tests/mad-repair-live.php'),'--legacy'],env=env);check(result.returncode==0,'legacy functional fixtures')
  legacy=repair.snapshot(db);check(all(v=='UM' for v in repair.classify(legacy).values()),'all three known legacy routines recognized')
  check(legacy['data']['compensation_requests']['count']==2 and legacy['data']['salary_conditions']['count']==1,'representative historical exact counts')
  spec=importlib.util.spec_from_file_location('payroll_admin',ROOT/'bin/payroll-admin.py');admin=importlib.util.module_from_spec(spec);spec.loader.exec_module(admin)
  # Match the administrative client's --database on every fresh connection.
  admin.mysql=lambda sql: db.sql('USE secure_payroll;\n'+sql)
  try:
   with contextlib.redirect_stdout(io.StringIO()):admin.prerequisites()
  except RuntimeError as error:check('MAD schema not confirmed' in str(error),'original inspect fails before repair')
  else:check(False,'legacy unexpectedly passes MAD')
  directory=instance.private/'before-repair'
  plan=repair.prepare(db,directory)
  check(plan['backup_sha256']==repair.digest(directory/'database.sql'),'backup SHA256')
  check(not (directory/'restoration-verified.json').exists(),'dump not falsely marked restored')
  try:repair.apply(db,directory,confirmed=False)
  except RuntimeError:check(repair.snapshot(db)==legacy,'missing authorization causes no change')
  repair.rehearse(directory)
  check(json.loads((directory/'restoration-verified.json').read_text())['complete_patch_rehearsed'],'exact backup restored and complete patch rehearsed')
  after=repair.apply(db,directory,confirmed=True)
  check(after['data']==legacy['data'],'all four historical tables byte-value hashes and counts preserved')
  check(after['triggers']==legacy['triggers'],'all immutability/coverage triggers unchanged')
  check(after['routine_grants']==legacy['routine_grants'] and after['account_grants']==legacy['account_grants'],'all original privileges exactly preserved')
  with mock.patch.object(admin.os,'geteuid',return_value=0), mock.patch.object(admin.sys,'argv',['payroll-admin.py','inspect']):
   admin.main()
  check(True,'complete administrative inspect now passes on the private instance')
  check(db.sql("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='secure_payroll' AND TABLE_NAME LIKE 'payroll%';")=='0','no payroll module installed')
  # New plan on the MAD state: a complete second cycle must not replace routines or alter tables.
  second=instance.private/'already-mad'
  repair.prepare(db,second);repair.rehearse(second)
  again=repair.apply(db,second,confirmed=True)
  check(again==after,'second complete correction cycle is idempotent')
  result=subprocess.run(['php',str(ROOT/'tests/mad-repair-live.php'),'--mad'],env=env);check(result.returncode==0,'new MAD request/Finance approval and UM safeguards')
  db.sql('USE secure_payroll; ALTER TABLE compensation_requests DROP CHECK ck_cr_amount;')
  try:admin.prerequisites()
  except RuntimeError as error:check('CHECK constraints not confirmed' in str(error),'inspect refuses MAD columns/routines without the amount/currency CHECK')
  else:check(False,'missing CHECK unexpectedly passes inspect')
  db.sql("USE secure_payroll; ALTER TABLE compensation_requests ADD CONSTRAINT ck_cr_amount CHECK(monthly_amount>0 AND currency IN ('MAD','UM'));")
  for table in repair.TABLES:
   try:db.sql('UPDATE secure_payroll.'+table+' SET id=id;')
   except RuntimeError as error:check('1644' in str(error),'privileged immutable history '+table)
   else:check(False,'immutable trigger missing '+table)
  # Permission restoration leaves svc_php usable (only service was created with a login secret).
  check(db.sql("SELECT account_locked FROM mysql.user WHERE User='compensation_owner' AND Host='localhost';")=='Y','owner remains locked')
  record={'lab_checks':count,'legacy_php_checks':8,'source_private_directory':str(instance.private),'primary_instance_connected':False,'backup_directory':str(directory),'repeat_directory':str(second),'original_counts':{t:v['count'] for t,v in legacy['data'].items()},'target_files':{p:repair.digest(ROOT/p) for p in repair.FILES}}
  target=instance.private/'mad-repair-result.json';target.write_text(json.dumps(record,indent=2)+'\n')
  print(f'{count} targeted repair/backup/restore/integrity checks passed; PHP workflow totals reported separately. Main instance never connected.',flush=True)
  print('Result retained at '+str(target),flush=True)
 return 0
if __name__=='__main__':
 try:raise SystemExit(main())
 except (RuntimeError,OSError,ValueError) as error:print(str(error) if isinstance(error,RuntimeError) else 'Private MAD campaign stopped; artifacts retained.',file=sys.stderr);raise SystemExit(1)
