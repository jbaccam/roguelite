"""Solve the reference camera from measured landmark pixels (system python + numpy).

    python camera_solve.py        -> writes source/camera_solve.json

Pinhole model, principal point at the image centre, no roll. The camera sits at
(xc, -D, h) looking toward +Y, pitched up by `pitch`. The character stands at
the origin facing -Y, ground z = 0, 1 unit = 1 stud.

A single view cannot fix depth on its own, so the solve combines hard
measurements with a small number of explicit, documented priors:

  measured (pixels, see source/REFERENCE_NOTES.md)
    uraeus top, both toe fronts, staff foot, both ankle-band centres and
    their image widths, the eye midpoint, and the staff-foot top-face sliver
  anchor
    the uraeus top is 12.5 studs above the ground (brief)
  priors (1-sigma, weak)
    horizon row ~1000 +- 60 px: the far sand/cliff base is at y~1095 and the
      horizon must sit a little above it
    both ankle bands are the same physical band at the same height
    depth layout: the uraeus sits ~0.95 in front of the pelvis axis, the left
      toe front ~2.9 in front, the right toe ~0.8 in front (left foot steps
      forward: its band images 11.7% wider and its sole 42 px lower), the
      staff foot ~2.2 in front (it is planted under the forward fist)

Gauss-Newton with a numeric Jacobian; residuals are divided by their sigma.
"""
import json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
W_IMG, H_IMG = 1086, 1448
CX, CY = W_IMG / 2.0, H_IMG / 2.0

OBS = {
    'uraeus_top': (545.0, 139.0),
    'toe_L_front': (843.0, 1360.0),
    'toe_R_front': (300.0, 1318.0),
    'staff_foot': (207.0, 1340.0),
    'ankle_L_centre': (778.0, 1178.0), 'ankle_L_width': 210.0,
    'ankle_R_centre': (377.0, 1162.0), 'ankle_R_width': 188.0,
    'eye_mid': (550.0, 279.0),
}
PRIORS = {
    'horizon': (1000.0, 60.0),
    'y_uraeus': (-0.95, 0.35), 'y_toeL': (-2.9, 0.8), 'y_toeR': (-0.8, 0.8),
    'y_staff': (-2.2, 0.8), 'band_z': (1.95, 0.25), 'band_w': (2.15, 0.5),
    'staff_top_angle_deg': (6.5, 3.0), 'x_head': (0.0, 0.15),
}

# parameter vector
NAMES = ['f', 'h', 'pitch', 'D', 'xc', 'xu', 'yu', 'xl', 'yl', 'xr', 'yr', 'xs', 'ys',
         'bw', 'bz', 'xal', 'xar']
P0 = np.array([1900, 3.8, np.radians(7), 20.5, 0.0, 0.0, -0.95, 2.6, -2.9, -2.4, -0.8,
               -3.6, -2.2, 2.15, 1.95, 2.4, -1.8], float)


def project(p, P):
    f, h, ph, D, xc = p[:5]
    C = np.array([xc, -D, h])
    F = np.array([0, np.cos(ph), np.sin(ph)])
    U = np.array([0, -np.sin(ph), np.cos(ph)])
    d = np.asarray(P, float) - C
    zc = d @ F
    return np.array([CX + f * d[0] / zc, CY - f * (d @ U) / zc]), zc


def residuals(p):
    r = []
    f, h, ph, D, xc, xu, yu, xl, yl, xr, yr, xs, ys, bw, bz, xal, xar = p
    px_sigma = 3.0

    def img(name, P):
        uv, _ = project(p, P)
        o = OBS[name]
        r.extend([(uv[0] - o[0]) / px_sigma, (uv[1] - o[1]) / px_sigma])

    img('uraeus_top', (xu, yu, 12.5))
    img('toe_L_front', (xl, yl, 0.0))
    img('toe_R_front', (xr, yr, 0.0))
    img('staff_foot', (xs, ys, 0.0))
    # ankle bands sit ~1.3 studs behind the toe front
    for side, x, y in (('L', xal, yl + 1.3), ('R', xar, yr + 1.2)):
        c, zc = project(p, (x, y, bz))
        o = OBS[f'ankle_{side}_centre']
        r.extend([(c[0] - o[0]) / 4.0, (c[1] - o[1]) / 4.0])
        w = f * bw / zc
        r.append((w - OBS[f'ankle_{side}_width']) / 4.0)
    # eye midpoint: head centre line, ~11.0 studs up, a little in front of axis
    img('eye_mid', (0.0 + p[5] * 0, -0.6, 11.0))
    # priors
    horizon = CY + f * np.tan(ph)
    r.append((horizon - PRIORS['horizon'][0]) / PRIORS['horizon'][1])
    for key, val in (('y_uraeus', yu), ('y_toeL', yl), ('y_toeR', yr), ('y_staff', ys),
                     ('band_z', bz), ('band_w', bw), ('x_head', xu)):
        m, s = PRIORS[key]
        r.append((val - m) / s)
    # staff-foot top face (1.15 studs up) is seen as a sliver: view angle ~6.5 deg
    ang = np.degrees(np.arctan2(h - 1.15, ys + D))
    m, s = PRIORS['staff_top_angle_deg']
    r.append((ang - m) / s)
    return np.array(r)


def solve():
    p = P0.copy()
    for it in range(200):
        r = residuals(p)
        J = np.zeros((len(r), len(p)))
        for i in range(len(p)):
            dp = np.zeros_like(p)
            dp[i] = 1e-5 * max(1.0, abs(p[i]))
            J[:, i] = (residuals(p + dp) - r) / dp[i]
        step, *_ = np.linalg.lstsq(J, -r, rcond=None)
        p = p + 0.7 * step
        if np.linalg.norm(step) < 1e-9:
            break
    r = residuals(p)
    J = np.zeros((len(r), len(p)))
    for i in range(len(p)):
        dp = np.zeros_like(p)
        dp[i] = 1e-5 * max(1.0, abs(p[i]))
        J[:, i] = (residuals(p + dp) - r) / dp[i]
    cov = np.linalg.pinv(J.T @ J)
    sig = np.sqrt(np.diag(cov))
    return p, r, sig


if __name__ == '__main__':
    p, r, sig = solve()
    f, h, ph, D, xc = p[:5]
    lens36 = f * 36.0 / H_IMG           # Blender sensor fit AUTO -> 36 mm spans 1448 px
    out = {
        'image': [W_IMG, H_IMG],
        'principal_point': [CX, CY],
        'focal_px': round(float(f), 2), 'focal_px_sigma': round(float(sig[0]), 1),
        'blender_lens_mm_sensor36_fit_auto': round(float(lens36), 3),
        'camera_height': round(float(h), 4), 'camera_height_sigma': round(float(sig[1]), 3),
        'pitch_up_deg': round(float(np.degrees(ph)), 4),
        'pitch_sigma_deg': round(float(np.degrees(sig[2])), 3),
        'distance_D': round(float(D), 4), 'distance_sigma': round(float(sig[3]), 3),
        'camera_x': round(float(xc), 4),
        'camera_location': [round(float(xc), 4), round(float(-D), 4), round(float(h), 4)],
        'horizon_row': round(float(CY + f * np.tan(ph)), 1),
        'landmarks_world': {n: round(float(v), 4) for n, v in zip(NAMES[5:], p[5:])},
        'rms_residual_sigma_units': round(float(np.sqrt(np.mean(r ** 2))), 4),
        'residuals': [round(float(v), 3) for v in r],
        'observations_px': OBS, 'priors': PRIORS,
    }
    (HERE / 'source').mkdir(exist_ok=True)
    (HERE / 'source' / 'camera_solve.json').write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in ('focal_px', 'blender_lens_mm_sensor36_fit_auto',
                                           'camera_height', 'pitch_up_deg', 'distance_D',
                                           'camera_x', 'horizon_row',
                                           'rms_residual_sigma_units')}, indent=1))
    print('landmarks', out['landmarks_world'])
    print('residuals', out['residuals'])
    print('sigmas', dict(zip(NAMES, np.round(sig, 3))))
