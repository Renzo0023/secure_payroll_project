# Sauvegarde, restauration et incident

Mise à jour de finalisation : la restauration complète incluant corrections,
paiements fictifs, remboursements et IAM a passé 35 contrôles dans deux instances
privées. Le lanceur d’activation administrative impose désormais un snapshot
InnoDB avant DDL. Voir [le rapport](FINALIZATION-VALIDATION-2026-11-06.md) et
[la procédure principale](FINALIZATION.md). Aucun export/restauration principal
n’a été effectué ; les instructions historiques suivantes restent à appliquer
dans un contexte administratif validé.

Procédure préparée, non exécutée. Ne pas considérer une sauvegarde exploitable avant
un essai de restauration dans une instance indépendante. Ne jamais restaurer sur
`secure_payroll` sans autorisation explicite et plan de reprise validé.

## Sauvegarde

Le DBA doit disposer d'un compte de sauvegarde dédié, de ses privilèges minimaux
pour la version MySQL installée et d'un login-path privé existant nommé
`securepayroll-backup`. Aucun secret ne doit être ajouté au projet. La création
du compte et l'attribution de ses droits sont des opérations administratives.

Dans un terminal privé, choisir un répertoire hors projet, sur un stockage protégé :

```bash
umask 077
backup_dir="$(mktemp -d /var/tmp/securepayroll-backup.XXXXXXXX)"
mysqldump --login-path=securepayroll-backup --single-transaction --quick \
  --routines --triggers --events --hex-blob --no-tablespaces \
  --set-gtid-purged=OFF --databases secure_payroll > "$backup_dir/database.sql"
```

Contrôler immédiatement le code de retour de mysqldump. Un fichier présent ou non
vide ne prouve pas le succès. En cas d'erreur, conserver le fichier comme export
incomplet et ne pas le réutiliser comme sauvegarde valide. Après succès :

```bash
sha256sum "$backup_dir/database.sql" > "$backup_dir/database.sql.sha256"
sha256sum --check "$backup_dir/database.sql.sha256"
```

Copier la sauvegarde et son empreinte sur un support privé chiffré, conserver des
versions datées et restreindre les accès. Aucun effacement automatique n'est prévu.
Ne pas réaliser de DDL pendant le dump : `--single-transaction` ne protège pas
contre les changements de schéma. Les comptes, GRANT et propriétaires ne sont pas
inclus dans cet export : conserver séparément leur inventaire administratif privé.
Les journaux de sécurité doivent être sauvegardés et conservés séparément.

## Restauration d'essai

Utiliser une instance MySQL isolée dont l'administrateur confirme l'identité et le
volume. Le dump contient `CREATE DATABASE` et `USE secure_payroll` : changer seulement
l'option `--database` du client ne redirige **pas** la cible. Ne pas importer ce dump
sur l'instance principale pour un essai. Préparer sur l'instance isolée les propriétaires
verrouillés nécessaires aux DEFINER puis importer avec son login-path privé, après
validation administrative. Réappliquer les droits revus, sans recopier les secrets.

Après restauration : vérifier empreinte, tables, contraintes, routines, DEFINER,
triggers et comptes verrouillés ; comparer les comptes de lignes et les totaux
financiers ; tester les refus de modification des historiques et une connexion
applicative non-root. Mesurer les durées pour fixer les objectifs de reprise.

## Incident

Restreindre l'accès au service concerné avec l'administrateur. Préserver les logs,
les horodatages UTC et les preuves avant correction. Documenter la chronologie,
les identifiants techniques et le périmètre, sans recopier de mots de passe.
Révoquer ou renouveler les secrets exposés via un canal privé et une validation
administrative. Restaurer d'abord dans l'instance indépendante, vérifier l'intégrité,
puis faire approuver la remise en service et la reprise éventuelle de production.
Ne pas effacer les historiques pour masquer ou corriger un incident financier.

## Lanceur de sauvegarde ajouté

`bin/backup.py` réalise un export et copie les logs sans modifier les sources.
Il exige un login-path de sauvegarde déjà configuré, un compte dédié non-root
(distinct de svc_php et des propriétaires) et un répertoire privé hors projet.
Il se connecte uniquement à 127.0.0.1, port 3306 par défaut, à `secure_payroll`.
Il ne crée pas de compte SQL et ne demande pas de secret dans les arguments.

Après préparation administrative du compte et du login-path :

```bash
install -d -m 700 "$HOME/securepayroll-backups"
python3 bin/backup.py --login-path securepayroll-backup \
  --directory "$HOME/securepayroll-backups"
```

Chaque exécution utilise un nouveau répertoire horodaté et des fichiers 0600.
Le fichier reste `database.partial.sql` en cas d'échec du dump. Après succès,
`manifest.json` contient tailles et SHA256, et `EXPORT_COMPLETE` indique seulement
que l'export et la copie des journaux sont terminés. Les données et journaux ne
sont jamais supprimés. Les journaux copiés pendant l'activité du service ne sont
pas un instantané transactionnel synchronisé avec le dump. Planifier une fenêtre
sans DDL pour garantir la cohérence du schéma.

Ce lanceur n'a pas été exécuté sur la base principale faute de login-path disponible.
La restauration reste une opération administrative distincte et non testée.

## Exercice réel dans le laboratoire autorisé

Le lanceur de sauvegarde accepte désormais un socket Unix explicite (`--socket`)
et une authentification privée fournie sur stdin (`--user ... --password-stdin`),
comme alternative au login-path. Aucun secret ne doit être saisi dans une commande
shell ou son historique. L'option `--logs-directory` permet de copier le runtime
privé du laboratoire sans lire les journaux principaux.

L'exercice suivant a été réellement exécuté sur une instance de test préexistante,
arrêtée, créée par le lanceur de laboratoire :

```bash
python3 lab/mysql-recovery.py \
  --source-private-dir /tmp/securepayroll-mysql-5g9p67gy
```

Résultat : 32 contrôles réussis, dont restauration dans un second datadir privé,
comparaison de toutes les tables et des totaux financiers, lecture avec svc_php
recréé et refus de modification d'un calcul restauré. Voir
[le rapport](LAB-VALIDATION-2026-11-04.md). Aucun export ni restauration de la base
principale n'a été effectué. Les sauvegardes de laboratoire dans /tmp ne constituent
pas une sauvegarde durable de la VM ou de l'application principale.

## Chiffrement de la sauvegarde et exercice phases 6-7 (phase 8)

Le dump contient la structure, les empreintes Argon2id et les colonnes chiffrées de la phase 6. Il doit
être **chiffré au repos**. `bin/backup-crypt.py` chiffre/déchiffre un fichier en AES-256-GCM (authentifié),
la clé de 32 octets étant lue dans un fichier, jamais passée en argument :

```bash
python3 bin/backup-crypt.py keygen  --key "$HOME/securepayroll-keys/backup.key"      # une fois, 0600
python3 bin/backup-crypt.py encrypt --in  "$backup_dir/database.sql" \
        --key "$HOME/securepayroll-keys/backup.key" --out "$backup_dir/database.sql.enc"
shred -u "$backup_dir/database.sql"       # ne conserver que le chiffré
```

Restauration : `decrypt` avec la même clé (GCM refuse une mauvaise clé ou une altération), puis import.

**Clés à conserver séparément de la sauvegarde** : la clé de sauvegarde ci-dessus **et** les clés de
chiffrement des données (phase 6 : `runtime/keys/field.key`, `blind.key`). Sans la clé de sauvegarde, le
fichier est illisible ; sans les clés phase 6, les données restaurées restent du chiffré illisible.

**Les GRANT ne sont pas dans un dump logique.** Après import, réappliquer la couche de droits depuis
l'inventaire administratif (`database/setup/*grants*.sql`, `app_roles.sql`, …) : les privilèges d'objet
(table/colonne/routine) disparaissent avec les objets lors du `DROP`/`CREATE` du dump.

Exercice complet rejouable (sauvegarde → chiffrement → perte de lignes **et** suppression de table →
restauration → vérification d'intégrité incluant déchiffrement et piste d'audit) :

```bash
python3 tests/backup-recovery.py      # 19 contrôles, instance jetable isolée sous /tmp
```
