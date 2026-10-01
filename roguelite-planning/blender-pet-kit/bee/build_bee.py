"""Bee pet (Rare, strong suit: poison) for the roguelite.

Self-contained generator for background Blender 5.2:

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 \
        --python build_bee.py
    ... -- --quick --out <dir>      iteration: 1024 raster, Eevee views + pose frames, no exports

Method (same family as the approved Golden Retriever and the Bunny): every part is ONE fused surface
(signed-distance fields joined with smooth unions, OpenVDB isosurface, quadric decimate to a coarse even
mesh, edge-flip + relax tidy), unwrapped into one 1024 atlas, flat-shaded so the facets read like cut gem
planes, and the atlas is painted per texel from world position, normals, SDF ambient occlusion and the face /
wing / jar masks (numpy rasteriser, no Cycles, no Studio).

Coordinates: Blender Z-up, 1 unit = 1 stud. The bee is modelled AT REST with its lowest point (the jar) at z of about 0.02 and faces -Y;
its own left is +X. The game lifts the whole rig by HOVER_H (install data) to hover. Studio = (-x, z, y) of Blender.
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
STEM = "bee"
PFX = "Bee_"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    if name in ARGS:
        i = ARGS.index(name)
        if i + 1 < len(ARGS):
            return ARGS[i + 1]
    return default


QUICK = "--quick" in ARGS
OUT = Path(arg("--out", str(ROOT / "previews")))
TEX_PATH = ROOT / "textures" / f"{STEM}.png"
FBX_PATH = ROOT / "exports" / "fbx" / f"{STEM}.fbx"
GLB_PATH = ROOT / "exports" / "glb" / f"{STEM}.glb"
BLEND_PATH = ROOT / f"{STEM}.blend"
ATLAS = 1024
RS = ATLAS if QUICK else ATLAS * 2          # raster resolution (2x supersample in the full run)
for d in (TEX_PATH.parent, FBX_PATH.parent, GLB_PATH.parent, OUT):
    d.mkdir(parents=True, exist_ok=True)


def log(*a):
    print(f"[bee {time.time() - T0:6.1f}s]", *a, flush=True)


def V(*a):
    return Vector(a if len(a) == 3 else a[0])


# =============================================================================================
# voxel fields
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


def ell(P, c, r, ax=None):
    return sd_ell(P, c, AXES if ax is None else ax, r)


def rcone(P, a, b, ra, rb):
    a, b = np.array(a, float), np.array(b, float)
    ab = b - a
    t = np.clip(((P - a) @ ab) / (ab @ ab), 0.0, 1.0)
    C = a + t[..., None] * ab
    return np.linalg.norm(P - C, axis=-1) - (ra + (rb - ra) * t)


def dir_axes(y):
    y = np.array(y, float)
    y /= np.linalg.norm(y)
    ref = np.array([0, 0, 1.0]) if abs(y[2]) < 0.9 else np.array([1.0, 0, 0])
    x = np.cross(y, ref)
    x /= np.linalg.norm(x)
    return np.array([x, y, np.cross(x, y)])


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def min_angles(vs, fs):
    a, b, c = vs[[f[0] for f in fs]], vs[[f[1] for f in fs]], vs[[f[2] for f in fs]]

    def ang(p, q, r):
        u, v = q - p, r - p
        cs = np.sum(u * v, 1) / np.maximum(np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1), 1e-12)
        return np.degrees(np.arccos(np.clip(cs, -1, 1)))
    return np.minimum(np.minimum(ang(a, b, c), ang(b, c, a)), ang(c, a, b))


def tidy(grid, F, vs, fs, passes=6):
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
        p = co + 0.6 * (cen - co)
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


def drop_floaters(vs, fs):
    """Keep only the big connected shells (tiny isolated bubbles from the isosurface are removed)."""
    par = list(range(len(vs)))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    for f in fs:
        for i in range(1, len(f)):
            ra, rb = find(f[0]), find(f[i])
            if ra != rb:
                par[ra] = rb
    cnt = {}
    for f in fs:
        r = find(f[0])
        cnt[r] = cnt.get(r, 0) + 1
    big = max(cnt.values())
    keep = [f for f in fs if cnt[find(f[0])] >= max(40, 0.04 * big)]
    used = sorted({i for f in keep for i in f})
    remap = {o: n for n, o in enumerate(used)}
    return vs[used], [tuple(remap[i] for i in f) for f in keep]


def extract(grid, F, target, sym=False, name="fused"):
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
    dm = ob.modifiers.new("Decimate", "DECIMATE")
    dm.ratio = min(1.0, target / max(n_tri, 1))
    dm.use_collapse_triangulate = True
    if sym:
        dm.use_symmetry = True
        dm.symmetry_axis = "X"
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    m2 = ev.to_mesh()
    vo = np.array([v.co[:] for v in m2.vertices], float)
    fo = [tuple(p.vertices) for p in m2.polygons]
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    vo, fo = drop_floaters(vo, fo)
    vo, fo = tidy(grid, F, vo, fo)
    log(name, "isosurface", n_tri, "->", len(fo), "tris")
    return vo, fo



# =============================================================================================
# design (studs). Chunky chibi bee: big round head, fuzzy striped body, thick rounded wings,
# tiny stubby legs, small stinger, honey jar with green (poison) honey hung from a cord.
# The model stands on z = 0 (feet); the game lifts the whole rig by HOVER_H when it hovers.
# =============================================================================================
HOVER_H = 1.2
WING_T = math.radians(38)                       # rest angle of the wings above horizontal
WING_B = math.radians(22)                       # rest sweep of the wings back toward the tail
WING_ROOT = {1: (0.10, 0.12, 0.80), -1: (-0.10, 0.12, 0.80)}
PIVOTS = {
    "Body": ((0.0, 0.20, 0.52), None),
    "Head": ((0.0, -0.10, 0.55), "Body"),
    "WingL": (WING_ROOT[1], "Body"), "WingR": (WING_ROOT[-1], "Body"),
    "Stinger": ((0.0, 0.74, 0.44), "Body"),
    "LegL": ((0.20, 0.10, 0.30), "Body"), "LegR": ((-0.20, 0.10, 0.30), "Body"),
    "Jar": ((0.0, -0.12, 0.40), "Body"),
}
PID = {n: i + 1 for i, n in enumerate(PIVOTS)}
SPEC = {}
STING_DIR = np.array((0.0, 0.985, -0.17))
STING_DIR /= np.linalg.norm(STING_DIR)
JAR_C = np.array((0.0, -0.28, 0.13))
HEAD_C = np.array((0.0, -0.30, 0.70))
BODY_SEGS = [((0, 0.06, 0.54), (0.36, 0.27, 0.33)), ((0, 0.27, 0.52), (0.35, 0.22, 0.33)),
             ((0, 0.45, 0.50), (0.31, 0.20, 0.29)), ((0, 0.59, 0.47), (0.23, 0.16, 0.22)),
             ((0, 0.70, 0.45), (0.11, 0.10, 0.11))]


def sd_ell2(u, v, cu, cv, ru, rv):
    x, y = (u - cu) / ru, (v - cv) / rv
    k0 = np.sqrt(x * x + y * y)
    k1 = np.sqrt((x / ru) ** 2 + (y / rv) ** 2)
    return np.where(k0 < 1e-6, -min(ru, rv), k0 * (k0 - 1.0) / np.maximum(k1, 1e-9))


def rcyl(P, c, R, H, r):
    q0 = np.hypot(P[..., 0] - c[0], P[..., 1] - c[1]) - R + r
    q1 = np.abs(P[..., 2] - c[2]) - H + r
    return np.sqrt(np.maximum(q0, 0) ** 2 + np.maximum(q1, 0) ** 2) + np.minimum(np.maximum(q0, q1), 0) - r


def build_body():
    g = Grid((-0.55, -0.40, 0.05), (0.55, 0.95, 1.0), 0.02, sym_x=True)
    P = g.P
    F = ell(P, *BODY_SEGS[0])
    for c, r in BODY_SEGS[1:]:
        F = smin(F, ell(P, c, r), 0.09)
    F = smin(F, ell(P, (0, -0.03, 0.58), (0.38, 0.17, 0.32)), 0.10)      # shoulder fuzz: one broad lump
    F = smin(F, ell(P, (0, 0.12, 0.80), (0.22, 0.20, 0.10)), 0.10)       # back fuzz tuft: one broad lump
    SPEC["Body"] = dict(grid=g, F=F, comps={}, target=1500, sym=True)


def build_head():
    g = Grid((-0.65, -0.85, 0.25), (0.65, 0.25, 1.25), 0.02, sym_x=True)
    P = g.P
    F = ell(P, HEAD_C, (0.40, 0.34, 0.36))
    for s in (1, -1):
        F = smin(F, ell(P, (0.21 * s, -0.44, 0.60), (0.16, 0.15, 0.14)), 0.10)     # chubby cheeks
    F = smin(F, ell(P, (0, -0.24, 0.94), (0.29, 0.24, 0.14)), 0.10)                 # crown fuzz
    F = smin(F, ell(P, (0, -0.46, 0.50), (0.20, 0.15, 0.12)), 0.10)                 # chin
    ant, tip = None, None
    for s in (1, -1):
        a, b, c = (0.12 * s, -0.42, 0.95), (0.19 * s, -0.50, 1.07), (0.25 * s, -0.60, 1.12)
        st = smin(rcone(P, a, b, 0.055, 0.048), rcone(P, b, c, 0.048, 0.045), 0.03)
        ball = ell(P, (0.26 * s, -0.63, 1.12), (0.07, 0.07, 0.07))
        an = smin(st, ball, 0.03)
        ant = an if ant is None else np.minimum(ant, an)
        tip = ball if tip is None else np.minimum(tip, ball)
        F = smin(F, an, 0.06)
    SPEC["Head"] = dict(grid=g, F=F, comps=dict(ant=ant, tip=tip), target=1500, sym=True)


def wing_frame(s):
    d = np.array((s * math.cos(WING_T) * math.cos(WING_B), math.cos(WING_T) * math.sin(WING_B), math.sin(WING_T)))
    c = np.array((0.0, 1.0, 0.0))
    c = c - d * (c @ d)
    c /= np.linalg.norm(c)
    n = np.cross(d, c)
    return d, c, n / np.linalg.norm(n)


def wing_2d(u, v):
    """Teardrop paddle: narrow at the root, wide and round at the tip."""
    tip = np.hypot(u - 0.37, v - 0.05) - 0.215
    root = sd_ell2(u, v, 0.14, 0.04, 0.17, 0.085)
    return smin(tip, root, 0.12)


def build_wing(s):
    name = "WingL" if s > 0 else "WingR"
    g = Grid((-0.10, -0.20, 0.60) if s > 0 else (-0.85, -0.20, 0.60), (0.85, 0.75, 1.45) if s > 0 else (0.10, 0.75, 1.45), 0.02)
    P = g.P
    d, c, n = wing_frame(s)
    q = P - np.array(WING_ROOT[s])
    u, v, w = q @ d, q @ c, q @ n
    th, r = 0.06, 0.045                                   # thick wing, fully rounded soft rim
    a, b = wing_2d(u, v) + r, np.abs(w) - th + r
    F = np.sqrt(np.maximum(a, 0) ** 2 + np.maximum(b, 0) ** 2) + np.minimum(np.maximum(a, b), 0) - r
    SPEC[name] = dict(grid=g, F=F, comps={}, target=340, sym=False)


def build_stinger():
    g = Grid((-0.2, 0.5, 0.2), (0.2, 1.1, 0.7), 0.015, sym_x=True)
    P = g.P
    piv = np.array(PIVOTS["Stinger"][0])
    F = smin(ell(P, piv, (0.10, 0.10, 0.10)), rcone(P, piv, piv + STING_DIR * 0.17, 0.10, 0.04), 0.05)
    F = smin(F, ell(P, piv + STING_DIR * 0.18, (0.045, 0.045, 0.045)), 0.03)
    SPEC["Stinger"] = dict(grid=g, F=F, comps={}, target=90, sym=True)


def build_legs(s):
    name = "LegL" if s > 0 else "LegR"
    g = Grid((0.03, -0.25, 0.05) if s > 0 else (-0.45, -0.25, 0.05), (0.45, 0.60, 0.46) if s > 0 else (-0.03, 0.60, 0.46), 0.012)
    P = g.P
    F = None
    for yc in (-0.02, 0.17, 0.36):          # tiny stubby nubs tucked under the belly and angled back
        L = smin(rcone(P, (0.17 * s, yc, 0.31), (0.20 * s, yc + 0.05, 0.19), 0.050, 0.038),
                 ell(P, (0.20 * s, yc + 0.06, 0.185), (0.045, 0.052, 0.036)), 0.03)
        F = L if F is None else smin(F, L, 0.03)
    SPEC[name] = dict(grid=g, F=F, comps={}, target=165, sym=False)


def build_jar():
    g = Grid((-0.28, -0.56, -0.03), (0.28, 0.02, 0.48), 0.015)
    P = g.P
    cx, cy, zc = JAR_C
    body = ell(P, JAR_C, (0.16, 0.16, 0.12))                       # round-bellied pot
    neck = rcyl(P, (cx, cy, zc + 0.125), 0.105, 0.02, 0.012)
    lid = rcyl(P, (cx, cy, zc + 0.165), 0.118, 0.022, 0.012)
    F = smin(smin(body, neck, 0.04), lid, 0.008)
    cord = None
    for s_ in (1, -1):
        cd = rcone(P, (0.09 * s_, cy + 0.015, zc + 0.16), (0.0, -0.13, 0.40), 0.028, 0.028)
        cord = cd if cord is None else smin(cord, cd, 0.02)
    F = smin(F, cord, 0.02)
    fy = cy - 0.155
    drip = ell(P, (0.05, fy, zc + 0.03), (0.042, 0.030, 0.09))
    drip = smin(drip, ell(P, (0.05, fy - 0.004, zc - 0.045), (0.048, 0.038, 0.048)), 0.035)
    drip = smin(drip, ell(P, (-0.07, fy + 0.006, zc + 0.05), (0.032, 0.026, 0.06)), 0.02)
    drip = smin(drip, ell(P, (0.0, cy - 0.115, zc + 0.105), (0.10, 0.065, 0.035)), 0.03)
    F = smin(F, drip, 0.02)
    SPEC["Jar"] = dict(grid=g, F=F, comps=dict(drip=drip, lid=lid, cord=cord), target=700, sym=False)


for fn, a_ in ((build_body, ()), (build_head, ()), (build_wing, (1,)), (build_wing, (-1,)), (build_stinger, ()),
               (build_legs, (1,)), (build_legs, (-1,)), (build_jar, ())):
    fn(*a_)
log("fields built")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
mat = bpy.data.materials.new("Bee_Atlas")
mat.use_nodes = True
OBJS, RAW = {}, {}
for name in PIVOTS:
    sp = SPEC[name]
    vs, fs = extract(sp["grid"], sp["F"], sp["target"], sp["sym"], PFX + name)
    RAW[name] = (vs, fs)
    bm = bmesh.new()
    bv = [bm.verts.new(tuple(v)) for v in vs]
    for fc in fs:
        try:
            bm.faces.new([bv[i] for i in fc])
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    piv = Vector(PIVOTS[name][0])
    me = bpy.data.meshes.new(PFX + name)
    bm.to_mesh(me)
    bm.free()
    me.transform(Matrix.Translation(-piv))
    me.materials.append(mat)
    ob = bpy.data.objects.new(PFX + name, me)
    ob.location = piv
    ob.pass_index = PID[name]
    scene.collection.objects.link(ob)
    OBJS[name] = ob
log("meshes", {n: len(o.data.polygons) for n, o in OBJS.items()})


def select_only(obs, active=None):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or obs[0]


# face frames on the head surface
hv, hf = RAW["Head"]
htree = BVHTree.FromPolygons([tuple(v) for v in hv], [tuple(f) for f in hf])


def frame_at(p, r=None, tilt=0.0):
    loc, nrm, _, _ = htree.find_nearest(Vector(p))
    n = np.array(nrm[:])
    u = np.array((1.0, 0, 0)) - n * n[0]
    u /= np.linalg.norm(u)
    v = np.cross(n, u)
    return dict(c=np.array(loc[:]), u=u, v=v, n=n, r=r, tilt=tilt)


FACE = {1: frame_at((0.18, -0.70, 0.69), (0.125, 0.145)), -1: frame_at((-0.18, -0.70, 0.69), (0.125, 0.145)),
        "mouth": frame_at((0.0, -0.72, 0.47))}
log("eye centres", FACE[1]["c"].round(3), FACE[-1]["c"].round(3), "mouth", FACE["mouth"]["c"].round(3))

# =============================================================================================
# UVs (one atlas)
# =============================================================================================
select_only(list(OBJS.values()))
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.0, scale_to_bounds=False)
bpy.ops.uv.select_all(action="SELECT")
bpy.ops.uv.average_islands_scale()
bpy.ops.uv.pack_islands(margin=0.006, rotate=True)
bpy.ops.object.mode_set(mode="OBJECT")
for o in OBJS.values():
    select_only([o])
    bpy.ops.object.shade_flat()
log("unwrapped")
def rgb(*c):
    return np.array(c, float) / 255.0


def mix(a, b, t):
    t = np.asarray(t, float)
    if t.ndim == 1:
        t = t[:, None]
    return a + (b - a) * t


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def vnoise(P, f, seed=0.0):
    q = P * f + seed
    i = np.floor(q)
    fr = q - i
    fr = fr * fr * (3 - 2 * fr)

    def h(dx, dy, dz):
        return np.abs(np.sin((i[:, 0] + dx) * 127.1 + (i[:, 1] + dy) * 311.7 + (i[:, 2] + dz) * 74.7) * 43758.5453) % 1.0
    out = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = ((fr[:, 0] if dx else 1 - fr[:, 0]) * (fr[:, 1] if dy else 1 - fr[:, 1]) * (fr[:, 2] if dz else 1 - fr[:, 2]))
                out = out + w * h(dx, dy, dz)
    return out

def cell_hash(a, b, k=0.0):
    v = np.sin(a * 12.9898 + b * 78.233 + k * 37.719) * 43758.5453
    return v - np.floor(v)


def stroke_masks(fu, fv, cw=0.14, ch=0.32, k=0.0):
    """Broad lens-shaped brush strokes laid along the coat flow on a jittered lattice (light, dark masks)."""
    row = np.floor(fv / ch)
    uu = fu / cw + cell_hash(row, 3.1, k) * 3.0
    col = np.floor(uu)
    h1, h2 = cell_hash(row, col, k + 1), cell_hash(row, col, k + 2)
    ly = fv / ch - row
    lx = uu - col - 0.5 - (h2 - 0.5) * 0.35
    a0, a1 = 0.05 + 0.2 * h2, 0.75 + 0.25 * h1
    t = np.clip((ly - a0) / np.maximum(a1 - a0, 1e-3), 0, 1)
    w = (0.22 + 0.12 * h1) * np.sin(np.pi * t) ** 0.8 * (1.0 - 0.4 * t)
    m = sstep(w + 0.02, np.maximum(w - 0.08, 0), np.abs(lx)) * (w > 0.02)
    return m * (h1 > 0.45), m * (h1 < 0.30)



HONEY = rgb(247, 190, 62)
HONEY_LT = rgb(255, 216, 108)
HONEY_DK = rgb(222, 146, 38)
MUZZLE = rgb(255, 222, 140)
BROWN = rgb(74, 46, 32)
BROWN_LT = rgb(124, 82, 48)
AMBER = rgb(238, 168, 50)
BLUSH = rgb(250, 150, 104)
EYE_DARK = rgb(40, 26, 30)
EYE_IRIS = rgb(128, 72, 40)
EYE_LINE = rgb(62, 40, 34)
PALE = rgb(226, 240, 250)
PALE_LT = rgb(246, 252, 255)
VEIN = rgb(150, 178, 210)
RIM = rgb(166, 198, 230)
GLASS = rgb(186, 200, 74)
GLASS_LT = rgb(216, 228, 108)
GLASS_DK = rgb(142, 158, 46)
DRIP = rgb(104, 196, 72)
DRIP_LT = rgb(178, 234, 118)
CORK = rgb(192, 138, 82)
CORK_DK = rgb(150, 98, 56)
LABEL = rgb(250, 236, 200)
LEATHER = rgb(142, 92, 56)


def zones_of(name, P):
    sp = SPEC[name]
    return {k: sp["grid"].sample(v, P) for k, v in sp["comps"].items()}


def fur_param(name, P):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    pole = np.ones(len(P))
    if name == "Body":
        fu, fv = np.arctan2(x, z - 0.5) * 0.33, y
        pole = sstep(0.04, 0.14, np.hypot(x, z - 0.5))
    elif name == "Head":
        fu, fv = np.arctan2(x, z - 0.7) * 0.30, y * 0.8
        pole = sstep(0.04, 0.14, np.hypot(x, z - 0.7))
    else:
        fu, fv = x * 0.8 + y * 0.5, -z
    return fu, fv, pole


def fur_paint(name, P, base, dark=None, cw=0.06, ch=0.15):
    """Painterly coat: value blotches plus broad brush strokes along the flow (2-4 value ranges)."""
    n1 = 0.6 * vnoise(P, 3.2) + 0.4 * vnoise(P, 6.5, 1)
    light_c = np.clip(base * 1.07 + 0.03, 0, 1)
    dark_c = base * np.array((0.90, 0.76, 0.58)) if dark is None else dark
    c = mix(base, light_c, 0.55 * sstep(0.52, 0.60, n1))
    c = mix(c, dark_c, 0.40 * sstep(0.42, 0.34, n1))
    fu, fv, pole = fur_param(name, P)
    a1, b1 = stroke_masks(fu, fv, cw, ch)
    a2, b2 = stroke_masks(fu * 1.7 + 0.37, fv * 1.6 + 0.11, cw, ch, k=5.0)
    c = mix(c, light_c, 0.50 * np.clip(a1 + 0.6 * a2, 0, 1) * pole)
    c = mix(c, dark_c, 0.45 * np.clip(b1 + 0.6 * b2, 0, 1) * pole)
    return c


def paint_body(P, Ns, Z):
    n = len(P)
    y, z = P[:, 1], P[:, 2]
    yy = y + (vnoise(P, 12.0, 3.0) - 0.5) * 0.07 + (vnoise(P, 24.0, 7.0) - 0.5) * 0.025   # soft fuzzy stripe edges
    e1, e2, e3, e4, w = 0.175, 0.375, 0.525, 0.665, 0.024
    dk = sstep(e1 - w, e1 + w, yy) * (1 - sstep(e2 - w, e2 + w, yy)) + sstep(e3 - w, e3 + w, yy) * (1 - sstep(e4 - w, e4 + w, yy))
    base = np.tile(HONEY, (n, 1))
    base = mix(base, HONEY_LT, 0.45 * sstep(-0.35, -0.7, Ns[:, 2]) * (1 - dk)[:, None][:, 0])    # lighter belly
    base = mix(base, rgb(176, 112, 44), 0.40 * sstep(0.70, 0.88, z) * sstep(0.26, 0.05, y))       # tan fuzzy shoulders
    base = mix(base, BROWN, dk)
    base = mix(base, BROWN_LT, 0.30 * dk * sstep(0.2, 0.8, Ns[:, 2]))
    return fur_paint("Body", P, base), np.zeros(n, bool)


def paint_head(P, Ns, Z):
    n = len(P)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    base = np.tile(HONEY, (n, 1))
    base = mix(base, HONEY_DK, 0.55 * sstep(0.86, 1.02, z))
    base = mix(base, HONEY_DK, 0.45 * sstep(-0.22, 0.02, y))
    dm = np.linalg.norm((P - np.array((0, -0.62, 0.56))) * np.array((1.0, 1.0, 1.3)), axis=1) / 0.30
    base = mix(base, MUZZLE, 0.85 * sstep(1.0, 0.35, dm))
    col = fur_paint("Head", P, base)
    for s in (1, -1):
        bd = np.linalg.norm((P - np.array((0.30 * s, -0.55, 0.56))) * np.array((1.0, 1.0, 1.5)), axis=1) / 0.12
        col = mix(col, BLUSH, 0.75 * sstep(1.0, 0.25, bd) * (Ns[:, 1] < -0.1))
    ant, tip = Z["ant"] < 0.012, Z["tip"] < 0.012
    col[ant] = mix(BROWN, BROWN_LT, 0.55 * sstep(0.2, 0.9, Ns[:, 2]) + 0.15 * (vnoise(P, 14.0) - 0.5))[ant]
    col[tip] = mix(AMBER, HONEY_LT, 0.6 * sstep(0.0, 0.8, Ns[:, 2]))[tip]
    hard = ant | tip
    after = []
    for side in (1, -1):
        e = FACE[side]
        d = P - e["c"]
        du, dv, dn = d @ e["u"], d @ e["v"], d @ e["n"]
        ru, rv = e["r"]
        eu, ev = du / ru, dv / rv
        front = (np.abs(dn) < 0.10) & ~ant
        r = np.sqrt(eu * eu + ev * ev)
        sdf = r - 1.0
        ring = front & (sdf > 0) & (sdf < 0.5)
        col[ring] = mix(col[ring], col[ring] * np.array((0.93, 0.80, 0.66)), (0.30 * sstep(0.5, 0.0, sdf))[ring])
        lw = 0.09 + 0.12 * sstep(0.0, 0.85, ev)
        lid = front & (sdf >= 0) & (sdf < lw)
        col[lid] = mix(col[lid], EYE_LINE, sstep(lw + 0.01, lw - 0.03, sdf)[lid])
        inside = front & (sdf < 0)
        ce = np.tile(EYE_DARK, (n, 1))
        ce = mix(ce, EYE_IRIS, 0.9 * sstep(0.2, 0.85, r) * sstep(0.25, -0.75, ev))
        ce = mix(ce, EYE_IRIS * 1.45, 0.5 * sstep(-0.35, -0.8, ev) * sstep(0.3, 0.8, r))
        col[inside] = ce[inside]
        after.append((inside, eu, ev))
    # mouth: small open smile (flat top, round bottom) with a pink tongue
    m = FACE["mouth"]
    d = P - m["c"]
    mu, mv, mn = d @ m["u"], d @ m["v"], d @ m["n"]
    mf = (np.abs(mn) < 0.08) & ~ant
    LINE = rgb(84, 44, 36)
    ru_, rv_ = 0.062, 0.050
    q = (mu / ru_) ** 2 + (mv / rv_) ** 2
    mouth_in = mf & (mv < 0.0) & (q < 1.0)
    outline = mf & (((q >= 1.0) & (q < 1.45) & (mv < 0.004)) | ((np.abs(mv) < 0.0075) & (np.abs(mu) < ru_ * 1.17)))
    col[mouth_in] = rgb(132, 52, 52)
    tq = (mu / 0.034) ** 2 + ((mv + 0.046) / 0.024) ** 2
    col[mouth_in & (tq < 1.0)] = rgb(244, 130, 130)
    col[outline] = mix(col[outline], LINE, 0.95)
    return col, hard, after


def paint_wing(P, Ns, s):
    n = len(P)
    d, c, nr = wing_frame(s)
    q = P - np.array(WING_ROOT[s])
    u, v = q @ d, q @ c
    d2 = wing_2d(u, v)
    base = np.tile(PALE, (n, 1))
    nz = vnoise(P, 5.0, 2.0)
    base = mix(base, PALE_LT, 0.6 * sstep(0.45, 0.62, nz) * sstep(-0.02, -0.10, d2))
    base = mix(base, RIM, 0.75 * sstep(-0.09, -0.01, d2))
    th = np.arctan2(v - 0.06, u + 0.05)
    vein = np.zeros(n)
    for t in (-0.5, -0.18, 0.15, 0.5, 0.85):
        vein = np.maximum(vein, np.exp(-((th - t) / 0.05) ** 2))
    vein *= sstep(0.03, 0.14, u) * sstep(-0.01, -0.07, d2)
    cross = np.exp(-((u - 0.40) / 0.013) ** 2) * sstep(-0.01, -0.08, d2)
    base = mix(base, VEIN, 0.5 * np.maximum(vein, 0.8 * cross))
    base = mix(base, HONEY_LT, 0.55 * sstep(0.14, 0.0, u))
    a1, b1 = stroke_masks(v + 0.2 * u, u, 0.07, 0.2, k=2.0)
    col = mix(base, np.clip(base * 1.05 + 0.03, 0, 1), 0.5 * a1)
    col = mix(col, base * np.array((0.95, 0.90, 0.90)), 0.35 * b1)
    return col, np.ones(n, bool)


def paint_stinger(P, Ns):
    t = (P - np.array(PIVOTS["Stinger"][0])) @ STING_DIR
    col = mix(np.tile(rgb(84, 52, 34), (len(P), 1)), rgb(176, 108, 44), sstep(0.05, 0.20, t))
    return col, np.ones(len(P), bool)


def paint_legs(P, Ns):
    z = P[:, 2]
    base = np.tile(rgb(176, 108, 48), (len(P), 1))
    base = mix(base, BROWN, 0.85 * sstep(0.21, 0.16, z))
    base = mix(base, HONEY, 0.85 * sstep(0.24, 0.30, z))
    return fur_paint("Leg", P, base), np.zeros(len(P), bool)


def paint_jar(P, Ns, Z):
    n = len(P)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    cy, zc = JAR_C[1], JAR_C[2]
    phi = np.arctan2(x, -(y - cy))
    zr = z - zc
    col = mix(rgb(206, 128, 34), rgb(242, 178, 52), sstep(-0.11, 0.0, zr))          # amber honey, deeper at the bottom
    col = mix(col, rgb(186, 176, 54), 0.55 * sstep(0.03, 0.12, zr))                  # a green tint creeping up to the rim
    col = mix(col, rgb(248, 238, 192), 0.55 * np.exp(-((phi + 0.9) / 0.14) ** 2) * sstep(-0.09, -0.05, zr) * sstep(0.12, 0.07, zr))
    lab = (np.abs(phi) < 0.85) & (zr > -0.07) & (zr < 0.065) & (Ns[:, 1] < -0.2)
    col[lab] = LABEL
    brd = lab & ((np.abs(phi) > 0.78) | (zr < -0.062) | (zr > 0.057))
    col[brd] = rgb(128, 86, 50)
    txt = lab & ~brd & (np.abs(phi) < 0.5) & ((np.abs(zr - 0.022) < 0.006) | (np.abs(zr + 0.006) < 0.006))
    col[txt] = rgb(128, 86, 50)
    lid = Z["lid"] < 0.012
    grain = 0.5 + 0.5 * np.sin(z * 260.0 + vnoise(P, 22.0) * 5.0)
    col[lid] = mix(CORK, CORK_DK, 0.6 * grain)[lid]
    cord = (Z["cord"] < 0.012) & ~lid
    col[cord] = mix(LEATHER, rgb(176, 120, 72), 0.5 * sstep(0.2, 0.9, Ns[:, 2]))[cord]
    dr = (Z["drip"] < 0.012) & ~lid
    dc = mix(DRIP, DRIP_LT, 0.55 * sstep(0.0, 0.8, Ns[:, 2] * 0.6 - Ns[:, 0] * 0.6 + 0.2))
    dc = mix(dc, DRIP * np.array((0.80, 0.90, 0.80)), 0.6 * sstep(0.04, -0.05, zr))
    col[dr] = dc[dr]
    return col, np.ones(n, bool)


def catchlights(col, after):
    for inside, eu, ev in after:
        g1 = np.sqrt(((eu + 0.30) / 0.36) ** 2 + ((ev - 0.38) / 0.32) ** 2)
        g2 = np.sqrt(((eu - 0.38) / 0.15) ** 2 + ((ev + 0.28) / 0.14) ** 2)
        m1, m2 = inside & (g1 < 1.0), inside & (g2 < 1.0)
        col[m1] = mix(col[m1], np.array((1.0, 1.0, 1.0)), sstep(1.0, 0.8, g1)[m1])
        col[m2] = mix(col[m2], np.array((1.0, 0.98, 0.94)), sstep(1.0, 0.75, g2)[m2])
    return col


# global SDF for ambient occlusion (rest pose)
GG = Grid((-0.85, -0.85, -0.06), (0.85, 1.15, 1.45), 0.025)
GF = None
for nm, sp in SPEC.items():
    v = sp["grid"].sample(sp["F"], GG.P.reshape(-1, 3))
    GF = v if GF is None else np.minimum(GF, v)
GF = GF.reshape(GG.P.shape[:3])


def ambient(P, N, ds):
    occ = 0.0
    for d in ds:
        sd = GG.sample(GF, P + N * d)
        occ = occ + np.clip(1.0 - sd / d, 0.0, 1.0)
    return 1.0 - occ / len(ds)


def light(col, P, Ns, Nf, pid, hard):
    Lk = np.array((-0.50, -0.62, 0.62))
    Lk /= np.linalg.norm(Lk)
    Lr = np.array((0.70, 0.62, 0.35))
    Lr /= np.linalg.norm(Lr)
    kf, ks = np.clip(Nf @ Lk, 0, 1), np.clip(Ns @ Lk, 0, 1)
    k = 0.90 * kf + 0.10 * ks                                  # mostly per-facet light: broad gem-cut planes
    sky = 0.5 + 0.5 * Ns[:, 2]
    lv = 0.54 + 0.50 * k + 0.12 * sky
    ao_s = ambient(P, Ns, (0.03, 0.055, 0.09))
    ao_l = ambient(P, Ns, (0.10, 0.17, 0.25))
    aof = (1.0 - 0.30 + 0.30 * sstep(0.15, 1.0, ao_s)) * (1.0 - 0.22 * (1.0 - sstep(0.2, 1.0, ao_l)))
    shade = lv * aof * (0.94 + 0.08 * sstep(0.0, 1.2, P[:, 2]))
    shade = shade * (0.945 + 0.11 * cell_hash(np.round(Nf[:, 0] * 40), np.round(Nf[:, 1] * 40) + 31 * np.round(Nf[:, 2] * 40), 2.0))   # per-facet value jitter
    wing = (pid == PID["WingL"]) | (pid == PID["WingR"])
    shade = np.where(wing, 0.74 + 0.26 * shade, shade)          # pale wings keep a light bake
    fq = shade * 6.0
    shade = 0.45 * shade + 0.55 * (np.floor(fq) + sstep(0.35, 0.65, fq - np.floor(fq))) / 6.0
    lit = col * shade[:, None]
    warmm = sstep(1.0, 0.8, shade) * sstep(0.55, 0.75, shade)
    lit = mix(lit, np.clip(lit * np.array((1.05, 0.96, 0.86)), 0, 1), 0.55 * warmm)
    lit = mix(lit, lit * np.array((1.0, 0.86, 0.72)), 0.55 * sstep(0.78, 0.45, shade))      # warm shadows, never grey
    lit = lit + (sstep(0.3, 1.0, Ns @ Lr) * 0.05)[:, None] * np.array((0.70, 0.80, 1.0))   # cool rim
    hl = np.clip(col * 1.12 + 0.08, 0, 1) * np.array((1.0, 0.96, 0.86))
    lit = mix(lit, hl, 0.30 * hard * sstep(-0.2, 0.6, Ns @ Lk))
    return np.clip(lit, 0, 1)

def raster(ob, S, buf):
    me = ob.data
    me.calc_loop_triangles()
    nl = len(me.loops)
    uv = np.empty(nl * 2)
    me.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2) * S
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3) + np.array(ob.location[:])
    vn = np.empty(len(me.vertices) * 3)
    me.vertex_normals.foreach_get("vector", vn)
    vn = vn.reshape(-1, 3)
    nt = len(me.loop_triangles)
    lo = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get("loops", lo)
    ve = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", ve)
    fnm = np.empty(nt * 3)
    me.loop_triangles.foreach_get("normal", fnm)
    lo, ve, fnm = lo.reshape(-1, 3), ve.reshape(-1, 3), fnm.reshape(-1, 3)
    cov, PP, NS, NF, PI = buf
    pid = ob.pass_index
    for t in range(nt):
        a, b, c = uv[lo[t, 0]], uv[lo[t, 1]], uv[lo[t, 2]]
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-9:
            continue
        x0, x1 = int(max(math.floor(min(a[0], b[0], c[0])), 0)), int(min(math.ceil(max(a[0], b[0], c[0])), S - 1))
        y0, y1 = int(max(math.floor(min(a[1], b[1], c[1])), 0)), int(min(math.ceil(max(a[1], b[1], c[1])), S - 1))
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w0 = ((b[1] - c[1]) * (X - c[0]) + (c[0] - b[0]) * (Y - c[1])) / den
        w1 = ((c[1] - a[1]) * (X - c[0]) + (a[0] - c[0]) * (Y - c[1])) / den
        w2 = 1 - w0 - w1
        m = (w0 >= -0.01) & (w1 >= -0.01) & (w2 >= -0.01)
        if not m.any():
            continue
        ys, xs = np.nonzero(m)
        ww = np.stack([w0[m], w1[m], w2[m]], 1)
        gy, gx = ys + y0, xs + x0
        cov[gy, gx] = True
        PP[gy, gx] = ww @ co[ve[t]]
        nn = ww @ vn[ve[t]]
        NS[gy, gx] = nn / np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-9)
        NF[gy, gx] = fnm[t]
        PI[gy, gx] = pid



log("rasterising at", RS)
cov = np.zeros((RS, RS), bool)
PP = np.zeros((RS, RS, 3), np.float32)
NS = np.zeros((RS, RS, 3), np.float32)
NF = np.zeros((RS, RS, 3), np.float32)
PI = np.zeros((RS, RS), np.int32)
for nm, ob in OBJS.items():
    raster(ob, RS, (cov, PP, NS, NF, PI))
idx = np.nonzero(cov)
P_ = PP[idx].astype(np.float64)
Ns_ = NS[idx].astype(np.float64)
Nf_ = NF[idx].astype(np.float64)
pid_ = PI[idx]
log("texels", len(P_))
col_ = np.zeros((len(P_), 3))
hard_ = np.zeros(len(P_), bool)
after = []
for nm in PIVOTS:
    m = pid_ == PID[nm]
    if not m.any():
        continue
    P, Ns = P_[m], Ns_[m]
    Z = zones_of(nm, P)
    if nm == "Body":
        c, h = paint_body(P, Ns, Z)
    elif nm == "Head":
        c, h, af = paint_head(P, Ns, Z)
        hm = np.nonzero(m)[0]
        after = [(hm[ins], eu[ins], ev[ins]) for ins, eu, ev in af]
    elif nm.startswith("Wing"):
        c, h = paint_wing(P, Ns, 1 if nm == "WingL" else -1)
    elif nm == "Stinger":
        c, h = paint_stinger(P, Ns)
    elif nm.startswith("Leg"):
        c, h = paint_legs(P, Ns)
    else:
        c, h = paint_jar(P, Ns, Z)
    col_[m], hard_[m] = c, h
for ix, eu, ev in after:
    ins = np.zeros(len(P_), bool)
    ins[ix] = True
    eu_, ev_ = np.zeros(len(P_)), np.zeros(len(P_))
    eu_[ix], ev_[ix] = eu, ev
    col_ = catchlights(col_, [(ins, eu_, ev_)])
lit = light(col_, P_, Ns_, Nf_, pid_, hard_)
log("lit")
img = np.zeros((RS, RS, 3), np.float32)
img[idx] = lit
cv = cov
if RS != ATLAS:
    w = cv.astype(np.float32)
    cw = (img * w[..., None]).reshape(ATLAS, 2, ATLAS, 2, 3).sum((1, 3))
    ws = w.reshape(ATLAS, 2, ATLAS, 2).sum((1, 3))
    img = cw / np.maximum(ws, 1)[..., None]
    cv = ws > 0
for _ in range(10):
    acc, cnt = np.zeros_like(img), np.zeros(cv.shape, np.float32)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        sm = np.roll(cv, (dy, dx), (0, 1))
        acc += np.roll(img, (dy, dx), (0, 1)) * sm[..., None]
        cnt += sm
    new = (~cv) & (cnt > 0)
    img[new] = acc[new] / cnt[new][:, None]
    cv = cv | new
img[~cv] = 0.6
rgba = np.concatenate([img, np.ones((ATLAS, ATLAS, 1), np.float32)], -1)
timg = bpy.data.images.new(STEM, ATLAS, ATLAS, alpha=False)
timg.pixels.foreach_set(rgba.ravel())
timg.filepath_raw = str(TEX_PATH)
timg.file_format = "PNG"
timg.save()
log("texture saved", TEX_PATH.name)

nt = mat.node_tree
for n_ in list(nt.nodes):
    nt.nodes.remove(n_)
tex_img = bpy.data.images.load(str(TEX_PATH), check_existing=False)
tex_img.name = STEM
bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
bs.inputs["Roughness"].default_value = 0.85
bs.inputs["Specular IOR Level"].default_value = 0.15
tx = nt.nodes.new("ShaderNodeTexImage")
tx.image = tex_img
nt.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
out_ = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(bs.outputs["BSDF"], out_.inputs["Surface"])


def tri_count(o):
    o.data.calc_loop_triangles()
    return len(o.data.loop_triangles)


tris = {PFX + n: tri_count(o) for n, o in OBJS.items()}
log("triangles", sum(tris.values()), tris)


# =============================================================================================
# reports (Studio axes = (-x, z, y) of Blender)
# =============================================================================================
bpy.context.view_layer.update()
parts = {o.name: o for o in OBJS.values()}
JOINT_PARENT = {PFX + n: (PFX + p if p else None) for n, (_, p) in PIVOTS.items()}
MOTION = {
    "Body": "root part: lifted HOVER_H studs above the ground while hovering, with a sine bob in Studio Y; pitch about Studio X for the sting dive",
    "Head": "nod = pitch about Studio X, tilt = roll about Studio Z, look = yaw about Studio Y, through the neck joint",
    "WingL": "flap = rotate about Studio Z (the front-back axis) through the wing root; positive Z = down for the bee's left wing",
    "WingR": "flap = rotate about Studio Z through the wing root; positive Z = UP for the bee's right wing (mirror of WingL)",
    "Stinger": "pitch about Studio X through the abdomen tip: rest points back and slightly down, -135 deg aims it down and a little forward for the sting",
    "LegL": "dangle: small pitch about Studio X through the hip (three stubby legs move together); tuck back in the dive",
    "LegR": "dangle: small pitch about Studio X through the hip (three stubby legs move together); tuck back in the dive",
    "Jar": "pendulum swing about Studio X (and a little Z) through the cord's top point inside the chest",
}


def studio(v):
    return [round(-v[0], 4) + 0.0, round(v[2], 4) + 0.0, round(v[1], 4) + 0.0]


def studio_size(v):
    return [round(v[0], 4), round(v[2], 4), round(v[1], 4)]


def world_bounds(o):
    ws = [o.matrix_world @ vv.co for vv in o.data.vertices]
    return (Vector([min(w[k] for w in ws) for k in range(3)]), Vector([max(w[k] for w in ws) for k in range(3)]))


report = {"asset": STEM, "blender_version": bpy.app.version_string,
          "authoring": "final Roblox stud size (1 Blender unit = 1 stud); import at 1:1, do not scale",
          "axes": "Blender Z-up, front -Y, the bee's left +X; modelled at rest, lowest point (the jar) at z of about 0.02 (hover offset is in studio-install-data.json)",
          "texture": f"textures/{TEX_PATH.name} ({ATLAS}x{ATLAS}, shared by every part)", "parts": {}}
lo_all, hi_all = Vector((1e9,) * 3), Vector((-1e9,) * 3)
for name, o in parts.items():
    me = o.data
    me.calc_loop_triangles()
    uvd = me.uv_layers.active.data
    us, vs_ = [d.uv.x for d in uvd], [d.uv.y for d in uvd]
    lo, hi = world_bounds(o)
    lo_all = Vector([min(lo_all[k], lo[k]) for k in range(3)])
    hi_all = Vector([max(hi_all[k], hi[k]) for k in range(3)])
    report["parts"][name] = {
        "triangles": len(me.loop_triangles), "vertices": len(me.vertices),
        "dimensions_studs": [round(v, 4) for v in o.dimensions],
        "bbox_min": [round(v, 4) for v in lo], "bbox_max": [round(v, 4) for v in hi],
        "pivot": [round(v, 4) for v in o.location], "joint_parent": JOINT_PARENT[name],
        "uv_range": [round(min(us), 4), round(max(us), 4), round(min(vs_), 4), round(max(vs_), 4)],
        "min_face_area": round(min(pl.area for pl in me.polygons), 8)}
report["total_triangles"] = sum(pp["triangles"] for pp in report["parts"].values())
size = hi_all - lo_all
report["overall"] = {"bbox_min": [round(v, 4) for v in lo_all], "bbox_max": [round(v, 4) for v in hi_all],
                     "height_studs": round(size.z, 4), "length_studs": round(size.y, 4), "width_studs": round(size.x, 4),
                     "height_with_hover_studs": round(size.z + HOVER_H, 4),
                     "head_top_studs": round(world_bounds(parts[PFX + "Head"])[1].z, 4)}
body_pivot = parts[PFX + "Body"].location.copy()
install = {
    "asset": STEM, "rarity": "Rare",
    "strong_suit": "poison (the stinger poisons enemies; the honey jar with green honey is the Rare charm)",
    "axis": "studio = (-x, z, y) of blender; Blender front -Y = Studio front -Z",
    "units": "studs; the model is at final size, import 1:1 and do not scale",
    "sides": "L/R are the bee's own left/right; its left is Blender +X = Studio -X",
    "origin": "all positions are relative to the model origin = the ground point under the world origin; the bee is modelled AT REST, lowest point (the jar) at Studio Y of about 0.02",
    "ground_point": studio((0.0, 0.0, 0.0)), "overall_size": studio_size(size), "overall_center": studio((lo_all + hi_all) / 2),
    "texture": f"textures/{TEX_PATH.name}",
    "texture_note": "one shared atlas; every MeshPart uses the same TextureID (Rare: no Neon, no glow; the green honey is painted)",
    "rest_rotation": "every part has identity rotation relative to the model at rest (wings rest 38 deg above horizontal and swept back 22 deg)",
    "rig": "one Motor6D per part: Part0 = joint_parent, Part1 = the part, C0/C1 placed at the part's pivot",
    "role_prop": "Bee_Jar: honey jar hung from a leather cord with a painted green (poison) honey drip; the sting/poison itself is game code",
    "parts": {}}
for name, o in parts.items():
    lo, hi = world_bounds(o)
    install["parts"][name] = {
        "center": studio((lo + hi) / 2), "size": studio_size(hi - lo), "pivot": studio(o.location),
        "pivot_from_body_pivot": studio(o.location - body_pivot), "pivot_is": "joint pivot",
        "joint_parent": JOINT_PARENT[name], "suggested_motion": MOTION[name.replace(PFX, "")]}
log("overall (w, len, h)", tuple(round(v, 3) for v in (size.x, size.y, size.z)), "tris", report["total_triangles"])

# World-axis degrees (Blender): rx about X (+ = nose down), ry about Y (the front-back axis: +ve swings the LEFT wing DOWN),
# rz about Z (yaw). Body_loc = (0, up, 0) in studs: the total lift of the body root above its rest position.
FR = {
    "hover_mid": dict(Body_loc=(0, HOVER_H, 0)),
    "wings_up": dict(WingL=(0, -30, 0), WingR=(0, 30, 0), LegL=(4, 0, 0), LegR=(4, 0, 0), Jar=(-4, 0, 0), Body_loc=(0, HOVER_H - 0.07, 0)),
    "wings_down": dict(WingL=(0, 62, 0), WingR=(0, -62, 0), LegL=(-3, 0, 0), LegR=(-3, 0, 0), Jar=(4, 0, 0), Body_loc=(0, HOVER_H + 0.07, 0)),
    "sting_windup": dict(Body=(-16, 0, 0), Head=(6, 0, 0), Stinger=(10, 0, 0), WingL=(0, -34, 0), WingR=(0, 34, 0),
                         LegL=(0, 0, 0), LegR=(0, 0, 0), Jar=(8, 0, 0), Body_loc=(0, HOVER_H + 0.18, 0)),
    "sting_dive": dict(Body=(38, 0, 0), Head=(-18, 0, 0), Stinger=(-135, 0, 0), WingL=(0, -30, 20), WingR=(0, 30, -20),
                       LegL=(6, 0, 0), LegR=(6, 0, 0), Jar=(-14, 0, 0), Body_loc=(0, 0.85, 0)),
}
FR_TIME = {"hover_mid": 0.0, "wings_up": 0.04, "wings_down": 0.04, "sting_windup": 0.22, "sting_dive": 0.18}
install["locomotion"] = "hover"
install["hover"] = {
    "hover_height_studs": HOVER_H,
    "overall_height_at_hover_studs": round(size.z + HOVER_H, 3),
    "how": "the model stands on the ground (lowest point (the jar) at Studio Y of about 0.02); lift the Body root by hover_height_studs (plus the bob) and keep every other part joined to it. The tiny leg nubs are tucked under the belly; nothing touches the ground while hovering.",
    "bob": {"amplitude_studs": 0.10, "period_s": 1.4, "formula": "body_up = hover_height_studs + amplitude_studs * sin(2*pi*t/period_s)",
            "extra": "pitch the Body +-4 deg about Studio X in time with the bob; nose-down when moving forward fast"},
    "wing_flap": {
        "frequency_hz": 12,
        "note": "alternate wings_up and wings_down every ~0.04 s (about 12 Hz, 2-3 frames at 60 fps; on the server just replicate the speed). Both wings mirror each other. "
                "Angles are DELTAS from the rest pose (wings 38 deg above horizontal, swept back 22 deg): up = 68 deg above horizontal, down = 24 deg below it.",
        "WingL_studio_rz_deg": {"up": -30, "down": 62}, "WingR_studio_rz_deg": {"up": 30, "down": -62},
        "body_lift_with_stroke": "the body rises 0.07 studs on the down stroke and sinks 0.07 on the up stroke"},
    "sting_dive": {
        "note": "windup (body nose-up, stinger tipped up), then dive: body pitched 38 deg nose-down, head -18 so it still looks at the target, "
                "stinger rotated -135 deg to aim down and slightly forward at the enemy, wings swept back and up, legs tucked a little, jar swung forward. "
                "Net result: the stinger points about 17 deg forward of straight down. Dive down to body_up 0.85 studs, hit, then recover to hover_mid.",
        "dive_distance_studs": 3.0, "recover_time_s": 0.35},
    "frames": {k: {"duration_s": FR_TIME[k], "body_up_studs": v["Body_loc"][1],
                   "joints": {PFX + b: {"blender_rot_deg": list(a), "studio_rot_deg": [-a[0], a[2], a[1]]}
                              for b, a in v.items() if not b.endswith("_loc")}} for k, v in FR.items()},
    "angle_convention": "blender_rot_deg = about world X, Y, Z; studio_rot_deg = [about Studio X, about Studio Y, about Studio Z] = [-bx, bz, by]. "
                        "Apply as CFrame.Angles(rad(sx), rad(sy), rad(sz)) in the joint's pivot frame, relative to the rest pose.",
}
objs = list(OBJS.values())
if not QUICK:
    (ROOT / "polygon-report.json").write_text(json.dumps(report, indent=2))
    (ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=2))
    select_only(objs, OBJS["Body"])
    bpy.ops.export_scene.gltf(filepath=str(GLB_PATH), export_format="GLB", use_selection=True, export_apply=True)
    select_only(objs, OBJS["Body"])
    bpy.ops.export_scene.fbx(filepath=str(FBX_PATH), use_selection=True, object_types={"MESH"}, axis_forward="-Z",
                             axis_up="Y", path_mode="COPY", embed_textures=True, add_leaf_bones=False)
    log("exported")

# armature for posing previews (exports above are the plain rigid parts)
arm_data = bpy.data.armatures.new("Bee_Rig")
arm = bpy.data.objects.new("Bee_Rig", arm_data)
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
drift = max((parts[n].matrix_world.translation - Vector(PIVOTS[n.replace(PFX, "")][0])).length for n in parts)
log("armature built; max pivot drift", round(drift, 6))



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
    log("saved blend")

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
add_sun("Rim", 2.0, (60, 0, 150), 10, (0.92, 0.94, 1.0))
add_sun("BackFill", 1.3, (70, 0, 200), 20, (1.0, 0.90, 0.78))
bpy.ops.mesh.primitive_circle_add(vertices=96, radius=90, fill_type="NGON", location=(0, 0, 0))
floor = bpy.context.object
floor.name = "Preview_Floor"
fm = bpy.data.materials.new("Preview_Floor")
fm.use_nodes = True
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.36, 0.40, 0.46, 1)
fm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
floor.data.materials.append(fm)
cam = bpy.data.objects.new("PreviewCam", bpy.data.cameras.new("PreviewCam"))
scene.collection.objects.link(cam)
scene.camera = cam


def shoot(path, loc, target, lens=85, res=(1200, 1200)):
    cam.data.type = "PERSP"
    cam.data.lens = lens
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
        x0 = pad + cidx * (tile + pad)
        y0 = head_h + r * (tile + lab_h + pad)
        im = bpy.data.images.load(str(path), check_existing=False)
        iw, ih = im.size
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
        tx_.image = im
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



tgt = V(0, 0.12, 1.25)
ft = V(0, -0.62, HOVER_H + 0.72)
D = 7.2
tgt_h = V(0, 0.12, HOVER_H + 0.55)
# every static render hovers at HOVER_H with the wings mid-flap and the ground shadow below
pose(dict(WingL=(0, -14, 0), WingR=(0, 14, 0), Body_loc=(0, HOVER_H, 0)))
POSES = [("Wings up (hover)", FR["wings_up"], (-0.75, -0.9, 0.2)),
         ("Wings down (hover)", FR["wings_down"], (-1, -0.2, 0.1)),
         ("Sting wind-up", FR["sting_windup"], (-1, 0.0, 0.1)),
         ("Sting dive: stinger aimed", FR["sting_dive"], (-1, 0.12, 0.08))]


def pose_shots(res, dist):
    out = []
    for i, (lab, rots, dirv) in enumerate(POSES):
        pose(rots)
        t = tgt_h if "dive" not in lab else V(0, 0.1, 1.05)
        out.append((shoot(OUT / f"_pose-{i}.png", around(t, dirv, dist * (0.68 if 'Sting' in lab else 1.0)), t, res=res), lab))
    pose({})
    return out


if QUICK:
    items = [(shoot(OUT / fn, loc, tgt), lab) for fn, lab, loc in (
        ("threeq.png", "Three-quarter", around(tgt, (-0.75, -0.9, 0.35), D)),
        ("front.png", "Front", around(tgt, (0, -1, 0.12), D)),
        ("side.png", "Side", around(tgt, (-1, 0, 0.10), D)),
        ("back.png", "Back", around(tgt, (0.35, 1, 0.3), D)))]
    items.append((shoot(OUT / "face-closeup.png", around(ft, (-0.3, -1, 0.08), 2.4), ft), "Face"))
    items += pose_shots((700, 700), 7.5)
    make_sheet(items, 4, 380, OUT / "quick-sheet.png", "bee quick", "quick run")
    for pth, _ in items[5:]:
        pth.unlink()
else:
    shots = [(shoot(OUT / fn, loc, tgt), lab) for fn, lab, loc in (
        ("threeq.png", "Three-quarter", around(tgt, (-0.75, -0.9, 0.35), D)),
        ("front.png", "Front", around(tgt, (0, -1, 0.12), D)),
        ("side.png", "Side (bee's right)", around(tgt, (-1, 0, 0.10), D)),
        ("back.png", "Back", around(tgt, (0.35, 1, 0.3), D)))]
    face = shoot(OUT / "face-closeup.png", around(ft, (-0.3, -1, 0.08), 2.4), ft, res=(1400, 1400))
    pose_items = pose_shots((900, 900), 7.5)
    make_sheet(pose_items, 2, 640, OUT / "pose-check.png", "Bee: hover and sting-dive pose check (wings up, wings down, wind-up, dive)",
               "Each part rotates about its own pivot (Blender armature, preview only). Look for gaps at neck, wing roots, stinger, legs, jar cord.")
    for pth, _ in pose_items:
        pth.unlink()
    make_sheet([shots[0], shots[1], shots[2], shots[3], (face, "Face close-up"), (OUT / "pose-check.png", "Hover / sting-dive pose check")],
               3, 520, OUT / "sheet.png", f"Bee pet (Rare, poison): {report['total_triangles']:,} tris, one 1024 atlas",
               "Blender 5.2 Eevee renders. Blender-verified, Studio untested.")
log("done")
