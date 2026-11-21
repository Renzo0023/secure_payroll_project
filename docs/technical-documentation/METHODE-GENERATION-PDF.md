# Méthode reproductible de génération du PDF

Le PDF est composé localement avec Cairo, Pango et les polices DejaVu déjà installés. Aucun paquet n’est téléchargé. Le moteur conserve le texte Unicode sélectionnable, les tableaux paginés avec en-têtes répétés, les définitions SQL complètes, une couverture, un sommaire paginé et des planches vectorielles. Le Markdown reste la source documentaire de référence. Les liens vers les fichiers du dépôt sont présentés comme chemins de sources dans le PDF.

Les diagrammes SVG sont des vues documentaires dessinées à partir des composants et FK inventoriés ; les sources Mermaid complètes restent fournies. Les vues EA regroupent les entités par domaine et ne remplacent pas la liste exhaustive des 63 FK.

Le script ci-dessous ne lit que les chapitres et l’inventaire documentaire. Il écrit uniquement des livrables dans ce dossier. Il n’utilise ni PHP, ni MySQL, ni le réseau. Le premier passage mesure la pagination en mémoire, le second crée le PDF définitif et vérifie la stabilité du sommaire.

```python
from pathlib import Path
import cairo, ctypes as C, ctypes.util, re, json, io, math
O=Path('docs/technical-documentation')
D=json.loads((O/'INVENTAIRE-STRUCTUREL.json').read_text())
chapters=sorted(O.glob('[0-9][0-9]-*.md'))
W,H=595.276,841.89; M=42; CW=W-2*M; BOTTOM=H-45
GREEN=(.09,.36,.29); INK=(.10,.17,.17); GRAY=(.36,.43,.41)
LIGHT=(.93,.96,.94); LINE=(.82,.87,.84)
# Native Pango API avoids requiring the optional GI/Pycairo bridge.
pg=C.CDLL(ctypes.util.find_library('pango-1.0'))
pc=C.CDLL(ctypes.util.find_library('pangocairo-1.0'))
go=C.CDLL(ctypes.util.find_library('gobject-2.0'))
def api(lib,name,rest,args):
 f=getattr(lib,name); f.restype=rest; f.argtypes=args; return f
vp=C.c_void_p; it=C.c_int; st=C.c_char_p
create=api(pc,'pango_cairo_create_layout',vp,[vp])
show=api(pc,'pango_cairo_show_layout',None,[vp,vp])
fontnew=api(pg,'pango_font_description_from_string',vp,[st])
fontsz=api(pg,'pango_font_description_set_absolute_size',None,[vp,C.c_double])
setfont=api(pg,'pango_layout_set_font_description',None,[vp,vp])
fontfree=api(pg,'pango_font_description_free',None,[vp])
setwidth=api(pg,'pango_layout_set_width',None,[vp,it])
setwrap=api(pg,'pango_layout_set_wrap',None,[vp,it])
setspace=api(pg,'pango_layout_set_spacing',None,[vp,it])
settext=api(pg,'pango_layout_set_text',None,[vp,st,it])
getsize=api(pg,'pango_layout_get_size',None,[vp,C.POINTER(it),C.POINTER(it)])
unref=api(go,'g_object_unref',None,[vp])
def ctxptr(c):
 # Pycairo Context begins with PyObject_HEAD followed by cairo_t*.
 return vp.from_address(id(c)+2*C.sizeof(vp)).value
def plain(s):return re.sub(r'\[([^\]]+)\]\([^)]+\)',r'\1',s).replace('**','').replace('`','')
def measure(c,s,width,size=9.4,bold=False,mono=False):
 lo=create(ctxptr(c)); fn=fontnew((('DejaVu Sans Mono' if mono else 'DejaVu Sans')+(' Bold' if bold else '')).encode())
 fontsz(fn,size*1024);setfont(lo,fn);fontfree(fn)
 setwidth(lo,int(width*1024));setwrap(lo,2);setspace(lo,1900)
 settext(lo,s.encode('utf-8'),-1); a=it();b=it();getsize(lo,C.byref(a),C.byref(b));return lo,b.value/1024

def text(c,s,x,y,w,size=9.4,bold=False,color=INK,mono=False):
 lo,h=measure(c,s,w,size,bold,mono);c.set_source_rgb(*color);c.move_to(x,y);show(ctxptr(c),lo);unref(lo);return h

def rect(c,x,y,w,h,color,stroke=None):
 c.set_source_rgb(*color);c.rectangle(x,y,w,h);c.fill_preserve()
 if stroke:c.set_source_rgb(*stroke);c.set_line_width(.5);c.stroke()
 else:c.new_path()

class Diagram:
 def __init__(self,c):self.c=c
 def box(self,x,y,w,h,title,sub=''):
  rect(self.c,x,y,w,h,LIGHT,GREEN);text(self.c,title,x+9,y+8,w-18,10,True,GREEN)
  if sub:text(self.c,sub,x+9,y+32,w-18,8.1)
 def arrow(self,x1,y1,x2,y2,label=''):
  c=self.c;c.set_source_rgb(*GRAY);c.set_line_width(.8);c.move_to(x1,y1);c.line_to(x2,y2);c.stroke();a=math.atan2(y2-y1,x2-x1)
  c.move_to(x2,y2);c.line_to(x2-6*math.cos(a-.4),y2-6*math.sin(a-.4));c.line_to(x2-6*math.cos(a+.4),y2-6*math.sin(a+.4));c.close_path();c.fill()
  if label:text(c,label,(x1+x2)/2+4,(y1+y2)/2-10,170,7.5)

def architecture(g):
 g.box(115,8,280,58,'Navigateur FR / EN','HTML · formulaires GET / POST')
 g.arrow(255,66,255,98,'HTTP local + CSRF')
 g.box(85,98,340,68,'public/index.php → Controller::run','En-têtes · session · routage · AuthService')
 g.arrow(255,166,255,202)
 g.box(10,202,490,62,'Contrôleurs spécialisés et vues PHP','RH · Compensation · Paie / Settlement · IAM\nValidation ; présentation via h(), t(), Money')
 g.arrow(255,264,255,302)
 g.box(85,302,340,62,'Repositories PDO','Requêtes préparées · acteur issu de session')
 g.arrow(190,364,125,410);g.arrow(320,364,390,410)
 g.box(5,410,230,68,'SQL direct limité','Identité, RBAC, catalogues et rémunération selon GRANT')
 g.box(275,410,230,68,'SQL SECURITY DEFINER','Assertions RBAC · transactions · verrous')
 g.arrow(125,478,255,531);g.arrow(390,478,255,531)
 g.box(65,531,380,78,'MySQL InnoDB : 25 tables déclarées','PK / FK / UNIQUE / CHECK\n42 triggers · versions et événements immuables')
 text(g.c,'Le journal technique PHP est distinct des événements métier transactionnels SQL.',5,638,500,9)

def sequence(g):
 xs=[30,147,267,388,493];names=['Acteurs','PHP / PDO','Procédures','Sources SQL','Historique']
 for x,name in zip(xs,names):
  text(g.c,name,x-25,3,100,8.2,True,GREEN);g.c.set_source_rgb(*LINE);g.c.set_dash([3,3]);g.c.move_to(x,30);g.c.line_to(x,638);g.c.stroke();g.c.set_dash([])
 steps=[(0,1,'RH : proposition'),(1,2,'submit'),(2,4,'Demande + événement'),(0,2,'Finance : décision indépendante'),(2,3,'Salaire approuvé MAD'),(0,1,'Paie : calcul'),(1,2,'calculate'),(2,3,'BEGIN, verrou, build'),(2,4,'Version + snapshot + hash ; COMMIT'),(0,2,'Paie : verified ; recalcul'),(0,2,'Finance : approved ; fraîcheur'),(2,4,'Approbation unique'),(0,2,'Paie : published'),(0,1,'Employée : lire'),(1,2,'detail : identité'),(0,2,'Finance : règlement fictif'),(2,4,'Solde SQL ; référence unique')]
 for i,(a,b,label) in enumerate(steps):
  y=52+i*34;g.arrow(xs[a],y,xs[b],y);text(g.c,label,min(xs[a],xs[b])+3,y-15,abs(xs[a]-xs[b])-4,7.4)
 text(g.c,'POST avec CSRF ; contrôles SQL du rôle, de la permission et de l’identité.\nLes noms abrégés renvoient aux procédures complètes du chapitre 06.',0,653,510,9)

groups=[('Identité et RBAC',['employees','accounts','roles','permissions','role_permissions','role_assignments']),('Organisation RH',['employees','accounts','departments','positions','employee_assignments','employment_contracts']),('Rémunération',['employees','accounts','employment_contracts','compensation_requests','compensation_decisions','salary_conditions','compensation_history']),('Paie et bulletins',['employees','accounts','payroll_periods','payroll_inputs','payroll_input_decisions','payroll_calculations','payslip_events','payroll_approvals']),('Corrections et règlements',['employees','accounts','payroll_calculations','payslip_corrections','correction_events','recovery_requests','recovery_events','settlement_ledger'])]
def ergroup(g,entities):
 pos={t:(5+(i%2)*268,12+(i//2)*144) for i,t in enumerate(entities)};bw=235;bh=94
 pairs={(c,p) for c,cc,p,pc in D['foreign_keys'] if c in pos and p in pos and c!=p}
 for child,parent in sorted(pairs):
  x,y=pos[child];xx,yy=pos[parent]
  if x!=xx:g.arrow(x+(0 if x>xx else bw),y+bh/2,xx+(bw if x>xx else 0),yy+bh/2)
  else:g.arrow(x+bw/2,y+(0 if y>yy else bh),xx+bw/2,yy+(bh if y>yy else 0))
 for t,(x,y) in pos.items():
  keys=[n for n,decl in D['tables'][t]['columns'] if n=='id' or n.endswith('_id') or n in ['employee_number','code','month_start']]
  g.box(x,y,bw,bh,t,', '.join(keys[:7]))
 text(g.c,'Flèche : enfant → parent ; seules les FK déclarées sont représentées.\nLes attributs affichés sont une sélection de clés. Les 197 colonnes sont décrites\nau chapitre 13 ; les 63 FK et liens entre domaines figurent dans la liste suivante.',5,621,500,8.8)

def svg(name,fn):
 sf=cairo.SVGSurface(str(O/name),530,700);c=cairo.Context(sf);c.set_source_rgb(1,1,1);c.paint();fn(Diagram(c));sf.finish()

class Report:
 def __init__(self,target,toc=None):
  self.sf=cairo.PDFSurface(target,W,H);self.sf.set_metadata(cairo.PDF_METADATA_TITLE,'SecurePayroll — Documentation technique et fonctionnelle complète');self.sf.set_metadata(cairo.PDF_METADATA_AUTHOR,'Documentation académique — Database Security');self.sf.set_metadata(cairo.PDF_METADATA_SUBJECT,'Analyse des sources au 11 novembre 2026')
  self.c=cairo.Context(self.sf);self.page=1;self.y=M;self.section='SecurePayroll';self.starts={};self.toc=toc or {}
 def draw(self,s,x,y,w,size=9.4,bold=False,color=INK,mono=False):return text(self.c,s,x,y,w,size,bold,color,mono)
 def height(self,s,w,size=9.4,bold=False,mono=False):
  lo,h=measure(self.c,s,w,size,bold,mono);unref(lo);return h
 def footer(self):
  rect(self.c,M,H-34,CW,.5,LINE);self.draw('SecurePayroll · Database Security · 11/11/2026',M,H-27,CW-40,7,color=GRAY);self.draw(str(self.page),W-M-30,H-27,30,7,color=GRAY)
 def new(self):
  self.footer();self.sf.show_page();self.page+=1;self.y=58;self.draw('SECUREPAYROLL',M,25,170,7.5,True,GREEN);self.draw(self.section,W/2,25,W/2-M,7,color=GRAY);rect(self.c,M,43,CW,.5,LINE)
 def ensure(self,h):
  if self.y+h>BOTTOM:self.new()
 def para(self,s,size=9.4,bold=False,color=INK,gap=7,mono=False):
  h=self.height(s,CW,size,bold,mono)
  if h>BOTTOM-70:
   pieces=re.split(r'(?<=\.)\s+',s)
   if len(pieces)<2:pieces=[s[i:i+500] for i in range(0,len(s),500)]
   for t in pieces:self.para(t,size,bold,color,gap,mono)
   return
  self.ensure(h);self.draw(s,M,self.y,CW,size,bold,color,mono);self.y+=h+gap
 def heading(self,s,level=2):
  self.ensure(65 if level<3 else 45);self.y+=10 if level>1 else 0;self.para(plain(s),{1:21,2:13.3,3:10.6}.get(level,10),True,GREEN,9)
 def cover(self):
  rect(self.c,0,0,W,H,(.96,.975,.96));rect(self.c,0,0,19,H,GREEN);rect(self.c,M,75,65,5,GREEN)
  self.draw('DATABASE SECURITY',M,100,CW,10,True,GREEN);self.draw('SecurePayroll',M,157,CW,39,True,GREEN)
  self.draw('Documentation technique\net fonctionnelle complète',M,225,CW,25,True)
  self.draw('Secure Employee & Payroll Management System',M,320,CW,12,color=GRAY)
  rect(self.c,M,385,CW,125,(1,1,1),LINE)
  self.draw('25 tables     24 procédures     42 triggers',M+20,407,CW-40,14,True,GREEN)
  self.draw('31 permissions · 6 rôles · FR / EN · MAD',M+20,445,CW-40,10)
  self.draw('Analyse des sources réelles et des preuves historiques.\nÉtat actuel de MySQL : Non vérifié dans cette mission.\nAucune modification de l’application ou de la base.',M,555,CW,11,color=GRAY)
  self.draw('11 novembre 2026',M,710,CW,12,True,GREEN);self.draw('Ubuntu / VMware · PHP & PDO · MySQL · HTML / CSS / JavaScript',M,742,CW,8.4,color=GRAY);self.new()
 def contents(self):
  self.section='Table des matières';self.heading('Table des matières',1);self.para('Les chapitres incluent les définitions SQL et le dictionnaire détaillé pour permettre la vérification des contrôles.',9.5,color=GRAY,gap=20)
  for p in chapters:
   title=plain(p.read_text().splitlines()[0][2:]);self.ensure(30);h=self.draw(title,M,self.y,CW-35,10.2,True);self.draw(str(self.toc.get(p.name,'—')),W-M-30,self.y,30,10.2,True,GREEN);self.y+=max(h,15)+13
  self.y+=10;self.para('Planches graphiques et relations MySQL',10.2,True,GREEN);self.para('Architecture, séquence de paie, entités par domaine et toutes les clés étrangères déclarées.',9,color=GRAY)
 def table(self,rows):
  n=max(map(len,rows));rows=[r+['']*(n-len(r)) for r in rows];head=rows[0]
  vals=[max(5,min(25,math.sqrt(sum(min(len(plain(r[j])),100) for r in rows)/len(rows)+4)*2.7)) for j in range(n)]
  widths=[CW*v/sum(vals) for v in vals];size=8.1 if n<=5 else 7.2
  def row(r,header=False,index=0):
   h=max(self.height(plain(v),widths[j]-10,size,header) for j,v in enumerate(r))+13
   if h>BOTTOM-70:raise RuntimeError('Table row too tall: '+str(h))
   if self.y+h>BOTTOM:
    self.new()
    if not header:row(head,True)
   x=M
   for j,v in enumerate(r):
    rect(self.c,x,self.y,widths[j],h,GREEN if header else (LIGHT if index%2==0 else (1,1,1)),LINE)
    self.draw(plain(v),x+5,self.y+6,widths[j]-10,size,header,(1,1,1) if header else INK);x+=widths[j]
   self.y+=h
  row(head,True)
  for i,r in enumerate(rows[1:]):row(r,False,i)
  self.y+=11
 def code(self,lines):
  for ln in lines:
   h=self.height(ln or ' ',CW-16,7.5,mono=True)+3;self.ensure(h);rect(self.c,M,self.y,CW,h,(.96,.97,.965));self.draw(ln or ' ',M+8,self.y+1,CW-16,7.5,color=(.20,.28,.25),mono=True);self.y+=h
  self.y+=10
 def markdown(self,s):
  lines=s.splitlines();i=0
  while i<len(lines):
   ln=lines[i]
   if not ln.strip():i+=1;continue
   if ln.startswith('```'):
    lang=ln[3:].strip();block=[];i+=1
    while i<len(lines) and not lines[i].startswith('```'):block.append(lines[i]);i+=1
    if lang=='mermaid':self.para('Diagramme : voir les planches graphiques en annexe ; source Mermaid éditable conservée séparément.',9,color=GRAY)
    else:self.code(block)
    i+=1;continue
   if ln.startswith('|'):
    rows=[]
    while i<len(lines) and lines[i].startswith('|'):
     cells=lines[i].strip().strip('|').split('|')
     if not all(re.fullmatch(r'\s*:?-+:?\s*',v) for v in cells):rows.append([v.strip() for v in cells])
     i+=1
    self.table(rows);continue
   mt=re.match(r'^(#{1,6})\s+(.+)',ln)
   if mt:self.heading(mt[2],len(mt[1]));i+=1;continue
   if ln.startswith('> '):self.para(plain(ln[2:]),8.5,color=GRAY,gap=12);i+=1;continue
   if re.match(r'^(?:[-*] |\d+\. )',ln):self.para('• '+plain(re.sub(r'^(?:[-*]|\d+\.)\s+','',ln)),9.2,gap=5);i+=1;continue
   par=[ln];i+=1
   while i<len(lines) and lines[i].strip() and not re.match(r'^(#|\||```|>|[-*] |\d+\. )',lines[i]):par.append(lines[i]);i+=1
   self.para(plain(' '.join(par)))
 def graphic(self,title,fn):
  self.section='Planches graphiques';self.new();self.heading(title,1);self.c.save();self.c.translate(M,self.y+3);fn(Diagram(self.c));self.c.restore();self.y=760
 def finish(self):self.footer();self.sf.finish()

def build(target,toc=None):
 r=Report(target,toc);r.cover();r.contents()
 for p in chapters:
  r.section=plain(p.read_text().splitlines()[0][2:]);r.new();r.starts[p.name]=r.page
  try:r.sf.add_outline(cairo.PDF_OUTLINE_ROOT,r.section,f'page={r.page}',cairo.PDF_OUTLINE_FLAG_OPEN)
  except (AttributeError,TypeError):pass
  r.markdown(p.read_text())
 r.graphic('Architecture de SecurePayroll',architecture);r.graphic('Séquence du traitement d’une paie',sequence)
 for title,entities in groups:r.graphic('Entités — '+title,lambda g,e=entities:ergroup(g,e))
 r.new();r.heading('Relations MySQL : toutes les FK déclarées',1);r.para('Inventaire issu des CREATE TABLE ; les références composées sont présentées comme une relation unique.',9,color=GRAY)
 r.table([['Table enfant','Colonne(s)','Table parent','Colonne(s) référencée(s)']]+D['foreign_keys'])
 pages=r.page;r.finish();return r.starts,pages
svg('DIAGRAMME-ARCHITECTURE.svg',architecture);svg('DIAGRAMME-SEQUENCE-PAIE.svg',sequence)
for i,(title,entities) in enumerate(groups,1):svg(f'DIAGRAMME-EA-{i:02d}.svg',lambda g,e=entities:ergroup(g,e))
buf=io.BytesIO();toc,pages=build(buf)
actual,pages=build(str(O/'RAPPORT_COMPLET_SECUREPAYROLL.pdf'),toc)
if actual!=toc:raise RuntimeError('Pagination non stable')
(O/'PAGINATION-PDF.json').write_text(json.dumps({'pages':pages,'chapitres':toc,'moteur':'Cairo / Pango / DejaVu'},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'pages':pages,'octets':(O/'RAPPORT_COMPLET_SECUREPAYROLL.pdf').stat().st_size,'sommaire':toc},ensure_ascii=False))
```
