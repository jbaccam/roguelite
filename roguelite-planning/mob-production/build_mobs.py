"""Reference-authored regular mobs. Run only in a dedicated background Blender process."""
import bpy, bmesh, math, json, sys, random
from pathlib import Path
from mathutils import Vector
import numpy as np

ROOT=Path(__file__).resolve().parent
ID=sys.argv[sys.argv.index('--')+1]
OUT=ROOT/ID
OUT.mkdir(exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
random.seed(49)
parts={}; bones={}; mats={}; palette=[]

def material(name, rgb):
    if name in mats:return mats[name]
    m=bpy.data.materials.new(name);m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value=(*rgb,1)
    bs.inputs['Roughness'].default_value=.88
    bs.inputs['Specular IOR Level'].default_value=.18
    m.diffuse_color=(*rgb,1)
    mats[name]=m;palette.append((name,rgb))
    return m

COLORS={'ivory':(.72,.66,.49),'bone':(.65,.57,.40),'dark':(.028,.026,.027),
 'white':(.75,.80,.84),'brown':(.15,.09,.052),'cloth':(.105,.078,.059),
 'steel':(.23,.28,.32),'cyan':(.26,.66,.79),'orange':(.8,.25,.035),
 'skin':(.20,.35,.55),'blue':(.08,.13,.23),'fur':(.64,.68,.72),
 'coral':(.60,.15,.065),'cream':(.61,.47,.28),'teal':(.10,.23,.26),
 'olive':(.24,.28,.085),'sand':(.55,.39,.19),'russet':(.28,.11,.045),
 'gray':(.18,.19,.24),'lightgray':(.46,.48,.49),'amber':(.9,.41,.055),
 'red':(.43,.09,.035),'charcoal':(.075,.065,.071),'sage':(.34,.39,.19)}
for name,col in COLORS.items():material(name,col)

def bone(name, head, parent='Root'):
    bones[name]={'head':list(head),'parent':parent}

bone('Root',(0,0,0),None)

def finish(o, group, mat, bevel=0):
    o.name=group+'_'+str(len(parts.get(group,[])))
    bpy.context.view_layer.objects.active=o
    if bevel:
        m=o.modifiers.new('Soft bevel','BEVEL');m.width=bevel;m.segments=2
        bpy.ops.object.modifier_apply(modifier=m.name)
    bm=bmesh.new();bm.from_mesh(o.data)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free()
    o.data.materials.clear();o.data.materials.append(mats[mat])
    parts.setdefault(group,[]).append(o)
    return o

def box(g,p,s,mat,bev=.08):
    bpy.ops.mesh.primitive_cube_add(size=1,location=p)
    o=bpy.context.object;o.dimensions=s
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return finish(o,g,mat,bev)

def ell(g,p,s,mat,seg=16,rings=10):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg,ring_count=rings,radius=1,location=p)
    o=bpy.context.object;o.scale=s
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return finish(o,g,mat)

def mesh(g,verts,faces,mat,bev=0):
    me=bpy.data.meshes.new(g);me.from_pydata(verts,[],faces);me.update()
    o=bpy.data.objects.new(g,me);scene.collection.objects.link(o)
    return finish(o,g,mat,bev)

def profile(w,d,n=12):
    # Rounded rectangle with broad front/back planes and softened corners.
    pts=[];r=min(w,d)*.23
    for cx,cy,start in [(w/2-r,d/2-r,0),(-w/2+r,d/2-r,90),(-w/2+r,-d/2+r,180),(w/2-r,-d/2+r,270)]:
        for t in [0,45,90]:
            a=math.radians(start+t);pts.append((cx+r*math.cos(a),cy+r*math.sin(a)))
    return pts

def loft(g,levels,mat,rag=0):
    v=[];n=12
    for j,(x,y,z,w,d) in enumerate(levels):
        for k,(a,b) in enumerate(profile(w,d)):
            zz=z+(rag*(.3 if k%2 else -.6) if j==0 else 0)
            v.append((x+a,y+b,zz))
    f=[tuple(range(n-1,-1,-1))]
    for j in range(len(levels)-1):
        for i in range(n):f.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
    f.append(tuple(range((len(levels)-1)*n,len(levels)*n)))
    return mesh(g,v,f,mat)

def tube(g,points,radii,mat,n=8):
    # Closed, tapered swept cross section; geometry—not a curve at export time.
    pts=[Vector(p) for p in points];v=[]
    for i,p in enumerate(pts):
        t=(pts[min(i+1,len(pts)-1)]-pts[max(i-1,0)]).normalized()
        ref=Vector((0,0,1)) if abs(t.z)<.92 else Vector((0,1,0))
        u=t.cross(ref).normalized();w=t.cross(u).normalized()
        r=radii[i] if isinstance(radii,list) else radii
        if isinstance(r,tuple):rx,ry=r
        else:rx=ry=r
        for k in range(n):
            a=k*2*math.pi/n;v.append(tuple(p+u*(math.cos(a)*rx)+w*(math.sin(a)*ry)))
    f=[tuple(range(n-1,-1,-1))]
    for j in range(len(pts)-1):
        for i in range(n):f.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
    f.append(tuple(range((len(pts)-1)*n,len(pts)*n)))
    return mesh(g,v,f,mat)

def tip(g,a,b,r,mat):return tube(g,[a,b],[r,.016],mat)

def plate(g,points,depth,mat):
    v=[tuple(p) for p in points]+[(x,y+depth,z) for x,y,z in points];n=len(points)
    f=[tuple(range(n-1,-1,-1)),tuple(range(n,n*2))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return mesh(g,v,f,mat,.014)

def eyes(g,z,y,x=.29,color='ivory',size=.17,angry=True):
    for s in [-1,1]:
        ell(g,(s*x,y,z),(size*1.32,.055,size*1.18),'dark',12,8)
        ell(g,(s*x,y-.043,z),(size*.68,.024,size*.77),color,12,8)
        if angry:
            o=box(g,(s*x,y-.04,z+size*.94),(size*2.65,.10,.105),'dark',.025);o.rotation_euler.y=s*-.19

def face(g,z,y,width=1.4,skin='skin',kind='normal'):
    eyes(g,z+.12,y,width*.23,'amber' if kind in ['goblin','ogre'] else 'ivory',width*.11)
    if kind not in ['mummy','knight']:
        ell(g,(0,y-.025,z-.28),(width*.23,.04,.075),'dark',12,6)
        if kind in ['goblin','ogre','zombie']:
            for s in [-1,1]:tip(g,(s*width*.21,y-.06,z-.36),(s*width*.19,y-.08,z-.05),.085,'ivory')

def sword(g,x,y,z,short=False):
    old=len(parts.get(g,[]))
    tube(g,[(x,y,z-.35),(x,y,z+.35)],.105,'brown')
    box(g,(x,y,z+.35),(.7,.18,.13),'steel',.035)
    l=.8 if short else 1.45
    plate(g,[(x-.22,y-.07,z+.40),(x+.22,y-.07,z+.40),(x+.22,y-.07,z+l),(x,y-.07,z+l+.35),(x-.22,y-.07,z+l)],.14,'steel')
    from mathutils import Matrix
    pivot=Vector((x,y,z));rotation=Matrix.Rotation(.65,4,'X')
    for o in parts[g][old:]:
        for v in o.data.vertices:
            world=o.matrix_world@v.co;world=pivot+rotation.to_3x3()@(world-pivot);v.co=o.matrix_world.inverted()@world

def humanoid():
    heavy=ID in ['obsidian-ogre','spitter-zombie','werewolf']
    short=ID in ['fire-goblin','ash-shaman']
    sc=.83 if short else (1.18 if ID=='obsidian-ogre' else 1)
    # Model in common authoring dimensions; scale applied to everything at end.
    w=2.0 if heavy else 1.65
    skin={'fire-goblin':'red','obsidian-ogre':'charcoal','werewolf':'gray','spitter-zombie':'sage','mummy':'sand','skeleton':'ivory','bow-skeleton':'ivory','ash-shaman':'gray','frozen-knight':'dark'}.get(ID,'skin')
    skel=ID in ['skeleton','bow-skeleton']
    cloth={'ice-elf':'blue','ash-shaman':'red','frozen-knight':'steel','mummy':'cream'}.get(ID,'cloth')
    bone('LowerTorso',(0,0,2.4));bone('UpperTorso',(0,0,3.0),'LowerTorso');bone('Head',(0,0,4.45),'UpperTorso')
    for s,side in [(-1,'Left'),(1,'Right')]:
        x=s*.49
        bone(side+'UpperLeg',(x,0,2.48),'LowerTorso');bone(side+'LowerLeg',(x,0,1.38),side+'UpperLeg');bone(side+'Foot',(x,0,.40),side+'LowerLeg')
        ax=s*(w/2+.30)
        bone(side+'UpperArm',(ax,0,4.15),'UpperTorso');bone(side+'LowerArm',(ax+s*.16,0,3.18),side+'UpperArm');bone(side+'Hand',(ax+s*.22,0,2.45),side+'LowerArm')
        for part,z,h,ww,dd,mat in [('UpperLeg',1.95,1.05,.70,.73,skin if skel or ID=='obsidian-ogre' else cloth),('LowerLeg',.91,.99,.65,.66,skin if ID not in ['ice-elf','ash-shaman','frozen-knight'] else 'dark')]:
            loft(side+part,[(x,0,z-h/2,ww*.83,dd*.85),(x,0,z-h*.31,ww*.94,dd*.93),(x,0,z,ww*(.66 if skel else 1),dd*(.72 if skel else 1)),(x,0,z+h*.31,ww*.96,dd*.95),(x,0,z+h/2,ww*.86,dd*.9)],mat)
        footmat=skin if ID not in ['ice-elf','ash-shaman','frozen-knight'] else 'brown' if ID!='frozen-knight' else 'steel'
        loft(side+'Foot',[(x,-.19,.015,.81,1.08),(x,-.21,.20,.88,1.18),(x,-.11,.48,.72,.88)],footmat)
        if ID in ['ice-elf','ash-shaman']:
            box(side+'LowerLeg',(x,0,.93),(.76,.75,.25),'fur' if ID=='ice-elf' else 'brown',.09)
        for part,xx,z,h,ww in [('UpperArm',ax,3.71,.94,.75 if not heavy else .94),('LowerArm',ax+s*.16,2.88,.76,.62 if not heavy else .85)]:
            mat=cloth if part=='UpperArm' and ID not in ['werewolf','obsidian-ogre'] and not skel else skin
            if ID=='frozen-knight':mat='steel'
            loft(side+part,[(xx,0,z-h/2,ww*.82,ww*.8),(xx,0,z,ww,ww*.94),(xx,0,z+h/2,ww*.92,ww*.87)],mat)
            if ID=='mummy':wraps(side+part,xx,0,z,h,ww,ww*.94)
        hx=ax+s*.22
        box(side+'Hand',(hx,-.02,2.20),(.68 if not heavy else .88,.68,.66),skin,.17)
        ell(side+'Hand',(hx-s*.34,-.21,2.22),(.16,.22,.24),skin,12,8)
        if ID in ['ice-elf','ash-shaman']:
            box(side+'LowerArm',(ax+s*.16,0,2.55),(.76,.75,.23),'fur' if ID=='ice-elf' else 'brown',.08)
        if skel:
            for z in [1.38,3.17]:ell(side+('LowerLeg' if z<2 else 'LowerArm'),(x if z<2 else ax+s*.16,0,z),(.26,.28,.23),'bone',12,8)
        if ID=='mummy':
            for part,z,h in [('UpperLeg',1.95,1.05),('LowerLeg',.91,.99)]:wraps(side+part,x,0,z,h,.70,.73)
        if ID=='werewolf':
            for k in range(3):
                tip(side+'Hand',(hx+(k-1)*.23,-.35,2.10),(hx+(k-1)*.23,-.48,1.75),.09,'dark')
                tip(side+'Foot',(x+(k-1)*.23,-.69,.18),(x+(k-1)*.23,-.95,.07),.10,'dark')
            for z in [3.9,3.6,2.9]:tuft(side+('UpperArm' if z>3.3 else 'LowerArm'),(ax+s*.22,.02,z),(.40*s,.02,-.47),'gray',.25)
        if ID=='frozen-knight':
            box(side+'UpperArm',(ax,0,4.04),(.94,.91,.58),'steel',.15)
            box(side+'LowerLeg',(x,-.37,1.33),(.57,.19,.44),'steel',.07)
    if skel:
        for z in [2.67,2.93,3.19,3.45,3.71,3.97]:box('UpperTorso' if z>3 else 'LowerTorso',(0,.14,z),(.38,.44,.23),'bone',.07)
        for z,wid in [(3.28,1.33),(3.64,1.59),(4.02,1.74)]:
            for s in [-1,1]:tube('UpperTorso',[(0,-.43,z),(s*wid*.35,-.46,z+.015),(s*wid*.51,-.19,z+.10),(s*wid*.48,.27,z+.13),(s*.2,.42,z+.04)],.12,'ivory',8)
        box('UpperTorso',(0,-.46,3.77),(.28,.18,1.12),'ivory',.035)
        ell('LowerTorso',(0,0,2.50),(.72,.44,.32),'bone',16,8)
    else:
        loft('LowerTorso',[(0,0,2.42,w*.75,.87),(0,0,2.80,w*.88,1.0),(0,0,3.12,w*.91,1.0)],skin if heavy else cloth)
        loft('UpperTorso',[(0,0,3.00,w*.86,1.0),(0,.02,3.48,w*1.05,1.15),(0,.01,4.03,w*1.10,1.04),(0,0,4.38,w*.76,.83)],skin if ID in ['werewolf','obsidian-ogre'] else cloth)
    headbody=box('Head',(0,-.03,5.05),(1.50,1.18,1.34),skin,.22)
    if skel:
        # Broad recessed-looking dark socket shapes with bone brows and separate jaw.
        for s in [-1,1]:
            bpy.ops.mesh.primitive_cube_add(size=1,location=(s*.34,-.61,5.15));cutter=bpy.context.object
            cutter.dimensions=(.51,.48,.49);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
            bevel=cutter.modifiers.new('Socket roundover','BEVEL');bevel.width=.12;bevel.segments=3;bpy.ops.object.modifier_apply(modifier=bevel.name)
            bpy.context.view_layer.objects.active=headbody
            cut=headbody.modifiers.new('Eye socket','BOOLEAN');cut.operation='DIFFERENCE';cut.object=cutter;bpy.ops.object.modifier_apply(modifier=cut.name)
            bpy.data.objects.remove(cutter,do_unlink=True)
            box('Head',(s*.34,-.388,5.15),(.47,.035,.45),'dark',.09)
            o=box('Head',(s*.34,-.668,5.39),(.57,.07,.14),'ivory',.035);o.rotation_euler.y=-s*.17
        plate('Head',[(-.11,-.676,4.95),(.11,-.676,4.95),(0,-.678,5.13)],.025,'dark')
        box('Head',(0,-.38,4.62),(1.1,.69,.24),'bone',.08)
        for i in range(5):box('Head',((i-2)*.205,-.715,4.72),(.175,.15,.27),'ivory',.045)
    elif ID=='mummy':
        box('Head',(0,-.639,5.17),(1.2,.05,.31),'dark',.03)
        for s in [-1,1]:ell('Head',(s*.26,-.676,5.17),(.10,.02,.13),'amber',12,8)
        wraps('Head',0,-.03,5.05,1.34,1.52,1.20,head=True)
        wraps('UpperTorso',0,0,3.67,1.30,w*1.08,1.16)
    elif ID=='frozen-knight':
        box('Head',(0,-.03,5.28),(1.57,1.25,.89),'steel',.18)
        box('Head',(0,-.03,4.76),(1.51,1.21,.49),'steel',.12)
        box('Head',(0,-.688,5.12),(1.27,.03,.14),'dark',.02)
        for s in [-1,1]:ell('Head',(s*.30,-.715,5.12),(.12,.017,.044),'cyan',10,6)
        for x in [-.34,0,.34]:box('Head',(x,-.66,4.77),(.095,.024,.22),'dark',.014)
        box('Head',(0,0,5.75),(.19,1.05,.22),'steel',.055)
    elif ID=='werewolf':wolf_head()
    else:
        if ID in ['ice-elf','ash-shaman']:
            for s in [-1,1]:
                ell('Head',(s*.32,-.632,5.19),(.215,.034,.205),'ivory',14,8)
                ell('Head',(s*.32,-.664,5.18),(.100,.017,.145),'blue' if ID=='ice-elf' else 'amber',12,8)
                ell('Head',(s*.32,-.68,5.18),(.046,.010,.086),'dark',10,6)
                o=box('Head',(s*.31,-.672,5.39),(.46,.06,.085),'dark',.018);o.rotation_euler.y=-s*.20
            tube('Head',[(-.22,-.652,4.91),(0,-.663,4.89),(.20,-.65,4.93)],.018,'dark',5)
        else:face('Head',5.02,-.641,1.5,skin,'goblin' if ID=='fire-goblin' else 'ogre' if ID=='obsidian-ogre' else 'zombie')
    if ID in ['ice-elf','fire-goblin','ash-shaman']:
        for s in [-1,1]:
            plate('Head',[(s*.69,-.17,5.34),(s*1.32,-.12,5.56),(s*.85,-.20,4.96)],.28,skin)
            plate('Head',[(s*.79,-.191,5.32),(s*1.14,-.16,5.45),(s*.88,-.221,5.10)],.025,'blue' if ID=='ice-elf' else 'cloth')
    if ID=='ice-elf':elf_details()
    if ID=='ash-shaman':shaman_details()
    if ID in ['fire-goblin','spitter-zombie','obsidian-ogre','werewolf','skeleton','bow-skeleton','ice-elf','ash-shaman']:
        box('LowerTorso',(0,0,2.91),(w*.98,1.06,.24),'brown',.065)
        box('LowerTorso',(0,-.568,2.91),(.40,.12,.31),'steel' if ID in ['ice-elf','skeleton','bow-skeleton'] else 'brown',.04)
        if ID not in ['spitter-zombie','werewolf']:
            skirt='sand' if ID=='bow-skeleton' else cloth
            for s in [-1,1]:plate('LowerTorso',[(s*.07,-.54,2.80),(s*w*.46,-.48,2.80),(s*w*.51,-.53,2.12),(s*w*.30,-.59,2.22),(s*.10,-.59,2.02)],.10,skirt)
    if ID in ['skeleton','frozen-knight','fire-goblin']:sword('RightHand',w/2+.52,-.15,2.20,ID=='fire-goblin')
    if ID=='bow-skeleton':bow_details(w)
    if ID=='spitter-zombie':
        ell('LowerTorso',(0,-.53,3.13),(.87,.56,.73),'sage',20,12)
        for s in [-1,1]:ell('Head',(s*.53,-.63,4.89),(.31,.27,.32),'sage',14,8)
    if ID=='obsidian-ogre':
        for s in [-1,1]:
            for k in range(2):tube(sides(s)+'UpperArm',[(s*1.29,-.40,4.10-k*.22),(s*1.39,-.45,3.99-k*.22),(s*1.52,-.41,4.03-k*.22)],.018,'orange',5)
    if sc!=1:
        for objs in parts.values():
            for o in objs:o.location*=sc;o.scale*=sc
        for b in bones.values():b['head']=[v*sc for v in b['head']]

def sides(s):return 'Left' if s<0 else 'Right'

def wraps(g,x,y,z,h,w,d,head=False):
    count=max(3,int(h/.22))
    for i in range(count):
        zz=z-h/2+(i+.5)*h/count
        if head and 5.02<zz<5.34:continue
        o=loft(g,[(x,y,zz-.095,w*1.015,d*1.018),(x,y,zz+.095,w*1.025,d*1.025)],'cream' if i%3 else 'sand')
        # Subtle diagonal frontage; closed wrapped volume across sides/back.
        for v in o.data.vertices:v.co.z+=v.co.x*(.08 if i%2 else -.07)

def tuft(g,p,delta,mat,width=.25):
    x,y,z=p;dx,dy,dz=delta
    return tube(g,[(x,y,z),(x+dx*.45,y+dy*.45-.055,z+dz*.35),(x+dx,y+dy,z+dz)],[(width,.15),(width*.80,.13),(.018,.018)],mat,6)

def elf_details():
    ell('Head',(0,.06,5.65),(.80,.65,.37),'white',16,8)
    for i in range(6):
        x=(i-2.5)*.235
        tuft('Head',(x,-.36,5.86+(.12 if i in [2,3] else 0)),(-.16,-.36,-.56-(.14 if i%2 else 0)),'white',.24)
    for i in range(4):
        tuft('Head',(-.42+i*.23,.04,5.89),(-.31,.03,.31+(.13 if i==2 else 0)),'white',.24)
    for s in [-1,1]:
        for i in range(3):tuft('Head',(s*.65,-.03+i*.20,5.70),(.14*s,-.17,-.66),'white',.23)
        for i in range(5):tuft('UpperTorso',(s*(.17+i*.16),-.43,4.42-i*.04),(.07*s,-.21,-.40),'fur',.22)
        for i in range(3):tuft('UpperTorso',(s*(.20+i*.22),.43,4.39-i*.03),(.08*s,.17,-.30),'fur',.23)
    for z in [3.72,4.00]:
        for s in [-1,1]:
            o=box('UpperTorso',(0,-.612,z),(.32,.08,.075),'fur',.014);o.rotation_euler.y=s*.75

def shaman_details():
    # Hood is an open front shell, not a solid box covering the face.
    n=14;v=[]
    for y,scale in [(-.66,1.0),(.30,1.08),(.62,.73)]:
        for i in range(n):
            a=math.pi*i/(n-1);v.append((math.cos(a)*.93*scale,y,4.53+math.sin(a)*1.38*scale))
    f=[]
    for j in range(2):
        for i in range(n-1):f.append((j*n+i,j*n+i+1,(j+1)*n+i+1,(j+1)*n+i))
    o=mesh('Head',v,f,'charcoal');bpy.context.view_layer.objects.active=o
    m=o.modifiers.new('Hood thickness','SOLIDIFY');m.thickness=.10;bpy.ops.object.modifier_apply(modifier=m.name)
    tube('Head',v[:n],.055,'brown',6)
    x=1.39;tube('RightHand',[(x,-.11,.18),(x,-.08,4.37)],.09,'brown',8)
    for s in [-1,1]:tube('RightHand',[(x,-.08,4.12),(x+s*.27,-.07,4.46),(x+s*.21,-.07,4.85)],[.12,.085,.025],'brown',6)
    ell('RightHand',(x,-.08,4.64),(.22,.19,.39),'orange',8,6)

def wolf_head():
    ell('Head',(0,-.62,4.93),(.52,.47,.31),'lightgray',14,8)
    box('Head',(0,-1.02,4.96),(.35,.20,.22),'dark',.07)
    eyes('Head',5.25,-.636,.39,'cyan',.115)
    for s in [-1,1]:
        plate('Head',[(s*.40,-.08,5.58),(s*.69,-.02,6.19),(s*.84,.01,5.58)],.27,'gray')
        for k in range(3):tuft('Head',(s*(.47+k*.09),-.34,5.08-k*.18),(.29*s,.01,-.28),'lightgray',.19)
        tip('Head',(s*.28,-.96,4.86),(s*.25,-.98,4.72),.055,'ivory')
        for k in range(3):tuft('UpperTorso',(s*(.16+k*.23),-.58,4.06-k*.11),(.05*s,-.035,-.60),'lightgray',.25)
    bone('Tail',(0,.40,2.61),'LowerTorso')
    tube('Tail',[(0,.40,2.61),(0,.73,2.33),(0,1.03,1.98),(0,1.11,1.87)],[.23,.28,.20,.018],'gray',10)

def bow_details(w):
    x=-w/2-.52;y=-.24
    tube('LeftHand',[(x,y,1.02),(x-.27,y,1.37),(x-.40,y,1.94),(x-.42,y,2.41),(x-.28,y,3.06),(x,y,3.56)],[.07,.10,.12,.12,.10,.055],'brown',8)
    tube('LeftHand',[(x,y,1.02),(x+.08,y,2.27),(x,y,3.56)],.018,'cream',5)
    tube('RightHand',[(w/2+.52,-.18,1.47),(w/2+.52,-.18,3.03)],.032,'brown',6)
    tip('RightHand',(w/2+.52,-.18,3.03),(w/2+.52,-.18,3.33),.13,'steel')
    tube('UpperTorso',[(.45,.58,3.05),(.45,.75,4.30)],.25,'brown',10)
    for k in range(3):tube('UpperTorso',[(.29+k*.15,.73,4.05),(.29+k*.15,.83,4.69)],.035,'cream',6)
    plate('UpperTorso',[(-.90,-.51,4.35),(.87,-.51,4.35),(.98,-.51,3.81),(.64,-.61,3.89),(-.69,-.61,4.08)],.12,'sand')

def crustacean():
    hermit=ID=='hermit-crab';scorpion=ID=='scorpion';thrower=ID=='rock-throwing-crab'
    mat='sand' if scorpion else 'teal' if thrower else 'coral'
    bone('Body',(0,0,1.0))
    ell('Body',(0,0,1.13),(1.14,1.0,.53),'cream' if not scorpion else 'russet',20,10)
    ell('Body',(0,.02,1.43),(1.23,1.03,.38),mat,20,10)
    if not scorpion and not hermit:
        for i in range(12):
            a=math.tau*i/12
            ell('Body',(math.cos(a)*1.07,math.sin(a)*.87,1.47),(.23,.21,.13),mat,8,6)
    if scorpion:
        for j in range(4):ell('Body',(0,.05+j*.25,1.47),(.85-j*.09,.25,.22),'sand',12,6)
    for s in [-1,1]:
        for i in range(3 if hermit else 4):
            y=-.40+i*.40
            a=(s*.90,y,1.17);b=(s*(1.52+(.15 if i in [1,2] else 0)),y+.05,.94);c=(s*(1.85+(.12 if i in [1,2] else 0)),y-.12,.045)
            upper=f'{sides(s)}Leg{i}Upper';lower=f'{sides(s)}Leg{i}Lower'
            bone(upper,a,'Body');bone(lower,b,upper)
            tube(upper,[a,((a[0]+b[0])/2,y,1.22),b],[.17,.20,.12],mat)
            tube(lower,[b,((b[0]+c[0])/2,y,.53),c],[.15,.17,.027],mat)
        a=(s*.84,-.66,1.15);b=(s*1.22,-1.19,1.04);c=(s*1.38,-1.78,1.19)
        g=sides(s)+'Arm';hand=sides(s)+'Claw';jaw=sides(s)+'Pincer'
        bone(g,a,'Body');bone(hand,b,g);bone(jaw,c,hand)
        tube(g,[a,b],[.24,.28],mat,10)
        ell(hand,(s*1.36,-1.53,1.16),(.45,.40,.37),mat,16,10)
        tube(hand,[(s*1.64,-1.66,1.14),(s*1.82,-2.03,1.15),(s*1.70,-2.38,1.13),(s*1.48,-2.56,1.12)],[.28,.25,.16,.022],mat,8)
        tube(jaw,[(s*1.11,-1.72,1.16),(s*.99,-2.08,1.18),(s*1.08,-2.38,1.15),(s*1.25,-2.51,1.12)],[.23,.20,.12,.022],'russet' if scorpion else mat,8)
        if not scorpion:
            tube('Body',[(s*.40,-.66,1.60),(s*.46,-.73,2.04)],[.11,.09],mat,8)
            ell('Body',(s*.46,-.77,2.09),(.15,.13,.20),'dark',12,8)
            ell('Body',(s*.48,-.878,2.15),(.032,.018,.045),'white',8,6)
        else:
            ell('Body',(s*.32,-.83,1.49),(.16,.09,.105),'amber',10,6)
    if hermit:
        # Solid shell volume with a raised spiral ridge; no hollow doughnut gap.
        ell('Body',(0,.48,2.12),(1.28,1.12,1.39),'cream',24,16)
        path=[];r=[]
        for i in range(65):
            t=i/64;a=.1+t*math.pi*4.2;radius=1.16*(1-t)+.035
            path.append((math.cos(a)*radius,-.35-.29*t,2.30+math.sin(a)*radius))
            r.append(.16*(1-t)+.045)
        tube('Body',path,r,'sand',8)
        ell('Body',(0,-.64,1.79),(.74,.10,.40),'brown',16,8)
        lip=[]
        for i in range(17):
            a=i*math.pi/16;lip.append((math.cos(a)*.82,-.70,1.71+math.sin(a)*.51))
        tube('Body',lip,.11,'cream',8)
    if scorpion:
        path=[(0,.75,1.38),(0,1.27,1.60),(0,1.50,2.12),(0,1.43,2.67),(0,1.09,3.04),(0,.51,3.14),(0,-.04,2.88),(0,-.28,2.48)]
        for i in range(len(path)-1):
            g=f'Tail{i}';bone(g,path[i],'Body' if i==0 else f'Tail{i-1}')
            tube(g,[path[i],tuple(Vector(path[i]).lerp(Vector(path[i+1]),.55)),path[i+1]],[.26-i*.022,.29-i*.024,.19-i*.022],'russet' if i%2 else 'sand',8)
        tip('Tail6',path[-1],(0,-.43,2.12),.15,'russet')
    if thrower:
        # Larger throwing claw, independent rock is authored as a projectile later.
        pivot=Vector(bones['RightClaw']['head'])
        for g in ['RightClaw','RightPincer']:
            for o in parts[g]:
                for v in o.data.vertices:
                    world=o.matrix_world@v.co;world=pivot+(world-pivot)*1.3;v.co=o.matrix_world.inverted()@world

def spider():
    bone('Body',(0,0,1));ell('Body',(0,.63,1.31),(.92,1.05,.84),'charcoal',20,12)
    ell('Body',(0,-.48,1.05),(.76,.73,.55),'charcoal',16,10)
    # Broad raised ember plates are intentional shell markings.
    for x,y,z,s in [(0,.57,2.09,(.40,.64,.055)),(-.61,.71,1.77,(.22,.45,.15)),(.61,.71,1.77,(.22,.45,.15)),(0,-.45,1.58,(.32,.41,.045))]:ell('Body',(x,y,z),s,'orange',12,6)
    for s in [-1,1]:
        for i in range(4):
            y=-.66+i*.38;a=(s*.55,y,1.1);b=(s*(1.20+.18*math.sin(i)),y+(i-1.5)*.30,1.35);c=(s*(1.65+.19*math.sin(i)),y+(i-1.5)*.40,.03)
            g=f'{sides(s)}Leg{i}Upper';lower=f'{sides(s)}Leg{i}Lower';bone(g,a,'Body');bone(lower,b,g)
            tube(g,[a,b],[.17,.19],'charcoal');tube(lower,[b,tuple(Vector(b).lerp(Vector(c),.5)),c],[.18,.15,.024],'charcoal')
            p=tuple(Vector(a).lerp(Vector(b),.54));ell(g,p,(.15,.17,.16),'orange',8,6)
        ell('Body',(s*.26,-1.07,1.20),(.21,.105,.22),'amber',12,8)
        ell('Body',(s*.53,-.96,1.39),(.08,.06,.09),'amber',10,6)
        bone(sides(s)+'Fang',(s*.22,-1.05,.86),'Body')
        tube(sides(s)+'Fang',[(s*.22,-1.05,.86),(s*.34,-1.19,.58),(s*.16,-1.28,.50)],[.15,.12,.014],'charcoal')

def snake():
    # Smooth skin weights along a continuous tube; no bead-chain body.
    path=[]
    for i in range(33):
        t=i/32
        radius=.39*(1-t)+.045
        path.append((.91*math.sin(t*math.pi*2.2)*min(1,t*3),-.9+3.2*t,radius+1.61*math.exp(-t*11)))
    radii=[.39*(1-i/32)+.045 for i in range(33)]
    o=tube('Spine0',path,radii,'olive',12)
    o['snake_skin']=True
    for i in range(9):bone(f'Spine{i}',path[min(i*4,32)],'Root' if i==0 else f'Spine{i-1}')
    # Continuous belly strip on the original mesh, rather than detached beads.
    belly_index=len(o.data.materials);o.data.materials.append(mats['cream'])
    for poly in o.data.polygons:
        if poly.normal.y<-.50 or poly.normal.z<-.60:poly.material_index=belly_index
    bone('Head',path[0],'Spine0')
    box('Head',(0,-1.10,2.11),(.94,1.0,.50),'olive',.19)
    ell('Head',(0,-1.30,1.95),(.40,.34,.12),'cream',14,8)
    for s in [-1,1]:
        ell('Head',(s*.40,-1.34,2.19),(.075,.15,.13),'dark',12,8)
        tip('Head',(s*.24,-1.47,1.96),(s*.23,-1.48,1.75),.06,'ivory')

def ghost():
    bone('Body',(0,0,1.8));bone('Head',(0,0,2.75),'Body')
    loft('Body',[(0,0,.37,1.82,1.25),(0,0,.83,1.56,1.10),(0,0,1.65,1.08,.81),(0,0,2.68,.91,.76)],'skin',.35)
    box('Head',(0,0,3.08),(1.62,1.32,1.49),'fur',.26)
    eyes('Head',3.14,-.688,.38,'cyan',.23)
    for s in [-1,1]:
        g=sides(s)+'Arm';bone(g,(s*.60,0,2.21),'Body')
        tube(g,[(s*.60,0,2.21),(s*.99,-.09,1.91),(s*1.04,-.24,1.68)],[.31,.32,.16],'skin',10)
    for s in [-1,1]:tuft('Body',(s*.36,-.48,1.36),(.20*s,-.02,-.80),'blue',.29)

def slime():
    bone('Body',(0,0,.3));bone('Crown',(0,0,1.22),'Body')
    levels=[(0,0,.02,2.70,2.04),(0,0,.24,2.89,2.18),(.05,0,.75,2.51,1.93),(.07,.02,1.32,2.08,1.63),(.12,.04,1.86,1.27,1.15),(.12,.04,2.04,.28,.32)]
    loft('Body',levels,'orange')
    eyes('Body',1.22,-.94,.41,'amber',.20)
    ell('Body',(0,-1.018,.79),(.20,.035,.075),'dark',12,6)
    for p,s in [((.11,.05,1.96),(.61,.51,.17)),((-.77,.02,1.40),(.28,.49,.30)),((.82,.0,.90),(.37,.60,.19)),((-.69,.73,.59),(.45,.32,.23)),((.09,.77,1.28),(.57,.31,.42))]:
        ell('Crown' if p[2]>1.6 else 'Body',p,s,'charcoal',10,6)

if ID in ['crab','hermit-crab','rock-throwing-crab','scorpion']:crustacean()
elif ID=='ember-spider':spider()
elif ID=='snake':snake()
elif ID=='frost-ghost':ghost()
elif ID=='lava-slime':slime()
else:humanoid()

# Finalize UV atlas and armature, animation and exports in shared delivery module.
exec(compile((ROOT/'deliver.py').read_text(),str(ROOT/'deliver.py'),'exec'))
