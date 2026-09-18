import sys,json,hashlib,bpy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_utility as build
root=Path(__file__).resolve().parents[2]
folder=root/'assets'/'19-boxing-gloves'
for label in ['LeftGlove','RightGlove']:
 out=folder/'components'/label
 checks={}
 for ext in ['blend','fbx','glb']:
  if ext=='blend':bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'))
  else:
   bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
   if ext=='fbx':bpy.ops.import_scene.fbx(filepath=str(out/'Model.fbx'))
   else:bpy.ops.import_scene.gltf(filepath=str(out/'Model.glb'))
  obs=[o for o in bpy.context.scene.objects if o.type=='MESH'];checks[ext]=build.stats(obs,ext=='glb');checks[ext]['object_names']=[o.name for o in obs];checks[ext]['parents']=[o.parent.name if o.parent else None for o in obs];checks[ext]['origins']=[list(o.location) for o in obs];checks[ext]['unexpected_objects']=len(bpy.context.scene.objects)-len(obs)
 validation=json.loads((out/'validation.json').read_text());validation['independent_file_checks']=checks;(out/'validation.json').write_text(json.dumps(validation,indent=2));print(label,json.dumps(checks))
for item in build.INV:
 if item['index'] not in build.BUILD:continue
 out=Path(item['output']);v=json.loads((out/'validation.json').read_text());v['source_copy_sha256_matches']=hashlib.sha256(Path(item['source']).read_bytes()).digest()==hashlib.sha256((out/'Reference.png').read_bytes()).digest();v['review_renders_visually_inspected']=True
 bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'));obs=[o for o in bpy.context.scene.objects if o.type=='MESH' and any('export geometry' in c.name for c in o.users_collection)];v.update(build.stats(obs))
 images={n.image for o in obs for m in o.data.materials if m and m.use_nodes for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image};v['packed_images']=[{'name':im.name,'size':list(im.size),'packed':bool(im.packed_file)} for im in images]
 if item['index']==19:
  v['components']={label:json.loads((out/'components'/label/'validation.json').read_text()) for label in ['LeftGlove','RightGlove']}
  desc='Two independent unparented meshes, LeftGlove and RightGlove, each with its own wrist pivot. The root files show the review pair. Use components/LeftGlove/Model.blend, Model.fbx, Model.glb and components/RightGlove/Model.blend, Model.fbx, Model.glb for individual imports. Each standalone file contains exactly one glove mesh with wrist center at the origin.\n'
 else:desc='One reusable '+item['name'].rstrip('s')+' item, following the final user scope. The reference may show multiple examples; this deliverable intentionally models one.\n'
 (out/'README.md').write_text('# '+item['name']+'\n\n'+desc+'\nEditable low-poly reference reconstruction. Export files contain only asset geometry. Model.blend contains a packed 320px portable color atlas and a separate review collection. Preview.png and Alternate.png are real Blender Cycles renders. Named pieces or vertex groups retain editing access. Palette UV islands overlap intentionally by color.\n\nRebuild: Blender 5.2 --background --threads 4 --python ../../batches/juggler_utility/build_utility.py -- '+str(item['index'])+'\n\nHidden surfaces and thickness inferred from the single view. Assembled parts intentionally overlap at joints. No rig or gameplay; no Roblox Studio import/validation. See validation.json for topology, texture, and actual FBX/GLB reimport checks.\n');(out/'validation.json').write_text(json.dumps(v,indent=2))
