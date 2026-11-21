# 10 — Tests et validation

> Synthèse documentaire au 11 novembre 2026. Les chiffres sont repris des rapports identifiés ; aucun test MySQL/HTTP, migration ou scénario offensif n’a été exécuté pour rédiger ces documents.

## A. Vérifications hors connexion

Une analyse de texte SQL ne prouve ni la syntaxe serveur effective, ni les droits installés, ni les transitions en concurrence. Un test de rendu avec tableaux PHP ne prouve pas la bonne réponse d’une application authentifiée réelle. Les chiffres suivants gardent cette portée.

| Source de test | Objectif / méthode | Résultat historiquement documenté | Limites |
|---|---|---|---|
| tests/sql-static.php | Motifs, catalogue et protections de la migration 001/seed/tests lus comme texte | 93 contrôles, rapports du 06/11 | Pas d’exécution SQL |
| tests/compensation-unit.php | Validation montants/textes, FR/EN, Money et habilitations PHP | 45 contrôles | Pas de preuve de routines installées |
| tests/payroll-calculator.php | Calcul pur en centimes, arrondis, caps, net, mois | 17 contrôles | Référence PHP, pas la procédure SQL |
| tests/payroll-calendar.php | Couverture, identités, salaires, suspensions et calendrier | 23 contrôles | Tableaux de sources fournis au test |
| tests/payroll-web-unit.php | Matrice can(), validation et rendu de vues | 210 puis 211 contrôles selon version de campagne | Les nombres changent avec les assertions ; pas HTTP réel |
| tests/login-limiter.php | Succès répétés et conservation des échecs | 18 contrôles | Fichiers runtime privés de test, pas une mesure réseau distribuée |
| tests/database-socket.php | Validation socket et runtime | 7 contrôles | Aucune connexion effectuée |
| tests/payroll-grants.py | Frontières du validateur de GRANT Paie | 12 contrôles | Compare des ensembles autorisés, pas SHOW GRANTS live |
| tests/database-config.php | Validation des variables privées | Aucun total revendiqué ici | Ne tente pas PDO |

Le rapport LAB-VALIDATION-2026-11-06 indique **413** contrôles hors connexion (sans les 12 GRANT et avec 210 web). Le rapport FINALIZATION-VALIDATION-2026-11-06 indique **426** (211 web et 12 GRANT). Ce sont deux états successifs : ne pas additionner 413 et 426. Les vérifications de syntaxe y portent respectivement sur 62 PHP/16 Python puis 73 PHP/24 Python. Ces nombres sont ceux du périmètre de chaque campagne, pas un nouveau comptage de réussite.

## B. Campagnes sur instances MySQL isolées

Les lanceurs créent des datadirs privés, identifient explicitement le socket, désactivent le réseau et vérifient le datadir avant les écritures. Les comptes appelés root dans ces harnais sont ceux de l’instance éphémère ; ils ne sont pas les comptes principaux. Les tests d’écriture ne deviennent pas « lecture seule » parce qu’un rollback est prévu : ils ne sont pas relancés dans cette mission documentaire.

### 4 novembre 2026

Source : `docs/LAB-VALIDATION-2026-11-04.md`. MySQL 8.4.11 privé, skip_networking=1, port=0, MySQL X désactivé. Le dernier parcours HTTP complet cible une instance différente du premier jeu de concurrence/restauration, ce que le rapport précise.

| Test | Contrôles réussis attestés | Portée |
|---|---:|---|
| payroll-mysql.php | 35 | RH → salaire MAD → paie → bulletin, montants et refus |
| payroll-http-live.py | 58 | Sept identités / six rôles, FR/EN, CSRF, IDOR, limiteur |
| payroll-races.py | 18 | Deux sessions en LOCK WAIT, caps, versions, approbation unique, GRANT |
| mysql-recovery.py | 32 | Export, SHA256, restauration indépendante, totaux, routines/triggers et compte service |
| mysql-attacks.py | 12 avant + 10 après | Six exercices pédagogiques dans un schéma séparé |
| mysql-security.py | 18 | Refus métier, salaire absent/en attente/rejeté, UM, net négatif et identités invalides |

Le jeu financier de laboratoire a produit base 10400, brut 10700 et net 10600, comparés au calculateur PHP. Ce jeu n’est pas le paiement principal de Nadia. Les courses ont vérifié deux demandes bloquées réellement puis une seule approbation de primes dépassant ensemble le plafond et une seule approbation de bulletin du couple salarié/mois. Les triggers ont été exercés avec un compte de laboratoire capable d’atteindre le DML, afin de distinguer refus de privilège et refus du trigger.

### 6 novembre — régression paie et intégrité

Source : `docs/LAB-VALIDATION-2026-11-06.md`.

| Test | Réussites attestées |
|---|---:|
| payroll-mysql.php | 35 |
| payroll-http-live.py | 58 |
| payroll-races.py | 18 |
| mysql-integrity.py | 33 |
| mysql-recovery.py | 32 |
| mysql-security.py | 18 |
| mysql-attacks.py | 12 avant + 10 après |
| **Total de cette campagne** | **216** |

`tests/INTEGRITY.md` confirme les 33 assertions et les six tables vides après rollback. Cela remplace le statut historique « bloqué » de la préparation 03C-1 pour le périmètre isolé, mais ne prouve pas que le même lanceur 03C-1 a ensuite été exécuté.

### 6 novembre — finalisation Settlement et IAM

Source : `docs/FINALIZATION-VALIDATION-2026-11-06.md`.

| Test | Réussites attestées | Objet |
|---|---:|---|
| payroll-mysql.php | 35 | Régression complète existante |
| payroll-http-live.py | 58 | HTTP authentifié et accès |
| payroll-races.py | 18 | Régression concurrence |
| settlement-mysql.php | 62 | Paiements, doublons, corrections, compléments et remboursements |
| settlement-http.py | 47 | Formulaires, workflow, CSRF/IDOR/FR-EN et échappement |
| settlement-races.py | 18 | Paiements et reçus concurrents, unicité réelle, triggers |
| iam-mysql.php | 34 | Octrois/révocations, activité, auto-octroi et conflits |
| iam-http.py | 33 | Admin/Audit, CSRF, FR/EN, révocation dans session ouverte |
| iam-races.py | 9 | Octrois incompatibles et révocations concurrents |
| mysql-final-recovery.py | 35 | Dump administratif, restauration, comptes de lignes, totaux et GRANT exacts |
| **Total de cette campagne** | **349** | Instance(s) privées seulement |

Les 349 ne s’ajoutent pas aux 216 pour produire un nombre de tests indépendants : plusieurs scénarios sont des régressions des mêmes chemins. Le rapport distingue 426 contrôles hors connexion supplémentaires en nature, sans les confondre avec des tests serveur.

### Devise MAD : diagnostic et réparation

`docs/MAD-DIAGNOSTIC.md` rapporte **18 contrôles MySQL réels** dans de nouveaux schémas fictifs d’une instance privée pour tester diagnostic et correctif de structure, plus les 12 frontières GRANT hors connexion. `docs/MAD-REPAIR.md` rapporte **22 contrôles** correctif/sauvegarde/restauration, **8** PHP du parcours historique UM et **19** du parcours MAD, ainsi que **45** hors SQL. Le rapport ne doit pas convertir ces nombres en nouvelles garanties sur une principale non inspectée. Les artefacts storage/mad-repair incluent un fichier applied.json dont la lecture a été refusée dans cette session ; aucun privilège supplémentaire n’a été demandé pour le lire.

### Régression isolée après restauration de la démo

`docs/DEMO-PRESENTATION.md` et `storage/logs/demo-verification.json` attestent **24 contrôles** dans une nouvelle instance privée restaurée : vrais champs target=0, paiement, préparation/vérification/approbation/publication d’une correction, lecture employee FR/EN, refus CSRF et état périmé. primary_connected=false est enregistré. Cette régression complète la preuve d’utilisation des formulaires, sans annoncer de correction créée sur la principale.

## C. Tests historiquement réalisés sur secure_payroll principale

Le rapport `storage/logs/demo-verification.json`, passed=true, est daté du **2026-11-06T19:39:59Z** et contient **64 libellés de contrôles**. Il décrit six authentifications HTTP, tableaux de bord/profils, écrans autorisés en FR/EN, base exacte 11200 pour Nadia, transitions indépendantes, accès personnel publié, règlement fictif et solde zéro, conservation des quatre tables de rémunération et présence d’historiques. Le rapport administratif y atteste six empreintes Argon2id, identités distinctes, propriétaires/droits, sauvegarde vérifiée et restauration privée.

Ce fichier n’est pas une transcription exhaustive de chaque requête ni un inventaire SHOW CREATE. Son état n’a pas été revalidé au 11 novembre. Aucun test négatif/offensif n’est inféré sur la principale ; le document de démonstration réserve les exercices correspondants au laboratoire. La restauration a été effectuée dans une autre instance, jamais présentée comme un import sur la principale.

## Six exercices pédagogiques avant / après correction

Le code volontairement vulnérable est limité à `tests/mysql-attack-demonstrations.php` et au schéma de formation privé préparé par `lab/mysql-attacks.py`. Il ne correspond pas à des endpoints vulnérables ajoutés à SecurePayroll et aucune de ces opérations n’a été exécutée dans cette mission.

| Exercice | État pédagogique avant | Mécanisme comparé après / témoin sûr |
|---|---|---|
| Injection SQL | Une concaténation de filtre peut révéler deux bulletins fictifs | Paramètre lié ; aucun élargissement du prédicat |
| IDOR | Lecture par ID seul d’un bulletin d’autrui | Prédicat propriétaire et procédure own_payslip du schéma de formation |
| Rôle fourni par le client | Une valeur fournie comme Finance déclenche une action | Rôle relu côté serveur ; refus d’écriture après restriction des droits |
| Élévation de privilèges | UPDATE excessif permet de modifier le rôle fictif | Suppression du DML direct et refus réel de privilège |
| Altération de montant | UPDATE excessif change le net d’un bulletin fictif | Accès via procédure bornée, UPDATE refusé |
| Mauvaise configuration MySQL | SELECT/UPDATE directs trop larges apparaissent dans SHOW GRANTS | EXECUTE seul sur l’accès de formation ; refus d’accès à salary_conditions de l’application |

Le jeu avant inclut une transaction annulée et un contrôle que le montant fictif initial est retrouvé. Le jeu après vérifie les refus MySQL attendus et les droits réels. Les 12/10 assertions englobent aussi les gardes datadir/réseau : elles ne sont pas douze/dix attaques distinctes ni un audit exhaustif.

## Catalogue complet des fichiers de tests racine

- `tests/compensation-readiness.php` : Inspection réelle explicite --verify ; pas une migration.
- `tests/compensation-unit.php` : A — logique pure.
- `tests/database-config.php` : A — configuration seule.
- `tests/database-connect.php` : Lecture PDO de diagnostic ; connexion réelle requise.
- `tests/database-integrity.php` : B — écritures de test avec rollback, cible dédiée.
- `tests/database-socket.php` : A — configuration seule.
- `tests/database-structure.php` : Inspection structurelle réelle ; exige secure_payroll et non-root.
- `tests/iam-http.py` : B — HTTP authentifié privé.
- `tests/iam-mysql.php` : B — intégration SQL privée.
- `tests/iam-races.py` : B — concurrence privée.
- `tests/login-limiter.php` : A — runtime local isolé.
- `tests/mad-repair-live.php` : B — réparation UM/MAD privée.
- `tests/mysql-attack-demonstrations.php` : B — exercices avant/après privés.
- `tests/payroll-calculator.php` : A — calcul pur.
- `tests/payroll-calendar.php` : A — calendrier pur.
- `tests/payroll-grants.py` : A — comparaison de GRANT.
- `tests/payroll-http-live.py` : B — HTTP authentifié privé.
- `tests/payroll-live.php` : Vérification réelle explicite --verify ; authentification et lectures.
- `tests/payroll-mysql.php` : B — intégration SQL privée.
- `tests/payroll-races.py` : B — concurrence privée.
- `tests/payroll-web-unit.php` : A — autorisation/validation/rendu.
- `tests/private_http.py` : B — utilitaire de fixture et serveur privé.
- `tests/settlement-http.py` : B — HTTP authentifié privé.
- `tests/settlement-mysql.php` : B — intégration SQL privée.
- `tests/settlement-races.py` : B — concurrence privée.
- `tests/sql-static.php` : A — analyse statique.
- `tests/web-boundaries.py` : C possible — requêtes HTTP anonymes vers boucle locale ; non exécuté ici.

## Incidents et corrections historiques

- Limiteur : les connexions réussies consommaient le quota ; succeeded retire désormais la seule réservation propre. Les 18 assertions dédiées couvrent succès répétés et cinq échecs conservés.
- HTTP isolé : une forte charge VM a déclenché un timeout ; le test a porté son délai à 60 s, sans diminuer le coût Argon2id. Les 58 contrôles ont ensuite réussi.
- Restauration : sélection erronée du runtime web corrigée pour retenir le runtime privé contenant les logs ; 32 contrôles réels ont suivi.
- Comparaison de GRANT IAM : l’ordre des colonnes provoquait un refus ; le comparateur traite les ensembles équivalents, sans élargissement des droits.
- Espace temporaire : une initialisation de restauration a échoué sur /tmp plein ; une destination /var/tmp a permis la campagne de 35 contrôles. Aucun artefact supprimé n’est revendiqué.
- Deux initialiseurs historiques sont rapportés en attente avec arrêt refusé ; les PID anciens ne sont pas une preuve de processus encore actifs aujourd’hui. Aucun signal n’a été envoyé pendant cette documentation.
- Contrat 503 : diagnostic technique réduit et préservation de l’exception PDO lors de closeCursor ; le patch de collation corrige une cause connue, sans attribuer chaque 503 à cette seule cause.

## Portée du contrôle documentaire courant

Cette mission a inventorié les sources, lu les rapports accessibles, recalculé la cohérence des nombres d’objets et vérifié la présence des livrables. Les tests applicatifs existants n’ont pas été relancés, car certains produisent sessions/logs, créent des fixtures ou modifient une base. Les contrôles du générateur documentaire ne constituent pas de nouveaux tests fonctionnels de SecurePayroll. Les preuves temporaires historiques référencées par les rapports n’ont pas toutes été relues ; leur disponibilité actuelle reste Non vérifié.
