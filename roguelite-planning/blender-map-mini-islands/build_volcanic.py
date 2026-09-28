"""Volcanic Crater mini island for the map-select background.

blender --background --factory-startup --python build_volcanic.py

A small floating island that condenses the Volcanic Crater arena: warm-grey
cracked basalt floor with thin glowing cracks, a back wall of chunky basalt
blocks with two lavafalls, a small erupting volcano cone at the back centre
feeding a U-shaped lava channel that spills over both sides of the island,
hex basalt columns around the rim (low at the front so props read), black
obsidian spike clusters with glowing veins, charred dead trees, a wooden
mining derrick, a gallows crane with a chain and ore bucket, a mine cart full
of ore on a short rail, crates/barrels, rubble piles and two cooled vents.

Everything that glows lives in ONE separate mesh, `Volcanic_Lava`, with its own
small emissive atlas so it can be set to Neon in Roblox. Everything else is
joined and baked into `Volcanic_Island` like the Pine Valley island.
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

MAP = "Volcanic"
STEM = "volcanic"
SEED = 23
RADIUS = 30.0
DEPTH = 26.0
LAVA_STRENGTH = 2.4

OUT_TEX = HERE / "textures"
OUT_PREV = HERE / "previews"
OUT_FBX = HERE / "exports" / "fbx"
OUT_GLB = HERE / "exports" / "glb"
for d in (OUT_TEX, OUT_PREV, OUT_FBX, OUT_GLB):
    d.mkdir(parents=True, exist_ok=True)

rng = random.Random(SEED)
scene = L.reset_scene()
PROPS = L.collection(f"{MAP}_Procedural")
GLOW = L.collection(f"{MAP}_Glow")

# hero camera position; veins/seams are painted on the camera-facing side
CAM_HERO = Vector((0, -118, 34))

# ---------------------------------------------------------------------------
# palette (sampled from the Volcanic Crater concept, kept readable: warm grey
# basalt, never pure black; the game adds +0.3 saturation)
# ---------------------------------------------------------------------------
FLOOR = L.paint_mat("VC_Floor", [(0.15, "#51475a"), (0.4, "#625766"), (0.64, "#736773"), (0.9, "#857880")],
                    blob=7.0, jitter=0.5, facing=0.3)
SCORCH = L.paint_mat("VC_Scorch", [(0.0, "#27222b"), (0.5, "#362e37"), (1.0, "#473a3f")], blob=3.0, jitter=0.35)
UNDER = L.paint_mat("VC_Underside", [(0.08, "#2b2736"), (0.36, "#3c3647"), (0.62, "#4e4654"), (0.9, "#625864")],
                    blob=5.0, jitter=0.32, facing=0.75)
BASALT = L.paint_mat("VC_Basalt", [(0.1, "#3b3445"), (0.38, "#4e4656"), (0.62, "#635a66"), (0.9, "#7a6f79")],
                     blob=4.0, jitter=0.3, facing=0.75)
BTOP = L.paint_mat("VC_BasaltCap", [(0.0, "#675d6a"), (0.6, "#7a6f7a"), (1.0, "#8d8089")], blob=3.0, jitter=0.3,
                   facing=0.2)
OBSIDIAN = L.paint_mat("VC_Obsidian", [(0.0, "#16121b"), (0.5, "#241d2d"), (1.0, "#3d3249")], blob=1.5, jitter=0.3,
                       facing=0.7, rough=0.35)
CHAR = L.paint_mat("VC_Char", [(0.0, "#1f1a19"), (0.5, "#2f2522"), (1.0, "#46372e")], blob=1.2, jitter=0.35,
                   facing=0.5)
WOOD = L.paint_mat("VC_Wood", [(0.0, "#4f3423"), (0.5, "#6f4b30"), (1.0, "#8c6441")], blob=1.4, jitter=0.35,
                   facing=0.4)
CUT = L.paint_mat("VC_CutWood", [(0.0, "#9c7550"), (1.0, "#b89068")], blob=0.6, jitter=0.3, facing=0.2)
METAL = L.paint_mat("VC_Metal", [(0.0, "#2c2e33"), (1.0, "#4d5058")], blob=1.0, jitter=0.2)
SMOKE = L.paint_mat("VC_Smoke", [(0.0, "#6a6272"), (0.5, "#877d8c"), (1.0, "#a79ca8")], blob=3.0, jitter=0.3,
                    facing=0.7)
ORE = L.paint_mat("VC_Ore", [(0.0, "#3a3439"), (0.6, "#554b4d"), (1.0, "#6d615d")], blob=0.8, jitter=0.35,
                  facing=0.6)

MATS = [BASALT, FLOOR, BTOP, OBSIDIAN, CHAR, WOOD, CUT, METAL, SMOKE, SCORCH, ORE]
(I_BASALT, I_FLOOR, I_BTOP, I_OBS, I_CHAR, I_WOOD, I_CUT, I_METAL, I_SMOKE, I_SCORCH, I_ORE) = range(len(MATS))


def lava_mat(name):
    """Hot lava: broad orange/yellow patches, emission driven by the same ramp."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.6
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.45, 0.45, 0.45)
    nt.links.new(coord.outputs["Object"], mp.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 1.0
    nz.inputs["Detail"].default_value = 1.2
    nz.inputs["Distortion"].default_value = 0.8
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position = 0.3
    els[0].color = L.srgb("#d8360a")
    els[1].position = 0.72
    els[1].color = L.srgb("#ffa232")
    e = els.new(0.5)
    e.color = L.srgb("#ff6814")
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = LAVA_STRENGTH
    return m


LAVA_MAT = lava_mat("VC_Lava")
LAVA = bmesh.new()          # every glowing piece goes in here (world coords)


# ---------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------
class Surf:
    """BVH over one or more objects (all procedural objects have identity
    transforms, but matrix_world is applied anyway)."""

    def __init__(self, objs):
        verts, polys = [], []
        for o in objs:
            base = len(verts)
            mw = o.matrix_world
            verts.extend(mw @ v.co for v in o.data.vertices)
            polys.extend([base + i for i in p.vertices] for p in o.data.polygons)
        self.bvh = BVHTree.FromPolygons(verts, polys)

    def cast(self, origin, direction, dist=1.0e4):
        loc, nrm, idx, d = self.bvh.ray_cast(Vector(origin), Vector(direction).normalized(), dist)
        return loc, nrm

    def down(self, x, y, default=0.0):
        loc, _ = self.cast((x, y, 300), (0, 0, -1))
        return loc.z if loc is not None else default


def catmull(pts, step):
    """Resample a polyline through `pts` (Vectors) as a smooth curve."""
    out = []
    P = [pts[0]] + list(pts) + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        n = max(1, int((p2 - p1).length / step))
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(pts[-1].copy())
    return out


def ribbon(bm, pts, nrms, widths, lift=0.06, mat=0, drape=None, drape_flags=None):
    """Quad strip through 3D points, lying on a surface with normals `nrms`.
    If `drape` (a Surf) is given, vertices whose flag is true are re-snapped
    straight down onto it (floor pieces), so wide strips follow the ground."""
    n = len(pts)
    if n < 2:
        return
    left, right = [], []
    for i in range(n):
        t = pts[min(n - 1, i + 1)] - pts[max(0, i - 1)]
        if t.length < 1e-6:
            t = Vector((1, 0, 0))
        t.normalize()
        nn = Vector(nrms[i]).normalized()
        side = t.cross(nn)
        if side.length < 1e-6:
            side = t.orthogonal()
        side.normalize()
        c = pts[i] + nn * lift
        w = max(0.05, widths[i]) / 2
        a, b = c + side * w, c - side * w
        if drape is not None and (drape_flags is None or drape_flags[i]):
            a.z = drape.down(a.x, a.y) + lift
            b.z = drape.down(b.x, b.y) + lift
        left.append(bm.verts.new(a))
        right.append(bm.verts.new(b))
    for i in range(n - 1):
        f = bm.faces.new((left[i], right[i], right[i + 1], left[i + 1]))
        f.material_index = mat
        f.normal_update()
        if f.normal.dot(Vector(nrms[i]) + Vector(nrms[i + 1])) < 0:
            f.normal_flip()


def disc(bm, center, rx, ry, lift, seed, drape=None, segs=12, mat=0, rot_z=0.0):
    """Irregular flat blob (lava pool / splash) draped on the floor."""
    c = bm.verts.new((center[0], center[1], (drape.down(center[0], center[1]) if drape else center[2]) + lift))
    ring = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        k = 1 + 0.16 * math.sin(a * 3 + seed) + 0.08 * math.cos(a * 5 + seed * 2)
        lx, ly = math.cos(a) * rx * k, math.sin(a) * ry * k
        x = center[0] + lx * math.cos(rot_z) - ly * math.sin(rot_z)
        y = center[1] + lx * math.sin(rot_z) + ly * math.cos(rot_z)
        z = (drape.down(x, y) if drape else center[2]) + lift
        ring.append(bm.verts.new((x, y, z)))
    for i in range(segs):
        f = bm.faces.new((c, ring[i], ring[(i + 1) % segs]))
        f.material_index = mat
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()


def limb(bm, a, b, r1, r2, mat, segs=6):
    a, b = Vector(a), Vector(b)
    d = b - a
    m = Matrix.Translation(a) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    L.cyl_bm(bm, r1, r2, d.length, segs=segs, matrix=m, mat_index=mat)


def beam(bm, a, b, t, mat, t2=None):
    a, b = Vector(a), Vector(b)
    d = b - a
    rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    L.box_bm(bm, (t, t2 or t, d.length), loc=(a + b) / 2, rot=rot, mat_index=mat)


def stone(bm, loc, size, seed, mat, squash=0.7, rot_z=0.0, blocky=False):
    tmp = bmesh.new()
    if blocky:
        bmesh.ops.create_cube(tmp, size=1.0)
        bmesh.ops.bevel(tmp, geom=list(tmp.edges), offset=0.14, segments=1, affect="EDGES", profile=0.5)
    else:
        bmesh.ops.create_icosphere(tmp, subdivisions=1, radius=0.5)
    L.jitter_bm(tmp, 0.1, seed, freq=1.7)
    L.transform_bm(tmp, loc=loc, rot=L.trs(rot=(rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15), rot_z)),
                   scale=(size, size * 0.85, size * squash))
    L.merge_bm(bm, tmp, mat)


def vein(bm, surf, A, B, width, t0=0.12, t1=0.85, n=8, zig=0.18, lift=0.05, view=CAM_HERO, seed=0,
         reach=8.0):
    """Glowing zig-zag vein painted on the camera-facing side of a shape whose
    axis runs A->B. Rays come from the camera side toward the axis."""
    A, B = Vector(A), Vector(B)
    axis = (B - A).normalized()
    pts, nrms, ws = [], [], []
    r2 = random.Random(seed)
    for i in range(n):
        t = t0 + (t1 - t0) * i / (n - 1)
        p = A.lerp(B, t)
        to_cam = view - p
        to_cam -= axis * to_cam.dot(axis)
        to_cam.normalize()
        lat = axis.cross(to_cam).normalized()
        off = lat * (zig * math.sin(i * 1.25 + seed * 0.7) * r2.uniform(0.7, 1.0))
        loc, nrm = surf.cast(p + to_cam * reach + off, -to_cam, reach * 2)
        if loc is None:
            if len(pts) >= 2:
                ribbon(bm, pts, nrms, ws, lift=lift)
            pts, nrms, ws = [], [], []
            continue
        pts.append(loc)
        nrms.append(nrm)
        ws.append(width * (0.35 + 0.65 * math.sin(math.pi * (0.15 + 0.85 * i / (n - 1)))))
    if len(pts) >= 2:
        ribbon(bm, pts, nrms, ws, lift=lift)


def rot2(v, a):
    return Vector((v.x * math.cos(a) - v.y * math.sin(a), v.x * math.sin(a) + v.y * math.cos(a)))


# ---------------------------------------------------------------------------
# island body
# ---------------------------------------------------------------------------
island, R = L.island_body(f"{MAP}_Body", RADIUS, DEPTH, SEED, FLOOR, SCORCH, UNDER, col=PROPS,
                          drip_mat=SCORCH, drips=16, spires=7, top_bumps=0.3)
bpy.context.view_layer.update()
BODY = Surf([island])


def polar(theta_deg, frac):
    th = math.radians(theta_deg)
    r = R(th) * frac
    return math.cos(th) * r, math.sin(th) * r


def ground(x, y):
    return BODY.down(x, y)


def facing_center(x, y):
    return math.atan2(-y, -x)


made = []
EXCLUDE = []     # (x, y, r) keep floor cracks out of prop footprints

# ---------------------------------------------------------------------------
# volcano: small erupting cone at the back centre
# ---------------------------------------------------------------------------
VX, VY = polar(90, 0.79)
V_RX, V_RY, V_H = 9.5, 7.0, 15.5


def volcano(name):
    bm = bmesh.new()
    segs = 12
    # (radius frac, z) outer flank from base to rim, then crater wall
    prof = [(1.0, -0.9), (0.84, 2.4), (0.66, 6.2), (0.49, 10.0), (0.36, 13.4), (0.27, V_H)]
    inner = [(0.2, V_H - 1.1), (0.13, V_H - 2.0)]
    notch = [-90, -62, -122]            # rim notches where lava spills (local deg, -90 = toward camera)
    rings = []
    for k, (rf, z) in enumerate(prof + inner):
        ring = []
        for i in range(segs):
            a = 2 * math.pi * (i + 0.28 * (k % 2)) / segs
            nz = noise.noise(Vector((math.cos(a) * 1.6, math.sin(a) * 1.6, k * 0.7 + SEED)))
            rr = rf * (1 + 0.09 * nz)
            x, y = VX + math.cos(a) * V_RX * rr, VY + math.sin(a) * V_RY * rr
            zz = z + 0.5 * noise.noise(Vector((math.cos(a) * 2, math.sin(a) * 2, k + 3.3)))
            if k == len(prof) - 1:
                deg = math.degrees(a)
                for nd in notch:
                    dd = abs((deg - nd + 180) % 360 - 180)
                    if dd < 20:
                        zz -= 0.9 * (1 - dd / 20)
            # keep the cone on the island
            r_here = math.hypot(x, y)
            lim = R(math.atan2(y, x)) * 0.975
            if r_here > lim:
                x, y = x * lim / r_here, y * lim / r_here
            ring.append(bm.verts.new((x, y, zz)))
        rings.append(ring)
    centre = bm.verts.new((VX, VY, V_H - 2.3))
    n_out = len(prof)
    for k in range(len(rings) - 1):
        a, b = rings[k], rings[k + 1]
        mat = I_BASALT if k < n_out - 1 else I_SCORCH
        for i in range(segs):
            f = bm.faces.new((a[i], a[(i + 1) % segs], b[(i + 1) % segs], b[i]))
            f.material_index = mat
    for i in range(segs):
        f = bm.faces.new((rings[-1][i], rings[-1][(i + 1) % segs], centre))
        f.material_index = I_SCORCH
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # lighter ashy rim band
    for f in bm.faces:
        if f.material_index == I_BASALT and f.calc_center_median().z > V_H - 2.2 and f.normal.z > 0.3:
            f.material_index = I_BTOP
    floor_ring = [v.co.copy() for v in rings[-1]]
    obj = L.bm_to_obj(name, bm, MATS, PROPS)
    return obj, notch, floor_ring


vol, V_NOTCH, crater_ring = volcano(f"{MAP}_Volcano")
made.append(vol)
VSURF = Surf([vol])

# crater lava pool (slightly larger than the crater floor ring, hidden by its walls)
c = LAVA.verts.new((VX, VY, V_H - 1.75))
ring = [LAVA.verts.new((VX + (v.x - VX) * 1.25, VY + (v.y - VY) * 1.25, V_H - 1.75)) for v in crater_ring]
for i in range(len(ring)):
    LAVA.faces.new((c, ring[i], ring[(i + 1) % len(ring)]))

# lava streaks down the flank from the rim notches
for s, nd in enumerate(V_NOTCH):
    pts, nrms, ws = [], [], []
    steps = 16
    for i in range(steps + 1):
        t = i / steps
        a = math.radians(nd) + 0.10 * math.sin(t * 7 + s * 2) * (0.3 + t)
        rf = 0.27 + (1.02 - 0.27) * t
        x, y = VX + math.cos(a) * V_RX * rf, VY + math.sin(a) * V_RY * rf
        loc, nrm = VSURF.cast((x, y, 300), (0, 0, -1))
        if loc is None or loc.z < -0.2:
            break
        pts.append(loc)
        nrms.append(nrm)
        ws.append((1.05 if s == 0 else 0.75) * (1.0 - 0.3 * t))
    ribbon(LAVA, pts, nrms, ws, lift=0.1)

# eruption: a short lava fountain and a few chunky smoke puffs drifting back
L.cyl_bm(LAVA, 0.9, 0.0, 3.4, segs=6, matrix=Matrix.Translation((VX, VY, V_H - 2.0)), cap_tris=True,
         jitter=0.15, seed=4)
L.cyl_bm(LAVA, 0.55, 0.0, 2.4, segs=5, matrix=L.trs((VX + 0.7, VY - 0.3, V_H - 1.8), (0.35, 0.3, 0)),
         cap_tris=True)
L.cyl_bm(LAVA, 0.5, 0.0, 2.2, segs=5, matrix=L.trs((VX - 0.8, VY + 0.2, V_H - 1.8), (-0.2, -0.4, 0)),
         cap_tris=True)
for (dx, dy, dz, r) in [(1.9, -0.4, 2.6, 0.32), (-1.7, 0.1, 3.3, 0.26), (0.4, -1.3, 4.1, 0.24)]:
    b = bmesh.new()
    bmesh.ops.create_icosphere(b, subdivisions=1, radius=r)
    L.transform_bm(b, loc=(VX + dx, VY + dy, V_H + dz))
    L.merge_bm(LAVA, b, 0)
smoke_bm = bmesh.new()
sr = random.Random(SEED + 60)
for lvl, (dz, spread, r, drift) in enumerate([(1.2, 0.8, 1.35, 0.6), (3.0, 1.4, 1.8, 1.6), (5.0, 1.9, 2.2, 2.8),
                                            (7.0, 2.2, 2.3, 4.0)]):
    for j in range(3 if lvl else 2):
        a = j * 2.1 + lvl * 0.9
        b = bmesh.new()
        bmesh.ops.create_icosphere(b, subdivisions=2, radius=1.0)
        L.jitter_bm(b, 0.1, SEED + lvl * 5 + j, freq=1.2)
        rr = r * sr.uniform(0.8, 1.05)
        L.transform_bm(b, loc=(VX + drift * 0.55 + math.cos(a) * spread * 0.6, VY + 0.8 + drift + math.sin(a) * spread * 0.4,
                               V_H + dz + sr.uniform(-0.3, 0.3)), scale=(rr * 1.1, rr, rr * 0.8))
        L.merge_bm(smoke_bm, b, I_SMOKE)
made.append(L.bm_to_obj(f"{MAP}_Smoke", smoke_bm, MATS, PROPS))

# ---------------------------------------------------------------------------
# back wall: chunky basalt blocks flanking the volcano
# ---------------------------------------------------------------------------
LAVAFALL_TH = (53, 127)
wall = []
wall_info = []
for k, th in enumerate([41, 53, 65, 115, 127, 139]):
    mid = 1 - abs(abs(th - 90) - 24) / 40       # tallest right next to the volcano
    h = 7.2 + 3.2 * mid + rng.uniform(-0.6, 0.6)
    w = rng.uniform(7.0, 8.4)
    d = rng.uniform(5.5, 6.8)
    x, y = polar(th + rng.uniform(-2, 2), 0.86)
    z = ground(x, y) - 0.6
    rot = math.radians(th + 90 + rng.uniform(-8, 8))
    b = L.cliff_block(f"{MAP}_Wall_{k:02d}", w, d, h, seed=SEED + k, mats=MATS, cap_index=I_BTOP,
                      loc=(x, y, z), rot_z=rot, col=PROPS)
    made.append(b)
    wall.append(b)
    wall_info.append((th, x, y, z, h, w, b))
    # (no lower steps: the lava channel runs along the wall foot)
    if False:
        x2, y2 = polar(th + rng.uniform(-3, 3), 0.72)
        s = L.cliff_block(f"{MAP}_WallStep_{k:02d}", w * 0.6, d * 0.6, h * 0.38, seed=SEED + 40 + k, mats=MATS,
                          cap_index=I_BTOP, loc=(x2, y2, ground(x2, y2) - 0.4), rot_z=rot + 0.3, col=PROPS)
        made.append(s)
        wall.append(s)
WALL = Surf(wall)

# glowing seams down some wall blocks (camera-facing side)
for k, (th, x, y, z, h, w, b) in enumerate(wall_info):
    if min(abs(th - lt) for lt in LAVAFALL_TH) < 4:
        continue
    bs = Surf([b])
    lat = Vector((-math.sin(math.radians(th)), math.cos(math.radians(th)), 0)) * rng.choice((-1, 1)) * w * 0.28
    vein(LAVA, bs, Vector((x, y, z + 0.4)) + lat, Vector((x, y, z + h * 0.95)) + lat, 0.3, t0=0.04, t1=0.72, n=16,
         zig=0.16, lift=0.14, seed=SEED + k, reach=12)

# lavafalls: sheets draped down the wall faces into splash pools
fall_bases = []
for fi, th_deg in enumerate(LAVAFALL_TH):
    th = math.radians(th_deg)
    u = Vector((math.cos(th), math.sin(th), 0))
    tng = Vector((-math.sin(th), math.cos(th), 0))
    inner = Vector(polar(th_deg, 0.55)).to_3d()
    loc, _ = WALL.cast(inner + Vector((0, 0, 3.0)), u, 30)
    if loc is None:
        loc = Vector(polar(th_deg, 0.76)).to_3d() + Vector((0, 0, 3.0))
    face_d = (loc - (inner + Vector((0, 0, 3.0)))).length
    ztop = WALL.down(*(loc + u * 1.4).xy) - 0.05
    zg = ground(*(loc - u * 0.6).xy)
    cols, rows = 5, 12
    W = 3.0
    grid = []
    for r_ in range(rows + 2):
        row = []
        for c_ in range(cols):
            s = (c_ / (cols - 1) - 0.5)
            if r_ < 2:   # lip rows lying on the block top, reaching back over the edge
                zb = ztop + 0.25
                back = 0.9 if r_ == 0 else 0.1
                p = loc + u * back + tng * s * W * 0.85
                p.z = WALL.down(p.x, p.y) + 0.14
                row.append(LAVA.verts.new(p))
                continue
            t = (r_ - 2) / (rows - 1)          # 0 at top, 1 at bottom
            zz = ztop - 0.35 + (zg + 0.15 - (ztop - 0.35)) * t
            wobble = 0.12 * math.sin(r_ * 1.3 + c_ * 2.1 + fi)
            origin = inner + tng * s * W * (0.85 + 0.55 * t ** 1.5) + Vector((0, 0, zz))
            hit, n = WALL.cast(origin, u, 30)
            if hit is None or (hit - origin).length > face_d + 3.0:
                hit = origin + u * face_d
            p = hit - u * (0.28 + wobble)
            if t > 0.97:
                p.z = zg + 0.13
            row.append(LAVA.verts.new(p))
        grid.append(row)
    for r_ in range(len(grid) - 1):
        for c_ in range(cols - 1):
            f = LAVA.faces.new((grid[r_][c_], grid[r_][c_ + 1], grid[r_ + 1][c_ + 1], grid[r_ + 1][c_]))
            f.normal_update()
            ref = Vector((0, 0, 1)) if r_ < 1 else -u
            if f.normal.dot(ref) < 0:
                f.normal_flip()
    base = loc - u * 1.6
    disc(LAVA, (base.x, base.y, 0), 2.1, 2.6, 0.12, fi * 3, drape=BODY, rot_z=th)
    fall_bases.append((base, u, ztop))

# ---------------------------------------------------------------------------
# lava channel: U-shaped moat in front of the back wall, spilling off both sides
# ---------------------------------------------------------------------------
path = [(29, 0.985), (32, 0.9), (39, 0.8), (50, 0.72), (62, 0.66), (75, 0.575), (90, 0.52), (105, 0.575),
        (118, 0.66), (130, 0.72), (141, 0.8), (148, 0.9), (151, 0.985)]
chan2d = catmull([Vector(polar(th, fr)) for th, fr in path], 1.1)
chan_pts = [Vector((p.x, p.y, ground(p.x, p.y))) for p in chan2d]
chan_w = [2.5 + 0.35 * math.sin(i * 0.55) for i in range(len(chan_pts))]
up = Vector((0, 0, 1))


def spill(th_deg, z0, z1, w0, w1, step=0.55, meander=2.5, seed=0):
    pts, nrms, ws = [], [], []
    z = z0
    i = 0
    total = max(0.1, z0 - z1)
    while z >= z1:
        th = math.radians(th_deg + meander * math.sin(i * 0.45 + seed))
        u = Vector((math.cos(th), math.sin(th), 0))
        loc, n = BODY.cast(u * (RADIUS * 2.5) + Vector((0, 0, z)), -u, RADIUS * 3)
        if loc is None:
            break
        pts.append(loc)
        nrms.append(n)
        t = (z0 - z) / total
        ws.append(w0 + (w1 - w0) * t)
        z -= step
        i += 1
    return pts, nrms, ws


def drip_tip(p, n, w):
    """Short downward cone finishing a lava streak."""
    m = Matrix.Translation(p + Vector(n) * 0.12) @ Matrix.Rotation(math.pi, 4, "X")
    L.cyl_bm(LAVA, w * 0.5, 0.0, 1.3, segs=5, matrix=m, cap_tris=True)


# one continuous strip: left spill (bottom -> lip) + floor channel + right spill (lip -> bottom)
lp, ln, lw = spill(29, -0.15, -11.0, 2.4, 0.5, seed=1)
rp, rn, rw = spill(151, -0.15, -8.5, 2.4, 0.5, seed=5)
all_pts = lp[::-1] + chan_pts + rp
all_n = ln[::-1] + [up] * len(chan_pts) + rn
all_w = lw[::-1] + chan_w + rw
flags = [False] * len(lp) + [True] * len(chan_pts) + [False] * len(rp)
ribbon(LAVA, all_pts, all_n, all_w, lift=0.12, drape=BODY, drape_flags=flags)
if lp:
    drip_tip(lp[-1], ln[-1], lw[-1])
if rp:
    drip_tip(rp[-1], rn[-1], rw[-1])

# scorched crust under the channel (baked) + bank stones
crust_bm = bmesh.new()
ribbon(crust_bm, chan_pts[1:-1], [up] * (len(chan_pts) - 2), [w + 1.6 for w in chan_w[1:-1]], lift=0.05,
       mat=I_SCORCH, drape=BODY)
for i, p in enumerate(chan2d[1:-1:2]):
    j = 1 + i * 2
    t = (chan2d[min(len(chan2d) - 1, j + 1)] - chan2d[j - 1]).normalized()
    side = Vector((-t.y, t.x))
    for sgn in (-1, 1):
        if rng.random() < 0.45:
            continue
        q = p + side * sgn * (chan_w[j] / 2 + 0.9 + rng.uniform(-0.2, 0.3))
        if q.length > R(math.atan2(q.y, q.x)) * 0.95:
            continue
        s = rng.uniform(0.7, 1.25)
        stone(crust_bm, (q.x, q.y, ground(q.x, q.y) + s * 0.12), s, SEED + 500 + i * 2 + sgn, I_BASALT,
              squash=0.6, rot_z=rng.uniform(0, 6), blocky=rng.random() < 0.5)
made.append(L.bm_to_obj(f"{MAP}_ChannelCrust", crust_bm, MATS, PROPS))
for p in chan2d:
    EXCLUDE.append((p.x, p.y, 2.6))

# ---------------------------------------------------------------------------
# hex basalt columns around the rim (low at the front so props stay readable)
# ---------------------------------------------------------------------------
col_bm = bmesh.new()
col_axes = []    # (base, top, radius) for glowing seams


def hex_col(x, y, r, h, seed):
    z0 = ground(x, y) - 0.5
    rot = seed * 0.37
    tilt = L.trs((x, y, z0), (rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05), rot))
    L.cyl_bm(col_bm, r, r * 0.93, h, segs=6, matrix=tilt, mat_index=I_BASALT)
    L.cyl_bm(col_bm, r * 0.93, r * 0.7, 0.32 * r, segs=6, matrix=tilt @ Matrix.Translation((0, 0, h)),
             mat_index=I_BTOP)
    col_axes.append((Vector((x, y, z0)), Vector((x, y, z0 + h)), r))


def column_cluster(th, fr, n, r, hmin, hmax, seed):
    r2 = random.Random(seed)
    cx, cy = polar(th, fr)
    u = Vector((cx, cy)).normalized()
    offs = [Vector((0, 0))] + [Vector((math.cos(a), math.sin(a))) * r * 1.8
                               for a in [i * math.pi / 3 + 0.3 for i in range(6)]]
    ring6 = offs[1:]
    r2.shuffle(ring6)
    offs = offs[:1] + ring6
    for i, o in enumerate(offs[:n]):
        p = Vector((cx, cy)) + o
        # keep columns on the island
        lim = R(math.atan2(p.y, p.x)) * 0.96 - r
        if p.length > lim:
            p = p * (lim / p.length)
        outward = o.dot(u) / (r * 1.8) if o.length else 0.3
        h = hmin + (hmax - hmin) * (0.5 + 0.5 * outward) * r2.uniform(0.75, 1.1)
        hex_col(p.x, p.y, r * r2.uniform(0.85, 1.1), max(0.9, h), seed * 10 + i)
    EXCLUDE.append((cx, cy, r * 3.2))


# sides: taller clusters
for k, (th, fr, n, r, hmin, hmax) in enumerate([
        (163, 0.9, 5, 1.5, 3.0, 6.5), (180, 0.9, 5, 1.6, 2.4, 5.5), (197, 0.9, 4, 1.4, 2.0, 4.4),
        (17, 0.9, 5, 1.5, 3.0, 6.5), (0, 0.9, 5, 1.6, 2.4, 5.5), (343, 0.9, 4, 1.4, 2.0, 4.4)]):
    column_cluster(th, fr, n, r, hmin, hmax, SEED + 60 + k)
# front: short stubs with gaps
for k, th in enumerate(range(214, 330, 9)):
    if th in (250, 251, 252, 253, 289, 290, 291, 292, 293) or rng.random() < 0.25:
        continue
    if abs(th - 251) < 5 or abs(th - 291) < 5:
        continue
    fr = rng.uniform(0.92, 0.95)
    edge = min(abs(th - 214), abs(th - 326)) / 56     # 0 at the corners -> taller there
    h = 1.2 + 2.2 * max(0.0, 1 - edge * 2.2) + rng.uniform(0, 0.8)
    x, y = polar(th + rng.uniform(-2, 2), fr)
    hex_col(x, y, rng.uniform(1.0, 1.4), h, SEED + 90 + k)
    if rng.random() < 0.5:
        x2, y2 = polar(th + 4, fr - 0.06)
        hex_col(x2, y2, rng.uniform(0.8, 1.0), h * 0.55, SEED + 95 + k)
cols_obj = L.bm_to_obj(f"{MAP}_Columns", col_bm, MATS, PROPS)
made.append(cols_obj)
COLS = Surf([cols_obj])
for k, (a, b, r) in enumerate(col_axes):
    if b.z - a.z > 3.2 and k % 2 == 0:
        vein(LAVA, COLS, a + Vector((0, 0, 0.5)), b, 0.2, t0=0.05, t1=0.8, n=6, zig=r * 0.12, lift=0.08, seed=k,
             reach=r + 3)

# ---------------------------------------------------------------------------
# obsidian spike clusters with glowing veins
# ---------------------------------------------------------------------------


def obsidian_cluster(name, th, fr, s, seed):
    r2 = random.Random(seed)
    cx, cy = polar(th, fr)
    specs = [((0, 0), 0.95, 6.2, 0.08), ((0.95, 0.45), 0.7, 4.3, 0.32), ((-0.85, 0.35), 0.62, 3.6, 0.38),
             ((0.35, -0.85), 0.5, 2.6, 0.45), ((-0.45, -0.7), 0.42, 2.0, 0.5)]
    objs = []
    for i, ((ox, oy), r, h, tilt) in enumerate(specs):
        o = rot2(Vector((ox, oy)), r2.uniform(0, 6.28)) * s
        x, y = cx + o.x, cy + o.y
        z = ground(x, y) - 0.45
        ang = math.atan2(o.y, o.x) if o.length > 1e-3 else r2.uniform(0, 6.28)
        # tilt away from the cluster centre
        rot = Matrix.Rotation(ang, 4, "Z") @ Matrix.Rotation(tilt, 4, "Y") @ Matrix.Rotation(-ang, 4, "Z")
        m = Matrix.Translation((x, y, z)) @ rot @ Matrix.Rotation(r2.uniform(0, 6.28), 4, "Z")
        bm = bmesh.new()
        L.cyl_bm(bm, r * s, r * s * 0.1, h * s * r2.uniform(0.9, 1.1), segs=5, matrix=m, mat_index=I_OBS,
                 jitter=0.06 * s, seed=seed + i)
        ob = L.bm_to_obj(f"{name}_{i}", bm, MATS, PROPS)
        objs.append(ob)
        if i < 3:
            A = m @ Vector((0, 0, 0))
            B = m @ Vector((0, 0, h * s))
            vein(LAVA, Surf([ob]), A, B, 0.13 * s + 0.06, t0=0.12, t1=0.72, n=5, zig=r * s * 0.1, lift=0.07, seed=seed + i,
                 reach=r * s + 2)
    EXCLUDE.append((cx, cy, 2.2 * s))
    return objs


for k, (th, fr, s) in enumerate([(228, 0.86, 0.95), (312, 0.86, 0.85), (189, 0.76, 0.75), (352, 0.76, 0.8),
                                 (104, 0.5, 0.55), (150, 0.62, 0.6)]):
    made.extend(obsidian_cluster(f"{MAP}_Obsidian_{k}", th, fr, s, SEED + 300 + k * 7))

# ---------------------------------------------------------------------------
# charred dead trees
# ---------------------------------------------------------------------------


def dead_tree(name, loc, h, seed):
    r2 = random.Random(seed)
    bm = bmesh.new()
    x0, y0, z0 = loc
    lean = Vector((r2.uniform(-0.4, 0.4), r2.uniform(-0.4, 0.4), 0))
    spine = [Vector((0, 0, -0.5)), Vector((0.2, 0.1, h * 0.42)) + lean * 0.5, Vector((-0.1, 0.25, h * 0.75)) + lean,
             Vector((0.25, 0.15, h)) + lean * 1.4]
    radii = [0.75, 0.52, 0.34, 0.1]
    for i in range(3):
        limb(bm, spine[i], spine[i + 1] + (spine[i + 1] - spine[i]).normalized() * 0.15, radii[i], radii[i + 1],
             I_CHAR)
    for i in range(4):
        a = i * math.pi / 2 + r2.uniform(-0.3, 0.3)
        limb(bm, (0, 0, 0.7), (math.cos(a) * 1.5, math.sin(a) * 1.5, -0.35), 0.42, 0.08, I_CHAR, segs=5)
    for i, (t, L_, up_) in enumerate([(0.45, 2.6, 0.9), (0.62, 2.2, 1.1), (0.8, 1.8, 1.0), (0.55, 1.6, 0.7)]):
        a = i * 2.2 + r2.uniform(-0.4, 0.4)
        k = min(2, int(t * 3))
        p = spine[k].lerp(spine[k + 1], t * 3 - k)
        q = p + Vector((math.cos(a) * L_, math.sin(a) * L_, up_ * L_ * 0.8))
        limb(bm, p, q, 0.24, 0.05, I_CHAR, segs=5)
        if i < 2:
            q2 = p.lerp(q, 0.55)
            limb(bm, q2, q2 + Vector((math.cos(a + 0.9) * 0.9, math.sin(a + 0.9) * 0.9, 0.8)), 0.12, 0.03, I_CHAR,
                 segs=4)
    L.transform_bm(bm, loc=(x0, y0, z0), rot_z=r2.uniform(0, 6.28))
    ob = L.bm_to_obj(name, bm, MATS, PROPS)
    vein(LAVA, Surf([ob]), Vector((x0, y0, z0 + 0.3)), Vector((x0, y0, z0 + h * 0.4)), 0.18, t0=0.05, t1=0.95,
         n=6, zig=0.2, seed=seed, reach=3)
    return ob


for k, (th, fr, h) in enumerate([(9, 0.8, 7.5), (171, 0.8, 8.0), (207, 0.79, 6.0), (36, 0.72, 5.5)]):
    x, y = polar(th, fr)
    made.append(dead_tree(f"{MAP}_DeadTree_{k}", (x, y, ground(x, y)), h, SEED + 700 + k))
    EXCLUDE.append((x, y, 1.8))

# ---------------------------------------------------------------------------
# mining equipment
# ---------------------------------------------------------------------------


def derrick(name, loc, rot_z, H=10.5, B=2.2, T=1.05):
    bm = bmesh.new()
    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]

    def leg(c, z):
        f = B + (T - B) * (z / H)
        return Vector((c[0] * f, c[1] * f, z))
    for c in corners:
        beam(bm, leg(c, -0.4), leg(c, H + 0.25), 0.44, I_WOOD)
    levels = [0.5, 3.8, 7.2, H]
    for z in levels:
        for i in range(4):
            a, b = leg(corners[i], z), leg(corners[(i + 1) % 4], z)
            d = (b - a).normalized()
            beam(bm, a - d * 0.3, b + d * 0.3, 0.3, I_WOOD)
    for j, (z0, z1) in enumerate(zip(levels[:-1], levels[1:])):
        for i in range(4):
            c0, c1 = corners[i], corners[(i + 1) % 4]
            if (i + j) % 2 == 0:
                beam(bm, leg(c0, z0 + 0.1), leg(c1, z1 - 0.1), 0.22, I_WOOD)
            else:
                beam(bm, leg(c1, z0 + 0.1), leg(c0, z1 - 0.1), 0.22, I_WOOD)
    # platform + head frame + sheave wheel
    L.box_bm(bm, (2 * T + 1.3, 2 * T + 1.3, 0.3), loc=(0, 0, H + 0.4), chamfer=0.08, mat_index=I_CUT)
    for sx in (-1, 1):
        beam(bm, (sx * (T + 0.1), 0, H + 0.5), (sx * 0.55, 0, H + 3.3), 0.3, I_WOOD)
    beam(bm, (-0.95, 0, H + 3.3), (0.95, 0, H + 3.3), 0.34, I_WOOD)
    wheel_m = Matrix.Translation((-0.18, 0, H + 2.6)) @ Matrix.Rotation(math.pi / 2, 4, "Y")
    L.cyl_bm(bm, 0.95, 0.95, 0.36, segs=10, matrix=wheel_m, mat_index=I_METAL)
    L.cyl_bm(bm, 0.28, 0.28, 0.6, segs=6, matrix=Matrix.Translation((-0.3, 0, H + 2.6)) @
             Matrix.Rotation(math.pi / 2, 4, "Y"), mat_index=I_CUT)
    # chain down the middle with a small ore bucket
    beam(bm, (0, -0.95, H + 2.6), (0, -0.95, 4.3), 0.13, I_METAL)
    L.cyl_bm(bm, 0.5, 0.62, 0.9, segs=8, matrix=Matrix.Translation((0, -0.95, 3.4)), mat_index=I_METAL)
    # ladder up one leg face
    for z in [0.9 + 0.8 * i for i in range(11)]:
        f = B + (T - B) * (z / H)
        beam(bm, (-0.45, -f - 0.18, z), (0.45, -f - 0.18, z), 0.12, I_CUT)
    for sx in (-1, 1):
        beam(bm, (sx * 0.5, -B - 0.18, 0), (sx * 0.5, -T - 0.18, H), 0.14, I_WOOD)
    L.transform_bm(bm, loc=loc, rot_z=rot_z)
    return L.bm_to_obj(name, bm, MATS, PROPS)


def crane(name, loc, rot_z):
    bm = bmesh.new()
    lv = bmesh.new()
    beam(bm, (0, 0, -0.4), (0, 0, 8.4), 0.52, I_WOOD)
    beam(bm, (-1.7, 0, 0.15), (1.7, 0, 0.15), 0.42, I_WOOD)
    beam(bm, (0, -1.7, 0.15), (0, 1.7, 0.15), 0.42, I_WOOD)
    for sx, sy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        beam(bm, (sx * 1.4, sy * 1.4, 0.3), (0, 0, 2.2), 0.24, I_WOOD)
    beam(bm, (-0.8, 0, 7.9), (5.0, 0, 7.9), 0.46, I_WOOD)
    beam(bm, (0, 0, 5.4), (2.4, 0, 7.8), 0.3, I_WOOD)
    L.cyl_bm(bm, 0.42, 0.42, 0.26, segs=8, matrix=Matrix.Translation((4.4, -0.13, 7.45)) @
             Matrix.Rotation(-math.pi / 2, 4, "X"), mat_index=I_METAL)
    # chain links
    z = 7.1
    i = 0
    while z > 4.0:
        rot = Matrix.Rotation((math.pi / 2) * (i % 2), 4, "Z")
        L.box_bm(bm, (0.12, 0.34, 0.5), loc=(4.4, 0, z), rot=rot, mat_index=I_METAL)
        z -= 0.4
        i += 1
    # bucket with bail and ore
    L.cyl_bm(bm, 0.7, 0.92, 1.25, segs=8, matrix=Matrix.Translation((4.4, 0, 2.35)), mat_index=I_METAL)
    L.cyl_bm(bm, 0.95, 0.95, 0.14, segs=8, matrix=Matrix.Translation((4.4, 0, 3.45)), mat_index=I_WOOD)
    for sx in (-1, 1):
        beam(bm, (4.4 + sx * 0.9, 0, 3.5), (4.4, 0, 4.1), 0.09, I_METAL)
    for j in range(4):
        a = j * 1.7
        stone(bm, (4.4 + math.cos(a) * 0.4, math.sin(a) * 0.4, 3.62), 0.55, SEED + 800 + j, I_ORE, squash=0.8)
    b = bmesh.new()
    bmesh.ops.create_icosphere(b, subdivisions=1, radius=0.28)
    L.transform_bm(b, loc=(4.35, 0.1, 3.85))
    L.merge_bm(lv, b, 0)
    L.transform_bm(bm, loc=loc, rot_z=rot_z)
    L.transform_bm(lv, loc=loc, rot_z=rot_z)
    L.merge_bm(LAVA, lv, 0)
    return L.bm_to_obj(name, bm, MATS, PROPS)


def mine_cart(name, loc, rot_z):
    bm = bmesh.new()
    lv = bmesh.new()
    for sy in (-0.78, 0.78):
        L.box_bm(bm, (8.5, 0.2, 0.22), loc=(0, sy, 0.3), mat_index=I_METAL)
    for i in range(6):
        L.box_bm(bm, (0.55, 2.4, 0.2), loc=(-3.6 + i * 1.45, 0, 0.12), rot=Matrix.Rotation(0.04 * (i % 3 - 1), 4, "Z"),
                 mat_index=I_WOOD)
    for sx in (-1.0, 1.0):
        for sy in (-0.78, 0.78):
            L.cyl_bm(bm, 0.46, 0.46, 0.24, segs=8, matrix=Matrix.Translation((sx, sy - 0.12 * (1 if sy < 0 else -1), 0.86))
                     @ Matrix.Rotation(math.pi / 2 * (1 if sy > 0 else -1), 4, "X"), mat_index=I_METAL)
    body = bmesh.new()
    bmesh.ops.create_cube(body, size=1.0)
    for v in body.verts:
        if v.co.z > 0:
            v.co.x *= 1.14
            v.co.y *= 1.18
    L.transform_bm(body, loc=(0, 0, 1.0 + 0.65), scale=(2.8, 1.65, 1.3))
    L.merge_bm(bm, body, I_WOOD)
    for sx in (-1, 1):
        L.box_bm(bm, (0.18, 2.0, 1.36), loc=(sx * 1.2, 0, 1.66), mat_index=I_METAL)
    for sy in (-1.0, 1.0):      # rim frame (open top)
        L.box_bm(bm, (3.3, 0.14, 0.18), loc=(0, sy * 0.99, 2.3), mat_index=I_METAL)
    for sx in (-1.0, 1.0):
        L.box_bm(bm, (0.14, 2.1, 0.18), loc=(sx * 1.6, 0, 2.3), mat_index=I_METAL)
    L.box_bm(bm, (3.0, 1.8, 0.1), loc=(0, 0, 2.15), mat_index=I_ORE)
    ore_spots = [(-1.0, -0.45), (-1.0, 0.45), (0.0, -0.5), (0.0, 0.5), (1.0, -0.45), (1.0, 0.45),
                 (-0.5, 0.0), (0.5, 0.0), (0.0, 0.0)]
    for j, (ox, oy) in enumerate(ore_spots):
        zz = 2.45 + (0.45 if j >= 6 else 0.0) + (0.3 if j == 8 else 0.0)
        stone(bm, (ox, oy, zz), rng.uniform(0.8, 1.0), SEED + 850 + j, I_ORE, squash=0.8)
    for (dx, dy, dz) in [(0.55, 0.25, 3.0), (-0.65, -0.3, 2.85)]:
        b = bmesh.new()
        bmesh.ops.create_icosphere(b, subdivisions=1, radius=0.3)
        L.transform_bm(b, loc=(dx, dy, dz))
        L.merge_bm(lv, b, 0)
    L.transform_bm(bm, loc=loc, rot_z=rot_z, scale=(1.25, 1.25, 1.25))
    L.transform_bm(lv, loc=loc, rot_z=rot_z, scale=(1.25, 1.25, 1.25))
    L.merge_bm(LAVA, lv, 0)
    return L.bm_to_obj(name, bm, MATS, PROPS)


def crate(bm, loc, size, rot_z):
    L.box_bm(bm, (size, size, size), loc=(loc[0], loc[1], loc[2] + size / 2), rot=Matrix.Rotation(rot_z, 4, "Z"),
             chamfer=size * 0.08, mat_index=I_WOOD)
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
        L.cyl_bm(bm, r * 0.93 + 0.05, r * 0.95 + 0.05, h * 0.08, segs=segs,
                 matrix=Matrix.Translation((loc[0], loc[1], loc[2] + h * z - h * 0.04)), mat_index=I_METAL)
    L.cyl_bm(bm, r * 0.84, r * 0.84, 0.06, segs=segs, matrix=Matrix.Translation((loc[0], loc[1], loc[2] + h)),
             mat_index=I_CUT)


# derrick: back-left, just inside the lava channel
dx_, dy_ = polar(134, 0.5)
made.append(derrick(f"{MAP}_Derrick", (dx_, dy_, ground(dx_, dy_)), facing_center(dx_, dy_) + math.pi / 2 + 0.35))
EXCLUDE.append((dx_, dy_, 3.6))
# supplies beside it
sup = bmesh.new()
face = facing_center(dx_, dy_)
for (a, b_, dz, s, r) in [(2.2, -3.4, 0, 1.6, 0.3), (3.6, -2.6, 0, 1.3, 0.8), (2.5, -3.2, 1.6, 1.1, 1.1)]:
    px = dx_ + a * math.cos(face) - b_ * math.sin(face)
    py = dy_ + a * math.sin(face) + b_ * math.cos(face)
    crate(sup, (px, py, ground(px, py) + dz), s, r)
    EXCLUDE.append((px, py, 1.4))
for (a, b_) in [(0.4, 3.6), (1.6, 4.0)]:
    px = dx_ + a * math.cos(face) - b_ * math.sin(face)
    py = dy_ + a * math.sin(face) + b_ * math.cos(face)
    barrel(sup, (px, py, ground(px, py) - 0.05), h=1.7, r=0.72)
    EXCLUDE.append((px, py, 1.2))
made.append(L.bm_to_obj(f"{MAP}_Supplies", sup, MATS, PROPS))

# gallows crane: back-right, arm swinging toward the camera side
gx, gy = polar(44, 0.5)
made.append(crane(f"{MAP}_Crane", (gx, gy, ground(gx, gy)), math.radians(200)))
EXCLUDE.append((gx, gy, 3.0))
EXCLUDE.append((gx + math.cos(math.radians(200)) * 4.4, gy + math.sin(math.radians(200)) * 4.4, 1.5))

# mine cart on a short rail, front-right
mx, my = polar(326, 0.6)
made.append(mine_cart(f"{MAP}_MineCart", (mx, my, ground(mx, my)), math.radians(14)))
EXCLUDE.append((mx, my, 4.6))

# rubble piles + cooled vents
rub = bmesh.new()
for k, (th, fr, n, s) in enumerate([(250, 0.42, 5, 1.0), (300, 0.3, 4, 0.8), (198, 0.4, 4, 0.9),
                                    (18, 0.45, 5, 0.9), (112, 0.3, 3, 0.7), (270, 0.72, 3, 0.8),
                                    (345, 0.4, 3, 0.7)]):
    cx, cy = polar(th, fr)
    r2 = random.Random(SEED + 900 + k)
    for i in range(n):
        a = r2.uniform(0, 6.28)
        rr = r2.uniform(0.0, 1.2) * s if i else 0
        x, y = cx + math.cos(a) * rr, cy + math.sin(a) * rr
        sz = (1.3 if i == 0 else r2.uniform(0.45, 0.85)) * s
        stone(rub, (x, y, ground(x, y) + sz * 0.1), sz, SEED + 950 + k * 10 + i, I_BASALT, squash=0.62,
              rot_z=r2.uniform(0, 6), blocky=r2.random() < 0.6)
made.append(L.bm_to_obj(f"{MAP}_Rubble", rub, MATS, PROPS))

vent_bm = bmesh.new()
for k, (th, fr) in enumerate([(215, 0.55), (15, 0.25)]):
    x, y = polar(th, fr)
    z = ground(x, y)
    L.cyl_bm(vent_bm, 2.0, 0.75, 1.0, segs=7, matrix=Matrix.Translation((x, y, z - 0.15)), mat_index=I_BASALT,
             jitter=0.12, seed=k)
    L.cyl_bm(vent_bm, 0.8, 0.55, 0.12, segs=7, matrix=Matrix.Translation((x, y, z + 0.8)), mat_index=I_SCORCH)
    L.cyl_bm(LAVA, 0.5, 0.42, 0.14, segs=7, matrix=Matrix.Translation((x, y, z + 0.84)))
    EXCLUDE.append((x, y, 2.4))
made.append(L.bm_to_obj(f"{MAP}_Vents", vent_bm, MATS, PROPS))

# glowing seep lines along the rim base, peeking out between columns
for k, (th0, th1, fr) in enumerate([(156, 204, 0.84), (336, 384, 0.84), (216, 240, 0.88), (262, 284, 0.88),
                                    (300, 324, 0.88)]):
    r2 = random.Random(SEED + 1200 + k)
    th = th0
    while th < th1:
        span = r2.uniform(6, 11)
        pts = []
        for i in range(6):
            a = th + span * i / 5
            ff = fr + 0.015 * math.sin(i * 1.7 + k)
            x, y = polar(a % 360, ff)
            pts.append(Vector((x, y, ground(x, y))))
        n = len(pts)
        ribbon(LAVA, pts, [up] * n, [0.18 + 0.22 * math.sin(math.pi * i / (n - 1)) for i in range(n)], lift=0.09,
               drape=BODY)
        th += span + r2.uniform(3, 7)

# ---------------------------------------------------------------------------
# glowing floor cracks (+ two that run over the front lip and down the rock)
# ---------------------------------------------------------------------------


def blocked(p):
    for (x, y, r) in EXCLUDE:
        if (p.x - x) ** 2 + (p.y - y) ** 2 < r * r:
            return True
    return p.length > R(math.atan2(p.y, p.x)) * 0.975


def crack(start, direction, segs, seg_len, w0, seed, branch=True, allow_start_blocked=False):
    r2 = random.Random(seed)
    d = Vector(direction).normalized()
    pts = [Vector(start)]
    for i in range(segs):
        d = rot2(d, r2.uniform(-0.55, 0.55))
        p = pts[-1] + d * seg_len * r2.uniform(0.8, 1.2)
        if blocked(p):
            break
        pts.append(p)
    if len(pts) < 3:
        return
    n = len(pts)
    ws = [max(0.08, w0 * (1 - 0.8 * i / (n - 1))) for i in range(n)]
    p3 = [Vector((p.x, p.y, ground(p.x, p.y))) for p in pts]
    ribbon(LAVA, p3, [up] * n, ws, lift=0.08, drape=BODY)
    if branch and n > 4:
        j = r2.randint(1, n - 3)
        dd = rot2((pts[j + 1] - pts[j]).normalized(), r2.choice((-1, 1)) * r2.uniform(0.7, 1.1))
        crack(pts[j], dd, r2.randint(2, 4), seg_len * 0.8, ws[j] * 0.7, seed + 77, branch=False)


# thin dark plate cracks (baked, non-glowing) so the floor reads as cracked slabs
plate_bm = bmesh.new()
pr = random.Random(SEED + 1300)
for k in range(16):
    th, fr = pr.uniform(0, 360), pr.uniform(0.1, 0.8)
    if 40 < th < 140 and fr > 0.45:
        continue
    p = Vector(polar(th, fr))
    d = rot2(Vector((1, 0)), pr.uniform(0, 6.28))
    pts = [p]
    for i in range(pr.randint(4, 8)):
        d = rot2(d, pr.uniform(-0.7, 0.7))
        q = pts[-1] + d * pr.uniform(1.4, 2.2)
        if blocked(q):
            break
        pts.append(q)
    if len(pts) < 3:
        continue
    n = len(pts)
    ribbon(plate_bm, [Vector((q.x, q.y, ground(q.x, q.y))) for q in pts], [up] * n,
           [0.22 * (0.4 + 0.6 * math.sin(math.pi * i / (n - 1))) + 0.06 for i in range(n)], lift=0.05,
           mat=I_SCORCH, drape=BODY)
made.append(L.bm_to_obj(f"{MAP}_PlateCracks", plate_bm, MATS, PROPS))

crack_starts = [(214, 0.93, 7), (236, 0.93, 8), (262, 0.93, 6), (278, 0.9, 7), (304, 0.93, 7), (336, 0.9, 6),
                (193, 0.7, 5), (8, 0.62, 5), (240, 0.2, 5), (320, 0.18, 4), (100, 0.22, 4), (170, 0.3, 5)]
for k, (th, fr, segs) in enumerate(crack_starts):
    sx, sy = polar(th, fr)
    inward = Vector((-sx, -sy))
    if fr < 0.4:
        inward = rot2(Vector((1, 0)), rng.uniform(0, 6.28))
    crack((sx, sy), inward, segs, 1.5, 0.6 if fr > 0.5 else 0.45, SEED + 1000 + k)

# front cracks that reach the lip and pour down the underside
for k, (th, zmin, seg) in enumerate([(251, -12.5, 6), (291, -9.5, 5)]):
    sx, sy = polar(th, 0.97)
    pts2 = [Vector((sx, sy))]
    d = Vector((-sx, -sy)).normalized()
    r2 = random.Random(SEED + 1100 + k)
    for i in range(seg):
        d = rot2(d, r2.uniform(-0.45, 0.45))
        p = pts2[-1] + d * 1.5
        if blocked(p) and i > 1:
            break
        pts2.append(p)
    floor_part = [Vector((p.x, p.y, ground(p.x, p.y))) for p in reversed(pts2)]   # interior -> lip
    nf = len(floor_part)
    fw = [0.25 + 0.5 * i / max(1, nf - 1) for i in range(nf)]
    sp, sn, sw = spill(th, -0.15, zmin, 0.85, 0.35, step=0.5, meander=1.8, seed=k * 3)
    ribbon(LAVA, floor_part + sp, [up] * nf + sn, fw + sw, lift=0.1, drape=BODY,
           drape_flags=[True] * nf + [False] * len(sp))
    if sp:
        drip_tip(sp[-1], sn[-1], sw[-1] + 0.2)

# ---------------------------------------------------------------------------
# lava object (its own small emissive atlas so Roblox can set it to Neon)
# ---------------------------------------------------------------------------
lava_obj = L.bm_to_obj(f"{MAP}_Lava", LAVA, [LAVA_MAT], GLOW)

# ---------------------------------------------------------------------------
# join + bake the procedural parts into one atlas mesh
# ---------------------------------------------------------------------------
island_mesh = L.join(f"{MAP}_Island", [island] + made, PROPS)
for ob in (island_mesh, lava_obj):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
L.bake_atlas(island_mesh, OUT_TEX / f"{STEM}-island-atlas.png", size=2048)
print("BAKED", island_mesh.name, flush=True)
L.bake_atlas(lava_obj, OUT_TEX / f"{STEM}-lava-atlas.png", size=512, margin=4)
lava_baked = lava_obj.data.materials[0]
lava_baked.name = "VC_Lava_Neon"
nt = lava_baked.node_tree
bs = nt.nodes["Principled BSDF"]
tex = [n for n in nt.nodes if n.type == "TEX_IMAGE"][0]
nt.links.new(tex.outputs["Color"], bs.inputs["Emission Color"])
bs.inputs["Emission Strength"].default_value = LAVA_STRENGTH
print("BAKED", lava_obj.name, flush=True)

# ---------------------------------------------------------------------------
# previews (dusk sky, warm low sun, orange fill lights near the lava)
# ---------------------------------------------------------------------------
L.setup_preview(sky_top="#4e4467", sky_horizon="#e3916a", sun_energy=3.3, sun_rot=(0.98, -0.2, -0.5),
                sun_color="#f6cfc8", fill=0.62)


def glow_light(name, loc, energy, radius=1.5):
    ld = bpy.data.lights.new(name, "POINT")
    ld.energy = energy
    ld.color = L.srgb("#ff8a3a")[:3]
    ld.shadow_soft_size = radius
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    L.link(ob, GLOW)
    return ob


glow_light("Glow_Crater", (VX, VY - 1.5, V_H + 1.5), 3500, 2.0)
for i, (base, u, ztop) in enumerate(fall_bases):
    glow_light(f"Glow_Fall_{i}", (base.x - u.x * 1.5, base.y - u.y * 1.5, 2.5), 2200)
for i in (len(chan_pts) // 4, len(chan_pts) // 2, 3 * len(chan_pts) // 4):
    p = chan_pts[i]
    glow_light(f"Glow_Channel_{i}", (p.x, p.y - 1.0, p.z + 2.0), 900)
for i, th in enumerate((29, 151, 251, 291)):
    x, y = polar(th, 1.12)
    glow_light(f"Glow_Spill_{i}", (x, y, -4.0), 1200 if i < 2 else 700)

wn = scene.world.node_tree
sky_ramp = [n for n in wn.nodes if n.type == "VALTORGB"][0].color_ramp
sky_ramp.elements[0].position = 0.24
sky_ramp.elements[0].color = L.srgb("#e38c62")
sky_ramp.elements[1].position = 0.5
sky_ramp.elements[1].color = L.srgb("#5a4a74")
mid = sky_ramp.elements.new(0.37)
mid.color = L.srgb("#b57378")

hero = L.camera("Cam_Hero", (0, -118, 34), (0, 0, -7), lens=35)
L.render(hero, OUT_PREV / f"{STEM}-hero.png")
close = L.camera("Cam_Close", (-8, -58, 40), (0, 4, 1), lens=35)
L.render(close, OUT_PREV / f"{STEM}-closeup.png")
side = L.camera("Cam_Side", (112, -52, 8), (0, 0, -8), lens=35)
L.render(side, OUT_PREV / f"{STEM}-side.png")

# ---------------------------------------------------------------------------
# export + report
# ---------------------------------------------------------------------------
export_objs = [island_mesh, lava_obj]
L.export(export_objs, OUT_FBX / f"{STEM}-mini-island.fbx", OUT_GLB / f"{STEM}-mini-island.glb")

bb = [island_mesh.matrix_world @ Vector(c) for c in island_mesh.bound_box]
report = {
    "map": MAP,
    "island_mesh": {"name": island_mesh.name, "triangles": L.tri_count(island_mesh),
                    "vertices": len(island_mesh.data.vertices),
                    "extent_studs": [round(max(v[i] for v in bb) - min(v[i] for v in bb), 2) for i in range(3)],
                    "atlas": f"textures/{STEM}-island-atlas.png"},
    "lava_mesh": {"name": lava_obj.name, "triangles": L.tri_count(lava_obj),
                  "vertices": len(lava_obj.data.vertices),
                  "atlas": f"textures/{STEM}-lava-atlas.png",
                  "note": "emissive; set MeshPart Material to Neon (orange) in Roblox"},
    "instances": {},
}
report["total_triangles"] = report["island_mesh"]["triangles"] + report["lava_mesh"]["triangles"]
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
