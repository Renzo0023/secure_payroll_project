# 08 — Analyse de vulnérabilité contrôlée (phase 4)

> Annexe des sections 11 et 12 du rapport. Ce document décrit le composant délibérément vulnérable, son confinement, l'attaque menée, ses résultats mesurés et les commandes de reproduction.
> Preuves : `lab/sqli-campaign.py` (26 contrôles avec `--sqlmap`), `tests/access-history-unit.php` (30 contrôles), `tests/local-install.py` (129 contrôles).
> Remédiation (phase 5), preuve « avant / après » et démonstration au navigateur : [`10-REMEDIATION-INJECTION.md`](10-REMEDIATION-INJECTION.md).

## 1. Composant étudié

**Fonction : « Mes accès »** (`GET /my-access`). Chaque utilisateur consulte l'historique des rôles attribués à **son** compte : début, expiration, révocation. Un champ date filtre les rôles attribués depuis une date donnée (`?since=AAAA-MM-JJ`).

Ce composant a été choisi pour trois raisons :
- **Il est ouvert à tous**, y compris au rôle le moins privilégié (Salarié). L'attaque part donc du point d'entrée le plus faible.
- **Sa fonction est légitime et plausible** : la transparence sur ses propres droits. Sa version corrigée fait désormais partie de l'application.
- **Le défaut est réaliste** : un champ `<input type="date">` donne l'illusion d'une saisie contrôlée, alors que le navigateur n'est pas une frontière de sécurité.

| Version | Fichier | Statut |
|---|---|---|
| Vulnérable (étudiée ici) | `lab/vulnerable/VulnerableAccessHistory.php` | Laboratoire uniquement, désactivée par défaut |
| Corrigée | `app/Access/AccessHistory.php` | En service dans l'application |

## 2. Confinement du composant vulnérable

L'énoncé exige que le composant reste dans le laboratoire. Le code vulnérable n'est chargé que si **toutes** les conditions suivantes sont réunies (`app/Security/LabMode.php`) :

| Condition | Effet |
|---|---|
| Variable `SECUREPAYROLL_LAB_VULNERABLE=access-history` | Désactivé par défaut |
| Serveur intégré de PHP (`php -S`) | Jamais sous un serveur web de production |
| Répertoire d'exécution sous `/tmp/securepayroll-lab-*` | Seulement dans une instance jetable créée par la campagne ; jamais `.local/` |
| Fichier présent dans `lab/vulnerable/`, hors de `public/` | Supprimer ce dossier suffit à retirer la vulnérabilité |

Des défenses supplémentaires protègent ce verrou :
- `bin/init-local.py` retire toute variable `SECUREPAYROLL_LAB_*` de l'environnement de l'application quotidienne.
- Le fichier vulnérable vérifie lui-même le verrou et s'arrête (404) s'il est chargé autrement.
- Un refus du verrou est journalisé (`lab.vulnerable_refused`).
- Toute page servie par le composant vulnérable affiche un bandeau « LABORATOIRE ».

**Preuves.** La recette lance volontairement l'instance de test **avec** le drapeau : le verrou le refuse, la page reste la version corrigée, et le refus est journalisé. Le test unitaire vérifie que le fichier ne se charge pas hors du verrou.

La base visée est une instance MySQL privée, sans réseau, créée pour la campagne, avec les seules données fictives du projet. Aucun système tiers n'est concerné.

## 3. Vulnérabilité

```php
// lab/vulnerable/VulnerableAccessHistory.php
$sql = "SELECT r.code, ra.valid_from, ra.expires_at, ra.revoked_at FROM role_assignments ra "
    . "JOIN roles r ON r.id = ra.role_id WHERE ra.account_id = " . $accountId
    . " AND ra.valid_from >= '" . $since . "' ORDER BY ra.valid_from DESC";
$db->query($sql);                              // la saisie fait partie du texte SQL
...
catch (PDOException $e) { return ['error' => $e->getMessage()]; }   // message du SGBD affiché
```

| Faiblesse | Référence | Description |
|---|---|---|
| **Injection SQL** | CWE-89 | La saisie est concaténée dans le texte de la requête. Une apostrophe ferme la chaîne SQL, et tout ce qui suit est interprété comme du SQL. |
| Absence de validation serveur | CWE-20 | Seul le navigateur impose un format de date. Modifier l'URL suffit à envoyer n'importe quel texte. |
| Divulgation d'erreurs | CWE-209 | Le message brut de MySQL est affiché. Il révèle la fin de la requête et guide l'attaquant. |

## 4. Attaque

L'attaquant est un salarié authentifié (`employee.demo`), donc le compte au **plus faible** privilège. Chaque charge est envoyée dans le paramètre `since` de l'URL.

| Réf. | Objectif | Charge (`since=`) |
|---|---|---|
| P0 | Usage normal | `2026-01-01` |
| P1 | Sonde | `'` |
| P2 | Tautologie | `2000-01-01' OR '1'='1` |
| P3 | Reconnaissance | `2999-01-01' UNION SELECT table_name, column_name, NULL, NULL FROM information_schema.columns WHERE table_schema = DATABASE() -- -` (avec conversion de collation) |
| P4 | Empreintes des mots de passe | `2999-01-01' UNION SELECT login, password_hash, NULL, NULL FROM accounts -- -` |
| P5 | Salaires | `2999-01-01' UNION SELECT e.employee_number, sc.monthly_amount, sc.effective_on, NULL FROM salary_conditions sc JOIN employees e ON e.id = sc.employee_id -- -` |
| P6 | Identité des collègues | `2999-01-01' UNION SELECT employee_number, CONCAT(first_name, ' ', last_name), NULL, NULL FROM employees -- -` |
| P7 | Données personnelles | `2999-01-01' UNION SELECT employee_id, rib, id_document_number, NULL FROM employee_personal_data -- -` |
| P8 | Écriture (requête empilée) | `2026-01-01'; UPDATE employees SET last_name = 'PIRATE' WHERE employee_number = 'EMP-2026-001'; -- -` |

**Comment l'attaquant progresse :**
1. **Il sonde le paramètre.** La sonde P1 provoque une erreur de syntaxe affichée en clair : `... near '''' ORDER BY ra.valid_from DESC'`. Elle confirme l'injection et révèle la fin de la requête.
2. **Il compte les colonnes.** Le tableau en affiche quatre : l'attaquant en déduit la forme de son `UNION`.
3. **Il adapte le commentaire de fin.** Une première version de nos charges, terminée par `-- `, échouait : le contrôleur applique `trim()`, qui supprime l'espace obligatoire après `--`. Le message d'erreur le révèle, et l'attaquant ajoute un caractère (`-- -`). C'est un exemple concret de l'aide que la divulgation d'erreurs (CWE-209) apporte à l'attaquant.
4. **Il aligne les collations** dans la charge P3 : `information_schema` n'utilise pas la même collation que les tables du projet, et `UNION` l'exige.

## 5. Impact mesuré

La campagne rejoue les mêmes charges en croisant le **code** (vulnérable ou corrigé) et les **privilèges MySQL** du service PHP. La phase 4 compare les quatre configurations ci-dessous ; la phase 5 en ajoute trois, qui isolent chaque contrôle de code ([section 10](10-REMEDIATION-INJECTION.md)).
- **Privilèges de la phase 1** : les 34 `GRANT` directs d'origine, rejoués depuis les fichiers `database/setup/*_grants.sql`.
- **Privilèges de la phase 2** : les rôles MySQL activés par requête.

Résultat de la dernière exécution (`python3 lab/sqli-campaign.py`) :

| Charge | **A** — vulnérable, phase 1 | **B** — vulnérable, rôles | **D** — corrigé, phase 1 | **C** — corrigé, rôles |
|---|---|---|---|---|
| P0 Saisie légitime | 1 ligne | 1 ligne | 1 ligne | 1 ligne |
| P1 Sonde | Erreur 1064 **affichée** | Erreur 1064 **affichée** | Refusé (422) | Refusé (422) |
| P2 Tautologie | **Fuite** : 6 attributions, tous comptes | **Fuite** : 6 attributions | Refusé (422) | Refusé (422) |
| P3 Reconnaissance | **Fuite** : 14 tables | **Fuite** : 6 tables | Refusé (422) | Refusé (422) |
| P4 Empreintes | **Fuite** : 6 empreintes Argon2id | Bloqué (1143) | Refusé (422) | Refusé (422) |
| P5 Salaires | **Fuite** : salaire de Nadia (12 000,00) | Bloqué (1142) | Refusé (422) | Refusé (422) |
| P6 Collègues | **Fuite** : 5 identités | **Fuite** : 5 identités | Refusé (422) | Refusé (422) |
| P7 RIB, CIN | Bloqué (1142) | Bloqué (1142) | Refusé (422) | Refusé (422) |
| P8 Écriture | Bloqué (1064) | Bloqué (1064) | Refusé (422) | Refusé (422) |

Aucune ligne de la base n'a été modifiée dans les quatre scénarios : une empreinte de contrôle (`CHECKSUM TABLE`) est comparée avant et après chacun.

**Interprétation :**
- **Avant toute correction (A)**, un simple salarié lit les empreintes Argon2id des 6 comptes et le salaire de ses collègues. Le jeu fictif ne contient qu'une condition salariale ; la requête renverrait toutes celles de la table. Les empreintes ne livrent pas directement les mots de passe : il faut ensuite une attaque par dictionnaire, lente contre Argon2id (section 8). Avec des mots de passe faibles, la compromission des comptes Finance ou Administrateur serait toutefois envisageable.
- **Les données personnelles (P7) étaient déjà protégées en phase 1** : aucun privilège ne les rend lisibles par le service PHP (section 6).
- **L'écriture (P8) échoue dans tous les cas.** Avec les requêtes préparées natives (`ATTR_EMULATE_PREPARES=false`), MySQL refuse plusieurs instructions dans un même envoi. Cette protection n'empêche pas pour autant la lecture par `UNION`.
- **Le moindre privilège seul (B) limite la fuite sans supprimer la vulnérabilité.** Empreintes et salaires sont refusés par MySQL, et la reconnaissance passe de 14 à 6 tables visibles. Mais l'identité de tous les collègues (Confidentiel) et l'ensemble des attributions de rôles restent lisibles, car le rôle `sp_session` en a besoin.

**Estimation de gravité (CVSS 3.1)** :

| Configuration | Vecteur | Score |
|---|---|---|
| A, état de la phase 1 | `AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N` | **6,5** (moyen, haut de fourchette) |
| B, rôles seuls | `C:L` au lieu de `C:H` | **4,3** |

Il s'agit d'une estimation : le contexte réel, un réseau interne, réduirait l'exposition.

## 6. Cause racine

La cause est un **mélange du code et des données**. La requête est construite comme un texte, dans lequel la saisie de l'utilisateur est insérée. MySQL reçoit donc un seul texte et ne peut pas distinguer ce que le développeur a écrit de ce que l'utilisateur a tapé.

Deux erreurs aggravent ce défaut :
- **Confiance dans le client** : le format de date imposé par le navigateur est pris pour une validation.
- **Privilèges excessifs** (configuration A) : le compte de service peut lire bien plus que ce dont la page a besoin. Une erreur locale devient ainsi une fuite globale.

## 7. Correction

La correction comporte trois contrôles indépendants, détaillés en section 12 (phase 5).

| Contrôle | Réalisation | Effet sur l'attaque |
|---|---|---|
| **Requête préparée** | Texte SQL constant ; la date est transmise **séparément**, comme une valeur liée (`ra.valid_from >= ?`) | La saisie ne peut plus jamais devenir du SQL |
| **Validation serveur** | Date réelle au format `AAAA-MM-JJ`, entre 1970 et 2100 (`AccessHistory::parseDate`) ; sinon réponse 422 | Toute charge est refusée avant d'atteindre la base |
| **Gestion d'erreur sûre** | Message générique, saisie refusée non réaffichée ; aucun message du SGBD dans la page | L'attaquant n'apprend rien de la structure |
| **Moindre privilège** (déjà en place, phase 2) | Rôles MySQL de l'utilisateur seulement | Limite les dégâts d'une éventuelle erreur future |

Le refus est journalisé (`input.rejected`), avec la longueur de la saisie et la présence de caractères SQL (`'`, `;`, `--`, `#`, `/*`). Le contenu de la saisie n'est pas journalisé. Ce signal servira à l'investigation de la phase 9.

## 8. Vérification

| Preuve | Résultat |
|---|---|
| Campagne, configurations C et D : 8 charges | Toutes refusées (422), sans message du SGBD ni fuite ; la saisie légitime fonctionne |
| Recette : injection P4 contre l'application réelle | 422, ni `$argon2id$`, ni `SQLSTATE`, ni écho de la saisie |
| Test unitaire : 14 saisies malveillantes ou mal formées | Toutes refusées par la validation |
| Test unitaire : code source | Texte SQL constant dans `prepare()`, saisie transmise par `execute()` |

Le détail du « avant / après » exigé par la phase 5 figure en section 12.

## 9. Revue du reste de l'application

L'application contient 27 appels à `prepare()`. Sept requêtes construisent du texte SQL dynamiquement ; aucune n'y insère une saisie :

| Endroit | Partie dynamique | Origine |
|---|---|---|
| `EmployeeRepository::listing` | Clause `WHERE` constante ; `OFFSET` | Recherche en paramètres liés, avec échappement de `%` et `_` ; `OFFSET` est un entier calculé |
| `CompensationRepository::contractedEmployees` | `OFFSET` | Entier calculé |
| `PeriodRepository::catalogue`, `projection` | Table et colonne | `match` sur une liste fermée ; colonne choisie entre `name_fr` et `name_en` |
| `CompensationRepository`, `Payroll\Repository`, `IAMRepository` (`call`) | Texte de la requête | Constantes `CALL procédure(?, …)` |
| `SessionRoles::set` | Noms de rôles | Liste fermée dans le code (section 10) |

Aucune des 27 définitions de procédures stockées n'emploie de SQL dynamique (`PREPARE … FROM`). Le seul SQL dynamique du dépôt se trouve dans un correctif d'administration (`database/patches/002_mad_schema_guarded.sql`) : son texte est constant, il n'est pas installé par `init-local.py` et il n'est accessible à aucun utilisateur.

**Conclusion** : hors du composant de laboratoire, aucune injection SQL n'a été identifiée dans le code de l'application. Il s'agit d'une revue manuelle, pas d'une preuve formelle.

## 10. Reproduction

Campagne complète, dans une nouvelle instance de laboratoire (environ 5 minutes) :

```bash
python3 lab/sqli-campaign.py
```

Le script affiche le tableau des sept scénarios et 23 contrôles `PASS`/`FAIL` (26 avec `--sqlmap`), puis enregistre le rapport détaillé dans `/tmp/securepayroll-lab-*/sqli-campaign.json` (mode 0600). Pour le rejouer sur la même instance :

```bash
python3 lab/sqli-campaign.py --instance /tmp/securepayroll-lab-XXXX/mysql
```

**Démonstration au jury, dans un navigateur :**

```bash
python3 lab/sqli-campaign.py --instance /tmp/securepayroll-lab-XXXX/mysql --serve A   # avant correction
```

1. Ouvrir http://127.0.0.1:8090/login et se connecter avec `employee.demo` ; le mot de passe de l'instance de laboratoire s'affiche dans le terminal.
2. Ouvrir « Mes accès », puis remplacer dans l'URL `since=…` par la charge P4 (encodée par le navigateur).
3. Constater que le tableau affiche les identifiants et les empreintes de mots de passe.
4. Arrêter avec Ctrl+C, puis relancer avec `--serve B` (moindre privilège seul), `--serve E/F/G` (un contrôle isolé) et `--serve C` (état final) pour comparer. Le guide complet est en [phase 5](10-REMEDIATION-INJECTION.md).
5. Arrêter MySQL : `python3 bin/init-local.py stop --directory /tmp/securepayroll-lab-XXXX/mysql`.

L'instance de laboratoire est indépendante de `.local/`. Les instances de laboratoire peuvent être supprimées une fois la démonstration terminée, après vérification de leur chemin.
