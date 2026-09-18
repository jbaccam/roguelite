import bpy,json,math
from mathutils import Vector,Matrix
from pathlib import Path
p=Path('C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning/weapon-models/studio-import')
bpy.ops.wm.open_mainfile(filepath=str(p/'Weapon_Showcase.blend'))
o=bpy.data.objects['W03_Katana'];pts=[o.matrix_world@v.co for v in o.data.vertices]
# Convert Blender world to Studio mesh coordinates, then center using imported MeshPart bounds.
v=[Vector((-a.x,a.z,a.y)) for a in pts]
lo=Vector([min(a[i] for a in v) for i in range(3)]);hi=Vector([max(a[i] for a in v) for i in range(3)])
scale=4.410099983215332/(hi.x-lo.x)
r=Matrix.Rotation(.97,3,'Z');v=[r@((a-(lo+hi)/2)*scale)for a in v]
lo=Vector([min(a[i] for a in v) for i in range(3)]);hi=Vector([max(a[i] for a in v) for i in range(3)]);size=hi-lo
bottom=[a for a in v if a.y<lo.y+size.y*.20]
grip=Vector((sum(a.x for a in bottom)/len(bottom),lo.y+size.y*.10,(lo.z+hi.z)/2))
data={'size':list(size),'center':list((lo+hi)/2-grip),'grip':list(grip),'meshScale':scale}
Path('C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning/studio-prototype/combat/katana-geometry.json').write_text(json.dumps(data,indent=2))
print(json.dumps(data))
