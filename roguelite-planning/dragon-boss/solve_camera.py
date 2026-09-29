"""Solve the reference camera from landmark pixels (system python + numpy).

The reference is one painted view. What it pins down, and how:

* Ground contacts. Every visible claw tip rests on the floor (z ~ 0.08). The
  four feet stand as a squared, mirror-symmetric stance: front claw rows centred
  at (+-a_f, -y_f), hind rows at (+-a_h, y_h). Each foot may splay about Z (the
  right feet visibly point further to the viewer's left than the left feet);
  the four claws of a row are spaced `sp` apart with the middle two pushed
  forward by `dm` (the rows are curved). The hind rows may be up to ~15 %
  smaller (`hsc`, prior 0.92 +- 0.06).
* Verticals are vertical. The painted background (cliff pillars, lava falls)
  and the dragon's legs show no three-point convergence, yet the horizon is
  low: the claw rows put it near v ~ 800 (the near-front row is 1.6x wider than
  the near-hind row and only 43 px lower, which only a very low camera
  produces), and the floor behind the dragon converges there too. That is a
  LEVEL camera with a vertical lens shift, so pitch is held at 0 and the
  principal point's v (= the horizon) is solved. In Blender this is
  camera.shift_y = (v0 - 512) / 1536.
* Scale. The skull top (between the brows, image (492, 198)) sits 11 studs up
  (brief), roughly over the midline (x prior 0 +- 0.8).
* Wings are NOT used: fitted as a mirror pair they miss by 40-95 px, i.e. the
  reference raises them asymmetrically (the right wing is posed higher/closer).

Focal length is profiled: at each f the solve is repeated and the residual and
the implied proportions (stance width, front-to-hind claw-row separation,
camera distance and height) are reported. The claw rows fit to ~2-4 px at any
f, so f is chosen from anatomy: at f = 1150 px (27 mm on a 36 mm sensor) the
front-to-hind separation is ~10 studs, which fits the brief's 30-stud
nose-to-tail dragon with its ~4-stud head, ~3-stud neck and ~13-stud tail.
Longer lenses stretch the stance to 14-18 studs between front and hind feet
(a dragon longer than the brief allows); shorter ones squash it.

Conventions: Blender world, Z up, the dragon faces -Y, +X is the dragon's LEFT
(the viewer's right). "R" landmarks are the dragon's right = viewer left.
Output: source/camera.json.
"""
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
W, H = 1536, 1024
CX = W / 2

CLAWS = {   # left-to-right in the image; lowest point of each claw tip (gridded 3-3.5x crops)
    'FR': [(198, 899), (240, 906), (310, 911)],               # three visible (k = 1..3)
    'FL': [(749, 928), (833, 936), (911, 934), (970, 928)],
    'HR': [(542, 873), (574, 877), (618, 879)],               # three visible (k = 1..3)
    'HL': [(993, 887), (1037, 889), (1087, 889), (1130, 884)],
}
CLAW_K = {'FR': [1, 2, 3], 'FL': [0, 1, 2, 3], 'HR': [1, 2, 3], 'HL': [0, 1, 2, 3]}
SKULL_TOP = (492, 198)
SKULL_TOP_Z = 11.0
CHOSEN_F = 1150.0

NAMES = ['cx', 'cy', 'cz', 'alpha', 'v0', 'a_f', 'y_f', 'a_h', 'y_h',
         's_FR', 's_FL', 's_HR', 's_HL', 'sp', 'dm', 'hsc', 'sk_x', 'sk_y']
IDX = {n: i for i, n in enumerate(NAMES)}


def g(p, n):
    return p[IDX[n]]


def cam_basis(alpha):
    d = np.array([math.sin(alpha), math.cos(alpha), 0.0])
    r = np.array([math.cos(alpha), -math.sin(alpha), 0.0])
    u = np.array([0.0, 0.0, 1.0])
    return r, u, d


def project(P, alpha, v0, f, X):
    r, u, d = cam_basis(alpha)
    q = np.atleast_2d(X) - P
    xc, yc, zc = q @ r, q @ u, q @ d
    return np.stack([CX + f * xc / zc, v0 - f * yc / zc], axis=1), zc


def claw_points(p, foot):
    left = foot[1] == 'L'
    front = foot[0] == 'F'
    a = g(p, 'a_f' if front else 'a_h')
    y = -g(p, 'y_f') if front else g(p, 'y_h')
    c = np.array([a if left else -a, y, 0.08])
    s = g(p, 's_' + foot)
    e = np.array([math.cos(s), math.sin(s), 0.0])
    fwd = np.array([math.sin(s), -math.cos(s), 0.0])
    sc = 1.0 if front else g(p, 'hsc')
    pts = []
    for k in CLAW_K[foot]:
        pts.append(c + sc * ((k - 1.5) * g(p, 'sp') * e + (g(p, 'dm') if k in (1, 2) else 0.0) * fwd))
    return np.array(pts)


def residuals(p, f):
    P = np.array([g(p, 'cx'), g(p, 'cy'), g(p, 'cz')])
    al, v0 = g(p, 'alpha'), g(p, 'v0')
    res = []
    for foot, obs in CLAWS.items():
        uv, _ = project(P, al, v0, f, claw_points(p, foot))
        sig = 2.5 if foot in ('FL', 'HL') else 5.0
        res.extend(((uv - np.array(obs)) / sig).ravel())
    sk = np.array([g(p, 'sk_x'), g(p, 'sk_y'), SKULL_TOP_Z])
    uv, _ = project(P, al, v0, f, sk)
    res.extend(((uv[0] - np.array(SKULL_TOP)) / 3.0).ravel())
    res.append(g(p, 'sk_x') / 0.8)
    res.append((g(p, 'dm') - 0.25) / 0.2)
    res.append((g(p, 'hsc') - 0.92) / 0.06)
    res.append((g(p, 'a_h') - g(p, 'a_f')) / 1.5)
    for foot in ('FR', 'FL', 'HR', 'HL'):
        res.append(g(p, 's_' + foot) / math.radians(30))
    return np.array(res)


def lm(fun, p0, iters=200):
    p = p0.astype(float).copy()
    lam = 1e-3
    r = fun(p)
    cost = r @ r
    for _ in range(iters):
        J = np.empty((len(r), len(p)))
        for j in range(len(p)):
            h = 1e-6 * max(1.0, abs(p[j]))
            dp = p.copy()
            dp[j] += h
            J[:, j] = (fun(dp) - r) / h
        A = J.T @ J
        gr = J.T @ r
        while True:
            step = np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-9), -gr)
            pn = p + step
            rn = fun(pn)
            cn = rn @ rn
            if cn < cost:
                p, r, cost = pn, rn, cn
                lam = max(lam / 3, 1e-9)
                break
            lam *= 4
            if lam > 1e10:
                return p, cost
        if np.linalg.norm(step) < 1e-9:
            break
    return p, cost


def initial():
    p = np.zeros(len(NAMES))
    init = {'cx': 8.0, 'cy': -18.0, 'cz': 1.8, 'alpha': math.radians(-25), 'v0': 800.0,
            'a_f': 4.5, 'y_f': 5.0, 'a_h': 4.8, 'y_h': 5.0, 'sp': 1.05, 'dm': 0.25, 'hsc': 0.92,
            's_FR': math.radians(-15), 's_FL': math.radians(15), 's_HR': math.radians(-10),
            's_HL': math.radians(5), 'sk_x': 0.0, 'sk_y': -8.0}
    for k, v in init.items():
        p[IDX[k]] = v
    return p


def claw_rms(p, f):
    P = np.array([g(p, 'cx'), g(p, 'cy'), g(p, 'cz')])
    errs = []
    for foot, obs in CLAWS.items():
        uv, _ = project(P, g(p, 'alpha'), g(p, 'v0'), f, claw_points(p, foot))
        errs.extend(np.linalg.norm(uv - np.array(obs), axis=1))
    return float(np.sqrt(np.mean(np.square(errs)))), float(np.max(errs))


def summary(p, f, cost):
    rms, mx = claw_rms(p, f)
    P = np.array([g(p, 'cx'), g(p, 'cy'), g(p, 'cz')])
    return {'f_px': f, 'lens_mm': round(f * 36 / W, 2), 'cost': round(float(cost), 2),
            'claw_rms_px': round(rms, 2), 'claw_max_px': round(mx, 2),
            'cam': [round(float(v), 2) for v in P], 'dist_xy': round(float(np.hypot(P[0], P[1])), 2),
            'yaw_deg': round(math.degrees(g(p, 'alpha')), 2), 'horizon_v': round(float(g(p, 'v0')), 1),
            'stance_halfwidth_front_hind': [round(float(g(p, 'a_f')), 2), round(float(g(p, 'a_h')), 2)],
            'front_to_hind_sep': round(float(g(p, 'y_f') + g(p, 'y_h')), 2),
            'claw_spacing': round(float(g(p, 'sp')), 3), 'hind_scale': round(float(g(p, 'hsc')), 3),
            'splay_deg': {k: round(math.degrees(g(p, 's_' + k)), 1) for k in ('FR', 'FL', 'HR', 'HL')},
            'skull_top': [round(float(g(p, 'sk_x')), 2), round(float(g(p, 'sk_y')), 2), SKULL_TOP_Z]}


def main():
    profile = []
    for f in (800, 950, 1050, 1150, 1250, 1400, 1600, 1900, 2300):
        p, cost = lm(lambda q, f=f: residuals(q, f), initial())
        profile.append(summary(p, f, cost))
        print('PROFILE', json.dumps(profile[-1]))
    f = CHOSEN_F
    p, cost = lm(lambda q: residuals(q, f), initial())
    s = summary(p, f, cost)
    out = {
        'image': [W, H], 'f_px': f, 'sensor_width_mm': 36.0, 'lens_mm': round(f * 36.0 / W, 4),
        'camera_location': [round(float(g(p, k)), 4) for k in ('cx', 'cy', 'cz')],
        'yaw_deg': round(math.degrees(g(p, 'alpha')), 4), 'pitch_deg': 0.0, 'roll_deg': 0.0,
        'principal_v': round(float(g(p, 'v0')), 3),
        'blender_shift_y': round((float(g(p, 'v0')) - H / 2) / W, 5),
        'params': {n: round(float(p[i]), 4) for n, i in IDX.items()},
        'feet_claw_rows_world': {k: [[round(float(c), 3) for c in pt] for pt in claw_points(p, k)] for k in CLAWS},
        'summary': s,
        'focal_profile': profile,
        'conventions': 'Blender world, Z up, dragon faces -Y, +X = dragon left. Level camera: '
                       'view dir (sin a, cos a, 0), right (cos a, -sin a, 0); u = cx + f*xc/zc, '
                       'v = principal_v - f*yc/zc.',
    }
    (HERE / 'source').mkdir(exist_ok=True)
    (HERE / 'source' / 'camera.json').write_text(json.dumps(out, indent=2))
    print('CHOSEN', json.dumps(s))


if __name__ == '__main__':
    main()
