import bpy,bmesh,sys,json,math,numpy as np
from pathlib import Path
from mathutils import Vector,Quaternion,Matrix
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parent;ID=sys.argv[sys.argv.index('--')+1];OUT=ROOT/ID
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Model.blend'))
scene=bpy.context.scene;data=json.loads((OUT/'anatomy.json').read_text());rig=bpy.data.objects['Rig']
meshes=[o for o in scene.objects if o.type=='MESH' and o.parent==rig]
spec={b.name:[list(b.head_local),list(b.tail_local),b.parent.name if b.parent else None] for b in rig.data.bones if b.name!='Root'}
if 'spinePath' in data:nb=data['spineBones']
rig.animation_data_clear()
for a in list(bpy.data.actions):bpy.data.actions.remove(a)
for p in rig.pose.bones:p.location=(0,0,0);p.rotation_quaternion=(1,0,0,0);p.scale=(1,1,1)
def activate(objects):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
skin=next((o for o in meshes if o.get('smooth_skin')),None)
if skin:
    # Bone heat follows the continuous skin surface, avoiding the torso-to-arm
    # bleed that a nearest-axis weighting can create at broad shoulders.
    old_weights=[[(skin.vertex_groups[g.group].name,g.weight) for g in v.groups] for v in skin.data.vertices]
    for vg in list(skin.vertex_groups):skin.vertex_groups.remove(vg)
    activate([rig,skin]);bpy.context.view_layer.objects.active=rig
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    if any(not v.groups for v in skin.data.vertices):
        for vg in list(skin.vertex_groups):skin.vertex_groups.remove(vg)
        for n in spec:skin.vertex_groups.new(name=n)
        for i,ww in enumerate(old_weights):
            for n,wgt in ww:skin.vertex_groups[n].add([i],wgt,'REPLACE')
        print('HEAT_FALLBACK',ID,flush=True)
    else:print('HEAT_BOUND',ID,flush=True)
    mods=[m for m in skin.modifiers if m.type=='ARMATURE']
    for mod in mods[1:]:skin.modifiers.remove(mod)
    names=list(spec);inds={n:i for i,n in enumerate(names)};w=np.zeros((len(skin.data.vertices),len(names)),dtype=float)
    for v in skin.data.vertices:
        for g in v.groups:w[v.index,inds[skin.vertex_groups[g.group].name]]=g.weight
    if ID=='fire-goblin':
        # Explicit anatomy regions for the short goblin. Bone heat cannot solve
        # its close-set hands reliably, and axis distance lets the arm grab ribs.
        def smooth(a,b,x):
            t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
        for v in skin.data.vertices:
            x,y,z=v.co;side='Right' if x>0 else 'Left';arm=smooth(.88,1.25,abs(x));leg=1-smooth(2.02,2.45,z)
            chest=smooth(2.68,3.08,z);torso={'Pelvis':1-chest,'Chest':chest}
            knee=smooth(1.20,1.60,z);foot=1-smooth(.38,.65,z)
            limb={side+'Thigh':knee*(1-foot),side+'Shin':(1-knee)*(1-foot),side+'Foot':foot}
            elbow=smooth(2.77,3.14,z);hand=1-smooth(2.12,2.45,z)
            arms={side+'UpperArm':elbow*(1-hand),side+'Forearm':(1-elbow)*(1-hand),side+'Hand':hand}
            row={}
            for n,value in torso.items():row[n]=value*(1-arm)*(1-leg)
            for n,value in limb.items():row[n]=value*(1-arm)*leg
            for n,value in arms.items():row[n]=value*arm
            w[v.index]=0
            for n,value in row.items():w[v.index,inds[n]]=value
    if ID=='obsidian-ogre':
        # The thick chest/back must not inherit arm weights just because its
        # surface is nearer the shoulder bone than the central chest axis.
        def smooth(a,b,x):
            t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
        for vertex in skin.data.vertices:
            x,y,z=vertex.co;side='Right' if x>0 else 'Left'
            arm=smooth(1.48,1.98,abs(x));leg=1-smooth(2.80,3.27,z)
            chest=smooth(3.45,4.08,z);neck=smooth(5.77,6.15,z)
            torso={'Pelvis':1-chest,'Chest':chest*(1-neck),'Head':chest*neck}
            knee=smooth(1.60,2.07,z);foot=1-smooth(.38,.84,z)
            legs={side+'Thigh':knee*(1-foot),side+'Shin':(1-knee)*(1-foot),side+'Foot':foot}
            elbow=smooth(3.83,4.43,z);hand=1-smooth(2.98,3.42,z)
            arms={side+'UpperArm':elbow*(1-hand),side+'Forearm':(1-elbow)*(1-hand),side+'Hand':hand}
            row={}
            for n,value in torso.items():row[n]=value*(1-arm)*(1-leg)
            for n,value in legs.items():row[n]=value*(1-arm)*leg
            for n,value in arms.items():row[n]=value*arm
            w[vertex.index]=0
            for n,value in row.items():w[vertex.index,inds[n]]=value
    if ID=='werewolf':
        # Fur skin regions. Below the armpit the arms hang clear of the torso,
        # so a sharp |x| split is safe; the face ruff (ManeMask) stays on the
        # Chest/Head even where its shards flare out past the shoulders.
        def smooth(a,b,x):
            t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
        mane=skin.data.attributes.get('ManeMask');mane=[d.value for d in mane.data] if mane else [0]*len(skin.data.vertices)
        for vertex in skin.data.vertices:
            x,y,z=vertex.co;side='Right' if x>0 else 'Left';ax=abs(x)
            t=smooth(3.9,4.7,z);arm=smooth(1.12+.10*t,1.25+.37*t,ax) if z>2.1 else 0
            if mane[vertex.index]>.5 and z>4.9:arm=0
            leg=1-smooth(2.55,3.0,z)
            chest=smooth(3.25,3.95,z);head=smooth(5.35,5.80,z)
            torso={'Pelvis':1-chest,'Chest':chest*(1-head),'Head':chest*head}
            knee=smooth(1.35,1.80,z);foot=1-smooth(.50,.78,z)
            legs={side+'Thigh':knee*(1-foot),side+'Shin':(1-knee)*(1-foot),side+'Foot':foot}
            elbow=smooth(3.50,3.95,z);hand=1-smooth(2.62,2.86,z)
            arms={side+'UpperArm':elbow*(1-hand),side+'Forearm':(1-elbow)*(1-hand),side+'Hand':hand}
            row={}
            for n,value in torso.items():row[n]=row.get(n,0)+value*(1-arm)*(1-leg)
            for n,value in legs.items():row[n]=row.get(n,0)+value*(1-arm)*leg
            for n,value in arms.items():row[n]=row.get(n,0)+value*arm
            w[vertex.index]=0
            for n,value in row.items():w[vertex.index,inds[n]]=value
    edges=np.array([list(e.vertices) for e in skin.data.edges],dtype=int);src=np.concatenate((edges[:,0],edges[:,1]));dst=np.concatenate((edges[:,1],edges[:,0]));degree=np.bincount(src,minlength=len(w))[:,None]
    for _ in range(5):
        accum=np.zeros_like(w);np.add.at(accum,src,w[dst]);w=.52*w+.48*accum/np.maximum(1,degree)
    for v in skin.data.vertices:
        for g in data.get('grips',[]):
            if (v.co-Vector(g['center'])).length<.47:w[v.index]=0;w[v.index,inds[g['bone']]]=1
        if ID=='fire-goblin' and abs(v.co.x)>1.04 and 1.65<v.co.z<2.29:
            # The complete palm/finger envelope follows the hand as one fist.
            # Blending remains in the narrow wrist above the metacarpals.
            side='Right' if v.co.x>0 else 'Left'
            w[v.index]=0;w[v.index,inds[side+'Hand']]=1
    for vg in list(skin.vertex_groups):skin.vertex_groups.remove(vg)
    for n in names:skin.vertex_groups.new(name=n)
    for i,row in enumerate(w):
        chosen=np.argsort(row)[-4:];total=float(sum(row[j] for j in chosen))
        for j in chosen:
            if row[j]>.000001:skin.vertex_groups[names[j]].add([i],float(row[j]/total),'REPLACE')
    tree=KDTree(len(skin.data.vertices))
    for v in skin.data.vertices:tree.insert(v.co,v.index)
    tree.balance()
    for o in meshes:
        cloth_names=('Sleeveless ragged vest','Short torn tunic','Fitted robe torso','Front robe panel','Robe lower drape','Ragged hide panel')
        transfer_cloth=o.name.startswith(cloth_names) or o.name in ['Chest_Geometry','Pelvis_Geometry']
        if ID=='fire-goblin' and o.get('rigid_bone'):transfer_cloth=False
        if o==skin or (o.get('rigid_bone') and not transfer_cloth):continue
        for vg in list(o.vertex_groups):o.vertex_groups.remove(vg)
        for n in names:o.vertex_groups.new(name=n)
        for v in o.data.vertices:
            _,i,_=tree.find(v.co)
            for g in skin.data.vertices[i].groups:o.vertex_groups[skin.vertex_groups[g.group].name].add([v.index],g.weight,'REPLACE')
exec('scene.render.fps=24'+(ROOT/'rig_export.py').read_text().split('scene.render.fps=24',1)[1],globals())
