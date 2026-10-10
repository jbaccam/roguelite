"""Signed-distance sculpting for the Tomb Warden (pure numpy, no bpy).

Adapted (copied, not imported) from frost-cyclops-boss/fc_sdf.py: the same
primitive set, ordered smooth union and naive surface nets, plus an extruded
polygon prism (mask fracture), a field-level API so cloth shells can be
offset from the body field, and the surface clean-up pass.
"""
import math

import numpy as np


# ----------------------------------------------------------------- frames
def axis_angle(axis, deg):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def rot_xyz(rx=0.0, ry=0.0, rz=0.0):
    rx, ry, rz = map(math.radians, (rx, ry, rz))
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


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


# ------------------------------------------------------------- primitives
class Prim:
    kind = 'prim'

    def __init__(self, center, R=None, k=0.2, bone='UpperTorso', op='union', tag=''):
        self.c = np.asarray(center, float)
        self.R = np.eye(3) if R is None else np.asarray(R, float)
        self.k = float(k)
        self.bone = bone
        self.op = op
        self.tag = tag

    def sdf(self, P):
        return self.local((P - self.c) @ self.R)

    def bounds(self):
        r = self.extent()
        corners = np.array([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]) * r
        w = corners @ self.R.T + self.c
        pad = self.k + 0.06
        return w.min(0) - pad, w.max(0) + pad


class Ellipsoid(Prim):
    kind = 'ellipsoid'

    def __init__(self, center, radii, R=None, **kw):
        super().__init__(center, R, **kw)
        self.r = np.asarray(radii, float)

    def local(self, q):
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
    """Rounded box whose X/Y half sizes scale linearly along local Z."""
    kind = 'taperbox'

    def __init__(self, center, half, R=None, round_=0.1, scale_bottom=0.8, **kw):
        super().__init__(center, R, **kw)
        self.h = np.asarray(half, float)
        self.rr = float(round_)
        self.sb = float(scale_bottom)

    def local(self, q):
        t = np.clip((q[..., 2] / self.h[2] + 1.0) * 0.5, 0.0, 1.0)
        s = self.sb + (1.0 - self.sb) * t
        d = np.stack([np.abs(q[..., 0]) - (self.h[0] * s - self.rr), np.abs(q[..., 1]) - (self.h[1] * s - self.rr),
                      np.abs(q[..., 2]) - (self.h[2] - self.rr)], -1)
        out = np.linalg.norm(np.maximum(d, 0.0), axis=-1)
        inside = np.minimum(np.max(d, axis=-1), 0.0)
        return (out + inside - self.rr) * 0.9

    def extent(self):
        return self.h


class RoundCone(Prim):
    """Capsule with different end radii from a to b (world); optional elliptic
    cross-section via `squash` (scales local x, y)."""
    kind = 'roundcone'

    def __init__(self, a, b, ra, rb, k=0.2, bone='UpperTorso', op='union', tag='', squash=None, x_hint=(1, 0, 0)):
        a = np.asarray(a, float)
        b = np.asarray(b, float)
        L = float(np.linalg.norm(b - a))
        super().__init__(a, frame_from(b - a, x_hint), k=k, bone=bone, op=op, tag=tag)
        self.a, self.b = a, b
        self.L = L
        self.ra = float(ra)
        self.rb = float(rb)
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
        k = -b * qx + a * qy
        d1 = np.sqrt(qx * qx + qy * qy) - r1
        d2 = np.sqrt(qx * qx + (qy - h) ** 2) - r2
        d3 = qx * a + qy * b - r1
        out = np.where(k < 0.0, d1, np.where(k > a * h, d2, d3))
        return out * min(self.sq.min(), 1.0)

    def bounds(self):
        m = max(self.ra, self.rb) * max(self.sq.max(), 1.0) + self.k + 0.06
        return np.minimum(self.a, self.b) - m, np.maximum(self.a, self.b) + m

    def axis_param(self, P):
        """(t in studs along a->b, angle around the axis) for points P."""
        q = (P - self.c) @ self.R
        return q[..., 2], np.arctan2(q[..., 1], q[..., 0])


class PolyPrism(Prim):
    """2D polygon (local x, z) extruded along local y over [-hy, hy]."""
    kind = 'polyprism'

    def __init__(self, center, poly, hy, R=None, round_=0.02, **kw):
        super().__init__(center, R, **kw)
        self.poly = np.asarray(poly, float)
        self.hy = float(hy)
        self.rr = float(round_)

    def _poly_sdf(self, x, z):
        v = self.poly
        n = len(v)
        d = np.full(x.shape, 1e9)
        s = np.ones(x.shape)
        for i in range(n):
            a = v[i]
            b = v[(i + 1) % n]
            e = b - a
            wx, wz = x - a[0], z - a[1]
            t = np.clip((wx * e[0] + wz * e[1]) / (e @ e), 0.0, 1.0)
            dx, dz = wx - e[0] * t, wz - e[1] * t
            d = np.minimum(d, dx * dx + dz * dz)
            c1 = z >= a[1]
            c2 = z < b[1]
            c3 = e[0] * wz > e[1] * wx
            flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
            s = np.where(flip, -s, s)
        return s * np.sqrt(d)

    def local(self, q):
        d2 = self._poly_sdf(q[..., 0], q[..., 2])
        dy = np.abs(q[..., 1]) - self.hy
        w = np.stack([d2, dy], -1)
        return np.minimum(np.maximum(w[..., 0], w[..., 1]), 0.0) + np.linalg.norm(np.maximum(w, 0.0), axis=-1) - self.rr

    def extent(self):
        m = np.abs(self.poly).max(0)
        return np.array([m[0], self.hy, m[1]])


# ----------------------------------------------------------------- combine
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

    def points(self, i0=None, i1=None):
        i0 = np.zeros(3, int) if i0 is None else i0
        i1 = self.n if i1 is None else i1
        ax = [self.lo[d] + self.h * np.arange(i0[d], i1[d]) for d in range(3)]
        X, Y, Z = np.meshgrid(*ax, indexing='ij')
        return np.stack([X, Y, Z], -1)

    def apply(self, prim, field=None):
        field = self.v if field is None else field
        lo, hi = prim.bounds()
        i0, i1 = self.idx_range(lo, hi)
        if np.any(i1 <= i0):
            return field
        P = self.points(i0, i1)
        d = prim.sdf(P).astype(np.float32)
        sl = tuple(slice(a, b) for a, b in zip(i0, i1))
        cur = field[sl]
        if prim.op == 'union':
            field[sl] = smin(cur, d, prim.k)
        elif prim.op == 'sub':
            field[sl] = smax(cur, -d, prim.k)
        elif prim.op == 'inter':
            field[sl] = smax(cur, d, prim.k)
        return field

    def field_of(self, prims):
        f = np.full(tuple(self.n), 1e3, dtype=np.float32)
        for p in prims:
            self.apply(p, f)
        return f


def eval_prims(prims, P):
    v = np.full(P.shape[:-1], 1e3)
    for p in prims:
        d = p.sdf(P)
        if p.op == 'union':
            v = smin(v, d, p.k)
        elif p.op == 'sub':
            v = smax(v, -d, p.k)
        else:
            v = smax(v, d, p.k)
    return v


def bounds_of(prims, pad=0.3):
    lo = np.full(3, 1e9)
    hi = np.full(3, -1e9)
    for p in prims:
        if p.op != 'union':
            continue
        a, b = p.bounds()
        lo = np.minimum(lo, a)
        hi = np.maximum(hi, b)
    return lo - pad, hi + pad


# ------------------------------------------------------------ surface nets
_CORNERS = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0],
                     [0, 0, 1], [1, 0, 1], [0, 1, 1], [1, 1, 1]])
_EDGES = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]


def surface_nets(v, lo, h):
    """Naive surface nets on field v (negative inside). Returns verts, quads
    (quads wound so normals point outward)."""
    inside = v < 0.0
    nx, ny, nz = v.shape
    c = [inside[i:nx - 1 + i, j:ny - 1 + j, k:nz - 1 + k] for i, j, k in _CORNERS]
    anyin = np.zeros_like(c[0])
    allin = np.ones_like(c[0])
    for a in c:
        anyin |= a
        allin &= a
    active = anyin & ~allin
    ci = np.argwhere(active)
    cell_id = np.full(active.shape, -1, dtype=np.int64)
    cell_id[tuple(ci.T)] = np.arange(len(ci))
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
    verts = np.asarray(lo) + (ci + local) * h
    quads = []
    for axis in range(3):
        a = inside[:-1, :, :] if axis == 0 else inside[:, :-1, :] if axis == 1 else inside[:, :, :-1]
        b = inside[1:, :, :] if axis == 0 else inside[:, 1:, :] if axis == 1 else inside[:, :, 1:]
        flip = a & ~b
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


def trilinear(v, lo, h, P):
    n = np.array(v.shape)
    x = (P - lo) / h
    i = np.clip(np.floor(x).astype(int), 0, n - 2)
    f = np.clip(x - i, 0, 1)
    out = np.zeros(len(P))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * \
                    (f[:, 2] if dz else 1 - f[:, 2])
                out += w * v[i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz]
    return out


def field_grad(v, lo, h, P):
    e = h * 0.5
    return np.stack([(trilinear(v, lo, h, P + np.eye(3)[k] * e) - trilinear(v, lo, h, P - np.eye(3)[k] * e)) / (2 * e)
                     for k in range(3)], 1)


def quad_adjacency(Q, n):
    rows = np.concatenate([Q[:, 0], Q[:, 1], Q[:, 2], Q[:, 3], Q[:, 1], Q[:, 2], Q[:, 3], Q[:, 0]])
    cols = np.concatenate([Q[:, 1], Q[:, 2], Q[:, 3], Q[:, 0], Q[:, 0], Q[:, 1], Q[:, 2], Q[:, 3]])
    key = np.unique(rows.astype(np.int64) * n + cols)
    return key // n, key % n


def clean_surface(v, lo, h, V, Q, iters=3, lam=0.5):
    """Laplacian smoothing of surface-nets steps, re-projected onto the zero set."""
    n = len(V)
    rows, cols = quad_adjacency(Q, n)
    deg = np.bincount(rows, minlength=n)
    for _ in range(iters):
        acc = np.zeros_like(V)
        np.add.at(acc, rows, V[cols])
        V = V + lam * (acc / np.maximum(deg, 1)[:, None] - V)
        d = trilinear(v, lo, h, V)
        g = field_grad(v, lo, h, V)
        gn = np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-6)
        V = V - g / gn * (d / gn[:, 0])[:, None]
    return V


def mesh_field(v, lo, h, smooth=3):
    V, Q = surface_nets(v, lo, h)
    if smooth:
        V = clean_surface(v, lo, h, V, Q, smooth)
    return V, Q


def vertex_normals(V, Q):
    N = np.zeros_like(V)
    a, b, c, d = (V[Q[:, i]] for i in range(4))
    fn = np.cross(c - a, d - b)
    for i in range(4):
        np.add.at(N, Q[:, i], fn)
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
