"""The Hammer Brute's two-handed grip (pure numpy).

1. `solve_hand()`: the canonical closed grip in RIGHT-hand-local space
   (+Y wrist -> knuckles, +Z back of the hand, thumb on -X; origin = wrist).
   A power grip on a thick haft: the haft (radius HAFT_R) lies across the palm
   on a shallow GRIP_PHI diagonal and passes right through the fist; the palm
   sits behind it; each finger's three hinges are searched so EVERY phalanx
   touches the wood (closest approach within CONTACT_WINDOW); the thumb wraps
   the opposite side and ends over the index finger's middle segment. The left
   hand is the mirror image (x -> -x), so both thumbs point at the hammer head.

2. `solve_reference()`: places the hammer and both hands for the reference
   stance (idle frame 0). Unknowns: the haft's depth, yaw and tilt, the left
   grip position along the haft, each hand's roll about the haft and each
   elbow's swivel. Cost: the haft, fists, butt and head land on their reference
   pixels; arm lengths are fixed; wrist flexion and deviation stay small; the
   elbows land near their reference pixels and stay out of the body.

Both results are cached in source/grip_solution.json (keyed by the inputs).
"""
import functools
import hashlib
import json
import math
from pathlib import Path

import numpy as np

import hb_design as D

HERE = Path(__file__).resolve().parent
SOLUTION = HERE / 'source' / 'grip_solution.json'

GRIP_PHI = 12.0             # haft diagonal across the palm (deg); head on the thumb side
PALM_SINK = 0.08            # the haft presses this far into the palm surface
CONTACT_TARGET = -0.005     # target skin-to-wood gap for every phalanx
CONTACT_WINDOW = (-0.03, 0.02)
VERSION = 'hb-grip-v6'


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def rot(axis, deg):
    a = unit(axis)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def rot_batch(axis, deg):
    """(n,3,3) rotations about one axis by n angles (deg)."""
    a = unit(axis)
    t = np.radians(np.asarray(deg, float))
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3)[None] + np.sin(t)[:, None, None] * K[None] + (1 - np.cos(t))[:, None, None] * (K @ K)[None]


def haft_dir_local():
    p = math.radians(GRIP_PHI)
    return unit([-math.cos(p), math.sin(p), 0.0])


def dist_to_line(P, o, d):
    v = P - o
    return np.linalg.norm(v - (v @ d)[..., None] * d, axis=-1)


TS = (0.25, 0.5, 0.75, 1.0)


def _finger_search(base, lens, splay, rads, c, d, r):
    """Vectorised search of (MCP, PIP, DIP) curls about the haft axis."""
    d0 = rot((0, 0, 1), splay) @ np.array([0, 1.0, 0])
    d0 = unit(d0 - d * (d0 @ d))                   # wrap in the plane square to the haft
    m = np.arange(0, 105.1, 2.5)
    p = np.arange(15, 125.1, 2.5)
    q = np.arange(0, 100.1, 4.0)
    M, Pp, Q = np.meshgrid(m, p, q, indexing='ij')
    M, Pp, Q = M.ravel(), Pp.ravel(), Q.ravel()
    cum = [M, M + Pp, M + Pp + Q]
    pts = [np.broadcast_to(base, (len(M), 3))]
    for k in range(3):
        R = rot_batch(d, cum[k])
        pts.append(pts[-1] + (R @ d0) * lens[k])
    gaps = []
    for k in range(3):
        for t in TS:
            s = pts[k] + (pts[k + 1] - pts[k]) * t
            rr = rads[k] + (rads[min(k + 1, 2)] - rads[k]) * t
            gaps.append(dist_to_line(s, c, d) - (r + rr) - CONTACT_TARGET)
    G = np.stack(gaps, 1)                          # (n, 12)
    cost = 400 * np.sum(np.minimum(G, 0) ** 2, 1)
    # every segment must actually touch: penalise each segment's closest approach
    segmin = np.stack([G[:, 4 * k:4 * k + 4].min(1) for k in range(3)], 1)
    cost += 120 * np.sum(segmin ** 2, 1)
    cost += 2.0 * np.sum(G[:, 2:] ** 2, 1) / 10
    cost += 3e-5 * ((M - 50) ** 2 + (Pp - 80) ** 2 + (Q - 42) ** 2) + 4e-5 * (Q - 0.62 * Pp) ** 2
    i = int(np.argmin(cost))
    chain = [np.asarray(x[i] if x.ndim == 2 else x, float).copy() for x in pts]
    return float(cost[i]), (float(M[i]), float(Pp[i]), float(Q[i])), chain


def _sph(theta, phi):
    return np.array([math.cos(phi) * math.cos(theta), math.cos(phi) * math.sin(theta), math.sin(phi)])


def _solve_thumb(base, lens, rads, c, d, r, target, avoid):
    rng = np.random.default_rng(3)

    def chain(a):
        pts = [np.asarray(base, float)]
        for k in range(3):
            pts.append(pts[-1] + _sph(a[2 * k], a[2 * k + 1]) * lens[k])
        return pts

    def samples(pts):
        return np.array([pts[k] + (pts[k + 1] - pts[k]) * t for k in range(3) for t in TS])

    def cost(a):
        pts = chain(a)
        S = samples(pts)
        rr = np.repeat([rads[0], rads[1], rads[2]], len(TS))
        gap = dist_to_line(S, c, d) - (r + rr) - CONTACT_TARGET
        cst = 300 * np.sum(np.minimum(gap, 0) ** 2) + 5.0 * np.sum((pts[3] - target) ** 2)
        cst += 4.0 * gap[4:].min() ** 2                    # the thumb lies on the wood
        for (p0, p1, fr) in avoid:
            ab = p1 - p0
            t = np.clip(((S - p0) @ ab) / (ab @ ab), 0, 1)
            dd = np.linalg.norm(S - (p0 + t[:, None] * ab), axis=1) - (fr + rr) + 0.01
            cst += 80 * np.sum(np.minimum(dd, 0) ** 2)
        segs = [unit(pts[k + 1] - pts[k]) for k in range(3)]
        for k in range(2):
            ang = math.degrees(math.acos(np.clip(segs[k] @ segs[k + 1], -1, 1)))
            cst += 0.002 * max(0.0, ang - 50) ** 2
        return cst
    best_a, best_c = None, None
    for trial in range(48):
        a = rng.uniform([-math.pi, -1.4] * 3, [math.pi, 1.4] * 3)
        c_ = cost(a)
        step = 0.5
        while step > 0.003:
            improved = False
            for i in range(6):
                for sgn in (1, -1):
                    b = a.copy()
                    b[i] += sgn * step
                    cb = cost(b)
                    if cb < c_:
                        a, c_, improved = b, cb, True
            if not improved:
                step *= 0.5
        if best_c is None or c_ < best_c:
            best_a, best_c = a, c_
    pts = chain(best_a)
    S = samples(pts)
    rr = np.repeat([rads[0], rads[1], rads[2]], len(TS))
    gap = dist_to_line(S, c, d) - (r + rr)
    return pts, gap, best_c


def _hand_inputs():
    return (D.HAFT_R, D.FINGER_X, D.FINGER_BASE, D.FINGER_BASE_OFF, D.FINGER_SPLAY, D.FINGER_SCALE, D.SEG_LEN, D.SEG_RAD,
            D.FINGER_RAD_SCALE, D.THUMB_BASE, D.THUMB_LEN, D.THUMB_RAD, D.PALM_C, D.PALM_HALF,
            GRIP_PHI, PALM_SINK, CONTACT_TARGET, VERSION)


def _solve_hand():
    r = D.HAFT_R
    d = haft_dir_local()
    palm_front = D.PALM_C[2] - D.PALM_HALF[2]
    z0 = palm_front - r + PALM_SINK
    best = None
    for y0 in np.arange(0.50, 1.06, 0.05):
        c = np.array([0.0, y0, z0])
        tot = 0.0
        sol = {}
        for i, nm in enumerate(D.FINGER_NAMES):
            rads = [D.SEG_RAD[k] * D.FINGER_RAD_SCALE[i] for k in range(3)]
            lens = [l * D.FINGER_SCALE[i] for l in D.SEG_LEN]
            base = D.finger_root(i)
            sol[nm] = _finger_search(base, lens, D.FINGER_SPLAY[i], rads, c, d, r)
            tot += sol[nm][0]
        if best is None or tot < best[0]:
            best = (tot, c, sol)
    _, c, sol = best
    joints, rep, avoid = {}, {}, []
    for i, nm in enumerate(D.FINGER_NAMES):
        cost, curls, pts = sol[nm]
        joints[nm] = pts
        rads = [D.SEG_RAD[k] * D.FINGER_RAD_SCALE[i] for k in range(3)]
        segs = []
        for k in range(3):
            g = [dist_to_line(pts[k] + (pts[k + 1] - pts[k]) * t, c, d)
                 - (r + rads[k] + (rads[min(k + 1, 2)] - rads[k]) * t) for t in np.linspace(0.15, 1.0, 18)]
            segs.append(round(float(min(g)), 4))
        rep[nm] = {'curls_deg': list(curls), 'segment_closest_gap': segs}
        avoid += [(pts[k], pts[k + 1], rads[k]) for k in range(3)]
    ip = joints['Index']
    tr = D.THUMB_RAD
    # the thumb tip rests on the outside of the index finger's last two segments,
    # wrapping the haft from the other side
    tipzone = ip[2] * 0.5 + ip[3] * 0.5
    v = tipzone - c
    out_n = unit(v - d * (v @ d))
    target = tipzone + out_n * (D.SEG_RAD[2] + tr[2][1] - 0.04) + d * 0.18
    tpts, tgap, tcost = _solve_thumb(np.array(D.THUMB_BASE), list(D.THUMB_LEN), [t[0] for t in tr], c, d, r,
                                     target, avoid)
    joints['Thumb'] = tpts
    rep['Thumb'] = {'closest_gap': round(float(tgap.min()), 4), 'tip_to_target': round(float(np.linalg.norm(tpts[3] - target)), 3)}
    rep['haft_radius'] = r
    rep['centre_local'] = [round(float(v), 4) for v in c]
    rep['direction_local'] = [round(float(v), 4) for v in d]
    rep['contact_window'] = list(CONTACT_WINDOW)
    rep['all_phalanges_in_window'] = all(CONTACT_WINDOW[0] <= g <= CONTACT_WINDOW[1]
                                         for nm in D.FINGER_NAMES for g in rep[nm]['segment_closest_gap'])
    return c, d, joints, rep


def _key(obj):
    return hashlib.sha1(repr(obj).encode()).hexdigest()


def _load():
    if SOLUTION.exists():
        return json.loads(SOLUTION.read_text())
    return {}


def _save(data):
    SOLUTION.write_text(json.dumps(data, indent=1))


@functools.lru_cache(maxsize=None)
def solve_hand():
    """(centre, direction, joints{name: [p0..p3]}, report) in right-hand-local coords."""
    key = _key(_hand_inputs())
    data = _load()
    h = data.get('hand_local')
    if h and h.get('key') == key:
        J = {k: [np.array(p) for p in v] for k, v in h['joints'].items()}
        return np.array(h['centre']), np.array(h['direction']), J, h['report']
    c, d, J, rep = _solve_hand()
    data['hand_local'] = {'key': key,
                          'note': 'Right-hand-local grip (+Y wrist->knuckles, +Z back of hand, thumb on -X, origin '
                                  'at the wrist). The left hand mirrors x. See hb_grip.py.',
                          'centre': c.tolist(), 'direction': d.tolist(),
                          'joints': {k: [p.tolist() for p in v] for k, v in J.items()}, 'report': rep}
    data.pop('reference', None)
    _save(data)
    return c, d, J, rep


GRIP_STYLE = 'barbell'


def grip_local(side):
    """(haft centre, haft direction toward the HEAD) in this hand's local coords.

    Barbell carry (the reference): both hands overhand, thumbs toward each other.
    The left hand (at the butt) has the head on its thumb side; the right hand
    (near the head) has the head on its little-finger side."""
    c, d, J, rep = solve_hand()
    d = unit(D.mirror_local(side, d))
    if side == 'Right' and GRIP_STYLE == 'barbell':
        d = -d
    return D.mirror_local(side, c), d


def grip_joints_local(side):
    c, d, J, rep = solve_hand()
    return {k: [D.mirror_local(side, p) for p in v] for k, v in J.items()}


# ==================================================================== placing
def hand_on_haft(side, G, h, alpha):
    """Hand frame R and wrist W that put this hand's grip on the haft line through
    G with direction h (toward the head), rolled by alpha (deg) about the haft."""
    c, dl = grip_local(side)
    R0 = _min_rot(dl, h)
    R = rot(h, alpha) @ R0
    return R, G - R @ c


def _min_rot(a, b):
    a = unit(a)
    b = unit(b)
    v = np.cross(a, b)
    cc = float(a @ b)
    if np.linalg.norm(v) < 1e-9:
        if cc > 0:
            return np.eye(3)
        p = np.cross(a, [1, 0, 0]) if abs(a[0]) < 0.9 else np.cross(a, [0, 1, 0])
        return rot(p, 180)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * (1 / (1 + cc))


def two_bone(S, W, l1, l2, pole):
    """Elbow position for shoulder S, wrist W and a pole direction."""
    v = W - S
    dd = min(np.linalg.norm(v), l1 + l2 - 1e-4)
    u = unit(v)
    p = pole - u * (pole @ u)
    p = unit(p) if np.linalg.norm(p) > 1e-9 else unit(np.cross(u, [0, 0, 1.0]))
    a = (l1 * l1 - l2 * l2 + dd * dd) / (2 * dd)
    hh = math.sqrt(max(0.0, l1 * l1 - a * a))
    return S + u * a + p * hh, np.linalg.norm(v) <= l1 + l2 - 1e-4


def wrist_angles(F, R):
    """(flexion/extension, deviation) of the hand frame R relative to the forearm
    direction F, in degrees (signed: +flex toward the palm, +dev toward the thumb)."""
    fl = math.degrees(math.atan2(F @ R[:, 2], F @ R[:, 1]))     # + = palmar flexion
    dv = math.degrees(math.atan2(F @ R[:, 0], F @ R[:, 1]))
    return fl, dv


# reference pixels (measure_reference.LANDMARKS)
HAFT_PX = ((478.0, 980.0), (840.0, 894.0))
GRIP_R_PX_X = 405.0
GRIP_L_PX_X = 928.0
BUTT_PX = (1041.0, 869.0)
HEAD_PX = (212.0, 1052.0)
ELBOW_PX = {'Right': (262.0, 668.0), 'Left': (940.0, 690.0)}
FIST_PX = {'Right': (398.0, 940.0), 'Left': (928.0, 880.0)}


def _haft_px_at(x):
    (x0, y0), (x1, y1) = HAFT_PX
    return np.array([x, y0 + (x - x0) * (y1 - y0) / (x1 - x0)])


def _ref_inputs():
    return (_hand_inputs(), D.SHOULDER.tolist(), D.REF_HUNCH, D.REF_ROLL, D.REF_ROLL_PIVOT_Z, D.L_UPPER, D.L_FORE, D.HEAD_HALF.tolist(), D.EYE_OFFSET,
            D.S_RIGHT, HAFT_PX, GRIP_R_PX_X, GRIP_L_PX_X, BUTT_PX, HEAD_PX, ELBOW_PX,
            json.loads((HERE / 'source' / 'camera_solution.json').read_text())['camera_location'], 'ref-v12', GRIP_STYLE)


def _strike_axis(h, Rh_right):
    """Striking-face normal: square to the haft, halfway between straight down and
    the right hand's knuckle direction (the face a natural strike leads with)."""
    down = np.array([0, 0, -1.0])
    a = unit(down - h * (down @ h))
    y = Rh_right[:, 1]
    b = y - h * (y @ h)
    b = unit(b) if np.linalg.norm(b) > 1e-6 else a
    return unit(a + b)


def build_reference(x, cam, body_check=None):
    """x = [y_R, yaw, tilt, s_L, alpha_R, alpha_L, swivel_R, swivel_L] -> dict."""
    yR, yaw, tilt, sL, aR, aL, wR, wL = x
    gR_px = _haft_px_at(GRIP_R_PX_X)
    G_R = cam.at(gR_px[0], gR_px[1], yR)
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    ct, st = math.cos(math.radians(tilt)), math.sin(math.radians(tilt))
    h = unit([-cy * ct, -sy * ct, -st])                  # toward the head
    G_L = G_R - (sL - D.S_RIGHT) * h
    out = {'h': h, 'G_R': G_R, 'G_L': G_L, 's_L': sL}
    for side, G, a, w in (('Right', G_R, aR, wR), ('Left', G_L, aL, wL)):
        R, W = hand_on_haft(side, G, h, a)
        S = D.ref_shoulder(side)
        lat = np.array([-1.0 if side == 'Right' else 1.0, 0, 0])
        # swivel: 0 = elbow straight out to the side, + = elbow toward the back
        u = unit(W - S)
        p1 = unit(lat - u * (lat @ u))
        p2 = unit(np.cross(u, p1)) * (1 if side == 'Left' else -1)
        back = np.array([0, 1.0, 0])
        if p2 @ back < 0:
            p2 = -p2
        pole = math.cos(math.radians(w)) * p1 + math.sin(math.radians(w)) * p2
        E, ok = two_bone(S, W, D.L_UPPER, D.L_FORE, pole)
        F = unit(W - E)
        fl, dv = wrist_angles(F, R)
        out[side] = {'R': R, 'W': W, 'E': E, 'S': S, 'reach_ok': ok, 'reach': float(np.linalg.norm(W - S)),
                     'wrist_flex': fl, 'wrist_dev': dv}
    n_strike = _strike_axis(h, out['Right']['R'])
    eye = G_R + D.S_RIGHT * h
    out['head_centre'] = eye + n_strike * D.EYE_OFFSET
    out['n_strike'] = n_strike
    out['butt'] = G_R - (sL + 1.55 - D.S_RIGHT) * h
    return out


@functools.lru_cache(maxsize=None)
def _clear_prims():
    keep = ('pelvis', 'seat', 'flank', 'belly', 'belly_low', 'thigh', 'thigh_bulk', 'knee', 'shin', 'calf')
    out = [p for p in D.torso_prims() if p.tag in keep and p.op == 'union']
    for side in ('Right', 'Left'):
        out += [p for p in D.leg_prims(side) if p.tag in keep]
    return tuple(out)


def _ref_cost(x, cam, verbose=False):
    o = build_reference(x, cam)
    c = 0.0
    terms = {}

    def px(P):
        return cam.project(P)[0][0]
    gl = px(o['G_L'])
    terms['grip_L'] = float(np.sum((gl - _haft_px_at(GRIP_L_PX_X)) ** 2))
    terms['butt'] = float(np.sum((px(o['butt']) - np.array(BUTT_PX)) ** 2))
    terms['head'] = 0.4 * float(np.sum((px(o['head_centre']) - np.array(HEAD_PX)) ** 2))
    for side in ('Right', 'Left'):
        s = o[side]
        terms['elbow_' + side] = 0.15 * float(np.sum((px(s['E']) - np.array(ELBOW_PX[side])) ** 2))
        fc = s['W'] + s['R'] @ np.array([0.0, 0.70, -0.40])
        terms['fist_' + side] = 0.3 * float(np.sum((px(fc) - np.array(FIST_PX[side])) ** 2))
        terms['wrist_' + side] = 6.0 * (s['wrist_flex'] ** 2 + 1.5 * s['wrist_dev'] ** 2) / 10
        terms['wrist_lim_' + side] = 400.0 * (max(0, abs(s['wrist_flex']) - 20) ** 2 + max(0, abs(s['wrist_dev']) - 18) ** 2)
        terms['reach_' + side] = 0.0 if s['reach_ok'] else 1e4 * (s['reach'] - D.L_UPPER - D.L_FORE + 0.05) ** 2
        # the elbow must be bent a natural amount (35..80 deg)
        u = unit(s['E'] - s['S'])
        f = unit(s['W'] - s['E'])
        flex = math.degrees(math.acos(np.clip(u @ f, -1, 1)))
        s['elbow_flex'] = flex
        terms['flex_' + side] = 2.0 * (max(0, 35 - flex) ** 2 + max(0, flex - 85) ** 2)
        # elbows stay outside the trunk
        lat = abs(s['E'][0])
        terms['elbow_out_' + side] = 300.0 * max(0, 3.6 - lat) ** 2
    # the reference shows the head's outer cheek: the head end of the haft comes toward the camera
    terms['cheek'] = 800.0 * max(0.0, o['h'][1] + 0.12) ** 2
    # right hand: an underhand 'cup' grip whose fingers close over the TOP of the haft (the
    # fist sits on the haft as in the reference): forearm reaching forward, palm facing up
    # both fists hang over the haft with the backs of the hands toward the camera (reference)
    for sd in ('Right', 'Left'):
        R_ = o[sd]['R']
        terms['back_fwd_' + sd] = 400.0 * max(0.0, R_[1, 2] + 0.35) ** 2
    # the haft and hammer head stay clear of the trunk and thighs
    hs = np.array([o['G_R'] + o['h'] * t for t in np.linspace(-(o['s_L'] + 1.2 - D.S_RIGHT), D.S_RIGHT - 1.0, 14)])
    dist = np.min([p.sdf(hs) for p in _clear_prims()], axis=0)
    terms['haft_clear'] = 400.0 * float(np.sum(np.minimum(dist - D.HAFT_R - 0.12, 0) ** 2))
    # the hammer head hangs just clear of the ground (the reference shows its shadow under it)
    hx = D.HEAD_HALF
    a_ = o['h']
    s_ = o['n_strike']
    w_ = np.cross(a_, s_)
    corners = np.array([o['head_centre'] + a_ * i * hx[0] + s_ * j * hx[1] + w_ * k * hx[2]
                        for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)])
    terms['ground'] = 2000.0 * max(0.0, 0.08 - corners[:, 2].min()) ** 2
    hc = o['head_centre'][None]
    dh = np.min([p.sdf(hc) for p in _clear_prims()], axis=0)
    terms['head_clear'] = 200.0 * float(np.sum(np.minimum(dh - 2.0, 0) ** 2))
    # the fists hang clear of the belly and thighs
    for side in ('Right', 'Left'):
        fc = o[side]['W'] + o[side]['R'][:, 1] * 0.75
        bel = np.array([0.0, -1.30, 6.55])
        q = (fc - bel) / np.array([3.15 + 0.9, 2.45 + 0.9, 2.05 + 0.9])
        terms['belly_' + side] = 500.0 * max(0, 1.0 - np.linalg.norm(q)) ** 2
    c = sum(terms.values())
    if verbose:
        return c, terms, o
    return c


@functools.lru_cache(maxsize=None)
def solve_reference():
    """The reference placement (cached). Returns a dict of plain lists."""
    from hb_camera import RefCam
    key = _key(_ref_inputs())
    data = _load()
    ref = data.get('reference')
    if ref and ref.get('key') == key:
        return ref
    solve_hand()
    data = _load()
    cam = RefCam()
    rng = np.random.default_rng(11)
    lo = np.array([-3.2, -10.0, 0.0, 8.6, -360.0, -360.0, -85.0, -85.0])
    hi = np.array([-1.8, 45.0, 25.0, 10.6, 360.0, 360.0, 90.0, 90.0])
    best = None
    starts = [np.array([-2.8, 14.0, 10.0, 9.7, a, b, 30.0, 50.0]) for a in (-120, 0, 120)
              for b in (-120, 0, 120)]
    starts += [rng.uniform(lo, hi) for _ in range(3)]
    for x in starts:
        c = _ref_cost(x, cam)
        steps = np.array([0.4, 6.0, 4.0, 0.3, 30.0, 30.0, 20.0, 20.0])
        while steps.max() > 1e-3 and steps[0] > 1e-4:
            improved = False
            for i in range(len(x)):
                for sg in (1, -1):
                    y = x.copy()
                    y[i] += sg * steps[i]
                    y = np.clip(y, lo, hi)
                    cy = _ref_cost(y, cam)
                    if cy < c:
                        x, c, improved = y, cy, True
            if not improved:
                steps *= 0.5
        if best is None or c < best[0]:
            best = (c, x)
    c, x = best
    cost, terms, o = _ref_cost(x, cam, verbose=True)
    h = o['h']
    ref = {'key': key, 'x': x.tolist(), 'cost': cost, 'terms': terms,
           'haft_dir_to_head': h.tolist(), 'grip_R': o['G_R'].tolist(), 'grip_L': o['G_L'].tolist(),
           's_right': D.S_RIGHT, 's_left': float(x[3]), 's_butt': float(x[3]) + 1.55,
           'head_centre': o['head_centre'].tolist(), 'n_strike': o['n_strike'].tolist(), 'butt': o['butt'].tolist()}
    for side in ('Right', 'Left'):
        s = o[side]
        Ru = None
        ref['hand_frame_' + side] = s['R'].tolist()
        ref['wrist_' + side] = s['W'].tolist()
        ref['elbow_' + side] = s['E'].tolist()
        ref['shoulder_' + side] = s['S'].tolist()
        ref['wrist_flex_' + side] = s['wrist_flex']
        ref['wrist_dev_' + side] = s['wrist_dev']
        ref['elbow_flex_' + side] = s.get('elbow_flex')
        # forearm frame in REF: Y along the forearm, X = elbow hinge (cross(u, f))
        u = unit(s['E'] - s['S'])
        f = unit(s['W'] - s['E'])
        hinge = unit(np.cross(u, f))
        ref['forearm_frame_' + side] = np.stack([hinge, f, np.cross(hinge, f)], 1).tolist()
        ref['upperarm_frame_' + side] = np.stack([hinge, u, np.cross(hinge, u)], 1).tolist()
    data['reference'] = ref
    _save(data)
    return ref
