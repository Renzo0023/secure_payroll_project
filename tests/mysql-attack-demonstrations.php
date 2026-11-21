<?php

declare(strict_types=1);
if(PHP_SAPI!=='cli'||$argc!==2||!in_array($argv[1],['--before','--after'],true)){exit(2);}
$count=0;
function check(bool $ok,string $name):void{global $count;if(!$ok){fwrite(STDERR,"FAIL isolated demonstration: $name\n");exit(1);}++$count;}
function denied(callable $call,string $name):void{try{$call();}catch(PDOException $e){check((int)($e->errorInfo[1]??0)===1142|| (int)($e->errorInfo[1]??0)===1370,$name);return;}check(false,$name);}
try{
    $socket=getenv('PAYROLL_TEST_SOCKET');$schema=getenv('PAYROLL_ATTACK_SCHEMA');$account=getenv('PAYROLL_ATTACK_ACCOUNT');
    if(!is_string($socket)||!preg_match('~/tmp/securepayroll-mysql-[A-Za-z0-9_-]+/mysql\.sock\z~D',$socket)
        ||!is_string($schema)||!preg_match('/\Aattack_training_[a-f0-9]{8}\z/D',$schema)
        ||!is_string($account)||!preg_match('/\Alab_drill_[a-f0-9]{8}\z/D',$account)){throw new RuntimeException();}
    $db=new PDO('mysql:unix_socket='.$socket.';dbname='.$schema,$account,getenv('PAYROLL_ATTACK_PASSWORD'),
        [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_EMULATE_PREPARES=>false]);
    check(realpath($db->query('SELECT @@datadir')->fetchColumn())===realpath(dirname($socket).'/data'),'private datadir');
    check((int)$db->query('SELECT @@skip_networking')->fetchColumn()===1,'network disabled');
    if($argv[1]==='--before'){
        // Intentionally unsafe code exists only in this CLI laboratory, never in public/.
        $payload='0 OR 1=1';
        check(count($db->query('SELECT id FROM payslips WHERE employee='.$payload)->fetchAll())===2,'injection reveals both fictional payslips');
        $safe=$db->prepare('SELECT id FROM payslips WHERE employee=?');$safe->execute([$payload]);
        check($safe->fetchAll()===[],'bound parameter prevents injection');
        check($db->query('SELECT id FROM payslips WHERE id=2')->fetch()!==false,'IDOR without owner restriction');
        $safe=$db->prepare('SELECT id FROM payslips WHERE id=? AND employee=?');$safe->execute([2,1]);
        check($safe->fetch()===false,'owner predicate prevents IDOR');
        $db->beginTransaction();
        $submittedRole='finance';
        if($submittedRole==='finance'){$db->exec('UPDATE payslips SET approved=0 WHERE id=2');}
        check((int)$db->query('SELECT approved FROM payslips WHERE id=2')->fetchColumn()===0,'trusting supplied role enables forbidden action');
        check($db->query('SELECT role FROM accounts WHERE id=1')->fetchColumn()==='employee','server role rejects Finance action');
        $db->exec("UPDATE accounts SET role='finance' WHERE id=1");
        check($db->query('SELECT role FROM accounts WHERE id=1')->fetchColumn()==='finance','excessive UPDATE permits privilege escalation');
        $db->exec('UPDATE payslips SET net=1 WHERE id=2');
        check($db->query('SELECT net FROM payslips WHERE id=2')->fetchColumn()==='1.00','unauthorized financial alteration demonstrated');
        $db->rollBack();
        check($db->query('SELECT net FROM payslips WHERE id=2')->fetchColumn()==='9000.00','demonstration transaction leaves original fictional amounts intact');
        check(str_contains(implode("\n",$db->query('SHOW GRANTS')->fetchAll(PDO::FETCH_COLUMN)),'UPDATE'),'bad MySQL configuration exposes updates');
    }else{
        denied(fn()=>$db->query('SELECT * FROM payslips'),'corrected grants remove direct global employee read');
        denied(fn()=>$db->exec('UPDATE payslips SET approved=0 WHERE id=2'),'corrected access control refuses forged Finance action');
        denied(fn()=>$db->exec("UPDATE accounts SET role='finance' WHERE id=1"),'corrected grants prevent escalation');
        denied(fn()=>$db->exec('UPDATE payslips SET net=1 WHERE id=2'),'corrected grants prevent financial tampering');
        $own=$db->prepare('CALL own_payslip(?)');$own->execute([1]);check(count($own->fetchAll())===1,'own data remains available');while($own->nextRowset()){$own->fetchAll();}$own->closeCursor();
        $other=$db->prepare('CALL own_payslip(?)');$other->execute([2]);check($other->fetchAll()===[],'corrected procedure hides foreign ID');while($other->nextRowset()){$other->fetchAll();}$other->closeCursor();
        denied(fn()=>$db->query('SELECT * FROM secure_payroll.salary_conditions'),'training account cannot read application payroll schema');
        $grants=implode("\n",$db->query('SHOW GRANTS')->fetchAll(PDO::FETCH_COLUMN));
        check(!str_contains($grants,'UPDATE')&&!str_contains($grants,'GRANT SELECT')&&str_contains($grants,'GRANT EXECUTE'),'least privilege configuration verified');
    }
    echo "$count real MySQL laboratory demonstration checks passed ($argv[1]).\n";
}catch(Throwable $e){fwrite(STDERR,'Private MySQL demonstration failed: '.get_class($e).' line '.$e->getLine().". No secrets printed.\n");exit(1);}
