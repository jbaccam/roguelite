import bpy, math, json, shutil
from pathlib import Path
from mathutils import Vector
import numpy as np

OUT=Path(__file__).resolve().parent
TEX=OUT/'textures'; TEX.mkdir(exist_ok=True)
SRC=Path('C:/Users/Jeremiah/Downloads')
sources={'foliage':'ChatGPT Image Sep 16, 2026, 06_10_48 PM.png','bark':'ChatGPT Image Sep 16, 2026, 06_07_54 PM.png'}
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
for name,filename in sources.items(): shutil.copy2(SRC/filename,TEX/(name+'_original.png'))
# One color atlas, two padded image regions; source colors are unmodified.
atlasarr=np.ones((1024,2048,4),dtype=np.float32)
for j,name in enumerate(['foliage','bark']):
    im=bpy.data.images.load(str(TEX/(name+'_original.png'))); im.scale(1008,1008)
    p=np.array(im.pixels[:],dtype=np.float32).reshape(1008,1008,4)
    atlasarr[:,j*1024:(j+1)*1024,:]=np.pad(p,((8,8),(8,8),(0,0)),mode='edge')
atlas=bpy.data.images.new('Evergreen_Color_Atlas',width=2048,height=1024,alpha=True)
atlas.colorspace_settings.name='sRGB'
atlas.pixels.foreach_set(atlasarr.ravel()); atlas.filepath_raw=str(TEX/'Evergreen_Color.png'); atlas.file_format='PNG'; atlas.save()
mat=bpy.data.materials.new('Evergreen • supplied foliage + bark'); mat.use_nodes=True
bsdf=mat.node_tree.nodes.get('Principled BSDF'); bsdf.inputs['Roughness'].default_value=.9
tex=mat.node_tree.nodes.new('ShaderNodeTexImage'); tex.image=atlas; tex.interpolation='Linear'
mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
verts=[]; faces=[]; uvs=[]; roles=[]
def atlasuv(u,v,bark=False): return ((8+1008*u+1024*int(bark))/2048,(8+1008*v)/1024)
def shell(rings,n,role,bark=False):
    start=len(verts)
    for ring in rings: verts.extend(ring)
    # Each shell has one cylindrical seam. All UV islands remain in the padded region.
    zlo=min(v[2] for ring in rings for v in ring); zhi=max(v[2] for ring in rings for v in ring)
    for k in range(len(rings)-1):
        for i in range(n):
            a=start+k*n+i; b=start+k*n+(i+1)%n; c=start+(k+1)*n+(i+1)%n; d=start+(k+1)*n+i
            faces.append((a,b,c,d)); roles.append(role)
            u0=i/n; u1=(i+1)/n
            uvs.append([atlasuv(u,(verts[idx][2]-zlo)/(zhi-zlo),bark) for idx,u in [(a,u0),(b,u1),(c,u1),(d,u0)]])
    for ringidx,reverse in [(0,True),(len(rings)-1,False)]:
        ring=rings[ringidx]; center=len(verts); verts.append((0,0,sum(v[2] for v in ring)/n))
        for i in range(n):
            ids=[start+ringidx*n+i,start+ringidx*n+(i+1)%n,center]
            if reverse: ids.reverse()
            faces.append(tuple(ids)); roles.append(role)
            uvs.append([atlasuv(.5+.42*verts[idx][0]/max(.01,max(abs(v[0]) for v in ring)),.5+.42*verts[idx][1]/max(.01,max(abs(v[1]) for v in ring)),bark) for idx in ids])

def canopy(name,radius,base,top,lobes,phase):
    n=lobes*6; rings=[]
    # Rolled underside, gently drooping broad lobes, curved flaring cone.
    profile=[(.90,-.025),(1,0),(.975,.075),(.66,.34),(.29,.70),(.025,.98)]
    if name=='05 pointed crown': profile.append((.0005,1.0))
    for rf,t in profile:
        ring=[]
        for i in range(n):
            a=2*math.pi*i/n+phase
            petal=(.5+.5*math.cos(lobes*(a-phase)))**.36
            influence=(rf**2.5)
            r=radius*rf*(1-.065*influence*(1-petal))
            # Small convex radial ribs, fading toward the neck.
            r*=1+.012*math.cos(lobes*(a-phase))*rf
            z=base+(top-base)*t-.15*(radius/2.9)*petal*influence
            ring.append((r*math.cos(a),r*math.sin(a),z))
        rings.append(ring)
    shell(rings,n,name)

canopy('01 bottom foliage',2.9,2.36,5.40,8,.06)
canopy('02 middle foliage',2.40,4.26,7.05,7,.21)
canopy('03 upper foliage',1.90,6.18,8.58,6,.10)
canopy('04 small foliage',1.32,7.78,9.52,5,.24)
canopy('05 pointed crown',.66,8.84,10.0,4,.10)
# Straight taper with a subtly split/flared foot, entirely within the trunk mesh.
rings=[]; n=24
for z,r,flare in [(0,.65,.43),(.38,.61,.25),(.9,.53,.06),(2.4,.46,0),(5.5,.32,0),(9.55,.07,0)]:
    ring=[]
    for i in range(n):
        a=2*math.pi*i/n
        petal=(.5+.5*math.cos(5*a+.6))**2
        rr=r+flare*petal
        ring.append((rr*math.cos(a),rr*math.sin(a),z))
    rings.append(ring)
shell(rings,n,'00 trunk',True)
mesh=bpy.data.meshes.new('Evergreen_Master_Mesh'); mesh.from_pydata(verts,[],faces); mesh.update()
obj=bpy.data.objects.new('Evergreen_Master',mesh); bpy.context.collection.objects.link(obj); mesh.materials.append(mat)
uv=mesh.uv_layers.new(name='UVMap')
for p,uvface in zip(mesh.polygons,uvs):
    p.use_smooth=True
    for li,coord in zip(p.loop_indices,uvface): uv.data[li].uv=coord
for role in sorted(set(roles)):
    group=obj.vertex_groups.new(name=role); ids=set()
    for face,r in zip(faces,roles):
        if r==role: ids.update(face)
    group.add(list(ids),1,'REPLACE')
# Consistent outward normals, no modifiers, one material, origin fixed at ground center.
bpy.context.view_layer.objects.active=obj; obj.select_set(True)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.normals_make_consistent(inside=False); bpy.ops.object.mode_set(mode='OBJECT')
obj['asset_description']='One master tree: four scalloped foliage tiers plus pointed crown, supplied textures, bottom-center origin.'
obj['uniform_scaling']='Scale all axes together.'
asset_collection=bpy.data.collections.new('ASSET • one master tree'); bpy.context.scene.collection.children.link(asset_collection)
for coll in list(obj.users_collection): coll.objects.unlink(obj)
asset_collection.objects.link(obj)
# Studio preview collection is intentionally excluded from every model export.
studio=bpy.data.collections.new('PREVIEW • excluded from exports'); bpy.context.scene.collection.children.link(studio)
def move_studio(o):
    for coll in list(o.users_collection): coll.objects.unlink(o)
    studio.objects.link(o)
bpy.ops.mesh.primitive_plane_add(size=2000); ground=bpy.context.object; ground.name='Preview ground'; move_studio(ground)
gm=bpy.data.materials.new('Preview slate blue'); gm.diffuse_color=(.18,.26,.38,1); ground.data.materials.append(gm)
gm.use_nodes=True; gm.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.18,.26,.38,1)
gm.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.85
def aim(o,point): o.rotation_euler=(Vector(point)-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(13,-23,8.8)); cam=bpy.context.object; move_studio(cam); aim(cam,(0,0,5)); cam.data.type='ORTHO'; cam.data.ortho_scale=11.55; bpy.context.scene.camera=cam
def light(name,pos,power,size,color):
    bpy.ops.object.light_add(type='AREA',location=pos); l=bpy.context.object; l.name=name; move_studio(l); l.data.energy=power; l.data.shape='DISK'; l.data.size=size; l.data.color=color; aim(l,(0,0,4))
light('Large warm key',(7,-2,13),1100,5,(1,1,1))
light('Soft sky fill',(-7,-4,8),300,7,(.72,.82,1))
light('Gentle back rim',(3,6,12),700,5,(.90,1,.86))
light('Broad front bounce',(2,-10,7),650,8,(.88,.92,1))
scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=48
scene.world.color=(.20,.20,.20); scene.render.resolution_x=1080; scene.render.resolution_y=1200; scene.render.resolution_percentage=100
scene.view_settings.view_transform='Standard'; scene.view_settings.look='None'; scene.view_settings.exposure=0; scene.view_settings.gamma=1
scene.render.image_settings.file_format='PNG'; scene.render.filepath=str(OUT/'Evergreen_Preview.png')
bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True); bpy.context.view_layer.objects.active=obj
# Match the surrounding kit's useful authoring scale without unapplied object transforms.
for v in mesh.vertices: v.co*=1.8
for o in studio.objects:
    o.location*=1.8
    if o.type=='CAMERA': o.data.ortho_scale*=1.8
    if o.type=='LIGHT': o.data.energy*=1.8**2; o.data.size*=1.8
bpy.context.view_layer.update()
mesh.calc_loop_triangles()
stats={'vertices':len(mesh.vertices),'polygons':len(mesh.polygons),'triangles':len(mesh.loop_triangles),'material_count':len(mesh.materials),'height':obj.dimensions.z,'width':max(obj.dimensions.x,obj.dimensions.y),'origin':list(obj.location),'objects_exported':1,'foliage_tiers':4,'pointed_crown':1}
(OUT/'asset_stats.json').write_text(json.dumps(stats,indent=2))
bpy.ops.export_scene.fbx(filepath=str(OUT/'Evergreen_Master.fbx'),use_selection=True,object_types={'MESH'},apply_unit_scale=True,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True,mesh_smooth_type='FACE',use_triangles=True)
bpy.ops.export_scene.gltf(filepath=str(OUT/'Evergreen_Master.glb'),export_format='GLB',use_selection=True,export_apply=True)
atlas.pack()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Evergreen_Master.blend'))
bpy.ops.render.render(write_still=True)
print('TREE_COMPLETE',json.dumps(stats))
