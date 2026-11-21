#!/usr/bin/env python3
"""Non-destructive anonymous checks against the authorized loopback application."""
import http.cookiejar
import re
import urllib.error
import urllib.parse
import urllib.request

BASE = 'http://127.0.0.1:8080'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    jar = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect())
    count = 0

    def check(ok, name):
        nonlocal count
        if not ok:
            raise RuntimeError('Failed: ' + name)
        count += 1

    def request(path, method='GET', data=None):
        payload = None if data is None else urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(BASE + path, data=payload, method=method)
        try:
            response = client.open(req, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.headers, response.read().decode('utf-8')

    status, headers, body = request('/login')
    check(status == 200 and '<html lang="fr">' in body, 'French login')
    for key, value in [('X-Content-Type-Options', 'nosniff'), ('Referrer-Policy', 'no-referrer')]:
        check(headers.get(key) == value, key)
    check('no-store' in [part.strip() for part in headers.get('Cache-Control', '').split(',')], 'Cache-Control')
    check("frame-ancestors 'none'" in headers.get('Content-Security-Policy', ''), 'framing policy')
    cookie = headers.get('Set-Cookie', '').lower()
    check('httponly' in cookie and 'samesite=lax' in cookie, 'session cookie flags')
    token = re.search(r'name="csrf" value="([a-f0-9]{64})"', body)
    check(token is not None, 'CSRF token rendered')
    for path in ['/dashboard', '/employees', '/employees/1', '/contracts/new', '/compensation', '/compensation/1', '/compensation/history', '/payroll', '/payslips/1']:
        status, headers, _ = request(path)
        check(status == 303 and headers.get('Location') == '/login', 'anonymous ' + path)
        check(headers.get('X-SecurePayroll-Contract-Diagnostic') is None, 'no diagnostic marker ' + path)
    for path in ['/login', '/contracts/new', '/compensation/new', '/compensation/1/decision', '/language', '/logout', '/payroll/periods', '/payroll/inputs', '/payroll/calculate', '/payroll/inputs/1/decision', '/payslips/1/transition']:
        check(request(path, 'POST', {'csrf': 'invalid'})[0] == 403, 'CSRF refusal ' + path)
    check(request('/compensation/1/decision')[0] == 405, 'decision method')
    check(request('/employees', 'PUT')[0] == 405, 'unsupported method')
    check(request('/payroll/calculate')[0] == 405, 'calculation requires POST')
    check(request('/payslips/1/transition')[0] == 405, 'transition requires POST')
    check(request('/not-a-route')[0] == 404, 'unknown route')
    status, headers, _ = request('/language', 'POST', {'csrf': token.group(1), 'language': 'en', 'return_to': '/login'})
    check(status == 303 and headers.get('Location') == '/login', 'language switch')
    status, headers, body = request('/login')
    check(status == 200 and '<html lang="en">' in body and headers.get('Content-Language') == 'en', 'English login')
    check(request('/language', 'POST', {'csrf': token.group(1), 'language': 'invalid', 'return_to': '/login'})[0] == 422, 'invalid locale')
    print(f'{count} HTTP checks passed. No login attempted or business data written.')


if __name__ == '__main__':
    main()
