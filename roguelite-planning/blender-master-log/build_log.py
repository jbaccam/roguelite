import bpy, math, json, shutil
import numpy as np
from pathlib import Path
from mathutils import Vector

OUT=Path(__file__).resolve().parent
TEX=OUT/'textures'; TEX.mkdir(exist_ok=True)
SRC=Path('C:/Users/Jeremiah/Downloads/ChatGPT Image Sep 16, 2026, 11_42_59 AM (6).png')
shutil.copy2(SRC,TEX/'Bark_Original.png')
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
# Preserve source color; padded bark island + solid end-grain colors in one atlas.
im=bpy.data.images.load(str(TEX/'Bark_Original.png')); im.scale(1520,2032)
arr=np.ones((2048,2048,4),dtype=np.float32)
arr[:,:1536,:]=np.pad(np.array(im.pixels[:],dtype=np.float32).reshape(2032,1520,4),((8,8),(8,8),(0,0)),mode='edge')
colors=[(.40,.265,.175),(.58,.425,.285),(.64,.485,.33),(.60,.448,.304),(.545,.397,.267),(.24,.15,.105)]
for i,col in enumerate(colors):
    lo=int(i*2048/6); hi=int((i+1)*2048/6)
    arr[lo:hi,1536:,:3]=col
atlas=bpy.data.images.new('Log_Color',width=2048,height=2048,alpha=True)
atlas.pixels.foreach_set(arr.ravel()); atlas.filepath_raw=str(TEX/'Log_Color.png'); atlas.file_format='PNG'; atlas.save()
mat=bpy.data.materials.new('Log textured bark and cut wood'); mat.use_nodes=True
bs=mat.node_tree.nodes.get('Principled BSDF'); bs.inputs['Roughness'].default_value=.92
node=mat.node_tree.nodes.new('ShaderNodeTexImage'); node.image=atlas
mat.node_tree.links.new(node.outputs['Color'],bs.inputs['Base Color'])
verts=[]; faces=[]; uvfaces=[]
def face(ids,uv): faces.append(ids); uvfaces.append(uv)
def bark(u,v): return ((8+1520*u)/2048,(8+2032*v)/2048)
def flatuv(n,c):
    # Tiny nondegenerate UV polygons within padded solid-color swatches.
    return [(.875+.018*math.cos(i*2*math.pi/n),(c+.5)/6+.018*math.sin(i*2*math.pi/n)) for i in range(n)]
def tube(start,end,radii,angles,split=False,offset=0):
    start,end=Vector(start),Vector(end); axis=(end-start).normalized()
    ref=Vector((0,1,0)) if abs(axis.y)<.9 else Vector((0,0,1))
    b1=(ref-axis*ref.dot(axis)).normalized(); b2=axis.cross(b1)
    n=len(angles); base=len(verts)
    ts=[0,.035,.19,.43,.70,.965,1] if split else [0,.25,.87,1]
    for k,t in enumerate(ts):
        for j,a in enumerate(angles):
            rad=(radii[0]*(1-t)+radii[1]*t)*(1+.034*math.sin(3*a+.3)+.018*math.cos(5*a+2*t))
            rad*=1+.023*math.sin(t*math.pi*2+a)
            if k in [0,len(ts)-1]: rad*=.965
            if split:
                # Three narrow longitudinal end checks taper into the intact shell.
                for sa in [.42,1.72,4.0]:
                    if abs(a-sa)<.001:
                        rad*=1-.24*max(0,1-t/.19) if sa!=1.72 else 1-.25*max(0,1-(1-t)/.30)
            p=start.lerp(end,t)+rad*(math.cos(a)*b1+math.sin(a)*b2)
            verts.append(tuple(p))
    for k in range(len(ts)-1):
        for j,a in enumerate(angles):
            jj=(j+1)%n; aa=angles[jj] if jj else 2*math.pi
            ids=[base+k*n+j,base+k*n+jj,base+(k+1)*n+jj,base+(k+1)*n+j]
            # Source grain is vertical in image, therefore V follows the cylinder axis.
            u0=a/(2*math.pi); u1=aa/(2*math.pi)
            face(ids,[bark(u0,offset+ts[k]*(1-offset)),bark(u1,offset+ts[k]*(1-offset)),bark(u1,offset+ts[k+1]*(1-offset)),bark(u0,offset+ts[k+1]*(1-offset))])
    for k in [0,len(ts)-1]:
        center=start if k==0 else end
        outer=[base+k*n+j for j in range(n)]
        prev=outer
        for rf,col in [(.84,0),(.68,2),(.59,1),(.34,3)]:
            ids=[]
            for j in range(n):
                p=center+(Vector(verts[outer[j]])-center)*rf
                ids.append(len(verts)); verts.append(tuple(p))
            for j in range(n):
                jj=(j+1)%n; f=[prev[j],prev[jj],ids[jj],ids[j]]
                if k==0: f.reverse()
                face(f,flatuv(4,col))
            prev=ids
        ci=len(verts); verts.append(tuple(center))
        for j in range(n):
            f=[prev[j],prev[(j+1)%n],ci]
            if k==0: f.reverse()
            face(f,flatuv(3,4))

angles=sorted(set([i*2*math.pi/16 for i in range(16)]+[s+d for s in [.42,1.72,4.0] for d in [-.045,0,.045]]))
tube((-6,0,1.48),(6,0,1.55),(1.48,1.40),angles,True)
stubangles=[i*2*math.pi/8 for i in range(8)]
for st,en,rr in [((-3.4,-.72,1.03),(-3.75,-2.0,.55),(.53,.35)),((3.8,-.72,1.06),(4.3,-1.96,.59),(.55,.34)),((-2.1,.04,2.42),(-2.7,.08,3.42),(.43,.28)),((3.7,.72,2.30),(3.9,1.04,3.38),(.41,.26))]:
    tube(st,en,rr,stubangles,offset=.18)
minz=min(p[2] for p in verts)
cx=(min(p[0] for p in verts)+max(p[0] for p in verts))/2
cy=(min(p[1] for p in verts)+max(p[1] for p in verts))/2
verts=[(x-cx,y-cy,z-minz) for x,y,z in verts]
mesh=bpy.data.meshes.new('Log_Master_Geometry'); mesh.from_pydata(verts,[],faces); mesh.update()
obj=bpy.data.objects.new('Log_Master',mesh); bpy.context.collection.objects.link(obj)
obj.data.materials.append(mat); layer=mesh.uv_layers.new(name='UVMap')
for poly,uv in zip(mesh.polygons,uvfaces):
    for li,co in zip(poly.loop_indices,uv): layer.data[li].uv=co
bpy.context.view_layer.objects.active=obj; obj.select_set(True)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.normals_make_consistent(inside=False); bpy.ops.object.mode_set(mode='OBJECT')
obj['asset_note']='One reusable fallen log; four intersecting closed branch shells. Lengthwise supplied bark. 1 Blender unit = 1 intended Roblox stud.'
obj['source_bark']=SRC.name
atlas.pack()
# Export only the asset; no cameras, lighting or ground.
bpy.ops.export_scene.fbx(filepath=str(OUT/'Log_Master.fbx'),use_selection=True,object_types={'MESH'},apply_unit_scale=True,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True)
bpy.ops.export_scene.gltf(filepath=str(OUT/'Log_Master.glb'),export_format='GLB',use_selection=True)
scene=bpy.context.scene
scene.render.engine='CYCLES'; scene.cycles.samples=48
scene.render.resolution_x=1500; scene.render.resolution_y=1100; scene.render.resolution_percentage=100
scene.world.color=(.25,.25,.25)
scene.view_settings.view_transform='AgX'
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.045)); ground=bpy.context.object; ground.name='Preview ground (not exported)'
gm=bpy.data.materials.new('Preview slate'); gm.use_nodes=True; gm.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.19,.255,.33,1); gm.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.85; ground.data.materials.append(gm)
def aim(o,p): o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
for name,loc,power,size in [('Key',(-4,-6,11),1800,7),('Fill',(3,5,8),1350,8),('Rim',(7,2,5),650,5),('Cut face fill',(-10,-5,5),550,6)]:
    bpy.ops.object.light_add(type='AREA',location=loc); l=bpy.context.object; l.name=name; l.data.energy=power; l.data.shape='DISK'; l.data.size=size; aim(l,(0,0,1))
bpy.ops.object.camera_add(location=(-12.5,-18,11)); camera=bpy.context.object; aim(camera,(0,0,1.5)); camera.data.type='ORTHO'; camera.data.ortho_scale=15.4; scene.camera=camera
scene.render.image_settings.file_format='PNG'; scene.render.filepath=str(OUT/'Log_Preview.png')
bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True); bpy.context.view_layer.objects.active=obj
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        area.spaces.active.region_3d.view_perspective='CAMERA'; area.spaces.active.shading.type='MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Log_Master.blend'))
bpy.ops.render.render(write_still=True)
mesh.calc_loop_triangles()
stats={'vertices':len(mesh.vertices),'triangles':len(mesh.loop_triangles),'dimensions':list(obj.dimensions),'pivot':list(obj.location),'materials':len(mesh.materials),'source_texture':str(SRC),'branch_stubs':4}
(OUT/'asset_stats.json').write_text(json.dumps(stats,indent=2))
