#!/usr/bin/env python3
"""Resume only authenticated HTTP checks on a stopped, private fictional lab instance."""
import argparse
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from mysql_instance import PrivateInstance
ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-private-dir',required=True)
    args=parser.parse_args()
    with PrivateInstance(args.source_private_dir) as instance:
        service=secrets.token_urlsafe(32);password=secrets.token_urlsafe(32)
        hashed=subprocess.run(['php','-d','display_errors=0','-d','log_errors=0','-r',
                               'echo password_hash(stream_get_contents(STDIN),PASSWORD_ARGON2ID);'],
                              input=password,text=True,capture_output=True,check=True).stdout
        if not re.fullmatch(r'\$argon2id\$v=19\$m=\d+,t=\d+,p=\d+\$[A-Za-z0-9+/]+\$[A-Za-z0-9+/]+',hashed):raise RuntimeError('Fixture hashing failed.')
        instance.sql("ALTER USER 'svc_php'@'localhost' IDENTIFIED BY '"+service+"'; UPDATE secure_payroll.accounts SET password_hash='"+hashed+"' WHERE login REGEXP '^lab[1-7]$';")
        env=instance.env.copy();env.update(PAYROLL_TEST_SOCKET=str(instance.socket),PAYROLL_TEST_PASSWORD=service,PAYROLL_TEST_APP_PASSWORD=password)
        result=subprocess.run(['python3',str(ROOT/'tests/payroll-http-live.py')],env=env)
        return result.returncode


if __name__=='__main__':
    try:sys.exit(main())
    except (RuntimeError,OSError,subprocess.TimeoutExpired) as error:
        print(str(error) if isinstance(error,RuntimeError) else 'Private HTTP resume stopped; artifacts retained.',file=sys.stderr)
        sys.exit(1)
