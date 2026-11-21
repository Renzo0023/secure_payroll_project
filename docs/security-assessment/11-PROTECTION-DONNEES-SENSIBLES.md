# 11 — Protection des données sensibles (phase 6)

Alimente la **section 13 du rapport** (« Sensitive Data Protection »). La phase 2 a confiné l'accès aux données
personnelles par rôle et par procédure ; la phase 6 ajoute la **protection intrinsèque de la donnée elle-même** :
le RIB, le numéro de pièce d'identité et le numéro CNSS sont désormais **chiffrés au repos**, affichés **masqués**,
et le RIB passe en **libre-service** du salarié.

Classification de référence : [02-CLASSIFICATION-DES-DONNEES.md](02-CLASSIFICATION-DES-DONNEES.md) (§ 5.1). Les
trois colonnes concernées sont **Restreint**, le niveau le plus élevé.

## 1. Les quatre contrôles et pourquoi ils fonctionnent

| Contrôle | Réalisation | Pourquoi il protège |
|---|---|---|
| **Chiffrement au repos authentifié** | `App\Security\FieldCipher` : AES-256-GCM (`openssl_encrypt`). Colonnes `rib`, `id_document_number`, `cnss_number` passées en `VARBINARY(128)` (migration `015`). Blob = `version(1)‖nonce(12)‖chiffré‖tag(16)`. | Un vidage SQL, une sauvegarde volée ou un accès `root` à la base ne livrent que des octets opaques : **la clé n'est pas dans la base**. GCM **authentifie** le texte chiffré — toute altération d'un octet stocké est détectée au déchiffrement (échec, pas de donnée falsifiée). |
| **Index aveugle (recherche / unicité)** | `FieldCipher::blindIndex` : HMAC-SHA256 (clé **distincte**) sur la valeur normalisée. Colonnes `*_index BINARY(32)` sous contrainte `UNIQUE`. | Un chiffré GCM a un nonce aléatoire : deux chiffrements d'un même RIB donnent des octets différents → l'unicité SQL classique est impossible. L'index aveugle est **déterministe** : il rejette un RIB déjà enregistré (indice de fraude : deux salariés, un compte) **sans jamais stocker le clair**. Clé séparée pour que l'index ne serve pas d'oracle sur le chiffrement. |
| **Gestion des clés hors base et hors dépôt** | Deux clés de 32 octets (`field.key`, `blind.key`) générées dans le répertoire d'exécution privé (`Runtime::directory()/keys`, `0600`), **hors dépôt** (`.gitignore` ignore `*.key`) et **hors base**. Octet de version en tête du blob : rotation de clé préparée. | Sépare le secret (la clé) de la donnée protégée (la base). Compromettre l'un ne suffit pas : il faut **la base et le système de fichiers privé**. La règle de l'énoncé — « clés hors du dépôt et hors de la base » — est tenue par construction. |
| **Masquage à l'affichage + moindre exposition** | `App\HR\PersonalData::mask*` : RIB réduit aux 4 derniers chiffres, CIN aux 2+2, CNSS aux 3 derniers. Le salarié ne voit jamais le clair complet à l'écran ; jamais de donnée sensible dans une URL ni un journal. | Réduit l'exposition même pour l'utilisateur légitime et en cas de capture d'écran ou d'épaule. Respecte l'exigence « Affichage masqué par défaut » de la classification. |

**Point clé pour le rapport.** Chiffrement et index aveugle protègent la donnée **au repos et en cas de fuite de la
base** ; la gestion des clés garantit que la base seule ne suffit pas ; le masquage réduit l'exposition **en
fonctionnement normal**. Les contrôles d'accès de la phase 2 (rôles, procédures `DEFINER`) restent la première
barrière — la phase 6 ajoute la défense en profondeur **sous** cette barrière.

## 2. Ce qui est chiffré, ce qui ne l'est pas, et pourquoi

| Donnée | Traitement | Justification |
|---|---|---|
| `rib`, `id_document_number`, `cnss_number` | **Chiffrées** (AES-256-GCM) + index aveugle | Identifiants officiels et coordonnées bancaires : cœur de l'usurpation et de la fraude. Non utilisées dans un calcul SQL → le chiffrement applicatif n'empêche aucun traitement. |
| `salary_conditions`, bulletins, montants | **Non chiffrées**, protégées par rôle | Les procédures de paie (calcul, prorata, net) **opèrent sur ces montants en SQL**. Les chiffrer casserait le calcul sans gain réel : ils restent illisibles au rôle Salarié et au compte de service (phase 2, écart E1). Décision explicite de périmètre. |
| `personal_email`, `address_line`, `birth_date`… | **Non chiffrées**, Confidentiel, protégées par rôle | Niveau inférieur (Confidentiel) ; accès déjà restreint à la RH. Le coût de chiffrement ne se justifie pas au regard du modèle de menace. |
| Mots de passe (`password_hash`) | **Hachage** Argon2id, jamais chiffrement réversible | Un authentifiant ne doit jamais pouvoir être redéchiffré (phase 3). À ne pas confondre avec le chiffrement réversible du RIB, qui doit, lui, être relu pour le virement. |

## 3. Accès : le salarié, ses seules données, par procédure

Le confinement à la fiche de l'acteur est porté par deux procédures `SQL SECURITY DEFINER` appartenant à un compte
verrouillé dédié, **`personal_data_owner`** (sixième propriétaire de procédures, `ACCOUNT LOCK`, mot de passe
aléatoire jeté) :

- **`personal_data_view(p_actor)`** — lecture. `p_actor` est l'identifiant de compte **fourni par le serveur**
  (session), jamais par l'utilisateur ; `payroll_assert` le résout vers l'employé correspondant et vérifie la
  permission `personal_data.view_own` + le rôle `employee`. Aucun paramètre ne permet de désigner la fiche d'un
  autre. Le texte chiffré est renvoyé tel quel ; déchiffrement et masquage se font en PHP.
- **`personal_data_set_rib(p_actor, p_rib_cipher, p_rib_index, p_bank_name)`** — saisie / mise à jour du **seul
  RIB**. Le chiffré et l'index aveugle sont calculés en PHP ; la procédure ne reçoit que des octets opaques.
  `SELECT … FOR UPDATE` puis `UPDATE` de la seule fiche de l'acteur ; l'index unique rejette un RIB déjà pris
  (`1062` → message « déjà enregistré »). Une fiche absente renvoie `PDATA_NO_RECORD`.

Le rôle applicatif `sp_employee` n'a **que l'EXECUTE** de ces deux procédures : aucun `SELECT`/`UPDATE` direct sur
`employee_personal_data` (vérifié : écriture directe du RIB refusée `1142`). Le libre-service du RIB répond à
l'exigence métier « le salarié saisit son RIB » tout en gardant la RH **sans accès au clair** du RIB ici.

## 4. Données en transit

L'instance MySQL privée est **socket-only** (`skip_networking`, port 0 — voir recette `assert_isolated`) : aucune
donnée sensible ne transite par le réseau entre l'application et la base. Pour un déploiement réparti, la même
donnée voyagerait sous TLS (`REQUIRE SSL` par compte, certificats serveur et client) ; le modèle socket élimine
le besoin dans le laboratoire. L'application web est servie en local (`127.0.0.1`).

## 5. Semence de démonstration : chiffrée, hors SQL en clair

Le SQL ne peut pas chiffrer avec notre clé applicative. Les données personnelles de démonstration ne sont donc
**plus** insérées par un script SQL en clair (`010_*` est devenu une pierre tombale) : elles sont semées,
**chiffrées**, par `bin/seed-personal-data.php` à partir de `database/seeds/personal_data_demo.json` (six fiches
fictives). L'installateur provisionne les clés puis appelle le semeur après les autres semences. Les RIB, CIN et
CNSS fictifs n'existent **jamais en clair** dans le dépôt sous une forme stockée en base.

## 6. Preuves

| Preuve | Où |
|---|---|
| 14 contrôles unitaires du chiffreur, **sans base** : aller-retour, nonce aléatoire, format du blob, détection d'altération GCM, mauvaise clé, index aveugle (déterminisme, séparation), clé de mauvaise longueur, blob tronqué, provision `0600` idempotente | `tests/field-cipher-unit.php` |
| Recette d'installation neuve (140 contrôles) : colonnes `VARBINARY`, six fiches chiffrées, **aucun secret en clair dans la page**, affichage masqué, RIB en libre-service enregistré **chiffré** (53 octets, le clair absent), doublon rejeté (index aveugle), RIB mal formé rejeté, accès refusé à un non-salarié, écriture directe refusée au rôle applicatif, six propriétaires verrouillés, matrice `sp_employee` 5/22 procédures | `tests/local-install.py`, `tests/privilege_matrix.py` |

Commandes : `php tests/field-cipher-unit.php` et `python3 tests/local-install.py`.

## 7. Ce qui reste (menace T-08)

Le RIB est l'**enjeu d'intégrité** majeur : en modifier la valeur détourne le salaire. La phase 6 en protège la
**confidentialité** (chiffrement, masquage) et l'**unicité** (index aveugle). La **double validation d'un
changement de RIB et l'alerte au salarié** (menace T-08 du [modèle de menace](04-MODELE-DE-MENACE.md)) sont
prévues pour une phase ultérieure : à ce stade, le salarié met à jour son RIB directement, l'action étant tracée
(`updated_by`, `updated_at`, événement `personal_data.rib_updated` au journal).
