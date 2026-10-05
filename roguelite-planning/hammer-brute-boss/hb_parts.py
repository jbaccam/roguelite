"""Hammer Brute accessories: hammer, shirt, suspenders + buckles, sash, trousers,
teeth and the glowing eyes. Pure numpy.

Every part is returned as Part(name, V, F, section, bone|None, mat, frame) where
`frame` says which space the vertices are in:
  'rest'    REST world (torso, legs and clothes: identical to REF)
  'hammer'  Hammer bone space (origin = right carry grip on the haft axis,
            +Y along the haft toward the head, +Z = the striking-face normal)

Cloth is built as signed-distance SHELLS over a softened copy of the body
(creases filled the way cloth bridges them), cut by smooth region functions
(neckline, armholes, ragged hems, holes) with smooth-max fillets, so every rim
is a thick rounded edge rather than a sheet edge or a sawtooth.
"""
import copy
import math
import random

import numpy as np

import hb_design as D
from hb_sdf import (Ellipsoid, RoundBox, RoundCone, Planes, FnPrim, box_planes, eval_prims, smin, smax, frame_from,
                    rot_xyz, axis_angle, mesh_prims, mesh_fn, project_to_surface, gradient)


class Part:
    def __init__(self, name, V, F, section, bone=None, mat='skin', frame='rest', rule=None):
        self.name = name
        self.V = np.asarray(V, float)
        self.F = [tuple(int(i) for i in f) for f in F]
        self.section = section
        self.bone = bone            # rigid owner, or None -> weights by `rule`
        self.mat = mat
        self.frame = frame
        self.rule = rule            # weight rule name for non-rigid parts


def _unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


# ============================================================ soft bodies
def _softened(prims, tags, k):
    out = []
    for p in prims:
        if p.tag in tags and p.op == 'union':
            q = copy.copy(p)
            q.k = max(p.k, k)
            out.append(q)
    return out


def soft_torso():
    tags = ('pelvis', 'seat', 'flank', 'belly', 'belly_low', 'chest', 'back_low', 'pec', 'traps', 'trap_side',
            'shoulder', 'lat', 'neck')
    return _softened(D.torso_prims(), tags, 0.85)


def soft_legs():
    tags = ('pelvis', 'seat', 'flank', 'thigh', 'thigh_bulk', 'knee', 'shin', 'calf')
    P = _softened(D.torso_prims(), tags, 0.9)
    for side in ('Right', 'Left'):
        P += _softened(D.leg_prims(side), tags, 0.6)
    return P


def soft_waist():
    tags = ('pelvis', 'seat', 'flank', 'belly_low', 'belly')
    return _softened(D.torso_prims(), tags, 0.8)


def _cyl(P, axis_xy=(0.0, 0.10)):
    """Cylindrical angle (deg, 0 = front, + = character's left) about a vertical axis."""
    return np.degrees(np.arctan2(P[:, 0] - axis_xy[0], -(P[:, 1] - axis_xy[1])))


def tatters(theta, seed, n, amp=(0.15, 0.45), width=(7.0, 13.0), period=360.0):
    """Rounded hanging tatters: the downward extension of a ragged hem at each angle.
    Broad, rounded points of uneven size (never a regular sawtooth)."""
    rnd = random.Random(seed)
    out = np.zeros_like(theta)
    for i in range(n):
        c = period * (i + rnd.uniform(-0.3, 0.3)) / n - period / 2
        a = rnd.uniform(*amp)
        w = rnd.uniform(*width)
        dt = (theta - c + period / 2) % period - period / 2
        t = np.clip(1 - (dt / w) ** 2, 0, 1)
        out = np.maximum(out, a * t ** 1.4)
    return out


# ================================================================== shirt
SHIRT_T = (0.02, 0.13)          # inner / outer offset from the softened torso
HEM_TH = np.array([-180, -130, -100, -70, -45, -20, 0, 20, 45, 70, 100, 130, 180], float)
HEM_Z = np.array([7.15, 7.15, 7.20, 7.55, 8.35, 8.62, 8.62, 8.62, 8.35, 7.55, 7.20, 7.15, 7.15])


def shirt_hem_z(theta):
    return np.interp(theta, HEM_TH, HEM_Z) - tatters(theta, 41, 22, amp=(0.18, 0.62), width=(7.0, 14.0))


def shirt_region(P):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    th = _cyl(P)
    r_hem = shirt_hem_z(th) - z                                  # inside when above the hem
    x_edge = 1.92 + 1.15 * smoothstep(9.7, 8.3, z)                # tank-top armholes (straps under the suspenders)
    r_arm = np.abs(x) - x_edge
    ax = np.minimum(np.abs(x) / 1.22, 1.5)
    front = smoothstep(0.6, -0.4, y)
    z_neck = front * (9.95 + 0.85 * ax ** 1.5) + (1 - front) * (10.6 + 0.9 * ax ** 2)
    r_neck = np.minimum(z - z_neck, 1.22 - np.abs(x))
    r = smax(smax(r_hem, r_arm, 0.10), r_neck, 0.10)
    return r


def shirt_sdf_fn():
    body = soft_torso()
    i0, i1 = SHIRT_T
    mid, half = (i0 + i1) / 2, (i1 - i0) / 2

    def fn(P):
        d = eval_prims(body, P)
        shell = np.abs(d - mid) - half
        return smax(shell, shirt_region(P), 0.045)
    return fn


def shirt_part(h=0.032):
    fn = shirt_sdf_fn()
    V, Q = mesh_fn(fn, (-3.7, -4.1, 6.3), (3.7, 3.1, 12.3), h)
    return Part('Shirt', V, Q, 'Shirt', mat='shirt', rule='shirt')


def shirt_bone_points():
    """{bone: (head, tail, parent)} for the shirt hem bones (REST world)."""
    return {
        'Shirt_Front_1': (np.array([0.0, -2.30, 9.25]), np.array([0.0, -2.75, 8.55]), 'UpperTorso'),
        'Shirt_Front_2': (np.array([0.0, -2.75, 8.55]), np.array([0.0, -3.05, 7.75]), 'Shirt_Front_1'),
        'Shirt_Back': (np.array([0.0, 2.05, 8.55]), np.array([0.0, 2.30, 7.10]), 'UpperTorso'),
    }


# ================================================================ trousers
TROUSER_TOP = 5.45
HEM_LEG = {'Right': 1.82, 'Left': 1.92}
TROUSER_HOLES = [   # (leg, direction from the leg axis (deg around, 0 = front), height, radii (along, around))
    ('Left', 25.0, 3.15, (0.36, 0.48)),
    ('Left', -40.0, 2.55, (0.26, 0.30)),
    ('Right', 15.0, 2.60, (0.30, 0.38)),
    ('Right', 75.0, 3.60, (0.22, 0.26)),
]


def _leg_axis(side, z):
    """Point on the leg's centre line at height z (hip -> knee -> ankle)."""
    H, K, A = D.J[side + 'UpperLeg'], D.J[side + 'LowerLeg'], D.J[side + 'Foot']
    zz = np.asarray(z, float)
    t1 = np.clip((H[2] - zz) / (H[2] - K[2]), 0, 1)
    t2 = np.clip((K[2] - zz) / (K[2] - A[2]), 0, 1)
    up = H[None] + (K - H)[None] * t1[:, None]
    lo = K[None] + (A - K)[None] * t2[:, None]
    return np.where((zz >= K[2])[:, None], up, lo)


def trousers_sdf_fn():
    body = soft_legs()
    holes = []
    for leg, ang, zc, (ra, rc) in TROUSER_HOLES:
        c0 = _leg_axis(leg, [zc])[0]
        a = math.radians(ang) * (1 if leg == 'Left' else -1)
        dr = np.array([math.sin(a), -math.cos(a), 0.0])
        # find the cloth surface along the ray
        ts = np.linspace(0.2, 3.5, 200)
        pts = c0[None] + dr[None] * ts[:, None]
        dd = eval_prims(body, pts)
        k = int(np.argmax(dd > 0.12))
        c = pts[k]
        Rh = frame_from(dr, (0, 0, 1)) @ np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]])
        rnd = random.Random(int(zc * 100) + int(ang))
        # a rip: a jagged chain of narrow slits along a slanted tear line
        tilt = rnd.uniform(-35, 35)
        along = Rh @ np.array([math.cos(math.radians(tilt)), 0.0, math.sin(math.radians(tilt))])
        for j in range(5):
            t = (j - 2) / 2.0
            off = along * t * ra * 0.95 + Rh @ np.array([0, 0, 1.0]) * rnd.uniform(-0.12, 0.12) * ra
            w = rc * (1.0 - 0.45 * abs(t)) * rnd.uniform(0.7, 1.1)
            holes.append(Ellipsoid(c + off, (w, 0.45, ra * 0.42), R=Rh @ rot_xyz(0, tilt + rnd.uniform(-25, 25), 0),
                                   k=0.0))

    def fn(P):
        d = eval_prims(body, P)
        x, z = P[:, 0], P[:, 2]
        thigh = smoothstep(1.6, 3.6, z) * (1 - smoothstep(4.6, 5.6, z))
        inner = 0.05 + 0.08 * thigh
        outer = inner + 0.11
        shell = np.abs(d - (inner + outer) / 2) - (outer - inner) / 2
        r = z - TROUSER_TOP
        # ragged hems per leg
        side_left = x > 0.0
        for side in ('Right', 'Left'):
            sel = side_left if side == 'Left' else ~side_left
            ax = _leg_axis(side, z)
            phi = np.degrees(np.arctan2(P[:, 0] - ax[:, 0], -(P[:, 1] - ax[:, 1])))
            zh = HEM_LEG[side] + 0.10 * np.cos(np.radians(phi)) \
                - tatters(phi, 61 if side == 'Left' else 67, 17, amp=(0.14, 0.42), width=(7.0, 15.0))
            r = np.where(sel, np.maximum(r, zh - z), r)
        out = smax(shell, r, 0.05)
        if holes:
            dh = np.min([hle.sdf(P) for hle in holes], axis=0)
            near = dh < 0.25
            if near.any():
                from hb_paint import value_noise
                rag = np.zeros_like(dh)
                Pn = P[near]
                rag[near] = (value_noise(Pn, 11.0, 5) - 0.5) * 0.10 + (value_noise(Pn, 23.0, 9) - 0.5) * 0.05
                dh = dh + rag
            out = smax(out, -dh, 0.03)
        return out
    return fn


def trousers_part(h=0.034):
    fn = trousers_sdf_fn()
    V, Q = mesh_fn(fn, (-3.6, -3.2, 1.3), (5.2, 2.9, 6.1), h)
    return Part('Trousers', V, Q, 'Trousers', mat='trousers', rule='trousers')


# =================================================================== sash
SASH_Z = (4.92, 5.55)


def sash_sdf_fn():
    body = soft_waist()

    def fn(P):
        d = eval_prims(body, P)
        z = P[:, 2]
        th = _cyl(P)
        fold = 0.02 * np.sin((z - SASH_Z[0]) / 0.34 * 2 * np.pi + 0.7 * np.sin(np.radians(th) * 3))
        inner, outer = 0.09, 0.22 + fold
        shell = np.abs(d - (inner + outer) / 2) - (outer - inner) / 2
        lo = SASH_Z[0] + 0.08 * np.sin(np.radians(th) * 2 + 1.0) - tatters(th, 81, 18, amp=(0.04, 0.16), width=(6, 12))
        hi = SASH_Z[1] + 0.06 * np.sin(np.radians(th) * 3)
        r = np.maximum(lo - z, z - hi)
        return smax(shell, r, 0.06)
    return fn


def sash_part(h=0.03):
    fn = sash_sdf_fn()
    V, Q = mesh_fn(fn, (-3.4, -3.8, 4.2), (3.4, 2.9, 6.2), h)
    return Part('Sash', V, Q, 'Gear', mat='sash', rule='sash')


def sash_tail_part(h=0.025):
    """The torn hanging end of the sash at the front-left, with a knot."""
    legs = soft_legs()
    top = np.array([1.05, -3.05, 5.05])
    pts = []
    for t in np.linspace(0, 1, 9):
        pts.append(top + np.array([0.18 * t, 0.15 * t, -1.75 * t]))
    pts = np.array(pts)
    cloth = lambda P: eval_prims(legs, P) - 0.32
    pts = np.array([p if cloth(p[None])[0] > 0 else project_to_surface(cloth, p[None])[0] for p in pts])
    prims = []
    for i in range(len(pts) - 1):
        w = 0.30 - 0.05 * i / len(pts)
        prims.append(RoundCone(pts[i], pts[i + 1], 0.10, 0.10, k=0.05, squash=(w / 0.10, 0.45), x_hint=(1, 0, 0),
                               bone='LowerTorso'))
    prims.append(Ellipsoid(top + np.array([0.0, 0.05, 0.12]), (0.42, 0.26, 0.30), k=0.12, bone='LowerTorso'))
    # torn, uneven end: two rounded tongues of different length
    end = pts[-1]
    prims.append(RoundCone(end, end + np.array([0.18, 0.05, -0.32]), 0.08, 0.05, k=0.06, squash=(1.6, 0.6),
                           x_hint=(1, 0, 0), bone='LowerTorso'))
    prims.append(RoundCone(end + np.array([-0.15, 0, 0.05]), end + np.array([-0.22, 0.04, -0.16]), 0.08, 0.05, k=0.06,
                           squash=(1.4, 0.6), x_hint=(1, 0, 0), bone='LowerTorso'))
    V, Q = mesh_prims(prims, h)
    return Part('SashTail', V, Q, 'Gear', mat='sash', rule='sash')


# ============================================================== suspenders
STRAP_W = 0.72
STRAP_T = 0.12
BUCKLE_AT = 0.47           # fraction along the front path where the buckle sits


def _catmull(pts, n):
    pts = np.asarray(pts, float)
    P = np.concatenate([pts[:1], pts, pts[-1:]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-2])
    return np.array(out)


def outer_surface_fn():
    """Body skin plus the shirt: what the suspenders lie on."""
    body = [p for p in D.torso_prims() if p.op == 'union']
    shirt = shirt_sdf_fn()

    def fn(P):
        return np.minimum(eval_prims(body, P), shirt(P))
    return fn


def strap_paths():
    out = {}
    for s in (-1, 1):
        side = 'Left' if s > 0 else 'Right'
        ctrl = [(1.35, 2.05, 5.45), (1.45, 2.20, 7.2), (1.55, 1.75, 9.6), (1.62, 0.65, 11.55), (1.70, -1.05, 11.05),
                (1.82, -1.95, 10.05), (1.98, -2.35, 9.0), (2.30, -2.65, 7.8), (2.62, -2.45, 6.6), (2.62, -1.95, 5.45)]
        out[side] = np.array([[s * c[0], c[1], c[2]] for c in ctrl])
    return out


def suspender_parts():
    surf = outer_surface_fn()
    parts = []
    buckles = {}
    for side, ctrl in strap_paths().items():
        P = _catmull(ctrl, 10)
        for it in range(3):
            P = project_to_surface(surf, P, offset=STRAP_T * 0.5 + 0.015)
            Q = P.copy()
            Q[1:-1] = 0.25 * P[:-2] + 0.5 * P[1:-1] + 0.25 * P[2:]
            P = Q
        P = project_to_surface(surf, P, offset=STRAP_T * 0.5 + 0.015)
        N = gradient(surf, P)
        V, F = sweep_profile(P, N, STRAP_W, STRAP_T)
        parts.append(Part('Suspender' + side, V, F, 'Gear', mat='strap', rule='skin'))
        # buckle location: the point at BUCKLE_AT of the path's length, on the chest
        front = np.nonzero(P[:, 1] < -0.6)[0]
        i = int(front[np.argmin(np.abs(P[front, 2] - 9.95))])           # high on the chest, below the slope
        tdir = _unit(P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)])
        nf = _unit(N[i] + np.array([0, -1.0, 0]) * 1.4)                   # plate turned to face forward
        buckles[side] = (P[i] + nf * 0.04, nf, tdir)
    for side, (c, n, t) in buckles.items():
        parts.append(buckle_part(side, c, n, t))
    return parts


def sweep_profile(path, normals, width, thick, n_round=3):
    """Sweep a rounded-rectangle (stadium) cross-section along a path: thick strap
    with soft rolled edges, never a sheet."""
    prof = []
    r = thick / 2
    hw = width / 2 - r
    for k in range(n_round + 1):
        a = -math.pi / 2 + math.pi * k / n_round
        prof.append((hw + r * math.cos(a), r * math.sin(a)))
    for k in range(n_round + 1):
        a = math.pi / 2 + math.pi * k / n_round
        prof.append((-hw + r * math.cos(a), r * math.sin(a)))
    m = len(prof)
    V = []
    n = len(path)
    for i in range(n):
        t = _unit(path[min(i + 1, n - 1)] - path[max(i - 1, 0)])
        up = normals[i] - t * (normals[i] @ t)
        up = _unit(up)
        sd = np.cross(t, up)
        for (a, b) in prof:
            V.append(path[i] + sd * a + up * b)
    F = []
    for i in range(n - 1):
        for k in range(m):
            a = i * m + k
            b = i * m + (k + 1) % m
            F.append((a, b, b + m, a + m))
    F.append(tuple(reversed(range(m))))
    F.append(tuple((n - 1) * m + k for k in range(m)))
    return np.array(V), F


def buckle_part(side, c, n, t):
    """Square iron buckle: a beveled frame plate with a sunk centre and a bar."""
    n = _unit(n)
    t = _unit(t - n * (t @ n))
    w = np.cross(n, t)
    R = np.stack([w, t, n], 1)
    cc = c + n * 0.05
    plate = box_planes(cc, R, (0.50, 0.50, 0.10), bevel=0.08, k=0.02, bone='UpperTorso')
    sunk = box_planes(cc + n * 0.12, R, (0.29, 0.29, 0.11), bevel=0.04, k=0.015, bone='UpperTorso', op='sub')
    bar = box_planes(cc + n * 0.03, R, (0.08, 0.38, 0.06), bevel=0.02, k=0.015, bone='UpperTorso')

    class _B:
        op = 'union'
        k = 0.0
        tag = 'buckle'
        bone = 'UpperTorso'

        def sdf(self, P):
            return np.minimum(smax(plate.sdf(P), -sunk.sdf(P), 0.02), bar.sdf(P))

        def bounds(self):
            return cc - 0.7, cc + 0.7
    V, Q = mesh_prims([_B()], 0.014)
    return Part('Buckle' + side, V, Q, 'Gear', bone='UpperTorso', mat='buckle')


# ================================================================= hammer
def hammer_head_prims():
    """Head of the hammer in Hammer-bone space. A beveled iron block with raised
    square plates on both sides, a square boss over the haft end on the outer
    cheek, a few chipped edges and a FLAT striking face (+Z)."""
    hx = D.HEAD_HALF                                     # (along haft, strike axis, side axis)
    c = np.array([0.0, D.S_RIGHT, D.EYE_OFFSET])
    R = np.stack([np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])], 1)
    # local box axes in bone space: along-haft = Y, strike = Z, side = X
    Rb = np.stack([np.array([0, 1.0, 0]), np.array([0, 0, 1.0]), np.array([1.0, 0, 0])], 1)
    head = box_planes(c, Rb, hx, bevel=D.HEAD_BEVEL, k=0.035, bone='Hammer', tag='head')
    prims = [head]
    for s in (-1, 1):
        pc = c + np.array([s * (hx[2] + 0.07), 0.05, -0.15])
        prims.append(box_planes(pc, Rb, (0.56, 0.60, 0.14), bevel=0.10, k=0.03, bone='Hammer', tag='plate'))
    boss_c = c + np.array([0.0, hx[0] + 0.20, -D.EYE_OFFSET])
    prims.append(box_planes(boss_c, Rb, (0.24, 0.95, 0.58), bevel=0.10, k=0.03, bone='Hammer', tag='boss'))
    # chips: small wedge bites out of edges and corners
    rnd = random.Random(5)
    chips = []
    for i in range(15):
        a = rnd.choice([-1, 1])
        b = rnd.choice([-1, 1])
        e = rnd.randrange(3)
        loc = np.zeros(3)
        dims = [hx[0], hx[1], hx[2]]
        ax = [0, 1, 2]
        ax.remove(e)
        loc[ax[0]] = a * dims[ax[0]] * 0.97
        loc[ax[1]] = b * dims[ax[1]] * 0.97
        loc[e] = rnd.uniform(-0.75, 0.75) * dims[e]
        if e == 1 and abs(loc[e]) > 0.0:
            pass
        p = c + Rb @ loc
        n1 = _unit(Rb @ (np.eye(3)[ax[0]] * a + np.eye(3)[ax[1]] * b + np.array([rnd.uniform(-.3, .3) for _ in range(3)])))
        size = rnd.uniform(0.16, 0.30)
        chips.append(Planes(p, [n1, -n1, _unit(np.cross(n1, Rb[:, e]) + 0.2 * Rb[:, e]),
                                -_unit(np.cross(n1, Rb[:, e]) - 0.2 * Rb[:, e]), Rb[:, e], -Rb[:, e]],
                            [size * 0.5, size * 0.5, size, size, size * 1.2, size * 1.2], k=0.02, bone='Hammer',
                            op='sub', tag='chip'))
    return prims, chips


def hammer_head_fn():
    prims, chips = hammer_head_prims()

    def fn(P):
        v = prims[0].sdf(P)
        for p in prims[1:]:
            v = smin(v, p.sdf(P), 0.05)
        for ch in chips:
            # chips never touch the striking face centre
            v = smax(v, -ch.sdf(P), 0.02)
        return v
    return fn


def haft_profile(y, s_left):
    """Haft radius at bone-space y (the right carry grip is y = 0, the head is +Y)."""
    s = D.S_RIGHT - y                                   # distance from the head centre toward the butt
    r = D.HAFT_R
    for b in D.BANDS:
        pass
    return r


def hammer_parts(s_left):
    """All hammer pieces in Hammer bone space."""
    parts = []
    lo = np.array([-2.0, D.S_RIGHT - D.HEAD_HALF[0] - 0.6, D.EYE_OFFSET - D.HEAD_HALF[1] - 0.3])
    hi = np.array([2.0, D.S_RIGHT + D.HEAD_HALF[0] + 0.7, D.EYE_OFFSET + D.HEAD_HALF[1] + 0.3])
    V, Q = mesh_fn(hammer_head_fn(), lo, hi, 0.028)
    parts.append(Part('HammerHead', V, Q, 'Hammer', bone='Hammer', mat='iron', frame='hammer'))
    s_butt = s_left + 1.55
    y_end = D.S_RIGHT - s_butt                         # butt end (bone y)
    y_top = D.S_RIGHT + D.HEAD_HALF[0] + 0.25           # into the boss
    # wooden haft: an 8-sided, slightly irregular prism
    stations = [y_end + 0.05, y_end + 0.30] + list(np.linspace(y_end + 0.6, y_top - 0.1, 14)) + [y_top]
    sides = 8
    Vh, Fh = [], []
    for si, y in enumerate(stations):
        r = D.HAFT_R * (1.0 + 0.05 * smoothstep(0.0, D.S_RIGHT - 1.6, y))
        for k in range(sides):
            a = 2 * math.pi * k / sides + math.pi / 8
            jit = 1.0 + 0.025 * math.sin(3 * a + 1.3 * si) + 0.015 * math.sin(5 * a - si)
            Vh.append([math.cos(a) * r * jit, y, math.sin(a) * r * jit])
    for si in range(len(stations) - 1):
        for k in range(sides):
            a = si * sides + k
            b = si * sides + (k + 1) % sides
            Fh.append((a, a + sides, b + sides, b))
    Fh.append(tuple(range(sides)))
    Fh.append(tuple(reversed([(len(stations) - 1) * sides + k for k in range(sides)])))
    parts.append(Part('HammerHaft', Vh, Fh, 'Hammer', bone='Hammer', mat='wood', frame='hammer'))
    # iron: collar at the head, near-flush bands, butt cap (rounded SDF rings)
    rings = []
    yc0, yc1 = D.S_RIGHT - D.COLLAR[1], D.S_RIGHT - D.COLLAR[0]
    rings.append(RoundCone((0, yc0, 0), (0, yc1 + 0.2, 0), D.HAFT_R + 0.10, D.HAFT_R + 0.13, k=0.0, bone='Hammer'))
    for b in D.BANDS:
        yb = D.S_RIGHT - b
        rings.append(RoundCone((0, yb - D.BAND_HALF + 0.03, 0), (0, yb + D.BAND_HALF - 0.03, 0),
                               D.HAFT_R + D.BAND_RAISE - 0.03, D.HAFT_R + D.BAND_RAISE - 0.03, k=0.0, bone='Hammer'))
    rings.append(RoundCone((0, y_end + 0.06, 0), (0, y_end + 0.36, 0), D.HAFT_R + D.CAP_RAISE - 0.02,
                           D.HAFT_R + D.CAP_RAISE - 0.04, k=0.0, bone='Hammer'))
    for i, rg in enumerate(rings):
        V, Q = mesh_prims([rg], 0.018)
        parts.append(Part('HammerIron%d' % i, V, Q, 'Hammer', bone='Hammer', mat='band', frame='hammer'))
    return parts


def hammer_corner_points():
    """Corners of the head block and the haft ends (bone space) for ground checks."""
    hx = D.HEAD_HALF
    c = np.array([0.0, D.S_RIGHT, D.EYE_OFFSET])
    pts = [c + np.array([sx * hx[2], sy * hx[0], sz * hx[1]]) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    return np.array(pts)


# =================================================================== face
def teeth_parts():
    """Broken, jagged teeth set in the snarl: chunky beveled blocks, some snapped
    at a slant, one missing (gaps), as in the reference."""
    Hd = D.Hd
    rnd = random.Random(17)
    parts = []
    # (x, width, height, slant deg, broken fraction)
    upper = [(-0.58, 0.18, 0.17, 8, 0.0), (-0.36, 0.22, 0.23, -6, 0.4), (-0.12, 0.23, 0.25, 4, 0.0),
             (0.32, 0.22, 0.22, -10, 0.45), (0.54, 0.18, 0.18, 6, 0.0)]
    lower = [(-0.48, 0.19, 0.15, -8, 0.3), (-0.23, 0.21, 0.17, 6, 0.0), (0.04, 0.20, 0.14, -4, 0.5),
             (0.43, 0.20, 0.16, -10, 0.0)]
    for nm, row, z0, sgn, bone in (('TeethUpper', upper, -0.49, -1, 'Head'), ('TeethLower', lower, -0.95, 1, 'Jaw')):
        prims = []
        for x, w, hgt, slant, brk in row:
            y = -1.17 + 0.10 * (x / 0.65) ** 2
            c = Hd(x, y, z0 + sgn * hgt * 0.5)
            R = rot_xyz(rnd.uniform(-6, 6), slant * 0.4, rnd.uniform(-5, 5))
            prims.append(box_planes(c, R, (w * 0.5, 0.075, hgt * 0.5 + 0.06), bevel=0.035, k=0.01, bone=bone))
            if brk > 0:
                # snapped tip: a slanted plane cut through the free end
                n = _unit(R @ np.array([math.sin(math.radians(slant * 2.5)), 0.15, sgn * 1.0]))
                tip = c + R @ np.array([0, 0, sgn * (hgt * 0.5 - brk * hgt * 0.6)])
                prims.append(Planes(tip, [n], [0.0], k=0.0, bone=bone, op='sub'))
        un = [p for p in prims if p.op == 'union']
        subs = [p for p in prims if p.op == 'sub']
        # a sub after each union applies to all; restrict cuts to their own tooth
        fns = []
        for i, p in enumerate(un):
            cut = [s for s in subs if np.linalg.norm(s.c - p.c) < 0.3]
            fns.append((p, cut))

        class _T:
            op = 'union'
            k = 0.0
            tag = 'teeth'

            def __init__(s, fns):
                s.fns = fns
                cs = np.array([p.c for p, _ in fns])
                s.lo, s.hi = cs.min(0) - 0.35, cs.max(0) + 0.35

            def sdf(s, P):
                v = np.full(P.shape[:-1], 1e3)
                for p, cut in s.fns:
                    d = p.sdf(P)
                    for c_ in cut:
                        d = np.maximum(d, -c_.sdf(P))
                    v = np.minimum(v, d)
                return v

            def bounds(s):
                return s.lo, s.hi
        tt = _T(fns)
        V, Q = mesh_prims([tt], 0.012)
        parts.append(Part(nm, V, Q, 'Head', bone=bone, mat='tooth'))
    return parts


EYE_R = 0.18


def eye_centres():
    return [D.Hd(s * 0.45, -1.165, -0.07) for s in (-1, 1)]


EYE_LID_SLOPE = 22.0       # deg: the upper lid line drops toward the nose (angry squint)


def eye_lens_fn(c, side):
    lens = Ellipsoid(c, (0.20, 0.05, 0.15), k=0.0, bone='Head')
    t = math.tan(math.radians(EYE_LID_SLOPE))
    s = 1.0 if side > 0 else -1.0

    def fn(P):
        lid = (P[..., 2] - c[2] - 0.045 - t * s * (P[..., 0] - c[0])) / math.sqrt(1 + t * t)
        return smax(lens.sdf(P), lid, 0.012)
    return fn


def eye_parts():
    Vs, Fs, base = [], [], 0
    for c, side in zip(eye_centres(), (-1, 1)):
        V, Q = mesh_fn(eye_lens_fn(c, side), c - 0.3, c + 0.3, 0.012)
        Vs.append(V)
        Fs += [tuple(int(i) + base for i in f) for f in Q]
        base += len(V)
    V, Q = np.concatenate(Vs), Fs
    return [Part('EyeGlow', V, Q, 'EyeGlow', mat='eye', rule='eye')]


# ================================================================== all
def cloth_parts():
    return [shirt_part(), trousers_part(), sash_part(), sash_tail_part()] + suspender_parts()


def face_parts():
    return teeth_parts() + eye_parts()
