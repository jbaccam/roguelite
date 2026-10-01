"""Shadow Daggers (round 2): Godly melee weapon (RARITY_GODLY_ARMOR.md section 9:
"Twin daggers zip from enemy to enemy, hitting up to 5 in a chain").

Run in background Blender 5.2 only (never the user's open scene):
  blender -b --factory-startup --threads 2 --python build_shadow_daggers.py

Environment switches (all optional):
  MODE=quick     build and render flat-colour review shots to OUT only (no bake, no exports)
  MODE=full      (default) build, bake, export, validate, render the brief's set
  OUT=<dir>      where quick renders go (default: ./wip)

Pipeline copied (not imported) from ../reapers-scythe/build_reapers_scythe.py via the v1 generator:
bmesh helpers, bevel + weighted normals, painterly bake to one 1024 BaseColor.png, Neon glow
meshes, catalogue stage, compose(), export + re-import validation.

Design (owner references: Kamish's-Wrath-style demon dagger pair, ref1..ref4):
  Dagger A (left hand)  "Rend": a near-black jagged blade, serrated cutting edge with a crimson Neon
      edge, glowing crimson crack veins on both faces, three hooked back-spikes on the spine and a
      Neon false edge near the needle tip.
  Dagger B (right hand) "Fang": a blood-crimson broad blade with four layered bone chevron plates
      climbing from the guard (claw tips past both edges), a hooked tip with a spine barb, a hot
      crimson Neon edge and a Neon line on the ridge.
  Shared hilt: a demon eye guard (bone lids, crimson Neon eyeball, slit pupil, both faces) held by
      hooked gold claws and bone claw plates; dragon-scale grip (overlapping scale rows) between
      gold collars; a gold claw pommel gripping a crimson Neon spike.
  Blades are diamond in section (centre ridge + steeper edge bevel) with crisp 1-segment bevels.

Axes: Blender +z up (blade up), blade flats look along +/-y. 1 Blender unit = 1 stud.
Studio axes are (-x, z, y) of Blender. Dagger A sits at Blender +x (character's left = Studio -X),
dagger B at Blender -x; each blade's tip curves outward, cutting edges face each other.
"""
import bpy, bmesh, math, json, os, sys, time
import numpy as np
from mathutils import Vector, Matrix
from pathlib import Path

T0 = time.time()
ROOT = Path(__file__).resolve().parent
NAME = "ShadowDaggers"
MODE = os.environ.get("MODE", "full")
OUT = Path(os.environ.get("OUT", str(ROOT / "wip")))
BAKE_SIZE = 1024
DX = 0.90                    # each dagger's axis sits at x = +/-DX in the delivered pair layout
BLEED_K, BLEED_STRENGTH, BLEED_FALL = 0.12, 0.42, 0.06


def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)


def V(*a):
    return Vector(a)


Y = V(0, 1, 0)

# ---------------------------------------------------------------------------
# Palette (slot index = material index). flat, painterly ramp (sRGB), bevel-edge tint
# ---------------------------------------------------------------------------
PAL = [
    ("Obsidian", (26, 9, 14), [(0.28, (9, 3, 6)), (0.5, (24, 8, 13)), (0.78, (50, 15, 22))], (170, 48, 56)),
    ("Crimson", (112, 8, 20), [(0.28, (46, 2, 9)), (0.52, (108, 8, 20)), (0.8, (158, 18, 28))], (240, 90, 80)),
    ("Hot", (140, 10, 22), [(0.3, (84, 4, 12)), (0.55, (138, 10, 22)), (0.82, (188, 28, 32))], (250, 120, 104)),
    ("Gold", (206, 138, 28), [(0.3, (110, 54, 10)), (0.52, (204, 134, 26)), (0.8, (250, 198, 74))], (255, 228, 140)),
    ("Bone", (214, 190, 146), [(0.3, (128, 92, 60)), (0.54, (206, 180, 136)), (0.8, (242, 226, 192))], (255, 248, 226)),
    ("Scale", (36, 26, 42), [(0.28, (14, 9, 20)), (0.52, (36, 26, 42)), (0.8, (72, 50, 78))], (176, 96, 112)),
    ("Socket", (14, 4, 8), [(0.4, (7, 2, 4)), (0.75, (26, 8, 12))], (90, 30, 36)),
    ("Shard", (190, 160, 116), [(0.3, (100, 68, 40)), (0.55, (188, 158, 114)), (0.82, (228, 206, 164))], (248, 234, 204)),
]
M_OBS, M_CRIM, M_HOT, M_GOLD, M_BONE, M_SCALE, M_SOCK, M_SHARD = range(len(PAL))
GLOW = (255, 14, 30)        # Roblox Neon, blood crimson (long lines: edges, veins, ridge, eye, pommel)
CORE = (255, 64, 48)       # Roblox Neon, hot core (edge rim lines, iris)


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


def frames(pts, up=Y):
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


DIAMOND = [(1, 0), (0, 1), (-1, 0), (0, -1)]
HEX = [(1, 0), (0.55, 1), (-0.55, 1), (-1, 0), (-0.55, -1), (0.55, -1)]


def tube(bm, pts, radii, sides=8, mat=0, flat=1.0, phase=0.0, up=Y, caps=True, shape=None):
    """Tube along a centreline. radii entries: r, or (r_normal, r_binormal); 0 = pointed end."""
    T, N, B = frames(pts, up)
    sec = shape or [(math.cos(phase + 2 * math.pi * s / sides), math.sin(phase + 2 * math.pi * s / sides)) for s in range(sides)]
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


def catmull(ctrl, n=4):
    P = [ctrl[0] + (ctrl[0] - ctrl[1])] + list(ctrl) + [ctrl[-1] + (ctrl[-1] - ctrl[-2])]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(ctrl[-1].copy())
    return out


def claw(bm, ctrl, r0, mat, n=4, up=Y, belly=0.8, shape=DIAMOND, rmid=None):
    """Tapered claw/hook along a Catmull-Rom path: diamond (or hex) section, needle point."""
    pts = catmull([Vector(c) for c in ctrl], n)
    m = len(pts)
    radii = []
    for k in range(m):
        t = k / (m - 1)
        f = 0.0 if k == m - 1 else (1 - t) ** belly
        if rmid is not None:
            f *= 1 + rmid * math.sin(math.pi * t)
        radii.append((r0[0] * f, r0[1] * f))
    return tube(bm, pts, radii, mat=mat, up=up, shape=shape)


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
    bs.inputs["Roughness"].default_value = 0.5 if name != "Gold" else 0.35
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


GLOW_STRENGTH = float(os.environ.get("GLOW_STRENGTH", "0.85"))
GLOW_MAT = emit_mat(f"{NAME}_Glow", GLOW, GLOW_STRENGTH)
CORE_MAT = emit_mat(f"{NAME}_GlowCore", CORE, GLOW_STRENGTH * 0.9)
PARTS = []
CUR = {"d": "A"}


def new_bm():
    return bmesh.new()


def make_obj(name, bm, kind="tex", smooth=False, coll=None):
    bm.normal_update()
    name = f"{CUR['d']}_{name}" if kind != "fig" else name
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
    ob["dagger"] = CUR["d"]
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


def hard(ob, width=0.008, segs=1, angle=30.0):
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


# ---------------------------------------------------------------------------
# Layout (studs). Each dagger is authored on the axis x = y = 0 with its tip curving to +x
# (dagger B is x-mirrored when the pair is placed). Pommel spike tip near z = 0.
# ---------------------------------------------------------------------------
ZB = 1.42                                   # blade root (inside the gold blade collar)
GRIP_Z = (0.50, 1.00)


def bez(P, t):
    a = 1 - t
    return P[0] * a ** 3 + P[1] * 3 * a * a * t + P[2] * 3 * a * t * t + P[3] * t ** 3


def bez_d(P, t):
    a = 1 - t
    return ((P[1] - P[0]) * 3 * a * a + (P[2] - P[1]) * 6 * a * t + (P[3] - P[2]) * 3 * t * t).normalized()


class Blade:
    """Diamond-section blade on a Bezier centreline. NE = toward the cutting (convex) edge (-x at the root).
    Ring per station: [E, Eb+, R+, Sb+, S, Sb-, R-, Eb-]  (E edge, Eb edge-bevel line, R ridge, S spine)."""

    def __init__(self, P, WE, WS, TH, teeth=None, mats=(M_OBS, M_CRIM, M_OBS), NS=40):
        self.P, self.WE, self.WS, self.TH, self.teeth, self.mats, self.NS = P, WE, WS, TH, teeth, mats, NS
        self.edge_pts = []

    def frame(self, u):
        C, T = bez(self.P, u), bez_d(self.P, u)
        return C, T, V(-T.z, 0, T.x)

    def dims(self, u):
        we, ws, th = interp(self.WE, u), interp(self.WS, u), interp(self.TH, u)
        return we, ws, th, (we - ws) * 0.5

    def tooth(self, u):
        if not self.teeth:
            return 0.0, 0.0
        ua, ub, n, depth, hook = self.teeth
        if u < ua or u > ub:
            return 0.0, 0.0
        t = (u - ua) / (ub - ua) * n
        k = min(int(t), n - 1)
        f = t - k
        sh = f / 0.3 if f < 0.3 else 1 - (f - 0.3) / 0.7
        fade = 0.65 + 0.35 * (1 - k / max(1, n - 1))
        return depth * sh * fade, hook * sh * fade

    def stations(self):
        us = [k / self.NS for k in range(self.NS + 1)]
        if self.teeth:
            ua, ub, n, _, _ = self.teeth
            keys = [ua + (ub - ua) * k / n for k in range(n + 1)] + [ua + (ub - ua) * (k + 0.3) / n for k in range(n)]
            us = [u for u in us if min(abs(u - q) for q in keys) > 0.006] + keys
        return sorted(set(round(u, 6) for u in us))

    def ring(self, u):
        C, T, NE = self.frame(u)
        we, ws, th, ro = self.dims(u)
        dw, dt = self.tooth(u)
        R = C + NE * ro
        E = C + NE * (we + dw) + T * dt
        Eb = R + NE * ((we - ro) * 0.75)
        S = C - NE * ws
        Sb = R - NE * ((ws + ro) * 0.70)
        ye, yr, ys = th * 0.5, th, th * 0.42
        return [E, Eb + Y * ye, R + Y * yr, Sb + Y * ys, S, Sb - Y * ys, R - Y * yr, Eb - Y * ye]

    def surf(self, u, v, sg, lift=0.0):
        """Point on the blade face (sg=+1 front/+y, -1 back) at u along, v across (+1 edge .. -1 spine)."""
        C, T, NE = self.frame(u)
        we, ws, th, ro = self.dims(u)
        if v >= 0:
            x = ro + v * (we - ro)
            y = th * (1 - v / 0.75 * 0.5) if v <= 0.75 else th * 0.5 * (1 - v) / 0.25
        else:
            a = -v
            x = ro - a * (ws + ro)
            y = th * (1 - a / 0.7 * 0.58) if a <= 0.7 else th * 0.42 * (1 - a) / 0.3
        return C + NE * x + Y * sg * (y + lift)

    def build(self, name):
        bm = new_bm()
        rings = []
        main, edge, spine = self.mats[:3]
        face2 = self.mats[3] if len(self.mats) > 3 else main
        for u in self.stations():
            if u >= 1.0:
                rings.append(bez(self.P, 1.0))
                continue
            r = self.ring(u)
            rings.append(r)
            self.edge_pts.append(tuple(r[0]))
        loft(bm, rings, mats=[edge, main, face2, spine, spine, face2, main, edge])
        ob = make_obj(name, bm, smooth=True)
        add_bevel(ob, 0.005, segs=1, angle=20)
        add_wn(ob)
        return ob

    def edge_glow(self, u0, out=0.032, cover=0.5):
        for kind, o, f, lift, ext in (("glow", out, cover, 0.006, 0.07), ("core", out + 0.012, 0.1, 0.004, 0.09)):
            bm = new_bm()
            rings = []
            us = [u for u in self.stations() if u >= u0]
            for u in us:
                C, T, NE = self.frame(u)
                if u >= 1.0:
                    rings.append(C + T * ext)
                    continue
                r = self.ring(u)
                we, ws, th, ro = self.dims(u)
                taper = 1.0 - 0.5 * smoothstep(0.8, 1.0, u)
                E, Eb = r[0], (r[1] + r[7]) * 0.5
                G = E.lerp(Eb, f)
                yb = th * 0.5 * f + lift
                if kind == "core":
                    G = E.lerp(Eb, 0.12)
                    yb = th * 0.5 * 0.12 + lift
                rings.append([E + NE * (o * taper), G + Y * yb, G - Y * yb])
            loft(bm, rings)
            make_obj(f"EdgeGlow_{kind}", bm, kind=kind)

    def spine_glow(self, u0, out=0.026, cover=0.4):
        bm = new_bm()
        rings = []
        us = [u for u in self.stations() if u >= u0]
        for i, u in enumerate(us):
            C, T, NE = self.frame(u)
            if u >= 1.0:
                rings.append(C + T * 0.07)
                continue
            r = self.ring(u)
            we, ws, th, ro = self.dims(u)
            g = smoothstep(u0, u0 + 0.12, u)
            S, Sb = r[4], (r[3] + r[5]) * 0.5
            G = S.lerp(Sb, cover * max(g, 0.15))
            yb = th * 0.42 * cover * max(g, 0.15) + 0.006
            rings.append([S - NE * (out * g), G + Y * yb, G - Y * yb])
        loft(bm, rings)
        make_obj("SpineGlow", bm, kind="glow")

    def ribbon(self, bm, poly, hw0, hw1, sg, lift=0.008, sink=0.02, sub=3):
        uv = []
        for (a, b) in zip(poly, poly[1:]):
            for k in range(sub):
                t = k / sub
                uv.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        uv.append(poly[-1])
        P = [self.surf(u, v, sg, lift) for u, v in uv]
        m = len(P)
        rings = []
        for k, p in enumerate(P):
            t_ = P[min(k + 1, m - 1)] - P[max(k - 1, 0)]
            t_.y = 0
            t_.normalize()
            side = t_.cross(Y).normalized()
            hw = hw0 + (hw1 - hw0) * k / (m - 1)
            if k == 0:
                hw *= 0.5
            down = Y * (-sg * sink)
            rings.append([p + side * hw, p - side * hw, p - side * hw + down, p + side * hw + down])
        loft(bm, rings)

    def local(self, u, a, b):
        """Point at u along the centreline, a across (+ edge side), b along the tangent; in the blade plane."""
        C, T, NE = self.frame(u)
        return C + NE * a + T * b


# ---------------------------------------------------------------------------
# Dagger A "Rend": near-black jagged blade, serrated, crimson veins, hooked spine spikes
# ---------------------------------------------------------------------------
BLADE_A = Blade(
    P=[V(0, 0, ZB - 0.12), V(0, 0, ZB + 1.15), V(0.08, 0, ZB + 2.2), V(0.66, 0, ZB + 3.0)],
    WE=[(0.0, 0.205), (0.12, 0.24), (0.32, 0.245), (0.55, 0.195), (0.78, 0.11), (1.0, 0.0)],
    WS=[(0.0, 0.185), (0.2, 0.175), (0.45, 0.15), (0.7, 0.10), (0.88, 0.05), (1.0, 0.0)],
    TH=[(0.0, 0.088), (0.4, 0.07), (0.75, 0.046), (1.0, 0.012)],
    teeth=(0.14, 0.50, 8, 0.07, -0.024),
    mats=(M_OBS, M_CRIM, M_OBS), NS=46)

BLADE_B = Blade(
    P=[V(0, 0, ZB - 0.12), V(0, 0, ZB + 1.05), V(0.0, 0, ZB + 2.05), V(0.74, 0, ZB + 2.72)],
    WE=[(0.0, 0.215), (0.25, 0.28), (0.5, 0.29), (0.7, 0.235), (0.87, 0.12), (1.0, 0.0)],
    WS=[(0.0, 0.195), (0.3, 0.17), (0.6, 0.14), (0.8, 0.09), (0.92, 0.045), (1.0, 0.0)],
    TH=[(0.0, 0.09), (0.4, 0.074), (0.75, 0.05), (1.0, 0.012)],
    teeth=(0.48, 0.76, 3, 0.08, -0.03), mats=(M_CRIM, M_HOT, M_OBS, M_OBS), NS=46)


def build_blade_A():
    bl = BLADE_A
    bl.build("Blade")
    bl.edge_glow(0.04, out=0.024, cover=0.3)
    bl.spine_glow(0.66)
    # hooked back-spikes on the spine (concave side), swept toward the grip
    bm = new_bm()
    for u, sc in ((0.20, 1.0), (0.34, 0.9), (0.48, 0.78), (0.62, 0.62)):
        we, ws, th, ro = bl.dims(u)
        ctrl = [bl.local(u, -ws * 0.35, 0.06 * sc), bl.local(u, -(ws + 0.09 * sc), 0.05 * sc),
                bl.local(u, -(ws + 0.19 * sc), -0.03 * sc), bl.local(u, -(ws + 0.22 * sc), -0.19 * sc)]
        claw(bm, ctrl, (0.085 * sc, th * 0.95), M_OBS, n=4, belly=0.9)
    hk = make_obj("SpineHooks", bm, smooth=True)
    hard(hk, 0.005, segs=1, angle=25)
    # crimson crack veins on both faces: two jagged lightning cracks with short spurs (not a leaf)
    cracks = [[(0.02, 0.06), (0.10, 0.27), (0.16, 0.10), (0.25, 0.36), (0.31, 0.17), (0.42, 0.42), (0.50, 0.20),
               (0.60, 0.33), (0.69, 0.13), (0.78, 0.2)],
              [(0.03, -0.12), (0.12, -0.36), (0.19, -0.14), (0.29, -0.42), (0.36, -0.19), (0.47, -0.36), (0.55, -0.1),
               (0.63, -0.24)]]
    spurs = [[(0.16, 0.10), (0.21, 0.52), (0.24, 0.66)], [(0.31, 0.17), (0.35, -0.02), (0.36, -0.19)],
             [(0.42, 0.42), (0.47, 0.64)], [(0.19, -0.14), (0.23, -0.5), (0.26, -0.62)], [(0.50, 0.20), (0.53, 0.02), (0.55, -0.1)]]
    vb = new_bm()
    for sg in (1, -1):
        for c in cracks:
            bl.ribbon(vb, c, 0.015, 0.004, sg, sub=3)
        for c in spurs:
            bl.ribbon(vb, c, 0.011, 0.003, sg, sub=2)
    make_obj("Veins", vb, kind="glow")


def build_blade_B():
    bl = BLADE_B
    bl.build("Blade")
    bl.edge_glow(0.04, out=0.026, cover=0.35)
    # ridge line glow above the plates, both faces
    rb = new_bm()
    for sg in (1, -1):
        bl.ribbon(rb, [(0.44, 0.0), (0.6, 0.0), (0.8, 0.0), (0.92, 0.0)], 0.016, 0.003, sg, sub=5)
    make_obj("RidgeGlow", rb, kind="glow")
    # bone armour shards: asymmetric, crooked, broken-edged, climbing mostly along the SPINE side in varied sizes,
    # two small ones on the edge side by the guard. f < 0: fraction of the spine half-width, f > 0: of the edge side.
    SH = [(((0.00, 0.35), (0.05, -0.2), (0.10, -0.75), (0.15, -1.4)), 0.17, 0.05, 0.0),
          (((0.08, 0.3), (0.13, -0.3), (0.17, -0.85), (0.225, -1.35)), 0.14, 0.042, 0.3),
          (((0.16, 0.2), (0.205, -0.4), (0.235, -0.8), (0.28, -1.0), (0.315, -1.4)), 0.115, 0.035, 0.6),
          (((0.25, 0.05), (0.29, -0.55), (0.34, -1.2)), 0.09, 0.028, 0.15),
          (((0.32, -0.2), (0.355, -0.75), (0.40, -1.15)), 0.06, 0.022, 0.45),
          (((0.0, 0.3), (0.035, 0.85), (0.075, 1.3)), 0.09, 0.036, 0.7),
          (((0.065, 0.4), (0.10, 1.0), (0.13, 1.22)), 0.055, 0.024, 0.2)]
    SHARD = [(1.0, 0.0), (0.35, 1.0), (-0.55, 0.85), (-1.0, 0.05), (-0.45, -0.92), (0.4, -1.0)]
    JAG = [1.0, 0.82, 1.0, 0.66, 0.8, 0.48, 0.56, 0.3, 0.34, 0.15]
    bm = new_bm()
    for ctrl_uv, ra, extra, ph in SH:
        ctrl = []
        for u, f in ctrl_uv:
            we, ws, th, ro = bl.dims(u)
            ctrl.append(bl.local(u, (we if f > 0 else ws) * f, 0.0))
        pts = catmull(ctrl, 3)
        m = len(pts)
        th0 = bl.dims(ctrl_uv[0][0])[2]
        radii = []
        for k in range(m):
            t = k / (m - 1)
            if k == m - 1:
                radii.append(0.0)
                continue
            jt = min(len(JAG) - 1.001, (t + ph * 0.1) * (len(JAG) - 1))
            j0 = int(jt)
            jag = JAG[j0] + (JAG[j0 + 1] - JAG[j0]) * (jt - j0)
            radii.append((ra * jag * (1 - 0.35 * t), (th0 + extra) * (1 - 0.55 * t) * (0.85 + 0.15 * jag)))
        tube(bm, pts, radii, mat=M_SHARD, shape=SHARD)
    pl = make_obj("BoneShards", bm, smooth=True)
    hard(pl, 0.005, segs=1, angle=25)
    # hooked tip: a barb on the spine behind the tip, plus a smaller one lower down
    bm = new_bm()
    for u, sc in ((0.78, 1.15), (0.58, 0.75)):
        we, ws, th, ro = bl.dims(u)
        ctrl = [bl.local(u, -ws * 0.3, 0.07 * sc), bl.local(u, -(ws + 0.10 * sc), 0.05 * sc),
                bl.local(u, -(ws + 0.20 * sc), -0.04 * sc), bl.local(u, -(ws + 0.20 * sc), -0.22 * sc)]
        claw(bm, ctrl, (0.09 * sc, th * 0.95), M_CRIM, n=4, belly=0.9)
    bb = make_obj("SpineBarbs", bm, smooth=True)
    hard(bb, 0.005, segs=1, angle=25)


# ---------------------------------------------------------------------------
# Shared hilt: demon-eye guard with gold + bone claws, scale grip, claw pommel
# ---------------------------------------------------------------------------
def almond(rx, rz, n=14, pinch=0.35):
    out = []
    for k in range(n):
        t = 2 * math.pi * k / n
        c, s = math.cos(t), math.sin(t)
        out.append((rx * c, rz * s * (1 - pinch * c * c)))
    return out


def dome(bm, M, outline, h, mat=0, rings=(1.0, 0.82, 0.5), heights=(0.0, 0.55, 0.88)):
    rs = [[M @ V(x * s, y * s, h * hh) for x, y in outline] for s, hh in zip(rings, heights)]
    rs.append(M @ V(0, 0, h))
    loft(bm, rs, mat=mat)


def build_guard():
    body = new_bm()
    prof = [(0.0, 0.99), (0.10, 1.0), (0.17, 1.06), (0.225, 1.15), (0.24, 1.25), (0.215, 1.34), (0.17, 1.41), (0.0, 1.43)]
    lathe(body, prof, sides=10, sy=0.56, mat=M_OBS)
    ob = make_obj("GuardBody", body, smooth=True)
    hard(ob, 0.008, segs=1, angle=28)

    gold = new_bm()
    # blade collar (blade enters here) and grip collar
    lathe(gold, [(0.15, 1.37), (0.205, 1.385), (0.222, 1.42), (0.205, 1.465), (0.165, 1.49), (0.12, 1.495)], sides=10, sy=0.55,
          mat=M_GOLD)
    lathe(gold, [(0.085, 0.965), (0.122, 0.975), (0.132, 1.01), (0.122, 1.045), (0.09, 1.06)], sides=10, mat=M_GOLD)
    for s in (1, -1):
        # short claws that grip the blade base, hooking in over the edges
        claw(gold, [V(s * 0.15, 0, 1.42), V(s * 0.25, 0, 1.50), V(s * 0.245, 0, 1.60), V(s * 0.185, 0, 1.68)], (0.05, 0.056),
             M_GOLD, n=3, belly=0.7)
        # big crossguard talons: swept out and down, needle tips pointing down-out
        claw(gold, [V(s * 0.17, 0, 1.25), V(s * 0.39, 0, 1.23), V(s * 0.55, 0, 1.12), V(s * 0.63, 0, 0.93)],
             (0.08, 0.064), M_GOLD, belly=0.8)
    g = make_obj("GuardGold", gold, smooth=True)
    hard(g, 0.006, segs=1, angle=25)

    bone = new_bm()
    for s in (1, -1):
        # bone claw plates above the crossguard, swept out and up beside the blade base
        claw(bone, [V(s * 0.17, 0, 1.31), V(s * 0.36, 0, 1.39), V(s * 0.48, 0, 1.54), V(s * 0.50, 0, 1.70)], (0.07, 0.054),
             M_BONE, n=3, belly=0.75)
        # small bone spur under the guard
        claw(bone, [V(s * 0.12, 0, 1.07), V(s * 0.21, 0, 1.01), V(s * 0.24, 0, 0.92)], (0.04, 0.036), M_BONE, n=3, belly=0.75)
    # the demon eye, both faces: bone lids with flicked corners, socket, glowing eyeball, iris, slit pupil
    eb, cb = new_bm(), new_bm()
    for sg in (1, -1):
        O = V(0, sg * 0.118, 1.235)
        Mf = Matrix.Translation(O) @ basis(V(1, 0, 0), V(0, 0, 1), V(0, sg, 0))
        F = V(0, sg, 0)
        lid_u = [O + V(-0.19, 0, 0.0), O + V(-0.10, 0, 0.068), O + V(0.0, 0, 0.088), O + V(0.10, 0, 0.068),
                 O + V(0.19, 0, 0.0)]
        lid_l = [O + V(-0.15, 0, -0.005), O + V(-0.07, 0, -0.06), O + V(0.07, 0, -0.06), O + V(0.15, 0, -0.005)]
        for pts, r in ((lid_u, (0.03, 0.034)), (lid_l, (0.022, 0.028))):
            pp = catmull(pts, 2)
            m = len(pp)
            rad = [0.0 if k in (0, m - 1) else (r[0] * (0.35 + 0.65 * math.sin(math.pi * k / (m - 1))),
                                               r[1] * (0.4 + 0.6 * math.sin(math.pi * k / (m - 1)))) for k in range(m)]
            tube(bone, [p + F * 0.012 for p in pp], rad, mat=M_BONE, up=F, shape=DIAMOND)
        # angry brow plates sweeping up and out
        for s in (1, -1):
            claw(bone, [O + V(s * 0.015, 0, 0.096) + F * 0.018, O + V(s * 0.12, 0, 0.104) + F * 0.016,
                        O + V(s * 0.215, 0, 0.122) + F * 0.004], (0.015, 0.024), M_BONE, n=3, up=F, belly=0.6)
        prism(bone, almond(0.165, 0.085, 12), O, V(1, 0, 0), V(0, 0, 1), F, -0.03, 0.006, mat=M_SOCK)
        dome(eb, Mf, almond(0.14, 0.066, 12), 0.04, mat=0)
        dome(cb, Matrix.Translation(F * 0.012) @ Mf, almond(0.058, 0.052, 12, pinch=0.1), 0.034, mat=0)
        prism(bone, [(0.0, 0.062), (0.017, 0.0), (0.0, -0.062), (-0.017, 0.0)], O, V(1, 0, 0), V(0, 0, 1), F, 0.02, 0.054,
              mat=M_SOCK)
    b = make_obj("GuardBone", bone, smooth=True)
    hard(b, 0.005, segs=1, angle=25)
    make_obj("Eye", eb, kind="glow")
    make_obj("Iris", cb, kind="core")


def build_grip():
    bm = new_bm()
    lathe(bm, [(0.0, GRIP_Z[0] - 0.04), (0.08, GRIP_Z[0] - 0.04), (0.088, 0.75), (0.08, GRIP_Z[1] + 0.02), (0.0, GRIP_Z[1] + 0.02)],
          sides=10, mat=M_SOCK)
    # dragon scales: overlapping rows, tips pointing down toward the pommel, alternate rows offset half a scale
    n = 9
    rows = 7
    for r in range(rows):
        zt = 0.995 - r * 0.068
        h = 0.092
        ph = (r % 2) * math.pi / n
        top, mid, zo, zi = [], [], [], []
        for k in range(2 * n):
            a = ph + math.pi * k / n
            d = V(math.cos(a), math.sin(a), 0)
            tip = k % 2 == 0
            top.append(d * 0.078 + V(0, 0, zt))
            mid.append(d * (0.104 if tip else 0.1) + V(0, 0, zt - 0.35 * h))
            z = zt - h if tip else zt - 0.5 * h
            zo.append(d * (0.112 if tip else 0.102) + V(0, 0, z))
            zi.append(d * 0.082 + V(0, 0, z + 0.012))
        loft(bm, [top, mid, zo, zi], mat=M_SCALE, caps=False)
    ob = make_obj("GripScales", bm, smooth=False)
    gb = new_bm()
    lathe(gb, [(0.09, 0.42), (0.128, 0.435), (0.136, 0.47), (0.126, 0.505), (0.088, 0.52)], sides=10, mat=M_GOLD)
    g = make_obj("GripCollar", gb, smooth=True)
    hard(g, 0.006, segs=1, angle=30)


def build_pommel():
    bm = new_bm()
    lathe(bm, [(0.0, 0.445), (0.10, 0.445), (0.135, 0.41), (0.13, 0.37), (0.09, 0.33), (0.0, 0.32)], sides=10, mat=M_GOLD)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        d = V(math.cos(a), math.sin(a), 0)
        tn = V(-math.sin(a), math.cos(a), 0)
        claw(bm, [d * 0.10 + V(0, 0, 0.40), d * 0.175 + V(0, 0, 0.33), d * 0.17 + V(0, 0, 0.21), d * 0.085 + V(0, 0, 0.10)],
             (0.048, 0.04), M_GOLD, n=3, up=tn, belly=0.7)
    ob = make_obj("PommelClaw", bm, smooth=True)
    hard(ob, 0.006, segs=1, angle=28)
    gb = new_bm()
    lathe(gb, [(0.0, 0.36), (0.08, 0.32), (0.085, 0.22), (0.0, -0.06)], sides=6, mat=0)
    make_obj("PommelSpike", gb, kind="glow")


def build_dagger(tag):
    CUR["d"] = tag
    if tag == "A":
        build_blade_A()
    else:
        build_blade_B()
    build_guard()
    build_grip()
    build_pommel()


build_dagger("A")
build_dagger("B")
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


def outward_check(ob):
    me = ob.data
    co = np.array([tuple(v.co) for v in me.vertices])
    cen = co.mean(axis=0)
    s = sum((Vector(p.center) - Vector(cen)).dot(p.normal) * p.area for p in me.polygons)
    return s


def place_pair():
    """A at +DX as authored; B x-mirrored (tip curves to -x) at -DX."""
    for o in PARTS:
        if o["dagger"] == "B":
            before = outward_check(o)
            o.scale = (-1, 1, 1)
            select_only([o])
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            if outward_check(o) * before < 0:
                o.data.flip_normals()
                log("flipped normals on", o.name)
            o.data.transform(Matrix.Translation(V(-DX, 0, 0)))
        else:
            o.data.transform(Matrix.Translation(V(DX, 0, 0)))
        o.data.update()
    BLADE_A.edge_pts = [(p[0] + DX, p[1], p[2]) for p in BLADE_A.edge_pts]
    BLADE_B.edge_pts = [(-p[0] - DX, p[1], p[2]) for p in BLADE_B.edge_pts]


place_pair()


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
log("TRIS pair", sum(TRIS.values()), sorted(TRIS.items(), key=lambda kv: -kv[1]))


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


def setup_comp(bloom=1.35, size=0.8, fog=0.75, fog_size=0.9):
    """Compositor Glare on every render (Roblox Neon blooms in game). The glare is driven by the Emission pass only, so
    only the Neon radiates a crimson haze (a tight Bloom plus a wide Fog Glow) and the light backdrop never blooms."""
    bpy.context.view_layer.use_pass_emit = True
    tree = bpy.data.node_groups.get("ReviewComp") or bpy.data.node_groups.new("ReviewComp", "CompositorNodeTree")
    tree.nodes.clear()
    if not tree.interface.items_tree:
        tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = tree.nodes.new("CompositorNodeRLayers")
    out = tree.nodes.new("NodeGroupOutput")
    src = rl.outputs["Image"]

    def add(a, b):
        try:
            m = tree.nodes.new("CompositorNodeMixRGB")
            m.blend_type = "ADD"
            m.inputs[0].default_value = 1.0
            tree.links.new(a, m.inputs[1])
            tree.links.new(b, m.inputs[2])
            return m.outputs[0]
        except Exception:
            tree.nodes.remove(tree.nodes[-1]) if False else None
            m = tree.nodes.new("ShaderNodeMix")
            m.data_type = "RGBA"
            m.blend_type = "ADD"
            m.inputs["Factor"].default_value = 1.0
            tree.links.new(a, m.inputs[6])
            tree.links.new(b, m.inputs[7])
            return m.outputs[2]

    for typ, strength, sz in (("Bloom", bloom, size), ("Fog Glow", fog, fog_size)):
        if strength <= 0:
            continue
        g = tree.nodes.new("CompositorNodeGlare")
        g.inputs["Type"].default_value = typ
        g.inputs["Quality"].default_value = "High"
        g.inputs["Threshold"].default_value = 0.0
        g.inputs["Strength"].default_value = strength
        g.inputs["Size"].default_value = sz
        tree.links.new(rl.outputs["Emission"], g.inputs["Image"])
        src = add(src, g.outputs["Glare"])
    tree.links.new(src, out.inputs[0])
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
    scene.view_settings.look = "AgX - Punchy"          # keeps the Neon a deep red and the darks rich
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


def closeup(path, target, size, camdir=(0.25, -1, 0.15), res=800, samples=16):
    cam = STAGE["cam"]
    cam.data.ortho_scale = size
    cam.location = Vector(target) + Vector(camdir).normalized() * 12
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.resolution_x = scene.render.resolution_y = res
    scene.cycles.samples = samples
    render(path)


if MODE == "quick":
    OUT.mkdir(parents=True, exist_ok=True)
    setup_comp()
    pair = list(PARTS)
    for nm, ang, vec in (("q_catalog", -12, (1.6, -15, 6.2)), ("q_front", 0, (0, -15, 1.2)), ("q_side", 0, (15, 0, 1.2))):
        r = catalog_stage(pair, ang, vec, res=800, samples=16)
        render(OUT / f"{nm}.png")
        r()
    r = catalog_stage(pair, 0, (0, -15, 1.2), res=800, samples=16)
    zoff = -min(p.z for p in world_bounds(pair))
    closeup(OUT / "q_hiltA.png", (DX, 0, 1.0 + zoff), 1.6)
    closeup(OUT / "q_bladeA.png", (DX + 0.25, 0, 3.0 + zoff), 2.6)
    closeup(OUT / "q_bladeB.png", (-DX - 0.2, 0, 2.4 + zoff), 2.2)
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
for bl in (BLADE_A, BLADE_B):
    bl.edge_pts = [(p[0], p[1], p[2] - Z0) for p in bl.edge_pts]
SIDES = {"A": "L", "B": "R"}
BODY, GLOWS, CORES = {}, {}, {}
GROUPS = {(d, k): [o for o in PARTS if o["dagger"] == d and o["kind"] == k] for d in SIDES for k in ("tex", "glow", "core")}
for d, h in SIDES.items():
    BODY[d] = join(GROUPS[(d, "tex")], f"{NAME}_{h}")
    GLOWS[d] = join(GROUPS[(d, "glow")], f"{NAME}_{h}_Glow")
    CORES[d] = join(GROUPS[(d, "core")], f"{NAME}_{h}_GlowCore")
PARTS = [BODY["A"], GLOWS["A"], CORES["A"], BODY["B"], GLOWS["B"], CORES["B"]]
for o in PARTS:
    while o.data.uv_layers:
        o.data.uv_layers.remove(o.data.uv_layers[0])
    for a in [a.name for a in o.data.color_attributes]:
        o.data.color_attributes.remove(o.data.color_attributes[a])
for d in SIDES:
    for o, m in ((GLOWS[d], GLOW_MAT), (CORES[d], CORE_MAT)):
        o.data.materials.clear()
        o.data.materials.append(m)
        for p in o.data.polygons:
            p.material_index = 0

bodies = [BODY["A"], BODY["B"]]
for b in bodies:
    b.data.uv_layers.new(name="UVMap")
select_only(bodies, bodies[0])
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(52), island_margin=0.003, area_weight=0.0, correct_aspect=True,
                         scale_to_bounds=False)
bpy.ops.uv.pack_islands(rotate=True, margin=0.003)
bpy.ops.object.mode_set(mode="OBJECT")
for d in SIDES:
    for o in (GLOWS[d], CORES[d]):
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


gP, gA, gC = [], [], []
for o in list(GLOWS.values()) + list(CORES.values()):
    me = o.data
    col = CORE if "_GlowCore" in o.name else GLOW
    c = np.empty(len(me.polygons) * 3, np.float32)
    me.polygons.foreach_get("center", c)
    a = np.empty(len(me.polygons), np.float32)
    me.polygons.foreach_get("area", a)
    gP.append(c.reshape(-1, 3))
    gA.append(a)
    gC.append(np.tile(np.array(rgba(col)[:3], np.float32), (len(a), 1)))
gP, gA, gC = np.concatenate(gP), np.concatenate(gA), np.concatenate(gC)
ZTOP = max(p.z for p in world_bounds(bodies))

for d, bl in (("A", BLADE_A), ("B", BLADE_B)):
    body = BODY[d]
    ax = DX if d == "A" else -DX
    P, NRM, MI = corner_arrays(body.data)
    NL = len(P)
    paint = np.ones((NL, 3), np.float32)
    edge = np.array(bl.edge_pts, np.float32)
    R_AX = np.sqrt((P[:, 0] - ax) ** 2 + P[:, 1] ** 2)
    zb = ZB - Z0
    hf = np.clip((P[:, 2] - zb) / (ZTOP - zb), 0, 1)
    dE = np.full(NL, 9.0, np.float32)
    blade_sel = np.isin(MI, [M_OBS, M_CRIM, M_HOT]) & (P[:, 2] > zb - 0.05)
    if blade_sel.any():
        idx = np.where(blade_sel)[0]
        for i0 in range(0, len(idx), 4000):
            ii = idx[i0:i0 + 4000]
            dE[ii] = np.min(np.linalg.norm(P[ii][:, None, :] - edge[None, :, :], axis=2), axis=1)
    kE = 1 - np_smooth(0.01, 0.06, dE)
    sel = MI == M_OBS
    if d == "A":
        # near-black body, crimson cast rising toward the edges and the tip
        s = sel & blade_sel
        paint[s] *= (0.8 + 0.25 * hf[s])[:, None]
        paint[s] *= np.stack([1 + 0.7 * kE[s] + 0.3 * hf[s], 1 + 0.05 * kE[s], 1 + 0.1 * kE[s]], axis=1)
        s2 = (MI == M_CRIM) & blade_sel
        paint[s2] *= 0.45
    sel = MI == M_CRIM
    s = sel & blade_sel
    paint[s] *= (0.66 + 0.3 * hf[s] + 0.15 * kE[s])[:, None]
    sel = MI == M_HOT
    paint[sel] *= (0.85 + 0.3 * kE[sel])[:, None]
    sel = MI == M_SHARD
    paint[sel] *= (0.5 + 0.55 * np_smooth(0.06, 0.12, np.abs(P[sel][:, 1])))[:, None]
    sel = MI == M_SCALE
    paint[sel] *= (0.6 + 0.75 * np_smooth(0.086, 0.114, R_AX[sel]))[:, None]
    sel = (MI == M_OBS) & ~blade_sel
    paint[sel] *= (0.85 + 0.5 * np_smooth(0.1, 0.24, np.abs(P[sel][:, 0] - ax)))[:, None]

    bleed = np.zeros((NL, 3), np.float32)
    for i0 in range(0, NL, 1500):
        i1 = min(NL, i0 + 1500)
        Ld = gP[None, :, :] - P[i0:i1, None, :]
        dd = np.linalg.norm(Ld, axis=2) + 1e-6
        wrap = np.clip(np.einsum("cgk,ck->cg", Ld, NRM[i0:i1]) / dd * 0.75 + 0.25, 0, 1)
        w = gA[None, :] * wrap * np.exp(-dd / BLEED_FALL) / (dd * dd + 0.03 ** 2)
        bleed[i0:i1] = w @ gC
    bleed = (1 - np.exp(-BLEED_K * bleed)) * BLEED_STRENGTH
    bleed[blade_sel & (MI == M_OBS)] *= 0.15         # black blade faces stay black; glow sits in lines
    bleed[blade_sel & (MI == M_CRIM)] *= 0.35
    bleed[MI == M_SHARD] *= 0.5
    for nm, arr in (("Paint", paint), ("Bleed", bleed)):
        at = body.data.color_attributes.new(nm, "FLOAT_COLOR", "CORNER")
        at.data.foreach_set("color", np.concatenate([arr, np.ones((NL, 1), np.float32)], axis=1).ravel())
log("masks done")

KEY_DIR = V(-0.45, -0.6, 0.75).normalized()
RIM_DIR = V(0.7, 0.6, 0.25).normalized()


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
    k = dot_light(KEY_DIR)
    light = remap(k, 0.0, 1.0, 0.56, 1.2)
    tint = mix((0.9, 0.9, 1.04, 1), (1.08, 1.0, 0.9, 1), k)
    ao = N("ShaderNodeAmbientOcclusion")
    ao.samples = 16
    ao.inputs["Distance"].default_value = 0.16
    aof = remap(ao.outputs["AO"], 0.2, 1.0, 0.45, 1.0)
    cav = N("ShaderNodeAmbientOcclusion")
    cav.samples = 16
    cav.inputs["Distance"].default_value = 0.03
    cavf = remap(cav.outputs["AO"], 0.35, 1.0, 0.55, 1.0)
    sep = N("ShaderNodeSeparateXYZ")
    L(pos, sep.inputs["Vector"])
    height = remap(sep.outputs["Z"], 0.0, ZTOP, 0.9, 1.05)
    shade = math_("MULTIPLY", math_("MULTIPLY", light, aof), math_("MULTIPLY", cavf, height))
    lit = mix(mix(albedo, tint, 1.0, "MULTIPLY"), grey(shade), 1.0, "MULTIPLY")
    rim = remap(dot_light(RIM_DIR), 0.25, 1.0, 0.0, 0.12)
    lit = mix(lit, (1.0, 0.22, 0.2, 1), rim, "ADD")
    bev = N("ShaderNodeBevel")
    bev.samples = 8
    bev.inputs["Radius"].default_value = 0.01
    ed = N("ShaderNodeVectorMath")
    ed.operation = "DOT_PRODUCT"
    L(bev.outputs["Normal"], ed.inputs[0])
    L(tn, ed.inputs[1])
    e = remap(ed.outputs["Value"], 0.99, 0.84, 0.0, 1.0)
    convex = remap(cav.outputs["AO"], 0.86, 0.97, 0.0, 1.0)
    efac = math_("MULTIPLY", math_("MULTIPLY", e, convex), remap(k, 0.0, 1.0, 0.5, 0.9))
    ecol = mix(albedo, rgba(edge_c), 0.65)
    lit = mix(lit, mix(ecol, grey(val(1.25)), 1.0, "MULTIPLY"), efac)
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
select_only(bodies, bodies[0])
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
bs.inputs["Roughness"].default_value = 0.6
bs.inputs["Specular IOR Level"].default_value = 0.3
tx = final_mat.node_tree.nodes.new("ShaderNodeTexImage")
tx.image = tex_img
final_mat.node_tree.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
for body in bodies:
    body.data.materials.clear()
    body.data.materials.append(final_mat)
    for p in body.data.polygons:
        p.material_index = 0
    for nm in ("Paint", "Bleed"):
        body.data.color_attributes.remove(body.data.color_attributes[nm])
for m in MATS:
    bpy.data.materials.remove(m)
log("texture done")

L_objs = [BODY["A"], GLOWS["A"], CORES["A"]]
R_objs = [BODY["B"], GLOWS["B"], CORES["B"]]
FINAL = L_objs + R_objs

select_only(FINAL, BODY["A"])
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
GRIP_LOCAL_Z = (GRIP_Z[0] + GRIP_Z[1]) / 2 - Z0
install = {
    "name": NAME, "blender_version": bpy.app.version_string, "status": "Blender-verified, Studio untested",
    "units": "1 Blender unit = 1 stud, authored at hero size; set the play size in Studio by uniform scale",
    "axes": "Studio = (-x, z, y) of Blender; FBX exported with axis_forward=-Z, axis_up=Y",
    "texture": f"BaseColor.png {BAKE_SIZE}x{BAKE_SIZE}, baked painted lighting, one atlas shared by both daggers (each dagger "
               "has its own UV islands); use MeshPart.TextureID (not SurfaceAppearance)",
    "parts": {},
    "daggers": {},
    "notes": ["Two different daggers, one per hand: left = 'Rend' (near-black serrated blade, crimson veins), right = 'Fang' "
              "(crimson blade, bone plates, hooked tip). Each has its own textured MeshPart plus a Neon glow and a Neon core "
              "MeshPart; weld the three parts of a dagger together and to that hand.",
              "Every MeshPart imports centred on its own bounding box: place each at its center_studio relative to the shared "
              "model origin (Blender origin, on the floor midway between the two daggers).",
              "grip_point = middle of the scale grip on that dagger's axis (hand attachment / spin pivot). blade_axis = the "
              "grip-to-blade direction in the delivered pose. The cutting edges face each other (inward); the tips curve outward.",
              "The left-hand dagger sits at Studio -X (character's left when facing -Z), the right-hand dagger at Studio +X."],
}
for side, objs, sx in (("left_hand", L_objs, DX), ("right_hand", R_objs, -DX)):
    grip = V(sx, 0, GRIP_LOCAL_Z)
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
NOTES = {
    "L_Glow": "crimson Neon: serrated cutting edge, crack veins on both faces, spine false edge, demon eye, pommel spike",
    "R_Glow": "crimson Neon: cutting edge, ridge line on both faces, demon eye, pommel spike",
    "L_GlowCore": "hot core: cutting-edge rim line, eye iris",
    "R_GlowCore": "hot core: cutting-edge rim line, eye iris",
}
for o in FINAL:
    st = STATS[o.name]
    mn, mx = np.array(st["bounds_min"]), np.array(st["bounds_max"])
    part = {"kind": "textured" if o in bodies else "glow", "center_studio": studio((mn + mx) / 2),
            "size_studio": studio_size(mx - mn), "triangles": st["triangles"]}
    key = o.name.replace(f"{NAME}_", "")
    if "_GlowCore" in o.name:
        part.update(material="Neon", color_rgb=list(CORE), note=NOTES[key])
    elif "_Glow" in o.name:
        part.update(material="Neon", color_rgb=list(GLOW), note=NOTES[key])
    else:
        part.update(material="SmoothPlastic (or Plastic), Color white", texture_id="BaseColor.png")
    install["parts"][o.name] = part
install["vfx_notes"] = [
    "Aura haze (idle, always on while equipped): one ParticleEmitter per dagger on an Attachment at mid-blade, Shape Box sized "
    "to the blade (about 0.5 x 2 x 0.2 studs), Texture a soft round glow, Color (255,26,38) -> (120,8,20), LightEmission 1, "
    "LightInfluence 0, Size 0.9 -> 1.6, Transparency 0.75 -> 1, Lifetime 0.6-0.9, Rate 14, Speed 0.2-0.5, "
    "Acceleration (0,0.8,0), RotSpeed -30..30. Plus a PointLight on the guard eye: Color (255,40,40), Brightness 1.5, Range 7.",
    "Ember motes (idle, optional): ParticleEmitter at the blade, Color (255,112,78) -> (255,26,38), Size 0.12 -> 0, "
    "LightEmission 1, Lifetime 0.5-0.8, Rate 6, Speed 0.6, SpreadAngle 30.",
    "Chain dash (ability, up to 5 hits): the twin daggers zip from enemy to enemy. For each hop spawn a crimson afterimage "
    "chain: a Beam between the dagger's current Attachment and the next enemy's Attachment, Color (255,112,78) -> "
    "(255,26,38) -> (70,4,12), LightEmission 1, LightInfluence 0, Width0 1.4 / Width1 0.3 studs, Transparency 0 -> 1 over "
    "0.3 s (tween), FaceCamera true, Segments 1.",
    "Afterimages: at every hop leave 3 ghost copies of the dagger's Neon glow MeshPart (or all three parts) along the beam, "
    "Material Neon, Color (255,26,38), Transparency tween 0.3 -> 1 over 0.25 s, staggered 0.03 s apart; up to 5 hops leaves a "
    "crimson zig-zag of afterimages between the enemies.",
    "Blade Trail per dagger: Attachment0 at the guard collar, Attachment1 at the blade tip; Color (255,26,38) -> (70,4,12), "
    "Lifetime 0.2, MinLength 0.05, WidthScale 1 -> 0, Transparency 0.15 -> 1, LightEmission 1, FaceCamera true.",
    "Hit burst on each chained enemy: ParticleEmitter Burst 14, Color (255,112,78) -> (255,26,38), Size 0.9 -> 0, "
    "Lifetime 0.25-0.4, Speed 9-15, SpreadAngle 180, LightEmission 1, Drag 6; plus a crimson slash decal/Beam X across the "
    "enemy for 0.15 s and 4 dark smoke puffs Color (40,8,14), Size 1.2 -> 2.2, Transparency 0.4 -> 1, Lifetime 0.5, Speed 2.",
]
(ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=1))
log("stats", {k: v["triangles"] for k, v in STATS.items()}, "total", sum(v["triangles"] for v in STATS.values()))

# ---------------------------------------------------------------------------
# Renders: Preview, Front, Back, Side, Scale, Hero (brief's set only)
# ---------------------------------------------------------------------------
setup_comp()


def shoot_catalog(name, angle, camvec, samples=32, res=1000):
    r = catalog_stage(FINAL, angle, camvec, samples=samples, res=res)
    render(ROOT / name)
    r()


shoot_catalog("Preview.png", -12, (1.6, -15, 6.2), samples=48)
shoot_catalog("Front.png", 0, (0, -15, 1.2))
shoot_catalog("Back.png", 0, (0, 15, 1.2))
shoot_catalog("Side.png", 0, (15, 0, 1.2))

if os.environ.get("WIP_CLOSEUPS", "1") == "1":
    (ROOT / "wip").mkdir(exist_ok=True)
    r = catalog_stage(FINAL, 0, (0, -15, 1.2), res=900, samples=32)
    closeup(ROOT / "wip" / "f_hiltA.png", (DX, 0, 1.05), 1.6, samples=32)
    closeup(ROOT / "wip" / "f_bladeA.png", (DX + 0.25, 0, 3.0), 2.6, samples=32)
    closeup(ROOT / "wip" / "f_bladeB.png", (-DX - 0.2, 0, 2.4), 2.2, samples=32)
    r()

fig_bm = new_bm()
FX = 3.7
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
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.02, 0.011, 0.014, 1)
    cd = bpy.data.cameras.new("Hero camera")
    cam = bpy.data.objects.new("Hero camera", cd)
    REVIEW.objects.link(cam)
    cd.lens = lens
    cam.location = cam_loc
    cam.rotation_euler = (target - cam_loc).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    for nm, loc, col, en, sz in (("Hero key", V(-3, -5, 6), (1.0, 0.92, 0.86), 750, 3),
                                  ("Hero rim crimson", V(3, 5, 4), (1.0, 0.16, 0.14), 1500, 3),
                                  ("Hero rim warm", V(-4, 4, 4), (1.0, 0.72, 0.6), 600, 3),
                                  ("Hero fill crimson", V(2, -4, 0.5), (1.0, 0.25, 0.2), 160, 3)):
        ld = bpy.data.lights.new(nm, "AREA")
        ld.color = col
        ld.energy = en
        ld.size = sz
        lo = bpy.data.objects.new(nm, ld)
        REVIEW.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = (V(0, 0, 2.2) - loc).to_track_quat("-Z", "Y").to_euler()
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Punchy"
    except TypeError:
        pass
    setup_comp(1.5, 0.85, fog=0.8)
    render(ROOT / name)
    scene.view_settings.look = "None"
    setup_comp()


hero("Hero.png", V(1.5, -7.6, 3.0), V(0.0, 0, 2.2), lens=50)

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
compose([(ROOT / "Preview.png", "Shadow Daggers (Godly, round 2)"), (ASSETS / "32-excalibur" / "Preview.png", "Excalibur"),
         (ASSETS / "31-mjolnir" / "Preview.png", "Mjolnir"), (ASSETS / "34-medusas-head" / "Preview.png", "Medusa's Head")],
        4, 700, ROOT / "Compare_Catalog.png", title="Catalogue framing: Godly Shadow Daggers beside the current top-tier weapons")
compose([(ROOT / "Preview.png", "Preview (catalogue 3/4)"), (ROOT / "Front.png", "Front"), (ROOT / "Back.png", "Back"),
         (ROOT / "Side.png", "Side"), (ROOT / "Hero.png", "Hero (dramatic lighting)"),
         (ROOT / "Scale.png", "Scale: 5-stud R15 block figure"), (ROOT / "BaseColor.png", "BaseColor.png (1024, baked)")],
        4, 560, ROOT / "Sheet.png", title="Shadow Daggers - Godly, round 2 (Blender renders, Studio untested)")

# ---------------------------------------------------------------------------
# Validation (re-import both exports into a fresh file)
# ---------------------------------------------------------------------------
report = {
    "name": NAME, "blender_version": bpy.app.version_string,
    "meshes": {k: v for k, v in STATS.items()},
    "total_triangles": sum(v["triangles"] for v in STATS.values()),
    "triangles_per_dagger": {"left_hand": install["daggers"]["left_hand"]["triangles"],
                             "right_hand": install["daggers"]["right_hand"]["triangles"]},
    "total_vertices": sum(v["vertices"] for v in STATS.values()),
    "mesh_count": len(FINAL),
    "materials": {o.name: o.data.materials[0].name for o in FINAL},
    "texture": {"file": "BaseColor.png", "size": list(tex_img.size), "packed_in_blend": bool(tex_img.packed_file),
                "uv_layers": {b.name: [l.name for l in b.data.uv_layers] for b in bodies}},
    "pair_length_studs": round(float(allmx[2] - allmn[2]), 4),
    "bounds_blender_min": [round(float(x), 4) for x in allmn], "bounds_blender_max": [round(float(x), 4) for x in allmx],
    "bounds_studio_size": studio_size(allmx - allmn),
}
uv_rng = []
for b in bodies:
    uvd = np.empty(len(b.data.loops) * 2, np.float32)
    b.data.uv_layers["UVMap"].data.foreach_get("uv", uvd)
    uv_rng += [float(uvd.min()), float(uvd.max())]
report["texture"]["uv_range"] = [round(min(uv_rng), 4), round(max(uv_rng), 4)]
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
    "max_mesh_triangles": max(v["triangles"] for v in STATS.values()),
    "every_mesh_under_20k": all(v["triangles"] < 20000 for v in STATS.values()),
    "glb_triangles_match": report["glb_reimport"]["triangles"] == report["total_triangles"],
    "fbx_triangles_match": report["fbx_reimport"]["triangles"] == report["total_triangles"],
}
report["notes"] = [
    "Non-manifold edge counts are expected: each textured mesh is many closed parts that overlap by design "
    "(claws rooted in the guard, plates on the blade, scale rows on the grip, eye lids on the guard).",
    "The two daggers are different meshes (not mirrors); both use the same 1024 atlas with separate UV islands.",
    "Studio import, Neon look and in-game scale are untested (no Studio access in this task).",
]
(ROOT / "validation.json").write_text(json.dumps(report, indent=1))
log("VALIDATION", json.dumps(report["checks"]), "tris", report["total_triangles"])
log("DONE")
