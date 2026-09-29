"""Solve the reference camera from landmark pixels (system python + numpy).

The reference is a single painted view, so the camera is recovered from the
crab's own bilateral symmetry: every paired landmark (eyes, rim corners, spike
apexes, eye-stalk cups) is one 3D point mirrored across the crab's midline, and
midline landmarks have x = 0. A symmetric point pair gives four image equations
for three unknowns, so each pair adds one constraint on the camera.

What the pairs cannot fix is overall scale (the ground is not a landmark), so
two anchors from the design brief close the system:
  * the tall spike pair apex sits 10 studs above the ground (unrolled body frame);
  * the ground point under the body centre projects at v ~ 790, the middle of
    the planted leg tips (835/815 near, 765/780 far).
The sea horizon (v ~ 440, measured where the water meets the far shore on the
right) pins pitch. Background cliff edges are vertical, so camera roll is 0.

The body itself is allowed to roll about its forward axis. Every right-side
landmark sits higher in the frame than its left twin by an amount proportional
to its distance from the midline (rim corners 85 px, outer spikes 57, tall
spikes 45, eyes 17), which perspective alone cannot produce at any plausible
focal length -- so the reference pose leans the body, right side up.

Focal length is profiled: the solve runs for each fixed f and the residual is
reported. It is flat (identical cost from 900 to 3600 px): symmetric pairs,
the horizon and the scale anchors trade yaw against distance without
preferring either, and the eyes' radius ratio (32.5 vs 28 px) is an artistic
asymmetry no plausible perspective reproduces. f is therefore chosen from
geometry the profile does move: at 1900 px (44.5 mm on a 36 mm sensor) the
carapace comes out 12.0 wide by ~9.5 long -- the "roughly hexagonal from
above" plan -- and the planted leg tips form a near-mirror footprint (B/E at
x -8.36 / +7.48). Shorter lenses stretch the carapace into an oval longer
than it is wide; longer ones flatten it to twice as wide as long and push the
front leg tips ahead of the face. Output: source/camera.json.

Conventions: Blender world, Z up, crab faces -Y, +X is the crab's LEFT (which
appears on the viewer's RIGHT). "R" landmarks are the crab's right = viewer left.
"""
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
W, H = 1536, 1024
CX, CY = W / 2, H / 2

# ------------------------------------------------------------------ landmarks
# (u, v) pixels measured on zoomed, gridded crops of the untouched reference.
PAIRS = {
    #               crab right (viewer left)   crab left (viewer right)
    'eye':          ((773.5, 352.5),            (933.0, 369.5)),
    'rim_corner':   ((427.0, 300.0),            (1142.0, 385.0)),
    'spike_tall':   ((637.0, 168.0),            (962.0, 213.0)),
    'spike_small':  ((536.0, 236.0),            (1050.0, 293.0)),
    'stalk_cup':    ((781.0, 428.0),            (920.0, 438.0)),
}
MIDLINE = {
    'spike_rear':   (797.0, 186.0),
    'tooth_gap_top': (850.0, 433.0),
    'belly_bottom': (800.0, 625.0),
}
EYE_RADIUS_PX = (32.5, 28.0)
HORIZON_V = 440.0
BODY_GROUND_V = 790.0
SPIKE_TALL_Z = 10.0
CHOSEN_F = 1900.0
# Planted leg tips (ground contacts) and the claw extremes, back-projected after
# the solve so the generator can place them.
GROUND_TIPS = {
    'tip_A_front_right': (665.0, 835.0),
    'tip_B_under_big_claw': (262.0, 803.0),
    'tip_C_under_belly': (864.0, 765.0),
    'tip_D_front_left': (1116.0, 815.0),
    'tip_E_rear_left': (1219.0, 780.0),
}


def cam_basis(alpha, phi):
    d = np.array([math.sin(alpha) * math.cos(phi), math.cos(alpha) * math.cos(phi), math.sin(phi)])
    r = np.array([math.cos(alpha), -math.sin(alpha), 0.0])
    u = np.cross(r, d)
    return r, u, d


def project(P, alpha, phi, f, X):
    r, u, d = cam_basis(alpha, phi)
    q = np.atleast_2d(X) - P
    xc, yc, zc = q @ r, q @ u, q @ d
    return np.stack([CX + f * xc / zc, CY - f * yc / zc], axis=1), zc


def roll_body(X, rho, pivot_z=5.0):
    X = np.atleast_2d(X).astype(float).copy()
    z = X[:, 2] - pivot_z
    x = X[:, 0]
    c, s = math.cos(rho), math.sin(rho)
    out = X.copy()
    out[:, 0] = x * c + z * s
    out[:, 2] = -x * s + z * c + pivot_z
    return out


PAIR_KEYS = list(PAIRS)
MID_KEYS = list(MIDLINE)


def unpack(p, fixed_f=None):
    i = 0
    P = p[0:3]; i = 3
    alpha, phi = p[3], p[4]; i = 5
    f = fixed_f if fixed_f is not None else math.exp(p[5])
    i = 6
    rho = p[i]; i += 1
    reye = p[i]; i += 1
    pairs = {}
    for k in PAIR_KEYS:
        if k == 'spike_tall':
            x, y = p[i], p[i + 1]; i += 2
            z = SPIKE_TALL_Z
        elif k == 'rim_corner':
            x, z = p[i], p[i + 1]; i += 2
            y = 0.0          # gauge: the rim corners define the body's mid-depth
        else:
            x, y, z = p[i], p[i + 1], p[i + 2]; i += 3
        pairs[k] = (x, y, z)
    mids = {}
    for k in MID_KEYS:
        mids[k] = (p[i], p[i + 1]); i += 2
    return P, alpha, phi, f, rho, reye, pairs, mids


def residuals(p, fixed_f=None):
    P, alpha, phi, f, rho, reye, pairs, mids = unpack(p, fixed_f)
    res = []
    for k in PAIR_KEYS:
        x, y, z = pairs[k]
        pts = roll_body(np.array([[-x, y, z], [x, y, z]]), rho)
        uv, zc = project(P, alpha, phi, f, pts)
        obs = np.array(PAIRS[k])
        res.extend(((uv - obs) / 2.0).ravel())
        if k == 'eye':
            rad = f * reye / zc
            res.extend((rad - np.array(EYE_RADIUS_PX)) / 6.0)
    for k in MID_KEYS:
        y, z = mids[k]
        pt = roll_body(np.array([[0.0, y, z]]), rho)
        uv, _ = project(P, alpha, phi, f, pt)
        res.extend(((uv[0] - np.array(MIDLINE[k])) / 2.5))
    # Horizon: v of a level direction straight ahead.
    res.append((CY + f * math.tan(phi) - HORIZON_V) / 10.0)
    # Ground under the body centre.
    uv, _ = project(P, alpha, phi, f, np.array([[0.0, 0.0, 0.0]]))
    res.append((uv[0, 1] - BODY_GROUND_V) / 12.0)
    return np.array(res)


def lm(fun, p0, iters=400):
    p = p0.astype(float).copy()
    lam = 1e-3
    r = fun(p)
    cost = r @ r
    for _ in range(iters):
        J = np.empty((len(r), len(p)))
        for j in range(len(p)):
            h = 1e-6 * max(1.0, abs(p[j]))
            dp = p.copy(); dp[j] += h
            J[:, j] = (fun(dp) - r) / h
        A = J.T @ J
        g = J.T @ r
        while True:
            step = np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-9), -g)
            pn = p + step
            rn = fun(pn)
            cn = rn @ rn
            if cn < cost:
                p, r, cost = pn, rn, cn
                lam = max(lam / 3, 1e-9)
                break
            lam *= 4
            if lam > 1e9:
                return p, cost
        if np.linalg.norm(step) < 1e-9:
            break
    return p, cost


def initial(fixed_f=None):
    p = [-9.0, -24.0, 5.5, math.radians(20), math.radians(-3)]
    p.append(math.log(1500.0))
    p.append(math.radians(6))
    p.append(0.55)
    guess = {'eye': (1.3, -4.2, 7.0), 'rim_corner': (6.0, 0, 7.8), 'spike_tall': (2.5, 0.5),
             'spike_small': (4.4, 0.0, 8.6), 'stalk_cup': (1.2, -4.3, 5.6)}
    for k in PAIR_KEYS:
        g = guess[k]
        p.extend(g if k not in ('spike_tall', 'rim_corner') else ((g[0], g[1]) if k == 'spike_tall' else (g[0], g[2])))
    mid_guess = {'spike_rear': (2.0, 9.5), 'tooth_gap_top': (-4.6, 5.4), 'belly_bottom': (-3.0, 3.0)}
    for k in MID_KEYS:
        p.extend(mid_guess[k])
    return np.array(p)


def pixel_rms(p, fixed_f=None):
    P, alpha, phi, f, rho, reye, pairs, mids = unpack(p, fixed_f)
    errs = []
    for k in PAIR_KEYS:
        x, y, z = pairs[k]
        uv, _ = project(P, alpha, phi, f, roll_body(np.array([[-x, y, z], [x, y, z]]), rho))
        errs.extend(np.linalg.norm(uv - np.array(PAIRS[k]), axis=1))
    for k in MID_KEYS:
        y, z = mids[k]
        uv, _ = project(P, alpha, phi, f, roll_body(np.array([[0.0, y, z]]), rho))
        errs.append(np.linalg.norm(uv[0] - np.array(MIDLINE[k])))
    return float(np.sqrt(np.mean(np.square(errs)))), float(np.max(errs))


def ray_ground(P, alpha, phi, f, uv):
    r, u, d = cam_basis(alpha, phi)
    ray = d + r * (uv[0] - CX) / f - u * (uv[1] - CY) / f
    t = -P[2] / ray[2]
    return P + ray * t


def main():
    profile = []
    for f in (900, 1100, 1300, 1500, 1700, 1900, 2200, 2600, 3000, 3600):
        p0 = initial()
        p0[5] = math.log(f)
        fun = lambda q, f=f: residuals(q, fixed_f=f)
        p, cost = lm(fun, p0)
        rms, mx = pixel_rms(p, fixed_f=f)
        P, alpha, phi, _, rho, reye, pairs, mids = unpack(p, fixed_f=f)
        profile.append({'f_px': f, 'cost': round(float(cost), 3), 'rms_px': round(rms, 2),
                        'max_px': round(mx, 2), 'distance': round(float(np.linalg.norm(P[:2])), 2),
                        'roll_deg': round(math.degrees(rho), 2),
                        'yaw_deg': round(math.degrees(alpha), 2)})
        print('PROFILE', profile[-1])
    f = CHOSEN_F
    p0 = initial()
    p0[5] = math.log(f)
    p, cost = lm(lambda q: residuals(q, fixed_f=f), p0)
    P, alpha, phi, _, rho, reye, pairs, mids = unpack(p, fixed_f=f)
    rms, mx = pixel_rms(p, fixed_f=f)
    print('CHOSEN f', f, 'cost', cost, 'rms', rms, 'max', mx)
    sensor = 36.0
    lens = f * sensor / W
    tips = {k: [round(float(c), 3) for c in ray_ground(P, alpha, phi, f, uv)] for k, uv in GROUND_TIPS.items()}
    out = {
        'image': [W, H],
        'f_px': round(float(f), 2),
        'sensor_width_mm': sensor,
        'lens_mm': round(float(lens), 3),
        'camera_location': [round(float(c), 4) for c in P],
        'yaw_deg': round(math.degrees(alpha), 4),
        'pitch_deg': round(math.degrees(phi), 4),
        'roll_deg': 0.0,
        'body_roll_deg': round(math.degrees(rho), 3),
        'body_roll_pivot_z': 5.0,
        'eye_radius': round(float(reye), 3),
        'pairs_body_frame': {k: [round(float(c), 3) for c in v] for k, v in pairs.items()},
        'midline_body_frame': {k: [0.0] + [round(float(c), 3) for c in v] for k, v in mids.items()},
        'ground_tips_world': tips,
        'rms_px': round(rms, 2),
        'max_px': round(mx, 2),
        'focal_profile': profile,
        'notes': 'Pairs are (x, y, z) with the crab-right member at -x. Roll is applied about the '
                 'body forward axis at z=5 in the reference pose only; the rest pose is level.',
    }
    (HERE / 'source').mkdir(exist_ok=True)
    (HERE / 'source' / 'camera.json').write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != 'focal_profile'}, indent=1))


if __name__ == '__main__':
    main()
