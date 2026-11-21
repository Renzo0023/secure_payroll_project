#!/usr/bin/env python3
"""Additive, backup-first activation of fictional settlements and IAM. Never replay existing objects."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('payroll_admin',ROOT/'bin/payroll-admin.py')
admin=importlib.util.module_from_spec(spec);spec.loader.exec_module(admin)
MODULES={
 'settlement':{
  'owner':'settlement_owner',
  'tables':('payslip_corrections','correction_events','recovery_requests','recovery_events','settlement_ledger'),
  'routines':('settlement_command','settlement_detail'),
  'files':('database/setup/settlement_owner.sql','database/migrations/009_settlement.sql','database/migrations/010_settlement_operations.sql','database/setup/settlement_owner_grants.sql','database/seeds/007_settlement_permissions.sql','database/setup/settlement_grants.sql'),
 },
 'iam':{
  'owner':'iam_owner','tables':(), 'routines':('iam_overview','iam_grant','iam_revoke'),
  'files':('database/setup/iam_owner.sql','database/migrations/011_iam_operations.sql','database/setup/iam_owner_grants.sql','database/seeds/008_iam_permissions.sql','database/setup/iam_grants.sql'),
 }}

def inventory(module):
    names=admin.names
    return {
      'tables':admin.mysql("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='secure_payroll' AND TABLE_NAME IN ("+names(module['tables'])+");").splitlines() if module['tables'] else [],
      'routines':admin.mysql("SELECT ROUTINE_NAME FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='secure_payroll' AND ROUTINE_NAME IN ("+names(module['routines'])+");").splitlines(),
      'owner_hosts':admin.mysql('SELECT Host FROM mysql.user WHERE User='+admin.quote(module['owner'])+';').splitlines(),
      'triggers':admin.mysql("SELECT TRIGGER_NAME FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA='secure_payroll' AND TRIGGER_NAME IN ("+names(tuple(table+'_no_'+op for table in module['tables'] for op in ('update','delete')))+");").splitlines() if module['tables'] else [],
    }

def canonical_grant(line):
    # Compare SHOW GRANTS with the reviewed scripts without discarding scope/columns.
    line=re.sub(r" TO .*",'',line.strip().rstrip(';'))
    line=re.sub(r'\s+','',line.replace('`','')).upper()
    return re.sub(r'\(([^()]*)\)',lambda match:'('+','.join(sorted(match[1].split(',')))+')',line)

def verify(module):
    state=inventory(module)
    admin.require(set(state['tables'])==set(module['tables']) and set(state['routines'])==set(module['routines'])
                  and state['owner_hosts']==['localhost'] and len(state['triggers'])==2*len(module['tables']), 'Module object inventory incomplete.')
    admin.require(admin.mysql('SELECT account_locked FROM mysql.user WHERE User='+admin.quote(module['owner'])+" AND Host='localhost';")=='Y','Owner must be locked.')
    expected={canonical_grant(line) for line in (ROOT/module['files'][-3]).read_text().splitlines() if line.startswith('GRANT ')}
    actual={canonical_grant(line) for line in admin.mysql("SHOW GRANTS FOR '"+module['owner']+"'@'localhost';").splitlines() if not line.startswith('GRANT USAGE ')}
    admin.require(actual==expected,'Owner grants differ from reviewed allowlist.')
    admin.require(admin.mysql('SELECT COUNT(*) FROM mysql.proxies_priv WHERE User='+admin.quote(module['owner'])+';')=='0','Unexpected proxy privilege.')
    admin.require(admin.mysql("SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='secure_payroll' AND ROUTINE_NAME IN ("+admin.names(module['routines'])+") AND DEFINER='"+module['owner']+"@localhost' AND SECURITY_TYPE='DEFINER';")==str(len(module['routines'])),'Unexpected routine definer/security.')
    if module['tables']:
        admin.require(admin.mysql("SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA='secure_payroll' AND EVENT_OBJECT_TABLE IN ("+admin.names(module['tables'])+") AND DEFINER='"+module['owner']+"@localhost';")==str(2*len(module['tables'])),'Unexpected trigger definer.')
    service=admin.mysql("SHOW GRANTS FOR 'svc_php'@'localhost';")
    for procedure in module['routines']:
        expected_grant=canonical_grant('GRANT EXECUTE ON PROCEDURE secure_payroll.'+procedure)
        admin.require(expected_grant in {canonical_grant(line) for line in service.splitlines()},'Missing service EXECUTE.')
    admin.service_grants()
    print('Module objects, locked owner, exact owner grants and service boundary verified. Business workflow on main remains to verify.')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['inspect','install','verify'])
    parser.add_argument('--module',choices=MODULES,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    admin.require(os.geteuid()==0,'Use an authenticated DBA terminal; no operation executed.')
    module=MODULES[args.module]
    admin.prerequisites();admin.verify()
    state=inventory(module);print(json.dumps(state,indent=2))
    if args.command=='inspect':return
    if args.command=='verify':verify(module);return
    admin.require(args.apply and sys.stdin.isatty(),'--apply and an interactive terminal required.')
    admin.require(not any(state.values()),'Existing/partial module detected. Refuse replay; inspect with DBA.')
    admin.FILES=module['files']
    scripts=[(path,(ROOT/path).read_text()) for path in module['files']]
    for path,script in scripts:print(path+' SHA256 '+admin.hashlib.sha256(script.encode()).hexdigest())
    admin.require(input('With application writes and DDL stopped, type secure_payroll for snapshot then NEW '+args.module+' objects: ').strip()=='secure_payroll','Cancelled.')
    backup=admin.backup_before_install()
    admin.require(not any(inventory(module).values()),'Object inventory changed during backup; no migration applied.')
    admin.require(all((ROOT/path).read_text()==script for path,script in scripts),'Installation files changed during backup; no migration applied.')
    for path,script in scripts:
        admin.mysql(script);print('Applied '+path,flush=True)
    verify(module)
    print('Activation verified; snapshot retained at '+str(backup)+'. Enable the web flag only after acceptance checks.')

if __name__=='__main__':
    try:main()
    except (RuntimeError,OSError,EOFError,KeyboardInterrupt) as error:
        print(str(error) if isinstance(error,RuntimeError) else 'Administrative operation stopped; retain artifacts and inspect before retrying.',file=sys.stderr)
        sys.exit(1)
