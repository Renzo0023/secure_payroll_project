# 15 — Investigation d'un incident de sécurité (phase 10)

Alimente la **section « Security Incident Investigation » du rapport**. L'énoncé fournit un scénario-type :
*« Plusieurs tentatives d'accès non autorisées à des données sensibles. Un compte privilégié a aussi
effectué des opérations inhabituelles. »* L'équipe de sécurité doit déterminer ce qui s'est passé,
établir une **chronologie**, et répondre — là où les preuves le permettent — à sept questions.

L'investigation est **rejouable** : `python3 tests/incident-investigation.py` (**16 contrôles**, instance
jetable isolée). Le script **joue l'incident avec les mécanismes réels du système** (donc des preuves
authentiques), puis mène l'enquête à partir des seules traces.

## 1. Sources de preuves et accès à moindre privilège

L'énoncé cite cinq sources (journaux de base, enregistrements d'authentification, journaux d'audit
applicatifs, enregistrements de base, activité des utilisateurs). Chacune est consultée par le **rôle
approprié**, sans sur-privilège :

| Source | Accès dans l'enquête | Rôle utilisé |
|---|---|---|
| **Journal d'audit applicatif** (`security_audit_log`) | `audit_suspicious()` (signaux) + `audit_recent()` (chronologie) | `sp_security_auditor` (jamais d'accès direct à la table) |
| **Enregistrements de base / activité utilisateur** | lecture directe des tables métier (`role_assignments`, comptes, historiques) | `sp_db_auditor` (investigateur, **aucune donnée Restreinte**) |
| **Enregistrements d'authentification** | événements `auth.*` dans la piste (compte visé + IP, jamais le mot de passe saisi) | `sp_security_auditor` |

L'investigateur `sp_db_auditor` **n'a aucun accès** aux données Restreintes : une tentative de lecture de
`employee_personal_data` (chiffré) est refusée (1142). On enquête sans jamais exposer les données
protégées — contrôle vérifié par le script.

## 2. Chronologie reconstituée

Reconstruite à partir de `occurred_at` (piste d'audit), l'horodatage étant en UTC :

| Instant (UTC) | Événement | Résultat | Acteur | Ressource |
|---|---|---|---|---|
| T0 (×6, en rafale) | `auth.failed` | échec | non authentifié, IP `203.0.113.66` | compte `hr.demo` (Camille RH) |
| T1 (×3) | `employees.access_denied` | **refusé** | compte salarié #4 (`employee.demo`) | fiches `employees#1,2,3` |
| T1 (×1) | `audit.access_denied` | **refusé** | compte salarié #4 | `security_audit_log` (supervision) |
| T2 | `role.granted` (source **trigger**) | succès | **`dba_ops@localhost` — hors application** | `role_assignments` (compte #4 ← rôle *application_administrator*) |
| T3 (×2) | effacement de la piste tenté | **refusé (1644)** | `dba_ops` | `security_audit_log` |

`203.0.113.66` est une adresse de **documentation** (RFC 5737), jamais une IP réelle.

## 3. Les sept questions

- **Que s'est-il passé ?** Une attaque en trois temps : (1) **force brute** sur un compte RH ; (2) après
  avoir pris pied comme salarié, des **tentatives d'accès non autorisées** (IDOR sur des fiches
  d'employés, accès à la supervision) — toutes **refusées** ; (3) une **escalade de privilèges** réalisée
  non pas par l'application, mais par un **compte privilégié (`dba_ops`) agissant directement sur la
  base**, qui s'octroie le rôle d'administrateur ; puis une **tentative d'effacement des traces**, échouée.
- **Quand ?** Séquence continue (voir chronologie), horodatée à la microseconde en UTC dans la piste.
- **Quels comptes ?** Le compte visé par la force brute (`hr.demo`) ; le compte salarié compromis
  (`employee.demo`, #4) ; et surtout le compte d'exploitation **`dba_ops`** (identité MySQL réelle
  établie par `SESSION_USER()`, indépendamment de tout rôle applicatif).
- **Quelles ressources ?** Les fiches `employees` (accès **tentés**, non aboutis), la table de
  supervision (accès **refusé**), et `role_assignments` (**réellement modifiée** : octroi du rôle admin).
- **Quels contrôles ont failli / tenu ?**
  - **Tenu** — *autorisation par objet* : toutes les tentatives IDOR et l'accès à la supervision ont été
    **refusés** (`outcome='denied'`).
  - **Tenu** — *piste d'audit inviolable* : l'effacement des traces par `dba_ops` a **échoué** (1644) ;
    l'attaquant n'a pas pu se cacher.
  - **Par conception (détection, pas prévention)** — l'opération directe du DBA **n'est pas empêchée** :
    `sp_dba` détient `ALL PRIVILEGES` (risque **T-14 explicitement accepté**, voir
    `database/setup/operator_roles.sql`). Le contrôle qui s'applique est la **détection** : le
    déclencheur DEFINER a tracé l'écriture avec `source='trigger'`, `db_user='dba_ops'` et **acteur
    applicatif nul** — signature non équivoque d'une action **hors application** par un compte privilégié.
- **Quelles preuves ?** Les lignes de `security_audit_log` (rafale `auth.failed` même IP ; trois
  `*.access_denied` par le compte #4 ; la ligne `role.granted` attribuée à `dba_ops`), corroborées par la
  ligne correspondante dans `role_assignments`. Les signaux `audit_suspicious()` (« rafale d'échecs » et
  « refus répétés ») matérialisent la détection automatique.
- **Quelles actions correctives ?** Voir §4.

## 4. Actions correctives recommandées

1. **Révoquer l'escalade** et auditer l'ensemble des attributions de rôle récentes ; réinitialiser le
   compte salarié compromis (`employee.demo`).
2. **Rotation immédiate** des identifiants de `dba_ops` ; vérifier pourquoi ce compte a agi hors
   application.
3. **Alerte temps réel** sur la signature « `source='trigger'` **et** acteur applicatif nul » : toute
   écriture sur une table sensible hors de l'application doit déclencher une notification (aujourd'hui
   détectable *a posteriori* ; à passer en alerte active).
4. **Durcir l'accès opérateur** : réserver `sp_dba` aux fenêtres de maintenance (activation à la demande),
   journaliser les sessions `dba_ops`, envisager une séparation des tâches (le DBA ne doit pas pouvoir
   modifier seul les attributions de rôle).
5. **Blocage anti-force-brute** : confirmer le verrouillage de compte après seuil (déjà `auth.throttled`
   côté application) et surveiller les rafales inter-comptes (pulvérisation).

## 5. Ce que l'incident démontre du système

L'incident n'aurait **pas abouti** sur l'essentiel : les données sensibles n'ont pas été lues (accès
refusés), les traces n'ont pas pu être effacées (ajout seul), et l'unique action réussie — l'abus d'un
compte privilégié, risque assumé — a été **intégralement tracée et attribuable**. C'est exactement ce que
les phases 6 à 9 visaient : quand la prévention ne peut pas tout (un DBA garde des droits), la
**détection inviolable** prend le relais et rend l'enquête possible.

## 6. Preuves et reproduction

| Preuve | Où |
|---|---|
| Investigation rejouable (16 contrôles : mise en scène + reconstruction) | `tests/incident-investigation.py` |
| Piste d'audit et procédures de supervision | migrations 016/017, `docs/security-assessment/12-JOURNALISATION-ET-AUDIT.md` |
| Modèle de menace de l'accès opérateur (risque T-14) | `database/setup/operator_roles.sql` |

Commande : `python3 tests/incident-investigation.py`.
