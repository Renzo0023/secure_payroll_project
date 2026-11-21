#!/usr/bin/env python3
"""Authorized academic demo: provision missing accounts and use the real HTTP workflow.
No migrations, SQL financial writes, privilege changes or persisted clear passwords.
"""
import argparse
import getpass
import http.cookiejar
import json
import os
from pathlib import Path
import re
import secrets
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'storage/logs/demo-verification.json'


def require(ok,label):
    if not ok:raise RuntimeError(label)


def run_admin(command,payload=None):
    result=subprocess.run(['sudo','python3',str(ROOT/'bin/payroll-admin.py'),command,*(['--apply'] if payload is not None else [])],
        input=None if payload is None else json.dumps(payload),text=True,stdout=subprocess.PIPE)
    require(result.returncode==0,'Administrative preflight/provisioning stopped. No automatic retry.')
    lines=result.stdout.strip().splitlines()
    for line in lines[:-1]:print(line,flush=True)
    return json.loads(lines[-1])


def hash_password(password):
    result=subprocess.run(['php','-d','display_errors=0','-d','log_errors=0','-d','zend.exception_ignore_args=1','-r',
        'echo password_hash(stream_get_contents(STDIN),PASSWORD_ARGON2ID);'],input=password,text=True,capture_output=True)
    require(result.returncode==0 and result.stdout.startswith('$argon2id$'),'Argon2id unavailable.')
    return result.stdout


def credential_broker(passwords):
    """One delivery over a private same-UID Unix socket; secrets remain in RAM."""
    directory=Path(tempfile.mkdtemp(prefix='sp-credentials-',dir='/tmp'));os.chmod(directory,0o700)
    address=directory/'once.sock'
    server=socket.socket(socket.AF_UNIX);server.bind(str(address));os.chmod(address,0o600);server.listen(1)
    pointer=ROOT/'storage/logs/demo-credentials.json'
    # No passwords in the pointer or on disk, only the socket address.
    with pointer.open('w') as output:
        os.chmod(pointer,0o600);json.dump({'socket':str(address),'expires_in_hours':6},output)
    pid=os.fork()
    if pid:
        server.close();return
    os.setsid()
    null=os.open('/dev/null',os.O_RDWR)
    for fd in (0,1,2):os.dup2(null,fd)
    if null>2:os.close(null)
    try:
        server.settimeout(21600)
        while True:
            client,_=server.accept()
            with client:
                client.settimeout(5)
                _,uid,_=struct.unpack('3i',client.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                if uid!=os.getuid() or client.recv(64)!=b'RETRIEVE-ONCE\n':continue
                client.sendall(json.dumps(passwords).encode());break
    except (OSError,ValueError):pass
    finally:
        server.close();address.unlink(missing_ok=True)
    os._exit(0)


def resume_credentials():
    """Resume interrupted verification without resetting accounts or printing secrets.
    Reissue the in-memory delivery endpoint so the user can still retrieve once.
    """
    pointer=ROOT/'storage/logs/demo-credentials.json'
    if not pointer.exists():return {}
    info=json.loads(pointer.read_text());address=Path(info['socket'])
    if not address.exists():return {}
    require(address.parent.stat().st_uid==os.getuid() and address.parent.stat().st_mode&0o077==0,'Unsafe credential endpoint.')
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(5);client.connect(str(address));client.sendall(b'RETRIEVE-ONCE\n');parts=[]
        while True:
            chunk=client.recv(8192)
            if not chunk:break
            parts.append(chunk)
    passwords=json.loads(b''.join(parts));credential_broker(passwords)
    return passwords


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):return None


class Client:
    def __init__(self):
        self.http=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),NoRedirect())
        self.token=''
    def request(self,path,fields=None):
        request=urllib.request.Request('http://127.0.0.1:8080'+path,data=None if fields is None else urllib.parse.urlencode(fields).encode())
        try:response=self.http.open(request,timeout=60)
        except urllib.error.HTTPError as error:response=error
        with response:
            body=response.read().decode();token=re.search(r'name="csrf" value="([a-f0-9]{64})"',body)
            if token:self.token=token[1]
            require(not re.search(r'(?:Fatal error|Warning:|Notice:|Stack trace:)',body),'Visible PHP error on '+path)
            return response.status,response.headers,body
    def post(self,path,**fields):return self.request(path,dict(csrf=self.token,**fields))
    def login(self,login,password):
        require(self.request('/login')[0]==200,'Login form unavailable.')
        status,headers,_=self.post('/login',login=login,password=password)
        require(status==303 and headers.get('Location')=='/dashboard','Real login failed for '+login)
        require(self.request('/dashboard')[0]==200,'Dashboard failed for '+login)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    require(args.apply and sys.stdin.isatty() and os.geteuid()!=0,'Run as the regular user in an interactive terminal with --apply.')
    print('Existing installation only. Missing demo accounts and authorized HTTP payroll/payment workflow; no migrations.',flush=True)
    db_password=getpass.getpass('Existing svc_php MySQL password: ')
    credentials={'rh.demo':getpass.getpass('Existing rh.demo application password: '),
                 'finance.demo':getpass.getpass('Existing finance.demo application password: ')}
    credentials.update(resume_credentials())
    def state(payslip=None):
        result=subprocess.run(['php',str(ROOT/'bin/demo-state.php')],input=json.dumps({'database_password':db_password,'payslip_id':payslip}),text=True,capture_output=True)
        require(result.returncode==0,'Read-only application database verification failed; details withheld.')
        return json.loads(result.stdout)
    before=state()
    nadia=next(p for p in before['people'] if p['employee_number']=='EMP-2026-001')
    salary=[s for s in before['salary'] if s['reference']=='CDI-EMP-2026-001-01' and s['effective_on']=='2026-11-03']
    require(len(salary)==1 and salary[0]['monthly_amount']=='12000.00' and salary[0]['currency']=='MAD' and salary[0]['decision']=='approved' and salary[0]['starts_on']=='2026-11-03','Existing Nadia approved salary differs; no compensation changes authorized.')
    periods=[p for p in before['overview']['periods'] if p['month_start']=='2026-11-01']
    require(len(periods)==1 and periods[0]['bonus_cap']=='3300.00' and periods[0]['deduction_cap']=='560.00','Existing November period differs; no period will be recreated.')
    period=periods[0]
    inventory=run_admin('demo-inventory')
    require(not {'rh.demo','finance.demo'}&set(inventory['missing']),'RH and Finance must already exist.')
    generated={login:secrets.token_urlsafe(18) for login in inventory['missing']}
    hashes={login:hash_password(password) for login,password in generated.items()}
    if generated:
        credential_broker(generated)
        inventory=run_admin('provision-demo',hashes)
        print('New passwords kept only in memory. Retrieve once in your own terminal: python3 bin/demo-passwords.py',flush=True)
    credentials.update(generated)
    employee_login=inventory['employee_login']
    expected={'rh.demo':'hr_manager','finance.demo':'finance_manager','payroll.demo':'payroll_manager',employee_login:'employee','admin.demo':'application_administrator','audit.demo':'security_auditor'}
    for login in expected:
        if login not in credentials:credentials[login]=getpass.getpass('Existing '+login+' application password (no reset): ')
    checks=[]
    clients={}
    for login in expected:
        client=Client();client.login(login,credentials[login]);clients[login]=client
        checks.append('Real HTTP login and dashboard: '+login)
        print('Verified real HTTP login: '+login,flush=True)
    # Only normal authorized navigation on the main database, no offensive probes.
    current=state()
    for login,client in clients.items():
        person=next(p for p in current['people'] if p['login']==login)
        pages=['/dashboard','/employees/'+str(person['id'])]
        if login=='rh.demo':pages+=['/employees','/departments','/positions','/assignments','/contracts','/compensation','/payroll']
        elif login=='finance.demo':pages+=['/compensation/pending','/payroll']
        elif login in ['payroll.demo',employee_login,'audit.demo']:pages+=['/payroll']
        if login in ['admin.demo','audit.demo']:pages+=['/iam']
        for language in ['fr','en']:
            require(client.post('/language',language=language,return_to='/dashboard')[0]==303,'Language switch failed.')
            for page in pages:
                status,headers,body=client.request(page)
                require(status==200 and '<html lang="'+language+'">' in body and headers.get('Content-Language')==language,'Page/language failed: '+login+' '+page+' '+language)
                checks.append(login+' '+language+' '+page)
    payroll=clients['payroll.demo'];finance=clients['finance.demo'];employee=clients[employee_login]
    calculations=[c for c in current['overview']['calculations'] if c['employee_id']==nadia['id'] and c['period_id']==period['id']]
    if calculations and calculations[0]['status']!='rejected':
        calculation=calculations[0];slip=int(calculation['id'])
        print('Reusing existing Nadia payslip #'+str(slip),flush=True)
    else:
        status,headers,_=payroll.post('/payroll/calculate',period_id=period['id'],employee_id=nadia['id'])
        require(status==303 and re.fullmatch('/payslips/[1-9][0-9]*',headers.get('Location','')),'Nadia HTTP payroll calculation failed.')
        slip=int(headers['Location'].rsplit('/',1)[1])
    detail=state(slip)['detail'];row=detail['row']
    require(all(row[k]==v for k,v in {'base_amount':'11200.00','bonus_amount':'0.00','deduction_amount':'0.00','gross_amount':'11200.00','net_amount':'11200.00','currency':'MAD'}.items()),'Nadia amounts differ; approval/publication/payment stopped.')
    days=row['snapshot']['days']
    # The SQL snapshot stores covered days only; the month denominator is 30.
    require([d['date'] for d in days]==['2026-11-'+str(day).zfill(2) for day in range(3,31)]
            and all(d['paid'] in (True,1) for d in days),'Nadia calendar differs from expected 28/30.')
    path='/payslips/'+str(slip)
    for prior,event,client in [('prepared','verified',payroll),('verified','approved',finance),('approved','published',payroll)]:
        detail=state(slip)['detail']
        if detail['row']['status']==prior:
            require(client.request(path)[0]==200,'Payslip form failed.')
            require(client.post(path+'/transition',event=event,reason='Academic demonstration: '+event+' after exact 28/30 MAD verification')[0]==303,'Payslip transition failed: '+event)
            print('Nadia payslip #'+str(slip)+': '+event,flush=True)
    after=state(slip)
    require(after['detail']['row']['status']=='published','Published Nadia payslip required.')
    for language in ['fr','en']:
        employee.post('/language',language=language,return_to=path)
        require(employee.request(path)[0]==200,'Employee cannot read own published payslip.')
        require(employee.request(path+'/settlement')[0]==200,'Employee cannot read own settlement.')
    settlement=after['settlement'];require(settlement is not None,'Settlement module unavailable.')
    require(settlement['summary']['net_amount']=='11200.00','Existing correction differs; no automatic replacement or payment.')
    balance=settlement['summary']['balance']
    if balance=='11200.00':
        finance.request(path+'/settlement')
        require(finance.post(path+'/settlement',action='pay',target='0',expected=settlement['summary']['current_correction_id'],reference='DEMO-NADIA-202611-'+str(slip),reason='Academic simulation only: November 2026 Nadia salary, no bank transfer')[0]==303,'Fictional payment failed.')
    else:require(balance=='0.00','Unexpected existing balance; no duplicate or partial payment performed.')
    after=state(slip)
    require(after['settlement']['summary']['balance']=='0.00','Final fictional balance is not zero.')
    require(before['compensation_fingerprints']==after['compensation_fingerprints'],'Existing compensation history changed; inspect immediately.')
    require({e['event_type'] for e in after['detail']['events']} >= {'verified','approved','published'},'Payslip event history incomplete.')
    require(any(e['entry_type']=='payment' for e in after['settlement']['ledger']),'Fictional payment ledger missing.')
    checks+=['Nadia exact 11200.00 MAD, 28/30 days','Paie verification / independent Finance approval / Paie publication','Employee own published payslip FR/EN','Fictional payment and zero balance','Original compensation table hashes unchanged','Payslip and settlement event histories present']
    # Persist only verification metadata, never credentials, cookies or CSRF tokens.
    report={'passed':True,'at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'primary_database':'secure_payroll',
            'payslip_id':slip,'employee_login':employee_login,'checks':checks,'accounts':expected,'net_amount':'11200.00','currency':'MAD','balance':'0.00',
            'original_compensation_counts':before['compensation_counts'],'compensation_history_preserved':True,
            'payslip_events':after['detail']['events'],'settlement_ledger':after['settlement']['ledger']}
    with REPORT.open('w') as output:os.chmod(REPORT,0o600);json.dump(report,output,indent=2)
    print('SUCCESS: '+str(len(checks))+' primary HTTP/database checks. Nadia published payslip '+path+', 11200.00 MAD, fictional balance 0.00.',flush=True)
    print('Report without secrets: '+str(REPORT),flush=True)

if __name__=='__main__':
    try:main()
    except (RuntimeError,OSError,ValueError,KeyError,StopIteration) as error:
        print(str(error) if isinstance(error,RuntimeError) else 'Demo finalization stopped; retain state, do not replay migrations or reset accounts.',file=sys.stderr);sys.exit(1)
