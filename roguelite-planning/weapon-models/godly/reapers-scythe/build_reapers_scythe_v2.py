"""Reaper's Scythe: Godly weapon style sample (RARITY_GODLY_ARMOR.md sections 9 and 13).

Run in background Blender 5.2 only (never the user's open scene):
  blender -b --factory-startup --threads 4 --python build_reapers_scythe.py

Environment switches (all optional):
  MODE=quick     build the model and render review shots only (no bake, no exports)
  MODE=full      (default) build, bake the painted texture, export, validate, render everything
  CONCEPT=A|B    A = hooded reaper skull (chosen), B = horned crowned skull (the rejected alternative)
  OUT=<dir>      where renders go (default: this folder)
  SHOTS=a,b      quick mode: which review shots to render (catalog,head,blade,front,side,back)

No reference image exists: designed from the section 9 text ("a huge spinning sweep; enemies it
kills come back as ghost helpers") with the Godly accent (crimson and obsidian), inside the art
direction in art-references/ART_DIRECTION_USER_2026-09-17.txt (chunky stylized low-poly,
bevelled, painterly baked texture, gems/runes/gold allowed).

Axes: Blender +z up, the blade sweeps toward -x, its flat faces look along +/-y, the skull faces -y.
1 Blender unit = 1 Roblox stud. Studio axes are (-x, z, y) of Blender.
"""
import bpy, bmesh, math, json, os, sys, time
import numpy as np
from mathutils import Vector, Matrix
from pathlib import Path

T0 = time.time()
ROOT = Path(__file__).resolve().parent
NAME = "ReapersScythe"
MODE = os.environ.get("MODE", "full")
CONCEPT = os.environ.get("CONCEPT", "A")
OUT = Path(os.environ.get("OUT", str(ROOT)))
OUT.mkdir(parents=True, exist_ok=True)
SHOTS = [s for s in os.environ.get("SHOTS", "catalog,head").split(",") if s]
BAKE_SIZE = 1024
TARGET_HEIGHT = 5.0          # hero size in studs; play size is set later in Studio
BLEED_K, BLEED_STRENGTH = 0.18, 0.85   # baked glow light on nearby surfaces


def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)


def V(*a):
    return Vector(a)


# ---------------------------------------------------------------------------
# Palette. Slot index = material index on every textured mesh.
# flat: quick-preview colour. ramp: painterly noise ramp (sRGB). edge: highlight tint on bevels.
# ---------------------------------------------------------------------------
PAL = [
    ("Obsidian", (28, 24, 38), [(0.28, (14, 12, 22)), (0.5, (28, 23, 40)), (0.76, (52, 43, 72))], (150, 134, 196)),
    ("Steel", (34, 28, 48), [(0.28, (16, 13, 25)), (0.52, (32, 26, 46)), (0.8, (60, 50, 84))], (190, 176, 232)),
    ("Crimson", (168, 22, 46), [(0.3, (104, 10, 30)), (0.52, (160, 20, 44)), (0.78, (212, 54, 72))], (255, 150, 160)),
    ("Gold", (238, 172, 34), [(0.3, (176, 100, 14)), (0.52, (238, 170, 30)), (0.78, (255, 226, 92))], (255, 240, 160)),
    ("Bone", (238, 224, 190), [(0.3, (200, 174, 128)), (0.54, (238, 220, 184)), (0.8, (255, 248, 228))], (255, 255, 244)),
    ("Socket", (22, 10, 20), [(0.4, (12, 5, 12)), (0.75, (34, 14, 26))], (70, 34, 44)),
    ("Cloth", (46, 36, 62), [(0.28, (26, 20, 38)), (0.52, (44, 35, 60)), (0.8, (74, 60, 100))], (136, 118, 170)),
    ("Lining", (120, 14, 34), [(0.3, (70, 6, 20)), (0.55, (112, 14, 32)), (0.8, (150, 28, 46))], (210, 90, 100)),
    ("Leather", (128, 22, 40), [(0.3, (78, 10, 26)), (0.52, (122, 20, 38)), (0.78, (170, 42, 58))], (236, 120, 130)),
]
M_OBS, M_STEEL, M_CRIM, M_GOLD, M_BONE, M_SOCK, M_CLOTH, M_LINING, M_LEATHER = range(len(PAL))
GLOW = (255, 22, 52)        # Roblox Neon, crimson (Godly accent)
CORE = (255, 150, 128)      # Roblox Neon, pale-hot core of eyes, edges and flames


def lin(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgba(c, a=1.0):
    return (lin(c[0]), lin(c[1]), lin(c[2]), a)


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------------------
# bmesh primitives
# ---------------------------------------------------------------------------
def loft(bm, rings, closed=True, caps=True, mat=0, recalc=True):
    """Connect rings (lists of points, or a single point = pole) with quads / fans."""
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


def lathe(bm, prof, sides=8, M=None, mat=0, phase=None, sy=1.0):
    """Surface of revolution about local +z; prof = [(radius, z)] bottom to top."""
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
    """2D polygon (u, v) in the plane (au, av) through origin, extruded along an from d0 to d1."""
    r0 = [origin + au * u + av * v + an * d0 for u, v in poly]
    r1 = [origin + au * u + av * v + an * d1 for u, v in poly]
    return loft(bm, [r0, r1], mat=mat)


def basis(x, y, z):
    """Matrix whose columns are the given axes (local -> world rotation)."""
    return Matrix((x, y, z)).transposed().to_4x4()


def flame(bm, base, up, height, width, lean=None, wiggle=0.35, sides=5, flat=0.6, mat=0, phase=0.0, side=None):
    """A faceted soul-fire tongue: wide belly, S-curved, pointed tip."""
    lean = lean or V(0, 0, 0)
    up = up.normalized()
    side = side or (up.cross(V(0, 1, 0)) if abs(up.y) < 0.9 else up.cross(V(1, 0, 0)))
    side.normalize()
    prof = [0.55, 0.95, 1.0, 0.82, 0.58, 0.32, 0.12, 0.0]
    n = len(prof) - 1
    pts = []
    for k in range(n + 1):
        t = k / n
        pts.append(base + up * height * t + lean * (t ** 1.7) * height
                   + side * math.sin(t * math.pi * 1.6 + phase) * wiggle * width * t)
    return tube(bm, pts, [width * p for p in prof], sides=sides, flat=flat, mat=mat, phase=phase * 0.3)


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
    bs.inputs["Roughness"].default_value = 0.55 if name not in ("Gold",) else 0.35
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


GLOW_MAT = emit_mat(f"{NAME}_Glow", GLOW, 0.95)
CORE_MAT = emit_mat(f"{NAME}_GlowCore", CORE, 1.3)

BM = {}          # kind -> list of (bm, name, smooth, bevel spec)
PARTS = []       # built objects


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


def add_bool(ob, cutter, op="DIFFERENCE", self_int=False):
    m = ob.modifiers.new(f"Bool_{cutter.name}", "BOOLEAN")
    m.operation = op
    m.solver = "EXACT"
    m.object = cutter
    m.material_mode = "INDEX"
    m.use_self = self_int
    m.use_hole_tolerant = True
    return m


def hard(ob, width=0.012, segs=2, angle=30.0):
    """Hard-surface finish: rounded multi-segment bevel + weighted normals, smooth shaded."""
    for p in ob.data.polygons:
        p.use_smooth = True
    add_bevel(ob, width, segs=segs, angle=angle)
    add_wn(ob)
    return ob


def soft(ob, width=0.01, angle=32.0):
    """Organic faceted finish: flat shading with a single soft chamfer."""
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
# Layout (studs). Shaft axis is x = y = 0.
# ---------------------------------------------------------------------------
S = V(0.0, 0.09, 4.54)                # skull centre, sunk back inside the cowl
SKULL_SCALE = 1.22
COWL_C = V(0.0, -0.02, 4.54)          # cowl axis centre
COWL_OUT = [(0.76, -0.60), (0.69, -0.44), (0.615, -0.24), (0.565, -0.02), (0.53, 0.18), (0.465, 0.36), (0.36, 0.51),
            (0.22, 0.63), (0.09, 0.71), (0.0, 0.75)]
COWL_IN = [(0.0, 0.68), (0.08, 0.65), (0.2, 0.57), (0.32, 0.46), (0.42, 0.32), (0.48, 0.15), (0.505, -0.03),
           (0.55, -0.24), (0.625, -0.43), (0.70, -0.58)]
SHAFT_Z0, SHAFT_Z1 = 0.62, 3.66


def shaft_r(z):
    t = (z - SHAFT_Z0) / (SHAFT_Z1 - SHAFT_Z0)
    return 0.148 + 0.014 * t


def head_radius(zr):
    """Outer radius of the head mass (cowl) at a height relative to the cowl centre."""
    return float(np.interp(zr, [q[1] for q in COWL_OUT], [q[0] for q in COWL_OUT]))


def bez(P, t):
    s_ = 1 - t
    return P[0] * s_ ** 3 + P[1] * 3 * s_ * s_ * t + P[2] * 3 * s_ * t * t + P[3] * t ** 3


class BladeShape:
    ROWS = [(0.0, 0.074, M_BONE), (0.04, 0.118, M_BONE), (0.20, 0.122, M_GOLD), (0.235, 0.080, M_STEEL),
            (0.60, 0.066, M_STEEL), (0.83, 0.054, None)]
    BODY = [(0.235, 0.080), (0.60, 0.066), (0.83, 0.054)]

    def __init__(self, P, w0, root_narrow=0.42, root_len=0.10, belly=0.22, thick=1.0, taper=0.5, tongues=7, tongue_depth=0.12):
        self.P, self.w0, self.rn, self.rl, self.belly = P, w0, root_narrow, root_len, belly
        self.thick, self.taper, self.tongues, self.td = thick, taper, tongues, tongue_depth
        mid = bez(P, 0.5)
        curv = bez(P, 0.52) + bez(P, 0.48) - mid * 2
        self.sign = 1.0
        if self._nin_raw(0.5).dot(curv) < 0:
            self.sign = -1.0
        us = np.linspace(0, 1, 801)
        sp = np.array([tuple(bez(P, u)) for u in us])
        self._us = us
        self._sl = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(sp, axis=0), axis=1))])
        self.length = float(self._sl[-1])

    def spine(self, u):
        return bez(self.P, u)

    def stan(self, u):
        e = 1e-3
        return (self.spine(min(u + e, 1.0)) - self.spine(max(u - e, 0.0))).normalized()

    def _nin_raw(self, u):
        t = self.stan(u)
        return V(-t.z, 0, t.x)

    def nin(self, u):
        return self._nin_raw(u) * self.sign

    def width(self, u):
        root = self.rn + (1 - self.rn) * smoothstep(0.0, self.rl, u) if self.rl > 0 else 1.0
        return self.w0 * (1 - u) ** 0.78 * (1 + self.belly * math.sin(math.pi * u)) * root

    def tt(self, u):
        return self.thick * (1 - self.taper * u)

    def row_t(self, v):
        pts = self.BODY
        if v <= pts[0][0]:
            return pts[0][1]
        for (a, ta), (b, tb) in zip(pts, pts[1:]):
            if v <= b:
                return lerp(ta, tb, (v - a) / (b - a))
        return pts[-1][1]

    def point(self, u, v, side=0.0, t=None):
        p = self.spine(u) + self.nin(u) * self.width(u) * v
        return p + V(0, side * (t if t is not None else self.row_t(v)) * self.tt(u), 0)

    def u_at(self, s):
        return float(np.interp(s, self._sl, self._us))

    def tongue(self, u):
        """Flame tongues licking up from the edge: sharp tip, long trailing tail toward the tip."""
        if self.tongues <= 0:
            return 0.0
        ph = (u * self.tongues + 0.35) % 1.0
        f = (ph / 0.3) ** 1.3 if ph < 0.3 else ((1 - ph) / 0.7) ** 2.2
        amp = 0.6 + 0.4 * math.sin(u * 23.7 + 1.3) ** 2
        return self.td * amp * f * smoothstep(0.04, 0.12, u) * (1 - smoothstep(0.8, 0.96, u))

    def build(self, name, nu=42, u_end=0.975, edge_pts=None, nu_glow=None):
        bm, gl = new_bm(), new_bm()
        R = len(self.ROWS)
        us = [u_end * i / nu for i in range(nu + 1)]
        top, bot = [], []
        for u in us:
            tt = self.tt(u)
            base, n, w = self.spine(u), self.nin(u), self.width(u)
            top.append([bm.verts.new(base + n * w * v + V(0, t * tt, 0)) for v, t, _ in self.ROWS])
            bot.append([bm.verts.new(base + n * w * v - V(0, t * tt, 0)) for v, t, _ in self.ROWS])
            if edge_pts is not None:
                edge_pts.append(tuple(base + n * w))
        tip = self.spine(1.0) + self.stan(1.0) * 0.02
        tipv = bm.verts.new(tip)
        faces = []

        def F(vs, mat):
            f = bm.faces.new(vs)
            f.material_index = mat
            faces.append(f)

        for i in range(nu):
            for k in range(R - 1):
                mat = self.ROWS[k][2]
                F([top[i][k], top[i][k + 1], top[i + 1][k + 1], top[i + 1][k]], mat)
                F([bot[i][k], bot[i + 1][k], bot[i + 1][k + 1], bot[i][k + 1]], mat)
            F([top[i][0], top[i + 1][0], bot[i + 1][0], bot[i][0]], self.ROWS[0][2])
            F([top[i][R - 1], bot[i][R - 1], bot[i + 1][R - 1], top[i + 1][R - 1]], M_STEEL)
        ring0 = top[0] + bot[0][::-1]
        F(ring0[::-1], M_OBS)
        ringN = top[nu] + bot[nu][::-1]
        for a_, b_ in zip(ringN, ringN[1:] + ringN[:1]):
            F([a_, b_, tipv], M_STEEL)
        bmesh.ops.recalc_face_normals(bm, faces=faces)
        ob = make_obj(name, bm, smooth=True)
        # glowing edge: crimson flame tongues (just proud of the body) down to a white-hot rim
        rings, crings = [], []
        ng = nu_glow or nu
        for u in [u_end * i / ng for i in range(ng + 1)]:
            tt = self.tt(u)
            base, n, w = self.spine(u), self.nin(u), self.width(u)
            v0 = 0.822 - self.tongue(u)
            t0 = self.row_t(v0) + 0.0025 / max(tt, 0.3)
            pts = [(v0, t0), (0.83, 0.057), (0.955, 0.03)]
            ring = [base + n * w * v + V(0, t * tt, 0) for v, t in pts]
            ring += [base + n * w * v - V(0, t * tt, 0) for v, t in reversed(pts)]
            rings.append(ring)
        for u in us:
            tt = self.tt(u)
            base, n, w = self.spine(u), self.nin(u), self.width(u)
            cp = [(0.945, 0.033), (1.0, 0.014)]
            cr = [base + n * w * v + V(0, t * tt, 0) for v, t in cp]
            cr += [base + n * w * v - V(0, t * tt, 0) for v, t in reversed(cp)]
            crings.append(cr)
        rings.append(tip)
        crings.append(tip + self.stan(1.0) * 0.004)
        loft(gl, rings)
        make_obj(name + "Edge_Glow", gl, kind="glow")
        cb = new_bm()
        loft(cb, crings)
        make_obj(name + "Edge_Core", cb, kind="core")
        return ob


BLADE = BladeShape([V(-0.30, 0, 4.64), V(-1.02, 0, 5.24), V(-3.34, 0, 4.94), V(-3.02, 0, 3.16)], 0.80, root_narrow=0.5,
                   tongues=14, tongue_depth=0.28)
HOOK = BladeShape([V(0.14, 0, 3.50), V(0.58, 0, 3.76), V(1.08, 0, 3.60), V(1.04, 0, 3.00)], 0.32, root_narrow=0.6,
                  root_len=0.12, belly=0.1, thick=0.9, taper=0.45, tongues=3, tongue_depth=0.10)
ROWS = BladeShape.ROWS
SPINE_LEN = BLADE.length


def spine(u):
    return BLADE.spine(u)


def stan(u):
    return BLADE.stan(u)


def nin(u):
    return BLADE.nin(u)


def bwidth(u):
    return BLADE.width(u)


def thick_taper(u):
    return BLADE.tt(u)


def row_t(v):
    return BLADE.row_t(v)


def blade_point(u, v, side=0.0, t=None):
    return BLADE.point(u, v, side, t)


def u_at(s):
    return BLADE.u_at(s)


def _ferrule_u():
    """First u where the blade spine leaves the cowl."""
    for i in range(1, 400):
        u = 0.3 * i / 400
        q = spine(u)
        if abs(q.x - COWL_C.x) > head_radius(q.z - COWL_C.z) + 0.015:
            return u
    return 0.08


U_F = _ferrule_u()
U_F_S = float(np.interp(U_F, BLADE._us, BLADE._sl))
BLADE_EDGE_PTS = []      # sampled cutting edge (for the painted gradient)


def build_blade():
    return BLADE.build("Blade", nu=30, edge_pts=BLADE_EDGE_PTS, nu_glow=72)


SIGILS = {
    # filled shapes in unit glyph space: a along the blade (toward the tip), b toward the spine
    "flame": [(0.00, -0.50), (0.20, -0.44), (0.32, -0.28), (0.34, -0.06), (0.26, 0.12), (0.32, 0.32), (0.14, 0.20),
              (0.06, 0.34), (-0.02, 0.52), (-0.10, 0.30), (-0.22, 0.16), (-0.32, 0.00), (-0.34, -0.20), (-0.24, -0.40)],
    "skull": [(0.00, 0.50), (0.24, 0.44), (0.36, 0.24), (0.36, 0.02), (0.26, -0.14), (0.20, -0.26), (0.20, -0.46),
              (-0.20, -0.46), (-0.20, -0.26), (-0.26, -0.14), (-0.36, 0.02), (-0.36, 0.24), (-0.24, 0.44)],
}
SKULL_HOLES = [[(-0.22, 0.14), (-0.05, 0.06), (-0.08, -0.07), (-0.22, -0.04)],
               [(0.22, 0.14), (0.08, -0.07), (0.05, 0.06)],
               [(0.0, -0.10), (-0.05, -0.2), (0.05, -0.2)],
               [(-0.13, -0.30), (0.13, -0.30), (0.13, -0.36), (-0.13, -0.36)]]
SKULL_HOLES[1] = [(0.22, 0.14), (0.22, -0.04), (0.08, -0.07), (0.05, 0.06)]
SIGIL_LAYOUT = [("flame", 0.235, 0.53, 0.36), ("skull", 0.36, 0.53, 0.33), ("flame", 0.48, 0.52, 0.29), ("skull", 0.595, 0.5, 0.22)]


def sigil_prism(bm, poly, u, v, size, side, d0, d1, grow=1.0, mat=0):
    a = stan(u)
    b = -nin(u)
    c = blade_point(u, v)
    c.y = 0
    t_s = row_t(v) * thick_taper(u)
    n = V(0, side, 0)
    pts = [c + a * (x * grow) * size + b * (y * grow) * size for x, y in poly]
    loft(bm, [[q + n * (t_s + d0) for q in pts], [q + n * (t_s + d1) for q in pts]], mat=mat)


def build_runes(blade):
    """Soul sigils (flames and skulls) engraved into both faces: boolean-cut grooves with a
    glowing inlay sunk inside; skull eyes, nose and mouth as dark plugs just proud of the glow."""
    cut, gl, det = new_bm(), new_bm(), new_bm()
    for glyph, u, v, sz in SIGIL_LAYOUT:
        for side in (1, -1):
            sigil_prism(cut, SIGILS[glyph], u, v, sz, side, -0.016, 0.08, grow=1.16, mat=M_SOCK)
            sigil_prism(gl, SIGILS[glyph], u, v, sz, side, -0.024, -0.006)
            if glyph == "skull":
                for hole in SKULL_HOLES:
                    sigil_prism(det, hole, u, v, sz, side, -0.024, -0.003, mat=M_SOCK)
    cutter = make_obj("RuneCutter", cut, kind="cut")
    add_bool(blade, cutter)
    make_obj("Runes_Glow", gl, kind="glow")
    return make_obj("SigilEyes", det)


def build_vertebrae():
    """Graded bone ribs riding the bone spine: big near the head, shrinking toward the tip.
    Each is a barrel centrum with a rib that curves back toward the tip; soft chamfered."""
    bm = new_bm()
    N = 9
    s_ = U_F_S + 0.46
    for k in range(N):
        f = k / (N - 1)
        u = u_at(s_)
        T, O = stan(u), -nin(u)
        r = 0.092 * (1 - 0.45 * f)
        L = 0.17 * (1 - 0.4 * f)
        M = Matrix.Translation(spine(u) + O * 0.02) @ basis(T, V(0, 1, 0), O)
        rings = []
        for x, rr in ((-L / 2, 0.7), (-L / 2 + 0.03, 1.0), (L / 2 - 0.03, 1.0), (L / 2, 0.7)):
            rings.append([M @ V(x, math.cos(a) * r * rr * 1.05, math.sin(a) * r * rr)
                          for a in [math.pi / 6 + 2 * math.pi * q / 6 for q in range(6)]])
        loft(bm, rings, mat=M_BONE)
        Ls = 0.52 * (1 - 0.80 * f) + 0.07
        w0 = 0.088 * (1 - 0.5 * f)
        sp = [V(-0.02, 0, r * 0.6), V(0.03 + 0.12 * Ls, 0, r + 0.42 * Ls), V(0.12 + 0.34 * Ls, 0, r + 0.80 * Ls),
              V(0.26 + 0.58 * Ls, 0, r + 1.0 * Ls)]
        tube(bm, [M @ q for q in sp], [(w0, w0 * 0.55), (w0 * 0.78, w0 * 0.45), (w0 * 0.5, w0 * 0.3), 0.0], sides=4,
             mat=M_BONE, up=V(0, 1, 0))
        s_ += 0.33 * (1 - 0.5 * f) + 0.07
    ob = make_obj("Vertebrae", bm)
    soft(ob, 0.009, angle=28)
    return ob


def build_blade_trim():
    """Gold ferrule where the blade leaves the cowl, a crimson soul gem set in each face,
    and soul-fire bursting from the ferrule and streaming back along the bone spine."""
    bm = new_bm()
    rings = []
    for u, grow in ((U_F - 0.022, 1.06), (U_F - 0.012, 1.16), (U_F + 0.028, 1.16), (U_F + 0.038, 1.06)):
        tt = thick_taper(u)
        base, n, w = spine(u), nin(u), bwidth(u)
        c = base + n * w * 0.45
        ring = [c + ((base + n * w * v + V(0, t * tt, 0)) - c) * grow for v, t, _ in ROWS + [(1.0, 0.03, None)]]
        ring += [c + ((base + n * w * v - V(0, t * tt, 0)) - c) * grow for v, t, _ in reversed(ROWS + [(1.0, 0.03, None)])]
        rings.append(ring)
    loft(bm, rings, mat=M_GOLD)
    g, c = new_bm(), new_bm()
    u = U_F + 0.008
    gc = blade_point(u, 0.50)
    t_out = row_t(0.5) * thick_taper(u) * 1.16 + 0.004
    for side in (1, -1):
        R = Matrix.Rotation(math.radians(-90 * side), 4, "X")
        M = Matrix.Translation(V(gc.x, side * t_out, gc.z)) @ R @ Matrix.Scale(1.15, 4)
        lathe(bm, [(0.0, -0.01), (0.10, -0.01), (0.112, 0.012), (0.098, 0.03), (0.07, 0.03)], sides=8, M=M, mat=M_GOLD)
        lathe(g, [(0.0, 0.0), (0.078, 0.02), (0.07, 0.045), (0.035, 0.065), (0.0, 0.068)], sides=8, M=M)
        lathe(c, [(0.0, 0.05), (0.03, 0.062), (0.0, 0.074)], sides=6, M=M)
    for du, h, w, ph in ((0.006, 0.50, 0.105, 0.3), (0.03, 0.36, 0.085, 1.7), (-0.012, 0.30, 0.075, 3.0)):
        uu = U_F + du
        o = -nin(uu)
        base = spine(uu) + o * 0.02
        up = o + stan(uu) * 0.8
        flame(g, base, up, h, w, lean=stan(uu) * 0.3, wiggle=0.45, sides=5, flat=0.55, phase=ph)
        flame(c, base + o * 0.03, up, h * 0.42, w * 0.5, wiggle=0.3, sides=4, flat=0.6, phase=ph)
    ob = make_obj("BladeFerrule", bm)
    hard(ob, 0.007, segs=1)
    make_obj("FerruleGem_Glow", g, kind="glow")
    make_obj("FerruleGem_Core", c, kind="core")
    return ob


def curve_mesh(name, paths, depth, mirror_y=False, mat=None, res=3):
    """Round-section gold wire: Bezier/poly curves with bevel depth, converted to mesh.
    Optional Mirror modifier (Y) puts the same ornament on the far face."""
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


def scroll_path(start, mid, center, r0, turns, sgn, n=10):
    """A lead-in stroke that ends in a tightening curl (2D points)."""
    pts = [start, mid]
    ang0 = math.atan2(mid[1] - center[1], mid[0] - center[0])
    for k in range(1, n + 1):
        t = k / n
        a = ang0 + sgn * turns * 2 * math.pi * t
        r = r0 * (1 - 0.72 * t)
        pts.append((center[0] + r * math.cos(a), center[1] + r * math.sin(a)))
    return pts


def build_filigree():
    """Gold scrollwork on both faces of the blade root: a pair of curls spreading from the ferrule."""
    u0 = U_F + 0.05
    T = stan(u0)
    Bv = -nin(u0)
    base = blade_point(u0, 0.52)
    y = row_t(0.52) * thick_taper(u0) + 0.004
    paths = []
    for sg in (1, -1):
        pts2 = scroll_path((0.0, sg * 0.03), (0.13, sg * 0.10), (0.20, sg * 0.055), 0.055, 1.1, -sg, n=7)
        paths.append([V((base + T * a + Bv * b).x, y, (base + T * a + Bv * b).z) for a, b in pts2])
    # a small diamond-tip stroke between the curls
    paths.append([V((base + T * a).x, y, (base + T * a).z) for a in (0.02, 0.10, 0.17)])
    return curve_mesh("Filigree", paths, 0.014, mirror_y=True, res=2)


def build_shaft():
    bm = new_bm()
    zs = [SHAFT_Z0 + (SHAFT_Z1 - SHAFT_Z0) * k / 2 for k in range(3)]
    tube(bm, [V(0, 0, z) for z in zs], [shaft_r(z) for z in zs], sides=8, mat=M_OBS, phase=math.pi / 8)
    ob = make_obj("Shaft", bm, smooth=True)
    hard(ob, 0.014, angle=30)
    return ob


def ring_band(bm, z, r_in, r_out, h, sides=10, mat=M_GOLD, crown=0.0, M=None):
    """Band around the shaft; crown > 0 raises every other top vertex into points."""
    M = M or Matrix()
    rings = []
    n = sides * (2 if crown else 1)
    prof = [(r_in, -h / 2), (r_out, -h / 2 + 0.012), (r_out, h / 2 - 0.012), (r_in, h / 2)]
    for j, (r, dz) in enumerate(prof):
        ring = []
        for s in range(n):
            a = math.pi / n + 2 * math.pi * s / n
            zz = z + dz
            if crown and j >= 2 and s % 2 == 0:
                zz += crown
            ring.append(M @ V(r * math.cos(a), r * math.sin(a), zz))
        rings.append(ring)
    return loft(bm, rings, mat=mat)


def build_grip():
    """Crimson leather strap wound around the shaft with gold crown bands at each end."""
    bm = new_bm()
    objs = []
    for z0, z1, pitch in ((1.52, 2.42, 0.078), (0.74, 1.02, 0.07)):
        R = shaft_r((z0 + z1) / 2) + 0.012
        turns = (z1 - z0) / pitch
        steps = int(turns * 6)
        rings = []
        wdt, th = pitch * 1.02, 0.03
        for k in range(steps + 1):
            th_a = 2 * math.pi * turns * k / steps
            z = z0 + (z1 - z0) * k / steps
            rad = V(math.cos(th_a), math.sin(th_a), 0)
            c = V(0, 0, z) + rad * R
            sec = [(-th * 0.5, -wdt * 0.5), (th * 0.2, -wdt * 0.46), (th * 0.6, 0.0), (th * 0.2, wdt * 0.46), (-th * 0.5, wdt * 0.5)]
            rings.append([c + rad * a + V(0, 0, b) + V(0, 0, 0) for a, b in sec])
        loft(bm, rings, mat=M_LEATHER)
    ob = make_obj("GripWrap", bm, smooth=False)
    objs.append(ob)
    b2 = new_bm()
    for z, cr in ((1.47, 0.0), (2.47, 0.0), (0.69, 0.0), (1.07, 0.0)):
        ring_band(b2, z, shaft_r(z) - 0.01, shaft_r(z) + 0.05, 0.075, sides=8)
    # crown-edged bands framing the main grip
    ring_band(b2, 1.40, shaft_r(1.4) - 0.01, shaft_r(1.4) + 0.035, 0.05, sides=6, crown=-0.045)
    ring_band(b2, 2.54, shaft_r(2.54) - 0.01, shaft_r(2.54) + 0.035, 0.05, sides=6, crown=0.045)
    ob2 = make_obj("GripBands", b2, smooth=True)
    hard(ob2, 0.008, segs=1, angle=30)
    objs.append(ob2)
    return objs


def build_collar():
    """Bold gold cup taking the shaft into the neck, crimson band, thorn ring, neck vertebrae."""
    bm = new_bm()
    lathe(bm, [(0.14, 3.26), (0.215, 3.31), (0.24, 3.43), (0.205, 3.51), (0.178, 3.55)], sides=10, mat=M_GOLD)
    lathe(bm, [(0.17, 3.55), (0.192, 3.56), (0.192, 3.645), (0.17, 3.655)], sides=10, mat=M_CRIM)
    lathe(bm, [(0.16, 3.655), (0.275, 3.70), (0.31, 3.80), (0.28, 3.885), (0.19, 3.925)], sides=12, mat=M_GOLD)
    ob = make_obj("Collar", bm, smooth=True)
    hard(ob, 0.012, segs=1, angle=28)
    b2 = new_bm()
    for k in range(6):
        a = 2 * math.pi * k / 6 + math.pi / 6
        d = V(math.cos(a), math.sin(a), 0)
        p0 = V(0, 0, 3.79) + d * 0.25
        tube(b2, [p0, p0 + d * 0.16 + V(0, 0, -0.12)], [0.058, 0.0], sides=4, mat=M_OBS, phase=math.pi / 4)
    ob2 = make_obj("CollarThorns", b2, smooth=True)
    hard(ob2, 0.007, segs=1)
    b3 = new_bm()
    for z, r in ((3.97, 0.105), (4.06, 0.095)):
        lathe(b3, [(r * 0.7, z - 0.04), (r, z - 0.022), (r, z + 0.022), (r * 0.7, z + 0.04)], sides=7, mat=M_BONE)
        for sx in (1, -1):
            tube(b3, [V(sx * r * 0.6, 0, z), V(sx * (r + 0.07), 0.01, z - 0.025)], [0.03, 0.0], sides=4, mat=M_BONE)
    ob3 = make_obj("NeckBones", b3)
    return [ob, ob2, ob3]


def build_back_spike():
    """Counter-hook: a smaller crescent on the other side of the head, same construction."""
    ob = HOOK.build("Hook", nu=11, edge_pts=BLADE_EDGE_PTS)
    add_bevel(ob, 0.007, segs=2, angle=24)
    add_wn(ob)
    bm = new_bm()
    rings = []
    for u, grow in ((0.0, 1.05), (0.02, 1.2), (0.09, 1.2), (0.11, 1.06)):
        base, n, w, tt = HOOK.spine(u), HOOK.nin(u), HOOK.width(u), HOOK.tt(u)
        c = base + n * w * 0.45
        ring = [c + ((base + n * w * v + V(0, t * tt, 0)) - c) * grow for v, t, _ in ROWS]
        ring += [c + ((base + n * w * v - V(0, t * tt, 0)) - c) * grow for v, t, _ in reversed(ROWS)]
        rings.append(ring)
    loft(bm, rings, mat=M_GOLD)
    ob2 = make_obj("HookCollar", bm)
    hard(ob2, 0.006, segs=1)
    return ob


def build_pommel():
    bm = new_bm()
    lathe(bm, [(0.14, 0.68), (0.18, 0.63), (0.225, 0.54), (0.23, 0.45), (0.20, 0.38), (0.14, 0.35)], sides=8, mat=M_GOLD)
    ob = make_obj("PommelCup", bm, smooth=True)
    hard(ob, 0.012, segs=1)
    b2 = new_bm()
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        d = V(math.cos(a), math.sin(a), 0)
        pts = [d * 0.19 + V(0, 0, 0.42), d * 0.215 + V(0, 0, 0.30), d * 0.17 + V(0, 0, 0.17), d * 0.08 + V(0, 0, 0.08)]
        tube(b2, pts, [(0.052, 0.04), (0.047, 0.036), (0.034, 0.026), 0.0], sides=5, mat=M_GOLD)
    ob2 = make_obj("PommelClaws", b2, smooth=True)
    hard(ob2, 0.008, segs=1)
    gl = new_bm()
    lathe(gl, [(0.0, -0.04), (0.09, 0.12), (0.14, 0.26), (0.12, 0.36), (0.0, 0.40)], sides=8)
    make_obj("PommelGem_Glow", gl, kind="glow")
    return [ob, ob2]


def build_chain():
    """Gold chain wound 1.5 turns around the upper shaft, then hanging with a soul lantern."""
    bm = new_bm()
    path = []
    turns, z0, z1 = 1.0, 3.24, 2.80
    for k in range(60):
        t = k / 59
        a = math.radians(-190) + 2 * math.pi * turns * t
        r = shaft_r(3.0) + 0.045
        path.append(V(r * math.cos(a), r * math.sin(a), lerp(z0, z1, t)))
    end = path[-1]
    out = V(end.x, end.y, 0).normalized()
    for k in range(1, 12):
        t = k / 11
        path.append(end + out * (0.13 * t) + V(0, 0, -0.30 * t))
    pts = np.array([tuple(p) for p in path])
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    step = 0.084
    n_links = int(cum[-1] / step)
    a_, b_, rr = 0.062, 0.036, 0.014
    for i in range(n_links):
        s = i * step + step * 0.5
        p = V(*[float(np.interp(s, cum, pts[:, j])) for j in range(3)])
        q = V(*[float(np.interp(min(s + 0.01, cum[-1]), cum, pts[:, j])) for j in range(3)])
        T = (q - p).normalized()
        radial = V(p.x, p.y, 0).normalized()
        side = T.cross(radial).normalized()
        up = side.cross(T).normalized()
        if i % 2:
            side, up = up, -side
        M = Matrix.Translation(p) @ basis(T, side, up)
        rings = []
        for j in range(6):
            ang = 2 * math.pi * j / 6
            c = V(a_ * math.cos(ang), b_ * math.sin(ang), 0)
            tn = V(-a_ * math.sin(ang), b_ * math.cos(ang), 0).normalized()
            nrm = V(tn.y, -tn.x, 0)
            rings.append([M @ (c + nrm * rr * math.cos(2 * math.pi * q4 / 4 + math.pi / 4) + V(0, 0, rr * math.sin(2 * math.pi * q4 / 4 + math.pi / 4)))
                          for q4 in range(4)])
        rings.append(rings[0])
        vr = [[bm.verts.new(p_) for p_ in r] for r in rings[:-1]]
        for j in range(6):
            A, B = vr[j], vr[(j + 1) % 6]
            for q4 in range(4):
                f = bm.faces.new([A[q4], A[(q4 + 1) % 4], B[(q4 + 1) % 4], B[q4]])
                f.material_index = M_GOLD
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    ob = make_obj("Chain", bm, smooth=True)
    add_wn(ob)
    # soul lantern hanging from the chain end
    tip = path[-1] + V(0, 0, -0.03)
    lb = new_bm()
    top = tip + V(0, 0, -0.03)
    lathe(lb, [(0.0, 0.0), (0.03, -0.01), (0.075, -0.05), (0.085, -0.07), (0.05, -0.08)], sides=6, M=Matrix.Translation(top), mat=M_GOLD)
    bot = top + V(0, 0, -0.28)
    lathe(lb, [(0.05, 0.0), (0.085, -0.01), (0.075, -0.04), (0.02, -0.07), (0.0, -0.12)], sides=6, M=Matrix.Translation(bot), mat=M_GOLD)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        d = V(math.cos(a), math.sin(a), 0)
        tube(lb, [top + V(0, 0, -0.07) + d * 0.07, top + V(0, 0, -0.16) + d * 0.095, bot + d * 0.07], [0.014, 0.016, 0.014],
             sides=4, mat=M_GOLD)
    ob2 = make_obj("Lantern", lb, smooth=True)
    add_wn(ob2)
    g = new_bm()
    c = new_bm()
    flame(g, bot + V(0, 0, 0.0), V(0, 0, 1), 0.2, 0.055, wiggle=0.2, sides=5, flat=0.9)
    flame(c, bot + V(0, -0.012, 0.01), V(0, 0, 1), 0.11, 0.03, wiggle=0.15, sides=5, flat=0.9)
    make_obj("LanternFlame_Glow", g, kind="glow")
    make_obj("LanternFlame_Core", c, kind="core")
    return [ob, ob2]


# ---------------------------------------------------------------------------
# Head: skull + hood (concept A) or horned crowned skull (concept B)
# ---------------------------------------------------------------------------
def skull_front_y(x, z):
    """Approximate y of the cranium's front surface (relative to S) at (x, z)."""
    prof = [(-0.19, 0.17), (-0.10, 0.26), (0.02, 0.30), (0.13, 0.305), (0.24, 0.27), (0.32, 0.19)]
    r = float(np.interp(z, [p[0] for p in prof], [p[1] for p in prof]))
    return -math.sqrt(max(r * r - x * x, 0.0)) * 0.95


def build_skull(scale=1.0):
    bm = new_bm()
    M = Matrix.Translation(S) @ Matrix.Scale(scale, 4)
    prof = [(0.0, -0.17), (0.15, -0.20), (0.24, -0.10), (0.30, 0.02), (0.305, 0.13), (0.27, 0.24), (0.19, 0.32),
            (0.09, 0.365), (0.0, 0.375)]
    lathe(bm, prof, sides=14, M=M, mat=M_BONE, sy=0.95, phase=0.0)
    cranium = make_obj("Cranium", bm)
    add_bevel(cranium, 0.008, segs=1, angle=35, harden=False)
    bm = new_bm()
    # angry brow ridge
    bpts = [V(-0.26, 0, 0.15), V(-0.14, 0, 0.115), V(0.0, 0, 0.06), V(0.14, 0, 0.115), V(0.26, 0, 0.15)]
    bpts = [V(p.x, skull_front_y(p.x, p.z) + 0.015, p.z) for p in bpts]
    tube(bm, [M @ p for p in bpts], [0.03, 0.042, 0.04, 0.042, 0.03], sides=5, mat=M_BONE, flat=0.8, up=V(0, 0, 1))
    # upper teeth
    for i in range(6):
        x = -0.125 + 0.05 * i
        y = skull_front_y(x, -0.2) + 0.03
        c = V(x, y, -0.235)
        box(bm, M @ c, (0.042 * scale, 0.05 * scale, 0.07 * scale), mat=M_BONE)
    # lower jaw with teeth
    jaw = [V(-0.21, 0.02, -0.25), V(-0.17, -0.15, -0.34), V(0.0, -0.215, -0.365), V(0.17, -0.15, -0.34), V(0.21, 0.02, -0.25)]
    tube(bm, [M @ p for p in jaw], [(0.045, 0.03), (0.055, 0.035), (0.06, 0.04), (0.055, 0.035), (0.045, 0.03)], sides=6,
         mat=M_BONE, up=V(0, 0, 1))
    for i in range(5):
        x = -0.1 + 0.05 * i
        y = -0.205 + 0.06 * (x / 0.17) ** 2
        box(bm, M @ V(x, y, -0.31), (0.04 * scale, 0.045 * scale, 0.055 * scale), mat=M_BONE)
    # dark mouth cavity behind the teeth
    box(bm, M @ V(0, -0.02, -0.29), (0.24 * scale, 0.26 * scale, 0.09 * scale), mat=M_SOCK)
    sk = make_obj("SkullDetail", bm)
    soft(sk, 0.007, angle=35)
    # sockets and nose, cut with booleans (cut faces take the dark Socket colour)
    cut = new_bm()
    for sx in (1, -1):
        c = V(sx * 0.122, -0.40, 0.03)
        R = Matrix.Rotation(math.radians(-sx * 17), 4, "Y")
        hexp = [(math.cos(math.pi / 6 + k * math.pi / 3) * 0.108, math.sin(math.pi / 6 + k * math.pi / 3) * 0.086) for k in range(6)]
        pts0 = [M @ (c + (R @ V(u, 0, v))) for u, v in hexp]
        pts1 = [M @ (c + (R @ V(u * 0.8, 0.30, v * 0.8))) for u, v in hexp]
        loft(cut, [pts0, pts1], mat=M_SOCK)
    tri = [(0.0, -0.035), (0.042, 0.04), (-0.042, 0.04)]
    loft(cut, [[M @ V(u, -0.40, -0.09 + v) for u, v in tri], [M @ V(u * 0.6, -0.16, -0.09 + v * 0.6) for u, v in tri]], mat=M_SOCK)
    cutter = make_obj("SkullCutter", cut, kind="cut")
    add_bool(cranium, cutter)
    # glowing eyes deep in the sockets
    g, c = new_bm(), new_bm()
    for sx in (1, -1):
        e = V(sx * 0.118, skull_front_y(sx * 0.118, 0.03) + 0.075, 0.025)
        lathe(g, [(0.0, -0.045), (0.056, -0.02), (0.066, 0.01), (0.045, 0.04), (0.0, 0.05)], sides=6,
              M=Matrix.Translation(M @ e) @ Matrix.Rotation(math.radians(90), 4, "X") @ Matrix.Scale(scale, 4), phase=0.0)
        lathe(c, [(0.0, -0.02), (0.03, 0.0), (0.0, 0.03)], sides=6,
              M=Matrix.Translation(M @ (e + V(0, -0.05, 0.005))) @ Matrix.Rotation(math.radians(90), 4, "X") @ Matrix.Scale(scale, 4))
    for sx in (1, -1):
        e0 = V(sx * 0.15, skull_front_y(sx * 0.15, 0.09) + 0.045, 0.09)
        up = V(sx * 0.6, 0.35, 1.0)
        flame(g, M @ e0, up, 0.30 * scale, 0.05 * scale, lean=V(sx * 0.1, 0.12, 0), wiggle=0.4, sides=4, flat=0.6, phase=1.0 + sx)
        flame(c, M @ (e0 + V(0, -0.012, 0)), up, 0.14 * scale, 0.025 * scale, wiggle=0.3, sides=4, flat=0.6, phase=1.0 + sx)
    make_obj("Eyes_Glow", g, kind="glow")
    make_obj("Eyes_Core", c, kind="core")
    return sk


def build_hood():
    """Draped cowl: one closed lathe (cloth outside, crimson lining inside) with a soft crown,
    a brim overhanging the sunken skull, a slight droop at the back, deep folds that grow toward
    a tattered hem; the face opening is a gothic-arch boolean; gold trim is raycast onto the
    opening edge; a gold medallion sits on the back."""
    bm = new_bm()
    sides = 24
    prof = COWL_OUT + COWL_IN
    nO = len(COWL_OUT)
    rings = []
    for idx, (r, z) in enumerate(prof):
        if r <= 1e-6:
            rings.append([V(0, 0, z)])
            continue
        fold = 0.11 * (1 - smoothstep(-0.58, 0.3, z))
        ring = []
        for k in range(sides):
            a_ = 2 * math.pi * k / sides - math.pi / 2
            rr = r * (1 + fold * math.sin(a_ * 8 + 0.5))
            x, y, zz = rr * math.cos(a_), rr * math.sin(a_), z
            fy = math.sin(a_)
            if fy < 0:
                y -= 0.10 * smoothstep(0.12, 0.34, z) * (1 - smoothstep(0.52, 0.66, z)) * (-fy)
            if fy > 0 and z > 0.2:
                t = (z - 0.2) / 0.46
                y += 0.20 * t ** 1.4 * fy
                zz -= 0.06 * t * fy
            if idx in (0, len(prof) - 1):
                hsh = (math.sin(k * 12.9898 + 1.7) * 43758.5453) % 1.0
                zz -= 0.03 + 0.15 * hsh * (0.6 + 0.4 * (k % 2))
            ring.append(V(x, y, zz))
        rings.append(ring)
    vr = [[bm.verts.new(q) for q in r] for r in rings]
    faces = []
    for k in range(len(vr)):
        A, B = vr[k], vr[(k + 1) % len(vr)]
        if len(A) == 1 and len(B) == 1:
            continue
        mat = M_CLOTH if k < nO - 1 else M_LINING
        for j in range(sides):
            j2 = (j + 1) % sides
            if len(B) == 1:
                f = bm.faces.new([A[j], A[j2], B[0]])
            elif len(A) == 1:
                f = bm.faces.new([A[0], B[j2], B[j]])
            else:
                f = bm.faces.new([A[j], A[j2], B[j2], B[j]])
            f.material_index = mat
            faces.append(f)
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    for v in bm.verts:
        v.co = v.co + COWL_C
    hood = make_obj("Hood", bm)
    cut = new_bm()
    W, Za, Zb = 0.37, 0.50, -0.95
    right = [(W, Zb), (W, -0.1), (W * 0.99, 0.08), (W * 0.9, 0.22), (W * 0.72, 0.34), (W * 0.44, 0.44), (0.0, Za)]
    arch = right + [(-x, z) for x, z in reversed(right[:-1])]
    loft(cut, [[COWL_C + V(x, -0.95, z) for x, z in arch], [COWL_C + V(x * 0.96, -0.02, z) for x, z in arch]], mat=M_LINING)
    cutter = make_obj("HoodCutter", cut, kind="cut")
    add_bool(hood, cutter)
    soft(hood, 0.012, angle=35)
    from mathutils.bvhtree import BVHTree
    for m in hood.modifiers:
        m.show_viewport = False
    bpy.context.view_layer.update()
    bvh = BVHTree.FromObject(hood, bpy.context.evaluated_depsgraph_get())
    for m in hood.modifiers:
        m.show_viewport = True
    bpy.context.view_layer.update()
    poly = np.array(arch[1:-1])
    seg = np.linalg.norm(np.diff(poly, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    tpts = []
    for sd in np.linspace(0, cum[-1], 28):
        x = float(np.interp(sd, cum, poly[:, 0]))
        z = float(np.interp(sd, cum, poly[:, 1]))
        if z < -0.62:
            continue
        hit, nrm, idx, dist = bvh.ray_cast(COWL_C + V(x * 1.03, -2.0, z), V(0, 1, 0))
        if hit is not None:
            tpts.append(hit + V(0, -0.006, 0))
    tb = new_bm()
    if len(tpts) > 2:
        rad = [0.036] * len(tpts)
        rad[0] = rad[-1] = 0.012
        tube(tb, tpts, rad, sides=6, mat=M_GOLD, up=V(0, 1, 0))
    hit, nrm, idx, dist = bvh.ray_cast(COWL_C + V(0, 1.6, 0.05), V(0, -1, 0))
    if hit is not None:
        Mm = Matrix.Translation(hit + nrm * 0.004) @ nrm.to_track_quat("Z", "Y").to_matrix().to_4x4()
        lathe(tb, [(0.0, -0.02), (0.115, -0.02), (0.125, 0.005), (0.11, 0.025), (0.085, 0.03), (0.0, 0.03)], sides=10, M=Mm, mat=M_GOLD)
        MEDALLION.append(Mm)
    trim = make_obj("HoodTrim", tb, smooth=True)
    add_wn(trim)
    return hood


HOOD_GEM = []
MEDALLION = []


def build_hood_flames():
    """The hood's glowing throat-clasp gem (the soul fire itself lives on the blade edge)."""
    g, c = new_bm(), new_bm()
    for Mm in MEDALLION:                   # eye rune: diamond ring with a slit, proud of the medallion
        ring = [(0, 0.075), (0.055, 0), (0, -0.075), (-0.055, 0)]
        inner = [(0, 0.045), (0.03, 0), (0, -0.045), (-0.03, 0)]
        for k in range(4):
            a0, a1 = ring[k], ring[(k + 1) % 4]
            b0, b1 = inner[k], inner[(k + 1) % 4]
            poly = [a0, a1, b1, b0]
            loft(g, [[Mm @ V(x, y, 0.026) for x, y in poly], [Mm @ V(x, y, 0.042) for x, y in poly]])
        loft(g, [[Mm @ V(x, y, 0.026) for x, y in ((-0.008, 0.03), (0.008, 0.03), (0.008, -0.03), (-0.008, -0.03))],
                 [Mm @ V(x, y, 0.042) for x, y in ((-0.008, 0.03), (0.008, 0.03), (0.008, -0.03), (-0.008, -0.03))]])
    for m_ in HOOD_GEM:
        lathe(g, [(0.0, -0.01), (0.05, 0.0), (0.04, 0.03), (0.0, 0.045)], sides=6,
              M=Matrix.Translation(m_) @ Matrix.Rotation(math.radians(90), 4, "X"))
    make_obj("HoodFlames_Glow", g, kind="glow")
    lathe(c, [(0.0, -0.005), (0.022, 0.012), (0.0, 0.05)], sides=6,
          M=Matrix.Translation(HOOD_GEM[0] + V(0, -0.012, 0)) @ Matrix.Rotation(math.radians(90), 4, "X")) if HOOD_GEM else None
    make_obj("HoodFlames_Core", c, kind="core")


def build_horns():
    bm = new_bm()
    for sx in (1, -1):
        pts = [V(sx * 0.2, 0.05, 0.22), V(sx * 0.36, 0.10, 0.36), V(sx * 0.46, 0.14, 0.56), V(sx * 0.42, 0.20, 0.76), V(sx * 0.30, 0.26, 0.86)]
        pts = [S + p for p in pts]
        tube(bm, pts, [0.085, 0.075, 0.058, 0.035, 0.0], sides=7, mat=M_OBS)
    ob = make_obj("Horns", bm, smooth=True)
    hard(ob, 0.008)
    b2 = new_bm()
    for sx in (1, -1):
        for t, r in ((0.3, 0.083), (0.5, 0.07)):
            c = S + V(sx * lerp(0.2, 0.46, t * 1.5), lerp(0.05, 0.14, t), lerp(0.22, 0.56, t * 1.2))
            lathe(b2, [(r, -0.02), (r + 0.015, -0.01), (r + 0.015, 0.01), (r, 0.02)], sides=8, M=Matrix.Translation(c), mat=M_GOLD)
    ob2 = make_obj("HornRings", b2, smooth=True)
    hard(ob2, 0.005)
    # crown circlet with spikes
    b3 = new_bm()
    ring_band(b3, S.z + 0.2, 0.28, 0.315, 0.07, sides=10, crown=0.09)
    ob3 = make_obj("Crown", b3, smooth=True)
    hard(ob3, 0.006)
    g, c = new_bm(), new_bm()
    lathe(g, [(0.0, -0.05), (0.05, 0.0), (0.0, 0.06)], sides=6, M=Matrix.Translation(S + V(0, -0.315, 0.24)) @ Matrix.Rotation(math.radians(90), 4, "X"))
    make_obj("CrownGem_Glow", g, kind="glow")
    g = new_bm()
    for x, h, ph in ((-0.12, 0.4, 0.2), (0.0, 0.55, 1.1), (0.12, 0.42, 2.0)):
        flame(g, S + V(x, 0.02, 0.33), V(0, 0.2, 1), h, 0.085, lean=V(0, 0.25, 0), wiggle=0.4, phase=ph)
        flame(c, S + V(x, -0.02, 0.35), V(0, 0.2, 1), h * 0.45, 0.045, lean=V(0, 0.15, 0), wiggle=0.3, phase=ph)
    make_obj("CrownFlames_Glow", g, kind="glow")
    make_obj("CrownFlames_Core", c, kind="core")


def build_head():
    if CONCEPT == "A":
        build_skull(SKULL_SCALE)
        build_hood()
        build_hood_flames()
    else:
        build_skull(1.08)
        build_horns()


def build_all():
    blade = build_blade()
    add_bevel(blade, 0.009, segs=2, angle=24)      # bevel first: never bevel boolean output
    build_runes(blade)
    add_wn(blade)
    build_vertebrae()
    build_blade_trim()
    build_shaft()
    build_grip()
    build_collar()
    build_back_spike()
    build_pommel()
    build_chain()
    build_head()


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
    """Freeze every modifier (bevels, booleans, mirrors), clean slivers the booleans leave,
    then apply weighted normals last; drop the cutters."""
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


# ---------------------------------------------------------------------------
# Review rendering: the weapon catalogue's own stage (batches/magic/build_magic.py `finish`):
# ortho camera at center + cam*extent/5, Key/Fill/Rim disk area lights, dark floor, grey world,
# Cycles 24 spp + denoise, AgX. Glow gets a mild bloom (Roblox Neon blooms in game).
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


def catalog_stage(objs, angle, camvec, res=1000, samples=24, ortho_pad=1.18, focus=None, world=0.0509, floor=True,
                  extra_objs=()):
    """Pose + camera + lights exactly like the catalogue. Returns a restore function."""
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
        # the catalogue's floor sets diffuse_color only, so its node base colour stays at the 0.8 default
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
    for shot in SHOTS:
        if shot == "catalog":
            r = catalog_stage(objs, -12, (1.6, -15, 6.2))
            render(OUT / f"q_{CONCEPT}_catalog.png")
            r()
        elif shot == "head":
            r = catalog_stage(objs, 0, (1.2, -15, 3.0))
            cam = STAGE["cam"]
            cam.data.ortho_scale = 2.0
            tgt = V(-0.35, 0, 4.5)
            cam.location = tgt + V(3.5, -11, 3.2)
            cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
            render(OUT / f"q_{CONCEPT}_head.png")
            r()
        elif shot in ("front", "side", "back"):
            vec = {"front": (0, -15, 2.0), "side": (15, 0, 2.0), "back": (0, 15, 2.0)}[shot]
            r = catalog_stage(objs, 0, vec)
            render(OUT / f"q_{CONCEPT}_{shot}.png")
            r()
        elif shot == "blade":
            r = catalog_stage(objs, 0, (1.2, -15, 3.0))
            cd = STAGE["cam"].data
            cd.ortho_scale = 3.0
            cam = STAGE["cam"]
            tgt = V(-1.7, 0, 4.4)
            cam.location = V(tgt.x + 1.0, -12, tgt.z + 2.4)
            cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
            render(OUT / f"q_{CONCEPT}_blade.png")
            r()


if MODE == "quick":
    quick_shots()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / f"q_{CONCEPT}.blend"))
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
SCALE = min(1.0, TARGET_HEIGHT / H0)
for o in PARTS:
    o.data.transform(Matrix.Scale(SCALE, 4) @ Matrix.Translation(V(0, 0, -Z0)))
    o.data.update()
BLADE_EDGE_PTS = [tuple((Vector(p) - V(0, 0, Z0)) * SCALE) for p in BLADE_EDGE_PTS]
SKULL = (S - V(0, 0, Z0)) * SCALE
log(f"authored height {H0:.3f} -> scale {SCALE:.4f}")

_by_kind = {k: [o for o in PARTS if o["kind"] == k] for k in ("tex", "glow", "core")}
PART_TRIS = dict(TRIS)
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
# glow meshes: one material, flat-shaded (Neon shows only the silhouette)
for o, m in ((glow_ob, GLOW_MAT), (core_ob, CORE_MAT)):
    o.data.materials.clear()
    o.data.materials.append(m)
    for p in o.data.polygons:
        p.material_index = 0

# UVs: one unique unwrap for the textured mesh (Roblox reads UV channel 1)
body.data.uv_layers.new(name="UVMap")
select_only([body])
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(52), island_margin=0.003, area_weight=0.0, correct_aspect=True,
                         scale_to_bounds=False)
bpy.ops.uv.pack_islands(rotate=True, margin=0.003)
bpy.ops.object.mode_set(mode="OBJECT")
for o in (glow_ob, core_ob):          # simple UVs so every exported mesh has a UV set
    o.data.uv_layers.new(name="UVMap")
    select_only([o])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.01)
    bpy.ops.object.mode_set(mode="OBJECT")
log("uv done")


# ---- painted masks (per face corner): Paint = value/colour gradient multiplier, Bleed = glow light
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
edge = np.array(BLADE_EDGE_PTS, np.float32)
sel = MI == M_STEEL
if sel.any():
    d = np.min(np.linalg.norm(P[sel][:, None, :] - edge[None, :, :], axis=2), axis=1)
    k = 1 - np_smooth(0.02, 0.55, d)
    paint[sel] *= (0.70 + 0.48 * k)[:, None]
sel = MI == M_CLOTH
if sel.any():
    t = np_smooth(SKULL.z - 0.55, SKULL.z + 0.75, P[sel][:, 2])
    paint[sel] *= (0.68 + 0.42 * t)[:, None]
sel = MI == M_OBS
paint[sel] *= (0.88 + 0.16 * np.clip(P[sel][:, 2] / 5.0, 0, 1))[:, None]
sel = MI == M_LINING
paint[sel] *= 0.85
sel = MI == M_BONE
paint[sel] *= np.array([1.0, 0.985, 0.95], np.float32)

# glow light bleeding onto nearby surfaces (baked; Roblox Neon does not light neighbours)
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


# ---- bake: painterly albedo x icon lighting (key, cool/warm, AO, cavity, height, rim) + bevel highlights + bleed
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
    if idx == M_BONE:        # broad painted hairline cracks, masked so only a few show
        vo = N("ShaderNodeTexVoronoi")
        vo.feature = "DISTANCE_TO_EDGE"
        vo.inputs["Scale"].default_value = 3.2
        L(pos, vo.inputs["Vector"])
        line = remap(vo.outputs["Distance"], 0.0, 0.03, 1.0, 0.0)
        nm = N("ShaderNodeTexNoise")
        nm.inputs["Scale"].default_value = 1.6
        L(pos, nm.inputs["Vector"])
        crack = math_("MULTIPLY", line, remap(nm.outputs["Fac"], 0.52, 0.64, 0.0, 1.0))
        albedo = mix(albedo, rgba((120, 92, 70)), math_("MULTIPLY", crack, 0.75))
    if idx in (M_CLOTH, M_LINING):   # soft vertical fold streaks
        vm = N("ShaderNodeVectorMath")
        vm.operation = "MULTIPLY"
        L(pos, vm.inputs[0])
        vm.inputs[1].default_value = (7.0, 7.0, 1.2)
        nf = N("ShaderNodeTexNoise")
        nf.inputs["Scale"].default_value = 1.0
        L(vm.outputs[0], nf.inputs["Vector"])
        albedo = mix(albedo, grey(remap(nf.outputs["Fac"], 0.3, 0.7, 0.8, 1.15)), 1.0, "MULTIPLY")
    k = dot_light(KEY_DIR)
    light = remap(k, 0.0, 1.0, 0.56, 1.2)
    tint = mix((0.86, 0.90, 1.07, 1), (1.08, 1.0, 0.9, 1), k)
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
    lit = mix(lit, (1.0, 0.32, 0.42, 1), rim, "ADD")
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

# ---- exports (asset geometry only)
select_only(FINAL, body)
bpy.ops.export_scene.gltf(filepath=str(ROOT / "Model.glb"), export_format="GLB", use_selection=True, export_apply=True)
bpy.ops.export_scene.fbx(filepath=str(ROOT / "Model.fbx"), use_selection=True, object_types={"MESH"}, axis_forward="-Z",
                         axis_up="Y", path_mode="COPY", embed_textures=True, add_leaf_bones=False, mesh_smooth_type="OFF")
log("exported")


# ---- stats + studio data
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
GRIP = V(0, 0, ((1.52 + 2.42) / 2 - Z0) * SCALE)
allmn = np.min([s["bounds_min"] for s in STATS.values()], axis=0)
allmx = np.max([s["bounds_max"] for s in STATS.values()], axis=0)
FLOAT_PIVOT = V(0, 0, float(allmn[2] + allmx[2]) / 2)
tex_c = (np.array(STATS[NAME]["bounds_min"]) + np.array(STATS[NAME]["bounds_max"])) / 2
install = {
    "name": NAME, "blender_version": bpy.app.version_string, "status": "Blender-verified, Studio untested",
    "units": "1 Blender unit = 1 stud, authored at hero size; set the play size in Studio by uniform scale",
    "axes": "Studio = (-x, z, y) of Blender; FBX exported with axis_forward=-Z, axis_up=Y",
    "texture": f"BaseColor.png {BAKE_SIZE}x{BAKE_SIZE}, baked painted lighting; use MeshPart.TextureID (not SurfaceAppearance)",
    "parts": {},
    "grip_point_studio": studio(GRIP),
    "grip_point_relative_to_textured_center": studio(np.array(tuple(GRIP)) - tex_c),
    "float_pivot_studio": studio(FLOAT_PIVOT),
    "float_pivot_relative_to_textured_center": studio(np.array(tuple(FLOAT_PIVOT)) - tex_c),
    "notes": ["Every MeshPart imports centred on its own bounding box: place each at its center_studio, "
              "relative to a shared model origin (Blender origin = pommel tip on the shaft axis).",
              "grip_point = middle of the crimson leather grip on the shaft axis (hand / spin pivot).",
              "float_pivot = mid-height point on the shaft axis (pivot for the floating idle bob and spin)."],
}
for o in FINAL:
    st = STATS[o.name]
    mn, mx = np.array(st["bounds_min"]), np.array(st["bounds_max"])
    kind = "textured" if o is body else "glow"
    part = {"kind": kind, "center_studio": studio((mn + mx) / 2), "size_studio": studio_size(mx - mn),
            "triangles": st["triangles"]}
    if o is glow_ob:
        part.update(material="Neon", color_rgb=list(GLOW), note="crimson glow: blade/hook edges, runes, eyes, flames, pommel gem")
    elif o is core_ob:
        part.update(material="Neon", color_rgb=list(CORE), note="white-hot cores: edge rims, eye pupils, flame hearts")
    else:
        part.update(material="SmoothPlastic (or Plastic), Color white", texture_id="BaseColor.png")
    install["parts"][o.name] = part
(ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=1))
log("stats", {k: v["triangles"] for k, v in STATS.items()}, "total", sum(v["triangles"] for v in STATS.values()))

# ---------------------------------------------------------------------------
# Renders
# ---------------------------------------------------------------------------
setup_comp(0.45)
HEAD = SKULL + V(-0.25, 0, 0.05)
BLADE_MID = (V(-1.55, 0, 4.35) - V(0, 0, Z0)) * SCALE


def zoom(target, scale, offset):
    cam = STAGE["cam"]
    cam.data.ortho_scale = scale
    cam.location = target + offset
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()


def shoot_catalog(name, angle, camvec, samples=32, res=1000):
    r = catalog_stage(FINAL, angle, camvec, samples=samples, res=res)
    render(ROOT / name)
    r()


RENDERS = os.environ.get("RENDERS", "all")
shoot_catalog("Preview.png", -12, (1.6, -15, 6.2), samples=48)
if RENDERS == "all":
    shoot_catalog("Front.png", 0, (0, -15, 1.2))
    shoot_catalog("Back.png", 0, (0, 15, 1.2))
    shoot_catalog("Side.png", 0, (15, 0, 1.2))
    shoot_catalog("Alternate.png", -12, (-4.6, 15, 6.2))
r = catalog_stage(FINAL, 0, (1.2, -15, 3.0), samples=48)
zoom(HEAD, 1.7, V(2.4, -9.0, 2.0))
render(ROOT / "CloseupHead.png")
zoom(BLADE_MID, 2.9, V(1.2, -9.0, 3.0))
render(ROOT / "CloseupBlade.png")
if RENDERS == "all":
    zoom(V(0, 0, 2.5 * SCALE), 2.2, V(3.0, -9.0, 2.0))
    render(ROOT / "CloseupShaft.png")
r()

if RENDERS == "all":
    # scale shot: a 5-stud grey R15 block figure beside the scythe
    fig_bm = new_bm()
    FX = 2.3
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

    # readability: the catalogue view at ~game size, upscaled with hard pixels
    r = catalog_stage(FINAL, -12, (1.6, -15, 6.2), samples=24, res=160)
    render(OUT / "_readability_small.png")
    r()
    im = bpy.data.images.load(str(OUT / "_readability_small.png"))
    a = np.empty(160 * 160 * 4, np.float32)
    im.pixels.foreach_get(a)
    a = np.repeat(np.repeat(a.reshape(160, 160, 4), 5, axis=0), 5, axis=1)
    big = bpy.data.images.new("Readability", 800, 800, alpha=False)
    big.pixels.foreach_set(a.ravel())
    big.filepath_raw = str(ROOT / "Readability.png")
    big.file_format = "PNG"
    big.save()
    bpy.data.images.remove(im)
    bpy.data.images.remove(big)
    os.remove(OUT / "_readability_small.png")


# hero beauty shot: dark stage, cool key, strong crimson rims, heavier bloom (Cycles)
def hero(name, cam_loc, target, lens=58, res=(1200, 1400), samples=96):
    clear_stage()
    w = scene.world
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.016, 0.019, 0.03, 1)
    cd = bpy.data.cameras.new("Hero camera")
    cam = bpy.data.objects.new("Hero camera", cd)
    REVIEW.objects.link(cam)
    cd.lens = lens
    cam.location = cam_loc
    cam.rotation_euler = (target - cam_loc).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    for nm, loc, col, en, sz in (("Hero key", V(-4, -6, 8), (0.78, 0.86, 1.0), 1150, 4),
                                  ("Hero rim crimson", V(4, 6, 6), (1.0, 0.12, 0.18), 1700, 3),
                                  ("Hero rim steel", V(-5, 5, 5), (0.6, 0.72, 1.0), 900, 3),
                                  ("Hero fill violet", V(2, -5, 0.5), (0.55, 0.45, 1.0), 180, 4)):
        ld = bpy.data.lights.new(nm, "AREA")
        ld.color = col
        ld.energy = en
        ld.size = sz
        lo = bpy.data.objects.new(nm, ld)
        REVIEW.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = (V(-0.8, 0, 3.0) - loc).to_track_quat("-Z", "Y").to_euler()
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


if RENDERS == "all":
    hero("Hero.png", V(1.96, -7.28, 1.62), V(-0.75, 0, 2.55), lens=50)

# saved file opens on the front review stage
catalog_stage(FINAL, 0, (0, -15, 1.2))
for o in FINAL:
    o.select_set(True)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "Model.blend"))
log("blend saved")


# ---------------------------------------------------------------------------
# Contact sheet + catalogue comparison (Blender-composited image planes with labels)
# ---------------------------------------------------------------------------
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
compose([(ROOT / "Preview.png", "Reaper's Scythe (Godly, new)"), (ASSETS / "32-excalibur" / "Preview.png", "Excalibur"),
         (ASSETS / "31-mjolnir" / "Preview.png", "Mjolnir"), (ASSETS / "34-medusas-head" / "Preview.png", "Medusa's Head")],
        4, 700, ROOT / "Compare_Catalog.png", title="Catalogue framing: Godly scythe beside the current top-tier weapons")
if RENDERS == "all":
    compose([(ROOT / "Preview.png", "Preview (catalogue 3/4)"), (ROOT / "Front.png", "Front"), (ROOT / "Back.png", "Back"),
             (ROOT / "Side.png", "Side"), (ROOT / "Alternate.png", "Alternate (back 3/4)"),
             (ROOT / "CloseupHead.png", "Close-up: head"), (ROOT / "CloseupBlade.png", "Close-up: blade"),
             (ROOT / "CloseupShaft.png", "Close-up: shaft, chain, lantern"), (ROOT / "Scale.png", "Scale: 5-stud R15 block figure"),
             (ROOT / "Hero.png", "Hero (dramatic lighting)"), (ROOT / "Readability.png", "Readability: 160 px render, pixel-doubled"),
             (ROOT / "BaseColor.png", "BaseColor.png (1024, baked)")],
            4, 560, ROOT / "Sheet.png", title="Reaper's Scythe - Godly style sample (Blender renders, Studio untested)")


# ---------------------------------------------------------------------------
# Validation (reimport both exports into a fresh file)
# ---------------------------------------------------------------------------
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
}
report["notes"] = [
    "Non-manifold edge counts are expected: the textured mesh is many closed parts that overlap by design "
    "(wraps on the shaft, bones on the blade spine, trim on the hood), and booleaned runes/sockets meet the bevels.",
    "Studio import, Neon look and in-game scale are untested (no Studio access in this task).",
]
(ROOT / "validation.json").write_text(json.dumps(report, indent=1))
log("VALIDATION", json.dumps(report["checks"]), "tris", report["total_triangles"])
log("DONE")
