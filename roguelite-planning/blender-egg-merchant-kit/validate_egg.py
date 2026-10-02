"""Re-import the exported egg kit fresh and check it against polygon-report-egg.json.

    blender --background --python validate_egg.py

FBX and GLB each: exactly the expected object names and count, triangle counts match the report,
world-space dimensions match within 1%, every UV inside 0-1, no zero-area faces, identity object
transforms. Writes validation-report-egg.json. Blender-verified only; says nothing about Studio.
"""
import json
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
REP = json.loads((ROOT / "polygon-report-egg.json").read_text())
WANT = REP["parts"]


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if path.suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    else:
        bpy.ops.import_scene.gltf(filepath=str(path))
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def is_identity(m, tol=1e-4):
    ident = Matrix.Identity(4)
    return all(abs(m[i][j] - ident[i][j]) < tol for i in range(4) for j in range(4))


results = {}
for path in (ROOT / "exports/fbx/egg-kit.fbx", ROOT / "exports/glb/egg-kit.glb"):
    problems, parts = [], {}
    objs = load(path)
    names = {o.name.split(".")[0]: o for o in objs}
    if len(objs) != len(WANT):
        problems.append(f"{len(objs)} meshes, expected {len(WANT)}")
    for extra in sorted(set(names) - set(WANT)):
        problems.append(f"unexpected object {extra}")
    for name, want in WANT.items():
        o = names.get(name)
        if o is None:
            problems.append(f"missing {name}")
            continue
        m = o.data
        m.calc_loop_triangles()
        tris = len(m.loop_triangles)
        if tris != want["triangles"]:
            problems.append(f"{name}: {tris} tris, report says {want['triangles']}")
        ws = [o.matrix_world @ v.co for v in m.vertices]
        dims = [max(c[k] for c in ws) - min(c[k] for c in ws) for k in range(3)]
        if any(abs(a - b) > max(0.01, 0.01 * b) for a, b in zip(dims, want["dimensions_studs"])):
            problems.append(f"{name}: dimensions {[round(d, 3) for d in dims]} vs {want['dimensions_studs']}")
        uv = m.uv_layers.get("UVMap") or m.uv_layers.active
        uv_ok = uv is not None and all(-1e-4 <= d.uv.x <= 1.0001 and -1e-4 <= d.uv.y <= 1.0001 for d in uv.data)
        if not uv_ok:
            problems.append(f"{name}: UV missing or outside 0-1")
        zero = sum(1 for p in m.polygons if p.area < 1e-7)
        if zero:
            problems.append(f"{name}: {zero} zero-area faces")
        ident = is_identity(o.matrix_world) and o.parent is None
        if not ident:
            problems.append(f"{name}: transform not identity (loc {tuple(round(v, 4) for v in o.matrix_world.translation)}, "
                            f"rot {tuple(round(v, 4) for v in o.matrix_world.to_euler())}, scale {tuple(round(v, 4) for v in o.matrix_world.to_scale())})")
        parts[name] = {"tris": tris, "dims": [round(d, 4) for d in dims], "uv_layers": [l.name for l in m.uv_layers],
                       "zero_area_faces": zero, "identity_transform": ident}
    results[path.suffix[1:]] = {"ok": not problems, "problems": problems, "objects": len(objs), "parts": parts}

(ROOT / "validation-report-egg.json").write_text(json.dumps(results, indent=2))
print("VALIDATION", json.dumps({k: {"ok": v["ok"], "problems": v["problems"]} for k, v in results.items()}), flush=True)
