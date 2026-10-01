"""Frog pet (Common, strong suit: space / knockback) for the roguelite.

Builds the whole art asset from scratch in background Blender 5.2. Self-contained: the fused-surface
method, bake, painter, export and preview code are adapted from the approved Golden Retriever
generator (copied, not imported).

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 \
        --python build_frog.py
    ... -- --flat --out <dir>       shape check: flat zone colours, three Eevee views, nothing else
    ... -- --quick --out <dir>      iteration: 1024 bake, four Eevee views, no exports
    ... -- --no-previews            exports + reports only

Writes (inside this folder): frog.blend, textures/frog.png (1024 atlas shared by every part),
exports/fbx + exports/glb, polygon-report.json, studio-install-data.json and previews/*.png.

Coordinates: Blender Z-up, 1 unit = 1 stud (final size, import 1:1), feet on z = 0, the frog faces -Y
and its own left is +X. Studio = (-x, z, y) of Blender, so Studio front is -Z.

Look: stylized chibi low-poly. Every body part is ONE fused surface (voxel union -> smooth -> decimate);
the eyes are domes fused into the head, the face (irises, catchlights, mouth line, nostrils, cheeks) is
painted over shallow relief. Common rarity: no glow, no Neon.
"""
import json
import math
import random
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
STEM = "frog"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    if name in ARGS:
        i = ARGS.index(name)
        if i + 1 < len(ARGS):
            return ARGS[i + 1]
    return default


QUICK = "--quick" in ARGS
FLAT = "--flat" in ARGS
NO_PREVIEWS = "--no-previews" in ARGS
MESH = arg("--mesh", "lattice")          # lattice: even coarse facets (kept); quadric: adaptive collapse
OUT = Path(arg("--out", str(ROOT / "previews")))
TEX_PATH = ROOT / "textures" / f"{STEM}.png"
FBX_PATH = ROOT / "exports" / "fbx" / f"{STEM}.fbx"
GLB_PATH = ROOT / "exports" / "glb" / f"{STEM}.glb"
BLEND_PATH = ROOT / f"{STEM}.blend"
ATLAS = 1024
BAKE = 1024 if QUICK else 2048
SMOOTH_ANGLE = 34.0
for d in (TEX_PATH.parent, FBX_PATH.parent, GLB_PATH.parent, OUT):
    d.mkdir(parents=True, exist_ok=True)


def log(*a):
    print(f"[frog {time.time() - T0:6.1f}s]", *a, flush=True)


Z_SKIN, Z_LEATHER, Z_GOLD = range(1, 4)
P_BODY, P_HEAD, P_LEGFL, P_LEGFR, P_LEGBL, P_LEGBR = range(1, 7)

RNG = random.Random(20260929)


def V(*a):
    return Vector(a if len(a) == 3 else a[0])


def se(a, n):
    c, s = math.cos(a), math.sin(a)
    return math.copysign(abs(c) ** (2.0 / n), c), math.copysign(abs(s) ** (2.0 / n), s)


def gauss(x, w):
    return math.exp(-(x / w) ** 2)


def angdiff(a, b):
    return (a - b + math.pi) % (2 * math.pi) - math.pi


# =============================================================================================
# mesh builder
# =============================================================================================

class Part:
    def __init__(self, name, pid, pivot, joint):
        self.name, self.pid, self.pivot, self.joint = name, pid, Vector(pivot), joint
        self.bm = bmesh.new()
        self.zl = self.bm.faces.layers.float.new("zone")
        self.tl = self.bm.verts.layers.float.new("tuft_t")
        self.fl = [self.bm.verts.layers.float.new(f"flow_{c}") for c in "xyz"]
        self.ll = self.bm.verts.layers.float.new("lock")
        self.new_faces = []

    def v(self, co, t=0.0, flow=(0.0, 0.0, 0.0), lock=0.0):
        vv = self.bm.verts.new(co)
        vv[self.tl] = t
        vv[self.ll] = lock
        for k in range(3):
            vv[self.fl[k]] = flow[k]
        return vv

    def add_mesh(self, verts, faces, zone, tuft=None, flow=None):
        """Append a finished surface (numpy verts + face index lists), e.g. a fused fur isosurface."""
        vs = [self.v(tuple(verts[i]), float(tuft[i]) if tuft is not None else 0.0,
                     tuple(flow[i]) if flow is not None else (0.0, 0.0, 0.0), 1.0) for i in range(len(verts))]
        made = 0
        for fc in faces:
            if self.f([vs[i] for i in fc]) is not None:
                made += 1
        log(self.name, "add_mesh faces", made, "of", len(faces))
        return self.close(zone)

    def f(self, verts):
        try:
            fc = self.bm.faces.new(verts)
        except ValueError:
            return None
        self.new_faces.append(fc)
        return fc

    def close(self, zone):
        fs = [fc for fc in self.new_faces if fc.is_valid]
        bmesh.ops.recalc_face_normals(self.bm, faces=fs)
        for fc in fs:
            fc[self.zl] = float(zone)
        self.new_faces = []
        return fs

    def bvh(self):
        self.bm.normal_update()
        return BVHTree.FromBMesh(self.bm)

    def loft(self, secs, zone, sides=12, cap0=None, cap1=None, up=(0, 0, 1), phase=0.0, tvals=None,
             closed_path=False):
        """Skin superellipse rings along a path. secs: dicts with c (centre), rx, rz, optional n
        (superellipse exponent), mod(a, x, z) -> (x, z), twist, t (tangent override)."""
        cs = [Vector(s["c"]) for s in secs]
        upv = Vector(up)
        rings = []
        m = len(secs)
        for i, s in enumerate(secs):
            if "t" in s:
                t = Vector(s["t"]).normalized()
            elif closed_path:
                t = (cs[(i + 1) % m] - cs[(i - 1) % m]).normalized()
            else:
                t = (cs[min(i + 1, m - 1)] - cs[max(i - 1, 0)]).normalized()
            x = upv.cross(t)
            if x.length < 1e-6:
                x = Vector((1, 0, 0)).cross(t)
            x.normalize()
            z = t.cross(x).normalized()
            n_ = s.get("n", 2.0)
            mod = s.get("mod")
            ring = []
            for k in range(sides):
                a = 2 * math.pi * k / sides + phase + s.get("twist", 0.0)
                ex, ez = se(a, n_)
                px, pz = s["rx"] * ex, s["rz"] * ez
                if mod:
                    px, pz = mod(a, px, pz)
                ring.append(self.v(cs[i] + x * px + z * pz, tvals[i] if tvals else 0.0, tuple(t)))
            rings.append(ring)
        pairs = list(zip(rings, rings[1:])) + ([(rings[-1], rings[0])] if closed_path else [])
        for r0, r1 in pairs:
            for k in range(sides):
                k2 = (k + 1) % sides
                self.f([r0[k], r0[k2], r1[k2], r1[k]])
        for ring, cap in ((rings[0], cap0), (rings[-1], cap1)):
            if cap is None or closed_path:
                continue
            if isinstance(cap, str):
                self.f(ring[::-1])
            else:
                tip = self.v(Vector(cap), (tvals[-1] if tvals else 0.0) if ring is rings[-1] else 0.0)
                for k in range(sides):
                    self.f([ring[(k + 1) % sides], ring[k], tip])
        return rings

    def ellipsoid(self, c, radii, axis, zone, useg=10, vseg=6, t=0.0):
        q = Vector(axis).normalized().to_track_quat("Z", "Y")
        mtx = Matrix.Translation(Vector(c)) @ q.to_matrix().to_4x4() @ Matrix.Diagonal((*radii, 1.0))
        res = bmesh.ops.create_uvsphere(self.bm, u_segments=useg, v_segments=vseg, radius=1.0, matrix=mtx)
        for vv in res["verts"]:
            vv[self.tl] = t
        self.new_faces += list({fc for vv in res["verts"] for fc in vv.link_faces})
        return self.close(zone)

    def box(self, c, size, zone, bevel=0.0, segments=2, rot=None):
        """Box (optionally rotated by matrix rot) with a multi-segment soft bevel."""
        hx, hy, hz = (s / 2 for s in size)
        R = rot if rot is not None else Matrix.Identity(3)
        cv = Vector(c)
        pts = [cv + R @ Vector((sx * hx, sy * hy, sz * hz)) for sz in (-1, 1) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        vs = [self.v(p) for p in pts]
        for idx in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self.f([vs[i] for i in idx])
        fs = self.close(zone)
        if bevel > 0:
            edges = list({e for fc in fs for e in fc.edges})
            res = bmesh.ops.bevel(self.bm, geom=edges, offset=bevel, offset_type="OFFSET", segments=segments,
                                  profile=0.5, affect="EDGES", clamp_overlap=True)
            for fc in res["faces"]:
                fc[self.zl] = float(zone)
        return fs

    def to_object(self, material):
        bm = self.bm
        bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=bm.edges[:])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        # guard: every closed shell must enclose positive volume (outward normals)
        seen, flipped = set(), 0
        for f0 in bm.faces:
            if f0.index in seen:
                continue
            bm.faces.index_update()
            stack, shell = [f0], []
            seen.add(f0.index)
            while stack:
                fc = stack.pop()
                shell.append(fc)
                for e in fc.edges:
                    for g in e.link_faces:
                        if g.index not in seen:
                            seen.add(g.index)
                            stack.append(g)
            vol = 0.0
            for fc in shell:
                vs_ = [lv.vert.co for lv in fc.loops]
                for i in range(1, len(vs_) - 1):
                    vol += vs_[0].dot(vs_[i].cross(vs_[i + 1]))
            if vol < 0:
                bmesh.ops.reverse_faces(bm, faces=shell)
                flipped += 1
        if flipped:
            log(self.name, "flipped", flipped, "inside-out shell(s)")
        me = bpy.data.meshes.new(self.name)
        bm.to_mesh(me)
        bm.free()
        me.transform(Matrix.Translation(-self.pivot))
        me.materials.append(material)
        ob = bpy.data.objects.new(self.name, me)
        ob.location = self.pivot
        ob.pass_index = self.pid
        bpy.context.scene.collection.objects.link(ob)
        return ob

def snap(tree, p):
    loc, nrm, _, _ = tree.find_nearest(Vector(p))
    return loc, nrm


def tangent(want, n):
    d = Vector(want) - n * Vector(want).dot(n)
    return d.normalized() if d.length > 1e-6 else n.orthogonal().normalized()


# =============================================================================================
# fused fur: every furry rigid part is ONE surface. Its base form and its fur volumes (ruff, belly,
# feathering, cheeks, muzzle) are signed distance fields joined with smooth unions, so each join is
# a real fillet; OpenVDB meshes the result and a quadric decimate brings it to budget. Nothing is
# ever fused across parts: each part gets its own field.
# =============================================================================================
class Grid:
    """Dense voxel lattice in world studs; voxel (i, j, k) sits at lo + h * (i, j, k). sym_x makes
    the lattice symmetric about x = 0 so a symmetric field meshes symmetrically."""

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
        """Trilinear lookup of the lattice array A at world points (N, 3)."""
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


def shape(fn):
    """Run fn(tmp_part) with the loft/ellipsoid helpers and return the closed mesh as (verts, tris)."""
    t = Part("_shape", 0, (0, 0, 0), "")
    fn(t)
    bm = t.bm
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.verts.index_update()
    vs = np.array([v.co[:] for v in bm.verts], float)
    tris = np.array([[v.index for v in fc.verts] for fc in bm.faces], np.uint32)
    bm.normal_update()
    tree = BVHTree.FromBMesh(bm)
    bm.free()
    return vs, tris, tree


def mesh_sdf(grid, vt, band=28.0):
    """Signed distance (studs, negative inside) of a closed mesh on the lattice, via OpenVDB."""
    vs, tris = vt[0], vt[1]
    pts = ((vs - grid.lo) / grid.h).astype(np.float32)
    ls = vdb.FloatGrid.createLevelSetFromPolygons(pts, triangles=tris, quads=None,
                                                   transform=vdb.createLinearTransform(1.0),
                                                   exBandWidth=band, inBandWidth=band)
    arr = np.zeros(grid.n, np.float32)
    ls.copyToArray(arr, ijk=(0, 0, 0))
    return arr.astype(np.float64) * grid.h


def sd_ell(P, c, R, radii, elong=0.0):
    """Approximate signed distance to an ellipsoid (centre c, rows of R = its local x, y, z axes in
    world, radii along them). elong stretches it along local y into a rounded capsule."""
    q = (P - np.asarray(c, float)) @ np.asarray(R, float).T
    if elong:
        q[..., 1] = np.sign(q[..., 1]) * np.maximum(np.abs(q[..., 1]) - elong, 0.0)
    r = np.asarray(radii, float)
    k0 = np.linalg.norm(q / r, axis=-1)
    k1 = np.linalg.norm(q / (r * r), axis=-1)
    return np.where(k0 < 1e-6, -min(radii), k0 * (k0 - 1.0) / np.maximum(k1, 1e-9))


AXES = np.eye(3)


def track_axes(axis):
    """Local axes of Part.ellipsoid(axis=...): local z along axis (same quaternion)."""
    q = Vector(axis).normalized().to_track_quat("Z", "Y")
    return np.array(q.to_matrix()).T


def lock_axes(n, fall, tip=0.0):
    """Axes for a fur volume lying on a surface with normal n: local y runs the way the fur falls
    (fall projected onto the surface), local z points out of the coat, local x across. tip (radians)
    lifts the falling end a little off the coat, so the lock hangs rather than lies flat."""
    n = Vector(n).normalized()
    d = tangent(fall, n)
    x = d.cross(n).normalized()
    d, n = d * math.cos(tip) + n * math.sin(tip), n * math.cos(tip) - d * math.sin(tip)
    return np.array([x[:], d[:], n[:]])


def smin(a, b, k):
    """Polynomial smooth union: blends the two surfaces with a fillet about k wide."""
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def ssub(a, b, k):
    """Smooth subtraction of b from a (rounded edges)."""
    return -smin(-a, b, k)


def blur(F, passes=1):
    """[1 2 1] / 4 separable smoothing of a distance field: softens facet creases and fillets."""
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
    a = vs[[f[0] for f in fs]]
    b = vs[[f[1] for f in fs]]
    c = vs[[f[2] for f in fs]]

    def ang(p, q, r):
        u, v = q - p, r - p
        cs = np.sum(u * v, 1) / np.maximum(np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1), 1e-12)
        return np.degrees(np.arccos(np.clip(cs, -1, 1)))
    return np.minimum(np.minimum(ang(a, b, c), ang(b, c, a)), ang(c, a, b))


def tidy(grid, F, vs, fs, passes=4, pin=None):
    """Even out the decimated triangles without moving the surface: flip edges toward better
    triangles, slide each vertex toward its neighbours' centre and project it back onto the
    isosurface. Long slivers get no texels in the atlas and show as cracks, so they must go."""
    before = int(np.sum(min_angles(vs, fs) < 12.0))
    bm = bmesh.new()
    bv = [bm.verts.new(tuple(v)) for v in vs]
    for fc in fs:
        try:
            bm.faces.new([bv[i] for i in fc])
        except ValueError:
            pass
    bm.normal_update()
    def flippable():
        if pin is None:
            return bm.edges[:]
        bm.verts.index_update()
        pv = pin(np.array([v.co[:] for v in bm.verts]))
        return [e for e in bm.edges if not (pv[e.verts[0].index] or pv[e.verts[1].index])]

    for it in range(passes):
        bmesh.ops.beautify_fill(bm, faces=bm.faces[:], edges=flippable(), use_restrict_tag=False, method="ANGLE")
        bm.verts.ensure_lookup_table()
        co = np.array([v.co[:] for v in bm.verts])
        cen = np.array([np.mean([e.other_vert(v).co[:] for e in v.link_edges], axis=0) for v in bm.verts])
        step = 0.5 if pin is None else np.where(pin(co), 0.0, 0.5)[:, None]
        p = co + step * (cen - co)
        for _ in range(2):
            eps = grid.h * 0.5
            d = grid.sample(F, p)
            g = np.stack([grid.sample(F, p + eps * e) - grid.sample(F, p - eps * e) for e in np.eye(3)], 1) / (2 * eps)
            p = p - (d / np.maximum(np.sum(g * g, 1), 1e-9))[:, None] * g
        for v, q in zip(bm.verts, p):
            v.co = q
    bmesh.ops.beautify_fill(bm, faces=bm.faces[:], edges=flippable(), use_restrict_tag=False, method="ANGLE")
    bm.verts.index_update()
    vo = np.array([v.co[:] for v in bm.verts])
    fo = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    log("  tidy: triangles with a corner under 12 deg", before, "->", int(np.sum(min_angles(vo, fo) < 12.0)))
    return vo, fo


def extract(grid, F, target, sym=False, name="fused", pin=None):
    """Mesh the zero isosurface of F (OpenVDB), then quadric-decimate to about `target` triangles.
    Returns (verts (N, 3), faces)."""
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
    vo, fo = tidy(grid, F, vo, fo, pin=pin)
    # diagnostics: orientation against the field gradient, non-manifold edges
    ctr = np.array([vo[list(fc)].mean(0) for fc in fo])
    nrm = np.array([np.cross(vo[fc[1]] - vo[fc[0]], vo[fc[2]] - vo[fc[0]]) for fc in fo])
    eps = grid.h
    grad = np.stack([grid.sample(F, ctr + eps * e) - grid.sample(F, ctr - eps * e) for e in np.eye(3)], 1)
    flips = int(np.sum(np.sum(nrm * grad, 1) < 0))
    if flips:
        log("  flipped at", np.round(ctr[np.sum(nrm * grad, 1) < 0], 3).tolist())
    ec = {}
    for fc in fo:
        for i in range(len(fc)):
            k = tuple(sorted((fc[i], fc[(i + 1) % len(fc)])))
            ec[k] = ec.get(k, 0) + 1
    nm = sum(1 for v in ec.values() if v != 2)
    log(name, "isosurface", n_tri, "tris ->", len(fo), "| faces against gradient", flips, "| non-manifold edges", nm)
    return vo, fo


def blend_flow(pts, comps):
    """Fur-flow vector per point: each component's flow weighted by how close it is to the point."""
    acc = np.zeros((len(pts), 3))
    for d, fl in comps:
        w = np.exp(-np.maximum(d, 0.0) / 0.03)[:, None]
        acc += w * np.asarray(fl, float)[None, :]
    return acc / np.maximum(np.linalg.norm(acc, axis=1), 1e-6)[:, None]


FUSED = {}          # per part: (grid, named component fields) for the painter's muzzle and mouth masks


def mirror_x(v):
    return Vector((-v[0], v[1], v[2]))


# =============================================================================================
# proportions (studs)
# =============================================================================================

_rng = np.random.default_rng(20260929)
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


# =============================================================================================
# proportions (studs)
# =============================================================================================
BODY_PIVOT = V(0.0, 0.10, 0.75)
NECK_PIVOT = V(0.0, -0.25, 0.95)
HIP = V(0.56, 0.42, 0.72)            # +x (left) side; mirrored for the right
SHOULDER = V(0.40, -0.40, 0.76)
BELT_C = V(0.0, 0.20, 0.56)
EYE_C = V(0.42, -0.50, 1.74)
EYE_R = 0.35
EYE_N = V(0.22, -0.80, 0.50).normalized()
MOUTH = dict(z0=0.98, k=0.30, xmax=0.72)
TRI = dict(body=1100, head=1700, front=380, hind=700)
FACE = {}
TOES = []                            # (centre, radius) of every toe bulb, for the pad paint
PLATES = []                          # (centre, axis, radius) of the belt plate


HC = dict(body=0.15, head=0.105, front=0.082, hind=0.097)      # facet size (studs) of the even lattice mesh


def mesh_part(G, F, key, sym=False, name=None):
    """Mesh the fused field into BROAD, EVEN facets (cut-gemstone look): mesh a coarse resampling of the field
    (uniform cell size, so every facet is about the same size), even the triangles out, then project the
    vertices back onto the fine field so the silhouette keeps its detail."""
    if MESH == "quadric":
        return extract(G, F, TRI[key], sym=sym, name=name or key)
    hi = G.lo + np.array(G.n) * G.h - G.h
    Gc = Grid(G.lo.copy(), hi, HC[key], sym_x=sym)
    Fc = G.sample(F, Gc.P.reshape(-1, 3)).reshape(Gc.n)
    g = vdb.FloatGrid(1.0e4)
    g.copyFromArray((Fc / Gc.h).astype(np.float32))
    pts, tris, quads = g.convertToPolygons(0.0, 0.0)
    vs = Gc.lo + Gc.h * pts.astype(np.float64)
    fs = [tuple(tq) for tq in tris.tolist()]
    for q in quads.tolist():
        a, b, c, d = (vs[i] for i in q)
        if np.linalg.norm(a - c) <= np.linalg.norm(b - d):
            fs += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
        else:
            fs += [(q[0], q[1], q[3]), (q[1], q[2], q[3])]
    vs, fs = tidy(Gc, Fc, vs, fs, passes=6)
    for _ in range(3):
        eps = G.h * 0.5
        d = G.sample(F, vs)
        gr = np.stack([G.sample(F, vs + eps * e) - G.sample(F, vs - eps * e) for e in np.eye(3)], 1) / (2 * eps)
        vs = vs - (d / np.maximum(np.sum(gr * gr, 1), 1e-9))[:, None] * gr
    log(name or key, "lattice mesh", len(fs), "tris at cell", HC[key])
    return vs, fs


def mouth_z(x):
    return MOUTH["z0"] + MOUTH["k"] * x * x


def cap(P, A, B, ra, rb):
    """Signed distance to a round cone (capsule with two radii)."""
    A, B = np.asarray(A, float), np.asarray(B, float)
    BA = B - A
    t = np.clip(((P - A) @ BA) / BA.dot(BA), 0.0, 1.0)
    C = A + t[..., None] * BA
    return np.linalg.norm(P - C, axis=-1) - (ra + (rb - ra) * t)


# =============================================================================================
# the frog
# =============================================================================================
def build_body():
    p = Part("Frog_Body", P_BODY, BODY_PIVOT, "body centre (root part): hop bob / squash pivot")
    G = Grid((-0.95, -0.95, -0.05), (0.95, 1.05, 1.65), 0.016, sym_x=True)
    P = G.P
    low = sd_ell(P, (0, 0.20, 0.56), AXES, (0.74, 0.84, 0.50))
    chest = sd_ell(P, (0, -0.12, 0.92), AXES, (0.62, 0.62, 0.52))
    rump = sd_ell(P, (0, 0.66, 0.80), AXES, (0.50, 0.44, 0.46))
    d = smin(smin(low, chest, 0.25), rump, 0.20)
    d = np.maximum(d, 0.02 - P[..., 2])
    vs, fs = mesh_part(G, blur(d), "body", sym=True, name="body")
    p.add_mesh(vs, fs, Z_SKIN)
    tree = p.bvh()
    # championship belt: a chunky leather strap hugging the waist, a big round gold plate at the front
    n_seg = 20
    secs, ring_pts = [], []
    for i in range(n_seg):
        a = 2 * math.pi * i / n_seg
        dn = V(math.cos(a), math.sin(a), 0.0)
        hit = tree.ray_cast(BELT_C + dn * 2.0, -dn, 3.0)
        on = hit[0] if hit[0] is not None else BELT_C + dn * 0.7
        ring_pts.append(on + dn * 0.040)
    for _ in range(1):                                   # even the strap out so coarse facets don't notch it
        ring_pts = [(ring_pts[i - 1] + 2 * ring_pts[i] + ring_pts[(i + 1) % n_seg]) * 0.25 for i in range(n_seg)]
    secs = [dict(c=c_, rx=0.055, rz=0.125, n=3.0) for c_ in ring_pts]
    p.loft(secs, Z_LEATHER, sides=6, up=(0, 0, 1), closed_path=True, tvals=[0.5] * n_seg)
    p.close(Z_LEATHER)
    hit = tree.ray_cast(BELT_C + V(0, -2, 0), V(0, 1, 0), 3.0)
    pc = hit[0] + V(0, -0.10, 0)
    ax = V(0, -1, -0.08).normalized()
    FW, FH = 0.31, 0.23
    plate = [dict(c=pc + ax * s, rx=FW * a, rz=FH * a, n=2.6)
             for s, a in ((-0.13, 0.55), (-0.03, 0.85), (0.0, 1.0), (0.07, 1.02), (0.10, 0.90))]
    p.loft(plate, Z_GOLD, sides=22, cap0="flat", cap1="flat", up=(0, 0, 1))
    p.close(Z_GOLD)
    boss = [dict(c=pc + ax * s, rx=FW * a, rz=FH * a, n=2.4) for s, a in ((0.09, 0.62), (0.115, 0.66), (0.135, 0.52))]
    p.loft(boss, Z_GOLD, sides=16, cap0="flat", cap1="flat", up=(0, 0, 1))
    p.close(Z_GOLD)
    PLATES.append((pc, ax, FW, FH, 0.06))
    for sg in (1, -1):                                   # a small title plate on each hip
        a = math.radians(-28) if sg > 0 else math.radians(208)
        dn = V(math.cos(a), math.sin(a), 0.0)
        h2 = tree.ray_cast(BELT_C + dn * 2.0, -dn, 3.0)
        sc_ = (h2[0] if h2[0] is not None else BELT_C + dn * 0.7) + dn * 0.05
        side = [dict(c=sc_ + dn * s, rx=rx_, rz=rz_, n=2.4)
                for s, rx_, rz_ in ((-0.08, 0.08, 0.07), (-0.02, 0.15, 0.125), (0.03, 0.16, 0.13), (0.055, 0.14, 0.115))]
        p.loft(side, Z_GOLD, sides=14, cap0="flat", cap1="flat", up=(0, 0, 1))
        p.close(Z_GOLD)
        PLATES.append((sc_, dn, 0.16, 0.13, 0.02))
    return p


def build_head():
    p = Part("Frog_Head", P_HEAD, NECK_PIVOT, "neck joint (nod / tilt / turn pivot)")
    G = Grid((-1.0, -1.25, 0.45), (1.0, 0.35, 2.30), 0.014, sym_x=True)
    P = G.P
    X, Y, Z = P[..., 0], P[..., 1], P[..., 2]
    main = sd_ell(P, (0, -0.45, 1.22), AXES, (0.82, 0.66, 0.50))
    jaw = sd_ell(P, (0, -0.50, 0.98), AXES, (0.80, 0.64, 0.36))
    d = smin(main, jaw, 0.20)
    for sx in (1, -1):
        d = smin(d, sd_ell(P, (sx * 0.66, -0.78, 1.02), AXES, (0.20, 0.22, 0.20)), 0.10)
    for sx in (1, -1):
        c = V(sx * EYE_C.x, EYE_C.y, EYE_C.z)
        d = smin(d, sd_ell(P, c, AXES, (EYE_R,) * 3), 0.09)
        FACE[f"eye{sx}"] = dict(c=c, n=V(sx * EYE_N.x, EYE_N.y, EYE_N.z))
    # shallow smile groove carved into the surface (the painted line follows it)
    slab = np.abs(Z - mouth_z(X)) - 0.016
    slab = np.maximum(np.maximum(slab, Y + 0.30), np.abs(X) - MOUTH["xmax"])
    groove = np.maximum(slab, -(d + 0.028))
    d = ssub(d, groove, 0.008)
    vs, fs = mesh_part(G, blur(d), "head", sym=True, name="head")
    p.add_mesh(vs, fs, Z_SKIN)
    return p


def hind_field(P):
    h = sd_ell(P, (0.72, 0.30, 0.52), AXES, (0.33, 0.52, 0.46))
    knee = sd_ell(P, (0.84, -0.12, 0.42), AXES, (0.22, 0.26, 0.24))
    shank = cap(P, (0.80, -0.08, 0.36), (0.80, -0.42, 0.17), 0.19, 0.13)
    foot = sd_ell(P, (0.82, -0.55, 0.10), AXES, (0.24, 0.30, 0.10))
    d = smin(smin(h, knee, 0.12), shank, 0.10)
    d = smin(d, foot, 0.08)
    for dx, ty in ((-0.20, -0.92), (0.0, -0.97), (0.20, -0.92)):
        bulb = sd_ell(P, (0.82 + dx, ty, 0.108), AXES, (0.115, 0.12, 0.108))
        link = cap(P, (0.82 + dx * 0.6, -0.72, 0.09), (0.82 + dx, ty + 0.05, 0.09), 0.06, 0.06)
        d = smin(d, smin(bulb, link, 0.04), 0.05)
    return np.maximum(d, -P[..., 2])


def front_field(P):
    arm = cap(P, (0.40, -0.42, 0.78), (0.36, -0.72, 0.20), 0.20, 0.145)
    elbow = sd_ell(P, (0.46, -0.50, 0.46), AXES, (0.16, 0.17, 0.17))
    hand = sd_ell(P, (0.36, -0.84, 0.08), AXES, (0.15, 0.17, 0.08))
    d = smin(smin(arm, elbow, 0.10), hand, 0.08)
    for dx, ty in ((-0.12, -1.03), (0.0, -1.06), (0.12, -1.03)):
        bulb = sd_ell(P, (0.36 + dx, ty, 0.085), AXES, (0.092, 0.095, 0.088))
        link = cap(P, (0.36 + dx * 0.6, -0.90, 0.07), (0.36 + dx, ty + 0.04, 0.08), 0.045, 0.045)
        d = smin(d, smin(bulb, link, 0.03), 0.04)
    return np.maximum(d, -P[..., 2])


def build_leg(name, pid, pivot, joint, field, box, target, side, toes):
    G = Grid(box[0], box[1], 0.014)
    vs, fs = mesh_part(G, blur(field(G.P)), "front" if pid in (P_LEGFL, P_LEGFR) else "hind", name=name.lower())
    piv = Vector(pivot)
    if side < 0:
        vs = vs * np.array((-1.0, 1.0, 1.0))
        fs = [tuple(reversed(f)) for f in fs]
        piv = Vector((-piv.x, piv.y, piv.z))
    p = Part(name, pid, piv, joint)
    p.add_mesh(vs, fs, Z_SKIN)
    for (cx, cy, cz, r) in toes:
        TOES.append((V(side * cx, cy, cz), r))
    return p


def build_front_leg(side):
    nm = "Frog_LegFL" if side > 0 else "Frog_LegFR"
    toes = [(0.36 + dx, ty, 0.085, 0.095) for dx, ty in ((-0.12, -1.03), (0.0, -1.06), (0.12, -1.03))]
    return build_leg(nm, P_LEGFL if side > 0 else P_LEGFR, SHOULDER, "shoulder (short front leg swing)", front_field,
                     ((0.10, -1.25, -0.05), (0.72, -0.20, 1.00)), TRI["front"], side, toes)


def build_hind_leg(side):
    nm = "Frog_LegBL" if side > 0 else "Frog_LegBR"
    toes = [(0.82 + dx, ty, 0.108, 0.12) for dx, ty in ((-0.20, -0.92), (0.0, -0.97), (0.20, -0.92))]
    return build_leg(nm, P_LEGBL if side > 0 else P_LEGBR, HIP, "hip (powerful hind leg kick / hop)", hind_field,
                     ((0.30, -1.15, -0.05), (1.20, 0.95, 1.05)), TRI["hind"], side, toes)


# =============================================================================================
# painting (numpy)
# =============================================================================================
GREEN, GREEN_LT, GREEN_DK = rgb(104, 178, 70), rgb(142, 208, 92), rgb(64, 136, 62)
BELLY, BELLY_SH = rgb(224, 238, 166), rgb(190, 214, 136)
SPOT = rgb(56, 118, 58)
MOUTH_LINE = rgb(36, 68, 42)
BLUSH = rgb(240, 152, 120)
PAD = rgb(208, 230, 130)
EYE_W, EYE_DARK, EYE_AMBER, LID = rgb(250, 247, 234), rgb(30, 24, 32), rgb(226, 142, 46), rgb(46, 106, 52)
LEATHER, LEATHER_LT = rgb(92, 52, 40), rgb(156, 98, 64)
GOLD, GOLD_DK, GOLD_LT = rgb(238, 188, 72), rgb(172, 112, 34), rgb(253, 226, 134)
JEWEL, JEWEL_LT = rgb(196, 58, 50), rgb(250, 146, 116)
COOL = np.array((0.80, 0.85, 1.0))


def paint_eyes(col, P, part):
    after = []
    head = part == P_HEAD
    for sx in (1, -1):
        e = FACE[f"eye{sx}"]
        c, nn = np.array(e["c"]), np.array(e["n"])
        t = np.array((0.0, 0.0, 1.0)) - nn * nn[2]
        t /= np.linalg.norm(t)
        s = np.cross(t, nn)
        q = P - c
        ql = np.maximum(np.linalg.norm(q, axis=1), 1e-6)
        th = np.arccos(np.clip((q @ nn) / ql, -1, 1))
        on = head & (ql > 0.24) & (ql < 0.46)
        sI = math.sin(0.68)
        a, b = (q @ s) / ql / sI, (q @ t) / ql / sI
        rr = np.sqrt(a * a + b * b)
        lid = on & (th < 1.16) & (th >= 0.98)
        col[lid] = mix(col[lid], LID, (0.95 * sstep(1.16, 1.04, th))[lid])
        scl = on & (th < 0.98)
        col[scl] = mix(col[scl], EYE_W, sstep(0.98, 0.93, th)[scl])
        iris = on & (th < 0.68)
        ce = np.tile(EYE_DARK, (len(P), 1))
        ce = mix(ce, EYE_AMBER, 0.8 * sstep(-0.05, -0.75, b) * sstep(0.25, 0.85, rr))
        col[iris] = mix(col[iris], ce[iris], sstep(0.68, 0.62, th)[iris])
        after.append((iris, a, b))
    return after


def paint(P, Ns, zone, part):
    n = len(P)
    hgt = sstep(0.1, 1.9, P[:, 2])
    col = mix(GREEN_LT, GREEN_DK, 0.85 * hgt)
    col = col * (0.93 + 0.14 * vnoise(P, 5.0, 1))[:, None]
    up = sstep(-0.2, 0.5, Ns[:, 2])
    blot = sstep(0.50, 0.74, vnoise(P * np.array((1.0, 1.0, 1.25)), 1.5, 2)) * up * sstep(0.5, 0.9, P[:, 2] + 0.25 * up)
    col = mix(col, rgb(76, 146, 66), 0.45 * blot)
    skin_ = (zone == Z_SKIN)
    top_ = sstep(0.25, 0.95, Ns[:, 2]) * (P[:, 2] > 0.7) * skin_
    side_ = sstep(0.30, 0.85, np.abs(Ns[:, 0])) * skin_ * (1.0 - top_)
    col = mix(col, rgb(54, 128, 58), 0.40 * top_)
    col = mix(col, GREEN_LT, 0.30 * side_)
    # broad brush strokes that follow the form: bands wrapping round body and head, long strokes along the limbs
    sc = np.where((part >= P_LEGFL)[:, None], np.array((9.0, 2.4, 9.0)), np.array((2.6, 2.6, 10.0)))
    sk = (zone == Z_SKIN)[:, None]
    n_a = vnoise(P * sc, 1.0, 5)
    col = np.where(sk, mix(col, col * np.array((0.80, 0.92, 0.90)), 0.75 * (1.0 - sstep(0.34, 0.42, n_a))), col)
    col = np.where(sk, mix(col, np.clip(col * np.array((1.14, 1.08, 0.86)), 0, 1), 0.7 * sstep(0.60, 0.68, n_a)), col)
    n_b = vnoise(P * sc * 1.9, 1.0, 6)
    col = np.where(sk, mix(col, col * np.array((0.88, 0.95, 0.93)), 0.5 * (1.0 - sstep(0.30, 0.37, n_b))), col)
    body, head = part == P_BODY, part == P_HEAD
    legs = part >= P_LEGFL
    skin = zone == Z_SKIN
    # cream-green belly on the body, chin and throat under the smile line, soles and inner limbs
    bel = body & skin
    bl = sstep(-0.05, 0.45, -Ns[:, 1] * 0.85 - Ns[:, 2] * 0.3) * sstep(1.22, 0.92, P[:, 2]) * sstep(0.45, 0.1, P[:, 1])
    col = mix(col, mix(BELLY_SH, BELLY, sstep(0.0, 0.6, bl)), (0.95 * sstep(0.05, 0.5, bl) * bel))
    zm = mouth_z(P[:, 0])
    jawm = head * sstep(zm + 0.03, zm - 0.07, P[:, 2]) * sstep(-0.10, -0.40, P[:, 1])
    col = mix(col, BELLY, 0.95 * jawm)
    limb = legs * sstep(0.0, 0.6, -Ns[:, 2])
    col = mix(col, BELLY, 0.65 * limb)
    # toe pads
    for (c, r) in TOES:
        dd = np.linalg.norm(P - np.array(c), axis=1) / r
        m = legs & (dd < 1.3)
        col[m] = mix(col[m], PAD, (0.92 * sstep(1.3, 1.0, dd))[m])
    # blush, smile line, nostrils
    for sx in (1, -1):
        dd = np.linalg.norm(P - np.array((sx * 0.58, -0.86, 1.08)), axis=1)
        m = head & (dd < 0.17) & (Ns[:, 1] < 0.1)
        col[m] = mix(col[m], BLUSH, (0.55 * sstep(0.17, 0.06, dd))[m])
        nd = np.sqrt((P[:, 0] - sx * 0.13) ** 2 + (P[:, 2] - 1.33) ** 2)
        m = head & (nd < 0.022) & (P[:, 1] < -0.8) & (Ns[:, 1] < -0.3)
        col[m] = mix(col[m], MOUTH_LINE, sstep(0.022, 0.012, nd)[m] * 0.9)
    dz = np.abs(P[:, 2] - zm)
    ml = head & (P[:, 1] < -0.28) & (np.abs(P[:, 0]) < MOUTH["xmax"] + 0.02) & (dz < 0.024)
    col[ml] = mix(col[ml], MOUTH_LINE, (sstep(0.024, 0.012, dz) * sstep(MOUTH["xmax"] + 0.02, MOUTH["xmax"] - 0.04, np.abs(P[:, 0])))[ml])
    # belt leather: stitched edges and gold studs
    lea = zone == Z_LEATHER
    lc = mix(LEATHER, LEATHER_LT, 0.35 * vnoise(P, 14.0, 3))
    col[lea] = lc[lea]
    st = lea & (np.abs(np.abs(P[:, 2] - BELT_C.z) - 0.082) < 0.008)
    col[st] = mix(col[st], LEATHER_LT, 0.85)
    ph = np.arctan2(P[:, 1] - BELT_C.y, P[:, 0])
    stepa = 2 * math.pi / 14
    fr = (ph / stepa + 0.5) % 1.0 - 0.5
    stud = lea & (np.abs(fr) * stepa * 0.75 < 0.030) & (np.abs(P[:, 2] - BELT_C.z) < 0.030)
    col[stud] = mix(col[stud], GOLD, 0.95)
    # gold plate: dark rim, groove ring, raised lighter boss with a red jewel
    gold = zone == Z_GOLD
    for (c, ax, rx, rz, bt) in PLATES:
        axv = np.array(ax)
        q = P - np.array(c)
        along = q @ axv
        perp = q - along[:, None] * axv
        lat = np.array((-axv[1], axv[0], 0.0))
        lat /= np.linalg.norm(lat)
        lu, lv = (perp @ lat) / rx, perp[:, 2] / rz
        rad = np.sqrt(lu ** 2 + lv ** 2)
        front = (Ns @ axv) > 0.55
        pc_ = np.tile(GOLD, (n, 1))
        pc_ = mix(pc_, GOLD_DK, sstep(0.80, 0.90, rad))
        pc_ = mix(pc_, GOLD_DK, 0.9 * sstep(0.05, 0.0, np.abs(rad - 0.70) - 0.015) * (rad < 0.8))
        pc_ = mix(pc_, GOLD_LT, 0.85 * sstep(0.66, 0.58, rad) * (along > bt))
        jw = sstep(0.27, 0.22, rad) * (along > bt)
        pc_ = mix(pc_, JEWEL, 0.95 * jw)
        pc_ = mix(pc_, JEWEL_LT, 0.9 * sstep(0.10, 0.06, np.sqrt((lu + 0.08) ** 2 + (lv - 0.08) ** 2)) * jw)
        pc_ = mix(pc_, GOLD_DK, 0.55 * (1.0 - front) * (rad > 0.7))
        m_ = gold & (np.linalg.norm(q, axis=1) < 0.42)
        col[m_] = pc_[m_]
    return col


def catchlights(col, after):
    for inside, eu, ev in after:
        g1 = np.sqrt(((eu + 0.34) / 0.30) ** 2 + ((ev - 0.36) / 0.30) ** 2)
        g2 = np.sqrt(((eu - 0.40) / 0.14) ** 2 + ((ev + 0.32) / 0.14) ** 2)
        m1, m2 = inside & (g1 < 1.0), inside & (g2 < 1.0)
        col[m1] = mix(col[m1], np.array((1.0, 1.0, 1.0)), sstep(1.0, 0.8, g1)[m1])
        col[m2] = mix(col[m2], np.array((1.0, 0.98, 0.94)), sstep(1.0, 0.75, g2)[m2])
    return col


def light(col, P, Ns, Nf, zone, ao_s, ao_l):
    Lk = np.array((-0.50, -0.62, 0.62))
    Lk /= np.linalg.norm(Lk)
    Lr = np.array((0.70, 0.62, 0.35))
    Lr /= np.linalg.norm(Lr)
    kf, ks = np.clip(Nf @ Lk, 0, 1), np.clip(Ns @ Lk, 0, 1)
    fw = np.where(zone == Z_SKIN, 0.65, 0.55)
    k = fw * kf + (1.0 - fw) * ks
    sky = 0.5 + 0.5 * Ns[:, 2]
    lightv = 0.64 + 0.36 * k + 0.12 * sky
    aof = (1.0 - 0.26 + 0.26 * sstep(0.12, 1.0, ao_s)) * (1.0 - 0.16 * (1.0 - sstep(0.2, 1.0, ao_l)))
    shade = lightv * aof * (0.92 + 0.10 * sstep(0.0, 2.0, P[:, 2]))
    u_ = shade * 4.0                                    # soft 4-step value banding (painterly value ranges)
    shade = 0.6 * shade + 0.4 * (np.floor(u_) + sstep(0.3, 0.7, u_ - np.floor(u_))) / 4.0
    lit = col * shade[:, None]
    lit = mix(lit, lit * COOL, 0.45 * sstep(0.78, 0.50, shade))
    rim = sstep(0.3, 1.0, Ns @ Lr) * 0.10
    lit = lit + rim[:, None] * np.array((0.55, 0.70, 1.0))
    return np.clip(lit, 0, 1)


# =============================================================================================
# build
# =============================================================================================
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
mat = bpy.data.materials.new("Frog_Atlas")
mat.use_nodes = True

builders = [build_body(), build_head(), build_front_leg(1), build_front_leg(-1), build_hind_leg(1), build_hind_leg(-1)]
meta = {b.name: dict(pivot=b.pivot.copy(), joint=b.joint, pid=b.pid) for b in builders}
objs = [b.to_object(mat) for b in builders]
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


def add_sun(name, energy, rot, angle, color):
    L = bpy.data.lights.new(name, "SUN")
    L.energy, L.angle, L.color = energy, math.radians(angle), color
    ob = bpy.data.objects.new(name, L)
    ob.rotation_euler = tuple(math.radians(v) for v in rot)
    scene.collection.objects.link(ob)
    return ob

def simple_mat(name, c):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*c, 1)
    b.inputs["Roughness"].default_value = 0.8
    return m

def shoot(path, loc, target, lens=85, res=(1200, 1200), ortho=None, show=(), engine="BLENDER_EEVEE", samples=64,
          sensor=None):
    for ob in extras:
        ob.hide_render = ob not in show
    scene.render.engine = engine
    if engine == "CYCLES":
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
    cam.data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cam.data.ortho_scale = ortho
    else:
        cam.data.lens = lens
    if sensor:
        cam.data.sensor_fit, cam.data.sensor_height = "VERTICAL", sensor
    else:
        cam.data.sensor_fit, cam.data.sensor_width = "AUTO", 36.0
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
    """Lay rendered PNGs out on a labelled contact sheet (its own tiny Eevee scene)."""
    sc = bpy.data.scenes.new("Sheet")
    sc.render.engine = "BLENDER_EEVEE"
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "PNG"
    wd = bpy.data.worlds.new("SheetWorld")
    wd.use_nodes = True
    wd.node_tree.nodes["Background"].inputs["Color"].default_value = (0.86, 0.87, 0.89, 1)
    sc.world = wd
    rows = math.ceil(len(items) / cols)
    k = 0.01                      # 1 px = 0.01 units
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

cam, extras = None, []


def setup_preview():
    global cam, extras
    scene.render.engine = "BLENDER_EEVEE"
    scene.view_settings.view_transform = "Standard"
    scene.render.image_settings.file_format = "PNG"
    world = bpy.data.worlds.new("Sky")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.66, 0.82, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
    scene.world = world
    add_sun("Key", 2.6, (50, 0, -35), 8, (1.0, 0.96, 0.9))
    add_sun("Rim", 1.4, (60, 0, 150), 10, (0.8, 0.88, 1.0))
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
    extras = []


tgt = V(0, -0.05, 0.98)
ft = V(0, -0.85, 1.42)
VIEWS = [
    ("threeq.png", "Three-quarter", around(tgt, (-0.75, -0.9, 0.42), 9.0), tgt),
    ("front.png", "Front", around(tgt, (0, -1, 0.15), 9.0), tgt),
    ("side.png", "Side (frog's right)", around(tgt, (-1, 0, 0.12), 9.0), tgt),
    ("back.png", "Back", around(tgt, (0, 1, 0.3), 9.5), tgt),
]
FACE_VIEW = ("face-closeup.png", around(ft, (-0.3, -1, 0.10), 5.6), ft)

if FLAT:
    flat_cols = {Z_SKIN: (0.36, 0.62, 0.24), Z_LEATHER: (0.36, 0.2, 0.14), Z_GOLD: (0.9, 0.7, 0.2)}
    fm_ = {z: simple_mat(f"flat{z}", c) for z, c in flat_cols.items()}
    select_only(objs)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))
    for o in objs:
        me = o.data
        me.materials.clear()
        for z in (Z_SKIN, Z_LEATHER, Z_GOLD):
            me.materials.append(fm_[z])
        zf = [int(round(a.value)) for a in me.attributes["zone"].data]
        for pl in me.polygons:
            pl.material_index = zf[pl.index] - 1
    setup_preview()
    tris_ = {o.name: tri_count(o) for o in objs}
    log("triangles", sum(tris_.values()), tris_)
    shots = [(shoot(OUT / f"flat-{fn}", loc, t, res=(640, 640)), lab) for fn, lab, loc, t in VIEWS[:3]]
    shots.append((shoot(OUT / "flat-face.png", FACE_VIEW[1], FACE_VIEW[2], res=(640, 640)), "Face"))
    make_sheet(shots, 4, 400, OUT / "flat-sheet.png", f"Frog flat shape check: {sum(tris_.values())} tris")
    sys.exit(0)

select_only(objs)
bpy.ops.object.shade_smooth_by_angle(angle=math.radians(SMOOTH_ANGLE), keep_sharp_edges=True)
for o in objs:
    me = o.data
    zf = np.array([a.value for a in me.attributes["zone"].data])
    flat = np.rint(zf).astype(int) == Z_SKIN          # big forms: flat facets (low-poly look); belt keeps soft bevels
    try:
        me.polygons.foreach_set("use_smooth", (~flat).tolist())
    except Exception:
        a_ = me.attributes.get("sharp_face") or me.attributes.new("sharp_face", "BOOLEAN", "FACE")
        a_.data.foreach_set("value", flat.tolist())
    fa = o.data.attributes.new("fnrm", "FLOAT_VECTOR", "FACE")
    fa.data.foreach_set("vector", np.array([pl.normal for pl in o.data.polygons], np.float32).ravel())

# ---- UVs ---------------------------------------------------------------------------------------
select_only(objs)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(52), island_margin=0.004, area_weight=0.0,
                         correct_aspect=True, scale_to_bounds=False)
bpy.ops.uv.pack_islands(rotate=True, margin=0.004)
bpy.ops.object.mode_set(mode="OBJECT")
for o in objs:
    o.data.uv_layers.active.name = "UVMap"
log("unwrapped")

# ---- bake data maps ------------------------------------------------------------------------------
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
    elif kind == "flow":
        cmb = N_("ShaderNodeCombineXYZ")
        for i, cc in enumerate("xyz"):
            L_(attr(f"flow_{cc}"), cmb.inputs[i])
        enc(cmb.outputs["Vector"], 0.5)
    elif kind == "attr":
        cmb = N_("ShaderNodeCombineXYZ")
        mz = N_("ShaderNodeMath")
        mz.operation = "MULTIPLY"
        L_(attr("zone"), mz.inputs[0])
        mz.inputs[1].default_value = 1.0 / 32.0
        oi = N_("ShaderNodeObjectInfo")
        mp = N_("ShaderNodeMath")
        mp.operation = "MULTIPLY"
        L_(oi.outputs["Object Index"], mp.inputs[0])
        mp.inputs[1].default_value = 1.0 / 16.0
        L_(mz.outputs[0], cmb.inputs[0])
        L_(mp.outputs[0], cmb.inputs[1])
        L_(attr("tuft_t"), cmb.inputs[2])
        L_(cmb.outputs["Vector"], em.inputs["Color"])
    elif kind == "attr2":
        cmb = N_("ShaderNodeCombineXYZ")
        L_(attr("lock"), cmb.inputs[0])
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
                                         ("occ", 12 if QUICK else 16))}
cov = maps["pos"][:, 3] > 0.5
idx = np.nonzero(cov)[0]


def dec(a, s):
    return (a[idx, :3].astype(np.float64) - 0.5) / s


def unit(a):
    return a / np.maximum(np.linalg.norm(a, axis=1), 1e-6)[:, None]


P = dec(maps["pos"], 0.125)
Ns = unit(dec(maps["nrm"], 0.5))
Nf = unit(dec(maps["fnrm"], 0.5))
at = maps["attr"][idx, :3].astype(np.float64)
zone = np.rint(at[:, 0] * 32.0).astype(np.int64)
part = np.rint(at[:, 1] * 16.0).astype(np.int64)
oc = maps["occ"][idx, :3].astype(np.float64)
ao_s, ao_l = np.clip(oc[:, 0], 0, 1), np.clip(oc[:, 1], 0, 1)
del maps

colour = paint(P, Ns, zone, part)
after = paint_eyes(colour, P, part)
colour = light(colour, P, Ns, Nf, zone, ao_s, ao_l)
colour = catchlights(colour, after)

full = np.zeros((BAKE * BAKE, 4), np.float32)
full[idx, :3] = colour
full[:, 3] = 1.0
full[~cov, :3] = GREEN
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
bs.inputs["Roughness"].default_value = 0.8
bs.inputs["Specular IOR Level"].default_value = 0.2
tx = nt.nodes.new("ShaderNodeTexImage")
tx.image = tex_img
nt.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
out = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])
for o in objs:
    for a in ("zone", "tuft_t", "flow_x", "flow_y", "flow_z", "fnrm", "lock"):
        if a in o.data.attributes:
            o.data.attributes.remove(o.data.attributes[a])

tris = {o.name: tri_count(o) for o in objs}
log("triangles", sum(tris.values()), tris)

# =============================================================================================
# reports (Studio axes = (-x, z, y) of Blender)
# =============================================================================================
bpy.context.view_layer.update()
JOINT_PARENT = {"Frog_Body": None, "Frog_Head": "Frog_Body", "Frog_LegFL": "Frog_Body", "Frog_LegFR": "Frog_Body",
                "Frog_LegBL": "Frog_Body", "Frog_LegBR": "Frog_Body"}
MOTION = {
    "Frog_Body": "root part: hop bob up/down in Studio Y, squash/stretch, a small pitch about Studio X on takeoff and landing",
    "Frog_Head": "nod = pitch about Studio X, tilt = roll about Studio Z, look = yaw about Studio Y, all through the neck joint",
    "Frog_LegFL": "short front leg: brace / slam = swing about Studio X (side-to-side axis) through the shoulder",
    "Frog_LegFR": "short front leg: brace / slam = swing about Studio X (side-to-side axis) through the shoulder",
    "Frog_LegBL": "powerful hind leg: hop kick = swing about Studio X (side-to-side axis) through the hip",
    "Frog_LegBR": "powerful hind leg: hop kick = swing about Studio X (side-to-side axis) through the hip",
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
          "axes": "Blender Z-up, front -Y, the frog's left +X; feet on z = 0",
          "texture": f"textures/{TEX_PATH.name} ({ATLAS}x{ATLAS}, shared by every part)",
          "parts": {}}
lo_all, hi_all = Vector((1e9,) * 3), Vector((-1e9,) * 3)
for name, o in parts.items():
    me = o.data
    me.calc_loop_triangles()
    uv = me.uv_layers.active.data
    us, vs = [d.uv.x for d in uv], [d.uv.y for d in uv]
    lo, hi = world_bounds(o)
    lo_all = Vector([min(lo_all[k], lo[k]) for k in range(3)])
    hi_all = Vector([max(hi_all[k], hi[k]) for k in range(3)])
    report["parts"][name] = {
        "triangles": len(me.loop_triangles), "vertices": len(me.vertices),
        "dimensions_studs": [round(v, 4) for v in o.dimensions],
        "bbox_min": [round(v, 4) for v in lo], "bbox_max": [round(v, 4) for v in hi],
        "pivot": [round(v, 4) for v in o.location], "pivot_is": meta[name]["joint"],
        "joint_parent": JOINT_PARENT[name],
        "uv_range": [round(min(us), 4), round(max(us), 4), round(min(vs), 4), round(max(vs), 4)],
        "min_face_area": round(min(pl.area for pl in me.polygons), 8),
    }
report["total_triangles"] = sum(pp["triangles"] for pp in report["parts"].values())
size = hi_all - lo_all
report["overall"] = {"bbox_min": [round(v, 4) for v in lo_all], "bbox_max": [round(v, 4) for v in hi_all],
                     "height_studs": round(size.z, 4), "length_studs": round(size.y, 4), "width_studs": round(size.x, 4),
                     "head_top_studs": round(hi_all.z, 4)}
body_pivot = parts["Frog_Body"].location.copy()
# hop cycle (Blender pose values: X rotation in degrees about world X through each pivot, lift in studs)
HOP = {
    "crouch": {"_lift": -0.08, "Body": (-6, 0, 0), "Head": (-4, 0, 0), "LegBL": (-2, 0, 0), "LegBR": (-2, 0, 0),
               "LegFL": (-8, 0, 0), "LegFR": (-8, 0, 0)},
    "launch": {"_lift": 0.95, "Body": (-22, 0, 0), "Head": (-8, 0, 0), "LegBL": (137, 0, 0), "LegBR": (137, 0, 0),
               "LegFL": (-10, 0, 0), "LegFR": (-10, 0, 0)},
    "apex": {"_lift": 1.20, "Body": (-6, 0, 0), "Head": (0, 0, 0), "LegBL": (85, 0, 0), "LegBR": (85, 0, 0),
             "LegFL": (-20, 0, 0), "LegFR": (-20, 0, 0)},
    "slam": {"_lift": -0.20, "Body": (6, 0, 0), "Head": (14, 0, 0), "LegBL": (-8, 0, 0), "LegBR": (-8, 0, 0),
             "LegFL": (-18, 0, 0), "LegFR": (-18, 0, 0)},
}
HOP_TIME = {"crouch": 0.0, "launch": 0.16, "apex": 0.36, "slam": 0.58}


def hop_frame(name):
    f = HOP[name]

    def g(b):
        return round(-f.get(b, (0, 0, 0))[0], 1) + 0.0          # Blender +X rotation = Studio -X rotation
    return {"frame": name, "time_s": HOP_TIME[name], "body_lift_studs": f["_lift"], "body_pitch_deg": g("Body"),
            "head_pitch_deg": g("Head"), "hind_legs_pitch_deg": g("LegBL"), "front_legs_pitch_deg": g("LegFL")}
install = {
    "asset": STEM,
    "axis": "studio = (-x, z, y) of blender; Blender front -Y = Studio front -Z",
    "units": "studs; the model is at final size, import 1:1 and do not scale",
    "sides": "L/R are the frog's own left/right; its left is Blender +X = Studio -X",
    "origin": "all positions are relative to the model origin = the ground point under the world origin (Blender world origin)",
    "ground_point": studio((0.0, 0.0, 0.0)),
    "overall_size": studio_size(size),
    "overall_center": studio((lo_all + hi_all) / 2),
    "texture": f"textures/{TEX_PATH.name}",
    "texture_note": "one shared atlas; every MeshPart uses the same TextureID (Common rarity: no Neon, no glow)",
    "rest_rotation": "every part has identity rotation relative to the model at rest",
    "rig": "one Motor6D per part: Part0 = joint_parent, Part1 = the part, C0/C1 placed at the part's pivot",
    "locomotion": "hop",
    "locomotion_notes": {
        "what": "The frog hops and slams: crouch, launch (hind legs extend back), apex, slam landing (knocks nearby enemies back), then recover to rest.",
        "angles": "Rotation angles are about Studio X (side-to-side axis) through each part's own pivot, in degrees, same value on L and R. "
                  "Positive = the Studio +X right-hand rotation (a positive body pitch tips the nose down). body_lift_studs is the Studio Y offset of the root part. "
                  "Body pitch applies to the root, leg angles are relative to the body, head pitch is relative to the body.",
        "easing": "launch snaps (ease-out, ~0.12 s), apex is a hold, slam falls fast then squashes; recover eases back to rest over ~0.25 s",
    },
    "hop_frames": [],
    "parts": {},
}
install["hop_frames"] = [hop_frame(n) for n in ("crouch", "launch", "apex", "slam")]
for name, o in parts.items():
    lo, hi = world_bounds(o)
    install["parts"][name] = {
        "center": studio((lo + hi) / 2), "size": studio_size(hi - lo), "pivot": studio(o.location),
        "pivot_from_body_pivot": studio(o.location - body_pivot), "pivot_is": meta[name]["joint"],
        "joint_parent": JOINT_PARENT[name], "suggested_motion": MOTION[name],
    }
log("overall (w, len, h)", tuple(round(v, 3) for v in (size.x, size.y, size.z)), "tris", report["total_triangles"])

if not QUICK:
    (ROOT / "polygon-report.json").write_text(json.dumps(report, indent=2))
    (ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=2))
    select_only(objs, parts["Frog_Body"])
    bpy.ops.export_scene.gltf(filepath=str(GLB_PATH), export_format="GLB", use_selection=True, export_apply=True)
    select_only(objs, parts["Frog_Body"])
    bpy.ops.export_scene.fbx(filepath=str(FBX_PATH), use_selection=True, object_types={"MESH"},
                             axis_forward="-Z", axis_up="Y", path_mode="COPY", embed_textures=True,
                             add_leaf_bones=False)
    log("exported", FBX_PATH.name, GLB_PATH.name)

# =============================================================================================
# armature (Blender only, for posing previews; the exports above are the plain rigid parts)
# =============================================================================================
arm_data = bpy.data.armatures.new("Frog_Rig")
arm = bpy.data.objects.new("Frog_Rig", arm_data)
scene.collection.objects.link(arm)
select_only([arm])
bpy.ops.object.mode_set(mode="EDIT")
ebs = {}
for name, o in parts.items():
    eb = arm_data.edit_bones.new(name.replace("Frog_", ""))
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
    o.parent_bone = name.replace("Frog_", "")
    bpy.context.view_layer.update()
    o.matrix_world = mwo
bpy.context.view_layer.update()
drift = max((parts[n].matrix_world.translation - meta[n]["pivot"]).length for n in parts)
log("armature built; max pivot drift after bone parenting", round(drift, 6))

def pose(rots):
    """rots: {bone: (x, y, z) degrees, "_lift": studs}. Bone axes: X = world X (pitch / leg swing), Y = world Z (yaw),
    Z = world -Y (roll). _lift raises the root body bone (and so every child) along world Z."""
    lift = rots.get("_lift", 0.0)
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = [math.radians(v) for v in rots.get(pb.name, (0, 0, 0))]
        pb.location = (0.0, lift, 0.0) if pb.name == "Body" else (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()


if not QUICK:
    for im in bpy.data.images:
        if im.source == "FILE":
            im.pack()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), relative_remap=True)
    log("saved", BLEND_PATH.name)

# =============================================================================================
# previews
# =============================================================================================
setup_preview()
if not NO_PREVIEWS and QUICK:
    shots = [(shoot(OUT / fn, loc, t, res=(640, 640)), lab) for fn, lab, loc, t in VIEWS[:3]]
    shots.append((shoot(OUT / FACE_VIEW[0], FACE_VIEW[1], FACE_VIEW[2], res=(640, 640)), "Face"))
    make_sheet(shots, 4, 400, OUT / "quick-sheet.png", f"Frog quick: {report['total_triangles']} tris")
elif not NO_PREVIEWS:
    shots = [(shoot(OUT / fn, loc, t, res=(1000, 1000)), lab) for fn, lab, loc, t in VIEWS]
    face = shoot(OUT / FACE_VIEW[0], FACE_VIEW[1], FACE_VIEW[2], res=(1200, 1200))
    tl = tgt + V(0, 0, 0.45)
    poses = [
        ("Crouch (side)", HOP["crouch"], around(tgt, (-1, 0.05, 0.1), 9.0), tgt),
        ("Launch: hind legs extended back (side)", HOP["launch"], around(tl, (-1, 0.05, 0.1), 11.5), tl),
        ("Slam landing (side)", HOP["slam"], around(tgt, (-1, 0.05, 0.1), 9.0), tgt),
        ("Crouch (front 3/4)", HOP["crouch"], around(tgt, (-0.6, -1.0, 0.25), 9.0), tgt),
        ("Launch (front 3/4)", HOP["launch"], around(tl, (-0.6, -1.0, 0.25), 11.5), tl),
        ("Slam landing (front 3/4)", HOP["slam"], around(tgt, (-0.6, -1.0, 0.25), 9.0), tgt),
        ("Head tilt 22 + nod down 18", {"Head": (18, 0, 22)}, around(ft, (-0.5, -1.0, 0.25), 5.5), ft),
        ("Head up 22 + turn 28", {"Head": (-22, 28, 0)}, around(tgt, (0.75, -0.75, 0.4), 9.0), tgt),
        ("Launch from behind (hinds extended)", HOP["launch"], around(tl, (0.55, 1.0, 0.3), 11.5), tl),
    ]
    pose_items = []
    for i, (lab, rots, loc, t) in enumerate(poses):
        pose(rots)
        pose_items.append((shoot(OUT / f"_pose-{i}.png", loc, t, res=(700, 700)), lab))
    pose({})
    make_sheet(pose_items, 3, 500, OUT / "pose-check.png", "Frog: hop pose check (crouch, launch, slam) through the joint pivots",
               "Hop cycle poses plus head tilt / turn, each part rotated about its own pivot (Blender armature, preview only). Look for gaps at shoulders, hips and neck.")
    for pth, _ in pose_items:
        pth.unlink()
    make_sheet([shots[0], shots[1], shots[2], shots[3], (face, "Face close-up"),
                (OUT / "pose-check.png", "Pose check (crouch, launch, slam, head)")], 3, 520, OUT / "sheet.png",
               f"Frog pet (Common, space / knockback): {report['total_triangles']:,} tris, one 1024 atlas",
               "Blender 5.2 Eevee renders. Every part is one fused surface. Blender-verified, Studio untested.")
log("done")
