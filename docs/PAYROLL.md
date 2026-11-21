# Paie et bulletins : développement et limites de validation

Les paiements fictifs, corrections et remboursements sont désormais développés
en extensions 009/010, avec IAM en 011, et validés dans le laboratoire.
Voir [FINALIZATION.md](FINALIZATION.md) pour leurs règles et leur activation
séparée, et [le rapport](FINALIZATION-VALIDATION-2026-11-06.md) pour les tests réels.
Les sections suivantes décrivent le socle 007/008 ; leurs limites historiques sur
les paiements/corrections ne décrivent pas les nouvelles extensions.

Les écrans FR/EN, le dépôt PHP et les nouvelles procédures MySQL sont développés.
Les nouvelles migrations 007/008 ne sont pas installées sur l'instance principale.
La présence des rémunérations et de `finance.demo` est confirmée par l'utilisateur ;
leur réinstallation est interdite. Voir [PAYROLL-ACTIVATION.md](PAYROLL-ACTIVATION.md).

## Règles implémentées

Ces règles conservatrices complètent les exigences documentées. Aucun barème chiffré
validé n'a été retrouvé : les plafonds sont donc explicites, obligatoires et sans
défaut. Leur approbation métier et les règles organisationnelles restent à confirmer.
Ce module académique ne calcule pas de cotisations fiscales ou sociales légales.

- Finance crée une période unique par mois et choisit des plafonds absolus MAD,
  cumulés par employé et par mois, avec justification. La période est immuable.
- RH soumet les primes, retenues et suspensions rémunérées/non rémunérées.
  Finance approuve ou rejette avec motif, distincte du créateur et du bénéficiaire.
  Toute décision est définitive. Les suspensions approuvées doivent être couvertes
  par un contrat, avec bornes inclusives, sans chevauchement. Une suspension sur
  plusieurs mois doit être divisée en demandes mensuelles.
- Seuls les éléments approuvés interviennent dans le calcul. Une demande en attente
  empêche la préparation/vérification/approbation jusqu'à sa décision. Une demande
  rejetée demeure dans l'historique sans effet financier.
- La base utilise chaque jour calendaire couvert par un contrat. Le salaire retenu
  est la dernière condition effective de ce contrat à cette date. Sa demande et sa
  décision d'approbation sont recroisées, avec contrôle des montants, devise, dates,
  bénéficiaire et indépendance de l'approbateur. Aucun salaire manquant n'est assimilé
  à zéro et aucun salaire non approuvé n'est utilisé.
- Un jour de suspension rémunérée conserve la rémunération. Un jour non rémunéré
  contribue zéro. Les jours hors contrat ne produisent pas de rémunération.
- Base = somme des salaires mensuels des jours payés / nombre réel de jours du mois.
  Un seul arrondi final au centime, à la moitié supérieure ; aucune arithmétique
  financière flottante. Brut = base + primes ; net = brut − retenues. Un net négatif
  ou un total supérieur à DECIMAL(12,2) est refusé. Primes/retenues approuvées ne sont
  pas proratisées une seconde fois.
- Les nouvelles paies utilisent exclusivement MAD. Les historiques UM sont préservés
  sans réétiquetage ni conversion ; un jour reposant sur UM bloque le calcul.
- Le gestionnaire de paie prépare une version immuable contenant montants, sources,
  instantané JSON, empreinte SHA256, algorithme et identité du préparateur.
- Chaque recalcul crée une nouvelle version. Les anciennes restent consultables.
  Les modifications de sources rendent obsolètes les versions non approuvées.
- Le gestionnaire vérifie les montants. Finance, distincte du préparateur et du
  bénéficiaire, approuve ou rejette avec motif. La procédure recalcule les sources
  à la vérification et à l'approbation et contrôle l'empreinte et les totaux.
- Une version approuvée bloque les nouvelles entrées et recalculs de cette personne
  pour ce mois. Une contrainte unique empêche deux approbations du même mois.
  Aucun remplacement/correction d'une paie approuvée n'est fourni ; un tel workflow
  devra être conçu et autorisé séparément.
- La publication est une action distincte du gestionnaire, après approbation.
  Elle rend le bulletin accessible à son seul employé. Les brouillons et versions
  rejetées ne sont jamais exposés au salarié, même par URL directe.

Les plafonds sont configurés au moment de la création de la période. Une période
créée avec un plafond erroné ne peut pas être modifiée par cette version ; faire
revoir le paramétrage avant sa création. Aucun paiement fictif n'a été développé,
car son inclusion au périmètre validé n'est pas confirmée.

## Sécurité et concurrence

Les six nouvelles tables et douze triggers interdisent UPDATE/DELETE. svc_php ne
reçoit que sept EXECUTE publics ; aucun SELECT/DML sur les nouveaux objets, ni
EXECUTE sur les helpers. Le propriétaire dédié reste verrouillé. Il ne reçoit ni
DDL, ni droit global, ni GRANT OPTION. UPDATE(id) employees sert au verrou InnoDB
parent comme dans les modules RH/rémunérations existants.

Toute écriture liée à une personne prend ce même verrou exclusif `employees`.
Les lectures de calcul utilisent READ COMMITTED après ce verrou ; les opérations
RH, rémunérations et paie ne doivent pas utiliser des chemins directs concurrents.
Les vérifications RBAC SQL relisent les attributions actives avec FOR SHARE.
Un conflit/deadlock est présenté sans retry automatique ; consulter l'état avant
nouvel essai, notamment après interruption réseau et COMMIT incertain.

Les rôles RH, Paie, Finance, administrateur et auditeur sont incompatibles entre eux
pour l'accès opérationnel à ce nouveau module, au niveau de la personne. Le rôle
Employee peut coexister. L'auditeur a une lecture globale sans action financière ;
l'administrateur ne reçoit aucun droit financier. La politique existante de
rémunérations demeure celle de 06A et doit faire l'objet de ses propres tests.

L'identité métier est exclusivement issue de la session PHP. Les procédures de
lecture vérifient également que le bulletin est publié et appartient à l'employé.
Les écritures exigent POST/CSRF ; les templates échappent les valeurs. Les événements
conservent identités, dates UTC et justifications ; les logs techniques ne reçoivent
que le type d'action et les identifiants, jamais les montants ou motifs.

Le service SQL reste un compte partagé par le serveur PHP : sa compromission peut
permettre de présenter un autre actor_id. Ce modèle ne prétend pas protéger contre
une compromission du serveur applicatif ni contre un administrateur SQL capable
de changer les routines/triggers. L'empreinte n'est pas une signature indépendante.

## Composants et tests

`app/Payroll/Calculator.php` calcule en centimes sur PHP 64 bits.
`Calendar.php` transforme un instantané de confiance en jours contractuels.
Ces composants sont un oracle indépendant pour vérifier le calcul SQL ; aucune
valeur déclarative envoyée par un navigateur ne constitue une preuve d'approbation.
La production des calculs persistants passe uniquement par `payroll_calculate`.

```bash
php tests/payroll-calculator.php
php tests/payroll-calendar.php
php tests/payroll-web-unit.php
python3 tests/web-boundaries.py
```

Exécutés : 17 assertions calcul, 23 calendrier et 210 autorisation/validation/rendu.
44 contrôles HTTP anonymes passent, avec un serveur local temporaire sans secrets
MySQL. Ils ne vérifient pas encore les écritures des nouvelles procédures.

`lab/mysql-validate.py` et `tests/payroll-mysql.php` préparent la validation réelle
sur une instance privée sans réseau, avec données fictives, contrôles de refus,
parcours RH/Finance, paie et publication, IDOR et parité PHP/SQL. L’autorisation explicite a été donnée et les tests ont été exécutés :
35 contrôles SQL, 58 HTTP authentifiés et 18 de concurrence/privilèges/intégrité
ont réussi. Voir [le rapport](LAB-VALIDATION-2026-11-04.md). Ces résultats
ne valent pas installation ou validation sur l’instance principale.

## Démonstration attendue après installation validée

1. Sur une personne fictive, établir un contrat débutant le 3 novembre 2026 et
   approuver indépendamment son salaire mensuel de 12000,00 MAD.
2. Finance crée novembre avec plafonds de démonstration explicites (par exemple
   500,00 MAD chacun, sans présenter cet exemple comme un barème validé).
3. Préparer une première version : 28/30 × 12000 = 11200,00 MAD.
4. RH soumet prime de 300,00, retenue de 100,00 et suspension non rémunérée des
   10 et 11 novembre ; Finance décide chaque élément. Une suspension rémunérée
   distincte des 12 et 13 ne réduit pas la rémunération.
5. Une ancienne version doit être refusée comme obsolète. Préparer la nouvelle :
   base 10400,00 ; brut 10700,00 ; net 10600,00 MAD.
6. Vérifier, puis approuver avec Finance distincte. Avant publication, le salarié
   ne doit voir aucune version. Publier séparément, puis vérifier la consultation
   du seul bénéficiaire et le refus du même identifiant par un autre employé.
7. Contrôler refus de double décision, dépassement cumulé des plafonds, suspension
   chevauchante, changement après approbation et écriture directe par svc_php.

Les listes paginent les entrées/bulletins par 50 ; les sélecteurs affichent les
120 périodes les plus récentes et jusqu'à 500 employés actifs. Ces limites sont
adaptées au jeu de démonstration, sans moteur de recherche supplémentaire.

Les choix de paramètres typés et de collations explicites suivent la
[syntaxe des procédures MySQL 8.4](https://dev.mysql.com/doc/refman/8.4/en/create-procedure.html).
Le compte de définition utilise le
[verrouillage de compte MySQL](https://dev.mysql.com/doc/refman/8.4/en/account-locking.html).
Ces références de conception ne remplacent pas l'exécution des migrations/tests.
