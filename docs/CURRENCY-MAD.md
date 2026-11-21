# Devise officielle : dirham marocain (MAD)

**Installation actuelle :** les tables de rémunération sont confirmées présentes.
La présence des tables ne suffit pas à prouver la version de devise installée.
Faire vérifier les colonnes et les routines avec `bin/payroll-admin.py inspect` ;
ne pas rejouer 006 sans avoir identifié précisément l’état existant.

Nadia Traoré : salaire mensuel de base proposé **12 000,00 MAD**. Le montant reste 12000.00 en base : aucun taux de change, conversion, multiplication ou arrondi n'est appliqué.

Le formateur commun `app/Finance/Money.php` utilise des chaînes décimales : `12 000,00 MAD` en français et `12,000.00 MAD` en anglais. Les formulaires de nouvelles demandes indiquent MAD. Les listes, fiches et historiques lisent la devise enregistrée avec le montant ; ils ne remplacent jamais un ancien code par MAD au moment de l'affichage.

## Activation d'un module de rémunération déjà installé

Pour une installation existante, suivre le [correctif ciblé sauvegardé et testé](MAD-REPAIR.md).
Ne rejouer ni 006, ni 004/005, ni les migrations RH. Le correctif traite les
colonnes, les contraintes et les trois procédures, en restaurant les privilèges
exacts enregistrés avant intervention. Il demande une autorisation interactive
avant tout DDL sur la principale. Garder l’application arrêtée jusqu’au succès
de `sudo python3 bin/payroll-admin.py inspect`.

Redémarrer le serveur comme utilisateur habituel :

```bash
python3 bin/local-demo.py serve
```

Si le module n'est pas encore installé, utiliser la procédure d'activation initiale dans [COMPENSATION.md](COMPENSATION.md) : le lanceur inclut maintenant 006 après 004/005. Ne pas appliquer 006 seule avant l'installation des tables et procédures dont elle dépend.

## Effet exact de la migration

- Élargit `currency` de CHAR(2) à CHAR(3) dans compensation_requests et salary_conditions ; défaut MAD.
- Conserve DECIMAL(12,2), les montants, identifiants, dates, décisions et données historiques.
- Conserve UM dans les contraintes pour lire les données existantes sans les altérer. Les nouvelles demandes passent exclusivement par la procédure qui écrit MAD.
- Recrée uniquement compensation_check_period, compensation_submit et compensation_decide avec leurs signatures, transactions, autorisations, collations et propriétaire compensation_owner@localhost conservés ; SQL SECURITY DEFINER reste explicite.
- Restaure les EXECUTE du propriétaire sur ces trois procédures, et de svc_php sur les deux commandes publiques. Aucun nouvel accès direct aux données salariales.
- Une approbation copie la devise MAD de la demande. Une demande historique UM reste consultable et peut être rejetée, mais ne peut pas être approuvée silencieusement en MAD.
- Une révision MAD sur un contrat possédant déjà un salaire approuvé UM est bloquée pour imposer une revue explicite. Aucun workflow de conversion n'est créé par cette modification. Il faut définir et autoriser séparément le traitement métier de ces historiques ; ne pas modifier leur montant ou leur devise à la main.

Les nouvelles demandes sont bloquées côté PHP tant que les colonnes ne sont pas configurées pour MAD. L'application doit rester arrêtée pendant toute la mise à jour, y compris la recréation des procédures.

## Vérifications et futurs bulletins

Après activation autorisée, soumettre une nouvelle demande pour Nadia avec 12000,00, puis l'approuver avec Finance : fiche et historique doivent afficher 12 000,00 MAD (ou 12,000.00 MAD en anglais). Une ancienne condition UM doit continuer à apparaître comme UM, avec son montant inchangé.

Les futurs calculs et bulletins devront conserver DECIMAL(12,2), enregistrer MAD pour leurs nouvelles données et afficher la devise de la donnée source avec `App\Finance\Money::format`. Ne jamais inférer la devise d'un ancien montant depuis la seule devise de référence actuelle. Les bulletins ne sont pas encore développés.

Les contrôles de syntaxe et de cohérence sont réalisés hors connexion. La validation MySQL isolée du correctif ciblé est décrite dans [MAD-REPAIR.md](MAD-REPAIR.md) ; elle ne prouve pas l’état de la principale.
