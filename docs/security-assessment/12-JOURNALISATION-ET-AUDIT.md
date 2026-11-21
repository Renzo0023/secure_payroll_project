# 12 — Journalisation et supervision de sécurité (phase 7)

Alimente la **section « Auditing and Monitoring » du rapport**. L'énoncé impose d'enregistrer les
activités sensibles et de répondre, pour chacune, aux cinq questions : **QUI**, **QUOI**, **QUAND**,
**QUELLE RESSOURCE**, **SUCCÈS ou ÉCHEC** ; puis de montrer comment ces traces permettent de détecter
et d'investiguer une activité suspecte.

Avant la phase 7, l'application tenait déjà un journal fichier (`auditEvent` → `application.log`). La
phase 7 ajoute une **piste d'audit EN BASE, centrale, inviolable et interrogeable**, et une **couche de
supervision**. Le journal fichier est conservé en parallèle (défense en profondeur).

## 1. Les contrôles et pourquoi ils fonctionnent

| Contrôle | Réalisation | Pourquoi il répond à l'énoncé |
|---|---|---|
| **Piste d'audit centrale en base** | Table `security_audit_log` (migration 016) : `occurred_at` (QUAND), `event` (QUOI), `actor_account_id` + `db_user` (QUI), `target_table`/`target_id` (QUELLE RESSOURCE), `outcome` ∈ {success, failure, denied} (RÉSULTAT), `source` ∈ {application, trigger}, `context` JSON. | Une seule source de vérité, **requêtable en SQL** — contrairement à un fichier plat — pour la détection et l'investigation. Chaque colonne répond à une des cinq questions. |
| **Ajout seul (inviolable)** | Des triggers `BEFORE UPDATE/DELETE` refusent toute modification ou suppression d'une trace, **pour tout le monde, y compris root** (migration 017). L'application n'a que l'EXECUTE de la procédure d'écriture. | Une piste d'audit altérable ne vaut rien. Ici, un attaquant — même avec un accès privilégié — ne peut pas effacer ses traces ; la tentative échoue et peut elle-même être constatée. |
| **Deux sources complémentaires** | `source='application'` : le code appelle `audit_record` (`App\Audit\AuditTrail`) pour connexions, lectures sensibles, refus, actions. `source='trigger'` : des déclencheurs DEFINER sur `employee_personal_data`, `role_assignments`, `salary_conditions` enregistrent **toute écriture, même hors application**. | L'application trace l'intention métier ; les triggers garantissent qu'**aucune écriture sur une table sensible n'échappe à l'audit**, même par un compte d'exploitation (`dba_ops`) qui contournerait l'application. |
| **Qui, de façon fiable** | L'acteur applicatif est posé dans `@audit_actor` à chaque requête authentifiée ; les triggers le lisent. `SESSION_USER()` donne **toujours** l'identité MySQL réelle (jamais le DEFINER), y compris pour une écriture directe. | On sait qui a agi au sens métier (compte applicatif) **et** au sens SGBD (compte MySQL), ce qui distingue une action via l'application d'un accès direct à la base. |
| **Moindre privilège sur l'audit lui-même** | Le rôle applicatif n'a **que** l'EXECUTE d'`audit_record` (écriture, jamais lecture ni modification de la table). L'auditeur lit **uniquement** par `audit_recent`/`audit_suspicious`. Le propriétaire `audit_owner` (7ᵉ compte verrouillé) porte le DML. | L'application ne peut pas relire ni trafiquer la piste ; l'auditeur ne peut pas écrire ; personne n'a d'accès direct à la table. Les rôles de l'audit suivent le même moindre privilège que le reste du système. |

## 2. Couverture des activités exigées

| Activité (énoncé) | Événement(s) | Source |
|---|---|---|
| Connexion réussie | `auth.login` | application |
| Connexion échouée | `auth.failed` (compte visé + IP, **jamais l'identifiant saisi**) | application |
| Blocage anti-rafale | `auth.throttled` | application |
| Déconnexion | `auth.logout` | application |
| Changement de mot de passe | `auth.password_changed` / `auth.password_change_failed` | application |
| **Accès aux données sensibles** | `personal_data.viewed`, `payslip.viewed`, `salary.viewed` | application |
| Modification d'enregistrement | `personal_data.modified`, `role.changed`, `personal_data.rib_updated` | trigger + application |
| Suppression d'enregistrement | refusée par conception (triggers phase 1) ; toute tentative est tracée | trigger |
| Action d'administration | `role.granted` / `role.changed` (attribution/révocation de rôle), `account.onboarded` | trigger + application |
| Refus d'accès | tout `*.access_denied` / `access.denied` → `outcome='denied'` | application |

## 3. Détection et investigation

La procédure `audit_suspicious()` (réservée à l'auditeur) matérialise trois signaux sur 24 h :

- **Rafale d'échecs de connexion** — `auth.failed` groupés par compte visé et IP, seuil ≥ 5. Détecte une attaque par force brute ou par pulvérisation.
- **Refus d'accès répétés** — `outcome='denied'` groupés par acteur, seuil ≥ 3. Détecte une tentative d'élévation ou d'exploration.
- **Lectures sensibles massives** — `*.viewed` groupés par acteur, seuil ≥ 10. Détecte une exfiltration par un compte légitime.

La page **« Audit de sécurité »** (`/audit`, rôle auditeur seul) affiche ces signaux et les événements
récents. Chaque ligne se **déplie** pour révéler le détail forensique complet : l'acteur applicatif
(compte + nom) **et** le compte MySQL réel (`SESSION_USER()`), le **compte ou la ressource visé résolu
en libellé** — par exemple une connexion échouée montre le compte employé ciblé et non un simple
`accounts#id` —, l'**IP source** extraite du contexte, et l'ensemble des champs du contexte JSON. C'est
la démonstration directe de « comment les traces permettent de détecter et d'investiguer ». La procédure
`audit_recent` résout acteur et cible côté DEFINER (l'auditeur n'a toujours aucun accès direct aux tables
`accounts`/`employees`). Pour une investigation ciblée, la piste se filtre aussi en SQL : par acteur
(`actor_account_id`), par ressource (`target_table`/`target_id`), par fenêtre de temps.

## 4. Confidentialité de la piste

La piste d'audit ne contient **jamais** de secret ni de donnée protégée : pas de mot de passe, pas
d'identifiant de connexion saisi (un mot de passe tapé par erreur dans le champ login n'y figure donc
jamais), pas de RIB/CIN/CNSS en clair. Les déclencheurs sur les données personnelles n'enregistrent que
des **indicateurs de changement** (`rib_change`, `contact_change`), jamais la valeur. Seules des
références (identifiants, tables) et des métadonnées voyagent dans `context`.

## 5. Données en base vs fichier

Les deux coexistent volontairement : la **base** porte la piste inviolable, requêtable, partagée ; le
**fichier** (`application.log`, répertoire privé 0700) survit à une indisponibilité de la base et sert
de recours. L'écriture en base est « best-effort » : une panne d'audit ne casse jamais la requête
applicative, mais laisse la trace fichier et un marqueur `audit.persist_failed`.

## 6. Preuves

| Preuve | Où |
|---|---|
| Recette d'installation (151 contrôles) : table présente ; déclencheurs peuplant la piste dès la semence (rôles, salaires, données personnelles) ; **ajout seul** (UPDATE/DELETE refusés même en root, 1644) ; écriture applicative via `audit_record` ; **aucune lecture directe** de la table par le service ni l'auditeur (1142) ; capture des événements applicatifs (connexion, lecture, saisie) ; modification du RIB **attribuée à l'acteur** via `@audit_actor` ; **détection** de la rafale d'échecs ; page `/audit` accessible à l'auditeur (200) et refusée au salarié (403) | `tests/local-install.py` |
| Matrice de privilèges : `security_audit_log` interdite en lecture directe à tous les rôles | `tests/privilege_matrix.py` |

Commande : `python3 tests/local-install.py`.

## 7. Articulation avec les autres phases

La piste d'audit est le socle de la **phase 10 (investigation d'incident)** : l'enquête s'appuiera sur
`security_audit_log`, les journaux d'authentification et les tables métier pour reconstruire une
chronologie. La phase 9 (durcissement) passera en revue la configuration de journalisation du SGBD
lui-même (general/slow/error log), complémentaire de cet audit applicatif et métier.
