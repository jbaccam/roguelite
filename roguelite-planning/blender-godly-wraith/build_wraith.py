"""Crimson Wraith: the helper the Godly Reaper's Scythe raises from enemies it kills.

Self-contained generator (pipeline pieces copied from weapon-models/godly/reapers-scythe/
build_reapers_scythe.py, never imported). Run in background Blender 5.2 only:
  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 --python build_wraith.py

Environment switches (all optional):
  MODE=quick   build + flat-colour review shots only (no UVs, bake or exports)
  MODE=full    (default) build, bake BaseColor.png, export FBX/GLB, reports, previews, wraith.blend
  OUT=<dir>    where quick-mode shots go (default: <this folder>/wip)
  SHOTS=a,b    quick mode: front34, side, back, game, claw

Design: a floating hooded reaper-wraith in the scythe's language (hooded skull, angry brow, glowing
crimson eyes, bone spikes, crimson lining, a thin gold hood rim). Open fanged jaw, broad hunched
shroud with bone spikes, an open rib cage with a glowing soul core, two long bony arms ending in
oversized four-talon hooked claws, and a ragged tail of sharp tatters with glowing edges.

Axes: Blender z up, the wraith faces -y, its right hand is at -x. 1 Blender unit = 1 stud.
Studio = (-x, z, y) of Blender, so the face looks along Studio -Z.
Model origin (0,0,0) = body axis at chest height (hover pivot); arms have their origin at the shoulder.
"""
import bpy, bmesh, math, json, os, sys, time
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from pathlib import Path

T0 = time.time()
ROOT = Path(__file__).resolve().parent
NAME = "Wraith"
MODE = os.environ.get("MODE", "full")
OUT = Path(os.environ.get("OUT", str(ROOT / "wip")))
SHOTS = [s for s in os.environ.get("SHOTS", "front34,side,back,game,claw").split(",") if s]
TEX_SIZE, BAKE_RES = 512, 1024
TARGET_HEIGHT = 4.5
BLEED_K, BLEED_STRENGTH = 0.18, 0.85
PREV = ROOT / "previews"
if MODE == "quick":
    OUT.mkdir(parents=True, exist_ok=True)
else:
    for d in ("exports/fbx", "exports/glb", "textures", "previews"):
        (ROOT / d).mkdir(parents=True, exist_ok=True)


def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)


def V(*a):
    return Vector(a)


# ---------------------------------------------------------------------------
# Palette (sRGB). flat: quick colour. ramp: painterly noise ramp. edge: bevel highlight tint.
# Near-black with a crimson cast, crimson lining, the scythe's bone ivory, brown-shaded gold.
# ---------------------------------------------------------------------------
PAL = [
    ("Shroud", (26, 12, 19), [(0.26, (10, 6, 13)), (0.5, (25, 10, 18)), (0.78, (48, 15, 26))], (112, 34, 50)),
    ("Lining", (96, 12, 30), [(0.3, (54, 5, 17)), (0.55, (98, 12, 30)), (0.8, (142, 26, 44))], (222, 96, 104)),
    ("Bone", (232, 218, 184), [(0.3, (196, 168, 124)), (0.54, (236, 218, 182)), (0.8, (255, 246, 224))], (255, 255, 244)),
    ("Socket", (20, 8, 14), [(0.4, (10, 4, 10)), (0.75, (32, 12, 22))], (70, 30, 40)),
    ("Gold", (212, 146, 32), [(0.3, (126, 70, 16)), (0.52, (210, 144, 32)), (0.8, (248, 210, 92))], (255, 236, 160)),
]
M_SHROUD, M_LINING, M_BONE, M_SOCK, M_GOLD = range(len(PAL))
GLOW = (255, 22, 52)        # Roblox Neon crimson (the scythe's glow)
CORE = (255, 150, 128)      # Roblox Neon white-hot core


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


def qbez(a, b, c, t):
    return a * (1 - t) ** 2 + b * (2 * t * (1 - t)) + c * (t * t)


# ---------------------------------------------------------------------------
# bmesh primitives (from the scythe pipeline)
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


def tube(bm, pts, radii, sides=8, mat=0, flat=1.0, phase=0.0, up=V(0, 1, 0), caps=True, twist=0.0):
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
        ang = twist * k / max(1, len(pts) - 1)
        ca, sa = math.cos(ang), math.sin(ang)
        rings.append([p + N[k] * (a * ca - b * sa) * ra + B[k] * (a * sa + b * ca) * rb for a, b in sec])
    return loft(bm, rings, mat=mat, caps=caps)


def lathe(bm, prof, sides=8, M=None, mat=0, phase=None, sy=1.0):
    """Surface of revolution about local +z; prof = [(radius, z)]."""
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


def mirror_x(bm):
    """Add an exact mirror copy (x -> -x) of everything in bm: paired parts are built on the
    wraith's right (-x) and mirrored, so left and right match vertex for vertex."""
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    ret = bmesh.ops.duplicate(bm, geom=geom)
    vs = [e for e in ret["geom"] if isinstance(e, bmesh.types.BMVert)]
    fs = [e for e in ret["geom"] if isinstance(e, bmesh.types.BMFace)]
    for v in vs:
        v.co.x = -v.co.x
    bmesh.ops.reverse_faces(bm, faces=fs)


def mx(v):
    return V(-v.x, v.y, v.z)


# ---------------------------------------------------------------------------
# Scene, materials, objects
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


GLOW_MAT = emit_mat(f"{NAME}_Neon", GLOW, 0.8)
CORE_MAT = emit_mat(f"{NAME}_NeonCore", CORE, 1.15)
GROUPS = {"body": [], "arm": [], "glow": [], "core": []}


def new_bm():
    return bmesh.new()


def make_obj(name, bm, kind="tex", grp="body", coll=None):
    bm.normal_update()
    me = bpy.data.meshes.new(name + "_Geo")
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
        p.use_smooth = False          # faceted, like the scythe's hood and skull
    ob = bpy.data.objects.new(name, me)
    (coll or (WORK if kind == "cut" else ASSET)).objects.link(ob)
    ob["kind"] = kind
    if kind == "cut":
        ob.display_type = "WIRE"
        ob.hide_render = True
    elif kind in ("glow", "core"):
        GROUPS[kind].append(ob)
    elif kind == "tex":
        GROUPS[grp].append(ob)
    return ob


def add_bool(ob, cutter, op="DIFFERENCE"):
    m = ob.modifiers.new(f"Bool_{cutter.name}", "BOOLEAN")
    m.operation = op
    m.solver = "EXACT"
    m.object = cutter
    m.material_mode = "INDEX"
    m.use_self = False
    m.use_hole_tolerant = True
    return m


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


def bvh_of(ob):
    return BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())


def ray(bvhs, o, d):
    best = None
    for b in bvhs:
        hit, nrm, idx, dist = b.ray_cast(o, d)
        if hit is not None and (best is None or dist < best[2]):
            best = (hit, nrm, dist)
    return best


# ---------------------------------------------------------------------------
# Layout (studs, before the final normalisation to 4.5 studs tall)
# ---------------------------------------------------------------------------
SK = V(0.0, -0.30, 0.98)          # skull centre: head thrust forward and low between the shoulders
HOOD_C = SK + V(0, 0.03, 0)
P_SH = V(-0.78, 0.04, 0.34)       # right shoulder pivot (inside the shroud)
ELBOW = V(-1.54, -0.20, -0.09)
WRIST = V(-1.82, -0.78, -0.30)
CORE_C = V(0.0, -0.16, 0.0)       # soul core behind the ribs
TAIL_TIP = V(0.0, 0.64, -2.74)
PTS = {"core": CORE_C, "tail_tip": TAIL_TIP}
SPIKE_TIPS = []


def skull_front_y(x, z):
    prof = [(-0.19, 0.17), (-0.10, 0.26), (0.02, 0.30), (0.13, 0.305), (0.24, 0.27), (0.32, 0.19)]
    r = float(np.interp(z, [p[0] for p in prof], [p[1] for p in prof]))
    return -math.sqrt(max(r * r - x * x, 0.0)) * 0.95


def build_skull():
    M = Matrix.Translation(SK)
    bm = new_bm()
    prof = [(0.0, -0.17), (0.15, -0.20), (0.24, -0.10), (0.30, 0.02), (0.305, 0.13), (0.27, 0.24), (0.19, 0.32),
            (0.09, 0.365), (0.0, 0.375)]
    lathe(bm, prof, sides=14, M=M, mat=M_BONE, sy=0.95, phase=0.0)
    cranium = make_obj("Cranium", bm)
    half = new_bm()
    # heavy angry brow: low at the centre, rising to the temples
    bpts = [V(0.03, 0, 0.03), V(-0.08, 0, 0.068), V(-0.17, 0, 0.125), V(-0.27, 0, 0.175)]
    bpts = [M @ V(p.x, skull_front_y(p.x, p.z) + 0.008, p.z) for p in bpts]
    tube(half, bpts, [(0.046, 0.052), (0.048, 0.054), (0.042, 0.046), (0.024, 0.028)], sides=6, mat=M_BONE, up=V(0, 0, 1))
    # upper fangs, canine longest
    for x, L in ((-0.03, 0.08), (-0.08, 0.135), (-0.13, 0.085)):
        y = skull_front_y(x, -0.2) + 0.035
        lathe(half, [(0.0, -L), (0.022, -0.03), (0.029, 0.012)], sides=4, phase=math.pi / 4,
              M=Matrix.Translation(M @ V(x, y, -0.20)), mat=M_BONE)
    # lower jaw, dropped open and jutting forward, with upward fangs
    n0 = len(half.verts)
    jp = [V(0.03, -0.215, -0.365), V(-0.17, -0.15, -0.34), V(-0.21, 0.02, -0.25)]
    tube(half, [M @ p for p in jp], [(0.062, 0.042), (0.056, 0.037), (0.046, 0.03)], sides=6, mat=M_BONE, up=V(0, 0, 1))
    for x, L in ((-0.03, 0.065), (-0.085, 0.11), (-0.135, 0.06)):
        y = -0.205 + 0.06 * (x / 0.17) ** 2
        lathe(half, [(0.028, -0.01), (0.021, 0.03), (0.0, L)], sides=4, phase=math.pi / 4,
              M=Matrix.Translation(M @ V(x, y, -0.33)), mat=M_BONE)
    hinge = M @ V(0, 0.04, -0.20)
    JR = Matrix.Translation(V(0, -0.07, -0.01)) @ Matrix.Translation(hinge) @ Matrix.Rotation(math.radians(28), 4, "X") \
        @ Matrix.Translation(-hinge)
    half.verts.ensure_lookup_table()
    for v in half.verts[n0:]:
        v.co = JR @ v.co
    mirror_x(half)
    # dark throat behind the teeth
    box(half, M @ V(0, 0.07, -0.33), (0.27, 0.24, 0.17), mat=M_SOCK)
    make_obj("SkullDetail", half)
    # sockets (slanted for an angry glare) and nose, cut with booleans
    cut = new_bm()
    c = V(-0.122, -0.40, 0.03)
    R = Matrix.Rotation(math.radians(24), 4, "Y")
    hexp = [(math.cos(math.pi / 6 + k * math.pi / 3) * 0.112, math.sin(math.pi / 6 + k * math.pi / 3) * 0.09) for k in range(6)]
    loft(cut, [[M @ (c + (R @ V(u, 0, v))) for u, v in hexp], [M @ (c + (R @ V(u * 0.8, 0.30, v * 0.8))) for u, v in hexp]], mat=M_SOCK)
    mirror_x(cut)
    tri = [(0.0, -0.035), (0.042, 0.04), (-0.042, 0.04)]
    loft(cut, [[M @ V(u, -0.40, -0.09 + v) for u, v in tri], [M @ V(u * 0.6, -0.16, -0.09 + v * 0.6) for u, v in tri]], mat=M_SOCK)
    add_bool(cranium, make_obj("SkullCutter", cut, kind="cut"))
    # glowing eyes deep in the sockets + white-hot pupils, and a glow in the open mouth
    g, cbm = new_bm(), new_bm()
    e = V(-0.118, skull_front_y(-0.118, 0.03) + 0.075, 0.025)
    RX = Matrix.Rotation(math.radians(90), 4, "X")
    lathe(g, [(0.0, -0.045), (0.064, -0.02), (0.077, 0.01), (0.052, 0.042), (0.0, 0.054)], sides=6,
          M=Matrix.Translation(M @ e) @ RX, phase=0.0)
    lathe(cbm, [(0.0, -0.02), (0.036, 0.0), (0.0, 0.032)], sides=6, M=Matrix.Translation(M @ (e + V(0, -0.052, 0.004))) @ RX)
    mirror_x(g)
    mirror_x(cbm)
    lathe(g, [(0.0, -0.025), (0.125, -0.008), (0.11, 0.02), (0.0, 0.03)], sides=8, sy=0.55,
          M=Matrix.Translation(M @ V(0, -0.05, -0.37)) @ RX)
    make_obj("Eyes_Glow", g, kind="glow")
    make_obj("Eyes_Core", cbm, kind="core")
    PTS["eye_R"] = M @ e
    PTS["eye_L"] = mx(M @ e)
    return cranium


def build_hood():
    """Big pointed cowl: one closed shell (shroud outside, crimson lining inside), its peak swept
    back, its back hem draped down onto the mantle, a gothic-arch face opening and a thin gold rim."""
    outer = [(0.58, -0.46), (0.58, -0.28), (0.565, -0.08), (0.525, 0.12), (0.455, 0.31), (0.345, 0.48), (0.215, 0.62),
             (0.095, 0.75), (0.0, 0.87)]
    inner = [(0.0, 0.75), (0.07, 0.66), (0.18, 0.535), (0.29, 0.415), (0.39, 0.275), (0.455, 0.10), (0.49, -0.08),
             (0.505, -0.27), (0.515, -0.43)]
    sides = 16
    rings = []
    for r, z in outer + inner:
        dy = 0.34 * smoothstep(0.15, 0.87, z) ** 1.4
        if r <= 1e-6:
            rings.append([HOOD_C + V(0, dy + 0.04, z)])
            continue
        ring = []
        for s in range(sides):
            a = 2 * math.pi * s / sides - math.pi / 2
            fold = 0.05 * (1 - smoothstep(-0.45, 0.3, z))
            rr = r * (1 + fold * math.cos(6 * (a + math.pi / 2)))
            ring.append(HOOD_C + V(rr * math.cos(a), rr * math.sin(a) * 0.97 + dy, z))
        rings.append(ring)
    for ring, w in ((rings[0], 1.0), (rings[-1], 1.0), (rings[1], 0.5), (rings[-2], 0.5)):
        for s, p in enumerate(ring):
            a = 2 * math.pi * s / sides - math.pi / 2
            back = max(0.0, math.sin(a))
            p.z -= w * (0.22 * back ** 1.5 + (0.11 if (s % 2 == 0 and w == 1.0) else 0.0))
            k = 1.0 + w * (0.06 * back + (0.04 if s % 2 == 0 else 0.0))
            p.x = HOOD_C.x + (p.x - HOOD_C.x) * k
            p.y = HOOD_C.y + (p.y - HOOD_C.y) * k
    bm = new_bm()
    vr = [[bm.verts.new(p) for p in r] for r in rings]
    faces = []
    nO = len(outer)
    for k in range(len(vr)):
        A, B = vr[k], vr[(k + 1) % len(vr)]
        if len(A) == 1 and len(B) == 1:
            continue
        mat = M_SHROUD if k < nO - 1 else M_LINING
        for s in range(sides):
            s2 = (s + 1) % sides
            if len(B) == 1:
                f = bm.faces.new([A[s], A[s2], B[0]])
            elif len(A) == 1:
                f = bm.faces.new([A[0], B[s2], B[s]])
            else:
                f = bm.faces.new([A[s], A[s2], B[s2], B[s]])
            f.material_index = mat
            faces.append(f)
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    hood = make_obj("Hood", bm)
    cut = new_bm()
    W, Za, Zb = 0.34, 0.45, -0.95
    right = [(W, Zb), (W, -0.1), (W * 0.99, 0.06), (W * 0.9, 0.2), (W * 0.72, 0.31), (W * 0.44, 0.40), (0.0, Za)]
    arch = right + [(-x, z) for x, z in reversed(right[:-1])]
    loft(cut, [[SK + V(x, -0.85, z) for x, z in arch], [SK + V(x * 0.96, -0.02, z) for x, z in arch]], mat=M_LINING)
    cutter = make_obj("HoodCutter", cut, kind="cut")
    # gold rim on the opening: raycast onto the uncut outer surface
    bpy.context.view_layer.update()
    bvh = bvh_of(hood)
    add_bool(hood, cutter)
    poly = np.array(arch[1:-1])
    seg = np.linalg.norm(np.diff(poly, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    tpts = []
    for sdist in np.linspace(0, cum[-1], 20):
        x = float(np.interp(sdist, cum, poly[:, 0]))
        z = float(np.interp(sdist, cum, poly[:, 1]))
        if z < -0.36:
            continue
        hit, nrm, idx, dist = bvh.ray_cast(SK + V(x * 1.04, -2.0, z), V(0, 1, 0))
        if hit is not None:
            tpts.append(hit + V(0, -0.006, 0))
    tb = new_bm()
    rad = [0.028] * len(tpts)
    rad[0] = rad[-1] = 0.012
    tube(tb, tpts, rad, sides=5, mat=M_GOLD, up=V(0, 1, 0))
    # the scythe's gold medallion with a glowing eye-rune, on the back of the cowl (the game camera sees it)
    o = SK + V(0, 2.0, 0.24)
    hit, nrm, idx, dist = bvh.ray_cast(o, V(0, -1, 0))
    g = new_bm()
    if hit is not None:
        Mm = Matrix.Translation(hit + nrm * 0.004) @ nrm.to_track_quat("Z", "Y").to_matrix().to_4x4()
        lathe(tb, [(0.0, -0.03), (0.12, -0.03), (0.13, 0.0), (0.115, 0.022), (0.0, 0.026)], sides=8, M=Mm, mat=M_GOLD,
              phase=math.pi / 8)
        ring = [(0, 0.085), (0.06, 0), (0, -0.085), (-0.06, 0)]
        inner = [(0, 0.05), (0.032, 0), (0, -0.05), (-0.032, 0)]
        for k in range(4):
            poly = [ring[k], ring[(k + 1) % 4], inner[(k + 1) % 4], inner[k]]
            loft(g, [[Mm @ V(x, y, 0.02) for x, y in poly], [Mm @ V(x, y, 0.04) for x, y in poly]])
        slit = ((-0.009, 0.034), (0.009, 0.034), (0.009, -0.034), (-0.009, -0.034))
        loft(g, [[Mm @ V(x, y, 0.02) for x, y in slit], [Mm @ V(x, y, 0.042) for x, y in slit]])
    make_obj("HoodRune_Glow", g, kind="glow")
    make_obj("HoodTrim", tb)
    PTS["hood_tip"] = HOOD_C + V(0, 0.38, 0.87)
    return hood


def sup(a, rx, ry, e=0.77):
    c, s = math.cos(a), math.sin(a)
    return math.copysign(abs(c) ** e, c) * rx, math.copysign(abs(s) ** e, s) * ry


def build_mantle():
    """Broad hunched shoulder shroud: a closed thick shell (shroud outside, lining inside), squared
    shoulders, a raised hump at the back and a hem of sharp hanging points."""
    sides = 20
    spec_out = [(0.30, 0.30, 0.82, 0.10, 0), (0.64, 0.45, 0.67, 0.08, 0), (0.90, 0.55, 0.50, 0.06, 0),
                (1.00, 0.59, 0.28, 0.05, 0), (1.03, 0.60, 0.03, 0.05, 1)]
    spec_in = [(0.95, 0.53, 0.06, 0.05, 1), (0.93, 0.52, 0.30, 0.05, 0), (0.82, 0.47, 0.52, 0.06, 0),
               (0.56, 0.39, 0.68, 0.08, 0), (0.26, 0.26, 0.80, 0.10, 0)]
    rings = []
    for rx, ry, z, cy, hem in spec_out + spec_in:
        ring = []
        for s in range(sides):
            a = 2 * math.pi * s / sides - math.pi / 2
            fold = 1 + 0.035 * math.cos(8 * (a + math.pi / 2)) * smoothstep(0.6, 0.1, z)
            x, y = sup(a, rx * fold, ry * fold)
            zz = z
            if z > 0.4:
                zz += 0.12 * max(0.0, math.sin(a)) * smoothstep(0.4, 0.7, z)
            if hem:
                zz -= 0.16 * math.cos(a) ** 2
                if s % 2 == 0:
                    zz -= 0.25
                    x *= 1.06
                    y *= 1.06
            ring.append(V(x, y + cy, zz))
        rings.append(ring)
    bm = new_bm()
    vr = [[bm.verts.new(p) for p in r] for r in rings]
    nO = len(spec_out)
    faces = []
    for k in range(len(vr)):
        A, B = vr[k], vr[(k + 1) % len(vr)]
        mat = M_SHROUD if k < nO else M_LINING
        for s in range(sides):
            s2 = (s + 1) % sides
            f = bm.faces.new([A[s], A[s2], B[s2], B[s]])
            f.material_index = mat
            faces.append(f)
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return make_obj("Mantle", bm)


TORSO_SPEC = [(0.30, 0.26, 0.62, 0.08), (0.50, 0.37, 0.45, 0.07), (0.60, 0.42, 0.20, 0.06), (0.58, 0.42, -0.10, 0.05),
              (0.48, 0.38, -0.45, 0.07), (0.36, 0.31, -0.85, 0.13), (0.28, 0.25, -1.25, 0.23), (0.21, 0.20, -1.65, 0.35),
              (0.14, 0.14, -2.05, 0.47), (0.075, 0.08, -2.40, 0.56)]
TORSO_RINGS = []


def build_torso():
    """Shroud body tapering into the tail; below the waist the section turns star-shaped so the tail
    reads as torn strips with sharp ridges."""
    sides = 16
    for rx, ry, z, cy in TORSO_SPEC:
        st = 0.30 * smoothstep(-0.5, -1.6, z)
        ring = []
        for s in range(sides):
            a = 2 * math.pi * s / sides - math.pi / 2
            m = (1 + (st if s % 2 else -0.45 * st)) * (1 + 0.03 * math.cos(6 * (a + math.pi / 2)))
            x, y = sup(a, rx * m, ry * m, e=0.85)
            ring.append(V(x, y + cy, z))
        TORSO_RINGS.append(ring)
    bm = new_bm()
    loft(bm, TORSO_RINGS + [TAIL_TIP], mat=M_SHROUD)
    return make_obj("Torso", bm)


VCUT = [(0.0, -0.66), (0.17, -0.38), (0.26, -0.08), (0.31, 0.24), (0.36, 0.52), (0.46, 0.90)]


def build_chest(mantle, torso):
    """Open the shroud in a V over the chest (lining-coloured edges, dark back wall), fill it with
    hooked ribs around a glowing soul core."""
    cut = new_bm()
    poly = VCUT + [(-x, z) for x, z in reversed(VCUT[1:])]
    faces = loft(cut, [[V(x, -1.4, z) for x, z in poly], [V(x, -0.10, z) for x, z in poly]], mat=M_LINING)
    faces[-1].material_index = M_SOCK
    cutter = make_obj("ChestCutter", cut, kind="cut")
    add_bool(mantle, cutter)
    add_bool(torso, cutter)
    bm = new_bm()
    for z, hw in ((0.30, 0.31), (0.10, 0.28), (-0.10, 0.245), (-0.30, 0.19)):
        pts = [V(-(hw + 0.06), -0.13, z + 0.03), V(-hw * 0.95, -0.27, z), V(-hw * 0.58, -0.335, z - 0.05), V(-0.07, -0.33, z - 0.10)]
        tube(bm, pts, [0.042, 0.04, 0.034, 0.0], sides=4, mat=M_BONE, up=V(0, 0, 1))
    mirror_x(bm)
    # neck vertebrae column from the skull into the chest
    tube(bm, [SK + V(0, 0.10, -0.14), V(0, -0.13, 0.62), V(0, -0.10, 0.38)], [0.075, 0.068, 0.058], sides=6, mat=M_BONE,
         up=V(1, 0, 0))
    make_obj("Ribs", bm)
    g, c = new_bm(), new_bm()
    lathe(g, [(0.0, -0.20), (0.12, -0.09), (0.155, 0.02), (0.10, 0.12), (0.0, 0.22)], sides=8, sy=0.8,
          M=Matrix.Translation(CORE_C), phase=math.pi / 8)
    lathe(c, [(0.0, -0.095), (0.066, -0.02), (0.072, 0.02), (0.0, 0.105)], sides=6, sy=0.8,
          M=Matrix.Translation(CORE_C + V(0, -0.09, 0)), phase=math.pi / 6)
    make_obj("SoulCore_Glow", g, kind="glow")
    make_obj("SoulCore_Core", c, kind="core")


TATTERS = [  # (start inside the body, control, needle tip, width, thickness)
    (V(-0.24, -0.22, -0.50), V(-0.38, -0.38, -1.05), V(-0.42, -0.30, -1.62), 0.17, 0.05),
    (V(-0.40, 0.02, -0.40), V(-0.66, 0.02, -1.05), V(-0.80, 0.32, -1.78), 0.19, 0.055),
    (V(-0.24, 0.28, -0.55), V(-0.44, 0.64, -1.25), V(-0.48, 1.02, -2.08), 0.18, 0.05),
]


def build_tatters():
    """Sharp torn strips (diamond section, needle tips) trailing from the hips, glow on both edges."""
    bm, g = new_bm(), new_bm()
    prof = [0.85, 1.0, 0.95, 0.80, 0.58, 0.32, 0.0]
    gr = [0.008, 0.024, 0.026, 0.02, 0.0]
    n = len(prof)
    for p0, p1, p2, w, th in TATTERS:
        pts = [qbez(p0, p1, p2, k / (n - 1)) for k in range(n)]
        radial = V(p0.x, p0.y - 0.05, 0).normalized()
        T, N, B = frames(pts, radial)
        tube(bm, pts, [(w * q, th * q) for q in prof], sides=4, mat=M_SHROUD, up=radial)
        for sgn in (1, -1):
            gp = [pts[k] + N[k] * (sgn * (w * prof[k] * 0.97 + 0.008)) for k in range(2, n)]
            tube(g, gp, gr, sides=3, up=radial)
    mirror_x(bm)
    mirror_x(g)
    # glow lines down the tail's four outer ridges (back pair is what the game camera sees)
    for s in (9, 13):
        line = []
        for ring, (rx, ry, z, cy) in zip(TORSO_RINGS, TORSO_SPEC):
            if z <= -0.8:
                p = ring[s]
                line.append(p + (p - V(0, cy, z)).normalized() * 0.012)
        line.append(TAIL_TIP)
        rad = [0.010] + [0.026] * (len(line) - 3) + [0.016, 0.0]
        tb = new_bm()
        tube(tb, line, rad, sides=3, up=V(0, 0, 1))
        mirror_x(tb)
        tmp = bpy.data.meshes.new("tmp")
        tb.to_mesh(tmp)
        tb.free()
        g.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    make_obj("Tatters", bm)
    make_obj("Tatters_Glow", g, kind="glow")


def spike(bm, base, d, L, r0, up=V(1, 0, 0), sides=6, lift=0.10):
    pts = [base, base + d * (L * 0.35), base + d * (L * 0.7) + V(0, 0, 0.04 * L), base + d * L + V(0, 0, lift * L)]
    tube(bm, pts, [r0, r0 * 0.78, r0 * 0.45, 0.0], sides=sides, mat=M_BONE, up=up)
    return pts[-1]


def build_spikes(hood, mantle, torso):
    """Bone spikes down the spine and on the shoulders, the scythe's bone-spine language."""
    bpy.context.view_layer.update()
    bvhs = [bvh_of(o) for o in (hood, mantle, torso)]
    bm = new_bm()
    for z, L in ((0.50, 0.64), (0.18, 0.58), (-0.16, 0.48), (-0.50, 0.36)):
        r = ray(bvhs, V(0, 3, z), V(0, -1, 0))
        if r is None:
            continue
        hit, nrm = r[0], r[1]
        d = (nrm * 0.5 + V(0, 0.3, 0.72)).normalized()
        SPIKE_TIPS.append(spike(bm, hit - nrm * 0.08, d, L, 0.105 * (L / 0.5) ** 0.5, lift=0.16))
    half = new_bm()
    tips = []
    for x, y, L in ((-0.62, 0.20, 0.58), (-0.40, 0.34, 0.42)):
        r = ray(bvhs, V(x, y, 3), V(0, 0, -1))
        if r is None:
            continue
        hit, nrm = r[0], r[1]
        d = (nrm * 0.5 + V(-0.30, 0.38, 0.8)).normalized()
        tips.append(spike(half, hit - nrm * 0.07, d, L, 0.095 * (L / 0.5) ** 0.5, up=V(0, 1, 0), lift=0.14))
    mirror_x(half)
    SPIKE_TIPS.extend(tips + [mx(t) for t in tips])
    tmp = bpy.data.meshes.new("tmp")
    half.to_mesh(tmp)
    half.free()
    bm.from_mesh(tmp)
    bpy.data.meshes.remove(tmp)
    make_obj("Spikes", bm)


def talon(bm, base, d, curl, L, r0, nseg=6, bend=1.75):
    """Hooked claw: straight at the root, curling hard toward the palm side, needle tip.
    Diamond section, taller in the curl plane than it is wide, so both curves carry a sharp keel."""
    curl = (curl - d * curl.dot(d)).normalized()
    lat = d.cross(curl).normalized()
    p = base - d * 0.03
    pts = [p.copy()]
    for k in range(1, nseg + 1):
        phi = bend * ((k - 0.5) / nseg) ** 1.5
        p = p + (d * math.cos(phi) + curl * math.sin(phi)) * (L / nseg)
        pts.append(p.copy())
    prof = [1.0, 0.97, 0.86, 0.70, 0.52, 0.30, 0.0]
    tube(bm, pts, [(r0 * k, r0 * 0.7 * k) for k in prof], sides=4, mat=M_BONE, up=lat)
    return pts[-1]


def build_arm():
    """Right arm (-x), one piece from the shoulder ball to the claw tips. The cloth ball centred on
    the pivot keeps the shoulder covered through any +-40 degree swing; the sleeve hides the root."""
    P, E, Wr = P_SH, ELBOW, WRIST
    u1 = (E - P).normalized()
    uf = (Wr - E).normalized()
    cloth, bone = new_bm(), new_bm()
    lathe(cloth, [(0.0, -0.20), (0.14, -0.145), (0.20, 0.0), (0.14, 0.145), (0.0, 0.20)], sides=8,
          M=Matrix.Translation(P), mat=M_SHROUD)
    tube(cloth, [P - u1 * 0.04, P + u1 * 0.10, P + u1 * 0.26, P + u1 * 0.40, P + u1 * 0.50],
         [0.17, 0.21, 0.225, 0.19, 0.11], sides=8, mat=M_SHROUD, up=V(0, 0, 1))
    for t, L in ((0.10, 0.50), (0.25, 0.44), (0.38, 0.34)):
        s0 = P + u1 * t + V(0, 0, -0.14)
        pts = [qbez(s0, s0 + V(0, 0.08, -L * 0.5), s0 + V(0.03, 0.20, -L), k / 4) for k in range(5)]
        upv = u1.cross((pts[1] - pts[0]).normalized())
        tube(cloth, pts, [(0.075, 0.025), (0.08, 0.024), (0.06, 0.02), (0.035, 0.012), (0.0, 0.0)], sides=4,
             mat=M_SHROUD, up=upv)
    tube(bone, [P + u1 * 0.30, P + u1 * 0.55, E - u1 * 0.05], [0.104, 0.092, 0.088], sides=6, mat=M_BONE)
    lathe(bone, [(0.0, -0.125), (0.095, -0.085), (0.125, 0.0), (0.095, 0.085), (0.0, 0.125)], sides=6,
          M=Matrix.Translation(E), mat=M_BONE)
    spike(bone, E, V(-0.30, 0.82, 0.48).normalized(), 0.48, 0.088, sides=5)
    tube(bone, [E + uf * 0.04, E + uf * 0.32, Wr - uf * 0.02], [0.094, 0.084, 0.074], sides=6, mat=M_BONE)
    tube(cloth, [Wr - uf * 0.22, Wr - uf * 0.12, Wr - uf * 0.02, Wr + uf * 0.03], [0.09, 0.13, 0.135, 0.095], sides=8,
         mat=M_SHROUD)
    s0 = Wr - uf * 0.12 + V(0, 0, -0.09)
    pts = [qbez(s0, s0 + V(0, 0.05, -0.14), s0 + V(0.0, 0.15, -0.30), k / 3) for k in range(4)]
    tube(cloth, pts, [(0.06, 0.02), (0.055, 0.018), (0.03, 0.01), (0.0, 0.0)], sides=4, mat=M_SHROUD,
         up=uf.cross((pts[1] - pts[0]).normalized()))
    # hand: palm faces down and inward, four hooked talons fanned open
    f = (uf * 0.35 + V(0, -1, -0.35).normalized() * 0.65).normalized()
    n = V(0.5, 0, -1).normalized()
    n = (n - f * n.dot(f)).normalized()
    lo = n.cross(f).normalized()
    if lo.x > 0:
        lo = -lo
    tube(bone, [Wr - f * 0.03, Wr + f * 0.10, Wr + f * 0.20], [(0.12, 0.072), (0.165, 0.078), (0.16, 0.066)], sides=6,
         mat=M_BONE, up=n)
    tips = []
    for off, ang, L, r0 in ((0.11, 0.55, 0.74, 0.074), (0.0, 0.06, 0.84, 0.08), (-0.11, -0.36, 0.72, 0.074)):
        d = (f * math.cos(ang) + lo * math.sin(ang)).normalized()
        tips.append(talon(bone, Wr + f * 0.17 + lo * off, d, n, L, r0))
    dt = (f * 0.55 - lo * 0.75 + n * 0.20).normalized()
    tips.append(talon(bone, Wr + f * 0.05 - lo * 0.13 + n * 0.02, dt, lo * 0.6 + n * 0.8, 0.56, 0.07))
    make_obj("ArmCloth", cloth, grp="arm")
    make_obj("ArmBone", bone, grp="arm")
    PTS["claw_tip_R"] = tips[1]
    PTS["claw_tip_L"] = mx(tips[1])
    PTS["talons_R"] = tips
    PTS["talons_L"] = [mx(t) for t in tips]


def build_all():
    build_skull()
    hood = build_hood()
    mantle = build_mantle()
    torso = build_torso()
    build_chest(mantle, torso)
    build_tatters()
    build_spikes(hood, mantle, torso)
    build_arm()


build_all()
log("built", sum(len(v) for v in GROUPS.values()), "parts")


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


for o in [o for g in GROUPS.values() for o in g]:
    if o.modifiers:
        apply_mods(o)
    clean_degenerate(o)
for o in list(WORK.objects):
    bpy.data.objects.remove(o, do_unlink=True)


def tri_count(objs):
    tot = {}
    for o in objs:
        o.data.calc_loop_triangles()
        tot[o.name] = len(o.data.loop_triangles)
    return tot


PART_TRIS = tri_count([o for g in GROUPS.values() for o in g])
log("PART TRIS", sorted(PART_TRIS.items(), key=lambda kv: -kv[1]))


def join(objs, name):
    select_only(objs)
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name + "_Geo"
    return ob


body = join(GROUPS["body"], f"{NAME}_Body")
armR = join(GROUPS["arm"], f"{NAME}_ArmR")
glow_ob = join(GROUPS["glow"], f"{NAME}_Glow")
core_ob = join(GROUPS["core"], f"{NAME}_GlowCore")
armL = armR.copy()
armL.data = armR.data.copy()
armL.name = f"{NAME}_ArmL"
armL.data.name = f"{NAME}_ArmL_Geo"
ASSET.objects.link(armL)
_bm = bmesh.new()
_bm.from_mesh(armL.data)
for v in _bm.verts:
    v.co.x = -v.co.x
bmesh.ops.reverse_faces(_bm, faces=_bm.faces[:])
_bm.to_mesh(armL.data)
_bm.free()
for o in (glow_ob, core_ob):
    o.data.materials.clear()
    o.data.materials.append(GLOW_MAT if o is glow_ob else CORE_MAT)
    for p in o.data.polygons:
        p.material_index = 0


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


# ---- normalise to exactly 4.5 studs tall (hood tip to tail tip), scaled about the chest origin
FINAL = [body, armL, armR, glow_ob, core_ob]
_pts = world_bounds(FINAL)
H0 = max(p.z for p in _pts) - min(p.z for p in _pts)
SCALE = TARGET_HEIGHT / H0
for o in FINAL:
    o.data.transform(Matrix.Scale(SCALE, 4))
    o.data.update()
for k in list(PTS):
    PTS[k] = [p * SCALE for p in PTS[k]] if isinstance(PTS[k], list) else PTS[k] * SCALE
SPIKE_TIPS = [p * SCALE for p in SPIKE_TIPS]
PIV = {armR.name: P_SH * SCALE, armL.name: mx(P_SH) * SCALE}
for o in (armR, armL):
    o.data.transform(Matrix.Translation(-PIV[o.name]))
    o.location = PIV[o.name]
bpy.context.view_layer.update()
TRIS = tri_count(FINAL)
log(f"authored height {H0:.3f} -> scale {SCALE:.4f}")
log("TRIS", TRIS, "total", sum(TRIS.values()))


# ---------------------------------------------------------------------------
# Review stage (the scythe's catalogue stage) + arm posing
# ---------------------------------------------------------------------------
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


def point(o, p):
    o.rotation_euler = (Vector(p) - o.location).to_track_quat("-Z", "Y").to_euler()


def catalog_stage(objs, camvec, res=1000, samples=24, ortho_pad=1.18, world=0.0509, floor=True, extra_objs=(), lift=0.4):
    clear_stage()
    saved = {o.name: o.matrix_world.copy() for o in objs}
    coords = world_bounds(objs)
    minz = min(c.z for c in coords)
    for o in objs:
        o.location.z += lift - minz
    bpy.context.view_layer.update()
    coords = world_bounds(list(objs) + list(extra_objs))
    mn = [min(c[i] for c in coords) for i in range(3)]
    mxx = [max(c[i] for c in coords) for i in range(3)]
    center = Vector([(mn[i] + mxx[i]) * 0.5 for i in range(3)])
    extent = max(mxx[2] - mn[2], mxx[0] - mn[0])
    cd = bpy.data.cameras.new("Review camera")
    cam = bpy.data.objects.new("Review camera", cd)
    REVIEW.objects.link(cam)
    cam.location = center + Vector(camvec) * extent / 5
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


def swing_axis(ob, sign_in):
    P = PIV[ob.name]
    tip = PTS["claw_tip_R"] if ob is armR else PTS["claw_tip_L"]
    d = (tip - P).normalized()
    s = V(sign_in * 0.3, -1.0, -0.8).normalized()
    return d.cross(s).normalized()


def pose_arms(deg):
    """Rotate both arms about their shoulder origins: + = claw swipe forward and down."""
    for ob, sgn in ((armR, 1), (armL, -1)):
        ob.matrix_world = Matrix.Translation(PIV[ob.name]) @ Matrix.Rotation(math.radians(deg), 4, swing_axis(ob, sgn))
    bpy.context.view_layer.update()


def game_view(path, res=(1280, 720), samples=16):
    """Roblox-like camera: 70 degree vertical FOV, about 18 studs behind and above."""
    r = catalog_stage(FINAL, (0, 15, 8), samples=samples, lift=2.0)
    cam = STAGE["cam"]
    cam.data.type = "PERSP"
    cam.data.sensor_fit = "VERTICAL"
    cam.data.sensor_height = 24
    cam.data.lens = 12 / math.tan(math.radians(35))
    c = STAGE["center"]
    cam.location = c + V(1.5, 15.5, 8.8).normalized() * 18
    point(cam, c + V(0, 0, -1.0))
    scene.render.resolution_x, scene.render.resolution_y = res
    render(path)
    r()


if MODE == "quick":
    setup_comp(0.4)
    for shot in SHOTS:
        if shot == "front34":
            r = catalog_stage(FINAL, (5.5, -13.5, 5.0), res=800, samples=16)
            render(OUT / "q_front34.png")
            r()
        elif shot == "side":
            r = catalog_stage(FINAL, (15, 0, 1.2), res=700, samples=16)
            render(OUT / "q_side.png")
            r()
        elif shot == "back":
            r = catalog_stage(FINAL, (-5.0, 13.5, 7.0), res=700, samples=16)
            render(OUT / "q_back.png")
            r()
        elif shot == "game":
            game_view(OUT / "q_game.png")
        elif shot == "claw":
            for deg, nm, vec in ((40, "q_claw_fwd_front.png", (5.5, -13.5, 5.0)), (40, "q_claw_fwd_back.png", (-5.0, 13.5, 7.0)),
                                 (-40, "q_claw_up_front.png", (5.5, -13.5, 3.0))):
                pose_arms(deg)
                r = catalog_stage(FINAL, vec, res=700, samples=12)
                render(OUT / nm)
                r()
            pose_arms(0)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "q_wraith.blend"))
    log("QUICK DONE")
    sys.exit(0)


# ===========================================================================
# FULL MODE: UVs, painted masks, bake, export, reports, previews
# ===========================================================================
TEX = [body, armR, armL]
for o in FINAL:
    while o.data.uv_layers:
        o.data.uv_layers.remove(o.data.uv_layers[0])
    for a in [a.name for a in o.data.color_attributes]:
        o.data.color_attributes.remove(o.data.color_attributes[a])
for o in TEX:
    o.data.uv_layers.new(name="UVMap")
select_only(TEX, body)                 # one shared UV layout for the three textured meshes
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(52), island_margin=0.004, area_weight=0.0, correct_aspect=True,
                         scale_to_bounds=False)
bpy.ops.uv.pack_islands(rotate=True, margin=0.006)
bpy.ops.object.mode_set(mode="OBJECT")
for o in (glow_ob, core_ob):
    o.data.uv_layers.new(name="UVMap")
    select_only([o])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.01)
    bpy.ops.object.mode_set(mode="OBJECT")
log("uv done")


def corner_arrays(ob):
    me = ob.data
    nl, npoly = len(me.loops), len(me.polygons)
    vi = np.empty(nl, np.int32)
    me.loops.foreach_get("vertex_index", vi)
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3) + np.array(tuple(ob.location), np.float32)
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


_all = world_bounds(FINAL)
ZMIN, ZTOP = min(p.z for p in _all), max(p.z for p in _all)

# glow sources for baked light bleed (Roblox Neon does not light its neighbours)
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

for ob in TEX:
    P, NRM, MI = corner_arrays(ob)
    NL = len(P)
    paint = np.ones((NL, 3), np.float32)
    sel = MI == M_SHROUD
    t = np_smooth(ZMIN, ZTOP - 0.4, P[sel][:, 2])
    paint[sel] *= (0.55 + 0.45 * t)[:, None]
    paint[sel, 0] *= 1.0 + 0.3 * (1 - t)          # the tail warms toward crimson as it darkens
    paint[MI == M_LINING] *= 0.9
    sel = MI == M_BONE
    if sel.any():
        tips = PTS["talons_R"] + PTS["talons_L"] if ob is not body else SPIKE_TIPS
        tp = np.array([tuple(p) for p in tips], np.float32)
        d = np.min(np.linalg.norm(P[sel][:, None, :] - tp[None, :, :], axis=2), axis=1)
        k = (1 - np_smooth(0.0, 0.34, d)) * 0.9
        dark = np.array([0.30, 0.12, 0.14], np.float32)
        paint[sel] *= (1 - k[:, None]) + k[:, None] * dark[None, :]
    bleed = np.zeros((NL, 3), np.float32)
    if ob is body:
        for i0 in range(0, NL, 1500):
            i1 = min(NL, i0 + 1500)
            Ld = gP[None, :, :] - P[i0:i1, None, :]
            dd = np.linalg.norm(Ld, axis=2) + 1e-6
            wrap = np.clip(np.einsum("cgk,ck->cg", Ld, NRM[i0:i1]) / dd * 0.75 + 0.25, 0, 1)
            w = gA[None, :] * wrap * np.exp(-dd / 0.16) / (dd * dd + 0.03 ** 2)
            bleed[i0:i1] = w @ gC
        bleed = (1 - np.exp(-BLEED_K * bleed)) * BLEED_STRENGTH
    for nm, arr in (("Paint", paint), ("Bleed", bleed)):
        at = ob.data.color_attributes.new(nm, "FLOAT_COLOR", "CORNER")
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
    if idx == M_BONE:        # a few broad painted hairline cracks
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
    if idx in (M_SHROUD, M_LINING):   # soft vertical fold streaks
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
    height = remap(sep.outputs["Z"], ZMIN, ZTOP, 0.86, 1.06)
    shade = math_("MULTIPLY", math_("MULTIPLY", light, aof), math_("MULTIPLY", cavf, height))
    lit = mix(mix(albedo, tint, 1.0, "MULTIPLY"), grey(shade), 1.0, "MULTIPLY")
    rim_k = {M_SHROUD: 0.3, M_LINING: 0.6, M_SOCK: 0.3}.get(idx, 1.0)   # a dark cloth must stay dark
    rim = remap(dot_light(RIM_DIR), 0.25, 1.0, 0.0, 0.14 * rim_k)
    lit = mix(lit, (1.0, 0.2, 0.28, 1), rim, "ADD")
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


bake_img = bpy.data.images.new(f"{NAME}_bake", BAKE_RES, BAKE_RES, alpha=False)
for i, m in enumerate(MATS):
    build_bake_shader(i, m, bake_img)
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 40
scene.render.bake.margin = 16
select_only(TEX, body)
t_b = time.time()
bpy.ops.object.bake(type="EMIT")
log(f"bake {time.time() - t_b:.0f}s")
px = np.empty(BAKE_RES * BAKE_RES * 4, np.float32)
bake_img.pixels.foreach_get(px)
px = px.reshape(BAKE_RES, BAKE_RES, 4)
fct = BAKE_RES // TEX_SIZE
small = px.reshape(TEX_SIZE, fct, TEX_SIZE, fct, 4).mean(axis=(1, 3))
TEX_PATH = ROOT / "textures" / "BaseColor.png"
tex_img = bpy.data.images.new(f"{NAME}_BaseColor_tmp", TEX_SIZE, TEX_SIZE, alpha=False)
tex_img.pixels.foreach_set(small.ravel())
tex_img.filepath_raw = str(TEX_PATH)
tex_img.file_format = "PNG"
tex_img.save()
bpy.data.images.remove(bake_img)
bpy.data.images.remove(tex_img)
tex_img = bpy.data.images.load(str(TEX_PATH))
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
for ob in TEX:
    ob.data.materials.clear()
    ob.data.materials.append(final_mat)
    for p in ob.data.polygons:
        p.material_index = 0
    for nm in ("Paint", "Bleed"):
        ob.data.color_attributes.remove(ob.data.color_attributes[nm])
for m in MATS:
    bpy.data.materials.remove(m)
log("texture done")

# ---- exports
FBX_PATH = ROOT / "exports" / "fbx" / "Wraith.fbx"
GLB_PATH = ROOT / "exports" / "glb" / "Wraith.glb"
select_only(FINAL, body)
bpy.ops.export_scene.gltf(filepath=str(GLB_PATH), export_format="GLB", use_selection=True, export_apply=True)
select_only(FINAL, body)
bpy.ops.export_scene.fbx(filepath=str(FBX_PATH), use_selection=True, object_types={"MESH"}, axis_forward="-Z",
                         axis_up="Y", path_mode="COPY", embed_textures=True, add_leaf_bones=False, mesh_smooth_type="OFF")
log("exported")


# ---- reports
def mesh_stats(ob):
    me = ob.data
    me.calc_loop_triangles()
    bm = bmesh.new()
    bm.from_mesh(me)
    loose = sum(1 for v in bm.verts if not v.link_faces)
    zero = sum(1 for f in bm.faces if f.calc_area() < 1e-9)
    nonman = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    co = np.array([tuple(ob.matrix_world @ v.co) for v in me.vertices])
    mn, mxv = co.min(axis=0), co.max(axis=0)
    return {"triangles": len(me.loop_triangles), "vertices": len(me.vertices), "loose_vertices": loose,
            "zero_area_faces": zero, "non_manifold_edges": nonman,
            "bbox_min": [round(float(x), 4) for x in mn], "bbox_max": [round(float(x), 4) for x in mxv],
            "dimensions_studs": [round(float(x), 4) for x in (mxv - mn)],
            "pivot": [round(float(x), 4) for x in ob.matrix_world.translation]}


def studio(v):
    return [round(-float(v[0]), 4), round(float(v[2]), 4), round(float(v[1]), 4)]


def studio_size(v):
    return [round(float(v[0]), 4), round(float(v[2]), 4), round(float(v[1]), 4)]


STATS = {o.name: mesh_stats(o) for o in FINAL}
allmn = np.min([s["bbox_min"] for s in STATS.values()], axis=0)
allmx = np.max([s["bbox_max"] for s in STATS.values()], axis=0)
tips_x = [p.x for p in PTS["talons_R"] + PTS["talons_L"]]
KINDS = {body.name: "textured", armR.name: "textured", armL.name: "textured", glow_ob.name: "glow", core_ob.name: "glow"}
poly_report = {
    "asset": "crimson-wraith", "blender_version": bpy.app.version_string,
    "authoring": "final Roblox stud size (1 Blender unit = 1 stud); import at 1:1, do not scale",
    "axes": "Blender Z-up, the wraith faces -Y, its right hand is at -X; Studio = (-x, z, y) of Blender",
    "origin": "Blender (0,0,0) = body axis at chest height (hover pivot); arm origins sit on the shoulder joints",
    "texture": f"textures/BaseColor.png ({TEX_SIZE}x{TEX_SIZE}), shared by Wraith_Body, Wraith_ArmL, Wraith_ArmR",
    "authored_scale_factor": round(SCALE, 5),
    "budget": "target 3000-5000 triangles total, hard cap 6000 (up to 24 on screen)",
    "parts": {o.name: dict(kind=KINDS[o.name], **STATS[o.name]) for o in FINAL},
    "total_triangles": sum(s["triangles"] for s in STATS.values()),
    "total_vertices": sum(s["vertices"] for s in STATS.values()),
    "height_studs": round(float(allmx[2] - allmn[2]), 4),
    "claw_spread_studs": round(max(tips_x) - min(tips_x), 4),
    "overall_width_studs": round(float(allmx[0] - allmn[0]), 4),
    "pre_join_part_triangles": PART_TRIS,
}
(ROOT / "polygon-report.json").write_text(json.dumps(poly_report, indent=1))

parts = {}
for o in FINAL:
    st = STATS[o.name]
    mn, mxv = np.array(st["bbox_min"]), np.array(st["bbox_max"])
    ctr = (mn + mxv) / 2
    part = {"kind": KINDS[o.name], "center_studio": studio(ctr), "size_studio": studio_size(mxv - mn), "triangles": st["triangles"]}
    if o is glow_ob:
        part.update(material="Neon", color_rgb=list(GLOW),
                    note="crimson glow: eye sockets, mouth, soul core, tail-tatter and tail-ridge edge lines")
    elif o is core_ob:
        part.update(material="Neon", color_rgb=list(CORE), note="white-hot cores: eye pupils, soul core centre")
    else:
        part.update(material="SmoothPlastic (or Plastic), Color white", texture_id="textures/BaseColor.png")
    if o in (armR, armL):
        pv = np.array(tuple(PIV[o.name]))
        part.update(shoulder_pivot_studio=studio(pv), shoulder_pivot_relative_to_center_studio=studio(pv - ctr))
    parts[o.name] = part
eyes_mid = (PTS["eye_R"] + PTS["eye_L"]) / 2
install = {
    "name": "CrimsonWraith", "blender_version": bpy.app.version_string, "status": "Blender-verified, Studio untested",
    "units": "1 Blender unit = 1 stud, authored at final size (4.5 studs hood tip to tail tip); import 1:1",
    "axes": "Studio = (-x, z, y) of Blender",
    "facing": "Studio -Z forward: the skull face looks along Studio -Z (Blender -Y); the wraith's right arm is at Studio +X",
    "model_origin": "Studio (0,0,0) = Blender origin = body axis at chest height (hover pivot / bob pivot)",
    "texture": f"textures/BaseColor.png {TEX_SIZE}x{TEX_SIZE}, baked painted lighting, shared by the three textured parts; "
               "use MeshPart.TextureID (not SurfaceAppearance)",
    "parts": parts,
    "points": {
        "eyes_studio": studio(eyes_mid), "eye_L_studio": studio(PTS["eye_L"]), "eye_R_studio": studio(PTS["eye_R"]),
        "core_studio": studio(PTS["core"]), "tail_tip_studio": studio(PTS["tail_tip"]),
        "claw_tip_L_studio": studio(PTS["claw_tip_L"]), "claw_tip_R_studio": studio(PTS["claw_tip_R"]),
    },
    "notes": [
        "Every MeshPart imports centred on its own bounding box: place each at its center_studio relative to the model origin.",
        "Arms: rotate each arm about its shoulder_pivot_studio for claw swipes. The arm root is a cloth ball centred on the "
        "pivot inside the shroud, so swings up to about 40 degrees in any direction show no gap (see previews/ClawPose.png).",
        "claw_tip = tip of the long middle talon in the rest pose (hit point for swipes).",
        "Glow parts are not attached to the arms; nothing on the arms glows, so they can rotate freely.",
    ],
    "vfx_notes": [
        "Spawn: a crimson (255,22,52) burst at the slain enemy, then the wraith rises; fade-in over ~0.2 s.",
        "Trail: ParticleEmitter at tail_tip, Color 255,22,52 -> 60,0,15, LightEmission 1, Size 0.6 -> 0, Lifetime 0.35, Rate 30, "
        "Speed 0, Drag 4, LockedToPart false.",
        "Soul core pulse: tween the Wraith_GlowCore part's Transparency 0 -> 0.35 or size 1 -> 1.12 at ~2 Hz.",
        "Despawn after 6 s: crimson wisp burst at core_studio, fade all parts over ~0.3 s.",
    ],
}
(ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=1))
log("reports", {k: v["triangles"] for k, v in STATS.items()}, "total", poly_report["total_triangles"],
    "spread", poly_report["claw_spread_studs"], "height", poly_report["height_studs"])


# ---------------------------------------------------------------------------
# Previews
# ---------------------------------------------------------------------------
def concat_images(paths, out_path):
    arrs = []
    for p in paths:
        im = bpy.data.images.load(str(p))
        w, h = im.size
        a = np.empty(w * h * 4, np.float32)
        im.pixels.foreach_get(a)
        arrs.append(a.reshape(h, w, 4))
        bpy.data.images.remove(im)
    big = np.concatenate(arrs, axis=1)
    h, w = big.shape[:2]
    img = bpy.data.images.new("concat", w, h, alpha=False)
    img.pixels.foreach_set(big.ravel())
    img.filepath_raw = str(out_path)
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    for p in paths:
        os.remove(p)


setup_comp(0.45)
r = catalog_stage(FINAL, (5.5, -13.5, 5.0), samples=48)
render(PREV / "Preview.png")
r()
r = catalog_stage(FINAL, (0, -15, 1.2), samples=32)
render(PREV / "Front.png")
r()
r = catalog_stage(FINAL, (15, 0, 1.2), samples=32)
render(PREV / "Side.png")
r()
pose_arms(35)
r = catalog_stage(FINAL, (5.5, -13.5, 5.0), samples=32, res=900)
render(PREV / "_claw_a.png")
r()
r = catalog_stage(FINAL, (-5.0, 13.5, 7.0), samples=32, res=900)
render(PREV / "_claw_b.png")
r()
pose_arms(0)
concat_images([PREV / "_claw_a.png", PREV / "_claw_b.png"], PREV / "ClawPose.png")

fig_bm = new_bm()
FX = 3.4
for c, sz in (((FX - 0.5, 0, 1.0), (1.0, 1.0, 2.0)), ((FX + 0.5, 0, 1.0), (1.0, 1.0, 2.0)), ((FX, 0, 3.0), (2.0, 1.0, 2.0)),
              ((FX - 1.5, 0, 3.0), (1.0, 1.0, 2.0)), ((FX + 1.5, 0, 3.0), (1.0, 1.0, 2.0)), ((FX, 0, 4.5), (1.15, 1.15, 1.0))):
    box(fig_bm, V(*c), sz)
fme = bpy.data.meshes.new("R15 block figure_Geo")
fig_bm.to_mesh(fme)
fig_bm.free()
fig = bpy.data.objects.new("R15 block figure 5 studs (not exported)", fme)
WORK.objects.link(fig)
fm = bpy.data.materials.new("Figure grey")
fm.use_nodes = True
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.38, 0.38, 0.4, 1)
fme.materials.append(fm)
r = catalog_stage(FINAL, (0.6, -15, 2.5), samples=32, extra_objs=[fig], lift=0.0)
render(PREV / "Scale.png")
r()
bpy.data.objects.remove(fig, do_unlink=True)


def hero(path, cam_loc, target, lens=50, res=(1200, 1400), samples=96):
    """Dark stage, neutral key, strong crimson rims and underglow, heavy bloom (Cycles)."""
    clear_stage()
    w = scene.world
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.014, 0.011, 0.016, 1)
    cd = bpy.data.cameras.new("Hero camera")
    cam = bpy.data.objects.new("Hero camera", cd)
    REVIEW.objects.link(cam)
    cd.lens = lens
    cam.location = cam_loc
    point(cam, target)
    scene.camera = cam
    for nm, loc, col, en, sz in (("Hero key", V(-4, -6, 7), (0.92, 0.92, 1.0), 900, 4),
                                  ("Hero rim crimson L", V(4.5, 5, 4), (1.0, 0.10, 0.16), 1800, 3),
                                  ("Hero rim crimson R", V(-4.5, 4.5, 3), (1.0, 0.16, 0.2), 1400, 3),
                                  ("Hero underglow", V(1.5, -4, -3.5), (1.0, 0.25, 0.25), 220, 4)):
        ld = bpy.data.lights.new(nm, "AREA")
        ld.color = col
        ld.energy = en
        ld.size = sz
        lo = bpy.data.objects.new(nm, ld)
        REVIEW.objects.link(lo)
        lo.location = loc
        point(lo, V(0, 0, 0))
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
    render(path)
    scene.view_settings.look = "None"
    setup_comp(0.45)


tgt = V(0, -0.2, -0.12)
hero(PREV / "Hero.png", tgt + V(0.32, -0.93, 0.08).normalized() * 7.9, tgt)

r = catalog_stage(FINAL, (0, -15, 1.2))
r()                                    # keep the review camera/lights, but leave the asset at its true origin
select_only(FINAL, body)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "wraith.blend"))
log("blend saved")
log("DONE")
