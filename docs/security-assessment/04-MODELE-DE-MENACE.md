# Phase 1 — Modèle de menace de base

> Livrable de la phase 1 (« Potential threat actors », « Major attack surfaces », « Basic threat model »).
> S'appuie sur [01-INVENTAIRE-DES-ACTIFS.md](01-INVENTAIRE-DES-ACTIFS.md), [02-CLASSIFICATION-DES-DONNEES.md](02-CLASSIFICATION-DES-DONNEES.md) et [03-ANALYSE-CIA.md](03-ANALYSE-CIA.md).
> Les contrôles cités existent dans le code, à l'emplacement indiqué. Lorsqu'un risque est seulement **déduit du code** et n'a pas été exercé, c'est précisé.

## 1. Méthode

1. Modéliser le système, ses flux et ses **frontières de confiance** (§ 2).
2. Recenser les **surfaces d'attaque** (§ 3).
3. Décrire les **acteurs de menace** (§ 4).
4. Identifier les menaces selon **STRIDE** :
   - *Spoofing* (usurpation)
   - *Tampering* (altération)
   - *Repudiation* (répudiation)
   - *Information disclosure* (divulgation)
   - *Denial of service* (déni de service)
   - *Elevation of privilege* (élévation de privilèges)
5. Évaluer le **risque résiduel**, compte tenu des contrôles existants : vraisemblance × impact (§ 5).
6. Affecter chaque risque à un traitement et à une phase du projet (§ 6).

**Échelles**

| Note | Vraisemblance (V), contrôles existants pris en compte | Impact (I) |
|---|---|---|
| 1 | Exige un accès déjà privilégié ou une compromission préalable de la machine, **ou** un contrôle testé bloque l'attaque | Donnée Interne ; gêne mineure |
| 2 | Possible pour un acteur interne avec ses droits légitimes, ou contrôle seulement partiel | Donnée Confidentiel ; interruption de quelques heures |
| 3 | Triviale, sans prérequis particulier | Donnée Restreint ; fraude financière ; paie bloquée ; prise de contrôle |

**Risque = V × I** : 1–2 **Faible**, 3–4 **Moyen**, 6–9 **Élevé**.

Un impact de 3 donne au minimum un risque Moyen, même si l'attaque est bien bloquée. C'est voulu : une menace sur des données Restreint reste à surveiller.

## 2. Modèle du système et frontières de confiance

```text
  Navigateur de l'utilisateur
        │  HTTP 127.0.0.1:8080 — cookie de session, jeton CSRF
════════╪═════════════════════════════════════════ FC-1  utilisateur ↔ application
        ▼
  Serveur PHP (public/index.php → app/Web/*Controller.php)
   ├─ authentification Argon2id, session, RBAC (AuthService::can)
   ├─ journal applicatif ──────────► .local/runtime/application.log
   └─ PDO, compte partagé svc_php, acteur transmis en paramètre (p_actor)
        │  socket Unix .local/mysql.sock — aucun port réseau
════════╪═════════════════════════════════════════ FC-2  application ↔ base
        ▼
  MySQL 8.4 (secure_payroll)
   ├─ SELECT directs autorisés à svc_php (RH, rémunération, comptes)
   ├─ 24 procédures SQL SECURITY DEFINER (comptes *_owner verrouillés)
   └─ 44 triggers d'immutabilité et de validation
        │
════════╪═════════════════════════════════════════ FC-3  base ↔ système de fichiers
        ▼
  .local/data (InnoDB en clair) · .local/*.json (secrets) · sauvegardes mysqldump
        ▲
════════╪═════════════════════════════════════════ FC-4  exploitant ↔ instance
  Compte Linux de l'exploitant : root MySQL, bin/*.py, bin/backup.py
        ▲
════════╪═════════════════════════════════════════ FC-5  dépôt ↔ installation
  Dépôt Git privé : migrations, procédures et GRANT installés par bin/init-local.py
```

| Frontière | Ce qui la franchit | Ce qui la protège |
|---|---|---|
| **FC-1** utilisateur ↔ application | Identifiants, formulaires, identifiants d'objets dans les URL | Authentification, session, CSRF, RBAC, validation serveur, échappement HTML, CSP |
| **FC-2** application ↔ base | Requêtes SQL, appels de procédures avec `p_actor` | Requêtes préparées ; droits limités de `svc_php` ; assertions dans les procédures. **Limite** : MySQL ne vérifie pas que `p_actor` correspond à l'utilisateur web réel (`07-SECURITE-RBAC-IAM.md`, « Frontière de confiance »). |
| **FC-3** base ↔ système de fichiers | Pages InnoDB, exports, journaux | Uniquement les permissions Unix (0700 / 0600) ; aucun chiffrement |
| **FC-4** exploitant ↔ instance | Commandes d'administration | Mot de passe `root` dans `.local/admin.json` ; aucune séparation entre l'exploitant et le compte Linux |
| **FC-5** dépôt ↔ installation | Code SQL exécuté en `root` à l'installation | Dépôt privé, audit de secrets ; **aucune revue de code obligatoire** |

## 3. Surfaces d'attaque

| ID | Surface | Exposition | Actifs visés | Source |
|---|---|---|---|---|
| SA-1 | Formulaire `POST /login` | Toute personne qui atteint le port 8080 | D-05 | `Controller.php`, `AuthService.php`, `LoginLimiter.php` |
| SA-2 | Routes authentifiées avec identifiant d'objet (`/employees/{id}`, `/payslips/{id}`, `/compensation/{id}`, `/contracts/{id}`, `/payslips/{id}/settlement`…) | Tout utilisateur connecté | D-02, D-03, D-04, D-07 | `14-INVENTAIRE-DES-ROUTES.md` (47 lignes) |
| SA-3 | Formulaires métier POST : employés, contrats, rémunérations, transitions de paie, règlements, IAM | Utilisateurs connectés selon leur rôle | D-02 à D-07 | `app/Web/*Controller.php` |
| SA-4 | Champs libres (`reason`, `justification`), réaffichés à d'autres rôles | Utilisateurs connectés | Sessions des autres utilisateurs | Vues `app/Views/*.php` |
| SA-5 | Cookie et fichiers de session | Navigateur, `.local/runtime/` | K-04 | `Session.php` |
| SA-6 | Paramètre `return_to` du changement de langue | Tout visiteur | Redirection | `helpers.php::languageReturnPath` |
| SA-7 | Socket MySQL et compte `svc_php` | Compte Linux local | S-04, D-02, D-05, D-07 | `database/setup/*grants.sql`, `.local/application.json` |
| SA-8 | Compte `root` MySQL et scripts d'administration | Exploitant | S-01 à S-06, toutes les données | `.local/admin.json`, `bin/*.py` |
| SA-9 | Répertoire `.local/` : datadir, secrets, journaux | Compte Linux local, logiciel malveillant, copie de la VM | I-01, K-01 à K-04, L-01 | `bin/init-local.py` |
| SA-10 | Sauvegardes `mysqldump` | Quiconque accède au répertoire d'export | B-01 | `bin/backup.py` |
| SA-11 | Dépôt Git : migrations et procédures | Collaborateurs du dépôt | S-01 à S-03 | `database/` |

## 4. Acteurs de menace

| ID | Acteur | Motivation | Accès et capacités | Cibles probables |
|---|---|---|---|---|
| TA-1 | **Salarié curieux** (rôle `employee`) | Connaître le salaire de ses collègues | Compte valide ; peut modifier les URL et les requêtes | D-02, D-03 par IDOR (SA-2) |
| TA-2 | **Opérateur RH, Paie ou Finance malveillant** | Gain financier : augmenter son salaire, détourner un virement | Droits métier légitimes, connaissance du processus | D-01 (RIB), D-02, D-03, D-04 |
| TA-3 | **Collusion de deux opérateurs** (par exemple RH et Finance) | Gain partagé | Ensemble, ils satisfont la séparation des tâches | D-02, D-03 |
| TA-4 | **Administrateur applicatif abusif** | Donner un rôle puissant à un complice | `iam.grant` / `iam.revoke` | D-06 |
| TA-5 | **Auditeur ou responsable indélicat** | Revendre ou divulguer des salaires | Lecture légitime de toute la paie | Exfiltration de D-02 et D-03 |
| TA-6 | **DBA ou exploitant** malveillant ou négligent | Fraude, effacement de traces, ou simple erreur | `root` MySQL, système de fichiers | Tout ; contourne triggers et droits |
| TA-7 | **Attaquant sans compte** | Accès initial | Doit atteindre `127.0.0.1:8080` (accès local) ou piéger un utilisateur connecté (CSRF, XSS) | SA-1, SA-4 |
| TA-8 | **Logiciel malveillant** sur la VM ou compte Linux compromis | Vol de données en masse | Lecture des fichiers de l'utilisateur | `.local/` (SA-9), sauvegardes (SA-10) |
| TA-9 | **Contributeur du dépôt** malveillant ou négligent | Porte dérobée, ou erreur de migration | Écriture dans le dépôt Git | Procédures, triggers, GRANT (SA-11) |

## 5. Menaces STRIDE et risque résiduel

| ID | STRIDE | Acteur → surface | Scénario | Contrôles existants (preuve) | V | I | Risque |
|---|---|---|---|---|:-:|:-:|---|
| T-01 | S | TA-7 → SA-1 | Force brute ou réutilisation de mots de passe | Limiteur de 5 essais par IP et par 15 min ; Argon2id ; message générique ; empreinte factice pour un login inexistant (`AuthService.php`) ; mots de passe de 24 octets aléatoires, soit 32 caractères (`init-local.py`) | 1 | 3 | **Moyen** |
| T-02 | S | TA-7, TA-8 → SA-5 | Vol de session : fichier `sess_*` ou cookie | `HttpOnly`, `SameSite=Lax`, régénération à la connexion et toutes les 15 min, expiration 20 min / 8 h, répertoire 0700 ; pas d'attribut `Secure` en HTTP | 1 | 3 | **Moyen** |
| T-03 | S | TA-8 → SA-7 | Avec le mot de passe de `svc_php` (K-02 en clair), appeler les procédures en se faisant passer pour Finance (`p_actor` arbitraire) | Fichier 0600, socket sans réseau ; **aucun lien** entre `p_actor` et l'identité MySQL | 1 | 3 | **Moyen** |
| T-04 | I | TA-1 → SA-2 | IDOR : changer `/payslips/{id}` pour lire le bulletin d'un collègue | `payslip_detail` vérifie le propriétaire et la publication (« Bulletin non publié inaccessible », `local-install.py` ; IDOR dans les deux sens, `payroll-http-live.py`) | 1 | 3 | **Moyen** |
| T-05 | T / I | TA-1, TA-7 → SA-3 | Injection SQL dans un champ de formulaire | Requêtes préparées natives (`ATTR_EMULATE_PREPARES=false`), identifiants SQL en liste blanche (`PeriodRepository.php`), `svc_php` sans DDL ni DML financier. **Phase 4** : l'impact a été mesuré sur un composant volontairement vulnérable, en laboratoire (`08-ANALYSE-DE-VULNERABILITE.md`). Avec les privilèges de la phase 1, un salarié lit les empreintes et les salaires ; avec les rôles de la phase 2, ces lectures sont refusées, mais l'identité des salariés reste lisible. Aucune injection n'a été trouvée dans l'application elle-même. | 1 | 3 | **Moyen** |
| T-06 | T | TA-2 → SA-3 | Un opérateur décide de sa propre augmentation ou approuve sa propre paie | `COMP_SELF_APPROVAL`, `PAY_FORBIDDEN`, incompatibilité des rôles (`lab/mysql-security.py`, 18 refus) | 1 | 3 | **Moyen** |
| T-07 | T | TA-3 → SA-3 | **Collusion RH + Finance** : augmentation injustifiée proposée et approuvée | Traçabilité complète (auteurs, motifs, historique immuable) ; **aucune détection** d'anomalie (seuil, augmentation hors norme) | 2 | 3 | **Élevé** |
| T-08 | T | TA-2, TA-6 → SA-8 | **Détournement de salaire par modification du RIB** | Unicité du RIB, auteur obligatoire, horodatage SQL, suppression interdite (migration `012`) ; aucune fonction applicative ne modifie le RIB à ce jour ; **ni double validation, ni notification, ni journal des accès** | 2 | 3 | **Élevé** |
| T-09 | E | TA-4 → SA-3 | L'administrateur attribue un rôle Finance à un complice | Auto-attribution interdite (`IAM_FORBIDDEN`), cumul interdit (`IAM_CONFLICT`), motif et historique obligatoires ; pas de double approbation | 1 | 3 | **Moyen** |
| T-10 | I | TA-8 → SA-7 | Avec `svc_php`, lecture directe de tous les salaires et des empreintes de mots de passe, puis cassage hors ligne | Argon2id ; mais **SELECT direct** sur `salary_conditions`, `compensation_requests` et `accounts.password_hash` (écart E1) | 1 | 3 | **Moyen** |
| T-11 | I | TA-5 → SA-2 | **Exfiltration légitime** : un auditeur ou un responsable consulte en masse les bulletins | Accès limité aux rôles habilités ; **aucune lecture journalisée** (écart E4), donc aucune détection | 2 | 3 | **Élevé** |
| T-12 | I | TA-8 → SA-9, SA-10 | Copie du datadir ou d'une sauvegarde : toutes les données en clair, CIN et RIB compris | Permissions 0700 / 0600 ; aucun chiffrement (écarts E2, E7) | 1 | 3 | **Moyen** |
| T-13 | I | TA-8 → SA-9 | Lecture des secrets `.local/*.json` : prise de contrôle de `root` et de tous les comptes web | Permissions 0600 ; secrets en clair (écart E6) | 1 | 3 | **Moyen** |
| T-14 | T / R | TA-6 → SA-8 | Le DBA désactive un trigger, modifie un montant, puis efface les traces | **Aucun** contrôle contre `root` par conception ; sauvegardes antérieures comme seule preuve | 1 | 3 | **Moyen** |
| T-15 | R | TA-2, TA-7 → SA-1, L-01 | Contester une action, ou lancer des tentatives de connexion non attribuables | Décisions signées par leur auteur en base ; mais `auth.failed` sans identifiant ni IP, et journal modifiable par l'application (EI-11) | 2 | 2 | **Moyen** |
| T-16 | T | TA-7 → SA-4 | XSS stockée dans un motif, exécutée dans la session d'un approbateur | Échappement `h()` (`ENT_QUOTES`) dans les vues, CSP `script-src 'self'`, jeton CSRF | 1 | 3 | **Moyen** |
| T-17 | T | TA-7 → SA-3 | CSRF : faire approuver un bulletin par un utilisateur connecté | Jeton CSRF sur tous les POST, vérifié par `hash_equals`, `SameSite=Lax` (« CSRF manquant refusé », `local-install.py`) | 1 | 3 | **Moyen** |
| T-18 | D | TA-1, TA-7 → SA-1 | **Blocage des connexions de tous** : en local, tout le monde arrive de `127.0.0.1` et partage le compteur. Cinq mauvais mots de passe bloquent tous les utilisateurs 15 minutes, de façon renouvelable (*déduit de `LoginLimiter.php`, non exercé*) | Aucun : c'est le contrôle de T-01 qui crée la faiblesse | 3 | 2 | **Élevé** |
| T-19 | D | TA-6 → SA-8 | Suppression accidentelle (`DROP TABLE`, `TRUNCATE`) ou corruption | `*_prevent_delete` bloque le `DELETE` ligne à ligne, pas `DROP` ni `TRUNCATE` ; sauvegarde **manuelle et non planifiée** (ED-1) | 2 | 3 | **Élevé** |
| T-20 | D | — → I-02, I-05 | Panne de la VM ou du disque | Instance unique ; redémarrage propre testé (ED-5) | 2 | 2 | **Moyen** |
| T-21 | E / T | TA-9 → SA-11 | Migration ou procédure piégée, installée avec les droits `root` | Dépôt privé, audit de secrets, refus de rejouer l'installation ; **pas de revue obligatoire** | 1 | 3 | **Moyen** |
| T-22 | D | TA-4 → SA-3 | Révocation du seul responsable Finance : approbations et paiements bloqués | Historique de révocation ; aucun minimum de titulaires (ED-8) | 1 | 2 | **Faible** |
| T-23 | I | TA-7 → SA-6 | Redirection ouverte via `return_to` | Liste blanche stricte des chemins internes (`languageReturnPath`) | 1 | 1 | **Faible** |
| T-24 | I | TA-7 → FC-1 | Divulgation via les messages d'erreur | Messages génériques, exceptions PDO non propagées, `display_errors=0` | 1 | 2 | **Faible** |

### Matrice des risques

| Vraisemblance ↓ / Impact → | 1 | 2 | 3 |
|---|---|---|---|
| **3** | | T-18 | |
| **2** | | T-15, T-20 | T-07, T-08, T-11, T-19 |
| **1** | T-23 | T-22, T-24 | T-01 à T-06, T-09, T-10, T-12 à T-14, T-16, T-17, T-21 |

**Bilan : 5 Élevé, 16 Moyen, 3 Faible.**

## 6. Traitement des risques

| Risque | Décision | Mesure | Phase |
|---|---|---|---|
| **T-08** Détournement par le RIB | Réduire | Lecture et modification du RIB par procédure dédiée ; double validation RH + Finance ; notification au salarié ; journal des accès | 2, 7 |
| **T-11** Exfiltration légitime | Réduire | Journaliser toute lecture de données Restreint (qui, quand, quel salarié) ; règle de détection des consultations massives | 7 |
| **T-07** Collusion | Réduire, puis accepter le résiduel | Alerte sur les augmentations au-delà d'un seuil ; revue périodique par l'auditeur. La collusion reste un risque organisationnel. | 7, 10 |
| **T-18** Blocage des connexions | Réduire | Limiter par compte **et** par IP, avec des seuils distincts ; journaliser le compte visé. **Fait en phase 3** : 5 échecs par compte, 30 tentatives par adresse ; le blocage d'un compte n'affecte plus les autres (preuve HTTP dans `tests/local-install.py`). Résiduel : un attaquant peut bloquer **un** compte qu'il cible pendant 15 min, et 30 tentatives depuis une même adresse bloquent encore cette adresse. Le risque passe de Élevé (3 × 2) à Moyen (2 × 2). | 3 |
| **T-19** Suppression accidentelle | Réduire | Sauvegarde planifiée hors VM ; exercice de perte et de restauration ; `DROP` réservé à un compte distinct | 8, 9 |
| T-10, T-03 Compromission de `svc_php` | Réduire | Retirer les SELECT directs sur les tables Restreint (passer par des procédures) ; protéger K-02. **Phase 2** : rôles MySQL activés par requête. Ils limitent l'exploitation d'une injection ou d'une erreur de code, mais **pas** le vol du secret, qui donne tous les rôles. Le risque de T-10 reste donc inchangé ; la protection de K-02 (phase 9) demeure la mesure principale. | 2, 9 |
| T-12, T-13 Copies et secrets en clair | Réduire | Chiffrement des colonnes D-01 et des exports ; suppression de `credentials.json` après première lecture | 6, 8, 9 |
| T-15 Répudiation | Réduire | Identifiant tenté et IP dans `auth.failed` ; journal en ajout seul, hors de portée de l'application. **Fait en phase 3** : `auth.failed` consigne le compte visé (s'il existe) et l'adresse, `auth.throttled` la portée du blocage. L'identifiant saisi n'est volontairement pas écrit, car il peut contenir un mot de passe tapé dans le mauvais champ. Reste à faire : un journal en ajout seul (phase 7). | 3, 7 |
| T-14 DBA malveillant | Accepter, et détecter | Journalisation MySQL hors du contrôle du DBA ; comparaison avec les sauvegardes | 7, 9 |
| T-21 Chaîne d'approvisionnement | Réduire | Revue obligatoire des migrations (branche protégée, relecture par un pair) | 9 |
| T-01, T-02, T-04 à T-06, T-09, T-16, T-17 | Accepter le résiduel | Contrôles en place et testés ; maintenir les tests de non-régression | 5 (preuve avant / après) |
| T-20, T-22 à T-24 | Accepter | Impact limité ou contexte académique | — |

## 7. Hypothèses et hors périmètre

- **Hôte de confiance.** La VM, son noyau et le compte Linux de l'exploitant sont supposés sains. Leur compromission (TA-8) est traitée comme un risque, mais pas leur durcissement système complet.
- **Déploiement local.** Le serveur web n'écoute que sur `127.0.0.1`. Une exposition réseau ajouterait des menaces (interception, attaques distantes) qui exigeraient HTTPS et un serveur web de production.
- **Paiements fictifs.** Il n'existe aucun lien bancaire réel ; les menaces visant un prestataire de paiement sont hors périmètre.
- **Données fictives.** Le jeu de démonstration (`009`, `010`) ne correspond à aucune personne réelle.
- **Attaques volumétriques** (saturation réseau) : hors périmètre en déploiement local.
