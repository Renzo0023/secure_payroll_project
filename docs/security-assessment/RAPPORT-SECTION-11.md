# Database Security Assessment Report — Section 11 (phase 4)

> Section du livrable 3, numérotée selon le plan imposé : **11** Vulnerability Analysis.
> Annexe détaillée, charges complètes et reproduction : `08-ANALYSE-DE-VULNERABILITE.md`. Campagne : `lab/sqli-campaign.py`.

---

## 11. Analyse de vulnérabilité

### 11.1 Démarche

L'énoncé demande d'étudier un composant délibérément vulnérable, dans le laboratoire. Pour chaque vulnérabilité, l'analyse doit présenter la vulnérabilité, son impact, sa cause racine, sa correction et sa vérification.

Le projet a d'abord vérifié qu'aucune injection n'existait dans l'application.
- **Revue des requêtes.** Les 27 requêtes préparées et les 7 constructions dynamiques de texte SQL n'insèrent que des constantes ou des valeurs issues d'une liste fermée.
- **Procédures stockées.** Aucune n'emploie de SQL dynamique (§ 9 de l'annexe).

Un composant vulnérable a donc été **ajouté volontairement**, en reproduisant une erreur courante, puis confiné au laboratoire. Une étude purement théorique aurait moins de valeur qu'une attaque mesurée sur la vraie base.

### 11.2 Composant vulnérable et confinement

**La fonction « Mes accès »** (`/my-access`) permet à chaque utilisateur de consulter l'historique de ses propres rôles, filtré par une date de début. La page est ouverte à tous les rôles, donc au salarié, le moins privilégié : c'est le point d'entrée le plus défavorable.

**La variante vulnérable** (`lab/vulnerable/VulnerableAccessHistory.php`) concatène la date reçue dans le texte SQL et affiche les erreurs de MySQL. Elle ne s'active que si quatre conditions sont réunies : un drapeau explicite, le serveur intégré `php -S`, une instance jetable sous `/tmp/securepayroll-lab-*`, et la présence du fichier hors de `public/`.

**L'instance quotidienne ne peut jamais l'activer**, et la recette le prouve : elle lance volontairement l'application avec le drapeau, et le verrou le refuse. L'attaque vise une instance MySQL privée, sans réseau, ne contenant que des données fictives.

### 11.3 Analyse

| Rubrique | Constat |
|---|---|
| **Vulnérabilité** | **Injection SQL de type `UNION`** dans le paramètre `since` (CWE-89), aggravée par l'absence de validation serveur (CWE-20) et par l'affichage des erreurs du SGBD (CWE-209). |
| **Impact** | Un salarié authentifié lit des données hors de son périmètre : les **empreintes de mots de passe** des 6 comptes, les **salaires**, l'identité de tous les salariés, les attributions de rôles de tous les comptes et la structure de la base. Gravité estimée : CVSS 3.1 **6,5** dans l'état de la phase 1. |
| **Cause racine** | Code et données mélangés : la saisie fait partie du texte envoyé à MySQL, qui ne peut plus distinguer l'une de l'autre. S'y ajoutent la confiance dans le contrôle du navigateur et, en phase 1, un compte de service aux privilèges excessifs. |
| **Correction** | Requête préparée (la date devient une valeur liée), validation serveur stricte de la date, message d'erreur générique sans écho de la saisie. Le moindre privilège (phase 2) limite les conséquences d'une erreur résiduelle. |
| **Vérification** | Les mêmes charges, rejouées contre le code corrigé, sont toutes refusées (422), sans fuite ni message du SGBD (section 12). |

### 11.4 Déroulement de l'attaque

L'attaquant, connecté en salarié, modifie le paramètre `since` dans l'URL :
1. **Sonde.** Une apostrophe seule provoque une erreur affichée en clair, qui confirme l'injection et révèle la fin de la requête : `… near '''' ORDER BY ra.valid_from DESC'`.
2. **Ajustement.** La page montre quatre colonnes, d'où la forme du `UNION`. Le message d'erreur révèle aussi que la fin de la saisie est tronquée : l'attaquant termine alors ses charges par `-- -` au lieu de `-- `.
3. **Reconnaissance.** Il lit `information_schema.columns`, puis les tables qui l'intéressent.
4. **Exfiltration.** Il récupère les données par `UNION SELECT`.

```text
since = 2999-01-01' UNION SELECT login, password_hash, NULL, NULL FROM accounts -- -

Rôle            Début
hr.demo         $argon2id$v=19$m=65536,t=4,p=1$RmhvN3laL…
finance.demo    $argon2id$v=19$m=65536,t=4,p=1$WmdhbkRaW…
…               (6 comptes)
```

### 11.5 Résultats mesurés

Les mêmes 9 requêtes (une saisie légitime et 8 charges) sont rejouées automatiquement dans quatre configurations, en croisant le code (vulnérable ou corrigé) et les privilèges du service PHP :
- **phase 1** : les 34 `GRANT` directs historiques ;
- **phase 2** : les rôles MySQL.

| Données visées | A — vulnérable, phase 1 | B — vulnérable, rôles | D et C — corrigé |
|---|---|---|---|
| Empreintes de mots de passe | **Lues (6)** | Bloquées par MySQL (1143) | Refusé (422) |
| Salaires | **Lus** | Bloqués par MySQL (1142) | Refusé (422) |
| Identité des collègues | **Lue (5)** | **Lue (5)** | Refusé (422) |
| Rôles de tous les comptes | **Lus (6)** | **Lus (6)** | Refusé (422) |
| Structure de la base | **14 tables** | **6 tables** | Refusé (422) |
| RIB, CIN | Bloqués (1142) | Bloqués (1142) | Refusé (422) |
| Écriture par requête empilée | Bloquée (1064) | Bloquée (1064) | Refusé (422) |

Aucune donnée n'a été modifiée : l'empreinte de contrôle des tables est identique avant et après chaque scénario.

### 11.6 Enseignements

1. **La saisie légitime fonctionne dans les quatre cas.** Une vulnérabilité d'injection est invisible à l'usage normal ; seuls des tests ciblés la révèlent.
2. **Les défenses des phases précédentes ont limité les dégâts, sans les empêcher :**
   - **Données personnelles** : aucun privilège ne les rend lisibles par le service PHP (phase 1).
   - **Requêtes préparées natives** (`ATTR_EMULATE_PREPARES=false`) : elles interdisent les requêtes empilées, donc toute écriture.
   - **Rôles MySQL** (phase 2) : ils rendent les empreintes et les salaires inaccessibles, et réduisent la reconnaissance de 14 à 6 tables.
3. **Le moindre privilège ne remplace pas un code correct.** En configuration B, l'identité de tous les salariés et l'ensemble des attributions de rôles fuient encore, car le rôle de session doit lire ces tables. Seule la correction du code supprime la vulnérabilité.
4. **La divulgation d'erreurs a un coût concret.** L'attaquant a ajusté ses charges grâce aux messages de MySQL, par exemple la fin de requête tronquée et le conflit de collation. Un message générique l'aurait privé de ces indices.

Les mesures correctives et la preuve « avant / après » exigée par la phase 5 font l'objet de la section 12.
