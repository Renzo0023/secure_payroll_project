# Database Security Assessment Report — Section 12 (phase 5)

> Section du livrable 3, numérotée selon le plan imposé : **12** SQL Injection Investigation and Remediation.
> Annexe détaillée et guide de démonstration : [`10-REMEDIATION-INJECTION.md`](10-REMEDIATION-INJECTION.md).
> Analyse de la vulnérabilité (phase 4) : section 11. Campagne : `lab/sqli-campaign.py`.

---

## 12. Investigation et remédiation de l'injection SQL

### 12.1 Mécanismes défensifs mis en place

L'énoncé liste cinq mécanismes attendus. Tous sont en place :

| Mécanisme | Réalisation |
|---|---|
| **Prepared statements** | `app/Access/AccessHistory.php` : `prepare()` à texte constant, `execute([$accountId, $date])` ; préparations natives du serveur (`ATTR_EMULATE_PREPARES=false`) |
| **Parameterized queries** | La date voyage comme **valeur liée** (`WHERE ra.valid_from >= ?`), hors du texte SQL |
| **Server-side input validation** | `AccessHistory::parseDate` : liste blanche `AAAA-MM-JJ` + `checkdate`, 1970-2100 ; sinon HTTP 422 |
| **Secure error handling** | Message générique, saisie refusée non réaffichée, aucun message du SGBD ni détail du pilote dans la page ou le journal ; `MYSQL_ATTR_MULTI_STATEMENTS=false` |
| **Least-privileged application accounts** | Rôles MySQL de la phase 2 (section 10) : le service ne lit ni empreintes, ni salaires, ni données personnelles |

### 12.2 Preuve « avant / après » sur la même attaque

Les mêmes huit charges (et une saisie légitime) sont rejouées automatiquement, avant et après correction, dans
`lab/sqli-campaign.py`. Extrait du tableau complet (section 10, § 2) :

| Charge | A — avant correction | C — après correction |
|---|---|---|
| Sonde `'` | Message SQL brut (1064) | Refusé 422, message neutre |
| Tautologie `OR '1'='1` | Rôles de tous les comptes | Refusé 422 |
| Reconnaissance (`information_schema`) | 14 tables révélées | Refusé 422 |
| Empreintes (`UNION … accounts`) | 6 empreintes `$argon2id$` | Refusé 422 |
| Salaires (`UNION … salary_conditions`) | Salaire exfiltré | Refusé 422 |
| Identité des collègues (`UNION … employees`) | 5 identités | Refusé 422 |
| Écriture empilée (`UPDATE … 'PIRATE'`) | Bloquée (1064, préparation native) | Refusé 422 |

**Preuve outillée.** `sqlmap`, lancé à l'identique sur A puis C :
- **A** : paramètre `since` injectable, quatre techniques (*boolean-based, error-based, time-based, UNION*), compte
  `svc_php@localhost` et base `secure_payroll` extraits ;
- **C** : « all tested parameters do not appear to be injectable ».

Aucune donnée n'est modifiée dans aucun scénario (empreinte `CHECKSUM TABLE` identique avant/après).

### 12.3 Pourquoi chaque contrôle empêche la vulnérabilité

La campagne isole chaque contrôle (configurations E, F, G, B) pour répondre précisément à cette exigence.

1. **Requête préparée / paramétrée (E).** La base reçoit le texte de la requête et les valeurs **séparément**. La
   saisie est traitée comme une donnée et n'est jamais analysée comme du SQL : apostrophe, `UNION` ou `OR '1'='1'` ne
   sont plus que des caractères d'une chaîne cherchée littéralement. Mesure : **les huit charges ne produisent aucune
   fuite ni aucune erreur de syntaxe.** *C'est le seul contrôle qui supprime la cause racine (mélange code/données).*

2. **Validation serveur (F).** Toute saisie qui n'est pas une date réelle `AAAA-MM-JJ` est **rejetée avant d'atteindre
   la base** (HTTP 422). Mesure : les huit charges sont refusées. *Défense en profondeur : même si une requête
   redevenait concaténée, la charge n'arriverait jamais au SQL.*

3. **Gestion d'erreur sûre (G).** Mesure : plus aucun message du SGBD, **mais empreintes et salaires fuient encore**.
   *Masquer les erreurs prive l'attaquant d'indices (il avait, en A, ajusté ses charges grâce à la fin de requête
   tronquée et au conflit de collation révélés par MySQL) ; cela ralentit l'attaque sans la supprimer.*

4. **Moindre privilège (B).** Mesure : empreintes et salaires bloqués par MySQL (1143/1142), reconnaissance réduite de
   14 à 6 tables, **mais identité des collègues et rôles de tous les comptes encore exfiltrés**. *Le rôle de session
   doit lire `employees`, `roles` et `role_assignments` ; le moindre privilège borne l'impact d'une faille, il ne la
   corrige pas.*

**Conclusion.** Paramétrage et validation agissent sur la cause et sur l'arrivée de la charge : ils **suppriment ou
arrêtent** l'attaque. Gestion d'erreur et moindre privilège agissent sur l'information divulguée et sur l'étendue de
l'accès : ils **réduisent** le risque. La combinaison des quatre, en configuration C, rend l'attaque inexploitable.

### 12.4 Généralisation à toute l'application

Au-delà du composant d'étude, un garde-fou statique (`tests/secure-coding-static.php`) analyse tout `app/` et
`public/` et échoue à chaque régression : SQL non littéral non revu, donnée HTTP dans une requête, message d'exception
ou trace exposés, options PDO affaiblies. Les 37 appels SQL de l'application sont ainsi tenus hors de portée d'une
injection (19 littéraux, 18 constructions dynamiques revues sans saisie). Vérifié par mutation : une concaténation de
`$_GET` et un `getMessage()` affiché sont détectés.

### 12.5 Vérification

| Preuve | Résultat |
|---|---|
| Campagne, 7 configurations × 9 requêtes + `sqlmap` | **26 contrôles `PASS`** |
| `sqlmap` sur A puis C | Injectable (4 techniques) → non injectable |
| Garde-fou de codage sécurisé | 13 contrôles, 36 appels SQL sûrs |
| Test unitaire « Mes accès » et verrou de laboratoire | 30 contrôles |
| Recette HTTP, injection réelle | 422, ni `$argon2id$`, ni `SQLSTATE`, ni écho de la saisie |
