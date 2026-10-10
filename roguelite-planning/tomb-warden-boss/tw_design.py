"""Tomb Warden design: joints, skeleton, sculpt primitives, bandage bands,
cloth regions, stone fists, broken stone mask, eyes and loincloth flaps.

Pure numpy. Units are studs (1 Blender unit = 1 stud). The character faces
-Y, +Z is up, his left is +X (matches frost-cyclops-boss). The rest pose is
the Idle start pose: every attack clip starts and ends on identity bases.
"""
import math

import numpy as np

import tw_sdf as S

import os

HEIGHT = 8.6
# Everything here is authored in design units (~8.6 tall). The build scales geometry, rig and
# root/pelvis translations by SC at the Blender boundary. SC 1.18 = about 10.2 studs tall (the coffin
# is rebuilt around the Emerge start pose; see requiredCavity in GameChecks.json).
SC = float(os.environ.get('TW_SC', '1.18'))

# gorilla proportions: massive upper body, raised traps (no neck), short thick legs (~34% of height),
# long heavy arms with the fists hanging near the knees
_J = {
    'pelvis': (0.0, 0.10, 3.25),
    'waist': (0.0, 0.05, 4.35),
    'neck': (0.0, -0.28, 6.72),
    'headtop': (0.0, -0.55, 8.55),
    'shoulder': (2.22, 0.12, 6.30),
    'elbow': (2.85, 0.22, 4.45),
    'wrist': (3.08, -0.16, 2.85),
    'handtip': (3.13, -0.33, 1.45),
    'hip': (0.98, 0.10, 2.95),
    'knee': (1.05, -0.10, 1.55),
    'ankle': (1.10, 0.15, 0.52),
    'ball': (1.12, -0.62, 0.22),
    'toe': (1.14, -1.25, 0.20),
}


def J(name, side=None):
    p = np.array(_J[name], float)
    if side == 'Right':
        p[0] = -p[0]
    return p


SIDES = ('Left', 'Right')


def sgn(side):
    return 1.0 if side == 'Left' else -1.0


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


# ---------------------------------------------------------------- skeleton
def _frame(y_axis, x_hint):
    y = unit(y_axis)
    x = np.asarray(x_hint, float)
    x = unit(x - y * (x @ y))
    z = np.cross(x, y)
    return np.stack([x, y, z], 1)


def _hinge(a, b, c):
    """Hinge axis X for a chain a->b->c so that +X rotation flexes."""
    return unit(np.cross(unit(b - a), unit(c - b)))


def skeleton_spec():
    """[(name, parent, head, tail, R(3x3 columns X,Y,Z))] in parent-first order."""
    out = []

    def add(name, parent, head, tail, x_hint):
        head = np.asarray(head, float)
        tail = np.asarray(tail, float)
        out.append((name, parent, head, tail, _frame(tail - head, x_hint)))

    add('Root', None, (0, 0, 0), (0, 0, 1.2), (1, 0, 0))
    add('HumanoidRootPart', 'Root', J('pelvis'), J('pelvis') + (0, 0, 0.9), (1, 0, 0))
    add('LowerTorso', 'HumanoidRootPart', J('pelvis'), J('waist'), (1, 0, 0))
    add('UpperTorso', 'LowerTorso', J('waist'), J('neck'), (1, 0, 0))
    add('Head', 'UpperTorso', J('neck'), J('headtop'), (1, 0, 0))
    for side in SIDES:
        sh, el, wr, ht = J('shoulder', side), J('elbow', side), J('wrist', side), J('handtip', side)
        hx = _hinge(sh, el, wr)
        # clavicle-style helper: takes part of every arm swing so the shoulder blend never spans 170 degrees
        add(side + 'Shoulder', 'UpperTorso', np.array([sgn(side) * 1.12, 0.18, 6.45]), sh, (0, 0, 1))
        add(side + 'UpperArm', side + 'Shoulder', sh, el, hx)
        add(side + 'LowerArm', side + 'UpperArm', el, wr, hx)
        # the stone fist continues the forearm line (wrist locked = identity basis)
        add(side + 'Hand', side + 'LowerArm', wr, wr + unit(wr - el) * 1.4, hx)
    for side in SIDES:
        hp, kn, an, ba, to = J('hip', side), J('knee', side), J('ankle', side), J('ball', side), J('toe', side)
        kx = _hinge(hp, kn, an)
        add(side + 'UpperLeg', 'LowerTorso', hp, kn, kx)
        add(side + 'LowerLeg', side + 'UpperLeg', kn, an, kx)
        add(side + 'Foot', side + 'LowerLeg', an, ba, (1, 0, 0))
        add(side + 'Toes', side + 'Foot', ba, to, (1, 0, 0))
    # half-rotation helpers: same rest frame as the limb bone, they follow half its rotation so the
    # skin blend across shoulder / elbow / knee never spans the full bend (linear-blend skinning collapse)
    for side in SIDES:
        for bone, parent in (('UpperArm', 'Shoulder'), ('LowerArm', 'UpperArm'), ('LowerLeg', 'UpperLeg')):
            name, par, head, tail, R = [e for e in out if e[0] == side + bone][0]
            out.append((side + bone + 'Half', side + parent, head, head + R[:, 1] * 0.35, R))
    name, par, head, tail, R = [e for e in out if e[0] == 'Head'][0]
    out.append(('HeadHalf', 'UpperTorso', head, head + R[:, 1] * 0.35, R))
    add('SashFront1', 'LowerTorso', (0, -1.24, 3.95), (0, -1.36, 2.75), (1, 0, 0))
    add('SashFront2', 'SashFront1', (0, -1.36, 2.75), (0, -1.50, 1.55), (1, 0, 0))
    add('SashBack1', 'LowerTorso', (0, 1.16, 3.95), (0, 1.28, 2.95), (1, 0, 0))
    add('SashBack2', 'SashBack1', (0, 1.28, 2.95), (0, 1.40, 1.95), (1, 0, 0))
    return out


HELPERS = {s + b + 'Half': s + b for s in SIDES for b in ('UpperArm', 'LowerArm', 'LowerLeg')}
HELPERS['HeadHalf'] = 'Head'
HELPER_PARENT_OF_BLEND = {k: v for s in SIDES for k, v in (
    (s + 'UpperArmHalf', s + 'Shoulder'), (s + 'LowerArmHalf', s + 'UpperArm'), (s + 'LowerLegHalf', s + 'UpperLeg'))}
HELPER_PARENT_OF_BLEND['HeadHalf'] = 'UpperTorso'


def hand_rest_dir(side):
    return unit(J('wrist', side) - J('elbow', side))


# ------------------------------------------------------------- body sculpt
BAND_GROUPS = {}


def _band(name, a, b, w, h, n=3, mixb=0.5, phase=0.0, hand=1.0):
    BAND_GROUPS[name] = dict(a=np.asarray(a, float), u=unit(np.asarray(b, float) - np.asarray(a, float)),
                             w=float(w), h=float(h), n=float(n), mixb=float(mixb), phase=float(phase), hand=float(hand))


def body_prims():
    """Sculpt primitives of the bandaged body; each carries a bone and a band group (tag)."""
    P = []
    E, RB, RC = S.Ellipsoid, S.RoundBox, S.RoundCone
    # massive upper body, broad not deep (the folded-arm coffin pose must fit 4.5 deep)
    P += [E((0, 0.12, 3.15), (1.55, 1.00, 0.80), k=0.30, bone='LowerTorso', tag='torso'),
          E((0, -0.05, 3.95), (1.62, 1.05, 0.90), k=0.35, bone='LowerTorso', tag='torso'),
          E((0, 0.05, 5.30), (2.12, 1.02, 1.35), k=0.40, bone='UpperTorso', tag='torso'),
          E((0, 0.25, 6.28), (1.85, 0.84, 0.90), k=0.30, bone='UpperTorso', tag='torso'),
          RC((-0.70, 0.20, 7.00), (0.70, 0.20, 7.00), 0.64, 0.64, k=0.36, bone='UpperTorso', tag='torso'),
          RC((0.70, 0.20, 7.00), (1.55, 0.18, 6.80), 0.64, 0.60, k=0.30, bone='LeftShoulder', tag='torso'),
          RC((-0.70, 0.20, 7.00), (-1.55, 0.18, 6.80), 0.64, 0.60, k=0.30, bone='RightShoulder', tag='torso'),
          E((1.55, 0.35, 5.20), (0.70, 0.66, 1.10), k=0.30, bone='UpperTorso', tag='torso'),
          E((-1.55, 0.35, 5.20), (0.70, 0.66, 1.10), k=0.30, bone='UpperTorso', tag='torso'),
          E((0.86, -0.60, 5.72), (0.90, 0.43, 0.66), k=0.25, bone='UpperTorso', tag='torso'),
          E((-0.86, -0.60, 5.72), (0.90, 0.43, 0.66), k=0.25, bone='UpperTorso', tag='torso')]
    # very short neck buried in the traps; blocky bandaged head behind the stone mask
    P += [RC((0, 0.0, 6.45), (0, -0.25, 6.95), 0.66, 0.60, k=0.30, bone='UpperTorso', tag='neck'),
          RC((0, -0.25, 6.95), (0, -0.40, 7.20), 0.60, 0.58, k=0.25, bone='Head', tag='neck'),
          RB((0, -0.50, 7.78), (0.72, 0.62, 0.74), round_=0.32, k=0.22, bone='Head', tag='head'),
          E((0, -0.45, 7.90), (0.72, 0.64, 0.64), k=0.20, bone='Head', tag='head')]
    for side in SIDES:
        s = sgn(side)
        sh, el, wr = J('shoulder', side), J('elbow', side), J('wrist', side)
        hd = hand_rest_dir(side)
        P += [E(sh + (0.02 * s, -0.02, 0.06), (0.92, 0.88, 0.90), k=0.32, bone=side + 'UpperArm', tag=side + '_uarm'),
              RC(sh, el, 0.80, 0.64, k=0.26, bone=side + 'UpperArm', tag=side + '_uarm'),
              RC(el, wr + hd * 0.14, 0.66, 0.50, k=0.22, bone=side + 'LowerArm', tag=side + '_farm')]
        hp, kn, an = J('hip', side), J('knee', side), J('ankle', side)
        P += [RC(hp, kn, 0.98, 0.78, k=0.32, bone=side + 'UpperLeg', tag=side + '_thigh'),
              RC(kn, an, 0.78, 0.64, k=0.26, bone=side + 'LowerLeg', tag=side + '_shin'),
              E(an + (0, -0.04, 0.02), (0.72, 0.74, 0.46), k=0.22, bone=side + 'Foot', tag=side + '_foot'),
              RB((an[0] + 0.02 * s, -0.12, 0.31), (0.70, 0.80, 0.31), round_=0.22, k=0.18, bone=side + 'Foot',
                 tag=side + '_foot'),
              E((an[0], 0.45, 0.30), (0.58, 0.40, 0.30), k=0.15, bone=side + 'Foot', tag=side + '_foot')]
        for i, (dx, hw, ln) in enumerate(((-0.46, 0.20, 0.30), (-0.12, 0.17, 0.28), (0.20, 0.155, 0.26),
                                          (0.49, 0.14, 0.22))):
            P.append(RB((an[0] + dx * s, -0.98 - (ln - 0.26), 0.21), (hw, ln, 0.21), round_=0.11, k=0.07,
                        bone=side + 'Toes', tag=side + '_toes'))
    return P


def _setup_bands():
    # wide bandage bands: one dominant diagonal family per region (A) with a few crossing bands (B) in
    # broad patches; n = turns' tilt, w = band width (a few clear overlap edges per limb, no fine web)
    _band('torso', (0, 0.05, 2.4), (0, 0.0, 7.4), 0.98, 0.13, n=3, mixb=0.45, phase=0.0)
    _band('neck', (0, 0.0, 6.4), (0, -0.30, 7.3), 0.60, 0.08, n=2, mixb=0.3)
    _band('head', (0, -0.50, 7.0), (0, -0.50, 8.6), 0.55, 0.08, n=2, mixb=0.3, phase=0.3)
    for side in SIDES:
        s = sgn(side)
        _band(side + '_uarm', J('shoulder', side) + (0, 0, 0.6), J('elbow', side), 0.78, 0.12, n=2, mixb=0.35,
              phase=0.2, hand=s)
        _band(side + '_farm', J('elbow', side), J('wrist', side), 0.70, 0.11, n=2, mixb=0.35, phase=0.5, hand=-s)
        _band(side + '_thigh', J('hip', side) + (0, 0, 0.5), J('knee', side), 0.80, 0.12, n=2, mixb=0.35,
              phase=0.1, hand=s)
        _band(side + '_shin', J('knee', side), J('ankle', side) + (0, 0, -0.3), 0.72, 0.11, n=2, mixb=0.3,
              phase=0.6, hand=-s)
        _band(side + '_foot', (J('ankle', side)[0], 0.85, 0.3), (J('ankle', side)[0], -0.9, 0.3), 0.62, 0.08,
              n=2, mixb=0.2, phase=0.35, hand=s)


_setup_bands()


def band_groups_of(prims, P):
    """Band group per point: the group whose primitives are nearest."""
    groups = sorted({p.tag for p in prims})
    D = np.stack([np.min(np.stack([p.sdf(P) for p in prims if p.tag == g], 0), 0) for g in groups], 0)
    return np.array(groups)[np.argmin(D, 0)], D


def _warp(P):
    """Smooth low-frequency warp so wrap widths and angles vary (not machine rows)."""
    return 0.16 * (np.sin(1.3 * P[:, 0] + 0.7 * P[:, 2] + 0.4) + np.sin(1.1 * P[:, 1] + 1.9 * P[:, 2] + 1.0) +
                   0.6 * np.sin(2.3 * P[:, 2] - 0.9 * P[:, 0]))


def band_coords(P, group, family='A'):
    """Helical wrap coordinates for one wrap family: s (shingle coordinate), f = frac(s),
    psi = continuous along-strip angle, r = radius from the axis. P is (n,3)."""
    g = BAND_GROUPS.get(group)
    if g is None:
        n = len(P)
        return np.zeros(n), np.zeros(n), np.zeros(n), np.ones(n)
    u = g['u']
    e1 = np.cross(u, (0, 1, 0)) if abs(u[1]) < 0.9 else np.cross(u, (1, 0, 0))
    e1 = unit(e1)
    e2 = np.cross(u, e1)
    d = P - g['a']
    t = d @ u
    rp = d - np.outer(t, u)
    th = np.arctan2(rp @ e2, rp @ e1)
    r = np.linalg.norm(rp, axis=1)
    hand = g['hand'] * (1.0 if family == 'A' else -1.0)
    n = g['n'] if family == 'A' else max(2.0, g['n'] - 1.0)
    w = g['w'] * (1.0 if family == 'A' else 0.85)
    s = t / w + hand * n * th / (2 * math.pi) + g['phase'] + (_warp(P) if family == 'A' else -0.8 * _warp(P)) \
        + (0.0 if family == 'A' else 0.37)
    m = np.floor(s)
    f = s - m
    psi = hand * th - 2 * math.pi * m / max(n, 1.0)
    return s, f, psi, r


def wrap_layers(P, group):
    """Both families' profiles and which one is on top (with the crossing families visible as X wraps)."""
    g = BAND_GROUPS.get(group)
    if g is None:
        n = len(P)
        return np.zeros(n), np.zeros(n), np.ones(n, bool), np.zeros(n), np.zeros(n)
    sA, fA, _, _ = band_coords(P, group, 'A')
    sB, fB, _, _ = band_coords(P, group, 'B')
    pA, pB = shingle(fA), shingle(fB)
    # family B shows through in broad patches (everywhere on the chest X)
    patch = 0.5 + 0.5 * np.sin(0.9 * P[:, 2] + 1.7 * P[:, 0] + 0.6) * np.cos(0.8 * P[:, 1] - 0.5 * P[:, 2])
    mask = np.clip((patch - (1.0 - g['mixb'])) / 0.25 + 0.5, 0, 1) if g['mixb'] < 1.0 else np.ones(len(P))
    pBe = 0.45 + (pB - 0.45) * mask
    topA = pA >= pBe
    return pA, pBe, topA, sA, sB


def shingle(f):
    """Overlapping-wrap profile in [0.45, 1]: a soft lip at f=0..0.12 (the lower
    edge of the wrap above), then a slow fall to the next lip."""
    lip = 0.45 + 0.55 * smoothstep(0.0, 0.12, f)
    fall = 1.0 - 0.55 * np.clip((f - 0.12) / 0.88, 0, 1)
    return np.where(f < 0.12, lip, fall)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


# ----------------------------------------------------------- cloth regions
SASH_N = unit((3.10, 0.0, -2.85))          # wide sash: left shoulder top to right hip
SASH_D = -(SASH_N @ np.array([1.35, 0.0, 6.95]))
SASH_HALF = 0.50


def sash_sdf(P):
    d = np.abs(P @ SASH_N + SASH_D) - SASH_HALF
    zc = np.maximum(3.6 - P[..., 2], P[..., 2] - 7.45)
    return np.maximum(d, zc)


def waist_center(P):
    return 3.92 + 0.10 * (P[..., 1] / 1.1)


def waist_sdf(P):
    return np.abs(P[..., 2] - waist_center(P)) - 0.38


FLAP_CS = [np.array([1.70, 0.16, 6.78]), np.array([-1.70, 0.16, 6.78])]


# torn linen strips hanging over each shoulder: (angle around the shoulder, 0 = straight out, + = back;
# angular half-width; hang length below the shoulder top)
FLAP_STRIPS = [(-1.05, 0.20, 1.55), (-0.45, 0.22, 1.95), (0.15, 0.21, 1.75), (0.72, 0.19, 1.40)]
FLAP_TOP = 0.18


def _flap_parts(P, c, seed):
    d = P - c
    sx = np.sign(c[0])
    phi = np.arctan2(d[..., 1], d[..., 0] * sx)
    hr = np.maximum(np.hypot(d[..., 0], d[..., 1]), 0.6)
    best = np.full(P.shape[:-1], 9.0)
    Lnear = np.ones(P.shape[:-1])
    angd = np.full(P.shape[:-1], 9.0)
    for k, (pk, hw, L) in enumerate(FLAP_STRIPS):
        a = np.abs(phi - pk) * hr - hw * hr
        # ragged torn end: uneven tongues and notches across the strip
        rag = 0.13 * np.abs(np.sin(9.0 * (phi - pk) / hw + 1.7 * k + seed)) + 0.06 * np.sin(23.0 * phi + 2.1 * k + seed)
        z_end = c[2] - L + rag
        s = np.maximum(a, z_end - P[..., 2])
        near = a < angd
        Lnear = np.where(near, L, Lnear)
        angd = np.minimum(angd, a)
        best = np.minimum(best, s)
    # collar over the top of the shoulder only (not across the chest or back)
    collar = np.maximum((c[2] - FLAP_TOP) - P[..., 2], np.maximum(-1.30 - phi, phi - 1.02) * hr)
    u = np.minimum(best, collar)
    u = np.maximum(u, np.linalg.norm(d, axis=-1) - 2.0)
    u = np.maximum(u, -(P[..., 0] * sx - 0.55))
    t = np.clip((c[2] - FLAP_TOP - P[..., 2]) / np.maximum(Lnear - FLAP_TOP, 0.2), 0, 1)
    return u, t


def flap_sdf(P):
    """Torn hanging linen strips over both shoulders (joined by a collar over the trap top)."""
    return np.minimum(_flap_parts(P, FLAP_CS[0], 0.0)[0], _flap_parts(P, FLAP_CS[1], 1.3)[0])


def flap_hem(P):
    """0 at the collar, 1 at a strip's torn end: the lower strip stands proud (hangs free)."""
    (u0, t0), (u1, t1) = _flap_parts(P, FLAP_CS[0], 0.0), _flap_parts(P, FLAP_CS[1], 1.3)
    return smoothstep(0.35, 1.0, np.where(u0 < u1, t0, t1))


RAISE = {'sash': 0.11, 'waist': 0.18, 'flap': 0.17, 'flap_hem': 0.15}


# ------------------------------------------------------------------ fists
def fist_frame(side):
    """Columns (u knuckle-row, v down the hand, w back-of-hand normal), origin at the wrist."""
    v = hand_rest_dir(side)
    # back of the hand (carved spiral) faces out to the side; the thumb and curled index finger face forward
    w = np.array([sgn(side) * 1.0, -0.20, 0.0])
    w = unit(w - v * (w @ v))
    u = np.cross(v, w)
    return np.stack([u, v, w], 1), J('wrist', side)


class OctPrism(S.Prim):
    """Regular octagon (apothem r) in local x/z, extruded along local y over [y0, y1]."""
    kind = 'octprism'

    def __init__(self, center, R, r, y0, y1, round_=0.05, **kw):
        super().__init__(center, R, **kw)
        self.r = float(r)
        self.y0, self.y1 = float(y0), float(y1)
        self.rr = float(round_)

    def local(self, q):
        k = np.array([-0.9238795325, 0.3826834323, 0.4142135623])
        px, pz = np.abs(q[..., 0]), np.abs(q[..., 2])
        r = self.r - self.rr
        d1 = np.minimum(k[0] * px + k[1] * pz, 0.0)
        px, pz = px - 2 * d1 * k[0], pz - 2 * d1 * k[1]
        d2 = np.minimum(-k[0] * px + k[1] * pz, 0.0)
        px, pz = px + 2 * d2 * k[0], pz - 2 * d2 * k[1]
        px = px - np.clip(px, -k[2] * r, k[2] * r)
        pz = pz - r
        d2d = np.sqrt(px * px + pz * pz) * np.sign(pz)
        ym = 0.5 * (self.y0 + self.y1)
        hy = 0.5 * (self.y1 - self.y0) - self.rr
        dy = np.abs(q[..., 1] - ym) - hy
        w0 = d2d
        return np.minimum(np.maximum(w0, dy), 0.0) + np.sqrt(np.maximum(w0, 0) ** 2 + np.maximum(dy, 0) ** 2) - self.rr

    def extent(self):
        return np.array([self.r * 1.1, max(abs(self.y0), abs(self.y1)), self.r * 1.1])


def _groove_path(pts, R, o, depth_axis, plane_axes, half_w, depth, k=0.02):
    """Grooves (subtracted rounded boxes) along a polyline in a face plane."""
    out = []
    a1, a2 = plane_axes
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        c2 = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
        L = math.hypot(x1 - x0, y1 - y0) / 2 + half_w
        horiz = abs(x1 - x0) > abs(y1 - y0)
        half = np.zeros(3)
        half[a1] = L if horiz else half_w
        half[a2] = half_w if horiz else L
        half[depth_axis] = depth
        c = np.zeros(3)
        c[a1], c[a2] = c2
        c[depth_axis] = o
        out.append((c, half))
    return [S.RoundBox(c_, h_, round_=min(half_w, depth) * 0.6, k=k, op='sub') for c_, h_ in out]


def fist_prims_local():
    """Stone fist in the canonical local frame (x=u knuckle row, y=v down the
    hand from the wrist, z=w back of hand). The cuff sits on the wrist and
    below it, so forearms can cross above it in the coffin pose."""
    RB, E = S.RoundBox, S.Ellipsoid
    I = np.eye(3)
    # the wrapped forearm runs straight into the blocky back of the hand (no wrist rim)
    P = [RB((0, 0.62, 0.12), (0.78, 0.58, 0.46), round_=0.09, k=0.04, bone='Hand', tag='hand'),
         RB((0, 0.62, -0.40), (0.70, 0.40, 0.22), round_=0.09, k=0.05, bone='Hand', tag='hand')]
    # four separate blocky curled fingers: proximal block down to the knuckle row (the slam face), middle
    # block curling back up the palm side; clear gaps between fingers and a knuckle ridge on top of each
    lens = (0.24, 0.28, 0.26, 0.20)
    for i, u in enumerate((-0.585, -0.195, 0.195, 0.575)):
        L = lens[i]
        P.append(RB((u, 1.30 + (L - 0.25) * 0.5, -0.02), (0.165, L, 0.50), round_=0.07, k=0.0,
                    bone='Hand', tag='finger'))
        P.append(RB((u, 1.08 + (L - 0.25) * 0.4, -0.58), (0.160, 0.34, 0.18), round_=0.07, k=0.0,
                    bone='Hand', tag='finger'))
        P.append(E((u, 1.16, 0.50), (0.19, 0.17, 0.15), k=0.03, bone='Hand', tag='knuckle'))
    # thumb: a heavy block along the index side, its tip pressed over the curled index and middle fingers
    th = S.axis_angle((0, 0, 1), -20)
    P.append(RB((-0.80, 0.86, -0.30), (0.20, 0.42, 0.25), R=th, round_=0.08, k=0.03, bone='Hand', tag='thumb'))
    P.append(RB((-0.42, 1.20, -0.74), (0.30, 0.16, 0.15), R=S.axis_angle((0, 1, 0), 12), round_=0.07, k=0.03,
                bone='Hand', tag='thumb'))
    # Greek-key square spiral carved on the back of the hand (z = 0.58 face)
    spiral = [(-0.50, 0.30), (-0.50, 1.02), (0.50, 1.02), (0.50, 0.32), (-0.26, 0.32), (-0.26, 0.80),
              (0.26, 0.80), (0.26, 0.54), (0.00, 0.54), (0.00, 0.66)]
    P += _groove_path(spiral, I, 0.58, 2, (0, 1), 0.06, 0.09)
    # weathered: chipped corners and edges on the stone
    for c, h, ang, ax in (((0.78, 0.24, 0.56), (0.16, 0.10, 0.12), 30, (0, 0, 1)), ((-0.76, 0.40, 0.56), (0.12, 0.14, 0.10), -25, (0, 1, 0)),
                          ((0.72, 0.62, -0.55), (0.10, 0.16, 0.12), 20, (1, 0, 0)), ((0.74, 1.50, 0.40), (0.10, 0.10, 0.12), 25, (0, 0, 1)),
                          ((0.0, 0.22, 0.58), (0.18, 0.08, 0.06), 10, (0, 0, 1)), ((-0.20, 1.62, 0.30), (0.10, 0.08, 0.12), -30, (0, 1, 0)),
                          ((0.40, 1.58, -0.30), (0.12, 0.08, 0.10), 20, (1, 0, 0))):
        P.append(RB(c, h, R=S.axis_angle(ax, ang), round_=0.03, k=0.02, bone='Hand', tag='chip', op='sub'))
    return P


FIST_SCALE = np.array([1.17, 1.12, 1.02])


def fist_to_world(side, V_local):
    R, o = fist_frame(side)
    V = V_local * FIST_SCALE
    if side == 'Left':
        V = V * np.array([-1.0, 1.0, 1.0])        # left fist is the mirror image (thumb stays forward)
    return V @ R.T + o


# ------------------------------------------------------------------- mask
MASK_EYES = [np.array([0.30, -1.17, 7.86]), np.array([-0.30, -1.17, 7.86])]
# the upper corner on his left is broken away (his left eye glows in the dark gap); x, z polygon
MASK_BREAK = [(1.30, 7.42), (0.88, 7.50), (0.70, 7.64), (0.46, 7.58), (0.22, 7.68), (0.10, 7.86), (0.02, 8.02),
              (0.14, 8.20), (0.04, 8.40), (0.12, 8.56), (0.02, 8.80), (1.30, 8.80)]


def mask_prims():
    RB = S.RoundBox
    P = [RB((0, -1.20, 7.76), (0.92, 0.21, 0.84), round_=0.12, k=0.0, bone='Head', tag='plate'),
         RB((0.92, -0.86, 7.74), (0.14, 0.36, 0.76), R=S.axis_angle((0, 0, 1), -30), round_=0.08, k=0.06,
            bone='Head', tag='wing'),
         RB((-0.92, -0.86, 7.74), (0.14, 0.36, 0.76), R=S.axis_angle((0, 0, 1), 30), round_=0.08, k=0.06,
            bone='Head', tag='wing'),
         RB((0, -0.72, 8.52), (0.86, 0.48, 0.12), round_=0.08, k=0.06, bone='Head', tag='crown'),
         RB((0, -1.42, 8.26), (0.92, 0.09, 0.13), round_=0.06, k=0.04, bone='Head', tag='brow'),
         RB((0.22, -1.38, 7.00), (0.70, 0.08, 0.09), round_=0.05, k=0.04, bone='Head', tag='chin')]
    I = np.eye(3)
    zf = -1.41
    # solid carved block over the whole face: bold glyph relief (key / R shapes) on the intact stone
    glyph_r = [(-0.74, 7.04), (-0.74, 7.66), (-0.16, 7.66), (-0.16, 7.36), (-0.50, 7.36), (-0.50, 7.04)]
    P += _groove_path(glyph_r, I, zf, 1, (0, 2), 0.06, 0.10)
    glyph_k = [(0.04, 7.04), (0.04, 7.44), (0.42, 7.44), (0.42, 7.20), (0.22, 7.20)]
    P += _groove_path(glyph_k, I, zf, 1, (0, 2), 0.055, 0.10)
    key = [(0.60, 7.04), (0.80, 7.04), (0.80, 7.34)]
    P += _groove_path(key, I, zf, 1, (0, 2), 0.05, 0.09)
    top = [(-0.80, 8.08), (-0.80, 8.44), (-0.30, 8.44), (-0.30, 8.20)]
    P += _groove_path(top, I, zf, 1, (0, 2), 0.055, 0.10)
    brow = [(-0.86, 8.00), (0.04, 8.00)]
    P += _groove_path(brow, I, -1.51, 1, (0, 2), 0.035, 0.06)
    # his right eye: a narrow carved slit through the stone (the glow shows as a thin line)
    P.append(RB((-0.30, -1.22, 7.86), (0.17, 0.24, 0.05), round_=0.03, k=0.01, bone='Head', tag='slit', op='sub'))
    # the broken-off upper corner on his left (through the plate, the left wing and the crown edge)
    P.append(S.PolyPrism((0, -1.0, 0), MASK_BREAK, 0.8, round_=0.02, k=0.03, bone='Head', tag='break', op='sub'))
    # chips: along the fracture and on the outer edges so the stone reads weathered
    for c, h, ang in (((0.50, -1.36, 7.56), (0.11, 0.08, 0.10), 25), ((0.10, -1.36, 8.30), (0.10, 0.08, 0.12), -15),
                      ((-0.66, -1.34, 7.86), (0.10, 0.09, 0.09), 35), ((-0.90, -1.30, 8.52), (0.14, 0.10, 0.12), 20),
                      ((0.88, -1.32, 6.96), (0.12, 0.10, 0.10), -20), ((-0.60, -1.30, 6.94), (0.12, 0.10, 0.08), 15),
                      ((-0.92, -1.30, 7.30), (0.10, 0.10, 0.14), 10)):
        P.append(RB(c, h, R=S.axis_angle((0, 1, 0), ang), round_=0.03, k=0.02, bone='Head', tag='chip', op='sub'))
    return P


# --------------------------------------------------------- loincloth flaps
def flap_surface(front, nx=13, nz=10):
    """(V, F) of a thick torn cloth flap hanging from the waist band."""
    if front:
        half_w, z0, z1 = 0.70, 3.96, 1.55
        notches = [(-0.32, 0.26), (0.30, 0.20), (0.75, 0.12)]
    else:
        half_w, z0, z1 = 0.76, 3.96, 1.95
        notches = [(-0.24, 0.18), (0.38, 0.22)]
    xs = np.linspace(-1, 1, nx)

    def hem(xn):
        z = z1 - 0.06 * xn ** 2
        for c, dpt in notches:
            z += dpt * np.clip(1 - np.abs(xn - c) / 0.16, 0, 1)
        return z + 0.04 * np.where(xn < -0.9, 1, 0)

    def pos(xn, t):
        z = z0 + (hem(xn) - z0) * t
        x = xn * half_w * (1.0 + 0.12 * t)
        drop = z0 - z
        if front:
            # long torn front flap: soft vertical folds that deepen toward the hem
            y = -1.18 - 0.09 * drop - 0.07 * (1 - xn ** 2) - 0.055 * t * math.sin(2.6 * math.pi * xn + 0.5)
        else:
            y = 1.12 + 0.12 * drop + 0.06 * (1 - xn ** 2)
        return np.array([x, y, z])

    out_dir = -1.0 if front else 1.0
    thick = 0.085
    V = []
    for layer in (0, 1):
        for j in range(nz):
            t = j / (nz - 1)
            for i, xn in enumerate(xs):
                p = pos(xn, t)
                V.append(p + np.array([0, -out_dir * thick * layer, 0]))
    V = np.array(V)
    idx = lambda layer, j, i: layer * nx * nz + j * nx + i
    F = []
    for j in range(nz - 1):
        for i in range(nx - 1):
            a, b, c, d = idx(0, j, i), idx(0, j, i + 1), idx(0, j + 1, i + 1), idx(0, j + 1, i)
            F.append((a, d, c, b) if front else (a, b, c, d))
            a, b, c, d = idx(1, j, i), idx(1, j, i + 1), idx(1, j + 1, i + 1), idx(1, j + 1, i)
            F.append((a, b, c, d) if front else (a, d, c, b))
    # rim
    ring = [(0, i) for i in range(nx)] + [(j, nx - 1) for j in range(1, nz)] + \
           [(nz - 1, i) for i in range(nx - 2, -1, -1)] + [(j, 0) for j in range(nz - 2, 0, -1)]
    for k in range(len(ring)):
        (j0, i0), (j1, i1) = ring[k], ring[(k + 1) % len(ring)]
        a, b, c, d = idx(0, j0, i0), idx(0, j1, i1), idx(1, j1, i1), idx(1, j0, i0)
        F.append((a, b, c, d) if front else (a, d, c, b))
    return V, F


# ---------------------------------------------------------- coffin cavity
# round10-props Sarcophagus, fourth pass 2026-10-10 (built around requiredCavity; exports/Sarcophagus.fbx,
# props-manifest.json), REAL studs: origin = cavity floor centre at ground level, open face -Y; cavity floor z 0.8,
# ceiling 12.7, front rim plane y -2.90, back inner wall +2.90, up to 7.0 wide. The game reads emergeOut = 4.9: the
# Emerge root travels from the cavity centre to 4.9 in front of it. The real meshes (body + the open lid) are the
# authoritative clearance check; the box profile below (max width only) is a coarse stand-in for the numpy side.
EMERGE_OUT = 4.9
COFFIN_START_REAL = np.array([0.0, EMERGE_OUT, 0.0])   # coffin origin in the boss's final-spot space
ROOT_START_REAL = np.array([0.0, EMERGE_OUT, 0.8])     # Emerge root start: standing on the cavity floor centre
CAVITY_REAL = {'floor': 0.8, 'ceiling': 12.7, 'front': -2.90, 'back': 2.90, 'w0': 3.50, 'z0': 0.8, 'slope': 0.0,
               'wall': 0.65, 'height': 11.9, 'depth': 5.8, 'width_at_shoulder': 7.0}
LID_HINGE_Y = -4.15729                                  # open lid: hinge on the ground at this coffin-space y
LID_TOP_Z = 1.257                                       # lies flat in front, top 1.257 above the ground
# the same in design units (everything numpy-side works in design units)
COFFIN_START = COFFIN_START_REAL / SC
ROOT_START = ROOT_START_REAL / SC
CAVITY = {k: (v / SC if isinstance(v, float) and k != 'slope' else v) for k, v in CAVITY_REAL.items()}
FEET_IN = 0.40                                  # each foot starts this much nearer the centre line (design units)


def cavity_halfwidth_real(z):
    c = CAVITY_REAL
    return c['w0'] + c['slope'] * (np.asarray(z) - c['z0'])


def cavity_clearance_real(P, inside_only=False):
    """Signed clearance (real studs) of final-space REAL points from the coffin walls/floor/back."""
    c = CAVITY_REAL
    x, y, z = P[:, 0] - COFFIN_START_REAL[0], P[:, 1] - COFFIN_START_REAL[1], P[:, 2]
    w = cavity_halfwidth_real(z)
    side = w - np.abs(x)
    beyond = np.abs(x) > w + c['wall'] + 0.05
    cl = np.minimum.reduce([side, z - c['floor'], c['back'] - y, c['ceiling'] - z])
    cl = np.where(beyond & (side < 0), 9.0, cl)
    front = y - c['front']
    if inside_only:
        return np.minimum(cl, front)
    return np.where(front < 0, 9.0, cl)


def cavity_halfwidth(z):
    """Design units."""
    return cavity_halfwidth_real(np.asarray(z) * SC) / SC


def cavity_clearance(P, inside_only=False):
    """Design-unit points in, design-unit clearance out."""
    return cavity_clearance_real(np.asarray(P) * SC, inside_only) / SC


def cavity_box():
    """Bounding extents of the cavity (real studs, for the record)."""
    c = CAVITY_REAL
    lo = COFFIN_START_REAL + np.array([-c['width_at_shoulder'] / 2, c['front'], c['floor']])
    hi = COFFIN_START_REAL + np.array([c['width_at_shoulder'] / 2, c['back'], c['ceiling']])
    return lo, hi
