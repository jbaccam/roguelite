"""Original standalone stylized Roblox cliff pillars. Run in Blender headlessly."""
import bpy, math, json
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parent
for p in ['previews','exports/fbx','exports/glb']: (ROOT/p).mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections): bpy.data.collections.remove(c)
def collection(name):
    c=bpy.data.collections.new(name); bpy.context.scene.collection.children.link(c); return c
MODULES=collection('StandalonePillars'); HELPERS=collection('PreviewHelpers')
def mat(name,color):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(*color,1)
    m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.9
    return m
ROCK=[mat('Rock_Base',(.36,.40,.46)),mat('Rock_Light',(.46,.50,.56)),mat('Rock_Mid',(.30,.34,.40)),mat('Rock_Shadow',(.24,.28,.34))]
GRASS=mat('Grass_Top',(.24,.55,.22)); EDGE=mat('Grass_Lip',(.17,.40,.16)); STAGE=mat('Preview_Stage',(.13,.18,.23))
def mesh(name,verts,faces,mats,inds):
    d=bpy.data.meshes.new(name+'_Mesh'); d.from_pydata(verts,[],faces); d.validate(); d.update()
    o=bpy.data.objects.new(name,d); MODULES.objects.link(o)
    for m in mats:d.materials.append(m)
    for i,p in enumerate(d.polygons): p.material_index=inds[i%len(inds)];p.use_smooth=False
    return o
def pillar(name,rx,ry,rings,sides,seed,offset):
    # Each horizontal ring shares a chunky irregular polygon silhouette.
    outline=[]
    for i in range(sides):
        a=2*math.pi*i/sides; wobble=1+.07*math.sin(i*2.19+seed)
        outline.append((rx*math.cos(a)*wobble,ry*math.sin(a)*wobble))
    v=[];f=[]
    for z,scale,dx,dy in rings:
        v.extend([(x*scale+dx,y*scale+dy,z) for x,y in outline])
    for k in range(len(rings)-1):
        for i in range(sides):
            j=(i+1)%sides;a=k*sides+i;b=k*sides+j;c=(k+1)*sides+j;d=(k+1)*sides+i
            f.extend([(a,b,d),(b,c,d)] if (i+k)%2 else [(a,b,c),(a,c,d)])
    v.extend([(rings[0][2],rings[0][3],rings[0][0]),(rings[-1][2],rings[-1][3],rings[-1][0])])
    for i in range(sides):
        j=(i+1)%sides;f.extend([(len(v)-2,j,i),(len(v)-1,(len(rings)-1)*sides+i,(len(rings)-1)*sides+j)])
    rock=mesh(name+'_Rock',v,f,ROCK,[0,1,0,2,0,3,1,0])
    z,s,dx,dy=rings[-1];cv=[];cf=[]
    for zz,ss in [(z-.05,s*1.015),(z+.55,s*1.05)]:cv.extend([(x*ss+dx,y*ss+dy,zz) for x,y in outline])
    cv.extend([(dx,dy,z-.05),(dx,dy,z+.55)])
    for i in range(sides):
        j=(i+1)%sides;cf.extend([(i,j,sides+j),(i,sides+j,sides+i),(len(cv)-2,j,i),(len(cv)-1,sides+i,sides+j)])
    cap=mesh(name+'_GrassCap',cv,cf,[GRASS,EDGE],[1,1,0,0])
    for o in (rock,cap):o.location=offset;o['module']=name;o['display_offset']=list(offset)
    return [rock,cap]

specs=[
 ('ShortNarrow',3.3,3.0,[(0,.9,0,0),(3,1.04,.15,0),(7,1,0,0)],8,1,(-31,-4,0)),
 ('MediumMesa',5.2,4.6,[(0,.94,0,0),(5,1.02,.2,-.1),(11,1,0,0)],9,2,(-19,3,0)),
 ('TallNarrow',3.7,3.5,[(0,.86,0,0),(7,.95,.25,0),(15,1.02,-.15,.1),(22,1,0,0)],8,3,(-6,6,0)),
 ('TallWideMesa',7.0,5.9,[(0,.95,0,0),(7,1.02,.2,0),(14,.97,-.2,.15),(20,1,0,0)],10,4,(10,7,0)),
 ('SquatBroadPlateau',8.7,6.5,[(0,.9,0,0),(3,1.03,.2,.1),(8,1,0,0)],11,5,(29,-1,0)),
 ('FloatingTapered',6.2,5.2,[(-10,.16,0,0),(-6,.5,.5,0),(-2,.87,-.2,0),(5,1,0,0)],9,6,(2,-14,13)),
]
groups={}
for name,rx,ry,rings,sides,seed,offset in specs:groups[name]=pillar(name,rx,ry,rings,sides,seed,offset)

# Render the actual individual models first; no environment or arena assembly.
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=1600;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.16,.22,.30,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.5
scene.view_settings.look='AgX - Medium High Contrast'
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.2));plane=bpy.context.object;plane.name='Preview_Ground';plane.data.materials.append(STAGE)
for c in list(plane.users_collection):c.objects.unlink(plane)
HELPERS.objects.link(plane)
bpy.ops.object.light_add(type='SUN',location=(30,-40,50));sun=bpy.context.object;sun.name='Preview_Sun';sun.data.energy=2.5;sun.rotation_euler=(math.radians(25),math.radians(-25),math.radians(-35))
bpy.ops.object.light_add(type='AREA',location=(-20,-30,35));bpy.context.object.data.energy=1500;bpy.context.object.data.size=30
bpy.ops.object.camera_add(location=(45,-75,45));cam=bpy.context.object;cam.name='Preview_Camera';cam.data.type='ORTHO';cam.data.ortho_scale=83
cam.rotation_euler=(Vector((0,0,10))-cam.location).to_track_quat('-Z','Y').to_euler();scene.camera=cam
scene.render.filepath=str(ROOT/'previews/standalone-cliff-pillars.png');bpy.ops.render.render(write_still=True)
print('PREVIEW_READY',scene.render.filepath,flush=True)

report={'blender_version':bpy.app.version_string,'modules':{}}
for name,objs in groups.items():
    bpy.ops.object.select_all(action='DESELECT');saved=[]
    for o in objs:
        saved.append((o,o.location.copy()));o.location-=Vector(o['display_offset']);o.select_set(True)
    bpy.context.view_layer.objects.active=objs[0]
    stem='cliff-'+''.join(('-'+c.lower() if c.isupper() else c) for c in name).lstrip('-')
    bpy.ops.export_scene.fbx(filepath=str(ROOT/'exports/fbx'/f'{stem}.fbx'),use_selection=True,object_types={'MESH'},apply_scale_options='FBX_SCALE_ALL',axis_forward='-Z',axis_up='Y',add_leaf_bones=False)
    bpy.ops.export_scene.gltf(filepath=str(ROOT/'exports/glb'/f'{stem}.glb'),export_format='GLB',use_selection=True,export_apply=True)
    report['modules'][name]={'file_stem':stem,'vertices':sum(len(o.data.vertices) for o in objs),'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objs),'pivot':'center at z=0; floating piece has modeled extent z=-10 to +5.55' if name=='FloatingTapered' else 'bottom center z=0'}
    for o,loc in saved:o.location=loc
(ROOT/'polygon-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'standalone-cliff-pillars.blend'))
print('KIT_READY',ROOT,flush=True)
