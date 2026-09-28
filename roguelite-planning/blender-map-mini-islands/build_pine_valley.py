"""Pine Valley mini island for the map-select background.

blender --background --factory-startup --python build_pine_valley.py

A small floating island that condenses the Pine Valley arena: bright meadow,
grey grass-capped cliff wall around the back, the project's evergreen master
trees, two canvas campsites with fire rings, crates, barrels and a fence, the
project's fallen-log master, stumps, low boulders and bushes. Underneath is a
faceted grey rock body with a soil band and hanging spires.
"""
import sys
import math
import random
import json
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector, Matrix

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import island_lib as L  # noqa: E402

MAP = "PineValley"
SEED = 11
RADIUS = 30.0
DEPTH = 26.0
KITS = HERE.parent
EVERGREEN_GLB = KITS / "blender-master-evergreen" / "Evergreen_Master.glb"
LOG_GLB = KITS / "blender-master-log" / "Log_Master.glb"

OUT_TEX = HERE / "textures"
OUT_PREV = HERE / "previews"
OUT_FBX = HERE / "exports" / "fbx"
OUT_GLB = HERE / "exports" / "glb"
for d in (OUT_TEX, OUT_PREV, OUT_FBX, OUT_GLB):
    d.mkdir(parents=True, exist_ok=True)

rng = random.Random(SEED)
scene = L.reset_scene()
PROPS = L.collection(f"{MAP}_Procedural")
FOLIAGE = L.collection(f"{MAP}_Masters")

# ---------------------------------------------------------------------------
# palette (sampled by eye from the Pine Valley arena, pushed slightly brighter
# because the game runs +0.3 saturation colour correction)
# ---------------------------------------------------------------------------
GRASS = L.paint_mat("PV_Grass", [(0.2, "#3f7f2c"), (0.42, "#5a9c38"), (0.62, "#74b546"), (0.85, "#90c957")],
                    blob=8.0, jitter=0.5, facing=0.3)
SOIL = L.paint_mat("PV_Soil", [(0.0, "#4a3325"), (0.5, "#6b4a31"), (1.0, "#86613f")], blob=3.0, jitter=0.3)
ROCK = L.paint_mat("PV_Rock", [(0.08, "#4a5364"), (0.36, "#6f7884"), (0.62, "#959a9f"), (0.9, "#b5ae9c")],
                   blob=5.0, jitter=0.32, facing=0.75)
DRIP = L.paint_mat("PV_GrassDrip", [(0.0, "#4a8a32"), (1.0, "#6aad40")], blob=3.0, jitter=0.2, facing=0.3)
WOOD = L.paint_mat("PV_Wood", [(0.0, "#5a3a24"), (0.5, "#7d5433"), (1.0, "#9a6d45")], blob=1.4, jitter=0.35, facing=0.4)
CUT = L.paint_mat("PV_CutWood", [(0.0, "#b58a5a"), (1.0, "#d2ab76")], blob=0.6, jitter=0.3, facing=0.2)
CANVAS = L.paint_mat("PV_Canvas", [(0.0, "#b9ad92"), (0.5, "#ddd3bb"), (1.0, "#efe8d6")], blob=2.0, jitter=0.25, facing=0.6)
METAL = L.paint_mat("PV_Band", [(0.0, "#3b3d42"), (1.0, "#5d6068")], blob=1.0, jitter=0.2)
FIRE = L.paint_mat("PV_Fire", [(0.0, "#ff7a1a"), (1.0, "#ffc445")], blob=0.5, jitter=0.3, facing=0.6,
                   emission="#ff9a2e", emission_strength=6.0)
BUSH = L.paint_mat("PV_Bush", [(0.1, "#2f6a2c"), (0.6, "#43893a"), (1.0, "#5ea447")], blob=2.0, jitter=0.3, facing=0.7)
DIRT = L.paint_mat("PV_Dirt", [(0.0, "#8a6a45"), (0.6, "#a8845a"), (1.0, "#bb9868")], blob=2.5, jitter=0.4, facing=0.1)

# material slot order shared by every prop object
MATS = [ROCK, GRASS, WOOD, CUT, CANVAS, METAL, FIRE, BUSH, DIRT]
I_ROCK, I_GRASS, I_WOOD, I_CUT, I_CANVAS, I_METAL, I_FIRE, I_BUSH, I_DIRT = range(len(MATS))

# ---------------------------------------------------------------------------
# island body
# ---------------------------------------------------------------------------
island, R = L.island_body(f"{MAP}_Body", RADIUS, DEPTH, SEED, GRASS, SOIL, ROCK, col=PROPS,
                          drip_mat=DRIP, drips=22, spires=7, top_bumps=0.3)
bpy.context.view_layer.update()


def polar(theta_deg, frac):
    th = math.radians(theta_deg)
    r = R(th) * frac
    return math.cos(th) * r, math.sin(th) * r


def ground(x, y):
    return L.top_height(island, x, y)


def facing_center(x, y):
    return math.atan2(-y, -x)


made = []

# ---------------------------------------------------------------------------
# back cliff wall: stepped, grass-capped blocks on the back arc (+Y)
# ---------------------------------------------------------------------------
cliff_tops = []
for k, th in enumerate(range(28, 158, 13)):
    mid = 1 - abs(th - 93) / 70         # tallest at the back centre
    h = 6.5 + 5.0 * mid + rng.uniform(-0.8, 0.8)
    w = rng.uniform(7.0, 9.0)
    d = rng.uniform(5.5, 7.0)
    x, y = polar(th + rng.uniform(-3, 3), 0.84)
    z = ground(x, y) - 0.6
    rot = math.radians(th + 90 + rng.uniform(-10, 10))
    b = L.cliff_block(f"{MAP}_Cliff_{k:02d}", w, d, h, seed=SEED + k, mats=MATS, cap_index=I_GRASS,
                      loc=(x, y, z), rot_z=rot, col=PROPS)
    made.append(b)
    cliff_tops.append((th, x, y, z + h, b))
    # lower step in front of every other block
    if k % 2 == 0:
        x2, y2 = polar(th + rng.uniform(-5, 5), 0.70)
        z2 = ground(x2, y2) - 0.4
        s = L.cliff_block(f"{MAP}_CliffStep_{k:02d}", w * 0.7, d * 0.7, h * 0.42, seed=SEED + 40 + k, mats=MATS,
                          cap_index=I_GRASS, loc=(x2, y2, z2), rot_z=rot + 0.3, col=PROPS)
        made.append(s)

# side outcrops
for k, (th, fr, size) in enumerate([(200, 0.86, (6, 5, 4.5)), (338, 0.86, (6.5, 5, 5)), (182, 0.9, (4, 4, 3))]):
    x, y = polar(th, fr)
    made.append(L.cliff_block(f"{MAP}_Outcrop_{k}", *size, seed=SEED + 70 + k, mats=MATS, cap_index=I_GRASS,
                              loc=(x, y, ground(x, y) - 0.5), rot_z=math.radians(th + 90), col=PROPS))

# low boulders: interior sprinkles + chunky front-rim rocks
for k, (th, fr, s) in enumerate([(250, 0.45, 2.0), (300, 0.30, 1.6), (40, 0.36, 1.8), (135, 0.38, 1.5),
                                  (210, 0.25, 1.4), (15, 0.12, 1.2),
                                  (238, 0.93, 5.0), (256, 0.95, 3.4), (292, 0.94, 4.6), (315, 0.9, 3.0)]):
    x, y = polar(th, fr)
    made.append(L.rock(f"{MAP}_Boulder_{k:02d}", (s * 1.25, s, s * 0.7), seed=SEED + 100 + k, mats=MATS,
                       cap_index=I_GRASS if s > 3 else None, loc=(x, y, ground(x, y)),
                       rot_z=rng.uniform(0, 6.28), col=PROPS))

# ---------------------------------------------------------------------------
# campsite pieces
# ---------------------------------------------------------------------------


def a_frame_tent(name, loc, rot_z, length=6.5, width=5.2, height=4.0):
    bm = bmesh.new()
    hw = width / 2
    t = 0.14
    # two canvas slopes as thin slabs
    slope_len = math.hypot(hw, height)
    ang = math.atan2(height, hw)
    for side in (-1, 1):
        # slab's local +Y runs from the ridge down to the ground on this side
        L.box_bm(bm, (length, slope_len + 0.3, t), loc=(0, side * hw / 2, height / 2),
                 rot=Matrix.Rotation(-side * ang, 4, "X"), mat_index=I_CANVAS)
    # closed back triangle
    tri = bmesh.new()
    prof = [(-hw, 0), (hw, 0), (0, height)]
    f = tri.faces.new([tri.verts.new((-length / 2 + 0.05, y, z)) for (y, z) in prof])
    ext = bmesh.ops.extrude_face_region(tri, geom=[f])
    bmesh.ops.translate(tri, vec=(0.12, 0, 0), verts=[v for v in ext["geom"] if isinstance(v, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(tri, faces=tri.faces)
    L.merge_bm(bm, tri, I_CANVAS)
    # A-frame poles at both ends + ridge pole
    for ex in (-length / 2 - 0.2, length / 2 + 0.2):
        for side in (-1, 1):
            p0 = Vector((ex, side * (hw + 0.2), 0))
            p1 = Vector((ex, -side * 0.35, height + 0.55))
            dvec = p1 - p0
            m = Matrix.Translation(p0) @ dvec.to_track_quat("Z", "Y").to_matrix().to_4x4()
            L.cyl_bm(bm, 0.14, 0.11, dvec.length, segs=6, matrix=m, mat_index=I_WOOD)
    m = Matrix.Translation((-length / 2 - 0.6, 0, height + 0.08)) @ Matrix.Rotation(math.pi / 2, 4, "Y")
    L.cyl_bm(bm, 0.13, 0.13, length + 1.2, segs=6, matrix=m, mat_index=I_WOOD)
    L.transform_bm(bm, loc=loc, rot_z=rot_z)
    return L.bm_to_obj(name, bm, MATS, PROPS)


def lean_to(name, loc, rot_z, length=6.0, depth=4.2, height=3.6):
    """Single sloped tarp on two front poles, back edge pegged to the ground."""
    bm = bmesh.new()
    ang = math.atan2(height, depth)
    slen = math.hypot(height, depth)
    L.box_bm(bm, (length, slen, 0.14), loc=(0, 0, height / 2), rot=L.trs(rot=(ang, 0, 0)), mat_index=I_CANVAS)
    for ex in (-length / 2 + 0.2, length / 2 - 0.2):
        L.cyl_bm(bm, 0.14, 0.12, height + 0.5, segs=6, matrix=Matrix.Translation((ex, -depth / 2, 0)),
                 mat_index=I_WOOD)
    m = Matrix.Translation((-length / 2 - 0.3, -depth / 2, height)) @ Matrix.Rotation(math.pi / 2, 4, "Y")
    L.cyl_bm(bm, 0.12, 0.12, length + 0.6, segs=6, matrix=m, mat_index=I_WOOD)
    L.transform_bm(bm, loc=loc, rot_z=rot_z)
    return L.bm_to_obj(name, bm, MATS, PROPS)


def campfire(name, loc, seed):
    r2 = random.Random(seed)
    bm = bmesh.new()
    for i in range(9):
        a = 2 * math.pi * i / 9
        st = bmesh.new()
        bmesh.ops.create_icosphere(st, subdivisions=1, radius=0.5)
        L.jitter_bm(st, 0.12, seed + i, freq=2.0)
        L.transform_bm(st, loc=(math.cos(a) * 1.35, math.sin(a) * 1.35, 0.15), rot_z=r2.uniform(0, 6),
                       scale=(0.75, 0.6, 0.5))
        L.merge_bm(bm, st, I_ROCK)
    for i in range(4):
        a = 2 * math.pi * i / 4 + 0.4
        p0 = Vector((math.cos(a) * 0.9, math.sin(a) * 0.9, 0.05))
        p1 = Vector((0, 0, 1.0))
        dvec = p1 - p0
        m = Matrix.Translation(p0) @ dvec.to_track_quat("Z", "Y").to_matrix().to_4x4()
        L.cyl_bm(bm, 0.16, 0.12, dvec.length, segs=5, matrix=m, mat_index=I_WOOD)
    L.cyl_bm(bm, 0.75, 0.0, 1.9, segs=6, matrix=Matrix.Translation((0, 0, 0.1)), mat_index=I_FIRE, cap_tris=True,
             jitter=0.12, seed=seed)
    L.cyl_bm(bm, 0.45, 0.0, 1.3, segs=5, matrix=L.trs((0.35, 0.2, 0.1), (0.12, -0.15, 0)), mat_index=I_FIRE,
             cap_tris=True)
    L.transform_bm(bm, loc=loc)
    return L.bm_to_obj(name, bm, MATS, PROPS)


def crate(bm, loc, size, rot_z):
    L.box_bm(bm, (size, size, size), loc=(loc[0], loc[1], loc[2] + size / 2), rot=Matrix.Rotation(rot_z, 4, "Z"),
             chamfer=size * 0.08, mat_index=I_WOOD)
    # darker slats on two faces
    for s in (-1, 1):
        L.box_bm(bm, (size * 1.02, size * 0.14, size * 1.02),
                 loc=(loc[0], loc[1], loc[2] + size / 2),
                 rot=Matrix.Rotation(rot_z, 4, "Z") @ Matrix.Rotation(s * 0.785, 4, "X"),
                 mat_index=I_CUT)


def barrel(bm, loc, h=1.9, r=0.8):
    segs = 10
    L.cyl_bm(bm, r * 0.86, r, h * 0.5, segs=segs, matrix=Matrix.Translation(loc), mat_index=I_WOOD)
    L.cyl_bm(bm, r, r * 0.86, h * 0.5, segs=segs, matrix=Matrix.Translation((loc[0], loc[1], loc[2] + h * 0.5)),
             mat_index=I_WOOD)
    for z in (0.18, 0.82):
        L.cyl_bm(bm, r * (0.93 if z < 0.5 else 0.93) + 0.05, r * 0.95 + 0.05, h * 0.08, segs=segs,
                 matrix=Matrix.Translation((loc[0], loc[1], loc[2] + h * z - h * 0.04)), mat_index=I_METAL)
    L.cyl_bm(bm, r * 0.84, r * 0.84, 0.06, segs=segs, matrix=Matrix.Translation((loc[0], loc[1], loc[2] + h)),
             mat_index=I_CUT)


def fence(bm, p0, p1, posts=3):
    p0, p1 = Vector(p0), Vector(p1)
    for i in range(posts):
        p = p0.lerp(p1, i / (posts - 1))
        L.cyl_bm(bm, 0.2, 0.17, 2.3, segs=6, matrix=Matrix.Translation(p), mat_index=I_WOOD, jitter=0.03, seed=i)
    d = p1 - p0
    rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    for hz in (0.85, 1.7):
        L.cyl_bm(bm, 0.12, 0.12, d.length + 0.5, segs=5,
                 matrix=Matrix.Translation(p0 - d.normalized() * 0.25 + Vector((0, 0, hz))) @ rot, mat_index=I_WOOD)


def stump(name, loc, r, h, seed):
    bm = bmesh.new()
    L.cyl_bm(bm, r * 1.25, r, h, segs=8, matrix=Matrix.Translation((0, 0, -0.2)), mat_index=I_WOOD,
             jitter=0.06, seed=seed)
    bm.normal_update()
    for f in bm.faces:
        if f.normal.z > 0.9:
            f.material_index = I_CUT
    L.transform_bm(bm, loc=loc, rot_z=seed)
    return L.bm_to_obj(name, bm, MATS, PROPS)


def bush(name, loc, s, seed):
    r2 = random.Random(seed)
    bm = bmesh.new()
    for i in range(3):
        b = bmesh.new()
        bmesh.ops.create_icosphere(b, subdivisions=1, radius=1.0)
        L.jitter_bm(b, 0.15, seed + i, freq=1.5)
        a = i * 2.1 + r2.uniform(0, 1)
        L.transform_bm(b, loc=(math.cos(a) * 0.8 * s, math.sin(a) * 0.8 * s, 0.45 * s),
                       scale=(s * r2.uniform(0.8, 1.1), s * r2.uniform(0.8, 1.1), s * 0.75))
        L.merge_bm(bm, b, I_BUSH)
    L.transform_bm(bm, loc=loc)
    return L.bm_to_obj(name, bm, MATS, PROPS)


def dirt_patch(name, loc, rx, ry, seed, rot_z=0.0):
    bm = bmesh.new()
    segs = 14
    c = bm.verts.new((0, 0, 0.07))
    ring = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        k = 1 + 0.18 * math.sin(a * 3 + seed) + 0.1 * math.cos(a * 5 + seed * 2)
        ring.append(bm.verts.new((math.cos(a) * rx * k, math.sin(a) * ry * k, 0.07)))
    for i in range(segs):
        bm.faces.new((c, ring[i], ring[(i + 1) % segs])).material_index = I_DIRT
    L.transform_bm(bm, loc=loc, rot_z=rot_z)
    obj = L.bm_to_obj(name, bm, MATS, PROPS)
    # drape each vertex onto the meadow
    for v in obj.data.vertices:
        v.co.z = ground(v.co.x, v.co.y) + 0.07
    return obj


def tufts(name, pts, seed):
    r2 = random.Random(seed)
    bm = bmesh.new()
    for (x, y) in pts:
        z = ground(x, y)
        for i in range(3):
            a = r2.uniform(0, 6.28)
            m = L.trs((x + math.cos(a) * 0.25, y + math.sin(a) * 0.25, z - 0.05),
                      (r2.uniform(-0.35, 0.35), r2.uniform(-0.35, 0.35), a))
            L.cyl_bm(bm, 0.22, 0.0, r2.uniform(0.8, 1.3), segs=3, matrix=m, mat_index=I_BUSH, cap_tris=True)
    return L.bm_to_obj(name, bm, MATS, PROPS)


# West campsite (left of camera): A-frame tent, fire, crates, barrel, fence
cx, cy = polar(168, 0.60)
cz = ground(cx, cy)
face = facing_center(cx, cy)
made.append(dirt_patch(f"{MAP}_CampDirt_W", (cx + 1.5, cy - 1.0, 0), 6.5, 4.5, 3, rot_z=face))
made.append(a_frame_tent(f"{MAP}_Tent_W", (cx - 1.0, cy + 1.0, cz), face + math.pi / 2 + 0.25))
fx, fy = cx + math.cos(face) * 5.0, cy + math.sin(face) * 5.0
made.append(campfire(f"{MAP}_Campfire_W", (fx, fy, ground(fx, fy)), 5))
bm = bmesh.new()
for (dx, dy, dz, s, r) in [(3.2, 3.4, 0, 1.7, 0.2), (4.6, 3.0, 0, 1.4, 0.6), (3.6, 3.2, 1.7, 1.2, 0.9)]:
    px, py = cx + dx * math.cos(face) - dy * math.sin(face), cy + dx * math.sin(face) + dy * math.cos(face)
    crate(bm, (px, py, ground(px, py) + dz), s, r)
bx, by = cx + 1.0 * math.cos(face) + 4.2 * math.sin(face), cy + 1.0 * math.sin(face) - 4.2 * math.cos(face)
barrel(bm, (bx, by, ground(bx, by)))
f0 = Vector(polar(150, 0.80)).to_3d()
f1 = Vector(polar(176, 0.86)).to_3d()
f0.z, f1.z = ground(f0.x, f0.y), ground(f1.x, f1.y)
fence(bm, f0, f1, posts=4)
made.append(L.bm_to_obj(f"{MAP}_CampProps_W", bm, MATS, PROPS))

# East campsite: lean-to tarp, fire, crate, barrels
ex_, ey_ = polar(8, 0.62)
ez = ground(ex_, ey_)
face_e = facing_center(ex_, ey_)
made.append(dirt_patch(f"{MAP}_CampDirt_E", (ex_ - 0.5, ey_, 0), 5.5, 4.2, 7, rot_z=face_e))
made.append(lean_to(f"{MAP}_LeanTo_E", (ex_ + 0.8, ey_ + 0.3, ez), face_e - math.pi / 2 + math.pi))
fx, fy = ex_ + math.cos(face_e) * 4.2, ey_ + math.sin(face_e) * 4.2
made.append(campfire(f"{MAP}_Campfire_E", (fx, fy, ground(fx, fy)), 9))
bm = bmesh.new()
px, py = ex_ - 2.5 * math.sin(face_e) + 1.0 * math.cos(face_e), ey_ + 2.5 * math.cos(face_e) + 1.0 * math.sin(face_e)
crate(bm, (px, py, ground(px, py)), 1.6, 0.4)
for k, (dx, dy) in enumerate([(-0.5, -3.6), (0.9, -4.2)]):
    px, py = ex_ + dx * math.cos(face_e) - dy * math.sin(face_e), ey_ + dx * math.sin(face_e) + dy * math.cos(face_e)
    barrel(bm, (px, py, ground(px, py)), h=1.7 + 0.2 * k, r=0.72)
made.append(L.bm_to_obj(f"{MAP}_CampProps_E", bm, MATS, PROPS))

# stumps, bushes, tufts
for k, (th, fr, r, h) in enumerate([(222, 0.72, 1.0, 1.1), (322, 0.66, 0.9, 0.9), (120, 0.58, 1.1, 1.2),
                                    (58, 0.60, 0.8, 0.8)]):
    x, y = polar(th, fr)
    made.append(stump(f"{MAP}_Stump_{k}", (x, y, ground(x, y)), r, h, SEED + k))
for k, (th, fr, s) in enumerate([(190, 0.80, 1.4), (205, 0.9, 1.0), (330, 0.78, 1.3), (350, 0.84, 1.1),
                                 (268, 0.9, 1.2), (160, 0.9, 1.1), (30, 0.9, 1.2)]):
    x, y = polar(th, fr)
    made.append(bush(f"{MAP}_Bush_{k}", (x, y, ground(x, y) - 0.2), s, SEED + 200 + k))
tuft_pts = [polar(rng.uniform(0, 360), rng.uniform(0.15, 0.8)) for _ in range(22)]
made.append(tufts(f"{MAP}_Tufts", tuft_pts, SEED + 300))

# ---------------------------------------------------------------------------
# trees + logs (project masters, linked duplicates)
# ---------------------------------------------------------------------------
tree = L.import_master(EVERGREEN_GLB, "Evergreen_Master")
log = L.import_master(LOG_GLB, "Log_Master")
trees = []
# on top of the back cliff wall
for k, (th, x, y, top, blk) in enumerate(cliff_tops):
    if k % 2 == 1 or k in (0,):
        continue
    tz = L.top_height(blk, x, y)
    trees.append(L.place_instance(tree, f"{MAP}_Tree_Cliff_{k}", (x, y, tz - 0.3), rng.uniform(0, 6.28),
                                  rng.uniform(0.72, 0.9), FOLIAGE))
# behind/between cliffs on the rim, and down the sides
for k, (th, fr, s) in enumerate([(40, 0.97, 0.95), (112, 0.97, 1.0), (145, 0.95, 0.9), (70, 0.99, 0.85),
                                 (190, 0.90, 0.85), (212, 0.86, 0.7), (350, 0.9, 0.8), (325, 0.9, 0.7),
                                 (18, 0.86, 0.75), (236, 0.80, 0.55), (302, 0.82, 0.6)]):
    x, y = polar(th, fr)
    trees.append(L.place_instance(tree, f"{MAP}_Tree_{k:02d}", (x, y, ground(x, y) - 0.3), rng.uniform(0, 6.28),
                                  s, FOLIAGE))
logs = []
for k, (th, fr, yaw, s) in enumerate([(205, 0.42, 20, 0.62), (318, 0.40, -35, 0.55), (100, 0.44, 75, 0.5)]):
    x, y = polar(th, fr)
    logs.append(L.place_instance(log, f"{MAP}_Log_{k}", (x, y, ground(x, y) - 0.15), math.radians(yaw), s, FOLIAGE))

# ---------------------------------------------------------------------------
# join + bake the procedural parts into one atlas mesh
# ---------------------------------------------------------------------------
# keep a procedural copy in the .blend for editing
island_mesh = L.join(f"{MAP}_Island", [island] + made, PROPS)
bpy.ops.object.select_all(action="DESELECT")
island_mesh.select_set(True)
bpy.context.view_layer.objects.active = island_mesh
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
L.bake_atlas(island_mesh, OUT_TEX / f"{MAP.lower()}-island-atlas.png", size=2048)
print("BAKED", island_mesh.name, flush=True)

# ---------------------------------------------------------------------------
# previews
# ---------------------------------------------------------------------------
L.setup_preview()
hero = L.camera("Cam_Hero", (0, -118, 34), (0, 0, -7), lens=35)
L.render(hero, OUT_PREV / f"{MAP.lower()}-hero.png")
close = L.camera("Cam_Close", (-8, -58, 40), (0, 4, 1), lens=35)
L.render(close, OUT_PREV / f"{MAP.lower()}-closeup.png")
side = L.camera("Cam_Side", (112, -52, 8), (0, 0, -8), lens=35)
L.render(side, OUT_PREV / f"{MAP.lower()}-side.png")

# ---------------------------------------------------------------------------
# export + report
# ---------------------------------------------------------------------------
tree.hide_viewport = False
log.hide_viewport = False
export_objs = [island_mesh] + trees + logs
L.export(export_objs, OUT_FBX / f"{MAP.lower()}-mini-island.fbx", OUT_GLB / f"{MAP.lower()}-mini-island.glb")
tree.hide_viewport = True
log.hide_viewport = True

bb = [island_mesh.matrix_world @ Vector(c) for c in island_mesh.bound_box]
report = {
    "map": MAP,
    "island_mesh": {"name": island_mesh.name, "triangles": L.tri_count(island_mesh),
                    "vertices": len(island_mesh.data.vertices),
                    "extent_studs": [round(max(v[i] for v in bb) - min(v[i] for v in bb), 2) for i in range(3)],
                    "atlas": f"textures/{MAP.lower()}-island-atlas.png"},
    "instances": {"Evergreen_Master": len(trees), "Log_Master": len(logs)},
    "instance_triangles": {"Evergreen_Master": L.tri_count(tree), "Log_Master": L.tri_count(log)},
}
report["total_triangles"] = (report["island_mesh"]["triangles"]
                             + len(trees) * report["instance_triangles"]["Evergreen_Master"]
                             + len(logs) * report["instance_triangles"]["Log_Master"])
(HERE / f"{MAP.lower()}-report.json").write_text(json.dumps(report, indent=2))

for im in bpy.data.images:
    if im.source in {"FILE", "GENERATED"} and im.has_data:
        try:
            im.pack()
        except RuntimeError:
            pass
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(HERE / f"{MAP.lower()}-mini-island.blend"))
print("ISLAND_READY", json.dumps(report), flush=True)
