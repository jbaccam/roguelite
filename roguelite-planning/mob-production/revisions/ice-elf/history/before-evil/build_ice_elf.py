"""Ice Elf revision: tailored silhouette and individually constructed equipment.
Runs in a separate Blender process. Never replaces the rejected originals.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
# Reuse only geometry primitives and export utilities, not the rejected character.
source=(ROOT/'build_mobs.py').read_text()
sys.argv=['build','--','ice-elf']
exec(compile(source[:source.index('def humanoid():')],str(ROOT/'build_mobs.py'),'exec'))
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'revisions'/'ice-elf';OUT.mkdir(parents=True,exist_ok=True)
import shutil
shutil.copyfile(ROOT/'ice-elf'/'Reference.png',OUT/'Reference.png')

def smooth(o):
    for f in o.data.polygons:f.use_smooth=True
    return o

def shaped(g,levels,mat):
    o=loft(g,levels,mat)
    # Preserve broad planes while beveling silhouette breaks.
    bpy.context.view_layer.objects.active=o
    m=o.modifiers.new('Tailored edges','BEVEL');m.width=.025;m.segments=2
    bpy.ops.object.modifier_apply(modifier=m.name)
    return o

def strand(g,points,widths,mat='white'):
    return smooth(tube(g,points,[(w,w*.56) for w in widths],mat,8))

def seam(g,pts,mat='steel',r=.025):return tube(g,pts,r,mat,6)

def buckle(g,x,y,z,w=.32,h=.25):
    for xx in [-w/2,w/2]:box(g,(x+xx,y,z),(.055,.08,h+.04),'steel',.012)
    for zz in [-h/2,h/2]:box(g,(x,y,z+zz),(w,.08,.055),'steel',.012)
    box(g,(x,y-.03,z),(.16,.045,.025),'steel',.005)

bone('LowerTorso',(0,0,2.95));bone('UpperTorso',(0,0,3.55),'LowerTorso')
bone('Head',(0,0,5.2),'UpperTorso')
for s,side in [(-1,'Left'),(1,'Right')]:
    bone(side+'UpperLeg',(s*.53,0,2.88),'LowerTorso')
    bone(side+'LowerLeg',(s*.55,0,1.65),side+'UpperLeg')
    bone(side+'Foot',(s*.55,-.05,.53),side+'LowerLeg')
    bone(side+'UpperArm',(s*1.15,0,4.9),'UpperTorso')
    bone(side+'LowerArm',(s*1.38,-.02,3.97),side+'UpperArm')
    bone(side+'Hand',(s*1.49,-.06,3.17),side+'LowerArm')

# Pelvis and quilted trousers taper through the knees, avoiding tube limbs.
shaped('LowerTorso',[(0,0,2.64,1.46,.85),(0,0,3.05,1.58,.91),(0,0,3.42,1.42,.88)],'blue')
for s,side in [(-1,'Left'),(1,'Right')]:
    x=s*.55
    shaped(side+'UpperLeg',[(x,0,1.53,.53,.60),(x,-.045,1.83,.61,.68),(x,0,2.36,.71,.75),(x,0,2.89,.72,.76)],'blue')
    shaped(side+'LowerLeg',[(x,0,.57,.49,.52),(x,.025,1.07,.59,.65),(x,0,1.66,.55,.62)],'blue')
    # Knee reinforcement, sparse diagonal trouser folds.
    plate(side+'LowerLeg',[(x-.23,-.35,1.77),(x+.23,-.35,1.77),(x+.20,-.37,1.49),(x-.19,-.37,1.44)],.055,'charcoal')
    for z in [2.22,2.40]:seam(side+'UpperLeg',[(x-.24,-.38,z+.055),(x,-.40,z),(x+.22,-.38,z+.02)],'blue',.035)
    # Full boot body, welt, toe, shaft and two fastening straps.
    shaped(side+'Foot',[(x,-.19,.07,.77,1.21),(x,-.20,.18,.82,1.27),(x,-.21,.27,.80,1.25)],'dark')
    shaped(side+'Foot',[(x,-.21,.23,.77,1.2),(x,-.24,.40,.76,1.16),(x,-.16,.59,.69,.94),(x,.01,.74,.60,.63)],'brown')
    shaped(side+'LowerLeg',[(x,0,.51,.62,.67),(x,.025,.86,.64,.67),(x,.035,1.26,.75,.75),(x,.035,1.42,.73,.72)],'brown')
    plate(side+'Foot',[(x-.32,-.795,.26),(x+.32,-.795,.26),(x+.29,-.75,.43),(x+.19,-.63,.52),(x-.19,-.63,.52),(x-.29,-.75,.43)],.09,'charcoal')
    for z in [.78,1.12]:
        shaped(side+'LowerLeg',[(x,.01,z-.065,.70,.76),(x,.01,z+.065,.70,.76)],'charcoal')
        buckle(side+'LowerLeg',x+s*.16,-.39,z,.19,.16)
    for k in range(13):
        a=k*math.tau/13
        strand(side+'LowerLeg',[(x+.33*math.cos(a),.035+.32*math.sin(a),1.46),(x+.38*math.cos(a),.035+.37*math.sin(a),1.34),(x+.35*math.cos(a),.035+.34*math.sin(a),1.22+random.uniform(-.035,.035))],[.13,.115,.035],'fur')

# Fitted coat with broad chest, pinched waist, overlapping skirt panels.
shaped('UpperTorso',[(0,0,3.38,1.46,.94),(0,0,3.68,1.56,1.00),(0,.02,4.14,1.81,1.11),(0,.02,4.58,2.02,1.10),(0,.025,4.90,1.91,.94),(0,.03,5.05,1.48,.79)],'blue')
for s in [-1,1]:
    # Front split tails are attached to their leg to clear the stride.
    side='Left' if s<0 else 'Right';g=side+'UpperLeg'
    p=[(s*.075,-.50,3.37),(s*.75,-.40,3.37),(s*.88,-.40,2.39),(s*.69,-.52,2.24),(s*.12,-.62,2.40)]
    plate(g,p,.10,'blue')
    seam(g,[p[0],p[4],p[3],p[2]],'steel',.040)
    p=[(s*.07,.47,3.37),(s*.72,.40,3.37),(s*.85,.47,2.40),(s*.12,.63,2.36)]
    plate(g,p,.10,'blue');seam(g,[p[0],p[3],p[2]],'steel',.03)
    seam('UpperTorso',[(s*.69,-.40,3.51),(s*.78,-.48,3.95),(s*.81,-.45,4.48)],'blue',.027)
    # Fitted sleeve with elbow panel and a cuff, hands with curled fingers.
    arm=side+'UpperArm';low=side+'LowerArm';hand=side+'Hand'
    shaped(arm,[(s*1.37,0,3.88,.51,.61),(s*1.32,0,4.19,.61,.72),(s*1.21,0,4.61,.77,.86),(s*1.10,0,4.93,.69,.80)],'blue')
    shaped(low,[(s*1.49,-.035,3.13,.48,.55),(s*1.46,-.025,3.44,.57,.64),(s*1.39,0,3.94,.58,.63)],'blue')
    shaped(low,[(s*1.39,0,3.83,.62,.67),(s*1.38,0,3.98,.62,.67)],'charcoal')
    seam(arm,[(s*1.52,-.29,4.09),(s*1.55,-.32,4.47),(s*1.46,-.28,4.74)],'steel',.024)
    for k in range(12):
        a=k*math.tau/12
        strand(low,[(s*1.49+.24*math.cos(a),-.04+.25*math.sin(a),3.34),(s*1.50+.30*math.cos(a),-.04+.30*math.sin(a),3.20),(s*1.51+.25*math.cos(a),-.04+.25*math.sin(a),3.07)],[.105,.105,.025],'fur')
    shaped(hand,[(s*1.51,-.05,2.72,.37,.37),(s*1.51,-.07,2.88,.46,.44),(s*1.50,-.05,3.15,.40,.39)],'skin')
    for k in range(4):
        xx=s*1.51+(k-1.5)*.105
        smooth(tube(hand,[(xx,-.13,2.91),(xx,-.22,2.77),(xx,-.16,2.66),(xx,-.07,2.72)],[.066,.067,.063,.049],'skin',8))
    smooth(tube(hand,[(s*1.31,-.08,3.03),(s*1.23,-.19,2.94),(s*1.28,-.28,2.84)],[.095,.090,.065],'skin',8))

# Belt has depth, keeper, hollow buckle, perforated hanging end and pouch.
shaped('LowerTorso',[(0,-.005,3.24,1.63,1.04),(0,-.005,3.48,1.63,1.04)],'brown')
buckle('LowerTorso',0,-.57,3.36,.39,.29)
box('LowerTorso',(.44,-.57,3.36),(.10,.09,.31),'charcoal',.02)
plate('LowerTorso',[(.46,-.54,3.36),(.68,-.51,3.36),(.74,-.62,2.90),(.61,-.65,2.81),(.48,-.64,2.91)],.065,'brown')
for z in [2.97,3.08,3.19]:ell('LowerTorso',(.59,-.662,z),(.023,.011,.025),'dark',8,4)
box('LowerTorso',(-.83,.10,3.16),(.32,.47,.50),'brown',.065)
box('LowerTorso',(-.85,.04,3.39),(.35,.49,.13),'charcoal',.03)

# Neck and high standing collar frame the face.
shaped('Head',[(0,0,4.99,.57,.56),(0,0,5.43,.66,.61)],'skin')
shaped('UpperTorso',[(0,.045,4.84,.92,.78),(0,.045,5.28,.96,.80)],'charcoal')
# V collar; overlapping swept locks have volume and varying length.
for s in [-1,1]:
    pts=[(s*.13,-.61,4.59),(s*.41,-.57,4.77),(s*.68,-.46,4.95),(s*.89,-.24,5.00)]
    tube('UpperTorso',pts,[.16,.19,.22,.23],'fur',10)
    for k in range(10):
        u=k/9;x=s*(.16+.79*u);z=4.69+.39*math.sin(u*1.57);y=-.56+.35*u*u
        strand('UpperTorso',[(x,y,z+.09),(x+s*.06,y-.075,z-.07),(x+s*.10,y-.03,z-.22-random.random()*.05)],[.14,.13,.018],'fur')
for k in range(11):
    a=k*math.pi/10
    strand('UpperTorso',[(.87*math.cos(a),.40*math.sin(a),5.04),(.99*math.cos(a),.49*math.sin(a),4.92),(1.00*math.cos(a),.47*math.sin(a),4.76)],[.16,.15,.025],'fur')
for z in [4.21,4.45]:
    for s in [-1,1]:seam('UpperTorso',[(s*.27,-.574,z+.06),(-s*.12,-.59,z-.07)],'steel',.046)
    for s in [-1,1]:ell('UpperTorso',(s*.30,-.573,z+.06),(.058,.025,.058),'steel',10,6)

# Angular cheek/jaw silhouette, shaped nose, small inset eyes and lids.
shaped('Head',[(0,-.025,5.31,.69,.71),(0,-.035,5.44,1.05,.89),(0,-.01,5.75,1.40,1.04),(0,.015,6.16,1.45,1.06),(0,.035,6.43,1.22,.98),(0,.04,6.53,.84,.72)],'skin')
for s in [-1,1]:
    # Ears constructed with inner cartilage set into an outer rim.
    p=[(s*.64,-.025,6.13),(s*1.18,.055,6.35),(s*1.05,-.02,5.91),(s*.70,-.10,5.74)]
    plate('Head',p,.16,'skin')
    plate('Head',[(s*.75,-.046,6.11),(s*1.06,.017,6.24),(s*.96,-.057,5.98),(s*.76,-.117,5.86)],.032,'blue')
    x=s*.32
    p=[(x-s*.23,-.541,6.04),(x+s*.22,-.53,6.08),(x+s*.20,-.552,5.90),(x-s*.17,-.556,5.89)]
    plate('Head',p,.025,'charcoal')
    p=[(x-s*.17,-.565,6.005),(x+s*.165,-.557,6.035),(x+s*.145,-.572,5.936),(x-s*.145,-.573,5.927)]
    plate('Head',p,.015,'white')
    ell('Head',(x+s*.025,-.589,5.981),(.064,.018,.064),'blue',12,6)
    ell('Head',(x+s*.025,-.606,5.98),(.029,.008,.042),'dark',10,6)
    seam('Head',[(x-s*.22,-.575,6.14),(x,-.590,6.17),(x+s*.24,-.552,6.23)],'charcoal',.043)
    seam('Head',[(x-s*.17,-.56,5.84),(x+s*.20,-.533,5.88)],'skin',.028)
mesh('Head',[(-.10,-.537,6.04),(.10,-.537,6.04),(-.12,-.55,5.78),(.12,-.55,5.78),(0,-.72,5.81),(0,-.59,5.73)],[(0,1,4),(0,4,2),(1,3,4),(2,4,5),(4,3,5),(0,2,5,3,1)],'skin',.014)
seam('Head',[(-.22,-.507,5.59),(0,-.535,5.57),(.22,-.505,5.63)],'blue',.019)

# Hair cap and layered swept locks follow the cranium, instead of isolated spikes.
smooth(ell('Head',(0,.065,6.27),(.745,.57,.45),'white',24,12))
for k in range(10):
    a=-.22+k*3.65/9;x=.62*math.cos(a);y=.065+.46*math.sin(a)
    strand('Head',[(x*.45,.08+y*.45,6.59),(x,y,6.39),(x*1.12,y*1.06,6.16),(x*1.09,y*1.03,5.89+random.uniform(-.10,.10))],[.14,.23,.15,.007])
# Asymmetric broad sweep: curved locks overlap, with staggered tapered ends.
for pts,widths in [
    ([(-.52,.22,6.49),(-.43,-.12,6.72),(-.10,-.43,6.69),(.30,-.58,6.42),(.53,-.58,6.19)],[.12,.24,.26,.17,.005]),
    ([(-.68,.07,6.35),(-.60,-.21,6.57),(-.32,-.51,6.52),(.03,-.62,6.29),(.15,-.60,6.11)],[.12,.24,.24,.12,.005]),
    ([(-.40,.44,6.42),(-.14,.13,6.72),(.23,-.16,6.70),(.62,-.39,6.49),(.79,-.38,6.29)],[.13,.24,.23,.15,.005]),
    ([(-.16,.50,6.40),(.16,.37,6.62),(.53,.08,6.63),(.76,-.12,6.43),(.87,-.08,6.21)],[.12,.25,.22,.12,.005]),
    ([(-.68,.16,6.30),(-.74,-.08,6.44),(-.69,-.39,6.31),(-.48,-.59,6.16),(-.37,-.59,6.06)],[.13,.19,.17,.09,.005]),
]:strand('Head',pts,widths)

# Small faceted casting icicle: a readable signature, separate from the fingers.
tube('RightHand',[(1.51,-.09,2.72),(1.51,-.09,3.15),(1.51,-.09,3.52),(1.51,-.09,3.97)],[.075,.11,.10,.003],'cyan',5)

# Review + rig/export. Rendering remains an actual Blender mesh render.
ATLAS_SOURCE=ROOT/'revisions'/'Materials.png'
exec(compile((ROOT/'deliver.py').read_text(),str(ROOT/'deliver.py'),'exec'))
