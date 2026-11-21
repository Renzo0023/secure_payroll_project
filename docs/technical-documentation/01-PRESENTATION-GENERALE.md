# 01 — Présentation générale de SecurePayroll

> Périmètre : analyse des sources au 11 novembre 2026. Les attestations de tests sont datées ; aucune campagne fonctionnelle n’a été relancée. Installation MySQL actuelle : **Non vérifié**.

## Finalité académique

**SecurePayroll — Secure Employee & Payroll Management System** est une application web locale de gestion des employés et de simulation de paie développée dans le cadre du module Database Security. Elle permet d’étudier une chaîne de décisions distinctes, depuis le contrat administratif jusqu’au paiement fictif, en faisant de MySQL une frontière de contrôle métier et de sécurité.

Le projet associe PHP/PDO, MySQL, HTML, CSS et JavaScript. Il ne déclare pas de framework MVC externe ni d’ORM : les classes `App\…` sont chargées par `app/bootstrap.php`, le routeur est écrit dans `app/Web/Controller.php` et les vues PHP produisent le HTML. L’environnement Ubuntu sous VMware est le contexte de réalisation fourni ; le code ne dépend pas d’une API VMware. Les campagnes historiques citent MySQL **8.4.11** et PHP CLI **8.5.4** ; ces versions ne sont pas un relevé actuel du serveur.

L’interface propose le français et l’anglais. Les nouvelles opérations sont exprimées en **MAD**. Les traces anciennes `UM` sont conservées en rémunération, sans conversion implicite ; la paie exige MAD. Source : `Money::REFERENCE_CURRENCY`, migration 006, procédures MAD et `payroll_build`.

## Périmètre fonctionnel constaté

| Domaine | Implémentation dans les sources | Installation / validation attestée |
|---|---|---|
| Authentification et sessions | Login Argon2id, limitation par IP, renouvellement et expiration | Rapports HTTP isolés ; six connexions principales dans le rapport du 06/11 |
| Identité RH | Création, liste, recherche, fiche et modification des noms | Recette RH historique ; aucun archivage par formulaire |
| Référentiels | Départements et postes bilingues consultables | Pages RH attestées ; administration des catalogues absente |
| Contrats et affectations | Création, consultation et clôture conservant l’historique | Procédures et tests isolés ; sources de Nadia attestées |
| Rémunération | Proposition RH, décision Finance indépendante, conditions versionnées | MAD et historique attestés ; ancien UM volontairement conservé |
| Paie | Mois/plafonds, ajustements approuvés, calcul, vérification, approbation, publication | Campagnes SQL/HTTP/concurrence ; bulletin de Nadia attesté |
| Règlements | Paiement fictif, correction, complément et restitution contrôlée | Module codé, option d’activation ; principal : paiement attesté ; corrections : isolé |
| IAM | Consultation, octroi et révocation de rôles | Module codé, option d’activation ; recette principale et campagnes isolées |
| Audit | Historiques métier SQL, historique IAM et journal technique local | Pas de console web générale des logs |
| Fiscalité, banque, PDF de bulletin | Absents des routes et calculs | Aucun résultat revendiqué |

## Échelle des preuves

**Implémenté** signifie qu’un chemin de code concret existe. **Installé historiquement** signifie qu’un rapport identifié décrit l’installation ; cela ne certifie pas l’état du 11 novembre. **Testé historiquement** renvoie à une campagne datée et au périmètre exercé. **Partiel** désigne une capacité disponible avec une couverture limitée, par exemple IAM sans création de comptes ni réinitialisation de mots de passe. **Prévu / perspective** désigne une évolution absente du code, sans promesse de livraison.

Le relevé structurel des sources compte **25 tables, 24 procédures distinctes, 42 triggers et 31 permissions** après prise en compte des remplacements de procédures. Une procédure réécrite dans une migration et un patch n’est comptée qu’une fois. Les 47 lignes de l’inventaire HTTP comprennent les méthodes GET/POST séparées et une ligne regroupant les deux assets ; ce nombre ne signifie pas 47 écrans.

## Lecture conseillée pour un jury

Commencer par l’architecture, suivre le scénario Nadia, présenter ensuite la frontière PDO/procédures, la matrice de rôles, les historiques immuables et les tests de concurrence. Le dictionnaire fournit la preuve détaillée des contraintes ; les chapitres de limites distinguent simulation académique et obligations d’un système professionnel.

Sources de synthèse : `public/index.php`, `app/Web/`, `database/migrations/001–011`, `database/seeds/`, `docs/DEMO-PRESENTATION.md`, `storage/logs/demo-verification.json`. Les mots de passe et empreintes d’authentification réelles sont exclus des livrables.
