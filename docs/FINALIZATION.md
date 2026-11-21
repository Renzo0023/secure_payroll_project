# Finalisation — référence historique d’activation

**État actuel :** les modules sont installés et vérifiés sur la principale. Les six
comptes fonctionnent, le bulletin de Nadia n°1 est publié et réglé fictivement.
Voir [DEMO-PRESENTATION.md](DEMO-PRESENTATION.md). Ne pas exécuter les commandes
d’installation ci-dessous : elles décrivent la préparation antérieure et restent
conservées uniquement comme référence. Aucune migration n’a été rejouée pendant
la finalisation de la démonstration.

## État à ne pas confondre

Les nouveaux paiements fictifs, corrections, remboursements et contrôles IAM sont
implémentés et testés dans le laboratoire privé. **Aucun objet n’a été installé
sur l’instance principale durant cette mission.** Aucun accès MySQL privé n’est
présent dans l’environnement de l’agent ; l’inspection administrative nécessite
l’authentification sudo de l’opérateur. Aucun secret n’est à communiquer à l’agent.

Les rapports du 4 et du 6 novembre restent conservés. La campagne de finalisation
est décrite dans `FINALIZATION-VALIDATION-2026-11-06.md`.

## Première intervention requise : inspection en lecture seule

Depuis un terminal administrateur authentifié, à la racine du projet :

```bash
sudo python3 bin/payroll-admin.py inspect
```

Transmettre uniquement les résultats et éventuels codes d’erreur, jamais de secret.
L’inventaire présente les tables/routines existantes avant le contrôle des
prérequis, de MAD et des droits. Aucun DDL n’est exécuté. Il n’existe pas de journal
historique de migrations faisant autorité dans le socle : l’inspection porte sur
les objets effectivement présents. Une présence partielle impose un diagnostic DBA,
jamais une réexécution des anciennes migrations ni un nettoyage automatique.

## Activation Paie et Bulletins

Si les six tables et les dix routines 007/008 sont déjà présentes, `inspect` vérifie
les propriétaires et droits : ne pas réinstaller. Si aucun nouvel objet/propriétaire
n’est présent et que tous les prérequis passent, mettre le service en maintenance
(arrêt des écritures et de tout DDL), puis :

```bash
sudo python3 bin/payroll-admin.py install --apply
```

Le lanceur présente les nouveaux fichiers et leurs SHA256. Il demande le nom de
base dans le terminal administratif. **Avant le premier DDL**, il vérifie InnoDB,
produit lui-même un dump `--single-transaction --routines --triggers --events`,
contrôle le code de retour, conserve les fichiers privés et écrit un manifeste
SHA256. Les sauvegardes administratives sont désormais placées sur disque dans
`/var/tmp/securepayroll-preinstall-*`, répertoires 0700 et fichiers 0600.

Il relit ensuite les prérequis, les collisions et les fichiers. Tout objet homonyme,
échec de dump, changement de fichier ou installation partielle bloque la suite.
Aucune migration 001–006 n’est rejouée. Les DDL ne sont pas transactionnels à
l’échelle du fichier ; après échec, conserver les artefacts et demander une reprise
ciblée au DBA. Le lanceur ne supprime ni ne remplace aucun objet existant.

Le snapshot n’exporte pas les comptes SQL et leurs secrets : conserver les scripts
reviewés de propriétaires/GRANT et l’inventaire administratif privé pour une reprise.
Copier les sauvegardes sur un stockage privé durable distinct avant de considérer
la stratégie de sauvegarde complète. Aucun dump principal n’a encore été produit
par cette session.

## Activation séparée des nouveaux modules

Uniquement après validation de Paie/Bulletins et inspection de chaque module :

```bash
sudo python3 bin/finalize-admin.py inspect --module settlement
sudo python3 bin/finalize-admin.py inspect --module iam
```

Si un objet existe, ne pas lancer l’installation. Pour une installation complète
existante, utiliser `verify` ; pour un état partiel, diagnostic DBA. Si tous les
objets du module sont absents et le plan approuvé, pendant la maintenance :

```bash
sudo python3 bin/finalize-admin.py install --module settlement --apply
sudo python3 bin/finalize-admin.py install --module iam --apply
```

Chaque commande crée son propre snapshot avant ses DDL, puis vérifie objets,
définisseurs, compte propriétaire verrouillé, privilèges exacts du propriétaire
et droits EXECUTE du service. La comparaison des colonnes GRANT est indépendante
de leur ordre d’affichage, sans élargir les privilèges acceptés.

Fichiers nouveaux uniquement :

- Settlement : propriétaire `settlement_owner`, migrations 009/010, GRANT dédiés,
  seed 007. Cinq tables immuables, dix triggers, deux procédures publiques.
- IAM : propriétaire `iam_owner`, migration 011, GRANT dédiés, seed 008.
  Trois procédures publiques ; conservation des tables et triggers RBAC existants.

Les comptes propriétaires sont verrouillés ; svc_php n’obtient aucun DML direct
sur les nouveaux historiques ni sur les attributions de rôle. Les anciens droits
des propriétaires RH/rémunérations/paie restent inchangés.

## Mise en service web et recette principale

Les deux fonctions sont désactivées par défaut. Après vérification SQL, exporter
ces variables dans l’environnement du serveur PHP, puis le relancer :

```bash
export SETTLEMENT_ENABLED=1
export IAM_ENABLED=1
python3 bin/local-demo.py serve
```

Les fichiers `.env` ne sont pas chargés automatiquement. Les secrets restent saisis
par le mécanisme privé existant du lanceur, jamais ajoutés aux sources.

Créer uniquement les comptes fictifs absents, avec saisie privée, selon
`PAYROLL-ACTIVATION.md`. L’IAM affecte les rôles aux comptes existants ; il ne crée
pas de compte ou de mot de passe. Un premier administrateur et un auditeur doivent
être provisionnés par le DBA. Aucune identité existante n’est réaffectée.

Recette opérateur sur personnes fictives distinctes :

1. RH crée un contrat et soumet la rémunération MAD ; Finance l’approuve.
2. Paie prépare et vérifie ; Finance approuve ; Paie publie ; seul le bénéficiaire
   consulte le bulletin dans sa session.
3. Depuis le bulletin publié, ouvrir « Paiements fictifs et corrections » ; Finance
   enregistre le paiement. Vérifier le solde nul et l’unique ligne de journal.
4. Paie prépare une correction motivée ; Paie vérifie, Finance décide et Paie
   publie. Les anciennes versions restent accessibles sans modification.
5. Si le net augmente, Finance paie seulement le complément. Si le net diminue
   après paiement, Paie demande le remboursement, Finance approuve et Paie
   enregistre séparément le reçu fictif ; aucune retenue automatique.
6. Vérifier les écrans FR/EN, le solde et les historiques via les comptes autorisés.
   La console `/iam` est disponible uniquement pour Admin/Audit, avec écriture Admin.

Cette recette est fonctionnelle ; **aucune campagne d’attaque principale n’est
prévue**. Les tests de SQLi, IDOR, privilèges et courses restent dans le laboratoire.

## Choix métier des corrections

Une correction est une proposition exceptionnelle de montants complets de
remplacement, avec justification obligatoire. Elle ne réécrit pas le calendrier,
les rémunérations approuvées, les entrées ni le bulletin initial. Elle forme une
nouvelle branche d’historique liée à la dernière correction publiée ; une seule
proposition non terminale est permise. Le net doit être positif ou nul, le brut et
le net sont dérivés, les plafonds mensuels de primes/retenues restent applicables.
La décision Finance indépendante autorise cette nouvelle version avant publication.
Elle ne constitue pas un recalcul automatique du calendrier salarial initial.

Le journal des paiements ne reçoit aucun montant navigateur. SQL calcule le solde
depuis le dernier net publié et le cumul paiements moins remboursements. Une
référence unique empêche sa réutilisation ; le verrou employé et la relecture du
solde empêchent aussi deux paiements avec des références différentes. La version
attendue évite de régler une correction que l’opérateur n’a pas consultée.

Un trop-perçu bloque le paiement ; un remboursement porte sur le trop-perçu entier,
sans échéancier ni retenue sur une autre période. Toute demande active bloque une
nouvelle correction. Il faut une décision Finance distincte du demandeur, du
préparateur et du bénéficiaire, puis un reçu distinct. Aucun virement réel ni règle
fiscale/sociale légale n’est implémenté.

## Contrôles IAM

Admin attribue/révoque uniquement pour d’autres personnes actives. Les rôles
RH/Finance/Paie/Admin/Audit sont mutuellement exclusifs ; Employee peut coexister.
Un rôle incompatible planifié est également refusé face à un octroi immédiat sans
expiration. Les comptes désactivés et employés archivés sont refusés. Les octrois
concurrents sont sérialisés par personne. Une révocation ne supprime pas l’attribution,
conserve auteur/motif/date et prend effet lors de la prochaine requête authentifiée.
L’auditeur lit sans droit d’octroi/révocation et aucun écran IAM ne retourne de hash.
Les accès directs d’un DBA et la compromission du service SQL restent hors de ce
modèle de contrôle applicatif.

## Nettoyage identifié, sans suppression

Les PID 7426 et 8023 ont été relus sur l’hôte pendant cette mission : ce sont
respectivement les initialiseurs des datadirs privés
`/tmp/securepayroll-mysql-l_f51ybd/data` et
`/tmp/securepayroll-mysql-yhg_kc5p/data`, avec `--initialize-insecure`.
Aucun signal ni suppression n’a été effectué pendant cette finalisation. Une
intervention de l’environnement hôte reste nécessaire ; vérifier à nouveau les
arguments et l’identité avant toute action, car les PID peuvent être réutilisés.
Ne pas toucher au service principal, ne pas retirer les datadirs pendant l’attente.
