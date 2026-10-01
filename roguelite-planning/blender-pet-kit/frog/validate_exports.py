"""Re-import the exported Frog (FBX and GLB) and check it against polygon-report.json.

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python validate_exports.py

Checks, for each file:
  - exactly the expected mesh objects, named as in the report (six rigid parts)
  - triangle count per part equals the report
  - world-space bounding box per part matches the report within 0.005 studs, and the sorted
    dimensions within 1% (Blender axes, after the importer's own axis conversion)
  - each object's origin sits on its reported joint pivot within 0.005 studs
  - every UV on the first UV map is inside 0-1
  - no zero-area triangles (world-space area below 1e-7 square studs)
  - every part has a material with an image texture, and all parts share the same image
  - the total height / length stays inside the brief (1.9-2.6 studs to the head top, 1.8-3.0 long)
Also checks the texture file is 1024x1024 and that studio-install-data.json covers every part with
a pivot and a joint parent. Writes validation-report.json. Blender-verified only; says nothing about Studio.
"""
import json
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parent
STEM = "frog"
REPORT = json.loads((ROOT / "polygon-report.json").read_text())
INSTALL = json.loads((ROOT / "studio-install-data.json").read_text())
FILES = [ROOT / "exports" / "fbx" / f"{STEM}.fbx", ROOT / "exports" / "glb" / f"{STEM}.glb"]
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
for path in FILES:
    problems, found = [], {}
    objs = load(path)
    names = [o.name.split(".")[0] for o in objs]
    want = set(REPORT["parts"])
    if sorted(names) != sorted(want):
        problems.append(f"objects {sorted(names)} != expected {sorted(want)}")
    images = set()
    lo_all, hi_all = [1e9] * 3, [-1e9] * 3
    for o in objs:
        name = o.name.split(".")[0]
        rep = REPORT["parts"].get(name)
        if rep is None:
            continue
        me = o.data
        me.calc_loop_triangles()
        mw = o.matrix_world
        ws = [mw @ v.co for v in me.vertices]
        lo = [min(w[k] for w in ws) for k in range(3)]
        hi = [max(w[k] for w in ws) for k in range(3)]
        lo_all = [min(a, b) for a, b in zip(lo_all, lo)]
        hi_all = [max(a, b) for a, b in zip(hi_all, hi)]
        pivot = list(mw.translation)
        tris = len(me.loop_triangles)
        info = {"triangles": tris, "pivot": [round(v, 4) for v in pivot],
                "bbox_min": [round(v, 4) for v in lo], "bbox_max": [round(v, 4) for v in hi]}
        if tris != rep["triangles"]:
            problems.append(f"{name}: {tris} tris, report says {rep['triangles']}")
        if not (close(lo, rep["bbox_min"]) and close(hi, rep["bbox_max"])):
            problems.append(f"{name}: bbox {info['bbox_min']}..{info['bbox_max']} vs {rep['bbox_min']}..{rep['bbox_max']}")
        dims = sorted(h - l for l, h in zip(lo, hi))
        ref = sorted(rep["dimensions_studs"])
        if any(abs(a - b) > max(0.002, 0.01 * b) for a, b in zip(dims, ref)):
            problems.append(f"{name}: dimensions {[round(d, 4) for d in dims]} vs {ref}")
        if not close(pivot, rep["pivot"]):
            problems.append(f"{name}: origin {info['pivot']} is not on the pivot {rep['pivot']}")
        uv = me.uv_layers[0] if me.uv_layers else None
        if uv is None:
            problems.append(f"{name}: no UV map")
        elif any(not (-1e-4 <= d.uv.x <= 1.0001 and -1e-4 <= d.uv.y <= 1.0001) for d in uv.data):
            problems.append(f"{name}: UV outside 0-1")
        tiny = 0
        for t in me.loop_triangles:
            a, b, c = (ws[i] for i in t.vertices)
            if (b - a).cross(c - a).length * 0.5 < 1e-7:
                tiny += 1
        info["zero_area_triangles"] = tiny
        if tiny:
            problems.append(f"{name}: {tiny} zero-area triangles")
        img = image_of(o)
        if img is None:
            problems.append(f"{name}: no image texture on its material")
        else:
            images.add(img.name)
            info["texture"] = [img.name, list(img.size)]
        found[name] = info
    if len(images) > 1:
        problems.append(f"parts use different images: {sorted(images)}")
    head_top = hi_all[2]
    length = hi_all[1] - lo_all[1]
    if not (1.9 <= head_top <= 2.6):
        problems.append(f"height to the head top {head_top:.3f} is outside 1.9-2.6 studs")
    if not (1.8 <= length <= 3.0):
        problems.append(f"length {length:.3f} is outside 1.8-3.0 studs")
    results[path.suffix[1:]] = {"file": str(path.relative_to(ROOT)).replace("\\", "/"), "ok": not problems,
                                "objects": len(objs), "total_triangles": sum(v["triangles"] for v in found.values()),
                                "head_top_studs": round(head_top, 4), "length_studs": round(length, 4),
                                "problems": problems, "parts": found}

tex = ROOT / "textures" / f"{STEM}.png"
img = bpy.data.images.load(str(tex), check_existing=False)
results["texture"] = {"file": f"textures/{STEM}.png", "size": list(img.size), "ok": tuple(img.size) == (1024, 1024)}
inst_problems = []
for name in REPORT["parts"]:
    part = INSTALL["parts"].get(name)
    if part is None:
        inst_problems.append(f"{name}: missing from studio-install-data.json")
        continue
    for key in ("center", "size", "pivot", "pivot_from_body_pivot", "joint_parent"):
        if key not in part:
            inst_problems.append(f"{name}: no {key}")
    rp = REPORT["parts"][name]["pivot"]
    if not close(part.get("pivot", [9, 9, 9]), [-rp[0], rp[2], rp[1]], 1e-3):
        inst_problems.append(f"{name}: Studio pivot {part.get('pivot')} is not (-x, z, y) of {rp}")
results["install_data"] = {"file": "studio-install-data.json", "ok": not inst_problems, "problems": inst_problems}
results["all_ok"] = all(r["ok"] for r in results.values() if isinstance(r, dict))
results["expected_parts"] = sorted(REPORT["parts"])
results["scope"] = "Blender re-import only (Blender " + bpy.app.version_string + "); Studio untested"
(ROOT / "validation-report.json").write_text(json.dumps(results, indent=2))
print("VALIDATION", "PASS" if results["all_ok"] else "FAIL",
      json.dumps({k: (v["ok"], v.get("problems")) for k, v in results.items() if isinstance(v, dict)}), flush=True)
if not results["all_ok"]:
    sys.exit(1)
