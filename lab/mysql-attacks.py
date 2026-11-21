#!/usr/bin/env python3
"""Pedagogical before/after demonstrations confined to a private MySQL lab schema."""
import argparse
import json
import os
from pathlib import Path
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
        suffix=secrets.token_hex(4)
        schema='attack_training_'+suffix
        account='lab_drill_'+suffix
        password=secrets.token_urlsafe(32)
        instance.sql(f"CREATE DATABASE {schema}; CREATE TABLE {schema}.accounts(id INT PRIMARY KEY, role VARCHAR(20)); INSERT INTO {schema}.accounts VALUES(1,'employee'),(2,'finance'); CREATE TABLE {schema}.payslips(id INT PRIMARY KEY,employee INT,net DECIMAL(12,2),approved BOOLEAN); INSERT INTO {schema}.payslips VALUES(1,1,12000.00,1),(2,2,9000.00,1); CREATE USER '{account}'@'localhost' IDENTIFIED BY '{password}'; GRANT SELECT,UPDATE ON {schema}.* TO '{account}'@'localhost';")
        env=instance.env.copy()
        env.update(PAYROLL_TEST_SOCKET=str(instance.socket),PAYROLL_ATTACK_SCHEMA=schema,
                   PAYROLL_ATTACK_ACCOUNT=account,PAYROLL_ATTACK_PASSWORD=password)
        result=subprocess.run(['php',str(ROOT/'tests/mysql-attack-demonstrations.php'),'--before'],env=env)
        if result.returncode:return result.returncode
        instance.sql(f"CREATE PROCEDURE {schema}.own_payslip(IN p_id INT) SQL SECURITY DEFINER READS SQL DATA SELECT id,employee,net FROM {schema}.payslips WHERE id=p_id AND employee=1; REVOKE SELECT,UPDATE ON {schema}.* FROM '{account}'@'localhost'; GRANT EXECUTE ON PROCEDURE {schema}.own_payslip TO '{account}'@'localhost';")
        result=subprocess.run(['php',str(ROOT/'tests/mysql-attack-demonstrations.php'),'--after'],env=env)
        if result.returncode:return result.returncode
        report={'schema':schema,'account':account,'private_directory':str(instance.private),
                'main_instance_connected':False,'scenarios':['sql_injection','missing_access_control','idor','privilege_escalation','unauthorized_tampering','excessive_mysql_grants']}
        target=instance.private/('attack-result-'+suffix+'.json')
        target.write_text(json.dumps(report,indent=2));os.chmod(target,0o600)
        print('Six MySQL before/after scenarios demonstrated in '+schema+'. Report: '+str(target))
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (RuntimeError,OSError,subprocess.TimeoutExpired) as error:
        print(str(error) if isinstance(error,RuntimeError) else 'Private attack exercise stopped; artifacts retained.',file=sys.stderr)
        sys.exit(1)
