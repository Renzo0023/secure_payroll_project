#!/usr/bin/env python3
"""Authenticated web scenarios targeting ONLY a private-socket laboratory server."""
import http.cookiejar
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None


def main():
    private_socket=os.environ.get('PAYROLL_TEST_SOCKET','')
    if not re.fullmatch(r'/tmp/securepayroll-mysql-[A-Za-z0-9_-]+/mysql.sock',private_socket):
        raise RuntimeError('A private laboratory socket is required.')
    private=Path(private_socket).parent
    run_id=secrets.token_hex(4)
    runtime=private/('web-runtime-'+run_id)
    runtime.mkdir(mode=0o700)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0))
        port=probe.getsockname()[1]
    env=os.environ.copy()
    env.update(DB_SOCKET=private_socket,DB_HOST='127.0.0.1',DB_PORT='3306',DB_NAME='secure_payroll',DB_USER='svc_php',
               DB_PASSWORD=os.environ['PAYROLL_TEST_PASSWORD'],APP_RUNTIME_DIR=str(runtime))
    base=f'http://127.0.0.1:{port}'
    log_path=private/('http-server-'+run_id+'.log')
    log=log_path.open('xb')
    os.chmod(log_path,0o600)
    server=subprocess.Popen(['php','-S',f'127.0.0.1:{port}','-t','public','public/index.php'],cwd=ROOT,env=env,
                            stdout=log,stderr=log)
    count=0
    try:
        def check(ok,name):
            nonlocal count
            if not ok: raise RuntimeError('HTTP test failed: '+name)
            count+=1
        class Client:
            def __init__(self):
                self.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),NoRedirect())
                self.token=None
            def request(self,path,fields=None):
                req=urllib.request.Request(base+path,data=None if fields is None else urllib.parse.urlencode(fields).encode())
                try: response=self.client.open(req,timeout=60)
                except urllib.error.HTTPError as error: response=error
                with response:
                    body=response.read().decode()
                    token=re.search(r'name="csrf" value="([a-f0-9]{64})"',body)
                    if token: self.token=token[1]
                    return response.status,response.headers,body
            def post(self,path,**fields):
                return self.request(path,dict(csrf=self.token,**fields))
            def login(self,number):
                check(self.request('/login')[0]==200,'login rendered')
                status,headers,_=self.post('/login',login='lab'+str(number),password=os.environ['PAYROLL_TEST_APP_PASSWORD'])
                check(status==303 and headers.get('Location')=='/dashboard','authenticated role '+str(number))
                check(self.request('/dashboard')[0]==200,'dashboard role '+str(number))
        deadline=time.monotonic()+15
        while True:
            try:
                urllib.request.urlopen(base+'/login',timeout=1).close()
                break
            except urllib.error.URLError:
                if server.poll() is not None or time.monotonic()>deadline: raise RuntimeError('Private HTTP server unavailable.')
                time.sleep(0.1)
        clients={}
        for number in range(1,8):
            client=Client(); client.login(number); clients[number]=client
        hr,finance,payroll,employee,other,auditor,administrator=[clients[i] for i in range(1,8)]
        for client in [hr,finance,payroll,employee,other,auditor]:
            check(client.request('/payroll')[0]==200,'authorized payroll overview')
        check(administrator.request('/payroll')[0]==403,'admin cannot read finances')
        check(employee.request('/payslips/3')[0]==200,'own published payslip')
        check(other.request('/payslips/3')[0]==404,'foreign payslip IDOR')
        check(employee.request('/payslips/1')[0]==404,'own unpublished version hidden')
        check(employee.request('/employees/5')[0]==403,'foreign HR profile IDOR')
        check(employee.post('/payroll/calculate',period_id='1',employee_id='5')[0]==403,'employee escalation refused')
        check(hr.post('/payslips/3/transition',event='approved',reason='Forbidden role')[0]==403,'HR cannot approve payslip')
        check(payroll.request('/payroll/calculate',{'csrf':'invalid','period_id':'1','employee_id':'5'})[0]==403,'authenticated CSRF')
        check(hr.request('/compensation')[0]==200 and finance.request('/compensation')[0]==200,'RH/Finance remuneration screens')
        check(payroll.request('/compensation')[0]==403,'payroll cannot edit compensation')
        check(employee.post('/language',language='en',return_to='/payroll')[0]==303,'English preference switch')
        status,headers,body=employee.request('/payslips/3')
        check(status==200 and '<html lang="en">' in body and headers.get('Content-Language')=='en','authenticated English payslip')
        # A second employee receives a separate payslip through the complete real HTTP workflow.
        status,headers,_=payroll.post('/payroll/calculate',period_id='1',employee_id='5')
        check(status==303,'HTTP calculation')
        location=headers.get('Location','')
        check(re.fullmatch(r'/payslips/[1-9][0-9]*',location) is not None,'calculation location')
        check(payroll.request(location)[0]==200,'HTTP prepared payslip rendering')
        check(other.request(location)[0]==404,'draft not exposed')
        check(payroll.post(location+'/transition',event='verified',reason='Amounts verified in isolated web test')[0]==303,'HTTP verification')
        check(finance.post(location+'/transition',event='approved',reason='Independent Finance in isolated web test')[0]==303,'HTTP independent approval')
        check(other.request(location)[0]==404,'approval does not publish')
        check(payroll.post(location+'/transition',event='published',reason='Explicit isolated publication')[0]==303,'HTTP publication')
        check(other.request(location)[0]==200,'second employee owns published payslip')
        check(employee.request(location)[0]==404,'reverse employee IDOR')
        check(auditor.request(location)[0]==200,'auditor read without modification')
        check(auditor.post(location+'/transition',event='approved',reason='Forbidden auditor action')[0]==403,'auditor cannot approve')
        failed=Client();check(failed.request('/login')[0]==200,'failed-login test form')
        for attempt in range(5):
            check(failed.post('/login',login='absent-laboratory-user',password='deliberately-invalid')[0]==401,'failed attempt charged '+str(attempt+1))
        check(failed.post('/login',login='absent-laboratory-user',password='deliberately-invalid')[0]==429,'sixth failed attempt rate limited')
        print(f'{count} authenticated isolated HTTP checks passed; MySQL socket and runtime artifacts private.')
        return 0
    finally:
        server.terminate()
        server.wait(timeout=60)
        log.close()


if __name__=='__main__':
    try:
        sys.exit(main())
    except (RuntimeError,OSError) as error:
        print(str(error) if isinstance(error,RuntimeError) else 'Private HTTP verification unavailable.',file=sys.stderr)
        sys.exit(1)
