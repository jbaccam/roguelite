"""Geometry toolkit for the Dragon generator (pure numpy; runs inside Blender's
bundled python and in system python).

* Signed-distance primitives with a per-primitive blend radius and bone tag.
* A sparse, bounded SDF grid evaluator (each primitive only touches its own
  padded box) and a vectorised surface-nets mesher with SDF re-projection.
* Mesh helpers: lofted tubes, convex hulls (quickhull), closed thick sheets
  (for wing membranes: real volume with closed, rounded rims), transforms.
"""
import math

import numpy as np


# ----------------------------------------------------------------- rotations
def rot_axis(axis, deg):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def frame_from(y_axis, z_hint):
    """Orthonormal frame (columns x, y, z) with local Y along y_axis, Z near z_hint."""
    y = np.asarray(y_axis, float)
    y = y / np.linalg.norm(y)
    z = np.asarray(z_hint, float)
    z = z - y * (z @ y)
    if np.linalg.norm(z) < 1e-6:
        z = np.array([0.0, 0.0, 1.0]) - y * y[2]
        if np.linalg.norm(z) < 1e-6:
            z = np.array([1.0, 0.0, 0.0]) - y * y[0]
    z = z / np.linalg.norm(z)
    x = np.cross(y, z)
    return np.stack([x, y, z], 1)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ----------------------------------------------------------------- primitives
class Prim:
    """Signed-distance primitive. `k` = smooth-union blend radius with what is
    already in the field, `bone` = deform bone that owns it (for skinning)."""

    def __init__(self, center, R=None, k=0.3, bone='Chest', op='union', tag=''):
        self.c = np.asarray(center, float)
        self.R = np.eye(3) if R is None else np.asarray(R, float)
        self.k = float(k)
        self.bone = bone
        self.op = op
        self.tag = tag

    def sdf(self, P):
        return self.local((P - self.c) @ self.R)

    def bounds(self):
        e = self.extent()
        corners = np.array([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]) * e
        w = corners @ self.R.T + self.c
        pad = self.k + 0.15
        return w.min(0) - pad, w.max(0) + pad


class Ellipsoid(Prim):
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
    def __init__(self, center, half, R=None, round_=0.2, **kw):
        super().__init__(center, R, **kw)
        self.h = np.asarray(half, float)
        self.rr = float(round_)

    def local(self, q):
        d = np.abs(q) - (self.h - self.rr)
        out = np.linalg.norm(np.maximum(d, 0.0), axis=-1)
        return out + np.minimum(np.max(d, axis=-1), 0.0) - self.rr

    def extent(self):
        return self.h


class RoundCone(Prim):
    """Capsule with different end radii between world points a and b."""

    def __init__(self, a, b, ra, rb, squash=(1.0, 1.0), z_hint=(0, 0, 1), **kw):
        a = np.asarray(a, float)
        b = np.asarray(b, float)
        R = frame_from(b - a, z_hint)
        super().__init__(a, R, **kw)
        self.L = float(np.linalg.norm(b - a))
        self.ra, self.rb = float(ra), float(rb)
        self.sq = np.asarray(squash, float)     # local x / z scale of the cross-section

    def local(self, q):
        # q: local coords with Y along the axis from a (y=0) to b (y=L)
        q = np.stack([q[..., 0] / self.sq[0], q[..., 1], q[..., 2] / self.sq[1]], -1)
        r1, r2, h = self.ra, self.rb, self.L
        b = (r1 - r2) / h
        a = math.sqrt(max(1.0 - b * b, 1e-9))
        qx = np.sqrt(q[..., 0] ** 2 + q[..., 2] ** 2)
        qy = q[..., 1]
        k = -b * qx + a * qy        # 2D: (qx, qy) projected on the side direction
        d1 = np.sqrt(qx ** 2 + qy ** 2) - r1
        d2 = np.sqrt(qx ** 2 + (qy - h) ** 2) - r2
        d3 = qx * a + qy * b - r1
        out = np.where(k < 0, d1, np.where(k > a * h, d2, d3))
        return out * min(self.sq)

    def extent(self):
        r = max(self.ra, self.rb)
        return np.array([r * self.sq[0], self.L / 2 + r, r * self.sq[1]])

    def bounds(self):
        r = max(self.ra, self.rb) * max(self.sq)
        a = self.c
        b = self.c + self.R[:, 1] * self.L
        pad = self.k + r + 0.15
        return np.minimum(a, b) - pad, np.maximum(a, b) + pad


def fib_sphere(n, seed=0):
    """n roughly even points on the unit sphere (Fibonacci lattice, jittered)."""
    rng = np.random.default_rng(seed)
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    th = math.pi * (1 + 5 ** 0.5) * i + rng.uniform(0, 2 * math.pi)
    P = np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], 1)
    P += rng.normal(0, 0.18 / math.sqrt(n), P.shape)
    return P / np.linalg.norm(P, axis=1, keepdims=True)


class FacetBall(Prim):
    """Faceted low-poly mass: the intersection of the tangent half-spaces of an
    ellipsoid at ~even surface points (the dual of a geodesic sphere), so every
    facet is truly planar, 5-7 sided and slightly irregular - the reference's
    chunky scale-plate masses. facet = target facet size in studs."""

    def __init__(self, center, radii, R=None, facet=0.8, jitter=0.05, seed=0, **kw):
        super().__init__(center, R, **kw)
        self.r = np.asarray(radii, float)
        a, b, c = self.r
        area = 4 * math.pi * ((a * b) ** 1.6 + (a * c) ** 1.6 + (b * c) ** 1.6) ** (1 / 1.6) / 3 ** (1 / 1.6)
        n = int(np.clip(area / (facet * facet * 0.9), 14, 400))
        q = fib_sphere(n, seed)
        rng = np.random.default_rng(seed + 1)
        p = q * self.r
        nrm = q / self.r
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
        nrm += rng.normal(0, 0.05, nrm.shape)
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
        self.N = nrm
        self.d = np.einsum('ij,ij->i', nrm, p) * (1 + rng.uniform(-jitter, jitter * 0.5, n))
        self.nf = n

    def local(self, q):
        sh = q.shape[:-1]
        Q = q.reshape(-1, 3)
        out = np.full(len(Q), -1e9, np.float32)
        for i in range(0, self.nf, 32):
            v = Q @ self.N[i:i + 32].T - self.d[i:i + 32]
            out = np.maximum(out, v.max(1))
        return out.reshape(sh)

    def extent(self):
        return self.r * 1.08


class FacetCone(Prim):
    """Faceted tapered capsule between a and b (planes tangent to a round cone)."""

    def __init__(self, a, b, ra, rb, squash=(1.0, 1.0), z_hint=(0, 0, 1), facet=0.8, jitter=0.05, seed=0, **kw):
        a = np.asarray(a, float)
        b = np.asarray(b, float)
        R = frame_from(b - a, z_hint)
        super().__init__(a, R, **kw)
        self.L = float(np.linalg.norm(b - a))
        self.ra, self.rb = float(ra), float(rb)
        self.sq = np.asarray(squash, float)
        rng = np.random.default_rng(seed)
        rm = 0.5 * (ra + rb)
        ring_n = max(5, int(round(2 * math.pi * rm / facet)))
        rows = max(2, int(round(self.L / facet)) + 1)
        N, D = [], []
        for ri in range(rows):
            t = ri / (rows - 1)
            y = t * self.L
            r = ra + (rb - ra) * t
            off = (ri % 2) * math.pi / ring_n + rng.uniform(0, 0.4)
            for k in range(ring_n):
                ang = off + 2 * math.pi * k / ring_n
                n = np.array([math.cos(ang) / self.sq[0], (ra - rb) / self.L, math.sin(ang) / self.sq[1]])
                n /= np.linalg.norm(n)
                n = n + rng.normal(0, 0.04, 3)
                n /= np.linalg.norm(n)
                p = np.array([math.cos(ang) * r * self.sq[0], y, math.sin(ang) * r * self.sq[1]])
                N.append(n)
                D.append(n @ p * (1 + rng.uniform(-jitter, jitter * 0.5)))
        # end caps: a few planes around each pole
        for (yc, r, sgn) in ((0.0, ra, -1), (self.L, rb, 1)):
            for k in range(6):
                ang = 2 * math.pi * k / 6 + rng.uniform(0, 1)
                n = np.array([math.cos(ang) * 0.55, sgn * 0.83, math.sin(ang) * 0.55])
                n /= np.linalg.norm(n)
                c = np.array([0, yc, 0])
                p = c + n * r * np.array([self.sq[0], 1, self.sq[1]])
                N.append(n)
                D.append(n @ p)
            N.append(np.array([0, sgn, 0.0]))
            D.append(sgn * yc + r * 0.98)
        self.N = np.array(N)
        self.d = np.array(D)
        self.nf = len(D)

    def local(self, q):
        sh = q.shape[:-1]
        Q = q.reshape(-1, 3)
        out = np.full(len(Q), -1e9, np.float32)
        for i in range(0, self.nf, 32):
            v = Q @ self.N[i:i + 32].T - self.d[i:i + 32]
            out = np.maximum(out, v.max(1))
        return out.reshape(sh)

    def extent(self):
        r = max(self.ra, self.rb)
        return np.array([r * self.sq[0], self.L / 2 + r, r * self.sq[1]])

    def bounds(self):
        r = max(self.ra, self.rb) * max(self.sq) * 1.1
        a = self.c
        b = self.c + self.R[:, 1] * self.L
        pad = self.k + r + 0.15
        return np.minimum(a, b) - pad, np.maximum(a, b) + pad


def smin(a, b, k):
    if k <= 1e-6:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def smax(a, b, k):
    return -smin(-a, -b, k)


# --------------------------------------------------------------------- grid
class Grid:
    def __init__(self, lo, hi, h):
        self.h = float(h)
        self.lo = np.asarray(lo, float)
        self.n = np.ceil((np.asarray(hi, float) - self.lo) / h).astype(int) + 1
        self.v = np.full(tuple(self.n), 1e3, np.float32)

    def build(self, prims):
        for p in prims:
            a, b = p.bounds()
            i0 = np.clip(np.floor((a - self.lo) / self.h).astype(int), 0, self.n - 1)
            i1 = np.clip(np.ceil((b - self.lo) / self.h).astype(int) + 1, 0, self.n)
            if np.any(i1 - i0 <= 0):
                continue
            xs = self.lo[0] + self.h * np.arange(i0[0], i1[0])
            ys = self.lo[1] + self.h * np.arange(i0[1], i1[1])
            zs = self.lo[2] + self.h * np.arange(i0[2], i1[2])
            X, Y, Z = np.meshgrid(xs, ys, zs, indexing='ij')
            Pt = np.stack([X, Y, Z], -1)
            d = p.sdf(Pt).astype(np.float32)
            sl = (slice(i0[0], i1[0]), slice(i0[1], i1[1]), slice(i0[2], i1[2]))
            cur = self.v[sl]
            if p.op == 'union':
                self.v[sl] = smin(cur, d, p.k)
            elif p.op == 'sub':
                self.v[sl] = smax(cur, -d, p.k)
        return self

    def sample(self, P):
        x = (np.asarray(P, float) - self.lo) / self.h
        i = np.clip(np.floor(x).astype(int), 0, self.n - 2)
        f = np.clip(x - i, 0.0, 1.0)
        out = np.zeros(len(P))
        for dx in (0, 1):
            wx = f[:, 0] if dx else 1 - f[:, 0]
            for dy in (0, 1):
                wy = f[:, 1] if dy else 1 - f[:, 1]
                for dz in (0, 1):
                    wz = f[:, 2] if dz else 1 - f[:, 2]
                    out += wx * wy * wz * self.v[i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz]
        return out

    def grad(self, P):
        e = self.h * 0.5
        g = np.stack([(self.sample(P + np.eye(3)[k] * e) - self.sample(P - np.eye(3)[k] * e)) / (2 * e)
                      for k in range(3)], 1)
        return g


def surface_nets(g):
    """Vectorised naive surface nets. Returns (V, Q) with outward quads."""
    v = g.v
    s = v < 0
    nx, ny, nz = v.shape
    corners = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0), (0, 0, 1), (1, 0, 1), (0, 1, 1), (1, 1, 1)]
    cs = [s[a:nx - 1 + a, b:ny - 1 + b, c:nz - 1 + c] for a, b, c in corners]
    anyin = np.zeros_like(cs[0])
    allin = np.ones_like(cs[0])
    for c in cs:
        anyin |= c
        allin &= c
    active = anyin & ~allin
    cell_idx = -np.ones(active.shape, np.int64)
    ids = np.argwhere(active)
    cell_idx[active] = np.arange(len(ids))
    # vertex = mean of edge crossings
    edges = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]
    acc = np.zeros((len(ids), 3))
    cnt = np.zeros(len(ids))
    vals = [v[a:nx - 1 + a, b:ny - 1 + b, c:nz - 1 + c][active] for a, b, c in corners]
    for e0, e1 in edges:
        f0, f1 = vals[e0], vals[e1]
        m = (f0 < 0) != (f1 < 0)
        t = np.where(m, f0 / np.where(m, f0 - f1, 1.0), 0.0)
        p0 = np.array(corners[e0], float)
        p1 = np.array(corners[e1], float)
        acc += m[:, None] * (p0[None, :] + t[:, None] * (p1 - p0)[None, :])
        cnt += m
    V = g.lo + g.h * (ids + acc / np.maximum(cnt, 1)[:, None])
    quads = []
    # x-edges: grid points (i,j,k)-(i+1,j,k); cells sharing: (i,j-1,k-1),(i,j,k-1),(i,j,k),(i,j-1,k)
    for axis in range(3):
        a0 = [slice(None)] * 3
        a1 = [slice(None)] * 3
        a0[axis] = slice(0, -1)
        a1[axis] = slice(1, None)
        e = s[tuple(a0)] != s[tuple(a1)]
        inside_first = s[tuple(a0)]
        pts = np.argwhere(e)
        flip = inside_first[e]
        o1, o2 = [ax for ax in range(3) if ax != axis]
        ok = (pts[:, o1] >= 1) & (pts[:, o2] >= 1) & (pts[:, o1] < [nx, ny, nz][o1] - 1) & (pts[:, o2] < [nx, ny, nz][o2] - 1)
        pts = pts[ok]
        flip = flip[ok]
        def cell(d1, d2):
            c = pts.copy()
            c[:, o1] -= d1
            c[:, o2] -= d2
            return cell_idx[c[:, 0], c[:, 1], c[:, 2]]
        q = np.stack([cell(1, 1), cell(0, 1), cell(0, 0), cell(1, 0)], 1)
        # orientation: normal along +axis when the first point is inside
        par = (axis == 1)
        rev = flip if not par else ~flip
        q[rev] = q[rev][:, ::-1]
        quads.append(q)
    Q = np.concatenate(quads)
    Q = Q[(Q >= 0).all(1)][:, ::-1]      # outward winding (checked: positive signed volume)
    return V, Q


def quad_neighbors(Q, n):
    r = np.concatenate([Q[:, 0], Q[:, 1], Q[:, 2], Q[:, 3], Q[:, 1], Q[:, 2], Q[:, 3], Q[:, 0]])
    c = np.concatenate([Q[:, 1], Q[:, 2], Q[:, 3], Q[:, 0], Q[:, 0], Q[:, 1], Q[:, 2], Q[:, 3]])
    key = np.unique(r.astype(np.int64) * n + c)
    return key // n, key % n


def relax_to_sdf(g, V, Q, iters=4, lam=0.5):
    n = len(V)
    rows, cols = quad_neighbors(Q, n)
    deg = np.bincount(rows, minlength=n)
    for _ in range(iters):
        acc = np.zeros_like(V)
        np.add.at(acc, rows, V[cols])
        V = V + lam * (acc / np.maximum(deg, 1)[:, None] - V)
        d = g.sample(V)
        gr = g.grad(V)
        gn = np.maximum(np.linalg.norm(gr, axis=1, keepdims=True), 1e-6)
        V = V - gr / gn * (d / gn[:, 0])[:, None]
    return V


def sdf_mesh(prims, h, pad=0.35, relax=4):
    lo = np.full(3, 1e9)
    hi = np.full(3, -1e9)
    for p in prims:
        if p.op != 'union':
            continue
        a, b = p.bounds()
        lo = np.minimum(lo, a)
        hi = np.maximum(hi, b)
    g = Grid(lo - pad, hi + pad, h).build(prims)
    V, Q = surface_nets(g)
    if relax:
        V = relax_to_sdf(g, V, Q, relax)
    return V, Q, g


# ----------------------------------------------------------------- mesh bits
def quads_to_tris(Q):
    return np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])


def ring(center, frame, rx, rz, n, phase=0.0, jitter=None):
    """Ring of n points in the plane of frame's x/z columns (frame = columns x, y, z)."""
    t = phase + np.arange(n) * 2 * math.pi / n
    x = np.cos(t) * rx
    z = np.sin(t) * rz
    if jitter is not None:
        x = x * jitter
        z = z * jitter
    return center + np.outer(x, frame[:, 0]) + np.outer(z, frame[:, 2])


def loft(rings, cap0=True, cap1=True):
    """Tube through rings (list of (n,3) arrays with equal n). Returns V, F (lists of polys)."""
    n = len(rings[0])
    V = np.concatenate(rings)
    F = []
    for i in range(len(rings) - 1):
        a = i * n
        b = (i + 1) * n
        for j in range(n):
            j1 = (j + 1) % n
            F.append([a + j, a + j1, b + j1, b + j])
    if cap0:
        F.append(list(range(n))[::-1])
    if cap1:
        m = (len(rings) - 1) * n
        F.append([m + j for j in range(n)])
    return V, F


def convex_hull(P):
    """Quickhull (3D). Returns triangle indices into P, outward-facing."""
    P = np.asarray(P, float)
    n = len(P)
    # initial tetrahedron
    i0 = int(np.argmin(P[:, 0]))
    i1 = int(np.argmax(P[:, 0]))
    if i0 == i1:
        i1 = (i0 + 1) % n
    d = np.linalg.norm(np.cross(P - P[i0], P[i1] - P[i0]), axis=1)
    i2 = int(np.argmax(d))
    nrm = np.cross(P[i1] - P[i0], P[i2] - P[i0])
    i3 = int(np.argmax(np.abs((P - P[i0]) @ nrm)))
    faces = [[i0, i1, i2], [i0, i2, i3], [i0, i3, i1], [i1, i3, i2]]
    cen = P[[i0, i1, i2, i3]].mean(0)

    def orient(f):
        a, b, c = P[f[0]], P[f[1]], P[f[2]]
        nn = np.cross(b - a, c - a)
        if (a - cen) @ nn < 0:
            return [f[0], f[2], f[1]]
        return f
    faces = [orient(f) for f in faces]
    eps = 1e-9 * max(1.0, float(np.abs(P).max()))
    for it in range(4 * n):
        best = None
        for fi, f in enumerate(faces):
            a, b, c = P[f[0]], P[f[1]], P[f[2]]
            nn = np.cross(b - a, c - a)
            ln = np.linalg.norm(nn)
            if ln < 1e-15:
                continue
            dist = (P - a) @ (nn / ln)
            j = int(np.argmax(dist))
            if dist[j] > eps and (best is None or dist[j] > best[0]):
                best = (dist[j], j)
        if best is None:
            break
        j = best[1]
        pj = P[j]
        visible = []
        for fi, f in enumerate(faces):
            a, b, c = P[f[0]], P[f[1]], P[f[2]]
            nn = np.cross(b - a, c - a)
            if (pj - a) @ nn > eps:
                visible.append(fi)
        edges = {}
        for fi in visible:
            f = faces[fi]
            for e in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
                if (e[1], e[0]) in edges:
                    del edges[(e[1], e[0])]
                else:
                    edges[e] = True
        faces = [f for fi, f in enumerate(faces) if fi not in set(visible)]
        for (a, b) in edges:
            faces.append([a, b, j])
    used = sorted({i for f in faces for i in f})
    remap = {o: i for i, o in enumerate(used)}
    return P[used], np.array([[remap[i] for i in f] for f in faces])


def thick_sheet(Vs, grid_shape, thick, rim_round=True):
    """Closed thick shell from a (rows x cols) sheet grid of points.

    Vs: (rows*cols, 3) mid-surface points, row-major. Returns V, F (quads),
    plus a per-vertex 'side' array (+1 front, -1 back). The rim is closed with
    a two-step rounded edge so the sheet reads as a real volume from any side.
    """
    R, C = grid_shape
    M = Vs.reshape(R, C, 3)
    # normals from the grid
    du = np.gradient(M, axis=1)
    dv = np.gradient(M, axis=0)
    N = np.cross(du, dv)
    N /= np.maximum(np.linalg.norm(N, axis=2, keepdims=True), 1e-9)
    t = np.full((R, C), thick * 0.5)
    if rim_round:
        # taper the thickness at the boundary so the rim is rounded, not a slab
        edge = np.zeros((R, C), bool)
        edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
        t[edge] *= 0.55
    top = (M + N * t[..., None]).reshape(-1, 3)
    bot = (M - N * t[..., None]).reshape(-1, 3)
    V = np.concatenate([top, bot])
    F = []
    off = R * C
    for i in range(R - 1):
        for j in range(C - 1):
            a, b, c, d = i * C + j, i * C + j + 1, (i + 1) * C + j + 1, (i + 1) * C + j
            F.append([a, b, c, d])
            F.append([off + d, off + c, off + b, off + a])
    # rim
    loop = [(0, j) for j in range(C)] + [(i, C - 1) for i in range(1, R)] + \
           [(R - 1, j) for j in range(C - 2, -1, -1)] + [(i, 0) for i in range(R - 2, 0, -1)]
    L = [i * C + j for i, j in loop]
    for k in range(len(L)):
        a = L[k]
        b = L[(k + 1) % len(L)]
        F.append([b, a, off + a, off + b])
    side = np.concatenate([np.ones(R * C), -np.ones(R * C)])
    return V, F, side


def polys_to_tris(F):
    T = []
    for f in F:
        for k in range(1, len(f) - 1):
            T.append([f[0], f[k], f[k + 1]])
    return np.array(T, np.int64)
