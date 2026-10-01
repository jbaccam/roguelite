"""Vampire Blade: Godly melee weapon (RARITY_GODLY_ARMOR.md section 9).

"Every hit heals you, and kills send red wisps flying into you for extra healing."

Run in background Blender 5.2 only (never the user's open scene):
  blender -b --factory-startup --threads 2 --python build_vampire_blade.py

Environment switches (all optional):
  MODE=quick     build the model and render flat review shots only (no bake, no exports)
  MODE=full      (default) build, bake the painted texture, export, validate, render everything
  OUT=<dir>      where quick renders go (default: this folder)
  SHOTS=a,b      quick mode: catalog,front,side

Pipeline (scene, helpers, painterly bake, export, validation, catalogue renders, composites) copied
from the approved Reaper's Scythe generator into this self-contained script.

Design: a big gothic longsword. Blackened steel blade with silver edges, a raised crimson enamel
panel framed by gold beads, a glowing blood channel (Neon fuller) threaded through three rune glyphs
(fangs, eye, double chevron), a flared, notched gothic tip. Bat-wing crossguard: chunky crimson
membranes on black finger ridges with gold arm bones and gold filigree, growing out of a gold
bat-eared boss that holds a Neon blood gem on each face. Crimson/black wrapped grip with gold bands,
big faceted ruby pommel in a gold claw setting.

Axes: Blender +z up along the blade, the flat faces look along +/-y, the guard spreads along x.
1 Blender unit = 1 Roblox stud. Studio axes are (-x, z, y) of Blender. Origin = ruby tip on the axis.
"""
import bpy, bmesh, math, json, os, sys, time
import numpy as np
from mathutils import Vector, Matrix
from pathlib import Path

T0 = time.time()
ROOT = Path(__file__).resolve().parent
NAME = "VampireBlade"
MODE = os.environ.get("MODE", "full")
OUT = Path(os.environ.get("OUT", str(ROOT)))
OUT.mkdir(parents=True, exist_ok=True)
SHOTS = [s for s in os.environ.get("SHOTS", "catalog,front,side").split(",") if s]
BAKE_SIZE = 1024
BLEED_K, BLEED_STRENGTH = 0.12, 0.5   # baked glow light on nearby surfaces
VIEW_TRANSFORM = os.environ.get("VT", "Khronos PBR Neutral")
VIEW_LOOK = os.environ.get("LOOK", "None")
CAT_ANGLE = -46.0                      # catalogue pose: tip up-left like the catalogue swords


def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)


def V(*a):
    return Vector(a)


# ---------------------------------------------------------------------------
# Palette. Slot index = material index on every textured mesh.
# flat: quick-preview colour. ramp: painterly noise ramp (sRGB). edge: highlight tint on bevels.
# ---------------------------------------------------------------------------
PAL = [
    ("Obsidian", (28, 14, 20), [(0.28, (14, 6, 10)), (0.52, (28, 14, 20)), (0.8, (58, 30, 40))], (170, 120, 140)),
    ("Steel", (30, 20, 30), [(0.28, (13, 8, 14)), (0.52, (30, 20, 30)), (0.8, (66, 46, 64))], (196, 170, 200)),
    ("Wine", (54, 8, 20), [(0.28, (26, 3, 9)), (0.52, (52, 8, 20)), (0.8, (96, 18, 34))], (220, 100, 120)),
    ("Crimson", (170, 16, 40), [(0.3, (92, 6, 22)), (0.52, (160, 16, 40)), (0.78, (214, 46, 66))], (255, 150, 160)),
    ("Gold", (206, 142, 52), [(0.3, (148, 88, 30)), (0.52, (206, 142, 50)), (0.8, (246, 202, 112))], (255, 236, 176)),
    ("Socket", (26, 10, 16), [(0.4, (14, 5, 9)), (0.75, (38, 14, 22))], (84, 36, 46)),
    ("Leather", (136, 22, 40), [(0.3, (80, 10, 24)), (0.52, (130, 22, 40)), (0.78, (178, 46, 62))], (236, 120, 130)),
    ("Bone", (232, 214, 186), [(0.3, (186, 156, 116)), (0.54, (232, 212, 178)), (0.8, (252, 242, 220))], (255, 255, 240)),
    ("Ruby", (214, 20, 46), [(0.3, (150, 8, 30)), (0.52, (220, 24, 50)), (0.78, (255, 112, 120))], (255, 220, 220)),
]
M_OBS, M_STEEL, M_WINE, M_CRIM, M_GOLD, M_SOCK, M_LEATHER, M_BONE, M_RUBY = range(len(PAL))
GLOW = tuple(int(x) for x in os.environ.get("GC", "255,6,36").split(","))        # Roblox Neon, hot blood crimson
CORE = (255, 72, 48)        # Roblox Neon, hot red-orange core (kept saturated, not pastel)
GLOW_STRENGTH, CORE_STRENGTH = float(os.environ.get("GS", "0.85")), float(os.environ.get("CS", "1.25"))


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
def loft(bm, rings, closed=True, caps=True, mat=0, recalc=True, segmats=None):
    """Connect rings (lists of points, or a single point = pole) with quads / fans.
    segmats: optional per-column material (segment j joins ring point j and j+1)."""
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
            f = bm.faces.new(f)
            f.material_index = segmats[s] if segmats else mat
            faces.append(f)
    if closed and caps:
        for r in (vr[0], vr[-1]):
            if len(r) > 2:
                f = bm.faces.new(r[::-1] if r is vr[0] else r)
                f.material_index = mat
                faces.append(f)
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


def tube(bm, pts, radii, sides=8, mat=0, flat=1.0, phase=0.0, section=None, up=V(0, 1, 0), caps=True):
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
        rings.append([p + N[k] * a * ra + B[k] * b * rb for a, b in sec])
    return loft(bm, rings, mat=mat, caps=caps)


def lathe(bm, prof, sides=8, M=None, mat=0, phase=None, sy=1.0, torus=False):
    """Surface of revolution about local +z; prof = [(radius, z)] bottom to top.
    torus=True: the profile is a closed loop (rings, bezels), no caps."""
    M = M or Matrix()
    phase = math.pi / sides if phase is None else phase
    rings = []
    for r, z in prof:
        if r <= 1e-6:
            rings.append(M @ V(0, 0, z))
        else:
            rings.append([M @ V(r * math.cos(phase + 2 * math.pi * s / sides), r * sy * math.sin(phase + 2 * math.pi * s / sides), z)
                          for s in range(sides)])
    if torus:
        return loft(bm, rings + [[v.copy() for v in rings[0]]], mat=mat, caps=False)
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


def face_matrix(c, side):
    """Local frame on a blade/boss face: local z points out along +/-y."""
    return Matrix.Translation(c) @ Matrix.Rotation(math.radians(-90 * side), 4, "X")


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
    bs.inputs["Roughness"].default_value = 0.55 if name not in ("Gold", "Steel", "Ruby") else 0.35
    if name in ("Gold", "Steel"):
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


GLOW_MAT = emit_mat(f"{NAME}_Glow", GLOW, GLOW_STRENGTH)
CORE_MAT = emit_mat(f"{NAME}_GlowCore", CORE, CORE_STRENGTH)

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


def curve_mesh(name, paths, depth, mat=None, res=3):
    """Round-section gold wire: poly curves with bevel depth, converted to mesh."""
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


# ---------------------------------------------------------------------------
# Layout (studs). Blade axis is x = y = 0; z = 0 is the ruby tip.
# ---------------------------------------------------------------------------
ZG = 1.60                      # guard boss centre
GRIP_Z0, GRIP_Z1 = 0.50, 1.20  # leather wrap
TIP_Z = 4.82

# blade half-width profile: waisted at the guard, gothic flare, a notch and barbs, ogive point
WZ = [(1.70, 0.30), (1.95, 0.33), (2.20, 0.345), (2.70, 0.34), (3.20, 0.365), (3.55, 0.405), (3.80, 0.44),
      (3.90, 0.445), (3.98, 0.33), (4.04, 0.33), (4.12, 0.40), (4.26, 0.355), (4.44, 0.22), (4.62, 0.09), (TIP_Z, 0.0)]
TOOTH_Z0, TOOTH_PITCH, TOOTH_N, TOOTH_H, TOOTH_RISE, HOOK = 2.30, 0.35, 4, 0.115, 0.055, 0.075
TEETH, PEAKS = [], set()
for _k in range(TOOTH_N):
    _z = TOOTH_Z0 + _k * TOOTH_PITCH
    TEETH += [round(_z, 4), round(_z + TOOTH_RISE, 4), round(_z + 0.17, 4)]
    PEAKS.add(round(_z + TOOTH_RISE, 4))
TOOTH_Z1 = round(TOOTH_Z0 + TOOTH_N * TOOTH_PITCH, 4)
BLADE_ROWS = [1.70, 1.95, 2.14] + TEETH + [TOOTH_Z1, 3.86, 3.92, 3.98, 4.04, 4.12, 4.26, 4.44, 4.62]


def tooth(z):
    """hooked barbs on the cutting edges: a steep face toward the guard, a long concave back toward the tip"""
    if z < TOOTH_Z0 or z > TOOTH_Z1:
        return 0.0
    f = (z - TOOTH_Z0) - TOOTH_PITCH * math.floor((z - TOOTH_Z0) / TOOTH_PITCH + 1e-6)
    if f <= TOOTH_RISE + 1e-6:
        return TOOTH_H * min(1.0, f / TOOTH_RISE)
    return TOOTH_H * max(0.0, (TOOTH_PITCH - f) / (TOOTH_PITCH - TOOTH_RISE)) ** 1.5


def edge_x(v, z):
    """x of cross-section fraction v: the panel stays straight, only the outer edge carries the barbs"""
    return v * bw(z) + tooth(z) * max(0.0, (v - 0.58) / 0.42)


def edge_z(v, z):
    """barb tips hook back toward the guard"""
    if round(z, 4) in PEAKS:
        return z - HOOK * max(0.0, (v - 0.58) / 0.42) ** 1.5
    return z


def bw(z):
    for (z0, w0), (z1, w1) in zip(WZ, WZ[1:]):
        if z <= z1:
            return lerp(w0, w1, (z - z0) / (z1 - z0)) if z >= z0 else w0
    return 0.0


def btt(z):
    """thickness taper toward the point"""
    return 1.0 - 0.45 * smoothstep(3.9, 4.65, z)


# half cross-section from the axis (v = 0) to the edge (v = 1) on the +y face:
# (v fraction of half-width, half-thickness, material of the segment to the next point)
H = [
    (0.00, 0.048, M_SOCK),     # blood channel floor (Neon strip lies in it)
    (0.15, 0.048, M_GOLD),     # gold lip up to the panel
    (0.17, 0.088, M_WINE),     # deep wine enamel panel (runes and veins cut into it)
    (0.47, 0.088, M_GOLD),     # gold bead framing the panel
    (0.50, 0.102, M_GOLD),
    (0.555, 0.102, M_GOLD),
    (0.585, 0.084, M_STEEL),   # blackened steel body
    (0.92, 0.046, M_STEEL),    # flat that the Neon cutting edge grows out of
]
EDGE_V0 = 0.90                # Neon cutting edge: from here to the very edge


def blade_ring(z):
    w, tt = bw(z), btt(z)
    n = len(H) - 1
    pts = []
    for i in range(n, 0, -1):
        pts.append((-H[i][0], H[i][1], H[i - 1][2]))
    for i in range(0, n):
        pts.append((H[i][0], H[i][1], H[i][2]))
    pts.append((H[n][0], H[n][1], M_STEEL))
    for i in range(n, 0, -1):
        pts.append((H[i][0], -H[i][1], H[i - 1][2]))
    for i in range(0, n):
        pts.append((-H[i][0], -H[i][1], H[i][2]))
    pts.append((-H[n][0], -H[n][1], M_STEEL))
    return [V(math.copysign(edge_x(abs(v), z), v), t * tt, edge_z(abs(v), z)) for v, t, _ in pts], [m for _, _, m in pts]


def build_blade():
    bm = new_bm()
    rings, mats = [], None
    for z in BLADE_ROWS:
        r, mats = blade_ring(z)
        rings.append(r)
    rings.append(V(0, 0, TIP_Z))
    loft(bm, rings, segmats=mats, mat=M_SOCK)
    ob = make_obj("Blade", bm, smooth=True)
    return ob


def build_fuller_glow():
    """Neon blood channel: one solid strip through the blade (its faces show in both channels),
    pointed at both ends, plus a hot core line on top."""
    g, c = new_bm(), new_bm()
    for bmx, z0, z1, fx, fy in ((g, 2.16, 4.56, 0.12, 0.062), (c, 2.30, 4.40, 0.04, 0.069)):
        zs = [z for z in BLADE_ROWS if z0 < z < z1]
        rings = [V(0, 0, z0)]
        for z in [z0 + 0.06] + zs + [z1 - 0.05]:
            w, tt = bw(z), btt(z)
            rings.append([V(-fx * w, -fy * tt, z), V(fx * w, -fy * tt, z), V(fx * w, fy * tt, z), V(-fx * w, fy * tt, z)])
        rings.append(V(0, 0, z1))
        loft(bmx, rings)
    # glowing serrated cutting edges (one wedge per side, meeting at the point)
    for sx in (1, -1):
        rings = []
        for z in [1.86] + [z for z in BLADE_ROWS if z > 1.86]:
            tt = btt(z)
            x0, x1 = edge_x(EDGE_V0, z), edge_x(1.0, z)
            z0_, z1_ = edge_z(EDGE_V0, z), edge_z(1.0, z)
            rings.append([V(sx * x0, 0.052 * tt, z0_), V(sx * x1, 0.012 * tt, z1_), V(sx * x1, -0.012 * tt, z1_), V(sx * x0, -0.052 * tt, z0_)])
        rings.append(V(0, 0, TIP_Z))
        loft(g, rings)
    make_obj("Fuller_Glow", g, kind="glow")
    make_obj("Fuller_Core", c, kind="core")


# rune glyphs: strokes in unit glyph space, a along the blade (toward the tip), b across.
# All glyphs are mirror-symmetric in b, and the blood channel runs through each of them.
RUNES = {
    "fangs": [[(0.34, -0.40), (0.34, -0.10), (-0.46, -0.25), (0.34, -0.40)],
              [(0.34, 0.40), (0.34, 0.10), (-0.46, 0.25), (0.34, 0.40)],
              [(0.46, -0.42), (0.46, 0.42)]],
    "eye": [[(-0.52, 0), (0, -0.40), (0.52, 0), (0, 0.40), (-0.52, 0)], [(0, -0.56), (0, -0.40)], [(0, 0.40), (0, 0.56)]],
    "chevrons": [[(-0.05, -0.42), (0.40, 0), (-0.05, 0.42)], [(-0.45, -0.42), (0.0, 0), (-0.45, 0.42)]],
}
RUNES["vein"] = [[(-0.06, 0.06), (0.10, 0.17), (0.06, 0.27), (0.24, 0.40)], [(0.10, 0.17), (0.26, 0.20)],
                 [(-0.06, -0.06), (0.10, -0.17), (0.06, -0.27), (0.24, -0.40)], [(0.10, -0.17), (0.26, -0.20)]]
RUNE_LAYOUT = [("fangs", 2.52, 0.30), ("vein", 2.72, 0.36), ("eye", 2.98, 0.30), ("vein", 3.18, 0.36),
               ("chevrons", 3.42, 0.30), ("vein", 3.62, 0.36)]


def rune_strokes(bm, glyph, zc, size, side, d0, d1, width, mat=0):
    t_s = 0.088 * btt(zc)
    n = V(0, side, 0)
    a, b = V(0, 0, 1), V(1, 0, 0)
    c = V(0, 0, zc)
    for stroke in RUNES[glyph]:
        for (x0, y0), (x1, y1) in zip(stroke, stroke[1:]):
            p0 = c + a * x0 * size + b * y0 * size
            p1 = c + a * x1 * size + b * y1 * size
            d = (p1 - p0)
            d.normalize()
            perp = n.cross(d).normalized()
            ext = width * 0.5
            p0e, p1e = p0 - d * ext, p1 + d * ext
            quad = [p0e - perp * ext, p1e - perp * ext, p1e + perp * ext, p0e + perp * ext]
            r0 = [q + n * (t_s + d0) for q in quad]
            r1 = [q + n * (t_s + d1) for q in quad]
            loft(bm, [r0, r1], mat=mat)


def build_runes(blade):
    cut = new_bm()
    gl = new_bm()
    for glyph, zc, sz in RUNE_LAYOUT:
        for side in (1, -1):
            rune_strokes(cut, glyph, zc, sz, side, -0.017, 0.08, 0.05, mat=M_SOCK)
            rune_strokes(gl, glyph, zc, sz, side, -0.024, -0.006, 0.034)
    for f in cut.faces:
        f.material_index = M_SOCK
    cutter = make_obj("RuneCutter", cut, kind="cut")
    add_bool(blade, cutter, self_int=True)
    make_obj("Runes_Glow", gl, kind="glow")


def build_langets():
    """Gold gothic-arch langets on both faces where the blade leaves the boss, each set with a Neon blood drop."""
    bm = new_bm()
    g, c = new_bm(), new_bm()
    poly = [(-0.27, 1.72), (0.27, 1.72), (0.27, 2.02), (0.20, 2.16), (0.09, 2.28), (0.0, 2.36), (-0.09, 2.28),
            (-0.20, 2.16), (-0.27, 2.02)]
    for side in (1, -1):
        prism(bm, poly, V(0, 0, 0), V(1, 0, 0), V(0, 0, 1), V(0, side, 0), 0.05, 0.122, mat=M_GOLD)
        M = face_matrix(V(0, side * 0.118, 2.10), side)
        lathe(bm, [(0.065, -0.01), (0.092, -0.01), (0.098, 0.016), (0.084, 0.03), (0.066, 0.026)], sides=8, M=M, mat=M_GOLD,
              sy=1.35, torus=True)
        lathe(g, [(0.0, -0.005), (0.07, 0.0), (0.066, 0.03), (0.04, 0.05), (0.0, 0.058)], sides=8, M=M, sy=1.35)
        lathe(c, [(0.0, 0.035), (0.026, 0.05), (0.0, 0.066)], sides=6, M=M, sy=1.35)
    ob = make_obj("Langets", bm, smooth=True)
    hard(ob, 0.008, segs=1, angle=30)
    make_obj("LangetGem_Glow", g, kind="glow")
    make_obj("LangetGem_Core", c, kind="core")
    return ob


# ---- bat-wing crossguard ---------------------------------------------------
WL = [(0.30, 0.14), (0.86, 0.22), (1.22, 0.64)]      # leading edge (arm bone), relative to the boss centre
WB = [(0.30, -0.26), (0.74, -0.66), (1.22, 0.64)]    # trailing edge before scalloping
SCALLOP = 0.46
FINGER_S = [(1 / 3) ** 1.25, (2 / 3) ** 1.25]       # where the scallops meet: finger tips


def qb(P, s):
    a = (1 - s) ** 2
    b = 2 * (1 - s) * s
    c = s * s
    return (a * P[0][0] + b * P[1][0] + c * P[2][0], a * P[0][1] + b * P[1][1] + c * P[2][1])


def wing_xz(s, v):
    lx, lz = qb(WL, s)
    bx, bz = qb(WB, s)
    sc = SCALLOP * abs(math.sin(3 * math.pi * s ** 0.8)) ** 0.8
    bx, bz = bx + (lx - bx) * sc, bz + (lz - bz) * sc
    return lx + (bx - lx) * v, lz + (bz - lz) * v


def wing_T(s):
    return lerp(0.12, 0.065, s)


def wing_t(s, v):
    return wing_T(s) * (1 - 0.40 * v)


def wing_pt(s, v, sx, y=0.0):
    x, z = wing_xz(s, v)
    return V(sx * x, y, ZG + z)


def build_wings():
    """Bat wings: thick crimson membranes with three scalloped lobes, black finger bones that run past the
    scallops into hooked claws, and a gold arm bone along the leading edge ending in an inward-hooked talon."""
    mem, bones, gold = new_bm(), new_bm(), new_bm()
    VS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    SS = sorted(set([round(i / 26, 5) for i in range(26)] + [round(s, 5) for s in FINGER_S]))
    for sx in (1, -1):
        rings = []
        for s in SS:
            ring = [wing_pt(s, v, sx, wing_t(s, v)) for v in VS]
            ring += [wing_pt(s, v, sx, -wing_t(s, v)) for v in reversed(VS)]
            rings.append(ring)
        loft(mem, rings, mat=M_CRIM)
        root = wing_pt(0.0, 0.5, sx)
        for sk in FINGER_S:
            tip = wing_pt(sk, 1.0, sx)
            d = (tip - root)
            dn = d.normalized()
            mid = root + d * 0.5 + V(0, 0, 0.04)
            near = root + d * 0.8
            c1 = tip + dn * 0.13
            c2 = tip + dn * 0.22 + V(0, 0, 0.07)        # claw hooks back up
            tube(bones, [root, mid, near, tip, c1, c2],
                 [(0.065, 0.13), (0.06, 0.122), (0.055, 0.105), (0.05, 0.085), (0.035, 0.05), 0.0], sides=6, mat=M_STEEL)
        pts, radii = [], []
        for i in range(11):
            s = i / 10
            pts.append(wing_pt(s, 0.0, sx))
            radii.append((lerp(0.075, 0.05, s), wing_T(s) + 0.035))
        d = (pts[-1] - pts[-2]).normalized()
        pts += [pts[-1] + d * 0.12, pts[-1] + d * 0.18 + V(0, 0, 0.10) + V(-sx * 0.04, 0, 0),
                pts[-1] + d * 0.12 + V(0, 0, 0.22) + V(-sx * 0.14, 0, 0)]
        radii += [(0.045, 0.075), (0.035, 0.05), 0.0]
        tube(gold, pts, radii, sides=8, mat=M_GOLD, phase=math.pi / 8)
        # a second, smaller gold claw plate layered over the wing root (upper shoulder spur)
        sp = [wing_pt(0.05, 0.05, sx) + V(0, 0, 0.02), wing_pt(0.22, 0.02, sx) + V(0, 0, 0.12),
              wing_pt(0.30, 0.0, sx) + V(sx * 0.02, 0, 0.30)]
        tube(gold, sp, [(0.06, 0.15), (0.045, 0.1), 0.0], sides=6, mat=M_GOLD)
    ob = make_obj("WingMembranes", mem, smooth=True)
    hard(ob, 0.007, segs=1, angle=35)
    ob2 = make_obj("WingFingers", bones, smooth=True)
    hard(ob2, 0.006, segs=1, angle=30)
    ob3 = make_obj("WingArms", gold, smooth=True)
    hard(ob3, 0.006, segs=1, angle=30)
    return [ob, ob2, ob3]


def build_wing_veins():
    """Glowing blood veins on every membrane lobe, both faces, laid on the lens surface."""
    g = new_bm()
    lobes = [(0.0, FINGER_S[0]), (FINGER_S[0], FINGER_S[1]), (FINGER_S[1], 0.92)]
    for li, (sa, sb) in enumerate(lobes):
        sc = (sa + sb) / 2
        span = sb - sa
        main = [(sc - 0.10 * span, 0.12), (sc + 0.04 * span, 0.34), (sc - 0.06 * span, 0.56), (sc + 0.02 * span, 0.80)]
        branch = [(sc + 0.04 * span, 0.34), (sc + 0.26 * span, 0.50), (sc + 0.30 * span, 0.66)]
        branch2 = [(sc - 0.06 * span, 0.56), (sc - 0.26 * span, 0.70)]
        for path, r0 in ((main, 0.022), (branch, 0.017), (branch2, 0.015)):
            for sx in (1, -1):
                for side in (1, -1):
                    pts = [wing_pt(s, v, sx, side * (wing_t(s, v) + 0.002)) for s, v in path]
                    n = len(pts)
                    tube(g, pts, [(r0 * (1 - 0.5 * k / (n - 1)), 0.012) for k in range(n - 1)] + [0.0], sides=4,
                         phase=math.pi / 4)
    make_obj("WingVeins_Glow", g, kind="glow")


SHIELD_R = [(0.0, 0.27), (0.20, 0.31), (0.38, 0.25), (0.47, 0.07), (0.43, -0.12), (0.27, -0.31), (0.0, -0.48)]


def shield_poly(k=1.0, cz=-0.03):
    right = [(x * k, cz + (z - cz) * k) for x, z in SHIELD_R]
    left = [(-x, z) for x, z in reversed(right[1:-1])]
    return right + left


def build_boss():
    """Gold bat-eared shield boss the wings grow out of (pointed like a fang below):
    crimson enamel inlay, gold bezel, Neon blood gem on each face."""
    bm, en = new_bm(), new_bm()
    g, c = new_bm(), new_bm()
    O = V(0, 0, ZG)
    X, Z = V(1, 0, 0), V(0, 0, 1)
    prism(bm, shield_poly(), O, X, Z, V(0, 1, 0), -0.20, 0.20, mat=M_GOLD)
    for side in (1, -1):
        prism(en, shield_poly(0.76), O, X, Z, V(0, side, 0), 0.17, 0.222, mat=M_CRIM)
        if side < 0:
            continue
        M = face_matrix(V(0, side * 0.218, ZG + 0.02), side)
        lathe(bm, [(0.12, -0.01), (0.19, -0.01), (0.20, 0.03), (0.175, 0.058), (0.14, 0.05)], sides=8, M=M, mat=M_GOLD,
              sy=1.12, torus=True, phase=0.0)
        lathe(g, [(0.0, 0.0), (0.142, 0.006), (0.136, 0.046), (0.09, 0.082), (0.0, 0.096)], sides=8, M=M, sy=1.12, phase=0.0)
        lathe(c, [(0.0, 0.066), (0.055, 0.086), (0.0, 0.108)], sides=6, M=M, sy=1.12)
    lathe(bm, [(0.112, 1.15), (0.15, 1.19), (0.19, 1.26), (0.2, 1.33), (0.16, 1.40)], sides=10, mat=M_GOLD)
    ob = make_obj("Boss", bm, smooth=True)
    hard(ob, 0.01, segs=1, angle=30)
    ob2 = make_obj("BossEnamel", en, smooth=True)
    hard(ob2, 0.008, segs=2, angle=30)
    make_obj("BossGem_Glow", g, kind="glow")
    make_obj("BossGem_Core", c, kind="core")
    return [ob, ob2]




HC = V(0, -0.20, ZG + 0.03)     # bat head centre (it faces -y, out of the front of the boss)


def build_bat_head():
    """Focal piece: a snarling vampire-bat head on the front of the guard. Bone skull, big black pointed ears
    with crimson inner ears, angry gold brows, glowing slanted eyes with hot slit pupils, open jaw with bone fangs."""
    bm, bone, sock = new_bm(), new_bm(), new_bm()
    g, c = new_bm(), new_bm()
    # cranium: faceted egg, half sunk into the boss
    Mc = Matrix.Translation(HC)
    lathe(bm, [(0.0, -0.24), (0.17, -0.20), (0.26, -0.08), (0.285, 0.04), (0.25, 0.15), (0.15, 0.235), (0.0, 0.265)],
          sides=10, M=Mc, mat=M_BONE, sy=0.78, phase=0.0)
    # muzzle: a short wedge pushed forward and down, with flared nostril ridges
    Mm = face_matrix(V(0, -0.30, ZG - 0.05), -1)
    lathe(bm, [(0.135, 0.0), (0.14, 0.06), (0.115, 0.13), (0.06, 0.175), (0.0, 0.185)], sides=8, M=Mm, mat=M_BONE,
          sy=0.78, phase=0.0)
    for sx in (1, -1):        # nostril pits
        lathe(sock, [(0.0, 0.0), (0.028, 0.01), (0.0, 0.02)], sides=6,
              M=face_matrix(V(sx * 0.04, -0.478, ZG - 0.025), -1))
    # mouth cavity and lower jaw
    mouth = [(-0.13, -0.075), (0.13, -0.075), (0.10, -0.175), (0.0, -0.205), (-0.10, -0.175)]
    prism(sock, mouth, V(0, 0, ZG), V(1, 0, 0), V(0, 0, 1), V(0, 1, 0), -0.28, -0.385, mat=M_SOCK)
    jaw = [(-0.15, -0.16), (0.15, -0.16), (0.11, -0.25), (0.0, -0.31), (-0.11, -0.25)]
    prism(bm, jaw, V(0, 0, ZG), V(1, 0, 0), V(0, 0, 1), V(0, 1, 0), -0.24, -0.43, mat=M_BONE)
    for sx in (1, -1):
        # fangs: two long upper canines, two short upper, two lower
        tube(bone, [V(sx * 0.072, -0.41, ZG - 0.07), V(sx * 0.07, -0.43, ZG - 0.17), V(sx * 0.062, -0.44, ZG - 0.27)],
             [0.036, 0.026, 0.0], sides=6, mat=M_BONE)
        tube(bone, [V(sx * 0.118, -0.405, ZG - 0.08), V(sx * 0.115, -0.42, ZG - 0.17)], [0.022, 0.0], sides=4, mat=M_BONE)
        tube(bone, [V(sx * 0.10, -0.42, ZG - 0.20), V(sx * 0.10, -0.43, ZG - 0.115)], [0.024, 0.0], sides=4, mat=M_BONE)
    # angry brows (gold): heavy ridge from the bridge out and up, ending in a small spike
    for sx in (1, -1):
        tube(bm, [V(sx * 0.02, -0.425, ZG + 0.105), V(sx * 0.13, -0.405, ZG + 0.16), V(sx * 0.25, -0.33, ZG + 0.225),
                  V(sx * 0.33, -0.26, ZG + 0.29)], [(0.04, 0.035), (0.042, 0.04), (0.03, 0.03), 0.0], sides=6, mat=M_GOLD,
             up=V(0, 0, 1))
    # eyes: slanted almonds (inner corner low) set in dark sockets, hot slit pupils
    for sx in (1, -1):
        eye = [(0.035, 0.055), (0.10, 0.075), (0.19, 0.13), (0.205, 0.105), (0.15, 0.04), (0.08, 0.025)]
        eye = [(sx * x, z) for x, z in eye]
        prism(sock, eye, V(0, 0, ZG), V(1, 0, 0), V(0, 0, 1), V(0, 1, 0), -0.33, -0.405, mat=M_SOCK)
        inner = [(0.05, 0.057), (0.10, 0.07), (0.175, 0.118), (0.188, 0.102), (0.145, 0.05), (0.085, 0.037)]
        inner = [(sx * x, z) for x, z in inner]
        prism(g, inner, V(0, 0, ZG), V(1, 0, 0), V(0, 0, 1), V(0, 1, 0), -0.34, -0.418)
        slit = [(0.118, 0.04), (0.132, 0.04), (0.14, 0.095), (0.127, 0.10)]
        slit = [(sx * x, z) for x, z in slit]
        prism(c, slit, V(0, 0, ZG), V(1, 0, 0), V(0, 0, 1), V(0, 1, 0), -0.40, -0.428)
    # ears: tall pointed lens plates with crimson inner ears, flaring out beside the blade root
    ears, inner_e = new_bm(), new_bm()
    ear = [(0.10, 0.17), (0.15, 0.44), (0.30, 0.68), (0.62, 0.86), (0.50, 0.56), (0.42, 0.32), (0.27, 0.10)]
    cen = (sum(p[0] for p in ear) / len(ear), sum(p[1] for p in ear) / len(ear))
    inn = [(cen[0] + (x - cen[0]) * 0.62, cen[1] + (z - cen[1]) * 0.66 - 0.01) for x, z in ear]
    for sx in (1, -1):
        e = [(sx * x, z) for x, z in ear]
        i_ = [(sx * x, z) for x, z in inn]
        if sx < 0:
            e, i_ = e[::-1], i_[::-1]
        prism(ears, e, V(0, 0, ZG), V(1, 0, 0), V(0, 0, 1), V(0, 1, 0), -0.14, -0.235, mat=M_STEEL)
        prism(inner_e, i_, V(0, 0, ZG), V(1, 0, 0), V(0, 0, 1), V(0, 1, 0), -0.20, -0.25, mat=M_CRIM)
    ob = make_obj("BatHead", bm, smooth=True)
    hard(ob, 0.007, segs=1, angle=30)
    ob2 = make_obj("BatFangs", bone, smooth=True)
    hard(ob2, 0.004, segs=1, angle=30)
    make_obj("BatSockets", sock)
    ob4 = make_obj("BatEars", ears, smooth=True)
    hard(ob4, 0.008, segs=2, angle=30)
    ob5 = make_obj("BatInnerEars", inner_e, smooth=True)
    hard(ob5, 0.006, segs=1, angle=30)
    make_obj("BatEyes_Glow", g, kind="glow")
    make_obj("BatPupils_Core", c, kind="core")



def ring_band(bm, z, r_in, r_out, h, sides=10, mat=M_GOLD, crown=0.0, M=None):
    """Band around the grip; crown != 0 raises every other top vertex into points."""
    M = M or Matrix()
    rings = []
    n = sides * (2 if crown else 1)
    prof = [(r_in, -h / 2), (r_out, -h / 2 + 0.012), (r_out, h / 2 - 0.012), (r_in, h / 2)]
    for j, (r, dz) in enumerate(prof):
        ring = []
        for s in range(n):
            a = math.pi / n + 2 * math.pi * s / n
            zz = z + dz
            if crown and ((crown > 0 and j >= 2) or (crown < 0 and j < 2)) and s % 2 == 0:
                zz += crown
            ring.append(M @ V(r * math.cos(a), r * math.sin(a), zz))
        rings.append(ring)
    return loft(bm, rings, mat=mat)


GRIP_R = 0.105


def build_grip():
    """Black core with interleaved crimson and black leather straps, gold bands."""
    core = new_bm()
    lathe(core, [(GRIP_R - 0.01, 0.40), (GRIP_R, 0.42), (GRIP_R, 1.30), (GRIP_R - 0.01, 1.32)], sides=8, mat=M_OBS)
    ob0 = make_obj("GripCore", core, smooth=True)
    bm = new_bm()
    pitch = 0.13
    z0, z1 = GRIP_Z0, GRIP_Z1
    for mat, off in ((M_LEATHER, 0.0), (M_OBS, 0.5)):
        turns = (z1 - z0) / pitch
        steps = int(turns * 8)
        rings = []
        wdt, th = pitch * 0.5, 0.032
        for k in range(steps + 1):
            th_a = 2 * math.pi * (turns * k / steps + off)
            z = z0 + (z1 - z0) * k / steps
            rad = V(math.cos(th_a), math.sin(th_a), 0)
            c = V(0, 0, z) + rad * (GRIP_R + 0.004)
            sec = [(-th * 0.5, -wdt * 0.5), (th * 0.25, -wdt * 0.45), (th * 0.6, 0.0), (th * 0.25, wdt * 0.45), (-th * 0.5, wdt * 0.5)]
            rings.append([c + rad * a + V(0, 0, b) for a, b in sec])
        loft(bm, rings, mat=mat)
    ob = make_obj("GripWrap", bm, smooth=False)
    b2 = new_bm()
    ring_band(b2, 0.85, GRIP_R - 0.01, GRIP_R + 0.06, 0.07, sides=8)
    ring_band(b2, 1.17, GRIP_R - 0.01, GRIP_R + 0.05, 0.06, sides=8, crown=-0.05)
    ring_band(b2, 0.53, GRIP_R - 0.01, GRIP_R + 0.05, 0.06, sides=8, crown=0.05)
    ob2 = make_obj("GripBands", b2, smooth=True)
    hard(ob2, 0.008, segs=1, angle=30)
    return [ob0, ob, ob2]


def build_pommel():
    bm = new_bm()
    lathe(bm, [(0.11, 0.52), (0.16, 0.47), (0.19, 0.40), (0.175, 0.33), (0.12, 0.30)], sides=8, mat=M_GOLD)
    ob = make_obj("PommelCup", bm, smooth=True)
    hard(ob, 0.01, segs=2)
    b2 = new_bm()
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        d = V(math.cos(a), math.sin(a), 0)
        pts = [d * 0.15 + V(0, 0, 0.37), d * 0.225 + V(0, 0, 0.25), d * 0.205 + V(0, 0, 0.13), d * 0.12 + V(0, 0, 0.055)]
        tube(b2, pts, [(0.055, 0.042), (0.05, 0.038), (0.038, 0.03), 0.0], sides=6, mat=M_GOLD)
    ob2 = make_obj("PommelClaws", b2, smooth=True)
    hard(ob2, 0.006, segs=1)
    rb = new_bm()
    lathe(rb, [(0.0, 0.0), (0.12, 0.06), (0.205, 0.165), (0.20, 0.235), (0.13, 0.315), (0.0, 0.335)], sides=8, mat=M_RUBY,
          phase=0.0)
    ob3 = make_obj("PommelRuby", rb, smooth=False)
    sh = new_bm()
    lathe(sh, [(0.0, 0.05), (0.075, 0.03), (0.06, -0.06), (0.0, -0.24)], sides=6, phase=0.0)
    make_obj("PommelShard_Glow", sh, kind="glow")
    soft(ob3, 0.006, angle=20)
    return [ob, ob2, ob3]


def build_all():
    blade = build_blade()
    add_bevel(blade, 0.007, segs=1, angle=24, harden=False)      # bevel first: never bevel boolean output
    build_runes(blade)
    add_wn(blade)
    build_fuller_glow()
    build_langets()
    build_boss()
    build_wings()
    build_wing_veins()
    build_bat_head()
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
# Review rendering: the weapon catalogue's own stage.
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
        g.inputs["Threshold"].default_value = 0.45
        g.inputs["Strength"].default_value = bloom
        g.inputs["Size"].default_value = 0.8
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
    scene.view_settings.view_transform = VIEW_TRANSFORM
    scene.view_settings.look = VIEW_LOOK
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
    setup_comp(0.8)
    objs = asset_objs()
    for shot in SHOTS:
        if shot == "catalog":
            r = catalog_stage(objs, CAT_ANGLE, (1.6, -15, 6.2), res=800)
        else:
            vec = {"front": (0, -15, 1.2), "side": (15, 0, 1.2), "back": (0, 15, 1.2)}[shot]
            r = catalog_stage(objs, 0, vec, res=int(os.environ.get("QRES", "800")))
        render(OUT / f"q_{shot}{os.environ.get('TAG', '')}.png")
        r()


if MODE == "quick":
    quick_shots()
    log("QUICK DONE")
    sys.exit(0)


# ===========================================================================
# FULL MODE: join, UV, painted masks, bake, export, render, validate
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
SCALE = 1.0          # authored at hero size (about 4.7 studs)
for o in PARTS:
    o.data.transform(Matrix.Scale(SCALE, 4) @ Matrix.Translation(V(0, 0, -Z0)))
    o.data.update()

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
ZT = TIP_Z - Z0
paint = np.ones((NL, 3), np.float32)
zf = np.clip(P[:, 2] / ZT, 0, 1)
ax = np.abs(P[:, 0])
for mi, lo, hi in ((M_STEEL, 0.82, 0.30), (M_WINE, 0.80, 0.34), (M_GOLD, 0.92, 0.14)):
    sel = MI == mi
    paint[sel] *= (lo + hi * zf[sel])[:, None]
sel = MI == M_CRIM
wing = ax > 0.40
s1 = sel & wing
paint[s1] *= (0.52 + 0.62 * np_smooth(0.35, 1.2, ax[s1]))[:, None]      # membranes brighten toward the tips
s2 = sel & ~wing
paint[s2] *= (0.86 + 0.24 * zf[s2])[:, None]
sel = MI == M_RUBY
paint[sel] *= (1.25 - 0.55 * np_smooth(0.0, 0.33, P[sel][:, 2] + Z0))[:, None]  # ruby brightest at its point
sel = MI == M_LEATHER
paint[sel] *= np.array([1.0, 0.95, 0.95], np.float32)

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
    if idx in (M_STEEL, M_WINE):   # soft lengthwise brushed streaks on the steel
        vm = N("ShaderNodeVectorMath")
        vm.operation = "MULTIPLY"
        L(pos, vm.inputs[0])
        vm.inputs[1].default_value = (9.0, 9.0, 1.0)
        nf = N("ShaderNodeTexNoise")
        nf.inputs["Scale"].default_value = 1.0
        L(vm.outputs[0], nf.inputs["Vector"])
        albedo = mix(albedo, grey(remap(nf.outputs["Fac"], 0.3, 0.7, 0.86, 1.12)), 1.0, "MULTIPLY")
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
    rim = remap(dot_light(RIM_DIR), 0.25, 1.0, 0.0, 0.10 if idx in (M_STEEL, M_OBS, M_WINE) else 0.14)
    lit = mix(lit, (0.55, 0.45, 0.75, 1) if idx in (M_STEEL, M_OBS) else (1.0, 0.32, 0.42, 1), rim, "ADD")
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


def symmetry_error(ob):
    """max distance from each vertex's x-mirror to the nearest vertex (0 = exactly symmetric)"""
    co = np.array([tuple(v.co) for v in ob.data.vertices], np.float64)
    co = co[co[:, 2] > GRIP_Z1 + 0.06 - Z0]          # the helical grip wraps are chiral by design
    q = co * np.array([-1, 1, 1])
    worst = 0.0
    for i0 in range(0, len(q), 150):
        d = np.min(np.linalg.norm(q[i0:i0 + 150, None, :] - co[None, :, :], axis=2), axis=1)
        worst = max(worst, float(d.max()))
    return worst


STATS = {o.name: mesh_stats(o) for o in FINAL}
GRIP = V(0, 0, ((GRIP_Z0 + GRIP_Z1) / 2 - Z0) * SCALE)
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
    "blade_axis_studio": [0, 1, 0],
    "blade_flat_normal_studio": [0, 0, 1],
    "notes": ["Every MeshPart imports centred on its own bounding box: place each at its center_studio, "
              "relative to a shared model origin (Blender origin = ruby pommel tip on the blade axis).",
              "grip_point = middle of the wrapped grip on the blade axis (hand pivot); the blade points along +Y "
              "(studio) from the grip, the flat faces look along +/-Z, the bat-wing guard spreads along X.",
              "float_pivot = mid-height point on the blade axis (pivot for the floating idle bob and spin)."],
    "vfx_notes": [
        "Ability (RARITY_GODLY_ARMOR.md section 9): every hit heals, kills send red wisps into the player for extra "
        "healing. Healing still goes through LifeSteal / LifeStealCap, so the visuals never imply uncapped healing.",
        "Kill wisps: on a kill, spawn 3 wisps (5 on elites/bosses) at the dead enemy's HumanoidRootPart + (0, 1.5, 0). "
        "Each wisp = a 0.35-stud Neon ball, Color (255, 12, 44), with a Trail (Lifetime 0.25, WidthScale 1 -> 0, "
        "Color (255, 84, 64) -> (150, 0, 24), Transparency 0 -> 1, LightEmission 1) and a ParticleEmitter (Rate 30, "
        "Lifetime 0.25-0.4, Size 0.35 -> 0, Speed 0, LightEmission 1, LightInfluence 0, Color (255, 40, 60)).",
        "Wisp path: client-side quadratic Bezier from the spawn point to the player's UpperTorso, control point "
        "lifted 3-4 studs and pushed 2-3 studs sideways (random sign per wisp), duration 0.45-0.65 s with ease-in "
        "(they accelerate into the player). Stagger launches by 0.06 s.",
        "Wisp arrival: ParticleEmitter:Emit(8) at the UpperTorso (Size 0.6 -> 0, Speed 4-7, Lifetime 0.3, "
        "SpreadAngle 360, Color (255, 60, 80), LightEmission 1) plus a PointLight (255, 30, 50), Brightness 2, "
        "Range 6, tweened to 0 over 0.25 s. Heal number pops in soft red.",
        "Hit-heal flash (subtle, every hit): Highlight on the player, FillColor (255, 40, 60), FillTransparency 0.85, "
        "OutlineTransparency 1, for 0.12 s; the blade's Glow MeshPart Color pulses (255, 12, 44) -> (255, 120, 110) "
        "-> (255, 12, 44) over 0.18 s; Emit(3) small red sparks (Size 0.2 -> 0, Speed 3, Lifetime 0.2) from the hit "
        "point toward the blade.",
        "Swing trail: Trail between two Attachments on the blade axis (0.3 studs above the guard, and the tip), "
        "Color (255, 12, 44) -> (60, 0, 12), Transparency 0.3 -> 1, Lifetime 0.15, LightEmission 0.6.",
        "Aura (always on while equipped): a ParticleEmitter on an Attachment at mid-blade with a box-shaped spread "
        "(Shape = Box, size about the blade: 0.8 x 3 x 0.3 studs), Rate 6, Lifetime 0.9-1.3, Speed 0.2-0.5, "
        "Size 0.9 -> 1.6 (NumberSequence), Transparency 0.82 -> 1, LightEmission 0.8, LightInfluence 0, "
        "Color (255, 20, 50) -> (120, 0, 20), Texture a soft round glow: a faint red haze hugging the blade. "
        "Pair with a PointLight on the guard, Color (255, 30, 50), Brightness 0.8, Range 7.",
        "Idle (optional, keep subtle): ParticleEmitter at mid-fuller, Rate 2-3, Lifetime 0.8, Speed 0.3, "
        "Acceleration (0, -3, 0), Size 0.1 -> 0, Color (200, 0, 30): slow blood droplets falling off the channel.",
    ],
}
for o in FINAL:
    st = STATS[o.name]
    mn, mx = np.array(st["bounds_min"]), np.array(st["bounds_max"])
    kind = "textured" if o is body else "glow"
    part = {"kind": kind, "center_studio": studio((mn + mx) / 2), "size_studio": studio_size(mx - mn),
            "triangles": st["triangles"]}
    if o is glow_ob:
        part.update(material="Neon", color_rgb=list(GLOW), note="blood crimson: fuller channel, runes, boss gems, langet drops")
    elif o is core_ob:
        part.update(material="Neon", color_rgb=list(CORE), note="hot core: fuller centre line, gem hearts")
    else:
        part.update(material="SmoothPlastic (or Plastic), Color white", texture_id="BaseColor.png")
    install["parts"][o.name] = part
(ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=1))
log("stats", {k: v["triangles"] for k, v in STATS.items()}, "total", sum(v["triangles"] for v in STATS.values()))
SYM = {o.name: round(symmetry_error(o), 6) for o in FINAL}
log("symmetry", SYM)

# ---------------------------------------------------------------------------
# Renders
# ---------------------------------------------------------------------------
setup_comp(0.8)


def shoot_catalog(name, angle, camvec, samples=32, res=1000):
    r = catalog_stage(FINAL, angle, camvec, samples=samples, res=res)
    render(ROOT / name)
    r()


shoot_catalog("Preview.png", CAT_ANGLE, (1.6, -15, 6.2), samples=48)
shoot_catalog("Front.png", 0, (0, -15, 1.2))
shoot_catalog("Back.png", 0, (0, 15, 1.2))
shoot_catalog("Side.png", 0, (15, 0, 1.2))

# scale shot: a 5-stud grey R15 block figure beside the sword
fig_bm = new_bm()
FX = 3.4
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

# readability tile for the sheet only: the catalogue view at 160 px, pixel-enlarged (temp file, deleted)
r = catalog_stage(FINAL, CAT_ANGLE, (1.6, -15, 6.2), samples=24, res=160)
render(ROOT / "_readability_small.png")
r()
im = bpy.data.images.load(str(ROOT / "_readability_small.png"))
a = np.empty(160 * 160 * 4, np.float32)
im.pixels.foreach_get(a)
a = np.repeat(np.repeat(a.reshape(160, 160, 4), 5, axis=0), 5, axis=1)
big = bpy.data.images.new("Readability", 800, 800, alpha=False)
big.pixels.foreach_set(a.ravel())
big.filepath_raw = str(ROOT / "_Readability.png")
big.file_format = "PNG"
big.save()
bpy.data.images.remove(im)
bpy.data.images.remove(big)
os.remove(ROOT / "_readability_small.png")


def hero(name, cam_loc, target, lens=58, res=(1200, 1400), samples=96):
    clear_stage()
    w = scene.world
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.016, 0.014, 0.022, 1)
    cd = bpy.data.cameras.new("Hero camera")
    cam = bpy.data.objects.new("Hero camera", cd)
    REVIEW.objects.link(cam)
    cd.lens = lens
    cam.location = cam_loc
    cam.rotation_euler = (target - cam_loc).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    for nm, loc, col, en, sz in (("Hero key", V(-4, -6, 8), (0.80, 0.86, 1.0), 1150, 4),
                                  ("Hero rim crimson", V(4, 6, 6), (1.0, 0.10, 0.16), 1800, 3),
                                  ("Hero rim steel", V(-5, 5, 5), (0.6, 0.7, 1.0), 900, 3),
                                  ("Hero fill wine", V(2, -5, 0.5), (0.7, 0.3, 0.45), 180, 4)):
        ld = bpy.data.lights.new(nm, "AREA")
        ld.color = col
        ld.energy = en
        ld.size = sz
        lo = bpy.data.objects.new(nm, ld)
        REVIEW.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = (V(0, 0, 2.4) - loc).to_track_quat("-Z", "Y").to_euler()
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.view_settings.view_transform = VIEW_TRANSFORM
    scene.view_settings.look = VIEW_LOOK
    setup_comp(1.3)
    render(ROOT / name)
    setup_comp(0.8)


hero("Hero.png", V(2.1, -7.3, 1.7), V(0.0, 0, 2.42), lens=50)

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
compose([(ROOT / "Preview.png", "Vampire Blade (Godly, new)"), (ASSETS / "32-excalibur" / "Preview.png", "Excalibur"),
         (ASSETS / "31-mjolnir" / "Preview.png", "Mjolnir"), (ASSETS / "34-medusas-head" / "Preview.png", "Medusa's Head")],
        4, 700, ROOT / "Compare_Catalog.png", title="Catalogue framing: Godly Vampire Blade beside the current top-tier weapons")
compose([(ROOT / "Preview.png", "Preview (catalogue 3/4)"), (ROOT / "Front.png", "Front"), (ROOT / "Back.png", "Back"),
         (ROOT / "Side.png", "Side"), (ROOT / "Hero.png", "Hero (Cycles, dark stage)"),
         (ROOT / "Scale.png", "Scale: 5-stud R15 block figure"),
         (ROOT / "_Readability.png", "Readability: 160 px render, pixel-enlarged"),
         (ROOT / "BaseColor.png", "BaseColor.png (1024, baked)")],
        4, 560, ROOT / "Sheet.png", title="Vampire Blade - Godly melee (Blender renders, Studio untested)")
os.remove(ROOT / "_Readability.png")

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
    "x_mirror_symmetry_max_error_studs_guard_and_blade": SYM,
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
    "(wraps on the grip, wings in the boss, langets on the blade), and booleaned rune grooves meet the bevels.",
    "Studio import, Neon look and in-game scale are untested (no Studio access in this task).",
]
(ROOT / "validation.json").write_text(json.dumps(report, indent=1))
log("VALIDATION", json.dumps(report["checks"]), "tris", report["total_triangles"])
log("DONE")
