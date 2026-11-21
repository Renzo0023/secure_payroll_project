# Campagne MySQL isolée — 6 novembre 2026

## Périmètre et conclusion

Les parcours existants RH → Finance → Paie → Bulletins ont été revalidés dans
une nouvelle instance MySQL 8.4.11 privée. Aucun compte, socket, port, paramètre
ou contenu de l’instance principale n’a été utilisé ou modifié. Aucun sudo,
effacement de données existantes ou publication GitHub n’a été effectué.

Les 216 contrôles réels ci-dessous ont réussi, ainsi que 413 contrôles hors
connexion. Cela valide les scénarios exercés dans le laboratoire, sans attester
l’installation principale ni constituer un audit exhaustif de l’application.

## Résultats de cette campagne

| Commande / test | Contrôles réussis | Objet |
|---|---:|---|
| `tests/payroll-mysql.php`, via `lab/mysql-validate.py` | 35 | Migrations 001–008, rémunérations MAD, paie, versions, décisions, publication, refus SQL |
| `tests/payroll-http-live.py`, même lanceur | 58 | Sept identités, six rôles, HTTP authentifié FR/EN, workflow complet, CSRF, IDOR, limiteur |
| `tests/payroll-races.py`, même lanceur | 18 | Concurrence réelle, plafonds, versions, approbation unique, privilèges et immutabilité |
| `lab/mysql-integrity.py --initialize-isolated` | 33 | Contraintes et triggers identité/RBAC, seed, révocations ; six tables vides après rollback |
| `lab/mysql-recovery.py --source-private-dir /tmp/securepayroll-mysql-9jt35599` | 32 | Export privé, empreintes, journaux, restauration distincte, totaux, routines, triggers et service non-root |
| `lab/mysql-security.py --source-private-dir /tmp/securepayroll-mysql-dote2lwx` | 18 | Refus métier, salaires absents/non approuvés, UM, net négatif, comptes et rôles invalides |
| `lab/mysql-attacks.py --source-private-dir /tmp/securepayroll-mysql-9jt35599` | 12 avant + 10 après | Six exercices pédagogiques dans un schéma distinct, aucune route vulnérable ajoutée |

Hors connexion : 93 contrôles SQL statiques, 45 rémunération, 17 calcul,
23 calendrier, 210 autorisation/validation/rendu, 18 limiteur et 7 configuration
socket/runtime. Syntaxe vérifiée sur 62 fichiers PHP et 16 scripts Python.

## Changements livrés

- Nouveau `lab/mysql-integrity.py` : crée une instance privée neuve, adapte le
  sélecteur de schéma d’une copie en mémoire de la migration 001, crée un compte
  non-root limité au schéma de test, lance les assertions existantes et vérifie
  les six tables vides après rollback. Résultat JSON conservé, arrêt SQL du serveur.
- Correction de `lab/mysql-recovery.py` : le lanceur cherchait uniquement
  `web-runtime`, alors que les tests HTTP créent `web-runtime-<identifiant>`.
  Il sélectionne désormais le runtime privé le plus récent contenant le journal
  applicatif et refuse l’absence de journal. Aucun repli sur les logs principaux.
  La correction a été validée par les 32 contrôles de restauration réels.
- Actualisation de `tests/INTEGRITY.md`, de l’aide du test PHP et du README du
  laboratoire pour distinguer les validations exécutées des préconditions historiques.

## Artefacts conservés et arrêt

- Instance fonctionnelle : `/tmp/securepayroll-mysql-9jt35599`.
- Instance restaurée : `/tmp/securepayroll-mysql-dote2lwx`.
- Instance intégrité : `/tmp/securepayroll-mysql-ngwaym9u`, avec `integrity-result.json`.
- Sauvegarde : `/tmp/securepayroll-mysql-9jt35599/backup-2dfbd4b9/securepayroll-20261106T154926Z-3cbcbaf8`.
- Résultats : `recovery-result.json` et `attack-result-9ca43709.json` dans
  l’instance fonctionnelle ; `security-result.json` dans l’instance restaurée.

Ces trois serveurs ont été arrêtés par SQL SHUTDOWN ; l’absence de leurs sockets
a été vérifiée en fin de campagne. Les données et journaux restent conservés.

Deux premiers essais confinés se sont bloqués pendant l’initialisation, avant
le chargement du schéma applicatif : `/tmp/securepayroll-mysql-l_f51ybd`
(mysqld PID 7426, parent Python 7367) et `/tmp/securepayroll-mysql-yhg_kc5p`
(mysqld PID 8023, parent Python 8022). À la dernière vérification, ils étaient
encore en attente. L’arrêt ciblé après vérification des arguments datadir a été
refusé avec `PermissionError: [Errno 13]`. Aucun contournement sudo n’a été tenté.
Ces PID sont des observations de session : vérifier les arguments et l’identité
des processus avant toute intervention ultérieure, car un PID peut être réutilisé.
Ils nécessitent une intervention de l’environnement hôte pour terminer leur cycle
de vie. Ne pas supprimer leurs répertoires pendant cette attente.

Les campagnes réussies ont ensuite été exécutées hors du confinement avec
autorisation d’exécution, comme utilisateur habituel, sans réseau MySQL.

## Base principale : aucune installation effectuée

Avant toute installation principale, suivre `PAYROLL-ACTIVATION.md` : inspection
de l’état réel et des droits, sauvegarde privée, application des seuls nouveaux
objets nécessaires, puis contrôles avec des comptes fictifs distincts. Ne pas
rejouer les migrations historiques ni recréer `finance.demo`. Les anciennes
confirmations utilisateur sur les tables ne remplacent pas cette inspection.

Restent à vérifier sur la principale : version MAD, routines de rémunération,
droits réels, activation des migrations 007/008 et parcours authentifiés après
installation. L’autorisation actuelle concerne le laboratoire ; aucune activation
principale n’a été déduite de celle-ci.

## Suite fonctionnelle

La campagne stabilise les modules déjà présents ; elle n’ajoute pas de paiement
fictif, de correction d’une paie approuvée ou de console IAM. Ces workflows ont
encore un périmètre à définir. Les plafonds restent explicites et leur politique
métier reste à confirmer. La phase d’attaque contrôlée peut s’appuyer sur ce
laboratoire et ses six exercices existants ; la préparation de l’installation
principale et le traitement des deux initialiseurs restent distincts.
