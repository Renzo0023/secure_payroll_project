# Database Security Assessment Report — Section 8 (phase 3)

> Section du livrable 3, numérotée selon le plan imposé : **8** Authentication Design.
> Annexe détaillée et commandes de reproduction : `07-AUTHENTIFICATION.md`. Démonstration : `lab/password-storage-demo.php`.

---

## 8. Conception de l'authentification

### 8.1 Exigences et couverture

L'énoncé impose huit fonctions. Le tableau indique comment chacune est réalisée et la preuve qui l'établit.

| Exigence | Réalisation | Preuve |
|---|---|---|
| Comptes individuels | Une ligne `accounts` par compte, liée à une personne (`employees`) ; login unique ; aucun compte partagé entre utilisateurs | Contrainte `UNIQUE` ; 6 comptes de démonstration distincts |
| Connexion | `POST /login` protégé par jeton CSRF ; requête préparée | Recette : 6 connexions réelles |
| Stockage sécurisé | Seule l'empreinte est stockée ; elle n'est lisible que par le rôle MySQL `sp_login` | Section 10 ; refus 1143 en session ordinaire |
| Hachage des mots de passe | **Argon2id** (`m=65536, t=4, p=1`), sel aléatoire de 16 octets par mot de passe | Format vérifié à l'installation et à chaque connexion |
| Identification du rôle | Les rôles valides sont relus en base **à chaque requête** et activés côté MySQL (`SET ROLE`) | Recette : pages autorisées et refusées par rôle |
| Gestion de session | Cookie `HttpOnly`, `SameSite=Lax`, mode strict ; nouvel identifiant à la connexion ; expirations | `app/Security/Session.php` |
| Déconnexion | `POST /logout` protégé par CSRF ; session vidée et identifiant renouvelé | Recette |
| Échecs de connexion | Message générique ; limitation par compte et par adresse ; journalisation | Recette (5 contrôles HTTP) ; 75 contrôles unitaires |

### 8.2 Stockage des mots de passe : quatre approches comparées

L'énoncé demande d'expliquer la différence entre stockage en clair, chiffrement, hachage et hachage sécurisé. Le script `lab/password-storage-demo.php` applique les quatre approches aux mêmes mots de passe fictifs. Deux salariés, nadia et samir, y partagent volontairement le même mot de passe, et chaque approche est soumise à une attaque par dictionnaire.

| Approche | Principe | Ce qu'obtient un attaquant qui vole la table | Résultat de la démonstration |
|---|---|---|---|
| **En clair** | Le mot de passe est écrit tel quel | Tous les mots de passe, immédiatement | Lecture directe |
| **Chiffrement** (AES-256-GCM) | Transformation **réversible** avec une clé | Rien sans la clé ; **tout** avec la clé, qui réside sur le même serveur que l'application | Déchiffrement immédiat avec la clé |
| **Hachage simple** (SHA-256) | Fonction à sens unique, **rapide et déterministe** | Les mots de passe faibles, par dictionnaire ou par tables précalculées. Deux mots de passe identiques ont la même empreinte. | Empreintes de nadia et samir **identiques** ; mot de passe retrouvé en 0,01 ms |
| **Hachage salé** (SHA-256 + sel) | Sel aléatoire par mot de passe | Plus de tables précalculées ni de doublons visibles, mais chaque essai reste très rapide | Empreintes distinctes ; mot de passe retrouvé en 0,01 ms |
| **Hachage sécurisé** (Argon2id) | Salé, **lent** et **coûteux en mémoire**, paramétrable | Chaque essai coûte environ 0,37 s et 64 Mio de mémoire | Empreintes distinctes ; 3,9 s pour seulement 13 essais |

Le chiffrement est inadapté parce que le serveur n'a jamais besoin de **relire** un mot de passe. Il lui suffit de vérifier qu'un mot de passe saisi produit la même empreinte. Un chiffrement réversible crée donc une clé à protéger sans aucun bénéfice. Il convient en revanche aux données qu'il faut relire, comme le RIB (section 13).

La différence entre hachage salé et hachage sécurisé est une question de **coût par essai**, mesuré sur la machine de développement (PHP, un seul cœur) :

| Mesure | SHA-256 salé | Argon2id |
|---|---:|---:|
| Essais par seconde | ≈ 1 270 000 | ≈ 2,7 |
| Dictionnaire d'un million de mots | < 1 seconde | ≈ 4 jours |
| Dictionnaire d'un milliard de mots | ≈ 13 minutes | ≈ 12 ans |

Ces chiffres varient d'une exécution à l'autre ; le rapport, d'environ 500 000, est stable. Un attaquant équipé de GPU est beaucoup plus rapide contre SHA-256. Contre Argon2id, son gain est limité, car chaque essai mobilise 64 Mio de mémoire.

Le hachage sécurisé ne protège pas pour autant un mot de passe faible : dans la démonstration, « Soleil2026! » figure dans le dictionnaire et il est retrouvé. C'est pourquoi les mots de passe générés par l'installateur sont **aléatoires (24 octets, 32 caractères)**, et l'outil d'administration en impose au moins 12.

### 8.3 Parcours de connexion

```text
POST /login (jeton CSRF vérifié)
  │
  ├─ 1. Limiteur : adresse (≤ 30 / 15 min) puis identifiant (≤ 5 / 15 min)
  │      refusé → 429 + Retry-After: 900, événement auth.throttled (portée journalisée)
  │
  ├─ 2. SET ROLE 'sp_login' → SELECT id, password_hash … WHERE login = ?
  │      (compte actif et salarié non archivé) → SET ROLE DEFAULT
  │
  ├─ 3. password_verify() — toujours exécuté, avec une empreinte factice si le compte n'existe pas
  │
  ├─ échec → 401 « Identifiant ou mot de passe incorrect », événement auth.failed
  │          (adresse, compte visé s'il existe, jamais l'identifiant saisi)
  │
  └─ succès → nouvel identifiant de session, nouveau jeton CSRF ; échecs du compte remis à zéro ;
              événement auth.login ; redirection vers /dashboard
```

**Choix de conception :**
- **Aucune énumération des comptes.** La réponse est la même, mot pour mot, pour un identifiant inconnu, un mauvais mot de passe, un compte désactivé ou un salarié archivé. Le temps de réponse est aussi identique, car Argon2id est calculé dans tous les cas : 358 ms mesurées dans les deux situations. Le limiteur traite enfin les identifiants inexistants exactement comme les autres.
- **L'empreinte n'est lue qu'au moment de la connexion.** Le rôle `sp_login` est activé pour cette seule requête (section 10). Une injection SQL dans une autre page ne peut pas lire les empreintes.
- **L'algorithme est vérifié.** Une empreinte qui ne serait pas Argon2id (MD5 ou SHA-1 importé par erreur) est refusée, même si le mot de passe correspond.
- **Pas de mot de passe dans les traces.** Le paramètre est marqué `#[\SensitiveParameter]`, ce qui le masque dans les traces d'exception. L'identifiant saisi n'est jamais journalisé, car un utilisateur tape parfois son mot de passe dans le mauvais champ.

### 8.4 Gestion des échecs de connexion

**Défaut corrigé (menace T-18).** L'analyse de la phase 1 avait déduit du code un défaut que la phase 3 a confirmé puis corrigé. Le limiteur comptait les échecs **par adresse IP** seulement. Or, en déploiement local, tous les utilisateurs arrivent de `127.0.0.1`. Cinq mauvais mots de passe, saisis par n'importe qui, bloquaient donc **tous** les utilisateurs pendant 15 minutes, et ce blocage pouvait être renouvelé indéfiniment.

Le limiteur repose désormais sur deux compteurs indépendants :

| Compteur | Seuil | Menace traitée |
|---|---|---|
| Par identifiant saisi (insensible à la casse) | 5 tentatives / 15 min | Force brute sur un compte (T-01) |
| Par adresse | 30 tentatives / 15 min | Pulvérisation : un mot de passe courant essayé sur de nombreux comptes |

**Règles complémentaires :**
- Une connexion réussie remet à zéro les échecs **du compte** : seul le titulaire du mot de passe peut réussir. Les autres échecs de l'adresse restent comptés.
- Une tentative sur un compte déjà bloqué ne déclenche aucun calcul et ne consomme pas le quota de l'adresse.
- Une adresse plafonnée ne crée plus de fichier d'état, ce qui borne l'espace disque qu'un attaquant peut consommer.
- Les fichiers d'état portent l'empreinte SHA-256 de l'adresse ou de l'identifiant et ne contiennent que le compteur et l'échéance.

**Preuve HTTP** (recette `tests/local-install.py`, sur l'application réelle) :

| Étape | Attendu et obtenu |
|---|---|
| 5 mauvais mots de passe sur `employee.demo` | 5 × 401, message générique |
| 6ᵉ tentative avec le **bon** mot de passe | 429, `Retry-After: 900` : le compte est bloqué |
| Connexion de `hr.demo`, depuis la même adresse `127.0.0.1` | 303 : connectée (**T-18 corrigée**) |
| Journal | 5 `auth.failed` avec `ip` et `target_account_id`, puis `auth.throttled` avec `scope: account` |
| Journal | Ni l'identifiant saisi, ni le mot de passe essayé, ni aucun mot de passe réel |

**Journalisation (menace T-15).** `auth.failed` consigne désormais l'adresse et le compte visé, s'il existe. Une série d'échecs peut ainsi être attribuée et analysée (phase 9).

### 8.5 Gestion de session

| Mesure | Valeur | Menace traitée |
|---|---|---|
| Cookie `HttpOnly` | Illisible par JavaScript | Vol de session par XSS |
| `SameSite=Lax`, plus un jeton CSRF de 256 bits sur chaque `POST` | Formulaires non rejouables depuis un autre site | CSRF |
| `Secure` | Activé automatiquement sous HTTPS | Interception |
| Mode strict, cookies seuls, pas d'identifiant dans l'URL | Identifiant imposé refusé | Fixation de session |
| Nouvel identifiant à la connexion et à la déconnexion, et toutes les 15 minutes | Ancien identifiant invalidé | Fixation, réutilisation |
| Expiration après inactivité | 20 minutes | Poste laissé ouvert |
| Expiration absolue | 8 heures | Session volée réutilisée longtemps |
| Revalidation à chaque requête | Compte désactivé, salarié archivé ou rôle révoqué : effet **immédiat** | Révocation retardée |
| Stockage des sessions | Répertoire privé de l'instance (`0700`, propriétaire vérifié) | Lecture des sessions par un autre utilisateur du système |

La session ne contient que l'identifiant du compte, des horodatages, le jeton CSRF et la langue. Les rôles n'y figurent pas : ils sont relus en base à chaque requête. Modifier la session ne permet donc pas d'obtenir un rôle.

### 8.6 Authentification au niveau de la base

Les comptes MySQL suivent les mêmes principes (section 10).

- **Plugin d'authentification.** Les comptes utilisent `caching_sha2_password`, le plugin par défaut de MySQL 8.4, qui stocke une empreinte SHA-256 salée et itérée.
- **Aucun accès réseau.** Le serveur tourne en `--skip-networking` et n'est joignable que par un socket local.
- **Comptes propriétaires des procédures.** Ils sont verrouillés (`ACCOUNT LOCK`) : aucune connexion n'est possible avec eux.
- **Comptes humains** (`dba_ops`, `audit_ops`). Ils sont verrouillés pendant un jour après 5 échecs, et leur mot de passe expire tous les 90 jours.
- **Secrets générés.** Ils sont aléatoires, stockés en mode `0600` hors du dépôt, et affichés uniquement dans un terminal.

### 8.7 Limites résiduelles

| Limite | Conséquence | Traitement prévu |
|---|---|---|
| Un attaquant peut bloquer **un** compte ciblé pendant 15 minutes | Déni de service ciblé, renouvelable (risque T-18 résiduel Moyen) | Accepté : la protection contre la force brute est prioritaire ; tracé dans le journal |
| Pas d'authentification à deux facteurs | Un mot de passe volé suffit (T-03) | Recommandation (section 19), prioritaire pour Finance et l'administrateur |
| Pas de changement ni de réinitialisation du mot de passe dans l'application | Gestion par l'outil d'administration seulement | Recommandation ; nécessiterait un droit `UPDATE` limité à la seule colonne `password_hash` |
| Pas de rehachage automatique (`password_needs_rehash`) | Un durcissement futur des paramètres Argon2id ne s'appliquerait pas aux anciens mots de passe | Lié au point précédent |
| HTTP sans TLS dans le laboratoire local | Cookie sans `Secure` ; mot de passe en clair sur la boucle locale | Acceptable en local uniquement ; HTTPS obligatoire en déploiement (section 16) |
| Journal d'authentification modifiable par l'application (EI-11) | Les traces d'une attaque peuvent être effacées | Phase 7 (section 14) |
