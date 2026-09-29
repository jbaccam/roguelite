"""Painterly albedo for the Dragon, computed in numpy from baked passes.

Every section is baked once (rest pose) into geometric passes: world position
P, shading normal N, ambient occlusion, a soft edge factor (bevel-normal
difference), a per-facet random value and the paint recipe id. The albedo is
then painted texel by texel:

* one dominant base colour per material with 2-4 value ranges in broad,
  soft-edged patches (world-space noise, so patch size is constant in studs),
* per-facet value breakup (hand-painted low-poly look),
* darker tone in recesses (AO) and lighter, warmer tone on edges,
* recipe-specific details: hot-orange seams near the spine, chips and pits on
  the belly plates, cool grey chamfer highlights on obsidian, membrane
  blotches that darken toward the bones.

No reference pixels are sampled: colours are the measured table in
source/REFERENCE_NOTES.md multiplied by the CALIBRATION gains (fitted by the
compare loop so the lit render lands on the reference's per-material colour).
"""
import numpy as np

_PERM = np.random.default_rng(20260929).permutation(4096).astype(np.int64)
_RAND = np.random.default_rng(7).random(4096)

RECIPES = ['skin', 'skin_head', 'jaw', 'belly', 'fang', 'mouth', 'obsidian', 'lava', 'eye', 'wingbone', 'membrane']


def _hash(ix, iy, iz, seed):
    h = _PERM[(ix * 73856093 ^ iy * 19349663 ^ iz * 83492791 ^ (seed * 2654435761)) & 4095]
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
    amp = 1.0
    norm = 0.0
    for o in range(octaves):
        tot += amp * value_noise(P, scale * (2.0 ** o), seed + 17 * o)
        norm += amp
        amp *= gain
    return tot / norm


def worley(P, scale, seed=0):
    """Distance to the nearest jittered cell point (F1) and the cell id."""
    X = P * scale
    i = np.floor(X).astype(np.int64)
    best = np.full(len(P), 9.0)
    cid = np.zeros(len(P))
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = i + np.array([dx, dy, dz])
                jx = _hash(c[:, 0], c[:, 1], c[:, 2], seed)
                jy = _hash(c[:, 0], c[:, 1], c[:, 2], seed + 1)
                jz = _hash(c[:, 0], c[:, 1], c[:, 2], seed + 2)
                d = np.sqrt((c[:, 0] + jx - X[:, 0]) ** 2 + (c[:, 1] + jy - X[:, 1]) ** 2 + (c[:, 2] + jz - X[:, 2]) ** 2)
                m = d < best
                best[m] = d[m]
                cid[m] = _hash(c[m, 0], c[m, 1], c[m, 2], seed + 3)
    return best, cid


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
    if t.ndim == 1:
        t = t[:, None]
    return a + (b - a) * t


def patches(P, scale, seed, soft=0.18):
    """Broad painterly patch field in [0,1] with soft plateaus (2-4 value ranges)."""
    n = fbm(P, scale, 3, seed)
    # gentle posterise: plateaus with soft borders
    lv = 3.0
    y = n * lv
    fl = np.floor(y)
    fr = y - fl
    return (fl + smoothstep(0.5 - soft, 0.5 + soft, fr)) / lv


# --------------------------------------------------------------- palette (sRGB)
PALETTE = {
    'skin': {'base': (176, 40, 36), 'dark': (118, 24, 26), 'light': (205, 62, 46), 'warm': (226, 92, 44),
             'hot': (255, 120, 36)},
    'wingbone': {'base': (160, 38, 36), 'dark': (104, 24, 26), 'light': (190, 56, 46), 'warm': (212, 84, 44)},
    'belly': {'base': (224, 170, 114), 'dark': (176, 120, 76), 'light': (240, 198, 146), 'pit': (138, 90, 58),
              'seam': (120, 70, 44)},
    'jaw': {'base': (226, 174, 118), 'dark': (176, 122, 78), 'light': (242, 202, 150), 'pit': (138, 90, 58),
            'seam': (118, 70, 44)},
    'fang': {'base': (224, 192, 144), 'dark': (176, 142, 100)},
    'mouth': {'base': (170, 44, 16), 'hot': (255, 176, 60)},
    'obsidian': {'base': (60, 48, 56), 'dark': (38, 30, 36), 'edge': (118, 108, 124), 'fleck': (96, 88, 102)},
    'membrane': {'base': (228, 112, 44), 'light': (246, 156, 64), 'dark': (190, 76, 30), 'bone': (160, 52, 28)},
    'lava': {'base': (255, 128, 30), 'core': (255, 214, 96)},
    'eye': {'base': (255, 150, 30), 'core': (255, 236, 150), 'rim': (150, 40, 10)},
}


def paint(recipe, P, N, AO, EDGE, FR, extra=None, gains=(1.0, 1.0, 1.0)):
    """Return linear albedo (n,3) for texels of one recipe."""
    pal = {k: srgb_to_lin(v) for k, v in PALETTE[recipe if recipe != 'skin_head' else 'skin'].items()}
    n = len(P)
    ao = np.clip(AO, 0, 1)
    up = np.clip(N[:, 2], -1, 1)
    fr = FR - 0.5
    if recipe in ('skin', 'skin_head', 'wingbone'):
        base = np.tile(pal['base'], (n, 1))
        # broad value ranges
        pt = patches(P, 0.5, 11)
        col = mix(pal['dark'], base, smoothstep(0.1, 0.55, pt))
        col = mix(col, pal['light'], smoothstep(0.66, 0.95, pt) * 0.7)
        # medium darker-crimson blotches: the reference's painterly mottling
        bl = fbm(P, 1.7, 3, 33)
        col = mix(col, pal['dark'] * 0.85, smoothstep(0.56, 0.7, bl) * 0.55)
        # small warm-light flecks
        fl = fbm(P, 4.2, 2, 35)
        col = mix(col, pal['light'], smoothstep(0.68, 0.8, fl) * 0.35)
        # scale-plate cells: each plate its own slight value
        w, cid = worley(P, 1.7, 21)
        col *= (1.0 + 0.16 * (cid - 0.5))[:, None]
        # per-facet value breakup (hand-painted low-poly look)
        col *= (1.0 + 0.16 * fr)[:, None]
        # cavities darker, soft edges lighter and warmer
        col *= (0.6 + 0.4 * ao)[:, None]
        col = mix(col, pal['warm'], np.clip(EDGE, 0, 1) * 0.35)
        # warm cast on up-facing planes (lit planes read red-orange)
        col = mix(col, pal['warm'], smoothstep(0.45, 0.95, up) * 0.18)
        # dark pits / speckles
        sp = value_noise(P, 7.5, 41)
        col = mix(col, pal['dark'] * 0.8, smoothstep(0.83, 0.9, sp) * 0.55)
        if extra is not None and 'spine' in extra:
            # faint hot-orange glow bleeding from the lava seams along the spine
            s = extra['spine']
            hot = smoothstep(1.4, 0.2, s) * (0.35 + 0.65 * (1 - ao))
            hot *= 0.55 + 0.45 * fbm(P, 1.3, 2, 51)
            col = mix(col, pal['hot'], np.clip(hot, 0, 0.85))
        if recipe == 'wingbone':
            col *= 0.95
    elif recipe in ('belly', 'jaw'):
        base = np.tile(pal['base'], (n, 1))
        pt = patches(P, 0.7, 12)
        col = mix(pal['dark'], base, smoothstep(0.1, 0.6, pt))
        col = mix(col, pal['light'], smoothstep(0.66, 0.97, pt) * 0.7)
        col *= (1.0 + 0.1 * fr)[:, None]
        # light chips
        ch = fbm(P, 2.4, 2, 61)
        col = mix(col, pal['light'], smoothstep(0.68, 0.78, ch) * 0.6)
        # small dark pits (the reference's plates are peppered with them)
        pits = value_noise(P, 9.0, 71)
        col = mix(col, pal['pit'], smoothstep(0.86, 0.93, pits) * 0.8)
        col *= (0.55 + 0.45 * ao)[:, None]
        col = mix(col, pal['seam'], smoothstep(0.55, 0.2, ao) * 0.55)
        col = mix(col, pal['light'], np.clip(EDGE, 0, 1) * 0.25)
    elif recipe == 'fang':
        col = mix(srgb_to_lin(PALETTE['fang']['dark']), srgb_to_lin(PALETTE['fang']['base']),
                  0.4 + 0.6 * np.clip(ao, 0, 1))
    elif recipe == 'mouth':
        col = np.tile(pal['base'], (n, 1))
        if extra is not None and 'throat' in extra:
            col = mix(col, pal['hot'], smoothstep(2.2, 0.3, extra['throat']) * 0.9)
    elif recipe == 'obsidian':
        base = np.tile(pal['base'], (n, 1))
        pt = patches(P, 0.9, 13)
        col = mix(pal['dark'], base, smoothstep(0.15, 0.7, pt))
        col *= (1.0 + 0.16 * fr)[:, None]
        fl = fbm(P, 3.0, 2, 81)
        col = mix(col, pal['fleck'], smoothstep(0.66, 0.8, fl) * 0.45)
        col = mix(col, pal['edge'], np.clip(EDGE, 0, 1) * 0.7)
        col *= (0.7 + 0.3 * ao)[:, None]
        # upward faces catch a little of the cool sky
        col = mix(col, pal['fleck'], smoothstep(0.5, 1.0, up) * 0.18)
    elif recipe == 'membrane':
        base = np.tile(pal['base'], (n, 1))
        pt = patches(P, 0.42, 14)
        col = mix(pal['dark'], base, smoothstep(0.08, 0.5, pt))
        col = mix(col, pal['light'], smoothstep(0.55, 0.92, pt) * 0.85)
        bl = fbm(P, 1.6, 3, 91)
        col = mix(col, pal['dark'], smoothstep(0.62, 0.78, bl) * 0.45)
        if extra is not None and 'bone_dist' in extra:
            bd = extra['bone_dist']
            col = mix(col, pal['bone'], smoothstep(1.1, 0.15, bd) * 0.55)
        col *= (0.85 + 0.15 * ao)[:, None]
    elif recipe == 'lava':
        col = mix(pal['base'], pal['core'], smoothstep(0.35, 0.9, fbm(P, 2.0, 2, 101)))
    elif recipe == 'eye':
        col = np.tile(pal['base'], (n, 1))
        if extra is not None and 'eye_r' in extra:
            r = extra['eye_r']
            col = mix(pal['core'], pal['base'], smoothstep(0.05, 0.2, r))
            col = mix(col, pal['rim'], smoothstep(0.2, 0.3, r))
    else:
        col = np.tile(np.array([1.0, 0.0, 1.0]), (n, 1))
    return np.clip(col * np.asarray(gains)[None, :], 0, 1)
