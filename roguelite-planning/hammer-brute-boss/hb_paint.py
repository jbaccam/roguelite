"""Painterly albedo for the Hammer Brute, computed in numpy from baked passes.

Each section is baked once into geometric passes (REST world position, normal,
AO, bevel-edge factor, per-facet random, material id). The albedo is painted
texel by texel from those passes:
  - 2-4 broad value ranges per material (posterised world-space patches),
    per-facet tone shifts, light worn edges, soft cavity shading;
  - skin: the reference's mottled green with clustered dark speckles (two sizes,
    clustered by a low-frequency density field, never per-pixel grain) and red
    wound patches with dark cores and a few painterly drips;
  - the face (eye sockets, frown and cheek creases, skull-like nostrils, gums,
    the scar across the brow, the bleeding forehead wound) is PAINTED onto the
    shallow relief of the sculpt;
  - blood stains on the shirt and the hammer, grime toward hems.
No reference pixels are sampled. Colours are eyedropped values (PALETTE) times
the per-material CALIBRATION gains read from calibration.json.
"""
import math

import numpy as np

# ------------------------------------------------------------------ noise
_PERM = np.random.default_rng(20261003).permutation(4096).astype(np.int64)
_RAND = np.random.default_rng(7).random(4096)


def _hash(ix, iy, iz, seed):
    h = _PERM[(ix * 73856093 ^ iy * 19349663 ^ iz * 83492791 ^ seed * 2654435761) & 4095]
    return _RAND[h]


def value_noise(P, scale, seed=0):
    X = P * scale
    i = np.floor(X).astype(np.int64)
    f = X - i
    u = f * f * (3 - 2 * f)
    out = np.zeros(len(P))
    for dx in (0, 1):
        wx = u[:, 0] if dx else 1 - u[:, 0]
        for dy in (0, 1):
            wy = u[:, 1] if dy else 1 - u[:, 1]
            for dz in (0, 1):
                wz = u[:, 2] if dz else 1 - u[:, 2]
                out += wx * wy * wz * _hash(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz, seed)
    return out


def fbm(P, scale, octaves=3, seed=0, gain=0.5):
    tot = np.zeros(len(P))
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        tot += amp * value_noise(P, scale * (2.0 ** o), seed + 17 * o)
        norm += amp
        amp *= gain
    return tot / norm


def cell_spots(P, scale, seed, jitter=0.8):
    """Distance (in cells) to the nearest random feature point: round spots with
    irregular spacing (a cheap 3D Worley)."""
    X = P * scale
    i = np.floor(X).astype(np.int64)
    best = np.full(len(P), 9.0)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = i + np.array([dx, dy, dz])
                fp = np.stack([_hash(c[:, 0], c[:, 1], c[:, 2], seed + k) for k in range(3)], 1)
                fp = c + 0.5 + (fp - 0.5) * jitter
                best = np.minimum(best, np.linalg.norm(X - fp, axis=1))
    return best


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def posterize(x, levels, soft=0.08):
    y = x * levels
    fl = np.floor(y)
    fr = y - fl
    return (fl + smoothstep(0.5 - soft * levels, 0.5 + soft * levels, fr)) / levels


def srgb_to_lin(c):
    c = np.asarray(c, float) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def mix(a, b, t):
    t = np.asarray(t)[..., None] if np.ndim(t) else t
    return a + (b - a) * t


# ---------------------------------------------------------------- palette
PALETTE = {
    'skin':     {'base': (118, 168, 62), 'dark': (84, 128, 42), 'light': (150, 196, 84), 'edge': (170, 212, 104),
                 'speck': (40, 70, 22), 'wound': (150, 30, 28), 'wound_dark': (64, 8, 10), 'socket': (20, 24, 18),
                 'mouth': (36, 12, 14), 'gum': (146, 58, 62), 'crease': (58, 94, 36), 'scar': (128, 150, 82)},
    'tooth':    {'base': (222, 214, 190), 'dark': (172, 160, 136), 'light': (238, 232, 214), 'edge': (246, 242, 228)},
    'shirt':    {'base': (190, 176, 152), 'dark': (142, 128, 106), 'light': (212, 200, 176), 'edge': (224, 214, 194),
                 'dirt': (128, 104, 78), 'blood': (132, 30, 28), 'blood_dark': (70, 12, 14)},
    'strap':    {'base': (88, 60, 44), 'dark': (58, 38, 28), 'light': (110, 78, 58), 'edge': (138, 104, 80)},
    'buckle':   {'base': (150, 148, 152), 'dark': (96, 94, 100), 'light': (182, 180, 184), 'edge': (222, 220, 222)},
    'iron':     {'base': (88, 82, 86), 'dark': (60, 56, 60), 'light': (110, 104, 106), 'edge': (172, 166, 162),
                 'blood': (122, 26, 26), 'blood_dark': (80, 14, 16)},
    'sash':     {'base': (100, 28, 38), 'dark': (66, 16, 26), 'light': (126, 44, 52), 'edge': (146, 64, 70)},
    'trousers': {'base': (62, 66, 80), 'dark': (42, 45, 56), 'light': (84, 89, 104), 'edge': (104, 108, 122),
                 'rim': (32, 34, 42)},
    'wood':     {'base': (104, 62, 38), 'dark': (70, 40, 26), 'light': (130, 82, 52), 'edge': (148, 100, 66)},
    'band':     {'base': (72, 64, 68), 'dark': (48, 42, 46), 'light': (94, 86, 88), 'edge': (146, 138, 136)},
    'eye':      {'base': (250, 250, 246)},
}
MAT_IDS = ['skin', 'tooth', 'shirt', 'strap', 'iron', 'sash', 'trousers', 'wood', 'band', 'eye', 'buckle']


def col(key, name, gains):
    g = np.asarray(gains.get(key, (1, 1, 1)), float)
    return np.clip(srgb_to_lin(PALETTE[key][name]) * g, 0, 1)


def tile(c, n):
    return np.tile(c, (n, 1))


def paint_generic(key, P, ao, edge, facet, gains, seed, streak_axis=None, patch_scale=0.8, contrast=1.0,
                  facet_amp=0.16, cavity=0.35, edge_amt=0.45, levels=3):
    """Shared painterly recipe: per-facet value, 2-4 posterised broad value
    ranges, soft dabs, light worn edges, cavity darkening."""
    n = len(P)
    base, dark, light, edgec = (col(key, k, gains) for k in ('base', 'dark', 'light', 'edge'))
    Q = P
    if streak_axis is not None:
        a = np.asarray(streak_axis, float)
        a = a / np.linalg.norm(a)
        along = P @ a
        Q = P - np.outer(along, a) + np.outer(along * 0.15, a)
    out = tile(base, n)
    f = (facet - 0.5) * 2.0
    out = mix(out, tile(light, n), np.clip(f, 0, 1) * facet_amp * 2.6 * contrast)
    out = mix(out, tile(dark, n), np.clip(-f, 0, 1) * facet_amp * 2.0 * contrast)
    # broad value ranges (posterised so they read as painted patches, not noise)
    broad = posterize(fbm(Q, patch_scale, 3, seed), levels, soft=0.06)
    out = mix(out, tile(light, n), np.clip(broad - 0.5, 0, 1) * 0.55 * contrast)
    out = mix(out, tile(dark, n), np.clip(0.5 - broad, 0, 1) * 0.65 * contrast)
    dab = smoothstep(0.60, 0.68, fbm(Q, patch_scale * 3.2, 2, seed + 5))
    out = mix(out, tile(light, n), dab * 0.18 * contrast)
    e = smoothstep(0.12, 0.5, edge) * smoothstep(0.5, 0.9, ao)
    out = mix(out, tile(edgec, n), e * edge_amt)
    out *= (1.0 - cavity + cavity * smoothstep(0.10, 0.85, ao))[:, None]
    return out


# ------------------------------------------------------------------ marks
def blotch(P, c, n, size, seed, ragged=0.55):
    """Signed distance-ish (studs) to an irregular blotch centred on the surface
    point c with normal n: negative inside."""
    v = P - c
    d = np.linalg.norm(v - np.outer(v @ n, n), axis=1)
    off = np.abs(v @ n)
    a = np.arctan2(v @ _ortho(n)[0], v @ _ortho(n)[1])
    rnd = np.random.default_rng(seed)
    wob = np.zeros(len(P))
    for k in (3, 5, 7, 11):
        wob += rnd.uniform(0.3, 1.0) * np.sin(k * a + rnd.uniform(0, 6.28)) / k * 3
    r = size * (1 + ragged * wob / 3)
    return d - r + np.where(off > size * 1.5, 9.0, 0.0)


def _ortho(n):
    n = np.asarray(n, float)
    a = np.array([0, 0, 1.0]) if abs(n[2]) < 0.9 else np.array([1.0, 0, 0])
    u = np.cross(n, a)
    u /= np.linalg.norm(u)
    return u, np.cross(n, u)


def drips(P, c, n, ddir, length, width, seed, count=4):
    """0..1 coverage of a few painterly drips running from c along ddir on the surface."""
    ddir = np.asarray(ddir, float)
    ddir = ddir - n * (ddir @ n)
    ddir /= np.linalg.norm(ddir)
    side = np.cross(n, ddir)
    v = P - c
    along = v @ ddir
    lat = v @ side
    off = np.abs(v @ n)
    rnd = np.random.default_rng(seed)
    cov = np.zeros(len(P))
    for i in range(count):
        x0 = rnd.uniform(-1, 1) * width * 1.6
        L = length * rnd.uniform(0.45, 1.0)
        w = width * rnd.uniform(0.35, 0.7)
        t = np.clip(along / L, 0, 1)
        ww = w * (1 - 0.55 * t) + 0.02
        inside = (along > 0) & (along < L + ww) & (off < 0.6)
        dl = np.abs(lat - x0 - 0.04 * np.sin(along * 7 + i))
        cov = np.maximum(cov, inside * smoothstep(ww, ww * 0.6, dl))
        # rounded drop at the end
        dd = np.hypot(lat - x0, along - L)
        cov = np.maximum(cov, (off < 0.6) * smoothstep(ww * 1.35, ww * 0.9, dd))
    return cov


def torn_mark(P, c, n, size, seed, aspect=1.4):
    """Signed distance-ish (studs) to an irregular torn patch: anisotropic, rotated,
    with spiky ragged edges (several angular frequencies + a domain warp)."""
    rnd = np.random.default_rng(seed)
    u, w = _ortho(n)
    ang = rnd.uniform(0, np.pi)
    a_ax = np.cos(ang) * u + np.sin(ang) * w
    b_ax = np.cross(n, a_ax)
    v = P - c
    off = np.abs(v @ n)
    warp = (fbm(P, 6.0, 2, seed + 3) - 0.5) * size * 0.9
    a = v @ a_ax / aspect + warp
    b = v @ b_ax + (fbm(P, 6.0, 2, seed + 7) - 0.5) * size * 0.9
    r = np.hypot(a, b)
    th = np.arctan2(b, a)
    rim = np.zeros(len(P))
    for k, amp in ((3, 0.22), (5, 0.18), (8, 0.14), (13, 0.10)):
        rim += amp * np.abs(np.sin(k * th / 2 + rnd.uniform(0, 6.28))) ** 1.5
    edge = size * (0.70 + rim)
    return r - edge + np.where(off > size * 1.6, 9.0, 0.0)


def paint_wounds(out, P, gains, wounds, key='skin', strength=1.0):
    """Torn wounds / stains: a ragged red patch, a darker torn centre, and a few
    drips of varied length. wounds: (c, n, drip_dir, size, drip_len, seed[, aspect])."""
    n = len(P)
    red = col(key, 'wound' if key == 'skin' else 'blood', gains)
    dred = col(key, 'wound_dark' if key == 'skin' else 'blood_dark', gains)
    for wnd in wounds:
        c, nrm, ddir, size, dl, seed = wnd[:6]
        aspect = wnd[6] if len(wnd) > 6 else 1.0 + (seed % 5) * 0.18
        near = np.linalg.norm(P - c, axis=1) < size * 3 + dl + 0.3
        if not near.any():
            continue
        Pn = P[near]
        b = torn_mark(Pn, c, nrm, size, seed, aspect)
        core = torn_mark(Pn, c, nrm, size * 0.42, seed + 1, aspect * 0.8)
        cov = smoothstep(0.015, -0.015, b)
        drp = drips(Pn, c, nrm, ddir, dl, size * 0.4, seed + 2, count=1 + seed % 3) if dl > 0 else 0
        o = out[near]
        o = mix(o, tile(red, len(Pn)), np.maximum(cov, drp * 0.85) * strength)
        o = mix(o, tile(dred, len(Pn)), smoothstep(0.02, -0.03, core) * 0.9 * strength)
        out[near] = o
    return out


def speckles(P, seed, density_scale=0.5, small=6.5, medium=3.2, amount=1.0):
    """Clustered dark speckles: two spot sizes of irregular blotchy shape (the
    lookup is domain-warped), gated by a slow density field."""
    dens = smoothstep(0.30, 0.75, fbm(P, density_scale, 2, seed))
    warp = np.stack([fbm(P, 9.0, 2, seed + 21 + k) - 0.5 for k in range(3)], 1) * 0.07
    Pw = P + warp
    s1 = cell_spots(Pw, small, seed + 3)
    s2 = cell_spots(Pw, medium, seed + 7)
    r1 = 0.18 + 0.15 * value_noise(P, small * 0.5, seed + 9)
    r2 = 0.14 + 0.14 * value_noise(P, medium * 0.5, seed + 11)
    spot = np.maximum(smoothstep(r1 + 0.05, r1, s1) * (0.35 + 0.65 * dens), smoothstep(r2 + 0.04, r2, s2) * dens)
    return np.clip(spot * amount, 0, 1)


# ------------------------------------------------------------------- skin
def _line_dist(q, pts):
    """Distance in the (x, z) plane to a polyline."""
    pts = np.asarray(pts, float)
    best = np.full(len(q), 9.0)
    for a, b in zip(pts[:-1], pts[1:]):
        ab = b - a
        t = np.clip(((q - a) @ ab) / (ab @ ab), 0, 1)
        best = np.minimum(best, np.linalg.norm(q - (a + t[:, None] * ab), axis=1))
    return best


def paint_face(out, P, N, gains, head_c, eye_centres, socket_r=0.31):
    """Painted face details in head-local (REST) coordinates: sockets, frown and
    cheek creases, skull nostrils, scar, mouth interior and gums."""
    n = len(P)
    hl = P - head_c
    front = smoothstep(-0.2, -0.75, N[:, 1]) * (hl[:, 1] < -0.6)
    q = hl[:, [0, 2]]
    sock = col('skin', 'socket', gains)
    for ec in eye_centres:
        e = ec - head_c
        d = np.hypot((hl[:, 0] - e[0]) / 1.0, (hl[:, 2] - e[2]) / 0.78)
        # dark socket shadow under the brow, heavier toward the nose and the brow
        inner = smoothstep(0.0, 0.25, -np.sign(e[0]) * (hl[:, 0] - e[0]))
        rr = socket_r * (1 + 0.20 * smoothstep(0.0, 0.2, hl[:, 2] - e[2]) + 0.10 * inner)
        out = mix(out, tile(sock, n), smoothstep(rr + 0.04, rr - 0.03, d) * front)
    crease = col('skin', 'crease', gains)
    lines = [
        # forehead furrows (angry, dipping toward the centre)
        [(-0.62, 0.92), (-0.30, 0.84), (0.0, 0.78), (0.30, 0.84), (0.62, 0.92)],
        [(-0.50, 1.07), (-0.20, 1.00), (0.10, 0.99), (0.45, 1.06)],
        # frown lines between the brows
        [(-0.10, 0.62), (-0.06, 0.40)], [(0.10, 0.62), (0.06, 0.40)],
        # under-eye bags
        [(-0.70, -0.20), (-0.45, -0.28), (-0.22, -0.20)], [(0.22, -0.20), (0.45, -0.28), (0.70, -0.20)],
        # snarl creases from the nose wings to the mouth corners
        [(-0.22, -0.30), (-0.50, -0.50), (-0.82, -0.80)], [(0.22, -0.30), (0.50, -0.50), (0.82, -0.80)],
        # cheek creases
        [(-0.80, -0.30), (-0.86, -0.62)], [(0.80, -0.30), (0.86, -0.62)],
    ]
    for pts in lines:
        d = _line_dist(q, pts)
        out = mix(out, tile(crease, n), smoothstep(0.045, 0.012, d) * front * 0.85)
    # skull-like nostrils: a dark inverted V on the nose tip
    nose = [(-0.13, -0.42), (0.0, -0.24), (0.13, -0.42)]
    d = _line_dist(q, nose)
    out = mix(out, tile(sock, n), smoothstep(0.06, 0.03, d) * front)
    for s in (-1, 1):
        dn = np.hypot(hl[:, 0] - s * 0.075, hl[:, 2] + 0.37)
        out = mix(out, tile(sock, n), smoothstep(0.065, 0.04, dn) * front)
    # scar across the brow (lighter, slightly raised-looking line with a dark edge)
    scar = [(-0.70, 0.62), (-0.35, 0.46), (-0.15, 0.30)]
    d = _line_dist(q, scar)
    out = mix(out, tile(col('skin', 'wound_dark', gains), n), smoothstep(0.05, 0.03, d) * front * 0.5)
    out = mix(out, tile(col('skin', 'scar', gains), n), smoothstep(0.03, 0.012, d) * front)
    return out


def paint_mouth(out, P, gains, mouth_prims, head_union):
    """The snarl's inside, by depth below the UNcarved head surface: a dull gum band
    just inside the lips (where the teeth root), then near-black. Lips stay skin."""
    from hb_sdf import eval_prims
    n = len(P)
    dark = col('skin', 'mouth', gains)
    gum = col('skin', 'gum', gains)
    near = np.min([p.sdf(P) for p in mouth_prims], axis=0) < 0.04
    depth = np.zeros(n)
    if near.any():
        depth[near] = -eval_prims(head_union, P[near])
    out = mix(out, tile(gum * 0.45, n), smoothstep(0.02, 0.04, depth) * near)
    out = mix(out, tile(dark, n), smoothstep(0.045, 0.085, depth) * near)
    return out


def paint_skin(P, N, ao, edge, facet, gains, ctx):
    n = len(P)
    out = paint_generic('skin', P, ao, edge, facet, gains, 1, patch_scale=0.55, facet_amp=0.30, cavity=0.45,
                        edge_amt=0.30, levels=3)
    # mottling: broad yellow-green and deep green patches (the reference's 3 value ranges)
    mot = posterize(fbm(P, 0.9, 3, 77), 3, soft=0.05)
    out = mix(out, tile(col('skin', 'light', gains), n), np.clip(mot - 0.55, 0, 1) * 0.9)
    out = mix(out, tile(col('skin', 'dark', gains), n), np.clip(0.45 - mot, 0, 1) * 0.9)
    # painted light: lighter top planes, darker side/under planes (the reference paints its light in)
    out *= (1.0 + 0.16 * smoothstep(0.25, 0.85, N[:, 2]) - 0.12 * smoothstep(-0.05, -0.75, N[:, 2]))[:, None]
    sp = speckles(P, 31, amount=ctx.get('speck', 1.15))
    out = mix(out, tile(col('skin', 'speck', gains), n), np.clip(sp * 0.95, 0, 1))
    if 'eyes' in ctx:
        out = paint_face(out, P, N, gains, ctx['head_c'], ctx['eyes'])
    if 'mouth' in ctx:
        out = paint_mouth(out, P, gains, ctx['mouth'], ctx['head_union'])
    out = paint_wounds(out, P, gains, ctx.get('wounds', []))
    return out


def paint_tooth(P, ao, edge, facet, gains):
    n = len(P)
    out = paint_generic('tooth', P, ao, edge, facet, gains, 9, patch_scale=3.0, facet_amp=0.10, cavity=0.55,
                        edge_amt=0.3, levels=2)
    stain = smoothstep(0.55, 0.75, fbm(P, 9.0, 2, 13))
    out = mix(out, tile(np.array([0.42, 0.33, 0.16]), n), stain * 0.35)
    return out


def paint_shirt(P, ao, edge, facet, gains, ctx):
    n = len(P)
    out = paint_generic('shirt', P, ao, edge, facet, gains, 21, patch_scale=0.8, facet_amp=0.12, cavity=0.30,
                        edge_amt=0.25, levels=3)
    dirt = col('shirt', 'dirt', gains)
    grime = smoothstep(0.45, 0.70, fbm(P, 0.9, 3, 23))
    out = mix(out, tile(dirt, n), grime * 0.55)
    rim = ctx.get('rim')
    if rim is not None:
        out = mix(out, tile(dirt, n), smoothstep(0.30, 0.0, -rim) * 0.6)
    sp = speckles(P, 25, density_scale=0.7, small=8.0, medium=4.0, amount=0.35)
    out = mix(out, tile(dirt * 0.6, n), sp * 0.5)
    out = paint_wounds(out, P, gains, ctx.get('stains', []), key='shirt')
    return out


def paint_iron(P, ao, edge, facet, gains, ctx, hammer=False, N=None):
    n = len(P)
    out = paint_generic('iron', P, ao, edge, facet, gains, 51, patch_scale=1.1, facet_amp=0.10, cavity=0.30,
                        edge_amt=0.75 if hammer else 0.55, levels=3)
    pits = speckles(P, 53, density_scale=0.8, small=12.0, medium=6.0, amount=0.5)
    out = mix(out, tile(col('iron', 'dark', gains), n), pits * 0.5)
    if N is not None and 'axes' in ctx:
        # the chamfers read as worn, lighter iron (as in the reference)
        A = np.asarray(ctx['axes'])
        al = np.max(np.abs(N @ A), axis=1)
        cham = smoothstep(0.95, 0.85, al)
        out = mix(out, tile(col('iron', 'edge', gains), n), cham * 0.62)
    if hammer:
        # worn surface: broad darker recesses and lighter rubbed patches (no grain noise)
        wear = posterize(fbm(P, 0.9, 3, 57), 3, soft=0.06)
        out = mix(out, tile(col('iron', 'light', gains), n), np.clip(wear - 0.6, 0, 1) * 0.9)
        out = mix(out, tile(col('iron', 'dark', gains), n), np.clip(0.45 - wear, 0, 1) * 1.2)
        out = paint_wounds(out, P, gains, ctx.get('stains', []), key='iron', strength=0.95)
        if 'face' in ctx:
            # blood coating the striking face and its rim, smeared and running off its edges
            fc, fn, fup = ctx['face']
            h = (P - fc) @ fn                       # height above the face plane (negative = behind)
            band = smoothstep(-0.55, -0.05, h) * (1 - smoothstep(0.02, 0.06, np.abs(np.minimum(h, 0) * 0)))
            rag = fbm(P, 4.0, 2, 61)
            reach = 0.25 + 0.75 * smoothstep(0.35, 0.8, fbm(P, 2.5, 2, 63)) * smoothstep(0.55, 0.7, value_noise(P * np.array([1, 1, 1]), 6.0, 65))
            smear = smoothstep(-(0.15 + reach * 0.9), -0.05, h + (rag - 0.5) * 0.25)
            out = mix(out, tile(col('iron', 'blood', gains), n), smear * 0.85)
            out = mix(out, tile(col('iron', 'blood_dark', gains), n), smoothstep(-0.12, -0.0, h) * 0.7)
    return out


def paint_wood(P, ao, edge, facet, gains, axis):
    n = len(P)
    out = paint_generic('wood', P, ao, edge, facet, gains, 61, streak_axis=axis, patch_scale=1.2, facet_amp=0.10,
                        contrast=1.1, cavity=0.35, edge_amt=0.35, levels=3)
    a = np.asarray(axis, float)
    a /= np.linalg.norm(a)
    side = np.cross(a, [0, 0, 1.0] if abs(a[2]) < 0.9 else [1.0, 0, 0])
    grain = fbm(np.stack([P @ a * 0.6, P @ side * 9.0, P @ np.cross(a, side) * 9.0], 1), 1.0, 2, 63)
    out = mix(out, tile(col('wood', 'dark', gains), n), smoothstep(0.55, 0.70, grain) * 0.45)
    return out


def fill_uncovered(img, cov):
    if cov.any():
        img[~cov] = img[cov].mean(0)
    return img
