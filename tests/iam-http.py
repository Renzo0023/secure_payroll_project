#!/usr/bin/env python3
"""Real admin/auditor HTTP IAM flow; no production identities or connections."""
import os
import re
from private_http import Client,server

def main():
    count=0
    def check(ok,name):
        nonlocal count
        if not ok:raise RuntimeError('IAM HTTP failure: '+name)
        count+=1
    with server() as base:
        clients=[Client(base) for _ in range(7)]
        for index,client in enumerate(clients,1):check(client.login('lab'+str(index))[0]==303,'role login')
        hr,finance,payroll,employee,other,auditor,admin=clients
        check(admin.request('/iam')[0]==200,'admin read')
        check(auditor.request('/iam')[0]==200,'auditor read')
        for client in [hr,finance,payroll,employee,other]:check(client.request('/iam')[0]==403,'other role denied')
        check(admin.request('/iam/grant')[0]==405,'grant requires POST')
        target=os.environ['IAM_TEST_TARGET']
        check(auditor.post('/iam/grant',account=target,role='security_auditor',reason='Forbidden')[0]==403,'auditor cannot grant')
        check(admin.request('/iam/grant',dict(csrf='bad',account=target,role='security_auditor',reason='No CSRF'))[0]==403,'CSRF denied')
        check(admin.post('/iam/grant',account='7',role='employee',reason='Self attribution')[0]==403,'self role denied')
        check(admin.post('/iam/grant',account=target,role="employee' OR 1=1 --",reason='SQL injection')[0]==422,'invalid role injection denied')
        marker='<script>iam-http</script>'
        check(admin.post('/iam/grant',account=target,role='security_auditor',reason=marker)[0]==303,'grant HTTP')
        body=admin.request('/iam')[2]
        check(marker not in body and '&lt;script&gt;iam-http&lt;/script&gt;' in body,'escape IAM audit text')
        assignment=int(re.search(r'<tr><td>iam-target</td>.*?action="/iam/(\d+)/revoke"',body,re.S)[1])
        check(admin.post('/iam/grant',account=target,role='finance_manager',reason='Conflict')[0]==409,'operational separation')
        target_client=Client(base);check(target_client.login('iam-target')[0]==303,'new auditor login')
        check(target_client.request('/iam')[0]==200,'granted role takes effect')
        check(admin.post(f'/iam/{assignment}/revoke',reason='Revoke immediately')[0]==303,'revoke HTTP')
        check(target_client.request('/iam')[0]==403,'revocation takes effect in existing session')
        check(admin.post(f'/iam/{assignment}/revoke',reason='Replay')[0]==409,'duplicate revocation denied')
        for language in ['en','fr']:
            check(admin.post('/language',language=language,return_to='/iam')[1].get('Location')=='/iam','IAM language return')
            status,headers,body=admin.request('/iam')
            check(status==200 and f'<html lang="{language}">' in body and headers.get('Content-Language')==language,'localized IAM')
            check('password_hash' not in body and '$argon2id$' not in body,'credentials absent')
    print(f'{count} isolated IAM HTTP checks passed.')
    return 0
if __name__=='__main__':raise SystemExit(main())
