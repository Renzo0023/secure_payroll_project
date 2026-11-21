# Phase 1 — Analyse de sécurité CIA

> Livrable de la phase 1 (« Confidentiality / Integrity / Availability requirements », « CIA security analysis »).
> S'appuie sur [01-INVENTAIRE-DES-ACTIFS.md](01-INVENTAIRE-DES-ACTIFS.md) (identifiants D-, S-, K-, L-, B-, I-) et [02-CLASSIFICATION-DES-DONNEES.md](02-CLASSIFICATION-DES-DONNEES.md).
> Chaque exigence indique le mécanisme existant, sa preuve et son état : **Satisfaite**, **Partielle** ou **Non satisfaite**. Une exigence n'est déclarée satisfaite que si un mécanisme est présent dans le code **et** vérifié par un test.

## 1. Échelle des besoins

| Besoin | Confidentialité | Intégrité | Disponibilité |
|---|---|---|---|
| **Élevé** | Divulgation = fraude, usurpation ou atteinte grave à un salarié | Altération = paiement erroné, fraude ou perte de la preuve | Indisponibilité en fin de mois = salaires non versés à temps |
| **Moyen** | Atteinte à la vie privée ou ciblage | Altération détectable et réparable sans perte financière | Gêne opérationnelle de quelques jours |
| **Faible** | Information interne sans personne | Gêne mineure | Sans effet sur la paie |

**Contexte de disponibilité.** La paie est un processus **mensuel** : calcul, vérification, approbation Finance, publication, paiement. Le besoin de disponibilité est donc **élevé pendant la fenêtre de paie** (fin de mois) et **moyen** le reste du temps. Les données doivent en revanche être **conservées sans perte en permanence**, car un bulletin approuvé est une pièce justificative.

## 2. Matrice des besoins par actif

| Actif | C | I | A | Justification |
|---|---|---|---|---|
| D-01 Données personnelles | **Élevé** | **Élevé** | Moyen | CIN, CNSS et RIB permettent l'usurpation. Un RIB altéré détourne le salaire. Elles ne sont lues qu'au moment du paiement. |
| D-02 Rémunérations | **Élevé** | **Élevé** | Moyen | Salaires individuels ; une condition altérée fausse toutes les paies suivantes. |
| D-03 Calcul et bulletins | **Élevé** | **Élevé** | **Élevé** | Montants versés ; nécessaires à la date de paie. |
| D-04 Règlements et corrections | Élevé | **Élevé** | **Élevé** | Registre comptable : une écriture fausse ou dupliquée est une perte financière. |
| D-05 Authentifiants (`accounts`) | **Élevé** | **Élevé** | **Élevé** | Sans compte valide, personne ne peut traiter la paie. |
| D-06 RBAC | Moyen | **Élevé** | **Élevé** | Une attribution falsifiée contourne tout. Sans rôles valides, aucune action n'est possible. |
| D-07 Identité et parcours | Moyen | **Élevé** | Moyen | Le contrat et l'affectation conditionnent le calcul (couverture des jours). |
| D-08 Référentiels | Faible | Moyen | Faible | Organigramme. |
| S-01 / S-02 Procédures et triggers | Faible | **Élevé** | **Élevé** | Ce sont les contrôles eux-mêmes. |
| S-03 / S-04 Privilèges et `svc_php` | Moyen | **Élevé** | **Élevé** | Ils définissent ce que l'application peut faire. |
| K-01 à K-04 Secrets et sessions | **Élevé** | Moyen | Moyen | Divulgation = prise de contrôle. |
| L-01 à L-04 Journaux et historiques | Moyen | **Élevé** | Moyen | Valeur probatoire : sans eux, aucune investigation n'est possible (phase 10). |
| B-01 / B-02 Sauvegardes | **Élevé** | **Élevé** | **Élevé** | Copie intégrale ; seul moyen de reprise. |
| I-01 / I-02 Datadir et serveur MySQL | **Élevé** | **Élevé** | **Élevé** | Tous les actifs en dépendent. |

**Lecture.** L'**intégrité** est le besoin dominant du système. Presque tous les actifs y sont en Élevé, car l'enjeu principal d'une paie est de **verser le bon montant à la bonne personne**. La confidentialité est élevée sur un périmètre plus restreint (D-01, D-02, D-03, secrets et copies). La disponibilité n'est élevée qu'en fin de mois.

## 3. Exigences de confidentialité

| ID | Exigence | Mécanisme existant | Preuve | État | Phase |
|---|---|---|---|---|---|
| EC-1 | Un salarié ne consulte que **ses propres** bulletins, et seulement une fois publiés | `payslip_detail` vérifie le propriétaire et l'événement `published` (`008_payroll_operations.sql`) | `tests/local-install.py` : « Bulletin non publié inaccessible à Employee », « Bulletin publié propre accessible » | **Satisfaite** | — |
| EC-2 | Les montants de rémunération ne sont lisibles que par RH, Finance, Paie et Audit, **au niveau de l'application comme de la base** | Application : `AuthService::can` (`payroll.read`, `compensation.read`). Base : procédures pour la paie. | Matrice `can()` testée par `tests/payroll-web-unit.php` | **Partielle** en phase 1 : `svc_php` lisait directement `salary_conditions` et `compensation_requests` (écart E1). **Satisfaite en phase 2** pour les sessions applicatives : rôles MySQL activés par requête, matrice testée ([06](06-MATRICE-DE-CONTROLE-D-ACCES.md)). Limite : le secret de `svc_php` donne tous les rôles (T-03, T-10) | 2 |
| EC-3 | Les données personnelles (D-01) ne sont lisibles que par RH, par le salarié pour ses propres données, et pour le seul RIB par Finance au moment du paiement | Aucun privilège accordé (migration `012`) | `tests/local-install.py` : « Service PHP sans accès aux données personnelles » | **Partielle** : protégées par l'absence d'accès ; le contrôle fin reste à construire | 2 |
| EC-4 | Les mots de passe ne sont **jamais** stockés ni journalisés en clair | Argon2id, contrainte `ck_accounts_argon2id`, `#[\SensitiveParameter]`, journal sans mot de passe | `tests/sql-static.php`, `tests/local-install.py` (six empreintes distinctes) | **Partielle** : `.local/credentials.json` conserve les mots de passe initiaux en clair (K-03) | 9 |
| EC-5 | Identifiants officiels, RIB et montants sont **chiffrés au repos**, y compris dans les sauvegardes | Aucun | — | **Non satisfaite** (E2, E3, E7) | 6, 8 |
| EC-6 | Aucune donnée sensible n'apparaît dans les erreurs, les URL ou les journaux | Messages génériques, `display_errors=0`, exceptions PDO non propagées (`Connection.php`), identifiants numériques dans les URL, `auditEvent` sans valeur métier | Revue de code (`helpers.php`, `bootstrap.php`, `Controller.php`) | **Satisfaite** | — |
| EC-7 | La base n'est **pas accessible par le réseau** | `--skip-networking`, `--mysqlx=OFF`, port 0, socket dans un répertoire 0700 | `init-local.py::assert_isolated` (vérifié à chaque démarrage) | **Satisfaite** | — |
| EC-8 | Les secrets d'exploitation ne sont jamais publiés | `.gitignore`, fichiers 0600 / répertoire 0700, `bin/audit-secrets.py` | Audit des secrets : `passed: true` | **Satisfaite** (secrets néanmoins en clair sur disque, voir EC-4) | 9 |
| EC-9 | Les flux navigateur ↔ serveur sont protégés | HTTP sur la boucle locale `127.0.0.1` uniquement, cookie `HttpOnly` / `SameSite=Lax`, CSP | Code `public/index.php`, `Session.php` | **Partielle** : pas de TLS ; acceptable en local uniquement, sinon `Secure` et HTTPS obligatoires | 6, 9 |

## 4. Exigences d'intégrité

| ID | Exigence | Mécanisme existant | Preuve | État | Phase |
|---|---|---|---|---|---|
| EI-1 | Les montants sont **exacts** : pas d'arrondi flottant, brut = base + primes, net = brut − retenues, net ≥ 0 | `DECIMAL(12,2)`, contraintes CHECK de `payroll_calculations`, `PAY_NET` | `tests/payroll-calculator.php` ; `tests/local-install.py` : 28/30 jours, 11 200,00 MAD | **Satisfaite** | — |
| EI-2 | **Séparation des tâches** : personne ne décide de sa propre rémunération ni de son propre bulletin ; le préparateur n'approuve pas | `COMP_SELF_APPROVAL` (`compensation_decide`), `PAY_FORBIDDEN` (`payroll_calculate`, `payslip_transition`), incompatibilité de rôles dans `AuthService::currentUser` | `lab/mysql-security.py` (18 refus métier, campagne du 06/11) ; « Approbation Finance indépendante » (`local-install.py`) | **Satisfaite**. Remarque : un responsable RH peut *proposer* son propre salaire ; la décision reste à une autre personne de Finance. | — |
| EI-3 | Les historiques et le registre sont **immuables** | Triggers `*_prevent_delete`, `*_preserve_*`, `*_no_update`, `*_no_delete` | `tests/database-integrity.php` (33 assertions, 06/11) ; « Suppression des données personnelles refusée » | **Partielle** : efficace contre le DML, **pas** contre un compte disposant de `TRIGGER`, de DDL ou de `root` | 9 |
| EI-4 | Chaque décision est **attribuable** : auteur (compte et personne) et heure SQL | Colonnes `*_by`, `actor_employee_id`, `occurred_at` NOT NULL ; heure fixée par la base | Schéma ; trigger `employee_personal_data_preserve_origin` | **Partielle** : satisfaite pour les décisions en base. Depuis la phase 3, `auth.failed` consigne le compte visé et l'adresse ; le journal reste modifiable (EI-11) | 7 |
| EI-5 | Un bulletin n'est **payé qu'une fois** | Verrou sur le salarié, relecture du solde, référence unique dans `settlement_ledger` | « Second paiement refusé », « Une seule écriture financière » (`local-install.py`) | **Satisfaite** | — |
| EI-6 | On n'approuve **pas un calcul périmé** | `source_hash` recalculé avant vérification et approbation (`PAY_STALE`) | `tests/payroll-races.py` (18 contrôles, 06/11) | **Satisfaite** | — |
| EI-7 | Les **droits** ne peuvent être modifiés que par un administrateur, jamais pour lui-même, avec motif et historique | `iam_grant` / `iam_revoke` : `IAM_FORBIDDEN`, `IAM_CONFLICT`, motif obligatoire, triggers sur `role_assignments` | `tests/iam-mysql.php`, `tests/iam-http.py` (campagne du 06/11) | **Partielle** : aucune double validation pour un rôle puissant | 2 |
| EI-8 | Toute modification du **RIB** est tracée, validée par une seconde personne et notifiée au salarié | Auteur obligatoire et horodatage SQL (trigger) ; unicité du RIB | « Modification sans auteur refusée », « RIB mal formé refusé » | **Partielle** : ni double validation ni notification | 2, 7 |
| EI-9 | Les données personnelles respectent des **formats valides** | Contraintes CHECK de la migration `012` (CIN, CNSS, RIB, téléphone, e-mail, âge ≥ 15 ans) | `tests/local-install.py` | **Satisfaite** (format du RIB seulement, sans clé de contrôle) | — |
| EI-10 | Les **sauvegardes** sont vérifiables | Manifeste SHA-256 (`bin/backup.py`) | `lab/mysql-recovery.py` (32 contrôles, 06/11) | **Satisfaite** | 8 |
| EI-11 | Les **journaux** ne peuvent être ni modifiés ni effacés par l'application | Aucun : `application.log` est un fichier modifiable par l'utilisateur Linux qui exécute PHP | — | **Non satisfaite** | 7 |
| EI-12 | Les **objets de sécurité** (procédures, triggers, droits) ne sont modifiés que par une migration revue | Comptes DEFINER verrouillés, `svc_php` sans DDL ni `GRANT OPTION`, installateur refusant tout rejeu | « Service sans privilège global ni GRANT OPTION », « Cinq propriétaires verrouillés » | **Partielle** : aucune revue obligatoire des migrations dans le dépôt | 9 |

## 5. Exigences de disponibilité

### Objectifs proposés

Ces objectifs sont **proposés par l'équipe** et doivent être validés par la Direction financière.

| Objectif | Fenêtre de paie (fin de mois) | Hors fenêtre | Justification |
|---|---|---|---|
| **RTO** (durée maximale d'interruption) | 4 heures ouvrées | 2 jours ouvrés | Les salaires doivent être versés à date fixe ; hors fenêtre, seules des saisies RH sont retardées. |
| **RPO** (perte de données maximale) | 24 heures | 24 heures | Une journée de saisies RH ou Finance peut être ressaisie depuis les justificatifs. Une décision approuvée perdue doit être retrouvée dans la sauvegarde du jour. |

### Exigences

| ID | Exigence | Mécanisme existant | Preuve | État | Phase |
|---|---|---|---|---|---|
| ED-1 | Une sauvegarde **quotidienne**, conservée **hors de la VM** | `bin/backup.py` existe, mais son lancement est **manuel** et sa destination laissée à l'opérateur | — | **Non satisfaite** : le RPO de 24 h n'est garanti par rien | 8 |
| ED-2 | La **restauration** est démontrée après une perte réelle, pas seulement l'existence d'un fichier | Restauration dans une seconde instance (`lab/mysql-recovery.py`) | 32 contrôles (06/11) | **Partielle** : aucune perte simulée (suppression de table) suivie d'une restauration | 8 |
| ED-3 | Une **suppression accidentelle** est empêchée ou rattrapable | Triggers `*_prevent_delete` ; clés étrangères `RESTRICT` (aucune cascade) | « Suppression des données personnelles refusée » | **Partielle** : `DROP TABLE` ou `TRUNCATE` par un administrateur ne sont pas bloqués ; le rattrapage dépend d'ED-1 | 8 |
| ED-4 | Un utilisateur ne peut pas **bloquer la connexion des autres** | Limiteur : 5 échecs par **adresse IP** et par fenêtre de 15 minutes (`LoginLimiter.php`) | — | **Non satisfaite** en phase 1 : tous les utilisateurs arrivent de `127.0.0.1` et partageaient le même compteur ; cinq mauvais mots de passe, de n'importe qui, bloquaient **tout le monde**. **Satisfaite en phase 3** : compteur par compte (5) et par adresse (30). Le blocage d'un compte n'affecte plus les autres (« Autre compte, même adresse 127.0.0.1 : connexion possible »). Résiduel : blocage ciblé d'un seul compte pendant 15 min. | 3 |
| ED-5 | Le serveur **redémarre** sans perte de données | Arrêt par `SHUTDOWN` SQL, InnoDB | « Données conservées après arrêt et redémarrage » (`local-install.py`) | **Satisfaite** | — |
| ED-6 | Pas de **point unique de défaillance** | Instance unique sur une VM unique | — | **Non satisfaite, risque accepté** : contexte académique, à compenser par ED-1 et ED-2 | — |
| ED-7 | Les **clés de chiffrement** futures restent disponibles : une clé perdue rend les données illisibles | Sans objet aujourd'hui | — | **À prévoir** | 6 |
| ED-8 | Les **workflows** ne sont pas bloqués par l'absence d'un rôle | Un administrateur peut révoquer le seul responsable Finance (`iam_revoke`) | — | **Partielle** : aucune règle n'impose au moins un titulaire actif par rôle opérationnel | 2 |

## 6. Tensions entre C, I et A

Ces arbitrages devront être justifiés dans le rapport.

| Tension | Description | Arbitrage retenu |
|---|---|---|
| **Sauvegardes : A contre C** | Chaque copie de sauvegarde améliore la disponibilité mais multiplie les copies en clair de D-01 et D-02 | Chiffrer les exports et stocker la clé séparément (phases 6 et 8) |
| **Chiffrement : C contre A** | Chiffrer CIN et RIB protège la confidentialité, mais une clé perdue détruit les données | Gestion des clés avec copie de secours de la clé (ED-7) |
| **Immutabilité : I contre droits des personnes** | L'interdiction de suppression (`*_prevent_delete`) s'oppose au droit à l'effacement après la durée légale de conservation (loi 09-08) | Effacement uniquement par une procédure administrative tracée, hors application, après expiration de la durée légale (E8) |
| **Journalisation des lectures : I contre C** | Tracer chaque lecture de données Restreint (phase 7) crée un journal qui révèle qui consulte qui | Journal classé Confidentiel, accès limité à l'auditeur |
| **Limiteur de connexion : C contre A** | Un limiteur strict protège contre la force brute (C) mais permet de bloquer les connexions (A, ED-4) | Limiter par compte **et** par IP, avec un seuil distinct |
| **Séparation des tâches : I contre A** | Exiger deux personnes différentes bloque le processus si l'une est absente (ED-8) | Garder la séparation ; prévoir un suppléant nommé par rôle |

## 7. Synthèse

État à la fin de la phase 1 :

| Dimension | Satisfaites | Partielles | Non satisfaites | Point le plus faible |
|---|---:|---:|---:|---|
| Confidentialité (9) | 4 | 4 | 1 | Aucun chiffrement au repos (EC-5) |
| Intégrité (12) | 6 | 5 | 1 | Journaux modifiables (EI-11) ; contrôles contournables par un administrateur (EI-3) |
| Disponibilité (8) | 1 | 3 | 3 | Sauvegarde non planifiée (ED-1) ; limiteur partagé (ED-4) |

**Suivi** : EC-2 est satisfaite depuis la phase 2 (rôles MySQL), ED-4 depuis la phase 3 (limiteur par compte). État actuel :

| Dimension | Satisfaites | Partielles | Non satisfaites | Point le plus faible |
|---|---:|---:|---:|---|
| Confidentialité (9) | 5 | 3 | 1 | Aucun chiffrement au repos (EC-5) |
| Intégrité (12) | 6 | 5 | 1 | Journaux modifiables (EI-11) ; contrôles contournables par un administrateur (EI-3) |
| Disponibilité (8) | 2 | 3 | 2 | Sauvegarde non planifiée (ED-1) |

Plus de la moitié des exigences d'intégrité sont **satisfaites et testées**. C'est le point fort du projet, cohérent avec la conception centrée sur MySQL. Les faiblesses portent sur la **confidentialité au repos**, la **disponibilité** et la **protection des traces**. Elles correspondent aux phases 6, 7, 8 et 9.

ED-7, classée « À prévoir », n'est comptée dans aucune colonne.
