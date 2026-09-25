"""Rig the separately authored sculptures, bake their materials, export and inspect.
The procedural Sculpt.blend remains untouched. No Studio scene is modified.
"""
import bpy,bmesh,sys,json,math,hashlib,time
from pathlib import Path
from mathutils import Vector,Quaternion,Matrix
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parent
ID=sys.argv[sys.argv.index('--')+1];OUT=ROOT/ID
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Sculpt.blend'))
scene=bpy.context.scene;data=json.loads((OUT/'anatomy.json').read_text())
meshes=[o for o in scene.objects if o.type=='MESH' and not any(c.name=='REVIEW_ONLY' for c in o.users_collection)]
def activate(objects):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
for o in meshes:
    activate([o]);bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    for i,m in enumerate(list(o.data.materials)):
        if m is None:o.data.materials[i]=next(m for m in o.data.materials if m)
    # The primitives and solids are authored closed; weld exact coincident seams.
    bm=bmesh.new();bm.from_mesh(o.data)
    if not o.get('transfer_skin'):bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free()
if 'spinePath' in data:
    path=[Vector(p) for p in data['spinePath']];nb=data['spineBones'];spec={}
    # Root is the tail; each successive parent carries the nearer neck segment.
    for j in range(nb-1,-1,-1):
        a=path[round((j+1)/nb*(len(path)-1))];b=path[round(j/nb*(len(path)-1))]
        spec[f'Spine{j}']=[list(a),list(b),f'Spine{j+1}' if j<nb-1 else None]
    spec['Head']=[list(path[0]),[0,-2.13,2.78],'Spine0']
else:spec=data['bones']
arm=bpy.data.armatures.new(ID+'_Anatomy');rig=bpy.data.objects.new('Rig',arm);scene.collection.objects.link(rig)
activate([rig]);bpy.ops.object.mode_set(mode='EDIT')
root=arm.edit_bones.new('Root');root.head=(0,0,0);root.tail=(0,0,.3);root.use_deform=False
for name,(a,b,parent) in spec.items():
    eb=arm.edit_bones.new(name);eb.head=a;eb.tail=b
    if (Vector(b)-Vector(a)).length<.015:eb.tail=Vector(a)+Vector((0,0,.1))
for name,(a,b,parent) in spec.items():arm.edit_bones[name].parent=arm.edit_bones[parent or 'Root']
bpy.ops.object.mode_set(mode='OBJECT')
rig.show_in_front=True
def weights(o,values):
    for g in list(o.vertex_groups):o.vertex_groups.remove(g)
    groups={n:o.vertex_groups.new(name=n) for n in spec}
    for i,ww in enumerate(values):
        top=sorted(((n,w) for n,w in ww.items() if w>.00001),key=lambda x:-x[1])[:4];total=sum(w for n,w in top)
        if not total:raise RuntimeError('Unweighted vertex '+o.name)
        for n,w in top:groups[n].add([i],w/total,'REPLACE')
def segment_dist(p,a,b):
    v=b-a;t=max(0,min(1,(p-a).dot(v)/max(v.length_squared,1e-8)))
    return (p-a-v*t).length
segments={n:(Vector(a),Vector(b)) for n,(a,b,pa) in spec.items()}
skin=next((o for o in meshes if o.get('smooth_skin')),None)
if skin:
    # Smooth capsule-distance weights are deterministic and use the actual joint
    # positions. Restrict blend to the closest bone and its connected neighbors.
    adjacency={n:{n} for n in spec}
    for n,(a,b,pa) in spec.items():
        if pa:adjacency[n].add(pa);adjacency[pa].add(n)
    vals=[]
    for v in skin.data.vertices:
        ds={n:segment_dist(v.co,*ab) for n,ab in segments.items()}
        near=min(ds,key=ds.get);allowed=adjacency[near]
        scores={n:1/max(.11,ds[n])**5 for n in allowed}
        # A closed grasp must have exactly the same transform as its prop.
        for g in data.get('grips',[]):
            c=Vector(g['center'])
            if (v.co-c).length<.48:scores={g['bone']:1}
        vals.append(scores)
    weights(skin,vals)
    tree=KDTree(len(skin.data.vertices))
    for v in skin.data.vertices:tree.insert(v.co,v.index)
    tree.balance()
    def nearest_skin(p):
        _,i,_=tree.find(p);v=skin.data.vertices[i]
        return {skin.vertex_groups[g.group].name:g.weight for g in v.groups}
if 'spinePath' in data:
    treepath=KDTree(len(path))
    for i,p in enumerate(path):treepath.insert(p,i)
    treepath.balance()
for o in meshes:
    if o==skin:continue
    if o.get('bow_string'):
        weights(o,[{'BowDraw':1} if abs(v.co.z-2.72)<.3 else {'LeftHand':1} for v in o.data.vertices])
    elif o.get('rigid_bone'):
        name=o['rigid_bone'];weights(o,[{name:1}]*len(o.data.vertices))
    elif o.get('spine_skin'):
        vv=[]
        for v in o.data.vertices:
            _,i,_=treepath.find(v.co);t=i/(len(path)-1)*nb-.5;j=max(0,min(nb-1,int(math.floor(t))));k=min(nb-1,j+1);f=max(0,min(1,t-j))
            d={f'Spine{j}':1-f};d[f'Spine{k}']=d.get(f'Spine{k}',0)+f;vv.append(d)
        weights(o,vv)
    elif o.get('slime_skin'):
        vv=[]
        for v in o.data.vertices:
            w=max(0,min(1,(v.co.z-.4)/1.8));vv.append({'Body':1-w,'Crown':w})
        weights(o,vv)
    elif skin:weights(o,[nearest_skin(v.co) for v in o.data.vertices])
    else:raise RuntimeError('Missing binding '+o.name)
for o in meshes:
    mod=o.modifiers.new('Anatomical skin','ARMATURE');mod.object=rig;o.parent=rig
print('BINDINGS_COMPLETE',ID,flush=True)

# All surfaces receive unique UV islands in one atlas. Bake the actual procedural
# sculpture colors; do not reuse an unrelated generic color-tile image.
activate(meshes);bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=1.05,island_margin=.006,area_weight=.6,correct_aspect=True,scale_to_bounds=False)
bpy.ops.uv.pack_islands(rotate=True,margin=.0025)
bpy.ops.object.mode_set(mode='OBJECT')
image=bpy.data.images.new(ID+'_BaseColor',width=2048,height=2048,alpha=False)
image.generated_color=(.02,.02,.02,1)
original_materials=set(m for o in meshes for m in o.data.materials if m)
for m in original_materials:
    node=m.node_tree.nodes.new('ShaderNodeTexImage');node.image=image;m.node_tree.nodes.active=node;node.select=True
scene.render.engine='CYCLES';scene.cycles.samples=1
scene.render.bake.use_clear=False;scene.render.bake.margin=4
bpy.ops.object.bake(type='DIFFUSE',pass_filter={'COLOR'},use_clear=False,margin=4)
image.filepath_raw=str(OUT/'BaseColor.png');image.file_format='PNG';image.save();image.pack()
normal_image=None
if ID=='obsidian-ogre':
    normal_image=bpy.data.images.new(ID+'_StoneNormal',width=2048,height=2048,alpha=False)
    normal_image.colorspace_settings.name='Non-Color';normal_image.generated_color=(.5,.5,1,1)
    for m in original_materials:
        node=m.node_tree.nodes.new('ShaderNodeTexImage');node.image=normal_image;m.node_tree.nodes.active=node
    scene.render.bake.normal_space='TANGENT'
    bpy.ops.object.bake(type='NORMAL',use_clear=False,margin=4)
    normal_image.filepath_raw=str(OUT/'Normal.png');normal_image.file_format='PNG';normal_image.save();normal_image.pack()
painted={}
def painted_mat(key):
    if key in painted:return painted[key]
    m=bpy.data.materials.new(ID+'_'+key);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Roughness'].default_value=.28 if key=='Eyes' else (.34 if key=='Metal' else .86);p.inputs['Specular IOR Level'].default_value=.18
    if key=='Metal':p.inputs['Metallic'].default_value=.72
    t=m.node_tree.nodes.new('ShaderNodeTexImage');t.image=image;m.node_tree.links.new(t.outputs['Color'],p.inputs['Base Color'])
    if normal_image:
        tex=m.node_tree.nodes.new('ShaderNodeTexImage');tex.image=normal_image
        normal=m.node_tree.nodes.new('ShaderNodeNormalMap');normal.inputs['Strength'].default_value=1
        m.node_tree.links.new(tex.outputs['Color'],normal.inputs['Color']);m.node_tree.links.new(normal.outputs['Normal'],p.inputs['Normal'])
    if key=='Ember':m.node_tree.links.new(t.outputs['Color'],p.inputs['Emission Color']);p.inputs['Emission Strength'].default_value=.25
    painted[key]=m;return m
for o in meshes:
    for i,m in enumerate(list(o.data.materials)):
        if m is None:continue
        bs=m.node_tree.nodes.get('Principled BSDF')
        key='Ember' if bs.inputs['Emission Strength'].default_value>0 else ('Metal' if bs.inputs['Metallic'].default_value>.4 else ('Eyes' if bs.inputs['Roughness'].default_value<.5 else 'Painted'))
        o.data.materials[i]=painted_mat(key)
print('BAKE_COMPLETE',ID,flush=True)

# Join only compatible rigid pieces; leave continuous skins intact. Split the
# thousands of independent snake shields by material to keep each mesh <20k tris.
grouped={}
for o in meshes:
    key=o.get('rigid_bone')
    if key and not o.get('held_projectile'):grouped.setdefault(key,[]).append(o)
for key,objects in grouped.items():
    activate(objects);bpy.ops.object.join();bpy.context.object.name=key+'_Geometry'
meshes=[o for o in scene.objects if o.type=='MESH' and o.parent==rig]
# Disconnected closed components can be split without cutting a surface.
for o in list(meshes):
    o.data.calc_loop_triangles()
    if len(o.data.loop_triangles)<=20000:continue
    bm=bmesh.new();bm.from_mesh(o.data);bm.verts.ensure_lookup_table();unseen=set(bm.verts);components=[]
    while unseen:
        seed=unseen.pop();stack=[seed];comp=[seed.index]
        while stack:
            v=stack.pop()
            for e in v.link_edges:
                w=e.other_vert(v)
                if w in unseen:unseen.remove(w);stack.append(w);comp.append(w.index)
        components.append(comp)
    bm.free()
    if len(components)==1:raise RuntimeError('Continuous mesh exceeds triangle budget: '+o.name)
    buckets=[];bucket=[];count=0
    for comp in components:
        if count+len(comp)>6000 and bucket:buckets.append(bucket);bucket=[];count=0
        bucket+=comp;count+=len(comp)
    if bucket:buckets.append(bucket)
    for i,indices in enumerate(buckets):
        cp=o.copy();cp.data=o.data.copy();scene.collection.objects.link(cp);cp.name=o.name+'_'+str(i)
        keep=set(indices);bm=bmesh.new();bm.from_mesh(cp.data);bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if v.index not in keep],context='VERTS');bm.to_mesh(cp.data);bm.free()
    bpy.data.objects.remove(o,do_unlink=True)
meshes=[o for o in scene.objects if o.type=='MESH' and o.parent==rig]

scene.render.fps=24
for p in rig.pose.bones:p.rotation_mode='QUATERNION'
def rot(name,deg,axis=(1,0,0)):
    if name not in rig.pose.bones:return
    pb=rig.pose.bones[name];local=pb.bone.matrix_local.to_3x3().inverted()@Vector(axis)
    pb.rotation_quaternion=Quaternion(local.normalized(),math.radians(-deg if axis==(1,0,0) else deg))
def move(name,world_vector):
    pb=rig.pose.bones[name];pb.location=pb.bone.matrix_local.to_3x3().inverted()@Vector(world_vector)
def arm_target(side,rest_center,center,q):
    upper=rig.pose.bones[side+'UpperArm'];fore=rig.pose.bones[side+'Forearm'];hand=rig.pose.bones[side+'Hand']
    s=upper.bone.head_local.copy();e0=fore.bone.head_local.copy();w0=hand.bone.head_local.copy()
    wrist=Vector(center)+q@(w0-Vector(rest_center));delta=wrist-s;distance=delta.length;d=delta.normalized()
    l1=(e0-s).length;l2=(w0-e0).length;distance=max(abs(l1-l2)+.001,min(l1+l2-.001,distance));wrist=s+d*distance
    along=(l1*l1-l2*l2+distance*distance)/(2*distance);height=math.sqrt(max(0,l1*l1-along*along))
    pole=Vector((1,-.65,.25)) if side=='Right' else Vector((-1,-.25,-.35));pole=(pole-d*pole.dot(d)).normalized();elbow=s+d*along+pole*height
    qu=(e0-s).rotation_difference(elbow-s);qf=(w0-e0).rotation_difference(wrist-elbow)
    upper.matrix=Matrix.Translation(s)@qu.to_matrix().to_4x4()@upper.bone.matrix_local.to_3x3().to_4x4();bpy.context.view_layer.update()
    fore.matrix=Matrix.Translation(elbow)@qf.to_matrix().to_4x4()@fore.bone.matrix_local.to_3x3().to_4x4();bpy.context.view_layer.update()
    hand.matrix=Matrix.Translation(wrist)@q.to_matrix().to_4x4()@hand.bone.matrix_local.to_3x3().to_4x4();bpy.context.view_layer.update()

def straight_draw_arm(rest_center,center,amount):
    """Solve to the drawing fingers with wrist rotation coupled to forearm.

    Treat the forearm plus aligned hand as one effective second IK segment.
    This reaches the string without independently tilting the hand beneath it.
    """
    upper=rig.pose.bones['RightUpperArm'];fore=rig.pose.bones['RightForearm'];hand=rig.pose.bones['RightHand']
    s=upper.bone.head_local.copy();e0=fore.bone.head_local.copy();w0=hand.bone.head_local.copy()
    fore_rest=w0-e0;hand_rest=hand.bone.tail_local-w0
    align=Quaternion((1,0,0,0)).slerp(hand_rest.rotation_difference(fore_rest),amount)
    effective=fore_rest+align@(Vector(rest_center)-w0)
    delta=Vector(center)-s;d=delta.normalized();l1=(e0-s).length;l2=effective.length
    distance=max(abs(l1-l2)+.001,min(l1+l2-.001,delta.length));grip=s+d*distance
    along=(l1*l1-l2*l2+distance*distance)/(2*distance);height=math.sqrt(max(0,l1*l1-along*along))
    pole=Vector((1,-.65,.25));pole=(pole-d*pole.dot(d)).normalized();elbow=s+d*along+pole*height
    qu=(e0-s).rotation_difference(elbow-s);qf=effective.rotation_difference(grip-elbow);qh=qf@align
    wrist=elbow+qf@fore_rest
    upper.matrix=Matrix.Translation(s)@qu.to_matrix().to_4x4()@upper.bone.matrix_local.to_3x3().to_4x4();bpy.context.view_layer.update()
    fore.matrix=Matrix.Translation(elbow)@qf.to_matrix().to_4x4()@fore.bone.matrix_local.to_3x3().to_4x4();bpy.context.view_layer.update()
    hand.matrix=Matrix.Translation(wrist)@qh.to_matrix().to_4x4()@hand.bone.matrix_local.to_3x3().to_4x4();bpy.context.view_layer.update()
def pose(clip,t):
    for p in rig.pose.bones:p.location=(0,0,0);p.rotation_quaternion=(1,0,0,0);p.scale=(1,1,1)
    wave=math.sin(t*math.tau);pulse=math.sin(t*math.pi)
    base='Pelvis' if 'Pelvis' in spec else ('Body' if 'Body' in spec else 'Root')
    if clip=='Idle':
        move(base,(0,0,.018*wave))
        rot('Chest',1.3*wave);rot('Head',1*wave)
        if base=='Body':rot('Body',1.2*wave,(0,1,0))
    elif clip=='Move':
        if 'Pelvis' in spec:
            move(base,(0,0,.035*(1-math.cos(t*math.tau*2))))
            for side,s in [('Left',-1),('Right',1)]:
                rot(side+'Thigh',s*23*wave);rot(side+'Shin',-max(0,s*wave)*22);rot(side+'UpperArm',-s*11*wave)
        elif data.get('crab'):
            for side,s in [('Left',-1),('Right',1)]:
                for j in range(4):
                    w=math.sin(t*math.tau+j*math.pi/2)*s;rot(side+f'Leg{j}Upper',12*w,(0,0,1));rot(side+f'Leg{j}Lower',max(0,w)*12,(0,1,0))
        elif data.get('slime'):
            rig.pose.bones['Body'].scale=(1+.065*wave,1-.095*wave,1+.065*wave);move('Root',(0,0,.045*(1-wave)))
        else:
            for j in range(nb):rot(f'Spine{j}',2.1*math.sin(t*math.tau-j*.53),(0,0,1))
    elif clip=='Attack':
        wind=math.sin(min(t/.38,1)*math.pi/2) if t<.38 else (1-(t-.38)/.62)
        impact=math.sin(max(0,min(1,(t-.32)/.68))*math.pi)
        if ID=='snake':
            move('Root',(0,-.75*math.sin(t*math.pi)**4,0))
            rot('Spine0',-9*impact);rot('Head',8*impact)
        elif data.get('slime'):
            rig.pose.bones['Body'].scale=(1+.13*pulse,1-.2*pulse,1+.13*pulse);move('Root',(0,-.32*pulse,0))
        elif data.get('crab'):
            rot('RightArm',-22*wind+63*impact);rot('RightForearm',-12*wind+23*impact)
        elif ID=='ash-shaman':
            rot('LeftUpperArm',26*impact);rot('LeftForearm',18*impact);rot('RightUpperArm',8*impact);rot('Chest',-4*wind+6*impact)
        elif ID=='spitter-zombie':rot('Head',-12*wind+24*impact);rot('Chest',-5*wind+10*impact)
        elif ID=='bow-skeleton':
            def ease(x):
                x=max(0,min(1,x));return x*x*(3-2*x)
            strength=ease(t/.25) if t<.79 else ease((1-t)/.21)
            pull=ease((t-.25)/.25)
            release=ease((t-14/24)/(2/24))
            direction=Vector((-.9,-math.sqrt(.19),0));rest_direction=Vector((-.55,-.835,0)).normalized()
            bowrest=Vector((-1.44,-.40,2.72));arrowrest=Vector((1.44,-.33,2.67))
            bowtarget=Vector((-.25,-1.00,4.12)).lerp(Vector((-.98,-1.50,4.12)),pull)
            arrowtarget=bowtarget-direction*(.42+.84*pull+.10*release)
            qb=Quaternion((1,0,0,0)).slerp(rest_direction.rotation_difference(direction),strength)
            bc=bowrest.lerp(bowtarget,strength);ac=arrowrest.lerp(arrowtarget,strength)
            arm_target('Left',bowrest,bc,qb);straight_draw_arm(arrowrest,ac,strength)
            if 'BowDraw' in rig.pose.bones:
                left=rig.pose.bones['LeftHand'];right=rig.pose.bones['RightHand'];pb=rig.pose.bones['BowDraw']
                neutral=left.matrix@left.bone.matrix_local.inverted()@pb.bone.head_local
                hand_center=right.matrix@right.bone.matrix_local.inverted()@arrowrest
                # Use the solved hand position, not the unreachable IK request.
                nock=neutral.lerp(hand_center,strength*(1-release))
                mat=pb.matrix.copy();mat.translation=nock;pb.matrix=mat;bpy.context.view_layer.update()
        else:
            rot('RightUpperArm',-38*wind+95*impact);rot('RightForearm',-24*wind+24*impact);rot('Chest',-4*wind+8*impact)
    elif clip=='Hit':rot(base,-8*pulse);rot('Head',-9*pulse)
    elif clip=='Death':
        # Collapse within the root footprint; the final root height is intentional.
        rot('Root',-78*t);move('Root',(0,0,.30*t));rot('Head',16*t)
    return
actions={};lengths={'Idle':33,'Move':25,'Attack':25,'Hit':13,'Death':25}
rig.animation_data_create()
for clip,end in lengths.items():
    action=bpy.data.actions.new(clip);rig.animation_data.action=action
    for f in range(1,end+1):
        t=(f-1)/(end-1);pose(clip,t)
        for p in rig.pose.bones:
            p.keyframe_insert('location',frame=f,group=p.name);p.keyframe_insert('rotation_quaternion',frame=f,group=p.name);p.keyframe_insert('scale',frame=f,group=p.name)
    action.use_fake_user=True;actions[clip]=action
    if clip=='Attack' and ID=='bow-skeleton':
        action.pose_markers.new('Draw').frame=7
        action.pose_markers.new('FullDraw').frame=13
        action.pose_markers.new('Release').frame=15
rig.animation_data.action=None;pose('Idle',0);scene.frame_set(1)
for clip,act in actions.items():
    track=rig.animation_data.nla_tracks.new();track.name=clip;strip=track.strips.new(clip,1,act);track.mute=True
scene.frame_end=33
activate([rig]+meshes)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Model.blend'))
bpy.ops.export_scene.fbx(filepath=str(OUT/'Model.fbx'),use_selection=True,object_types={'MESH','ARMATURE'},add_leaf_bones=False,bake_anim=False,path_mode='COPY',embed_textures=True,axis_forward='-Z',axis_up='Y',use_armature_deform_only=False)
(OUT/'animations').mkdir(exist_ok=True)
for clip,action in actions.items():
    rig.animation_data.action=action;scene.frame_end=lengths[clip]
    activate([rig]);bpy.ops.export_scene.fbx(filepath=str(OUT/'animations'/f'{clip}.fbx'),use_selection=True,object_types={'ARMATURE'},add_leaf_bones=False,bake_anim=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,bake_anim_simplify_factor=0,axis_forward='-Z',axis_up='Y')
rig.animation_data.action=None;pose('Idle',0);scene.frame_set(1);scene.frame_end=33
activate([rig]+meshes)
for track in rig.animation_data.nla_tracks:track.mute=False
bpy.ops.export_scene.gltf(filepath=str(OUT/'Model.glb'),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='NLA_TRACKS',export_skins=True,export_all_influences=False)
for track in rig.animation_data.nla_tracks:track.mute=True
for held in [o for o in meshes if o.get('held_projectile')]:
    projectile=held.copy();projectile.data=held.data.copy();scene.collection.objects.link(projectile);projectile.name='RockProjectile';projectile.parent=None
    for modifier in list(projectile.modifiers):projectile.modifiers.remove(modifier)
    center=Vector(data['rockContact']['rockCenter'])
    for vertex in projectile.data.vertices:vertex.co-=center
    projectile.vertex_groups.clear();activate([projectile])
    bpy.ops.export_scene.fbx(filepath=str(OUT/'RockProjectile.fbx'),use_selection=True,object_types={'MESH'},bake_anim=False,path_mode='COPY',embed_textures=True,axis_forward='-Z',axis_up='Y')
    bpy.ops.export_scene.gltf(filepath=str(OUT/'RockProjectile.glb'),use_selection=True,export_format='GLB',export_animations=False)
    bpy.data.objects.remove(projectile,do_unlink=True)
# Verify the authored asset, not the lighting stage.
checks=[];totals={'vertices':0,'triangles':0};bad=[]
for o in meshes:
    me=o.data;me.calc_loop_triangles();bm=bmesh.new();bm.from_mesh(me)
    boundary=sum(not e.is_manifold for e in bm.edges);bm.free()
    missing=0;unnormalized=0;excess=0
    for v in me.vertices:
        ww=[g.weight for g in v.groups if g.weight>.00001]
        missing+=not ww;unnormalized+=abs(sum(ww)-1)>1e-4;excess+=len(ww)>4
    item={'mesh':o.name,'vertices':len(me.vertices),'triangles':len(me.loop_triangles),'nonManifoldEdges':boundary,'unweighted':missing,'badWeightSum':unnormalized,'overFourInfluences':excess,'hasUV':bool(me.uv_layers)}
    checks.append(item);totals['vertices']+=len(me.vertices);totals['triangles']+=len(me.loop_triangles)
    if boundary or missing or unnormalized or excess or not me.uv_layers or len(me.loop_triangles)>20000:bad.append(item)
report={'id':ID,'status':'Blender candidate; visual review and Studio acceptance pending','totals':totals,'bones':list(spec),'actions':lengths,'checks':checks,'failures':bad,'grips':data.get('grips',[]),'gameplayImplemented':False,'studioImportVerified':False,'attackEvents':{'frame':15 if ID=='bow-skeleton' else 12,'type':'projectile' if ID in ['ash-shaman','spitter-zombie','rock-throwing-crab','bow-skeleton'] else 'contact'},'notes':['Baked UV atlas and reference-specific anatomy.','Attack timing metadata does not implement server damage or projectile release.']}
(OUT/'Rig.json').write_text(json.dumps(report,indent=2))
scene.cycles.samples=24;scene.render.resolution_x=900;scene.render.resolution_y=900
rig.animation_data.action=None;pose('Idle',0);scene.frame_set(1)
scene.render.filepath=str(OUT/'Rigged.png');bpy.ops.render.render(write_still=True)
rig.animation_data.action=actions['Attack'];scene.frame_set(13);scene.render.filepath=str(OUT/'Attack.png');bpy.ops.render.render(write_still=True)
rig.animation_data.action=None;pose('Idle',0);scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Model.blend'))
print('COMPLETE',ID,json.dumps(totals),'FAILURES',len(bad),flush=True)
