"""Baby Dragon pet (Legendary, strong suit: fire) for the roguelite.

Self-contained generator for background Blender 5.2 (no code imported from other kits).

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 \
        --python build_baby_dragon.py
    ... -- --shape --out <dir>     fast look-dev: per-vertex painted colours, no bake, one shape sheet
    ... -- --quick --out <dir>     1024 bake, a few renders, no exports
    ... -- --no-previews           exports + reports only
    ... -- --no-hero               skip the small Cycles hero render

Coordinates: Blender Z-up, 1 unit = 1 stud (final size, import 1:1), feet on z = 0, the dragon faces
-Y and its own left is +X. Studio = (-x, z, y) of Blender.

Method (same family as the approved Golden Retriever / Turtle / Owl): every rigid part is ONE surface
made from analytic signed-distance volumes joined with smooth unions (real fillets), meshed on a fine
grid, then decimated and relaxed (edge flips + smoothing projected back onto the surface) so the facets stay
broad and even while the designed forms (snout, brows, plates) survive. Colour is painted by 3D position (continuous
over every join and UV seam) and baked to one 1024 atlas with icon lighting (per-facet key, AO, warm
shadow, cool rim). The ember markings are separate thin-shell `_Glow` meshes laid just proud of the
facets (Neon in Studio).
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
ROOT = Path("C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning/blender-pet-kit/baby-dragon")
STEM = "baby-dragon"
PFX = "BabyDragon_"
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
NO_HERO = "--no-hero" in ARGS
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
    print(f"[baby-dragon {time.time() - T0:6.1f}s]", *a, flush=True)


(P_BODY, P_HEAD, P_WINGL, P_WINGR, P_LEGL, P_LEGR, P_TAIL,
 P_GCHEEK, P_GBACK, P_GWINGL, P_GWINGR, P_GTAIL) = range(1, 13)
GLOW_PIDS = (P_GCHEEK, P_GBACK, P_GWINGL, P_GWINGR, P_GTAIL)
P_ARML, P_ARMR = 13, 14


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


def rcone(P, a, b, ra, rb):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ba = b - a
    t = np.clip(((P - a) @ ba) / (ba @ ba), 0.0, 1.0)
    r = ra + (rb - ra) * t
    return np.linalg.norm(P - (a + t[..., None] * ba), axis=-1) - r


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


def extract(grid, F, target=None, name="fused", passes=6):
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
    vo, fo = tidy(grid, F, vo, fo, passes)
    log(name, "isosurface", n_tri, "tris ->", len(fo))
    return vo, fo


def surf_point(G, F, x, z, y0, y1):
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


def frame_at(G, F, x, z, y0, y1, r=None):
    p, n = surf_point(G, F, x, z, y0, y1)
    R = track_axes(n)
    u, v = R[0].copy(), R[1].copy()
    if u[0] < 0:
        u = -u
    if v[2] < 0:
        v = -v
    fr = dict(c=p, u=u, v=v, n=n)
    if r:
        fr["r"] = r
    return fr


def mirror(vf):
    vs, fs = vf
    return vs * np.array((-1.0, 1.0, 1.0)), [tuple(reversed(f)) for f in fs]


# =============================================================================================
# design (studs). Rework after the owner's notes: designed masses, judged by the side silhouette.
# - head: a rounded wedge / bean from the side; a wide boxy rounded muzzle pushes clearly forward,
#   two nostril bumps on top, toothy overbite (modelled fangs) over a cream lower jaw, big round eyes
#   set high and wide under soft brow ridges, thick horns sweeping BACK, small ear fins
# - body: pear that tapers up into a short thick neck, low pot belly with MODELLED cream plates,
#   haunches (thighs fused into the hips with fillets), soft bumps down the spine, no arms
# - wings: big bat wings (about 2x the first pass): thick arm, wrist thumb, 3 finger struts and a thick
#   scalloped membrane; spread and raised so they read from the front, side and back
# - tail: thick root continuing the body line, tapering to a rounded spade with a Neon flame
# - legs: short chunky shins + feet with 3 rounded claws, pivoting at the knee inside the fused thigh
# It is a flyer: the game hovers the rig HOVER_H studs up; the exported rest pose stands on z = 0.
# =============================================================================================
FUSED = {}         # part -> (grid, named fields) for the painter's masks
FACE = {}          # eye / mouth / nose frames for the painter
HOVER_H = 1.5
PIVOT = {
    PFX + "Body": V(0.0, 0.04, 0.72),
    PFX + "Head": V(0.0, -0.13, 1.34),
    PFX + "WingL": V(0.22, 0.16, 1.08),
    PFX + "WingR": V(-0.22, 0.16, 1.08),
    PFX + "LegL": V(0.34, -0.08, 0.36),
    PFX + "LegR": V(-0.34, -0.08, 0.36),
    PFX + "Tail": V(0.0, 0.30, 0.52),
    PFX + "ArmL": V(0.45, -0.30, 0.78),
    PFX + "ArmR": V(-0.45, -0.30, 0.78),
}
H_FINE = 0.02
BELLY_C, BELLY_R = (0.0, -0.10, 0.60), (0.48, 0.46, 0.48)
CHEST_C, CHEST_R = (0.0, -0.06, 1.00), (0.42, 0.36, 0.38)
PL_Z0, PL_SP, PL_N = 0.27, 0.166, 5
HEAD_C, HEAD_R = (0.0, -0.20, 1.80), (0.52, 0.48, 0.44)
HEAD_S = 1.12                              # whole head scaled about the neck pivot (chibi)
HC0 = np.array((0.0, -0.13, 1.34))


def head_world(q):
    return HC0 + (np.asarray(q, float) - HC0) * HEAD_S


def head_design(p):
    return HC0 + (p - HC0) / HEAD_S
CLAW_FOOT = [(dx, -0.37, 0.07) for dx in (-0.085, 0.0, 0.085)]
LEG_X = 0.35
W0 = np.array((0.22, 0.16, 1.08))
WING_EL, WING_SW = math.radians(40), math.radians(28)
WING_PTS = dict(root=(0.0, 0.0), wrist=(0.55, -0.06), tip1=(1.30, 0.06), tip2=(1.08, 0.60), tip3=(0.64, 0.84), back=(0.06, 0.52))


def rbox(P, c, b, r):
    q = np.abs(P - np.asarray(c, float)) - (np.asarray(b, float) - r)
    return np.linalg.norm(np.maximum(q, 0.0), axis=-1) + np.minimum(np.max(q, axis=-1), 0.0) - r


ARM_SH = np.array((0.38, -0.12, 0.98))
ARM_E = np.array((0.45, -0.30, 0.78))


def upper_arm(P, s):
    """Body-owned chubby shoulder + upper arm ending in a round elbow mass that hides the forearm's elbow ball."""
    m = np.array((s, 1.0, 1.0))
    a = smin(ell(P, ARM_SH * m, (0.19, 0.19, 0.20)), rcone(P, ARM_SH * m, ARM_E * m, 0.18, 0.17), 0.05)
    return smin(a, ell(P, ARM_E * m, (0.195, 0.195, 0.195)), 0.05)


def back_point(G, F, x, z, y0=0.95, y1=-0.3):
    p, _ = surf_point(G, F, x, z, y0, y1)
    return p


def body_field(h):
    G = Grid((-0.85, -0.80, 0.05), (0.85, 0.85, 1.50), h, sym_x=True)
    P = G.P
    X, Y, Z = P[..., 0], P[..., 1], P[..., 2]
    belly = ell(P, BELLY_C, BELLY_R)
    chest = ell(P, CHEST_C, CHEST_R)
    F = smin(belly, chest, 0.20)                                               # pear: pot belly low, narrower chest
    F = smin(F, ell(P, (0.0, 0.08, 0.74), (0.38, 0.36, 0.42)), 0.15)           # rounded back
    F = smin(F, rcone(P, (0.0, -0.07, 1.02), (0.0, -0.18, 1.34), 0.30, 0.27), 0.15)   # thick chubby neck, no pinch
    F = smin(F, ell(P, (0.0, -0.28, 1.16), (0.28, 0.24, 0.24)), 0.15)          # throat: chin -> chest -> belly in one curve
    thigh = np.minimum(ell(P, (0.33, 0.0, 0.42), (0.25, 0.31, 0.28)), ell(P, (-0.33, 0.0, 0.42), (0.25, 0.31, 0.28)))
    F = smin(F, thigh, 0.14)                                                   # thick thighs tucked under, wide fillets
    F = smin(F, ell(P, (0.0, 0.34, 0.52), (0.23, 0.28, 0.23)), 0.15)          # tail root continues the body line
    shoulder = np.minimum(upper_arm(P, 1), upper_arm(P, -1))
    F = smin(F, shoulder, 0.12)                                                # round shoulders + upper arms melt into the torso
    # soft bumps down the spine, sitting on the surface
    bumps = None
    for z, sc in ((1.26, 0.85), (1.06, 1.0), (0.86, 1.0), (0.66, 0.85)):
        bp = back_point(G, F, 0.0, z)
        b = ell(P, (0.0, bp[1] - 0.035, z), (0.085 * sc, 0.11 * sc, 0.12 * sc))
        bumps = b if bumps is None else np.minimum(bumps, b)
    F = smin(F, bumps, 0.05)
    plates, shell = plates_sdf(P)                                              # painter masks; plates are meshed separately
    return G, F, dict(bumps=bumps, plates=plates, shell=shell, thigh=thigh, shoulder=shoulder)


def plates_sdf(P):
    """Five clean belly bands: a 0.045-stud-proud shell sliced into bands with rounded rims, hollowed inside the body."""
    X, Y, Z = P[..., 0], P[..., 1], P[..., 2]
    shell = smin(ell(P, BELLY_C, np.array(BELLY_R) + 0.045), ell(P, CHEST_C, np.array(CHEST_R) + 0.045), 0.20)
    inner = smin(ell(P, BELLY_C, np.array(BELLY_R) - 0.05), ell(P, CHEST_C, np.array(CHEST_R) - 0.05), 0.20)
    zz = Z + 0.30 * X ** 2
    pl = None
    for k in range(PL_N):
        band = smax(shell, np.abs(zz - (PL_Z0 + (k + 0.5) * PL_SP)) - (PL_SP / 2 - 0.026), 0.03)
        pl = band if pl is None else np.minimum(pl, band)
    pl = smax(pl, np.abs(X) - 0.32, 0.045)
    pl = smax(pl, Y + 0.05, 0.03)
    pl = smax(pl, -inner, 0.01)
    return pl, shell


PLATE_NF = 0
PLATE_FULL = None


def build_plates():
    """Each plate is a lofted band laid on the body surface: flat top 0.045 proud, quarter-circle rounded rims that dive
    0.02 under the skin, rounded lateral ends that sink into the body. All boundaries are hidden inside the body."""
    G, fl = FUSED["body"]
    F = fl["F"]
    xs = np.linspace(-0.34, 0.34, 13)
    ts = [-1.0, -0.93, -0.82, -0.66, -0.3, 0.3, 0.66, 0.82, 0.93, 1.0]
    hb = PL_SP / 2 - 0.012
    vs, fs = [], []
    nt = len(ts)
    for k in range(PL_N):
        zc = PL_Z0 + (k + 0.5) * PL_SP
        base = len(vs)
        for x in xs:
            ex = float(sstep(0.0, 1.0, np.array([(0.34 - abs(x)) / 0.07]))[0])
            for t in ts:
                z = zc + t * hb - 0.30 * x * x
                p_, n_ = surf_point(G, F, x, z, -1.0, 0.3)
                at = abs(t)
                prof = 0.045 if at <= 0.62 else -0.02 + 0.065 * math.sqrt(max(0.0, 1 - ((at - 0.62) / 0.38) ** 2))
                vs.append(p_ + n_ * (-0.02 + (prof + 0.02) * ex))
        for i in range(len(xs) - 1):
            for j in range(nt - 1):
                a = base + i * nt + j
                b = a + nt
                fs.append((a, b, b + 1, a + 1))
    vs = np.array(vs)
    f0 = fs[len(fs) // 2]
    if np.cross(vs[f0[1]] - vs[f0[0]], vs[f0[2]] - vs[f0[0]])[1] > 0:
        fs = [tuple(reversed(f)) for f in fs]
    global PLATE_NF
    PLATE_NF = len(fs)
    log("plates", len(fs), "quads (lofted, no decimation)")
    return vs, fs


def horn_sdf(P, s):
    h0, h1, h2 = (s * 0.22, -0.12, 2.10), (s * 0.29, 0.14, 2.24), (s * 0.33, 0.42, 2.25)
    return smin(rcone(P, h0, h1, 0.115, 0.08), rcone(P, h1, h2, 0.08, 0.045), 0.03)


def head_field(h, store):
    frames = {}
    G = Grid((-0.95, -1.25, 1.05), (0.95, 0.75, 2.55), h, sym_x=True)
    P = head_design(G.P)
    cran = ell(P, HEAD_C, HEAD_R)
    base = smin(cran, ell(P, (0.0, 0.04, 1.64), (0.32, 0.32, 0.30)), 0.15)     # back of the head into the neck: bean
    base = smin(base, ell(P, (0.0, -0.12, 1.36), (0.24, 0.24, 0.22)), 0.10)    # neck plug (hidden joint)
    for s in (1, -1):
        base = smin(base, ell(P, (s * 0.33, -0.46, 1.62), (0.18, 0.17, 0.15)), 0.10)   # cheeks
    base = smin(base, ell(P, (0.0, -0.18, 1.38), (0.30, 0.30, 0.24)), 0.10)    # thick neck plug under the jaw
    muzzle = rbox(P, (0.0, -0.72, 1.62), (0.32, 0.26, 0.15), 0.12)             # long wide rounded upper snout
    jaw = smin(rbox(P, (0.0, -0.66, 1.385), (0.30, 0.25, 0.115), 0.11),        # BIG rounded lower jaw, as far forward
               ell(P, (0.0, -0.70, 1.31), (0.25, 0.22, 0.12)), 0.06)             # chunky round chin
    nost = np.minimum(ell(P, (0.11, -0.86, 1.765), (0.07, 0.065, 0.05)), ell(P, (-0.11, -0.86, 1.765), (0.07, 0.065, 0.05)))
    Pb = P.copy()
    Pb[..., 2] = Pb[..., 2] - 0.5 * Pb[..., 0] ** 2                             # grin curves up at the corners
    cav = ell(Pb, (0.0, -0.95, 1.495), (0.31, 0.17, 0.05))                     # open mouth
    tongue = ell(P, (0.0, -0.84, 1.455), (0.13, 0.12, 0.035))
    teeth = None
    for x, z0, z1 in ((0.09, 1.55, 1.505), (0.20, 1.55, 1.51), (-0.09, 1.55, 1.505), (-0.20, 1.55, 1.51),
                      (0.14, 1.44, 1.49), (-0.14, 1.44, 1.49)):
        t_ = rcone(P, (x, -0.925, z0 + 0.5 * x * x), (x, -0.935, z1 + 0.5 * x * x), 0.032, 0.02)
        teeth = t_ if teeth is None else np.minimum(teeth, t_)
    brow = np.minimum(ell(P, (0.25, -0.50, 2.05), (0.16, 0.085, 0.06), axis=(0.9, 0.0, 0.3)),
                      ell(P, (-0.25, -0.50, 2.05), (0.16, 0.085, 0.06), axis=(-0.9, 0.0, 0.3)))
    F = smin(base, muzzle, 0.14)
    F = smin(F, jaw, 0.10)
    F = smin(F, nost, 0.04)
    F = smin(F, brow, 0.07)
    F = smax(F, -cav, 0.025)
    F = smin(F, tongue, 0.02)
    F = smin(F, teeth, 0.012)
    if store:
        for name, s in (("eyeL", 1), ("eyeR", -1)):
            ew = head_world((s * 0.27, 0.0, 1.86))
            frames[name] = frame_at(G, smin(base, muzzle, 0.14), ew[0], ew[2], -1.4, -0.1, (0.165 * HEAD_S, 0.18 * HEAD_S))
        frames["mouth"] = frame_at(G, F, 0.0, head_world((0, 0, 1.495))[2], -1.4, -0.3)
    horn = np.minimum(horn_sdf(P, 1), horn_sdf(P, -1))
    fin = np.minimum(ell(P, (0.50, 0.04, 1.86), (0.05, 0.10, 0.15), axis=(1.0, 0.8, 0.2)),
                     ell(P, (-0.50, 0.04, 1.86), (0.05, 0.10, 0.15), axis=(-1.0, 0.8, 0.2)))
    F = smin(F, horn, 0.06)
    F = smin(F, fin, 0.05)
    if store:
        FACE.update(frames)
    S = HEAD_S
    return G, F * S, dict(horn=horn * S, fin=fin * S, muzzle=muzzle * S, jaw=jaw * S, teeth=teeth * S, brow=brow * S, nost=nost * S,
                          cav=cav * S, tongue=tongue * S)


def wing_frame():
    d = np.array((math.cos(WING_EL) * math.cos(WING_SW), math.cos(WING_EL) * math.sin(WING_SW), math.sin(WING_EL)))
    e0 = np.array((0.0, 0.25, -1.0))
    e = e0 - d * (e0 @ d)
    e /= np.linalg.norm(e)
    n = np.cross(d, e)
    return d, e, n / np.linalg.norm(n)


def sd_poly(u, v, pts):
    pts = [np.array(p, float) for p in pts]
    d = (u - pts[0][0]) ** 2 + (v - pts[0][1]) ** 2
    s = np.ones_like(u)
    N = len(pts)
    for i in range(N):
        j = (i - 1) % N
        e = pts[j] - pts[i]
        wu, wv = u - pts[i][0], v - pts[i][1]
        t = np.clip((wu * e[0] + wv * e[1]) / (e @ e), 0, 1)
        bu, bv = wu - e[0] * t, wv - e[1] * t
        d = np.minimum(d, bu * bu + bv * bv)
        c1, c2, c3 = v >= pts[i][1], v < pts[j][1], e[0] * wv > e[1] * wu
        flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
        s = np.where(flip, -s, s)
    return s * np.sqrt(d)


def wing_2d(u, v):
    W = WING_PTS
    poly = [W["root"], W["wrist"], W["tip1"], W["tip2"], W["tip3"], W["back"]]
    m = sd_poly(u, v, poly)
    cen = np.mean(np.array(poly), axis=0)
    for a, b, sag in ((W["tip1"], W["tip2"], 0.16), (W["tip2"], W["tip3"], 0.16), (W["tip3"], W["back"], 0.12)):
        a, b = np.array(a), np.array(b)
        L = np.linalg.norm(b - a)
        mid = (a + b) / 2
        nn = np.array(((b - a)[1], -(b - a)[0])) / L
        if nn @ (mid - cen) < 0:
            nn = -nn
        s_ = sag * L
        R = (L / 2) ** 2 / (2 * s_) + s_ / 2
        cc = mid + nn * (R - s_)
        m = smax(m, -(np.hypot(u - cc[0], v - cc[1]) - R), 0.03)
    return m


def wing_struts(P):
    """Arm, thumb and three finger struts of the LEFT wing (P in left-wing world space)."""
    d, e, n = wing_frame()
    W = {k: W0 + d * p[0] + e * p[1] for k, p in WING_PTS.items()}
    arm = smin(rcone(P, W0, W["wrist"], 0.11, 0.085), ell(P, W["wrist"], (0.095, 0.095, 0.095)), 0.03)
    thumb = rcone(P, W["wrist"], W["wrist"] - e * 0.13 + d * 0.05, 0.065, 0.042)
    fing = None
    for k in ("tip1", "tip2", "tip3"):
        f = rcone(P, W["wrist"], W[k], 0.072, 0.056)
        fing = f if fing is None else np.minimum(fing, f)
    return smin(smin(arm, thumb, 0.03), fing, 0.04)


def wing_outline(k_arc=(12, 12, 10)):
    """Clean 2D membrane outline (u, v): leading edge under the arm and finger, smooth scallop arcs between the tips."""
    W = {k: np.array(v, float) for k, v in WING_PTS.items()}
    cen = np.mean(np.array(list(W.values())), axis=0)
    tip = {k: W[k] + (cen - W[k]) / np.linalg.norm(cen - W[k]) * 0.035 for k in ("tip1", "tip2", "tip3")}
    pts = []

    def line(a, b, k):
        for i in range(k):
            pts.append(a + (b - a) * i / k)

    def arc(a, b, sag, k):
        L = np.linalg.norm(b - a)
        mid = (a + b) / 2
        nn = np.array(((b - a)[1], -(b - a)[0])) / L
        if nn @ (mid - cen) < 0:
            nn = -nn
        s_ = sag * L
        R = (L / 2) ** 2 / (2 * s_) + s_ / 2
        cc = mid + nn * (R - s_)
        ta, tb = math.atan2((a - cc)[1], (a - cc)[0]), math.atan2((b - cc)[1], (b - cc)[0])
        dt = (tb - ta + math.pi) % (2 * math.pi) - math.pi
        for i in range(k):
            t = ta + dt * i / k
            pts.append(cc + R * np.array((math.cos(t), math.sin(t))))

    line(W["root"], W["wrist"], 3)
    line(W["wrist"], tip["tip1"], 5)
    arc(tip["tip1"], tip["tip2"], 0.16, k_arc[0])
    arc(tip["tip2"], tip["tip3"], 0.16, k_arc[1])
    arc(tip["tip3"], W["back"], 0.12, k_arc[2])
    line(W["back"], W["root"], 3)
    return np.array(pts)


def wing_membrane():
    d, e, n = wing_frame()
    uv = wing_outline()
    vs = [tuple(W0 + d * u + e * v) for u, v in uv]
    me = bpy.data.meshes.new("memb")
    me.from_pydata(vs, [], [tuple(range(len(vs)))])
    ob = bpy.data.objects.new("memb", me)
    bpy.context.scene.collection.objects.link(ob)
    so = ob.modifiers.new("Solid", "SOLIDIFY")
    so.thickness, so.offset, so.use_even_offset = 0.05, 0.0, True
    bv = ob.modifiers.new("Bevel", "BEVEL")
    bv.width, bv.segments, bv.limit_method, bv.angle_limit = 0.016, 2, "ANGLE", math.radians(30)
    tr = ob.modifiers.new("Tri", "TRIANGULATE")
    tr.quad_method, tr.ngon_method = "BEAUTY", "BEAUTY"
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    m2 = ev.to_mesh()
    vo = np.array([v.co[:] for v in m2.vertices], float)
    fo = [tuple(p.vertices) for p in m2.polygons]
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    log("membrane", len(uv), "outline points ->", len(fo), "tris")
    return vo, fo


def struts_field(h):
    d, e, n = wing_frame()
    corners = np.array([W0 + d * a + e * b + n * c for a in (-0.25, 1.45) for b in (-0.35, 0.95) for c in (-0.2, 0.2)])
    G = Grid(corners.min(0) - 0.05, corners.max(0) + 0.05, h)
    P = G.P
    return G, smin(wing_struts(P), ell(P, W0, (0.12, 0.12, 0.12)), 0.05)


def leg_field(h):
    """Left shin + foot (+X), pivoting at the knee hidden inside the fused thigh."""
    G = Grid((0.10, -0.55, -0.05), (0.62, 0.15, 0.56), h)
    P = G.P
    Z = P[..., 2]
    F = rcone(P, (LEG_X - 0.01, -0.08, 0.36), (LEG_X, -0.11, 0.12), 0.13, 0.12)
    F = smin(F, ell(P, (LEG_X, -0.18, 0.085), (0.15, 0.21, 0.085)), 0.08)       # chunky foot
    for dx, dy, dz in CLAW_FOOT:
        F = smin(F, ell(P, (LEG_X + dx, dy, dz), (0.055, 0.065, 0.055)), 0.03)
    F = smax(F, -Z, 0.012)
    return G, F


ARM_W, ARM_H = np.array((0.40, -0.58, 0.76)), np.array((0.37, -0.675, 0.735))


def arm_parts(P):
    """Left forearm (+X): elbow ball on the pivot (buried in the body's elbow mass), short thick forearm held forward,
    stubby round hand with 3 rounded ivory toes pointing forward and down."""
    F = smin(ell(P, ARM_E, (0.165, 0.165, 0.165)), rcone(P, ARM_E, ARM_W, 0.17, 0.145), 0.05)
    F = smin(F, ell(P, ARM_H, (0.15, 0.135, 0.12)), 0.07)                     # fat rounded mitten hand
    toes = None
    for dx in (-0.06, 0.0, 0.06):
        t_ = ell(P, ARM_H + np.array((dx * 1.5, -0.105, -0.045)), (0.058, 0.05, 0.05))
        toes = t_ if toes is None else np.minimum(toes, t_)
    return smin(F, toes, 0.04), toes


def arm_field(h):
    G = Grid((0.14, -0.92, 0.45), (0.72, -0.08, 1.02), h)
    return G, arm_parts(G.P)[0]


TAIL_CHAIN = [((0, 0.34, 0.52), 0.23), ((0, 0.62, 0.42), 0.17), ((0, 0.90, 0.37), 0.125),
              ((0, 1.12, 0.42), 0.09), ((0, 1.27, 0.54), 0.068)]
SPADE_C, SPADE_AX = (0.0, 1.36, 0.62), (0.0, 0.55, 0.83)


def tail_field(h):
    G = Grid((-0.40, 0.05, 0.05), (0.40, 1.62, 1.00), h, sym_x=True)
    P = G.P
    F = None
    for (a, ra), (b, rb) in zip(TAIL_CHAIN[:-1], TAIL_CHAIN[1:]):
        seg = rcone(P, a, b, ra, rb)
        F = seg if F is None else smin(F, seg, 0.06)
    spade = ell(P, SPADE_C, (0.17, 0.065, 0.15), axis=SPADE_AX)
    F = smin(F, spade, 0.07)
    return G, F, dict(spade=spade)


def flame_field(h):
    G = Grid((-0.22, 1.20, 0.55), (0.22, 1.70, 1.10), h, sym_x=True)
    P = G.P
    F = rcone(P, (0, 1.41, 0.69), (0, 1.48, 0.97), 0.085, 0.02)
    for s in (1, -1):
        F = smin(F, rcone(P, (s * 0.04, 1.41, 0.71), (s * 0.115, 1.45, 0.87), 0.05, 0.018), 0.04)
    F = smin(F, rcone(P, (0, 1.38, 0.71), (0, 1.34, 0.85), 0.05, 0.018), 0.03)
    return G, F


# ---- ember markings: thin shells laid on the facets (cheeks, back bumps, wing arms, tail) ------
GLOW_MARKS = []    # (carrier pid, c, a, b, n, L, W)
CARRIER_PID = {P_GCHEEK: P_HEAD, P_GBACK: P_BODY, P_GWINGL: P_WINGL, P_GWINGR: P_WINGR, P_GTAIL: P_TAIL}


def wing_world(u, v):
    d, e, _ = wing_frame()
    return W0 + d * u + e * v


def marks():
    d, e, _ = wing_frame()
    wr = np.array(WING_PTS["wrist"])
    arm_pts = [wr * t for t in (0.42, 0.78)]
    return {
        P_GCHEEK: [(tuple(head_world((s * 1.2, -0.42, 1.66))), (-s, 0, 0), (0, 1, 0.5), 0.09, 0.026, 0.55, 0.0) for s in (1, -1)]
        + [(tuple(head_world((s * 1.2, -0.30, 1.55))), (-s, 0, 0), (0, 1, 0.3), 0.07, 0.022, 0.55, 0.0) for s in (1, -1)],
        P_GBACK: [((0.0, 1.3, z), (0, -1, 0.0), (0, 0, 1), 0.05, 0.045, 0.3, 0.0) for z in (1.08, 0.88, 0.68)],
        P_GWINGL: [(tuple(wing_world(*p) - e * 0.6), tuple(e), tuple(d), 0.08, 0.026, 0.5, 0.0) for p in arm_pts],
        P_GTAIL: [((0.0, 0.62, 1.3), (0, 0, -1), (0, 1, 0), 0.05, 0.036, 0.25, 0.0),
                  ((0.0, 0.88, 1.3), (0, 0, -1), (0, 1, 0), 0.04, 0.03, 0.25, 0.0)],
    }


def ember_patch(tree, pid, anchor, dirv, along, L, W, taper, bend, seg=10):
    loc, nrm, _, _ = tree.ray_cast(Vector(anchor), Vector(dirv).normalized(), 5.0)
    c, n = np.array(loc), np.array(nrm)
    a = np.array(along, float)
    a = a - n * (a @ n)
    a /= np.linalg.norm(a)
    b = np.cross(n, a)
    GLOW_MARKS.append((CARRIER_PID[pid], c, a, b, n, L, W))
    if pid == P_GWINGL:
        mx = np.array((-1.0, 1.0, 1.0))
        GLOW_MARKS.append((P_WINGR, c * mx, a * mx, b * mx, n * mx, L, W))

    def on_surf(x, y, off):
        p0 = c + a * x + b * y
        h = tree.ray_cast(Vector(p0 + n * 0.3), Vector(-n), 1.0)
        if h[0] is None:
            return p0 + n * off
        return np.array(h[0]) + np.array(h[1]) * off

    def local(r, th):
        x = r * math.cos(th) * L
        y = r * math.sin(th) * W * (1.0 - taper * max(0.0, math.cos(th) * r))
        return x, y + bend * (x / L) ** 2 * L

    TOP, BOT = 0.020, 0.006
    vs = [on_surf(0, 0, TOP)]
    for r in (0.55, 1.0):
        for k in range(seg):
            vs.append(on_surf(*local(r, 2 * math.pi * k / seg), TOP))
    bc = len(vs)
    vs.append(on_surf(0, 0, BOT))
    br = len(vs)
    for k in range(seg):
        vs.append(on_surf(*local(1.0, 2 * math.pi * k / seg), BOT))
    fs = []
    for k in range(seg):
        k1 = (k + 1) % seg
        fs.append((0, 1 + k, 1 + k1))
        fs.append((1 + k, 1 + seg + k, 1 + seg + k1, 1 + k1))
        fs.append((bc, br + k1, br + k))
        fs.append((1 + seg + k, br + k, br + k1, 1 + seg + k1))
    return np.array(vs), fs


def merge(vfs):
    vs, fs, off = [], [], 0
    for v, f in vfs:
        vs.append(v)
        fs += [tuple(i + off for i in fc) for fc in f]
        off += len(v)
    return np.concatenate(vs), fs


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


def bands(p, fx, fz, seed, cy=0.0):
    """Broad painterly brush bands following the form: (dark, light) masks, three value ranges."""
    az_ = np.arctan2(p[:, 0], -(p[:, 1] - cy))
    q = np.stack([np.cos(az_) * fx, np.sin(az_) * fx, p[:, 2] * fz], 1)
    s_ = vnoise(q, 1.0, seed)
    return 1.0 - sstep(0.38, 0.46, s_), sstep(0.60, 0.68, s_)


def sample(part, name, p):
    G, fl = FUSED[part]
    return G.sample(fl[name], p)


RED, RED_LT, RED_SH, RED_DK = rgb(214, 62, 46), rgb(242, 110, 70), rgb(156, 36, 42), rgb(118, 26, 38)
BELLY, BELLY_LT, BELLY_SH, BELLY_LINE = rgb(252, 216, 140), rgb(255, 240, 192), rgb(232, 168, 94), rgb(196, 112, 64)
IVORY, IVORY_SH = rgb(252, 240, 214), rgb(214, 186, 146)
GOLD, GOLD_LT, GOLD_DK = rgb(250, 184, 72), rgb(255, 222, 128), rgb(212, 124, 48)
MEMB, MEMB_LT, MEMB_SH = rgb(255, 170, 108), rgb(255, 206, 148), rgb(232, 118, 78)
EYE_DARK, EYE_IRIS, EYE_LINE = rgb(40, 16, 22), rgb(238, 150, 38), rgb(66, 20, 26)
MOUTH_C = rgb(96, 22, 32)
BLUSH, HALO = rgb(255, 140, 112), rgb(120, 26, 32)
NEON, NEON_LT = rgb(255, 150, 46), rgb(255, 214, 120)


def halos(c, p, n, carrier):
    for pid, cc, a, b, nn, L, W in GLOW_MARKS:
        if pid != carrier:
            continue
        d = p - cc
        e = np.sqrt(((d @ a) / (L * 1.45)) ** 2 + ((d @ b) / (W * 2.4)) ** 2)
        m = (np.abs(d @ nn) < 0.08) & (n @ nn > 0.2)
        c = mix(c, HALO, 0.55 * sstep(1.0, 0.55, e) * m)
    return c


def red_skin(p, n, seed, z0, z1, cy=0.0):
    c = mix(RED_SH, RED, sstep(z0, z1, p[:, 2]))
    c = mix(c, RED_LT, 0.30 * sstep(0.25, 0.9, n[:, 2]))
    bd, bl = bands(p, 3.2, 1.8, seed, cy)
    c = mix(c, RED_DK, 0.24 * bd)
    return mix(c, RED_LT, 0.22 * bl * sstep(-0.3, 0.6, n[:, 2]))


def paint_body(p, n):
    X, Y, Z = p[:, 0], p[:, 1], p[:, 2]
    c = red_skin(p, n, 11, 0.15, 1.0, 0.04)
    # modelled cream plates (each lighter in its middle), warm orange grooves between them
    sh = sstep(0.14, 0.10, sample("body", "shell", p)) * sstep(0.35, 0.30, np.abs(X)) * sstep(-0.02, -0.10, Y) \
        * sstep(0.10, -0.25, n[:, 1]) * sstep(PL_Z0 - 0.02, PL_Z0 + 0.03, Z + 0.3 * X ** 2) \
        * sstep(PL_Z0 + PL_N * PL_SP + 0.09, PL_Z0 + PL_N * PL_SP + 0.04, Z + 0.3 * X ** 2)
    ph = (Z + 0.3 * X ** 2 - PL_Z0) / PL_SP
    fr = ph - np.floor(ph)
    pm = sstep(0.074, 0.064, np.abs(fr - 0.5) * PL_SP) * sstep(0.345, 0.30, np.abs(X))
    pc = mix(BELLY_SH, BELLY, sstep(0.0, 0.40, fr))
    pc = mix(pc, BELLY_LT, 0.50 * sstep(0.35, 0.65, fr) * sstep(0.95, 0.70, fr))
    bd2, _ = bands(p, 4.0, 2.0, 17, 0.0)
    pc = mix(pc, BELLY_SH, 0.16 * bd2)
    pc = mix(BELLY_LINE, pc, pm)
    c = mix(c, pc, sh * (1 - (1 - sstep(-0.02, 0.03, sample("body", "shoulder", p))) * sstep(0.29, 0.34, np.abs(X))))
    th = sstep(0.98, 1.08, Z) * sstep(0.27, 0.20, np.abs(X)) * sstep(-0.12, -0.30, Y) * sstep(0.0, -0.35, n[:, 1])
    c = mix(c, mix(BELLY_SH, BELLY, sstep(-0.6, 0.3, n[:, 2] + 0.3)), th)
    # spine bumps: a deeper warm red under their ember tops
    bm = sstep(0.02, -0.01, sample("body", "bumps", p)) * (Y > 0.1)
    c = mix(c, mix(RED_DK, RED, sstep(-0.3, 0.6, n[:, 2] + 0.4 * n[:, 1])), 0.7 * bm)
    c = halos(c, p, n, P_BODY)
    global _PLATE_LOCAL
    _PLATE_LOCAL = pm * sh > 0.5
    return c, bm > 0.5


def paint_head(p, n, eyes_out):
    pw = p
    p = head_design(pw)
    X, Y, Z = p[:, 0], p[:, 1], p[:, 2]
    c = red_skin(p, n, 13, 1.2, 1.95, HEAD_C[1])
    mz = sstep(0.02, -0.01, sample("head", "muzzle", pw))
    c = mix(c, RED_LT, 0.20 * mz * sstep(0.2, 0.8, n[:, 2]))                   # muzzle top catches light
    br = sstep(0.02, -0.01, sample("head", "brow", pw))
    c = mix(c, RED_LT, 0.25 * br * sstep(0.1, 0.7, n[:, 2]))
    # cream lower jaw / chin, dark open grin, pink tongue, rounded ivory teeth
    jw = sstep(0.02, -0.01, sample("head", "jaw", pw)) * sstep(1.47, 1.43, Z - 0.5 * X ** 2)
    jc = mix(BELLY_SH, BELLY, sstep(-0.6, 0.2, n[:, 2] - n[:, 1] * 0.5))
    c = mix(c, jc, jw)
    cv = sample("head", "cav", pw)
    mo = sstep(0.022, 0.004, cv) * (Y > -1.02)
    c = mix(c, mix(MOUTH_C * 0.7, MOUTH_C * 1.25, sstep(-0.80, -0.95, Y)), mo)
    tg = sstep(0.012, -0.004, sample("head", "tongue", pw)) * mo
    c = mix(c, mix(rgb(214, 84, 98), rgb(250, 136, 140), sstep(-0.2, 0.8, n[:, 2])), tg)
    fg = sstep(0.012, -0.004, sample("head", "teeth", pw))
    c = mix(c, mix(IVORY_SH, IVORY, sstep(-0.5, 0.3, -n[:, 1])), fg)
    # nostrils on the front of the nostril bumps
    for s in (1, -1):
        nd = np.sqrt(((X - s * 0.115) / 0.035) ** 2 + ((Z - 1.765) / 0.025) ** 2)
        c = mix(c, RED_DK * 0.7, sstep(1.0, 0.6, nd) * (Y < -0.82) * (n[:, 1] < -0.3))
    front = (Y < -0.45) & (n[:, 1] < -0.15)
    for s in (1, -1):                                                          # soft cheek blush
        bdd = np.sqrt(((X - s * 0.40) / 0.11) ** 2 + ((Z - 1.64) / 0.07) ** 2)
        c = mix(c, BLUSH, 0.35 * sstep(1.0, 0.2, bdd) * front)
    # big round glossy eyes, set high and wide under the brows
    hard = np.zeros(len(p), bool)
    for name in ("eyeL", "eyeR"):
        e = FACE[name]
        d = pw - e["c"]
        eu, ev = (d @ e["u"]) / e["r"][0], (d @ e["v"]) / e["r"][1]
        frontm = (np.abs(d @ e["n"]) < 0.16) & (n @ e["n"] > -0.05)
        r = np.sqrt(eu * eu + ev * ev)
        line = frontm & (r >= 0.97) & (r < 1.16 + 0.10 * sstep(0.2, 0.8, ev))
        c[line] = mix(c[line], EYE_LINE, sstep(1.28, 1.05, r)[line])
        ins = frontm & (r < 1.0)
        ce = np.tile(EYE_DARK, (len(p), 1))
        iris = sstep(0.25, 0.85, r) * sstep(0.3, -0.75, ev)
        ce = mix(ce, EYE_IRIS, 0.88 * iris)
        ce = mix(ce, np.clip(EYE_IRIS * 1.25, 0, 1), 0.5 * sstep(-0.40, -0.85, ev) * sstep(0.30, 0.8, r))
        c[ins] = ce[ins]
        eyes_out.append((ins, eu, ev))
    # horns: warm ivory, soft growth rings toward the base
    hm = sstep(0.02, -0.008, sample("head", "horn", pw)) * (Z > 2.02)
    t = sstep(-0.10, 0.40, Y)
    ic = mix(IVORY_SH, IVORY, 0.35 + 0.65 * t)
    ic = mix(ic, IVORY_SH, 0.20 * sstep(0.6, 1.0, 0.5 + 0.5 * np.cos(Y * 40.0)) * (1 - t))
    ic = mix(ic, np.array((1.0, 0.98, 0.94)), 0.30 * sstep(0.3, 0.9, n[:, 2]))
    c = mix(c, ic, hm)
    hard |= (hm > 0.5) | (fg > 0.5)
    fm = sstep(0.02, -0.01, sample("head", "fin", pw)) * sstep(0.42, 0.50, np.abs(X))
    c = mix(c, mix(MEMB_SH, MEMB_LT, sstep(0.45, 0.66, np.abs(X))), fm)
    c = halos(c, pw, n, P_HEAD)
    return c, hard


def paint_wing(p, n, s, pid):
    q = p * np.array((s, 1.0, 1.0))
    d, e, nw = wing_frame()
    qq = q - W0
    u, v = qq @ d, qq @ e
    st = wing_struts(q)
    rmask = sstep(0.018, -0.004, st)
    m = mix(MEMB_SH, MEMB, sstep(-0.02, 0.10, st))                             # deeper next to the struts
    m = mix(m, MEMB_LT, 0.55 * sstep(-0.05, 0.03, wing_2d(u, v)) * sstep(0.04, 0.12, st))   # light rim
    bd, bl = bands(np.stack([u * 3, v * 3, qq @ nw], 1), 2.5, 1.0, 37, 0.0)
    m = mix(m, MEMB_SH, 0.15 * bd)
    m = mix(m, MEMB_LT, 0.15 * bl)
    r_ = mix(RED_SH, RED, sstep(-0.4, 0.6, n[:, 2]))
    r_ = mix(r_, RED_LT, 0.30 * sstep(0.4, 0.95, n[:, 2]))
    c = mix(m, r_, rmask)
    c = halos(c, p, n, pid)
    return c, rmask > 0.5


def paint_leg(p, n, s):
    X, Y, Z = p[:, 0] * s, p[:, 1], p[:, 2]
    c = red_skin(p - np.array((s * LEG_X, 0.0, 0.0)), n, 29 + s, 0.0, 0.45)
    c = mix(c, BELLY_SH, 0.75 * sstep(0.04, 0.012, Z))                         # pale sole
    hard = np.zeros(len(p), bool)
    for dx, dy, dz in CLAW_FOOT:
        dd = np.sqrt(((X - LEG_X - dx) / 0.062) ** 2 + ((Y - dy) / 0.075) ** 2 + ((Z - dz) / 0.062) ** 2)
        cm = sstep(1.05, 0.85, dd) * (Y < dy + 0.035)
        c = mix(c, mix(IVORY_SH, IVORY, sstep(-0.2, 0.6, n[:, 2] - n[:, 1])), cm)
        hard |= cm > 0.5
    return c, hard


def paint_arm(p, n, s):
    q = p * np.array((s, 1.0, 1.0))
    c = red_skin(p, n, 11, 0.15, 1.0, 0.04)                                    # same coat as the body across the elbow
    under = sstep(-0.15, -0.55, n[:, 2]) * sstep(-0.50, -0.60, q[:, 1])
    c = mix(c, mix(BELLY_SH, BELLY, 0.6), 0.85 * under)                        # cream palm / forearm underside
    cm = sstep(0.012, -0.004, arm_parts(q)[1])
    c = mix(c, mix(IVORY_SH, IVORY, sstep(-0.3, 0.5, n[:, 2] - n[:, 1])), cm)
    return c, cm > 0.5


def paint_tail(p, n):
    X, Y, Z = p[:, 0], p[:, 1], p[:, 2]
    c = red_skin(p * np.array((1, 0.5, 1)), n, 31, -0.2, 0.6, 0.5)
    c = mix(RED_SH, c, sstep(-0.7, 0.3, n[:, 2]))
    um = sstep(-0.15, -0.45, n[:, 2]) * (np.abs(X) < 0.17)                    # cream underside bands
    ph = (Y - 0.40) / 0.14
    fr = ph - np.floor(ph)
    uc = mix(BELLY_SH, BELLY, sstep(0.0, 0.5, fr))
    uc = mix(uc, BELLY_LINE, 0.5 * sstep(0.12, 0.0, np.minimum(fr, 1 - fr)))
    c = mix(c, uc, um)
    sp = sstep(0.025, -0.01, sample("tail", "spade", p)) * (Y > 1.25)
    gc = mix(GOLD_DK, GOLD, sstep(-0.3, 0.6, n[:, 2] + 0.3 * n[:, 1]))
    gc = mix(gc, GOLD_LT, 0.35 * sstep(0.4, 0.9, n[:, 2]))
    c = mix(c, gc, sp)
    c = halos(c, p, n, P_TAIL)
    return c, sp > 0.5


def paint_glow(p, n, pid):
    c = mix(NEON, NEON_LT, 0.55 + 0.45 * sstep(0.0, 0.8, np.abs(n[:, 2])))
    if pid == P_GTAIL:
        c = mix(c, NEON_LT, sstep(0.80, 1.0, p[:, 2]))
    return c


def paint_all(P, Ns, part):
    col = np.zeros((len(P), 3))
    hard = np.zeros(len(P), bool)
    eyes = []
    for pid in range(1, 15):
        m = part == pid
        if not m.any():
            continue
        p, n = P[m], Ns[m]
        ex = []
        h = np.zeros(len(p), bool)
        if pid == P_BODY:
            c, h = paint_body(p, n)
            global PLATE_FULL
            PLATE_FULL = np.zeros(len(P), bool)
            PLATE_FULL[m] = _PLATE_LOCAL
        elif pid == P_HEAD:
            c, h = paint_head(p, n, ex)
        elif pid in (P_WINGL, P_WINGR):
            c, h = paint_wing(p, n, 1 if pid == P_WINGL else -1, pid)
        elif pid in (P_LEGL, P_LEGR):
            c, h = paint_leg(p, n, 1 if pid == P_LEGL else -1)
        elif pid == P_TAIL:
            c, h = paint_tail(p, n)
        elif pid in (P_ARML, P_ARMR):
            c, h = paint_arm(p, n, 1 if pid == P_ARML else -1)
        else:
            c = paint_glow(p, n, pid)
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
    k = np.clip(ks + np.where(hard, 1.3, 1.6) * (kf - ks), 0.0, 1.0)             # visible facets
    sky = 0.5 + 0.5 * Ns[:, 2]
    lightv = 0.62 + 0.40 * k + 0.12 * sky
    head = part_ids == P_HEAD
    plate = PLATE_FULL if PLATE_FULL is not None else np.zeros(len(P), bool)
    ao_w = np.where(head, 0.22, np.where(plate, 0.22, 0.30))
    aol_w = np.where(head | plate, np.where(plate, 0.0, 0.08), 0.16)
    aof = (1.0 - ao_w + ao_w * sstep(0.12, 1.0, ao_s)) * (1.0 - aol_w * (1.0 - sstep(0.2, 1.0, ao_l)))
    eld = np.minimum(np.linalg.norm(P - ARM_E, axis=1), np.linalg.norm(P - ARM_E * np.array((-1, 1, 1)), axis=1))
    aof = mix(aof[:, None], np.ones((len(P), 1)), sstep(0.30, 0.20, eld))[:, 0]   # elbow joint: no crease
    shade = lightv * aof * (0.92 + 0.10 * sstep(0.0, 2.2, P[:, 2]))
    lit = col * shade[:, None]
    lit = mix(lit, np.clip(lit * np.array((1.06, 0.97, 0.88)), 0, 1), 0.5 * sstep(1.0, 0.8, shade) * sstep(0.55, 0.75, shade))
    lit = mix(lit, np.clip(lit * np.array((1.02, 0.86, 0.84)) + np.array((0.02, 0.0, 0.004)), 0, 1),
              0.75 * sstep(0.80, 0.50, shade))                                  # warm shadows, never grey
    lit = lit + (sstep(0.3, 1.0, Ns @ Lr) * 0.10)[:, None] * np.array((0.55, 0.70, 1.0))   # cool rim
    hl = np.clip(col * 1.15 + 0.10, 0, 1) * np.array((1.0, 0.96, 0.88))
    lit = mix(lit, hl, 0.25 * edge * hard * sstep(-0.3, 0.5, Ns @ Lk))
    glow = np.isin(part_ids, GLOW_PIDS)
    lit[glow] = col[glow]
    return np.clip(lit, 0, 1)


def catchlights(col, eyes):
    for inside, eu, ev in eyes:
        g1 = np.sqrt(((eu + 0.30) / 0.36) ** 2 + ((ev - 0.38) / 0.32) ** 2)
        g2 = np.sqrt(((eu - 0.38) / 0.15) ** 2 + ((ev + 0.30) / 0.14) ** 2)
        m1, m2 = inside & (g1 < 1.0), inside & (g2 < 1.0)
        col[m1] = mix(col[m1], np.array((1.0, 1.0, 1.0)), sstep(1.0, 0.8, g1)[m1])
        col[m2] = mix(col[m2], np.array((1.0, 0.98, 0.94)), sstep(1.0, 0.75, g2)[m2])
    return col


# =============================================================================================
# build
# =============================================================================================
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
mat = bpy.data.materials.new("BabyDragon_Atlas")
mat.use_nodes = True


def world_bounds_early(o):
    ws = [o.matrix_world @ vv.co for vv in o.data.vertices]
    return ([min(w[k] for w in ws) for k in range(3)], [max(w[k] for w in ws) for k in range(3)])


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


TARGET = dict(body=1800, head=3200, struts=720, leg=300, tail=620, flame=200, arm=440)
G_, F_, fl_ = body_field(H_FINE)
fl_["F"] = F_
FUSED["body"] = (G_, fl_)
body_vf = extract(G_, F_, TARGET["body"], "body")
body_vf = merge([body_vf, build_plates()])
G_, F_, fl_ = head_field(H_FINE, True)
FUSED["head"] = (G_, fl_)
head_vf = extract(G_, F_, TARGET["head"], "head", passes=12)
G_, F_, fl_ = tail_field(H_FINE)
FUSED["tail"] = (G_, fl_)
tail_vf = extract(G_, F_, TARGET["tail"], "tail")
G_, F_ = leg_field(0.015)
leg_l = extract(G_, F_, TARGET["leg"], "leg")
G_, F_ = arm_field(0.014)
arm_l = extract(G_, F_, TARGET["arm"], "arm")
G_, F_ = struts_field(0.014)
wing_l = merge([extract(G_, F_, TARGET["struts"], "struts"), wing_membrane()])
G_, F_ = flame_field(0.012)
flame_vf = extract(G_, F_, TARGET["flame"], "flame")
del G_, F_

TREES = {P_HEAD: BVHTree.FromPolygons(head_vf[0].tolist(), head_vf[1]),
         P_BODY: BVHTree.FromPolygons(body_vf[0].tolist(), body_vf[1]),
         P_WINGL: BVHTree.FromPolygons(wing_l[0].tolist(), wing_l[1]),
         P_TAIL: BVHTree.FromPolygons(tail_vf[0].tolist(), tail_vf[1])}
glow_vf = {}
for gpid, mk_list in marks().items():
    pts = [ember_patch(TREES[CARRIER_PID[gpid]], gpid, *mk) for mk in mk_list]
    if gpid == P_GTAIL:
        pts.append(flame_vf)
    glow_vf[gpid] = merge(pts)
glow_vf[P_GWINGR] = mirror(glow_vf[P_GWINGL])
GLOW_NAME = {P_GCHEEK: PFX + "Cheeks_Glow", P_GBACK: PFX + "Back_Glow", P_GWINGL: PFX + "WingL_Glow",
             P_GWINGR: PFX + "WingR_Glow", P_GTAIL: PFX + "TailFlame_Glow"}
for gpid, (vs_, _) in glow_vf.items():
    PIVOT[GLOW_NAME[gpid]] = V(*np.round((vs_.min(0) + vs_.max(0)) / 2, 4))

specs = [(PFX + "Body", P_BODY, body_vf), (PFX + "Head", P_HEAD, head_vf),
         (PFX + "WingL", P_WINGL, wing_l), (PFX + "WingR", P_WINGR, mirror(wing_l)),
         (PFX + "LegL", P_LEGL, leg_l), (PFX + "LegR", P_LEGR, mirror(leg_l)),
         (PFX + "Tail", P_TAIL, tail_vf), (PFX + "ArmL", P_ARML, arm_l), (PFX + "ArmR", P_ARMR, mirror(arm_l))] + [(GLOW_NAME[g], g, glow_vf[g]) for g in GLOW_PIDS]
objs = [make_object(n, pid, vf, mat) for n, pid, vf in specs]
parts = {o.name: o for o in objs}
GLOWS = [parts[GLOW_NAME[g]] for g in GLOW_PIDS]
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
bpy.ops.object.shade_flat()     # faceted: broad planes like cut gemstone facets
SMOOTH_DEG = 24.0               # ... but rims, tubes and bevels (sharper folds) shade smooth so edges read soft


def smooth_rims(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    flags = []
    for f in bm.faces:
        mx = 0.0
        for e in f.edges:
            if len(e.link_faces) == 2:
                mx = max(mx, math.degrees(e.calc_face_angle(0.0)))
        flags.append(mx > SMOOTH_DEG)
    bm.free()
    o.data.polygons.foreach_set("use_smooth", flags)
    return int(sum(flags))


log("smooth-shaded rim faces", {o.name.replace(PFX, ""): smooth_rims(o) for o in objs if o.pass_index not in GLOW_PIDS})
_bp = parts[PFX + "Body"].data.polygons
_fl = [False] * len(_bp)
_bp.foreach_get("use_smooth", _fl)
for _i in range(len(_bp) - PLATE_NF, len(_bp)):
    _fl[_i] = True
_bp.foreach_set("use_smooth", _fl)
log("belly plates fully smooth:", PLATE_NF, "faces")

if SHAPE:
    for o in objs:
        me = o.data
        mw = o.matrix_world
        Pv = np.array([(mw @ v.co)[:] for v in me.vertices])
        Nv = np.array([(mw.to_3x3() @ v.normal)[:] for v in me.vertices])
        Nv /= np.maximum(np.linalg.norm(Nv, axis=1), 1e-9)[:, None]
        col, hard, eyes = paint_all(Pv, Nv, np.full(len(Pv), o.pass_index))
        sh = 0.70 + 0.30 * np.clip(Nv @ (np.array((-0.5, -0.62, 0.62)) / 0.93), 0, 1)
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
    tris = {o.name: tri_count(o) for o in objs}
    log("triangles", sum(tris.values()), tris)
else:
    for o in objs:
        fa = o.data.attributes.new("fnrm", "FLOAT_VECTOR", "FACE")
        fa.data.foreach_set("vector", np.array([(0.0, 0.0, 0.0) if pl.use_smooth else pl.normal[:] for pl in o.data.polygons],
                                               np.float32).ravel())

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
    head_obj = parts[PFX + "Head"]
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
        if not (nrm.dot(radial) > 0.35 and nrm.y < -0.1 and abs(ang) < 1.2 and 1.30 < c.z < 2.10):
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
    log("unwrapped; base texel ratio", round(base_ratio, 4), "face-island faces", n_face)

    # ---- bake data maps (glow shells moved aside so they cast no AO on the painted skin) ---------
    for g in GLOWS:
        g.location.x += 10.0
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
            b.inputs["Radius"].default_value = 0.015
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
            a1.inputs["Distance"].default_value = 0.10
            a2 = N_("ShaderNodeAmbientOcclusion")
            a2.samples = 16
            a2.inputs["Distance"].default_value = 0.5
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

    P = dec(maps["pos"], 0.04)
    Ns, Nb = unit(dec(maps["nrm"], 0.5)), unit(dec(maps["bev"], 0.5))
    Nf_raw = dec(maps["fnrm"], 0.5)
    Nf = np.where((np.linalg.norm(Nf_raw, axis=1) < 0.5)[:, None], Ns, unit(Nf_raw))   # smooth faces: no facet key
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
    gl = np.isin(part, GLOW_PIDS)
    P[gl, 0] -= 10.0                       # glow texels back to their real place for the painter
    oc = maps["occ"][idx, :3].astype(np.float64)
    ao_s, ao_l, curv = np.clip(oc[:, 0], 0, 1), np.clip(oc[:, 1], 0, 1), oc[:, 2]
    del maps
    edge = sstep(0.995, 0.93, np.sum(Nb * Ns, axis=1)) * sstep(0.49, 0.53, curv)
    colour, hard, eyes = paint_all(P, Ns, part)
    colour = light(colour, P, Ns, Nf, hard, ao_s, ao_l, edge, part)
    colour = catchlights(colour, eyes)
    for g in GLOWS:
        g.location.x -= 10.0
    bpy.context.view_layer.update()

    full = np.zeros((BAKE * BAKE, 4), np.float32)
    full[idx, :3] = colour
    full[:, 3] = 1.0
    full[~cov, :3] = RED_SH
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
    tris = {o.name: tri_count(o) for o in objs}
    log("triangles", sum(tris.values()), tris)


# =============================================================================================
# reports (Studio axes = (-x, z, y) of Blender)
# =============================================================================================
bpy.context.view_layer.update()
CARRIER = {GLOW_NAME[P_GCHEEK]: PFX + "Head", GLOW_NAME[P_GBACK]: PFX + "Body", GLOW_NAME[P_GWINGL]: PFX + "WingL",
           GLOW_NAME[P_GWINGR]: PFX + "WingR", GLOW_NAME[P_GTAIL]: PFX + "Tail"}
JOINT_PARENT = {n: (None if n == PFX + "Body" else CARRIER.get(n, PFX + "Body")) for n in PIVOT}
JOINT_NAME = {PFX + "Body": "root (centre of the pot belly)", PFX + "Head": "neck, hidden inside the head and the neck",
              PFX + "WingL": "shoulder (round wing root sunk into the upper back)",
              PFX + "WingR": "shoulder (round wing root sunk into the upper back)",
              PFX + "LegL": "knee, hidden inside the thigh fused to the hip", PFX + "LegR": "knee, hidden inside the thigh fused to the hip",
              PFX + "Tail": "tail root, inside the tail stub of the body",
              PFX + "ArmL": "elbow: the forearm's elbow ball is centred on the pivot and buried in the body's upper-arm mass",
              PFX + "ArmR": "elbow: the forearm's elbow ball is centred on the pivot and buried in the body's upper-arm mass",
              GLOW_NAME[P_GCHEEK]: "centre of the cheek ember streaks (welded to the head, Neon)",
              GLOW_NAME[P_GBACK]: "centre of the ember tops of the spine bumps (welded to the body, Neon)",
              GLOW_NAME[P_GWINGL]: "centre of the ember streaks on the left wing arm (welded to WingL, Neon)",
              GLOW_NAME[P_GWINGR]: "centre of the ember streaks on the right wing arm (welded to WingR, Neon)",
              GLOW_NAME[P_GTAIL]: "centre of the tail flame and tail ember dots (welded to the tail, Neon)"}
MOTION = {
    PFX + "Body": f"root: hovers {HOVER_H} studs up, bobs with the wingbeat (+0.10 on the up-beat, -0.08 on the down-beat); glide pitches 12 deg nose-down; fire breath leans back 10 deg",
    PFX + "Head": "nod = pitch about Studio X, look = yaw about Studio Y, tilt = roll about Studio Z; fire breath: nose up 20 deg, 0.05 studs forward",
    PFX + "WingL": "wingbeat = rotate about Studio Z through the shoulder: wings_up / wings_down frames (big, slow: 0.8 s per beat); glide flattens and spreads",
    PFX + "WingR": "mirror of WingL",
    PFX + "LegL": "knee joint: tucked 20 deg forward while flying, swing +/-22 deg in the landing waddle",
    PFX + "LegR": "mirror of LegL",
    PFX + "Tail": "hangs 12 deg down in flight; swish = yaw about Studio Y (+/-30 deg)",
    PFX + "ArmL": "forearm + hand at the elbow (shoulders and upper arms are part of the body): rest = elbows bent, forearms held forward in front of the belly; flight = small tuck (Studio X -6..-12) with the beat; fire breath = braced forward and up; glide = tucked back along the sides",
    PFX + "ArmR": "mirror of ArmL",
}
for g in GLOW_PIDS:
    MOTION[GLOW_NAME[g]] = f"none (WeldConstraint to {CARRIER[GLOW_NAME[g]]}); Material Neon"


def studio(v):
    return [round(-v[0], 4) + 0.0, round(v[2], 4) + 0.0, round(v[1], 4) + 0.0]


def studio_size(v):
    return [round(v[0], 4), round(v[2], 4), round(v[1], 4)]


def world_bounds(o):
    ws = [o.matrix_world @ vv.co for vv in o.data.vertices]
    return (Vector([min(w[k] for w in ws) for k in range(3)]), Vector([max(w[k] for w in ws) for k in range(3)]))


# ---- poses (Blender bone angles: X = pitch about world X, Y = yaw about world Z, Z = roll about world -Y).
# Flight frames are relative to the hover root (the game lifts the rig HOVER_H); the previews add the lift.
TUCK = {"LegL": (-20, 0, 0), "LegR": (-20, 0, 0), "Tail": (-12, 0, 0), "ArmL": (6, 0, 0), "ArmR": (6, 0, 0)}


def fly(rots, locs=None):
    r = dict(TUCK)
    r.update(rots)
    return r, dict(locs or {})


HOVER_MID = fly({"Head": (-4, 0, 0)})
WINGS_UP = fly({"WingL": (0, 0, 30), "WingR": (0, 0, -30), "Head": (-6, 0, 0), "ArmL": (0, 0, 0), "ArmR": (0, 0, 0)}, {"Body": (0, 0, 0.10)})
WINGS_DOWN = fly({"WingL": (0, 0, -55), "WingR": (0, 0, 55), "Body": (4, 0, 0), "Tail": (-6, 0, 0), "ArmL": (12, 0, 0), "ArmR": (12, 0, 0)}, {"Body": (0, 0, -0.08)})
GLIDE = fly({"Body": (12, 0, 0), "Head": (-12, 0, 0), "WingL": (50, 0, -40), "WingR": (50, 0, 40),
             "LegL": (25, 0, 0), "LegR": (25, 0, 0), "Tail": (-6, 0, 0), "ArmL": (45, 0, 25), "ArmR": (45, 0, -25)})
FIRE = fly({"Body": (-10, 0, 0), "Head": (-20, 0, 0), "WingL": (0, 25, 10), "WingR": (0, -25, -10),
            "LegL": (-30, 0, 0), "LegR": (-30, 0, 0), "Tail": (-18, 0, 0), "ArmL": (-28, 0, 8), "ArmR": (-28, 0, -8)}, {"Head": (0, -0.05, 0.02)})
SWISH = fly({"Tail": (-12, 30, 0), "Head": (0, -8, 0)})
HEADTURN = fly({"Head": (8, 30, 12), "Tail": (-12, -15, 0)})


def waddle(s):
    rots = {"Body": (0, 0, 7 * s), "LegL": (-22 * s, 0, 0), "LegR": (22 * s, 0, 0), "Head": (-3, 4 * s, -5 * s),
            "Tail": (0, -16 * s, 0), "WingL": (0, 20, -20 + 10 * (s > 0)), "WingR": (0, -20, 20 - 10 * (s < 0)),
            "ArmL": (10 * s, 0, 0), "ArmR": (-10 * s, 0, 0)}
    return rots, {"Body": (0, 0, 0.03), ("LegL" if s > 0 else "LegR"): (0, 0, 0.07)}


WADDLE_PASS = ({"WingL": (0, 20, -15), "WingR": (0, -20, 15)}, {})
BONES = ["Body", "Head", "WingL", "WingR", "LegL", "LegR", "Tail", "ArmL", "ArmR"]


def lifted(rl, h=HOVER_H):
    rots, locs = rl
    locs = dict(locs)
    b = locs.get("Body", (0, 0, 0))
    locs["Body"] = (b[0], b[1], b[2] + h)
    return rots, locs


def studio_pose(rl):
    rots, locs = rl
    out = {}
    for b in BONES:
        r, l = rots.get(b, (0, 0, 0)), locs.get(b, (0, 0, 0))
        if any(r) or any(l):
            out[PFX + b] = {"rot_deg_studio_xyz": [-r[0] + 0.0, r[1] + 0.0, -r[2] + 0.0],
                            "offset_studs_studio_xyz": [-l[0] + 0.0, l[2] + 0.0, l[1] + 0.0]}
    return out


report = {"asset": STEM, "blender_version": bpy.app.version_string,
          "authoring": "final Roblox stud size (1 Blender unit = 1 stud); import at 1:1, do not scale",
          "axes": "Blender Z-up, front -Y, the dragon's left +X; feet on z = 0 (the game hovers it)",
          "texture": f"textures/{TEX_PATH.name} ({ATLAS}x{ATLAS}, shared by every part)", "parts": {}}
lo_all, hi_all = Vector((1e9,) * 3), Vector((-1e9,) * 3)
for name, o in parts.items():
    me = o.data
    me.calc_loop_triangles()
    if me.uv_layers:
        uv = me.uv_layers.active.data
        us, vs = [d.uv.x for d in uv], [d.uv.y for d in uv]
        uvr = [round(min(us), 4), round(max(us), 4), round(min(vs), 4), round(max(vs), 4)]
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
                     "height_studs": round(size.z, 4), "length_studs": round(size.y, 4), "width_studs": round(size.x, 4)}
log("overall (w, len, h)", tuple(round(v, 3) for v in (size.x, size.y, size.z)), "tris", report["total_triangles"])

body_pivot = parts[PFX + "Body"].location.copy()
head_pivot = parts[PFX + "Head"].location.copy()
tail_pivot = parts[PFX + "Tail"].location.copy()
MOUTH_P = Vector(FACE["mouth"]["c"]) + Vector(FACE["mouth"]["n"]) * 0.05
FLAME_TIP = V(0.0, 1.48, 0.99)
BACK_EMBER = V(0.0, 0.42, 1.12)
WT_ = wing_world(*WING_PTS["tip1"])
WT2_ = wing_world(*WING_PTS["tip2"])
WINGTIP = {1: V(*WT_), -1: V(*(WT_ * np.array((-1, 1, 1))))}
WINGTIP2 = {1: V(*WT2_), -1: V(*(WT2_ * np.array((-1, 1, 1))))}
GLOW_RGB = [255, 150, 46]
install = {
    "asset": STEM, "rarity": "Legendary",
    "strong_suit": "Fire: small fire breaths that burn groups (BurnChance on every enemy in the breath cone)",
    "accent": "Neon ember streaks on the cheeks and wing arms, ember tops on the spine bumps, ember dots on the tail, a Neon tail-tip flame, plus the particle specs below",
    "role_prop": "the fire itself (breath + tail flame); no extra prop",
    "axis": "studio = (-x, z, y) of blender; Blender front -Y = Studio front -Z",
    "units": "studs; the model is at final size, import 1:1 and do not scale",
    "sides": "L/R are the dragon's own left/right; its left is Blender +X = Studio -X",
    "origin": "all positions are relative to the model origin = the ground point under the model centre (Blender world origin); the feet stand on it at rest",
    "ground_point": studio((0.0, 0.0, 0.0)), "overall_size": studio_size(size),
    "overall_center": studio((lo_all + hi_all) / 2), "texture": f"textures/{TEX_PATH.name}",
    "texture_note": "one shared atlas on every MeshPart via MeshPart.TextureID. The five *_Glow parts: Material = Neon, Color = "
                    f"{GLOW_RGB} (their atlas texels are that colour too)",
    "rest_rotation": "every part has identity rotation relative to the model at rest",
    "rig": "one Motor6D per animated part: Part0 = joint_parent, Part1 = the part, C0/C1 at the part's pivot; the *_Glow parts are WeldConstraints to their carrier",
    "parts": {}}
for name, o in parts.items():
    lo, hi = world_bounds(o)
    install["parts"][name] = {
        "center": studio((lo + hi) / 2), "size": studio_size(hi - lo), "pivot": studio(o.location),
        "pivot_from_body_pivot": studio(o.location - body_pivot), "pivot_is": JOINT_NAME[name],
        "joint_parent": JOINT_PARENT[name], "suggested_motion": MOTION[name]}
install["locomotion"] = "fly"
install["locomotion_data"] = {
    "gait": f"fly: hovers about {HOVER_H} studs up with big, slow wingbeats, legs tucked a little forward and the tail hanging; "
            "flies to targets in short glides; lands and waddles only as an extra (e.g. idle on the ground)",
    "hover_height_studs": HOVER_H,
    "angle_convention": "per part, rotation about the part's own pivot in Studio axes (Roblox CFrame.Angles, degrees) plus a translation "
                        "offset in studs applied in the parent's frame (Motor6D C0). Only parts that move are listed; others stay at rest. "
                        "Flight frames are relative to the hovering root (add hover_height_studs to the root). "
                        "Blender bone angles in the previews map as Studio X = -bone X, Studio Y = bone Y, Studio Z = -bone Z.",
    "wingbeat": {"period_s": 0.8, "loop": ["wings_up", "hover_mid", "wings_down", "hover_mid"],
                 "bob_studs": [0.10, -0.08], "note": "big and slow; ease in/out at wings_up and wings_down"},
    "glide": {"note": "used while travelling to a target: hold 0.4-0.8 s between beats, wings flattened and spread, body 12 deg nose-down"},
    "frames": {"hover_mid": studio_pose(HOVER_MID), "wings_up": studio_pose(WINGS_UP), "wings_down": studio_pose(WINGS_DOWN),
               "glide": studio_pose(GLIDE), "fire_breath": studio_pose(FIRE), "tail_swish": studio_pose(SWISH),
               "head_turn": studio_pose(HEADTURN)},
    "fire_breath": {"note": "hovering: head forward and up, wings swept back, legs braced forward, body leaning back; "
                            "ease in 0.12 s, hold 0.6 s while the fire_breath emitter runs, ease out 0.2 s"},
    "landing_waddle_extra": {"note": "only when grounded (root at 0): short waddle with the wings half folded",
                             "step_period_s": 0.55, "loop": ["waddle_A", "waddle_pass", "waddle_B", "waddle_pass"],
                             "frames": {"waddle_A": studio_pose(waddle(1)), "waddle_pass": studio_pose(WADDLE_PASS),
                                        "waddle_B": studio_pose(waddle(-1))}},
}
FIRE_COLOURS = [[0.0, [255, 240, 150]], [0.22, [255, 178, 60]], [0.5, [240, 84, 36]], [0.75, [150, 52, 40]], [1.0, [72, 60, 60]]]
EMBER_COLOURS = [[0.0, [255, 222, 130]], [0.5, [255, 146, 50]], [1.0, [220, 70, 40]]]
install["vfx"] = [
    {"kind": "fire_breath", "part": PFX + "Head", "attachment_position": studio(MOUTH_P),
     "attachment_from_part_pivot": studio(MOUTH_P - head_pivot),
     "attachment_axis": "emit along the head's forward (Studio -Z of the head) so the cone follows the 20 deg nose-up breath pose",
     "trigger": "burst-driven while breathing: Enabled = true for the 0.6 s hold (or :Emit(6) every 0.05 s), off otherwise",
     "cone_length_studs": 5.0, "cone_half_angle_deg": 18, "cone_end_radius_studs": 1.6,
     "burn_hitbox": "server cone from the mouth: 5 studs long, 18 deg half-angle (end radius ~1.6); every enemy inside rolls BurnChance",
     "colour_sequence": FIRE_COLOURS,
     "suggested": {"Rate": 90, "Lifetime": [0.48, 0.56], "Speed": [9, 10.5], "SpreadAngle": [18, 18],
                   "EmissionDirection": "Front", "Size": "0.25 -> 0.85 (t 0.4) -> 1.3", "Transparency": "0.05 -> 0.2 (t 0.6) -> 1",
                   "LightEmission": 0.9, "LightInfluence": 0, "Acceleration": [0, 1.5, 0], "Drag": 0,
                   "Rotation": [0, 360], "RotSpeed": [-140, 140], "ZOffset": 0.4, "LockedToPart": False,
                   "Texture": "soft round flame puff sprite (e.g. Roblox's fire_main particle texture or a soft cloud puff)",
                   "note": "speed x lifetime ~ 5 studs = cone length; the colour runs yellow -> orange -> red -> smoke",
                   "PointLight_while_breathing": {"Color": [255, 150, 60], "Brightness": 2, "Range": 8, "Shadows": False}}},
    {"kind": "ambient_embers", "parts": [PFX + "Body", PFX + "Tail"],
     "attachments": {PFX + "Body": {"position": studio(BACK_EMBER), "from_part_pivot": studio(BACK_EMBER - body_pivot)},
                     PFX + "Tail": {"position": studio(FLAME_TIP), "from_part_pivot": studio(FLAME_TIP - tail_pivot)}},
     "enabled": "always on", "colour_sequence": EMBER_COLOURS,
     "suggested": {"Rate": 2.5, "Lifetime": [1.2, 1.8], "Speed": [0.3, 0.7], "SpreadAngle": [25, 25],
                   "EmissionDirection": "Top", "Size": "0.10 -> 0.07 (t 0.6) -> 0", "Transparency": "0 -> 0.2 (t 0.7) -> 1",
                   "LightEmission": 1, "LightInfluence": 0, "Acceleration": [0, 1.0, 0], "Drag": 0.5,
                   "Rotation": [0, 360], "RotSpeed": [-60, 60], "LockedToPart": False,
                   "Texture": "small soft spark dot", "note": "a few slow sparks drifting up from the spine embers and the tail flame; never a stream"}},
    {"kind": "flight_trail", "parts": [PFX + "WingL", PFX + "WingR"],
     "attachments_from_wing_pivot": {PFX + "WingL": [studio(WINGTIP[1] - PIVOT[PFX + "WingL"]), studio(WINGTIP2[1] - PIVOT[PFX + "WingL"])],
                                     PFX + "WingR": [studio(WINGTIP[-1] - PIVOT[PFX + "WingR"]), studio(WINGTIP2[-1] - PIVOT[PFX + "WingR"])]},
     "attachment_positions": {PFX + "WingL": [studio(WINGTIP[1]), studio(WINGTIP2[1])], PFX + "WingR": [studio(WINGTIP[-1]), studio(WINGTIP2[-1])]},
     "enabled": "always while flying (wingtips: the leading finger tip and the middle finger tip); Rate x1.5 in glides", "colour_sequence": EMBER_COLOURS,
     "suggested": {"Rate": 10, "Lifetime": [0.3, 0.45], "Speed": [0.1, 0.3], "SpreadAngle": [10, 10],
                   "Size": "0.14 -> 0", "Transparency": "0.35 -> 1", "LightEmission": 1, "LightInfluence": 0,
                   "Acceleration": [0, 0.5, 0], "Drag": 1, "LockedToPart": False, "Texture": "small soft spark dot",
                   "note": "faint ember trail off each wingtip; a Trail between the two tip attachments of each wing (Lifetime 0.25, WidthScale 1 -> 0, Transparency 0.6 -> 1) also works"}},
    {"kind": "neon_glow", "parts": [GLOW_NAME[g] for g in GLOW_PIDS], "colour_rgb": GLOW_RGB, "material": "Neon",
     "suggested": {"Transparency_idle": [0.0, 0.2], "pulse_period_s": 1.6,
                   "TailFlame_flicker": "random Transparency 0 -> 0.25 every 0.08-0.15 s",
                   "PointLight_on_tail_flame": {"Color": [255, 150, 60], "Brightness": 0.8, "Range": 4, "Shadows": False}}},
]

if not QUICK:
    (ROOT / "polygon-report.json").write_text(json.dumps(report, indent=2))
    (ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=2))
    select_only(objs, parts[PFX + "Body"])
    bpy.ops.export_scene.gltf(filepath=str(GLB_PATH), export_format="GLB", use_selection=True, export_apply=True)
    select_only(objs, parts[PFX + "Body"])
    bpy.ops.export_scene.fbx(filepath=str(FBX_PATH), use_selection=True, object_types={"MESH"},
                             axis_forward="-Z", axis_up="Y", path_mode="COPY", embed_textures=True, mesh_smooth_type="FACE",
                             add_leaf_bones=False)
    log("exported", FBX_PATH.name, GLB_PATH.name)

# =============================================================================================
# armature (Blender only, for posing previews; exports are the plain rigid parts)
# =============================================================================================
arm_data = bpy.data.armatures.new("BabyDragon_Rig")
arm = bpy.data.objects.new("BabyDragon_Rig", arm_data)
scene.collection.objects.link(arm)
select_only([arm])
bpy.ops.object.mode_set(mode="EDIT")
ebs = {}
for b in BONES:
    eb = arm_data.edit_bones.new(b)
    eb.head = PIVOT[PFX + b]
    eb.tail = PIVOT[PFX + b] + Vector((0, 0, 0.25))
    eb.roll = 0.0
    ebs[b] = eb
for b in BONES:
    if b != "Body":
        ebs[b].parent = ebs["Body"]
bpy.ops.object.mode_set(mode="OBJECT")
for name, o in parts.items():
    mwo = o.matrix_world.copy()
    o.parent = arm
    o.parent_type = "BONE"
    o.parent_bone = CARRIER.get(name, name).replace(PFX, "")
    bpy.context.view_layer.update()
    o.matrix_world = mwo
bpy.context.view_layer.update()


def pose(rl):
    rots, locs = rl if isinstance(rl, tuple) else (rl, {})
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = [math.radians(v) for v in rots.get(pb.name, (0, 0, 0))]
        d = locs.get(pb.name, (0, 0, 0))
        pb.location = (d[0], d[2], -d[1])
    bpy.context.view_layer.update()


if not QUICK:
    for im in bpy.data.images:
        if im.source == "FILE":
            im.pack()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), relative_remap=True)
    log("saved", BLEND_PATH.name)

# =============================================================================================
# previews (Eevee); the glow parts show emissive like Neon; presentation shots hover mid-beat
# =============================================================================================
gm = bpy.data.materials.new("BabyDragon_Neon_Preview")
gm.use_nodes = True
gnt = gm.node_tree
gnt.nodes.clear()
ge = gnt.nodes.new("ShaderNodeEmission")
ge.inputs["Color"].default_value = (1.0, 0.30, 0.03, 1)
ge.inputs["Strength"].default_value = 1.6
go = gnt.nodes.new("ShaderNodeOutputMaterial")
gnt.links.new(ge.outputs[0], go.inputs[0])
for g in GLOWS:
    g.data.materials[0] = gm
for _n in ("ArmL", "ArmR", "WingL", "WingR"):
    parts[PFX + _n].visible_shadow = False

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
fm_ = bpy.data.materials.new("Preview_Floor")
fm_.use_nodes = True
fm_.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.36, 0.40, 0.46, 1)
fm_.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
floor.data.materials.append(fm_)
cam = bpy.data.objects.new("PreviewCam", bpy.data.cameras.new("PreviewCam"))
scene.collection.objects.link(cam)
scene.camera = cam

# placeholder fire cone for the fire-breath pose frame (preview only, never exported)
bpy.ops.mesh.primitive_cone_add(vertices=20, radius1=0.55, radius2=0.04, depth=1.7, location=(0, 0, -50))
cone = bpy.context.object
cone.name = "Preview_FireCone"
cm_ = bpy.data.materials.new("Preview_Fire")
cm_.use_nodes = True
cnt = cm_.node_tree
cnt.nodes.clear()
tco = cnt.nodes.new("ShaderNodeTexCoord")
sep = cnt.nodes.new("ShaderNodeSeparateXYZ")
ramp = cnt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[0].color = 0.0, (0.85, 0.12, 0.04, 1)
ramp.color_ramp.elements[1].position, ramp.color_ramp.elements[1].color = 1.0, (1.0, 0.92, 0.45, 1)
mid = ramp.color_ramp.elements.new(0.55)
mid.color = (1.0, 0.45, 0.06, 1)
cem = cnt.nodes.new("ShaderNodeEmission")
cem.inputs["Strength"].default_value = 2.5
cout = cnt.nodes.new("ShaderNodeOutputMaterial")
cnt.links.new(tco.outputs["Generated"], sep.inputs[0])
cnt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
cnt.links.new(ramp.outputs["Color"], cem.inputs["Color"])
cnt.links.new(cem.outputs[0], cout.inputs[0])
cone.data.materials.append(cm_)
HEAD_OBJ = parts[PFX + "Head"]
HEAD_REST = HEAD_OBJ.matrix_world.copy()


def place_cone(on):
    if not on:
        cone.location = (0, 0, -50)
        return
    M = HEAD_OBJ.matrix_world @ HEAD_REST.inverted()
    mp = M @ MOUTH_P
    dr = (M.to_3x3() @ Vector((0.0, -1.0, 0.0))).normalized()
    cone.rotation_euler = (-dr).to_track_quat("Z", "Y").to_euler()
    cone.location = mp + dr * 0.87
    bpy.context.view_layer.update()


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



H = V(0, 0, HOVER_H)
tgt = V(0, 0.10, 1.30) + H
ft = V(0, -0.66, 1.80) + H
D = 10.6
POSES = [
    ("Wings up (beat top), hovering", WINGS_UP, around(tgt, (-0.7, -0.8, 0.25), D), tgt, False),
    ("Wings down (beat bottom)", WINGS_DOWN, around(tgt, (-0.7, -0.8, 0.25), D), tgt, False),
    ("Glide: wings flat, arms tucked back", GLIDE, around(tgt, (-0.55, -0.7, 0.75), D), tgt, False),
    ("Fire breath: arms braced forward, wings back", FIRE, around(tgt + V(0, -0.6, 0.1), (-1, -0.25, 0.12), D + 1.0), tgt + V(0, -0.6, 0.1), True),
    ("Tail swish 30 (from behind)", SWISH, around(tgt, (0.45, 1, 0.35), D), tgt, False),
    ("Head turn 30 + nod 8 + tilt 12", HEADTURN, around(tgt, (0.35, -1, 0.2), D - 1.0), tgt, False),
]
VIEWS = [("threeq", "Three-quarter (hovering)", (-0.75, -0.9, 0.30), D, tgt),
         ("front", "Front", (0, -1, 0.10), D - 0.5, tgt),
         ("side", "Side (dragon's right)", (-1, 0, 0.06), D, tgt),
         ("back", "Back (follow view)", (0, 1, 0.30), D - 0.5, tgt)]

WING_CU = V(*wing_world(0.86, 0.72)) + H
BELLY_CU = V(0.0, -0.40, 0.66) + H
CLOSEUPS = [("closeup-wing-edge", "Close-up: wing edge", around(WING_CU, (0.35, -1, 0.25), 2.4), WING_CU),
            ("closeup-belly", "Close-up: belly plates + arm", around(BELLY_CU, (-0.55, -1, 0.15), 2.8), BELLY_CU),
            ("closeup-shoulder", "Close-up: shoulder + arm (3/4)", around(V(-0.36, -0.32, 0.88) + H, (-0.8, -1, 0.25), 3.0),
             V(-0.36, -0.32, 0.88) + H)]

if not NO_PREVIEWS and QUICK:
    pose(lifted(HOVER_MID))
    items = [(shoot(OUT / f"_{k}.png", around(t, dv, dd), t, res=(700, 700)), lab) for k, lab, dv, dd, t in VIEWS]
    items.append((shoot(OUT / "_face.png", around(ft, (-0.35, -1, 0.10), 4.6), ft, res=(700, 700)), "Face"))
    pose(({}, {}))
    items.append((shoot(OUT / "_rest_side.png", around(tgt - H, (-1, 0, 0.06), D), tgt - H, res=(700, 700)), "Rest side (standing)"))
    pose(lifted(HOVER_MID))
    for k, lab, loc, t in CLOSEUPS[1:]:
        items.append((shoot(OUT / f"_{k}.png", loc, t, res=(700, 700)), lab))
    for i in (3,):
        pose(lifted(POSES[i][1]))
        place_cone(POSES[i][4])
        items.append((shoot(OUT / f"_pose{i}.png", POSES[i][2], POSES[i][3], res=(700, 700)), POSES[i][0]))
    pose(({}, {}))
    place_cone(False)
    make_sheet(items, 3, 400, OUT / ("shape-sheet.png" if SHAPE else "quick-sheet.png"), "Baby Dragon shape run")
    for pth, _ in items:
        pth.unlink()
elif not NO_PREVIEWS:
    pose(lifted(HOVER_MID))
    shots = [(shoot(OUT / f"{k}.png", around(t, dv, dd), t), lab) for k, lab, dv, dd, t in VIEWS]
    face = shoot(OUT / "face-closeup.png", around(ft, (-0.35, -1, 0.10), 4.6), ft, res=(1400, 1400))
    for k, lab, loc, t in CLOSEUPS:
        shoot(OUT / f"{k}.png", loc, t, res=(1000, 1000))
    pose_items = []
    for i, (lab, rl, loc, t, fire) in enumerate(POSES):
        pose(lifted(rl))
        place_cone(fire)
        pose_items.append((shoot(OUT / f"_pose-{i}.png", loc, t, res=(900, 900)), lab))
    place_cone(False)
    make_sheet(pose_items, 3, 450, OUT / "pose-check.png", "Baby Dragon: pose check through the joint pivots (hovering 1.5 studs)",
               "Each part rotates about its own pivot (Blender armature, preview only). Fire cone = placeholder for the particle breath.")
    for pth, _ in pose_items:
        pth.unlink()
    if not NO_HERO:
        scene.render.engine = "CYCLES"
        scene.cycles.samples = 40
        scene.cycles.use_denoising = True
        pose(lifted(WINGS_UP))
        shoot(OUT / "hero.png", around(tgt, (-0.85, -0.85, 0.25), D - 1.0), tgt, res=(900, 900))
        scene.render.engine = "BLENDER_EEVEE"
    pose(({}, {}))
    items = shots + [(face, "Face close-up"), (OUT / "pose-check.png", "Pose check (beat, glide, fire, swish, head turn)")]
    make_sheet(items, 3, 520, OUT / "sheet.png",
               f"Baby Dragon pet (Legendary, fire, flyer): {report['total_triangles']:,} tris, one 1024 atlas, Neon ember glow parts",
               "Blender 5.2 Eevee renders, hovering 1.5 studs mid-beat (glow parts shown emissive). Blender-verified, Studio untested.")
log("done")
