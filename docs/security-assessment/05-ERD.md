# Phase 1 — Diagramme entité-association (ERD)

> Livrable de la phase 1 (« Entity Relationship Diagram », « Database schema »).
> Les diagrammes sont **générés à partir des migrations** par `bin/generate-erd.py`. Ils sont donc fidèles au schéma réellement installé par `bin/init-local.py`.

## 1. Fichiers

| Fichier | Contenu |
|---|---|
| [erd/ERD.md](erd/ERD.md) | **Tous les diagrammes**, affichés directement sur GitHub et dans l'aperçu Markdown de VS Code |
| [erd/ERD-00-GLOBAL.mmd](erd/ERD-00-GLOBAL.mmd) | Vue globale : 28 tables, clés primaires, 34 relations structurelles |
| [erd/ERD-01-IDENTITE-RBAC.mmd](erd/ERD-01-IDENTITE-RBAC.mmd) | Identité, données personnelles, comptes, invitations et RBAC (8 tables) |
| [erd/ERD-02-ORGANISATION-RH.mmd](erd/ERD-02-ORGANISATION-RH.mmd) | Départements, postes, affectations, contrats (4 tables) |
| [erd/ERD-03-REMUNERATION.mmd](erd/ERD-03-REMUNERATION.mmd) | Demandes, décisions, conditions salariales, historique (4 tables) |
| [erd/ERD-04-PAIE.mmd](erd/ERD-04-PAIE.mmd) | Périodes, éléments variables, calculs, bulletins, approbations (6 tables) |
| [erd/ERD-05-REGLEMENTS.mmd](erd/ERD-05-REGLEMENTS.mmd) | Corrections, restitutions, registre des paiements (5 tables) |
| [erd/ERD-06-AUDIT.mmd](erd/ERD-06-AUDIT.mmd) | Piste d'audit de sécurité en ajout seul, sans clé étrangère (1 table, phase 7) |
| [erd/RELATIONS.md](erd/RELATIONS.md) | Inventaire des **68 clés étrangères**, avec cardinalité et nature |
| [erd/images/](erd/images/) | Rendu de chaque diagramme en **SVG** (vectoriel) et en **PNG** (résolution ×2) pour le rapport PDF |

**Régénérer** après toute nouvelle migration :

```bash
python3 bin/generate-erd.py           # écrit docs/security-assessment/erd/
python3 bin/generate-erd.py --check   # échoue si l'ERD ne correspond plus aux migrations
```

Le générateur refuse de produire un ERD incohérent. Il vérifie :
- le nombre de tables (28) ;
- la présence d'une clé primaire dans chaque table ;
- l'existence de chaque table et colonne référencée par une clé étrangère ;
- le rattachement de chaque table à un domaine ;
- l'existence de chaque colonne marquée `RESTREINT`.

## 2. Lecture des diagrammes

| Notation | Signification |
|---|---|
| `PK` / `FK` / `UK` | Clé primaire / clé étrangère / membre d'une contrainte d'unicité |
| `"NULL"` | Colonne facultative ; sinon `NOT NULL` |
| `"RESTREINT"` | Donnée du niveau le plus sensible ([02-CLASSIFICATION-DES-DONNEES.md](02-CLASSIFICATION-DES-DONNEES.md)) |
| `"autre domaine"` | Table d'un autre domaine, réduite aux colonnes référencées |
| `A \|\|--o{ B` | Chaque B référence exactement un A ; un A a zéro, une ou plusieurs B |
| `A \|\|--o\| B` | Relation 1 à 0..1 : la clé étrangère de B contient une clé unique |
| `A \|o--o{ B` | La clé étrangère de B accepte NULL : la référence est facultative |

| `"calculée"` | Colonne générée par MySQL (`GENERATED ALWAYS … STORED`) |
| `"auteur → accounts"` | Clé étrangère de traçabilité, indiquée sans trait |

**Clés de traçabilité.** Les **33 clés étrangères de traçabilité** désignent l'auteur d'une action (`created_by`, `decided_by`, `actor_id`, `actor_employee_id`…). Elles relient presque chaque table à `accounts` et `employees`. Tracées, elles rendaient les diagrammes illisibles. Elles sont donc :
- signalées dans les vues par domaine par la mention `auteur → accounts` ou `auteur → employees` sur la colonne, sans trait ;
- omises de la vue globale ;
- toutes listées dans [erd/RELATIONS.md](erd/RELATIONS.md).

## 3. Structure du modèle

```text
employees ─1:0..1─ employee_personal_data          (données personnelles isolées)
    │ └─1:0..1─ accounts ─1:N─ role_assignments ─N:1─ roles ─1:N─ role_permissions ─N:1─ permissions
    ├─1:N─ employment_contracts ─1:N─ compensation_requests ─1:0..1─ compensation_decisions ─1:0..1─ salary_conditions
    ├─1:N─ employee_assignments ─N:1─ departments / positions
    └─1:N─ payroll_calculations ─N:1─ payroll_periods ─1:N─ payroll_inputs ─1:0..1─ payroll_input_decisions
              ├─1:N─ payslip_events            ├─1:0..1─ payroll_approvals
              ├─1:N─ payslip_corrections ─1:N─ correction_events
              ├─1:N─ recovery_requests ─1:N─ recovery_events
              └─1:N─ settlement_ledger ─0..1:0..1─ recovery_requests
```

`employees` est le pivot : chaque donnée métier se rattache à un salarié, ce qui permet le contrôle « ses propres données » (exigence EC-1).

## 4. Choix de conception liés à la sécurité

| Choix visible dans l'ERD | Rôle pour la sécurité | Exigence ou menace |
|---|---|---|
| `employee_personal_data` séparée d'`employees` (1:0..1) | Le compte de service lit `employees` mais n'a **aucun** droit sur les données personnelles | EC-3, T-10 |
| **Demande → décision → condition** dans trois tables distinctes | Une proposition ne devient jamais un salaire par simple changement d'état ; la décision appartient à une autre personne | EI-2, T-06 |
| **Événements en ajout seul** (`*_history`, `*_events`, `settlement_ledger`) au lieu de colonnes d'état modifiables | Historique immuable protégé par triggers ; chaque transition a son auteur et son heure | EI-3, EI-4, T-15 |
| **Double référence de l'auteur** : compte (`*_by`, `actor_id`) **et** personne (`*_employee_id`) | La séparation des tâches se vérifie au niveau de la personne, même si elle avait plusieurs comptes | EI-2 |
| **Clés étrangères composites** : `salary_conditions` → `compensation_decisions(request_id, id)` ; `payroll_approvals` → `payroll_calculations(id, period_id, employee_id)` | La base garantit qu'une condition reprend la **bonne** décision, et qu'une approbation vise le calcul du **bon** salarié et du **bon** mois | EI-1, T-06 |
| `payroll_approvals` en 1:0..1 avec `payroll_calculations`, unique par (période, salarié) | Un seul calcul approuvé par salarié et par mois | EI-5 |
| `settlement_ledger.recovery_id` unique | Une restitution ne peut être encaissée qu'une fois | EI-5 |
| Aucune cascade (`ON DELETE RESTRICT` implicite ou explicite) | Supprimer un parent ne peut pas effacer silencieusement un historique | ED-3 |

## 5. Remplacement des anciens diagrammes

Le présent ERD **remplace**, pour la phase 1 :
- les planches EA du rapport PDF (`docs/technical-documentation/DIAGRAMME-EA-01..05.svg`), qui n'avaient ni cardinalités ni marqueurs de clés, et dont certains traits traversaient des tables sans lien ;
- le fichier `docs/technical-documentation/ENTITE-ASSOCIATION.mmd` du 11 novembre, qui ignore la migration `012` et n'a pas de marqueurs PK/FK.

Sur deux relations, le générateur est aussi **plus précis** que l'ancien diagramme. `compensation_decisions → salary_conditions` et `payroll_calculations → payroll_approvals` y figuraient en 1:N. Ce sont en réalité des relations **1:0..1**, garanties par `uq_sc_request` et par la clé primaire `payroll_approvals.calculation_id`.

## 6. Images pour le rapport PDF

Les images de [erd/images/](erd/images/) sont prêtes à insérer :
- le **PNG** pour un traitement de texte ;
- le **SVG** pour LaTeX ou un export vectoriel.

Pour le rapport, nous recommandons la vue globale ([ERD-00-GLOBAL.png](erd/images/ERD-00-GLOBAL.png)) en pleine page, puis une vue par domaine dans chaque sous-section. Le format de la vue globale est vertical (environ 1 × 2), adapté à une page A4.

Chaque image a été contrôlée visuellement : aucune table ni libellé ne se chevauche, et les cardinalités et marqueurs sont lisibles.

**Régénérer les images** après `bin/generate-erd.py` (Google Chrome requis, Mermaid 10.9.1 téléchargé à part) :

```bash
curl -o /tmp/mermaid.min.js https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js
python3 bin/render-erd.py /tmp/mermaid.min.js
```

`generate-erd.py --check` ne contrôle que les sources `.mmd`, pas les images. Après une nouvelle migration, il faut donc relancer **les deux** scripts.
