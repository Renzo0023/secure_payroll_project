# 14 — Durcissement de la base de données (phase 9)

Alimente la **section « Database Hardening » du rapport**. L'énoncé impose un **bilan avant / après
durcissement** couvrant au minimum : comptes par défaut, utilisateurs inutiles, privilèges excessifs,
comptes applicatifs faibles, exposition réseau, journalisation, fichiers de configuration, fonctions
inutiles, permissions de fichiers, niveau de correctifs, protection des sauvegardes — **chaque décision
majeure justifiée**.

Particularité de ce projet : il est construit « sécurité d'abord » depuis la phase 1. La colonne
**« Après »** décrit donc l'état **réellement livré** par les phases 1 à 8, plus l'unique correctif
résiduel ajouté en phase 9 (`secure_file_priv=NULL`, `local_infile=OFF`). La colonne **« Avant »**
décrit le déploiement **MySQL par défaut / naïf** qu'on obtiendrait sans ces choix — c'est la base de
comparaison exigée.

Montrer une configuration ne suffit pas : l'état « Après » est **prouvé** par un audit rejouable,
`python3 tests/hardening-audit.py` (**28 contrôles**, instance jetable isolée).

## 1. Bilan avant / après durcissement

| Zone de sécurité | Avant durcissement (MySQL par défaut / naïf) | Après durcissement (livré) | Où / preuve |
|---|---|---|---|
| **Comptes par défaut & anonymes** | Comptes anonymes possibles, base `test` ouverte à tous | **Aucun anonyme, aucune base `test`**, `root` limité à `localhost` | audit §comptes ; `assert_isolated` |
| **Utilisateurs inutiles** | Comptes de démonstration et d'exemple laissés actifs | **Seuls 5 comptes de connexion** (`root`, `svc_php`, 3 opérateurs) ; propriétaires DEFINER et rôles **verrouillés** | `mysql.user` ; audit §utilisateurs |
| **Privilèges excessifs** | Compte applicatif avec privilèges larges, voire `GRANT OPTION` | **Moindre privilège par rôles** ; `svc_php` **aucun** privilège direct (tout par rôles) ; **aucun** FILE/SUPER/… hors `root`/système/`sp_dba` | phase 2 ; audit §privilèges |
| **Comptes applicatifs faibles** | Mots de passe faibles, hachage réversible ou absent | **Argon2id** (comptes applicatifs), mots de passe **aléatoires** (`svc_php`), `caching_sha2_password` partout | phase 3 ; audit §comptes faibles |
| **Exposition réseau** | Écoute TCP sur `0.0.0.0:3306`, protocole X ouvert | **`--skip-networking` (0 port TCP)**, socket Unix privé, **X protocol désactivé** | `start()` ; audit §réseau |
| **Journalisation** | Audit désactivé/limité ; traces altérables | **Piste d'audit en base inviolable (ajout seul)** + journal fichier + log d'erreur privé ; `general_log` off | phases 7 ; audit §journalisation |
| **Fichiers de configuration** | `my.cnf` lu depuis plusieurs emplacements, variables persistées | **`--no-defaults`** (aucun `my.cnf` lu) + **`--persisted-globals-load=OFF`** (aucune variable persistée) | `start()` ; audit §config |
| **Fonctions / services inutiles** | `LOAD DATA LOCAL`, opérations fichiers, X protocol actifs | **`local_infile=0`**, **`secure_file_priv=NULL`** (aucune opération fichier, même root), mysqlx off | **phase 9** ; audit §fonctions |
| **Permissions de fichiers** | datadir et fichiers lisibles par le groupe/les autres | **Instance 0700**, secrets et **clés 0600**, datadir fermé aux « autres » | audit §permissions |
| **Niveau de correctifs** | Version ancienne non maintenue | **MySQL 8.4.13** (série LTS maintenue) | `VERSION()` ; audit §correctifs |
| **Protection des sauvegardes** | Sauvegarde absente ou en clair, mêmes identifiants | **Dump chiffré AES-256-GCM**, **compte de sauvegarde en lecture seule**, **clés conservées à part** | phase 8 ; audit §sauvegardes |

### Reprise du tableau-type de l'énoncé

| Security Issue | Before Hardening | After Hardening |
|---|---|---|
| Shared accounts | Present | **Removed** (comptes nominatifs/dédiés, pas de compte partagé ; `root` non utilisé par l'app) |
| Excessive privileges | Present | **Restricted** (rôles à moindre privilège, `svc_php` sans droit direct) |
| Password storage | Insecure | **Securely hashed** (Argon2id ; `caching_sha2_password`) |
| SQL Injection | Vulnerable | **Mitigated** (requêtes paramétrées + accès par procédures ; démontré phases 4-5) |
| Audit logging | Disabled/Limited | **Enabled** (piste en base inviolable, phase 7) |
| Backup strategy | Inadequate | **Implemented** (chiffrée, compte dédié, restauration vérifiée, phase 8) |
| Sensitive data | Insufficiently Protected | **Appropriate controls applied** (chiffrement au repos AES-256-GCM, phase 6) |
| Network exposure | Exposed (TCP) | **Closed** (socket-only, `--skip-networking`) |

## 2. Justification des décisions majeures

- **Socket-only (`--skip-networking`)** : supprime toute la surface d'attaque réseau (balayage, force
  brute à distance, CVE du protocole). L'application et la base sont sur le même hôte ; aucun besoin de
  TCP. `assert_isolated` **refuse de fonctionner** si un port s'ouvrait — le durcissement est vérifié à
  chaque opération, pas seulement supposé.
- **Moindre privilège par rôles + `svc_php` sans droit direct** : même si le compte applicatif était
  compromis (p. ex. via une injection résiduelle), il ne détient aucun privilège en propre ; il n'agit
  qu'au travers de rôles et de procédures DEFINER au périmètre strict. L'audit vérifie `svc_php`
  **absent** des tables de privilèges (table/colonne/schéma).
- **`secure_file_priv=NULL` + `local_infile=OFF` (ajout phase 9)** : neutralise `LOAD_FILE`,
  `INTO OUTFILE`, `LOAD DATA [LOCAL] INFILE` — vecteurs classiques de lecture/écriture de fichiers
  serveur et d'exfiltration, **même pour `root`**. Aucun compte n'ayant le privilège `FILE`, c'est une
  défense en profondeur sans impact : l'application n'utilise jamais ces fonctions.
- **`--no-defaults` + `--persisted-globals-load=OFF`** : la configuration de sécurité est **explicite
  et reproductible** dans le code de lancement ; aucun `my.cnf` externe ni variable persistée ne peut la
  desserrer à notre insu.
- **Piste d'audit en ajout seul** : un durcissement qui n'empêche pas l'effacement des traces est
  incomplet ; ici même `root` ne peut ni modifier ni supprimer une trace (erreur 1644).
- **Sauvegardes chiffrées à compte dédié, clés séparées** : la sauvegarde ne doit pas devenir le maillon
  faible (vol du dump, écriture par le compte de sauvegarde). Lecture seule + chiffrement + séparation
  des clés traitent les trois risques (voir [13-SAUVEGARDE-ET-RESTAURATION](13-SAUVEGARDE-ET-RESTAURATION.md)).

## 3. Ce qui reste hors périmètre (et pourquoi c'est acceptable ici)

- **TLS / `require_secure_transport`** : sans objet en socket-only (pas de trafic réseau à chiffrer). À
  activer si une exposition réseau devenait nécessaire.
- **`skip_name_resolve`** : sans objet (aucune connexion TCP à résoudre). Le socket n'utilise pas la
  résolution de noms.
- **Schéma `sys`** : conservé (vues de diagnostic standard, compte `mysql.sys` verrouillé) ; aucun
  privilège applicatif ne s'y rattache.
- **Rotation/HSM des clés** : les clés sont hors base et hors dépôt, en 0600 ; une exploitation réelle
  ajouterait rotation et coffre matériel.

## 4. Preuves

| Preuve | Où |
|---|---|
| Audit de durcissement rejouable (28 contrôles, 11 zones) | `tests/hardening-audit.py` |
| Durcissement intégré au lancement du serveur | `bin/init-local.py` (`start`, `assert_isolated`) |
| Moindre privilège et absence de droits directs `svc_php` | `tests/privilege_matrix.py`, `tests/local-install.py` |

Commande : `python3 tests/hardening-audit.py`.

## 5. Articulation avec les autres phases

Le durcissement n'est pas une couche ajoutée en fin de projet : il **consolide et vérifie** les choix des
phases 1 à 8 (moindre privilège, hachage fort, chiffrement, audit inviolable, sauvegarde protégée) et
n'ajoute qu'un correctif résiduel. La **phase 10 (investigation d'incident)** s'appuiera sur cet état
durci — piste d'audit inviolable et sauvegardes fiables — pour reconstruire et contenir un incident
simulé.
