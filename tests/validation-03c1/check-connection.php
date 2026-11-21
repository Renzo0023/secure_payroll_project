<?php

declare(strict_types=1);

// Invoqué uniquement par --run ; aucune connexion à l’inclusion de admin-connection.php.
require __DIR__ . '/admin-connection.php';
try {
    $pdo = validationConnection(false);
    $row = $pdo->query('SELECT CURRENT_USER() AS identity, @@server_uuid AS uuid, @@socket AS socket, @@global.log_bin AS log_bin, @@global.log_bin_trust_function_creators AS trust_creators')->fetch();
    echo json_encode($row, JSON_THROW_ON_ERROR);
} catch (Throwable) {
    fwrite(STDERR, "Connexion de validation refusée : vérifier en privé les variables et les privilèges limités à la cible.\n");
    exit(1);
}
