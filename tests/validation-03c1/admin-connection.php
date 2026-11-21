<?php

declare(strict_types=1);

// Nom historique : ce harnais refuse désormais tout compte root et tout droit global.
ini_set('display_errors', '0');
ini_set('zend.exception_ignore_args', '1');

function validationConnection(bool $selectDatabase = true): PDO
{
    if (PHP_SAPI !== 'cli' || !function_exists('posix_geteuid') || posix_geteuid() === 0
        || getenv('DB_NAME') !== 'secure_payroll_validation_03b'
        || strtolower(trim((string) getenv('DB_USER'))) === 'root'
        || getenv('DB_HOST') !== 'localhost') {
        throw new RuntimeException('Contexte de validation refusé.');
    }
    require_once dirname(__DIR__, 2) . '/app/Database/Connection.php';
    \App\Database\Connection::validateConfiguration();
    $config = require dirname(__DIR__, 2) . '/config/database.php';
    // Sans base par défaut pour pouvoir vérifier l’absence de la cible avant sa création.
    $pdo = new PDO(
        'mysql:host=localhost;port=' . $config['port'] . ';charset=utf8mb4',
        $config['user'],
        $config['password'],
        [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES => false,
            \Pdo\Mysql::ATTR_MULTI_STATEMENTS => false]
    );
    $user = (string) $pdo->query('SELECT CURRENT_USER()')->fetchColumn();
    if (strtolower(explode('@', $user)[0]) === 'root'
        || $pdo->query('SELECT CURRENT_ROLE()')->fetchColumn() !== 'NONE') {
        throw new RuntimeException('Identité MySQL ou rôles refusés.');
    }
    $partialRevokes = (int) $pdo->query('SELECT @@global.partial_revokes')->fetchColumn() === 1;
    $grants = $pdo->query('SHOW GRANTS')->fetchAll(PDO::FETCH_COLUMN);
    validationCheckGrants($grants, $partialRevokes);
    if ($selectDatabase) {
        $pdo->exec('USE `secure_payroll_validation_03b`');
        if ($pdo->query('SELECT DATABASE()')->fetchColumn() !== 'secure_payroll_validation_03b') {
            throw new RuntimeException('Cible de validation refusée.');
        }
    }
    return $pdo;
}

/** Refus conservateur des privilèges globaux, autres bases, rôles et GRANT OPTION. */
function validationCheckGrants(array $grants, bool $partialRevokes): void
{
    $allowed = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'TRIGGER', 'REFERENCES'];
    $found = [];
    foreach ($grants as $grant) {
        if (preg_match('/\AGRANT USAGE ON \*\.\* TO .+\z/D', $grant) === 1
            && !str_contains($grant, 'WITH GRANT OPTION')) {
            continue;
        }
        if (preg_match('/\AGRANT ([A-Z, ]+) ON `([^`]+)`\.\* TO .+\z/D', $grant, $match) !== 1
            || str_contains($grant, 'WITH GRANT OPTION')) {
            throw new RuntimeException('Privilèges hors périmètre.');
        }
        $schema = $match[2];
        if (!$partialRevokes && preg_match('/(?<!\\\\)[_%]/', $schema) === 1) {
            throw new RuntimeException('Périmètre de privilèges contenant un joker.');
        }
        if (str_replace(['\\_', '\\%'], ['_', '%'], $schema) !== 'secure_payroll_validation_03b') {
            throw new RuntimeException('Autre base accessible.');
        }
        foreach (explode(', ', $match[1]) as $privilege) {
            if (!in_array($privilege, $allowed, true)) {
                throw new RuntimeException('Privilège non nécessaire.');
            }
            $found[$privilege] = true;
        }
    }
    foreach ($allowed as $privilege) {
        if (!isset($found[$privilege])) {
            throw new RuntimeException('Privilèges de validation incomplets.');
        }
    }
}
