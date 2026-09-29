"""Dragon geometry design (pure numpy). Every part is built in the REST pose.

A part is a dict:
    name, section, mat (paint recipe key), V (n,3), F (list of polys),
    weights: {bone: (n,) array} or bone: 'Name' (rigid),
    bevel: (width, segments, angle_deg) or None, smooth: False (flat facets).

Sections (one skinned mesh each, < 20k tris): Body, Head, Wings, Belly,
Obsidian, LavaGlow, EyeGlow.
"""
import math

import numpy as np

import dragon_mesh as M
import dragon_rig as RG
from dragon_rig import J, mirror

RNG = np.random.default_rng(20260929)
SIDES = ('L', 'R')


def side_fn(s):
    return (lambda p: np.asarray(p, float)) if s == 'L' else mirror


def jp(name, s='L'):
    return side_fn(s)(J[name])


# =========================================================================
# BODY: one continuous SDF skin (torso, neck, head base, legs, tail)
# =========================================================================
def body_prims():
    """Faceted scale-plate masses (planar facets, soft SDF-sampled edges),
    united with small blend radii so creases show between masses."""
    FB, FC, E = M.FacetBall, M.FacetCone, M.Ellipsoid
    P = []
    sd = iter(range(1000, 2000))
    # --- torso
    P.append(FB((0, -3.0, 6.7), (2.75, 2.5, 3.25), facet=0.95, seed=next(sd), bone='Chest', k=0.0, tag='chest'))
    P.append(FB((0, -0.8, 8.6), (2.8, 2.6, 2.3), facet=0.9, seed=next(sd), bone='Spine_3', k=0.5, tag='withers'))
    P.append(FB((0, -0.5, 5.1), (3.8, 3.1, 3.15), facet=0.95, seed=next(sd), bone='Spine_2', k=0.5, tag='belly_f'))
    P.append(FB((0, 2.4, 5.2), (3.5, 2.9, 3.0), facet=0.95, seed=next(sd), bone='Spine_1', k=0.5, tag='belly_r'))
    P.append(FB((0, 1.7, 8.0), (2.55, 2.7, 2.3), facet=0.9, seed=next(sd), bone='Spine_1', k=0.4, tag='back'))
    P.append(FB((0, 4.9, 6.2), (2.6, 2.4, 2.35), facet=0.9, seed=next(sd), bone='Hips', k=0.5, tag='hips'))
    for s in SIDES:   # heavy upper-back / shoulder-blade masses behind the shoulders (wing roots sit here)
        P.append(FB(side_fn(s)((2.15, 0.7, 8.15)), (1.75, 2.3, 1.65), facet=0.8, seed=next(sd), bone='Spine_2', k=0.35, tag='back'))
    # --- neck: thick, short, carrying the head forward of the withers
    P.append(FC((0, -2.6, 8.5), (0, -4.5, 8.9), 2.3, 1.75, facet=0.75, seed=next(sd), bone='Neck_1', k=0.45, tag='neck'))
    P.append(FC((0, -4.5, 8.9), (0, -5.6, 9.15), 1.75, 1.35, facet=0.68, seed=next(sd), bone='Neck_2', k=0.35, tag='neck'))
    P.append(FC((0, -5.55, 9.2), (0, -6.3, 9.4), 1.35, 1.1, facet=0.65, seed=next(sd), bone='Neck_3', k=0.3, tag='neck'))
    P.append(FC((0, -4.3, 7.65), (0, -5.9, 8.35), 1.45, 1.0, facet=0.65, seed=next(sd), bone='Neck_2', k=0.4, tag='neck'))
    P.append(FC((0, -5.6, 9.95), (0, -2.0, 10.2), 0.8, 1.15, facet=0.65, seed=next(sd), bone='Neck_1', k=0.4, tag='neck_top'))
    P.append(E(RG.head_xf((0, -5.75, 9.6)), (0.7, 0.8, 0.62), bone='Head', k=0.3, tag='head_core'))
    # --- legs: thick continuous pillars - a big rounded shoulder/thigh mass
    # flowing into a straight heavy column, then a wide splayed foot. The
    # columns are split at the joints (one bone each) and united with soft
    # blends, so the pillar reads continuous but bends cleanly.
    for s in SIDES:
        m = side_fn(s)
        P.append(FB(m((3.5, -4.25, 6.3)), (1.62, 1.85, 1.72), facet=0.82, seed=next(sd), bone=f'UpperArm_{s}', k=0.35, tag='shoulder'))
        P.append(FC(m(J['shoulder']), m(J['elbow']), 1.48, 1.38, facet=0.8, seed=next(sd), bone=f'UpperArm_{s}', k=0.35, tag='arm'))
        P.append(FC(m(J['elbow']), m((5.08, -3.75, 1.75)), 1.4, 1.32, facet=0.8, seed=next(sd), bone=f'Forearm_{s}', k=0.3, tag='forearm'))
        P.append(FB(m((5.12, -3.6, 0.9)), (1.72, 1.15, 0.76), facet=0.72, seed=next(sd), bone=f'Hand_{s}', k=0.3, tag='hand'))
        P.append(FB(m((5.12, -3.45, 0.5)), (1.55, 0.95, 0.5), facet=0.7, seed=next(sd), bone=f'Hand_{s}', k=0.2, tag='hand'))
        P.append(FB(m((3.85, 5.0, 5.0)), (1.95, 2.45, 2.15), facet=0.85, seed=next(sd), bone=f'Thigh_{s}', k=0.4, tag='thigh'))
        P.append(FC(m(J['knee']), m(J['hock']), 1.38, 1.18, facet=0.78, seed=next(sd), bone=f'Shin_{s}', k=0.35, tag='shin'))
        P.append(FC(m(J['hock']), m((5.45, 5.6, 1.25)), 1.12, 1.02, facet=0.72, seed=next(sd), bone=f'Ankle_{s}', k=0.3, tag='ankle'))
        P.append(FB(m((5.48, 5.6, 0.8)), (1.5, 1.05, 0.68), facet=0.7, seed=next(sd), bone=f'Foot_{s}', k=0.28, tag='foot'))
        P.append(FB(m((5.48, 5.75, 0.46)), (1.38, 0.85, 0.46), facet=0.7, seed=next(sd), bone=f'Foot_{s}', k=0.2, tag='foot'))
    # --- tail: faceted tapering segments
    tp = RG.tail_points()
    radii = np.linspace(2.05, 0.45, RG.TAIL_N + 1)
    for i in range(RG.TAIL_N):
        P.append(FC(tp[i], tp[i + 1], radii[i], radii[i + 1], squash=(0.92, 1.0), facet=0.75 - 0.03 * i, seed=next(sd),
                    bone=f'Tail_{i + 1}', k=0.6 if i == 0 else 0.15, tag='tail'))
    return P


def ownership_weights(prims, V, tau=0.32):
    """Soft arg-min ownership of the SDF primitives, summed per bone."""
    D = np.array([p.sdf(V) for p in prims if p.op == 'union'])
    bones = [p.bone for p in prims if p.op == 'union']
    dmin = D.min(0)
    E = np.exp(-(D - dmin) / tau)
    W = {}
    for i, b in enumerate(bones):
        W[b] = W.get(b, 0) + E[i]
    tot = sum(W.values())
    return {b: w / tot for b, w in W.items()}


def limit_weights(W, n, k=4, floor=0.02):
    names = list(W)
    A = np.stack([W[b] for b in names], 1)
    A[A < floor] = 0.0
    idx = np.argsort(-A, axis=1)[:, k:]
    np.put_along_axis(A, idx, 0.0, axis=1)
    s = A.sum(1, keepdims=True)
    A = A / np.maximum(s, 1e-12)
    return {b: A[:, i] for i, b in enumerate(names) if A[:, i].max() > 0}


def smooth_weights(W, F, n, iters=3, lam=0.5):
    rows, cols = [], []
    for f in F:
        for a, b in zip(f, list(f[1:]) + [f[0]]):
            rows += [a, b]
            cols += [b, a]
    rows = np.array(rows)
    cols = np.array(cols)
    deg = np.bincount(rows, minlength=n)
    out = {}
    for b, w in W.items():
        w = w.copy()
        for _ in range(iters):
            acc = np.zeros(n)
            np.add.at(acc, rows, w[cols])
            w = w + lam * (acc / np.maximum(deg, 1) - w)
        out[b] = w
    return out


# =========================================================================
# Surface helpers
# =========================================================================
def surface_point(grid, origin, direction, max_t=8.0, step=0.05):
    """March from `origin` (inside the body) along `direction` to the SDF zero."""
    d = np.asarray(direction, float)
    d = d / np.linalg.norm(d)
    o = np.asarray(origin, float)
    t = 0.0
    prev = grid.sample(o[None])[0]
    while t < max_t:
        t += step
        v = grid.sample((o + d * t)[None])[0]
        if prev < 0 <= v:
            tt = t - step * v / max(v - prev, 1e-9)
            return o + d * tt
        prev = v
    return o + d * t


def surface_normal(grid, p):
    g = grid.grad(np.asarray(p, float)[None])[0]
    return g / max(np.linalg.norm(g), 1e-9)


# =========================================================================
# Belly plates: chevron bands along the ventral midline
# =========================================================================
BELLY_LINE = [   # core points and outward (ventral) directions, throat -> tail tip
    ((0, -6.0, 8.65), (0, -0.35, -0.94)),
    ((0, -5.3, 8.25), (0, -0.7, -0.72)),
    ((0, -4.5, 7.85), (0, -0.95, -0.3)),
    ((0, -3.3, 6.6), (0, -0.97, -0.25)),
    ((0, -2.6, 5.4), (0, -0.8, -0.6)),
    ((0, -1.3, 4.7), (0, -0.45, -0.9)),
    ((0, 0.6, 4.6), (0, -0.1, -1.0)),
    ((0, 2.6, 4.8), (0, 0.15, -1.0)),
    ((0, 4.6, 5.6), (0, 0.35, -0.94)),
]
CHEST_PLATES = 10       # throat to groin
TAIL_PLATES = 16


def ventral_curve(grid, n=160):
    core = [np.array(c, float) for c, _ in BELLY_LINE]
    dirs = [np.array(d, float) / np.linalg.norm(d) for _, d in BELLY_LINE]
    # tail core, direction straight down
    tp = RG.tail_points()
    for i in range(1, len(tp) - 1):
        core.append(np.array(tp[i], float))
        dirs.append(np.array([0, 0.12, -1.0]) / np.linalg.norm([0, 0.12, -1.0]))
    core = np.array(core)
    dirs = np.array(dirs)
    seg = np.linalg.norm(np.diff(core, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    ss = np.linspace(0, s[-1], n)
    C = np.stack([np.interp(ss, s, core[:, k]) for k in range(3)], 1)
    D = np.stack([np.interp(ss, s, dirs[:, k]) for k in range(3)], 1)
    D /= np.linalg.norm(D, axis=1, keepdims=True)
    S = np.array([surface_point(grid, C[i], D[i]) for i in range(n)])
    return C, D, S


def _curve_frame(C, D, S, arc, s):
    s = min(max(s, 0.0), arc[-1])
    k = int(np.clip(np.searchsorted(arc, s), 1, len(arc) - 1))
    t = (s - arc[k - 1]) / max(arc[k] - arc[k - 1], 1e-9)
    c = C[k - 1] * (1 - t) + C[k] * t
    dn = D[k - 1] * (1 - t) + D[k] * t
    dn /= np.linalg.norm(dn)
    tan = S[k] - S[k - 1]
    tan /= np.linalg.norm(tan)
    lat = np.cross(tan, dn)
    lat /= np.linalg.norm(lat)
    return c, dn, lat


def plate_solid(outer_rows, inner_rows):
    """Closed solid from rows of outer and inner points (rows x cols each)."""
    R, Cn = len(outer_rows), len(outer_rows[0])
    O = np.array(outer_rows).reshape(-1, 3)
    I = np.array(inner_rows).reshape(-1, 3)
    V = np.concatenate([O, I])
    off = R * Cn
    F = []
    for i in range(R - 1):
        for j in range(Cn - 1):
            a, b, c, e = i * Cn + j, i * Cn + j + 1, (i + 1) * Cn + j + 1, (i + 1) * Cn + j
            F.append([a, e, c, b])
            F.append([off + a, off + b, off + c, off + e])
    loop = [(0, j) for j in range(Cn)] + [(i, Cn - 1) for i in range(1, R)] +            [(R - 1, j) for j in range(Cn - 2, -1, -1)] + [(i, 0) for i in range(R - 2, 0, -1)]
    L = [i * Cn + j for i, j in loop]
    for k in range(len(L)):
        a, b = L[k], L[(k + 1) % len(L)]
        F.append([a, b, off + b, off + a])
    return V, F


def belly_plates(grid, prims):
    """Thick chevron plates stacked like shingles: planar faces (few columns),
    a V crease on the midline, the lower lip standing proud over the next
    plate, wide over the chest and narrowing under the belly and tail."""
    C, D, S = ventral_curve(grid)
    seg = np.linalg.norm(np.diff(S, axis=0), axis=1)
    arc = np.concatenate([[0], np.cumsum(seg)])
    tp = RG.tail_points()
    tail_start = next(arc[i] for i in range(len(C)) if C[i, 1] > tp[1][1])
    chest_len = tail_start - 0.2
    cb = np.cumsum(np.array([0.0, 0.7, 0.8, 0.95, 1.15, 1.35, 1.5, 1.5, 1.4, 1.3, 1.2, 1.1]))
    cb = cb / cb[-1] * chest_len
    tail_end = arc[-1] - 0.9
    tl = np.linspace(1.05, 0.62, TAIL_PLATES)
    tb = tail_start + np.concatenate([[0], np.cumsum(tl / tl.sum() * (tail_end - tail_start))])
    bounds = [(cb[i], cb[i + 1]) for i in range(len(cb) - 1)] + [(tb[i], tb[i + 1]) for i in range(len(tb) - 1)]
    cols = np.array([-1.0, -0.7, -0.4, -0.12, 0.0, 0.12, 0.4, 0.7, 1.0])
    parts = []
    for pi, (s0, s1) in enumerate(bounds):
        mid = 0.5 * (s0 + s1)
        is_tail = s0 >= tail_start - 1e-6
        if is_tail:
            f = (mid - tail_start) / max(tail_end - tail_start, 1e-3)
            half = math.radians(70)
            lip = 0.2 - 0.08 * f
            chev = 0.16
        else:
            f = mid / chest_len
            half = math.radians(60 + 18 * math.sin(math.pi * min(1.0, f * 1.1)))
            lip = 0.42
            chev = 0.55 if f < 0.7 else 0.36
        overlap = 0.3
        outer, inner = [], []
        for row, (sv, lift) in enumerate(((0.0, 0.03), (0.55, None), (1.0, lip))):
            o_row, i_row = [], []
            for u in cols:
                s = s0 + (s1 - s0 + overlap) * sv - chev * abs(u) ** 1.15
                c, dn, lat = _curve_frame(C, D, S, arc, s)
                ang = u * half
                p = surface_point(grid, c, dn * math.cos(ang) + lat * math.sin(ang))
                nrm = surface_normal(grid, p)
                h = lift if lift is not None else 0.03 + (lip - 0.03) * 0.62
                # roof-like midline crease: the two halves rise toward the centre ridge
                ridge = 0.14 * (1 - abs(u)) ** 1.5
                edge_drop = 0.6 if abs(u) == 1.0 else 1.0
                o_row.append(p + nrm * (h + ridge) * edge_drop)
                i_row.append(p - nrm * 0.3)
            outer.append(o_row)
            inner.append(i_row)
        V, F = plate_solid(outer, inner)
        W = limit_weights(ownership_weights(prims, V), len(V))
        parts.append(dict(name=f'BellyPlate_{pi + 1:02d}', section='Belly', mat='belly', V=V, F=F, weights=W,
                          bevel=(0.04, 1, 20.0), smooth=False))
    return parts


# =========================================================================
# Dorsal spikes (obsidian) + lava glow at their bases
# =========================================================================
DORSAL = [   # (core point, bone, height, base radius, lean_deg) - behind the head to the hips
    ((0, -3.6, 10.4), 'Neck_1', 1.55, 0.92, 16),
    ((0, -2.2, 10.3), 'Chest', 1.85, 1.0, 15),
    ((0, -0.6, 9.6), 'Spine_3', 2.0, 0.98, 15),
    ((0, 1.05, 8.9), 'Spine_2', 1.85, 0.88, 15),
    ((0, 2.6, 8.4), 'Spine_1', 1.65, 0.82, 15),
    ((0, 4.15, 7.9), 'Hips', 1.5, 0.76, 15),
]


def dorsal_list():
    out = list(DORSAL)
    tp = RG.tail_points()
    n = RG.TAIL_N
    for i in range(n - 1):
        c = 0.5 * (tp[i] + tp[i + 1])
        t = i / (n - 2)
        out.append((tuple(c), f'Tail_{i + 1}', 1.5 - 0.7 * t, 0.74 - 0.34 * t, 15 + 5 * t))
    return out


def spike_mesh(base, up, back, height, radius, lean_deg, sides=6, seed=0):
    """Chunky obsidian block spike: slightly tapered hexagonal column, stretched
    fore-aft, with a slanted flat top that is highest at the front edge."""
    rng = np.random.default_rng(seed)
    up = up / np.linalg.norm(up)
    back = back - up * (back @ up)
    back /= np.linalg.norm(back)
    axis = up * math.cos(math.radians(lean_deg)) + back * math.sin(math.radians(lean_deg))
    axis /= np.linalg.norm(axis)
    b2 = back - axis * (back @ axis)
    b2 /= np.linalg.norm(b2)
    s2 = np.cross(axis, b2)
    angs = [2 * math.pi * (k + 0.5) / sides + rng.uniform(-0.1, 0.1) for k in range(sides)]
    rs = [1 + rng.uniform(-0.06, 0.06) for _ in range(sides)]
    rings = []
    for h, sc in ((-0.4, 1.02), (0.0, 1.0), (0.58, 0.9)):
        c = base + axis * height * h
        rings.append(np.array([c + (b2 * math.cos(a) * 1.45 + s2 * math.sin(a) * 0.9) * radius * sc * r
                               for a, r in zip(angs, rs)]))
    top = []
    for a, r in zip(angs, rs):
        fb = math.cos(a)                       # +1 = back edge, -1 = front edge
        h = 0.72 + 0.28 * (1 - fb) / 2
        c = base + axis * height * h
        top.append(c + (b2 * math.cos(a) * 1.45 + s2 * math.sin(a) * 0.9) * radius * 0.8 * r)
    rings.append(np.array(top))
    V, F = M.loft(rings, cap0=True, cap1=True)
    return V, F


def glow_shards(base, nrm, radius, seed=0):
    """Lava seams at a spike root: short thin glowing slivers radiating from the
    base, sunk so only a narrow bright line shows (Neon in Roblox)."""
    rng = np.random.default_rng(seed)
    fr = M.frame_from(nrm, (0, 1, 0))
    x, z = fr[:, 0], fr[:, 2]
    V, F = [], []
    for k in range(5):
        a = 2 * math.pi * k / 5 + rng.uniform(-0.4, 0.4)
        dvec = x * math.cos(a) + z * math.sin(a)
        side = np.cross(nrm, dvec)
        r0 = radius * rng.uniform(0.95, 1.1)
        L = radius * rng.uniform(0.45, 0.8)
        w = radius * rng.uniform(0.07, 0.12)
        p0 = base + dvec * r0
        p1 = base + dvec * (r0 + L)
        o = len(V)
        for p, ww in ((p0, w), (p1, w * 0.3)):
            V += [p + side * ww + nrm * 0.07, p - side * ww + nrm * 0.07, p + side * ww - nrm * 0.12,
                  p - side * ww - nrm * 0.12]
        F += [[o, o + 1, o + 5, o + 4], [o + 2, o + 6, o + 7, o + 3], [o, o + 4, o + 6, o + 2],
              [o + 1, o + 3, o + 7, o + 5], [o, o + 2, o + 3, o + 1], [o + 4, o + 5, o + 7, o + 6]]
    return np.array(V), F


SPINE_LINE = []     # rest-pose spike root points (for the hot-seam paint)


def dorsal_spikes(grid):
    parts = []
    glow = []
    SPINE_LINE.clear()
    for i, (core, bone, h, r, lean) in enumerate(dorsal_list()):
        core = np.array(core, float)
        top = surface_point(grid, core - np.array([0, 0, 0.5]), (0, 0.0, 1.0))
        nrm = surface_normal(grid, top)
        SPINE_LINE.append(top.copy())
        up = 0.5 * nrm + 0.5 * np.array([0, 0, 1.0])
        V, F = spike_mesh(top - nrm * 0.05, up, np.array([0, 1.0, 0]), h, r, lean, seed=100 + i)
        parts.append(dict(name=f'Spike_{i + 1:02d}', section='Obsidian', mat='obsidian', V=V, F=F,
                          weights=bone, bevel=(min(0.06, r * 0.08), 1, 25.0), smooth=False))
        gv, gf = glow_shards(top, nrm, r * 1.05, seed=300 + i)
        glow.append(dict(name=f'LavaGlow_{i + 1:02d}', section='LavaGlow', mat='lava', V=gv, F=gf,
                         weights=bone, bevel=None, smooth=False))
    return parts, glow


def collar_mesh(center, normal, r_out, r_in, height, seed=0, n=10):
    rng = np.random.default_rng(seed)
    fr = M.frame_from(normal, (0, 1, 0))
    x, zz = fr[:, 0], fr[:, 2]
    rings = []
    for (h, r) in ((-0.12, r_out * 0.98), (height * 0.35, r_out), (height * 0.55, r_in)):
        pts = []
        for k in range(n):
            a = 2 * math.pi * k / n
            rr = r * (1 + rng.uniform(-0.1, 0.12))
            pts.append(center + normal * h + x * math.cos(a) * rr * 1.1 + zz * math.sin(a) * rr)
        rings.append(np.array(pts))
    V, F = M.loft(rings, cap0=True, cap1=True)
    return V, F


# =========================================================================
# Beveled hull chunks (head, toes, plates)
# =========================================================================
def box_pts(center, half, frame=None, taper=(1.0, 1.0), chamfer=0.0, jitter=0.0, seed=0):
    """8 corners of a (tapered) box; taper scales the +Y end's x/z."""
    rng = np.random.default_rng(seed)
    fr = np.eye(3) if frame is None else np.asarray(frame, float)
    pts = []
    for sy in (-1, 1):
        for sx in (-1, 1):
            for sz in (-1, 1):
                tx = taper[0] if sy > 0 else 1.0
                tz = taper[1] if sy > 0 else 1.0
                q = np.array([sx * half[0] * tx, sy * half[1], sz * half[2] * tz])
                q = q * (1 + rng.uniform(-jitter, jitter, 3))
                pts.append(q)
    pts = np.array(pts)
    if chamfer > 0:
        more = []
        for p in pts:
            for ax in range(3):
                q = p.copy()
                q[ax] *= (1 - chamfer / max(abs(q[ax]), 1e-6))
                more.append(q)
        pts = np.array(more)
    return np.asarray(center, float) + pts @ fr.T


def hull_part(name, pts, section, mat, weights, bevel=(0.05, 1, 30.0)):
    V, T = M.convex_hull(np.asarray(pts, float))
    return dict(name=name, section=section, mat=mat, V=V, F=[list(t) for t in T], weights=weights,
                bevel=bevel, smooth=False, hull=True)


# =========================================================================
# Head (rest pose, faces -Y). Chunky beveled hull plates over the SDF core.
# =========================================================================
def sections_hull(secs):
    """Hull points from (y, half_width, z_bottom, z_top, top_inset) cross-sections."""
    pts = []
    for y, hw, zb, zt, ins in secs:
        for sx in (-1, 1):
            pts += [(sx * hw, y, zb), (sx * hw, y, zt - ins), (sx * (hw - ins * 0.9), y, zt)]
    return pts


def chunk(name, center, half, section, mat, weights, yaw=0.0, pitch=0.0, roll=0.0, chamfer=0.3, jitter=0.1,
          seed=0, bevel=(0.05, 2, 24.0), mirror_side=None):
    """Lumpy beveled block: a chamfered box (octagonal silhouette in every
    direction) with jittered corners, rotated by yaw/pitch/roll (deg)."""
    fr = M.rot_axis((0, 0, 1), yaw) @ M.rot_axis((1, 0, 0), pitch) @ M.rot_axis((0, 1, 0), roll)
    c = min(half) * chamfer
    pts = box_pts((0, 0, 0), half, frame=fr, chamfer=c, jitter=jitter, seed=seed)
    pts = pts + np.asarray(center, float)
    if mirror_side == 'R':
        pts = pts * np.array([-1, 1, 1])
    return hull_part(name, pts, section, mat, weights, bevel=bevel)


def head_parts():
    """Chunky lumpy plates over the SDF head core, proportioned from the
    reference: a blocky upper snout ending in a rounded nose knob, heavy
    blocky brows overhanging a small deep-set eye, lumpy cheek/jowl chunks,
    a massive beige lower jaw built from two big blocks with a notch between
    them (underbite), tusks standing up in front of the lip, and a glowing
    mouth interior seen through the gap between lip and jaw.
    Design space: head faces -Y, z up; placed by RG.head_xf."""
    P = []
    Hd = 'Head'
    bev2 = (0.06, 2, 24.0)
    # --- upper snout core (red)
    snout = sections_hull([(-8.55, 0.64, 9.16, 9.86, 0.2), (-7.85, 0.74, 9.14, 10.0, 0.22),
                           (-7.05, 0.86, 9.14, 10.2, 0.24), (-6.3, 0.96, 9.16, 10.35, 0.26)])
    P.append(hull_part('Head_Snout', snout, 'Head', 'skin_head', Hd, bevel=bev2))
    # nose knob: rounded lumpy block, the nostrils sit in its upper front
    P.append(chunk('Head_Nose', (0, -8.62, 9.72), (0.7, 0.42, 0.36), 'Head', 'skin_head', Hd, pitch=-8,
                   chamfer=0.45, jitter=0.06, seed=3))
    # lumps along the snout top
    P.append(chunk('Head_SnoutLump_1', (0.18, -7.75, 10.02), (0.34, 0.4, 0.14), 'Head', 'skin_head', Hd, yaw=8,
                   pitch=-10, jitter=0.12, seed=4, bevel=(0.04, 1, 24.0)))
    P.append(chunk('Head_SnoutLump_2', (-0.2, -7.2, 10.15), (0.32, 0.38, 0.14), 'Head', 'skin_head', Hd, yaw=-6,
                   pitch=-12, jitter=0.12, seed=5, bevel=(0.04, 1, 24.0)))
    # cranium
    skull = sections_hull([(-6.7, 0.95, 9.3, 10.75, 0.28), (-5.9, 1.08, 9.25, 11.08, 0.3),
                           (-4.95, 0.98, 9.35, 10.85, 0.3)])
    P.append(hull_part('Head_Skull', skull, 'Head', 'skin_head', Hd, bevel=bev2))
    for s in SIDES:
        m = side_fn(s)
        sg = 1 if s == 'L' else -1
        # heavy brow block over the eye, angled down toward the snout (angry V)
        P.append(chunk(f'Head_Brow_{s}', (0.66, -6.95, 10.62), (0.5, 0.62, 0.26), 'Head', 'skin_head', f'Brow_{s}',
                       yaw=-28, pitch=-14, roll=-10, chamfer=0.35, jitter=0.08, seed=10 + (s == 'R'),
                       bevel=(0.05, 2, 22.0), mirror_side=s))
        # forehead chunk above/behind the brow
        P.append(chunk(f'Head_Forehead_{s}', (0.55, -6.2, 11.0), (0.46, 0.5, 0.24), 'Head', 'skin_head', Hd,
                       yaw=-15, pitch=-6, roll=-12, jitter=0.1, seed=12 + (s == 'R'), mirror_side=s))
        # cheek / jowl: two lumpy chunks behind and below the eye
        P.append(chunk(f'Head_Cheek_{s}', (0.98, -6.25, 9.62), (0.34, 0.62, 0.46), 'Head', 'skin_head', Hd,
                       yaw=-12, roll=8, chamfer=0.4, jitter=0.1, seed=14 + (s == 'R'), mirror_side=s))
        P.append(chunk(f'Head_Jowl_{s}', (1.08, -5.4, 9.45), (0.36, 0.55, 0.55), 'Head', 'skin_head', Hd,
                       yaw=-5, roll=6, chamfer=0.4, jitter=0.12, seed=16 + (s == 'R'), mirror_side=s))
        # snout side plate (the lit plane between the nose and the eye)
        P.append(chunk(f'Head_SnoutSide_{s}', (0.74, -7.7, 9.58), (0.14, 0.78, 0.36), 'Head', 'skin_head', Hd,
                       yaw=-8, jitter=0.08, seed=18 + (s == 'R'), bevel=(0.04, 1, 22.0), mirror_side=s))
        # upper lip: overhangs the jaw along the mouth line, lifted at the rear to show the glowing mouth
        lip = [m(p) for p in ((0.58, -8.72, 9.12), (0.86, -7.4, 9.12), (1.02, -6.3, 9.24), (0.7, -8.62, 9.42),
                             (0.92, -7.3, 9.44), (1.06, -6.3, 9.55), (0.5, -8.8, 9.3))]
        P.append(hull_part(f'Head_Lip_{s}', lip, 'Head', 'skin_head', Hd, bevel=(0.04, 1, 22.0)))
        # rear jaw-hinge plate
        jm = [m(p) for p in ((1.0, -5.95, 8.95), (1.32, -5.0, 9.1), (1.36, -5.1, 9.95), (1.12, -5.85, 9.9),
                            (0.92, -4.8, 8.95), (0.98, -4.7, 9.9))]
        P.append(hull_part(f'Head_JawHinge_{s}', jm, 'Head', 'skin_head', Hd, bevel=(0.05, 1, 22.0)))
        # upper eyelid (blinks down over the eye)
        e = np.asarray(RG.J_HEAD_DESIGN['eye'], float) * np.array([sg, 1, 1])
        lid = [e + np.array(v) * np.array([sg, 1, 1]) for v in
               ((-0.24, -0.26, 0.1), (0.18, -0.3, 0.08), (0.26, 0.16, 0.08), (-0.16, 0.2, 0.12),
                (-0.16, -0.24, 0.22), (0.16, 0.16, 0.22), (0.02, -0.04, 0.26))]
        P.append(hull_part(f'Head_Eyelid_{s}', lid, 'Head', 'skin_head', f'Eyelid_{s}', bevel=(0.03, 1, 25.0)))
    # crest plates along the skull top
    for i, (y, z, w) in enumerate(((-6.4, 11.18, 0.3), (-5.75, 11.3, 0.38), (-5.05, 11.12, 0.4))):
        c = box_pts((0, y, z), (w, 0.3, 0.18), chamfer=0.1, jitter=0.08, seed=40 + i)
        P.append(hull_part(f'Head_Crest_{i + 1}', c, 'Head', 'skin_head', Hd, bevel=(0.04, 1, 25.0)))
    # --- lower jaw (beige): two massive lumpy blocks + chin, hinged on Jaw
    P.append(chunk('Head_JawFront', (0, -8.25, 8.58), (0.9, 0.72, 0.44), 'Head', 'jaw', 'Jaw', pitch=3,
                   chamfer=0.28, jitter=0.06, seed=30))
    for s in SIDES:
        P.append(chunk(f'Head_JawSide_{s}', (0.66, -6.75, 8.62), (0.46, 0.95, 0.4), 'Head', 'jaw', 'Jaw', yaw=-5,
                       roll=-4, chamfer=0.3, jitter=0.07, seed=31 + (s == 'R'), mirror_side=s))
        P.append(chunk(f'Head_JawRear_{s}', (0.8, -5.6, 8.72), (0.42, 0.62, 0.4), 'Head', 'jaw', 'Jaw', yaw=-8,
                       roll=-6, chamfer=0.32, jitter=0.08, seed=33 + (s == 'R'), mirror_side=s))
    P.append(chunk('Head_JawUnder', (0, -6.6, 8.5), (0.62, 1.6, 0.28), 'Head', 'jaw', 'Jaw', chamfer=0.3,
                   jitter=0.04, seed=35))
    # mouth interior (glowing): floor on the jaw, palate under the snout. Seen through
    # the lip gap and fully when the jaw opens (fire breath). Emissive -> Neon.
    P.append(hull_part('Head_MouthFloor', box_pts((0, -7.0, 8.99), (0.78, 1.55, 0.05)), 'LavaGlow', 'mouth', 'Jaw',
                       bevel=None))
    P.append(hull_part('Head_Palate', box_pts((0, -7.1, 9.16), (0.72, 1.45, 0.05)), 'LavaGlow', 'mouth', Hd,
                       bevel=None))
    P.append(hull_part('Head_Throat', box_pts((0, -5.55, 9.05), (0.7, 0.2, 0.2)), 'LavaGlow', 'mouth', Hd,
                       bevel=None))
    # Teeth (user polish: clearly bigger). Lower teeth stand up along the jaw just
    # outside the upper lip, with a big corner tusk overlapping the lip; upper
    # teeth hang from the lip, with a big corner fang outside the rear jaw. All
    # chunky faceted cones (hexagonal base, bulged shoulder ring, blunt tip).
    def lip_x(y):
        return float(np.interp(y, [-8.72, -7.4, -6.3], [0.58, 0.86, 1.02]))
    teeth = [  # (y, x offset from the lip edge, length, base radius, up, tilt out)
        (-8.62, 0.04, 0.46, 0.13, True, 0.05), (-8.1, 0.05, 0.56, 0.15, True, 0.06),
        (-7.45, 0.1, 1.0, 0.25, True, 0.12),                       # lower corner tusk over the lip
        (-6.85, 0.06, 0.6, 0.16, True, 0.06), (-6.2, 0.05, 0.46, 0.14, True, 0.05),
        (-8.5, -0.04, 0.4, 0.12, False, 0.05),
        (-6.55, 0.18, 0.82, 0.21, False, 0.12),                    # upper corner fang outside the jaw
    ]
    for s in SIDES:
        m = side_fn(s)
        for i, (y, dx, L, r, up, tilt) in enumerate(teeth):
            x = lip_x(y) + dx
            base = np.array([x, y, 8.96 if up else 9.16])
            d_ = np.array([tilt, 0.0, 1.0 if up else -1.0])
            d_ /= np.linalg.norm(d_)
            ring = [base + np.array([math.cos(a_) * r, math.sin(a_) * r * 0.85, 0]) for a_ in np.linspace(0, 2 * math.pi, 6, endpoint=False)]
            ring0 = [q - d_ * 0.16 for q in ring]
            ring1 = [base + d_ * L * 0.38 + (q - base) * 0.82 for q in ring]
            tip = base + d_ * L + np.array([0, 0.05, 0])
            tip2 = tip - d_ * 0.06 + np.array([r * 0.18, 0, 0])
            pts = [m(q) for q in ring0 + ring + ring1 + [tip, tip2]]
            P.append(hull_part(f'Fang_{s}_{i + 1}', pts, 'Head', 'fang', 'Jaw' if up else Hd, bevel=(0.025, 1, 30.0)))
    return P


def horn_mesh(root, dirs, lengths, radius, sides=5, seed=0):
    """Faceted curved horn: pentagonal cross-section tapering to a beveled point."""
    rng = np.random.default_rng(seed)
    pts = [np.asarray(root, float)]
    for d, L in zip(dirs, lengths):
        d = np.asarray(d, float)
        pts.append(pts[-1] + d / np.linalg.norm(d) * L)
    pts = np.array(pts)
    n = len(pts)
    rings = []
    for i in range(n - 1):
        t = i / (n - 1)
        tan = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        fr = M.frame_from(tan, (0, 0, 1))
        r = radius * (1 - 0.82 * t ** 0.9)
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides + 0.3
            rr = r * (1 + rng.uniform(-0.08, 0.08))
            ring.append(pts[i] + fr[:, 0] * math.cos(a) * rr + fr[:, 2] * math.sin(a) * rr * 1.15)
        rings.append(np.array(ring))
    V, F = M.loft(rings, cap0=True, cap1=False)
    V = np.concatenate([V, [pts[-1]]])
    ti = len(V) - 1
    last = (len(rings) - 1) * sides
    for k in range(sides):
        F.append([last + k, last + (k + 1) % sides, ti])
    return V, F


def horns():
    """Two obsidian horns per side: a huge swept-back horn from the rear of the
    skull (tip ~(+-1.9, -1.0, 13.6) design space, the reference's big horns
    that sweep back over the neck) and a smaller one above the brow (tip
    fitted to the reference within 3 px)."""
    parts = []
    for s in SIDES:
        m = side_fn(s)
        sx = 1 if s == 'L' else -1
        V, F = horn_mesh(m((0.8, -5.45, 10.7)),
                         [(sx * 0.15, 0.35, 0.92), (sx * 0.2, 0.75, 0.63), (sx * 0.22, 0.93, 0.3), (sx * 0.2, 0.97, 0.05)],
                         [1.5, 1.5, 1.4, 1.3], 0.84, sides=6, seed=10 + (s == 'R'))
        parts.append(dict(name=f'Horn_{s}_1', section='Obsidian', mat='obsidian', V=V, F=F, weights='Head',
                          bevel=(0.05, 1, 25.0), smooth=False))
        V, F = horn_mesh(m((0.55, -6.4, 10.75)),
                         [(sx * 0.3, 0.45, 0.84), (sx * 0.4, 0.8, 0.45)],
                         [1.2, 1.2], 0.46, sides=6, seed=20 + (s == 'R'))
        parts.append(dict(name=f'Horn_{s}_2', section='Obsidian', mat='obsidian', V=V, F=F, weights='Head',
                          bevel=(0.035, 1, 25.0), smooth=False))
    return parts


def eyes():
    parts = []
    for s in SIDES:
        m = side_fn(s)
        e = m(RG.J_HEAD_DESIGN['eye'])
        sx = 1 if s == 'L' else -1
        out = np.array([sx * 0.82, -0.52, 0.12])
        out /= np.linalg.norm(out)
        fr = M.frame_from(out, (0, 0, 1))
        pts = []
        for k in range(10):
            a = 2 * math.pi * k / 10
            pts.append(e + fr[:, 0] * math.cos(a) * 0.36 * (1 + 0.25 * math.cos(a) * sx) + fr[:, 2] * math.sin(a) * 0.19)
        pts.append(e + out * 0.1)
        pts.append(e - out * 0.12)
        parts.append(hull_part(f'Eye_{s}', pts, 'EyeGlow', 'eye', 'Head', bevel=None))
    return parts


# =========================================================================
# Feet: red toe plates + obsidian claws
# =========================================================================
def claw_mesh(base, tip, width, thick, seed=0):
    """Chunky blunt obsidian claw: a faceted wedge (pentagonal section with a
    top ridge) running from the knuckle steeply down to a blunt tip resting on
    the ground. `width` across the toe, `thick` perpendicular to the claw axis."""
    base = np.asarray(base, float)
    tip = np.asarray(tip, float)
    ax = tip - base
    L = np.linalg.norm(ax)
    ax /= L
    h = np.cross(ax, np.array([0, 0, 1.0]))
    lat = h / np.linalg.norm(h)
    up = np.cross(lat, ax)                           # outer (top) side of the claw
    sect = [(-1.0, -0.45), (-0.8, 0.42), (0.0, 1.0), (0.8, 0.42), (1.0, -0.45), (0.0, -0.78)]
    rings = []
    ts = (0.0, 0.3, 0.6, 0.85, 1.0)
    for t in ts:
        sc = 1.0 - 0.58 * t ** 1.4
        bow = thick * 0.35 * math.sin(math.pi * t)       # slight outward arch (hooked talon)
        c = base + ax * L * t + up * bow
        if t == 1.0:
            c = tip + up * thick * 0.18
        rings.append(np.array([c + lat * px * width * 0.5 * sc + up * pz * thick * 0.5 * sc for px, pz in sect]))
    V, F = M.loft(rings, cap0=True, cap1=True)
    return V, F


def feet_parts():
    parts = []
    for kind, hand in (('front', 'Hand'), ('hind', 'Foot')):
        sc = RG.TOE_ROWS[kind][3]
        for s in SIDES:
            for k, (base, mid, cb, tip) in enumerate(RG.toe_layout(kind, s)):
                b1 = f'{hand}_{s}_Toe{k + 1}_1'
                b2 = f'{hand}_{s}_Toe{k + 1}_2'
                # proximal toe plate
                d1 = mid - base
                fr1 = M.frame_from(d1, (0, 0, 1))
                c1 = 0.5 * (base + mid) + np.array([0, 0, 0.06])
                seed0 = (0 if kind == 'front' else 100) + (0 if s == 'L' else 50) + 4 * k
                P1 = box_pts(c1, (0.4 * sc, np.linalg.norm(d1) * 0.6, 0.38 * sc), frame=fr1, taper=(0.92, 0.9),
                             chamfer=0.14, jitter=0.05, seed=seed0 + 1)
                parts.append(hull_part(f'Toe_{hand}_{s}_{k + 1}_a', P1, 'Body', 'skin', b1, bevel=(0.05, 1, 25.0)))
                # distal toe plate (knuckle cap over the claw root)
                d2 = cb - mid
                fr2 = M.frame_from(d2, (0, 0, 1))
                c2 = 0.5 * (mid + cb) + np.array([0, 0, 0.05])
                P2 = box_pts(c2, (0.42 * sc, max(np.linalg.norm(d2) * 0.62, 0.3), 0.4 * sc), frame=fr2,
                             taper=(0.9, 0.85), chamfer=0.14, jitter=0.05, seed=seed0 + 2)
                parts.append(hull_part(f'Toe_{hand}_{s}_{k + 1}_b', P2, 'Body', 'skin', b2, bevel=(0.05, 1, 25.0)))
                V, F = claw_mesh(cb - (cb - mid) * 0.3, tip, 0.88 * sc, 0.7 * sc, seed=k)
                parts.append(dict(name=f'Claw_{hand}_{s}_{k + 1}', section='Obsidian', mat='obsidian', V=V, F=F,
                                  weights=b2, bevel=(0.035, 1, 25.0), smooth=False))
    return parts


# =========================================================================
# Tail spade (obsidian arrowhead in the tail's vertical plane)
# =========================================================================
def spade():
    """Big chunky obsidian arrowhead: a thick faceted crystal kite at the tail
    tip (point forward along the tail, long barbs up-back and down), sized from
    the reference (~3.2 long, ~4 across the barbs, ~1.4 thick)."""
    sk = RG.Skeleton()
    h = sk.head['TailTip']
    t = sk.tail['TailTip']
    d = (t - h) / np.linalg.norm(t - h)
    up = np.array([0, 0, 1.0]) - d * d[2]
    up /= np.linalg.norm(up)
    lat = np.cross(d, up)
    o = h + d * 0.55
    pts = [o + d * 2.05 + up * 0.15,                     # point
           o - d * 1.05 + up * 2.0,                      # upper barb
           o - d * 0.5 - up * 1.8,                       # lower barb
           o + d * 0.35 + lat * 0.72 + up * 0.15,        # side ridges (thick middle)
           o + d * 0.35 - lat * 0.72 + up * 0.15,
           o - d * 0.35 + lat * 0.5 + up * 0.95,
           o - d * 0.35 - lat * 0.5 + up * 0.95,
           o - d * 0.1 + lat * 0.5 - up * 0.85,
           o - d * 0.1 - lat * 0.5 - up * 0.85,
           o - d * 0.85 + lat * 0.3,                     # root collar
           o - d * 0.85 - lat * 0.3,
           o + d * 1.2 + lat * 0.35 + up * 0.45,         # facets toward the point
           o + d * 1.2 - lat * 0.35 + up * 0.45,
           o + d * 1.1 + lat * 0.3 - up * 0.3,
           o + d * 1.1 - lat * 0.3 - up * 0.3]
    return [hull_part('TailSpade', pts, 'Obsidian', 'obsidian', 'TailTip', bevel=(0.06, 1, 20.0))]


# =========================================================================
# Wings: thick red bone prisms, obsidian claws, thick scalloped membrane
# =========================================================================
def wing_chain(s):
    m = side_fn(s)
    return {k: m(J[k]) for k in ('w_root', 'w_elbow', 'w_wrist', 'w_hand', 'w_thumb', 'w_f1k', 'w_f1t', 'w_f2k', 'w_f2t')}


def bone_prism(a, b, ra, rb, sides=6, z_hint=(0, 0, 1), knob=1.0):
    fr = M.frame_from(np.asarray(b) - np.asarray(a), z_hint)
    rings = []
    for t, r in ((0.0, ra * knob * 0.8), (0.08, ra * knob), (0.2, ra), (0.8, rb), (0.93, rb * knob), (1.0, rb * knob * 0.75)):
        c = np.asarray(a) * (1 - t) + np.asarray(b) * t
        rings.append(M.ring(c, fr, r, r * 1.12, sides, phase=math.pi / sides))
    return M.loft(rings, cap0=True, cap1=True)


def resample(poly, n):
    poly = np.asarray(poly, float)
    seg = np.linalg.norm(np.diff(poly, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    ss = np.linspace(0, s[-1], n)
    return np.stack([np.interp(ss, s, poly[:, k]) for k in range(3)], 1), ss / s[-1], s / s[-1]


def membrane_panel(lead, trail, lead_bones, trail_bones, nu=10, nv=12, scallop=0.22, tatter=0.0, sag=0.12,
                   thick=0.15, seed=0, flank_bone=None):
    """Thick membrane between two bone polylines, free edge scalloped inward.

    lead/trail: polylines from the shared root to the tips. lead_bones /
    trail_bones: bone name per polyline segment. Weights interpolate the lead
    and trail bones across the panel so it stretches cleanly when fingers
    spread or fold (no twisting: every vertex follows at most 2+2 bones)."""
    rng = np.random.default_rng(seed)
    Lp, _, lk = resample(lead, 200)
    Tp, _, tk = resample(trail, 200)
    pts = []
    Wlist = []
    for iv in range(nv):
        for iu in range(nu):
            u = iu / (nu - 1)
            v_edge = 1 - scallop * math.sin(math.pi * u) ** 0.85
            if tatter > 0 and 0.05 < u < 0.95:
                v_edge -= tatter * (0.5 + 0.5 * math.cos(u * math.pi * 7 + rng.uniform(-0.3, 0.3)))
            v = (iv / (nv - 1)) * v_edge
            li = min(int(v * 199), 199)
            a = Lp[li]
            b = Tp[li]
            p = a * (1 - u) + b * u
            pts.append(p)
            Wlist.append((u, v))
    G = np.array(pts).reshape(nv, nu, 3)
    # billow: sag along the panel normal
    du = G[:, -1] - G[:, 0]
    dv = G[-1, :] - G[0, :]
    nrm = np.cross(du.mean(0), dv.mean(0))
    nrm /= np.linalg.norm(nrm)
    for iv in range(nv):
        for iu in range(nu):
            u, v = Wlist[iv * nu + iu]
            G[iv, iu] += nrm * sag * math.sin(math.pi * u) * math.sin(math.pi * min(v * 1.05, 1.0)) * v
    V, F, side = M.thick_sheet(G.reshape(-1, 3), (nv, nu), thick)
    # weights
    def seg_weights(bones, knots, v):
        w = {}
        nseg = len(bones)
        for k in range(nseg):
            lo, hi = knots[k], knots[k + 1]
            blend = 0.08
            wk = 1.0
            if k > 0:
                wk *= M.smoothstep(lo - blend, lo + blend, v)
            if k < nseg - 1:
                wk *= 1 - M.smoothstep(hi - blend, hi + blend, v)
            w[bones[k]] = w.get(bones[k], 0) + wk
        tot = sum(w.values())
        return {b: x / max(tot, 1e-9) for b, x in w.items()}
    W = {}
    n = len(V)
    for idx in range(n):
        u, v = Wlist[idx % (nu * nv)]
        wl = seg_weights(lead_bones, lk, v)
        wt = seg_weights(trail_bones, tk, v)
        for b, x in wl.items():
            W.setdefault(b, np.zeros(n))[idx] += x * (1 - u)
        for b, x in wt.items():
            W.setdefault(b, np.zeros(n))[idx] += x * u
    return V, F, W


def wing_parts(body_grid=None):
    parts = []
    for s in SIDES:
        c = wing_chain(s)
        sx = 1 if s == 'L' else -1
        # bones (red, beveled hexagonal prisms with knuckle knobs)
        spec = [('w_root', 'w_elbow', 0.78, 0.6, f'Wing_{s}_1'), ('w_elbow', 'w_wrist', 0.62, 0.46, f'Wing_{s}_2'),
                ('w_hand', 'w_f1k', 0.42, 0.3, f'Wing_{s}_Finger1_1'), ('w_f1k', 'w_f1t', 0.3, 0.16, f'Wing_{s}_Finger1_2'),
                ('w_hand', 'w_f2k', 0.36, 0.26, f'Wing_{s}_Finger2_1'), ('w_f2k', 'w_f2t', 0.26, 0.14, f'Wing_{s}_Finger2_2')]
        for a, b, ra, rb, bone in spec:
            V, F = bone_prism(c[a], c[b], ra, rb, sides=7, z_hint=(0, -1, 0), knob=1.08)
            parts.append(dict(name=f'WingBone_{bone}', section='Wings', mat='wingbone', V=V, F=F, weights=bone,
                              bevel=(0.07, 2, 22.0), smooth=False))
        # wrist knob
        wk = box_pts(0.5 * (c['w_wrist'] + c['w_hand']), (0.68, 0.58, 0.62), chamfer=0.2, jitter=0.06, seed=7)
        parts.append(hull_part(f'WingWrist_{s}', wk, 'Wings', 'wingbone', f'Wing_{s}_3', bevel=(0.05, 1, 25.0)))
        ek = box_pts(c['w_elbow'], (0.7, 0.62, 0.66), chamfer=0.2, jitter=0.06, seed=8)
        parts.append(hull_part(f'WingElbow_{s}', ek, 'Wings', 'wingbone', f'Wing_{s}_2', bevel=(0.05, 1, 25.0)))
        # claws
        th = c['w_thumb'] - c['w_wrist']
        V, F = horn_mesh(c['w_wrist'] + th * 0.28, [th], [np.linalg.norm(th) * 0.72], 0.36, seed=30)
        parts.append(dict(name=f'WingClaw_{s}_Thumb', section='Obsidian', mat='obsidian', V=V, F=F,
                          weights=f'Wing_{s}_Thumb', bevel=(0.03, 1, 25.0), smooth=False))
        for fi in (1, 2):
            k, t = c[f'w_f{fi}k'], c[f'w_f{fi}t']
            d = (t - k) / np.linalg.norm(t - k)
            V, F = horn_mesh(t - d * 0.35, [d], [1.6 if fi == 1 else 1.35], 0.3, seed=31 + fi)
            parts.append(dict(name=f'WingClaw_{s}_F{fi}', section='Obsidian', mat='obsidian', V=V, F=F,
                              weights=f'Wing_{s}_Finger{fi}_2', bevel=(0.025, 1, 25.0), smooth=False))
        # membrane panel A: finger 1 (leading) to finger 2
        lead = [c['w_hand'], c['w_f1k'], c['w_f1t']]
        trail = [c['w_hand'], c['w_f2k'], c['w_f2t']]
        V, F, W = membrane_panel(lead, trail, [f'Wing_{s}_Finger1_1', f'Wing_{s}_Finger1_2'],
                                 [f'Wing_{s}_Finger2_1', f'Wing_{s}_Finger2_2'], nu=11, nv=13, scallop=0.16, sag=0.25 * sx,
                                 thick=0.16, seed=1)
        parts.append(dict(name=f'Membrane_{s}_A', section='Wings', mat='membrane', V=V, F=F, weights=W,
                          bevel=None, smooth=False))
        # panel B: finger 2 to the arm and down to the flank
        flank = side_fn(s)((2.3, 2.9, 9.2))
        lead = [c['w_hand'], c['w_f2k'], c['w_f2t']]
        flank = side_fn(s)((3.35, 1.3, 8.5))
        trail = [c['w_wrist'], c['w_elbow'], c['w_root'] + np.array([0.3, 0.1, -0.2]), flank]
        V, F, W = membrane_panel(lead, trail, [f'Wing_{s}_Finger2_1', f'Wing_{s}_Finger2_2'],
                                 [f'Wing_{s}_2', f'Wing_{s}_1', 'Spine_2'], nu=12, nv=13, scallop=0.06,
                                 tatter=0.04, sag=0.3 * sx, thick=0.16, seed=2)
        parts.append(dict(name=f'Membrane_{s}_B', section='Wings', mat='membrane', V=V, F=F, weights=W,
                          bevel=None, smooth=False))
    return parts


# =========================================================================
def torso_grid(prims, h=0.1):
    keep = [p for p in prims if p.tag in ('chest', 'withers', 'belly_f', 'belly_r', 'back', 'hips', 'neck',
                                           'neck_top', 'head_core', 'tail')]
    lo = np.full(3, 1e9)
    hi = np.full(3, -1e9)
    for p in keep:
        a, b = p.bounds()
        lo = np.minimum(lo, a)
        hi = np.maximum(hi, b)
    return M.Grid(lo - 0.4, hi + 0.4, h).build(keep)


def build_all(h=0.1):
    prims = body_prims()
    V, Q, grid = M.sdf_mesh(prims, h)
    tgrid = torso_grid(prims, 0.1)
    body = dict(name='BodySkin', section='Body', mat='skin', V=V, F=[list(q) for q in Q], weights='__prims__',
                bevel=None, smooth=False, sdf=True)
    parts = [body]
    for p in head_parts() + horns() + eyes():
        p['V'] = RG.head_xf(p['V'])
        parts.append(p)
    parts += feet_parts()
    parts += spade()
    sp, glow = dorsal_spikes(tgrid)
    parts += sp + glow
    parts += belly_plates(tgrid, prims)
    parts += wing_parts()
    return parts, prims, grid
