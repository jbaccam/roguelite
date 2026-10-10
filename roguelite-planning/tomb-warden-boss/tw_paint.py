"""Painterly albedo for the Tomb Warden, computed in numpy from baked passes
(rest-pose position, normal, AO, bevel-edge factor, per-facet random).

Broad 2-4 value patches in world space (constant scale in studs), per-facet
tone shifts, soft worn edges, cavity darkening and sparse grunge. Bandage
wraps use the same helical band coordinates as the geometry so the painted
overlap shadows sit exactly under the sculpted lips. No photo textures.
"""
import numpy as np

import tw_design as D

_PERM = np.random.default_rng(20261009).permutation(4096).astype(np.int64)
_RAND = np.random.default_rng(11).random(4096)


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


def noise1(x, seed=0):
    i = np.floor(x).astype(np.int64)
    f = x - i
    u = f * f * (3 - 2 * f)
    a = _RAND[_PERM[(i * 2654435761 + seed * 97) & 4095]]
    b = _RAND[_PERM[((i + 1) * 2654435761 + seed * 97) & 4095]]
    return a + (b - a) * u


def fbm(P, scale, octaves=3, seed=0, gain=0.5):
    tot = np.zeros(len(P))
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        tot += amp * value_noise(P, scale * (2.0 ** o), seed + 17 * o)
        norm += amp
        amp *= gain
    return tot / norm


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def srgb_to_lin(c):
    c = np.asarray(c, float) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def mix(a, b, t):
    t = np.asarray(t, float)
    if t.ndim:
        t = t[:, None]
    return a + (b - a) * t


PAL = {
    # warm, saturated on purpose: Studio's blue sky ambient + ColorCorrection (+0.3 sat) cools and greys pale tones
    'cream': (238, 214, 162), 'sand': (206, 160, 96), 'tan': (176, 122, 64), 'shadow': (128, 84, 44),
    'grime': (156, 112, 66),
    'flap': (228, 204, 156), 'flap_stain': (196, 152, 92),
    'teal': (56, 130, 118), 'teal_dark': (32, 90, 86), 'teal_light': (104, 164, 146), 'teal_dust': (196, 170, 120),
    'stone': (200, 108, 52), 'stone_light': (228, 150, 82), 'stone_dark': (138, 68, 34), 'stone_edge': (240, 182, 112),
    'stone_groove': (110, 52, 26), 'stone_fresh': (238, 192, 128),
    'cavity': (26, 14, 8), 'cavity_warm': (130, 54, 10),
    'eye': (255, 168, 30), 'eye_core': (255, 232, 130),
}


def C(name):
    return srgb_to_lin(PAL[name])


def _shade(c, ao, edge, facet, facet_amp=0.06, cavity=0.35, edge_amt=0.10):
    v = 1.0 + facet_amp * (facet - 0.5) * 2.0
    v *= 1.0 - cavity * (1.0 - np.clip(ao, 0, 1)) ** 1.4
    out = c * v[:, None]
    return mix(out, out * 1.25 + 0.02, np.clip(edge, 0, 1) * edge_amt / 0.10 * 0.5)


# --------------------------------------------------------------- bandage
def paint_bandage(P, N, ao, edge, facet, groups):
    """Two-tone weathered linen on crossing diagonal wraps: each wrap strip is cream or tan, the
    top strip's lower lip casts a shade line, overlap edges where one family crosses over the
    other read as darker seams, broad tan/brown stains on top."""
    n = len(P)
    out = np.zeros((n, 3))
    cream, sand, tan, shadow = C('cream'), C('sand'), C('tan'), C('shadow')
    for g in np.unique(groups):
        sel = groups == g
        Pg = P[sel]
        pA, pBe, topA, sA, sB = D.wrap_layers(Pg, g)
        has_band = g in D.BAND_GROUPS
        s_top = np.where(topA, sA, sB)
        f = s_top - np.floor(s_top)
        k = np.floor(s_top).astype(np.int64) + np.where(topA, 0, 7919) + (sum(map(ord, g)) % 97)
        tk = _RAND[_PERM[(k * 2654435761) & 4095]]
        # sandy two-tone: each wide band is cream or sand, with broad low-frequency mottling across bands
        along = fbm(Pg, 0.45, 2, seed=3)
        t = np.clip(0.80 * (tk > 0.45) + 0.55 * (along - 0.5), 0, 1)
        base = mix(mix(cream, sand, 0.12), mix(sand, tan, 0.30), t)
        mott = smoothstep(0.40, 0.68, fbm(Pg, 0.75, 3, seed=7))
        base = mix(base, mix(sand, tan, 0.25), 0.50 * mott)
        # tea-brown stains in soft patches, darker at their cores
        st = smoothstep(0.54, 0.72, fbm(Pg, 0.6, 3, seed=5))
        base = mix(base, tan, 0.80 * st)
        base = mix(base, shadow, 0.40 * smoothstep(0.68, 0.84, fbm(Pg, 0.6, 3, seed=5)))
        dab = fbm(Pg, 1.6, 2, seed=9)
        base = base * (0.94 + 0.12 * dab)[:, None]
        if has_band:
            # one clean overlap edge per band: shade tucked under the band above, a lit lip on top of it
            sh = smoothstep(0.86, 0.99, f)
            base = mix(base, shadow, 0.50 * sh)
            hl = smoothstep(0.02, 0.08, f) * (1 - smoothstep(0.10, 0.22, f))
            base = mix(base, cream * 1.05, 0.30 * hl)
            seam = (1 - smoothstep(0.0, 0.05, np.abs(pA - pBe))) * (pBe > 0.5)
            base = mix(base, shadow, 0.35 * seam)
        out[sel] = base
    gz = smoothstep(1.2, 0.0, P[:, 2]) * (0.5 + 0.5 * fbm(P, 1.3, 2, seed=21))
    out = mix(out, C('grime'), 0.45 * gz)
    return _shade(out, ao, edge, facet, facet_amp=0.02, cavity=0.40, edge_amt=0.04)


def paint_teal(P, N, ao, edge, facet, border=None, hem=None, folds=None, tone=1.0):
    """Weathered teal linen: dark/light dye patches, sun-faded blooms, sand dust (heavier at the hem),
    grime stains, worn lighter edges, darker folds and recesses."""
    patch = fbm(P, 0.7, 3, seed=31)
    c = mix(C('teal_dark'), C('teal_light'), smoothstep(0.25, 0.80, patch))
    c = mix(C('teal'), c, 0.85)
    fade = smoothstep(0.58, 0.78, fbm(P, 0.5, 2, seed=37))
    c = mix(c, C('teal_light') * 1.04, 0.35 * fade)
    dust = 0.7 * smoothstep(0.58, 0.80, fbm(P, 0.8, 3, seed=33))
    if hem is not None:
        dust = np.maximum(dust, 0.6 * hem)
    c = mix(c, C('teal_dust'), 0.45 * dust)
    stain = smoothstep(0.66, 0.80, fbm(P, 1.2, 2, seed=39))
    c = mix(c, C('teal_dark') * 0.72, 0.45 * stain)
    if folds is not None:
        c = c * (1.0 - 0.28 * folds)[:, None]
    if border is not None:
        c = mix(c, C('teal_light') * 1.08, 0.40 * border)
    c = c * tone * (0.94 + 0.12 * fbm(P, 2.4, 2, seed=35))[:, None]
    return _shade(c, ao, edge, facet, facet_amp=0.03, cavity=0.45, edge_amt=0.08)


def paint_flapcloth(P, N, ao, edge, facet, hem):
    """Torn linen strips: sandy two-tone with stains, darker frayed ends."""
    c = mix(C('flap'), C('flap_stain'), 0.70 * smoothstep(0.45, 0.72, fbm(P, 1.0, 2, seed=41)))
    c = mix(c, C('sand'), 0.55 * smoothstep(0.40, 0.68, fbm(P, 0.6, 2, seed=45)))
    c = mix(c, mix(C('tan'), C('shadow'), 0.3), 0.85 * hem)
    c = c * (0.95 + 0.1 * fbm(P, 2.5, 2, seed=43))[:, None]
    return _shade(c, ao, edge, facet, facet_amp=0.05, cavity=0.35, edge_amt=0.06)


def paint_stone(P, N, ao, edge, facet, fresh=None, seed=51):
    patch = fbm(P, 0.85, 3, seed=seed)
    c = mix(C('stone_dark'), C('stone_light'), smoothstep(0.25, 0.78, patch))
    c = mix(C('stone'), c, 0.7)
    # broad mottled darker terracotta blotches + paler sandy blooms
    blot = smoothstep(0.55, 0.70, fbm(P, 1.4, 2, seed=seed + 3))
    c = mix(c, C('stone_dark'), 0.60 * blot)
    bloom = smoothstep(0.64, 0.80, fbm(P, 1.1, 2, seed=seed + 5))
    c = mix(c, C('stone_fresh'), 0.30 * bloom)
    if fresh is not None:
        c = mix(c, C('stone_fresh'), 0.75 * fresh)
    # sparse darker flecks (low frequency, soft)
    fl = smoothstep(0.80, 0.88, value_noise(P, 9.0, seed + 7))
    c = c * (1.0 - 0.18 * fl)[:, None]
    # carved grooves and creases read darker; convex edges worn lighter
    groove = np.clip((0.82 - ao) / 0.5, 0, 1)
    c = mix(c, C('stone_groove'), 0.65 * groove)
    c = mix(c, C('stone_edge'), 0.55 * np.clip(edge, 0, 1))
    v = 1.0 + 0.10 * (facet - 0.5) * 2.0
    return c * v[:, None]


def paint_cavity(P, N, ao, edge, facet):
    d = np.min(np.stack([np.linalg.norm(P - e, axis=1) for e in D.MASK_EYES], 0), 0)
    warm = smoothstep(0.34, 0.08, d)
    c = mix(C('cavity'), C('cavity_warm'), 0.85 * warm)
    return c * (0.9 + 0.2 * facet)[:, None]


def paint_eye(P, N):
    d = np.min(np.stack([np.linalg.norm((P - e) / np.array([0.12, 0.07, 0.09]), axis=1) for e in D.MASK_EYES], 0), 0)
    core = smoothstep(0.75, 0.15, d)
    return mix(C('eye'), C('eye_core'), core)


def fill_uncovered(img, cov, iters=24):
    """Bleed colour past island borders (no seams at mip levels)."""
    img = img.copy()
    cov = cov.copy()
    for _ in range(iters):
        if cov.all():
            break
        acc = np.zeros_like(img)
        cnt = np.zeros(cov.shape)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            sc = np.roll(np.roll(cov, dy, 0), dx, 1)
            si = np.roll(np.roll(img, dy, 0), dx, 1)
            acc += si * sc[..., None]
            cnt += sc
        grow = (~cov) & (cnt > 0)
        img[grow] = acc[grow] / cnt[grow][:, None]
        cov = cov | grow
    img[~cov] = img[cov].mean(0)
    return img
