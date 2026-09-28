import bpy, json
from mathutils import Vector
out = {}
for o in bpy.data.objects:
    if o.type != "MESH" or not o.name.startswith("Armory_") or o.hide_render:
        continue
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c, s = (lo + hi) / 2, hi - lo
    # Studio axes after the FBX importer: (-x, z, y)
    out[o.name] = {"center": [round(-c.x, 4), round(c.z, 4), round(c.y, 4)], "size": [round(s.x, 4), round(s.z, 4), round(s.y, 4)]}
print("BOUNDS", json.dumps(out))
