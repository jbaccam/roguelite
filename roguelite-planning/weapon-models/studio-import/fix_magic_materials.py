import bpy,numpy as np
from pathlib import Path
P=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(P/'Weapon_Showcase.blend'))
p=bpy.data.objects['W33_Pandoras_Box']
imgs=[];mapping={}
for i,m in enumerate(p.data.materials):
 im=next(n.image for n in m.node_tree.nodes if n.type=='TEX_IMAGE')
 if im not in imgs:imgs.append(im)
 mapping[i]=imgs.index(im)
side=256
atlas=np.ones((side,side*len(imgs),4),dtype=np.float32)
for i,im in enumerate(imgs):
 w,h=im.size;arr=np.array(im.pixels[:],dtype=np.float32).reshape(h,w,4)
 yy=np.minimum((np.arange(side)*h/side).astype(int),h-1);xx=np.minimum((np.arange(side)*w/side).astype(int),w-1)
 atlas[:,i*side:(i+1)*side,:]=arr[yy[:,None],xx[None,:],:]
im=bpy.data.images.new('Pandora_Unified_Atlas',width=side*len(imgs),height=side,alpha=True)
im.pixels.foreach_set(atlas.ravel());im.filepath_raw=str(P/'textures/Pandora_Unified_Atlas.png');im.file_format='PNG';im.save()
uv=p.data.uv_layers.active
for poly in p.data.polygons:
 tile=mapping[poly.material_index]
 for li in poly.loop_indices:uv.data[li].uv.x=(uv.data[li].uv.x+tile)/len(imgs)
 poly.material_index=0
mat=bpy.data.materials.new('Pandora_Unified');mat.use_nodes=True
tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=im
mat.node_tree.links.new(tex.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
p.data.materials.clear();p.data.materials.append(mat)
# Keep translucent crystal shell separate from the solid pedestal and inner symbol.
crystal=bpy.data.objects['W35_Crystal_Ball']
bpy.ops.object.select_all(action='DESELECT');crystal.select_set(True);bpy.context.view_layer.objects.active=crystal
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.separate(type='MATERIAL');bpy.ops.object.mode_set(mode='OBJECT')
crystals=[o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('W35')]
for o in crystals:
 name=o.data.materials[0].name
 o.name='W35_Crystal_'+('Shell' if 'shell' in name.lower() else 'Core' if 'interior' in name.lower() else 'Base')
bpy.ops.object.select_all(action='DESELECT')
p.select_set(True)
for o in crystals:o.select_set(True)
arm=next(mod.object for mod in p.modifiers if mod.type=='ARMATURE');arm.select_set(True)
bpy.ops.export_scene.fbx(filepath=str(P/'Magic_Material_Fix.fbx'),use_selection=True,object_types={'MESH','ARMATURE'},add_leaf_bones=False,bake_anim=False,path_mode='COPY',embed_textures=True,axis_forward='-Z',axis_up='Y')
print('READY MAGIC FIX')
# Retain a complete corrected Blender/FBX source for future imports.
for name,filename in [('W20_Cinder_Blocks','Cinder_Corrected.png'),('W22_Bowling_Ball','Bowling_Charcoal_Corrected.png')]:
 o=bpy.data.objects[name]
 texture=bpy.data.images.load(str(P/'textures'/filename),check_existing=True)
 texture.pack()
 for material in o.data.materials:
  for node in material.node_tree.nodes:
   if node.type=='TEX_IMAGE':node.image=texture
bpy.ops.object.select_all(action='DESELECT')
for o in bpy.data.objects:
 if o.type in {'MESH','ARMATURE'}:o.select_set(True)
bpy.ops.wm.save_as_mainfile(filepath=str(P/'Weapon_Showcase_Corrected.blend'))
bpy.ops.export_scene.fbx(filepath=str(P/'Weapon_Showcase_Corrected.fbx'),use_selection=True,object_types={'MESH','ARMATURE'},add_leaf_bones=False,bake_anim=False,path_mode='COPY',embed_textures=True,axis_forward='-Z',axis_up='Y')
