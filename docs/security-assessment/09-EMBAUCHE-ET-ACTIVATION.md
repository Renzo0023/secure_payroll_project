# 09 — Embauche, invitation et activation du compte

Fonctionnalité ajoutée sur la branche `onboarding-comptes`. Elle comble deux manques constatés après la phase 3 :

- aucun moyen de créer un compte de connexion depuis l'application ;
- aucun moyen de changer son mot de passe.

## 1. Parcours

```text
 RH (rôle hr_manager)                     Base (procédure account_onboard, DEFINER iam_owner)
 ─────────────────────                    ───────────────────────────────────────────────────
 /employees/new : prénom, nom,        ──► payroll_assert : rôle RH actif, permission employees.create
 e-mail PERSONNEL (pas de matricule)      matricule EMP-<année>-<numéro> généré, puis INSERT employees
                                          identifiant prenom.nom@securepayroll.ma (suffixe 2, 3… si homonyme)
 PHP : mot de passe temporaire aléatoire  INSERT accounts : password_change_required = TRUE,
       haché en Argon2id AVANT l'appel    expiration = maintenant + 72 h
                                          INSERT account_invitations (e-mail personnel, auteur, échéance)
                                          INSERT role_assignments : rôle Employé, auteur = la RH,
                                          motif « Embauche »                        → COMMIT (tout ou rien)
 PHP : e-mail écrit dans la boîte d'envoi privée (0600) → adressé à l'e-mail personnel
 La RH voit le matricule attribué et l'identifiant créés, jamais le mot de passe temporaire.

 Salarié
 ───────
 1re connexion (identifiant + mot de passe temporaire)
   → session ouverte, mais SEUL sp_session est actif en base, et toute page redirige vers /password
 /password : mot de passe temporaire + nouveau mot de passe (deux fois)
   → procédure account_change_password (rôle sp_password) → compte actif, autres sessions fermées
```

## 2. Besoin d'en connaître : ce que la RH voit et ne voit pas

La RH crée le salarié, mais n'a pas besoin de toutes ses données. Matrice retenue :

| Donnée | Salarié (lui-même) | RH | Finance | Paie |
|---|---|---|---|---|
| Nom, prénom, matricule | — | lit, écrit | lit | lit |
| E-mail / téléphone personnels | lit, modifie | **écrit à l'embauche, ne relit jamais** | — | — |
| CIN, CNSS | lit masqué | écrit, lit masqué | — | lit (déclarations CNSS) |
| Situation familiale, enfants | lit | lit, écrit | — | lit (charges de famille) |
| RIB | lit masqué, demande un changement | **aucun accès** | lit masqué ; le paiement l'utilise sans l'afficher | — |
| Salaire | son bulletin | lit, propose | lit, décide | via les procédures |

**Mis en œuvre dans cette fonctionnalité :**

- **E-mail personnel.** La RH l'écrit dans le formulaire d'embauche. Il est enregistré dans `account_invitations`, et aucun rôle de l'application ne peut le lire (refus 1142 vérifié). Il n'est pas réaffiché après l'enregistrement, ni écrit dans le journal.
- **Formulaire d'embauche.** Il ne contient ni RIB, ni CIN, ni CNSS.
- **Mot de passe temporaire.** Il est généré par PHP, puis transmis au seul salarié. La base ne reçoit que son empreinte Argon2id.

**Reste à faire (phase 6, protection des données sensibles).** Le salarié saisira lui-même son RIB, et un changement ultérieur exigera une double validation et une alerte au salarié (menace T-08). Les affichages masqués de la matrice n'existent pas encore, car l'application n'affiche aucune donnée de `employee_personal_data` à ce stade.

## 3. Contrôles et pourquoi ils fonctionnent

| Menace | Contrôle | Où |
|---|---|---|
| La RH connaît le mot de passe du salarié et peut se connecter à sa place | Mot de passe généré côté serveur, envoyé à l'adresse personnelle, jamais affiché à la RH ; changement obligatoire à la 1re connexion | `Onboarding::onboard`, `Controller` |
| Un compte non activé est utilisé avec le mot de passe temporaire intercepté | Pendant l'attente : seul `sp_session` actif en base (aucun droit métier) ; toute page redirige vers `/password` ; expiration au bout de 72 h, vérifiée à la connexion **et** dans la procédure | `SessionRoles::names`, `AuthService::login`, `account_change_password` |
| Création d'un compte avec un rôle élevé | La procédure n'attribue que le rôle Employé ; les autres rôles restent réservés à l'administrateur (`iam_grant`, sans auto-attribution) | `account_onboard` |
| Un non-RH crée un compte, y compris par appel SQL direct | `EXECUTE` accordé au seul rôle `sp_hr_manager`, **et** `payroll_assert` revérifie le rôle de l'acteur en base. Le droit `INSERT` direct sur `employees` est retiré à la RH | `onboarding_grants.sql` |
| Création partielle (salarié sans compte, compte sans rôle) | Une seule transaction ; `ROLLBACK` sur toute erreur | `account_onboard` |
| Injection d'en-têtes dans l'e-mail (`\r\nBcc:`) | Adresse validée (`FILTER_VALIDATE_EMAIL`, aucun caractère de contrôle) ; refus des retours à la ligne dans le destinataire et l'objet | `Onboarding::personalEmailError`, `Outbox::send` |
| Identifiant forgé (`'; DROP …`) | Identifiant réduit à `[a-z0-9.-]` en PHP, puis revérifié par une expression régulière dans la procédure ; requêtes préparées | `Onboarding::loginBase`, `account_onboard` |
| Changement du mot de passe d'un autre compte | La procédure exige l'**empreinte actuelle**, que PHP ne lit que sous `sp_login`, après vérification du mot de passe actuel. Le seul droit `EXECUTE` ne suffit donc pas | `account_change_password` |
| Force brute sur le formulaire de changement | Même limiteur que la connexion (5 essais par compte, 30 par adresse, sur 15 min) | `Controller::password` |
| Session volée conservée après un changement de mot de passe | Toute session ouverte avant `password_changed_at` est fermée à la requête suivante | `AuthService::currentUser` |
| Mot de passe faible | 12 à 128 caractères, différent de l'actuel, sans le nom, le prénom ou l'identifiant, hors liste de mots de passe courants | `PasswordPolicy` |
| Fuite par les journaux | Le journal trace `account.onboarded`, `auth.password_changed` et `auth.password_change_failed` (motif seulement), sans mot de passe ni e-mail personnel | `auditEvent` |

## 4. Rôles MySQL

- **`account_onboard`** est exécutable par `sp_hr_manager` seulement.
- **`account_change_password`** est exécutable par un nouveau rôle, `sp_password`. Il n'est actif que le temps de l'appel (`SessionRoles::duringPasswordChange`). Il n'est pas accordé à `sp_session`, qui est actif avant même la vérification du mot de passe actuel.
- **`sp_session`** lit désormais aussi `login`, `password_change_required` et `password_changed_at`, mais aucune empreinte.
- **Le propriétaire `iam_owner`** reçoit exactement les colonnes écrites par les deux procédures. Il reçoit aussi `EXECUTE` sur elles : MySQL vérifie ce droit du DEFINER, comme pour `iam_grant`.

Le système compte désormais **12 rôles MySQL** : 9 rôles applicatifs et 3 d'exploitation.

## 4 bis. Matricule généré et choix des employés

Deux frictions de saisie ont été levées après la mise en place de l'embauche :

- **Matricule.** La RH ne le tape plus. La procédure `account_onboard` (migration 014) l'attribue au format
  `EMP-<année>-<numéro sur 3 chiffres>`, la séquence suivant le plus grand numéro déjà attribué dans l'année. Cela
  supprime les fautes de frappe, les formats divergents et les collisions. L'index unique sur `employee_number` reste
  le garde-fou : deux embauches simultanées visant le même numéro font échouer la seconde (1062), à rejouer — limite
  assumée vu le très faible volume RH, sans table de séquence dédiée.
- **Désignation d'un employé (contrats, affectations, rémunération).** Les champs texte où il fallait connaître le
  matricule par cœur sont remplacés par un menu déroulant des employés actifs (`EmployeeRepository::activeOptions`),
  comme les départements et les postes. Le formulaire soumet toujours le matricule : la résolution côté serveur et sa
  validation sont inchangées. Le formulaire de rémunération en bénéficie aussi (employé en menu déroulant) ; sa
  référence de contrat reste saisie, une sélection en cascade employé → contrat restant une amélioration ultérieure.

## 5. Boîte d'envoi locale

Le projet n'a pas de serveur de messagerie. Chaque message est donc écrit dans `.local/runtime/outbox/` : dossier en 0700, fichiers en 0600, noms aléatoires. La classe refuse d'écrire hors d'un répertoire d'exécution privé, si bien qu'aucun mot de passe temporaire ne peut atterrir dans l'arborescence du projet.

Pour lire la boîte d'envoi (dans un terminal uniquement, sans redirection) :

```bash
python3 bin/init-local.py outbox
```

Brancher un vrai serveur SMTP ne demanderait de remplacer que `App\Mail\Outbox`. Limite assumée : un message transmis sans TLS exposerait le mot de passe temporaire. Le changement obligatoire et l'expiration à 72 h en réduisent la durée d'utilité.

## 6. Mise à niveau d'une instance existante

Une instance `.local/` installée avant cette fonctionnalité se met à niveau sans perte :

```bash
python3 bin/init-local.py upgrade
```

La commande applique les migrations 013 et 014 et `onboarding_grants.sql` une seule fois ; des témoins (colonne, nombre de paramètres de la procédure) indiquent si c'est déjà fait. La migration 014 remplace `account_onboard` : le matricule n'est plus un paramètre, il est généré par la base. Elle vérifie ensuite l'inventaire (27 tables, 26 procédures, 46 triggers) et les 12 rôles, puis écrit un fichier privé `upgrade-<date>.json`. Les comptes existants ne sont pas concernés : `password_change_required` vaut faux par défaut.

Vérification faite : une instance a été installée avec le code de `main`, puis mise à niveau, deux fois de suite. Le second passage n'applique rien. La matrice des privilèges de l'instance mise à niveau est identique à celle d'une installation neuve.

## 7. Tests

| Test | Contrôles |
|---|---|
| `php tests/onboarding-unit.php` (sans base) | 52 : identifiant, adresse personnelle, mot de passe temporaire (format, unicité, environ 92,9 bits), politique, rôles d'un compte non activé, boîte d'envoi (0700/0600, injection d'en-têtes), cohérence des scripts SQL, génération du matricule (format, `p_number` retiré, droits EXECUTE réaccordés) |
| `python3 tests/local-install.py` (instance neuve) | 132 au total. Le scénario d'embauche ajoute notamment : refus au Salarié ; adresses invalides (rien créé) ; compte en attente et rôle tracé ; invitation privée ; mot de passe temporaire absent de la page RH et du journal ; e-mail personnel illisible en base ; homonyme ; redirection forcée ; mot de passe faux (401) ou faible (422) ; activation ; session antérieure fermée ; ancien mot de passe refusé ; mot de passe temporaire expiré refusé, en HTTP **et** dans la procédure ; changement impossible sans l'empreinte actuelle ; matrice `sp_password` |
