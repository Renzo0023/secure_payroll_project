<?php

declare(strict_types=1);
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
if ($argc !== 2 || $argv[1] !== '--verify') { fwrite(STDERR,"Explicit --verify required.\n"); exit(2); }
require dirname(__DIR__) . '/app/bootstrap.php';
// No session file or credential artifact is produced by this CLI verification.
session_set_save_handler(new class implements SessionHandlerInterface {
    public function open(string $path,string $name): bool { return true; }
    public function close(): bool { return true; }
    public function read(string $id): string|false { return ''; }
    public function write(string $id,string $data): bool { return true; }
    public function destroy(string $id): bool { return true; }
    public function gc(int $max_lifetime): int|false { return 0; }
},true);
try {
    $payload=json_decode(stream_get_contents(STDIN),true,8,JSON_THROW_ON_ERROR);
    if (!is_string($payload['login']??null) || !is_string($payload['password']??null)) { throw new RuntimeException(); }
    if (getenv('DB_NAME')!=='secure_payroll' || getenv('DB_USER')!=='svc_php') { throw new RuntimeException(); }
    App\Security\Session::start();
    $db=App\Database\Connection::connect(); $db->exec("SET SESSION time_zone='+00:00'");
    if ($db->query('SELECT CURRENT_USER()')->fetchColumn()!=='svc_php@localhost') { throw new RuntimeException(); }
    $auth=new App\Auth\AuthService($db);
    if (!$auth->login($payload['login'],$payload['password'])) { throw new RuntimeException(); }
    unset($payload['password']);
    $user=$auth->currentUser(); if ($user===null) { throw new RuntimeException(); }
    $checks=['PASS real service connection and application authentication'];
    if (App\Auth\AuthService::can($user,'compensation.read')) {
        $comp=new App\Compensation\CompensationRepository($db);
        if (!$comp->referenceCurrencyReady()) { throw new RuntimeException(); }
        $comp->requests('pending',1);
        $checks[]='PASS MAD column configuration and compensation read';
    }
    if (!App\Auth\AuthService::can($user,'payroll.read') && !App\Auth\AuthService::can($user,'payslip.self')) {
        $checks[]='BLOCKED payroll permission absent or conflicting roles; verify installation/assignments';
        echo implode(PHP_EOL,$checks),PHP_EOL; exit(1);
    }
    $repo=new App\Payroll\Repository($db);
    $result=$repo->overview((int)$user['account_id'],1);
    $staff=App\Auth\AuthService::can($user,'payroll.read');
    if (!$staff && ($result['periods']!==[] || $result['employees']!==[] || $result['inputs']!==[])) { throw new RuntimeException(); }
    foreach ($result['calculations'] as $row) {
        if (!$staff && ((int)$row['employee_id']!==(int)$user['employee_id'] || $row['status']!=='published')) { throw new RuntimeException(); }
    }
    foreach (array_slice($result['calculations'],0,3) as $row) {
        $detail=$repo->detail((int)$row['id'],(int)$user['account_id']);
        if ((int)$detail['row']['id']!==(int)$row['id']) { throw new RuntimeException(); }
    }
    $checks[]='PASS actor-scoped payroll overview and returned payslip details';
    if ($result['calculations']===[]) { $checks[]='NOTE no accessible payslip: full published-payslip workflow remains untested'; }
    if (!$staff) {
        $probe=$payload['forbidden_payslip_id']??null;
        if (is_int($probe) && $probe>0) {
            $denied=false;
            try { $repo->detail($probe,(int)$user['account_id']); }
            catch (PDOException $exception) { $denied=str_contains($exception->errorInfo[2]??'','PAY_NOT_FOUND'); }
            if (!$denied) { throw new RuntimeException(); }
            $checks[]='PASS supplied forbidden payslip ID refused by MySQL';
        } else { $checks[]='NOTE no foreign/unpublished payslip ID supplied: negative IDOR test not executed'; }
    }
    echo implode(PHP_EOL,$checks),PHP_EOL;
} catch (Throwable) {
    fwrite(STDERR,"Live verification failed/unavailable. Check credentials, MAD setup, payroll installation and permissions privately. No business write performed.\n"); exit(1);
} finally {
    if (session_status()===PHP_SESSION_ACTIVE) { $_SESSION=[]; session_destroy(); }
}
