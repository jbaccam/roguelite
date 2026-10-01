"""Fox pet (Rare, strong suit: damage) for the roguelite.

Builds the whole art asset from scratch in background Blender 5.2. Self-contained: no code from
sibling kits (the fused-surface, painter, bake and export method is the approved Golden Retriever
pipeline, copied in).

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 \
        --python build_fox.py
    ... -- --quick --out <dir>        iteration mode: 1024 bake, a few Eevee views, no exports
    ... -- --no-previews              exports + reports only

Writes (inside this folder): fox.blend, textures/fox.png (1024, one atlas shared by every part),
exports/fbx + exports/glb, polygon-report.json, studio-install-data.json and previews/*.png.

Coordinates: Blender Z-up, 1 unit = 1 stud (final size, import 1:1), paws on z = 0, the fox faces
-Y and its own left is +X. Studio = (-x, z, y) of Blender, so Studio front is -Z.

Look: stylized chibi low-poly, painterly baked texture. The face (eyes, brows, smile) is PAINTED over
shallow relief. Every furry part (body, head, legs, tail, ears) is ONE fused surface (voxel SDF union,
smooth, decimate); the tail is one fused plume whose cream tip is blended by colour only.
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
STEM = "fox"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    if name in ARGS:
        i = ARGS.index(name)
        if i + 1 < len(ARGS):
            return ARGS[i + 1]
    return default


VARIANT = "fox"
QUICK = "--quick" in ARGS
NO_PREVIEWS = "--no-previews" in ARGS
DEBUG_MAPS = "--debug-maps" in ARGS
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
    print(f"[fox {time.time() - T0:6.1f}s]", *a, flush=True)


# zones (per face) tell the painter what each texel is
(Z_FUR, Z_CLUMP, Z_EAR, Z_NOSE, Z_SCARF, Z_KNOT, Z_CHARM, Z_CORD) = range(1, 9)
# part ids (object pass index)
P_BODY, P_HEAD, P_EARL, P_EARR, P_LEGFL, P_LEGFR, P_LEGBL, P_LEGBR, P_TAIL, P_SCARF = range(1, 11)

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

    def fringe(self, strand, lobes, zone=Z_CLUMP, rows=5, cpl=4, th=(0.09, 0.025), notch=0.34, lob_pow=0.75,
               end_len=0.5, bottom=0.5, phase=0.0, valley=0.30, valley_from=0.0, end_sink=0.0):
        """A fur mass: a thick sheet grown from a root line whose far edge splits into `lobes`
        pointed locks. strand(u, s) -> (point, outward normal) gives the sheet's mid-surface
        (u across the root line, s root -> tip). Each lock is a little thicker in its middle so it
        reads as its own clump; tuft_t = s and lock = 0 in the grooves .. 1 on the lock ridges."""
        cols = lobes * cpl + 1
        T, B = [], []
        for i in range(rows + 1):
            sn = i / rows
            rt, rb = [], []
            for j in range(cols):
                u = j / (cols - 1)
                lob = abs(math.sin(math.pi * (u * lobes + phase))) ** lob_pow
                smax = 1.0 - notch * (1.0 - lob)
                e = min(u, 1.0 - u) * 2.0
                smax *= end_len + (1.0 - end_len) * min(1.0, e * 2.2) ** 0.5
                s = sn * smax
                c, n = strand(u, s)
                if end_sink:
                    c = c - n * (end_sink * (1.0 - min(1.0, e * 3.0) ** 0.6))   # side ends sink into the coat
                c2, _ = strand(u, min(s + 0.03, 1.0))
                fl = c2 - c
                fl = tuple(fl.normalized()) if fl.length > 1e-7 else (0.0, 0.0, 0.0)
                t = th[0] + (th[1] - th[0]) * sn ** 1.4
                vf = min(1.0, max(0.0, (sn - valley_from) / max(1e-6, 1.0 - valley_from)))
                vly = 1.0 - (1.0 - valley) * vf * vf * (3 - 2 * vf)
                bulge = vly + (1.0 - vly) * math.sqrt(abs(math.sin(math.pi * (u * lobes + phase))))
                rt.append(self.v(c + n * t * 0.5 * bulge, s, fl, lob))
                rb.append(self.v(c - n * t * bottom * bulge, s, fl, lob))
            T.append(rt)
            B.append(rb)
        for i in range(rows):
            for j in range(cols - 1):
                self.f([T[i][j], T[i][j + 1], T[i + 1][j + 1], T[i + 1][j]])
                self.f([B[i][j], B[i + 1][j], B[i + 1][j + 1], B[i][j + 1]])
        for j in range(cols - 1):
            self.f([T[rows][j], B[rows][j], B[rows][j + 1], T[rows][j + 1]])
            self.f([T[0][j], T[0][j + 1], B[0][j + 1], B[0][j]])
        for i in range(rows):
            self.f([T[i][0], T[i + 1][0], B[i + 1][0], B[i][0]])
            self.f([T[i][cols - 1], B[i][cols - 1], B[i + 1][cols - 1], T[i + 1][cols - 1]])
        return self.close(zone)

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

    CLUMP_SECT = ((-1.0, 0.0), (-0.62, 0.78), (0.0, 1.0), (0.62, 0.78), (1.0, 0.0), (0.45, -0.42), (-0.45, -0.42))
    CLUMP_ST = ((0.0, 0.60, 0.50), (0.20, 0.95, 0.95), (0.44, 1.0, 1.0), (0.67, 0.78, 0.80), (0.86, 0.44, 0.48))

    def clump(self, base, normal, direction, length, width, thick, zone=Z_CLUMP, bend=0.10, side=0.0,
              twist=0.0, sink=1.0, tip_lift=0.0):
        """One sculpted fur clump: a ridged (fur-lock crease down the middle), tapering, gently
        curved flame whose root is sunk into the surface it grows from. tuft_t runs 0 (root) ->
        1 (tip) for the painter."""
        n = Vector(normal).normalized()
        d = Vector(direction)
        d = (d - n * d.dot(n))
        if d.length < 1e-6:
            d = n.orthogonal()
        d.normalize()
        sv = d.cross(n).normalized()
        L = length

        def path(s):
            return (Vector(base) + d * (L * s) + n * (bend * L * s * s + tip_lift * L * s ** 4
                                                      - thick * sink * (1.0 - s) ** 2)
                    + sv * (side * L * s * s))

        rings = []
        for s, wf, tf in self.CLUMP_ST:
            c = path(s)
            t = (path(min(s + 0.02, 1.0)) - path(max(s - 0.02, 0.0))).normalized()
            vv = (n - t * n.dot(t)).normalized()
            u = t.cross(vv).normalized()
            ang = twist * s
            u, vv = u * math.cos(ang) + vv * math.sin(ang), vv * math.cos(ang) - u * math.sin(ang)
            w, h = 0.5 * width * wf, 0.5 * thick * tf
            rings.append([self.v(c + u * (w * a) + vv * (h * b), s, tuple(t)) for a, b in self.CLUMP_SECT])
        tip = self.v(path(1.0), 1.0, tuple(d))
        k = len(self.CLUMP_SECT)
        for r0, r1 in zip(rings, rings[1:]):
            for i in range(k):
                j = (i + 1) % k
                self.f([r0[i], r0[j], r1[j], r1[i]])
        for i in range(k):
            self.f([rings[-1][i], rings[-1][(i + 1) % k], tip])
        self.f(rings[0][::-1])
        return self.close(zone)

    def cull_hidden(self):
        """Delete faces buried inside another closed shell of this same rigid part (they can never
        be seen, whatever the pose): every corner and the centre must be inside another shell."""
        bm = self.bm
        bm.faces.ensure_lookup_table()
        bm.faces.index_update()
        bm.normal_update()
        shell_of = {}
        sid = 0
        for f0 in bm.faces:
            if f0.index in shell_of:
                continue
            stack = [f0]
            shell_of[f0.index] = sid
            while stack:
                fc = stack.pop()
                for e in fc.edges:
                    for g in e.link_faces:
                        if g.index not in shell_of:
                            shell_of[g.index] = sid
                            stack.append(g)
            sid += 1
        tree = BVHTree.FromBMesh(bm)

        def inside_other(pt, d, own):
            o = pt + d * 1e-4
            for _ in range(10):
                loc, nrm, idx, _ = tree.ray_cast(o, d, 3.0)
                if loc is None:
                    return False
                if shell_of.get(idx) == own:
                    o = loc + d * 1e-4
                    continue
                return nrm.dot(d) > 0.0
            return False

        kill = []
        for fc in bm.faces:
            own = shell_of[fc.index]
            n = fc.normal
            if n.length < 0.5:
                continue
            pts = [fc.calc_center_median()] + [v.co.copy() for v in fc.verts]
            if all(inside_other(q, n, own) for q in pts):
                kill.append(fc)
        if kill:
            bmesh.ops.delete(bm, geom=kill, context="FACES")
            loose = [v for v in bm.verts if not v.link_faces]
            bmesh.ops.delete(bm, geom=loose, context="VERTS")
        log(self.name, "culled", len(kill), "buried faces")

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
        self.cull_hidden()
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


def tidy(grid, F, vs, fs, passes=8, pin=None):
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
NECK_PIVOT = V(0.0, -0.52, 1.18)
CRAN = [(-0.36, 1.54, 0.15, 0.14), (-0.42, 1.54, 0.36, 0.33), (-0.52, 1.54, 0.49, 0.43),
        (-0.66, 1.54, 0.55, 0.46), (-0.80, 1.53, 0.565, 0.46), (-0.94, 1.52, 0.52, 0.43),
        (-1.05, 1.50, 0.43, 0.37), (-1.12, 1.485, 0.31, 0.28), (-1.15, 1.47, 0.16, 0.14)]
CRAN_TIP = (0, -1.175, 1.465)
HS, HC, EYE_BIG = 1.2, V(0.0, -0.55, 1.15), 1.12      # head scale about HC; extra eye scale
EYE_X, EYE_Z, EYE_R, EYE_TILT = 0.34, 1.60, (0.122, 0.146), -0.20
FACE = {}          # filled by build_head: eyes and nose frames for the painter
FUSED = {}         # (grid, component fields) for the painter's muzzle / cheek masks
EAR_FIELD = {}     # the ear's inner-fluff field (left ear geometry; right ear is its mirror)
EAR_E = V(0.36, -0.66, 1.97)
EAR_A = V(0.20, 0.10, 0.97).normalized()
EAR_LEN = 0.66

BODY_SECS = [  # (y, zc, rx, rz, n)
    (0.51, 0.82, 0.11, 0.11, 2.2), (0.46, 0.81, 0.27, 0.24, 2.3), (0.35, 0.80, 0.375, 0.34, 2.4),
    (0.19, 0.79, 0.41, 0.375, 2.5), (0.00, 0.79, 0.40, 0.375, 2.5), (-0.18, 0.80, 0.40, 0.385, 2.5),
    (-0.33, 0.84, 0.375, 0.38, 2.4), (-0.44, 0.90, 0.30, 0.32, 2.3), (-0.49, 0.95, 0.17, 0.19, 2.2)]
COLLAR_C = V(0.0, -0.50, 0.98)
COLLAR_A = V(0.0, -0.30, 0.95).normalized()
KNOT = {}


def catmull(pts, t):
    n = len(pts) - 1
    f = min(max(t, 0.0), 1.0) * n
    k = min(int(f), n - 1)
    u = f - k
    p0, p1, p2, p3 = pts[max(k - 1, 0)], pts[k], pts[k + 1], pts[min(k + 2, n)]
    return 0.5 * ((2 * p1) + (p2 - p0) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                  + (3 * p1 - p0 - 3 * p2 + p3) * u ** 3)


def body_section(y):
    s = sorted(BODY_SECS, key=lambda r: r[0])
    for a, b in zip(s, s[1:]):
        if a[0] <= y <= b[0]:
            t = (y - a[0]) / (b[0] - a[0])
            return tuple(a[k] + (b[k] - a[k]) * t for k in range(1, 5))
    return s[0][1:]


# =============================================================================================
# the fox
# =============================================================================================
def build_body():
    p = Part("Fox_Body", P_BODY, (0.0, 0.0, 0.86), "body centre (root part; bob/roll pivot)")
    secs = [dict(c=(0, y, zc), rx=rx, rz=rz, n=n) for y, zc, rx, rz, n in BODY_SECS]
    neck = [dict(c=(0, -0.34, 0.92), rx=0.30, rz=0.30), dict(c=(0, -0.44, 1.06), rx=0.31, rz=0.30),
            dict(c=(0, -0.54, 1.22), rx=0.29, rz=0.28), dict(c=(0, -0.62, 1.36), rx=0.25, rz=0.24)]
    trunk = shape(lambda t: t.loft(secs, Z_FUR, sides=18, cap0=(0, 0.56, 0.82), cap1=(0, -0.55, 0.97)))
    nk = shape(lambda t: t.loft(neck, Z_FUR, sides=14, cap0="flat", cap1="flat", up=(0, -1, 0)))
    G = Grid((-0.56, -0.92, 0.40), (0.56, 0.80, 1.52), 0.016, sym_x=True)
    d_trunk, d_neck = mesh_sdf(G, trunk), mesh_sdf(G, nk)
    base = smin(d_trunk, d_neck, 0.10)
    chest = sd_ell(G.P, (0, -0.47, 0.97), AXES, (0.22, 0.17, 0.23))
    base = smin(base, chest, 0.10)
    vs, fs = extract(G, blur(base), 900, name="body_fur")
    flow = blend_flow(vs, [(G.sample(d_trunk, vs), (0, -1, 0)), (G.sample(d_neck, vs), (0, -0.39, 0.92))])
    p.add_mesh(vs, fs, Z_FUR, np.zeros(len(vs)), flow)
    build_collar(p, p.bvh())
    return p


def collar_dir(theta):
    a = COLLAR_A
    ex = V(1, 0, 0)
    ey = a.cross(ex).normalized()
    return ex * math.sin(theta) - ey * math.cos(theta)      # theta 0 = front, + toward the fox's left


def build_collar(p, tree):
    """The scarf band: a soft loop hugging the fused neck; the knot (separate part) sits front-left."""
    secs, n_seg = [], 22
    th_k = math.pi / 2 - 0.50
    for i in range(n_seg):
        th = 2 * math.pi * i / n_seg
        d = collar_dir(th)
        hit = tree.ray_cast(COLLAR_C + d * 1.0, -d, 1.6)
        on = hit[0] if hit[0] is not None else COLLAR_C + d * 0.30
        secs.append(dict(c=on + d * (0.034 + 0.006 * math.sin(3 * th + 0.5)), rx=0.062, rz=0.095, n=2.6))
        if abs(th - th_k) < math.pi / n_seg + 1e-6 or i == round(th_k / (2 * math.pi) * n_seg):
            KNOT["c"], KNOT["d"] = on + d * 0.07, d
    p.loft(secs, Z_SCARF, sides=8, up=tuple(COLLAR_A), closed_path=True, tvals=[0.0] * n_seg)
    p.close(Z_SCARF)


def build_scarf():
    kc, d = KNOT["c"], KNOT["d"]
    p = Part("Fox_Scarf", P_SCARF, kc, "scarf knot (flutter / sway pivot)")
    p.ellipsoid(kc, (0.11, 0.095, 0.10), (1, 0.1, 0.1), Z_KNOT, useg=8, vseg=5)
    # two short tie ends: a longer one that flutters out behind, a shorter one lying on the chest
    def strip(L, dx, dy, sway, w0, w1):
        secs, tv = [], []
        for i in range(6):
            s = i / 5
            c = V(kc.x + 0.04 + dx * s + 0.018 * math.sin(2 * math.pi * 1.3 * s + 0.6),
                  kc.y + dy * s ** 1.5 + sway * math.sin(2 * math.pi * 1.1 * s),
                  kc.z - 0.06 - L * s)
            secs.append(dict(c=c, rx=w0 + (w1 - w0) * s ** 1.4, rz=0.034, n=3.2))
            tv.append(s)
        p.loft(secs, Z_SCARF, sides=6, cap0="flat", cap1="flat", up=(1, 0, 0), tvals=tv)
        p.close(Z_SCARF)
    strip(0.62, 0.30, 0.34, 0.04, 0.10, 0.14)
    strip(0.42, 0.12, 0.08, 0.025, 0.085, 0.115)
    # the Rare accent: a small painted claw charm on a cord ring hanging from the knot
    hp = kc + d * 0.10 + V(-0.03, 0, -0.125)
    ring = [dict(c=hp + V(math.cos(2 * math.pi * i / 8) * 0.038, 0, math.sin(2 * math.pi * i / 8) * 0.038),
                 rx=0.013, rz=0.013) for i in range(8)]
    p.loft(ring, Z_CORD, sides=4, up=(0, 1, 0), closed_path=True)
    p.close(Z_CORD)
    fs_ = hp + V(0, -0.004, -0.038)
    fsec = []
    for s, r in ((0.0, 0.050), (0.2, 0.050), (0.45, 0.040), (0.7, 0.026), (0.88, 0.014)):
        c = fs_ + V(0.025 * s * s, -0.045 * s * s, -0.21 * s)
        fsec.append(dict(c=c, rx=r, rz=r * 0.8))
    p.loft(fsec, Z_CHARM, sides=6, cap0="flat", cap1=tuple(fs_ + V(0.025, -0.045, -0.21)), up=(0, 1, 0))
    p.close(Z_CHARM)
    wrap = [dict(c=fs_ + V(0, -0.0008, -0.04) + V(math.cos(2 * math.pi * i / 8) * 0.053, math.sin(2 * math.pi * i / 8) * 0.043, 0),
                 rx=0.010, rz=0.02) for i in range(8)]
    p.loft(wrap, Z_CORD, sides=4, up=(0, 0, 1), closed_path=True)
    p.close(Z_CORD)
    return p


def build_head():
    p = Part("Fox_Head", P_HEAD, NECK_PIVOT, "neck joint (nod / tilt / turn pivot)")

    def cheek_mod(k):
        def mod(a, x, z):
            m = 1.0 + 0.09 * k * (gauss(angdiff(a, -0.5), 0.5) + gauss(angdiff(a, math.pi + 0.5), 0.5))
            m *= 1.0 - 0.03 * gauss(angdiff(a, math.pi / 2), 0.6)
            return x * m, z * m
        return mod

    secs = []
    for i, (y, zc, rx, rz) in enumerate(CRAN):
        k = math.sin(math.pi * i / (len(CRAN) - 1))
        secs.append(dict(c=(0, y, zc), rx=rx, rz=rz, n=2.25, mod=cheek_mod(k)))
    cr = shape(lambda t: t.loft(secs, Z_FUR, sides=22, cap0=(0, CRAN[0][0] + 0.05, CRAN[0][1]), cap1=CRAN_TIP,
                                up=(0, 0, 1)))
    G = Grid((-0.80, -1.62, 1.02), (0.80, -0.22, 2.22), 0.012, sym_x=True)
    P = G.P
    d_cran = mesh_sdf(G, cr)
    # one muzzle mass that flows out of the face: a broad base narrowing to a small rounded tip, with a
    # small lower jaw under it; no stuck-on beak, just a gentle stop
    d_up = smin(sd_ell(P, (0, -1.06, 1.405), AXES, (0.205, 0.22, 0.15)),
                sd_ell(P, (0, -1.31, 1.41), AXES, (0.115, 0.20, 0.10)), 0.12)
    d_jaw = sd_ell(P, (0, -1.06, 1.29), AXES, (0.15, 0.16, 0.085))
    d_mz = smin(d_up, d_jaw, 0.06)
    cheeks = None
    for sx in (1, -1):
        c1 = sd_ell(P, (sx * 0.44, -0.93, 1.40), AXES, (0.12, 0.18, 0.13))
        R = lock_axes(V(sx * 0.85, -0.2, 0.25), V(0, 0.6, -0.6))
        c2 = sd_ell(P, (sx * 0.46, -0.82, 1.30), R, (0.09, 0.17, 0.07))
        c = smin(c1, c2, 0.07)
        cheeks = c if cheeks is None else np.minimum(cheeks, c)
    d_rest = smin(d_cran, cheeks, 0.09)
    head = smin(d_rest, d_mz, 0.11)
    FUSED["head"] = (G, dict(mz=d_mz, rest=d_rest, cheek=cheeks))
    vs, fs = extract(G, blur(head), 1200, name="head_fur")
    flow = blend_flow(vs, [(G.sample(d_cran, vs), (0, -1, 0)), (G.sample(d_mz, vs), (0, -1, 0))])
    p.add_mesh(vs, fs, Z_FUR, np.zeros(len(vs)), flow)
    # nose: a small rounded inverted triangle at the muzzle tip
    nz = 1.455

    def nose_mod(a, x, z):
        if z < 0:
            x *= 1.0 + 0.55 * z / 0.06
        return x, z

    ns = [dict(c=(0, -1.405, nz - 0.005), rx=0.072, rz=0.052, n=2.4, mod=nose_mod),
          dict(c=(0, -1.465, nz), rx=0.088, rz=0.063, n=2.4, mod=nose_mod),
          dict(c=(0, -1.502, nz + 0.003), rx=0.070, rz=0.050, n=2.3, mod=nose_mod)]
    p.loft(ns, Z_NOSE, sides=16, cap0="flat", cap1=(0, -1.522, nz + 0.005))
    p.close(Z_NOSE)
    # chibi: scale the whole finished head up about HC (the painter's fields follow the lattice)
    for v in p.bm.verts:
        v.co = HC + (v.co - HC) * HS
    G.lo = np.array(HC[:]) + (G.lo - np.array(HC[:])) * HS
    G.h = G.h * HS
    nzs = HC.z + HS * (nz - HC.z)
    FACE["nose"] = dict(c=V(0, HC.y + HS * (-1.47 - HC.y), nzs), top=nzs + 0.063 * HS, bottom=nzs - 0.063 * HS)
    tree = p.bvh()
    ez = HC.z + HS * (EYE_Z - HC.z)
    eye_rs = (EYE_R[0] * HS * EYE_BIG, EYE_R[1] * HS * EYE_BIG)
    for side in (1, -1):
        ex = EYE_X * HS * side
        org = V(ex * 2.2, -2.4, ez)
        hit = tree.ray_cast(org, (V(ex, HC.y + HS * (-0.62 - HC.y), ez) - org).normalized())
        loc, nrm = hit[0], hit[1]
        u = V(0, 0, 1).cross(nrm).normalized() * -1.0         # points to the fox's right (-X)
        vv = nrm.cross(u).normalized()
        if vv.z < 0:
            vv = -vv
        FACE[f"eye{side}"] = dict(c=loc, n=nrm, u=u, v=vv, r=eye_rs, side=side, tilt=EYE_TILT)
    return p


def build_ear(side):
    """One thick, broad, softly pointed ear: a single fused surface with a shallow inner dish and a
    little tuft of inner fluff growing out of it (built for +X, mirrored for the other side)."""
    s = side
    E, a = EAR_E, EAR_A
    u = V(0, 1, 0).cross(a).normalized()
    w = a.cross(u).normalized()
    ts = [(-0.06, 0.19, 0.115), (0.10, 0.205, 0.115), (0.25, 0.19, 0.105), (0.40, 0.155, 0.09), (0.52, 0.105, 0.072),
          (0.60, 0.058, 0.052)]
    secs = []
    for t, rx, rz in ts:
        bend = V(0.05, 0, 0) * (max(t, 0.0) / EAR_LEN) ** 2
        secs.append(dict(c=E + a * t + bend, rx=rx, rz=rz, n=2.3))
    tip = tuple(E + a * 0.675 + V(0.05, 0, 0) * (0.675 / EAR_LEN) ** 2)
    lf = shape(lambda t: t.loft(secs, Z_EAR, sides=20, cap0="flat", cap1=tip, up=(0, 1, 0)))
    G = Grid((0.06, -0.90, 1.90), (0.72, -0.44, 2.76), 0.009)
    d_ear = mesh_sdf(G, lf)
    R = np.array([u[:], w[:], a[:]])
    ctr = E + a * 0.26 - w * 0.125
    dish = sd_ell(G.P, ctr, R, (0.09, 0.06, 0.22))
    fluff = sd_ell(G.P, E + a * 0.14 - w * 0.085, R, (0.065, 0.04, 0.10))
    inner = sd_ell(G.P, E + a * 0.27 - w * 0.10, R, (0.105, 0.10, 0.27))
    d = smin(ssub(d_ear, dish, 0.03), fluff, 0.03)
    EAR_FIELD["inner"] = (G, inner)
    vs, fs = extract(G, blur(d), 240, name="ear_fur")
    pivot = V(s * E.x, E.y, E.z)
    p = Part(f"Fox_Ear{'L' if s > 0 else 'R'}", P_EARL if s > 0 else P_EARR, pivot, "ear root on the skull (flop pivot)")
    flow = np.tile(np.array((0.0, 0.1, 1.0)), (len(vs), 1))
    if s < 0:
        m = np.array((-1.0, 1.0, 1.0))
        vs, flow, fs = vs * m, flow * m, [tuple(reversed(fc)) for fc in fs]
    p.add_mesh(vs, fs, Z_EAR, np.zeros(len(vs)), flow)
    return p


def paw_parts(c, k):
    """Chunky paw: rounded block plus four short toes (centre, radii, axis)."""
    cx, cy = c.x, c.y
    secs = [dict(c=(cx, cy, 0.02), rx=0.135 * k, rz=0.16 * k, n=2.6),
            dict(c=(cx, cy - 0.005, 0.06), rx=0.152 * k, rz=0.175 * k, n=2.6),
            dict(c=(cx, cy + 0.01, 0.12), rx=0.145 * k, rz=0.16 * k, n=2.5),
            dict(c=(cx, cy + 0.03, 0.17), rx=0.125 * k, rz=0.13 * k, n=2.3)]
    toes = []
    for ang in (-0.6, -0.2, 0.2, 0.6):
        tx = cx + math.sin(ang) * 0.125 * k
        ty = cy - math.cos(ang) * 0.14 * k - 0.02
        toes.append(((tx, ty, 0.062), (0.05 * k, 0.06 * k, 0.054 * k), (math.sin(ang) * 0.3, -1.0, 0.9)))
    return secs, toes


FRONT_LEG = dict(path=[V(0.23, -0.25, 0.64), V(0.245, -0.26, 0.50), V(0.25, -0.27, 0.35), V(0.25, -0.28, 0.20),
                       V(0.25, -0.29, 0.09)],
                 rx=(0.19, 0.19, 0.165, 0.15, 0.145), rz=(0.20, 0.20, 0.175, 0.155, 0.15), sides=12,
                 cap0=(0.22, -0.24, 0.72), paw=(V(0.25, -0.32, 0), 1.08), lo=(0.0, -0.72, -0.05),
                 hi=(0.52, 0.12, 0.80), target=330, blob=None)
REAR_LEG = dict(path=[V(0.24, 0.27, 0.66), V(0.285, 0.30, 0.54), V(0.28, 0.33, 0.38), V(0.265, 0.32, 0.22),
                      V(0.26, 0.29, 0.09)],
                rx=(0.19, 0.23, 0.19, 0.155, 0.145), rz=(0.22, 0.27, 0.20, 0.16, 0.15), sides=14,
                cap0=(0.23, 0.26, 0.74), paw=(V(0.26, 0.26, 0), 1.10), lo=(0.0, -0.05, -0.05),
                hi=(0.56, 0.80, 0.82), target=380, blob=((0.29, 0.32, 0.58), (0.16, 0.20, 0.17)))
LEG_CACHE = {}


def fused_leg(spec):
    """One fused surface for the fox's LEFT leg (the right leg is its exact mirror)."""
    key = id(spec)
    if key in LEG_CACHE:
        return LEG_CACHE[key]
    path = spec["path"]
    secs = [dict(c=path[i], rx=spec["rx"][i], rz=spec["rz"][i], n=2.3) for i in range(len(path))]
    lg = shape(lambda t: t.loft(secs, Z_FUR, sides=spec["sides"], cap0=spec["cap0"], cap1="flat", up=(0, -1, 0)))
    pc, pk = spec["paw"]
    psecs, toes = paw_parts(pc, pk)
    pw = shape(lambda t: t.loft(psecs, Z_FUR, sides=16, cap0="flat", cap1=(pc.x, pc.y + 0.03, 0.2), up=(0, -1, 0)))
    G = Grid(spec["lo"], spec["hi"], 0.011)
    d_leg, d_paw = mesh_sdf(G, lg), mesh_sdf(G, pw)
    base = smin(d_leg, d_paw, 0.05)
    if spec["blob"]:
        bc, br = spec["blob"]
        base = smin(base, sd_ell(G.P, bc, AXES, br), 0.08)
    d_toes = None
    for c, r, ax in toes:
        d = sd_ell(G.P, c, track_axes(ax), r)
        d_toes = d if d_toes is None else np.minimum(d_toes, d)
    base = smin(base, d_toes, 0.016)
    vs, fs = extract(G, blur(base), spec["target"], name="leg_fur")
    flow = blend_flow(vs, [(G.sample(d_leg, vs), (0, -0.05, -1)), (G.sample(d_paw, vs), (0, -1, 0))])
    LEG_CACHE[key] = (vs, fs, np.zeros(len(vs)), flow)
    return LEG_CACHE[key]


def leg_part(spec, side, name, pid, pivot, joint):
    p = Part(name, pid, pivot, joint)
    vs, fs, tuft, flow = fused_leg(spec)
    if side < 0:
        m = np.array((-1.0, 1.0, 1.0))
        vs, flow, fs = vs * m, flow * m, [tuple(reversed(fc)) for fc in fs]
    p.add_mesh(vs, fs, Z_FUR, tuft, flow)
    return p


def build_front_leg(side):
    s = side
    return leg_part(FRONT_LEG, s, f"Fox_LegF{'L' if s > 0 else 'R'}", P_LEGFL if s > 0 else P_LEGFR,
                    V(s * 0.23, -0.25, 0.64), "shoulder (swing about the side-to-side axis)")


def build_rear_leg(side):
    s = side
    return leg_part(REAR_LEG, s, f"Fox_LegB{'L' if s > 0 else 'R'}", P_LEGBL if s > 0 else P_LEGBR,
                    V(s * 0.26, 0.28, 0.66), "hip (swing about the side-to-side axis)")


TAIL_PATH = [(0.38, 0.80), (0.70, 0.82), (1.02, 0.94), (1.30, 1.17), (1.42, 1.50)]
TAIL_RS = [0.0, 0.12, 0.35, 0.60, 0.82, 0.94, 1.0]
TAIL_RR = [0.13, 0.195, 0.33, 0.415, 0.365, 0.23, 0.085]


def build_tail():
    """ONE continuous plume: a union of spheres swept along a soft S-curve whose radius swells to a
    big brush and closes in a rounded tip (a few broad waves in the radius at most). The cream tip is
    colour only (tuft = distance along the path)."""
    pivot = V(0.0, 0.40, 0.80)
    p = Part("Fox_Tail", P_TAIL, pivot, "tail root (wag = turn about the vertical axis)")
    pts = [np.array(q) for q in TAIL_PATH]
    N = 160
    C = np.array([catmull(pts, i / (N - 1)) for i in range(N)])
    seg = np.linalg.norm(np.diff(C, axis=0), axis=1)
    sv = np.concatenate([[0.0], np.cumsum(seg)]) / seg.sum()
    R = np.interp(sv, TAIL_RS, TAIL_RR) * (1.0 + 0.04 * np.sin(2 * np.pi * 2.0 * sv + 0.6) * sstep(0.05, 0.3, sv)
                                           * sstep(1.0, 0.8, sv))
    G = Grid((-0.55, 0.15, 0.35), (0.55, 2.00, 2.12), 0.012, sym_x=True)
    X, Y, Z = G.P[..., 0], G.P[..., 1], G.P[..., 2]
    F = np.full(X.shape, 1e9)
    for i in range(N):
        F = np.minimum(F, np.sqrt(X * X + (Y - C[i, 0]) ** 2 + (Z - C[i, 1]) ** 2) - R[i])
    vs, fs = extract(G, blur(F, 1), 900, name="tail_fur")
    D = np.sqrt(vs[:, None, 0] ** 2 + (vs[:, None, 1] - C[None, :, 0]) ** 2 + (vs[:, None, 2] - C[None, :, 1]) ** 2) - R[None, :]
    idx = np.argmin(D, axis=1)
    tuft = sv[idx]
    tan = np.gradient(C, axis=0)
    flow = np.stack([np.zeros(len(vs)), tan[idx, 0], tan[idx, 1]], 1)
    flow /= np.maximum(np.linalg.norm(flow, axis=1), 1e-6)[:, None]
    p.add_mesh(vs, fs, Z_FUR, tuft, flow)
    return p

# =============================================================================================
# painting helpers (numpy)
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


def cell_hash(a, b, k=0.0):
    v = np.sin(a * 12.9898 + b * 78.233 + k * 37.719) * 43758.5453
    return v - np.floor(v)

def stroke_masks(fu, fv, cw=0.11, ch=0.26, k=0.0):
    """Broad lens-shaped brush strokes laid along the fur flow on a jittered lattice.
    Returns (light, dark) soft masks."""
    row = np.floor(fv / ch)
    uu = fu / cw + cell_hash(row, 3.1, k) * 3.0
    col = np.floor(uu)
    h1 = cell_hash(row, col, k + 1)
    h2 = cell_hash(row, col, k + 2)
    ly = fv / ch - row
    lx = uu - col - 0.5 - (h2 - 0.5) * 0.35
    a0, a1 = 0.05 + 0.2 * h2, 0.75 + 0.25 * h1
    t = np.clip((ly - a0) / np.maximum(a1 - a0, 1e-3), 0, 1)
    w = (0.22 + 0.12 * h1) * np.sin(np.pi * t) ** 0.8 * (1.0 - 0.4 * t)
    m = sstep(w + 0.02, np.maximum(w - 0.08, 0), np.abs(lx)) * (w > 0.02)
    return m * (h1 > 0.45), m * (h1 < 0.30)

# =============================================================================================
# painting (numpy). Colour is continuous across every join: it comes from position, normals and a
# few fields, never from part boundaries.
# =============================================================================================
ORANGE = rgb(238, 124, 40)
ORANGE_LT = rgb(249, 154, 68)
ORANGE_DK = rgb(204, 94, 30)
RUST = rgb(178, 76, 28)
GOLD = ORANGE                       # atlas fill colour
CREAM = rgb(252, 236, 208)
CREAM_LT = rgb(255, 248, 232)
SOCK = rgb(56, 40, 40)
SOCK_LT = rgb(92, 66, 60)
EAR_DARK = rgb(64, 42, 36)
NOSE = rgb(34, 27, 33)
SCARF = (rgb(200, 42, 54), rgb(238, 92, 84), rgb(132, 24, 44))
BONE = (rgb(246, 236, 214), rgb(255, 252, 240), rgb(196, 172, 134))
CORD = (rgb(132, 86, 52), rgb(176, 122, 78), rgb(84, 52, 34))
EYE_DARK, EYE_IRIS, EYE_IRIS_LT, EYE_LINE = rgb(28, 19, 20), rgb(190, 104, 30), rgb(236, 160, 64), rgb(56, 32, 24)
BROW = rgb(122, 54, 22)
COOL = np.array((0.80, 0.85, 1.0))
POLE_FADE = 1.0


def fur_param(P, part):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    fu = np.zeros(len(P))
    fv = np.zeros(len(P))
    bs = sorted(BODY_SECS, key=lambda r: r[0])
    zc = np.interp(y, [r[0] for r in bs], [r[1] for r in bs])
    body = part == P_BODY
    fu = np.where(body, np.arctan2(x, z - zc) * 0.36, fu)
    fv = np.where(body, y, fv)
    head = part == P_HEAD
    hax = np.array((0.0, 0.90, -0.30))
    hax /= np.linalg.norm(hax)
    hd = P - np.array((0.0, -0.85, 1.59))
    along_h = hd @ hax
    perp = hd - along_h[:, None] * hax
    e1 = np.array((1.0, 0.0, 0.0))
    e2 = np.cross(hax, e1)
    fu = np.where(head, np.arctan2(perp @ e1, perp @ e2) * 0.40, fu)
    fv = np.where(head, along_h, fv)
    global POLE_FADE
    POLE_FADE = np.where(head, sstep(0.10, 0.25, np.linalg.norm(perp, axis=1)), 1.0)
    for pid, lx, ly in ((P_LEGFL, 0.23, -0.25), (P_LEGFR, -0.23, -0.25), (P_LEGBL, 0.26, 0.29), (P_LEGBR, -0.26, 0.29)):
        m = part == pid
        fu = np.where(m, np.arctan2(x - lx, -(y - ly)) * 0.15, fu)
        fv = np.where(m, -z, fv)
    tail = part == P_TAIL
    fu = np.where(tail, x + 0.3 * np.arctan2(x, z - 0.9), fu)
    fv = np.where(tail, 0.8 * y + 0.5 * z, fv)
    ears = np.isin(part, (P_EARL, P_EARR))
    fu = np.where(ears, y, fu)
    fv = np.where(ears, -z, fv)
    return fu, fv


_HEAD_MASKS = {}


def head_masks(P, part):
    """Per texel: muzzle weight (0 on the skull .. 1 on the muzzle, smooth across the fillet) and
    cheek-fluff weight, both from the head's own fields."""
    if "m" not in _HEAD_MASKS:
        M = len(P)
        mzw, chk = np.zeros(M), np.zeros(M)
        h = part == P_HEAD
        if "head" in FUSED and h.any():
            G, comp = FUSED["head"]
            ph = P[h]
            mzw[h] = sstep(-0.025, 0.025, G.sample(comp["rest"], ph) - G.sample(comp["mz"], ph))
            chk[h] = sstep(0.02, -0.03, G.sample(comp["cheek"], ph))
        _HEAD_MASKS["m"] = (mzw, chk)
    return _HEAD_MASKS["m"]


def fur_colour(P, Ns, zone, part, tuft, flow, lock):
    M = len(P)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    ax = np.abs(x)
    up = np.clip(Ns[:, 2], 0, 1)
    n1 = 0.6 * vnoise(P, 2.0) + 0.4 * vnoise(P, 4.1, 1)
    c = mix(np.tile(ORANGE, (M, 1)), ORANGE_LT, 0.55 * sstep(0.52, 0.60, n1))
    c = mix(c, ORANGE_DK, 0.40 * sstep(0.42, 0.34, n1))
    fl = flow.copy()
    fl_len = np.linalg.norm(fl, axis=1)
    dflt = np.tile(np.array((0.0, 0.93, -0.37)), (M, 1))
    fl = np.where(fl_len[:, None] > 0.3, fl / np.maximum(fl_len, 1e-6)[:, None], dflt)
    along = np.sum(P * fl, axis=1)
    q = P - fl * along[:, None] * 0.85
    sn = vnoise(q, 6.5, 3)
    c = mix(c, ORANGE_LT, 0.18 * sstep(0.60, 0.70, sn))
    c = mix(c, ORANGE_DK, 0.16 * sstep(0.36, 0.27, sn))
    fu, fv = fur_param(P, part)
    st_lt, st_dk = stroke_masks(fu, fv)
    st_lt2, st_dk2 = stroke_masks(fu * 1.7 + 0.37, fv * 1.6 + 0.11, k=5.0)

    body, head, tail = part == P_BODY, part == P_HEAD, part == P_TAIL
    ears = np.isin(part, (P_EARL, P_EARR))
    legs = np.isin(part, (P_LEGFL, P_LEGFR, P_LEGBL, P_LEGBR))
    mzw, chk = head_masks(P, part)
    # rust along the back, the crown and the top of the tail
    saddle = body * sstep(0.2, 0.9, up) * sstep(1.05, 1.20, z)
    saddle += head * sstep(0.35, 0.95, up) * sstep(2.0, 2.17, z) * 0.6
    saddle += tail * sstep(0.0, 0.8, Ns[:, 2]) * 0.45 * (1.0 - sstep(0.62, 0.82, tuft))
    saddle += legs * sstep(0.50, 0.66, z) * sstep(0.1, 0.7, np.abs(Ns[:, 0])) * 0.35
    c = mix(c, RUST, 0.45 * np.clip(saddle, 0, 1))
    # cream: underside, chest bib, muzzle (orange bridge on top), lower cheeks, tail tip
    under = body * np.clip(sstep(-0.05, -0.60, Ns[:, 2]), 0, 1)
    bib = body * sstep(0.30, 0.18, np.sqrt((x / 0.9) ** 2 + ((z - 0.98) * 0.85) ** 2)) * sstep(-0.16, -0.34, y)
    bib = np.maximum(bib, body * sstep(-0.30, -0.45, y) * sstep(0.55, -0.15, Ns[:, 2]) * sstep(0.30, 0.14, ax))
    bridge = sstep(0.25, 0.80, Ns[:, 2]) * 0.93
    muzzle = head * np.clip(mzw * (1.0 - bridge), 0, 1)
    zb = 1.34 + 0.10 * sstep(0.10, 0.50, ax) + 0.025 * (n1 - 0.5)
    cheeks = head * sstep(zb + 0.03, zb - 0.03, z) * sstep(-0.62, -0.80, y)       # one cream sweep: cheek -> muzzle -> chin
    tiptail = tail * sstep(0.72, 0.86, tuft)
    cream = np.clip(under + bib + muzzle + cheeks + tiptail, 0, 1)
    c = mix(c, CREAM, cream)
    c = mix(c, CREAM_LT, 0.40 * np.clip(muzzle + tiptail, 0, 1) * sstep(0.45, 0.75, n1))
    # dark socks on the lower legs, ragged like painted fur
    sock = legs * sstep(0.30, 0.18, z + 0.05 * (n1 - 0.5))
    c = mix(c, mix(np.tile(SOCK_LT, (M, 1)), SOCK, sstep(0.24, 0.10, z)), 0.95 * sock)
    # ears: orange outside, cream inner fluff on the front, dark tips
    te = ((ax - EAR_E.x) * EAR_A.x + (y - EAR_E.y) * EAR_A.y + (z - EAR_E.z) * EAR_A.z) / EAR_LEN
    inner = np.zeros(M)
    if ears.any():
        G_, fld = EAR_FIELD["inner"]
        pe = P[ears].copy()
        pe[:, 0] = np.abs(pe[:, 0])
        inner[ears] = sstep(0.012, -0.012, G_.sample(fld, pe)) * sstep(0.1, -0.3, Ns[ears, 1])
    c = mix(c, RUST, 0.30 * ears * (1.0 - inner))
    c = mix(c, CREAM, 0.95 * inner * sstep(0.62, 0.50, te))
    c = mix(c, CREAM_LT, 0.45 * inner * sstep(0.45, 0.05, te))
    c = mix(c, EAR_DARK, 0.96 * ears * sstep(0.56, 0.74, te))
    plain = (~ears) * (1.0 - legs * sstep(0.20, 0.10, z))
    lt_col = mix(np.tile(ORANGE_LT, (M, 1)), CREAM_LT, cream)
    dk_col = mix(np.tile(ORANGE_DK, (M, 1)), CREAM * np.array((0.93, 0.88, 0.80)), cream)
    c = mix(c, lt_col, 0.34 * np.clip(st_lt + 0.6 * st_lt2, 0, 1) * plain * POLE_FADE)
    c = mix(c, dk_col, 0.30 * np.clip(st_dk + 0.6 * st_dk2, 0, 1) * plain * POLE_FADE)
    return c, cream


def paint(P, Ns, Nf, zone, part, tuft, flow, lock):
    M = len(P)
    col = np.tile(ORANGE, (M, 1))
    furry = np.isin(zone, (Z_FUR, Z_CLUMP, Z_EAR))
    fc, cream = fur_colour(P, Ns, zone, part, tuft, flow, lock)
    col[furry] = fc[furry]

    def solid(zid, pal):
        base, light_, dark = pal
        sh = 0.5 + 0.5 * Ns[:, 2]
        cc = mix(np.tile(dark, (M, 1)), base, sstep(0.05, 0.55, sh))
        cc = mix(cc, light_, 0.7 * sstep(0.65, 1.0, sh))
        sel = zone == zid
        col[sel] = cc[sel]

    col[zone == Z_NOSE] = NOSE
    solid(Z_SCARF, SCARF)
    solid(Z_KNOT, (SCARF[0] * 0.95, SCARF[1], SCARF[2]))
    solid(Z_CORD, CORD)
    cr = zone == Z_CHARM
    fac = 0.5 + 0.35 * Nf[:, 2] + 0.25 * Nf[:, 0] - 0.2 * Nf[:, 1]
    cc = mix(np.tile(BONE[2], (M, 1)), BONE[0], sstep(0.2, 0.6, fac))
    cc = mix(cc, BONE[1], sstep(0.66, 0.98, fac))
    col[cr] = cc[cr]
    return col, furry


def paint_patterns(col, P, Ns, zone, part, tuft):
    """Two thin cream bands across the scarf's tie ends."""
    sc = (part == P_SCARF) & (zone == Z_SCARF)
    for t0 in (0.74,):
        st = sc & (np.abs(tuft - t0) < 0.035)
        col[st] = mix(col[st], CREAM_LT, 0.9)
    rib_zone = (zone == Z_SCARF) | (zone == Z_KNOT)
    ang = np.arctan2(P[:, 0], -(P[:, 1] + 0.50))
    rib = np.where(part == P_SCARF, 0.5 + 0.5 * np.sin(P[:, 2] * 70.0), 0.5 + 0.5 * np.sin(ang * 30.0))
    k_ = rib_zone & (rib > 0.55)
    col[k_] = mix(col[k_], col[k_] * 0.74, (0.8 * sstep(0.55, 0.9, rib))[k_])
    return col


def paint_face(col, P, Ns, zone, part):
    """Eyes, brows, nose-to-mouth smile and whisker dots, painted in 3D around the recorded frames."""
    head = part == P_HEAD
    after = []
    for side in (1, -1):
        e = FACE[f"eye{side}"]
        d = P - np.array(e["c"])
        u, v, n = np.array(e["u"]), np.array(e["v"]), np.array(e["n"])
        du, dv, dn = d @ u, d @ v, d @ n
        ru, rv = e["r"]
        tilt = -e["tilt"] * side
        eu = (du * math.cos(tilt) + dv * math.sin(tilt)) / ru
        ev = (-du * math.sin(tilt) + dv * math.cos(tilt)) / rv
        front = head & (np.abs(dn) < 0.10) & (zone == Z_FUR)
        r = np.sqrt(eu * eu + ev * ev)
        cut = ev - (-0.80 + 0.20 * eu * eu)
        sdf = np.maximum(np.maximum(r - 1.0, -cut * 0.9), (ev - 0.82) * 1.5)
        ring = front & (sdf > 0) & (sdf < 0.6)
        col[ring] = mix(col[ring], col[ring] * np.array((0.93, 0.86, 0.80)), (0.16 * sstep(0.6, 0.0, sdf))[ring])
        line_w = 0.075 + 0.11 * sstep(0.0, 0.85, ev)
        lid = front & (sdf >= 0) & (sdf < line_w)
        col[lid] = mix(col[lid], EYE_LINE, sstep(line_w + 0.01, line_w - 0.03, sdf)[lid])
        inside = front & (sdf < 0)
        ce = np.tile(EYE_DARK, (len(P), 1))
        iris = sstep(0.28, 0.80, r) * sstep(0.25, -0.75, ev)
        ce = mix(ce, EYE_IRIS, 0.92 * iris)
        ce = mix(ce, EYE_IRIS_LT, 0.55 * sstep(-0.35, -0.8, ev) * sstep(0.3, 0.8, r))
        col[inside] = ce[inside]
        after.append((inside, eu, ev))
        # a confident little brow: a short dark stroke, outer end a touch higher
        tt = np.clip((-eu * side + 0.75) / 1.45, 0, 1)
        curve = 1.34 + 0.20 * np.sin(np.pi * np.clip(tt * 0.9 + 0.05, 0, 1)) + 0.12 * tt
        dist = np.abs(ev - curve)
        wdt = 0.14 * (0.55 + 0.6 * np.sin(np.pi * np.clip(tt, 0, 1)) ** 0.7)
        inseg = (-eu * side > -0.75) & (-eu * side < 0.70)
        bm = front & inseg & (dist < wdt + 0.06)
        col[bm] = mix(col[bm], BROW, (0.95 * sstep(wdt + 0.06, wdt - 0.03, dist))[bm])
    # philtrum and a sly little smile (the fox's left corner lifts a bit more), whisker dots
    nz_ = FACE["nose"]
    mx, my, mz = P[:, 0], P[:, 1], P[:, 2]
    mzw, _ = head_masks(P, part)
    fr = head & (mzw > 0.4) & (Ns[:, 1] < -0.10) & (my < -1.28) & (zone == Z_FUR)
    z0 = nz_["bottom"] - 0.060
    phil = fr & (np.abs(mx) < 0.010) & (mz < nz_["bottom"] + 0.004) & (mz > z0 - 0.002)
    col[phil] = mix(col[phil], EYE_LINE, 0.9)
    axm = np.abs(mx)
    zline = z0 - 0.050 * np.sin(np.pi * np.clip(axm / 0.20, 0, 1)) + 0.034 * sstep(0.11, 0.20, mx)
    sm = fr & (axm < 0.21) & (np.abs(mz - zline) < 0.010)
    col[sm] = mix(col[sm], EYE_LINE, 0.9)
    tick = fr & (mx > 0.19) & (mx < 0.22) & (np.abs(mz - (z0 + 0.036)) < 0.014)
    col[tick] = mix(col[tick], EYE_LINE, 0.8)
    for sx in (1, -1):
        for (dx, dz) in ((0.10, 0.036), (0.15, 0.054), (0.125, 0.09)):
            wd = np.sqrt((mx - sx * dx) ** 2 + (mz - (nz_["bottom"] + dz)) ** 2)
            wm = fr & (wd < 0.010) & (my < -1.33)
            col[wm] = mix(col[wm], rgb(120, 66, 40), 0.75)
    return after


def light(col, P, Ns, Nf, zone, ao_s, ao_l, curv, edge, furry, part_ids):
    """Icon-style baked lighting: per-facet key, AO, cool shadows, cool rim, warm edge highlights."""
    Lk = np.array((-0.50, -0.62, 0.62))
    Lk /= np.linalg.norm(Lk)
    Lr = np.array((0.70, 0.62, 0.35))
    Lr /= np.linalg.norm(Lr)
    kf = np.clip(Nf @ Lk, 0, 1)
    ks = np.clip(Ns @ Lk, 0, 1)
    fw = np.where(zone == Z_FUR, 0.22, np.where(furry, 0.30, 0.55))
    k = fw * kf + (1.0 - fw) * ks
    sky = 0.5 + 0.5 * Ns[:, 2]
    lightv = 0.58 + 0.44 * k + 0.12 * sky
    clz = zone == Z_EAR
    ao_w = np.where(part_ids == P_HEAD, 0.20, np.where(clz, 0.22, 0.32))
    aol_w = np.where(part_ids == P_HEAD, 0.08, np.where(clz, 0.08, 0.20))
    aof = (1.0 - ao_w + ao_w * sstep(0.12, 1.0, ao_s)) * (1.0 - aol_w * (1.0 - sstep(0.2, 1.0, ao_l)))
    hgt = 0.90 + 0.12 * sstep(0.0, 1.9, P[:, 2])
    shade = lightv * aof * hgt
    lit = col * shade[:, None]
    warmm = sstep(1.0, 0.8, shade) * sstep(0.55, 0.75, shade)
    lit = mix(lit, np.clip(lit * np.array((1.05, 0.96, 0.84)), 0, 1), 0.6 * warmm * furry)
    coolm = sstep(0.78, 0.50, shade)
    lit = mix(lit, lit * COOL, np.where(clz, 0.55, 0.85) * coolm)
    rim = sstep(0.3, 1.0, Ns @ Lr) * 0.10
    lit = lit + rim[:, None] * np.array((0.55, 0.70, 1.0))
    warm = np.array((1.0, 0.95, 0.84))
    hl = np.clip(col * 1.15 + 0.10, 0, 1) * warm
    hard = np.isin(zone, (Z_SCARF, Z_KNOT, Z_CHARM, Z_CORD, Z_NOSE))
    lit = mix(lit, hl, 0.45 * edge * hard * sstep(-0.3, 0.5, Ns @ Lk))
    return np.clip(lit, 0, 1)

def catchlights(col, after):
    for inside, eu, ev in after:
        g1 = np.sqrt(((eu + 0.30) / 0.36) ** 2 + ((ev - 0.38) / 0.32) ** 2)
        g2 = np.sqrt(((eu - 0.38) / 0.15) ** 2 + ((ev + 0.28) / 0.14) ** 2)
        m1 = inside & (g1 < 1.0)
        m2 = inside & (g2 < 1.0)
        col[m1] = mix(col[m1], np.array((1.0, 1.0, 1.0)), sstep(1.0, 0.8, g1)[m1])
        col[m2] = mix(col[m2], np.array((1.0, 0.98, 0.94)), sstep(1.0, 0.75, g2)[m2])
    return col

# =============================================================================================
# build
# =============================================================================================
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
mat = bpy.data.materials.new("Fox_Atlas")
mat.use_nodes = True

builders = [build_body(), build_head(), build_ear(1), build_ear(-1), build_front_leg(1), build_front_leg(-1),
            build_rear_leg(1), build_rear_leg(-1), build_tail(), build_scarf()]
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


select_only(objs)
bpy.ops.object.shade_smooth_by_angle(angle=math.radians(SMOOTH_ANGLE), keep_sharp_edges=True)
for o in objs:
    # the fused fur surfaces shade continuously everywhere (no hard edge at a fillet or crevice)
    me = o.data
    zf = np.array([a.value for a in me.attributes["zone"].data])
    if "sharp_edge" in me.attributes:
        sh = me.attributes["sharp_edge"]
        edge_faces = {}
        for pl in me.polygons:
            for ek in pl.edge_keys:
                edge_faces.setdefault(ek, []).append(pl.index)
        vals = np.zeros(len(me.edges), bool)
        sh.data.foreach_get("value", vals)
        for e in me.edges:
            fl_ = edge_faces.get(e.key, [])
            if fl_ and all(int(round(zf[i])) == Z_FUR for i in fl_):
                vals[e.index] = True
        sh.data.foreach_set("value", vals)
    wn = o.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
    wn.mode = "FACE_AREA"
    wn.keep_sharp = True
    wn.weight = 50
    select_only([o])
    bpy.ops.object.modifier_apply(modifier=wn.name)
    # per-face (quad) normal for the facet light: cleaner than Cycles' per-triangle True Normal
    fa = o.data.attributes.new("fnrm", "FLOAT_VECTOR", "FACE")
    fa.data.foreach_set("vector", np.array([pl.normal for pl in o.data.polygons], np.float32).ravel())

# ---- UVs: smart project, then a denser planar island for the visible face ----------------------
select_only(objs)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.006, area_weight=0.0,
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
        a = 0.0
        for i in range(1, len(uvs) - 1):
            a += abs((uvs[i] - uvs[0]).cross(uvs[i + 1] - uvs[0])) * 0.5
        ratios.append(math.sqrt(a / poly.area))
base_ratio = float(np.median(ratios))
head_obj = parts["Fox_Head"]
hm = head_obj.data
uvl = hm.uv_layers.active.data
FACE_DENSITY = 2.1
FACE_AXIS = (0.0, -0.72)          # vertical axis the face island is wrapped around (x, y)
mw = head_obj.matrix_world
hbm = bmesh.new()
hbm.from_mesh(hm)
hbm.transform(mw)
htree = BVHTree.FromBMesh(hbm)
zattr = hm.attributes["zone"].data
n_face = 0


def cyl_uv(co, off):
    ang = math.atan2(co.x - FACE_AXIS[0], -(co.y - FACE_AXIS[1]))
    return (ang * 0.55 * base_ratio * FACE_DENSITY + off, co.z * base_ratio * FACE_DENSITY)


for poly in hm.polygons:
    c = mw @ poly.center
    nrm = poly.normal
    zid = int(round(zattr[poly.index].value))
    radial = V(c.x - FACE_AXIS[0], c.y - FACE_AXIS[1], 0.0)
    if radial.length < 1e-6:
        continue
    radial.normalize()
    ang = math.atan2(c.x - FACE_AXIS[0], -(c.y - FACE_AXIS[1]))
    if not (nrm.dot(radial) > 0.35 and nrm.y < -0.1 and abs(ang) < 1.25 and c.z > 1.25
            and zid in (Z_FUR, Z_NOSE)):
        continue
    hit = htree.ray_cast(c + nrm * 0.002, nrm, 1.0)
    if hit[0] is not None:            # something of the head covers this face: keep it apart
        continue
    n_face += 1
    for li in poly.loop_indices:
        uvl[li].uv = cyl_uv(mw @ hm.vertices[hm.loops[li].vertex_index].co, 5.0 if zid == Z_FUR else 8.0)
hbm.free()
select_only(objs)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.pack_islands(rotate=True, margin=0.008)
bpy.ops.object.mode_set(mode="OBJECT")
for o in objs:
    o.data.uv_layers.active.name = "UVMap"
log("unwrapped; base texel ratio", round(base_ratio, 4), "face-island faces", n_face)

# ---- bake data maps -----------------------------------------------------------------------------
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
    bpy.ops.object.bake(type="EMIT", margin=int(5 * BAKE / 1024), margin_type="EXTEND", use_clear=True)
    arr = np.empty(BAKE * BAKE * 4, np.float32)
    img.pixels.foreach_get(arr)
    bpy.data.images.remove(img)
    log("baked", kind)
    return arr.reshape(-1, 4)


maps = {k: bake_pass(k, s) for k, s in (("pos", 1), ("nrm", 1), ("fnrm", 1), ("attr", 1), ("attr2", 1), ("flow", 1),
                                         ("occ", 12 if QUICK else 32), ("bev", 8 if QUICK else 16))}
cov = maps["pos"][:, 3] > 0.5
idx = np.nonzero(cov)[0]


def dec(a, s):
    return (a[idx, :3].astype(np.float64) - 0.5) / s


def unit(a):
    return a / np.maximum(np.linalg.norm(a, axis=1), 1e-6)[:, None]


P = dec(maps["pos"], 0.125)
Ns = unit(dec(maps["nrm"], 0.5))
Nf = unit(dec(maps["fnrm"], 0.5))
Nb = unit(dec(maps["bev"], 0.5))
FL = dec(maps["flow"], 0.5)
at = maps["attr"][idx, :3].astype(np.float64)
zone = np.rint(at[:, 0] * 32.0).astype(np.int64)
part = np.rint(at[:, 1] * 16.0).astype(np.int64)
tuft = np.clip(at[:, 2], 0, 1)
lock = np.clip(maps["attr2"][idx, 0].astype(np.float64), 0, 1)
oc = maps["occ"][idx, :3].astype(np.float64)
ao_s, ao_l, curv = np.clip(oc[:, 0], 0, 1), np.clip(oc[:, 1], 0, 1), oc[:, 2]
del maps
# edge mask: where the bevel-rounded normal leaves the shading normal on a convex edge
bevdot = np.sum(Nb * Ns, axis=1)
edge = sstep(0.995, 0.93, bevdot) * sstep(0.49, 0.53, curv)

if DEBUG_MAPS:
    for nm, arr_ in (("ao_s", ao_s), ("ao_l", ao_l), ("curv", np.clip((curv - 0.5) * 4 + 0.5, 0, 1)), ("edge", edge),
                     ("tuft", tuft), ("zone", zone / 16.0)):
        buf = np.zeros((BAKE * BAKE, 4), np.float32)
        buf[:, 3] = 1
        buf[idx, 0] = buf[idx, 1] = buf[idx, 2] = arr_
        im = bpy.data.images.new(f"dbg_{nm}", BAKE, BAKE, alpha=False)
        im.pixels.foreach_set(buf.ravel())
        im.filepath_raw = str(OUT / f"debug-{nm}.png")
        im.file_format = "PNG"
        im.save()
        bpy.data.images.remove(im)

colour, furry = paint(P, Ns, Nf, zone, part, tuft, FL, lock)
occl_rows = []
for pid in range(1, 11):
    for zid in np.unique(zone[part == pid]):
        m_ = (part == pid) & (zone == zid)
        if m_.sum() > 200:
            occl_rows.append((round(float(np.median(ao_s[m_])), 3), pid, int(zid), int(m_.sum())))
occl_rows.sort()
log("lowest median AO (ao, part, zone, texels):", occl_rows[:4])
colour = paint_patterns(colour, P, Ns, zone, part, tuft)
after = paint_face(colour, P, Ns, zone, part)
colour = light(colour, P, Ns, Nf, zone, ao_s, ao_l, curv, edge, furry, part)
colour = catchlights(colour, after)
# nose shine and nostrils, painted after lighting
nose = FACE["nose"]
nsel = zone == Z_NOSE
dn = P - np.array(nose["c"])
shine = np.exp(-(((dn[:, 0] + 0.030) / 0.038) ** 2 + ((P[:, 2] - (nose["top"] - 0.017)) / 0.018) ** 2)) * (Ns[:, 2] > 0.1)
colour[nsel] = mix(colour[nsel], np.array((0.93, 0.96, 1.0)), (0.9 * shine)[nsel])
colour[nsel] = mix(colour[nsel], colour[nsel] + 0.10, (sstep(0.5, 0.95, Ns[:, 2]) * 0.6)[nsel])
for sx_ in (1.0, -1.0):
    ex_ = (dn[:, 0] - sx_ * 0.041) / 0.024
    ez_ = (P[:, 2] - (nose["c"].z - 0.019) - 0.35 * (dn[:, 0] - sx_ * 0.041) * sx_) / 0.012
    dd_ = np.sqrt(ex_ ** 2 + ez_ ** 2)
    nm_ = nsel & (Ns[:, 1] < -0.15) & (dd_ < 1.0)
    colour[nm_] = mix(colour[nm_], colour[nm_] * 0.30, sstep(1.0, 0.65, dd_)[nm_])

full = np.zeros((BAKE * BAKE, 4), np.float32)
full[idx, :3] = colour
full[:, 3] = 1.0
full[~cov, :3] = GOLD
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
    for a in ("zone", "tuft_t", "flow_x", "flow_y", "flow_z", "fnrm", "lock"):
        if a in o.data.attributes:
            o.data.attributes.remove(o.data.attributes[a])

tris = {o.name: tri_count(o) for o in objs}
log("triangles", sum(tris.values()), tris)

# =============================================================================================
# reports (Studio axes = (-x, z, y) of Blender)
# =============================================================================================
bpy.context.view_layer.update()
JOINT_PARENT = {"Fox_Body": None, "Fox_Head": "Fox_Body", "Fox_EarL": "Fox_Head", "Fox_EarR": "Fox_Head",
                "Fox_LegFL": "Fox_Body", "Fox_LegFR": "Fox_Body", "Fox_LegBL": "Fox_Body", "Fox_LegBR": "Fox_Body",
                "Fox_Tail": "Fox_Body", "Fox_Scarf": "Fox_Body"}
MOTION = {
    "Fox_Body": "root part: bob up/down in Studio Y and a small roll about Studio Z while running; crouch before a pounce",
    "Fox_Head": "nod = pitch about Studio X, tilt = roll about Studio Z, look = yaw about Studio Y, all through the neck joint",
    "Fox_EarL": "flick / flop = rotate about Studio Z (front-back axis) through the ear root; child of the head",
    "Fox_EarR": "flick / flop = rotate about Studio Z (front-back axis) through the ear root; child of the head",
    "Fox_LegFL": "trot / pounce reach = swing about Studio X (side-to-side axis) through the shoulder",
    "Fox_LegFR": "trot / pounce reach = swing about Studio X (side-to-side axis) through the shoulder",
    "Fox_LegBL": "trot / pounce push = swing about Studio X (side-to-side axis) through the hip",
    "Fox_LegBR": "trot / pounce push = swing about Studio X (side-to-side axis) through the hip",
    "Fox_Tail": "wag / sweep = yaw about Studio Y through the tail root (lift = pitch about Studio X)",
    "Fox_Scarf": "flutter = swing about Studio X (and a little about Studio Z) through the knot; lags the body",
}
def studio(v):
    return [round(-v[0], 4) + 0.0, round(v[2], 4) + 0.0, round(v[1], 4) + 0.0]


def studio_size(v):
    return [round(v[0], 4), round(v[2], 4), round(v[1], 4)]


def world_bounds(o):
    ws = [o.matrix_world @ vv.co for vv in o.data.vertices]
    return (Vector([min(w[k] for w in ws) for k in range(3)]), Vector([max(w[k] for w in ws) for k in range(3)]))



report = {"asset": STEM, "pet": "Fox", "rarity": "Rare", "strong_suit": "damage (pounces on nearby enemies)",
          "blender_version": bpy.app.version_string,
          "authoring": "final Roblox stud size (1 Blender unit = 1 stud); import at 1:1, do not scale",
          "axes": "Blender Z-up, front -Y, the fox's left +X; paws on z = 0",
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
                     "head_top_studs": round(world_bounds(parts["Fox_Head"])[1].z, 4)}
body_pivot = parts["Fox_Body"].location.copy()
install = {
    "asset": STEM,
    "rarity": "Rare",
    "strong_suit": "damage (pounces on nearby enemies)",
    "axis": "studio = (-x, z, y) of blender; Blender front -Y = Studio front -Z",
    "units": "studs; the model is at final size, import 1:1 and do not scale",
    "sides": "L/R are the fox's own left/right; its left is Blender +X = Studio -X",
    "origin": "all positions are relative to the model origin = the ground point under the body pivot (Blender world origin)",
    "ground_point": studio((0.0, 0.0, 0.0)),
    "overall_size": studio_size(size),
    "overall_center": studio((lo_all + hi_all) / 2),
    "texture": f"textures/{TEX_PATH.name}",
    "texture_note": "one shared atlas; every MeshPart uses the same TextureID (Rare: one painted charm, no Neon, no glow)",
    "rest_rotation": "every part has identity rotation relative to the model at rest",
    "rig": "one Motor6D per part: Part0 = joint_parent, Part1 = the part, C0/C1 placed at the part's pivot",
    "parts": {},
}
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
    select_only(objs, parts["Fox_Body"])
    bpy.ops.export_scene.gltf(filepath=str(GLB_PATH), export_format="GLB", use_selection=True, export_apply=True)
    select_only(objs, parts["Fox_Body"])
    bpy.ops.export_scene.fbx(filepath=str(FBX_PATH), use_selection=True, object_types={"MESH"},
                             axis_forward="-Z", axis_up="Y", path_mode="COPY", embed_textures=True,
                             add_leaf_bones=False)
    log("exported", FBX_PATH.name, GLB_PATH.name)

# =============================================================================================
# armature (Blender only, for posing previews; the exports above are the plain rigid parts)
# =============================================================================================
arm_data = bpy.data.armatures.new("Fox_Rig")
arm = bpy.data.objects.new("Fox_Rig", arm_data)
scene.collection.objects.link(arm)
select_only([arm])
bpy.ops.object.mode_set(mode="EDIT")
ebs = {}
for name, o in parts.items():
    eb = arm_data.edit_bones.new(name.replace("Fox_", ""))
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
    o.parent_bone = name.replace("Fox_", "")
    bpy.context.view_layer.update()
    o.matrix_world = mwo
bpy.context.view_layer.update()
drift = max((parts[n].matrix_world.translation - meta[n]["pivot"]).length for n in parts)
log("armature built; max pivot drift after bone parenting", round(drift, 6))


def pose(rots):
    """rots: {bone: (x, y, z) degrees}. Bone axes: X = world X (pitch / leg swing), Y = world Z (yaw),
    Z = world -Y (roll)."""
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
# previews
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
    return ob


key = add_sun("Key", 2.6, (50, 0, -35), 8, (1.0, 0.96, 0.9))
rim = add_sun("Rim", 1.4, (60, 0, 150), 10, (0.8, 0.88, 1.0))
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


def simple_mat(name, c):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*c, 1)
    b.inputs["Roughness"].default_value = 0.8
    return m


def label(text, loc, size, rot=(90, 0, 0), color=(0.04, 0.04, 0.05)):
    cu = bpy.data.curves.new("Label", "FONT")
    cu.body, cu.size, cu.align_x, cu.extrude = text, size, "CENTER", 0.003
    cu.materials.append(simple_mat("LabelInk", color))
    ob = bpy.data.objects.new("Preview_Label", cu)
    ob.location, ob.rotation_euler = loc, tuple(math.radians(v) for v in rot)
    scene.collection.objects.link(ob)
    ob.hide_render = True
    return ob


def r15_figure(at):
    """Grey R15-proportioned block figure, 5 studs tall (legs 2, torso 2, head 1); preview only."""
    grey = simple_mat("R15Grey", (0.30, 0.31, 0.33))
    pieces = []
    at = Vector(at)
    for (c, sz) in (((-0.5, 0, 1.0), (0.98, 1.0, 2.0)), ((0.5, 0, 1.0), (0.98, 1.0, 2.0)),
                    ((0, 0, 3.0), (2.0, 1.0, 2.0)), ((-1.5, 0, 3.0), (0.98, 1.0, 2.0)),
                    ((1.5, 0, 3.0), (0.98, 1.0, 2.0)), ((0, 0, 4.5), (1.0, 1.0, 1.0))):
        bm_ = bmesh.new()
        bmesh.ops.create_cube(bm_, size=1.0)
        for vv in bm_.verts:
            vv.co = Vector((vv.co.x * sz[0], vv.co.y * sz[1], vv.co.z * sz[2]))
        bmesh.ops.bevel(bm_, geom=bm_.edges[:], offset=0.06, segments=2, affect="EDGES")
        for vv in bm_.verts:
            vv.co += Vector(c) + at
        me_ = bpy.data.meshes.new("R15Piece")
        bm_.to_mesh(me_)
        bm_.free()
        me_.materials.append(grey)
        ob = bpy.data.objects.new("Preview_R15", me_)
        scene.collection.objects.link(ob)
        ob.hide_render = True
        pieces.append(ob)
    return pieces


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


tgt = V(0, 0.05, 1.20)
ft = V(0, -1.08, 1.56)
TROT_A = {"LegFL": (28, 0, 0), "LegBR": (28, 0, 0), "LegFR": (-28, 0, 0), "LegBL": (-28, 0, 0)}
if not NO_PREVIEWS and QUICK:
    shoot(OUT / "threeq.png", around(tgt, (-0.75, -0.9, 0.42), 12.0), tgt)
    shoot(OUT / "side.png", around(tgt, (-1, 0, 0.12), 12.5), tgt)
    shoot(OUT / "front.png", around(tgt, (0, -1, 0.15), 12.0), tgt)
    shoot(OUT / "face-closeup.png", around(ft, (-0.35, -1, 0.12), 5.0), ft)
    if "--debug" in ARGS:
        crown = V(0, -0.7, 2.0)
        shoot(OUT / "dbg-crown.png", around(crown, (0.0, -0.45, 1.0), 3.0), crown, res=(1000, 1000))
        fm_ = simple_mat("dbg", (0.9, 0.5, 0.2))
        for o_ in objs:
            o_.data.materials.clear()
            o_.data.materials.append(fm_)
        shoot(OUT / "dbg-crown-flat.png", around(crown, (0.0, -0.45, 1.0), 3.0), crown, res=(1000, 1000))
    if "--pose" in ARGS:
        pose(dict(TROT_A, Head=(-15, 18, 20), Tail=(0, 30, 0), EarL=(0, 0, 25), EarR=(0, 0, 25), Scarf=(25, 0, 0)))
        shoot(OUT / "pose-quick.png", around(tgt, (-0.8, -0.7, 0.3), 12.0), tgt)
        pose({})
elif not NO_PREVIEWS:
    P_ = OUT
    views = [
        ("threeq.png", "Three-quarter", around(tgt, (-0.75, -0.9, 0.42), 12.0), tgt),
        ("front.png", "Front", around(tgt, (0, -1, 0.15), 12.0), tgt),
        ("side.png", "Side (fox's right)", around(tgt, (-1, 0, 0.12), 12.5), tgt),
        ("back.png", "Back", around(tgt, (0, 1, 0.3), 12.5), tgt),
    ]
    shots = [(shoot(P_ / fn, loc, t), lab) for fn, lab, loc, t in views]
    face = shoot(P_ / "face-closeup.png", around(ft, (-0.35, -1, 0.12), 5.0), ft, res=(1400, 1400))
    fig = r15_figure((3.1, 0.8, 0.0))
    view = Vector((-0.30, -1.0, 0.10)).normalized()
    yaw = math.degrees(math.atan2(view.x, -view.y))
    top_z = report["overall"]["height_studs"]
    labs = [label("R15 block figure, 5 studs", (3.1, 0.8, 5.3), 0.22, (90, 0, yaw)),
            label(f"Fox: {top_z:.2f} tall, {size.y:.2f} long", (-0.55, -0.3, top_z + 0.45), 0.17, (90, 0, yaw))]
    extras += fig + labs
    scale_png = shoot(P_ / "scale-vs-5stud-r15.png", Vector((1.45, 0.3, 2.75)) + view * 40, (1.45, 0.3, 2.75),
                      ortho=8.2, res=(1500, 1300), show=fig + labs)
    TROT_B = {k_: (-v_[0], 0, 0) for k_, v_ in TROT_A.items()}
    poses = [
        ("Trot A: legs +/-28 deg (right side)", TROT_A, around(tgt, (-1, 0.05, 0.1), 12.0), tgt),
        ("Trot B: legs -/+28 deg (left side)", TROT_B, around(tgt, (1, 0.05, 0.1), 12.0), tgt),
        ("Trot A from low front, tail wag 25", dict(TROT_A, Tail=(0, 25, 0)),
         around(tgt + V(0, 0, -0.3), (-0.55, -1.0, -0.02), 10.5), tgt + V(0, 0, -0.3)),
        ("Head tilt 22 + nod 18, ears flick, scarf 25", {"Head": (18, 0, 22), "EarL": (0, 0, 20), "EarR": (0, 0, 25),
                                                        "Scarf": (25, 0, 0)},
         around(ft + V(0, 0.3, -0.25), (-0.5, -1.0, 0.25), 6.5), ft + V(0, 0.3, -0.25)),
        ("Head up 22 + turn 28, tail wag 30", {"Head": (-22, 28, 0), "Tail": (0, 30, 0), "EarL": (0, 0, -20),
                                                "EarR": (0, 0, -20)}, around(tgt, (0.75, 0.75, 0.45), 12.0), tgt),
        ("Pounce reach: fronts -30, backs +30, tail lift 25",
         {"LegFL": (-30, 0, 0), "LegFR": (-30, 0, 0), "LegBL": (30, 0, 0), "LegBR": (30, 0, 0),
          "Scarf": (-30, 0, 0), "Head": (10, 0, 0), "Tail": (25, 0, 0)}, around(tgt, (-1, -0.35, 0.05), 12.0), tgt),
    ]
    pose_items = []
    for i, (lab, rots, loc, t) in enumerate(poses):
        pose(rots)
        pose_items.append((shoot(P_ / f"_pose-{i}.png", loc, t, res=(900, 900)), lab))
    pose({})
    make_sheet(pose_items, 3, 600, P_ / "pose-check.png", "Fox: pose check through the joint pivots",
               "Each part rotates about its own pivot (Blender armature, preview only). "
               "Look for gaps at the shoulders, hips, neck, ears, tail root and scarf knot.")
    for pth, _ in pose_items:
        pth.unlink()
    make_sheet([shots[0], shots[1], shots[2], shots[3], (face, "Face close-up"),
                (scale_png, "True scale vs 5-stud R15 figure"), (P_ / "pose-check.png", "Pose check (trot, head, tail)")],
               4, 440, P_ / "sheet.png",
               f"Fox pet (Rare, damage): {report['total_triangles']:,} tris, one 1024 atlas",
               "Blender 5.2 Eevee renders. Every furry part is one fused surface; the tail is one plume. Blender-verified, Studio untested.")
log("done")
