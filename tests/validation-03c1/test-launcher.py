"""Tests du lanceur uniquement : aucun appel mysql, sudo ou Git, aucune connexion."""
import importlib.util
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PROCESS_RUN = subprocess.run
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('validation_launcher', HERE / 'validate.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def test_canonical_seed(self):
        seed = (launcher.ROOT / 'database/seeds/001_application_roles.sql').read_text()
        self.assertEqual(dict(launcher.seed_pairs(seed)), launcher.EXPECTED_ROLES)
        for bad in [seed.replace("'Employee' AS name", "'Wrong' AS name"),
                    seed.replace("'hr_manager'", "'employee'"),
                    seed.replace("UNION ALL SELECT 'security_auditor', 'Security Auditor'", ''),
                    seed.replace(') AS incoming', "UNION ALL SELECT 'extra', 'Extra'\n) AS incoming")]:
            with self.assertRaises(RuntimeError):
                launcher.seed_pairs(bad)

    def test_real_roles_exact(self):
        good = '\n'.join(f'{i}\t{code}\t{name}' for i, (code, name) in enumerate(launcher.EXPECTED_ROLES.items(), 1))
        self.assertEqual(len(launcher.role_snapshot(good)), 6)
        for bad in [good.replace('\tEmployee\n', '\tWrong\n'), good + '\n7\textra\tExtra',
                    good.replace('2\thr_manager', '1\thr_manager')]:
            with self.assertRaises(RuntimeError):
                launcher.role_snapshot(bad)

    def test_system_root_refused_before_subprocess(self):
        with patch.object(launcher.os, 'geteuid', return_value=0), patch.object(launcher.subprocess, 'run') as run:
            with self.assertRaises(RuntimeError):
                launcher.run()
            run.assert_not_called()

    def test_no_mysql_before_preflight(self):
        with patch.object(launcher, 'MYSQL_SOCKET', None), patch.object(launcher.subprocess, 'run') as run:
            with self.assertRaises(RuntimeError):
                launcher.mysql('not executed')
            run.assert_not_called()

    def test_prepared_copies_and_reporting(self):
        with tempfile.TemporaryDirectory(prefix='payroll-launcher-') as directory:
            with patch.object(launcher, 'OUT', Path(directory)), patch.object(launcher.subprocess, 'run'):
                launcher.prepare()
                integrity = (Path(directory) / 'database-integrity.php').read_text()
                self.assertEqual(integrity.count('OK :'), 1)
                self.assertLess(integrity.index('if (!$pdo->rollBack())'), integrity.index('OK :'))
                self.assertNotIn('fwrite(STDOUT, "OK : $scenario', integrity)
                self.assertIn('"OK : $finished\\n"', integrity)
                self.assertIn("$scenario = 'fixture_actor';", integrity)
                self.assertIn("getenv('DB_NAME') !== 'secure_payroll_validation_03b'", integrity)
                for name in ['001_create_identity_and_rbac.sql', '001_application_roles.sql']:
                    sql = re.sub(r'--[^\n]*', '', (Path(directory) / name).read_text())
                    self.assertEqual(re.findall(r'\bUSE\s+(\w+)\s*;', sql), [launcher.TARGET])
                    self.assertIsNone(re.search(r'\bsecure_payroll\b', sql))

                start = integrity.rindex('    $completed[] = $scenario;', 0, integrity.index('OK :'))
                end = integrity.index('    fwrite(STDOUT, "$passed', start)
                reporting = integrity[start:end]
                for behavior, expected_code, expected_output in [
                    ('return true;', 0, 'OK : first\nOK : last\n'),
                    ('return false;', 1, ''),
                    ('throw new RuntimeException();', 1, ''),
                ]:
                    # Objet factice : seul le reporting est exécuté, sans PDO ou SQL.
                    php = "$completed = ['first']; $scenario = 'last'; "
                    php += '$pdo = new class { public function rollBack(): bool { ' + behavior + ' } }; '
                    php += 'try { ' + reporting + ' } catch (Throwable) { exit(1); }'
                    result = PROCESS_RUN(['php', '-r', php], text=True, capture_output=True)
                    self.assertEqual(result.returncode, expected_code, result.stderr)
                    self.assertEqual(result.stdout, expected_output)

    def test_privilege_policy_offline(self):
        # Inclusion seule du helper et tests sur des chaînes : aucune instanciation PDO.
        php = r'''<?php
require $argv[1];
$rights = 'SELECT, INSERT, UPDATE, DELETE, CREATE, TRIGGER, REFERENCES';
$grant = "GRANT $rights ON `secure_payroll_validation_03b`.* TO `validator`@`localhost`";
validationCheckGrants(['GRANT USAGE ON *.* TO `validator`@`localhost`', $grant], true);
validationCheckGrants([str_replace('_', '\\_', $grant)], false);
$bad = [
    [$grant, false],
    [str_replace('secure_payroll_validation_03b', 'secure_payroll', $grant), true],
    ['GRANT ALL PRIVILEGES ON *.* TO `validator`@`localhost`', true],
    [$grant . ' WITH GRANT OPTION', true],
    [str_replace('SELECT, ', '', $grant), true],
    ['GRANT `admin_role`@`%` TO `validator`@`localhost`', true],
    [str_replace('TRIGGER', 'DROP', $grant), true],
];
foreach ($bad as [$text, $partial]) {
    try { validationCheckGrants([$text], $partial); }
    catch (RuntimeException) { continue; }
    exit(1);
}
echo "Politique de privilèges : deux cas admis, sept cas refusés, sans connexion.\n";
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.php', prefix='payroll-grants-') as fixture:
            fixture.write(php)
            fixture.flush()
            result = subprocess.run(['php', fixture.name, str(HERE / 'admin-connection.php')],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_integrity_write_audit(self):
        text = (launcher.ROOT / 'tests/database-integrity.php').read_text()
        self.assertNotRegex(text, r'(?<!->)\b(?:exec|shell_exec|system|passthru|proc_open|popen|pcntl_exec)\s*\(')
        # Les backticks dans une chaîne SQL citent un identifiant ; seuls les tokens
        # PHP autonomes correspondants exécuteraient une commande système.
        scanner = 'foreach (token_get_all(file_get_contents($argv[1])) as $token) { if ($token === "`") { exit(1); } }'
        result = subprocess.run(['php', '-r', scanner, str(launcher.ROOT / 'tests/database-integrity.php')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        statements = re.findall(r'\$pdo->(?:exec|query|prepare)\((["\'])(.*?)\1\)', text, re.S)
        writes = []
        for _, sql in statements:
            code = re.sub(r"'(?:''|[^'])*'", "''", sql)
            self.assertNotRegex(code, r'(?i)\b(?:USE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|OUTFILE|LOAD_FILE)\b')
            if re.match(r'(?:INSERT|UPDATE|DELETE)\b', sql):
                writes.append(sql)
                match = re.match(r'(?:INSERT INTO|UPDATE|DELETE FROM) (\w+)\b', sql)
                self.assertIsNotNone(match)
                self.assertIn(match[1], ['roles', 'employees', 'accounts', 'role_assignments'])
                self.assertNotIn('.', sql.split(' ', 3)[2])
        self.assertGreater(len(writes), 20)
        self.assertIn('$pdo->beginTransaction()', text)
        self.assertIn('$pdo->rollBack()', text)


if __name__ == '__main__':
    unittest.main()
