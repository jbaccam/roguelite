"""Non-destructive animation/export copies of the approved existing zombie masters."""
import bpy,bmesh,math,json,sys,random
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
ID=sys.argv[sys.argv.index('--')+1];OUT=ROOT/ID;OUT.mkdir(exist_ok=True)
sources={'baby-zombie':ROOT.parent/'baby-mutant-zombies/Baby/Model.blend',
 'tank-zombie':ROOT.parent/'baby-mutant-zombies/Mutant/Model.blend',
 'regular-zombie':ROOT.parent/'zombie-stock-r15-preview/supplied-textures/Zombie_Blender_Provided_Textures.blend'}
bpy.ops.wm.open_mainfile(filepath=str(sources[ID]));scene=bpy.context.scene
rigold=next(o for o in scene.objects if o.type=='ARMATURE')
parts={};bones={'Root':{'head':[0,0,0],'parent':None}}
for b in rigold.data.bones:
    if b.name=='HumanoidRootPart':continue
    bones[b.name]={'head':list(b.head_local),'parent':'Root' if not b.parent or b.parent.name=='HumanoidRootPart' else b.parent.name}
for o in list(scene.objects):
    if o.type=='MESH' and o.name in bones:
        world=o.matrix_world.copy();o.parent=None;o.matrix_world=world
        for m in list(o.modifiers):
            if m.type=='ARMATURE':o.modifiers.remove(m)
        o.vertex_groups.clear();parts[o.name]=[o]
    else:bpy.data.objects.remove(o,do_unlink=True)
assert len(parts)==15,(ID,list(parts))
for action in list(bpy.data.actions):bpy.data.actions.remove(action)
# Keep the original UV artwork, packed and also saved beside the delivery copy.
for olist in parts.values():
    for o in olist:
        for m in o.data.materials:
            if not m or not m.use_nodes:continue
            for n in m.node_tree.nodes:
                if n.type=='TEX_IMAGE' and n.image:
                    im=n.image;_=im.pixels[0];im.pack()
                    im.filepath_raw=str(OUT/(im.name.replace('/','_').replace('\\','_')+'.png'));im.file_format='PNG';im.save()
text=(ROOT/'deliver.py').read_text();text=text[text.index('rigdata=bpy.data.armatures.new'):]
exec(compile(text,str(ROOT/'deliver.py'),'exec'))
p=OUT/'manifest.json';m=json.loads(p.read_text());m['preservedSource']=str(sources[ID]);m['textureMethod']='Preserved source UV textures, no recoloring or remodeling';m['texture']='Packed source textures'
if ID=='regular-zombie':m['limitations'].append('This is the existing Blender comparison master; native Studio zombie remains authoritative and was not replaced.')
p.write_text(json.dumps(m,indent=2))
