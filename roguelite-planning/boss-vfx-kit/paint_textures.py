"""
paint_textures.py -- numpy-only painters for the boss VFX kit.

Runs under system Python or Blender's bundled Python (numpy only; PNGs are
written with zlib, no Pillow needed):

    python paint_textures.py [out_dir]

build_vfx_kit.py imports this module for the shared noise, SDF, glyph and PNG
helpers, and calls paint_all() so one Blender run rebuilds the whole kit.

Style rules (ART_DIRECTION_USER_2026-09-17): painterly, low-noise, 2-4 value
bands with soft transitions, chunky readable shapes, bright but controlled
colour, glow used sparingly. Every sprite has a transparent, colour-bled
background so Roblox mip-maps do not grow dark fringes.
"""
import math
import os
import struct
import sys
import zlib

import numpy as np

TAU = 2.0 * math.pi


# --------------------------------------------------------------------------- io
def save_png(path, img):
    """img: HxWx3 or HxWx4 float 0..1, straight alpha, values already sRGB."""
    a = np.clip(np.asarray(img, dtype=np.float64) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    h, w, c = a.shape
    raw = np.concatenate([np.zeros((h, 1), np.uint8), a.reshape(h, w * c)], axis=1).tobytes()

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6 if c == 4 else 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 7))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def bleed(rgbc, a, thresh=0.004):
    """Push-pull fill: transparent texels take the colour of nearby painted ones."""
    w = (np.asarray(a) > thresh).astype(np.float64)
    if w.all():
        return rgbc
    cs, ws = [rgbc * w[..., None]], [w]
    while cs[-1].shape[0] > 1 and cs[-1].shape[1] > 1:
        c, ww = cs[-1], ws[-1]
        h2, w2 = c.shape[0] // 2, c.shape[1] // 2
        cs.append(c[:h2 * 2, :w2 * 2].reshape(h2, 2, w2, 2, 3).sum(axis=(1, 3)))
        ws.append(ww[:h2 * 2, :w2 * 2].reshape(h2, 2, w2, 2).sum(axis=(1, 3)))
    fill = cs[-1] / np.maximum(ws[-1], 1e-9)[..., None]
    for c, ww in zip(reversed(cs[:-1]), reversed(ws[:-1])):
        up = np.repeat(np.repeat(fill, 2, axis=0), 2, axis=1)[:c.shape[0], :c.shape[1]]
        fill = np.where((ww > 0)[..., None], c / np.maximum(ww, 1e-9)[..., None], up)
    return np.where(w[..., None] > 0, rgbc, fill)


def save_rgba(path, rgbc, a, do_bleed=True):
    rgbc = np.clip(rgbc, 0, 1)
    if do_bleed:
        rgbc = bleed(rgbc, a)
    save_png(path, np.dstack([rgbc, np.clip(a, 0, 1)]))


# ----------------------------------------------------------------------- basics
def rgb(r, g, b):
    return np.array([r, g, b], dtype=np.float64) / 255.0


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, np.float64) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def mix(a, b, t):
    t = np.asarray(t, np.float64)
    if t.ndim:
        t = t[..., None]
    return a + (np.asarray(b, np.float64) - a) * t


def bands(v, cols, edges, soft=0.05):
    """Soft posterise v into len(cols) painted value bands."""
    v = np.asarray(v, np.float64)
    out = np.empty(v.shape + (3,))
    out[...] = cols[0]
    for c, e in zip(cols[1:], edges):
        out = mix(out, c, smoothstep(e - soft, e + soft, v))
    return out


def over(dst_rgb, dst_a, src_rgb, src_a):
    sa = np.asarray(src_a)[..., None]
    da = np.asarray(dst_a)[..., None]
    out_a = sa + da * (1 - sa)
    out = (np.asarray(src_rgb) * sa + dst_rgb * da * (1 - sa)) / np.maximum(out_a, 1e-6)
    return out, out_a[..., 0]


def grid(n):
    """Pixel-centre coordinates in [-1, 1], y up (row 0 is the top)."""
    c = (np.arange(n) + 0.5) / n * 2.0 - 1.0
    x, y = np.meshgrid(c, -c)
    return x, y


def cov(sd, aa):
    """Coverage of an SDF (negative inside) with an anti-alias width aa."""
    return np.clip(0.5 - sd / aa, 0.0, 1.0)


def edge_mask(n, inner=0.9, outer=0.985):
    x, y = grid(n)
    return smoothstep(outer, inner, np.maximum(np.abs(x), np.abs(y)))


def stamp_window(n, cx, cy, rad):
    j0 = max(0, int(((cx - rad) + 1) / 2 * n) - 1)
    j1 = min(n, int(((cx + rad) + 1) / 2 * n) + 2)
    i0 = max(0, int((1 - (cy + rad)) / 2 * n) - 1)
    i1 = min(n, int((1 - (cy - rad)) / 2 * n) + 2)
    return slice(i0, max(i0, i1)), slice(j0, max(j0, j1))


# ------------------------------------------------------------------------ noise
_U = np.uint64


def _hash3(ix, iy, iz, seed):
    ix = ix.astype(np.int64).astype(_U)
    iy = iy.astype(np.int64).astype(_U)
    iz = iz.astype(np.int64).astype(_U)
    m = _U(0xFFFFFFFF)
    h = (ix * _U(73856093)) ^ (iy * _U(19349663)) ^ (iz * _U(83492791)) ^ _U((seed * 2654435761) & 0xFFFFFFFF)
    h &= m
    h = ((h ^ (h >> _U(15))) * _U(2246822519)) & m
    h = ((h ^ (h >> _U(13))) * _U(3266489917)) & m
    h ^= h >> _U(16)
    return (h & _U(0xFFFFFF)).astype(np.float64) / 16777216.0


def vnoise3(x, y, z, seed=0):
    x, y, z = np.broadcast_arrays(np.asarray(x, np.float64), np.asarray(y, np.float64),
                                  np.asarray(z, np.float64))
    xf, yf, zf = np.floor(x), np.floor(y), np.floor(z)
    tx, ty, tz = x - xf, y - yf, z - zf
    tx = tx * tx * (3 - 2 * tx)
    ty = ty * ty * (3 - 2 * ty)
    tz = tz * tz * (3 - 2 * tz)
    xi, yi, zi = xf.astype(np.int64), yf.astype(np.int64), zf.astype(np.int64)

    def h(dx, dy, dz):
        return _hash3(xi + dx, yi + dy, zi + dz, seed)

    x00 = h(0, 0, 0) + (h(1, 0, 0) - h(0, 0, 0)) * tx
    x10 = h(0, 1, 0) + (h(1, 1, 0) - h(0, 1, 0)) * tx
    x01 = h(0, 0, 1) + (h(1, 0, 1) - h(0, 0, 1)) * tx
    x11 = h(0, 1, 1) + (h(1, 1, 1) - h(0, 1, 1)) * tx
    y0 = x00 + (x10 - x00) * ty
    y1 = x01 + (x11 - x01) * ty
    return y0 + (y1 - y0) * tz


def fbm3(x, y, z, octaves=3, seed=0, lac=2.03, gain=0.5):
    total, amp, norm, f = 0.0, 1.0, 0.0, 1.0
    for o in range(octaves):
        total = total + amp * vnoise3(np.asarray(x) * f, np.asarray(y) * f, np.asarray(z) * f, seed + o * 101)
        norm += amp
        amp *= gain
        f *= lac
    return total / norm


# -------------------------------------------------------------------------- sdf
def sd_circle(x, y, cx, cy, r):
    return np.hypot(x - cx, y - cy) - r


def sd_ellipse(x, y, cx, cy, rx, ry, rot=0.0):
    dx, dy = x - cx, y - cy
    if rot:
        c, s = math.cos(rot), math.sin(rot)
        dx, dy = c * dx + s * dy, -s * dx + c * dy
    return (np.hypot(dx / rx, dy / ry) - 1.0) * min(rx, ry)


def sd_segment(x, y, ax, ay, bx, by):
    px, py = x - ax, y - ay
    ex, ey = bx - ax, by - ay
    h = np.clip((px * ex + py * ey) / (ex * ex + ey * ey + 1e-12), 0.0, 1.0)
    return np.hypot(px - ex * h, py - ey * h), h


def sd_polyline(x, y, pts, r):
    d = np.full(np.shape(x), 9.0)
    for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
        d = np.minimum(d, sd_segment(x, y, ax, ay, bx, by)[0])
    return d - r


def sd_box(x, y, cx, cy, hw, hh, rad=0.0):
    dx = np.abs(x - cx) - hw + rad
    dy = np.abs(y - cy) - hh + rad
    return (np.hypot(np.maximum(dx, 0), np.maximum(dy, 0))
            + np.minimum(np.maximum(dx, dy), 0) - rad)


def sd_poly(x, y, pts):
    """Signed distance to a simple polygon (negative inside)."""
    p = np.asarray(pts, np.float64)
    n = len(p)
    d = (x - p[0, 0]) ** 2 + (y - p[0, 1]) ** 2
    s = np.ones(np.shape(x))
    j = n - 1
    for i in range(n):
        ex, ey = p[j, 0] - p[i, 0], p[j, 1] - p[i, 1]
        wx, wy = x - p[i, 0], y - p[i, 1]
        h = np.clip((wx * ex + wy * ey) / (ex * ex + ey * ey + 1e-12), 0.0, 1.0)
        bx, by = wx - ex * h, wy - ey * h
        d = np.minimum(d, bx * bx + by * by)
        c1 = y >= p[i, 1]
        c2 = y < p[j, 1]
        c3 = ex * wy > ey * wx
        flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
        s = np.where(flip, -s, s)
        j = i
    return s * np.sqrt(d)


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def _arc(cx, cy, r, a0, a1, n=10):
    return [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in np.linspace(a0, a1, n)]


# ----------------------------------------------------------------------- glyphs
# Simplified bold hieroglyphs in glyph units ([-1, 1], y up). Negative = ink.
def g_eye(x, y):
    t = np.linspace(-1, 1, 11)
    up = [(0.72 * v, 0.08 + 0.30 * (1 - v * v)) for v in t]
    lo = [(0.72 * v, 0.08 - 0.20 * (1 - v * v)) for v in t]
    d = np.minimum(sd_polyline(x, y, up, 0.09), sd_polyline(x, y, lo, 0.09))
    d = np.minimum(d, sd_circle(x, y, 0.0, 0.1, 0.17))
    d = np.minimum(d, sd_polyline(x, y, [(-0.72, 0.58), (-0.1, 0.68), (0.72, 0.55)], 0.08))
    d = np.minimum(d, sd_polyline(x, y, [(-0.14, -0.1), (-0.22, -0.78)], 0.08))
    curl = [(0.12, -0.12), (0.28, -0.42), (0.43, -0.66)] + _arc(0.6, -0.6, 0.18, math.radians(200), math.radians(470), 9)
    return np.minimum(d, sd_polyline(x, y, curl, 0.075))


def g_ankh(x, y):
    loop = np.abs(sd_ellipse(x, y, 0, 0.5, 0.27, 0.36)) - 0.1
    bar = sd_box(x, y, 0, 0.06, 0.62, 0.1, 0.03)
    stem = sd_poly(x, y, [(-0.11, 0.1), (0.11, 0.1), (0.2, -0.95), (-0.2, -0.95)])
    return np.minimum(np.minimum(loop, bar), stem)


def g_scarab(x, y):
    d = np.minimum(sd_ellipse(x, y, 0, -0.18, 0.4, 0.52), sd_ellipse(x, y, 0, 0.47, 0.26, 0.16))
    d = np.maximum(d, -(sd_segment(x, y, 0, -0.62, 0, 0.26)[0] - 0.035))
    d = np.maximum(d, -(sd_segment(x, y, -0.3, 0.3, 0.3, 0.3)[0] - 0.03))
    for sx in (-1, 1):
        for pts in ([(0.3, 0.1), (0.62, 0.32), (0.72, 0.62)], [(0.38, -0.15), (0.82, -0.12)],
                    [(0.32, -0.5), (0.62, -0.72), (0.66, -0.95)]):
            d = np.minimum(d, sd_polyline(x, y, [(sx * a, b) for a, b in pts], 0.065))
    return d


def g_falcon(x, y):
    d = sd_ellipse(x, y, -0.05, -0.05, 0.46, 0.33, rot=0.5)
    d = np.minimum(d, sd_segment(x, y, 0.1, 0.12, 0.3, 0.4)[0] - 0.17)
    d = np.minimum(d, sd_circle(x, y, 0.34, 0.48, 0.22))
    d = np.minimum(d, sd_poly(x, y, [(0.5, 0.58), (0.82, 0.4), (0.5, 0.32)]))
    d = np.minimum(d, sd_poly(x, y, [(-0.3, -0.16), (-0.92, -0.55), (-0.8, -0.72), (-0.2, -0.42)]))
    d = np.minimum(d, sd_polyline(x, y, [(0.02, -0.3), (0.0, -0.86), (-0.16, -0.9)], 0.06))
    d = np.minimum(d, sd_polyline(x, y, [(0.2, -0.3), (0.24, -0.86), (0.4, -0.9)], 0.06))
    d = np.maximum(d, -sd_circle(x, y, 0.4, 0.52, 0.065))
    return np.maximum(d, -(sd_polyline(x, y, [(-0.36, 0.14), (0.04, -0.04), (0.3, -0.26)], 0.03)))


def g_water(x, y):
    d = np.full(np.shape(x), 9.0)
    for yc in (0.5, 0.0, -0.5):
        pts = [(-0.85 + i * 0.2833, yc + (0.14 if i % 2 == 0 else -0.14)) for i in range(7)]
        d = np.minimum(d, sd_polyline(x, y, pts, 0.085))
    return d


def g_feather(x, y):
    left, right, centre = [], [], []
    for t in np.linspace(0.18, 1.0, 14):
        yy = -0.95 + 1.85 * t
        cx = 0.3 * t ** 3 - 0.05
        w = 0.27 * math.sin(math.pi * min((t - 0.18) / 0.82, 1.0)) ** 0.55 + 0.02
        left.append((cx - w, yy))
        right.append((cx + w, yy))
        centre.append((cx, yy))
    d = sd_poly(x, y, left + right[::-1])
    d = np.maximum(d, -(sd_polyline(x, y, centre[1:9], 0.025)))
    return np.minimum(d, sd_segment(x, y, -0.05, -0.95, -0.05, -0.55)[0] - 0.06)


def g_sun(x, y):
    d = np.minimum(np.abs(sd_circle(x, y, 0, 0, 0.5)) - 0.1, sd_circle(x, y, 0, 0, 0.17))
    for k in range(8):
        a = k * math.pi / 4
        d = np.minimum(d, sd_segment(x, y, 0.72 * math.cos(a), 0.72 * math.sin(a),
                                     0.92 * math.cos(a), 0.92 * math.sin(a))[0] - 0.075)
    return d


def g_cobra(x, y):
    d = np.minimum(sd_ellipse(x, y, 0.05, 0.48, 0.27, 0.36), sd_circle(x, y, 0.05, 0.84, 0.13))
    d = np.minimum(d, sd_polyline(x, y, [(0.05, 0.2), (-0.32, -0.12), (0.2, -0.42), (-0.25, -0.72),
                                         (0.1, -0.9), (0.6, -0.86)], 0.1))
    return np.maximum(d, -(sd_segment(x, y, 0.05, 0.25, 0.05, 0.62)[0] - 0.035))


def g_djed(x, y):
    d = np.minimum(sd_box(x, y, 0, -0.3, 0.17, 0.62, 0.03), sd_box(x, y, 0, -0.88, 0.4, 0.08, 0.03))
    for yy in (0.1, 0.32, 0.54, 0.76):
        d = np.minimum(d, sd_box(x, y, 0, yy, 0.46, 0.065, 0.03))
    return d


def g_pyramid(x, y):
    d = np.abs(sd_poly(x, y, [(-0.88, -0.66), (0.88, -0.66), (0.0, 0.8)])) - 0.09
    d = np.minimum(d, sd_polyline(x, y, [(0.0, 0.8), (0.26, -0.66)], 0.07))
    return np.minimum(d, sd_box(x, y, 0, -0.86, 0.95, 0.06, 0.02))


def _leaf(x, y, bx, by, ang, length, width):
    c, s = math.cos(ang), math.sin(ang)
    dx, dy = x - bx, y - by
    lx, ly = c * dx + s * dy, -s * dx + c * dy     # rotate into leaf frame (leaf along +ly)
    pts = []
    ts = np.linspace(0, 1, 9)
    for t in ts:
        pts.append((-width * math.sin(math.pi * t) ** 0.8, t * length))
    for t in ts[::-1]:
        pts.append((width * math.sin(math.pi * t) ** 0.8, t * length))
    return sd_poly(lx, ly, pts)


def g_lotus(x, y):
    d = _leaf(x, y, 0, -0.45, 0.0, 1.3, 0.24)
    d = np.minimum(d, _leaf(x, y, 0, -0.45, 0.66, 1.0, 0.21))
    d = np.minimum(d, _leaf(x, y, 0, -0.45, -0.66, 1.0, 0.21))
    d = np.minimum(d, sd_ellipse(x, y, 0, -0.52, 0.44, 0.17))
    return np.minimum(d, sd_segment(x, y, 0, -0.6, 0, -0.95)[0] - 0.07)


def g_vase(x, y):
    d = sd_ellipse(x, y, 0, -0.25, 0.42, 0.52)
    d = np.minimum(d, sd_box(x, y, 0, 0.4, 0.14, 0.2))
    d = np.minimum(d, sd_box(x, y, 0, 0.64, 0.3, 0.07, 0.03))
    d = np.minimum(d, sd_box(x, y, 0, -0.82, 0.22, 0.08, 0.02))
    for sx in (-1, 1):
        d = np.minimum(d, np.abs(sd_circle(x, y, sx * 0.44, 0.12, 0.17)) - 0.06)
    return d


def g_crook(x, y):
    d = sd_segment(x, y, 0.2, -0.95, 0.2, 0.42)[0] - 0.1
    return np.minimum(d, sd_polyline(x, y, _arc(-0.08, 0.45, 0.28, 0.0, math.pi * 1.15, 10), 0.1))


def g_shen(x, y):
    d = np.abs(sd_circle(x, y, 0, 0.22, 0.5)) - 0.11
    d = np.minimum(d, sd_box(x, y, 0, -0.5, 0.62, 0.1, 0.03))
    return np.minimum(d, sd_poly(x, y, [(-0.22, -0.2), (0.22, -0.2), (0.3, -0.42), (-0.3, -0.42)]))


def g_owl(x, y):
    d = sd_ellipse(x, y, 0, -0.12, 0.44, 0.66)
    d = np.minimum(d, sd_poly(x, y, [(-0.42, 0.3), (-0.16, 0.5), (-0.4, 0.8)]))
    d = np.minimum(d, sd_poly(x, y, [(0.42, 0.3), (0.16, 0.5), (0.4, 0.8)]))
    for sx in (-1, 1):
        d = np.maximum(d, -(np.abs(sd_circle(x, y, sx * 0.19, 0.22, 0.14)) - 0.04))
        d = np.minimum(d, sd_segment(x, y, sx * 0.18, -0.74, sx * 0.2, -0.95)[0] - 0.06)
    return np.maximum(d, -sd_poly(x, y, [(-0.08, 0.06), (0.08, 0.06), (0.0, -0.12)]))


def g_star(x, y):
    pts = []
    for k in range(10):
        r = 0.95 if k % 2 == 0 else 0.4
        a = math.pi / 2 + k * math.pi / 5
        pts.append((r * math.cos(a), r * math.sin(a)))
    return sd_poly(x, y, pts)


GLYPHS = [g_eye, g_ankh, g_scarab, g_falcon, g_water, g_feather, g_sun, g_cobra,
          g_djed, g_pyramid, g_lotus, g_vase, g_crook, g_shen, g_owl, g_star]
GLYPH_NAMES = ["eye", "ankh", "scarab", "falcon", "water", "feather", "sun", "cobra",
               "djed", "pyramid", "lotus", "vase", "crook", "shen", "owl", "star"]


# ---------------------------------------------------------------------- cracks
def crack_tree(rng, n_main, r0, len_range, step, jitter, branch_p, w0, w1, max_depth=2):
    segs = []

    def grow(px, py, base, length, wa, wb, depth):
        s, ang = 0.0, base
        while s < length - 1e-6:
            st = min(step * rng.uniform(0.7, 1.25), length - s)
            ang = base + 0.55 * (ang - base) + rng.normal(0, jitter)
            nx, ny = px + math.cos(ang) * st, py + math.sin(ang) * st
            f0, f1 = s / length, (s + st) / length
            segs.append((px, py, nx, ny, wa + (wb - wa) * f0, wa + (wb - wa) * f1))
            if depth < max_depth and s > 0.12 * length and rng.random() < branch_p:
                side = 1 if rng.random() < 0.5 else -1
                grow(nx, ny, ang + side * rng.uniform(0.45, 0.9), (length - s) * rng.uniform(0.35, 0.65),
                     (wa + (wb - wa) * f1) * 0.8, wb * 0.8, depth + 1)
            px, py, s = nx, ny, s + st

    for k in range(n_main):
        a = TAU * k / n_main + rng.uniform(-0.25, 0.25)
        grow(math.cos(a) * r0, math.sin(a) * r0, a, rng.uniform(*len_range), w0 * rng.uniform(0.8, 1.15), w1, 0)
    return segs


def crack_field(n, segs, margin):
    """Union SDF of tapered capsules (negative inside) plus the local half-width."""
    x, y = grid(n)
    F = np.full((n, n), 9.0)
    Wd = np.zeros((n, n))
    for ax, ay, bx, by, wa, wb in segs:
        rad = math.hypot(bx - ax, by - ay) / 2 + max(wa, wb) + margin
        si, sj = stamp_window(n, (ax + bx) / 2, (ay + by) / 2, rad)
        d, h = sd_segment(x[si, sj], y[si, sj], ax, ay, bx, by)
        w = wa + (wb - wa) * h
        f = d - w
        better = f < F[si, sj]
        F[si, sj] = np.where(better, f, F[si, sj])
        Wd[si, sj] = np.where(better, w, Wd[si, sj])
    return F, Wd


# ------------------------------------------------------------------------ puffs
def puff_layer(n, blobs, cols, light=(-0.5, 0.62, 0.6), soft=0.03, k=0.07, erosion=0.0,
               seed=0, noise_amp=0.07, band_edges=(0.42, 0.7), band_soft=0.05):
    """Cartoon puff: overlapping sphere lobes, shaded into 3 painted bands."""
    x, y = grid(n)
    L = np.array(light) / np.linalg.norm(light)
    H = np.full((n, n), -9.0)
    NX, NY, NZ = np.zeros((n, n)), np.full((n, n), -0.35), np.full((n, n), 0.3)
    sd = np.full((n, n), 9.0)
    for cx, cy, r, z in blobs:
        dx, dy = x - cx, y - cy
        d2 = dx * dx + dy * dy
        hh = np.sqrt(np.maximum(r * r - d2, 0.0))
        upd = (d2 < r * r) & (hh + z > H)
        H = np.where(upd, hh + z, H)
        NX = np.where(upd, dx / r, NX)
        NY = np.where(upd, dy / r, NY)
        NZ = np.where(upd, hh / r, NZ)
        sd = smin(sd, np.sqrt(d2) - r, k)
    lam = (NX * L[0] + NY * L[1] + NZ * L[2]) / np.maximum(np.sqrt(NX * NX + NY * NY + NZ * NZ), 1e-6)
    v = 0.5 + 0.5 * lam + (fbm3(x * 2.6 + seed * 1.7, y * 2.6, 0.3 + seed, 3, seed) - 0.5) * noise_amp * 2
    col = bands(v, cols, band_edges, band_soft)
    er = fbm3(x * 3.1, y * 3.1 - seed * 0.37, 1.7 + seed * 0.11, 3, seed + 7)
    sde = sd + erosion * 0.06 + (er - 0.5) * 0.1 * (0.4 + erosion * 1.4)
    a = smoothstep(soft, -soft * 0.5, sde) * (0.85 + 0.15 * smoothstep(0.0, 0.15, -sde))
    return col, a


def fit_blobs(blobs, lim=0.9):
    ext = max(max(abs(b[0]) + b[2], abs(b[1]) + b[2]) for b in blobs) if blobs else 0
    if ext <= lim:
        return blobs
    s = lim / ext
    return [(b[0] * s, b[1] * s, b[2] * s, b[3] * s) for b in blobs]


def grains_layer(n, pts, cols):
    x, y = grid(n)
    c = np.zeros((n, n, 3))
    a = np.zeros((n, n))
    for gx, gy, gr, ci, ga in pts:
        if ga <= 0.01 or abs(gx) > 0.97 or abs(gy) > 0.97:
            continue
        si, sj = stamp_window(n, gx, gy, gr + 0.02)
        d = np.hypot(x[si, sj] - gx, y[si, sj] - gy) - gr
        cv = smoothstep(0.008, -0.004, d) * ga
        sub = a[si, sj]
        c[si, sj] = np.where((cv > sub)[..., None], cols[ci], c[si, sj])
        a[si, sj] = np.maximum(sub, cv)
    return c, a


def assemble(frames, g=4):
    n = frames[0][0].shape[0]
    c = np.zeros((n * g, n * g, 3))
    a = np.zeros((n * g, n * g))
    for i, (fc, fa) in enumerate(frames):
        r, q = divmod(i, g)
        c[r * n:(r + 1) * n, q * n:(q + 1) * n] = bleed(np.clip(fc, 0, 1), fa)
        a[r * n:(r + 1) * n, q * n:(q + 1) * n] = fa
    return c, a


def puff_sequence(n, seed, cols, count=7, spread=0.3, squash=1.0, rise=0.0, grow=(0.8, 1.0),
                  rad=(0.34, 0.46), alpha_max=0.95, fade=(0.35, 1.0), erosion_start=0.3, soft=0.03,
                  noise_amp=0.07, drift_x=0.0):
    rng = np.random.default_rng(seed)
    base = []
    for i in range(count):
        a = rng.uniform(0, TAU)
        d = spread * math.sqrt(rng.uniform(0.05, 1))
        base.append((math.cos(a) * d, math.sin(a) * d * squash, rng.uniform(*rad), rng.uniform(0.8, 1.25)))
    mask = edge_mask(n)
    frames = []
    for f in range(16):
        t = f / 15.0
        e = 1 - (1 - t) ** 2.4
        rs = grow[0] + (grow[1] - grow[0]) * e
        blobs = []
        for bx, by, br, spd in base:
            ps = 0.55 + 0.5 * e * spd
            cy = by * ps + rise * e
            r = br * rs * (1 - 0.2 * t)
            blobs.append((bx * ps + drift_x * e, cy, r, -cy * 0.15 * r))
        blobs = fit_blobs(blobs, 0.9)
        c, a = puff_layer(n, blobs, cols, soft=soft, erosion=smoothstep(erosion_start, 1.0, t),
                          seed=seed * 3 + f, noise_amp=noise_amp)
        alpha = alpha_max * (0.8 + 0.2 * smoothstep(0, 0.15, t)) * (1 - 0.93 * smoothstep(fade[0], fade[1], t))
        frames.append((c, a * alpha * mask))
    return assemble(frames)


# ==================================================================== painters
# Each returns (rgb HxWx3, alpha HxW[, already_bled]).

def paint_frost_floor(n=1024):
    rng = np.random.default_rng(7)
    x, y = grid(n)
    r, th = np.hypot(x, y), np.arctan2(y, x)
    rb = 0.8 + 0.1 * (fbm3(np.cos(th) * 1.6, np.sin(th) * 1.6, 0.5, 3, 5) - 0.5) * 2
    patch = smoothstep(rb, rb - 0.22, r)
    pts = rng.uniform(-0.95, 0.95, (44, 2))
    d1, d2 = np.full((n, n), 9.0), np.full((n, n), 9.0)
    cid = np.zeros((n, n), np.int64)
    for i, (px, py) in enumerate(pts):
        d = np.hypot(x - px, y - py)
        closer = d < d1
        d2 = np.where(closer, d1, np.minimum(d2, d))
        cid = np.where(closer, i, cid)
        d1 = np.where(closer, d, d1)
    plate = rng.uniform(-1, 1, len(pts))[cid] * 0.07
    seam = smoothstep(0.012, 0.0, d2 - d1)
    v = 0.55 + (fbm3(x * 2.4, y * 2.4, 1.3, 3, 9) - 0.5) * 0.55 + plate + 0.18 * smoothstep(0.5, 0.0, r)
    col = bands(v, [rgb(140, 190, 226), rgb(196, 226, 246), rgb(236, 247, 255)], [0.42, 0.62], 0.05)
    col = mix(col, rgb(250, 253, 255), seam * 0.35)
    segs = crack_tree(rng, 8, 0.05, (0.5, 0.72), 0.085, 0.35, 0.45, 0.013, 0.004)
    F, _ = crack_field(n, segs, 0.03)
    aa = 1.5 * 2 / n
    core = cov(F, aa)
    outline = cov(F - 0.007, aa) * (1 - core)
    col = mix(col, rgb(70, 128, 196), outline * 0.9)
    col = mix(col, rgb(252, 254, 255), core)
    col = mix(col, rgb(250, 253, 255), smoothstep(0.16, 0.0, r) * 0.55)
    a = np.maximum(patch * 0.92, np.maximum(core, outline) * smoothstep(0.95, 0.8, r))
    return col, a * smoothstep(0.995, 0.95, r)


def paint_frost_ring(n=1024):
    rng = np.random.default_rng(12)
    x, y = grid(n)
    r, th = np.hypot(x, y), np.arctan2(y, x)
    R, teeth = 0.84, 48
    hts = rng.uniform(0.012, 0.045, teeth)
    u = (th / TAU + 0.5) * teeth
    k = np.floor(u).astype(np.int64) % teeth
    fr = u - np.floor(u)
    edge_r = R + hts[k] * (1 - np.abs(2 * fr - 1))
    d = r - edge_r
    a_edge = np.where(d <= 0, np.exp(d / 0.014), smoothstep(0.004, 0.0, d))
    body = np.where(d <= 0, np.exp(d / 0.11), 0.0)
    v = (0.55 * fbm3(x * 6, y * 6, 0.2, 3, 3)
         + 0.45 * fbm3(np.cos(th) * 18, np.sin(th) * 18, r * 2.0, 2, 4))
    col = bands(v, [rgb(104, 176, 232), rgb(168, 218, 250), rgb(236, 250, 255)], [0.42, 0.6], 0.05)
    col = mix(col, rgb(255, 255, 255), np.where(d <= 0, np.exp(d / 0.02), 1.0))
    a = np.clip(np.maximum(a_edge, body * 0.9 * (0.75 + 0.25 * v)), 0, 1)
    return col, a * smoothstep(0.99, 0.95, r)


def paint_frost_mist(n=256):
    return puff_sequence(n, 11, [rgb(150, 196, 228), rgb(204, 230, 247), rgb(244, 251, 255)],
                         count=8, spread=0.34, squash=0.72, rise=0.08, alpha_max=0.82, soft=0.06,
                         noise_amp=0.06, fade=(0.3, 1.0), erosion_start=0.2) + (True,)


def paint_snow_sparkle(n=256):
    x, y = grid(n)
    r = np.hypot(x, y)
    pts = []
    for k in range(16):
        a = k * TAU / 16 + math.pi / 2
        rr = 0.9 if k % 4 == 0 else (0.46 if k % 4 == 2 else 0.11)
        pts.append((rr * math.cos(a), rr * math.sin(a)))
    star = cov(sd_poly(x, y, pts), 2.5 * 2 / n)
    core = np.exp(-(r / 0.16) ** 2)
    glow = np.exp(-(r / 0.42) ** 2) * 0.55
    col = mix(np.broadcast_to(rgb(180, 228, 255), (n, n, 3)).copy(), rgb(255, 255, 255), np.clip(star + core, 0, 1))
    return col, np.clip(np.maximum(star, glow) + core, 0, 1) * smoothstep(0.99, 0.9, r)


def paint_lava_cracks(n=1024):
    rng = np.random.default_rng(19)
    x, y = grid(n)
    r = np.hypot(x, y)
    segs = crack_tree(rng, 9, 0.07, (0.5, 0.84), 0.08, 0.4, 0.4, 0.028, 0.006)
    F, Wd = crack_field(n, segs, 0.08)
    aa = 1.5 * 2 / n
    depth = np.clip(-F / np.maximum(Wd, 1e-4), 0, 1)
    stops = [(0.0, rgb(255, 242, 160)), (0.18, rgb(255, 204, 72)), (0.38, rgb(255, 132, 26)),
             (0.62, rgb(220, 56, 18)), (0.9, rgb(116, 20, 10))]
    ramp = np.empty((n, n, 3))
    ramp[...] = stops[0][1]
    for (r0, _), (r1, c1) in zip(stops[:-1], stops[1:]):
        ramp = mix(ramp, c1, smoothstep(r0, r1, r))
    hot = mix(ramp, rgb(255, 246, 190), depth ** 1.5 * 0.55 * smoothstep(0.8, 0.2, r))
    c = np.zeros((n, n, 3))
    a = np.zeros((n, n))
    glow = 0.42 * np.exp(-np.maximum(F, 0) / 0.022) * smoothstep(0.95, 0.1, r)
    c, a = over(c, a, rgb(255, 120, 30), glow)
    rim = cov(F - 0.013, aa) * 0.88
    c, a = over(c, a, rgb(40, 20, 16), rim)
    core = cov(F, aa)
    c, a = over(c, a, hot, core)
    # impact crater: charred broken ring around a molten core
    rn = r + (fbm3(x * 9, y * 9, 0.4, 2, 23) - 0.5) * 0.05
    crater = smoothstep(0.15, 0.13, rn) * 0.92
    c, a = over(c, a, rgb(36, 18, 14), crater)
    pool = smoothstep(0.085, 0.07, rn)
    c, a = over(c, a, mix(np.broadcast_to(rgb(255, 150, 36), (n, n, 3)).copy(), rgb(255, 238, 150),
                          smoothstep(0.07, 0.0, r)), pool)
    return c, a * smoothstep(0.99, 0.94, r)


def paint_scorch_mark(n=512):
    rng = np.random.default_rng(29)
    x, y = grid(n)
    r, th = np.hypot(x, y), np.arctan2(y, x)
    rb = 0.74 + 0.1 * (fbm3(np.cos(th) * 1.8, np.sin(th) * 1.8, 0.2, 3, 31) - 0.5) * 2
    a = smoothstep(rb, rb * 0.42, r) ** 0.8 * 0.9
    v = fbm3(x * 2.8, y * 2.8, 0.7, 3, 33) + 0.25 * smoothstep(0.6, 0.0, r)
    col = bands(1 - v, [rgb(20, 16, 16), rgb(38, 28, 24), rgb(62, 44, 34)], [0.4, 0.58], 0.05)
    col = mix(col, rgb(84, 64, 50), smoothstep(0.55, 1.0, r / rb) * 0.4)   # ashy rim
    specks = []
    for i in range(18):
        ang, rad = rng.uniform(0, TAU), 0.62 * math.sqrt(rng.uniform(0.02, 1))
        specks.append((math.cos(ang) * rad, math.sin(ang) * rad, rng.uniform(0.006, 0.014),
                       int(rng.integers(0, 2)), 1.0))
    gc, ga = grains_layer(n, specks, [rgb(255, 150, 40), rgb(255, 214, 110)])
    col, a = over(col, a, gc, ga)
    return col, a * smoothstep(0.99, 0.93, r)


def _teardrop(base_y, height, width, phase, sway, curl, ripple, n=28):
    left, right = [], []
    for i in range(n + 1):
        s = i / n
        yv = base_y + s * height
        if s < 0.3:
            hw = width * math.sqrt(max(0.0, 1 - ((0.3 - s) / 0.3) ** 2))
        else:
            hw = width * ((1 - s) / 0.7) ** 1.25
        hw *= 1 + ripple * math.sin(s * 9.0 + phase * 2.0) * s
        cx = sway * math.sin(phase + s * 2.8) * s ** 1.2 + curl * s ** 3
        left.append((cx - hw, yv))
        right.append((cx + hw, yv))
    return left + right[::-1]


def paint_flame(n=256):
    x, y = grid(n)
    mask = edge_mask(n)
    aa = 2.2 * 2 / n
    cols = [rgb(214, 48, 28), rgb(250, 120, 26), rgb(255, 194, 64), rgb(255, 238, 160)]
    frames = []
    for f in range(16):
        t = f / 15.0
        sc = (0.45 + 0.55 * smoothstep(0, 0.22, t)) * (1 - 0.55 * smoothstep(0.62, 1, t))
        base_y = -0.82 + 0.5 * smoothstep(0.55, 1, t)
        Hh, Wd = 1.5 * sc, 0.42 * (0.6 + 0.4 * sc)
        ph = t * TAU * 1.1
        sway, curl = 0.13, 0.16 * math.sin(t * math.pi * 1.3)
        wob = (fbm3(x * 3.5, y * 3.5 - t * 2.0, 0.5, 2, 61) - 0.5) * 0.05
        side = 1 if (f // 4) % 2 == 0 else -1
        outer = sd_poly(x, y, _teardrop(base_y, Hh, Wd, ph, sway, curl, 0.12))
        lick = sd_poly(x - side * Wd * 0.55, y, _teardrop(base_y + 0.1 * Hh, Hh * 0.55, Wd * 0.5, ph + 1.7, sway, -curl, 0.1))
        outer = smin(outer, lick, 0.05)
        if 0.3 < t < 0.97:
            q = (t - 0.3) / 0.67
            sz = 0.2 * (1 - q)
            y0 = base_y + Hh * 0.92 + 0.08 + q * 0.4
            det = sd_poly(x - curl * 0.8, y, _teardrop(y0, sz * 1.6, sz * 0.45, ph + 2.5, 0.05, 0.02, 0.0, 16))
            outer = np.minimum(outer, det)
        layers = [outer + wob,
                  sd_poly(x, y, _teardrop(base_y + 0.02, Hh * 0.72, Wd * 0.68, ph + 0.3, sway * 0.8, curl * 0.7, 0.1)) + wob,
                  sd_poly(x, y, _teardrop(base_y + 0.05, Hh * 0.46, Wd * 0.42, ph + 0.6, sway * 0.6, curl * 0.4, 0.08)) + wob * 0.6,
                  sd_poly(x, y, _teardrop(base_y + 0.08, Hh * 0.24, Wd * 0.22, ph + 0.9, sway * 0.4, curl * 0.2, 0.0))]
        col = np.empty((n, n, 3))
        col[...] = cols[0]
        for lay, c in zip(layers[1:], cols[1:]):
            col = mix(col, c, cov(lay, aa * 0.8))
        a = cov(layers[0], aa) * (1 - 0.8 * smoothstep(0.75, 1, t))
        frames.append((col, a * mask))
    return assemble(frames) + (True,)


def paint_ember(n=128):
    x, y = grid(n)
    r = np.hypot(x, y)
    core = smoothstep(0.2, 0.08, r)
    mid = np.exp(-(r / 0.3) ** 2)
    glow = np.exp(-(r / 0.42) ** 2) * 0.7
    col = mix(np.broadcast_to(rgb(255, 112, 28), (n, n, 3)).copy(), rgb(255, 186, 64), mid)
    col = mix(col, rgb(255, 248, 200), core)
    return col, np.clip(glow + mid * 0.5 + core, 0, 1) * smoothstep(0.98, 0.85, r)


def paint_smoke(n=256):
    return puff_sequence(n, 23, [rgb(52, 50, 56), rgb(84, 82, 90), rgb(124, 122, 130)],
                         count=7, spread=0.28, squash=0.9, rise=0.18, alpha_max=0.95, soft=0.035) + (True,)


def paint_dust(n=256):
    return puff_sequence(n, 37, [rgb(160, 160, 160), rgb(204, 204, 204), rgb(238, 238, 238)],
                         count=8, spread=0.34, squash=0.62, rise=0.06, alpha_max=0.92, soft=0.035) + (True,)


GOLD, WHITEGOLD, LAPIS = rgb(248, 190, 62), rgb(255, 247, 214), rgb(28, 40, 104)


def paint_hieroglyph_circle(n=1024):
    x, y = grid(n)
    r = np.hypot(x, y)
    S = np.full((n, n), 9.0)
    for r0, hw in ((0.925, 0.026), (0.862, 0.008), (0.605, 0.008), (0.55, 0.016), (0.2, 0.009)):
        S = np.minimum(S, np.abs(r - r0) - hw)
    for k in range(40):
        a = k * TAU / 40
        cx, cy = 0.8835 * math.cos(a), 0.8835 * math.sin(a)
        si, sj = stamp_window(n, cx, cy, 0.03)
        S[si, sj] = np.minimum(S[si, sj], sd_circle(x[si, sj], y[si, sj], cx, cy, 0.0075))
    tri = [(0.52 * math.cos(a), 0.52 * math.sin(a)) for a in (math.pi / 2, math.pi / 2 + TAU / 3, math.pi / 2 + 2 * TAU / 3)]
    S = np.minimum(S, np.abs(sd_poly(x, y, tri)) - 0.008)
    s = 0.13
    S = np.minimum(S, g_eye(x / s, (y + 0.01) / s) * s)
    rm, gs = 0.735, 0.085
    for k in range(16):
        a = math.pi / 2 - k * TAU / 16
        cx, cy = rm * math.cos(a), rm * math.sin(a)
        si, sj = stamp_window(n, cx, cy, gs * 1.3)
        xs, ys = x[si, sj] - cx, y[si, sj] - cy
        lx = (xs * math.sin(a) - ys * math.cos(a)) / gs
        ly = (xs * math.cos(a) + ys * math.sin(a)) / gs
        S[si, sj] = np.minimum(S[si, sj], GLYPHS[k](lx, ly) * gs)
    aa = 1.6 * 2 / n
    stroke = cov(S, aa)
    core = smoothstep(0.0, 0.012, -S)
    outline = cov(S - 0.0075, aa) * (1 - stroke)
    glow = 0.42 * np.exp(-np.maximum(S, 0) / 0.02)
    wash = smoothstep(0.965, 0.94, r) * (0.2 + 0.1 * smoothstep(0.58, 0.62, r) * smoothstep(0.89, 0.85, r))
    c = np.zeros((n, n, 3))
    c[...] = LAPIS
    a = wash.copy()
    c, a = over(c, a, rgb(255, 214, 110), glow * (1 - outline))
    c, a = over(c, a, rgb(58, 34, 12), outline * 0.55)
    c, a = over(c, a, mix(np.broadcast_to(GOLD, (n, n, 3)).copy(), WHITEGOLD, core * 0.85), stroke)
    return c, a * smoothstep(0.995, 0.97, r)


def paint_hieroglyph_flipbook(n=256):
    x, y = grid(n)
    mask = edge_mask(n)
    aa = 1.5 * 2 / n
    frames = []
    for g in GLYPHS:
        s = 0.62
        S = g(x / s, y / s) * s
        stroke = cov(S, aa)
        core = smoothstep(0.0, 0.05, -S)
        col = mix(np.broadcast_to(rgb(255, 200, 80), (n, n, 3)).copy(),
                  mix(np.broadcast_to(GOLD, (n, n, 3)).copy(), WHITEGOLD, core), stroke)
        glow = 0.55 * np.exp(-np.maximum(S, 0) / 0.055)
        frames.append((col, np.maximum(stroke, glow) * mask))
    return assemble(frames) + (True,)


def paint_sand_burst(n=256):
    rng = np.random.default_rng(41)
    cols = [rgb(176, 128, 78), rgb(220, 176, 112), rgb(247, 222, 166)]
    colb = []
    for k in range(11):
        s = k / 10
        colb.append((rng.normal(0, 0.07) * (0.5 + s), s, 0.22 + 0.17 * s + rng.uniform(-0.015, 0.015),
                     rng.uniform(-1, 1)))
    grains = [(rng.normal(0, 0.45), rng.uniform(0.8, 1.5), rng.uniform(0.0, 0.3), rng.uniform(0.01, 0.022),
               int(rng.integers(0, 2))) for _ in range(46)]
    mask = edge_mask(n)
    frames = []
    for f in range(16):
        t = f / 15.0
        rise, spread, fall = smoothstep(0, 0.38, t), smoothstep(0.25, 1.0, t), smoothstep(0.5, 1.0, t)
        blobs = []
        for jx, s, r, side in colb:
            if s > rise * 1.05 + 0.02:
                continue
            yy = -0.8 + s * 1.3 * (0.6 + 0.4 * rise) - fall * 0.18 * s
            rr = r * (0.75 + 0.45 * spread) * (0.8 + 0.2 * rise)
            blobs.append((jx + side * spread * 0.5 * s, yy, rr, -yy * 0.1 * rr))
        blobs = fit_blobs(blobs, 0.92)
        c, a = puff_layer(n, blobs, cols, erosion=smoothstep(0.35, 1, t) * 0.95, seed=f + 3, soft=0.03)
        a = a * 0.97 * (1 - 0.9 * smoothstep(0.55, 1, t))
        gl = []
        for ang, spd, t0, r, ci in grains:
            if t < t0:
                continue
            dt = t - t0
            gl.append((math.sin(ang) * spd * dt * 0.9, -0.7 + math.cos(ang) * spd * dt * 1.4 - 1.6 * dt * dt, r, ci,
                       1 - smoothstep(0.45, 0.95, dt)))
        gc, ga = grains_layer(n, gl, [rgb(160, 112, 64), rgb(238, 206, 146)])
        c, a = over(c, a, gc, ga)
        frames.append((c, a * mask))
    return assemble(frames) + (True,)


def paint_curse_orb(n=256):
    x, y = grid(n)
    r, th = np.hypot(x, y), np.arctan2(y, x)
    aa = 2.0 * 2 / n
    col = np.empty((n, n, 3))
    col[...] = rgb(236, 255, 255)
    col = mix(col, rgb(110, 232, 246), smoothstep(0.08, 0.26, r))
    col = mix(col, rgb(28, 170, 214), smoothstep(0.26, 0.47, r))
    swirl = smoothstep(0.8, 0.95, np.sin(3 * th + r * 9.0)) * smoothstep(0.1, 0.2, r) * smoothstep(0.44, 0.34, r)
    col = mix(col, rgb(200, 250, 255), swirl * 0.55)
    ring = np.abs(r - 0.51) - 0.055
    lit = (x * -0.7 + y * 0.7) / np.maximum(r, 1e-6)
    gold = bands(0.5 + 0.5 * lit, [rgb(196, 128, 26), rgb(246, 186, 56), rgb(255, 234, 150)], [0.35, 0.72], 0.08)
    rc = cov(ring, aa)
    col = mix(col, gold, rc)
    outer = r > 0.56
    glow_col = mix(np.broadcast_to(rgb(255, 214, 110), (n, n, 3)).copy(), rgb(120, 236, 240), smoothstep(0.6, 0.85, r))
    col = np.where(outer[..., None] & (rc[..., None] < 0.5), glow_col, col)
    body = cov(r - 0.566, aa)
    glow = 0.6 * np.exp(-((np.maximum(r - 0.56, 0)) / 0.16) ** 2)
    return col, np.maximum(body, glow) * smoothstep(0.98, 0.9, r)


def paint_bubble(n=256):
    x, y = grid(n)
    r = np.hypot(x, y)
    R = 0.84
    aa = 2.0 * 2 / n
    inside = cov(r - R, aa)
    fres = 0.10 + 0.35 * smoothstep(R - 0.35, R, r)
    rim = np.exp(-((r - (R - 0.03)) / 0.035) ** 2) * 0.85
    diag = (x * -0.7 + y * 0.7) / np.maximum(r, 1e-6)
    cres = np.maximum(sd_circle(x, y, 0, 0, R - 0.07), -sd_circle(x, y, 0.07, -0.07, R - 0.1))
    cres = cov(cres, aa) * smoothstep(0.45, 0.7, diag)
    dot = cov(sd_circle(x, y, -0.42, 0.2, 0.065), aa)
    back = cov(np.maximum(sd_circle(x, y, 0, 0, R - 0.1), -sd_circle(x, y, -0.05, 0.05, R - 0.13)), aa)
    back = back * smoothstep(0.55, 0.8, -diag) * 0.45
    col = np.empty((n, n, 3))
    col[...] = rgb(150, 220, 246)
    col = mix(col, rgb(224, 248, 255), np.clip(rim * 1.2, 0, 1))
    hl = np.clip(cres + dot + back, 0, 1)
    col = mix(col, rgb(255, 255, 255), hl)
    a = np.maximum(np.maximum(fres * inside, rim), hl)
    return col, a * smoothstep(0.99, 0.93, r)


def paint_water_splash(n=256):
    rng = np.random.default_rng(67)
    x, y = grid(n)
    mask = edge_mask(n)
    aa = 1.6 * 2 / n
    spikes = [(-1.05, 0.55, 0.1), (-0.62, 0.8, 0.12), (-0.25, 0.95, 0.13), (0.03, 1.0, 0.13),
              (0.3, 0.9, 0.12), (0.66, 0.78, 0.11), (1.02, 0.52, 0.1)]
    drops = []
    for ang, lf, _ in spikes:
        for _ in range(2):
            drops.append((ang + rng.normal(0, 0.1), lf, rng.uniform(0.35, 0.7), rng.uniform(0.045, 0.075),
                          rng.uniform(0.2, 0.45)))
    base = (0.0, -0.6)
    frames = []
    for f in range(16):
        t = f / 15.0
        grow = 1 - (1 - min(t / 0.38, 1)) ** 2.5
        retract = smoothstep(0.42, 0.9, t)
        sd = np.full((n, n), 9.0)
        for ang, lf, wb in spikes:
            L = 0.95 * lf * grow * (1 - 0.75 * retract)
            if L < 0.03:
                continue
            dx, dy = math.sin(ang), math.cos(ang)
            tip = (base[0] + dx * L, base[1] + dy * L)
            px, py = dy, -dx
            w = wb * (1 - 0.5 * retract)
            rt = w * 0.42
            poly = [(base[0] + px * w, base[1] + py * w), (tip[0] + px * rt, tip[1] + py * rt),
                    (tip[0] - px * rt, tip[1] - py * rt), (base[0] - px * w, base[1] - py * w)]
            sd = smin(sd, np.minimum(sd_poly(x, y, poly), sd_circle(x, y, tip[0], tip[1], rt * 1.25)), 0.05)
        if t < 0.95:
            sd = smin(sd, sd_ellipse(x, y, 0, -0.64, 0.42 * (1 - 0.35 * retract) + 0.05,
                                     0.15 * (1 - 0.6 * retract) + 0.02), 0.08)
        for ang, lf, spd, r0, t0 in drops:
            if t < t0:
                continue
            dt = t - t0
            dx, dy = math.sin(ang), math.cos(ang)
            dist = 0.95 * lf + spd * dt
            px_, py_ = base[0] + dx * dist, base[1] + dy * dist - 1.2 * dt * dt
            rr = r0 * (1 - 0.75 * dt / max(1 - t0, 1e-6))
            vx, vy = dx * spd, dy * spd - 2.4 * dt
            rot = math.atan2(vy, vx) - math.pi / 2
            sd = np.minimum(sd, sd_ellipse(x, y, px_, py_, rr, rr * 1.35, rot=rot))
        gy, gx = np.gradient(sd)
        nx, ny = gx, -gy
        nl = np.maximum(np.hypot(nx, ny), 1e-9)
        ndl = (nx * -0.6 + ny * 0.8) / nl
        depth = np.clip(-sd / 0.07, 0, 1)
        rim = smoothstep(0.035, 0.0, -sd)
        col = np.empty((n, n, 3))
        col[...] = rgb(72, 186, 236)
        col = mix(col, rgb(160, 232, 252), smoothstep(0.3, 0.9, depth) * 0.7)
        col = mix(col, rgb(255, 255, 255), rim * smoothstep(0.1, 0.5, ndl))
        col = mix(col, rgb(38, 130, 204), rim * smoothstep(-0.1, -0.6, ndl))
        col = mix(col, rgb(250, 254, 255), smoothstep(-0.52, -0.7, y) * 0.75)
        a = cov(sd, aa) * (1 - 0.9 * smoothstep(0.7, 1, t))
        frames.append((col, a * mask))
    return assemble(frames) + (True,)


def paint_sand_spray(n=256):
    rng = np.random.default_rng(53)
    cols = [rgb(190, 156, 104), rgb(228, 202, 150), rgb(250, 236, 200)]
    arc = [(k / 8, rng.normal(0, 0.03), rng.normal(0, 0.03), rng.uniform(-0.015, 0.015)) for k in range(9)]
    grains = [(math.radians(rng.uniform(25, 70)), rng.uniform(0.8, 1.6), rng.uniform(0, 0.3),
               rng.uniform(0.01, 0.02), int(rng.integers(0, 2))) for _ in range(40)]
    mask = edge_mask(n)
    frames = []
    for f in range(16):
        t = f / 15.0
        prog, spread = smoothstep(0, 0.35, t), smoothstep(0.2, 1.0, t)
        blobs = []
        for s, jx, jy, jr in arc:
            if s > prog * 1.05 + 0.02:
                continue
            ss = s * (0.8 + 0.25 * spread)
            px_ = -0.62 + 1.2 * ss + jx
            py_ = -0.66 + 0.95 * ss - 0.42 * ss * ss + jy + 0.1 * spread * s
            rr = (0.2 + 0.15 * s + jr) * (0.8 + 0.45 * spread)
            blobs.append((px_, py_, rr, -py_ * 0.1 * rr))
        blobs = fit_blobs(blobs, 0.92)
        c, a = puff_layer(n, blobs, cols, erosion=smoothstep(0.35, 1, t) * 0.95, seed=f + 11, soft=0.03)
        a = a * 0.95 * (1 - 0.9 * smoothstep(0.55, 1, t))
        gl = []
        for ang, spd, t0, r, ci in grains:
            if t < t0:
                continue
            dt = t - t0
            gl.append((-0.55 + math.cos(ang) * spd * dt, -0.62 + math.sin(ang) * spd * dt - 1.5 * dt * dt, r, ci,
                       1 - smoothstep(0.45, 0.95, dt)))
        gc, ga = grains_layer(n, gl, [rgb(176, 140, 88), rgb(246, 228, 184)])
        c, a = over(c, a, gc, ga)
        frames.append((c, a * mask))
    return assemble(frames) + (True,)


def paint_shockwave_ring(n=1024):
    x, y = grid(n)
    r = np.hypot(x, y)
    d = r - 0.86
    a = np.where(d >= 0, smoothstep(0.016, 0.0, d), np.exp(d / 0.07)) * 0.95
    col = np.ones((n, n, 3))
    return col, a * smoothstep(0.99, 0.95, r)


def paint_impact_star(n=256):
    x, y = grid(n)
    r = np.hypot(x, y)
    pts = []
    for k in range(16):
        a = k * TAU / 16 + math.pi / 2
        rr = 0.95 if k % 4 == 0 else (0.62 if k % 4 == 2 else 0.3)
        pts.append((rr * math.cos(a), rr * math.sin(a)))
    star = cov(sd_poly(x, y, pts) + 0.025, 2.5 * 2 / n)
    halo = 0.3 * np.exp(-(r / 0.55) ** 2)
    col = mix(np.full((n, n, 3), 0.88), rgb(255, 255, 255), smoothstep(0.55, 0.1, r))
    return col, np.maximum(star, halo) * smoothstep(0.99, 0.92, r)


# name -> (painter, pixels, kind, layout)
TEXTURES = [
    ("FrostFloor.png", paint_frost_floor, 1024, "decal", None),
    ("FrostRing.png", paint_frost_ring, 1024, "decal", None),
    ("FrostMist_Flipbook4x4.png", paint_frost_mist, 1024, "flipbook", "4x4"),
    ("SnowSparkle.png", paint_snow_sparkle, 256, "sprite", None),
    ("LavaCracks.png", paint_lava_cracks, 1024, "decal", None),
    ("ScorchMark.png", paint_scorch_mark, 512, "decal", None),
    ("Flame_Flipbook4x4.png", paint_flame, 1024, "flipbook", "4x4"),
    ("Ember.png", paint_ember, 128, "sprite", None),
    ("SmokePuff_Flipbook4x4.png", paint_smoke, 1024, "flipbook", "4x4"),
    ("HieroglyphCircle.png", paint_hieroglyph_circle, 1024, "decal", None),
    ("Hieroglyphs_Flipbook4x4.png", paint_hieroglyph_flipbook, 1024, "flipbook", "4x4"),
    ("SandBurst_Flipbook4x4.png", paint_sand_burst, 1024, "flipbook", "4x4"),
    ("CurseOrb.png", paint_curse_orb, 256, "sprite", None),
    ("WaterSplash_Flipbook4x4.png", paint_water_splash, 1024, "flipbook", "4x4"),
    ("Bubble.png", paint_bubble, 256, "sprite", None),
    ("SandSpray_Flipbook4x4.png", paint_sand_spray, 1024, "flipbook", "4x4"),
    ("ShockwaveRing.png", paint_shockwave_ring, 1024, "decal", None),
    ("ImpactStar.png", paint_impact_star, 256, "sprite", None),
    ("DustPuff_Flipbook4x4.png", paint_dust, 1024, "flipbook", "4x4"),
]


def paint_all(out_dir, only=None, log=print):
    os.makedirs(out_dir, exist_ok=True)
    for name, fn, px, kind, layout in TEXTURES:
        if only and name not in only:
            continue
        res = fn()
        c, a = res[0], res[1]
        pre_bled = len(res) > 2 and res[2]
        assert c.shape[0] == px and c.shape[1] == px, (name, c.shape)
        save_rgba(os.path.join(out_dir, name), c, a, do_bleed=not pre_bled)
        log("painted %s (%dpx %s)" % (name, px, kind))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "textures")
    only = set(sys.argv[2:]) or None
    paint_all(out, only)
