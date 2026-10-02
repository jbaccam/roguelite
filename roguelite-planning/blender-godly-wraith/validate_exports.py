"""Re-import the exported Crimson Wraith (FBX and GLB) and check it against polygon-report.json.

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python validate_exports.py

Checks, for each file:
  - exactly the five expected mesh objects, named as in the report
  - triangle count per part equals the report
  - 0 loose vertices and 0 zero-area faces (world-space area below 1e-9 square studs)
  - world-space bounding box per part matches the report within 0.005 studs (after the importer's axis conversion)
  - each object's origin sits on its reported pivot within 0.005 studs (arms: the shoulder joints)
  - the textured parts carry an image texture (FBX: the embedded BaseColor) and a UV map inside 0-1
Writes validation-report.json. This is Blender-verified only; it says nothing about Studio.
"""
import json
from pathlib import Path

import bmesh
import bpy

ROOT = Path(__file__).resolve().parent
REPORT = json.loads((ROOT / "polygon-report.json").read_text())
FILES = {"fbx": ROOT / "exports" / "fbx" / "Wraith.fbx", "glb": ROOT / "exports" / "glb" / "Wraith.glb"}
TOL = 0.005


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if path.suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    else:
        bpy.ops.import_scene.gltf(filepath=str(path))
    bpy.context.view_layer.update()
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def image_of(o):
    for slot in o.material_slots:
        m = slot.material
        if m and m.node_tree:
            for n in m.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image:
                    return n.image
    return None


def close(a, b, tol=TOL):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


results = {}
for kind, path in FILES.items():
    problems, parts = [], {}
    objs = load(path)
    names = sorted(o.name for o in objs)
    want = sorted(REPORT["parts"])
    if names != want:
        problems.append(f"objects {names} != expected {want}")
    for o in objs:
        rep = REPORT["parts"].get(o.name)
        if rep is None:
            continue
        me = o.data
        me.calc_loop_triangles()
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.transform(o.matrix_world)
        loose = sum(1 for v in bm.verts if not v.link_faces)
        zero = sum(1 for f in bm.faces if f.calc_area() < 1e-9)
        ws = [v.co.copy() for v in bm.verts]
        bm.free()
        mn = [round(min(v[i] for v in ws), 4) for i in range(3)]
        mx = [round(max(v[i] for v in ws), 4) for i in range(3)]
        piv = [round(x, 4) for x in o.matrix_world.translation]
        img = image_of(o)
        uv_ok = None
        if me.uv_layers:
            uv = [c for d in me.uv_layers[0].data for c in d.uv]
            uv_ok = min(uv) >= -1e-4 and max(uv) <= 1 + 1e-4
        entry = {"triangles": len(me.loop_triangles), "expected_triangles": rep["triangles"], "loose_vertices": loose,
                 "zero_area_faces": zero, "bbox_min": mn, "bbox_max": mx, "origin": piv, "expected_origin": rep["pivot"],
                 "image": f"{img.name} {img.size[0]}x{img.size[1]}" if img else None, "uv_inside_0_1": uv_ok}
        if entry["triangles"] != rep["triangles"]:
            problems.append(f"{o.name}: triangles {entry['triangles']} != {rep['triangles']}")
        if loose:
            problems.append(f"{o.name}: {loose} loose vertices")
        if zero:
            problems.append(f"{o.name}: {zero} zero-area faces")
        if not (close(mn, rep["bbox_min"]) and close(mx, rep["bbox_max"])):
            problems.append(f"{o.name}: bbox {mn}..{mx} != {rep['bbox_min']}..{rep['bbox_max']}")
        if not close(piv, rep["pivot"]):
            problems.append(f"{o.name}: origin {piv} != {rep['pivot']}")
        if rep["kind"] == "textured":
            if img is None or img.size[0] == 0:
                problems.append(f"{o.name}: no image texture after import")
            if uv_ok is not True:
                problems.append(f"{o.name}: UVs missing or outside 0-1")
        parts[o.name] = entry
    results[kind] = {"file": str(path.relative_to(ROOT)).replace("\\", "/"), "meshes": len(objs),
                     "total_triangles": sum(p["triangles"] for p in parts.values()),
                     "images": sorted(f"{i.name} {i.size[0]}x{i.size[1]}" for i in bpy.data.images if i.size[0] > 0),
                     "parts": parts, "problems": problems, "pass": not problems}

out = {"asset": REPORT["asset"], "blender_version": bpy.app.version_string,
       "expected_total_triangles": REPORT["total_triangles"], "results": results,
       "all_pass": all(r["pass"] for r in results.values()),
       "note": "Blender re-import only. Studio import, Neon look, TextureID and in-game scale are untested."}
(ROOT / "validation-report.json").write_text(json.dumps(out, indent=1))
print("VALIDATION", "PASS" if out["all_pass"] else "FAIL", {k: r["problems"] for k, r in results.items()}, flush=True)
