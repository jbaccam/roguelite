"""Solve the reference camera from landmark pixels. System Python + numpy.

    python solve_camera.py

Model: pinhole camera, square pixels, principal point at the image centre
(543, 724), zero roll. Blender world: Z up, the character faces -Y, +X is the
character's LEFT (viewer's right). Unknowns:

    f        focal length in pixels
    cx,cy,cz camera position (studs)
    pitch    rotation about the camera's right axis (+ looks up)
    yaw      rotation about Z (+ turns the view toward +X)
    x_i      the unknown lateral position of each anchor

A single picture cannot fix absolute depth, so the depth (Y) of each anchor is
a stance prior (listed in ANCHORS and the README). Absolute scale comes from the
crown: the top of the head is 13.7 studs above the ground in the reference
stance (the in-game height the user asked to keep). Everything else is solved
by damped Gauss-Newton on the reprojection error with weak priors:
  pitch 0 +- 2 deg  (the cliffs' vertical edges in the background stay vertical)
  yaw   0 +- 1 deg
  f     2300 +- 400 px (the foot-depth cue alone is too weak to pin the lens)

Cross-check: the near (left) foot's sole edge sits 38 px lower than the far
(right) foot's; with the solved camera that is the 1.9-stud stance offset.
"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
W, H = 1086, 1448
PP = np.array([W / 2.0, H / 2.0])

TARGET_HEIGHT = 13.7          # studs, crown to ground, reference stance

# (name, pixel u, v, depth prior y, height z, weight)
ANCHORS = [
    ('head_top_back',             538, 214, 0.35, TARGET_HEIGHT, 1.0),
    ('foot_L_front_bottom_left',  752, 1262, -2.85, 0.0, 1.0),
    ('foot_L_front_bottom_right', 969, 1246, -2.45, 0.0, 1.0),
    ('foot_R_front_bottom',       470, 1224, -0.80, 0.0, 1.0),
]
PRIORS = {'f': (2300.0, 400.0), 'pitch': (0.0, 2.0), 'yaw': (0.0, 1.0)}


def basis(pitch, yaw):
    cp, sp, cyw, syw = np.cos(pitch), np.sin(pitch), np.cos(yaw), np.sin(yaw)
    F = np.array([syw * cp, cyw * cp, sp])
    R = np.array([cyw, -syw, 0.0])
    U = np.cross(R, F)
    return F, R, U


def project(params, P):
    f, cx, cy, cz, pitch, yaw = params
    F, R, U = basis(pitch, yaw)
    d = P - np.array([cx, cy, cz])
    depth = d @ F
    return np.stack([PP[0] + f * (d @ R) / depth, PP[1] - f * (d @ U) / depth], -1), depth


def residuals(theta):
    cam = theta[:6]
    xs = theta[6:]
    res = []
    for i, (name, u, v, y, z, w) in enumerate(ANCHORS):
        P = np.array([xs[i], y, z])
        uv, _ = project(cam, P[None])
        res += [w * (uv[0, 0] - u), w * (uv[0, 1] - v)]
    # weak priors expressed as pixel-equivalent residuals
    res.append((cam[0] - PRIORS['f'][0]) / PRIORS['f'][1] * 2.0)
    res.append((cam[4] - np.radians(PRIORS['pitch'][0])) / np.radians(PRIORS['pitch'][1]) * 2.0)
    res.append((cam[5] - np.radians(PRIORS['yaw'][0])) / np.radians(PRIORS['yaw'][1]) * 2.0)
    return np.array(res)


def solve():
    theta = np.array([2300.0, 0.0, -30.0, 6.5, 0.0, 0.0] + [0.0] * len(ANCHORS))
    lam = 1e-2
    for it in range(600):
        r = residuals(theta)
        J = np.zeros((len(r), len(theta)))
        for j in range(len(theta)):
            h = 1e-5 * max(1.0, abs(theta[j]))
            t2 = theta.copy()
            t2[j] += h
            J[:, j] = (residuals(t2) - r) / h
        A = J.T @ J + lam * np.diag(np.diag(J.T @ J) + 1e-9)
        step = np.linalg.solve(A, -J.T @ r)
        cand = theta + step
        if (residuals(cand) ** 2).sum() < (r ** 2).sum():
            theta, lam = cand, lam * 0.5
        else:
            lam *= 4
        if np.abs(step).max() < 1e-10:
            break
    return theta, residuals(theta)


def main():
    theta, r = solve()
    f, cx, cy, cz, pitch, yaw = theta[:6]
    rows = []
    for i, (name, u, v, y, z, w) in enumerate(ANCHORS):
        P = np.array([theta[6 + i], y, z])
        uv, depth = project(theta[:6], P[None])
        rows.append({'name': name, 'pixel': [u, v], 'world': [round(float(c), 4) for c in P],
                     'reprojected': [round(float(c), 2) for c in uv[0]], 'depth': round(float(depth[0]), 3)})
    sensor = 36.0
    out = {
        'image': [W, H],
        'principal_point_px': PP.tolist(),
        'focal_px': round(float(f), 2),
        'blender_lens_mm_sensor36_fit_vertical': round(float(f) * sensor / H, 3),
        'camera_location': [round(float(cx), 4), round(float(cy), 4), round(float(cz), 4)],
        'pitch_deg': round(float(np.degrees(pitch)), 4),
        'yaw_deg': round(float(np.degrees(yaw)), 4),
        'vertical_fov_deg': round(float(np.degrees(2 * np.arctan(H / 2 / f))), 3),
        'rms_reprojection_px': round(float(np.sqrt((r[:-3] ** 2).mean())), 3),
        'crown_height_studs': TARGET_HEIGHT,
        'anchors': rows,
        'priors': PRIORS,
        'depth_priors_note': 'Y of each anchor is a stance prior: the left foot 1.9 studs ahead of the right, '
                             'the back of the crown 0.35 behind the pelvis centre (he hunches forward). '
                             'Everything else is solved.',
    }
    (HERE / 'source' / 'camera_solution.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
