import bpy, math, random, json
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent
OUT.mkdir(exist_ok=True); (OUT/'textures').mkdir(exist_ok=True)
random.seed(24)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
parts={}; spec={}

def material(name,color,patch=True):
    m=bpy.data.materials.new(name); m.use_nodes=True
    n=m.node_tree.nodes; n.clear(); out=n.new('ShaderNodeOutputMaterial'); em=n.new('ShaderNodeEmission')
    m.node_tree.links.new(em.outputs[0],out.inputs['Surface'])
    if patch:
        coord=n.new('ShaderNodeTexCoord'); noise=n.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value=4.5; noise.inputs['Detail'].default_value=1.0; noise.inputs['Roughness'].default_value=.65
        m.node_tree.links.new(coord.outputs['Generated'],noise.inputs['Vector'])
        ramp=n.new('ShaderNodeValToRGB'); ramp.color_ramp.interpolation='CONSTANT'
        ramp.color_ramp.elements.remove(ramp.color_ramp.elements[1])
        for i,(pos,fac) in enumerate([(0,.66),(.34,.80),(.45,.94),(.56,1.06),(.67,1.15)]):
            e=ramp.color_ramp.elements[0] if i==0 else ramp.color_ramp.elements.new(pos); e.position=pos; e.color=(*[c*fac for c in color],1)
        m.node_tree.links.new(noise.outputs['Fac'],ramp.inputs[0]); m.node_tree.links.new(ramp.outputs[0],em.inputs[0])
    else: em.inputs[0].default_value=(*color,1)
    return m
skin=material('Mottled olive skin',(.34,.40,.19)); cloth=material('Weathered linen',(.48,.40,.29)); pants=material('Torn brown trousers',(.16,.105,.075)); hair=material('Chunky brown hair',(.13,.085,.06)); boot=material('Worn brown boots',(.115,.075,.048)); dark=material('Mouth and sockets',(.026,.021,.012),False); eye=material('Pale yellow eyes',(.87,.77,.38),False); tooth=material('Old ivory teeth',(.65,.51,.24),False)

def add(obj,part,mat):
    obj.data.materials.clear(); obj.data.materials.append(mat); parts.setdefault(part,[]).append(obj); return obj
def box(part,loc,dim,mat,bev=.04,rot=None):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.dimensions=dim
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if bev:
        mod=o.modifiers.new('Small worn corners','BEVEL'); mod.width=bev; mod.segments=1; bpy.ops.object.modifier_apply(modifier=mod.name)
    if rot:o.rotation_euler=rot
    return add(o,part,mat)
def panel(part,coords,y,thick,mat):
    verts=[(x,y,z) for x,z in coords]+[(x,y+thick,z) for x,z in coords]; n=len(coords)
    faces=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    me=bpy.data.meshes.new('torn panel'); me.from_pydata(verts,[],faces); me.update(); o=bpy.data.objects.new('detail',me); scene.collection.objects.link(o); return add(o,part,mat)
def sphere(part,loc,scale,mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=6,radius=1,location=loc); o=bpy.context.object; o.scale=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); return add(o,part,mat)
def register(name,parent,head,tail):spec[name]={'parent':parent,'head':head,'tail':tail}

# Rest pose: upright, arms lowered with breathing room; front is Blender -Y.
register('LowerTorso','HumanoidRootPart',(0,0,2.95),(0,0,3.48))
register('UpperTorso','LowerTorso',(0,0,3.48),(0,0,4.95))
register('Head','UpperTorso',(0,0,4.95),(0,0,6.45))
box('LowerTorso',(0,0,3.14),(1.53,.78,.67),pants,.08)
box('UpperTorso',(0,0,4.17),(1.85,.90,1.57),cloth,.12)
box('UpperTorso',(0,-.485,4.43),(.74,.06,.98),pants,.03)
panel('UpperTorso',[(-.40,4.95),(.40,4.95),(.32,4.61),(0,4.38),(-.32,4.61)],-.535,.03,skin)
# Shirt fronts and angular lapels with uneven hems.
panel('UpperTorso',[(-.86,4.85),(-.46,4.91),(-.22,4.14),(-.04,3.58),(-.28,3.40),(-.48,3.58),(-.78,3.38),(-.89,3.68)],-.54,.11,cloth)
panel('UpperTorso',[(.86,4.85),(.46,4.91),(.24,4.18),(-.03,3.62),(.09,3.34),(.36,3.55),(.64,3.42),(.89,3.63)],-.55,.12,cloth)
panel('UpperTorso',[(-.48,4.93),(-.71,4.60),(-.48,4.69),(-.30,4.26),(-.20,4.48)],-.68,.09,cloth)
panel('UpperTorso',[(.48,4.93),(.73,4.58),(.48,4.68),(.27,4.20),(.18,4.47)],-.68,.09,cloth)
for z in [3.75,3.96,4.15]:sphere('UpperTorso',(.08,-.695,z),(.06,.025,.065),cloth)
box('Head',(0,0,5.69),(1.64,1.30,1.46),skin,.12)
box('Head',(0,0,4.99),(.67,.67,.24),skin,.04)
for s in [-1,1]:
    sphere('Head',(s*.39,-.651,5.82),(.295,.10,.28),pants)
    sphere('Head',(s*.39,-.725,5.83),(.205,.047,.205),dark)
    sphere('Head',(s*.39,-.773,5.86),(.132,.026,.145),eye)
    box('Head',(s*.39,-.795,6.00),(.53,.095,.14),hair,.02,rot=(0,s*.11,0))
box('Head',(0,-.678,5.37),(.79,.055,.34),dark,.095)
for x,z in [(-.24,5.46),(.08,5.48),(.26,5.27),(-.22,5.27)]:box('Head',(x,-.725,z),(.13,.065,.13),tooth,.014,rot=(0,random.uniform(-.18,.18),0))
box('Head',(0,-.70,5.60),(.13,.10,.17),skin,.035)
# Mottled angular hair cap, silhouette chunks and hanging fringe.
box('Head',(0,.015,6.32),(1.71,1.34,.42),hair,.12)
box('Head',(0,-.48,6.29),(1.55,.20,.33),hair,.03)
for i,(x,z,w) in enumerate([(-.64,6.30,.52),(-.30,6.43,.62),(.12,6.43,.69),(.58,6.34,.53)]):
    panel('Head',[(x-w*.5,z+.12),(x+w*.48,z+.04),(x+w*.53,z-.22),(x+.03,z-.49),(x-w*.5,z-.15)],-.81-i*.025,.36,hair)
for s in [-1,1]:
    panel('Head',[(s*.70,6.44),(s*.92,6.20),(s*.83,5.84),(s*.73,5.99)],-.35,.75,hair)
for i in range(6):
    x=random.uniform(-.6,.6); y=random.uniform(-.32,.35)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=1,location=(x,y,6.57)); o=bpy.context.object; o.scale=(.40,.40,.22); add(o,'Head',hair)

for side,s in [('Left',1),('Right',-1)]:
    x=s*1.40
    register(side+'UpperArm','UpperTorso',(x,0,4.67),(x,0,3.70)); register(side+'LowerArm',side+'UpperArm',(x,0,3.70),(x,-.035,2.91)); register(side+'Hand',side+'LowerArm',(x,-.035,2.91),(x,-.08,2.49))
    box(side+'UpperArm',(x,0,4.20),(.77,.85,.97),skin,.08)
    box(side+'UpperArm',(x,.0,4.41),(.86,.93,.66),cloth,.06)
    coords=[(x-.43,4.43),(x+.43,4.43),(x+.45,3.93),(x+.20,4.08),(x+.12,3.88),(x-.08,4.02),(x-.25,3.91),(x-.44,4.09)]
    panel(side+'UpperArm',coords,-.48,.94,cloth)
    box(side+'LowerArm',(x,-.02,3.32),(.68,.73,.79),skin,.065)
    box(side+'Hand',(x,-.10,2.68),(.72,.77,.50),skin,.07)
    box(side+'Hand',(x-s*.34,-.28,2.87),(.20,.40,.32),skin,.055)
    lx=s*.43
    register(side+'UpperLeg','LowerTorso',(lx,0,2.99),(lx,0,1.89)); register(side+'LowerLeg',side+'UpperLeg',(lx,0,1.89),(lx,0,.65)); register(side+'Foot',side+'LowerLeg',(lx,0,.65),(lx,-.50,.27))
    box(side+'UpperLeg',(lx,0,2.42),(.77,.83,1.12),pants,.065)
    box(side+'LowerLeg',(lx,0,1.27),(.71,.76,1.24),skin,.07)
    box(side+'LowerLeg',(lx,.04,1.52),(.76,.80,.71),pants,.045)
    panel(side+'LowerLeg',[(lx-.39,1.93),(lx-.11,1.88),(lx-.18,1.66),(lx+.02,1.52),(lx+.20,1.72),(lx+.36,1.77),(lx+.37,.89),(lx+.16,1.08),(lx+.04,.88),(lx-.18,1.05),(lx-.38,.94)],-.445,.08,pants)
    box(side+'Foot',(lx,-.23,.30),(.85,1.22,.58),boot,.08)
    box(side+'Foot',(lx,-.23,.075),(.88,1.25,.15),boot,.018)
    box(side+'Foot',(lx,-.38,.62),(.48,.30,.13),pants,.02)

# Join details into exactly the 15 articulated sections and unwrap into a shared atlas.
objects={}
for idx,(name,items) in enumerate(parts.items()):
    bpy.ops.object.select_all(action='DESELECT')
    for o in items:o.select_set(True)
    bpy.context.view_layer.objects.active=items[0]; bpy.ops.object.join(); o=bpy.context.object; o.name=name
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
    scene.cursor.location=spec[name]['head']; bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.normals_make_consistent(inside=False) if hasattr(bpy.ops.mesh,'normals_make_consistent') else None
    bpy.ops.uv.smart_project(angle_limit=1.15,island_margin=.025); bpy.ops.object.mode_set(mode='OBJECT')
    for uv in o.data.uv_layers.active.data:uv.uv=((uv.uv.x*.94+.03+idx%4)/4,(uv.uv.y*.94+.03+idx//4)/4)
    objects[name]=o

for node in hair.node_tree.nodes:
    if node.type=='VALTORGB':
        for e in node.color_ramp.elements:e.color=(*(c*.48 for c in e.color[:3]),1)
atlas=bpy.data.images.new('Zombie_Color',width=2048,height=2048,alpha=False)
for m in [skin,cloth,pants,hair,boot,dark,eye,tooth]:
    n=m.node_tree.nodes.new('ShaderNodeTexImage'); n.image=atlas; m.node_tree.nodes.active=n
scene.render.engine='CYCLES'; scene.cycles.samples=1; scene.render.bake.margin=5; scene.render.bake.use_clear=False
for o in objects.values():
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active=o; bpy.ops.object.bake(type='EMIT')
atlas.filepath_raw=str(OUT/'textures/Zombie_Color.png'); atlas.file_format='PNG'; atlas.save(); atlas.pack()
mat=bpy.data.materials.new('Zombie painted atlas'); mat.use_nodes=True
bs=mat.node_tree.nodes.get('Principled BSDF'); bs.inputs['Roughness'].default_value=.94
tex=mat.node_tree.nodes.new('ShaderNodeTexImage'); tex.image=atlas; mat.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
for o in objects.values():
    o.data.materials.clear(); o.data.materials.append(mat)
    for p in o.data.polygons:p.material_index=0

bpy.ops.object.select_all(action='DESELECT'); bpy.ops.object.armature_add(location=(0,0,0)); rig=bpy.context.object; rig.name='Zombie_R15_Rig'; rig.show_in_front=True
bpy.ops.object.mode_set(mode='EDIT'); eb=rig.data.edit_bones; eb.remove(eb[0]); root=eb.new('HumanoidRootPart'); root.head=(0,0,2.95); root.tail=(0,0,3.3)
for name,d in spec.items():
    b=eb.new(name); b.head=d['head']; b.tail=d['tail']; b.parent=eb[d['parent']]; b.use_connect=False
bpy.ops.object.mode_set(mode='OBJECT')
for name,o in objects.items():
    vg=o.vertex_groups.new(name=name); vg.add(list(range(len(o.data.vertices))),1,'REPLACE'); mod=o.modifiers.new('Rigid limb skinning','ARMATURE'); mod.object=rig; o.parent=rig

# A non-exported full-range pose check exercises all animated joints.
scene.frame_start=1; scene.frame_end=40
for frame,fac in [(1,0),(20,1),(40,0)]:
    for name,p in rig.pose.bones.items():
        p.rotation_mode='XYZ'; p.rotation_euler=(0,0,0)
        if name!='HumanoidRootPart':
            a=.18 if name in ['Head','UpperTorso','LowerTorso'] else .45
            p.rotation_euler.x=fac*a*(1 if name.startswith('Left') else -1)
        p.keyframe_insert(data_path='rotation_euler',frame=frame,group=name)
rig.animation_data.action.name='Joint_Mobility_Check_NOT_FINAL_ANIMATION'; scene.frame_set(1)
action=rig.animation_data.action; rig.animation_data.action=None
bpy.ops.object.select_all(action='DESELECT'); rig.select_set(True)
for o in objects.values():o.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.fbx(filepath=str(OUT/'Zombie_R15.fbx'),use_selection=True,object_types={'MESH','ARMATURE'},add_leaf_bones=False,bake_anim=False,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True)
bpy.ops.export_scene.gltf(filepath=str(OUT/'Zombie_R15.glb'),use_selection=True,export_format='GLB',export_animations=False)
rig.select_set(False)
bpy.ops.export_scene.fbx(filepath=str(OUT/'Zombie_R15_Parts.fbx'),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True)
rig.animation_data.action=action; action.use_fake_user=True
stats={'body_sections':len(objects),'bones':len(rig.data.bones),'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objects.values()),'sections':{n:{'vertices':len(o.data.vertices),'origin':list(o.location),'dimensions':list(o.dimensions)} for n,o in objects.items()},'joints':spec,'front':'Blender -Y; Roblox -Z','height':max((o.matrix_world@v.co).z for o in objects.values() for v in o.data.vertices),'animation_status':'Mobility check only; six production animations not authored'}
(OUT/'rig_manifest.json').write_text(json.dumps(stats,indent=2))
# Presentation stage, excluded from exports.
floor=material('Preview backdrop',(.17,.23,.31),False)
box('preview',(0,0,-.16),(200,200,.22),floor,0)
# Replace backdrop emission for natural shadows.
floor.use_nodes=True; floor.node_tree.nodes.clear(); out= floor.node_tree.nodes.new('ShaderNodeOutputMaterial'); bs=floor.node_tree.nodes.new('ShaderNodeBsdfPrincipled'); bs.inputs['Base Color'].default_value=(.17,.23,.31,1); bs.inputs['Roughness'].default_value=.9; floor.node_tree.links.new(bs.outputs[0],out.inputs[0])
def aim(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(9,-21,10)); cam=bpy.context.object; aim(cam,(0,0,3.35)); cam.data.type='ORTHO'; cam.data.ortho_scale=8.2; scene.camera=cam
for loc,power,size in [((-5,-7,12),1250,7),((5,-3,8),800,6),((1,5,10),1200,5)]:
    bpy.ops.object.light_add(type='AREA',location=loc); l=bpy.context.object; l.data.energy=power; l.data.shape='DISK'; l.data.size=size; aim(l,(0,0,3))
scene.world.color=(.25,.25,.25); scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.cycles.use_denoising=True
scene.render.resolution_x=900; scene.render.resolution_y=1100; scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'; scene.render.image_settings.file_format='PNG'; scene.render.filepath=str(OUT/'Zombie_Preview.png')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Zombie_R15.blend')); bpy.ops.render.render(write_still=True)
print('ZOMBIE_BUILD_COMPLETE',json.dumps({k:stats[k] for k in ['body_sections','bones','triangles','height']}))
