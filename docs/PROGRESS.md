# Avancement SecurePayroll — mise à jour du 6 novembre 2026

## Finalisation : paiements, corrections et IAM livrés au laboratoire

Les paiements fictifs anti-doublon, corrections par versions, compléments,
remboursements contrôlés et console IAM FR/EN sont désormais développés.
La campagne de finalisation compte **349 contrôles réels réussis**, dont 203
pour les nouveaux workflows SQL/HTTP/concurrence et 35 pour leur restauration ;
les 111 autres revalident les parcours existants. 426 contrôles hors connexion
passent. Aucun nouveau module installé sur la principale : inspection sudo de
l’opérateur encore nécessaire. Les lanceurs administratifs imposent désormais
un snapshot avant le premier DDL et refusent tout rejeu/état partiel.

État actuel, limites et artefacts :
[rapport de finalisation](FINALIZATION-VALIDATION-2026-11-06.md).
Activation principale préparée : [procédure](FINALIZATION.md).
Les bilans ci-dessous restent historiques, notamment les mentions de paiements
et console IAM non développés dans les campagnes précédentes.

## Nouvelle campagne du 6 novembre

Revalidation sur de nouveaux datadirs : **216 contrôles réels réussis** (35 SQL,
58 HTTP authentifiés, 18 concurrence/privilèges, 33 identité/RBAC, 32 restauration,
18 refus métier/sécurité, 22 exercices avant/après), et 413 hors connexion.
Nouveau lanceur d’intégrité isolée et correction du chemin de journaux utilisé
pour la restauration, vérifiée par un export/import réel. La base principale
reste inchangée. Trois serveurs validés sont arrêtés ; deux initialiseurs bloqués
dans le confinement nécessitent encore une intervention de l’environnement hôte.
Voir [le rapport de cette campagne](LAB-VALIDATION-2026-11-06.md) pour les artefacts,
les limites, les processus en attente et les opérations principales restantes.

Les sections suivantes conservent le bilan fonctionnel du 4 novembre.

## État actuel : laboratoire validé, base principale inchangée

L’utilisateur confirme sur l’instance principale `secure_payroll` les quatre tables
`compensation_requests`, `compensation_decisions`, `compensation_history`,
`salary_conditions`, ainsi que `finance.demo`. **Ne pas relancer activate-compensation,
create-finance-demo ou les migrations 001 à 006 sur cette instance.** Son parcours
réel RH → Finance, ses colonnes/procédures MAD et ses droits restent à vérifier.

L’utilisateur a explicitement autorisé les instances MySQL privées et leurs comptes,
GRANT, migrations et tests. Les validations ci-dessous ont été exécutées sur ces
seules instances. Aucun socket/port, compte ou jeu de données de l’instance
principale n’a été utilisé. Aucune migration, modification de privilège ou restauration
n’y a été appliquée. Aucun sudo, commande Git, publication externe ou suppression
de données/journaux existants n’a été effectué par l’assistant.

Rapport détaillé et artefacts : [LAB-VALIDATION-2026-11-04.md](LAB-VALIDATION-2026-11-04.md).

## Phase 1 — rémunérations validées dans le laboratoire

Terminé côté code et testé : demandes RH, approbations Finance indépendantes,
refus de double décision et auto-approbation, conditions salariales MAD, historique,
refus d’utilisation d’un salaire non approuvé et préservation des anciennes valeurs UM.
Le parcours RH → Finance a réellement utilisé les routines MySQL et le service non-root.

Fichiers : code de rémunération existant conservé ;
`tests/compensation-readiness.php`, `tests/compensation-unit.php`,
`tests/payroll-mysql.php`, `lab/mysql-security.py`, documentation de rémunération.
Le vérificateur principal en lecture seule est prêt, mais l’environnement CLI privé
de cette base n’est pas fourni. La validation du laboratoire ne démontre pas la
version ou les droits de l’installation principale.

## Phase 2 — paie développée et testée sur MySQL

Périodes mensuelles, plafonds explicites par employé/mois, primes/retenues et
suspensions payées/non payées avec décision Finance indépendante ; calcul à deux
décimales sur les seules rémunérations approuvées ; proratisation calendaire ;
versions immuables, instantanés et détection des sources obsolètes.

Fichiers : `app/Payroll/{Calculator,Calendar,Repository,Validation}.php`,
`app/Web/PayrollController.php`, `app/Views/payroll.php`, `payroll-select.php`,
`database/migrations/007_payroll.sql`, `008_payroll_operations.sql`,
`database/seeds/006_payroll_permissions.sql`, les trois fichiers de setup payroll,
`bin/payroll-admin.py`, `docs/PAYROLL.md`, `docs/PAYROLL-ACTIVATION.md`.

Migrations appliquées : 007/008 et leurs dépendances uniquement dans les datadirs
neufs du laboratoire. Aucune nouvelle migration principale appliquée.
Les 35 contrôles SQL réels couvrent notamment le calcul final 10400,00 de base,
10700,00 brut et 10600,00 net en MAD, comparé au calculateur PHP indépendant.
Les tests complémentaires refusent salaire absent/en attente/rejeté, UM et net négatif.
Les plafonds restent configurables et sans défaut : aucun barème chiffré validé n’a
été retrouvé ; la politique organisationnelle conservatrice reste à confirmer métier.

## Phase 3 — bulletins développés et testés de bout en bout

Préparation, vérification des montants, décision Finance indépendante/rejet motivé,
publication distincte et consultation du seul employé bénéficiaire ; historique
complet pour les gestionnaires et versions publiées seules pour l’employé.

Fichiers : `app/Views/payslip.php`, dépôt/procédures ci-dessus, intégration dans
`app/Web/Controller.php`, `app/Auth/AuthService.php`, `app/Web/helpers.php`,
`app/Views/header.php`, catalogues `lang/fr.php` et `lang/en.php`.

Tests réellement exécutés : 58 contrôles HTTP authentifiés sur un serveur PHP
local relié au seul socket MySQL du laboratoire. Sept comptes fictifs couvrent les
six rôles et deux employés. FR/EN, actions réelles de calcul/vérification/approbation/
publication, refus CSRF, séparation des tâches et IDOR dans les deux sens passent.
Aucun paiement fictif ni correction d’une paie approuvée n’est développé, faute
de périmètre confirmé pour ces workflows. Le rôle administrateur conserve son
profil et sa connexion existants ; aucune nouvelle console IAM n’est ajoutée.

## Phase 4 — sécurité, audit, concurrence et récupération

Les GRANT réels du propriétaire de paie ont été comparés à la liste exacte des
colonnes, tables et procédures nécessaires. Le compte est verrouillé ; svc_php
n’a que les EXECUTE publics sur le nouveau module, sans SELECT/DML direct.
L’auditeur dispose de la lecture et ne peut approuver. Les triggers d’immutabilité
ont été exercés même depuis l’administration du laboratoire.

18 contrôles de concurrence/privilèges/intégrité ont réussi : deux connexions
observées en attente du même verrou parent, un seul dépassement de plafond évité,
versions distinctes pour deux calculs et une seule approbation Finance.
18 contrôles métier/sécurité supplémentaires passent : propre salaire Finance,
propre paie du préparateur, couverture, net, UM, rôles incompatibles/futurs/révoqués
et compte désactivé. Les événements et leurs justifications sont conservés.

Corrigé après échec HTTP réel : les authentifications réussies étaient comptées
par le limiteur, bloquant le sixième rôle. Une réussite libère maintenant uniquement
sa réservation ; les autres échecs restent comptés. Les 58 contrôles HTTP incluent
le blocage de la sixième tentative après cinq échecs. 18 assertions unitaires
complémentaires passent. Aucun compteur principal n’a été effacé.

Pour isoler également le serveur PHP de laboratoire, `DB_SOCKET` sélectionne
explicitement un socket validé sans repli TCP, et `APP_RUNTIME_DIR` isole logs,
sessions et limiteur dans un dossier privé. En l’absence de ces options, les
chemins et la connexion TCP historiques sont conservés.

Fichiers : `app/Database/Connection.php`, `app/Security/{Runtime,Session,LoginLimiter}.php`,
`app/bootstrap.php`, `app/Web/Controller.php`, `bin/backup.py`,
`database/audit/privileges-readonly.sql`, `tests/payroll-grants.py`,
`tests/login-limiter.php`, `tests/database-socket.php`, `tests/payroll-races.py`,
`tests/payroll-http-live.py`, `lab/mysql_instance.py`, `lab/mysql-recovery.py`,
`lab/mysql-web-check.py`, `docs/RECOVERY.md`, `docs/WEB-SETUP.md`.

32 contrôles de sauvegarde/restauration passent : export réel avec compte dédié,
manifestes SHA256, copie des logs privés, import dans un second datadir, comparaison
de chaque table et des totaux, routines/triggers, droits réappliqués, lecture employé
non-root et immutabilité restaurée. Aucun export/restauration principal effectué.
Les artefacts /tmp sont conservés ; ils ne remplacent pas une sauvegarde durable de la VM.

## Phase 5 — laboratoire d’attaque isolé exécuté

`lab/demonstrate.py` conserve ses six exercices hors connexion. Des démonstrations
MySQL réelles ont été ajoutées dans `lab/mysql-attacks.py` et
`tests/mysql-attack-demonstrations.php` : injection SQL, accès insuffisant, IDOR,
élevation de privilèges, altération financière et mauvaise configuration des droits.
Douze contrôles avant et dix après correction passent dans `attack_training_*`,
schéma séparé de l’instance privée. Aucune route vulnérable n’a été introduite
et aucune attaque externe n’a été lancée. Les données et journaux sont conservés.

`lab/mysql-validate.py` prépare un datadir neuf et ne reprend pas des migrations
partiellement appliquées. Les instances privées sont arrêtées par SQL SHUTDOWN sur
leur socket, sans signal système refusé, modification de configuration ou sudo.
Une erreur de nom de colonne dans une fixture de révocation a été corrigée ; le
rôle de test a été révoqué avec historique, puis les tests ont passé sur la copie restaurée.
Un passage HTTP a expiré sous forte charge VM ; les 58 contrôles ont ensuite passé
avec un délai de test de 60 secondes, sans réduire Argon2id ou les protections.

## Installation principale restant à autoriser et effectuer

Le plan exact est dans [PAYROLL-ACTIVATION.md](PAYROLL-ACTIVATION.md).
Les nouveaux objets sont reviewables et validés en laboratoire. Une validation
administrative distincte reste nécessaire avant leur installation principale :
inspection en lecture seule, sauvegarde privée, puis nouvelles migrations 007/008,
seed de permissions et droits dédiés. Ne pas rejouer les anciennes migrations ou
créer à nouveau finance.demo. Les comptes Paie/Employee/Audit/Admin ne doivent être
créés que s’ils sont absents, avec saisie privée et identités fictives distinctes.

## Tableau de livraison

| Fonctionnalité | Développée | Installée principale | Test réel laboratoire | Reste |
|---|---|---|---|---|
| Authentification, sessions et RBAC | Oui | Socle existant | Sept identités connectées, rôles et limiteur | Reprendre les parcours principaux après installation |
| Gestion RH et contrats | Existante | Existante selon contexte | Créations contractuelles et profils, refus d’accès | Validation RH principale complémentaire |
| FR/EN dès la connexion | Oui | Code intégré | Connexion et bulletins authentifiés | Vérifier les nouveaux écrans après activation |
| Six rôles | Oui pour les parcours actuels | Attributions supplémentaires à vérifier | Six rôles connectés, deux employés isolés | Pas de nouvelle console IAM |
| Rémunérations RH → Finance, historique | Oui | Tables et finance.demo confirmés par l’utilisateur | Procédures et écrans réels | Vérifier parcours et droits principaux |
| MAD et historiques UM | Oui | Version 006 à vérifier | MAD utilisé ; UM inchangé et refusé pour paie | Inspection des colonnes/routines principales |
| Périodes, plafonds, primes, retenues, suspensions | Oui | Non, nouvelles migrations | Oui, avec refus métier | Installer 007/008 ; confirmer politique des plafonds |
| Calcul et versions | Oui | Non | Totaux exacts et concurrence | Installation et tests principaux |
| Bulletins, vérification, Finance, publication | Oui | Non | Workflow SQL et HTTP complet | Installation et tests principaux |
| Consultation personnelle / IDOR | Oui | Non pour nouveaux bulletins | Deux employés, refus croisés et brouillons cachés | Retester sur principaux comptes fictifs |
| Paiements fictifs | Non | Non | Non | Périmètre à confirmer |
| Audit financier et moindre privilège | Oui pour nouveaux workflows | Nouveaux objets non installés | Traces, droits réels et triggers vérifiés | Audit DBA principal |
| Sauvegarde/restauration et incident | Lanceur et procédure | Compte principal à vérifier | 32 contrôles, seconde instance | Sauvegarde durable et exercice principal autorisé |
| Laboratoire d’attaque | Oui | Instance séparée uniquement | Six scénarios MySQL avant/après | Préparer présentation pédagogique |
| Installation et démonstration | Documentation actualisée | Sans objet | Rapport détaillé des tests réels | Autorisation administrative principale |

## Vérification finale de cette continuation

Syntaxe vérifiée : 66 fichiers PHP et douze scripts Python concernés. Les tests
ciblés finaux repassent : 18 limiteur, sept configuration socket/runtime,
210 autorisation/rendu paie et douze frontières de privilèges hors connexion.
Les cinq datadirs utilisés ont conservé leurs données/journaux et leur socket
MySQL privé est absent après arrêt. Aucun processus du laboratoire n’est laissé
en service. Les 58 tests HTTP finaux sont consignés séparément du premier passage
à 51 dans le rapport ; les contrôles SQL/concurrence/restauration ne sont pas
présentés comme des tests de l’instance principale.
