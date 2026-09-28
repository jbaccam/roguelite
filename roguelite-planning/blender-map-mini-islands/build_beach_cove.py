"""Beach Cove mini island for the map-select background.

blender --background --factory-startup --python build_beach_cove.py

A small floating island that condenses the Beach Cove arena: pale warm sand
with light grass patches, grey grass-capped sea-stack cliffs with hanging vines
around the back, the beach kit's own palms, driftwood, wrecked rowboat and tide
pools, plus procedural posts, scallop shells, starfish and low grey stones. A
small turquoise shore spills over the front-right lip. Underneath is the same
faceted grey rock body as the other islands, with a wet-sand band.
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

MAP = "BeachCove"
STEM = "beachcove"
SEED = 23
RADIUS = 30.0
DEPTH = 26.0
KIT = HERE.parent / "blender-beach-cove-kit" / "exports" / "glb"

OUT_TEX = HERE / "textures"
OUT_PREV = HERE / "previews"
OUT_FBX = HERE / "exports" / "fbx"
OUT_GLB = HERE / "exports" / "glb"
for d in (OUT_TEX, OUT_PREV, OUT_FBX, OUT_GLB):
    d.mkdir(parents=True, exist_ok=True)

rng = random.Random(SEED)
scene = L.reset_scene()
PROPS = L.collection(f"{MAP}_Procedural")
MASTERS = L.collection(f"{MAP}_Masters")

# ---------------------------------------------------------------------------
# palette (from map-concepts/beach-cove.png, pushed slightly brighter because
# the game runs +0.3 saturation colour correction)
# ---------------------------------------------------------------------------
SAND = L.paint_mat("BC_Sand", [(0.2, "#d8b477"), (0.44, "#e6c98c"), (0.66, "#f0d9a2"), (0.88, "#f7e7bd")],
                   blob=7.0, jitter=0.5, facing=0.3)
WETSAND = L.paint_mat("BC_WetSand", [(0.0, "#7d5f40"), (0.5, "#9c7852"), (1.0, "#b89267")], blob=3.0, jitter=0.3)
ROCK = L.paint_mat("BC_Rock", [(0.08, "#4a5364"), (0.36, "#6f7884"), (0.62, "#959a9f"), (0.9, "#b5ae9c")],
                   blob=5.0, jitter=0.32, facing=0.75)
CLIFF = L.paint_mat("BC_Cliff", [(0.08, "#4c4f58"), (0.34, "#6a6c72"), (0.6, "#8b8b8a"), (0.9, "#aba594")],
                    blob=4.0, jitter=0.34, facing=0.7)
GRASS = L.paint_mat("BC_GrassCap", [(0.2, "#4f8a2c"), (0.45, "#6caa38"), (0.7, "#8cc248"), (0.9, "#a6d35c")],
                    blob=4.0, jitter=0.5, facing=0.3)
VINE = L.paint_mat("BC_Vine", [(0.0, "#3a7428"), (1.0, "#5c9c36")], blob=1.5, jitter=0.3, facing=0.3)
PATCH = L.paint_mat("BC_GrassPatch", [(0.0, "#96b659"), (0.55, "#aac66a"), (1.0, "#bfd57f")],
                    blob=2.5, jitter=0.45, facing=0.1)
WOOD = L.paint_mat("BC_Driftwood", [(0.0, "#6b5038"), (0.5, "#8c6c4c"), (1.0, "#a98a66")],
                   blob=1.2, jitter=0.35, facing=0.4)
SHELL = L.paint_mat("BC_Shell", [(0.0, "#e4c3ad"), (0.6, "#f2dcc6"), (1.0, "#fbeedd")], blob=0.5, jitter=0.2, facing=0.5)
STAR = L.paint_mat("BC_Starfish", [(0.0, "#dd6526"), (1.0, "#f6983f")], blob=0.5, jitter=0.25, facing=0.5)
WATER = L.paint_mat("BC_Water", [(0.0, "#27a9c0"), (0.5, "#43c6cf"), (1.0, "#86e3dc")], blob=3.0, jitter=0.45,
                    facing=0.15, rough=0.4)
FOAM = L.paint_mat("BC_Foam", [(0.0, "#e3f3f1"), (1.0, "#ffffff")], blob=1.0, jitter=0.2, facing=0.2)
SANDDRIP = L.paint_mat("BC_SandDrip", [(0.0, "#c9a46e"), (1.0, "#e0c08a")], blob=2.0, jitter=0.25, facing=0.3)

MATS = [ROCK, CLIFF, GRASS, VINE, PATCH, WOOD, SHELL, STAR, WATER, FOAM, SANDDRIP]
(I_ROCK, I_CLIFF, I_GRASS, I_VINE, I_PATCH, I_WOOD, I_SHELL, I_STAR, I_WATER, I_FOAM,
 I_SANDDRIP) = range(len(MATS))

# ---------------------------------------------------------------------------
# island body (no library drips: beach drips are placed per sector below)
# ---------------------------------------------------------------------------
LIP = 1.4
island, R = L.island_body(f"{MAP}_Body", RADIUS, DEPTH, SEED, SAND, WETSAND, ROCK, col=PROPS,
                          drip_mat=None, drips=0, spires=7, top_bumps=0.12, lip=LIP)
bpy.context.view_layer.update()


def polar(theta_deg, frac):
    th = math.radians(theta_deg)
    r = R(th) * frac
    return math.cos(th) * r, math.sin(th) * r


def ground(x, y):
    return L.top_height(island, x, y)


made = []

# ---------------------------------------------------------------------------
# shore sector (front-right): turquoise shallows spilling over the lip
# ---------------------------------------------------------------------------
SHORE = (284.0, 322.0)


def shore_sheet(name):
    bm = bmesh.new()
    nth, nfr = 16, 5
    grid = []
    for i in range(nth + 1):
        t = i / nth
        th = SHORE[0] + (SHORE[1] - SHORE[0]) * t
        # inner edge wobbles and tapers toward both ends of the sector
        taper = math.sin(math.pi * t) ** 0.6
        inner = 1.0 - (0.06 + 0.13 * taper + 0.025 * math.sin(t * 17.0))
        row = []
        for j in range(nfr + 1):
            fr = inner + (1.004 - inner) * (j / nfr)
            x, y = polar(th, fr)
            row.append(bm.verts.new((x, y, ground(x, y) + 0.09)))
        grid.append(row)
    for i in range(nth):
        for j in range(nfr):
            bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1])).material_index = I_WATER
    # foam line along the inner (beach-side) edge
    foam = []
    for i in range(nth + 1):
        a = grid[i][0].co.copy()
        b = grid[i][1].co.copy()
        inward = (a - b).normalized()
        foam.append((a - inward * 0.15, a + inward * 0.55))
    fv = []
    for p0, p1 in foam:
        v0 = bm.verts.new(p0)
        v1 = bm.verts.new(p1)
        v0.co.z = ground(p0.x, p0.y) + 0.12
        v1.co.z = ground(p1.x, p1.y) + 0.12
        fv.append((v0, v1))
    for i in range(nth):
        bm.faces.new((fv[i][0], fv[i + 1][0], fv[i + 1][1], fv[i][1])).material_index = I_FOAM
    bm.normal_update()
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    return L.bm_to_obj(name, bm, MATS, PROPS)


made.append(shore_sheet(f"{MAP}_Shore"))


def edge_drips(name, specs):
    """Flattened downward cones hugging the edge band (copied from island_body).
    specs: (theta_rad, length, width, mat_index)."""
    bm = bmesh.new()
    for th, Ld, w, mi in specs:
        r = R(th) * 1.01
        m = (Matrix.Translation((math.cos(th) * r, math.sin(th) * r, -LIP * 0.3 - Ld / 2))
             @ Matrix.Rotation(th, 4, "Z")
             @ Matrix.Rotation(math.pi, 4, "X")
             @ Matrix.Diagonal((0.45, 1.0, 1.0, 1.0)))
        geom = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=True, segments=4,
                                     radius1=w, radius2=0.0, depth=Ld, matrix=m)
        for f in {f for v in geom["verts"] for f in v.link_faces}:
            f.material_index = mi
    bm.normal_update()
    return L.bm_to_obj(name, bm, MATS, PROPS)


drip_specs = []
n_drips = 24
for s in range(n_drips):
    deg = 360.0 * (s + rng.uniform(-0.3, 0.3)) / n_drips
    if SHORE[0] - 4 < deg % 360 < SHORE[1] + 4:
        continue
    # mossy drips under the grassy cliff arc, sand drips elsewhere
    mi = I_VINE if 15 < deg < 195 else I_SANDDRIP
    drip_specs.append((math.radians(deg), rng.uniform(1.2, 2.6), rng.uniform(0.9, 1.6), mi))
made.append(edge_drips(f"{MAP}_EdgeDrips", drip_specs))


def shore_spill(name):
    """Foam rim where the shallows meet the lip, plus one narrow waterfall that
    rolls over the edge band and thins into a couple of drip tips."""
    bm = bmesh.new()
    band_bottom = -LIP - 1.6
    # foam rim hugging the rolled lip across the whole shore sector
    a0, a1 = SHORE[0] + 1.5, SHORE[1] - 1.5
    n = 16
    rim = []
    for i in range(n + 1):
        th = math.radians(a0 + (a1 - a0) * i / n)
        c, s_ = math.cos(th), math.sin(th)
        x, y = c * R(th) * 0.99, s_ * R(th) * 0.99
        z0 = ground(x, y) + 0.12
        rim.append([bm.verts.new((c * R(th) * f, s_ * R(th) * f, z)) for f, z in
                    ((0.985, z0), (1.006, z0 - 0.05), (1.02, -LIP * 0.42))])
    for i in range(n):
        for j in range(2):
            bm.faces.new((rim[i][j], rim[i][j + 1], rim[i + 1][j + 1], rim[i + 1][j])).material_index = I_FOAM
    # the fall: centred in the sector, ~11 degrees wide at the top, tapering
    mid_deg, half = (SHORE[0] + SHORE[1]) / 2 + 2, 5.5
    rows = [(1.02, -LIP * 0.42, 1.0), (1.03, band_bottom * 0.55, 0.95), (1.034, band_bottom - 0.3, 0.85),
            (1.03, band_bottom - 2.2, 0.62), (1.024, band_bottom - 4.0, 0.38)]
    m = 8
    grid = []
    for (f, z, wscale) in rows:
        row = []
        for i in range(m + 1):
            u = -1 + 2 * i / m
            th = math.radians(mid_deg + u * half * wscale)
            zz = z - (0.5 * abs(math.sin(i * 1.7)) if z < band_bottom else 0.0)
            row.append(bm.verts.new((math.cos(th) * R(th) * f, math.sin(th) * R(th) * f, zz)))
        grid.append(row)
    for j in range(len(rows) - 1):
        for i in range(m):
            bm.faces.new((grid[j][i], grid[j + 1][i], grid[j + 1][i + 1], grid[j][i + 1])).material_index = I_WATER
    # drip tips off the bottom edge
    last = grid[-1]
    for i in (1, 4, 7):
        tip = (last[i].co + last[i + 1].co) / 2
        tip = tip * 1.0
        tip.z -= 1.4 + 0.5 * (i % 2)
        tv = bm.verts.new(tip)
        bm.faces.new((last[i], tv, last[i + 1])).material_index = I_WATER
    bm.normal_update()
    for f in bm.faces:
        cen = f.calc_center_median()
        out = Vector((cen.x, cen.y, 0)).normalized() + Vector((0, 0, 0.3))
        if f.normal.dot(out) < 0:
            f.normal_flip()
    return L.bm_to_obj(name, bm, MATS, PROPS)


made.append(shore_spill(f"{MAP}_ShoreSpill"))

# ---------------------------------------------------------------------------
# sea-stack cliffs on the back arc, grass-capped, with hanging vines
# ---------------------------------------------------------------------------
CLIFF_MATS = [CLIFF, GRASS]  # cliff_block caps with index 1


def remap_slots(obj, mapping):
    """Swap a 2-slot object onto the shared MATS slot order, keeping per-face picks."""
    idx = [mapping[p.material_index] for p in obj.data.polygons]
    obj.data.materials.clear()
    for m in MATS:
        obj.data.materials.append(m)
    obj.data.polygons.foreach_set("material_index", idx)
    obj.data.update()


def cliff(name, th, fr, w, d, h, seed, yaw_jit=10):
    x, y = polar(th, fr)
    z = ground(x, y) - 0.6
    rot = math.radians(th + 90 + rng.uniform(-yaw_jit, yaw_jit))
    b = L.cliff_block(name, w, d, h, seed=seed, mats=CLIFF_MATS, cap_index=1,
                      loc=(x, y, z), rot_z=rot, col=PROPS, taper=0.86)
    # remap to the shared slot order (CLIFF -> I_CLIFF, GRASS -> I_GRASS)
    remap_slots(b, {0: I_CLIFF, 1: I_GRASS})
    return b, (x, y, z, h, rot)


def vines_on(block, info, count, seed):
    """Hang thin vine strips down the island-facing side of a cliff block."""
    r2 = random.Random(seed)
    x, y, z, h, rot = info
    inward = Vector((-x, -y, 0)).normalized()
    side = Vector((-inward.y, inward.x, 0))
    bm = bmesh.new()
    for i in range(count):
        lat = r2.uniform(-0.35, 0.35) * 5.0
        Lv = r2.uniform(0.28, 0.6) * h
        zt = z + h * 0.94
        zb = zt - Lv
        o = Vector((x, y, 0)) + side * lat
        hits = []
        for zz in (zt, zb):
            orig = o + inward * 20 + Vector((0, 0, zz))
            hit, loc, nrm, _ = block.ray_cast(orig, -inward)
            if not hit:
                break
            hits.append((loc, nrm))
        if len(hits) < 2:
            continue
        (pt, nt), (pb, nb) = hits
        n = (nt + nb).normalized()
        axis = (pb - pt).normalized()
        xa = (n - axis * n.dot(axis)).normalized()
        ya = axis.cross(xa)
        rotm = Matrix((xa, ya, axis)).transposed().to_4x4()
        mid = (pt + pb) / 2 + n * 0.22
        w = r2.uniform(0.7, 1.05)
        # a vine curtain: one wide strip plus a thinner trailing strand beside it
        for (off, ww, ll) in ((0.0, w, 1.0), (w * 1.1, w * 0.55, r2.uniform(0.55, 0.8))):
            p_top = pt + ya * off
            p_bot = pt + ya * off + (pb - pt) * ll
            mid = (p_top + p_bot) / 2 + n * 0.2
            m = Matrix.Translation(mid) @ rotm @ Matrix.Diagonal((0.28, 1.0, 1.0, 1.0))
            geom = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=True, segments=4,
                                         radius1=ww, radius2=0.08, depth=(p_bot - p_top).length, matrix=m)
            for f in {f for v in geom["verts"] for f in v.link_faces}:
                f.material_index = I_VINE
    bm.normal_update()
    if not bm.faces:
        bm.free()
        return None
    return L.bm_to_obj(block.name + "_Vines", bm, MATS, PROPS)


cliff_tops = {}
# (key, theta, frac, w, d, h, vines)
CLIFFS = [
    ("R1", 28, 0.86, 6.8, 5.8, 8.0, 2), ("R2", 43, 0.88, 6.5, 6.0, 11.5, 3), ("R3", 58, 0.85, 5.8, 5.4, 7.2, 2),
    ("C1", 76, 0.86, 7.4, 6.4, 12.5, 3), ("C2", 92, 0.89, 7.2, 6.2, 15.0, 3), ("C3", 107, 0.86, 7.0, 6.2, 11.0, 3),
    ("L1", 124, 0.86, 6.4, 5.8, 8.6, 2), ("L2", 139, 0.87, 7.4, 6.4, 12.8, 3), ("L3", 155, 0.85, 6.0, 5.4, 7.8, 2),
]
blocks = {}
for k, (key, th, fr, w, d, h, nv) in enumerate(CLIFFS):
    b, info = cliff(f"{MAP}_Cliff_{key}", th + rng.uniform(-2, 2), fr, w, d, h + rng.uniform(-0.6, 0.6), SEED + k)
    made.append(b)
    blocks[key] = (b, info)
    bpy.context.view_layer.update()
    v = vines_on(b, info, nv, SEED + 500 + k)
    if v:
        made.append(v)
# lower steps in front of the wall
for k, (th, fr, w, d, h) in enumerate([(38, 0.72, 5.0, 4.2, 3.6), (84, 0.73, 5.6, 4.4, 4.6),
                                       (116, 0.72, 4.8, 4.0, 3.4), (146, 0.72, 5.2, 4.2, 4.0)]):
    b, info = cliff(f"{MAP}_CliffStep_{k}", th, fr, w, d, h, SEED + 40 + k, yaw_jit=20)
    made.append(b)
    blocks[f"S{k}"] = (b, info)
# side outcrops (left and right shoulders of the cove)
for k, (key, th, fr, w, d, h) in enumerate([("OL1", 183, 0.87, 6.2, 5.2, 6.0), ("OL2", 200, 0.88, 4.8, 4.4, 3.8),
                                            ("OR1", 352, 0.87, 6.0, 5.0, 6.6), ("OR2", 8, 0.86, 5.2, 4.6, 4.4)]):
    b, info = cliff(f"{MAP}_Outcrop_{key}", th, fr, w, d, h, SEED + 70 + k)
    made.append(b)
    blocks[key] = (b, info)
    bpy.context.view_layer.update()
    if h > 5:
        v = vines_on(b, info, 1, SEED + 600 + k)
        if v:
            made.append(v)

# ---------------------------------------------------------------------------
# rocks: chunky front-rim boulders + low flat grey stones on the sand
# ---------------------------------------------------------------------------
ROCK_MATS = [ROCK, GRASS]


def boulder(name, th, fr, s, seed, cap=False, flat=0.7):
    x, y = polar(th, fr)
    o = L.rock(name, (s * 1.3, s, s * flat), seed=seed, mats=ROCK_MATS, cap_index=1 if cap else None,
               loc=(x, y, ground(x, y)), rot_z=rng.uniform(0, 6.28), col=PROPS)
    remap_slots(o, {0: I_ROCK, 1: I_GRASS})
    return o


rim_rocks = {}
for k, (th, fr, s, cap) in enumerate([(236, 0.93, 4.8, True), (258, 0.95, 3.2, False), (214, 0.93, 3.4, False),
                                      (334, 0.93, 4.4, False), (278, 0.96, 2.4, False)]):
    rim_rocks[k] = boulder(f"{MAP}_RimRock_{k}", th, fr, s, SEED + 100 + k, cap)
    made.append(rim_rocks[k])
flat_rocks = {}
for k, (th, fr, s) in enumerate([(100, 0.50, 3.0), (302, 0.50, 2.6), (182, 0.46, 1.5), (22, 0.44, 1.6),
                                 (62, 0.62, 1.2), (262, 0.22, 1.1), (336, 0.30, 1.0), (205, 0.66, 1.0),
                                 (150, 0.58, 1.3), (270, 0.62, 0.9)]):
    flat_rocks[k] = boulder(f"{MAP}_Stone_{k:02d}", th, fr, s, SEED + 140 + k, flat=0.42)
    made.append(flat_rocks[k])

# ---------------------------------------------------------------------------
# grass patches, tufts
# ---------------------------------------------------------------------------


def flat_patch(name, loc, rx, ry, seed, mi, lobes=3, lift=0.07):
    r2 = random.Random(seed)
    bm = bmesh.new()
    for li in range(lobes):
        segs = 12
        ox = r2.uniform(-rx, rx) * 0.55 if li else 0
        oy = r2.uniform(-ry, ry) * 0.55 if li else 0
        s = 1.0 if li == 0 else r2.uniform(0.5, 0.75)
        z = lift + 0.012 * li
        c = bm.verts.new((ox, oy, z))
        ring = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            kk = 1 + 0.2 * math.sin(a * 3 + seed + li) + 0.1 * math.cos(a * 5 + seed * 2)
            ring.append(bm.verts.new((ox + math.cos(a) * rx * s * kk, oy + math.sin(a) * ry * s * kk, z)))
        for i in range(segs):
            bm.faces.new((c, ring[i], ring[(i + 1) % segs])).material_index = mi
    L.transform_bm(bm, loc=loc, rot_z=r2.uniform(0, 6.28))
    obj = L.bm_to_obj(name, bm, MATS, PROPS)
    for v in obj.data.vertices:
        base = v.co.z - loc[2]
        v.co.z = ground(v.co.x, v.co.y) + base
    return obj


PATCHES = [(62, 0.70, 3.2, 2.2), (98, 0.70, 3.8, 2.4), (132, 0.70, 3.0, 2.0), (172, 0.62, 3.0, 2.2),
           (18, 0.64, 3.0, 2.0), (228, 0.62, 2.6, 1.8), (250, 0.80, 3.4, 2.2), (318, 0.56, 2.6, 1.8),
           (150, 0.34, 2.0, 1.5), (40, 0.30, 1.8, 1.4), (345, 0.70, 2.4, 1.8)]
patch_pts = []
for k, (th, fr, rx, ry) in enumerate(PATCHES):
    x, y = polar(th, fr)
    made.append(flat_patch(f"{MAP}_GrassPatch_{k:02d}", (x, y, 0), rx, ry, SEED + 300 + k, I_PATCH))
    patch_pts.append((x, y, rx))


def tufts(name, pts, seed):
    r2 = random.Random(seed)
    bm = bmesh.new()
    for (x, y) in pts:
        z = ground(x, y)
        for i in range(3):
            a = r2.uniform(0, 6.28)
            m = L.trs((x + math.cos(a) * 0.25, y + math.sin(a) * 0.25, z - 0.05),
                      (r2.uniform(-0.35, 0.35), r2.uniform(-0.35, 0.35), a))
            L.cyl_bm(bm, 0.2, 0.0, r2.uniform(0.7, 1.1), segs=3, matrix=m, mat_index=I_VINE, cap_tris=True)
    return L.bm_to_obj(name, bm, MATS, PROPS)


tuft_pts = []
for (x, y, rx) in patch_pts:
    for _ in range(2):
        a = rng.uniform(0, 6.28)
        tuft_pts.append((x + math.cos(a) * rx * 0.6, y + math.sin(a) * rx * 0.6))
made.append(tufts(f"{MAP}_Tufts", tuft_pts, SEED + 350))

# ---------------------------------------------------------------------------
# posts, shells, starfish
# ---------------------------------------------------------------------------


def posts(name, spots, seed):
    r2 = random.Random(seed)
    bm = bmesh.new()
    for (th, fr, h) in spots:
        x, y = polar(th, fr)
        m = L.trs((x, y, ground(x, y) - 0.4), (r2.uniform(-0.18, 0.18), r2.uniform(-0.18, 0.18), r2.uniform(0, 6)))
        faces = L.cyl_bm(bm, 0.36, 0.3, h + 0.4, segs=6, matrix=m, mat_index=I_WOOD, jitter=0.04, seed=int(th))
    bm.normal_update()
    return L.bm_to_obj(name, bm, MATS, PROPS)


made.append(posts(f"{MAP}_Posts", [(160, 0.74, 2.6), (164, 0.77, 1.9), (168, 0.73, 2.2),
                                   (312, 0.82, 2.4), (318, 0.80, 1.7), (22, 0.76, 2.0)], SEED + 400))


def scallop(bm, loc, rot_z, s):
    """Fan-shaped scallop shell: domed ribbed fan with a small hinge."""
    tmp = bmesh.new()
    arc = []
    n = 9
    for i in range(n):
        a = math.radians(15 + 150 * i / (n - 1))
        rr = s * (1.0 if i % 2 == 0 else 0.88)
        # alternating rib heights so the fan reads as a ribbed scallop
        arc.append(tmp.verts.new((math.cos(a) * rr, math.sin(a) * rr, 0.03 if i % 2 else 0.14 * s)))
    top = tmp.verts.new((0, s * 0.4, s * 0.36))
    hinge = tmp.verts.new((0, -s * 0.05, 0.05))
    for i in range(n - 1):
        tmp.faces.new((top, arc[i], arc[i + 1]))
    tmp.faces.new((hinge, arc[0], top))
    tmp.faces.new((hinge, top, arc[-1]))
    # hinge ears
    e = [tmp.verts.new(p) for p in ((-s * 0.3, -s * 0.12, 0.03), (s * 0.3, -s * 0.12, 0.03), (0, s * 0.1, s * 0.16))]
    tmp.faces.new(e)
    bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces)
    for f in tmp.faces:
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
    L.transform_bm(tmp, loc=loc, rot_z=rot_z)
    L.merge_bm(bm, tmp, I_SHELL)


def starfish(bm, loc, rot_z, s):
    tmp = bmesh.new()
    ring = []
    for i in range(10):
        a = 2 * math.pi * i / 10 + math.pi / 2
        rr = s if i % 2 == 0 else s * 0.42
        ring.append(tmp.verts.new((math.cos(a) * rr, math.sin(a) * rr, 0.04 if i % 2 == 0 else 0.1)))
    top = tmp.verts.new((0, 0, s * 0.28))
    bot = tmp.verts.new((0, 0, 0.0))
    for i in range(10):
        tmp.faces.new((top, ring[i], ring[(i + 1) % 10]))
        tmp.faces.new((bot, ring[(i + 1) % 10], ring[i]))
    bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces)
    L.transform_bm(tmp, loc=loc, rot_z=rot_z)
    L.merge_bm(bm, tmp, I_STAR)


bm = bmesh.new()
for (th, fr, s) in [(254, 0.70, 1.05), (286, 0.46, 0.95), (198, 0.55, 1.0), (330, 0.64, 1.0), (118, 0.60, 0.9),
                    (40, 0.52, 0.9), (242, 0.40, 0.9)]:
    x, y = polar(th, fr)
    scallop(bm, (x, y, ground(x, y) - 0.02), rng.uniform(0, 6.28), s * 1.2)
for (th, fr, s) in [(268, 0.56, 1.1), (222, 0.48, 1.0), (70, 0.56, 0.95), (296, 0.72, 1.0)]:
    x, y = polar(th, fr)
    starfish(bm, (x, y, ground(x, y) + 0.02), rng.uniform(0, 6.28), s)
# a starfish resting on the big front-right flat stone and one on a rim rock
for obj, s in ((flat_rocks[1], 1.0), (rim_rocks[0], 1.1)):
    bpy.context.view_layer.update()
    c = obj.location + Vector(obj.bound_box[0]).lerp(Vector(obj.bound_box[6]), 0.5)
    tz = L.top_height(obj, c.x, c.y)
    starfish(bm, (c.x, c.y, tz - 0.05), rng.uniform(0, 6.28), s)
made.append(L.bm_to_obj(f"{MAP}_ShellsStarfish", bm, MATS, PROPS))

# ---------------------------------------------------------------------------
# beach-kit masters: palms, driftwood, rowboat, tide pools (instanced)
# ---------------------------------------------------------------------------
masters = {
    "PalmTall": L.import_master(KIT / "16-palm-tall.glb", "BC_PalmTall_Master"),
    "PalmLean": L.import_master(KIT / "17-palm-leaning.glb", "BC_PalmLeaning_Master"),
    "PalmShort": L.import_master(KIT / "18-palm-short.glb", "BC_PalmShort_Master"),
    "Log": L.import_master(KIT / "19-driftwood-log.glb", "BC_DriftwoodLog_Master"),
    "Planks": L.import_master(KIT / "20-driftwood-planks.glb", "BC_DriftwoodPlanks_Master"),
    "Boat": L.import_master(KIT / "21-wrecked-rowboat.glb", "BC_WreckedRowboat_Master"),
    "PoolSmall": L.import_master(KIT / "22-tide-pool-small.glb", "BC_TidePoolSmall_Master"),
    "PoolLarge": L.import_master(KIT / "23-tide-pool-large.glb", "BC_TidePoolLarge_Master"),
}
GLB_FILES = {"PalmTall": "16-palm-tall.glb", "PalmLean": "17-palm-leaning.glb", "PalmShort": "18-palm-short.glb",
             "Log": "19-driftwood-log.glb", "Planks": "20-driftwood-planks.glb", "Boat": "21-wrecked-rowboat.glb",
             "PoolSmall": "22-tide-pool-small.glb", "PoolLarge": "23-tide-pool-large.glb"}
bpy.context.view_layer.update()


def lean_angle(master):
    """Horizontal direction (radians) the crown leans toward, from the master mesh."""
    vs = [v.co for v in master.data.vertices]
    zmax = max(v.z for v in vs)
    top = [v for v in vs if v.z > zmax * 0.75]
    cx = sum(v.x for v in top) / len(top)
    cy = sum(v.y for v in top) / len(top)
    return math.atan2(cy, cx)


LEAN = lean_angle(masters["PalmLean"])
instances = []
scales = {}


def place(kind, name, loc, rot_z, s, tilt=(0.0, 0.0)):
    o = L.place_instance(masters[kind], name, loc, rot_z, s, MASTERS, tilt)
    instances.append((kind, o))
    scales.setdefault(kind, set()).add(round(s, 3))
    return o


# palms on the cliff tops
for k, (key, kind, s) in enumerate([("R2", "PalmTall", 0.50), ("C2", "PalmShort", 0.62), ("L2", "PalmTall", 0.52),
                                    ("C3", "PalmShort", 0.55), ("OR1", "PalmShort", 0.58)]):
    b, (x, y, z, h, rot) = blocks[key]
    tz = L.top_height(b, x, y)
    place(kind, f"{MAP}_Palm_Cliff_{key}", (x, y, tz - 0.3), rng.uniform(0, 6.28), s)
# palms on the rim and sides; leaning ones lean outward, away from the cove
for k, (th, fr, kind, s) in enumerate([(66, 0.97, "PalmTall", 0.58), (116, 0.97, "PalmLean", 0.62),
                                       (176, 0.76, "PalmLean", 0.64), (205, 0.76, "PalmShort", 0.62),
                                       (226, 0.82, "PalmLean", 0.62), (14, 0.74, "PalmTall", 0.56),
                                       (340, 0.76, "PalmShort", 0.6)]):
    x, y = polar(th, fr)
    rz = (math.radians(th) - LEAN) if kind == "PalmLean" else rng.uniform(0, 6.28)
    place(kind, f"{MAP}_Palm_{k:02d}", (x, y, ground(x, y) - 0.3), rz, s)

# driftwood, rowboat


def place_ground(kind, name, th, fr, yaw_deg, s, sink=0.1, tilt=(0.0, 0.0)):
    x, y = polar(th, fr)
    return place(kind, name, (x, y, ground(x, y) - sink), math.radians(yaw_deg), s, tilt)


place_ground("Log", f"{MAP}_DriftLog_0", 252, 0.60, 28, 0.45)
place_ground("Log", f"{MAP}_DriftLog_1", 30, 0.56, -60, 0.4)
place_ground("Planks", f"{MAP}_DriftPlanks_0", 214, 0.60, 70, 0.5)
place_ground("Planks", f"{MAP}_DriftPlanks_1", 128, 0.52, -20, 0.42)
place_ground("Boat", f"{MAP}_Rowboat", 308, 0.66, 300 - 90 + 25, 0.58, sink=0.25, tilt=(0.0, math.radians(8)))

# tide pools, sat on the average sand height of their footprint, with rocks in them


def place_pool(kind, name, th, fr, yaw_deg, s, rocks):
    x, y = polar(th, fr)
    m = masters[kind]
    bb = [Vector(c) for c in m.bound_box]
    hx = (max(v.x for v in bb) - min(v.x for v in bb)) * s * 0.4
    hy = (max(v.y for v in bb) - min(v.y for v in bb)) * s * 0.4
    yaw = math.radians(yaw_deg)
    zs = []
    for u in (-1, 0, 1):
        for v in (-1, 0, 1):
            px = x + u * hx * math.cos(yaw) - v * hy * math.sin(yaw)
            py = y + u * hx * math.sin(yaw) + v * hy * math.cos(yaw)
            zs.append(ground(px, py))
    z = sum(zs) / len(zs) - 0.02
    o = place(kind, name, (x, y, z), yaw, s)
    for i, (dx, dy, rs) in enumerate(rocks):
        px = x + dx * math.cos(yaw) - dy * math.sin(yaw)
        py = y + dx * math.sin(yaw) + dy * math.cos(yaw)
        made.append(L.rock(f"{name}_Rock_{i}", (rs * 1.3, rs, rs * 0.6), seed=SEED + 700 + i + int(th),
                           mats=MATS, loc=(px, py, ground(px, py) - 0.05), rot_z=rng.uniform(0, 6.28), col=PROPS))
    return o


place_pool("PoolLarge", f"{MAP}_TidePool_0", 234, 0.36, 15, 0.68, [(-1.0, 0.3, 1.5), (1.7, -0.6, 1.1)])
place_pool("PoolSmall", f"{MAP}_TidePool_1", 72, 0.44, -25, 0.8, [(0.4, 0.1, 1.0), (-1.3, 0.4, 0.7)])
place_pool("PoolSmall", f"{MAP}_TidePool_2", 352, 0.44, 40, 0.7, [(0.2, 0.0, 0.9)])

# ---------------------------------------------------------------------------
# join + bake the procedural parts into one atlas mesh
# ---------------------------------------------------------------------------
island_mesh = L.join(f"{MAP}_Island", [island] + made, PROPS)
bpy.ops.object.select_all(action="DESELECT")
island_mesh.select_set(True)
bpy.context.view_layer.objects.active = island_mesh
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
L.bake_atlas(island_mesh, OUT_TEX / f"{STEM}-island-atlas.png", size=2048)
print("BAKED", island_mesh.name, flush=True)

# ---------------------------------------------------------------------------
# previews (same three cameras as every other island)
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
for m in masters.values():
    m.hide_viewport = False
inst_objs = [o for _, o in instances]
L.export([island_mesh] + inst_objs, OUT_FBX / f"{STEM}-mini-island.fbx", OUT_GLB / f"{STEM}-mini-island.glb")
for m in masters.values():
    m.hide_viewport = True

bb = [island_mesh.matrix_world @ Vector(c) for c in island_mesh.bound_box]
counts, tris = {}, {}
for kind, _ in instances:
    counts[kind] = counts.get(kind, 0) + 1
for kind, m in masters.items():
    tris[kind] = L.tri_count(m)
report = {
    "map": MAP,
    "island_mesh": {"name": island_mesh.name, "triangles": L.tri_count(island_mesh),
                    "vertices": len(island_mesh.data.vertices),
                    "extent_studs": [round(max(v[i] for v in bb) - min(v[i] for v in bb), 2) for i in range(3)],
                    "atlas": f"textures/{STEM}-island-atlas.png"},
    "instances": counts,
    "instance_triangles": tris,
    "instance_scales": {k: sorted(v) for k, v in scales.items()},
    "source_glbs": {k: f"blender-beach-cove-kit/exports/glb/{GLB_FILES[k]}" for k in masters},
}
report["instances_triangles_total"] = sum(counts[k] * tris[k] for k in counts)
report["total_triangles"] = report["island_mesh"]["triangles"] + report["instances_triangles_total"]
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
