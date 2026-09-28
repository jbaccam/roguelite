"""Frozen Pass mini island for the map-select background.

blender --background --factory-startup --python build_frozen.py

A small floating island that condenses the Frozen Pass arena: a soft blue-white
snow floor with pale cracked ice patches, a back arc of grey cliffs capped with
thick overhanging snow slabs and a frozen ice fall in a notch, snow-laden pines
(the project's evergreen master with procedural snow caps on every tier), ice
crystal clusters, an abandoned camp (torn tarp lean-to, stone fire ring,
crates) on the left, and a wrecked sled, crate and hanging-lantern post on the
right. Underneath: a packed-snow/ice band with snow drips and icicles over a
grey-blue rock body with hanging rock and ice spires.

Same framing, cameras and lighting as build_pine_valley.py so the islands line
up in the menu.
"""
import sys
import math
import random
import json
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector, Matrix, noise
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import island_lib as L  # noqa: E402

MAP = "FrozenPass"
STEM = "frozen"
SEED = 23
RADIUS = 30.0
DEPTH = 26.0
KITS = HERE.parent
EVERGREEN_GLB = KITS / "blender-master-evergreen" / "Evergreen_Master.glb"

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
# palette (from the Frozen Pass concept: white snow with soft blue shadows,
# blue-grey cliffs, pale-blue ice, brown camp wood/tarp, amber lantern).
# Snow is held below pure white so the sun does not blow it out.
# ---------------------------------------------------------------------------
SNOW = L.paint_mat("FP_Snow", [(0.30, "#aebfd6"), (0.50, "#c6d4e6"), (0.66, "#d8e2ef"), (0.82, "#e4ebf3")],
                   blob=8.0, jitter=0.5, facing=0.35)
BAND = L.paint_mat("FP_PackedIce", [(0.0, "#7092b6"), (0.45, "#8cabcb"), (1.0, "#a9c2dc")], blob=3.0, jitter=0.35,
                   facing=0.5)
UNDER = L.paint_mat("FP_UnderRock", [(0.08, "#414d63"), (0.36, "#5e6b82"), (0.62, "#7d8aa0"), (0.9, "#a3aebf")],
                    blob=5.0, jitter=0.32, facing=0.75)
DRIP = L.paint_mat("FP_SnowDrip", [(0.0, "#c3d2e4"), (1.0, "#e0e8f2")], blob=3.0, jitter=0.2, facing=0.4)
ROCK = L.paint_mat("FP_CliffRock", [(0.08, "#4c586e"), (0.36, "#69768c"), (0.62, "#8793a6"), (0.9, "#a7b0c0")],
                   blob=5.0, jitter=0.32, facing=0.75)
WOOD = L.paint_mat("FP_Wood", [(0.0, "#4e3322"), (0.5, "#6e4a30"), (1.0, "#8c6443")], blob=1.4, jitter=0.35, facing=0.4)
CUT = L.paint_mat("FP_CutWood", [(0.0, "#9c7650"), (1.0, "#b8936a")], blob=0.6, jitter=0.3, facing=0.2)
TARP = L.paint_mat("FP_Tarp", [(0.0, "#5e2c20"), (0.5, "#7d3f2b"), (1.0, "#9a5638")], blob=1.5, jitter=0.35, facing=0.5)
METAL = L.paint_mat("FP_Metal", [(0.0, "#2f3238"), (1.0, "#4f535c")], blob=1.0, jitter=0.2)
ICE = L.paint_mat("FP_Ice", [(0.0, "#6fa6d4"), (0.5, "#95c3e6"), (1.0, "#c4e2f5")], blob=2.0, jitter=0.3, facing=0.6)
ICE_DEEP = L.paint_mat("FP_IceDeep", [(0.0, "#5f98cb"), (0.5, "#7fb3de"), (1.0, "#a8d2ef")], blob=2.0, jitter=0.3,
                       facing=0.6)
CRYSTAL = L.paint_mat("FP_Crystal", [(0.0, "#7fb8e6"), (0.5, "#a6d4f3"), (1.0, "#d6f0fd")], blob=1.2, jitter=0.25,
                      facing=0.7)
ICE_FLOOR = L.paint_mat("FP_IceFloor", [(0.3, "#93bfe0"), (0.6, "#a8cde8"), (0.9, "#bcd9ef")], blob=3.0, jitter=0.45,
                        facing=0.3)
CRACK = L.paint_mat("FP_IceCrack", [(0.0, "#7eaed6"), (1.0, "#8cb8dc")], blob=1.0, jitter=0.1, facing=0.2)
ICE_FLOOR2 = L.paint_mat("FP_IceFloorLight", [(0.3, "#b0d2ec"), (0.6, "#c1dcf0"), (0.9, "#cfe4f4")], blob=3.0,
                         jitter=0.4, facing=0.3)
CHAR = L.paint_mat("FP_Charred", [(0.0, "#2a221e"), (1.0, "#443630")], blob=0.8, jitter=0.3, facing=0.4)
ASH = L.paint_mat("FP_Ash", [(0.0, "#5d5f66"), (1.0, "#7d8088")], blob=0.8, jitter=0.3, facing=0.2)
GLOW = L.paint_mat("FP_LanternGlow", [(0.0, "#ffb347"), (1.0, "#ffd27a")], blob=0.5, jitter=0.2, facing=0.4,
                   emission="#ffb347", emission_strength=4.0)
TWIG = L.paint_mat("FP_Twig", [(0.0, "#4a3a30"), (1.0, "#6e5a4a")], blob=0.8, jitter=0.3, facing=0.3)

# material slot order shared by every prop object
MATS = [ROCK, SNOW, WOOD, CUT, TARP, METAL, ICE, ICE_DEEP, CRYSTAL, ICE_FLOOR, CRACK, CHAR, ASH, GLOW, TWIG, ICE_FLOOR2]
(I_ROCK, I_SNOW, I_WOOD, I_CUT, I_TARP, I_METAL, I_ICE, I_ICE_DEEP, I_CRYSTAL, I_ICE_FLOOR, I_CRACK, I_CHAR,
 I_ASH, I_GLOW, I_TWIG, I_ICE_FLOOR2) = range(len(MATS))

# ---------------------------------------------------------------------------
# island body
# ---------------------------------------------------------------------------
island, R = L.island_body(f"{MAP}_Body", RADIUS, DEPTH, SEED, SNOW, BAND, UNDER, col=PROPS,
                          drip_mat=DRIP, drips=24, spires=7, top_bumps=0.35)
bpy.context.view_layer.update()
LIP, EDGE_BAND = 1.4, 1.6  # island_body defaults


def polar(theta_deg, frac):
    th = math.radians(theta_deg)
    r = R(th) * frac
    return math.cos(th) * r, math.sin(th) * r


def ground(x, y):
    return L.top_height(island, x, y)


def underside(x, y):
    """Height of the island's underside straight below (x, y) (ray from inside the body)."""
    deps = bpy.context.evaluated_depsgraph_get()
    eo = island.evaluated_get(deps)
    hit, loc, nrm, idx = eo.ray_cast(Vector((x, y, -LIP - EDGE_BAND - 0.5)), Vector((0, 0, -1)))
    return loc.z if hit else None


def facing_center(x, y):
    return math.atan2(-y, -x)


def local_to_world(cx, cy, face, dx, dy):
    """(dx, dy) in a frame whose +x points along `face`."""
    return (cx + dx * math.cos(face) - dy * math.sin(face), cy + dx * math.sin(face) + dy * math.cos(face))


made = []

# ---------------------------------------------------------------------------
# shape helpers
# ---------------------------------------------------------------------------


def rounded_box(bm, size, loc=(0, 0, 0), rot_z=0.0, bevel=0.4, segments=2, mat_index=0, jitter=0.0, seed=0):
    """Box with an absolute (not stretched) rounded bevel."""
    tmp = bmesh.new()
    bmesh.ops.create_cube(tmp, size=1.0)
    bmesh.ops.scale(tmp, vec=Vector(size), verts=tmp.verts)
    b = min(bevel, min(size) * 0.45)
    bmesh.ops.bevel(tmp, geom=list(tmp.edges), offset=b, segments=segments, affect="EDGES", profile=0.5)
    if jitter:
        L.jitter_bm(tmp, jitter, seed, freq=0.4)
    L.transform_bm(tmp, loc=loc, rot_z=rot_z)
    return L.merge_bm(bm, tmp, mat_index)


def blob(bm, loc, scale, seed, mat_index, subdiv=1, jitter=0.12, rot_z=0.0):
    tmp = bmesh.new()
    bmesh.ops.create_icosphere(tmp, subdivisions=subdiv, radius=1.0)
    L.jitter_bm(tmp, jitter, seed, freq=1.2)
    L.transform_bm(tmp, loc=loc, rot_z=rot_z, scale=scale)
    return L.merge_bm(bm, tmp, mat_index)


def hanging_cone(bm, top, r, length, mat_index, squash=1.0, rot_z=0.0, segs=5, seed=0):
    """Downward-pointing cone whose base is at `top`."""
    m = (Matrix.Translation(Vector(top)) @ Matrix.Rotation(rot_z, 4, "Z") @ Matrix.Rotation(math.pi, 4, "X")
         @ Matrix.Diagonal((1.0, squash, 1.0, 1.0)))
    return L.cyl_bm(bm, r, 0.0, length, segs=segs, matrix=m, mat_index=mat_index, cap_tris=True,
                    jitter=r * 0.12, seed=seed)


def snow_slab(bm, sw, sd, th, z0, seed, segs=16, p=4.5):
    """Thick snow cushion: rounded-rectangle (superellipse) footprint, rolled rim."""
    tmp = bmesh.new()
    rings = []
    for z in (0.0, th):
        ring = []
        for i in range(segs):
            a = 2 * math.pi * i / segs + math.pi / segs
            c, s_ = math.cos(a), math.sin(a)
            k = (abs(c) ** p + abs(s_) ** p) ** (-1 / p)
            ring.append(tmp.verts.new((c * k * sw * 0.5, s_ * k * sd * 0.5, z)))
        rings.append(ring)
    for i in range(segs):
        i2 = (i + 1) % segs
        tmp.faces.new((rings[0][i], rings[0][i2], rings[1][i2], rings[1][i]))
    tmp.faces.new(list(reversed(rings[0])))
    tmp.faces.new(rings[1])
    bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces)
    rim = [e for e in tmp.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-4]
    bmesh.ops.bevel(tmp, geom=rim, offset=min(0.55, th * 0.42), segments=2, affect="EDGES", profile=0.5)
    L.jitter_bm(tmp, 0.22, seed, freq=0.4)
    L.transform_bm(tmp, loc=(0, 0, z0))
    return L.merge_bm(bm, tmp, I_SNOW)


def snow_cliff(name, w, d, h, seed, loc, rot_z, taper=0.85, drips=2):
    """Grey rock block with a thick, rounded, slightly overhanging snow slab."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 0.5],
                              cuts=2, use_grid_fill=True)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.18, segments=1, affect="EDGES", profile=0.5)
    for v in bm.verts:
        t = v.co.z + 0.5
        k = 1.0 - (1.0 - taper) * t
        v.co.x *= k
        v.co.y *= k
    L.transform_bm(bm, loc=(0, 0, 0.5))
    L.transform_bm(bm, scale=(w, d, h))
    L.jitter_bm(bm, min(w, d, h) * 0.09, seed, freq=0.45)
    for f in bm.faces:
        f.material_index = I_ROCK
    bm.normal_update()
    L.faces_by_normal(bm, I_SNOW, 0.75, above=h * 0.8)
    # snow slab: rounded, a little wider than the tapered top so it overhangs
    sw, sd = w * taper * 1.10, d * taper * 1.12
    th = 1.35 + 0.25 * (seed % 3)
    snow_slab(bm, sw, sd, th, h - 0.55, seed + 5)
    L.transform_bm(bm, loc=loc, rot_z=rot_z)
    return L.bm_to_obj(name, bm, MATS, PROPS)


def snow_rock(name, size, seed, loc, rot_z=0.0, cap=0.5, sink=0.25):
    """Faceted boulder with snow on its upward facets."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.5)
    L.jitter_bm(bm, 0.22, seed, freq=1.3)
    for v in bm.verts:
        if v.co.z < -0.25:
            v.co.z = -0.25 + (v.co.z + 0.25) * 0.25
    L.transform_bm(bm, scale=size)
    zmin = min(v.co.z for v in bm.verts)
    for v in bm.verts:
        v.co.z -= zmin + size[2] * sink * 0.5
    for f in bm.faces:
        f.material_index = I_ROCK
    bm.normal_update()
    top = max(v.co.z for v in bm.verts)
    L.faces_by_normal(bm, I_SNOW, cap, above=top - size[2] * 0.6)
    L.transform_bm(bm, loc=loc, rot_z=rot_z)
    return L.bm_to_obj(name, bm, MATS, PROPS)


def crystal_cluster(bm, loc, s, seed, count=5):
    """Hexagonal ice prisms with pointed tips, leaning out from a common root."""
    r2 = random.Random(seed)
    for i in range(count):
        big = i == 0
        r = s * (0.42 if big else r2.uniform(0.2, 0.32))
        hgt = s * (2.4 if big else r2.uniform(1.0, 1.8))
        a = r2.uniform(0, 6.28)
        lean = 0.0 if big else r2.uniform(0.35, 0.75)
        off = 0.0 if big else s * r2.uniform(0.25, 0.5)
        base = Vector((loc[0] + math.cos(a) * off, loc[1] + math.sin(a) * off, loc[2] - 0.3))
        rot = Matrix.Rotation(a, 4, "Z") @ Matrix.Rotation(lean, 4, "Y")
        spin = Matrix.Rotation(r2.uniform(0, 1), 4, "Z")
        mi = I_CRYSTAL if i % 3 else I_ICE
        L.cyl_bm(bm, r, r * 0.92, hgt, segs=6, matrix=Matrix.Translation(base) @ rot @ spin, mat_index=mi)
        L.cyl_bm(bm, r * 0.92, 0.0, r * 1.6, segs=6, matrix=Matrix.Translation(base) @ rot @ spin
                 @ Matrix.Translation((0, 0, hgt)), mat_index=mi, cap_tris=True)


def snow_mound(bm, loc, sx, sy, sz, seed, rot_z=0.0):
    blob(bm, (loc[0], loc[1], loc[2] - sz * 0.35), (sx, sy, sz), seed, I_SNOW, subdiv=1, jitter=0.1, rot_z=rot_z)


def twig_bush(bm, loc, s, seed):
    r2 = random.Random(seed)
    n = r2.randint(4, 6)
    for i in range(n):
        a = 2 * math.pi * i / n + r2.uniform(-0.3, 0.3)
        tilt = r2.uniform(0.25, 0.7)
        ln = s * r2.uniform(0.9, 1.6)
        m = L.trs((loc[0], loc[1], loc[2] - 0.05), (0, 0, 0)) @ Matrix.Rotation(a, 4, "Z") @ \
            Matrix.Rotation(tilt, 4, "Y")
        L.cyl_bm(bm, 0.07 * s, 0.025 * s, ln, segs=4, matrix=m, mat_index=I_TWIG)
        # one fork per twig
        fm = m @ Matrix.Translation((0, 0, ln * 0.55)) @ Matrix.Rotation(r2.choice((-1, 1)) * 0.6, 4, "X")
        L.cyl_bm(bm, 0.04 * s, 0.015 * s, ln * 0.45, segs=3, matrix=fm, mat_index=I_TWIG)


def ice_patch(name, loc, rx, ry, seed, rot_z=0.0, cracks=4):
    """Flat pale-blue ice sheet draped on the snow with a few darker crack lines."""
    r2 = random.Random(seed)
    bm = bmesh.new()
    segs = 18
    # off-centre hub so the shards are irregular, like a cracked sheet
    hub = Vector((rx * r2.uniform(-0.25, 0.25), ry * r2.uniform(-0.25, 0.25), 0))
    c = bm.verts.new(hub)
    ring = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        k = 1 + 0.2 * math.sin(a * 2 + seed) + 0.1 * math.cos(a * 3 + seed * 2) + 0.07 * math.sin(a * 7 + seed)
        ring.append(bm.verts.new((math.cos(a) * rx * k, math.sin(a) * ry * k, 0)))
    # group the fan into a few shards of 2-5 wedges, alternating two ice tones
    cuts, i = [], 0
    while i < segs:
        cuts.append(i)
        i += r2.randint(2, 5)
    tone = I_ICE_FLOOR
    for j, start in enumerate(cuts):
        end = cuts[j + 1] if j + 1 < len(cuts) else segs
        for w in range(start, end):
            bm.faces.new((c, ring[w], ring[(w + 1) % segs])).material_index = tone
        tone = I_ICE_FLOOR2 if tone == I_ICE_FLOOR else I_ICE_FLOOR
    L.transform_bm(bm, loc=(loc[0], loc[1], 0), rot_z=rot_z)
    obj = L.bm_to_obj(name, bm, MATS, PROPS)
    for v in obj.data.vertices:
        v.co.z += ground(v.co.x, v.co.y) + 0.06
    return obj


# ---------------------------------------------------------------------------
# back cliff wall with a notch for the ice fall at the back centre
# ---------------------------------------------------------------------------
cliff_tops = []
cliff_thetas = [24, 37, 50, 63, 75, 105, 117, 130, 143, 156]
for k, th in enumerate(cliff_thetas):
    mid = 1 - abs(th - 90) / 70
    h = 7.0 + 5.5 * mid + rng.uniform(-0.8, 0.8)
    w = rng.uniform(7.0, 8.8)
    d = rng.uniform(5.5, 6.8)
    x, y = polar(th + rng.uniform(-2, 2), 0.84)
    z = ground(x, y) - 0.6
    rot = math.radians(th + 90 + rng.uniform(-8, 8))
    b = snow_cliff(f"{MAP}_Cliff_{k:02d}", w, d, h, SEED + k, (x, y, z), rot)
    made.append(b)
    cliff_tops.append((th, x, y, z + h, b))
    if k % 2 == 0:
        x2, y2 = polar(th + rng.uniform(-5, 5), 0.70)
        z2 = ground(x2, y2) - 0.4
        s = snow_cliff(f"{MAP}_CliffStep_{k:02d}", w * 0.7, d * 0.7, h * 0.4, SEED + 40 + k, (x2, y2, z2),
                       rot + 0.3, drips=1)
        made.append(s)

# recessed tall block behind the notch, with the frozen fall down its face
FALL_TH = 90
bx, by = polar(FALL_TH, 0.90)
bz = ground(bx, by) - 0.6
BACK_H, BACK_W, BACK_D = 13.8, 9.5, 5.0
back_rot = math.radians(FALL_TH + 90)
made.append(snow_cliff(f"{MAP}_CliffBack", BACK_W, BACK_D, BACK_H, SEED + 90, (bx, by, bz), back_rot, drips=0))
cliff_tops.append((FALL_TH, bx, by, bz + BACK_H, made[-1]))


def ice_fall(name):
    """Frozen waterfall: a curtain of flattened vertical ice columns, a curled lip
    spilling over the snow slab and a bulging frozen splash at the foot."""
    r2 = random.Random(SEED + 7)
    bm = bmesh.new()
    top = BACK_H + 0.4
    face_y = BACK_D * 0.5 + 0.1      # local front face (+Y faces the arena) of the back block, at its base
    for i in range(6):
        dx = -2.6 + i * 1.05 + r2.uniform(-0.15, 0.15)
        rr = r2.uniform(0.62, 0.85)
        hh = top - r2.uniform(0.0, 0.8)
        # lean back with the block's taper
        lean = math.atan2(BACK_D * 0.5 * 0.15, BACK_H)
        m = (Matrix.Translation((dx, face_y - 0.1, -0.4)) @ Matrix.Rotation(lean, 4, "X")
             @ Matrix.Diagonal((1.0, 0.55, 1.0, 1.0)))
        L.cyl_bm(bm, rr * 1.15, rr * 0.85, hh, segs=7, matrix=m, mat_index=I_ICE if i % 2 else I_ICE_DEEP,
                 jitter=0.08, seed=SEED + i)
    # lip curling over the top
    m = Matrix.Translation((-3.4, face_y - 0.45, top - 0.5)) @ Matrix.Rotation(math.pi / 2, 4, "Y") @ \
        Matrix.Diagonal((0.75, 1.0, 1.0, 1.0))
    L.cyl_bm(bm, 0.9, 0.9, 6.8, segs=7, matrix=m, mat_index=I_ICE, jitter=0.1, seed=SEED + 30)
    # bulging splash at the base
    blob(bm, (0, face_y + 1.0, 0.1), (4.2, 2.0, 1.6), SEED + 31, I_ICE_DEEP, jitter=0.12)
    blob(bm, (-2.3, face_y + 1.6, 0.0), (1.8, 1.4, 1.0), SEED + 32, I_ICE, jitter=0.1)
    blob(bm, (2.4, face_y + 1.4, 0.0), (1.7, 1.3, 0.9), SEED + 33, I_ICE, jitter=0.1)
    L.transform_bm(bm, loc=(bx, by, bz + 0.6), rot_z=back_rot)
    return L.bm_to_obj(name, bm, MATS, PROPS)


made.append(ice_fall(f"{MAP}_IceFall"))
# frozen pool in front of the fall
px, py = polar(FALL_TH, 0.62)
made.append(ice_patch(f"{MAP}_IcePool", (px, py), 5.0, 3.4, 3, rot_z=0.0, cracks=3))

# side outcrops (snow capped)
for k, (th, fr, size) in enumerate([(197, 0.86, (6, 5, 4.8)), (340, 0.86, (6.5, 5, 5.2)), (181, 0.9, (4, 4, 3.2))]):
    x, y = polar(th, fr)
    made.append(snow_cliff(f"{MAP}_Outcrop_{k}", *size, SEED + 70 + k, (x, y, ground(x, y) - 0.5),
                           math.radians(th + 90), drips=1))

# snow-capped boulders: interior sprinkles + chunky front-rim rocks
for k, (th, fr, s) in enumerate([(250, 0.42, 1.8), (300, 0.30, 1.4), (40, 0.40, 1.6), (140, 0.36, 1.5),
                                  (212, 0.22, 1.2), (20, 0.14, 1.1), (275, 0.62, 1.5), (110, 0.55, 1.3),
                                  (236, 0.93, 5.0), (257, 0.95, 3.4), (293, 0.94, 4.6), (316, 0.9, 3.2)]):
    x, y = polar(th, fr)
    made.append(snow_rock(f"{MAP}_Boulder_{k:02d}", (s * 1.25, s, s * 0.72), SEED + 100 + k, (x, y, ground(x, y)),
                          rot_z=rng.uniform(0, 6.28), cap=0.45 if s > 3 else 0.55))

# ice patches on the floor
for k, (th, fr, rx, ry, rot) in enumerate([(222, 0.40, 5.2, 3.6, 0.3), (318, 0.44, 5.6, 3.8, -0.2),
                                           (150, 0.32, 3.8, 2.6, 0.6), (38, 0.38, 3.6, 2.5, -0.5)]):
    x, y = polar(th, fr)
    made.append(ice_patch(f"{MAP}_IcePatch_{k}", (x, y), rx, ry, 11 + k * 5, rot_z=rot))

# ---------------------------------------------------------------------------
# abandoned camp (left): torn tarp lean-to, stone fire ring, crates
# ---------------------------------------------------------------------------


def crate(bm, loc, size, rot_z, snow=True):
    L.box_bm(bm, (size, size, size), loc=(loc[0], loc[1], loc[2] + size / 2), rot=Matrix.Rotation(rot_z, 4, "Z"),
             chamfer=size * 0.08, mat_index=I_WOOD)
    for s in (-1, 1):
        L.box_bm(bm, (size * 1.02, size * 0.14, size * 1.02), loc=(loc[0], loc[1], loc[2] + size / 2),
                 rot=Matrix.Rotation(rot_z, 4, "Z") @ Matrix.Rotation(s * 0.785, 4, "X"), mat_index=I_CUT)
    if snow:
        rounded_box(bm, (size * 0.96, size * 0.96, size * 0.2), loc=(loc[0], loc[1], loc[2] + size + 0.06),
                    rot_z=rot_z, bevel=size * 0.09, segments=1, mat_index=I_SNOW)


def torn_lean_to(name, loc, rot_z, length=6.8, depth=4.6, height=4.1, seed=3):
    """Crossed stick frames at both ends, a ridge pole, and a sagging torn tarp
    draped from the ridge down to the snow on one side."""
    r2 = random.Random(seed)
    bm = bmesh.new()
    # crossed sticks at each end (X frame)
    for ex in (-length / 2, length / 2):
        for side in (-1, 1):
            p0 = Vector((ex, side * 1.4, -0.1))
            p1 = Vector((ex, -side * 0.45, height + 0.7))
            dvec = p1 - p0
            m = Matrix.Translation(p0) @ dvec.to_track_quat("Z", "Y").to_matrix().to_4x4()
            L.cyl_bm(bm, 0.13, 0.09, dvec.length, segs=5, matrix=m, mat_index=I_WOOD)
    m = Matrix.Translation((-length / 2 - 0.5, 0, height)) @ Matrix.Rotation(math.pi / 2, 4, "Y")
    L.cyl_bm(bm, 0.12, 0.11, length + 1.0, segs=5, matrix=m, mat_index=I_WOOD)
    # tarp grid: u along the ridge, v from ridge down to the ground (+Y side)
    nu, nv = 6, 4
    tarp = bmesh.new()
    grid = []
    for j in range(nv + 1):
        row = []
        t = j / nv
        for i in range(nu + 1):
            u = i / nu
            x = (u - 0.5) * (length + 0.5)
            y = 0.1 + t * depth
            z = height + 0.1 - t * height
            # sag between the frames, stronger lower down
            z -= 0.45 * math.sin(math.pi * u) * math.sin(math.pi * min(1.0, t * 1.1))
            # ragged bottom edge
            if j == nv:
                y -= r2.uniform(0.0, 0.9)
                z += r2.uniform(0.0, 0.8)
            row.append(tarp.verts.new((x, y, z)))
        grid.append(row)
    for j in range(nv):
        for i in range(nu):
            # tear: drop a couple of lower quads for a ripped look
            if (j, i) in ((nv - 1, 1), (nv - 1, 4), (nv - 2, 4)):
                continue
            tarp.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    loose = [v for v in tarp.verts if not v.link_faces]
    bmesh.ops.delete(tarp, geom=loose, context="VERTS")
    bmesh.ops.solidify(tarp, geom=list(tarp.faces), thickness=0.1)
    L.merge_bm(bm, tarp, I_TARP)
    L.transform_bm(bm, loc=loc, rot_z=rot_z)
    obj = L.bm_to_obj(name, bm, MATS, PROPS)
    return obj


def fire_ring(name, loc, seed):
    r2 = random.Random(seed)
    bm = bmesh.new()
    for i in range(9):
        a = 2 * math.pi * i / 9
        st = bmesh.new()
        bmesh.ops.create_icosphere(st, subdivisions=1, radius=0.5)
        L.jitter_bm(st, 0.12, seed + i, freq=2.0)
        L.transform_bm(st, loc=(math.cos(a) * 1.35, math.sin(a) * 1.35, 0.15), rot_z=r2.uniform(0, 6),
                       scale=(0.8, 0.62, 0.55))
        for f in st.faces:
            f.material_index = 0
        st.normal_update()
        faces = L.merge_bm(bm, st, I_ROCK)
        for f in faces:
            f.normal_update()
            if f.normal.z > 0.6:
                f.material_index = I_SNOW
    # ash bed + charred logs, long dead
    L.cyl_bm(bm, 1.05, 0.9, 0.12, segs=9, matrix=Matrix.Translation((0, 0, -0.02)), mat_index=I_ASH)
    for i in range(3):
        a = 2 * math.pi * i / 3 + 0.3
        p0 = Vector((math.cos(a) * 0.95, math.sin(a) * 0.95, 0.1))
        p1 = Vector((math.cos(a + 0.4) * -0.2, math.sin(a + 0.4) * -0.2, 0.45))
        dvec = p1 - p0
        m = Matrix.Translation(p0) @ dvec.to_track_quat("Z", "Y").to_matrix().to_4x4()
        L.cyl_bm(bm, 0.17, 0.13, dvec.length, segs=5, matrix=m, mat_index=I_CHAR)
    L.transform_bm(bm, loc=loc)
    return L.bm_to_obj(name, bm, MATS, PROPS)


cx, cy = polar(166, 0.60)
cz = ground(cx, cy)
face = facing_center(cx, cy)
made.append(torn_lean_to(f"{MAP}_TarpLeanTo", (cx - 0.5, cy + 0.6, cz - 0.05), face + math.pi / 2 + 0.3))
fx, fy = local_to_world(cx, cy, face, 4.6, -0.6)
made.append(fire_ring(f"{MAP}_FireRing", (fx, fy, ground(fx, fy)), 5))
bm = bmesh.new()
for (dx, dy, dz, s, r) in [(3.0, 3.6, 0, 1.6, 0.3), (4.4, 3.2, 0, 1.3, 0.8), (1.6, -3.6, 0, 1.4, 0.2)]:
    px, py = local_to_world(cx, cy, face, dx, dy)
    crate(bm, (px, py, ground(px, py) + dz - 0.1), s, r)
for k, (dx, dy) in enumerate([(2.5, -1.8), (6.0, 1.8)]):
    px, py = local_to_world(cx, cy, face, dx, dy)
    snow_mound(bm, (px, py, ground(px, py)), 1.2, 0.9, 0.5, SEED + 400 + k)
made.append(L.bm_to_obj(f"{MAP}_CampProps", bm, MATS, PROPS))

# ---------------------------------------------------------------------------
# right side: wrecked sled, crate, lantern post
# ---------------------------------------------------------------------------


def wrecked_sled(name, loc, rot_z):
    bm = bmesh.new()
    ln, wd = 4.6, 2.2
    for side in (-1, 1):
        y = side * wd * 0.45
        # runner + curled front
        L.box_bm(bm, (ln, 0.2, 0.22), loc=(0, y, 0.11), chamfer=0.05, mat_index=I_WOOD)
        for k, (ang, dx, dz) in enumerate([(0.55, ln / 2 + 0.3, 0.3), (1.2, ln / 2 + 0.62, 0.85),
                                           (2.1, ln / 2 + 0.5, 1.35)]):
            L.box_bm(bm, (0.8, 0.2, 0.2), loc=(dx, y, dz), rot=Matrix.Rotation(-ang, 4, "Y"), chamfer=0.05,
                     mat_index=I_WOOD)
        # struts
        for sx in (-1.5, 0.0, 1.5):
            L.box_bm(bm, (0.18, 0.18, 0.6), loc=(sx, y, 0.5), mat_index=I_WOOD)
    # deck slats (one missing, one knocked askew)
    for k, sx in enumerate((-1.8, -1.1, -0.4, 0.3, 1.0, 1.7)):
        if k == 3:
            continue
        rot = Matrix.Rotation(0.25, 4, "Z") if k == 4 else None
        L.box_bm(bm, (0.5, wd + 0.2, 0.14), loc=(sx, 0, 0.86), rot=rot, chamfer=0.04,
                 mat_index=I_CUT if k % 2 else I_WOOD)
    # one side rail intact, the other snapped and leaning
    L.box_bm(bm, (ln * 0.8, 0.16, 0.16), loc=(-0.1, wd * 0.5, 1.25), chamfer=0.04, mat_index=I_WOOD)
    L.box_bm(bm, (ln * 0.45, 0.16, 0.16), loc=(-1.0, -wd * 0.5 - 0.1, 1.0), rot=Matrix.Rotation(0.35, 4, "Y"),
             chamfer=0.04, mat_index=I_WOOD)
    for sx in (-1.6, 0.0, 1.4):
        L.box_bm(bm, (0.14, 0.14, 0.45), loc=(sx, wd * 0.5, 1.05), mat_index=I_WOOD)
    # snow drifted onto the deck
    blob(bm, (-1.0, 0.1, 1.0), (1.1, 0.9, 0.35), SEED + 501, I_SNOW, jitter=0.08)
    # the missing slat lying in the snow beside it
    L.box_bm(bm, (0.5, wd + 0.2, 0.14), loc=(0.6, -wd - 0.6, 0.05), rot=Matrix.Rotation(0.9, 4, "Z"),
             chamfer=0.04, mat_index=I_CUT)
    # tipped onto one runner, half sunk
    L.transform_bm(bm, rot=Matrix.Rotation(0.14, 4, "X") @ Matrix.Rotation(-0.05, 4, "Y"), scale=(1.3, 1.3, 1.3))
    L.transform_bm(bm, loc=loc, rot_z=rot_z)
    return L.bm_to_obj(name, bm, MATS, PROPS)


def lantern_post(name, loc, rot_z):
    bm = bmesh.new()
    H = 5.2
    L.box_bm(bm, (0.5, 0.5, H), loc=(0, 0, H / 2 - 0.3), chamfer=0.06, mat_index=I_WOOD)
    L.box_bm(bm, (2.0, 0.36, 0.36), loc=(0.8, 0, H - 0.7), chamfer=0.05, mat_index=I_WOOD)
    L.box_bm(bm, (1.1, 0.24, 0.24), loc=(0.45, 0, H - 1.25), rot=Matrix.Rotation(0.75, 4, "Y"), chamfer=0.04,
             mat_index=I_WOOD)
    # snow on the post top and the arm
    rounded_box(bm, (0.62, 0.62, 0.3), loc=(0, 0, H - 0.18), bevel=0.12, segments=1, mat_index=I_SNOW)
    rounded_box(bm, (1.7, 0.44, 0.2), loc=(0.95, 0, H - 0.44), bevel=0.08, segments=1, mat_index=I_SNOW)
    # chain + lantern
    lx = 1.55
    L.cyl_bm(bm, 0.05, 0.05, 0.55, segs=4, matrix=Matrix.Translation((lx, 0, H - 1.42)), mat_index=I_METAL)
    L.cyl_bm(bm, 0.5, 0.14, 0.38, segs=4, matrix=Matrix.Translation((lx, 0, H - 1.8)) @ Matrix.Rotation(0.785, 4, "Z"),
             mat_index=I_METAL)
    L.box_bm(bm, (0.58, 0.58, 0.78), loc=(lx, 0, H - 2.22), mat_index=I_GLOW)
    for sx in (-1, 1):
        for sy in (-1, 1):
            L.box_bm(bm, (0.1, 0.1, 0.84), loc=(lx + sx * 0.3, sy * 0.3, H - 2.22), mat_index=I_METAL)
    L.box_bm(bm, (0.7, 0.7, 0.12), loc=(lx, 0, H - 2.66), mat_index=I_METAL)
    # snow heaped at the foot
    blob(bm, (0, 0, -0.25), (1.1, 1.0, 0.6), SEED + 601, I_SNOW, jitter=0.08)
    L.transform_bm(bm, scale=(1.2, 1.2, 1.2))
    L.transform_bm(bm, loc=loc, rot_z=rot_z)
    return L.bm_to_obj(name, bm, MATS, PROPS)


sx_, sy_ = polar(14, 0.60)
face_e = facing_center(sx_, sy_)
made.append(wrecked_sled(f"{MAP}_Sled", (sx_, sy_, ground(sx_, sy_) - 0.15), face_e + 0.5))
bm = bmesh.new()
px, py = local_to_world(sx_, sy_, face_e, 0.8, -3.8)
crate(bm, (px, py, ground(px, py) - 0.1), 1.5, 0.5)
px, py = local_to_world(sx_, sy_, face_e, -1.5, 3.2)
snow_mound(bm, (px, py, ground(px, py)), 1.4, 1.0, 0.6, SEED + 410)
made.append(L.bm_to_obj(f"{MAP}_SledProps", bm, MATS, PROPS))
lx_, ly_ = polar(1, 0.76)
made.append(lantern_post(f"{MAP}_LanternPost", (lx_, ly_, ground(lx_, ly_)), facing_center(lx_, ly_) - 0.5))

# ---------------------------------------------------------------------------
# ice crystals, twig bushes, snow drifts at cliff feet
# ---------------------------------------------------------------------------
bm = bmesh.new()
for k, (th, fr, s) in enumerate([(80, 0.74, 1.3), (100, 0.74, 1.1), (47, 0.73, 1.0), (133, 0.72, 1.1),
                                 (170, 0.80, 1.0), (200, 0.76, 0.9), (345, 0.75, 1.1), (5, 0.84, 0.9),
                                 (248, 0.88, 1.0), (285, 0.92, 1.2), (330, 0.94, 0.9), (228, 0.90, 0.8),
                                 (62, 0.93, 0.9), (158, 0.93, 0.9)]):
    x, y = polar(th, fr)
    crystal_cluster(bm, (x, y, ground(x, y)), s * 1.35, SEED + 700 + k, count=5 if s > 1.0 else 4)
for k, (th, x, y, top, blk) in enumerate(cliff_tops):
    if k % 2 == 1 and k < len(cliff_tops) - 1:
        cx2, cy2 = x - math.cos(math.radians(th)) * 1.2, y - math.sin(math.radians(th)) * 1.2
        crystal_cluster(bm, (cx2, cy2, L.top_height(blk, cx2, cy2) + 0.2), 1.1, SEED + 760 + k, count=4)
made.append(L.bm_to_obj(f"{MAP}_Crystals", bm, MATS, PROPS))

bm = bmesh.new()
for k in range(11):
    th = rng.uniform(0, 360)
    fr = rng.uniform(0.2, 0.8)
    x, y = polar(th, fr)
    twig_bush(bm, (x, y, ground(x, y)), rng.uniform(0.8, 1.2), SEED + 800 + k)
made.append(L.bm_to_obj(f"{MAP}_Twigs", bm, MATS, PROPS))

bm = bmesh.new()
for k, th in enumerate([30, 56, 70, 110, 124, 150, 190, 350]):
    x, y = polar(th, 0.74)
    snow_mound(bm, (x, y, ground(x, y)), rng.uniform(2.2, 3.2), rng.uniform(1.4, 2.0), rng.uniform(0.9, 1.3),
               SEED + 900 + k, rot_z=math.radians(th + 90))
made.append(L.bm_to_obj(f"{MAP}_Drifts", bm, MATS, PROPS))

# ---------------------------------------------------------------------------
# underside: icicles hanging from the ice band + a few long ice spires
# ---------------------------------------------------------------------------
bm = bmesh.new()
n_ic = 40
for s in range(n_ic):
    th = 2 * math.pi * (s + 0.5 + rng.uniform(-0.3, 0.3)) / n_ic
    r = R(th) * 0.975
    ln = rng.uniform(0.9, 2.6)
    hanging_cone(bm, (math.cos(th) * r, math.sin(th) * r, -LIP - EDGE_BAND + 0.5), rng.uniform(0.3, 0.5), ln + 0.5,
                 I_ICE if s % 3 else I_ICE_DEEP, segs=5, seed=SEED + s)
for s in range(6):
    th = rng.uniform(0, 2 * math.pi)
    rr = RADIUS * rng.uniform(0.45, 0.7)
    x, y = math.cos(th) * rr, math.sin(th) * rr
    z = underside(x, y)
    if z is None:
        continue
    hanging_cone(bm, (x, y, z + 0.8), rng.uniform(0.7, 1.1), rng.uniform(4.0, 8.0), I_ICE, segs=6, seed=SEED + 50 + s)
made.append(L.bm_to_obj(f"{MAP}_Icicles", bm, MATS, PROPS))

# ---------------------------------------------------------------------------
# snowy pines: the project's evergreen master + procedural snow caps per tier,
# baked into one SnowPine master (own atlas), then instanced like Pine Valley
# ---------------------------------------------------------------------------
# tier table from blender-master-evergreen/build_tree.py (authoring units; the
# master's mesh is scaled x1.8 afterwards): radius, base, top, lobes, phase
TIERS = [(2.9, 2.36, 5.40, 8, .06), (2.40, 4.26, 7.05, 7, .21), (1.90, 6.18, 8.58, 6, .10),
         (1.32, 7.78, 9.52, 5, .24), (.66, 8.84, 10.0, 4, .10)]
PROFILE = [(1.0, 0.0), (.975, .075), (.66, .34), (.29, .70), (.025, .98), (0.0, 1.0)]


def profile_t(rf):
    for (r0, t0), (r1, t1) in zip(PROFILE[:-1], PROFILE[1:]):
        if r1 <= rf <= r0:
            return t0 + (t1 - t0) * (r0 - rf) / max(1e-6, r0 - r1)
    return 0.0 if rf > 1 else 1.0


def snow_caps(tree_mesh, S):
    """White snow shells on each foliage tier, snapped onto the real tier surface."""
    verts = [v.co.copy() for v in tree_mesh.vertices]
    polys = [tuple(p.vertices) for p in tree_mesh.polygons]
    bvh = BVHTree.FromPolygons(verts, polys)
    bm = bmesh.new()
    for ti, (rad, base, top, lobes, phase) in enumerate(TIERS):
        n = lobes * 3
        crown = ti == len(TIERS) - 1

        def surf(a, rf, lift):
            petal = (.5 + .5 * math.cos(lobes * (a - phase))) ** .36
            infl = rf ** 2.5
            r = rad * rf * (1 - .065 * infl * (1 - petal)) * S
            z = (base + (top - base) * profile_t(rf) - .15 * (rad / 2.9) * petal * infl) * S
            p = Vector((r * math.cos(a), r * math.sin(a), z))
            hit = bvh.ray_cast(p + Vector((0, 0, 0.6 * S)), Vector((0, 0, -1)), 1.2 * S)
            if hit[0] is not None:
                p, nrm = hit[0], hit[1]
                if nrm.z < 0:
                    nrm = -nrm
            else:
                nrm = Vector((math.cos(a) * 0.5, math.sin(a) * 0.5, 1.0)).normalized()
            return p + nrm * lift

        rings = []
        edge = []
        for i in range(n):
            a = 2 * math.pi * i / n + phase
            wave = math.cos(lobes * (a - phase))
            wob = noise.noise(Vector((math.cos(a) * 2, math.sin(a) * 2, ti * 3.1)))
            edge.append(min(0.95, (0.80 if crown else 0.69) + 0.04 * wave + 0.03 * wob))
        fracs = [(-0.035, -0.06), (0.0, 0.15), (None, 0.17), (None, 0.15)]
        for k, (dr, lift) in enumerate(fracs):
            ring = []
            for i in range(n):
                a = 2 * math.pi * i / n + phase
                e = edge[i]
                rf = e + dr if dr is not None else e * (0.62 if k == 2 else 0.28)
                p = surf(a, rf, lift * S)
                if k == 1:
                    p.z -= 0.06 * S   # rolled, slightly drooping snow edge
                ring.append(bm.verts.new(p))
            rings.append(ring)
        tip = bm.verts.new(Vector((0, 0, top * S + 0.12 * S)))
        for a_ring, b_ring in zip(rings[:-1], rings[1:]):
            for i in range(n):
                i2 = (i + 1) % n
                bm.faces.new((a_ring[i], a_ring[i2], b_ring[i2], b_ring[i])).material_index = 0
        last = rings[-1]
        for i in range(n):
            bm.faces.new((last[i], last[(i + 1) % n], tip)).material_index = 0
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


tree_src = L.import_master(EVERGREEN_GLB, "Evergreen_Master_Src", hide=False)
zmax = max(v.co.z for v in tree_src.data.vertices)
TREE_S = zmax / 10.0            # authoring crown tip is at z = 10
print("EVERGREEN height", round(zmax, 3), "scale", round(TREE_S, 3), flush=True)

# own copy of the master's material: explicit UV map (the atlas bake makes a new
# active UV) + cooler, deeper foliage like the concept's snowy pines (trunk
# region of the atlas, u > 0.5, is left untouched)
src_mat = tree_src.data.materials[0].copy()
src_mat.name = "FP_EvergreenCool"
tree_src.data.materials[0] = src_mat
nt = src_mat.node_tree
uv_name = tree_src.data.uv_layers[0].name
uvn = nt.nodes.new("ShaderNodeUVMap")
uvn.uv_map = uv_name
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
texn = next(n for n in nt.nodes if n.type == "TEX_IMAGE")
nt.links.new(uvn.outputs["UV"], texn.inputs["Vector"])
hsv = nt.nodes.new("ShaderNodeHueSaturation")
hsv.inputs["Hue"].default_value = 0.54
hsv.inputs["Saturation"].default_value = 0.85
hsv.inputs["Value"].default_value = 0.64
nt.links.new(texn.outputs["Color"], hsv.inputs["Color"])
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(uvn.outputs["UV"], sep.inputs["Vector"])
step = nt.nodes.new("ShaderNodeMath")
step.operation = "GREATER_THAN"
step.inputs[1].default_value = 0.5
nt.links.new(sep.outputs["X"], step.inputs[0])
mix = nt.nodes.new("ShaderNodeMix")
mix.data_type = "RGBA"
nt.links.new(step.outputs[0], mix.inputs[0])
nt.links.new(hsv.outputs["Color"], mix.inputs[6])
nt.links.new(texn.outputs["Color"], mix.inputs[7])
nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])

TREE_SNOW = L.paint_mat("FP_TreeSnow", [(0.3, "#b9c9de"), (0.6, "#d4dfec"), (0.9, "#e3eaf3")], blob=2.0, jitter=0.3,
                        facing=0.6)
cap_bm = snow_caps(tree_src.data, TREE_S)
caps = L.bm_to_obj("SnowPine_Caps", cap_bm, [TREE_SNOW], FOLIAGE, flat=False)
for p in caps.data.polygons:
    p.use_smooth = True
snowpine = L.join("SnowPine_Master", [tree_src, caps], FOLIAGE)
L.bake_atlas(snowpine, OUT_TEX / f"{STEM}-snowpine-atlas.png", size=1024, margin=8)
snowpine.data.materials[0].name = "SnowPine_Atlas"
snowpine.hide_render = True
snowpine.hide_viewport = True
print("SNOWPINE", L.tri_count(snowpine), flush=True)

trees = []
for k, (th, x, y, top, blk) in enumerate(cliff_tops):
    if k % 2 == 1 or k == len(cliff_tops) - 1:
        continue
    tz = L.top_height(blk, x, y)
    trees.append(L.place_instance(snowpine, f"{MAP}_SnowPine_Cliff_{k}", (x, y, tz - 0.4), rng.uniform(0, 6.28),
                                  rng.uniform(0.62, 0.78), FOLIAGE))
for k, (th, fr, s) in enumerate([(44, 0.97, 0.85), (121, 0.97, 0.9), (98, 0.99, 0.8), (150, 0.95, 0.8),
                                 (190, 0.90, 0.85), (213, 0.84, 0.7), (345, 0.92, 0.8), (326, 0.86, 0.68),
                                 (240, 0.78, 0.55), (300, 0.80, 0.58)]):
    x, y = polar(th, fr)
    trees.append(L.place_instance(snowpine, f"{MAP}_SnowPine_{k:02d}", (x, y, ground(x, y) - 0.3),
                                  rng.uniform(0, 6.28), s, FOLIAGE))

# ---------------------------------------------------------------------------
# join + bake the procedural parts into one atlas mesh
# ---------------------------------------------------------------------------
island_mesh = L.join(f"{MAP}_Island", [island] + made, PROPS)
bpy.ops.object.select_all(action="DESELECT")
island_mesh.select_set(True)
bpy.context.view_layer.objects.active = island_mesh
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
L.bake_atlas(island_mesh, OUT_TEX / f"{STEM}-island-atlas.png", size=2048)
print("BAKED", island_mesh.name, L.tri_count(island_mesh), flush=True)

# ---------------------------------------------------------------------------
# previews (identical cameras/lighting to Pine Valley)
# ---------------------------------------------------------------------------
L.setup_preview()
hero = L.camera("Cam_Hero", (0, -118, 34), (0, 0, -7), lens=35)
L.render(hero, OUT_PREV / f"{STEM}-hero.png")
close = L.camera("Cam_Close", (-8, -58, 40), (0, 4, 1), lens=35)
L.render(close, OUT_PREV / f"{STEM}-closeup.png")
side = L.camera("Cam_Side", (112, -52, 8), (0, 0, -8), lens=35)
L.render(side, OUT_PREV / f"{STEM}-side.png")

# ---------------------------------------------------------------------------
# export + report
# ---------------------------------------------------------------------------
snowpine.hide_viewport = False
export_objs = [island_mesh] + trees
L.export(export_objs, OUT_FBX / f"{STEM}-mini-island.fbx", OUT_GLB / f"{STEM}-mini-island.glb")
snowpine.hide_viewport = True

bb = [island_mesh.matrix_world @ Vector(c) for c in island_mesh.bound_box]
report = {
    "map": MAP,
    "island_mesh": {"name": island_mesh.name, "triangles": L.tri_count(island_mesh),
                    "vertices": len(island_mesh.data.vertices),
                    "extent_studs": [round(max(v[i] for v in bb) - min(v[i] for v in bb), 2) for i in range(3)],
                    "atlas": f"textures/{STEM}-island-atlas.png"},
    "instances": {"SnowPine_Master": len(trees)},
    "instance_triangles": {"SnowPine_Master": L.tri_count(snowpine)},
    "instance_atlas": {"SnowPine_Master": f"textures/{STEM}-snowpine-atlas.png"},
    "snowpine_source": "blender-master-evergreen/Evergreen_Master.glb + procedural snow caps (baked)",
}
report["total_triangles"] = (report["island_mesh"]["triangles"]
                             + len(trees) * report["instance_triangles"]["SnowPine_Master"])
(HERE / f"{STEM}-report.json").write_text(json.dumps(report, indent=2))

for im in bpy.data.images:
    if im.source in {"FILE", "GENERATED"} and im.has_data:
        try:
            im.pack()
        except RuntimeError:
            pass
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(HERE / f"{STEM}-mini-island.blend"))
print("ISLAND_READY", json.dumps(report), flush=True)
