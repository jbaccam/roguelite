"""Bloater: Pine Valley round-10 exploding zombie ("POP GOES THE ZOMBIE").

Self-contained generator. Dedicated background Blender 5.2 only:
  & 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' -b --threads 4 --python-exit-code 1 --python roguelite-planning/bloater-zombie/build_bloater.py

Follows the Baby/Mutant native zombie contract exactly: 15 rigid R15 sections with plain
section names, each object's origin at its joint head, Blender -Y front, character left at
+X, Z up, 1 unit = 1 stud, one material, one UV layer named PaintedAtlas, mesh-only FBX
(axis_forward -Z, axis_up Y) with the atlas embedded. One extra mesh, EyeGlow, is welded to
Head in Studio (Neon). Shapes are implicit surfaces (smooth-union fillets) sampled on
bevel-aware cube lattices, so cheeks, brow, shoulders and blisters are fused, not stuck on.
The 1024 atlas is painted in numpy from each texel's 3D position (seamless by construction).
"""
import bpy, bmesh, math, json, shutil, hashlib, sys
import numpy as np
from pathlib import Path
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

OUT = Path(__file__).resolve().parent
PREV = OUT / 'previews'; TEXD = OUT / 'textures'
for d in (PREV, TEXD):
    d.mkdir(parents=True, exist_ok=True)
RP = OUT.parent
REF = RP / 'art-references' / 'round-10-modeling-pack-2026-10-09' / '01-exploding-zombie.png'
BABY_FBX = RP / 'baby-mutant-zombies' / 'BabyZombie_Import.fbx'
MUTANT_FBX = RP / 'baby-mutant-zombies' / 'MutantZombie_Import.fbx'
ATLAS = 1024
# Optional: -- renders=Front,Inflated (or renders=none). Default renders every preview.
ARGS = dict(a.split('=', 1) for a in (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []) if '=' in a)
RENDERS = None if 'renders' not in ARGS else set(ARGS['renders'].split(',')) - {'none', ''}
def want(view):
    return RENDERS is None or view in RENDERS
INFLATE, HEAD_INFLATE = 1.3, 1.08

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# --------------------------------------------------------------------------- math helpers
def _len(v):
    return np.sqrt((v * v).sum(-1))

def unit(v):
    v = np.asarray(v, float); return v / np.linalg.norm(v)

def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)

def sd_sphere(p, c, r):
    return _len(p - np.asarray(c, float)) - r

def sd_capsule(p, a, b, r):
    a = np.asarray(a, float); b = np.asarray(b, float)
    pa = p - a; ba = b - a
    h = np.clip((pa @ ba) / (ba @ ba), 0, 1)
    return _len(pa - h[:, None] * ba) - r

def sd_round_box(q, b, r):
    d = np.abs(q) - (b - r)
    return _len(np.maximum(d, 0)) + np.minimum(d.max(-1), 0) - r

def sd_ellipsoid6(p, c, rpos, rneg):
    q = p - np.asarray(c, float)
    r = np.where(q >= 0, np.asarray(rpos, float), np.asarray(rneg, float))
    k0 = _len(q / r); k1 = _len(q / (r * r))
    return np.where(k1 < 1e-9, -r.min(-1), k0 * (k0 - 1) / np.maximum(k1, 1e-9))

def sd_superellipsoid6(p, c, rpos, rneg, n):
    q = p - np.asarray(c, float)
    r = np.where(q >= 0, np.asarray(rpos, float), np.asarray(rneg, float))
    f = ((np.abs(q) / r) ** n).sum(-1) ** (1 / n)
    return _len(q) * (1 - 1 / np.maximum(f, 1e-9))

def sd_round_cyl_z(p, cxy, rad, z0, z1, rr):
    dxy = np.sqrt((p[:, 0] - cxy[0]) ** 2 + (p[:, 1] - cxy[1]) ** 2) - rad + rr
    dz = np.abs(p[:, 2] - (z0 + z1) / 2) - (z1 - z0) / 2 + rr
    return np.minimum(np.maximum(dxy, dz), 0) + np.sqrt(np.maximum(dxy, 0) ** 2 + np.maximum(dz, 0) ** 2) - rr

def rot_axis(axis, deg):
    return np.asarray(Matrix.Rotation(math.radians(deg), 3, Vector(axis)))

def frame(w, hint):
    """Proper frame with columns (u, v, w); u is perpendicular to w toward `hint`."""
    w = unit(w); h = np.asarray(hint, float)
    u = unit(h - w * (h @ w)); v = np.cross(w, u)
    return np.stack([u, v, w], 1)

# ------------------------------------------------------------- implicit surface sampling
def lattice(px, py, pz):
    """Boundary of a param grid on [-1,1]^3 as quads (shared edge vertices)."""
    nx, ny, nz = len(px) - 1, len(py) - 1, len(pz) - 1
    idx, pts, faces = {}, [], []
    def vid(i, j, k):
        key = (i, j, k)
        if key not in idx:
            idx[key] = len(pts); pts.append((px[i], py[j], pz[k]))
        return idx[key]
    for i, s in ((0, -1), (nx, 1)):
        for j in range(ny):
            for k in range(nz):
                q = [vid(i, j, k), vid(i, j + 1, k), vid(i, j + 1, k + 1), vid(i, j, k + 1)]
                faces.append(q if s > 0 else q[::-1])
    for j, s in ((0, -1), (ny, 1)):
        for i in range(nx):
            for k in range(nz):
                q = [vid(i, j, k), vid(i + 1, j, k), vid(i + 1, j, k + 1), vid(i, j, k + 1)]
                faces.append(q if s < 0 else q[::-1])
    for k, s in ((0, -1), (nz, 1)):
        for i in range(nx):
            for j in range(ny):
                q = [vid(i, j, k), vid(i + 1, j, k), vid(i + 1, j + 1, k), vid(i, j + 1, k)]
                faces.append(q if s > 0 else q[::-1])
    return np.array(pts, float), faces

def bevel_params(half, r, inner):
    """Flat-face rows end where the rounding starts: two soft bevel facets per edge."""
    b = max(0.12, 1 - r / half)
    return [-1.0] + list(np.linspace(-b, b, inner + 1)) + [1.0]

def warp_params(n):
    return list(np.tan(np.linspace(-1, 1, n + 1) * math.pi / 4))

def march(field, origin, dirs, tmax, steps=260):
    origin = np.asarray(origin, float)
    assert field(origin[None])[0] < 0, 'ray origin must be inside the surface'
    n = len(dirs); dt = tmax / steps
    hit = np.full(n, np.nan)
    for i in range(1, steps + 1):
        todo = np.isnan(hit)
        if not todo.any():
            break
        out = field(origin + dirs[todo] * (i * dt)) > 0
        hit[np.nonzero(todo)[0][out]] = i * dt
    assert not np.isnan(hit).any(), 'ray missed the surface'
    lo, hi = hit - dt, hit.copy()
    for _ in range(30):
        mid = (lo + hi) / 2
        out = field(origin + dirs * mid[:, None]) > 0
        hi = np.where(out, mid, hi); lo = np.where(out, lo, mid)
    return origin + dirs * ((lo + hi) / 2)[:, None]

def grad(field, p, e=1e-3):
    g = np.zeros_like(p)
    for i in range(3):
        d = np.zeros(3); d[i] = e
        g[:, i] = field(p + d) - field(p - d)
    return g / np.maximum(_len(g)[:, None], 1e-12)

def implicit_piece(field, centre, half, params, rot=None, tmax=None):
    rot = np.eye(3) if rot is None else np.asarray(rot, float)
    pts, faces = lattice(*params)
    L = pts * np.asarray(half, float)
    d = (L / _len(L)[:, None]) @ rot.T
    pos = march(field, centre, d, tmax or 2.8 * max(half))
    return pos, faces, grad(field, pos)

def box_field(centre, rot, half_top, half_bot, c, r):
    """Rounded block in a local frame; local +z runs from the top (-c) to the bottom (+c)."""
    centre = np.asarray(centre, float); rot = np.asarray(rot, float)
    ht = np.asarray(half_top, float); hb = np.asarray(half_bot, float)
    def f(p):
        q = (p - centre) @ rot
        s = np.clip((q[:, 2] + c) / (2 * c), 0, 1)[:, None]
        b = np.concatenate([ht + (hb - ht) * s, np.full((len(q), 1), c)], 1)
        return sd_round_box(q, b, r)
    return f

def block(centre, rot, half_top, half_bot, c, r, inner=(1, 1, 3)):
    f = box_field(centre, rot, half_top, half_bot, c, r)
    hm = [(half_top[0] + half_bot[0]) / 2, (half_top[1] + half_bot[1]) / 2, c]
    params = [bevel_params(hm[i], r, inner[i]) for i in range(3)]
    return implicit_piece(f, centre, hm, params, rot)

def tube(points, radii, nside, ref, tip=True, roll=0.0):
    """Closed rounded tube along points (fingers, neck). Analytic normals."""
    P = [np.asarray(p, float) for p in points]; n = len(P)
    verts, norms, faces = [], [], []
    for k in range(n):
        t = unit(P[min(k + 1, n - 1)] - P[max(k - 1, 0)])
        u = unit(np.cross(ref, t)); v = np.cross(t, u)
        for i in range(nside):
            a = 2 * math.pi * i / nside + roll
            radial = math.cos(a) * u + math.sin(a) * v
            verts.append(P[k] + radii[k] * radial); norms.append(radial)
    for k in range(n - 1):
        for i in range(nside):
            j = (i + 1) % nside
            faces.append([k * nside + i, k * nside + j, (k + 1) * nside + j, (k + 1) * nside + i])
    faces.append(list(range(nside))[::-1])
    last = (n - 1) * nside
    if tip:
        t = unit(P[-1] - P[-2]); verts.append(P[-1] + t * radii[-1] * 0.55); norms.append(t)
        tipv = len(verts) - 1
        for i in range(nside):
            faces.append([last + i, last + (i + 1) % nside, tipv])
    else:
        faces.append(list(range(last, last + nside)))
    return np.array(verts), faces, np.array(norms)

def shell_grid(outer, inner, wrap):
    """Closed cloth shell from matching outer/inner grids (rows x cols x 3)."""
    R, Cn = outer.shape[:2]; n0 = R * Cn
    o = lambda j, i: j * Cn + (i % Cn)
    q = lambda j, i: n0 + j * Cn + (i % Cn)
    ci = Cn if wrap else Cn - 1
    faces = []
    for j in range(R - 1):
        for i in range(ci):
            faces.append([o(j, i), o(j, i + 1), o(j + 1, i + 1), o(j + 1, i)])
            faces.append([q(j, i), q(j + 1, i), q(j + 1, i + 1), q(j, i + 1)])
    edges = []
    for i in range(ci):
        edges += [((0, i), (0, i + 1)), ((R - 1, i + 1), (R - 1, i))]
    if not wrap:
        for j in range(R - 1):
            edges += [((j + 1, 0), (j, 0)), ((j, Cn - 1), (j + 1, Cn - 1))]
    for a, b in edges:
        faces.append([o(*a), o(*b), q(*b), q(*a)])
    return np.concatenate([outer.reshape(-1, 3), inner.reshape(-1, 3)]), faces

def tongues(x, centres, amps, halfwidth):
    """Rounded hanging rag tongues: cos^2 bumps, broad flat valleys, no sawtooth."""
    out = np.zeros_like(x)
    for c, a in zip(centres, amps):
        d = np.abs(x - c) / halfwidth
        out = np.maximum(out, np.where(d < 1, a * np.cos(d * math.pi / 2) ** 2, 0))
    return out

def squircle(theta, w, d, n=3.2):
    c, s = np.cos(theta), np.sin(theta)
    return np.stack([w / 2 * np.sign(c) * np.abs(c) ** (2 / n), d / 2 * np.sign(s) * np.abs(s) ** (2 / n)], -1)

def rag_tube(centres, sizes, rot, nprof, hem_drop, thick, seed_roll=0.0):
    """Torn cloth tube: rings top->bottom along rot[:,2]; last ring hangs by hem_drop(theta)."""
    rot = np.asarray(rot, float); u, v, w = rot[:, 0], rot[:, 1], rot[:, 2]
    th = np.linspace(0, 2 * math.pi, nprof, endpoint=False) + seed_roll
    drop = hem_drop(th)
    outer, inner, hem = [], [], []
    R = len(centres)
    for j, (c, (sw, sd)) in enumerate(zip(centres, sizes)):
        po = squircle(th, sw, sd); pi_ = squircle(th, sw - 2 * thick, sd - 2 * thick)
        extra = drop if j == R - 1 else (drop * 0.25 if j == R - 2 else 0 * drop)
        c = np.asarray(c, float)
        outer.append(c + po[:, :1] * u + po[:, 1:] * v + extra[:, None] * w)
        inner.append(c + pi_[:, :1] * u + pi_[:, 1:] * v + extra[:, None] * w)
        hem.append(np.full(nprof, j / (R - 1)))
    verts, faces = shell_grid(np.array(outer), np.array(inner), True)
    hem = np.concatenate([np.concatenate(hem)] * 2)
    return verts, faces, hem

# ------------------------------------------------------------------- section accumulation
SECTIONS = ['LowerTorso', 'UpperTorso', 'Head']
for _side in ('Left', 'Right'):
    SECTIONS += [_side + n for n in ('UpperArm', 'LowerArm', 'Hand', 'UpperLeg', 'LowerLeg', 'Foot')]
OBJECTS = SECTIONS + ['EyeGlow']
SKIN, RAG, TEETH, GLOW = 0, 1, 2, 3
acc = {name: {'v': [], 'f': [], 'reg': [], 'hem': [], 'n': [], 'count': 0} for name in OBJECTS}

def add(section, pos, faces, region, nrm=None, hem=None):
    A = acc[section]; base = A['count']
    pos = np.asarray(pos, float)
    A['v'].append(pos); A['f'] += [[base + i for i in f] for f in faces]
    A['reg'] += [region] * len(faces)
    A['hem'].append(np.zeros(len(pos)) if hem is None else np.asarray(hem, float))
    A['n'].append(np.zeros((len(pos), 3)) if nrm is None else np.asarray(nrm, float))
    A['count'] += len(pos)

JOINTS = {}
def joint(name, parent, head, tail):
    JOINTS[name] = dict(parent=parent, head=[round(float(x), 4) for x in head], tail=[round(float(x), 4) for x in tail])

# ----------------------------------------------------------------------------- joints
ROOT, WAIST, NECK = (0, 0.05, 1.55), (0, 0.0, 1.98), (0, -0.06, 4.78)
joint('LowerTorso', 'HumanoidRootPart', ROOT, WAIST)
joint('UpperTorso', 'LowerTorso', WAIST, NECK)
joint('Head', 'UpperTorso', NECK, (0, -0.10, 6.0))
ARM = {}
for side, s in (('Left', 1), ('Right', -1)):
    S = np.array((s * 2.47, 0.02, 4.12)); E = np.array((s * 2.98, -0.02, 3.40)); Wr = np.array((s * 3.10, -0.10, 2.80))
    D = unit(unit(Wr - E) + np.array((0, 0, -0.25)))
    ARM[side] = (S, E, Wr, D)
    joint(side + 'UpperArm', 'UpperTorso', S, E)
    joint(side + 'LowerArm', side + 'UpperArm', E, Wr)
    joint(side + 'Hand', side + 'LowerArm', Wr, Wr + D * 0.66)
    joint(side + 'UpperLeg', 'LowerTorso', (s * 0.63, 0.05, 1.55), (s * 0.64, 0.0, 0.90))
    joint(side + 'LowerLeg', side + 'UpperLeg', (s * 0.64, 0.0, 0.90), (s * 0.645, -0.02, 0.36))
    joint(side + 'Foot', side + 'LowerLeg', (s * 0.645, -0.02, 0.36), (s * 0.65, -0.62, 0.10))

# ------------------------------------------------------------------- belly (UpperTorso)
CB = np.array((0, -0.05, 2.98))
def body_base(p):
    d = sd_superellipsoid6(p, CB, (2.28, 1.72, 1.57), (2.28, 1.95, 1.55), 2.4)
    d = smin(d, sd_ellipsoid6(p, (0, -0.42, 2.62), (2.0, 1.3, 1.1), (2.0, 1.95, 1.27)), 0.35)
    for s in (1, -1):  # shoulder masses the arms hang from
        d = smin(d, sd_sphere(p, (s * 2.13, 0.02, 4.05), 0.48), 0.35)
    return smin(d, sd_round_cyl_z(p, (0, -0.08), 0.48, 4.0, 4.74, 0.12), 0.22)  # neck/trapezius mound

BLISTERS = []  # (apex, normal, footprint radius, sphere centre, sphere radius)
CBL = np.array((0, -0.2, 2.9))
for direction, a, h in (((-0.42, -0.90, -0.24), 0.78, 0.30),   # big, lower front, character right
                        ((0.80, -0.60, 0.02), 0.64, 0.26),     # side front, character left
                        ((0.08, -0.90, 0.46), 0.56, 0.24)):    # upper front
    apex_base = march(body_base, CBL, unit(direction)[None], 4.0)
    nb = grad(body_base, apex_base)[0]
    Rs = (a * a + h * h) / (2 * h)
    BLISTERS.append((apex_base[0] + nb * h, nb, a, apex_base[0] - nb * (Rs - h), Rs))

def body_field(p):
    d = body_base(p)
    for _, _, _, c, Rs in BLISTERS:
        d = smin(d, sd_sphere(p, c, Rs), 0.10)
    return d

pos, faces, nrm = implicit_piece(body_field, CB, (2.3, 2.1, 1.7), [warp_params(13)] * 3, tmax=3.8)
add('UpperTorso', pos, faces, SKIN, nrm)

# Torn vest: an open shell draped on the shoulders/upper back, front open between the flaps.
A0, NA = 0.50, 60
a_cols = np.linspace(A0, 2 * math.pi - A0, NA)
keys_a = np.array([0.50, 0.72, 1.05, 1.40, 1.75, 2.20, 2.70, math.pi])
keys_t = np.array([0.62, 0.98, 0.95, 1.00, 1.02, 1.28, 1.42, 1.45])
def hem_curve(a):
    a = np.where(a > math.pi, 2 * math.pi - a, a)
    i = np.clip(np.searchsorted(keys_a, a) - 1, 0, len(keys_a) - 2)
    t = (a - keys_a[i]) / (keys_a[i + 1] - keys_a[i]); t = t * t * (3 - 2 * t)
    return keys_t[i] + (keys_t[i + 1] - keys_t[i]) * t
vr = np.random.default_rng(1007)
n_tongue = 13
centres = A0 + 0.18 + (np.arange(n_tongue) + vr.uniform(-0.22, 0.22, n_tongue)) * (2 * math.pi - 2 * A0 - 0.36) / (n_tongue - 1)
amps = vr.uniform(0.05, 0.15, n_tongue)
edge_fade = np.clip((np.minimum(a_cols - A0, 2 * math.pi - A0 - a_cols)) / 0.25, 0, 1)
th_hem = hem_curve(a_cols) + tongues(a_cols, centres, amps, 0.22) * edge_fade
th_col = 0.40 + 0.015 * np.sin(3 * a_cols)
rows_t = np.array([0.0, 0.36, 0.72, 1.0])
outer, inner, vest_hem = [], [], []
CV = np.array((0, -0.05, 2.98))
for t in rows_t:
    th = th_col + (th_hem - th_col) * t
    dirs = np.stack([np.sin(th) * np.sin(a_cols), -np.sin(th) * np.cos(a_cols), np.cos(th)], 1)
    P = march(body_base, CV, dirs, 3.8); N = grad(body_base, P)
    outer.append(P + N * 0.075); inner.append(P - N * 0.02)
    vest_hem.append(np.maximum(t, 1 - edge_fade * 1.0) * np.ones(NA))
vverts, vfaces = shell_grid(np.array(outer), np.array(inner), False)
vhem = np.concatenate([np.concatenate(vest_hem)] * 2)
add('UpperTorso', vverts, vfaces, RAG, None, vhem)

# ------------------------------------------------------------------------------- head
HC = np.array((0, -0.10, 5.425)); HH = np.array((0.68, 0.61, 0.575))
CHEEKS = [np.array((s * 0.64, -0.42, 5.17)) for s in (1, -1)]   # round puffed lobes at the lower head sides
BROWS = [(np.array((s * 0.50, -0.68, 5.71)), np.array((s * 0.07, -0.70, 5.61))) for s in (1, -1)]
def head_field(p):
    d = sd_round_box(p - HC, HH, 0.17)
    for c in CHEEKS:
        d = smin(d, sd_sphere(p, c, 0.39), 0.07)
    for a, b in BROWS:
        d = smin(d, sd_capsule(p, a, b, 0.105), 0.07)
    return d
params = [bevel_params(0.68, 0.17, 8), bevel_params(0.61, 0.17, 6), bevel_params(0.575, 0.17, 7)]
pos, faces, nrm = implicit_piece(head_field, HC, HH, params, tmax=1.8)
add('Head', pos, faces, SKIN, nrm)
pos, faces, nrm = tube([(0, -0.08, 4.45), (0, -0.08, 4.98)], [0.40, 0.40], 10, np.array((1.0, 0, 0)), tip=False)
NECK_RANGE = (acc['Head']['count'], acc['Head']['count'] + len(pos))
add('Head', pos, faces, SKIN, nrm)   # neck seat, hidden inside the trapezius mound
tr = np.random.default_rng(31)
for row, zc, hz, xs in (('upper', 5.235, 0.060, [-0.255, -0.128, 0.0, 0.128, 0.255]),
                        ('lower', 5.112, 0.052, [-0.225, -0.098, 0.030, 0.158, 0.272])):
    for x in xs:
        half = np.array((0.057, 0.06, hz + tr.uniform(-0.008, 0.01)))
        c = np.array((x + tr.uniform(-0.01, 0.01), -0.685, zc + tr.uniform(-0.012, 0.012)))
        R = rot_axis((0, 1, 0), tr.uniform(-7, 7)) @ rot_axis((0, 0, 1), tr.uniform(-5, 5))
        f = box_field(c, R, half[:2], half[:2], half[2], 0.026)
        pos, faces, nrm = implicit_piece(f, c, half, [[-1, 0, 1], [-1, 1], [-1, 0, 1]], R)
        add('Head', pos, faces, TEETH, nrm)
EYES = []
for s in (1, -1):
    c = np.array((s * 0.28, -0.695, 5.53)); R = rot_axis((0, 1, 0), -s * 14)   # proud of the face so Neon reads
    radii = np.array((0.14, 0.06, 0.095))
    f = (lambda c, R, radii: (lambda p: sd_ellipsoid6((p - c) @ R, (0, 0, 0), radii, radii)))(c, R, radii)
    pos, faces, nrm = implicit_piece(f, c, radii, [warp_params(2)] * 3, R)
    add('EyeGlow', pos, faces, GLOW, nrm); EYES.append((c, R, radii))

# ------------------------------------------------------------------------- lower torso
pos, faces, nrm = block((0, 0.10, 1.60), np.eye(3), (0.98, 0.62), (0.98, 0.62), 0.36, 0.15, (4, 1, 1))
add('LowerTorso', pos, faces, RAG, nrm, np.zeros(len(pos)))

# ------------------------------------------------------------------------- arms, hands
for side, s in (('Left', 1), ('Right', -1)):
    S, E, Wr, D = ARM[side]
    rng = np.random.default_rng(71 if s > 0 else 72)
    # Upper arm: thick deltoid tapering to the elbow; top seated inside the shoulder mass.
    W1 = unit(E - S); R1 = frame(W1, (s, 0, 0.3))
    top, bot = S - W1 * 0.32, E + W1 * 0.10
    pos, faces, nrm = block((top + bot) / 2, R1, (0.40, 0.42), (0.31, 0.33), np.linalg.norm(bot - top) / 2, 0.14)
    add(side + 'UpperArm', pos, faces, SKIN, nrm)
    # Torn short sleeve on the upper arm (moves with the arm, tucks under the vest).
    rr = rng.uniform(0, 2 * math.pi); ca = rr + np.arange(5) * 2 * math.pi / 5 + rng.uniform(-0.25, 0.25, 5)
    am = rng.uniform(0.05, 0.12, 5)
    drop = lambda th, ca=ca, am=am: np.maximum.reduce([tongues((th - c + math.pi) % (2 * math.pi) - math.pi, [0], [a], 0.55) for c, a in zip(ca, am)])
    ring_d = [-0.30, -0.04, 0.22, 0.42]
    sizes = [(0.88, 0.92), (0.85, 0.89), (0.81, 0.85), (0.79, 0.83)]   # fitted: ~0.04 proud of the arm
    pos, faces, hem = rag_tube([S + W1 * d for d in ring_d], sizes, R1, 16, drop, 0.045)
    add(side + 'UpperArm', pos, faces, RAG, None, hem)
    # Forearm.
    W2 = unit(Wr - E); R2 = frame(W2, (s, 0, 0))
    top, bot = E - W2 * 0.14, Wr + W2 * 0.06
    pos, faces, nrm = block((top + bot) / 2, R2, (0.31, 0.33), (0.26, 0.28), np.linalg.norm(bot - top) / 2, 0.12)
    add(side + 'LowerArm', pos, faces, SKIN, nrm)
    # Hand: palm block, four fat curled fingers, tucked thumb. Palm faces the belly.
    out = unit(np.array((s, 0.0, 0.0)) - D * (D @ np.array((s, 0.0, 0.0))))
    F = np.cross(D, out) if s > 0 else -np.cross(D, out)
    F = unit(F - D * (F @ D)); F = F if F[1] < 0 else -F
    RH = np.stack([out, F, D], 1)
    pc = Wr + D * 0.25
    pos, faces, nrm = block(pc, RH, (0.19, 0.30), (0.19, 0.30), 0.25, 0.09, (1, 2, 1))
    add(side + 'Hand', pos, faces, SKIN, nrm)
    for off, r, l1, l2 in ((0.205, 0.088, 0.20, 0.14), (0.07, 0.092, 0.22, 0.15),
                           (-0.065, 0.087, 0.20, 0.14), (-0.195, 0.078, 0.16, 0.12)):
        base = pc + D * 0.19 + F * off + out * 0.02
        d1 = unit(D - out * 0.22 + F * off * 0.15); d2 = unit(D * 0.55 - out * 0.85)
        p1 = base + d1 * l1; p2 = p1 + d2 * l2
        pos, faces, nrm = tube([base - d1 * 0.10, p1, p2 - d2 * 0.4 * r], [r * 0.95, r, r * 0.88], 6, F, roll=math.pi / 6)
        add(side + 'Hand', pos, faces, SKIN, nrm)
    base = pc + F * 0.27 - out * 0.06 - D * 0.02
    d1 = unit(F * 0.55 + D * 0.65 - out * 0.30); d2 = unit(D * 0.75 - out * 0.50 + F * 0.15)
    p1 = base + d1 * 0.17; p2 = p1 + d2 * 0.13
    pos, faces, nrm = tube([base - d1 * 0.10, p1, p2 - d2 * 0.04], [0.09, 0.095, 0.085], 6, out, roll=math.pi / 6)
    add(side + 'Hand', pos, faces, SKIN, nrm)

# ------------------------------------------------------------------------------- legs
for side, s in (('Left', 1), ('Right', -1)):
    rng = np.random.default_rng(91 if s > 0 else 92)
    x = s * 0.63
    ca = rng.uniform(0, 2 * math.pi) + np.arange(6) * 2 * math.pi / 6 + rng.uniform(-0.3, 0.3, 6)
    am = rng.uniform(0.05, 0.15, 6)
    drop = lambda th, ca=ca, am=am: np.maximum.reduce([tongues((th - c + math.pi) % (2 * math.pi) - math.pi, [0], [a], 0.5) for c, a in zip(ca, am)])
    R = np.stack([np.array((1.0, 0, 0)), np.array((0, 1.0, 0)) * -1, np.array((0, 0, -1.0))], 1)
    pos, faces, hem = rag_tube([(x, 0.05, 1.95), (x, 0.05, 1.60), (x, 0.04, 1.27), (x, 0.03, 1.00)],
                               [(0.84, 0.88), (0.88, 0.92), (0.90, 0.94), (0.94, 0.98)], R, 20, drop, 0.05)
    add(side + 'UpperLeg', pos, faces, RAG, None, hem)
    pos, faces, nrm = block((s * 0.64, 0.0, 0.67), np.diag((1.0, -1.0, -1.0)), (0.31, 0.33), (0.34, 0.36), 0.37, 0.11)
    add(side + 'LowerLeg', pos, faces, SKIN, nrm)
    pos, faces, nrm = block((s * 0.65, -0.12, 0.20), np.diag((1.0, -1.0, -1.0)), (0.39, 0.60), (0.40, 0.61), 0.20, 0.10, (1, 2, 1))
    add(side + 'Foot', pos, faces, SKIN, nrm)

# ------------------------------------------------------------------- build the objects
material = bpy.data.materials.new('Bloater painted atlas')
material.use_nodes = True
bsdf = material.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Roughness'].default_value = 0.9
bsdf.inputs['Specular IOR Level'].default_value = 0.15
objects = {}
for name in OBJECTS:
    A = acc[name]
    verts = np.concatenate(A['v']); hem = np.concatenate(A['hem']); sdfn = np.concatenate(A['n'])
    head = np.array(JOINTS['Head' if name == 'EyeGlow' else name]['head'])
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v - head) for v in verts], [], A['f'])
    me.update()
    me.attributes.new('region', 'INT', 'FACE').data.foreach_set('value', A['reg'])
    me.attributes.new('hem', 'FLOAT', 'POINT').data.foreach_set('value', hem.astype(np.float32))
    me.attributes.new('sdfn', 'FLOAT_VECTOR', 'POINT').data.foreach_set('vector', sdfn.astype(np.float32).ravel())
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bmesh.ops.triangulate(bm, faces=list(bm.faces), quad_method='BEAUTY', ngon_method='BEAUTY')
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        e.smooth = not (e.is_manifold and e.calc_face_angle(0) > math.radians(40))
    bm.to_mesh(me); bm.free(); me.update()
    corner = np.empty(len(me.loops) * 3, np.float32); me.corner_normals.foreach_get('vector', corner)
    corner = corner.reshape(-1, 3)
    lv = np.empty(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', lv)
    sv = np.empty(len(me.vertices) * 3, np.float32); me.attributes['sdfn'].data.foreach_get('vector', sv)
    sv = sv.reshape(-1, 3)[lv]
    use = np.linalg.norm(sv, axis=1) > 0.5
    corner[use] = sv[use]
    me.normals_split_custom_set([tuple(n) for n in corner])
    me.attributes.remove(me.attributes['sdfn'])
    o = bpy.data.objects.new(name, me); scene.collection.objects.link(o)
    o.location = tuple(head)
    me.materials.append(material)
    objects[name] = o
bpy.context.view_layer.update()

# --------------------------------------------------------------------------------- UVs
bpy.ops.object.select_all(action='DESELECT')
for o in objects.values():
    o.select_set(True)
bpy.context.view_layer.objects.active = objects['UpperTorso']
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(58), island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
bpy.ops.uv.average_islands_scale()
bpy.ops.object.mode_set(mode='OBJECT')
for name, k in (('Head', 1.7), ('EyeGlow', 1.4)):   # more texels for the face
    uvl = objects[name].data.uv_layers.active
    uv = np.empty(len(uvl.data) * 2, np.float32); uvl.data.foreach_get('uv', uv)
    uv = uv.reshape(-1, 2); uv = (uv - uv.mean(0)) * k + uv.mean(0); uvl.data.foreach_set('uv', uv.ravel())
for o in objects.values():
    o.data.uv_layers.active.name = 'PaintedAtlas'
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.pack_islands(rotate=True, margin=0.004, shape_method='CONCAVE')
bpy.ops.object.mode_set(mode='OBJECT')

# ------------------------------------------------------------------- painting helpers
def _hash(ix, iy, iz, seed):
    h = ix * np.int64(374761393) + iy * np.int64(668265263) + iz * np.int64(1274126177) + np.int64(seed) * np.int64(1442695041)
    h = (h ^ (h >> 13)) * np.int64(1274126177)
    h = h ^ (h >> 16)
    return (h & 0xFFFFFF).astype(np.float64) / float(0xFFFFFF)

def vnoise(p, seed):
    pf = np.floor(p); i = pf.astype(np.int64); f = p - pf; u = f * f * (3 - 2 * f)
    res = 0.0
    for dx in (0, 1):
        wx = u[:, 0] if dx else 1 - u[:, 0]
        for dy in (0, 1):
            wy = u[:, 1] if dy else 1 - u[:, 1]
            for dz in (0, 1):
                wz = u[:, 2] if dz else 1 - u[:, 2]
                res = res + wx * wy * wz * _hash(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz, seed)
    return res

def fbm(p, seed, octaves=4):
    tot, amp, norm, q = 0.0, 1.0, 0.0, p
    for o in range(octaves):
        tot = tot + amp * vnoise(q, seed + o * 17); norm += amp; amp *= 0.5; q = q * 2.03 + 3.1
    return tot / norm

def warped(p, seed, scale):
    q = p * scale
    w = np.stack([fbm(q * 0.7, seed + 101, 2), fbm(q * 0.7, seed + 202, 2), fbm(q * 0.7, seed + 303, 2)], 1) - 0.5
    return fbm(q + w * 1.4, seed, 4)

def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)

def mix(a, b, t):
    t = np.asarray(t)[..., None] if np.ndim(t) else t
    return a + (np.asarray(b, float) - a) * t

def col(rgb):
    return np.array([c / 255 for c in rgb], float)

SKIN_C, SKIN_D, SKIN_L, SKIN_O = col((222, 185, 46)), col((176, 136, 30)), col((240, 213, 86)), col((182, 168, 52))
RAG_C, RAG_D, RAG_L, HOLE = col((121, 82, 44)), col((84, 54, 28)), col((150, 107, 62)), col((50, 30, 16))
AMBER_C, AMBER_D, AMBER_L, SHINE = col((246, 176, 42)), col((214, 128, 26)), col((255, 212, 98)), col((255, 247, 214))
SOCKET, MOUTH, LIP, CREASE = col((86, 62, 14)), col((54, 20, 14)), col((140, 86, 26)), col((150, 112, 22))
TEETH_C, TEETH_S, GLOW_C, GLOW_E = col((244, 238, 214)), col((196, 186, 156)), col((255, 246, 168)), col((255, 206, 64))

# ------------------------------------------------------------------ rasterise the atlas
H = W = ATLAS
gpos = np.zeros((H, W, 3), np.float32); gnrm = np.zeros((H, W, 3), np.float32)
ghem = np.zeros((H, W), np.float32); greg = np.full((H, W), -1, np.int16); gobj = np.full((H, W), -1, np.int16)
for oi, name in enumerate(OBJECTS):
    o = objects[name]; me = o.data; me.calc_loop_triangles()
    mw = np.array(o.matrix_world); rot = mw[:3, :3]
    nt = len(me.loop_triangles)
    tl = np.empty(nt * 3, np.int32); me.loop_triangles.foreach_get('loops', tl); tl = tl.reshape(-1, 3)
    tp = np.empty(nt, np.int32); me.loop_triangles.foreach_get('polygon_index', tp)
    uv = np.empty(len(me.loops) * 2, np.float32); me.uv_layers.active.data.foreach_get('uv', uv); uv = uv.reshape(-1, 2) * ATLAS
    co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3) @ rot.T + mw[:3, 3]
    lv = np.empty(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', lv)
    cn = np.empty(len(me.loops) * 3, np.float32); me.corner_normals.foreach_get('vector', cn); cn = cn.reshape(-1, 3) @ rot.T
    reg = np.empty(len(me.polygons), np.int32); me.attributes['region'].data.foreach_get('value', reg)
    hv = np.empty(len(me.vertices), np.float32); me.attributes['hem'].data.foreach_get('value', hv)
    for t in range(nt):
        L = tl[t]; a, b, c = uv[L]
        x0, x1 = int(max(0, math.floor(min(a[0], b[0], c[0]) - 1))), int(min(W - 1, math.ceil(max(a[0], b[0], c[0]) + 1)))
        y0, y1 = int(max(0, math.floor(min(a[1], b[1], c[1]) - 1))), int(min(H - 1, math.ceil(max(a[1], b[1], c[1]) + 1)))
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-9:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l0 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / den
        l1 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / den
        l2 = 1 - l0 - l1
        m = (l0 >= -1e-4) & (l1 >= -1e-4) & (l2 >= -1e-4)
        if not m.any():
            continue
        yy, xx = np.nonzero(m); yy += y0; xx += x0
        w0, w1, w2 = l0[m][:, None], l1[m][:, None], l2[m][:, None]
        V = lv[L]
        gpos[yy, xx] = w0 * co[V[0]] + w1 * co[V[1]] + w2 * co[V[2]]
        gnrm[yy, xx] = w0 * cn[L[0]] + w1 * cn[L[1]] + w2 * cn[L[2]]
        ghem[yy, xx] = (w0 * hv[V[0]] + w1 * hv[V[1]] + w2 * hv[V[2]])[:, 0]
        greg[yy, xx] = reg[tp[t]]; gobj[yy, xx] = oi
covered = greg >= 0
P = gpos[covered].astype(np.float64); Nn = gnrm[covered].astype(np.float64)
Nn /= np.maximum(_len(Nn)[:, None], 1e-9)
R = greg[covered]; OBJ = gobj[covered]; HEM = ghem[covered].astype(np.float64)
print('ATLAS_COVERAGE', round(float(covered.mean()), 3))

# ---------------------------------------------------------------------------- shading
out = np.zeros((len(P), 3))
light = 0.94 + 0.08 * Nn[:, 2] - 0.10 * np.clip(-Nn[:, 2], 0, 1)
grain = 0.97 + 0.06 * fbm(P * 7.0, 9)

# Skin: mustard yellow, broad darker ochre blotches, lighter warm patches, faint olive.
m = R == SKIN
p = P[m]
blot = np.maximum(sstep(0.56, 0.62, warped(p, 11, 0.95)), 0.8 * sstep(0.62, 0.67, warped(p, 23, 2.1)))
lite = sstep(0.55, 0.63, warped(p, 37, 0.7))
olive = sstep(0.58, 0.66, fbm(p * 0.5, 41))
c = np.tile(SKIN_C, (len(p), 1))
c = mix(c, SKIN_L, lite * 0.55); c = mix(c, SKIN_O, olive * 0.35); c = mix(c, SKIN_D, blot * 0.85)
oname = np.array(OBJECTS)[OBJ[m]]
low = (oname == 'UpperTorso') & (p[:, 2] < 2.2)
c[low] = mix(c[low], SKIN_D, sstep(2.2, 1.45, p[low, 2]) * 0.35)
feet = np.char.endswith(oname.astype(str), 'Foot')
c[feet] = mix(c[feet], SKIN_D, sstep(0.09, 0.02, p[feet, 2]) * 0.7)   # sole band
# Blisters on the belly: amber domes with a fused orange fillet, painted gloss.
belly = oname == 'UpperTorso'
Ldir = unit((-0.45, -0.55, 0.70))
for apex, nb, a, _, _ in BLISTERS:
    rel = p[belly] - apex
    along = rel @ nb
    tang = rel - along[:, None] * nb
    t = _len(tang) / a + sstep(-0.45, -0.75, along) * 10
    cb = c[belly]
    inner = sstep(1.08, 0.86, t)
    amber = mix(np.tile(AMBER_D, (len(t), 1)), AMBER_C, sstep(0.95, 0.55, t))
    amber = mix(amber, AMBER_L, sstep(0.55, 0.0, t) * 0.8)
    ring = sstep(1.25, 1.02, t) * (1 - inner)
    cb = mix(cb, AMBER_D * 0.92, ring * 0.55)
    cb = mix(cb, amber, inner)
    hl_dir = Ldir - (Ldir @ nb) * nb; hl_dir = hl_dir / np.linalg.norm(hl_dir)
    hl = _len(tang / a - hl_dir * 0.42)
    cb = mix(cb, SHINE, sstep(0.26, 0.10, hl) * 0.95)
    cb = mix(cb, SHINE, sstep(0.10, 0.04, _len(tang / a - hl_dir * 0.12 + np.cross(nb, hl_dir) * 0.18)) * 0.8)
    rim = _len(tang / a + hl_dir * 0.55)
    cb = mix(cb, AMBER_L, sstep(0.22, 0.05, rim) * inner * 0.45)
    c[belly] = cb
out[m] = c

# Face, painted onto the same continuous skin (front of the head only).
fm = (R == SKIN) & (np.array(OBJECTS)[OBJ] == 'Head') & (P[:, 1] < -0.35)
q = P[fm]; cf = out[fm]; x, z = q[:, 0], q[:, 2]
def seg(px, pz, ax, az, bx, bz):
    vx, vz = bx - ax, bz - az; t = np.clip(((px - ax) * vx + (pz - az) * vz) / (vx * vx + vz * vz), 0, 1)
    return np.hypot(px - ax - t * vx, pz - az - t * vz)
def line(dist, width):
    return sstep(width, width * 0.35, dist)
for s in (1, -1):
    ex, ez, ang = s * 0.28, 5.53, math.radians(14) * s
    dx, dz = x - ex, z - ez
    u_ = dx * math.cos(ang) + dz * math.sin(ang); v_ = -dx * math.sin(ang) + dz * math.cos(ang)
    e = np.hypot(u_ / 0.21, v_ / 0.15)
    cf = mix(cf, SOCKET, sstep(1.05, 0.55, e) * 0.92)
    cf = mix(cf, CREASE * 0.8, line(np.abs(np.hypot(u_ / 0.2, (v_ + 0.03) / 0.17) - 1.25), 0.07) * (v_ < -0.05) * 0.6)
    bx0, bz0, bx1, bz1 = s * 0.50, 5.71, s * 0.07, 5.61
    cf = mix(cf, CREASE * 0.75, line(seg(x, z, bx0, bz0 - 0.115, bx1, bz1 - 0.115), 0.035) * 0.7)
    cf = mix(cf, CREASE * 0.8, line(seg(x, z, s * 0.05, 5.60, s * 0.09, 5.74), 0.018) * 0.8)
    cf = mix(cf, CREASE * 0.85, line(seg(x, z, s * 0.13, 5.37, s * 0.37, 5.10), 0.022) * 0.7)
    cf = mix(cf, SOCKET, sstep(0.04, 0.018, np.hypot(x - s * 0.065, (z - 5.37) * 1.3)))
for zz in (5.82, 5.90):
    wav = zz + 0.015 * np.sin(x * 9)
    cf = mix(cf, CREASE * 0.85, line(np.abs(z - wav), 0.016) * sstep(0.36, 0.22, np.abs(x)) * 0.75)
mx, mz = np.abs(x), z - 5.185
mouth = sd_round_box(np.stack([x, np.zeros_like(x), mz], 1), np.array((0.335, 1.0, 0.135)), 0.06)
cf = mix(cf, LIP, sstep(0.04, 0.0, mouth) * 0.85)
cf = mix(cf, MOUTH, sstep(0.006, -0.012, mouth))
cf = mix(cf, CREASE * 0.85, line(seg(x, z, -0.12, 4.98, 0.12, 4.98), 0.02) * 0.7)
for s in (1, -1):  # warm puff on the cheeks
    cf = mix(cf, col((236, 170, 60)), sstep(0.30, 0.05, np.hypot(x - s * 0.64, z - 5.25)) * 0.25)
out[fm] = cf

# Rags: brown cloth, darker patches, vertical fibre streaks, darker frayed hems, a few holes.
m = R == RAG
p = P[m]; hm = HEM[m]
c = np.tile(RAG_C, (len(p), 1))
c = mix(c, RAG_L, sstep(0.55, 0.65, fbm(p * np.array((5.0, 5.0, 1.2)), 51)) * 0.5)
c = mix(c, RAG_D, sstep(0.55, 0.62, warped(p, 57, 1.5)) * 0.75)
c = mix(c, RAG_D * 0.85, sstep(0.72, 1.0, hm) * 0.55)
c = mix(c, HOLE, sstep(0.70, 0.74, warped(p, 63, 2.6)))
out[m] = c

m = R == TEETH
c = mix(np.tile(TEETH_S, (m.sum(), 1)), TEETH_C, np.clip(-Nn[m, 1], 0, 1) ** 0.7)
c = mix(c, col((176, 150, 96)), sstep(0.65, 0.75, fbm(P[m] * 9, 71)) * 0.4)
out[m] = c
m = R == GLOW
out[m] = mix(np.tile(GLOW_E, (m.sum(), 1)), GLOW_C, np.clip(-Nn[m, 1], 0, 1) ** 2)

shade = np.where((R == GLOW)[:, None], 1.0, (light * grain)[:, None])
img = np.zeros((H, W, 3), np.float64); img[covered] = np.clip(out * shade, 0, 1)
# Bleed colour past every island edge so mips and seams never show background.
filled = covered.copy()
for _ in range(14):
    acc_c = np.zeros_like(img); cnt = np.zeros((H, W))
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        acc_c += np.roll(np.roll(img * filled[..., None], dy, 0), dx, 1); cnt += np.roll(np.roll(filled, dy, 0), dx, 1)
    new = (~filled) & (cnt > 0)
    img[new] = acc_c[new] / cnt[new][:, None]; filled |= new
img[~filled] = SKIN_C
rgba = np.concatenate([img, np.ones((H, W, 1))], 2).astype(np.float32)
image = bpy.data.images.new('BaseColor', ATLAS, ATLAS, alpha=False)
image.pixels.foreach_set(rgba.ravel())
image.filepath_raw = str(TEXD / 'BaseColor.png'); image.file_format = 'PNG'; image.save()
bpy.data.images.remove(image)
texture = bpy.data.images.load(str(TEXD / 'BaseColor.png'))
tex = material.node_tree.nodes.new('ShaderNodeTexImage'); tex.image = texture
material.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])

# ------------------------------------------------------------------- export (rest pose)
bpy.ops.object.select_all(action='DESELECT')
for o in objects.values():
    o.select_set(True)
bpy.context.view_layer.objects.active = objects['UpperTorso']
FBX = OUT / 'BloaterZombie_Import.fbx'
bpy.ops.export_scene.fbx(filepath=str(FBX), use_selection=True, object_types={'MESH'}, bake_anim=False,
                         axis_forward='-Z', axis_up='Y', path_mode='COPY', embed_textures=True,
                         use_armature_deform_only=True)
fbm = OUT / 'BloaterZombie_Import.fbm'; fbm.mkdir(exist_ok=True)
shutil.copy2(TEXD / 'BaseColor.png', fbm / 'BaseColor.png')

# ------------------------------------------------- Studio import data (ZombieImportData schema)
C = Matrix(((-1, 0, 0), (0, 0, 1), (0, 1, 0)))
def rnd(v):
    return [round(float(x), 6) for x in v]
world = {n: [o.matrix_world @ v.co for v in o.data.vertices] for n, o in objects.items()}
def bounds(name):
    pts = [C @ v for v in world[name]]
    lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return (lo + hi) / 2, hi - lo
height = max(v.z for vs in world.values() for v in vs)
ground = min(v.z for vs in world.values() for v in vs)
parts = {}
for n in SECTIONS:
    cen, size = bounds(n); parts[n] = {'center': rnd(cen), 'size': rnd(size)}
cen, size = bounds('EyeGlow')
studio_joints = {n: {'parent': j['parent'], 'head': rnd(C @ Vector(j['head'])), 'tail': rnd(C @ Vector(j['tail']))} for n, j in JOINTS.items()}
ut_c, ut_s = bounds('UpperTorso')
import_data = {'Bloater': {
    'height': float(height), 'joints': studio_joints, 'parts': parts,
    'extras': {'EyeGlow': {'weldTo': 'Head', 'center': rnd(cen), 'size': rnd(size), 'material': 'Neon'}},
    'rootHeight': float(ROOT[2]),
    'inflate': {'part': 'UpperTorso', 'maxScale': INFLATE, 'about': 'UpperTorso part centre', 'center': rnd(ut_c),
                'movesJoints': ['LeftShoulder', 'RightShoulder', 'Neck'], 'headScale': HEAD_INFLATE},
}}
(OUT / 'bloater-import-data.json').write_text(json.dumps(import_data, indent=1))

# ------------------------------------------------------------- quick clearance report
def tri_set(name, mat=None, keep=None):
    o = objects[name]; me = o.data; me.calc_loop_triangles()
    vs = [o.matrix_world @ v.co for v in me.vertices]
    if mat is not None:
        vs = [mat(v) for v in vs]
    tris = [tuple(t.vertices) for t in me.loop_triangles if keep is None or keep(t, vs)]
    return vs, tris
def clearance(a, b):
    va, ta = a; vb, tb = b
    ba, bb = BVHTree.FromPolygons(va, ta, all_triangles=True), BVHTree.FromPolygons(vb, tb, all_triangles=True)
    pairs = len(ba.overlap(bb)); used = {i for t in ta for i in t}
    best = 1e9
    for i in used:
        loc, n, _, d = bb.find_nearest(va[i])
        best = min(best, -d if (va[i] - loc).dot(n) < 0 else d)
    return pairs, round(best, 3)
c_ut = Vector(json.loads(json.dumps(rnd(C @ ut_c))))  # back to Blender space
def inflated(name):
    if name == 'UpperTorso':
        return lambda v: c_ut + (v - c_ut) * INFLATE
    for side in ('Left', 'Right'):
        if name.startswith(side) and ('Arm' in name or 'Hand' in name):
            off = (Vector(JOINTS[side + 'UpperArm']['head']) - c_ut) * (INFLATE - 1)
            return lambda v, off=off: v + off
    if name in ('Head', 'EyeGlow'):
        off = (Vector(JOINTS['Head']['head']) - c_ut) * (INFLATE - 1)
        hc = Vector(rnd(C @ bounds('Head')[0])) + off
        return lambda v, off=off, hc=hc: hc + (v + off - hc) * HEAD_INFLATE
    return None
neck_seat = lambda t, vs: not all(NECK_RANGE[0] <= i < NECK_RANGE[1] for i in t.vertices)
report = {}
for state in ('rest', 'inflated'):
    tf = (lambda n: None) if state == 'rest' else inflated
    belly = tri_set('UpperTorso', tf('UpperTorso'))
    for n in ('LeftHand', 'RightHand', 'LeftLowerArm', 'RightLowerArm', 'EyeGlow'):
        report[f'{state}:{n}'] = clearance(tri_set(n, tf(n)), belly)
    report[f'{state}:Head(face)'] = clearance(tri_set('Head', tf('Head'), neck_seat), belly)
print('CLEARANCE', json.dumps(report))

# ---------------------------------------------------- preview rig + Model.blend
bpy.ops.object.select_all(action='DESELECT')
arm = bpy.data.armatures.new('BloaterZombie_Rig'); rig = bpy.data.objects.new('BloaterZombie_Rig', arm)
scene.collection.objects.link(rig); bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
root = arm.edit_bones.new('HumanoidRootPart'); root.head = ROOT; root.tail = (ROOT[0], ROOT[1], ROOT[2] + 0.25)
for n, j in JOINTS.items():
    b = arm.edit_bones.new(n); b.head = j['head']; b.tail = j['tail']; b.parent = arm.edit_bones[j['parent']]
bpy.ops.object.mode_set(mode='OBJECT')
for n, o in objects.items():
    bone = 'Head' if n == 'EyeGlow' else n
    vg = o.vertex_groups.new(name=bone); vg.add(list(range(len(o.data.vertices))), 1.0, 'REPLACE')
    mod = o.modifiers.new('Rigid segmented body skinning', 'ARMATURE'); mod.object = rig
    mw = o.matrix_world.copy(); o.parent = rig; o.matrix_world = mw
texture.pack()

stage = bpy.data.collections.new('PREVIEW_ONLY'); scene.collection.children.link(stage)
def to_stage(o):
    for cl in list(o.users_collection):
        cl.objects.unlink(o)
    stage.objects.link(o)
def aim(o, p):
    o.rotation_euler = (Vector(p) - o.location).to_track_quat('-Z', 'Y').to_euler()
fl = bpy.data.meshes.new('Preview floor'); fl.from_pydata([(-40, -40, -0.003), (40, -40, -0.003), (40, 40, -0.003), (-40, 40, -0.003)], [], [(0, 1, 2, 3)])
floor = bpy.data.objects.new('Preview floor', fl); stage.objects.link(floor)
fmat = bpy.data.materials.new('Neutral studio floor'); fmat.use_nodes = True
fmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.36, 0.36, 0.35, 1)
fmat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.95
fl.materials.append(fmat)
for nm, loc, power, size, color in (('Key', (-6, -8, 10), 1500, 6, (1.0, 0.96, 0.9)), ('Fill', (8, -5, 5), 520, 6, (0.88, 0.93, 1.0)),
                                    ('Rim', (3, 8, 9), 1100, 5, (1.0, 0.97, 0.92))):
    ld = bpy.data.lights.new(nm, 'AREA'); ld.energy = power; ld.size = size; ld.color = color
    lo = bpy.data.objects.new(nm + ' light', ld); stage.objects.link(lo); lo.location = loc; aim(lo, (0, 0, 3))
scene.world = bpy.data.worlds.new('Neutral grey studio'); scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (0.50, 0.52, 0.55, 1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = 0.8
camd = bpy.data.cameras.new('Preview camera'); cam = bpy.data.objects.new('Preview camera', camd)
stage.objects.link(cam); scene.camera = cam
scene.render.engine = 'BLENDER_EEVEE'
try:
    scene.eevee.taa_render_samples = 48
except Exception:
    pass
try:
    scene.view_settings.view_transform = 'Standard'
except Exception:
    pass
scene.render.image_settings.file_format = 'PNG'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'Model.blend'))

# ------------------------------------------------------------------------- renders
glow = bpy.data.materials.new('EyeGlow preview neon (render only)'); glow.use_nodes = True
gb = glow.node_tree.nodes['Principled BSDF']
gb.inputs['Base Color'].default_value = (1.0, 0.86, 0.3, 1); gb.inputs['Emission Color'].default_value = (1.0, 0.86, 0.3, 1)
gb.inputs['Emission Strength'].default_value = 6.0
objects['EyeGlow'].data.materials[0] = glow
def shot(path, loc, target, ortho=None, lens=50, res=(1024, 1024)):
    cam.location = loc; aim(cam, target)
    camd.type = 'ORTHO' if ortho else 'PERSP'
    if ortho:
        camd.ortho_scale = ortho
    else:
        camd.lens = lens
    scene.render.resolution_x, scene.render.resolution_y = res
    if want(Path(path).stem):
        scene.render.filepath = str(path); bpy.ops.render.render(write_still=True)
shot(PREV / 'Front.png', (0, -30, 3.1), (0, 0, 3.1), 7.4)
shot(PREV / 'Back.png', (0, 30, 3.1), (0, 0, 3.1), 7.4)
shot(PREV / 'Side.png', (30, 0, 3.1), (0, 0, 3.1), 7.4)
shot(PREV / 'ThreeQuarter.png', (30 * math.sin(math.radians(35)), -30 * math.cos(math.radians(35)), 7.5), (0, 0, 3.05), lens=140)
shot(PREV / 'Hero.png', (-5.2, -8.2, 1.5), (0, -0.3, 3.4), lens=36)

# Rest vs 1.3x inflation (runtime contract: UpperTorso scaled about its centre, shoulders and
# neck moved by the same factor, Head x1.08). Front view so arm/belly gaps are readable.
dups = []
for n, o in objects.items():
    tf = inflated(n)
    d = o.copy(); d.data = o.data; d.parent = None; d.modifiers.clear(); stage.objects.link(d)
    mw = o.matrix_world.copy()
    if n == 'UpperTorso':
        mw = Matrix.Translation(c_ut) @ Matrix.Scale(INFLATE, 4) @ Matrix.Translation(-c_ut) @ mw
    elif tf is not None and n in ('Head', 'EyeGlow'):
        off = (Vector(JOINTS['Head']['head']) - c_ut) * (INFLATE - 1)
        hc = Vector(rnd(C @ bounds('Head')[0])) + off
        mw = Matrix.Translation(hc) @ Matrix.Scale(HEAD_INFLATE, 4) @ Matrix.Translation(-hc) @ Matrix.Translation(off) @ mw
    elif tf is not None:
        mw = Matrix.Translation(tf(Vector()) - Vector()) @ mw
    d.matrix_world = Matrix.Translation((4.4, 0, 0)) @ mw
    dups.append(d)
rig.location.x = -4.0
def label(text, loc, size=0.42):
    cu = bpy.data.curves.new(text, 'FONT'); cu.body = text; cu.size = size; cu.align_x = 'CENTER'; cu.extrude = 0.01
    t = bpy.data.objects.new('Label ' + text, cu); stage.objects.link(t); t.location = loc; t.rotation_euler = (math.radians(90), 0, 0)
    lm = bpy.data.materials.new('Label'); lm.use_nodes = True
    lm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.95, 0.95, 0.95, 1)
    cu.materials.append(lm); return t
labels = [label('REST', (-4.0, -3.2, 0.05)), label('1.3x INFLATED', (4.4, -3.4, 0.05))]
shot(PREV / 'Inflated.png', (0.3, -30, 3.6), (0.3, 0, 3.6), 17.0, res=(1024, 760))
for d in dups + labels:
    bpy.data.objects.remove(d)
rig.location.x = 0

# Family/scale lineup with the shipped Baby and Mutant import files (read-only).
baby, mutant = [], []
before = set(bpy.data.objects)
if want('Lineup'):
    bpy.ops.import_scene.fbx(filepath=str(BABY_FBX))
    baby = [o for o in bpy.data.objects if o not in before]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(MUTANT_FBX))
    mutant = [o for o in bpy.data.objects if o not in before]
for o in baby:
    o.location.x -= 4.9
for o in mutant:
    o.location.x += 7.4
labels = [label('Baby 3.5', (-4.9, -2.6, 0.05), 0.5), label('Bloater 6.0', (0, -3.3, 0.05), 0.5), label('Mutant 8.5', (7.4, -2.6, 0.05), 0.5)]
shot(PREV / 'Lineup.png', (2.6 + 8, -40, 7.0), (2.6, 0, 4.2), 18.5, res=(1024, 700))

tris = {n: len(objects[n].data.polygons) for n in OBJECTS}
summary = {'triangles': tris, 'total_triangles': sum(tris.values()), 'height': height, 'ground': ground,
           'belly_width_x': float(ut_s[0]), 'reference_sha256': hashlib.sha256(REF.read_bytes()).hexdigest(),
           'clearance_build_check': report}
print('BLOATER_COMPLETE', json.dumps(summary))
