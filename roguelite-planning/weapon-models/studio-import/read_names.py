import bpy,json
from pathlib import Path
p=Path('C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning/weapon-models/studio-import')
bpy.ops.wm.open_mainfile(filepath=str(p/'Weapon_Showcase.blend'))
a=[{'name':o.name,'data':o.data.name,'vertices':len(o.data.vertices)} for o in bpy.data.objects if o.type=='MESH']
(p/'mesh_names.json').write_text(json.dumps(a,indent=2))
