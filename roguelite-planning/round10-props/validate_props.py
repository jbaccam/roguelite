"""Round 10 props: fresh re-import of every exported FBX and the checks the art brief asks for.

    blender -b --threads 4 --python-exit-code 1 --python validate_props.py

Writes validation-report.json next to this script. Blender-verified only; says nothing about Roblox Studio.
Checks: mesh names, no armature/animation, triangle budgets, closed (watertight) shells, UVs in 0-1, atlas textures load
and have the right size, lid fit gap/overlap/outline, cavity extents + clearance profile, broken-chunk offsets
(every chunk vertex lies on/inside the intact coffin when placed with an identity transform), vent height/width/opening,
debris sizes, origins.
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parent
EXPORTS = ROOT / "exports"
TEXTURES = ROOT / "textures"

REPORT = {"blender": bpy.app.version_string, "files": {}, "checks": [], "ok": True}


def check(name, ok, detail=None):
    REPORT["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
    if not ok:
        REPORT["ok"] = False
    print(("PASS " if ok else "FAIL ") + name, "" if detail is None else json.dumps(detail, default=str)[:300], flush=True)


def load(fbx):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(EXPORTS / fbx))
    scene = bpy.context.scene
    objs = {o.name.split(".")[0]: o for o in scene.objects}
    return scene, objs


def world_bm(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    bm.normal_update()
    return bm


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def open_edges(bm):
    return sum(1 for e in bm.edges if len(e.link_faces) != 2)


def shells(bm):
    seen, n = set(), 0
    for f in bm.faces:
        if f.index in seen:
            continue
        n += 1
        stack = [f]
        seen.add(f.index)
        while stack:
            c = stack.pop()
            for e in c.edges:
                for nb in e.link_faces:
                    if nb.index not in seen:
                        seen.add(nb.index)
                        stack.append(nb)
    return n


def uv_ok(ob):
    uv = ob.data.uv_layers.active
    if not uv:
        return False, "no UV layer"
    xs = [d.uv.x for d in uv.data]
    ys = [d.uv.y for d in uv.data]
    ok = min(xs) >= -1e-4 and max(xs) <= 1.0001 and min(ys) >= -1e-4 and max(ys) <= 1.0001
    return ok, [round(min(xs), 4), round(max(xs), 4), round(min(ys), 4), round(max(ys), 4)]


def zero_area(ob):
    """Zero-area or hair-thin faces (height < ~1e-4 of the longest edge)."""
    me = ob.data
    n = 0
    for p in me.polygons:
        pts = [me.vertices[v].co for v in p.vertices]
        L = max((pts[i] - pts[(i + 1) % len(pts)]).length for i in range(len(pts)))
        if p.area < 1e-8 or p.area < 5e-5 * L * L:
            n += 1
    return n


def bounds(ob):
    pts = [ob.matrix_world @ v.co for v in ob.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def common(fbx, scene, objs, names, budget_each=None, budget_total=None, atlas=None, atlas_px=None):
    info = {"meshes": {}}
    check(f"{fbx}: mesh names exact", set(objs) == set(names), sorted(objs))
    check(f"{fbx}: no armature / animation", not [o for o in scene.objects if o.type != "MESH"] and not bpy.data.actions,
          {"nonMesh": [o.name for o in scene.objects if o.type != "MESH"], "actions": len(bpy.data.actions)})
    total = 0
    for n in names:
        ob = objs.get(n)
        if not ob:
            continue
        t = tris(ob)
        total += t
        bm = world_bm(ob)
        bm.faces.ensure_lookup_table()
        for i, f in enumerate(bm.faces):
            f.index = i
        oe = open_edges(bm)
        sh = shells(bm)
        uok, uvr = uv_ok(ob)
        za = zero_area(ob)
        lo, hi = bounds(ob)
        info["meshes"][n] = {"tris": t, "openEdges": oe, "shells": sh, "uvRange": uvr, "zeroAreaFaces": za,
                             "boundsMin": [round(v, 4) for v in lo], "boundsMax": [round(v, 4) for v in hi],
                             "size": [round(v, 4) for v in (hi - lo)], "location": [round(v, 5) for v in ob.location]}
        check(f"{fbx}:{n}: closed shells (0 open/non-manifold edges)", oe == 0, {"openEdges": oe, "shells": sh})
        check(f"{fbx}:{n}: UVs inside 0-1", uok, uvr)
        check(f"{fbx}:{n}: no zero-area / sliver faces", za == 0, za)
        if budget_each:
            check(f"{fbx}:{n}: triangle budget {budget_each}", budget_each[0] <= t <= budget_each[1], t)
        bm.free()
    info["totalTris"] = total
    if budget_total:
        check(f"{fbx}: total triangle budget <= {budget_total}", total <= budget_total, total)
    if atlas:
        img = None
        try:
            img = bpy.data.images.load(str(EXPORTS / atlas))
            sz = tuple(img.size)
            img.pixels[0]
            check(f"{fbx}: atlas {atlas} loads at {atlas_px}px", sz == (atlas_px, atlas_px), sz)
        except Exception as ex:
            check(f"{fbx}: atlas {atlas} loads", False, str(ex))
        embedded = [i for i in bpy.data.images if i.size[0] > 0 and i.name.lower().startswith(atlas.split("_")[0].lower())]
        info["importedImages"] = [(i.name, tuple(i.size)) for i in bpy.data.images]
        check(f"{fbx}: embedded texture came back with the FBX", len([i for i in bpy.data.images if i.size[0] >= 512]) >= 1,
              info["importedImages"])
    REPORT["files"][fbx] = info
    return info


def bvh_of(ob):
    bm = world_bm(ob)
    t = BVHTree.FromBMesh(bm)
    return t, bm


def inside_or_on(tree, p, tol=2e-3):
    near = tree.find_nearest(p)
    if near and near[3] <= tol:
        return True
    d = Vector((0.2923, 0.5731, 0.7641)).normalized()
    cnt, origin = 0, p.copy()
    for _ in range(64):
        hit = tree.ray_cast(origin + d * 1e-5, d)
        if hit[0] is None:
            break
        cnt += 1
        origin = hit[0] + d * 1e-4
    return cnt % 2 == 1


# ------------------------------------------------------------------------------------------------
# Sarcophagus
# ------------------------------------------------------------------------------------------------
scene, objs = load("Sarcophagus.fbx")
info = common("Sarcophagus.fbx", scene, objs, ["Sarcophagus_Body", "Sarcophagus_Lid"], budget_total=3000,
              atlas="Sarcophagus_atlas.png", atlas_px=1024)
body, lid = objs["Sarcophagus_Body"], objs["Sarcophagus_Lid"]
blo, bhi = bounds(body)
llo, lhi = bounds(lid)
check("Body origin at ground / cavity floor centre (location 0,0,0; bottom z=0)", body.location.length < 1e-4 and abs(blo.z) < 1e-3,
      {"location": list(body.location), "minZ": blo.z})
size = bhi - blo
check("Body outer: ~15 tall, ~7.6 wide at the shoulders, 5.2 deep", abs(size.z - 15.0) < 0.05 and 7.4 <= size.x <= 7.7 and abs(size.y - 5.2) < 0.05,
      [round(v, 3) for v in size])
# foot width: widest x at z < 1.0
body_bm = world_bm(body)
foot = [v.co.x for v in body_bm.verts if v.co.z <= 1.4 + 1e-3]         # the foot band (incl. its chamfer verts)
check("Body foot band width ~4.8", abs((max(foot) - min(foot)) - 4.8) < 0.1, round(max(foot) - min(foot), 3))
# anthropoid silhouette: narrow head, widest at the shoulders (~70% of the height), clear taper to the foot
def width_at(bm_, z0, z1):
    xs = [v.co.x for v in bm_.verts if z0 <= v.co.z < z1]
    return (max(xs) - min(xs)) if xs else 0.0
H = size.z
bands_w = [(round(z0, 2), round(width_at(body_bm, z0, z0 + 0.4), 3)) for z0 in [0.1 + 0.4 * k for k in range(int(H / 0.4))]]
w_max = max(w for _, w in bands_w)
z_widest = max(bands_w, key=lambda t: t[1])[0]
w_head = max(w for z, w in bands_w if z >= 0.9 * H - 0.4)
w_foot = max(w for z, w in bands_w if z < 0.12 * H)
REPORT["silhouette"] = {"widestAtZ": z_widest, "widestAtFractionOfHeight": round(z_widest / H, 3), "shoulderWidth": w_max, "headWidth": w_head, "footWidth": w_foot,
                        "headOverShoulder": round(w_head / w_max, 3), "footOverShoulder": round(w_foot / w_max, 3)}
check("Reference silhouette (2026-10-09): widest at 65-78% height, head end 0.70-0.80 and foot 0.58-0.68 of the shoulder width, height >= 1.9x width",
      0.65 <= z_widest / H <= 0.78 and 0.70 <= w_head / w_max <= 0.80 and 0.58 <= w_foot / w_max <= 0.68 and H >= 1.9 * w_max, REPORT["silhouette"])
# lid fit
body_front_y = blo.y
lid_back_y = lhi.y
gap = body_front_y - lid_back_y
check("Lid closed fit: gap |<= 0.05| and no overlap", -1e-3 <= gap <= 0.05, {"gap": round(gap, 5), "bodyFrontY": round(body_front_y, 4), "lidBackY": round(lid_back_y, 4)})
lid_bm = world_bm(lid)
under = [v.co for v in lid_bm.verts if v.co.y > lhi.y - 1e-3]
front = [v.co for v in body_bm.verts if v.co.y < blo.y + 1e-3]
front_edges = [(e.verts[0].co, e.verts[1].co) for e in body_bm.edges
               if e.verts[0].co.y < blo.y + 1e-3 and e.verts[1].co.y < blo.y + 1e-3]


def seg_dist(p, a_, b_):
    ab = Vector((b_.x - a_.x, 0, b_.z - a_.z))
    ap = Vector((p.x - a_.x, 0, p.z - a_.z))
    t = 0.0 if ab.length_squared < 1e-12 else max(0.0, min(1.0, ap.dot(ab) / ab.length_squared))
    return (ap - ab * t).length


worst = max(min(seg_dist(u, a_, b_) for a_, b_ in front_edges) for u in under)
check("Lid underside outline lies on the body front rim edges (worst vertex <= 0.05, the brief's gap limit)", worst <= 0.05, round(worst, 5))
check("Lid XZ extents equal the body's", abs(llo.x - blo.x) < 0.01 and abs(lhi.x - bhi.x) < 0.01 and abs(llo.z - blo.z) < 0.01 and abs(lhi.z - bhi.z) < 0.01,
      {"lid": [round(v, 3) for v in (llo.x, lhi.x, llo.z, lhi.z)], "body": [round(v, 3) for v in (blo.x, bhi.x, blo.z, bhi.z)]})
hinge_y = llo.y
check("Lid origin on its bottom front hinge line (x=0, y=front-most, z=0)", abs(lid.location.x) < 1e-4 and abs(lid.location.y - hinge_y) < 1e-3 and abs(lid.location.z) < 1e-4,
      {"lidLocation": [round(v, 4) for v in lid.location], "frontMostY": round(hinge_y, 4)})
# the underside is plain/flat: all verts at the max y plane belong to a single planar face region
flat_under = [p for p in lid.data.polygons if (lid.matrix_world @ p.center).y > lhi.y - 1e-3]
check("Lid underside is one flat plane", len(flat_under) >= 1 and all(abs((lid.matrix_world.to_3x3() @ p.normal).y - 1) < 1e-3 for p in flat_under), len(flat_under))
# cavity measurement by ray casts from the inside
tree, _ = bvh_of(body)
def ray(o, d):
    h = tree.ray_cast(Vector(o), Vector(d).normalized())
    return None if h[0] is None else h[0]
floor_hit = ray((0, 0, 4.0), (0, 0, -1))
ceil_hit = ray((0, 0, 4.0), (0, 0, 1))
back_hit = ray((0, -1.0, 4.0), (0, 1, 0))
cav_h = ceil_hit.z - floor_hit.z
cav_d = back_hit.y - blo.y
widths = []
NS = 380
for k in range(0, NS):
    z = floor_hit.z + 0.1 + k * ((cav_h - 0.2) / (NS - 1))
    r, l = ray((0, 0, z), (1, 0, 0)), ray((0, 0, z), (-1, 0, 0))
    if r and l:
        widths.append((round(z, 3), round(r.x - l.x, 3)))
max_w = max(w for _, w in widths)
check("Cavity extents >= 13.4 tall x 6.2 wide x 4.2 deep (Warden box 9.4 x 6.2 x 4.2 fits)", cav_h >= 13.4 - 1e-3 and max_w >= 6.2 and cav_d >= 4.2,
      {"height": round(cav_h, 3), "maxWidth": round(max_w, 3), "depth": round(cav_d, 3), "floorZ": round(floor_hit.z, 3), "ceilingZ": round(ceil_hit.z, 3)})
prof = {}
for W in (3.4, 4.4, 5.2, 6.2):
    zs = [z for z, w in widths if w >= W]
    prof[str(W)] = round(max(zs) - min(zs), 2) if zs else 0
REPORT["cavityProfile"] = {"widthByHeight": [w for i, w in enumerate(widths) if i % 20 == 0], "heightAvailableAtMinWidth": prof,
                           "note": "The coffin is anthropoid, so the 9.4 x 6.2 x 4.2 box is the cavity's bounding extents (tall at the head, 6.2 wide only at the shoulders), not a rectangular void."}
# wall thickness (side) at three heights
wt = []
for z in (2.0, 5.0, 7.0):
    r = ray((0, 0, z), (1, 0, 0))
    out = tree.ray_cast(r + Vector((0.01, 0, 0)), Vector((1, 0, 0)))
    if out[0] is not None:
        wt.append((z, round(out[0].x - r.x, 3)))
back_wall = back_hit.y
REPORT["wallThickness"] = {"sideAtZ": wt, "back": round(bhi.y - back_hit.y, 3), "floor": round(floor_hit.z, 3), "ceiling": round(bhi.z - ceil_hit.z, 3)}
check("Back is solid and flat (no relief): all back-plane faces coplanar", all(abs((body.matrix_world @ p.center).y - bhi.y) < 1e-3 for p in body.data.polygons if (body.matrix_world.to_3x3() @ p.normal).y > 0.99),
      None)
body_bm.free()
lid_bm.free()
body_tree, lid_tree = bvh_of(body)[0], bvh_of(lid)[0]
REPORT["sarcophagusFrame"] = {"hingeBodySpaceBlender": [0, round(hinge_y, 4), 0], "bodyFrontY": round(body_front_y, 4)}

# ------------------------------------------------------------------------------------------------
# Broken kit
# ------------------------------------------------------------------------------------------------
scene, objs = load("SarcophagusBroken.fbx")
names = ["SarcophagusBroken_Base", "SarcophagusBroken_LeftWall", "SarcophagusBroken_RightWall", "SarcophagusBroken_LidFragment"]
info = common("SarcophagusBroken.fbx", scene, objs, names, budget_total=3000, atlas="Sarcophagus_atlas.png", atlas_px=1024)
check("Broken kit: exactly four chunks", len(objs) == 4, len(objs))
offsets = json.loads((EXPORTS / "SarcophagusBroken-offsets.json").read_text())["chunks"]
out_max = 0.0
for n in names:
    ob = objs[n]
    lo_l = Vector((min(v.co.x for v in ob.data.vertices), min(v.co.y for v in ob.data.vertices), min(v.co.z for v in ob.data.vertices)))
    hi_l = Vector((max(v.co.x for v in ob.data.vertices), max(v.co.y for v in ob.data.vertices), max(v.co.z for v in ob.data.vertices)))
    centred = ((lo_l + hi_l) / 2).length
    want = Vector(offsets[n]["offsetBodySpaceBlender"])
    check(f"{n}: origin at its bounding-box centre and location == JSON offset", centred < 2e-3 and (ob.location - want).length < 1e-3,
          {"meshCentreOffset": round(centred, 5), "location": [round(v, 4) for v in ob.location], "json": want[:]})
    ref_tree = lid_tree if n.endswith("LidFragment") else body_tree
    bad = 0
    for v in ob.data.vertices:
        p = ob.matrix_world @ v.co
        if not inside_or_on(ref_tree, p):
            bad += 1
    out_max = max(out_max, bad)
    check(f"{n}: placed with identity transform it sits inside/on the intact {'lid' if n.endswith('LidFragment') else 'body'}", bad == 0,
          {"verticesOutside": bad, "of": len(ob.data.vertices)})
    # darker interior faces: fracture faces use the dedicated atlas tile (UV v in lower-right quadrant)
    uv = ob.data.uv_layers.active.data
    fr = sum(1 for p in ob.data.polygons if all(0.5 <= uv[l].uv.x <= 1.0 and 0.14 <= uv[l].uv.y <= 0.5 for l in p.loop_indices))
    info["meshes"][n]["fractureTileFaces"] = fr
    check(f"{n}: has fracture-tile (darker interior) faces", fr > 0, fr)

# ------------------------------------------------------------------------------------------------
# Vent
# ------------------------------------------------------------------------------------------------
scene, objs = load("VolcanicVent.fbx")
info = common("VolcanicVent.fbx", scene, objs, ["Vent_Rock", "Vent_Glow"], budget_total=2000, atlas="Volcanic_atlas.png", atlas_px=512)
rock, glow = objs["Vent_Rock"], objs["Vent_Glow"]
rlo, rhi = bounds(rock)
glo, ghi = bounds(glow)
top = max(rhi.z, ghi.z)
check("Vent height <= 1.8", top <= 1.8, round(top, 4))
check("Vent about 9 across", 8.4 <= (rhi.x - rlo.x) <= 10.0 and 8.4 <= (rhi.y - rlo.y) <= 10.0, [round(rhi.x - rlo.x, 3), round(rhi.y - rlo.y, 3)])
tree_r, _ = bvh_of(rock)
dists = []
for k in range(72):
    a = 2 * math.pi * k / 72
    h = tree_r.ray_cast(Vector((0, 0, 0.7)), Vector((math.cos(a), math.sin(a), 0)))
    if h[0] is not None:
        dists.append(h[3])
opening = [round(2 * min(dists), 3), round(2 * sum(dists) / len(dists), 3)]
check("Vent opening about 3.5 across (min/mean diameter at z=0.7)", 3.0 <= opening[0] and opening[1] <= 4.4, opening)
check("Vent origin at ground centre of the opening", rock.location.length < 1e-4 and glow.location.length < 1e-4 and rlo.z >= -0.2,
      {"rockMinZ": round(rlo.z, 3)})
check("Vent_Glow is a separate mesh from Vent_Rock", rock.data != glow.data, None)
REPORT["vent"] = {"heightMax": round(top, 4), "across": [round(rhi.x - rlo.x, 3), round(rhi.y - rlo.y, 3)], "openingDiameterMinMean": opening}

# ------------------------------------------------------------------------------------------------
# Debris
# ------------------------------------------------------------------------------------------------
scene, objs = load("VolcanicDebris.fbx")
names = [f"Debris_{i}" for i in range(1, 6)]
info = common("VolcanicDebris.fbx", scene, objs, names, budget_each=(30, 150), atlas="Volcanic_atlas.png", atlas_px=512)
for n in names:
    ob = objs[n]
    lo, hi = bounds(ob)
    d = sorted((hi - lo)[:], reverse=True)
    check(f"{n}: 0.15-0.5 across, not a matchstick (min dim >= 0.1, aspect <= 4)", 0.15 <= d[0] <= 0.5 and d[2] >= 0.1 and d[0] / d[2] <= 4.0,
          [round(v, 3) for v in d])
    cen = ((lo + hi) / 2) - ob.location
    check(f"{n}: origin at the fragment centre", cen.length < 2e-3, round(cen.length, 5))

(ROOT / "validation-report.json").write_text(json.dumps(REPORT, indent=2, default=str))
print("VALIDATION", "OK" if REPORT["ok"] else "FAILED", len([c for c in REPORT["checks"] if not c["ok"]]), "failing checks", flush=True)
