"""Storm Bow (round 2): Godly weapon (RARITY_GODLY_ARMOR.md section 9: "Ranged. Each arrow splits into 5
mid-air and rains down on a group", with lightning trails).

Run in background Blender 5.2 only (never the user's open scene):
  blender -b --factory-startup --threads 2 --python build_storm_bow.py

Environment switches (all optional):
  MODE=quick     build the model and render flat-colour review shots only (no bake, no exports)
  MODE=full      (default) build, bake the painted texture, export, validate, render everything
  OUT=<dir>      where quick renders go (default: this folder)
  SHOTS=a,b      quick mode: which review shots (catalog,front,side,back,head)

Pipeline parts (scene, bake, export, validation, composites) copied, not imported, from the approved
weapon-models/godly/reapers-scythe pipeline via the v1 bow. The design and modelling are new.

Design: the bow is a thunderbird. A big aggressive recurve whose limbs are its wings:
  - limbs: a dark gunmetal diamond-section core with a long gold-framed zig-zag Neon bolt inlay down the
    belly half of each face, and four overlapping storm-slate armour plates down the back half. Every
    plate has a gold back edge and tapers into a hooked barb that juts out of the back of the limb, so
    the back reads as a serrated row of wing-bone spikes;
  - tips: thick Z-shaped lightning-bolt blades (diamond section, gold chamfer edge, Neon core) out of
    gold crown collars;
  - riser: a storm-eagle head (gold hooked screeching beak, glowing eyes under angry brow blades, swept
    feather-blade crest and ear tufts) clutching a big faceted storm crystal (blue Neon facets around a
    white-hot belt) in gold talons, with a hooked tail plume below; dark leather grip;
  - string: a white-hot core inside a jagged electric-blue Neon ribbon, with crackle forks at the nocks.
Limbs, collars, tips and string are one authored upper half mirrored about the grip (z = 0).

Axes: Blender +z up, the bow lies in the xz plane, the string is on +x (archer side), the head and the
back of the bow face -x (target side), the flat faces look along +/-y.
1 Blender unit = 1 Roblox stud after the final uniform scale. Studio axes are (-x, z, y) of Blender.
"""
import bpy, bmesh, math, json, os, sys, time
import numpy as np
from mathutils import Vector, Matrix
from pathlib import Path

T0 = time.time()
ROOT = Path(__file__).resolve().parent
NAME = "StormBow"
MODE = os.environ.get("MODE", "full")
OUT = Path(os.environ.get("OUT", str(ROOT))).resolve()
OUT.mkdir(parents=True, exist_ok=True)
SHOTS = [s for s in os.environ.get("SHOTS", "catalog,front,side").split(",") if s]
# Khronos PBR Neutral keeps saturated Neon saturated (AgX turns it pastel); EXPOSURE pulls the grey catalogue
# backdrop back to the AgX catalogue renders' brightness so the comparison stays fair.
VIEW = os.environ.get("VIEW", "Khronos PBR Neutral")
EXPOSURE = float(os.environ.get("EXPOSURE", "-0.55" if VIEW.startswith("Khronos") else "0"))
BAKE_SIZE = 1024
TARGET_HEIGHT = 5.0          # hero size in studs; play size is set later in Studio
BLEED_K, BLEED_STRENGTH = 0.10, 0.34   # baked glow light on nearby surfaces


def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)


def V(*a):
    return Vector(a)


Y = V(0, 1, 0)
Z = V(0, 0, 1)

# ---------------------------------------------------------------------------
# Palette. Slot index = material index on every textured mesh.
# flat: quick-preview colour. ramp: painterly noise ramp (sRGB). edge: warm highlight tint on bevels.
# Darks are near-black with a cool cast; highlights are warm. The only bright colour is the Neon.
# ---------------------------------------------------------------------------
PAL = [
    ("Gunmetal", (36, 39, 47), [(0.25, (17, 19, 25)), (0.52, (36, 39, 47)), (0.8, (64, 66, 72))], (214, 196, 168)),
    ("Slate", (57, 62, 72), [(0.25, (29, 32, 41)), (0.52, (57, 62, 72)), (0.8, (96, 98, 104))], (234, 214, 182)),
    ("Gold", (196, 136, 44), [(0.28, (100, 56, 20)), (0.52, (190, 128, 42)), (0.8, (244, 198, 104))], (255, 236, 172)),
    ("Leather", (54, 36, 28), [(0.3, (25, 16, 12)), (0.52, (54, 36, 28)), (0.8, (90, 62, 44))], (158, 118, 86)),
    ("Socket", (14, 15, 19), [(0.4, (8, 8, 11)), (0.75, (24, 25, 30))], (70, 70, 80)),
    ("Silver", (132, 137, 146), [(0.25, (70, 74, 86)), (0.52, (132, 137, 146)), (0.8, (192, 191, 188))], (255, 240, 210)),
]
M_GUN, M_SLATE, M_GOLD, M_LEATHER, M_SOCK, M_SILVER = range(len(PAL))
GLOW = (18, 108, 255)       # Roblox Neon, saturated electric blue
CORE = (214, 240, 255)      # Roblox Neon, white-hot core: string core, crystal belt, pupils, nocking bead
GLOW_STRENGTH = float(os.environ.get("GLOW_STRENGTH", "1.8"))
CORE_STRENGTH = float(os.environ.get("CORE_STRENGTH", "3.4"))


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
# bmesh primitives (from the scythe pipeline; loft gains per-section materials and a gradient layer)
# ---------------------------------------------------------------------------
def grad_layer(bm):
    return bm.verts.layers.float.get("grad") or bm.verts.layers.float.new("grad")


def loft(bm, rings, closed=True, caps=True, mat=0, recalc=True, segmat=None, g=None):
    """Rings of points (or single points for tips). segmat[i] = material of the i-th section segment.
    g = per-ring painterly gradient 0 (dark base) .. 1 (light edge/tip), stored +1 in the 'grad' layer."""
    lay = grad_layer(bm) if g is not None else None
    vr = []
    for k, r in enumerate(rings):
        vs = [bm.verts.new(p) for p in r] if isinstance(r, (list, tuple)) else [bm.verts.new(r)]
        if lay is not None:
            for v in vs:
                v[lay] = g[k] + 1.0
        vr.append(vs)
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
            fc.material_index = segmat[s % len(segmat)] if segmat else mat
            faces.append(fc)
    if closed and caps:
        for ring in (vr[0][::-1], vr[-1]):
            if len(ring) > 2:
                fc = bm.faces.new(ring)
                fc.material_index = segmat[0] if segmat else mat
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


def tube(bm, pts, radii, sides=8, mat=0, flat=1.0, phase=0.0, section=None, up=V(0, 1, 0), caps=True, segmat=None,
         g=None):
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
    return loft(bm, rings, mat=mat, caps=caps, segmat=segmat, g=g)


def lathe(bm, prof, sides=8, M=None, mat=0, phase=None, g=None):
    M = M or Matrix()
    phase = math.pi / sides if phase is None else phase
    rings = []
    for r, z in prof:
        if r <= 1e-6:
            rings.append(M @ V(0, 0, z))
        else:
            rings.append([M @ V(r * math.cos(phase + 2 * math.pi * s / sides), r * math.sin(phase + 2 * math.pi * s / sides), z)
                          for s in range(sides)])
    return loft(bm, rings, mat=mat, g=g)


def box(bm, c, size, M=None, mat=0):
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    Mt = Matrix.Translation(c) @ (M or Matrix())
    r0 = [Mt @ V(-hx, -hy, -hz), Mt @ V(hx, -hy, -hz), Mt @ V(hx, hy, -hz), Mt @ V(-hx, hy, -hz)]
    r1 = [Mt @ V(-hx, -hy, hz), Mt @ V(hx, -hy, hz), Mt @ V(hx, hy, hz), Mt @ V(-hx, hy, hz)]
    return loft(bm, [r0, r1], mat=mat)


def basis(x, y, z):
    return Matrix((x, y, z)).transposed().to_4x4()


def solid(bm, ra, rb, mat=0):
    """Closed solid between two matching (possibly concave) polygons; caps ear-clipped."""
    va = [bm.verts.new(p) for p in ra]
    vb = [bm.verts.new(p) for p in rb]
    n = len(va)
    faces = [bm.faces.new([va[i], va[(i + 1) % n], vb[(i + 1) % n], vb[i]]) for i in range(n)]
    fa = bm.faces.new(va[::-1])
    fb = bm.faces.new(vb)
    res = bmesh.ops.triangulate(bm, faces=[fa, fb], quad_method="BEAUTY", ngon_method="EAR_CLIP")
    faces += res["faces"]
    for f in faces:
        f.material_index = mat
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def lens_solid(bm, polys, ys, mats, mp, capmat, wallmat):
    """Layered lens / diamond-section solid from a 2D profile polygon. polys[0] is the outline (at +/-ys[0]),
    each later poly an inset of it at a higher +/-y; mats[i] colours the chamfer band between layer i and i+1.
    mp(p2d, y) -> 3D point."""
    n = len(polys[0])
    top = [[bm.verts.new(mp(p, y)) for p in poly] for poly, y in zip(polys, ys)]
    bot = [[bm.verts.new(mp(p, -y)) for p in poly] for poly, y in zip(polys, ys)]
    faces = []

    def quad(a, b, c, d, m):
        f = bm.faces.new([a, b, c, d])
        f.material_index = m
        faces.append(f)

    for i in range(n):
        j = (i + 1) % n
        quad(top[0][i], top[0][j], bot[0][j], bot[0][i], wallmat)
        for L in range(len(polys) - 1):
            quad(top[L + 1][i], top[L + 1][j], top[L][j], top[L][i], mats[L])
            quad(bot[L][i], bot[L][j], bot[L + 1][j], bot[L + 1][i], mats[L])
    ft = bm.faces.new(top[-1])
    fb = bm.faces.new(bot[-1][::-1])
    ft.material_index = fb.material_index = capmat
    res = bmesh.ops.triangulate(bm, faces=[ft, fb], quad_method="BEAUTY", ngon_method="EAR_CLIP")
    faces += res["faces"]
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def poly_area(poly):
    return 0.5 * sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1] for i in range(len(poly)))


def inset(poly, d):
    """Mitred inward offset of a simple 2D polygon (lists of (x, y))."""
    sg = 1.0 if poly_area(poly) > 0 else -1.0
    out = []
    n = len(poly)
    for i in range(n):
        p0, p1, p2 = Vector(poly[i - 1]), Vector(poly[i]), Vector(poly[(i + 1) % n])
        e1, e2 = (p1 - p0).normalized(), (p2 - p1).normalized()
        n1, n2 = Vector((-e1.y, e1.x)) * sg, Vector((-e2.y, e2.x)) * sg
        bis = n1 + n2
        if bis.length < 1e-6:
            bis = n1
        bis.normalize()
        c = max(bis.dot(n1), 0.3)
        q = p1 + bis * d / c
        out.append((q.x, q.y))
    return out


def densify(poly, step, closed=True):
    out = []
    n = len(poly)
    for i in range(n if closed else n - 1):
        a, b = Vector(poly[i]), Vector(poly[(i + 1) % n])
        k = max(1, int(math.ceil((b - a).length / step)))
        for j in range(k):
            q = a.lerp(b, j / k)
            out.append((q.x, q.y))
    if not closed:
        out.append(tuple(poly[-1]))
    return out


def strip_poly(pts, hws):
    """Closed outline of a mitred strip along a 2D polyline; a zero half-width end becomes a sharp point."""
    P = [Vector(p) for p in pts]
    n = len(P)
    Lf, Rt = [], []
    for i in range(n):
        if i == 0:
            d = (P[1] - P[0]).normalized()
            m = Vector((-d.y, d.x))
        elif i == n - 1:
            d = (P[-1] - P[-2]).normalized()
            m = Vector((-d.y, d.x))
        else:
            d1, d2 = (P[i] - P[i - 1]).normalized(), (P[i + 1] - P[i]).normalized()
            n1, n2 = Vector((-d1.y, d1.x)), Vector((-d2.y, d2.x))
            b = n1 + n2
            b.normalize()
            m = b / max(b.dot(n1), 0.4)
        Lf.append(P[i] + m * hws[i])
        Rt.append(P[i] - m * hws[i])
    poly = []
    if hws[0] <= 1e-6:
        poly.append(P[0])
        Lf, Rt = Lf[1:], Rt[1:]
        endpt = None
    if hws[-1] <= 1e-6:
        endpt = P[-1]
        Lf, Rt = Lf[:-1], Rt[:-1]
    else:
        endpt = None
    poly += Lf + ([endpt] if endpt is not None else []) + Rt[::-1]
    return [(p.x, p.y) for p in poly]


# Z-shaped lightning bolt outline in (u across, v along): v = 0 is the wide root, v = 1 the point.
BOLTZ = [(0.45, 0.0), (0.65, 0.0), (0.50, 0.30), (0.82, 0.30), (0.57, 0.62), (0.80, 0.62), (0.22, 1.0),
         (0.48, 0.70), (0.35, 0.70), (0.60, 0.38), (0.30, 0.38)]
BOLT_SPINE = [(0.03, 0.55), (0.31, 0.44), (0.35, 0.69), (0.64, 0.48), (0.67, 0.66), (0.93, 0.27)]   # (v, u) stroke centres

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


GLOW_MAT = emit_mat(f"{NAME}_Glow", GLOW, GLOW_STRENGTH)
CORE_MAT = emit_mat(f"{NAME}_GlowCore", CORE, CORE_STRENGTH)
PARTS = []


def new_bm():
    return bmesh.new()


def make_obj(name, bm, kind="tex", smooth=False, coll=None, gfn=None):
    if kind in ("tex", "cut"):
        lay = grad_layer(bm)
        for v in bm.verts:
            val = v[lay]
            v[lay] = (val - 1.0) if val > 0.5 else (gfn(v.co) if gfn else 0.5)
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


def add_bevel(ob, width, segs=2, angle=30.0, profile=0.55, harden=True, miter="MITER_ARC"):
    m = ob.modifiers.new("Bevel", "BEVEL")
    m.width = width
    m.segments = segs
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle)
    m.profile = profile
    m.use_clamp_overlap = True
    m.harden_normals = harden and segs > 1
    m.miter_outer = miter
    return m


def add_wn(ob):
    m = ob.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
    m.keep_sharp = True
    m.weight = 50
    m.mode = "FACE_AREA"
    return m


def mirror_z(ob):
    """Upper half authored; the lower half is its mirror about the grip (z = 0)."""
    m = ob.modifiers.new("MirrorZ", "MIRROR")
    m.use_axis = (False, False, True)
    m.use_mirror_merge = False
    return ob


def hard(ob, width=0.012, segs=2, angle=30.0, miter="MITER_ARC"):
    for p in ob.data.polygons:
        p.use_smooth = True
    add_bevel(ob, width, segs=segs, angle=angle, miter=miter)
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


def ring_band(bm, z, r_in, r_out, h, sides=10, mat=M_GOLD, crown=0.0, M=None, ry_scale=1.0, crown_down=False):
    """Band around local z; crown > 0 raises every other top (or bottom) vertex into points."""
    M = M or Matrix()
    rings = []
    n = sides * (2 if crown else 1)
    prof = [(r_in, -h / 2), (r_out, -h / 2 + 0.014), (r_out, h / 2 - 0.014), (r_in, h / 2)]
    for j, (r, dz) in enumerate(prof):
        ring = []
        for s in range(n):
            a = math.pi / n + 2 * math.pi * s / n
            zz = z + dz
            if crown and s % 2 == 0 and ((j >= 2 and not crown_down) or (j < 2 and crown_down)):
                zz += -crown if crown_down else crown
            ring.append(M @ V(r * math.cos(a), r * math.sin(a) * ry_scale, zz))
        rings.append(ring)
    return loft(bm, rings, mat=mat)


# Blade section: diamond with a centre ridge and gold edge bands. (a = in-plane width, b = thickness)
SEC_BLADE = [(1, 0), (0.70, 0.52), (0, 1), (-0.70, 0.52), (-1, 0), (-0.70, -0.52), (0, -1), (0.70, -0.52)]
MAT_BLADE = [M_GOLD, M_SLATE, M_SLATE, M_GOLD, M_GOLD, M_SLATE, M_SLATE, M_GOLD]


def tip_silver(faces, nsec, k0, segs):
    """Faces of ring pairs >= k0 in the given section segments become light silver steel (bone-spike read)."""
    for idx, f in enumerate(faces):
        k, sgi = divmod(idx, nsec)
        if k >= k0 and sgi in segs and f.material_index == M_SLATE:
            f.material_index = M_SILVER


def blade(bm, pts, widths, thick, mat_edges=True, g0=0.3, g1=1.0, up=Y, silver_from=None):
    n = len(pts)
    faces = tube(bm, pts, [(w, t) for w, t in zip(widths, thick)], section=SEC_BLADE, up=up,
                 segmat=MAT_BLADE if mat_edges else [M_SLATE] * 8, g=[lerp(g0, g1, k / (n - 1)) for k in range(n)])
    if silver_from is not None:
        tip_silver(faces, 8, silver_from, {1, 2, 5, 6})
    return faces


# ---------------------------------------------------------------------------
# Layout (authored units, grip centre at the origin; scaled to 5 studs tall at the end).
# Upper limb centreline: a cubic Bezier rising from the riser, bowing toward the string (+x), then
# recurving hard back toward -x at the tip.
# ---------------------------------------------------------------------------
LP = [V(0.02, 0, 0.80), V(0.0, 0, 1.40), V(1.60, 0, 1.80), V(0.20, 0, 2.32)]


def bez(t):
    u = 1 - t
    return LP[0] * u ** 3 + LP[1] * (3 * u * u * t) + LP[2] * (3 * u * t * t) + LP[3] * t ** 3


def bez_d(t):
    u = 1 - t
    return (LP[1] - LP[0]) * (3 * u * u) + (LP[2] - LP[1]) * (6 * u * t) + (LP[3] - LP[2]) * (3 * t * t)


_TT = np.linspace(0, 1, 801)
_PP = [bez(float(t)) for t in _TT]
_LL = np.concatenate([[0.0], np.cumsum([(_PP[i + 1] - _PP[i]).length for i in range(800)])])
LIMB_LEN = float(_LL[-1])


def limb_at(s):
    """s = arc-length fraction 0 (riser) .. 1 (tip). Returns point, tangent, back normal (toward -x side)."""
    t = float(np.interp(s * LIMB_LEN, _LL, _TT))
    T = bez_d(t).normalized()
    return bez(t), T, V(-T.z, 0, T.x)


def rx(s):      # half thickness in the bow plane (back <-> belly)
    return lerp(0.34, 0.14, s ** 0.9)


def ry(s):      # half width across the faces (y): the plateau height of the core
    return lerp(0.21, 0.11, s)


def lmap(s, c, y):
    p, T, N = limb_at(s)
    return p + N * c + Y * y


def core_sec(s):
    r, w = rx(s), ry(s)
    i, ye = 0.24 * r, 0.34 * w
    return [(r, ye), (r - i, w), (-r + i, w), (-r, ye), (-r, -ye), (-r + i, -w), (r - i, -w), (r, -ye)]


def belly(s):
    p, T, N = limb_at(s)
    return p - N * (rx(s) + 0.03), N


S_NOCK = 0.925
_ss = np.linspace(0.3, S_NOCK, 140)
S_TAN = float(_ss[int(np.argmax([belly(float(s))[0].x for s in _ss]))])
RC = 0.036                      # string white-hot core radius
STRING_X = belly(S_TAN)[0].x + RC + 0.006
REST_Z = 0.42                   # arrow rest / nocking height (upper side of the grip)
HEAD_Z = 0.80
TAIL_Z = -0.80
HEAD_S, TAIL_S, CRYSTAL_S = 1.40, 1.25, 1.25
CC = V(-0.66, 0, 0)            # storm crystal centre
log(f"limb length {LIMB_LEN:.3f}, tangent s {S_TAN:.3f}, string x {STRING_X:.3f}")


# ---------------------------------------------------------------------------
# Limbs
# ---------------------------------------------------------------------------
def build_limb_core():
    bm = new_bm()
    n = 22
    ss = [k / n for k in range(n + 1)]
    rings = [[lmap(s, c, y) for c, y in core_sec(s)] for s in ss]
    loft(bm, rings, segmat=[M_GUN] * 8, g=[0.25 + 0.6 * s for s in ss])
    ob = make_obj("LimbCore", bm, smooth=True)
    mirror_z(ob)
    hard(ob, 0.012, segs=1, angle=26)
    # gold belly edge strip (string side)
    bm = new_bm()
    s0, s1 = 0.05, 0.93
    rings, gs = [], []
    for k in range(17):
        s = s0 + (s1 - s0) * k / 16
        r, w = rx(s), ry(s)
        f = smoothstep(0.0, 0.05, s - s0) * (1 - 0.6 * smoothstep(0.85, 1.0, (s - s0) / (s1 - s0)))
        hy = (0.34 * w + 0.026) * (0.6 + 0.4 * f)
        sec = [(-r + 0.03, hy), (-r - 0.012, hy * 0.92), (-r - 0.03, 0.0), (-r - 0.012, -hy * 0.92), (-r + 0.03, -hy)]
        rings.append([lmap(s, c, y) for c, y in sec])
        gs.append(0.5)
    loft(bm, rings, mat=M_GOLD, g=gs)
    ob = make_obj("BellyTrim", bm, smooth=True)
    mirror_z(ob)
    add_wn(ob)


INLAY = [(0.07, -0.40), (0.17, -0.62), (0.205, -0.26), (0.33, -0.60), (0.365, -0.24), (0.50, -0.58),
         (0.535, -0.25), (0.66, -0.57), (0.69, -0.28), (0.80, -0.52), (0.82, -0.34), (0.89, -0.42)]


def strip_rings(pts, hws, step):
    """Left/right point pairs along a mitred 2D strip, resampled every ~step (zero half-width = point)."""
    P = [Vector(p) for p in pts]
    n = len(P)
    M = []
    for i in range(n):
        if i == 0 or i == n - 1:
            d = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized()
            M.append(Vector((-d.y, d.x)))
        else:
            d1, d2 = (P[i] - P[i - 1]).normalized(), (P[i + 1] - P[i]).normalized()
            n1, n2 = Vector((-d1.y, d1.x)), Vector((-d2.y, d2.x))
            b = (n1 + n2).normalized()
            M.append(b / max(b.dot(n1), 0.4))
    out = []
    for i in range(n - 1):
        k = max(1, int(math.ceil((P[i + 1] - P[i]).length / step)))
        for j in range(k + (1 if i == n - 2 else 0)):
            t = j / k
            c = P[i].lerp(P[i + 1], t)
            m = M[i].lerp(M[i + 1], t)
            h = lerp(hws[i], hws[i + 1], t)
            out.append((c, m, h))
    return out


def build_inlays():
    """A long gold-framed zig-zag Neon bolt down the belly half of each limb face (lofted strips)."""
    pts = [(s * LIMB_LEN, q * rx(s)) for s, q in INLAY]
    n = len(pts)
    hw = [0.0] + [0.026 * (1 - 0.45 * INLAY[i][0]) for i in range(1, n - 1)] + [0.0]
    hwg = [0.0] + [h + 0.022 for h in hw[1:-1]] + [0.0]

    def to3d(q, y, sgn):
        s = min(max(q.x / LIMB_LEN, 0.0), 1.0)
        return lmap(s, q.y, sgn * (ry(s) + y))

    def strip(bm, hws, y0, y1, mat, sgn, ext=0.0):
        rings = []
        for c, m, h in strip_rings(pts, hws, 0.07):
            if h <= 1e-6:
                rings.append(to3d(c, (y0 + y1) / 2, sgn))
                continue
            L, R = c + m * h, c - m * h
            rings.append([to3d(L, y0, sgn), to3d(R, y0, sgn), to3d(R, y1, sgn), to3d(L, y1, sgn)])
        loft(bm, rings, mat=mat)

    bg, bn = new_bm(), new_bm()
    for sgn in (1, -1):
        strip(bg, hwg, -0.014, 0.016, M_GOLD, sgn)
        strip(bn, hw, -0.008, 0.028, 0, sgn)
    ob = make_obj("InlayGold", bg, smooth=False)
    mirror_z(ob)
    ob = make_obj("Inlay_Glow", bn, kind="glow")
    mirror_z(ob)


PLATES = [(0.00, 0.35, 0.44), (0.19, 0.54, 0.42), (0.38, 0.73, 0.38), (0.57, 0.90, 0.32)]   # (s0, s1, barb height)


def build_plates():
    """Overlapping storm-slate armour plates on the back half; each tapers into a hooked barb."""
    bm = new_bm()
    npl = len(PLATES)
    for k, (a, b, H) in enumerate(PLATES):
        lift = 0.02 * (npl - 1 - k)
        tip_c = rx(b) + H
        _, Tb, Nb = limb_at(b)
        Nfix = (Nb + Tb * 0.45).normalized()        # barbs lean toward the limb tip and never fold

        def pmap(s_, c, y, Nfix=Nfix):
            r_ = rx(s_)
            if c <= r_:
                return lmap(s_, c, y)
            p_, T_, N_ = limb_at(s_)
            return p_ + N_ * r_ + Nfix * (c - r_) + Y * y

        NR = 10
        rings, gs = [], []
        for j in range(NR + 1):
            u = j / NR
            s = a + (b - a) * u
            r, w = rx(s), ry(s)
            if j == NR:
                rings.append(pmap(s, tip_c, 0.0))
                gs.append(1.0)
                break
            g = smoothstep(0.28, 1.0, u)
            e_out = 1 - (1 - g) ** 2.4
            e_in = g ** 1.35
            c_in = lerp(0.05 * r, tip_c, e_in)
            c_out = lerp(1.07 * r, tip_c, e_out)
            f = (1 - g) ** 0.7
            start = 0.62 + 0.38 * smoothstep(0.0, 0.06, u)        # chamfered start of the plate
            y_in = (w + 0.035 + lift) * f * start
            y_lo = max(0.02, (w - 0.04) * (1 - e_in))
            y_r = (w + 0.075 + lift) * f * start
            y_e = 0.026 * f + 0.004
            c_m = lerp(c_in, c_out, 0.40)
            te = min(0.05, 0.32 * (c_out - c_m)) / max(c_out - c_m, 1e-4)
            c_e2, y_e2 = lerp(c_out, c_m, te), lerp(y_e, y_r, te) + 0.006 * f
            sec = [(c_out, y_e), (c_e2, y_e2), (c_m, y_r), (c_in, y_in), (c_in, y_lo),
                   (c_in, -y_lo), (c_in, -y_in), (c_m, -y_r), (c_e2, -y_e2), (c_out, -y_e)]
            rings.append([pmap(s, c, y) for c, y in sec])
            gs.append(0.18 + 0.82 * u)
        segmat = [M_GOLD, M_SLATE, M_SLATE, M_GUN, M_GUN, M_GUN, M_SLATE, M_SLATE, M_GOLD, M_GOLD]
        faces = loft(bm, rings, segmat=segmat, g=gs)
        tip_silver(faces, 10, int(NR * 0.5), {1, 2, 6, 7})
    ob = make_obj("LimbPlates", bm, smooth=True)
    mirror_z(ob)
    hard(ob, 0.008, segs=1, angle=24)


def ell_band(bm, s, ra, rb, h, n=16, crown=0.0, mat=M_GOLD):
    """Elliptical collar around the limb at s; crown points toward the limb tip."""
    p, T, N = limb_at(s)
    rings = []
    prof = [(0.86, -h / 2), (1.0, -h / 2 + 0.016), (1.0, h / 2 - 0.016), (0.86, h / 2)]
    for j, (f, dz) in enumerate(prof):
        ring = []
        for i in range(n):
            ang = 2 * math.pi * (i + 0.5) / n
            zz = dz + (crown if (crown and j >= 2 and i % 2 == 0) else 0.0)
            ring.append(p + N * (math.cos(ang) * ra * f) + Y * (math.sin(ang) * rb * f) + T * zz)
        rings.append(ring)
    return loft(bm, rings, mat=mat, g=[0.3, 0.6, 0.8, 1.0])


def build_collars():
    bm = new_bm()
    ell_band(bm, 0.035, rx(0.035) + 0.06, ry(0.035) + 0.15, 0.17, n=10, crown=0.09)
    ell_band(bm, 0.115, rx(0.115) + 0.035, ry(0.115) + 0.11, 0.06, n=10)
    ell_band(bm, 0.945, rx(0.945) + 0.05, ry(0.945) + 0.07, 0.13, n=10, crown=0.07)
    ob = make_obj("Collars", bm, smooth=True)
    mirror_z(ob)
    hard(ob, 0.008, segs=1, angle=30)


def build_tips():
    """Z-shaped lightning-bolt blades: diamond section, gold chamfer edge, Neon core."""
    p1, T0_, N0_ = limb_at(1.0)
    base = p1 - T0_ * 0.12
    T1 = (Matrix.Rotation(math.radians(-38), 3, "Y") @ T0_).normalized()   # tilt the bolt up toward +z
    if T1.z < T0_.z:
        T1 = (Matrix.Rotation(math.radians(38), 3, "Y") @ T0_).normalized()
    N1 = V(-T1.z, 0, T1.x)
    Lb, W = 1.45, 1.05
    outer = densify([(v * Lb, (u - 0.55) * W) for u, v in BOLTZ], 0.14)

    def mp(q, y):
        return base + T1 * q[0] + N1 * q[1] + Y * y

    bm = new_bm()
    lens_solid(bm, [outer, inset(outer, 0.036)], [0.045, 0.125], [M_GOLD], mp, capmat=M_GOLD, wallmat=M_GOLD)
    ob = make_obj("TipBolts", bm, smooth=True,
                  gfn=lambda co: min(1.0, 0.3 + 0.7 * (co - base).dot(T1) / Lb))
    mirror_z(ob)
    hard(ob, 0.008, segs=1, angle=30, miter="MITER_SHARP")
    bm = new_bm()
    core = inset(outer, 0.044)
    lens_solid(bm, [core, inset(outer, 0.06)], [0.105, 0.15], [0], mp, capmat=0, wallmat=0)
    ob = make_obj("TipBolt_Glow", bm, kind="glow")
    mirror_z(ob)
    # white-hot centre line down each bolt (a thin zig strip following the bolt's strokes)
    spine = [(v * Lb, (u - 0.55) * W) for v, u in BOLT_SPINE]
    bm = new_bm()
    for sg in (1, -1):
        rings = []
        for c, m, h in strip_rings(spine, [0.0, 0.017, 0.017, 0.017, 0.015, 0.0], 0.08):
            if h <= 1e-6:
                rings.append(mp((c.x, c.y), sg * 0.158))
                continue
            L_, R_ = c + m * h, c - m * h
            rings.append([mp((L_.x, L_.y), sg * 0.14), mp((R_.x, R_.y), sg * 0.14), mp((R_.x, R_.y), sg * 0.166),
                          mp((L_.x, L_.y), sg * 0.166)])
        loft(bm, rings, mat=0)
    ob = make_obj("TipBoltSpine_Core", bm, kind="core")
    mirror_z(ob)


# ---------------------------------------------------------------------------
# Riser, grip, arrow rest
# ---------------------------------------------------------------------------
R_UP = [(0.21, 0.0), (0.21, 0.33), (0.29, 0.41), (0.26, 0.60), (0.22, 0.80), (0.18, 0.98), (0.02, 1.08),
        (-0.18, 1.02), (-0.27, 0.82), (-0.33, 0.56), (-0.37, 0.28), (-0.35, 0.0)]


def build_riser():
    poly = R_UP + [(x, -z) for x, z in reversed(R_UP[1:-1])]
    poly = densify(poly, 0.12)
    bm = new_bm()
    lens_solid(bm, [poly, inset(poly, 0.05)], [0.13, 0.20], [M_GUN], lambda q, y: V(q[0], y, q[1]),
               capmat=M_GUN, wallmat=M_GUN)
    ob = make_obj("Riser", bm, smooth=True, gfn=lambda co: 0.25 + 0.5 * abs(co.z))
    hard(ob, 0.012, segs=1, angle=28, miter="MITER_SHARP")


GRIP_X = 0.03


def build_grip():
    bm = new_bm()
    z0, z1, pitch = -0.33, 0.33, 0.072
    Rx, Ry = 0.19, 0.225
    turns = (z1 - z0) / pitch
    steps = int(turns * 8)
    wdt, th = pitch * 1.02, 0.03
    rings = []
    for k in range(steps + 1):
        a = 2 * math.pi * turns * k / steps
        z = z0 + (z1 - z0) * k / steps
        rad = V(math.cos(a) * Rx, math.sin(a) * Ry, 0)
        dn = V(math.cos(a) / Rx, math.sin(a) / Ry, 0).normalized()
        c = V(GRIP_X, 0, z) + rad
        sec = [(-th * 0.5, -wdt * 0.5), (th * 0.25, -wdt * 0.45), (th * 0.6, 0.0), (th * 0.25, wdt * 0.45), (-th * 0.5, wdt * 0.5)]
        rings.append([c + dn * a_ + V(0, 0, b_) for a_, b_ in sec])
    loft(bm, rings, mat=M_LEATHER)
    make_obj("GripWrap", bm, smooth=False)
    # gold crown bands framing the grip
    bm = new_bm()
    M = Matrix.Translation(V(GRIP_X, 0, 0))
    ring_band(bm, 0.375, 0.17, 0.235, 0.07, sides=8, crown=0.045, M=M, ry_scale=1.12)
    ring_band(bm, -0.375, 0.17, 0.235, 0.07, sides=8, crown=0.045, M=M, ry_scale=1.12, crown_down=True)
    ob = make_obj("GripBands", bm, smooth=True)
    hard(ob, 0.007, segs=1, angle=30)


def build_rest():
    """Neon arrow rest on the -y face just above the grip, on a gold bracket (one-sided)."""
    bm = new_bm()
    poly = [(-0.06, REST_Z - 0.018), (0.08, REST_Z - 0.018), (0.12, REST_Z), (0.08, REST_Z + 0.018),
            (-0.06, REST_Z + 0.018), (-0.03, REST_Z)]
    solid(bm, [V(x, -0.33, z) for x, z in poly], [V(x, -0.20, z) for x, z in poly], mat=0)
    make_obj("ArrowRest_Glow", bm, kind="glow")
    bm = new_bm()
    poly = [(-0.04, 0.36), (0.09, 0.36), (0.11, REST_Z - 0.016), (-0.07, REST_Z - 0.016)]
    solid(bm, [V(x, -0.32, z) for x, z in poly], [V(x, -0.18, z) for x, z in poly], mat=M_GOLD)
    ob = make_obj("RestBracket", bm, smooth=True)
    hard(ob, 0.008, segs=1, angle=35)


# ---------------------------------------------------------------------------
# Focal piece: storm-eagle head, crystal in talons, tail plume
# ---------------------------------------------------------------------------
HEAD = [(-0.06, 0.15, 0.19, -0.19), (-0.20, 0.21, 0.29, -0.25), (-0.36, 0.235, 0.31, -0.25),
        (-0.50, 0.21, 0.25, -0.22), (-0.60, 0.16, 0.17, -0.18)]


def head_ring(x, w, zt, zb, zc):
    h = zt - zb
    pts = [(0, zt), (0.60 * w, zt - 0.07 * h), (w, zt - 0.32 * h), (w, zb + 0.36 * h), (0.70 * w, zb + 0.05 * h), (0, zb)]
    ring = pts + [(-y, z) for y, z in reversed(pts[1:-1])]
    return [V(x, y, zc + z) for y, z in ring]


SEC_BEAK = [(-1, 0), (-0.55, 0.62), (0.3, 0.96), (1.0, 0.72), (1.0, -0.72), (0.3, -0.96), (-0.55, -0.62)]
SEC_JAW = [(1, 0), (0.55, 0.62), (-0.3, 0.96), (-1.0, 0.72), (-1.0, -0.72), (-0.3, -0.96), (0.55, -0.62)]


def build_head():
    zc = HEAD_Z
    bm = new_bm()
    loft(bm, [head_ring(x, w, zt, zb, zc) for x, w, zt, zb in HEAD], mat=M_SILVER, g=[0.15, 0.4, 0.6, 0.75, 0.85])
    ob = make_obj("Head", bm, smooth=True)
    hard(ob, 0.012, segs=2, angle=24)
    # gold hooked beak (screeching, open) with an electric glow in the mouth
    bm = new_bm()
    up = [V(-0.50, 0, zc + 0.05), V(-0.66, 0, zc + 0.045), V(-0.80, 0, zc + 0.015), V(-0.92, 0, zc - 0.05),
          V(-0.985, 0, zc - 0.15), V(-0.975, 0, zc - 0.25), V(-0.93, 0, zc - 0.32)]
    tube(bm, up, [(0.15, 0.17), (0.13, 0.135), (0.105, 0.10), (0.08, 0.07), (0.06, 0.045), (0.035, 0.028), (0, 0)],
         section=SEC_BEAK, mat=M_GOLD, g=[0.25, 0.4, 0.55, 0.7, 0.85, 0.95, 1.0])
    jaw = [V(-0.50, 0, zc - 0.11), V(-0.63, 0, zc - 0.16), V(-0.75, 0, zc - 0.215), V(-0.84, 0, zc - 0.265)]
    tube(bm, jaw, [(0.07, 0.13), (0.055, 0.10), (0.035, 0.06), (0, 0)], section=SEC_JAW, mat=M_GOLD, g=[0.2, 0.45, 0.7, 0.9])
    ob = make_obj("Beak", bm, smooth=True)
    hard(ob, 0.008, segs=1, angle=28)
    bm = new_bm()
    tube(bm, [V(-0.46, 0, zc - 0.075), V(-0.62, 0, zc - 0.10), V(-0.78, 0, zc - 0.15)], [(0.05, 0.07), (0.035, 0.05), (0, 0)],
         sides=6, mat=0)
    make_obj("Mouth_Glow", bm, kind="glow")
    # angry brow blades, glowing slanted eyes with white-hot pupils
    bm = new_bm()
    for sg in (1, -1):
        pts = [V(-0.20, sg * 0.19, zc + 0.22), V(-0.33, sg * 0.245, zc + 0.175), V(-0.47, sg * 0.25, zc + 0.115),
               V(-0.58, sg * 0.215, zc + 0.05), V(-0.64, sg * 0.18, zc + 0.0)]
        blade(bm, pts, [0.06, 0.06, 0.05, 0.03, 0.0], [0.045, 0.045, 0.04, 0.025, 0.0], mat_edges=False)
    ob = make_obj("Brows", bm, smooth=True)
    hard(ob, 0.006, segs=1, angle=28)
    be, bc = new_bm(), new_bm()
    d = V(-0.94, 0, -0.34).normalized()
    e = V(-d.z, 0, d.x)
    if e.z < 0:
        e = -e
    for sg in (1, -1):
        c = V(-0.42, 0, zc + 0.045)
        wy = 0.232
        eye = [c - d * 0.13, c + e * 0.05 - d * 0.015, c + d * 0.13, c - e * 0.04 + d * 0.025]
        solid(be, [p + Y * sg * (wy - 0.03) for p in eye], [p + Y * sg * (wy + 0.022) for p in eye], mat=0)
        pup = [c - d * 0.06, c + e * 0.02, c + d * 0.06, c - e * 0.017]
        solid(bc, [p + Y * sg * (wy) for p in pup], [p + Y * sg * (wy + 0.032) for p in pup], mat=0)
    make_obj("Eyes_Glow", be, kind="glow")
    make_obj("Pupils_Core", bc, kind="core")


def crest_set(bm, zsign=1.0):
    """Swept feather-blade crest (or, mirrored, the tail feathers) and ear tufts."""
    zc = HEAD_Z * zsign

    def P(x, y, z):
        return V(x, y, zc + z * zsign)

    blade(bm, [P(-0.18, 0, 0.18), P(-0.33, 0, 0.33), P(-0.42, 0, 0.55), P(-0.44, 0, 0.76), P(-0.40, 0, 0.98)],
          [0.10, 0.115, 0.095, 0.06, 0.0], [0.075, 0.07, 0.055, 0.035, 0.0], silver_from=2)
    for sg in (1, -1):
        blade(bm, [P(-0.14, sg * 0.10, 0.16), P(-0.30, sg * 0.15, 0.30), P(-0.44, sg * 0.19, 0.46), P(-0.54, sg * 0.20, 0.62)],
              [0.085, 0.09, 0.06, 0.0], [0.05, 0.05, 0.035, 0.0], silver_from=1)
        blade(bm, [P(-0.20, sg * 0.20, -0.02), P(-0.08, sg * 0.245, 0.04), P(0.06, sg * 0.28, 0.13), P(0.19, sg * 0.29, 0.26),
                   P(0.28, sg * 0.27, 0.40)], [0.065, 0.075, 0.065, 0.042, 0.0], [0.04, 0.042, 0.036, 0.025, 0.0])
        blade(bm, [P(-0.22, sg * 0.19, -0.15), P(-0.08, sg * 0.23, -0.14), P(0.06, sg * 0.25, -0.09), P(0.17, sg * 0.24, -0.01)],
              [0.05, 0.055, 0.04, 0.0], [0.035, 0.035, 0.025, 0.0])


def build_crest(zsign):
    bm = new_bm()
    crest_set(bm, zsign)
    ob = make_obj("CrestFeathers" if zsign > 0 else "TailFeathers", bm, smooth=True)
    hard(ob, 0.007, segs=1, angle=26)


def scale_parts(i0, pivot, k):
    M = Matrix.Translation(pivot) @ Matrix.Scale(k, 4) @ Matrix.Translation(-pivot)
    for o in PARTS[i0:]:
        o.data.transform(M)
        o.data.update()


def build_tail():
    zc = TAIL_Z
    bm = new_bm()
    pts = [V(-0.06, 0, zc), V(-0.26, 0, zc + 0.01), V(-0.44, 0, zc - 0.05), V(-0.56, 0, zc - 0.20), V(-0.60, 0, zc - 0.40),
           V(-0.56, 0, zc - 0.58)]
    sec = [(1, 0), (0.6, 0.75), (0, 1), (-0.6, 0.75), (-1, 0), (-0.6, -0.75), (0, -1), (0.6, -0.75)]
    tube(bm, pts, [(0.20, 0.17), (0.22, 0.20), (0.18, 0.165), (0.12, 0.11), (0.06, 0.055), (0, 0)], section=sec,
         mat=M_SILVER, g=[0.15, 0.35, 0.5, 0.7, 0.9, 1.0])
    ob = make_obj("TailPlume", bm, smooth=True)
    hard(ob, 0.01, segs=2, angle=24)
    bm = new_bm()
    M = Matrix.Translation(V(-0.47, 0, zc - 0.08)) @ Matrix.Rotation(math.radians(-38), 4, "Y")
    ring_band(bm, 0.0, 0.15, 0.205, 0.07, sides=10, M=M, crown=0.0, ry_scale=1.0)
    M = Matrix.Translation(V(-0.575, 0, zc - 0.30)) @ Matrix.Rotation(math.radians(-8), 4, "Y")
    ring_band(bm, 0.0, 0.08, 0.125, 0.05, sides=8, M=M)
    ob = make_obj("TailBands", bm, smooth=True)
    hard(ob, 0.006, segs=1, angle=30)


def crystal_r(z):
    z = abs(z)
    return float(np.interp(z, [0.0, 0.10, 0.24, 0.42], [0.265, 0.25, 0.20, 0.0]))


def build_crystal():
    M = Matrix.Translation(CC)
    bm = new_bm()
    for sg in (1, -1):
        Ms = M @ Matrix.Scale(sg, 4, Z) if sg < 0 else M
        prof = [(0.0, 0.085), (0.25, 0.10), (0.20, 0.24), (0.0, 0.42)]
        lathe(bm, prof, sides=6, M=Ms, mat=0, phase=0.0)
    make_obj("Crystal_Glow", bm, kind="glow")
    bm = new_bm()
    lathe(bm, [(0.0, -0.125), (0.24, -0.125), (0.268, 0.0), (0.24, 0.125), (0.0, 0.125)], sides=6, M=M, mat=0, phase=math.pi / 6)
    make_obj("CrystalHeart_Core", bm, kind="core")
    # gold cuffs (the bird's ankles) above and below, and five talons gripping the crystal
    bm = new_bm()
    for sg in (1, -1):
        Mc = Matrix.Translation(CC + V(0.05, 0, sg * 0.47))
        ring_band(bm, 0.0, 0.09, 0.155, 0.15, sides=6, M=Mc, crown=0.06, crown_down=(sg > 0))
    ob = make_obj("Cuffs", bm, smooth=True)
    hard(ob, 0.007, segs=1, angle=30)
    bm = new_bm()
    claws = [(0.0, 1), (62.0, 1), (-62.0, 1), (128.0, -1), (-128.0, -1)]
    zs = [0.46, 0.36, 0.24, 0.11, -0.01, -0.10, -0.15]
    rad = [0.08, 0.07, 0.078, 0.066, 0.052, 0.03, 0.0]
    for phi, sg in claws:
        dvec = V(-math.cos(math.radians(phi)), math.sin(math.radians(phi)), 0)
        pts = []
        for k, z in enumerate(zs):
            off = 0.03 if k < 4 else (0.012 if k == 4 else -0.025 - 0.02 * (k - 5))
            r = (0.12 if k == 0 else crystal_r(z) + off)
            pts.append(CC + dvec * r + Z * (z * sg))
        tube(bm, pts, [(r_, r_ * 0.8) for r_ in rad], sides=6, mat=M_GOLD, up=Z if abs(phi) > 1 else Y,
             g=[0.3, 0.45, 0.6, 0.7, 0.8, 0.9, 1.0])
    ob = make_obj("Talons", bm, smooth=True)
    add_wn(ob)


# ---------------------------------------------------------------------------
# String: white-hot core inside a jagged electric-blue ribbon, crackle forks near the nocks
# ---------------------------------------------------------------------------
def build_string():
    upper = []
    n = 7
    for k in range(n + 1):
        s = S_NOCK + (S_TAN - S_NOCK) * k / n
        b, N = belly(s)
        upper.append(b - N * (RC + 0.004))
    zt = upper[-1].z
    upper[-1] = V(STRING_X, 0, zt)
    kinks = [(0.10, 0.035), (0.19, -0.03), (0.27, 0.02)]
    mid = [V(STRING_X + dx, 0, zt - dz) for dz, dx in kinks]
    m2 = 10
    mid += [V(STRING_X, 0, (zt - 0.34) - (2 * (zt - 0.34)) * k / m2) for k in range(m2 + 1)]
    mid += [V(STRING_X + dx, 0, -(zt - dz)) for dz, dx in reversed(kinks)]
    lower = [V(p.x, 0, -p.z) for p in reversed(upper)]
    pts = upper + mid + lower
    bm = new_bm()
    tube(bm, pts, [RC] * len(pts), sides=6, mat=0)
    make_obj("String_Core", bm, kind="core")
    # jagged ribbon (in the bow plane, thin in y so the white core shows on both faces)
    bm = new_bm()
    ztop = zt - 0.02
    K = 44
    left, right = [], []
    for k in range(K + 1):
        z = ztop - 2 * ztop * k / K
        env = smoothstep(0.0, 0.10, (ztop - abs(z)))
        jag_l = 0.034 + (0.03 if k % 2 == 0 else 0.0) + (0.014 if k % 5 == 1 else 0.0)
        jag_r = 0.034 + (0.03 if k % 2 == 1 else 0.0) + (0.014 if k % 7 == 3 else 0.0)
        xc = STRING_X
        for dz, dx in kinks:
            if abs(abs(z) - (zt - dz)) < 0.05:
                xc += dx
        left.append((xc - (0.02 + jag_l * env), z))
        right.append((xc + (0.02 + jag_r * env), z))
    poly = left + right[::-1]
    solid(bm, [V(x, -0.017, z) for x, z in poly], [V(x, 0.017, z) for x, z in poly], mat=0)
    # crackle forks off the string near each nock
    for zs_ in (1, -1):
        for z0, ln, ang in ((zt - 0.12, 0.20, 35), (zt - 0.30, 0.16, -30), (zt - 0.46, 0.12, 40)):
            dirv = V(math.cos(math.radians(ang)), 0, math.sin(math.radians(ang)) * zs_)
            p0 = V(STRING_X, 0, z0 * zs_)
            side = V(-dirv.z, 0, dirv.x)
            path = [(0.0, 0.0), (ln * 0.4, 0.035), (ln * 0.65, -0.03), (ln, 0.01)]
            pts2 = [p0 + dirv * a + side * b for a, b in path]
            tube(bm, pts2, [(0.026, 0.014), (0.02, 0.012), (0.014, 0.009), (0.0, 0.0)], sides=4, mat=0, up=Y)
    make_obj("String_Glow", bm, kind="glow")
    # nocking point: white-hot bead between two gold rings
    bm = new_bm()
    c = V(STRING_X, 0, REST_Z)
    lathe(bm, [(0.0, -0.08), (0.075, 0.0), (0.0, 0.08)], sides=6, M=Matrix.Translation(c), mat=0)
    make_obj("Nock_Core", bm, kind="core")
    bm = new_bm()
    for dz in (-0.11, 0.11):
        ring_band(bm, dz, RC * 0.8, RC + 0.035, 0.045, sides=8, M=Matrix.Translation(c))
    ob = make_obj("NockRings", bm, smooth=True)
    hard(ob, 0.005, segs=1, angle=35)


def build_all():
    build_riser()
    build_grip()
    build_rest()
    i0 = len(PARTS)
    build_head()
    build_crest(1.0)
    scale_parts(i0, V(-0.10, 0, HEAD_Z), HEAD_S)
    i0 = len(PARTS)
    build_tail()
    build_crest(-1.0)
    scale_parts(i0, V(-0.06, 0, TAIL_Z), TAIL_S)
    i0 = len(PARTS)
    build_crystal()
    scale_parts(i0, CC, CRYSTAL_S)
    build_limb_core()
    build_inlays()
    build_plates()
    build_collars()
    build_tips()
    build_string()


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
# Review rendering: the weapon catalogue's own stage
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


def setup_comp(bloom=0.45, halo=1.0):
    """Mild bloom on the whole image plus a blue halo grown from the Emit pass only (Neon radiates a haze,
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
        g.inputs["Threshold"].default_value = 0.6
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
        h.inputs["Saturation"].default_value = 1.6
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


WORLD = float(os.environ.get("WORLD", "0.0509"))


def catalog_stage(objs, angle, camvec, res=1000, samples=24, ortho_pad=1.18, focus=None, world=None, floor=True,
                  extra_objs=(), ortho=None):
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
    aim = (rot @ focus - V(0, 0, minz)) if focus is not None else center   # focus is given in authored coords

    def point(o, p):
        o.rotation_euler = (Vector(p) - o.location).to_track_quat("-Z", "Y").to_euler()

    point(cam, aim)
    cd.type = "ORTHO"
    bpy.context.view_layer.update()
    inv = cam.rotation_euler.to_matrix().transposed()
    if ortho:
        cd.ortho_scale = ortho
    elif focus is None:
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
    world = WORLD if world is None else world
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (world, world, world, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = VIEW
    scene.view_settings.look = "None"
    scene.view_settings.exposure = EXPOSURE
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


CAM = {"catalog": (-12, (1.6, -15, 6.2)), "front": (0, (0, -15, 1.2)), "back": (0, (0, 15, 1.2)), "side": (0, (15, 0, 1.2))}

if MODE == "quick":
    setup_comp(0.45, 1.0)
    objs = asset_objs()
    for o in objs:
        co = np.array([tuple(v.co) for v in o.data.vertices])
        if len(co) == 0 or not np.isfinite(co).all() or np.abs(co).max() > 6:
            log("BAD GEOMETRY", o.name, len(co), co.min(axis=0).round(2), co.max(axis=0).round(2))
    for shot in SHOTS:
        if shot == "head":
            r = catalog_stage(objs, -12, (1.6, -15, 6.2), res=700, samples=16, focus=V(-0.45, 0, 0.35), ortho=2.6)
        else:
            ang, vec = CAM[shot]
            r = catalog_stage(objs, ang, vec, res=640, samples=12)
        render(OUT / f"q_{shot}.png")
        r()
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
GRIP = V(GRIP_X * SCALE, 0, -Z0 * SCALE)
log(f"authored height {H0:.3f} -> scale {SCALE:.4f}")

_by_kind = {k: [o for o in PARTS if o["kind"] == k] for k in ("tex", "glow", "core")}
body = join(_by_kind["tex"], NAME)
glow_ob = join(_by_kind["glow"], f"{NAME}_Glow")
core_ob = join(_by_kind["core"], f"{NAME}_GlowCore")
PARTS = [body, glow_ob, core_ob]
FINAL = [body, glow_ob, core_ob]
for o in FINAL:
    clean_degenerate(o)
for o in FINAL:
    while o.data.uv_layers:
        o.data.uv_layers.remove(o.data.uv_layers[0])
    for a in [a.name for a in o.data.color_attributes]:
        o.data.color_attributes.remove(o.data.color_attributes[a])
for o in (glow_ob, core_ob):
    if "grad" in o.data.attributes:
        o.data.attributes.remove(o.data.attributes["grad"])
for o, m in ((glow_ob, GLOW_MAT), (core_ob, CORE_MAT)):
    o.data.materials.clear()
    o.data.materials.append(m)
    for p in o.data.polygons:
        p.material_index = 0
        p.use_smooth = False

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
    return co[vi], pn.reshape(-1, 3)[lp], pm[lp], vi


def np_smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


P, NRM, MI, VI = corner_arrays(body.data)
NL = len(P)
gv = np.full(len(body.data.vertices), 0.5, np.float32)
if "grad" in body.data.attributes:
    body.data.attributes["grad"].data.foreach_get("value", gv)
    body.data.attributes.remove(body.data.attributes["grad"])
G = np.clip(gv[VI], 0, 1)
paint = np.ones((NL, 3), np.float32)
dz = np.abs(P[:, 2] - GRIP.z) / (TARGET_HEIGHT / 2)       # 0 at the grip, 1 at the tips
for mi, lo, hi in ((M_GUN, 0.78, 0.42), (M_SLATE, 0.72, 0.52)):
    sel = MI == mi
    if sel.any():
        paint[sel] *= (lo + hi * np_smooth(0.0, 1.0, G[sel]))[:, None]
        # a touch cooler toward the tips (storm sky), warmer near the gold grip
        paint[sel] *= np.stack([1 - 0.03 * dz[sel], np.ones(sel.sum()), 1 + 0.03 * dz[sel]], axis=1)
sel = MI == M_GOLD
paint[sel] *= (0.82 + 0.30 * np_smooth(0.0, 1.0, G[sel]))[:, None]
sel = MI == M_LEATHER
paint[sel] *= (0.9 + 0.2 * np_smooth(0.0, 0.35, 0.35 - np.abs(P[sel][:, 2] - GRIP.z)))[:, None]

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
    w = gA[None, :] * wrap * np.exp(-d / 0.08) / (d * d + 0.03 ** 2)
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
    if idx in (M_GUN, M_SLATE):   # soft brushed streaks
        vm = N("ShaderNodeVectorMath")
        vm.operation = "MULTIPLY"
        L(pos, vm.inputs[0])
        vm.inputs[1].default_value = (6.0, 6.0, 1.0)
        nf = N("ShaderNodeTexNoise")
        nf.inputs["Scale"].default_value = 1.2
        L(vm.outputs[0], nf.inputs["Vector"])
        albedo = mix(albedo, grey(remap(nf.outputs["Fac"], 0.3, 0.7, 0.88, 1.1)), 1.0, "MULTIPLY")
    k = dot_light(KEY_DIR)
    light = remap(k, 0.0, 1.0, 0.56, 1.22)
    tint = mix((0.88, 0.92, 1.06, 1), (1.09, 1.0, 0.88, 1), k)
    ao = N("ShaderNodeAmbientOcclusion")
    ao.samples = 16
    ao.inputs["Distance"].default_value = 0.28
    aof = remap(ao.outputs["AO"], 0.2, 1.0, 0.45, 1.0)
    cav = N("ShaderNodeAmbientOcclusion")
    cav.samples = 16
    cav.inputs["Distance"].default_value = 0.045
    cavf = remap(cav.outputs["AO"], 0.35, 1.0, 0.55, 1.0)
    sep = N("ShaderNodeSeparateXYZ")
    L(pos, sep.inputs["Vector"])
    height = remap(sep.outputs["Z"], 0.0, ZTOP, 0.94, 1.03)
    shade = math_("MULTIPLY", math_("MULTIPLY", light, aof), math_("MULTIPLY", cavf, height))
    lit = mix(mix(albedo, tint, 1.0, "MULTIPLY"), grey(shade), 1.0, "MULTIPLY")
    rim = remap(dot_light(RIM_DIR), 0.25, 1.0, 0.0, 0.10)
    lit = mix(lit, (0.6, 0.72, 1.0, 1), math_("MULTIPLY", rim, 0.6), "ADD")
    bev = N("ShaderNodeBevel")
    bev.samples = 8
    bev.inputs["Radius"].default_value = 0.016
    ed = N("ShaderNodeVectorMath")
    ed.operation = "DOT_PRODUCT"
    L(bev.outputs["Normal"], ed.inputs[0])
    L(tn, ed.inputs[1])
    e = remap(ed.outputs["Value"], 0.99, 0.84, 0.0, 1.0)
    convex = remap(cav.outputs["AO"], 0.86, 0.97, 0.0, 1.0)
    efac = math_("MULTIPLY", math_("MULTIPLY", e, convex), remap(k, 0.0, 1.0, 0.5, 0.9))
    ecol = mix(albedo, rgba(edge_c), 0.62 if idx != M_GOLD else 0.5)
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
bs.inputs["Roughness"].default_value = 0.6
bs.inputs["Specular IOR Level"].default_value = 0.28
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
allmn = np.min([s["bounds_min"] for s in STATS.values()], axis=0)
allmx = np.max([s["bounds_max"] for s in STATS.values()], axis=0)
FLOAT_PIVOT = GRIP.copy()
tex_c = (np.array(STATS[NAME]["bounds_min"]) + np.array(STATS[NAME]["bounds_max"])) / 2
REST_POINT = V(0.02 * SCALE, -0.30 * SCALE, (REST_Z - Z0) * SCALE)
NOCK_POINT = V(STRING_X * SCALE, 0, (REST_Z - Z0) * SCALE)
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
    "arrow_rest_point_studio": studio(REST_POINT),
    "nocking_point_studio": studio(NOCK_POINT),
    "arrow_direction_studio": studio(V(-1, 0, 0)),
    "notes": ["Every MeshPart imports centred on its own bounding box: place each at its center_studio, "
              "relative to a shared model origin (Blender origin = bottom of the bow on the grip axis).",
              "grip_point = middle of the dark leather wrap (hand pivot); the bow is held upright, string toward the "
              "player; the eagle head and crystal face the target (Studio -x of the bow faces the target, i.e. arrows "
              "fly along arrow_direction).",
              "float_pivot = the grip point too (the limbs are symmetric top/bottom), for the floating idle bob and spin.",
              "Arrows spawn at nocking_point_studio and leave past arrow_rest_point_studio (rest is on the -y face)."],
    "vfx_notes": [
        "Colours: electric blue RGB(18,108,255) body, white-hot RGB(214,240,255) core, gold RGB(255,205,110) sparks; "
        "keep the blue saturated (no pastel), never yellow-only.",
        "Charge/draw: a ParticleEmitter at the crystal (Attachment at the crystal centre): Rate 20, Lifetime 0.25-0.4, "
        "Speed 1-2, SpreadAngle 180, Size 0.25->0, LightEmission 1, Color white->blue; a second tiny emitter in the "
        "eagle's beak (Rate 10, Size 0.12->0); plus a PointLight Range 8, Brightness 2, blue, pulsing with the draw.",
        "Arrow in flight: a blue Neon arrow with a Trail (Attachment0 at the nock, Attachment1 at the head), "
        "Lifetime 0.18, WidthScale 1->0, LightEmission 1, FaceCamera true, Color white->blue; a jagged Beam "
        "(Segments 6, CurveSize random +/-0.6 re-rolled every 0.05 s) along the trail sells the lightning.",
        "Split: at about 60% of the flight distance, or 6 studs above the target group, the arrow flashes "
        "(ParticleEmitter Burst 24, Lifetime 0.2, Speed 8-14, Size 0.4->0, white core) with a short crack-of-thunder "
        "sound and becomes 5 arrows fanned 12-16 degrees apart that tilt down onto the group.",
        "Each of the 5 split arrows keeps a thinner lightning Trail (Lifetime 0.12, Width 0.15) and a 2-segment zig "
        "Beam to its neighbour for the first 0.1 s so the split reads as one forking bolt.",
        "Impact: per arrow a small ground flash decal (blue ring, 2 studs, fades 0.25 s) and a ParticleEmitter Burst 10 "
        "(sparks, Speed 6-10, Lifetime 0.2-0.35, Acceleration (0,-30,0), Color blue->gold).",
        "Idle in hand: the string, inlays, bolt tips, eyes and crystal are Neon already; an optional faint "
        "ParticleEmitter along the string (Rate 4, Lifetime 0.3, Size 0.1) gives crackle without hiding the model.",
    ],
}
for o in FINAL:
    st = STATS[o.name]
    mn, mx = np.array(st["bounds_min"]), np.array(st["bounds_max"])
    kind = "textured" if o is body else "glow"
    part = {"kind": kind, "center_studio": studio((mn + mx) / 2), "size_studio": studio_size(mx - mn),
            "triangles": st["triangles"]}
    if o is glow_ob:
        part.update(material="Neon", color_rgb=list(GLOW),
                    note="electric-blue glow: string ribbon and crackle forks, limb bolt inlays, tip bolt cores, crystal "
                         "facets, eyes, beak glow, arrow rest")
    elif o is core_ob:
        part.update(material="Neon", color_rgb=list(CORE), note="white-hot: string core, crystal heart, pupils, nocking bead")
    else:
        part.update(material="SmoothPlastic (or Plastic), Color white", texture_id="BaseColor.png")
    install["parts"][o.name] = part
(ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=1))
log("stats", {k: v["triangles"] for k, v in STATS.items()}, "total", sum(v["triangles"] for v in STATS.values()))

# ---------------------------------------------------------------------------
# Renders (brief set only): Preview, Front, Back, Side, Scale, Hero
# ---------------------------------------------------------------------------
setup_comp(0.45, 1.0)


def shoot_catalog(name, angle, camvec, samples=32, res=1000):
    r = catalog_stage(FINAL, angle, camvec, samples=samples, res=res)
    render(ROOT / name)
    r()


shoot_catalog("Preview.png", -12, (1.6, -15, 6.2), samples=48)
shoot_catalog("Front.png", 0, (0, -15, 1.2))
shoot_catalog("Back.png", 0, (0, 15, 1.2))
shoot_catalog("Side.png", 0, (15, 0, 1.2))

fig_bm = new_bm()
FX = 3.5
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
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.010, 0.013, 0.024, 1)
    cd = bpy.data.cameras.new("Hero camera")
    cam = bpy.data.objects.new("Hero camera", cd)
    REVIEW.objects.link(cam)
    cd.lens = lens
    cam.location = cam_loc
    cam.rotation_euler = (target - cam_loc).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    for nm, loc, col, en, sz in (("Hero key", V(-4, -6, 8), (1.0, 0.92, 0.82), 1150, 4),
                                  ("Hero rim blue", V(4, 6, 6), (0.2, 0.5, 1.0), 1900, 3),
                                  ("Hero rim amber", V(-5, 5, 5), (1.0, 0.72, 0.4), 800, 3),
                                  ("Hero fill slate", V(2, -5, 0.5), (0.5, 0.58, 0.8), 160, 4)):
        ld = bpy.data.lights.new(nm, "AREA")
        ld.color = col
        ld.energy = en
        ld.size = sz
        lo = bpy.data.objects.new(nm, ld)
        REVIEW.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = (target - loc).to_track_quat("-Z", "Y").to_euler()
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.view_settings.view_transform = VIEW
    try:
        scene.view_settings.look = "AgX - Punchy"
    except TypeError:
        pass
    setup_comp(0.8, 1.4)
    render(ROOT / name)
    scene.view_settings.look = "None"
    setup_comp(0.45, 1.0)


hero("Hero.png", V(-3.6, -7.4, 3.9), V(-0.1, 0, 2.5), lens=50)

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
compose([(ROOT / "Preview.png", "Storm Bow (Godly, round 2)"), (ASSETS / "32-excalibur" / "Preview.png", "Excalibur"),
         (ASSETS / "31-mjolnir" / "Preview.png", "Mjolnir"), (ASSETS / "34-medusas-head" / "Preview.png", "Medusa's Head")],
        4, 700, ROOT / "Compare_Catalog.png", title="Catalogue framing: Godly Storm Bow beside the current top-tier weapons")
compose([(ROOT / "Preview.png", "Preview (catalogue 3/4)"), (ROOT / "Front.png", "Front"), (ROOT / "Back.png", "Back"),
         (ROOT / "Side.png", "Side"), (ROOT / "Hero.png", "Hero (dramatic lighting)"),
         (ROOT / "Scale.png", "Scale: 5-stud R15 block figure"), (ROOT / "BaseColor.png", "BaseColor.png (1024, baked)")],
        4, 560, ROOT / "Sheet.png", title="Storm Bow - Godly, round 2 (Blender renders, Studio untested)")

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
    "symmetry_top_bottom_about_grip": "limbs, plates, inlays, collars, tip bolts and string are one authored half mirrored "
                                      "about z = grip; the eagle head (top) and tail plume (bottom) balance the riser",
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
    "(plates over the limb core, wrap on the riser, inlays set into the faces, collars over the joints, talons over the crystal).",
    "Studio import, Neon look and in-game scale are untested (no Studio access in this task).",
]
(ROOT / "validation.json").write_text(json.dumps(report, indent=1))
log("VALIDATION", json.dumps(report["checks"]), "tris", report["total_triangles"])
log("DONE")
