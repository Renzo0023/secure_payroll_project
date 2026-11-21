# Activation des nouveaux modules paie et bulletins

État de démonstration du 6 novembre 2026 : les modules et les six comptes sont
installés sur la principale ; le bulletin Nadia n°1 est publié et réglé fictivement.
Suivre [DEMO-PRESENTATION.md](DEMO-PRESENTATION.md) pour la présentation.
Les commandes d’installation ci-dessous sont conservées comme référence et ne
doivent pas être exécutées sur cette base déjà installée.

Référence technique : suivre également [FINALIZATION.md](FINALIZATION.md). Le lanceur
produit désormais son propre snapshot cohérent et son manifeste SHA256 avant
le premier DDL ; il ne repose plus sur une simple déclaration de sauvegarde.
Les nouveaux paiements/corrections et l’IAM ont une activation distincte, avec
les mêmes protections contre le rejeu. Cette procédure décrit leur préparation
antérieure ; ils sont désormais présents et vérifiés sur la principale.

La présence des quatre tables de rémunération et de `finance.demo` a été confirmée
par l'utilisateur. **Ne pas relancer activate-compensation, create-finance-demo,
ni les migrations 001 à 006.** Le parcours RH → Finance de Nadia est confirmé et a été conservé.

Les nouveaux fichiers ont été appliqués et testés sur MySQL 8.4.11 dans le
laboratoire explicitement autorisé : calculs, workflow HTTP authentifié, IDOR,
concurrence, privilèges et restauration ont été exercés. Voir
[le rapport](LAB-VALIDATION-2026-11-04.md). Ils ne sont **pas appliqués à
l’instance principale lors de cette ancienne campagne**. L’installation a depuis été
réalisée par l’opérateur, puis vérifiée pendant la finalisation. Une future mise à jour requiert une validation
administrative distincte et une sauvegarde privée récente.

## Plan administratif précis

L'installation nécessite un nouveau propriétaire verrouillé, des DDL et des GRANT.
Elle doit être effectuée après revue, sauvegarde et validation explicite dans un
terminal administrateur. Depuis le projet :

```bash
sudo python3 bin/payroll-admin.py inspect
```

Cette commande lit l'état sans installation. Elle vérifie MySQL 8.4, les tables
prérequis, les colonnes MAD, les procédures de rémunération MAD, le compte Finance
existant et les privilèges de svc_php. Elle n'affiche aucun secret. Si MAD n'est pas
confirmé, examiner l'état de 006 avec le DBA ; ne pas la rejouer automatiquement.

Après validation du plan d'installation :

```bash
sudo python3 bin/payroll-admin.py install --apply
```

Le lanceur affiche les fichiers et leurs SHA256 puis demande `secure_payroll`.
Il refuse tout propriétaire, table, procédure ou trigger homonyme, y compris après
un échec partiel. Il n'utilise pas `--force`, n'efface rien, ne remplace aucun objet
et n'installe jamais les anciennes rémunérations. Arrêter les écritures web pendant
l'installation pour éviter l'exposition d'un module partiel.

Ordre des nouveaux fichiers uniquement :

1. `database/setup/payroll_owner.sql` : propriétaire MySQL `payroll_owner@localhost`
   verrouillé, sans connexion autorisée ; aucun mot de passe dans les fichiers.
2. `database/migrations/007_payroll.sql` : six nouvelles tables et douze triggers
   interdisant UPDATE/DELETE.
3. `database/migrations/008_payroll_operations.sql` : dix procédures DEFINER.
4. `database/setup/payroll_owner_grants.sql` : droits dédiés du propriétaire.
5. `database/seeds/006_payroll_permissions.sql` : neuf permissions, associations
   aux rôles déjà présents ; aucun nouveau rôle.
6. `database/setup/payroll_grants.sql` : sept EXECUTE publics pour svc_php,
   aucun SELECT/INSERT/UPDATE/DELETE sur les nouvelles tables.

Les DDL impliquent des commits implicites. Après échec : conserver la sortie,
examiner l'état et préparer une reprise ciblée avec le DBA. Ne pas relancer le
lanceur, supprimer les objets partiels ou contourner ses contrôles.

## Comptes de présentation

Les six comptes sont désormais présents : `rh.demo`, `finance.demo`,
`payroll.demo`, `employee.demo`, `admin.demo`, `audit.demo`. Le compte
`employee.demo` appartient à **Nadia**, matricule `EMP-2026-001`, sans doublon.
Ne lancer aucune ancienne commande `create-demo` sur cette installation.
L’IAM est accessible à l’administrateur et en lecture à l’auditeur.

Le mécanisme existant de création a été complété par `demo-inventory` et
`provision-demo` dans `bin/payroll-admin.py` : inventaire avant toute écriture,
refus des collisions/rôles incompatibles, sauvegarde, création des seuls absents,
hachages Argon2id reçus sur stdin. Une identité existante n’est pas réaffectée.
`bin/demo-finalize.py --apply` orchestre cette préparation puis le parcours HTTP
avec les rôles séparés ; il ne rejoue aucune migration. Il peut reprendre un
bulletin déjà préparé ou publié sans recréer le calcul ou le paiement. Il vérifie
les montants avant approbation et s’arrête sur toute divergence.

La récupération privée et unique des quatre nouveaux mots de passe se fait avec
`python3 bin/demo-passwords.py` dans le terminal de l’utilisateur, sans redirection.
Aucun mot de passe en clair n’est conservé dans un fichier du projet. Voir le
[guide de démonstration](DEMO-PRESENTATION.md) pour les limites et l’état vérifié.

## Vérifications connectées sans écriture métier

Utilisateur Ubuntu habituel, sans sudo :

```bash
python3 bin/payroll-check.py --login rh.demo
python3 bin/payroll-check.py --login finance.demo
python3 bin/payroll-check.py --login payroll.demo
python3 bin/payroll-check.py --login employee.demo
```

Chaque commande demande confidentiellement le secret MySQL existant de svc_php
puis le mot de passe applicatif. Aucun secret n'est sauvegardé. La vérification
s'authentifie réellement, appelle les procédures de lecture et contrôle les lignes
retournées. Un résultat sans bulletin indique explicitement que le parcours de
publication n'est pas testé. Pour un test IDOR négatif, fournir un identifiant
connu d'un bulletin étranger ou non publié :

```bash
python3 bin/payroll-check.py --login employee.demo --forbidden-payslip-id 123
```

Remplacer 123 par une véritable ligne interdite au compte ; un identifiant inexistant
ne prouve pas l'isolation entre deux employés. Compléter avec deux comptes employés
et leurs bulletins publiés. Le lanceur n'affirme pas avoir testé la concurrence,
les écritures ou les comptes propriétaires.

Relancer le serveur web avec les secrets privés existants :

```bash
python3 bin/local-demo.py serve
```

Consulter `/payroll`. Le menu apparaît seulement après installation des permissions
et pour les rôles autorisés. Toutes les actions d'écriture utilisent POST et CSRF.

Le contrôle final du propriétaire compare le jeu de droits exact, y compris les
restrictions de colonnes. Il refuse aussi bien des droits manquants que des droits
excédentaires, une lecture de schéma, un accès aux empreintes des comptes ou un
rôle SQL hérité. Les scénarios du vérificateur peuvent être exécutés sans connexion :

```bash
python3 tests/payroll-grants.py
```
