# Validation de la finalisation — 6 novembre 2026

## Résultat et frontière

**349 contrôles réels réussis** dans les seules instances privées de cette
finalisation, plus **426 contrôles hors connexion**. Les 216 contrôles réels et
413 contrôles hors connexion de la campagne précédente restent documentés dans
`LAB-VALIDATION-2026-11-06.md` ; ils ne sont pas additionnés à ce nouveau total.

Aucune connexion, sauvegarde, migration, attaque ou modification de données de
l’instance principale n’a été effectuée. Aucun identifiant MySQL principal n’est
présent dans l’environnement de l’agent. L’inspection administrative a été demandée
à l’opérateur, avec sa propre authentification sudo. Aucun Git, publication GitHub,
sudo ou effacement de données/journaux n’a été exécuté pendant cette finalisation.

## Contrôles effectivement exécutés

| Test | Réussites | Portée |
|---|---:|---|
| `tests/payroll-mysql.php` | 35 | Régression RH → Finance → Paie → Bulletins |
| `tests/payroll-http-live.py` | 58 | Régression HTTP authentifiée, six rôles, FR/EN, CSRF et IDOR |
| `tests/payroll-races.py` | 18 | Régression concurrence et privilèges |
| `tests/settlement-mysql.php` | 62 | Paiement initial, doublons, référence dupliquée, corrections, complément, trop-perçu, remboursement, rôles, brouillons et immutabilité du service |
| `tests/settlement-http.py` | 47 | Parcours réel de correction/publication/paiement, montants navigateur ignorés, CSRF, IDOR, échappement et FR/EN |
| `tests/settlement-races.py` | 18 | Deux paiements et deux reçus réellement observés en LOCK WAIT, une seule réussite ; triggers exercés avec compte privilégié |
| `tests/iam-mysql.php` | 34 | Octroi, révocation, historique, compte désactivé, employé archivé, auto-attribution, rôle incompatible planifié et droits directs refusés |
| `tests/iam-http.py` | 33 | Admin/Audit, CSRF, échappement, FR/EN, révocation effective dans une session ouverte |
| `tests/iam-races.py` | 9 | Octrois incompatibles et révocations simultanés, deux sessions observées en attente, une seule réussite |
| `lab/mysql-final-recovery.py` | 35 | Snapshot du lanceur administratif, SHA256, import complet, comptes de lignes de toutes les tables, totaux paiement/remboursement, GRANT réappliqués et exacts, lectures non-root et triggers restaurés |

Hors connexion : 93 SQL statiques, 45 rémunération, 17 calcul, 23 calendrier,
211 autorisation/validation/rendu paie, 18 limiteur, 7 configuration socket/runtime
et 12 frontières de GRANT du propriétaire Paie. Syntaxe contrôlée sur 73 fichiers
PHP et 24 scripts Python ; égalité des clés FR/EN et présence des clés littérales
des nouveaux écrans vérifiées.

## Objets et comportements livrés

Migrations nouvelles uniquement : `009_settlement.sql`,
`010_settlement_operations.sql`, `011_iam_operations.sql`, propriétaires verrouillés
et GRANT/permissions associés. Les migrations historiques sont inchangées et n’ont
été chargées que dans le datadir neuf de cette campagne.

Les nouveaux règlements et corrections n’altèrent aucune ancienne ligne financière.
La correction est une version exceptionnelle motivée de montants complets, dont
brut/net sont dérivés et plafonds conservés. Elle exige vérification, décision
Finance indépendante et publication avant tout effet sur le solde. Le calendrier
initial reste une preuve historique et n’est pas recalculé par cette opération.

Le paiement est fictif, intégral sur le solde positif SQL et lié à une version
publiée attendue. Les deux protections de doublon ont été exercées : unicité de
référence et sérialisation/relecture du solde, même avec des références différentes.
Le trop-perçu n’entraîne aucune retenue automatique. Il exige demande Paie,
décision Finance puis reçu Paie séparé, avec un seul remboursement possible.

L’IAM utilise les tables/triggers existants et conserve motifs, dates et auteurs.
Admin peut attribuer/révoquer pour les autres personnes ; Audit ne peut que lire.
Employee peut coexister avec un rôle opérationnel unique. Les procédures et les
contrôles PHP relisent l’identité et les rôles ; aucun rôle transmis par le
navigateur ne détermine l’identité métier. Aucun hash n’est retourné par l’IAM.

Les contrôles SQLi portent sur les entrées exercées, les requêtes paramétrées et
les rôles/références malformés ; ce n’est pas un audit exhaustif. L’IDOR est exercée
entre deux vrais employés fictifs, avant et après publication. Les actions
financières des autres rôles sont refusées par PHP et les procédures MySQL.

## Artefacts et incidents

Instance source neuve : `/tmp/securepayroll-mysql-w8zhfdyj`.
Instance de restauration finale : `/var/tmp/securepayroll-mysql-ga9l9i9k`.
Les deux serveurs sont arrêtés ; leurs sockets sont absents à la vérification finale.
La preuve de restauration est conservée dans
`/tmp/securepayroll-mysql-w8zhfdyj/final-recovery-c723080a.json`.
Snapshot restauré : `/tmp/securepayroll-preinstall-cxd_po4i`, avec dump et manifeste
SHA256. Aucune sauvegarde principale n’a été faite. Les prochaines sauvegardes du
lanceur administratif utilisent `/var/tmp`, sur disque, en fichiers privés.

Les tests Paie puis Settlement ont été lancés avec :

```bash
python3 lab/mysql-validate.py --initialize-isolated --with-settlement
```

Les nouveaux objets IAM ont été appliqués une seule fois dans cette source, avec
`lab/mysql-iam.py`. La première vérification a refusé un ordre de colonnes GRANT
différent dans SHOW GRANTS. Le comparateur a été corrigé pour comparer les mêmes
ensembles de colonnes ; les privilèges autorisés n’ont pas été élargis. Les tests
ont repris avec `--resume-tests`, sans rejouer le DDL ni les seeds. Cette option
n’est destinée qu’à des fixtures encore non consommées ; les scénarios financiers
ou IAM déjà exécutés ne doivent pas être rejoués aveuglément.

Une première restauration n’a pas pu initialiser son datadir
`/tmp/securepayroll-mysql-89jselvh` : l’espace du tmpfs /tmp était insuffisant.
Les logs d’erreur et le snapshot `/tmp/securepayroll-preinstall-81633qil` ont été
conservés sans suppression. Une nouvelle destination sous /var/tmp a ensuite
permis les 35 contrôles de restauration réussis. `PrivateInstance` accepte ces
deux racines temporaires explicites, avec les mêmes contrôles de nom, propriétaire,
permissions 0700, datadir et absence de réseau.

Les deux initialiseurs historiques ont été identifiés à nouveau sur l’hôte :
PID 7426 → `/tmp/securepayroll-mysql-l_f51ybd/data`, PID 8023 →
`/tmp/securepayroll-mysql-yhg_kc5p/data`. Aucun signal ni suppression n’a été tenté
durant cette finalisation. Leur traitement par l’environnement hôte reste à faire,
sans action sur le serveur principal. Vérifier les PID et arguments avant toute
intervention ultérieure.

## Principale : étapes restantes

Le détail des commandes et des conditions est dans `FINALIZATION.md`.

1. Inspection administrative réelle de l’installation existante et des droits.
2. Maintenance, snapshot cohérent et activation des seuls modules réellement absents.
3. Vérification des propriétaires/droits, activation des options web et recette
   fonctionnelle avec comptes fictifs distincts.
4. Copie durable des sauvegardes et traitement des deux initialiseurs historiques.

Les lanceurs refuseront tout objet déjà présent ou partiellement installé. Les
nouvelles fonctions sont désactivées par défaut (`SETTLEMENT_ENABLED=0`,
`IAM_ENABLED=0`). La validation en laboratoire n’autorise pas à affirmer que ces
fonctions sont déjà utilisables sur la base principale.
