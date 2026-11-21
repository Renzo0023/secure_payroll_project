# Préparation de publication privée — SecurePayroll

## Destination et statut

Destination demandée : **bymelwine/securepayroll**, visibilité **privée**. La préparation locale et les tests sont réalisés. La branche locale `main` et la destination `origin=https://github.com/bymelwine/securepayroll.git` sont préparées ; un premier commit propre a été validé depuis un clone local indépendant. Le propriétaire a confirmé le 15 novembre 2026 la création du dépôt GitHub privé à cette adresse. Il ne faut pas recréer ce dépôt. Le push doit encore être effectué avec un accès GitHub authentifié, puis confirmé par comparaison des références distantes ; sa réussite ne doit pas être déduite de la seule présence de origin.

Aucun jeton GitHub n’est inscrit dans le projet ou demandé dans la conversation. Le propriétaire a indiqué que son compte est connecté à VS Code. Cette session doit néanmoins vérifier qu’elle peut utiliser cette authentification ; sinon le push peut être déclenché depuis l’interface Git de VS Code avec le compte déjà connecté. Ne pas créer un dépôt public pour contourner ce prérequis.

## Périmètre conservé

Frontend, backend, configuration PDO générique, tous les scripts de migrations, procédures, triggers, permissions, patches et audit SQL ; scripts d’exploitation historiques ; tests et documentation. Le nouveau lanceur `bin/init-local.py` emploie un ordre explicite de sources SQL, jamais une réapplication automatique sur une base existante. `database/seeds/009_collaboration_demo.sql` crée seulement de nouvelles données fictives dans cette instance neuve.

L’ancien README est conservé dans `docs/README-HISTORIQUE.md`. Les fonctions métier n’ont pas été modifiées.

## Exclusions vérifiées

`.local/`, les fichiers `.env` autres que le modèle vide, clés, profils MySQL, journaux, compteurs de connexion, `storage/logs/demo-credentials.json`, `storage/logs/demo-verification.json`, tout le dossier de réparation `storage/mad-repair-*` (dump et états compris), sauvegardes/export et caches Python ne sont pas à publier. Les copies SQL générées des anciens tests sont également exclues ; les sources originales sont conservées.

Le fichier privé `storage/mad-repair-20261106T184209Z/applied.json` n’est pas lisible avec les droits courants. Son répertoire entier est exclu, aucun droit supplémentaire n’est demandé pour en extraire le contenu. Ce refus ne doit pas devenir une raison de publier le fichier ou le dump.

## Audit des secrets et historique

Le dépôt ne possédait **aucun commit ni ref** avant cette mission ; l’index déjà préparé et les **19 objets Git initiaux**, dont 10 blobs, ont néanmoins été contrôlés. Aucune réécriture d’historique n’est nécessaire ni effectuée. L’audit final doit être relancé après préparation du commit.

`bin/audit-secrets.py` analyse les fichiers publiables, chaque blob de l’index et tous les objets locaux Git, même non accessibles par une branche. Les secrets privés lisibles sont comparés en mémoire aux contenus publiables ; les rapports indiquent seulement le chemin, la ligne et le type de détection. Le texte des PDF est aussi extrait pour contrôle lorsque pdftotext est disponible.

Deux cas explicitement revus ne sont pas des identifiants opérateur : l’empreinte publique de travail constant du login inexistant dans AuthService, et la chaîne volontairement invalide du test de refus pour utilisateur absent. Ils restent documentés comme tels, sans affaiblir les contrôles des vrais secrets.

Résultat machine : [PUBLICATION-SECURITY-AUDIT.json](PUBLICATION-SECURITY-AUDIT.json). L’absence de détection par motifs ne prouve pas l’absence de tout secret imaginable ; la revue des chemins et des changements complète cet outil. **Un résultat non réussi interdit le push.**

## Validation et suite de publication

La recette réelle est décrite dans [COLLABORATION-VALIDATION.md](COLLABORATION-VALIDATION.md) : 58 contrôles serveur/HTTP et 389 hors connexion, sur des cibles distinctes de la principale.

Après authentification GitHub, la publication doit : utiliser exclusivement le dépôt existant `bymelwine/securepayroll`, annoncé privé par son propriétaire ; vérifier ses informations accessibles ; refuser tout historique distant incompatible ; pousser normalement la branche préparée sans `--force`, sans inclure les fichiers privés ; confirmer ensuite le commit distant et les fichiers publiés. Aucun collaborateur n’est invité sans liste nominative autorisée.

La barrière elle-même a passé **8 contrôles réels** dans un dépôt Git temporaire : acceptation d’un dépôt sain, exclusion des secrets privés, détection d’une copie accidentelle, absence de valeur sensible dans les rapports, détection d’un jeton synthétique et maintien de sa détection après retrait du fichier courant grâce à l’inspection de l’historique. Aucun vrai jeton ni accès réseau n’a été utilisé.

Le propriétaire peut ensuite inviter ses collaborateurs depuis les paramètres d’accès du dépôt. Chaque collaborateur génère ses secrets et reconstruit son instance locale ; aucune sauvegarde de la VM n’est nécessaire.

## Vérification d’accès lors de la finalisation

La lecture distante `git ls-remote origin`, tentée hors confinement réseau avec saisie interactive désactivée, a échoué : `fatal: unable to get password from user`. La connexion du compte dans VS Code n’est donc pas utilisable par ce processus Git. Aucun jeton n’a été demandé ni enregistré dans le projet. Une vérification des fichiers distants ne peut être annoncée sans authentification utilisable.

Après le dernier commit local, le propriétaire peut déclencher le push depuis le panneau **Contrôle de code source** de VS Code, via le menu **…**, puis **Push / Pousser** ou **Push to… / Pousser vers…**, et sélectionner le remote existant **origin**, branche **main**. Ne pas choisir une action créant un nouveau dépôt et ne pas utiliser de force push. Autoriser l’authentification GitHub de VS Code si elle est demandée. Sur GitHub, sélectionner main et comparer le dernier commit avec le commit local affiché dans l’historique Git ; contrôler README, app, public, database et bin/init-local.py.

Référence de l’interface : [gestion des dépôts distants dans VS Code](https://code.visualstudio.com/docs/sourcecontrol/repos-remotes).
