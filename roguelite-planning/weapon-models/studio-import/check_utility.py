import bpy
from pathlib import Path
p=Path('C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning/weapon-models/studio-import')
bpy.ops.wm.open_mainfile(filepath=str(p/'Weapon_Showcase.blend'))
for o in bpy.data.objects:
 if o.type=='MESH' and (o.name.startswith('W20')or o.name.startswith('W22')):
  print(o.name,[(m.name,[(n.image.name,n.image.size[:]) for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image])for m in o.data.materials])

