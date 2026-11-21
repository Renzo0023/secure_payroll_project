# Mission 04 — livraison de la première interface web

## Fonctionnalités livrées

Connexion réelle par PDO et password_verify pour les empreintes Argon2id, contrôles
de compte et d’employé actifs, rôles actuellement valides, sessions sécurisées,
CSRF, limitation locale des tentatives et déconnexion POST. Aucun accès de
démonstration n’est fourni.

Tableau de bord avec navigation latérale, barre supérieure, identité et tous les
rôles actifs de la personne connectée. Chaque rôle possède son espace explicatif ;
seul le module RH est fonctionnel dans cette version. Paie, Finance, IAM et Audit
ne présentent aucune donnée artificielle.

Annuaire RH avec recherche et pagination, détail d’employé, création, modification
du prénom et du nom. La fiche personnelle est lisible par son titulaire ; les
opérations sur l’annuaire nécessitent HR Manager et la permission correspondante.
La validation serveur, les requêtes préparées, l’échappement HTML et la protection
contre les modifications concurrentes sont intégrés. Le matricule et les colonnes
techniques ne sont pas modifiables. Aucun formulaire d’archivage ou de suppression
n’est livré pour cette étape.

## Fichiers

Créés :

- app/Auth/AuthService.php
- app/Security/Session.php et LoginLimiter.php
- app/HR/EmployeeRepository.php
- app/Web/Controller.php et helpers.php
- app/Views/login.php, header.php, footer.php, dashboard.php, employees.php,
  employee.php, employee-form.php et error.php
- public/assets/app.css et app.js
- database/seeds/002_hr_permissions.sql (préparé, non exécuté)
- docs/WEB-SETUP.md et ce compte rendu

Modifiés : public/index.php (routage web et assets), app/bootstrap.php (autoload et
masquage des arguments d’exception), app/Database/Connection.php (refus de root),
.env.example (nom de base illustratif corrigé) et README.md.

Les migrations 001, le seed des six rôles, config/database.php et les tests
existants sont conservés. Aucun framework, paquet ou système de test n’est ajouté.

## Vérifications effectivement réalisées

- Syntaxe valide des 18 fichiers PHP dans app/, config/ et public/.
- Autoload des classes du contrôleur, de l’authentification, de la session et du dépôt RH.
- HTTP 200 de /login, formulaire et jeton CSRF présents, cookie HttpOnly/SameSite=Lax,
  réponses sans cache ; CSS et JavaScript accessibles avec leurs types MIME.
- HTTP 404 pour une route inconnue, /app/bootstrap.php et /config/database.php.
- Redirection 303 vers la connexion pour les pages privées sans session authentifiée.
- GET /logout refusé en 405 ; POST sans CSRF refusé en 403 ; déconnexion POST avec
  jeton valide redirigée en 303.
- Configuration DB_* absente : tentative de connexion web en 503 générique, sans
  SQLSTATE, chemin interne ou message PDO ; aucun accès MySQL n’a été effectué.
- Cinq cas d’autorisation hors connexion : absence de rôle, employé et administrateur
  refusés pour la création RH ; HR Manager sans permission refusé ; avec permission autorisé.
- Validation des noms Unicode, des champs vides et longueurs excessives ; CSRF invalide,
  valeur tableau et jeton correct ; rendu CLI des quatre vues privées avec contrôle
  d’échappement d’un texte contenant des balises.

Les données du contrôle de rendu sont exclusivement en mémoire CLI : elles ne
sont ni sauvegardées ni exposées par l’application, et n’authentifient personne.
La vérification initiale d’en-tête a été ajustée pour accepter le Cache-Control
renforcé par PHP (no-store, no-cache, must-revalidate). Le contrôle final passe.
Un appel de contrôle CLI utilisant une option d’assertion dépréciée a été retiré ;
les vérifications finales utilisent des conditions explicites.

## À effectuer après validation MySQL

La connexion réelle, l’état installé du schéma, les autorisations avec de vraies
attributions, la création et la modification sur MySQL n’ont pas été testés : les
cinq variables DB_* étaient absentes dans cette session. Ne pas confondre la
livraison du code et une validation de bout en bout sur une base installée.

Voir WEB-SETUP.md pour les prérequis : migration 001 validée si nécessaire, seed
des rôles, approbation du seed 002 des permissions RH, compte SQL applicatif non-root
à privilèges limités, première identité et attribution de rôle créées par un
administrateur habilité. Aucune de ces opérations administratives n’a été exécutée.

## Visualisation

Le port 8000 était occupé ; son processus n’a pas été modifié. Un serveur de
développement a été lancé pour cette application sur :

**http://127.0.0.1:8080/login**

Pour le relancer si nécessaire, depuis la racine et après fourniture privée de
l’environnement : `php -S 127.0.0.1:8080 -t public public/index.php`.
Ce serveur est réservé au développement. Aucune publication ou configuration
système n’a été effectuée et aucune commande Git n’a été utilisée.
