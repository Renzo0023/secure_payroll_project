#!/usr/bin/env python3
"""Interactive read-only real connection test, without credential files."""
import argparse
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--login', required=True)
    parser.add_argument('--forbidden-payslip-id', type=int)
    args = parser.parse_args()
    if os.geteuid() == 0 or not sys.stdin.isatty():
        print('Run as the regular user in an interactive terminal, without sudo.', file=sys.stderr)
        return 2
    env = os.environ.copy()
    env.update(DB_HOST='127.0.0.1', DB_PORT='3306', DB_NAME='secure_payroll', DB_USER='svc_php',
               DB_PASSWORD=getpass.getpass('Existing MySQL svc_php password: '))
    password = getpass.getpass('Application password: ')
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(['php', str(root / 'tests/payroll-live.php'), '--verify'],
                            input=json.dumps({'login': args.login, 'password': password,
                                              'forbidden_payslip_id': args.forbidden_payslip_id}),
                            text=True, env=env)
    del password
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
