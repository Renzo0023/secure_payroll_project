# 10 — Remédiation de l'injection SQL et codage sécurisé (phase 5)

Suite de la phase 4 ([08-ANALYSE-DE-VULNERABILITE.md](08-ANALYSE-DE-VULNERABILITE.md)). La phase 4 a démontré la
vulnérabilité ; la phase 5 la corrige et prouve, **sur la même attaque**, qu'elle n'est plus exploitable.

L'énoncé impose la preuve suivante : « Before Remediation; Attack/Test → Vulnerability successfully demonstrated;
After Remediation; Same Test → Vulnerability no longer exploitable », puis l'explication de **pourquoi** chaque
contrôle empêche la vulnérabilité.

## 1. Les quatre contrôles et pourquoi ils fonctionnent

| Contrôle | Réalisation | Pourquoi l'attaque échoue |
|---|---|---|
| **Requête préparée / paramétrée** | `app/Access/AccessHistory.php` : texte SQL constant, la date voyage comme valeur liée (`WHERE ra.valid_from >= ?`), préparations natives (`ATTR_EMULATE_PREPARES=false`) | La base reçoit **le texte de la requête et les valeurs séparément**. La saisie est traitée comme une donnée, jamais analysée comme du SQL : une apostrophe ou un `UNION` ne sont plus que des caractères d'une chaîne. C'est le seul contrôle qui **supprime** la faille. |
| **Validation serveur** | `AccessHistory::parseDate` : liste blanche `^\d{4}-\d{2}-\d{2}$` + `checkdate`, années 1970-2100 ; sinon réponse 422 | Toute saisie qui n'est pas une date réelle est **rejetée avant d'atteindre la base**. Défense en profondeur : même si une requête redevenait concaténée, la charge n'arriverait jamais jusqu'au SQL. |
| **Gestion d'erreur sûre** | Message générique, saisie refusée non réaffichée, aucun message du SGBD, aucune donnée du pilote dans le journal | L'attaquant **n'apprend rien** de la structure de la requête ni du schéma. Seul : il ralentit l'attaque sans la bloquer (voir scénario G). |
| **Moindre privilège** | Rôles MySQL de la phase 2 ; le compte de service ne lit ni empreintes, ni salaires, ni données personnelles | **Réduit l'impact** d'une éventuelle faille future, sans la supprimer : les tables que le rôle doit lire restent exposées si le code est vulnérable (scénario B). |

Point clé pour le rapport : **paramétrage et validation agissent avant/pendant la requête et suppriment ou arrêtent
l'attaque ; gestion d'erreur et moindre privilège ne font que réduire l'information et l'impact.** La campagne le
démontre en isolant chaque contrôle.

## 2. Preuve « avant / après » automatisée

`lab/sqli-campaign.py` rejoue **une saisie légitime et huit charges** dans sept configurations, chacune servie par
`php -S` sur une instance jetable `/tmp/securepayroll-lab-*`, avec le compte le moins privilégié `employee.demo`.

| Clé | Code | Privilèges | Ce qu'on isole |
|---|---|---|---|
| **A** | vulnérable (aucune défense) | phase 1 (34 GRANT directs) | état d'avant toute correction |
| **E** | requête préparée seule | phase 1 | effet du paramétrage seul |
| **F** | validation seule | phase 1 | effet de la validation seule |
| **G** | erreurs génériques seules | phase 1 | effet du masquage d'erreur seul |
| **B** | vulnérable | rôles (phase 2) | effet du moindre privilège seul |
| **D** | corrigé (3 contrôles) | phase 1 | effet du code corrigé seul |
| **C** | corrigé | rôles | **état final** |

### Résultats mesurés (26 contrôles `PASS`, `sqlmap` compris)

| Charge | A avant | E préparée | F validation | G err. génér. | B moindre priv. | C/D corrigé |
|---|---|---|---|---|---|---|
| P0 saisie légitime | 1 ligne | 1 ligne | 1 ligne | 1 ligne | 1 ligne | 1 ligne |
| P1 sonde `'` | **erreur 1064 brute** | 0 ligne | refusé 422 | erreur générique | erreur 1064 | refusé 422 |
| P2 tautologie | **rôles d'autrui** | 1 ligne | refusé 422 | **rôles d'autrui** | **rôles d'autrui** | refusé 422 |
| P3 reconnaissance | **14 tables** | 0 ligne | refusé 422 | **14 tables** | **6 tables** | refusé 422 |
| P4 empreintes | **6 empreintes** | 0 ligne | refusé 422 | **6 empreintes** | bloqué 1143 | refusé 422 |
| P5 salaires | **salaires** | 0 ligne | refusé 422 | **salaires** | bloqué 1142 | refusé 422 |
| P6 collègues | **5 identités** | 0 ligne | refusé 422 | **5 identités** | **5 identités** | refusé 422 |
| P7 RIB/CIN | bloqué 1142 | 0 ligne | refusé 422 | erreur générique | bloqué 1142 | refusé 422 |
| P8 écriture empilée | bloqué 1064 | 1 ligne | refusé 422 | erreur générique | bloqué 1064 | refusé 422 |

Lecture : **E et F neutralisent toutes les charges ; G laisse fuir empreintes et salaires** (le masquage d'erreur ne
corrige rien) ; **B limite sans supprimer** (collègues et rôles fuient encore). Aucune donnée n'est modifiée dans les
sept scénarios (empreinte `CHECKSUM TABLE` identique avant/après).

### Preuve outillée : `sqlmap`

Même outil, même cible, même paramètre `since`, seule la configuration change :

- **sur A** : `since` jugé injectable, quatre techniques confirmées — *boolean-based blind, error-based, time-based
  blind, UNION query* — et `sqlmap` obtient `current user: svc_php@localhost`, `current database: secure_payroll` ;
- **sur C** : « all tested parameters do not appear to be injectable » ; les 35 charges reçoivent un 422.

Journaux : `/tmp/securepayroll-lab-*/sqlmap-A.txt` et `sqlmap-C.txt` (cookie de session masqué).

## 3. Démonstration au navigateur, scénario par scénario

### 3.1 Lancer un scénario

```bash
# Première fois : créer une instance de laboratoire et la laisser en place
python3 lab/sqli-campaign.py --instance /tmp/securepayroll-lab-XXXX/mysql --serve A
# (si vous n'avez pas encore d'instance : lancez d'abord `python3 lab/sqli-campaign.py` une fois,
#  elle en crée une sous /tmp/securepayroll-lab-* et affiche son chemin, puis réutilisez-le ici.)
```

La commande affiche l'URL (`http://127.0.0.1:8090/login`) et le mot de passe de `employee.demo` de cette instance.
Changez la lettre après `--serve` pour changer de scénario : **A, E, F, G, B, D, C**. `Ctrl+C` arrête le serveur PHP ;
MySQL reste actif pour le scénario suivant.

### 3.2 Se connecter et ouvrir la page

1. Ouvrir `http://127.0.0.1:8090/login`, se connecter avec `employee.demo` et le mot de passe affiché.
2. Menu **« Mes accès »** (`/my-access`). En configuration vulnérable, un **bandeau rouge « LABORATOIRE »** indique
   la variante active (`vulnerable`, `prepared-only`, `validation-only`, `generic-errors`). En C/D, pas de bandeau.
3. Les charges se déposent dans l'URL : `http://127.0.0.1:8090/my-access?since=<CHARGE>`. Le navigateur encode les
   espaces et apostrophes automatiquement ; on peut aussi taper la charge dans le champ date (il n'est pas bridé en
   mode vulnérable). Les charges finissent par `-- -` : le `--` commente la fin de la requête d'origine, et le `-`
   final empêche le `trim()` du contrôleur de supprimer l'espace obligatoire après `--`.

### 3.3 Les charges et ce qu'on observe

| # | But | `since=` | Sur A (avant) | Sur C (après) |
|---|---|---|---|---|
| P0 | Référence | `2026-01-01` | Une ligne : vos propres rôles | Identique |
| P1 | Sonder | `'` | Message **« SQLSTATE[42000]… 1064 … near … »** : la requête est révélée | Alerte neutre, HTTP 422 |
| P2 | Tautologie | `2000-01-01' OR '1'='1` | Le tableau liste les rôles de **tous** les comptes | 422, rien |
| P3 | Cartographier | `2999-01-01' UNION SELECT table_name, column_name, NULL, NULL FROM information_schema.columns WHERE table_schema = DATABASE() -- -` | **14 tables** et leurs colonnes s'affichent | 422, rien |
| P4 | Voler les mots de passe | `2999-01-01' UNION SELECT login, password_hash, NULL, NULL FROM accounts -- -` | Les 6 identifiants et leurs **empreintes `$argon2id$…`** | 422, rien |
| P5 | Voler les salaires | `2999-01-01' UNION SELECT e.employee_number, sc.monthly_amount, sc.effective_on, NULL FROM salary_conditions sc JOIN employees e ON e.id = sc.employee_id -- -` | Le salaire de Nadia (12000.00) apparaît | 422, rien |
| P6 | Identifier les collègues | `2999-01-01' UNION SELECT employee_number, CONCAT(first_name,' ',last_name), NULL, NULL FROM employees -- -` | Les 5 autres salariés | 422, rien |
| P7 | Données personnelles | `2999-01-01' UNION SELECT employee_id, rib, id_document_number, NULL FROM employee_personal_data -- -` | **Bloqué même sur A** : MySQL refuse (1142), aucun rôle ne lit cette table | 422, rien |
| P8 | Modifier des données | `2026-01-01'; UPDATE employees SET last_name='PIRATE' WHERE employee_number='EMP-2026-001'; -- -` | **Bloqué** : requête empilée refusée (1064, préparation native) | 422, rien |

> Observation pédagogique : P0 (saisie normale) fonctionne **à l'identique** dans tous les scénarios. Une faille
> d'injection est invisible à l'usage ordinaire — seule une charge ciblée la révèle.

### 3.4 Comparer les contrôles isolés

Rejouer **P4** (ou P2) après `--serve <lettre>` :

- **E (`prepared-only`)** : le tableau reste vide, aucune erreur. La valeur `2999-01-01' UNION…` est cherchée
  littéralement comme une date de début ; aucune ligne n'a cette date. **Le paramétrage seul suffit.**
- **F (`validation-only`)** : alerte neutre, HTTP 422. La charge n'a pas le format `AAAA-MM-JJ`, elle est rejetée
  avant la base.
- **G (`generic-errors`)** : plus de message MySQL (P1 donne « Une erreur est survenue »), **mais P4 affiche encore
  les empreintes**. Masquer les erreurs gêne l'attaquant sans le stopper.
- **B (`vulnerable` + rôles)** : P4 et P5 sont bloquées par MySQL (1143/1142), **mais P2 et P6 fuient toujours** : le
  rôle de session doit lire `roles`, `role_assignments` et `employees`. Le moindre privilège limite, ne corrige pas.
- **C / D** : tout est refusé (422). État final.

### 3.5 Vérifier qu'aucune donnée n'a bougé

Après P8, en C/D l'écriture est refusée ; même sur A elle est bloquée par la préparation native. Pour le confirmer en
base, depuis un autre terminal :

```bash
python3 bin/init-local.py --directory /tmp/securepayroll-lab-XXXX/mysql status   # ou via mysql --socket=…
# SELECT employee_number, last_name FROM secure_payroll.employees WHERE employee_number='EMP-2026-001';
```

Le nom reste `TRAORE`. La campagne le vérifie automatiquement par `CHECKSUM TABLE` avant/après chaque scénario.

## 4. Codage sécurisé dans tout le reste de l'application

La correction ne se limite pas à « Mes accès ». Un garde-fou statique, **`tests/secure-coding-static.php`** (13
contrôles, sans connexion), analyse lexicalement tout `app/` et `public/` et échoue si une régression apparaît :

1. chaque `->query/exec/prepare()` reçoit du SQL **entièrement littéral**, ou une construction dynamique **revue et
   justifiée** dans le test (table issue d'une liste fermée, `OFFSET` entier, `CALL …(?)` constant) ;
2. **aucune** donnée de requête HTTP (`$_GET`, `$_POST`, `$_COOKIE`, `$_REQUEST`, `$_SERVER`, `$_FILES`) dans un
   argument SQL ;
3. **aucun** message d'exception ni trace (`getMessage`, `getTraceAsString`, `var_dump`…) ; le texte `SIGNAL` des
   procédures (`errorInfo[2]`) n'est lu que par cinq contrôleurs revus, qui le comparent à des codes fixes sans jamais
   l'afficher ni le journaliser ;
4. pilote PDO : `EMULATE_PREPARES=false`, `ERRMODE_EXCEPTION`, `MYSQL_ATTR_MULTI_STATEMENTS=false` (une seule
   instruction par appel) ; `display_errors` désactivé ;
5. le composant vulnérable n'est référencé que par le verrou (`LabMode`) et le contrôleur.

Vérification du garde-fou lui-même : une requête concaténant `$_GET` et un `getMessage()` affiché, injectés dans une
copie du code, sont bien détectés (test de mutation hors dépôt).

## 5. Reproduction

```bash
python3 lab/sqli-campaign.py            # 7 scénarios, ~6 min, 23 contrôles
python3 lab/sqli-campaign.py --sqlmap   # + sqlmap sur A et C, ~+5 min, 26 contrôles
php    tests/secure-coding-static.php    # garde-fou statique, sans base
php    tests/access-history-unit.php     # 30 contrôles : validation, verrou, variantes
```

Rapport détaillé (JSON, mode 0600) : `/tmp/securepayroll-lab-*/sqli-campaign.json`. Les instances de laboratoire sont
indépendantes de `.local/` et peuvent être supprimées après vérification de leur chemin.
