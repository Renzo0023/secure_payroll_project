# Phase 1 — Classification des données

> Livrable de la phase 1 (« Sensitive information », « Data classification table »).
> Périmètre : les **26 tables** de `secure_payroll` (migrations `001` à `012`) et les actifs hors base de [01-INVENTAIRE-DES-ACTIFS.md](01-INVENTAIRE-DES-ACTIFS.md).
> La colonne « Exposition actuelle » décrit l'état réel des `GRANT` versionnés dans `database/setup/`. Elle ne décrit pas un état souhaité.

## 1. Référentiel

Les salariés étant au Maroc et la paie en MAD, le cadre de référence est la **loi n° 09-08** relative à la protection des personnes physiques à l'égard du traitement des données à caractère personnel, sous le contrôle de la **CNDP**.

- Presque toutes les données de la base sont des **données à caractère personnel** : elles se rapportent à un salarié identifié ou identifiable.
- **Aucune donnée « sensible » au sens de la loi** (origine, opinions, convictions, appartenance syndicale, santé) n'est collectée. C'est un choix de **minimisation** fait dans la migration `012`. Il impose une règle sur les champs libres (§ 3, règle R4).

## 2. Niveaux de classification

| Niveau | Critère | Conséquence d'une divulgation | Exemples dans SecurePayroll |
|---|---|---|---|
| **Public** | Information destinée à être publiée | Aucune | Aucune donnée de la base. Seuls les fichiers de `public/assets/` et les libellés de `lang/` sont publics. |
| **Interne** | Réservé au personnel authentifié ; ne concerne pas un individu | Faible : aide un attaquant à comprendre l'organisation | Référentiels départements et postes, catalogue des rôles et permissions |
| **Confidentiel** | Donnée personnelle ou décision RH/financière sans montant ni identifiant officiel | Atteinte à la vie privée, ciblage d'un salarié, hameçonnage | Noms, coordonnées, contrats, attributions de rôles, historiques de décision |
| **Restreint** | Montant de rémunération, identifiant officiel, donnée bancaire, authentifiant ou secret | Fraude financière, usurpation d'identité, prise de contrôle de compte | Salaires, bulletins, CIN, CNSS, RIB, empreintes de mots de passe, secrets |

### Exigences de traitement par niveau

Chaque niveau impose des mesures minimales. La colonne de droite indique la phase du projet qui les met en œuvre.

| Exigence | Interne | Confidentiel | Restreint | Phase |
|---|---|---|---|---|
| **Accès** | Tout utilisateur authentifié | Rôles ayant un besoin métier (RBAC) | Rôles nommés, besoin d'en connaître, restriction à ses propres lignes pour le salarié ; **pas de lecture directe des tables par le compte de service**, seulement par procédure contrôlée | 2 |
| **Stockage au repos** | Permissions de fichiers | Datadir et sauvegardes protégés | **Chiffrement** des identifiants officiels et du RIB ; mots de passe uniquement en **hachage adaptatif** (jamais en chiffrement réversible) | 3, 6 |
| **Transit** | Local | TLS dès que la donnée quitte l'hôte | TLS obligatoire dès que la donnée quitte l'hôte | 6, 9 |
| **Journalisation** | Modifications | Modifications et refus d'accès | Modifications, refus **et chaque lecture** (qui, quand, quel salarié) | 7 |
| **Affichage** | Libre | Aux seuls rôles autorisés | **Masqué par défaut** (par exemple RIB réduit aux 4 derniers chiffres), jamais dans une URL ni un journal | 6 |
| **Intégrité** | Contraintes | Historique des modifications | Historique immuable avec auteur ; séparation des tâches pour toute modification financière ou bancaire | 1, 2 |
| **Sauvegarde** | Standard | Accès restreint aux exports | **Export chiffré**, clé stockée séparément | 8 |
| **Conservation** | Selon le besoin | Durée définie par la Direction RH | Durée légale minimale, puis destruction tracée | — |

## 3. Règles de classification

- **R1 — Colonnes techniques.** Clés primaires, clés étrangères et horodatages sont **Interne**, sauf s'ils révèlent à eux seuls un fait personnel. Par exemple, `employees.archived_at` révèle un départ.
- **R2 — Agrégation.** Le niveau d'un ensemble est au moins celui de sa colonne la plus sensible. Une jointure qui réunit nom, matricule, CIN et RIB produit un profil d'usurpation complet ; tout export ou toute vue de ce type est **Restreint**.
- **R3 — Copies.** Une copie hérite du niveau de l'original : `payroll_calculations.snapshot`, exports `mysqldump`, datadir InnoDB, journaux qui citent une valeur.
- **R4 — Champs libres.** Les motifs et justifications (`reason`, `justification`, `grant_reason`…, jusqu'à 2 000 caractères) sont **Confidentiel**. Ils **ne doivent contenir ni montant d'un autre salarié, ni identifiant officiel, ni information de santé**. Les éléments `paid_leave` et `unpaid_leave` de `payroll_inputs` peuvent couvrir une absence pour maladie : leur motif ne doit jamais en préciser la cause. La base ne peut pas imposer cette règle ; elle relève de la formation des utilisateurs et de la revue d'audit.
- **R5 — Niveau d'une table.** Il est égal au niveau le plus élevé de ses colonnes.

## 4. Synthèse par table

**Exposition actuelle** : accès du compte de service `svc_php`, selon `database/setup/*grants.sql`.
- *Directe* : SELECT sur la table.
- *Procédure* : uniquement par `CALL` d'une procédure `SQL SECURITY DEFINER` qui contrôle l'acteur.
- *Aucune* : aucun privilège.

| Table | Niveau | Propriétaire | Exposition actuelle (`svc_php`) | Écart avec le niveau |
|---|---|---|---|---|
| `employee_personal_data` | **Restreint** | Direction RH | Aucune (lecture du salarié par procédure `personal_data_view`) | **Phase 6** : RIB, pièce d'identité et CNSS **chiffrés au repos** (AES-256-GCM, clés hors base) ; le salarié lit ses seules données, masquées |
| `account_invitations` | **Confidentiel** (e-mail personnel) | Direction RH | Écriture par procédure (`account_onboard`), aucune lecture | Conforme : la RH écrit l'adresse à l'embauche sans pouvoir la relire (document 09) |
| `accounts` | **Restreint** | RSSI | Directe, `password_hash` compris | Lecture du hash nécessaire à `password_verify` (voir § 6). **Phase 2** : `password_hash` réservé au rôle `sp_login`, actif pendant la seule connexion |
| `salary_conditions` | **Restreint** | Direction financière | **Directe** | Lecture directe interdite pour ce niveau. **Phase 2** : lisible uniquement sous les rôles MySQL RH et Finance |
| `compensation_requests` | **Restreint** | Direction financière | **Directe** | Lecture directe interdite pour ce niveau. **Phase 2** : lisible uniquement sous les rôles MySQL RH et Finance |
| `payroll_inputs` | **Restreint** | Responsable paie | Procédure | Conforme sur l'accès |
| `payroll_calculations` | **Restreint** | Responsable paie | Procédure | Conforme sur l'accès |
| `payslip_corrections` | **Restreint** | Responsable paie | Procédure | Conforme sur l'accès |
| `recovery_requests` | **Restreint** | Responsable paie | Procédure | Conforme sur l'accès |
| `settlement_ledger` | **Restreint** | Direction financière | Procédure | Conforme sur l'accès |
| `security_audit_log` | **Restreint** | RSSI / Auditeur | Écriture par procédure (`audit_record`), aucune lecture directe ; supervision par procédures | Phase 7 : piste d'audit en ajout seul (inviolable), lue par l'auditeur via procédures |
| `employees` | Confidentiel | Direction RH | Directe ; INSERT matricule et noms, UPDATE noms | Conforme |
| `employment_contracts` | Confidentiel | Direction RH | Directe ; écriture par procédure | Conforme |
| `employee_assignments` | Confidentiel | Direction RH | Directe ; écriture par procédure | Conforme |
| `role_assignments` | Confidentiel | RSSI | Directe (5 colonnes) ; écriture par procédure | Conforme |
| `compensation_decisions` | Confidentiel | Direction financière | Directe | Conforme |
| `compensation_history` | Confidentiel | Direction financière | Directe | Conforme |
| `payroll_periods` | Confidentiel | Direction financière | Procédure | Conforme |
| `payroll_input_decisions` | Confidentiel | Direction financière | Procédure | Conforme |
| `payslip_events` | Confidentiel | Responsable paie | Procédure | Conforme |
| `payroll_approvals` | Confidentiel | Responsable paie | Procédure | Conforme |
| `correction_events` | Confidentiel | Responsable paie | Procédure | Conforme |
| `recovery_events` | Confidentiel | Responsable paie | Procédure | Conforme |
| `roles` | Interne | RSSI | Directe (3 colonnes) | Conforme |
| `permissions` | Interne | RSSI | Directe (2 colonnes) | Conforme |
| `role_permissions` | Interne | RSSI | Directe | Conforme |
| `departments` | Interne | Direction RH | Directe | Conforme |
| `positions` | Interne | Direction RH | Directe | Conforme |

**Bilan : 10 tables Restreint, 12 Confidentiel, 5 Interne, 0 Public.**

## 5. Classification détaillée par colonne

Les colonnes techniques suivent la règle R1 et ne sont pas répétées : `id`, clés étrangères (`*_id`, `created_by`, `decided_by`, `actor_id`…), horodatages (`created_at`, `occurred_at`…). Les colonnes ci-dessous sont celles qui portent l'information.

### 5.1 Données personnelles — `employee_personal_data` (migrations `012` puis `015`)

**Phase 6.** Les trois colonnes **Restreint** ci-dessous sont **chiffrées au repos** (AES-256-GCM côté application, `App\Security\FieldCipher` ; colonnes `VARBINARY`, format `version‖nonce‖chiffré‖tag`). Les clés (donnée + index) vivent dans le répertoire d'exécution privé, **hors dépôt et hors base** : un vidage SQL ne révèle rien. L'unicité, impossible sur un chiffré à nonce aléatoire, est portée par un **index aveugle** HMAC-SHA256 à clé distincte (`*_index`). Le format est validé en PHP avant chiffrement ; l'affichage est **masqué** (voir [11-PROTECTION-DONNEES-SENSIBLES.md](11-PROTECTION-DONNEES-SENSIBLES.md)).

| Colonne | Niveau | Justification |
|---|---|---|
| `id_document_number` | **Restreint** | CIN ou numéro de titre de séjour ou de passeport : identifiant officiel unique, principal ingrédient d'une usurpation d'identité. **Chiffré au repos**, unicité par index aveugle |
| `cnss_number` | **Restreint** | Identifiant de sécurité sociale ; permet la fraude aux prestations. **Chiffré au repos** (facultatif), unicité par index aveugle |
| `rib` | **Restreint** | Coordonnées bancaires. **Chiffré au repos**, unicité par index aveugle. Saisi par le salarié lui-même (libre-service, `personal_data_set_rib`), NULL tant qu'il ne l'a pas fait. **Enjeu d'intégrité majeur** : modifier le RIB détourne le salaire → double validation et alerte au salarié prévues (menace T-08, phase ultérieure). |
| `id_document_type` | Confidentiel | La valeur `residence_card` révèle qu'un salarié est étranger |
| `birth_date` | Confidentiel | Donnée d'identification ; devient Restreint combinée au nom et à la CIN (R2) |
| `marital_status`, `dependent_children` | Confidentiel | Vie privée et familiale ; nécessaires aux charges de famille de la paie marocaine |
| `personal_email`, `personal_phone` | Confidentiel | Permettent hameçonnage ciblé et harcèlement |
| `address_line`, `city`, `postal_code` | Confidentiel | Sécurité physique du salarié |
| `bank_name` | Confidentiel | Moins discriminant que le RIB, mais facilite l'hameçonnage bancaire |
| `updated_by`, `updated_at` | Interne | Traçabilité (R1) ; leur intégrité est garantie par le trigger `employee_personal_data_preserve_origin` |

### 5.2 Identité, authentification et contrôle d'accès

| Table.colonne | Niveau | Justification |
|---|---|---|
| `accounts.password_hash` | **Restreint** | Empreinte Argon2id. Une fuite permet une attaque hors ligne, d'autant plus efficace que le mot de passe est faible. |
| `accounts.login` | Confidentiel | Moitié de l'authentifiant ; permet une force brute ciblée |
| `accounts.disabled_at` | Interne | État du compte |
| `employees.first_name`, `last_name`, `employee_number` | Confidentiel | Données personnelles ; le matricule est la clé de jointure vers les salaires (R2) |
| `employees.archived_at` | Confidentiel | Révèle le départ du salarié (exception à R1) |
| `role_assignments.role_id`, `valid_from`, `expires_at`, `revoked_at` | Confidentiel | Indique qui détient un rôle puissant, donc qui viser. **Intégrité critique** : une attribution ajoutée est une élévation de privilèges. |
| `role_assignments.grant_reason`, `revocation_reason` | Confidentiel | Champs libres (R4) |
| `roles.*`, `permissions.*`, `role_permissions.*` | Interne | Politique d'accès ; sa divulgation aide un attaquant sans exposer de personne |

### 5.3 Parcours professionnel

| Table.colonne | Niveau | Justification |
|---|---|---|
| `employment_contracts.reference`, `contract_type`, `starts_on`, `ends_on`, `closed_on` | Confidentiel | Situation contractuelle : précarité, fin de contrat |
| `employee_assignments.department_id`, `position_id`, `starts_on`, `ends_on`, `closed_on` | Confidentiel | Parcours professionnel individuel |
| `departments.*`, `positions.*` | Interne | Organigramme sans personne |

### 5.4 Rémunération (migrations `004`, `006`)

| Table.colonne | Niveau | Justification |
|---|---|---|
| `salary_conditions.monthly_amount` | **Restreint** | Salaire contractuel approuvé : source de toutes les paies |
| `compensation_requests.monthly_amount` | **Restreint** | Salaire proposé, y compris s'il est refusé |
| `compensation_requests.justification` | Confidentiel | Champ libre (R4) ; peut évoquer une évaluation |
| `compensation_decisions.decision`, `reason` | Confidentiel | Acceptation ou refus d'une augmentation |
| `compensation_history.event_type` | Confidentiel | Chronologie des décisions. **Intégrité** : piste d'audit. |
| `compensation_requests.request_kind`, `effective_on` ; `salary_conditions.effective_on` | Confidentiel | Même sans montant, `revision` et sa date révèlent qu'un salarié a demandé ou obtenu une augmentation |
| `currency` (toutes tables) | Interne | Devise (MAD, ou UM pour l'historique), identique pour tous |

### 5.5 Paie (migrations `007`, `008`)

| Table.colonne | Niveau | Justification |
|---|---|---|
| `payroll_calculations.base_amount`, `bonus_amount`, `deduction_amount`, `gross_amount`, `net_amount` | **Restreint** | Montants du bulletin |
| `payroll_calculations.snapshot` | **Restreint** | **Copie** du salaire mensuel pour chaque jour du mois et des éléments variables (R3), construite par `payroll_build` |
| `payroll_calculations.source_hash`, `algorithm`, `version_no` | Interne | Contrôle de cohérence, sans valeur |
| `payroll_inputs.amount` | **Restreint** | Prime ou retenue individuelle |
| `payroll_inputs.kind`, `starts_on`, `ends_on`, `reason` | Confidentiel | `paid_leave` / `unpaid_leave` révèlent une absence ; le motif ne doit pas en donner la cause (R4) |
| `payroll_input_decisions.decision`, `reason` | Confidentiel | Décision Finance individuelle |
| `payroll_periods.bonus_cap`, `deduction_cap` | Confidentiel | Politique financière de l'organisation (plafonds mensuels) |
| `payroll_periods.month_start`, `reason` | Interne | Calendrier de paie |
| `payslip_events.event_type`, `reason` | Confidentiel | Cycle de vie du bulletin. **Intégrité** : prouve la vérification, l'approbation et la publication. |
| `payroll_approvals.*` | Confidentiel | Désigne le calcul approuvé. **Intégrité critique** : changer l'ancrage changerait le montant versé. |

### 5.6 Règlements et corrections (migrations `009`, `010`)

| Table.colonne | Niveau | Justification |
|---|---|---|
| `settlement_ledger.amount` | **Restreint** | Somme versée ou restituée. **Intégrité critique** : registre comptable. |
| `settlement_ledger.entry_type`, `reference`, `reason` | Confidentiel | Nature et référence du mouvement |
| `payslip_corrections.base_amount`, `bonus_amount`, `deduction_amount`, `gross_amount`, `net_amount` | **Restreint** | Montants corrigés du bulletin |
| `payslip_corrections.reason`, `revision` | Confidentiel | Motif et numéro de correction |
| `recovery_requests.amount` | **Restreint** | Trop-perçu à restituer |
| `recovery_requests.reason` | Confidentiel | Champ libre (R4) |
| `correction_events.*`, `recovery_events.*` (hors techniques) | Confidentiel | Pistes d'audit des corrections et restitutions |

## 6. Données hors base

| Actif (voir 01) | Niveau | Justification |
|---|---|---|
| K-01 `.local/admin.json`, K-02 `.local/application.json`, K-03 `.local/credentials.json` | **Restreint** | Secrets en clair : `root`, `svc_php`, mots de passe des comptes web |
| K-04 fichiers de session `.local/runtime/sess_*` | **Restreint** | Équivalent d'un authentifiant tant que la session est valide |
| B-01 exports `mysqldump`, I-01 datadir `.local/data/` | **Restreint** | Copies intégrales de la base (R3) |
| L-01 `application.log` | Confidentiel | Identifiants d'acteurs et de salariés, nature des actions ; aucun mot de passe ni montant n'y est écrit (`helpers.php::auditEvent`) |
| L-02 `mysql.log`, L-03 état du limiteur | Interne | Informations techniques ; l'adresse IP et l'identifiant y sont hachés (SHA-256) |
| I-04 code source et scripts SQL | Interne | Dépôt privé ; ne contient aucun secret (contrôle `bin/audit-secrets.py`) |

**Cas de `accounts.password_hash`.** Le compte de service doit lire l'empreinte, car la vérification Argon2id a lieu en PHP (`AuthService::login`). C'est une exception justifiée à la règle « pas de lecture directe » du niveau Restreint. Elle est acceptable parce que l'empreinte n'est pas réversible et que la colonne est contrainte au format Argon2id (`ck_accounts_argon2id`). Elle reste à documenter comme risque résiduel.

## 7. Écarts entre classification et état actuel

| # | Écart | Données concernées | Phase de traitement |
|---|---|---|---|
| E1 | Données **Restreint** lisibles directement par le compte de service | `salary_conditions`, `compensation_requests` (et `accounts.password_hash`, exception justifiée au § 6) | 2 — **corrigé** : rôles MySQL activés par requête ([06](06-MATRICE-DE-CONTROLE-D-ACCES.md)) ; le vol du secret de `svc_php` reste hors de portée de cette mesure |
| E2 | Identifiants officiels et RIB **en clair** au repos, y compris dans le datadir et les sauvegardes | `employee_personal_data`, I-01, B-01 | 6, 8 |
| E3 | Montants copiés en clair dans `snapshot` | `payroll_calculations.snapshot` | 6 |
| E4 | **Aucune lecture** de donnée Restreint n'est journalisée | Toutes les tables Restreint | 7 |
| E5 | Pas de double validation ni d'alerte lors d'une modification du RIB | `employee_personal_data.rib` | 2, 7 |
| E6 | Secrets en clair, protégés uniquement par les permissions de fichiers | K-01 à K-03 | 9 |
| E7 | Exports non chiffrés | B-01 | 8 |
| E8 | Aucune durée de conservation définie | Toutes | Rapport (recommandations) |
| E9 | Règle R4 sur les champs libres non outillée | Toutes les colonnes `reason`, `justification` | 7 (revue d'audit) |
