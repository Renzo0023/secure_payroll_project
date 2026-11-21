#!/usr/bin/env python3
"""Génère le rapport SecurePayroll en .docx (via HTML + LibreOffice), style du modèle input/Rapport.docx.
Prose française, mots de liaison, sans puces ni pronoms personnels (« nous »), captures embarquées."""
import base64, pathlib, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]  # racine du dépôt (docs/security-assessment/<script>)
CAP = ROOT / 'docs/security-assessment/captures-phase7'
ERD = ROOT / 'docs/security-assessment/erd/images'
ARCHI = ROOT / 'docs/security-assessment/architecture.png'
CR = ROOT / 'docs/security-assessment/captures-rapport'
OUT = ROOT / 'RAPPORT-SecurePayroll.docx'
SP = pathlib.Path(tempfile.mkdtemp(prefix='securepayroll-report-'))  # intermédiaires hors du dépôt

_fig = 0
def img(path, width=560, caption=''):
    global _fig
    data = pathlib.Path(path).read_bytes()
    ext = pathlib.Path(path).suffix.lstrip('.').replace('jpg', 'jpeg')
    b64 = base64.b64encode(data).decode()
    _fig += 1
    cap = f'<p class="cap">Figure {_fig} — {caption}</p>' if caption else ''
    return (f'<p class="imgp"><img src="data:image/{ext};base64,{b64}" width="{width}"></p>{cap}')

def figcap(caption):
    global _fig
    _fig += 1
    return f'<p class="cap">Figure {_fig} — {caption}</p>'

CSS = """
<style>
body { font-family: 'Liberation Serif','Times New Roman',serif; font-size: 12pt; line-height: 1.4; }
h1 { font-family: 'Liberation Sans',Arial,sans-serif; font-size: 18pt; color:#1b3a5b; page-break-before: always; }
h2 { font-family: 'Liberation Sans',Arial,sans-serif; font-size: 14pt; color:#23527c; }
h3 { font-family: 'Liberation Sans',Arial,sans-serif; font-size: 12.5pt; color:#2c3e50; }
p { text-align: justify; margin: 6pt 0; }
table { border-collapse: collapse; width: 100%; font-size: 10.5pt; margin: 8pt 0; }
th,td { border: 1px solid #889; padding: 4pt 6pt; text-align: left; vertical-align: top; }
th { background: #e8eef5; }
pre { background: #f3f4f6; border: 1px solid #ccc; padding: 6pt; font-family: 'Liberation Mono',monospace; font-size: 9pt; white-space: pre-wrap; }
.cap { font-style: italic; font-size: 10pt; color:#444; text-align:center; margin-top:2pt; }
.imgp { text-align:center; margin: 8pt 0 2pt 0; }
.cover { text-align:center; }
.cover .big { font-size: 20pt; font-weight: bold; color:#1b3a5b; }
.cover .mid { font-size: 14pt; }
.toc p { margin: 2pt 0; text-align:left; }
</style>
"""

# ------- CONTENU -------
H = []
def add(s): H.append(s)

# ---- PAGE DE GARDE ----
add('<div class="cover">')
add('<p class="mid">Université Internationale de Rabat (UIR)</p>')
add('<p class="mid">Département : Cybersécurité</p>')
add('<p class="mid">Module : Sécurité des bases de données</p>')
add('<p>&nbsp;</p><p>&nbsp;</p>')
add('<p class="mid">Rapport de projet</p>')
add('<p class="big">Conception, implémentation, test et durcissement<br>d\'un système de paie sécurisé — SecurePayroll</p>')
add('<p>&nbsp;</p><p>&nbsp;</p>')
add('<p class="mid"><b>Encadrant :</b> Dr. Harazeem Abdulganiyu</p>')
add('<p class="mid"><b>Réalisé par :</b></p>')
add('<p class="mid">CISSE Marwane Mouawiyah<br>LANKOANDE Melwine Ange Lormel Lankoulmani<br>'
    'SOUNDA Abdelkerim Ahmat<br>TILENGAR Mbaihornom Lionel<br>ZONGO Nabonswendé Regis Epiphane</p>')
add('<p>&nbsp;</p><p class="mid">Année universitaire 2025 — 2026</p>')
add('</div>')

# ---- SOMMAIRE (statique) ----
add('<h1 style="page-break-before:always">Sommaire</h1>')
toc = [
 '1. Résumé', '2. Introduction et description du système', '3. Architecture du système',
 '4. Diagramme entité-association et conception de la base', '5. Classification des données et analyse CIA',
 '6. Modèle de menace', '7. Conception de l\'authentification', '8. Contrôle d\'accès par rôles (RBAC)',
 '9. Mise en œuvre du moindre privilège', '10. Analyse de vulnérabilité',
 '11. Investigation et remédiation de l\'injection SQL', '12. Protection des données sensibles',
 '13. Journalisation et supervision', '14. Sauvegarde et restauration', '15. Durcissement de la base',
 '16. Investigation d\'un incident de sécurité', '17. Bilan final de sécurité', '18. Recommandations',
 '19. Conclusion', '20. Références',
 'Annexe A — Diagrammes entité-association détaillés', 'Annexe B — Reproduire les preuves']
add('<div class="toc">')
for t in toc:
    add(f'<p>{t}</p>')
add('</div>')

# ===================== 1. RÉSUMÉ =====================
add('<h1>1. Résumé</h1>')
add("<p>Le présent rapport décrit la conception et la sécurisation de SecurePayroll, une application de "
    "paie adossée à une base de données MySQL. La paie manipule des informations hautement sensibles — "
    "coordonnées bancaires, pièces d'identité, numéros de sécurité sociale et salaires — dont la "
    "divulgation ou l'altération exposerait directement les personnes et l'organisation. Pour cette "
    "raison, la sécurité a guidé chaque décision de conception, depuis le schéma relationnel jusqu'à "
    "l'exploitation.</p>")
add("<p>Le système repose sur un principe directeur unique : une <b>défense en profondeur</b> doublée "
    "d'un <b>moindre privilège de bout en bout</b>. L'application n'accède jamais directement aux "
    "tables ; toute opération transite par des rôles MySQL au périmètre strict et par des procédures "
    "stockées exécutées sous l'identité de propriétaires verrouillés. En complément, les données "
    "sensibles sont chiffrées au repos, les activités de sécurité sont tracées dans une piste d'audit "
    "en ajout seul, les sauvegardes sont chiffrées et la surface d'attaque est réduite à un socket privé.</p>")
add("<p>Au terme du projet, les neuf axes de sécurité imposés sont couverts et, surtout, "
    "<b>prouvés</b> : deux cent quatorze contrôles automatisés, rejouables sur une instance "
    "jetable, valident l'authentification, l'autorisation, le moindre privilège, la résistance à "
    "l'injection, le chiffrement, l'audit, la sauvegarde, le durcissement et la capacité d'enquête. "
    "Là où la prévention atteint ses limites — un administrateur de base conserve nécessairement des "
    "droits étendus — la détection et la capacité d'investigation prennent le relais.</p>")

# ===================== 2. INTRODUCTION =====================
add('<h1>2. Introduction et description du système</h1>')
add("<p>La multiplication des atteintes aux bases de données a fait de leur protection un enjeu "
    "central de la cybersécurité. Une base de paie concentre précisément les données qu'un attaquant "
    "convoite. C'est dans ce contexte que s'inscrit SecurePayroll, dont l'objectif n'est pas de "
    "proposer une interface sophistiquée, mais de démontrer une <b>architecture de données "
    "sécurisée</b>, méthodique et vérifiable.</p>")
add("<p>Fonctionnellement, l'application gère les employés, leurs affectations, leur rémunération, le "
    "calcul de la paie et les règlements. Plusieurs profils y interviennent : le salarié, le "
    "gestionnaire des ressources humaines, le gestionnaire de paie, le responsable financier, "
    "l'administrateur applicatif et l'auditeur de sécurité. À ces rôles applicatifs s'ajoutent des "
    "comptes d'exploitation de la base (administration, sauvegarde, investigation), strictement "
    "séparés des précédents.</p>")
add("<p>Sur le plan technique, la base <code>secure_payroll</code> est hébergée sur une instance "
    "MySQL 8.4 <b>privée</b>, accessible uniquement par un socket Unix local, sans aucune exposition "
    "réseau. L'ensemble — schéma, comptes, rôles, procédures, déclencheurs et jeux de données de "
    "démonstration — est installé de façon déterministe, ce qui rend chaque affirmation du rapport "
    "reproductible. Les secrets et les clés de chiffrement sont conservés hors de la base et hors du "
    "dépôt de code. Les actifs à protéger se répartissent ainsi en données publiques, internes et "
    "restreintes, ces dernières recevant les protections les plus fortes.</p>")

# ===================== 3. ARCHITECTURE =====================
add('<h1>3. Architecture du système</h1>')
add("<p>L'architecture de SecurePayroll obéit à une règle non négociable : <b>l'application n'accède "
    "jamais directement aux tables</b>. Chaque requête traverse une chaîne de responsabilités dont le "
    "périmètre se resserre à chaque étape, de sorte qu'une compromission à un niveau ne donne pas "
    "accès au niveau suivant.</p>")
add(img(ARCHI, 470, "Architecture en couches : aucun accès direct de l'application aux tables."))
add("<p>Au sommet, le compte de service <code>svc_php</code> ne détient <b>aucun privilège en "
    "propre</b> : il ne peut agir qu'à travers des rôles MySQL, chacun limité à l'exécution des "
    "procédures de son domaine. Aucune instruction de lecture ou d'écriture directe sur une table "
    "n'est émise par le code applicatif. Par conséquent, un attaquant qui compromettrait "
    "<code>svc_php</code> n'obtiendrait ni accès direct aux tables, ni les privilèges d'un "
    "propriétaire de données.</p>")
add("<p>Chaque procédure est en effet déclarée au nom d'un <b>propriétaire de domaine</b> "
    "(par exemple <code>hr_module_owner</code>, <code>personal_data_owner</code> ou "
    "<code>audit_owner</code>) et s'exécute sous son identité. Or ces propriétaires sont des comptes "
    "<b>verrouillés</b>, dotés d'un mot de passe aléatoire : personne ne peut s'y connecter. Ils "
    "n'existent que pour porter, à l'intérieur des procédures, les privilèges sur les seules tables "
    "concernées. Ce découpage réalise ainsi un moindre privilège à deux niveaux : l'appelant n'a que "
    "le droit d'exécuter la procédure, et la procédure ne peut toucher que son périmètre.</p>")
add("<p>Enfin, l'isolation de l'instance complète ce dispositif. Le serveur démarre sans réseau "
    "(<code>--skip-networking</code>), sans fichier de configuration externe "
    "(<code>--no-defaults</code>) et sans variable persistée, de sorte que la configuration de "
    "sécurité, explicite dans le code de lancement, ne peut être relâchée à notre insu. Un garde-fou "
    "interne refuse même de fonctionner si l'instance ouvrait un port : le durcissement est donc "
    "vérifié en continu, et non simplement supposé.</p>")

# ===================== 4. ERD =====================
add('<h1>4. Diagramme entité-association et conception de la base</h1>')
add("<p>La base <code>secure_payroll</code> est construite par une série de migrations SQL ordonnées, "
    "installées sur l'instance privée. Toutes les tables utilisent le moteur InnoDB et une collation "
    "sensible à la casse et aux accents ; les montants sont stockés en décimal exact et les "
    "horodatages en UTC, fixés par la base elle-même afin d'éviter toute dérive côté application.</p>")
add("<p>La conception sépare clairement les grands domaines — identité et contrôle d'accès, "
    "organisation des ressources humaines, rémunération, paie et règlements. Cette séparation n'est "
    "pas seulement fonctionnelle : elle soutient le moindre privilège, puisque chaque rôle ne reçoit "
    "de droits que sur les procédures de son domaine. L'intégrité référentielle est garantie par des "
    "clés étrangères strictes, et plusieurs tables sont rendues <b>immuables</b> : au lieu d'une "
    "suppression, l'historique est conservé et toute tentative de modification d'une donnée "
    "historisée est refusée par un déclencheur.</p>")
add(img(ERD / 'ERD-00-GLOBAL.png', 620, "Diagramme entité-association global de secure_payroll."))
add("<p>Les diagrammes détaillés par domaine (identité et RBAC, organisation RH, rémunération, paie, "
    "règlements) figurent en annexe. Ils montrent notamment la table des données personnelles "
    "chiffrées, isolée et reliée à l'employé, ainsi que la table d'audit en ajout seul, au cœur de la "
    "supervision.</p>")

# ===================== 5. CLASSIFICATION + CIA =====================
add('<h1>5. Classification des données et analyse CIA</h1>')
add("<p>Avant de protéger, il faut classer. Chaque table et, lorsque c'est pertinent, chaque colonne "
    "a été rangée dans l'un de trois niveaux de sensibilité, afin d'ajuster les protections au risque "
    "réel.</p>")
add('<table><tr><th>Niveau</th><th>Exemples</th><th>Protection associée</th></tr>'
    '<tr><td><b>Restreint</b></td><td>RIB, CIN, CNSS, salaires, empreintes de mots de passe, piste d\'audit</td>'
    '<td>Chiffrement au repos, accès par procédures, audit, interdiction de lecture directe</td></tr>'
    '<tr><td><b>Interne</b></td><td>Affectations, contrats, structure organisationnelle</td>'
    '<td>Accès par rôles, moindre privilège</td></tr>'
    '<tr><td><b>Public</b></td><td>Référentiels (départements, intitulés de poste)</td>'
    '<td>Lecture contrôlée</td></tr></table>')
add(figcap("Classification des données en trois niveaux de sensibilité."))
add("<p>À cette classification répond une analyse selon le triptyque confidentialité, intégrité et "
    "disponibilité. La <b>confidentialité</b> des données restreintes est assurée par le chiffrement "
    "au repos et par l'absence de tout accès direct. L'<b>intégrité</b> repose sur l'immutabilité des "
    "historiques, sur les contraintes référentielles et sur une piste d'audit en ajout seul qu'aucune "
    "opération ordinaire ne peut altérer et dont la falsification par un compte privilégié est "
    "elle-même détectée. La <b>disponibilité</b>, enfin, est traitée par une stratégie de sauvegarde chiffrée "
    "dont la restauration est effectivement vérifiée. Ainsi, chaque besoin de sécurité est associé à "
    "un contrôle précis, détaillé dans les sections suivantes.</p>")

# ===================== 6. MODÈLE DE MENACE =====================
add('<h1>6. Modèle de menace</h1>')
add("<p>La conception s'appuie sur un modèle de menace qui recense les attaquants plausibles et les "
    "scénarios qu'ils pourraient tenter. Nous distinguons l'attaquant externe, qui cherche à pénétrer "
    "le système, l'utilisateur légitime qui tenterait d'outrepasser ses droits, et l'acteur "
    "privilégié — un administrateur de base — dont l'accès étendu constitue un risque particulier.</p>")
add("<p>Parmi les menaces identifiées, l'une mérite une attention spéciale et sert de fil conducteur "
    "jusqu'à l'investigation finale : le risque <b>T-14</b>, soit l'<b>accès direct d'un opérateur "
    "privilégié</b> à la base, en dehors de l'application. Un administrateur dispose en effet, par "
    "nécessité de maintenance, de droits étendus. Plutôt que de prétendre l'en empêcher — ce qui "
    "serait illusoire — nous avons fait le choix explicite d'<b>accepter ce risque et de le traiter "
    "par la détection</b> : toute écriture directe sur une table sensible est enregistrée dans la "
    "piste d'audit, attribuée au compte réel. Cette décision structure la défense et se vérifie "
    "concrètement lors de l'incident simulé de la section 16.</p>")
add("<p>Pour chaque autre menace — injection SQL, accès indirect à un objet d'autrui (IDOR), "
    "privilèges excessifs, fuite de secrets, mauvaise configuration — un contrôle de prévention est "
    "associé, puis vérifié. Le modèle de menace n'est donc pas un exercice théorique : il relie "
    "chaque risque à une parade concrète et testée.</p>")

# ===================== 7. AUTHENTIFICATION =====================
add('<h1>7. Conception de l\'authentification</h1>')
add("<p>L'authentification constitue la première barrière. Les mots de passe des comptes applicatifs "
    "ne sont jamais stockés en clair ni au moyen d'une empreinte réversible : ils sont hachés avec "
    "<b>Argon2id</b>, une fonction de dérivation moderne conçue pour résister aux attaques par force "
    "brute matérielle grâce à son coût mémoire et temporel paramétrable. En cas de vol de la base, les "
    "empreintes ne permettent donc pas de retrouver les mots de passe.</p>")
add("<p>Au-delà du stockage, la politique d'authentification limite activement les tentatives. Deux "
    "compteurs indépendants opèrent sur une fenêtre de quinze minutes : après <b>cinq échecs sur un "
    "même compte</b>, les tentatives sur ce compte sont bloquées, ce qui contre la force brute ; et "
    "après <b>trente tentatives depuis une même adresse IP</b>, cette adresse est bloquée, ce qui "
    "contre la pulvérisation de mots de passe sur plusieurs comptes. Un compte bloqué ne déclenche "
    "aucun calcul Argon2id, de sorte que le verrouillage ne peut lui-même devenir un vecteur "
    "d'épuisement de ressources. Chaque échec est enregistré, ce qui permet de détecter une attaque en "
    "cours. L'onboarding suit la même rigueur : un compte est créé par les ressources humaines avec un "
    "mot de passe temporaire à changer à la première connexion, et un matricule est généré par la "
    "base.</p>")
add("<p>Il convient enfin de distinguer deux plans. Les comptes <b>applicatifs</b> s'authentifient "
    "par Argon2id au niveau de l'application ; les comptes <b>MySQL</b> (service, opérateurs) "
    "utilisent le mécanisme <code>caching_sha2_password</code> du serveur, avec des mots de passe "
    "aléatoires, tandis que les propriétaires de domaine demeurent verrouillés. Cette double couche "
    "garantit qu'aucun accès, applicatif ou direct, ne repose sur un secret faible.</p>")
add("<p>Afin d'illustrer cette rigueur, le parcours complet d'un nouvel employé, de la création de "
    "son compte jusqu'à son activation, est reproduit ci-dessous. Tout commence lorsque le service "
    "des ressources humaines enregistre l'employé ; aucune donnée bancaire n'est saisie à ce stade, "
    "l'employé renseignant lui-même ses coordonnées par la suite.</p>")
add(img(CR / 'onb-1-ajout-employe.png', 540, "Création d'un employé par les ressources humaines."))
add("<p>Dès l'enregistrement, un compte professionnel est provisionné automatiquement et un "
    "matricule permanent est attribué par la base. Une invitation est alors envoyée à l'adresse "
    "personnelle de l'employé, sans que personne n'ait connaissance de son futur mot de passe.</p>")
add(img(CR / 'onb-2-compte-cree.png', 540, "Compte professionnel créé et invitation envoyée."))
add("<p>L'invitation contient un <b>mot de passe temporaire</b>, valable soixante-douze heures et "
    "qu'il faudra obligatoirement changer à la première connexion. Passé ce délai, ce mot de passe "
    "cesse de fonctionner, ce qui limite la fenêtre d'exposition.</p>")
add(img(CR / 'onb-3-email-mdp-temporaire.png', 540,
    "Invitation adressée à l'employé, comportant un mot de passe temporaire à durée limitée."))
add("<p>Muni de ce mot de passe temporaire, l'employé se présente ensuite sur la page de connexion.</p>")
add(img(CR / 'onb-4-connexion.png', 540, "Page de connexion de l'application."))
add("<p>À cette première connexion, l'accès au reste de l'application est <b>bloqué</b> tant que le "
    "mot de passe temporaire n'a pas été remplacé. La politique imposée exige au moins douze "
    "caractères et interdit de réutiliser le nom, le prénom ou l'identifiant, ce qui écarte les "
    "secrets faibles ou devinables.</p>")
add(img(CR / 'onb-5-changement-mdp.png', 540,
    "Activation du compte : changement obligatoire du mot de passe à la première connexion."))
add("<p>Une fois le mot de passe personnel enregistré, le compte devient pleinement actif et "
    "l'employé accède à son espace de travail, limité aux fonctions correspondant à son rôle.</p>")
add(img(CR / 'onb-6-tableau-de-bord.png', 540, "Compte activé : accès à l'espace de travail de l'employé."))

# ===================== 8. RBAC =====================
add('<h1>8. Contrôle d\'accès par rôles (RBAC)</h1>')
add("<p>L'autorisation repose sur un modèle de rôles : six rôles applicatifs (salarié, gestionnaire "
    "RH, gestionnaire de paie, responsable financier, administrateur applicatif, auditeur de "
    "sécurité) et trois rôles d'exploitation (administration, sauvegarde, investigation). À chaque "
    "rôle correspond un ensemble minimal de permissions, matérialisé par les seules procédures qu'il "
    "peut exécuter. La matrice de contrôle d'accès ci-dessous récapitule, domaine par domaine, les "
    "permissions associées à chacun des six rôles applicatifs (une marque ● signale la permission "
    "accordée).</p>")
add('<table>'
    '<tr><th>Domaine — permission</th><th>Salarié</th><th>RH</th><th>Finance</th><th>Paie</th><th>Admin</th><th>Auditeur</th></tr>'
    '<tr><td>Identité des employés (consulter, créer, modifier)</td><td></td><td>●</td><td></td><td></td><td></td><td></td></tr>'
    '<tr><td>Référentiels (départements, postes)</td><td></td><td>●</td><td></td><td></td><td></td><td></td></tr>'
    '<tr><td>Contrats (consulter, créer, clôturer)</td><td></td><td>●</td><td></td><td></td><td></td><td></td></tr>'
    '<tr><td>Affectations (consulter, créer, clôturer)</td><td></td><td>●</td><td></td><td></td><td></td><td></td></tr>'
    '<tr><td>Rémunération — consulter</td><td></td><td>●</td><td>●</td><td></td><td></td><td></td></tr>'
    '<tr><td>Rémunération — proposer</td><td></td><td>●</td><td></td><td></td><td></td><td></td></tr>'
    '<tr><td>Rémunération — décider</td><td></td><td></td><td>●</td><td></td><td></td><td></td></tr>'
    '<tr><td>Paie — consulter</td><td></td><td>●</td><td>●</td><td>●</td><td></td><td>●</td></tr>'
    '<tr><td>Paie — ouvrir une période, valider les éléments</td><td></td><td></td><td>●</td><td></td><td></td><td></td></tr>'
    '<tr><td>Paie — saisir les éléments variables</td><td></td><td>●</td><td></td><td></td><td></td><td></td></tr>'
    '<tr><td>Paie — calculer</td><td></td><td></td><td></td><td>●</td><td></td><td></td></tr>'
    '<tr><td>Bulletins — vérifier, publier, corriger</td><td></td><td></td><td></td><td>●</td><td></td><td></td></tr>'
    '<tr><td>Bulletins — approuver ou rejeter</td><td></td><td></td><td>●</td><td></td><td></td><td></td></tr>'
    '<tr><td>Bulletins — consulter les siens (publiés)</td><td>●</td><td></td><td></td><td></td><td></td><td></td></tr>'
    '<tr><td>Règlements — payer, décider d\'une récupération</td><td></td><td></td><td>●</td><td></td><td></td><td></td></tr>'
    '<tr><td>Règlements — demander, recevoir une récupération</td><td></td><td></td><td></td><td>●</td><td></td><td></td></tr>'
    '<tr><td>IAM — consulter les rôles</td><td></td><td></td><td></td><td></td><td>●</td><td>●</td></tr>'
    '<tr><td>IAM — attribuer, révoquer un rôle</td><td></td><td></td><td></td><td></td><td>●</td><td></td></tr>'
    '</table>')
add('<p class="cap">Matrice de contrôle d\'accès — permissions par domaine et par rôle applicatif. '
    'À ces six rôles s\'ajoutent trois rôles d\'exploitation (administration de la base, sauvegarde en '
    'lecture seule, investigation) hors du périmètre applicatif.</p>')
add("<p>Toutefois, un contrôle par rôle ne suffit pas à lui seul. Un salarié authentifié pourrait "
    "tenter d'accéder à la fiche d'un collègue en modifiant simplement l'identifiant dans l'URL — une "
    "attaque de type IDOR. SecurePayroll s'en défend par une <b>autorisation au niveau de l'objet</b>, "
    "vérifiée côté serveur à chaque requête : un utilisateur non habilité n'accède qu'à son propre "
    "identifiant d'employé. Cette protection repose sur une vérification de propriété, et non sur "
    "l'obscurcissement de l'identifiant ; encoder ou chiffrer l'identifiant relèverait de la sécurité "
    "par l'obscurité et ne remplacerait pas ce contrôle.</p>")
add(img(CAP / '04-idor-employes-bloque.jpg', 540,
    "Défense contre l'IDOR : un salarié qui force l'URL d'une autre fiche reçoit un refus (403), "
    "et la tentative est tracée."))
add("<p>En outre, toute tentative d'accès non autorisée est <b>refusée puis journalisée</b>, ce qui "
    "alimente la détection d'activité suspecte décrite à la section 13.</p>")

# ===================== 9. MOINDRE PRIVILÈGE =====================
add('<h1>9. Mise en œuvre du moindre privilège</h1>')
add("<p>Le moindre privilège a été poussé jusqu'au bout. Lors d'une phase dédiée, les droits directs "
    "du compte de service <code>svc_php</code> ont été <b>révoqués</b> puis remplacés par des rôles. "
    "Dès lors, le compte applicatif ne possède plus aucun privilège en propre : il ne détient que "
    "l'appartenance à des rôles, chacun limité à l'exécution des procédures de son périmètre. Aucun "
    "rôle ne dispose de droit d'écriture directe sur une table.</p>")
add("<p>Cette rigueur se vérifie objectivement. La matrice ci-dessous mesure, pour chaque rôle, le "
    "nombre de procédures qu'il peut exécuter sur les vingt-deux existantes et le nombre de tables "
    "qu'il peut lire directement sur les seize contrôlées. Elle confirme qu'aucun rôle n'excède son "
    "strict nécessaire et que le compte de service, à lui seul, ne détient <b>aucun</b> droit en "
    "propre.</p>")
add('<table>'
    '<tr><th>Rôle</th><th>Compte MySQL</th><th>Procédures exécutables</th><th>Tables lisibles directement</th></tr>'
    '<tr><td>Salarié</td><td><code>sp_employee</code></td><td>5 / 22</td><td>0 / 16</td></tr>'
    '<tr><td>Gestionnaire RH</td><td><code>sp_hr_manager</code></td><td>10 / 22</td><td>8 / 16</td></tr>'
    '<tr><td>Responsable financier</td><td><code>sp_finance_manager</code></td><td>8 / 22</td><td>5 / 16</td></tr>'
    '<tr><td>Gestionnaire de paie</td><td><code>sp_payroll_manager</code></td><td>6 / 22</td><td>0 / 16</td></tr>'
    '<tr><td>Administrateur applicatif</td><td><code>sp_application_administrator</code></td><td>3 / 22</td><td>0 / 16</td></tr>'
    '<tr><td>Auditeur de sécurité</td><td><code>sp_security_auditor</code></td><td>4 / 22</td><td>0 / 16</td></tr>'
    '<tr><td>Changement de mot de passe</td><td><code>sp_password</code></td><td>1 / 22</td><td>0 / 16</td></tr>'
    '<tr><td><b>Compte de service</b></td><td><code>svc_php</code></td><td><b>0</b> (aucun droit propre)</td><td><b>0 / 16</b></td></tr>'
    '</table>')
add('<p class="cap">Matrice de moindre privilège, vérifiée sur une instance réelle par '
    '<code>tests/privilege_matrix.py</code>. Les huit tables les plus sensibles — dont '
    '<code>employee_personal_data</code> et le journal d\'audit — ne sont lisibles directement par '
    '<b>aucun</b> rôle ; tout accès passe par une procédure au périmètre fixe.</p>')
add("<p>Il faut souligner que les rares lectures de tables autorisées (RH et finance) ne portent que "
    "sur des données de gestion non protégées — départements, postes, contrats, conditions salariales "
    "—, jamais sur les données chiffrées ni sur la piste d'audit. De surcroît, aucun privilège global "
    "dangereux (lecture de fichiers, arrêt du serveur, création de comptes) n'est accordé en dehors du "
    "compte d'administration et des comptes système de MySQL, ce que confirme l'audit de durcissement "
    "(section 15).</p>")

# ===================== 10. VULNÉRABILITÉ =====================
add('<h1>10. Analyse de vulnérabilité</h1>')
add("<p>Une analyse de vulnérabilité a été menée sur l'ensemble du système afin d'identifier, puis de "
    "corriger, les faiblesses classiques des applications adossées à une base : injection SQL, accès "
    "indirect à un objet d'autrui, privilèges excessifs, exposition de secrets et mauvaise "
    "configuration. Pour chacune, nous avons suivi une démarche en quatre temps — <b>cause racine, "
    "impact, mitigation, vérification</b> — conformément à l'exigence de ne jamais se contenter de "
    "montrer une faille sans l'expliquer.</p>")
add("<p>L'injection SQL, en particulier, a fait l'objet d'une étude approfondie, présentée à la "
    "section suivante avec sa démonstration « avant / après ». Conformément aux règles du projet, "
    "cette démonstration n'a visé que des composants créés par le groupe à cette fin, jamais "
    "l'application elle-même.</p>")

# ===================== 11. INJECTION SQL =====================
add('<h1>11. Investigation et remédiation de l\'injection SQL</h1>')
add("<p>L'injection SQL survient lorsqu'une entrée utilisateur est concaténée directement dans une "
    "requête : l'attaquant peut alors détourner la logique de la requête pour lire ou modifier des "
    "données qui ne lui sont pas destinées. Telle est la <b>cause racine</b>, et son <b>impact</b> "
    "est majeur puisqu'il peut aller jusqu'à l'extraction de la base entière.</p>")
add("<p>La <b>mitigation</b> retenue est double. D'une part, toutes les requêtes de l'application "
    "sont <b>paramétrées</b> : les valeurs fournies par l'utilisateur sont transmises séparément du "
    "texte de la requête, si bien qu'elles ne peuvent plus en altérer la structure. D'autre part, "
    "l'accès aux données passe par des <b>procédures stockées</b> au périmètre fixe, ce qui réduit "
    "encore la surface exploitable. La <b>vérification</b>, enfin, consiste à rejouer sur la version "
    "corrigée les charges d'attaque qui réussissaient sur la version vulnérable : toutes sont "
    "désormais neutralisées.</p>")
add("<p>Pour rendre la faille tangible sans jamais fragiliser l'application, une page « Mon accès » "
    "volontairement vulnérable a été construite dans un <b>laboratoire confiné</b>, servi sur un port "
    "séparé (8099), tandis que l'application réelle et corrigée reste servie sur son port habituel "
    "(8080). La démonstration « avant / après » rejoue trois charges d'attaque de nature croissante, "
    "chacune sur les deux versions.</p>")
add("<p>La première charge se borne à injecter une apostrophe dans le paramètre de filtrage. Sur la "
    "version vulnérable, elle suffit à <b>briser la requête</b> : le serveur renvoie une erreur de "
    "syntaxe SQL qui, au passage, dévoile la structure de la requête — une information précieuse pour "
    "l'attaquant. Sur la version corrigée, en revanche, l'entrée est validée en amont et poliment "
    "rejetée, sans qu'aucune erreur SQL ne filtre.</p>")
add(img(CR / 'sqli-erreur-before.png', 540,
    "Avant — l'injection d'une apostrophe provoque une erreur SQL (1064) révélant la requête."))
add(img(CR / 'sqli-erreur-after.png', 540,
    "Après — la même entrée est validée et rejetée, sans aucune fuite d'erreur."))
add("<p>La deuxième charge exploite une condition toujours vraie, <code>' OR '1'='1</code>, pour "
    "contourner le filtre. Sur la version vulnérable, le résultat est éloquent : l'attaquant "
    "obtient l'<b>intégralité des attributions de rôle</b>, bien au-delà des siennes. Sur la version "
    "corrigée, l'entrée est de nouveau rejetée et aucune donnée ne fuit.</p>")
add(img(CR / 'sqli-boolean-before.png', 540,
    "Avant — l'injection booléenne « OR '1'='1 » renvoie tous les rôles, filtrage contourné."))
add(img(CR / 'sqli-boolean-after.png', 540, "Après — la même charge est rejetée, aucune donnée exposée."))
add("<p>La troisième charge va jusqu'à l'exfiltration. Au moyen d'une clause <code>UNION SELECT "
    "login, password_hash … FROM accounts</code>, l'attaquant tente de lire la table des comptes. Sur "
    "la version vulnérable, il récupère les identifiants et les <b>empreintes de mots de passe</b> de "
    "tous les comptes ; fort heureusement, ces empreintes sont des hachages Argon2id (section 7), qui "
    "demeurent extrêmement coûteux à casser. Sur la version corrigée, l'attaque échoue entièrement.</p>")
add(img(CR / 'sqli-union-before.png', 560,
    "Avant — l'injection UNION exfiltre les identifiants et les empreintes Argon2id des comptes."))
add(img(CR / 'sqli-union-after.png', 540, "Après — la même charge UNION est neutralisée, aucune donnée extraite."))
add("<p>Ces trois paires établissent la <b>vérification</b> attendue : des attaques qui réussissaient "
    "toutes sur la version vulnérable sont systématiquement neutralisées sur la version corrigée, et "
    "ce grâce aux requêtes paramétrées et à la validation des entrées, non à un simple filtrage de "
    "surface.</p>")

# ===================== 12. PROTECTION DONNÉES =====================
add('<h1>12. Protection des données sensibles</h1>')
add("<p>Les données les plus sensibles — coordonnées bancaires (RIB), pièce d'identité (CIN) et "
    "numéro de sécurité sociale (CNSS) — sont <b>chiffrées au repos</b>. Le chiffrement emploie "
    "l'algorithme AES-256 en mode GCM, un mode <b>authentifié</b> : il garantit à la fois la "
    "confidentialité et l'intégrité de chaque valeur, de sorte que toute altération d'un octet "
    "chiffré, en base comme dans une sauvegarde, est détectée au déchiffrement. Ce choix se justifie "
    "précisément par cette capacité de détection, qu'un mode non authentifié n'offrirait pas. Il faut "
    "toutefois le dire clairement : chaque valeur est authentifiée isolément ; le format actuel "
    "(version, nonce, texte chiffré et tag) ne lie pas un texte chiffré à la ligne et à la colonne "
    "auxquelles il appartient. GCM seul ne détecterait donc pas un attaquant disposant d'un accès en "
    "écriture qui permuterait les valeurs chiffrées de deux employés ; lier chaque valeur à sa ligne "
    "et à sa colonne par des données associées est une amélioration recommandée (section 18).</p>")
add("<p>Chiffrer un champ interdit cependant de le rechercher par égalité. Pour concilier "
    "confidentialité et exploitabilité, chaque valeur sensible est accompagnée d'un <b>index "
    "aveugle</b> : une empreinte HMAC-SHA256 déterministe, calculée avec une clé dédiée, sur laquelle "
    "l'application effectue ses recherches sans jamais manipuler la valeur en clair. Cet index "
    "n'expose pas la valeur en clair ; étant déterministe, il révèle néanmoins que deux "
    "enregistrements partagent la même valeur, et comme des identifiants tels que la CIN ou la CNSS "
    "ont une entropie limitée, sa résistance à l'énumération repose entièrement sur le secret de la "
    "clé dédiée — c'est précisément pourquoi cette clé est conservée hors de la base. Quiconque "
    "obtiendrait cette clé pourrait recalculer l'empreinte de chaque valeur candidate ; la garder à "
    "part est donc essentiel.</p>")
add("<p>Toute la sûreté du dispositif tient enfin à la <b>gestion des clés</b>. Deux clés distinctes "
    "— l'une pour le chiffrement, l'autre pour l'index aveugle — sont conservées hors de la base et "
    "hors du dépôt de code, dans des fichiers aux permissions restreintes. Les séparer de la base est "
    "essentiel : comme le montre la section 14, un vol du dump sans ces clés ne livre que du chiffré "
    "illisible. Chaque consultation ou modification d'une donnée personnelle est de surcroît tracée.</p>")

# ===================== 13. JOURNALISATION =====================
add('<h1>13. Journalisation et supervision</h1>')
add("<p>Une table d'audit centrale constitue la source de vérité des activités sensibles. Chaque "
    "trace répond aux cinq questions attendues : <b>quand</b> l'événement s'est produit, <b>quoi</b>, "
    "<b>qui</b> en est l'auteur — à la fois le compte applicatif et le compte MySQL réel —, "
    "<b>quelle ressource</b> est concernée, et si l'action a <b>réussi ou échoué</b>. Contrairement à "
    "un simple fichier journal, cette piste est interrogeable en SQL, ce qui rend possibles la "
    "détection et l'investigation.</p>")
add("<p>Surtout, cette piste est <b>en ajout seul</b> : des déclencheurs BEFORE UPDATE et BEFORE "
    "DELETE refusent toute modification ou suppression d'une trace, et ils se déclenchent pour "
    "<b>tout le monde, y compris root</b> ; nul ne peut donc altérer ou retirer discrètement une ligne "
    "par une opération de données ordinaire. Une limite doit cependant être énoncée honnêtement : un "
    "administrateur de base dispose des droits de schéma et pourrait, en principe, supprimer les "
    "déclencheurs eux-mêmes avant d'agir. C'est précisément le risque <b>T-14 assumé</b> (section 6) ; "
    "il n'est pas laissé sans réponse mais reporté sur la <b>détection</b> et sur les mesures "
    "d'exploitation de la section 18 — alerte en temps réel sur les écritures hors application, "
    "rotation des identifiants et séparation des tâches. La garantie d'ajout seul est ainsi absolue "
    "face à tout compte non administrateur, et adossée à la détection face à l'administrateur. Par "
    "ailleurs, la piste est alimentée par deux sources complémentaires : l'application, qui journalise "
    "les intentions métier, et des déclencheurs sur les tables sensibles, qui enregistrent toute "
    "écriture <b>même réalisée hors application</b>. Cette seconde source est déterminante, car elle "
    "capte précisément l'accès direct d'un opérateur privilégié.</p>")
add(img(CAP / '01-audit-vue-ensemble.jpg', 580,
    "Page de supervision : signaux suspects (rafale d'échecs détectée) et événements récents."))
add("<p>La supervision s'appuie sur des signaux calculés automatiquement sur vingt-quatre heures : "
    "rafale d'échecs de connexion (révélatrice d'une force brute), refus d'accès répétés (tentative "
    "d'élévation) et lectures sensibles massives (exfiltration par un compte légitime). Une page "
    "réservée à l'auditeur présente ces signaux et permet de déplier chaque événement pour en lire le "
    "détail forensique complet.</p>")
add(img(CAP / '02-audit-detail-connexion-echouee.jpg', 580,
    "Détail forensique d'une connexion échouée : compte visé résolu, adresse source et contexte."))
add("<p>Enfin, la supervision respecte elle-même le moindre privilège. La page d'audit n'est "
    "accessible qu'au rôle auditeur ; un salarié qui tenterait de l'ouvrir reçoit un refus. La piste "
    "ne contient par ailleurs jamais de secret : ni mot de passe, ni identifiant saisi, ni donnée "
    "personnelle en clair, seulement des références et des indicateurs.</p>")
add(img(CAP / '03-audit-acces-refuse-salarie.jpg', 540,
    "Contrôle d'accès à la supervision : un salarié reçoit un refus (403) sur la page d'audit."))

# ===================== 14. SAUVEGARDE =====================
add('<h1>14. Sauvegarde et restauration</h1>')
add("<p>La disponibilité repose sur une stratégie de sauvegarde qui traite chaque risque "
    "explicitement. La sauvegarde est <b>logique</b> et produit un instantané cohérent sans bloquer "
    "l'application. Elle est réalisée par un <b>compte dédié en lecture seule</b>, incapable d'écrire "
    "ou de supprimer, ce qui prolonge le moindre privilège jusque dans l'exploitation. Le fichier "
    "produit est ensuite <b>chiffré au repos</b> en AES-256-GCM, et les clés — celle de la sauvegarde "
    "comme celles du chiffrement des données — sont <b>conservées séparément</b> du dump.</p>")
add("<p>Un point mérite d'être souligné, car il conditionne toute reprise réelle : un dump logique "
    "<b>ne contient pas les droits</b>. Lors d'une restauration, les tables et procédures sont "
    "recréées, mais les privilèges qui leur étaient attachés — stockés dans le schéma système de "
    "MySQL — disparaissent avec les objets. La reprise n'est donc complète qu'après <b>réapplication "
    "de la couche de droits</b> depuis l'inventaire administratif. Cette leçon est intégrée à la "
    "procédure.</p>")
add("<p>Conformément à l'exigence selon laquelle montrer qu'un fichier de sauvegarde existe ne suffit "
    "pas, un exercice de reprise complet a été rejoué. Après avoir relevé une vérité terrain, nous "
    "avons provoqué une perte contrôlée — suppression d'enregistrements critiques <b>et</b> "
    "suppression d'une table entière — puis restauré depuis la sauvegarde chiffrée. La vérification "
    "d'intégrité confirme alors que les comptes de lignes sont identiques, que les colonnes chiffrées "
    "sont restaurées à l'octet près, que les données sensibles restent déchiffrables et que la piste "
    "d'audit demeure intacte et toujours en ajout seul.</p>")
add('<pre>'
    'PASS Sauvegarde logique par backup_ops (role sp_backup, lecture seule)\n'
    'PASS Dump chiffre au repos (AES-256-GCM) : plus aucun texte clair\n'
    'PASS Sans la bonne cle de sauvegarde, la restauration est refusee (GCM)\n'
    'PASS Perte simulee : role_permissions videe ET table employee_personal_data supprimee\n'
    'PASS Comptes de lignes identiques a l\'avant-perte (28 tables)\n'
    'PASS Colonnes chiffrees restaurees octet pour octet\n'
    'PASS Donnees sensibles restaurees toujours dechiffrables (CIN identique)\n'
    'PASS Piste d\'audit toujours en ajout seul apres restauration\n'
    '19 controles de sauvegarde/restauration reussis.</pre>')
add(figcap("Sortie de l'exercice de reprise rejouable (extrait des dix-neuf contrôles)."))

# ===================== 15. DURCISSEMENT =====================
add('<h1>15. Durcissement de la base</h1>')
add("<p>Le durcissement n'a pas été une couche ajoutée en fin de parcours : le système est construit "
    "« sécurité d'abord » depuis l'origine. Cette phase a donc surtout consisté à <b>consolider et "
    "vérifier</b> l'existant, puis à ajouter un unique correctif résiduel. Le bilan ci-dessous "
    "compare un déploiement MySQL par défaut à l'état livré.</p>")
add('<table><tr><th>Zone</th><th>Avant (MySQL par défaut)</th><th>Après (livré)</th></tr>'
    '<tr><td>Comptes par défaut / anonymes</td><td>Anonymes possibles, base « test » ouverte</td>'
    '<td>Aucun anonyme, aucune base « test », root limité à localhost</td></tr>'
    '<tr><td>Privilèges excessifs</td><td>Compte applicatif large</td>'
    '<td>Moindre privilège par rôles ; svc_php sans aucun droit direct</td></tr>'
    '<tr><td>Comptes faibles</td><td>Hachage réversible</td><td>Argon2id et caching_sha2_password</td></tr>'
    '<tr><td>Exposition réseau</td><td>Écoute TCP, protocole X ouvert</td>'
    '<td>Socket-only (aucun port), protocole X désactivé</td></tr>'
    '<tr><td>Journalisation</td><td>Audit limité, altérable</td><td>Piste en ajout seul, journal privé</td></tr>'
    '<tr><td>Fonctions inutiles</td><td>LOAD DATA LOCAL, opérations fichiers</td>'
    '<td>local_infile désactivé, secure_file_priv à NULL</td></tr>'
    '<tr><td>Permissions de fichiers</td><td>Lisibles par le groupe</td><td>Instance et clés en droits restreints</td></tr>'
    '<tr><td>Protection des sauvegardes</td><td>Absente ou en clair</td><td>Chiffrée, compte dédié, clés à part</td></tr></table>')
add(figcap("Bilan avant / après durcissement (extrait)."))
add("<p>Chaque décision se justifie. Le mode <b>socket-only</b> supprime toute la surface d'attaque "
    "réseau ; la mise à <b>NULL</b> de <code>secure_file_priv</code> interdit les opérations serveur "
    "sur fichiers, même à l'administrateur, fermant un vecteur classique d'exfiltration ; l'absence "
    "de fichier de configuration externe rend la configuration reproductible et non modifiable à "
    "notre insu. Certaines mesures demeurent volontairement hors périmètre, car sans objet en "
    "socket-only : le chiffrement du transport réseau, par exemple, n'a pas lieu d'être en l'absence "
    "de trafic réseau. L'ensemble est vérifié automatiquement par un audit de durcissement couvrant "
    "les onze zones imposées.</p>")

# ===================== 16. INCIDENT =====================
add('<h1>16. Investigation d\'un incident de sécurité</h1>')
add("<p>Pour éprouver la capacité d'enquête du système, un incident a été simulé puis investigué. Le "
    "scénario reprend celui de l'énoncé : plusieurs tentatives d'accès non autorisées à des données "
    "sensibles, et un compte privilégié effectuant une opération inhabituelle. Fait important, "
    "l'incident est joué avec les <b>mécanismes réels</b> du système, de sorte que les preuves "
    "analysées sont authentiques.</p>")
add("<p>L'enquête s'appuie sur plusieurs sources, chacune consultée avec le rôle approprié et sans "
    "sur-privilège : le journal d'audit applicatif, lu par le rôle auditeur, et les enregistrements "
    "de la base, lus par un rôle d'investigation dépourvu d'accès aux données restreintes. La "
    "chronologie reconstituée ci-dessous résume le déroulement.</p>")
add('<table><tr><th>Instant</th><th>Événement</th><th>Résultat</th><th>Acteur</th><th>Ressource</th></tr>'
    '<tr><td>T0 (×6)</td><td>Échec de connexion</td><td>échec</td><td>non authentifié (IP externe)</td><td>compte RH</td></tr>'
    '<tr><td>T1 (×3)</td><td>Accès à une fiche d\'employé</td><td><b>refusé</b></td><td>compte salarié</td><td>fiches d\'autres employés</td></tr>'
    '<tr><td>T1 (×1)</td><td>Accès à la supervision</td><td><b>refusé</b></td><td>compte salarié</td><td>piste d\'audit</td></tr>'
    '<tr><td>T2</td><td>Octroi d\'un rôle (déclencheur)</td><td>succès</td><td><b>administrateur, hors application</b></td><td>attribution de rôle</td></tr>'
    '<tr><td>T3 (×2)</td><td>Effacement de la piste tenté</td><td><b>refusé (ajout seul)</b></td><td>administrateur</td><td>piste d\'audit</td></tr></table>')
add(figcap("Chronologie de l'incident reconstituée à partir de la piste d'audit."))
add("<p>À partir de ces seules preuves, l'enquête répond tour à tour aux sept questions imposées. "
    "<b>Quoi ?</b> Une attaque en trois temps : une force brute contre un compte RH — six échecs "
    "consécutifs, ce qui signifie que le compte a été bloqué dès le cinquième essai par la politique "
    "de verrouillage de la section 7 —, puis plusieurs tentatives d'accès non autorisées, à des "
    "fiches d'autres employés et à la supervision, toutes <b>refusées</b>, et enfin une escalade de "
    "privilèges réalisée non par l'application mais par un administrateur agissant <b>directement sur "
    "la base</b>, suivie d'une tentative d'effacement des traces, échouée. <b>Quand ?</b> L'instant "
    "est fixé à la microseconde en UTC par la piste. <b>Quels comptes ?</b> Le compte RH visé, le "
    "compte salarié à l'origine des lectures non autorisées, et surtout l'administrateur, reconnu par "
    "son identité MySQL réelle plutôt que par un acteur applicatif. L'adresse externe observée lors de "
    "la force brute est une adresse de documentation réservée par la RFC 5737, jamais une adresse "
    "réelle.</p>")
add("<p><b>Quelles ressources ?</b> Les fiches d'employés (accès tenté et refusé), la page de "
    "supervision (refusée) et la table des attributions de rôle (réellement modifiée). Quant aux "
    "<b>contrôles qui ont tenu ou failli</b> : l'autorisation par objet a tenu, puisque tout accès "
    "non autorisé a été refusé, et la piste en ajout seul a tenu, puisque la tentative de suppression "
    "a échoué ; par conception, l'écriture directe de l'administrateur n'est pas empêchée — le risque "
    "T-14 assumé — mais elle est intégralement tracée et attribuable. Les <b>preuves</b> reposent sur "
    "les lignes d'audit elles-mêmes — la rafale d'échecs, les refus, l'octroi de rôle attribué à "
    "l'administrateur par un déclencheur —, corroborées par l'enregistrement d'attribution de rôle. "
    "Les <b>actions correctives</b> en découlent directement : révoquer l'escalade, renouveler les "
    "identifiants de l'administrateur, mettre en place une alerte en temps réel sur toute écriture "
    "hors application, et restreindre l'accès opérateur à des fenêtres de maintenance. En définitive, "
    "l'incident démontre que l'attaque n'aboutit pas sur l'essentiel : les données sensibles ne sont "
    "pas lues, les traces ne peuvent être effacées, et l'unique action réussie est entièrement "
    "documentée.</p>")

# ===================== 17. BILAN FINAL =====================
add('<h1>17. Bilan final de sécurité</h1>')
add("<p>Au terme du projet, les neuf axes de sécurité imposés trouvent une réponse étayée. Le tableau "
    "suivant les récapitule en indiquant, pour chacun, le moyen mis en œuvre.</p>")
add('<table><tr><th>Axe</th><th>Réponse et moyen</th></tr>'
    '<tr><td>Authentification</td><td>Argon2id, verrouillage anti-force-brute, propriétaires verrouillés</td></tr>'
    '<tr><td>Autorisation</td><td>RBAC et autorisation au niveau de l\'objet (défense IDOR)</td></tr>'
    '<tr><td>Moindre privilège</td><td>svc_php sans droit direct, exécution par procédures au périmètre strict</td></tr>'
    '<tr><td>Sécurité applicative</td><td>Requêtes paramétrées et accès par procédures (injection neutralisée)</td></tr>'
    '<tr><td>Protection des données</td><td>Chiffrement AES-256-GCM au repos, index aveugle, clés séparées</td></tr>'
    '<tr><td>Audit et supervision</td><td>Piste centrale en ajout seul, détection automatique de signaux</td></tr>'
    '<tr><td>Sauvegarde et reprise</td><td>Sauvegarde chiffrée, restauration vérifiée</td></tr>'
    '<tr><td>Durcissement</td><td>Socket-only, services inutiles désactivés, comptes durcis</td></tr>'
    '<tr><td>Investigation</td><td>Chronologie et preuves reconstituées à moindre privilège</td></tr></table>')
add(figcap("Réponse aux neuf axes du bilan final."))
add("<p>Au-delà du tableau, la cohérence d'ensemble mérite d'être soulignée. Le système applique la "
    "<b>prévention</b> partout où elle est possible ; là où elle atteint ses limites, la "
    "<b>détection</b> et la <b>capacité de réponse</b> prennent le relais. Aucun contrôle "
    "n'agit isolément : chaque couche couvre les angles morts de la précédente, selon le principe de "
    "défense en profondeur qui structure l'ensemble des dix phases.</p>")
add("<p>Enfin, cette posture n'est pas déclarative mais <b>prouvée</b>. Cinq suites de contrôles "
    "automatisés, exécutables sur une instance jetable isolée, valident l'ensemble : cent cinquante "
    "et un contrôles pour l'installation complète, dix-neuf pour la sauvegarde et la restauration, "
    "vingt-huit pour le durcissement et seize pour l'investigation — deux cent quatorze contrôles au "
    "total —, complétés par la matrice de privilèges par rôle, tous rejouables à volonté.</p>")

# ===================== 18. RECOMMANDATIONS =====================
add('<h1>18. Recommandations</h1>')
add("<p>Bien que le système réponde aux objectifs fixés, plusieurs améliorations renforceraient encore "
    "sa posture dans un contexte d'exploitation réelle. En premier lieu, la gestion des clés "
    "gagnerait à être confiée à un module matériel dédié et assortie d'une rotation régulière. "
    "Dans le même esprit, chaque valeur chiffrée devrait être liée à sa ligne et à sa colonne par des "
    "données associées (AAD), afin que le déplacement d'un texte chiffré d'un enregistrement à un "
    "autre soit détecté plutôt que silencieusement accepté. "
    "Ensuite, la détection d'une écriture hors application, aujourd'hui constatable a posteriori, "
    "mériterait de déclencher une <b>alerte en temps réel</b>. De plus, l'accès de l'administrateur "
    "de base pourrait être restreint à des fenêtres de maintenance activées à la demande, avec une "
    "séparation des tâches empêchant un acteur unique de modifier seul les attributions de rôle. "
    "Enfin, les sauvegardes devraient être planifiées et dotées d'une politique de rétention, et le "
    "chiffrement du transport serait à activer si une exposition réseau devenait nécessaire.</p>")

# ===================== 19. CONCLUSION =====================
add('<h1>19. Conclusion</h1>')
add("<p>SecurePayroll démontre qu'une base de données peut être protégée de manière méthodique, "
    "cohérente et vérifiable. En plaçant la sécurité au centre dès la conception — moindre privilège, "
    "accès exclusivement par procédures, chiffrement des données sensibles, audit en ajout seul, "
    "sauvegarde chiffrée et surface d'attaque réduite — le système traite l'ensemble des axes exigés. "
    "Surtout, il assume honnêtement ses limites : parce qu'un administrateur conserve nécessairement "
    "des droits, la défense ne repose pas sur la seule prévention mais aussi sur une détection "
    "difficile à contourner et sur une capacité d'enquête éprouvée. Cette articulation entre prévention, "
    "détection et réponse constitue, à nos yeux, l'apport essentiel du projet.</p>")

# ===================== 20. RÉFÉRENCES =====================
add('<h1>20. Références</h1>')
add("<p>MySQL 8.4 Reference Manual (procédures DEFINER, rôles, privilèges, configuration). "
    "A. Biryukov et al., « Argon2 », RFC 9106. NIST SP 800-38D, « AES-GCM ». "
    "H. Krawczyk et al., « HMAC », RFC 2104. J. Arkko et al., « IPv4 Address Blocks Reserved for "
    "Documentation », RFC 5737. OWASP, « Top Ten » et « Cheat Sheets » (injection SQL, stockage des "
    "mots de passe). CIS, « MySQL Benchmark ».</p>")

# ===================== ANNEXE =====================
add('<h1>Annexe A — Diagrammes entité-association détaillés</h1>')
add("<p>Pour compléter le diagramme global de la section 4, les schémas suivants détaillent chacun des "
    "cinq domaines de la base. Ils font apparaître l'isolement de la table des données personnelles "
    "chiffrées, la piste d'audit en ajout seul et les relations qui portent l'intégrité "
    "référentielle.</p>")
add(img(ERD / 'ERD-01-IDENTITE-RBAC.png', 620, "Domaine identité et contrôle d'accès (comptes, rôles, attributions, audit)."))
add(img(ERD / 'ERD-02-ORGANISATION-RH.png', 620, "Domaine organisation RH (employés, données personnelles chiffrées, contrats, affectations)."))
add(img(ERD / 'ERD-03-REMUNERATION.png', 620, "Domaine rémunération (propositions, décisions, conditions salariales, historique)."))
add(img(ERD / 'ERD-04-PAIE.png', 620, "Domaine paie (périodes, éléments variables, calculs, bulletins et corrections)."))
add(img(ERD / 'ERD-05-REGLEMENTS.png', 620, "Domaine règlements (paiements, demandes et réceptions de récupération, grand livre)."))

add('<h1>Annexe B — Reproduire les preuves</h1>')
add("<p>Toutes les affirmations de ce rapport sont vérifiables. Les suites suivantes s'exécutent sur "
    "une instance jetable isolée, sans jamais toucher une base existante.</p>")
add('<table><tr><th>Suite</th><th>Portée</th><th>Contrôles</th></tr>'
    '<tr><td>tests/local-install.py</td><td>Installation, schéma, rôles, chiffrement, audit, détection</td><td>151</td></tr>'
    '<tr><td>tests/privilege_matrix.py</td><td>Matrice de moindre privilège par rôle</td><td>—</td></tr>'
    '<tr><td>tests/backup-recovery.py</td><td>Sauvegarde chiffrée et restauration vérifiée</td><td>19</td></tr>'
    '<tr><td>tests/hardening-audit.py</td><td>Durcissement, onze zones</td><td>28</td></tr>'
    '<tr><td>tests/incident-investigation.py</td><td>Investigation d\'incident</td><td>16</td></tr></table>')
add(figcap("Suites de preuves rejouables."))

# ---- RENDU ----
html = '<!DOCTYPE html><html><head><meta charset="utf-8">' + CSS + '</head><body>' + ''.join(H) + '</body></html>'
html_path = SP / 'rapport.html'
html_path.write_text(html, encoding='utf-8')
print('HTML écrit :', len(html), 'octets,', _fig, 'figures')

conv = subprocess.run(['soffice', '--headless', f'-env:UserInstallation=file://{SP}/profile',
                       '--convert-to', 'docx:MS Word 2007 XML', '--outdir', str(SP), str(html_path)],
                      capture_output=True, text=True)
print(conv.stdout.strip()[-200:]); print(conv.stderr.strip()[-200:] if conv.stderr else '')
produced = SP / 'rapport.docx'
if produced.exists():
    import zipfile
    z = zipfile.ZipFile(produced)
    media = [n for n in z.namelist() if 'media' in n]
    produced.replace(OUT)
    print('DOCX ->', OUT, '| images embarquées:', len(media))
else:
    print('ÉCHEC conversion'); sys.exit(1)
