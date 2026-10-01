"""Baby Dragon pet (Legendary, strong suit: fire) for the roguelite.

Self-contained generator for background Blender 5.2 (no code imported from other kits).

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 \
        --python build_baby_dragon.py
    ... -- --shape --out <dir>     fast look-dev: per-vertex painted colours, no bake, one shape sheet
    ... -- --quick --out <dir>     1024 bake, a few renders, no exports
    ... -- --no-previews           exports + reports only
    ... -- --no-hero               skip the small Cycles hero render

Coordinates: Blender Z-up, 1 unit = 1 stud (final size, import 1:1), feet on z = 0, the dragon faces
-Y and its own left is +X. Studio = (-x, z, y) of Blender.

Method (same family as the approved Golden Retriever / Turtle / Owl): every rigid part is ONE surface
made from analytic signed-distance volumes joined with smooth unions (real fillets), meshed on a COARSE
lattice so the facets are broad and even like cut gemstone planes (flat shading). The thick wings and
the tail flame are meshed finer then decimated + relaxed. Colour is painted by 3D position (continuous
over every join and UV seam) and baked to one 1024 atlas with icon lighting (per-facet key, AO, warm
shadow, cool rim). The ember markings are separate thin-shell `_Glow` meshes laid just proud of the
facets (Neon in Studio).
"""

import json
import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np
import openvdb as vdb
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

T0 = time.time()
ROOT = Path("C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning/blender-pet-kit/baby-dragon")
STEM = "baby-dragon"
PFX = "BabyDragon_"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    if name in ARGS:
        i = ARGS.index(name)
        if i + 1 < len(ARGS):
            return ARGS[i + 1]
    return default


SHAPE = "--shape" in ARGS
QUICK = "--quick" in ARGS or SHAPE
NO_PREVIEWS = "--no-previews" in ARGS
NO_HERO = "--no-hero" in ARGS
OUT = Path(arg("--out", str(ROOT / "previews")))
TEX_PATH = ROOT / "textures" / f"{STEM}.png"
FBX_PATH = ROOT / "exports" / "fbx" / f"{STEM}.fbx"
GLB_PATH = ROOT / "exports" / "glb" / f"{STEM}.glb"
BLEND_PATH = ROOT / f"{STEM}.blend"
ATLAS = 1024
BAKE = 1024 if QUICK else 2048
for d in (TEX_PATH.parent, FBX_PATH.parent, GLB_PATH.parent, OUT):
    d.mkdir(parents=True, exist_ok=True)


def log(*a):
    print(f"[baby-dragon {time.time() - T0:6.1f}s]", *a, flush=True)


(P_BODY, P_HEAD, P_WINGL, P_WINGR, P_LEGL, P_LEGR, P_TAIL, P_GCHEEK, P_GBODY, P_GTAIL) = range(1, 11)
GLOW_PIDS = (P_GCHEEK, P_GBODY, P_GTAIL)


def V(*a):
    return Vector(a if len(a) == 3 else a[0])


# =============================================================================================
# signed-distance toolkit
# =============================================================================================
class Grid:
    def __init__(self, lo, hi, h, sym_x=False):
        lo, hi = np.array(lo, float), np.array(hi, float)
        n = np.ceil((hi - lo) / h).astype(int) + 1
        if sym_x:
            half = max(abs(lo[0]), abs(hi[0]))
            n[0] = int(math.ceil(2 * half / h)) + 1
            lo[0] = -(n[0] - 1) * h / 2
        self.lo, self.h, self.n = lo, h, tuple(int(v) for v in n)
        ax = [lo[k] + h * np.arange(self.n[k]) for k in range(3)]
        self.P = np.stack(np.meshgrid(*ax, indexing="ij"), axis=-1)

    def sample(self, A, pts):
        f = (np.asarray(pts, float) - self.lo) / self.h
        n = np.array(self.n)
        i0 = np.clip(np.floor(f).astype(int), 0, n - 2)
        t = np.clip(f - i0, 0.0, 1.0)
        out = np.zeros(len(f))
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    w = ((t[:, 0] if dx else 1 - t[:, 0]) * (t[:, 1] if dy else 1 - t[:, 1])
                         * (t[:, 2] if dz else 1 - t[:, 2]))
                    out += w * A[i0[:, 0] + dx, i0[:, 1] + dy, i0[:, 2] + dz]
        return out


AXES = np.eye(3)


def sd_ell(P, c, R, radii, elong=0.0):
    q = (P - np.asarray(c, float)) @ np.asarray(R, float).T
    r = np.asarray(radii, float)
    k0 = np.linalg.norm(q / r, axis=-1)
    k1 = np.linalg.norm(q / (r * r), axis=-1)
    return np.where(k0 < 1e-6, -min(radii), k0 * (k0 - 1.0) / np.maximum(k1, 1e-9))


def sd_ell2(u, v, cu, cv, ru, rv):
    x, y = (u - cu) / ru, (v - cv) / rv
    k0 = np.sqrt(x * x + y * y)
    k1 = np.sqrt((x / ru) ** 2 + (y / rv) ** 2)
    return np.where(k0 < 1e-6, -min(ru, rv), k0 * (k0 - 1.0) / np.maximum(k1, 1e-9))


def track_axes(axis):
    """Local axes (rows) of an ellipsoid whose local z runs along `axis` (local y ~ world up)."""
    q = Vector(axis).normalized().to_track_quat("Z", "Y")
    return np.array(q.to_matrix()).T


def ell(P, c, radii, axis=None):
    return sd_ell(P, c, AXES if axis is None else track_axes(axis), radii)


def rcone(P, a, b, ra, rb):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ba = b - a
    t = np.clip(((P - a) @ ba) / (ba @ ba), 0.0, 1.0)
    r = ra + (rb - ra) * t
    return np.linalg.norm(P - (a + t[..., None] * ba), axis=-1) - r


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def blur(F, passes=1):
    F = F.copy()
    for _ in range(passes):
        for ax in range(3):
            def sl(a, b, ax=ax):
                return tuple(slice(a, b) if i == ax else slice(None) for i in range(3))
            G = F.copy()
            G[sl(1, -1)] = 0.25 * F[sl(0, -2)] + 0.5 * F[sl(1, -1)] + 0.25 * F[sl(2, None)]
            F = G
    return F


def min_angles(vs, fs):
    a, b, c = vs[[f[0] for f in fs]], vs[[f[1] for f in fs]], vs[[f[2] for f in fs]]

    def ang(p, q, r):
        u, v = q - p, r - p
        cs = np.sum(u * v, 1) / np.maximum(np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1), 1e-12)
        return np.degrees(np.arccos(np.clip(cs, -1, 1)))
    return np.minimum(np.minimum(ang(a, b, c), ang(b, c, a)), ang(c, a, b))


def tidy(grid, F, vs, fs, passes=6):
    """Even out triangles without moving the surface (flip edges, relax, project back)."""
    before = int(np.sum(min_angles(vs, fs) < 12.0))
    bm = bmesh.new()
    bv = [bm.verts.new(tuple(v)) for v in vs]
    for fc in fs:
        try:
            bm.faces.new([bv[i] for i in fc])
        except ValueError:
            pass
    bm.normal_update()
    for _ in range(passes):
        bmesh.ops.beautify_fill(bm, faces=bm.faces[:], edges=bm.edges[:], use_restrict_tag=False, method="ANGLE")
        bm.verts.ensure_lookup_table()
        co = np.array([v.co[:] for v in bm.verts])
        cen = np.array([np.mean([e.other_vert(v).co[:] for e in v.link_edges], axis=0) if v.link_edges else v.co[:]
                        for v in bm.verts])
        p = co + 0.5 * (cen - co)
        for _ in range(2):
            eps = grid.h * 0.5
            d = grid.sample(F, p)
            g = np.stack([grid.sample(F, p + eps * e) - grid.sample(F, p - eps * e) for e in np.eye(3)], 1) / (2 * eps)
            p = p - (d / np.maximum(np.sum(g * g, 1), 1e-9))[:, None] * g
        for v, q in zip(bm.verts, p):
            v.co = q
    bmesh.ops.beautify_fill(bm, faces=bm.faces[:], edges=bm.edges[:], use_restrict_tag=False, method="ANGLE")
    bm.verts.index_update()
    vo = np.array([v.co[:] for v in bm.verts])
    fo = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    log("  tidy: corners under 12 deg", before, "->", int(np.sum(min_angles(vo, fo) < 12.0)))
    return vo, fo


def extract(grid, F, target=None, name="fused"):
    g = vdb.FloatGrid(1.0e4)
    g.copyFromArray((F / grid.h).astype(np.float32))
    pts, tris, quads = g.convertToPolygons(0.0, 0.0)
    vs = grid.lo + grid.h * pts.astype(np.float64)
    faces = [tuple(q) for q in quads.tolist()] + [tuple(t) for t in tris.tolist()]
    me = bpy.data.meshes.new(name)
    me.from_pydata(vs.tolist(), [], faces)
    me.validate()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    n_tri = sum(len(p.vertices) - 2 for p in me.polygons)
    if target is None:                       # coarse lattice: already even, just triangulate
        ob.modifiers.new("Tri", "TRIANGULATE")
    else:
        dm = ob.modifiers.new("Decimate", "DECIMATE")
        dm.ratio = min(1.0, target / max(n_tri, 1))
        dm.use_collapse_triangulate = True
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    m2 = ev.to_mesh()
    vo = np.array([v.co[:] for v in m2.vertices], float)
    fo = [tuple(p.vertices) for p in m2.polygons]
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    vo, fo = tidy(grid, F, vo, fo)
    log(name, "isosurface", n_tri, "tris ->", len(fo))
    return vo, fo


def surf_point(G, F, x, z, y0, y1):
    """First surface crossing of the field along +Y from the front, plus the outward normal."""
    ys = np.linspace(y0, y1, 1200)
    pts = np.stack([np.full_like(ys, x), ys, np.full_like(ys, z)], 1)
    d = G.sample(F, pts)
    i = int(np.nonzero(d < 0)[0][0])
    t = d[i - 1] / (d[i - 1] - d[i])
    p = np.array((x, ys[i - 1] + t * (ys[i] - ys[i - 1]), z))
    e = 0.01
    g = np.array([G.sample(F, (p + e * ax)[None])[0] - G.sample(F, (p - e * ax)[None])[0] for ax in np.eye(3)])
    return p, g / np.linalg.norm(g)


def frame_at(G, F, x, z, y0, y1, r=None):
    p, n = surf_point(G, F, x, z, y0, y1)
    R = track_axes(n)
    u, v = R[0].copy(), R[1].copy()
    if u[0] < 0:
        u = -u
    if v[2] < 0:
        v = -v
    fr = dict(c=p, u=u, v=v, n=n)
    if r:
        fr["r"] = r
    return fr


def mirror(vf):
    vs, fs = vf
    return vs * np.array((-1.0, 1.0, 1.0)), [tuple(reversed(f)) for f in fs]


# =============================================================================================
# design (studs). Chibi baby dragon: big round head about as wide as the body, short rounded snout
# flowing out of the face, two short thick ivory horns and soft ear fins fused into the head, round
# belly with cream scale bands, stubby arms fused to the chest, a row of soft gold bumps fused into
# the back, stubby hind legs with chunky feet and rounded claws, short thick tail with a rounded
# spade and an ember flame, stubby thick bat wings that pivot at the shoulders.
# =============================================================================================
FUSED = {}         # part -> (grid, named fields) for the painter's masks
FACE = {}          # eye / mouth frames for the painter
PIVOT = {
    PFX + "Body": V(0.0, 0.06, 0.70),
    PFX + "Head": V(0.0, -0.10, 1.22),
    PFX + "WingL": V(0.26, 0.26, 1.08),
    PFX + "WingR": V(-0.26, 0.26, 1.08),
    PFX + "LegL": V(0.30, 0.08, 0.42),
    PFX + "LegR": V(-0.30, 0.08, 0.42),
    PFX + "Tail": V(0.0, 0.38, 0.40),
}
BODY_C, BODY_R = (0.0, 0.06, 0.72), (0.50, 0.46, 0.56)
HEAD_C, HEAD_R = (0.0, -0.16, 1.68), (0.66, 0.56, 0.52)
SNOUT_C, SNOUT_R = (0.0, -0.62, 1.47), (0.34, 0.24, 0.22)
HAND_C = {s: np.array((s * 0.23, -0.48, 0.72)) for s in (1, -1)}
CLAW_FOOT = [(dx, -0.35, 0.075) for dx in (-0.10, 0.0, 0.10)]
LEG_X = 0.34
H_FINE = 0.022
H_BODY, H_HEAD, H_LEG, H_TAIL = 0.08, 0.074, 0.068, 0.064     # coarse lattices ARE the mesh
WING_EL, WING_SW = math.radians(32), math.radians(38)
W0 = np.array((0.26, 0.26, 1.08))
WS = 1.2                                   # wing scale


def body_field(h):
    G = Grid((-0.78, -0.80, 0.05), (0.78, 0.80, 1.48), h, sym_x=True)
    P = G.P
    F = ell(P, BODY_C, BODY_R)
    F = smin(F, ell(P, (0.0, -0.10, 0.58), (0.46, 0.40, 0.40)), 0.15)          # round belly
    F = smin(F, ell(P, (0.0, -0.10, 1.12), (0.30, 0.28, 0.28)), 0.15)          # neck into the head
    arm = None
    for s in (1, -1):                                                          # stubby arms hugging the belly
        a = smin(rcone(P, (s * 0.34, -0.22, 0.94), (s * 0.25, -0.44, 0.75), 0.105, 0.09),
                 ell(P, HAND_C[s], (0.10, 0.10, 0.09)), 0.05)
        arm = a if arm is None else np.minimum(arm, a)
    F = smin(F, arm, 0.08)
    ridge = None
    for z, rr in ((1.10, 1.0), (0.88, 0.92), (0.66, 0.80)):                    # soft bumps fused into the back
        ys = BODY_C[1] + BODY_R[1] * math.sqrt(max(0.0, 1 - ((z - BODY_C[2]) / BODY_R[2]) ** 2))
        b = ell(P, (0.0, ys - 0.03, z), (0.085 * rr, 0.12 * rr, 0.12 * rr))
        ridge = b if ridge is None else np.minimum(ridge, b)
    F = smin(F, ridge, 0.06)
    return G, F, dict(ridge=ridge, arm=arm)


def horn_sdf(P, s):
    h0, h1, h2 = (s * 0.26, -0.06, 2.00), (s * 0.32, 0.06, 2.19), (s * 0.36, 0.21, 2.30)
    return smin(rcone(P, h0, h1, 0.125, 0.09), rcone(P, h1, h2, 0.09, 0.062), 0.03)


def head_field(h, store):
    frames = {}
    G = Grid((-1.0, -1.05, 0.95), (1.0, 0.60, 2.45), h, sym_x=True)
    P = G.P
    base = ell(P, HEAD_C, HEAD_R)
    for s in (1, -1):                                                          # chubby cheeks
        base = smin(base, ell(P, (s * 0.34, -0.46, 1.50), (0.24, 0.20, 0.18)), 0.12)
    base = smin(base, ell(P, (0.0, -0.08, 1.24), (0.28, 0.26, 0.24)), 0.12)   # neck plug
    snout = ell(P, SNOUT_C, SNOUT_R)
    base = smin(base, snout, 0.18)                                             # short snout flowing out
    base = smax(base, -ell(P, (0.0, -0.885, 1.385), (0.15, 0.09, 0.05)), 0.03)  # shallow open-mouth relief
    if store:
        for name, s in (("eyeL", 1), ("eyeR", -1)):
            frames[name] = frame_at(G, base, s * 0.28, 1.73, -1.3, -0.1, (0.16, 0.19))
        frames["mouth"] = frame_at(G, base, 0.0, 1.40, -1.3, -0.3)
        frames["nose"] = frame_at(G, base, 0.0, 1.575, -1.3, -0.3)
    horn = np.minimum(horn_sdf(P, 1), horn_sdf(P, -1))
    fin = None
    for s in (1, -1):                                                          # soft ear fins
        f_ = ell(P, (s * 0.63, 0.04, 1.78), (0.065, 0.12, 0.18), axis=(s * 1.0, 0.55, 0.45))
        fin = f_ if fin is None else np.minimum(fin, f_)
    bump = ell(P, (0.0, 0.32, 1.88), (0.085, 0.11, 0.10))
    F = smin(base, horn, 0.07)
    F = smin(F, fin, 0.07)
    F = smin(F, bump, 0.05)
    if store:
        FACE.update(frames)
    return G, F, dict(horn=horn, fin=fin, bump=bump, snout=snout)


def wing_frame():
    d = np.array((math.cos(WING_EL) * math.cos(WING_SW), math.cos(WING_EL) * math.sin(WING_SW), math.sin(WING_EL)))
    c0 = np.array((0.0, 0.55, -1.0))
    c = c0 - d * (c0 @ d)
    c /= np.linalg.norm(c)
    n = np.cross(d, c)
    return d, c, n / np.linalg.norm(n)


SCALLOPS = (0.15, 0.36, 0.56)


def memb_edge(u):
    return 0.17 + 0.26 * np.sqrt(np.clip(1 - ((u - 0.34) / 0.36) ** 2, 0, 1))


def wing_2d(u, v):
    m = sd_ell2(u, v, 0.34, 0.17, 0.36, 0.26)
    m = smax(m, -v, 0.04)
    for uc in SCALLOPS:
        circ = np.hypot(u - uc, v - (memb_edge(uc) + 0.06)) - 0.10
        m = smax(m, -circ, 0.025)
    return m


def wing_field(h):
    """Left wing (+X); the right one is its mirror. Thick rounded arm ridge + thick scalloped membrane."""
    G = Grid((0.0, -0.15, 0.40), (1.12, 1.20, 1.95), h)
    P = G.P
    d, c, n = wing_frame()
    q = (P - W0) / WS
    Ps = W0 + q
    u, v, w = q @ d, q @ c, q @ n
    th, r = 0.050, 0.034
    a, b = wing_2d(u, v) + r, np.abs(w) - th + r
    slab = np.sqrt(np.maximum(a, 0) ** 2 + np.maximum(b, 0) ** 2) + np.minimum(np.maximum(a, b), 0) - r
    ridge = smin(rcone(Ps, W0, W0 + d * 0.60, 0.085, 0.062), ell(Ps, W0 + d * 0.60, (0.072, 0.072, 0.072)), 0.03)
    ridge = smin(ridge, rcone(Ps, W0 + d * 0.60, W0 + d * 0.72 + c * 0.03, 0.06, 0.042), 0.03)
    F = smin(slab, ridge, 0.05)
    F = smin(F, ell(Ps, W0, (0.10, 0.10, 0.10)), 0.05) * WS                   # root ball sunk in the shoulder
    return G, F


def leg_field(h):
    G = Grid((0.0, -0.58, -0.05), (0.68, 0.42, 0.72), h)
    P = G.P
    Z = P[..., 2]
    F = ell(P, (LEG_X - 0.01, 0.08, 0.38), (0.20, 0.24, 0.23))                 # round drumstick thigh
    F = smin(F, ell(P, (LEG_X, -0.02, 0.18), (0.16, 0.18, 0.15)), 0.10)
    F = smin(F, ell(P, (LEG_X, -0.12, 0.09), (0.19, 0.25, 0.10)), 0.10)       # chunky foot
    for dx, dy, dz in CLAW_FOOT:                                               # rounded claws
        F = smin(F, ell(P, (LEG_X + dx, dy, dz), (0.062, 0.075, 0.06)), 0.035)
    F = smax(F, -Z, 0.015)
    return G, F


TAIL_CHAIN = [((0, 0.42, 0.38), 0.21), ((0, 0.66, 0.30), 0.17), ((0, 0.88, 0.32), 0.135),
              ((0, 1.04, 0.44), 0.105), ((0, 1.12, 0.59), 0.085)]
SPADE_C, SPADE_AX = (0.0, 1.17, 0.70), (0.0, 0.35, 0.94)


def tail_field(h):
    G = Grid((-0.40, 0.15, 0.05), (0.40, 1.45, 1.00), h, sym_x=True)
    P = G.P
    F = None
    for (a, ra), (b, rb) in zip(TAIL_CHAIN[:-1], TAIL_CHAIN[1:]):
        seg = rcone(P, a, b, ra, rb)
        F = seg if F is None else smin(F, seg, 0.06)
    spade = ell(P, SPADE_C, (0.16, 0.075, 0.14), axis=SPADE_AX)
    F = smin(F, spade, 0.07)
    return G, F, dict(spade=spade)


def flame_field(h):
    G = Grid((-0.22, 0.95, 0.65), (0.22, 1.45, 1.20), h, sym_x=True)
    P = G.P
    F = rcone(P, (0, 1.20, 0.81), (0, 1.26, 1.08), 0.085, 0.02)
    for s in (1, -1):
        F = smin(F, rcone(P, (s * 0.04, 1.20, 0.83), (s * 0.115, 1.23, 0.99), 0.05, 0.018), 0.04)
    F = smin(F, rcone(P, (0, 1.17, 0.83), (0, 1.12, 0.97), 0.05, 0.018), 0.03)
    return G, F


# ---- ember markings: thin shells laid on the coarse facets -------------------------------------
GLOW_MARKS = []    # (carrier part pid, c, a, b, n, L, W)
MARKS = {
    P_GCHEEK: [((s * 1.3, -0.40, 1.57), (-s, 0, 0), (0, 1, 0.55), 0.085, 0.025, 0.55, 0.0) for s in (1, -1)]
    + [((s * 1.3, -0.29, 1.43), (-s, 0, 0), (0, 1, 0.30), 0.065, 0.021, 0.55, 0.0) for s in (1, -1)],
    P_GBODY: [((s * 1.3, 0.08, 0.90), (-s, 0, 0), (0, 0.25, 1), 0.11, 0.032, 0.55, 0.25) for s in (1, -1)]
    + [((s * 1.3, 0.22, 0.70), (-s, 0, 0), (0, 0.2, 1), 0.08, 0.026, 0.55, 0.25) for s in (1, -1)]
    + [((0.0, -1.3, 0.95), (0, 1, 0), (0, 0, 1), 0.065, 0.048, 0.65, 0.0)],
    P_GTAIL: [((0.0, 0.70, 1.3), (0, 0, -1), (0, 1, 0), 0.05, 0.036, 0.25, 0.0),
              ((0.0, 0.92, 1.3), (0, 0, -1), (0, 1, 0), 0.04, 0.03, 0.25, 0.0)],
}
CARRIER_PID = {P_GCHEEK: P_HEAD, P_GBODY: P_BODY, P_GTAIL: P_TAIL}


def ember_patch(tree, pid, anchor, dirv, along, L, W, taper, bend, seg=10):
    loc, nrm, _, _ = tree.ray_cast(Vector(anchor), Vector(dirv).normalized(), 5.0)
    c, n = np.array(loc), np.array(nrm)
    a = np.array(along, float)
    a = a - n * (a @ n)
    a /= np.linalg.norm(a)
    b = np.cross(n, a)
    GLOW_MARKS.append((CARRIER_PID[pid], c, a, b, n, L, W))

    def on_surf(x, y, off):
        p0 = c + a * x + b * y
        h = tree.ray_cast(Vector(p0 + n * 0.3), Vector(-n), 1.0)
        if h[0] is None:
            return p0 + n * off
        return np.array(h[0]) + np.array(h[1]) * off

    def local(r, th):
        x = r * math.cos(th) * L
        y = r * math.sin(th) * W * (1.0 - taper * max(0.0, math.cos(th) * r))
        return x, y + bend * (x / L) ** 2 * L

    TOP, BOT = 0.020, 0.006
    vs = [on_surf(0, 0, TOP)]
    for r in (0.55, 1.0):
        for k in range(seg):
            vs.append(on_surf(*local(r, 2 * math.pi * k / seg), TOP))
    bc = len(vs)
    vs.append(on_surf(0, 0, BOT))
    br = len(vs)
    for k in range(seg):
        vs.append(on_surf(*local(1.0, 2 * math.pi * k / seg), BOT))
    fs = []
    for k in range(seg):
        k1 = (k + 1) % seg
        fs.append((0, 1 + k, 1 + k1))
        fs.append((1 + k, 1 + seg + k, 1 + seg + k1, 1 + k1))
        fs.append((bc, br + k1, br + k))
        fs.append((1 + seg + k, br + k, br + k1, 1 + seg + k1))
    return np.array(vs), fs


def merge(vfs):
    vs, fs, off = [], [], 0
    for v, f in vfs:
        vs.append(v)
        fs += [tuple(i + off for i in fc) for fc in f]
        off += len(v)
    return np.concatenate(vs), fs


# =============================================================================================
# painting (numpy), all driven by 3D position
# =============================================================================================
_rng = np.random.default_rng(20260930)
_PERM = np.concatenate([_rng.permutation(256)] * 2)
_VALS = _rng.random(256)


def vnoise(p, freq, seed=0):
    q = p * freq + seed * 17.31
    i = np.floor(q).astype(np.int64)
    f = q - i
    u = f * f * (3 - 2 * f)
    out = np.zeros(len(p))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (u[:, 0] if dx else 1 - u[:, 0]) * (u[:, 1] if dy else 1 - u[:, 1]) * (u[:, 2] if dz else 1 - u[:, 2])
                h = _VALS[_PERM[_PERM[_PERM[(i[:, 0] + dx) & 255] + ((i[:, 1] + dy) & 255)] + ((i[:, 2] + dz) & 255)]]
                out += w * h
    return out


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def rgb(*c):
    return np.array(c, dtype=np.float64) / 255.0


def mix(a, b, t):
    t = np.asarray(t, dtype=np.float64)
    if t.ndim == 1:
        t = t[:, None]
    return a + (b - a) * t


def bands(p, fx, fz, seed, cy=0.0):
    """Broad painterly brush bands following the form: (dark, light) masks, three value ranges."""
    az_ = np.arctan2(p[:, 0], -(p[:, 1] - cy))
    q = np.stack([np.cos(az_) * fx, np.sin(az_) * fx, p[:, 2] * fz], 1)
    s_ = vnoise(q, 1.0, seed)
    return 1.0 - sstep(0.38, 0.46, s_), sstep(0.60, 0.68, s_)


def sample(part, name, p):
    G, fl = FUSED[part]
    return G.sample(fl[name], p)


RED, RED_LT, RED_SH, RED_DK = rgb(214, 62, 46), rgb(242, 110, 70), rgb(156, 36, 42), rgb(118, 26, 38)
BELLY, BELLY_LT, BELLY_SH, BELLY_LINE = rgb(252, 216, 140), rgb(255, 240, 192), rgb(232, 168, 94), rgb(210, 128, 72)
IVORY, IVORY_SH = rgb(252, 240, 214), rgb(214, 186, 146)
GOLD, GOLD_LT, GOLD_DK = rgb(250, 184, 72), rgb(255, 222, 128), rgb(212, 124, 48)
MEMB, MEMB_LT, MEMB_SH, VEIN = rgb(255, 178, 116), rgb(255, 212, 156), rgb(238, 128, 84), rgb(204, 82, 62)
EYE_DARK, EYE_IRIS, EYE_LINE = rgb(40, 16, 22), rgb(238, 150, 38), rgb(66, 20, 26)
MOUTH_C, TONGUE = rgb(118, 28, 40), rgb(248, 122, 124)
BLUSH, HALO = rgb(255, 150, 122), rgb(140, 34, 36)
NEON, NEON_LT = rgb(255, 150, 46), rgb(255, 214, 120)
COOL = np.array((0.80, 0.86, 1.0))


def halos(c, p, n, carrier):
    for pid, cc, a, b, nn, L, W in GLOW_MARKS:
        if pid != carrier:
            continue
        d = p - cc
        e = np.sqrt(((d @ a) / (L * 1.45)) ** 2 + ((d @ b) / (W * 2.4)) ** 2)
        m = (np.abs(d @ nn) < 0.08) & (n @ nn > 0.2)
        c = mix(c, HALO, 0.55 * sstep(1.0, 0.55, e) * m)
    return c


def paint_body(p, n):
    X, Y, Z = p[:, 0], p[:, 1], p[:, 2]
    c = mix(RED_SH, RED, sstep(0.10, 0.95, Z))
    c = mix(c, RED_LT, 0.30 * sstep(0.2, 0.9, n[:, 2]) * sstep(0.6, 1.2, Z))
    bd, bl = bands(p, 3.2, 1.8, 11, BODY_C[1])
    c = mix(c, RED_DK, 0.24 * bd)
    c = mix(c, RED_LT, 0.24 * bl * sstep(-0.3, 0.6, n[:, 2]))
    # cream belly with broad painted scale bands curving round the belly
    be = (X / 0.37) ** 2 + ((Z - 0.64) / 0.50) ** 2
    bm = sstep(1.05, 0.82, be) * sstep(-0.02, -0.20, Y) * sstep(0.05, -0.30, n[:, 1])
    bz = Z + 0.40 * X ** 2
    ph = (bz - 0.18) / 0.15
    fr = ph - np.floor(ph)
    bc = mix(BELLY_SH, BELLY, sstep(0.0, 0.45, fr))
    bc = mix(bc, BELLY_LT, 0.45 * sstep(0.35, 0.70, fr) * sstep(0.98, 0.75, fr))
    bc = mix(bc, BELLY_LINE, 0.55 * sstep(0.10, 0.0, np.minimum(fr, 1 - fr)))
    bd2, bl2 = bands(p, 4.0, 2.0, 17, BODY_C[1])
    bc = mix(bc, BELLY_SH, 0.18 * bd2)
    c = mix(c, bc, bm)
    # soft gold back bumps
    rm = sstep(0.03, -0.012, sample("body", "ridge", p)) * (Y > 0.15)
    gc = mix(GOLD_DK, GOLD, sstep(-0.5, 0.4, n[:, 2]))
    gc = mix(gc, GOLD_LT, 0.5 * sstep(0.3, 0.9, n[:, 2] + 0.3 * n[:, 1]))
    c = mix(c, gc, rm)
    # little rounded hand claws
    hard = rm > 0.5
    for s in (1, -1):
        for dx in (-0.055, 0.0, 0.055):
            cc = HAND_C[s] + np.array((dx, -0.085, -0.035))
            dd = np.linalg.norm(p - cc, axis=1)
            cm = sstep(0.040, 0.026, dd) * (n[:, 1] < 0.0)
            c = mix(c, IVORY, cm)
            hard |= cm > 0.5
    c = halos(c, p, n, P_BODY)
    return c, hard


def paint_head(p, n, eyes_out):
    X, Y, Z = p[:, 0], p[:, 1], p[:, 2]
    c = mix(RED_SH, RED, sstep(1.10, 1.85, Z))
    c = mix(c, RED_LT, 0.28 * sstep(0.2, 0.9, n[:, 2]) * sstep(1.6, 2.0, Z))
    bd, bl = bands(p, 3.0, 1.6, 13, HEAD_C[1])
    c = mix(c, RED_DK, 0.22 * bd)
    c = mix(c, RED_LT, 0.24 * bl * sstep(-0.3, 0.6, n[:, 2]))
    # snout top a touch lighter, cream jaw and chin under the mouth
    sn = sstep(0.03, -0.02, sample("head", "snout", p))
    c = mix(c, RED_LT, 0.22 * sn * sstep(0.1, 0.7, n[:, 2]))
    jaw = np.maximum(sstep(-0.15, -0.55, n[:, 2]) * sstep(1.52, 1.36, Z),
                     sstep(1.37, 1.32, Z) * sstep(-0.3, -0.6, n[:, 1]))
    jaw = jaw * sstep(-0.25, -0.45, Y)
    jc = mix(BELLY_SH, BELLY, sstep(1.15, 1.40, Z))
    c = mix(c, jc, jaw)
    front = (Y < -0.45) & (n[:, 1] < -0.15)
    for s in (1, -1):                                                          # soft cheek blush
        bdd = np.sqrt(((X - s * 0.42) / 0.12) ** 2 + ((Z - 1.50) / 0.08) ** 2)
        c = mix(c, BLUSH, 0.40 * sstep(1.0, 0.2, bdd) * front)
    # nostrils
    nf = FACE["nose"]
    for s in (1, -1):
        d = p - (nf["c"] + nf["u"] * s * 0.085)
        nd = np.sqrt((d @ nf["u"]) ** 2 + (d @ nf["v"]) ** 2)
        nm = (np.abs(d @ nf["n"]) < 0.06) & (n @ nf["n"] > 0.3)
        c = mix(c, RED_DK * 0.75, sstep(0.032, 0.020, nd) * nm)
    # open toothy smile: dark mouth, pink tongue, two tiny rounded ivory fangs
    mf = FACE["mouth"]
    d = p - mf["c"]
    du, dv = d @ mf["u"], d @ mf["v"]
    mfront = (np.abs(d @ mf["n"]) < 0.08) & (n @ mf["n"] > 0.25)
    up = 0.014 + 1.3 * du ** 2
    lo = -0.078 + 4.6 * du ** 2
    inside = mfront & (dv < up) & (dv > lo)
    mc = mix(MOUTH_C * 0.8, MOUTH_C, sstep(lo, up, dv))
    mc = mix(mc, TONGUE, sstep(0.10, 0.05, np.abs(du)) * sstep(lo + 0.045, lo + 0.015, dv))
    for s in (1, -1):
        fd = up - dv
        fang = (np.abs(du - s * 0.078) < 0.024 * np.clip(1 - fd / 0.048, 0, 1) + 0.004) & (fd < 0.046) & (fd > -0.004)
        mc[fang] = IVORY
    c[inside] = mc[inside]
    lip = mfront & ~inside & (np.abs(du) < 0.21) & (
        (np.abs(dv - up) < 0.010) | ((np.abs(dv - lo) < 0.008) & (np.abs(du) < 0.15)))
    c = mix(c, EYE_LINE, 0.85 * lip)
    # big glossy painted eyes over a shallow face
    hard = np.zeros(len(p), bool)
    for name in ("eyeL", "eyeR"):
        e = FACE[name]
        d = p - e["c"]
        eu, ev = (d @ e["u"]) / e["r"][0], (d @ e["v"]) / e["r"][1]
        frontm = (np.abs(d @ e["n"]) < 0.09) & (n @ e["n"] > 0.4)
        r = np.sqrt(eu * eu + ev * ev)
        line = frontm & (r >= 0.97) & (r < 1.18 + 0.12 * sstep(0.2, 0.8, ev))
        c[line] = mix(c[line], EYE_LINE, sstep(1.30, 1.06, r)[line])
        ins = frontm & (r < 1.0)
        ce = np.tile(EYE_DARK, (len(p), 1))
        iris = sstep(0.25, 0.85, r) * sstep(0.3, -0.75, ev)
        ce = mix(ce, EYE_IRIS, 0.88 * iris)
        ce = mix(ce, np.clip(EYE_IRIS * 1.25, 0, 1), 0.5 * sstep(-0.40, -0.85, ev) * sstep(0.30, 0.8, r))
        c[ins] = ce[ins]
        eyes_out.append((ins, eu, ev))
    # horns: warm ivory, soft growth rings
    hm = sstep(0.022, -0.008, sample("head", "horn", p)) * (Z > 1.94)
    t = sstep(1.97, 2.32, Z)
    ic = mix(IVORY_SH, IVORY, 0.35 + 0.65 * t)
    ic = mix(ic, IVORY_SH, 0.20 * sstep(0.6, 1.0, 0.5 + 0.5 * np.cos(Z * 42.0)) * (1 - t))
    ic = mix(ic, np.array((1.0, 0.98, 0.94)), 0.30 * sstep(0.3, 0.9, n[:, 2]))
    c = mix(c, ic, hm)
    hard |= hm > 0.5
    # ear fins: lighter warm membrane colour, with a fold line
    fm = sstep(0.02, -0.01, sample("head", "fin", p)) * sstep(0.53, 0.63, np.abs(X))
    fc = mix(MEMB_SH, MEMB, sstep(0.53, 0.78, np.abs(X)))
    fc = mix(fc, MEMB_LT, 0.4 * sstep(0.71, 0.83, np.abs(X)))
    c = mix(c, fc, fm)
    bm_ = sstep(0.025, -0.01, sample("head", "bump", p)) * (Y > 0.15)
    c = mix(c, mix(GOLD_DK, GOLD, sstep(-0.4, 0.5, n[:, 2] + 0.4 * n[:, 1])), bm_)
    c = halos(c, p, n, P_HEAD)
    return c, hard


def wing_uvw(p, s):
    q = (p * np.array((s, 1.0, 1.0)) - W0) / WS
    d, cc, nw = wing_frame()
    return q @ d, q @ cc, q @ nw


def paint_wing(p, n, s):
    u, v, w = wing_uvw(p, s)
    d, cc, _ = wing_frame()
    q = W0 + (p * np.array((s, 1.0, 1.0)) - W0) / WS
    ridge = rcone(q, W0, W0 + d * 0.60, 0.085, 0.062)
    ridge = np.minimum(ridge, rcone(q, W0 + d * 0.60, W0 + d * 0.72 + cc * 0.03, 0.06, 0.042))
    rmask = sstep(0.022, -0.004, ridge)
    edge = memb_edge(np.clip(u, -0.02, 0.70))
    m = mix(MEMB_SH, MEMB, sstep(0.02, 0.22, v))
    m = mix(m, MEMB_LT, 0.6 * sstep(edge - 0.16, edge - 0.02, v))
    wr = np.array((0.60, 0.0))
    for uc0, uc1 in zip(SCALLOPS[:-1], SCALLOPS[1:]):                          # finger veins to the cusps
        um = 0.5 * (uc0 + uc1)
        tip = np.array((um, memb_edge(um) - 0.01))
        for a0 in (wr, np.array((0.05, 0.02))):
            ab = tip - a0
            t = np.clip(((u - a0[0]) * ab[0] + (v - a0[1]) * ab[1]) / (ab @ ab), 0, 1)
            dist = np.hypot(u - (a0[0] + t * ab[0]), v - (a0[1] + t * ab[1]))
            m = mix(m, VEIN, 0.55 * sstep(0.022, 0.008, dist) * sstep(1.0, 0.75, t))
    bd, bl = bands(np.stack([u * 3, v * 3, w], 1), 2.5, 1.0, 37, 0.0)
    m = mix(m, MEMB_SH, 0.15 * bd)
    m = mix(m, MEMB_LT, 0.18 * bl)
    r_ = mix(RED_SH, RED, sstep(-0.2, 0.7, n[:, 2]))
    r_ = mix(r_, RED_LT, 0.35 * sstep(0.4, 0.95, n[:, 2]))
    return mix(m, r_, rmask), rmask > 0.5


def paint_leg(p, n, s):
    X, Y, Z = p[:, 0] * s, p[:, 1], p[:, 2]
    c = mix(RED_SH, RED, sstep(0.0, 0.55, Z))
    c = mix(c, RED_LT, 0.32 * sstep(0.3, 0.9, n[:, 2]) * sstep(0.25, 0.55, Z))
    bd, bl = bands(p - np.array((s * LEG_X, 0.0, 0.0)), 4.0, 2.0, 29 + s, 0.0)
    c = mix(c, RED_DK, 0.22 * bd)
    c = mix(c, RED_LT, 0.20 * bl)
    c = mix(c, BELLY_SH, 0.75 * sstep(0.05, 0.015, Z))                         # pale sole
    hard = np.zeros(len(p), bool)
    for dx, dy, dz in CLAW_FOOT:
        dd = np.sqrt(((X - LEG_X - dx) / 0.07) ** 2 + ((Y - dy) / 0.085) ** 2 + ((Z - dz) / 0.07) ** 2)
        cm = sstep(1.05, 0.85, dd) * (Y < dy + 0.04)
        c = mix(c, mix(IVORY_SH, IVORY, sstep(-0.2, 0.6, n[:, 2] - n[:, 1])), cm)
        hard |= cm > 0.5
    return c, hard


def paint_tail(p, n):
    X, Y, Z = p[:, 0], p[:, 1], p[:, 2]
    c = mix(RED_SH, RED, sstep(-0.6, 0.5, n[:, 2]))
    c = mix(c, RED_LT, 0.30 * sstep(0.4, 0.95, n[:, 2]))
    bd, bl = bands(p * np.array((1, 0.5, 1)), 4.0, 3.0, 31, 1.0)
    c = mix(c, RED_DK, 0.24 * bd)
    c = mix(c, RED_LT, 0.20 * bl)
    um = sstep(-0.15, -0.45, n[:, 2]) * (np.abs(X) < 0.16)                    # cream underside with bands
    ph = (Y - 0.40) / 0.14
    fr = ph - np.floor(ph)
    uc = mix(BELLY_SH, BELLY, sstep(0.0, 0.5, fr))
    uc = mix(uc, BELLY_LINE, 0.5 * sstep(0.12, 0.0, np.minimum(fr, 1 - fr)))
    c = mix(c, uc, um)
    sp = sstep(0.025, -0.01, sample("tail", "spade", p)) * (Z > 0.62)
    gc = mix(GOLD_DK, GOLD, sstep(-0.3, 0.6, n[:, 2] + 0.3 * n[:, 1]))
    gc = mix(gc, GOLD_LT, 0.35 * sstep(0.4, 0.9, n[:, 2]))
    c = mix(c, gc, sp)
    c = halos(c, p, n, P_TAIL)
    return c, sp > 0.5


def paint_glow(p, n, pid):
    c = mix(NEON, NEON_LT, 0.55 + 0.45 * sstep(0.0, 0.8, np.abs(n[:, 2])))
    if pid == P_GTAIL:
        c = mix(c, NEON_LT, sstep(0.85, 1.05, p[:, 2]))
    return c


def paint_all(P, Ns, part):
    col = np.zeros((len(P), 3))
    hard = np.zeros(len(P), bool)
    eyes = []
    for pid in range(1, 11):
        m = part == pid
        if not m.any():
            continue
        p, n = P[m], Ns[m]
        ex = []
        h = np.zeros(len(p), bool)
        if pid == P_BODY:
            c, h = paint_body(p, n)
        elif pid == P_HEAD:
            c, h = paint_head(p, n, ex)
        elif pid in (P_WINGL, P_WINGR):
            c, h = paint_wing(p, n, 1 if pid == P_WINGL else -1)
        elif pid in (P_LEGL, P_LEGR):
            c, h = paint_leg(p, n, 1 if pid == P_LEGL else -1)
        elif pid == P_TAIL:
            c, h = paint_tail(p, n)
        else:
            c = paint_glow(p, n, pid)
        col[m], hard[m] = c, h
        for inside, eu, ev in ex:
            fi, feu, fev = np.zeros(len(P), bool), np.zeros(len(P)), np.zeros(len(P))
            fi[m], feu[m], fev[m] = inside, eu, ev
            eyes.append((fi, feu, fev))
    return col, hard, eyes


def light(col, P, Ns, Nf, hard, ao_s, ao_l, edge, part_ids):
    Lk = np.array((-0.50, -0.62, 0.62))
    Lk /= np.linalg.norm(Lk)
    Lr = np.array((0.70, 0.62, 0.35))
    Lr /= np.linalg.norm(Lr)
    kf, ks = np.clip(Nf @ Lk, 0, 1), np.clip(Ns @ Lk, 0, 1)
    k = np.clip(ks + np.where(hard, 1.3, 1.6) * (kf - ks), 0.0, 1.0)             # visible facets
    sky = 0.5 + 0.5 * Ns[:, 2]
    lightv = 0.62 + 0.40 * k + 0.12 * sky
    head = part_ids == P_HEAD
    ao_w = np.where(head, 0.20, 0.30)
    aol_w = np.where(head, 0.08, 0.16)
    aof = (1.0 - ao_w + ao_w * sstep(0.12, 1.0, ao_s)) * (1.0 - aol_w * (1.0 - sstep(0.2, 1.0, ao_l)))
    shade = lightv * aof * (0.92 + 0.10 * sstep(0.0, 2.2, P[:, 2]))
    lit = col * shade[:, None]
    lit = mix(lit, np.clip(lit * np.array((1.06, 0.97, 0.88)), 0, 1), 0.5 * sstep(1.0, 0.8, shade) * sstep(0.55, 0.75, shade))
    lit = mix(lit, np.clip(lit * np.array((1.02, 0.86, 0.84)) + np.array((0.02, 0.0, 0.004)), 0, 1),
              0.75 * sstep(0.80, 0.50, shade))                                  # warm shadows, never grey
    lit = lit + (sstep(0.3, 1.0, Ns @ Lr) * 0.10)[:, None] * np.array((0.55, 0.70, 1.0))   # cool rim
    hl = np.clip(col * 1.15 + 0.10, 0, 1) * np.array((1.0, 0.96, 0.88))
    lit = mix(lit, hl, 0.25 * edge * hard * sstep(-0.3, 0.5, Ns @ Lk))
    glow = np.isin(part_ids, GLOW_PIDS)
    lit[glow] = col[glow]
    return np.clip(lit, 0, 1)


def catchlights(col, eyes):
    for inside, eu, ev in eyes:
        g1 = np.sqrt(((eu + 0.30) / 0.36) ** 2 + ((ev - 0.38) / 0.32) ** 2)
        g2 = np.sqrt(((eu - 0.38) / 0.15) ** 2 + ((ev + 0.30) / 0.14) ** 2)
        m1, m2 = inside & (g1 < 1.0), inside & (g2 < 1.0)
        col[m1] = mix(col[m1], np.array((1.0, 1.0, 1.0)), sstep(1.0, 0.8, g1)[m1])
        col[m2] = mix(col[m2], np.array((1.0, 0.98, 0.94)), sstep(1.0, 0.75, g2)[m2])
    return col


# =============================================================================================
# build
# =============================================================================================
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
mat = bpy.data.materials.new("BabyDragon_Atlas")
mat.use_nodes = True


def world_bounds_early(o):
    ws = [o.matrix_world @ vv.co for vv in o.data.vertices]
    return ([min(w[k] for w in ws) for k in range(3)], [max(w[k] for w in ws) for k in range(3)])


def make_object(name, pid, vf, material):
    vs, fs = vf
    piv = PIVOT[name]
    bm = bmesh.new()
    bv = [bm.verts.new(tuple(v)) for v in vs]
    for f in fs:
        try:
            bm.faces.new([bv[i] for i in f])
        except ValueError:
            pass
    bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=bm.edges[:])
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    vol = 0.0
    for fc in bm.faces:
        a = [lv.vert.co for lv in fc.loops]
        for i in range(1, len(a) - 1):
            vol += a[0].dot(a[i].cross(a[i + 1]))
    if vol < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        log(name, "flipped inside-out")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.transform(Matrix.Translation(-piv))
    me.materials.append(material)
    ob = bpy.data.objects.new(name, me)
    ob.location = piv
    ob.pass_index = pid
    scene.collection.objects.link(ob)
    return ob


Gf, _, fl_ = body_field(H_FINE)
FUSED["body"] = (Gf, fl_)
Gf, _, fl_ = head_field(H_FINE, True)
FUSED["head"] = (Gf, fl_)
Gf, _, fl_ = tail_field(H_FINE)
FUSED["tail"] = (Gf, fl_)
del Gf, fl_
Gc, Fc, _ = body_field(H_BODY)
body_vf = extract(Gc, Fc, None, "body")
Gc, Fc, _ = head_field(H_HEAD, False)
head_vf = extract(Gc, Fc, None, "head")
Gc, Fc = leg_field(H_LEG)
leg_l = extract(Gc, Fc, None, "leg")
Gc, Fc, _ = tail_field(H_TAIL)
tail_vf = extract(Gc, Fc, None, "tail")
Gc, Fc = wing_field(0.02)
wing_l = extract(Gc, Fc, 560, "wing")
Gc, Fc = flame_field(0.012)
flame_vf = extract(Gc, Fc, 200, "flame")
del Gc, Fc

TREES = {P_HEAD: BVHTree.FromPolygons(head_vf[0].tolist(), head_vf[1]),
         P_BODY: BVHTree.FromPolygons(body_vf[0].tolist(), body_vf[1]),
         P_TAIL: BVHTree.FromPolygons(tail_vf[0].tolist(), tail_vf[1])}
glow_vf = {}
for gpid, marks in MARKS.items():
    pts = [ember_patch(TREES[CARRIER_PID[gpid]], gpid, *mk) for mk in marks]
    if gpid == P_GTAIL:
        pts.append(flame_vf)
    glow_vf[gpid] = merge(pts)
GLOW_NAME = {P_GCHEEK: PFX + "Cheeks_Glow", P_GBODY: PFX + "Embers_Glow", P_GTAIL: PFX + "TailFlame_Glow"}
for gpid, (vs_, _) in glow_vf.items():
    PIVOT[GLOW_NAME[gpid]] = V(*np.round((vs_.min(0) + vs_.max(0)) / 2, 4))

specs = [(PFX + "Body", P_BODY, body_vf), (PFX + "Head", P_HEAD, head_vf),
         (PFX + "WingL", P_WINGL, wing_l), (PFX + "WingR", P_WINGR, mirror(wing_l)),
         (PFX + "LegL", P_LEGL, leg_l), (PFX + "LegR", P_LEGR, mirror(leg_l)),
         (PFX + "Tail", P_TAIL, tail_vf)] + [(GLOW_NAME[g], g, glow_vf[g]) for g in GLOW_PIDS]
objs = [make_object(n, pid, vf, mat) for n, pid, vf in specs]
parts = {o.name: o for o in objs}
GLOWS = [parts[GLOW_NAME[g]] for g in GLOW_PIDS]
log("built", {o.name: len(o.data.polygons) for o in objs})


def select_only(obs, active=None):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or obs[0]


def tri_count(o):
    o.data.calc_loop_triangles()
    return len(o.data.loop_triangles)


select_only(objs)
bpy.ops.object.shade_flat()     # faceted: broad planes like cut gemstone facets

if SHAPE:
    for o in objs:
        me = o.data
        mw = o.matrix_world
        Pv = np.array([(mw @ v.co)[:] for v in me.vertices])
        Nv = np.array([(mw.to_3x3() @ v.normal)[:] for v in me.vertices])
        Nv /= np.maximum(np.linalg.norm(Nv, axis=1), 1e-9)[:, None]
        col, hard, eyes = paint_all(Pv, Nv, np.full(len(Pv), o.pass_index))
        sh = 0.70 + 0.30 * np.clip(Nv @ (np.array((-0.5, -0.62, 0.62)) / 0.93), 0, 1)
        col = catchlights(np.clip(col * sh[:, None], 0, 1), eyes)
        ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
        rgba = np.concatenate([col, np.ones((len(col), 1))], 1)
        ca.data.foreach_set("color", rgba.ravel().astype(np.float32))
    nt = mat.node_tree
    nt.nodes.clear()
    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "Col"
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bs.inputs["Roughness"].default_value = 0.85
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(vc.outputs["Color"], bs.inputs["Base Color"])
    nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])
    tris = {o.name: tri_count(o) for o in objs}
    log("triangles", sum(tris.values()), tris)
else:
    for o in objs:
        fa = o.data.attributes.new("fnrm", "FLOAT_VECTOR", "FACE")
        fa.data.foreach_set("vector", np.array([pl.normal for pl in o.data.polygons], np.float32).ravel())

    # ---- UVs: smart project, then a denser cylindrical island for the visible face -------------
    select_only(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(68), island_margin=0.006, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    ratios = []
    for o in objs:
        me = o.data
        uvl = me.uv_layers.active.data
        for poly in me.polygons:
            if poly.area < 1e-6:
                continue
            uvs = [uvl[li].uv for li in poly.loop_indices]
            a = sum(abs((uvs[i] - uvs[0]).cross(uvs[i + 1] - uvs[0])) * 0.5 for i in range(1, len(uvs) - 1))
            ratios.append(math.sqrt(a / poly.area))
    base_ratio = float(np.median(ratios))
    head_obj = parts[PFX + "Head"]
    hm = head_obj.data
    uvl = hm.uv_layers.active.data
    FACE_DENSITY, FACE_AXIS = 2.0, (HEAD_C[0], HEAD_C[1])
    mw = head_obj.matrix_world
    hbm = bmesh.new()
    hbm.from_mesh(hm)
    hbm.transform(mw)
    htree = BVHTree.FromBMesh(hbm)
    n_face = 0
    for poly in hm.polygons:
        c = mw @ poly.center
        nrm = poly.normal
        radial = V(c.x - FACE_AXIS[0], c.y - FACE_AXIS[1], 0.0)
        if radial.length < 1e-6:
            continue
        radial.normalize()
        ang = math.atan2(c.x - FACE_AXIS[0], -(c.y - FACE_AXIS[1]))
        if not (nrm.dot(radial) > 0.35 and nrm.y < -0.1 and abs(ang) < 1.2 and 1.12 < c.z < 1.98):
            continue
        if htree.ray_cast(c + nrm * 0.002, nrm, 1.0)[0] is not None:
            continue
        n_face += 1
        for li in poly.loop_indices:
            co = mw @ hm.vertices[hm.loops[li].vertex_index].co
            a2 = math.atan2(co.x - FACE_AXIS[0], -(co.y - FACE_AXIS[1]))
            uvl[li].uv = (a2 * 0.60 * base_ratio * FACE_DENSITY + 5.0, co.z * base_ratio * FACE_DENSITY)
    hbm.free()
    select_only(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, margin=0.008)
    bpy.ops.object.mode_set(mode="OBJECT")
    for o in objs:
        o.data.uv_layers.active.name = "UVMap"
    log("unwrapped; base texel ratio", round(base_ratio, 4), "face-island faces", n_face)

    # ---- bake data maps (glow shells moved aside so they cast no AO on the painted skin) ---------
    for g in GLOWS:
        g.location.x += 10.0
    bpy.context.view_layer.update()
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.render.bake.use_selected_to_active = False
    nt = mat.node_tree

    def bake_pass(kind, samples):
        nt.nodes.clear()
        N_, L_ = nt.nodes.new, nt.links.new
        geo = N_("ShaderNodeNewGeometry")
        em = N_("ShaderNodeEmission")
        out = N_("ShaderNodeOutputMaterial")
        L_(em.outputs["Emission"], out.inputs["Surface"])

        def enc(sock, scale):
            m = N_("ShaderNodeVectorMath")
            m.operation = "MULTIPLY_ADD"
            L_(sock, m.inputs[0])
            m.inputs[1].default_value = (scale,) * 3
            m.inputs[2].default_value = (0.5,) * 3
            L_(m.outputs["Vector"], em.inputs["Color"])

        def attr(name, out_="Fac"):
            a = N_("ShaderNodeAttribute")
            a.attribute_type = "GEOMETRY"
            a.attribute_name = name
            return a.outputs[out_]

        if kind == "pos":
            enc(geo.outputs["Position"], 0.04)
        elif kind == "nrm":
            enc(geo.outputs["Normal"], 0.5)
        elif kind == "fnrm":
            enc(attr("fnrm", "Vector"), 0.5)
        elif kind == "bev":
            b = N_("ShaderNodeBevel")
            b.samples = 16
            b.inputs["Radius"].default_value = 0.015
            enc(b.outputs["Normal"], 0.5)
        elif kind == "attr":
            cmb = N_("ShaderNodeCombineXYZ")
            oi = N_("ShaderNodeObjectInfo")
            mp = N_("ShaderNodeMath")
            mp.operation = "MULTIPLY"
            L_(oi.outputs["Object Index"], mp.inputs[0])
            mp.inputs[1].default_value = 1.0 / 16.0
            L_(mp.outputs[0], cmb.inputs[0])
            L_(cmb.outputs["Vector"], em.inputs["Color"])
        elif kind == "occ":
            cmb = N_("ShaderNodeCombineXYZ")
            a1 = N_("ShaderNodeAmbientOcclusion")
            a1.samples = 16
            a1.inputs["Distance"].default_value = 0.10
            a2 = N_("ShaderNodeAmbientOcclusion")
            a2.samples = 16
            a2.inputs["Distance"].default_value = 0.5
            L_(a1.outputs["AO"], cmb.inputs[0])
            L_(a2.outputs["AO"], cmb.inputs[1])
            L_(geo.outputs["Pointiness"], cmb.inputs[2])
            L_(cmb.outputs["Vector"], em.inputs["Color"])
        img = bpy.data.images.new(f"bake_{kind}", BAKE, BAKE, alpha=True, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
        tn = N_("ShaderNodeTexImage")
        tn.image = img
        nt.nodes.active = tn
        scene.cycles.samples = samples
        select_only(objs)
        bpy.ops.object.bake(type="EMIT", margin=int(16 * BAKE / 2048) + 4, margin_type="EXTEND", use_clear=True)
        arr = np.empty(BAKE * BAKE * 4, np.float32)
        img.pixels.foreach_get(arr)
        bpy.data.images.remove(img)
        log("baked", kind)
        return arr.reshape(-1, 4)

    maps = {k: bake_pass(k, s) for k, s in (("pos", 1), ("nrm", 1), ("fnrm", 1), ("attr", 1),
                                             ("occ", 12 if QUICK else 24), ("bev", 8 if QUICK else 12))}
    cov = maps["pos"][:, 3] > 0.5
    idx = np.nonzero(cov)[0]

    def dec(a, s):
        return (a[idx, :3].astype(np.float64) - 0.5) / s

    def unit(a):
        return a / np.maximum(np.linalg.norm(a, axis=1), 1e-6)[:, None]

    P = dec(maps["pos"], 0.04)
    Ns, Nf, Nb = unit(dec(maps["nrm"], 0.5)), unit(dec(maps["fnrm"], 0.5)), unit(dec(maps["bev"], 0.5))
    pf = maps["attr"][idx, 0].astype(np.float64) * 16.0
    part = np.rint(pf).astype(np.int64)
    bbs, trees = {}, {}
    for o in objs:
        lo_, hi_ = world_bounds_early(o)
        bbs[o.pass_index] = (np.array(lo_) - 0.04, np.array(hi_) + 0.04)
        hb = bmesh.new()
        hb.from_mesh(o.data)
        hb.transform(o.matrix_world)
        trees[o.pass_index] = BVHTree.FromBMesh(hb)
        hb.free()
    inside_box = np.zeros(len(P), bool)
    for pid_, (l_, h_) in bbs.items():
        m_ = part == pid_
        inside_box[m_] = np.all((P[m_] >= l_) & (P[m_] <= h_), axis=1)
    sus = (np.abs(pf - part) > 0.04) | ~inside_box
    log("suspicious part ids:", int(sus.sum()), "of", len(P))
    for i in np.nonzero(sus)[0]:
        best, bd = part[i], 1e9
        for pid_, tr_ in trees.items():
            loc_, _, _, dist_ = tr_.find_nearest(Vector(P[i]))
            if loc_ is not None and dist_ < bd:
                best, bd = pid_, dist_
        part[i] = best
    gl = np.isin(part, GLOW_PIDS)
    P[gl, 0] -= 10.0                       # glow texels back to their real place for the painter
    oc = maps["occ"][idx, :3].astype(np.float64)
    ao_s, ao_l, curv = np.clip(oc[:, 0], 0, 1), np.clip(oc[:, 1], 0, 1), oc[:, 2]
    del maps
    edge = sstep(0.995, 0.93, np.sum(Nb * Ns, axis=1)) * sstep(0.49, 0.53, curv)
    colour, hard, eyes = paint_all(P, Ns, part)
    colour = light(colour, P, Ns, Nf, hard, ao_s, ao_l, edge, part)
    colour = catchlights(colour, eyes)
    for g in GLOWS:
        g.location.x -= 10.0
    bpy.context.view_layer.update()

    full = np.zeros((BAKE * BAKE, 4), np.float32)
    full[idx, :3] = colour
    full[:, 3] = 1.0
    full[~cov, :3] = RED_SH
    img4 = full.reshape(BAKE, BAKE, 4)
    if BAKE != ATLAS:
        f = BAKE // ATLAS
        img4 = img4.reshape(ATLAS, f, ATLAS, f, 4).mean(axis=(1, 3))
    atlas = bpy.data.images.new(f"{STEM}-src", ATLAS, ATLAS, alpha=False)
    atlas.pixels.foreach_set(img4.astype(np.float32).ravel())
    atlas.filepath_raw = str(TEX_PATH if not QUICK else OUT / f"{STEM}-atlas.png")
    atlas.file_format = "PNG"
    atlas.save()
    tex_file = Path(atlas.filepath_raw)
    bpy.data.images.remove(atlas)
    log("painted", tex_file.name)

    nt.nodes.clear()
    tex_img = bpy.data.images.load(str(tex_file), check_existing=False)
    tex_img.name = STEM
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bs.inputs["Roughness"].default_value = 0.85
    bs.inputs["Specular IOR Level"].default_value = 0.15
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = tex_img
    nt.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])
    for o in objs:
        if "fnrm" in o.data.attributes:
            o.data.attributes.remove(o.data.attributes["fnrm"])
    tris = {o.name: tri_count(o) for o in objs}
    log("triangles", sum(tris.values()), tris)

# =============================================================================================
# reports (Studio axes = (-x, z, y) of Blender)
# =============================================================================================
bpy.context.view_layer.update()
CARRIER = {GLOW_NAME[P_GCHEEK]: PFX + "Head", GLOW_NAME[P_GBODY]: PFX + "Body", GLOW_NAME[P_GTAIL]: PFX + "Tail"}
JOINT_PARENT = {n: (None if n == PFX + "Body" else CARRIER.get(n, PFX + "Body")) for n in PIVOT}
JOINT_NAME = {PFX + "Body": "root (belly centre)", PFX + "Head": "neck, hidden inside the head and chest",
              PFX + "WingL": "shoulder (round wing root sunk into the upper back)",
              PFX + "WingR": "shoulder (round wing root sunk into the upper back)",
              PFX + "LegL": "hip, inside the round thigh", PFX + "LegR": "hip, inside the round thigh",
              PFX + "Tail": "tail root, inside the lower back",
              GLOW_NAME[P_GCHEEK]: "centre of the cheek ember marks (welded to the head, Neon)",
              GLOW_NAME[P_GBODY]: "centre of the flank and chest ember marks (welded to the body, Neon)",
              GLOW_NAME[P_GTAIL]: "centre of the tail-tip flame and tail ember dots (welded to the tail, Neon)"}
MOTION = {
    PFX + "Body": "root: waddle roll about Studio Z (+/-7 deg) with a small bob; hop-glide lifts it 0.6 studs and pitches 14 deg nose-down; fire breath leans back 8 deg",
    PFX + "Head": "nod = pitch about Studio X, look = yaw about Studio Y, tilt = roll about Studio Z; fire breath: nose up 22 deg and 0.06 studs forward",
    PFX + "WingL": "flap = rotate about Studio Z through the shoulder (+ raises the left wing in Blender-bone terms; see locomotion_data); glide = spread forward and down",
    PFX + "WingR": "mirror of WingL",
    PFX + "LegL": "waddle swing about Studio X through the hip (+/-22 deg) with a 0.07 stud lift; tucked back 30 deg in a glide",
    PFX + "LegR": "mirror of LegL, opposite phase",
    PFX + "Tail": "swish = yaw about Studio Y (+/-28 deg), counter-swings the waddle",
    GLOW_NAME[P_GCHEEK]: "none (WeldConstraint to the head); Material Neon, gentle Transparency pulse",
    GLOW_NAME[P_GBODY]: "none (WeldConstraint to the body); Material Neon",
    GLOW_NAME[P_GTAIL]: "none (WeldConstraint to the tail); Material Neon, flicker the flame's Transparency",
}


def studio(v):
    return [round(-v[0], 4) + 0.0, round(v[2], 4) + 0.0, round(v[1], 4) + 0.0]


def studio_size(v):
    return [round(v[0], 4), round(v[2], 4), round(v[1], 4)]


def world_bounds(o):
    ws = [o.matrix_world @ vv.co for vv in o.data.vertices]
    return (Vector([min(w[k] for w in ws) for k in range(3)]), Vector([max(w[k] for w in ws) for k in range(3)]))


# ---- locomotion (Blender bone angles: X = pitch about world X, Y = yaw about world Z, Z = roll about world -Y)
def waddle(s):
    rots = {"Body": (0, 0, 7 * s), "LegL": (-22 * s, 0, 0), "LegR": (22 * s, 0, 0),
            "Head": (-3, 4 * s, -5 * s), "Tail": (0, -16 * s, 0),
            "WingL": (0, 0, 16 if s > 0 else 4), "WingR": (0, 0, -4 if s > 0 else -16)}
    locs = {"Body": (0, 0, 0.03), ("LegL" if s > 0 else "LegR"): (0, 0, 0.07)}
    return rots, locs


WADDLE_PASS = ({"Head": (2, 0, 0), "WingL": (0, 0, 8), "WingR": (0, 0, -8)}, {"Body": (0, 0, 0.0)})
WINGS_UP = ({"WingL": (0, 0, 38), "WingR": (0, 0, -38), "Body": (-4, 0, 0), "Head": (-6, 0, 0), "Tail": (6, 0, 0)},
            {"Body": (0, 0, 0.30)})
WINGS_DOWN = ({"WingL": (0, -10, -34), "WingR": (0, 10, 34), "Body": (4, 0, 0), "LegL": (14, 0, 0), "LegR": (14, 0, 0)},
              {"Body": (0, 0, 0.45)})
GLIDE = ({"Body": (14, 0, 0), "Head": (-12, 0, 0), "WingL": (40, 0, -36), "WingR": (40, 0, 36),
          "LegL": (30, 0, 0), "LegR": (30, 0, 0), "Tail": (-14, 0, 0)}, {"Body": (0, 0, 0.60)})
FIRE = ({"Body": (-8, 0, 0), "Head": (-22, 0, 0), "WingL": (0, 30, 16), "WingR": (0, -30, -16),
         "LegL": (-12, 0, 6), "LegR": (12, 0, -6), "Tail": (-6, 0, 0)}, {"Head": (0, -0.06, 0.02)})
SWISH = ({"Tail": (0, 28, 0), "Head": (0, -10, 4), "Body": (0, 0, -3)}, {})
BONES = ["Body", "Head", "WingL", "WingR", "LegL", "LegR", "Tail"]


def studio_pose(rl):
    rots, locs = rl
    out = {}
    for b in BONES:
        r, l = rots.get(b, (0, 0, 0)), locs.get(b, (0, 0, 0))
        if any(r) or any(l):
            out[PFX + b] = {"rot_deg_studio_xyz": [-r[0] + 0.0, r[1] + 0.0, -r[2] + 0.0],
                            "offset_studs_studio_xyz": [-l[0] + 0.0, l[2] + 0.0, l[1] + 0.0]}
    return out


report = {"asset": STEM, "blender_version": bpy.app.version_string,
          "authoring": "final Roblox stud size (1 Blender unit = 1 stud); import at 1:1, do not scale",
          "axes": "Blender Z-up, front -Y, the dragon's left +X; feet on z = 0",
          "texture": f"textures/{TEX_PATH.name} ({ATLAS}x{ATLAS}, shared by every part)", "parts": {}}
lo_all, hi_all = Vector((1e9,) * 3), Vector((-1e9,) * 3)
for name, o in parts.items():
    me = o.data
    me.calc_loop_triangles()
    if me.uv_layers:
        uv = me.uv_layers.active.data
        us, vs = [d.uv.x for d in uv], [d.uv.y for d in uv]
        uvr = [round(min(us), 4), round(max(us), 4), round(min(vs), 4), round(max(vs), 4)]
    else:
        uvr = None
    lo, hi = world_bounds(o)
    lo_all = Vector([min(lo_all[k], lo[k]) for k in range(3)])
    hi_all = Vector([max(hi_all[k], hi[k]) for k in range(3)])
    report["parts"][name] = {
        "triangles": len(me.loop_triangles), "vertices": len(me.vertices),
        "dimensions_studs": [round(v, 4) for v in o.dimensions],
        "bbox_min": [round(v, 4) for v in lo], "bbox_max": [round(v, 4) for v in hi],
        "pivot": [round(v, 4) for v in o.location], "pivot_is": JOINT_NAME[name],
        "joint_parent": JOINT_PARENT[name], "uv_range": uvr}
report["total_triangles"] = sum(pp["triangles"] for pp in report["parts"].values())
size = hi_all - lo_all
report["overall"] = {"bbox_min": [round(v, 4) for v in lo_all], "bbox_max": [round(v, 4) for v in hi_all],
                     "height_studs": round(size.z, 4), "length_studs": round(size.y, 4), "width_studs": round(size.x, 4)}
log("overall (w, len, h)", tuple(round(v, 3) for v in (size.x, size.y, size.z)), "tris", report["total_triangles"])

body_pivot = parts[PFX + "Body"].location.copy()
head_pivot = parts[PFX + "Head"].location.copy()
tail_pivot = parts[PFX + "Tail"].location.copy()
MOUTH_P = Vector(FACE["mouth"]["c"]) + Vector(FACE["mouth"]["n"]) * 0.05
FLAME_TIP = V(0.0, 1.26, 1.10)
BACK_EMBER = V(0.0, 0.40, 1.20)
wd_, wc_, _ = wing_frame()
WT_ = W0 + (wd_ * 0.74 + wc_ * 0.03) * WS
WINGTIP = {1: V(*WT_), -1: V(*(WT_ * np.array((-1, 1, 1))))}
GLOW_RGB = [255, 150, 46]
install = {
    "asset": STEM, "rarity": "Legendary",
    "strong_suit": "Fire: small fire breaths that burn groups (BurnChance on every enemy in the breath cone)",
    "accent": "Neon ember markings (cheeks, flanks, chest, tail dots) and a Neon tail-tip flame, plus the particle specs below",
    "role_prop": "the fire itself (breath + tail flame); no extra prop",
    "axis": "studio = (-x, z, y) of blender; Blender front -Y = Studio front -Z",
    "units": "studs; the model is at final size, import 1:1 and do not scale",
    "sides": "L/R are the dragon's own left/right; its left is Blender +X = Studio -X",
    "origin": "all positions are relative to the model origin = the ground point under the model centre (Blender world origin)",
    "ground_point": studio((0.0, 0.0, 0.0)), "overall_size": studio_size(size),
    "overall_center": studio((lo_all + hi_all) / 2), "texture": f"textures/{TEX_PATH.name}",
    "texture_note": "one shared atlas on every MeshPart via MeshPart.TextureID. The three *_Glow parts: Material = Neon, Color = "
                    f"{GLOW_RGB} (their atlas texels are that colour too)",
    "rest_rotation": "every part has identity rotation relative to the model at rest",
    "rig": "one Motor6D per animated part: Part0 = joint_parent, Part1 = the part, C0/C1 at the part's pivot; the *_Glow parts are WeldConstraints to their carrier",
    "parts": {}}
for name, o in parts.items():
    lo, hi = world_bounds(o)
    install["parts"][name] = {
        "center": studio((lo + hi) / 2), "size": studio_size(hi - lo), "pivot": studio(o.location),
        "pivot_from_body_pivot": studio(o.location - body_pivot), "pivot_is": JOINT_NAME[name],
        "joint_parent": JOINT_PARENT[name], "suggested_motion": MOTION[name]}
install["locomotion"] = "waddle_glide"
install["locomotion_data"] = {
    "gait": "waddle: quick side-to-side waddle on the stubby hind legs, body rolls over the planted foot, the wings give little "
            "balance flaps and the tail counter-swings; every few seconds (or to cross gaps) a short hop-glide with the wings spread",
    "angle_convention": "per part, rotation about the part's own pivot in Studio axes (Roblox CFrame.Angles, degrees) plus a translation "
                        "offset in studs applied in the parent's frame (Motor6D C0). Only parts that move are listed; others stay at rest. "
                        "Blender bone angles in the previews map as Studio X = -bone X, Studio Y = bone Y, Studio Z = -bone Z.",
    "waddle": {"step_period_s": 0.55, "loop": ["waddle_A", "waddle_pass", "waddle_B", "waddle_pass"],
               "body_roll_deg": 7, "leg_swing_deg": 22, "foot_lift_studs": 0.07, "wing_balance_flap_deg": 16,
               "frames": {"waddle_A": studio_pose(waddle(1)), "waddle_pass": studio_pose(WADDLE_PASS),
                          "waddle_B": studio_pose(waddle(-1))}},
    "hop_glide": {"sequence": [["wings_up", 0.12], ["wings_down", 0.10], ["glide", 0.55], ["wings_up", 0.10], ["land = waddle_pass", 0.15]],
                  "note": "seconds per key; glide holds the wings spread while the root travels ~3 studs forward at 0.6 studs up; ease the land",
                  "frames": {"wings_up": studio_pose(WINGS_UP), "wings_down": studio_pose(WINGS_DOWN), "glide": studio_pose(GLIDE)}},
    "fire_breath": {"note": "head forward and up, mouth (painted open) toward the target, wings swept back, legs braced; "
                            "ease in 0.12 s, hold 0.6 s while the fire_breath emitter runs, ease out 0.2 s",
                    "pose": studio_pose(FIRE)},
    "tail_swish": {"note": "idle accent, +/-28 deg yaw, 0.8 s period", "pose": studio_pose(SWISH)},
}
FIRE_COLOURS = [[0.0, [255, 240, 150]], [0.22, [255, 178, 60]], [0.5, [240, 84, 36]], [0.75, [150, 52, 40]], [1.0, [72, 60, 60]]]
EMBER_COLOURS = [[0.0, [255, 222, 130]], [0.5, [255, 146, 50]], [1.0, [220, 70, 40]]]
install["vfx"] = [
    {"kind": "fire_breath", "part": PFX + "Head", "attachment_position": studio(MOUTH_P),
     "attachment_from_part_pivot": studio(MOUTH_P - head_pivot),
     "attachment_axis": "emit along the head's forward (Studio -Z of the head) so the cone follows the 22 deg nose-up breath pose",
     "trigger": "burst-driven while breathing: Enabled = true for the 0.6 s hold (or :Emit(6) every 0.05 s), off otherwise",
     "cone_length_studs": 5.0, "cone_half_angle_deg": 18, "cone_end_radius_studs": 1.6,
     "burn_hitbox": "server cone from the mouth: 5 studs long, 18 deg half-angle (end radius ~1.6); every enemy inside rolls BurnChance",
     "colour_sequence": FIRE_COLOURS,
     "suggested": {"Rate": 90, "Lifetime": [0.48, 0.56], "Speed": [9, 10.5], "SpreadAngle": [18, 18],
                   "EmissionDirection": "Front", "Size": "0.25 -> 0.85 (t 0.4) -> 1.3", "Transparency": "0.05 -> 0.2 (t 0.6) -> 1",
                   "LightEmission": 0.9, "LightInfluence": 0, "Acceleration": [0, 1.5, 0], "Drag": 0,
                   "Rotation": [0, 360], "RotSpeed": [-140, 140], "ZOffset": 0.4, "LockedToPart": False,
                   "Texture": "soft round flame puff sprite (e.g. Roblox's fire_main particle texture or a soft cloud puff)",
                   "note": "speed x lifetime ~ 5 studs = cone length; the colour runs yellow -> orange -> red -> smoke",
                   "PointLight_while_breathing": {"Color": [255, 150, 60], "Brightness": 2, "Range": 8, "Shadows": False}}},
    {"kind": "ambient_embers", "parts": [PFX + "Body", PFX + "Tail"],
     "attachments": {PFX + "Body": {"position": studio(BACK_EMBER), "from_part_pivot": studio(BACK_EMBER - body_pivot)},
                     PFX + "Tail": {"position": studio(FLAME_TIP), "from_part_pivot": studio(FLAME_TIP - tail_pivot)}},
     "enabled": "always on", "colour_sequence": EMBER_COLOURS,
     "suggested": {"Rate": 2.5, "Lifetime": [1.2, 1.8], "Speed": [0.3, 0.7], "SpreadAngle": [25, 25],
                   "EmissionDirection": "Top", "Size": "0.10 -> 0.07 (t 0.6) -> 0", "Transparency": "0 -> 0.2 (t 0.7) -> 1",
                   "LightEmission": 1, "LightInfluence": 0, "Acceleration": [0, 1.0, 0], "Drag": 0.5,
                   "Rotation": [0, 360], "RotSpeed": [-60, 60], "LockedToPart": False,
                   "Texture": "small soft spark dot", "note": "a few slow sparks drifting up; never a stream"}},
    {"kind": "glide_trail", "parts": [PFX + "WingL", PFX + "WingR"],
     "attachments_from_wing_pivot": {PFX + "WingL": studio(WINGTIP[1] - PIVOT[PFX + "WingL"]),
                                     PFX + "WingR": studio(WINGTIP[-1] - PIVOT[PFX + "WingR"])},
     "attachment_positions": {PFX + "WingL": studio(WINGTIP[1]), PFX + "WingR": studio(WINGTIP[-1])},
     "enabled": "glide frames only (hop_glide glide key)", "colour_sequence": EMBER_COLOURS,
     "suggested": {"Rate": 16, "Lifetime": [0.3, 0.45], "Speed": [0.1, 0.3], "SpreadAngle": [10, 10],
                   "Size": "0.14 -> 0", "Transparency": "0.35 -> 1", "LightEmission": 1, "LightInfluence": 0,
                   "Acceleration": [0, 0.5, 0], "Drag": 1, "LockedToPart": False, "Texture": "small soft spark dot",
                   "note": "faint ember trail off each wingtip; a Trail between two wingtip attachments (Lifetime 0.25, WidthScale 1 -> 0) also works"}},
    {"kind": "neon_glow", "parts": [GLOW_NAME[g] for g in GLOW_PIDS], "colour_rgb": GLOW_RGB, "material": "Neon",
     "suggested": {"Transparency_idle": [0.0, 0.2], "pulse_period_s": 1.6,
                   "TailFlame_flicker": "random Transparency 0 -> 0.25 every 0.08-0.15 s",
                   "PointLight_on_tail_flame": {"Color": [255, 150, 60], "Brightness": 0.8, "Range": 4, "Shadows": False}}},
]

if not QUICK:
    (ROOT / "polygon-report.json").write_text(json.dumps(report, indent=2))
    (ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=2))
    select_only(objs, parts[PFX + "Body"])
    bpy.ops.export_scene.gltf(filepath=str(GLB_PATH), export_format="GLB", use_selection=True, export_apply=True)
    select_only(objs, parts[PFX + "Body"])
    bpy.ops.export_scene.fbx(filepath=str(FBX_PATH), use_selection=True, object_types={"MESH"},
                             axis_forward="-Z", axis_up="Y", path_mode="COPY", embed_textures=True,
                             add_leaf_bones=False)
    log("exported", FBX_PATH.name, GLB_PATH.name)

# =============================================================================================
# armature (Blender only, for posing previews; exports are the plain rigid parts)
# =============================================================================================
arm_data = bpy.data.armatures.new("BabyDragon_Rig")
arm = bpy.data.objects.new("BabyDragon_Rig", arm_data)
scene.collection.objects.link(arm)
select_only([arm])
bpy.ops.object.mode_set(mode="EDIT")
ebs = {}
for b in BONES:
    eb = arm_data.edit_bones.new(b)
    eb.head = PIVOT[PFX + b]
    eb.tail = PIVOT[PFX + b] + Vector((0, 0, 0.25))
    eb.roll = 0.0
    ebs[b] = eb
for b in BONES:
    if b != "Body":
        ebs[b].parent = ebs["Body"]
bpy.ops.object.mode_set(mode="OBJECT")
for name, o in parts.items():
    mwo = o.matrix_world.copy()
    o.parent = arm
    o.parent_type = "BONE"
    o.parent_bone = CARRIER.get(name, name).replace(PFX, "")
    bpy.context.view_layer.update()
    o.matrix_world = mwo
bpy.context.view_layer.update()


def pose(rl):
    rots, locs = rl if isinstance(rl, tuple) else (rl, {})
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = [math.radians(v) for v in rots.get(pb.name, (0, 0, 0))]
        d = locs.get(pb.name, (0, 0, 0))
        pb.location = (d[0], d[2], -d[1])
    bpy.context.view_layer.update()


if not QUICK:
    for im in bpy.data.images:
        if im.source == "FILE":
            im.pack()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), relative_remap=True)
    log("saved", BLEND_PATH.name)

# =============================================================================================
# previews (Eevee); the glow parts show emissive like Neon
# =============================================================================================
gm = bpy.data.materials.new("BabyDragon_Neon_Preview")
gm.use_nodes = True
gnt = gm.node_tree
gnt.nodes.clear()
ge = gnt.nodes.new("ShaderNodeEmission")
ge.inputs["Color"].default_value = (1.0, 0.30, 0.03, 1)
ge.inputs["Strength"].default_value = 1.6
go = gnt.nodes.new("ShaderNodeOutputMaterial")
gnt.links.new(ge.outputs[0], go.inputs[0])
for g in GLOWS:
    g.data.materials[0] = gm

scene.render.engine = "BLENDER_EEVEE"
scene.view_settings.view_transform = "Standard"
scene.render.image_settings.file_format = "PNG"
world = bpy.data.worlds.new("Sky")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.66, 0.82, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
scene.world = world


def add_sun(name, energy, rot, angle, color):
    L = bpy.data.lights.new(name, "SUN")
    L.energy, L.angle, L.color = energy, math.radians(angle), color
    ob = bpy.data.objects.new(name, L)
    ob.rotation_euler = tuple(math.radians(v) for v in rot)
    scene.collection.objects.link(ob)


add_sun("Key", 2.6, (50, 0, -35), 8, (1.0, 0.96, 0.9))
add_sun("Rim", 1.4, (60, 0, 150), 10, (0.8, 0.88, 1.0))
bpy.ops.mesh.primitive_circle_add(vertices=96, radius=90, fill_type="NGON", location=(0, 0, 0))
floor = bpy.context.object
fm_ = bpy.data.materials.new("Preview_Floor")
fm_.use_nodes = True
fm_.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.36, 0.40, 0.46, 1)
fm_.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
floor.data.materials.append(fm_)
cam = bpy.data.objects.new("PreviewCam", bpy.data.cameras.new("PreviewCam"))
scene.collection.objects.link(cam)
scene.camera = cam

# placeholder fire cone for the fire-breath pose frame (preview only, never exported)
bpy.ops.mesh.primitive_cone_add(vertices=20, radius1=0.55, radius2=0.04, depth=1.7, location=(0, 0, -50))
cone = bpy.context.object
cone.name = "Preview_FireCone"
cm_ = bpy.data.materials.new("Preview_Fire")
cm_.use_nodes = True
cnt = cm_.node_tree
cnt.nodes.clear()
tco = cnt.nodes.new("ShaderNodeTexCoord")
sep = cnt.nodes.new("ShaderNodeSeparateXYZ")
ramp = cnt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[0].color = 0.0, (0.85, 0.12, 0.04, 1)
ramp.color_ramp.elements[1].position, ramp.color_ramp.elements[1].color = 1.0, (1.0, 0.92, 0.45, 1)
mid = ramp.color_ramp.elements.new(0.55)
mid.color = (1.0, 0.45, 0.06, 1)
cem = cnt.nodes.new("ShaderNodeEmission")
cem.inputs["Strength"].default_value = 2.5
cout = cnt.nodes.new("ShaderNodeOutputMaterial")
cnt.links.new(tco.outputs["Generated"], sep.inputs[0])
cnt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
cnt.links.new(ramp.outputs["Color"], cem.inputs["Color"])
cnt.links.new(cem.outputs[0], cout.inputs[0])
cone.data.materials.append(cm_)
HEAD_OBJ = parts[PFX + "Head"]
HEAD_REST = HEAD_OBJ.matrix_world.copy()


def place_cone(on):
    if not on:
        cone.location = (0, 0, -50)
        return
    M = HEAD_OBJ.matrix_world @ HEAD_REST.inverted()
    mp = M @ MOUTH_P
    dr = (M.to_3x3() @ Vector((0.0, -1.0, 0.0))).normalized()
    cone.rotation_euler = (-dr).to_track_quat("Z", "Y").to_euler()
    cone.location = mp + dr * (0.85 + 0.02)
    bpy.context.view_layer.update()


def shoot(path, loc, target, lens=85, res=(1200, 1200)):
    cam.data.type, cam.data.lens = "PERSP", lens
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    log("rendered", Path(path).name)
    return Path(path)


def around(target, direction, dist):
    return Vector(target) + Vector(direction).normalized() * dist


def make_sheet(items, cols, tile, out_path, title, sub=None):
    sc = bpy.data.scenes.new("Sheet")
    sc.render.engine = "BLENDER_EEVEE"
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "PNG"
    wd = bpy.data.worlds.new("SheetWorld")
    wd.use_nodes = True
    wd.node_tree.nodes["Background"].inputs["Color"].default_value = (0.86, 0.87, 0.89, 1)
    sc.world = wd
    rows = math.ceil(len(items) / cols)
    k = 0.01
    lab_h, head_h, pad = 44, (96 if sub else 64), 10
    W = cols * (tile + pad) + pad
    H = rows * (tile + lab_h + pad) + head_h + pad
    sc.render.resolution_x, sc.render.resolution_y = W, H
    cam_ = bpy.data.objects.new("SheetCam", bpy.data.cameras.new("SheetCam"))
    cam_.data.type = "ORTHO"
    cam_.data.ortho_scale = max(W, H) * k
    cam_.location = (W * k / 2, -H * k / 2, 10)
    sc.collection.objects.link(cam_)
    sc.camera = cam_

    def txt(body, x, y, size, color=(0.03, 0.03, 0.04), align="CENTER"):
        cu = bpy.data.curves.new("SheetText", "FONT")
        cu.body, cu.size, cu.align_x = body, size, align
        m = bpy.data.materials.new("SheetInk")
        m.use_nodes = True
        nt_ = m.node_tree
        nt_.nodes.clear()
        e = nt_.nodes.new("ShaderNodeEmission")
        e.inputs["Color"].default_value = (*color, 1)
        o_ = nt_.nodes.new("ShaderNodeOutputMaterial")
        nt_.links.new(e.outputs[0], o_.inputs[0])
        cu.materials.append(m)
        ob = bpy.data.objects.new("SheetText", cu)
        ob.location = (x, y, 0.1)
        sc.collection.objects.link(ob)

    txt(title, pad * k, -40 * k, 26 * k, align="LEFT")
    if sub:
        txt(sub, pad * k, -74 * k, 16 * k, color=(0.25, 0.26, 0.28), align="LEFT")
    for i, (path, text) in enumerate(items):
        r, cidx = divmod(i, cols)
        x0, y0 = pad + cidx * (tile + pad), head_h + r * (tile + lab_h + pad)
        img = bpy.data.images.load(str(path), check_existing=False)
        iw, ih = img.size
        sw, sh = (tile, tile * ih / iw) if iw >= ih else (tile * iw / ih, tile)
        cx, cy = (x0 + tile / 2) * k, -(y0 + tile / 2) * k
        me_ = bpy.data.meshes.new("SheetTile")
        hw_, hh_ = sw * k / 2, sh * k / 2
        me_.from_pydata([(cx - hw_, cy - hh_, 0), (cx + hw_, cy - hh_, 0), (cx + hw_, cy + hh_, 0), (cx - hw_, cy + hh_, 0)],
                        [], [(0, 1, 2, 3)])
        uvl_ = me_.uv_layers.new()
        for li, uvv in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
            uvl_.data[li].uv = uvv
        m = bpy.data.materials.new("SheetTileMat")
        m.use_nodes = True
        nt_ = m.node_tree
        nt_.nodes.clear()
        tx_ = nt_.nodes.new("ShaderNodeTexImage")
        tx_.image = img
        e = nt_.nodes.new("ShaderNodeEmission")
        o_ = nt_.nodes.new("ShaderNodeOutputMaterial")
        nt_.links.new(tx_.outputs["Color"], e.inputs["Color"])
        nt_.links.new(e.outputs[0], o_.inputs[0])
        me_.materials.append(m)
        ob = bpy.data.objects.new("SheetTile", me_)
        sc.collection.objects.link(ob)
        txt(text, cx, -(y0 + tile + 30) * k, 18 * k)
    sc.render.filepath = str(out_path)
    bpy.ops.render.render(write_still=True, scene=sc.name)
    log("sheet", Path(out_path).name)


tgt = V(0, 0.10, 1.12)
ft = V(0, -0.62, 1.62)
D = 9.6
POSES = [
    ("Waddle A: left foot forward, roll +7, balance flap", waddle(1), around(tgt, (-0.8, -0.75, 0.2), D), tgt, False),
    ("Waddle B: right foot forward, roll -7", waddle(-1), around(tgt, (0.8, -0.75, 0.2), D), tgt, False),
    ("Wings up (hop take-off)", WINGS_UP, around(tgt + V(0, 0, 0.3), (-0.6, -0.8, 0.35), D + 0.6), tgt + V(0, 0, 0.3), False),
    ("Glide: wings spread, legs tucked", GLIDE, around(tgt + V(0, 0, 0.6), (-0.5, -0.75, 0.7), D + 0.3), tgt + V(0, 0, 0.6), False),
    ("Fire breath: nose up, wings back, braced", FIRE, around(tgt + V(0, -0.6, 0.1), (-1, -0.25, 0.12), D + 1.6), tgt + V(0, -0.6, 0.1), True),
    ("Tail swish 28 + head look", SWISH, around(tgt, (0.35, 1, 0.45), D), tgt, False),
]

if not NO_PREVIEWS and QUICK:
    items = [(shoot(OUT / "_threeq.png", around(tgt, (-0.75, -0.9, 0.35), D), tgt, res=(800, 800)), "Three-quarter"),
             (shoot(OUT / "_front.png", around(tgt, (0, -1, 0.12), D - 0.6), tgt, res=(800, 800)), "Front"),
             (shoot(OUT / "_side.png", around(tgt, (-1, 0, 0.1), D), tgt, res=(800, 800)), "Side"),
             (shoot(OUT / "_back.png", around(tgt, (0, 1, 0.3), D - 0.4), tgt, res=(800, 800)), "Back"),
             (shoot(OUT / "_face.png", around(ft, (-0.3, -1, 0.12), 4.2), ft, res=(800, 800)), "Face")]
    for i in (3, 4, 0, 5):
        pose(POSES[i][1])
        place_cone(POSES[i][4])
        items.append((shoot(OUT / f"_pose{i}.png", POSES[i][2], POSES[i][3], res=(800, 800)), POSES[i][0]))
    pose({})
    place_cone(False)
    make_sheet(items, 3, 400, OUT / ("shape-sheet.png" if SHAPE else "quick-sheet.png"), "Baby Dragon shape run")
    for pth, _ in items:
        pth.unlink()
elif not NO_PREVIEWS:
    shots = [(shoot(OUT / "threeq.png", around(tgt, (-0.75, -0.9, 0.35), D), tgt), "Three-quarter"),
             (shoot(OUT / "front.png", around(tgt, (0, -1, 0.12), D - 0.6), tgt), "Front"),
             (shoot(OUT / "side.png", around(tgt, (-1, 0, 0.1), D), tgt), "Side (dragon's right)"),
             (shoot(OUT / "back.png", around(tgt, (0, 1, 0.3), D - 0.4), tgt), "Back (follow view)")]
    face = shoot(OUT / "face-closeup.png", around(ft, (-0.3, -1, 0.12), 4.2), ft, res=(1400, 1400))
    pose_items = []
    for i, (lab, rl, loc, t, fire) in enumerate(POSES):
        pose(rl)
        place_cone(fire)
        pose_items.append((shoot(OUT / f"_pose-{i}.png", loc, t, res=(900, 900)), lab))
    pose({})
    place_cone(False)
    make_sheet(pose_items, 3, 450, OUT / "pose-check.png", "Baby Dragon: pose check through the joint pivots",
               "Each part rotates about its own pivot (Blender armature, preview only). Fire cone = placeholder for the particle breath.")
    for pth, _ in pose_items:
        pth.unlink()
    hero = None
    if not NO_HERO:
        scene.render.engine = "CYCLES"
        scene.cycles.samples = 40
        scene.cycles.use_denoising = True
        pose(waddle(1))
        hero = shoot(OUT / "hero.png", around(tgt, (-0.85, -0.85, 0.3), D - 0.8), tgt, res=(900, 900))
        pose({})
        scene.render.engine = "BLENDER_EEVEE"
    items = shots + [(face, "Face close-up"), (OUT / "pose-check.png", "Pose check (waddle, wings up, glide, fire, swish)")]
    make_sheet(items, 3, 520, OUT / "sheet.png",
               f"Baby Dragon pet (Legendary, fire): {report['total_triangles']:,} tris, one 1024 atlas, Neon ember glow parts",
               "Blender 5.2 Eevee renders (glow parts shown emissive). Blender-verified, Studio untested.")
log("done")
