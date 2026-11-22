#!/usr/bin/env python3
"""Génère l'ERD (Mermaid) et l'inventaire des relations à partir des migrations SQL.

Lecture seule des fichiers database/migrations/*.sql ; aucune connexion MySQL.
  python3 bin/generate-erd.py           écrit docs/security-assessment/erd/
  python3 bin/generate-erd.py --check   échoue si les fichiers générés sont périmés
"""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / 'database/migrations'
OUTPUT = ROOT / 'docs/security-assessment/erd'
EXPECTED_TABLES = 28

DOMAINS = {
    '01-IDENTITE-RBAC': ('Identité, données personnelles et RBAC',
                         ['employees', 'employee_personal_data', 'accounts', 'roles', 'permissions',
                          'role_permissions', 'role_assignments', 'account_invitations']),
    '02-ORGANISATION-RH': ('Organisation RH',
                           ['departments', 'positions', 'employee_assignments', 'employment_contracts']),
    '03-REMUNERATION': ('Rémunération',
                        ['compensation_requests', 'compensation_decisions', 'salary_conditions',
                         'compensation_history']),
    '04-PAIE': ('Paie et bulletins',
                ['payroll_periods', 'payroll_inputs', 'payroll_input_decisions', 'payroll_calculations',
                 'payslip_events', 'payroll_approvals']),
    '05-REGLEMENTS': ('Règlements et corrections',
                      ['payslip_corrections', 'correction_events', 'recovery_requests', 'recovery_events',
                       'settlement_ledger']),
    # Phase 7 (migration 016) : piste d'audit en ajout seul, sans clé étrangère par conception.
    '06-AUDIT': ('Journalisation et audit', ['security_audit_log']),
}

# Colonnes classées « Restreint » (docs/security-assessment/02-CLASSIFICATION-DES-DONNEES.md).
RESTRICTED = {
    'employee_personal_data': {'id_document_number', 'cnss_number', 'rib'},
    'accounts': {'password_hash'},
    'salary_conditions': {'monthly_amount'},
    'compensation_requests': {'monthly_amount'},
    'payroll_inputs': {'amount'},
    'payroll_calculations': {'base_amount', 'bonus_amount', 'deduction_amount', 'gross_amount',
                             'net_amount', 'snapshot'},
    'payslip_corrections': {'base_amount', 'bonus_amount', 'deduction_amount', 'gross_amount', 'net_amount'},
    'recovery_requests': {'amount'},
    'settlement_ledger': {'amount'},
}

# Clés étrangères de traçabilité (auteur d'une action) : omises dans la vue globale.
ACTOR_COLUMNS = {
    'created_by', 'closed_by', 'updated_by', 'requested_by', 'decided_by', 'prepared_by', 'actor_id',
    'requester_employee_id', 'approver_employee_id', 'actor_employee_id', 'preparer_employee_id',
    'creator_employee_id', 'granted_by_account_id', 'revoked_by_account_id', 'issued_by_account_id',
}


def split_top_level(body):
    items, depth, quote, start = [], 0, None, 0
    for index, char in enumerate(body):
        if quote:
            if char == quote:
                quote = None
        elif char in "'\"":
            quote = char
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        elif char == ',' and depth == 0:
            items.append(body[start:index].strip())
            start = index + 1
    items.append(body[start:].strip())
    return [item for item in items if item]


def columns_of(text):
    return [part.strip().strip('`') for part in text.split(',')]


def parse():
    tables = {}
    for path in sorted(MIGRATIONS.glob('*.sql')):
        sql = re.sub(r'--[^\n]*', '', path.read_text())
        for name, body in re.findall(r'CREATE TABLE (\w+) \((.*?)\n\) ENGINE', sql, re.S):
            table = {'columns': {}, 'order': [], 'pk': [], 'unique': [], 'unique_names': {}, 'fks': [],
                     'source': path.name}
            for item in split_top_level(body):
                item = re.sub(r'\s+', ' ', item)
                constraint = re.match(r'CONSTRAINT (\w+) ', item)
                item = re.sub(r'^CONSTRAINT \w+ ', '', item)
                if item.startswith('PRIMARY KEY'):
                    table['pk'] = columns_of(re.search(r'\((.*)\)', item)[1])
                elif re.match(r'UNIQUE', item):
                    columns = columns_of(re.search(r'\(([^)]*)\)', item)[1])
                    table['unique'].append(columns)
                    if constraint:
                        table['unique_names'][constraint[1]] = columns
                elif item.startswith('FOREIGN KEY'):
                    match = re.match(r'FOREIGN KEY ?\(([^)]*)\) REFERENCES (\w+) ?\(([^)]*)\)', item)
                    table['fks'].append({'columns': columns_of(match[1]), 'parent': match[2],
                                         'parent_columns': columns_of(match[3])})
                elif re.match(r'(CHECK|KEY|INDEX)\b', item):
                    continue
                else:
                    match = re.match(r'(\w+) (\w+(?:\([^)]*\))?)(.*)', item)
                    column, kind, rest = match[1], match[2].lower(), match[3].upper()
                    table['columns'][column] = {'type': kind,
                                                'nullable': 'NOT NULL' not in rest and 'PRIMARY KEY' not in rest,
                                                'generated': 'GENERATED ALWAYS' in rest}
                    table['order'].append(column)
                    if 'PRIMARY KEY' in rest:
                        table['pk'] = [column]
                    if re.search(r'\bUNIQUE\b', rest):
                        table['unique'].append([column])
            tables[name] = table
        for name, body in re.findall(r'ALTER TABLE (\w+)\s+(.*?);', sql, re.S):
            for match in re.finditer(r'ADD COLUMN (\w+) (\w+(?:\([^)]*\))?)([^,]*)', body):
                tables[name]['columns'][match[1]] = {'type': match[2].lower(),
                                                     'nullable': 'NOT NULL' not in match[3].upper(), 'generated': False}
                tables[name]['order'].append(match[1])
            for match in re.finditer(r'MODIFY (?:COLUMN )?(\w+) (\w+(?:\([^)]*\))?)([^,]*)', body):
                column = tables[name]['columns'][match[1]]
                column['type'] = match[2].lower()
                column['nullable'] = 'NOT NULL' not in match[3].upper()
            # Contraintes d'unicité retirées ou ajoutées (ex. migration 015 : unicité portée par les index aveugles).
            table = tables[name]
            for match in re.finditer(r'DROP (?:INDEX|KEY) (\w+)', body):
                columns = table['unique_names'].pop(match[1], None)
                if columns is not None:
                    table['unique'].remove(columns)
            for match in re.finditer(r'ADD CONSTRAINT (\w+) UNIQUE (?:KEY |INDEX )?\(([^)]*)\)', body):
                columns = columns_of(match[2])
                table['unique'].append(columns)
                table['unique_names'][match[1]] = columns
    return tables


def validate(tables):
    problems = []
    if len(tables) != EXPECTED_TABLES:
        problems.append(f'{len(tables)} tables trouvées, {EXPECTED_TABLES} attendues')
    domain_tables = [t for _, members in DOMAINS.values() for t in members]
    if sorted(domain_tables) != sorted(tables):
        problems.append('Domaines incomplets ou en double : ' + str(set(tables) ^ set(domain_tables)))
    for name, table in tables.items():
        if not table['pk']:
            problems.append(f'{name} : clé primaire absente')
        for fk in table['fks']:
            parent = tables.get(fk['parent'])
            if parent is None or any(c not in parent['columns'] for c in fk['parent_columns']):
                problems.append(f"{name} : référence invalide vers {fk['parent']}")
            if any(c not in table['columns'] for c in fk['columns']):
                problems.append(f'{name} : colonne de clé étrangère inconnue')
    for name, columns in RESTRICTED.items():
        for column in columns - set(tables.get(name, {}).get('columns', {})):
            problems.append(f'Colonne Restreint inconnue : {name}.{column}')
    if problems:
        raise SystemExit('ERD non généré :\n- ' + '\n- '.join(problems))


def cardinality(table, fk):
    parent_side = '|o' if any(table['columns'][c]['nullable'] for c in fk['columns']) else '||'
    # Au plus un enfant par parent si les colonnes de la FK contiennent une clé unique de l'enfant.
    keys = [table['pk']] + table['unique']
    child_side = 'o|' if any(set(k) <= set(fk['columns']) for k in keys) else 'o{'
    return parent_side, child_side


def is_actor(fk):
    return any(c in ACTOR_COLUMNS for c in fk['columns'])


def relation_line(name, table, fk):
    left, right = cardinality(table, fk)
    return f'    {fk["parent"]} {left}--{right} {name} : "{", ".join(fk["columns"])}"'


def attribute_line(name, table, column):
    info = table['columns'][column]
    # Mermaid refuse virgules, espaces et guillemets dans un type : decimal(12,2) → decimal, enum('a', 'b') → enum.
    kind = re.sub(r'\(.*\)', '', info['type']) if info['type'].startswith(('decimal', 'enum')) else info['type']
    keys = []
    if column in table['pk']:
        keys.append('PK')
    if any(column in fk['columns'] for fk in table['fks']):
        keys.append('FK')
    if column not in table['pk'] and any(column in u for u in table['unique']):
        keys.append('UK')
    notes = []
    if info.get('generated'):
        notes.append('calculée')
    if info['nullable']:
        notes.append('NULL')
    if column in RESTRICTED.get(name, ()):
        notes.append('RESTREINT')
    actor = [fk for fk in table['fks'] if is_actor(fk) and column in fk['columns']]
    if actor:
        notes.append('auteur → ' + actor[0]['parent'])
    line = f'        {kind} {column}'
    if keys:
        line += ' ' + ', '.join(keys)
    if notes:
        line += ' "' + ' · '.join(notes) + '"'
    return line


def domain_diagram(tables, title, members):
    lines = ['---', f'title: SecurePayroll — {title}', '---', 'erDiagram']
    # Les FK de traçabilité sont signalées dans les attributs, sans trait, pour la lisibilité.
    referenced = {}
    for name in members:
        for fk in tables[name]['fks']:
            if fk['parent'] not in members and not is_actor(fk):
                referenced.setdefault(fk['parent'], set()).update(fk['parent_columns'])
    for name in members:
        lines.append(f'    {name} {{')
        lines += [attribute_line(name, tables[name], c) for c in tables[name]['order']]
        lines.append('    }')
    for name in sorted(referenced):
        lines.append(f'    {name} {{')
        for column in [c for c in tables[name]['order'] if c in referenced[name]]:
            lines.append(f'        {tables[name]["columns"][column]["type"]} {column} PK "autre domaine"')
        lines.append('    }')
    for name in members:
        lines += [relation_line(name, tables[name], fk) for fk in tables[name]['fks'] if not is_actor(fk)]
    return '\n'.join(lines) + '\n'


def global_diagram(tables):
    lines = ['---', 'title: SecurePayroll — vue globale (relations structurelles)',
             'config:', '  er:', '    layoutDirection: LR', '---', 'erDiagram']
    for _, members in DOMAINS.values():
        for name in members:
            lines.append(f'    {name} {{')
            for column in tables[name]['pk']:
                lines.append(f'        {tables[name]["columns"][column]["type"]} {column} PK')
            lines.append('    }')
    for _, members in DOMAINS.values():
        for name in members:
            lines += [relation_line(name, tables[name], fk) for fk in tables[name]['fks'] if not is_actor(fk)]
    return '\n'.join(lines) + '\n'


def relations_inventory(tables):
    rows = []
    for _, members in DOMAINS.values():
        for name in members:
            for fk in tables[name]['fks']:
                left, right = cardinality(tables[name], fk)
                parent = {'||': '1', '|o': '0..1'}[left]
                child = {'o{': '0..N', 'o|': '0..1'}[right]
                rows.append(f"| `{name}` | `{', '.join(fk['columns'])}` | `{fk['parent']}`"
                            f"(`{', '.join(fk['parent_columns'])}`) | {parent} → {child} | "
                            f"{'Traçabilité' if is_actor(fk) else 'Structurelle'} |")
    actor = sum(is_actor(fk) for t in tables.values() for fk in t['fks'])
    total = sum(len(t['fks']) for t in tables.values())
    header = ['# Inventaire des relations (clés étrangères)', '',
              '> Fichier **généré** par `python3 bin/generate-erd.py` depuis `database/migrations/*.sql`. '
              'Ne pas modifier à la main.', '',
              f'**{len(tables)} tables, {total} clés étrangères** : {total - actor} structurelles et '
              f'{actor} de traçabilité (auteur d\'une action, omises de la vue globale).', '',
              'Cardinalité « parent → enfant » : `1` le parent est obligatoire ; `0..1` la clé étrangère '
              'accepte NULL (avec une clé composite, MySQL ne contrôle pas la référence dès qu\'une '
              'composante est NULL) ; côté enfant, `0..1` quand les colonnes de la clé étrangère contiennent '
              'une clé primaire ou unique de l\'enfant.', '',
              '| Table enfant | Colonnes | Table parente (colonnes) | Cardinalité | Nature |',
              '|---|---|---|---|---|']
    return '\n'.join(header + rows) + '\n'


def diagrams_page(files):
    lines = ['# ERD de SecurePayroll', '',
             '> Fichier **généré** par `python3 bin/generate-erd.py` depuis `database/migrations/*.sql`. '
             'Ne pas modifier à la main. Les diagrammes s\'affichent sur GitHub et dans l\'aperçu Markdown '
             'de VS Code ; les sources `.mmd` sont à côté de ce fichier.', '',
             'Notation : `PK` clé primaire, `FK` clé étrangère, `UK` membre d\'une contrainte d\'unicité ; '
             '`"NULL"` colonne facultative ; `"RESTREINT"` donnée du niveau le plus sensible '
             '(voir `02-CLASSIFICATION-DES-DONNEES.md`) ; `"auteur → accounts"` clé étrangère de '
             'traçabilité, signalée sans trait pour la lisibilité (liste complète dans `RELATIONS.md`). '
             'Liens : `||` exactement un, `|o` zéro ou un, `o{` zéro ou plusieurs.', '']
    for name, content in files.items():
        if name.endswith('.mmd'):
            title = re.search(r'title: (.*)', content)[1]
            lines += [f'## {title.replace("SecurePayroll — ", "")}', '', f'Source : [`{name}`]({name})', '',
                      '```mermaid', content.rstrip(), '```', '']
    return '\n'.join(lines)


def outputs(tables):
    files = {'ERD-00-GLOBAL.mmd': global_diagram(tables)}
    for key, (title, members) in DOMAINS.items():
        files[f'ERD-{key}.mmd'] = domain_diagram(tables, title, members)
    files['ERD.md'] = diagrams_page(files)
    files['RELATIONS.md'] = relations_inventory(tables)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true', help='vérifier sans écrire')
    args = parser.parse_args()
    tables = parse()
    validate(tables)
    files = outputs(tables)
    stale = [name for name, content in files.items()
             if not (OUTPUT / name).is_file() or (OUTPUT / name).read_text() != content]
    if args.check:
        if stale:
            sys.exit('ERD périmé, relancer bin/generate-erd.py : ' + ', '.join(stale))
        print(f'ERD à jour : {len(tables)} tables, {sum(len(t["fks"]) for t in tables.values())} clés étrangères.')
        return
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name in stale:
        (OUTPUT / name).write_text(files[name])
    print(f'{len(tables)} tables, {sum(len(t["fks"]) for t in tables.values())} clés étrangères ; '
          f'{len(stale)} fichier(s) écrit(s) dans {OUTPUT.relative_to(ROOT)}.')


if __name__ == '__main__':
    main()
