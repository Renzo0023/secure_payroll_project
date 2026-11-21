#!/usr/bin/env python3
"""Backup-first targeted MAD repair. No primary mutation without explicit apply confirmation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
TABLES=('compensation_requests','compensation_decisions','compensation_history','salary_conditions')
ROUTINES=('compensation_check_period','compensation_submit','compensation_decide')
FILES=('database/patches/002_mad_schema_guarded.sql','database/patches/003_mad_compensation_routines.sql')

def require(ok,message):
    if not ok:raise RuntimeError(message)
def quote(s):return "'"+s.replace("'","''")+"'"
def names(values):return ','.join(quote(v) for v in values)
def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def tokens(s):
    pattern=r"--[^\n]*|/\*.*?\*/|'(?:''|\\.|[^'\\])*'|`[^`]*`|[A-Za-z_][A-Za-z_0-9]*|\d+|[^\s]"
    return tuple(t if t.startswith("'") else t.strip('`').lower() for t in re.findall(pattern,s,re.S) if not t.startswith(('--','/*')))

def restored_ddl(definition):
    # mysqldump makes inherited column charsets explicit on restoration.
    # Only normalize that redundant utf8mb4 annotation; snapshot columns still
    # compare actual charset/collation independently and without normalization.
    return re.sub(r"(  `[^`]+` (?:var)?char\(\d+\)) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs",r"\1 COLLATE utf8mb4_0900_as_cs",definition)
def definitions(path):
    blocks=re.findall(r"CREATE\s+DEFINER\s*=\s*'compensation_owner'@'localhost'\s+PROCEDURE\s+(\w+)\((.*?)END\$\$",Path(path).read_text(),re.S|re.I)
    out={}
    for name,tail in blocks:
        if name in ROUTINES:
            definition="CREATE DEFINER='compensation_owner'@'localhost' PROCEDURE "+name+'('+tail+'END'
            body=definition[definition.index('\nBEGIN')+1:]
            header=definition[:definition.index('SQL SECURITY')]
            signature=[]
            for mode,param,dtype,charset,collation in re.findall(r'\b(IN|OUT)\s+(\w+)\s+(BIGINT UNSIGNED|DECIMAL\(12,2\)|DATE|VARCHAR\(\d+\))(?:\s+CHARACTER SET (\w+)\s+COLLATE (\w+))?',header,re.I):
                signature.append([mode.upper(),param,dtype.lower(),charset or None,collation or None])
            out[name]={'create':definition,'body':body,'signature':signature}
    require(set(out)==set(ROUTINES),'Three reviewed routine definitions required.')
    return out

class Client:
    def __init__(self,socket='/var/run/mysqld/mysqld.sock'):
        require(re.fullmatch(r'/[A-Za-z0-9_./-]+',socket) and '..' not in socket.split('/'),'Invalid explicit socket.')
        self.socket=socket
        self.env={k:v for k,v in os.environ.items() if k not in {'MYSQL_PWD','DB_PASSWORD'}}
        self.base=['--no-defaults','--no-login-paths','--protocol=socket','--socket='+socket,'--user=root','--default-character-set=utf8mb4']
    def sql(self,sql):
        r=subprocess.run(['mysql',*self.base,'--batch','--raw','--skip-column-names','--binary-mode'],input="SET SESSION time_zone='+00:00'; SET NAMES utf8mb4 COLLATE utf8mb4_0900_as_cs;\n"+sql,text=True,capture_output=True,env=self.env,timeout=120)
        require(r.returncode==0,'MySQL error '+','.join(re.findall(r'ERROR (\d+)',r.stderr))+'. Stop; artifacts retained, no automatic replay.')
        return r.stdout.strip()
    def rows(self,sql):return [json.loads(row) for row in self.sql(sql).splitlines()]

def snapshot(db):
    state={}
    state['server']=db.rows("SELECT JSON_OBJECT('uuid',@@server_uuid,'datadir',@@datadir,'version',VERSION());")[0]
    require(state['server']['version'].startswith('8.4.'),'MySQL 8.4 required.')
    state['columns']=db.rows("SELECT JSON_OBJECT('table',TABLE_NAME,'name',COLUMN_NAME,'type',COLUMN_TYPE,'default',COLUMN_DEFAULT,'nullable',IS_NULLABLE,'charset',CHARACTER_SET_NAME,'collation',COLLATION_NAME,'extra',EXTRA,'comment',COLUMN_COMMENT,'generated',GENERATION_EXPRESSION) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='secure_payroll' AND TABLE_NAME IN ("+names(TABLES)+") ORDER BY TABLE_NAME,ORDINAL_POSITION;")
    state['checks']=db.rows("SELECT JSON_OBJECT('table',tc.TABLE_NAME,'name',tc.CONSTRAINT_NAME,'enforced',tc.ENFORCED,'clause',cc.CHECK_CLAUSE) FROM information_schema.TABLE_CONSTRAINTS tc JOIN information_schema.CHECK_CONSTRAINTS cc ON cc.CONSTRAINT_SCHEMA=tc.CONSTRAINT_SCHEMA AND cc.CONSTRAINT_NAME=tc.CONSTRAINT_NAME WHERE tc.TABLE_SCHEMA='secure_payroll' AND tc.TABLE_NAME IN ("+names(TABLES)+") AND tc.CONSTRAINT_TYPE='CHECK' ORDER BY tc.TABLE_NAME,tc.CONSTRAINT_NAME;")
    state['routines']=db.rows("SELECT JSON_OBJECT('name',ROUTINE_NAME,'definer',DEFINER,'security',SECURITY_TYPE,'access',SQL_DATA_ACCESS,'mode',SQL_MODE,'body',ROUTINE_DEFINITION,'client_charset',CHARACTER_SET_CLIENT,'connection_collation',COLLATION_CONNECTION) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='secure_payroll' AND ROUTINE_TYPE='PROCEDURE' ORDER BY ROUTINE_NAME;")
    state['parameters']=db.rows("SELECT JSON_OBJECT('routine',SPECIFIC_NAME,'mode',PARAMETER_MODE,'name',PARAMETER_NAME,'type',DTD_IDENTIFIER,'charset',CHARACTER_SET_NAME,'collation',COLLATION_NAME) FROM information_schema.PARAMETERS WHERE SPECIFIC_SCHEMA='secure_payroll' AND SPECIFIC_NAME IN ("+names(ROUTINES)+") ORDER BY SPECIFIC_NAME,ORDINAL_POSITION;")
    state['triggers']=db.rows("SELECT JSON_OBJECT('name',TRIGGER_NAME,'table',EVENT_OBJECT_TABLE,'definer',DEFINER,'timing',ACTION_TIMING,'event',EVENT_MANIPULATION,'body',ACTION_STATEMENT,'mode',SQL_MODE) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA='secure_payroll' ORDER BY TRIGGER_NAME;")
    state['routine_grants']=db.rows("SELECT JSON_OBJECT('user',User,'host',Host,'routine',Routine_name,'privileges',CAST(Proc_priv AS CHAR)) FROM mysql.procs_priv WHERE Db='secure_payroll' AND Routine_type='PROCEDURE' AND Routine_name IN ("+names(ROUTINES)+") ORDER BY Routine_name,User,Host;")
    require(db.sql("SELECT account_locked FROM mysql.user WHERE User='compensation_owner' AND Host='localhost';")=='Y','compensation_owner must already exist and remain locked.')
    state['account_grants']={}
    owners={'svc_php@localhost','compensation_owner@localhost'}|{r['definer'] for r in state['routines']}|{t['definer'] for t in state['triggers']}
    for identity in sorted(owners-{'root@localhost'}):
        user,host=identity.rsplit('@',1)
        state['account_grants'][identity]=db.sql('SHOW GRANTS FOR '+quote(user)+'@'+quote(host)+';').splitlines()
    state['data']={}
    state['table_ddl']={table:db.sql('SHOW CREATE TABLE secure_payroll.'+table+';') for table in TABLES}
    for table in TABLES:
        columns=[c['name'] for c in state['columns'] if c['table']==table]
        require(columns and all(re.fullmatch(r'[A-Za-z0-9_]+',c) for c in columns),'Missing or unexpected financial columns.')
        rows=db.sql('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY; SELECT JSON_ARRAY('+','.join('`'+c+'`' for c in columns)+') FROM secure_payroll.'+table+' ORDER BY id; COMMIT;')
        state['data'][table]={'count':len(rows.splitlines()) if rows else 0,'sha256':hashlib.sha256(rows.encode()).hexdigest()}
    return state

def classify(state):
    old=definitions(ROOT/'database/migrations/005_compensation_operations.sql')
    target=definitions(ROOT/FILES[1]);result={}
    for name in ROUTINES:
        actual=next((r for r in state['routines'] if r['name']==name),None)
        require(actual and actual['body'] is not None,'Missing/hidden routine '+name)
        require(actual['definer']=='compensation_owner@localhost' and actual['security']=='DEFINER','Unexpected routine security '+name)
        signature=[[p[k] for k in ('mode','name','type','charset','collation')] for p in state['parameters'] if p['routine']==name]
        require(signature==target[name]['signature'],'Unexpected signature '+name)
        if tokens(actual['body'])==tokens(target[name]['body']):result[name]='MAD'
        elif tokens(actual['body'])==tokens(old[name]['body']):result[name]='UM'
        else:raise RuntimeError('Custom/unrecognized routine '+name+'; DBA review required before replacement.')
    required={(name,'compensation_owner','localhost') for name in ROUTINES}|{(name,'svc_php','localhost') for name in ('compensation_submit','compensation_decide')}
    actual={(g['routine'],g['user'],g['host']) for g in state['routine_grants'] if 'Execute' in g['privileges'].split(',')}
    require(required<=actual,'Existing required EXECUTE grants missing; no new privilege will be inferred.')
    return result

def save(path,value):
    with Path(path).open('x') as f:
        os.chmod(path,0o600);json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())

def prepare(db,directory):
    require(not directory.exists(),'Use a NEW private directory; never overwrite a previous backup/plan.')
    state=snapshot(db);classification=classify(state)
    require(db.sql("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='secure_payroll' AND TABLE_TYPE='BASE TABLE' AND ENGINE<>'InnoDB';")=='0','Non-InnoDB table: DBA backup strategy required.')
    # Evaluate the existing guard only; do not execute PREPARE or ALTER.
    guard=(ROOT/FILES[0]).read_text().split('-- An unexpected state')[0]
    require(db.sql('SET @mad_schema_repair_authorized=1;\n'+guard+'\nSELECT @mad_schema_guard;')=='1','Schema differs from reviewed repair states; no backup plan applied.')
    directory.mkdir(mode=0o700)
    partial=directory/'database.partial.sql'
    with partial.open('xb') as f:
        os.chmod(partial,0o600)
        r=subprocess.run(['mysqldump',*db.base,'--single-transaction','--quick','--routines','--triggers','--events','--hex-blob','--no-tablespaces','--set-gtid-purged=OFF','--databases','secure_payroll'],stdout=f,stderr=subprocess.PIPE,env=db.env)
        f.flush();os.fsync(f.fileno())
    require(r.returncode==0 and partial.stat().st_size>0,'Dump incomplete; retained partial file, no DDL executed.')
    partial.rename(directory/'database.sql')
    plan={'state':state,'routine_states':classification,'backup_sha256':digest(directory/'database.sql'),
          'files':{p:digest(ROOT/p) for p in FILES},'restoration_tested':False}
    save(directory/'plan.json',plan)
    # Newly created private artifacts may be rehearsed by the invoking regular user.
    if os.geteuid()==0 and os.environ.get('SUDO_UID','').isdigit():
        uid=int(os.environ['SUDO_UID']);gid=int(os.environ['SUDO_GID'])
        for p in directory.iterdir():os.chown(p,uid,gid)
        os.chown(directory,uid,gid)
    print(json.dumps({'directory':str(directory),'exact_counts':{t:v['count'] for t,v in state['data'].items()},'routines':classification,'backup_sha256':plan['backup_sha256'],'primary_ddl_executed':False},indent=2),flush=True)
    return plan

def read_plan(directory):
    require(directory.is_dir() and not directory.is_symlink() and directory.stat().st_mode&0o077==0,'Private nonsymlink directory required.')
    for filename in ['plan.json','database.sql']:
        p=directory/filename
        require(p.is_file() and not p.is_symlink() and p.stat().st_mode&0o077==0,'Private regular artifact required: '+filename)
    plan=json.loads((directory/'plan.json').read_text())
    require(digest(directory/'database.sql')==plan['backup_sha256'],'Backup SHA256 mismatch.')
    require(set(plan['files'])==set(FILES),'Unexpected patch files in plan.')
    require(all(digest(ROOT/p)==sha for p,sha in plan['files'].items()),'Reviewed patch files changed; prepare a new plan.')
    return plan

def restore_routine_grants(db,saved):
    current=db.rows("SELECT JSON_OBJECT('user',User,'host',Host,'routine',Routine_name,'privileges',CAST(Proc_priv AS CHAR)) FROM mysql.procs_priv WHERE Db='secure_payroll' AND Routine_type='PROCEDURE' AND Routine_name IN ("+names(ROUTINES)+") ORDER BY Routine_name,User,Host;")
    for g in current:
        expected=next((v for v in saved if (v['user'],v['host'],v['routine'])==(g['user'],g['host'],g['routine'])),None)
        if expected==g:continue
        privileges=[{'Execute':'EXECUTE','Alter Routine':'ALTER ROUTINE','Grant':'GRANT OPTION'}[v] for v in g['privileges'].split(',')]
        db.sql('REVOKE '+','.join(privileges)+' ON PROCEDURE secure_payroll.'+g['routine']+' FROM '+quote(g['user'])+'@'+quote(g['host'])+';')
    for g in saved:
        require(set(g['privileges'].split(','))<={'Execute','Alter Routine','Grant'},'Unknown routine privilege.')
        privileges=[{'Execute':'EXECUTE','Alter Routine':'ALTER ROUTINE'}[v] for v in g['privileges'].split(',') if v!='Grant']
        db.sql('GRANT '+','.join(privileges)+' ON PROCEDURE secure_payroll.'+g['routine']+' TO '+quote(g['user'])+'@'+quote(g['host'])+(' WITH GRANT OPTION' if 'Grant' in g['privileges'].split(',') else '')+';')

def verify_preservation(before,after):
    for key in ['data','triggers','routine_grants','account_grants','parameters']:
        require(before[key]==after[key],'Preservation check failed: '+key+'; keep maintenance and inspect artifacts.')
    require([r for r in before['routines'] if r['name'] not in ROUTINES]==[r for r in after['routines'] if r['name'] not in ROUTINES],'Unrelated routine changed.')
    require([c for c in before['columns'] if c['name']!='currency']==[c for c in after['columns'] if c['name']!='currency'],'Unrelated column changed.')
    require([c for c in before['checks'] if c['name'] not in ('ck_cr_amount','ck_sc_amount')]==[c for c in after['checks'] if c['name'] not in ('ck_cr_amount','ck_sc_amount')],'Unrelated CHECK changed.')
    for table in ('compensation_decisions','compensation_history'):
        require(before['table_ddl'][table]==after['table_ddl'][table],'Unrelated table definition changed.')
    require(all(v=='MAD' for v in classify(after).values()),'MAD routines not complete.')
    for r in after['routines']:
        if r['name'] in ROUTINES:
            original=next(o for o in before['routines'] if o['name']==r['name'])
            require({k:v for k,v in r.items() if k!='body'}=={k:v for k,v in original.items() if k!='body'},'Routine metadata changed.')

def apply(db,directory,confirmed=False,_rehearsal=False):
    require(confirmed,'Explicit administrative authorization required.')
    plan=read_plan(directory)
    receipt_path=directory/'restoration-verified.json'
    require(receipt_path.is_file() and not receipt_path.is_symlink() and receipt_path.stat().st_mode&0o077==0,'Private restoration receipt required.')
    receipt=json.loads(receipt_path.read_text())
    require(receipt['backup_sha256']==plan['backup_sha256'] and receipt['passed'] is True,'Successful independent restoration of this exact backup required.')
    require(_rehearsal or receipt.get('complete_patch_rehearsed') is True,'Complete patch rehearsal on this exact backup required.')
    before=snapshot(db)
    require(before==plan['state'],'Live state/data/grants changed since backup. No DDL executed; prepare a new plan.')
    states=classify(before)
    db.sql('SET @mad_schema_repair_authorized=1;\n'+(ROOT/FILES[0]).read_text())
    targets=definitions(ROOT/FILES[1])
    for name in ROUTINES:
        if states[name]=='MAD':continue
        original=next(r for r in before['routines'] if r['name']==name)
        db.sql('SET SESSION sql_mode='+quote(original['mode'])+'; SET NAMES '+original['client_charset']+' COLLATE '+original['connection_collation']+'; USE secure_payroll; DROP PROCEDURE '+name+';\nDELIMITER $$\n'+targets[name]['create']+'$$\nDELIMITER ;\n')
        restore_routine_grants(db,before['routine_grants'])
    after=snapshot(db);verify_preservation(before,after)
    require(db.sql("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='secure_payroll' AND TABLE_NAME IN ('compensation_requests','salary_conditions') AND COLUMN_NAME='currency' AND CHARACTER_MAXIMUM_LENGTH=3 AND COLUMN_DEFAULT='MAD';")=='2','MAD columns incomplete.')
    save(directory/'applied.json',{'passed':True,'preserved_data':after['data'],'routines':classify(after),'backup_sha256':plan['backup_sha256']})
    print('MAD correction verified; all historical rows, triggers, signatures and original privileges preserved. No payroll installation.',flush=True)
    return after

def rehearse(directory):
    require(os.geteuid()!=0,'Run rehearsal as the regular user, without sudo.')
    sys.path.insert(0,str(ROOT/'lab'))
    from mysql_instance import PrivateInstance
    plan=read_plan(directory)
    with PrivateInstance(temporary_root='/var/tmp') as instance:
        db=Client(str(instance.socket))
        for identity in plan['state']['account_grants']:
            user,host=identity.rsplit('@',1)
            db.sql('CREATE USER '+quote(user)+'@'+quote(host)+" IDENTIFIED WITH caching_sha2_password AS '' ACCOUNT LOCK;")
        with (directory/'database.sql').open('r') as source:
            r=subprocess.run(['mysql',*db.base,'--binary-mode'],stdin=source,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,env=db.env)
        require(r.returncode==0,'Independent restoration failed; source unchanged.')
        for grants in plan['state']['account_grants'].values():
            for grant in grants:db.sql(grant+';')
        restore_routine_grants(db,plan['state']['routine_grants'])
        restored=snapshot(db)
        for key in plan['state']:
            if key=='table_ddl':
                require({t:restored_ddl(v) for t,v in restored[key].items()}=={t:restored_ddl(v) for t,v in plan['state'][key].items()},'Restored snapshot differs: table_ddl')
            elif key!='server':require(restored[key]==plan['state'][key],'Restored snapshot differs: '+key)
        # Test the same repair against this restored copy before touching any source.
        trial=instance.private/'repair-trial';trial.mkdir(mode=0o700)
        for filename in ['database.sql','plan.json']:
            import shutil
            shutil.copyfile(directory/filename,trial/filename);os.chmod(trial/filename,0o600)
        trialplan=dict(plan);trialplan['state']=restored
        (trial/'plan.json').write_text(json.dumps(trialplan));os.chmod(trial/'plan.json',0o600)
        save(trial/'restoration-verified.json',{'passed':True,'backup_sha256':plan['backup_sha256']})
        apply(db,trial,confirmed=True,_rehearsal=True)
        restored_password=secrets.token_urlsafe(32)
        db.sql("ALTER USER 'svc_php'@'localhost' IDENTIFIED BY "+quote(restored_password)+' ACCOUNT UNLOCK;')
        env=db.env.copy();env['MYSQL_PWD']=restored_password
        service_base=[arg if arg!='--user=root' else '--user=svc_php' for arg in db.base]
        probe=subprocess.run(['mysql',*service_base,'--batch','--skip-column-names'],input='SELECT COUNT(*) FROM secure_payroll.compensation_requests; SELECT COUNT(*) FROM secure_payroll.salary_conditions;',text=True,capture_output=True,env=env)
        require(probe.returncode==0,'Restored non-root service read failed.')
        save(directory/'restoration-verified.json',{'passed':True,'backup_sha256':plan['backup_sha256'],'private_directory':str(instance.private),'complete_patch_rehearsed':True})
        print('Exact backup restored and complete patch rehearsed in '+str(instance.private)+'. Private instance stopped on exit.',flush=True)
    return True

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['inspect','prepare','rehearse','apply'])
    parser.add_argument('--directory',type=Path)
    parser.add_argument('--maintenance-confirmed',action='store_true')
    args=parser.parse_args()
    if args.command=='rehearse':require(args.directory is not None,'--directory required.');rehearse(args.directory);return
    require(os.geteuid()==0,'Authenticated sudo required; no connection made.')
    db=Client()
    if args.command=='inspect':
        state=snapshot(db);print(json.dumps({'exact_counts':{t:v['count'] for t,v in state['data'].items()},'routines':classify(state)},indent=2));return
    require(args.directory is not None and args.directory.is_absolute(),'Explicit absolute private directory required.')
    require(args.maintenance_confirmed,'Stop application writes/DDL and pass --maintenance-confirmed.')
    if args.command=='prepare':prepare(db,args.directory);return
    require(sys.stdin.isatty(),'Interactive administrative terminal required.')
    require(input('Authorize targeted principal MAD DDL and exact grant restoration? Type REPAIR-MAD secure_payroll: ').strip()=='REPAIR-MAD secure_payroll','Cancelled.')
    apply(db,args.directory,confirmed=True)
if __name__=='__main__':
    try:main()
    except (RuntimeError,OSError,ValueError,EOFError,KeyboardInterrupt) as error:
        print(str(error) if isinstance(error,RuntimeError) else 'Stopped; retain artifacts, maintenance and inspect state before retrying.',file=sys.stderr);sys.exit(1)
