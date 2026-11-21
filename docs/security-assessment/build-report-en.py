#!/usr/bin/env python3
"""Generates the English SecurePayroll report as .docx (HTML + LibreOffice).
Formal academic prose, linking words, no bullet lists, embedded screenshots."""
import base64, pathlib, subprocess, sys, tempfile
from io import BytesIO
from PIL import Image

def _shrink(path, maxw=1400):
    """Lightly downscale very wide images (keeps the docx reasonable) and return bytes + extension.
    On a machine with normal free RAM this is optional; set maxw huge to keep originals untouched."""
    im = Image.open(path)
    fmt = (im.format or 'PNG').upper()
    if im.width <= maxw:
        data = pathlib.Path(path).read_bytes()
        return data, pathlib.Path(path).suffix.lstrip('.').replace('jpg', 'jpeg')
    im = im.convert('RGB').resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
    buf = BytesIO()
    im.save(buf, 'JPEG', quality=88, optimize=True)
    return buf.getvalue(), 'jpeg'

ROOT = pathlib.Path(__file__).resolve().parents[2]  # repository root (docs/security-assessment/<script>)
CAP = ROOT / 'docs/security-assessment/captures-phase7'
ERD = ROOT / 'docs/security-assessment/erd/images'
ARCHI = ROOT / 'docs/security-assessment/architecture.png'
CR = ROOT / 'docs/security-assessment/captures-rapport'
OUT = ROOT / 'SecurePayroll-Security-Report.docx'
SP = pathlib.Path(tempfile.mkdtemp(prefix='securepayroll-report-'))  # intermediates outside the repo

_fig = 0
def img(path, width=560, caption=''):
    global _fig
    data, ext = _shrink(path)
    b64 = base64.b64encode(data).decode()
    _fig += 1
    cap = f'<p class="cap">Figure {_fig} — {caption}</p>' if caption else ''
    return (f'<p class="imgp"><img src="data:image/{ext};base64,{b64}" width="{width}"></p>{cap}')

def figcap(caption):
    global _fig
    _fig += 1
    return f'<p class="cap">Figure {_fig} — {caption}</p>'

CSS = """
<style>
body { font-family: 'Liberation Serif','Times New Roman',serif; font-size: 12pt; line-height: 1.4; }
h1 { font-family: 'Liberation Sans',Arial,sans-serif; font-size: 18pt; color:#1b3a5b; page-break-before: always; }
h2 { font-family: 'Liberation Sans',Arial,sans-serif; font-size: 14pt; color:#23527c; }
h3 { font-family: 'Liberation Sans',Arial,sans-serif; font-size: 12.5pt; color:#2c3e50; }
p { text-align: justify; margin: 6pt 0; }
table { border-collapse: collapse; width: 100%; font-size: 10.5pt; margin: 8pt 0; }
th,td { border: 1px solid #889; padding: 4pt 6pt; text-align: left; vertical-align: top; }
th { background: #e8eef5; }
pre { background: #f3f4f6; border: 1px solid #ccc; padding: 6pt; font-family: 'Liberation Mono',monospace; font-size: 9pt; white-space: pre-wrap; }
.cap { font-style: italic; font-size: 10pt; color:#444; text-align:center; margin-top:2pt; }
.imgp { text-align:center; margin: 8pt 0 2pt 0; }
.cover { text-align:center; }
.cover .big { font-size: 20pt; font-weight: bold; color:#1b3a5b; }
.cover .mid { font-size: 14pt; }
.toc p { margin: 2pt 0; text-align:left; }
</style>
"""

# ------- CONTENT -------
H = []
def add(s): H.append(s)

# ---- COVER PAGE ----
add('<div class="cover">')
add('<p class="mid">International University of Rabat (UIR)</p>')
add('<p class="mid">Fifth-Year Engineering — Cybersecurity</p>')
add('<p class="mid">Module: Database Security</p>')
add('<p>&nbsp;</p><p>&nbsp;</p>')
add('<p class="mid">Project Report</p>')
add('<p class="big">Design, Implementation, Testing and Hardening<br>of a Secure Payroll System — SecurePayroll</p>')
add('<p>&nbsp;</p><p>&nbsp;</p>')
add('<p class="mid"><b>Supervisor:</b> Dr. Harazeem Abdulganiyu</p>')
add('<p class="mid"><b>Prepared by:</b></p>')
add('<p class="mid">CISSE Marwane Mouawiyah<br>LANKOANDE Melwine Ange Lormel Lankoulmani<br>'
    'SOUNDA Abdelkerim Ahmat<br>TILENGAR Mbaihornom Lionel<br>ZONGO Nabonswendé Regis Epiphane</p>')
add('<p>&nbsp;</p><p class="mid">Academic Year 2025 — 2026</p>')
add('</div>')

# ---- TABLE OF CONTENTS (static) ----
add('<h1 style="page-break-before:always">Table of Contents</h1>')
toc = [
 '1. Executive Summary', '2. Introduction and System Description', '3. System Architecture',
 '4. ER Diagram and Database Design', '5. Data Classification and CIA Analysis',
 '6. Threat Model', '7. Authentication Design', '8. RBAC and Access-Control Matrix',
 '9. Least-Privilege Implementation', '10. Vulnerability Analysis',
 '11. SQL Injection Investigation and Remediation', '12. Sensitive Data Protection',
 '13. Auditing and Monitoring', '14. Backup and Recovery', '15. Database Hardening',
 '16. Security Incident Investigation', '17. Final Security Assessment', '18. Recommendations',
 '19. Conclusion', '20. References',
 'Appendix A — Detailed Entity-Relationship Diagrams', 'Appendix B — Reproducing the Evidence']
add('<div class="toc">')
for t in toc:
    add(f'<p>{t}</p>')
add('</div>')

# ===================== 1. EXECUTIVE SUMMARY =====================
add('<h1>1. Executive Summary</h1>')
add("<p>This report describes the design and the securing of SecurePayroll, a payroll application built "
    "on a MySQL database. Payroll handles highly sensitive information — bank details, identity "
    "documents, social-security numbers and salaries — whose disclosure or alteration would directly "
    "harm both individuals and the organisation. For that reason, security guided every design "
    "decision, from the relational schema through to operation.</p>")
add("<p>The system rests on a single guiding principle: <b>defence in depth</b> combined with "
    "<b>end-to-end least privilege</b>. The application never accesses the tables directly; every "
    "operation passes through tightly scoped MySQL roles and through stored procedures executed under "
    "the identity of locked owner accounts. In addition, sensitive data is encrypted at rest, security "
    "activity is recorded in an append-only audit trail, backups are encrypted, and the attack surface "
    "is reduced to a private socket.</p>")
add("<p>By the end of the project, the nine required security dimensions are covered and, above all, "
    "<b>proven</b>: two hundred and fourteen automated checks, replayable on a disposable "
    "instance, validate authentication, authorisation, least privilege, injection resistance, "
    "encryption, auditing, backup, hardening and investigative capability. Where prevention reaches its "
    "limits — a database administrator necessarily retains broad rights — detection and "
    "investigative capability take over.</p>")

# ===================== 2. INTRODUCTION =====================
add('<h1>2. Introduction and System Description</h1>')
add("<p>The growing number of database breaches has made their protection a central concern of "
    "cybersecurity. A payroll database concentrates precisely the data an attacker covets. It is in "
    "this context that SecurePayroll is situated, whose aim is not to offer a sophisticated interface "
    "but to demonstrate a <b>secure data architecture</b> that is methodical and verifiable.</p>")
add("<p>Functionally, the application manages employees, their assignments, their compensation, the "
    "payroll computation and the settlements. Several profiles take part: the employee, the human "
    "resources manager, the payroll manager, the finance manager, the application administrator and "
    "the security auditor. In addition to these application roles, dedicated database operation "
    "accounts (administration, backup, investigation) are kept strictly separate from the former.</p>")
add("<p>Technically, the <code>secure_payroll</code> database is hosted on a <b>private</b> MySQL 8.4 "
    "instance, reachable only through a local Unix socket, with no network exposure whatsoever. The "
    "whole — schema, accounts, roles, procedures, triggers and demonstration datasets — is installed "
    "deterministically, which makes every claim in this report reproducible. Secrets and encryption "
    "keys are stored outside the database and outside the code repository. The assets to protect are "
    "accordingly split into public, internal and restricted data, the latter receiving the strongest "
    "protections.</p>")

# ===================== 3. ARCHITECTURE =====================
add('<h1>3. System Architecture</h1>')
add("<p>The SecurePayroll architecture obeys one non-negotiable rule: <b>the application never "
    "accesses the tables directly</b>. Every request travels through a chain of responsibilities whose "
    "scope narrows at each step, so that a compromise at one level does not grant access to the "
    "next.</p>")
add(img(ARCHI, 470, "Layered architecture: the application has no direct access to the tables."))
add("<p>At the top, the service account <code>svc_php</code> holds <b>no privilege of its own</b>: it "
    "can act only through MySQL roles, each limited to executing the procedures of its domain. No "
    "direct read or write statement against a table is ever issued by the application code. "
    "Consequently, an attacker who compromised <code>svc_php</code> would obtain neither direct access "
    "to the tables nor the privileges of a data owner.</p>")
add("<p>Each procedure is in fact declared under the name of a <b>domain owner</b> (for example "
    "<code>hr_module_owner</code>, <code>personal_data_owner</code> or <code>audit_owner</code>) and "
    "runs under its identity. These owners, however, are <b>locked</b> accounts with a random "
    "password: no one can connect as them. They exist only to carry, inside the procedures, the "
    "privileges on the few tables concerned. This separation achieves least privilege at two levels: "
    "the caller holds only the right to execute the procedure, and the procedure can touch only its own "
    "scope.</p>")
add("<p>Finally, the isolation of the instance completes this design. The server starts with no "
    "network (<code>--skip-networking</code>), no external configuration file "
    "(<code>--no-defaults</code>) and no persisted variable, so that the security configuration, "
    "explicit in the launch code, cannot be loosened without our knowledge. An internal safeguard even "
    "refuses to run if the instance were to open a port: hardening is therefore verified continuously, "
    "not merely assumed.</p>")

# ===================== 4. ERD =====================
add('<h1>4. ER Diagram and Database Design</h1>')
add("<p>The <code>secure_payroll</code> database is built by a series of ordered SQL migrations "
    "installed on the private instance. Every table uses the InnoDB engine and a case- and "
    "accent-sensitive collation; amounts are stored as exact decimals and timestamps in UTC, set by "
    "the database itself to avoid any drift on the application side.</p>")
add("<p>The design cleanly separates the major domains — identity and access control, human-resources "
    "organisation, compensation, payroll and settlements. This separation is not merely functional: it "
    "supports least privilege, since each role receives rights only on the procedures of its domain. "
    "Referential integrity is guaranteed by strict foreign keys, and several tables are made "
    "<b>immutable</b>: instead of a deletion, history is preserved and any attempt to modify a "
    "historised record is refused by a trigger.</p>")
add(img(ERD / 'ERD-00-GLOBAL.png', 620, "Global entity-relationship diagram of secure_payroll."))
add("<p>The detailed per-domain diagrams (identity and RBAC, HR organisation, compensation, payroll, "
    "settlements) appear in Appendix A. They show in particular the encrypted personal-data table, "
    "isolated and linked to the employee, as well as the append-only audit table at the heart of "
    "monitoring.</p>")

# ===================== 5. CLASSIFICATION + CIA =====================
add('<h1>5. Data Classification and CIA Analysis</h1>')
add("<p>Before protecting, one must classify. Every table and, where relevant, every column was placed "
    "in one of three sensitivity levels, so as to match the protections to the real risk.</p>")
add('<table><tr><th>Level</th><th>Examples</th><th>Associated protection</th></tr>'
    '<tr><td><b>Restricted</b></td><td>Bank details, national ID, social security, salaries, password '
    'hashes, audit trail</td>'
    '<td>Encryption at rest, access through procedures, auditing, no direct read</td></tr>'
    '<tr><td><b>Internal</b></td><td>Assignments, contracts, organisational structure</td>'
    '<td>Access through roles, least privilege</td></tr>'
    '<tr><td><b>Public</b></td><td>Reference data (departments, job titles)</td>'
    '<td>Controlled read</td></tr></table>')
add(figcap("Data classification into three sensitivity levels."))
add("<p>This classification is matched by an analysis along the confidentiality, integrity and "
    "availability triad. The <b>confidentiality</b> of restricted data is ensured by encryption at "
    "rest and by the absence of any direct access. <b>Integrity</b> rests on the immutability of "
    "history, on referential constraints and on an append-only audit trail that no ordinary operation "
    "can alter and whose tampering by a privileged account is itself detected. "
    "<b>Availability</b>, finally, is addressed by an encrypted backup strategy whose restoration is "
    "actually verified. Thus, each security need is tied to a precise control, detailed in the "
    "following sections.</p>")

# ===================== 6. THREAT MODEL =====================
add('<h1>6. Threat Model</h1>')
add("<p>The design builds on a threat model that enumerates the plausible attackers and the scenarios "
    "they might attempt. We distinguish the external attacker, who seeks to break into the system, the "
    "legitimate user who would try to exceed their rights, and the privileged actor — a database "
    "administrator — whose broad access constitutes a particular risk.</p>")
add("<p>Among the identified threats, one deserves special attention and serves as a common thread "
    "through to the final investigation: risk <b>T-14</b>, namely the <b>direct access of a privileged "
    "operator</b> to the database, outside the application. An administrator necessarily holds broad "
    "rights for maintenance purposes. Rather than claiming to prevent this — which would be illusory — "
    "we made the explicit choice to <b>accept this risk and to treat it through detection</b>: any "
    "direct write on a sensitive table is recorded in the audit trail, attributed to the real account. "
    "This decision shapes the defence and is concretely verified during the simulated incident of "
    "Section 16.</p>")
add("<p>For every other threat — SQL injection, indirect access to another's object (IDOR), excessive "
    "privileges, secret leakage, misconfiguration — a preventive control is associated and then "
    "verified. The threat model is therefore not a theoretical exercise: it ties each risk to a "
    "concrete, tested countermeasure.</p>")

# ===================== 7. AUTHENTICATION =====================
add('<h1>7. Authentication Design</h1>')
add("<p>Authentication is the first barrier. The passwords of application accounts are never stored in "
    "clear text nor as a reversible digest: they are hashed with <b>Argon2id</b>, a modern derivation "
    "function designed to resist hardware brute-force attacks through its tunable memory and time cost. "
    "Should the database be stolen, the hashes therefore do not allow the passwords to be "
    "recovered.</p>")
add("<p>Beyond storage, the authentication policy actively limits attempts. Two independent counters "
    "operate over a fifteen-minute window: after <b>five failed attempts on the same account</b>, "
    "further tries on that account are blocked, which counters brute force; and after <b>thirty "
    "attempts from the same IP address</b>, that address is blocked, which counters password spraying "
    "across several accounts. A blocked account triggers no Argon2id computation, so the lockout cannot "
    "itself be turned into a resource-exhaustion vector. Each failure is recorded, which makes an "
    "ongoing attack detectable. Onboarding follows the same rigour: an account is created by human "
    "resources with a temporary password to be changed at first login, and an employee number is "
    "generated by the database.</p>")
add("<p>Finally, two planes must be distinguished. <b>Application</b> accounts authenticate through "
    "Argon2id at the application level; the <b>MySQL</b> accounts (service, operators) use the server's "
    "<code>caching_sha2_password</code> mechanism, with random passwords, while the domain owners "
    "remain locked. This double layer guarantees that no access, whether through the application or "
    "direct, relies on a weak secret.</p>")
add("<p>To illustrate this rigour, the complete journey of a new employee, from account creation to "
    "activation, is reproduced below. Everything begins when the human-resources department registers "
    "the employee; no bank details are entered at this stage, the employee filling in their own "
    "details later.</p>")
add(img(CR / 'onb-1-ajout-employe.png', 540, "Creation of an employee by human resources."))
add("<p>As soon as the record is created, a professional account is provisioned automatically and a "
    "permanent employee number is assigned by the database. An invitation is then sent to the "
    "employee's personal address, without anyone knowing their future password.</p>")
add(img(CR / 'onb-2-compte-cree.png', 540, "Professional account created and invitation sent."))
add("<p>The invitation contains a <b>temporary password</b>, valid for seventy-two hours and which "
    "must be changed at first login. After that window, the temporary password stops working, which "
    "limits the exposure window.</p>")
add(img(CR / 'onb-3-email-mdp-temporaire.png', 540,
    "Invitation sent to the employee, carrying a time-limited temporary password."))
add("<p>Equipped with this temporary password, the employee then reaches the login page.</p>")
add(img(CR / 'onb-4-connexion.png', 540, "Login page of the application."))
add("<p>At this first login, access to the rest of the application is <b>blocked</b> until the "
    "temporary password has been replaced. The enforced policy requires at least twelve characters and "
    "forbids reusing the last name, first name or username, which rules out weak or guessable "
    "secrets.</p>")
add(img(CR / 'onb-5-changement-mdp.png', 540,
    "Account activation: mandatory password change at first login."))
add("<p>Once the personal password is saved, the account becomes fully active and the employee reaches "
    "their workspace, limited to the functions matching their role.</p>")
add(img(CR / 'onb-6-tableau-de-bord.png', 540, "Activated account: access to the employee's workspace."))

# ===================== 8. RBAC =====================
add('<h1>8. RBAC and Access-Control Matrix</h1>')
add("<p>Authorisation rests on a role model: six application roles (employee, HR manager, payroll "
    "manager, finance manager, application administrator, security auditor) and three operation roles "
    "(administration, backup, investigation). Each role corresponds to a minimal set of permissions, "
    "embodied by the only procedures it may execute. The access-control matrix below summarises, "
    "domain by domain, the permissions granted to each of the six application roles (a ● mark denotes "
    "the granted permission).</p>")
add('<table>'
    '<tr><th>Domain — permission</th><th>Employee</th><th>HR</th><th>Finance</th><th>Payroll</th><th>Admin</th><th>Auditor</th></tr>'
    '<tr><td>Employee identity (view, create, update)</td><td></td><td>●</td><td></td><td></td><td></td><td></td></tr>'
    '<tr><td>Reference data (departments, positions)</td><td></td><td>●</td><td></td><td></td><td></td><td></td></tr>'
    '<tr><td>Contracts (view, create, close)</td><td></td><td>●</td><td></td><td></td><td></td><td></td></tr>'
    '<tr><td>Assignments (view, create, close)</td><td></td><td>●</td><td></td><td></td><td></td><td></td></tr>'
    '<tr><td>Compensation — view</td><td></td><td>●</td><td>●</td><td></td><td></td><td></td></tr>'
    '<tr><td>Compensation — propose</td><td></td><td>●</td><td></td><td></td><td></td><td></td></tr>'
    '<tr><td>Compensation — decide</td><td></td><td></td><td>●</td><td></td><td></td><td></td></tr>'
    '<tr><td>Payroll — view</td><td></td><td>●</td><td>●</td><td>●</td><td></td><td>●</td></tr>'
    '<tr><td>Payroll — open a period, validate inputs</td><td></td><td></td><td>●</td><td></td><td></td><td></td></tr>'
    '<tr><td>Payroll — enter variable inputs</td><td></td><td>●</td><td></td><td></td><td></td><td></td></tr>'
    '<tr><td>Payroll — compute</td><td></td><td></td><td></td><td>●</td><td></td><td></td></tr>'
    '<tr><td>Payslips — verify, publish, correct</td><td></td><td></td><td></td><td>●</td><td></td><td></td></tr>'
    '<tr><td>Payslips — approve or reject</td><td></td><td></td><td>●</td><td></td><td></td><td></td></tr>'
    '<tr><td>Payslips — view one\'s own (published)</td><td>●</td><td></td><td></td><td></td><td></td><td></td></tr>'
    '<tr><td>Settlements — pay, decide a recovery</td><td></td><td></td><td>●</td><td></td><td></td><td></td></tr>'
    '<tr><td>Settlements — request, receive a recovery</td><td></td><td></td><td></td><td>●</td><td></td><td></td></tr>'
    '<tr><td>IAM — view roles</td><td></td><td></td><td></td><td></td><td>●</td><td>●</td></tr>'
    '<tr><td>IAM — grant, revoke a role</td><td></td><td></td><td></td><td></td><td>●</td><td></td></tr>'
    '</table>')
add('<p class="cap">Access-control matrix — permissions by domain and by application role. To these '
    'six roles are added three operation roles (database administration, read-only backup, '
    'investigation) outside the application scope.</p>')
add("<p>A role-based control, however, is not sufficient on its own. An authenticated employee could "
    "try to reach a colleague's record simply by changing the identifier in the URL — an IDOR attack. "
    "SecurePayroll defends against this with <b>object-level authorisation</b>, verified server-side on "
    "every request: an unauthorised user reaches only their own employee identifier. This protection "
    "rests on an ownership check, not on obscuring the identifier; encoding or encrypting the "
    "identifier would amount to security through obscurity and would not replace this control.</p>")
add(img(CAP / '04-idor-employes-bloque.jpg', 540,
    "Defence against IDOR: an employee who forces the URL of another record receives a refusal (403), "
    "and the attempt is logged."))
add("<p>Furthermore, any unauthorised access attempt is <b>refused and then logged</b>, which feeds "
    "the suspicious-activity detection described in Section 13.</p>")

# ===================== 9. LEAST PRIVILEGE =====================
add('<h1>9. Least-Privilege Implementation</h1>')
add("<p>Least privilege has been pushed to its conclusion. During a dedicated phase, the direct rights "
    "of the service account <code>svc_php</code> were <b>revoked</b> and then replaced by roles. From "
    "that point on, the application account holds no privilege of its own: it holds only membership of "
    "roles, each limited to executing the procedures within its scope. No role has any direct write "
    "right on a table.</p>")
add("<p>This rigour is verified objectively. The matrix below measures, for each role, the number of "
    "procedures it may execute out of the twenty-two that exist and the number of tables it may read "
    "directly out of the sixteen checked. It confirms that no role exceeds its strict necessity and "
    "that the service account, on its own, holds <b>no</b> right of its own.</p>")
add('<table>'
    '<tr><th>Role</th><th>MySQL account</th><th>Executable procedures</th><th>Directly readable tables</th></tr>'
    '<tr><td>Employee</td><td><code>sp_employee</code></td><td>5 / 22</td><td>0 / 16</td></tr>'
    '<tr><td>HR manager</td><td><code>sp_hr_manager</code></td><td>10 / 22</td><td>8 / 16</td></tr>'
    '<tr><td>Finance manager</td><td><code>sp_finance_manager</code></td><td>8 / 22</td><td>5 / 16</td></tr>'
    '<tr><td>Payroll manager</td><td><code>sp_payroll_manager</code></td><td>6 / 22</td><td>0 / 16</td></tr>'
    '<tr><td>Application administrator</td><td><code>sp_application_administrator</code></td><td>3 / 22</td><td>0 / 16</td></tr>'
    '<tr><td>Security auditor</td><td><code>sp_security_auditor</code></td><td>4 / 22</td><td>0 / 16</td></tr>'
    '<tr><td>Password change</td><td><code>sp_password</code></td><td>1 / 22</td><td>0 / 16</td></tr>'
    '<tr><td><b>Service account</b></td><td><code>svc_php</code></td><td><b>0</b> (no right of its own)</td><td><b>0 / 16</b></td></tr>'
    '</table>')
add('<p class="cap">Least-privilege matrix, verified on a real instance by '
    '<code>tests/privilege_matrix.py</code>. The eight most sensitive tables — including '
    '<code>employee_personal_data</code> and the audit log — are directly readable by <b>no</b> role; '
    'all access goes through a fixed-scope procedure.</p>')
add("<p>It should be stressed that the few authorised table reads (HR and finance) concern only "
    "unprotected management data — departments, positions, contracts, salary conditions — never the "
    "encrypted data nor the audit trail. Moreover, no dangerous global privilege (file reading, server "
    "shutdown, account creation) is granted outside the administration account and the MySQL system "
    "accounts, which the hardening audit confirms (Section 15).</p>")

# ===================== 10. VULNERABILITY =====================
add('<h1>10. Vulnerability Analysis</h1>')
add("<p>A vulnerability analysis was carried out across the whole system in order to identify, and then "
    "correct, the classic weaknesses of database-backed applications: SQL injection, indirect access "
    "to another's object, excessive privileges, secret exposure and misconfiguration. For each one, we "
    "followed a four-step approach — <b>root cause, impact, mitigation, verification</b> — in keeping "
    "with the requirement never to merely show a flaw without explaining it.</p>")
add("<p>SQL injection in particular was the subject of an in-depth study, presented in the next "
    "section together with its before/after demonstration. In keeping with the project rules, that "
    "demonstration was carried out only against components the group built for this purpose, never "
    "against the application itself.</p>")

# ===================== 11. SQL INJECTION =====================
add('<h1>11. SQL Injection Investigation and Remediation</h1>')
add("<p>SQL injection arises when user input is concatenated directly into a query: the attacker can "
    "then divert the query's logic to read or modify data not intended for them. That is the <b>root "
    "cause</b>, and its <b>impact</b> is major since it can go as far as extracting the entire "
    "database.</p>")
add("<p>The chosen <b>mitigation</b> is twofold. On the one hand, all of the application's queries are "
    "<b>parameterised</b>: the values supplied by the user are transmitted separately from the query "
    "text, so that they can no longer alter its structure. On the other hand, data access goes through "
    "<b>stored procedures</b> with a fixed scope, which further reduces the exploitable surface. The "
    "<b>verification</b>, finally, consists in replaying on the corrected version the attack payloads "
    "that succeeded on the vulnerable version: all are now neutralised.</p>")
add("<p>To make the flaw tangible without ever weakening the application, a deliberately vulnerable "
    "“My access” page was built in a <b>confined laboratory</b>, served on a separate port (8099), "
    "while the real, corrected application remains served on its usual port (8080). The "
    "“before / after” demonstration replays three attack payloads of increasing severity, each on both "
    "versions.</p>")
add("<p>The first payload merely injects a single quote into the filter parameter. On the vulnerable "
    "version, this is enough to <b>break the query</b>: the server returns an SQL syntax error which, "
    "incidentally, discloses the query's structure — valuable information for the attacker. On the "
    "corrected version, by contrast, the input is validated upstream and politely rejected, without "
    "any SQL error leaking.</p>")
add(img(CR / 'sqli-erreur-before.png', 540,
    "Before — injecting a single quote triggers an SQL error (1064) that reveals the query."))
add(img(CR / 'sqli-erreur-after.png', 540,
    "After — the same input is validated and rejected, with no error leakage."))
add("<p>The second payload exploits an always-true condition, <code>' OR '1'='1</code>, to bypass the "
    "filter. On the vulnerable version, the result is telling: the attacker obtains <b>all of the role "
    "assignments</b>, far beyond their own. On the corrected version, the input is once again rejected "
    "and no data leaks.</p>")
add(img(CR / 'sqli-boolean-before.png', 540,
    "Before — the boolean injection “OR '1'='1” returns every role, the filter bypassed."))
add(img(CR / 'sqli-boolean-after.png', 540, "After — the same payload is rejected, no data exposed."))
add("<p>The third payload goes as far as exfiltration. By means of a <code>UNION SELECT login, "
    "password_hash … FROM accounts</code> clause, the attacker tries to read the accounts table. On "
    "the vulnerable version, they retrieve the logins and the <b>password hashes</b> of all accounts; "
    "fortunately, those hashes are Argon2id digests (Section 7), which remain extremely costly to "
    "crack. On the corrected version, the attack fails entirely.</p>")
add(img(CR / 'sqli-union-before.png', 560,
    "Before — the UNION injection exfiltrates the logins and the Argon2id hashes of the accounts."))
add(img(CR / 'sqli-union-after.png', 540, "After — the same UNION payload is neutralised, no data extracted."))
add("<p>These three pairs establish the expected <b>verification</b>: attacks that all succeeded on "
    "the vulnerable version are systematically neutralised on the corrected version, thanks to "
    "parameterised queries and input validation, not to any superficial filtering.</p>")

# ===================== 12. DATA PROTECTION =====================
add('<h1>12. Sensitive Data Protection</h1>')
add("<p>The most sensitive data — bank details, national identity document and social-security number "
    "— are <b>encrypted at rest</b>. The encryption uses the AES-256 algorithm in GCM mode, an "
    "<b>authenticated</b> mode: it guarantees both the confidentiality and the integrity of each "
    "value, so that any alteration of an encrypted value, whether in the database or in a backup, is "
    "detected at decryption. This choice is justified precisely by that detection capability, which an "
    "unauthenticated mode would not offer. It must be stated plainly, however, that each value is "
    "authenticated in isolation: the current format (version, nonce, ciphertext and tag) does not bind "
    "a ciphertext to the row and column it belongs to. GCM alone would therefore not detect an "
    "attacker with direct write access who swapped the encrypted values of two employees; binding each "
    "value to its row and column through associated data is a recommended improvement (Section 18).</p>")
add("<p>Encrypting a field, however, prevents searching it by equality. To reconcile confidentiality "
    "and usability, each sensitive value is accompanied by a <b>blind index</b>: a deterministic "
    "HMAC-SHA256 digest, computed with a dedicated key, on which the application performs its searches "
    "without ever handling the clear value. This index does not expose the plaintext; being "
    "deterministic, it does nonetheless reveal when two records share the same value, and because "
    "identifiers such as the national ID or the social-security number have limited entropy, its "
    "resistance to enumeration rests entirely on the secrecy of the dedicated key — which is precisely "
    "why that key is kept outside the database. Whoever obtained that key could recompute the digest of "
    "every candidate value; keeping it separate is therefore essential.</p>")
add("<p>The whole safety of the scheme finally rests on <b>key management</b>. Two separate keys — one "
    "for encryption, the other for the blind index — are kept outside the database and outside the "
    "code repository, in files with restricted permissions. Separating them from the database is "
    "essential: as Section 14 shows, a theft of the dump without these keys yields only unreadable "
    "ciphertext. Every consultation or modification of personal data is moreover logged.</p>")

# ===================== 13. AUDITING =====================
add('<h1>13. Auditing and Monitoring</h1>')
add("<p>A central audit table constitutes the source of truth for sensitive activities. Each entry "
    "answers the five expected questions: <b>when</b> the event occurred, <b>what</b> it was, <b>who</b> "
    "the author was — both the application account and the real MySQL account —, <b>which resource</b> "
    "is concerned, and whether the action <b>succeeded or failed</b>. Unlike a plain log file, this "
    "trail is queryable in SQL, which makes detection and investigation possible.</p>")
add("<p>Above all, this trail is <b>append-only</b>: BEFORE UPDATE and BEFORE DELETE triggers reject "
    "any modification or deletion of an entry, and these triggers fire for <b>every</b> account, root "
    "included, so no one can quietly alter or remove a line through ordinary data operations. One "
    "limit must be stated honestly: a database administrator holds schema rights and could, in "
    "principle, drop the triggers themselves before tampering. This is exactly the accepted T-14 "
    "residual risk (Section 6); it is not left unaddressed but shifted to <b>detection</b> and to the "
    "operational controls of Section 18 — real-time alerting on out-of-application writes, credential "
    "rotation and separation of duties. The append-only guarantee is thus absolute against every "
    "non-administrative account, and backed by detection against the administrator. Furthermore, the "
    "trail is fed by two complementary sources: the application, which logs business intent, and "
    "triggers on the sensitive tables, which record any write <b>even performed outside the "
    "application</b>. This second source is decisive, because it captures precisely the direct access "
    "of a privileged operator.</p>")
add(img(CAP / '01-audit-vue-ensemble.jpg', 580,
    "Monitoring page: suspicious signals (a burst of failures detected) and recent events."))
add("<p>Monitoring relies on signals computed automatically over twenty-four hours: a burst of login "
    "failures (indicative of brute force), repeated access refusals (an escalation attempt) and massive "
    "sensitive reads (exfiltration by a legitimate account). A page reserved for the auditor presents "
    "these signals and allows each event to be expanded to read its full forensic detail.</p>")
add(img(CAP / '02-audit-detail-connexion-echouee.jpg', 580,
    "Forensic detail of a failed login: the targeted account resolved, the source address and context."))
add("<p>Finally, monitoring itself respects least privilege. The audit page is accessible only to the "
    "auditor role; an employee who tried to open it receives a refusal. The trail, moreover, never "
    "contains any secret: neither password, nor entered credential, nor personal data in clear, only "
    "references and indicators.</p>")
add(img(CAP / '03-audit-acces-refuse-salarie.jpg', 540,
    "Access control over monitoring: an employee receives a refusal (403) on the audit page."))

# ===================== 14. BACKUP =====================
add('<h1>14. Backup and Recovery</h1>')
add("<p>Availability rests on a backup strategy that addresses each risk explicitly. The backup is "
    "<b>logical</b> and produces a consistent snapshot without blocking the application. It is "
    "performed by a <b>dedicated read-only account</b>, unable to write or delete, which extends least "
    "privilege into operation. The resulting file is then <b>encrypted at rest</b> with AES-256-GCM, "
    "and the keys — the backup key as well as the data-encryption keys — are <b>kept separately</b> "
    "from the dump.</p>")
add("<p>One point deserves emphasis, because it conditions any real recovery: a logical dump <b>does "
    "not contain the grants</b>. During a restoration, the tables and procedures are recreated, but the "
    "privileges attached to them — stored in the MySQL system schema — disappear with the objects. "
    "Recovery is therefore complete only after <b>reapplying the grant layer</b> from the "
    "administrative inventory. This lesson is built into the procedure.</p>")
add("<p>In keeping with the requirement that showing a backup file exists is not enough, a full "
    "recovery drill was replayed. After recording a ground truth, we caused a controlled loss — "
    "deletion of critical records <b>and</b> deletion of an entire table — then restored from the "
    "encrypted backup. The integrity verification then confirms that row counts are identical, that "
    "the encrypted columns are restored byte for byte, that sensitive data remains decryptable and "
    "that the audit trail stays intact and still append-only.</p>")
add('<pre>'
    'PASS Logical backup by backup_ops (role sp_backup, read-only)\n'
    'PASS Dump encrypted at rest (AES-256-GCM): no clear text remains\n'
    'PASS Without the correct backup key, restoration is refused (GCM)\n'
    'PASS Simulated loss: role_permissions emptied AND table employee_personal_data dropped\n'
    'PASS Row counts identical to the pre-loss state (28 tables)\n'
    'PASS Encrypted columns restored byte for byte\n'
    'PASS Restored sensitive data still decryptable (national ID identical)\n'
    'PASS Audit trail still append-only after restoration\n'
    '19 backup/recovery checks passed.</pre>')
add(figcap("Output of the replayable recovery drill (extract of the nineteen checks)."))

# ===================== 15. HARDENING =====================
add('<h1>15. Database Hardening</h1>')
add("<p>Hardening was not a layer added at the end of the project: the system is built "
    "“security first” from the outset. This phase therefore consisted mainly in <b>consolidating and "
    "verifying</b> the existing state, then adding a single residual fix. The summary below compares a "
    "default MySQL deployment with the delivered state.</p>")
add('<table><tr><th>Area</th><th>Before (default MySQL)</th><th>After (delivered)</th></tr>'
    '<tr><td>Default / anonymous accounts</td><td>Anonymous accounts possible, “test” database open</td>'
    '<td>No anonymous account, no “test” database, root limited to localhost</td></tr>'
    '<tr><td>Excessive privileges</td><td>Broad application account</td>'
    '<td>Least privilege through roles; svc_php with no direct right</td></tr>'
    '<tr><td>Weak accounts</td><td>Reversible hashing</td><td>Argon2id and caching_sha2_password</td></tr>'
    '<tr><td>Network exposure</td><td>TCP listening, X protocol open</td>'
    '<td>Socket-only (no port), X protocol disabled</td></tr>'
    '<tr><td>Logging</td><td>Limited, alterable audit</td><td>Append-only trail, private log</td></tr>'
    '<tr><td>Unneeded features</td><td>LOAD DATA LOCAL, file operations</td>'
    '<td>local_infile disabled, secure_file_priv set to NULL</td></tr>'
    '<tr><td>File permissions</td><td>Group-readable</td><td>Instance and keys with restricted rights</td></tr>'
    '<tr><td>Backup protection</td><td>Absent or in clear</td><td>Encrypted, dedicated account, keys kept apart</td></tr></table>')
add(figcap("Hardening before / after summary (extract)."))
add("<p>Each decision is justified. The <b>socket-only</b> mode removes the entire network attack "
    "surface; setting <code>secure_file_priv</code> to <b>NULL</b> forbids server-side file operations, "
    "even for the administrator, closing a classic exfiltration vector; the absence of an external "
    "configuration file makes the configuration reproducible and not alterable without our knowledge. "
    "Some measures remain deliberately out of scope, as they are moot under socket-only: network "
    "transport encryption, for instance, has no purpose in the absence of network traffic. The whole "
    "is verified automatically by a hardening audit covering the eleven required areas.</p>")

# ===================== 16. INCIDENT =====================
add('<h1>16. Security Incident Investigation</h1>')
add("<p>To test the system's investigative capability, an incident was simulated and then "
    "investigated. The scenario follows that of the assignment: several unauthorised access attempts "
    "to sensitive data, and a privileged account performing an unusual operation. Importantly, the "
    "incident is played with the system's <b>real mechanisms</b>, so that the evidence analysed is "
    "authentic.</p>")
add("<p>The investigation relies on several sources, each consulted with the appropriate role and "
    "without over-privilege: the application audit log, read by the auditor role, and the database "
    "records, read by an investigation role deprived of access to restricted data. The reconstructed "
    "timeline below summarises the sequence of events.</p>")
add('<table><tr><th>Moment</th><th>Event</th><th>Outcome</th><th>Actor</th><th>Resource</th></tr>'
    '<tr><td>T0 (×6)</td><td>Login failure</td><td>failure</td><td>unauthenticated (external IP)</td><td>HR account</td></tr>'
    '<tr><td>T1 (×3)</td><td>Access to an employee record</td><td><b>refused</b></td><td>employee account</td><td>other employees\' records</td></tr>'
    '<tr><td>T1 (×1)</td><td>Access to monitoring</td><td><b>refused</b></td><td>employee account</td><td>audit trail</td></tr>'
    '<tr><td>T2</td><td>Role grant (trigger)</td><td>success</td><td><b>administrator, outside the application</b></td><td>role assignment</td></tr>'
    '<tr><td>T3 (×2)</td><td>Attempt to erase the trail</td><td><b>refused (append-only)</b></td><td>administrator</td><td>audit trail</td></tr></table>')
add(figcap("Incident timeline reconstructed from the audit trail."))
add("<p>From this evidence alone, the investigation answers the seven required questions in turn. "
    "<b>What</b> happened is an attack in three stages: a brute-force attempt against an HR account — "
    "six consecutive failures, which means the account was blocked from the fifth attempt onward by "
    "the lockout policy of Section 7 — then several unauthorised access attempts, to other employees' "
    "records and to monitoring, all <b>refused</b>, and finally a privilege escalation carried out not "
    "through the application but by an administrator acting <b>directly on the database</b>, followed "
    "by a failed attempt to erase the traces. <b>When</b> it happened is fixed to the microsecond in "
    "UTC by the trail. <b>Which accounts</b> were involved are the targeted HR account, the employee "
    "account behind the unauthorised reads, and above all the administrator, recognised by their real "
    "MySQL identity rather than by any application actor. The external address seen during the "
    "brute-force stage is a documentation address reserved by RFC 5737, never a real one.</p>")
add("<p><b>Which resources</b> were affected are the employee records (access attempted and refused), "
    "the monitoring page (refused) and the role-assignment table (actually modified). As for <b>which "
    "controls held or failed</b>, object-level authorisation held, since every unauthorised access was "
    "refused, and the append-only trail held, since the deletion attempt failed; by design, the "
    "administrator's direct write is not prevented — the accepted T-14 risk — but it is fully logged "
    "and attributable. The <b>evidence</b> rests on the audit lines themselves — the burst of "
    "failures, the refusals, the role grant attributed to the administrator by a trigger — corroborated "
    "by the role-assignment record. The <b>corrective actions</b> follow directly: revoke the "
    "escalation, rotate the administrator's credentials, add a real-time alert on any write performed "
    "outside the application, and restrict operator access to on-demand maintenance windows. "
    "Ultimately, the incident demonstrates that the attack does not succeed on the essentials: "
    "sensitive data is not read, traces cannot be erased, and the single successful action is entirely "
    "documented.</p>")

# ===================== 17. FINAL ASSESSMENT =====================
add('<h1>17. Final Security Assessment</h1>')
add("<p>At the end of the project, the nine required security dimensions find a substantiated answer. "
    "The following table summarises them, indicating for each the means implemented.</p>")
add('<table><tr><th>Dimension</th><th>Answer and means</th></tr>'
    '<tr><td>Authentication</td><td>Argon2id, anti-brute-force lockout, locked owners</td></tr>'
    '<tr><td>Authorisation</td><td>RBAC and object-level authorisation (IDOR defence)</td></tr>'
    '<tr><td>Least privilege</td><td>svc_php with no direct right, execution through tightly scoped procedures</td></tr>'
    '<tr><td>Application security</td><td>Parameterised queries and procedure-based access (injection neutralised)</td></tr>'
    '<tr><td>Data protection</td><td>AES-256-GCM encryption at rest, blind index, separate keys</td></tr>'
    '<tr><td>Auditing and monitoring</td><td>Central append-only trail, automatic signal detection</td></tr>'
    '<tr><td>Backup and recovery</td><td>Encrypted backup, verified restoration</td></tr>'
    '<tr><td>Hardening</td><td>Socket-only, unneeded services disabled, hardened accounts</td></tr>'
    '<tr><td>Investigation</td><td>Timeline and evidence reconstructed under least privilege</td></tr></table>')
add(figcap("Answer to the nine dimensions of the final assessment."))
add("<p>Beyond the table, the overall coherence deserves to be stressed. The system applies "
    "<b>prevention</b> wherever it is possible; where it reaches its limits, "
    "<b>detection</b> and <b>response capability</b> take over. No control acts in isolation: each "
    "layer covers the blind spots of the previous one, following the defence-in-depth principle that "
    "structures all ten phases.</p>")
add("<p>Finally, this posture is not declarative but <b>proven</b>. Five suites of automated checks, "
    "runnable on an isolated disposable instance, validate the whole: one hundred and fifty-one checks "
    "for the complete installation, nineteen for backup and recovery, twenty-eight for hardening and "
    "sixteen for the investigation — two hundred and fourteen checks in all — complemented by the "
    "per-role privilege matrix, all replayable at will.</p>")

# ===================== 18. RECOMMENDATIONS =====================
add('<h1>18. Recommendations</h1>')
add("<p>Although the system meets the stated objectives, several improvements would further strengthen "
    "its posture in a real operational context. First, key management would benefit from being "
    "entrusted to a dedicated hardware module and paired with regular rotation. In the same vein, each "
    "encrypted value should be bound to its row and column through GCM associated data, so that moving "
    "a ciphertext from one record to another would be detected rather than silently accepted. Next, the detection of "
    "a write outside the application, today observable after the fact, would warrant triggering a "
    "<b>real-time alert</b>. In addition, the database administrator's access could be restricted to "
    "on-demand maintenance windows, with a separation of duties preventing a single actor from "
    "altering role assignments alone. Finally, backups should be scheduled and given a retention "
    "policy, and transport encryption would be worth enabling should network exposure become "
    "necessary.</p>")

# ===================== 19. CONCLUSION =====================
add('<h1>19. Conclusion</h1>')
add("<p>SecurePayroll demonstrates that a database can be protected in a methodical, coherent and "
    "verifiable way. By placing security at the centre from the design stage — least privilege, access "
    "exclusively through procedures, encryption of sensitive data, an append-only audit, an encrypted "
    "backup and a reduced attack surface — the system addresses all of the required dimensions. Above "
    "all, it honestly acknowledges its limits: because an administrator necessarily retains rights, the "
    "defence does not rely on prevention alone but also on a detection that no one can circumvent and "
    "on a proven investigative capability. This articulation between prevention, detection and response "
    "constitutes, in our view, the essential contribution of the project.</p>")

# ===================== 20. REFERENCES =====================
add('<h1>20. References</h1>')
add("<p>MySQL 8.4 Reference Manual (DEFINER procedures, roles, privileges, configuration). "
    "A. Biryukov et al., “Argon2”, RFC 9106. NIST SP 800-38D, “AES-GCM”. "
    "H. Krawczyk et al., “HMAC”, RFC 2104. J. Arkko et al., “IPv4 Address Blocks Reserved for "
    "Documentation”, RFC 5737. OWASP, “Top Ten” and “Cheat Sheets” (SQL injection, password "
    "storage). CIS, “MySQL Benchmark”.</p>")

# ===================== APPENDIX =====================
add('<h1>Appendix A — Detailed Entity-Relationship Diagrams</h1>')
add("<p>To complement the global diagram of Section 4, the following schemas detail each of the five "
    "database domains. They reveal the isolation of the encrypted personal-data table, the append-only "
    "audit trail and the relationships that carry referential integrity.</p>")
add(img(ERD / 'ERD-01-IDENTITE-RBAC.png', 620, "Identity and access-control domain (accounts, roles, assignments, audit)."))
add(img(ERD / 'ERD-02-ORGANISATION-RH.png', 620, "HR organisation domain (employees, encrypted personal data, contracts, assignments)."))
add(img(ERD / 'ERD-03-REMUNERATION.png', 620, "Compensation domain (proposals, decisions, salary conditions, history)."))
add(img(ERD / 'ERD-04-PAIE.png', 620, "Payroll domain (periods, variable inputs, computations, payslips and corrections)."))
add(img(ERD / 'ERD-05-REGLEMENTS.png', 620, "Settlements domain (payments, recovery requests and receipts, ledger)."))

add('<h1>Appendix B — Reproducing the Evidence</h1>')
add("<p>Every claim in this report is verifiable. The following suites run on an isolated disposable "
    "instance, without ever touching an existing database.</p>")
add('<table><tr><th>Suite</th><th>Scope</th><th>Checks</th></tr>'
    '<tr><td>tests/local-install.py</td><td>Installation, schema, roles, encryption, auditing, detection</td><td>151</td></tr>'
    '<tr><td>tests/privilege_matrix.py</td><td>Least-privilege matrix per role</td><td>—</td></tr>'
    '<tr><td>tests/backup-recovery.py</td><td>Encrypted backup and verified restoration</td><td>19</td></tr>'
    '<tr><td>tests/hardening-audit.py</td><td>Hardening, eleven areas</td><td>28</td></tr>'
    '<tr><td>tests/incident-investigation.py</td><td>Incident investigation</td><td>16</td></tr></table>')
add(figcap("Replayable evidence suites."))

# ---- RENDER ----
html = '<!DOCTYPE html><html><head><meta charset="utf-8">' + CSS + '</head><body>' + ''.join(H) + '</body></html>'
# Normalise a few typographic characters to straight ASCII (harmless; avoids OOXML quirks).
# Em-dashes (—) are kept for typography. If LibreOffice aborts with an Io/Abort error at the
# store step, it means free RAM is too low (too many image bitmaps at once): close other apps
# or lower maxw in _shrink, then rerun.
for a, b in {'“': '"', '”': '"', '‘': "'", '’': "'", '…': '...',
             ' ': ' '}.items():
    html = html.replace(a, b)
html_path = SP / 'report_en.html'
html_path.write_text(html, encoding='utf-8')
print('HTML written:', len(html), 'bytes,', _fig, 'figures')
import gc
H.clear(); html = None; gc.collect()  # release memory before LibreOffice runs (tight RAM)

profile = SP / 'enconv_profile'
conv = subprocess.run(['soffice', '--headless', f'-env:UserInstallation=file://{profile}',
                       '--convert-to', 'docx:MS Word 2007 XML', '--outdir', str(SP), str(html_path)],
                      capture_output=True, text=True)
print(conv.stdout.strip()[-200:]); print(conv.stderr.strip()[-200:] if conv.stderr else '')
produced = SP / 'report_en.docx'
if produced.exists():
    import zipfile
    z = zipfile.ZipFile(produced)
    media = [n for n in z.namelist() if 'media' in n]
    produced.replace(OUT)
    print('DOCX ->', OUT, '| embedded images:', len(media))
else:
    print('CONVERSION FAILED'); sys.exit(1)
