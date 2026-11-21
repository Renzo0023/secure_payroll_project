# Mission 05B — activation avec un propriétaire MySQL dédié

## Commande locale exacte après revue

Depuis le terminal Ubuntu permettant l’authentification sudo :

```sh
cd ~/projects/database-security
sudo python3 bin/local-demo.py activate-hr --apply --with-demo-catalogues
```

L’opérateur confirme la cible en tapant `secure_payroll`. Le lanceur utilise le
client mysql local par socket pour l’installation administrative uniquement.
L’option --lang en permet d’afficher les messages anglais. Aucun mot de passe
de compte applicatif n’est demandé pour cette activation.

Pour utiliser vos propres départements/postes au lieu des exemples HR/FIN/IT,
omettre --with-demo-catalogues. Ne pas exécuter les deux variantes : il s’agit
de deux choix pour une même première activation. Après une installation sans
catalogue, le DBA pourra alimenter les deux tables avant les affectations.

Le lanceur vérifie les six tables existantes, HR Manager et svc_php@localhost,
l’absence de rôles SQL obligatoires, les droits de svc_php et l’absence des quatre
tables, des neuf objets et du propriétaire RH. Une collision entraîne un arrêt,
sans remplacement, suppression ou modification de données existantes. Cela couvre
aussi une ancienne installation 05A : ne pas rejouer les migrations pour changer
un DEFINER déjà installé ; le DBA doit préparer une reprise ciblée sans recréer
les tables ou perdre leur contenu.

L’ordre d’application est fixé dans le lanceur :

1. database/setup/advanced_hr_owner.sql : crée hr_module_owner@localhost, verrouillé.
2. database/migrations/002_advanced_hr.sql : crée les quatre tables et quatre triggers.
3. database/migrations/003_hr_period_operations.sql : crée les cinq procédures.
4. database/setup/advanced_hr_owner_grants.sql : attribue les droits d’exécution ciblés.
5. database/seeds/003_advanced_hr_permissions.sql : huit permissions au rôle RH existant.
6. database/setup/advanced_hr_grants.sql : SELECT et quatre EXECUTE supplémentaires à svc_php.
7. database/seeds/004_hr_reference_demo.sql seulement si demandé explicitement.

À la première erreur MySQL, le lanceur s’arrête et affiche seulement son code
numérique. Les DDL/DCL antérieurs peuvent déjà être validés ; ne pas relancer
aveuglément. Aucun DROP, nettoyage ou retour arrière destructif n’est automatisé.
Les migrations 001, les six rôles et le premier utilisateur RH ne sont pas rejoués.

## Corrections des propriétaires

Les clauses DEFINER étaient implicites. Une installation exécutée administrativement
aurait attribué les objets à cet administrateur. Elles sont désormais toutes fixées
à `'hr_module_owner'@'localhost'` :

| Objet | Contrôle conservé |
| --- | --- |
| hr_assert_permission | Compte actif, employé actif, rôle HR Manager et permission à la date courante |
| hr_create_assignment | Références actives, dates, verrou parent et absence de chevauchement |
| hr_close_assignment | Même ordre de verrous, fin valide et première clôture uniquement |
| hr_create_contract | Type, référence, dates et absence de chevauchement pour tout type |
| hr_close_contract | Fin valide, parent verrouillé et clôture définitive |
| ea_no_delete / ec_no_delete | Refus des suppressions d’historique |
| ea_preserve_history / ec_preserve_history | Immutabilité des données d’origine, première clôture ou UPDATE sans changement |

Les procédures restent SQL SECURITY DEFINER ; les triggers utilisent par définition
le contexte de leur DEFINER. Les contrôles PHP de rôle/permission, le CSRF, les
requêtes PDO et les interfaces FR/EN restent inchangés. La connexion PDO web reste
svc_php, jamais le propriétaire ou root. Le scope de cette correction couvre
uniquement les neuf nouveaux objets, sans modifier les triggers de la migration 001.

## Privilèges exacts du propriétaire

hr_module_owner est un compte d’exécution, sans connexion interactive. Le mot de
passe aléatoire est généré par MySQL pour rester compatible avec validate_password,
puis sa sortie est capturée et ignorée par le lanceur, sans affichage ou fichier.
ACCOUNT LOCK reste obligatoire. Ne pas exécuter advanced_hr_owner.sql isolément
avec une sortie vers le terminal ou des logs, car MySQL renvoie le secret généré.
Ne pas déverrouiller, renommer, supprimer ou prêter ce compte à svc_php via rôle/proxy.

Ses droits sont définis dans advanced_hr_owner_grants.sql :

- SELECT limité aux colonnes utilisées sur les comptes, employés et tables RBAC ;
  aucun accès à accounts.password_hash ou accounts.login.
- SELECT id/archived_at sur les deux catalogues, et SELECT sur les deux historiques.
- INSERT limité aux colonnes de création des deux historiques.
- UPDATE limité aux trois colonnes de clôture des deux historiques.
- UPDATE(id) sur employees, nécessaire au SELECT FOR UPDATE du parent sous MySQL
  8.4. Les procédures n’exécutent aucun UPDATE employees. Ce droit ne modifie pas
  les droits de svc_php et ne déclenche pas le trigger d’identité pendant un SELECT.
  Le trigger 001 existant interdit en outre les changements effectifs de cet id.
- TRIGGER uniquement sur employee_assignments et employment_contracts, requis à
  l’activation des quatre triggers, même pour un trigger qui refuse un DELETE.
  Ce privilège permet aussi de créer/supprimer des triggers sur ces deux tables :
  MySQL n’a pas de privilège séparé limité à leur activation. D’où le compte
  verrouillé, sans connexion/proxy accordé et sans SQL dynamique dans les routines.
- EXECUTE sur les cinq procédures : le DEFINER doit pouvoir exécuter les routines,
  notamment hr_assert_permission appelée par les quatre autres.

Aucun privilège global, droit sur une autre base, CREATE/ALTER/DROP de table, DELETE,
CREATE ROUTINE, GRANT OPTION ou droit d’écriture IAM n’est donné au propriétaire.
Les UPDATE des historiques restent contrôlés par les triggers. Le propriétaire
ne reçoit pas de rémunérations ni de validation financière.

Le compte d’installation doit disposer des droits administratifs nécessaires à
CREATE USER, CREATE TABLE, CREATE ROUTINE, TRIGGER, aux GRANT concernés et à
SET_ANY_DEFINER pour désigner un autre propriétaire. Selon la politique du journal
binaire, CREATE TRIGGER peut aussi demander SUPER. Ces droits restent ceux de
l’administrateur lors de la création ; ils ne sont pas accordés au propriétaire
ou à svc_php. Aucun réglage global ni configuration système n’est modifié ici.

## Garanties concernant svc_php

advanced_hr_grants.sql ne contient que quatre SELECT et quatre EXECUTE ; aucun
EXECUTE direct sur hr_assert_permission et aucun DML sur les nouveaux historiques.
Le lanceur contrôle SHOW GRANTS avant et après activation. Il refuse les rôles SQL,
GRANT OPTION, droits globaux (hors USAGE), autres bases, DDL, droits de schéma global
et écritures sur les historiques. Les seules écritures directes admises restent
les INSERT employee_number/first_name/last_name et UPDATE first_name/last_name de
la table employees, déjà nécessaires au module opérationnel.

Un profil svc_php plus large entraîne un arrêt pour revue DBA, sans révocation
automatique qui pourrait casser une fonctionnalité existante. La politique suppose
que les fichiers et les droits ne sont pas modifiés simultanément par un autre
administrateur pendant l’installation. Les comptes de DBA restent hors de cette
garantie de moindre privilège.

## Vérification après activation

Le lanceur vérifie réellement, lorsqu’il est exécuté : compte propriétaire verrouillé,
cinq procédures SECURITY_TYPE=DEFINER et quatre triggers appartenant tous à
hr_module_owner@localhost, huit permissions RH et périmètre des grants de svc_php.
Un message final n’est affiché qu’après ces contrôles, pas comme preuve anticipée.

Dans le navigateur, recharger http://127.0.0.1:8080/login et utiliser le compte RH
existant. Si le serveur tourne déjà, aucun redémarrage n’est nécessaire pour relire
les permissions. Sinon, sous votre utilisateur habituel, sans sudo :

```sh
python3 bin/local-demo.py serve
```

1. Ouvrir Départements et Postes ; avec les catalogues de démonstration, les listes
   contiennent trois départements et quatre postes, traduits suivant FR/EN.
2. Ouvrir une fiche employé, puis Enregistrer une affectation. Choisir son matricule,
   un département, un poste et les dates ; enregistrer et consulter l’historique.
3. Depuis cette fiche, Créer un contrat avec une référence unique et les dates.
   Un contrat permanent reste sans fin prévue ; les autres types exigent une fin.
4. Consulter le détail, puis essayer une période qui chevauche le même employé :
   elle doit être refusée. Les jours de fin sont inclusifs.
5. Clôturer une période ; vérifier que ses dates d’origine restent affichées et
   qu’une nouvelle période commence au plus tôt le lendemain de sa fin effective.
6. Vérifier ces parcours en FR et EN. Aucun montant ou bouton d’approbation salariale
   n’est présent. Les autres rôles ne reçoivent pas ces permissions par le seed.

L’usage du navigateur valide les parcours métier ; la concurrence de deux écritures
et la validité des droits réduits pendant les CALL restent aussi à vérifier sur
MySQL. Aucun succès SQL ou navigateur authentifié n’est déclaré par la préparation.

## Contrôles hors connexion de cette mission

Inspection des cinq procédures et quatre triggers, contrôle des neuf clauses
DEFINER, absence de droits globaux/DDL/DELETE du propriétaire, périmètre des GRANT,
syntaxe Python et catalogues FR/EN contrôlés sans appel MySQL. Un jeu de droits
svc_php conforme est accepté et dix variantes trop larges sont refusées par le
précontrôle. Les gardes --apply et identité administrative sont vérifiées avec
des appels MySQL neutralisés, sans nouveau fichier/framework de tests.

Aucune migration, création de compte, commande sudo ou Git n’a été exécutée pour
cette mission. Les objets déjà installés et les fonctions opérationnelles ne sont
pas modifiés sur le serveur.

Références : [contexte des objets stockés](https://dev.mysql.com/doc/refman/8.4/en/stored-objects-security.html),
[verrouillage du compte propriétaire](https://dev.mysql.com/doc/refman/8.4/en/account-locking.html),
[privilèges des lectures verrouillantes](https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html),
[privilèges des triggers](https://dev.mysql.com/doc/refman/8.4/en/create-trigger.html).
