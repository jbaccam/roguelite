"""Armory backdrop: the 3D stage behind the lobby Armory screen.

blender --background --factory-startup --python build_armory.py

An open-front timber armory hall in the lobby's kiosk language (warm wood,
light cool-grey stone footing, slate-blue roof and cloth, restrained lime).
The avatar stands on a round stone dais in the middle; behind it hangs a big
round armory crest with a katana and a baseball bat crossed behind it, flanked
by two hanging lanterns. Side bays hold a standing weapon rack, a pegged wall
display and a shelf, with an anvil on a stump, a barrel and crates. The weapons
themselves are the game's real models, placed by ArmoryStage.luau (DISPLAY). The project's
evergreen master peeks over the roof.

Conventions (same as blender-map-mini-islands, whose island_lib is imported):
1 unit = 1 stud; the camera looks from -Y towards +Y; origin = dais top centre
(where the avatar's feet go), so the floor sits at z = -DAIS_H.

Outputs
- exports/fbx/armory-backdrop.fbx (+ exports/glb) : Armory_Room (2048 atlas),
  Armory_Props (2048 atlas), Armory_Trees (evergreen master texture),
  Armory_GlowLime / Armory_GlowWarm (flat colour, Neon in Studio)
- textures/armory-room-atlas.png, textures/armory-props-atlas.png
- previews/*.png (real Blender renders at the Studio cameras)
- armory-report.json
"""
import sys
import math
import random
import json
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector, Matrix, Euler, noise

HERE = Path(__file__).resolve().parent
KITS = HERE.parent
sys.path.insert(0, str(KITS / "blender-map-mini-islands"))
import island_lib as L  # noqa: E402

EVERGREEN_GLB = KITS / "blender-master-evergreen" / "Evergreen_Master.glb"
SEED = 7
DAIS_H = 0.9          # floor is at z = -DAIS_H
FLOOR = -DAIS_H
WALL_Y = 7.5          # front face of the back wall planks
HALF_W = 16.0         # hall half width
WALL_TOP = FLOOR + 10.0

# Studio camera presets (mirrored in ArmoryStage.luau). FOV is vertical.
CAMERAS = {
    "hero": {"eye": (0.0, -20.5, 3.3), "look": (0.0, 0.0, 2.75), "fov": 30.0},
    "upgrade": {"eye": (0.0, -8.5, 3.9), "look": (0.0, 0.0, 3.6), "fov": 30.0},
}

rng = random.Random(SEED)
L.reset_scene()
L.PAINT_MATERIALS.clear()


# ---------------------------------------------------------------------------
# materials: broad 2-4 value painterly ramps (island_lib.paint_mat)
# ---------------------------------------------------------------------------
M = {}
M["plank"] = L.paint_mat("Armory_Plank", [(0.0, "#6c472d"), (0.42, "#95653f"), (0.72, "#b27d4b"), (1.0, "#c99661")], blob=2.2, jitter=0.4)
M["dark"] = L.paint_mat("Armory_DarkWood", [(0.0, "#46301f"), (0.5, "#65432c"), (1.0, "#86593a")], blob=2.6, jitter=0.35)
M["stone"] = L.paint_mat("Armory_Stone", [(0.0, "#7c838b"), (0.4, "#9ea4a9"), (0.72, "#bdbcb6"), (1.0, "#d4cbb6")], blob=2.4, jitter=0.45)
M["plank2"] = L.paint_mat("Armory_Plank2", [(0.0, "#7a4d30"), (0.45, "#a46d42"), (0.75, "#bf8952"), (1.0, "#d6a56c")], blob=2.0, jitter=0.4)
M["slate"] = L.paint_mat("Armory_Slate", [(0.0, "#2f4866"), (0.5, "#44648a"), (1.0, "#5f82ab")], blob=2.4, jitter=0.35)
M["cream"] = L.paint_mat("Armory_Cream", [(0.0, "#c4b384"), (0.5, "#e0d2a0"), (1.0, "#f2e8c4")], blob=2.0, jitter=0.3)
M["lime"] = L.paint_mat("Armory_LimeCloth", [(0.0, "#5c9a10"), (0.5, "#7fcb17"), (1.0, "#a3ec33")], blob=2.0, jitter=0.3)
M["metal"] = L.paint_mat("Armory_Metal", [(0.0, "#2a2d32"), (0.5, "#41464d"), (1.0, "#626971")], blob=1.6, jitter=0.3, rough=0.7)
M["steel"] = L.paint_mat("Armory_Steel", [(0.0, "#8793a0"), (0.5, "#b6c0c9"), (1.0, "#e4e9ed")], blob=1.4, jitter=0.25, rough=0.55)
M["light"] = L.paint_mat("Armory_LightWood", [(0.0, "#a9794a"), (0.5, "#c79a64"), (1.0, "#e0bb85")], blob=1.6, jitter=0.3)
M["leather"] = L.paint_mat("Armory_Leather", [(0.0, "#4a2620"), (0.5, "#6b352b"), (1.0, "#8a4a39")], blob=1.4, jitter=0.3)
M["brass"] = L.paint_mat("Armory_Brass", [(0.0, "#8a6424"), (0.5, "#c0913a"), (1.0, "#e6c066")], blob=1.4, jitter=0.25, rough=0.6)
M["rope"] = L.paint_mat("Armory_Rope", [(0.0, "#8c7447"), (0.5, "#b09461"), (1.0, "#cdb482")], blob=1.2, jitter=0.25)
ORDER = ["plank", "dark", "stone", "slate", "cream", "lime", "metal", "steel", "light", "leather", "brass", "rope", "plank2"]
I = {k: i for i, k in enumerate(ORDER)}
MATS = [M[k] for k in ORDER]


def flat_mat(name, hex_, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = L.srgb(hex_)
    b.inputs["Emission Color"].default_value = L.srgb(hex_)
    b.inputs["Emission Strength"].default_value = strength
    b.inputs["Roughness"].default_value = 0.6
    return m


GLOW = {
    "lime": flat_mat("Armory_GlowLime", "#91ef14", 3.0),
    "warm": flat_mat("Armory_GlowWarm", "#ffc766", 4.0),
}

# ---------------------------------------------------------------------------
# geometry helpers (temporary bmeshes, transformed then merged)
# ---------------------------------------------------------------------------


def box_tmp(size, chamfer=0.06):
    """Box with an absolute chamfer in studs (scaled first, so plank ends stay square)."""
    tmp = bmesh.new()
    bmesh.ops.create_cube(tmp, size=1.0)
    bmesh.ops.transform(tmp, matrix=Matrix.Diagonal((*size, 1.0)), verts=tmp.verts)
    if chamfer > 0:
        bmesh.ops.bevel(tmp, geom=list(tmp.edges), offset=min(chamfer, min(size) * 0.45), segments=1,
                        affect="EDGES", profile=0.5, clamp_overlap=True)
    return tmp


def cyl_tmp(r1, r2, h, segs=10, bevel=0.0):
    """Cylinder/cone standing on z=0. `bevel` softens both rims."""
    tmp = bmesh.new()
    bmesh.ops.create_cone(tmp, cap_ends=True, cap_tris=False, segments=segs, radius1=r1, radius2=r2,
                          depth=h, matrix=Matrix.Translation((0, 0, h / 2)))
    if bevel > 0:
        rims = [e for e in tmp.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-5]
        bmesh.ops.bevel(tmp, geom=rims, offset=bevel, segments=1, affect="EDGES", profile=0.5,
                        clamp_overlap=True)
    return tmp


def prism_tmp(poly, z0, z1, bevel=0.0):
    """Extrude a 2D outline (x, y) between z0 and z1."""
    tmp = bmesh.new()
    bot = [tmp.verts.new((x, y, z0)) for x, y in poly]
    top = [tmp.verts.new((x, y, z1)) for x, y in poly]
    tmp.faces.new(list(reversed(bot)))
    tmp.faces.new(top)
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        tmp.faces.new((bot[i], bot[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces)
    if bevel > 0:
        bmesh.ops.bevel(tmp, geom=list(tmp.edges), offset=bevel, segments=1, affect="EDGES", profile=0.5,
                        clamp_overlap=True)
    return tmp


def jitter_tmp(tmp, amount, seed, freq=0.8):
    for v in tmp.verts:
        d = noise.noise_vector(v.co * freq + Vector((seed * 3.1, seed * 1.7, seed * 0.9)))
        v.co += d * amount


def put(bm, tmp, mat, loc=(0, 0, 0), rot=(0, 0, 0), jitter=0.0, seed=0, sc=1.0):
    if jitter:
        jitter_tmp(tmp, jitter, seed)
    bmesh.ops.transform(tmp, matrix=L.trs(loc, rot, (sc, sc, sc)), verts=tmp.verts)
    return L.merge_bm(bm, tmp, I[mat] if isinstance(mat, str) else mat)


def circle(r, n, start=0.0):
    return [(math.cos(start + 2 * math.pi * k / n) * r, math.sin(start + 2 * math.pi * k / n) * r) for k in range(n)]


# "Wall" items are modelled flat in XY (thickness along Z) and stood up to face
# the camera: rotate +90 deg about X, so local +Y -> world +Z, local +Z -> world -Y.
FACE_CAM = (math.pi / 2, 0, 0)


# ---------------------------------------------------------------------------
# weapon display spots
# ---------------------------------------------------------------------------
# The hall holds the game's real weapon models (RogueliteCombat.WeaponTemplates),
# placed by ArmoryStage.luau at runtime, so they always match the combat models.
# This file only builds the holders (crest post, rack, pegs, shelf, barrel, anvil).
# Blender coordinates; `dir` is where the model's long axis points (the tip, +Y,
# for normalized melee weapons), `len` the model's longest side in studs, and
# `up`/`face` optional overrides (see ArmoryStage). Written to armory-report.json
# in Studio axes: (x, y, z) -> (-x, z, y).
lean = math.radians(8)
_c42, _s42 = math.cos(math.radians(42)), math.sin(math.radians(42))


def _lean_at(x, half):
    # Base on the bottom rail, clear of the timber post at x = -6.4 (Excalibur's blade hid in it).
    return (x, 6.15 + math.sin(lean) * half, -0.2 + math.cos(lean) * half)


DISPLAY = [
    # crest: katana and baseball bat crossed behind the plaque
    {"id": "03", "at": (0.0, 6.95, 5.9), "dir": (-_s42, 0, _c42), "len": 7.4},
    {"id": "06", "at": (0.0, 6.85, 5.9), "dir": (_s42, 0, _c42), "len": 7.0},
    # left bay standing rack, leaning back into the top rail
    {"id": "32", "at": _lean_at(-7.5, 2.3), "dir": (0, math.sin(lean), math.cos(lean)), "len": 4.6},
    {"id": "30", "at": _lean_at(-8.7, 2.5), "dir": (0, math.sin(lean), math.cos(lean)), "len": 5.0},
    {"id": "26", "at": _lean_at(-9.85, 2.1), "dir": (0, math.sin(lean), math.cos(lean)), "len": 4.2},
    # right bay wall: launcher on pegs, pan hanging by its handle, boomerang on pegs
    {"id": "11", "at": (8.1, 6.75, 6.5), "dir": (1, 0, 0), "len": 4.0, "up": (0, 0, 1)},
    {"id": "01", "at": (10.9, 7.0, 5.6), "dir": (0, 0, -1), "len": 3.6},
    {"id": "12", "at": (8.1, 7.1, 3.55), "dir": (1, 0, 0), "len": 2.8, "up": (0, 0, 1)},
    # shelf
    {"id": "35", "at": (10.0, 6.9, 3.27), "dir": (0, 0, 1), "len": 1.5},
    {"id": "33", "at": (12.0, 6.8, 3.27), "dir": (1, 0, 0), "len": 1.6, "up": (0, 0, 1)},
    # barrel of spare gear, handles up
    {"id": "06", "at": (11.65, 3.25, 1.0), "dir": (0.12, -0.06, -0.99), "len": 3.8},
    {"id": "03", "at": (12.2, 3.05, 0.9), "dir": (-0.1, 0.1, -0.99), "len": 4.6},
    # Mjolnir resting on the anvil, lying flat
    {"id": "31", "at": (-12.2, 3.0, 2.03), "dir": (math.cos(math.radians(20)), math.sin(math.radians(20)), 0),
     "len": 3.0, "face": (0, 0, 1)},
]


def studio(v):
    return [round(-v[0], 3), round(v[2], 3), round(v[1], 3)]


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
ROOM = L.collection("Armory")
room = bmesh.new()
props = bmesh.new()
glow = {k: bmesh.new() for k in GLOW}

# --- floor: plank rows along X, staggered joints -----------------------------
PLANK_W = 1.15
y = -9.0
row = 0
while y < WALL_Y + 0.3:
    x = -HALF_W - rng.uniform(0, 3)
    while x < HALF_W:
        ln = rng.uniform(3.2, 6.8)
        x1 = min(x + ln, HALF_W)
        h = 0.32 + rng.uniform(-0.03, 0.03)
        put(room, box_tmp((x1 - x - 0.06, PLANK_W - 0.07, h), 0.05), rng.choice(("plank", "plank", "plank2")),
            ((x + x1) / 2, y + PLANK_W / 2, FLOOR - h / 2 + rng.uniform(-0.02, 0.02)),
            (rng.uniform(-0.01, 0.01), rng.uniform(-0.008, 0.008), rng.uniform(-0.006, 0.006)))
        x = x1
    y += PLANK_W
    row += 1

# --- round rug under the dais: slate with a cream border ----------------------
put(room, cyl_tmp(4.7, 4.7, 0.05, segs=24, bevel=0.02), "cream", (0, -0.2, FLOOR))
put(room, cyl_tmp(4.35, 4.35, 0.06, segs=24), "slate", (0, -0.2, FLOOR + 0.01))

# --- dais: flagstone ring (base tier) + solid top tier -----------------------
BASE_R_IN, BASE_R_OUT, TIER = 2.7, 3.75, DAIS_H / 2
for k in range(9):
    a0 = 2 * math.pi * k / 9 + 0.05
    a1 = 2 * math.pi * (k + 1) / 9 - 0.05
    steps = 4
    outer = [(math.cos(a0 + (a1 - a0) * s / steps) * BASE_R_OUT, math.sin(a0 + (a1 - a0) * s / steps) * BASE_R_OUT)
             for s in range(steps + 1)]
    inner = [(math.cos(a1 - (a1 - a0) * s / steps) * BASE_R_IN, math.sin(a1 - (a1 - a0) * s / steps) * BASE_R_IN)
             for s in range(steps + 1)]
    h = TIER + rng.uniform(-0.04, 0.02)
    t = prism_tmp(outer + inner, 0.0, h, 0.07)
    put(room, t, "stone", (0, 0, FLOOR + 0.03), (rng.uniform(-0.015, 0.015), rng.uniform(-0.015, 0.015), 0),
        jitter=0.04, seed=k)
top = cyl_tmp(2.95, 2.8, DAIS_H - 0.02, segs=18, bevel=0.1)
put(room, top, "stone", (0, 0, FLOOR + 0.02), jitter=0.025, seed=40)
put(room, cyl_tmp(2.25, 2.25, 0.03, segs=18), "slate", (0, 0, -0.005))
# lime glow ring on the top + rune inlays around the top tier's side
ring = bmesh.new()
n = 36
ov = [ring.verts.new((x, y, 0.02)) for x, y in circle(2.52, n)]
iv = [ring.verts.new((x, y, 0.02)) for x, y in circle(2.3, n)]
for k in range(n):
    j = (k + 1) % n
    ring.faces.new((ov[k], ov[j], iv[j], iv[k]))
bmesh.ops.recalc_face_normals(ring, faces=ring.faces)
L.merge_bm(glow["lime"], ring, 0)
for k in range(8):
    a = 2 * math.pi * k / 8 + math.pi / 8
    rune = box_tmp((0.36, 0.06, 0.16), 0.0)
    m = L.trs((math.cos(a) * 2.9, math.sin(a) * 2.9, -DAIS_H * 0.42), (0, 0, a + math.pi / 2))
    bmesh.ops.transform(rune, matrix=m, verts=rune.verts)
    L.merge_bm(glow["lime"], rune, 0)

# --- back wall: stone footing, plank infill, timber frame ---------------------
FOOT_H = 1.5
x = -HALF_W - 0.4
k = 0
while x < HALF_W + 0.4:
    w = rng.uniform(1.5, 2.6)
    h = FOOT_H + rng.uniform(-0.18, 0.14)
    # fieldstones: chunky, softly faceted, slightly tilted so they read as stone not ice
    put(room, box_tmp((w - 0.06, 1.25, h), 0.3), "stone", (x + w / 2, WALL_Y + 0.3, FLOOR + h / 2 - 0.05),
        (rng.uniform(-0.04, 0.04), rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05)), jitter=0.13, seed=100 + k)
    x += w - 0.05
    k += 1
PLANK_V = 0.92
# solid backing board so no gap between planks ever shows the sky
put(room, box_tmp((2 * HALF_W, 0.2, WALL_TOP - FLOOR - FOOT_H + 0.2), 0.0), "dark",
    (0, WALL_Y + 0.38, (FLOOR + FOOT_H - 0.2 + WALL_TOP) / 2))
x = -HALF_W
k = 0
while x < HALF_W:
    h0 = FLOOR + FOOT_H - 0.25
    h1 = WALL_TOP - rng.uniform(0.0, 0.15)
    put(room, box_tmp((PLANK_V - 0.05, 0.26, h1 - h0), 0.06), rng.choice(("plank", "plank", "plank2", "dark")),
        (x + PLANK_V / 2, WALL_Y + 0.14 + rng.uniform(-0.03, 0.03), (h0 + h1) / 2),
        (0, rng.uniform(-0.004, 0.004), 0))
    x += PLANK_V
    k += 1
POSTS = [-15.6, -6.4, 6.4, 15.6]
for i, px in enumerate(POSTS):
    put(room, box_tmp((0.95, 0.95, WALL_TOP - FLOOR + 1.3), 0.14), "dark",
        (px, WALL_Y - 0.4, FLOOR + (WALL_TOP - FLOOR + 1.3) / 2), jitter=0.035, seed=300 + i)
# top beam and a mid rail on the side bays
put(room, box_tmp((2 * HALF_W + 1.4, 0.9, 0.8), 0.13), "dark", (0, WALL_Y - 0.45, WALL_TOP - 0.2), jitter=0.04, seed=320)
for s in (-1, 1):
    put(room, box_tmp((9.0, 0.5, 0.42), 0.1), "dark", (s * 11.0, WALL_Y - 0.15, FLOOR + 6.2), jitter=0.03, seed=330 + s)

# --- roof overhang: rafters, deck, slate shingles, knee braces ---------------
ROOF_BACK = (WALL_Y + 0.2, WALL_TOP + 0.9)
ROOF_FRONT = (WALL_Y - 4.6, WALL_TOP + 0.1)
slope = math.atan2(ROOF_BACK[1] - ROOF_FRONT[1], ROOF_BACK[0] - ROOF_FRONT[0])
depth = math.hypot(ROOF_BACK[0] - ROOF_FRONT[0], ROOF_BACK[1] - ROOF_FRONT[1])
mid = ((ROOF_BACK[0] + ROOF_FRONT[0]) / 2, (ROOF_BACK[1] + ROOF_FRONT[1]) / 2)
for k in range(17):
    rx = -HALF_W + k * (2 * HALF_W) / 16
    put(room, box_tmp((0.42, depth + 0.4, 0.5), 0.08), "dark", (rx, mid[0], mid[1] - 0.2), (-slope, 0, 0),
        jitter=0.02, seed=400 + k)
put(room, box_tmp((2 * HALF_W + 1.2, depth + 0.2, 0.14), 0.03), "plank", (0, mid[0], mid[1] + 0.12), (-slope, 0, 0))
# shingle rows, overlapping downhill; chunky slate tiles with a hanging front row
rows = 5
for r in range(rows):
    t = r / (rows - 1)
    cy = ROOF_BACK[0] + (ROOF_FRONT[0] - ROOF_BACK[0]) * t
    cz = ROOF_BACK[1] + (ROOF_FRONT[1] - ROOF_BACK[1]) * t + 0.4
    x = -HALF_W - 0.8 + (0.55 if r % 2 else 0)
    while x < HALF_W + 0.8:
        w = rng.uniform(1.0, 1.3)
        put(room, box_tmp((w - 0.06, 1.5, 0.3), 0.1), "slate", (x + w / 2, cy - (0.25 if r == rows - 1 else 0), cz),
            (-slope - 0.1 + rng.uniform(-0.02, 0.02), rng.uniform(-0.015, 0.015), rng.uniform(-0.015, 0.015)))
        x += w
# fascia board along the front edge
put(room, box_tmp((2 * HALF_W + 1.6, 0.26, 0.55), 0.07), "dark", (0, ROOF_FRONT[0] - 0.2, ROOF_FRONT[1] - 0.05),
    jitter=0.02, seed=450)
for i, px in enumerate(POSTS):
    brace = box_tmp((0.34, 3.4, 0.34), 0.07)
    put(room, brace, "dark", (px, WALL_Y - 2.2, WALL_TOP - 0.7), (math.radians(-38), 0, 0), jitter=0.02, seed=460 + i)

# --- the crest behind the avatar ----------------------------------------------
# The plaque stands off the wall on a hidden post so the real katana and bat
# (DISPLAY) fit crossed behind it.
CREST = (0.0, WALL_Y - 1.4, 5.9)   # plaque back face centre (x, y, z)
CR = 2.75
cx, cy, cz = CREST
put(props, cyl_tmp(0.45, 0.45, WALL_Y - cy + 0.05, segs=8), "dark", (cx, cy, cz), (-math.pi / 2, 0, 0))


def crest_put(tmp, mat, dz):
    """Plaque layers: dark wood rim, slate face, lime ring, cream star, brass boss."""
    bmesh.ops.transform(tmp, matrix=Matrix.Translation((0, 0, dz)), verts=tmp.verts)
    put(props, tmp, mat, (cx, cy, cz), FACE_CAM)


crest_put(cyl_tmp(CR, CR, 0.34, segs=20, bevel=0.1), "dark", 0.0)
crest_put(cyl_tmp(CR * 0.86, CR * 0.86, 0.06, segs=20), "slate", 0.32)
cring = bmesh.new()
n = 28
ov = [cring.verts.new((x, y, 0.4)) for x, y in circle(CR * 0.8, n)]
iv = [cring.verts.new((x, y, 0.4)) for x, y in circle(CR * 0.71, n)]
for k in range(n):
    j = (k + 1) % n
    cring.faces.new((ov[k], ov[j], iv[j], iv[k]))
bmesh.ops.recalc_face_normals(cring, faces=cring.faces)
put(props, cring, "lime", (cx, cy, cz), FACE_CAM)
star = []
for k in range(8):
    a = math.pi / 2 + 2 * math.pi * k / 8
    rr = CR * 0.56 if k % 2 == 0 else CR * 0.2
    star.append((math.cos(a) * rr, math.sin(a) * rr))
crest_put(prism_tmp(star, 0.0, 0.08, 0.02), "cream", 0.36)
crest_put(cyl_tmp(0.42, 0.3, 0.2, segs=10, bevel=0.05), "brass", 0.42)
for k in range(10):  # rim studs
    a = 2 * math.pi * k / 10 + 0.31
    stud = cyl_tmp(0.1, 0.07, 0.12, segs=6)
    bmesh.ops.transform(stud, matrix=Matrix.Translation((math.cos(a) * CR * 0.93, math.sin(a) * CR * 0.93, 0.32)),
                        verts=stud.verts)
    put(props, stud, "brass", (cx, cy, cz), FACE_CAM)

# --- hanging lanterns flanking the crest ---------------------------------------
for s in (-1, 1):
    lx, ly = s * 3.9, WALL_Y - 2.4
    top_z = WALL_TOP + 0.4
    body_top = FLOOR + 8.0
    put(props, box_tmp((0.08, 0.08, top_z - body_top - 0.2), 0.0), "rope", (lx, ly, (top_z + body_top + 0.2) / 2))
    # cap, frame posts, base
    put(props, cyl_tmp(0.62, 0.2, 0.42, segs=6, bevel=0.04), "metal", (lx, ly, body_top - 0.05))
    put(props, cyl_tmp(0.12, 0.12, 0.2, segs=6), "metal", (lx, ly, body_top + 0.34))
    for k in range(6):
        a = 2 * math.pi * k / 6
        put(props, box_tmp((0.1, 0.1, 1.05), 0.02), "metal", (lx + math.cos(a) * 0.46, ly + math.sin(a) * 0.46, body_top - 0.55))
    put(props, cyl_tmp(0.5, 0.56, 0.18, segs=6, bevel=0.03), "metal", (lx, ly, body_top - 1.2))
    glass = cyl_tmp(0.42, 0.42, 0.95, segs=6)
    bmesh.ops.transform(glass, matrix=Matrix.Translation((lx, ly, body_top - 1.05)), verts=glass.verts)
    L.merge_bm(glow["warm"], glass, 0)

# --- left bay: standing weapon rack (Excalibur, Magic Staff, Shovel) -----------
RY = WALL_Y - 1.0
for rx in (-5.3, -10.4):
    put(props, box_tmp((0.34, 0.5, 4.3), 0.07), "dark", (rx, RY, FLOOR + 2.15), jitter=0.02, seed=int(abs(rx) * 10))
    put(props, box_tmp((0.8, 0.8, 0.22), 0.06), "dark", (rx, RY, FLOOR + 0.11))
put(props, box_tmp((5.6, 0.72, 0.3), 0.08), "dark", (-7.85, RY, FLOOR + 0.55), jitter=0.02, seed=501)
put(props, box_tmp((5.6, 0.42, 0.28), 0.07), "dark", (-7.85, RY + 0.35, FLOOR + 3.9), jitter=0.02, seed=502)

# --- right bay: wall display (launcher, frying pan, boomerang, shelf) -----------
WY = WALL_Y - 0.12


def peg(x, z, length=0.9):
    """Wooden peg sticking out of the wall towards the camera."""
    put(props, cyl_tmp(0.1, 0.1, length, segs=6), "dark", (x, WALL_Y + 0.05, z), (math.pi / 2, 0, 0))


for px in (7.0, 9.8):
    peg(px, 5.45, 1.5)   # launcher rests on these
peg(10.9, 7.45)          # frying pan hangs by its handle
for px in (7.3, 8.9):
    peg(px, 3.05)        # boomerang
put(props, box_tmp((7.4, 0.9, 0.24), 0.07), "plank", (11.0, WY - 0.5, FLOOR + 3.3), jitter=0.02, seed=520)
for bx in (8.0, 14.0):
    put(props, box_tmp((0.24, 0.6, 0.7), 0.05), "dark", (bx, WY - 0.35, FLOOR + 2.95))
# folded cloths at the shelf's end: chunky cream + slate bundles
put(props, box_tmp((1.2, 0.7, 0.4), 0.14), "slate", (13.9, WY - 0.5, FLOOR + 3.62), jitter=0.04, seed=530)
put(props, box_tmp((1.0, 0.62, 0.34), 0.13), "cream", (13.9, WY - 0.5, FLOOR + 3.98), jitter=0.04, seed=531)

# --- floor props: anvil on stump (left), barrel + crates (right) ----------------
sx, sy = -12.2, 3.0
put(props, cyl_tmp(1.05, 0.95, 1.35, segs=9, bevel=0.08), "dark", (sx, sy, FLOOR), jitter=0.06, seed=600)
put(props, cyl_tmp(0.92, 0.92, 0.06, segs=9), "light", (sx, sy, FLOOR + 1.34))
anvil = [(-1.1, 0.0), (1.2, 0.0), (1.2, 0.18), (0.55, 0.3), (0.45, 0.7), (1.35, 0.95), (1.1, 1.18), (-0.9, 1.18),
         (-1.7, 1.02), (-0.55, 0.72), (-0.6, 0.3), (-1.1, 0.18)]
put(props, prism_tmp(anvil, -0.4, 0.4, 0.05), "metal", (sx, sy, FLOOR + 1.4), (math.pi / 2, 0, math.radians(20)))

bx, by = 11.9, 3.2
put(props, cyl_tmp(1.0, 1.0, 1.9, segs=10, bevel=0.08), "plank", (bx, by, FLOOR), jitter=0.03, seed=610)
for hz in (0.3, 1.55):
    put(props, cyl_tmp(1.04, 1.04, 0.14, segs=10), "metal", (bx, by, FLOOR + hz))
cxr, cyr = 14.0, 5.4
put(props, box_tmp((1.8, 1.8, 1.7), 0.12), "light", (cxr, cyr, FLOOR + 0.85), (0, 0, 0.12), jitter=0.03, seed=620)
put(props, box_tmp((1.4, 1.4, 1.3), 0.11), "plank", (cxr - 0.2, cyr + 0.1, FLOOR + 2.35), (0, 0, -0.2), jitter=0.03, seed=621)

# --- objects ---------------------------------------------------------------
room_obj = L.bm_to_obj("Armory_Room", room, MATS, ROOM)
props_obj = L.bm_to_obj("Armory_Props", props, MATS, ROOM)
glow_objs = {}
for key, gbm in glow.items():
    name = "Armory_Glow" + key.capitalize()
    glow_objs[key] = L.bm_to_obj(name, gbm, [GLOW[key]], ROOM)

# evergreens peeking over the roof, and a few beyond the open front corners
FOLIAGE = L.collection("ArmoryTrees")
tree = L.import_master(EVERGREEN_GLB, "Evergreen_Master")
trees = []
spots = [(-19, 15, 0.95), (-12, 19, 1.1), (-5.5, 17, 0.85), (2.5, 21, 1.15), (9, 17.5, 0.95), (15.5, 20, 1.1),
         (22, 15, 0.9), (-24, 22, 1.0), (27, 23, 1.05), (-2, 26, 1.2), (7, 27, 1.15), (-15, 27, 1.2)]
for k, (tx, ty, s) in enumerate(spots):
    trees.append(L.place_instance(tree, f"Armory_Tree_{k:02d}", (tx, ty, FLOOR - 1.5), rng.uniform(0, 6.28), s, FOLIAGE))
trees_obj = L.join("Armory_Trees", trees, ROOM)
# ground behind the hall so trees are not floating
ground = bmesh.new()
put(ground, box_tmp((80, 30, 1.0), 0.0), 0, (0, 23, FLOOR - 1.9))
grass = L.paint_mat("Armory_Grass", [(0.0, "#4f9a2e"), (0.5, "#6fbe3a"), (1.0, "#8fd650")], blob=6.0, jitter=0.35)
ground_obj = L.bm_to_obj("Armory_Ground", ground, [grass], ROOM)

report = {"triangles": {}, "pivot": "dais top centre (avatar feet)", "floor_z": FLOOR, "cameras": CAMERAS,
          "crest_centre": list(CREST), "crest_radius": CR,
          "weapon_slots_studio": [
              dict(d, at=studio(d["at"]), dir=studio(d["dir"]),
                   **({"up": studio(d["up"])} if "up" in d else {}),
                   **({"face": studio(d["face"])} if "face" in d else {}))
              for d in DISPLAY]}
for o in (room_obj, props_obj, trees_obj, ground_obj, *glow_objs.values()):
    report["triangles"][o.name] = L.tri_count(o)

# --- bake procedural parts --------------------------------------------------------
TEX = HERE / "textures"
TEX.mkdir(exist_ok=True)
L.join("Armory_Room", [room_obj, ground_obj], ROOM)
room_obj = bpy.data.objects["Armory_Room"]
L.bake_atlas(room_obj, TEX / "armory-room-atlas.png", size=2048)
L.bake_atlas(props_obj, TEX / "armory-props-atlas.png", size=2048)

# --- export ------------------------------------------------------------------------
(HERE / "exports" / "fbx").mkdir(parents=True, exist_ok=True)
(HERE / "exports" / "glb").mkdir(parents=True, exist_ok=True)
export_objs = [room_obj, props_obj, trees_obj, *glow_objs.values()]
L.export(export_objs, HERE / "exports" / "fbx" / "armory-backdrop.fbx", HERE / "exports" / "glb" / "armory-backdrop.glb")
bpy.ops.wm.save_as_mainfile(filepath=str(HERE / "armory-backdrop.blend"))

# --- previews at the Studio cameras ------------------------------------------------
PREV = HERE / "previews"
PREV.mkdir(exist_ok=True)
L.setup_preview(sun_rot=(0.41, 0.0, 0.35), sun_energy=3.8, fill=0.75)
for name, c in CAMERAS.items():
    lens = (36 * 9 / 16) / 2 / math.tan(math.radians(c["fov"]) / 2)
    cam = L.camera("Cam_" + name, c["eye"], c["look"], lens=lens)
    L.render(cam, PREV / f"armory-{name}.png")
wide = L.camera("Cam_wide", (0, -26, 6), (0, 2, 3.5), lens=24)
L.render(wide, PREV / "armory-wide.png")

(HERE / "armory-report.json").write_text(json.dumps(report, indent=2))
print("ARMORY_DONE", json.dumps(report["triangles"]))
