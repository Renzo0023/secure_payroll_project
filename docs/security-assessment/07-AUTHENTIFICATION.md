# 07 — Authentification sécurisée (phase 3)

> Annexe de la section 8 du rapport (`RAPPORT-SECTION-08.md`). Ce document liste les preuves, les modifications de la phase 3 et les commandes pour les reproduire devant le jury.

## 1. Fichiers concernés

| Fichier | Rôle |
|---|---|
| `app/Auth/AuthService.php` | Vérification Argon2id, empreinte factice, relecture du compte et des rôles à chaque requête |
| `app/Security/Session.php` | Paramètres du cookie, rotation, expirations, jeton CSRF |
| `app/Security/LoginLimiter.php` | Limitation par identifiant (5) et par adresse (30) sur 15 minutes |
| `app/Database/SessionRoles.php` | Rôle `sp_login` pendant la seule lecture de l'empreinte |
| `app/Web/Controller.php` | `POST /login`, `POST /logout`, réponses 401 et 429, journalisation |
| `lab/password-storage-demo.php` | Démonstration : clair, chiffrement, hachage et hachage sécurisé |
| `tests/login-limiter.php` | 75 contrôles unitaires du limiteur |
| `tests/local-install.py` | Recette réelle (100 contrôles, dont connexions, verrouillage et journal) |

## 2. Modifications de la phase 3

| Avant | Après | Motif |
|---|---|---|
| Limiteur **par adresse IP seulement** (5 échecs / 15 min) | Par identifiant (5) **et** par adresse (30) | T-18 : en local, tout le monde partage `127.0.0.1` ; un tiers bloquait tous les utilisateurs |
| `auth.failed` sans contexte | `ip`, `target_account_id`, `known_account` ; nouvel événement `auth.throttled` avec `scope` | T-15 : rendre les échecs attribuables |
| Une réussite rendait seulement son propre crédit | Une réussite remet à zéro les échecs du compte | Un utilisateur légitime ne reste pas pénalisé par ses fautes de frappe |
| Aucune démonstration des quatre approches de stockage | `lab/password-storage-demo.php` | Exigence explicite de l'énoncé |
| — | Contrôle des plugins MySQL et du verrouillage des 5 comptes propriétaires | Prouver la section 8.6 |

Les fichiers d'état du limiteur sont désormais nommés `login-address-<sha256>.json` et `login-account-<sha256>.json`. Les anciens fichiers `login-<sha256>.json` sont simplement ignorés.

## 3. Démonstration du stockage des mots de passe

```bash
php lab/password-storage-demo.php
```

Le script fonctionne hors ligne, sans base de données, avec des mots de passe fictifs, et dure environ 15 secondes. Il affiche, pour les mêmes utilisateurs :
1. le stockage en clair ;
2. le chiffrement AES-256-GCM, avec un déchiffrement qui rend le mot de passe ;
3. SHA-256 sans sel : empreintes identiques pour nadia et samir ;
4. SHA-256 salé : empreintes distinctes ;
5. Argon2id, avec le détail du format `$argon2id$v=19$m=65536,t=4,p=1$<sel>$<empreinte>` ;
6. les débits mesurés et le temps d'attaque d'un dictionnaire.

Mesures d'une exécution (machine de développement, PHP, un seul cœur) : SHA-256 salé ≈ 1 270 000 essais/s, Argon2id ≈ 2,7 essais/s (≈ 370 ms par essai), soit un rapport d'environ 470 000.

## 4. Égalité des temps de réponse

Le temps de `password_verify` a été mesuré sur 5 essais : **358 ms** avec l'empreinte factice (identifiant inconnu) comme avec une empreinte réelle. Commande de vérification :

```bash
php -r '$d="\$argon2id\$v=19\$m=65536,t=4,p=1\$MTIzNDU2Nzg5MGFiY2RlZg\$phRfPWZoyG2Rva8DQN7nGkXzB0JRslvJM5t30pPJbF4";
$r=password_hash("x",PASSWORD_ARGON2ID);
foreach(["inconnu"=>$d,"existant"=>$r] as $k=>$h){$t=hrtime(true);for($i=0;$i<5;$i++)password_verify("faux",$h);
printf("%s %.0f ms\n",$k,(hrtime(true)-$t)/5e6);}'
```

## 5. Démonstration au jury

Sur l'instance locale (`python3 bin/init-local.py start`), avec un navigateur :

1. Connexion `employee.demo` avec un mauvais mot de passe : message « Identifiant ou mot de passe incorrect ».
2. Même message pour un identifiant inexistant (`personne.demo`).
3. Après 5 échecs sur `employee.demo` : « Trop de tentatives », même avec le bon mot de passe.
4. Dans un autre navigateur, depuis la même machine, `hr.demo` se connecte normalement.
5. Journal : `tail -n 8 .local/runtime/application.log`. Il montre les événements `auth.failed` (avec `ip` et `target_account_id`) et `auth.throttled`, sans identifiant saisi ni mot de passe.
6. Cookie de session, dans les outils de développement du navigateur : `HttpOnly`, `SameSite=Lax`.
7. Déconnexion : le bouton envoie un `POST /logout` ; le retour arrière ne rouvre pas la session.
8. Côté base, en tant que `root` : `SELECT login, LEFT(password_hash, 31) FROM secure_payroll.accounts;` montre les préfixes `$argon2id$v=19$m=65536,t=4,p=1$`.

Le compte `employee.demo` reste bloqué 15 minutes. Pour le débloquer plus tôt pendant une démonstration, supprimer les fichiers `.local/runtime/login-account-*.json`, après avoir vérifié leur nom avec `ls`.

## 6. Tests

```bash
php tests/login-limiter.php                          # 75 contrôles, sans base de données
PYTHONDONTWRITEBYTECODE=1 python3 tests/local-install.py   # 100 contrôles, instance neuve dans /tmp
```

Contrôles de la recette propres à la phase 3 :
- cinq échecs donnent cinq réponses 401 génériques ;
- le compte est ensuite verrouillé (429, `Retry-After: 900`), même avec le bon mot de passe ;
- un autre compte se connecte depuis la même adresse : **T-18 corrigée** ;
- les échecs sont journalisés avec l'adresse et le compte visé ;
- le journal ne contient ni l'identifiant saisi ni aucun mot de passe ;
- les comptes MySQL utilisent `caching_sha2_password`, et les 5 propriétaires sont verrouillés.

## 7. Lien avec les phases suivantes

- **Phase 4 (vulnérabilités).** Le formulaire de connexion n'est **pas** injectable : sa requête est préparée et l'empreinte n'est lisible que sous `sp_login`. La recherche de vulnérabilités devra le montrer, et le composant délibérément vulnérable sera placé ailleurs.
- **Embauche et changement de mot de passe** (document [09](09-EMBAUCHE-ET-ACTIVATION.md)). Les comptes sont créés par la RH avec un mot de passe temporaire de 72 h, dont le changement est obligatoire à la 1re connexion. Le changement de mot de passe, absent en phase 3, est désormais disponible pour tous (`/password`) : même limiteur, politique de 12 caractères minimum, autres sessions fermées.
- **Phase 9 (investigation).** Les événements `auth.failed` et `auth.throttled` permettent de reconstituer une attaque par force brute ou par pulvérisation : adresse, comptes visés, chronologie.
