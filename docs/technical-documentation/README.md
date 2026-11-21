# Documentation technique et fonctionnelle de SecurePayroll

Dossier établi le **11 novembre 2026** à partir des sources PHP, vues, assets, migrations, seeds, procédures, triggers, scripts et rapports accessibles. Il respecte une mission documentaire : les nouveaux fichiers sont tous contenus dans ce dossier.

## Livrables principaux

- [Rapport consolidé Markdown](RAPPORT_COMPLET_SECUREPAYROLL.md)
- [Rapport complet PDF](RAPPORT_COMPLET_SECUREPAYROLL.pdf) — A4, couverture, sommaire paginé, tableaux et diagrammes
- [Preuves et périmètre de vérification](PREUVES-ET-PERIMETRE.md)

## Chapitres

- [01 — Présentation générale de SecurePayroll](01-PRESENTATION-GENERALE.md)
- [02 — Architecture et organisation](02-ARCHITECTURE.md)
- [03 — Frontend et pages](03-FRONTEND-ET-PAGES.md)
- [04 — Backend PHP](04-BACKEND-PHP.md)
- [05 — Conception et inventaire MySQL](05-BASE-DE-DONNEES.md)
- [06 — Procédures stockées et triggers](06-PROCEDURES-ET-TRIGGERS.md)
- [07 — Sécurité, RBAC et IAM](07-SECURITE-RBAC-IAM.md)
- [08 — Règles métier et traitement de la paie](08-REGLES-METIER-ET-PAIE.md)
- [09 — Scénario fonctionnel Nadia TRAORE](09-SCENARIO-DEMONSTRATION.md)
- [10 — Tests et validation](10-TESTS-ET-VALIDATION.md)
- [11 — Installation, exploitation et maintenance](11-DEPLOIEMENT-ET-MAINTENANCE.md)
- [12 — Limites, contradictions et perspectives](12-LIMITES-ET-PERSPECTIVES.md)
- [13 — Dictionnaire complet des données](13-DICTIONNAIRE-DE-DONNEES.md)
- [14 — Inventaire des routes HTTP](14-INVENTAIRE-DES-ROUTES.md)
- [15 — Inventaire des rôles et permissions](15-INVENTAIRE-DES-PERMISSIONS.md)

## Diagrammes et tableaux

- [Architecture Mermaid](ARCHITECTURE.mmd)
- [Entité-association Mermaid : toutes les colonnes et FK déclarées](ENTITE-ASSOCIATION.mmd)
- [Relations MySQL Mermaid](RELATIONS-MYSQL.mmd)
- [Séquence du traitement d’une paie Mermaid](SEQUENCE-PAIE.mmd)
- [Tableau des pages](TABLEAU-DES-PAGES.md)
- [Tableau des tables](TABLEAU-DES-TABLES.md)
- [Tableau des rôles et permissions](TABLEAU-ROLES-ET-PERMISSIONS.md)
- [Empreintes SHA-256 des sources](SOURCES-SHA256.md)
- [Inventaire structurel lisible par programme](INVENTAIRE-STRUCTUREL.json)
- [Inspection MySQL préparée en lecture seule, non exécutée](INSPECTION-MYSQL-LECTURE-SEULE.sql)

## Statut des constats

Les sources déclarent **25 tables, 24 procédures distinctes, 42 triggers, 31 permissions et six rôles**. Les remplacements successifs de routines ne sont pas comptés comme de nouvelles procédures. Les tables et index implicites réellement installés doivent être confirmés par inspection MySQL.

Le fichier historique `storage/logs/demo-verification.json` atteste **64 contrôles** sur la principale le 6 novembre 2026 : six rôles, bulletin de Nadia à **11 200,00 MAD**, publication et paiement fictif, solde zéro. Les campagnes de laboratoire sont décrites séparément. Aucun résultat historique n’est présenté comme un test relancé dans cette mission.

L’état MySQL actuel est **Non vérifié** : aucune variable de connexion disponible dans cette session, aucune demande de droits supplémentaires. Les contradictions entre anciens documents et code actuel sont recensées au chapitre 12.

Le PDF documentaire ne constitue pas une fonction d’export de bulletin ajoutée à l’application. Aucun code PHP/SQL existant n’a été modifié ; aucune donnée métier ni aucun privilège n’a été écrit. Les instructions d’exploitation sont préparées pour l’opérateur et ne sont pas exécutées ici.

## Fabrication et contrôle des livrables

- [Méthode reproductible de génération PDF](METHODE-GENERATION-PDF.md)
- [Pagination des chapitres PDF](PAGINATION-PDF.json)
- [Contrôle documentaire final](CONTROLE-DOCUMENTAIRE.md)
- [Architecture vectorielle](DIAGRAMME-ARCHITECTURE.svg) et [séquence vectorielle](DIAGRAMME-SEQUENCE-PAIE.svg)
- Planches EA vectorielles : [identité/RBAC](DIAGRAMME-EA-01.svg), [organisation RH](DIAGRAMME-EA-02.svg), [rémunération](DIAGRAMME-EA-03.svg), [paie](DIAGRAMME-EA-04.svg), [règlements](DIAGRAMME-EA-05.svg)

Le PDF conserve les quinze chapitres complets et les définitions SQL. Les blocs Mermaid y sont remplacés par des planches graphiques et une liste complète des FK ; leur code source reste disponible en Markdown et dans les fichiers .mmd. Les fichiers d’aperçu illustrent le contrôle visuel, sans constituer des captures de l’application.
