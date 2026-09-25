"""Second-pass geometry, anatomy, equipment and proportion corrections.
Preserves first-pass assets. Exports to revisions/<mob> for separate review.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
src=(ROOT/'build_mobs.py').read_text()
exec(compile(src[:src.index("if ID in ['crab','hermit-crab','rock-throwing-crab','scorpion']:crustacean()")],str(ROOT/'build_mobs.py'),'exec'))
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'revisions'/ID;OUT.mkdir(parents=True,exist_ok=True)
import shutil
shutil.copyfile(ROOT/ID/'Reference.png',OUT/'Reference.png')

def smooth(o):
    for p in o.data.polygons:p.use_smooth=True
    return o
def line(g,p,r=.025,mat='bone'):return tube(g,p,r,mat,6)
def remove(g,indices=None):
    old=parts.get(g,[])
    for i,o in reversed(list(enumerate(old))):
        if indices is None or i in indices:
            old.pop(i);bpy.data.objects.remove(o,do_unlink=True)
def move_vertices(g,fn):
    for o in parts.get(g,[]):
        for v in o.data.vertices:v.co=o.matrix_world.inverted()@Vector(fn(o.matrix_world@v.co))
def lock(g,p,delta,width,mat):
    p=Vector(p);d=Vector(delta)
    return smooth(tube(g,[p,p+d*.30+Vector((0,-.05,.025)),p+d*.70,p+d],[(width,width*.40),(width*.93,width*.38),(width*.50,width*.22),(.006,.006)],mat,8))
def ring(g,x,y,z,w,d,h,mat):return loft(g,[(x,y,z-h/2,w,d),(x,y,z+h/2,w,d)],mat)
def buckle(g,x,y,z,w=.25,h=.21):
    for xx in [-w/2,w/2]:box(g,(x+xx,y,z),(.047,.08,h),'steel',.01)
    for zz in [-h/2,h/2]:box(g,(x,y,z+zz),(w,.08,.047),'steel',.01)
def rivet(g,p,mat='steel',r=.04):ell(g,p,(r,r*.5,r),mat,8,6)

def shell_details():
    crustacean()
    mat='sand' if ID=='scorpion' else 'teal' if ID=='rock-throwing-crab' else 'coral'
    if ID=='scorpion':
        remove('Body',[0,1])
        ell('Body',(0,-.38,1.23),(.84,.59,.31),'russet',20,10)
        ell('Body',(0,-.38,1.43),(.80,.53,.24),'sand',20,10)
        for j in range(5):
            ell('Body',(0,.04+j*.23,1.31),(.80-j*.082,.28,.29),'russet',16,8)
    # Reduce cartoon eyes and stalk height; dark bead eyes remain recessed in sockets.
    if ID!='scorpion':
        for o in parts['Body']:
            if o.data.materials[0].name in ['dark','white']:
                o.scale*=.64;o.location.z-=.16
        # Surface grooves delineate branchial and gastric carapace regions.
        for s in [-1,1]:
            for j in range(3):
                y=-.15+j*.28
                line('Body',[(s*.32,y,1.775),(s*.59,y+.04,1.745),(s*.87,y+.02,1.68)],.027,'russet' if mat=='coral' else 'blue')
            for j in range(4):
                a=.12+j*.39;p=(s*(1.13+.05*math.sin(a)),-.40+j*.28,1.47)
                lock('Body',p,(s*.19,.02,.025),.10,mat)
        line('Body',[(-.24,-.78,1.66),(-.16,-.54,1.76),(0,-.38,1.80),(.16,-.54,1.76),(.24,-.78,1.66)],.026,'russet' if mat=='coral' else 'blue')
    for s in [-1,1]:
        side=sides(s)
        for i in range(3 if ID=='hermit-crab' else 4):
            g=f'{side}Leg{i}Lower';p=Vector(bones[g]['head'])
            smooth(ell(g,p,(.16,.15,.16),'russet' if mat!='teal' else 'blue',12,8))
            # Tarsal joint at mid-leg and chitin edge accent.
            line(g,[p+Vector((s*.015,-.13,-.03)),p+Vector((s*.18,-.14,-.35)),p+Vector((s*.25,-.10,-.60))],.024,'cream')
        for g,sgn in [(side+'Claw',1),(side+'Pincer',-1)]:
            for k in range(4):
                x=s*(1.30+(.17 if g.endswith('Claw') else -.14));y=-1.94-k*.13
                tip(g,(x,y,1.15),(x-s*.12*sgn,y-.04,1.15),.07,'cream')
        line(side+'Claw',[(s*1.24,-1.25,1.46),(s*1.44,-1.58,1.50),(s*1.69,-1.95,1.38)],.035,'cream')
        # Broad shell knuckles and small surface chips, distributed irregularly.
        for k in range(6):
            x=s*(1.17+random.random()*.35);y=-1.35-random.random()*.34
            ell(side+'Claw',(x,y,1.45),(.045,.06,.02),'russet' if mat=='coral' else 'sand',8,4)
    if ID=='rock-throwing-crab':
        o=ell('RightClaw',(1.45,-1.95,1.61),(.44,.38,.43),'lightgray',10,7)
        for v in o.data.vertices:v.co*=1+random.uniform(-.075,.075)
    if ID=='hermit-crab':
        for j in range(8):
            a=j*.55
            line('Body',[(.98*math.cos(a),-.41,2.30+.98*math.sin(a)),(.83*math.cos(a+.07),-.46,2.30+.83*math.sin(a+.07))],.028,'brown')
    if ID=='scorpion':
        for j in range(4):
            line('Body',[(-.58+j*.07,.17+j*.25,1.58),(0,.27+j*.25,1.72-j*.025),(.58-j*.07,.17+j*.25,1.58)],.03,'russet')
        for j in range(6):
            g=f'Tail{j}';p=Vector(bones[g]['head'])
            ell(g,p,(.25-j*.021,.23-j*.02,.25-j*.021),'russet',12,8)

def skeleton_details():
    humanoid()
    # Reconstruct bone shafts and hands rather than painting bones on block limbs.
    for s in [-1,1]:
        side=sides(s);ax=s*1.125;x=s*.49
        for part,p0,p1,split in [
            ('UpperLeg',(x,0,2.46),(x,0,1.44),False),
            ('LowerLeg',(x,0,1.35),(x,0,.44),True),
            ('UpperArm',(ax,0,4.10),(ax+s*.16,0,3.20),False),
            ('LowerArm',(ax+s*.16,0,3.15),(ax+s*.22,0,2.46),True)]:
            g=side+part;remove(g);a=Vector(p0);b=Vector(p1)
            for off in [-.105,.105] if split else [0]:
                d=Vector((off,0,0))
                smooth(tube(g,[a+d,a.lerp(b,.25)+d+Vector((.025,0,0)),a.lerp(b,.70)+d,b+d],[.13 if split else .21,.095 if split else .14,.08 if split else .13,.13 if split else .20],'ivory',10))
            for p in [a,b]:smooth(ell(g,p,(.235,.22,.17),'bone',12,8))
        g=side+'Hand';hx=ax+s*.22
        # Keep the held sword/bow/arrow, remove just original palm and thumb.
        remove(g,[0,1])
        if ID=='bow-skeleton' and side=='Left':
            for o in parts[g]:o.location.x+=.42
        box(g,(hx,-.015,2.29),(.48,.30,.36),'bone',.055)
        for k in range(4):
            xx=hx+(k-1.5)*.117
            for a,b in [((xx,-.08,2.19),(xx,-.17,2.05)),((xx,-.17,2.05),(xx,-.06,1.95))]:
                smooth(tube(g,[a,b],[.069,.055],'ivory',8))
        smooth(tube(g,[(hx-s*.23,-.03,2.34),(hx-s*.32,-.14,2.18),(hx-s*.23,-.20,2.10)],[.085,.075,.05],'ivory',8))
        g=side+'Foot';remove(g)
        smooth(ell(g,(x,.04,.23),(.24,.27,.20),'bone',12,8))
        for k in range(4):
            xx=x+(k-1.5)*.135
            smooth(tube(g,[(xx,0,.23),(xx,-.31,.16),(xx,-.62+abs(k-1.5)*.035,.12)],[.082,.075,.052],'ivory',8))
    # Remove the old skull, replace with rounded cranium, narrowed jaw and sockets.
    remove('Head')
    skull=loft('Head',[(0,0,4.63,.75,.64),(0,-.02,4.83,1.09,.92),(0,.015,5.18,1.43,1.12),(0,.025,5.48,1.36,1.10),(0,.03,5.68,.89,.83)],'ivory')
    for s in [-1,1]:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=10,location=(s*.32,-.51,5.17));cut=bpy.context.object;cut.scale=(.29,.31,.26)
        bpy.context.view_layer.objects.active=skull;m=skull.modifiers.new('Recessed orbit','BOOLEAN');m.operation='DIFFERENCE';m.object=cut;bpy.ops.object.modifier_apply(modifier=m.name);bpy.data.objects.remove(cut,do_unlink=True)
        ell('Head',(s*.32,-.32,5.16),(.23,.025,.205),'dark',14,8)
        line('Head',[(s*.08,-.54,5.37),(s*.32,-.58,5.43),(s*.58,-.49,5.42)],.065,'bone')
        smooth(tube('Head',[(s*.58,-.36,4.97),(s*.44,-.53,4.85),(s*.28,-.49,4.75)],[.13,.11,.075],'ivory',8))
    plate('Head',[(-.11,-.487,4.94),(.11,-.487,4.94),(0,-.55,5.09)],.02,'dark')
    tube('Head',[(-.48,-.18,4.84),(-.43,-.48,4.63),(0,-.52,4.58),(.43,-.48,4.63),(.48,-.18,4.84)],.10,'bone',8)
    for i in range(6):box('Head',((i-2.5)*.13,-.527,4.76),(.105,.13,.17),'ivory',.024)
    line('Head',[(-.22,-.40,5.59),(-.12,-.49,5.49),(-.20,-.53,5.42)],.015,'bone')
    # Clavicles, scapulae and extra tapered floating ribs.
    for s in [-1,1]:
        smooth(tube('UpperTorso',[(0,-.18,4.18),(s*.44,-.22,4.28),(s*.85,0,4.19)],[.10,.13,.09],'ivory',10))
        plate('UpperTorso',[(s*.18,.38,4.14),(s*.74,.36,4.17),(s*.62,.48,3.62)],.09,'bone')
        tube('UpperTorso',[(0,.35,3.43),(s*.48,.36,3.34),(s*.70,.04,3.23),(s*.51,-.34,3.16)],[.09,.095,.095,.05],'bone',8)
        buckle('LowerTorso',s*.32,-.57,2.91,.12,.19)
    # Replace the solid buckle face with a small real framed fastening.
    if len(parts['LowerTorso'])>0:buckle('LowerTorso',0,-.66,2.91,.32,.25)

def humanoid_details():
    humanoid()
    # Undo the original uniform size changes so detail placement is consistent.
    sc=.83 if ID in ['fire-goblin','ash-shaman'] else 1.18 if ID=='obsidian-ogre' else 1
    if sc!=1:
        for objs in parts.values():
            for o in objs:o.location/=sc;o.scale/=sc
        for b in bones.values():b['head']=[v/sc for v in b['head']]
    heavy=ID in ['obsidian-ogre','werewolf','spitter-zombie'];w=2 if heavy else 1.65
    if ID=='werewolf':
        remove('UpperTorso',list(range(1,7)))
        for side in ['Left','Right']:
            remove(side+'UpperArm',[1,2]);remove(side+'LowerArm',[1])
            for g in [side+'UpperArm',side+'LowerArm',side+'UpperLeg',side+'LowerLeg']:
                for o in parts[g]:smooth(o)
    if ID in ['werewolf','fire-goblin','ash-shaman','obsidian-ogre','spitter-zombie']:
        remove('Head',[0])
        skin={'werewolf':'gray','fire-goblin':'red','ash-shaman':'gray','obsidian-ogre':'charcoal','spitter-zombie':'sage'}[ID]
        loft('Head',[(0,-.03,4.43,.81,.75),(0,-.03,4.63,1.14,.98),(0,-.01,4.99,1.50,1.16),(0,.02,5.34,1.46,1.14),(0,.04,5.61,1.13,.91),(0,.05,5.71,.70,.62)],skin)
        if ID in ['fire-goblin','ash-shaman']:
            # Broad wedge nose and shaped cheekbones replace the flat face block.
            mesh('Head',[(-.12,-.61,5.22),(.12,-.61,5.22),(-.17,-.60,4.98),(.17,-.60,4.98),(0,-.85,5.02)],[(0,1,4),(0,4,2),(1,3,4),(2,4,3),(0,2,3,1)],skin,.015)
            for s in [-1,1]:line('Head',[(s*.27,-.60,4.91),(s*.48,-.59,4.96),(s*.59,-.48,5.07)],.045,skin)
    if ID in ['fire-goblin','ash-shaman','obsidian-ogre']:
        indices=[i for i,o in enumerate(parts['Head']) if 5.05<o.location.z<5.30 and o.location.y<-.60 and o.data.materials[0].name in ['ivory','dark','amber']]
        remove('Head',indices)
        for s in [-1,1]:
            x=s*.32
            plate('Head',[(x-s*.20,-.66,5.25),(x+s*.20,-.62,5.30),(x+s*.17,-.66,5.10),(x-s*.14,-.68,5.10)],.035,'dark')
            plate('Head',[(x-s*.12,-.701,5.21),(x+s*.13,-.669,5.25),(x+s*.11,-.692,5.14),(x-s*.10,-.712,5.14)],.015,'amber')
    for s in [-1,1]:
        side=sides(s);ax=s*(w/2+.30);hx=ax+s*.22;x=s*.49
        if ID!='mummy':
            g=side+'Hand';remove(g,[0,1]);skin={'werewolf':'gray','obsidian-ogre':'charcoal','fire-goblin':'red','ash-shaman':'gray','frozen-knight':'dark','spitter-zombie':'sage'}[ID]
            box(g,(hx,-.01,2.27),(.52,.46,.41),skin,.07)
            for k in range(4):
                xx=hx+(k-1.5)*.13
                smooth(tube(g,[(xx,-.16,2.28),(xx,-.30,2.08),(xx,-.19,1.98),(xx,-.04,2.07)],[.082,.08,.073,.056],skin,8))
            smooth(tube(g,[(hx-s*.23,0,2.38),(hx-s*.34,-.16,2.25),(hx-s*.26,-.30,2.14)],[.11,.10,.078],skin,8))
        if ID in ['frozen-knight','ash-shaman','fire-goblin']:
            # Bracers, layered boots and functional straps.
            for z in [2.62,3.03]:ring(side+'LowerArm',ax+s*.16,0,z,.71,.70,.11,'brown')
            for z in [.28,.43]:ring(side+'Foot',x,-.21,z,.87,1.15,.09,'charcoal')
            for z in [.72,1.05]:
                ring(side+'LowerLeg',x,0,z,.70,.74,.10,'brown');buckle(side+'LowerLeg',x,-.39,z,.18,.15)
            for k in range(3):line(side+'Hand',[(hx+(k-1)*.16,-.38,2.30),(hx+(k-1)*.16,-.40,2.08)],.016,'dark')
        if ID=='frozen-knight':
            for z,ww in [(3.96,.99),(3.78,.88)]:ring(side+'UpperArm',ax,0,z,ww,.96,.12,'lightgray')
            for zz in [2.68,2.90]:
                for xx in [-.22,.22]:rivet(side+'LowerArm',(ax+s*.16+xx,-.365,zz))
            # Embossed angular breastplate and inset center ridge.
            plate('UpperTorso',[(s*.04,-.60,4.26),(s*.74,-.51,4.15),(s*.85,-.55,3.67),(s*.35,-.67,3.34),(s*.04,-.67,3.47)],.065,'lightgray')
            line('UpperTorso',[(s*.15,-.70,3.56),(s*.64,-.59,3.81),(s*.62,-.56,4.06)],.03,'steel')
            for k in range(3):lock(side+'UpperArm',(ax+s*.28,.03,4.27),(.14*s,.05,.27+k*.10),.10,'cyan')
            for k in range(3):box(side+'Foot',(x,-.48+k*.20,.43+k*.035),(.77,.13,.12),'steel',.025)
        if ID=='werewolf':
            # Layered fur follows shoulder, forearm and chest anatomy.
            for j in range(3):
                for k in range(4):
                    lock(side+'UpperArm',(ax+s*(.10+j*.10),-.27+k*.15,4.13-j*.18),(s*.24,.01,-.34),.16,'gray')
            for k in range(5):lock(side+'LowerArm',(hx+s*.21,-.16+k*.11,3.11),(s*.20,.02,-.49),.16,'gray')
            for j in range(3):
                for k in range(3):lock('UpperTorso',(s*(.15+k*.19),-.56,4.12-j*.15),(.08*s,-.06,-.35),.16,'lightgray')
            for k in range(4):lock('Head',(s*.50,.05+k*.11,5.32),(s*.32,.04,-.44),.17,'gray')
            # Longer angled muzzle and brow recess, no teddy-bear muzzle.
            plate('Head',[(s*.14,-.82,5.16),(s*.45,-.63,5.21),(s*.45,-.94,4.95),(s*.19,-1.15,4.95)],.08,'gray')
            for k in range(3):tip('Head',(s*(.18+k*.10),-.98,4.86),(s*(.18+k*.10),-.99,4.73),.033,'ivory')
            # Hock bends and individual toes change the feet silhouette.
            for k in range(3):smooth(ell(side+'Foot',(x+(k-1)*.235,-.64,.21),(.145,.25,.15),'gray',12,8))
        if ID=='obsidian-ogre':
            for j in range(3):
                lock(side+'UpperArm',(ax+s*.22,-.20+j*.24,4.19),(s*.38,.03,.33),.22,'charcoal')
            for k in range(4):
                p=(s*(.25+k*.19),-.57,3.6+random.random()*.5)
                line('UpperTorso',[p,(p[0]+s*.08,-.60,p[2]-.13),(p[0]-.04,-.58,p[2]-.25)],.024,'orange')
            for k in range(3):box(side+'Hand',(hx+(k-1)*.23,-.38,2.32),(.18,.15,.17),'charcoal',.035)
        if ID=='mummy':
            # Loose wrap ends and broad cloth creases break the uniform cylinder pattern.
            for g,xx,zz in [(side+'UpperArm',ax,3.89),(side+'LowerLeg',x,1.18)]:
                plate(g,[(xx-.12,-.40,zz),(xx+.15,-.40,zz+.035),(xx+.18,-.46,zz-.38),(xx+.04,-.47,zz-.52),(xx-.12,-.46,zz-.44)],.028,'cream')
            for k in range(4):line('UpperTorso',[(s*.12,-.60,3.25+k*.24),(s*.58,-.60,3.35+k*.24)],.013,'sand')
        if ID in ['fire-goblin','ash-shaman']:
            for k in range(3):rivet('LowerTorso',(s*(.23+k*.20),-.58,2.91),'steel',.035)
            # Leather shoulder pad with overlapping lames.
            for k in range(3):ring(side+'UpperArm',ax,0,4.11-k*.14,.84-k*.04,.87-k*.02,.15,'charcoal')
    if ID=='ash-shaman':
        for k in range(5):
            z=3.19+k*.18;buckle('UpperTorso',0,-.64,z,.17,.11)
        for s in [-1,1]:line('UpperTorso',[(s*.60,-.58,4.12),(s*.35,-.64,3.57),(s*.47,-.59,3.08)],.045,'sand')
    if ID=='fire-goblin':
        # Scarf with layered fold, belt pouch and serrated brow expression.
        ring('UpperTorso',0,0,4.35,1.15,.94,.28,'brown')
        plate('UpperTorso',[(-.43,-.50,4.36),(-.10,-.58,4.32),(.22,-.58,3.87),(-.12,-.63,3.58),(-.35,-.59,3.78)],.09,'brown')
    if ID=='mummy':
        move_vertices('Head',lambda v:(v.x*(.69+.31*min(1,max(0,(v.z-4.44)/.72))),v.y,v.z))
        for o in parts['Head']:
            if o.data.materials[0].name=='amber':o.scale*=.65
        for s in [-1,1]:line('UpperTorso',[(s*.54,-.62,4.16),(s*.39,-.67,3.92),(0,-.68,3.82)],.06,'sand')
        plate('UpperTorso',[(-.16,-.70,3.87),(0,-.70,4.02),(.16,-.70,3.87),(0,-.70,3.62)],.06,'teal')
    if ID=='spitter-zombie':
        # Frayed shirt edge around the swollen torso; clear seams and uneven tears.
        for s in [-1,1]:
            for k in range(4):
                x=s*(.42+k*.15)
                plate('UpperTorso',[(x-.10,-.59,3.80),(x+.11,-.57,3.78),(x+.035,-.68,3.49-random.random()*.14)],.05,'cloth')
            line('UpperTorso',[(s*.84,-.40,4.02),(s*.87,-.45,3.69),(s*.88,-.42,3.45)],.025,'brown')
            for k in range(4):line('UpperTorso',[(s*.77,-.46,3.55+k*.12),(s*.91,-.46,3.58+k*.12)],.014,'cream')
            plate(sides(s)+'UpperLeg',[(s*.49-.23,-.39,2.12),(s*.49+.21,-.39,2.09),(s*.49+.16,-.42,1.74),(s*.49-.19,-.42,1.77)],.04,'charcoal')
        buckle('LowerTorso',0,-.66,2.91,.34,.27)

def organic_details():
    if ID=='snake':
        snake()
        # Broad overlapping dorsal plates: visible intentional scale pattern.
        for j in range(24):
            t=j/32;rr=.39*(1-t)+.045
            p=Vector((.91*math.sin(t*math.pi*2.2)*min(1,t*3),-.9+3.2*t,rr+1.61*math.exp(-t*11)))
            g=f'Spine{min(8,j//4)}'
            for s in [-1,1]:
                ell(g,p+Vector((s*rr*.52,0,rr*.67)),(rr*.30,.085,rr*.13),'olive' if j%3 else 'sand',8,5)
        for s in [-1,1]:line('Head',[(s*.43,-1.15,2.07),(s*.42,-1.44,2.02),(s*.20,-1.57,2.0)],.017,'brown')
    elif ID=='ember-spider':
        spider()
        for o in parts['Body']:
            if o.data.materials[0].name=='amber':o.scale*=.60
        for s in [-1,1]:
            for i in range(4):
                g=f'{sides(s)}Leg{i}Lower';p=Vector(bones[g]['head'])
                ell(g,p,(.22,.20,.21),'charcoal',12,8)
                lock(g,p+Vector((0,0,.11)),(s*.19,.02,.19),.10,'charcoal')
            for k in range(4):
                y=.18+k*.27
                line('Body',[(s*.30,y,2.02),(s*.61,y+.07,1.87),(s*.80,y+.02,1.66)],.045,'orange')
        for s in [-1,1]:
            for k in range(2):ell('Body',(s*(.37+k*.13),-1.01,1.37+k*.10),(.058,.041,.068),'orange',10,6)
    elif ID=='frost-ghost':
        # Continuous billowing shroud replaces the block head/cone assembly.
        bone('Body',(0,0,1.8));bone('Head',(0,0,2.75),'Body')
        n=24;verts=[]
        for j,(z,r,d) in enumerate([(.30,1.08,.65),(.90,.89,.56),(1.65,.61,.43),(2.35,.70,.48),(2.8,.66,.51)]):
            for k in range(n):
                a=k*math.tau/n;fold=1+.08*math.cos(a*7+j*.15)
                verts.append((r*math.cos(a)*fold,d*math.sin(a)*fold,z+(.16*math.sin(a*5) if j==0 else 0)))
        faces=[tuple(range(n-1,-1,-1))]
        for j in range(4):
            for k in range(n):faces.append((j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k))
        faces.append(tuple(range(4*n,5*n)));smooth(mesh('Body',verts,faces,'skin'))
        smooth(ell('Head',(0,.01,3.08),(.71,.58,.79),'fur',24,16))
        # Deep face aperture under a real hood rim.
        ell('Head',(0,-.60,3.11),(.48,.06,.49),'charcoal',20,12)
        points=[]
        for k in range(25):
            a=k*math.tau/24;points.append((.53*math.cos(a),-.59,3.11+.56*math.sin(a)))
        smooth(tube('Head',points,.095,'fur',8))
        for s in [-1,1]:
            ell('Head',(s*.19,-.675,3.15),(.077,.02,.11),'cyan',12,8)
            g=sides(s)+'Arm';bone(g,(s*.57,0,2.43),'Body')
            smooth(tube(g,[(s*.57,0,2.43),(s*.96,-.10,2.12),(s*1.08,-.29,1.87)],[.28,.26,.13],'skin',12))
            for k in range(3):lock(g,(s*1.06+(k-1)*.075,-.30,1.92),(.05*s,-.09,-.29-k*.02),.055,'fur')
    else:
        bone('Body',(0,0,.3));bone('Crown',(0,0,1.22),'Body')
        # A basalt crust wraps a continuous molten dome. Broad cracks remain orange.
        n=24;levels=[(.03,1.26,.93),(.27,1.44,1.06),(.78,1.29,.97),(1.30,1.02,.80),(1.75,.61,.50),(1.95,.05,.05)]
        verts=[]
        for z,rx,ry in levels:
            for k in range(n):
                a=k*math.tau/n;verts.append((rx*math.cos(a),ry*math.sin(a),z))
        faces=[tuple(range(n-1,-1,-1))]
        for j in range(len(levels)-1):
            for k in range(n):faces.append((j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k))
        faces.append(tuple(range((len(levels)-1)*n,len(levels)*n)))
        smooth(mesh('Body',verts,faces,'orange'))
        for j in range(1,4):
            z0,rx0,ry0=levels[j];z1,rx1,ry1=levels[j+1]
            for k in range(8):
                # Leave front center molten, framed by cracked crust and angular eyes.
                a0=(k+.055)*math.tau/8;a1=(k+.945)*math.tau/8
                if k in [5,6] and j==2:continue
                corners=[]
                for z,rx,ry in [(z0+.035,rx0,ry0),(z1-.035,rx1,ry1)]:
                    for q in range(4):
                        a=a0+(a1-a0)*q/3;corners.append((rx*1.035*math.cos(a),ry*1.035*math.sin(a),z))
                inner=[(x*.91,y*.91,z) for x,y,z in corners];faces=[]
                for q in range(3):
                    faces += [(q,q+1,q+5,q+4),(q+12,q+13,q+9,q+8),(q+8,q+9,q+1,q),(q+4,q+5,q+13,q+12)]
                faces += [(0,4,12,8),(3,11,15,7)]
                mesh('Crown' if j==3 else 'Body',corners+inner,faces,'charcoal',.012)
        for s in [-1,1]:
            plate('Body',[(s*.14,-.918,1.28),(s*.62,-.829,1.38),(s*.56,-.91,1.16),(s*.21,-.975,1.12)],.055,'dark')
            plate('Body',[(s*.22,-.983,1.235),(s*.53,-.916,1.29),(s*.48,-.956,1.20),(s*.24,-.999,1.18)],.025,'amber')

if ID in ['crab','hermit-crab','rock-throwing-crab','scorpion']:shell_details()
elif ID in ['skeleton','bow-skeleton']:skeleton_details()
elif ID in ['snake','ember-spider','frost-ghost','lava-slime']:organic_details()
else:humanoid_details()

# Humanoid proportions: longer legs, smaller head, no bobble-head scaling.
if 'UpperTorso' in bones:
    def proportions(v,head=False):
        x,y,z=v
        if head:x*=.89;y*=.89;z=4.45+(z-4.45)*.91
        z=z*1.16 if z<2.5 else z+.40
        return (x,y,z)
    for g in parts:move_vertices(g,lambda v,g=g:proportions(v,g=='Head'))
    for g,b in bones.items():b['head']=list(proportions(b['head'],False)) if g!='Root' else [0,0,0]
    character_scale={'fire-goblin':.82,'obsidian-ogre':1.28,'werewolf':1.08,'spitter-zombie':1.05}.get(ID,1)
    for g in parts:move_vertices(g,lambda v:tuple(c*character_scale for c in v))
    for b in bones.values():b['head']=[c*character_scale for c in b['head']]

ATLAS_SOURCE=ROOT/'revisions'/'Materials.png'
if ID in ['crab','hermit-crab','rock-throwing-crab','scorpion','snake']:
    for objects in parts.values():
        for o in objects:
            for i,m in enumerate(o.data.materials):
                if m.name=='cream':o.data.materials[i]=mats['ivory']
REVIEW_RESOLUTION=800;REVIEW_SAMPLES=16
exec(compile((ROOT/'deliver.py').read_text(),str(ROOT/'deliver.py'),'exec'))
