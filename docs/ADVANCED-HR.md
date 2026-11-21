# Mission 05A — départements, postes, affectations et contrats

## Activation MySQL : uniquement après revue et validation administrative

Les migrations 001 et le compte svc_php existent déjà : ne pas les rejouer ni
relancer l’installation de démonstration. La revue 05B a fixé les DEFINER au compte
verrouillé hr_module_owner@localhost. Suivre [ADVANCED-HR-ACTIVATION.md](ADVANCED-HR-ACTIVATION.md)
pour les droits et contrôles. Depuis la racine, après validation des fichiers :

```sh
sudo python3 bin/local-demo.py activate-hr --apply --with-demo-catalogues
```

L’option --with-demo-catalogues applique le seed 004, contenant des références de
démonstration à adapter à votre organisation. Pour une activation sans ces données :

```sh
sudo python3 bin/local-demo.py activate-hr --apply
```

Les commandes utilisent l’administration locale par socket ; aucun secret n’est
inscrit en ligne de commande. Ne pas utiliser --force. Aucune de ces commandes
n’est exécutée par l’application ou par cette livraison. Les seeds sont relançables
en séquence, sans modifier les libellés existants ni recréer les six rôles.

Le DDL MySQL a des commits implicites. Appliquer 002 et 003 une seule fois. Si
des objets existent déjà ou si une étape échoue, examiner l’état avec le DBA avant
reprise ; aucun objet/donnée existant n’est supprimé automatiquement. La création
des triggers peut exiger des droits administratifs supplémentaires suivant la
politique de journal binaire ; ne pas modifier cette politique ou élargir svc_php
pour contourner un échec. Le DEFINER explicite des neuf nouveaux objets est
hr_module_owner@localhost, distinct du créateur administratif. Cette identité doit
rester verrouillée et conserver uniquement les droits nécessaires à l’exécution.

Le PHP existant utilise les mêmes DB_* et svc_php, sans root. Pour démarrer ou
redémarrer le serveur avec saisie confidentielle du mot de passe SQL :

```sh
python3 bin/local-demo.py serve
```

Ouvrir http://127.0.0.1:8080/login et se connecter avec le compte RH existant.
Les nouvelles permissions sont relues à la prochaine requête, sans recréer le compte.

## Parcours navigateur

- Menu Départements / Postes : consulter les catalogues et leur état actif/archivé.
  Les noms FR et EN sont stockés dans le catalogue, pas déduits d’une traduction
  approximative. La gestion administrative du catalogue reste hors de cette interface.
- Menu Affectations : historique paginé, consultation détaillée, nouvelle période
  avec matricule, département et poste actifs, début et fin prévue facultative.
- Menu Contrats : liste paginée, création par matricule et référence unique, détail,
  type, dates et clôture. Types : permanent, fixed_term, internship, traduits dans l’UI.
- Fiche employé : liens vers ses contrats, son historique d’affectations et les
  formulaires préremplis avec son matricule. Les mêmes permissions sont vérifiées
  sur les URL directes ; les autres rôles n’accèdent pas aux contrats via leur fiche.
- Clôture : enregistrer une fin effective, une seule fois, depuis le détail.
  Pour un changement de poste, clôturer l’affectation précédente puis enregistrer
  la suivante. Les contrats sans fin doivent être clôturés avant un nouveau contrat.

Toutes les pages, erreurs et validations sont FR/EN. Le sélecteur conserve la route
courante (et les paramètres de pagination) dans le périmètre autorisé.
L’interface existante et ses protections CSRF/échappement/sessions sont réutilisées.

## Modèle et intégrité

Quatre tables normalisées, InnoDB/utf8mb4, sont ajoutées : departments, positions,
employee_assignments et employment_contracts. Le poste est un métier indépendant
du département ; l’affectation relie un employé, un département et un poste.
Le contrat est lié directement à l’employé : un changement de département ne
réécrit pas son contrat. Les codes de catalogue et références de contrat sont uniques.
Toutes les FK sont en RESTRICT ; aucune suppression en cascade n’est définie.

Les dates sont DATE, au format ISO YYYY-MM-DD, à partir du 01/01/1900. Les périodes
incluent leur dernier jour. Deux périodes peuvent donc se suivre, mais pas partager
une journée : fin au 31 janvier, début suivant au 1er février. Une date de fin
NULL réserve une période jusqu’à clôture, même face à une nouvelle période future.

Politique académique retenue : au plus un contrat de tout type à la fois par
employé, et au plus une affectation organisationnelle à la fois. Aucun cumul de
types de contrats n’est autorisé. Le contrat permanent exige une fin prévue NULL ;
les contrats fixed_term et internship exigent une fin. Des saisies historiques et
futures sont admises si elles respectent ces règles.

starts_on et ends_on sont les dates d’origine, immuables. closed_on est une fin
effective enregistrée séparément ; effective_ends_on est générée par MySQL avec
COALESCE(closed_on, ends_on). Une clôture ne peut ni précéder le début ni prolonger
la fin d’origine. Les dates d’origine, created_at et created_by sont conservés ;
closed_at et closed_by identifient la clôture. Une date de clôture future est
possible : le dossier reste en cours jusqu’à son dernier jour inclus.

Quatre triggers refusent les DELETE des historiques et la réécriture de leurs
informations d’origine. Seule une première clôture est possible ; un UPDATE sans
changement reste permis. Une correction de saisie autre qu’une clôture n’est pas
un CRUD ordinaire : aucun effacement, réouverture, annulation ou avenant n’est
implémenté silencieusement. Une procédure exceptionnelle devra être définie séparément.

Les libellés de catalogue affichés dans l’historique restent les noms courants
des références liées ; il ne s’agit pas de snapshots des anciennes traductions.

## Non-chevauchement et privilèges

Les quatre points d’écriture sont des procédures SQL SECURITY DEFINER :
hr_create_assignment, hr_close_assignment, hr_create_contract et hr_close_contract.
Elles valident le compte auteur actif, l’employé de cet auteur, son rôle hr_manager
actif et sa permission métier à travers hr_assert_permission. Ce helper n’est pas
exécutable directement par svc_php. Le PHP vérifie aussi ces permissions avant tout appel.

Chaque procédure gère sa propre transaction avec ROLLBACK et RESIGNAL en cas d’erreur.
Ne pas l’appeler depuis une transaction déjà ouverte. Le dépôt PDO le refuse et
consomme tous les résultats des CALL pour ne pas bloquer la requête suivante.

Les créations verrouillent la ligne parent employees avec FOR UPDATE, puis
effectuent une lecture **courante verrouillante** de l’historique, y compris sous
REPEATABLE READ. Cela sérialise les créations concurrentes pour un même employé,
y compris lorsqu’il n’existe encore aucun contrat. La clôture prend les verrous
dans le même ordre (employé, puis dossier). Un conflit de verrou ou deadlock est
renvoyé comme erreur métier invitant à recharger, sans détail SQL. Il n’y a pas
de retry implicite susceptible de créer un doublon après un résultat incertain.

svc_php reçoit seulement SELECT sur les quatre nouvelles tables et EXECUTE sur
les quatre procédures publiques. Il ne reçoit aucun INSERT, UPDATE, DELETE ou
DDL direct sur ces tables, ni droit sur une autre base. Les droits existants de
création/modification d’identité employé sont inchangés.

La garantie de non-chevauchement suppose ce chemin d’écriture exclusif. Un DBA
disposant de droits directs sur les historiques peut contourner les procédures ;
il doit les utiliser pour ses opérations ordinaires. Les triggers ne constituent
pas une protection contre un administrateur qui modifie le schéma. L’identifiant
d’auteur est fourni par la session applicative au CALL ; le compte SQL partagé
n’est pas une signature individuelle indépendante du serveur PHP.

Les catalogues actifs sont relus avec FOR SHARE lors de la création d’une
affectation : une désactivation concurrente ne repose pas sur une ancienne vue
cohérente de ces références. Une affectation n’impose pas qu’un contrat couvre
toute sa période ; ce contrôle de workflow reste distinct et n’est pas inventé ici.

Permissions RH ajoutées : departments.read, positions.read, assignments.read,
assignments.create, assignments.close, contracts.read, contracts.create,
contracts.close. Aucun rôle autre que HR Manager ne les reçoit par ce seed.

## Rémunérations futures

Aucune colonne de montant, devise, rémunération ou approbation salariale n’existe
dans ces tables ou formulaires. Créer un contrat ici est une opération administrative,
pas une validation de salaire ou un déclenchement de paie. Le futur domaine Finance
devra gérer des conditions salariales dans des relations distinctes référencées
par le contrat, avec ses propres droits et approbations indépendantes. Ne pas
ajouter des montants aux tables actuellement lisibles par le RH.

## Vérifications et limites de cette livraison

La syntaxe PHP, les clés FR/EN, les validations de dates et les rendus sont contrôlés
hors connexion. Les migrations et les quatre procédures doivent encore être
validées sur MySQL après autorisation. Aucune réussite SQL ou de concurrence n’est
affirmée sans exécution.

Après activation autorisée, vérifier dans le navigateur : catalogue, affectation,
historique depuis la fiche, contrat permanent puis refus d’un chevauchement,
clôture et nouvelle période adjacente. Vérifier aussi deux créations concurrentes
du même employé avec des sessions distinctes : une seule période incompatible
doit être créée. Faire vérifier le refus d’écriture directe des historiques avec
svc_php et le refus d’accès par un rôle sans les permissions métier.

Référence : [lectures verrouillantes InnoDB](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html).

## Fichiers livrés et contrôles exécutés

Créés : les migrations 002 et 003, les seeds 003 et 004, le fichier de droits
database/setup/advanced_hr_grants.sql, app/HR/PeriodRepository.php,
app/HR/PeriodValidation.php, app/Web/AdvancedHRController.php et quatre vues
hr-catalogue, hr-period-list, hr-period-form et hr-period-detail dans app/Views/.

Adaptés : le routage de app/Web/Controller.php, les retours de langue dans
app/Web/helpers.php, le menu app/Views/header.php, les liens de app/Views/employee.php,
les assets existants, les catalogues lang/fr.php et lang/en.php et le README.
L’authentification, la classe PDO, les anciens seeds/migrations et les écritures
du module employés ne sont pas modifiés. La revue 05B ajoute le propriétaire et
son activation au lanceur CLI local existant, sans modifier les contrôleurs PHP.

Contrôles réellement exécutés sans MySQL : syntaxe des 29 fichiers PHP applicatifs,
parité des 250 clés FR/EN, paramètres et références des traductions, sept dates
et cas de validation type/période/références, 16 rendus HTML FR/EN avec contrôle
d’échappement, huit refus d’accès serveur avec un rôle non RH et sans requête SQL.
Les contrôles statiques SQL retrouvent les quatre tables, huit FK RESTRICT,
huit CHECK, quatre triggers, cinq procédures et les seuls droits SELECT/EXECUTE
additionnels. Ils ne valident pas la syntaxe avec le moteur MySQL.

Onze contrôles HTTP locaux sans session ont confirmé les redirections des nouvelles
pages vers /login, le refus GET de la clôture (405) et le rejet d’un identifiant
de route invalide (404). Aucun identifiant réel n’a été employé et aucune donnée
métier n’a été écrite. Aucun framework de tests, commande Git ou changement
système n’a été ajouté.
