# Database Security Assessment Report — Sections 9 et 10 (phase 2)

> Sections du livrable 3, numérotées selon le plan imposé : **9** RBAC and Access-Control Matrix, **10** Least-Privilege Implementation.
> Annexe détaillée : `06-MATRICE-DE-CONTROLE-D-ACCES.md`. Preuves : `tests/local-install.py` (94 contrôles) et `tests/database-roles-unit.php` (23 contrôles).

---

## 9. RBAC et matrice de contrôle d'accès

### 9.1 Catégories d'utilisateurs

Le système distingue trois familles de comptes, qui n'ont ni le même mode d'accès ni les mêmes risques.

| Famille | Comptes | Accès à la base |
|---|---|---|
| **Utilisateurs de l'application** | Salarié, Responsable RH, Responsable Finance, Gestionnaire de paie, Administrateur applicatif, Auditeur de sécurité | Jamais directement : par l'application, avec les seuls droits MySQL de leur rôle |
| **Comptes techniques** | `svc_php` (service de l'application) ; 5 comptes propriétaires des procédures (`*_owner`, **verrouillés**) | Le service se connecte par socket local ; les propriétaires ne peuvent pas se connecter |
| **Comptes d'exploitation** | `dba_ops` (DBA), `backup_ops` (sauvegarde), `audit_ops` (auditeur SQL), `root` (installation et gestion des droits) | Client `mysql` par socket local, sans accès réseau |

### 9.2 Modèle RBAC de l'application

Le RBAC est stocké dans la base et suit le modèle classique **utilisateur → rôle → permission** :
- 6 rôles (`roles`) et 31 permissions (`permissions`), associés par `role_permissions` ;
- les attributions (`role_assignments`) sont **datées** : début, expiration facultative, révocation avec auteur et motif. Des triggers interdisent la suppression d'une attribution et toute modification autre que sa révocation, qui n'est possible qu'une fois.

L'autorisation est vérifiée à **chaque requête**. `AuthService::currentUser` relit le compte et ses attributions encore valides, ce qui rend une révocation effective immédiatement. `AuthService::can` exige alors **à la fois** le rôle attendu et la permission enregistrée : une permission ajoutée par erreur à un autre rôle ne suffit pas.

La **gestion des droits** est elle-même contrôlée : elle passe par les procédures `iam_grant` et `iam_revoke`.

| Règle | Mécanisme | Code d'erreur |
|---|---|---|
| Seul l'administrateur applicatif attribue ou révoque | Contrôle de l'acteur dans la procédure | `IAM_FORBIDDEN` |
| Personne ne s'attribue un rôle à soi-même | Comparaison de l'acteur et du bénéficiaire, au niveau de la personne | `IAM_FORBIDDEN` |
| Pas de cumul de rôles incompatibles | Recherche des rôles actifs sur tous les comptes de la personne | `IAM_CONFLICT` |
| Toute attribution et toute révocation sont motivées et historisées | Motif obligatoire ; ajout seul | Triggers |

### 9.3 Séparation des tâches

| Règle | Où elle est appliquée |
|---|---|
| Un salarié ne cumule pas deux rôles parmi RH, Finance, Paie, Administrateur et Auditeur | `AuthService` (indicateur `payroll_conflict`) et `iam_grant` |
| Personne ne décide de sa propre rémunération | `compensation_decide` (`COMP_SELF_APPROVAL`) |
| Le préparateur d'un bulletin ne l'approuve pas ; Finance approuve, Paie publie | `payroll_calculate`, `payslip_transition` (`PAY_FORBIDDEN`) |
| Une proposition salariale RH ne devient un salaire qu'après une décision Finance | Tables séparées : demande, décision, condition (section 5.5) |

Ces règles sont vérifiées **dans la base**, par les procédures stockées. Elles s'appliquent même si le contrôle PHP était contourné.

### 9.4 Matrice de contrôle d'accès

● = autorisé. Chaque permission de l'application correspond à des privilèges MySQL précis du rôle équivalent (§ 9.5).

| Fonction | Salarié | RH | Finance | Paie | Admin | Auditeur |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Consulter ses propres bulletins publiés et leur règlement | ● | | | | | |
| Gérer l'identité des salariés, les contrats, les affectations | | ● | | | | |
| Proposer une rémunération | | ● | | | | |
| Décider d'une rémunération | | | ● | | | |
| Consulter les rémunérations | | ● | ● | | | |
| Saisir les primes, retenues et absences | | ● | | | | |
| Créer une période de paie ; accepter les éléments variables | | | ● | | | |
| Calculer, vérifier et publier les bulletins ; corriger | | | | ● | | |
| Approuver ou rejeter un bulletin | | | ● | | | |
| Consulter toute la paie | | ● | ● | ● | | ● |
| Payer ; décider d'une restitution | | | ● | | | |
| Demander et encaisser une restitution | | | | ● | | |
| Consulter les rôles et leur historique | | | | | ● | ● |
| Attribuer ou révoquer un rôle (à autrui) | | | | | ● | |
| Lire ou modifier les données personnelles (CIN, CNSS, RIB) | — | — | — | — | — | — |

La dernière ligne est volontairement vide. Aucune fonction de l'application n'accède encore aux données personnelles, protégées par l'absence de tout privilège (section 6). Leur accès contrôlé, avec double validation des modifications du RIB, est prévu en réponse à la menace T-08.

**Comptes d'exploitation** (hors application) :

| Fonction | `dba_ops` | `backup_ops` | `audit_ops` | `root` |
|---|:-:|:-:|:-:|:-:|
| Modifier le schéma (tables, index, procédures, triggers) | ● | | | ● |
| Exporter toute la base | | ● | | ● |
| Lire les historiques et les attributions, sans montant ni donnée personnelle | ● | ● | ● | ● |
| Lire les montants, les empreintes et les données personnelles | ● | ● | | ● |
| Créer des comptes ; attribuer ou retirer des droits | | | | ● |

Le DBA et l'opérateur de sauvegarde peuvent techniquement lire les données Restreint : la maintenance et l'export l'exigent. Ce risque interne est accepté et traité par la journalisation (section 14) et le chiffrement des sauvegardes (section 15).

### 9.5 Traduction en rôles MySQL

Chaque rôle de l'application a un **rôle MySQL** équivalent, auquel s'ajoutent deux rôles techniques :

| Rôle MySQL | Privilèges |
|---|---|
| `sp_session` | Lecture de l'identité et des attributions, nécessaire à chaque requête. **Ni** empreinte de mot de passe, **ni** login. |
| `sp_login` | Lecture de l'empreinte du mot de passe, pendant la seule requête de connexion |
| `sp_employee` | Exécution des 3 procédures de consultation (filtrées par l'acteur) |
| `sp_hr_manager` | Écriture limitée sur `employees` (3 colonnes) ; lecture des contrats, affectations, référentiels et rémunérations ; 6 procédures RH, plus les 3 de consultation |
| `sp_finance_manager` | Lecture des contrats et des rémunérations ; 5 procédures Finance, plus les 3 de consultation |
| `sp_payroll_manager` | 3 procédures Paie, plus les 3 de consultation |
| `sp_application_administrator` | `iam_overview`, `iam_grant`, `iam_revoke` |
| `sp_security_auditor` | `iam_overview`, plus les 3 de consultation |

Six tables ne sont lisibles directement par **aucun** rôle de l'application : `employee_personal_data`, `payroll_inputs`, `payroll_calculations`, `payslip_corrections`, `recovery_requests` et `settlement_ledger`. Leurs données ne circulent qu'au travers des procédures, qui vérifient l'acteur.

**Vérification.** La matrice attendue est écrite **indépendamment** du script SQL, dans `tests/privilege_matrix.py`. La recette active chaque rôle, puis :
- appelle chacune des 18 procédures de l'application : une procédure autorisée s'exécute et refuse l'acteur fictif (1644), une procédure interdite est bloquée par MySQL (1370) ;
- lit chacune des 14 tables : les tables autorisées sont lisibles, les autres refusées (1142) ;
- vérifie qu'aucune ligne de la base n'a changé.

Le résultat, conforme pour les 6 rôles, est le suivant :

| Rôle | Procédures exécutables | Tables lisibles (sur 14 testées) |
|---|---:|---:|
| Salarié | 3 / 18 | 0 |
| RH | 9 / 18 | 8 |
| Finance | 8 / 18 | 5 |
| Paie | 6 / 18 | 0 |
| Administrateur | 3 / 18 | 0 |
| Auditeur | 4 / 18 | 0 |

---

## 10. Mise en œuvre du moindre privilège

### 10.1 Situation initiale

À l'issue de la phase 1, l'application utilisait **un seul compte MySQL**, `svc_php`. Il recevait **34 instructions `GRANT` directes** : l'union de tout ce dont les six rôles avaient besoin. Le contrôle d'accès reposait donc entièrement sur le code PHP.

Conséquence : une erreur ou une injection SQL dans une page ouverte au simple salarié s'exécutait avec le droit de lire tous les salaires (`salary_conditions`, `compensation_requests`) et toutes les empreintes de mots de passe. C'était l'écart **E1** (section 6.4).

### 10.2 Principe retenu

Le moindre privilège est appliqué à **trois niveaux** successifs. Chacun reste efficace si le précédent est contourné.

```text
 1. Compte de service      svc_php : aucun privilège direct ; rôles MySQL activés par requête
        │                  selon l'utilisateur authentifié (SET ROLE)
        ▼
 2. Procédures DEFINER     les données sensibles ne sont accessibles que par procédure ; celle-ci
        │                  s'exécute avec les droits d'un compte propriétaire verrouillé
        ▼
 3. Contrôle de l'acteur   chaque procédure vérifie le rôle, les incompatibilités et la propriété
                           de la donnée pour l'utilisateur transmis (p_actor)
```

Deux options ont été comparées pour le premier niveau :

| Option | Avantage | Inconvénient | Retenue |
|---|---|---|---|
| Un compte MySQL par rôle métier (6 comptes) | Isolation visible dans la liste des comptes | 6 mots de passe dans le même fichier de configuration : la protection contre le vol de ce fichier est identique | Non |
| **Un compte, plusieurs rôles activés par requête** | Un seul secret ; démontre `CREATE ROLE`, `SET DEFAULT ROLE`, `SET ROLE` | Le compte détient tous les rôles, donc un vol du secret les donne tous | **Oui** |

### 10.3 Implémentation

**Création des rôles et attribution des privilèges** (`database/setup/app_roles.sql`). Les privilèges sont accordés au niveau le plus fin possible : colonne, table ou procédure, jamais `*.*`.

```sql
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'svc_php'@'localhost';      -- retrait de tous les privilèges directs
CREATE ROLE 'sp_session', 'sp_login', 'sp_employee', 'sp_hr_manager', ...;
GRANT SELECT (id, employee_id, disabled_at) ON secure_payroll.accounts TO 'sp_session';
GRANT SELECT (id, employee_id, login, password_hash, disabled_at) ON secure_payroll.accounts TO 'sp_login';
GRANT EXECUTE ON PROCEDURE secure_payroll.payslip_detail TO 'sp_employee';
GRANT 'sp_session', 'sp_login', 'sp_employee', ... TO 'svc_php'@'localhost';
SET DEFAULT ROLE 'sp_session' TO 'svc_php'@'localhost';
```

**Activation par requête** (`app/Database/SessionRoles.php`) :

| Moment | Rôles actifs | Effet |
|---|---|---|
| Connexion MySQL de la requête | `sp_session` (rôle par défaut) | Relecture du compte et de ses rôles applicatifs |
| Requête de connexion (`POST /login`) | `sp_login` seul, puis retour au rôle par défaut | Seul moment où l'empreinte du mot de passe est lisible |
| Après authentification | `sp_session` + les rôles de l'utilisateur | Les requêtes de la page n'ont que les droits de cet utilisateur |
| Cumul de rôles interdit | `sp_session` + `sp_employee` au plus | Les droits financiers ne sont jamais activés |

Les noms de rôles passés à `SET ROLE` proviennent d'une **liste fermée** dans le code. Ils ne sont jamais construits depuis une donnée reçue, car `SET ROLE` n'accepte pas de paramètre lié.

**Garde-fous de l'installation** (`bin/init-local.py`). L'installation refuse de se terminer :
- si `activate_all_roles_on_login` est actif ou si `mandatory_roles` n'est pas vide, car tous les rôles seraient alors actifs d'office ;
- si `svc_php` conserve le moindre privilège direct (contrôle de `mysql.db`, `tables_priv`, `columns_priv` et `procs_priv`) ;
- si l'un des 11 rôles est absent.

**Comptes d'exploitation** (`database/setup/operator_roles.sql`). Un compte et un rôle par tâche ; `root` est réservé à l'installation et à la gestion des comptes et des droits.

| Compte | Rôle | Moindre privilège appliqué |
|---|---|---|
| `dba_ops` | `sp_dba` | Tous les droits sur le **seul** schéma `secure_payroll` ; aucun privilège global, pas de `GRANT OPTION`. Il ne peut donc ni créer de compte ni distribuer de droits. |
| `backup_ops` | `sp_backup` | Exactement les droits de `mysqldump` (`SELECT`, `SHOW VIEW`, `TRIGGER`, `EVENT`, `LOCK TABLES`, `SHOW_ROUTINE`) ; aucune écriture |
| `audit_ops` | `sp_db_auditor` | Historiques et attributions **par colonne** : registre sans `amount`, comptes sans `password_hash` ; aucune donnée personnelle |

Les comptes humains (`dba_ops`, `audit_ops`) sont verrouillés pendant un jour après 5 échecs de connexion, et leur mot de passe expire après 90 jours. Les comptes techniques n'ont pas de verrouillage : sinon, quelques faux mots de passe saisis par un tiers suffiraient à bloquer la sauvegarde ou toute l'application.

### 10.4 Preuves

**Avant / après, droits déclarés de `svc_php`** (`SHOW GRANTS FOR 'svc_php'@'localhost'`) :

```text
Avant :  GRANT USAGE ON *.* ...
         34 instructions GRANT directes : SELECT sur salary_conditions, compensation_requests,
         accounts(password_hash), EXECUTE sur les 18 procédures, ...
Après :  GRANT USAGE ON *.* TO `svc_php`@`localhost`
         GRANT `sp_application_administrator`@`%`,`sp_employee`@`%`,...,`sp_session`@`%` TO `svc_php`@`localhost`
```

**Droits effectifs d'une session Salarié** (`SHOW GRANTS FOR 'svc_php'@'localhost' USING 'sp_session','sp_employee'`) : lecture de l'identité et des attributions, et exécution de `payroll_overview`, `payslip_detail` et `settlement_detail`. Aucune mention de `salary_conditions` ni de `password_hash`.

**Contrôles de la recette** (extrait des 94) :

| Test | Résultat attendu et obtenu |
|---|---|
| Session ordinaire : `SELECT password_hash FROM accounts` | Refusé (1143) |
| Rôle Salarié : `SELECT monthly_amount FROM salary_conditions` | Refusé (1142) |
| Rôle Salarié : `CALL compensation_decide(...)` | Refusé (1370) |
| Rôle RH : `SELECT COUNT(*) FROM salary_conditions` | Autorisé |
| `SET ROLE 'sp_dba'` par `svc_php` (rôle non accordé) | Refusé (3530) |
| DBA : `CREATE USER` / `GRANT` | Refusés (1227 / 1142) |
| Auditeur SQL : `settlement_ledger.amount`, `employee_personal_data`, `password_hash` | Refusés (1143 / 1142 / 1143) |
| `REVOKE 'sp_db_auditor' FROM 'audit_ops'@'localhost'`, puis nouvelle connexion | Schéma inaccessible (1044) ; accès rétabli après un nouveau `GRANT` |
| Sauvegarde complète par `backup_ops` | Réussie (tables et procédures exportées) |
| Matrice 6 rôles × 18 procédures × 14 tables | Conforme ; aucune donnée modifiée |
| Parcours HTTP des 6 rôles (connexion, pages, calcul, approbation, publication, paiement) | Inchangés : aucune régression fonctionnelle |

### 10.5 Apport pour la phase d'attaque (sections 11 et 12)

Les phases 4 et 5 exigent un composant **délibérément vulnérable**, puis la preuve qu'une même attaque réussit avant la correction et échoue après. Le moindre privilège y joue le rôle de **deuxième ligne de défense**, distincte des requêtes préparées :
- **requêtes préparées** : elles empêchent l'injection elle-même ;
- **rôles MySQL** : si une injection subsistait dans une page ouverte au salarié, elle s'exécuterait sans aucun droit sur les salaires ni sur les empreintes. MySQL la refuserait (1142 ou 1143), et une injection ne peut pas activer un autre rôle, car `SET ROLE` est une instruction distincte.

La démonstration prévue mesurera donc séparément l'effet de chaque défense : la même charge contre le composant vulnérable avec les privilèges de la phase 1, puis avec les rôles, puis avec les requêtes préparées.

### 10.6 Limites résiduelles

| Limite | Conséquence | Traitement |
|---|---|---|
| `svc_php` détient tous les rôles | Le **vol de son mot de passe** les donne tous : la menace T-10 n'est pas réduite par cette mesure | Protection du secret (section 16) |
| MySQL ne peut pas vérifier que l'acteur et les rôles activés correspondent à l'utilisateur web réel | Le code PHP reste dans la base de confiance | Inhérent à un compte de service partagé ; troisième niveau de contrôle dans les procédures |
| Les droits MySQL ne filtrent pas les lignes | Toute session lit en base les noms et matricules de tous les salariés (Confidentiel), sans montant ni identifiant officiel | Accepté ; une procédure de lecture dédiée est possible |
| Le DBA lit et modifie les données du schéma | Risque interne (T-14) | Journalisation hors de son contrôle (section 14) |
| RH et Finance lisent directement les rémunérations | Nécessaire à leurs fonctions | Journalisation des lectures (écart E4, section 14) |
