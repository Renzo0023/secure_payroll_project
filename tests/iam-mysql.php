<?php

declare(strict_types=1);
if (PHP_SAPI!=='cli' || ($argv[1]??'')!=='--isolated') { exit(2); }
require dirname(__DIR__).'/app/bootstrap.php';
$count=0;
function check(bool $ok,string $name): void { global $count;if (!$ok) { throw new RuntimeException($name); }++$count; }
function denied(callable $run,string $token): void { try { $run(); } catch (PDOException $e) { check(str_contains((string)($e->errorInfo[2]??''),$token),'refusal '.$token);return; } throw new RuntimeException('Expected '.$token); }
try {
    $socket=getenv('PAYROLL_TEST_SOCKET');
    if (!is_string($socket)||!preg_match('~\A/tmp/securepayroll-mysql-[A-Za-z0-9_-]+/mysql.sock\z~D',$socket)) { exit(2); }
    $db=new PDO('mysql:unix_socket='.$socket.';dbname=secure_payroll;charset=utf8mb4','svc_php',getenv('PAYROLL_TEST_PASSWORD'),[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_EMULATE_PREPARES=>false]);
    $db->exec("SET SESSION time_zone='+00:00'");
    check(realpath($db->query('SELECT @@datadir')->fetchColumn())===realpath(getenv('PAYROLL_TEST_DATADIR')),'private datadir');
    check((int)$db->query('SELECT @@skip_networking')->fetchColumn()===1,'no network');
    $repo=new App\Auth\IAMRepository($db);$target=(int)getenv('IAM_TEST_TARGET');
    check(count($repo->overview(7,1)['roles'])===6,'admin overview');
    check(count($repo->overview(6,1)['roles'])===6,'auditor overview');
    foreach ([1,2,3,4,5] as $actor) { denied(fn()=>$repo->overview($actor,1),'PAY_FORBIDDEN'); }
    foreach ([1,2,3,4,5,6] as $actor) { denied(fn()=>$repo->grant($target,'employee','Forbidden',$actor),'PAY_FORBIDDEN'); }
    denied(fn()=>$repo->grant(7,'employee','Self role',7),'IAM_FORBIDDEN');
    denied(fn()=>$repo->grant((int)getenv('IAM_TEST_DISABLED'),'employee','Disabled',7),'IAM_INVALID');
    denied(fn()=>$repo->grant((int)getenv('IAM_TEST_ARCHIVED'),'employee','Archived',7),'IAM_INVALID');
    denied(fn()=>$repo->grant((int)getenv('IAM_TEST_FUTURE'),'hr_manager','Future conflict',7),'IAM_CONFLICT');
    denied(fn()=>$repo->grant($target,"employee' OR 1=1 --",'SQL injection role',7),'IAM_INVALID');
    denied(fn()=>$repo->grant($target,'employee',str_repeat('x',256),7),'IAM_INVALID');
    $repo->grant($target,'finance_manager','Independent controlled grant',7);
    denied(fn()=>$repo->grant($target,'hr_manager','Incompatible',7),'IAM_CONFLICT');
    denied(fn()=>$repo->grant($target,'finance_manager','Duplicate',7),'IAM_CONFLICT');
    $find=static function(string $role) use ($repo,$target): array {
        foreach ($repo->overview(7,1)['assignments'] as $assignment) { if ((int)$assignment['account_id']===$target && $assignment['code']===$role && $assignment['revoked_at']===null) { return $assignment; } }
        throw new RuntimeException('Assignment missing');
    };
    $finance=$find('finance_manager');
    denied(fn()=>$repo->revoke((int)$finance['id'],'Auditor cannot revoke',6),'PAY_FORBIDDEN');
    $repo->revoke((int)$finance['id'],'Controlled revocation',7);
    denied(fn()=>$repo->revoke((int)$finance['id'],'Duplicate revocation',7),'IAM_STATE');
    $repo->grant($target,'hr_manager','Evidence <script>iam</script>',7);
    $repo->grant($target,'employee','Employee can coexist',7);
    check($find('hr_manager')['code']==='hr_manager' && $find('employee')['code']==='employee','employee coexistence');
    $repo->grant((int)getenv('IAM_TEST_EXPIRED'),'hr_manager','Expired role does not conflict',7);
    check(true,'expired role ignored');
    $hr=$find('hr_manager');$repo->revoke((int)$hr['id'],'Preserve history',7);
    $repo->grant($target,'security_auditor','Temporary audit permission',7);
    check(count($repo->overview($target,1)['roles'])===6,'new auditor can read');
    $audit=$find('security_auditor');$repo->revoke((int)$audit['id'],'Revoke read permission',7);
    denied(fn()=>$repo->overview($target,1),'PAY_FORBIDDEN');
    $all=$repo->overview(7,1)['assignments'];
    check(count(array_filter($all,fn(array $r):bool=>(int)$r['account_id']===$target && $r['revoked_at']!==null))===3,'revoked history retained');
    check(!str_contains(json_encode($repo->overview(7,1)),'password_hash'),'no credential exposure');
    foreach (['INSERT INTO role_assignments(account_id,role_id,grant_reason) VALUES (1,1,\'Bypass\')','UPDATE role_assignments SET revoked_at=CURRENT_TIMESTAMP(6)','DELETE FROM role_assignments'] as $sql) { denied(fn()=>$db->exec($sql),'denied'); }
    echo "$count isolated IAM SQL checks passed.\n";
} catch (Throwable $e) {
    fwrite(STDERR,$e instanceof PDOException ? 'IAM SQL failure code '.($e->errorInfo[1]??0).' at line '.$e->getLine()."; driver details withheld.\n" : 'IAM failure: '.$e->getMessage()."\n");exit(1);
}
