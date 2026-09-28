"""Desert mini island for the map-select background.

blender --background --factory-startup --python build_desert.py

A small floating island that condenses the Desert arena: a warm golden sand
floor with soft ripples and broad darker patches, ringed by big chunky rounded
orange sandstone boulders (tall mesas at the back, low boulders at the front),
green saguaro cacti (some with pink flowers), white animal ribcages, leafless
dead trees, a leaning tan sandstone obelisk on a rubble base at the back-right,
small reddish floor rocks with tiny pink flowers, and dry grass tufts.
Underneath is a faceted orange-red sandstone body with a packed-sand band,
sand drips over the lip and hanging spires.

Everything is procedural (no desert GLB masters exist) and baked into one
atlas mesh, like Pine Valley.

Set DESERT_QUICK=1 to skip bake/export/save and render straight to the
scratch folder given by DESERT_QUICK_DIR (for fast look-dev passes).
"""
import os
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

MAP = "Desert"
STEM = "desert"
SEED = 23
RADIUS = 30.0
DEPTH = 26.0
QUICK = bool(os.environ.get("DESERT_QUICK"))

OUT_TEX = HERE / "textures"
OUT_PREV = Path(os.environ["DESERT_QUICK_DIR"]) if QUICK else HERE / "previews"
OUT_FBX = HERE / "exports" / "fbx"
OUT_GLB = HERE / "exports" / "glb"
for d in (OUT_TEX, OUT_PREV, OUT_FBX, OUT_GLB):
    d.mkdir(parents=True, exist_ok=True)

rng = random.Random(SEED)
scene = L.reset_scene()
PROPS = L.collection(f"{MAP}_Procedural")

# ---------------------------------------------------------------------------
# palette (by eye from the Desert arena screenshot, pushed a touch brighter
# because the game runs +0.3 saturation colour correction)
# ---------------------------------------------------------------------------
SAND = L.paint_mat("DS_Sand", [(0.18, "#cf9748"), (0.40, "#dfaa58"), (0.62, "#ebbb68"), (0.86, "#f5cc7e")],
                   blob=9.0, jitter=0.5, facing=0.3)
PACKED = L.paint_mat("DS_PackedSand", [(0.0, "#7a4a2e"), (0.5, "#94603a"), (1.0, "#ab7545")], blob=3.0,
                     jitter=0.3)
UNDER = L.paint_mat("DS_UnderRock", [(0.06, "#5e2e36"), (0.32, "#8c4434"), (0.60, "#b8613d"), (0.90, "#d98c58")],
                    blob=5.0, jitter=0.32, facing=0.75)
DRIP = L.paint_mat("DS_SandDrip", [(0.0, "#c98f45"), (1.0, "#e0ab58")], blob=3.0, jitter=0.2, facing=0.3)
STONE = L.paint_mat("DS_Sandstone", [(0.08, "#7e4131"), (0.34, "#a95c3b"), (0.60, "#c7794a"), (0.88, "#e09c67")],
                    blob=5.5, jitter=0.3, facing=0.75)
CACTUS = L.paint_mat("DS_Cactus", [(0.1, "#2f7a35"), (0.55, "#47993f"), (1.0, "#69b650")], blob=1.6, jitter=0.25,
                     facing=0.7)
FLOWER = L.paint_mat("DS_Flower", [(0.0, "#e0628f"), (1.0, "#f79ab8")], blob=0.5, jitter=0.2, facing=0.5)
BONE = L.paint_mat("DS_Bone", [(0.0, "#cfc5ad"), (0.55, "#ece5d3"), (1.0, "#faf6ea")], blob=1.2, jitter=0.2,
                   facing=0.6)
DEADWOOD = L.paint_mat("DS_DeadWood", [(0.0, "#5b3b2b"), (0.5, "#7e5840"), (1.0, "#9c7656")], blob=1.4,
                       jitter=0.3, facing=0.45)
OBELISK = L.paint_mat("DS_Obelisk", [(0.05, "#85592f"), (0.45, "#b8874b"), (0.85, "#d8aa68")], blob=2.5,
                      jitter=0.25, facing=0.6)
DRYGRASS = L.paint_mat("DS_DryGrass", [(0.0, "#6f7f36"), (1.0, "#9dab52")], blob=1.0, jitter=0.3, facing=0.3)
REDROCK = L.paint_mat("DS_RedRock", [(0.1, "#7a3a2e"), (0.5, "#a44f38"), (0.9, "#c9744d")], blob=1.5, jitter=0.3,
                      facing=0.7)


def add_ripples(mat, period=1.5, strength=0.03):
    """Soft wind ripples: a distorted band wave nudging the ramp coordinate."""
    nt = mat.node_tree
    ramp = next(n for n in nt.nodes if n.type == "VALTORGB")
    src = ramp.inputs["Fac"].links[0].from_socket
    coord = next(n for n in nt.nodes if n.type == "TEX_COORD")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "X"
    wave.inputs["Scale"].default_value = 2 * math.pi / (20 * period)
    wave.inputs["Distortion"].default_value = 1.0
    wave.inputs["Detail"].default_value = 0.0
    wave.inputs["Detail Scale"].default_value = 0.6
    rot = nt.nodes.new("ShaderNodeMapping")
    rot.inputs["Rotation"].default_value = (0, 0, math.radians(28))
    nt.links.new(coord.outputs["Object"], rot.inputs["Vector"])
    nt.links.new(rot.outputs["Vector"], wave.inputs["Vector"])
    sub = nt.nodes.new("ShaderNodeMath")
    sub.operation = "SUBTRACT"
    sub.inputs[1].default_value = 0.5
    nt.links.new(wave.outputs["Fac"], sub.inputs[0])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = strength * 2
    nt.links.new(sub.outputs[0], mul.inputs[0])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    add.use_clamp = True
    nt.links.new(src, add.inputs[0])
    nt.links.new(mul.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], ramp.inputs["Fac"])


add_ripples(SAND)

# material slot order shared by every prop object
MATS = [STONE, SAND, CACTUS, FLOWER, BONE, DEADWOOD, OBELISK, DRYGRASS, REDROCK]
I_STONE, I_SAND, I_CACTUS, I_FLOWER, I_BONE, I_WOOD, I_OBELISK, I_GRASS, I_RED = range(len(MATS))

# ---------------------------------------------------------------------------
# island body
# ---------------------------------------------------------------------------
island, R = L.island_body(f"{MAP}_Body", RADIUS, DEPTH, SEED, SAND, PACKED, UNDER, col=PROPS,
                          drip_mat=DRIP, drips=16, spires=7, top_bumps=0.45,
                          rim_raise=lambda th: 0.7)
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
counts = {}


def count(kind):
    counts[kind] = counts.get(kind, 0) + 1


# ---------------------------------------------------------------------------
# generic tube (cactus trunks/arms, bones, branches)
# ---------------------------------------------------------------------------
def tube(bm, pts, radii, segs=8, mat_index=0, tip="round", flute=0.0):
    """Tapered tube along a polyline. `tip` = round | point | flat. Start is capped flat."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    tans = []
    for i in range(n):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = (pts[i + 1] - pts[i]).normalized() + (pts[i] - pts[i - 1]).normalized()
        tans.append(t.normalized())
    up = Vector((0, 0, 1)) if abs(tans[0].z) < 0.9 else Vector((1, 0, 0))
    u = tans[0].cross(up).normalized()
    centres, rads, frames = list(pts), list(radii), []
    for i in range(n):
        u = (u - tans[i] * u.dot(tans[i])).normalized()
        frames.append((u.copy(), tans[i].cross(u)))
    # extra rings for a rounded end
    end_t = tans[-1]
    r_end = radii[-1]
    if tip == "round":
        for off, k in ((0.45, 0.82), (0.8, 0.45)):
            centres.append(pts[-1] + end_t * r_end * off)
            rads.append(r_end * k)
            frames.append(frames[-1])
    tmp = bmesh.new()
    rings = []
    for c, r, (uu, vv) in zip(centres, rads, frames):
        ring = []
        for s in range(segs):
            a = 2 * math.pi * s / segs
            rr = r * (1 - flute * (s % 2))
            ring.append(tmp.verts.new(c + (uu * math.cos(a) + vv * math.sin(a)) * rr))
        rings.append(ring)
    for a, b in zip(rings[:-1], rings[1:]):
        for s in range(segs):
            s2 = (s + 1) % segs
            tmp.faces.new((a[s], a[s2], b[s2], b[s]))
    # start cap
    tmp.faces.new(list(reversed(rings[0])))
    if tip == "flat":
        tmp.faces.new(rings[-1])
    else:
        off = 0.95 if tip == "round" else 1.6
        apex = tmp.verts.new(pts[-1] + end_t * r_end * off)
        last = rings[-1]
        for s in range(segs):
            tmp.faces.new((last[s], last[(s + 1) % segs], apex))
    bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces)
    return L.merge_bm(bm, tmp, mat_index)


def blob(bm, loc, r, mat_index, scale=(1, 1, 1), seed=0, subdiv=1, jit=0.1):
    tmp = bmesh.new()
    bmesh.ops.create_icosphere(tmp, subdivisions=subdiv, radius=r)
    if jit:
        L.jitter_bm(tmp, r * jit, seed, freq=2.0)
    L.transform_bm(tmp, loc=loc, scale=scale)
    return L.merge_bm(bm, tmp, mat_index)


# ---------------------------------------------------------------------------
# sandstone boulders: puffy chamfered blocks (rounded, faceted, soft edges)
# ---------------------------------------------------------------------------
def boulder_block(name, w, d, h, seed, loc, rot_z, taper=0.82, chamfer=0.2, puff=0.14, tilt=(0.0, 0.0),
                  slant=None):
    """Chunky faceted sandstone block: broad planes, soft chamfers, a slanted top."""
    r2 = random.Random(seed)
    if slant is None:
        slant = (r2.uniform(-0.22, 0.22), r2.uniform(-0.12, 0.12))
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 0.5],
                              cuts=1, use_grid_fill=True)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=chamfer, segments=1, affect="EDGES", profile=0.5,
                    clamp_overlap=True)
    for v in bm.verts:
        v.co = v.co.lerp(v.co.normalized() * 0.62, puff)
        t = v.co.z + 0.5
        k = 1.0 - (1.0 - taper) * t
        v.co.x *= k
        v.co.y *= k
        if v.co.z > 0:
            v.co.z += (slant[0] * v.co.x + slant[1] * v.co.y) * t * 2
    L.transform_bm(bm, loc=(0, 0, 0.5))
    L.transform_bm(bm, scale=(w, d, h))
    L.jitter_bm(bm, min(w, d, h) * 0.08, seed, freq=0.5)
    bm.normal_update()
    rot = Matrix.Rotation(rot_z, 4, "Z") @ Matrix.Rotation(tilt[0], 4, "X") @ Matrix.Rotation(tilt[1], 4, "Y")
    L.transform_bm(bm, loc=loc, rot=rot)
    for f in bm.faces:
        f.material_index = I_STONE
    return L.bm_to_obj(name, bm, MATS, PROPS)


# back arc: tall rounded mesas, a few stacked, with lower boulders in front
rim_tops = []
for k, th in enumerate(range(26, 160, 12)):
    mid = 1 - abs(th - 93) / 70          # tallest at the back centre
    h = 7.0 + 7.0 * max(0.0, mid) + rng.uniform(-1.4, 1.4)
    w = rng.uniform(7.0, 9.8)
    d = rng.uniform(6.0, 7.8)
    tj = th + rng.uniform(-3, 3)
    x, y = polar(tj, rng.uniform(0.81, 0.87))
    z = ground(x, y) - 0.8
    rot = math.radians(th + 90 + rng.uniform(-12, 12))
    made.append(boulder_block(f"{MAP}_Mesa_{k:02d}", w, d, h, SEED + k, (x, y, z), rot))
    count("sandstone_mesa")
    rim_tops.append((th, x, y, z + h))
    if k % 3 == 1:
        # stacked cap block, set back and narrower (double-mesa look)
        x2, y2 = polar(tj + rng.uniform(-4, 4), 0.9)
        made.append(boulder_block(f"{MAP}_MesaCap_{k:02d}", w * 0.62, d * 0.62, h * 0.38, SEED + 20 + k,
                                  (x2, y2, z + h * 0.8), rot + 0.4))
        count("sandstone_mesa")
    if k % 2 == 0:
        x2, y2 = polar(th + rng.uniform(-6, 6), 0.69)
        made.append(boulder_block(f"{MAP}_MesaStep_{k:02d}", w * 0.62, d * 0.6, h * 0.36, SEED + 40 + k,
                                  (x2, y2, ground(x2, y2) - 0.4), rot + 0.35, taper=0.78))
        count("sandstone_boulder")

# two tall flat-topped mesas behind the back rim (the arena's distant mesas)
for k, (th, h) in enumerate([(122, 16.5), (74, 15.0)]):
    x, y = polar(th, 0.93)
    made.append(boulder_block(f"{MAP}_TallMesa_{k}", 8.6, 6.6, h, SEED + 90 + k, (x, y, ground(x, y) - 1.0),
                              math.radians(th + 90), taper=0.86, puff=0.08, slant=(0.04, 0.0)))
    count("sandstone_mesa")

# sides: medium blocks
for k, (th, fr, w, d, h) in enumerate([(166, 0.86, 7.5, 6.0, 6.8), (180, 0.87, 6.5, 5.5, 5.4),
                                       (196, 0.88, 6.8, 5.5, 4.6), (210, 0.9, 5.5, 4.8, 3.6),
                                       (14, 0.86, 7.2, 6.0, 6.4), (0, 0.87, 6.5, 5.5, 5.2),
                                       (345, 0.88, 6.8, 5.5, 4.4), (331, 0.9, 5.5, 4.8, 3.4)]):
    x, y = polar(th + rng.uniform(-2, 2), fr)
    made.append(boulder_block(f"{MAP}_Side_{k:02d}", w, d, h, SEED + 60 + k, (x, y, ground(x, y) - 0.6),
                              math.radians(th + 90 + rng.uniform(-15, 15))))
    count("sandstone_boulder")

# front: low chunky boulders with gaps so the floor reads
for k, (th, fr, w, d, h) in enumerate([(224, 0.91, 6.0, 5.0, 3.8), (233, 0.95, 3.4, 3.0, 2.2),
                                       (262, 0.94, 5.0, 4.2, 2.8),
                                       (292, 0.93, 6.2, 5.0, 3.6), (301, 0.96, 3.2, 2.8, 2.0),
                                       (322, 0.92, 4.8, 4.2, 3.0)]):
    x, y = polar(th, fr)
    made.append(boulder_block(f"{MAP}_Front_{k:02d}", w, d, h, SEED + 80 + k, (x, y, ground(x, y) - 0.5),
                              math.radians(th + 90 + rng.uniform(-25, 25)), taper=0.74, puff=0.2))
    count("sandstone_boulder")

# ---------------------------------------------------------------------------
# props
# ---------------------------------------------------------------------------


def saguaro(name, loc, h, seed, rot_z=0.0, arms=2, flowers=True):
    r2 = random.Random(seed)
    bm = bmesh.new()
    r = 0.55 + 0.05 * h / 6
    lean = Vector((r2.uniform(-0.12, 0.12), r2.uniform(-0.12, 0.12), 0))
    top = h - r
    tpts = [(0, 0, -0.5), (0, 0, top * 0.3), lean * 0.5 + Vector((0, 0, top * 0.62)), lean + Vector((0, 0, top))]
    tube(bm, tpts, [r * 1.05, r, r * 0.98, r * 0.92], segs=10, mat_index=I_CACTUS, flute=0.12)
    tips = [Vector(tpts[-1]) + Vector((0, 0, r * 0.95))]
    ra = r * 0.64
    sides = [1, -1][:arms]
    for i, side in enumerate(sides):
        ha = top * (r2.uniform(0.34, 0.44) if i == 0 else r2.uniform(0.5, 0.6))
        reach = r + r2.uniform(0.7, 1.0)
        up = r2.uniform(1.3, 2.0) * (1.0 if i == 0 else 0.8)
        a = r2.uniform(-0.35, 0.35)
        ca, sa = math.cos(a), math.sin(a)

        def P(x, z):
            return Vector((x * ca * side, x * sa * side, z))
        apts = [P(0.1, ha - 0.05), P(r + 0.25, ha), P(reach - 0.15, ha + 0.12),
                P(reach, ha + 0.55), P(reach + 0.02, ha + 0.55 + up)]
        tube(bm, apts, [ra * 1.05, ra, ra, ra * 0.98, ra * 0.92], segs=8, mat_index=I_CACTUS, flute=0.1)
        tips.append(apts[-1] + Vector((0, 0, ra * 0.95)))
    if flowers:
        for j, tp in enumerate(tips):
            if j > 0 and r2.random() < 0.4:
                continue
            for q in range(2 if j == 0 else 1):
                off = Vector((r2.uniform(-0.2, 0.2), r2.uniform(-0.2, 0.2), -0.05))
                blob(bm, tp + off, 0.22, I_FLOWER, scale=(1, 1, 0.65), seed=seed + j * 5 + q, jit=0.05)
    L.transform_bm(bm, loc=loc, rot_z=rot_z)
    count("cactus")
    return L.bm_to_obj(name, bm, MATS, PROPS)


def ribcage(name, loc, yaw, length=5.0, seed=0, roll=0.0, sink=0.0):
    """Arched spine with paired curved ribs dropping into the sand on both sides."""
    r2 = random.Random(seed)
    bm = bmesh.new()
    H = length * 0.42
    half = length / 2
    spts, srad = [], []
    for i in range(9):
        t = i / 8
        x = -half + length * t
        z = H * math.sin(math.pi * (0.12 + 0.76 * t)) - 0.25
        spts.append((x, 0, z))
        srad.append(0.32 if i % 2 == 0 else 0.24)
    tube(bm, spts, srad, segs=6, mat_index=I_BONE)
    nr = 4
    W = length * 0.3
    for i in range(nr):
        t = 0.22 + 0.56 * i / (nr - 1)
        x = -half + length * t
        zt = H * math.sin(math.pi * (0.12 + 0.76 * t)) - 0.3
        k = 1.0 - 0.35 * abs(t - 0.45) / 0.33      # longer ribs in the middle
        for side in (-1, 1):
            w = W * k
            pts = [(x, side * 0.1, zt), (x + 0.1, side * w * 0.55, zt + 0.1),
                   (x + 0.2, side * w * 0.95, zt * 0.6), (x + 0.28, side * w * 1.02, zt * 0.25),
                   (x + 0.32, side * w * 0.9, -0.3)]
            tube(bm, pts, [0.26, 0.23, 0.2, 0.17, 0.14], segs=6, mat_index=I_BONE)
    # a small pelvis/skull knob at the neck end
    blob(bm, (half + 0.2, 0, 0.15), 0.55, I_BONE, scale=(1.3, 0.9, 0.7), seed=seed, jit=0.08)
    rot = Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(roll, 4, "X")
    L.transform_bm(bm, loc=(loc[0], loc[1], loc[2] - sink), rot=rot)
    count("ribcage")
    return L.bm_to_obj(name, bm, MATS, PROPS)


def dead_tree(name, loc, h, seed, rot_z=0.0):
    r2 = random.Random(seed)
    bm = bmesh.new()
    tp = [(0, 0, -0.5), (0.15, 0, h * 0.2), (0.45, 0.05, h * 0.4), (0.4, 0.0, h * 0.56)]
    tube(bm, tp, [0.95, 0.68, 0.56, 0.48], segs=8, mat_index=I_WOOD, tip="flat")
    # branch A: long crooked reach to the right
    tube(bm, [(0.38, 0, h * 0.5), (0.9, 0.1, h * 0.68), (1.5, 0.2, h * 0.78), (2.3, 0.1, h * 0.88)],
         [0.44, 0.33, 0.22, 0.12], segs=6, mat_index=I_WOOD, tip="point")
    # branch B: up and slightly back-left
    tube(bm, [(0.35, 0, h * 0.5), (0.05, 0.05, h * 0.72), (-0.25, 0.15, h * 0.9), (-0.2, 0.1, h * 1.02)],
         [0.42, 0.31, 0.2, 0.1], segs=6, mat_index=I_WOOD, tip="point")
    # twig off A
    tube(bm, [(1.2, 0.15, h * 0.74), (1.35, 0.2, h * 0.88), (1.3, 0.25, h * 0.98)], [0.12, 0.08, 0.05],
         segs=5, mat_index=I_WOOD, tip="point")
    # root flares
    for i in range(3):
        a = 2 * math.pi * i / 3 + r2.uniform(-0.3, 0.3)
        tube(bm, [(0, 0, 0.5), (math.cos(a) * 0.7, math.sin(a) * 0.7, 0.05),
                  (math.cos(a) * 1.15, math.sin(a) * 1.15, -0.2)], [0.35, 0.22, 0.1], segs=5,
             mat_index=I_WOOD, tip="point")
    L.transform_bm(bm, loc=loc, rot_z=rot_z)
    count("dead_tree")
    return L.bm_to_obj(name, bm, MATS, PROPS)


def chamfer_box(bm, size, loc, rot, mat_index, ch=0.12):
    L.box_bm(bm, size, loc=loc, rot=rot, chamfer=ch, mat_index=mat_index)


def obelisk(name, loc, h, base_w, rot_z, lean, seed):
    r2 = random.Random(seed)
    bm = bmesh.new()
    shaft = bmesh.new()
    bmesh.ops.create_cube(shaft, size=1.0)
    bmesh.ops.bevel(shaft, geom=list(shaft.edges), offset=0.08, segments=1, affect="EDGES", profile=0.5)
    top_k = 0.7
    for v in shaft.verts:
        t = v.co.z + 0.5
        k = 1 - (1 - top_k) * t
        v.co.x *= k
        v.co.y *= k
    L.transform_bm(shaft, loc=(0, 0, 0.5))
    L.transform_bm(shaft, loc=(0, 0, -1.2), scale=(base_w, base_w, h + 1.2))
    L.merge_bm(bm, shaft, I_OBELISK)
    tw = base_w * top_k
    # pyramidion
    L.cyl_bm(bm, tw * 0.74, 0.0, tw * 0.95, segs=4, cap_tris=True,
             matrix=Matrix.Translation((0, 0, h - 0.05)) @ Matrix.Rotation(math.pi / 4, 4, "Z"),
             mat_index=I_OBELISK)
    # carved collar band near the base
    zb = h * 0.14
    kb = 1 - (1 - top_k) * (zb + 1.2) / (h + 1.2)
    chamfer_box(bm, (base_w * kb + 0.22, base_w * kb + 0.22, 0.35), (0, 0, zb), None, I_OBELISK, ch=0.08)
    rot = Matrix.Rotation(rot_z, 4, "Z") @ Matrix.Rotation(lean, 4, "Y")
    L.transform_bm(bm, loc=loc, rot=rot)
    # plinth + rubble (not leaning)
    M = Matrix.Translation(Vector(loc)) @ Matrix.Rotation(rot_z, 4, "Z")
    MR = Matrix.Rotation(rot_z, 4, "Z")
    chamfer_box(bm, (base_w * 1.9, base_w * 1.8, 1.1), M @ Vector((0, 0, 0.2)),
                MR @ Matrix.Rotation(0.05, 4, "X"), I_OBELISK, ch=0.2)
    for i in range(7):
        a = 2 * math.pi * i / 7 + r2.uniform(-0.3, 0.3)
        rr = r2.uniform(base_w * 1.15, base_w * 1.9)
        s = r2.uniform(0.55, 1.1)
        chamfer_box(bm, (s * 1.2, s, s * 0.8), M @ Vector((math.cos(a) * rr, math.sin(a) * rr, s * 0.2)),
                    MR @ L.trs(rot=(r2.uniform(-0.4, 0.4), r2.uniform(-0.4, 0.4), r2.uniform(0, 3))),
                    I_OBELISK if i % 2 else I_STONE, ch=0.12)
    count("obelisk")
    return L.bm_to_obj(name, bm, MATS, PROPS)


def floor_rock(name, loc, s, seed, flowers=0):
    r2 = random.Random(seed)
    s *= 1.2
    obj = boulder_block(name, s * 1.4, s * 1.1, s * 0.62, seed, (loc[0], loc[1], loc[2] - 0.25),
                        r2.uniform(0, 6.28), taper=0.7, chamfer=0.24, puff=0.25)
    for p in obj.data.polygons:
        p.material_index = I_RED
    count("floor_rock")
    if not flowers:
        return [obj]
    bm = bmesh.new()
    for i in range(flowers):
        a = r2.uniform(0, 6.28)
        d = s * r2.uniform(0.8, 1.1)
        fx, fy = loc[0] + math.cos(a) * d, loc[1] + math.sin(a) * d
        fz = ground(fx, fy)
        # tiny green leaves + pink bloom
        for j in range(3):
            b = a + j * 2.1
            m = L.trs((fx + math.cos(b) * 0.12, fy + math.sin(b) * 0.12, fz - 0.05),
                      (r2.uniform(-0.4, 0.4), r2.uniform(-0.4, 0.4), b))
            L.cyl_bm(bm, 0.14, 0.0, 0.6, segs=3, matrix=m, mat_index=I_GRASS, cap_tris=True)
        blob(bm, (fx, fy, fz + 0.55), 0.2, I_FLOWER, scale=(1, 1, 0.7), seed=seed + i, jit=0.05)
    count("flower")
    return [obj, L.bm_to_obj(name + "_Flowers", bm, MATS, PROPS)]


def tufts(name, pts, seed):
    r2 = random.Random(seed)
    bm = bmesh.new()
    for (x, y) in pts:
        z = ground(x, y)
        for i in range(4):
            a = r2.uniform(0, 6.28)
            m = L.trs((x + math.cos(a) * 0.25, y + math.sin(a) * 0.25, z - 0.05),
                      (r2.uniform(-0.45, 0.45), r2.uniform(-0.45, 0.45), a))
            L.cyl_bm(bm, 0.16, 0.0, r2.uniform(0.7, 1.15), segs=3, matrix=m, mat_index=I_GRASS, cap_tris=True)
    return L.bm_to_obj(name, bm, MATS, PROPS)


# obelisk at the back-right, leaning to the right, in front of the mesas
ox, oy = polar(58, 0.67)
made.append(obelisk(f"{MAP}_Obelisk", (ox, oy, ground(ox, oy) - 0.3), h=12.5, base_w=3.2,
                    rot_z=math.radians(-15), lean=math.radians(13), seed=SEED + 400))

# cacti around the rim (none in the open middle, like the arena)
for k, (th, fr, h, arms, fl) in enumerate([
        (150, 0.70, 5.2, 2, True), (124, 0.66, 6.2, 2, False), (100, 0.62, 4.4, 1, True),
        (80, 0.70, 5.0, 2, False), (36, 0.70, 5.6, 2, True), (8, 0.72, 4.4, 1, False),
        (338, 0.72, 6.4, 2, True), (306, 0.80, 5.0, 2, False), (254, 0.80, 5.4, 2, True),
        (222, 0.76, 4.4, 1, False), (192, 0.72, 5.8, 2, True), (176, 0.62, 4.0, 1, False)]):
    x, y = polar(th + rng.uniform(-2, 2), fr)
    made.append(saguaro(f"{MAP}_Cactus_{k:02d}", (x, y, ground(x, y)), h, SEED + 500 + k,
                        rot_z=rng.uniform(-0.35, 0.35), arms=arms, flowers=fl))

# ribcages
for k, (th, fr, yaw, ln, roll, sink) in enumerate([
        (158, 0.60, 70, 5.2, 0.0, 0.1), (96, 0.66, 10, 4.2, 0.0, 0.15),
        (26, 0.54, 110, 5.6, 0.0, 0.1), (292, 0.64, -30, 5.0, 0.0, 0.35)]):
    x, y = polar(th, fr)
    made.append(ribcage(f"{MAP}_Ribcage_{k}", (x, y, ground(x, y)), math.radians(yaw), ln, SEED + 600 + k,
                        roll=roll, sink=sink))

# dead trees
for k, (th, fr, h, yaw) in enumerate([(204, 0.64, 6.8, 20), (352, 0.60, 6.2, 200)]):
    x, y = polar(th, fr)
    made.append(dead_tree(f"{MAP}_DeadTree_{k}", (x, y, ground(x, y)), h, SEED + 700 + k, math.radians(yaw)))

# small reddish floor rocks, some with pink flowers
for k, (th, fr, s, fl) in enumerate([(232, 0.45, 2.2, 2), (122, 0.46, 1.9, 0), (62, 0.42, 1.8, 1),
                                     (286, 0.36, 2.0, 2), (4, 0.36, 1.6, 0), (180, 0.36, 1.7, 1),
                                     (262, 0.16, 1.5, 0), (86, 0.22, 1.4, 0), (330, 0.52, 1.3, 1)]):
    x, y = polar(th, fr)
    made.extend(floor_rock(f"{MAP}_FloorRock_{k}", (x, y, ground(x, y)), s, SEED + 800 + k, flowers=fl))

tuft_pts = [polar(rng.uniform(0, 360), rng.uniform(0.15, 0.8)) for _ in range(26)]
made.append(tufts(f"{MAP}_Tufts", tuft_pts, SEED + 900))
counts["dry_grass_tufts"] = len(tuft_pts)

# ---------------------------------------------------------------------------
# join (+ bake the procedural parts into one atlas mesh)
# ---------------------------------------------------------------------------
island_mesh = L.join(f"{MAP}_Island", [island] + made, PROPS)
bpy.ops.object.select_all(action="DESELECT")
island_mesh.select_set(True)
bpy.context.view_layer.objects.active = island_mesh
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
print("TRIS", L.tri_count(island_mesh), flush=True)
if not QUICK:
    L.bake_atlas(island_mesh, OUT_TEX / f"{STEM}-island-atlas.png", size=2048)
    print("BAKED", island_mesh.name, flush=True)

# ---------------------------------------------------------------------------
# previews (same sky, sun and cameras as Pine Valley so the islands line up)
# ---------------------------------------------------------------------------
L.setup_preview()
if QUICK:
    scene.eevee.taa_render_samples = 16
hero = L.camera("Cam_Hero", (0, -118, 34), (0, 0, -7), lens=35)
L.render(hero, OUT_PREV / f"{STEM}-hero.png")
close = L.camera("Cam_Close", (-8, -58, 40), (0, 4, 1), lens=35)
L.render(close, OUT_PREV / f"{STEM}-closeup.png")
side = L.camera("Cam_Side", (112, -52, 8), (0, 0, -8), lens=35)
L.render(side, OUT_PREV / f"{STEM}-side.png")
if QUICK:
    print("QUICK_DONE", counts, flush=True)
    raise SystemExit(0)

# ---------------------------------------------------------------------------
# export + report
# ---------------------------------------------------------------------------
L.export([island_mesh], OUT_FBX / f"{STEM}-mini-island.fbx", OUT_GLB / f"{STEM}-mini-island.glb")

bb = [island_mesh.matrix_world @ Vector(c) for c in island_mesh.bound_box]
report = {
    "map": MAP,
    "island_mesh": {"name": island_mesh.name, "triangles": L.tri_count(island_mesh),
                    "vertices": len(island_mesh.data.vertices),
                    "extent_studs": [round(max(v[i] for v in bb) - min(v[i] for v in bb), 2) for i in range(3)],
                    "atlas": f"textures/{STEM}-island-atlas.png"},
    "instances": {},
    "procedural_props": counts,
}
report["total_triangles"] = report["island_mesh"]["triangles"]
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
