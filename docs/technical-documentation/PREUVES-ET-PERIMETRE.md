# Preuves et périmètre documentaire

Analyse locale du 11 novembre 2026. Aucune commande Git, installation, migration, attaque, modification du code applicatif ou accès administratif supplémentaire n’a été exécuté. Tous les nouveaux livrables sont dans docs/technical-documentation/.

| Observation courante | Résultat | Portée |
|---|---|---|
| Sources migrations 001–011 et patches | 25 tables ; 24 procédures distinctes ; 42 triggers | Inventaire statique, pas installation live |
| Seeds permissions 002/003/005/006/007/008 | 31 permissions ; six rôles | Politique déclarée, pas attribution actuelle |
| Environnement de cette session | Aucune variable DB_* ou MYSQL_* disponible | Aucune connexion MySQL principale tentée |
| Fichiers de configuration | .env.example présent ; aucun .env trouvé à la racine | Le modèle n’est pas chargé automatiquement |
| storage/logs/demo-verification.json | Fichier lisible, passed=true, 64 libellés, 06/11/2026 | Recette historique principale, pas revalidation courante |
| Rapport de finalisation isolée | 349 contrôles serveur et 426 hors connexion annoncés | Résultats historiques du rapport identifié |
| Artefact storage/mad-repair…/applied.json | Lecture refusée | Aucun contournement ; contenu Non vérifié |
| Autres dumps /tmp ou /var/tmp des campagnes | Non relus intégralement | Disponibilité et intégrité actuelles Non vérifié |

Les empreintes de SOURCES-SHA256.md permettent de rattacher les constats aux fichiers versionnés effectivement disponibles. Les données de connexion, cookies, sessions, mots de passe et empreintes réelles de comptes ne sont pas copiés.
