"""Canonical right-hand grip on the club, designed in (scaled) hand-local space.

Hand-local (right hand): +Y from the wrist toward the knuckles, +Z = back of
the hand, the thumb on -X; units are studs (the hand scale HS already applied).
The palm's front surface is z = PALM_FRONT * HS.

A proper hammer grip:
- the haft (radius r) lies across the palm on a shallow diagonal (index
  knuckle -> heel of the hand) and passes all the way through the fist: toward
  the stone on the thumb side, and out the pinky side as a short butt;
- the palm sits behind the handle (the handle presses PALM_SINK into it);
- the four fingers curl round its front with every segment at contact distance
  (haft radius + finger radius + CONTACT), knuckles staggered by their lengths;
- the thumb wraps round the other side and ends over the index finger's middle
  segment.

`solve()` searches the haft's position on the palm together with each finger's
three hinge curls, and the thumb's three segment directions (bone lengths are
fixed, so the REST and REFERENCE skeletons agree). Pure numpy.
"""
import functools
import math

import numpy as np

PALM_FRONT = -0.40
FINGER_BASE = (1.10, -0.20)       # (y, z) of the finger roots, pre-scale
GRIP_PHI = 28.0                   # diagonal across the palm (deg): index knuckle -> heel of the hand
CONTACT = 0.015                   # target gap between skin and wood (studs)
PALM_SINK = 0.10                  # how far the handle presses into the palm (studs)


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def rot(axis, deg):
    a = unit(axis)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def haft_dir():
    p = math.radians(GRIP_PHI)
    return unit([-math.cos(p), math.sin(p), 0.0])


def dist_to_line(P, o, d):
    v = np.atleast_2d(P) - o
    return np.linalg.norm(v - np.outer(v @ d, d), axis=1)


CURL_LEAN = 0.45                  # how far each finger's curl axis leans toward the haft direction


def curl_axis():
    h = haft_dir()
    a = unit((1 - CURL_LEAN) * np.array([1.0, 0, 0]) + CURL_LEAN * np.array([-h[0], -h[1], 0.0]))
    return a


def finger_chain(base, curls, lens, splay, axis=None):
    axis = np.array([1.0, 0, 0]) if axis is None else np.asarray(axis, float)
    lean = math.degrees(math.atan2(axis[1], axis[0]))           # rotate the finger with its axis
    d0 = rot((0, 0, 1), splay + lean) @ np.array([0, 1.0, 0])
    pts = [np.asarray(base, float)]
    tot = 0.0
    for k in range(3):
        tot += curls[k]
        pts.append(pts[-1] + (rot(axis, -tot) @ d0) * lens[k])
    return pts


def _samples(pts, ts=(0.3, 0.65, 1.0)):
    return np.array([pts[k] + (pts[k + 1] - pts[k]) * t for k in range(3) for t in ts])


def _solve_finger(base, lens, splay, rad, c, d, r):
    best = None
    for m in range(0, 111, 3):
        for pp in range(20, 131, 4):
            for dd in range(0, 111, 6):
                pts = finger_chain(base, (m, pp, dd), lens, splay, curl_axis())
                gap = dist_to_line(_samples(pts), c, d) - (r + rad + CONTACT)
                cost = 200 * np.sum(np.minimum(gap, 0) ** 2) + 3.0 * np.sum(gap[1:] ** 2) \
                    + 0.0001 * ((pp - 95) ** 2 + (dd - 60) ** 2)
                if best is None or cost < best[0]:
                    best = (cost, (m, pp, dd), pts, gap)
    return best


def _sph(theta, phi):
    return np.array([math.cos(phi) * math.cos(theta), math.cos(phi) * math.sin(theta), math.sin(phi)])


def _solve_thumb(base, lens, rad, c, d, r, target, avoid):
    """Three fixed-length segments from `base` ending near `target`, outside the
    haft and outside the finger capsules in `avoid`, bending smoothly."""
    rng = np.random.default_rng(3)

    def chain(a):
        pts = [np.asarray(base, float)]
        for k in range(3):
            pts.append(pts[-1] + _sph(a[2 * k], a[2 * k + 1]) * lens[k])
        return pts

    def cost(a):
        pts = chain(a)
        S = _samples(pts)
        gap = dist_to_line(S, c, d) - (r + rad + CONTACT)
        cst = 200 * np.sum(np.minimum(gap, 0) ** 2) + 4.0 * np.sum((pts[3] - target) ** 2)
        for (p0, p1, fr) in avoid:
            ab = p1 - p0
            t = np.clip(((S - p0) @ ab) / (ab @ ab), 0, 1)
            dd = np.linalg.norm(S - (p0 + t[:, None] * ab), axis=1) - (fr + rad)
            cst += 60 * np.sum(np.minimum(dd, 0) ** 2)
        segs = [unit(pts[k + 1] - pts[k]) for k in range(3)]
        for k in range(2):
            ang = math.degrees(math.acos(np.clip(segs[k] @ segs[k + 1], -1, 1)))
            cst += 0.002 * max(0.0, ang - 55) ** 2
        return cst
    best_a, best_c = None, None
    for trial in range(60):
        a = rng.uniform([-math.pi, -1.4] * 3, [math.pi, 1.4] * 3)
        c_ = cost(a)
        step = 0.5
        while step > 0.004:
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
    gap = dist_to_line(_samples(pts), c, d) - (r + rad + CONTACT)
    return pts, gap, best_c


def solve(*args):
    """Cached on disk (source/grip_solution.json) because the search takes ~2 min."""
    import hashlib
    import json
    from pathlib import Path
    key = hashlib.sha1(repr((args, PALM_FRONT, FINGER_BASE, GRIP_PHI, CONTACT, PALM_SINK, 'v4', CURL_LEAN)).encode()).hexdigest()
    path = Path(__file__).resolve().parent / 'source' / 'grip_solution.json'
    if path.exists():
        data = json.loads(path.read_text())
        if data.get('key') == key:
            J = {k: [np.array(p) for p in v] for k, v in data['joints_local'].items()}
            return np.array(data['centre_local']), np.array(data['direction_local']), J, data['report']
    c, d, J, rep = _solve(*args)
    path.write_text(json.dumps({'key': key, 'note': 'Right-hand club grip, scaled hand-local coordinates '
                                '(+Y wrist->knuckles, +Z back of hand, thumb on -X). See fc_grip.py.',
                                'centre_local': c.tolist(), 'direction_local': d.tolist(),
                                'joints_local': {k: [p.tolist() for p in v] for k, v in J.items()},
                                'report': rep}, indent=1))
    return c, d, J, rep


@functools.lru_cache(maxsize=None)
def _solve(HS, r, finger_x, finger_splay, finger_scale, seg_len, seg_rad, thumb_base, thumb_len, thumb_rad):
    """Returns (centre, direction, joints{name: [p0..p3]}, report) in scaled hand-local coords."""
    d = haft_dir()
    fb_y, fb_z = FINGER_BASE
    best = None
    for y0 in np.arange(0.35, 0.86, 0.05):
        z0 = PALM_FRONT * HS - r + PALM_SINK
        c = np.array([0.0, y0 * HS, z0])
        tot = 0.0
        sol = {}
        for i in range(4):
            rad = seg_rad[0] * HS * (0.9 if i == 3 else 1.0)
            lens = [l * finger_scale[i] * HS for l in seg_len]
            base = np.array([finger_x[i], fb_y, fb_z]) * HS
            b = _solve_finger(base, lens, finger_splay[i], rad, c, d, r)
            tot += b[0]
            sol[i] = b
        if best is None or tot < best[0]:
            best = (tot, c, sol)
    _, c, sol = best
    names = ['Index', 'Middle', 'Ring', 'Pinky']
    joints = {}
    rep = {'haft_radius': r, 'centre_local': [round(float(v), 3) for v in c],
           'direction_local': [round(float(v), 3) for v in d], 'contact_target': CONTACT}
    avoid = []
    for i, nm in enumerate(names):
        cost, curls, pts, gap = sol[i]
        joints[nm] = pts
        rep[nm] = {'curls_deg': list(curls), 'clearance_min': round(float(gap.min()), 3),
                   'clearance_max': round(float(gap.max()), 3)}
        rad = seg_rad[0] * HS * (0.9 if i == 3 else 1.0)
        avoid += [(pts[k], pts[k + 1], rad) for k in range(3)]
    # The thumb comes from the thenar (heel side of the palm), wraps down the
    # handle's heel side and lies against the thumb-side face of the index
    # finger's middle segment, pressing the curled fingers closed.
    ip = joints['Index']
    trad = thumb_rad * HS
    target = ip[2] + d * (seg_rad[1] * HS + trad * 0.85)
    tb = np.asarray(thumb_base, float) * HS
    tpts, tgap, tcost = _solve_thumb(tb, [l * HS for l in thumb_len], trad, c, d, r, target, avoid)
    joints['Thumb'] = tpts
    rep['Thumb'] = {'clearance_min': round(float(tgap.min()), 3), 'clearance_max': round(float(tgap.max()), 3),
                    'tip_to_target': round(float(np.linalg.norm(tpts[3] - target)), 3)}
    return c, d, joints, rep
