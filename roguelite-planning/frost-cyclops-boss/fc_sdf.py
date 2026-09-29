"""Signed-distance sculpting helpers for the Frost Cyclops generator.

Pure numpy (works in Blender's bundled Python and in system Python). Nothing
here touches bpy, so it can be unit-tested outside Blender.

A body is a list of primitives, each with a smooth-union radius `k` and a
`bone` tag. The grid SDF is the ordered smooth-min of all primitives; the same
primitives are re-evaluated at the final vertices to derive skin weights, which
is why every primitive carries the bone that owns it.
"""
import math

import numpy as np


# ----------------------------------------------------------------- rotations
def rot_xyz(rx=0.0, ry=0.0, rz=0.0):
    """Rotation matrix, degrees, applied X then Y then Z (Blender 'XYZ')."""
    rx, ry, rz = map(math.radians, (rx, ry, rz))
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def axis_angle(axis, deg):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def frame_from(z_axis, x_hint=(1, 0, 0)):
    """Orthonormal frame whose local Z is z_axis (columns = local X, Y, Z)."""
    z = np.asarray(z_axis, float)
    z = z / np.linalg.norm(z)
    x = np.asarray(x_hint, float)
    x = x - z * (x @ z)
    if np.linalg.norm(x) < 1e-6:
        x = np.array([0.0, 1.0, 0.0]) - z * z[1]
    x = x / np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], 1)


# ------------------------------------------------------------ primitives
class Prim:
    """Base: subclasses implement `local(p)` on points already in local frame."""
    kind = 'prim'

    def __init__(self, center, R=None, k=0.25, bone='UpperTorso', op='union', tag=''):
        self.c = np.asarray(center, float)
        self.R = np.eye(3) if R is None else np.asarray(R, float)
        self.k = float(k)
        self.bone = bone
        self.op = op            # 'union' | 'sub' | 'inter'
        self.tag = tag

    def sdf(self, P):
        q = (P - self.c) @ self.R          # world -> local (R columns = local axes)
        return self.local(q)

    def bounds(self):
        r = self.extent()
        corners = np.array([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]) * r
        w = corners @ self.R.T + self.c
        pad = self.k + 0.05
        return w.min(0) - pad, w.max(0) + pad

    def transformed(self, M, pivot):
        """Rigidly rotate this primitive about `pivot` by 3x3 M (returns self)."""
        pivot = np.asarray(pivot, float)
        self.c = (self.c - pivot) @ M.T + pivot
        self.R = M @ self.R
        return self


class Ellipsoid(Prim):
    kind = 'ellipsoid'

    def __init__(self, center, radii, R=None, **kw):
        super().__init__(center, R, **kw)
        self.r = np.asarray(radii, float)

    def local(self, q):
        # Inigo Quilez's bound-corrected ellipsoid distance.
        k0 = np.linalg.norm(q / self.r, axis=-1)
        k1 = np.linalg.norm(q / (self.r * self.r), axis=-1)
        return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)

    def extent(self):
        return self.r


class RoundBox(Prim):
    kind = 'roundbox'

    def __init__(self, center, half, R=None, round_=0.1, **kw):
        super().__init__(center, R, **kw)
        self.h = np.asarray(half, float)
        self.rr = float(round_)

    def local(self, q):
        d = np.abs(q) - (self.h - self.rr)
        out = np.linalg.norm(np.maximum(d, 0.0), axis=-1)
        inside = np.minimum(np.max(d, axis=-1), 0.0)
        return out + inside - self.rr

    def extent(self):
        return self.h


class TaperBox(Prim):
    """Rounded box whose X/Y half-size scales linearly along local Z
    (scale_bottom at z=-h, 1 at z=+h). Distance is approximate (Lipschitz-safe
    enough for smooth-union sculpting)."""
    kind = 'taperbox'

    def __init__(self, center, half, R=None, round_=0.1, scale_bottom=0.8, **kw):
        super().__init__(center, R, **kw)
        self.h = np.asarray(half, float)
        self.rr = float(round_)
        self.sb = float(scale_bottom)

    def local(self, q):
        t = np.clip((q[..., 2] / self.h[2] + 1.0) * 0.5, 0.0, 1.0)
        s = self.sb + (1.0 - self.sb) * t
        hx = self.h[0] * s
        hy = self.h[1] * s
        d = np.stack([np.abs(q[..., 0]) - (hx - self.rr), np.abs(q[..., 1]) - (hy - self.rr),
                      np.abs(q[..., 2]) - (self.h[2] - self.rr)], -1)
        out = np.linalg.norm(np.maximum(d, 0.0), axis=-1)
        inside = np.minimum(np.max(d, axis=-1), 0.0)
        return (out + inside - self.rr) * 0.9

    def extent(self):
        return self.h


class RoundCone(Prim):
    """Capsule with different end radii between points a and b (world)."""
    kind = 'roundcone'

    def __init__(self, a, b, ra, rb, k=0.25, bone='UpperTorso', op='union', tag='', squash=None, x_hint=(1, 0, 0)):
        a = np.asarray(a, float)
        b = np.asarray(b, float)
        axis = b - a
        L = float(np.linalg.norm(axis))
        R = frame_from(axis, x_hint)
        super().__init__(a, R, k=k, bone=bone, op=op, tag=tag)
        self.L = L
        self.ra = float(ra)
        self.rb = float(rb)
        # optional elliptic cross-section: scale local x,y (1,1 = round)
        self.sq = np.asarray(squash if squash is not None else (1.0, 1.0), float)

    def local(self, q):
        q = q.copy()
        q[..., 0] /= self.sq[0]
        q[..., 1] /= self.sq[1]
        r1, r2, h = self.ra, self.rb, self.L
        b = (r1 - r2) / h
        a = math.sqrt(max(1e-9, 1.0 - b * b))
        qx = np.sqrt(q[..., 0] ** 2 + q[..., 1] ** 2)
        qy = q[..., 2]
        k = -b * qx + a * qy     # note: IQ uses dot(q, vec2(-b, a))
        d1 = np.sqrt(qx * qx + qy * qy) - r1
        d2 = np.sqrt(qx * qx + (qy - h) ** 2) - r2
        d3 = qx * a + qy * b - r1
        out = np.where(k < 0.0, d1, np.where(k > a * h, d2, d3))
        return out * min(self.sq.min(), 1.0)

    def extent(self):
        m = max(self.ra, self.rb) * max(self.sq.max(), 1.0)
        return np.array([m, m, self.L / 2 + m])

    def bounds(self):
        m = max(self.ra, self.rb) * max(self.sq.max(), 1.0) + self.k + 0.05
        a = self.c
        b = self.c + self.R[:, 2] * self.L
        return np.minimum(a, b) - m, np.maximum(a, b) + m

    def transformed(self, M, pivot):
        pivot = np.asarray(pivot, float)
        self.c = (self.c - pivot) @ M.T + pivot
        self.R = M @ self.R
        return self


# ---------------------------------------------------------------- combine
def smin(a, b, k):
    if k <= 1e-6:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def smax(a, b, k):
    return -smin(-a, -b, k)


class Grid:
    def __init__(self, lo, hi, h):
        self.lo = np.asarray(lo, float)
        self.h = float(h)
        self.n = np.ceil((np.asarray(hi, float) - self.lo) / h).astype(int) + 1
        self.v = np.full(tuple(self.n), 1e3, dtype=np.float32)

    def idx_range(self, lo, hi):
        i0 = np.clip(np.floor((lo - self.lo) / self.h).astype(int), 0, self.n - 1)
        i1 = np.clip(np.ceil((hi - self.lo) / self.h).astype(int) + 1, 0, self.n)
        return i0, i1

    def points(self, i0, i1):
        ax = [self.lo[d] + self.h * np.arange(i0[d], i1[d]) for d in range(3)]
        X, Y, Z = np.meshgrid(*ax, indexing='ij')
        return np.stack([X, Y, Z], -1)

    def apply(self, prim):
        lo, hi = prim.bounds()
        i0, i1 = self.idx_range(lo, hi)
        if np.any(i1 <= i0):
            return
        P = self.points(i0, i1)
        d = prim.sdf(P).astype(np.float32)
        sl = tuple(slice(a, b) for a, b in zip(i0, i1))
        cur = self.v[sl]
        if prim.op == 'union':
            self.v[sl] = smin(cur, d, prim.k)
        elif prim.op == 'sub':
            self.v[sl] = smax(cur, -d, prim.k)
        elif prim.op == 'inter':
            self.v[sl] = smax(cur, d, prim.k)

    def build(self, prims):
        for p in prims:
            self.apply(p)
        return self


def eval_prims(prims, P):
    """Evaluate the composed field at arbitrary points (for projection/weights)."""
    v = np.full(len(P), 1e3)
    for p in prims:
        d = p.sdf(P)
        if p.op == 'union':
            v = smin(v, d, p.k)
        elif p.op == 'sub':
            v = smax(v, -d, p.k)
        else:
            v = smax(v, d, p.k)
    return v


# ------------------------------------------------------------- surface nets
_CORNERS = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0],
                     [0, 0, 1], [1, 0, 1], [0, 1, 1], [1, 1, 1]])
_EDGES = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]


def surface_nets(grid):
    """Naive surface nets. Returns (verts Nx3 world, quads Mx4) for the zero set.

    Quads are oriented so normals point out of the solid (toward positive SDF).
    """
    v = grid.v
    inside = v < 0.0
    nx, ny, nz = v.shape
    # active cells: corners disagree
    c = [inside[i:nx - 1 + i, j:ny - 1 + j, k:nz - 1 + k] for i, j, k in _CORNERS]
    anyin = np.zeros_like(c[0])
    allin = np.ones_like(c[0])
    for a in c:
        anyin |= a
        allin &= a
    active = anyin & ~allin
    ci = np.argwhere(active)                     # (M,3) cell indices
    cell_id = np.full(active.shape, -1, dtype=np.int64)
    cell_id[tuple(ci.T)] = np.arange(len(ci))
    # vertex = mean of edge crossings
    acc = np.zeros((len(ci), 3))
    cnt = np.zeros(len(ci))
    vals = [v[ci[:, 0] + i, ci[:, 1] + j, ci[:, 2] + k] for i, j, k in _CORNERS]
    for e0, e1 in _EDGES:
        a, b = vals[e0], vals[e1]
        cross = (a < 0) != (b < 0)
        t = np.where(cross, a / np.where(cross, a - b, 1.0), 0.0)
        p0 = _CORNERS[e0]
        p1 = _CORNERS[e1]
        pt = p0[None] + t[:, None] * (p1 - p0)[None]
        acc += np.where(cross[:, None], pt, 0.0)
        cnt += cross
    local = acc / np.maximum(cnt, 1)[:, None]
    verts = grid.lo + (ci + local) * grid.h
    quads = []
    # x-edges: between (i,j,k) and (i+1,j,k); cells (i,j-1,k-1),(i,j,k-1),(i,j,k),(i,j-1,k)
    for axis in range(3):
        a = inside[:-1, :, :] if axis == 0 else inside[:, :-1, :] if axis == 1 else inside[:, :, :-1]
        b = inside[1:, :, :] if axis == 0 else inside[:, 1:, :] if axis == 1 else inside[:, :, 1:]
        flip = a & ~b                      # inside -> outside along +axis
        edge = a != b
        e = np.argwhere(edge)
        if axis == 0:
            e = e[(e[:, 1] > 0) & (e[:, 2] > 0) & (e[:, 1] < ny - 1) & (e[:, 2] < nz - 1)]
            i, j, k = e.T
            cells = [(i, j - 1, k - 1), (i, j, k - 1), (i, j, k), (i, j - 1, k)]
        elif axis == 1:
            e = e[(e[:, 0] > 0) & (e[:, 2] > 0) & (e[:, 0] < nx - 1) & (e[:, 2] < nz - 1)]
            i, j, k = e.T
            cells = [(i - 1, j, k - 1), (i - 1, j, k), (i, j, k), (i, j, k - 1)]
        else:
            e = e[(e[:, 0] > 0) & (e[:, 1] > 0) & (e[:, 0] < nx - 1) & (e[:, 1] < ny - 1)]
            i, j, k = e.T
            cells = [(i - 1, j - 1, k), (i, j - 1, k), (i, j, k), (i - 1, j, k)]
        q = np.stack([cell_id[cc] for cc in cells], 1)
        f = flip[tuple(e.T)]
        q = np.where(f[:, None], q, q[:, ::-1])
        quads.append(q)
    quads = np.concatenate(quads, 0)
    quads = quads[(quads >= 0).all(1)]
    return verts, quads
