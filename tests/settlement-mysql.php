<?php

declare(strict_types=1);
if (PHP_SAPI !== 'cli' || ($argv[1] ?? '') !== '--isolated') { exit(2); }
require dirname(__DIR__).'/app/bootstrap.php';
$count=0;
function check(bool $ok,string $name): void { global $count; if (!$ok) { throw new RuntimeException($name); } ++$count; }
function reject(callable $run,string $token): void {
    try { $run(); } catch (PDOException $e) { check(str_contains((string)($e->errorInfo[2]??''),$token),'SQL refusal '.$token); return; }
    throw new RuntimeException('Expected refusal '.$token);
}
try {
    $socket=getenv('PAYROLL_TEST_SOCKET');
    if (!is_string($socket) || !preg_match('~\A/tmp/securepayroll-mysql-[A-Za-z0-9_-]+/mysql.sock\z~D',$socket)) { exit(2); }
    $db=new PDO('mysql:unix_socket='.$socket.';dbname=secure_payroll;charset=utf8mb4','svc_php',getenv('PAYROLL_TEST_PASSWORD'),
        [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_EMULATE_PREPARES=>false]);
    $db->exec("SET SESSION time_zone='+00:00'");
    check(realpath($db->query('SELECT @@datadir')->fetchColumn())===realpath(getenv('PAYROLL_TEST_DATADIR')),'private datadir');
    check((int)$db->query('SELECT @@skip_networking')->fetchColumn()===1,'no networking');
    $repo=new App\Payroll\Repository($db);
    $run=static fn(string $action,int $target=0,int $expected=0,array $amounts=[null,null,null],string $ref='',int $actor=3,string $reason='Fictional isolated settlement') =>
        $repo->settle([3,$action,$target,$expected,...$amounts,$ref,$reason,$actor]);
    $summary=static fn(int $actor=3)=>$repo->settlement(3,$actor);
    check($summary()['summary']['balance']==='10600.00','original published due');
    reject(fn()=>$repo->settlement(3,5),'PAY_NOT_FOUND');
    reject(fn()=>$repo->settlement(1,4),'PAY_NOT_FOUND');
    reject(fn()=>$repo->settlement(3,7),'PAY_FORBIDDEN');
    check($summary(6)['summary']['net_amount']==='10600.00','auditor read');
    foreach ([1,3,4,5,6,7] as $actor) { reject(fn()=>$run('pay',0,0,[null,null,null],'PAY-FORBID-'.$actor,$actor),'PAY_FORBIDDEN'); }
    reject(fn()=>$run('pay',0,0,[null,null,null],"x' OR 1=1 --",2),'PAY_INVALID');
    $payment=$run('pay',0,0,[null,null,null],'PAY-ORIGINAL-001',2);
    check($payment>0 && $summary()['summary']['balance']==='0.00','full fictional original payment');
    reject(fn()=>$run('pay',0,0,[null,null,null],'PAY-ORIGINAL-001',2),'PAY_STATE');
    reject(fn()=>$run('pay',0,0,[null,null,null],'PAY-OTHER-REF',2),'PAY_STATE');
    reject(fn()=>$run('correct',0,0,['10000.00','501.00','0.00']),'PAY_CAP');
    reject(fn()=>$run('correct',0,0,['1.00','0.00','2.00']),'PAY_INVALID');
    foreach ([1,2,4,5,6,7] as $actor) { reject(fn()=>$run('correct',0,0,['10800.00','300.00','100.00'],'',$actor),'PAY_FORBIDDEN'); }
    $correction=$run('correct',0,0,['10800.00','300.00','100.00'],'',3,'Evidence <script>fictional</script>');
    check($summary(4)['corrections']===[],'employee cannot read correction draft');
    reject(fn()=>$run('correct',0,0,['10800.00','300.00','100.00']),'PAY_STATE');
    reject(fn()=>$run('pay',0,0,[null,null,null],'PAY-PENDING-001',2),'PAY_STATE');
    reject(fn()=>$run('published',$correction),'PAY_STATE');
    reject(fn()=>$run('approved',$correction,0,[null,null,null],'',2),'PAY_STATE');
    $run('verified',$correction);
    reject(fn()=>$run('approved',$correction),'PAY_FORBIDDEN');
    $run('approved',$correction,0,[null,null,null],'',2);
    check($summary()['summary']['net_amount']==='10600.00','approval does not publish');
    $run('published',$correction);
    check($summary(4)['summary']['net_amount']==='11000.00' && count($summary(4)['corrections'])===1,'published correction visible');
    reject(fn()=>$run('pay',0,0,[null,null,null],'PAY-STALE-001',2),'PAY_STALE');
    reject(fn()=>$run('pay',0,$correction,[null,null,null],'PAY-ORIGINAL-001',2),'Duplicate');
    check($summary()['summary']['balance']==='400.00','duplicate reference transaction rolled back');
    $run('pay',0,$correction,[null,null,null],'PAY-SUPPLEMENT-001',2);
    $ledger=$summary()['ledger'];
    check(count($ledger)===2 && $ledger[1]['amount']==='400.00','only supplementary amount paid');
    check($summary()['summary']['balance']==='0.00','supplement settled');
    $lower=$run('correct',0,$correction,['10200.00','300.00','100.00']);
    $run('verified',$lower,$correction); $run('approved',$lower,$correction,[null,null,null],'',2); $run('published',$lower,$correction);
    check($summary()['summary']['balance']==='-600.00','overpayment explicitly visible');
    reject(fn()=>$run('pay',0,$lower,[null,null,null],'PAY-OVERPAID-001',2),'PAY_STATE');
    $recovery=$run('recover_request',0,$lower);
    reject(fn()=>$run('recover_request',0,$lower),'PAY_STATE');
    reject(fn()=>$run('correct',0,$lower,['10100.00','300.00','100.00']),'PAY_STATE');
    reject(fn()=>$run('recover_receive',$recovery,$lower,[null,null,null],'REC-EARLY-001'),'PAY_STATE');
    reject(fn()=>$run('recover_approve',$recovery,$lower),'PAY_FORBIDDEN');
    check($summary(4)['recoveries']===[],'pending recovery hidden from employee');
    $run('recover_approve',$recovery,$lower,[null,null,null],'',2);
    check($summary()['summary']['balance']==='-600.00','approval does not record receipt');
    $run('recover_receive',$recovery,$lower,[null,null,null],'REC-RECEIPT-001');
    check($summary()['summary']['balance']==='0.00','controlled recovery settled');
    check($summary(4)['recoveries'][0]['status']==='received','receipt visible to employee');
    reject(fn()=>$run('recover_receive',$recovery,$lower,[null,null,null],'REC-RECEIPT-002'),'PAY_STATE');
    $rejected=$run('correct',0,$lower,['10000.00','300.00','100.00']);
    $run('verified',$rejected,$lower); $run('rejected',$rejected,$lower,[null,null,null],'',2);
    reject(fn()=>$run('approved',$rejected,$lower,[null,null,null],'',2),'PAY_STATE');
    check(count($summary(4)['corrections'])===2,'rejected versions hidden from employee');
    $original=$repo->detail(3,4);
    check($original['row']['net_amount']==='10600.00' && $original['row']['version_no']===3,'original preserved');
    foreach (['payslip_corrections','correction_events','settlement_ledger','recovery_requests','recovery_events'] as $table) {
        reject(fn()=>$db->query('SELECT * FROM '.$table),'denied');
        reject(fn()=>$db->exec('UPDATE '.$table.' SET id=id'),'denied');
    }
    echo "$count real isolated settlement checks passed.\n";
} catch (Throwable $error) {
    if ($error instanceof PDOException) { fwrite(STDERR,'Settlement SQL failure code '.($error->errorInfo[1]??0).' at line '.$error->getLine()."; driver details withheld.\n"); }
    else { fwrite(STDERR,'Settlement failure: '.$error->getMessage()."\n"); }
    exit(1);
}
