# 04 — Backend PHP

> Périmètre : analyse des sources au 11 novembre 2026. Les attestations de tests sont datées ; aucune campagne fonctionnelle n’a été relancée. Installation MySQL actuelle : **Non vérifié**.

## Amorçage et modèle d’exécution

`app/bootstrap.php` active E_ALL, désactive l’affichage d’erreurs, active les logs, ignore les arguments d’exception et fixe UTC. Son autoloader ne résout que les classes App\ avec un nom validé. Un handler convertit les avertissements PHP en ErrorException ; le handler global journalise classe/fichier/ligne, puis répond 500 sans trace ni argument. La destination finale du journal est fournie par Runtime.

Aucune classe Entity/Model active-record n’est définie. Les données sont des tableaux associatifs renvoyés par PDO ; les validateurs sont des fonctions pures et les repositories ne déterminent pas à eux seuls les autorisations HTTP. Les contrôleurs ont un handle/run et des render privés qui utilisent extract(EXTR_SKIP), puis une vue choisie dans le code.

## Contrats de retour et dépendances communs

Les lectures repository retournent array, ?array ou bool selon signature. Les commandes SQL publiques renvoient généralement un id positif (`SELECT ... AS id`) ou void pour clôture RH et IAM. Les tableaux métier sont décrits par les SELECT et le dictionnaire. Les erreurs sont levées sous forme d’exceptions puis traduites par le contrôleur ; aucun repository ne doit être enveloppé dans une transaction PHP lorsque la procédure la gère déjà.

Les signatures ci-dessous proviennent directement des déclarations PHP, y compris les paramètres, valeurs par défaut et types de retour. Les dépendances `use` désignent des classes importées, pas toutes les fonctions natives utilisées. Les constantes et détails des règles se trouvent dans les chapitres Sécurité et Paie.

## `App\Auth\AuthService`

**Fichier :** [app/Auth/AuthService.php](../../app/Auth/AuthService.php).

**Responsabilité :** Authentifier par Argon2id et reconstituer à chaque requête l’identité, les rôles, permissions et conflits.

**Dépendances importées :** App\Security\Session, PDO.

### Méthodes et paramètres

```php
public function __construct(private PDO $db) 
public function login(string $login, #[\SensitiveParameter] string $password): bool
public function currentUser(): ?array
public static function can(array $user, string $permission): bool
```

**MySQL :** Références textuelles directes : employees, accounts, roles, permissions, role_permissions, role_assignments.

**Contrat et sécurité :** les types de retour ci-dessus sont les contrats PHP. Les valeurs invalides provoquent une exception ou un résultat de validation négatif selon méthode ; elles ne sont pas persistées par cette classe, sauf session/limiteur/journal dans les composants de sécurité. Voir les règles détaillées des chapitres 07–08.

## `App\Auth\IAMRepository`

**Fichier :** [app/Auth/IAMRepository.php](../../app/Auth/IAMRepository.php).

**Responsabilité :** Adapter les trois procédures IAM et consommer tous les jeux de résultats.

**Dépendances importées :** PDO.

### Méthodes et paramètres

```php
public function __construct(private PDO $db) 
public function overview(int $actor,int $page): array
public function grant(int $account,string $role,string $reason,int $actor): void
public function revoke(int $assignment,string $reason,int $actor): void
private function call(string $sql,array $parameters): array
```

**MySQL :** CALL iam_grant, iam_overview, iam_revoke. Références textuelles directes : accounts, roles.

**Sécurité et résultats :** paramètres liés aux requêtes préparées ; les identifiants de table dynamiques sont sélectionnés par liste fermée lorsqu’ils existent. L’acteur est transmis par le contrôleur. Les fermetures de curseurs et, pour les adaptateurs concernés, le drainage nextRowset évitent de laisser des résultats CALL en attente. Les lectures RH/rémunération directes dépendent des autorisations PHP et des droits du compte SQL.

## `App\Compensation\CompensationRepository`

**Fichier :** [app/Compensation/CompensationRepository.php](../../app/Compensation/CompensationRepository.php).

**Responsabilité :** Lire les demandes, décisions et historiques, vérifier la devise et appeler les commandes salariales.

**Dépendances importées :** PDO.

### Méthodes et paramètres

```php
public function __construct(private PDO $db) 
public function referenceCurrencyReady(): bool
public function requests(string $status, int $page): array
public function find(int $id): ?array
public function events(int $request): array
public function contract(string $number, string $reference): ?array
public function contractedEmployees(int $page): array
public function history(int $page, ?int $employee): array
public function submit(array $values, array $contract, int $actor): int
public function decide(int $request, string $decision, string $reason, int $actor): int
private function call(string $sql, array $params): int
```

**MySQL :** CALL compensation_decide, compensation_submit, terminé. Références textuelles directes : employees, accounts, employment_contracts, compensation_requests, compensation_decisions, salary_conditions, compensation_history.

**Sécurité et résultats :** paramètres liés aux requêtes préparées ; les identifiants de table dynamiques sont sélectionnés par liste fermée lorsqu’ils existent. L’acteur est transmis par le contrôleur. Les fermetures de curseurs et, pour les adaptateurs concernés, le drainage nextRowset évitent de laisser des résultats CALL en attente. Les lectures RH/rémunération directes dépendent des autorisations PHP et des droits du compte SQL.

## `App\Compensation\CompensationValidation`

**Fichier :** [app/Compensation/CompensationValidation.php](../../app/Compensation/CompensationValidation.php).

**Responsabilité :** Normaliser montants exacts et valider textes Unicode et dates de proposition.

**Dépendances importées :** App\HR\PeriodValidation.

### Méthodes et paramètres

```php
public static function amount(string $value): ?string
public static function text(string $value, int $limit): bool
public static function errors(array $values): array
```

**MySQL :** Pas de nom de table direct ; les dépendances peuvent réaliser les accès.

**Contrat et sécurité :** les types de retour ci-dessus sont les contrats PHP. Les valeurs invalides provoquent une exception ou un résultat de validation négatif selon méthode ; elles ne sont pas persistées par cette classe, sauf session/limiteur/journal dans les composants de sécurité. Voir les règles détaillées des chapitres 07–08.

## `App\Database\Connection`

**Fichier :** [app/Database/Connection.php](../../app/Database/Connection.php).

**Responsabilité :** Valider la configuration et ouvrir PDO MySQL sans exposer les erreurs du pilote.

**Dépendances importées :** PDO, PDOException, RuntimeException.

### Méthodes et paramètres

```php
public static function validateConfiguration(): void
public static function connect(): PDO
private static function configuration(): array
```

**MySQL :** Pas de nom de table direct ; les dépendances peuvent réaliser les accès.

**Options PDO :** ERRMODE_EXCEPTION, FETCH_ASSOC, ATTR_EMULATE_PREPARES=false, charset utf8mb4. Variables host/port/name/user/password non vides, root refusé, validation anti-injection DSN, port 1–65535 et socket absolu optionnel. En cas d’échec PDO : RuntimeException générique sans chaînage du pilote.

## `App\Finance\Money`

**Fichier :** [app/Finance/Money.php](../../app/Finance/Money.php).

**Responsabilité :** Formater une chaîne décimale MAD/UM selon FR/EN sans calcul flottant ni conversion.

**Dépendances importées :** App\I18n\Translator.

### Méthodes et paramètres

```php
public static function format(string $amount, string $currency): string
```

**MySQL :** Pas de nom de table direct ; les dépendances peuvent réaliser les accès.

**Contrat et sécurité :** les types de retour ci-dessus sont les contrats PHP. Les valeurs invalides provoquent une exception ou un résultat de validation négatif selon méthode ; elles ne sont pas persistées par cette classe, sauf session/limiteur/journal dans les composants de sécurité. Voir les règles détaillées des chapitres 07–08.

## `App\HR\EmployeeRepository`

**Fichier :** [app/HR/EmployeeRepository.php](../../app/HR/EmployeeRepository.php).

**Responsabilité :** Lire/rechercher et créer/modifier uniquement l’identité autorisée ; concurrence optimiste.

**Dépendances importées :** PDO.

### Méthodes et paramètres

```php
public function __construct(private PDO $db) 
public function listing(string $search, int $page): array
public function find(int $id): ?array
public function create(array $values): int
public static function version(array $row): string
public function update(array $row, array $values): bool
```

**MySQL :** Références textuelles directes : employees.

**Sécurité et résultats :** paramètres liés aux requêtes préparées ; les identifiants de table dynamiques sont sélectionnés par liste fermée lorsqu’ils existent. L’acteur est transmis par le contrôleur. Les fermetures de curseurs et, pour les adaptateurs concernés, le drainage nextRowset évitent de laisser des résultats CALL en attente. Les lectures RH/rémunération directes dépendent des autorisations PHP et des droits du compte SQL.

## `App\HR\PeriodRepository`

**Fichier :** [app/HR/PeriodRepository.php](../../app/HR/PeriodRepository.php).

**Responsabilité :** Lire les catalogues/périodes RH et appeler les procédures de création/clôture.

**Dépendances importées :** PDO, RuntimeException.

### Méthodes et paramètres

```php
public function __construct(private PDO $db, private string $language = 'fr') 
private function table(string $kind): string
public function catalogue(string $kind, bool $activeOnly = false): array
private function projection(string $kind): string
public function listing(string $kind, ?int $employeeId, int $page): array
public function find(string $kind, int $id): ?array
public function employeeByNumber(string $number): ?array
public function create(string $kind, array $values, int $actor): int
public function close(string $kind, int $id, string $end, int $actor): void
```

**MySQL :** CALL hr_close_assignment, hr_close_contract, hr_create_assignment, hr_create_contract. Références textuelles directes : employees, departments, positions, employee_assignments, employment_contracts.

**Sécurité et résultats :** paramètres liés aux requêtes préparées ; les identifiants de table dynamiques sont sélectionnés par liste fermée lorsqu’ils existent. L’acteur est transmis par le contrôleur. Les fermetures de curseurs et, pour les adaptateurs concernés, le drainage nextRowset évitent de laisser des résultats CALL en attente. Les lectures RH/rémunération directes dépendent des autorisations PHP et des droits du compte SQL.

## `App\HR\PeriodValidation`

**Fichier :** [app/HR/PeriodValidation.php](../../app/HR/PeriodValidation.php).

**Responsabilité :** Valider dates, types et identifiants RH ; dériver le statut temporel.

**Dépendances importées :** Aucune ; fonctions natives et/ou références pleinement qualifiées.

### Méthodes et paramètres

```php
public static function date(string $value): bool
public static function errors(string $kind, array $values): array
public static function status(array $row): string
```

**MySQL :** Pas de nom de table direct ; les dépendances peuvent réaliser les accès.

**Contrat et sécurité :** les types de retour ci-dessus sont les contrats PHP. Les valeurs invalides provoquent une exception ou un résultat de validation négatif selon méthode ; elles ne sont pas persistées par cette classe, sauf session/limiteur/journal dans les composants de sécurité. Voir les règles détaillées des chapitres 07–08.

## `App\I18n\Translator`

**Fichier :** [app/I18n/Translator.php](../../app/I18n/Translator.php).

**Responsabilité :** Résoudre langue et clés de traduction avec repli français.

**Dépendances importées :** Aucune ; fonctions natives et/ou références pleinement qualifiées.

### Méthodes et paramètres

```php
public static function locale(): string
public static function text(string $key, array $parameters = []): string
private static function catalogue(string $language): array
```

**MySQL :** Pas de nom de table direct ; les dépendances peuvent réaliser les accès.

**Contrat et sécurité :** les types de retour ci-dessus sont les contrats PHP. Les valeurs invalides provoquent une exception ou un résultat de validation négatif selon méthode ; elles ne sont pas persistées par cette classe, sauf session/limiteur/journal dans les composants de sécurité. Voir les règles détaillées des chapitres 07–08.

## `App\Payroll\Calculator`

**Fichier :** [app/Payroll/Calculator.php](../../app/Payroll/Calculator.php).

**Responsabilité :** Calculateur pur indépendant en centimes entiers pour validation et comparaison ; non appelé par le parcours HTTP de calcul.

**Dépendances importées :** Aucune ; fonctions natives et/ou références pleinement qualifiées.

### Méthodes et paramètres

```php
public static function calculate(string $month, array $days, string $bonus, string $deduction, string $bonusCap, string $deductionCap): array
private static function cents(string $amount): int
private static function decimal(int $cents): string
```

**MySQL :** Pas de nom de table direct ; les dépendances peuvent réaliser les accès.

**Contrat et sécurité :** les types de retour ci-dessus sont les contrats PHP. Les valeurs invalides provoquent une exception ou un résultat de validation négatif selon méthode ; elles ne sont pas persistées par cette classe, sauf session/limiteur/journal dans les composants de sécurité. Voir les règles détaillées des chapitres 07–08.

## `App\Payroll\Calendar`

**Fichier :** [app/Payroll/Calendar.php](../../app/Payroll/Calendar.php).

**Responsabilité :** Transformer des sources approuvées de confiance en journées couvertes, avec contrôles d’identité, chevauchements et devise.

**Dépendances importées :** App\HR\PeriodValidation.

### Méthodes et paramètres

```php
public static function build(int $employee, string $month, array $contracts, array $conditions, array $suspensions = []): array
private static function identity(mixed $row, int $employee): void
private static function period(array $row, string $endKey, bool $nullable): void
```

**MySQL :** Pas de nom de table direct ; les dépendances peuvent réaliser les accès.

**Contrat et sécurité :** les types de retour ci-dessus sont les contrats PHP. Les valeurs invalides provoquent une exception ou un résultat de validation négatif selon méthode ; elles ne sont pas persistées par cette classe, sauf session/limiteur/journal dans les composants de sécurité. Voir les règles détaillées des chapitres 07–08.

## `App\Payroll\Repository`

**Fichier :** [app/Payroll/Repository.php](../../app/Payroll/Repository.php).

**Responsabilité :** Adapter les procédures Paie et Settlement ; décoder les instantanés et renvoyer des tableaux structurés.

**Dépendances importées :** PDO.

### Méthodes et paramètres

```php
public function __construct(private PDO $db) 
public function overview(int $actor, int $page): array
public function detail(int $id, int $actor): array
public function createPeriod(string $month, string $bonusCap, string $deductionCap, string $reason, int $actor): int
public function submitInput(int $period, int $employee, string $kind, string $amount, string $start, string $end, string $reason, int $actor): int
public function decideInput(int $id, string $decision, string $reason, int $actor): int
public function calculate(int $period, int $employee, int $actor): int
public function transition(int $id, string $event, string $reason, int $actor): int
public function settlement(int $root, int $actor): array
public function settle(array $parameters): int
private function command(string $sql, array $parameters): int
private function call(string $sql, array $parameters): array
```

**MySQL :** CALL payroll_calculate, payroll_input_decide, payroll_input_submit, payroll_overview, payroll_period_create, payslip_detail, payslip_transition, settlement_command, settlement_detail. Références textuelles directes : employees.

**Sécurité et résultats :** paramètres liés aux requêtes préparées ; les identifiants de table dynamiques sont sélectionnés par liste fermée lorsqu’ils existent. L’acteur est transmis par le contrôleur. Les fermetures de curseurs et, pour les adaptateurs concernés, le drainage nextRowset évitent de laisser des résultats CALL en attente. Les lectures RH/rémunération directes dépendent des autorisations PHP et des droits du compte SQL.

## `App\Payroll\Validation`

**Fichier :** [app/Payroll/Validation.php](../../app/Payroll/Validation.php).

**Responsabilité :** Valider IDs, mois, montants zéro/positifs et éléments de paie.

**Dépendances importées :** App\Compensation\CompensationValidation, App\HR\PeriodValidation.

### Méthodes et paramètres

```php
public static function amount(string $value): ?string
public static function id(mixed $value): ?int
public static function month(string $value): bool
public static function input(array $values): bool
```

**MySQL :** Pas de nom de table direct ; les dépendances peuvent réaliser les accès.

**Contrat et sécurité :** les types de retour ci-dessus sont les contrats PHP. Les valeurs invalides provoquent une exception ou un résultat de validation négatif selon méthode ; elles ne sont pas persistées par cette classe, sauf session/limiteur/journal dans les composants de sécurité. Voir les règles détaillées des chapitres 07–08.

## `App\Security\LoginLimiter`

**Fichier :** [app/Security/LoginLimiter.php](../../app/Security/LoginLimiter.php).

**Responsabilité :** Réserver les tentatives par IP dans un fichier verrouillé et libérer seulement une connexion réussie.

**Dépendances importées :** Aucune ; fonctions natives et/ou références pleinement qualifiées.

### Méthodes et paramètres

```php
public static function allow(): bool
public static function succeeded(): void
```

**MySQL :** Pas de nom de table direct ; les dépendances peuvent réaliser les accès.

**Contrat et sécurité :** les types de retour ci-dessus sont les contrats PHP. Les valeurs invalides provoquent une exception ou un résultat de validation négatif selon méthode ; elles ne sont pas persistées par cette classe, sauf session/limiteur/journal dans les composants de sécurité. Voir les règles détaillées des chapitres 07–08.

## `App\Security\Runtime`

**Fichier :** [app/Security/Runtime.php](../../app/Security/Runtime.php).

**Responsabilité :** Sélectionner le répertoire privé de logs/limiteur et, si option configurée, des sessions.

**Dépendances importées :** Aucune ; fonctions natives et/ou références pleinement qualifiées.

### Méthodes et paramètres

```php
public static function directory(): string
```

**MySQL :** Pas de nom de table direct ; les dépendances peuvent réaliser les accès.

**Contrat et sécurité :** les types de retour ci-dessus sont les contrats PHP. Les valeurs invalides provoquent une exception ou un résultat de validation négatif selon méthode ; elles ne sont pas persistées par cette classe, sauf session/limiteur/journal dans les composants de sécurité. Voir les règles détaillées des chapitres 07–08.

## `App\Security\Session`

**Fichier :** [app/Security/Session.php](../../app/Security/Session.php).

**Responsabilité :** Démarrer, expirer et renouveler les sessions ; générer et valider les jetons CSRF.

**Dépendances importées :** Aucune ; fonctions natives et/ou références pleinement qualifiées.

### Méthodes et paramètres

```php
public static function start(): void
public static function signIn(int $accountId): void
public static function clear(): void
public static function validCsrf(mixed $token): bool
```

**MySQL :** Pas de nom de table direct ; les dépendances peuvent réaliser les accès.

**Contrat et sécurité :** les types de retour ci-dessus sont les contrats PHP. Les valeurs invalides provoquent une exception ou un résultat de validation négatif selon méthode ; elles ne sont pas persistées par cette classe, sauf session/limiteur/journal dans les composants de sécurité. Voir les règles détaillées des chapitres 07–08.

## `App\Web\AdvancedHRController`

**Fichier :** [app/Web/AdvancedHRController.php](../../app/Web/AdvancedHRController.php).

**Responsabilité :** Orchestrer les catalogues, contrats et affectations et traduire les refus métier.

**Dépendances importées :** App\Auth\AuthService, App\HR\EmployeeRepository, App\HR\PeriodRepository, App\HR\PeriodValidation, PDO, PDOException.

### Méthodes et paramètres

```php
public function __construct(private PDO $db) 
public static function matches(string $path): bool
public static function methods(string $path): array
private function render(string $view, array $data, int $status = 200): void
public function handle(string $path, string $method, array $data): void
private function notFound(array $data): void
private function databaseError(PDOException $error): array
```

**MySQL :** Références textuelles directes : employees, departments, positions.

**Sécurité et résultats :** permission évaluée avec AuthService::can, champs filtrés/validés puis SQL via repository ; réponse HTML/303, erreurs 403/404/409/422/503 selon route. Le contrôleur central applique CSRF avant délégation. Les signatures privées render/erreurs sont internes et ne constituent pas des routes.

## `App\Web\CompensationController`

**Fichier :** [app/Web/CompensationController.php](../../app/Web/CompensationController.php).

**Responsabilité :** Orchestrer soumission, listes et décision Finance des demandes salariales.

**Dépendances importées :** App\Auth\AuthService, App\Compensation\CompensationRepository, App\Compensation\CompensationValidation, PDO, PDOException.

### Méthodes et paramètres

```php
public function __construct(private PDO $db) 
public static function matches(string $path): bool
public static function methods(string $path): array
private function render(string $view, array $data, int $status = 200): void
public function handle(string $path, string $method, array $data): void
private function databaseError(PDOException $error): array
```

**MySQL :** Références textuelles directes : employees.

**Sécurité et résultats :** permission évaluée avec AuthService::can, champs filtrés/validés puis SQL via repository ; réponse HTML/303, erreurs 403/404/409/422/503 selon route. Le contrôleur central applique CSRF avant délégation. Les signatures privées render/erreurs sont internes et ne constituent pas des routes.

## `App\Web\Controller`

**Fichier :** [app/Web/Controller.php](../../app/Web/Controller.php).

**Responsabilité :** Routeur central, authentification, identité RH, erreurs et délégation des modules.

**Dépendances importées :** App\Auth\AuthService, App\Database\Connection, App\HR\EmployeeRepository, App\Security\LoginLimiter, App\Security\Session, PDO, PDOException.

### Méthodes et paramètres

```php
private function database(): PDO
private function render(string $view, array $data = [], int $status = 200): void
private function existingMethods(string $path): array
public function run(): void
private function logContractCreationDiagnostic(PDOException $exception): void
private function denied(array $data): void
```

**MySQL :** Références textuelles directes : employees.

**Sécurité et résultats :** permission évaluée avec AuthService::can, champs filtrés/validés puis SQL via repository ; réponse HTML/303, erreurs 403/404/409/422/503 selon route. Le contrôleur central applique CSRF avant délégation. Les signatures privées render/erreurs sont internes et ne constituent pas des routes.

## `App\Web\IAMController`

**Fichier :** [app/Web/IAMController.php](../../app/Web/IAMController.php).

**Responsabilité :** Orchestrer lecture, octroi et révocation des attributions sans gérer les mots de passe.

**Dépendances importées :** App\Auth\AuthService, App\Auth\IAMRepository, App\Compensation\CompensationValidation, App\Payroll\Validation, PDO, PDOException.

### Méthodes et paramètres

```php
public function __construct(private PDO $db) 
public static function matches(string $path): bool
public static function methods(string $path): array
private function render(string $view,array $data,int $status=200): void
public function handle(string $path,string $method,array $data): void
```

**MySQL :** Pas de nom de table direct ; les dépendances peuvent réaliser les accès.

**Sécurité et résultats :** permission évaluée avec AuthService::can, champs filtrés/validés puis SQL via repository ; réponse HTML/303, erreurs 403/404/409/422/503 selon route. Le contrôleur central applique CSRF avant délégation. Les signatures privées render/erreurs sont internes et ne constituent pas des routes.

## `App\Web\PayrollController`

**Fichier :** [app/Web/PayrollController.php](../../app/Web/PayrollController.php).

**Responsabilité :** Orchestrer mois, éléments, calcul, transitions et consultation des bulletins ; déléguer Settlement.

**Dépendances importées :** App\Auth\AuthService, App\Compensation\CompensationValidation, App\Payroll\Repository, App\Payroll\Validation, PDO, PDOException.

### Méthodes et paramètres

```php
public function __construct(private PDO $db) 
public static function matches(string $path): bool
public static function methods(string $path): array
private function render(string $view, array $data, int $status = 200): void
public function handle(string $path, string $method, array $data): void
```

**MySQL :** Pas de nom de table direct ; les dépendances peuvent réaliser les accès.

**Sécurité et résultats :** permission évaluée avec AuthService::can, champs filtrés/validés puis SQL via repository ; réponse HTML/303, erreurs 403/404/409/422/503 selon route. Le contrôleur central applique CSRF avant délégation. Les signatures privées render/erreurs sont internes et ne constituent pas des routes.

## `App\Web\SettlementController`

**Fichier :** [app/Web/SettlementController.php](../../app/Web/SettlementController.php).

**Responsabilité :** Orchestrer corrections, paiements fictifs et restitutions avec version attendue.

**Dépendances importées :** App\Auth\AuthService, App\Compensation\CompensationValidation, App\Payroll\Repository, App\Payroll\Validation, PDO, PDOException.

### Méthodes et paramètres

```php
public function __construct(private PDO $db) 
private function render(string $view, array $data, int $status = 200): void
public static function permission(string $action): ?string
public function handle(string $path, string $method, array $data): void
```

**MySQL :** Pas de nom de table direct ; les dépendances peuvent réaliser les accès.

**Sécurité et résultats :** permission évaluée avec AuthService::can, champs filtrés/validés puis SQL via repository ; réponse HTML/303, erreurs 403/404/409/422/503 selon route. Le contrôleur central applique CSRF avant délégation. Les signatures privées render/erreurs sont internes et ne constituent pas des routes.

## Fonctions de app/Web/helpers.php

- `t(key, parameters): string`, `locale(): string`, `roleNames(roles): string` : traduction et présentation des rôles.
- `h(value): string` : échappement HTML de toute valeur par htmlspecialchars UTF-8.
- `field(data, key): string` : refuse les valeurs POST/GET de type tableau en renvoyant une chaîne vide.
- `redirectTo(path): never` : en-tête Location 303 et exit ; les chemins sont construits côté serveur.
- `csrfField(): string` : champ caché avec jeton échappé.
- `languageReturnPath(value): string` : chemin interne autorisé, sans hôte/protocole/fragment, sinon /dashboard.
- `employeeErrors(values, creating): array` : longueurs Unicode et caractères de contrôle ; messages traduits par champ.
- `auditEvent(event, actor, employee, resource): void` : JSON horodaté dans error_log, identifiants seulement, aucun motif libre ni montant.

## Transactions, concurrence et journalisation

`EmployeeRepository::update` compare les anciennes valeurs binaires dans WHERE ; la version HMAC est liée au CSRF de session. Un doublon de matricule retourne 409. La création d’identité est un INSERT simple, sans événement métier SQL atomique : le log PHP intervient après écriture.

Les procédures financières et IAM possèdent leurs transactions. Les exceptions SQL utilisent rollback/resignal et les opérations concurrentes sont sérialisées par le verrou de la ligne employé. Les erreurs 1062, 1205 et 1213 sont rendues comme conflits 409 dans les modules concernés ; l’interface demande une nouvelle tentative, sans retry automatique généralisé. Les lectures peuvent être multi-jeux de résultats ; `Repository::detail` décode snapshot avec JSON_THROW_ON_ERROR et profondeur 32.

Le journal PHP protège la confidentialité en ne recopiant pas getMessage/errorInfo[2] en sortie brute. Un diagnostic temporaire de `/contracts/new` subsiste dans Controller : opération, SQLSTATE et code MySQL seulement. L’audit métier des procédures conserve au contraire les motifs et identités dans les tables autorisées.

Les routes détaillées sont dans `14-INVENTAIRE-DES-ROUTES.md`. Le parcours navigateur/PHP/PDO/MySQL/réponse est développé dans `02-ARCHITECTURE.md` et la séquence de paie.

## Complément — contrats détaillés des méthodes métier

| Classe / méthodes | Entrées et traitement | Retour / effet attendu |
|---|---|---|
| AuthService::login | login et mot de passe sensible ; recherche préparée, vérification Argon2id ; identité active | bool ; true initialise Session::signIn, false ne connecte pas |
| AuthService::currentUser | account_id de session ; relecture identité et rôles | ?array contenant account_id, employee_id, employee_number, first_name, last_name, roles, permissions, compensation_conflict, payroll_conflict ; null et session nettoyée si identité invalide |
| AuthService::can | tableau user et code permission | bool ; rôle attendu ET permission, avec contrôle de conflits propre au module |
| Connection::validateConfiguration / connect | environnement privé ; configuration validée, socket facultatif | void sans connexion pour validateConfiguration ; instance PDO pour connect ; RuntimeException générique si invalide/indisponible |
| EmployeeRepository::listing | search littéral, page bornée par contrôleur ; COUNT puis LIMIT 20 | array rows/total/page ; lignes d’identité et état d’archivage |
| EmployeeRepository::find / create | id positif ; ou values validés matricule/prénom/nom | ?array si lecture ; int lastInsertId si création |
| EmployeeRepository::version / update | ancien tableau et CSRF ; nouvelles valeurs de nom | signature HMAC string ; bool si UPDATE conditionnel réussi ou état final déjà identique ; false si conflit |
| PeriodRepository::catalogue | kind departments/positions, activeOnly et langue constructeur | array de id/code/label/archived_at ; noms de tables et colonnes choisis en liste fermée |
| PeriodRepository::listing / find | kind contracts/assignments, employeeId facultatif, page ; ou id | rows/total/page pour liste ; ?array pour détail, projection enrichie de salarié et libellés d’affectation |
| PeriodRepository::employeeByNumber | matricule exact | ?array id/employee_number/first_name/last_name/archived_at |
| PeriodRepository::create / close | kind validé, salarié et champs, actor ; ou id/date de clôture/actor | int id nouveau ou void ; CALL autonome avec curseur fermé |
| PeriodValidation::date / errors / status | date ISO ; valeurs de formulaire et kind ; ou ligne à fin effective | bool ; array de clés de traduction d’erreur ; clé de statut hr.status.ended/planned/current |
| CompensationRepository::referenceCurrencyReady | aucune entrée utilisateur ; information_schema.COLUMNS | bool si les deux colonnes sont char(3), défaut MAD ; ne vérifie pas les routines |
| CompensationRepository::requests | status fermé et page | rows/total/page/pages ; état dérivé d’une LEFT JOIN décision, pending si absent |
| CompensationRepository::find / events | id de demande | ?array enrichi de contrat/demandeur/approbateur ; array d’événements avec acteur et instant |
| CompensationRepository::contract | employee_number et reference exacts | ?array du contrat joint au salarié non archivé |
| CompensationRepository::contractedEmployees / history | page et employee facultatif pour history | rows/total/page/pages ; history dérive ends_on par prochaine version et fin du contrat |
| CompensationRepository::submit / decide | values et contrat résolu côté serveur, actor ; ou request/decision/reason/actor | int id retourné par procédure ; exception si id absent ou erreur d’un jeu de résultats différé |
| CompensationValidation::amount | chaîne décimale utilisateur, point/virgule | ?string normalisée avec deux décimales ; null si zéro/invalide |
| CompensationValidation::text / errors | texte Unicode/limite ; ou tableau de formulaire | bool ; array de clés d’erreurs, jamais messages PDO |
| Calendar::build | employee, month, contrats, conditions approuvées, suspensions ; types d’identité stricts | array de jours date/salary_condition_id/monthly_amount/currency/paid ; InvalidArgumentException si couverture ou identité invalide |
| Calculator::calculate | mois, journées de référence, bonus/deduction et plafonds exacts | array algorithm/month/currency/calendar_days/covered_days/paid_days/base/bonus/deduction/gross/net/inputs/salary_sources ; montants en chaînes |
| Validation::amount / id / month / input | chaînes de formulaire ; kinds et dates | ?string montant admettant zéro ; ?int id ; bool mois ; bool validité des éléments |
| Payroll\Repository::overview | actor et page | periods/employees/inputs/calculations à partir de quatre jeux SQL ; jeux restreints pour Employee |
| Payroll\Repository::detail | id du calcul et actor | row dont snapshot est décodé en array, events, versions ; exception si première ligne absente |
| Payroll\Repository::createPeriod / submitInput / decideInput | mois/caps/motif ; élément salarié/période/type/montant/dates ; ou id/décision/motif ; actor obligatoire | int id renvoyé par payroll_period_create / payroll_input_submit / payroll_input_decide |
| Payroll\Repository::calculate / transition | période/salarié/actor ; ou calcul/event/reason/actor | int id du calcul ou événement ; aucun calcul financier PHP dans ces méthodes |
| Payroll\Repository::settlement | root et actor | summary/corrections/correctionEvents/ledger/recoveries/recoveryEvents issus de six jeux |
| Payroll\Repository::settle | tableau ordonné root/action/target/expected/base/bonus/deduction/reference/reason/actor | int id de l’objet/événement créé par settlement_command |
| IAMRepository::overview / grant / revoke | actor/page ; cible account/role/reason/actor ; assignment/reason/actor | accounts/roles/assignments pour lecture ; void pour commandes, résultat SQL drainé |
| Session::start / signIn / clear / validCsrf | contexte HTTP ; accountId authentifié ; token fourni | void pour transitions de session ; bool pour comparaison CSRF |
| LoginLimiter::allow / succeeded | adresse REMOTE_ADDR et réservation statique de requête | bool autorisation/réservation ; void pour libération ciblée d’un succès |
| Runtime::directory | APP_RUNTIME_DIR facultatif et métadonnées système | string chemin ; exception si répertoire configuré insuffisamment privé |
| Translator::locale / text | langue session ; clé et paramètres de substitution | fr/en ; string traduite avec repli français ; les vues restent responsables de h() |
| Money::format | montant positif ou nul sous forme de chaîne, MAD/UM | string localisée ; UnexpectedValueException si représentation invalide ; aucune conversion |
| Controller::run | URI, méthode, GET/POST, session | void ou fin via redirectTo ; route/CSRF/authentification/délégation/rendu |
| Contrôleurs spécialisés ::matches / methods | chemin complet | bool de correspondance ; array de méthodes HTTP admises |
| Contrôleurs spécialisés ::handle | path, method, data contenant user et contexte de vue | void ou 303 ; refuse accès/champs/états invalides avant commande |
| SettlementController::permission | code action pay/correct/verified/... | ?string permission ; null pour action inconnue ; ne dépend jamais d’un rôle fourni comme identité |

Les méthodes privées table/projection/call/command/render/databaseError et assertions internes sont des adaptateurs : elles sélectionnent les ressources dans des listes constantes, consomment les résultats, produisent le HTML ou traduisent les codes SQL. Leur signature complète et leur contexte figurent dans les fiches de classe précédentes ; elles ne sont pas accessibles par URL.
