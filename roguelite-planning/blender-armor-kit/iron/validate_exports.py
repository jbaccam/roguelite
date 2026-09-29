"""Re-import the exported Iron set and check it against polygon-report.json.

    blender -b --factory-startup --python validate_exports.py

Checks, for the FBX and the GLB separately:
  * every mesh in the polygon report is present, with the same triangle count
  * no loose vertices, no zero-area faces, no non-finite coordinates
  * textured meshes carry one UV map inside 0-1 and a material with a baked image;
    glow meshes carry the glow material (Neon in Studio)
  * no vertex-colour layers (Roblox would read them as vertex colour)
  * the embedded/linked texture images exist and are 1024x1024 (Roblox's cap)
Writes validation-report.json. Blender-verified only; says nothing about Studio.
"""
import json
import math
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parent
SET = "iron"


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if path.suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    else:
        bpy.ops.import_scene.gltf(filepath=str(path))
    return {o.name.split(".")[0]: o for o in bpy.context.scene.objects if o.type == "MESH"}


rep = json.loads((ROOT / "polygon-report.json").read_text())
want = {n: v for d in rep["pieces"].values() for n, v in d.items()}
results = {}
for path in (ROOT / "exports" / "fbx" / f"{SET}.fbx", ROOT / "exports" / "glb" / f"{SET}.glb"):
    problems, checked = [], 0
    objs = load(path)
    for name, info in want.items():
        o = objs.get(name)
        if not o:
            problems.append(f"missing {name}")
            continue
        checked += 1
        m = o.data
        m.calc_loop_triangles()
        if len(m.loop_triangles) != info["triangles"]:
            problems.append(f"{name}: {len(m.loop_triangles)} tris, report says {info['triangles']}")
        used = set(v for p in m.polygons for v in p.vertices)
        loose = len(m.vertices) - len(used)
        if loose:
            problems.append(f"{name}: {loose} loose vertices")
        zero = sum(1 for p in m.polygons if p.area < 1e-8)
        if zero:
            problems.append(f"{name}: {zero} zero-area faces")
        if any(not all(math.isfinite(c) for c in v.co) for v in m.vertices):
            problems.append(f"{name}: non-finite coordinates")
        if m.color_attributes:
            problems.append(f"{name}: has vertex colour layers {[a.name for a in m.color_attributes]}")
        glow = name.endswith("_Glow")
        if not glow:
            if len(m.uv_layers) != 1:
                problems.append(f"{name}: {len(m.uv_layers)} UV maps")
            elif any(not (-1e-4 <= d.uv.x <= 1.0001 and -1e-4 <= d.uv.y <= 1.0001) for d in m.uv_layers[0].data):
                problems.append(f"{name}: UV outside 0-1")
            imgs = [n.image for s in o.material_slots if s.material
                    for n in s.material.node_tree.nodes if n.type == "TEX_IMAGE" and n.image]
            if not imgs:
                problems.append(f"{name}: no baked texture on its material")
        else:
            if not any(s.material and "Glow" in s.material.name for s in o.material_slots):
                problems.append(f"{name}: glow material missing")
    images = {}
    for im in bpy.data.images:
        if im.size[0] and im.size[1]:
            images[im.name] = list(im.size)
            if tuple(im.size) != (1024, 1024):
                problems.append(f"image {im.name} is {tuple(im.size)}, expected 1024x1024")
    results[path.suffix[1:]] = {"ok": not problems, "meshes_checked": checked, "meshes_expected": len(want),
                                "images": images, "problems": problems}
    print("VALIDATION", path.name, "ok" if not problems else problems[:8], flush=True)
(ROOT / "validation-report.json").write_text(json.dumps(results, indent=2))
