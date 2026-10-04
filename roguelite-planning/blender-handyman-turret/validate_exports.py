"""Re-import every exported turret tier and check it against exports/turret-spec.json.

    blender --background --python validate_exports.py

Per tier, for both the FBX and the GLB:
  * exactly the contract mesh names (HandymanTurret_T{n}_Base / _Head / _Barrel [/ _Glow]), no suffixes;
  * transforms applied: identity rotation, unit scale, object origin == the spec pivot;
  * triangle counts == spec == polygon-report.json, total within the tier budget;
  * bounding-box centre and size == spec (what a Studio normaliser matches against);
  * textured parts have every UV inside 0-1; no zero-area faces.
FBX axes: the file is re-imported a second time with NO axis conversion, which shows the raw file
space. It must be Y-up with the barrels toward +Z(file). Studio's importer turn (x, y, z) -> (-x, y, -z)
(seen on the chest, armory and island kits) then gives the spec's Roblox positions: pivots, part
boxes, and the Barrel's front-most vertices at the muzzle Z (forward = -Z, the LookVector).
Spec checks: height, radius <= 2.5, muzzle count per tier, spin only on T4, texture 1024 px,
icons 512 px RGBA. Writes validation-report.json. Blender-verified only; says nothing about Studio.
"""
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
SPEC = json.loads((ROOT / "exports/turret-spec.json").read_text())
REP = json.loads((ROOT / "polygon-report.json").read_text())
TOL = 2e-3
MUZZLES = {"T1": 1, "T2": 2, "T3": 4, "T4": 6}


def to_blender(r):
    return Vector((-r[0], r[2], r[1]))


def raw_to_roblox(p):
    return Vector((-p[0], p[1], -p[2]))


def load(path, raw=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if path.suffix == ".fbx":
        if raw:
            bpy.ops.import_scene.fbx(filepath=str(path), use_manual_orientation=True, axis_forward="Y", axis_up="Z")
        else:
            bpy.ops.import_scene.fbx(filepath=str(path))
    else:
        bpy.ops.import_scene.gltf(filepath=str(path))
    bpy.context.view_layer.update()
    return {o.name: o for o in bpy.context.scene.objects if o.type == "MESH"}


def bbox(points):
    lo = Vector([min(p[i] for p in points) for i in range(3)])
    hi = Vector([max(p[i] for p in points) for i in range(3)])
    return (lo + hi) / 2, hi - lo


def close(a, b, tol=TOL):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


report = {"blender_version": bpy.app.version_string, "tiers": {}}
all_ok = True
for tier, ts in SPEC["tiers"].items():
    problems, info = [], {}
    parts = ts["parts"]
    expected = {p["mesh"] for p in parts.values()}
    for role, p in parts.items():
        if p["mesh"] != f"HandymanTurret_{tier}_{role}":
            problems.append(f"{role}: mesh name {p['mesh']} breaks the contract")
    for fmt in ("fbx", "glb"):
        path = ROOT / ts[fmt]
        if not path.exists():
            problems.append(f"{fmt}: missing {path.name}")
            continue
        objs = load(path)
        if set(objs) != expected:
            problems.append(f"{fmt}: meshes {sorted(objs)} != {sorted(expected)}")
        for role, p in parts.items():
            o = objs.get(p["mesh"])
            if o is None:
                continue
            mw = o.matrix_world
            loc, rot, scale = mw.decompose()
            if (loc - to_blender(p["pivot"])).length > TOL:
                problems.append(f"{fmt} {role}: origin {tuple(round(v, 3) for v in loc)} != pivot")
            if rot.angle > 1e-3 or any(abs(s - 1) > 1e-3 for s in scale):
                problems.append(f"{fmt} {role}: transform not applied (rot {math.degrees(rot.angle):.2f} deg, scale {tuple(scale)})")
            me = o.data
            me.calc_loop_triangles()
            if len(me.loop_triangles) != p["triangles"]:
                problems.append(f"{fmt} {role}: {len(me.loop_triangles)} tris, spec {p['triangles']}")
            c, s = bbox([mw @ v.co for v in me.vertices])
            if not close(c, to_blender(p["center"])) or not close((s.x, s.z, s.y), p["size"]):
                problems.append(f"{fmt} {role}: bbox centre/size differ from spec")
            if role != "Glow":
                uv = me.uv_layers.active
                if uv is None or any(not (-1e-4 <= d.uv.x <= 1.0001 and -1e-4 <= d.uv.y <= 1.0001) for d in uv.data):
                    problems.append(f"{fmt} {role}: UV missing or outside 0-1")
            if any(f.area < 1e-8 for f in me.polygons):
                problems.append(f"{fmt} {role}: zero-area faces")
    # raw FBX file space -> Roblox via the importer's 180 degree turn
    objs = load(ROOT / ts["fbx"], raw=True)
    raw_nodes = {}
    for role, p in parts.items():
        o = objs.get(p["mesh"])
        if o is None:
            continue
        mw = o.matrix_world
        raw_nodes[role] = [round(math.degrees(a), 1) for a in mw.to_euler()]
        piv = raw_to_roblox(mw.translation)
        if not close(piv, p["pivot"]):
            problems.append(f"raw fbx {role}: pivot {tuple(round(v, 3) for v in piv)} != spec {p['pivot']}")
        pts = [raw_to_roblox(mw @ v.co) for v in o.data.vertices]
        c, s = bbox(pts)
        if not close(c, p["center"]) or not close(s, p["size"]):
            problems.append(f"raw fbx {role}: box differs from spec (centre {tuple(round(v, 3) for v in c)})")
        if role == "Barrel":
            front = min(q.z for q in pts)
            want = min(m[2] for m in ts["muzzles"])
            info["barrel_front_z"] = round(front, 4)
            if abs(front - want) > 0.01:
                problems.append(f"raw fbx: barrel front z {front:.3f} != muzzle z {want:.3f} (forward must be -Z)")
            if not front < p["pivot"][2]:
                problems.append("raw fbx: barrel does not point to -Z")
    head = parts["Head"]["pivot"]
    if not (head[1] > 1.5 and abs(head[0]) < TOL and abs(head[2]) < TOL):
        problems.append("Head pivot is not on the vertical yaw axis above the base (Y up)")
    info["raw_fbx_node_rotation_deg"] = raw_nodes
    # spec-level checks
    tri_total = sum(p["triangles"] for p in parts.values())
    if tri_total != ts["triangles"]["total"] or tri_total != REP["tiers"][tier]["triangles"]["total"]:
        problems.append("triangle totals disagree between spec, report and parts")
    if tri_total > REP["budgets"][tier[1:]]:
        problems.append(f"{tri_total} tris over budget {REP['budgets'][tier[1:]]}")
    top = max(p["center"][1] + p["size"][1] / 2 for p in parts.values())
    if abs(top - ts["height"]) > 0.01:
        problems.append(f"height {ts['height']} != part tops {top:.3f}")
    if ts["radius"] > 2.5:
        problems.append(f"radius {ts['radius']} > 2.5")
    if len(ts["muzzles"]) != MUZZLES[tier]:
        problems.append(f"{len(ts['muzzles'])} muzzles, expected {MUZZLES[tier]}")
    if ts["spin"] != (tier == "T4"):
        problems.append("spin flag wrong")
    tex = ROOT / "textures" / ts["texture"]
    if not tex.exists():
        problems.append(f"missing texture {tex.name}")
    else:
        im = bpy.data.images.load(str(tex))
        if tuple(im.size) != (1024, 1024):
            problems.append(f"texture is {tuple(im.size)}, expected 1024")
    icon = ROOT / ts["icon"]
    if not icon.exists():
        problems.append(f"missing icon {icon.name}")
    else:
        im = bpy.data.images.load(str(icon))
        if tuple(im.size) != (512, 512) or im.channels != 4:
            problems.append(f"icon is {tuple(im.size)} with {im.channels} channels, expected 512 RGBA")
    info.update({"triangles": tri_total, "height": ts["height"], "radius": ts["radius"],
                 "muzzles": len(ts["muzzles"]), "spin": ts["spin"]})
    report["tiers"][tier] = {"ok": not problems, "problems": problems, **info}
    all_ok &= not problems
    print("VALIDATION", tier, "OK" if not problems else problems, flush=True)

report["ok"] = all_ok
report["note"] = "Blender re-import only (FBX twice: normal and raw axes; GLB once). Studio untested."
(ROOT / "validation-report.json").write_text(json.dumps(report, indent=2))
print("VALIDATION_DONE", all_ok, flush=True)
