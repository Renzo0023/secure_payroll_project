<?php

declare(strict_types=1);
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
if ($argc !== 2 || $argv[1] !== '--verify') {
    fwrite(STDERR, "Usage: php tests/compensation-readiness.php --verify\n"); exit(2);
}
require dirname(__DIR__) . '/app/bootstrap.php';
try {
    $db = App\Database\Connection::connect();
    $db->exec("SET SESSION time_zone='+00:00'");
    $checks = [
        'MAD columns' => ["SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('compensation_requests','salary_conditions') AND COLUMN_NAME='currency' AND COLUMN_DEFAULT='MAD' AND CHARACTER_MAXIMUM_LENGTH=3", 2],
        'Compensation tables' => ["SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN ('compensation_requests','compensation_decisions','salary_conditions','compensation_history') AND ENGINE='InnoDB'", 4],
        'Six roles' => ['SELECT COUNT(*) FROM roles', 6],
        'Independent demo identities' => ["SELECT COUNT(DISTINCT employee_id) FROM accounts WHERE login IN ('rh.demo','finance.demo') AND disabled_at IS NULL", 2],
        'Approved salary integrity' => ["SELECT COUNT(*) FROM salary_conditions s
            LEFT JOIN compensation_decisions d ON d.id=s.decision_id AND d.request_id=s.request_id
            LEFT JOIN compensation_requests q ON q.id=s.request_id
            WHERE d.id IS NULL OR q.id IS NULL OR d.decision<>'approved'
            OR s.employee_id<>q.employee_id OR s.contract_id<>q.contract_id
            OR s.monthly_amount<>q.monthly_amount OR s.currency<>q.currency OR s.effective_on<>q.effective_on
            OR d.approver_employee_id=q.requester_employee_id OR d.approver_employee_id=s.employee_id", 0],
        'Decision salary coverage' => ["SELECT COUNT(*) FROM compensation_decisions d
            LEFT JOIN salary_conditions s ON s.decision_id=d.id AND s.request_id=d.request_id
            WHERE (d.decision='approved' AND s.id IS NULL) OR (d.decision='rejected' AND s.id IS NOT NULL)", 0],
    ];
    $ok = true;
    foreach ($checks as $label => [$sql, $expected]) {
        $pass = (int) $db->query($sql)->fetchColumn() === $expected;
        echo ($pass ? 'PASS ' : 'FAIL ') . $label . PHP_EOL;
        $ok = $ok && $pass;
    }
    // Public service routines only; hidden owner metadata needs the separate DBA review.
    foreach (['compensation_submit', 'compensation_decide'] as $routine) {
        $query = $db->prepare("SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=DATABASE() AND ROUTINE_NAME=? AND DEFINER='compensation_owner@localhost' AND SECURITY_TYPE='DEFINER'");
        $query->execute([$routine]);
        $pass = (int) $query->fetchColumn() === 1;
        echo ($pass ? 'PASS ' : 'FAIL ') . $routine . PHP_EOL;
        $ok = $ok && $pass;
    }
    echo "Read-only readiness check; no workflow or owner privileges validated.\n";
    exit($ok ? 0 : 1);
} catch (Throwable) {
    fwrite(STDERR, "Readiness unavailable: check private connection configuration and installation.\n"); exit(1);
}
