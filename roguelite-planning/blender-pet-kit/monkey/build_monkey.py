"""Monkey pet (Rare, strong suit: attack speed) for the roguelite.

Self-contained generator for background Blender 5.2 (no code imported from other kits).

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 \
        --python build_monkey.py
    ... -- --shape                 fast look-dev: per-vertex painted colours, no bake, a few renders
    ... -- --shape --pose          also the six pose-check frames
    ... -- --quick --out <dir>     1024 bake, a few renders, no exports
    ... -- --no-previews           exports + reports only

Coordinates: Blender Z-up, 1 unit = 1 stud (final size, import 1:1), feet on z = 0, the monkey faces
-Y and its own left is +X. Studio = (-x, z, y) of Blender.

Method (same family as the approved Monkey / Golden Retriever): every rigid part is ONE surface made
from analytic signed-distance volumes joined with smooth unions (real fillets), meshed on a COARSE voxel
lattice (the lattice is the mesh, so facets are even and broad), relaxed back onto the surface and flat
shaded. Colour is painted by 3D position (continuous over every join and UV seam) and baked to one 1024
atlas with icon-style lighting (per-facet key, AO, warm shadow, cool rim).
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
ROOT = Path(__file__).resolve().parent
STEM = "monkey"
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
    print(f"[monkey {time.time() - T0:6.1f}s]", *a, flush=True)


P_BODY, P_HEAD, P_ARML, P_ARMR, P_LEGL, P_LEGR, P_TAIL = range(1, 8)


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
    if elong:
        q[..., 1] = np.sign(q[..., 1]) * np.maximum(np.abs(q[..., 1]) - elong, 0.0)
    r = np.asarray(radii, float)
    k0 = np.linalg.norm(q / r, axis=-1)
    k1 = np.linalg.norm(q / (r * r), axis=-1)
    return np.where(k0 < 1e-6, -min(radii), k0 * (k0 - 1.0) / np.maximum(k1, 1e-9))


def track_axes(axis):
    """Local axes (rows) of an ellipsoid whose local z runs along `axis` (local y ~ world up)."""
    q = Vector(axis).normalized().to_track_quat("Z", "Y")
    return np.array(q.to_matrix()).T


def ell(P, c, radii, axis=None):
    return sd_ell(P, c, AXES if axis is None else track_axes(axis), radii)


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
    """Even out decimated triangles without moving the surface (flip edges, relax, project back)."""
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
        cen = np.array([np.mean([e.other_vert(v).co[:] for e in v.link_edges], axis=0) for v in bm.verts])
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
    ctr = np.array([vo[list(fc)].mean(0) for fc in fo])
    nrm = np.array([np.cross(vo[fc[1]] - vo[fc[0]], vo[fc[2]] - vo[fc[0]]) for fc in fo])
    eps = grid.h
    grad = np.stack([grid.sample(F, ctr + eps * e) - grid.sample(F, ctr - eps * e) for e in np.eye(3)], 1)
    flips = int(np.sum(np.sum(nrm * grad, 1) < 0))
    ec = {}
    for fc in fo:
        for i in range(len(fc)):
            k = tuple(sorted((fc[i], fc[(i + 1) % len(fc)])))
            ec[k] = ec.get(k, 0) + 1
    log(name, "isosurface", n_tri, "tris ->", len(fo), "| against gradient", flips,
        "| non-manifold edges", sum(1 for v in ec.values() if v != 2))
    return vo, fo


def surf_point(G, F, x, z, y0=-1.15, y1=-0.05):
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

# =============================================================================================
# the seven parts (Blender axes, studs). Monkey left = +X.
# =============================================================================================
FUSED = {}         # part -> (grid, named fields) for the painter's masks
FACE = {}          # eye frames for the painter
PIVOT = {
    "Monkey_Body": V(0.0, 0.05, 0.90),
    "Monkey_Head": V(0.0, -0.20, 1.36),
    "Monkey_ArmL": V(0.56, -0.05, 1.18),
    "Monkey_ArmR": V(-0.56, -0.05, 1.18),
    "Monkey_LegL": V(0.40, 0.26, 0.70),
    "Monkey_LegR": V(-0.40, 0.26, 0.70),
    "Monkey_Tail": V(0.0, 0.62, 0.72),
}
HEAD_C = (0.0, -0.28, 1.72)
HEAD_R = (0.74, 0.64, 0.62)
HF_BODY, HF_HEAD, HF_ARM = 0.026, 0.022, 0.026       # fine lattices only drive the painter's masks
H_BODY = float(arg("--hbody", 0.135))                  # coarse lattices ARE the mesh: broad, even facets
H_HEAD = float(arg("--hhead", 0.105))
H_ARM = float(arg("--harm", 0.095))
H_LEG = float(arg("--hleg", 0.090))
H_TAIL = float(arg("--htail", 0.095))
BAND_HALF = 0.14


def zs_band(Y):
    """Headband centre height: a little higher over the forehead, lower at the back."""
    return 2.02 - 0.18 * (Y + 0.30)


def capsule(P, a, b, ra, rb):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ab = b - a
    t = np.clip(((P - a) @ ab) / np.dot(ab, ab), 0.0, 1.0)
    return np.linalg.norm(P - (a + t[..., None] * ab), axis=-1) - (ra + (rb - ra) * t)


def body_field(h):
    G = Grid((-0.95, -0.80, 0.10), (0.95, 1.0, 1.80), h, sym_x=True)
    P = G.P
    chest = ell(P, (0, -0.08, 1.12), (0.58, 0.50, 0.50))
    hip = ell(P, (0, 0.24, 0.74), (0.62, 0.54, 0.48))
    belly = ell(P, (0, -0.18, 0.84), (0.50, 0.42, 0.50))
    F = smin(smin(chest, hip, 0.25), belly, 0.15)
    if h < 0.05:
        F = blur(F, 1)
    return G, F, {}


def head_field(h, store):
    frames = {}
    G = Grid((-1.25, -1.25, 1.00), (1.25, 0.85, 2.55), h, sym_x=True)
    P = G.P
    X, Y, Z = P[..., 0], P[..., 1], P[..., 2]
    base = ell(P, HEAD_C, HEAD_R)
    for s in (1, -1):
        base = smin(base, ell(P, (s * 0.50, -0.50, 1.46), (0.28, 0.28, 0.26)), 0.16)           # chubby cheeks
        base = smin(base, ell(P, (s * 0.84, -0.10, 1.55), (0.34, 0.35, 0.21), axis=(s * 0.85, -0.5, 0.0)), 0.08)   # big round ears, set out at eye level, turned slightly forward
    for name, s in (("eyeL", 1), ("eyeR", -1)):
        p, n = surf_point(G, base, s * 0.34, 1.76, y0=-1.3, y1=-0.1)
        R = track_axes(n)
        u, v = R[0].copy(), R[1].copy()
        if u[0] < 0:
            u = -u
        if v[2] < 0:
            v = -v
        frames[name] = dict(c=p, u=u, v=v, n=n, r=(0.16, 0.19))
    muz = smin(ell(P, (0, -0.80, 1.45), (0.30, 0.20, 0.18)), ell(P, (0, -0.74, 1.32), (0.24, 0.18, 0.12)), 0.08)
    F = smin(base, muz, 0.10)                                                                 # muzzle flows out of the face
    # sweatband: a ring a little proud of the skull, higher over the forehead, tied at the back with a short fused knot
    shell = ell(P, HEAD_C, (HEAD_R[0] + 0.075, HEAD_R[1] + 0.075, HEAD_R[2] + 0.075))
    band = smax(shell, np.abs(Z - zs_band(Y)) - BAND_HALF, 0.02)
    knot = ell(P, (0, 0.42, 1.90), (0.17, 0.14, 0.15))
    for s in (1, -1):
        knot = smin(knot, ell(P, (s * 0.16, 0.62, 1.72), (0.11, 0.085, 0.22), axis=(s * 0.45, 0.55, -0.7)), 0.05)
    band = smin(band, knot, 0.05)
    F = smin(F, band, 0.03)
    if h < 0.05:
        F = blur(F, 1)
    if store:
        FACE.update(frames)
    return G, F, dict(muz=muz, band=band)


ARM_PTS = dict(S=(0.56, -0.05, 1.18), E=(0.77, -0.22, 0.90), W=(0.78, -0.40, 0.56), Fc=(0.78, -0.48, 0.26))
WRAP_A, WRAP_B = (0.775, -0.35, 0.73), (0.78, -0.40, 0.58)


def arm_field(h):
    """Left arm (+X): shoulder ball hidden in the body, chunky arm, sweatband wrap, big fist on the ground."""
    G = Grid((0.05, -0.95, -0.05), (1.15, 0.40, 1.60), h)
    P = G.P
    A = ARM_PTS
    sh = ell(P, A["S"], (0.27, 0.27, 0.27))
    up = capsule(P, A["S"], A["E"], 0.25, 0.20)
    fo = capsule(P, A["E"], A["W"], 0.20, 0.175)
    fist = ell(P, A["Fc"], (0.25, 0.27, 0.24))
    wrap = capsule(P, WRAP_A, WRAP_B, 0.215, 0.215)
    F = smin(smin(smin(sh, up, 0.10), fo, 0.08), fist, 0.07)
    F = smin(F, wrap, 0.03)
    F = smax(F, -P[..., 2], 0.02)                       # flat knuckle contact
    if h < 0.05:
        F = blur(F, 1)
    return G, F, dict(wrap=wrap)


def build_leg(h):
    """Left leg (+X): chunky thigh hidden partly in the hip, calf, big foot with three toes, flat sole."""
    G = Grid((0.0, -0.75, -0.05), (0.95, 0.75, 1.0), h)
    P = G.P
    F = ell(P, (0.42, 0.24, 0.52), (0.27, 0.30, 0.30))
    F = smin(F, ell(P, (0.43, 0.10, 0.30), (0.21, 0.24, 0.24)), 0.10)
    F = smin(F, ell(P, (0.44, -0.10, 0.12), (0.22, 0.34, 0.13)), 0.08)
    for dx in (-0.145, 0.0, 0.145):
        F = smin(F, ell(P, (0.44 + dx, -0.40 - (0.02 if dx == 0 else 0.0), 0.09), (0.075, 0.11, 0.075)), 0.05)
    F = smax(F, -P[..., 2], 0.02)
    return extract(G, F, None, "leg")


TAIL_PTS = [(0.62, 0.70, 0.17), (0.92, 0.74, 0.165), (1.18, 0.92, 0.16), (1.30, 1.20, 0.155), (1.24, 1.48, 0.15),
            (1.06, 1.64, 0.145), (0.90, 1.56, 0.145), (0.88, 1.40, 0.15)]       # (y, z, radius)
TAIL_TIP = (0.0, 0.88, 1.40)


def catmull(pts, n):
    pts = np.asarray(pts, float)
    ext = np.vstack([2 * pts[0] - pts[1], pts, 2 * pts[-1] - pts[-2]])
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(pts[-1])
    return np.array(out)


def build_tail(h):
    """One thick soft tail that curls over at the end; its pivot is the base inside the rump."""
    G = Grid((-0.40, 0.35, 0.40), (0.40, 1.65, 1.95), h)
    P = G.P
    cu = catmull(TAIL_PTS, 8)
    F = np.full(P.shape[:3], 9.0)
    for a, b in zip(cu[:-1], cu[1:]):
        F = np.minimum(F, capsule(P, (0, a[0], a[1]), (0, b[0], b[1]), a[2], b[2]))
    F = smin(F, ell(P, TAIL_TIP, (0.17, 0.17, 0.17)), 0.06)
    return extract(G, F, None, "tail")


def mirror(vf):
    vs, fs = vf
    return vs * np.array((-1.0, 1.0, 1.0)), [tuple(reversed(f)) for f in fs]


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

COOL = np.array((0.80, 0.86, 1.0))
TAU = 2 * math.pi


FUR_DK, FUR, FUR_MD, FUR_LT = rgb(100, 60, 38), rgb(152, 98, 54), rgb(186, 126, 70), rgb(222, 164, 100)
TAN, TAN_SH, TAN_LT, TAN_DK = rgb(240, 198, 152), rgb(212, 156, 116), rgb(252, 228, 194), rgb(150, 96, 70)
BLUSH = rgb(250, 160, 140)
TEAL, TEAL_DK, TEAL_LT = rgb(36, 164, 176), rgb(18, 108, 126), rgb(120, 218, 216)
WHITE, AMBER, AMBER_DK = rgb(247, 245, 238), rgb(255, 196, 66), rgb(206, 122, 34)
EYE_DARK, EYE_IRIS, EYE_LINE, NOSE = rgb(26, 16, 14), rgb(156, 88, 38), rgb(34, 20, 16), rgb(88, 46, 40)
MOUTH, TONGUE = rgb(112, 34, 46), rgb(232, 112, 120)
BOLT = [(0.25, 1.0), (-0.55, 0.0), (-0.05, 0.0), (-0.30, -1.0), (0.60, 0.12), (0.08, 0.12)]


def bands(p, fx, fy, fz, seed, cy=0.0):
    """Broad painterly brush bands: (dark, light) masks from anisotropic noise, three value ranges."""
    az_ = np.arctan2(p[:, 0], -(p[:, 1] - cy))
    q = np.stack([np.cos(az_) * fx, np.sin(az_) * fx, p[:, 2] * fz], 1)
    s_az = vnoise(q, 1.0, seed)
    s3 = vnoise(np.stack([p[:, 0] * fx, (p[:, 1] - cy) * fx, p[:, 2] * fz], 1), 1.0, seed + 3)
    w = sstep(0.12, 0.40, np.hypot(p[:, 0], p[:, 1] - cy))          # no azimuth spokes at the head pole
    s_ = s3 + (s_az - s3) * w
    return 1.0 - sstep(0.38, 0.46, s_), sstep(0.60, 0.68, s_)


def sample(part, name, p):
    G, fl = FUSED[part]
    return G.sample(fl[name], p)


def in_poly(x, y, pts):
    inside = np.zeros(len(x), bool)
    k = len(pts)
    for i in range(k):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % k]
        cond = (y1 > y) != (y2 > y)
        xin = (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1
        inside ^= cond & (x < xin)
    return inside


def fur(p, n, seed, zr, cy=0.0, fx=3.0, fz=1.4):
    """Warm brown fur in three-four value ranges: dark base low, mid on top, brush strokes dark and light."""
    nz = vnoise(p * np.array((1.0, 1.0, 0.4)), 8.0, seed)
    c = mix(FUR_DK, FUR, sstep(zr[0], zr[1], p[:, 2]))
    c = mix(c, FUR_MD, 0.45 * sstep(-0.1, 0.9, n[:, 2]) * sstep(zr[0] + 0.3, zr[1], p[:, 2]))
    c = mix(c, FUR_MD, 0.10 * (nz - 0.5) * 2 + 0.04)
    sd_, sl_ = bands(p, fx, 0, fz, seed + 10, cy)
    c = mix(c, FUR_DK, 0.50 * sd_)
    c = mix(c, FUR_LT, 0.42 * sl_ * sstep(-0.3, 0.6, n[:, 2]))
    c = mix(c, rgb(150, 70, 52), 0.16 * sstep(0.45, 0.10, p[:, 2]))          # warm bounce low down
    big = vnoise(p, 1.7, seed + 5)                                              # broad warm patches
    c = mix(c, rgb(214, 128, 62), 0.34 * sstep(0.54, 0.70, big))
    c = mix(c, FUR_DK, 0.26 * sstep(0.36, 0.22, big))
    return c


def paint_body(p, n):
    X, Y, Z = p[:, 0], p[:, 1], p[:, 2]
    c = fur(p, n, 1, (0.2, 1.7), 0.0, 3.0, 1.2)
    nz2 = vnoise(p, 3.0, 2)
    bm = (X / 0.40) ** 2 + ((Z - 0.86) / 0.52) ** 2 + 0.14 * (nz2 - 0.5)
    belly = sstep(1.1, 0.85, bm) * sstep(0.0, -0.3, n[:, 1])
    tan = mix(TAN_SH, TAN, sstep(0.3, 1.0, Z))
    cd_, cl_ = bands(p, 0.8, 0, 5.0, 12)
    tan = mix(mix(tan, TAN_SH, 0.35 * cd_), TAN_LT, 0.35 * cl_)
    c = mix(c, tan, belly)
    return c, np.zeros(len(p), bool)


def paint_head(p, n, eyes_out):
    X, Y, Z = p[:, 0], p[:, 1], p[:, 2]
    nz2 = vnoise(p, 3.0, 4)
    c = fur(p, n, 3, (1.0, 2.4), -0.28, 3.0, 1.6)
    hard = np.zeros(len(p), bool)
    # heart-shaped tan face mask: two lobes round the eyes, running down into the muzzle
    e1 = ((X - 0.29) / 0.34) ** 2 + ((Z - 1.75) / 0.29) ** 2
    e2 = ((X + 0.29) / 0.34) ** 2 + ((Z - 1.75) / 0.29) ** 2
    e3 = (X / 0.40) ** 2 + ((Z - 1.44) / 0.30) ** 2
    mk = np.minimum(np.minimum(e1, e2), e3) + 0.08 * (nz2 - 0.5)
    face = sstep(1.10, 0.90, mk) * sstep(-0.50, -0.72, Y)
    tan = mix(TAN_SH, TAN, sstep(1.3, 1.9, Z))
    dm = sample("head", "muz", p)
    tan = mix(tan, TAN_LT, 0.65 * sstep(0.06, -0.02, dm))
    for s in (1, -1):                                                         # soft cheek blush
        bd = np.sqrt(((X - s * 0.47) / 0.13) ** 2 + ((Z - 1.52) / 0.085) ** 2)
        tan = mix(tan, BLUSH, 0.45 * sstep(1.0, 0.25, bd) * (Y < -0.45))
    c = mix(c, tan, face)
    hard |= face > 0.5
    # round ears with tan inner
    for s in (1, -1):
        ax = np.array((s * 0.85, -0.5, 0.0))
        ax /= np.linalg.norm(ax)
        d3 = p - np.array((s * 0.84, -0.10, 1.55))
        along = d3 @ ax
        inpl = np.linalg.norm(d3 - along[:, None] * ax, axis=1) / 0.30
        inner = sstep(1.0, 0.78, inpl) * sstep(0.35, 0.7, n @ ax) * (along > 0.05)
        ear = mix(TAN, rgb(224, 142, 118), 0.55 * sstep(0.7, 0.0, inpl))
        c = mix(c, ear, inner)
    # eyes: big glossy painted eyes over shallow relief
    for name in ("eyeL", "eyeR"):
        e = FACE[name]
        d = p - e["c"]
        eu, ev = (d @ e["u"]) / e["r"][0], (d @ e["v"]) / e["r"][1]
        front = (np.abs(d @ e["n"]) < 0.07) & (n @ e["n"] > 0.45)
        r = np.sqrt(eu * eu + ev * ev)
        ring = front & (r >= 1.0) & (r < 1.55)
        c[ring] = mix(c[ring], c[ring] * np.array((0.92, 0.84, 0.82)), (0.20 * sstep(1.55, 1.0, r))[ring])
        line = front & (r >= 0.97) & (r < 1.17)
        c[line] = mix(c[line], EYE_LINE, sstep(1.17, 1.06, r)[line])
        brow = front & (r >= 1.28) & (r < 1.62) & (ev > 0.30)
        bw = sstep(1.62, 1.45, r) * sstep(1.28, 1.40, r) * sstep(0.30, 0.70, ev)
        c[brow] = mix(c[brow], FUR_DK, (0.85 * bw)[brow])
        inside = front & (r < 1.0)
        ce = np.tile(EYE_DARK, (len(p), 1))
        iris = sstep(0.25, 0.85, r) * sstep(0.3, -0.75, ev)
        ce = mix(ce, EYE_IRIS, 0.85 * iris)
        ce = mix(ce, EYE_IRIS * 1.5, 0.50 * sstep(-0.40, -0.80, ev) * sstep(0.30, 0.8, r))
        c[inside] = ce[inside]
        eyes_out.append((inside, eu, ev))
        hard |= front & (r < 1.6)
    # nose and big grin on the muzzle
    fr = (n[:, 1] < -0.15) & (Y < -0.82)
    nd = ((X / 0.105) ** 2 + ((Z - 1.585) / 0.062) ** 2)
    nm = fr & (nd < 1.0) & (Z > 1.52)
    c[nm] = mix(c[nm], NOSE, sstep(1.0, 0.6, nd)[nm])
    s_ = np.clip(1.0 - (X / 0.26) ** 2, 0.0, 1.0)
    zu = 1.475 - 0.065 * s_
    zl = zu - 0.115 * np.sqrt(s_)
    inm = fr & (np.abs(X) < 0.26) & (Z < zu) & (Z > zl)
    mc = np.tile(MOUTH, (len(p), 1))
    mc = mix(mc, TONGUE, sstep(zl + 0.05 * np.sqrt(s_), zl + 0.015, Z))
    mc = mix(mc, WHITE, sstep(zu - 0.032, zu - 0.020, Z))
    c[inm] = mc[inm]
    outl = fr & (np.abs(X) < 0.275) & (np.minimum(np.abs(Z - zu), np.abs(Z - zl)) < 0.013) & ((Z <= zu + 0.013) & (Z >= zl - 0.013))
    c[outl] = TAN_DK * 0.55
    hard |= inm | outl | nm
    # sweatband: teal with white edge lines, a painted lightning bolt at the front, darker knot and ends
    db = sample("head", "band", p)
    bm_ = sstep(0.026, -0.008, db)
    dz = Z - zs_band(Y)
    bc = mix(TEAL_DK, TEAL, sstep(-0.12, 0.10, dz / 0.14 * 0.5 + 0.35 * n[:, 2] + 0.35))
    bc = mix(bc, TEAL_LT, 0.30 * sstep(0.2, 0.9, n[:, 2]))
    ew = sstep(0.016, 0.004, np.abs(np.abs(dz) - 0.090)) * sstep(0.04, 0.02, np.abs(dz) - 0.082 + 0.0)
    ew = sstep(0.016, 0.005, np.abs(np.abs(dz) - 0.118))
    frontb = (Y < -0.45) & (n[:, 1] < -0.1)
    ew = ew * (1.0 - frontb * sstep(0.20, 0.14, np.abs(X)))
    bc = mix(bc, WHITE, 0.92 * ew)
    knot = (Y > 0.30)
    bc = mix(bc, TEAL_DK, 0.40 * knot)
    bs = 0.115
    bu, bv = X / bs, dz / bs
    ol = in_poly(bu * 0.88, bv * 0.88, BOLT)
    bl = in_poly(bu, bv, BOLT)
    bz = frontb & (np.abs(X) < 0.20)
    bc[bz & ol] = WHITE
    bc[bz & bl] = mix(AMBER, AMBER_DK, 0.55 * sstep(0.2, -0.6, bv))[bz & bl]
    c = mix(c, bc, bm_)
    hard |= bm_ > 0.5
    return c, hard


def paint_arm(p, n, s):
    Pm, nm = p * np.array((s, 1.0, 1.0)), n * np.array((s, 1.0, 1.0))
    X, Y, Z = Pm[:, 0], Pm[:, 1], Pm[:, 2]
    c = fur(Pm, nm, 5, (0.0, 1.3), 0.0, 2.5, 2.0)
    Fc = np.array(ARM_PTS["Fc"])
    dist = np.linalg.norm(Pm - Fc, axis=1)
    front = sstep(-0.05, -0.45, nm[:, 1]) * sstep(0.36, 0.27, dist)
    tan = mix(TAN_SH, TAN, sstep(0.0, 0.4, Z))
    c = mix(c, tan, front)
    back = sstep(0.34, 0.26, dist) * np.maximum(sstep(0.2, 0.5, nm[:, 2]), sstep(0.1, 0.5, nm[:, 1])) * (1 - front)
    c = mix(c, mix(FUR_LT, TAN, 0.65), 0.85 * back)                           # light fur on the back of the hands
    for k in (-1, 1):                                                         # finger grooves
        gx = np.abs(X - (0.78 + k * 0.085))
        gr = sstep(0.016, 0.006, gx) * front * sstep(0.06, 0.12, Z) * sstep(0.46, 0.38, Z)
        c = mix(c, TAN_DK, 0.75 * gr)
    wr = sstep(0.026, -0.008, sample("arm", "wrap", Pm)) * sstep(0.54, 0.575, Z)
    wc = mix(TEAL_DK, TEAL, sstep(-0.3, 0.7, nm[:, 2] + 0.4))
    wc = mix(wc, WHITE, 0.92 * sstep(0.020, 0.008, np.abs(Z - 0.655)))
    c = mix(c, wc, wr)
    return c, (wr > 0.5) | (front > 0.5)


def paint_leg(p, n, s):
    Pm, nm = p * np.array((s, 1.0, 1.0)), n * np.array((s, 1.0, 1.0))
    X, Y, Z = Pm[:, 0], Pm[:, 1], Pm[:, 2]
    c = fur(Pm, nm, 7, (0.0, 0.9), 0.0, 2.5, 2.2)
    sole = np.maximum(sstep(-0.15, -0.32, Y) * sstep(0.30, 0.18, Z), sstep(-0.3, -0.7, nm[:, 2]) * sstep(0.30, 0.18, Z))
    tan = mix(TAN_SH, TAN, sstep(0.0, 0.2, Z))
    c = mix(c, tan, sole)
    heel = sstep(0.1, 0.5, nm[:, 1]) * sstep(0.34, 0.2, Z) * (1 - sole)
    c = mix(c, mix(FUR_LT, TAN, 0.55), 0.8 * heel)                            # light heels
    for k in (-1, 1):
        gx = np.abs(X - (0.44 + k * 0.0725))
        c = mix(c, TAN_DK, 0.7 * sstep(0.014, 0.005, gx) * sstep(-0.30, -0.36, Y) * sstep(0.05, 0.10, Z))
    return c, sole > 0.5


def paint_tail(p, n):
    c = fur(p, n, 9, (0.5, 1.8), 0.0, 2.5, 2.0)
    tip = sstep(0.56, 0.30, np.linalg.norm(p - np.array(TAIL_TIP), axis=1))
    c = mix(c, mix(FUR_LT, TAN, 0.75), 0.95 * tip)
    return c, np.zeros(len(p), bool)


def paint_all(P, Ns, part):
    col = np.zeros((len(P), 3))
    hard = np.zeros(len(P), bool)
    eyes = []
    for pid in range(1, 8):
        m = part == pid
        if not m.any():
            continue
        p, n = P[m], Ns[m]
        ex = []
        if pid == P_BODY:
            c, h = paint_body(p, n)
        elif pid == P_HEAD:
            c, h = paint_head(p, n, ex)
        elif pid in (P_ARML, P_ARMR):
            c, h = paint_arm(p, n, 1 if pid == P_ARML else -1)
        elif pid in (P_LEGL, P_LEGR):
            c, h = paint_leg(p, n, 1 if pid == P_LEGL else -1)
        else:
            c, h = paint_tail(p, n)
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
    k = np.clip(ks + np.where(hard, 1.2, 1.5) * (kf - ks), 0.0, 1.0)      # visible soft faceting
    sky = 0.5 + 0.5 * Ns[:, 2]
    Lf = np.array((0.30, 0.80, 0.40))
    Lf /= np.linalg.norm(Lf)
    lightv = 0.60 + 0.42 * k + 0.12 * sky + 0.22 * np.clip(Ns @ Lf, 0, 1)   # warm fill from behind so the back reads
    head = part_ids == P_HEAD
    ao_w = np.where(head, 0.20, 0.32)
    aol_w = np.where(head, 0.08, 0.18)
    aof = (1.0 - ao_w + ao_w * sstep(0.12, 1.0, ao_s)) * (1.0 - aol_w * (1.0 - sstep(0.2, 1.0, ao_l)))
    shade = lightv * aof * (0.90 + 0.12 * sstep(0.0, 2.3, P[:, 2]))
    lit = col * shade[:, None]
    lit = mix(lit, np.clip(lit * np.array((1.05, 0.97, 0.88)), 0, 1), 0.5 * sstep(1.0, 0.8, shade) * sstep(0.55, 0.75, shade))
    lit = mix(lit, lit * COOL, 0.80 * sstep(0.78, 0.50, shade))
    lit = lit + (sstep(0.3, 1.0, Ns @ Lr) * 0.10)[:, None] * np.array((0.55, 0.70, 1.0))
    hl = np.clip(col * 1.15 + 0.10, 0, 1) * np.array((1.0, 0.96, 0.88))
    lit = mix(lit, hl, 0.25 * edge * hard * sstep(-0.3, 0.5, Ns @ Lk))
    return np.clip(lit, 0, 1)


def catchlights(col, eyes):
    for inside, eu, ev in eyes:
        g1 = np.sqrt(((eu + 0.30) / 0.36) ** 2 + ((ev - 0.38) / 0.32) ** 2)
        g2 = np.sqrt(((eu - 0.38) / 0.15) ** 2 + ((ev + 0.28) / 0.14) ** 2)
        m1, m2 = inside & (g1 < 1.0), inside & (g2 < 1.0)
        col[m1] = mix(col[m1], np.array((1.0, 1.0, 1.0)), sstep(1.0, 0.8, g1)[m1])
        col[m2] = mix(col[m2], np.array((1.0, 0.98, 0.94)), sstep(1.0, 0.75, g2)[m2])
    return col


def world_bounds_early(o):
    ws = [o.matrix_world @ vv.co for vv in o.data.vertices]
    return ([min(w[k] for w in ws) for k in range(3)], [max(w[k] for w in ws) for k in range(3)])


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
mat = bpy.data.materials.new("Monkey_Atlas")
mat.use_nodes = True


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


Gf, Ff, fl_ = head_field(HF_HEAD, True)
FUSED["head"] = (Gf, fl_)
Gf, Ff, fl_ = arm_field(HF_ARM)
FUSED["arm"] = (Gf, fl_)
del Gf, Ff, fl_
Gc, Fc, _ = body_field(H_BODY)
body_vf = extract(Gc, Fc, None, "body")
Gc, Fc, _ = head_field(H_HEAD, False)
head_vf = extract(Gc, Fc, None, "head")
Gc, Fc, _ = arm_field(H_ARM)
arm_l = extract(Gc, Fc, None, "arm")
leg_l = build_leg(H_LEG)
tail_vf = build_tail(H_TAIL)
specs = [("Monkey_Body", P_BODY, body_vf), ("Monkey_Head", P_HEAD, head_vf),
         ("Monkey_ArmL", P_ARML, arm_l), ("Monkey_ArmR", P_ARMR, mirror(arm_l)),
         ("Monkey_LegL", P_LEGL, leg_l), ("Monkey_LegR", P_LEGR, mirror(leg_l)),
         ("Monkey_Tail", P_TAIL, tail_vf)]
objs = [make_object(n, pid, vf, mat) for n, pid, vf in specs]
parts = {o.name: o for o in objs}
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
    # look-dev: per-vertex painted colours, no bake
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
    head_obj = parts["Monkey_Head"]
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
        if not (nrm.dot(radial) > 0.35 and nrm.y < -0.1 and abs(ang) < 1.25 and 1.15 < c.z < 2.40):
            continue
        if htree.ray_cast(c + nrm * 0.002, nrm, 1.0)[0] is not None:
            continue
        n_face += 1
        for li in poly.loop_indices:
            co = mw @ hm.vertices[hm.loops[li].vertex_index].co
            a2 = math.atan2(co.x - FACE_AXIS[0], -(co.y - FACE_AXIS[1]))
            uvl[li].uv = (a2 * 0.55 * base_ratio * FACE_DENSITY + 5.0, co.z * base_ratio * FACE_DENSITY)
    hbm.free()
    select_only(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, margin=0.008)
    bpy.ops.object.mode_set(mode="OBJECT")
    for o in objs:
        o.data.uv_layers.active.name = "UVMap"
    deg = 0
    for o in objs:
        uvd = o.data.uv_layers.active.data
        for poly in o.data.polygons:
            uu = [uvd[li].uv for li in poly.loop_indices]
            if abs((uu[1] - uu[0]).cross(uu[2] - uu[0])) < 1e-9:
                deg += 1
    log("unwrapped; base texel ratio", round(base_ratio, 4), "face-island faces", n_face, "| degenerate UV tris", deg)

    # ---- bake data maps ---------------------------------------------------------------------------
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
            enc(geo.outputs["Position"], 0.125)
        elif kind == "nrm":
            enc(geo.outputs["Normal"], 0.5)
        elif kind == "fnrm":
            enc(attr("fnrm", "Vector"), 0.5)
        elif kind == "bev":
            b = N_("ShaderNodeBevel")
            b.samples = 16
            b.inputs["Radius"].default_value = 0.02
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
            a1.inputs["Distance"].default_value = 0.14
            a2 = N_("ShaderNodeAmbientOcclusion")
            a2.samples = 16
            a2.inputs["Distance"].default_value = 0.7
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

    P = dec(maps["pos"], 0.125)
    Ns, Nf, Nb = unit(dec(maps["nrm"], 0.5)), unit(dec(maps["fnrm"], 0.5)), unit(dec(maps["bev"], 0.5))
    pf = maps["attr"][idx, 0].astype(np.float64) * 16.0
    part = np.rint(pf).astype(np.int64)
    # guard: a blended / stray part id would paint another part's colours (seen as speckles). Flag
    # texels whose id is fractional or whose position is outside that part's box, then re-assign them
    # to the nearest part surface.
    bbs = {}
    trees = {}
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
    log("suspicious part ids:", int(sus.sum()), "of", len(P), "| fractional", int((np.abs(pf - part) > 0.04).sum()),
        "| outside box", int((~inside_box).sum()))
    for i in np.nonzero(sus)[0]:
        best, bd = part[i], 1e9
        for pid_, tr_ in trees.items():
            loc_, _, _, dist_ = tr_.find_nearest(Vector(P[i]))
            if loc_ is not None and dist_ < bd:
                best, bd = pid_, dist_
        part[i] = best
    oc = maps["occ"][idx, :3].astype(np.float64)
    ao_s, ao_l, curv = np.clip(oc[:, 0], 0, 1), np.clip(oc[:, 1], 0, 1), oc[:, 2]
    del maps
    edge = sstep(0.995, 0.93, np.sum(Nb * Ns, axis=1)) * sstep(0.49, 0.53, curv)

    colour, hard, eyes = paint_all(P, Ns, part)
    rows = []
    for pid in range(1, 8):
        m_ = part == pid
        if m_.sum() > 200:
            rows.append((round(float(np.median(ao_s[m_])), 3), pid, int(m_.sum())))
    log("median AO per part (ao, part, texels):", sorted(rows))
    colour = light(colour, P, Ns, Nf, hard, ao_s, ao_l, edge, part)
    colour = catchlights(colour, eyes)

    full = np.zeros((BAKE * BAKE, 4), np.float32)
    full[idx, :3] = colour
    full[:, 3] = 1.0
    full[~cov, :3] = FUR_DK
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
JOINT_PARENT = {"Monkey_Body": None, "Monkey_Head": "Monkey_Body", "Monkey_ArmL": "Monkey_Body",
                "Monkey_ArmR": "Monkey_Body", "Monkey_LegL": "Monkey_Body", "Monkey_LegR": "Monkey_Body",
                "Monkey_Tail": "Monkey_Body"}
JOINT_NAME = {"Monkey_Body": "root (belly centre)", "Monkey_Head": "neck, hidden under the chin and chest",
              "Monkey_ArmL": "shoulder", "Monkey_ArmR": "shoulder", "Monkey_LegL": "hip", "Monkey_LegR": "hip",
              "Monkey_Tail": "tail base, inside the rump"}
MOTION = {
    "Monkey_Body": "root part: bob in Studio Y, lean (pitch about Studio X) and a little roll about Studio Z for the scamper; tips back for the hype pose",
    "Monkey_Head": "nod = pitch about Studio X, tilt = roll about Studio Z, look = yaw about Studio Y, through the neck joint",
    "Monkey_ArmL": "swing about Studio X (side-to-side axis) through the shoulder; reach forward = positive Studio X angle; raise out = Studio Z",
    "Monkey_ArmR": "swing about Studio X through the shoulder; reach forward = positive Studio X angle; raise out = Studio Z (mirrored sign)",
    "Monkey_LegL": "swing about Studio X through the hip; foot forward = positive Studio X angle",
    "Monkey_LegR": "swing about Studio X through the hip; foot forward = positive Studio X angle",
    "Monkey_Tail": "curl / bounce = pitch about Studio X through the base, wave = yaw about Studio Y",
}

# Pose dictionaries in Blender-bone degrees (X pitch, Y yaw about world Z, Z roll about world -Y); also exported
# as Studio angles (Studio = (-x, y, -z) of these, right-hand rule about Studio X / Y / Z).
SCAMPER_A = {"Body": (7, 0, 5), "Head": (-7, 0, -5), "ArmL": (-40, 0, 0), "ArmR": (26, 0, 0), "LegL": (30, 0, 0),
             "LegR": (-28, 0, 0), "Tail": (-14, 0, 8)}
SCAMPER_B = {"Body": (-3, 0, -5), "Head": (3, 0, 5), "ArmL": (26, 0, 0), "ArmR": (-40, 0, 0), "LegL": (-28, 0, 0),
             "LegR": (30, 0, 0), "Tail": (12, 0, -8)}
HYPE = {"Body": (-20, 0, 0), "Head": (14, 0, 0), "ArmL": (-122, 0, -26), "ArmR": (-122, 0, 26), "LegL": (18, 0, 0),
        "LegR": (18, 0, 0), "Tail": (-10, 0, 0)}
HEAD_TURN = {"Head": (6, 30, 18)}
TAIL_CURL = {"Tail": (30, 24, 0), "Body": (2, 0, 0)}


def studio_angles(d):
    return {"Monkey_" + k: [round(-v[0], 1) + 0.0, round(v[1], 1) + 0.0, round(-v[2], 1) + 0.0] for k, v in d.items()}


def studio(v):
    return [round(-v[0], 4) + 0.0, round(v[2], 4) + 0.0, round(v[1], 4) + 0.0]


def studio_size(v):
    return [round(v[0], 4), round(v[2], 4), round(v[1], 4)]


def world_bounds(o):
    ws = [o.matrix_world @ vv.co for vv in o.data.vertices]
    return (Vector([min(w[k] for w in ws) for k in range(3)]), Vector([max(w[k] for w in ws) for k in range(3)]))


report = {"asset": STEM, "blender_version": bpy.app.version_string,
          "authoring": "final Roblox stud size (1 Blender unit = 1 stud); import at 1:1, do not scale",
          "axes": "Blender Z-up, front -Y, the monkey's left +X; feet on z = 0",
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
body_pivot = parts["Monkey_Body"].location.copy()
install = {
    "asset": STEM, "rarity": "Rare", "strong_suit": "Attack speed (a plain +attack speed stat)",
    "axis": "studio = (-x, z, y) of blender; Blender front -Y = Studio front -Z",
    "units": "studs; the model is at final size, import 1:1 and do not scale",
    "sides": "L/R are the monkey's own left/right; its left is Blender +X = Studio -X",
    "origin": "all positions are relative to the model origin = the ground point under the body pivot (Blender world origin)",
    "ground_point": studio((0.0, 0.0, 0.0)), "overall_size": studio_size(size),
    "overall_center": studio((lo_all + hi_all) / 2), "texture": f"textures/{TEX_PATH.name}",
    "texture_note": "one shared atlas; every MeshPart uses the same TextureID via MeshPart.TextureID (Rare: one small painted accent, no Neon, no glow)",
    "rare_accent": "painted amber lightning bolt on the teal sweatband (texture only, no glow)",
    "role_props": "teal sweatband with white edge lines and a short tied knot (fused into the head part); teal wrist wraps with a white stripe on both wrists (fused into the arm parts)",
    "natural_stance": "the rest pose in the mesh IS the natural stance: a knuckle-walking crouch on all fours, fists on the ground",
    "rest_rotation": "every part has identity rotation relative to the model at rest",
    "rig": "one Motor6D per part: Part0 = joint_parent, Part1 = the part, C0/C1 placed at the part's pivot",
    "parts": {}}
for name, o in parts.items():
    lo, hi = world_bounds(o)
    install["parts"][name] = {
        "center": studio((lo + hi) / 2), "size": studio_size(hi - lo), "pivot": studio(o.location),
        "pivot_from_body_pivot": studio(o.location - body_pivot), "pivot_is": JOINT_NAME[name],
        "joint_parent": JOINT_PARENT[name], "suggested_motion": MOTION[name]}
install["locomotion"] = "scamper"
install["locomotion_data"] = {
    "gait": "scamper: a bouncy knuckle-walk on all fours in a diagonal gait (left arm with right leg), body bobbing "
            "up at mid-step, tail counter-swinging; a hop-bounce when it speeds up",
    "angle_convention": "degrees, rotation of the part about its own pivot in Studio axes (right-hand rule, Roblox "
                        "CFrame.Angles); 'blender_bone_deg' are the values used in the Blender preview armature "
                        "(X pitch, Y yaw about world Z, Z roll about world -Y). Studio = (-x, y, -z) of the bone angles.",
    "scamper": {
        "step_period_s": 0.36,
        "body_bob_studs": 0.07,
        "frame_A": {"blender_bone_deg": SCAMPER_A, "studio_deg": studio_angles(SCAMPER_A)},
        "frame_B": {"blender_bone_deg": SCAMPER_B, "studio_deg": studio_angles(SCAMPER_B)},
        "note": "alternate A and B (ease in/out); arms reach forward = negative Blender X / positive Studio X, legs "
                "swing the opposite way to the arm on their diagonal; add +0.07 stud Studio Y bob at mid-step",
    },
    "hype_pose": {
        "note": "celebrate / buff-ready: stands up on its hind legs, chest out, both fists pumped up beside the head",
        "blender_bone_deg": HYPE, "studio_deg": studio_angles(HYPE),
    },
    "head_turn": {"blender_bone_deg": HEAD_TURN, "studio_deg": studio_angles(HEAD_TURN),
                  "note": "look around / tilt: yaw 30 and roll 18 through the neck joint"},
    "tail_curl": {"blender_bone_deg": TAIL_CURL, "studio_deg": studio_angles(TAIL_CURL),
                  "note": "tail pitched forward over the back with a sideways wave; use as the idle tail wag amplitude"},
}
log("overall (w, len, h)", tuple(round(v, 3) for v in (size.x, size.y, size.z)), "tris", report["total_triangles"])

if not QUICK:
    (ROOT / "polygon-report.json").write_text(json.dumps(report, indent=2))
    (ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=2))
    select_only(objs, parts["Monkey_Body"])
    bpy.ops.export_scene.gltf(filepath=str(GLB_PATH), export_format="GLB", use_selection=True, export_apply=True)
    select_only(objs, parts["Monkey_Body"])
    bpy.ops.export_scene.fbx(filepath=str(FBX_PATH), use_selection=True, object_types={"MESH"},
                             axis_forward="-Z", axis_up="Y", path_mode="COPY", embed_textures=True,
                             add_leaf_bones=False)
    log("exported", FBX_PATH.name, GLB_PATH.name)

# =============================================================================================
# armature (Blender only, for posing previews; exports are the plain rigid parts)
# =============================================================================================
arm_data = bpy.data.armatures.new("Monkey_Rig")
arm = bpy.data.objects.new("Monkey_Rig", arm_data)
scene.collection.objects.link(arm)
select_only([arm])
bpy.ops.object.mode_set(mode="EDIT")
ebs = {}
for name, o in parts.items():
    eb = arm_data.edit_bones.new(name.replace("Monkey_", ""))
    eb.head = o.location
    eb.tail = o.location + Vector((0, 0, 0.25))
    eb.roll = 0.0
    ebs[name] = eb
for name, par in JOINT_PARENT.items():
    if par:
        ebs[name].parent = ebs[par]
bpy.ops.object.mode_set(mode="OBJECT")
for name, o in parts.items():
    mwo = o.matrix_world.copy()
    o.parent = arm
    o.parent_type = "BONE"
    o.parent_bone = name.replace("Monkey_", "")
    bpy.context.view_layer.update()
    o.matrix_world = mwo
bpy.context.view_layer.update()
log("armature built; max pivot drift", round(max((parts[n].matrix_world.translation - PIVOT[n]).length for n in parts), 6))


def pose(rots):
    """rots: {bone: (x, y, z) degrees}. Bone axes: X = world X (pitch / swing), Y = world Z (yaw),
    Z = world -Y (roll about the front-back axis)."""
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = [math.radians(v) for v in rots.get(pb.name, (0, 0, 0))]
    bpy.context.view_layer.update()


if not QUICK:
    for im in bpy.data.images:
        if im.source == "FILE":
            im.pack()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), relative_remap=True)
    log("saved", BLEND_PATH.name)

# =============================================================================================
# previews (Eevee)
# =============================================================================================
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
fm = bpy.data.materials.new("Preview_Floor")
fm.use_nodes = True
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.36, 0.40, 0.46, 1)
fm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
floor.data.materials.append(fm)
cam = bpy.data.objects.new("PreviewCam", bpy.data.cameras.new("PreviewCam"))
scene.collection.objects.link(cam)
scene.camera = cam


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



tgt = V(0, 0.15, 1.15)
ft = V(0, -0.75, 1.65)
DIST = 10.5
POSES = [
    ("Scamper A: left arm + right leg reach forward", SCAMPER_A, around(tgt, (-1, -0.3, 0.1), DIST), tgt),
    ("Scamper B: opposite diagonal", SCAMPER_B, around(tgt, (1, -0.3, 0.1), DIST), tgt),
    ("Scamper A from the front 3/4", SCAMPER_A, around(tgt, (-0.6, -1, 0.2), DIST), tgt),
    ("Hype pose: upright on hind legs, fists pumped", HYPE, around(V(0, 0.1, 1.25), (-0.35, -1, 0.15), DIST), V(0, 0.1, 1.25)),
    ("Head turn 30 + tilt 18", HEAD_TURN, around(ft, (0.35, -1, 0.15), 7.0), ft),
    ("Tail curl: pitched forward + wave", TAIL_CURL, around(V(0, 0.9, 1.2), (-1, 0.45, 0.15), DIST), V(0, 0.9, 1.2)),
]

if not NO_PREVIEWS and QUICK:
    shoot(OUT / "threeq.png", around(tgt, (-0.75, -0.9, 0.35), DIST), tgt)
    shoot(OUT / "face-closeup.png", around(ft, (-0.3, -1, 0.12), 4.5), ft)
    shoot(OUT / "side.png", around(tgt, (-1, 0, 0.1), DIST), tgt)
    shoot(OUT / "back.png", around(tgt, (0.3, 1, 0.3), DIST), tgt, res=(800, 800))
    if "--pose" in ARGS:
        pose_items = []
        for i, (lab, rots, loc, t) in enumerate(POSES):
            pose(rots)
            pose_items.append((shoot(OUT / f"_pose-{i}.png", loc, t, res=(700, 700)), lab))
        pose({})
        make_sheet(pose_items, 3, 400, OUT / "pose-quick.png", "Monkey pose check (quick)")
        for pth, _ in pose_items:
            pth.unlink()
elif not NO_PREVIEWS:
    shots = [(shoot(OUT / "threeq.png", around(tgt, (-0.75, -0.9, 0.35), DIST), tgt), "Three-quarter (natural stance)"),
             (shoot(OUT / "front.png", around(tgt, (0, -1, 0.1), DIST), tgt), "Front"),
             (shoot(OUT / "side.png", around(tgt, (-1, 0, 0.1), DIST), tgt), "Side (monkey's right)"),
             (shoot(OUT / "back.png", around(tgt, (0.3, 1, 0.3), DIST), tgt), "Back (tail and headband knot)")]
    face = shoot(OUT / "face-closeup.png", around(ft, (-0.3, -1, 0.12), 4.5), ft, res=(1400, 1400))
    pose_items = []
    for i, (lab, rots, loc, t) in enumerate(POSES):
        pose(rots)
        pose_items.append((shoot(OUT / f"_pose-{i}.png", loc, t, res=(900, 900)), lab))
    pose({})
    make_sheet(pose_items, 3, 450, OUT / "pose-check.png", "Monkey: pose check through the joint pivots",
               "Each part rotates about its own pivot (Blender armature, preview only). Look for gaps at the shoulders, hips, neck and tail base.")
    for pth, _ in pose_items:
        pth.unlink()
    make_sheet(shots + [(face, "Face close-up"), (OUT / "pose-check.png", "Pose check (scamper, hype, head turn, tail curl)")],
               3, 520, OUT / "sheet.png",
               f"Monkey pet (Rare, attack speed): {report['total_triangles']:,} tris, one 1024 atlas",
               "Blender 5.2 Eevee renders. Blender-verified, Studio untested.")
log("done")
