<?php

declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}
require dirname(__DIR__) . '/app/bootstrap.php';
require dirname(__DIR__) . '/app/Web/helpers.php';

$directory = null;
$exitCode = 0;
try {
    if (!function_exists('posix_geteuid') || posix_geteuid() === 0
        || getenv('DB_NAME') !== 'secure_payroll' || getenv('DB_USER') !== 'svc_php') {
        throw new RuntimeException();
    }
    $payload = json_decode(stream_get_contents(STDIN), true, 8, JSON_THROW_ON_ERROR);
    $directory = sys_get_temp_dir() . '/payroll-check-' . bin2hex(random_bytes(12));
    if (!mkdir($directory, 0700)) {
        throw new RuntimeException();
    }
    ini_set('session.save_path', $directory);
    \App\Security\Session::start();
    $_SESSION['language'] = in_array($payload['language'] ?? null, ['fr', 'en'], true) ? $payload['language'] : 'fr';
    $db = \App\Database\Connection::connect();
    $db->exec("SET SESSION time_zone='+00:00'");
    if ($db->query('SELECT CURRENT_USER()')->fetchColumn() !== 'svc_php@localhost') {
        throw new RuntimeException();
    }
    $auth = new \App\Auth\AuthService($db);
    if (!is_string($payload['password'] ?? null) || !$auth->login('rh.demo', $payload['password'])) {
        throw new RuntimeException();
    }
    unset($payload['password']);
    $user = $auth->currentUser();
    if ($user === null) {
        throw new RuntimeException();
    }
    foreach (['employees.read', 'employees.create', 'employees.update'] as $permission) {
        if (!\App\Auth\AuthService::can($user, $permission)) {
            throw new RuntimeException();
        }
    }
    $repository = new \App\HR\EmployeeRepository($db);
    if ($repository->listing('DEMO-HR-001', 1)['total'] !== 1
        || $repository->find((int) $user['employee_id']) === null) {
        throw new RuntimeException();
    }
    echo t('setup.check_ok'), PHP_EOL;
} catch (Throwable) {
    fwrite(STDERR, t('setup.check_failed') . PHP_EOL);
    $exitCode = 1;
} finally {
    if (session_status() === PHP_SESSION_ACTIVE) {
        $_SESSION = [];
        session_destroy();
    }
    if ($directory !== null && is_dir($directory)) {
        rmdir($directory);
    }
}
exit($exitCode);
