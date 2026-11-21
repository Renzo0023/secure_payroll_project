<?php

declare(strict_types=1);
if (PHP_SAPI!=='cli' || $argc!==2 || $argv[1]!=='--isolated') { exit(2); }
require dirname(__DIR__).'/app/bootstrap.php';
$count=0;
function verify(bool $ok,string $name): void {
    global $count;
    if (!$ok) { fwrite(STDERR,"FAIL $name\n"); exit(1); }
    ++$count;
}
function call(PDO $db,string $sql,array $params): array {
    $query=$db->prepare($sql);
    try {
        $query->execute($params); $sets=[];
        do { if ($query->columnCount()>0) { $sets[]=$query->fetchAll(); } } while($query->nextRowset());
        return $sets;
    } finally { $query->closeCursor(); }
}
function id(PDO $db,string $sql,array $params): int { return (int)call($db,$sql,$params)[0][0]['id']; }
function denied(callable $action,string $token): void {
    try { $action(); } catch (PDOException $e) {
        verify(str_contains($e->errorInfo[2]??'',$token),'expected SQL refusal '.$token); return;
    }
    verify(false,'missing SQL refusal '.$token);
}
try {
    $socket=getenv('PAYROLL_TEST_SOCKET'); $directory=getenv('PAYROLL_TEST_DATADIR');
    if (!is_string($socket) || !preg_match('~\A/tmp/securepayroll-mysql-[A-Za-z0-9_\-]+/mysql\.sock\z~D',$socket)
        || dirname($socket).'/data'!==$directory || getenv('PAYROLL_TEST_PASSWORD')===false) { throw new RuntimeException(); }
    $db=new PDO('mysql:unix_socket='.$socket.';dbname=secure_payroll;charset=utf8mb4','svc_php',getenv('PAYROLL_TEST_PASSWORD'),
        [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_EMULATE_PREPARES=>false]);
    $db->exec("SET SESSION time_zone='+00:00'");
    verify(realpath($db->query('SELECT @@datadir')->fetchColumn())===realpath($directory),'private data directory');
    verify((int)$db->query('SELECT @@skip_networking')->fetchColumn()===1,'no network');
    verify($db->query('SELECT CURRENT_USER()')->fetchColumn()==='svc_php@localhost','non-root application account');
    foreach ([4,5] as $employee) {
        $contract=id($db,'CALL hr_create_contract(?,?,?,?,?,?)',[$employee,'LAB-CONTRACT-'.$employee,'permanent','2026-11-03',null,1]);
        $request=id($db,'CALL compensation_submit(?,?,?,?,?,?)',[$employee,$contract,'12000.00','2026-11-03','Fictional salary',1]);
        denied(fn()=>id($db,'CALL compensation_decide(?,?,?,?)',[$request,'approved','HR forbidden',1]),'COMP_FORBIDDEN');
        id($db,'CALL compensation_decide(?,?,?,?)',[$request,'approved','Independent Finance',2]);
        denied(fn()=>id($db,'CALL compensation_decide(?,?,?,?)',[$request,'approved','Duplicate',2]),'COMP_');
    }
    $repo=new App\Payroll\Repository($db);
    denied(fn()=>$repo->createPeriod('2026-11','500.00','500.00','No finance',1),'PAY_FORBIDDEN');
    $period=$repo->createPeriod('2026-11','500.00','500.00','Fictional explicit caps',2);
    denied(fn()=>$repo->calculate($period,4,4),'PAY_FORBIDDEN');
    $first=$repo->calculate($period,4,3);
    $detail=$repo->detail($first,3);
    verify($detail['row']['net_amount']==='11200.00','initial calendar prorating');
    denied(fn()=>$repo->detail($first,4),'PAY_NOT_FOUND');
    denied(fn()=>$repo->transition($first,'published','Too early',3),'PAY_STATE');
    $bonus=$repo->submitInput($period,4,'bonus','300.00','2026-11-01','2026-11-30','Fictional bonus',1);
    denied(fn()=>$repo->calculate($period,4,3),'PAY_PENDING');
    denied(fn()=>$repo->decideInput($bonus,'approved','Wrong role',1),'PAY_FORBIDDEN');
    $repo->decideInput($bonus,'approved','Independent Finance',2);
    denied(fn()=>$repo->transition($first,'verified','Stale sources',3),'PAY_STALE');
    $second=$repo->calculate($period,4,3);
    $repo->transition($second,'verified','Amounts checked',3);
    $repo->transition($second,'rejected','Fictional correction required',2);
    denied(fn()=>$repo->transition($second,'approved','Cannot approve rejected',2),'PAY_FROZEN');
    $extra=$repo->submitInput($period,4,'bonus','201.00','2026-11-01','2026-11-30','Beyond cap',1);
    denied(fn()=>$repo->decideInput($extra,'approved','Too much',2),'PAY_CAP');
    $repo->decideInput($extra,'rejected','Cap enforced',2);
    $deduction=$repo->submitInput($period,4,'deduction','100.00','2026-11-01','2026-11-30','Fictional deduction',1);
    $repo->decideInput($deduction,'approved','Independent Finance',2);
    $unpaid=$repo->submitInput($period,4,'unpaid_leave','0.00','2026-11-10','2026-11-11','Two unpaid days',1);
    $repo->decideInput($unpaid,'approved','Independent Finance',2);
    $paid=$repo->submitInput($period,4,'paid_leave','0.00','2026-11-12','2026-11-13','Two paid days',1);
    $repo->decideInput($paid,'approved','Independent Finance',2);
    $overlap=$repo->submitInput($period,4,'paid_leave','0.00','2026-11-11','2026-11-12','Overlapping days',1);
    denied(fn()=>$repo->decideInput($overlap,'approved','Overlapping',2),'PAY_OVERLAP');
    $repo->decideInput($overlap,'rejected','Overlap refused',2);
    $third=$repo->calculate($period,4,3);
    $detail=$repo->detail($third,3); $row=$detail['row'];
    verify($row['base_amount']==='10400.00' && $row['gross_amount']==='10700.00' && $row['net_amount']==='10600.00','SQL financial totals');
    $days=array_map(static fn(array $d):array=>['date'=>$d['date'],'salary_condition_id'=>(int)$d['salary_condition_id'],
        'monthly_amount'=>$d['monthly_amount'],'currency'=>'MAD','paid'=>(bool)$d['paid']],$row['snapshot']['days']);
    $expected=App\Payroll\Calculator::calculate('2026-11',$days,'300.00','100.00','500.00','500.00');
    verify($expected['net']===$row['net_amount'] && $expected['base']===$row['base_amount'],'PHP/SQL calculation parity');
    $repo->transition($third,'verified','Amounts and sources checked',3);
    denied(fn()=>$repo->transition($third,'approved','Payroll cannot approve',3),'PAY_FORBIDDEN');
    $repo->transition($third,'approved','Independent Finance approval',2);
    denied(fn()=>$repo->detail($third,4),'PAY_NOT_FOUND');
    denied(fn()=>$repo->calculate($period,4,3),'PAY_FROZEN');
    denied(fn()=>$repo->submitInput($period,4,'bonus','1.00','2026-11-01','2026-11-30','Frozen payroll',1),'PAY_FROZEN');
    $repo->transition($third,'published','Separate publication',3);
    verify((int)$repo->detail($third,4)['row']['employee_id']===4,'employee reads published own payslip');
    denied(fn()=>$repo->detail($third,5),'PAY_NOT_FOUND');
    verify($repo->overview(5,1)['calculations']===[],'foreign employee list isolation');
    verify(count($repo->overview(4,1)['calculations'])===1,'employee sees only published version');
    verify(count($repo->detail($third,4)['versions'])===1,'employee history hides drafts');
    verify(count($repo->detail($third,3)['versions'])===3,'staff retains all versions');
    verify(count($repo->overview(6,1)['calculations'])===3,'auditor read');
    denied(fn()=>$repo->overview(7,1),'PAY_FORBIDDEN');
    denied(fn()=>$db->query('SELECT * FROM payroll_calculations'),'denied');
    denied(fn()=>$db->exec('UPDATE payroll_calculations SET net_amount=1 WHERE id=1'),'denied');
    denied(fn()=>call($db,'CALL payroll_build(?,?,@a,@b,@c,@d)',[$period,4]),'denied');
    echo "$count real isolated MySQL checks passed. Main instance never connected.\n";
} catch (Throwable $error) {
    $code=$error instanceof PDOException?(int)($error->errorInfo[1]??0):0;
    fwrite(STDERR,'Isolated integration failed: '.get_class($error).' code '.$code.' at line '.$error->getLine().". No driver message or credentials printed.\n");
    exit(1);
}
