"""Egg kit: the pet egg on its straw-nest pedestal, pre-broken so it can crack open in game.

    blender --background --python build_egg.py -- --quick [--quick-dir=<folder>]   # painted atlas only, 2 shape renders
    blender --background --python build_egg.py -- --preview                         # full bake + renders, no export
    blender --background --python build_egg.py                                      # full build, exports, reports

Self-contained (see the kit README). Style: ../art-references/ART_DIRECTION_USER_2026-09-17.txt
and the egg in ../art-references/egg-merchant/egg-merchant-concept-v1.png (no belt, no medallion).

How the egg is made
* One faceted egg surface: Poisson-spaced points on an egg shape plus the break lines, triangulated
  once (convex hull = Delaunay on a convex surface). The break lines are forced to be mesh edges, so
  the same facets are shared by every piece and the intact egg tiles with zero gap.
* Each piece (bottom cup, four side shards, the crown) is its outer facets + an inner shell 0.12 studs
  in + rim walls along its cut edges. Custom normals come from the analytic egg, so no shading seam.
* Spots and cream are painted in (angle, arc-length) space, so they run straight across the cracks.
* Crack_1 / Crack_2 are thin ribbons on the break lines (+0.02 proud), together tracing every cut.

Everything else follows the chest kit: every board/plate/bolt bevelled on its own, a painted atlas,
then icon lighting (per-facet key x AO x height + cool rim + bevel-edge highlights) baked onto unique
UVs at 1024.
"""
import json
import math
import random
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
TEX = ROOT / "textures"
PREV = ROOT / "previews"
for d in ("textures", "previews", "exports/fbx", "exports/glb"):
    (ROOT / d).mkdir(parents=True, exist_ok=True)

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
QUICK = "--quick" in ARGS
PREVIEW = "--preview" in ARGS
QUICK_DIR = Path(next((a.split("=", 1)[1] for a in ARGS if a.startswith("--quick-dir=")), str(PREV)))

SEED = 20261002
ATLAS = 2048            # painted source sheet (not shipped to Roblox)
BAKE_SIZE = 1024        # shipped texture (Roblox caps at 1024)
GLOW_SRGB = (255, 208, 118)
SHARP = math.radians(30)
TAU = 2 * math.pi
UP = Vector((0, 0, 1))

# ---------------------------------------------------------------------------
# painted atlas layout (u0, u1, v0, v1); v up, image rows bottom-up
# ---------------------------------------------------------------------------
REG = {
    "egg": (0.0, 1.0, 0.5, 1.0),      # outer shell in (angle, arc) space, periodic with a wrap margin
    "inner": (0.0, 0.25, 0.375, 0.5),  # inner shell, same mapping
    "straw": (0.25, 0.75, 0.375, 0.5),  # 8 straw-clump strips, base at v0, tip at v1
    "misc": (0.75, 1.0, 0.375, 0.5),   # flat swatches
    "wood": (0.0, 0.5, 0.0, 0.375),    # 16 board bands
    "dwood": (0.5, 0.75, 0.0, 0.375),  # 8 dark rim bands
    "gold": (0.75, 1.0, 0.0, 0.375),
}
SWATCHES = ("rim", "mound", "gap", "bolt", "core", "spare")
WOOD_BANDS, DWOOD_BANDS, STRAW_VARIANTS = 16, 8, 8
EGG_MARGIN = 0.4        # radians painted past +-pi so faces crossing the back seam stay continuous
WOOD_SPAN = 8.0         # studs across the wood region

PAL = {
    "cream": (239, 226, 200), "cream_light": (249, 242, 224), "cream_dark": (224, 206, 178),
    "teal": (88, 170, 178), "teal_core": (70, 150, 164), "teal_edge": (136, 204, 204),
    "inner": (248, 242, 228), "inner_deep": (247, 228, 188), "rim": (253, 249, 238),
    "straw_base": (150, 84, 32), "straw_mid": (226, 160, 56), "straw_tip": (250, 214, 116),
    "mound": (166, 108, 40),
    "wood": (160, 82, 47), "wood_light": (206, 122, 72), "wood_dark": (108, 52, 31), "gap": (58, 28, 18),
    "dwood": (112, 56, 35), "dwood_light": (150, 84, 52), "dwood_dark": (76, 37, 23),
    "gold": (240, 180, 46), "gold_light": (255, 228, 116), "gold_dark": (192, 122, 26),
    "bolt": (248, 200, 76), "core": (98, 50, 30),
}


def reg_uv(name, x, y):
    u0, u1, v0, v1 = REG[name]
    return (u0 + (u1 - u0) * x, v0 + (v1 - v0) * y)


def swatch_uv(name, x=0.5, y=0.5):
    i = SWATCHES.index(name)
    return reg_uv("misc", (i + 0.2 + 0.6 * x) / len(SWATCHES), 0.1 + 0.8 * y)


# ---------------------------------------------------------------------------
# egg shape: rho(s) = R sqrt(1-s^2)(1 - k s), z = zc + s H/2  (s = -1 bottom .. 1 top)
# ---------------------------------------------------------------------------
EGG_H, EGG_W, EGG_Z0 = 4.6, 3.4, 1.80
EGG_ZC = EGG_Z0 + EGG_H / 2
TAPER = 0.17
SHELL = 0.12
SEG_MAX = 0.30          # break-line vertex spacing (studs)
R_MIN = 0.29            # facet point spacing (studs)


def _rf(s):
    return math.sqrt(max(0.0, 1 - s * s)) * (1 - TAPER * s)


EGG_R = (EGG_W / 2) / max(_rf(-1 + 2 * i / 4000) for i in range(4001))


def egg_r(s):
    return EGG_R * _rf(max(-1.0, min(1.0, s)))


def egg_pt(th, s):
    r = egg_r(s)
    return Vector((r * math.sin(th), -r * math.cos(th), EGG_ZC + s * EGG_H / 2))


def egg_nrm(th, s):
    c = math.sqrt(max(0.0, 1 - s * s))
    nr = EGG_H / 2 * c
    nz = EGG_R * (s * (1 - TAPER * s) + TAPER * (1 - s * s))
    ln = math.hypot(nr, nz)
    nr, nz = nr / ln, nz / ln
    return Vector((nr * math.sin(th), -nr * math.cos(th), nz))


def egg_param(p):
    s = max(-1.0, min(1.0, (p.z - EGG_ZC) / (EGG_H / 2)))
    return math.atan2(p.x, -p.y), s


_S = np.linspace(-1, 1, 4001)
_RR = np.array([egg_r(s) for s in _S])
_A = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(_RR), np.diff(_S) * EGG_H / 2))])
EGG_ARC = float(_A[-1])
_A /= EGG_ARC


def arc_of_s(s):
    return float(np.interp(s, _S, _A))


def r_of_arc(a):
    return egg_r(float(np.interp(a, _A, _S)))


def wrap(a):
    return (a + math.pi) % TAU - math.pi


def radial(th):
    return Vector((math.sin(th), -math.cos(th), 0.0))


def tangent(th):
    return Vector((math.cos(th), math.sin(th), 0.0))


def cyl(r, th, z):
    return Vector((r * math.sin(th), -r * math.cos(th), z))


def newell(pts):
    n = Vector((0.0, 0.0, 0.0))
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n.x += (a.y - b.y) * (a.z + b.z)
        n.y += (a.z - b.z) * (a.x + b.x)
        n.z += (a.x - b.x) * (a.y + b.y)
    return n


def select_only(objs, active=None):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def set_face_attr(obj, name, vals):
    me = obj.data
    a = me.attributes.get(name) or me.attributes.new(name, "FLOAT", "FACE")
    a.data.foreach_set("value", [float(v) for v in vals])


# ---------------------------------------------------------------------------
# mesh builder (from the chest kit): every primitive is its own piece, welded, normals fixed and
# bevelled alone, then all joined. Welding touching pieces first makes the bevel clamp to zero.
# ---------------------------------------------------------------------------
class Builder:
    def __init__(self):
        self.pieces = []
        self.begin()

    def begin(self, chamfer=None):
        self.verts, self.faces, self.uvs = [], [], []
        self.pieces.append((self.verts, self.faces, self.uvs, chamfer))

    def poly(self, pts, uvs):
        base = len(self.verts)
        self.verts += [tuple(p) for p in pts]
        self.faces.append(list(range(base, base + len(pts))))
        self.uvs.append(list(uvs))

    def loft(self, rings, uvf, cap0=True, cap1=True, chamfer=None):
        self.begin(chamfer)
        n = len(rings[0])
        for r in range(len(rings) - 1):
            a, b = rings[r], rings[r + 1]
            for j in range(n):
                jj = (j + 1) % n
                pts = [a[j], a[jj], b[jj], b[j]]
                if (pts[0] - pts[1]).length < 1e-6 and (pts[2] - pts[3]).length < 1e-6:
                    continue
                if (pts[0] - pts[1]).length < 1e-6:
                    pts = [pts[0], pts[2], pts[3]]
                elif (pts[2] - pts[3]).length < 1e-6:
                    pts = [pts[0], pts[1], pts[2]]
                self.poly(pts, [uvf(p) for p in pts])
        if cap0:
            pts = list(reversed(rings[0]))
            self.poly(pts, [uvf(p) for p in pts])
        if cap1:
            pts = list(rings[-1])
            self.poly(pts, [uvf(p) for p in pts])

    def build(self, name, material, bevel=True, default_chamfer=0.05):
        objs = []
        for i, (verts, faces, uvs, chamfer) in enumerate(self.pieces):
            if not faces:
                continue
            mesh = bpy.data.meshes.new(f"{name}_{i}")
            mesh.from_pydata(verts, [], faces)
            mesh.update()
            mesh.materials.append(material)
            layer = mesh.uv_layers.new(name="UVMap")
            for poly, uv in zip(mesh.polygons, uvs):
                for li, u in zip(poly.loop_indices, uv):
                    layer.data[li].uv = u
            mesh.validate()
            obj = bpy.data.objects.new(f"{name}_{i}", mesh)
            bpy.context.collection.objects.link(obj)
            weld_and_bevel(obj, bevel, default_chamfer if chamfer is None else chamfer)
            objs.append(obj)
        select_only(objs)
        if len(objs) > 1:
            bpy.ops.object.join()
        obj = bpy.context.view_layer.objects.active
        obj.name = obj.data.name = name
        for p in obj.data.polygons:
            p.use_smooth = True
        bpy.ops.object.shade_smooth_by_angle(angle=SHARP)
        return obj


def weld_and_bevel(obj, bevel, chamfer):
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    if not bevel or chamfer <= 0:
        return
    xs = [v.co for v in me.vertices]
    span = min(max(c[i] for c in xs) - min(c[i] for c in xs) for i in range(3))
    width = min(chamfer, 0.3 * span) if span > 1e-3 else chamfer
    select_only([obj])
    bev = obj.modifiers.new("Soft_chamfer", "BEVEL")
    bev.width = width
    bev.segments = 1
    bev.limit_method = "ANGLE"
    bev.angle_limit = math.radians(32)
    bpy.ops.object.modifier_apply(modifier=bev.name)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])
    bm.to_mesh(me)
    bm.free()


# ---------------------------------------------------------------------------
# EGG
# ---------------------------------------------------------------------------
def make_lines(rng):
    """Break lines in (angle, height-fraction f). Main zigzag ~57.5%, crown ring ~85.5%,
    four zigzag shard lines between them, starting on main peaks 90 degrees apart."""
    BREAK_F, CROWN_F = 0.575, 0.855
    main = []
    for k in range(16):
        th = -math.pi + (k + 0.5) * math.pi / 8 + rng.uniform(-0.05, 0.05)
        amp = rng.uniform(0.052, 0.072)
        main.append((th, BREAK_F + (amp if k % 2 == 0 else -amp)))
    crown = []
    for j in range(12):
        th = -math.pi + (j + 0.5) * math.pi / 6 + rng.uniform(-0.05, 0.05)
        amp = rng.uniform(0.024, 0.032)
        crown.append((th, CROWN_F + (amp if j % 2 == 0 else -amp)))
    shards = []
    used = set()
    for k in (4, 8, 12, 0):                       # -79, 11, 101, -169 degrees (sector order)
        th0, f0 = main[k]
        j = min((j for j in range(1, 12, 2) if j not in used), key=lambda j: abs(wrap(crown[j][0] - th0)))
        used.add(j)
        th1, f1 = crown[j]
        th1 = th0 + wrap(th1 - th0)
        sign = rng.choice((1, -1))
        pts = [(th0, f0)]
        for i, t in enumerate((1 / 3, 2 / 3)):
            off = 0.15 * sign * (1 if i == 0 else -1)
            pts.append((th0 + (th1 - th0) * t + off, f0 + (f1 - f0) * t + rng.uniform(-0.008, 0.008)))
        pts.append((th1, f1))
        shards.append((k, j, pts))
    return main, crown, shards, BREAK_F


def densify(poly, closed):
    out = []
    n = len(poly)
    for i in (range(n) if closed else range(n - 1)):
        (t0, f0), (t1, f1) = poly[i], poly[(i + 1) % n]
        t1 = t0 + wrap(t1 - t0)
        ln = (egg_pt(t0, 2 * f0 - 1) - egg_pt(t1, 2 * f1 - 1)).length
        k = max(1, math.ceil(ln / SEG_MAX))
        for j in range(k):
            out.append((t0 + (t1 - t0) * j / k, f0 + (f1 - f0) * j / k, j == 0))
    if not closed:
        out.append((poly[-1][0], poly[-1][1], True))
    return out


def hull_faces(points):
    bm = bmesh.new()
    pid = bm.verts.layers.int.new("pid")
    for i, p in enumerate(points):
        v = bm.verts.new(p)
        v[pid] = i
    res = bmesh.ops.convex_hull(bm, input=bm.verts[:])
    off = {v[pid] for v in res["geom_interior"] + res["geom_unused"] if isinstance(v, bmesh.types.BMVert)}
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    faces = [[v[pid] for v in f.verts] for f in bm.faces]
    bm.free()
    return faces, off


def build_egg(mats):
    rng = random.Random(SEED)
    main, crown, shard_defs, break_f = make_lines(rng)
    P, fixed = [], []

    def add(th, f, fx=True):
        P.append((wrap(th), max(-1.0, min(1.0, 2 * f - 1))))
        fixed.append(fx)
        return len(P) - 1

    main_d = densify(main, True)
    main_idx = [add(t, f) for t, f, _ in main_d]
    main_orig = [main_idx[i] for i, d in enumerate(main_d) if d[2]]
    crown_d = densify(crown, True)
    crown_idx = [add(t, f) for t, f, _ in crown_d]
    crown_orig = [crown_idx[i] for i, d in enumerate(crown_d) if d[2]]
    shard_lines = []          # (start k, index list, (fs, ths))
    for k, j, pts in shard_defs:
        dd = densify(pts, False)
        idx = [main_orig[k]] + [add(t, f) for t, f, _ in dd[1:-1]] + [crown_orig[j]]
        shard_lines.append((k, idx, (np.array([d[1] for d in dd]), np.array([d[0] for d in dd]))))
    add(0.0, 0.0)
    add(0.0, 1.0)
    constraints = set()
    for loop in (main_idx, crown_idx):
        for a, b in zip(loop, loop[1:] + loop[:1]):
            constraints.add((min(a, b), max(a, b)))
    for _, idx, _ in shard_lines:
        for a, b in zip(idx, idx[1:]):
            constraints.add((min(a, b), max(a, b)))

    # Poisson-disc facet points on the egg, kept off the break lines
    golden = math.pi * (3 - math.sqrt(5))
    M = 36000
    cand = [(((i * golden) % TAU) - math.pi, 1 - 2 * (i + 0.5) / M) for i in range(M)]
    rng.shuffle(cand)
    cell = R_MIN
    grid = {}

    def gkey(p):
        return (int(math.floor(p.x / cell)), int(math.floor(p.y / cell)), int(math.floor(p.z / cell)))

    def ok(p):
        kx, ky, kz = gkey(p)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for q, rad in grid.get((kx + dx, ky + dy, kz + dz), ()):
                        if (p - q).length < rad:
                            return False
        return True

    for i in range(len(P)):
        p = egg_pt(*P[i])
        grid.setdefault(gkey(p), []).append((p, 0.72 * R_MIN))
    for th, s in cand:
        p = egg_pt(th, s)
        if ok(p):
            grid.setdefault(gkey(p), []).append((p, R_MIN))
            P.append((th, s))
            fixed.append(False)

    # triangulate; force the break lines to be edges
    alive = list(range(len(P)))
    for it in range(10):
        pts3 = [egg_pt(*P[i]) for i in alive]
        faces_l, off = hull_faces(pts3)
        faces = [[alive[i] for i in f] for f in faces_l]
        edges = set()
        for f in faces:
            for a, b in zip(f, f[1:] + f[:1]):
                edges.add((min(a, b), max(a, b)))
        missing = [e for e in constraints if e not in edges]
        if not missing and not off:
            break
        drop = set(alive[i] for i in off if not fixed[alive[i]])
        for a, b in missing:
            pa, pb = egg_pt(*P[a]), egg_pt(*P[b])
            mid, rad = (pa + pb) / 2, 0.62 * (pa - pb).length
            near = [i for i in alive if not fixed[i] and (egg_pt(*P[i]) - mid).length < rad]
            if near:
                drop.update(near)
            else:                                 # split the constraint segment
                ta, fa = P[a][0], (P[a][1] + 1) / 2
                tb, fb = P[a][0] + wrap(P[b][0] - P[a][0]), (P[b][1] + 1) / 2
                m = add((ta + tb) / 2, (fa + fb) / 2)
                alive.append(m)
                constraints.discard((a, b))
                constraints.add((min(a, m), max(a, m)))
                constraints.add((min(m, b), max(m, b)))
                for lst in [main_idx, crown_idx] + [sl[1] for sl in shard_lines]:
                    for q in range(len(lst)):
                        nq = (q + 1) % len(lst)
                        if {lst[q], lst[nq]} == {a, b}:
                            lst.insert(q + 1, m)
                            break
        alive = [i for i in alive if i not in drop]
    else:
        raise SystemExit(f"egg: break lines not resolved, missing {len(missing)}")
    print(f"EGG points {len(alive)} faces {len(faces)} iterations {it}", flush=True)

    centre = Vector((0, 0, EGG_ZC))
    for f in faces:
        ps = [egg_pt(*P[i]) for i in f]
        if newell(ps).dot(sum(ps, Vector()) / 3 - centre) < 0:
            f.reverse()

    # classification helpers (param space)
    MT = np.array([d[0] for d in main_d]); MF = np.array([d[1] for d in main_d])
    CT = np.array([d[0] for d in crown_d]); CF = np.array([d[1] for d in crown_d])
    names = ["Egg_Top_1", "Egg_Top_2", "Egg_Top_3", "Egg_Top_4"]

    def classify(th, f):
        if f < np.interp(th, MT, MF, period=TAU):
            return "Egg_Bottom"
        if f > np.interp(th, CT, CF, period=TAU):
            return "Egg_Top_5"
        lines = [float(np.interp(f, fs, ts)) for _, _, (fs, ts) in shard_lines]
        for i in range(4):
            a, b = lines[i], lines[(i + 1) % 4]
            if (th - a) % TAU < (b - a) % TAU:
                return names[i]
        return names[0]

    # connected components across non-constraint edges
    parent = list(range(len(faces)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    owner = {}
    for fi, f in enumerate(faces):
        for a, b in zip(f, f[1:] + f[:1]):
            e = (min(a, b), max(a, b))
            if e in constraints:
                continue
            if e in owner:
                ra, rb = find(owner[e]), find(fi)
                if ra != rb:
                    parent[ra] = rb
            else:
                owner[e] = fi
    comps = {}
    for fi in range(len(faces)):
        comps.setdefault(find(fi), []).append(fi)
    piece_faces = {}
    for fis in comps.values():
        votes = {}
        for fi in fis:
            c = sum((egg_pt(*P[i]) for i in faces[fi]), Vector()) / 3
            th, s = egg_param(c)
            nm = classify(th, (s + 1) / 2)
            votes[nm] = votes.get(nm, 0) + 1
        nm = max(votes, key=votes.get)
        if nm in piece_faces:
            raise SystemExit(f"egg: piece {nm} split into several components")
        piece_faces[nm] = [faces[fi] for fi in fis]
        if len(votes) > 1:
            print("EGG classify disagreement", votes, flush=True)
    order = ["Egg_Bottom"] + names + ["Egg_Top_5"]
    if sorted(piece_faces) != sorted(order):
        raise SystemExit(f"egg: expected 6 pieces, got {sorted(piece_faces)}")

    # vertex data: un-jittered point, normal, inward jitter (line points barely move)
    on_line = set(main_idx) | set(crown_idx) | {i for _, idx, _ in shard_lines for i in idx}
    jr = random.Random(SEED + 1)
    N, POUT, PIN = {}, {}, {}
    for i in alive:
        th, s = P[i]
        n = egg_nrm(th, s)
        j = 0.0 if abs(s) > 0.9999 else (jr.uniform(-0.012, 0.0) if i in on_line else jr.uniform(-0.045, 0.0))
        N[i] = n
        POUT[i] = egg_pt(th, s) + n * j
        PIN[i] = POUT[i] - n * SHELL

    pieces, loop_normals = {}, {}
    for nm in order:
        fs = piece_faces[nm]
        used = sorted({i for f in fs for i in f})
        lo = {g: k for k, g in enumerate(used)}
        li = {g: k + len(used) for k, g in enumerate(used)}
        verts = [POUT[g] for g in used] + [PIN[g] for g in used]
        polys, kinds, uvs = [], [], []
        ecount = {}
        for f in fs:
            for a, b in zip(f, f[1:] + f[:1]):
                ecount[(min(a, b), max(a, b))] = ecount.get((min(a, b), max(a, b)), 0) + 1
        for f in fs:
            polys.append([lo[g] for g in f]); kinds.append(0); uvs.append(egg_face_uv(P, f, "egg"))
            polys.append([li[g] for g in reversed(f)]); kinds.append(1); uvs.append(list(reversed(egg_face_uv(P, f, "inner"))))
            for a, b in zip(f, f[1:] + f[:1]):
                if ecount[(min(a, b), max(a, b))] == 1:
                    polys.append([lo[a], li[a], li[b], lo[b]]); kinds.append(2)
                    uvs.append([swatch_uv("rim", 0, 1), swatch_uv("rim", 0, 0), swatch_uv("rim", 1, 0), swatch_uv("rim", 1, 1)])
        me = bpy.data.meshes.new(nm)
        me.from_pydata([tuple(v) for v in verts], [], polys)
        me.update()
        layer = me.uv_layers.new(name="UVMap")
        for poly, uv in zip(me.polygons, uvs):
            for lix, u in zip(poly.loop_indices, uv):
                layer.data[lix].uv = u
        me.attributes.new("ekind", "INT", "FACE").data.foreach_set("value", kinds)
        me.validate()
        me.materials.append(mats["atlas"])
        ob = bpy.data.objects.new(nm, me)
        bpy.context.collection.objects.link(ob)
        ek = [0] * len(me.polygons)
        me.attributes["ekind"].data.foreach_get("value", ek)
        nrm_g = [N[g] for g in used] * 2
        ln = []
        for poly, k in zip(me.polygons, ek):
            for vi in poly.vertices:
                if k == 0:
                    ln.append(tuple(nrm_g[vi]))
                elif k == 1:
                    ln.append(tuple(-nrm_g[vi]))
                else:
                    ln.append(tuple(poly.normal))
        loop_normals[nm] = ln
        set_face_attr(ob, "uvw", [{0: 2.1, 1: 0.75, 2: 0.6}[k] for k in ek])
        set_face_attr(ob, "edgemask", [0.0] * len(ek))
        set_face_attr(ob, "soft", [{0: 0.12, 1: 0.3, 2: 0.0}[k] for k in ek])
        fj = [0.0] * len(ek)
        for pi, poly in enumerate(me.polygons):     # per-facet value jitter, keyed by the shared facet
            if ek[pi] == 0:
                key = tuple(sorted(used[v] for v in poly.vertices))
                fj[pi] = random.Random(hash(key) ^ SEED).uniform(-0.045, 0.045)
        set_face_attr(ob, "fjit", fj)
        pieces[nm] = ob
    apply_egg_normals(pieces, loop_normals)

    # glow cracks on the break lines
    pos = lambda lst: [POUT[i] for i in lst]
    nrm = lambda lst: [N[i] for i in lst]
    Mn = len(main_idx)
    p5, p10 = main_idx.index(main_orig[5]), main_idx.index(main_orig[10])
    front = main_idx[p5:p10 + 1]
    rest = [main_idx[(p10 - 2 + t) % Mn] for t in range(((p5 + 2) - (p10 - 2)) % Mn + 1)]
    front_line = next(idx for k, idx, _ in shard_lines if k == 8)
    branch = front_line[:max(2, math.ceil(len(front_line) * 0.55))]
    c1 = [ribbon(pos(front), nrm(front), 0.115, False, taper=(True, True)),
          ribbon(pos(branch), nrm(branch), 0.095, False, taper=(False, True))]
    c2 = [ribbon(pos(rest), nrm(rest), 0.115, False),
          ribbon(pos(crown_idx), nrm(crown_idx), 0.095, True)]
    c2 += [ribbon(pos(idx), nrm(idx), 0.095, False) for _, idx, _ in shard_lines]
    cracks = {"Egg_Crack_1": mesh_from_parts("Egg_Crack_1", c1, mats["glow"]),
              "Egg_Crack_2": mesh_from_parts("Egg_Crack_2", c2, mats["glow"])}
    glow = inner_glow(mats["floor"])
    break_z = sum(POUT[i].z for i in main_idx) / len(main_idx)
    return {"pieces": pieces, "loop_normals": loop_normals, "cracks": cracks, "inner": glow,
            "break_z": break_z, "outer": {nm: sorted({i for f in piece_faces[nm] for i in f}) for nm in order},
            "POUT": POUT}


def apply_egg_normals(pieces, loop_normals):
    for nm, ob in pieces.items():
        me = ob.data
        me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
        me.normals_split_custom_set(loop_normals[nm])


def egg_face_uv(P, f, region):
    """(angle, arc) -> region uv; faces crossing the back seam are unwrapped, pole verts take
    their neighbours' angle."""
    ths, arcs = [], []
    ref = None
    for i in f:
        th, s = P[i]
        arcs.append(arc_of_s(s))
        if abs(s) > 0.9999:
            ths.append(None)
            continue
        if ref is None:
            ref = th
        ths.append(ref + wrap(th - ref))
    known = [t for t in ths if t is not None]
    avg = sum(known) / len(known)
    ths = [avg if t is None else t for t in ths]
    mean = sum(ths) / len(ths)
    if mean > math.pi:
        ths = [t - TAU for t in ths]
    elif mean < -math.pi:
        ths = [t + TAU for t in ths]
    return [reg_uv(region, (t + math.pi + EGG_MARGIN) / (TAU + 2 * EGG_MARGIN), a) for t, a in zip(ths, arcs)]


def ribbon(pos, nrm, width, closed, taper=(False, False), top=0.022, bot=-0.035):
    m = len(pos)
    dist = [0.0]
    for i in range(1, m):
        dist.append(dist[-1] + (pos[i] - pos[i - 1]).length)
    total = dist[-1]
    verts, faces, want = [], [], []
    sides = []
    for i in range(m):
        p, n = pos[i], nrm[i]
        prv = pos[i - 1] if (closed or i > 0) else None
        nxt = pos[(i + 1) % m] if (closed or i < m - 1) else None
        dirs = [(p - prv).normalized()] if prv is not None else []
        if nxt is not None:
            dirs.append((nxt - p).normalized())
        t = sum(dirs, Vector((0, 0, 0)))
        t = (t - n * t.dot(n)).normalized()
        sd = n.cross(t).normalized()
        mit = 1.0
        if len(dirs) == 2:
            d0 = (dirs[0] - n * dirs[0].dot(n)).normalized()
            mit = 1 / max(0.55, t.dot(d0))
        w = width
        if taper[0]:
            w *= min(1.0, 0.15 + dist[i] / 0.35)
        if taper[1]:
            w *= min(1.0, 0.15 + (total - dist[i]) / 0.35)
        hw = w / 2 * mit
        verts += [p + sd * hw + n * top, p - sd * hw + n * top, p - sd * hw + n * bot, p + sd * hw + n * bot]
        sides.append((n, sd, t))
    for i in (range(m) if closed else range(m - 1)):
        j = (i + 1) % m
        a, b = 4 * i, 4 * j
        n = (sides[i][0] + sides[j][0]).normalized()
        sd = (sides[i][1] + sides[j][1]).normalized()
        faces += [[a, b, b + 1, a + 1], [a + 3, b + 3, b, a], [a + 1, b + 1, b + 2, a + 2]]
        want += [n, sd, -sd]
    if not closed:
        faces += [[0, 1, 2, 3], [4 * (m - 1), 4 * (m - 1) + 1, 4 * (m - 1) + 2, 4 * (m - 1) + 3]]
        want += [-sides[0][2], sides[-1][2]]
    out = []
    for f, w in zip(faces, want):
        if newell([verts[k] for k in f]).dot(w) < 0:
            f = list(reversed(f))
        out.append(f)
    return verts, out


def mesh_from_parts(name, parts, mat):
    verts, faces = [], []
    for vs, fs in parts:
        base = len(verts)
        verts += [tuple(v) for v in vs]
        faces += [[base + k for k in f] for f in fs]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    me.materials.append(mat)
    planar_uv(me)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def planar_uv(me):
    xs = [v.co for v in me.vertices]
    lo = Vector((min(c.x for c in xs), min(c.y for c in xs), min(c.z for c in xs)))
    hi = Vector((max(c.x for c in xs), max(c.y for c in xs), max(c.z for c in xs)))
    sz = hi - lo
    layer = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            c = me.vertices[me.loops[li].vertex_index].co
            layer.data[li].uv = ((c.x - lo.x) / max(sz.x, 1e-4) * 0.98 + 0.01,
                                 (c.z - lo.z + 0.3 * (c.y - lo.y)) / max(sz.z + 0.3 * sz.y, 1e-4) * 0.98 + 0.01)


def inner_glow(mat):
    """Soft glowing dome inside the bottom cup; its rim is buried in the shell so no gap shows."""
    s_rim = 2 * 0.43 - 1
    z_rim = EGG_ZC + s_rim * EGG_H / 2
    r_rim = egg_r(s_rim) - 0.16
    prof = [(r_rim, z_rim), (0.78 * r_rim, z_rim + 0.15), (0.45 * r_rim, z_rim + 0.27), (0.0, z_rim + 0.32)]
    n = 16
    verts, faces = [], []
    for r, z in prof[:-1]:
        verts += [tuple(cyl(r, k * TAU / n, z)) for k in range(n)]
    verts.append((0.0, 0.0, prof[-1][1]))
    for ring in range(len(prof) - 2):
        for k in range(n):
            a, b = ring * n + k, ring * n + (k + 1) % n
            faces.append([a, b, b + n, a + n])
    top = len(verts) - 1
    last = (len(prof) - 2) * n
    for k in range(n):
        faces.append([last + k, last + (k + 1) % n, top])
    faces.append(list(reversed(range(n))))
    me = bpy.data.meshes.new("Egg_Inner_Glow")
    me.from_pydata(verts, [], faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bm.to_mesh(me)
    bm.free()
    me.validate()
    me.materials.append(mat)
    planar_uv(me)
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("Egg_Inner_Glow", me)
    bpy.context.collection.objects.link(ob)
    return ob


# ---------------------------------------------------------------------------
# PEDESTAL: two-tier drum of bevelled boards, dark rim lips, gold brackets and hex bolts
# ---------------------------------------------------------------------------
def board_uv(region, nb, band, along, across):
    u0, u1, v0, v1 = REG[region]
    bh = (v1 - v0) / nb
    return (u0 + (u1 - u0) * max(0.0, min(1.0, along / WOOD_SPAN)), v0 + bh * (band + 0.06 + 0.88 * across))


def arc_block(B, r0, r1, a0, a1, z0, z1, nseg, region, nb, band, along0, chamfer):
    B.begin(chamfer)
    ths = [a0 + (a1 - a0) * i / nseg for i in range(nseg + 1)]
    rm = (r0 + r1) / 2

    def al(th):
        return along0 + (th - a0) * rm

    uv = lambda along, across: board_uv(region, nb, band, along, across)
    for i in range(nseg):
        A, Bt = ths[i], ths[i + 1]
        for r in (r1, r0):                                                   # outer, inner
            B.poly([cyl(r, A, z0), cyl(r, Bt, z0), cyl(r, Bt, z1), cyl(r, A, z1)],
                   [uv(al(A), 0), uv(al(Bt), 0), uv(al(Bt), 1), uv(al(A), 1)])
        for z in (z1, z0):                                                   # top, bottom
            B.poly([cyl(r0, A, z), cyl(r0, Bt, z), cyl(r1, Bt, z), cyl(r1, A, z)],
                   [uv(al(A), 0), uv(al(Bt), 0), uv(al(Bt), 1), uv(al(A), 1)])
    for th in (a0, a1):                                                      # ends
        B.poly([cyl(r0, th, z0), cyl(r1, th, z0), cyl(r1, th, z1), cyl(r0, th, z1)],
               [uv(along0, 0), uv(along0 + r1 - r0, 0), uv(along0 + r1 - r0, 1), uv(along0, 1)])


def ring_of_blocks(B, rng, cuts, r0, r1, z0, z1, nseg, region, nb, band0, chamfer=0.05):
    """One row of long curved planks between the given seam angles; rows share seams so they line up."""
    n = len(cuts)
    cuts = list(cuts) + [cuts[0] + TAU]
    for k in range(n):
        g = 0.022 / r1
        a0, a1 = cuts[k] + g / 2, cuts[k + 1] - g / 2
        arc_block(B, r0, r1 + rng.uniform(-0.01, 0.01), a0, a1, z0, z1, nseg, region, nb, (band0 + k) % nb,
                  rng.uniform(0.3, WOOD_SPAN - (a1 - a0) * r1 - 0.4), chamfer)


def gold_uv(p):
    u0, u1, v0, v1 = REG["gold"]
    a = (p.x * 0.8 + p.y * 0.6 + 3.6) / 7.2
    b = (p.z + 0.2) / 2.4
    return (u0 + (u1 - u0) * max(0, min(1, a)), v0 + (v1 - v0) * max(0, min(1, b)))


def bolt(B, th, z, r_surf, size=1.0):
    """Chunky domed hex bolt on the drum, pointing outward."""
    R, T = radial(th), tangent(th)
    sw = swatch_uv("bolt")
    rad = 0.16 * size

    def ring(rd, rr):
        c = R * rd + UP * z
        return [c + T * (rr * math.cos(math.radians(30 + 60 * k))) + UP * (rr * math.sin(math.radians(30 + 60 * k))) for k in range(6)]

    tip = R * (r_surf + 0.14 * size) + UP * z
    rings = [ring(r_surf - 0.03, rad), ring(r_surf + 0.06 * size, rad), ring(r_surf + 0.115 * size, rad * 0.62), [tip] * 6]
    B.loft(rings, lambda p: sw, cap0=True, cap1=False, chamfer=0.022 * size)


BRACKETS = (math.pi / 4, -math.pi / 4, 3 * math.pi / 4, -3 * math.pi / 4)


def offset_profile(pts, off):
    out = []
    for k, (y, z) in enumerate(pts):
        prev = pts[k - 1] if k > 0 else None
        nxt = pts[k + 1] if k < len(pts) - 1 else None
        normals = []
        for a, b in ((prev, (y, z)), ((y, z), nxt)):
            if a and b:
                dy, dz = b[0] - a[0], b[1] - a[1]
                ln = math.hypot(dy, dz)
                normals.append((-dz / ln, dy / ln))
        ny = sum(n[0] for n in normals) / len(normals)
        nz = sum(n[1] for n in normals) / len(normals)
        ln = math.hypot(ny, nz)
        ny, nz = ny / ln, nz / ln
        scale = 1.0
        if len(normals) == 2:
            dot = normals[0][0] * normals[1][0] + normals[0][1] * normals[1][1]
            scale = 1 / max(0.5, math.sqrt((1 + dot) / 2))
        out.append((y + ny * off * scale, z + nz * off * scale))
    return out


def build_pedestal(mat):
    rng = random.Random(SEED + 2)
    B = Builder()
    seams = [k * TAU / 8 for k in range(8)]               # 45-degree planks; seams front/sides/back + under brackets
    rims = [math.pi / 4 + k * TAU / 4 for k in range(4)]   # rim lips: joints hidden under the brackets
    ring_of_blocks(B, rng, rims, 2.60, 2.84, 0.00, 0.20, 5, "dwood", DWOOD_BANDS, 0)                  # plinth
    ring_of_blocks(B, rng, seams, 2.42, 2.72, 0.20, 0.53, 3, "wood", WOOD_BANDS, 0)                   # lower tier, row 1
    ring_of_blocks(B, rng, seams, 2.42, 2.72, 0.53, 0.86, 3, "wood", WOOD_BANDS, 8)                   # lower tier, row 2
    ring_of_blocks(B, rng, rims, 2.48, 2.78, 0.86, 0.98, 5, "dwood", DWOOD_BANDS, 4, chamfer=0.035)   # lip
    ring_of_blocks(B, rng, seams, 2.24, 2.52, 0.98, 1.25, 3, "wood", WOOD_BANDS, 4)                   # upper tier, row 1
    ring_of_blocks(B, rng, seams, 2.24, 2.52, 1.25, 1.52, 3, "wood", WOOD_BANDS, 12)                  # upper tier, row 2
    ring_of_blocks(B, rng, rims, 2.20, 2.60, 1.52, 1.70, 5, "dwood", DWOOD_BANDS, 2)                  # top rim
    # dark core seen through the board grooves
    n = 24
    core_sw = swatch_uv("core")
    B.loft([[cyl(2.21, k * TAU / n, 0.04) for k in range(n)], [cyl(2.21, k * TAU / n, 1.64) for k in range(n)]],
           lambda p: core_sw, chamfer=0.0)
    # gold brackets over both tiers at the diagonals, each with two big bolts
    prof = [(2.70, 0.0), (2.70, 1.00), (2.50, 1.08), (2.50, 1.71), (2.16, 1.71)]
    outer = offset_profile(prof, -0.17)
    widths = [0.80, 0.80, 0.66, 0.66, 0.66]
    for th in BRACKETS:
        R, T = radial(th), tangent(th)
        rings = []
        for (ri, zi), (ro, zo), w in zip(prof, outer, widths):
            rings.append([R * ri - T * (w / 2) + UP * zi, R * ro - T * (w / 2) + UP * zo,
                          R * ro + T * (w / 2) + UP * zo, R * ri + T * (w / 2) + UP * zi])
        B.loft(rings, gold_uv, chamfer=0.045)
        bolt(B, th, 0.50, 2.87, 1.05)
        bolt(B, th, 1.38, 2.67, 0.95)
    for th in (0.0, math.pi / 2, math.pi, -math.pi / 2):    # bolts on the plank corners where seams meet
        bolt(B, th, 0.53, 2.72, 0.85)
    for th in (0.0, math.pi / 2, math.pi, -math.pi / 2):
        bolt(B, th, 1.25, 2.52, 0.8)
    ob = B.build("Pedestal_Base", mat, bevel=True)
    me = ob.data
    uvw = []
    for p in me.polygons:
        c, n = p.center, p.normal
        rho = math.hypot(c.x, c.y)
        nr = (n.x * c.x + n.y * c.y) / max(rho, 1e-6)
        if n.z < -0.5 or (n.z > 0.5 and min(abs(c.z - zz) for zz in (0.53, 0.86, 1.25, 1.52)) < 0.02):
            uvw.append(0.05)                    # undersides and plank tops covered by the row above
        elif n.z > 0.5 and rho < 2.205:
            uvw.append(0.05)                    # core top, under the straw pile
        elif nr < -0.5:
            uvw.append(0.08)                    # inner faces hidden by the core
        elif rho < 2.215 and abs(n.z) < 0.5:
            uvw.append(0.3)                     # core, only seen in grooves
        else:
            uvw.append(1.25)
    set_face_attr(ob, "uvw", uvw)
    set_face_attr(ob, "edgemask", [1.0] * len(me.polygons))
    set_face_attr(ob, "soft", [0.0] * len(me.polygons))
    set_face_attr(ob, "fjit", [0.0] * len(me.polygons))
    return ob


# ---------------------------------------------------------------------------
# NEST: a woven straw rim (twisted bundles spiralling round a torus), irregular tufts of 2-4 thick
# blades, a few strands draped over the drum edge, and a straw mound under the egg
# ---------------------------------------------------------------------------
NEST_R0, NEST_Z0, NEST_A, NEST_B = 1.95, 2.14, 0.50, 0.48     # rim torus: centre radius/height, half-width/half-height


def egg_push(p, margin=0.045):
    """Keep straw outside the egg so the nest hugs it without poking through."""
    if EGG_Z0 - 0.05 < p.z < EGG_Z0 + EGG_H:
        s = (p.z - EGG_ZC) / (EGG_H / 2)
        re = egg_r(s) + margin
        rho = math.hypot(p.x, p.y)
        if rho < re:
            if rho < 1e-6:
                return Vector((re, 0, p.z))
            return Vector((p.x * re / rho, p.y * re / rho, p.z))
    return p


def torus_pt(phi, psi, scale=1.0):
    """psi: 0 outward, 90 up, 180 toward the egg, 270 down."""
    return cyl(NEST_R0 + NEST_A * scale * math.cos(psi), phi, NEST_Z0 + NEST_B * scale * math.sin(psi))


def torus_nrm(phi, psi):
    nr, nz = math.cos(psi) / NEST_A, math.sin(psi) / NEST_B
    ln = math.hypot(nr, nz)
    return radial(phi) * (nr / ln) + UP * (nz / ln)


def strand(B, path, ups, widths, thick, variant, vmap, twist=0.0):
    """Chunky straw bundle along a polyline: flat-topped, keeled cross-section; width 0 = pointed end."""
    m = len(path)
    u0, du = variant / STRAW_VARIANTS, 1 / STRAW_VARIANTS
    xs = (0.0, 0.3, 0.7, 1.0, 0.5)
    rings, ruv = [], []
    for i in range(m):
        p = path[i]
        t = (path[min(i + 1, m - 1)] - path[max(i - 1, 0)]).normalized()
        n = ups[i] - t * ups[i].dot(t)
        n.normalize()
        s = t.cross(n).normalized()
        a = twist * i / max(1, m - 1)
        s, n = s * math.cos(a) + n * math.sin(a), n * math.cos(a) - s * math.sin(a)
        v = 0.02 + 0.96 * vmap(i / (m - 1))
        if widths[i] <= 1e-6:
            rings.append([egg_push(p)])
            ruv.append([reg_uv("straw", u0 + du * 0.5, v)])
            continue
        w, h = widths[i] / 2, thick[i] / 2
        pts = [p - s * w, p - s * (w * 0.5) + n * h, p + s * (w * 0.5) + n * h, p + s * w, p - n * (h * 0.8)]
        rings.append([egg_push(q) for q in pts])
        ruv.append([reg_uv("straw", u0 + du * (0.08 + 0.84 * x), v) for x in xs])
    for i in range(m - 1):
        a, b, ua, ub = rings[i], rings[i + 1], ruv[i], ruv[i + 1]
        for j in range(5):
            jj = (j + 1) % 5
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                B.poly([a[0], b[jj], b[j]], [ua[0], ub[jj], ub[j]])
            elif len(b) == 1:
                B.poly([a[j], a[jj], b[0]], [ua[j], ua[jj], ub[0]])
            else:
                B.poly([a[j], a[jj], b[jj], b[j]], [ua[j], ua[jj], ub[jj], ub[j]])
    for i in (0, m - 1):
        if len(rings[i]) == 5:
            B.poly(rings[i] if i else list(reversed(rings[i])), ruv[i] if i else list(reversed(ruv[i])))


def build_nest(mat):
    rng = random.Random(SEED + 3)
    B = Builder()
    msw = swatch_uv("mound")
    # dark straw core of the rim, seen in the gaps between bundles
    nb_, nt_ = 16, 6
    B.loft([[torus_pt(k * TAU / nb_, q * TAU / nt_, 0.84) for q in range(nt_)] for k in range(nb_ + 1)],
           lambda p: msw, cap0=False, cap1=False)
    # straw mound inside the rim, under the egg
    n = 16
    prof = [(0.8, 2.0), (1.4, 1.93), (1.95, 1.76), (1.95, 1.68)]
    B.loft([[Vector((0, 0, 1.98))] * n] + [[cyl(r, (k + 0.5 * (i % 2)) * TAU / n, z) for k in range(n)] for i, (r, z) in enumerate(prof)],
           lambda p: msw, cap0=False, cap1=True)
    B.begin(0.0)
    # woven rim: twisted bundles spiralling round the torus, five strands deep, pointed straw ends
    bundles = 0
    for ph in range(6):
        for j in range(9):
            phi0 = j * TAU / 9 + ph * 0.13 + rng.uniform(-0.05, 0.05)
            dphi = 0.92 * rng.uniform(0.94, 1.08)
            psi0 = ph * TAU / 6 + rng.uniform(-0.12, 0.12)
            dpsi = 1.7 * rng.uniform(0.9, 1.1)
            ts = (0.0, 0.14, 0.38, 0.62, 0.86, 1.0)
            W, T = 0.48 * rng.uniform(0.92, 1.1), 0.17 * rng.uniform(0.9, 1.1)
            wf = (0.0, 0.62, 1.0, 1.0, 0.62, 0.0)
            strand(B, [torus_pt(phi0 + dphi * t, psi0 + dpsi * t, 0.94) for t in ts],
                   [torus_nrm(phi0 + dphi * t, psi0 + dpsi * t) for t in ts],
                   [W * f for f in wf], [T * max(f, 0.6) for f in wf], rng.randrange(STRAW_VARIANTS),
                   lambda t: 0.3 + 0.7 * abs(2 * t - 1), twist=rng.uniform(-0.5, 0.5))
            bundles += 1
    # irregular tufts of 2-4 thick pointed blades, some lying along the rim
    blades = 0
    NT = 11
    for i in range(NT):
        phi = (i + rng.uniform(0.15, 0.85)) * TAU / NT
        r = rng.random()
        psi = math.radians(rng.uniform(5, 75) if r < 0.5 else (rng.uniform(95, 140) if r < 0.8 else rng.uniform(-25, 5)))
        base = torus_pt(phi, psi, 0.86)
        nt = torus_nrm(phi, psi)
        tang = tangent(phi) * (1 if rng.random() < 0.5 else -1)
        if rng.random() < 0.3:
            main = (tang * rng.uniform(0.9, 1.3) + nt * 0.5 + UP * 0.3).normalized()
        else:
            main = (nt * rng.uniform(0.5, 1.0) + UP * rng.uniform(0.3, 1.0) + tang * rng.uniform(-0.4, 0.4)).normalized()
        for _ in range(rng.randint(2, 4)):
            d = (main + Vector((rng.uniform(-0.35, 0.35), rng.uniform(-0.35, 0.35), rng.uniform(-0.2, 0.3)))).normalized()
            L, W, T = rng.uniform(0.55, 1.0), rng.uniform(0.2, 0.28), 0.08
            droop = rng.uniform(0.05, 0.2)
            ts = (0.0, 0.35, 0.7, 1.0)
            up = UP - d * UP.dot(d)
            up = up.normalized() if up.length > 1e-3 else nt
            strand(B, [base + d * (L * t) - UP * (droop * L * t * t) for t in ts], [up] * 4,
                   [W * f for f in (0.6, 1.0, 0.72, 0.0)], [T * f for f in (0.8, 1.0, 0.8, 0.0)],
                   rng.randrange(STRAW_VARIANTS), lambda t: t, twist=rng.uniform(-0.4, 0.4))
            blades += 1
    # loose strands draped over the drum edge (clear of the gold brackets)
    for phi in (-0.25, 0.30, 1.55, 3.05, -1.75, -2.85):
        dr = rng.choice((1, -1)) * rng.uniform(0.02, 0.04)
        path = [torus_pt(phi, math.radians(55), 0.9), torus_pt(phi + dr, 0.0, 1.02), cyl(2.58, phi + 2 * dr, 1.82),
                cyl(2.71, phi + 3 * dr, 1.64), cyl(2.72, phi + 4 * dr, 1.50), cyl(2.76, phi + 5 * dr, 1.36)]
        R = radial(phi)
        ups = [torus_nrm(phi, math.radians(55)), torus_nrm(phi, 0.0), UP, (UP + R).normalized(), R, R]
        strand(B, path, ups, [0.11, 0.15, 0.15, 0.14, 0.12, 0.0], [0.06, 0.07, 0.07, 0.07, 0.06, 0.0],
               rng.randrange(STRAW_VARIANTS), lambda t: 0.35 + 0.65 * t, twist=rng.uniform(-0.3, 0.3))
    ob = B.build("Pedestal_Nest", mat, bevel=False)
    print(f"NEST bundles {bundles} blades {blades}", flush=True)
    m = len(ob.data.polygons)
    set_face_attr(ob, "uvw", [0.05 if (p.normal.z < -0.5 and p.center.z < 1.72) else 0.6 for p in ob.data.polygons])
    set_face_attr(ob, "edgemask", [0.5] * m)
    set_face_attr(ob, "soft", [0.1] * m)
    set_face_attr(ob, "fjit", [0.0] * m)
    return ob


# ---------------------------------------------------------------------------
# painted atlas (numpy only; Blender has no Pillow)
# ---------------------------------------------------------------------------
def col(c):
    return np.array(c, np.float32) / 255.0


def lerp(a, b, t):
    return a + (b - a) * t[..., None]


def fft_noise(h, w, sx, sy, rng):
    """Smooth periodic noise; sx, sy ~ feature size in pixels. Roughly in [-0.5, 0.5]."""
    n = rng.standard_normal((h, w)).astype(np.float32)
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    g = np.exp(-((fx * sx) ** 2 + (fy * sy) ** 2) * 4.0)
    out = np.real(np.fft.ifft2(np.fft.fft2(n) * g)).astype(np.float32)
    return out / (out.std() * 4 + 1e-9)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def paint_bands(h, w, nb, p, keys, rng):
    wood, light, dark, gap = (col(p[k]) for k in keys)
    rows = (np.arange(h, dtype=np.float32) + 0.5)[:, None]
    bh = h / nb
    band = np.floor(rows / bh).astype(int)[:, 0]
    within = ((rows - band[:, None] * bh) / bh)[:, 0]
    base = np.empty((h, w, 3), np.float32)
    value = rng.uniform(-0.07, 0.07, nb)
    warm = rng.uniform(-0.04, 0.04, nb)
    for k in range(nb):
        base[band == k] = wood * (1 + value[k]) * np.array([1 + warm[k], 1, 1 - warm[k]], np.float32)
    shade = 1 + fft_noise(h, w, 150, 70, rng) * 0.16 + fft_noise(h, w, 50, 30, rng) * 0.05 + fft_noise(h, w, 260, 5, rng) * 0.13
    base *= shade[..., None]
    t = np.broadcast_to(within[:, None], (h, w))
    base = lerp(base, light, (np.clip((t - 0.84) / 0.16, 0, 1) ** 1.5) * 0.35)
    base = lerp(base, dark, (np.clip(1 - t / 0.36, 0, 1) ** 1.6) * 0.40)
    # sparse painted grain dashes and a few soft knots
    for k in range(nb):                               # soft horizontal grain strokes along each plank
        for _ in range(int(rng.integers(6, 10))):
            y = (k + rng.uniform(0.2, 0.86)) * bh
            x0, ln = rng.uniform(-0.1, 0.8) * w, rng.uniform(0.25, 0.6) * w
            thick = rng.uniform(1.6, 3.2) * bh / 48
            r0, r1 = max(0, int(y - 4 * thick)), min(h, int(y + 4 * thick) + 2)
            c0, c1 = max(0, int(x0)), min(w, int(x0 + ln) + 1)
            if r1 <= r0 or c1 <= c0:
                continue
            ys = np.arange(r0, r1, dtype=np.float32)[:, None]
            xs = np.arange(c0, c1, dtype=np.float32)[None, :]
            wave = np.sin((xs - x0) / ln * np.pi * rng.uniform(1.0, 2.5)) * thick * 0.6
            a = np.exp(-((ys - y - wave) / thick) ** 2) * np.sin(np.clip((xs - x0) / ln, 0, 1) * np.pi) * rng.uniform(0.22, 0.36)
            tgt = dark if rng.random() < 0.7 else light
            base[r0:r1, c0:c1] = lerp(base[r0:r1, c0:c1], tgt, a)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    for _ in range(max(3, nb // 3)):
        k = rng.integers(0, nb)
        cy, cx = (k + rng.uniform(0.35, 0.65)) * bh, rng.uniform(0.08, 0.92) * w
        rx, ry = rng.uniform(16, 30), bh * rng.uniform(0.2, 0.3)
        d = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
        base = lerp(base, dark, np.maximum(np.clip(1 - d, 0, 1) ** 0.8 * 0.5, np.clip(1 - np.abs(d - 1.25) / 0.35, 0, 1) * 0.2))
    base[(within < 0.03) | (within > 0.97)] = gap
    return np.clip(base, 0, 1)


def make_spots(rng):
    """Big irregular polygonal spots, placed in physical (arc) space, bigger ones first."""
    sizes = [0.62, 0.58, 0.55, 0.52, 0.50, 0.48, 0.46, 0.44, 0.42, 0.40, 0.40, 0.38, 0.36,
             0.35, 0.34, 0.32, 0.31, 0.30, 0.29, 0.28, 0.27, 0.26]
    spots = []
    for R in sizes:
        for _ in range(4000):
            a = rng.uniform(0.15, 0.86)
            if rng.random() > r_of_arc(a) / (EGG_W / 2):
                continue
            th = rng.uniform(-math.pi, math.pi)
            good = True
            for (t2, a2, R2, _) in spots:
                rr = r_of_arc((a + a2) / 2)
                d = math.hypot(wrap(th - t2) * rr, (a - a2) * EGG_ARC)
                if d < R + R2 + 0.32:
                    good = False
                    break
            if good:
                nv = int(rng.integers(6, 9))
                angs = sorted(TAU * k / nv + rng.uniform(-0.25, 0.25) * TAU / nv for k in range(nv))
                asp, rot = rng.uniform(0.78, 1.18), rng.uniform(0, math.pi)
                poly = []
                for ang in angs:
                    rad = R * rng.uniform(0.80, 1.12)
                    x, y = rad * math.cos(ang), rad * math.sin(ang) * asp
                    poly.append((x * math.cos(rot) - y * math.sin(rot), x * math.sin(rot) + y * math.cos(rot)))
                spots.append((th, a, R, poly))
                break
    return spots


def paint_egg_canvas(Hc, Wp, spots, rng):
    p = PAL
    base = np.broadcast_to(col(p["cream"]), (Hc, Wp, 3)).copy()
    n1 = fft_noise(Hc, Wp, 260, 200, rng)
    n2 = fft_noise(Hc, Wp, 70, 60, rng)
    t = np.clip(n1 * 1.6 + n2 * 0.5, -1, 1)
    base = lerp(base, col(p["cream_light"]), np.clip(t, 0, None) * 0.75)
    base = lerp(base, col(p["cream_dark"]), np.clip(-t, 0, None) * 0.55)
    a = (np.arange(Hc, dtype=np.float32) + 0.5) / Hc
    th = -math.pi + (np.arange(Wp, dtype=np.float32) + 0.5) / Wp * TAU
    for (tc, ac, R, poly) in spots:
        rc = r_of_arc(ac)
        ext = 1.25 * R
        r0, r1 = max(0, int((ac - ext / EGG_ARC) * Hc)), min(Hc, int((ac + ext / EGG_ARC) * Hc) + 2)
        dc = int(ext / rc / TAU * Wp) + 2
        cc = int((tc + math.pi) / TAU * Wp)
        cols = np.arange(cc - dc, cc + dc + 1) % Wp
        X = (((th[cols] - tc + math.pi) % TAU) - math.pi)[None, :] * rc
        Y = ((a[r0:r1] - ac) * EGG_ARC)[:, None]
        X = np.broadcast_to(X, (r1 - r0, len(cols)))
        Y = np.broadcast_to(Y, (r1 - r0, len(cols)))
        inside = np.zeros(X.shape, bool)
        dist = np.full(X.shape, 1e9, np.float32)
        for i in range(len(poly)):
            (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
            cond = (y0 > Y) != (y1 > Y)
            xin = x0 + (Y - y0) * (x1 - x0) / ((y1 - y0) if abs(y1 - y0) > 1e-9 else 1e-9)
            inside ^= cond & (X < xin)
            ex, ey = x1 - x0, y1 - y0
            tt = np.clip(((X - x0) * ex + (Y - y0) * ey) / (ex * ex + ey * ey), 0, 1)
            dist = np.minimum(dist, np.hypot(X - (x0 + tt * ex), Y - (y0 + tt * ey)))
        sd = np.where(inside, dist, -dist)
        alpha = np.clip(sd / 0.009 + 0.5, 0, 1)
        c = lerp(np.broadcast_to(col(p["teal_edge"]), X.shape + (3,)), col(p["teal"]), smoothstep(0.015, 0.075, sd))
        c = lerp(c, col(p["teal_core"]), smoothstep(0.10, 0.36, sd) * 0.75)
        c *= (1 + fft_noise(X.shape[0], X.shape[1], 40, 40, rng) * 0.06)[..., None]
        sub = base[r0:r1][:, cols]
        base[r0:r1, cols] = lerp(sub, c, alpha)
    # near the poles the (angle, arc) map pinches: fade to the row average there
    w = np.maximum(1 - smoothstep(0.03, 0.09, a), smoothstep(0.91, 0.97, a))
    base = lerp(base, np.broadcast_to(base.mean(axis=1, keepdims=True), base.shape), np.broadcast_to(w[:, None], (Hc, Wp)))
    return np.clip(base, 0, 1)


def periodic_region(canvas, width):
    Wp = canvas.shape[1]
    th = -math.pi - EGG_MARGIN + (np.arange(width) + 0.5) / width * (TAU + 2 * EGG_MARGIN)
    idx = np.floor((th + math.pi) / TAU * Wp).astype(int) % Wp
    return canvas[:, idx]


def paint_straw(h, w, rng):
    p = PAL
    out = np.zeros((h, w, 3), np.float32)
    sw = w // STRAW_VARIANTS
    t = ((np.arange(h, dtype=np.float32) + 0.5) / h)[:, None]
    tints = [(1, 1, 1), (1.04, 0.97, 0.88), (0.98, 1.02, 1.06), (1.02, 0.98, 0.92),
             (0.96, 0.98, 1.0), (1.05, 1.0, 0.9), (1.0, 1.03, 1.04), (0.97, 0.95, 0.92)]
    for k in range(STRAW_VARIANTS):
        x = ((np.arange(sw, dtype=np.float32) + 0.5) / sw)[None, :]
        x = (x - 0.08) / 0.84
        tt = np.broadcast_to(t, (h, sw))
        c = lerp(np.broadcast_to(col(p["straw_base"]), (h, sw, 3)), col(p["straw_mid"]), smoothstep(0.0, 0.5, tt))
        c = lerp(c, col(p["straw_tip"]), smoothstep(0.45, 1.0, tt))
        edge = np.abs(x - 0.5) * 2
        c *= (1 - 0.13 * np.clip(edge, 0, 1) ** 2)[..., None]
        c *= (1 + 0.07 * np.clip(1 - np.abs(x - 0.5) / 0.09, 0, 1))[..., None]
        for _ in range(3):
            xc = rng.uniform(0.2, 0.8)
            line = np.clip(1 - np.abs(x - xc) / 0.025, 0, 1) * smoothstep(0.08, 0.25, tt) * (1 - smoothstep(0.7, 0.9, tt))
            c = lerp(c, col(p["straw_base"]), line * 0.18)
        c *= (1 + fft_noise(h, sw, 60, 60, rng) * 0.05)[..., None]
        c *= np.array(tints[k], np.float32)
        out[:, k * sw:(k + 1) * sw] = c
    return np.clip(out, 0, 1)


def paint_atlas(spots):
    rng = np.random.default_rng(SEED)
    S = ATLAS
    img = np.zeros((S, S, 3), np.float32)

    def px(name):
        u0, u1, v0, v1 = REG[name]
        return int(v0 * S), int(v1 * S), int(u0 * S), int(u1 * S)

    r0, r1, c0, c1 = px("egg")
    Wp = int(round((c1 - c0) * TAU / (TAU + 2 * EGG_MARGIN)))
    img[r0:r1, c0:c1] = periodic_region(paint_egg_canvas(r1 - r0, Wp, spots, rng), c1 - c0)

    r0, r1, c0, c1 = px("inner")
    h = r1 - r0
    a = ((np.arange(h, dtype=np.float32) + 0.5) / h)[:, None]
    inner = lerp(np.broadcast_to(col(PAL["inner_deep"]), (h, 256, 3)), col(PAL["inner"]), np.broadcast_to(smoothstep(0.05, 0.5, a), (h, 256)))
    inner *= (1 + fft_noise(h, 256, 60, 50, rng) * 0.04)[..., None]
    img[r0:r1, c0:c1] = periodic_region(inner, c1 - c0)

    r0, r1, c0, c1 = px("straw")
    img[r0:r1, c0:c1] = paint_straw(r1 - r0, c1 - c0, rng)

    r0, r1, c0, c1 = px("misc")
    n = len(SWATCHES)
    sw = (c1 - c0) // n
    for i, name in enumerate(SWATCHES):
        c = col(PAL.get(name, PAL["gap"]) if name != "spare" else PAL["gold"])
        tile = np.broadcast_to(c, (r1 - r0, sw, 3)) * (1 + fft_noise(r1 - r0, sw, 40, 40, rng) * 0.05)[..., None]
        img[r0:r1, c0 + i * sw:c0 + (i + 1) * sw] = tile
    img[r0:r1, c0 + n * sw:c1] = col(PAL["gap"])

    r0, r1, c0, c1 = px("wood")
    img[r0:r1, c0:c1] = paint_bands(r1 - r0, c1 - c0, WOOD_BANDS, PAL, ("wood", "wood_light", "wood_dark", "gap"), rng)
    r0, r1, c0, c1 = px("dwood")
    img[r0:r1, c0:c1] = paint_bands(r1 - r0, c1 - c0, DWOOD_BANDS, PAL, ("dwood", "dwood_light", "dwood_dark", "gap"), rng)

    r0, r1, c0, c1 = px("gold")
    h, w = r1 - r0, c1 - c0
    g = np.broadcast_to(col(PAL["gold"]), (h, w, 3)).copy()
    t = np.clip(fft_noise(h, w, 120, 160, rng) * 1.8 + fft_noise(h, w, 40, 40, rng) * 0.4, -1, 1)
    g = lerp(g, col(PAL["gold_light"]), np.clip(t, 0, None) * 0.6)
    g = lerp(g, col(PAL["gold_dark"]), np.clip(-t, 0, None) * 0.55)
    img[r0:r1, c0:c1] = g
    return np.clip(img, 0, 1)


def save_png(arr, path, alpha=None):
    h, w = arr.shape[:2]
    im = bpy.data.images.new(path.stem, w, h, alpha=alpha is not None)
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = arr[..., :3]
    if alpha is not None:
        rgba[..., 3] = alpha
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = str(path)
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


def load_png(path):
    im = bpy.data.images.load(str(path), check_existing=False)
    w, h = im.size
    buf = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(buf)
    bpy.data.images.remove(im)
    return buf.reshape(h, w, 4)


# ---------------------------------------------------------------------------
# materials and bake
# ---------------------------------------------------------------------------
def srgb_to_linear(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def emit_material(name, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = (0, 0, 0, 1)
    bs.inputs["Emission Color"].default_value = (*[srgb_to_linear(c) for c in GLOW_SRGB], 1)
    bs.inputs["Emission Strength"].default_value = strength
    return m


def painted_material(m, image):
    nt = m.node_tree
    nt.nodes.clear()
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
    tx = nt.nodes.new("ShaderNodeTexImage"); tx.image = image
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bs.inputs["Roughness"].default_value = 0.8
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(uvn.outputs["UV"], tx.inputs["Vector"])
    nt.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
    nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])


BAKE = {
    "key_dir": (-0.45, -0.6, 0.75), "key_lo": 0.70, "key_hi": 1.14,
    "ao_distance": 0.45, "ao_lo": 0.45,
    "height_lo": 0.88, "height_hi": 1.04,
    "rim_dir": (0.75, 0.55, 0.15), "rim": 0.12, "rim_color": (0.45, 0.62, 1.0),
    "edge": 0.60, "edge_radius": 0.06, "edge_tint": (1.0, 0.93, 0.8), "edge_tint_mix": 0.55,
}


def scale_islands(obj, layer_name):
    """Scale each UV island about its centre by its faces' 'uvw' weight (egg shell up, hidden faces down)."""
    me = obj.data
    uv = me.uv_layers[layer_name].data
    w = [0.0] * len(me.polygons)
    me.attributes["uvw"].data.foreach_get("value", w)
    loop_face = [0] * len(me.loops)
    for p in me.polygons:
        for li in p.loop_indices:
            loop_face[li] = p.index
    parent = list(range(len(me.polygons)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    seen = {}
    for p in me.polygons:
        n = len(p.loop_indices)
        for k, li in enumerate(p.loop_indices):
            lj = p.loop_indices[(k + 1) % n]
            va, vb = me.loops[li].vertex_index, me.loops[lj].vertex_index
            key = (min(va, vb), max(va, vb))
            ua = (va, tuple(round(c, 6) for c in uv[li].uv))
            ub = (vb, tuple(round(c, 6) for c in uv[lj].uv))
            sig = frozenset((ua, ub))
            if key in seen:
                other, osig = seen[key]
                if osig == sig:
                    ra, rb = find(other), find(p.index)
                    if ra != rb:
                        parent[ra] = rb
            else:
                seen[key] = (p.index, sig)
    islands = {}
    for p in me.polygons:
        islands.setdefault(find(p.index), []).append(p)
    for faces in islands.values():
        lis = [li for p in faces for li in p.loop_indices]
        cx = sum(uv[li].uv.x for li in lis) / len(lis)
        cy = sum(uv[li].uv.y for li in lis) / len(lis)
        s = sum(w[p.index] for p in faces) / len(faces)
        for li in lis:
            u = uv[li].uv
            uv[li].uv = (cx + (u.x - cx) * s, cy + (u.y - cy) * s)


def bake(mat, objs, top, painted_path, egg):
    P = BAKE
    for o in objs:
        o.data.uv_layers.active = o.data.uv_layers.new(name="BakeUV")
    select_only(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(50), island_margin=0.004, correct_aspect=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    for o in objs:
        scale_islands(o, "BakeUV")
    select_only(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, margin=0.005)
    bpy.ops.object.mode_set(mode="OBJECT")
    apply_egg_normals(egg["pieces"], egg["loop_normals"])

    nt = mat.node_tree
    nt.nodes.clear()
    N = nt.nodes.new
    L = nt.links.new
    uvsrc = N("ShaderNodeUVMap"); uvsrc.uv_map = "UVMap"
    tex = N("ShaderNodeTexImage"); tex.image = bpy.data.images.load(str(painted_path)); tex.interpolation = "Linear"
    L(uvsrc.outputs["UV"], tex.inputs["Vector"])
    geo = N("ShaderNodeNewGeometry")
    tco = N("ShaderNodeTexCoord")

    def attr(name):
        a = N("ShaderNodeAttribute"); a.attribute_type = "GEOMETRY"; a.attribute_name = name
        return a.outputs["Fac"]

    mixn = N("ShaderNodeMix"); mixn.data_type = "VECTOR"
    L(attr("soft"), mixn.inputs[0]); L(geo.outputs["True Normal"], mixn.inputs[4]); L(geo.outputs["Normal"], mixn.inputs[5])
    nn = N("ShaderNodeVectorMath"); nn.operation = "NORMALIZE"; L(mixn.outputs[1], nn.inputs[0])

    def dot_light(direction, normal):
        d = N("ShaderNodeVectorMath"); d.operation = "DOT_PRODUCT"
        L(normal, d.inputs[0])
        d.inputs[1].default_value = Vector(direction).normalized()
        c = N("ShaderNodeClamp")
        L(d.outputs["Value"], c.inputs["Value"])
        return c.outputs["Result"]

    def remap(sock, a, b, lo, hi):
        r = N("ShaderNodeMapRange")
        r.inputs["From Min"].default_value, r.inputs["From Max"].default_value = a, b
        r.inputs["To Min"].default_value, r.inputs["To Max"].default_value = lo, hi
        L(sock, r.inputs["Value"])
        return r.outputs["Result"]

    def mul(a, b):
        m = N("ShaderNodeMath"); m.operation = "MULTIPLY"
        L(a, m.inputs[0]); L(b, m.inputs[1])
        return m.outputs[0]

    key = remap(dot_light(P["key_dir"], nn.outputs["Vector"]), 0, 1, P["key_lo"], P["key_hi"])
    ao = N("ShaderNodeAmbientOcclusion"); ao.samples = 16; ao.inputs["Distance"].default_value = P["ao_distance"]
    aof = remap(ao.outputs["AO"], 0.15, 1.0, P["ao_lo"], 1.0)
    sep = N("ShaderNodeSeparateXYZ"); L(tco.outputs["Object"], sep.inputs["Vector"])
    height = remap(sep.outputs["Z"], 0.0, max(top, 1.0), P["height_lo"], P["height_hi"])
    shade = mul(mul(key, aof), height)
    lit = N("ShaderNodeMix"); lit.data_type = "RGBA"; lit.blend_type = "MULTIPLY"; lit.inputs[0].default_value = 1.0
    L(tex.outputs["Color"], lit.inputs[6])
    grey = N("ShaderNodeCombineColor")
    for i in range(3):
        L(shade, grey.inputs[i])
    L(grey.outputs["Color"], lit.inputs[7])
    rim = remap(dot_light(P["rim_dir"], geo.outputs["True Normal"]), 0.2, 1.0, 0.0, P["rim"])
    rimadd = N("ShaderNodeMix"); rimadd.data_type = "RGBA"; rimadd.blend_type = "ADD"
    L(rim, rimadd.inputs[0]); L(lit.outputs[2], rimadd.inputs[6]); rimadd.inputs[7].default_value = (*P["rim_color"], 1)
    bev = N("ShaderNodeBevel"); bev.samples = 8; bev.inputs["Radius"].default_value = P["edge_radius"]
    ed = N("ShaderNodeVectorMath"); ed.operation = "DOT_PRODUCT"
    L(bev.outputs["Normal"], ed.inputs[0]); L(geo.outputs["True Normal"], ed.inputs[1])
    edge = remap(ed.outputs["Value"], 0.985, 0.80, 0.0, P["edge"])
    edge_up = mul(mul(edge, remap(dot_light((-0.3, -0.35, 0.9), geo.outputs["True Normal"]), 0, 1, 0.45, 1.0)), attr("edgemask"))
    tint = N("ShaderNodeMix"); tint.data_type = "RGBA"; tint.inputs[0].default_value = P["edge_tint_mix"]
    L(tex.outputs["Color"], tint.inputs[6]); tint.inputs[7].default_value = (*P["edge_tint"], 1)
    final = N("ShaderNodeMix"); final.data_type = "RGBA"
    L(edge_up, final.inputs[0]); L(rimadd.outputs[2], final.inputs[6]); L(tint.outputs[2], final.inputs[7])
    j1 = N("ShaderNodeMath"); j1.operation = "ADD"; L(attr("fjit"), j1.inputs[0]); j1.inputs[1].default_value = 1.0
    jc = N("ShaderNodeCombineColor")
    for i in range(3):
        L(j1.outputs[0], jc.inputs[i])
    jit = N("ShaderNodeMix"); jit.data_type = "RGBA"; jit.blend_type = "MULTIPLY"; jit.inputs[0].default_value = 1.0
    L(final.outputs[2], jit.inputs[6]); L(jc.outputs["Color"], jit.inputs[7])
    em = N("ShaderNodeEmission"); L(jit.outputs[2], em.inputs["Color"])
    out = N("ShaderNodeOutputMaterial"); L(em.outputs["Emission"], out.inputs["Surface"])

    img = bpy.data.images.new("egg-kit-baked", BAKE_SIZE, BAKE_SIZE, alpha=False)
    target = N("ShaderNodeTexImage"); target.image = img
    nt.nodes.active = target
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 16
    scene.render.bake.margin = 8
    # open pose for the bake so the inner shell is not baked black
    tops = [o for n, o in egg["pieces"].items() if n.startswith("Egg_Top")]
    for o in tops:
        o.matrix_world = Matrix.Translation((0, 0, 40))
    hidden = list(egg["cracks"].values()) + [egg["inner"]]
    for o in hidden:
        o.hide_render = True
    select_only(objs)
    bpy.ops.object.bake(type="EMIT")
    for o in tops:
        o.matrix_world = Matrix.Identity(4)
    for o in hidden:
        o.hide_render = False
    path = TEX / "egg-kit-baked.png"
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()

    nt.nodes.clear()
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bs.inputs["Roughness"].default_value = 0.78
    bs.inputs["Specular IOR Level"].default_value = 0.15
    tx = nt.nodes.new("ShaderNodeTexImage"); tx.image = img
    nt.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])
    for o in objs:
        o.data.uv_layers.remove(o.data.uv_layers["UVMap"])
        o.data.uv_layers["BakeUV"].name = "UVMap"
        o.data.uv_layers.active = o.data.uv_layers["UVMap"]
    apply_egg_normals(egg["pieces"], egg["loop_normals"])
    return path


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
mats = {"atlas": bpy.data.materials.new("EggKit_Atlas"), "glow": emit_material("EggKit_Glow", 4.0),
        "floor": emit_material("EggKit_InnerGlow", 3.0)}
mats["atlas"].use_nodes = True

pedestal = build_pedestal(mats["atlas"])
nest = build_nest(mats["atlas"])
egg = build_egg(mats)
spots = make_spots(np.random.default_rng(SEED + 5))
print(f"SPOTS {len(spots)}", flush=True)
painted_path = TEX / "egg-kit.png"
save_png(paint_atlas(spots), painted_path)

parts = {"Pedestal_Base": pedestal, "Pedestal_Nest": nest}
parts.update(egg["pieces"])
parts.update(egg["cracks"])
parts["Egg_Inner_Glow"] = egg["inner"]
kinds = {n: "textured" for n in parts}
kinds.update({"Egg_Crack_1": "glow", "Egg_Crack_2": "glow", "Egg_Inner_Glow": "floor"})
textured = [o for n, o in parts.items() if kinds[n] == "textured"]
TOP = max((o.matrix_world @ Vector(c)).z for o in parts.values() for c in o.bound_box)

if QUICK:
    painted_material(mats["atlas"], bpy.data.images.load(str(painted_path)))
else:
    baked_path = bake(mats["atlas"], textured, TOP, painted_path, egg)

for n, o in parts.items():
    o.data.calc_loop_triangles()
tris = {n: len(o.data.loop_triangles) for n, o in parts.items()}
print("TRIS", json.dumps(tris), flush=True)

# ---------------------------------------------------------------------------
# shard fling data and poses
# ---------------------------------------------------------------------------
POUT = egg["POUT"]
shard_info = {}
egg_axis_c = Vector((0, 0, egg["break_z"]))
for nm, ids in egg["outer"].items():
    if not nm.startswith("Egg_Top"):
        continue
    c = sum((POUT[i] for i in ids), Vector()) / len(ids)
    if nm == "Egg_Top_5":
        out = Vector((0.12, -0.08, 1.0)).normalized()
    else:
        h = Vector((c.x, c.y, 0)).normalized()
        out = (h + UP * 0.55).normalized()
    shard_info[nm] = (c, out)


def pose(state):
    """closed | cracked | open"""
    for nm, ob in egg["pieces"].items():
        ob.matrix_world = Matrix.Identity(4)
        if state == "open" and nm in shard_info:
            c, out = shard_info[nm]
            if nm == "Egg_Top_5":
                axis, ang, dist = Vector((1, 0.4, 0)).normalized(), math.radians(-24), 2.3
            else:
                axis, ang, dist = UP.cross(out).normalized(), math.radians(30), 1.55
            ob.matrix_world = Matrix.Translation(c + out * dist) @ Matrix.Rotation(ang, 4, axis) @ Matrix.Translation(-c)
    for nm, ob in egg["cracks"].items():
        ob.hide_render = state != "cracked"
    egg["inner"].hide_render = state != "open"


# ---------------------------------------------------------------------------
# preview renders
# ---------------------------------------------------------------------------
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.view_settings.view_transform = "Standard"
scene.render.resolution_x = scene.render.resolution_y = 1024   # square before framing
scene.render.resolution_percentage = 100
world = bpy.data.worlds.new("Grey")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.40, 0.40, 0.415, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
scene.world = world
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
scene.collection.objects.link(sun)
sun.data.energy = 2.4
sun.data.angle = math.radians(14)
sun.data.color = (1.0, 0.96, 0.9)
sun.rotation_euler = (math.radians(48), 0, math.radians(-38))
cup = bpy.data.objects.new("CupLight", bpy.data.lights.new("CupLight", "POINT"))
scene.collection.objects.link(cup)
cup.location = (0, 0, EGG_Z0 + 0.55 * EGG_H)
cup.data.energy = 140
cup.data.color = tuple(c / 255 for c in GLOW_SRGB)
cup.data.shadow_soft_size = 0.5
bpy.ops.mesh.primitive_circle_add(vertices=64, radius=80, fill_type="NGON", location=(0, 0, 0))
floor = bpy.context.object
floor.name = "Preview_Floor"
fm = bpy.data.materials.new("Preview_Floor")
fm.use_nodes = True
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.425, 0.425, 0.44, 1)
fm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
floor.data.materials.append(fm)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
scene.collection.objects.link(cam)
scene.camera = cam

try:
    ng = bpy.data.node_groups.new("EggBloom", "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = ng.nodes.new("CompositorNodeRLayers")
    gl = ng.nodes.new("CompositorNodeGlare")
    gl.inputs["Type"].default_value = "Bloom"
    gl.inputs["Threshold"].default_value = 1.2
    gl.inputs["Strength"].default_value = 0.7
    go = ng.nodes.new("NodeGroupOutput")
    ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
    ng.links.new(gl.outputs["Image"], go.inputs[0])
    scene.compositing_node_group = ng
    scene.render.use_compositing = True
    BLOOM = True
except Exception as e:  # preview nicety only
    print("BLOOM unavailable:", e, flush=True)
    BLOOM = False


def frame(objs, direction, target, ortho=False, fill=0.86, lens=50):
    d = Vector(direction).normalized()
    cam.data.type = "ORTHO" if ortho else "PERSP"
    cam.data.lens = lens
    pts = [o.matrix_world @ v.co for o in objs for v in list(o.data.vertices)[::2]]
    tgt = Vector(target)
    dist = 30.0 if ortho else 14.0
    cam.data.ortho_scale = 8.0
    for _ in range(5):
        cam.location = tgt + d * dist
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        bpy.context.view_layer.update()
        co = [world_to_camera_view(scene, cam, p) for p in pts]
        x0, x1 = min(c.x for c in co), max(c.x for c in co)
        y0, y1 = min(c.y for c in co), max(c.y for c in co)
        cx, cy = (x0 + x1) / 2 - 0.5, (y0 + y1) / 2 - 0.5
        ext = max(x1 - x0, y1 - y0)
        vis = cam.data.ortho_scale if ortho else 2 * dist * math.tan(cam.data.angle / 2)
        tgt = tgt + cam.matrix_world.to_3x3() @ Vector((cx * vis, cy * vis, 0))
        if ortho:
            cam.data.ortho_scale *= ext / fill
        else:
            dist *= ext / fill


def shoot(path, size=1024):
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


visible = [o for o in parts.values()]
HERO = (-0.6, -1.0, 0.40)
OPEN = (-0.6, -1.0, 0.70)
if QUICK:
    QUICK_DIR.mkdir(parents=True, exist_ok=True)
    pose("cracked")
    frame(visible, HERO, (0, 0, 3.2))
    shoot(QUICK_DIR / "quick-hero.png", 900)
    pose("open")
    cup.hide_render = False
    frame(visible, OPEN, (0, 0, 3.6), fill=0.9)
    shoot(QUICK_DIR / "quick-open.png", 900)
    print("QUICK_DONE", flush=True)
    raise SystemExit(0)

cup.hide_render = True
pose("closed")
frame(visible, HERO, (0, 0, 3.2))
shoot(PREV / "egg-closed.png")
pose("cracked")
shoot(PREV / "egg-cracked.png")
pose("open")
cup.hide_render = False
frame(visible, OPEN, (0, 0, 3.6), fill=0.9)
shoot(PREV / "egg-open.png")
cup.hide_render = True
pose("closed")
frame(visible, (0, -1, 0.0), (0, 0, 3.2), ortho=True, fill=0.84)
shoot(PREV / "egg-front.png")
frame(visible, (1, 0, 0.0), (0, 0, 3.2), ortho=True, fill=0.84)
shoot(PREV / "egg-side.png")

# icon: egg on its nest, no pedestal, transparent
pedestal.hide_render = True
floor.hide_render = True
scene.render.film_transparent = True
scene.render.use_compositing = False
frame([nest] + list(egg["pieces"].values()), (-0.55, -1.0, 0.5), (0, 0, 4.0), ortho=True, fill=0.92)
shoot(PREV / "icon-egg.png", 512)
scene.render.film_transparent = False
scene.render.use_compositing = BLOOM
pedestal.hide_render = False
floor.hide_render = False

# sheet: the five renders at half size, 3 x 2, icon in the last cell
cells = [load_png(PREV / f"egg-{n}.png") for n in ("closed", "cracked", "open", "front", "side")]
icon = load_png(PREV / "icon-egg.png")
sheet = np.zeros((1024, 1536, 3), np.float32)
sheet[:] = cells[0][0, 0, :3]
for i, c in enumerate(cells):
    small = c[:, :, :3].reshape(512, 2, 512, 2, 3).mean(axis=(1, 3))
    r, k = divmod(i, 3)
    sheet[(1 - r) * 512:(2 - r) * 512, k * 512:(k + 1) * 512] = small
a = icon[..., 3:4]
sheet[0:512, 1024:1536] = icon[..., :3] * a + sheet[0:512, 1024:1536] * (1 - a)
save_png(sheet, PREV / "egg-sheet.png")

# ---------------------------------------------------------------------------
# export, reports, .blend
# ---------------------------------------------------------------------------
pose("closed")
for o in parts.values():
    o.hide_render = False
    for an in ("uvw", "edgemask", "soft", "ekind", "fjit"):
        if an in o.data.attributes:
            o.data.attributes.remove(o.data.attributes[an])


def studio(v):
    return [round(-v[0], 4), round(v[2], 4), round(v[1], 4)]


def bbox(o):
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector([min(c[k] for c in cs) for k in range(3)])
    hi = Vector([max(c[k] for c in cs) for k in range(3)])
    return lo, hi


report = {"blender_version": bpy.app.version_string, "units": "studs at final size; import 1:1, do not scale",
          "axes": "Blender Z-up, front -Y; every object origin at world origin with identity transform",
          "texture": f"textures/egg-kit-baked.png ({BAKE_SIZE}x{BAKE_SIZE}, baked icon lighting, UVMap)",
          "painted_source": "textures/egg-kit.png (2048x2048, unbaked)", "parts": {}}
for n, o in parts.items():
    lo, hi = bbox(o)
    uvl = o.data.uv_layers.get("UVMap")
    us = [d.uv.x for d in uvl.data] if uvl else [0]
    vs = [d.uv.y for d in uvl.data] if uvl else [0]
    report["parts"][n] = {"kind": kinds[n], "triangles": tris[n], "vertices": len(o.data.vertices),
                          "bbox_min": [round(v, 4) for v in lo], "bbox_max": [round(v, 4) for v in hi],
                          "dimensions_studs": [round(v, 4) for v in (hi - lo)],
                          "uv_range": [round(min(us), 4), round(max(us), 4), round(min(vs), 4), round(max(vs), 4)]}
egg_names = [n for n in parts if n.startswith("Egg_")]
report["totals"] = {"egg_all_pieces": sum(tris[n] for n in egg_names),
                    "pedestal_and_nest": tris["Pedestal_Base"] + tris["Pedestal_Nest"],
                    "all": sum(tris.values())}

shell = [egg["pieces"][n] for n in egg["pieces"]]
elo = Vector([min(bbox(o)[0][k] for o in shell) for k in range(3)])
ehi = Vector([max(bbox(o)[1][k] for o in shell) for k in range(3)])
report["egg"] = {"height": round(ehi.z - elo.z, 4), "width_x": round(ehi.x - elo.x, 4), "depth_y": round(ehi.y - elo.y, 4),
                 "bottom_z": round(elo.z, 4), "top_z": round(ehi.z, 4), "break_z_mean": round(egg["break_z"], 4)}
install = {"axis": "studio = (-x, z, y) of blender; front = -Z", "parts": {}, "egg": {}, "shards": {},
           "glow_colour": list(GLOW_SRGB),
           "notes": {"textured": "MeshPart TextureID = textures/egg-kit-baked.png",
                     "glow": "Neon in glow_colour; Crack_1 shown at tap 1, Crack_2 added at tap 2, both hidden at the burst",
                     "floor": "Neon in glow_colour; Egg_Inner_Glow shown when the top is gone",
                     "intact": "all Egg_Top_* and Egg_Bottom tile seamlessly at rest (shared vertices, zero gap)"}}
for n, o in parts.items():
    lo, hi = bbox(o)
    install["parts"][n] = {"kind": kinds[n], "centre": studio((lo + hi) / 2),
                           "size": [round(hi.x - lo.x, 4), round(hi.z - lo.z, 4), round(hi.y - lo.y, 4)], "tris": tris[n]}
install["egg"] = {"centre": studio((elo + ehi) / 2), "height": round(ehi.z - elo.z, 4),
                  "break_height": round(egg["break_z"], 4), "top": round(ehi.z, 4), "bottom": round(elo.z, 4)}
for nm, (c, out) in sorted(shard_info.items()):
    so = studio(out)
    ln = math.sqrt(sum(x * x for x in so))
    install["shards"][nm] = {"centroid": studio(c), "outward": [round(x / ln, 4) for x in so]}

if not PREVIEW:
    order = ["Pedestal_Base", "Pedestal_Nest", "Egg_Bottom"] + [f"Egg_Top_{i}" for i in range(1, 6)] + \
            ["Egg_Crack_1", "Egg_Crack_2", "Egg_Inner_Glow"]
    objs = [parts[n] for n in order]
    select_only(objs)
    bpy.ops.export_scene.gltf(filepath=str(ROOT / "exports/glb/egg-kit.glb"), export_format="GLB",
                              use_selection=True, export_apply=True)
    select_only(objs)
    bpy.ops.export_scene.fbx(filepath=str(ROOT / "exports/fbx/egg-kit.fbx"), use_selection=True,
                             object_types={"MESH"}, axis_forward="-Z", axis_up="Y", path_mode="COPY",
                             embed_textures=True, add_leaf_bones=False)
    (ROOT / "polygon-report-egg.json").write_text(json.dumps(report, indent=2))
    (ROOT / "studio-install-data-egg.json").write_text(json.dumps(install, indent=2))
    coll = bpy.data.collections.new("EggKit")
    scene.collection.children.link(coll)
    for o in objs:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
    for im in bpy.data.images:
        if im.source == "FILE" or im.is_dirty:
            im.pack()
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "egg-kit.blend"))

print("EGG_READY", json.dumps(report["totals"]), json.dumps(report["egg"]), flush=True)
