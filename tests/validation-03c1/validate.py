#!/usr/bin/env python3
"""Prépare les copies hors connexion ; --run refuse root et exige des droits limités à la cible."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE / 'generated'
TARGET = 'secure_payroll_validation_03b'
EXPECTED_ROLES = {
    'employee': 'Employee', 'hr_manager': 'HR Manager',
    'payroll_manager': 'Payroll Manager', 'finance_manager': 'Finance Manager',
    'application_administrator': 'Application Administrator', 'security_auditor': 'Security Auditor',
}
MYSQL_SOCKET = None


def seed_pairs(text):
    sql = re.sub(r'--[^\n]*', '', text)
    pairs = re.findall(r"SELECT '([^']+)'(?: AS code)?, '([^']+)'(?: AS name)?", sql)
    if len(pairs) != 6 or len(dict(pairs)) != 6 or dict(pairs) != EXPECTED_ROLES:
        raise RuntimeError('Le seed ne contient pas exactement les six couples canoniques.')
    return pairs


def role_snapshot(output):
    rows = [row.split('\t') for row in output.splitlines()]
    if (len(rows) != 6 or any(len(row) != 3 or not row[0].isdigit() for row in rows)
            or len({row[0] for row in rows}) != 6
            or len({row[1] for row in rows}) != 6
            or {row[1]: row[2] for row in rows} != EXPECTED_ROLES):
        raise RuntimeError('Le catalogue réel ne contient pas les six couples canoniques.')
    return rows


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError('Source inattendue : adaptation à revoir avant exécution.')
    return text.replace(old, new, 1)


def prepare():
    OUT.mkdir(exist_ok=True)
    sources = [ROOT / 'database/migrations/001_create_identity_and_rbac.sql',
               ROOT / 'database/seeds/001_application_roles.sql',
               ROOT / 'tests/database-structure.php', ROOT / 'tests/database-integrity.php']
    manifest = []
    for source in sources:
        text = source.read_text()
        manifest.append(f'{hashlib.sha256(source.read_bytes()).hexdigest()}  {source.relative_to(ROOT)}')
        if source.suffix == '.sql':
            if source.name == '001_application_roles.sql':
                seed_pairs(text)
            text = replace_once(text, 'USE secure_payroll;', f'USE {TARGET};')
            # Vérifier les USE exécutables, pas les commentaires.
            sql = re.sub(r'--[^\n]*', '', text)
            if re.findall(r'\bUSE\s+(\w+)\s*;', sql, re.I) != [TARGET]:
                raise RuntimeError('Cible SQL inattendue.')
            if re.search(r'\bsecure_payroll\b', sql):
                raise RuntimeError('Référence à la base principale dans le SQL adapté.')
        else:
            text = replace_once(text, "require dirname(__DIR__) . '/app/bootstrap.php';",
                                "require __DIR__ . '/../admin-connection.php';")
            text = replace_once(text, "require dirname(__DIR__) . '/app/Database/Connection.php';", '')
            text = replace_once(text, r'\App\Database\Connection::connect()', 'validationConnection()')
            if source.name == 'database-structure.php':
                text = replace_once(text,
                    "getenv('DB_NAME') !== 'secure_payroll' || strtolower((string) getenv('DB_USER')) === 'root'",
                    f"getenv('DB_NAME') !== '{TARGET}'")
            else:
                text = replace_once(text,
                    "getenv('DB_NAME') !== 'secure_payroll_test_integrity'\n    || strtolower(trim((string) getenv('DB_USER'))) === 'root'",
                    f"getenv('DB_NAME') !== '{TARGET}'")
                text = text.replace("'secure_payroll_test_integrity'", f"'{TARGET}'")
                text = text.replace('Base de test dédiée et compte non-root obligatoires.',
                                    'Base de validation dédiée obligatoire.')
                text = replace_once(text,
                    "file_get_contents(dirname(__DIR__) . '/database/seeds/001_application_roles.sql')",
                    "file_get_contents(__DIR__ . '/001_application_roles.sql')")
                text = replace_once(text, 'foreach ($tables as $table) {',
                    "foreach ($tables as $table) {\n        if ($table === 'roles') { continue; }")
                text = replace_once(text, "$scenario = 'seed_first_run';\n    $check($pdo->exec($seedInsert) === 6);",
                    "$scenario = 'seed_existing_roles';\n    $check($pdo->exec($seedInsert) === 0);\n    $check((int) $pdo->query('SELECT COUNT(*) FROM roles')->fetchColumn() === 6);")
                # Distinguer les préparations des scénarios voisins pour éviter une fausse attribution.
                text = replace_once(text, '    $pdo->exec("INSERT INTO employees (employee_number, first_name, last_name) VALUES (\'TEST-001\'',
                    '    $scenario = \'fixture_employee\';\n    $pdo->exec("INSERT INTO employees (employee_number, first_name, last_name) VALUES (\'TEST-001\'')
                text = replace_once(text, '    $hash = password_hash(',
                    '    $scenario = \'fixture_argon2id\';\n    $hash = password_hash(')
                text = replace_once(text, '    $pdo->exec("INSERT INTO employees (employee_number, first_name, last_name) VALUES (\'TEST-002\'',
                    '    $scenario = \'fixture_actor\';\n    $pdo->exec("INSERT INTO employees (employee_number, first_name, last_name) VALUES (\'TEST-002\'')
                text = replace_once(text, '    $role = (int)',
                    '    $scenario = \'fixture_roles\';\n    $role = (int)')
                text = replace_once(text, "$scenario = 'preflight';", "$scenario = 'preflight';\n$completed = [];")
                # Enregistrer seulement à la FIN du bloc. Aucun OK avant le rollback réussi.
                text = re.sub(r"(?m)^    \$scenario = '([^']+)';",
                    lambda m: '    $completed[] = $scenario;\n' + m[0], text)
                text = replace_once(text, '    $pdo->rollBack();\n    fwrite(STDOUT,',
                    '    $completed[] = $scenario;\n    if (!$pdo->rollBack()) { throw new RuntimeException(\'Rollback failed\'); }\n'
                    '    foreach ($completed as $finished) { fwrite(STDOUT, "OK : $finished\\n"); }\n    fwrite(STDOUT,')
                text = replace_once(text, '} catch (Throwable) {', '} catch (Throwable $error) {')
                text = replace_once(text, '    fwrite(STDERR, "Échec du scénario :',
                    '    if ($error instanceof PDOException) { fwrite(STDERR, "Code MySQL : " . (int) ($error->errorInfo[1] ?? 0) . "\\n"); }\n    fwrite(STDERR, "Échec du scénario :')
        (OUT / source.name).write_text(text)
    (OUT / 'sources.sha256').write_text('\n'.join(manifest) + '\n')
    print('Copies préparées et cibles vérifiées : ' + str(OUT), flush=True)
    for file in OUT.glob('*.php'):
        subprocess.run(['php', '-l', str(file)], check=True)
    for name in ['admin-connection.php', 'check-connection.php']:
        subprocess.run(['php', '-l', str(HERE / name)], check=True)


def mysql(sql):
    if not MYSQL_SOCKET:
        raise RuntimeError('Précontrôle de privilèges non effectué.')
    env = {key: value for key, value in os.environ.items()
           if key not in {'DB_PASSWORD', 'MYSQL_PWD', 'DB_USER'}}
    # Profil privé préexistant, jamais créé par ce script. Aucune authentification en argument.
    result = subprocess.run(['mysql', '--no-defaults', '--login-path=secure_payroll_validation_03b',
                             '--protocol=socket', '--socket=' + MYSQL_SOCKET,
                             '--database=information_schema', '--batch', '--skip-column-names'],
                            input=sql, text=True, capture_output=True, env=env)
    if result.returncode:
        codes = re.findall(r'ERROR (\d+)', result.stderr)
        print('Code(s) MySQL : ' + ', '.join(codes or ['indisponible']), file=sys.stderr)
        raise RuntimeError('Commande MySQL échouée ; arrêt sans nettoyage.')
    if result.stderr:
        print('Diagnostic client MySQL non vide : à examiner en privé.', file=sys.stderr)
    return result.stdout


def run():
    global MYSQL_SOCKET
    if os.geteuid() == 0:
        raise RuntimeError('Exécution système root interdite. Ne pas utiliser sudo.')
    if os.environ.get('DB_NAME') != TARGET:
        raise RuntimeError('DB_NAME doit correspondre exclusivement à la base de validation.')
    preflight = subprocess.run(['php', str(HERE / 'check-connection.php')],
                              text=True, capture_output=True)
    if preflight.returncode:
        raise RuntimeError('Précontrôle refusé : configuration privée ou privilèges de validation incorrects.')
    identity = json.loads(preflight.stdout)
    MYSQL_SOCKET = identity['socket']
    # Le client et PDO doivent employer le même compte vérifié sur le même serveur.
    client_identity = mysql('SELECT CURRENT_USER(), @@server_uuid;').strip().split('\t')
    if client_identity != [identity['identity'], identity['uuid']]:
        raise RuntimeError('PDO et le client mysql n’utilisent pas la même identité/instance.')
    if int(identity['log_bin']) and not int(identity['trust_creators']):
        raise RuntimeError('La politique de journal binaire peut exiger SUPER pour les triggers. Arrêt avant création : décision DBA nécessaire, sans élévation automatique.')
    version = mysql('SELECT VERSION();').strip()
    print('Version constatée : ' + version, flush=True)
    if not version.startswith('8.4.11'):
        raise RuntimeError('Version différente de la cible 8.4.11 ; arrêt pour revue.')
    exists = mysql(f"SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = '{TARGET}';")
    if exists.strip():
        raise RuntimeError('La base de validation existe déjà : aucune modification, aucune suppression.')
    print('Base absente ; création de la seule base ' + TARGET, flush=True)
    # Sans IF NOT EXISTS : une création concurrente provoque un arrêt, jamais une réutilisation.
    mysql(f'CREATE DATABASE `{TARGET}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs;')
    mysql((OUT / '001_create_identity_and_rbac.sql').read_text())
    print('Migration exécutée.', flush=True)
    mysql((OUT / '001_application_roles.sql').read_text())
    baseline = mysql(f'USE {TARGET}; SELECT id, code, name FROM roles ORDER BY code;')
    role_snapshot(baseline)
    mysql((OUT / '001_application_roles.sql').read_text())
    second = mysql(f'USE {TARGET}; SELECT id, code, name FROM roles ORDER BY code;')
    role_snapshot(second)
    if second != baseline:
        raise RuntimeError('Le deuxième seed modifie les rôles.')
    print('Seed : deux exécutions, six rôles, identifiants et libellés inchangés.', flush=True)
    print(mysql(f"SELECT TABLE_NAME, ENGINE, TABLE_COLLATION FROM information_schema.TABLES WHERE TABLE_SCHEMA = '{TARGET}' ORDER BY TABLE_NAME;"), end='')
    print(mysql(f"SELECT CONSTRAINT_TYPE, COUNT(*) FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = '{TARGET}' GROUP BY CONSTRAINT_TYPE ORDER BY CONSTRAINT_TYPE;"), end='')
    print(mysql(f"SELECT TRIGGER_NAME, ACTION_TIMING, EVENT_MANIPULATION FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA = '{TARGET}' ORDER BY TRIGGER_NAME;"), end='')
    env = dict(os.environ)
    subprocess.run(['php', str(OUT / 'database-structure.php'), '--verify'], env=env, check=True)
    subprocess.run(['php', str(OUT / 'database-integrity.php'), '--run', '--confirm-test-database'], env=env, check=True)
    if mysql(f'USE {TARGET}; SELECT id, code, name FROM roles ORDER BY code;') != baseline:
        raise RuntimeError('Les rôles ne correspondent plus au snapshot initial.')
    for table in ['employees', 'accounts', 'permissions', 'role_permissions', 'role_assignments']:
        if mysql(f'USE {TARGET}; SELECT COUNT(*) FROM `{table}`;').strip() != '0':
            raise RuntimeError('Données résiduelles inattendues : ' + table)
    print('Validation terminée ; base et six rôles conservés. Aucun DROP ni nettoyage.', flush=True)


if __name__ == '__main__':
    try:
        if sys.argv[1:] not in ([], ['--prepare'], ['--run']):
            raise RuntimeError('Usage : validate.py [--prepare|--run]')
        prepare()
        if sys.argv[1:] == ['--run']:
            run()
    except (RuntimeError, subprocess.CalledProcessError, OSError, ValueError, KeyError) as error:
        print('ARRÊT : ' + str(error), file=sys.stderr)
        sys.exit(1)
