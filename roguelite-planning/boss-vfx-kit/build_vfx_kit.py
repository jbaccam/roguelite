"""
build_vfx_kit.py -- Boss VFX kit generator (Blender 5.2, headless, self-contained).

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup ^
        --python build_vfx_kit.py [-- --skip-sprites --skip-render]

One run:
  1. paints every sprite / flipbook / decal PNG (paint_textures.py, numpy only)
  2. builds the debris meshes at final stud size (1 unit = 1 stud, Z up, front = -Y,
     origin at base centre, z = 0 is the ground)
  3. smart-UVs each texture family jointly and paints its shared atlas with a small
     numpy software rasteriser (3D position/normal/facet-flag -> painterly colour;
     no Cycles bake)
  4. exports one FBX per mesh + AllMeshes.fbx (textures embedded, .fbm copy beside)
  5. re-imports every FBX to verify triangles, size and the embedded PNG
  6. renders EEVEE 3/4 thumbnails and writes previews/Kit.png + manifest.json
"""
import json
import math
import os
import shutil
import sys
import tempfile
import time

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paint_textures as PT  # noqa: E402

TEX = os.path.join(HERE, "textures")
FBX = os.path.join(HERE, "exports", "fbx")
PREV = os.path.join(HERE, "previews")
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
T0 = time.time()
TAU = math.tau


def log(*a):
    print("[vfx %6.1fs]" % (time.time() - T0), *a, flush=True)


# face flags (stored per face, survive bevel + triangulate)
BODY, CHAMFER, GOLD, GOLD_CH, OUTER, INNER, EDGE, EDGE_CH, BASE = range(9)
C = PT.rgb

# palettes (sRGB), matched to the four boss sheets
ICE_DEEP, ICE_MID, ICE_LIGHT, ICE_PALE = C(58, 118, 196), C(104, 176, 230), C(172, 223, 248), C(234, 249, 255)
ICE_EDGE, ICE_STREAK = C(246, 252, 255), C(226, 246, 255)
CH_DARK, CH_MID, CH_LIGHT, CH_EDGE, CH_CHAR = C(40, 38, 45), C(58, 56, 65), C(80, 78, 90), C(122, 128, 142), C(26, 21, 23)
SEAM_RED, SEAM_ORANGE, SEAM_CORE = C(198, 58, 22), C(255, 138, 28), C(255, 224, 124)
SS_SHADOW, SS_MID, SS_LIGHT, SS_EDGE = C(186, 144, 96), C(216, 178, 124), C(238, 210, 162), C(247, 230, 190)
SS_BAND, SS_CARVE, SS_CARVE_DARK, SS_GROOVE = C(200, 160, 108), C(150, 108, 66), C(116, 80, 48), C(138, 98, 60)
G_DARK, G_MID, G_LIGHT, G_EDGE = C(180, 120, 28), C(232, 170, 46), C(252, 214, 104), C(255, 238, 164)
RED_DARK, RED_MID, RED_LIGHT, RED_EDGE = C(172, 46, 34), C(212, 68, 46), C(236, 98, 64), C(244, 132, 96)
BEIGE, BEIGE_DK, BEIGE_MID, BEIGE_LT = C(232, 210, 172), C(198, 170, 128), C(216, 190, 148), C(240, 222, 188)


# ============================================================ bmesh building
def new_bm():
    bm = bmesh.new()
    bm.faces.layers.int.new("flag")
    bm.faces.layers.int.new("tone")
    return bm


def set_flags(bm, flag):
    fl = bm.faces.layers.int["flag"]
    for f in bm.faces:
        f[fl] = flag


def finish(bm, rng, bevel, min_angle=0.3, keep_verts=None):
    """Soft chamfer on real creases, tag the chamfer faces, triangulate."""
    fl, tl = bm.faces.layers.int["flag"], bm.faces.layers.int["tone"]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        f[tl] = int(rng.integers(0, 1 << 20))
    keep = set(keep_verts or [])
    edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > min_angle
             and not (keep and all(v in keep for v in e.verts))]
    if bevel > 0 and edges:
        res = bmesh.ops.bevel(bm, geom=edges, offset=bevel, offset_type="OFFSET", segments=1, profile=0.5,
                              affect="EDGES", clamp_overlap=True)
        new = set(res["faces"])
        for f in new:
            nb = set()
            for e in f.edges:
                for g in e.link_faces:
                    if g is not f and g not in new:
                        nb.add(g[fl])
            if nb and nb <= {GOLD}:
                f[fl] = GOLD_CH
            elif OUTER in nb:
                f[fl] = CHAMFER
            elif nb and nb <= {INNER, EDGE}:
                f[fl] = EDGE_CH
            else:
                f[fl] = CHAMFER
            f[tl] = int(rng.integers(0, 1 << 20))
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    return bm


def hull(points):
    bm = new_bm()
    vs = [bm.verts.new(p) for p in points]
    bmesh.ops.convex_hull(bm, input=vs)
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(6), verts=bm.verts[:], edges=bm.edges[:])
    return bm


def crystal(rng, length, radius, sides=6, tip=0.3, taper=0.8, sink=0.1, oblique=(0.0, 0.0)):
    """Hexagonal-ish prism with a pointed, slightly offset tip. Local axis = +Z."""
    bm = new_bm()
    rot0 = rng.uniform(0, TAU)
    step = TAU / sides
    angs = [rot0 + k * step + rng.uniform(-0.15, 0.15) * step for k in range(sides)]
    jit = [rng.uniform(0.84, 1.14) for _ in range(sides)]
    rings = []
    for i, (z, s) in enumerate(zip([-sink * length, 0.5 * (1 - tip) * length, (1 - tip) * length], [1.0, 0.95, taper])):
        ring = []
        for a, j in zip(angs, jit):
            px, py = math.cos(a) * radius * j * s, math.sin(a) * radius * j * s
            pz = z + (oblique[0] * px + oblique[1] * py if i == 0 else rng.uniform(-0.012, 0.012) * length)
            ring.append(bm.verts.new((px, py, pz)))
        rings.append(ring)
    apex = bm.verts.new((rng.uniform(-0.12, 0.12) * radius, rng.uniform(-0.12, 0.12) * radius, length))
    bm.faces.new(list(reversed(rings[0])))
    for r0, r1 in zip(rings[:-1], rings[1:]):
        for k in range(sides):
            k2 = (k + 1) % sides
            bm.faces.new((r0[k], r0[k2], r1[k2], r1[k]))
    for k in range(sides):
        bm.faces.new((rings[-1][k], rings[-1][(k + 1) % sides], apex))
    return bm, rings[0], rot0


def ring_points(rng, sx, sy, sz, rings):
    pts = []
    for hz, rs, cnt in rings:
        off = rng.uniform(0, TAU)
        for k in range(cnt):
            a = off + k * TAU / cnt + rng.uniform(-0.22, 0.22)
            j = rng.uniform(0.86, 1.12)
            pts.append((math.cos(a) * sx * rs * j, math.sin(a) * sy * rs * j, (hz + rng.uniform(-0.02, 0.02)) * sz))
    return pts


def block_points(rng, sx, sy, sz):
    """Box with every corner knocked off: chunky broken cut-stone block."""
    pts = []
    for cx in (-1, 1):
        for cy in (-1, 1):
            for cz in (0, 1):
                ch = rng.uniform(0.14, 0.3)
                X, Y, Z = cx * sx / 2, cy * sy / 2, cz * sz
                zd = -1 if cz else 1
                for p in ((X - cx * ch * sx * 0.6, Y, Z), (X, Y - cy * ch * sy * 0.6, Z), (X, Y, Z + zd * ch * sz * 0.6)):
                    pts.append(tuple(v + rng.uniform(-0.035, 0.035) * s for v, s in zip(p, (sx, sy, sz))))
    return pts


def tilt_to(d, angle):
    """Rotation that leans +Z by angle toward horizontal direction d."""
    axis = Vector((0, 0, 1)).cross(Vector((d[0], d[1], 0)).normalized())
    return Matrix.Rotation(angle, 4, axis)


class MeshBuild:
    def __init__(self, name):
        self.name = name
        self.V, self.P, self.vlocal, self.T = [], [], [], []
        self.flag, self.part, self.tone, self.meta = [], [], [], []

    def add(self, bm, meta, world=None, local_paint=False):
        world = Matrix.Identity(4) if world is None else world
        fl, tl = bm.faces.layers.int["flag"], bm.faces.layers.int["tone"]
        bm.verts.index_update()
        base, pid = len(self.V), len(self.meta)
        self.meta.append(dict(meta))
        for v in bm.verts:
            w = world @ v.co
            p = v.co if local_paint else w
            self.V.append((w.x, w.y, w.z))
            self.P.append((p.x, p.y, p.z))
            self.vlocal.append(local_paint)
        for f in bm.faces:
            idx = [v.index for v in f.verts]
            assert len(idx) == 3
            self.T.append((base + idx[0], base + idx[1], base + idx[2]))
            self.flag.append(f[fl])
            self.part.append(pid)
            self.tone.append(f[tl])
        bm.free()

    def _xf(self, fn):
        V, P, loc = np.array(self.V), np.array(self.P), np.array(self.vlocal)
        V = fn(V)
        P[~loc] = fn(P[~loc])
        self.V, self.P = [tuple(v) for v in V], [tuple(p) for p in P]

    def scale(self, s):
        self._xf(lambda a: a * s)

    def ground(self):
        dz = -min(v[2] for v in self.V)
        self._xf(lambda a: a + np.array([0.0, 0.0, dz]))

    def to_object(self):
        V, T = np.array(self.V), np.array(self.T, np.int64)
        area = np.linalg.norm(np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]), axis=1)
        keep = area > 1e-9
        self.Tk = T[keep]
        self.flagk = np.array(self.flag)[keep]
        self.partk = np.array(self.part)[keep]
        self.tonek = np.array(self.tone)[keep]
        me = bpy.data.meshes.new(self.name)
        me.from_pydata(V.tolist(), [], self.Tk.tolist())
        me.update()
        assert len(me.polygons) == len(self.Tk), self.name
        obj = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(obj)
        self.obj = obj
        return obj


# ============================================================ asset builders
def build_ice_spike(name, H, n, seed):
    rng = np.random.default_rng(seed)
    B = MeshBuild(name)
    pts = ring_points(rng, 0.42 * H, 0.34 * H, H, ((-0.05, 1.0, 9), (0.07, 0.92, 8), (0.15, 0.58, 6)))
    pts = [(x, y - 0.03 * H, z) for x, y, z in pts]
    bm = hull(pts)
    set_flags(bm, BASE)
    B.add(finish(bm, rng, 0.03 * H), {"kind": 0, "H": H})
    specs = [((rng.uniform(-0.04, 0.04) * H, 0.05 * H), (0.0, -1.0), math.radians(12), 1.0 * H, 0.17 * H)]
    side = 1
    for i in range(n - 1):
        f = i / max(1, n - 2)
        if i >= 3:   # fill in behind on the bigger clusters
            az = math.radians(90 + side * rng.uniform(25, 60))
            fwd = -0.3
        else:
            az = math.radians(-90 + side * rng.uniform(35, 80))
            fwd = -0.9
        side = -side
        dist = rng.uniform(0.12, 0.24) * H
        pos = (math.cos(az) * dist, math.sin(az) * dist)
        d = Vector((math.cos(az), math.sin(az) + fwd, 0)).normalized()
        L = H * rng.uniform(0.44, 0.66) * (1 - 0.25 * f)
        specs.append((pos, (d.x, d.y), math.radians(rng.uniform(18, 32)), L, L * rng.uniform(0.17, 0.21)))
    for pos, d, lean, L, R in specs:
        bm, bottom, rot0 = crystal(rng, L, R, tip=rng.uniform(0.26, 0.34), taper=rng.uniform(0.74, 0.84), sink=0.12)
        finish(bm, rng, 0.09 * R, keep_verts=bottom)
        M = Matrix.Translation((pos[0], pos[1], -0.02 * H)) @ tilt_to(d, lean)
        B.add(bm, {"kind": 1, "L": L, "R": R, "rot0": rot0, "sides": 6, "H": H}, world=M, local_paint=True)
    B.scale(H / max(v[2] for v in B.V))
    return B


def build_ice_shard(name, size, seed, double=False):
    rng = np.random.default_rng(seed)
    B = MeshBuild(name)
    sides = 6 if size > 0.7 else 5
    L, R = size, 0.19 * size
    bm, bottom, rot0 = crystal(rng, L, R, sides=sides, tip=0.32, taper=0.8, sink=0.0,
                               oblique=(rng.uniform(-0.35, 0.35), rng.uniform(-0.35, 0.35)))
    finish(bm, rng, 0.08 * R, keep_verts=bottom)
    B.add(bm, {"kind": 1, "L": L, "R": R, "rot0": rot0, "sides": sides, "H": size},
          world=tilt_to((0.3, -1.0), math.radians(8)), local_paint=True)
    if double:
        L2, R2 = 0.62 * size, 0.15 * size
        bm, bottom, rot0 = crystal(rng, L2, R2, sides=5, tip=0.32, taper=0.8, sink=0.05, oblique=(0.2, -0.1))
        finish(bm, rng, 0.08 * R2, keep_verts=bottom)
        M = Matrix.Translation((0.12 * size, 0.04 * size, 0.0)) @ tilt_to((1.0, -0.4), math.radians(38))
        B.add(bm, {"kind": 1, "L": L2, "R": R2, "rot0": rot0, "sides": 5, "H": size}, world=M, local_paint=True)
    B.ground()
    return B


def build_molten_rock(name, size, seed):
    rng = np.random.default_rng(seed)
    B = MeshBuild(name)
    sx, sy, sz = 0.56 * size, 0.47 * size, 0.66 * size
    bm = hull(ring_points(rng, sx, sy, sz, ((0.0, 0.72, 6), (0.32, 1.0, 7), (0.72, 0.86, 6), (1.0, 0.42, 4))))
    set_flags(bm, BODY)
    B.add(finish(bm, rng, 0.05 * size, min_angle=0.25), {"kind": 0, "S": size, "cz": sz * 0.5, "seed": seed})
    B.ground()
    return B


def build_rubble(name, dims, seed):
    rng = np.random.default_rng(seed)
    B = MeshBuild(name)
    bm = hull(block_points(rng, *dims))
    set_flags(bm, BODY)
    M = (Matrix.Rotation(rng.uniform(0, TAU), 4, "Z")
         @ tilt_to((rng.uniform(-1, 1), rng.uniform(-1, 1)), math.radians(rng.uniform(4, 10))))
    B.add(finish(bm, rng, 0.035 * max(dims)), {"kind": 2}, world=M)
    B.ground()
    return B


def build_obelisk(name, H, seed, gold, bands):
    rng = np.random.default_rng(seed)
    B = MeshBuild(name)
    bhw, thw, zt = 0.125 * H, 0.08 * H, 0.84 * H
    bm = new_bm()
    fl = bm.faces.layers.int["flag"]
    rings = []
    for i, z in enumerate([-0.06 * H, 0.33 * zt, 0.67 * zt, zt]):
        hw = bhw + (thw - bhw) * max(z, 0.0) / zt
        rot = rng.uniform(-0.03, 0.03)
        ring = []
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2 + rot
            j = rng.uniform(0.96, 1.04) * math.sqrt(2) * hw
            dz = rng.uniform(-0.008, 0.008) * H if 0 < i < 3 else 0.0
            ring.append(bm.verts.new((math.cos(a) * j, math.sin(a) * j, z + dz)))
        rings.append(ring)
    apex = bm.verts.new((rng.uniform(-0.04, 0.04) * thw, rng.uniform(-0.04, 0.04) * thw, H))
    bm.faces.new(list(reversed(rings[0])))[fl] = BODY
    for r0, r1 in zip(rings[:-1], rings[1:]):
        for k in range(4):
            bm.faces.new((r0[k], r0[(k + 1) % 4], r1[(k + 1) % 4], r1[k]))[fl] = BODY
    for k in range(4):
        bm.faces.new((rings[-1][k], rings[-1][(k + 1) % 4], apex))[fl] = GOLD if gold else BODY
    finish(bm, rng, 0.012 * H + 0.02, keep_verts=rings[0])
    lean_dir = (rng.uniform(-1, 1), rng.uniform(-1, 0.3))
    B.add(bm, {"kind": 0, "H": H, "zt": zt, "bhw": bhw, "thw": thw, "seed": seed,
               "bands": [(a * zt, b * zt) for a, b in bands]},
          world=tilt_to(lean_dir, math.radians(rng.uniform(4, 7))), local_paint=True)
    a0 = rng.uniform(0, TAU)
    for k in range(3):   # broken blocks heaved up around the foot
        a = a0 + k * TAU / 3 + rng.uniform(-0.4, 0.4)
        dist = bhw * rng.uniform(1.05, 1.35)
        dims = (rng.uniform(0.1, 0.16) * H, rng.uniform(0.08, 0.13) * H, rng.uniform(0.06, 0.1) * H)
        bm = hull(block_points(rng, *dims))
        set_flags(bm, BODY)
        finish(bm, rng, 0.03 * max(dims))
        M = (Matrix.Translation((math.cos(a) * dist, math.sin(a) * dist, -0.25 * dims[2]))
             @ tilt_to((rng.uniform(-1, 1), rng.uniform(-1, 1)), math.radians(rng.uniform(8, 25)))
             @ Matrix.Rotation(rng.uniform(0, TAU), 4, "Z"))
        B.add(bm, {"kind": 1}, world=M)
    for k in range(3):   # cracked ground plates pushed up, inner edge raised
        a = a0 + k * TAU / 3 + TAU / 6 + rng.uniform(-0.3, 0.3)
        dist = bhw * rng.uniform(1.45, 1.8)
        rx, ry, th = 0.16 * H, 0.11 * H, 0.05 * H
        pts = []
        for zz, s in ((0.0, 1.0), (th, 0.9)):
            for q in range(7):
                aa = q * TAU / 7 + rng.uniform(-0.2, 0.2)
                j = rng.uniform(0.85, 1.1) * s
                pts.append((math.cos(aa) * rx * j, math.sin(aa) * ry * j, zz))
        bm = hull(pts)
        set_flags(bm, BODY)
        finish(bm, rng, 0.35 * th)
        d = (math.cos(a), math.sin(a))
        M = (Matrix.Translation((d[0] * dist, d[1] * dist, -0.03 * H)) @ tilt_to(d, math.radians(rng.uniform(16, 30)))
             @ Matrix.Rotation(a + math.pi / 2, 4, "Z"))
        B.add(bm, {"kind": 1}, world=M)
    return B


def build_shell_chip(name, size, seed):
    rng = np.random.default_rng(seed)
    B = MeshBuild(name)
    n = int(rng.integers(7, 10))
    rx, ry, th, dome = 0.5 * size, 0.38 * size, 0.13 * size, 0.14 * size
    outline = []
    for k in range(n):
        a = k * TAU / n + rng.uniform(-0.3, 0.3) * TAU / n
        j = rng.uniform(0.72, 1.08)
        outline.append((math.cos(a) * rx * j, math.sin(a) * ry * j))

    def zc(x, y):
        return dome * (1 - (x / rx) ** 2 - (y / ry) ** 2)

    bm = new_bm()
    fl = bm.faces.layers.int["flag"]
    bot = [bm.verts.new((x, y, zc(x, y))) for x, y in outline]
    top = [bm.verts.new((x, y, zc(x, y) + th)) for x, y in outline]
    mt = [bm.verts.new((x * .5, y * .5, zc(x * .5, y * .5) + th)) for x, y in outline]
    mb = [bm.verts.new((x * .5, y * .5, zc(x * .5, y * .5))) for x, y in outline]
    ct, cb = bm.verts.new((0, 0, dome + th)), bm.verts.new((0, 0, dome))
    for k in range(n):
        k2 = (k + 1) % n
        bm.faces.new((top[k], top[k2], mt[k2], mt[k]))[fl] = OUTER
        bm.faces.new((mt[k], mt[k2], ct))[fl] = OUTER
        bm.faces.new((bot[k2], bot[k], mb[k], mb[k2]))[fl] = INNER
        bm.faces.new((mb[k2], mb[k], cb))[fl] = INNER
        bm.faces.new((bot[k], bot[k2], top[k2], top[k]))[fl] = EDGE
    finish(bm, rng, 0.04 * size, min_angle=0.5)
    B.add(bm, {"kind": 0}, world=Matrix.Rotation(rng.uniform(0, TAU), 4, "Z"))
    B.ground()
    return B


# ================================================================ shaders
def parr(c, key, default=0.0):
    return np.array([p.get(key, default) for p in c.parts], dtype=np.float64)[c.gpart]


def part_rng_table(c, seed, shape):
    return np.array([np.random.default_rng(seed + 17 * i).random(shape) for i in range(len(c.parts))])


def shade_ice(c):
    kind, L, R, H = parr(c, "kind"), parr(c, "L", 1), parr(c, "R", 1), parr(c, "H", 1)
    rot0, sides = parr(c, "rot0"), parr(c, "sides", 6)
    Pw, Pl = c.Pw, c.Pl
    shard = kind == 1
    t = np.where(shard, np.clip(Pl[:, 2] / L, 0, 1), 0.12 + np.clip(Pw[:, 2] / (0.2 * H), 0, 1) * 0.25)
    off = c.gpart[:, None] * 3.7
    nz = PT.fbm3((Pw[:, 0] + off[:, 0]) * 0.42, Pw[:, 1] * 0.42, Pw[:, 2] * 0.42, 3, 5)
    v = 0.06 + t * 0.92 + (nz - 0.5) * 0.26 + (c.tone - 0.5) * 0.12 + np.clip(c.Nw[:, 2], 0, 1) * 0.08
    sec = TAU / sides
    fr = np.mod(np.arctan2(Pl[:, 1], Pl[:, 0]) - rot0, sec) / sec
    v -= np.where(shard, (1 - np.abs(2 * fr - 1)) ** 1.5 * 0.1 * (1.1 - t), 0.0)   # darker facet cores
    col = PT.bands(v, [ICE_DEEP, ICE_MID, ICE_LIGHT, ICE_PALE], [0.3, 0.55, 0.8], 0.05)
    tab = part_rng_table(c, 31, (3, 4))[c.gpart]
    for s in range(3):
        h = tab[:, s]
        phi, nzc = h[:, 0] * TAU, (h[:, 1] - 0.5) * 0.5
        nrm = np.stack([np.cos(phi), np.sin(phi), nzc], 1)
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
        d = np.abs(Pl[:, 0] * nrm[:, 0] + Pl[:, 1] * nrm[:, 1] + (Pl[:, 2] - 0.5 * L) * nrm[:, 2] - (h[:, 2] - 0.5) * R * 1.1)
        w = 0.06 * R + 0.02
        m = PT.smoothstep(w, 0.0, d) * PT.smoothstep(0.1, 0.25, t) * PT.smoothstep(0.92, 0.72, t) * shard * (h[:, 3] > 0.3)
        col = PT.mix(col, ICE_STREAK, m * 0.5)
    ch = (c.flag == CHAMFER) & shard
    col[ch] = PT.mix(col[ch], ICE_EDGE, 0.82)
    chb = (c.flag == CHAMFER) & ~shard
    col[chb] = PT.mix(col[chb], ICE_LIGHT, 0.45)
    return {"rgb": col}


def shade_molten(c):
    Pw = c.Pw
    S, cz = parr(c, "S", 1), parr(c, "cz", 0.5)
    off = c.gpart * 5.3
    nz = PT.fbm3(Pw[:, 0] * 1.6 + off, Pw[:, 1] * 1.6, Pw[:, 2] * 1.6, 3, 11)
    v = 0.5 + (nz - 0.5) * 0.55 + (c.tone - 0.5) * 0.24 + c.Nw[:, 2] * 0.1
    col = PT.bands(v, [CH_DARK, CH_MID, CH_LIGHT], [0.42, 0.62], 0.05)
    ch = c.flag == CHAMFER
    col[ch] = PT.mix(col[ch], CH_EDGE, 0.85)
    emis = np.zeros(len(v))
    tab = part_rng_table(c, 77, (3, 5))[c.gpart]
    rel = Pw - np.stack([np.zeros_like(cz), np.zeros_like(cz), cz], 1)
    for k in range(3):
        h = tab[:, k]
        nrm = np.stack([h[:, 0] - 0.5, h[:, 1] - 0.5, (h[:, 2] - 0.5) * 0.6], 1)
        nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-6)
        wob = (PT.fbm3(Pw[:, 0] * 3 + k * 7 + off, Pw[:, 1] * 3, Pw[:, 2] * 3, 2, 13 + k) - 0.5) * 0.18 * S
        d = np.abs((rel * nrm).sum(1) - (h[:, 3] - 0.5) * 0.3 * S + wob)
        mask = PT.smoothstep(0.42, 0.54, PT.fbm3(Pw[:, 0] * 1.2 + k * 13 + off, Pw[:, 1] * 1.2, Pw[:, 2] * 1.2, 2, 19 + k))
        w = 0.03 * S
        col = PT.mix(col, CH_CHAR, PT.smoothstep(w * 2.8, w * 1.7, d) * mask * 0.6)
        glow = PT.smoothstep(w * 1.7, w, d) * mask
        hot = PT.smoothstep(w, w * 0.35, d) * mask
        col = PT.mix(col, SEAM_RED, glow)
        col = PT.mix(col, SEAM_ORANGE, hot)
        col = PT.mix(col, SEAM_CORE, PT.smoothstep(w * 0.45, 0.0, d) * mask)
        emis = np.maximum(emis, np.maximum(hot, glow * 0.45))
    return {"rgb": col, "emis": emis}


def shade_sandstone(c):
    Pw, Pl = c.Pw, c.Pl
    off = c.gpart * 4.1
    nz = PT.fbm3(Pw[:, 0] * 0.9 + off, Pw[:, 1] * 0.9, Pw[:, 2] * 0.9, 3, 23)
    v = (0.52 + (nz - 0.5) * 0.5 + (c.tone - 0.5) * 0.16 + c.Nw[:, 2] * 0.08
         - 0.12 * PT.smoothstep(0.5, 0.0, Pw[:, 2]))
    col = PT.bands(v, [SS_SHADOW, SS_MID, SS_LIGHT], [0.36, 0.64], 0.05)
    ch = c.flag == CHAMFER
    col[ch] = PT.mix(col[ch], SS_EDGE, 0.75)
    g = c.flag == GOLD
    vg = 0.5 + (c.tone - 0.5) * 0.35 + c.Nw[:, 2] * 0.2 + (nz - 0.5) * 0.2
    col[g] = PT.bands(vg[g], [G_DARK, G_MID, G_LIGHT], [0.4, 0.66], 0.05)
    col[c.flag == GOLD_CH] = G_EDGE
    for pid, meta in enumerate(c.parts):
        if meta.get("kind") != 0:
            continue
        idx = np.nonzero((c.gpart == pid) & (c.flag == BODY) & (np.abs(c.Nl[:, 2]) < 0.5))[0]
        if not len(idx):
            continue
        P, N = Pl[idx], c.Nl[idx]
        nh = N[:, :2] / np.maximum(np.linalg.norm(N[:, :2], axis=1, keepdims=True), 1e-9)
        u = P[:, 0] * -nh[:, 1] + P[:, 1] * nh[:, 0]
        side = np.round(np.arctan2(nh[:, 1], nh[:, 0]) / (math.pi / 2)).astype(np.int64) % 4
        z = P[:, 2]
        sub = col[idx]
        for bi, (z0, z1) in enumerate(meta["bands"]):
            zm, bh = 0.5 * (z0 + z1), z1 - z0
            hw = meta["bhw"] + (meta["thw"] - meta["bhw"]) * zm / meta["zt"]
            count = max(1, int(round(2 * hw / (bh * 1.05))))
            cw = 2 * hw / count
            k = np.clip(np.floor((u + hw) / cw), 0, count - 1)
            gs = bh * 0.38
            lx, ly = (u - (-hw + (k + 0.5) * cw)) / gs, (z - zm) / gs
            band = (z > z0) & (z < z1)
            sub = PT.mix(sub, SS_BAND, band * 0.45)
            for zz, sgn in ((z0, -1), (z1, 1)):          # carved border grooves with a lit lip
                sub = PT.mix(sub, SS_GROOVE, PT.smoothstep(0.035, 0.0, np.abs(z - zz)) * 0.85)
                sub = PT.mix(sub, SS_EDGE, PT.smoothstep(0.03, 0.0, np.abs(z - (zz - sgn * 0.05))) * 0.5)
            gid = (side * 5 + bi * 3 + k.astype(np.int64) * 7 + meta["seed"]) % 16
            for gi in np.unique(gid[band]):
                m = band & (gid == gi) & (np.abs(lx) < 1.15) & (np.abs(ly) < 1.15)
                if not m.any():
                    continue
                glyph = PT.GLYPHS[int(gi)]
                aa = 0.06
                c0 = PT.cov(glyph(lx[m], ly[m]), aa)
                c_up = PT.cov(glyph(lx[m] - 0.13, ly[m] + 0.13), aa)
                c_dn = PT.cov(glyph(lx[m] + 0.13, ly[m] - 0.13), aa)
                s2 = PT.mix(sub[m], SS_CARVE, c0)
                s2 = PT.mix(s2, SS_CARVE_DARK, c0 * (1 - c_up))
                s2 = PT.mix(s2, SS_LIGHT, c0 * (1 - c_dn) * 0.7)
                sub[m] = s2
        col[idx] = sub
    return {"rgb": col}


def shade_shell(c):
    Pw = c.Pw
    off = c.gpart * 6.7
    nz = PT.fbm3(Pw[:, 0] * 2.2 + off, Pw[:, 1] * 2.2, Pw[:, 2] * 2.2, 3, 41)
    v = 0.5 + (nz - 0.5) * 0.5 + (c.tone - 0.5) * 0.22 + c.Nw[:, 2] * 0.06
    red = PT.bands(v, [RED_DARK, RED_MID, RED_LIGHT], [0.4, 0.64], 0.05)
    pn = PT.fbm3(Pw[:, 0] * 2.6 + off + 3.3, Pw[:, 1] * 2.6, Pw[:, 2] * 2.6, 3, 91)
    patch = PT.smoothstep(0.55, 0.59, pn)
    red = PT.mix(red, BEIGE_DK, (PT.smoothstep(0.5, 0.55, pn) - patch) * 0.55)
    red = PT.mix(red, BEIGE, patch)
    col = red.copy()
    e = c.flag == EDGE
    col[e] = PT.bands(v[e], [BEIGE_DK, BEIGE_MID], [0.5], 0.06)
    i = c.flag == INNER
    col[i] = PT.bands(v[i], [BEIGE_MID, BEIGE_LT], [0.5], 0.06)
    ch = c.flag == CHAMFER
    col[ch] = PT.mix(red[ch], RED_EDGE, 0.7)
    col[c.flag == EDGE_CH] = BEIGE_LT
    return {"rgb": col}


# ============================================================ UV + software bake
def unwrap(objs, margin):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(50), island_margin=margin, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def raster_tri(x, y, S):
    x0, x1, x2 = x
    y0, y1, y2 = y
    A = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if abs(A) < 1e-8:
        return None
    j0, j1 = max(int(math.floor(min(x))) - 1, 0), min(int(math.ceil(max(x))) + 1, S - 1)
    i0, i1 = max(int(math.floor(min(y))) - 1, 0), min(int(math.ceil(max(y))) + 1, S - 1)
    if j1 < j0 or i1 < i0:
        return None
    jj, ii = np.meshgrid(np.arange(j0, j1 + 1, dtype=np.float64), np.arange(i0, i1 + 1, dtype=np.float64))
    w0 = ((x1 - jj) * (y2 - ii) - (x2 - jj) * (y1 - ii)) / A
    w1 = ((x2 - jj) * (y0 - ii) - (x0 - jj) * (y2 - ii)) / A
    w2 = 1.0 - w0 - w1
    aA = abs(A)
    l0, l1, l2 = math.hypot(x2 - x1, y2 - y1), math.hypot(x0 - x2, y0 - y2), math.hypot(x1 - x0, y1 - y0)
    ok = ((w0 * aA / max(l0, 1e-9) >= -0.75) & (w1 * aA / max(l1, 1e-9) >= -0.75)
          & (w2 * aA / max(l2, 1e-9) >= -0.75))
    if not ok.any():
        return None
    W = np.clip(np.stack([w0[ok], w1[ok], w2[ok]], 1), 0, None)
    W /= W.sum(1, keepdims=True)
    return ii[ok].astype(np.int64), jj[ok].astype(np.int64), W


class Ctx:
    pass


def bake(builds, S, shader):
    pi, pj, tg, bw = [], [], [], []
    Vs, Ps, Ts, flag, tone, gpart, metas = [], [], [], [], [], [], []
    voff = poff = toff = 0
    for B in builds:
        me = B.obj.data
        nl = len(me.loops)
        uv = np.empty(nl * 2)
        me.uv_layers.active.data.foreach_get("uv", uv)
        uv = uv.reshape(-1, 3, 2)
        lv = np.empty(nl, np.int64)
        me.loops.foreach_get("vertex_index", lv)
        assert (lv.reshape(-1, 3) == B.Tk).all(), B.name
        px, py = uv[..., 0] * S - 0.5, (1 - uv[..., 1]) * S - 0.5
        for ti in range(len(B.Tk)):
            r = raster_tri(px[ti], py[ti], S)
            if r is None:
                continue
            pi.append(r[0])
            pj.append(r[1])
            bw.append(r[2])
            tg.append(np.full(len(r[0]), toff + ti, np.int64))
        Vs.append(np.array(B.V))
        Ps.append(np.array(B.P))
        Ts.append(B.Tk + voff)
        flag.append(B.flagk)
        tone.append(B.tonek)
        gpart.append(B.partk + poff)
        metas.extend(B.meta)
        voff += len(B.V)
        poff += len(B.meta)
        toff += len(B.Tk)
    ii, jj, tg, W = np.concatenate(pi), np.concatenate(pj), np.concatenate(tg), np.concatenate(bw)
    V, P, T = np.concatenate(Vs), np.concatenate(Ps), np.concatenate(Ts)
    flag, tone, gpart = np.concatenate(flag), np.concatenate(tone), np.concatenate(gpart)

    def fnorm(X):
        n = np.cross(X[T[:, 1]] - X[T[:, 0]], X[T[:, 2]] - X[T[:, 0]])
        return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)

    tv = T[tg]
    c = Ctx()
    c.Pw = (V[tv] * W[..., None]).sum(1)
    c.Pl = (P[tv] * W[..., None]).sum(1)
    c.Nw, c.Nl = fnorm(V)[tg], fnorm(P)[tg]
    c.flag, c.tone, c.gpart, c.parts = flag[tg], tone[tg] / float(1 << 20), gpart[tg], metas
    out = shader(c)
    covm = np.zeros((S, S))
    covm[ii, jj] = 1.0
    img = np.zeros((S, S, 3))
    img[ii, jj] = np.clip(out["rgb"], 0, 1)
    res = {"rgb": PT.bleed(img, covm, 0.5), "texels": int(covm.sum())}
    if "emis" in out:
        e = np.zeros((S, S, 3))
        e[ii, jj] = np.clip(out["emis"], 0, 1)[:, None]
        res["emis"] = PT.bleed(e, covm, 0.5)
    return res


# ================================================================ materials
def principled(mat):
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            return n
    return mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")


def make_material(name, img_path, rough):
    mat = bpy.data.materials.new(name)
    if mat.node_tree is None:
        mat.use_nodes = True
    nt = mat.node_tree
    bsdf = principled(mat)
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None) or nt.nodes.new("ShaderNodeOutputMaterial")
    if not bsdf.outputs["BSDF"].is_linked:
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(img_path, check_existing=True)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = rough
    return mat


def add_preview_emission(mat, mask_path, strength=4.0):
    nt = mat.node_tree
    bsdf = principled(mat)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(mask_path, check_existing=True)
    tex.image.colorspace_settings.name = "Non-Color"
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = strength
    nt.links.new(tex.outputs["Color"], mul.inputs[0])
    bsdf.inputs["Emission Color"].default_value = (1.0, 0.35, 0.05, 1.0)
    nt.links.new(mul.outputs["Value"], bsdf.inputs["Emission Strength"])


# ================================================================== assets
FAMILIES = {
    "Ice": dict(tex="IceSpikes_BaseColor.png", size=1024, shader=shade_ice, rough=0.45, margin=0.004),
    "Molten": dict(tex="MoltenRock_BaseColor.png", size=512, shader=shade_molten, rough=0.8, margin=0.008,
                   emis="MoltenRock_EmissiveMask.png"),
    "Sandstone": dict(tex="Obelisk_BaseColor.png", size=1024, shader=shade_sandstone, rough=0.9, margin=0.004),
    "Shell": dict(tex="ShellChip_BaseColor.png", size=512, shader=shade_shell, rough=0.7, margin=0.008),
}

FC, DR, PH, KC = "Frost Cyclops", "Dragon", "Pharaoh", "King Crab"
MESHES = [
    # name, family, builder, kwargs, boss, attack, use
    ("IceSpike_A", "Ice", build_ice_spike, dict(H=3, n=3, seed=101), FC, "Stomp",
     "First (smallest) glacier of the travelling ice wall; tween up out of the ground from the base origin."),
    ("IceSpike_B", "Ice", build_ice_spike, dict(H=5, n=4, seed=102), FC, "Stomp", "Ice wall step 2."),
    ("IceSpike_C", "Ice", build_ice_spike, dict(H=7, n=5, seed=103), FC, "Stomp", "Ice wall step 3."),
    ("IceSpike_D", "Ice", build_ice_spike, dict(H=10, n=6, seed=104), FC, "Stomp", "Ice wall step 4."),
    ("IceSpike_E", "Ice", build_ice_spike, dict(H=13, n=7, seed=105), FC, "Stomp",
     "Last and largest glacier; shards lean forward (-Y) along the wall's travel direction."),
    ("IceShard_A", "Ice", build_ice_shard, dict(size=0.5, seed=111), FC, "Stomp / Ground Slam",
     "Small flung debris when glaciers erupt or shatter."),
    ("IceShard_B", "Ice", build_ice_shard, dict(size=0.8, seed=112), FC, "Stomp / Ground Slam", "Flung ice debris."),
    ("IceShard_C", "Ice", build_ice_shard, dict(size=1.2, seed=113, double=True), FC, "Stomp / Ground Slam",
     "Twin-crystal debris chunk."),
    ("MoltenRock_A", "Molten", build_molten_rock, dict(size=0.8, seed=121), DR, "Front Stomp / Tail Whip",
     "Obsidian ejecta with glowing seams; optional EmissiveMask for a SurfaceAppearance emissive setup."),
    ("MoltenRock_B", "Molten", build_molten_rock, dict(size=1.4, seed=122), DR, "Front Stomp / Tail Whip", "Obsidian ejecta."),
    ("MoltenRock_C", "Molten", build_molten_rock, dict(size=2.0, seed=123), DR, "Front Stomp / Tail Whip", "Largest ejecta chunk."),
    ("Obelisk_A", "Sandstone", build_obelisk, dict(H=4.5, seed=131, gold=False, bands=[(0.40, 0.54)]), PH, "Tomb Eruption",
     "Stone spike bursting up through a hieroglyph circle; leans slightly, broken rubble at the foot."),
    ("Obelisk_B", "Sandstone", build_obelisk, dict(H=6.0, seed=132, gold=False, bands=[(0.28, 0.42), (0.58, 0.72)]), PH,
     "Tomb Eruption", "Medium obelisk spike."),
    ("Obelisk_C", "Sandstone", build_obelisk, dict(H=8.0, seed=133, gold=True, bands=[(0.22, 0.34), (0.46, 0.58), (0.70, 0.82)]),
     PH, "Tomb Eruption", "Tallest obelisk spike with the gold pyramidion cap."),
    ("SandstoneRubble_A", "Sandstone", build_rubble, dict(dims=(1.1, 0.85, 0.7), seed=141), PH, "Tomb Eruption",
     "Flung sandstone chunk."),
    ("SandstoneRubble_B", "Sandstone", build_rubble, dict(dims=(1.7, 1.3, 1.05), seed=142), PH, "Tomb Eruption",
     "Larger flung sandstone chunk."),
    ("ShellChip_A", "Shell", build_shell_chip, dict(size=0.6, seed=151), KC, "Claw Crush / Sideways Rush",
     "Small shell fragment knocked off on impact."),
    ("ShellChip_B", "Shell", build_shell_chip, dict(size=0.9, seed=152), KC, "Claw Crush / Sideways Rush", "Shell fragment."),
    ("ShellChip_C", "Shell", build_shell_chip, dict(size=1.3, seed=153), KC, "Claw Crush / Sideways Rush", "Largest shell fragment."),
]

G4 = {"FlipbookLayout": "Grid4x4", "FlipbookMode": "OneShot"}
TEXTURE_USE = {
    "FrostFloor.png": (FC, "Ground Slam / Stomp", "Top-down frosted ground patch under impacts; Decal on a flat part or a SurfaceGui-free Texture.", None),
    "FrostRing.png": (FC, "Ground Slam", "360-degree frost shockwave ring; scale a flat part outward, bright leading edge on the outside.", None),
    "FrostMist_Flipbook4x4.png": (FC, "Ground Slam / Stomp", "Cold mist puff that dissipates over 16 frames.", G4),
    "SnowSparkle.png": (FC, "Ground Slam / Stomp", "Small star/snow sparkle particle.", None),
    "LavaCracks.png": (DR, "Front Stomp", "Top-down glowing lava cracks radiating from the stomp point.", None),
    "ScorchMark.png": (DR, "Fire Breath", "Soft scorched ground patch with ember specks left by the breath cone.", None),
    "Flame_Flipbook4x4.png": (DR, "Fire Breath", "Stylized flame tongue: grows, sways, curls and lifts off over 16 frames.", G4),
    "Ember.png": (DR, "Fire Breath / Front Stomp", "Small ember spark particle.", None),
    "SmokePuff_Flipbook4x4.png": (DR, "Fire Breath / Front Stomp", "Dark-grey smoke puff, rising and dissipating.", G4),
    "HieroglyphCircle.png": (PH, "Tomb Eruption", "Telegraph circle under targeted players: gold rings, 16 glyphs, lapis wash.", None),
    "Hieroglyphs_Flipbook4x4.png": (PH, "Cursed Bolts / Tomb Eruption", "16 single glowing glyphs; one glyph per particle.",
                                    {"FlipbookLayout": "Grid4x4", "FlipbookMode": "Random"}),
    "SandBurst_Flipbook4x4.png": (PH, "Tomb Eruption", "Sand geyser plume: column rises, spreads and falls apart. Bottom-anchored in each frame.", G4),
    "CurseOrb.png": (PH, "Cursed Bolts", "Projectile orb: cyan core, gold rim, soft glow.", None),
    "WaterSplash_Flipbook4x4.png": (KC, "Claw Crush", "Cartoon crown splash: bursts up, throws droplets, collapses. Bottom-anchored.", G4),
    "Bubble.png": (KC, "Bubble Barrage", "Bubble: clear centre, bright rim, curved shine and a dot highlight.", None),
    "SandSpray_Flipbook4x4.png": (KC, "Sideways Rush / Claw Crush", "Beige sand kick sweeping up and to the right; flip with particle rotation or a mirrored emitter.", G4),
    "ShockwaveRing.png": ("Shared", "Any slam", "White tintable ring band, sharp outer edge, soft inner falloff.", None),
    "ImpactStar.png": ("Shared", "Any hit", "Chunky 8-point white impact flash, tintable.", None),
    "DustPuff_Flipbook4x4.png": ("Shared", "Any landing / stomp", "Light-grey tintable dust puff over 16 frames.", G4),
    "IceSpikes_BaseColor.png": (FC, "Stomp", "Shared atlas for IceSpike_A-E and IceShard_A-C (embedded in their FBX).", None),
    "MoltenRock_BaseColor.png": (DR, "Front Stomp / Tail Whip", "Atlas for MoltenRock_A-C.", None),
    "MoltenRock_EmissiveMask.png": (DR, "Front Stomp / Tail Whip", "Optional seam glow mask (white = glowing). Not embedded in the FBX.", None),
    "Obelisk_BaseColor.png": (PH, "Tomb Eruption", "Shared atlas for Obelisk_A-C and SandstoneRubble_A-B.", None),
    "ShellChip_BaseColor.png": (KC, "Claw Crush / Sideways Rush", "Atlas for ShellChip_A-C.", None),
}


# ================================================================ export / check
def select_only(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def export_fbx(objs, path):
    select_only(objs)
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH"}, axis_forward="-Z",
                             axis_up="Y", path_mode="COPY", embed_textures=True, add_leaf_bones=False)


def validate_fbx(path):
    data = open(path, "rb").read()
    before_o, before_m = set(bpy.data.objects), set(bpy.data.meshes)
    before_mat, before_img = set(bpy.data.materials), set(bpy.data.images)
    bpy.ops.import_scene.fbx(filepath=path, axis_forward="-Z", axis_up="Y")
    new = [o for o in bpy.data.objects if o not in before_o]
    tris, dims = 0, [0, 0, 0]
    bpy.context.view_layer.update()
    lo, hi = np.full(3, 1e9), np.full(3, -1e9)
    for o in new:
        if o.type == "MESH":
            o.data.calc_loop_triangles()
            tris += len(o.data.loop_triangles)
            for cn in o.bound_box:
                w = np.array(o.matrix_world @ Vector(cn))
                lo, hi = np.minimum(lo, w), np.maximum(hi, w)
    dims = (hi - lo).tolist()
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    for m in [m for m in bpy.data.meshes if m not in before_m]:
        bpy.data.meshes.remove(m)
    for m in [m for m in bpy.data.materials if m not in before_mat]:
        bpy.data.materials.remove(m)
    for im in [i for i in bpy.data.images if i not in before_img]:
        bpy.data.images.remove(im)
    return {"reimport_triangles": tris, "reimport_size": [round(d, 3) for d in dims],
            "embedded_png_count": data.count(b"\x89PNG\r\n\x1a\n"), "bytes": len(data)}


# ================================================================ previews
FONT = {
    "A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110", "D": "11110 10001 10001 10001 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111", "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110", "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001", "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001", "N": "10001 10001 11001 10101 10011 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110", "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101", "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110", "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 10101 01010", "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 01010 00100 00100 00100 00100", "Z": "11111 00001 00010 00100 01000 10000 11111",
    "0": "01110 10001 10011 10101 11001 10001 01110", "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111", "3": "11110 00001 00001 01110 00001 00001 11110",
    "4": "00010 00110 01010 10010 11111 00010 00010", "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110", "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110", "9": "01110 10001 10001 01111 00001 00010 01100",
    "_": "00000 00000 00000 00000 00000 00000 11111", ".": "00000 00000 00000 00000 00000 01100 01100",
    "-": "00000 00000 00000 11111 00000 00000 00000", ",": "00000 00000 00000 00000 01100 00100 01000",
    "/": "00001 00010 00010 00100 01000 01000 10000", "(": "00010 00100 01000 01000 01000 00100 00010",
    ")": "01000 00100 00010 00010 00010 00100 01000", ":": "00000 01100 01100 00000 01100 01100 00000",
    "+": "00000 00100 00100 11111 00100 00100 00000", "=": "00000 00000 11111 00000 11111 00000 00000", " ": "00000 00000 00000 00000 00000 00000 00000",
}


def draw_text(img, x, y, text, scale=2, color=(0.1, 0.1, 0.12)):
    for ch in text.upper():
        rows = FONT.get(ch, FONT[" "]).split()
        for r, row in enumerate(rows):
            for q, bit in enumerate(row):
                if bit == "1":
                    y0, x0 = y + r * scale, x + q * scale
                    if 0 <= y0 < img.shape[0] - scale and 0 <= x0 < img.shape[1] - scale:
                        img[y0:y0 + scale, x0:x0 + scale, :3] = color
        x += 5 * scale + 1


def load_rgba(path):
    im = bpy.data.images.load(path, check_existing=False)
    w, h = im.size
    px = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(px)
    bpy.data.images.remove(im)
    return px.reshape(h, w, 4)[::-1].astype(np.float64)


def fit_cell(rgba, cell):
    h = rgba.shape[0]
    if h > cell:
        f = h // cell
        a = rgba[..., 3:4]
        c = (rgba[..., :3] * a).reshape(cell, f, cell, f, 3).mean((1, 3))
        a2 = a.reshape(cell, f, cell, f, 1).mean((1, 3))
        return np.dstack([c / np.maximum(a2, 1e-6), a2])
    if h < cell:
        f = cell // h
        return np.repeat(np.repeat(rgba, f, 0), f, 1)
    return rgba


def setup_render(size):
    sc = bpy.context.scene
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            sc.render.engine = eng
            break
        except Exception:
            pass
    sc.render.resolution_x = sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    try:
        sc.eevee.taa_render_samples = 24
    except Exception:
        pass
    world = bpy.data.worlds.new("Sky")
    sc.world = world
    if world.node_tree is None:
        world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.55, 0.62, 0.72, 1.0)
    bg.inputs["Strength"].default_value = 0.6
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = 2.3
    sun.angle = math.radians(8)
    so = bpy.data.objects.new("Sun", sun)
    sc.collection.objects.link(so)
    so.rotation_euler = (math.radians(50), 0, math.radians(-35))
    cam = bpy.data.cameras.new("Cam")
    cam.type = "ORTHO"
    cam.clip_end = 2000
    co = bpy.data.objects.new("Cam", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    return co


def frame_camera(co, obj):
    d = Vector((0.85, -1.3, 0.8)).normalized()
    corners = [obj.matrix_world @ Vector(cn) for cn in obj.bound_box]
    ctr = sum(corners, Vector()) / 8
    rot = (-d).to_track_quat("-Z", "Y")
    co.rotation_euler = rot.to_euler()
    R = rot.to_matrix()
    right, up = R @ Vector((1, 0, 0)), R @ Vector((0, 1, 0))
    xs, ys = [(p - ctr).dot(right) for p in corners], [(p - ctr).dot(up) for p in corners]
    ctr = ctr + right * (max(xs) + min(xs)) / 2 + up * (max(ys) + min(ys)) / 2
    co.data.ortho_scale = max(max(xs) - min(xs), max(ys) - min(ys)) * 1.1
    co.location = ctr + d * (obj.dimensions.length * 2 + 20)


def contact_sheet(mesh_rows, tex_rows, path):
    cell, pad, lab, cols = 256, 14, 34, 8
    W = cols * (cell + pad) + pad
    n_mesh_r, n_tex_r = (len(mesh_rows) + cols - 1) // cols, (len(tex_rows) + cols - 1) // cols
    Hh = 70 + 40 + n_mesh_r * (cell + lab + pad) + 40 + n_tex_r * (cell + lab + pad) + pad
    img = np.ones((Hh, W, 3)) * np.array([0.93, 0.93, 0.92])
    draw_text(img, pad, 18, "BOSS VFX KIT  -  BLENDER-VERIFIED, STUDIO UNTESTED", 3)
    draw_text(img, pad, 50, "1 UNIT = 1 STUD, Z UP, FRONT -Y, ORIGIN AT BASE CENTRE.  GENERATED BY BUILD_VFX_KIT.PY", 2, (0.35, 0.35, 0.38))
    y = 84
    draw_text(img, pad, y, "MESHES  (EEVEE, 3/4 VIEW FROM FRONT-RIGHT)", 2, (0.2, 0.3, 0.5))
    y += 26
    gy = np.linspace(0, 1, cell)[:, None, None]
    panel = np.array([0.80, 0.85, 0.91]) * (1 - gy) + np.array([0.66, 0.72, 0.80]) * gy
    panel = np.broadcast_to(panel, (cell, cell, 3))
    for i, (thumb, l1, l2) in enumerate(mesh_rows):
        r, q = divmod(i, cols)
        x0, y0 = pad + q * (cell + pad), y + r * (cell + lab + pad)
        t = fit_cell(thumb, cell)
        img[y0:y0 + cell, x0:x0 + cell] = panel * (1 - t[..., 3:4]) + t[..., :3] * t[..., 3:4]
        draw_text(img, x0, y0 + cell + 4, l1, 2)
        draw_text(img, x0, y0 + cell + 20, l2, 2, (0.4, 0.4, 0.44))
    y += n_mesh_r * (cell + lab + pad) + 10
    draw_text(img, pad, y, "TEXTURES  (ON MID-GREY CHECKER SO ALPHA READS)", 2, (0.2, 0.3, 0.5))
    y += 26
    yy, xx = np.mgrid[0:cell, 0:cell]
    checker = np.where(((yy // 16 + xx // 16) % 2)[..., None] == 0, 0.47, 0.56) * np.ones(3)
    for i, (tex, l1, l2) in enumerate(tex_rows):
        r, q = divmod(i, cols)
        x0, y0 = pad + q * (cell + pad), y + r * (cell + lab + pad)
        t = fit_cell(tex, cell)
        img[y0:y0 + cell, x0:x0 + cell] = checker * (1 - t[..., 3:4]) + t[..., :3] * t[..., 3:4]
        draw_text(img, x0, y0 + cell + 4, l1, 2)
        draw_text(img, x0, y0 + cell + 20, l2, 2, (0.4, 0.4, 0.44))
    PT.save_png(path, img)


# ==================================================================== main
def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for d in (TEX, FBX, PREV):
        os.makedirs(d, exist_ok=True)
    if "--skip-sprites" not in ARGS:
        PT.paint_all(TEX, log=log)

    builds = {}
    for name, fam, fn, kw, *_ in MESHES:
        B = fn(name, **kw)
        B.family = fam
        B.to_object()
        builds[name] = B
        log("built %-18s %5d tris" % (name, len(B.Tk)))

    mats = {}
    for fam, spec in FAMILIES.items():
        fb = [b for b in builds.values() if b.family == fam]
        unwrap([b.obj for b in fb], spec["margin"])
        res = bake(fb, spec["size"], spec["shader"])
        tex_path = os.path.join(TEX, spec["tex"])
        PT.save_png(tex_path, res["rgb"])
        if "emis" in res:
            PT.save_png(os.path.join(TEX, spec["emis"]), res["emis"])
        spec["texel_coverage"] = round(res["texels"] / spec["size"] ** 2, 3)
        mats[fam] = make_material("%s_Mat" % fam, tex_path, spec["rough"])
        for b in fb:
            b.obj.data.materials.append(mats[fam])
        log("baked %s atlas (%dpx, %.0f%% texels used)" % (fam, spec["size"], 100 * spec["texel_coverage"]))

    manifest_meshes = []
    for name, fam, fn, kw, boss, attack, use in MESHES:
        B = builds[name]
        o = B.obj
        path = os.path.join(FBX, name + ".fbx")
        export_fbx([o], path)
        fbm = os.path.join(FBX, name + ".fbm")
        os.makedirs(fbm, exist_ok=True)
        shutil.copy2(os.path.join(TEX, FAMILIES[fam]["tex"]), fbm)
        check = validate_fbx(path)
        V = np.array(B.V)
        entry = {
            "name": name, "type": "mesh", "file": "exports/fbx/%s.fbx" % name,
            "texture": "textures/" + FAMILIES[fam]["tex"],
            "size_studs": [round(float(x), 3) for x in (V.max(0) - V.min(0))],
            "height_above_ground_studs": round(float(V[:, 2].max()), 3),
            "below_ground_studs": round(float(max(0.0, -V[:, 2].min())), 3),
            "triangles": int(len(B.Tk)), "vertices": int(len(B.V)),
            "boss": boss, "attack": attack, "use": use, "fbx_check": check,
        }
        entry["fbx_check"]["triangles_match"] = check["reimport_triangles"] == entry["triangles"]
        manifest_meshes.append(entry)
        log("exported %-18s tris=%d reimport=%d png=%d" % (name, entry["triangles"], check["reimport_triangles"],
                                                          check["embedded_png_count"]))

    # AllMeshes.fbx: every mesh, spaced out in family rows
    x, row_y, fam_prev, placed = 0.0, 0.0, None, []
    for name, fam, *_ in MESHES:
        o = builds[name].obj
        if fam != fam_prev and fam_prev is not None:
            row_y -= 24.0
            x = 0.0
        fam_prev = fam
        w = o.dimensions.x
        o.location = (x + w / 2, row_y, 0.0)
        x += w + 4.0
        placed.append(o)
    all_path = os.path.join(FBX, "AllMeshes.fbx")
    export_fbx(placed, all_path)
    fbm = os.path.join(FBX, "AllMeshes.fbm")
    os.makedirs(fbm, exist_ok=True)
    for spec in FAMILIES.values():
        shutil.copy2(os.path.join(TEX, spec["tex"]), fbm)
    all_check = validate_fbx(all_path)
    for o in placed:
        o.location = (0.0, 0.0, 0.0)
    log("AllMeshes.fbx reimport tris=%d png=%d" % (all_check["reimport_triangles"], all_check["embedded_png_count"]))

    # previews
    mesh_rows = []
    if "--skip-render" not in ARGS:
        add_preview_emission(mats["Molten"], os.path.join(TEX, FAMILIES["Molten"]["emis"]))
        co = setup_render(512)
        tmp = tempfile.mkdtemp(prefix="vfxkit_")
        objs = [builds[m[0]].obj for m in MESHES]
        for e in manifest_meshes:
            o = builds[e["name"]].obj
            for other in objs:
                other.hide_render = other is not o
            frame_camera(co, o)
            bpy.context.scene.render.filepath = os.path.join(tmp, e["name"] + ".png")
            bpy.ops.render.render(write_still=True)
            mesh_rows.append((load_rgba(os.path.join(tmp, e["name"] + ".png")), e["name"],
                              "H%.1f W%.1f %dT" % (e["height_above_ground_studs"], max(e["size_studs"][:2]), e["triangles"])))
        shutil.rmtree(tmp, ignore_errors=True)
        log("rendered %d thumbnails" % len(mesh_rows))

    manifest_tex, tex_rows = [], []
    names = [t[0] for t in PT.TEXTURES] + [s["tex"] for s in FAMILIES.values()] + [FAMILIES["Molten"]["emis"]]
    kinds = {t[0]: (t[3], t[4]) for t in PT.TEXTURES}
    for n in names:
        path = os.path.join(TEX, n)
        rgba = load_rgba(path)
        h, w = rgba.shape[:2]
        kind, layout = kinds.get(n, ("atlas", None))
        boss, attack, use, roblox = TEXTURE_USE[n]
        e = {"name": n[:-4], "type": kind, "file": "textures/" + n, "pixels": [w, h],
             "alpha": bool(rgba[..., 3].min() < 0.999), "boss": boss, "attack": attack, "use": use}
        if layout:
            e.update({"flipbook_layout": layout, "frames": 16, "frame_pixels": w // 4, "frame_order": "left-to-right, top-to-bottom"})
        if roblox:
            e["roblox"] = roblox
        if kind in ("sprite", "decal", "flipbook") and boss == "Shared":
            e["tintable"] = True
        manifest_tex.append(e)
        tex_rows.append((rgba, n[:-4], "%dPX %s" % (w, (kind + " " + layout) if layout else kind)))

    if mesh_rows:
        contact_sheet(mesh_rows, tex_rows, os.path.join(PREV, "Kit.png"))
        log("wrote previews/Kit.png")

    manifest = {
        "kit": "boss-vfx-kit",
        "status": "Blender-verified, Studio untested",
        "generated": time.strftime("%Y-%m-%d"),
        "generator": "build_vfx_kit.py + paint_textures.py (Blender 5.2 --factory-startup, numpy only)",
        "conventions": {
            "units": "1 Blender unit = 1 stud; author-final size, import at scale 1.0",
            "axes": "Z up, model front faces -Y; FBX written with axis_forward=-Z, axis_up=Y",
            "origin": "base centre; z = 0 is the ground line. Glaciers and obelisks extend slightly below z = 0 so they can rise out of the floor with no gap.",
            "fbx": "one FBX per mesh, textures embedded (path_mode=COPY, embed_textures=True); a <name>.fbm folder beside each holds a plain copy of the same PNG",
            "flipbooks": "4x4 grid in one 1024x1024 PNG, 256px frames, read left-to-right then top-to-bottom (Roblox Grid4x4)",
        },
        "families": {k: {"atlas": "textures/" + v["tex"], "pixels": v["size"], "texel_coverage": v["texel_coverage"]}
                     for k, v in FAMILIES.items()},
        "all_meshes_fbx": {"file": "exports/fbx/AllMeshes.fbx", "check": all_check},
        "assets": manifest_meshes + manifest_tex,
    }
    with open(os.path.join(HERE, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    bad = [e["name"] for e in manifest_meshes if e["triangles"] >= 10000 or not e["fbx_check"]["triangles_match"]
           or e["fbx_check"]["embedded_png_count"] < 1]
    log("manifest written; problems: %s" % (bad or "none"))
    log("DONE")


if __name__ == "__main__":
    main()
