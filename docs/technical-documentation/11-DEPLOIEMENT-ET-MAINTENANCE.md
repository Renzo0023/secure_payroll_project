# 11 — Installation, exploitation et maintenance

> Synthèse documentaire au 11 novembre 2026. Les chiffres sont repris des rapports identifiés ; aucun test MySQL/HTTP, migration ou scénario offensif n’a été exécuté pour rédiger ces documents.

## Préconditions

Une installation neuve nécessite PHP CLI/serveur avec PDO MySQL, Argon2id et sessions ; un PHP 64 bits pour le calculateur de référence ; MySQL 8.4 conforme aux CHECK, JSON, procédures et collations utilisés ; clients mysql/mysqldump ; Python pour les lanceurs. Ubuntu sous VMware est l’environnement académique. Les validations historiques utilisent MySQL 8.4.11. La version minimale exacte de PHP n’est pas déclarée dans un manifeste : vérifier la syntaxe réellement utilisée (never, propriétés typées, match, attributs).

La seule racine web doit être `public/`. `app/`, `config/`, `database/`, `storage/`, les dumps et l’environnement privé ne doivent pas être servis. Le serveur intégré PHP convient à la démonstration locale, pas à une exposition professionnelle multi-utilisateur.

## Vérification préalable sans modification

Commandes indicatives de consultation, non exécutées ici :

```bash
php -v
php -m
mysql --version
systemctl status mysql --no-pager
ss -ltn '( sport = :8080 )'
```

`mysql --version` indique le client, pas la version du serveur. La confirmer par SELECT VERSION() avec un accès existant. Si l’unité MySQL porte un autre nom, vérifier les unités de l’hôte ; le code ne configure pas systemd.

## Démarrer MySQL et l’application

**Action opérateur, hors mission documentaire :** si le service MySQL installé est arrêté et que son nom a été vérifié, `sudo systemctl start mysql` démarre le service ; cette action demande une autorisation système. Aucun arrêt/redémarrage global ni modification de configuration n’est prescrit sans diagnostic.

Le `.env.example` n’est pas chargé automatiquement. Fournir DB_HOST, DB_PORT, DB_NAME=secure_payroll, DB_USER et DB_PASSWORD dans l’environnement privé du processus. Le mot de passe doit être non vide ; root est refusé. DB_SOCKET peut sélectionner un socket absolu validé ; les cinq variables historiques restent requises même avec cette option.

Une fois l’environnement déjà fourni confidentiellement :

```bash
php -S 127.0.0.1:8080 -t public public/index.php
```

Consulter http://127.0.0.1:8080/login. Contrôler d’abord si un serveur écoute déjà pour éviter un second processus sur le même port. Le lanceur `python3 bin/local-demo.py serve` peut demander le secret en privé. Aucun mot de passe ne doit figurer dans la commande, le rapport ou un export public.

APP_RUNTIME_DIR est optionnel ; il doit être un répertoire absolu existant, privé 0700 et appartenant au processus PHP. Il centralise les logs/compteurs et, lorsqu’il est explicitement configuré, les sessions. Sans cette option, le journal/limiteur utilisent storage/logs tandis que les sessions utilisent la configuration PHP courante.

## Installation neuve : ordre de dépendance à expliquer

Cette section décrit le workflow des scripts ; **ne pas appliquer sur la principale existante**. Les DDL MySQL ont des commits implicites, les migrations ne sont pas un rollback global et plusieurs scripts refusent de reprendre un état partiel.

1. Inspecter schéma, version et droits ; préparer un compte applicatif distinct des opérateurs d’installation.
2. Sur une base neuve autorisée seulement : socle identité/RBAC 001, catalogue des six rôles et permissions RH.
3. Créer le contexte RH verrouillé et ses droits requis ; structures 002, procédures 003, permissions 003 et références 004 si la démonstration les prévoit ; contrôle de collation du helper RH.
4. Préparer propriétaire rémunération verrouillé, structures 004/procédures 005 puis évolution 006 vers MAD, permissions 005 et droits des deux contextes. Un schéma historique partiellement MAD nécessite diagnostic ciblé, pas rejeu général.
5. Préparer propriétaire Paie et droits ; structures 007, opérations 008, permissions 006 et EXECUTE du service.
6. Pour Settlement : propriétaire, structures 009/opérations 010, permissions 007 et GRANT stricts. Pour IAM : propriétaire, opérations 011 sur tables existantes, permissions 008 et GRANT.
7. Vérifier DEFINER, paramètres/collations, ACCOUNT LOCK et droits réels ; recette avec personnes fictives distinctes ; seulement ensuite activer les modules web.

Les lanceurs existants portent les détails et gardes : `bin/local-demo.py` (socle/RH/rémunération), `bin/payroll-admin.py` (Paie), `bin/finalize-admin.py` (Settlement/IAM), `bin/mad-repair.py` (diagnostic/plan/répétition/correctif ciblé). Les verbes install/activate/provision/apply/create-demo ont des effets persistants et ne sont pas des commandes de lecture.

## Activation des fonctionnalités déjà installées

SETTLEMENT_ENABLED=1 et IAM_ENABLED=1 rendent accessibles les modules concernés ; leur défaut d’exemple est 0. Ils ne créent ni tables ni privilèges. La Paie et la rémunération n’ont pas de drapeau PAYROLL_ENABLED ou COMPENSATION_ENABLED dans le code. Une route peut donc exister mais retourner 503 si le SQL manque. referenceCurrencyReady ne vérifie que deux définitions de colonnes MAD ; il ne prouve pas la bonne version de toutes les routines.

Le document de démonstration rapporte les deux options activées lors de la recette du 6 novembre. Pour relancer cette démonstration installée, uniquement après vérification de l’absence du serveur existant :

```bash
SETTLEMENT_ENABLED=1 IAM_ENABLED=1 python3 bin/local-demo.py serve
```

Ne pas lancer install/activate-* pour simplement redémarrer le web. Les comptes et données de Nadia étaient déjà préparés.

## Inventaire et maintenance des privilèges

Le fichier `INSPECTION-MYSQL-LECTURE-SEULE.sql` prépare l’inventaire des tables, colonnes, contraintes, index, routines, paramètres et triggers. Les droits effectifs et comptes verrouillés nécessitent une visibilité suffisante. Les scripts inspect/verify des lanceurs peuvent nécessiter une authentification administrative déjà autorisée ; cette mission n’en a demandé aucune.

À titre de commande opérateur préparée, `sudo python3 bin/payroll-admin.py inspect` est décrite dans la documentation de démonstration comme inspection administrative : elle est nécessaire pour lire les propriétaires et droits que svc_php ne doit pas voir. Ne pas substituer install à inspect. Comparer les droits avec les listes précises `database/setup/*_grants.sql`, sans ajouter de privilège global pour faire disparaître une erreur.

Après remplacement ciblé d’une routine, vérifier ses EXECUTE propres : DROP/CREATE peut les supprimer. Vérifier aussi le DEFINER, les colonnes autorisées, l’absence de GRANT OPTION et le verrouillage du contexte. Les modifications de comptes/droits restent des opérations distinctes, jamais une maintenance automatique au démarrage HTTP.

## Sauvegarde non destructive

`bin/backup.py` exige un compte de sauvegarde déjà existant (profil privé ou saisie via stdin), un répertoire 0700 appartenant à l’opérateur, hors projet, et refuse l’utilisateur système root. Il utilise TCP local ou socket explicite et vérifie la cible secure_payroll et le compte dédié.

Exemple **opérateur seulement**, exportant vers un répertoire privé déjà préparé :

```bash
python3 bin/backup.py --login-path securepayroll-backup --directory /CHEMIN/PRIVE/EXISTANT
```

Le dump utilise single-transaction/quick/routines/triggers/events/hex-blob/no-tablespaces/set-gtid-purged=OFF. Pendant le dump, éviter les DDL : single-transaction assure la cohérence des tables InnoDB dans ces conditions, pas un instantané de tous les éléments système. Le script conserve un fichier partial en cas d’erreur, puis un database.sql après succès, un manifeste SHA256/tailles et EXPORT_COMPLETE ; ce marqueur prouve l’export et copie des logs, pas une restauration testée. Les fichiers sont 0600.

Les journaux copiés ne sont pas synchronisés transactionnellement avec le dump. Les comptes MySQL et leurs secrets ne sont pas exportés comme des données applicatives : inventorier séparément les contextes et droits, conserver les secrets sur un canal privé. Stocker une copie durable protégée/chiffrée ; /tmp et /var/tmp restent des supports temporaires, pas une politique d’archivage.

## Restauration et reprise

**Avertissement : une importation SQL peut remplacer ou écraser des structures et données.** Aucun import n’est exécuté ni proposé sur la principale dans ce livrable. Le dump contient CREATE DATABASE et USE secure_payroll ; changer uniquement --database au client ne détourne pas ces instructions vers une base de test.

La méthode sûre documentée consiste à provisionner une autre instance explicitement isolée, vérifier son datadir/socket, préparer les propriétaires verrouillés, importer le dump dans cette instance, réappliquer strictement les GRANT puis vérifier les empreintes, comptes de lignes, totaux, DEFINER et triggers. Une recette non-root et des refus d’altération doivent suivre. Les programmes `lab/mysql-recovery.py`, `lab/mysql-final-recovery.py` et `lab/demo-settlement-check.py` mettent en œuvre des variantes isolées ; ils écrivent et nécessitent une mission de test autorisée distincte.

Une remise en place sur la principale exige un plan de reprise tenant compte des écritures postérieures à la sauvegarde. Ne jamais importer la sauvegarde pré-démo pour réinitialiser la présentation : elle précède les nouveaux comptes et le bulletin. Aucun RPO/RTO mesuré ne peut être annoncé d’après les sources.

## Journaux et diagnostic

```bash
tail -n 80 storage/logs/application.log
rg 'contract.create|Application unavailable' storage/logs/application.log
```

Adapter le chemin si APP_RUNTIME_DIR est activé. Le journal n’est pas une page web ; restreindre sa lecture et sa sauvegarde. Les traces métier détaillées se consultent dans compensation-detail, payslip, settlement et iam. Les événements techniques n’enregistrent pas de montant ni texte libre, contrairement aux tables métier contrôlées.

Diagnostiquer dans l’ordre : statut HTTP et route ; CSRF/session ; permission active et incompatibilité ; configuration privée ; version des objets SQL ; privilèges/DEFINER ; règles métier ; contention. Un 403 n’est pas une indisponibilité PDO. Un 409 signale conflit, gel ou version périmée ; un 422 signale une entrée/règle invalide ; un 503 peut provenir d’une configuration ou erreur SQL non traduite.

Pour `/contracts/new`, Controller journalise uniquement opération/SQLSTATE/code MySQL. Un échec de closeCursor peut survenir après COMMIT : un 503 ne prouve pas qu’aucun contrat n’a été créé. Rechercher d’abord la référence en lecture au lieu de renvoyer aveuglément le POST. Le diagnostic temporaire subsiste ; son retrait éventuel relève d’une future modification de code.

Sources : `docs/WEB-SETUP.md`, `LOCAL-DEMO.md`, `PAYROLL-ACTIVATION.md`, `FINALIZATION.md`, `RECOVERY.md`, `DEMO-PRESENTATION.md`, `bin/backup.py`, les lanceurs et les classes de configuration/sécurité. Les contradictions chronologiques sont recensées au chapitre 12.
