#!/usr/bin/env python3
"""Authenticated correction/payment workflow on a private MySQL socket only."""
import http.cookiejar
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None

def main():
    private_socket=os.environ.get('PAYROLL_TEST_SOCKET','')
    if not re.fullmatch(r'/tmp/securepayroll-mysql-[A-Za-z0-9_-]+/mysql.sock',private_socket):raise RuntimeError('Private socket required')
    private=Path(private_socket).parent
    runtime=private/('settlement-runtime-'+secrets.token_hex(4));runtime.mkdir(mode=0o700)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    env=os.environ.copy();env.update(DB_SOCKET=private_socket,DB_HOST='127.0.0.1',DB_PORT='1',DB_NAME='secure_payroll',DB_USER='svc_php',
        DB_PASSWORD=os.environ['PAYROLL_TEST_PASSWORD'],APP_RUNTIME_DIR=str(runtime),SETTLEMENT_ENABLED='1')
    count=0
    def check(ok,name):
        nonlocal count
        if not ok:raise RuntimeError('Settlement HTTP failed: '+name)
        count+=1
    with (runtime/'http.log').open('xb') as log:
        server=subprocess.Popen(['php','-S',f'127.0.0.1:{port}','-t','public','public/index.php'],cwd=ROOT,env=env,stdout=log,stderr=log)
        try:
            base=f'http://127.0.0.1:{port}'
            class Client:
                def __init__(self):
                    self.http=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),NoRedirect());self.token=''
                def request(self,path,fields=None):
                    request=urllib.request.Request(base+path,data=None if fields is None else urllib.parse.urlencode(fields).encode())
                    try: response=self.http.open(request,timeout=60)
                    except urllib.error.HTTPError as error:response=error
                    with response:
                        body=response.read().decode();match=re.search(r'name="csrf" value="([a-f0-9]{64})"',body)
                        if match:self.token=match[1]
                        return response.status,response.headers,body
                def post(self,path,**fields):return self.request(path,dict(csrf=self.token,**fields))
                def login(self,number):
                    check(self.request('/login')[0]==200,'login form')
                    check(self.post('/login',login='lab'+str(number),password=os.environ['PAYROLL_TEST_APP_PASSWORD'])[0]==303,'role login '+str(number))
            deadline=time.monotonic()+20
            while True:
                try:urllib.request.urlopen(base+'/login',timeout=1).close();break
                except urllib.error.URLError:
                    if time.monotonic()>deadline:raise RuntimeError('HTTP server unavailable')
                    time.sleep(.1)
            clients=[Client() for _ in range(7)]
            for index,client in enumerate(clients,1):client.login(index)
            hr,finance,payroll,employee,other,audit,admin=clients
            path='/payslips/3/settlement'
            for client in [hr,finance,payroll,employee,audit]:check(client.request(path)[0]==200,'authorized read')
            check(other.request(path)[0]==404,'foreign employee IDOR')
            check(admin.request(path)[0]==403,'admin cannot read financial data')
            check(employee.request('/payslips/1/settlement')[0]==404,'unpublished original refused')
            check(payroll.request(path,dict(csrf='invalid',action='correct'))[0]==403,'CSRF refused')
            check(payroll.request(path)[0]==200,'form reload')
            page=payroll.request(path)[2];expected=int(re.search(r'name="expected" value="(\d+)"',page)[1])
            for client in [hr,employee,other,audit,admin]:
                check(client.post(path,action='pay',expected=expected,reason='Forbidden',reference='HTTP-FORBIDDEN-001')[0]==403,'payment role refused')
            check(payroll.post(path,action='correct',expected=expected,base='-1',bonus='0',deduction='0',reason='Invalid')[0]==422,'invalid amounts')
            marker='<script>http-fixture</script>'
            check(payroll.post(path,action='correct',target='0',expected=expected,base='10500.00',bonus='300.00',deduction='100.00',reason=marker)[0]==303,'prepare correction HTTP with actual form target=0')
            body=payroll.request(path)[2]
            check(marker not in body and '&lt;script&gt;http-fixture&lt;/script&gt;' in body,'HTML escaping')
            check('http-fixture' not in employee.request(path)[2],'employee draft hidden')
            target=int(re.search(r'name="action" value="verified".*?name="target" value="(\d+)"',body,re.S)[1])
            check(payroll.post(path,action='verified',target=target,expected=expected,reason='Checked evidence')[0]==303,'verify correction HTTP')
            check(payroll.post(path,action='approved',target=target,expected=expected,reason='Wrong role')[0]==403,'self approval refused')
            check(finance.post(path,action='approved',target=target,expected=expected,reason='Independent finance')[0]==303,'approve correction HTTP')
            check('http-fixture' not in employee.request(path)[2],'approval does not expose correction')
            check(payroll.post(path,action='published',target=target,expected=expected,reason='Publish correction')[0]==303,'publish correction HTTP')
            check('http-fixture' in employee.request(path)[2],'own published correction visible')
            check(finance.post(path,action='pay',expected=expected,reason='Stale browser',reference='HTTP-STALE-001')[0]==409,'stale payment refused')
            check(finance.post(path,action='pay',target='0',expected=target,reason='Supplement only',reference='HTTP-SUPPLEMENT-001',amount='999999.99')[0]==303,'supplement payment with actual form target=0; SQL determines amount')
            check(finance.post(path,action='pay',expected=target,reason='Replay',reference='HTTP-SUPPLEMENT-002')[0]==409,'duplicate payment refused with another reference')
            for language in ['en','fr']:
                check(employee.post('/language',language=language,return_to=path)[1].get('Location')==path,'language return path')
                status,headers,body=employee.request(path)
                check(status==200 and f'<html lang="{language}">' in body and headers.get('Content-Language')==language,'localized settlement')
            check(other.request(path)[0]==404,'IDOR after new publication')
            print(f'{count} isolated settlement HTTP checks passed.')
        finally:
            server.terminate();server.wait(timeout=30)
    return 0
if __name__=='__main__':raise SystemExit(main())
