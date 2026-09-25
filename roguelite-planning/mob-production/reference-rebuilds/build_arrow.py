"""Separate, textured projectile. Nock at origin; tip points down local -Y."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from meshlib import *
out=reset('bow-skeleton')
wood=mat('Arrow shaft',(.20,.105,.045),.18,18)
feather=mat('Cream fletching',(.62,.53,.34),.10,20)
metal=mat('Arrowhead steel',(.31,.33,.34),.08,30,rough=.42)
binding=mat('Flax binding',(.38,.29,.15),.10,24)
objects=[tube('Straight wooden shaft',[(0,0,0),(0,-1.56,0)],.024,wood,10)]
for y in [-.03,-.07,-.42,-.46,-1.47,-1.51]:
    objects.append(tube('Arrow binding',[(0,y+.014,0),(0,y-.014,0)],.032,binding,10))
for j in range(3):
    theta=j*math.tau/3
    radial=Vector((math.cos(theta),0,math.sin(theta)));side=Vector((-math.sin(theta),0,math.cos(theta)))
    profile=[(0,-.07),(.115,-.10),(.10,-.29),(0,-.43)]
    verts=[radial*r+Vector((0,y,0))+side*th for th in [-.012,.012] for r,y in profile]
    objects.append(mesh('Feather vane',verts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],feather))
verts=[(-.115,-1.54,0),(0,-1.54,.047),(.115,-1.54,0),(0,-1.54,-.047),(0,-1.90,0)]
objects.append(mesh('Pointed steel broadhead',verts,[(3,2,1,0),(0,1,4),(1,2,4),(2,3,4),(3,0,4)],metal))
arrow=join(objects,'ArrowProjectile')
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(island_margin=.015);bpy.ops.object.mode_set(mode='OBJECT')
image=bpy.data.images.new('ArrowBaseColor',width=512,height=512,alpha=False)
for m in set(arrow.data.materials):
    node=m.node_tree.nodes.new('ShaderNodeTexImage');node.image=image;m.node_tree.nodes.active=node
bpy.context.scene.render.engine='CYCLES';bpy.context.scene.cycles.samples=1
bpy.ops.object.bake(type='DIFFUSE',pass_filter={'COLOR'},margin=4)
image.filepath_raw=str(out/'ArrowBaseColor.png');image.file_format='PNG';image.save();image.pack()
for m in set(arrow.data.materials):
    tex=next(n for n in m.node_tree.nodes if n.type=='TEX_IMAGE')
    m.node_tree.links.new(tex.outputs['Color'],m.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
bpy.ops.wm.save_as_mainfile(filepath=str(out/'ArrowProjectile.blend'))
bpy.ops.export_scene.fbx(filepath=str(out/'ArrowProjectile.fbx'),use_selection=True,object_types={'MESH'},bake_anim=False,path_mode='COPY',embed_textures=True,axis_forward='-Z',axis_up='Y')
bpy.ops.export_scene.gltf(filepath=str(out/'ArrowProjectile.glb'),use_selection=True,export_format='GLB',export_animations=False)
arrow.data.calc_loop_triangles()
(out/'ArrowProjectile.json').write_text(json.dumps({'origin':'nock','blenderForward':[0,-1,0],'length':1.90,'triangles':len(arrow.data.loop_triangles),'texture':'ArrowBaseColor.png','separateFromCharacter':True},indent=2))
print('ARROW_COMPLETE',flush=True)
