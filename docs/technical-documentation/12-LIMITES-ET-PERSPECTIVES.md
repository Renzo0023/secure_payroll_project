# 12 — Limites, contradictions et perspectives

> Synthèse documentaire au 11 novembre 2026. Les chiffres sont repris des rapports identifiés ; aucun test MySQL/HTTP, migration ou scénario offensif n’a été exécuté pour rédiger ces documents.

## Limites fonctionnelles confirmées

La paie est une simulation académique en MAD. Elle ne calcule ni barèmes légaux d’impôt, ni cotisations sociales, ni congés légaux, ni heures supplémentaires, ni avantages en nature réglementaires. Bonus et deduction sont des montants approuvés, pas des assiettes fiscales. Il n’existe pas de connexion bancaire, paiement réel, déclaration fiscale ni export comptable réglementaire.

Le bulletin est une page HTML. Le PDF de ce dossier est un rapport documentaire externe, sans créer une fonctionnalité d’export PDF de bulletin dans l’application. Les départements/postes sont des catalogues consultables : aucun CRUD web de référentiel n’est implémenté. La fiche personnelle ne permet pas au salarié d’éditer son identité. L’archivage et la désactivation sont modélisés mais non exposés comme commandes RH générales dans les routes.

IAM gère les attributions, pas la création de comptes, la réinitialisation de mots de passe, la création de rôles ou la modification de permissions. La structure accepte expiration et planification, mais le formulaire d’octroi ne les propose pas. Les octrois puissants ne font pas l’objet d’une seconde approbation indépendante. Les limites de sélection (500 comptes/salariés, 120 mois) demandent une évolution pour de plus gros volumes.

La correction financière est un remplacement motivé de totaux, avec circuit indépendant ; elle ne recalcule pas le calendrier historique ni ne produit une nouvelle condition salariale. Le paiement fictif couvre le solde positif intégral ; un paiement partiel choisi ou échelonné n’est pas implémenté. La restitution n’entraîne aucune retenue automatique sur un mois futur.

## Limites de sécurité et de preuve

L’architecture partage un compte MySQL de service. L’acteur est transmis comme paramètre de routine après authentification PHP ; MySQL ne lie pas ce paramètre à une identité web indépendante. Une compromission du serveur ou de ses identifiants dépasse donc la garantie de séparation offerte aux utilisateurs normaux de l’application. Les SELECT directs de rémunération autorisés au service élargissent aussi l’impact d’une compromission de ce compte.

Les triggers bloquent les DML ordinaires mais pas un acteur administratif capable de modifier schéma, triggers ou droits. Les journaux techniques sont des fichiers locaux ; pas d’export vers un collecteur immuable, ni signature externe des décisions. La journalisation RH PHP ne forme pas une transaction atomique avec l’écriture d’identité. Le hash de snapshot protège la cohérence des sources dans le workflow ; il ne constitue pas une preuve juridique signée.

Le limiteur est par IP et local, sans gestion distribuée ; un NAT partagé peut pénaliser des utilisateurs. Le HTTP local ne positionne pas Secure sur les cookies ; une exposition distante nécessiterait HTTPS et un serveur adapté. MFA, politique de rotation/compromission, historique de mots de passe, révocation globale centralisée et surveillance d’événements externes ne sont pas démontrés. Chiffrement disque, TLS MySQL et stratégie de sauvegarde chiffrée actuelle : **Non vérifié**.

Une validation statique ou un test unitaire réussi n’est pas une preuve fonctionnelle serveur. Les scénarios isolés ne certifient pas les privilèges principaux. Les rapports décrivent les chemins exercés, pas un audit de sécurité exhaustif ni une mesure de charge, disponibilité ou conformité réglementaire. L’état courant du serveur n’a pas été inspecté et tous les artefacts historiques temporaires n’ont pas été relus.

## Contradictions documentaires et résolution par le code / la date

| Source historique | Énoncé à contextualiser | Constat retenu |
|---|---|---|
| WEB-SETUP.md | Paie/Finance/IAM/Audit à venir | Controllers, migrations 007–011 et vues existent ; modules livrés ensuite |
| WEB-SETUP.md | Les succès de connexion consomment le quota | LoginLimiter::succeeded libère maintenant la réservation propre ; campagne dédiée de 18 assertions |
| LAB-VALIDATION-2026-11-06.md | Paiement, correction et console IAM encore à définir | FINALIZATION-VALIDATION du même jour les décrit ensuite implémentés et testés isolément |
| FINALIZATION-VALIDATION / RECOVERY | Aucune opération principale dans ces campagnes | DEMO-PRESENTATION et demo-verification.json attestent une étape principale ultérieure ; ne pas généraliser le statut ancien |
| tests/validation-03c1/REPORT.md | Validation MySQL bloquée | Historique exact pour cette préparation ; le socle a ensuite 33 assertions isolées via un autre lanceur |
| Migration 004 / procédures 005 | UM et CHAR(2) | Version initiale ; 006 et patches MAD élargissent et changent les nouvelles opérations ; UM ancien reste valide |
| Commentaire Money.php | Réutilisable par de futurs bulletins | Les vues payslip/payroll utilisent déjà Money::format ; commentaire resté historique |
| Instructions de diagnostic contrat | Marqueur HTTP temporaire | Le document indique son retrait ; code actuel conserve seulement le diagnostic technique restreint |
| Rapports d’instances/PID /tmp | Processus en attente et chemins de preuves | Observations de session, pas preuve qu’ils sont encore actifs ou présents au 11 novembre |

La documentation présente donc une chronologie et ne fusionne pas tous les états anciens en une unique vérité. Le code actuel tranche les fonctionnalités ; les rapports datés tranchent seulement ce qui a été effectivement exercé lors de leur campagne.

## Améliorations envisageables — non implémentées

- Formaliser et faire valider une politique de paie réglementaire avant tout usage réel : fiscalité, cotisations, absences, arrondis, justificatifs et conformité de bulletin.
- Renforcer la séparation des contextes et l’authentification des acteurs jusqu’à la frontière SQL ; réduire l’exposition des données salariales au compte partagé.
- Déployer sur un serveur PHP de production avec HTTPS, permissions privées, stockage protégé, logs centralisés, supervision et procédures d’incident.
- Ajouter MFA et gestion sécurisée du cycle de vie des comptes/secrets, sans contourner l’audit IAM et avec approbations adaptées aux rôles sensibles.
- Industrialiser les migrations par inventaire/version explicite, préconditions, répétitions de restauration, sauvegardes durables et contrôle des DEFINER/GRANT.
- Automatiser des campagnes isolées reproductibles et une traçabilité signée des résultats, puis étudier charge, index et plans d’exécution sur volumes réalistes.
- Compléter les limites UX : recherche dans les sélecteurs volumineux, formulaires de catalogues si besoin autorisé, accessibilité auditée, export de bulletin distinct et rétention documentaire.
- Définir des objectifs RPO/RTO mesurés, une conservation des logs/sauvegardes, une vérification périodique de restauration et un contrôle de dérive des privilèges.

Aucune de ces perspectives n’a été ajoutée au code dans cette mission.
