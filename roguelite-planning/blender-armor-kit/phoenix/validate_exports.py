"""Re-import the exported Phoenix v2 set and check it against polygon-report.json and studio-install-data.json.

    blender -b --factory-startup --python validate_exports.py

Checks, for the FBX and the GLB separately:
  * every mesh in the polygon report is present, with the same triangle count
  * no loose vertices, no zero-area faces, no non-finite coordinates
  * textured meshes carry one UV map inside 0-1 and a material with a baked image;
    glow meshes carry the glow material (Neon in Studio)
  * no vertex-colour layers (Roblox would read them as vertex colour)
  * the embedded/linked texture images exist and are 1024x1024 (Roblox's cap)
  * install data: helmet 'full', the wings mesh on UpperTorso, glow colours, and a complete vfx list
Writes validation-report.json. Blender-verified only; says nothing about Studio.
"""
import json
import math
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parent
SET = "phoenix"


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

# Phoenix extras: the install data carries the full-helm mode, both Neon colours, the wings mesh and the vfx list.
inst = json.loads((ROOT / "studio-install-data.json").read_text())
extra = []
if inst.get("helmet") != "full":
    extra.append("helmet mode is not 'full'")
vfx = inst.get("vfx", [])
kinds = [v["kind"] for v in vfx]
if kinds.count("light") < 2:
    extra.append(f"expected a core light and a wing light, found {kinds.count('light')} lights")
for k in ("flame_plume", "flame_sheet", "embers_rise", "ember_swirl", "heat_glow"):
    if k not in kinds:
        extra.append(f"no {k} vfx")
need = {"ParticleEmitter": ("Texture", "Rate", "Lifetime", "Speed", "SpreadAngle", "Size", "Transparency", "Color",
                            "LightEmission", "LightInfluence", "Drag", "Acceleration", "Rotation", "RotSpeed",
                            "EmissionDirection"),
        "PointLight": ("Brightness", "Range", "Color")}
for v in vfx:
    missing = [k for k in need[v["class"]] if k not in v["properties"]]
    if missing:
        extra.append(f"vfx {v['name']} missing {missing}")
    if v.get("parent") == "attachment" and "position" not in v.get("attachment", {}):
        extra.append(f"vfx {v['name']} has no attachment position")
    for k in ("body_part", "piece"):
        if not v.get(k):
            extra.append(f"vfx {v['name']} has no {k}")
for tex in inst.get("particle_textures", {}).values():
    if not (ROOT / tex).exists():
        extra.append(f"particle texture missing: {tex}")
glows = {n: p for n, p in inst["parts"].items() if p["kind"] == "glow"}
if not glows:
    extra.append("no glow meshes")
if any("color_srgb" not in p for p in glows.values()):
    extra.append("glow part without color_srgb")
wings = inst["parts"].get("Phoenix_Chest_Wings")
if not wings or wings["body_part"] != "UpperTorso":
    extra.append("Phoenix_Chest_Wings missing or not on UpperTorso")
big = [n for n, v in want.items() if v["triangles"] >= 20000]
if big:
    extra.append(f"meshes over 20k triangles: {big}")
total = sum(v["triangles"] for v in want.values())
results["install_data"] = {"ok": not extra, "triangles_total": total, "vfx_count": len(vfx),
                           "vfx_kinds": {k: kinds.count(k) for k in sorted(set(kinds))}, "problems": extra}
print("VALIDATION install data", "ok" if not extra else extra, total, "tris", flush=True)
(ROOT / "validation-report.json").write_text(json.dumps(results, indent=2))
