"""Executed by build_mobs.py after reference-specific geometry authoring."""
import hashlib

# Shared original AI-painted texture atlas; source image pixels are preserved.
import shutil
shutil.copyfile(globals().get('ATLAS_SOURCE',ROOT/'PaintedMaterials.png'),OUT/'BaseColor.png')
cols=rows=4
atlas=bpy.data.images.load(str(OUT/'BaseColor.png'));atlas.pack()
unified=bpy.data.materials.new(ID+'_Painted');unified.use_nodes=True
bs=unified.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.88
bs.inputs['Specular IOR Level'].default_value=.15
tex=unified.node_tree.nodes.new('ShaderNodeTexImage');tex.image=atlas
unified.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
source_tiles={'sage':0,'olive':0,'skin':1,'cyan':1,'gray':2,'lightgray':2,'ivory':3,'bone':3,'coral':4,'teal':5,'brown':6,'cloth':6,'charcoal':7,'blue':8,'red':9,'russet':9,'cream':10,'sand':11,'steel':12,'orange':13,'amber':13,'white':14,'fur':14,'dark':15,'glow':5,'mark':4}
tile={name:(3-index//4)*4+index%4 for name,index in source_tiles.items()}
for group,objects in parts.items():
    for o in objects:
        original_materials=list(o.data.materials)
        while o.data.uv_layers:o.data.uv_layers.remove(o.data.uv_layers[0])
        uv=o.data.uv_layers.new(name='PaintedAtlas')
        co=[v.co for v in o.data.vertices];lo=[min(p[j] for p in co) for j in range(3)];hi=[max(p[j] for p in co) for j in range(3)]
        for p in o.data.polygons:
            idx=tile[original_materials[p.material_index].name]
            axis=max(range(3),key=lambda j:abs(p.normal[j]));a,b=[j for j in range(3) if j!=axis]
            for li in p.loop_indices:
                v=o.data.vertices[o.data.loops[li].vertex_index].co
                u=(v[a]-lo[a])/max(hi[a]-lo[a],1e-7);w=(v[b]-lo[b])/max(hi[b]-lo[b],1e-7)
                uv.data[li].uv=((idx%cols+.03+.94*u)/cols,(idx//cols+.015+.97*w)/rows)
        o.data.materials.clear();o.data.materials.append(unified)

rigdata=bpy.data.armatures.new(ID+'_Skeleton');rig=bpy.data.objects.new('Rig',rigdata)
scene.collection.objects.link(rig);bpy.context.view_layer.objects.active=rig
rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
for name,data in bones.items():
    b=rigdata.edit_bones.new(name);b.head=data['head'];b.tail=Vector(data['head'])+Vector((0,0,.24))
    if data['parent']:b.parent=rigdata.edit_bones[data['parent']]
bpy.ops.object.mode_set(mode='OBJECT')
meshes=[]
for group,objects in parts.items():
    for o in objects:
        bpy.context.view_layer.objects.active=o
        bpy.ops.object.select_all(action='DESELECT');o.select_set(True)
        bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
        if ID=='lava-slime' and group=='Body':
            base=o.vertex_groups.new(name='Body');top=o.vertex_groups.new(name='Crown')
            for v in o.data.vertices:
                w=max(0,min(1,(v.co.z-.12)/1.6));base.add([v.index],1-w,'REPLACE')
                if w:top.add([v.index],w,'REPLACE')
        elif o.get('snake_skin'):
            for name in [f'Spine{i}' for i in range(9)]:o.vertex_groups.new(name=name)
            # Tube has 12 vertices per ring, smoothly blend adjacent spinal bones.
            for v in o.data.vertices:
                t=(v.index//12)/4;j=min(7,int(t));f=min(1,t-j)
                o.vertex_groups[f'Spine{j}'].add([v.index],1-f,'REPLACE')
                if f:o.vertex_groups[f'Spine{j+1}'].add([v.index],f,'REPLACE')
        else:
            vg=o.vertex_groups.new(name=group);vg.add(list(range(len(o.data.vertices))),1,'REPLACE')
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join()
    o=bpy.context.object;o.name=group
    m=o.modifiers.new('Skin','ARMATURE');m.object=rig;o.parent=rig
    meshes.append(o)

for b in rig.pose.bones:b.rotation_mode='XYZ'
scene.render.fps=30
humanoid_rig='UpperTorso' in bones
ranged=ID in ['ice-elf','ash-shaman','bow-skeleton','rock-throwing-crab','spitter-zombie']
def pose(clip,t):
    for b in rig.pose.bones:b.location=(0,0,0);b.rotation_euler=(0,0,0);b.scale=(1,1,1)
    def rot(name,x=0,y=0,z=0):
        if name in rig.pose.bones:rig.pose.bones[name].rotation_euler=(x,y,z)
    def loc(name,x=0,y=0,z=0):rig.pose.bones[name].location=(x,y,z)
    wave=math.sin(t*math.tau)
    if clip in ['Idle','Move']:
        moving=clip=='Move';amp=.43 if moving else .025
        if humanoid_rig:
            for sign,side in [(-1,'Left'),(1,'Right')]:
                rot(side+'UpperLeg',sign*wave*amp);rot(side+'LowerLeg',max(0,-sign*wave)*amp*.65)
                rot(side+'UpperArm',-sign*wave*amp*.65-.05);rot(side+'LowerArm',-.08)
            loc('Root',y=abs(wave)*(.055 if moving else .012))
            if ID in ['werewolf','obsidian-ogre','spitter-zombie','tank-zombie']:rot('UpperTorso',.11)
            if ID in ['regular-zombie','baby-zombie']:
                for sign,side in [(-1,'Left'),(1,'Right')]:rot(side+'UpperArm',-1.04-sign*wave*amp*.12);rot(side+'LowerArm',-.15)
            if ID=='bow-skeleton':rot('LeftUpperArm',-.25);rot('LeftLowerArm',-.12)
        elif ID=='snake':
            for i in range(9):rot(f'Spine{i}',y=math.sin(t*math.tau-i*.55)*(.085 if moving else .022))
        elif ID=='lava-slime':
            v=wave*(.16 if moving else .04);loc('Crown',y=v)
            loc('Root',y=max(0,wave)*(.20 if moving else .025))
        elif ID=='frost-ghost':
            loc('Root',y=wave*.09);rot('LeftArm',.08,y=wave*.06);rot('RightArm',-.08,y=-wave*.06)
        else:
            for n in bones:
                if 'Leg' in n:
                    side=-1 if n.startswith('Left') else 1;i=int(n.split('Leg')[1][0]);s=math.sin(t*math.tau+i*math.pi+side*.5)
                    rot(n,x=s*amp*.23,y=s*amp*.35,z=max(0,s)*amp*.28*side)
            loc('Body',y=abs(wave)*(.025 if moving else .008))
    elif clip=='Attack':
        # The complete action has anticipation, one impact/release, and recovery.
        wind=min(1,t/.36);strike=max(0,min(1,(t-.36)/.12));recover=max(0,min(1,(t-.52)/.48))
        a=wind*(1-strike);b=strike*(1-recover)
        if humanoid_rig:
            rot('UpperTorso',-.09*a+.16*b)
            if ID=='bow-skeleton':
                rot('LeftUpperArm',-1.1*(a+b));rot('RightUpperArm',-.7*a-.9*b,y=.3*a);rot('RightLowerArm',-.85*a-.18*b)
            elif ranged:
                side='Left' if ID=='ash-shaman' else 'Right'
                rot(side+'UpperArm',-.48*a-1.24*b);rot(side+'LowerArm',-.8*a-.1*b)
                if ID=='spitter-zombie':rot('Head',-.22*a+.28*b)
            elif ID in ['obsidian-ogre','tank-zombie']:
                for side in ['Left','Right']:rot(side+'UpperArm',-2.4*a-.65*b);rot(side+'LowerArm',-.28*a)
            else:
                rot('RightUpperArm',-.95*a-.8*b,y=-.45*a+.40*b);rot('RightLowerArm',-.65*a-.10*b)
        elif ID=='snake':
            rot('Spine0',-.20*a+.32*b);loc('Root',y=.10*b,z=.23*b)
            rot('Head',-.06*a+.15*b)
        elif ID=='frost-ghost':
            rot('LeftArm',-.5*b);rot('RightArm',-.5*b);loc('Root',z=.18*b)
        elif ID=='lava-slime':
            loc('Crown',y=-.32*a+.28*b);loc('Root',y=.26*b)
        elif ID=='ember-spider':
            for side in ['Left','Right']:rot(side+'Fang',-.2*a+.5*b)
            loc('Body',y=.07*a,z=.18*b)
        elif ID=='scorpion':
            for i in range(7):rot(f'Tail{i}',-.06*a+.09*b)
            loc('Body',z=.16*b)
        else:
            side='Right';rot(side+'Arm',-.50*a-.20*b);rot(side+'Claw',-.5*a+.55*b);rot(side+'Pincer',y=.45*a-.20*b)
    elif clip=='Hit':
        a=math.sin(t*math.pi)*(1-t)
        rot('UpperTorso' if humanoid_rig else 'Spine0' if ID=='snake' else 'Body',-.20*a)
    elif clip=='Death':
        e=t*t*(3-2*t)
        rot('Root',math.radians(78)*e)
        loc('Root',y=.06*e)
        if ID=='lava-slime':loc('Crown',y=-.65*e)
    bpy.context.view_layer.update()

clips={'Idle':(30,True),'Move':(24,True),'Attack':(30,False),'Hit':(9,False),'Death':(18,False)}
actions={};samples={}
for clip,(duration,loop) in clips.items():
    rig.animation_data_create();rig.animation_data.action=None
    frames=[]
    for f in range(duration+1):
        scene.frame_set(f+1);pose(clip,f/duration)
        for b in rig.pose.bones:
            b.keyframe_insert(data_path='rotation_euler',frame=f+1,group=b.name)
            b.keyframe_insert(data_path='location',frame=f+1,group=b.name)
            b.keyframe_insert(data_path='scale',frame=f+1,group=b.name)
        frames.append({n:{'rotation':list(b.rotation_euler),'location':list(b.location),'scale':list(b.scale)} for n,b in ((b.name,b) for b in rig.pose.bones)})
    action=rig.animation_data.action;action.name=clip;action.use_fake_user=True;actions[clip]=action
    samples[clip]={'duration':duration/30,'loop':loop,'fps':30,'frames':frames,'impactTime':.48 if clip=='Attack' else None}
rig.animation_data.action=None
pose('Idle',0)
scene.frame_start=1;scene.frame_end=31

def select_asset():
    bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
    for o in meshes:o.select_set(True)
    bpy.context.view_layer.objects.active=rig
select_asset()
fbxargs=dict(use_selection=True,object_types={'MESH','ARMATURE'},add_leaf_bones=False,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True)
bpy.ops.export_scene.fbx(filepath=str(OUT/'Model.fbx'),bake_anim=False,**fbxargs)
for clip,action in actions.items():
    rig.animation_data.action=action;scene.frame_end=clips[clip][0]+1
    bpy.ops.export_scene.fbx(filepath=str(OUT/(clip+'.fbx')),bake_anim=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,bake_anim_simplify_factor=0,**fbxargs)
rig.animation_data.action=actions['Idle'];scene.frame_end=31;scene.frame_set(1)
gltfargs=dict(filepath=str(OUT/'Model.glb'),export_format='GLB',use_selection=True,export_animations=True,export_skins=True)
if 'export_animation_mode' in bpy.ops.export_scene.gltf.get_rna_type().properties:gltfargs['export_animation_mode']='ACTIONS'
bpy.ops.export_scene.gltf(**gltfargs)
rig.animation_data.action=None;pose('Idle',0)

# Portable source geometry and rest matrices for a scoped Studio importer.
geometry={}
for o in meshes:
    me=o.data;me.calc_loop_triangles();uv=me.uv_layers.active
    geometry[o.name]={'vertices':[list(v.co) for v in me.vertices],
       'triangles':[list(t.vertices) for t in me.loop_triangles],
       'triangleUVs':[[list(uv.data[l].uv) for l in t.loops] for t in me.loop_triangles],
       'weights':[{o.vertex_groups[g.group].name:g.weight for g in v.groups if g.weight>0} for v in me.vertices]}
(OUT/'Geometry.json').write_text(json.dumps(geometry,separators=(',',':')))
(OUT/'AnimationSamples.json').write_text(json.dumps(samples,separators=(',',':')))
(OUT/'Rig.json').write_text(json.dumps({'bones':bones,'restMatrices':{b.name:[list(row) for row in b.matrix_local] for b in rigdata.bones},'axes':'Blender Z up, forward -Y. Roblox conversion (x,z,y) with face-winding reversal, forward -Z.','unit':'authoring units; set importer scale explicitly'},indent=2))

stats={'id':ID,'reference':'Reference.png','status':'Authored; independent validation and Studio import pending',
 'triangles':sum(len(o.data.loop_triangles) for o in meshes),'meshCount':len(meshes),'boneCount':len(bones),
 'clips':{c:{'seconds':d/30,'loop':l} for c,(d,l) in clips.items()},
 'texture':'BaseColor.png','textureMethod':('Shared original AI-painted material atlas. Reference images guide geometry; source atlas pixels are unmodified.' if 'ATLAS_SOURCE' not in globals() or Path(ATLAS_SOURCE).name=='Materials.png' else 'Derived from the shared painted atlas by '+Path(ATLAS_SOURCE).stem+' (see its generator); other tiles unmodified.'),
 'limitations':['Layered clothing and fur use intentional intersecting closed pieces.','Rigid weights on articulated hard sections; snake main body uses blended weights.','No multiplayer or mobile performance claim.','Studio import and actual gameplay verification pending.']}
(OUT/'manifest.json').write_text(json.dumps(stats,indent=2))

# Neutral stage excluded from all exports.
stage=bpy.data.collections.new('REVIEW_ONLY');scene.collection.children.link(stage)
def stage_obj(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    stage.objects.link(o)
def aim(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
coords=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
lo=Vector(tuple(min(v[i] for v in coords) for i in range(3)));hi=Vector(tuple(max(v[i] for v in coords) for i in range(3)))
center=(lo+hi)/2;span=hi-lo;size=max(span.x,span.y,span.z)
bpy.ops.mesh.primitive_plane_add(size=100,location=(0,0,-.03));floor=bpy.context.object;stage_obj(floor)
fm=bpy.data.materials.new('Review gray');fm.use_nodes=True
fm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.24,.23,.22,1)
fm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.9;floor.data.materials.append(fm)
scene.world=bpy.data.worlds.new('Review world');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.55,.58,.64,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.5
for off,power in [((-1.3,-1.7,2),950),((1.4,-.7,1.1),650),((.5,1.5,1.8),1100)]:
    bpy.ops.object.light_add(type='AREA',location=center+Vector(off)*size)
    o=bpy.context.object;o.data.energy=power*(size/5)**2;o.data.size=size;aim(o,center);stage_obj(o)
bpy.ops.object.camera_add(location=center+Vector((.85,-2.1,.78))*size)
cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=size*1.40;aim(cam,center);stage_obj(cam);scene.camera=cam
scene.render.engine='CYCLES';scene.cycles.samples=globals().get('REVIEW_SAMPLES',24);scene.cycles.use_denoising=True
scene.render.resolution_x=globals().get('REVIEW_RESOLUTION',960);scene.render.resolution_y=scene.render.resolution_x;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX';scene.render.image_settings.file_format='PNG'
rig.animation_data.action=actions['Idle'];scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Model.blend'))
scene.render.filepath=str(OUT/'Preview.png');bpy.ops.render.render(write_still=True)
cam.location=center+Vector((-1.3,1.8,.65))*size;aim(cam,center)
scene.render.filepath=str(OUT/'Back.png');bpy.ops.render.render(write_still=True)
cam.location=center+Vector((.85,-2.1,.78))*size;aim(cam,center)
scene.render.resolution_x=640;scene.render.resolution_y=640;scene.cycles.samples=12
rig.animation_data.action=actions['Attack']
for f,label in [(11,'Windup'),(16,'Impact')]:
    scene.frame_set(f);scene.render.filepath=str(OUT/(label+'.png'));bpy.ops.render.render(write_still=True)
print('MOB_COMPLETE',json.dumps(stats))
