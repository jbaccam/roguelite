"""Poseidon's Trident: Godly weapon (RARITY_GODLY_ARMOR.md section 9: thrown + melee; where it lands a
tidal wave rolls out and washes enemies away).

Run in background Blender 5.2 only (never the user's open scene):
  blender -b --factory-startup --threads 2 --python build_poseidons_trident.py

Environment switches (all optional):
  MODE=quick     build the model and render flat review shots only (no bake, no exports)
  MODE=full      (default) build, bake the painted texture, export, validate, render everything
  OUT=<dir>      where quick renders go (default: this folder)
  SHOTS=a,b      quick mode: which review shots to render (catalog,front,side,head)

Pipeline copied (not imported) from the approved Reaper's Scythe generator
(weapon-models/godly/reapers-scythe/build_reapers_scythe.py): bmesh tube/lathe/loft helpers, bevel +
weighted-normal finish, painterly bake to one 1024 BaseColor.png, separate Neon glow meshes, the
catalogue review stage, exports, validation and the composites.

Design:
  silhouette  three thick barbed prongs; the two side prongs grow out of the crests of two big gold
              waves that curl inward over a large glowing pearl; a teal under-wave rolls out beneath
  palette     deep-sea gold (brown shading), teal + coral enamel, abyss-navy shaft with a scale motif
  motif       breaking-wave scrolls, raised enamel inlays following each wave and spearhead
  glow        aqua Neon edge bands on every spearhead, barb and wave lip; the pearl core; butt pearl
  hold/throw  balanced spear grip: coral-braided grip at the balance point, weighted scalloped butt cap

Axes: Blender +z up, prongs spread along x, flat faces look along +/-y (front = -y).
1 Blender unit = 1 Roblox stud. Studio axes are (-x, z, y) of Blender.
"""
import bpy, bmesh, math, json, os, sys, time
import numpy as np
from mathutils import Vector, Matrix
from pathlib import Path

T0 = time.time()
ROOT = Path(__file__).resolve().parent
NAME = "PoseidonsTrident"
MODE = os.environ.get("MODE", "full")
OUT = Path(os.environ.get("OUT", str(ROOT)))
OUT.mkdir(parents=True, exist_ok=True)
SHOTS = [s for s in os.environ.get("SHOTS", "catalog,front,side").split(",") if s]
BAKE_SIZE = 1024
TARGET_HEIGHT = 6.4          # hero size in studs (a trident towers over the 5-stud player; Studio sets play size)
BLEED_K, BLEED_STRENGTH = 0.18, 0.55
PREVIEW_ANGLE = -24


def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)


def V(*a):
    return Vector(a)


# ---------------------------------------------------------------------------
# Palette. Slot index = material index on every textured mesh.
# ---------------------------------------------------------------------------
PAL = [
    ("Gold", (190, 128, 38), [(0.22, (80, 42, 10)), (0.5, (176, 118, 34)), (0.82, (240, 202, 112))], (255, 236, 170)),
    ("Bronze", (128, 70, 26), [(0.3, (66, 32, 10)), (0.55, (116, 62, 22)), (0.8, (162, 98, 40))], (230, 170, 100)),
    ("Teal", (26, 140, 150), [(0.28, (10, 80, 96)), (0.52, (22, 134, 146)), (0.8, (70, 196, 190))], (170, 250, 240)),
    ("Coral", (160, 44, 36), [(0.28, (100, 20, 18)), (0.52, (158, 42, 34)), (0.8, (204, 78, 58))], (250, 150, 120)),
    ("Abyss", (14, 40, 74), [(0.28, (5, 18, 40)), (0.52, (12, 38, 72)), (0.8, (26, 70, 112))], (110, 186, 236)),
    ("Socket", (10, 26, 34), [(0.4, (6, 16, 22)), (0.75, (18, 40, 50))], (60, 110, 120)),
    ("Scale", (14, 74, 84), [(0.28, (5, 32, 44)), (0.52, (12, 70, 82)), (0.8, (36, 128, 126))], (120, 236, 214)),
    ("Ivory", (236, 226, 198), [(0.3, (196, 176, 136)), (0.55, (234, 220, 188)), (0.8, (252, 246, 228))], (255, 255, 240)),
    ("Crimson", (120, 18, 32), [(0.28, (58, 6, 16)), (0.52, (116, 18, 32)), (0.8, (166, 40, 50))], (236, 120, 120)),
]
M_GOLD, M_BRONZE, M_TEAL, M_CORAL, M_ABYSS, M_SOCK, M_SCALE, M_IVORY, M_CRIMSON = range(len(PAL))
GLOW = (0, 132, 172)       # Roblox Neon, aqua sea-glow
CORE = (176, 255, 240)      # Roblox Neon, pale pearl core / glints


def lin(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgba(c, a=1.0):
    return (lin(c[0]), lin(c[1]), lin(c[2]), a)


def lerp(a, b, t):
    return a + (b - a) * t


# ---------------------------------------------------------------------------
# bmesh primitives (from the scythe)
# ---------------------------------------------------------------------------
def loft(bm, rings, closed=True, caps=True, mat=0, recalc=True):
    vr = [[bm.verts.new(p) for p in r] if isinstance(r, (list, tuple)) else [bm.verts.new(r)] for r in rings]
    faces = []
    for A, B in zip(vr, vr[1:]):
        if len(A) == 1 and len(B) == 1:
            continue
        n = max(len(A), len(B))
        for s in (range(n) if closed else range(n - 1)):
            s2 = (s + 1) % n
            if len(B) == 1:
                f = [A[s], A[s2], B[0]]
            elif len(A) == 1:
                f = [A[0], B[s2], B[s]]
            else:
                f = [A[s], A[s2], B[s2], B[s]]
            faces.append(bm.faces.new(f))
    if closed and caps:
        if len(vr[0]) > 2:
            faces.append(bm.faces.new(vr[0][::-1]))
        if len(vr[-1]) > 2:
            faces.append(bm.faces.new(vr[-1]))
    for f in faces:
        f.material_index = mat
    if recalc:
        bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def frames(pts, up=V(0, 1, 0)):
    n = len(pts)
    T = []
    for k in range(n):
        a, b = pts[max(k - 1, 0)], pts[min(k + 1, n - 1)]
        T.append((b - a).normalized())
    nn = T[0].cross(up)
    if nn.length < 1e-5:
        nn = T[0].cross(V(1, 0, 0))
    nn.normalize()
    N = []
    for t in T:
        nn = nn - t * nn.dot(t)
        if nn.length < 1e-6:
            nn = t.cross(up)
        nn.normalize()
        N.append(nn.copy())
    B = [t.cross(v) for t, v in zip(T, N)]
    return T, N, B


def tube(bm, pts, radii, sides=8, mat=0, flat=1.0, phase=0.0, section=None, up=V(0, 1, 0), caps=True, twist=0.0):
    """Tube along a centreline. radii entries: r, or (r_normal, r_binormal); 0 = pointed end."""
    T, N, B = frames(pts, up)
    sec = section or [(math.cos(phase + 2 * math.pi * s / sides), math.sin(phase + 2 * math.pi * s / sides))
                      for s in range(sides)]
    rings = []
    for k, p in enumerate(pts):
        r = radii[k]
        ra, rb = (r, r * flat) if not isinstance(r, (tuple, list)) else r
        if ra <= 1e-6 and rb <= 1e-6:
            rings.append(p.copy())
            continue
        ang = twist * k / max(1, len(pts) - 1)
        ca, sa = math.cos(ang), math.sin(ang)
        rings.append([p + N[k] * (a * ca - b * sa) * ra + B[k] * (a * sa + b * ca) * rb for a, b in sec])
    return loft(bm, rings, mat=mat, caps=caps)


def lathe(bm, prof, sides=8, M=None, mat=0, phase=None, sy=1.0, ripple=0.0, lobes=0):
    """Surface of revolution about local +z; prof = [(radius, z)]. ripple/lobes scallop the radius."""
    M = M or Matrix()
    phase = math.pi / sides if phase is None else phase
    rings = []
    for r, z in prof:
        if r <= 1e-6:
            rings.append(M @ V(0, 0, z))
        else:
            ring = []
            for s in range(sides):
                a = phase + 2 * math.pi * s / sides
                rr = r * (1 + ripple * math.cos(lobes * (a - phase))) if lobes else r
                ring.append(M @ V(rr * math.cos(a), rr * sy * math.sin(a), z))
            rings.append(ring)
    return loft(bm, rings, mat=mat)


def box(bm, c, size, M=None, mat=0):
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    Mt = Matrix.Translation(c) @ (M or Matrix())
    r0 = [Mt @ V(-hx, -hy, -hz), Mt @ V(hx, -hy, -hz), Mt @ V(hx, hy, -hz), Mt @ V(-hx, hy, -hz)]
    r1 = [Mt @ V(-hx, -hy, hz), Mt @ V(hx, -hy, hz), Mt @ V(hx, hy, hz), Mt @ V(-hx, hy, hz)]
    return loft(bm, [r0, r1], mat=mat)


def basis(x, y, z):
    return Matrix((x, y, z)).transposed().to_4x4()


def sphere(bm, c, r, rings_n=7, sides=12, M=None, mat=0):
    prof = [(r * math.sin(math.pi * k / rings_n), -r * math.cos(math.pi * k / rings_n)) for k in range(rings_n + 1)]
    return lathe(bm, prof, sides=sides, M=Matrix.Translation(c) @ (M or Matrix()), mat=mat)


def catmull(ctrl, n):
    """Centripetal-ish Catmull-Rom resample of control points (Vectors) to n points, plus param t in [0,1]."""
    P = [ctrl[0] * 2 - ctrl[1]] + list(ctrl) + [ctrl[-1] * 2 - ctrl[-2]]
    segs = len(ctrl) - 1
    out, ts = [], []
    for k in range(n):
        u = k / (n - 1) * segs
        i = min(int(u), segs - 1)
        t = u - i
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        t2, t3 = t * t, t * t * t
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
        ts.append(u / segs)
    return out, ts


def interp(vals, t):
    """Piecewise-linear lookup of evenly spaced control values at t in [0,1]."""
    u = t * (len(vals) - 1)
    i = min(int(u), len(vals) - 2)
    return lerp(vals[i], vals[i + 1], u - i)


# ---------------------------------------------------------------------------
# Scene objects, modifiers
# ---------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.save_version = 0
scene = bpy.context.scene
ASSET = bpy.data.collections.new("ASSET export geometry")
REVIEW = bpy.data.collections.new("REVIEW not exported")
WORK = bpy.data.collections.new("WORK cutters")
for c in (ASSET, REVIEW, WORK):
    scene.collection.children.link(c)

MATS = []
for name, flat_c, ramp, edge in PAL:
    m = bpy.data.materials.new(f"{NAME}_{name}")
    m.use_nodes = True
    bs = m.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = rgba(flat_c)
    bs.inputs["Roughness"].default_value = 0.35 if name in ("Gold", "Bronze") else 0.5
    if name in ("Gold", "Bronze"):
        bs.inputs["Metallic"].default_value = 0.6
    MATS.append(m)


def emit_mat(name, col, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = (0, 0, 0, 1)
    bs.inputs["Emission Color"].default_value = rgba(col)
    bs.inputs["Emission Strength"].default_value = strength
    return m


GLOW_MAT = emit_mat(f"{NAME}_Glow", GLOW, 0.85)
CORE_MAT = emit_mat(f"{NAME}_GlowCore", CORE, 2.2)
PARTS = []


def new_bm():
    return bmesh.new()


def make_obj(name, bm, kind="tex", smooth=False, coll=None):
    bm.normal_update()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if kind in ("tex", "cut"):
        for m in MATS:
            me.materials.append(m)
    elif kind == "glow":
        me.materials.append(GLOW_MAT)
    elif kind == "core":
        me.materials.append(CORE_MAT)
    for p in me.polygons:
        p.use_smooth = smooth
    ob = bpy.data.objects.new(name, me)
    (coll or (WORK if kind == "cut" else ASSET)).objects.link(ob)
    ob["kind"] = kind
    if kind == "cut":
        ob.display_type = "WIRE"
        ob.hide_render = True
    else:
        PARTS.append(ob)
    return ob


def add_bevel(ob, width, segs=2, angle=30.0, profile=0.55, harden=True):
    m = ob.modifiers.new("Bevel", "BEVEL")
    m.width = width
    m.segments = segs
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle)
    m.profile = profile
    m.use_clamp_overlap = True
    m.harden_normals = harden and segs > 1
    m.miter_outer = "MITER_ARC"
    return m


def add_wn(ob):
    m = ob.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
    m.keep_sharp = True
    m.weight = 50
    m.mode = "FACE_AREA"
    return m


def hard(ob, width=0.012, segs=2, angle=30.0):
    for p in ob.data.polygons:
        p.use_smooth = True
    add_bevel(ob, width, segs=segs, angle=angle)
    add_wn(ob)
    return ob


def select_only(objs, active=None):
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def apply_mods(ob):
    select_only([ob])
    for m in list(ob.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=m.name)
        except RuntimeError as e:
            log("modifier apply failed", ob.name, m.name, e)
            ob.modifiers.remove(m)


def curve_mesh(name, paths, depth, mirror_y=False, mat=None, res=3):
    """Round-section gold wire along poly paths, converted to mesh (optionally mirrored to the far face)."""
    cu = bpy.data.curves.new(name + "Curve", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = depth
    cu.bevel_resolution = 0
    cu.resolution_u = res
    cu.use_fill_caps = True
    for pts in paths:
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for i, p in enumerate(pts):
            sp.points[i].co = (p.x, p.y, p.z, 1.0)
    ob = bpy.data.objects.new(name, cu)
    ASSET.objects.link(ob)
    if mirror_y:
        mir = ob.modifiers.new("MirrorY", "MIRROR")
        mir.use_axis = (False, True, False)
    select_only([ob])
    bpy.ops.object.convert(target="MESH")
    ob = bpy.context.object
    ob.data.materials.clear()
    for m in MATS:
        ob.data.materials.append(m)
    for p in ob.data.polygons:
        p.material_index = M_GOLD if mat is None else mat
        p.use_smooth = True
    ob["kind"] = "tex"
    PARTS.append(ob)
    add_wn(ob)
    return ob


def ring_band(bm, z, r_in, r_out, h, sides=10, mat=M_GOLD, crown=0.0, M=None):
    """Band around the shaft (local z axis); crown != 0 raises every other top/bottom vertex into points."""
    M = M or Matrix()
    rings = []
    n = sides * (2 if crown else 1)
    prof = [(r_in, -h / 2), (r_out, -h / 2 + 0.012), (r_out, h / 2 - 0.012), (r_in, h / 2)]
    for j, (r, dz) in enumerate(prof):
        ring = []
        for s in range(n):
            a = math.pi / n + 2 * math.pi * s / n
            zz = z + dz
            if crown and s % 2 == 0 and ((crown > 0 and j >= 2) or (crown < 0 and j < 2)):
                zz += crown
            ring.append(M @ V(r * math.cos(a), r * math.sin(a), zz))
        rings.append(ring)
    return loft(bm, rings, mat=mat)


# ---------------------------------------------------------------------------
# Layout (authored studs, normalised to TARGET_HEIGHT in full mode). Shaft axis is x = y = 0.
# ---------------------------------------------------------------------------
SHAFT_Z0, SHAFT_Z1 = 0.42, 3.40
GRIP_Z0, GRIP_Z1 = 2.10, 2.94            # coral braid = balanced spear grip (melee hold + throw)
PEARL_C, PEARL_R = V(0, 0, 4.32), 0.31
Y = V(0, 1, 0)


def shaft_r(z):
    t = (z - SHAFT_Z0) / (SHAFT_Z1 - SHAFT_Z0)
    return 0.195 - 0.018 * t


HEX_LENS = [(1, 0), (0.42, 0.82), (-0.42, 0.82), (-1, 0), (-0.42, -0.82), (0.42, -0.82)]   # sharp in-plane edges

# main breaking wave (right half; left = mirror): sweeps out of the beast's head, rises, curls inward over the
# pearl and ends in a needle; claw spikes rake up its outer crest
WAVE_CTRL = [(-0.06, 3.86), (0.28, 3.92), (0.58, 4.05), (0.80, 4.28), (0.94, 4.56), (0.92, 4.86),
             (0.74, 5.02), (0.52, 4.98), (0.40, 4.82), (0.42, 4.65), (0.56, 4.56)]
WAVE_R = [0.25, 0.245, 0.235, 0.22, 0.2, 0.175, 0.145, 0.11, 0.08, 0.05, 0.0]
WAVE_FLAT = 0.6
WAVE_CURL_C = (0.66, 4.78)
# teal under-wave curling downward beneath it
UNDER_CTRL = [(0.04, 3.76), (0.34, 3.72), (0.60, 3.63), (0.77, 3.48), (0.77, 3.31), (0.65, 3.24),
              (0.55, 3.30), (0.60, 3.42)]
UNDER_R = [0.13, 0.125, 0.112, 0.096, 0.076, 0.056, 0.034, 0.0]
UNDER_FLAT = 0.66
UNDER_CURL_C = (0.67, 3.38)

# tines: straight, parallel, diamond-section, needle points, big hooked barbs; centre clearly longest
SIDE_X, SIDE_BASE_Z, SIDE_BLADE_Z, SIDE_W, SIDE_L = 0.84, 4.90, 5.80, 0.27, 0.92
MID_BASE_Z, MID_BLADE_Z, MID_W, MID_L = 4.62, 6.08, 0.33, 1.12
HEAD_INFO = {}
BEAST_C, BEAST_S, BEAST_SY = V(0, -0.02, 3.62), 1.75, 1.4


def wave_samples(ctrl, radii, sx, n=23):
    pts, ts = catmull([V(sx * x, 0, z) for x, z in ctrl], n)
    return pts, [interp(radii, t) for t in ts], ts


def claw(bm, gbm, p, out, tang, length, w0, mat=M_GOLD):
    """A flat, lens-section claw spike raking along the crest (sharp edges, needle tip) + a Neon edge line."""
    mid = p + out * (length * 0.55) + tang * (length * 0.32)
    tip = p + out * length + tang * (length * 0.9)
    pts = [p - out * (w0 * 0.6), p + out * (w0 * 0.25), mid, tip]
    tube(bm, pts, [(w0, w0 * 0.42), (w0 * 0.95, w0 * 0.4), (w0 * 0.55, w0 * 0.3), 0.0], section=HEX_LENS, mat=mat, up=Y)
    ext = tip + (tip - mid).normalized() * 0.05
    tube(gbm, [pts[1], mid, ext], [(w0 * 1.28, w0 * 0.14), (w0 * 0.85, w0 * 0.12), 0.0], section=HEX_LENS, up=Y)


def outward(p, n, c):
    return n if (p - c).dot(n) > 0 else -n


def build_waves():
    g = new_bm()
    for sx in (1, -1):
        tag = 'R' if sx > 0 else 'L'
        pts, rr, ts = wave_samples(WAVE_CTRL, WAVE_R, sx)
        bm = new_bm()
        tube(bm, pts, [(r, r * WAVE_FLAT) for r in rr[:-1]] + [0.0], section=HEX_LENS, mat=M_GOLD, up=Y)
        ob = make_obj(f"Wave{tag}", bm, smooth=True)
        hard(ob, 0.006, segs=2, angle=35)
        # raised coral enamel inlay along both faces
        k0, k1 = 2, len(pts) - 6
        sub = pts[k0:k1 + 1]
        m = len(sub) - 1
        rad = []
        for j in range(len(sub)):
            env = min(1.0, min(j, m - j) / 3.0) ** 0.6
            r = rr[k0 + j]
            rad.append((r * 0.42 * env, r * WAVE_FLAT * 1.1) if 0 < j < m else 0.0)
        b2 = new_bm()
        tube(b2, sub, rad, section=HEX_LENS, mat=M_CORAL, up=Y)
        o2 = make_obj(f"WaveInlay{tag}", b2, smooth=True)
        add_wn(o2)
        # Neon lip along the curl: a thin band proud of both sharp edges, running out to the needle
        k0 = 8
        sub = pts[k0:]
        gr = []
        for j in range(len(sub) - 1):
            r = rr[k0 + j]
            gr.append((r * lerp(0.96, 1.22, min(1.0, j / 4)) + 0.03, max(r, 0.02) * WAVE_FLAT * 0.3))
        tube(g, sub[:-1] + [sub[-1] + (sub[-1] - sub[-2]) * 0.8], gr + [0.0], section=HEX_LENS, up=Y)
        # claw spikes raking up the outer crest (breaking-wave claws)
        T_, N_, _ = frames(pts)
        cc = V(sx * WAVE_CURL_C[0], 0, WAVE_CURL_C[1])
        bc = new_bm()
        for k, ln in ((5, 0.2), (7, 0.27), (9, 0.31), (11, 0.25)):
            o = outward(pts[k], N_[k], cc)
            claw(bc, g, pts[k] + o * (rr[k] * 0.7), o, T_[k], ln, 0.085)
        oc = make_obj(f"WaveClaws{tag}", bc, smooth=True)
        hard(oc, 0.005, segs=1, angle=35)
        # teal under-wave (downward curl ending in a needle) with two teal claws
        upts, ur, _ = wave_samples(UNDER_CTRL, UNDER_R, sx, n=18)
        b3 = new_bm()
        tube(b3, upts, [(r, r * UNDER_FLAT) for r in ur[:-1]] + [0.0], section=HEX_LENS, mat=M_TEAL, up=Y)
        T2, N2, _ = frames(upts)
        uc = V(sx * UNDER_CURL_C[0], 0, UNDER_CURL_C[1])
        for k, ln in ((6, 0.16), (9, 0.17)):
            o = outward(upts[k], N2[k], uc)
            claw(b3, g, upts[k] + o * (ur[k] * 0.7), o, T2[k], ln, 0.06, mat=M_TEAL)
        o3 = make_obj(f"UnderWave{tag}", b3, smooth=True)
        hard(o3, 0.005, segs=1, angle=35)
        k0 = 7
        sub = upts[k0:]
        gr = [(max(ur[k0 + j], 0.02) * lerp(0.96, 1.22, min(1.0, j / 3)) + 0.02, max(ur[k0 + j], 0.02) * UNDER_FLAT * 0.3)
              for j in range(len(sub) - 1)]
        tube(g, sub[:-1] + [sub[-1] + (sub[-1] - sub[-2]) * 0.8], gr + [0.0], section=HEX_LENS, up=Y)
    make_obj("WaveLips_Glow", g, kind="glow")


# blade half outline (units of W, L from the blade base): (edge_u, edge_s, ridge_u, ridge_s, ridge_thickness)
BLADE_HALF = [(0.40, -0.02, 0.0, -0.02, 0.12), (0.46, 0.10, 0.30, 0.14, 0.12),
              (0.86, -0.02, 0.98, 0.06, 0.10), (1.14, -0.22, 1.22, -0.17, 0.07), (1.38, -0.52, 1.38, -0.52, 0.022),
              (1.32, -0.15, 1.22, -0.17, 0.07), (1.16, 0.10, 0.98, 0.06, 0.10), (0.86, 0.27, 0.30, 0.22, 0.12),
              (0.58, 0.42, 0.0, 0.42, 0.10), (0.30, 0.63, 0.0, 0.63, 0.075), (0.12, 0.83, 0.0, 0.83, 0.05)]
T_EDGE = 0.02


def tine(tag, x0, base_z, blade_z, W, L, shank_w=0.12):
    """One tine cut from a 2D outline (shank + barbed spearhead) with a diamond section: every outline vertex is
    joined to its own ridge point (the centre line, or the barb's own centre line), front and back."""
    sb = blade_z - base_z
    half = [(shank_w, -sb, 0.0, -sb, 0.1), (shank_w * 0.86, -sb * 0.5, 0.0, -sb * 0.5, 0.09),
            (shank_w * 0.95, -0.12, 0.0, -0.12, 0.1)]
    half += [(eu * W, es * L, ru * W, rs * L, rt) for eu, es, ru, rs, rt in BLADE_HALF]
    tipv = (0.0, L, 0.0, L, T_EDGE)
    loop = half + [tipv] + [(-eu, es, -ru, rs, rt) for eu, es, ru, rs, rt in reversed(half)]

    def P(u, s, yy):
        return V(x0 + u, yy, blade_z + s)

    bm = new_bm()
    rings = [[P(ru, rs, -rt) for eu, es, ru, rs, rt in loop], [P(eu, es, -T_EDGE) for eu, es, ru, rs, rt in loop],
             [P(eu, es, T_EDGE) for eu, es, ru, rs, rt in loop], [P(ru, rs, rt) for eu, es, ru, rs, rt in loop]]
    loft(bm, rings, caps=False, mat=M_GOLD, recalc=False)
    # close the shank bottom (buried in the wave / socket)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bmesh.ops.holes_fill(bm, edges=bm.edges[:], sides=0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        f.material_index = M_GOLD
    # teal enamel leaf inlay riding both blade faces (projected onto the faces)
    from mathutils.bvhtree import BVHTree
    bm.normal_update()
    tree = BVHTree.FromBMesh(bm)
    leaf = [(0.0, 0.14), (0.2, 0.3), (0.13, 0.52), (0.0, 0.72), (-0.13, 0.52), (-0.2, 0.3)]
    b2 = new_bm()
    for sy in (-1, 1):
        lo, hi = [], []
        for u, s in leaf:
            o = P(u * W, s * L, sy * 1.0)
            hit = tree.ray_cast(o, V(0, -sy, 0))[0]
            yy = hit.y if hit is not None else sy * 0.1
            lo.append(P(u * W, s * L, yy - sy * 0.02))
            hi.append(P(u * W, s * L, yy + sy * 0.014))
        loft(b2, [lo, hi], mat=M_TEAL)
    ob = make_obj(f"Tine{tag}", bm, smooth=True)
    hard(ob, 0.005, segs=2, angle=30)
    o2 = make_obj(f"TineInlay{tag}", b2, smooth=True)
    hard(o2, 0.003, segs=1, angle=30)
    # Neon line along every edge of the tine (offset outline, thin through the blade)
    pts2 = [(eu, es) for eu, es, ru, rs, rt in loop]
    n = len(pts2)
    area = sum(pts2[i - 1][0] * pts2[i][1] - pts2[i][0] * pts2[i - 1][1] for i in range(n))
    sg = 1.0 if area > 0 else -1.0
    big = []
    for i in range(n):
        a_, b_, c_ = Vector(pts2[i - 1]), Vector(pts2[i]), Vector(pts2[(i + 1) % n])
        e1, e2 = (b_ - a_).normalized(), (c_ - b_).normalized()
        n1, n2 = Vector((e1.y, -e1.x)), Vector((e2.y, -e2.x))
        nm = n1 + n2
        nm = nm.normalized() if nm.length > 1e-6 else n1
        k = min(2.4, 1.0 / max(0.3, nm.dot(n1)))
        d = 0.045 * sg * k
        big.append((b_.x + nm.x * d, b_.y + nm.y * d))
    gb = new_bm()
    loft(gb, [[P(u, s, -0.015) for u, s in big], [P(u, s, 0.015) for u, s in big]])
    make_obj(f"TineEdge_Glow{tag}", gb, kind="glow")
    HEAD_INFO[tag] = {"tip": P(0, L, 0)}
    return ob


def build_prongs():
    for sx in (1, -1):
        tag = "R" if sx > 0 else "L"
        x0 = sx * SIDE_X
        tine(tag, x0, SIDE_BASE_Z, SIDE_BLADE_Z, SIDE_W, SIDE_L, shank_w=0.12)
        b2 = new_bm()
        M = Matrix.Translation(V(x0, 0, 0))
        zc = lerp(SIDE_BASE_Z, SIDE_BLADE_Z, 0.62)
        ring_band(b2, zc, 0.09, 0.15, 0.09, sides=8, M=M, mat=M_TEAL)
        lathe(b2, [(0.1, 5.02), (0.17, 5.06), (0.18, 5.11), (0.12, 5.16)], sides=8, M=M, mat=M_GOLD)
        lathe(b2, [(0.1, SIDE_BLADE_Z - 0.16), (0.16, SIDE_BLADE_Z - 0.12), (0.17, SIDE_BLADE_Z - 0.05),
                   (0.12, SIDE_BLADE_Z - 0.0)], sides=8, M=M, mat=M_BRONZE)
        o2 = make_obj(f"TineBands{tag}", b2, smooth=True)
        hard(o2, 0.004, segs=1)
    tine("M", 0.0, MID_BASE_Z, MID_BLADE_Z, MID_W, MID_L, shank_w=0.13)
    b2 = new_bm()
    lathe(b2, [(0.07, 4.50), (0.16, 4.56), (0.2, 4.66), (0.17, 4.76), (0.13, 4.84)], sides=8, mat=M_GOLD)
    for zc in (5.35,):
        ring_band(b2, zc, 0.1, 0.165, 0.09, sides=8, mat=M_TEAL)
        ring_band(b2, zc + 0.075, 0.1, 0.155, 0.04, sides=8, mat=M_GOLD, crown=0.05)
    lathe(b2, [(0.11, MID_BLADE_Z - 0.17), (0.18, MID_BLADE_Z - 0.13), (0.19, MID_BLADE_Z - 0.05),
               (0.13, MID_BLADE_Z)], sides=8, mat=M_BRONZE)
    o2 = make_obj("TineBandsM", b2, smooth=True)
    hard(o2, 0.004, segs=1)


def build_pearl():
    """Big aqua pearl in a gold bezel at the heart of the waves, with a bright core glowing through both faces."""
    g = new_bm()
    sphere(g, PEARL_C, PEARL_R, rings_n=8, sides=14, M=Matrix.Rotation(math.pi / 2, 4, "X"))
    make_obj("Pearl_Glow", g, kind="glow")
    c = new_bm()
    for sy in (-1, 1):
        sphere(c, PEARL_C + Y * (sy * PEARL_R * 0.55), PEARL_R * 0.55, rings_n=7, sides=12,
               M=Matrix.Rotation(math.pi / 2, 4, "X"))
    make_obj("PearlCore_Core", c, kind="core")
    bm = new_bm()
    n = 24
    rings_ = []
    for k in range(n):
        a = 2 * math.pi * k / n
        rad = V(math.cos(a), 0, math.sin(a))
        p = PEARL_C + rad * (PEARL_R + 0.035)
        rr = 0.06 if k % 2 else 0.078
        rings_.append([p + rad * (math.cos(2 * math.pi * s / 6) * rr) + Y * (math.sin(2 * math.pi * s / 6) * rr * 1.2)
                       for s in range(6)])
    vr = [[bm.verts.new(q) for q in r] for r in rings_]
    faces = []
    for i in range(n):
        A, B = vr[i], vr[(i + 1) % n]
        for s in range(6):
            faces.append(bm.faces.new([A[s], A[(s + 1) % 6], B[(s + 1) % 6], B[s]]))
    for f in faces:
        f.material_index = M_GOLD
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    ob = make_obj("Bezel", bm, smooth=True)
    hard(ob, 0.004, segs=1, angle=40)


def sec9(w, zt, zb):
    half = [(0.55 * w, zt * 0.92), (w, zt * 0.35), (w * 0.9, zb * 0.45), (0.58 * w, zb)]
    return [(0.0, zt)] + half + [(-x, z) for x, z in reversed(half)]


def build_beast():
    """Focal piece: a fierce sea-dragon head facing front at the base of the head, jaws open on ivory fangs, angry
    gold brows sweeping into horns that clasp the pearl, gill-fin spikes, glowing aqua eyes. The back of the skull
    carries overlapping teal scale plates under a spiny gold fin crest."""
    S, SY, C = BEAST_S, BEAST_SY, BEAST_C

    def W(x, y, z):
        return C + V(x * S, y * SY, z * S)

    st = [(0.36, 0.19, 0.14, -0.17), (0.22, 0.25, 0.2, -0.2), (0.05, 0.30, 0.25, -0.17), (-0.13, 0.25, 0.2, -0.08),
          (-0.30, 0.18, 0.12, -0.045), (-0.44, 0.13, 0.075, -0.03)]
    bm = new_bm()
    rings = [[W(x, y, z) for x, z in sec9(w, zt, zb)] for y, w, zt, zb in st] + [W(0, -0.53, 0.01)]
    loft(bm, rings, mat=M_SCALE)
    jaw = [(0.04, 0.21, -0.12, -0.27), (-0.18, 0.17, -0.15, -0.27), (-0.34, 0.11, -0.16, -0.24)]
    rings = [[W(x, y, z) for x, z in sec9(w, zt, zb)] for y, w, zt, zb in jaw] + [W(0, -0.44, -0.2)]
    loft(bm, rings, mat=M_SCALE)
    box(bm, W(0, -0.2, -0.11), (0.26 * S, 0.34 * SY, 0.12 * S), mat=M_SOCK)
    ob = make_obj("BeastHead", bm, smooth=True)
    hard(ob, 0.006, segs=1, angle=30)
    # fangs
    fb = new_bm()
    for x, y, ln in ((0.12, -0.27, 0.16), (0.07, -0.37, 0.1), (0.03, -0.43, 0.07)):
        for sx in (1, -1):
            p = W(sx * x, y, -0.035)
            tube(fb, [p, p + V(sx * 0.005, -0.01, -ln * S)], [0.04 if ln > 0.12 else 0.03, 0.0], sides=4, mat=M_IVORY,
                 phase=math.pi / 4)
    for x, y in ((0.1, -0.24), (0.06, -0.33)):
        for sx in (1, -1):
            p = W(sx * x, y, -0.15)
            tube(fb, [p, p + V(0, -0.01, 0.08 * S)], [0.028, 0.0], sides=4, mat=M_IVORY, phase=math.pi / 4)
    of = make_obj("BeastFangs", fb, smooth=True)
    hard(of, 0.003, segs=1)
    gb = new_bm()
    for sx in (1, -1):
        # brow ridge -> horn that sweeps up outside the bezel and hooks in over the pearl
        brow = [W(sx * 0.05, -0.27, 0.13), W(sx * 0.17, -0.16, 0.2), W(sx * 0.29, -0.03, 0.25),
                V(sx * 0.5, -0.15, 4.3), V(sx * 0.44, -0.18, 4.56), V(sx * 0.29, -0.21, 4.72)]
        tube(gb, brow, [(0.05, 0.038), (0.068, 0.05), (0.075, 0.055), (0.06, 0.045), (0.042, 0.032), 0.0],
             section=HEX_LENS, mat=M_GOLD, up=V(0, -1, 0.3))
        # gill-fin spikes raking back from the cheeks
        for z0, ln, d in ((0.08, 0.24, V(sx, 0.45, -0.1)), (-0.03, 0.28, V(sx, 0.5, -0.22)),
                          (-0.13, 0.22, V(sx, 0.5, -0.34))):
            p0 = W(sx * 0.25, 0.1, z0)
            d = d.normalized()
            L = ln * S * 0.85
            tube(gb, [p0, p0 + d * (L * 0.5) + V(0, 0, 0.02), p0 + d * L], [(0.062, 0.026), (0.044, 0.019), 0.0],
                 section=HEX_LENS, mat=M_GOLD, up=Y if abs(d.y) < 0.8 else V(0, 0, 1))
    # snout spine
    spine = [W(0, -0.46, 0.08), W(0, -0.3, 0.135), W(0, -0.12, 0.21), W(0, 0.02, 0.27)]
    tube(gb, spine, [(0.03, 0.035), (0.036, 0.046), (0.036, 0.05), (0.024, 0.035)], section=HEX_LENS, mat=M_GOLD,
         up=V(1, 0, 0))
    # spiny fin crest running down the back of the skull (flat blades, thickness along x)
    crest = [W(0, 0.12, 0.27), W(0, 0.25, 0.22), W(0, 0.35, 0.12), W(0, 0.39, 0.0), W(0, 0.38, -0.12)]
    tube(gb, crest, [(0.03, 0.03), (0.035, 0.032), (0.035, 0.032), (0.03, 0.03), (0.02, 0.025)], section=HEX_LENS,
         mat=M_GOLD, up=V(1, 0, 0))
    for k, base in enumerate(crest):
        d = V(0, 0.45 + 0.14 * k, 0.9 - 0.32 * k).normalized()
        L = (0.2 - 0.025 * k) * S
        tube(gb, [base - d * 0.02, base + d * (L * 0.5) + V(0, 0.02, 0), base + d * L],
             [(0.07, 0.022), (0.05, 0.017), 0.0], section=HEX_LENS, mat=M_GOLD, up=V(1, 0, 0))
    og = make_obj("BeastGold", gb, smooth=True)
    hard(og, 0.004, segs=1, angle=30)
    # overlapping teal scale plates on the back of the skull (rows overlap top over bottom)
    pb = new_bm()
    for z, xs in ((0.08, (0.08, 0.16)), (-0.02, (0.06, 0.14)), (-0.11, (0.1,))):
        for x in xs:
            for sx in (1, -1):
                top, bot = W(sx * x, 0.365, z + 0.05), W(sx * x, 0.385, z - 0.07)
                tube(pb, [top, top.lerp(bot, 0.45), bot], [(0.058, 0.016), (0.064, 0.02), 0.0], section=HEX_LENS,
                     mat=M_TEAL, up=Y)
    op = make_obj("BeastScales", pb, smooth=True)
    hard(op, 0.003, segs=1, angle=30)
    # glowing almond eyes under the brows + white-hot slit pupils
    ge, ce = new_bm(), new_bm()
    for sx in (1, -1):
        e = W(sx * 0.165, -0.2, 0.1)
        d = V(sx * 0.5, -0.85, 0.1).normalized()
        xa = d.cross(V(0, 0, 1)).normalized()
        R = basis(xa, d.cross(xa), d) @ Matrix.Rotation(math.radians(sx * -20), 4, "Z")
        lathe(ge, [(0.0, -0.035), (0.095, -0.012), (0.1, 0.014), (0.0, 0.04)], sides=8,
              M=Matrix.Translation(e) @ R @ Matrix.Scale(S * 0.95, 4), sy=0.55)
        lathe(ce, [(0.0, 0.0), (0.026, 0.025), (0.0, 0.055)], sides=6,
              M=Matrix.Translation(e) @ R @ Matrix.Scale(S * 0.95, 4), sy=1.8)
    make_obj("BeastEyes_Glow", ge, kind="glow")
    make_obj("BeastEyes_Core", ce, kind="core")


def build_collar():
    """Gold socket flaring from the shaft up into the beast's neck, with a teal enamel band."""
    bm = new_bm()
    lathe(bm, [(0.17, 3.28), (0.24, 3.31), (0.265, 3.40), (0.235, 3.47), (0.215, 3.50)], sides=12, mat=M_GOLD)
    lathe(bm, [(0.21, 3.58), (0.27, 3.62), (0.31, 3.69), (0.27, 3.75), (0.18, 3.80)], sides=12, mat=M_GOLD,
          ripple=0.08, lobes=6)
    ob = make_obj("Collar", bm, smooth=True)
    hard(ob, 0.005, segs=1, angle=28)
    b2 = new_bm()
    ring_band(b2, 3.54, 0.19, 0.245, 0.09, sides=12, mat=M_TEAL)
    o2 = make_obj("CollarBands", b2, smooth=True)
    hard(o2, 0.004, segs=1)


def build_shaft():
    bm = new_bm()
    zs = [SHAFT_Z0 + (SHAFT_Z1 - SHAFT_Z0) * k / 2 for k in range(3)]
    tube(bm, [V(0, 0, z) for z in zs], [shaft_r(z) for z in zs], sides=8, mat=M_ABYSS, phase=math.pi / 8)
    ob = make_obj("Shaft", bm, smooth=True)
    hard(ob, 0.014, angle=30)
    # gold rings + teal/coral enamel bands
    b2 = new_bm()
    for z in (1.2, 1.38, 3.19):
        ring_band(b2, z, shaft_r(z) - 0.01, shaft_r(z) + 0.065, 0.075, sides=8)
    ring_band(b2, GRIP_Z0 - 0.07, shaft_r(GRIP_Z0) - 0.01, shaft_r(GRIP_Z0) + 0.072, 0.095, sides=8, crown=-0.07)
    ring_band(b2, GRIP_Z1 + 0.07, shaft_r(GRIP_Z1) - 0.01, shaft_r(GRIP_Z1) + 0.072, 0.095, sides=8, crown=0.07)
    o2 = make_obj("ShaftRings", b2, smooth=True)
    hard(o2, 0.006, segs=1)
    b3 = new_bm()
    ring_band(b3, 1.29, shaft_r(1.29) - 0.01, shaft_r(1.29) + 0.045, 0.12, sides=10, mat=M_TEAL)
    ring_band(b3, 3.11, shaft_r(3.1) - 0.01, shaft_r(3.1) + 0.045, 0.085, sides=10, mat=M_TEAL)
    o3 = make_obj("ShaftEnamel", b3, smooth=True)
    hard(o3, 0.005, segs=1)
    return ob


def strap_helix(bm, z0, z1, R, pitch, w, th, direction, mat, phase=0.0):
    """Flat leather strap wound around the shaft (section in the radial/z plane)."""
    turns = (z1 - z0) / pitch
    steps = max(6, int(turns * 8))
    rings = []
    for k in range(steps + 1):
        a = direction * 2 * math.pi * turns * k / steps + phase
        z = z0 + (z1 - z0) * k / steps
        rad = V(math.cos(a), math.sin(a), 0)
        c = V(0, 0, z) + rad * R
        sec = [(-th * 0.5, -w * 0.5), (th * 0.2, -w * 0.46), (th * 0.6, 0.0), (th * 0.2, w * 0.46), (-th * 0.5, w * 0.5)]
        rings.append([c + rad * a_ + V(0, 0, b_) for a_, b_ in sec])
    loft(bm, rings, mat=mat)


def build_grip():
    """Tight criss-cross leather wrap (deep crimson over dark coral) on a crimson sleeve, split by gold bands,
    at the hand position used for both melee and throw; a shorter matching wrap low on the shaft."""
    bm = new_bm()
    bands = new_bm()
    zm = (GRIP_Z0 + GRIP_Z1) / 2
    for z0, z1 in ((GRIP_Z0, zm - 0.045), (zm + 0.045, GRIP_Z1), (0.68, 1.04)):
        R = shaft_r((z0 + z1) / 2)
        tube(bm, [V(0, 0, z0), V(0, 0, z1)], [R + 0.012, R + 0.012], sides=8, mat=M_CRIMSON)
        for ph in (0.0, math.pi):
            strap_helix(bm, z0, z1, R + 0.026, 0.34, 0.075, 0.03, 1, M_CRIMSON, phase=ph)
            strap_helix(bm, z0, z1, R + 0.034, 0.34, 0.068, 0.03, -1, M_CORAL, phase=ph + math.pi / 2)
    ring_band(bands, zm, shaft_r(zm) - 0.01, shaft_r(zm) + 0.07, 0.07, sides=8)
    ring_band(bands, 0.86, shaft_r(0.86) - 0.01, shaft_r(0.86) + 0.065, 0.06, sides=8)
    ring_band(bands, 0.66, shaft_r(0.66) - 0.01, shaft_r(0.66) + 0.06, 0.05, sides=8)
    ring_band(bands, 1.06, shaft_r(1.06) - 0.01, shaft_r(1.06) + 0.06, 0.05, sides=8)
    ob = make_obj("GripWrap", bm, smooth=False)
    o2 = make_obj("GripBands", bands, smooth=True)
    hard(o2, 0.005, segs=1)


def build_butt():
    """Weighted scalloped butt cap ending in a gold diamond spike ringed by small down-swept spikes, Neon ring."""
    bm = new_bm()
    lathe(bm, [(0.15, 0.08), (0.25, 0.13), (0.32, 0.22), (0.34, 0.31), (0.29, 0.39), (0.22, 0.45), (0.19, 0.48)],
          sides=12, mat=M_GOLD, ripple=0.1, lobes=6, phase=0.0)
    lathe(bm, [(0.19, 0.50), (0.245, 0.53), (0.25, 0.6), (0.2, 0.63)], sides=10, mat=M_GOLD)
    lathe(bm, [(0.17, 0.12), (0.15, 0.04), (0.09, -0.1), (0.0, -0.36)], sides=6, mat=M_GOLD, phase=0.0)
    for k in range(4):
        a = 2 * math.pi * k / 4 + math.pi / 4
        d = V(math.cos(a), math.sin(a), 0)
        p = d * 0.2 + V(0, 0, 0.12)
        tube(bm, [p, p + d * 0.1 + V(0, 0, -0.1), p + d * 0.14 + V(0, 0, -0.22)], [(0.05, 0.03), (0.035, 0.02), 0.0],
             section=HEX_LENS, mat=M_BRONZE, up=V(0, 0, 1))
    ob = make_obj("ButtCap", bm, smooth=True)
    hard(ob, 0.005, segs=1, angle=30)
    b2 = new_bm()
    ring_band(b2, 0.49, 0.18, 0.235, 0.055, sides=12, mat=M_TEAL)
    o2 = make_obj("ButtBand", b2, smooth=True)
    hard(o2, 0.004, segs=1)
    g = new_bm()
    ring_band(g, 0.31, 0.3, 0.37, 0.045, sides=16, mat=0)
    make_obj("ButtRing_Glow", g, kind="glow")


def build_all():
    build_shaft()
    build_grip()
    build_butt()
    build_collar()
    build_beast()
    build_waves()
    build_pearl()
    build_prongs()


build_all()
log("built", len(PARTS), "parts")


def clean_degenerate(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])
    bad = [f for f in bm.faces if f.calc_area() < 1e-9]
    if bad:
        bmesh.ops.delete(bm, geom=bad, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(o.data)
    bm.free()


def apply_all():
    for o in list(PARTS):
        wn = [m for m in o.modifiers if m.type == "WEIGHTED_NORMAL"]
        for m in wn:
            o.modifiers.remove(m)
        if o.modifiers:
            apply_mods(o)
        clean_degenerate(o)
        if wn:
            add_wn(o)
            apply_mods(o)
    for o in list(WORK.objects):
        bpy.data.objects.remove(o, do_unlink=True)


apply_all()
log("modifiers applied")


def tri_count(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    tot = {}
    for o in objs:
        me = o.evaluated_get(dg).to_mesh()
        me.calc_loop_triangles()
        tot[o.name] = len(me.loop_triangles)
        o.evaluated_get(dg).to_mesh_clear()
    return tot


TRIS = tri_count(PARTS)
log("TRIS total", sum(TRIS.values()), sorted(TRIS.items(), key=lambda kv: -kv[1]))


def world_bounds(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in objs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = o.matrix_world
        pts.extend([mw @ v.co for v in me.vertices])
        ev.to_mesh_clear()
    return pts


def balance_point(objs):
    """Approximate centre of mass: volume-weighted centroid of each closed part via signed tetrahedra."""
    tot_v, acc = 0.0, Vector((0, 0, 0))
    for o in objs:
        me = o.data
        me.calc_loop_triangles()
        for tri in me.loop_triangles:
            a, b, c = (me.vertices[i].co for i in tri.vertices)
            v = a.dot(b.cross(c)) / 6.0
            tot_v += v
            acc += v * (a + b + c) / 4.0
    return acc / tot_v if abs(tot_v) > 1e-9 else Vector((0, 0, 0))


# ---------------------------------------------------------------------------
# Review rendering: the weapon catalogue's own stage
# ---------------------------------------------------------------------------
def setup_comp(bloom=0.45, halo=1.1):
    """Mild bloom on the whole image plus an aqua halo grown from the Emit pass only (Neon radiates a haze,
    the way Roblox Neon blooms in game, without blooming the light backdrop or greying the darks)."""
    scene.view_layers[0].use_pass_emit = True
    tree = bpy.data.node_groups.get("ReviewComp") or bpy.data.node_groups.new("ReviewComp", "CompositorNodeTree")
    tree.nodes.clear()
    if not tree.interface.items_tree:
        tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = tree.nodes.new("CompositorNodeRLayers")
    out = tree.nodes.new("NodeGroupOutput")
    img = rl.outputs["Image"]
    if bloom > 0:
        g = tree.nodes.new("CompositorNodeGlare")
        g.inputs["Type"].default_value = "Bloom"
        g.inputs["Quality"].default_value = "High"
        g.inputs["Threshold"].default_value = 0.55
        g.inputs["Strength"].default_value = bloom
        g.inputs["Size"].default_value = 0.55
        tree.links.new(img, g.inputs["Image"])
        img = g.outputs["Image"]
    if halo > 0 and "Emission" in rl.outputs:
        h = tree.nodes.new("CompositorNodeGlare")
        h.inputs["Type"].default_value = "Fog Glow"
        h.inputs["Quality"].default_value = "High"
        h.inputs["Threshold"].default_value = 0.0
        h.inputs["Strength"].default_value = halo
        h.inputs["Size"].default_value = 0.7
        h.inputs["Saturation"].default_value = 1.8
        h.inputs["Tint"].default_value = (0.25, 0.85, 1.0, 1.0)
        tree.links.new(rl.outputs["Emission"], h.inputs["Image"])
        gl = h.outputs["Glare"] if "Glare" in h.outputs else h.outputs["Image"]
        try:
            m = tree.nodes.new("ShaderNodeMix")
            m.data_type = "RGBA"
            m.blend_type = "ADD"
            m.inputs[0].default_value = 1.0
            tree.links.new(img, m.inputs[6])
            tree.links.new(gl, m.inputs[7])
            img = m.outputs[2]
        except RuntimeError:
            m = tree.nodes.new("CompositorNodeMixRGB")
            m.blend_type = "ADD"
            m.inputs[0].default_value = 1.0
            tree.links.new(img, m.inputs[1])
            tree.links.new(gl, m.inputs[2])
            img = m.outputs[0]
    tree.links.new(img, out.inputs[0])
    scene.compositing_node_group = tree


STAGE = {}


def clear_stage():
    for o in list(REVIEW.objects):
        bpy.data.objects.remove(o, do_unlink=True)


def catalog_stage(objs, angle, camvec, res=1000, samples=24, ortho_pad=1.18, focus=None, world=0.0509, floor=True,
                  extra_objs=()):
    clear_stage()
    saved = {o.name: o.matrix_world.copy() for o in objs}
    rot = Matrix.Rotation(math.radians(angle), 4, "Y")
    for o in objs:
        o.matrix_world = rot @ saved[o.name]
    bpy.context.view_layer.update()
    coords = world_bounds(objs)
    minz = min(c.z for c in coords)
    for o in objs:
        o.location.z -= minz
    bpy.context.view_layer.update()
    coords = world_bounds(list(objs) + list(extra_objs))
    mn = [min(c[i] for c in coords) for i in range(3)]
    mx = [max(c[i] for c in coords) for i in range(3)]
    center = Vector([(mn[i] + mx[i]) * 0.5 for i in range(3)])
    extent = max(mx[2] - mn[2], mx[0] - mn[0])
    cd = bpy.data.cameras.new("Review camera")
    cam = bpy.data.objects.new("Review camera", cd)
    REVIEW.objects.link(cam)
    cam.location = center + Vector(camvec) * extent / 5
    aim = focus if focus is not None else center

    def point(o, p):
        o.rotation_euler = (Vector(p) - o.location).to_track_quat("-Z", "Y").to_euler()

    point(cam, aim)
    cd.type = "ORTHO"
    bpy.context.view_layer.update()
    inv = cam.rotation_euler.to_matrix().transposed()
    if focus is None:
        pc = [inv @ (v - center) for v in coords]
        cd.ortho_scale = max(max(v[j] for v in pc) - min(v[j] for v in pc) for j in (0, 1)) * ortho_pad
    cd.clip_end = 500
    scene.camera = cam
    for name, off, power, sz in [("Key", (-4, -6, 9), 1000, 5), ("Fill", (5, -3, 6), 700, 4), ("Rim", (2, 5, 8), 1100, 4)]:
        ld = bpy.data.lights.new(name, "AREA")
        lo = bpy.data.objects.new(name, ld)
        REVIEW.objects.link(lo)
        lo.location = center + Vector(off) * extent / 5
        ld.energy = power * (extent / 5) ** 2
        ld.shape = "DISK"
        ld.size = sz * extent / 5
        point(lo, center)
    if floor:
        fme = bpy.data.meshes.new("Review floor")
        fme.from_pydata([(-100, -100, -0.04), (100, -100, -0.04), (100, 100, -0.04), (-100, 100, -0.04)], [], [(0, 1, 2, 3)])
        fo = bpy.data.objects.new("Review floor (not exported)", fme)
        REVIEW.objects.link(fo)
        fm = bpy.data.materials.get("Neutral floor") or bpy.data.materials.new("Neutral floor")
        fm.diffuse_color = (0.115, 0.12, 0.135, 1)
        fm.use_nodes = True
        fme.materials.append(fm)
    w = scene.world or bpy.data.worlds.new("World")
    scene.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (world, world, world, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "None"
    scene.render.image_settings.file_format = "PNG"
    STAGE.update(center=center, extent=extent, cam=cam, inv=inv)

    def restore():
        for o in objs:
            o.matrix_world = saved[o.name]
        bpy.context.view_layer.update()

    return restore


def render(path):
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    log("rendered", Path(path).name)


def asset_objs():
    return [o for o in ASSET.objects if o.type == "MESH"]


def quick_shots():
    setup_comp(0.4)
    objs = asset_objs()
    bp = balance_point([o for o in objs if o["kind"] == "tex"])
    log("balance point (authored)", tuple(round(x, 3) for x in bp), "grip mid", (GRIP_Z0 + GRIP_Z1) / 2)
    for shot in SHOTS:
        if shot == "catalog":
            r = catalog_stage(objs, PREVIEW_ANGLE, (1.6, -15, 6.2), res=640, samples=16)
            render(OUT / "q_catalog.png")
            r()
        elif shot in ("front", "side", "back"):
            vec = {"front": (0, -15, 1.2), "side": (15, 0, 1.2), "back": (0, 15, 1.2)}[shot]
            r = catalog_stage(objs, 0, vec, res=640, samples=16)
            render(OUT / f"q_{shot}.png")
            r()
        elif shot == "head":
            r = catalog_stage(objs, 0, (1.2, -15, 3.0), res=640, samples=16)
            cam = STAGE["cam"]
            cam.data.ortho_scale = 3.8
            tgt = V(0, 0, 5.3)
            cam.location = tgt + V(2.5, -11, 3.0)
            cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
            render(OUT / "q_head.png")
            r()


if MODE == "quick":
    quick_shots()
    log("QUICK DONE")
    sys.exit(0)


# ===========================================================================
# FULL MODE: scale, join, UV, painted masks, bake, export, render, validate
# ===========================================================================
def join(objs, name):
    select_only(objs)
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


pts0 = world_bounds(PARTS)
Z0 = min(p.z for p in pts0)
H0 = max(p.z for p in pts0) - Z0
SCALE = TARGET_HEIGHT / H0
for o in PARTS:
    o.data.transform(Matrix.Scale(SCALE, 4) @ Matrix.Translation(V(0, 0, -Z0)))
    o.data.update()


def S_(v):
    return (Vector(v) - V(0, 0, Z0)) * SCALE


log(f"authored height {H0:.3f} -> scale {SCALE:.4f}")
BALANCE = balance_point([o for o in PARTS if o["kind"] == "tex"])
BALANCE = V(0, 0, BALANCE.z)

_by_kind = {k: [o for o in PARTS if o["kind"] == k] for k in ("tex", "glow", "core")}
body = join(_by_kind["tex"], NAME)
glow_ob = join(_by_kind["glow"], f"{NAME}_Glow")
core_ob = join(_by_kind["core"], f"{NAME}_GlowCore")
PARTS = [body, glow_ob, core_ob]
FINAL = [body, glow_ob, core_ob]
for o in FINAL:
    while o.data.uv_layers:
        o.data.uv_layers.remove(o.data.uv_layers[0])
    for a in [a.name for a in o.data.color_attributes]:
        o.data.color_attributes.remove(o.data.color_attributes[a])
for o, m in ((glow_ob, GLOW_MAT), (core_ob, CORE_MAT)):
    o.data.materials.clear()
    o.data.materials.append(m)
    for p in o.data.polygons:
        p.material_index = 0

body.data.uv_layers.new(name="UVMap")
select_only([body])
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(52), island_margin=0.003, area_weight=0.0, correct_aspect=True,
                         scale_to_bounds=False)
bpy.ops.uv.pack_islands(rotate=True, margin=0.003)
bpy.ops.object.mode_set(mode="OBJECT")
for o in (glow_ob, core_ob):
    o.data.uv_layers.new(name="UVMap")
    select_only([o])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.01)
    bpy.ops.object.mode_set(mode="OBJECT")
log("uv done")


def corner_arrays(me):
    nl, npoly = len(me.loops), len(me.polygons)
    vi = np.empty(nl, np.int32)
    me.loops.foreach_get("vertex_index", vi)
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    pn = np.empty(npoly * 3, np.float32)
    me.polygons.foreach_get("normal", pn)
    pm = np.empty(npoly, np.int32)
    me.polygons.foreach_get("material_index", pm)
    lt = np.empty(npoly, np.int32)
    me.polygons.foreach_get("loop_total", lt)
    lp = np.repeat(np.arange(npoly), lt)
    return co[vi], pn.reshape(-1, 3)[lp], pm[lp]


P, NRM, MI = corner_arrays(body.data)
NL = len(P)
paint = np.ones((NL, 3), np.float32)
hz = np.clip(P[:, 2] / TARGET_HEIGHT, 0, 1)
for mi, lo, hi in ((M_ABYSS, 0.82, 0.28), (M_SCALE, 0.8, 0.3), (M_CRIMSON, 0.85, 0.15), (M_GOLD, 0.82, 0.14), (M_TEAL, 0.88, 0.2), (M_CORAL, 0.92, 0.12)):
    sel = MI == mi
    paint[sel] *= (lo + hi * hz[sel])[:, None]
# teal/coral enamel: cooler toward the outside of the waves (painted depth)
sel = (MI == M_TEAL) & (P[:, 2] > 3.2)
paint[sel] *= np.array([0.95, 1.0, 1.04], np.float32)

gP, gA, gC = [], [], []
for ob, col in ((glow_ob, GLOW), (core_ob, CORE)):
    me = ob.data
    c = np.empty(len(me.polygons) * 3, np.float32)
    me.polygons.foreach_get("center", c)
    a = np.empty(len(me.polygons), np.float32)
    me.polygons.foreach_get("area", a)
    gP.append(c.reshape(-1, 3))
    gA.append(a)
    gC.append(np.tile(np.array(rgba(col)[:3], np.float32), (len(a), 1)))
gP, gA, gC = np.concatenate(gP), np.concatenate(gA), np.concatenate(gC)
bleed = np.zeros((NL, 3), np.float32)
for i0 in range(0, NL, 1500):
    i1 = min(NL, i0 + 1500)
    Ld = gP[None, :, :] - P[i0:i1, None, :]
    d = np.linalg.norm(Ld, axis=2) + 1e-6
    wrap = np.clip(np.einsum("cgk,ck->cg", Ld, NRM[i0:i1]) / d * 0.75 + 0.25, 0, 1)
    w = gA[None, :] * wrap * np.exp(-d / 0.16) / (d * d + 0.03 ** 2)
    bleed[i0:i1] = w @ gC
bleed = (1 - np.exp(-BLEED_K * bleed)) * BLEED_STRENGTH
for nm, arr in (("Paint", paint), ("Bleed", bleed)):
    at = body.data.color_attributes.new(nm, "FLOAT_COLOR", "CORNER")
    at.data.foreach_set("color", np.concatenate([arr, np.ones((NL, 1), np.float32)], axis=1).ravel())
log("masks done")

KEY_DIR = V(-0.45, -0.6, 0.75).normalized()
RIM_DIR = V(0.7, 0.6, 0.25).normalized()
ZTOP = max(p.z for p in world_bounds([body]))


def build_bake_shader(idx, mat, img):
    name, flat_c, ramp, edge_c = PAL[idx]
    nt = mat.node_tree
    nt.nodes.clear()
    N, L = nt.nodes.new, nt.links.new

    def val(v):
        n = N("ShaderNodeValue")
        n.outputs[0].default_value = v
        return n.outputs[0]

    def math_(op, a, b):
        n = N("ShaderNodeMath")
        n.operation = op
        for i, x in enumerate((a, b)):
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                L(x, n.inputs[i])
        return n.outputs[0]

    def remap(sock, a, b, lo, hi):
        r = N("ShaderNodeMapRange")
        r.inputs["From Min"].default_value, r.inputs["From Max"].default_value = a, b
        r.inputs["To Min"].default_value, r.inputs["To Max"].default_value = lo, hi
        L(sock, r.inputs["Value"])
        return r.outputs["Result"]

    def mix(a, b, fac, blend="MIX"):
        m = N("ShaderNodeMix")
        m.data_type = "RGBA"
        m.blend_type = blend
        for sock, x in ((m.inputs[6], a), (m.inputs[7], b)):
            if isinstance(x, tuple):
                sock.default_value = x
            else:
                L(x, sock)
        if isinstance(fac, (int, float)):
            m.inputs["Factor"].default_value = fac
        else:
            L(fac, m.inputs["Factor"])
        return m.outputs[2]

    def grey(sock):
        c = N("ShaderNodeCombineColor")
        for i in range(3):
            L(sock, c.inputs[i])
        return c.outputs[0]

    geo = N("ShaderNodeNewGeometry")
    pos = geo.outputs["Position"]
    tn = geo.outputs["True Normal"]

    def dot_light(d):
        v = N("ShaderNodeVectorMath")
        v.operation = "DOT_PRODUCT"
        L(tn, v.inputs[0])
        v.inputs[1].default_value = d
        return math_("MAXIMUM", v.outputs["Value"], 0.0)

    n1 = N("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = 1.7
    n1.inputs["Detail"].default_value = 2.0
    n1.inputs["Roughness"].default_value = 0.45
    n1.inputs["Distortion"].default_value = 0.35
    L(pos, n1.inputs["Vector"])
    n2 = N("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 5.5
    n2.inputs["Detail"].default_value = 1.0
    L(pos, n2.inputs["Vector"])
    nmix = math_("ADD", n1.outputs["Fac"], math_("MULTIPLY", math_("SUBTRACT", n2.outputs["Fac"], 0.5), 0.4))
    rp = N("ShaderNodeValToRGB")
    el = rp.color_ramp.elements
    el[0].position, el[0].color = ramp[0][0], rgba(ramp[0][1])
    el[1].position, el[1].color = ramp[-1][0], rgba(ramp[-1][1])
    for p_, c_ in ramp[1:-1]:
        e = el.new(p_)
        e.color = rgba(c_)
    L(nmix, rp.inputs["Fac"])
    pa = N("ShaderNodeAttribute")
    pa.attribute_name = "Paint"
    albedo = mix(rp.outputs["Color"], pa.outputs["Color"], 1.0, "MULTIPLY")
    if idx in (M_ABYSS, M_SCALE):       # painted fish-scale motif on the shaft and the sea-dragon
        vm = N("ShaderNodeVectorMath")
        vm.operation = "MULTIPLY"
        L(pos, vm.inputs[0])
        vm.inputs[1].default_value = (1.0, 1.0, 0.7)
        vo = N("ShaderNodeTexVoronoi")
        vo.feature = "DISTANCE_TO_EDGE"
        vo.inputs["Scale"].default_value = 11.0 if idx == M_ABYSS else 16.0
        L(vm.outputs[0], vo.inputs["Vector"])
        line = remap(vo.outputs["Distance"], 0.0, 0.05, 1.0, 0.0)
        albedo = mix(albedo, rgba((40, 130, 160) if idx == M_ABYSS else (60, 190, 170)), math_("MULTIPLY", line, 0.6))
    if idx in (M_TEAL, M_CORAL):     # soft wave bands painted into the enamel
        wv = N("ShaderNodeTexWave")
        wv.wave_type = "BANDS"
        wv.bands_direction = "Z"
        wv.inputs["Scale"].default_value = 3.0
        wv.inputs["Distortion"].default_value = 3.0
        wv.inputs["Detail"].default_value = 1.0
        L(pos, wv.inputs["Vector"])
        hi_c = (110, 226, 214) if idx == M_TEAL else (255, 176, 140)
        albedo = mix(albedo, rgba(hi_c), remap(wv.outputs["Fac"], 0.6, 0.95, 0.0, 0.35))
    k = dot_light(KEY_DIR)
    light = remap(k, 0.0, 1.0, 0.56, 1.2)
    tint = mix((0.86, 0.92, 1.07, 1), (1.08, 1.0, 0.9, 1), k)
    ao = N("ShaderNodeAmbientOcclusion")
    ao.samples = 16
    ao.inputs["Distance"].default_value = 0.28
    aof = remap(ao.outputs["AO"], 0.2, 1.0, 0.5, 1.0)
    cav = N("ShaderNodeAmbientOcclusion")
    cav.samples = 16
    cav.inputs["Distance"].default_value = 0.045
    cavf = remap(cav.outputs["AO"], 0.35, 1.0, 0.6, 1.0)
    sep = N("ShaderNodeSeparateXYZ")
    L(pos, sep.inputs["Vector"])
    height = remap(sep.outputs["Z"], 0.0, ZTOP, 0.9, 1.05)
    shade = math_("MULTIPLY", math_("MULTIPLY", light, aof), math_("MULTIPLY", cavf, height))
    lit = mix(mix(albedo, tint, 1.0, "MULTIPLY"), grey(shade), 1.0, "MULTIPLY")
    rim = remap(dot_light(RIM_DIR), 0.25, 1.0, 0.0, 0.14)
    lit = mix(lit, (0.25, 0.75, 0.95, 1), rim, "ADD")
    bev = N("ShaderNodeBevel")
    bev.samples = 8
    bev.inputs["Radius"].default_value = 0.016
    ed = N("ShaderNodeVectorMath")
    ed.operation = "DOT_PRODUCT"
    L(bev.outputs["Normal"], ed.inputs[0])
    L(tn, ed.inputs[1])
    e = remap(ed.outputs["Value"], 0.99, 0.84, 0.0, 1.0)
    convex = remap(cav.outputs["AO"], 0.86, 0.97, 0.0, 1.0)
    efac = math_("MULTIPLY", math_("MULTIPLY", e, convex), remap(k, 0.0, 1.0, 0.45, 0.85))
    ecol = mix(albedo, rgba(edge_c), 0.6)
    lit = mix(lit, mix(ecol, grey(val(1.2)), 1.0, "MULTIPLY"), efac)
    ba = N("ShaderNodeAttribute")
    ba.attribute_name = "Bleed"
    lit = mix(lit, ba.outputs["Color"], 1.0, "ADD")
    em = N("ShaderNodeEmission")
    L(lit, em.inputs["Color"])
    out = N("ShaderNodeOutputMaterial")
    L(em.outputs["Emission"], out.inputs["Surface"])
    target = N("ShaderNodeTexImage")
    target.image = img
    nt.nodes.active = target


BAKE_RES = 2048
bake_img = bpy.data.images.new(f"{NAME}_bake", BAKE_RES, BAKE_RES, alpha=False)
for i, m in enumerate(MATS):
    build_bake_shader(i, m, bake_img)
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 40
scene.render.bake.margin = 16
select_only([body])
t_b = time.time()
bpy.ops.object.bake(type="EMIT")
log(f"bake {time.time() - t_b:.0f}s")
px = np.empty(BAKE_RES * BAKE_RES * 4, np.float32)
bake_img.pixels.foreach_get(px)
px = px.reshape(BAKE_RES, BAKE_RES, 4)
f = BAKE_RES // BAKE_SIZE
small = px.reshape(BAKE_SIZE, f, BAKE_SIZE, f, 4).mean(axis=(1, 3))
tex_img = bpy.data.images.new(f"{NAME}_BaseColor_tmp", BAKE_SIZE, BAKE_SIZE, alpha=False)
tex_img.pixels.foreach_set(small.ravel())
tex_img.filepath_raw = str(ROOT / "BaseColor.png")
tex_img.file_format = "PNG"
tex_img.save()
bpy.data.images.remove(bake_img)
bpy.data.images.remove(tex_img)
tex_img = bpy.data.images.load(str(ROOT / "BaseColor.png"))
tex_img.name = f"{NAME}_BaseColor"
tex_img.pack()

final_mat = bpy.data.materials.new(f"{NAME}_Baked")
final_mat.use_nodes = True
bs = final_mat.node_tree.nodes["Principled BSDF"]
bs.inputs["Roughness"].default_value = 0.62
bs.inputs["Specular IOR Level"].default_value = 0.12
tx = final_mat.node_tree.nodes.new("ShaderNodeTexImage")
tx.image = tex_img
final_mat.node_tree.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
body.data.materials.clear()
body.data.materials.append(final_mat)
for p in body.data.polygons:
    p.material_index = 0
for nm in ("Paint", "Bleed"):
    body.data.color_attributes.remove(body.data.color_attributes[nm])
for m in MATS:
    bpy.data.materials.remove(m)
log("texture done")

select_only(FINAL, body)
bpy.ops.export_scene.gltf(filepath=str(ROOT / "Model.glb"), export_format="GLB", use_selection=True, export_apply=True)
bpy.ops.export_scene.fbx(filepath=str(ROOT / "Model.fbx"), use_selection=True, object_types={"MESH"}, axis_forward="-Z",
                         axis_up="Y", path_mode="COPY", embed_textures=True, add_leaf_bones=False, mesh_smooth_type="OFF")
log("exported")


def mesh_stats(ob):
    me = ob.data
    me.calc_loop_triangles()
    bm = bmesh.new()
    bm.from_mesh(me)
    loose = sum(1 for v in bm.verts if not v.link_faces)
    zero = sum(1 for f in bm.faces if f.calc_area() < 1e-9)
    nonman = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    co = np.array([tuple(v.co) for v in me.vertices])
    mn, mx = co.min(axis=0), co.max(axis=0)
    return {"triangles": len(me.loop_triangles), "vertices": len(me.vertices), "loose_vertices": loose,
            "zero_area_faces": zero, "non_manifold_edges": nonman, "bounds_min": [round(float(x), 4) for x in mn],
            "bounds_max": [round(float(x), 4) for x in mx]}


def studio(v):
    return [round(-float(v[0]), 4), round(float(v[2]), 4), round(float(v[1]), 4)]


def studio_size(v):
    return [round(float(v[0]), 4), round(float(v[2]), 4), round(float(v[1]), 4)]


STATS = {o.name: mesh_stats(o) for o in FINAL}
GRIP = S_(V(0, 0, (GRIP_Z0 + GRIP_Z1) / 2))
TIP = S_(HEAD_INFO["M"]["tip"])
PEARL = S_(PEARL_C)
allmn = np.min([s["bounds_min"] for s in STATS.values()], axis=0)
allmx = np.max([s["bounds_max"] for s in STATS.values()], axis=0)
tex_c = (np.array(STATS[NAME]["bounds_min"]) + np.array(STATS[NAME]["bounds_max"])) / 2


def rel(v):
    return studio(np.array(tuple(v)) - tex_c)


install = {
    "name": NAME, "blender_version": bpy.app.version_string, "status": "Blender-verified, Studio untested",
    "units": "1 Blender unit = 1 stud, authored at hero size; set the play size in Studio by uniform scale",
    "axes": "Studio = (-x, z, y) of Blender; FBX exported with axis_forward=-Z, axis_up=Y",
    "texture": f"BaseColor.png {BAKE_SIZE}x{BAKE_SIZE}, baked painted lighting; use MeshPart.TextureID (not SurfaceAppearance)",
    "parts": {},
    "grip_point_studio": studio(GRIP),
    "grip_point_relative_to_textured_center": rel(GRIP),
    "balance_point_studio": studio(BALANCE),
    "balance_point_relative_to_textured_center": rel(BALANCE),
    "throw_pivot_studio": studio(BALANCE),
    "tip_point_studio": studio(TIP),
    "tip_point_relative_to_textured_center": rel(TIP),
    "pearl_center_studio": studio(PEARL),
    "notes": [
        "Every MeshPart imports centred on its own bounding box: place each at its center_studio, relative to a "
        "shared model origin (Blender origin = bottom of the butt pearl on the shaft axis).",
        "grip_point = middle of the coral-braided grip on the shaft axis; it sits near the balance point so one "
        "hand position serves both the melee thrust/sweep and the throw.",
        "Melee: hold at grip_point with the shaft along the hand's grip axis, prongs forward/up.",
        "Throw: release from grip_point, fly prongs-first along the shaft axis (+Y studio = tip direction before "
        "rotation); spin/tumble, if any, pivots on throw_pivot (approximate centre of mass). The impact point is "
        "tip_point.",
        "A second, short coral wrap low on the shaft marks a two-hand / wind-up hold.",
    ],
    "vfx_notes": [
        "Signature effect: tidal wave on landing. Spawn at the world position of tip_point when the thrown trident "
        "hits the ground (or the target's feet), snapped to the floor.",
        "Colours: wave body deep teal (20,120,160) at Transparency 0.35, crest aqua (40,215,255) Neon, foam "
        "(225,252,255), spray droplets (150,235,255). Same aqua as the trident's Neon so it reads as its power.",
        "Wave ring: a thick open ring/torus mesh (Neon crest + translucent teal body) starting at radius 1 stud, "
        "tweened outward to ~14 studs over 0.7 s (Quad Out) while its height goes 3 -> 1.5 studs and "
        "Transparency 0.3 -> 1 over the last 0.25 s. Push enemies the ring passes away from the centre (knockback "
        "along the radial direction, no extra hits).",
        "Foam ring burst: ParticleEmitter on an Attachment at the spawn point, Shape Cylinder (ShapeStyle Surface, "
        "ShapeInOut Outward), EmissionDirection Top, Rate 0, :Emit(70) once; Lifetime 0.6-1.0; Speed 22-30; "
        "SpreadAngle (10, 10); Acceleration (0, -40, 0); Drag 2; Size 1.2 -> 2.6 -> 0; Transparency 0.15 -> 1; "
        "LightEmission 0.5; Color foam -> aqua; Orientation VelocityParallel.",
        "Droplets: second emitter, :Emit(40); Lifetime 0.8-1.2; Speed 14-24; SpreadAngle (70, 70); Acceleration "
        "(0, -60, 0); Size 0.35 -> 0; LightEmission 0.8; Color (150,235,255).",
        "Mist puff: :Emit(12); Lifetime 1.2-1.6; Speed 2-4; Size 4 -> 8; Transparency 0.6 -> 1; Color (190,240,250); "
        "LightEmission 0.2.",
        "Optional: a PointLight on the spawn point, aqua, Brightness 3 -> 0 over 0.5 s, Range 16; and while the "
        "trident is in flight a Trail between two attachments at the pearl and the butt, aqua -> transparent, "
        "Lifetime 0.25.",
    ],
}
for o in FINAL:
    st = STATS[o.name]
    mn, mx = np.array(st["bounds_min"]), np.array(st["bounds_max"])
    kind = "textured" if o is body else "glow"
    part = {"kind": kind, "center_studio": studio((mn + mx) / 2), "size_studio": studio_size(mx - mn),
            "triangles": st["triangles"]}
    if o is glow_ob:
        part.update(material="Neon", color_rgb=list(GLOW), note="aqua sea-glow: spearhead and barb edge bands, wave lips, pearl, butt pearl")
    elif o is core_ob:
        part.update(material="Neon", color_rgb=list(CORE), note="bright pearl core showing through the front and back of the pearl")
    else:
        part.update(material="SmoothPlastic (or Plastic), Color white", texture_id="BaseColor.png")
    install["parts"][o.name] = part
(ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=1))
log("stats", {k: v["triangles"] for k, v in STATS.items()}, "total", sum(v["triangles"] for v in STATS.values()),
    "grip z", round(GRIP.z, 3), "balance z", round(BALANCE.z, 3))

# ---------------------------------------------------------------------------
# Renders: Preview, Front, Back, Side, Scale, Hero
# ---------------------------------------------------------------------------
setup_comp(0.45)


def shoot_catalog(name, angle, camvec, samples=32, res=1000):
    r = catalog_stage(FINAL, angle, camvec, samples=samples, res=res)
    render(ROOT / name)
    r()


shoot_catalog("Preview.png", PREVIEW_ANGLE, (1.6, -15, 6.2), samples=48)
shoot_catalog("Front.png", 0, (0, -15, 1.2))
shoot_catalog("Back.png", 0, (0, 15, 1.2))
shoot_catalog("Side.png", 0, (15, 0, 1.2))

fig_bm = new_bm()
FX = 3.1
for c, sz in (((FX - 0.5, 0, 1.0), (1.0, 1.0, 2.0)), ((FX + 0.5, 0, 1.0), (1.0, 1.0, 2.0)),
              ((FX, 0, 3.0), (2.0, 1.0, 2.0)), ((FX - 1.5, 0, 3.0), (1.0, 1.0, 2.0)),
              ((FX + 1.5, 0, 3.0), (1.0, 1.0, 2.0)), ((FX, 0, 4.5), (1.15, 1.15, 1.0))):
    box(fig_bm, V(*c), sz)
fig = make_obj("R15 block figure 5 studs (not exported)", fig_bm, kind="fig", coll=WORK)
PARTS.remove(fig)
fm = bpy.data.materials.new("Figure grey")
fm.use_nodes = True
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.38, 0.38, 0.4, 1)
fig.data.materials.clear()
fig.data.materials.append(fm)
add_bevel(fig, 0.06, segs=2, angle=40)
r = catalog_stage(FINAL, 0, (0.6, -15, 2.5), samples=32, extra_objs=[fig])
render(ROOT / "Scale.png")
r()
bpy.data.objects.remove(fig, do_unlink=True)


def hero(name, cam_loc, target, lens=58, res=(1200, 1400), samples=96):
    clear_stage()
    w = scene.world
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.012, 0.022, 0.034, 1)
    cd = bpy.data.cameras.new("Hero camera")
    cam = bpy.data.objects.new("Hero camera", cd)
    REVIEW.objects.link(cam)
    cd.lens = lens
    cam.location = cam_loc
    cam.rotation_euler = (target - cam_loc).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    mid = V(0, 0, TARGET_HEIGHT * 0.6)
    for nm, loc, col, en, sz in (("Hero key", V(-4, -6, 8), (0.8, 0.88, 1.0), 1150, 4),
                                  ("Hero rim aqua", V(4, 6, 6), (0.15, 0.8, 1.0), 1800, 3),
                                  ("Hero rim gold", V(-5, 5, 5), (1.0, 0.78, 0.45), 900, 3),
                                  ("Hero fill teal", V(2, -5, 0.5), (0.3, 0.6, 0.8), 180, 4)):
        ld = bpy.data.lights.new(nm, "AREA")
        ld.color = col
        ld.energy = en
        ld.size = sz
        lo = bpy.data.objects.new(nm, ld)
        REVIEW.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = (mid - loc).to_track_quat("-Z", "Y").to_euler()
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Punchy"
    except TypeError:
        pass
    setup_comp(0.9)
    render(ROOT / name)
    scene.view_settings.look = "None"
    setup_comp(0.45)


hero("Hero.png", V(2.5, -9.0, 1.6), V(0, 0, TARGET_HEIGHT * 0.55), lens=40)

catalog_stage(FINAL, 0, (0, -15, 1.2))
for o in FINAL:
    o.select_set(True)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "Model.blend"))
log("blend saved")


def compose(tiles, cols, cell, out_path, label_px=46, title=None, bg=(238, 237, 235)):
    sc = bpy.data.scenes.new("Compose")
    rows = math.ceil(len(tiles) / cols)
    title_px = 64 if title else 0
    Wpx, Hpx = cols * cell, rows * (cell + label_px) + title_px
    U = 0.01

    def emit_img_mat(img):
        m = bpy.data.materials.new("cmp_" + img.name)
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = img
        e = nt.nodes.new("ShaderNodeEmission")
        o = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(t.outputs["Color"], e.inputs["Color"])
        nt.links.new(e.outputs["Emission"], o.inputs["Surface"])
        return m

    tm = bpy.data.materials.new("cmp_text")
    tm.use_nodes = True
    tm.node_tree.nodes.clear()
    e = tm.node_tree.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (0.02, 0.02, 0.02, 1)
    o = tm.node_tree.nodes.new("ShaderNodeOutputMaterial")
    tm.node_tree.links.new(e.outputs["Emission"], o.inputs["Surface"])

    def text(body_, x, y, size):
        cu = bpy.data.curves.new("cmp_label", "FONT")
        cu.body = body_
        cu.size = size * U
        cu.align_x = "CENTER"
        cu.align_y = "CENTER"
        ob = bpy.data.objects.new("cmp_label", cu)
        ob.data.materials.append(tm)
        ob.location = (x, y, 0.01)
        sc.collection.objects.link(ob)

    for i, (path, label) in enumerate(tiles):
        if not Path(path).exists():
            continue
        rr, cc = divmod(i, cols)
        img = bpy.data.images.load(str(path), check_existing=False)
        w, h = img.size
        s_ = min((cell - 12) / w, (cell - 12) / h)
        pw, ph = w * s_ * U / 2, h * s_ * U / 2
        cx = (cc * cell + cell / 2 - Wpx / 2) * U
        cy = (Hpx / 2 - title_px - rr * (cell + label_px) - cell / 2) * U
        me = bpy.data.meshes.new("cmp_plane")
        me.from_pydata([(cx - pw, cy - ph, 0), (cx + pw, cy - ph, 0), (cx + pw, cy + ph, 0), (cx - pw, cy + ph, 0)], [], [(0, 1, 2, 3)])
        uv = me.uv_layers.new(name="UVMap")
        for li, c_ in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
            uv.data[li].uv = c_
        me.materials.append(emit_img_mat(img))
        ob = bpy.data.objects.new("cmp_plane", me)
        sc.collection.objects.link(ob)
        text(label, cx, cy - (cell / 2 + label_px * 0.45) * U, 24)
    if title:
        text(title, 0, (Hpx / 2 - title_px / 2) * U, 30)
    cd = bpy.data.cameras.new("cmp_cam")
    cd.type = "ORTHO"
    cd.ortho_scale = max(Wpx, Hpx) * U
    cam = bpy.data.objects.new("cmp_cam", cd)
    cam.location = (0, 0, 10)
    sc.collection.objects.link(cam)
    sc.camera = cam
    wd = bpy.data.worlds.new("cmp_world")
    wd.use_nodes = True
    wd.node_tree.nodes["Background"].inputs["Color"].default_value = rgba(bg)
    sc.world = wd
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = Wpx, Hpx
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = str(out_path)
    sc.render.film_transparent = False
    bpy.ops.render.render(write_still=True, scene=sc.name)
    log("composed", Path(out_path).name)


ASSETS = ROOT.parents[1] / "assets"
compose([(ROOT / "Preview.png", "Poseidon's Trident (Godly, new)"), (ASSETS / "32-excalibur" / "Preview.png", "Excalibur"),
         (ASSETS / "31-mjolnir" / "Preview.png", "Mjolnir"), (ASSETS / "34-medusas-head" / "Preview.png", "Medusa's Head")],
        4, 700, ROOT / "Compare_Catalog.png", title="Catalogue framing: Poseidon's Trident beside the current top-tier weapons")
compose([(ROOT / "Preview.png", "Preview (catalogue 3/4)"), (ROOT / "Front.png", "Front"), (ROOT / "Back.png", "Back"),
         (ROOT / "Side.png", "Side"), (ROOT / "Hero.png", "Hero (dramatic lighting)"),
         (ROOT / "Scale.png", "Scale: 5-stud R15 block figure"), (ROOT / "BaseColor.png", "BaseColor.png (1024, baked)")],
        4, 560, ROOT / "Sheet.png", title="Poseidon's Trident - Godly (Blender renders, Studio untested)")

report = {
    "name": NAME, "blender_version": bpy.app.version_string, "authored_scale_factor": round(SCALE, 5),
    "meshes": {k: v for k, v in STATS.items()},
    "total_triangles": sum(v["triangles"] for v in STATS.values()),
    "total_vertices": sum(v["vertices"] for v in STATS.values()),
    "mesh_count": len(FINAL),
    "materials": {NAME: final_mat.name, f"{NAME}_Glow": GLOW_MAT.name, f"{NAME}_GlowCore": CORE_MAT.name},
    "texture": {"file": "BaseColor.png", "size": list(tex_img.size), "packed_in_blend": bool(tex_img.packed_file),
                "uv_layers": [l.name for l in body.data.uv_layers]},
    "height_studs": round(float(allmx[2] - allmn[2]), 4),
    "bounds_blender_min": [round(float(x), 4) for x in allmn], "bounds_blender_max": [round(float(x), 4) for x in allmx],
    "bounds_studio_size": studio_size(allmx - allmn),
    "grip_z": round(GRIP.z, 4), "balance_z": round(BALANCE.z, 4),
}
uvd = np.empty(len(body.data.loops) * 2, np.float32)
body.data.uv_layers["UVMap"].data.foreach_get("uv", uvd)
report["texture"]["uv_range"] = [round(float(uvd.min()), 4), round(float(uvd.max()), 4)]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(ROOT / "Model.glb"))
g = [o for o in bpy.data.objects if o.type == "MESH"]
for o in g:
    o.data.calc_loop_triangles()
report["glb_reimport"] = {"meshes": len(g), "triangles": sum(len(o.data.loop_triangles) for o in g),
                          "names": sorted(o.name for o in g),
                          "images": sorted(f"{i.name} {i.size[0]}x{i.size[1]}" for i in bpy.data.images if i.size[0] > 0)}
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(ROOT / "Model.fbx"))
g = [o for o in bpy.data.objects if o.type == "MESH"]
for o in g:
    o.data.calc_loop_triangles()
imgs = [i for i in bpy.data.images if i.source == "FILE"]
report["fbx_reimport"] = {"meshes": len(g), "triangles": sum(len(o.data.loop_triangles) for o in g),
                          "names": sorted(o.name for o in g),
                          "embedded_images": sorted(f"{i.name} {i.size[0]}x{i.size[1]}" for i in imgs),
                          "dimensions_after_axis_conversion": {o.name: [round(x, 3) for x in o.dimensions] for o in g}}
report["checks"] = {
    "loose_vertices_total": sum(v["loose_vertices"] for v in STATS.values()),
    "zero_area_faces_total": sum(v["zero_area_faces"] for v in STATS.values()),
    "glb_triangles_match": report["glb_reimport"]["triangles"] == report["total_triangles"],
    "fbx_triangles_match": report["fbx_reimport"]["triangles"] == report["total_triangles"],
    "every_mesh_under_20k": all(v["triangles"] < 20000 for v in STATS.values()),
}
report["notes"] = [
    "Non-manifold edge counts are expected: the textured mesh is many closed parts that overlap by design "
    "(coral braid on the shaft, inlays raised through the wave and spearhead faces, rods sunk into the waves).",
    "Studio import, Neon look and in-game scale are untested (no Studio access in this task).",
]
(ROOT / "validation.json").write_text(json.dumps(report, indent=1))
log("VALIDATION", json.dumps(report["checks"]), "tris", report["total_triangles"])
log("DONE")
