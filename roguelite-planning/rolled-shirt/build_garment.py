"""Normalized, hollow low-poly cotton tee panels. Scaled per animated body part."""
import bpy, math, json
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
def shell(name,rings,n=12):
 v=[];f=[];cols=[]
 for y,rx,rz in rings:
  for i in range(n):
   a=2*math.pi*i/n
   # Broad front/back surfaces with softened polygonal side corners.
   x=math.copysign(abs(math.cos(a))**.65,math.cos(a))*rx
   z=math.copysign(abs(math.sin(a))**.65,math.sin(a))*rz
   v.append((x,y,z))
 for j in range(len(rings)-1):
  for i in range(n):
   f.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
   s=.025*math.sin(i*1.5+j*.8);cols.append((.88+s,.85+s,.78+s))
 mesh=bpy.data.meshes.new(name);mesh.from_pydata([(x,-z,y) for x,y,z in v],[],f);mesh.update()
 obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
 for i,c in enumerate(cols):
  mat=bpy.data.materials.new(name+' cotton '+str(i));mat.diffuse_color=(*c,1);mesh.materials.append(mat);mesh.polygons[i].material_index=i
 mesh.calc_loop_triangles()
 data={'vertices':v,'triangles':[[*t.vertices,t.material_index+1] for t in mesh.loop_triangles],'colors':cols}
 def lua(x):return '{'+','.join(lua(k) for k in x)+'}' if isinstance(x,(list,tuple)) else str(round(x,6))
 (OUT/(name+'Data.luau')).write_text('return {vertices='+lua(v)+',triangles='+lua(data['triangles'])+',colors='+lua(cols)+'}\n')
 return obj
torso=shell('TeeTorso',[(-.525,.505,.515),(-.47,.52,.54),(.12,.54,.565),(.40,.535,.54),(.49,.39,.38),(.54,.19,.20)])
sleeve=shell('TeeSleeve',[(-.06,.52,.535),(.0,.54,.55),(.35,.54,.54),(.51,.38,.39)])
sleeve.location.x=1.1
bpy.ops.object.select_all(action='SELECT');bpy.ops.export_scene.fbx(filepath=str(OUT/'DesignerTeePanels.fbx'),use_selection=True,object_types={'MESH'})
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'DesignerTeePanels.blend'))
print('Normalized torso and sleeve shells exported')
