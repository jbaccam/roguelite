"""Painterly albedo for the Frost Cyclops, computed in numpy from baked passes.

Every section is baked once into geometric passes (rest-pose world position,
normal, ambient occlusion, bevel-edge factor, per-facet random, material id).
The albedo is then painted texel by texel from those passes: broad 2-4 value
patches in world space (so the scale is constant in studs), per-facet tone
shifts, light worn edges, cavity darkening, sparse grunge, and deliberately
placed details (eye, toenails, mouth, worn leather edges, stitch-like scratches).
No reference pixels are ever sampled; colours come from the measured table in
source/REFERENCE_NOTES.md scaled by the CALIBRATION gains.
"""
import numpy as np

# ------------------------------------------------------------------ noise
_PERM = np.random.default_rng(20260929).permutation(4096).astype(np.int64)
_RAND = np.random.default_rng(7).random(4096)


def _hash(ix, iy, iz, seed):
    h = _PERM[(ix * 73856093 ^ iy * 19349663 ^ iz * 83492791 ^ seed * 2654435761) & 4095]
    return _RAND[h]


def value_noise(P, scale, seed=0):
    """Smooth 3D value noise in [0,1] at world points P (n,3), feature size 1/scale studs."""
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


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def posterize(x, levels, soft=0.08):
    """Soft staircase: painterly flat patches with slightly soft borders."""
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
# Albedo targets (sRGB) before calibration. Measured reference colours are
# lit results; these are the authored albedos that the probe loop tunes.
PALETTE = {
    'skin':      {'base': (138, 154, 184), 'dark': (112, 130, 166), 'light': (164, 178, 204), 'edge': (184, 194, 216)},
    'nail':      {'base': (160, 174, 200), 'rim': (86, 104, 140)},
    'mouth':     {'base': (34, 22, 32)},
    'socket':    {'base': (40, 52, 80)},
    'fur':       {'base': (214, 199, 180), 'dark': (182, 166, 148), 'light': (232, 220, 204), 'edge': (244, 236, 224)},
    'leather':   {'base': (106, 82, 74), 'dark': (78, 58, 56), 'light': (128, 100, 88), 'edge': (158, 124, 104)},
    'loin':      {'base': (72, 58, 58), 'dark': (52, 42, 46), 'light': (96, 78, 74), 'edge': (118, 96, 86)},
    'buckle':    {'base': (112, 108, 112), 'dark': (84, 80, 86), 'light': (138, 132, 134), 'edge': (186, 178, 176)},
    'stone':     {'base': (150, 142, 142), 'dark': (112, 106, 110), 'light': (176, 168, 166), 'edge': (206, 198, 192)},
    'wood':      {'base': (104, 78, 68), 'dark': (74, 54, 50), 'light': (128, 98, 84), 'edge': (146, 114, 96)},
    'strap':     {'base': (88, 68, 64), 'dark': (62, 48, 48), 'light': (106, 84, 78), 'edge': (132, 104, 92)},
    'eye':       {'sclera': (238, 246, 252), 'shade': (190, 206, 226), 'iris_out': (22, 90, 124),
                  'iris': (64, 186, 216), 'iris_in': (120, 226, 244), 'pupil': (14, 18, 28)},
    'tooth':     {'base': (234, 222, 204), 'dark': (190, 176, 160), 'light': (246, 238, 226), 'edge': (250, 246, 238)},
    'lid':       {'base': (132, 150, 184), 'rim': (34, 44, 70)},
}
MAT_IDS = ['skin', 'fur', 'leather', 'loin', 'buckle', 'stone', 'wood', 'strap', 'eye', 'tooth', 'lid']


def col(key, name, gains):
    g = np.asarray(gains.get(key, (1, 1, 1)), float)
    return np.clip(srgb_to_lin(PALETTE[key][name]) * g, 0, 1)


def paint_generic(key, P, ao, edge, facet, gains, seed, streak_axis=None, patch_scale=0.9, contrast=1.0,
                  facet_amp=0.16, cavity=0.40, flecks=1.0):
    """Shared painterly recipe matching the reference's treatment: every flat
    facet carries its own value (the strongest variation), soft broad drift,
    small painted dabs with soft borders, light worn edges on convex facets,
    cavity darkening between forms and a few sparse darker flecks."""
    n = len(P)
    base = col(key, 'base', gains)
    dark = col(key, 'dark', gains)
    light = col(key, 'light', gains)
    edgec = col(key, 'edge', gains)
    Q = P
    if streak_axis is not None:
        a = np.asarray(streak_axis, float)
        a = a / np.linalg.norm(a)
        along = P @ a
        Q = P - np.outer(along, a) + np.outer(along * 0.18, a)     # stretch along the axis
    out = np.tile(base, (n, 1))
    # per-facet value: lighter facets lean toward the light colour, darker toward dark
    f = (facet - 0.5) * 2.0
    out = mix(out, np.tile(light, (n, 1)), np.clip(f, 0, 1) * facet_amp * 3.0 * contrast)
    out = mix(out, np.tile(dark, (n, 1)), np.clip(-f, 0, 1) * facet_amp * 2.2 * contrast)
    # soft broad drift (low contrast)
    broad = fbm(Q, patch_scale, 3, seed)
    out *= (1.0 + 0.10 * contrast * (broad - 0.5))[:, None]
    # painted dabs: two-level with soft borders, a little lighter
    dab = posterize(fbm(Q, patch_scale * 4.0, 2, seed + 5), 2, soft=0.10)
    out = mix(out, np.tile(light, (n, 1)), dab * 0.22 * contrast)
    dab2 = fbm(Q, patch_scale * 7.0, 2, seed + 9)
    out = mix(out, np.tile(dark, (n, 1)), smoothstep(0.62, 0.72, dab2) * 0.18 * contrast)
    # worn / lit edges and cavity
    e = smoothstep(0.10, 0.45, edge) * smoothstep(0.55, 0.9, ao)
    out = mix(out, np.tile(edgec, (n, 1)), e * 0.50)
    out *= (1.0 - cavity + cavity * smoothstep(0.10, 0.85, ao))[:, None]
    # sparse darker flecks
    g = value_noise(P, 7.0, seed + 11)
    out = mix(out, np.tile(dark, (n, 1)), smoothstep(0.84, 0.90, g) * 0.22 * flecks)
    return out


def box_local(P, prim):
    return (P - prim.c) @ prim.R


def rounded_rect(q, hx, hy, r):
    dx = np.abs(q[:, 0]) - (hx - r)
    dy = np.abs(q[:, 1]) - (hy - r)
    out = np.hypot(np.maximum(dx, 0), np.maximum(dy, 0)) + np.minimum(np.maximum(dx, dy), 0) - r
    return out


def paint_skin(P, N, ao, edge, facet, gains, prims):
    out = paint_generic('skin', P, ao, edge, facet, gains, 1, patch_scale=0.85, facet_amp=0.22, flecks=0.4)
    by_tag = {}
    for p in prims:
        by_tag.setdefault(p.tag, []).append(p)
    # toenails: rounded rectangles on the top-front of each toe block
    nail = col('nail', 'base', gains)
    rim = col('nail', 'rim', gains)
    for tag in ('toe0', 'toe1', 'toe2', 'toe3'):
        for p in by_tag.get(tag, []):
            q = box_local(P, p)
            h = p.h
            # nail plate: front 60% of the toe length, near the top surface
            qq = np.stack([q[:, 0] / (h[0] * 0.78), (q[:, 1] - h[1] * 0.30) / (h[1] * 0.62)], 1)
            d = rounded_rect(qq, 1.0, 1.0, 0.45)
            top = smoothstep(h[2] * 0.25, h[2] * 0.75, q[:, 2]) * smoothstep(0.6, 0.2, N[:, 2] * -1 + 0.8)
            inside = smoothstep(0.08, -0.05, d) * top
            border = (smoothstep(0.16, 0.04, d) - smoothstep(0.02, -0.10, d)) * top
            out = mix(out, np.tile(nail, (len(P), 1)), inside * 0.9)
            out = mix(out, np.tile(rim, (len(P), 1)), np.clip(border, 0, 1) * 0.75)
    # dark interior of mouth, navel, ear hollows, brow notch
    dark = col('mouth', 'base', gains)
    for tag, strength, pad in (('mouth', 1.0, 0.03), ('navel', 0.85, 0.02), ('ear_hollow', 0.6, 0.02),
                               ('notch', 0.7, 0.015)):
        for p in by_tag.get(tag, []):
            d = p.sdf(P)
            out = mix(out, np.tile(dark, (len(P), 1)), smoothstep(pad, -0.02, d) * strength)
    # dark navy ring around the eye: the socket rim
    sock = col('socket', 'base', gains)
    for p in by_tag.get('socket', []):
        d = p.sdf(P)
        out = mix(out, np.tile(sock, (len(P), 1)), smoothstep(0.07, 0.0, d) * 0.95)
    return out


def paint_eye(P, eye_c, fwd, up, gains, R):
    """Sclera, iris ring, pupil and a small highlight, from the angle to the eye axis."""
    c = PALETTE['eye']
    g = np.asarray(gains.get('eye', (1, 1, 1)))
    gi = np.asarray(gains.get('iris', (1, 1, 1)))
    L = lambda k: np.clip(srgb_to_lin(c[k]) * (gi if k.startswith('iris') else g), 0, 1)
    v = P - eye_c
    v /= np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)
    cosang = v @ fwd
    ang = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
    side = np.cross(up, fwd)
    lx = v @ side
    ly = v @ up
    n = len(P)
    out = np.tile(L('sclera'), (n, 1))
    out = mix(out, np.tile(L('shade'), (n, 1)), smoothstep(45, 85, ang) * 0.8)
    iris_r = 27.0
    pupil_r = 12.5
    t = np.clip(ang / iris_r, 0, 1)
    iris = mix(np.tile(L('iris_in'), (n, 1)), np.tile(L('iris'), (n, 1)), smoothstep(0.35, 0.7, t))
    iris = mix(iris, np.tile(L('iris_out'), (n, 1)), smoothstep(0.78, 0.97, t))
    # lighter lower half of the iris (as painted in the reference)
    iris = mix(iris, np.tile(L('iris_in'), (n, 1)), smoothstep(0.0, -0.25, ly) * smoothstep(0.9, 0.5, t) * 0.5)
    out = mix(out, iris, smoothstep(iris_r + 0.8, iris_r - 0.8, ang))
    out = mix(out, np.tile(L('pupil'), (n, 1)), smoothstep(pupil_r + 0.6, pupil_r - 0.6, ang))
    # catch light up and to the viewer's left of the pupil
    hl = np.hypot(lx + 0.10, ly - 0.12)
    out = mix(out, np.ones((n, 3)) * 0.95, smoothstep(0.055, 0.035, hl) * 0.9)
    return out


def paint_lid(P, eye_c, up, fwd, gains):
    base = col('lid', 'base', gains)
    rim = col('lid', 'rim', gains)
    v = P - eye_c
    h = v @ up
    lower = smoothstep(0.02, -0.06, h - np.min(h) - 0.10)
    n = len(P)
    out = np.tile(base, (n, 1))
    # the lash line: the lowest part of the lid shell reads as the dark rim
    edge_band = smoothstep(np.min(h) + 0.09, np.min(h) + 0.02, h)
    out = mix(out, np.tile(rim, (n, 1)), edge_band)
    return out


def fill_uncovered(img, cov):
    """Fill texels outside every island (beyond the bake margin) with the mean colour."""
    if cov.any():
        m = img[cov].mean(0)
        img[~cov] = m
    return img
