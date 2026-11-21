<?php

declare(strict_types=1);

/*
 * Démonstration (phase 3) : stockage en clair, chiffrement, hachage et hachage sécurisé d'un mot de passe.
 * Hors ligne, sans base de données, avec des mots de passe fictifs. Les débits sont mesurés sur cette
 * machine, avec PHP sur un seul cœur : un attaquant équipé de GPU va beaucoup plus vite sur les hachages
 * rapides (SHA-256), alors qu'Argon2id, coûteux en mémoire, résiste à cette accélération.
 *
 *   php lab/password-storage-demo.php
 */

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

$secret = 'Soleil2026!';                 // mot de passe fictif de deux salariés différents
$users = ['nadia' => $secret, 'samir' => $secret, 'camille' => 'Atlas#Rabat-91'];
// Petit dictionnaire fictif : un attaquant réel en utilise des milliards (fuites publiques, règles).
$dictionary = ['123456', 'motdepasse', 'Azerty123', 'Maroc2026', 'Bonjour1', 'Paie2026!', 'Casablanca1',
               'Admin123', 'Printemps2026', 'Soleil2025!', 'Soleil2026!', 'Rabat2026', 'Welcome1'];

$line = static fn (string $text = '') => print($text . PHP_EOL);
$title = static function (string $text) use ($line): void {
    $line();
    $line(str_repeat('=', 78));
    $line($text);
    $line(str_repeat('=', 78));
};
$attack = static function (callable $matches) use ($dictionary): array {
    $start = hrtime(true);
    foreach ($dictionary as $candidate) {
        if ($matches($candidate)) {
            return [$candidate, (hrtime(true) - $start) / 1e9];
        }
    }
    return [null, (hrtime(true) - $start) / 1e9];
};
$rate = static function (callable $hash, int $iterations): float {
    $start = hrtime(true);
    for ($i = 0; $i < $iterations; ++$i) {
        $hash('candidat-' . $i);
    }
    return $iterations / ((hrtime(true) - $start) / 1e9);
};
$duration = static function (float $seconds): string {
    foreach ([[31557600, 'ans'], [86400, 'jours'], [3600, 'heures'], [60, 'minutes'], [1, 'secondes']] as [$unit, $name]) {
        if ($seconds >= $unit) {
            return number_format($seconds / $unit, 1, ',', ' ') . ' ' . $name;
        }
    }
    return number_format($seconds * 1000, 2, ',', ' ') . ' ms';
};

$title('1. STOCKAGE EN CLAIR');
foreach ($users as $name => $password) {
    $line(sprintf('  %-8s | %s', $name, $password));
}
$line('  → Une fuite de la table révèle immédiatement tous les mots de passe, sans aucun calcul.');

$title('2. CHIFFREMENT (AES-256-GCM) : réversible avec la clé');
$key = random_bytes(32);
$stored = [];
foreach ($users as $name => $password) {
    $iv = random_bytes(12);
    $cipher = openssl_encrypt($password, 'aes-256-gcm', $key, OPENSSL_RAW_DATA, $iv, $tag);
    $stored[$name] = [$iv, $cipher, $tag];
    $line(sprintf('  %-8s | %s', $name, bin2hex($iv . $tag . $cipher)));
}
[$iv, $cipher, $tag] = $stored['nadia'];
$line('  Déchiffrement avec la clé : ' . openssl_decrypt($cipher, 'aes-256-gcm', $key, OPENSSL_RAW_DATA, $iv, $tag));
$line('  → Illisible sans la clé ; mais qui obtient la clé (fichier de configuration, mémoire du serveur)');
$line('    récupère tous les mots de passe en clair. Le serveur n\'a jamais besoin de relire un mot de passe :');
$line('    le chiffrement n\'est donc pas adapté. Il convient aux données à relire, comme le RIB (phase 6).');

$title('3. HACHAGE SIMPLE (SHA-256, sans sel) : irréversible, mais rapide et déterministe');
$sha = [];
foreach ($users as $name => $password) {
    $sha[$name] = hash('sha256', $password);
    $line(sprintf('  %-8s | %s', $name, $sha[$name]));
}
$line('  → nadia et samir ont la MÊME empreinte : on voit qu\'ils partagent un mot de passe, et une seule');
$line('    attaque les casse tous les deux. Des tables précalculées (« rainbow tables ») s\'appliquent directement.');
[$found, $seconds] = $attack(static fn (string $c): bool => hash_equals($sha['nadia'], hash('sha256', $c)));
$line(sprintf('  Attaque par dictionnaire : « %s » retrouvé en %s.', $found, $duration($seconds)));

$title('4. HACHAGE SALÉ (SHA-256 + sel aléatoire) : empreintes distinctes, mais toujours rapide');
$salted = [];
foreach ($users as $name => $password) {
    $salt = random_bytes(16);
    $salted[$name] = [$salt, hash('sha256', $salt . $password)];
    $line(sprintf('  %-8s | sel %s | %s', $name, bin2hex($salt), substr($salted[$name][1], 0, 32) . '…'));
}
[$salt, $digest] = $salted['nadia'];
[$found, $seconds] = $attack(static fn (string $c): bool => hash_equals($digest, hash('sha256', $salt . $c)));
$line('  → Le sel rend les empreintes uniques et les tables précalculées inutiles, mais chaque essai reste');
$line(sprintf('    très rapide : « %s » retrouvé en %s.', $found, $duration($seconds)));

$title('5. HACHAGE SÉCURISÉ (Argon2id, utilisé par SecurePayroll) : salé, lent et coûteux en mémoire');
$argon = [];
foreach ($users as $name => $password) {
    $argon[$name] = password_hash($password, PASSWORD_ARGON2ID);
    $line(sprintf('  %-8s | %s', $name, $argon[$name]));
}
$parts = explode('$', $argon['nadia']);
$line('  Format : $algorithme$version$paramètres$sel$empreinte');
$line('    ' . $parts[1] . ' | ' . $parts[2] . ' | ' . $parts[3] . ' (mémoire en Kio, itérations, parallélisme)');
$line('  → Sel aléatoire intégré : nadia et samir ont des empreintes différentes.');
[$found, $seconds] = $attack(static fn (string $c): bool => password_verify($c, $argon['nadia']));
$line(sprintf('  Attaque par dictionnaire (%d mots) : « %s » retrouvé en %s.', count($dictionary), $found, $duration($seconds)));

$title('6. COMPARAISON DES DÉBITS (cette machine, PHP, un seul cœur)');
$fast = $rate(static fn (string $c): string => hash('sha256', 'sel' . $c), 300000);
$slow = $rate(static fn (string $c): string => password_hash($c, PASSWORD_ARGON2ID), 10);
$line(sprintf('  SHA-256 salé : %s essais par seconde', number_format($fast, 0, ',', ' ')));
$line(sprintf('  Argon2id     : %s essais par seconde (%s par essai)', number_format($slow, 1, ',', ' '), $duration(1 / $slow)));
$line(sprintf('  Argon2id est environ %s fois plus lent à attaquer.', number_format($fast / $slow, 0, ',', ' ')));
$line();
$line('  Temps pour essayer un dictionnaire, à ce débit :');
$line(sprintf('  %-28s | %-18s | %s', 'Taille du dictionnaire', 'SHA-256 salé', 'Argon2id'));
foreach ([1e6 => '1 million', 1e9 => '1 milliard'] as $size => $label) {
    $line(sprintf('  %-28s | %-18s | %s', $label, $duration($size / $fast), $duration($size / $slow)));
}
$line();
$line('  Le chiffre d\'un attaquant réel est plus élevé (GPU, plusieurs machines). L\'écart entre les deux');
$line('  colonnes demeure : Argon2id exige ~64 Mio de mémoire par essai, ce qui limite le parallélisme.');
$line('  Un mot de passe du dictionnaire reste néanmoins retrouvé : la longueur et l\'unicité des mots de');
$line('  passe restent nécessaires, d\'où les mots de passe de l\'installateur : 24 octets aléatoires, soit 32 caractères.');
