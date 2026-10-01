"""Cheetah Cub pet (Epic, strong suit: speed) for the roguelite.

Self-contained generator for background Blender 5.2 (no code imported from other kits).

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 \
        --python build_cheetah_cub.py
    ... -- --shape                 fast look-dev: per-vertex painted colours, no bake, a few renders
    ... -- --shape --pose          also the six pose-check frames
    ... -- --no-previews           exports + reports only

Coordinates: Blender Z-up, 1 unit = 1 stud (final size, import 1:1), paws on z = 0, the cub faces -Y
and its own left is +X. Studio = (-x, z, y) of Blender.

Method (same family as the approved Golden Retriever / Monkey / Penguin): every rigid part is ONE
surface made from analytic signed-distance volumes joined with smooth unions (real fillets), meshed on
a COARSE voxel lattice (the lattice is the mesh, so facets are broad and even), relaxed back onto the
surface and flat shaded. Colour is painted by 3D position (continuous over every join and UV seam) and
baked to one 1024 atlas with icon-style lighting (per-facet key, AO, warm shadow, cool rim).
Epic: one small Neon lightning bolt (separate thin-shell `_Glow` mesh on the scarf end) + a VFX spec.
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
ROOT = Path(r"C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning/blender-pet-kit/cheetah-cub")
STEM = "cheetah-cub"
PRE = "CheetahCub_"
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
    print(f"[cheetah {time.time() - T0:6.1f}s]", *a, flush=True)


P_BODY, P_HEAD, P_EARL, P_EARR, P_FLL, P_FLR, P_RLL, P_RLR, P_TAIL, P_SCARF = range(1, 11)
P_GLOW = 11


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


def frame(z_axis, y_hint):
    """Rows (x, y, z) of a local frame whose z runs along z_axis and whose y leans toward y_hint."""
    z = np.asarray(z_axis, float)
    z = z / np.linalg.norm(z)
    x = np.cross(np.asarray(y_hint, float), z)
    x /= np.linalg.norm(x)
    return np.stack([x, np.cross(z, x), z])


def ell(P, c, radii, R=None):
    return sd_ell(P, c, AXES if R is None else R, radii)


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def capsule(P, a, b, ra, rb):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ab = b - a
    t = np.clip(((P - a) @ ab) / np.dot(ab, ab), 0.0, 1.0)
    return np.linalg.norm(P - (a + t[..., None] * ab), axis=-1) - (ra + (rb - ra) * t)


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


def min_angles(vs, fs):
    a, b, c = vs[[f[0] for f in fs]], vs[[f[1] for f in fs]], vs[[f[2] for f in fs]]

    def ang(p, q, r):
        u, v = q - p, r - p
        cs = np.sum(u * v, 1) / np.maximum(np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1), 1e-12)
        return np.degrees(np.arccos(np.clip(cs, -1, 1)))
    return np.minimum(np.minimum(ang(a, b, c), ang(b, c, a)), ang(c, a, b))


def tidy(grid, F, vs, fs, passes=6):
    """Even out the lattice triangles without moving the surface (flip edges, relax, project back)."""
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


def extract(grid, F, name="fused"):
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
    ob.modifiers.new("Tri", "TRIANGULATE")
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    m2 = ev.to_mesh()
    vo = np.array([v.co[:] for v in m2.vertices], float)
    fo = [tuple(p.vertices) for p in m2.polygons]
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    vo, fo = tidy(grid, F, vo, fo)
    ec = {}
    for fc in fo:
        for i in range(len(fc)):
            k = tuple(sorted((fc[i], fc[(i + 1) % len(fc)])))
            ec[k] = ec.get(k, 0) + 1
    log(name, "isosurface", n_tri, "tris ->", len(fo), "| non-manifold edges", sum(1 for v in ec.values() if v != 2))
    return vo, fo


def build(fn, lo, hi, h, name, sym=False):
    G = Grid(lo, hi, h, sym_x=sym)
    return extract(G, fn(G.P)[0], name)


def grad(fn, p, e=0.004):
    p = np.atleast_2d(p)
    g = np.stack([fn(p + e * ax)[0] - fn(p - e * ax)[0] for ax in np.eye(3)], -1) / (2 * e)
    return g / np.maximum(np.linalg.norm(g, axis=-1, keepdims=True), 1e-9)


def project(fn, p, steps=6):
    p = np.atleast_2d(np.asarray(p, float)).copy()
    for _ in range(steps):
        d = fn(p)[0]
        p = p - d[:, None] * grad(fn, p)
    return p


def surf_point(fn, x, z, y0=-1.5, y1=-0.3):
    """First surface crossing along +Y from the front, plus the outward normal."""
    ys = np.linspace(y0, y1, 1500)
    pts = np.stack([np.full_like(ys, x), ys, np.full_like(ys, z)], 1)
    d = fn(pts)[0]
    i = int(np.nonzero(d < 0)[0][0])
    t = d[i - 1] / (d[i - 1] - d[i])
    p = np.array((x, ys[i - 1] + t * (ys[i] - ys[i - 1]), z))
    return p, grad(fn, p)[0]


def mirror(vf):
    vs, fs = vf
    return vs * np.array((-1.0, 1.0, 1.0)), [tuple(reversed(f)) for f in fs]


# =============================================================================================
# the parts (Blender axes, studs). Cub's left = +X, front = -Y.
# =============================================================================================
HS = float(arg("--hscale", 1.0))
H_BODY, H_HEAD, H_EAR, H_LEG, H_TAIL, H_SCARF = (0.122 * HS, 0.100 * HS, 0.054 * HS, 0.082 * HS,
                                                  0.086 * HS, 0.060 * HS)
PIVOT = {
    PRE + "Body": V(0.0, 0.10, 0.80),
    PRE + "Head": V(0.0, -0.40, 1.14),
    PRE + "EarL": V(0.40, -0.47, 2.02),
    PRE + "EarR": V(-0.40, -0.47, 2.02),
    PRE + "FrontLegL": V(0.30, -0.30, 0.64),
    PRE + "FrontLegR": V(-0.30, -0.30, 0.64),
    PRE + "RearLegL": V(0.32, 0.50, 0.64),
    PRE + "RearLegR": V(-0.32, 0.50, 0.64),
    PRE + "Tail": V(0.0, 0.86, 0.86),
    PRE + "Scarf": V(-0.47, -0.30, 1.09),
}
PIVOT[PRE + "Scarf_Glow"] = PIVOT[PRE + "Scarf"].copy()
HEAD_C = (0.0, -0.55, 1.62)
HEAD_R = (0.70, 0.60, 0.58)
NECK_C = np.array((0.0, -0.36, 1.06))
COLLAR_N = np.array((0.0, -0.33, 1.0)) / np.linalg.norm((0.0, -0.33, 1.0))
FACE = {}


def body_sdf(P):
    barrel = ell(P, (0, 0.12, 0.80), (0.56, 0.70, 0.48))
    chest = ell(P, (0, -0.28, 0.88), (0.52, 0.44, 0.46))
    rump = ell(P, (0, 0.52, 0.82), (0.54, 0.40, 0.46))
    neck = ell(P, NECK_C, (0.40, 0.36, 0.30))
    F = smin(smin(barrel, chest, 0.20), rump, 0.20)
    F = smin(F, neck, 0.15)
    # cub mane: soft broad lumps of fluff on the nape and shoulders, ONE surface with the body
    mane = ell(P, (0, 0.10, 1.25), (0.30, 0.26, 0.15))
    for s in (1, -1):
        mane = smin(mane, ell(P, (s * 0.25, 0.00, 1.19), (0.20, 0.22, 0.14)), 0.10)
    mane = smin(mane, ell(P, (0, 0.38, 1.22), (0.25, 0.22, 0.12)), 0.10)
    F = smin(F, mane, 0.10)
    # collar band of the speed scarf, a little proud of the neck, dipping toward the chest
    shell = ell(P, NECK_C, (0.47, 0.43, 0.37))
    band = smax(shell, np.abs((P - NECK_C) @ COLLAR_N) - 0.075, 0.02)
    F = smin(F, band, 0.03)
    return F, dict(mane=mane, collar=band)


def head_sdf(P):
    base = ell(P, HEAD_C, HEAD_R)
    for s in (1, -1):
        base = smin(base, ell(P, (s * 0.44, -0.72, 1.38), (0.27, 0.25, 0.21)), 0.14)      # chubby cheeks
    base = smin(base, ell(P, (0, -0.22, 1.36), (0.36, 0.24, 0.24)), 0.12)                  # nape fluff
    muz = smin(ell(P, (0, -0.98, 1.43), (0.29, 0.24, 0.20)), ell(P, (0, -0.90, 1.31), (0.21, 0.20, 0.12)), 0.08)
    nose = ell(P, (0, -1.17, 1.545), (0.10, 0.06, 0.065))
    F = smin(base, muz, 0.10)                        # the muzzle flows out of the face with a gentle stop
    F = smin(F, nose, 0.03)
    return F, dict(base=base, muz=muz, nose=nose)


EAR_A = np.array((0.55, 0.05, 1.0)) / np.linalg.norm((0.55, 0.05, 1.0))
EAR_R = frame(EAR_A, (0, 1, 0))


def ear_sdf(P):
    """Left ear: small, round, a soft thick disc whose base sinks into the head."""
    piv = np.array(PIVOT[PRE + "EarL"])
    F = ell(P, piv + EAR_A * 0.16, (0.195, 0.09, 0.205), EAR_R)
    return F, {}


FL_PTS = dict(top=(0.30, -0.30, 0.56), a=(0.30, -0.31, 0.50), b=(0.31, -0.36, 0.18), paw=(0.31, -0.43, 0.10))
RL_PTS = dict(top=(0.33, 0.50, 0.58), a=(0.34, 0.52, 0.42), b=(0.34, 0.46, 0.18), paw=(0.34, 0.37, 0.10))


def leg_sdf(P, L, top_r):
    F = ell(P, L["top"], top_r)
    F = smin(F, capsule(P, L["a"], L["b"], 0.165, 0.15), 0.08)
    pw = np.array(L["paw"])
    F = smin(F, ell(P, pw, (0.175, 0.22, 0.11)), 0.07)
    for dx in (-0.085, 0.0, 0.085):
        F = smin(F, ell(P, pw + (dx, -0.15, -0.025), (0.065, 0.08, 0.075)), 0.04)
    F = smax(F, -P[..., 2], 0.02)                       # flat pads on the ground
    return F, {}


def front_leg_sdf(P):
    return leg_sdf(P, FL_PTS, (0.20, 0.22, 0.22))


def rear_leg_sdf(P):
    return leg_sdf(P, RL_PTS, (0.24, 0.30, 0.28))     # chunky haunch


TAIL_PTS = [(0.80, 0.86, 0.155), (1.06, 0.90, 0.155), (1.32, 1.02, 0.15), (1.52, 1.24, 0.145),
            (1.60, 1.50, 0.14), (1.54, 1.74, 0.135), (1.40, 1.84, 0.13)]          # (y, z, radius)
_tc = catmull(TAIL_PTS, 8)
TAIL_CU = np.stack([np.zeros(len(_tc)), _tc[:, 0], _tc[:, 1]], 1)
TAIL_RAD = _tc[:, 2]
_seg = np.linalg.norm(np.diff(TAIL_CU, axis=0), axis=1)
TAIL_T = np.concatenate([[0.0], np.cumsum(_seg)]) / np.sum(_seg)


def tail_sdf(P):
    F = np.full(P.shape[:-1], 9.0)
    for i in range(len(TAIL_CU) - 1):
        F = np.minimum(F, capsule(P, TAIL_CU[i], TAIL_CU[i + 1], TAIL_RAD[i], TAIL_RAD[i + 1]))
    F = smin(F, ell(P, TAIL_CU[-1], (0.135, 0.135, 0.135)), 0.05)
    return F, {}


def ribbon(pts, n_per, n0, w_fn):
    cu = catmull(pts, n_per)
    T = np.gradient(cu, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    n0 = np.asarray(n0, float) / np.linalg.norm(n0)
    N = n0 - (T @ n0)[:, None] * T
    N /= np.linalg.norm(N, axis=1)[:, None]
    W = np.cross(T, N)
    seg = np.linalg.norm(np.diff(cu, axis=0), axis=1)
    t = np.concatenate([[0.0], np.cumsum(seg)]) / np.sum(seg)
    return dict(c=cu, T=T, N=N, W=W, t=t, w=w_fn(t))


SCARF_THICK = 0.072
SCARF_MAIN = ribbon([(-0.47, -0.30, 1.09), (-0.62, -0.08, 1.16), (-0.68, 0.22, 1.26), (-0.66, 0.52, 1.36),
                     (-0.60, 0.80, 1.42), (-0.54, 1.04, 1.40)], 12, (-1, 0, 0.8),
                    lambda t: 0.12 + 0.07 * np.clip(t / 0.25, 0, 1) - 0.03 * np.clip((t - 0.80) / 0.20, 0, 1))
SCARF_SHORT = ribbon([(-0.48, -0.32, 1.07), (-0.60, -0.22, 0.95), (-0.66, -0.10, 0.84)], 10, (-1, 0, 0),
                     lambda t: 0.10 + 0.02 * t)
KNOT_C = np.array(PIVOT[PRE + "Scarf"])


def ribbon_sdf(P, rb):
    F = np.full(P.shape[:-1], 9.0)
    for i in range(len(rb["c"])):
        R = np.stack([rb["W"][i], rb["N"][i], rb["T"][i]])
        F = np.minimum(F, sd_ell(P, rb["c"][i], R, (rb["w"][i], SCARF_THICK, 0.06)))
    return F


def scarf_sdf(P):
    main = ribbon_sdf(P, SCARF_MAIN)
    rb = SCARF_MAIN
    we = rb["w"][-1]
    R = np.stack([rb["W"][-1], rb["N"][-1], rb["T"][-1]])
    main = smin(main, sd_ell(P, rb["c"][-1] - rb["T"][-1] * 0.04, R, (we, SCARF_THICK, we * 0.85)), 0.02)   # rounded tongue end
    short = ribbon_sdf(P, SCARF_SHORT)
    knot = ell(P, KNOT_C, (0.125, 0.13, 0.12))
    F = smin(smin(main, short, 0.04), knot, 0.05)
    return F, dict(knot=knot)


# Epic Neon accent: a small lightning bolt, a thin shell just proud of the scarf's outer face
BOLT = [(0.25, 1.0), (-0.55, 0.0), (-0.05, 0.0), (-0.30, -1.0), (0.60, 0.12), (0.08, 0.12)]
BOLT_TRIS = [(0, 1, 2), (0, 2, 5), (2, 3, 4), (2, 4, 5)]
BOLT_T, BOLT_S = 0.72, 0.12
GLOW_RGB = (255, 226, 92)


def build_bolt():
    rb = SCARF_MAIN
    i = int(round(BOLT_T * (len(rb["c"]) - 1)))
    c, T, N, W = rb["c"][i], rb["T"][i], rb["N"][i], rb["W"][i]
    guess = np.array([c + W * u * BOLT_S + T * v * BOLT_S + N * (SCARF_THICK + 0.03) for u, v in BOLT])
    on = project(scarf_sdf, guess)
    nr = grad(scarf_sdf, on)
    top, bot = on + 0.016 * nr, on - 0.008 * nr
    vs = np.vstack([top, bot])
    k = len(BOLT)
    fs = [tuple(f) for f in BOLT_TRIS] + [tuple(j + k for j in reversed(f)) for f in BOLT_TRIS]
    for a in range(k):
        b = (a + 1) % k
        fs += [(a, b + k, b), (a, a + k, b + k)]
    FACE["bolt"] = dict(c=on.mean(0), n=nr.mean(0))
    return vs, fs


SPOTS = {}


def make_spots(key, vs, seed, keep, radius, gap, max_n):
    vs = np.asarray(vs)
    km = keep(vs)
    rng = np.random.default_rng(seed)
    cs, rs = [], []
    for i in rng.permutation(len(vs)):
        if not km[i]:
            continue
        p = vs[i]
        r = float(radius(p[None])[0])
        if cs and np.any(np.linalg.norm(np.asarray(cs) - p, axis=1) < np.asarray(rs) + r + float(gap(p[None])[0])):
            continue
        cs.append(p)
        rs.append(r)
        if len(cs) >= max_n:
            break
    SPOTS[key] = (np.array(cs).reshape(-1, 3), np.array(rs))
    log("spots", key, len(cs))


# =============================================================================================
# painting: colour by 3D position
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


COOL = np.array((0.80, 0.86, 1.0))
COAT_DK, COAT, COAT_MD, COAT_LT = rgb(184, 112, 46), rgb(222, 156, 70), rgb(236, 180, 92), rgb(250, 212, 136)
CREAM_SH, CREAM, CREAM_LT = rgb(232, 200, 156), rgb(250, 234, 204), rgb(255, 248, 232)
MANE, MANE_LT = rgb(240, 214, 164), rgb(252, 238, 206)
SPOT, SPOT_LT = rgb(52, 34, 26), rgb(86, 56, 38)
BLUE_DK, BLUE, BLUE_LT = rgb(16, 80, 146), rgb(26, 136, 208), rgb(112, 202, 244)
WHITE = rgb(247, 245, 238)
EYE_DARK, EYE_IRIS, EYE_LINE = rgb(30, 18, 12), rgb(200, 130, 36), rgb(36, 22, 16)
NOSE, MOUTH, TONGUE = rgb(46, 30, 30), rgb(112, 34, 46), rgb(236, 116, 126)
EAR_DK, EAR_IN = rgb(48, 32, 26), rgb(246, 204, 176)
BLUSH = rgb(250, 160, 130)


def bands(p, fx, fz, seed, cy=0.0):
    """Broad painterly brush bands: (dark, light) masks from anisotropic noise."""
    az_ = np.arctan2(p[:, 0], -(p[:, 1] - cy))
    q = np.stack([np.cos(az_) * fx, np.sin(az_) * fx, p[:, 2] * fz], 1)
    s_az = vnoise(q, 1.0, seed)
    s3 = vnoise(np.stack([p[:, 0] * fx, (p[:, 1] - cy) * fx, p[:, 2] * fz], 1), 1.0, seed + 3)
    w = sstep(0.12, 0.40, np.hypot(p[:, 0], p[:, 1] - cy))
    s_ = s3 + (s_az - s3) * w
    return 1.0 - sstep(0.38, 0.46, s_), sstep(0.60, 0.68, s_)


def fur(p, n, seed, zr, cy=0.0, fx=3.0, fz=1.4):
    """Golden-tan coat in three-four value ranges: warmer/darker low, light on top, broad brush strokes."""
    nz = vnoise(p * np.array((1.0, 1.0, 0.4)), 8.0, seed)
    c = mix(COAT_DK, COAT, sstep(zr[0], zr[1], p[:, 2]))
    c = mix(c, COAT_MD, 0.50 * sstep(-0.1, 0.9, n[:, 2]) * sstep(zr[0] + 0.25, zr[1], p[:, 2]))
    c = mix(c, COAT_MD, 0.10 * (nz - 0.5) * 2 + 0.04)
    sd_, sl_ = bands(p, fx, fz, seed + 10, cy)
    c = mix(c, COAT_DK, 0.42 * sd_)
    c = mix(c, COAT_LT, 0.40 * sl_ * sstep(-0.3, 0.6, n[:, 2]))
    c = mix(c, rgb(176, 92, 52), 0.16 * sstep(0.40, 0.08, p[:, 2]))          # warm bounce low down
    big = vnoise(p, 1.7, seed + 5)
    c = mix(c, rgb(240, 176, 84), 0.30 * sstep(0.54, 0.70, big))
    c = mix(c, COAT_DK, 0.22 * sstep(0.36, 0.22, big))
    return c


def spot_mask(p, key, seed):
    cs, rs = SPOTS.get(key, (np.zeros((0, 3)), np.zeros(0)))
    if len(cs) == 0:
        return np.zeros(len(p))
    d = np.full(len(p), 9.0)
    for c, r in zip(cs, rs):
        d = np.minimum(d, (np.linalg.norm(p - c, axis=1) - r) / r)
    wob = vnoise(p, 9.0, seed) - 0.5
    return sstep(0.10, -0.12, d + 0.25 * wob)


def spot_colour(p, seed):
    sd_, sl_ = bands(p, 4.0, 4.0, seed)
    return mix(mix(np.tile(SPOT, (len(p), 1)), SPOT_LT, 0.35 * sl_), SPOT * 0.8, 0.3 * sd_)


def seg_dist2d(x, z, pts):
    d = np.full(len(x), 9.0)
    tt = np.zeros(len(x))
    L = 0.0
    lens = [np.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts[:-1], pts[1:])]
    tot = sum(lens)
    for (ax, az), (bx, bz), ln in zip(pts[:-1], pts[1:], lens):
        ux, uz = bx - ax, bz - az
        t = np.clip(((x - ax) * ux + (z - az) * uz) / (ux * ux + uz * uz), 0, 1)
        dd = np.hypot(x - (ax + t * ux), z - (az + t * uz))
        better = dd < d
        d = np.where(better, dd, d)
        tt = np.where(better, (L + t * ln) / tot, tt)
        L += ln
    return d, tt


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


def scarf_colour(p, n, wn, knot):
    """Electric-blue speed scarf: lit along the outer face, white racing stripes near both edges."""
    c = mix(BLUE_DK, BLUE, sstep(-0.6, 0.5, n[:, 2] + 0.3 * (-n[:, 0])))
    sd_, sl_ = bands(p, 3.0, 3.0, 31)
    c = mix(mix(c, BLUE_DK, 0.30 * sd_), BLUE_LT, 0.40 * sl_ * sstep(0.0, 0.7, n[:, 2]))
    st = sstep(0.09, 0.03, np.abs(np.abs(wn) - 0.70))
    c = mix(c, WHITE, 0.90 * st)
    c = mix(c, BLUE_DK, 0.45 * knot)
    return c


def paint_body(p, n):
    X, Y, Z = p[:, 0], p[:, 1], p[:, 2]
    c = fur(p, n, 1, (0.35, 1.30), 0.1, 3.0, 1.4)
    nz2 = vnoise(p, 3.0, 2)
    under = sstep(-0.25, -0.60, n[:, 2]) * sstep(0.95, 0.6, Z)
    chest = sstep(-0.42, -0.62, Y) * sstep(1.12, 0.92, Z)
    cm = np.clip(np.maximum(under, chest) + 0.20 * (nz2 - 0.5), 0, 1)
    cr = mix(CREAM_SH, CREAM, sstep(0.3, 1.0, Z))
    cd_, cl_ = bands(p, 1.0, 5.0, 12)
    cr = mix(mix(cr, CREAM_SH, 0.35 * cd_), CREAM_LT, 0.35 * cl_)
    c = mix(c, cr, cm)
    fl = body_sdf(p)[1]
    mm = sstep(0.07, 0.0, fl["mane"] + 0.05 * (vnoise(p, 6.0, 3) - 0.5)) * sstep(1.02, 1.15, Z)
    md_, ml_ = bands(p, 3.5, 2.0, 14)
    mc = mix(mix(MANE_LT, MANE, 0.40 * md_), CREAM_LT, 0.45 * ml_)
    c = mix(c, mc, mm)
    sm = spot_mask(p, "body", 4) * (1 - cm) * (1 - mm)
    c = mix(c, spot_colour(p, 5), 0.94 * sm)
    cb = sstep(0.025, -0.005, fl["collar"])
    dz = (p - NECK_C) @ COLLAR_N
    col = mix(BLUE_DK, BLUE, sstep(-0.4, 0.6, n[:, 2] + 0.6 * dz / 0.075))
    col = mix(col, WHITE, 0.9 * sstep(0.016, 0.006, np.abs(np.abs(dz) - 0.050)))
    c = mix(c, col, cb)
    return c, cb > 0.5


def paint_head(p, n, eyes_out):
    X, Y, Z = p[:, 0], p[:, 1], p[:, 2]
    nz2 = vnoise(p, 3.0, 4)
    c = fur(p, n, 3, (1.05, 2.2), -0.55, 3.0, 1.6)
    hard = np.zeros(len(p), bool)
    fl = head_sdf(p)[1]
    # nape: the start of the cub mane, slightly lighter fluffy fur
    nape = sstep(-0.42, -0.18, Y + 0.06 * (nz2 - 0.5)) * sstep(1.78, 1.55, Z)
    md_, ml_ = bands(p, 3.5, 2.0, 16)
    c = mix(c, mix(mix(MANE_LT, MANE, 0.40 * md_), CREAM_LT, 0.45 * ml_), 0.95 * nape)
    sm = spot_mask(p, "head", 6) * (1 - nape)
    c = mix(c, spot_colour(p, 7), 0.92 * sm)
    # cream muzzle, chin and lower cheeks
    front = sstep(-0.05, -0.40, n[:, 1])
    muzm = sstep(0.05, -0.01, fl["muz"] + 0.03 * (nz2 - 0.5))
    chk = np.zeros(len(p))
    for s in (1, -1):
        chk = np.maximum(chk, sstep(1.05, 0.85, ((X - s * 0.30) / 0.30) ** 2 + ((Z - 1.38) / 0.15) ** 2 + 0.2 * (nz2 - 0.5)))
    chin = sstep(1.30, 1.18, Z) * sstep(-0.62, -0.85, Y)
    cm = np.clip(np.maximum(np.maximum(muzm, chk * front), chin), 0, 1)
    cr = mix(CREAM_SH, CREAM, sstep(1.15, 1.55, Z))
    cr = mix(cr, CREAM_LT, 0.5 * sstep(0.05, -0.02, fl["muz"]) * sstep(-0.3, 0.6, n[:, 2] - n[:, 1]))
    c = mix(c, cr, cm)
    for s in (1, -1):                                                         # soft warm blush
        bd = np.sqrt(((X - s * 0.46) / 0.13) ** 2 + ((Z - 1.47) / 0.08) ** 2)
        c = mix(c, BLUSH, 0.30 * sstep(1.0, 0.2, bd) * (Y < -0.75))
    hard |= cm > 0.5
    # eyes: big glossy painted eyes over shallow relief, cream patch above each
    for name in ("eyeL", "eyeR"):
        e = FACE[name]
        d = p - e["c"]
        eu, ev = (d @ e["u"]) / e["r"][0], (d @ e["v"]) / e["r"][1]
        fr = (np.abs(d @ e["n"]) < 0.08) & (n @ e["n"] > 0.40)
        r = np.sqrt(eu * eu + ev * ev)
        above = sstep(1.0, 0.75, np.sqrt((eu / 1.05) ** 2 + ((ev - 1.62) / 0.42) ** 2))
        c = mix(c, CREAM_LT, 0.85 * above * fr)
        ring = fr & (r >= 1.0) & (r < 1.45)
        c[ring] = mix(c[ring], c[ring] * np.array((0.94, 0.86, 0.80)), (0.25 * sstep(1.45, 1.0, r))[ring])
        line = fr & (r >= 0.97) & (r < 1.15)
        c[line] = mix(c[line], EYE_LINE, sstep(1.15, 1.05, r)[line])
        inside = fr & (r < 1.0)
        ce = np.tile(EYE_DARK, (len(p), 1))
        iris = sstep(0.25, 0.85, r) * sstep(0.3, -0.75, ev)
        ce = mix(ce, EYE_IRIS, 0.85 * iris)
        ce = mix(ce, np.clip(EYE_IRIS * 1.35, 0, 1), 0.55 * sstep(-0.40, -0.85, ev) * sstep(0.30, 0.8, r))
        c[inside] = ce[inside]
        eyes_out.append((inside, eu, ev))
        hard |= fr & (r < 1.5)
    # signature tear lines: inner eye corner down the side of the muzzle to the mouth corner
    fm = (n[:, 1] < -0.15) & (Y < -0.80)
    eye_in = np.zeros(len(p), bool)
    for inside, _, _ in eyes_out:
        eye_in |= inside
    for s in (1, -1):
        d2, tt = seg_dist2d(X * s, Z, [(0.165, 1.600), (0.190, 1.540), (0.180, 1.485), (0.125, 1.440)])
        wdt = 0.062 - 0.026 * tt                        # bold: about 3x the first pass
        tl = fm * sstep(wdt, wdt - 0.012, d2) * ~eye_in
        edge_ = fm * sstep(wdt + 0.030, wdt + 0.018, d2) * (1 - tl) * ~eye_in * (X * s > 0.10)
        c = mix(c, CREAM_LT, 0.9 * edge_)              # thin cream highlight so the stripe reads at distance
        c = mix(c, SPOT, tl)
        hard |= (tl > 0.5) | (edge_ > 0.5)
    # nose and a small happy open mouth
    nm = sstep(0.012, -0.004, fl["nose"]) * (n[:, 1] < 0.2)
    ncol = mix(np.tile(NOSE, (len(p), 1)), rgb(120, 96, 100), 0.6 * sstep(0.4, 0.9, n[:, 2]) * sstep(1.56, 1.60, Z))
    c = mix(c, ncol, nm)
    fr = (n[:, 1] < -0.15) & (Y < -1.0)
    s_ = np.clip(1.0 - (X / 0.11) ** 2, 0.0, 1.0)
    zu = 1.445 - 0.030 * s_
    zl = zu - 0.072 * np.sqrt(s_)
    inm = fr & (np.abs(X) < 0.11) & (Z < zu) & (Z > zl)
    mc = np.tile(MOUTH, (len(p), 1))
    mc = mix(mc, TONGUE, sstep(zl + 0.035 * np.sqrt(s_), zl + 0.008, Z))
    c[inm] = mc[inm]
    outl = fr & (np.abs(X) < 0.122) & (np.minimum(np.abs(Z - zu), np.abs(Z - zl)) < 0.011) & (Z <= zu + 0.011) & (Z >= zl - 0.011)
    c[outl] = SPOT
    phil = fr & (np.abs(X) < 0.009) & (Z < 1.49) & (Z > zu)
    c[phil] = SPOT
    hard |= inm | outl | phil | (nm > 0.5)
    return c, hard


def paint_ear(p, n, s):
    Pm, nm_ = p * np.array((s, 1.0, 1.0)), n * np.array((s, 1.0, 1.0))
    piv = np.array(PIVOT[PRE + "EarL"])
    d = Pm - piv
    along = d @ EAR_A
    c = fur(Pm, nm_, 21, (1.9, 2.3), -0.47, 3.0, 2.0)
    ry = d @ EAR_R[1]                                    # + = back of the ear
    back = sstep(-0.01, 0.03, ry) * sstep(0.06, 0.14, along)
    c = mix(c, mix(np.tile(EAR_DK, (len(p), 1)), SPOT_LT, 0.25 * sstep(0.2, 0.9, nm_[:, 2])), back)
    inpl = np.sqrt(((d @ EAR_R[0]) / 0.15) ** 2 + ((along - 0.15) / 0.16) ** 2)
    inner = sstep(-0.01, -0.04, ry) * sstep(1.0, 0.75, inpl)
    c = mix(c, mix(EAR_IN, CREAM_LT, 0.4 * sstep(0.6, 0.0, inpl)), inner)
    rim = sstep(-0.02, -0.04, ry) * sstep(0.82, 1.0, inpl) * sstep(0.12, 0.2, along)
    c = mix(c, EAR_DK, 0.7 * rim)
    return c, (inner > 0.5) | (back > 0.5)


def paint_leg(p, n, pid):
    s = 1 if pid in (P_FLL, P_RLL) else -1
    Pm, nm_ = p * np.array((s, 1.0, 1.0)), n * np.array((s, 1.0, 1.0))
    X, Y, Z = Pm[:, 0], Pm[:, 1], Pm[:, 2]
    L = FL_PTS if pid in (P_FLL, P_FLR) else RL_PTS
    c = fur(Pm, nm_, 7 + pid, (0.0, 0.8), 0.0, 2.5, 2.2)
    inner = sstep(0.25, 0.14, X) * sstep(0.5, 0.2, Z)
    c = mix(c, CREAM_SH, 0.5 * inner)
    paw = sstep(0.24, 0.14, Z)
    c = mix(c, mix(COAT_LT, CREAM, 0.45), 0.55 * paw * sstep(-0.2, 0.4, nm_[:, 2] - nm_[:, 1]))
    pw = np.array(L["paw"])
    for k in (-1, 1):                                                       # toe grooves
        gx = np.abs(X - (pw[0] + k * 0.0425))
        c = mix(c, rgb(140, 84, 44), 0.75 * sstep(0.013, 0.004, gx) * sstep(pw[1] - 0.12, pw[1] - 0.17, Y) * sstep(0.03, 0.08, Z))
    key = {P_FLL: "flegL", P_FLR: "flegR", P_RLL: "rlegL", P_RLR: "rlegR"}[pid]
    c = mix(c, spot_colour(p, 9), 0.92 * spot_mask(p, key, 8))
    return c, paw > 0.5


def tail_param(p):
    d = np.linalg.norm(p[:, None, :] - TAIL_CU[None], axis=2)
    i = np.argmin(d, axis=1)
    return TAIL_T[i]


def paint_tail(p, n):
    t = tail_param(p)
    c = fur(p, n, 11, (0.7, 1.6), 0.0, 2.5, 2.0)
    c = mix(c, CREAM_SH, 0.55 * sstep(-0.2, -0.6, n[:, 2]) * sstep(0.9, 0.7, t))
    c = mix(c, spot_colour(p, 12), 0.92 * spot_mask(p, "tail", 10) * sstep(0.56, 0.48, t))
    wob = 0.012 * (vnoise(p, 7.0, 13) - 0.5)
    ring = np.zeros(len(p))
    for tc, hw in ((0.62, 0.030), (0.74, 0.034), (0.85, 0.036)):
        ring = np.maximum(ring, sstep(hw + 0.008, hw - 0.006, np.abs(t + wob - tc)))
    ring = np.maximum(ring, sstep(0.915, 0.93, t + wob))
    c = mix(c, spot_colour(p, 14), 0.95 * ring)
    return c, ring > 0.5


def scarf_param(p):
    best = np.full(len(p), 9.0)
    wn = np.zeros(len(p))
    for rb in (SCARF_MAIN, SCARF_SHORT):
        d = np.linalg.norm(p[:, None, :] - rb["c"][None], axis=2)
        i = np.argmin(d, axis=1)
        dm = d[np.arange(len(p)), i]
        w = np.sum((p - rb["c"][i]) * rb["W"][i], axis=1) / rb["w"][i]
        better = dm < best
        best = np.where(better, dm, best)
        wn = np.where(better, w, wn)
    return wn


def paint_scarf(p, n):
    wn = scarf_param(p)
    knot = sstep(0.02, -0.03, ell(p, KNOT_C, (0.125, 0.13, 0.12)))
    c = scarf_colour(p, n, wn, knot)
    return c, np.ones(len(p), bool)


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
        if pid == P_BODY:
            c, h = paint_body(p, n)
        elif pid == P_HEAD:
            c, h = paint_head(p, n, ex)
        elif pid in (P_EARL, P_EARR):
            c, h = paint_ear(p, n, 1 if pid == P_EARL else -1)
        elif pid in (P_FLL, P_FLR, P_RLL, P_RLR):
            c, h = paint_leg(p, n, pid)
        elif pid == P_TAIL:
            c, h = paint_tail(p, n)
        else:
            c, h = paint_scarf(p, n)
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
    lightv = 0.60 + 0.42 * k + 0.12 * sky + 0.24 * np.clip(Ns @ Lf, 0, 1)   # warm fill from behind so the back reads
    head = part_ids == P_HEAD
    ao_w = np.where(head, 0.20, 0.32)
    aol_w = np.where(head, 0.08, 0.18)
    aof = (1.0 - ao_w + ao_w * sstep(0.12, 1.0, ao_s)) * (1.0 - aol_w * (1.0 - sstep(0.2, 1.0, ao_l)))
    shade = lightv * aof * (0.90 + 0.12 * sstep(0.0, 2.3, P[:, 2]))
    lit = col * shade[:, None]
    lit = mix(lit, np.clip(lit * np.array((1.07, 0.96, 0.84)), 0, 1), 0.65 * sstep(1.0, 0.65, shade))   # warm shadows
    lit = mix(lit, lit * COOL, 0.30 * sstep(0.70, 0.45, shade))
    lit = lit + (sstep(0.3, 1.0, Ns @ Lr) * 0.11)[:, None] * np.array((0.55, 0.70, 1.0))           # cool rim
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
def world_bounds_early(o):
    ws = [o.matrix_world @ vv.co for vv in o.data.vertices]
    return ([min(w[k] for w in ws) for k in range(3)], [max(w[k] for w in ws) for k in range(3)])


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
mat = bpy.data.materials.new("CheetahCub_Atlas")
mat.use_nodes = True
glow_mat = bpy.data.materials.new("CheetahCub_Glow")
glow_mat.use_nodes = True
_gl = tuple(((c / 255.0 + 0.055) / 1.055) ** 2.4 for c in GLOW_RGB) + (1.0,)
_bs = glow_mat.node_tree.nodes["Principled BSDF"]
_bs.inputs["Base Color"].default_value = _gl
_bs.inputs["Emission Color"].default_value = _gl
_bs.inputs["Emission Strength"].default_value = 2.5


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


for nm, sgn in (("eyeL", 1), ("eyeR", -1)):
    p_, n_ = surf_point(lambda P: (head_sdf(P)[1]["base"], None), sgn * 0.30, 1.70)
    R_ = frame(n_, (0, 0, 1))
    u_, v_ = R_[0].copy(), R_[1].copy()
    if u_[0] < 0:
        u_ = -u_
    if v_[2] < 0:
        v_ = -v_
    FACE[nm] = dict(c=p_, u=u_, v=v_, n=n_, r=(0.165, 0.19))
log("eye centres", {k: np.round(v["c"], 3).tolist() for k, v in FACE.items()})

body_vf = build(body_sdf, (-0.75, -0.95, 0.15), (0.75, 1.05, 1.55), H_BODY, "body", sym=True)
head_vf = build(head_sdf, (-1.0, -1.40, 0.95), (1.0, 0.20, 2.35), H_HEAD, "head", sym=True)
ear_l = build(ear_sdf, (0.10, -0.72, 1.80), (0.80, -0.18, 2.50), H_EAR, "ear")
fleg_l = build(front_leg_sdf, (0.0, -0.85, -0.05), (0.62, -0.02, 0.90), H_LEG, "front_leg")
rleg_l = build(rear_leg_sdf, (0.0, 0.02, -0.05), (0.70, 0.95, 0.95), H_LEG, "rear_leg")
tail_vf = build(tail_sdf, (-0.30, 0.55, 0.60), (0.30, 1.85, 2.05), H_TAIL, "tail")
scarf_vf = build(scarf_sdf, (-0.95, -0.55, 0.62), (-0.20, 1.62, 1.62), H_SCARF, "scarf")
bolt_vf = build_bolt()

# spots: bold, soft, rounded; bigger and fewer on the back
bvs = body_vf[0]


def _body_keep(q):
    f = body_sdf(q)[1]
    chest = (q[:, 1] < -0.42) & (q[:, 2] < 1.08)
    return (q[:, 2] > 0.55) & (f["mane"] > 0.06) & (f["collar"] > 0.06) & ~chest


make_spots("body", bvs, 11, _body_keep, lambda q: 0.062 + 0.058 * sstep(0.95, 1.28, q[:, 2]),
           lambda q: 0.07 + 0.06 * sstep(0.95, 1.28, q[:, 2]), 34)
ear_piv = [np.array(PIVOT[PRE + "EarL"]), np.array(PIVOT[PRE + "EarR"])]
make_spots("head", head_vf[0], 12,
           lambda q: (q[:, 1] > -0.78) & (q[:, 2] > 1.62) & ~((q[:, 1] > -0.30) & (q[:, 2] < 1.80))
           & (np.linalg.norm(q - ear_piv[0], axis=1) > 0.20) & (np.linalg.norm(q - ear_piv[1], axis=1) > 0.20),
           lambda q: np.full(len(q), 0.042), lambda q: np.full(len(q), 0.075), 16)
for key, vf, sd in (("flegL", fleg_l, 13), ("flegR", mirror(fleg_l), 14), ("rlegL", rleg_l, 15), ("rlegR", mirror(rleg_l), 16)):
    make_spots(key, vf[0], sd, lambda q: (q[:, 2] > 0.22) & (q[:, 2] < 0.7), lambda q: np.full(len(q), 0.045),
               lambda q: np.full(len(q), 0.07), 8)
make_spots("tail", tail_vf[0], 17, lambda q: tail_param(q) < 0.50, lambda q: np.full(len(q), 0.05),
           lambda q: np.full(len(q), 0.06), 10)

specs = [(PRE + "Body", P_BODY, body_vf), (PRE + "Head", P_HEAD, head_vf),
         (PRE + "EarL", P_EARL, ear_l), (PRE + "EarR", P_EARR, mirror(ear_l)),
         (PRE + "FrontLegL", P_FLL, fleg_l), (PRE + "FrontLegR", P_FLR, mirror(fleg_l)),
         (PRE + "RearLegL", P_RLL, rleg_l), (PRE + "RearLegR", P_RLR, mirror(rleg_l)),
         (PRE + "Tail", P_TAIL, tail_vf), (PRE + "Scarf", P_SCARF, scarf_vf)]
objs = [make_object(n, pid, vf, mat) for n, pid, vf in specs]
glow = make_object(PRE + "Scarf_Glow", P_GLOW, bolt_vf, glow_mat)
parts = {o.name: o for o in objs}
parts[glow.name] = glow
log("built", {o.name: len(o.data.polygons) for o in objs + [glow]})


def select_only(obs, active=None):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or obs[0]


def tri_count(o):
    o.data.calc_loop_triangles()
    return len(o.data.loop_triangles)


select_only(objs + [glow])
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
        col = catchlights(np.clip(col * sh[:, None], 0, 1), eyes) ** 2.2     # sRGB-authored -> linear attribute
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
    tris = {o.name: tri_count(o) for o in objs + [glow]}
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
    head_obj = parts[PRE + "Head"]
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
        if not (nrm.dot(radial) > 0.35 and nrm.y < -0.1 and abs(ang) < 1.25 and 1.15 < c.z < 2.25):
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
    oc = maps["occ"][idx, :3].astype(np.float64)
    ao_s, ao_l, curv = np.clip(oc[:, 0], 0, 1), np.clip(oc[:, 1], 0, 1), oc[:, 2]
    del maps
    edge = sstep(0.995, 0.93, np.sum(Nb * Ns, axis=1)) * sstep(0.49, 0.53, curv)

    colour, hard, eyes = paint_all(P, Ns, part)
    colour = light(colour, P, Ns, Nf, hard, ao_s, ao_l, edge, part)
    colour = catchlights(colour, eyes)

    full = np.zeros((BAKE * BAKE, 4), np.float32)
    full[idx, :3] = colour
    full[:, 3] = 1.0
    full[~cov, :3] = COAT
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
    tris = {o.name: tri_count(o) for o in objs + [glow]}
    log("triangles", sum(tris.values()), tris)

# =============================================================================================
# reports (Studio axes = (-x, z, y) of Blender)
# =============================================================================================
bpy.context.view_layer.update()
JOINT_PARENT = {PRE + "Body": None, PRE + "Head": PRE + "Body", PRE + "EarL": PRE + "Head", PRE + "EarR": PRE + "Head",
                PRE + "FrontLegL": PRE + "Body", PRE + "FrontLegR": PRE + "Body", PRE + "RearLegL": PRE + "Body",
                PRE + "RearLegR": PRE + "Body", PRE + "Tail": PRE + "Body", PRE + "Scarf": PRE + "Body",
                PRE + "Scarf_Glow": PRE + "Scarf"}
JOINT_NAME = {PRE + "Body": "root (belly centre)", PRE + "Head": "neck, hidden under the big head",
              PRE + "EarL": "ear base, sunk into the head", PRE + "EarR": "ear base, sunk into the head",
              PRE + "FrontLegL": "shoulder", PRE + "FrontLegR": "shoulder", PRE + "RearLegL": "hip",
              PRE + "RearLegR": "hip", PRE + "Tail": "tail base, inside the rump",
              PRE + "Scarf": "the scarf knot on the collar (cub's right side of the neck)",
              PRE + "Scarf_Glow": "same as the scarf pivot (rigid weld to the scarf)"}
MOTION = {
    PRE + "Body": "root part: bob in Studio Y and pitch about Studio X for the gallop's spine stretch and curl",
    PRE + "Head": "nod = pitch about Studio X, tilt = roll about Studio Z, look = yaw about Studio Y, through the neck",
    PRE + "EarL": "flick / fold back = pitch about Studio X through the ear base (back = negative Studio X angle)",
    PRE + "EarR": "flick / fold back = pitch about Studio X through the ear base (back = negative Studio X angle)",
    PRE + "FrontLegL": "swing about Studio X through the shoulder; reach forward = positive Studio X angle",
    PRE + "FrontLegR": "swing about Studio X through the shoulder; reach forward = positive Studio X angle",
    PRE + "RearLegL": "swing about Studio X through the hip; push back = negative Studio X angle",
    PRE + "RearLegR": "swing about Studio X through the hip; push back = negative Studio X angle",
    PRE + "Tail": "lift / lower = pitch about Studio X through the base, flick = yaw about Studio Y",
    PRE + "Scarf": "stream up = pitch about Studio X through the knot, flutter = small yaw / roll noise",
    PRE + "Scarf_Glow": "none: WeldConstraint to CheetahCub_Scarf",
}

# Pose dictionaries in Blender-bone degrees (X pitch, Y yaw about world Z, Z roll about world -Y); also exported
# as Studio angles (Studio = (-x, y, -z) of these). "_drop" lowers the root (studs).
GATHER = {"Body": (6, 0, 0), "Head": (-8, 0, 0), "FrontLegL": (30, 0, 0), "FrontLegR": (24, 0, 0),
          "RearLegL": (-34, 0, 0), "RearLegR": (-28, 0, 0), "Tail": (-12, 0, 0), "Scarf": (-8, 0, 0)}
REACH = {"Body": (-3, 0, 0), "Head": (2, 0, 0), "FrontLegL": (-44, 0, 0), "FrontLegR": (-38, 0, 0),
         "RearLegL": (-20, 0, 0), "RearLegR": (-14, 0, 0), "Tail": (2, 0, 0), "Scarf": (4, 0, 0)}
STRETCH = {"Body": (-8, 0, 0), "Head": (8, 0, 0), "FrontLegL": (-42, 0, 0), "FrontLegR": (-36, 0, 0),
           "RearLegL": (42, 0, 0), "RearLegR": (36, 0, 0), "Tail": (14, 0, 0), "Scarf": (10, 0, 0),
           "EarL": (-14, 0, 0), "EarR": (-14, 0, 0)}
LAND = {"Body": (3, 0, 0), "Head": (-4, 0, 0), "FrontLegL": (14, 0, 0), "FrontLegR": (20, 0, 0),
        "RearLegL": (26, 0, 0), "RearLegR": (20, 0, 0), "Tail": (6, 0, 0), "Scarf": (2, 0, 0)}
ZOOM = {"_drop": 0.12, "Body": (-5, 0, 0), "Head": (10, 0, 0), "EarL": (-55, 0, 0), "EarR": (-55, 0, 0),
        "FrontLegL": (-62, 0, 0), "FrontLegR": (-56, 0, 0), "RearLegL": (58, 0, 0), "RearLegR": (52, 0, 0),
        "Tail": (-24, 0, 0), "Scarf": (16, 0, 0)}
HEAD_TURN = {"Head": (4, 32, 12)}
TAIL_FLICK = {"Tail": (12, 30, 0)}


def studio_angles(d):
    return {PRE + k: [round(-v[0], 1) + 0.0, round(v[1], 1) + 0.0, round(-v[2], 1) + 0.0]
            for k, v in d.items() if not k.startswith("_")}


def studio(v):
    return [round(-v[0], 4) + 0.0, round(v[2], 4) + 0.0, round(v[1], 4) + 0.0]


def studio_size(v):
    return [round(v[0], 4), round(v[2], 4), round(v[1], 4)]


def world_bounds(o):
    ws = [o.matrix_world @ vv.co for vv in o.data.vertices]
    return (Vector([min(w[k] for w in ws) for k in range(3)]), Vector([max(w[k] for w in ws) for k in range(3)]))


def gframe(d, t, name):
    return dict(t=t, name=name, blender_bone_deg={k: list(v) for k, v in d.items() if not k.startswith("_")},
                studio_deg=studio_angles(d), body_drop_studs=d.get("_drop", 0.0))


report = {"asset": STEM, "blender_version": bpy.app.version_string,
          "authoring": "final Roblox stud size (1 Blender unit = 1 stud); import at 1:1, do not scale",
          "axes": "Blender Z-up, front -Y, the cub's left +X; paws on z = 0",
          "texture": f"textures/{TEX_PATH.name} ({ATLAS}x{ATLAS}, shared by every part except the _Glow part)",
          "parts": {}}
lo_all, hi_all = Vector((1e9,) * 3), Vector((-1e9,) * 3)
for name, o in parts.items():
    me = o.data
    me.calc_loop_triangles()
    if me.uv_layers:
        uv = me.uv_layers.active.data
        us, vs_ = [d.uv.x for d in uv], [d.uv.y for d in uv]
        uvr = [round(min(us), 4), round(max(us), 4), round(min(vs_), 4), round(max(vs_), 4)]
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
        "joint_parent": JOINT_PARENT[name], "uv_range": uvr, "glow": name.endswith("_Glow")}
report["total_triangles"] = sum(pp["triangles"] for pp in report["parts"].values())
size = hi_all - lo_all
report["overall"] = {"bbox_min": [round(v, 4) for v in lo_all], "bbox_max": [round(v, 4) for v in hi_all],
                     "height_studs": round(size.z, 4), "length_studs": round(size.y, 4), "width_studs": round(size.x, 4)}
body_pivot = parts[PRE + "Body"].location.copy()
scarf_end = Vector(SCARF_MAIN["c"][-1])
PAWS = {PRE + "FrontLegL": V(*FL_PTS["paw"]), PRE + "FrontLegR": V(-FL_PTS["paw"][0], *FL_PTS["paw"][1:]),
        PRE + "RearLegL": V(*RL_PTS["paw"]), PRE + "RearLegR": V(-RL_PTS["paw"][0], *RL_PTS["paw"][1:])}
install = {
    "asset": STEM, "rarity": "Epic", "strong_suit": "Speed: +move speed, and a short speed burst after you get hit "
                                                    "(numbers live in the pet balance table, not in the model)",
    "axis": "studio = (-x, z, y) of blender; Blender front -Y = Studio front -Z",
    "units": "studs; the model is at final size, import 1:1 and do not scale",
    "sides": "L/R are the cub's own left/right; its left is Blender +X = Studio -X",
    "origin": "all positions are relative to the model origin = the ground point under the body (Blender world origin)",
    "ground_point": studio((0.0, 0.0, 0.0)), "overall_size": studio_size(size),
    "overall_center": studio((lo_all + hi_all) / 2), "texture": f"textures/{TEX_PATH.name}",
    "texture_note": "one shared atlas on every MeshPart via MeshPart.TextureID, except CheetahCub_Scarf_Glow",
    "glow_parts": {PRE + "Scarf_Glow": {
        "Material": "Neon", "Color": list(GLOW_RGB), "Transparency": 0, "TextureID": "none",
        "weld": "WeldConstraint to CheetahCub_Scarf (same pivot)",
        "note": "a small lightning bolt, a thin shell 0.016 stud proud of the scarf's outer face near its end. "
                "Subtle on purpose: only the bolt glows"}},
    "role_prop": "electric-blue speed scarf: a collar band fused into the body, plus the knot, one long streaming "
                 "tail and one short hanging tail as their own part (CheetahCub_Scarf) pivoting at the knot",
    "rest_pose": "mobile, ready-to-run standing stance on all four paws (head up, tail up, scarf streaming); the "
                 "model is never authored sitting. Any idle is an extra pose layered on top (see locomotion_data)",
    "rest_rotation": "every part has identity rotation relative to the model at rest",
    "rig": "one Motor6D per part (except the _Glow weld): Part0 = joint_parent, Part1 = the part, C0/C1 at the part's pivot",
    "angle_convention": "studio_deg = CFrame.Angles(math.rad(x), math.rad(y), math.rad(z)) about the part's own pivot, "
                        "applied as Motor6D.Transform; blender_bone_deg are the preview-rig values (Studio = (-x, y, -z) "
                        "of them); body_drop_studs lowers the root in Studio Y",
    "parts": {}}
for name, o in parts.items():
    lo, hi = world_bounds(o)
    install["parts"][name] = {
        "center": studio((lo + hi) / 2), "size": studio_size(hi - lo), "pivot": studio(o.location),
        "pivot_from_body_pivot": studio(o.location - body_pivot), "pivot_is": JOINT_NAME[name],
        "joint_parent": JOINT_PARENT[name], "suggested_motion": MOTION[name]}
install["locomotion"] = "gallop"
install["locomotion_data"] = {
    "gait": "eager bounding gallop: the FRONT pair reaches together, then the BACK pair pushes together (the pairs move "
            "as pairs, left slightly ahead of right). The spine stretches and curls through the body pitch, the head "
            "counter-pitches to stay level, the tail and scarf trail the body by a quarter cycle",
    "period_s": 0.42,
    "body_bob_studs": 0.10,
    "frames": [gframe(GATHER, 0.0, "gather: all four paws collected under the body, spine curled"),
               gframe(REACH, 0.28, "front reach: front pair swings forward together, back pair still under"),
               gframe(STRETCH, 0.55, "stretch: back pair pushes back together, full spine stretch, highest point"),
               gframe(LAND, 0.80, "land: front pair plants and sweeps back, back pair swings forward")],
    "interpolation": "cubic ease between frames, loop to gather; add +body_bob_studs Studio-Y at the stretch frame "
                     "and 0 at gather. Walk speed below ~60% of max: scale every angle by 0.6 and the period by 1.2",
    "zoom_sprint": dict(note="speed-burst pose (after-hit burst or catching up): low and stretched, ears folded back, "
                             "scarf streaming up; hold this and oscillate the legs +/-12 deg at 0.25 s",
                        **gframe(ZOOM, 0.0, "zoom")),
    "head_turn": dict(note="idle look-around: yaw 32 and roll 12 through the neck", **gframe(HEAD_TURN, 0.0, "head turn")),
    "tail_flick": dict(note="idle tail flick: lift 12 and yaw 30 through the tail base, 0.5 s out and back",
                       **gframe(TAIL_FLICK, 0.0, "tail flick")),
}
install["vfx"] = [
    {"name": "ScarfSpeedTrail", "kind": "Trail between two attachments across the scarf tip; Enabled while running",
     "part": PRE + "Scarf",
     "attachment0_from_part_pivot": studio(Vector(SCARF_MAIN["c"][-4] + SCARF_MAIN["W"][-4] * 0.07) - PIVOT[PRE + "Scarf"]),
     "attachment1_from_part_pivot": studio(Vector(SCARF_MAIN["c"][-4] - SCARF_MAIN["W"][-4] * 0.07) - PIVOT[PRE + "Scarf"]),
     "position_model": studio(scarf_end), "color": [120, 220, 255],
     "suggested": {"Lifetime": 0.22, "MinLength": 0.05, "FaceCamera": True, "LightEmission": 0.7, "LightInfluence": 0,
                   "Transparency": "NumberSequence 0:0.55, 1:1", "WidthScale": "NumberSequence 0:1, 1:0.2",
                   "Color": "ColorSequence 0:(150,230,255), 1:(70,170,240)",
                   "note": "faint; Enabled only above ~70% of the cub's run speed"}},
    {"name": "PawSparks", "kind": "ParticleEmitter on an attachment at each paw (four copies), faint speed sparks "
                                  "kicked back while running",
     "parts": {k: {"attachment_from_part_pivot": studio(v - PIVOT[k]), "position_model": studio(v)} for k, v in PAWS.items()},
     "color": [255, 230, 120],
     "suggested": {"Texture": "a small soft streak / spark (e.g. rbxasset://textures/particles/sparkles_main.dds)",
                   "Rate": 6, "Lifetime": [0.15, 0.3], "Size": "NumberSequence 0:0.08, 1:0", "Speed": [1.5, 3],
                   "SpreadAngle": [25, 25], "EmissionDirection": "Back", "Drag": 4, "LightEmission": 0.8,
                   "LightInfluence": 0, "Transparency": "NumberSequence 0:0.35, 1:1", "LockedToPart": False,
                   "note": "Rate 0 when idle or walking slowly"}},
    {"name": "SpeedBurst", "kind": "one-shot ParticleEmitter:Emit(18) + 1.5 s boost when the after-hit speed burst "
                                   "triggers",
     "part": PRE + "Body", "attachment_from_part_pivot": studio(V(0, 0.15, 0.85) - body_pivot),
     "position_model": studio(V(0, 0.15, 0.85)), "color": [255, 236, 130],
     "suggested": {"Texture": "the same spark streak", "Emit": 18, "Lifetime": [0.25, 0.45],
                   "Size": "NumberSequence 0:0.18, 1:0", "Speed": [6, 10], "SpreadAngle": [180, 180],
                   "Drag": 6, "LightEmission": 1, "LightInfluence": 0, "Transparency": "NumberSequence 0:0.1, 1:1",
                   "during_burst": "ScarfSpeedTrail Transparency 0:0.25 and LightEmission 1, PawSparks Rate 20, "
                                   "Scarf_Glow Color brightened ~20%, pose blends to zoom_sprint; all revert after 1.5 s"}},
]
log("overall (w, len, h)", tuple(round(v, 3) for v in (size.x, size.y, size.z)), "tris", report["total_triangles"])

if not QUICK:
    (ROOT / "polygon-report.json").write_text(json.dumps(report, indent=2))
    (ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=2))
    select_only(objs + [glow], parts[PRE + "Body"])
    bpy.ops.export_scene.gltf(filepath=str(GLB_PATH), export_format="GLB", use_selection=True, export_apply=True)
    select_only(objs + [glow], parts[PRE + "Body"])
    bpy.ops.export_scene.fbx(filepath=str(FBX_PATH), use_selection=True, object_types={"MESH"},
                             axis_forward="-Z", axis_up="Y", path_mode="COPY", embed_textures=True,
                             add_leaf_bones=False)
    log("exported", FBX_PATH.name, GLB_PATH.name)

# =============================================================================================
# armature (Blender only, for posing previews; exports are the plain rigid parts)
# =============================================================================================
arm_data = bpy.data.armatures.new("CheetahCub_Rig")
arm = bpy.data.objects.new("CheetahCub_Rig", arm_data)
scene.collection.objects.link(arm)
select_only([arm])
bpy.ops.object.mode_set(mode="EDIT")
ebs = {}
for name, o in parts.items():
    if name.endswith("_Glow"):
        continue
    eb = arm_data.edit_bones.new(name.replace(PRE, ""))
    eb.head = o.location
    eb.tail = o.location + Vector((0, 0, 0.25))
    eb.roll = 0.0
    ebs[name] = eb
for name, par in JOINT_PARENT.items():
    if par and name in ebs:
        ebs[name].parent = ebs[par]
bpy.ops.object.mode_set(mode="OBJECT")
for name, o in parts.items():
    mwo = o.matrix_world.copy()
    o.parent = arm
    o.parent_type = "BONE"
    o.parent_bone = "Scarf" if name.endswith("_Glow") else name.replace(PRE, "")
    bpy.context.view_layer.update()
    o.matrix_world = mwo
bpy.context.view_layer.update()
log("armature built; max pivot drift", round(max((parts[n].matrix_world.translation - PIVOT[n]).length for n in parts), 6))


def pose(rots):
    """rots: {bone: (x, y, z) degrees}. Bone axes: X = world X (pitch / swing), Y = world Z (yaw),
    Z = world -Y (roll). '_drop' lowers the root bone."""
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = [math.radians(v) for v in rots.get(pb.name, (0, 0, 0))]
        pb.location = (0.0, -rots.get("_drop", 0.0), 0.0) if pb.name == "Body" else (0.0, 0.0, 0.0)
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


tgt = V(0, 0.22, 1.08)
ft = V(0, -0.92, 1.66)
DIST = 11.0
POSES = [
    ("Gallop gather: paws collected, spine curled", GATHER, around(tgt, (-1, -0.12, 0.08), DIST), tgt),
    ("Gallop stretch: front pair reaches, back pair pushes", STRETCH, around(tgt, (-1, -0.12, 0.08), DIST), tgt),
    ("Zoom sprint: low, ears back, scarf streaming", ZOOM, around(tgt, (-0.8, -0.75, 0.22), DIST), tgt),
    ("Head turn 32 + tilt 12", HEAD_TURN, around(ft, (-0.35, -1, 0.15), 7.5), ft),
    ("Tail flick: lift 12 + yaw 30 (from behind)", TAIL_FLICK, around(tgt, (0.45, 1, 0.35), DIST), tgt),
    ("Gallop stretch from behind", STRETCH, around(tgt, (-0.35, 1, 0.3), DIST), tgt),
]

if not NO_PREVIEWS and QUICK:
    shoot(OUT / "threeq.png", around(tgt, (-0.75, -0.9, 0.35), DIST), tgt, res=(800, 800))
    shoot(OUT / "front.png", around(tgt, (0, -1, 0.12), DIST), tgt, res=(800, 800))
    shoot(OUT / "face-closeup.png", around(ft, (-0.3, -1, 0.12), 4.8), ft, res=(800, 800))
    shoot(OUT / "side.png", around(tgt, (-1, 0, 0.1), DIST), tgt, res=(800, 800))
    shoot(OUT / "back.png", around(tgt, (0.3, 1, 0.3), DIST), tgt, res=(800, 800))
    if "--pose" in ARGS:
        pose_items = []
        for i, (lab, rots, loc, t) in enumerate(POSES):
            pose(rots)
            pose_items.append((shoot(OUT / f"_pose-{i}.png", loc, t, res=(600, 600)), lab))
        pose({})
        make_sheet(pose_items, 3, 400, OUT / "pose-quick.png", "Cheetah Cub pose check (quick)")
        for pth, _ in pose_items:
            pth.unlink()
    shots = [(OUT / n, n) for n in ("threeq.png", "front.png", "side.png", "back.png", "face-closeup.png")]
    make_sheet(shots, 3, 400, OUT / "shape-quick.png", "Cheetah Cub shape pass (vertex colour, no bake)")
elif not NO_PREVIEWS:
    shots = [(shoot(OUT / "threeq.png", around(tgt, (-0.75, -0.9, 0.35), DIST), tgt), "Three-quarter"),
             (shoot(OUT / "front.png", around(tgt, (0, -1, 0.12), DIST), tgt), "Front"),
             (shoot(OUT / "side.png", around(tgt, (-1, 0, 0.1), DIST), tgt), "Side (cub's right, scarf side)"),
             (shoot(OUT / "back.png", around(tgt, (0.3, 1, 0.3), DIST), tgt), "Back (follow view)")]
    face = shoot(OUT / "face-closeup.png", around(ft, (-0.3, -1, 0.12), 4.8), ft, res=(1400, 1400))
    pose_items = []
    for i, (lab, rots, loc, t) in enumerate(POSES):
        pose(rots)
        pose_items.append((shoot(OUT / f"_pose-{i}.png", loc, t, res=(900, 900)), lab))
    pose({})
    make_sheet(pose_items, 3, 450, OUT / "pose-check.png", "Cheetah Cub: pose check through the joint pivots",
               "Each part rotates about its own pivot (Blender armature, preview only). Look for gaps at the shoulders, hips, neck, ears, tail base and scarf knot.")
    for pth, _ in pose_items:
        pth.unlink()
    make_sheet(shots + [(face, "Face close-up"), (OUT / "pose-check.png", "Pose check (gallop, zoom, head turn, tail flick)")],
               3, 520, OUT / "sheet.png",
               f"Cheetah Cub pet (Epic, speed): {report['total_triangles']:,} tris, one 1024 atlas + Neon bolt",
               "Blender 5.2 Eevee renders, glow part shown emissive. Blender-verified, Studio untested.")
log("done")
