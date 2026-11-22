# Présentation SecurePayroll

Application locale : **http://127.0.0.1:8080**.
La base utilisée est `secure_payroll`. Le serveur existant a été conservé :
un seul serveur écoute sur le port 8080, avec Settlement et IAM activés.

## Comptes à utiliser

| Identifiant | Rôle | Identité et usage |
|---|---|---|
| `rh.demo` | Responsable RH | Identité RH existante ; employés, contrats, rémunérations |
| `finance.demo` | Responsable Finance | Identité Finance existante ; approbations et paiements fictifs |
| `payroll.demo` | Gestionnaire de paie | Identité distincte ; calcul, vérification et publication |
| `employee.demo` | Employé | **Nadia TRAORE**, matricule `EMP-2026-001` |
| `admin.demo` | Administrateur applicatif | Identité distincte ; console IAM |
| `audit.demo` | Auditeur | Identité distincte ; lecture des bulletins et de l’historique IAM |

Les six connexions ont été vérifiées sur la vraie application HTTP. Les quatre
comptes manquants ont été créés, sans réinitialiser RH ou Finance. Les six
empreintes sont Argon2id ; chaque employé possède au plus un compte. Les cinq
identités opérationnelles sont distinctes de Nadia et ne cumulent pas leurs rôles.

### Récupérer les quatre nouveaux mots de passe

Dans **votre propre terminal Ubuntu**, comme utilisateur habituel, sans sudo :

```bash
cd secure_payroll_project
python3 bin/demo-passwords.py
```

Affichage unique : conserver immédiatement les valeurs dans un gestionnaire
privé. Ne pas rediriger la sortie, la photographier ou la joindre au rapport.
Les valeurs sont gardées seulement en mémoire par un processus privé ; elles
ne figurent dans aucun fichier du projet. Le point de récupération expire six
heures après sa création ou sa dernière reprise de vérification. Après lecture,
une seconde récupération est refusée. Ne pas relancer une création de comptes
pour retrouver un mot de passe. Les secrets de RH et Finance restent ceux connus
par l’opérateur. Aucun mot de passe n’est fourni dans ce document.

## Scénario de présentation, environ huit minutes

Utiliser la déconnexion entre les rôles : les onglets d’un même profil Firefox
partagent la session. Ouvrir une fenêtre privée pour isoler une seconde session.
Ne pas ressaisir les contrats, salaires, périodes ou règlements déjà enregistrés.

1. **RH — données sources.** Se connecter à `/login`, puis ouvrir `/dashboard`,
   `/employees`, `/employees/2`, `/contracts` et `/compensation/history`.
   Montrer Nadia, le contrat `CDI-EMP-2026-001-01` démarrant le 03/11/2026 et le
   salaire approuvé de **12 000,00 MAD**, effet au 03/11/2026. Les départements,
   postes et affectations sont accessibles à RH via le menu. Ces sources existaient
   déjà et n’ont pas été recréées pendant la finalisation.
2. **Paie — calcul et traçabilité.** Se déconnecter, connecter `payroll.demo`,
   ouvrir `/payroll`, puis **`/payslips/1`**. Montrer novembre 2026, le calendrier
   du 3 au 30 novembre, **28 jours couverts sur 30** et le calcul
   `12000 × 28 / 30 = 11200,00 MAD`. Prime et retenue : **0,00 MAD** ; brut et
   net : **11 200,00 MAD**. Le bulletin est déjà publié : montrer son historique
   plutôt que refaire les transitions. Les plafonds du mois sont **3 300,00 MAD**
   et **560,00 MAD** ; ce sont des plafonds, pas des montants déduits du salaire.
3. **Finance — approbation indépendante.** Se connecter avec `finance.demo`,
   ouvrir `/payslips/1`. L’historique montre vérification Paie, approbation Finance
   et publication Paie, avec les auteurs et dates. L’approbateur est différent du
   préparateur et de la bénéficiaire.
4. **Finance — simulation de paiement.** Ouvrir
   **`/payslips/1/settlement`**. Le règlement fictif de **11 200,00 MAD** est déjà
   enregistré sous la référence `DEMO-NADIA-202611-1`. Le solde est **0,00 MAD**.
   Le bouton de règlement disparaît lorsque rien n’est dû. Ne pas créer un second
   paiement. Aucun virement ni service bancaire n’est utilisé.
5. **Nadia — accès personnel.** Se connecter avec `employee.demo`, ouvrir
   `/payroll`, `/payslips/1` puis `/payslips/1/settlement`. Montrer le bulletin
   publié et le solde, sans boutons de calcul, d’approbation ou de règlement.
   Le profil `/employees/2` est celui de Nadia. Basculer **FR / EN** et constater
   la traduction de l’interface et le format monétaire, sans changer la devise.
6. **Administration IAM.** Se connecter avec `admin.demo` et ouvrir `/iam`.
   Montrer les comptes, les rôles et l’historique. Les formulaires d’octroi et de
   révocation sont réservés à l’administrateur. Pour la présentation, ne changer
   aucune attribution : les comptes de démonstration sont prêts.
7. **Audit.** Se connecter avec `audit.demo`, ouvrir `/iam`, `/payroll`,
   `/payslips/1` et `/payslips/1/settlement`. Montrer les historiques en lecture,
   sans commandes financières ni octroi/révocation. Terminer sur le bulletin et
   son règlement fictif.

## Ce qui a été vérifié sur la principale

Le contrôle enregistré à `2026-11-06T19:39:59Z` a validé **64 vérifications HTTP
et base de données**, dont les six connexions réelles, les tableaux de bord et
profils, les écrans RH, Paie et IAM autorisés en FR/EN, le calcul de Nadia, les
transitions et le règlement fictif. Aucune erreur PHP visible n’a été détectée
sur les pages exercées. Les empreintes des quatre tables de rémunération sont
restées identiques avant/après : 1 demande, 1 décision, 2 événements et 1 condition
salariale. Le calcul n’a pas réécrit ces données.

Le contrôle administratif final a confirmé les structures de Paie, les deux
modules Settlement/IAM, leurs propriétaires MySQL verrouillés, leurs DEFINER,
les droits dédiés et les frontières du compte `svc_php`. `inspect` réussit.
Aucun privilège MySQL n’a été élargi, aucune migration rejouée, aucune donnée
supprimée et aucune commande Git exécutée.

Le rapport détaillé sans secrets est conservé dans
`storage/logs/demo-verification.json`. Le journal technique est
`storage/logs/application.log` : événements `auth.login`, `payroll.calculated`,
`payslip.verified`, `payslip.approved`, `payslip.published`, `settlement.pay`, avec
identifiants et dates. Les historiques métier sont dans les pages correspondantes.
Le journal technique ne contient pas les mots de passe ni les corps des requêtes.

## Mécanismes de sécurité à expliquer

- **Authentification :** Argon2id, compte et identité actifs requis ; protection
  contre les tentatives répétées. Les rôles sont relus à chaque requête.
- **Session :** identifiant renouvelé après connexion, cookies HttpOnly/SameSite,
  expiration d’inactivité et durée maximale. HTTPS est requis pour un déploiement
  distant ; cette démonstration utilise seulement la boucle locale HTTP.
- **RBAC et séparation des tâches :** RH propose la rémunération, Finance décide ;
  Paie prépare/vérifie/publie le bulletin et Finance l’approuve et règle fictivement.
  L’administrateur IAM ne reçoit pas les droits financiers.
- **CSRF et accès aux objets :** écritures en POST avec jeton de session ; les
  procédures limitent l’employé à ses propres bulletins publiés. Les tests négatifs
  et offensifs restent réservés au laboratoire isolé.
- **MySQL :** service non root, procédures préparées avec paramètres, propriétaires
  DEFINER verrouillés et droits dédiés. Aucun accès direct du service en écriture
  aux historiques financiers.
- **Intégrité :** DECIMAL, contraintes et triggers d’immutabilité, versions et
  événements conservés. Les approbations ne sont pas simulées par des UPDATE.
- **Devise :** nouvelles opérations MAD ; aucun réétiquetage ni conversion des
  historiques UM. Les anciennes rémunérations UM ne deviennent pas MAD en silence.

## Sauvegarde et reprise

La sauvegarde cohérente préalable aux comptes est conservée dans
`/var/tmp/securepayroll-preinstall-ucly7zri/database.sql`, avec son manifeste
SHA256 vérifié. Elle précède les nouveaux comptes et le bulletin : ne jamais
l’importer sur la principale pour refaire une démonstration. Toute restauration
principale demanderait une décision distincte pour préserver les écritures suivantes.
Les copies de laboratoire et les rapports sont conservés.

La restauration de cette sauvegarde a ensuite réussi sur une nouvelle instance
privée sans réseau. **24 contrôles isolés** ont validé les vrais champs cachés
`target=0` des formulaires, le paiement, la préparation/vérification/approbation/
publication d’une correction, sa lecture employé FR/EN, le refus CSRF et le refus
d’un état périmé. Aucune correction ni tentative offensive n’a été faite sur la
principale. Résultat conservé dans
`/var/tmp/securepayroll-mysql-j6fw7e47/demo-settlement-result.json`.
Le manifeste initial conserve honnêtement son état antérieur au test ; le résultat
de restauration et son empreinte sont joints au rapport de vérification final.

Le serveur HTTP existant reste en fonctionnement. Ne pas lancer un deuxième
serveur si l’adresse répond déjà. Si le serveur a été arrêté, le relancer dans
un terminal normal avec saisie privée du secret MySQL :

```bash
cd secure_payroll_project
SETTLEMENT_ENABLED=1 IAM_ENABLED=1 python3 bin/local-demo.py serve
```

Ne lancer ni `install`, ni `activate-*`, ni une ancienne migration. Pour un contrôle
administratif en lecture seule : `sudo python3 bin/payroll-admin.py inspect`.

## Limites à annoncer

Simulation académique locale, sans calcul réglementaire de cotisations/impôts et
sans paiement bancaire réel. Le bulletin est une page HTML ; aucun export PDF
spécifique n’a été ajouté. Les départements et postes sont des catalogues existants
consultables, pas une nouvelle console d’administration de ces catalogues.
L’audit web est présenté via les historiques métier et IAM ; le journal technique
complet reste un fichier local. Les contrôles courants ont été réalisés par HTTP
et MySQL ; ils ne constituent pas un nouvel audit de pénétration sur la principale.
Une correction financière de Nadia n’a pas été fabriquée dans la principale :
son montant de référence doit rester à 11 200,00 MAD.

Après la présentation, remplacer les mots de passe temporaires selon une opération
administrative distincte ; ne pas publier les identifiants secrets ou les sauvegardes.
