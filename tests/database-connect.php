<?php

declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

// Exécution volontaire uniquement, une fois les identifiants configurés.
if ($argc !== 2 || $argv[1] !== '--connect') {
    fwrite(STDERR, "Usage : php tests/database-connect.php --connect\nAucune connexion effectuée.\n");
    exit(2);
}

require dirname(__DIR__) . '/app/bootstrap.php';
require dirname(__DIR__) . '/app/Database/Connection.php';

try {
    $connection = \App\Database\Connection::connect();
    $result = $connection->query('SELECT 1')->fetchColumn();
    if ((int) $result !== 1) {
        throw new RuntimeException('Résultat inattendu.');
    }
    fwrite(STDOUT, "Connexion et SELECT 1 réussis.\n");
} catch (Throwable) {
    fwrite(STDERR, "Vérification de connexion échouée. Vérifier la configuration et le service en privé.\n");
    exit(1);
}
