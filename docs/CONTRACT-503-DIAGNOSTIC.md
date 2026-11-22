# Diagnostic temporaire du 503 à la création d’un contrat

## Résultat de la revue urgente du 3 novembre 2026

La seule ligne `Application unavailable: PDOException` présente dans le journal
local consulté est horodatée **00:08:36 UTC**. Le contrôleur et le dépôt instrumentés
ont été enregistrés à **00:18:03 UTC**. Cette ligne est donc antérieure à
l’instrumentation : elle ne prouve pas que le nouveau diagnostic a été exécuté.
Aucune nouvelle création de contrat n’a été tentée par l’assistant.

Le processus PHP sur 8080 utilise bien le répertoire courant. Un marqueur HTTP
temporaire a été ajouté sur /contracts/new :
`X-SecurePayroll-Contract-Diagnostic: v2`. Un GET sans session a effectivement
renvoyé ce marqueur avec la redirection 303 normale vers la connexion. Cela permet
de confirmer le code chargé sans effectuer d’INSERT ni afficher de donnée sensible.
Le journal reste limité aux trois champs techniques existants.

### Correspondance des arguments

| Position | Valeur PHP | Paramètre du fichier SQL |
| --- | --- | --- |
| 1 | employee_id issu de la recherche par matricule | p_employee BIGINT UNSIGNED |
| 2 | reference | p_reference VARCHAR(64) |
| 3 | contract_type : permanent / fixed_term / internship | p_type VARCHAR(16) |
| 4 | starts_on au format YYYY-MM-DD | p_start DATE |
| 5 | ends_on ou NULL si vide | p_end DATE |
| 6 | account_id de la session authentifiée | p_actor BIGINT UNSIGNED |

Les six positions correspondent, sans confusion entre identifiant d’employé et
identifiant de compte. La signature **réellement installée** ne peut pas être
affirmée à partir d’un fichier : les variables DB_* ne sont pas disponibles dans
la session de l’assistant et les secrets du serveur n’ont pas été lus.

### Instructions et droits examinés

hr_create_contract appelle hr_assert_permission, verrouille l’employé actif,
contrôle les dates et le type, cherche un chevauchement avec une lecture courante,
insère les sept colonnes prévues, COMMIT puis retourne l’identifiant. Les scripts
de droits prévoient SELECT des colonnes utilisées pour l’autorisation, EXECUTE du
propriétaire sur le helper et la procédure publique, les droits de lecture/verrou
du parent et de l’historique, ainsi que INSERT sur ces sept colonnes.

Les triggers ec_no_delete et ec_preserve_history sont BEFORE DELETE / UPDATE :
ils ne sont pas déclenchés par l’INSERT initial. Les FK employee_id/created_by et
les CHECK du contrat restent applicables ; les champs transmis ne présentent pas
de défaut certain au regard des contraintes du fichier. Un contrat permanent doit
avoir ends_on NULL, les autres types une fin supérieure ou égale au début. La
référence doit être unique. Les violations connues sont normalement traduites en
erreurs 4xx ; le 503 indique une exception non reconnue par ce traitement.

Les GRANT présents dans le dépôt ne prouvent pas les GRANT actuellement installés.
Aucun ajout/retrait de droit n’est justifié sans le code d’erreur réel.

### Piste précise à confirmer : collation du paramètre d’autorisation

Le fichier 001 définit permissions.code avec utf8mb4_0900_as_cs. Dans le helper,
`p.code=p_permission` compare cette colonne à un VARCHAR(100) sans CHARACTER SET
ou COLLATE explicite. MySQL détermine alors le type texte du paramètre à partir
des valeurs par défaut de la base lors de la création du helper ; SET NAMES dans
le fichier de migration ne suffit pas à imposer sa collation.

Si le paramètre et la colonne ont des collations implicites incompatibles, cette
comparaison peut provoquer **HY000 / 1267**, avant le verrou ou le premier INSERT.
Il s’agit d’une piste fondée sur le code, **pas du code d’erreur constaté** ici.

Pour lire uniquement la signature et les collations réellement installées, sans
appel de procédure ni écriture, le responsable local peut exécuter :

```sh
sudo mysql --table secure_payroll <<'SQL'
SELECT SPECIFIC_NAME, ORDINAL_POSITION, PARAMETER_NAME, DTD_IDENTIFIER,
       CHARACTER_SET_NAME, COLLATION_NAME
FROM information_schema.PARAMETERS
WHERE SPECIFIC_SCHEMA = 'secure_payroll'
  AND SPECIFIC_NAME IN ('hr_create_contract', 'hr_assert_permission')
ORDER BY SPECIFIC_NAME, ORDINAL_POSITION;
SELECT TABLE_NAME, COLUMN_NAME, CHARACTER_SET_NAME, COLLATION_NAME
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = 'secure_payroll'
  AND TABLE_NAME = 'permissions' AND COLUMN_NAME = 'code';
SQL
```

Cette commande est facultative tant que le code d’erreur n’est pas connu et n’a
pas été exécutée par l’assistant. Elle ne lit aucun compte, mot de passe, contrat
ou paramètre métier.

Si **1267** et ces métadonnées confirment ce conflit, la correction minimale à
préparer dans la définition du seul helper consiste à déclarer son paramètre :

```sql
IN p_permission VARCHAR(100)
    CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs
```

Ce changement n’est pas appliqué. Remplacer le helper installé exige une opération
DBA ciblée et la conservation de son DEFINER et de ses droits EXECUTE ; ne pas
rejouer 003 ou modifier la collation globale pour cela. Un autre code d’erreur
impose une correction différente, basée sur ce code.

Références : [types des paramètres de procédures MySQL](https://dev.mysql.com/doc/refman/8.4/en/create-procedure.html)
et [code serveur 1267](https://dev.mysql.com/doc/mysql-errors/8.4/en/server-error-reference.html).

### Une seule prochaine tentative

Le diagnostic v2 est déjà chargé sur le serveur vérifié. Ouvrir normalement le
formulaire dans le navigateur avec le compte RH, choisir une référence inutilisée,
un employé existant et des dates valides, puis cliquer une seule fois sur Enregistrer.
Ne pas rafraîchir le POST. Si le détail du contrat s’ouvre avec le message de
succès, conserver ce contrat : la création a fonctionné, aucun nouvel essai n’est
nécessaire. Sinon, lire immédiatement la dernière ligne :

```sh
cd secure_payroll_project
grep '"operation":"contract.create"' storage/logs/application.log | tail -n 1
```

Conserver le préfixe horodaté pour distinguer cette tentative d’une ancienne ligne.
Si la nouvelle réponse est bien un POST /contracts/new en 503 et qu’aucune ligne
n’apparaît, contrôler le marqueur v2 et le serveur/journal utilisés avant de
réessayer. Une erreur d’affichage GET après une redirection de création réussie
est une opération distincte : consulter d’abord le contrat, sans renvoyer le POST.

La syntaxe PHP, les six positions du CALL et le marqueur HTTP ont été vérifiés.
Aucun nouveau module, privilège, migration ou système de tests n’a été ajouté.

Chemin examiné : POST /contracts/new → contrôle CSRF/session/permissions →
AdvancedHRController::handle → employeeByNumber → PeriodRepository::create →
CALL hr_create_contract → fetchColumn → closeCursor. La procédure appelle
hr_assert_permission, verrouille l’employé, contrôle les périodes et insère le
contrat dans une transaction avec ROLLBACK/RESIGNAL sur erreur.

AdvancedHRController::databaseError traite certains codes métier connus, puis
relance les exceptions inconnues. Controller::run les capture et renvoie le 503
générique traduit. C’est ce catch central qui journalisait seulement la classe.
Le gestionnaire global de bootstrap.php est un filet distinct (500 non intercepté).

## Modification temporaire

Pour une PDOException qui atteint ce catch pendant POST /contracts/new, une ligne
JSON supplémentaire est écrite uniquement dans storage/logs/application.log :

- operation : contract.create, constante sans donnée issue du formulaire ;
- sqlstate : code SQLSTATE de cinq caractères ou null si absent/invalide ;
- mysql_code : code numérique du pilote MySQL ou null si absent/invalide.

Ni message PDO, errorInfo[2], requête, paramètres, identité, URL complète, référence
de contrat, mot de passe ou trace ne sont ajoutés. Les exceptions déjà traitées
comme erreurs métier ne deviennent pas des 503. La réponse générique reste inchangée.
Retirer l’appel et la méthode logContractCreationDiagnostic après le diagnostic.

Une correction PHP ciblée préserve l’exception initiale si closeCursor échoue
pendant le nettoyage après un échec. Sans cela, le finally pouvait remplacer
son SQLSTATE par celui du nettoyage. Un échec de closeCursor après un CALL réussi
reste propagé et journalisé : ne pas assimiler tout 503 à un INSERT annulé.
La procédure COMMIT précède le retour de l’identifiant au PHP.

## Reproduire une seule fois

1. Garder le serveur démarré avec son environnement svc_php habituel. Avec le
   serveur PHP intégré, les fichiers PHP sont relus à la prochaine requête ; si
   votre installation conserve le code en cache, redémarrer votre serveur de
   développement habituel sans changer ses identifiants ou sa configuration.
2. Se connecter normalement au compte RH, ouvrir Contrats → Créer un contrat.
3. Utiliser un employé existant non archivé et les valeurs qui déclenchaient le
   503. Choisir une référence encore inutilisée. Pour un permanent, laisser la fin
   prévue vide ; pour les autres types, fournir une fin supérieure ou égale au début.
4. Cliquer UNE fois sur Enregistrer. Ne pas répéter le clic, recharger le POST ou
   réessayer automatiquement, même si la page affiche 503.
5. Lire uniquement la dernière ligne du diagnostic dans le terminal :

   ```sh
   cd secure_payroll_project
   grep '"operation":"contract.create"' storage/logs/application.log | tail -n 1
   ```

La ligne contient uniquement les trois champs ci-dessus, avec le préfixe habituel
du journal PHP. Aucun affichage de l’environnement ou des secrets n’est nécessaire.
Si aucune ligne n’apparaît, le code instrumenté n’a pas été atteint : vérifier le
serveur utilisé, le statut de la réponse et la possibilité d’écriture dans le
journal, sans multiplier les créations. Une validation 422/409/403 n’emprunte pas
le catch 503 ciblé.

Les codes constatés permettront de distinguer une erreur de privilège/DEFINER,
de routine, de contrainte ou de gestion des résultats PDO. La seule mention
PDOException ne permet pas de conclure à un privilège manquant.

Aucune migration, modification de privilège, connexion administrative ou écriture
de contrat n’est exécutée par cette préparation. La reproduction navigateur est
la seule tentative de création proposée à l’opérateur. Si elle réussit, ne pas la
répéter et conserver le contrat créé ; aucun nettoyage des données n’est effectué.

## Mise à jour du 4 novembre 2026

Le marqueur public `X-SecurePayroll-Contract-Diagnostic` a été retiré : la route
répond bien depuis le code du projet et ce marqueur n'est plus nécessaire.
L'absence de cet en-tête a été vérifiée par HTTP sur `/contracts/new`.
La journalisation technique restreinte du code SQL est conservée, car la résolution
réelle du problème MySQL n'a pas encore été confirmée dans cette intervention.
Aucune ligne de journal n'a été effacée. Les mentions antérieures du marqueur
ci-dessus décrivent uniquement l'instrumentation historique.
