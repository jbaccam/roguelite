"""Frost Cyclops accessories: club, wraps, belt, buckle, loincloth, fur mantle,
teeth, tusks, eye. Pure numpy; every part is returned as

    Part(name, V (n,3), F (m,3|4 list), section, bone | weights, smooth=False)

in the REFERENCE pose. `to_rest(part)` maps arm-attached parts into the rest pose.
Volumetric parts (stone, buckle, tusks) are surface-nets meshes of SDFs so
their bevels come out soft; sheet parts (straps, bands, loincloth, tufts) are
built directly.
"""
import math
import random

import numpy as np

import fc_design as D
from fc_sdf import (Grid, surface_nets, Ellipsoid, RoundBox, RoundCone, eval_prims, frame_from, axis_angle,
                    rot_xyz, smin, smax)


class Part:
    def __init__(self, name, V, F, section, bone=None, weights=None, kind='mesh', mat='default', attach=None):
        self.name = name
        self.V = np.asarray(V, float)
        self.F = [tuple(int(i) for i in f) for f in F]
        self.section = section
        self.bone = bone          # rigid owner, or None -> weights
        self.weights = weights    # {bone: array(n)} when not rigid
        self.kind = kind
        self.mat = mat
        self.attach = attach      # 'RightArm' / 'LeftArm' for rest-pose transform


def _unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def sdf_mesh(prims, h, pad=0.2):
    lo = np.full(3, 1e9)
    hi = np.full(3, -1e9)
    for p in prims:
        if p.op != 'union':
            continue
        a, b = p.bounds()
        lo = np.minimum(lo, a)
        hi = np.maximum(hi, b)
    g = Grid(lo - pad, hi + pad, h)
    g.build(prims)
    V, Q = surface_nets(g)
    return V, Q


class Planes:
    """Convex polyhedron as a smooth intersection of half-spaces (soft bevels)."""
    kind = 'planes'

    def __init__(self, center, normals, offsets, k=0.06, bone='Club', op='union', tag=''):
        self.c = np.asarray(center, float)
        self.n = np.asarray(normals, float)
        self.d = np.asarray(offsets, float)
        self.k = k
        self.bone = bone
        self.op = op
        self.tag = tag
        self.r = float(np.max(self.d)) * 1.9

    def sdf(self, P):
        q = P - self.c
        v = q @ self.n[0] - self.d[0]
        for i in range(1, len(self.n)):
            v = smax(v, q @ self.n[i] - self.d[i], self.k)
        return v

    def bounds(self):
        return self.c - self.r - 0.1, self.c + self.r + 0.1


def sweep_rect(path, width, thick, up_fn, closed=False):
    """Sweep a width x thick rectangle along a polyline. up_fn(i, p, t) -> the
    direction the rectangle's 'thick' axis should face (usually the surface normal)."""
    path = [np.asarray(p, float) for p in path]
    n = len(path)
    V = []
    for i, p in enumerate(path):
        if closed:
            t = path[(i + 1) % n] - path[i - 1]
        else:
            t = path[min(i + 1, n - 1)] - path[max(i - 1, 0)]
        t = _unit(t)
        up = up_fn(i, p, t)
        up = _unit(up - t * (up @ t))
        side = np.cross(t, up)
        w = width[i] if hasattr(width, '__len__') else width
        th = thick[i] if hasattr(thick, '__len__') else thick
        for sx, sy in ((-1, 0), (1, 0), (1, 1), (-1, 1)):
            V.append(p + side * (sx * w / 2) + up * (sy * th))
    F = []
    segs = n if closed else n - 1
    for i in range(segs):
        j = (i + 1) % n
        for k in range(4):
            a = i * 4 + k
            b = i * 4 + (k + 1) % 4
            F.append((a, b, j * 4 + (k + 1) % 4, j * 4 + k))
    if not closed:
        F.append((3, 2, 1, 0))
        F.append(tuple((n - 1) * 4 + k for k in range(4)))
    return np.array(V), F


def project_to(prims, P, offset=0.0, iters=6):
    """Move points onto the iso-surface sdf = offset of a primitive set."""
    P = np.array(P, float)
    e = 1e-3
    for _ in range(iters):
        d = eval_prims(prims, P) - offset
        g = np.stack([(eval_prims(prims, P + np.eye(3)[i] * e) - eval_prims(prims, P - np.eye(3)[i] * e)) / (2 * e)
                      for i in range(3)], 1)
        g /= np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-9)
        P = P - g * d[:, None]
    return P, g


def ray_exit(prims, origin, dirs, rmax=4.0, iters=26):
    """First exit of the solid along rays from an interior origin (bisection
    on each ray after a coarse forward scan)."""
    origin = np.asarray(origin, float)
    dirs = np.array([_unit(d) for d in dirs])
    n = len(dirs)
    steps = np.linspace(0.0, rmax, 90)
    lo = np.zeros(n)
    hi = np.full(n, rmax)
    inside_prev = np.ones(n, bool)
    found = np.zeros(n, bool)
    for i in range(1, len(steps)):
        P = origin + dirs * steps[i]
        ins = eval_prims(prims, P) < 0
        hit = inside_prev & ~ins & ~found
        lo[hit] = steps[i - 1]
        hi[hit] = steps[i]
        found |= hit
        inside_prev = ins
    for _ in range(iters):
        m = (lo + hi) / 2
        ins = eval_prims(prims, origin + dirs * m[:, None]) < 0
        lo = np.where(ins, m, lo)
        hi = np.where(ins, hi, m)
    return origin + dirs * ((lo + hi) / 2)[:, None]


def normals_at(prims, P):
    e = 1e-3
    g = np.stack([(eval_prims(prims, P + np.eye(3)[i] * e) - eval_prims(prims, P - np.eye(3)[i] * e)) / (2 * e)
                  for i in range(3)], 1)
    return g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-9)


# ============================================================== club (REF pose)
STONE_R = np.array([1.62, 1.36, 1.86])    # half extents: across, depth, up


def club_frame():
    T, h = D.club_axis()
    up = -h                                    # stone local +Z points back up the haft
    Rs = frame_from(up, (1, 0, 0))
    return T, h, Rs


STRIKE_FACE = 0.78          # flat striking face at this fraction of the stone's half-length


def strike_normal():
    """Outward normal of the stone's flat striking face (REFERENCE-pose world).

    It is the direction that points straight DOWN at the Ground Slam impact
    frame, so the face meets the ground flat. fc_motion.write_strike() solves it
    (source/club_strike.json); before that exists the club's end face is used."""
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parent / 'source' / 'club_strike.json'
    if p.exists():
        return _unit(np.array(json.loads(p.read_text())['normal_ref_world']))
    return D.club_axis()[1]


def strike_offset(n):
    """Distance from the stone centre to the flat face along n (cuts ~22 % in)."""
    return 0.80 * math.sqrt(np.sum((STONE_R * (club_frame()[2].T @ n)) ** 2))


def club_impact_point():
    """Centre of the stone's flat striking face (REFERENCE pose, world)."""
    n = strike_normal()
    return D.club_stone_center() + n * strike_offset(n)


def haft_profile(t):
    """Haft radius at axial distance t from the grip centre (toward the stone)."""
    r0, r1 = D.HAFT_R
    return float(np.interp(t, [-1.38, -1.24, -1.14, 0.75, 1.25, 4.5], [0.43, 0.43, r0, r0, 0.42, r1]))


def club_parts():
    T, h, Rs = club_frame()
    S = D.club_stone_center()
    rnd = random.Random(7)
    # faceted boulder: ~30 large planes around an egg shape, plus a flat striking face
    normals, offs = [], []
    golden = math.pi * (3 - math.sqrt(5))
    N = 30
    for i in range(N):
        zc = 1 - 2 * (i + 0.5) / N
        r = math.sqrt(1 - zc * zc)
        th = golden * i + rnd.uniform(-0.25, 0.25)
        d = np.array([r * math.cos(th), r * math.sin(th), zc])
        d = _unit(d + np.array([rnd.uniform(-.12, .12) for _ in range(3)]))
        sup = math.sqrt(np.sum((STONE_R * d) ** 2))
        n_local = _unit(d / STONE_R ** 2 * STONE_R.max() ** 2)
        normals.append(Rs @ n_local)
        offs.append(sup * rnd.uniform(0.88, 0.97) * (n_local @ d) ** 0.2)
    ns = strike_normal()                               # the flat striking face
    normals.append(ns)
    offs.append(strike_offset(ns))
    stone = Planes(S, normals, offs, k=0.03, bone='Club', tag='stone')
    Vs, Qs = sdf_mesh([stone], 0.05)
    parts = [Part('ClubStone', Vs, Qs, 'Club', bone='Club', kind='sdf', mat='stone', attach='RightArm')]

    # haft: an 8-sided, slightly irregular wooden prism that runs right through
    # the fist (pommel knob past the pinky side) and deep into the stone
    Lend = (S - T) @ h + 0.2
    stations = [-1.38, -1.30, -1.24, -1.14, -0.8, -0.4, 0.0, 0.5, 0.8, 1.3, 1.9, 2.6, 3.3, Lend]
    sides = 8
    Rh = frame_from(h, (1, 0, 0))
    V, F = [], []
    for si, t in enumerate(stations):
        p = T + h * t
        r = haft_profile(t)
        for k in range(sides):
            a = 2 * math.pi * k / sides + 0.2
            jit = 1.0 + 0.05 * math.sin(3 * a + 1.7 * si) + 0.03 * math.sin(5 * a - si)
            V.append(p + Rh @ np.array([math.cos(a) * r * jit, math.sin(a) * r * jit, 0]))
    for si in range(len(stations) - 1):
        for k in range(sides):
            a = si * sides + k
            b = si * sides + (k + 1) % sides
            F.append((a, b, b + sides, a + sides))
    F.append(tuple(reversed(range(sides))))
    F.append(tuple((len(stations) - 1) * sides + k for k in range(sides)))
    parts.append(Part('ClubHaft', V, F, 'Club', bone='Club', mat='wood', attach='RightArm'))
    top = T - h * 1.38
    L = Lend + 1.38

    # straps: an X over the front face plus a band around the top and lashing on the haft
    straps = []
    cam_dir = _unit(np.array([0.05, -1.0, 0.0]))     # stone front faces the camera
    xs = Rs[:, 0]
    zs = Rs[:, 2]
    fwd = _unit(np.cross(zs, xs))
    if fwd @ cam_dir < 0:
        fwd = -fwd

    def ring(axis_a, axis_b, center_off=np.zeros(3), n=40):
        pts = []
        for i in range(n):
            a = 2 * math.pi * i / n
            pts.append(S + center_off + (axis_a * math.cos(a) + axis_b * math.sin(a)) * 3.0)
        return pts

    def on_stone(pts, off=0.035):
        P = ray_exit([stone], S, [np.asarray(p) - S for p in pts], rmax=3.5) 
        g = normals_at([stone], P)
        return P + g * off, g

    # diagonal straps crossing in an X at the centre of the camera-facing side
    # (great circles through that point, tilted +-34 deg from the stone's long axis)
    face = _unit(np.array([0.05, -1.0, 0.12]))
    up_on_face = _unit(zs - face * (zs @ face))
    for tilt in (+34, -34):
        ax = axis_angle(face, tilt) @ up_on_face
        pts = ring(ax, face, n=48)
        P, g = on_stone(pts)
        V, F = sweep_rect(P, 0.40, 0.10, lambda i, p, t: g[i], closed=True)
        parts.append(Part(f'ClubStrap{tilt:+d}', V, F, 'Club', bone='Club', mat='strap', attach='RightArm'))
    # horizontal band near the top of the stone
    c = S + zs * (STONE_R[2] * 0.62)
    pts = [c + (xs * math.cos(a) + fwd * math.sin(a)) * 2.0 for a in np.linspace(0, 2 * math.pi, 40, endpoint=False)]
    P, g = on_stone(pts)
    V, F = sweep_rect(P, 0.36, 0.10, lambda i, p, t: g[i], closed=True)
    parts.append(Part('ClubStrapTop', V, F, 'Club', bone='Club', mat='strap', attach='RightArm'))
    # lashing where the haft enters: two loops around the haft
    enter = (S - T) @ h - STONE_R[2] * 0.72
    for j, t in enumerate((enter - 0.62, enter - 0.28)):
        cp = T + h * t
        r = haft_profile(t) + 0.07
        a0 = Rh[:, 0]
        b0 = Rh[:, 1]
        tilt = axis_angle(a0, 12 if j == 0 else -10)
        pts = [cp + tilt @ ((a0 * math.cos(a) + b0 * math.sin(a)) * r) for a in np.linspace(0, 2 * math.pi, 16, endpoint=False)]
        V, F = sweep_rect(pts, 0.30, 0.09, lambda i, p, t, cp=cp: p - cp, closed=True)
        parts.append(Part(f'ClubLash{j}', V, F, 'Club', bone='Club', mat='strap', attach='RightArm'))
    return parts


# ============================================================== forearm wraps
WRAP_SPEC = {
    # (start distance below the elbow, stop distance above the wrist, relative band lengths, radius pad)
    # The wrap runs down to the wrist so the hand emerges straight from its lower edge.
    'Right': (0.26, 0.02, [0.30, 0.32, 0.38], 0.10),
    'Left': (0.30, 0.02, [0.36, 0.32, 0.32], 0.17),
}


def wrap_parts():
    """Leather wraps: each band is a rounded strap (bulged profile, soft rolled
    edges), slightly tilted, with a wavy irregular edge, overlapping the next."""
    parts = []
    prof_t = [0.0, 0.10, 0.30, 0.50, 0.70, 0.90, 1.0]
    prof_r = [0.015, 0.085, 0.125, 0.140, 0.125, 0.085, 0.015]
    sides = 26
    for side in ('Right', 'Left'):
        E, W = D.J[side + 'LowerArm'], D.J[side + 'Hand']
        ax = _unit(W - E)
        Lf = np.linalg.norm(W - E)
        prims = [p for p in D.arm_prims(side, rest=False)]
        start, stop, rel, pad = WRAP_SPEC[side]
        span = Lf - start - stop
        lens = [r * span / sum(rel) for r in rel]
        t = start
        rnd = random.Random(3 if side == 'Right' else 5)
        for bi, bl in enumerate(lens):
            tilt = axis_angle(frame_from(ax, (0, -1, 0))[:, 0], rnd.uniform(-5, 5))
            bax = tilt @ ax
            Rf = frame_from(bax, (0, -1, 0))
            ph = rnd.uniform(0, 6.28)
            base_r = []
            angs = [2 * math.pi * k / sides for k in range(sides)]
            cmid = E + ax * (t + bl * 0.5)
            for a_ in angs:
                d = Rf @ np.array([math.cos(a_), math.sin(a_), 0])
                lo, hi = 0.0, 2.6
                for _ in range(22):
                    m = (lo + hi) / 2
                    if eval_prims(prims, (cmid + d * m)[None])[0] < 0:
                        lo = m
                    else:
                        hi = m
                base_r.append(lo)
            V, F = [], []
            for ti, (pt, pr) in enumerate(zip(prof_t, prof_r)):
                for k, a_ in enumerate(angs):
                    d = Rf @ np.array([math.cos(a_), math.sin(a_), 0])
                    wav = 0.035 * math.sin(2 * a_ + ph) + 0.02 * math.sin(5 * a_ + 2 * ph)
                    tt = t + bl * pt + (wav if ti in (0, len(prof_t) - 1) else wav * 0.4)
                    c = E + ax * tt
                    V.append(c + d * (base_r[k] + pad * 0.35 + pr + rnd.uniform(-0.006, 0.006)))
            # inner closing ring (hidden against the forearm)
            n0 = len(V)
            for k, a_ in enumerate(angs):
                d = Rf @ np.array([math.cos(a_), math.sin(a_), 0])
                V.append(E + ax * (t + bl * 0.5) + d * (base_r[k] - 0.05))
            nr = len(prof_t)
            for i in range(nr - 1):
                for k in range(sides):
                    k2 = (k + 1) % sides
                    F.append((i * sides + k, i * sides + k2, (i + 1) * sides + k2, (i + 1) * sides + k))
            for k in range(sides):
                k2 = (k + 1) % sides
                F.append(((nr - 1) * sides + k, (nr - 1) * sides + k2, n0 + k2, n0 + k))
                F.append((n0 + k, n0 + k2, k2, k))
            parts.append(Part(f'Wrap{side}{bi}', V, F, 'Gear', bone=side + 'LowerArm', mat='leather',
                              attach=side + 'Arm'))
            t += bl * 0.86
    return parts


def _norm_rows(a):
    return a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-9)


# ================================================================ face parts
def face_parts():
    parts = []
    Hd = D.Hd
    RH = D.RH
    eye_c = D.J['Eye']
    Ve, Qe = sdf_mesh([Ellipsoid(eye_c, (0.31, 0.31, 0.31), k=0.0, bone='Eye')], 0.02)
    parts.append(Part('Eyeball', Ve, Qe, 'Eye', bone='Eye', kind='sdf', mat='eye'))
    # upper eyelid: a shell over the top of the eye, lowered into the glare
    lid = [Ellipsoid(eye_c, (0.345, 0.345, 0.345), k=0.0, bone='EyelidUpper'),
           Ellipsoid(eye_c, (0.318, 0.318, 0.318), k=0.02, op='sub', bone='EyelidUpper'),
           RoundBox(Hd(0.0, -0.66, -0.20), (0.6, 0.6, 0.36), R=RH @ rot_xyz(-18, 0, 0), round_=0.02, k=0.02,
                    op='sub', bone='EyelidUpper'),
           RoundBox(Hd(0.0, -0.20, -0.01), (0.6, 0.30, 0.6), R=RH, round_=0.02, k=0.02, op='sub', bone='EyelidUpper')]
    Vl, Ql = sdf_mesh(lid, 0.02)
    parts.append(Part('EyelidUpper', Vl, Ql, 'Head', bone='EyelidUpper', kind='sdf', mat='lid'))
    # tusks: broad cones rising from the lower-jaw corners, curving slightly in
    for s, base, tip in ((-1, (-0.46, -1.16, -0.86), (-0.46, -1.20, -0.36)),
                         (1, (0.64, -1.14, -0.78), (0.60, -1.20, -0.28))):
        b = Hd(*base)
        t = Hd(*tip)
        mid = (b + t) / 2 + RH @ np.array([s * 0.03, -0.04, 0.0])
        tp = [RoundCone(b, mid, 0.16, 0.12, k=0.04, bone='Jaw'), RoundCone(mid, t, 0.12, 0.025, k=0.04, bone='Jaw')]
        Vt, Qt = sdf_mesh(tp, 0.016)
        parts.append(Part('Tusk%s' % ('L' if s > 0 else 'R'), Vt, Qt, 'Head', bone='Jaw', kind='sdf', mat='tooth'))
    # snarl: a few chunky, uneven upper teeth hanging from the lip (canine-like
    # points at the sides), and three worn lower stumps in front of the tusks
    up = [(-0.21, 0.085, 0.13, -8), (-0.03, 0.075, 0.10, 4), (0.13, 0.08, 0.115, -5), (0.30, 0.09, 0.14, 9)]
    teeth = []
    for x, w, h, tilt in up:
        top = Hd(x, -0.99, -0.44)
        tip = Hd(x + 0.01 * np.sign(tilt), -1.01, -0.44 - h)
        teeth.append(RoundCone(top, tip, w, w * 0.45, k=0.0, bone='Head', x_hint=RH @ np.array([1.0, 0, 0]),
                               squash=(1.0, 0.7)))
    Vt, Qt = sdf_mesh(teeth, 0.014)
    parts.append(Part('TeethUpper', Vt, Qt, 'Head', bone='Head', kind='sdf', mat='tooth'))
    lo = [(-0.12, 0.07, 0.07), (0.06, 0.08, 0.09), (0.24, 0.065, 0.06)]
    teeth = []
    for x, w, h in lo:
        base = Hd(x, -1.02, -0.66)
        tip = Hd(x, -1.03, -0.66 + h)
        teeth.append(RoundCone(base, tip, w, w * 0.6, k=0.0, bone='Jaw', x_hint=RH @ np.array([1.0, 0, 0]),
                               squash=(1.0, 0.7)))
    Vt, Qt = sdf_mesh(teeth, 0.014)
    parts.append(Part('TeethLower', Vt, Qt, 'Head', bone='Jaw', kind='sdf', mat='tooth'))
    return parts


# ================================================================== fur tufts
def tuft_mesh(root, axis, normal, length, width, thick, rnd, curl=0.10):
    """One chunky leaf-shaped fur tuft: a real volume, broad at the base, a
    rounded-pointed tip, a raised centre ridge (two readable top planes),
    shoulders, thick edges and a rounded underside. Faceted on purpose."""
    v = _unit(axis)
    n = _unit(normal - v * (normal @ v))
    u = np.cross(n, v)
    ts = [0.0, 0.16, 0.36, 0.56, 0.76]
    wp = [0.62, 0.95, 1.0, 0.80, 0.44]
    hp = [0.70, 1.0, 1.0, 0.84, 0.56]
    # cross-section (across, up) as fractions of half-width / thickness
    sec = [(0.0, 1.0), (0.55, 0.78), (1.0, 0.30), (0.62, -0.28), (-0.62, -0.28), (-1.0, 0.30), (-0.55, 0.78)]
    V = []
    for i, t in enumerate(ts):
        c = root + v * (length * t) + n * (length * curl * t * t)
        w = width * 0.5 * wp[i] * (1 + rnd.uniform(-0.08, 0.08))
        h = thick * hp[i]
        skew = rnd.uniform(-0.05, 0.05) * width
        for k, (a, b) in enumerate(sec):
            V.append(c + u * (a * w + (skew if k == 0 else 0.0)) + n * (b * h))
    tip = root + v * length + n * (length * curl) + n * (thick * 0.15)
    V.append(tip)
    m = len(sec)
    F = []
    for i in range(len(ts) - 1):
        a0, b0 = i * m, (i + 1) * m
        for k in range(m):
            k2 = (k + 1) % m
            F.append((a0 + k, b0 + k, b0 + k2, a0 + k2))
    last = (len(ts) - 1) * m
    ti = len(V) - 1
    for k in range(m):
        F.append((last + k, ti, last + (k + 1) % m))
    F.append(tuple(reversed(range(m))))           # root cap
    return np.array(V), F


MANTLE_C = D.T(0.0, 0.35, 8.70)        # rays start inside the upper chest
# theta (deg, torso frame, 0 = front, + = character's left), phi_top (collar), phi_bot (outer edge of pelt)
MANTLE_EXTENT = [
    (-180, 70, 18), (-150, 70, 24), (-125, 66, 40), (-105, 60, 52), (-90, 56, 52), (-78, 53, 32),
    (-66, 51, 8), (-54, 49, 16), (-44, 47, 32), (-34, 45, 40),
    (14, 45, 36), (22, 50, 12), (32, 56, -4), (46, 60, -6), (62, 62, 4), (80, 64, 14), (98, 66, 20),
    (125, 66, 20), (150, 70, 18), (180, 70, 18)]
PELT_THICK = [(-180, 1.75), (-135, 1.55), (-110, 1.35), (-90, 1.20), (-70, 1.00), (-50, 0.80), (-33, 0.60),
              (30, 0.60), (45, 0.95), (60, 1.30), (90, 1.45), (120, 1.65), (180, 1.75)]
MANTLE_GAP = (-40, 36)
PELT_TOP = 1.05        # pelt thickness at the collar
PELT_EDGE = 0.35       # ... and at the outer edge


def _interp_ext(th):
    ths = np.array([e[0] for e in MANTLE_EXTENT], float)
    return (np.interp(th, ths, [e[1] for e in MANTLE_EXTENT]),
            np.interp(th, ths, [e[2] for e in MANTLE_EXTENT]))


def _sph(P):
    rel = (np.atleast_2d(P) - MANTLE_C) @ D.RT
    r = np.linalg.norm(rel, axis=1)
    phi = np.degrees(np.arcsin(np.clip(rel[:, 2] / np.maximum(r, 1e-9), -1, 1)))
    th = np.degrees(np.arctan2(rel[:, 0], -rel[:, 1]))
    return th, phi, r


def _sph_dir(theta, phi):
    t, p = math.radians(theta), math.radians(phi)
    return D.RT @ np.array([math.sin(t) * math.cos(p), -math.cos(t) * math.cos(p), math.sin(p)])


class Pelt:
    """The fur mantle's base volume: the torso+arm skin dilated by a thickness
    that tapers from the collar to the edge, clipped to the mantle region."""
    op = 'union'

    def __init__(self, body):
        self.body = body

    def frac(self, P):
        th, phi, r = _sph(P)
        top, bot = _interp_ext(th)
        return th, phi, r, np.clip((top - phi) / np.maximum(1.0, top - bot), 0, 1), top, bot

    def sdf(self, P):
        P = np.atleast_2d(P)
        th, phi, r, fr, top, bot = self.frac(P)
        gap = (th > MANTLE_GAP[0]) & (th < MANTLE_GAP[1])
        region = np.maximum(phi - top, bot - phi) * np.radians(1) * r
        region = np.where(gap, np.maximum(region, 0.5), region)
        db = eval_prims(self.body, P)
        t_top = np.interp(th, [e[0] for e in PELT_THICK], [e[1] for e in PELT_THICK])
        # thin at the collar (so its cut edge never shows behind the head), full over
        # the shoulders, tapering to the outer edge
        rise = np.clip(fr / 0.22, 0, 1)
        rise = rise * rise * (3 - 2 * rise)
        fall = (1 - np.clip((fr - 0.22) / 0.78, 0, 1)) ** 1.4
        thick = np.where(fr < 0.22, 0.18 + (t_top - 0.18) * rise, PELT_EDGE + (t_top - PELT_EDGE) * fall)
        # the thin collar is only needed behind the head; at the sides the pile stays full
        behind = np.clip((np.abs(th) - 100) / 30, 0, 1)
        full = PELT_EDGE + (t_top - PELT_EDGE) * (1 - fr) ** 1.6
        thick = behind * thick + (1 - behind) * full
        self._db = db
        return np.maximum(np.maximum(db - thick, -(db + 0.05)), region)

    def solid(self, P):
        """Body plus pelt: rays from inside the chest exit on the pelt's outer face."""
        v = self.sdf(P)
        return np.minimum(v, self._db)


def mantle_parts(body):
    rnd = random.Random(11)
    pelt = Pelt(body)
    # ---- pelt mesh
    g = Grid(np.array([-6.2, -3.6, 6.8]), np.array([6.8, 3.4, 13.2]), 0.07)
    X = g.points(np.zeros(3, int), g.n).reshape(-1, 3)
    th, phi, r = _sph(X)
    top, bot = _interp_ext(th)
    cand = (phi < top + 8) & (phi > bot - 8)
    vals = np.full(len(X), 1.0)
    vals[cand] = pelt.sdf(X[cand])
    g.v = vals.reshape(g.v.shape).astype(np.float32)
    Vp, Qp = surface_nets(g)
    parts = [Part('MantlePelt', Vp, Qp, 'Fur', weights=None, kind='sdf', mat='fur')]
    # ---- tufts on the pelt surface, in staggered rows from collar to edge
    specs = []
    row = 0
    ph = 70.0
    while ph > -16:
        n_around = max(18, int(2 * math.pi * 3.9 * math.cos(math.radians(ph)) / 0.66))
        off = (row % 2) * 0.5
        for j in range(n_around):
            t = -180 + 360 * (j + off + rnd.uniform(-0.15, 0.15)) / n_around
            if MANTLE_GAP[0] - 2 < t < MANTLE_GAP[1] + 2:
                continue
            tp, bt = _interp_ext(t)
            if ph > tp + 2 or ph < bt + 1:
                continue
            fr = float(np.clip((tp - ph) / max(1.0, tp - bt), 0, 1))
            specs.append((t, ph + rnd.uniform(-1.5, 1.5), fr))
        ph -= 7.5
        row += 1

    class _F:
        op = 'union'
        k = 0.0

        def __init__(s, fn):
            s.fn = fn

        def sdf(s, P):
            return s.fn(P)
    pf = [_F(pelt.solid)]
    dirs = [_sph_dir(t, p) for t, p, _ in specs]
    hits = ray_exit(pf, MANTLE_C, dirs, rmax=8.0)
    nrm = normals_at(pf, hits)
    V_all, F_all = [], []
    base = 0
    for (t, p, fr), hp, n in zip(specs, hits, nrm):
        radial = hp - MANTLE_C
        radial[2] = 0
        radial = _unit(radial)
        grav = np.array([0, 0, -1.0])
        flow = (grav - n * (grav @ n)) * (1.0 + 0.8 * fr) + 0.28 * (radial - n * (radial @ n))
        collar = fr < 0.16 and abs(t) > 55
        if collar:
            flow = (-grav - n * (-grav @ n)) * 0.9 + (radial - n * (radial @ n))   # raised fur collar
        if np.linalg.norm(flow) < 1e-4:
            continue
        flow = _unit(flow)
        droop = math.radians(55 * max(0.0, fr - 0.25) ** 1.2 / 0.75 ** 1.2) if not collar else 0.0
        flow = _unit(flow * math.cos(droop) + np.array([0, 0, -1.0]) * math.sin(droop))
        lift = math.radians(10 + 10 * fr)
        axis = _unit(flow * math.cos(lift) + n * math.sin(lift))
        L = 0.98 + 0.38 * fr + rnd.uniform(-0.10, 0.12)
        Wd = 0.72 + 0.12 * fr + rnd.uniform(-0.05, 0.05)
        root = hp - n * 0.14 - axis * 0.22
        V, F = tuft_mesh(root, axis, n, L, Wd, 0.34, rnd, curl=0.06)
        V_all.append(V)
        F_all += [tuple(k + base for k in f) for f in F]
        base += len(V)
    parts.append(Part('MantleTufts', np.concatenate(V_all), F_all, 'Fur', weights=None, mat='fur'))
    return parts


# ======================================================================= belt
BELT_C = D.Pv(0.0, 0.10, 6.95)
BELT_TILT = 20.0
BELT_FRONT = -9.0     # ring angle of the buckle (deg; the reference buckle sits right of the pelvis centre)
BELT_W = 0.56
BELT_T = 0.15


def belt_ring(body, n=64):
    R = D.RP @ rot_xyz(BELT_TILT, 0, 0)
    a0 = math.radians(BELT_FRONT)
    dirs = [R @ np.array([math.sin(a + a0), -math.cos(a + a0), 0.0]) for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]
    P = ray_exit(body, BELT_C, dirs, rmax=5.0)
    N = normals_at(body, P)
    return P + N * 0.03, N, R


def belt_parts(body):
    P, N, R = belt_ring(body)
    V, F = sweep_rect(P, BELT_W, BELT_T, lambda i, p, t: N[i], closed=True)
    parts = [Part('Belt', V, F, 'Gear', bone='LowerTorso', mat='leather')]
    # octagonal stone buckle at the front
    fwd = _unit(N[0] * np.array([1.0, 1.0, 0.25]))
    c = P[0] + N[0] * 0.06 + fwd * (BELT_T - 0.04)
    up = _unit(np.array([0, 0, 1.0]) - fwd * fwd[2])
    side = np.cross(up, fwd)
    normals, offs = [], []
    hw, hh, th = 0.80, 0.64, 0.24
    for k in range(8):
        a = (k + 0.5) * 2 * math.pi / 8
        d2 = side * math.cos(a) + up * math.sin(a)
        rad = 1.0 / math.sqrt((math.cos(a) / hw) ** 2 + (math.sin(a) / hh) ** 2)
        normals.append(d2)
        offs.append(rad * 0.97)
        cham = _unit(d2 + fwd * 1.1)
        normals.append(cham)
        offs.append((rad * 0.97) * (d2 @ cham) + th * (fwd @ cham) - 0.07)
    normals.append(fwd)
    offs.append(th)
    normals.append(-fwd)
    offs.append(0.10)
    buck = Planes(c, normals, offs, k=0.03, bone='LowerTorso', tag='buckle')
    Vb, Qb = sdf_mesh([buck], 0.02)
    parts.append(Part('Buckle', Vb, Qb, 'Gear', bone='LowerTorso', kind='sdf', mat='buckle'))
    # rivets either side
    for k in (-9, 9):
        i = k % len(P)
        rv = [Ellipsoid(P[i] + N[i] * BELT_T, (0.09, 0.09, 0.09), k=0.0, bone='LowerTorso')]
        Vr, Qr = sdf_mesh(rv, 0.015)
        parts.append(Part('Rivet%+d' % k, Vr, Qr, 'Gear', bone='LowerTorso', kind='sdf', mat='buckle'))
    return parts, (P, N, R)


# ================================================================== loincloth
LOIN_LEN = [(-180, 1.6), (-140, 1.3), (-110, 1.0), (-80, 1.2), (-55, 1.3), (-30, 1.35), (-12, 1.7),
            (0, 2.4), (8, 3.0), (14, 3.3), (22, 2.6), (32, 1.7), (45, 1.3), (62, 1.05), (85, 0.9), (110, 0.95),
            (140, 1.3), (180, 1.6)]


def loincloth_parts(body, ring):
    P, N, R = ring
    n = len(P)
    rnd = random.Random(21)
    down0 = -R[:, 2]
    rows = 9
    thick = 0.075
    cols = []
    for j in range(n):
        th = math.degrees(2 * math.pi * j / n)
        th = (th + 180) % 360 - 180
        L = float(np.interp(th, [e[0] for e in LOIN_LEN], [e[1] for e in LOIN_LEN]))
        # jagged hem: alternate long points and short notches, randomised
        # broad ragged points every third column, shallow notches between
        L *= (1.0 + rnd.uniform(0.10, 0.25)) if j % 3 == 0 else (0.86 + rnd.uniform(-0.06, 0.06))
        top = P[j] + down0 * (BELT_W * 0.42)
        pts = []
        for k in range(rows):
            s_ = L * k / (rows - 1)
            pts.append(top + np.array([0, 0, -1.0]) * s_ * 0.92 + down0 * s_ * 0.08)
        cols.append(pts)
    cols = np.array(cols)          # (n, rows, 3)
    axis_c = BELT_C
    flat = cols.reshape(-1, 3)
    for it in range(4):
        d = eval_prims(body, flat) - 0.10
        radial = flat - axis_c
        radial[:, 2] = 0
        radial = radial / np.maximum(np.linalg.norm(radial, axis=1, keepdims=True), 1e-9)
        push = np.where(d < 0, -d, 0.0)
        flat = flat + radial * push[:, None] * 1.05
    cols = flat.reshape(cols.shape)
    for j in range(n):
        for k in range(1, rows):
            r_prev = cols[j, k - 1] - axis_c
            r_cur = cols[j, k] - axis_c
            hp = np.linalg.norm(r_prev[:2])
            hc = np.linalg.norm(r_cur[:2])
            if hc < hp * 0.985:
                cols[j, k, :2] = axis_c[:2] + r_cur[:2] / max(hc, 1e-9) * hp * 0.985
    nrm = np.zeros_like(cols)
    for j in range(n):
        for k in range(rows):
            tj = cols[(j + 1) % n, k] - cols[j - 1, k]
            tk = cols[j, min(k + 1, rows - 1)] - cols[j, max(k - 1, 0)]
            nrm[j, k] = _unit(np.cross(tk, tj))
    out = cols - axis_c
    out[..., 2] = 0
    flip = (np.sum(nrm * out, axis=-1) < 0)
    nrm[flip] *= -1
    outer = cols
    inner = cols - nrm * thick
    V = np.concatenate([outer.reshape(-1, 3), inner.reshape(-1, 3)])
    off = n * rows
    F = []

    def idx(j, k):
        return (j % n) * rows + k
    for j in range(n):
        for k in range(rows - 1):
            a, b, c, d_ = idx(j, k), idx(j + 1, k), idx(j + 1, k + 1), idx(j, k + 1)
            F.append((a, d_, c, b))
            F.append((a + off, b + off, c + off, d_ + off))
        a, b = idx(j, rows - 1), idx(j + 1, rows - 1)
        F.append((a, b, b + off, a + off))
        a, b = idx(j, 0), idx(j + 1, 0)
        F.append((a, a + off, b + off, b))
    parts = [Part('Loincloth', V, F, 'Gear', weights=None, mat='loin')]
    for k, (j, Ls, w) in enumerate(((3, 1.55, 0.44), (-8, 1.70, 0.40))):
        j = j % n
        top = P[j] + N[j] * (BELT_T + 0.06)
        path = np.array([top + np.array([0, 0, -1.0]) * (Ls * t) + N[j] * (0.10 * t) for t in np.linspace(0, 1, 6)])
        dd = eval_prims(body, path) - 0.30
        path += N[j] * np.maximum(0, -dd)[:, None]
        nj = N[j]
        Vs, Fs = sweep_rect(path, w, 0.09, lambda i, p, t: nj)
        parts.append(Part('BeltTail%d' % k, Vs, Fs, 'Gear', weights=None, mat='leather'))
    return parts


def hipfur_parts(body, ring):
    """Cream fur peeking out at both hips under the belt, partly behind the skirt."""
    P, N, R = ring
    n = len(P)
    rnd = random.Random(31)
    V_all, F_all, base = [], [], 0
    for centre, sgn in ((int(n * 0.27), 1), (int(n * 0.73), -1)):
        for m in range(4):
            j = (centre + m - 1) % n
            p = P[j] - R[:, 2] * (0.30 + 0.22 * (m % 2))
            nn = N[j]
            back = np.cross(nn, [0, 0, 1.0]) * sgn * 0.0
            axis = _unit(np.array([0, 0, -1.0]) + nn * 0.45 + np.array([0, 0.25, 0]))
            V, F = tuft_mesh(p + nn * 0.02, axis, nn, 0.70 + rnd.uniform(-0.10, 0.12), 0.46, 0.20, rnd, curl=0.12)
            V_all.append(V)
            F_all += [tuple(i + base for i in f) for f in F]
            base += len(V)
    return [Part('HipFur', np.concatenate(V_all), F_all, 'Fur', weights=None, mat='fur')]


def all_parts(body_ref):
    parts = club_parts() + wrap_parts() + face_parts()
    torso_arms = [p for p in body_ref if p.bone not in ('Jaw', 'Brow', 'Head')]
    parts += mantle_parts(torso_arms)
    bparts, ring = belt_parts(body_ref)
    parts += bparts + loincloth_parts(body_ref, ring) + hipfur_parts(body_ref, ring)
    return parts


def all_parts_reference():
    body = D.body_prims(rest=False)
    out = {}
    for p in all_parts(body):
        tris = []
        for f in p.F:
            for k in range(1, len(f) - 1):
                tris.append((f[0], f[k], f[k + 1]))
        out[p.name] = (p.V, np.array(tris), p.mat)
    return out
