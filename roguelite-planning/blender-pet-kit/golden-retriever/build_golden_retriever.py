"""Golden Retriever pet (Common, strong suit: Loot) for the roguelite.

Builds the whole art asset from scratch in background Blender 5.2. Self-contained: no code from
sibling kits.

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 4 \
        --python build_golden_retriever.py
    ... -- --quick --out <dir>        iteration mode: 1024 bake, a few Eevee views, no exports
    ... -- --variant A|B              head/face variant (B is the kept one)
    ... -- --no-previews              exports + reports only
    ... -- --debug-maps               also write the baked masks (AO, curvature, edges) as PNGs

Writes (inside this folder): golden-retriever.blend, textures/golden-retriever.png (1024, one atlas
shared by every part), exports/fbx + exports/glb, polygon-report.json, studio-install-data.json and
previews/*.png (real Blender renders).

Coordinates: Blender Z-up, 1 unit = 1 stud (final size, import 1:1), paws on z = 0, the dog faces
-Y and its own left is +X. Studio = (-x, z, y) of Blender, so Studio front is -Z.

Look (../../art-references/ART_DIRECTION_USER_2026-09-17.txt): stylized low-poly, chunky readable
silhouette, soft faceting, painterly low-noise texture. The face (eyes, brows, mouth line, nose
shine) is PAINTED over shallow relief; modelled sockets read as sunglasses in this project.

Texture method: all parts are unwrapped into one atlas (the face gets a denser planar island),
Cycles bakes world position, smooth and per-face normals, zone/part/clump-gradient attributes, two
AO radii, pointiness and a bevel-edge mask into float maps, and numpy paints the final colour and
an icon-style lighting pass (per-facet key light, AO, cool shadows, rim, clump-edge highlights)
from those maps at 2x resolution, then downsamples to 1024.
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
STEM = "golden-retriever"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    if name in ARGS:
        i = ARGS.index(name)
        if i + 1 < len(ARGS):
            return ARGS[i + 1]
    return default


VARIANT = arg("--variant", "B")
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
    print(f"[retriever {time.time() - T0:6.1f}s]", *a, flush=True)


# zones (per face) tell the painter what each texel is
(Z_FUR, Z_CLUMP, Z_EAR, Z_MUZZLE, Z_NOSE, Z_TONGUE, Z_MOUTH, Z_PAW, Z_TOE, Z_PAD,
 Z_BANDANA, Z_KNOT, Z_LEATHER, Z_STRAP, Z_METAL, Z_CRYSTAL) = range(1, 17)
# part ids (object pass index)
P_BODY, P_HEAD, P_EARL, P_EARR, P_LEGFL, P_LEGFR, P_LEGBL, P_LEGBR, P_TAIL, P_TAG = range(1, 11)

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
NECK_PIVOT = V(0.0, -0.54, 1.36)
HEAD_VARIANTS = {
    # A: round puppy head, short muzzle, soft cream brow spots
    "A": dict(cran=[(-0.32, 1.80, 0.12, 0.11), (-0.38, 1.80, 0.32, 0.29), (-0.48, 1.79, 0.43, 0.38),
                    (-0.62, 1.78, 0.49, 0.43), (-0.78, 1.77, 0.51, 0.44), (-0.93, 1.76, 0.48, 0.42),
                    (-1.03, 1.74, 0.42, 0.37), (-1.09, 1.72, 0.32, 0.29), (-1.12, 1.70, 0.17, 0.16)],
              cran_tip=(0, -1.135, 1.69),
              muzzle=[(-0.88, 1.555, 0.25, 0.17), (-1.04, 1.555, 0.285, 0.18), (-1.18, 1.55, 0.28, 0.175),
                      (-1.28, 1.555, 0.25, 0.165), (-1.34, 1.56, 0.19, 0.13), (-1.37, 1.565, 0.10, 0.075)],
              muzzle_tip=(0, -1.38, 1.57), eye_x=0.25, eye_z=1.85, eye_r=(0.112, 0.130), eye_tilt=0.0,
              brow="spot"),
    # B: a touch longer muzzle, taller skull, arched brows
    "B": dict(cran=[(-0.32, 1.82, 0.12, 0.11), (-0.38, 1.82, 0.31, 0.29), (-0.48, 1.81, 0.42, 0.39),
                    (-0.62, 1.80, 0.475, 0.44), (-0.78, 1.79, 0.495, 0.45), (-0.93, 1.78, 0.465, 0.43),
                    (-1.03, 1.76, 0.40, 0.38), (-1.09, 1.74, 0.31, 0.30), (-1.12, 1.72, 0.165, 0.16)],
              cran_tip=(0, -1.135, 1.71),
              muzzle=[(-0.88, 1.555, 0.245, 0.17), (-1.04, 1.555, 0.28, 0.18), (-1.20, 1.55, 0.275, 0.175),
                      (-1.32, 1.555, 0.245, 0.165), (-1.39, 1.56, 0.185, 0.13), (-1.42, 1.565, 0.095, 0.075)],
              muzzle_tip=(0, -1.43, 1.57), eye_x=0.25, eye_z=1.87, eye_r=(0.106, 0.124), eye_tilt=0.08,
              brow="arch"),
}
HV = HEAD_VARIANTS[VARIANT]
FACE = {}          # filled by build_head: eyes, nose, mouth frames for the painter

BODY_SECS = [  # (y, zc, rx, rz, n)
    (0.68, 0.98, 0.10, 0.09, 2.2), (0.62, 0.99, 0.26, 0.23, 2.3), (0.50, 0.99, 0.37, 0.31, 2.4),
    (0.34, 0.98, 0.40, 0.33, 2.5), (0.14, 0.96, 0.37, 0.33, 2.5), (-0.08, 0.95, 0.38, 0.37, 2.5),
    (-0.30, 0.95, 0.40, 0.41, 2.5), (-0.48, 0.97, 0.38, 0.40, 2.4), (-0.60, 1.00, 0.31, 0.34, 2.3),
    (-0.68, 1.04, 0.19, 0.22, 2.2)]
STRAP_Y = 0.00
SATCHEL = dict(c=V(-0.47, 0.00, 0.92), size=(0.14, 0.36, 0.29))


def body_section(y):
    """Interpolated (zc, rx, rz, n) of the body loft at y (for straps and anchors)."""
    s = sorted(BODY_SECS, key=lambda r: r[0])
    for a, b in zip(s, s[1:]):
        if a[0] <= y <= b[0]:
            t = (y - a[0]) / (b[0] - a[0])
            return tuple(a[k] + (b[k] - a[k]) * t for k in range(1, 5))
    return s[0][1:]


# =============================================================================================
# the dog
# =============================================================================================
def build_body():
    p = Part("Retriever_Body", P_BODY, (0.0, 0.0, 0.96), "body centre (root part; bob/roll pivot)")
    secs = [dict(c=(0, y, zc), rx=rx, rz=rz, n=n) for y, zc, rx, rz, n in BODY_SECS]
    neck = [dict(c=(0, -0.36, 0.98), rx=0.30, rz=0.30), dict(c=(0, -0.47, 1.18), rx=0.34, rz=0.33),
            dict(c=(0, -0.56, 1.38), rx=0.32, rz=0.31), dict(c=(0, -0.64, 1.56), rx=0.27, rz=0.26)]
    trunk = shape(lambda t: t.loft(secs, Z_FUR, sides=18, cap0=(0, 0.71, 0.98), cap1=(0, -0.71, 1.06)))
    nk = shape(lambda t: t.loft(neck, Z_FUR, sides=14, cap0="flat", cap1="flat", up=(0, -1, 0)))
    G = Grid((-0.56, -1.02, 0.38), (0.56, 0.86, 1.76), 0.016, sym_x=True)
    d_trunk, d_neck = mesh_sdf(G, trunk), mesh_sdf(G, nk)
    base = smin(d_trunk, d_neck, 0.10)

    X, Y, Z = G.P[..., 0], G.P[..., 1], G.P[..., 2]
    # the coat itself grows outward where the fur is long, ending in a soft hem with a few broad waves:
    # chest ruff: across the front of the chest under the collar, longest in the middle
    ph = np.arctan2(X, -(Y + 0.30))
    edge = 0.73 + 0.08 * (ph / 0.95) ** 2 - 0.018 * np.cos(np.pi * ph / 0.32)
    ruff = (0.05 * (0.5 + 0.5 * sstep(0.98, 0.80, Z)) * sstep(1.10, 0.80, np.abs(ph))
            * sstep(edge - 0.012, edge + 0.04, Z) * sstep(1.10, 0.96, Z) * sstep(-0.40, -0.55, Y))
    # belly: a soft fringe along the underside between the legs, gently waved along its length
    belly = (0.034 * (1.0 + 0.4 * np.cos(2 * np.pi * Y / 0.20)) * sstep(0.74, 0.62, Z)
             * sstep(-0.36, -0.24, Y) * sstep(0.28, 0.16, Y))
    grow = np.maximum(ruff, belly)
    vs, fs = extract(G, blur(base - grow), 2300, name="body_fur")
    tuft = sstep(0.0, 0.045, G.sample(grow, vs))
    flow = blend_flow(vs, [(G.sample(d_trunk, vs), (0, -1, 0)), (G.sample(d_neck, vs), (0, -0.39, 0.92))])
    flow = flow + tuft[:, None] * np.array((0.0, 0.3, -1.0))
    flow /= np.maximum(np.linalg.norm(flow, axis=1), 1e-6)[:, None]
    p.add_mesh(vs, fs, Z_FUR, tuft, flow)
    tree_fur = p.bvh()
    build_bandana(p, tree_fur)
    build_satchel(p, tree_fur)
    return p


def neck_frame():
    a = V(0, -0.25, 0.53).normalized()
    w = a.cross(V(1, 0, 0)).normalized()      # points up-back
    return V(0, -0.52, 1.28), a, w


def band_point(theta, r, c, w):
    """Point on the collar loop; theta = 0 at the front of the neck, positive toward the dog's left."""
    return c + (V(1, 0, 0) * math.sin(theta) - w * math.cos(theta)) * r


def build_bandana(p, tree):
    c, a, w = neck_frame()
    R = 0.375
    secs = []
    n_seg = 24
    for i in range(n_seg):
        th = 2 * math.pi * i / n_seg
        pt = band_point(th, R + 0.012 * math.sin(3 * th + 0.5), c, w)
        secs.append(dict(c=pt, rx=0.032, rz=0.075, n=3.0))
    p.loft(secs, Z_BANDANA, sides=8, up=tuple(a), closed_path=True, tvals=[0.5] * n_seg)
    p.close(Z_BANDANA)
    # the triangle: a draped cloth sheet from the band's front down over the ruff
    rows, cols = 9, 11
    top = [band_point(-1.45 + 2.9 * j / (cols - 1), R - 0.005, c, w) for j in range(cols)]
    tip = V(0.0, -1.02, 0.72)
    grid = []
    for i in range(rows):
        v = i / (rows - 1)
        row = []
        for j in range(cols):
            u = -1.0 + 2.0 * j / (cols - 1)
            width = 1.0 - v * 0.95
            uu = (u * width + 1.0) * 0.5 * (cols - 1)
            j0 = min(int(uu), cols - 2)
            ft = uu - j0
            a_pt = top[j0].lerp(top[j0 + 1], ft)
            pt = a_pt.lerp(tip, v ** 0.85)
            inner_pt = V(0, -0.35, pt.z + 0.1)
            d_out = (pt - inner_pt).normalized()
            org = pt + d_out * 0.8
            hit = tree.ray_cast(org, -d_out, 1.6)
            if hit[0] is not None:
                nrm = hit[1]
                # rest on the outermost fur nearby, so no lock pokes through between grid points
                side_ax = d_out.cross(V(0, 0, 1)).normalized()
                up_ax = side_ax.cross(d_out).normalized()
                best = hit[3]
                for du, dv in ((0.05, 0), (-0.05, 0), (0, 0.05), (0, -0.05), (0.035, 0.035), (-0.035, -0.035)):
                    h2 = tree.ray_cast(org + side_ax * du + up_ax * dv, -d_out, 1.6)
                    if h2[0] is not None:
                        best = min(best, h2[3])
                loc = org - d_out * best
                if nrm.dot(d_out) < 0:
                    nrm = -nrm
            else:
                loc, nrm = snap(tree, pt)
            fold = 0.018 * math.sin(u * math.pi * 1.5 + 0.4) * (0.2 + v)
            puff = 0.03 + 0.03 * math.sin(math.pi * min(v * 1.1, 1.0))
            edge = min(1.0 - abs(u), 1.0 - v) if v < 0.999 else 0.0
            row.append((loc + nrm * (puff + fold), nrm, edge))
        grid.append(row)
    sheet(p, grid, 0.03, Z_BANDANA)
    # knot on the dog's left (+X), two short flared ends
    kc = band_point(math.pi / 2 + 0.25, R + 0.05, c, w)
    p.ellipsoid(kc, (0.085, 0.07, 0.075), (1, 0.1, 0.1), Z_KNOT, useg=10, vseg=6)
    for ang, L in ((-0.35, 0.22), (0.55, 0.19)):
        d = V(0.25, 0.9 * math.cos(ang), -math.sin(ang) - 0.6)
        p.clump(kc + V(0.03, 0.02, -0.02), V(1, 0, 0.1), d, L, 0.13, 0.04, zone=Z_KNOT, bend=0.15,
                sink=0.4, twist=-0.3)


def sheet(p, grid, th, zone):
    """Thick cloth sheet from a grid of (point, normal, edge) with a rounded border."""
    rows, cols = len(grid), len(grid[0])
    top = [[p.v(g[0] + g[1] * th * 0.5, g[2]) for g in row] for row in grid]
    bot = [[p.v(g[0] - g[1] * th * 0.5, g[2]) for g in row] for row in grid]
    for i in range(rows - 1):
        for j in range(cols - 1):
            p.f([top[i][j], top[i][j + 1], top[i + 1][j + 1], top[i + 1][j]])
            p.f([bot[i][j], bot[i + 1][j], bot[i + 1][j + 1], bot[i][j + 1]])
    border = ([(0, j) for j in range(cols)] + [(i, cols - 1) for i in range(1, rows)] +
              [(rows - 1, j) for j in range(cols - 2, -1, -1)] + [(i, 0) for i in range(rows - 2, 0, -1)])
    mids = []
    nb = len(border)
    cen = grid[rows // 3][cols // 2][0]
    for k, (i, j) in enumerate(border):
        pi_, pj = border[(k - 1) % nb], border[(k + 1) % nb]
        g = grid[i][j]
        tang = grid[pj[0]][pj[1]][0] - grid[pi_[0]][pi_[1]][0]
        out = tang.cross(g[1])
        if out.length < 1e-9:
            out = g[0] - cen
        out.normalize()
        if out.dot(g[0] - cen) < 0:
            out = -out
        mids.append(p.v(g[0] + out * th * 0.55, 0.0))
    for k in range(nb):
        (i0, j0), (i1, j1) = border[k], border[(k + 1) % nb]
        m0, m1 = mids[k], mids[(k + 1) % nb]
        p.f([top[i0][j0], top[i1][j1], m1, m0])
        p.f([m0, m1, bot[i1][j1], bot[i0][j0]])
    p.close(zone)


def build_satchel(p, tree):
    c, (sx, sy, sz) = SATCHEL["c"], SATCHEL["size"]
    s = -1.0 if c.x < 0 else 1.0                                 # which flank it hangs on
    tilt = Matrix.Rotation(math.radians(8 * s), 3, "Y")         # top leans in against the flank
    p.box(c, (sx, sy, sz), Z_LEATHER, bevel=0.035, segments=3, rot=tilt)
    # flap over the top 62% of the outer face
    flap_c = c + tilt @ V(s * (sx / 2 + 0.01), 0, sz * 0.19)
    p.box(flap_c, (0.03, sy + 0.025, sz * 0.66), Z_LEATHER, bevel=0.013, segments=2, rot=tilt)
    # pocket strap + gold buckle on the flap
    bc = c + tilt @ V(s * (sx / 2 + 0.034), 0, -0.035)
    p.box(bc + tilt @ V(0, 0, 0.07), (0.02, 0.075, 0.17), Z_STRAP, bevel=0.007, segments=2, rot=tilt)
    p.box(bc, (0.032, 0.11, 0.085), Z_METAL, bevel=0.013, segments=2, rot=tilt)
    # loot crystals peeking out from under the flap at the front
    cc = c + tilt @ V(s * 0.01, -sy * 0.26, sz * 0.5 + 0.03)
    crystal(p, cc, V(-0.2 * s, -0.55, 1.0), 0.23, 0.058)
    crystal(p, cc + V(0.0, 0.08, -0.015), V(0.15 * s, 0.35, 1.0), 0.15, 0.04)
    # the girth strap that carries it: a flat band hugging the barrel (the bag hangs over it)
    zc, rx, rz, n = body_section(STRAP_Y)
    secs = []
    n_seg = 30
    for i in range(n_seg):
        a = 2 * math.pi * i / n_seg
        ex, ez = se(a, n)
        rad = V(ex * rx, 0.0, ez * rz)
        dn = rad.normalized()
        hit = tree.ray_cast(V(0, STRAP_Y, zc) + dn * 1.2, -dn, 2.0)     # hug the fused coat
        on = hit[0] if hit[0] is not None else V(0, STRAP_Y, zc) + rad
        secs.append(dict(c=on + dn * 0.016, rx=0.016, rz=0.05, n=3.0))
    p.loft(secs, Z_STRAP, sides=6, up=(0, 1, 0), closed_path=True)
    p.close(Z_STRAP)
    # two short hanger loops from the strap to the bag's top edge
    for dy in (-0.11, 0.11):
        hc = c + tilt @ V(s * 0.0, dy, sz / 2 + 0.03)
        p.box(hc, (0.10, 0.045, 0.07), Z_STRAP, bevel=0.012, segments=2, rot=tilt)
    # strap buckle on the top of the back
    top = V(0.0, STRAP_Y, zc + rz + 0.03)
    p.box(top, (0.13, 0.12, 0.03), Z_METAL, bevel=0.012, segments=2)
    p.box(top + V(0, 0, 0.012), (0.075, 0.13, 0.02), Z_STRAP, bevel=0.006, segments=2)


def crystal(p, c, axis, h, r, sides=6):
    """Faceted bipyramid loot crystal (matches the game's crystal shard)."""
    ax = Vector(axis).normalized()
    secs = [dict(c=c - ax * h * 0.16, rx=r, rz=r), dict(c=c + ax * h * 0.16, rx=r, rz=r)]
    p.loft(secs, Z_CRYSTAL, sides=sides, cap0=tuple(c - ax * h * 0.42), cap1=tuple(c + ax * h * 0.58),
           up=tuple(ax.orthogonal()))
    p.close(Z_CRYSTAL)


MOUTH_CUT = dict(cy=-0.98, cz=1.495, fy=-1.46, drop=0.09, open=0.046, smile=0.45)


def mouth_cavity(P):
    """The open, smiling mouth as a signed field (negative inside the cut): a lens between the upper
    lip and the lower jaw that closes at the mouth corners and lifts toward them."""
    m = MOUTH_CUT
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    u = np.clip((m["cy"] - y) / (m["cy"] - m["fy"]), 0.0, 1.0)
    zc = m["cz"] - m["drop"] * u ** 1.2 + m["smile"] * x * x
    hw = m["open"] * np.sin(0.5 * np.pi * np.clip(u / 0.75, 0.0, 1.0)) ** 0.8
    return np.maximum(np.abs(z - zc) - hw, y - m["cy"])


def lip_z(y, upper):
    """z of the upper-lip edge (upper) or the lower-lip / jaw-top edge along the centre line."""
    m = MOUTH_CUT
    u = min(max((m["cy"] - y) / (m["cy"] - m["fy"]), 0.0), 1.0)
    hw = m["open"] * math.sin(0.5 * math.pi * min(u / 0.75, 1.0)) ** 0.8
    return m["cz"] - m["drop"] * u ** 1.2 + (hw if upper else -hw)


def build_head():
    p = Part("Retriever_Head", P_HEAD, NECK_PIVOT, "neck joint (nod / tilt / turn pivot)")

    def cheek_mod(k):
        def mod(a, x, z):
            # cheeks swell on the lower sides, the crown is a touch flatter
            m = 1.0 + 0.08 * k * (gauss(angdiff(a, -0.5), 0.5) + gauss(angdiff(a, math.pi + 0.5), 0.5))
            m *= 1.0 - 0.035 * gauss(angdiff(a, math.pi / 2), 0.6)
            return x * m, z * m
        return mod

    cran = HV["cran"]
    secs = []
    for i, (y, zc, rx, rz) in enumerate(cran):
        k = math.sin(math.pi * i / (len(cran) - 1))
        secs.append(dict(c=(0, y, zc), rx=rx, rz=rz, n=2.25, mod=cheek_mod(k)))
    cr = shape(lambda t: t.loft(secs, Z_FUR, sides=22, cap0=(0, cran[0][0] + 0.05, cran[0][1]),
                                cap1=HV["cran_tip"], up=(0, 0, 1)))
    mz = HV["muzzle"]
    tip_y = HV["muzzle_tip"][1]
    G = Grid((-0.66, -1.60, 1.10), (0.66, -0.16, 2.34), 0.012, sym_x=True)
    P = G.P
    d_cran = mesh_sdf(G, cr)
    # one muzzle mass that grows out of the face: a rounded, blunt upper muzzle and a smaller, rounder
    # lower jaw set back under it; the mouth is carved out of it below
    d_up = sd_ell(P, (0, -1.13, 1.555), AXES, (0.262, 0.14, 0.172), elong=0.17)
    d_jaw = sd_ell(P, (0, -1.07, 1.365), AXES, (0.175, 0.10, 0.078), elong=0.10)
    d_mz = smin(d_up, d_jaw, 0.06)
    # soft cheeks carrying the muzzle sides back into the face, and a fluffy bulge at each jaw corner
    cheeks, fluff, fl_axes = None, None, []
    for sx in (1, -1):
        c1 = sd_ell(P, (sx * 0.29, -0.95, 1.52), AXES, (0.14, 0.15, 0.13))
        cheeks = c1 if cheeks is None else np.minimum(cheeks, c1)
        hit = cr[2].ray_cast(V(sx * 1.2, -0.80, 1.38), (V(0, -0.80, 1.70) - V(sx * 1.2, -0.80, 1.38)).normalized(), 3.0)
        S, N = hit[0], hit[1]
        R = lock_axes(N, V(0, 0.35, -1))
        fl_axes.append(R[1])
        c2 = sd_ell(P, S - N * 0.03, R, (0.10, 0.13, 0.075))
        fluff = c2 if fluff is None else np.minimum(fluff, c2)
    d_rest = smin(smin(d_cran, cheeks, 0.08), fluff, 0.06)
    head = smin(d_rest, d_mz, 0.11)
    FUSED["head"] = (G, dict(mz=d_mz, rest=d_rest))
    vs, fs = extract(G, blur(ssub(head, mouth_cavity(P), 0.02)), 1750, name="head_fur",
                     pin=lambda q: mouth_cavity(q) < 0.035)       # keep the thin lips where they are
    base = smin(smin(d_cran, cheeks, 0.08), d_mz, 0.11)
    tuft = sstep(0.004, 0.05, G.sample(base, vs))
    flow = blend_flow(vs, [(G.sample(d_cran, vs), (0, -1, 0)), (G.sample(d_mz, vs), (0, -1, 0)),
                           (G.sample(fluff, vs), tuple(fl_axes[0] * np.array((0, 1, 1))))])
    p.add_mesh(vs, fs, Z_FUR, tuft, flow)
    # tongue: a soft, broad, rounded lobe lying on the jaw and hanging out over the chin
    def tongue_mod(a, x, z):
        if z > 0:
            z *= 1.0 - 0.5 * math.exp(-(x / 0.022) ** 2)          # the groove down its middle
        return x, z

    zl = lip_z(-1.295, False)
    tg = [dict(c=(0.0, -1.04, lip_z(-1.04, False) + 0.010), rx=0.072, rz=0.030),
          dict(c=(0.004, -1.14, lip_z(-1.14, False) + 0.016), rx=0.086, rz=0.036),
          dict(c=(0.01, -1.23, lip_z(-1.23, False) + 0.012), rx=0.09, rz=0.038),
          dict(c=(0.016, -1.30, zl - 0.004), rx=0.088, rz=0.037),
          dict(c=(0.02, -1.33, zl - 0.055), rx=0.082, rz=0.034),
          dict(c=(0.022, -1.335, zl - 0.105), rx=0.072, rz=0.031),
          dict(c=(0.023, -1.325, zl - 0.138), rx=0.05, rz=0.024)]
    for d_ in tg:
        d_["mod"] = tongue_mod
        d_["n"] = 2.0
    p.loft(tg, Z_TONGUE, sides=14, cap0="flat", cap1=(0.024, -1.32, zl - 0.152), up=(0, -1, 0))
    p.close(Z_TONGUE)
    # nose: rounded inverted triangle at the top of the muzzle tip
    nz = mz[-2][1] + mz[-2][3] * 0.80

    def nose_mod(a, x, z):
        if z < 0:
            x *= 1.0 + 0.55 * z / 0.075
        return x, z

    ns = [dict(c=(0, tip_y + 0.10, nz - 0.01), rx=0.095, rz=0.065, n=2.4, mod=nose_mod),
          dict(c=(0, tip_y + 0.02, nz), rx=0.11, rz=0.075, n=2.4, mod=nose_mod),
          dict(c=(0, tip_y - 0.03, nz + 0.005), rx=0.09, rz=0.061, n=2.3, mod=nose_mod)]
    p.loft(ns, Z_NOSE, sides=16, cap0="flat", cap1=(0, tip_y - 0.05, nz + 0.008))
    p.close(Z_NOSE)
    FACE["nose"] = dict(c=V(0, tip_y - 0.01, nz), top=nz + 0.075)
    FACE["mouth"] = dict(tip_y=tip_y, lip_z=lip_z(-1.42, True), nose_bottom=nz - 0.07)

    tree = p.bvh()
    for side in (1, -1):
        ex = HV["eye_x"] * side
        hit = tree.ray_cast(V(ex * 2.2, -1.9, HV["eye_z"]), (V(ex, -0.70, HV["eye_z"]) - V(ex * 2.2, -1.9, HV["eye_z"])).normalized())
        loc, nrm = hit[0], hit[1]
        u = V(0, 0, 1).cross(nrm).normalized() * -1.0         # points to the dog's right (-X)
        vv = nrm.cross(u).normalized()
        if vv.z < 0:
            vv = -vv
        FACE[f"eye{side}"] = dict(c=loc, n=nrm, u=u, v=vv, r=HV["eye_r"], side=side, tilt=HV["eye_tilt"])
    return p


def build_ear(side):
    s = side
    pivot = V(s * 0.36, -0.74, 2.05)
    p = Part(f"Retriever_Ear{'L' if s > 0 else 'R'}", P_EARL if s > 0 else P_EARR, pivot,
             "ear root on the skull (flop pivot)")
    y0 = pivot.y
    # spine: the leather folds out over the skull, then hangs close to the cheek
    spine = [V(s * 0.27, y0, 2.10), V(s * 0.44, y0, 2.10), V(s * 0.545, y0 - 0.01, 1.98),
             V(s * 0.585, y0 - 0.02, 1.80), V(s * 0.59, y0 - 0.03, 1.62), V(s * 0.57, y0 - 0.04, 1.44)]
    width = (0.22, 0.30, 0.37, 0.41, 0.40, 0.34)
    m = len(spine) - 1

    # outward normal at each spine point (away from the skull), averaged over the adjacent segments
    head_c = V(0, y0, 1.80)
    pn = []
    for i in range(m + 1):
        t0 = (spine[min(i + 1, m)] - spine[max(i - 1, 0)]).normalized()
        nn = V(0, 1, 0).cross(t0).normalized()
        if nn.dot(spine[i] - head_c) < 0:
            nn = -nn
        pn.append(nn)

    def strand(u, t):
        f = min(max(t, 0.0), 1.0) * m
        k = min(int(f), m - 1)
        a = f - k
        c = spine[k].lerp(spine[k + 1], a)
        w = width[k] + (width[k + 1] - width[k]) * a
        nrm = pn[k].lerp(pn[k + 1], a).normalized()
        cup = 0.035 * math.sin(math.pi * u) * math.sin(math.pi * min(t * 1.2, 1.0))
        return c + V(0, (u - 0.5) * w, 0) + nrm * cup, nrm

    p.fringe(strand, lobes=3, zone=Z_EAR, rows=7, cpl=4, th=(0.11, 0.05), notch=0.18, end_len=0.8,
             bottom=0.5, valley=0.40, valley_from=0.45)
    return p


def paw_parts(c, k):
    """Chunky paw: loft sections of the rounded block and its four toes (centre, radii, axis)."""
    cx, cy = c.x, c.y
    secs = [dict(c=(cx, cy, 0.02), rx=0.135 * k, rz=0.16 * k, n=2.6),
            dict(c=(cx, cy - 0.005, 0.06), rx=0.152 * k, rz=0.175 * k, n=2.6),
            dict(c=(cx, cy + 0.01, 0.12), rx=0.145 * k, rz=0.16 * k, n=2.5),
            dict(c=(cx, cy + 0.03, 0.17), rx=0.125 * k, rz=0.13 * k, n=2.3)]
    toes = []
    for ang in (-0.64, -0.215, 0.215, 0.64):
        tx = cx + math.sin(ang) * 0.125 * k
        ty = cy - math.cos(ang) * 0.14 * k - 0.02
        tz = 0.066 if abs(ang) < 0.4 else 0.06
        toes.append(((tx, ty, tz), (0.052 * k, 0.062 * k, 0.056 * k), (math.sin(ang) * 0.3, -1.0, 0.9)))
    return secs, toes


def pads(p, c, k):
    """Toe beans + main pad underneath (separate dark shells)."""
    cx, cy = c.x, c.y
    pad_z = 0.02
    for ang in (-0.6, -0.2, 0.2, 0.6):
        tx = cx + math.sin(ang) * 0.092 * k
        ty = cy - math.cos(ang) * 0.11 * k - 0.01
        dome(p, V(tx, ty, pad_z), 0.03 * k, 0.036 * k, 0.02)
    dome(p, V(cx, cy + 0.045 * k, pad_z), 0.07 * k, 0.055 * k, 0.02)


def dome(p, c, rx, ry, h):
    secs = [dict(c=(c.x, c.y, c.z + 0.004), rx=rx, rz=ry), dict(c=(c.x, c.y, c.z - h * 0.55), rx=rx * 0.86, rz=ry * 0.86)]
    p.loft(secs, Z_PAD, sides=8, cap0="flat", cap1=(c.x, c.y, c.z - h), up=(0, -1, 0))
    p.close(Z_PAD)


FRONT_LEG = dict(path=[V(0.20, -0.30, 1.06), V(0.25, -0.31, 0.84), V(0.27, -0.33, 0.56), V(0.275, -0.35, 0.32),
                       V(0.275, -0.365, 0.12)],
                 rx=(0.15, 0.18, 0.15, 0.135, 0.125), rz=(0.18, 0.20, 0.155, 0.138, 0.13), sides=12,
                 cap0=(0.19, -0.29, 1.13), paw=(V(0.275, -0.40, 0), 1.05), lo=(0.0, -0.74, -0.05),
                 hi=(0.54, 0.02, 1.22), target=640,
                 # feathering on the back of the forearm: centre angle, (top z, hem z, thickness)
                 feather_c=0.0, feather_z=(0.86, 0.47, 0.05))
REAR_LEG = dict(path=[V(0.20, 0.33, 1.04), V(0.28, 0.38, 0.86), V(0.30, 0.46, 0.64), V(0.30, 0.54, 0.42),
                      V(0.29, 0.52, 0.24), V(0.285, 0.46, 0.10)],
                rx=(0.15, 0.20, 0.19, 0.145, 0.125, 0.122), rz=(0.20, 0.27, 0.235, 0.155, 0.13, 0.125), sides=14,
                cap0=(0.19, 0.32, 1.12), paw=(V(0.285, 0.43, 0), 1.0), lo=(0.0, 0.02, -0.05), hi=(0.64, 0.92, 1.22),
                target=720,
                # "pants" on the back and outer back of the thigh
                feather_c=0.35, feather_z=(1.00, 0.56, 0.055))
LEG_CACHE = {}


def fused_leg(spec):
    """One fused surface for the dog's LEFT leg (the right leg is its exact mirror): the leg loft, the
    paw block and toes, and soft feathering volumes, joined with fillets."""
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
    d_toes = None
    for c, r, ax in toes:
        d = sd_ell(G.P, c, track_axes(ax), r)
        d_toes = d if d_toes is None else np.minimum(d_toes, d)
    base = smin(base, d_toes, 0.016)
    # feathering: the coat on the back of the forearm / thigh grows out and ends in a soft, gently
    # waved hem (theta = 0 straight behind the leg, positive toward the outside)
    X, Y, Z = G.P[..., 0], G.P[..., 1], G.P[..., 2]
    zs = [q.z for q in path][::-1]
    ax_x = np.interp(Z, zs, [q.x for q in path][::-1])
    ax_y = np.interp(Z, zs, [q.y for q in path][::-1])
    th = np.arctan2(X - ax_x, Y - ax_y) - spec["feather_c"]
    z_top, z_hem, T = spec["feather_z"]
    edge = z_hem + 0.03 * np.cos(np.pi * th / 0.45) + 0.05 * (th / 1.2) ** 2
    grow = (T * (0.45 + 0.55 * sstep(z_top - 0.04, edge + 0.08, Z)) * sstep(1.45, 0.95, np.abs(th))
            * sstep(edge - 0.012, edge + 0.045, Z) * sstep(z_top, z_top - 0.14, Z))
    vs, fs = extract(G, blur(base - grow), spec["target"], name="leg_fur")
    tuft = sstep(0.0, 0.045, G.sample(grow, vs))
    flow = blend_flow(vs, [(G.sample(d_leg, vs), (0, -0.05, -1)), (G.sample(d_paw, vs), (0, -1, 0))])
    flow = flow + tuft[:, None] * np.array((0.0, 0.35, -1.0))
    flow /= np.maximum(np.linalg.norm(flow, axis=1), 1e-6)[:, None]
    LEG_CACHE[key] = (vs, fs, tuft, flow)
    return LEG_CACHE[key]


def leg_part(spec, side, name, pid, pivot, joint):
    p = Part(name, pid, pivot, joint)
    vs, fs, tuft, flow = fused_leg(spec)
    if side < 0:
        m = np.array((-1.0, 1.0, 1.0))
        vs, flow, fs = vs * m, flow * m, [tuple(reversed(fc)) for fc in fs]
    p.add_mesh(vs, fs, Z_FUR, tuft, flow)
    pc, pk = spec["paw"]
    pads(p, V(side * pc.x, pc.y, 0), pk)
    return p


def build_front_leg(side):
    s = side
    return leg_part(FRONT_LEG, s, f"Retriever_LegF{'L' if s > 0 else 'R'}", P_LEGFL if s > 0 else P_LEGFR,
                    V(s * 0.25, -0.32, 0.92), "shoulder (swing about the side-to-side axis)")


def build_rear_leg(side):
    s = side
    return leg_part(REAR_LEG, s, f"Retriever_LegB{'L' if s > 0 else 'R'}", P_LEGBL if s > 0 else P_LEGBR,
                    V(s * 0.26, 0.36, 0.96), "hip (swing about the side-to-side axis)")


# the tail's side silhouette (y, z): a smooth front line and a fuller, feathered back line that
# meet in a soft point; the root end sits inside the rump
TAIL_FRONT = [(0.44, 1.18), (0.62, 1.35), (0.78, 1.52), (0.89, 1.70), (0.95, 1.86), (1.00, 1.97)]
TAIL_BACK = [(0.62, 1.02), (0.83, 1.05), (1.01, 1.14), (1.14, 1.29), (1.20, 1.47), (1.19, 1.65), (1.13, 1.82),
             (1.07, 1.94)]
TAIL_TIP = (1.04, 2.02)


def catmull(pts, t):
    n = len(pts) - 1
    f = min(max(t, 0.0), 1.0) * n
    k = min(int(f), n - 1)
    u = f - k
    p0, p1, p2, p3 = pts[max(k - 1, 0)], pts[k], pts[k + 1], pts[min(k + 2, n)]
    return 0.5 * ((2 * p1) + (p2 - p0) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                  + (3 * p1 - p0 - 3 * p2 + p3) * u ** 3)


def seg_dist2(py, pz, A, B):
    """Distance from 2D points to the segments A[i] -> B[i] (min over segments)."""
    P = np.stack([py, pz], -1)[..., None, :]
    AB = B - A
    t = np.clip(np.sum((P - A) * AB, -1) / np.maximum(np.sum(AB * AB, -1), 1e-12), 0.0, 1.0)
    return np.linalg.norm(P - (A + t[..., None] * AB), axis=-1).min(-1)


def poly_sdf2(py, pz, poly):
    """Signed distance (negative inside) from 2D points to a closed polygon."""
    A = np.asarray(poly, float)
    B = np.roll(A, -1, axis=0)
    d = seg_dist2(py, pz, A, B)
    ay, az, by, bz = A[:, 0], A[:, 1], B[:, 0], B[:, 1]
    zz, yy = pz[..., None], py[..., None]
    cross = (az > zz) != (bz > zz)
    yint = ay + (zz - az) * (by - ay) / np.where(np.abs(bz - az) < 1e-12, 1e-12, bz - az)
    inside = (np.sum(cross & (yy < yint), -1) % 2) == 1
    return np.where(inside, -d, d)


def build_tail():
    """ONE continuous plume. Its side silhouette is drawn as a smooth front line and a fuller back
    line with a few broad, gentle waves, meeting in a soft point; the silhouette is then inflated
    into a rounded body (thickest along the front, where the tail bone runs, rounded off toward the
    feathered back edge), so there is no sheet, no seam and no edge anywhere."""
    pivot = V(0.0, 0.62, 1.16)
    p = Part("Retriever_Tail", P_TAIL, pivot, "tail root (wag = turn about the vertical axis)")
    front = [np.array(q) for q in TAIL_FRONT + [TAIL_TIP]]
    back = [np.array(q) for q in TAIL_BACK + [TAIL_TIP]]
    F_line = np.array([catmull(front, i / 120) for i in range(121)])
    B_line = np.array([catmull(back, i / 160) for i in range(161)])
    # broad soft waves along the feathered back edge (none at the root or the tip)
    tan = np.gradient(B_line, axis=0)
    nrm = np.stack([tan[:, 1], -tan[:, 0]], 1)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1), 1e-9)[:, None]
    mid = F_line[np.argmin(np.linalg.norm(F_line[None, :, :] - B_line[:, None, :], axis=2), axis=1)]
    nrm *= np.where(np.sum(nrm * (B_line - mid), 1) < 0, -1.0, 1.0)[:, None]
    sv = np.linspace(0.0, 1.0, len(B_line))
    amp = 0.02 * sstep(0.08, 0.28, sv) * sstep(0.95, 0.72, sv)
    B_line = B_line + nrm * (amp * np.cos(2 * np.pi * 3.5 * (sv - 0.12)))[:, None]
    outline = np.concatenate([F_line, B_line[::-1][1:-1]])
    G = Grid((-0.20, 0.34, 0.90), (0.20, 1.36, 2.12), 0.010, sym_x=True)
    X, Y, Z = G.P[..., 0], G.P[..., 1], G.P[..., 2]
    Y2, Z2 = Y[0], Z[0]
    d2 = poly_sdf2(Y2, Z2, outline)                       # 2D silhouette distance
    d_front = seg_dist2(Y2, Z2, F_line[:-1], F_line[1:])  # distance behind the front line
    taper = 1.0 - 0.5 * sstep(1.35, 2.02, Z2)
    w_max = (0.085 + 0.05 * sstep(0.30, 0.06, d_front)) * taper
    din = np.clip(-d2 / 0.11, 0.0, 1.0)
    W = w_max * np.sqrt(1.0 - (1.0 - din) ** 2)           # round profile: no thin edge anywhere
    F = np.where(d2[None] < 0, np.abs(X) - W[None], np.sqrt(X * X + d2[None] ** 2))
    vs, fs = extract(G, blur(F, 2), 1150, name="tail_fur")
    tuft = sstep(0.06, 0.34, seg_dist2(vs[:, 1], vs[:, 2], F_line[:-1], F_line[1:]))
    flow = np.tile(np.array((0.0, 0.45, 0.89)), (len(vs), 1))
    p.add_mesh(vs, fs, Z_FUR, tuft, flow)
    return p


def build_tag():
    c, a, w = neck_frame()
    ring_c = band_point(0.0, 0.40, c, w) + V(0, -0.035, -0.03)
    pivot = ring_c + V(0, 0, 0.05)
    p = Part("Retriever_CrystalTag", P_TAG, pivot, "tag ring on the collar (swing pivot)")
    secs = []
    for i in range(14):
        th = 2 * math.pi * i / 14
        secs.append(dict(c=ring_c + V(math.cos(th) * 0.048, 0, math.sin(th) * 0.048), rx=0.015, rz=0.015))
    p.loft(secs, Z_METAL, sides=6, up=(0, 1, 0), closed_path=True)
    p.close(Z_METAL)
    cap_c = ring_c + V(0, -0.005, -0.07)
    p.loft([dict(c=cap_c + V(0, 0, 0.02), rx=0.04, rz=0.04), dict(c=cap_c - V(0, 0, 0.02), rx=0.05, rz=0.05)],
           Z_METAL, sides=6, cap0="flat", cap1="flat", up=(0, -1, 0))
    p.close(Z_METAL)
    crystal(p, ring_c + V(0, -0.012, -0.19), V(0, -0.10, 1.0), 0.27, 0.075)
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


# palette (sRGB)
HONEY = rgb(186, 110, 38)
GOLD_DK = rgb(214, 144, 56)
GOLD = rgb(236, 174, 78)
GOLD_LT = rgb(248, 204, 122)
CREAM = rgb(252, 230, 182)
CREAM_LT = rgb(255, 244, 218)
NOSE = rgb(44, 34, 40)
TONGUE = (rgb(238, 108, 128), rgb(252, 156, 168), rgb(190, 62, 92))
MOUTH = (rgb(118, 38, 50), rgb(150, 56, 66), rgb(70, 20, 32))
PAD = (rgb(84, 58, 60), rgb(130, 94, 92))
RED = (rgb(204, 46, 50), rgb(238, 90, 78), rgb(142, 24, 40))
LEATHER = (rgb(156, 94, 52), rgb(196, 130, 76), rgb(100, 56, 34))
METAL = (rgb(238, 186, 66), rgb(255, 234, 146), rgb(166, 106, 30))
CRYSTAL = (rgb(84, 190, 255), rgb(214, 248, 255), rgb(36, 106, 214))
EYE_DARK, EYE_IRIS, EYE_LINE = rgb(28, 19, 20), rgb(128, 74, 36), rgb(56, 32, 24)
BROW = rgb(122, 66, 30)
COOL = np.array((0.80, 0.85, 1.0))


POLE_FADE = 1.0


def cell_hash(a, b, k=0.0):
    v = np.sin(a * 12.9898 + b * 78.233 + k * 37.719) * 43758.5453
    return v - np.floor(v)


def fur_param(P, part):
    """Per-part 2D fur coordinates in studs: fu across the flow, fv along it (fur points toward +fv).
    Seams sit where nobody looks (under the belly, the throat, the back of the legs)."""
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
    hd = P - np.array((0.0, -1.30, 1.60))
    along_h = hd @ hax
    perp = hd - along_h[:, None] * hax
    e1 = np.array((1.0, 0.0, 0.0))
    e2 = np.cross(hax, e1)
    fu = np.where(head, np.arctan2(perp @ e1, perp @ e2) * 0.40, fu)
    fv = np.where(head, along_h, fv)
    global POLE_FADE
    POLE_FADE = np.where(head, sstep(0.10, 0.25, np.linalg.norm(perp, axis=1)), 1.0)
    for pid, lx, ly in ((P_LEGFL, 0.27, -0.33), (P_LEGFR, -0.27, -0.33), (P_LEGBL, 0.29, 0.46), (P_LEGBR, -0.29, 0.46)):
        m = part == pid
        fu = np.where(m, np.arctan2(x - lx, -(y - ly)) * 0.15, fu)
        fv = np.where(m, -z, fv)
    tail = part == P_TAIL
    fu = np.where(tail, x + 0.3 * np.arctan2(x, z - y), fu)
    fv = np.where(tail, 0.6 * y + 0.8 * z, fv)
    ears = np.isin(part, (P_EARL, P_EARR))
    fu = np.where(ears, y, fu)
    fv = np.where(ears, -z, fv)
    return fu, fv


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


_HEAD_MASKS = {}


def head_masks(P, part):
    """Per texel: the muzzle weight (0 on the skull .. 1 on the muzzle, smooth across the fused
    fillet, from the head's own component fields) and the mouth mask (the carved opening's walls)."""
    if "m" not in _HEAD_MASKS:
        M = len(P)
        mzw, mouth = np.zeros(M), np.zeros(M)
        h = part == P_HEAD
        if "head" in FUSED and h.any():
            G, comp = FUSED["head"]
            ph = P[h]
            mzw[h] = sstep(-0.025, 0.025, G.sample(comp["rest"], ph) - G.sample(comp["mz"], ph))
            mouth[h] = sstep(0.009, 0.002, mouth_cavity(ph))
        _HEAD_MASKS["m"] = (mzw, mouth)
    return _HEAD_MASKS["m"]


def fur_colour(P, Ns, zone, part, tuft, flow, lock):
    """Albedo of all fur surfaces (fringes included), before lighting."""
    M = len(P)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    up = np.clip(Ns[:, 2], 0, 1)
    n1 = 0.6 * vnoise(P, 2.0) + 0.4 * vnoise(P, 4.1, 1)
    c = mix(np.tile(GOLD, (M, 1)), GOLD_LT, 0.55 * sstep(0.52, 0.60, n1))
    c = mix(c, GOLD_DK, 0.40 * sstep(0.42, 0.34, n1))
    # broad directional strokes along the fur flow (stretched value noise)
    fl = flow.copy()
    fl_len = np.linalg.norm(fl, axis=1)
    dflt = np.tile(np.array((0.0, 0.93, -0.37)), (M, 1))
    fl = np.where(fl_len[:, None] > 0.3, fl / np.maximum(fl_len, 1e-6)[:, None], dflt)
    along = np.sum(P * fl, axis=1)
    q = P - fl * along[:, None] * 0.85
    sn = vnoise(q, 6.5, 3)
    c = mix(c, GOLD_LT, 0.18 * sstep(0.60, 0.70, sn))
    c = mix(c, GOLD_DK, 0.16 * sstep(0.36, 0.27, sn))
    fu, fv = fur_param(P, part)
    st_lt, st_dk = stroke_masks(fu, fv)
    st_lt2, st_dk2 = stroke_masks(fu * 1.7 + 0.37, fv * 1.6 + 0.11, k=5.0)

    body, head, tail = part == P_BODY, part == P_HEAD, part == P_TAIL
    ears = np.isin(part, (P_EARL, P_EARR))
    legs = np.isin(part, (P_LEGFL, P_LEGFR, P_LEGBL, P_LEGBR))
    fused = (zone == Z_FUR) & (body | head | legs | tail)     # the one-piece fur surfaces
    mzw, _ = head_masks(P, part)
    # darker honey saddle along the back, the crown and the top of the tail
    saddle = body * sstep(0.2, 0.9, up) * sstep(1.14, 1.36, z)
    saddle += head * sstep(0.35, 0.95, up) * sstep(2.0, 2.2, z) * 0.6
    saddle += tail * (zone == Z_FUR) * sstep(0.0, 0.7, Ns[:, 2] - Ns[:, 1]) * 0.5
    saddle += legs * sstep(0.84, 1.02, z) * sstep(0.1, 0.7, np.abs(Ns[:, 0])) * 0.35
    c = mix(c, HONEY, 0.55 * np.clip(saddle, 0, 1))
    # cream: underside, chest bib (and its ruff), lower legs + back of legs, muzzle, cheeks and chin
    under = body * np.clip(sstep(-0.05, -0.65, Ns[:, 2]) + sstep(-0.30, -0.66, y) * sstep(1.24, 1.02, z)
                           * sstep(0.1, -0.5, Ns[:, 1]), 0, 1)
    lowleg = legs * sstep(0.50, 0.22, z)
    backleg = legs * np.clip(sstep(0.1, 0.7, Ns[:, 1]) * 0.55, 0, 1)
    # the muzzle is cream by its (continuous) fused weight, fading to gold up its bridge toward the stop
    muzzle = head * np.clip(mzw * (1.0 - 0.85 * sstep(1.62, 1.74, z) * sstep(-1.30, -1.08, y)), 0, 1)
    muzzle = np.maximum(muzzle, head * (zone == Z_FUR) * sstep(1.70, 1.56, z) * sstep(-0.95, -1.12, y))
    cheeks = head * np.clip(sstep(1.68, 1.50, z) * sstep(-0.55, -0.9, y) * 0.9, 0, 1)
    cream = np.clip(under + lowleg + backleg + muzzle + cheeks, 0, 1)
    c = mix(c, CREAM, cream)
    c = mix(c, CREAM_LT, 0.45 * muzzle * sstep(1.46, 1.62, z))
    stop = head * (zone == Z_FUR) * sstep(-0.98, -1.10, y) * sstep(1.80, 1.66, z) * sstep(0.30, 0.10, np.abs(x))
    c = mix(c, GOLD_LT, 0.55 * stop)
    # tail: the feathered underside lightens from gold at its root to cream along its outer edge
    c = mix(c, mix(np.tile(GOLD_LT, (M, 1)), CREAM_LT, sstep(0.35, 1.0, tuft)), tail * 0.85 * sstep(0.05, 0.7, tuft))
    # ears: deeper gold, honey toward the tips
    ear_t = ears * np.clip(tuft, 0, 1)
    c = mix(c, GOLD_DK, 0.6 * ears)
    c = mix(c, HONEY, 0.8 * ear_t ** 1.3)
    # painted brush strokes along the fur flow (not on the ears, which carry their own locks), fading
    # out over the paws
    plain = (zone != Z_EAR) * (1.0 - legs * sstep(0.24, 0.12, z))
    lt_col = mix(np.tile(GOLD_LT, (M, 1)), CREAM_LT, cream)
    dk_col = mix(np.tile(GOLD_DK, (M, 1)), CREAM * np.array((0.93, 0.88, 0.80)), cream)
    c = mix(c, lt_col, 0.34 * np.clip(st_lt + 0.6 * st_lt2, 0, 1) * plain * POLE_FADE)
    c = mix(c, dk_col, 0.30 * np.clip(st_dk + 0.6 * st_dk2, 0, 1) * plain * POLE_FADE)
    # fused fur volumes (ruff, belly, feathering, cheek fluff): coat colour at their roots, lighter
    # toward their outer edge. tuft is 0 on the bare coat, so there is no colour step at any join
    ftip = mix(np.tile(GOLD_LT, (M, 1)), CREAM_LT, cream)
    c = mix(c, ftip, 0.55 * sstep(0.25, 1.0, tuft) * fused * ~tail)
    # ears: lighter toward the lock tips, painted grooves between locks, a soft ridge light
    fringe = ears & (zone == Z_EAR)
    tip_col = np.tile(GOLD * 0.92, (M, 1))
    tipm = sstep(0.55, 1.0, tuft) * fringe * 0.35
    c = mix(c, tip_col, tipm)
    groove = sstep(0.30, 0.04, lock) * sstep(0.45, 0.85, tuft) * fringe
    c = mix(c, c * np.array((0.90, 0.84, 0.80)), 0.35 * groove)
    ridge = sstep(0.62, 1.0, lock) * sstep(0.45, 0.9, tuft) * fringe
    c = mix(c, np.clip(tip_col * 1.04, 0, 1), 0.20 * ridge)
    return c, cream


def paint(P, Ns, Nf, zone, part, tuft, flow, lock):
    M = len(P)
    col = np.tile(GOLD, (M, 1))
    furry = np.isin(zone, (Z_FUR, Z_CLUMP, Z_EAR))
    fc, cream = fur_colour(P, Ns, zone, part, tuft, flow, lock)
    col[furry] = fc[furry]
    down = np.clip(-Ns[:, 2], 0, 1)
    # the mouth opening is carved into the fused head: its walls take the mouth colour
    _, mouthw = head_masks(P, part)
    sh_ = 0.5 + 0.5 * Ns[:, 2]
    mc = mix(np.tile(MOUTH[2], (M, 1)), MOUTH[0], sstep(0.05, 0.55, sh_))
    mc = mix(mc, MOUTH[1], 0.5 * sstep(0.65, 1.0, sh_))
    col = mix(col, mc, mouthw * (zone == Z_FUR))

    def solid(zid, pal):
        base, light_, dark = pal
        sh = 0.5 + 0.5 * Ns[:, 2]
        cc = mix(np.tile(dark, (M, 1)), base, sstep(0.05, 0.55, sh))
        cc = mix(cc, light_, 0.7 * sstep(0.65, 1.0, sh))
        sel = zone == zid
        col[sel] = cc[sel]

    col[zone == Z_NOSE] = NOSE
    solid(Z_TONGUE, TONGUE)
    solid(Z_MOUTH, MOUTH)
    pd = zone == Z_PAD
    col[pd] = mix(np.tile(PAD[0], (M, 1)), PAD[1], 0.5 * sstep(0.3, 0.9, down))[pd]
    solid(Z_BANDANA, RED)
    solid(Z_KNOT, (RED[0] * 0.95, RED[1], RED[2]))
    solid(Z_LEATHER, LEATHER)
    solid(Z_STRAP, (LEATHER[0] * 0.82, LEATHER[1] * 0.88, LEATHER[2]))
    solid(Z_METAL, METAL)
    cr = zone == Z_CRYSTAL
    fac = 0.5 + 0.35 * Nf[:, 2] + 0.25 * Nf[:, 0] - 0.2 * Nf[:, 1]
    ccr = mix(np.tile(CRYSTAL[2], (M, 1)), CRYSTAL[0], sstep(0.2, 0.6, fac))
    ccr = mix(ccr, CRYSTAL[1], sstep(0.66, 0.98, fac))
    col[cr] = ccr[cr]
    return col, furry


def paint_patterns(col, P, Ns, zone, tuft):
    """Bandana polka dots + cream edge line, leather stitching."""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    band = zone == Z_BANDANA
    # dots on a slightly staggered lattice in the chest plane
    gx, gz = x / 0.085, (z + 0.5 * (np.floor(x / 0.085) % 2) * 0.085) / 0.085
    dd = np.sqrt((gx - np.round(gx)) ** 2 + (gz - np.round(gz)) ** 2)
    dots = band & (dd < 0.24) & (tuft > 0.10)
    col[dots] = mix(col[dots], CREAM_LT, sstep(0.24, 0.18, dd)[dots])
    edge_line = band & (tuft > 0.035) & (tuft < 0.075)
    col[edge_line] = mix(col[edge_line], CREAM_LT, 0.85)
    # stitches around the satchel flap and body
    c, (sx, sy, sz) = SATCHEL["c"], SATCHEL["size"]
    lea = zone == Z_LEATHER
    ly, lz = y - c.y, z - c.z
    near_y = np.abs(np.abs(ly) - (sy / 2 - 0.028)) < 0.006
    near_z = (np.abs(lz - (sz * 0.19 - sz * 0.33 + 0.026)) < 0.006)
    dash_y = (np.mod(lz, 0.04) < 0.024)
    dash_z = (np.mod(ly, 0.04) < 0.024)
    stitch = lea & ((near_y & dash_y & (lz > -sz * 0.14)) | (near_z & dash_z & (np.abs(ly) < sy / 2 - 0.03)))
    col[stitch] = mix(col[stitch], CREAM, 0.8)
    return col


def paint_face(col, P, Ns, zone, part):
    """Eyes, brows, lip line and whisker dots, painted in 3D around the recorded face frames."""
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
        front = head & (np.abs(dn) < 0.08) & (zone == Z_FUR)
        r = np.sqrt(eu * eu + ev * ev)
        # happy lower lid: the cheek pushes up into the bottom of the eye
        cut = ev - (-0.78 + 0.28 * eu * eu)
        sdf = np.maximum(r - 1.0, -cut * 0.9)
        ring = front & (sdf > 0) & (sdf < 0.6)
        col[ring] = mix(col[ring], col[ring] * np.array((0.93, 0.86, 0.80)), (0.16 * sstep(0.6, 0.0, sdf))[ring])
        line_w = 0.075 + 0.11 * sstep(0.0, 0.85, ev)
        lid = front & (sdf >= 0) & (sdf < line_w)
        col[lid] = mix(col[lid], EYE_LINE, sstep(line_w + 0.01, line_w - 0.03, sdf)[lid])
        inside = front & (sdf < 0)
        ce = np.tile(EYE_DARK, (len(P), 1))
        iris = sstep(0.25, 0.85, r) * sstep(0.2, -0.75, ev)
        ce = mix(ce, EYE_IRIS, 0.9 * iris)
        ce = mix(ce, EYE_IRIS * 1.5, 0.55 * sstep(-0.45, -0.8, ev) * sstep(0.3, 0.8, r))
        col[inside] = ce[inside]
        after.append((inside, eu, ev))
        if HV["brow"] == "spot":
            bu, bv = eu - 0.02, ev - 1.55
            bd = np.sqrt((bu / 0.55) ** 2 + (bv / 0.30) ** 2)
            bm = front & (bd < 1.0)
            col[bm] = mix(col[bm], CREAM_LT, (0.8 * sstep(1.0, 0.55, bd))[bm])
        else:
            # arched stroke: a raised, eager brow with the inner end tucked a little lower
            tt = np.clip((eu * side + 0.75) / 1.45, 0, 1)                  # 0 inner .. 1 outer
            curve = 1.36 + 0.26 * np.sin(np.pi * np.clip(tt * 0.9 + 0.05, 0, 1)) + 0.06 * tt
            dist = np.abs(ev - curve)
            wdt = 0.13 * (0.55 + 0.6 * np.sin(np.pi * np.clip(tt, 0, 1)) ** 0.7)
            inseg = (eu * side > -0.75) & (eu * side < 0.70)
            bm = front & inseg & (dist < wdt + 0.06)
            col[bm] = mix(col[bm], BROW, (0.95 * sstep(wdt + 0.06, wdt - 0.03, dist))[bm])
    # a thin dark lip rim around the carved mouth opening, a short philtrum, and whisker dots
    mo = FACE["mouth"]
    mx, my, mz = P[:, 0], P[:, 1], P[:, 2]
    mzw, mouthw = head_masks(P, part)
    cav = np.full(len(P), 1.0)
    cav[head] = mouth_cavity(P[head])
    rim = head & (zone == Z_FUR) & (cav > 0.004) & (cav < 0.02)
    col[rim] = mix(col[rim], EYE_LINE, (0.75 * sstep(0.02, 0.011, cav) * sstep(0.004, 0.008, cav))[rim])
    fr = head & (mzw > 0.5) & (mouthw < 0.5) & (my < mo["tip_y"] + 0.30)
    phil = fr & (np.abs(mx) < 0.01) & (mz < mo["nose_bottom"] + 0.005) & (mz > mo["lip_z"]) & (Ns[:, 1] < -0.3)
    col[phil] = mix(col[phil], EYE_LINE, 0.9)
    for sx in (1, -1):
        for (dx, dz) in ((0.10, 0.07), (0.145, 0.055), (0.125, 0.105)):
            wd = np.sqrt((mx - sx * dx) ** 2 + (mz - (mo["lip_z"] + dz)) ** 2)
            wm = fr & (wd < 0.0095) & (my < mo["tip_y"] + 0.16)
            col[wm] = mix(col[wm], GOLD_DK, 0.75)
    # tongue centre groove
    tg = (zone == Z_TONGUE) & (np.abs(mx - 0.012) < 0.008) & (Ns[:, 2] > 0.2)
    col[tg] = col[tg] * 0.8
    return after


def light(col, P, Ns, Nf, zone, ao_s, ao_l, curv, edge, furry, part_ids):
    """Icon-style baked lighting: per-facet key, AO, cool shadows, cool rim, warm edge highlights."""
    Lk = np.array((-0.50, -0.62, 0.62))
    Lk /= np.linalg.norm(Lk)
    Lr = np.array((0.70, 0.62, 0.35))
    Lr /= np.linalg.norm(Lr)
    kf = np.clip(Nf @ Lk, 0, 1)
    ks = np.clip(Ns @ Lk, 0, 1)
    fw = np.where(zone == Z_FUR, 0.10, np.where(furry, 0.18, 0.55))
    k = fw * kf + (1.0 - fw) * ks
    sky = 0.5 + 0.5 * Ns[:, 2]
    lightv = 0.62 + 0.38 * k + 0.12 * sky
    clz = (zone == Z_EAR)
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
    hard = np.isin(zone, (Z_LEATHER, Z_STRAP, Z_METAL, Z_CRYSTAL, Z_BANDANA, Z_KNOT, Z_TOE, Z_PAW, Z_NOSE))
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
mat = bpy.data.materials.new("GoldenRetriever_Atlas")
mat.use_nodes = True

builders = [build_body(), build_head(), build_ear(1), build_ear(-1), build_front_leg(1), build_front_leg(-1),
            build_rear_leg(1), build_rear_leg(-1), build_tail(), build_tag()]
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
                vals[e.index] = False
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
bpy.ops.uv.smart_project(angle_limit=math.radians(52), island_margin=0.004, area_weight=0.0,
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
head_obj = parts["Retriever_Head"]
hm = head_obj.data
uvl = hm.uv_layers.active.data
FACE_DENSITY = 2.1
FACE_AXIS = (0.0, -0.66)          # vertical axis the face island is wrapped around (x, y)
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
    if not (nrm.dot(radial) > 0.35 and nrm.y < -0.1 and abs(ang) < 1.25 and c.z > 1.30
            and zid in (Z_FUR, Z_MUZZLE, Z_NOSE)):
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
bpy.ops.uv.pack_islands(rotate=True, margin=0.004)
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
    bpy.ops.object.bake(type="EMIT", margin=int(16 * BAKE / 2048) + 4, margin_type="EXTEND", use_clear=True)
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
# sanity: an inside-out shell bakes near-zero AO; report the darkest part/zone combinations
occl_rows = []
for pid in range(1, 11):
    for zid in np.unique(zone[part == pid]):
        m_ = (part == pid) & (zone == zid)
        if m_.sum() > 200:
            occl_rows.append((round(float(np.median(ao_s[m_])), 3), pid, int(zid), int(m_.sum())))
occl_rows.sort()
log("lowest median AO (ao, part, zone, texels):", occl_rows[:4])
if DEBUG_MAPS:
    em = np.isin(part, (P_EARL, P_EARR))
    log("DBG ear texels", int(em.sum()), "albedo mean", np.round(colour[em].mean(0), 3),
        "ao_s", round(float(ao_s[em].mean()), 3), "ao_l", round(float(ao_l[em].mean()), 3),
        "Ns.x*side", round(float((Ns[em, 0] * np.sign(P[em, 0])).mean()), 3), "tuft", round(float(tuft[em].mean()), 3),
        "zones", np.unique(zone[em]).tolist())
colour = paint_patterns(colour, P, Ns, zone, tuft)
after = paint_face(colour, P, Ns, zone, part)
colour = light(colour, P, Ns, Nf, zone, ao_s, ao_l, curv, edge, furry, part)
colour = catchlights(colour, after)
# nose shine and nostrils, painted after lighting
nose = FACE["nose"]
nsel = zone == Z_NOSE
dn = P - np.array(nose["c"])
shine = np.exp(-(((dn[:, 0] + 0.03) / 0.04) ** 2 + ((P[:, 2] - (nose["top"] - 0.016)) / 0.018) ** 2)) * (Ns[:, 2] > 0.1)
colour[nsel] = mix(colour[nsel], np.array((0.93, 0.96, 1.0)), (0.9 * shine)[nsel])
colour[nsel] = mix(colour[nsel], colour[nsel] + 0.10, (sstep(0.5, 0.95, Ns[:, 2]) * 0.6)[nsel])
for sx_ in (1.0, -1.0):
    ex_ = (dn[:, 0] - sx_ * 0.040) / 0.024
    ez_ = (P[:, 2] - (nose["c"].z - 0.020) - 0.35 * (dn[:, 0] - sx_ * 0.040) * sx_) / 0.012
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
JOINT_PARENT = {"Retriever_Body": None, "Retriever_Head": "Retriever_Body",
                "Retriever_EarL": "Retriever_Head", "Retriever_EarR": "Retriever_Head",
                "Retriever_LegFL": "Retriever_Body", "Retriever_LegFR": "Retriever_Body",
                "Retriever_LegBL": "Retriever_Body", "Retriever_LegBR": "Retriever_Body",
                "Retriever_Tail": "Retriever_Body", "Retriever_CrystalTag": "Retriever_Body"}
MOTION = {
    "Retriever_Body": "root part: bob up/down in Studio Y and a small roll about Studio Z while running",
    "Retriever_Head": "nod = pitch about Studio X, tilt = roll about Studio Z, look = yaw about Studio Y, all through the neck joint",
    "Retriever_EarL": "flop = rotate about Studio Z (front-back axis) through the ear root; child of the head",
    "Retriever_EarR": "flop = rotate about Studio Z (front-back axis) through the ear root; child of the head",
    "Retriever_LegFL": "trot = swing about Studio X (side-to-side axis) through the shoulder",
    "Retriever_LegFR": "trot = swing about Studio X (side-to-side axis) through the shoulder",
    "Retriever_LegBL": "trot = swing about Studio X (side-to-side axis) through the hip",
    "Retriever_LegBR": "trot = swing about Studio X (side-to-side axis) through the hip",
    "Retriever_Tail": "wag = yaw about Studio Y through the tail root (lift = pitch about Studio X)",
    "Retriever_CrystalTag": "dangle = swing about Studio X through the ring on the collar (lags the body)",
}


def studio(v):
    return [round(-v[0], 4) + 0.0, round(v[2], 4) + 0.0, round(v[1], 4) + 0.0]


def studio_size(v):
    return [round(v[0], 4), round(v[2], 4), round(v[1], 4)]


def world_bounds(o):
    ws = [o.matrix_world @ vv.co for vv in o.data.vertices]
    return (Vector([min(w[k] for w in ws) for k in range(3)]), Vector([max(w[k] for w in ws) for k in range(3)]))


report = {"asset": STEM, "variant": VARIANT, "blender_version": bpy.app.version_string,
          "authoring": "final Roblox stud size (1 Blender unit = 1 stud); import at 1:1, do not scale",
          "axes": "Blender Z-up, front -Y, the dog's left +X; paws on z = 0",
          "texture": f"textures/{TEX_PATH.name} ({ATLAS}x{ATLAS}, shared by every part)",
          "budget_note": "over the first 5k brief on purpose (the raised detail budget allows ~12k+); "
                         "every part stays far below Roblox's 20k per-mesh cap",
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
                     "head_top_studs": round(world_bounds(parts["Retriever_Head"])[1].z, 4)}
body_pivot = parts["Retriever_Body"].location.copy()
install = {
    "asset": STEM,
    "axis": "studio = (-x, z, y) of blender; Blender front -Y = Studio front -Z",
    "units": "studs; the model is at final size, import 1:1 and do not scale",
    "sides": "L/R are the dog's own left/right; its left is Blender +X = Studio -X",
    "origin": "all positions are relative to the model origin = the ground point under the body pivot (Blender world origin)",
    "ground_point": studio((0.0, 0.0, 0.0)),
    "overall_size": studio_size(size),
    "overall_center": studio((lo_all + hi_all) / 2),
    "texture": f"textures/{TEX_PATH.name}",
    "texture_note": "one shared atlas; every MeshPart uses the same TextureID (Common rarity: no Neon, no glow)",
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
    select_only(objs, parts["Retriever_Body"])
    bpy.ops.export_scene.gltf(filepath=str(GLB_PATH), export_format="GLB", use_selection=True, export_apply=True)
    select_only(objs, parts["Retriever_Body"])
    bpy.ops.export_scene.fbx(filepath=str(FBX_PATH), use_selection=True, object_types={"MESH"},
                             axis_forward="-Z", axis_up="Y", path_mode="COPY", embed_textures=True,
                             add_leaf_bones=False)
    log("exported", FBX_PATH.name, GLB_PATH.name)

# =============================================================================================
# armature (Blender only, for posing previews; the exports above are the plain rigid parts)
# =============================================================================================
arm_data = bpy.data.armatures.new("Retriever_Rig")
arm = bpy.data.objects.new("Retriever_Rig", arm_data)
scene.collection.objects.link(arm)
select_only([arm])
bpy.ops.object.mode_set(mode="EDIT")
ebs = {}
for name, o in parts.items():
    eb = arm_data.edit_bones.new(name.replace("Retriever_", ""))
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
    o.parent_bone = name.replace("Retriever_", "")
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


tgt = V(0, -0.2, 1.05)
ft = V(0, -1.05, 1.70)
TAIL_T = V(0, 0.98, 1.50)          # close-ups straight from the dog's right side, like side.png
FACE_T = V(0, -1.00, 1.66)


def closeups(out):
    shoot(out / "closeup-tail.png", around(TAIL_T, (-1, 0, 0.12), 4.6), TAIL_T, res=(1200, 1200))
    shoot(out / "closeup-face-side.png", around(FACE_T, (-1, 0, 0.10), 4.4), FACE_T, res=(1200, 1200))


TROT_A = {"LegFL": (28, 0, 0), "LegBR": (28, 0, 0), "LegFR": (-28, 0, 0), "LegBL": (-28, 0, 0)}
if not NO_PREVIEWS and QUICK:
    shoot(OUT / "three-quarter.png", around(tgt, (-0.75, -0.9, 0.42), 11.0), tgt)
    shoot(OUT / "side.png", around(tgt, (-1, 0, 0.12), 11.5), tgt)
    shoot(OUT / "front.png", around(tgt, (0, -1, 0.15), 11.0), tgt)
    shoot(OUT / "face-closeup.png", around(ft, (-0.35, -1, 0.12), 5.0), ft)
    shoot(OUT / "back-three-quarter.png", around(tgt, (0.8, 0.9, 0.5), 11.5), tgt)
    shoot(OUT / "face-side.png", around(ft + V(0, 0.1, -0.05), (-1, -0.45, 0.05), 5.0), ft + V(0, 0.1, -0.05))
    closeups(OUT)
    if "--pose" in ARGS:
        pose(dict(TROT_A, Head=(-15, 18, 20), Tail=(0, 30, 0), EarL=(0, 0, 25), EarR=(0, 0, 25)))
        shoot(OUT / "pose-quick.png", around(tgt, (-0.8, -0.7, 0.3), 11.0), tgt)
        pose({})

if not NO_PREVIEWS and not QUICK and "--views-min" in ARGS:
    # reduced render set: side, three-quarter and the tail / face close-ups only
    shoot(OUT / "three-quarter.png", around(tgt, (-0.75, -0.9, 0.42), 11.0), tgt)
    shoot(OUT / "side.png", around(tgt, (-1, 0, 0.12), 11.5), tgt)
    closeups(OUT)
elif not NO_PREVIEWS and not QUICK:
    P_ = OUT
    views = [
        ("three-quarter.png", "Three-quarter", around(tgt, (-0.75, -0.9, 0.42), 11.0), tgt),
        ("front.png", "Front", around(tgt, (0, -1, 0.15), 11.0), tgt),
        ("side.png", "Side (dog's right)", around(tgt, (-1, 0, 0.12), 11.5), tgt),
        ("back.png", "Back", around(tgt, (0, 1, 0.3), 11.5), tgt),
    ]
    shots = [(shoot(P_ / fn, loc, t), lab) for fn, lab, loc, t in views]
    face = shoot(P_ / "face-closeup.png", around(ft, (-0.35, -1, 0.12), 5.0), ft, res=(1400, 1400))
    face_side = shoot(P_ / "face-side.png", around(ft + V(0, 0.1, -0.05), (-1, -0.45, 0.05), 5.0),
                      ft + V(0, 0.1, -0.05), res=(1400, 1400))
    closeups(P_)

    # --- true scale: orthographic, the dog beside a grey 5-stud R15 block figure -------------------
    fig = r15_figure((3.1, 0.8, 0.0))
    view = Vector((-0.30, -1.0, 0.10)).normalized()
    yaw = math.degrees(math.atan2(view.x, -view.y))
    ht = report["overall"]["head_top_studs"]
    labs = [label("R15 block figure, 5 studs", (3.1, 0.8, 5.3), 0.22, (90, 0, yaw)),
            label(f"Golden Retriever: {ht:.2f} tall, {size.y:.2f} long", (-0.55, -0.3, ht + 0.45), 0.17, (90, 0, yaw))]
    extras += fig + labs
    scale_png = shoot(P_ / "scale-vs-5stud-r15.png", Vector((1.45, 0.3, 2.75)) + view * 40, (1.45, 0.3, 2.75),
                      ortho=8.2, res=(1500, 1300), show=fig + labs)
    # --- a guess at the gameplay camera: 70 deg vertical FOV, ~18 studs away, high angle -------------
    for o_ in fig:
        o_.location = (-5.3, 0.4, 0)
    gl_view = Vector((-0.25, -0.8, 1.0)).normalized()
    game_png = shoot(P_ / "gameplay-view.png", Vector((-1.2, 0.3, 1.2)) + gl_view * 16.0, (-1.2, 0.3, 1.2),
                     lens=12.0 / math.tan(math.radians(35)), res=(1600, 900), show=fig, sensor=24.0)
    for o_ in fig:
        o_.location = (0, 0, 0)

    # --- pose check: trot and head tilt through the bone pivots ------------------------------------
    TROT_B = {k_: (-v_[0], 0, 0) for k_, v_ in TROT_A.items()}
    poses = [
        ("Trot A: legs +/-28 deg (right side)", TROT_A, around(tgt, (-1, 0.05, 0.1), 11.0), tgt),
        ("Trot B: legs -/+28 deg (left side)", TROT_B, around(tgt, (1, 0.05, 0.1), 11.0), tgt),
        ("Trot A from low front, tail wag 25", dict(TROT_A, Tail=(0, 25, 0)),
         around(tgt + V(0, 0, -0.3), (-0.55, -1.0, -0.02), 9.5), tgt + V(0, 0, -0.3)),
        ("Head tilt 22 + nod down 18, ears flop", {"Head": (18, 0, 22), "EarL": (0, 0, 20), "EarR": (0, 0, 25)},
         around(ft + V(0, 0.3, -0.25), (-0.5, -1.0, 0.25), 6.5), ft + V(0, 0.3, -0.25)),
        ("Head up 22 + turn 28, tail wag 30", {"Head": (-22, 28, 0), "Tail": (0, 30, 0), "EarL": (0, 0, -20),
                                                "EarR": (0, 0, -20)}, around(tgt, (0.75, 0.75, 0.45), 11.0), tgt),
        ("Gallop reach: fronts -30, backs +30, tag 30",
         {"LegFL": (-30, 0, 0), "LegFR": (-30, 0, 0), "LegBL": (30, 0, 0), "LegBR": (30, 0, 0),
          "CrystalTag": (-30, 0, 0), "Head": (10, 0, 0), "Tail": (25, 0, 0)}, around(tgt, (-1, -0.35, 0.05), 11.0), tgt),
    ]
    pose_items = []
    for i, (lab, rots, loc, t) in enumerate(poses):
        pose(rots)
        pose_items.append((shoot(P_ / f"_pose-{i}.png", loc, t, res=(900, 900)), lab))
    pose({})
    make_sheet(pose_items, 3, 600, P_ / "pose-check.png", "Golden Retriever: pose check through the joint pivots",
               "Each part rotates about its own pivot (Blender armature, preview only). "
               "Look for gaps at the shoulders, hips, neck, ears and tail root.")
    for pth, _ in pose_items:
        pth.unlink()

    for stale in ("hero-cycles.png", "hero-cycles-low.png", "side-left.png", "back-three-quarter.png"):
        if (P_ / stale).exists():
            (P_ / stale).unlink()
    make_sheet([shots[0], shots[1], shots[2], shots[3], (face, "Face close-up"),
                (scale_png, "True scale vs 5-stud R15 figure"), (P_ / "pose-check.png", "Pose check (trot, head tilt)")],
               4, 440, P_ / f"{STEM}-sheet.png",
               f"Golden Retriever pet (Common, Loot): {report['total_triangles']:,} tris, one 1024 atlas",
               "Blender 5.2 Eevee renders. Fur is fused into each part as soft volumes. Blender-verified, Studio untested.")
log("done")
