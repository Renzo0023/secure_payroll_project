<?php

declare(strict_types=1);
if (PHP_SAPI!=='cli' || !in_array($argv[1]??'',['--legacy','--mad'],true)) { exit(2); }
require dirname(__DIR__).'/app/bootstrap.php';
$count=0;
function verify(bool $ok,string $name): void { global $count;if (!$ok) { throw new RuntimeException($name); }++$count; }
function call(PDO $db,string $sql,array $parameters): array {
 $q=$db->prepare($sql);try { $q->execute($parameters);$sets=[];do { if ($q->columnCount()>0) {$sets[]=$q->fetchAll();} } while ($q->nextRowset());return $sets; } finally {$q->closeCursor();}
}
function id(PDO $db,string $sql,array $parameters): int {return (int)call($db,$sql,$parameters)[0][0]['id'];}
function denied(callable $run,string $token): void {try {$run();} catch(PDOException $e) {verify(str_contains((string)($e->errorInfo[2]??''),$token),'refusal '.$token);return;}throw new RuntimeException('Missing refusal '.$token);}
try {
 $socket=getenv('MAD_TEST_SOCKET');
 if (!is_string($socket)||!preg_match('~\A/(?:var/)?tmp/securepayroll-mysql-[A-Za-z0-9_-]+/mysql.sock\z~D',$socket)) {exit(2);}
 $db=new PDO('mysql:unix_socket='.$socket.';dbname=secure_payroll;charset=utf8mb4','svc_php',getenv('MAD_TEST_PASSWORD'),[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_EMULATE_PREPARES=>false]);
 $db->exec("SET SESSION time_zone='+00:00'");
 verify(realpath($db->query('SELECT @@datadir')->fetchColumn())===realpath(dirname($socket).'/data'),'private datadir');
 verify((int)$db->query('SELECT @@skip_networking')->fetchColumn()===1,'network disabled');
 $repo=new App\Compensation\CompensationRepository($db);
 if ($argv[1]==='--legacy') {
  verify(!$repo->referenceCurrencyReady(),'PHP blocks MAD forms on legacy schema');
  foreach ([3,4,5] as $employee) {
   $contract=id($db,'CALL hr_create_contract(?,?,?,?,?,?)',[$employee,'MAD-REPAIR-'.$employee,'permanent','2026-11-03',null,1]);
   verify($contract===$employee-2,'new fixture contract id');
   if ($employee!==5) {
    $request=id($db,'CALL compensation_submit(?,?,?,?,?,?)',[$employee,$contract,'12000.00','2026-11-03','Historical fictional UM',1]);
    if ($employee===3) {id($db,'CALL compensation_decide(?,?,?,?)',[$request,'approved','Historical Finance approval',2]);}
   }
  }
  verify($db->query('SELECT currency FROM compensation_requests ORDER BY id LIMIT 1')->fetchColumn()==='UM','fixture request UM');
  verify($db->query('SELECT currency FROM salary_conditions ORDER BY id LIMIT 1')->fetchColumn()==='UM','fixture approved salary UM');
 } else {
  verify($repo->referenceCurrencyReady(),'PHP enables MAD forms after complete patch');
  $request=id($db,'CALL compensation_submit(?,?,?,?,?,?)',[5,3,'12345.67','2026-11-03','New MAD after targeted repair',1]);
  $q=$db->prepare('SELECT currency,monthly_amount FROM compensation_requests WHERE id=?');$q->execute([$request]);$row=$q->fetch();
  verify($row['currency']==='MAD' && $row['monthly_amount']==='12345.67','new request MAD with exact decimal');
  denied(fn()=>id($db,'CALL compensation_decide(?,?,?,?)',[$request,'approved','HR cannot approve',1]),'COMP_FORBIDDEN');
  denied(fn()=>id($db,'CALL compensation_decide(?,?,?,?)',[$request,'approved','Employee cannot approve',3]),'COMP_FORBIDDEN');
  denied(fn()=>id($db,'CALL compensation_decide(?,?,?,?)',[$request,'approved','Auditor cannot approve',7]),'COMP_FORBIDDEN');
  id($db,'CALL compensation_decide(?,?,?,?)',[$request,'approved','Independent Finance MAD',2]);
  $q=$db->prepare('SELECT currency,monthly_amount FROM salary_conditions WHERE request_id=?');$q->execute([$request]);$row=$q->fetch();
  verify($row['currency']==='MAD' && $row['monthly_amount']==='12345.67','approved salary MAD and exact amount');
  denied(fn()=>id($db,'CALL compensation_decide(?,?,?,?)',[$request,'approved','Duplicate',2]),'COMP_ALREADY_DECIDED');
  denied(fn()=>id($db,'CALL compensation_decide(?,?,?,?)',[2,'approved','Do not reinterpret legacy UM',2]),'COMP_CURRENCY_REVIEW');
  denied(fn()=>id($db,'CALL compensation_submit(?,?,?,?,?,?)',[3,1,'13000.00','2026-12-01','No implicit legacy conversion',1]),'COMP_CURRENCY_REVIEW');
  denied(fn()=>id($db,'CALL compensation_submit(?,?,?,?,?,?)',[5,3,'13000.00','2026-12-01','Finance cannot submit',2]),'COMP_FORBIDDEN');
  id($db,'CALL compensation_decide(?,?,?,?)',[2,'rejected','Historical UM rejected without conversion',2]);
  verify($db->query('SELECT currency FROM compensation_requests WHERE id=2')->fetchColumn()==='UM','legacy rejected request remains UM');
  verify($db->query('SELECT monthly_amount FROM salary_conditions WHERE id=1')->fetchColumn()==='12000.00','legacy approved salary amount unchanged');
  verify($db->query('SELECT currency FROM salary_conditions WHERE id=1')->fetchColumn()==='UM','legacy approved salary currency unchanged');
  verify(str_ends_with(App\Finance\Money::format('12000.00','UM'),' UM'),'PHP display preserves UM');
  verify(str_ends_with(App\Finance\Money::format('12345.67','MAD'),' MAD'),'PHP display MAD');
  denied(fn()=>$db->exec('UPDATE salary_conditions SET monthly_amount=1'),'denied');
  denied(fn()=>call($db,'CALL compensation_check_period(?,?,?,@kind)',[3,5,'2026-12-01']),'denied');
 }
 echo "$count isolated MAD workflow checks passed (".$argv[1].").\n";
} catch(Throwable $e) {fwrite(STDERR,$e instanceof PDOException ? 'MAD workflow SQL code '.($e->errorInfo[1]??0).' line '.$e->getLine()."; driver details withheld.\n" : 'MAD workflow: '.$e->getMessage()."\n");exit(1);}
