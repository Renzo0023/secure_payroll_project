<?php
declare(strict_types=1);
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
ini_set('display_errors','0');
ini_set('zend.exception_ignore_args','1');
try {
    $input=json_decode(stream_get_contents(STDIN),true,16,JSON_THROW_ON_ERROR);
    $payslipId=isset($input['payslip_id']) ? filter_var($input['payslip_id'],FILTER_VALIDATE_INT,['options'=>['min_range'=>1]]) : null;
    foreach (['DB_HOST'=>'localhost','DB_PORT'=>'3306','DB_NAME'=>'secure_payroll','DB_USER'=>'svc_php','DB_PASSWORD'=>$input['database_password']] as $key=>$value) { putenv($key.'='.$value); }
    unset($input);
    require dirname(__DIR__).'/app/bootstrap.php';
    $db=App\Database\Connection::connect();
    $db->exec("SET SESSION time_zone='+00:00'");
    $db->beginTransaction();
    $people=$db->query("SELECT e.id,e.employee_number,e.first_name,e.last_name,a.id AS account_id,a.login FROM employees e LEFT JOIN accounts a ON a.employee_id=e.id WHERE e.employee_number='EMP-2026-001' OR a.login IN ('rh.demo','finance.demo','payroll.demo','employee.demo','admin.demo','audit.demo') ORDER BY e.id")->fetchAll();
    $nadia=array_values(array_filter($people,fn($p)=>$p['employee_number']==='EMP-2026-001'));
    if (count($nadia)!==1) { throw new RuntimeException(); }
    $q=$db->prepare('SELECT c.reference,c.starts_on,c.effective_ends_on,s.monthly_amount,s.currency,s.effective_on,d.decision FROM employment_contracts c JOIN salary_conditions s ON s.contract_id=c.id JOIN compensation_decisions d ON d.id=s.decision_id WHERE c.employee_id=? ORDER BY s.effective_on');
    $q->execute([$nadia[0]['id']]);$salary=$q->fetchAll();
    $counts=[];$fingerprints=[];
    foreach (['compensation_requests','compensation_decisions','compensation_history','salary_conditions'] as $table) {
        $rows=$db->query('SELECT * FROM '.$table.' ORDER BY id')->fetchAll();
        $counts[$table]=count($rows);$fingerprints[$table]=hash('sha256',json_encode($rows,JSON_THROW_ON_ERROR));
    }
    $grants=$db->query('SHOW GRANTS')->fetchAll(PDO::FETCH_COLUMN);
    $db->commit();
    $finance=array_values(array_filter($people,fn($p)=>$p['login']==='finance.demo'));
    if(count($finance)!==1) {throw new RuntimeException();}
    $repo=new App\Payroll\Repository($db);
    $overview=$repo->overview((int)$finance[0]['account_id'],1);
    $iam=array_values(array_filter($people,fn($p)=>in_array($p['login'],['admin.demo','audit.demo'],true)));
    $iamResult=[];
    foreach($iam as $person) { $iamResult[$person['login']]=(new App\Auth\IAMRepository($db))->overview((int)$person['account_id'],1); }
    $detail=$payslipId ? $repo->detail($payslipId,(int)$finance[0]['account_id']) : null;
    $settlement=$detail && $detail['row']['status']==='published' ? $repo->settlement($payslipId,(int)$finance[0]['account_id']) : null;
    echo json_encode(['people'=>$people,'salary'=>$salary,'compensation_counts'=>$counts,'compensation_fingerprints'=>$fingerprints,'overview'=>$overview,'service_grants'=>$grants,'iam'=>$iamResult,'detail'=>$detail,'settlement'=>$settlement],JSON_THROW_ON_ERROR);
} catch (Throwable) { fwrite(STDERR,"Demo state unavailable; no driver details or secrets printed.\n");exit(1); }
