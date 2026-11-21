# 16 — Bilan final de sécurité du système (section 6)

Alimente la **section « Final Database Security Assessment » du rapport**. L'énoncé demande, le projet
terminé, un bilan répondant à neuf questions. Pour chacune : la **réponse**, **comment** elle est obtenue,
et la **preuve** vérifiable. Toutes les preuves sont **rejouables** (voir §11).

Principe directeur du système : **défense en profondeur et moindre privilège de bout en bout**, avec une
base privée (socket Unix, sans réseau) où l'application n'accède à rien directement — tout passe par des
**procédures DEFINER** et des **rôles** au périmètre strict.

## 1. Authentification — *les utilisateurs sont-ils correctement authentifiés ?*
**Oui.** Mots de passe applicatifs hachés en **Argon2id** (jamais réversibles) ; comptes MySQL en
`caching_sha2_password` avec mots de passe aléatoires ; propriétaires DEFINER **verrouillés** (aucune
connexion) ; verrouillage anti-force-brute (`auth.throttled`). *Preuve : phases 1-3 ; `tests/local-install.py`.*

## 2. Autorisation — *chacun n'accède-t-il qu'à ce dont il a besoin ?*
**Oui.** Contrôle d'accès par rôles **et** autorisation **au niveau de l'objet** côté serveur (un salarié
n'accède qu'à ses propres données ; l'IDOR est refusée, pas obscurcie). Les droits sont portés par des
rôles MySQL distincts, activés par requête. *Preuve : phases 1-2, 7 ; `tests/privilege_matrix.py`,
`Controller.php` (autorisation par objet).*

## 3. Moindre privilège — *les privilèges inutiles ont-ils été retirés ?*
**Oui.** `svc_php` ne détient **aucun** privilège direct (tout par rôles) ; chaque rôle n'a que l'EXECUTE
des procédures de son périmètre ; aucun `FILE`/`SUPER`/`GRANT OPTION` hors root et comptes système. La
piste d'audit elle-même suit le moindre privilège (l'app écrit sans lire, l'auditeur lit sans écrire).
*Preuve : phase 2 ; `tests/privilege_matrix.py`, `tests/hardening-audit.py`.*

## 4. Sécurité applicative — *l'injection SQL est-elle maîtrisée ?*
**Oui.** Requêtes **paramétrées** systématiques et accès **par procédures stockées** ; démonstration
avant/après sur une page volontairement vulnérable, confinée à un laboratoire hors de l'application.
*Preuve : phases 4-5 ; captures et lab d'injection.*

## 5. Protection des données — *les données sensibles sont-elles protégées ?*
**Oui.** Chiffrement **au repos AES-256-GCM** des données personnelles (RIB, CIN, CNSS), index aveugle
HMAC pour la recherche, **clés hors base et hors dépôt** (0600). L'accès du salarié est masqué ; la piste
d'audit ne contient jamais de secret. *Preuve : phase 6 ; `docs/security-assessment/...` + `tests/local-install.py`.*

## 6. Audit et supervision — *les activités de sécurité importantes sont-elles traçables ?*
**Oui.** Piste d'audit **centrale, inviolable (ajout seul), interrogeable** répondant aux cinq questions
(qui/quoi/quand/ressource/résultat), alimentée par l'application **et** par des déclencheurs qui captent
toute écriture directe sur une table sensible. Supervision avec détection de signaux (rafales, refus
répétés, lectures massives). *Preuve : phase 7 ; `tests/local-install.py` (piste + détection).*

## 7. Sauvegarde et restauration — *la base peut-elle être restaurée après une perte ?*
**Oui, démontré.** Sauvegarde logique par un **compte dédié en lecture seule**, **chiffrée au repos**,
clés conservées à part. Exercice complet rejoué : perte d'enregistrements **et** suppression de table →
restauration → **intégrité vérifiée** (comptes de lignes, données toujours déchiffrables, audit intact).
La leçon clé — les GRANT ne figurent pas dans un dump logique — est intégrée à la procédure de reprise.
*Preuve : phase 8 ; `tests/backup-recovery.py` (19 contrôles).*

## 8. Durcissement — *la surface d'attaque a-t-elle été réduite ?*
**Oui.** **Socket-only** (aucun port TCP), X protocol désactivé, `secure_file_priv=NULL`,
`local_infile=0`, `--no-defaults`, aucun compte par défaut/anonyme, permissions 0700/0600. Bilan
avant/après justifié, vérifié automatiquement. *Preuve : phase 9 ; `tests/hardening-audit.py`
(28 contrôles).*

## 9. Investigation d'incident — *les preuves disponibles permettent-elles d'enquêter ?*
**Oui, démontré.** Sur un incident simulé (tentatives d'accès non autorisées + abus d'un compte
privilégié), l'enquête reconstruit la **chronologie**, identifie les comptes et ressources, distingue les
contrôles qui ont tenu de la détection, et établit les preuves — chacun avec le **rôle d'investigation à
moindre privilège** adéquat, sans jamais exposer de donnée Restreinte. *Preuve : phase 10 ;
`tests/incident-investigation.py` (16 contrôles).*

## 10. Posture d'ensemble

| Axe | État | Nature du contrôle dominant |
|---|---|---|
| Authentification | ✔ | Prévention (hachage fort, verrouillage) |
| Autorisation | ✔ | Prévention (rôles + autorisation par objet) |
| Moindre privilège | ✔ | Prévention (rôles stricts, zéro droit direct) |
| Injection SQL | ✔ | Prévention (requêtes paramétrées, procédures) |
| Protection des données | ✔ | Prévention (chiffrement au repos, clés séparées) |
| Audit et supervision | ✔ | **Détection** (piste inviolable + signaux) |
| Sauvegarde et reprise | ✔ | Résilience (chiffrée, restauration vérifiée) |
| Durcissement | ✔ | Réduction de surface (socket-only, services off) |
| Investigation | ✔ | **Réponse** (reconstruction à partir des preuves) |

Là où la prévention ne peut pas tout (un DBA conserve des droits — risque assumé T-14), la **détection
inviolable** et la **capacité d'enquête** prennent le relais : c'est la cohérence recherchée entre les dix
phases.

## 11. Reproduire l'ensemble des preuves

| Suite | Portée | Contrôles |
|---|---|---|
| `python3 tests/local-install.py` | Installation, schéma, rôles, chiffrement, audit, détection | 151 |
| `python3 tests/privilege_matrix.py` | Matrice de moindre privilège par rôle | — |
| `python3 tests/backup-recovery.py` | Sauvegarde chiffrée et restauration vérifiée (phase 8) | 19 |
| `python3 tests/hardening-audit.py` | Durcissement, 11 zones (phase 9) | 28 |
| `python3 tests/incident-investigation.py` | Investigation d'incident (phase 10) | 16 |

Chaque suite s'exécute sur une **instance jetable isolée** (`/tmp`), sans jamais toucher d'instance
existante, et peut être rejouée à volonté.
