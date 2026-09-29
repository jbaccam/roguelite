"""Reference camera for the Dragon (pure numpy; works in system python and in
Blender's bundled python). Reads source/camera.json written by solve_camera.py.

Level camera (pitch 0) with a vertical lens shift: u = 768 + f*xc/zc,
v = v0 - f*yc/zc. Blender world, Z up, dragon faces -Y, +X = dragon left.
"""
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CAM = json.loads((HERE / 'source' / 'camera.json').read_text())
W, H = CAM['image']
F = float(CAM['f_px'])
P = np.array(CAM['camera_location'], float)
ALPHA = math.radians(CAM['yaw_deg'])
V0 = float(CAM['principal_v'])
CX = W / 2.0
R_AX = np.array([math.cos(ALPHA), -math.sin(ALPHA), 0.0])
U_AX = np.array([0.0, 0.0, 1.0])
D_AX = np.array([math.sin(ALPHA), math.cos(ALPHA), 0.0])


def project(X):
    X = np.atleast_2d(np.asarray(X, float))
    q = X - P
    xc, yc, zc = q @ R_AX, q @ U_AX, q @ D_AX
    return np.stack([CX + F * xc / zc, V0 - F * yc / zc], axis=1), zc


def ray(uv):
    u, v = uv
    d = D_AX + R_AX * (u - CX) / F - U_AX * (v - V0) / F
    return d / np.linalg.norm(d)


def on_plane(uv, n, p0):
    """Back-project pixel uv onto the plane through p0 with normal n."""
    d = ray(uv)
    n = np.asarray(n, float)
    t = ((np.asarray(p0, float) - P) @ n) / (d @ n)
    return P + d * t


def at_depth(uv, depth):
    """Point on the pixel's ray at camera-space depth zc = depth."""
    d = ray(uv)
    return P + d * (depth / (d @ D_AX))


def px_per_stud(X):
    """Pixels per stud of a small object at X (fronto-parallel)."""
    _, zc = project(X)
    return F / zc[0]


def blender_camera_settings():
    """Lens (mm, 36 mm sensor fit horizontal), shift_y, location and rotation (XYZ Euler)."""
    lens = F * 36.0 / W
    shift_y = (V0 - H / 2.0) / W      # +shift moves the frustum up: horizon lands below centre
    # Blender camera looks down its local -Z with +Y up. Level camera with yaw ALPHA
    # (view dir (sin a, cos a, 0)): rotate X by 90 deg, then Z by -ALPHA.
    rot = (math.pi / 2, 0.0, -ALPHA)
    return {'lens': lens, 'shift_y': shift_y, 'location': tuple(P), 'rotation_euler': rot}
