"""Fit a pinhole camera to chest landmarks read off the reference painting (1920x1080).
python fit_camera.py  -> prints yaw, elev, dist, focal_px, target and residuals; writes ref_camera.json"""
import json
import math
from pathlib import Path

import numpy as np

W, H = 1920, 1080
L = {  # world (our model, studs) -> painting pixel
    "lock_orb": ((0, -2.62, 4.13), (1148, 565)),
    "left_orb": ((-3.58, 0, 3.46), (775, 635)),
    "fl_top": ((-3.72, -2.84, 4.08), (905, 655)),
    "fl_bot": ((-3.72, -2.84, 0.58), (905, 935)),
    "fr_top": ((2.1, -2.84, 4.08), (1300, 540)),
    "fr_bot": ((2.1, -2.84, 0.58), (1300, 790)),
    "bl_bot": ((-3.72, 1.3, 0.58), (690, 795)),
}
P = np.array([v[0] for v in L.values()], float)
Q = np.array([v[1] for v in L.values()], float)


def project(x, pts):
    yaw, elev, dist, f, cx, cy = x
    tx, ty, tz = 0.0, 0.0, 3.0
    y, e = math.radians(yaw), math.radians(elev)
    d = np.array((-math.sin(y) * math.cos(e), -math.cos(y) * math.cos(e), math.sin(e)))
    T = np.array((tx, ty, tz))
    C = T + d * dist
    fw = -d
    r = np.cross(fw, (0, 0, 1)); r /= np.linalg.norm(r)
    u = np.cross(r, fw)
    q = pts - C
    xc, yc, zc = q @ r, q @ u, q @ fw
    return np.stack([cx + f * xc / zc, cy - f * yc / zc], 1)


def cost(x):
    return float(((project(x, P) - Q) ** 2).sum())


def nelder_mead(f, x0, step, iters=6000):
    n = len(x0)
    S = [np.array(x0, float)] + [np.array(x0, float) + np.eye(n)[i] * step[i] for i in range(n)]
    F = [f(s) for s in S]
    for _ in range(iters):
        o = np.argsort(F); S = [S[i] for i in o]; F = [F[i] for i in o]
        c = np.mean(S[:-1], 0)
        xr = c + (c - S[-1]); fr = f(xr)
        if fr < F[0]:
            xe = c + 2 * (c - S[-1]); fe = f(xe)
            S[-1], F[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < F[-2]:
            S[-1], F[-1] = xr, fr
        else:
            xc = c + 0.5 * (S[-1] - c); fc = f(xc)
            if fc < F[-1]:
                S[-1], F[-1] = xc, fc
            else:
                S = [S[0]] + [S[0] + 0.5 * (s - S[0]) for s in S[1:]]; F = [f(s) for s in S]
    i = int(np.argmin(F))
    return S[i], F[i]


best = None
for yaw0 in (20, 30, 40):
    for el0 in (10, 20, 30):
        for d0 in (12, 20, 35):
            x, c = nelder_mead(cost, [yaw0, el0, d0, d0 * 75, 1000, 600], [5, 5, 3, 200, 30, 30])
            if best is None or c < best[1]:
                best = (x, c)
x, c = best
res = project(x, P) - Q
print("fit yaw %.2f elev %.2f dist %.2f focal %.1f principal (%.1f %.1f)" % tuple(x))
print("rms px %.1f" % math.sqrt(c / len(P)))
for k, r in zip(L, res):
    print("  %-9s %6.1f %6.1f" % (k, r[0], r[1]))
Path(__file__).with_name("ref_camera.json").write_text(json.dumps(dict(zip(["yaw", "elev", "dist", "focal_px", "cx", "cy"], [float(v) for v in x]))))
