"""Bunny pet (Common, strong suit: team healing) for the roguelite.

Self-contained generator for background Blender 5.2:

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 \
        --python build_bunny.py
    ... -- --quick --out <dir>      iteration: 1024 raster, three Eevee views, no exports
    ... -- --pose                   (quick) also one pose render

Method (same family as the approved Golden Retriever, but the colour bake is a numpy rasteriser
instead of Cycles): every part is ONE fused surface (signed-distance fields joined with smooth
unions, OpenVDB isosurface, quadric decimate, edge-flip tidy), unwrapped into one 1024 atlas, and
the atlas is painted per texel from world position, normals, SDF ambient occlusion and the face /
ear / bandolier masks. No Cycles, no Studio.

Coordinates: Blender Z-up, 1 unit = 1 stud, the bunny sits on z = 0 and faces -Y; its own left is
+X. Studio = (-x, z, y) of Blender.
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
STEM = "bunny"
PFX = "Bunny_"
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
    print(f"[bunny {time.time() - T0:6.1f}s]", *a, flush=True)


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


def tidy(grid, F, vs, fs, passes=4):
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
# design (studs). Upright seated chibi bunny, big head, floppy lop ears, bandolier of carrots.
# =============================================================================================
BC = np.array((0.0, 0.12, 0.78))                # body centre
HC = np.array((0.0, -0.12, 1.60))               # skull centre
S_N = np.array((0.6, 0.0, 0.8))                 # bandolier: across-strap direction (carrot axis)
S_D = np.array((0.8, 0.0, -0.6))                # along the strap, bunny's right shoulder -> left hip
S_C = np.array((0.0, 0.12, 0.68))
BUCKLE_S = -0.38
STRAP_HW = 0.085
CARROT_S = (-0.24, 0.0, 0.24)
EAR_PTS = [(0.42, -0.06, 2.02), (0.58, -0.05, 1.98), (0.71, -0.05, 1.82), (0.77, -0.04, 1.60),
           (0.79, -0.04, 1.38), (0.79, -0.03, 1.22)]
EAR_HW = [0.17, 0.21, 0.23, 0.23, 0.21, 0.16]
EAR_TH = [0.105, 0.11, 0.11, 0.11, 0.10, 0.09]
EAR_A = math.radians(120)     # flat faces turn forward/inward so the pink lining shows
PIVOTS = {
    "Body": ((0.0, 0.10, 0.75), None),
    "Head": ((0.0, -0.05, 1.25), "Body"),
    "EarL": ((0.42, -0.06, 2.00), "Head"), "EarR": ((-0.42, -0.06, 2.00), "Head"),
    "LegFL": ((0.50, -0.04, 1.02), "Body"), "LegFR": ((-0.50, -0.04, 1.02), "Body"),
    "LegBL": ((0.40, 0.22, 0.42), "Body"), "LegBR": ((-0.40, 0.22, 0.42), "Body"),
    "Tail": ((0.0, 0.60, 0.52), "Body"),
}
PID = {n: i + 1 for i, n in enumerate(PIVOTS)}
SPEC = {}


def strap_surface(s, infl=(0.545, 0.525, 0.625)):
    x, z = S_C[0] + S_D[0] * s, S_C[2] + S_D[2] * s
    dx, dz = x - BC[0], z - BC[2]
    y = BC[1] - infl[1] * math.sqrt(max(1 - (dx / infl[0]) ** 2 - (dz / infl[2]) ** 2, 0.05))
    return np.array((x, y, z))


def build_body():
    g = Grid((-0.72, -0.66, 0.06), (0.72, 0.82, 1.50), 0.02)
    P = g.P
    base = ell(P, BC, (0.50, 0.48, 0.58))
    base = smin(base, ell(P, (0, -0.05, 0.62), (0.38, 0.32, 0.38)), 0.16)
    base = smin(base, ell(P, (0, 0.28, 0.52), (0.40, 0.36, 0.36)), 0.16)
    base = smin(base, ell(P, (0, 0.0, 1.12), (0.44, 0.36, 0.30)), 0.14)
    strap = smax(base - 0.045, np.abs((P - S_C) @ S_N) - STRAP_HW, 0.03)
    F = smin(base, strap, 0.025)
    carrot, leaf = None, None
    a = S_N + np.array((0, -0.15, 0))
    a /= np.linalg.norm(a)
    f = np.array((0, -1.0, 0))
    for s in CARROT_S:
        c = strap_surface(s) + np.array((0, 0.01, 0))
        tip, top = c - a * 0.19, c + a * 0.19
        ca = rcone(P, tip, top, 0.028, 0.108)
        carrot = ca if carrot is None else smin(carrot, ca, 0.01)
        for dvec in (a + S_D * 0.50, a - S_D * 0.50, a + f * 0.55):
            dv = dvec / np.linalg.norm(dvec)
            le = ell(P, top + a * 0.02 + dv * 0.10, (0.055, 0.125, 0.045), dir_axes(dv))
            leaf = le if leaf is None else smin(leaf, le, 0.02)
    F = smin(F, carrot, 0.02)
    F = smin(F, leaf, 0.02)
    bp = strap_surface(BUCKLE_S) + np.array((0, 0.0, 0.0))
    buckle = ell(P, bp, (0.078, 0.055, 0.088))
    F = smin(F, buckle, 0.015)
    SPEC["Body"] = dict(grid=g, F=F, comps=dict(strap=strap, carrot=carrot, leaf=leaf, buckle=buckle), target=2400, sym=False)


def build_head():
    g = Grid((-0.9, -1.0, 0.9), (0.9, 0.62, 2.25), 0.02, sym_x=True)
    P = g.P
    sk = ell(P, HC, (0.70, 0.60, 0.56))
    for s in (1, -1):
        sk = smin(sk, ell(P, (0.44 * s, -0.44, 1.36), (0.30, 0.27, 0.25)), 0.12)
    sk = smin(sk, ell(P, (0, -0.66, 1.39), (0.25, 0.16, 0.19)), 0.12)
    sk = smin(sk, ell(P, (0, -0.48, 1.17), (0.26, 0.22, 0.13)), 0.12)
    nose = ell(P, (0, -0.835, 1.47), (0.09, 0.06, 0.065))
    F = smin(sk, nose, 0.03)
    SPEC["Head"] = dict(grid=g, F=F, comps=dict(nose=nose), target=1500, sym=True)


def ear_frames(s):
    out = []
    n = len(EAR_PTS)
    for i, p in enumerate(EAR_PTS):
        p = np.array((p[0] * s, p[1], p[2]))
        nx, pv = EAR_PTS[min(i + 1, n - 1)], EAR_PTS[max(i - 1, 0)]
        t = np.array(((nx[0] - pv[0]) * s, nx[1] - pv[1], nx[2] - pv[2]))
        t /= np.linalg.norm(t)
        et = np.array((s * math.cos(EAR_A), -math.sin(EAR_A), 0.0))
        et = et - t * (et @ t)
        et /= np.linalg.norm(et)
        w = np.cross(t, et)
        w /= np.linalg.norm(w)
        out.append((p, t, et, w))
    return out


def build_ear(s):
    name = "EarL" if s > 0 else "EarR"
    lo = (0.18, -0.45, 1.0) if s > 0 else (-1.05, -0.45, 1.0)
    hi = (1.05, 0.35, 2.25) if s > 0 else (-0.18, 0.35, 2.25)
    g = Grid(lo, hi, 0.02)
    P = g.P
    F = None
    fr = ear_frames(s)
    for i, (p, t, et, w) in enumerate(fr):
        Lh = 0.5 * np.linalg.norm(np.array(fr[min(i + 1, len(fr) - 1)][0]) - np.array(fr[max(i - 1, 0)][0])) + 0.05
        e = ell(P, p, (EAR_TH[i], Lh, EAR_HW[i]), np.array([et, t, w]))
        F = e if F is None else smin(F, e, 0.06)
    SPEC[name] = dict(grid=g, F=F, comps={}, target=280, sym=False)


def build_arm(s):
    name = "LegFL" if s > 0 else "LegFR"
    sh, el, pw = (0.50 * s, -0.04, 1.02), (0.60 * s, -0.10, 0.82), (0.57 * s, -0.20, 0.64)
    g = Grid((0.2, -0.65, 0.3) if s > 0 else (-0.95, -0.65, 0.3), (0.95, 0.25, 1.35) if s > 0 else (-0.2, 0.25, 1.35), 0.02)
    P = g.P
    F = rcone(P, sh, el, 0.19, 0.175)
    F = smin(F, rcone(P, el, pw, 0.175, 0.155), 0.05)
    F = smin(F, ell(P, (0.57 * s, -0.25, 0.57), (0.16, 0.19, 0.14)), 0.07)
    for dx in (-0.065, 0.0, 0.065):
        F = smin(F, ell(P, (0.57 * s + dx, -0.41, 0.54), (0.058, 0.06, 0.052)), 0.035)
    SPEC[name] = dict(grid=g, F=F, comps={}, target=260, sym=False)


def build_leg(s):
    name = "LegBL" if s > 0 else "LegBR"
    g = Grid((0.05, -0.95, -0.02) if s > 0 else (-0.8, -0.95, -0.02), (0.8, 0.75, 0.85) if s > 0 else (-0.05, 0.75, 0.85), 0.02)
    P = g.P
    F = ell(P, (0.42 * s, 0.22, 0.36), (0.25, 0.36, 0.34))
    F = smin(F, ell(P, (0.40 * s, -0.28, 0.15), (0.18, 0.40, 0.15)), 0.12)
    for dx in (-0.085, 0.0, 0.085):
        F = smin(F, ell(P, (0.40 * s + dx, -0.66, 0.12), (0.068, 0.085, 0.072)), 0.035)
    SPEC[name] = dict(grid=g, F=F, comps={}, target=300, sym=False)


def build_tail():
    g = Grid((-0.5, 0.35, 0.2), (0.5, 1.2, 0.9), 0.02, sym_x=True)
    P = g.P
    c = np.array((0.0, 0.76, 0.52))
    F = ell(P, c, (0.25, 0.25, 0.25))
    for off in ((0.17, 0.10, 0.10), (-0.17, 0.10, 0.10), (0, 0.20, 0.08), (0.12, 0.12, -0.12), (-0.12, 0.12, -0.12),
                (0, 0.12, 0.19), (0, 0.05, -0.16)):
        F = smin(F, ell(P, c + np.array(off), (0.15, 0.15, 0.15)), 0.08)
    SPEC["Tail"] = dict(grid=g, F=F, comps={}, target=190, sym=True)


for fn, a_ in ((build_body, ()), (build_head, ()), (build_ear, (1,)), (build_ear, (-1,)), (build_arm, (1,)),
               (build_arm, (-1,)), (build_leg, (1,)), (build_leg, (-1,)), (build_tail, ())):
    fn(*a_)
log("fields built")

# =============================================================================================
# meshes
# =============================================================================================
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
mat = bpy.data.materials.new("Bunny_Atlas")
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


FACE = {1: frame_at((0.30, -0.85, 1.62), (0.14, 0.16)), -1: frame_at((-0.30, -0.85, 1.62), (0.14, 0.16)),
        "mouth": frame_at((0.0, -0.95, 1.36))}
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

# =============================================================================================
# painting
# =============================================================================================
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


CREAM = rgb(250, 232, 196)
TAN = rgb(232, 200, 152)
TAN_DK = rgb(214, 174, 124)
WHITE = rgb(255, 249, 234)
PINK_IN = rgb(246, 160, 172)
NOSE = rgb(236, 118, 140)
BLUSH = rgb(255, 168, 166)
EYE_DARK = rgb(52, 32, 40)
EYE_IRIS = rgb(128, 74, 52)
EYE_LINE = rgb(74, 46, 46)
LEATHER = rgb(150, 94, 56)
LEATHER_LT = rgb(186, 124, 76)
STITCH = rgb(238, 208, 154)
GOLD = rgb(240, 190, 76)
CARROT = rgb(244, 138, 52)
CARROT_DK = rgb(212, 96, 34)
LEAF = rgb(86, 166, 72)
LEAF_LT = rgb(146, 208, 98)
COOL = np.array((0.90, 0.92, 1.0))


def zones_of(name, P):
    """Sample this part's component fields at the texels: boolean masks per prop."""
    sp = SPEC[name]
    return {k: sp["grid"].sample(v, P) for k, v in sp["comps"].items()}


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


def fur_param(name, P):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    pole = np.ones(len(P))
    if name == "Body":
        fu, fv = np.arctan2(x, -(y - 0.12)) * 0.40, -z
    elif name == "Head":
        fu, fv = np.arctan2(x, -(y + 0.12)) * 0.45, -z
        pole = sstep(0.10, 0.28, np.hypot(x, y + 0.12))
    elif name.startswith("Ear"):
        fu, fv = y + 0.3 * x, -z
    elif name.startswith("LegF"):
        fu, fv = np.arctan2(x - 0.57 * np.sign(x), -(y + 0.2)) * 0.18, -z
    elif name.startswith("LegB"):
        fu, fv = np.arctan2(x - 0.40 * np.sign(x), -(y - 0.1)) * 0.18, -z + 0.5 * y
    else:
        fu, fv = x + 0.3 * np.arctan2(x, z - 0.52), 0.6 * y + 0.8 * z
    return fu, fv, pole


def fur_paint(name, P, base, dark=None):
    """Painterly coat: value blotches plus broad brush strokes along the flow (2-4 value ranges)."""
    n1 = 0.6 * vnoise(P, 2.0) + 0.4 * vnoise(P, 4.1, 1)
    light_c = np.clip(base * 1.07 + 0.025, 0, 1)
    dark_c = base * np.array((0.90, 0.81, 0.70)) if dark is None else dark
    c = mix(base, light_c, 0.55 * sstep(0.52, 0.60, n1))
    c = mix(c, dark_c, 0.40 * sstep(0.42, 0.34, n1))
    fu, fv, pole = fur_param(name, P)
    a1, b1 = stroke_masks(fu, fv)
    a2, b2 = stroke_masks(fu * 1.7 + 0.37, fv * 1.6 + 0.11, k=5.0)
    c = mix(c, light_c, 0.50 * np.clip(a1 + 0.6 * a2, 0, 1) * pole)
    c = mix(c, dark_c, 0.45 * np.clip(b1 + 0.6 * b2, 0, 1) * pole)
    return c


TAN2 = rgb(226, 184, 130)


def paint_body(P, Ns, Z):
    n = len(P)
    back = np.clip(sstep(0.0, 0.45, P[:, 1]) * 0.75 + sstep(0.95, 1.4, P[:, 2]) * 0.3, 0, 1)
    base = mix(np.tile(CREAM, (n, 1)), TAN2, back)
    belly = sstep(-0.05, -0.42, Ns[:, 1]) * sstep(1.15, 0.6, P[:, 2])
    base = mix(base, WHITE, 0.8 * belly)
    col = fur_paint("Body", P, base)
    hard = np.zeros(n, bool)
    strap = Z["strap"] < 0.012
    off = (P - S_C) @ S_N
    nz = vnoise(P, 9.0) - 0.5
    col[strap] = mix(LEATHER, LEATHER_LT, 0.55 * sstep(0.3, 0.9, Ns[:, 1] * -1.0)[strap] + 0.15 * nz[strap])
    along = (P - S_C) @ S_D
    st = strap & (np.abs(np.abs(off) - 0.057) < 0.0085) & (((along / 0.055) % 1.0) < 0.55)
    col[st] = STITCH
    hard |= strap
    lf, cr, bk = Z["leaf"] < 0.012, Z["carrot"] < 0.012, Z["buckle"] < 0.012
    ridge = np.abs(np.sin((P @ S_N) * 30.0))
    cc = mix(CARROT, CARROT_DK, 0.55 * sstep(0.25, 0.05, ridge))
    col[cr] = cc[cr]
    col[lf] = mix(LEAF, LEAF_LT, sstep(0.0, 0.8, nz * 2.0 + 0.5 + Ns[:, 2] * 0.4))[lf]
    bl = P - strap_surface(BUCKLE_S)
    inner = bk & (np.abs(bl[:, 0]) < 0.032) & (np.abs(bl[:, 2]) < 0.045) & (Ns[:, 1] < -0.3)
    col[bk] = GOLD
    col[inner] = LEATHER
    hard |= lf | cr | bk
    return col, hard


def paint_head(P, Ns, Z):
    n = len(P)
    base = np.tile(CREAM, (n, 1))
    base = mix(base, TAN2, np.clip(0.55 * sstep(1.78, 2.12, P[:, 2]) + 0.6 * sstep(-0.15, 0.35, P[:, 1]), 0, 1))
    face = sstep(-0.35, -0.72, P[:, 1]) * sstep(1.95, 1.45, P[:, 2])
    base = mix(base, WHITE, 0.45 * face)
    dm = np.linalg.norm((P - np.array((0, -0.70, 1.38))) * np.array((1.0, 1.0, 1.1)), axis=1) / 0.33
    base = mix(base, WHITE, 0.85 * sstep(1.0, 0.45, dm))
    col = fur_paint("Head", P, base)
    for s in (1, -1):
        bd = np.linalg.norm((P - np.array((0.50 * s, -0.52, 1.40))) * np.array((1.0, 1.0, 1.5)), axis=1) / 0.17
        col = mix(col, BLUSH, 0.7 * sstep(1.0, 0.25, bd) * (Ns[:, 1] < -0.1))
    nose = Z["nose"] < 0.010
    col[nose] = NOSE
    hard = nose.copy()
    sh = nose & (Ns[:, 2] > 0.35) & (Ns[:, 1] < -0.3)
    col[sh] = mix(col[sh], rgb(255, 214, 220), 0.7)
    after = []
    for side in (1, -1):
        e = FACE[side]
        d = P - e["c"]
        du, dv, dn = d @ e["u"], d @ e["v"], d @ e["n"]
        ru, rv = e["r"]
        eu, ev = du / ru, dv / rv
        front = (np.abs(dn) < 0.10) & ~nose
        r = np.sqrt(eu * eu + ev * ev)
        sdf = r - 1.0
        ring = front & (sdf > 0) & (sdf < 0.5)
        col[ring] = mix(col[ring], col[ring] * np.array((0.93, 0.87, 0.82)), (0.18 * sstep(0.5, 0.0, sdf))[ring])
        lw = 0.09 + 0.12 * sstep(0.0, 0.85, ev)
        lid = front & (sdf >= 0) & (sdf < lw)
        col[lid] = mix(col[lid], EYE_LINE, sstep(lw + 0.01, lw - 0.03, sdf)[lid])
        inside = front & (sdf < 0)
        ce = np.tile(EYE_DARK, (n, 1))
        ce = mix(ce, EYE_IRIS, 0.9 * sstep(0.2, 0.85, r) * sstep(0.25, -0.75, ev))
        ce = mix(ce, EYE_IRIS * 1.45, 0.5 * sstep(-0.35, -0.8, ev) * sstep(0.3, 0.8, r))
        col[inside] = ce[inside]
        after.append((inside, eu, ev))
    # mouth: thick philtrum, a bold "w", two big buck teeth with a clear outline
    m = FACE["mouth"]
    d = P - m["c"]
    mu, mv, mn = d @ m["u"], d @ m["v"], d @ m["n"]
    mf = (np.abs(mn) < 0.08) & ~nose
    LINE = rgb(70, 40, 42)
    col[mf & (np.abs(mu) < 0.0145) & (mv < 0.0) & (mv > -0.085)] = LINE
    sa = np.abs(mu) / 0.13
    curve = -0.085 - 0.05 * np.sin(np.pi * np.clip(sa, 0, 1) * 0.92) + 0.03 * sa ** 3
    wl = mf & (sa < 1.0) & (np.abs(mv - curve) < 0.0165)
    col[wl] = mix(col[wl], LINE, 0.97)
    tt = mf & (np.abs(mu) < 0.058) & (mv < -0.090) & (mv > -0.205)
    col[tt] = rgb(255, 252, 244)
    tl = mf & (((np.abs(mu) < 0.008) & (mv < -0.090) & (mv > -0.205))
               | ((np.abs(np.abs(mu) - 0.058) < 0.009) & (mv < -0.090) & (mv > -0.205))
               | ((np.abs(mu) < 0.067) & (np.abs(mv + 0.205) < 0.009)))
    col[tl] = mix(col[tl], rgb(120, 86, 80), 0.95)
    for sx in (1, -1):
        for (dx, dz) in ((0.20, 0.0), (0.24, 0.06), (0.18, 0.10)):
            wd = np.sqrt((mu - sx * dx) ** 2 + (mv - dz - 0.04) ** 2)
            wm = mf & (wd < 0.017)
            col[wm] = mix(col[wm], TAN_DK * 0.85, 0.85)
    return col, hard, after


def paint_ear(P, Ns, s):
    n = len(P)
    base = np.tile(mix(CREAM, TAN2, 0.45), (n, 1))
    base = mix(base, TAN_DK, 0.4 * sstep(1.55, 1.2, P[:, 2]))
    col = fur_paint("Ear", P, base)
    zs = np.array([p[2] for p in EAR_PTS])[::-1]
    cen = np.stack([np.interp(P[:, 2], zs, np.array([p[k] * (s if k == 0 else 1) for p in EAR_PTS])[::-1]) for k in range(3)], 1)
    hw = np.interp(P[:, 2], zs, np.array(EAR_HW)[::-1])
    w0 = np.array((math.sin(EAR_A) * s, math.cos(EAR_A), 0.0))
    et = np.array((s * math.cos(EAR_A), -math.sin(EAR_A), 0.0))
    frac = np.abs((P - cen) @ w0) / hw
    face = sstep(0.15, 0.40, Ns @ et)                      # the flat face looking forward / toward the head
    pink = face * sstep(0.92, 0.62, frac) * sstep(1.12, 1.40, P[:, 2]) * sstep(2.03, 1.85, P[:, 2])
    pk = mix(rgb(255, 150, 170), rgb(255, 196, 204), 0.45 * sstep(0.2, 0.75, frac))
    pk = mix(pk, PINK_IN * 0.93, 0.35 * sstep(0.45, 0.75, vnoise(P, 8.0, 2.0)))
    return mix(col, pk, pink), pink > 0.4


def paint_limb(name, P, Ns):
    n = len(P)
    base = np.tile(CREAM, (n, 1))
    dark = None
    if name.startswith("LegB"):
        base = mix(base, TAN2, np.clip(0.45 * sstep(0.35, 0.75, P[:, 2]) * sstep(-0.1, 0.4, P[:, 1]) + 0.25 * sstep(0.5, 0.8, P[:, 2]), 0, 1))
        base = mix(base, WHITE, 0.75 * sstep(0.30, 0.10, P[:, 2]))
    elif name.startswith("LegF"):
        base = mix(base, WHITE, 0.6 * sstep(0.68, 0.5, P[:, 2]))
        base = mix(base, TAN2, 0.4 * sstep(0.85, 1.12, P[:, 2]))
    else:   # cotton tail: clearly white, warm peach shadows
        base = np.tile(rgb(255, 251, 240), (n, 1))
        dark = np.tile(rgb(248, 224, 192), (n, 1))
    return fur_paint(name, P, base, dark), np.zeros(n, bool)


def catchlights(col, after):
    for inside, eu, ev in after:
        g1 = np.sqrt(((eu + 0.30) / 0.36) ** 2 + ((ev - 0.38) / 0.32) ** 2)
        g2 = np.sqrt(((eu - 0.38) / 0.15) ** 2 + ((ev + 0.28) / 0.14) ** 2)
        m1, m2 = inside & (g1 < 1.0), inside & (g2 < 1.0)
        col[m1] = mix(col[m1], np.array((1.0, 1.0, 1.0)), sstep(1.0, 0.8, g1)[m1])
        col[m2] = mix(col[m2], np.array((1.0, 0.98, 0.94)), sstep(1.0, 0.75, g2)[m2])
    return col


# global SDF for ambient occlusion
GG = Grid((-1.15, -1.05, -0.06), (1.15, 1.15, 2.3), 0.03)
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
    fw = np.where(hard, 0.6, 0.55)
    k = fw * kf + (1 - fw) * ks
    sky = 0.5 + 0.5 * Ns[:, 2]
    lv = 0.70 + 0.30 * k + 0.12 * sky
    ao_s = ambient(P, Ns, (0.05, 0.09, 0.14))
    ao_l = ambient(P, Ns, (0.2, 0.32, 0.46))
    head = (pid == PID["Head"])
    ao_w = np.where(head, 0.22, 0.32)
    aol_w = np.where(head, 0.10, 0.22)
    aof = (1.0 - ao_w + ao_w * sstep(0.15, 1.0, ao_s)) * (1.0 - aol_w * (1.0 - sstep(0.2, 1.0, ao_l)))
    shade = lv * aof * (0.92 + 0.10 * sstep(0.0, 2.0, P[:, 2]))
    shade = np.where(pid == PID["Tail"], 0.52 + 0.48 * shade, shade)     # the white tail keeps a warm, light bake
    fq = shade * 5.0
    shade = 0.6 * shade + 0.4 * (np.floor(fq) + sstep(0.35, 0.65, fq - np.floor(fq))) / 5.0
    lit = col * shade[:, None]
    warmm = sstep(1.0, 0.8, shade) * sstep(0.55, 0.75, shade)
    lit = mix(lit, np.clip(lit * np.array((1.05, 0.96, 0.86)), 0, 1), 0.55 * warmm)
    lit = mix(lit, lit * np.array((1.0, 0.90, 0.80)), 0.55 * sstep(0.78, 0.45, shade))
    lit = lit + (sstep(0.3, 1.0, Ns @ Lr) * 0.08)[:, None] * np.array((0.70, 0.80, 1.0))
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
    elif nm.startswith("Ear"):
        c, h = paint_ear(P, Ns, 1 if nm == "EarL" else -1)
    else:
        c, h = paint_limb(nm, P, Ns)
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
    "Body": "root part: a small bob up/down in Studio Y while following",
    "Head": "nod = pitch about Studio X, tilt = roll about Studio Z, look = yaw about Studio Y, through the neck joint",
    "EarL": "flop = rotate about Studio Z (front-back axis) through the ear base; child of the head",
    "EarR": "flop = rotate about Studio Z (front-back axis) through the ear base; child of the head",
    "LegFL": "arm swing about Studio X through the shoulder",
    "LegFR": "arm swing about Studio X through the shoulder",
    "LegBL": "hind leg swing about Studio X through the hip (thigh and big foot move together)",
    "LegBR": "hind leg swing about Studio X through the hip (thigh and big foot move together)",
    "Tail": "wag = yaw about Studio Y through the tail root (lift = pitch about Studio X)",
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
          "axes": "Blender Z-up, front -Y, the bunny's left +X; sits on z = 0",
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
                     "head_top_studs": round(world_bounds(parts[PFX + "Head"])[1].z, 4)}
body_pivot = parts[PFX + "Body"].location.copy()
install = {
    "asset": STEM, "rarity": "Common", "strong_suit": "team healing (carrot drop every 10 s heals you or the closest hurt teammate)",
    "axis": "studio = (-x, z, y) of blender; Blender front -Y = Studio front -Z",
    "units": "studs; the model is at final size, import 1:1 and do not scale",
    "sides": "L/R are the bunny's own left/right; its left is Blender +X = Studio -X",
    "origin": "all positions are relative to the model origin = the ground point under the body pivot (Blender world origin)",
    "ground_point": studio((0.0, 0.0, 0.0)), "overall_size": studio_size(size), "overall_center": studio((lo_all + hi_all) / 2),
    "texture": f"textures/{TEX_PATH.name}",
    "texture_note": "one shared atlas; every MeshPart uses the same TextureID (Common rarity: no Neon, no glow)",
    "rest_rotation": "every part has identity rotation relative to the model at rest",
    "rig": "one Motor6D per part: Part0 = joint_parent, Part1 = the part, C0/C1 placed at the part's pivot",
    "role_prop": "carrot bandolier (strap, four carrots with leafy tops, buckle) is part of Bunny_Body; the carrot drop itself is game code",
    "parts": {}}
for name, o in parts.items():
    lo, hi = world_bounds(o)
    install["parts"][name] = {
        "center": studio((lo + hi) / 2), "size": studio_size(hi - lo), "pivot": studio(o.location),
        "pivot_from_body_pivot": studio(o.location - body_pivot), "pivot_is": "joint pivot",
        "joint_parent": JOINT_PARENT[name], "suggested_motion": MOTION[name.replace(PFX, "")]}
log("overall (w, len, h)", tuple(round(v, 3) for v in (size.x, size.y, size.z)), "tris", report["total_triangles"])

HOP = {   # Blender bone-axis degrees: X = pitch about world X. Body_loc = (0, up, 0) in studs.
    "crouch": dict(Body=(8, 0, 0), Head=(-6, 0, 0), LegFL=(-20, 0, 0), LegFR=(-20, 0, 0), LegBL=(0, 0, 0), LegBR=(0, 0, 0),
                   EarL=(10, 0, 0), EarR=(10, 0, 0), Tail=(0, 0, 0), Body_loc=(0, 0, 0)),
    "launch": dict(Body=(-30, 0, 0), Head=(10, 0, 0), LegFL=(35, 0, 0), LegFR=(35, 0, 0), LegBL=(185, 0, 0), LegBR=(185, 0, 0),
                   EarL=(40, 0, 0), EarR=(40, 0, 0), Tail=(-15, 0, 0), Body_loc=(0, 0.25, 0)),
    "airborne": dict(Body=(-12, 0, 0), Head=(0, 0, 0), LegFL=(-75, 0, 0), LegFR=(-75, 0, 0), LegBL=(175, 0, 0), LegBR=(175, 0, 0),
                     EarL=(62, 0, 0), EarR=(62, 0, 0), Tail=(20, 0, 0), Body_loc=(0, 0.85, 0)),
    "land": dict(Body=(10, 0, 0), Head=(-10, 0, 0), LegFL=(-55, 0, 0), LegFR=(-55, 0, 0), LegBL=(40, 0, 0), LegBR=(40, 0, 0),
                 EarL=(30, 0, 0), EarR=(30, 0, 0), Tail=(10, 0, 0), Body_loc=(0, 0.12, 0)),
}
HOP_TIME = {"crouch": 0.15, "launch": 0.10, "airborne": 0.40, "land": 0.15}
install["locomotion"] = "hop"
install["hop"] = {
    "suggested_hop_height_studs": 0.9, "suggested_hop_length_studs": 3.0,
    "note": "Rest pose = the crouch. Angles are about each bone's pivot (Blender X axis = pitch). A rotation of +a about Blender +X "
            "is -a about Studio +X (Studio = (-x, z, y)), given as studio_rx_deg. Positive Blender X swings a forward-pointing part "
            "down and then back; negative lifts the front. body_up_studs lifts the whole body root (Studio Y). Tween between frames.",
    "frames": {k: {"duration_s": HOP_TIME[k], "body_up_studs": v["Body_loc"][1],
                   "joints": {PFX + b: {"blender_rx_deg": a[0], "studio_rx_deg": -a[0]} for b, a in v.items() if not b.endswith("_loc")}}
               for k, v in HOP.items()},
    "hind_legs": "pivot at the hip (inside the thigh); +175..185 deg (with the body pitched up 12..30) extends thigh and foot straight back on launch and in flight, +40 lands toes-first",
    "front_legs": "pivot at the shoulder; -55..-75 reaches forward and down for the landing, +35 sweeps back on launch",
    "ears": "rotate about X at the ear base; +40..62 trails them back while airborne",
    "total_cycle_s": round(sum(HOP_TIME.values()), 2),
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
arm_data = bpy.data.armatures.new("Bunny_Rig")
arm = bpy.data.objects.new("Bunny_Rig", arm_data)
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
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = [math.radians(v) for v in rots.get(pb.name, (0, 0, 0))]
        pb.location = rots.get(pb.name + "_loc", (0, 0, 0))   # bone axes: Y = world up
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


tgt = V(0, -0.05, 1.08)
ft = V(0, -0.75, 1.50)
D = 9.6
TROT_A = {"LegFL": (28, 0, 0), "LegBR": (28, 0, 0), "LegFR": (-28, 0, 0), "LegBL": (-28, 0, 0)}
if QUICK:
    shoot(OUT / "threeq.png", around(tgt, (-0.75, -0.9, 0.35), D), tgt)
    shoot(OUT / "front.png", around(tgt, (0, -1, 0.12), D), tgt)
    shoot(OUT / "face-closeup.png", around(ft, (-0.3, -1, 0.08), 4.2), ft)
    if "--pose" in ARGS:
        pose(dict(TROT_A, Head=(-15, 18, 20), Tail=(0, 30, 0), EarL=(0, 0, 25), EarR=(0, 0, 25)))
        shoot(OUT / "pose-quick.png", around(tgt, (-0.8, -0.7, 0.3), D), tgt)
        pose({})
else:
    shots = [(shoot(OUT / fn, loc, tgt), lab) for fn, lab, loc in (
        ("threeq.png", "Three-quarter", around(tgt, (-0.75, -0.9, 0.35), D)),
        ("front.png", "Front", around(tgt, (0, -1, 0.12), D)),
        ("side.png", "Side (bunny's right)", around(tgt, (-1, 0, 0.10), D)),
        ("back.png", "Back", around(tgt, (0.35, 1, 0.3), D)))]
    face = shoot(OUT / "face-closeup.png", around(ft, (-0.3, -1, 0.08), 4.2), ft, res=(1400, 1400))
    tgt2 = tgt + V(0, 0, 0.35)
    poses = [(f"Hop {i + 1}: {k}", HOP[k], around(tgt2, (-1, 0.05, 0.12), 11.5), tgt2) for i, k in enumerate(HOP)]
    pose_items = []
    for i, (lab, rots, loc, t) in enumerate(poses):
        pose(rots)
        pose_items.append((shoot(OUT / f"_pose-{i}.png", loc, t, res=(900, 900)), lab))
    pose({})
    make_sheet(pose_items, 2, 640, OUT / "pose-check.png", "Bunny: hop pose check (crouch, launch, airborne, land)",
               "Each part rotates about its own pivot (Blender armature, preview only). Look for gaps at shoulders, hips, neck, ears, tail.")
    for pth, _ in pose_items:
        pth.unlink()
    make_sheet([shots[0], shots[1], shots[2], shots[3], (face, "Face close-up"), (OUT / "pose-check.png", "Hop pose check")],
               3, 520, OUT / "sheet.png", f"Bunny pet (Common, team healing): {report['total_triangles']:,} tris, one 1024 atlas",
               "Blender 5.2 Eevee renders. Blender-verified, Studio untested.")
log("done")
