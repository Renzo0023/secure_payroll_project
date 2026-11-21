#!/usr/bin/env python3
"""Exercise the owner privilege boundary without connecting to MySQL."""
import importlib.util
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('payroll_admin',ROOT/'bin/payroll-admin.py')
admin=importlib.util.module_from_spec(spec)
spec.loader.exec_module(admin)
source=(ROOT/'database/setup/payroll_owner_grants.sql').read_text()
lines=[]
for statement in re.findall(r'^GRANT (.+);$',source,re.MULTILINE):
    line='GRANT '+statement
    line=re.sub(r'ON (PROCEDURE )?secure_payroll\.(\w+)',lambda match:'ON '+(match[1] or '')+'`secure_payroll`.`'+match[2]+'`',line)
    # SHOW GRANTS quotes column identifiers and canonicalizes whitespace.
    line=re.sub(r'\(([^()]+)\)',lambda match:'('+', '.join('`'+word.strip()+'`' for word in match[1].split(','))+')',line)
    line=line.replace('),UPDATE','), UPDATE')
    line=re.sub(r'(SELECT|UPDATE)\(',r'\1 (',line)
    lines.append(line)
valid="GRANT USAGE ON *.* TO 'payroll_owner'@'localhost'\n"+'\n'.join(lines)
admin.validate_owner_grants(valid)
count=1

def rejects(text):
    global count
    try:
        admin.validate_owner_grants(text)
    except RuntimeError:
        count+=1
        return
    raise AssertionError('Excessive/incomplete owner grants accepted')

rejects(valid+"\nGRANT SELECT ON `secure_payroll`.* TO 'payroll_owner'@'localhost'")
rejects(valid+"\nGRANT SELECT ON *.* TO 'payroll_owner'@'localhost'")
rejects(valid+"\nGRANT `shared_role`@`localhost` TO 'payroll_owner'@'localhost'")
rejects(valid+"\nGRANT SELECT ON `secure_payroll`.`accounts` TO 'payroll_owner'@'localhost'")
rejects(valid.replace('SELECT (`id`, `employee_id`, `disabled_at`)','SELECT (`id`, `employee_id`, `disabled_at`, `password_hash`)'))
rejects(valid.replace('UPDATE (`id`)','UPDATE (`id`, `first_name`)'))
rejects(valid+'\n'+lines[-1]+' WITH GRANT OPTION')
rejects('\n'.join(valid.splitlines()[:-1]))
rejects(valid.replace(',INSERT,TRIGGER',',TRIGGER'))
rejects(valid+"\nGRANT EXECUTE ON PROCEDURE `secure_payroll`.`compensation_decide` TO 'payroll_owner'@'localhost'")
rejects(valid+"\nGRANT DELETE ON `secure_payroll`.`payroll_calculations` TO 'payroll_owner'@'localhost'")
print(f'{count} owner privilege boundary checks passed; no MySQL connection.')
