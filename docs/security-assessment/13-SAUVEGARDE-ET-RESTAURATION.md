# 13 — Sauvegarde et restauration (phase 8)

Alimente la **section « Backup and Recovery » du rapport**. L'énoncé impose de créer une sauvegarde, de
la documenter, de **simuler une perte de données contrôlée**, de restaurer, de **vérifier l'intégrité**
des données récupérées et de documenter la reprise. Exigence explicite : *« montrer qu'un fichier de
sauvegarde existe ne suffit pas »* — il faut **démontrer une restauration réussie**.

La démonstration porte sur le système **actuel**, chiffrement (phase 6) et piste d'audit (phase 7)
compris, et est **rejouable** : `python3 tests/backup-recovery.py` (19 contrôles, instance jetable isolée).

## 1. Stratégie et pourquoi elle tient

| Décision | Réalisation | Justification |
|---|---|---|
| **Sauvegarde logique** | `mysqldump --single-transaction --quick --routines --triggers --events --hex-blob --no-tablespaces --databases secure_payroll` (via `bin/backup.py`). | Portable et sélective : permet de restaurer une table précise, de comparer, et de rejouer dans une instance indépendante. Le `--single-transaction` donne un instantané cohérent sans bloquer l'application. |
| **Compte dédié en lecture seule** | `backup_ops` (rôle `sp_backup`) : `SELECT, SHOW VIEW, TRIGGER, EVENT, LOCK TABLES` sur le schéma + `SHOW_ROUTINE` global. Aucune écriture, aucun DDL. `bin/backup.py` **refuse** root, `svc_php` et les propriétaires. | Moindre privilège jusque dans la sauvegarde : une compromission du compte de sauvegarde ne permet ni d'écrire ni de supprimer. |
| **Chiffrement au repos** | `bin/backup-crypt.py` chiffre le dump en **AES-256-GCM** (authentifié), clé de 32 octets lue dans un fichier (jamais en argument). | Le dump contient la structure, les **empreintes Argon2id** et les colonnes chiffrées de la phase 6. Même partiellement chiffré par la phase 6, l'ensemble est protégé au repos ; GCM détecte toute altération ou mauvaise clé. |
| **Gestion des clés séparée** | La **clé de sauvegarde** et les **clés de chiffrement des données** (phase 6 : `runtime/keys/field.key`, `blind.key`) sont conservées **hors** du répertoire de sauvegarde. | Une sauvegarde volée sans la clé de sauvegarde est illisible ; un dump restauré sans les clés phase 6 laisse les données sensibles **chiffrées illisibles**. Séparer clés et données est la condition de la confidentialité **et** de la récupérabilité. |
| **Intégrité vérifiable** | `manifest.json` (SHA-256 par fichier) + marqueur `EXPORT_COMPLETE`. Le code retour de `mysqldump` est contrôlé : un fichier présent ne prouve pas le succès. | Une sauvegarde n'est réputée exploitable qu'après contrôle d'empreinte **et** essai de restauration. |

## 2. Ce qui est, et n'est pas, dans une sauvegarde logique

| Dans le dump | **Hors** du dump (inventaire administratif séparé) |
|---|---|
| Schéma, données, procédures, déclencheurs, événements de `secure_payroll` | **Comptes MySQL, rôles et GRANT** (vivent dans le schéma système `mysql`) |
| Colonnes chiffrées (ciphertext phase 6) | **Clés de chiffrement** (phase 6) et **clé de sauvegarde** |
| Lignes de la piste d'audit | Configuration serveur, journaux système |

**Conséquence majeure, démontrée par l'exercice** : une restauration logique fait `DROP TABLE`/
`DROP PROCEDURE` puis `CREATE`. Or les **privilèges d'objet** (table, colonne, routine) sont stockés dans
le schéma `mysql`, **indexés par l'objet**, et **disparaissent avec lui**. Après un import, les objets sont
là mais **les GRANT aux rôles ont été effacés** : l'application non-root est encore refusée. La reprise
n'est complète qu'après **réapplication de la couche de droits** depuis l'inventaire administratif
(fichiers `database/setup/*grants*.sql`, `app_roles.sql`…). Seuls les comptes/rôles et les privilèges
globaux survivent au `DROP`.

## 3. Scénario de perte et restauration (rejoué, 19 contrôles)

1. **Instance isolée neuve** (propriétaires verrouillés, données chiffrées, audit en ajout seul).
2. **Vérité terrain** : comptes de lignes, empreinte des colonnes chiffrées, **déchiffrement d'un
   document d'identité** via le code applicatif, nombre de lignes d'audit, ajout-seul vérifié.
3. **Sauvegarde** par `backup_ops`, puis **chiffrement** du dump ; clés conservées à part. Contrôle :
   sans la bonne clé de sauvegarde, la restauration est **refusée** (GCM).
4. **Perte contrôlée** : `DELETE FROM role_permissions` (perte d'enregistrements critiques pour le RBAC)
   **et** `DROP TABLE employee_personal_data` (suppression d'une table critique).
5. **Restauration** depuis la sauvegarde **chiffrée** (déchiffrement, puis import).
6. **Vérification d'intégrité** :
   - toutes les tables de retour, **comptes de lignes identiques** à l'avant-perte ;
   - colonnes chiffrées restaurées **octet pour octet** ;
   - données sensibles **toujours déchiffrables** (document d'identité identique à l'avant-perte) ;
   - piste d'audit **restaurée intégralement** et **toujours en ajout seul** (déclencheurs restaurés) ;
   - procédures et déclencheurs au compte d'inventaire (31 / 53) ;
   - schéma seul → lecture applicative **encore refusée**, puis **rétablie** après réapplication des droits.

C'est la démonstration exigée : non pas « un fichier existe », mais un système **remis en état de marche
vérifié**, données déchiffrables et contrôles de sécurité intacts.

## 4. Objectifs de reprise et limites

- **RPO** : dépend de la fréquence des sauvegardes (ici à la demande ; une planification hors fenêtre DDL
  est recommandée). **RTO** : dominé par l'import + la réapplication des droits, de l'ordre de la minute
  sur ce jeu de démonstration.
- `--single-transaction` ne protège **pas** contre un DDL concurrent : sauvegarder hors fenêtre de
  changement de schéma.
- Les sauvegardes de laboratoire sous `/tmp` ne sont **pas** une sauvegarde durable : une vraie
  exploitation copie la sauvegarde chiffrée et les clés sur des supports distincts et protégés, avec
  rétention datée.

## 5. Preuves et procédures

| Preuve / procédure | Où |
|---|---|
| Exercice complet rejouable (19 contrôles) | `tests/backup-recovery.py` |
| Lanceur de sauvegarde (compte dédié, manifeste SHA-256) | `bin/backup.py` |
| Chiffrement/déchiffrement authentifié de la sauvegarde | `bin/backup-crypt.py` |
| Procédure d'exploitation (sauvegarde, restauration d'essai, incident) | `docs/RECOVERY.md` |

## 6. Articulation avec les autres phases

La **phase 6** impose la gestion séparée des clés (sans elles, la restauration est illisible). La
**phase 7** fournit la piste d'audit dont l'exercice vérifie la restauration et l'inviolabilité. La
**phase 9 (durcissement)** couvrira la *protection des sauvegardes* dans son tableau avant/après
(chiffrement, permissions, séparation des clés — déjà en place ici). La **phase 10 (investigation)**
s'appuiera sur les sauvegardes et la piste d'audit pour la reconstruction après incident.
