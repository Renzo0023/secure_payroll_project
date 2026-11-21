# Captures — Phase 7 (journalisation et supervision)

Illustrations pour la section « Auditing and Monitoring » du rapport. Données de **démonstration**
sur l'instance locale (`.local`) ; aucun secret réel.

## Images fournies

| Fichier | Ce qu'il montre | Usage conseillé dans le rapport |
|---|---|---|
| `01-audit-vue-ensemble.jpg` | Page `/audit` (auditeur *Noa Audit*) : panneau **« Signaux suspects (24 h) »** avec la *Rafale d'échecs de connexion* détectée (compte#4, 5 occurrences) + liste des **événements récents** (résultats colorés Succès/Échec, compte visé résolu dans la colonne *Ressource*). | Figure « supervision + détection d'activité suspecte ». |
| `02-audit-detail-connexion-echouee.jpg` | Une ligne `auth.failed` **dépliée** : l'auditeur voit le **compte visé résolu** (`accounts#4 · employee.demo · Nadia TRAORE`), la **source réseau (IP 127.0.0.1)**, l'acteur (« tentative non authentifiée », compte MySQL `svc_php@localhost`), la source (Application) et le **contexte** complet (`reason`, `known_account`, `target_account_id`). | Figure « détail forensique : qui/quoi/quand/ressource/résultat + source ». |
| `03-audit-acces-refuse-salarie.jpg` | Un **salarié** (Nadia TRAORE) qui ouvre `/audit` reçoit **403 Accès non autorisé** ; le menu « Audit de sécurité » est d'ailleurs absent de sa barre. | Figure « contrôle d'accès : supervision réservée à l'auditeur ». |
| `04-idor-employes-bloque.jpg` | **Défense IDOR** : le salarié *Nadia TRAORE* force l'URL `/employees/6` (fiche d'un autre employé) → **403**. La protection est l'**autorisation par objet côté serveur** (`app/Web/Controller.php:214` : un non-RH n'accède qu'à son propre `employee_id`), pas l'obscurcissement de l'identifiant ; la tentative est de plus **tracée** (`access.denied`). | Figure « défense contre l'IDOR : autorisation par objet, pas sécurité par obscurité ». |

### Note — IDOR et identifiants séquentiels
L'ID entier visible dans l'URL (`/employees/5`) n'est **pas** une faille ici : l'IDOR est bloquée par
l'autorisation au niveau de l'objet, vérifiée côté serveur à chaque requête (fiche employé : propre
`employee_id` ou rôle RH ; bulletin : requête filtrée par propriétaire ; données personnelles : aucun ID
en URL, lecture via la session). Encoder ou chiffrer l'ID serait de la sécurité par l'obscurité et ne
remplacerait pas ce contrôle. Un identifiant opaque (UUID) resterait une option de **durcissement**
anti-énumération (phase 9), en complément — jamais en substitut — de l'autorisation.

> Chaque ligne du journal se **déplie** (clic) pour révéler le détail complet (acteur applicatif + compte
> MySQL, compte/ressource visé résolu, IP source, contexte JSON) — voir `02`.

## Reproduire la preuve terminal d'inviolabilité (à capturer vous-même)

Instance démarrée (`python3 bin/init-local.py serve`), depuis la racine du projet :

```bash
python3 - <<'PY'
import importlib.util; from pathlib import Path
s=importlib.util.spec_from_file_location('m','bin/init-local.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
inst=m.LocalInstance(Path('.local'))
for stmt in ["UPDATE security_audit_log SET outcome='success' WHERE id=1;",
             "DELETE FROM security_audit_log WHERE id=1;"]:
    try: inst.sql("USE secure_payroll; "+stmt); print(stmt, "-> ACCEPTÉ (ANOMALIE)")
    except Exception as e: print(stmt, "-> REFUSÉ :", e)   # code 1644 = ajout seul
print(inst.sql("USE secure_payroll; CALL audit_suspicious();"))  # lecture par procédure
PY
```

Attendu : les deux écritures **refusées (code 1644)**, puis la ligne de détection.

## Rejouer le scénario (pour la vidéo)

1. `python3 bin/init-local.py serve` puis `python3 bin/init-local.py credentials` (mots de passe de démo).
2. **Salarié** `employee.demo` : se connecter → *Mes données personnelles* → enregistrer un RIB → tenter l'URL `/audit` (⇒ 403).
3. **Attaque** : sur la page de connexion, 5 essais ratés sur `hr.demo` (mot de passe quelconque).
4. **Auditeur** `audit.demo` : se connecter → menu **« Audit de sécurité »** → le panneau « Signaux suspects » montre la rafale, le tableau liste tous les événements.

> Astuce : sur une instance fraîchement réinstallée, le panneau de signaux est vide tant que l'activité
> (étapes 2–3) n'a pas été jouée.
