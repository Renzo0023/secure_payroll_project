"""Socket-only MySQL fixture plus loopback PHP server for authorized laboratory tests."""
from contextlib import contextmanager
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
class Client:
    def __init__(self,base):
        self.base=base;self.token='';self.http=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),NoRedirect())
    def request(self,path,fields=None):
        request=urllib.request.Request(self.base+path,data=None if fields is None else urllib.parse.urlencode(fields).encode())
        try:response=self.http.open(request,timeout=60)
        except urllib.error.HTTPError as error:response=error
        with response:
            body=response.read().decode();match=re.search(r'name="csrf" value="([a-f0-9]{64})"',body)
            if match:self.token=match[1]
            return response.status,response.headers,body
    def post(self,path,**fields):return self.request(path,dict(csrf=self.token,**fields))
    def login(self,login):
        self.request('/login')
        return self.post('/login',login=login,password=os.environ['PAYROLL_TEST_APP_PASSWORD'])
@contextmanager
def server():
    sock=os.environ.get('PAYROLL_TEST_SOCKET','')
    if not re.fullmatch(r'/tmp/securepayroll-mysql-[A-Za-z0-9_-]+/mysql.sock',sock):raise RuntimeError('Private socket required')
    runtime=Path(sock).parent/('iam-runtime-'+secrets.token_hex(4));runtime.mkdir(mode=0o700)
    with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    env=os.environ.copy();env.update(DB_SOCKET=sock,DB_HOST='127.0.0.1',DB_PORT='1',DB_NAME='secure_payroll',DB_USER='svc_php',DB_PASSWORD=os.environ['PAYROLL_TEST_PASSWORD'],APP_RUNTIME_DIR=str(runtime),SETTLEMENT_ENABLED='1',IAM_ENABLED='1')
    with (runtime/'http.log').open('xb') as log:
        process=subprocess.Popen(['php','-S',f'127.0.0.1:{port}','-t','public','public/index.php'],cwd=ROOT,env=env,stdout=log,stderr=log)
        try:
            base=f'http://127.0.0.1:{port}';deadline=time.monotonic()+20
            while True:
                try:urllib.request.urlopen(base+'/login',timeout=1).close();break
                except urllib.error.URLError:
                    if time.monotonic()>deadline:raise RuntimeError('Private PHP startup failed')
                    time.sleep(.1)
            yield base
        finally:process.terminate();process.wait(timeout=30)
