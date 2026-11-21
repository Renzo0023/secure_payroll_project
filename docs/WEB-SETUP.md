# Première version web — installation locale

L’application utilise les six tables et rôles existants de la migration 001.
Aucun SQL n’est exécuté automatiquement au démarrage. La disponibilité réelle
des tables/comptes n’est pas attestée par cette mission ; aucune connexion MySQL
administrative n’a été effectuée.

## Prérequis à faire valider par le responsable MySQL

1. Si les six tables et les triggers ne sont pas installés, terminer la validation
   MySQL de la migration 001 puis approuver son application à secure_payroll.
   Ne pas rejouer une migration déjà appliquée.
2. Installer le seed 001 des six rôles s’il ne l’est pas déjà.
3. Relire puis faire approuver `database/seeds/002_hr_permissions.sql` : il prépare
   trois permissions et les associe au seul rôle HR Manager. Sans ce seed, le
   tableau de bord et la fiche personnelle fonctionnent ; la gestion RH reste refusée.
4. Prévoir un compte SQL applicatif **non-root**, différent du compte de migration,
   limité à secure_payroll. Les besoins de cette version sont SELECT sur accounts,
   employees, roles, role_assignments, permissions et role_permissions ; INSERT sur
   employees ; UPDATE limité à first_name et last_name sur employees. Aucun besoin
   de DELETE, DDL, GRANT ou d’écriture sur accounts/role_assignments pour le serveur web.
   Le compte applicatif ne crée pas de compte utilisateur depuis l’interface.
5. Préparer au moins une vraie identité de connexion dans les tables existantes :
   un employé non archivé, un compte non désactivé avec login unique, une empreinte
   générée par `password_hash(..., PASSWORD_ARGON2ID)` et une attribution du rôle
   hr_manager pour la personne habilitée à gérer les employés. Ne pas insérer un
   mot de passe en clair et ne pas utiliser les comptes MySQL comme logins web.

Cette mise en place des identités relève de l’administration IAM autorisée. Aucun
compte de démonstration, mot de passe initial ou mécanisme de contournement n’est
livré. Générer l’empreinte dans un processus privé qui lit le secret sans l’afficher
ni le placer dans l’historique ; transmettre uniquement l’empreinte par un mécanisme
privé au responsable habilité, jamais dans le dépôt ou la conversation.

Pour une attribution immédiate, fixer la session SQL à `+00:00` et omettre
granted_at et valid_from dans l’INSERT de role_assignments, comme prévu par la
migration. Renseigner l’auteur et le motif. Ne pas désactiver les triggers.

## Lancement sans changement système

Fournir DB_HOST, DB_PORT, DB_NAME=secure_payroll, DB_USER et DB_PASSWORD dans
l’environnement privé du processus PHP. Le .env n’est pas chargé automatiquement.
Le compte root est refusé par la classe PDO. Ne jamais mettre les identifiants
dans le code, la ligne de commande, Git ou une URL.

Depuis la racine :

```sh
php -S 127.0.0.1:8080 -t public public/index.php
```

Puis ouvrir **http://127.0.0.1:8080/login**. La page de connexion est consultable
même sans configuration MySQL ; une tentative de connexion renverra un message
générique d’indisponibilité si le service n’est pas prêt. Arrêt par Ctrl+C.
Seul public/ doit être exposé. Les assets CSS et JS sont servis par une liste
explicite dans le point d’entrée pour fonctionner avec le serveur intégré.

## Fonctions et autorisations

- Connexion réelle par login de accounts et password_verify, uniquement Argon2id.
- Compte désactivé ou employé archivé : accès refusé ; état et rôles relus à chaque requête.
- Sessions HttpOnly, SameSite=Lax, strict mode, identifiant renouvelé à la connexion
  et toutes les 15 minutes ; inactivité maximale 20 minutes, durée absolue 8 heures.
- CSRF sur toutes les opérations POST, dont connexion et déconnexion ; déconnexion
  refusée en GET ; réponses privées non mises en cache.
- Cinq tentatives de connexion par IP en 15 minutes, compteur verrouillé dans
  storage/logs/ ; aucune confiance dans X-Forwarded-For. Un poste/NAT partagé partage
  ce quota, y compris les tentatives réussies. Une nouvelle session ne contourne
  pas le quota. Les fichiers expirés sont réinitialisés à la prochaine tentative.
- Annuaire paginé et recherche littérale par prénom, nom ou matricule : HR Manager
  avec employees.read. Création : HR Manager avec employees.create. Modification :
  HR Manager avec employees.update. Un rôle administratif ou d’audit n’accorde pas
  implicitement de droit RH. Les autres rôles disposent de leur propre fiche en lecture.
- Modification limitée au prénom et nom ; matricule, identifiants techniques,
  création et archivage ne sont jamais écrits par le formulaire de modification.
  Détection des modifications concurrentes avec signature de version et UPDATE conditionnel.
- Tableaux de bord personnalisés pour chaque rôle actif. Les modules Paie, Finance,
  IAM et Audit sont annoncés comme à venir, sans données fictives ou boutons inactifs.
- Événements techniques de connexion, accès refusé et modification RH journalisés
  avec identifiants techniques, sans nom, login, empreinte ou mot de passe.

## Vérifications essentielles et limites

Vérifier la syntaxe PHP et les routes publiques ; puis, après installation autorisée,
essayer une vraie connexion, la lecture personnelle et les autorisations RH avec
des comptes réellement attribués. Vérifier un POST sans CSRF, la déconnexion, le
refus d’accès aux fiches d’autrui, le doublon de matricule et une modification concurrente.
Aucun nouveau système de tests n’est nécessaire.

Utiliser HTTPS au déploiement pour activer le cookie Secure ; le HTTP local reste
réservé au développement. La détection HTTPS repose sur la configuration serveur,
pas sur des en-têtes proxy fournis par le client. En cas de terminaison TLS sur un
proxy, configurer proprement le serveur dans une future mission de déploiement.
Le limiteur local n’est pas distribué et ne protège pas une ferme multi-serveurs.
Les journaux techniques ne remplacent pas un audit métier immuable/transactionnel :
une écriture RH et son événement de journal ne forment pas une transaction atomique.
La matrice d’incompatibilités et les approbations de rôles restent hors périmètre.

## Connexion par socket et runtime isolé

La variable optionnelle `DB_SOCKET` sélectionne explicitement un socket Unix absolu.
Son chemin est validé pour refuser l'injection de paramètres DSN ; il n'y a pas de
repli silencieux vers TCP en cas d'échec. Les cinq variables DB_* historiques
restent requises. Sans DB_SOCKET, la connexion TCP existante est conservée.

`APP_RUNTIME_DIR`, optionnelle, doit désigner un répertoire absolu existant,
accessible, privé (0700) et appartenant au processus PHP. Elle isole les journaux,
les compteurs de connexion et les sessions. Sans cette option, les chemins
historiques restent utilisés. Ces options sont fournies uniquement au processus
de laboratoire, sans changement d'environnement du serveur principal.
