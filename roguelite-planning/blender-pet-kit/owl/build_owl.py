"""Owl pet (Epic, strong suit: bosses -- marks the toughest nearby enemy, your hits on it do +20%).

Self-contained generator for background Blender 5.2 (no code imported from other kits).

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 \
        --python build_owl.py
    ... -- --shape                 fast look-dev: per-vertex painted colours, no bake, one quick sheet
    ... -- --no-previews           exports + reports only

Coordinates: Blender Z-up, 1 unit = 1 stud (final size, import 1:1), feet on z = 0, the owl faces -Y and
its own left is +X. Studio = (-x, z, y) of Blender.

Method (same family as the approved Golden Retriever / Penguin): every rigid part is ONE surface made
from analytic signed-distance volumes joined with smooth unions (real fillets). The body, head, wings
and feet are meshed straight from a COARSE lattice (OpenVDB) and tidied, so the facets are broad and
even like cut gemstone planes, then flat shaded. Colour is painted by 3D position (continuous over every
join and UV seam) and baked to one 1024 atlas with icon lighting (per-facet key, AO, warm shadow, cool
rim). The scope reticle is a separate `_Glow` mesh for a subtle Neon accent.
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
ROOT = Path("C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning/blender-pet-kit/owl")
STEM = "owl"
PFX = "Owl_"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    if name in ARGS:
        i = ARGS.index(name)
        if i + 1 < len(ARGS):
            return ARGS[i + 1]
    return default


SHAPE = "--shape" in ARGS
QUICK = SHAPE
NO_PREVIEWS = "--no-previews" in ARGS
OUT = Path(arg("--out", str(ROOT / "previews")))
TEX_PATH = ROOT / "textures" / f"{STEM}.png"
FBX_PATH = ROOT / "exports" / "fbx" / f"{STEM}.fbx"
GLB_PATH = ROOT / "exports" / "glb" / f"{STEM}.glb"
BLEND_PATH = ROOT / f"{STEM}.blend"
ATLAS = 1024
BAKE = 2048
for d in (TEX_PATH.parent, FBX_PATH.parent, GLB_PATH.parent, OUT):
    d.mkdir(parents=True, exist_ok=True)


def log(*a):
    print(f"[owl {time.time() - T0:6.1f}s]", *a, flush=True)


P_BODY, P_HEAD, P_WINGL, P_WINGR, P_FOOTL, P_FOOTR, P_SCOPE, P_GLOW = range(1, 9)


def V(*a):
    return Vector(a if len(a) == 3 else a[0])


# =============================================================================================
# signed-distance toolkit (copied from the penguin kit)
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


def surf_point(G, F, x, z, y0=-1.0, y1=0.0):
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


def mirror(vf):
    vs, fs = vf
    return vs * np.array((-1.0, 1.0, 1.0)), [tuple(reversed(f)) for f in fs]


# =============================================================================================
# design (studs). Chunky chibi owl: egg body that is mostly head, flat cream facial disc, two soft
# fused ear tufts, small hooked beak flowing out of the disc, short rounded scalloped wings on shoulder
# pivots, stubby orange-tan feet, a short fan tail fused to the body, and a brass monocle-scope with a
# leather strap over its RIGHT eye (-X); the lens reticle is the Neon `_Glow` part.
# =============================================================================================
FUSED = {}
FACE = {}
HOVER_H = 1.5
HEAD_C = (0.0, -0.02, 1.46)
HEAD_R = (0.68, 0.58, 0.54)
FACE_PLANE = -0.50                       # the facial disc is a broad flat plane at y = -0.50
WING_PIV = (0.52, 0.10, 0.92)
FOOT_PIV = (0.22, -0.10, 0.24)
PIVOT = {
    "Owl_Body": V(0.0, 0.03, 0.62),
    "Owl_Head": V(0.0, 0.0, 1.00),
    "Owl_WingL": V(WING_PIV), "Owl_WingR": V(-WING_PIV[0], WING_PIV[1], WING_PIV[2]),
    "Owl_FootL": V(FOOT_PIV), "Owl_FootR": V(-FOOT_PIV[0], FOOT_PIV[1], FOOT_PIV[2]),
}
H_FINE_BODY, H_FINE_HEAD = 0.025, 0.02                 # fine lattices only drive the painter's masks
H_BODY, H_HEAD, H_WING, H_FOOT = 0.115, 0.09, 0.06, 0.048  # coarse lattices ARE the mesh: broad even facets


def body_field(h):
    G = Grid((-0.85, -0.85, -0.02), (0.85, 1.0, 1.35), h, sym_x=True)
    P = G.P
    egg = ell(P, (0, 0.04, 0.64), (0.62, 0.55, 0.54))
    belly = ell(P, (0, -0.12, 0.58), (0.50, 0.44, 0.46))
    neck = ell(P, (0, 0.02, 0.98), (0.53, 0.47, 0.30))
    F = smin(smin(egg, belly, 0.15), neck, 0.15)
    tail = ell(P, (0, 0.62, 0.30), (0.28, 0.10, 0.23), axis=(0, 0.8, -0.6))
    for s in (1, -1):                          # two broad side lobes so the fan reads as a fan
        tail = smin(tail, ell(P, (s * 0.15, 0.64, 0.25), (0.13, 0.09, 0.19), axis=(s * 0.35, 0.8, -0.6)), 0.06)
    F = smin(F, tail, 0.12)
    if h < 0.05:
        F = blur(F, 1)
    return G, F, dict(tail=tail)


def head_shape(P):
    """Head volume shared by the head part and the scope strap: big egg, cheeks, ear tufts, flat disc."""
    Y = P[..., 1]
    F = ell(P, HEAD_C, HEAD_R)
    for s in (1, -1):
        F = smin(F, ell(P, (s * 0.36, -0.18, 1.30), (0.31, 0.30, 0.27)), 0.14)                   # full cheeks
        ax = np.array((s * 1.23, 0.30, 1.0))
        ax /= np.linalg.norm(ax)                                  # tufts lean ~50 deg out and a little back
        b0 = np.array((s * 0.38, 0.04, 1.83))
        tuft = smin(ell(P, b0, (0.19, 0.16, 0.16), axis=tuple(ax)), ell(P, b0 + ax * 0.20, (0.10, 0.085, 0.13), axis=tuple(ax)), 0.08)
        F = smin(F, tuft, 0.13)  # soft tufts
    F = smax(F, -Y + FACE_PLANE, 0.16)          # broad flat facial disc
    return F


def head_field(h, store):
    G = Grid((-0.95, -1.0, 0.70), (0.95, 0.75, 2.30), h, sym_x=True)
    P = G.P
    base = head_shape(P)
    frames = {}
    for name, s in (("eyeL", 1), ("eyeR", -1)):
        p, n = surf_point(G, base, s * 0.27, 1.44)
        R = track_axes(n)
        u, v = R[0].copy(), R[1].copy()
        if u[0] < 0:
            u = -u
        if v[2] < 0:
            v = -v
        frames[name] = dict(c=p, u=u, v=v, n=n, r=(0.175, 0.195))
    up = ell(P, (0, -0.56, 1.30), (0.115, 0.09, 0.15), axis=(0, -0.45, -1))
    hook = ell(P, (0, -0.635, 1.185), (0.065, 0.055, 0.075), axis=(0, 0.25, -1))
    beak = smin(up, hook, 0.04)
    F = smin(base, beak, 0.05)
    if h < 0.05:
        F = blur(F, 1)
    if store:
        FACE.update(frames)
    return G, F, dict(beak=beak, hook=hook)


def wing_frame(s):
    """Rest (folded) wing: d runs from the shoulder down to the tip, c toward the front edge, n outward."""
    d = np.array((s * 0.30, 0.18, -0.94))
    d /= np.linalg.norm(d)
    c = np.array((0.0, -1.0, 0.0))
    c = c - d * (c @ d)
    c /= np.linalg.norm(c)
    n = np.cross(d, c)
    if n[0] * s < 0:
        n = -n
    return d, c, n / np.linalg.norm(n)


LOBES = ((-0.33, 0.64), (-0.04, 0.71), (0.25, 0.64))      # wide fan, three broad scallops      # (v, u) of the three broad feather scallops


def build_wing(h):
    """Left wing (+X); the right one is its mirror. One thick fused paddle with a cambered middle."""
    piv = np.array(WING_PIV)
    d, c, nw = wing_frame(1)
    G = Grid((0.10, -0.85, -0.15), (1.50, 0.95, 1.30), h)
    P = G.P
    q = P - piv
    u, v, w = q @ d, q @ c, q @ nw
    wc = 0.09 * np.sin(np.pi * np.clip(u / 0.82, 0, 1)) - 0.10 * np.clip((u - 0.45) / 0.37, 0, 1) ** 2 - 0.10 * (v / 0.46) ** 2
    blade = smin(sd_ell2(u, v, 0.12, 0.0, 0.16, 0.15), sd_ell2(u, v, 0.44, -0.04, 0.28, 0.44), 0.12)
    lobes = None
    for v0, u0 in LOBES:
        lb = np.hypot(u - u0, v - v0) - 0.16
        lobes = lb if lobes is None else np.minimum(lobes, lb)
    two = smin(blade, lobes, 0.04)
    th = 0.075 + 0.045 * sstep(-0.10, 0.38, v) - 0.03 * np.clip(u / 0.8, 0, 1)   # thick leading edge
    r = 0.05
    a, b = two + r, np.abs(w - wc) - th + r
    slab = np.sqrt(np.maximum(a, 0) ** 2 + np.maximum(b, 0) ** 2) + np.minimum(np.maximum(a, b), 0) - r
    root = ell(P, piv, (0.15, 0.17, 0.15))
    F = smin(slab, root, 0.10)
    return extract(G, F, None, "wing")


def build_foot(h):
    """Left foot (+X): feathered ankle hidden in the belly, a round pad and three stubby toes."""
    G = Grid((-0.05, -0.60, -0.10), (0.50, 0.20, 0.45), h)
    P = G.P
    Z = P[..., 2]
    hx = FOOT_PIV[0]
    F = ell(P, (hx, -0.10, 0.22), (0.13, 0.13, 0.15))
    F = smin(F, ell(P, (hx, -0.15, 0.08), (0.12, 0.12, 0.085)), 0.06)
    for a in (-30.0, 0.0, 30.0):
        ar = math.radians(a)
        dr = np.array((math.sin(ar), -math.cos(ar), 0.0))
        c = np.array((hx, -0.15, 0.0)) + dr * 0.14 + np.array((0, 0, 0.06))
        F = smin(F, ell(P, c, (0.062, 0.058, 0.115), axis=tuple(dr)), 0.04)
    F = smax(F, -Z, 0.02)
    return extract(G, F, None, "foot")


def build_scope():
    """Chunky brass monocle rim over the right eye plus a leather strap hugging the head side."""
    e = FACE["eyeR"]
    C = e["c"] + e["n"] * 0.04
    G = Grid((-0.85, -0.85, 1.02), (0.30, 0.75, 1.92), 0.02)
    P = G.P
    q = P - C
    a = q @ e["n"]
    rho = np.sqrt((q @ e["u"]) ** 2 + (q @ e["v"]) ** 2)
    ring = np.sqrt((rho - 0.215) ** 2 + (a / 0.8) ** 2) - 0.05
    X, Y, Z = P[..., 0], P[..., 1], P[..., 2]
    hs = head_shape(P)
    shell = np.abs(hs - 0.035) - 0.035
    band = np.abs(Z - (C[2] + 0.10 * (Y - C[1]))) - 0.062
    region = smax(np.minimum(X - (C[0] - 0.19), -0.30 - Y), X - 0.12, 0.03)      # wraps round the back of the head
    strap = smax(smax(shell, band, 0.01), region, 0.02)
    F = smin(ring, strap, 0.03)
    PIVOT["Owl_Scope"] = V(C)
    return extract(G, F, 900, "scope")


def build_reticle():
    """Thin ring + four crosshair ticks floating just in front of the painted right eye (Neon in Studio)."""
    e = FACE["eyeR"]
    C = e["c"] + e["n"] * 0.045
    u, v, n = e["u"], e["v"], e["n"]
    vs, fs = [], []
    R, seg = 0.118, 20
    cs = [(0.015, 0.0), (0.0, 0.011), (-0.015, 0.0), (0.0, -0.011)]
    for i in range(seg):
        ang = 2 * math.pi * i / seg
        rd = math.cos(ang) * u + math.sin(ang) * v
        for dr, dn in cs:
            vs.append(C + rd * (R + dr) + n * dn)
    for i in range(seg):
        j = (i + 1) % seg
        for k in range(4):
            k2 = (k + 1) % 4
            fs.append((i * 4 + k, j * 4 + k, j * 4 + k2, i * 4 + k2))

    def box(mid, a1, a2, a3, h1, h2, h3):
        b0 = len(vs)
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    vs.append(mid + a1 * h1 * sx + a2 * h2 * sy + a3 * h3 * sz)
        for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            fs.append(tuple(b0 + i for i in f))
    for dv, side in ((u, v), (-u, v), (v, u), (-v, u)):
        box(C + dv * 0.115, dv, side, n, 0.062, 0.0095, 0.008)
    PIVOT["Owl_Reticle_Glow"] = V(C)
    return np.array(vs), fs


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


TAWNY, TAWNY_DK, TAWNY_LT, BROWN_DK = rgb(178, 112, 58), rgb(122, 70, 36), rgb(214, 152, 88), rgb(86, 50, 28)
CREAM, CREAM_SH, DISC, DISC_RIM = rgb(250, 236, 206), rgb(224, 196, 154), rgb(253, 242, 218), rgb(100, 56, 30)
BEAK, BEAK_LT = rgb(104, 82, 70), rgb(160, 134, 112)
FOOT, FOOT_DK, FOOT_LT, CLAW = rgb(234, 158, 78), rgb(190, 110, 50), rgb(252, 198, 122), rgb(72, 50, 40)
EYE_DARK, AMBER, AMBER_DK, EYE_LINE = rgb(22, 14, 12), rgb(250, 176, 46), rgb(200, 106, 26), rgb(44, 26, 18)
BRASS, BRASS_DK, BRASS_LT, LEATHER = rgb(212, 160, 66), rgb(142, 96, 38), rgb(252, 222, 140), rgb(108, 62, 38)
RETICLE = rgb(255, 116, 70)
BLUSH = rgb(246, 156, 124)


def bands(p, fx, fz, seed, cy=0.0):
    """Broad painterly brush bands: (dark, light) masks from anisotropic noise, three value ranges."""
    az_ = np.arctan2(p[:, 0], -(p[:, 1] - cy))
    q = np.stack([np.cos(az_) * fx, np.sin(az_) * fx, p[:, 2] * fz], 1)
    s_ = vnoise(q, 1.0, seed)
    return 1.0 - sstep(0.38, 0.46, s_), sstep(0.60, 0.68, s_)


def sample(part, name, p):
    G, fl = FUSED[part]
    return G.sample(fl[name], p)


def feather(p, n, seed, z0=0.0):
    """Tawny plumage with broad strokes running down the form."""
    c = mix(TAWNY_DK, TAWNY, sstep(z0 + 0.05, z0 + 1.0, p[:, 2]))
    c = mix(c, TAWNY_LT, 0.35 * sstep(-0.2, 0.9, n[:, 2]))
    sd_, sl_ = bands(p, 3.0, 1.5, seed)
    c = mix(c, TAWNY_DK, 0.38 * sd_)
    c = mix(c, TAWNY_LT, 0.34 * sl_)
    return c


def paint_body(p, n):
    X, Y, Z = p[:, 0], p[:, 1], p[:, 2]
    nz = vnoise(p, 3.0, 2)
    c = feather(p, n, 11)
    spot = sstep(0.80, 0.84, vnoise(p * np.array((1.0, 1.0, 0.7)), 6.0, 21)) * sstep(0.0, 0.25, Y)
    c = mix(c, CREAM, 0.75 * spot)                                         # a few pale back spots
    cream = mix(CREAM_SH, CREAM, sstep(0.15, 0.9, Z))
    cd_, cl_ = bands(p, 0.9, 5.0, 12)
    cream = mix(mix(cream, CREAM_SH, 0.35 * cd_), rgb(255, 249, 232), 0.30 * cl_)
    for x0, z0 in ((-0.13, 0.36), (0.13, 0.36), (-0.25, 0.56), (0.0, 0.53), (0.25, 0.56), (-0.12, 0.74), (0.12, 0.74)):
        dx, dz = X - x0, Z - z0
        chev = sstep(0.036, 0.018, np.abs(dz - 0.50 * np.abs(dx))) * sstep(0.10, 0.075, np.abs(dx))
        cream = mix(cream, TAWNY, 0.80 * chev)
    bel = sstep(0.04, -0.04, Y + 0.16 + 0.30 * (X / 0.6) ** 2 + 0.06 * (nz - 0.5)) * sstep(1.05, 0.95, Z)
    c = mix(c, cream, bel)
    dt = sample("body", "tail", p)
    tm = sstep(0.05, -0.02, dt) * sstep(0.35, 0.50, Y)
    t = (Y - 0.44) * 0.8 - (Z - 0.43) * 0.6
    bars = sstep(0.45, 0.55, np.abs(((t / 0.11) % 1.0) - 0.5) * 2)
    tc = mix(TAWNY, BROWN_DK, 0.55 * bars)
    tc = mix(tc, CREAM, 0.55 * sstep(0.28, 0.34, t))
    c = mix(c, tc, tm)
    return c


def paint_head(p, n, eyes_out):
    X, Y, Z = p[:, 0], p[:, 1], p[:, 2]
    nz2 = vnoise(p, 3.0, 4)
    c = feather(p, n, 13, 1.0)
    speck = sstep(0.80, 0.84, vnoise(p, 9.0, 7)) * sstep(1.55, 1.75, Z)
    c = mix(c, CREAM, 0.70 * speck)
    tuft = sstep(1.82, 2.0, Z) * sstep(0.22, 0.34, np.abs(X))
    c = mix(c, BROWN_DK, 0.45 * tuft)                                       # darker tuft tips
    back = sstep(0.05, 0.25, Y)                                             # back of the head: pale nape + broad feather V
    vmask = sstep(0.08, 0.05, np.abs(Z - (1.16 + 0.62 * np.abs(X)))) * sstep(0.55, 0.45, np.abs(X)) * back
    c = mix(c, TAWNY_LT, 0.55 * sstep(1.22, 1.05, Z) * back)
    c = mix(c, mix(CREAM, TAWNY_LT, 0.3), 0.85 * vmask)
    # facial disc: two rounds around the eyes merging into the lower face, a V brow wedge between
    e1 = ((X - 0.27) / 0.35) ** 2 + ((Z - 1.44) / 0.35) ** 2
    e2 = ((X + 0.27) / 0.35) ** 2 + ((Z - 1.44) / 0.35) ** 2
    e3 = (X / 0.30) ** 2 + ((Z - 1.16) / 0.24) ** 2
    mk = np.minimum(np.minimum(e1, e2), e3) + 0.10 * (nz2 - 0.5)
    front = sstep(-0.20, -0.36, Y)
    disc = sstep(1.08, 0.92, mk) * front
    brow = sstep(0.012, -0.012, np.abs(X) - (0.035 + 0.36 * (Z - 1.30))) * sstep(1.30, 1.36, Z) * sstep(1.80, 1.70, Z)
    ang = np.where(X > 0, np.arctan2(Z - 1.44, X - 0.27), np.arctan2(Z - 1.44, -X - 0.27))
    rr = np.where(X > 0, np.sqrt(e1), np.sqrt(e2))
    rs = vnoise(np.stack([np.cos(ang) * 2.6, np.sin(ang) * 2.6, rr * 1.2], 1), 1.0, 31)   # radial disc strokes
    dc = mix(CREAM_SH, DISC, sstep(1.0, 0.45, rr))
    dc = mix(mix(dc, CREAM_SH, 0.30 * (1 - sstep(0.38, 0.46, rs))), rgb(255, 250, 236), 0.30 * sstep(0.60, 0.68, rs))
    for s in (1, -1):
        bd = np.sqrt(((X - s * 0.44) / 0.12) ** 2 + ((Z - 1.25) / 0.075) ** 2)
        dc = mix(dc, BLUSH, 0.40 * sstep(1.0, 0.2, bd))
    c = mix(c, dc, disc * (1 - brow))
    rim = sstep(0.97, 1.04, mk) * sstep(1.32, 1.20, mk) * front
    c = mix(c, DISC_RIM, 0.92 * rim * (1 - brow))
    c = mix(c, mix(TAWNY, TAWNY_LT, 0.4), brow * front)
    # eyes: big glossy amber eyes with big pupils; the scoped (right) eye is a touch "magnified"
    for name in ("eyeL", "eyeR"):
        e = FACE[name]
        d = p - e["c"]
        eu, ev = (d @ e["u"]) / e["r"][0], (d @ e["v"]) / e["r"][1]
        fr = (np.abs(d @ e["n"]) < 0.07) & (n @ e["n"] > 0.45)
        r = np.sqrt(eu * eu + ev * ev)
        line = fr & (r >= 0.96) & (r < 1.16)
        c[line] = mix(c[line], EYE_LINE, sstep(1.16, 1.05, r)[line])
        inside = fr & (r < 1.0)
        pup = 0.60 if name == "eyeR" else 0.54
        ce = mix(AMBER_DK, AMBER, sstep(0.55, -0.6, ev))
        ce = mix(ce, rgb(255, 214, 110), 0.55 * sstep(-0.2, -0.85, ev) * sstep(pup, 0.9, r))
        ce = mix(ce, AMBER_DK * 0.8, 0.6 * sstep(0.82, 0.98, r))
        ce = mix(ce, EYE_DARK, sstep(pup + 0.03, pup - 0.03, r))
        c[inside] = ce[inside]
        eyes_out.append((inside, eu, ev))
    # beak: dark warm horn flowing out of the disc, lighter ridge on top
    db, dh = sample("head", "beak", p), sample("head", "hook", p)
    bm = sstep(0.04, -0.012, db)
    bc = mix(BEAK, BEAK_LT, 0.6 * sstep(0.2, 0.8, n[:, 2]) * sstep(0.04, 0.0, np.abs(X)))
    bc = mix(bc, BEAK * 0.7, 0.6 * sstep(0.02, -0.01, dh))
    c = mix(c, bc, bm)
    return c, bm > 0.5


def paint_wing(p, n, s):
    pl, nl = p * np.array((s, 1, 1)), n * np.array((s, 1, 1))
    d, cc, nw = wing_frame(1)
    q = pl - np.array(WING_PIV)
    u, v = q @ d, q @ cc
    outer = sstep(-0.25, 0.25, nl @ nw)
    st = vnoise(np.stack([u * 2.2, v * 8.0, (q @ nw) * 2.0], 1), 1.0, 41)
    c = mix(TAWNY, TAWNY_DK, sstep(0.30, 0.75, u))
    c = mix(mix(c, TAWNY_DK, 0.35 * (1 - sstep(0.38, 0.46, st))), TAWNY_LT, 0.35 * sstep(0.60, 0.68, st))
    for u0, v0 in ((0.24, -0.22), (0.26, 0.02), (0.40, -0.10), (0.40, 0.15), (0.38, -0.34), (0.16, 0.18), (0.50, 0.02), (0.50, -0.24)):
        sp = sstep(0.068, 0.045, np.hypot(u - u0, v - v0))
        c = mix(c, CREAM, 0.85 * sp * outer)
    for v0, u0 in LOBES:
        dl = np.hypot(u - u0, v - v0) - 0.16
        fe = sstep(-0.14, -0.09, dl) * sstep(0.46, 0.52, u)
        c = mix(c, BROWN_DK, 0.40 * fe * (1 - sstep(-0.035, -0.015, dl)))
        c = mix(c, mix(CREAM, TAWNY_LT, 0.4), 0.70 * sstep(-0.04, -0.015, dl) * sstep(0.48, 0.54, u))
    under = mix(CREAM_SH, TAWNY_LT, 0.45 + 0.2 * (st - 0.5))
    return mix(under, c, outer)


def paint_foot(p, n, s):
    X, Y, Z = p[:, 0] * s, p[:, 1], p[:, 2]
    c = mix(FOOT_DK, FOOT, sstep(0.0, 0.12, Z))
    c = mix(c, FOOT_LT, 0.50 * sstep(0.45, 0.95, n[:, 2]))
    rr = np.sqrt((X - FOOT_PIV[0]) ** 2 + (Y + 0.15) ** 2)
    c = mix(c, CLAW, 0.85 * sstep(0.22, 0.27, rr) * sstep(0.2, -0.1, Y + 0.30))
    fz = sstep(0.12, 0.17, Z)
    fd, fl = bands(p, 4.0, 4.0, 51)
    fc = mix(mix(CREAM_SH, CREAM, 0.5), TAWNY_LT, 0.35 * fd + 0.0 * fl)
    return mix(c, fc, fz)


def paint_scope(p, n):
    e = FACE["eyeR"]
    C = e["c"] + e["n"] * 0.04
    q = p - C
    rho = np.sqrt((q @ e["u"]) ** 2 + (q @ e["v"]) ** 2)
    brass = mix(BRASS_DK, BRASS, sstep(-0.6, 0.3, n[:, 2] - 0.4 * n[:, 1]))
    brass = mix(brass, BRASS_LT, 0.65 * sstep(0.45, 0.85, n[:, 2] - 0.3 * n[:, 1]))
    ang = np.arctan2(q @ e["v"], q @ e["u"])
    knurl = sstep(0.3, 0.7, np.abs(((ang * 18 / (2 * math.pi)) % 1.0) - 0.5) * 2) * sstep(0.24, 0.27, rho)
    brass = mix(brass, BRASS_DK, 0.35 * knurl)
    lc = mix(LEATHER * 0.8, LEATHER, sstep(-0.3, 0.6, n[:, 2]))
    st = ((np.arctan2(p[:, 0], -(p[:, 1] - HEAD_C[1])) / 0.08) % 1.0 > 0.5)
    edge = np.abs(p[:, 2] - (C[2] + 0.10 * (p[:, 1] - C[1])))
    lc[st & (edge > 0.040) & (edge < 0.050)] = mix(LEATHER, CREAM, 0.6)
    strap = sstep(0.27, 0.30, rho)
    return mix(mix(brass, lc, strap), brass, sstep(-0.02, 0.02, p[:, 0]) * strap)    # brass buckle at the end


def paint_all(P, Ns, part):
    col = np.zeros((len(P), 3))
    hard = np.zeros(len(P), bool)
    eyes = []
    for pid in range(1, 9):
        m = part == pid
        if not m.any():
            continue
        p, n = P[m], Ns[m]
        ex = []
        h = np.zeros(len(p), bool)
        if pid == P_BODY:
            c = paint_body(p, n)
        elif pid == P_HEAD:
            c, h = paint_head(p, n, ex)
        elif pid in (P_WINGL, P_WINGR):
            c = paint_wing(p, n, 1 if pid == P_WINGL else -1)
        elif pid in (P_FOOTL, P_FOOTR):
            c, h = paint_foot(p, n, 1 if pid == P_FOOTL else -1), np.ones(len(p), bool)
        elif pid == P_SCOPE:
            c, h = paint_scope(p, n), np.ones(len(p), bool)
        else:
            c = np.tile(RETICLE, (len(p), 1))
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
    k = np.clip(ks + np.where(hard, 1.4, 1.8) * (kf - ks), 0.0, 1.0)      # clearly visible broad facets
    sky = 0.5 + 0.5 * Ns[:, 2]
    lightv = 0.58 + 0.44 * k + 0.10 * sky
    head = (part_ids == P_HEAD) | (part_ids == P_SCOPE)
    ao_w = np.where(head, 0.22, 0.32)
    aol_w = np.where(head, 0.08, 0.16)
    aof = (1.0 - ao_w + ao_w * sstep(0.12, 1.0, ao_s)) * (1.0 - aol_w * (1.0 - sstep(0.2, 1.0, ao_l)))
    shade = lightv * aof
    lit = col * shade[:, None]
    lit = mix(lit, lit * np.array((1.0, 0.84, 0.70)), 0.70 * sstep(0.86, 0.52, shade))     # warm shadows, never grey
    lit = lit + (sstep(0.3, 1.0, Ns @ Lr) * 0.10)[:, None] * np.array((0.55, 0.70, 1.0))   # cool rim
    hl = np.clip(col * 1.15 + 0.10, 0, 1) * np.array((1.0, 0.96, 0.88))
    lit = mix(lit, hl, 0.25 * edge * hard * sstep(-0.3, 0.5, Ns @ Lk))
    glow = part_ids == P_GLOW
    lit[glow] = col[glow]
    return np.clip(lit, 0, 1)


def catchlights(col, eyes):
    for inside, eu, ev in eyes:
        g1 = np.sqrt(((eu + 0.30) / 0.30) ** 2 + ((ev - 0.36) / 0.27) ** 2)
        g2 = np.sqrt(((eu - 0.36) / 0.13) ** 2 + ((ev + 0.30) / 0.12) ** 2)
        m1, m2 = inside & (g1 < 1.0), inside & (g2 < 1.0)
        col[m1] = mix(col[m1], np.array((1.0, 1.0, 1.0)), sstep(1.0, 0.8, g1)[m1])
        col[m2] = mix(col[m2], np.array((1.0, 0.98, 0.94)), sstep(1.0, 0.75, g2)[m2])
    return col


# =============================================================================================
# build
# =============================================================================================
def world_bounds(o):
    ws = [o.matrix_world @ vv.co for vv in o.data.vertices]
    return (Vector([min(w[k] for w in ws) for k in range(3)]), Vector([max(w[k] for w in ws) for k in range(3)]))


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
mat = bpy.data.materials.new("Owl_Atlas")
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
del Gc, Fc
wing_l = build_wing(H_WING)
foot_l = build_foot(H_FOOT)
scope_vf = build_scope()
ret_vf = build_reticle()
specs = [("Owl_Body", P_BODY, body_vf), ("Owl_Head", P_HEAD, head_vf),
         ("Owl_WingL", P_WINGL, wing_l), ("Owl_WingR", P_WINGR, mirror(wing_l)),
         ("Owl_FootL", P_FOOTL, foot_l), ("Owl_FootR", P_FOOTR, mirror(foot_l)),
         ("Owl_Scope", P_SCOPE, scope_vf), ("Owl_Reticle_Glow", P_GLOW, ret_vf)]
objs = [make_object(n, pid, vf, mat) for n, pid, vf in specs]
parts = {o.name: o for o in objs}
GLOW = parts["Owl_Reticle_Glow"]


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
tris = {o.name: tri_count(o) for o in objs}
log("triangles", sum(tris.values()), tris)

if SHAPE:
    for o in objs:
        me = o.data
        mw = o.matrix_world
        Pv = np.array([(mw @ v.co)[:] for v in me.vertices])
        Nv = np.array([(mw.to_3x3() @ v.normal)[:] for v in me.vertices])
        Nv /= np.maximum(np.linalg.norm(Nv, axis=1), 1e-9)[:, None]
        col, hard, eyes = paint_all(Pv, Nv, np.full(len(Pv), o.pass_index))
        sh = 0.70 + 0.30 * np.clip(Nv @ (np.array((-0.5, -0.62, 0.62)) / 0.93), 0, 1)
        col = catchlights(np.clip(col * sh[:, None], 0, 1), eyes) ** 2.2
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
    head_obj = parts["Owl_Head"]
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
        if not (nrm.dot(radial) > 0.35 and nrm.y < -0.1 and abs(ang) < 1.25 and 1.0 < c.z < 1.95):
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
    log("unwrapped; base texel ratio", round(base_ratio, 4), "face-island faces", n_face)

    # ---- bake data maps (the reticle is moved aside so it casts no AO onto the painted eye) ------
    GLOW.location.x += 10.0
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
                                             ("occ", 24), ("bev", 12))}
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
        lo_, hi_ = world_bounds(o)
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
    GLOW.location.x -= 10.0
    bpy.context.view_layer.update()
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
    full[~cov, :3] = TAWNY
    img4 = full.reshape(BAKE, BAKE, 4)
    f = BAKE // ATLAS
    img4 = img4.reshape(ATLAS, f, ATLAS, f, 4).mean(axis=(1, 3))
    atlas = bpy.data.images.new(f"{STEM}-src", ATLAS, ATLAS, alpha=False)
    atlas.pixels.foreach_set(img4.astype(np.float32).ravel())
    atlas.filepath_raw = str(TEX_PATH)
    atlas.file_format = "PNG"
    atlas.save()
    bpy.data.images.remove(atlas)
    log("painted", TEX_PATH.name)

    nt.nodes.clear()
    tex_img = bpy.data.images.load(str(TEX_PATH), check_existing=False)
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

# =============================================================================================
# reports (Studio axes = (-x, z, y) of Blender)
# =============================================================================================
bpy.context.view_layer.update()
JOINT_PARENT = {"Owl_Body": None, "Owl_Head": "Owl_Body", "Owl_WingL": "Owl_Body", "Owl_WingR": "Owl_Body",
                "Owl_FootL": "Owl_Body", "Owl_FootR": "Owl_Body", "Owl_Scope": "Owl_Head",
                "Owl_Reticle_Glow": "Owl_Scope"}
JOINT_NAME = {"Owl_Body": "root (belly centre)", "Owl_Head": "neck, hidden inside the head",
              "Owl_WingL": "shoulder (round wing root sunk into the body side)", "Owl_WingR": "shoulder",
              "Owl_FootL": "hip, inside the belly", "Owl_FootR": "hip, inside the belly",
              "Owl_Scope": "centre of the monocle rim (rigid, never animated)",
              "Owl_Reticle_Glow": "centre of the reticle (rigid, never animated; Neon)"}
MOTION = {
    "Owl_Body": "root part: lifted HOVER_H studs while flying, sine bob in Studio Y; pitch about Studio X (nose down to glide); yaw about Studio Y for the perched hop-turn",
    "Owl_Head": "nod = pitch about Studio X, tilt = roll about Studio Z, look = yaw about Studio Y, through the neck joint (owls turn their heads a lot: up to +-60 deg yaw is fine)",
    "Owl_WingL": "flap = rotate about Studio Z (front-back axis) through the shoulder; NEGATIVE Blender-Y = POSITIVE Studio Z raises the left wing (see locomotion_data.angle_convention)",
    "Owl_WingR": "flap = rotate about Studio Z through the shoulder; mirror of WingL (opposite sign)",
    "Owl_FootL": "pitch about Studio X through the hip: tuck the toes down/back while flying, small dangle on the hop",
    "Owl_FootR": "pitch about Studio X through the hip: tuck the toes down/back while flying, small dangle on the hop",
    "Owl_Scope": "none (welded to the head)",
    "Owl_Reticle_Glow": "none (welded to the scope); Material = Neon, pulse its Transparency (see vfx)",
}


def studio(v):
    return [round(-v[0], 4) + 0.0, round(v[2], 4) + 0.0, round(v[1], 4) + 0.0]


def studio_size(v):
    return [round(v[0], 4), round(v[2], 4), round(v[1], 4)]


report = {"asset": STEM, "blender_version": bpy.app.version_string,
          "authoring": "final Roblox stud size (1 Blender unit = 1 stud); import at 1:1, do not scale",
          "axes": "Blender Z-up, front -Y, the owl's left +X; modelled perched, feet on z = 0 (hover offset is in studio-install-data.json)",
          "texture": f"textures/{TEX_PATH.name} ({ATLAS}x{ATLAS}, shared by every part)", "parts": {}}
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
        "joint_parent": JOINT_PARENT[name], "uv_range": uvr}
report["total_triangles"] = sum(pp["triangles"] for pp in report["parts"].values())
size = hi_all - lo_all
report["overall"] = {"bbox_min": [round(v, 4) for v in lo_all], "bbox_max": [round(v, 4) for v in hi_all],
                     "height_studs": round(size.z, 4), "length_studs": round(size.y, 4), "width_studs": round(size.x, 4),
                     "height_with_hover_studs": round(size.z + HOVER_H, 4)}
body_pivot = parts["Owl_Body"].location.copy()
glow_c = parts["Owl_Reticle_Glow"].location.copy()
dL = wing_frame(1)[0]
install = {
    "asset": STEM, "rarity": "Epic",
    "strong_suit": "bosses: marks the toughest nearby enemy; the player's hits on the marked enemy do +20% (game code)",
    "axis": "studio = (-x, z, y) of blender; Blender front -Y = Studio front -Z",
    "units": "studs; the model is at final size, import 1:1 and do not scale",
    "sides": "L/R are the owl's own left/right; its left is Blender +X = Studio -X. The scope sits over its RIGHT eye",
    "origin": "all positions are relative to the model origin = the ground point under the body (Blender world origin); modelled perched, feet on Studio Y = 0",
    "ground_point": studio((0.0, 0.0, 0.0)), "overall_size": studio_size(size),
    "overall_center": studio((lo_all + hi_all) / 2), "texture": f"textures/{TEX_PATH.name}",
    "texture_note": "one shared atlas on every MeshPart via MeshPart.TextureID. Owl_Reticle_Glow: set Material = Neon and Color = [255, 116, 70] (its atlas texels are that colour too)",
    "rest_rotation": "every part has identity rotation relative to the model at rest (wings folded down the body sides)",
    "rig": "one Motor6D per animated part: Part0 = joint_parent, Part1 = the part, C0/C1 at the part's pivot; Owl_Scope and Owl_Reticle_Glow are WeldConstraints",
    "role_prop": "Owl_Scope: chunky brass monocle-scope with a leather strap over the right eye; Owl_Reticle_Glow: the Neon target reticle in its lens (the painted eye shows through)",
    "parts": {}}
for name, o in parts.items():
    lo, hi = world_bounds(o)
    install["parts"][name] = {
        "center": studio((lo + hi) / 2), "size": studio_size(hi - lo), "pivot": studio(o.location),
        "pivot_from_body_pivot": studio(o.location - body_pivot), "pivot_is": JOINT_NAME[name],
        "joint_parent": JOINT_PARENT[name], "suggested_motion": MOTION[name]}

# World-axis degrees (Blender): rx about X (+ = nose / toes down), ry about Y (the front-back axis: + swings the
# LEFT wing DOWN), rz about Z (yaw, + turns the face toward the owl's left... i.e. brings the RIGHT (scoped) eye forward).
# Body_loc = (0, up, 0): lift of the body root above its perched rest position.
TUCK = (48, 0, 0)
FR = {
    "hover_mid": dict(Body_loc=(0, HOVER_H, 0), WingL=(0, -105, -24), WingR=(0, 105, 24), FootL=TUCK, FootR=TUCK),
    "wings_up": dict(Body_loc=(0, HOVER_H - 0.07, 0), WingL=(0, -112, 0), WingR=(0, 112, 0), FootL=TUCK, FootR=TUCK, Head=(4, 0, 0)),
    "wings_down": dict(Body_loc=(0, HOVER_H + 0.07, 0), WingL=(0, -36, 0), WingR=(0, 36, 0), FootL=(40, 0, 0), FootR=(40, 0, 0), Head=(-3, 0, 0)),
    "glide": dict(Body_loc=(0, HOVER_H, 0), Body=(12, 0, 0), Head=(-12, 0, 0), WingL=(0, -90, 10), WingR=(0, 90, -10),
                  FootL=(60, 0, 0), FootR=(60, 0, 0)),
    "mark_target": dict(Body_loc=(0, HOVER_H, 0), Body=(6, 0, 0), Head=(6, -14, 20), WingL=(0, -50, 0), WingR=(0, 50, 0),
                        FootL=TUCK, FootR=TUCK),
    "head_turn": dict(Head=(0, 8, 50)),
    "perch_hop_turn": dict(Body_loc=(0, 0.18, 0), Body=(0, 0, 24), Head=(0, 0, -12), WingL=(0, -22, 0), WingR=(0, 22, 0),
                           FootL=(14, 0, 0), FootR=(14, 0, 0)),
}
FR_TIME = {"hover_mid": 0.0, "wings_up": 0.30, "wings_down": 0.30, "glide": 0.0, "mark_target": 0.25,
           "head_turn": 0.35, "perch_hop_turn": 0.30}
install["locomotion"] = "fly"
install["locomotion_data"] = {
    "summary": "flies: hovers about 1.5 studs up with slow, broad wingbeats and a gentle bob, glides on held wings when the player runs, "
               "and when idle near the player for a while it lands and perches (little hop-turns on its stubby feet)",
    "hover_height_studs": HOVER_H,
    "overall_height_at_hover_studs": round(size.z + HOVER_H, 3),
    "how": "the model stands on the ground (feet on Studio Y = 0); lift the Body root by hover_height_studs (plus the bob) and keep every other part joined to it",
    "bob": {"amplitude_studs": 0.12, "period_s": 1.6, "formula": "body_up = hover_height_studs + amplitude_studs * sin(2*pi*t/period_s)",
            "extra": "pitch the Body +-3 deg about Studio X in time with the bob"},
    "wingbeat": {
        "period_s": 0.6,
        "note": "slow, broad owl beats: ease between wings_up and wings_down (sine), 0.3 s each way. Angles are DELTAS from the folded rest "
                "pose (wing hanging about 68 deg below horizontal): up = about 44 deg above horizontal, down = about 32 deg below it. "
                "Body rises 0.07 on the down stroke. Every 3-4 beats hold the glide frame for 0.4 s for a flap-flap-glide rhythm.",
        "WingL_studio_rz_deg": {"up": -112, "down": -36, "mid": -105}, "WingR_studio_rz_deg": {"up": 112, "down": 36, "mid": 105}, "mid_cup_studio_ry_deg": {"WingL": -24, "WingR": 24}},
    "glide": "wings held level (WingL/R -90/+90, swept back 10 deg), body nose-down 12 deg, head counter-pitched to stay level, feet tucked",
    "mark_target": "on mark: face the target, head tilted 14 deg and yawed 20 deg so the scoped RIGHT eye leads, body leans in 6 deg, wings half-spread; "
                   "hold 0.25 s while the reticle pulse fires (see vfx), then return to hover",
    "perched_idle": "lands on its feet (Body_loc 0); every 2-4 s a little hop-turn: up 0.18 studs and yaw 24 deg over 0.3 s, wings flick out 22 deg, "
                    "head lags -12 deg; between hops a slow head turn up to 50 deg (head_turn)",
    "frames": {k: {"duration_s": FR_TIME[k], "body_up_studs": v.get("Body_loc", (0, 0, 0))[1],
                   "joints": {PFX + b: {"blender_rot_deg": list(a), "studio_rot_deg": [-a[0], a[2], a[1]]}
                              for b, a in v.items() if not b.endswith("_loc")}} for k, v in FR.items()},
    "angle_convention": "blender_rot_deg = about world X, Y, Z; studio_rot_deg = [about Studio X, about Studio Y, about Studio Z] = [-bx, bz, by]. "
                        "Apply as CFrame.Angles(rad(sx), rad(sy), rad(sz)) in the joint's pivot frame, relative to the rest pose.",
}
install["vfx"] = [
    {"kind": "neon_pulse", "part": "Owl_Reticle_Glow", "position": studio(glow_c),
     "colour_rgb": [255, 116, 70], "material": "Neon",
     "suggested": {"Transparency_idle": [0.35, 0.55], "idle_pulse_period_s": 1.4,
                   "Transparency_marking": [0.05, 0.35], "marking_pulse_period_s": 0.45,
                   "PointLight": {"Color": [255, 140, 90], "Brightness": 0.6, "Range": 3, "Shadows": False},
                   "note": "subtle: tween Transparency with a sine, never fully opaque at idle; the PointLight only while marking"}},
    {"kind": "particle_trail", "part": "Owl_Body", "attachment_position": studio(V(0.0, 0.55, 0.70)),
     "attachment_from_body_pivot": studio(V(0.0, 0.55, 0.70) - body_pivot),
     "colour_rgb": [[255, 236, 200], [255, 176, 96]], "enabled": "only while flying (Body_loc > 0.5)",
     "suggested": {"Texture": "soft feather sprite or soft round sparkle", "Rate": 6, "Lifetime": [0.6, 1.0], "Speed": [0.3, 0.8],
                   "SpreadAngle": [25, 25], "EmissionDirection": "Back", "Size": "0 -> 0.22 (t 0.15) -> 0", "Transparency": "0.45 -> 1",
                   "LightEmission": 0.5, "Drag": 2, "Acceleration": [0, -1.2, 0], "Rotation": [0, 360], "RotSpeed": [-60, 60],
                   "LockedToPart": False, "note": "faint: a few drifting feathers/sparkles, not a stream"}},
    {"kind": "wingtip_trail_optional", "parts": ["Owl_WingL", "Owl_WingR"],
     "attachments_from_wing_pivot": {"Owl_WingL": [studio(V(dL * 0.45)), studio(V(dL * 0.66))],
                                     "Owl_WingR": [studio(V(dL * 0.45 * np.array((-1, 1, 1)))), studio(V(dL * 0.66 * np.array((-1, 1, 1))))]},
     "colour_rgb": [255, 236, 200],
     "suggested": {"Trail.Lifetime": 0.25, "Transparency": "0.75 -> 1", "WidthScale": "1 -> 0", "LightEmission": 0.3,
                   "enabled": "glide frames only"}},
    {"kind": "mark_on_target", "part": "the marked enemy (game code)", "colour_rgb": [255, 116, 70],
     "suggested": {"Highlight": {"FillColor": [255, 116, 70], "FillTransparency": 0.85, "OutlineColor": [255, 170, 100],
                                 "OutlineTransparency": 0.2, "DepthMode": "Occluded"},
                   "BillboardGui_reticle": "a small amber reticle ring above the enemy's head (Size 2x2 studs), slow 1.4 s spin",
                   "Beam_on_mark_optional": {"from": "Owl_Reticle_Glow attachment", "to": "enemy", "Color": [255, 140, 90],
                                             "Transparency": "0.6 -> 0.95", "Width0": 0.06, "Width1": 0.14, "LightEmission": 1,
                                             "FaceCamera": True, "duration_s": 0.35}}},
]
log("overall (w, len, h)", tuple(round(v, 3) for v in (size.x, size.y, size.z)), "tris", report["total_triangles"])

if not QUICK:
    (ROOT / "polygon-report.json").write_text(json.dumps(report, indent=2))
    (ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=2))
    select_only(objs, parts["Owl_Body"])
    bpy.ops.export_scene.gltf(filepath=str(GLB_PATH), export_format="GLB", use_selection=True, export_apply=True)
    select_only(objs, parts["Owl_Body"])
    bpy.ops.export_scene.fbx(filepath=str(FBX_PATH), use_selection=True, object_types={"MESH"},
                             axis_forward="-Z", axis_up="Y", path_mode="COPY", embed_textures=True,
                             add_leaf_bones=False)
    log("exported", FBX_PATH.name, GLB_PATH.name)

# =============================================================================================
# armature (Blender only, for posing previews; exports are the plain rigid parts)
# =============================================================================================
arm_data = bpy.data.armatures.new("Owl_Rig")
arm = bpy.data.objects.new("Owl_Rig", arm_data)
scene.collection.objects.link(arm)
select_only([arm])
bpy.ops.object.mode_set(mode="EDIT")
ebs = {}
for name, o in parts.items():
    eb = arm_data.edit_bones.new(name.replace(PFX, ""))
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
    o.parent_bone = name.replace(PFX, "")
    bpy.context.view_layer.update()
    o.matrix_world = mwo
bpy.context.view_layer.update()


def pose(rots):
    """rots: part -> world-axis degrees (rx, ry, rz); 'Body_loc' = (0, up, 0). Bones point +Z with roll 0, so
    bone X = world X, bone Y = world Z (yaw), bone Z = world -Y."""
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        rx, ry, rz = rots.get(pb.name, (0, 0, 0))
        pb.rotation_euler = [math.radians(rx), math.radians(rz), -math.radians(ry)]
        pb.location = (0, 0, 0)
    arm.pose.bones["Body"].location = (0, rots.get("Body_loc", (0, 0, 0))[1], 0)
    bpy.context.view_layer.update()


if not QUICK:
    for im in bpy.data.images:
        if im.source == "FILE":
            im.pack()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), relative_remap=True)
    log("saved", BLEND_PATH.name)

# =============================================================================================
# previews (Eevee); the reticle shows emissive like Neon
# =============================================================================================
gm = bpy.data.materials.new("Owl_Neon_Preview")
gm.use_nodes = True
gnt = gm.node_tree
gnt.nodes.clear()
ge = gnt.nodes.new("ShaderNodeEmission")
ge.inputs["Color"].default_value = (*[float(x) for x in RETICLE], 1)
ge.inputs["Strength"].default_value = 0.9
go = gnt.nodes.new("ShaderNodeOutputMaterial")
gnt.links.new(ge.outputs[0], go.inputs[0])
GLOW.data.materials[0] = gm

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


# presentation: HOVERING with the wings mid-beat (its natural in-game stance); the perched idle is in the pose check
up = HOVER_H
tgt = V(0, 0, 1.05 + up)
ft = V(0, -0.5, 1.40 + up)
tp = V(0, 0, 1.05)
POSES = [
    ("Wings up (hover)", FR["wings_up"], around(tgt, (-0.75, -0.9, 0.25), 9.5), tgt),
    ("Wings down (hover)", FR["wings_down"], around(tgt, (-0.75, -0.9, 0.25), 9.5), tgt),
    ("Glide: wings level, nose down 12", FR["glide"], around(tgt, (-1, -0.45, 0.35), 9.5), tgt),
    ("Mark target: head tilt+turn, wings half", FR["mark_target"], around(ft, (-0.35, -1, 0.12), 6.5), ft),
    ("Perched head turn 50", FR["head_turn"], around(tp + V(0, 0, 0.3), (0.2, -1, 0.15), 7.5), tp + V(0, 0, 0.3)),
    ("Perched hop-turn", FR["perch_hop_turn"], around(tp, (-0.6, -1, 0.3), 8.5), tp),
]

if not NO_PREVIEWS and SHAPE:
    items = []
    pose(FR["hover_mid"])
    items.append((shoot(OUT / "_s-threeq.png", around(tgt, (-0.75, -0.9, 0.3), 9.5), tgt, res=(600, 600)), "threeq hover"))
    items.append((shoot(OUT / "_s-front.png", around(tgt, (0, -1, 0.1), 9.5), tgt, res=(600, 600)), "front hover"))
    pose({})
    items.append((shoot(OUT / "_s-side.png", around(tp, (-1, 0, 0.1), 8.0), tp, res=(600, 600)), "side perched"))
    items.append((shoot(OUT / "_s-face.png", around(V(0, -0.5, 1.4), (-0.3, -1, 0.12), 4.0), V(0, -0.5, 1.4), res=(600, 600)), "face"))
    pose(FR["wings_up"])
    items.append((shoot(OUT / "_s-up.png", POSES[0][2], POSES[0][3], res=(600, 600)), "wings up"))
    pose(FR["mark_target"])
    items.append((shoot(OUT / "_s-mark.png", POSES[3][2], POSES[3][3], res=(600, 600)), "mark"))
    make_sheet(items, 3, 500, OUT / "_shape-sheet.png", f"Owl shape run: {sum(tris.values())} tris")
    for pth, _ in items:
        pth.unlink()
elif not NO_PREVIEWS:
    pose(FR["hover_mid"])
    shots = [(shoot(OUT / "threeq.png", around(tgt, (-0.75, -0.9, 0.3), 9.5), tgt), "Three-quarter (hovering, wings mid-beat)"),
             (shoot(OUT / "front.png", around(tgt, (0, -1, 0.1), 9.5), tgt), "Front"),
             (shoot(OUT / "side.png", around(tgt, (-1, 0, 0.1), 9.5), tgt), "Side (owl's right)"),
             (shoot(OUT / "back.png", around(tgt, (0, 1, 0.25), 9.5), tgt), "Back")]
    face = shoot(OUT / "face-closeup.png", around(ft, (-0.3, -1, 0.10), 4.2), ft, res=(1400, 1400))
    pose_items = []
    for i, (lab, rots, loc, t) in enumerate(POSES):
        pose(rots)
        pose_items.append((shoot(OUT / f"_pose-{i}.png", loc, t, res=(900, 900)), lab))
    pose({})
    make_sheet(pose_items, 3, 450, OUT / "pose-check.png", "Owl: flight + perch pose check through the joint pivots",
               "Each part rotates about its own pivot (Blender armature, preview only). Look for gaps at the shoulders, neck and hips.")
    for pth, _ in pose_items:
        pth.unlink()
    make_sheet(shots + [(face, "Face close-up (scope reticle = Neon)"), (OUT / "pose-check.png", "Pose check (wingbeat, glide, mark, perch)")],
               3, 520, OUT / "sheet.png",
               f"Owl pet (Epic, bosses): {report['total_triangles']:,} tris, one 1024 atlas + Neon reticle",
               "Blender 5.2 Eevee renders. Presented hovering 1.5 studs up, wings mid-beat. Blender-verified, Studio untested.")
log("done")
