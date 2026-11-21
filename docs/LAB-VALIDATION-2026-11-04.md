# Validation réelle sur MySQL isolé — 4 novembre 2026

## Frontière vérifiée

L’utilisateur a autorisé explicitement les datadirs temporaires, comptes, GRANT,
migrations, données fictives et tests de ses instances privées. Aucune connexion
à l’instance MySQL principale n’a été utilisée dans ces validations.

Instance de référence : `/tmp/securepayroll-mysql-5g9p67gy/data`, socket privé
`/tmp/securepayroll-mysql-5g9p67gy/mysql.sock`, MySQL 8.4.11, `skip_networking=1`,
port MySQL 0 et plugin MySQL X désactivé. Les programmes vérifient le datadir avant
les écritures, utilisent `--no-defaults --no-login-paths --protocol=socket`, et
conservent les artefacts dans des répertoires privés 0700.

Les noms de comptes ressemblent à ceux du projet, mais ces comptes ont été créés
exclusivement dans le nouveau datadir. Les connexions applicatives utilisent le
nouveau svc_php privé ; root sert uniquement au bootstrap et à l’administration
du laboratoire par son socket. Les secrets sont aléatoires, transmis en mémoire,
sans fichier de mot de passe dans le projet ni argument de commande contenant un
secret. Les migrations historiques ont été appliquées une fois dans un datadir
neuf ; aucune migration installée dans la base principale n’a été rejouée.

La dernière validation HTTP complète utilise le datadir privé
`/tmp/securepayroll-mysql-1x6p6117/data`. Il a également passé les 35 contrôles SQL.
Les tests de concurrence, restauration et scénarios avant/après ci-dessous
référencent la première instance complète et sa copie restaurée.

## Résultats exécutés

| Exercice | Résultat | Portée |
|---|---|---|
| Migrations et procédures 001–008 | Appliquées dans le laboratoire | Syntaxe MySQL réelle et dépendances |
| `tests/payroll-mysql.php` | 35 contrôles réussis | RH → Finance en MAD, paie, primes/retenues/suspensions, versions, décisions/publication, refus SQL et IDOR |
| `tests/payroll-http-live.py` | 58 contrôles réussis au dernier passage | Sept identités couvrant les six rôles, workflow HTTP FR/EN, CSRF, IDOR entre deux employés et blocage après cinq échecs |
| `tests/payroll-races.py` | 18 contrôles réussis | Deux sessions observées en LOCK WAIT, plafonds cumulés, calculs sérialisés et approbation unique ; droits réels et immutabilité |
| `lab/mysql-recovery.py` | 32 contrôles réussis | Export avec compte dédié, empreintes, copie des logs, restauration distincte, comptes propriétaires, droits, lecture employé non-root et immutabilité |
| `lab/mysql-attacks.py` | 12 contrôles avant et 10 après réussis | Six scénarios pédagogiques sur un schéma distinct, aucune vulnérabilité ajoutée à l’application |
| `lab/mysql-security.py` | 18 contrôles réussis | Auto-approbation, salaire absent/en attente/rejeté, couverture de suspension, UM, net négatif, rôles incompatibles/futurs/révoqués et compte désactivé |

Le jeu de paie produit une base de 10400,00 MAD, un brut de 10700,00 MAD et un net
de 10600,00 MAD après deux jours non rémunérés, prime de 300,00 et retenue de 100,00.
Le résultat SQL est comparé au calculateur PHP indépendant. Les suspensions payées
ne réduisent pas la base. Avant publication, l’employé n’accède à aucune version ;
après publication, le second employé est refusé dans les deux sens.

La concurrence est exercée avec deux connexions réellement bloquées sur le verrou
parent, puis libérées : deux primes de 300,00 face à un plafond de 500,00 n’obtiennent
qu’une approbation ; les calculs simultanés conservent deux numéros de version uniques ;
les décisions Finance simultanées n’obtiennent qu’une approbation du mois.

Les refus d’UPDATE des historiques sont aussi vérifiés avec un compte administratif
du laboratoire, pour exercer les triggers, au-delà du simple refus de droit DML
par svc_php. Le propriétaire de paie est verrouillé et ses GRANT réels correspondent
à la liste exacte des colonnes/tables/procédures prévues.

## Récupération

Export privé :
`/tmp/securepayroll-mysql-5g9p67gy/backup-c3cc4771/securepayroll-20261104T161933Z-2e29ecdd`.
Destination de restauration : `/tmp/securepayroll-mysql-ymqcl2b_/data`.
Les comptes de lignes de chaque table, totaux financiers, nombres de routines et
triggers concordent. Le compte svc_php de restauration a été créé avec un nouveau
secret et les droits ont été réappliqués explicitement ; aucun compte de la base
principale n’est exporté ou réutilisé. Les logs et exports sont conservés.

Le résultat est enregistré dans
`/tmp/securepayroll-mysql-5g9p67gy/recovery-result.json`.
Le résultat des refus métier est dans
`/tmp/securepayroll-mysql-ymqcl2b_/security-result.json`.
Le résultat des scénarios avant/après est dans
`/tmp/securepayroll-mysql-5g9p67gy/attack-result-994d8f51.json`.

## Défauts rencontrés et corrections

- Les 35 tests SQL du premier passage avaient réussi, mais l’arrêt par signal du
  processus mysqld a été refusé par l’environnement. Le laboratoire utilise désormais
  `SHUTDOWN` via son seul socket privé, puis attend son propre processus. Les arrêts
  suivants ont réussi sans sudo ni modification système.
- Le limiteur de connexion comptait les authentifications réussies : la sixième
  identité depuis la même IP recevait un refus. Une connexion réussie libère
  maintenant uniquement sa réservation, sans effacer les autres échecs. Dix succès
  successifs et le maintien du seuil de cinq échecs sont vérifiés par 18 tests dédiés.
- La VM a présenté une charge élevée et un swap presque saturé pendant un
  passage complémentaire HTTP, interrompu par son délai de 15 secondes. Le délai
  de ce test a été porté à 60 secondes sans modifier les coûts Argon2id ni les
  contrôles applicatifs. Les 58 contrôles ont ensuite réussi sur le datadir déjà
  préparé, sans rejouer les migrations ni effacer les sessions/journaux précédents.
- Une extension des fixtures de sécurité utilisait `revoke_reason` au lieu de
  `revocation_reason`. La fixture a été corrigée, le rôle de test temporaire a été
  révoqué en conservant son historique, puis les 18 contrôles ont réussi sur la
  copie restaurée. Les migrations et procédures applicatives n’étaient pas en cause.

Pour tester le véritable point d’entrée PHP sans réseau MySQL, `DB_SOCKET` est
maintenant une option explicite validée. Sans cette variable, le fonctionnement
TCP existant est conservé. `APP_RUNTIME_DIR` isole sessions, logs et limiteur dans
un répertoire privé pour les tests ; aucun compteur ou journal de l’application
principale n’est effacé ni utilisé pour les connexions du laboratoire.

## Limites et suite principale

Ces succès concernent exclusivement le laboratoire. Les quatre tables de
rémunération et finance.demo sont confirmés dans la base principale par l’utilisateur ;
son parcours RH → Finance, ses droits réels et sa version MAD restent à contrôler
avec son environnement privé. Les migrations 007/008 et les nouveaux GRANT ne sont
pas appliqués sur la base principale. Leur installation nécessite toujours une
validation administrative distincte.

Les plafonds mensuels sont explicites et sans défaut : aucun barème chiffré validé
n’a été retrouvé. Le choix organisationnel conservateur reste à confirmer. Aucun
paiement fictif ni workflow de correction d’une paie déjà approuvée n’est livré.
Le rôle administrateur dispose de son authentification/profil existants ; aucune
nouvelle console IAM n’est développée. Les tests ne constituent pas un audit
exhaustif ou une garantie contre une compromission du serveur applicatif/DBA.
