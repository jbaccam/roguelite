"""The solved reference camera (source/camera_solution.json), shifted so the
pelvis centre sits on world X = 0. Pure numpy."""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
W, H = 1086, 1448


class RefCam:
    def __init__(self, path=HERE / 'source' / 'camera_solution.json', pelvis_px=(571, 820), pelvis_y=0.1):
        s = json.loads(Path(path).read_text())
        self.f = s['focal_px']
        self.pp = np.array(s['principal_point_px'], float)
        self.C = np.array(s['camera_location'], float)
        self.pitch = np.radians(s['pitch_deg'])
        self.yaw = np.radians(s['yaw_deg'])
        cp, sp, cy, sy = np.cos(self.pitch), np.sin(self.pitch), np.cos(self.yaw), np.sin(self.yaw)
        self.F = np.array([sy * cp, cy * cp, sp])
        self.R = np.array([cy, -sy, 0.0])
        self.U = np.cross(self.R, self.F)
        # shift world X so the pelvis centre is at x = 0
        p = self.at(*pelvis_px, pelvis_y)
        self.C[0] -= p[0]
        self.lens_mm = self.f * 36.0 / H

    def ray(self, u, v):
        d = self.F + ((u - self.pp[0]) / self.f) * self.R - ((v - self.pp[1]) / self.f) * self.U
        return self.C.copy(), d

    def at(self, u, v, y):
        """World point on the plane Y = y that projects to pixel (u, v)."""
        o, d = self.ray(u, v)
        t = (y - o[1]) / d[1]
        return o + t * d

    def at_z(self, u, v, z):
        o, d = self.ray(u, v)
        t = (z - o[2]) / d[2]
        return o + t * d

    def project(self, P):
        P = np.atleast_2d(np.asarray(P, float))
        d = P - self.C
        depth = d @ self.F
        u = self.pp[0] + self.f * (d @ self.R) / depth
        v = self.pp[1] - self.f * (d @ self.U) / depth
        return np.stack([u, v], -1), depth

    def scale(self, y):
        """Pixels per stud on the plane Y = y (near the optical axis)."""
        return self.f / ((y - self.C[1]) * self.F[1])

    def px(self, n, y):
        """Convert a pixel length at depth plane y into studs."""
        return n / self.scale(y)
