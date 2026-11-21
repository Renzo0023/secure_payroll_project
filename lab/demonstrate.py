#!/usr/bin/env python3
"""Offline fictional security exercises. No network, files, credentials or MySQL."""
import sqlite3


def main():
    db = sqlite3.connect(':memory:')
    db.executescript('''
        CREATE TABLE payslips(id INTEGER PRIMARY KEY, employee INTEGER, net INTEGER);
        INSERT INTO payslips VALUES (1,101,1200000),(2,102,900000);
        CREATE TABLE principals(id INTEGER PRIMARY KEY, role TEXT);
        INSERT INTO principals VALUES(101,'employee'),(102,'finance');
    ''')
    checks = 0

    def check(name, before, after):
        nonlocal checks
        assert before and after, name
        checks += 1
        print(f'PASS {name}: vulnerable effect demonstrated; correction verified')

    # Intentional unsafe queries exist only in this in-memory CLI laboratory.
    payload = '0 OR 1=1'
    unsafe = db.execute('SELECT id FROM payslips WHERE employee=' + payload).fetchall()
    safe = db.execute('SELECT id FROM payslips WHERE employee=?', (payload,)).fetchall()
    check('SQL injection', len(unsafe) == 2, safe == [])

    def read_slip(actor, slip):
        return db.execute('SELECT id FROM payslips WHERE id=? AND employee=?', (slip, actor)).fetchone()

    check('IDOR', db.execute('SELECT id FROM payslips WHERE id=2').fetchone() is not None,
          read_slip(101, 2) is None and read_slip(101, 1) is not None)

    def role(actor):
        return db.execute('SELECT role FROM principals WHERE id=?', (actor,)).fetchone()[0]

    def approve(actor):
        return role(actor) == 'finance'

    check('Missing access control', bool({'requested_action': 'approve'}),
          not approve(101) and approve(102))
    request = {'role': 'finance'}
    check('Privilege escalation', request['role'] == 'finance', role(101) != 'finance')

    db.execute('UPDATE payslips SET net=1 WHERE id=2')
    altered = db.execute('SELECT net FROM payslips WHERE id=2').fetchone()[0] == 1
    db.executescript('''
        CREATE TRIGGER immutable_amount BEFORE UPDATE ON payslips
        BEGIN SELECT RAISE(ABORT,'immutable approved record'); END;
    ''')
    blocked = False
    try:
        db.execute('UPDATE payslips SET net=2 WHERE id=2')
    except sqlite3.IntegrityError:
        blocked = True
    check('Unauthorized financial alteration', altered, blocked)

    # Privilege model only; this does not claim to exercise a MySQL server.
    excessive = {'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'GRANT'}
    service = {'SELECT', 'EXECUTE'}
    check('MySQL misconfiguration model', {'DROP', 'GRANT'} <= excessive,
          not ({'DROP', 'GRANT', 'UPDATE'} & service))
    db.close()
    print(f'{checks} offline scenarios passed. No MySQL behavior tested.')


if __name__ == '__main__':
    main()
