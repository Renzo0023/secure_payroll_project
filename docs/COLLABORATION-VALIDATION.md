# Validation réelle de l’installation collaborative — 15 novembre 2026

**58 contrôles MySQL/HTTP réussis**, puis **389 contrôles hors connexion réussis**. Ces deux catégories restent distinctes. Aucun accès ni aucune modification de la base MySQL principale n’a été effectué.

## Environnement et méthode

La recette `tests/local-install.py` utilise une instance MySQL privée neuve, réseau désactivé, MySQL X désactivé et port zéro. Les clients utilisent exclusivement son socket explicite, avec `--no-defaults --no-login-paths`. Le datadir et la version sont vérifiés avant les écritures. Le serveur PHP de recette n’écoute que sur 127.0.0.1, sur un port temporaire. La recette ne charge pas les identifiants de la VM.

Versions effectivement utilisées : MySQL **8.4.13-0ubuntu0.26.04.2**, PHP **8.5.4**. Le résultat synthétique sans secrets est conservé dans [COLLABORATION-VALIDATION.json](COLLABORATION-VALIDATION.json).

## Contrôles réellement exercés

- Installation complète depuis les migrations et configurations SQL existantes : **25 tables, 24 procédures, 42 triggers, 31 permissions**.
- Six comptes web fictifs et six empreintes différentes ; sept mots de passe service/web neufs et distincts ; fichiers privés en 0600 ; cinq propriétaires DEFINER verrouillés.
- Refus de relancer l’initialisation dans un répertoire déjà présent, sans migration ni duplication de comptes.
- Six connexions HTTP Argon2id et six tableaux de bord ; pages employés, départements, postes, contrats, affectations et rémunérations pour RH.
- IAM lisible par Admin et Audit, refusé à Employee.
- Salaire fictif approuvé de 12 000 MAD ; calcul réel via HTTP : **28/30 jours, base et net de 11 200,00 MAD**.
- Bulletin caché à l’employée avant publication ; vérification Paie, approbation Finance indépendante, publication Paie ; accès personnel FR/EN après publication.
- Paiement fictif du solde calculé côté SQL, refus CSRF et refus du second paiement ; exactement une écriture de 11 200 MAD.
- Arrêt et redémarrage de MySQL avec conservation des données.

Les deux arrêts MySQL du passage réussi sont terminés et son socket est absent. Les données et journaux de test restent privés sous `/tmp/securepayroll-install-g4szlwpu`, sans copie dans Git. Aucune suppression ni import sur la base actuelle.

## Tests hors connexion

| Test | Contrôles réussis |
|---|---:|
| tests/sql-static.php | 93 |
| tests/compensation-unit.php | 45 |
| tests/payroll-calculator.php | 17 |
| tests/payroll-calendar.php | 23 |
| tests/payroll-web-unit.php | 211 |
| Total hors connexion | 389 |

Ces résultats ne doivent pas être présentés comme 389 contrôles serveur supplémentaires. Les 93 fichiers métier d’origine `app/`, `public/`, `lang/`, `config/` et `database/` présents dans le relevé d’empreintes du 11 novembre sont inchangés ; seuls de nouveaux outils d’installation, un seed fictif, des tests et documents ont été ajoutés.

## Incidents et correction

Un premier initialiseur s’est bloqué dans le confinement d’exécution ; il n’a jamais ciblé la principale. Son arrêt ciblé par SIGTERM, après vérification du PID, du propriétaire et du datadir, a été refusé par le système avec PermissionError. Ses fichiers sont conservés ; aucune suppression ni intervention sur MySQL principal n’a été effectuée. Son traitement exige les droits de l’environnement hôte, distincts de ceux nécessaires à l’installation sur un poste Linux ordinaire. L’essai hors confinement a installé le schéma, puis révélé un redémarrage trop rapide après SHUTDOWN dans le nouveau lanceur. L’attente de disparition du PID/socket et de fin du processus créé a été corrigée. La recette complète a ensuite été reprise dans une instance neuve et ses 58 contrôles ont réussi.

## Limites

Le test valide Linux et les versions indiquées, pas toutes les distributions ni les autres systèmes. Le mode interactif de choix des mots de passe partage la validation et l’installation du mode généré, mais sa saisie manuelle n’a pas fait l’objet d’une seconde campagne automatisée. La recette ne constitue pas un audit de pénétration exhaustif. Les données de paie et paiements sont fictifs ; le calcul fiscal/social réglementaire et les virements bancaires ne sont pas implémentés.

## Reproduction depuis un clone propre du commit

Un clone local indépendant du commit **587ab2d77e0f6675b9e091ce2014c959a52002e6**, obtenu par `git clone --no-local --no-hardlinks`, ne contenait ni `.local/`, ni sauvegarde de réparation, ni identifiants de la VM. La même recette y a installé une nouvelle instance, puis ses **58 contrôles ont de nouveau réussi** : schéma, six connexions, calcul, publication, paiement et persistance. Son serveur est arrêté et son socket absent.

Cette répétition vérifie l’absence de dépendance à un fichier ignoré de la copie de travail ; elle ne représente pas 58 scénarios métier nouveaux à additionner à la première campagne. Le deuxième passage conserve ses artefacts privés sous `/tmp/securepayroll-install-_hihu_8v`. Les seules modifications après le commit testé concernent les rapports, le README et le test de l’auditeur ; les sources du lanceur, le seed, le test MySQL et le code métier sont identiques au clone validé.

La barrière de publication `tests/secret-audit.py` a par ailleurs réussi **8 contrôles** avec un dépôt Git temporaire et des secrets synthétiques, sans utilisation d’un jeton opérateur ni accès au réseau.
