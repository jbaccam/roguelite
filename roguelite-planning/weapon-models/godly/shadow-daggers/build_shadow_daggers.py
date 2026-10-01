"""Shadow Daggers: Godly melee weapon (RARITY_GODLY_ARMOR.md section 9:
"Twin daggers zip from enemy to enemy, hitting up to 5 in a chain").

Run in background Blender 5.2 only (never the user's open scene):
  blender -b --factory-startup --threads 2 --python build_shadow_daggers.py

Environment switches (all optional):
  MODE=quick     build and render flat-colour review shots to OUT only (no bake, no exports)
  MODE=full      (default) build, bake, export, validate, render the brief's set
  OUT=<dir>      where quick renders go (default: this folder)

Pipeline copied (not imported) from ../reapers-scythe/build_reapers_scythe.py: bmesh helpers, bevel
+ weighted normals, painterly bake to one 1024 BaseColor.png, Neon glow meshes, catalogue stage,
compose(), export + re-import validation.

Design: a mirrored pair of oversized curved obsidian daggers. Each blade sweeps outward with a
violet Neon cutting edge on the long convex side, a gold spine with two back-hooks on the concave
side, and gold-framed Neon moth-eye runes on both faces. The crossguard is a death's-head moth:
bone skull on the thorax (both faces), violet enamel forewings with gold piping and Neon eye-spot
gems, and smoky hindwings that curl into wisp tails. Dark wrapped grip with gold bands; gold claw
pommel holding a violet Neon gem, with two curling smoke wisps.

Axes: Blender +z up (blade up), blade flats look along +/-y. 1 Blender unit = 1 stud.
Studio axes are (-x, z, y) of Blender. The authored dagger curves toward +x; it is the LEFT-hand
dagger (character's left = Studio -X = Blender +x). The right-hand dagger is its exact x-mirror.
"""
import bpy, bmesh, math, json, os, sys, time
import numpy as np
from mathutils import Vector, Matrix
from pathlib import Path

T0 = time.time()
ROOT = Path(__file__).resolve().parent
NAME = "ShadowDaggers"
MODE = os.environ.get("MODE", "full")
OUT = Path(os.environ.get("OUT", str(ROOT)))
OUT.mkdir(parents=True, exist_ok=True)
BAKE_SIZE = 1024
DX = 0.80                    # each dagger's axis sits at x = +/-DX in the delivered pair layout
BLEED_K, BLEED_STRENGTH = 0.18, 0.85


def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)


def V(*a):
    return Vector(a)


# ---------------------------------------------------------------------------
# Palette (slot index = material index). flat, painterly ramp (sRGB), bevel-edge tint
# ---------------------------------------------------------------------------
PAL = [
    ("Obsidian", (40, 30, 62), [(0.28, (22, 16, 36)), (0.5, (40, 30, 62)), (0.78, (70, 54, 104))], (176, 150, 236)),
    ("Steel", (104, 80, 156), [(0.28, (66, 48, 108)), (0.52, (102, 78, 154)), (0.8, (150, 126, 206))], (226, 210, 255)),
    ("Gold", (238, 172, 34), [(0.3, (176, 100, 14)), (0.52, (238, 170, 30)), (0.78, (255, 226, 92))], (255, 240, 160)),
    ("Bone", (238, 224, 190), [(0.3, (200, 174, 128)), (0.54, (238, 220, 184)), (0.8, (255, 248, 228))], (255, 255, 244)),
    ("Socket", (22, 10, 26), [(0.4, (12, 5, 16)), (0.75, (34, 16, 40))], (80, 50, 110)),
    ("Enamel", (96, 44, 156), [(0.28, (60, 24, 104)), (0.52, (94, 44, 152)), (0.8, (136, 80, 200))], (210, 170, 255)),
    ("Smoke", (74, 56, 112), [(0.28, (44, 32, 72)), (0.52, (74, 56, 112)), (0.8, (120, 100, 170))], (200, 186, 240)),
    ("Leather", (46, 34, 60), [(0.28, (26, 19, 36)), (0.52, (46, 34, 60)), (0.8, (74, 58, 96))], (150, 130, 190)),
]
M_OBS, M_STEEL, M_GOLD, M_BONE, M_SOCK, M_ENAMEL, M_SMOKE, M_LEATHER = range(len(PAL))
GLOW = (170, 64, 255)       # Roblox Neon, shadow violet (Godly accent)
CORE = (232, 206, 255)      # Roblox Neon, pale lavender core of edges / eyes


def lin(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgba(c, a=1.0):
    return (lin(c[0]), lin(c[1]), lin(c[2]), a)


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def interp(table, u):
    for (u0, a), (u1, b) in zip(table, table[1:]):
        if u <= u1:
            t = (u - u0) / (u1 - u0) if u1 > u0 else 0
            return a + (b - a) * max(0.0, min(1.0, t))
    return table[-1][1]


# ---------------------------------------------------------------------------
# bmesh primitives (from the scythe pipeline)
# ---------------------------------------------------------------------------
def loft(bm, rings, closed=True, caps=True, mat=0, recalc=True, mats=None):
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
            fc = bm.faces.new(f)
            fc.material_index = mats[s] if mats else mat
            faces.append(fc)
    if closed and caps:
        for r in (vr[0], vr[-1]):
            if len(r) > 2:
                fc = bm.faces.new(r[::-1] if r is vr[0] else r)
                fc.material_index = mats[0] if mats else mat
                faces.append(fc)
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


def tube(bm, pts, radii, sides=8, mat=0, flat=1.0, phase=0.0, up=V(0, 1, 0), caps=True):
    """Tube along a centreline. radii entries: r, or (r_normal, r_binormal); 0 = pointed end."""
    T, N, B = frames(pts, up)
    sec = [(math.cos(phase + 2 * math.pi * s / sides), math.sin(phase + 2 * math.pi * s / sides)) for s in range(sides)]
    rings = []
    for k, p in enumerate(pts):
        r = radii[k]
        ra, rb = (r, r * flat) if not isinstance(r, (tuple, list)) else r
        if ra <= 1e-6 and rb <= 1e-6:
            rings.append(p.copy())
            continue
        rings.append([p + N[k] * a * ra + B[k] * b * rb for a, b in sec])
    return loft(bm, rings, mat=mat, caps=caps)


def lathe(bm, prof, sides=8, M=None, mat=0, phase=None, sy=1.0):
    M = M or Matrix()
    phase = math.pi / sides if phase is None else phase
    rings = []
    for r, z in prof:
        if r <= 1e-6:
            rings.append(M @ V(0, 0, z))
        else:
            rings.append([M @ V(r * math.cos(phase + 2 * math.pi * s / sides), r * sy * math.sin(phase + 2 * math.pi * s / sides), z)
                          for s in range(sides)])
    return loft(bm, rings, mat=mat)


def box(bm, c, size, M=None, mat=0):
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    Mt = Matrix.Translation(c) @ (M or Matrix())
    r0 = [Mt @ V(-hx, -hy, -hz), Mt @ V(hx, -hy, -hz), Mt @ V(hx, hy, -hz), Mt @ V(-hx, hy, -hz)]
    r1 = [Mt @ V(-hx, -hy, hz), Mt @ V(hx, -hy, hz), Mt @ V(hx, hy, hz), Mt @ V(-hx, hy, hz)]
    return loft(bm, [r0, r1], mat=mat)


def prism(bm, poly, origin, au, av, an, d0, d1, mat=0):
    r0 = [origin + au * u + av * v + an * d0 for u, v in poly]
    r1 = [origin + au * u + av * v + an * d1 for u, v in poly]
    return loft(bm, [r0, r1], mat=mat)


def basis(x, y, z):
    return Matrix((x, y, z)).transposed().to_4x4()


# ---------------------------------------------------------------------------
# Scene, materials, modifiers
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
    bs.inputs["Roughness"].default_value = 0.55 if name != "Gold" else 0.35
    if name == "Gold":
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


GLOW_MAT = emit_mat(f"{NAME}_Glow", GLOW, 1.5)
CORE_MAT = emit_mat(f"{NAME}_GlowCore", CORE, 1.6)
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


def soft(ob, width=0.01, angle=32.0):
    add_bevel(ob, width, segs=1, angle=angle, harden=False)
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


# ---------------------------------------------------------------------------
# Layout (studs), authored dagger on the axis x = y = 0, pommel tip near z = 0
# ---------------------------------------------------------------------------
ZB = 1.46                                   # blade root (inside the gold socket collar)
BL = [V(0, 0, ZB - 0.08), V(0, 0, ZB + 0.72), V(0.03, 0, ZB + 1.40), V(0.56, 0, ZB + 1.86)]
WE = [(0.0, 0.205), (0.18, 0.27), (0.40, 0.29), (0.64, 0.245), (0.84, 0.15), (1.0, 0.0)]   # edge-side half width
WS = [(0.0, 0.185), (0.2, 0.19), (0.45, 0.17), (0.7, 0.125), (0.88, 0.07), (1.0, 0.0)]     # spine-side half width
TH = [(0.0, 0.078), (0.4, 0.068), (0.75, 0.048), (1.0, 0.012)]                            # half thickness
GRIP_Z = (0.47, 1.06)
Y = V(0, 1, 0)


def bez(P, t):
    a = 1 - t
    return P[0] * a ** 3 + P[1] * 3 * a * a * t + P[2] * 3 * a * t * t + P[3] * t ** 3


def bez_d(P, t):
    a = 1 - t
    return ((P[1] - P[0]) * 3 * a * a + (P[2] - P[1]) * 6 * a * t + (P[3] - P[2]) * 3 * t * t).normalized()


def station(u):
    C, T = bez(BL, u), bez_d(BL, u)
    NE = V(-T.z, 0, T.x)                   # toward the cutting (convex) edge, -x at the root
    return C, T, NE, interp(WE, u), interp(WS, u), interp(TH, u)


# blade cross-section (v across: +1 cutting edge, -1 spine; y in units of half thickness)
SEC = [(1.0, 0.0), (0.42, 1.0), (-0.5, 1.0), (-1.0, 0.55), (-1.0, -0.55), (-0.5, -1.0), (0.42, -1.0)]
SEC_M = [M_STEEL, M_OBS, M_OBS, M_GOLD, M_OBS, M_OBS, M_STEEL]
EDGE_PTS = []


def sec_y(v):
    """Half thickness factor of the section at v (upper surface)."""
    if v >= 0.42:
        return (1 - v) / 0.58
    if v >= -0.5:
        return 1.0
    return 1.0 - 0.45 * (-0.5 - v) / 0.5


def build_blade():
    bm = new_bm()
    rings = []
    NS = 30
    for k in range(NS + 1):
        u = k / NS
        C, T, NE, we, ws, th = station(u)
        if k == NS:
            rings.append(C)
            continue
        rings.append([C + NE * (v * (we if v > 0 else ws)) + Y * (yy * th) for v, yy in SEC])
        EDGE_PTS.append(tuple(C + NE * we))
    loft(bm, rings, mats=SEC_M)
    ob = make_obj("Blade", bm, smooth=True)
    add_bevel(ob, 0.008, segs=2, angle=24)
    add_wn(ob)
    # back-hooks on the spine (concave side): chunky, swept toward the grip
    bm = new_bm()
    for u, sc in ((0.28, 1.4), (0.49, 1.15)):
        C, T, NE, we, ws, th = station(u)
        S = C - NE * (ws - 0.02)
        poly = [(0.075 * sc, -0.05), (0.0, 0.035 * sc), (-0.13 * sc, 0.15 * sc), (-0.07 * sc, -0.05)]
        prism(bm, poly, S, T, -NE, Y, -0.62 * th, 0.62 * th, mat=M_OBS)
    hk = make_obj("SpineHooks", bm)
    hard(hk, 0.012, segs=1, angle=28)


def build_blade_glow():
    # main cutting edge: violet Neon cap wrapping the steel edge, pale core line on the very rim
    for kind, out, base, lift, tip_ext in (("glow", 0.045, 0.72, 0.012, 0.06), ("core", 0.068, 0.93, 0.006, 0.08)):
        bm = new_bm()
        rings = []
        NS = 30
        for k in range(1, NS + 1):
            u = k / NS
            C, T, NE, we, ws, th = station(u)
            if k == NS:
                rings.append(C + T * tip_ext)
                continue
            taper = 1.0 - 0.55 * smoothstep(0.75, 1.0, u)
            yb = th * sec_y(base) + lift
            rings.append([C + NE * (we + out * taper), C + NE * (we * base) + Y * yb, C + NE * (we * base) - Y * yb])
        loft(bm, rings)
        make_obj(f"EdgeGlow_{kind}", bm, kind=kind)
    # false edge on the spine near the tip
    bm = new_bm()
    rings = []
    NS = 16
    for k in range(NS + 1):
        u = 0.58 + 0.42 * k / NS
        C, T, NE, we, ws, th = station(u)
        if k == 0:
            rings.append(C - NE * (ws * 0.95))
            continue
        if k == NS:
            rings.append(C + T * 0.06)
            continue
        g = smoothstep(0.58, 0.70, u)
        yb = th * sec_y(-0.78) + 0.01
        rings.append([C - NE * (ws + 0.035 * g), C - NE * (ws * (1 - 0.25 * g)) + Y * yb, C - NE * (ws * (1 - 0.25 * g)) - Y * yb])
    loft(bm, rings)
    make_obj("SpineGlow", bm, kind="glow")


def build_runes():
    """Gold-framed Neon moth-eye diamonds down both blade faces."""
    gb, nb = new_bm(), new_bm()
    for u, s in ((0.13, 0.095), (0.30, 0.083), (0.46, 0.07), (0.61, 0.056), (0.74, 0.042)):
        C, T, NE, we, ws, th = station(u)
        O = C + NE * 0.015
        dia = [(s, 0), (0, 0.62 * s), (-s, 0), (0, -0.62 * s)]
        fr = [(a * 1.5 + (0.012 if a > 0 else -0.012 if a < 0 else 0), b * 1.5) for a, b in dia]
        for sg in (1, -1):
            prism(gb, fr, O, T, NE, Y * sg, th - 0.006, th + 0.011, mat=M_GOLD)
            prism(nb, dia, O, T, NE, Y * sg, th - 0.004, th + 0.019)
        # small chevron ticks between runes
    g = make_obj("RuneFrames", gb, smooth=True)
    hard(g, 0.004, segs=1, angle=30)
    make_obj("Runes", nb, kind="glow")


def build_collar():
    bm = new_bm()
    prof = [(0.185, ZB - 0.14), (0.25, ZB - 0.11), (0.285, ZB - 0.05), (0.275, ZB + 0.02), (0.24, ZB + 0.07), (0.205, ZB + 0.085)]
    lathe(bm, prof, sides=10, sy=0.48, mat=M_GOLD, M=Matrix.Translation(V(-0.01, 0, 0)))
    # crown points on the collar rim, front and back faces
    for sg in (1, -1):
        for x in (-0.14, 0.0, 0.14):
            b = V(x - 0.01, sg * 0.105, ZB + 0.04)
            tube(bm, [b, b + V(0, sg * 0.005, 0.07), b + V(0, sg * 0.0, 0.12)], [0.034, 0.026, 0.0], sides=5, mat=M_GOLD)
    ob = make_obj("Collar", bm, smooth=True)
    hard(ob, 0.008, segs=1, angle=30)


def build_thorax():
    bm = new_bm()
    prof = [(0.0, 1.02), (0.10, 1.035), (0.165, 1.10), (0.195, 1.20), (0.19, 1.29), (0.16, 1.36), (0.0, 1.40)]
    lathe(bm, prof, sides=12, sy=0.74, mat=M_OBS)
    ob = make_obj("Thorax", bm, smooth=True)
    hard(ob, 0.01, segs=2, angle=28)
    # death's-head skull relief on both faces
    bb, eb, cb = new_bm(), new_bm(), new_bm()
    for sg in (-1, 1):
        Mf = Matrix.Translation(V(0, sg * 0.10, 1.215)) @ basis(V(1, 0, 0), V(0, 0, 1), V(0, sg, 0))
        lathe(bb, [(0.0, -0.01), (0.09, -0.01), (0.10, 0.03), (0.085, 0.065), (0.05, 0.085), (0.0, 0.092)], sides=8, M=Mf,
              mat=M_BONE, sy=1.12)
        box(bb, V(0, sg * 0.15, 1.115), (0.11, 0.06, 0.06), mat=M_BONE)
        for x in (-0.037, 0.037):
            Me = Matrix.Translation(V(x, sg * 0.165, 1.228)) @ basis(V(1, 0, 0), V(0, 0, 1), V(0, sg, 0))
            lathe(bb, [(0.0, 0.0), (0.034, 0.0), (0.032, 0.022), (0.0, 0.026)], sides=6, M=Me, mat=M_SOCK)
            lathe(eb, [(0.0, 0.015), (0.02, 0.016), (0.018, 0.034), (0.0, 0.038)], sides=6, M=Me)
        # teeth notches
        box(bb, V(0, sg * 0.181, 1.112), (0.075, 0.01, 0.012), mat=M_SOCK)
        # nose
        prism(bb, [(-0.014, 0.0), (0.014, 0.0), (0.0, 0.024)], V(0, sg * 0.168, 1.17), V(1, 0, 0), V(0, 0, 1), V(0, sg, 0),
              0.0, 0.022, mat=M_SOCK)
    sk = make_obj("Skulls", bb, smooth=True)
    hard(sk, 0.006, segs=1, angle=30)
    make_obj("SkullEyes", eb, kind="glow")


def spiral(c, s, r0, r1, a0, turns, n, ccw=False):
    """Points on a shrinking spiral in the xz plane around c (wisp curls). a0 in turns, measured from +x (mirrored by s)."""
    out = []
    d = 1 if ccw else -1
    for k in range(n + 1):
        t = k / n
        a = 2 * math.pi * (a0 + d * turns * t)
        r = r0 + (r1 - r0) * t
        out.append(c + V(s * r * math.cos(a), 0, r * math.sin(a)))
    out.append(out[-1] + (out[-1] - out[-2]).normalized() * 0.03)
    return out


def up_normal(T):
    n = V(-T.z, 0, T.x)
    return n if n.z >= 0 else -n


def build_wings():
    wb, gb, eb, cb, sb = new_bm(), new_bm(), new_bm(), new_bm(), new_bm()
    for s in (1, -1):
        # forewing: broad, swept up and out like a crossguard
        fw = [V(s * 0.10, 0, 1.26), V(s * 0.28, 0, 1.32), V(s * 0.46, 0, 1.43), V(s * 0.60, 0, 1.57), V(s * 0.68, 0, 1.72),
              V(s * 0.70, 0, 1.79)]
        fr = [(0.11, 0.07), (0.15, 0.064), (0.175, 0.056), (0.16, 0.046), (0.09, 0.034), (0.0, 0.0)]
        tube(wb, fw, fr, sides=8, mat=M_ENAMEL)
        T, N, B = frames(fw)
        trim = [fw[k] + up_normal(T[k]) * fr[k][0] * 0.93 for k in range(5)] + [fw[5] + V(0, 0, 0.0)]
        tube(gb, trim, [0.032, 0.034, 0.034, 0.03, 0.024, 0.0], sides=5, mat=M_GOLD)
        # Neon eye-spot gem in a gold ring, both faces
        c = fw[2] + up_normal(T[2]) * 0.0 + V(s * 0.0, 0, 0)
        for sg in (1, -1):
            Mf = Matrix.Translation(c) @ basis(V(1, 0, 0), V(0, 0, 1), V(0, sg, 0))
            lathe(gb, [(0.0, 0.03), (0.088, 0.03), (0.092, 0.058), (0.07, 0.07), (0.0, 0.066)], sides=8, M=Mf, mat=M_GOLD)
            lathe(eb, [(0.0, 0.05), (0.058, 0.05), (0.052, 0.078), (0.025, 0.09), (0.0, 0.092)], sides=8, M=Mf)
            lathe(cb, [(0.0, 0.07), (0.022, 0.07), (0.0, 0.099)], sides=6, M=Mf)
        # hindwing: smoky, swept down and out, curling into a wisp tail
        hw = [V(s * 0.09, 0, 1.17), V(s * 0.25, 0, 1.12), V(s * 0.38, 0, 1.03), V(s * 0.45, 0, 0.92)] +              spiral(V(s * 0.375, 0, 0.885), s, 0.08, 0.055, -0.15, 1.05, 6)
        hr = [(0.09, 0.06), (0.115, 0.055), (0.105, 0.05), (0.085, 0.046), (0.075, 0.043), (0.066, 0.04), (0.058, 0.036),
              (0.05, 0.033), (0.046, 0.031), (0.043, 0.029), (0.04, 0.027), (0.0, 0.0)]
        tube(sb, hw, hr, sides=8, mat=M_SMOKE)
    w = make_obj("Forewings", wb, smooth=True)
    hard(w, 0.01, segs=1, angle=30)
    g = make_obj("WingTrim", gb, smooth=True)
    add_wn(g)
    h = make_obj("Hindwings", sb, smooth=True)
    hard(h, 0.01, segs=1, angle=30)
    make_obj("WingEyes", eb, kind="glow")
    make_obj("WingEyeCores", cb, kind="core")


def build_grip():
    bm = new_bm()
    lathe(bm, [(0.0, GRIP_Z[0] - 0.02), (0.10, GRIP_Z[0] - 0.02), (0.10, GRIP_Z[1] + 0.02), (0.0, GRIP_Z[1] + 0.02)], sides=10,
          mat=M_LEATHER)
    for z0, z1 in ((GRIP_Z[0] + 0.03, 0.73), (0.79, GRIP_Z[1] - 0.03)):
        pitch = 0.072
        turns = (z1 - z0) / pitch
        steps = int(turns * 8)
        rings = []
        wdt, th = pitch * 1.02, 0.034
        for k in range(steps + 1):
            a = 2 * math.pi * turns * k / steps
            z = z0 + (z1 - z0) * k / steps
            rad = V(math.cos(a), math.sin(a), 0)
            c = V(0, 0, z) + rad * 0.106
            sec = [(-th * 0.5, -wdt * 0.5), (th * 0.2, -wdt * 0.46), (th * 0.6, 0.0), (th * 0.2, wdt * 0.46), (-th * 0.5, wdt * 0.5)]
            rings.append([c + rad * p + V(0, 0, q) for p, q in sec])
        loft(bm, rings, mat=M_LEATHER)
    ob = make_obj("GripWrap", bm, smooth=False)
    b2 = new_bm()
    for z, h, ro in ((GRIP_Z[0], 0.075, 0.15), (0.76, 0.065, 0.145), (GRIP_Z[1], 0.08, 0.15)):
        prof = [(0.09, z - h / 2), (ro, z - h / 2 + 0.012), (ro + 0.012, z), (ro, z + h / 2 - 0.012), (0.09, z + h / 2)]
        lathe(b2, prof, sides=8, mat=M_GOLD)
    ob2 = make_obj("GripBands", b2, smooth=True)
    hard(ob2, 0.008, segs=1, angle=30)


def build_pommel():
    bm = new_bm()
    prof = [(0.0, 0.215), (0.11, 0.215), (0.165, 0.26), (0.15, 0.32), (0.105, 0.37), (0.10, 0.44)]
    lathe(bm, prof, sides=10, mat=M_GOLD)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        d = V(math.cos(a), math.sin(a) * 0.9, 0)
        tube(bm, [d * 0.15 + V(0, 0, 0.25), d * 0.142 + V(0, 0, 0.17), d * 0.118 + V(0, 0, 0.09)], [0.036, 0.03, 0.0], sides=6,
             mat=M_GOLD)
    ob = make_obj("PommelClaw", bm, smooth=True)
    hard(ob, 0.008, segs=1, angle=30)
    gb, cb = new_bm(), new_bm()
    lathe(gb, [(0.0, -0.04), (0.118, 0.10), (0.122, 0.16), (0.075, 0.25), (0.0, 0.26)], sides=6, mat=0)
    make_obj("PommelGem", gb, kind="glow")
    # wisps curling off the pommel cup
    sb = new_bm()
    for s in (1, -1):
        pts = [V(s * 0.12, 0, 0.33), V(s * 0.23, 0, 0.29)] + spiral(V(s * 0.30, 0, 0.405), s, 0.115, 0.05, -0.25, 1.2, 7, ccw=True)
        rad = [(0.06, 0.042), (0.072, 0.045), (0.068, 0.042), (0.062, 0.039), (0.056, 0.036), (0.05, 0.033), (0.045, 0.03),
               (0.04, 0.028), (0.037, 0.026), (0.034, 0.025), (0.0, 0.0)]
        tube(sb, pts, rad, sides=6, mat=M_SMOKE)
    w = make_obj("PommelWisps", sb, smooth=True)
    hard(w, 0.008, segs=1, angle=30)


def build_all():
    build_blade()
    build_blade_glow()
    build_runes()
    build_collar()
    build_thorax()
    build_wings()
    build_grip()
    build_pommel()


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
log("TRIS per dagger", sum(TRIS.values()), sorted(TRIS.items(), key=lambda kv: -kv[1]))


# ---------------------------------------------------------------------------
# Review stage (the weapon catalogue's own framing)
# ---------------------------------------------------------------------------
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


def setup_comp(bloom=0.45):
    tree = bpy.data.node_groups.get("ReviewComp") or bpy.data.node_groups.new("ReviewComp", "CompositorNodeTree")
    tree.nodes.clear()
    if not tree.interface.items_tree:
        tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = tree.nodes.new("CompositorNodeRLayers")
    out = tree.nodes.new("NodeGroupOutput")
    if bloom > 0:
        g = tree.nodes.new("CompositorNodeGlare")
        g.inputs["Type"].default_value = "Bloom"
        g.inputs["Quality"].default_value = "High"
        g.inputs["Threshold"].default_value = 0.55
        g.inputs["Strength"].default_value = bloom
        g.inputs["Size"].default_value = 0.55
        tree.links.new(rl.outputs["Image"], g.inputs["Image"])
        tree.links.new(g.outputs["Image"], out.inputs[0])
    else:
        tree.links.new(rl.outputs["Image"], out.inputs[0])
    scene.compositing_node_group = tree


STAGE = {}


def clear_stage():
    for o in list(REVIEW.objects):
        bpy.data.objects.remove(o, do_unlink=True)


def catalog_stage(objs, angle, camvec, res=1000, samples=24, ortho_pad=1.18, world=0.0509, floor=True, extra_objs=()):
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

    def point(o, p):
        o.rotation_euler = (Vector(p) - o.location).to_track_quat("-Z", "Y").to_euler()

    point(cam, center)
    cd.type = "ORTHO"
    bpy.context.view_layer.update()
    inv = cam.rotation_euler.to_matrix().transposed()
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
    STAGE.update(center=center, extent=extent, cam=cam)

    def restore():
        for o in objs:
            o.matrix_world = saved[o.name]
        bpy.context.view_layer.update()

    return restore


def render(path):
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    log("rendered", Path(path).name)


def join(objs, name):
    select_only(objs)
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def mirror_copy(ob, name):
    """Exact x-mirror (scale -1 applied, winding and custom normals fixed by Blender)."""
    me = ob.data.copy()
    me.name = name
    o2 = bpy.data.objects.new(name, me)
    ASSET.objects.link(o2)
    o2["kind"] = ob["kind"]
    o2.scale = (-1, 1, 1)
    select_only([o2])
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    # outward-normal check: flip if the apply did not
    co = np.array([tuple(v.co) for v in me.vertices])
    cen = co.mean(axis=0)
    s = sum((Vector(p.center) - Vector(cen)).dot(p.normal) * p.area for p in me.polygons)
    if s < 0:
        me.flip_normals()
        log("flipped normals on", name)
    return o2


def shift(ob, d):
    ob.data.transform(Matrix.Translation(d))
    ob.data.update()


if MODE == "quick":
    setup_comp(0.4)
    pair = []
    for o in list(PARTS):
        m = mirror_copy(o, o.name + "_R")
        shift(o, V(DX, 0, 0))
        shift(m, V(-DX, 0, 0))
        pair += [o, m]
    for nm, ang, vec in (("q_catalog", -12, (1.6, -15, 6.2)), ("q_front", 0, (0, -15, 1.2)), ("q_side", 0, (15, 0, 1.2))):
        r = catalog_stage(pair, ang, vec, res=700, samples=12)
        render(OUT / f"{nm}.png")
        r()
    r = catalog_stage(pair, 0, (1.2, -15, 3.0), res=700, samples=12)
    cam = STAGE["cam"]
    cam.data.ortho_scale = 1.5
    tgt = V(DX, 0, 1.25 + STAGE["center"].z - 1.6)
    tgt = V(DX, 0, 1.3)
    cam.location = tgt + V(1.5, -9, 1.5)
    cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
    render(OUT / "q_guard.png")
    r()
    log("QUICK DONE")
    sys.exit(0)

# ===========================================================================
# FULL MODE
# ===========================================================================
pts0 = world_bounds(PARTS)
Z0 = min(p.z for p in pts0)
for o in PARTS:
    o.data.transform(Matrix.Translation(V(0, 0, -Z0)))
    o.data.update()
EDGE_PTS = [tuple(Vector(p) - V(0, 0, Z0)) for p in EDGE_PTS]
_by_kind = {k: [o for o in PARTS if o["kind"] == k] for k in ("tex", "glow", "core")}
body = join(_by_kind["tex"], f"{NAME}_L")
glow_ob = join(_by_kind["glow"], f"{NAME}_L_Glow")
core_ob = join(_by_kind["core"], f"{NAME}_L_GlowCore")
PARTS = [body, glow_ob, core_ob]
for o in PARTS:
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


def np_smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


P, NRM, MI = corner_arrays(body.data)
NL = len(P)
paint = np.ones((NL, 3), np.float32)
edge = np.array(EDGE_PTS, np.float32)
R_AX = np.abs(P[:, 0])
sel = MI == M_STEEL
if sel.any():
    d = np.min(np.linalg.norm(P[sel][:, None, :] - edge[None, :, :], axis=2), axis=1)
    k = 1 - np_smooth(0.02, 0.22, d)
    paint[sel] *= (0.78 + 0.45 * k)[:, None]
sel = MI == M_OBS
paint[sel] *= (0.86 + 0.2 * np.clip((P[sel][:, 2] - 1.4) / 1.9, 0, 1))[:, None]
sel = MI == M_ENAMEL
paint[sel] *= (0.72 + 0.5 * np_smooth(0.12, 0.66, R_AX[sel]))[:, None]
sel = MI == M_SMOKE
paint[sel] *= (0.72 + 0.75 * np_smooth(0.12, 0.42, R_AX[sel]))[:, None]
sel = MI == M_BONE
paint[sel] *= np.array([1.0, 0.985, 0.95], np.float32)

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
    w = gA[None, :] * wrap * np.exp(-d / 0.12) / (d * d + 0.03 ** 2)
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
    n1.inputs["Scale"].default_value = 2.6
    n1.inputs["Detail"].default_value = 2.0
    n1.inputs["Roughness"].default_value = 0.45
    n1.inputs["Distortion"].default_value = 0.35
    L(pos, n1.inputs["Vector"])
    n2 = N("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 8.0
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
    if idx in (M_SMOKE, M_LEATHER):      # soft streaks along the form
        vm = N("ShaderNodeVectorMath")
        vm.operation = "MULTIPLY"
        L(pos, vm.inputs[0])
        vm.inputs[1].default_value = (9.0, 9.0, 2.0)
        nf = N("ShaderNodeTexNoise")
        nf.inputs["Scale"].default_value = 1.0
        L(vm.outputs[0], nf.inputs["Vector"])
        albedo = mix(albedo, grey(remap(nf.outputs["Fac"], 0.3, 0.7, 0.82, 1.15)), 1.0, "MULTIPLY")
    k = dot_light(KEY_DIR)
    light = remap(k, 0.0, 1.0, 0.56, 1.2)
    tint = mix((0.86, 0.90, 1.07, 1), (1.08, 1.0, 0.9, 1), k)
    ao = N("ShaderNodeAmbientOcclusion")
    ao.samples = 16
    ao.inputs["Distance"].default_value = 0.16
    aof = remap(ao.outputs["AO"], 0.2, 1.0, 0.5, 1.0)
    cav = N("ShaderNodeAmbientOcclusion")
    cav.samples = 16
    cav.inputs["Distance"].default_value = 0.03
    cavf = remap(cav.outputs["AO"], 0.35, 1.0, 0.6, 1.0)
    sep = N("ShaderNodeSeparateXYZ")
    L(pos, sep.inputs["Vector"])
    height = remap(sep.outputs["Z"], 0.0, ZTOP, 0.9, 1.05)
    shade = math_("MULTIPLY", math_("MULTIPLY", light, aof), math_("MULTIPLY", cavf, height))
    lit = mix(mix(albedo, tint, 1.0, "MULTIPLY"), grey(shade), 1.0, "MULTIPLY")
    rim = remap(dot_light(RIM_DIR), 0.25, 1.0, 0.0, 0.14)
    lit = mix(lit, (0.62, 0.34, 1.0, 1), rim, "ADD")
    bev = N("ShaderNodeBevel")
    bev.samples = 8
    bev.inputs["Radius"].default_value = 0.012
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
bs.inputs["Specular IOR Level"].default_value = 0.25
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

# ---- the pair: authored dagger = left hand at +DX; right hand = exact x-mirror at -DX (shares UVs + texture)
GRIP_LOCAL = V(0, 0, (GRIP_Z[0] + GRIP_Z[1]) / 2 - Z0)
R_objs = [mirror_copy(o, o.name.replace("_L", "_R", 1)) for o in (body, glow_ob, core_ob)]
L_objs = [body, glow_ob, core_ob]
for o in L_objs:
    shift(o, V(DX, 0, 0))
for o in R_objs:
    shift(o, V(-DX, 0, 0))
FINAL = L_objs + R_objs
body_R = R_objs[0]

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
allmn = np.min([s["bounds_min"] for s in STATS.values()], axis=0)
allmx = np.max([s["bounds_max"] for s in STATS.values()], axis=0)
per_dagger = sum(STATS[o.name]["triangles"] for o in L_objs)
install = {
    "name": NAME, "blender_version": bpy.app.version_string, "status": "Blender-verified, Studio untested",
    "units": "1 Blender unit = 1 stud, authored at hero size; set the play size in Studio by uniform scale",
    "axes": "Studio = (-x, z, y) of Blender; FBX exported with axis_forward=-Z, axis_up=Y",
    "texture": f"BaseColor.png {BAKE_SIZE}x{BAKE_SIZE}, baked painted lighting, shared by both daggers (the right dagger is an "
               "exact mirror with the same UVs); use MeshPart.TextureID (not SurfaceAppearance)",
    "parts": {},
    "daggers": {},
    "notes": ["Two independent daggers, one per hand. Each has its own textured MeshPart plus a Neon glow and a Neon core "
              "MeshPart; weld the three parts of a dagger together and to that hand.",
              "Every MeshPart imports centred on its own bounding box: place each at its center_studio relative to the shared "
              "model origin (Blender origin, on the floor midway between the two daggers).",
              "grip_point = middle of the wrapped grip on that dagger's axis (hand attachment / spin pivot). blade_axis = the "
              "grip-to-blade direction in the delivered pose. The cutting edge (long glowing curve) faces the other dagger "
              "(inward); the tip curves outward.",
              "The left-hand dagger sits at Studio -X (character's left when facing -Z), the right-hand dagger at Studio +X."],
}
for side, objs, sx in (("left_hand", L_objs, DX), ("right_hand", R_objs, -DX)):
    grip = GRIP_LOCAL + V(sx, 0, 0)
    st = STATS[objs[0].name]
    tc = (np.array(st["bounds_min"]) + np.array(st["bounds_max"])) / 2
    install["daggers"][side] = {
        "parts": [o.name for o in objs],
        "grip_point_studio": studio(grip),
        "grip_point_relative_to_textured_center": studio(np.array(tuple(grip)) - tc),
        "blade_axis_studio": [0.0, 1.0, 0.0],
        "flat_normal_studio": [0.0, 0.0, 1.0],
        "tip_curves_toward_studio": [round(-math.copysign(1, sx), 1), 0.0, 0.0],
        "triangles": sum(STATS[o.name]["triangles"] for o in objs),
    }
for o in FINAL:
    st = STATS[o.name]
    mn, mx = np.array(st["bounds_min"]), np.array(st["bounds_max"])
    part = {"kind": "textured" if o in (body, body_R) else "glow", "center_studio": studio((mn + mx) / 2),
            "size_studio": studio_size(mx - mn), "triangles": st["triangles"]}
    if "_GlowCore" in o.name:
        part.update(material="Neon", color_rgb=list(CORE), note="pale lavender cores: cutting-edge rim line, wing eye-spot pupils")
    elif "_Glow" in o.name:
        part.update(material="Neon", color_rgb=list(GLOW),
                    note="violet glow: cutting edge, spine false edge, blade runes, skull eyes, wing eye-spots, pommel gem")
    else:
        part.update(material="SmoothPlastic (or Plastic), Color white", texture_id="BaseColor.png")
    install["parts"][o.name] = part
install["vfx_notes"] = [
    "Chain dash (ability): for each hop, spawn an afterimage Beam between the dagger's current Attachment and the next enemy's "
    "Attachment: Color ColorSequence (232,206,255) -> (170,64,255) -> (60,20,110), LightEmission 1, LightInfluence 0, "
    "Width0 1.2 / Width1 0.3 studs, Transparency 0 -> 1 over 0.25 s (tween), FaceCamera true, Segments 1.",
    "Afterimage ghosts: at every chain hit clone the dagger's three MeshParts (or the Neon glow part only) as a non-colliding "
    "copy, Material Neon, Color (170,64,255), Transparency tween 0.35 -> 1 over 0.3 s; up to 5 hits = up to 5 ghosts, one per "
    "hop, leaving a violet zig-zag between enemies.",
    "Blade Trail per dagger: Attachment0 at the guard collar, Attachment1 at the blade tip; Color (170,64,255) -> (60,20,110), "
    "Lifetime 0.18, MinLength 0.05, WidthScale 1 -> 0, Transparency 0.2 -> 1, LightEmission 1, FaceCamera true.",
    "Hit burst on each chained enemy: ParticleEmitter Burst 12, Color (170,64,255) -> (232,206,255), Size 0.8 -> 0, "
    "Lifetime 0.25-0.4, Speed 8-14, SpreadAngle 180, LightEmission 1, Drag 6; plus 4 dark smoke puffs Color (40,30,62), "
    "Size 1.2 -> 2.2, Transparency 0.4 -> 1, Lifetime 0.5, Speed 2.",
    "Idle (optional): PointLight on the pommel gem, Color (170,64,255), Brightness 1.2, Range 6; a slow smoke ParticleEmitter "
    "at the pommel wisps, Rate 3, Color (74,56,112), Size 0.4 -> 0.9, Transparency 0.5 -> 1, Lifetime 0.8, Speed 0.6, "
    "Acceleration (0,1.5,0).",
]
(ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=1))
log("stats", {k: v["triangles"] for k, v in STATS.items()}, "total", sum(v["triangles"] for v in STATS.values()))

# ---------------------------------------------------------------------------
# Renders: Preview, Front, Back, Side, Scale, Hero (brief's set only)
# ---------------------------------------------------------------------------
setup_comp(0.45)


def shoot_catalog(name, angle, camvec, samples=32, res=1000):
    r = catalog_stage(FINAL, angle, camvec, samples=samples, res=res)
    render(ROOT / name)
    r()


shoot_catalog("Preview.png", -12, (1.6, -15, 6.2), samples=48)
shoot_catalog("Front.png", 0, (0, -15, 1.2))
shoot_catalog("Back.png", 0, (0, 15, 1.2))
shoot_catalog("Side.png", 0, (15, 0, 1.2))

fig_bm = new_bm()
FX = 2.6
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
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.016, 0.017, 0.032, 1)
    cd = bpy.data.cameras.new("Hero camera")
    cam = bpy.data.objects.new("Hero camera", cd)
    REVIEW.objects.link(cam)
    cd.lens = lens
    cam.location = cam_loc
    cam.rotation_euler = (target - cam_loc).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    for nm, loc, col, en, sz in (("Hero key", V(-3, -5, 6), (0.78, 0.84, 1.0), 700, 3),
                                  ("Hero rim violet", V(3, 5, 4), (0.62, 0.22, 1.0), 1300, 3),
                                  ("Hero rim steel", V(-4, 4, 4), (0.6, 0.7, 1.0), 650, 3),
                                  ("Hero fill violet", V(2, -4, 0.5), (0.55, 0.4, 1.0), 140, 3)):
        ld = bpy.data.lights.new(nm, "AREA")
        ld.color = col
        ld.energy = en
        ld.size = sz
        lo = bpy.data.objects.new(nm, ld)
        REVIEW.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = (V(0, 0, 1.6) - loc).to_track_quat("-Z", "Y").to_euler()
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


hero("Hero.png", V(1.5, -5.6, 2.5), V(0.0, 0, 1.65), lens=50)

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
compose([(ROOT / "Preview.png", "Shadow Daggers (Godly, new)"), (ASSETS / "32-excalibur" / "Preview.png", "Excalibur"),
         (ASSETS / "31-mjolnir" / "Preview.png", "Mjolnir"), (ASSETS / "34-medusas-head" / "Preview.png", "Medusa's Head")],
        4, 700, ROOT / "Compare_Catalog.png", title="Catalogue framing: Godly Shadow Daggers beside the current top-tier weapons")
compose([(ROOT / "Preview.png", "Preview (catalogue 3/4)"), (ROOT / "Front.png", "Front"), (ROOT / "Back.png", "Back"),
         (ROOT / "Side.png", "Side"), (ROOT / "Hero.png", "Hero (dramatic lighting)"),
         (ROOT / "Scale.png", "Scale: 5-stud R15 block figure"), (ROOT / "BaseColor.png", "BaseColor.png (1024, baked)")],
        4, 560, ROOT / "Sheet.png", title="Shadow Daggers - Godly (Blender renders, Studio untested)")

# ---------------------------------------------------------------------------
# Validation (re-import both exports into a fresh file)
# ---------------------------------------------------------------------------
report = {
    "name": NAME, "blender_version": bpy.app.version_string,
    "meshes": {k: v for k, v in STATS.items()},
    "total_triangles": sum(v["triangles"] for v in STATS.values()),
    "triangles_per_dagger": per_dagger,
    "total_vertices": sum(v["vertices"] for v in STATS.values()),
    "mesh_count": len(FINAL),
    "materials": {o.name: o.data.materials[0].name for o in FINAL},
    "texture": {"file": "BaseColor.png", "size": list(tex_img.size), "packed_in_blend": bool(tex_img.packed_file),
                "uv_layers": [l.name for l in body.data.uv_layers]},
    "dagger_length_studs": round(float(allmx[2] - allmn[2]), 4),
    "bounds_blender_min": [round(float(x), 4) for x in allmn], "bounds_blender_max": [round(float(x), 4) for x in allmx],
    "bounds_studio_size": studio_size(allmx - allmn),
}
uvd = np.empty(len(body.data.loops) * 2, np.float32)
body.data.uv_layers["UVMap"].data.foreach_get("uv", uvd)
report["texture"]["uv_range"] = [round(float(uvd.min()), 4), round(float(uvd.max()), 4)]
# mirror exactness: every vertex of R mirrored in x must land on a vertex of L (same mesh order)
mir = {}
for a, b in zip(L_objs, R_objs):
    ca = np.array([tuple(v.co) for v in a.data.vertices])
    cb = np.array([tuple(v.co) for v in b.data.vertices])
    cb[:, 0] *= -1
    mir[a.name] = round(float(np.abs(ca - cb).max()), 6) if ca.shape == cb.shape else "vertex count differs"
report["mirror_max_vertex_error"] = mir
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
    "pair_is_exact_mirror": all(isinstance(v, float) and v < 1e-4 for v in mir.values()),
}
report["notes"] = [
    "Non-manifold edge counts are expected: each textured mesh is many closed parts that overlap by design "
    "(wraps on the grip, skull on the thorax, trim on the wings, runes on the blade).",
    "Studio import, Neon look and in-game scale are untested (no Studio access in this task).",
]
(ROOT / "validation.json").write_text(json.dumps(report, indent=1))
log("VALIDATION", json.dumps(report["checks"]), "tris", report["total_triangles"])
log("DONE")
