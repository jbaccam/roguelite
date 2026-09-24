"""Blender-authored rolled fabric; deterministic runtime triangle export."""
import bpy, math, json
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
verts=[]; faces=[]; colors=[]
def quad(points, color):
    i=len(verts); verts.extend(points); faces.append((i,i+1,i+2,i+3)); colors.append(color)
# Squashed, softly faceted roll, with a loose overlapping cloth edge.
N=12
for j in range(2):
    for i in range(N):
        pts=[]
        for x,k in [(-.43+j*.43,i),(-.43+j*.43,i+1),(j*.43,i+1),(j*.43,i)]:
            a=k*2*math.pi/N; r=.235*(1+.05*math.sin(a*3+x*2))
            pts.append((x,r*math.cos(a),r*.86*math.sin(a)))
        quad(pts, (.83+.025*math.sin(i),.80+.02*math.sin(i),.73+.02*math.sin(i)))
# Both ends expose a real rolled fabric spiral, rather than flat cylinder caps.
for side in [-1,1]:
    for i in range(28):
        pts=[]
        for k,dr in [(i,0),(i+1,0),(i+1,.047),(i,.047)]:
            a=k/28*math.pi*4.5; r=.012+.175*k/28+dr
            pts.append((side*(.432+.007*math.sin(a)),r*math.cos(a),r*.86*math.sin(a)))
        quad(pts,(.69,.66,.60) if i%7==0 else (.90,.87,.80))
quad([(-.38,-.20,.10),(.35,-.20,.10),(.32,-.32,-.06),(-.31,-.30,-.10)],(.92,.89,.82))
quad([(-.31,-.30,-.10),(.32,-.32,-.06),(.28,-.29,-.12),(-.29,-.27,-.15)],(.76,.73,.67))
# Restrained red box label on the outer fold.
quad([(-.17,-.224,.09),(.17,-.224,.09),(.17,-.291,-.015),(-.17,-.284,-.04)],(.72,.055,.075))
mesh=bpy.data.meshes.new('Rolled cotton with exposed spiral');mesh.from_pydata(verts,[],faces);mesh.update()
obj=bpy.data.objects.new('BundledDesignerTee',mesh);bpy.context.collection.objects.link(obj)
for i,c in enumerate(colors):
    mat=bpy.data.materials.new('Cotton shade %03d'%i);mat.diffuse_color=(*c,1);mat.use_nodes=True
    bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*c,1);bs.inputs['Roughness'].default_value=.9
    mesh.materials.append(mat);mesh.polygons[i].material_index=i
mesh.calc_loop_triangles()
data={'vertices':[[round(v.co.x,6),round(v.co.z,6),round(-v.co.y,6)] for v in mesh.vertices], 'triangles':[[*t.vertices,t.material_index+1] for t in mesh.loop_triangles], 'colors':colors}
(OUT/'geometry.json').write_text(json.dumps(data))
def lua(x):
    if isinstance(x,(list,tuple)):return '{'+','.join(lua(v) for v in x)+'}'
    return str(x)
(OUT/'RolledShirtData.luau').write_text('return {vertices='+lua(data['vertices'])+',triangles='+lua(data['triangles'])+',colors='+lua(colors)+'}\n')
bpy.context.view_layer.objects.active=obj;obj.select_set(True)
bpy.ops.export_scene.fbx(filepath=str(OUT/'BundledDesignerTee.fbx'),use_selection=True,object_types={'MESH'},axis_forward='-Z',axis_up='Y')
bpy.ops.export_scene.gltf(filepath=str(OUT/'BundledDesignerTee.glb'),use_selection=True)
scene=bpy.context.scene
world=scene.world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.18,.21,.25,1)
for loc,power,size in [((1,-3,4),350,4),((-3,-1,2),170,3)]:
    bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.rotation_euler=(Vector((0,0,0))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(1.4,-2,1.05));cam=bpy.context.object;cam.rotation_euler=(-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.5;scene.camera=cam
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.render.resolution_x=900;scene.render.resolution_y=700;scene.render.resolution_percentage=100
scene.render.filepath=str(OUT/'Preview.png');scene.view_settings.view_transform='AgX'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'BundledDesignerTee.blend'));bpy.ops.render.render(write_still=True)
print(json.dumps({'triangles':len(data['triangles']),'vertices':len(verts)}))
