"""Lucky Cat pet (Epic, strong suit: Luck) for the roguelite. A chibi maneki-neko.

Self-contained generator for background Blender 5.2 (no code imported from other kits; the coarse-lattice
meshing, painter, bake and preview code is copied from the approved Penguin / Golden Retriever kits).

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 \
        --python build_lucky_cat.py
    ... -- --shape --out <ABSOLUTE dir>     fast look-dev: per-vertex painted colours, no bake, few renders
    ... -- --quick --out <ABSOLUTE dir>     1024 bake, a few renders, no exports
    ... -- --pose                           add walk / beckon quick renders to a --shape or --quick run
    ... -- --no-previews                    exports + reports only

Coordinates: Blender Z-up, 1 unit = 1 stud (final size, import 1:1), seated on z = 0, the cat faces -Y
and its own left is +X. Studio = (-x, z, y) of Blender.

REST POSE = standing on all four legs (walk-ready chibi stance): short chunky legs, big head forward, tail up,
red collar with a separate dangling gold bell and a separate dangling koban coin. The walk (diagonal pairs) and the
short beckon emote (right front paw lifted beside the cheek, palm forward, waving) are rig data in
studio-install-data.json. The head is modelled in its own local frame and moved by HEAD_OFF.

Method: every rigid part is ONE surface from analytic signed-distance volumes joined with smooth unions,
meshed on a COARSE voxel lattice (the lattice is the mesh: broad, even facets), relaxed back onto the
surface and flat shaded. Colour is painted by 3D position (continuous over every join) and baked to one
1024 atlas with icon lighting (per-facet key, AO, warm shadow, cool rim).
Glow (Epic): the coin is painted gold in the atlas; a thin separate rim mesh `LuckyCat_CoinRim_Glow`
wraps the coin edge and is meant to be Neon warm gold in Studio.
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
STEM = "lucky-cat"
PRE = "LuckyCat_"
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
_out = arg("--out", str(ROOT / "previews"))
if not Path(_out).is_absolute():
    raise SystemExit("--out must be an ABSOLUTE path")
OUT = Path(_out)
TEX_PATH = ROOT / "textures" / f"{STEM}.png"
FBX_PATH = ROOT / "exports" / "fbx" / f"{STEM}.fbx"
GLB_PATH = ROOT / "exports" / "glb" / f"{STEM}.glb"
BLEND_PATH = ROOT / f"{STEM}.blend"
ATLAS = 1024
BAKE = 1024 if QUICK else 2048
for d in (TEX_PATH.parent, FBX_PATH.parent, GLB_PATH.parent, OUT):
    d.mkdir(parents=True, exist_ok=True)


def log(*a):
    print(f"[lucky-cat {time.time() - T0:6.1f}s]", *a, flush=True)


P_BODY, P_HEAD, P_FRONTR, P_FRONTL, P_HINDL, P_HINDR, P_TAIL, P_BELL, P_COIN = range(1, 10)
P_GLOW = 10


def V(*a):
    return Vector(a if len(a) == 3 else a[0])


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


# =============================================================================================
# signed-distance toolkit (copied from the Penguin kit)
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


def sd_ell(P, c, R, radii):
    q = (P - np.asarray(c, float)) @ np.asarray(R, float).T
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


def capsule(P, a, b, ra, rb):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ba = b - a
    t = np.clip(((P - a) @ ba) / (ba @ ba), 0.0, 1.0)
    q = P - (a + t[..., None] * ba)
    return np.linalg.norm(q, axis=-1) - (ra + (rb - ra) * t)


def sd_tri(px, py, A, B, C):
    """2D signed distance to a triangle (Inigo Quilez), vectorised."""
    p = np.stack([px, py], -1)
    A, B, C = (np.asarray(v, float) for v in (A, B, C))
    e0, e1, e2 = B - A, C - B, A - C
    v0, v1, v2 = p - A, p - B, p - C

    def seg(v, e):
        t = np.clip((v @ e) / (e @ e), 0.0, 1.0)
        return v - t[..., None] * e
    pq0, pq1, pq2 = seg(v0, e0), seg(v1, e1), seg(v2, e2)
    s = np.sign(e0[0] * e2[1] - e0[1] * e2[0])
    dx = np.minimum(np.minimum(np.sum(pq0 * pq0, -1), np.sum(pq1 * pq1, -1)), np.sum(pq2 * pq2, -1))
    dy = np.minimum(np.minimum(s * (v0[..., 0] * e0[1] - v0[..., 1] * e0[0]),
                               s * (v1[..., 0] * e1[1] - v1[..., 1] * e1[0])),
                    s * (v2[..., 0] * e2[1] - v2[..., 1] * e2[0]))
    return -np.sqrt(dx) * np.sign(dy)


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
    ob.modifiers.new("Tri", "TRIANGULATE")           # coarse lattice: already even, just triangulate
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
# design (Blender axes, studs). Cat's left = +X. Seated beckon pose is the rest pose.
# =============================================================================================
HEAD_C = np.array((0.0, -0.10, 1.60))        # head LOCAL frame (fields, eyes, ears, face paint)
HEAD_R = (0.64, 0.54, 0.52)
HEAD_OFF = np.array((0.0, -0.30, -0.17))     # local head frame -> standing position
ZC_COLLAR = 0.74
NECK_Y, NECK_RX, NECK_RY = -0.30, 0.285, 0.265
EAR_TRI = ((-0.15, -0.06), (0.15, -0.06), (0.0, 0.30))
SHOULDER_L = np.array((0.22, -0.22, 0.50))
ANKLE_F = np.array((0.225, -0.27, 0.15))
FPAW_C = np.array((0.23, -0.31, 0.085))
HIP_L = np.array((0.25, 0.40, 0.52))
ANKLE_H = np.array((0.26, 0.43, 0.15))
HFOOT_C = np.array((0.26, 0.38, 0.085))
BELL_C = np.array((-0.06, -0.63, 0.585))
BELL_LOOP = np.array((-0.06, -0.565, 0.685))
COIN_C = np.array((0.20, -0.62, 0.52))
COIN_W = unit((0.12, -1.0, 0.10))                       # coin face normal (front)
COIN_V = unit(np.array((0.0, 0.0, 1.0)) - COIN_W * COIN_W[2])
COIN_U = np.cross(COIN_V, COIN_W)
COIN_A, COIN_B, COIN_T = 0.13, 0.175, 0.026
COIN_PIVOT = COIN_C + COIN_V * (COIN_B + 0.05)
GLOW_RGB = (255, 196, 92)

FUSED = {}         # part -> (grid, named fields) for the painter's masks
FACE = {}          # eye / ear frames for the painter (head local frame)
PIVOT = {
    PRE + "Body": V(0.0, 0.10, 0.62),
    PRE + "Head": V(*(np.array((0.0, -0.06, 1.10)) + HEAD_OFF)),
    PRE + "FrontL": V(*SHOULDER_L),
    PRE + "FrontR": V(*(SHOULDER_L * np.array((-1, 1, 1)))),
    PRE + "HindL": V(*HIP_L),
    PRE + "HindR": V(*(HIP_L * np.array((-1, 1, 1)))),
    PRE + "Tail": V(0.0, 0.60, 0.74),
    PRE + "Bell": V(-0.06, -0.55, 0.71),
    PRE + "Coin": V(*COIN_PIVOT),
    PRE + "CoinRim_Glow": V(*COIN_PIVOT),
}
H_FINE_BODY, H_FINE_HEAD = 0.022, 0.020             # fine lattices only drive the painter's masks
H_BODY, H_HEAD, H_LIMB, H_HIND, H_TAIL, H_BELL = 0.105, 0.088, 0.066, 0.068, 0.066, 0.036


def body_field(h):
    G = Grid((-0.72, -0.90, 0.12), (0.72, 0.88, 1.14), h, sym_x=True)
    P = G.P
    X, Y, Z = P[..., 0], P[..., 1], P[..., 2]
    trunk = ell(P, (0, 0.12, 0.62), (0.40, 0.55, 0.36))
    neck = ell(P, (0, NECK_Y, 0.80), (0.28, 0.26, 0.24))
    chest = ell(P, (0, -0.32, 0.58), (0.30, 0.24, 0.24))
    base = smin(smin(trunk, neck, 0.20), chest, 0.14)
    f = np.clip(-(Y - NECK_Y) / NECK_RY, 0, 1)
    zc = ZC_COLLAR - 0.04 * f                                          # collar droops a little at the front
    rho = np.sqrt((X / NECK_RX) ** 2 + ((Y - NECK_Y) / NECK_RY) ** 2)
    qx = np.abs((rho - 1.0) * 0.27) - 0.03
    qz = np.abs(Z - zc) - 0.045
    collar = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qz, 0) ** 2) + np.minimum(np.maximum(qx, qz), 0) - 0.03
    F = smin(base, collar, 0.03)
    if h < 0.05:
        F = blur(F, 1)
    return G, F, dict(collar=collar)


def ear_frame(s):
    B = np.array((s * 0.36, -0.04, 1.90))
    w = unit((s * 0.30, -1.0, 0.05))
    v0 = unit((s * 0.30, 0.05, 1.0))
    v = unit(v0 - w * (v0 @ w))
    u = np.cross(v, w)
    return dict(B=B, u=u, v=v, w=w)


def ear_sd(P, e):
    q = P - e["B"]
    pu, pv, pw = q @ e["u"], q @ e["v"], q @ e["w"]
    d2 = sd_tri(pu, pv, *EAR_TRI)
    tw = np.abs(pw) - 0.05
    return np.sqrt(np.maximum(d2, 0) ** 2 + np.maximum(tw, 0) ** 2) + np.minimum(np.maximum(d2, tw), 0) - 0.06


def head_field(h, store):
    """Head in its LOCAL frame (the mesh is moved by HEAD_OFF afterwards)."""
    frames = {}
    G = Grid((-0.95, -0.95, 0.98), (0.95, 0.62, 2.45), h, sym_x=True)
    P = G.P
    skull = ell(P, HEAD_C, HEAD_R)
    for s in (1, -1):
        skull = smin(skull, ell(P, (s * 0.44, -0.24, 1.42), (0.26, 0.26, 0.20)), 0.16)      # chubby jowls
    skull = smin(skull, ell(P, (0, -0.36, 1.33), (0.30, 0.20, 0.14)), 0.10)                 # soft chin
    for name, s in (("eyeL", 1), ("eyeR", -1)):
        p, n = surf_point(G, skull, s * 0.27, 1.70)
        R = track_axes(n)
        u, v = R[0].copy(), R[1].copy()
        if u[0] < 0:
            u = -u
        if v[2] < 0:
            v = -v
        frames[name] = dict(c=p, u=u, v=v, n=n, r=(0.140, 0.165))
    muzzle = np.minimum(ell(P, (0.085, -0.585, 1.455), (0.12, 0.085, 0.085)),
                        ell(P, (-0.085, -0.585, 1.455), (0.12, 0.085, 0.085)))
    F = smin(skull, muzzle, 0.07)                      # whisker pads flow out of the face
    ears = None
    for name, s in (("earL", 1), ("earR", -1)):
        e = ear_frame(s)
        frames[name] = e
        d = ear_sd(P, e)
        ears = d if ears is None else np.minimum(ears, d)
    F = smin(F, ears, 0.08)
    if h < 0.05:
        F = blur(F, 1)
    if store:
        FACE.update(frames)
    return G, F, dict(skull=skull, muzzle=muzzle, ears=ears)


def build_front_leg(h):
    """Left front leg (+X): short chunky column from the shoulder to a round paw (the right one is its mirror)."""
    G = Grid((-0.05, -0.62, -0.10), (0.50, 0.05, 0.78), h)
    P = G.P
    root = ell(P, SHOULDER_L, (0.17, 0.17, 0.17))
    seg = capsule(P, SHOULDER_L, ANKLE_F, 0.172, 0.152)
    paw = ell(P, FPAW_C, (0.168, 0.200, 0.105))
    F = smin(smin(root, seg, 0.06), paw, 0.08)
    F = smax(F, -P[..., 2], 0.02)
    return extract(G, F, "frontL")


def build_hind(h):
    """Left hind leg (+X): rounded haunch on the side of the rump, short leg, round paw."""
    G = Grid((-0.02, 0.02, -0.10), (0.58, 0.82, 0.82), h)
    P = G.P
    thigh = ell(P, (0.27, 0.44, 0.47), (0.17, 0.23, 0.23))
    seg = capsule(P, (0.27, 0.44, 0.40), ANKLE_H, 0.168, 0.150)
    paw = ell(P, HFOOT_C, (0.165, 0.200, 0.105))
    F = smin(smin(thigh, seg, 0.08), paw, 0.08)
    F = smax(F, -P[..., 2], 0.02)
    return extract(G, F, "hindL")


def build_tail():
    """Short, thick, upright tail."""
    G = Grid((-0.30, 0.38, 0.45), (0.30, 1.02, 1.42), H_TAIL, sym_x=True)
    P = G.P
    a = ell(P, (0, 0.64, 0.76), (0.14, 0.14, 0.14))
    b = ell(P, (0, 0.73, 0.95), (0.13, 0.13, 0.13))
    c = ell(P, (0, 0.75, 1.13), (0.12, 0.12, 0.12))
    F = smin(smin(a, b, 0.10), c, 0.10)
    return extract(G, F, "tail")


def build_bell():
    G = Grid((-0.22, -0.78, 0.44), (0.10, -0.48, 0.77), H_BELL)
    P = G.P
    F = ell(P, BELL_C, (0.105, 0.100, 0.100))
    F = smin(F, ell(P, BELL_LOOP, (0.030, 0.026, 0.034)), 0.012)
    return extract(G, F, "bell")


def build_coin():
    """Koban: low-poly oval coin with bevelled faces, slight front dome, eyelet at the top."""
    N = 20
    vs, fs = [], []
    vs.append(COIN_C - COIN_W * COIN_T * 1.1)
    rings = [(0.70, -COIN_T), (0.96, -COIN_T), (1.0, 0.0), (0.96, COIN_T), (0.70, COIN_T * 1.15)]
    for sc, w in rings:
        for i in range(N):
            th = 2 * math.pi * i / N
            vs.append(COIN_C + sc * (COIN_A * math.cos(th) * COIN_U + COIN_B * math.sin(th) * COIN_V) + COIN_W * w)
    vs.append(COIN_C + COIN_W * COIN_T * 1.6)
    for i in range(N):
        fs.append((0, 1 + (i + 1) % N, 1 + i))
    for r in range(len(rings) - 1):
        a0, b0 = 1 + r * N, 1 + (r + 1) * N
        for i in range(N):
            j = (i + 1) % N
            fs.append((a0 + i, a0 + j, b0 + j, b0 + i))
    last, top = 1 + (len(rings) - 1) * N, len(vs) - 1
    for i in range(N):
        fs.append((last + i, last + (i + 1) % N, top))
    # eyelet: small ring in the coin plane at the top
    E = COIN_C + COIN_V * (COIN_B + 0.022)
    base = len(vs)
    M, K, R0, r0 = 8, 4, 0.028, 0.011
    for i in range(M):
        th = 2 * math.pi * i / M
        rad = math.cos(th) * COIN_U + math.sin(th) * COIN_V
        for k in range(K):
            ph = 2 * math.pi * k / K
            vs.append(E + rad * (R0 + r0 * math.cos(ph)) + COIN_W * r0 * math.sin(ph))
    for i in range(M):
        for k in range(K):
            a, b = base + i * K + k, base + ((i + 1) % M) * K + k
            c, d = base + ((i + 1) % M) * K + (k + 1) % K, base + i * K + (k + 1) % K
            fs.append((a, b, c, d))
    return np.array(vs), fs


def build_rim():
    """Thin oval tube wrapping the coin edge: the Neon glow part."""
    N, M, R = 24, 6, 0.029
    vs, fs = [], []
    for i in range(N):
        th = 2 * math.pi * i / N
        e = COIN_C + COIN_A * math.cos(th) * COIN_U + COIN_B * math.sin(th) * COIN_V
        nn = unit(math.cos(th) / COIN_A * COIN_U + math.sin(th) / COIN_B * COIN_V)
        for k in range(M):
            ph = 2 * math.pi * k / M
            vs.append(e + R * (math.cos(ph) * nn + math.sin(ph) * COIN_W))
    for i in range(N):
        for k in range(M):
            a, b = i * M + k, ((i + 1) % N) * M + k
            c, d = ((i + 1) % N) * M + (k + 1) % M, i * M + (k + 1) % M
            fs.append((a, b, c, d))
    return np.array(vs), fs


def mirror(vf):
    vs, fs = vf
    return vs * np.array((-1.0, 1.0, 1.0)), [tuple(reversed(f)) for f in fs]


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


CREAM, CREAM_SH, CREAM_LT = rgb(252, 245, 232), rgb(240, 214, 190), rgb(255, 251, 242)
OR_DK, OR, OR_LT = rgb(198, 98, 42), rgb(236, 142, 62), rgb(250, 186, 112)
CH_DK, CH, CH_LT = rgb(44, 38, 42), rgb(70, 62, 64), rgb(116, 104, 100)
PINK, PINK_DK, BLUSH = rgb(244, 164, 172), rgb(212, 116, 132), rgb(255, 160, 160)
RED, RED_DK, RED_LT = rgb(196, 46, 50), rgb(130, 26, 38), rgb(232, 96, 86)
GOLD, GOLD_DK, GOLD_LT = rgb(238, 182, 64), rgb(170, 110, 30), rgb(255, 230, 150)
KOBAN, KOBAN_DK, KOBAN_LT = rgb(232, 156, 36), rgb(146, 80, 16), rgb(255, 204, 92)
EYE_DARK, EYE_IRIS, EYE_IRIS_LT, EYE_LINE = rgb(22, 22, 28), rgb(64, 140, 84), rgb(150, 214, 108), rgb(14, 12, 16)
WHISK, MOUTH = rgb(92, 72, 70), rgb(86, 44, 46)
SH_TINT = np.array((1.04, 0.86, 0.75))          # warm shadows
TAU = 2 * math.pi

BODY_PATCHES = [("or", (0.30, 0.32, 0.86), (0.32, 0.40, 0.30), 51),
                ("ch", (-0.32, 0.16, 0.76), (0.28, 0.32, 0.28), 52),
                ("or", (0.0, 0.72, 0.95), (0.22, 0.22, 0.26), 53),
                ("ch", (0.0, 0.75, 1.24), (0.20, 0.20, 0.16), 54)]
HEAD_PATCHES = [("or", (0.40, -0.02, 2.06), (0.34, 0.42, 0.32), 41),
                ("ch", (-0.44, 0.02, 2.16), (0.24, 0.32, 0.24), 42)]


def bands(p, fx, fz, seed, cy=0.0):
    """Broad painterly brush bands: (dark, light) masks from anisotropic noise, three value ranges."""
    az_ = np.arctan2(p[:, 0], -(p[:, 1] - cy))
    q = np.stack([np.cos(az_) * fx, np.sin(az_) * fx, p[:, 2] * fz], 1)
    s_ = vnoise(q, 1.0, seed)
    return 1.0 - sstep(0.38, 0.46, s_), sstep(0.60, 0.68, s_)


def sample(part, name, p):
    G, fl = FUSED[part]
    return G.sample(fl[name], p)


def fur(p, n, seed, zlo, zhi, cy=0.0):
    nz = vnoise(p * np.array((1.0, 1.0, 0.5)), 7.0, seed)
    c = mix(CREAM_SH, CREAM, sstep(zlo, zhi, p[:, 2]))
    c = mix(c, CREAM_LT, 0.30 * sstep(0.3, 0.9, n[:, 2]))
    sd_, sl_ = bands(p, 2.0, 1.6, seed + 20, cy)
    c = mix(c, CREAM_SH, 0.32 * sd_)
    c = mix(c, CREAM_LT, 0.26 * sl_)
    return mix(c, CREAM_SH, 0.05 * (nz - 0.5) * 2 + 0.02)


def calico(c, p, n, patches):
    for kind, ctr, rad, seed in patches:
        d = np.linalg.norm((p - np.array(ctr)) / np.array(rad), axis=1) + 0.38 * (vnoise(p, 3.2, seed) - 0.5)
        m = sstep(1.0, 0.86, d)
        if not m.any():
            continue
        sd_, sl_ = bands(p, 2.4, 2.4, seed + 7)
        if kind == "or":
            pc = mix(OR_DK, OR, sstep(-0.4, 0.6, n[:, 2] + 0.3))
            pc = mix(mix(pc, OR_DK, 0.35 * sd_), OR_LT, 0.35 * sl_)
        else:
            pc = mix(CH_DK, CH, sstep(-0.4, 0.6, n[:, 2] + 0.3))
            pc = mix(mix(pc, CH_DK, 0.30 * sd_), CH_LT, 0.35 * sl_)
        c = mix(c, pc, m)
    return c


def toe_grooves(c, p, n, pc, s):
    X, Y, Z = p[:, 0], p[:, 1], p[:, 2]
    for k in (-1, 1):
        g = (sstep(0.011, 0.004, np.abs(X - (pc[0] + s * k * 0.045))) * sstep(pc[1] - 0.06, pc[1] - 0.12, Y)
             * sstep(0.05, 0.10, Z) * sstep(-0.2, 0.2, n[:, 2] - n[:, 1] * 0.5))
        c = mix(c, CREAM_SH * np.array((0.82, 0.74, 0.72)), 0.85 * g)
    return c


def paint_body(p, n):
    X, Y, Z = p[:, 0], p[:, 1], p[:, 2]
    c = fur(p, n, 11, 0.0, 1.0)
    c = calico(c, p, n, BODY_PATCHES)
    dcol = sample("body", "collar", p)
    cm = sstep(0.030, -0.008, dcol)
    f = np.clip(-(Y - NECK_Y) / NECK_RY, 0, 1)
    dz = Z - (ZC_COLLAR - 0.04 * f)
    rc = mix(RED_DK, RED, sstep(-0.07, -0.01, dz))
    rc = mix(rc, RED_LT, 0.45 * sstep(0.0, 0.05, dz) * sstep(-0.1, 0.6, n[:, 2]))
    rc = mix(rc, RED_DK * 0.85, 0.65 * sstep(0.045, 0.062, np.abs(dz)))
    stitch = (((np.arctan2(Y - NECK_Y, X) * 180 / math.pi) / 7.0) % 1.0 < 0.5) & (np.abs(dz) < 0.008)
    rc[stitch] = mix(rc[stitch], rgb(250, 214, 150), 0.7)
    c = mix(c, rc, cm)
    return c, cm > 0.5


def paint_head(p, n, eyes_out):
    p = p - HEAD_OFF                       # head paint is defined in the head's local frame
    X, Y, Z = p[:, 0], p[:, 1], p[:, 2]
    c = fur(p, n, 31, 1.10, 2.0, -0.10)
    c = calico(c, p, n, HEAD_PATCHES)
    dm = sample("head", "muzzle", p)
    c = mix(c, CREAM_LT, 0.55 * sstep(0.05, -0.01, dm))
    ds = sample("head", "skull", p)
    for name in ("earL", "earR"):
        e = FACE[name]
        q = p - e["B"]
        pu, pv, pw = q @ e["u"], q @ e["v"], q @ e["w"]
        t2 = sd_tri(pu, pv, *EAR_TRI)
        k = (sstep(0.0, -0.04, t2) * sstep(0.10, 0.35, n @ e["w"]) * sstep(-0.01, 0.02, pw) * sstep(0.015, 0.05, ds))
        pk = mix(PINK_DK, PINK, sstep(-0.02, 0.18, pv))
        c = mix(c, pk, k)
    front = sstep(-0.15, -0.45, n[:, 1]) * sstep(-0.25, -0.40, Y)
    for s in (1, -1):
        bd = np.sqrt(((X - s * 0.43) / 0.10) ** 2 + ((Z - 1.535) / 0.05) ** 2)
        c = mix(c, BLUSH, 0.50 * sstep(1.0, 0.2, bd) * front)
    xs = np.abs(X)
    for z0, sl in ((1.478, 0.20), (1.448, 0.0), (1.418, -0.20)):            # painted whisker lines
        zl = z0 + sl * (xs - 0.23)
        along = sstep(0.215, 0.245, xs) * sstep(0.52, 0.45, xs)
        th = 0.0085 * (1 - 0.5 * sstep(0.30, 0.50, xs))
        w = sstep(th, th * 0.35, np.abs(Z - zl)) * along * sstep(0.1, -0.3, n[:, 1]) * (Y < -0.15)
        c = mix(c, WHISK, 0.85 * w)
    for s in (1, -1):                                                         # whisker dots
        for dx, dz_ in ((0.105, 1.478), (0.145, 1.462), (0.122, 1.437)):
            dd = np.sqrt((X - s * dx) ** 2 + (Z - dz_) ** 2)
            c = mix(c, WHISK, 0.85 * sstep(0.013, 0.008, dd) * front)
    nz_t, nz_b = 1.548, 1.502                                                 # small pink nose
    tt = np.clip((Z - nz_b) / (nz_t - nz_b), 0, 1)
    hw = 0.014 + 0.046 * tt
    nose = (sstep(0.005, -0.004, xs - hw) * sstep(-0.004, 0.004, Z - nz_b) * sstep(0.004, -0.004, Z - nz_t) * front)
    nc = mix(PINK_DK, PINK, sstep(1.505, 1.540, Z))
    nc = mix(nc, rgb(255, 214, 214), 0.6 * sstep(0.020, 0.0, np.sqrt(X ** 2 + (Z - 1.536) ** 2)))
    c = mix(c, nc, nose)
    phil = sstep(0.0065, 0.003, xs) * sstep(nz_b + 0.002, nz_b - 0.004, Z) * sstep(1.474, 1.480, Z)
    arcs = np.zeros(len(p))
    for s in (1, -1):                                                         # the "w" mouth
        r = np.sqrt((X - s * 0.038) ** 2 + (Z - 1.482) ** 2)
        arcs = np.maximum(arcs, sstep(0.0075, 0.003, np.abs(r - 0.038)) * sstep(1.484, 1.478, Z))
    c = mix(c, MOUTH, 0.95 * np.maximum(phil, arcs) * front)
    for name in ("eyeL", "eyeR"):                                             # big glossy eyes
        e = FACE[name]
        d = p - e["c"]
        eu, ev = (d @ e["u"]) / e["r"][0], (d @ e["v"]) / e["r"][1]
        fr = (np.abs(d @ e["n"]) < 0.07) & (n @ e["n"] > 0.45)
        r = np.sqrt(eu * eu + ev * ev)
        ring = fr & (r >= 1.0) & (r < 1.5)
        c[ring] = mix(c[ring], c[ring] * np.array((0.93, 0.88, 0.88)), (0.22 * sstep(1.5, 1.0, r))[ring])
        line = fr & (r >= 0.97) & (r < 1.15)
        c[line] = mix(c[line], EYE_LINE, sstep(1.15, 1.05, r)[line])
        inside = fr & (r < 1.0)
        ce = np.tile(EYE_DARK, (len(p), 1))
        iris = sstep(0.30, 0.85, r) * sstep(0.35, -0.70, ev)
        ce = mix(ce, EYE_IRIS, 0.90 * iris)
        ce = mix(ce, EYE_IRIS_LT, 0.65 * sstep(-0.35, -0.80, ev) * sstep(0.30, 0.8, r))
        c[inside] = ce[inside]
        eyes_out.append((inside, eu, ev))
    return c, nose > 0.5


def paint_limb(p, n, pid):
    c = fur(p, n, 60 + pid, 0.0, 1.2)
    c = calico(c, p, n, BODY_PATCHES)
    if pid in (P_FRONTL, P_FRONTR, P_HINDL, P_HINDR):
        s = 1 if pid in (P_FRONTL, P_HINDL) else -1
        pc = (FPAW_C if pid in (P_FRONTL, P_FRONTR) else HFOOT_C) * np.array((s, 1, 1))
        c = toe_grooves(c, p, n, pc, s)
        du, dv = p[:, 0] - pc[0], p[:, 1] - pc[1]
        sole = sstep(-0.30, -0.65, n[:, 2]) * sstep(0.045, 0.02, p[:, 2])
        beans = sstep(1.0, 0.80, np.sqrt((du / 0.064) ** 2 + ((dv - 0.034) / 0.050) ** 2))
        for bu, bv in ((-0.068, -0.034), (-0.025, -0.074), (0.025, -0.074), (0.068, -0.034)):
            beans = np.maximum(beans, sstep(1.0, 0.75, np.sqrt(((du - bu) / 0.029) ** 2 + ((dv - bv) / 0.029) ** 2)))
        c = mix(c, mix(PINK_DK, PINK, 0.6), beans * sole)
        return c, beans * sole > 0.5
    return c, np.zeros(len(p), bool)


def paint_bell(p, n):
    q = p - BELL_C
    c = mix(GOLD_DK, GOLD, sstep(-0.5, 0.7, n[:, 2] * 0.7 - n[:, 1] * 0.3))
    c = mix(c, GOLD_LT, 0.55 * sstep(0.55, 0.95, n @ unit((-0.5, -0.62, 0.62))))
    for z0 in (0.020, -0.004):
        c = mix(c, GOLD_DK * 0.78, 0.8 * sstep(0.0075, 0.003, np.abs(q[:, 2] - z0)))
    slit = sstep(0.011, 0.005, np.abs(q[:, 0])) * sstep(-0.03, -0.045, q[:, 2]) * (q[:, 1] < -0.02)
    hole = sstep(0.024, 0.016, np.sqrt(q[:, 0] ** 2 + (q[:, 2] + 0.035) ** 2)) * (q[:, 1] < -0.02)
    c = mix(c, rgb(64, 38, 22), np.maximum(slit, hole))
    c = mix(c, GOLD_DK, 0.5 * sstep(0.075, 0.09, q[:, 2]))
    return c


def paint_coin(p, n):
    d = p - COIN_C
    du, dv, dw = d @ COIN_U / COIN_A, d @ COIN_V / COIN_B, d @ COIN_W
    r = np.sqrt(du * du + dv * dv)
    c = mix(KOBAN_DK, KOBAN, sstep(-0.5, 0.7, n @ COIN_V * 0.4 + n @ COIN_W * 0.7))
    face = sstep(0.35 * COIN_T, 0.75 * COIN_T, dw) * sstep(0.95, 0.86, r)
    fc = mix(KOBAN, KOBAN_LT, 0.45 * sstep(-0.6, 0.9, -du * 0.5 + dv * 0.6))
    fc = mix(fc, KOBAN_DK, 0.60 * sstep(0.78, 0.92, r))                       # darker gold edge band
    ph = dv * COIN_B / 0.036                                                  # a few horizontal ridges
    ridge = sstep(0.17, 0.07, np.abs(ph % 1.0 - 0.5)) * sstep(0.46, 0.40, np.abs(dv)) * sstep(0.80, 0.68, np.abs(du))
    fc = mix(fc, KOBAN_DK * 0.85, 0.80 * ridge)
    for sv in (0.66, -0.66):                                                  # two stamped seals
        rs = np.sqrt((du / 0.34) ** 2 + ((dv - sv) / 0.17) ** 2)
        fc = mix(fc, KOBAN_DK * 0.85, 0.60 * sstep(0.95, 0.80, rs))
        fc = mix(fc, KOBAN_DK * 0.6, 0.90 * sstep(1.05, 0.95, rs) * sstep(0.80, 0.92, rs))
        fc = mix(fc, KOBAN_LT, 0.70 * sstep(0.40, 0.22, rs))
    c = mix(c, fc, face)
    c = mix(c, KOBAN_DK, 0.6 * sstep(1.0, 1.15, dv))                    # eyelet
    return c


def paint_all(P, Ns, part):
    col = np.zeros((len(P), 3))
    hard = np.zeros(len(P), bool)
    eyes = []
    for pid in range(1, 10):
        m = part == pid
        if not m.any():
            continue
        p, n = P[m], Ns[m]
        ex = []
        if pid == P_BODY:
            c, h = paint_body(p, n)
        elif pid == P_HEAD:
            c, h = paint_head(p, n, ex)
        elif pid == P_BELL:
            c, h = paint_bell(p, n), np.ones(len(p), bool)
        elif pid == P_COIN:
            c, h = paint_coin(p, n), np.ones(len(p), bool)
        else:
            c, h = paint_limb(p, n, pid)
        col[m], hard[m] = c, h
        for inside, eu, ev in ex:
            fi, feu, fev = np.zeros(len(P), bool), np.zeros(len(P)), np.zeros(len(P))
            fi[m], feu[m], fev[m] = inside, eu, ev
            eyes.append((fi, feu, fev))
    return col, hard, eyes


def light(col, P, Ns, Nf, hard, ao_s, ao_l, edge, part_ids):
    Lk = unit((-0.50, -0.62, 0.62))
    Lr = unit((0.70, 0.62, 0.35))
    kf, ks = np.clip(Nf @ Lk, 0, 1), np.clip(Ns @ Lk, 0, 1)
    k = np.clip(ks + np.where(hard, 1.2, 1.25) * (kf - ks), 0.0, 1.0)     # visible soft faceting
    sky = 0.5 + 0.5 * Ns[:, 2]
    lightv = 0.70 + 0.34 * k + 0.10 * sky
    head = part_ids == P_HEAD
    ao_w = np.where(head, 0.20, 0.32)
    aol_w = np.where(head, 0.08, 0.18)
    aof = (1.0 - ao_w + ao_w * sstep(0.12, 1.0, ao_s)) * (1.0 - aol_w * (1.0 - sstep(0.2, 1.0, ao_l)))
    shade = lightv * aof * (0.90 + 0.12 * sstep(0.0, 2.3, P[:, 2]))
    lit = col * shade[:, None]
    peach = col * np.array((0.97, 0.80, 0.68)) * (0.80 + 0.25 * shade)[:, None]      # warm peach shadows
    lit = mix(lit, peach, 0.90 * sstep(0.94, 0.62, shade))                 # warm shadows, never grey
    lit = lit + (sstep(0.3, 1.0, Ns @ Lr) * 0.10)[:, None] * np.array((0.55, 0.70, 1.0))   # cool rim
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
mat = bpy.data.materials.new("LuckyCat_Atlas")
mat.use_nodes = True
glow_mat = bpy.data.materials.new("LuckyCat_Glow")
glow_mat.use_nodes = True
_gl = tuple(((c / 255.0 + 0.055) / 1.055) ** 2.4 for c in GLOW_RGB) + (1.0,)
_bs = glow_mat.node_tree.nodes["Principled BSDF"]
_bs.inputs["Base Color"].default_value = _gl
_bs.inputs["Emission Color"].default_value = _gl
_bs.inputs["Emission Strength"].default_value = 7.0


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
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
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
body_vf = extract(Gc, Fc, "body")
Gc, Fc, _ = head_field(H_HEAD, False)
head_vf = extract(Gc, Fc, "head")
head_vf = (head_vf[0] + HEAD_OFF, head_vf[1])
del Gc, Fc
hind_l = build_hind(H_HIND)
front_l = build_front_leg(H_LIMB)
specs = [(PRE + "Body", P_BODY, body_vf), (PRE + "Head", P_HEAD, head_vf),
         (PRE + "FrontL", P_FRONTL, front_l), (PRE + "FrontR", P_FRONTR, mirror(front_l)),
         (PRE + "HindL", P_HINDL, hind_l), (PRE + "HindR", P_HINDR, mirror(hind_l)),
         (PRE + "Tail", P_TAIL, build_tail()), (PRE + "Bell", P_BELL, build_bell()),
         (PRE + "Coin", P_COIN, build_coin())]
objs = [make_object(n, pid, vf, mat) for n, pid, vf in specs]
glow = make_object(PRE + "CoinRim_Glow", P_GLOW, build_rim(), glow_mat)
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

# glow rim UVs: simple planar projection inside 0-1 (it is a flat Neon colour, no texture)
gme = glow.data
guv = gme.uv_layers.new(name="UVMap")
gco = np.array([v.co[:] for v in gme.vertices])
gu, gv = gco @ COIN_U, gco @ COIN_V
gu, gv = (gu - gu.min()) / np.ptp(gu), (gv - gv.min()) / np.ptp(gv)
for li, lp in enumerate(gme.loops):
    guv.data[li].uv = (0.02 + 0.96 * gu[lp.vertex_index], 0.02 + 0.96 * gv[lp.vertex_index])

if SHAPE:
    for o in objs:
        me = o.data
        mw = o.matrix_world
        Pv = np.array([(mw @ v.co)[:] for v in me.vertices])
        Nv = np.array([(mw.to_3x3() @ v.normal)[:] for v in me.vertices])
        Nv /= np.maximum(np.linalg.norm(Nv, axis=1), 1e-9)[:, None]
        col, hard, eyes = paint_all(Pv, Nv, np.full(len(Pv), o.pass_index))
        sh = 0.70 + 0.30 * np.clip(Nv @ unit((-0.5, -0.62, 0.62)), 0, 1)
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
        cw = mw @ poly.center
        c = cw - V(*HEAD_OFF)
        nrm = poly.normal
        radial = V(c.x - FACE_AXIS[0], c.y - FACE_AXIS[1], 0.0)
        if radial.length < 1e-6:
            continue
        radial.normalize()
        ang = math.atan2(c.x - FACE_AXIS[0], -(c.y - FACE_AXIS[1]))
        if not (nrm.dot(radial) > 0.35 and nrm.y < -0.1 and abs(ang) < 1.25 and 1.28 < c.z < 1.95):
            continue
        if htree.ray_cast(cw + nrm * 0.002, nrm, 1.0)[0] is not None:
            continue
        n_face += 1
        for li in poly.loop_indices:
            co = mw @ hm.vertices[hm.loops[li].vertex_index].co - V(*HEAD_OFF)
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
            a1.inputs["Distance"].default_value = 0.12
            a2 = N_("ShaderNodeAmbientOcclusion")
            a2.samples = 16
            a2.inputs["Distance"].default_value = 0.6
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

    def nunit(a):
        return a / np.maximum(np.linalg.norm(a, axis=1), 1e-6)[:, None]

    P = dec(maps["pos"], 0.125)
    Ns, Nf, Nb = nunit(dec(maps["nrm"], 0.5)), nunit(dec(maps["fnrm"], 0.5)), nunit(dec(maps["bev"], 0.5))
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
    full[~cov, :3] = CREAM_SH
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
JOINT_PARENT = {PRE + "Body": None, PRE + "Head": PRE + "Body", PRE + "FrontL": PRE + "Body",
                PRE + "FrontR": PRE + "Body", PRE + "HindL": PRE + "Body", PRE + "HindR": PRE + "Body",
                PRE + "Tail": PRE + "Body", PRE + "Bell": PRE + "Body", PRE + "Coin": PRE + "Body",
                PRE + "CoinRim_Glow": PRE + "Coin"}
JOINT_NAME = {PRE + "Body": "root (body centre)", PRE + "Head": "neck, hidden inside the head and collar",
              PRE + "FrontL": "left shoulder", PRE + "FrontR": "right shoulder (also the beckon emote paw)",
              PRE + "HindL": "left hip", PRE + "HindR": "right hip", PRE + "Tail": "tail root",
              PRE + "Bell": "bell loop on the collar", PRE + "Coin": "coin eyelet on the collar",
              PRE + "CoinRim_Glow": "same as the coin pivot (rigid weld to the coin)"}
MOTION = {
    PRE + "Body": "root part: walk bob in Studio Y and a small roll about Studio Z",
    PRE + "Head": "nod = pitch about Studio X, tilt = roll about Studio Z, look = yaw about Studio Y, through the neck",
    PRE + "FrontL": "step = swing about Studio X through the shoulder (positive Studio X = paw reaches forward)",
    PRE + "FrontR": "step = swing about Studio X through the shoulder; beckon emote = lift to Studio X +145 with a Studio Z -38 outward roll, wave between +115 and +145",
    PRE + "HindL": "step = swing about Studio X through the hip",
    PRE + "HindR": "step = swing about Studio X through the hip",
    PRE + "Tail": "swish = yaw about Studio Y through the tail root; perk = pitch about Studio X",
    PRE + "Bell": "dangle: small lagging swing about Studio X",
    PRE + "Coin": "dangle like the bell, slightly out of phase",
    PRE + "CoinRim_Glow": "none: WeldConstraint to LuckyCat_Coin",
}


def studio(v):
    return [round(-v[0], 4) + 0.0, round(v[2], 4) + 0.0, round(v[1], 4) + 0.0]


def studio_size(v):
    return [round(v[0], 4), round(v[2], 4), round(v[1], 4)]


def studio_ang(b):
    """Blender preview-bone euler (x, y, z) degrees -> Studio CFrame.Angles degrees about Studio (X, Y, Z).
    Bone X = world X (Studio -X), bone Y = world Z (Studio +Y), bone Z = world -Y (Studio -Z)."""
    return [round(-b[0], 1) + 0.0, round(b[1], 1) + 0.0, round(-b[2], 1) + 0.0]


def world_bounds(o):
    ws = [o.matrix_world @ vv.co for vv in o.data.vertices]
    return (Vector([min(w[k] for w in ws) for k in range(3)]), Vector([max(w[k] for w in ws) for k in range(3)]))


report = {"asset": STEM, "blender_version": bpy.app.version_string,
          "authoring": "final Roblox stud size (1 Blender unit = 1 stud); import at 1:1, do not scale",
          "axes": "Blender Z-up, front -Y, the cat's left +X; standing on z = 0 (rest pose = standing, walk-ready)",
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
log("overall (w, len, h)", tuple(round(v, 3) for v in (size.x, size.y, size.z)), "tris", report["total_triangles"])

if not QUICK:
    (ROOT / "polygon-report.json").write_text(json.dumps(report, indent=2))
    allp = objs + [glow]
    select_only(allp, parts[PRE + "Body"])
    bpy.ops.export_scene.gltf(filepath=str(GLB_PATH), export_format="GLB", use_selection=True, export_apply=True)
    select_only(allp, parts[PRE + "Body"])
    bpy.ops.export_scene.fbx(filepath=str(FBX_PATH), use_selection=True, object_types={"MESH"},
                             axis_forward="-Z", axis_up="Y", path_mode="COPY", embed_textures=True,
                             add_leaf_bones=False)
    log("exported", FBX_PATH.name, GLB_PATH.name)

# =============================================================================================
# armature (Blender only, for posing previews; exports are the plain rigid parts)
# =============================================================================================
arm_data = bpy.data.armatures.new("LuckyCat_Rig")
arm = bpy.data.objects.new("LuckyCat_Rig", arm_data)
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
    o.parent_bone = "Coin" if name.endswith("_Glow") else name.replace(PRE, "")
    bpy.context.view_layer.update()
    o.matrix_world = mwo
bpy.context.view_layer.update()
log("armature built; max pivot drift", round(max((parts[n].matrix_world.translation - PIVOT[n]).length for n in parts), 6))
VCO = {n: np.array([v.co[:] for v in o.data.vertices]) for n, o in parts.items()}


def lowest_z():
    zs = []
    for n, o in parts.items():
        M = np.array(o.matrix_world)
        zs.append(float(np.min(VCO[n] @ M[2, :3] + M[2, 3])))
    return min(zs)


def pose(rots, ground=False):
    """rots: {bone: (x, y, z) degrees}. Bone axes: X = world X (pitch / swing), Y = world Z (yaw),
    Z = world -Y (roll about the front-back axis). ground=True lifts the body so the lowest point sits on z = 0."""
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = [math.radians(v) for v in rots.get(pb.name, (0, 0, 0))]
        pb.location = (0, 0, 0)
    bpy.context.view_layer.update()
    up = 0.0
    if ground:
        up = -lowest_z()
        arm.pose.bones["Body"].location = (0, up, 0)
        bpy.context.view_layer.update()
    return round(up, 4)


WALK_A = {"Body": (0, 0, 3), "Head": (-3, 0, -3), "FrontL": (-22, 0, 0), "HindR": (-20, 0, 0),
          "FrontR": (18, 0, 0), "HindL": (16, 0, 0), "Tail": (-6, 12, 0), "Bell": (6, 0, 0), "Coin": (4, 0, 0)}
WALK_B = {"Body": (0, 0, -3), "Head": (-3, 0, 3), "FrontR": (-22, 0, 0), "HindL": (-20, 0, 0),
          "FrontL": (18, 0, 0), "HindR": (16, 0, 0), "Tail": (-6, -12, 0), "Bell": (-6, 0, 0), "Coin": (-4, 0, 0)}
BECKON_UP = {"FrontR": (-145, 0, 38), "Head": (-6, 0, -8), "Tail": (-8, 10, 0)}
BECKON_DOWN = {"FrontR": (-115, 0, 38), "Head": (-4, 0, -6), "Tail": (-8, -6, 0)}
HEAD_TILT = {"Head": (0, 25, 20)}
TAIL_SWISH = {"Tail": (0, 28, 0)}
up_a, up_b = pose(WALK_A, True), pose(WALK_B, True)
up_u, up_d = pose(BECKON_UP, True), pose(BECKON_DOWN, True)
pose({})
log("ground offsets walk A/B, beckon up/down", up_a, up_b, up_u, up_d)


def frame(rots, up=0.0):
    out = {"body_offset_studs": [0.0, up, 0.0]}
    out["studio_angles_deg"] = {PRE + k: studio_ang(v) for k, v in rots.items()}
    out["blender_bone_angles_deg"] = {PRE + k: list(v) for k, v in rots.items()}
    return out


body_pivot = PIVOT[PRE + "Body"].copy()
install = {
    "asset": STEM, "rarity": "Epic", "strong_suit": "Luck (+Luck: the run shop rolls better tiers more often)",
    "axis": "studio = (-x, z, y) of blender; Blender front -Y = Studio front -Z",
    "units": "studs; the model is at final size, import 1:1 and do not scale",
    "sides": "L/R are the cat's own left/right; its left is Blender +X = Studio -X. The beckon emote uses the RIGHT front paw",
    "origin": "all positions are relative to the model origin = the ground point under the body (Blender world origin)",
    "rest_pose": "standing on all four legs (walk-ready chibi stance), tail up; pets are always moving, so this is the rest pose",
    "ground_point": studio((0.0, 0.0, 0.0)), "overall_size": studio_size(size),
    "overall_center": studio((lo_all + hi_all) / 2), "texture": f"textures/{TEX_PATH.name}",
    "texture_note": "one shared atlas on every MeshPart via MeshPart.TextureID, except LuckyCat_CoinRim_Glow",
    "glow_parts": {PRE + "CoinRim_Glow": {
        "Material": "Neon", "Color": list(GLOW_RGB), "Transparency": 0, "TextureID": "none",
        "weld": "WeldConstraint to LuckyCat_Coin (same pivot)",
        "note": "thin rim wrapping the koban edge; the coin itself is painted gold in the atlas (not Neon). Subtle on purpose: only the rim glows"}},
    "rest_rotation": "every part has identity rotation relative to the model at rest",
    "rig": "one Motor6D per part (except the _Glow weld): Part0 = joint_parent, Part1 = the part, C0/C1 at the part's pivot",
    "angle_convention": "studio_angles_deg = CFrame.Angles(math.rad(x), math.rad(y), math.rad(z)) about the part's own pivot, "
                        "applied as Motor6D.Transform; blender_bone_angles_deg are the preview-rig values (X then Y then Z); "
                        "body_offset_studs is the root bob (Studio Y) that keeps the lowest paw on the ground",
    "parts": {}}
for name, o in parts.items():
    lo, hi = world_bounds(o)
    install["parts"][name] = {
        "center": studio((lo + hi) / 2), "size": studio_size(hi - lo), "pivot": studio(PIVOT[name]),
        "pivot_from_body_pivot": studio(PIVOT[name] - body_pivot), "pivot_is": JOINT_NAME[name],
        "joint_parent": JOINT_PARENT[name], "suggested_motion": MOTION[name]}
install["locomotion"] = "cat_walk"
install["locomotion_data"] = {
    "gait": "four-legged chibi cat walk in diagonal pairs (left front + right hind reach while right front + left hind "
            "push back, then swap), gentle body bob and roll, head steady, tail up with a small swish",
    "period_s": 0.5,
    "frames": [dict(t=0.0, name="step A (left front + right hind reach)", **frame(WALK_A, up_a)),
               dict(t=0.5, name="step B (right front + left hind reach)", **frame(WALK_B, up_b))],
    "interpolation": "sine ease A -> B -> A; pass through the rest pose (body offset 0) at t = 0.25 and 0.75, which gives the bob",
}
install["beckon_emote"] = {
    "note": "short emote (about 1.5 s, two or three waves), the cat stays standing: the right front paw lifts beside "
            "the cheek, palm (pink beans) forward, and waves at the shoulder; the head tilts slightly",
    "blend_in_s": 0.15, "wave_period_s": 0.5, "duration_s": 1.5,
    "frames": [dict(t=0.0, name="paw up", **frame(BECKON_UP, up_u)),
               dict(t=0.5, name="paw down (wave)", **frame(BECKON_DOWN, up_d))],
}
install["extras"] = {"head_tilt": frame(HEAD_TILT), "tail_swish": frame(TAIL_SWISH),
                     "timing": "while following: head tilt every 3-4 s, tail swish +/-28 deg on a slow 1.6 s sine"}
install["vfx"] = [
    {"name": "CoinSparkle", "kind": "ParticleEmitter (always on), soft gold sparkle around the coin",
     "part": PRE + "Coin", "attachment_position_from_part_pivot": studio(Vector(COIN_C) - Vector(COIN_PIVOT)),
     "position_model": studio(Vector(COIN_C)), "color": [255, 214, 120],
     "suggested": {"Texture": "a soft 4-point star sparkle (e.g. rbxasset://textures/particles/sparkles_main.dds)",
                   "Rate": 3, "Lifetime": [0.5, 0.9], "Size": "NumberSequence 0:0.10, 0.4:0.14, 1:0",
                   "Speed": [0.2, 0.5], "SpreadAngle": [180, 180], "Acceleration": [0, 0.4, 0], "Drag": 2,
                   "Rotation": [0, 360], "RotSpeed": [-90, 90], "LightEmission": 0.8, "LightInfluence": 0,
                   "Transparency": "NumberSequence 0:0.3, 0.7:0.5, 1:1", "ZOffset": 0.2, "LockedToPart": False}},
    {"name": "WalkSparkleTrail", "kind": "ParticleEmitter, faint gold sparkle trail; Enabled only while the pet moves",
     "part": PRE + "Body", "attachment_position_from_part_pivot": studio(Vector((0, 0.40, 0.05)) - body_pivot),
     "position_model": studio(Vector((0, 0.40, 0.05))), "color": [255, 226, 150],
     "suggested": {"Texture": "same sparkle as CoinSparkle", "Rate": 8, "Lifetime": [0.6, 1.0],
                   "Size": "NumberSequence 0:0.08, 1:0", "Speed": [0.05, 0.2], "SpreadAngle": [40, 40],
                   "EmissionDirection": "Top", "Acceleration": [0, 0.5, 0], "LightEmission": 0.6, "LightInfluence": 0,
                   "Transparency": "NumberSequence 0:0.45, 1:1", "LockedToPart": False,
                   "note": "LockedToPart false so the sparks stay behind as a trail; set Rate 0 when idle"}},
]

if not QUICK:
    (ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=2))
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


tgt = V(0, -0.12, 0.95)
ft = V(*(np.array((0.0, -0.50, 1.62)) + HEAD_OFF))
POSES = [
    ("Walk A (side): left front + right hind reach", WALK_A, up_a, around(tgt, (-1, -0.2, 0.12), 9.0), tgt),
    ("Walk B (3/4): right front + left hind reach", WALK_B, up_b, around(tgt, (0.8, -1, 0.25), 9.0), tgt),
    ("Beckon emote: paw up, beans forward", BECKON_UP, up_u, around(tgt, (-0.45, -1, 0.15), 9.0), tgt),
    ("Beckon emote: paw down (wave)", BECKON_DOWN, up_d, around(tgt, (-0.45, -1, 0.15), 9.0), tgt),
    ("Head tilt 20 + turn 25", HEAD_TILT, 0.0, around(ft, (0.25, -1, 0.15), 6.0), ft),
    ("Tail swish 28 (from behind)", TAIL_SWISH, 0.0, around(tgt, (0.7, 1, 0.35), 9.0), tgt),
]
THREEQ = (0.75, -0.9, 0.35)

if not NO_PREVIEWS and QUICK:
    r = (700, 700)
    shoot(OUT / "threeq.png", around(tgt, THREEQ, 9.0), tgt, res=r)
    shoot(OUT / "front.png", around(tgt, (0, -1, 0.1), 9.0), tgt, res=r)
    shoot(OUT / "side.png", around(tgt, (-1, 0, 0.1), 9.0), tgt, res=r)
    shoot(OUT / "face-closeup.png", around(ft, (0.3, -1, 0.12), 4.0), ft, res=r)
    if "--pose" in ARGS:
        for i in (0, 2):
            lab, rots, up, loc, t = POSES[i]
            pose(rots)
            if up:
                arm.pose.bones["Body"].location = (0, up, 0)
                bpy.context.view_layer.update()
            shoot(OUT / f"pose-quick{i}.png", loc, t, res=(600, 600))
        pose({})
elif not NO_PREVIEWS:
    shots = [(shoot(OUT / "threeq.png", around(tgt, THREEQ, 9.0), tgt), "Three-quarter (standing)"),
             (shoot(OUT / "front.png", around(tgt, (0, -1, 0.1), 9.0), tgt), "Front"),
             (shoot(OUT / "side.png", around(tgt, (-1, 0, 0.1), 9.0), tgt), "Side (cat's right)"),
             (shoot(OUT / "back.png", around(tgt, (0, 1, 0.25), 9.0), tgt), "Back")]
    face = shoot(OUT / "face-closeup.png", around(ft, (0.3, -1, 0.12), 4.0), ft, res=(1400, 1400))
    pose_items = []
    for i, (lab, rots, up, loc, t) in enumerate(POSES):
        pose(rots)
        if up:
            arm.pose.bones["Body"].location = (0, up, 0)
            bpy.context.view_layer.update()
        pose_items.append((shoot(OUT / f"_pose-{i}.png", loc, t, res=(900, 900)), lab))
    pose({})
    make_sheet(pose_items, 3, 450, OUT / "pose-check.png", "Lucky Cat: pose check through the joint pivots",
               "Each part rotates about its own pivot (Blender armature, preview only). Look for gaps at the shoulders, hips, neck and tail.")
    for pth, _ in pose_items:
        pth.unlink()
    make_sheet(shots + [(face, "Face close-up"), (OUT / "pose-check.png", "Pose check (walk, beckon, head, tail)")],
               3, 520, OUT / "sheet.png",
               f"Lucky Cat pet (Epic, Luck): {report['total_triangles']:,} tris, one 1024 atlas + Neon coin rim",
               "Blender 5.2 Eevee renders. Blender-verified, Studio untested.")
log("done")
