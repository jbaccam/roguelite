"""Turtle pet (Rare, strong suit: team defense) for the roguelite.

Self-contained generator for background Blender 5.2 (no code imported from other kits).

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 \
        --python build_turtle.py
    ... -- --shape                 fast look-dev: per-vertex painted colours, no bake, one shape sheet
    ... -- --quick --out <dir>     1024 bake, a few renders, no exports
    ... -- --no-previews           exports + reports only

Coordinates: Blender Z-up, 1 unit = 1 stud (final size, import 1:1), feet on z = 0, the turtle faces
-Y and its own left is +X. Studio = (-x, z, y) of Blender.

Method (same family as the approved Golden Retriever / Penguin): every rigid part is ONE surface made
from analytic signed-distance volumes joined with smooth unions (real fillets), meshed on a COARSE
lattice so the facets are broad and even like cut gemstone planes (flat shading). Colour is painted by
3D position (continuous over every join and UV seam) and baked to one 1024 atlas with icon-style
lighting (per-facet key, AO, warm shadow, cool rim).
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
STEM = "turtle"
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
    print(f"[turtle {time.time() - T0:6.1f}s]", *a, flush=True)





P_BODY, P_HEAD, P_FLF, P_FRF, P_FLB, P_FRB, P_TAIL = range(1, 8)

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


def bands(p, fx, fy, fz, seed, cy=0.0):
    """Broad painterly brush bands: (dark, light) masks from anisotropic noise, three value ranges."""
    # strokes follow the form: narrow around the vertical axis, long from top to bottom (feather flow);
    # fx scales the cells around the axis, fz the cells along z
    az_ = np.arctan2(p[:, 0], -(p[:, 1] - cy))
    q = np.stack([np.cos(az_) * fx, np.sin(az_) * fx, p[:, 2] * fz], 1)
    s_ = vnoise(q, 1.0, seed)
    return 1.0 - sstep(0.38, 0.46, s_), sstep(0.60, 0.68, s_)


def sample(part, name, p):
    G, fl = FUSED[part]
    return G.sample(fl[name], p)




# =============================================================================================
# the seven parts (Blender axes, studs). Turtle left = +X.
# =============================================================================================
FUSED = {}         # part -> (grid, named fields) for the painter's masks
FACE = {}          # eye / emblem frames for the painter
PIVOT = {
    "Turtle_Body": V(0.0, 0.12, 0.80),
    "Turtle_Head": V(0.0, -0.80, 0.95),
    "Turtle_LegFL": V(0.72, -0.36, 0.80),
    "Turtle_LegFR": V(-0.72, -0.36, 0.80),
    "Turtle_LegBL": V(0.72, 0.66, 0.80),
    "Turtle_LegBR": V(-0.72, 0.66, 0.80),
    "Turtle_Tail": V(0.0, 0.96, 0.62),
}
SHELL_C, SHELL_R = (0.0, 0.12, 0.95), (1.0, 0.82, 1.12)
RIM_Z, RIM_N, RIM_K, RIM_T = 0.76, 2.3, 1.05, 0.19
HEAD_C, HEAD_R = (0.0, -1.38, 1.05), (0.86, 0.76, 0.72)
HELM_C = (0.0, -1.36, 1.50)
LEG_X, LEG_YF, LEG_YB = 0.72, -0.36, 0.66
H_FINE_BODY, H_FINE_HEAD = 0.026, 0.021              # fine lattices only drive the painter's masks
H_BODY, H_HEAD, H_LEG, H_TAIL = 0.15, 0.12, 0.12, 0.10   # coarse lattices ARE the mesh: broad, even facets


def rim_rho(X, Y):
    return ((np.abs(X) / SHELL_R[0]) ** RIM_N + (np.abs(Y - SHELL_C[1]) / SHELL_R[1]) ** RIM_N) ** (1.0 / RIM_N)


def body_field(h):
    """Tall domed shell + thick shield-crest rim + plastron, one surface."""
    G = Grid((-1.45, -1.3, -0.05), (1.45, 1.6, 2.15), h, sym_x=True)
    P = G.P
    X, Y, Z = P[..., 0], P[..., 1], P[..., 2]
    dome = smax(ell(P, SHELL_C, SHELL_R), 0.55 - Z, 0.06)
    plas = ell(P, (0.0, 0.12, 0.64), (0.84, 0.70, 0.24))
    rim = np.sqrt((rim_rho(X, Y) - RIM_K) ** 2 + (Z - RIM_Z) ** 2) - RIM_T
    F = smin(smin(dome, rim, 0.10), plas, 0.10)
    if h < 0.05:
        F = blur(F, 1)
    return G, F, dict(dome=dome, rim=rim, plas=plas)


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


def head_field(h, store):
    frames = {}
    G = Grid((-1.2, -2.55, 0.2), (1.2, -0.15, 2.45), h, sym_x=True)
    P = G.P
    X, Y, Z = P[..., 0], P[..., 1], P[..., 2]
    base = ell(P, HEAD_C, HEAD_R)
    for s in (1, -1):                                               # chubby cheeks
        base = smin(base, ell(P, (s * 0.52, -1.82, 0.82), (0.34, 0.34, 0.30)), 0.16)
    base = smin(base, ell(P, (0.0, -0.85, 0.95), (0.52, 0.55, 0.48)), 0.20)       # neck
    for name, s in (("eyeL", 1), ("eyeR", -1)):
        frames[name] = frame_at(G, base, s * 0.38, 1.12, -2.5, -0.8, (0.19, 0.23))
    # kettle helm, open face: dome + broad rounded brim + a fused plume
    dome = smax(ell(P, HELM_C, (0.88, 0.80, 0.60)), 1.46 - Z, 0.03)
    brim = ell(P, (0.0, -1.36, 1.50), (0.97, 0.90, 0.13))
    plume = smin(ell(P, (0.0, -1.36, 2.10), (0.13, 0.55, 0.20)), ell(P, (0.0, -0.90, 1.98), (0.13, 0.28, 0.20)), 0.12)
    nose = ell(P, (0.0, -2.16, 1.28), (0.105, 0.13, 0.27))                       # nose guard between the eyes
    cheek_g = smin(ell(P, (0.86, -1.60, 1.14), (0.11, 0.30, 0.26)), ell(P, (-0.86, -1.60, 1.14), (0.11, 0.30, 0.26)), 0.02)
    guards = smin(nose, cheek_g, 0.02)
    helm = smin(smin(smin(dome, brim, 0.05), plume, 0.12), guards, 0.05)
    F = smin(base, helm, 0.04)
    snout = ell(P, (0.0, -2.10, 0.88), (0.36, 0.26, 0.24))
    F = smin(F, snout, 0.18)
    frames["emblem"] = frame_at(G, helm, 0.0, 1.78, -2.5, -0.8)
    if h < 0.05:
        F = blur(F, 1)
    if store:
        FACE.update(frames)
    return G, F, dict(helm=helm, brim=brim, plume=plume, dome=dome)


def build_leg(h):
    """Front-left leg (+X): chunky elephant-like column, flat sole, three toe nubs. Others are copies."""
    hx, hy = LEG_X, LEG_YF
    G = Grid((0.15, hy - 0.85, -0.05), (1.35, hy + 0.55, 1.05), h)
    P = G.P
    Z = P[..., 2]
    top = ell(P, (hx, hy, 0.66), (0.33, 0.34, 0.26))
    mid = ell(P, (hx, hy - 0.01, 0.40), (0.33, 0.35, 0.34))
    foot = ell(P, (hx, hy - 0.06, 0.15), (0.37, 0.42, 0.17))
    F = smin(smin(top, mid, 0.18), foot, 0.14)
    for dx, dy in ((-0.21, 0.04), (0.0, 0.0), (0.21, 0.04)):
        F = smin(F, ell(P, (hx + dx, hy - 0.40 + dy, 0.10), (0.115, 0.135, 0.10)), 0.07)
    F = smax(F, -Z, 0.02)                      # flat underside on the ground
    return extract(G, F, None, "leg")


def build_tail(h):
    G = Grid((-0.5, 0.7, 0.1), (0.5, 1.9, 1.1), h, sym_x=True)
    P = G.P
    F = ell(P, (0.0, 1.28, 0.55), (0.17, 0.26, 0.15), axis=(0, 1, -0.25))
    F = smin(F, ell(P, (0.0, 1.04, 0.60), (0.22, 0.24, 0.20)), 0.12)
    return extract(G, F, None, "tail")


def mirror(vf):
    vs, fs = vf
    return vs * np.array((-1.0, 1.0, 1.0)), [tuple(reversed(f)) for f in fs]


def shifted(vf, dy):
    vs, fs = vf
    return vs + np.array((0.0, dy, 0.0)), fs

# =============================================================================================
# painting (numpy), all driven by 3D position
# =============================================================================================
SKIN, SKIN_LT, SKIN_SH, BELLY = rgb(138, 188, 114), rgb(184, 222, 140), rgb(98, 134, 84), rgb(222, 226, 160)
PLATE_A, PLATE_B, PLATE_LT, PLATE_DK, SEAM = rgb(184, 128, 70), rgb(158, 140, 74), rgb(232, 186, 112), rgb(112, 70, 46), rgb(74, 46, 34)
BRASS, BRASS_DK, BRASS_LT = rgb(224, 168, 72), rgb(146, 90, 40), rgb(250, 216, 134)
PLAS, PLAS_SH = rgb(232, 214, 154), rgb(184, 152, 100)
STEEL, STEEL_LT, STEEL_DK = rgb(168, 172, 182), rgb(246, 234, 212), rgb(96, 100, 114)
AMB, AMB_DK, AMB_LT = rgb(226, 142, 52), rgb(170, 84, 40), rgb(250, 190, 98)
CREAM, NAIL, NAVY = rgb(250, 242, 224), rgb(240, 228, 196), rgb(48, 66, 104)
EYE_DARK, EYE_IRIS, EYE_LINE = rgb(24, 16, 20), rgb(112, 62, 36), rgb(30, 22, 24)
BLUSH = rgb(255, 176, 150)
COOL = np.array((0.80, 0.86, 1.0))
TAU = 2 * math.pi


def hash2(a, b):
    return np.modf(np.abs(np.sin(a * 12.9898 + b * 78.233) * 43758.5453))[0]


def _sd(phi, th):
    a, t = math.radians(phi), math.radians(th)
    return np.array((math.sin(a) * math.sin(t), -math.sin(a) * math.cos(t), math.cos(a)))


SCUTE_SEEDS = [_sd(0, 0)] + [_sd(40, 60 * k) for k in range(6)] + [_sd(80, 15 + 30 * k) for k in range(12)]


def paint_body(p, n):
    X, Y, Z = p[:, 0], p[:, 1], p[:, 2]
    d_dome, d_rim = sample("body", "dome", p), sample("body", "rim", p)
    rimm = sstep(0.05, -0.012, d_rim)
    shm = sstep(0.07, -0.012, d_dome) * (1.0 - rimm)
    # rounded hexagonal / pentagonal scutes = Voronoi cells of a crown + 6 + 12 seed layout on the dome
    dv_ = np.stack([X / SHELL_R[0], (Y - SHELL_C[1]) / SHELL_R[1], (Z - SHELL_C[2]) / SHELL_R[2]], 1)
    dv_ /= np.maximum(np.linalg.norm(dv_, axis=1), 1e-6)[:, None]
    d1 = np.full(len(p), 9.0)
    d2 = d1.copy()
    sid = np.zeros(len(p))
    for k, sd in enumerate(SCUTE_SEEDS):
        dk = np.linalg.norm(dv_ - sd, axis=1)
        new1 = dk < d1
        d2 = np.where(new1, d1, np.minimum(d2, dk))
        sid = np.where(new1, float(k), sid)
        d1 = np.where(new1, dk, d1)
    edge = (d2 - d1) * 0.5
    tint = hash2(sid * 1.37 + 2.0, sid * 0.61 + 5.0)
    base = mix(PLATE_A, PLATE_B, tint * 0.8) * (0.92 + 0.16 * hash2(sid * 1.7 + 3.0, sid * 0.3 + 5.3))[:, None]
    lit_top = sstep(-0.1, 0.9, n[:, 2])
    shell = mix(PLATE_DK, base, sstep(0.0, 0.20, edge))                                   # darker toward each plate edge
    shell = mix(shell, PLATE_LT, 0.55 * sstep(0.34, 0.0, d1) * (0.55 + 0.45 * lit_top))   # lighter warm centre
    rings = 0.5 + 0.5 * np.cos(d1 * 34.0 + tint * 6.0)                                   # faint growth rings
    shell = mix(shell, PLATE_DK, 0.10 * sstep(0.6, 1.0, rings) * sstep(0.05, 0.2, edge))
    bd, bl = bands(p, 3.0, 0, 1.5, 11, SHELL_C[1])
    shell = mix(shell, PLATE_DK, 0.22 * bd)
    shell = mix(shell, PLATE_LT, 0.20 * bl * lit_top)
    shell = mix(shell, rgb(120, 74, 50), 0.22 * sstep(1.0, 0.6, Z))
    shell = mix(shell, SEAM, 0.70 * sstep(0.060, 0.012, edge))                            # soft seams
    # plastron / skin underneath
    pl = mix(PLAS_SH, PLAS, sstep(0.3, 0.75, Z))
    # brass shield rim with rivets
    q = rim_rho(X, Y) - RIM_K
    psi = np.arctan2(Z - RIM_Z, q)
    rc = mix(BRASS_DK, BRASS, sstep(-0.9, 0.1, n[:, 2]))
    rc = mix(rc, BRASS_LT, 0.6 * sstep(0.35, 0.95, n[:, 2]))
    bd2, bl2 = bands(p, 4.0, 0, 2.0, 19, SHELL_C[1])
    rc = mix(rc, BRASS_DK, 0.25 * bd2)
    rc = mix(rc, BRASS_LT, 0.25 * bl2)
    ang = np.degrees(np.arctan2(X, -(Y - SHELL_C[1])))
    cell = ((ang + 9.0) % 18.0) / 18.0
    arc = np.minimum(cell, 1 - cell) * math.radians(18) * 1.05
    rd = np.sqrt(arc ** 2 + ((psi - math.radians(55)) * RIM_T) ** 2)
    riv = sstep(0.050, 0.040, rd)
    ring_o = sstep(0.064, 0.054, rd) * (1 - riv)
    rc = mix(rc, BRASS_DK * 0.55, 0.8 * ring_o)
    rc = mix(rc, BRASS_LT, 0.9 * riv)
    c = mix(pl, shell, shm)
    c = mix(c, rc, rimm)
    return c, rimm > 0.5


def paint_head(p, n, eyes_out):
    X, Y, Z = p[:, 0], p[:, 1], p[:, 2]
    nz = vnoise(p * np.array((1.0, 1.0, 0.4)), 8.0, 3)
    c = mix(SKIN_SH, SKIN, sstep(0.3, 1.5, Z))
    c = mix(c, SKIN_LT, 0.10 * (nz - 0.5) * 2 + 0.06)
    c = mix(c, BELLY, 0.70 * sstep(0.0, -0.6, n[:, 2]) * sstep(1.3, 0.9, Z))          # pale chin / throat
    bd, bl = bands(p, 3.0, 0, 1.6, 13, HEAD_C[1])
    c = mix(c, SKIN_SH, 0.30 * bd)
    c = mix(c, SKIN_LT, 0.26 * bl * sstep(-0.3, 0.6, n[:, 2]))
    front = (Y < -1.7) & (n[:, 1] < -0.2)
    for s in (1, -1):                                                                  # soft cheek blush
        bdd = np.sqrt(((X - s * 0.56) / 0.15) ** 2 + ((Z - 0.88) / 0.10) ** 2)
        c = mix(c, BLUSH, 0.45 * sstep(1.0, 0.2, bdd) * front)
    for s in (1, -1):                                                                  # nostrils
        nd = np.sqrt((X - s * 0.10) ** 2 + (Z - 0.97) ** 2)
        nm = (nd < 0.04) & (Y < -2.18) & (n[:, 1] < -0.35)
        c[nm] = mix(c[nm], rgb(70, 74, 44), sstep(0.04, 0.025, nd)[nm])
    zm = 0.72 + 0.9 * X ** 2                                                           # friendly smile
    sm = sstep(0.018, 0.006, np.abs(Z - zm)) * sstep(0.44, 0.38, np.abs(X)) * ((Y < -1.8) & (n[:, 1] < -0.25))
    c = mix(c, rgb(72, 66, 40), 0.9 * sm)
    # eyes: big glossy painted eyes over shallow relief
    for name in ("eyeL", "eyeR"):
        e = FACE[name]
        d = p - e["c"]
        eu, ev = (d @ e["u"]) / e["r"][0], (d @ e["v"]) / e["r"][1]
        frontm = (np.abs(d @ e["n"]) < 0.07) & (n @ e["n"] > 0.45)
        r = np.sqrt(eu * eu + ev * ev)
        ring_ = frontm & (r >= 1.0) & (r < 1.55)
        c[ring_] = mix(c[ring_], c[ring_] * np.array((0.92, 0.88, 0.90)), (0.20 * sstep(1.55, 1.0, r))[ring_])
        line = frontm & (r >= 0.97) & (r < 1.17)
        c[line] = mix(c[line], EYE_LINE, sstep(1.17, 1.06, r)[line])
        inside = frontm & (r < 1.0)
        ce = np.tile(EYE_DARK, (len(p), 1))
        iris = sstep(0.25, 0.85, r) * sstep(0.3, -0.75, ev)
        ce = mix(ce, EYE_IRIS, 0.85 * iris)
        ce = mix(ce, EYE_IRIS * 1.6, 0.50 * sstep(-0.40, -0.80, ev) * sstep(0.30, 0.8, r))
        c[inside] = ce[inside]
        eyes_out.append((inside, eu, ev))
    # kettle helm: painted steel, brass band with rivets, rounded brim, amber plume, crest emblem
    dh, db_, dp = sample("head", "helm", p), sample("head", "brim", p), sample("head", "plume", p)
    hm = np.maximum(sstep(0.05, -0.012, dh), sstep(0.16, 0.02, dp) * sstep(1.80, 1.92, Z))
    st = mix(mix(STEEL_DK, STEEL, 0.55), STEEL, sstep(0.9, 1.6, Z))
    st = mix(st, STEEL_LT, 0.5 * sstep(0.1, 0.9, n[:, 2]) * sstep(1.2, 1.9, Z))
    st = mix(st, STEEL_LT, 0.35 * sstep(0.25, 0.7, -n[:, 1]) * sstep(0.9, 1.3, Z) * sstep(1.45, 1.3, Z))   # warm glint on the guards
    bd2, bl2 = bands(p, 3.0, 0, 2.5, 17, HELM_C[1])
    st = mix(st, STEEL_DK, 0.30 * bd2)
    st = mix(st, STEEL_LT, 0.30 * bl2 * sstep(-0.1, 0.7, n[:, 2]))
    bm = sstep(0.03, -0.01, db_) * sstep(1.52, 1.46, Z)
    st = mix(st, STEEL_DK * 1.05, 0.40 * bm)
    st = mix(st, STEEL_LT, 0.35 * bm * sstep(0.2, 0.8, n[:, 2]))
    bstripe = sstep(0.034, 0.022, np.abs(Z - 1.585)) * (Z > 1.0)
    st = mix(st, mix(BRASS_DK, BRASS, sstep(-0.2, 0.7, n[:, 2])), bstripe * (1 - bm))
    az = np.degrees(np.arctan2(X, -(Y - HELM_C[1])))
    cellr = ((az + 10.0) % 20.0) / 20.0
    rdd = np.sqrt((np.minimum(cellr, 1 - cellr) * math.radians(20) * 0.8) ** 2 + (Z - 1.585) ** 2)
    st = mix(st, BRASS_DK * 0.6, 0.8 * sstep(0.034, 0.026, rdd) * (1 - sstep(0.026, 0.020, rdd)))
    st = mix(st, BRASS_LT, 0.9 * sstep(0.026, 0.020, rdd))
    pm = sstep(0.12, 0.0, dp) * sstep(1.90, 2.00, Z)
    amb = mix(AMB_DK, AMB, sstep(1.9, 2.3, Z))
    amb = mix(amb, AMB_LT, 0.45 * sstep(0.3, 0.9, n[:, 2]))
    bd3, bl3 = bands(p * np.array((3.0, 0.5, 1.0)), 2.0, 0, 3.0, 23, 0.0)
    amb = mix(amb, AMB_DK, 0.30 * bd3)
    st = mix(st, amb, pm)
    # emblem (small shield crest, the Rare accent)
    em = FACE["emblem"]
    d = p - em["c"]
    du, dv, dn = d @ em["u"], d @ em["v"], d @ em["n"]
    efr = (np.abs(dn) < 0.07) & (n @ em["n"] > 0.4)

    def wsh(vv, k=0.0):
        return np.clip(0.17 - k, 0, None) * np.clip(1.0 - (np.clip(-0.04 - vv, 0, None) / 0.23) ** 1.7, 0, 1)
    ins0 = efr & (np.abs(du) < wsh(dv)) & (dv < 0.19) & (dv > -0.27)
    ins1 = efr & (np.abs(du) < wsh(dv, 0.035)) & (dv < 0.155) & (dv > -0.235)
    st[ins0] = CREAM
    st[ins1] = mix(AMB, AMB_LT, np.clip(0.5 + dv[ins1] * 2.0, 0, 1) * 0.5)
    chev = efr & (np.abs(np.abs(du) * 1.0 + dv - 0.02) < 0.025) & (np.abs(du) < 0.10) & ins1
    st[chev] = NAVY
    dot = efr & (np.sqrt(du ** 2 + (dv - 0.095) ** 2) < 0.028) & ins1
    st[dot] = CREAM
    c = mix(c, st, hm)
    return c, hm > 0.5


def paint_leg(p, n, pid):
    s = 1 if pid in (P_FLF, P_FLB) else -1
    hy = LEG_YF if pid in (P_FLF, P_FRF) else LEG_YB
    Z = p[:, 2]
    lx, ly = p[:, 0] * s - LEG_X, p[:, 1] - hy
    c = mix(SKIN_SH, SKIN, sstep(0.0, 0.7, Z))
    c = mix(c, SKIN_LT, 0.35 * sstep(0.3, 0.9, n[:, 2]))
    q = p - np.array((s * LEG_X, hy, 0.0))
    bd, bl = bands(q, 4.0, 0, 2.0, 29 + pid, 0.0)
    c = mix(c, SKIN_SH, 0.28 * bd)
    c = mix(c, SKIN_LT, 0.24 * bl)
    wr = 0.5 + 0.5 * np.cos(Z * 22.0)
    c = mix(c, SKIN_SH, 0.16 * sstep(0.7, 1.0, wr) * sstep(0.1, 0.5, Z))
    for dx in (-0.21, 0.0, 0.21):
        nd = np.sqrt(((lx - dx) / 0.075) ** 2 + ((Z - 0.105) / 0.06) ** 2)
        nm = (ly < -0.30) & (n[:, 1] < -0.3)
        c = mix(c, NAIL, sstep(1.0, 0.7, nd) * nm)
    c = mix(c, SKIN_SH * 0.8, 0.6 * sstep(0.05, 0.0, Z))
    return c


def paint_tail(p, n):
    c = mix(SKIN_SH, SKIN, sstep(0.3, 0.8, p[:, 2]))
    c = mix(c, SKIN_LT, 0.30 * sstep(1.20, 1.60, p[:, 1]))
    bd, bl = bands(p, 4.0, 0, 3.0, 31, 1.4)
    c = mix(c, SKIN_SH, 0.28 * bd)
    return mix(c, SKIN_LT, 0.22 * bl)


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
        h = np.zeros(len(p), bool)
        if pid == P_BODY:
            c, h = paint_body(p, n)
        elif pid == P_HEAD:
            c, h = paint_head(p, n, ex)
        elif pid == P_TAIL:
            c = paint_tail(p, n)
        else:
            c = paint_leg(p, n, pid)
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
    k = np.clip(ks + np.where(hard, 1.2, np.where(part_ids == P_BODY, 1.9, 1.5)) * (kf - ks), 0.0, 1.0)      # visible facets
    sky = 0.5 + 0.5 * Ns[:, 2]
    lightv = 0.60 + 0.42 * k + 0.12 * sky
    head = part_ids == P_HEAD
    ao_w = np.where(head, 0.20, 0.32)
    aol_w = np.where(head, 0.08, 0.18)
    aof = (1.0 - ao_w + ao_w * sstep(0.12, 1.0, ao_s)) * (1.0 - aol_w * (1.0 - sstep(0.2, 1.0, ao_l)))
    shade = lightv * aof * (0.90 + 0.12 * sstep(0.0, 2.3, P[:, 2]))
    lit = col * shade[:, None]
    lit = mix(lit, np.clip(lit * np.array((1.06, 0.97, 0.88)), 0, 1), 0.5 * sstep(1.0, 0.8, shade) * sstep(0.55, 0.75, shade))
    lit = mix(lit, np.clip(lit * np.array((1.0, 0.88, 0.86)) + np.array((0.015, 0.0, 0.006)), 0, 1), 0.75 * sstep(0.78, 0.50, shade))   # warm, never grey
    lit = lit + (sstep(0.3, 1.0, Ns @ Lr) * 0.10)[:, None] * np.array((0.55, 0.70, 1.0))                              # cool rim
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

# =============================================================================================
# build
# =============================================================================================
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
mat = bpy.data.materials.new("Turtle_Atlas")
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


Gf, Ff, fl_ = body_field(H_FINE_BODY)
FUSED["body"] = (Gf, fl_)
Gf, Ff, fl_ = head_field(H_FINE_HEAD, True)
FUSED["head"] = (Gf, fl_)
del Gf, Ff, fl_
Gc, Fc, _ = body_field(H_BODY)
body_vf = extract(Gc, Fc, None, "body")
Gc, Fc, _ = head_field(H_HEAD, False)
head_vf = extract(Gc, Fc, None, "head")
leg_fl = build_leg(H_LEG)
tail_vf = build_tail(H_TAIL)
specs = [("Turtle_Body", P_BODY, body_vf), ("Turtle_Head", P_HEAD, head_vf),
         ("Turtle_LegFL", P_FLF, leg_fl), ("Turtle_LegFR", P_FRF, mirror(leg_fl)),
         ("Turtle_LegBL", P_FLB, shifted(leg_fl, LEG_YB - LEG_YF)), ("Turtle_LegBR", P_FRB, mirror(shifted(leg_fl, LEG_YB - LEG_YF))),
         ("Turtle_Tail", P_TAIL, tail_vf)]
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
    head_obj = parts["Turtle_Head"]
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
        if not (nrm.dot(radial) > 0.35 and nrm.y < -0.1 and abs(ang) < 1.25 and 0.4 < c.z < 2.0):
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
    full[~cov, :3] = SKIN_SH
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
JOINT_PARENT = {n: ("Turtle_Body" if n != "Turtle_Body" else None) for n in PIVOT}
JOINT_NAME = {"Turtle_Body": "root (centre of the shell, under the dome)", "Turtle_Head": "neck, hidden inside the shell front",
              "Turtle_LegFL": "hip, tucked under the rim", "Turtle_LegFR": "hip, tucked under the rim",
              "Turtle_LegBL": "hip, tucked under the rim", "Turtle_LegBR": "hip, tucked under the rim",
              "Turtle_Tail": "tail root, inside the rear of the shell"}
MOTION = {
    "Turtle_Body": "root part: sway roll about Studio Z (+/-4 deg), small bob in Studio Y; shield-up pitch about Studio X (-12 deg = top leans forward)",
    "Turtle_Head": "plod: bob forward (Studio -Z up to 0.12) with a +/-4 deg nod about Studio X; look = yaw about Studio Y; shield-up: pull back 0.45 studs (Studio +Z) and pitch down 20 deg",
    "Turtle_LegFL": "plod = swing about Studio X through the hip (+/-16 deg, diagonal pair with LegBR); lift 0.10 studs in Studio Y on the forward swing",
    "Turtle_LegFR": "plod = swing about Studio X through the hip (+/-16 deg, diagonal pair with LegBL); lift 0.10 studs in Studio Y on the forward swing",
    "Turtle_LegBL": "plod = swing about Studio X through the hip (+/-16 deg, diagonal pair with LegFR); lift 0.10 studs on the forward swing",
    "Turtle_LegBR": "plod = swing about Studio X through the hip (+/-16 deg, diagonal pair with LegFL); lift 0.10 studs on the forward swing",
    "Turtle_Tail": "idle wag about Studio Y (+/-12 deg); shield-up: tuck 0.12 studs forward",
}


def studio(v):
    return [round(-v[0], 4) + 0.0, round(v[2], 4) + 0.0, round(v[1], 4) + 0.0]


def studio_size(v):
    return [round(v[0], 4), round(v[2], 4), round(v[1], 4)]


def world_bounds(o):
    ws = [o.matrix_world @ vv.co for vv in o.data.vertices]
    return (Vector([min(w[k] for w in ws) for k in range(3)]), Vector([max(w[k] for w in ws) for k in range(3)]))


# ---- locomotion data (Blender bone angles: X = pitch, Y = yaw about world Z, Z = roll about -Y) -----------
def plod(s):
    """s = +1 step A, -1 step B. rots in degrees, locs in studs (Blender axes)."""
    lift = 0.10
    rots = {"Body": (0, 0, 4 * s), "LegFL": (16 * s, 0, 0), "LegBR": (16 * s, 0, 0), "LegFR": (-16 * s, 0, 0),
            "LegBL": (-16 * s, 0, 0), "Head": (-4 * s, 0, -4 * s), "Tail": (0, 12 * s, 0)}
    locs = {"Head": (0, -0.06 - 0.06 * s, 0)}
    for b, fwd in (("LegFR", s > 0), ("LegBL", s > 0), ("LegFL", s < 0), ("LegBR", s < 0)):
        if fwd:
            locs[b] = (0, 0, lift)
    return rots, locs


PLOD_PASS = ({"Body": (0, 0, 0), "Head": (0, 0, 0)}, {"Body": (0, 0, 0.04), "Head": (0, -0.06, 0)})
SHIELD = ({"Body": (12, 0, 0), "Head": (20, 0, 0), "LegFL": (-12, 0, 0), "LegFR": (-12, 0, 0), "LegBL": (8, 0, 0), "LegBR": (8, 0, 0)},
          {"Head": (0, 0.45, -0.06), "LegFL": (-0.14, 0, 0.30), "LegFR": (0.14, 0, 0.30), "LegBL": (-0.14, 0, 0.16),
           "LegBR": (0.14, 0, 0.16), "Tail": (0, -0.12, 0.05)})


def studio_pose(rl):
    rots, locs = rl
    out = {}
    for b in PIVOT_BONES:
        r, l = rots.get(b, (0, 0, 0)), locs.get(b, (0, 0, 0))
        if any(r) or any(l):
            out["Turtle_" + b] = {"rot_deg_studio_xyz": [-r[0] + 0.0, r[1] + 0.0, -r[2] + 0.0],
                                  "offset_studs_studio_xyz": [-l[0] + 0.0, l[2] + 0.0, l[1] + 0.0]}
    return out


PIVOT_BONES = [n.replace("Turtle_", "") for n in PIVOT]

report = {"asset": STEM, "blender_version": bpy.app.version_string,
          "authoring": "final Roblox stud size (1 Blender unit = 1 stud); import at 1:1, do not scale",
          "axes": "Blender Z-up, front -Y, the turtle's left +X; feet on z = 0",
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
body_pivot = parts["Turtle_Body"].location.copy()
install = {
    "asset": STEM, "rarity": "Rare", "strong_suit": "Team defense (every 15 s a shell shield blocks one hit to you or a hurt teammate)",
    "accent": "small painted shield-crest emblem on the front of the helm (no glow, no Neon)",
    "role_prop": "knight kettle helm with plume, fused into Turtle_Head; brass shield-crest rim fused into the shell",
    "axis": "studio = (-x, z, y) of blender; Blender front -Y = Studio front -Z",
    "units": "studs; the model is at final size, import 1:1 and do not scale",
    "sides": "L/R are the turtle's own left/right; its left is Blender +X = Studio -X",
    "origin": "all positions are relative to the model origin = the ground point under the model centre (Blender world origin)",
    "ground_point": studio((0.0, 0.0, 0.0)), "overall_size": studio_size(size),
    "overall_center": studio((lo_all + hi_all) / 2), "texture": f"textures/{TEX_PATH.name}",
    "texture_note": "one shared atlas; every MeshPart uses the same TextureID via MeshPart.TextureID (Rare: no Neon, no glow)",
    "rest_rotation": "every part has identity rotation relative to the model at rest",
    "rig": "one Motor6D per part: Part0 = joint_parent, Part1 = the part, C0/C1 placed at the part's pivot",
    "parts": {}}
for name, o in parts.items():
    lo, hi = world_bounds(o)
    install["parts"][name] = {
        "center": studio((lo + hi) / 2), "size": studio_size(hi - lo), "pivot": studio(o.location),
        "pivot_from_body_pivot": studio(o.location - body_pivot), "pivot_is": JOINT_NAME[name],
        "joint_parent": JOINT_PARENT[name], "suggested_motion": MOTION[name]}
install["locomotion"] = "plod"
install["locomotion_data"] = {
    "gait": "plod: slow, sturdy diagonal-pair steps (FL+BR then FR+BL), the shell sways side to side and the head bobs forward with each push",
    "angle_convention": "per part, rotation about the part's own pivot in Studio axes (Roblox CFrame.Angles, degrees) plus a translation offset "
                        "in studs applied in the parent's frame (Motor6D C0). Only parts that move are listed; others stay at rest. "
                        "Blender bone angles in the previews map as Studio X = -bone X, Studio Y = bone Y, Studio Z = -bone Z.",
    "plod": {
        "step_period_s": 1.4, "loop": ["plod_A", "plod_pass_1", "plod_B", "plod_pass_2"],
        "body_sway_deg": 4, "leg_swing_deg": 16, "head_bob_studs": 0.12,
        "frames": {"plod_A": studio_pose(plod(1)), "plod_pass_1": studio_pose(PLOD_PASS),
                   "plod_B": studio_pose(plod(-1)), "plod_pass_2": studio_pose(PLOD_PASS)},
    },
    "shield_up": {
        "note": "guard pose while the team shield is up or on a blocked hit: head and legs half tucked, the shell leans forward like a held shield; hold 0.4 s then ease back to plod",
        "pose": studio_pose(SHIELD),
        "ground_note": "front legs are lifted 0.30 studs and back legs 0.16 so the feet stay on the ground after the shell pitches; re-check against the live ground in Studio",
    },
}
log("overall (w, len, h)", tuple(round(v, 3) for v in (size.x, size.y, size.z)), "tris", report["total_triangles"])

if not QUICK:
    (ROOT / "polygon-report.json").write_text(json.dumps(report, indent=2))
    (ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=2))
    select_only(objs, parts["Turtle_Body"])
    bpy.ops.export_scene.gltf(filepath=str(GLB_PATH), export_format="GLB", use_selection=True, export_apply=True)
    select_only(objs, parts["Turtle_Body"])
    bpy.ops.export_scene.fbx(filepath=str(FBX_PATH), use_selection=True, object_types={"MESH"},
                             axis_forward="-Z", axis_up="Y", path_mode="COPY", embed_textures=True,
                             add_leaf_bones=False)
    log("exported", FBX_PATH.name, GLB_PATH.name)

# =============================================================================================
# armature (Blender only, for posing previews; exports are the plain rigid parts)
# =============================================================================================
arm_data = bpy.data.armatures.new("Turtle_Rig")
arm = bpy.data.objects.new("Turtle_Rig", arm_data)
scene.collection.objects.link(arm)
select_only([arm])
bpy.ops.object.mode_set(mode="EDIT")
ebs = {}
for name, o in parts.items():
    eb = arm_data.edit_bones.new(name.replace("Turtle_", ""))
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
    o.parent_bone = name.replace("Turtle_", "")
    bpy.context.view_layer.update()
    o.matrix_world = mwo
bpy.context.view_layer.update()
log("armature built; max pivot drift", round(max((parts[n].matrix_world.translation - PIVOT[n]).length for n in parts), 6))


def pose(rl):
    """rl = (rots, locs): rots {bone: (x, y, z) degrees}; locs {bone: (dx, dy, dz)} studs in Blender world axes.
    Bone axes: X = world X (pitch), Y = world Z (yaw), Z = world -Y (roll)."""
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




tgt = V(0, -0.25, 1.05)
ft = V(0, -2.0, 1.05)
HEADTURN = ({"Head": (8, 28, 14), "Tail": (0, 25, 0)}, {})
POSES = [
    ("Plod step A: diagonal pair FL+BR back, sway +4, head forward", plod(1), around(tgt, (-0.8, -0.7, 0.2), 13.0), tgt),
    ("Plod step B: FR+BL back, sway -4", plod(-1), around(tgt, (0.8, -0.7, 0.2), 13.0), tgt),
    ("Plod from the side (step A)", plod(1), around(tgt, (-1, 0, 0.08), 14.0), tgt),
    ("Shield up (side): head and legs tucked, shell leans forward", SHIELD, around(tgt, (-1, 0, 0.08), 14.0), tgt),
    ("Shield up (front 3/4)", SHIELD, around(tgt, (-0.7, -1, 0.25), 12.0), tgt),
    ("Head turn 28 + nod 8 + tail wag 25", HEADTURN, around(tgt, (0.45, -1, 0.3), 12.0), tgt),
]

if not NO_PREVIEWS and QUICK:
    items = [(shoot(OUT / "_threeq.png", around(tgt, (-0.75, -0.9, 0.35), 13.0), tgt, res=(800, 800)), "Three-quarter"),
             (shoot(OUT / "_front.png", around(tgt, (0, -1, 0.1), 11.0), tgt, res=(800, 800)), "Front"),
             (shoot(OUT / "_side.png", around(tgt, (-1, 0, 0.1), 14.0), tgt, res=(800, 800)), "Side"),
             (shoot(OUT / "_back.png", around(tgt, (0, 1, 0.25), 12.0), tgt, res=(800, 800)), "Back"),
             (shoot(OUT / "_face.png", around(ft, (-0.3, -1, 0.12), 4.8), ft, res=(800, 800)), "Face")]
    for i in (3, 0):
        pose(POSES[i][1])
        items.append((shoot(OUT / f"_pose{i}.png", POSES[i][2], POSES[i][3], res=(800, 800)), POSES[i][0]))
    pose({})
    make_sheet(items, 3, 400, OUT / ("shape-sheet.png" if SHAPE else "quick-sheet.png"), "Turtle shape run")
    for pth, _ in items:
        pth.unlink()
elif not NO_PREVIEWS:
    shots = [(shoot(OUT / "threeq.png", around(tgt, (-0.75, -0.9, 0.35), 13.0), tgt), "Three-quarter"),
             (shoot(OUT / "front.png", around(tgt, (0, -1, 0.1), 11.0), tgt), "Front"),
             (shoot(OUT / "side.png", around(tgt, (-1, 0, 0.1), 14.0), tgt), "Side (turtle's right)"),
             (shoot(OUT / "back.png", around(tgt, (0, 1, 0.25), 12.0), tgt), "Back")]
    face = shoot(OUT / "face-closeup.png", around(ft, (-0.3, -1, 0.12), 4.8), ft, res=(1400, 1400))
    pose_items = []
    for i, (lab, rl, loc, t) in enumerate(POSES):
        pose(rl)
        pose_items.append((shoot(OUT / f"_pose-{i}.png", loc, t, res=(900, 900)), lab))
    pose({})
    make_sheet(pose_items, 3, 450, OUT / "pose-check.png", "Turtle: pose check through the joint pivots",
               "Each part rotates about its own pivot (Blender armature, preview only). Look for gaps at the hips, neck and tail, in the plod and the shield-up guard.")
    for pth, _ in pose_items:
        pth.unlink()
    make_sheet(shots + [(face, "Face close-up"), (OUT / "pose-check.png", "Pose check (plod, shield up, head turn)")],
               3, 520, OUT / "sheet.png",
               f"Turtle pet (Rare, team defense): {report['total_triangles']:,} tris, one 1024 atlas",
               "Blender 5.2 Eevee renders. Blender-verified, Studio untested.")
log("done")
