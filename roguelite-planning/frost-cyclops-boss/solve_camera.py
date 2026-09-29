"""Solve the reference camera from landmark pixels. System Python + numpy.

    python solve_camera.py

Model: pinhole camera, square pixels, principal point at the image centre
(543, 724), zero roll. Blender world: Z up, the character faces -Y, +X is the
character's LEFT (viewer's right). Unknowns:

    f        focal length in pixels
    cx,cy,cz camera position (studs)
    pitch    rotation about the camera's right axis (+ looks up)
    yaw      rotation about Z (+ turns the view toward +X)
    x_i      the unknown lateral position of each ground/axis landmark

A single photograph cannot fix absolute depth, so the depth (Y) of each anchor
is a design prior taken from the stance (recorded below and in the README).
Everything else is solved by damped Gauss-Newton on the reprojection error, with
weak priors pitch = 0 +- 0.5 deg and yaw = 0 +- 1 deg (the cliffs' vertical
edges in the background are vertical, so the camera is not tilted).

The cross-check that makes the priors trustworthy: the near (left) big toenail
is 57 px wide and the far (right) one 53 px. For equal nails that ratio is the
depth ratio, and it independently predicts the horizon at v~715 -- within 9 px
of the image centre, i.e. zero pitch, which is what the solve returns.
"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
W, H = 1086, 1448
PP = np.array([W / 2.0, H / 2.0])

TARGET_HEIGHT = 13.0          # studs, crown to ground, reference stance

# (name, pixel u, v, depth prior y, height z or None, weight)
# z None -> height unknown (solved); x is always solved.
ANCHORS = [
    ('head_top',          541, 185, -0.70, TARGET_HEIGHT, 1.0),
    ('foot_L_toe_bottom', 760, 1290, -3.00, 0.0, 1.0),
    ('foot_R_toe_bottom', 395, 1248, -1.00, 0.0, 1.0),
    ('club_head_bottom',  215, 1300, -3.05, 0.0, 0.6),
    ('foot_L_little_toe', 905, 1283, -2.72, 0.0, 0.6),
    ('foot_L_big_toe_in', 668, 1287, -2.95, 0.0, 0.6),
]


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
    # priors (scaled into pixel-equivalent residuals)
    res.append((cam[4] - 0.0) / np.radians(0.5) * 2.0)
    res.append((cam[5] - 0.0) / np.radians(1.0) * 2.0)
    return np.array(res)


def solve():
    theta = np.array([2000.0, 0.0, -24.0, 6.3, 0.0, 0.0] + [0.0] * len(ANCHORS))
    lam = 1e-2
    for it in range(400):
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
        if np.abs(step).max() < 1e-9:
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
                     'reprojected': [round(float(c), 2) for c in uv[0]],
                     'depth': round(float(depth[0]), 3)})
    sensor = 36.0          # Blender sensor_fit AUTO -> larger side (height, 1448 px)
    out = {
        'image': [W, H],
        'principal_point_px': PP.tolist(),
        'focal_px': round(float(f), 2),
        'blender_lens_mm_sensor36_fit_vertical': round(float(f) * sensor / H, 3),
        'camera_location': [round(float(cx), 4), round(float(cy), 4), round(float(cz), 4)],
        'pitch_deg': round(float(np.degrees(pitch)), 4),
        'yaw_deg': round(float(np.degrees(yaw)), 4),
        'vertical_fov_deg': round(float(np.degrees(2 * np.arctan(H / 2 / f))), 3),
        'rms_reprojection_px': round(float(np.sqrt((r[:-2] ** 2).mean())), 3),
        'anchors': rows,
        'depth_priors_note': 'Y of each anchor is a stance prior: left toes 1.6 studs ahead of the '
                             'right toes, crown 2.3 studs behind the left toes. Everything else solved.',
    }
    (HERE / 'source' / 'camera_solution.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
