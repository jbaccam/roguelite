"""Magical chest (700 emeralds, 4th of 5): the enchanted chest.

Remodelled 2026-09-28 from the user's painted reference (a horned, skull-topped fantasy chest;
third-party art, used for design only). Measured from the painting (a camera fitted to it,
work-magical/fit_camera.py) and rebuilt with real Blender modelling (bmesh sweeps,
multi-segment bevels, a signed-distance-field sculpted skull):

* TWO GIANT ARCHES, one over each end: a thick smooth weathered-gold band sweeping over the
  lid end, standing on a leg of three stacked, notched stone-like blocks at each corner, on
  dark bronze ball feet. A heavy steel block clamps each arch at the top -- the band runs
  through it, its top surface crossing the block a third of the way down -- and a thick ivory
  horn with a dark steel tip grows low out of the block's outer side. Nothing crosses the
  front: wood and the lock only.
* Compact, heavy proportions: 7.4 wide, body 3.3 tall above the feet, a full half-round
  barrel lid (radius 2.2) hinged on the base's back top edge. The lid, its arch-topped ends,
  both arches with their blocks and horns, and the skull swing up together (102 degrees) and
  the opened lid rests back against the chest.
* Violet-plum boards lit from inside: blue light in every seam (recessed Neon strips), blue
  glow bleeding onto the boards near the seams and around the lock and side orbs, and blue
  spill painted onto the arch and leg faces that look at the wood.
* One thick steel lock plate traced from the user's sketch (spikes flanking a cup, long wings,
  one long point down) with a raised ring holding a glowing orb, across the lid seam; the
  same socket + orb on each end panel.
* The painted skull, recreated in its own lid part (Chest_LidSkull): a big short dome broken
  open on its right-rear side (hollow inside, the chain runs in), a crack over the top closed
  with a row of thick stitch loops, a cross stitch over the right eye and a loop over the left
  brow, angular angry sockets with raised rims, an upside-down-heart nose, cheekbones sweeping
  back over a dark hollow, a short upper jaw and eight hooked mauve claw-fangs gripping the
  lid's front curve. Grimy olive bone: dark brown in every cavity, worn highlights on ridges,
  brown round the break, violet glow bouncing up under the face.

Tier files are plain Python at the top level (no bpy / mathutils / numpy imports), so
author_textures.py can read PALETTE from system Python; build(k) runs inside Blender.
"""
import random

NAME = "Magical"

# sRGB 0-255. GLOW: lid-gap light and the open floor. ACCENT: always-on seams and orbs.
GLOW = (80, 176, 255)
ACCENT = (150, 224, 255)

PALETTE = {
    # violet-plum boards, magenta highlights; the magic light painted near the seams
    "wood": (110, 64, 128), "wood_dark": (52, 30, 76), "wood_light": (178, 112, 178),
    "halo": (70, 150, 255), "halo_core": (196, 236, 255),
    # weathered gold-bronze: lit gold -> bronze -> teal patina -> blue-lit -> glow blue
    "metal_light": (244, 210, 118), "metal": (200, 152, 68), "metal_dark": (132, 110, 72),
    "patina": (82, 116, 118), "patina_dark": (50, 70, 98), "glowlit": (84, 136, 236),
    "glowhot": (140, 196, 255),
    # skull bone (measured off the painting, lifted for daylight): olive bone, brown grime,
    # blue bounce light from the glow, near-black cavities
    "bone_hi": (164, 180, 100), "bone_light": (126, 148, 66), "bone": (92, 110, 52), "bone_dark": (54, 62, 36),
    "bone_under": (72, 92, 110), "sk_void": (34, 26, 24),
    "sk_warm_dark": (70, 52, 40), "sk_warm": (124, 98, 66), "sk_warm_light": (178, 152, 110),
    "sk_cool_dark": (50, 48, 98), "sk_cool": (90, 96, 164), "sk_cool_light": (140, 150, 214),
    "ivory": (242, 224, 184), "ivory_mid": (218, 184, 132), "ivory_dark": (150, 108, 76),
    "iron_light": (176, 184, 210), "iron": (116, 124, 152), "iron_dark": (46, 50, 72),
    "steel_light": (204, 208, 222), "steel": (138, 142, 166), "steel_dark": (58, 60, 86),
    "mauve_light": (196, 150, 196), "mauve": (122, 84, 134), "mauve_dark": (66, 42, 86),
    "fang_tip": (206, 176, 206), "fang_tip_light": (244, 226, 240),
    # flat swatches: mid steel, dark cavity, pale glow, spare
    "rivet": (150, 160, 186), "keyhole": (30, 22, 38), "gem": (200, 225, 255),
    "swatch4": (90, 80, 62), "swatch5": (40, 34, 60), "swatch6": (190, 140, 176),
}

CHAMFER = 0.06
BAKE = {
    "rim_color": (0.5, 0.68, 1.0), "rim": 0.2,
    "ao_distance": 0.5, "ao_lo": 0.36,
    "edge": 0.7, "edge_tint": (1.0, 0.93, 0.74), "edge_tint_mix": 0.5,
}

# ---------------------------------------------------------------------------
# dimensions (studs; Blender Z up, ground z=0, front faces -Y)
# ---------------------------------------------------------------------------
R = 2.2                        # lid radius = half the body depth
D = 2 * R
FOOT = 0.58                    # bottom of the rail / body; ball feet below lift it clear
RAIL_H, RAIL_OUT = 0.5, 0.14   # thick bottom rail round the base, standing proud of the boards
BOARD0 = FOOT + RAIL_H         # boards start above the rail
ZT = 4.08                      # top of the base boards (lid seam)
HB = ZT - FOOT
GAP = 0.1
ZL = ZT + GAP                  # lid bottom
SKIRT = 0.2
ZC = ZL + SKIRT                # axis of the half-round lid
APEX = ZC + R
PL = (ZT - BOARD0) / 4         # four boards per body face
SEAM = 0.08
BOARD_T = 0.28
XIN = 2.44                     # body boards end here; fixed end walls start here
XLID = 2.41                    # lid half width (opens between the arches)
XE = 3.28                      # end panel outer face
XB0, XB1 = 2.45, 3.55          # arch band, x
RB_IN, RB_OUT = R - 0.14, R + 0.6
XL0, XL1 = 2.1, 3.72           # legs, x
LY_OUT, LY_IN = R + 0.64, R - 0.9
LEG_Z = [(FOOT, FOOT + 1.14), (FOOT + 1.22, FOOT + 2.36), (FOOT + 2.44, ZT)]
# arch top block, +x side: a heavy clamp the arch band runs THROUGH -- the band's top surface
# crosses the block just under its top (where the user drew the line, 2026-09-28); the rest of
# the block wraps down round the band on both sides
TB = (2.25, 3.74, -0.62, 1.02, ZC + RB_OUT - 1.12, ZC + RB_OUT + 0.16)
Z_SEAMLOCK = ZT + GAP / 2
Z_ORB = ZT - 0.62
END_BOARDS = 7
FLOOR_DEPTH = 1.0

# painted atlas layout (shared by paint_primary and build)
U_SPAN = 10.4                  # studs across the primary region (u 0-0.75)
BAND_STUDS = 0.8               # studs per painted band (1/16 of v)
MISC_BAND = 13                 # bands 13-15: skull / horn / iron / steel / mauve zones
MISC_V0 = MISC_BAND / 16
ZONES = {"skull": (0.0, 0.25), "horn": (0.25, 0.40), "iron": (0.40, 0.52), "steel": (0.52, 0.64), "mauve": (0.64, 0.75)}
A_FRONT, A_BACK, A_LID, A_END = 0.2, 5.4, 0.2, 5.6
BAND_FRONT, BAND_LID0, BAND_END0, BAND_SPARE = 0, 4, 5, 12
LOCK_UV = (0.75 * (XIN + A_FRONT) / U_SPAN, (BAND_FRONT + 4) / 16)
ORB_UV = (0.75 * (R + A_END) / U_SPAN, (BAND_END0 + (Z_ORB - BOARD0) / PL) / 16)

# Preview point lights (Blender only; place matching PointLights in Studio).
LIGHTS = [
    ((0.0, -R - 1.3, Z_SEAMLOCK), GLOW, 240.0),
    ((-XE - 1.1, 0.0, Z_ORB), GLOW, 110.0),
    ((XE + 1.1, 0.0, Z_ORB), GLOW, 110.0),
    ((0.0, 0.0, ZT + 0.6), GLOW, 120.0),
]


# ---------------------------------------------------------------------------
# painted source atlas
# ---------------------------------------------------------------------------
def _ramp(np, col, lerp, x, stops):
    out = np.broadcast_to(col(stops[0][1]), x.shape + (3,)).copy()
    for (ta, _), (tb, cb) in zip(stops, stops[1:]):
        f = np.clip((x - ta) / (tb - ta), 0, 1)
        out = lerp(out, col(cb), (f * f * (3 - 2 * f)).astype(np.float32))
    return out


def paint_primary(np, rng, w, h, p, tools):
    """Bands 0-12: violet boards lit from inside (blue seam halo, glow blooms at the lock and
    the side orbs). Bands 13-15: painterly zones for skull bone, horn ivory, dark steel,
    polished steel and mauve, addressed by build() through ZONES."""
    sn, col, lerp = tools["smooth_noise"], tools["col"], tools["lerp"]
    S = w / 0.75
    U = np.broadcast_to(((np.arange(w, dtype=np.float32) + 0.5) / S)[None, :], (h, w))
    V = np.broadcast_to((1 - (np.arange(h, dtype=np.float32) + 0.5) / h)[:, None], (h, w))
    band = np.clip((V * 16).astype(np.int32), 0, 15)
    t = V * 16 - band

    # ---- boards ----
    wood = np.empty((h, w, 3), np.float32)
    vals, hues = rng.uniform(-0.09, 0.09, 16), rng.uniform(-0.07, 0.07, 16)
    for b in range(16):
        c = col(p["wood"]) * (1 + vals[b]) * np.array([1 + hues[b], 1 - abs(hues[b]) * 0.3, 1 - 0.6 * hues[b]], np.float32)
        wood[band == b] = c
    wood *= (1 + sn(h, w, 9, 8, rng) * 0.26 + sn(h, w, 30, 22, rng) * 0.08)[..., None]
    # long flowing grain: dark broken strokes and soft magenta streaks between them
    f = t * 3.2 + sn(h, w, 18, 12, rng) * 1.9 + sn(h, w, 64, 6, rng) * 0.45 + band * 0.41
    d = np.abs(f - np.round(f))
    stroke = np.clip(sn(h, w, 48, 36, rng) * 3.0 + 0.6, 0, 1)
    wood = lerp(wood, col(p["wood_dark"]), np.clip(1 - d / 0.085, 0, 1) * stroke * 0.55)
    light = np.clip(1 - np.abs(d - 0.5) / 0.2, 0, 1) * np.clip(sn(h, w, 24, 16, rng) * 2.6 + 0.25, 0, 1)
    wood = lerp(wood, col(p["wood_light"]), light * 0.42)
    # hand-painted board shading: warm lit upper edge, dark lower edge
    wood = lerp(wood, col(p["wood_light"]), (np.clip((t - 0.78) / 0.22, 0, 1) ** 1.5) * 0.38)
    wood = lerp(wood, col(p["wood_dark"]), (np.clip((0.32 - t) / 0.32, 0, 1) ** 1.5) * 0.5)
    # magic light from the seams: a patchy wash, a tight halo and a hot core at the edge
    E = np.minimum(t, 1 - t) * BAND_STUDS
    patch = np.clip(sn(h, w, 10, 14, rng) * 1.8 + 0.6, 0.18, 1.0)
    wood = lerp(wood, col(p["halo"]) * 0.75, np.exp(-(E / 0.22) ** 2) * patch * 0.16)
    wood = lerp(wood, col(p["halo"]), np.exp(-(E / 0.06) ** 2) * (0.3 + 0.7 * patch) * 0.8)
    wood = lerp(wood, col(p["halo_core"]), np.clip(1 - E / 0.028, 0, 1) * (0.45 + 0.55 * patch))
    # glow blooms round the lock orb (front boards) and the side orbs (end boards)
    su, sv = 0.75 / U_SPAN, 1 / 16 / BAND_STUDS

    def bloom(c, rad, mask):
        r2 = ((U - c[0]) / su) ** 2 + ((V - c[1]) / sv) ** 2
        return np.exp(-r2 / rad ** 2) * mask

    front = (band <= BAND_LID0) & (U < 0.375)
    ends = (band >= BAND_END0) & (band < BAND_END0 + END_BOARDS) & (U >= 0.375)
    g = bloom(LOCK_UV, 1.2, front) * 0.6 + bloom(LOCK_UV, 2.4, front) * 0.2
    g = g + bloom(ORB_UV, 0.9, ends) * 0.6 + bloom(ORB_UV, 1.8, ends) * 0.2
    wood = lerp(wood, col(p["halo"]), np.clip(g, 0, 0.9).astype(np.float32))
    # a few magic sparkles in the blooms
    for c, rad, lim in ((LOCK_UV, 2.2, (0.0, 0.375, 0, (BAND_LID0 + 1) / 16)), (ORB_UV, 1.8, (0.375, 0.75, BAND_END0 / 16, (BAND_END0 + END_BOARDS) / 16))):
        for _ in range(70):
            a, r_ = rng.uniform(0, 2 * np.pi), abs(rng.normal(0, rad * 0.55))
            uu, vv = c[0] + np.cos(a) * r_ * su, c[1] + np.sin(a) * r_ * sv
            if not (lim[0] < uu < lim[1] and lim[2] < vv < lim[3]):
                continue
            cx, cy = int(uu * S), int((1 - vv) * h)
            rr = int(rng.integers(2, 5))
            y0, y1, x0, x1 = max(cy - rr, 0), min(cy + rr + 1, h), max(cx - rr, 0), min(cx + rr + 1, w)
            yy, xx = np.mgrid[y0:y1, x0:x1]
            k = np.clip(1 - np.hypot(yy - cy, xx - cx) / (rr + 0.5), 0, 1)[..., None]
            wood[y0:y1, x0:x1] = wood[y0:y1, x0:x1] * (1 - k) + col(p["halo_core"]) * k

    # ---- misc zones ----
    bz = np.clip((V - MISC_V0) / (1 - MISC_V0), 0, 1)
    img = wood
    misc = band >= MISC_BAND
    n1, n2 = sn(h, w, 60, 40, rng), sn(h, w, 150, 90, rng)

    def zone(name):
        u0, u1 = ZONES[name]
        return misc & (U >= u0) & (U < u1), np.clip((U - u0) / (u1 - u0), 0, 1)

    # skull: a 2D table the sculpted skull's vertices pick from (skull_paint): across, hue --
    # warm brown grime / olive bone / cool blue bounce light; up, tone -- black cavity -> grime
    # -> bone -> worn highlight. Soft brush patches on top.
    m, az = zone("skull")
    tone = np.clip(bz + n2 * 0.03, 0, 1)
    warm = _ramp(np, col, lerp, tone, [(0.0, p["sk_void"]), (0.25, p["sk_warm_dark"]), (0.55, p["sk_warm"]), (0.9, p["sk_warm_light"])])
    olive = _ramp(np, col, lerp, tone, [(0.0, p["sk_void"]), (0.22, p["bone_dark"]), (0.5, p["bone"]), (0.78, p["bone_light"]), (1.0, p["bone_hi"])])
    cool = _ramp(np, col, lerp, tone, [(0.0, p["sk_void"]), (0.25, p["sk_cool_dark"]), (0.55, p["sk_cool"]), (0.9, p["sk_cool_light"])])
    hue = np.clip(az + n1 * 0.05, 0, 1)
    c = np.where((hue < 0.5)[..., None], lerp(warm, olive, np.clip(hue / 0.5, 0, 1)), lerp(olive, cool, np.clip((hue - 0.5) / 0.5, 0, 1)))
    c *= (1 + sn(h, w, 40, 28, rng)[..., None] * 0.1)
    img[m] = c[m]
    m, az = zone("horn")
    x = np.clip(bz + n1 * 0.12, 0, 1)
    c = _ramp(np, col, lerp, x, [(0.0, p["ivory_dark"]), (0.3, p["ivory_mid"]), (0.75, p["ivory"]), (1.0, p["ivory"])])
    streak = np.clip(1 - np.abs(np.sin(az * np.pi * 7 + n2 * 3)) / 0.18, 0, 1)
    c = lerp(c, col(p["ivory_dark"]), streak * 0.28)
    img[m] = c[m]
    m, az = zone("iron")
    x = np.clip(az + n1 * 0.2, 0, 1)
    c = _ramp(np, col, lerp, x, [(0.0, p["iron_light"]), (0.45, p["iron"]), (1.0, p["iron_dark"])])
    c *= (1 + n2[..., None] * 0.1)
    img[m] = c[m]
    m, az = zone("steel")
    x = np.clip(az + n1 * 0.12, 0, 1)
    c = _ramp(np, col, lerp, x, [(0.0, p["steel_light"]), (0.4, p["steel"]), (1.0, p["steel_dark"])])
    img[m] = c[m]
    # fangs and stitches: across, tone (lit -> shadow); up, root mauve -> pale tip
    m, az = zone("mauve")
    x = np.clip(az + n1 * 0.06, 0, 1)
    base = _ramp(np, col, lerp, x, [(0.0, p["mauve_light"]), (0.45, p["mauve"]), (1.0, p["mauve_dark"])])
    tip = _ramp(np, col, lerp, x, [(0.0, p["fang_tip_light"]), (0.45, p["fang_tip"]), (1.0, p["mauve"])])
    f = np.clip((bz - 0.35) / 0.6, 0, 1)
    c = lerp(base, tip, (f * f * (3 - 2 * f)).astype(np.float32))
    img[m] = c[m]
    return np.clip(img, 0, 1)


def paint_metal(np, rng, w, h, p, tools):
    """Weathered gold-bronze as a ramp across u: lit gold -> gold -> bronze -> teal patina ->
    blue-lit -> glow blue. build() picks each face's spot on the ramp from how it faces the
    key light and the glowing wood; v is a position coordinate, so every face carries
    painterly patches and brush streaks."""
    sn, col, lerp = tools["smooth_noise"], tools["col"], tools["lerp"]
    T = np.broadcast_to(np.linspace(0, 1, w, dtype=np.float32)[None, :], (h, w))
    T = np.clip(T + sn(h, w, 16, 4, rng) * 0.12 + sn(h, w, 44, 8, rng) * 0.05, 0, 1)
    stops = [(0.0, p["metal_light"]), (0.18, p["metal"]), (0.36, p["metal_dark"]), (0.55, p["patina"]),
             (0.72, p["patina_dark"]), (0.87, p["glowlit"]), (1.0, p["glowhot"])]
    base = _ramp(np, col, lerp, T, stops)
    base *= (1 + sn(h, w, 40, 10, rng)[..., None] * 0.1 + sn(h, w, 20, 8, rng)[..., None] * 0.08
             - np.clip(sn(h, w, 14, 6, rng) - 0.15, 0, None)[..., None] * 0.35)
    return np.clip(base, 0, 1)


# ---------------------------------------------------------------------------
# the skull, sculpted as a signed distance field (numpy is passed in; build() meshes it with
# surface nets, projects the vertices onto the exact surface and decimates to soft facets).
# Skull-local units: face toward -y, up +z, ~1.8 units across (x SKULL_SCALE -> ~2.7 studs).
# Recreated from the reference painting and measured against it through a camera fitted to
# the painting (work-magical/fit_camera.py, ref_render.py): a big, short, squat dome broken open
# on its right-rear side (a jagged edge over the hollow inside; the chain runs into it) and
# split over the top by a crack closed with thick stitches; angular sockets with raised rims
# whose tops slant down toward the nose under angry brow pads; an upside-down-heart nasal
# cavity; cheekbones sweeping back over a dark hollow; a short upper jaw whose long hooked
# claw-fangs grip the lid. It lies nearly level on the lid's front curve, turned a little
# toward the chain side, the face looking out over the front, as painted.
# ---------------------------------------------------------------------------
SKULL_SCALE = 1.5              # studs per skull unit (~2.7 studs across)
SKULL_YAW = 10.0               # degrees the face turns toward the chain side / the viewer, as painted
SKULL_TILT = 3.0               # degrees the face tips down; nearly level, face presented as painted
SKULL_Y = -1.45                # skull origin, y (z is solved so it sits into the lid)
SKULL_SINK = 0.4               # studs the underside sits into the lid (trimmed flush)
SKULL_TRIS = 5000              # decimation target for the bone
SK_C0 = (0.0, 0.06, 0.14)      # cranium centre and radii: a big, short dome, like the painting
SK_CR = (0.88, 0.78, 0.7)
SK_EYE_C = (0.42, -0.88, -0.04)   # eye socket centre (x mirrored)
SK_SHELL = 0.1                 # bone thickness, seen at the broken opening
SK_OPEN_DIR = (-0.9, -0.14, 0.0)   # the skull's right-rear side is broken open (the chain goes in)
SK_OPEN = [(-0.4, 0.1), (-0.3, 0.24), (-0.16, 0.19), (-0.06, 0.3), (0.06, 0.2), (0.18, 0.24), (0.23, 0.09),
           (0.29, 0.0), (0.2, -0.09), (0.23, -0.2), (0.06, -0.25), (-0.12, -0.21), (-0.28, -0.25), (-0.38, -0.1)]
SK_EYE = [(-0.2, 0.0), (0.0, 0.12), (0.22, 0.165), (0.265, 0.0), (0.2, -0.155), (0.02, -0.21),
          (-0.13, -0.165), (-0.2, -0.08)]          # eye socket outline, outer = +
SK_NOSE = [(0.0, 0.17), (0.12, -0.02), (0.15, -0.11), (0.08, -0.16), (0.0, -0.11), (-0.08, -0.16),
           (-0.15, -0.11), (-0.12, -0.02)]
SK_ARCH = [(-0.39, -0.42), (-0.35, -0.66), (-0.2, -0.84), (0.0, -0.9), (0.2, -0.84), (0.35, -0.66), (0.39, -0.42)]
# the stitched crack: over the dome from the back, down the forehead into the right socket
SK_CRACK = [(0.03, 1.0, 0.62), (-0.04, 0.76, 0.8), (0.05, 0.5, 0.86), (-0.03, 0.24, 0.87), (0.05, -0.02, 0.82),
            (-0.03, -0.28, 0.7), (0.03, -0.5, 0.5), (-0.08, -0.7, 0.3), (-0.12, -0.86, 0.14), (-0.22, -0.94, 0.06)]
SK_CRACK2 = [(-0.8, -0.1, 0.42), (-0.62, -0.2, 0.54), (-0.44, -0.34, 0.58)]
SK_STITCHES = (0.42, 0.465, 0.51, 0.555)   # where the stitch loops sit along the main crack
SK_STITCH_X = 0.84                       # the cross stitch over the right eye
SK_CRACK3 = [(0.7, -0.7, 0.2), (0.8, -0.52, 0.34), (0.88, -0.36, 0.4)]   # short split over the left brow


def _sk_v(np, c):
    return np.asarray(c, np.float32)


def _sk_ell(np, P, c, r):
    c, r = _sk_v(np, c), _sk_v(np, r)
    q = (P - c) / r
    k0 = np.sqrt((q * q).sum(1))
    k1 = np.sqrt(((q / r) ** 2).sum(1))
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)


def _sk_seg(np, P, a, b, ra, rb=None):
    a, b = _sk_v(np, a), _sk_v(np, b)
    pa, ba = P - a, b - a
    h = np.clip(pa @ ba / float(ba @ ba), 0.0, 1.0)
    d = np.sqrt(((pa - h[:, None] * ba) ** 2).sum(1))
    return d - (ra if rb is None else ra + (rb - ra) * h)


def _sk_smin(np, a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def _sk_smax(np, a, b, k):
    return -_sk_smin(np, -a, -b, k)


def _sk_poly(np, px, py, pts):
    """Signed distance to a 2D polygon (negative inside)."""
    d = (px - pts[0][0]) ** 2 + (py - pts[0][1]) ** 2
    s = np.ones_like(px)
    j = len(pts) - 1
    for i in range(len(pts)):
        (xi, yi), (xj, yj) = pts[i], pts[j]
        ex, ey = xj - xi, yj - yi
        wx, wy = px - xi, py - yi
        t = np.clip((wx * ex + wy * ey) / (ex * ex + ey * ey), 0.0, 1.0)
        d = np.minimum(d, (wx - ex * t) ** 2 + (wy - ey * t) ** 2)
        c1, c2, c3 = py >= yi, py < yj, ex * wy > ey * wx
        s = np.where((c1 & c2 & c3) | (~c1 & ~c2 & ~c3), -s, s)
        j = i
    return s * np.sqrt(d)


def _sk_pit(np, P, c, axis, shape, depth, taper, mirror=1.0, flare=0.3):
    """Cavity cutter: a 2D outline (x outward, z up) pushed along axis into the skull,
    narrowing with depth and flaring a little in front so the rim is softly rounded."""
    a = _sk_v(np, axis)
    a = a / np.linalg.norm(a)
    ex = np.array((a[1], -a[0], 0.0), np.float32)
    ex /= np.linalg.norm(ex)
    ez = np.cross(ex, a)
    q = P - _sk_v(np, c)
    t, u, v = q @ a, q @ ex, q @ ez
    sc = np.where(t > 0, np.maximum(1.0 - taper * np.maximum(t - 0.2, 0.0), 0.4), 1.0 + flare * np.minimum(-t, 0.25))
    return np.maximum(_sk_poly(np, mirror * u / sc, v / sc, shape) * sc, t - depth)


def _sk_line(np, P, pts):
    g = None
    for a, b in zip(pts, pts[1:]):
        e = _sk_seg(np, P, a, b, 0.0)
        g = e if g is None else np.minimum(g, e)
    return g


def skull_env(np, P):
    """The uncarved skull volume: cranium, face, brows, cheekbones, arches, upper jaw."""
    d = _sk_ell(np, P, SK_C0, SK_CR)
    d = _sk_smin(np, d, _sk_ell(np, P, (0.0, 0.26, 0.14), (0.85, 0.62, 0.64)), 0.2)       # wider behind
    d = _sk_smin(np, d, _sk_ell(np, P, (0.0, -0.45, -0.24), (0.74, 0.5, 0.44)), 0.24)   # face
    for s in (-1.0, 1.0):
        d = _sk_smax(np, d, -_sk_ell(np, P, (s * 0.99, -0.3, -0.02), (0.2, 0.42, 0.32)), 0.22)   # temple
        d = _sk_smax(np, d, -_sk_ell(np, P, (s * 0.86, -0.12, -0.48), (0.18, 0.34, 0.17)), 0.12)    # hollow under the arch
    for s in (-1.0, 1.0):
        d = _sk_smin(np, d, _sk_ell(np, P, (s * 0.28, -0.72, 0.1), (0.26, 0.12, 0.1)), 0.15)                   # angry brow pad
        d = _sk_smin(np, d, _sk_ell(np, P, (s * 0.58, -0.76, -0.38), (0.2, 0.15, 0.13)), 0.1)                 # cheekbone
        d = _sk_smin(np, d, _sk_seg(np, P, (s * 0.59, -0.7, -0.36), (s * 0.68, 0.02, -0.28), 0.1, 0.065), 0.1)  # zygomatic arch
    d = _sk_smin(np, d, _sk_ell(np, P, (0.0, -0.62, -0.54), (0.46, 0.3, 0.13)), 0.12)   # upper jaw
    d = _sk_smin(np, d, _sk_ell(np, P, (0.0, -0.84, -0.36), (0.28, 0.08, 0.18)), 0.14)    # snout round the nose
    arch = None
    for (xa, ya), (xb, yb) in zip(SK_ARCH, SK_ARCH[1:]):
        e = _sk_seg(np, P, (xa, ya, -0.63), (xb, yb, -0.65), 0.08)
        arch = e if arch is None else np.minimum(arch, e)
    return _sk_smin(np, d, arch, 0.06)                                                  # tooth ridge


def skull_hole(np):
    """Centre (on the envelope) and inward axis of the broken opening in the right-rear side."""
    n = np.array(SK_OPEN_DIR, np.float32)
    n /= np.linalg.norm(n)
    c0 = np.array(SK_C0, np.float32)
    lo, hi = 0.0, 2.0
    for _ in range(30):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if skull_env(np, (c0 + n * m)[None])[0] < 0 else (lo, m)
    return c0 + n * lo, -n


def _sk_hollow(np, P):
    """The hollow inside the cranium, kept behind the face and above the base."""
    inner = _sk_ell(np, P, SK_C0, tuple(r - SK_SHELL for r in SK_CR))
    return np.maximum(np.maximum(inner, P[:, 0] - 0.3), np.maximum(-0.12 - P[:, 1], -0.08 - P[:, 2]))


def _sk_opening(np, P):
    hc, ha = skull_hole(np)
    return _sk_pit(np, P, hc, ha, SK_OPEN, 0.45, 0.35, flare=0.0)


def skull_field(np, P, cracks=(), lid=None):
    """Final skull (negative inside) and its uncarved envelope. cracks: polylines on the
    surface; lid: (M 3x3, t 3, zc, r) skull->world, trims whatever would sit inside the lid."""
    env = skull_env(np, P)
    d = env
    for s in (-1.0, 1.0):                                  # raised bony rim round each socket
        a = np.array((-s * 0.2, 1.0, 0.06), np.float32)
        a /= np.linalg.norm(a)
        ex = np.array((a[1], -a[0], 0.0), np.float32)
        ex /= np.linalg.norm(ex)
        q = P - np.array((s * SK_EYE_C[0], SK_EYE_C[1], SK_EYE_C[2]), np.float32)
        band = np.abs(_sk_poly(np, s * (q @ ex), q @ np.cross(ex, a), SK_EYE)) - 0.075
        d = _sk_smin(np, d, np.maximum(band, env - 0.055), 0.028)
    for s in (-1.0, 1.0):
        d = _sk_smax(np, d, -_sk_pit(np, P, (s * SK_EYE_C[0], SK_EYE_C[1], SK_EYE_C[2]), (-s * 0.2, 1.0, 0.06), SK_EYE, 0.6, 0.9, mirror=s), 0.016)
    d = _sk_smax(np, d, -_sk_pit(np, P, (0.0, -1.0, -0.36), (0.0, 1.0, 0.12), SK_NOSE, 0.5, 0.7), 0.03)
    for line in cracks:
        d = _sk_smax(np, d, 0.018 - _sk_line(np, P, line), 0.006)
    d = _sk_smax(np, d, -_sk_opening(np, P), 0.02)
    d = _sk_smax(np, d, -_sk_hollow(np, P), 0.02)
    if lid is not None:
        M, t, zc, r = lid
        W = P @ M.T + t
        d = np.maximum(d, (r + 0.02) - np.sqrt(W[:, 1] ** 2 + (W[:, 2] - zc) ** 2))
    return d, env


def skull_project(np, fn, V, iters=4, eps=0.003, cap=0.03):
    """Newton steps that pull points onto the zero surface of fn."""
    E = np.eye(3, dtype=np.float32) * eps
    for _ in range(iters):
        d = fn(V)
        g = np.stack([(fn(V + E[i]) - fn(V - E[i])) / (2 * eps) for i in range(3)], 1)
        step = (d / np.maximum((g * g).sum(1), 1e-6))[:, None] * g
        ln = np.sqrt((step * step).sum(1))[:, None]
        V = V - step * np.minimum(1.0, cap / np.maximum(ln, 1e-9))
    return V


def skull_cracks(np):
    """The crack polylines, snapped onto the envelope and given a jagged zigzag."""
    fn = lambda Q: skull_env(np, Q)
    out = []
    for pts in (SK_CRACK, SK_CRACK2, SK_CRACK3):
        P = skull_project(np, fn, np.array(pts, np.float32), 8, cap=0.2)
        dense = [P[0]]
        for i in range(len(P) - 1):
            a, b = P[i], P[i + 1]
            side = np.cross(b - a, a / np.linalg.norm(a))
            side /= max(np.linalg.norm(side), 1e-6)
            for f, o in ((0.33, 0.022), (0.66, -0.018)):
                dense.append(a + (b - a) * f + side * o * (1 if i % 2 else -1))
            dense.append(b)
        out.append(skull_project(np, fn, np.array(dense, np.float32), 6))
    return out


def skull_place(np):
    """Skull -> world: scale, tip the face down by SKULL_TILT, and lower it onto the lid
    until its underside sits SKULL_SINK into the barrel (that part is trimmed off)."""
    a, b = SKULL_TILT * 3.141592653589793 / 180, -SKULL_YAW * 3.141592653589793 / 180
    c, s = float(np.cos(a)), float(np.sin(a))
    cb, sb = float(np.cos(b)), float(np.sin(b))
    M = SKULL_SCALE * np.array(((cb, -sb, 0), (sb, cb, 0), (0, 0, 1)), np.float32) @ np.array(((1, 0, 0), (0, c, -s), (0, s, c)), np.float32)
    g = np.arange(-1.2, 1.4, 0.04, dtype=np.float32)
    P = np.stack(np.meshgrid(g, g, g, indexing="ij"), -1).reshape(-1, 3)
    P = P[skull_env(np, P) < 0]
    lo, hi = ZC, ZC + 8.0
    for _ in range(40):
        cz = (lo + hi) / 2
        W = P @ M.T + np.array((0.0, SKULL_Y, cz), np.float32)
        sink = float(np.max(R - np.sqrt(W[:, 1] ** 2 + (W[:, 2] - ZC) ** 2)))
        lo, hi = (cz, hi) if sink > SKULL_SINK else (lo, cz)
    return M, np.array((0.0, SKULL_Y, (lo + hi) / 2), np.float32)


def skull_surface(np, cracks, lid, h=0.016):
    """Sample the field on a grid and extract a quad mesh with surface nets (one vertex per
    crossed cell, at the mean of its edge crossings), then project it onto the surface."""
    lo = np.array((-1.14, -1.22, -1.1), np.float32)
    hi = np.array((1.14, 1.34, 1.36), np.float32)
    n = (np.ceil((hi - lo) / h) + 1).astype(int)
    axes = [lo[i] + h * np.arange(n[i], dtype=np.float32) for i in range(3)]
    X, Y = np.meshgrid(axes[0], axes[1], indexing="ij")
    F = np.empty(tuple(n), np.float32)
    for k0 in range(0, n[2], 12):
        zs = axes[2][k0:k0 + 12]
        P = np.stack([np.repeat(X[..., None], len(zs), 2).ravel(), np.repeat(Y[..., None], len(zs), 2).ravel(),
                      np.broadcast_to(zs, X.shape + (len(zs),)).ravel()], 1).astype(np.float32)
        F[:, :, k0:k0 + len(zs)] = skull_field(np, P, cracks, lid)[0].reshape(X.shape + (len(zs),))
    nx, ny, nz = F.shape
    corner = [(i, j, k) for k in (0, 1) for j in (0, 1) for i in (0, 1)]
    C = [F[i:nx - 1 + i, j:ny - 1 + j, k:nz - 1 + k] for i, j, k in corner]
    anyin = np.zeros(C[0].shape, bool)
    allin = np.ones(C[0].shape, bool)
    for c in C:
        anyin |= c < 0
        allin &= c < 0
    active = anyin & ~allin
    cells = np.argwhere(active)
    idx = np.full(C[0].shape, -1, np.int64)
    idx[active] = np.arange(len(cells))
    acc = np.zeros((len(cells), 3))
    cnt = np.zeros(len(cells))
    for a in range(8):
        for bit in (1, 2, 4):
            if a & bit:
                continue
            fa, fb = C[a][active], C[a | bit][active]
            m = (fa < 0) != (fb < 0)
            t = fa[m] / (fa[m] - fb[m])
            pa, pb = np.array(corner[a], float), np.array(corner[a | bit], float)
            acc[m] += pa + (pb - pa) * t[:, None]
            cnt[m] += 1
    verts = lo + (cells + acc / cnt[:, None]) * h
    quads = []
    for ax in range(3):
        sl0 = [slice(1, -1)] * 3
        sl1 = [slice(1, -1)] * 3
        sl0[ax], sl1[ax] = slice(0, -1), slice(1, None)
        s0 = F[tuple(sl0)] < 0
        e = s0 != (F[tuple(sl1)] < 0)
        I = [a_ + (0 if i == ax else 1) for i, a_ in enumerate(np.nonzero(e))]
        b1, b2 = [(1, 2), (2, 0), (0, 1)][ax]
        def cell(o1, o2):
            J = list(I)
            J[b1] = J[b1] - o1
            J[b2] = J[b2] - o2
            return idx[J[0], J[1], J[2]]
        q = np.stack([cell(1, 1), cell(0, 1), cell(0, 0), cell(1, 0)], 1)
        flip = ~s0[e]
        q[flip] = q[flip][:, ::-1]
        quads.append(q)
    fn = lambda Q: skull_field(np, Q.astype(np.float32), cracks, lid)[0]
    return skull_project(np, fn, verts.astype(np.float32), 3, cap=h), np.concatenate(quads)


def skull_paint(np, V, N, cracks, lid):
    """Per-vertex spot in the painted skull zone: a = hue (warm brown grime / olive bone /
    cool reflected blue), b = tone (black cavity -> grime -> bone -> worn highlight)."""
    fn = lambda Q: skull_field(np, Q.astype(np.float32), cracks, lid)[0]
    env = skull_env(np, V)
    occ = np.zeros(len(V))
    for hh, w in ((0.03, 1.0), (0.07, 0.8), (0.13, 0.6), (0.22, 0.4)):
        occ += w * np.clip((hh - fn(V + N * hh)) / hh, 0, 1)
    occ /= 2.8
    e = 0.05
    lap = sum(fn(V + E) + fn(V - E) for E in np.eye(3, dtype=np.float32) * e) / 6 - fn(V)
    ridge = np.clip(lap / 0.005, -1, 1)
    carved = np.clip((-env - 0.005) / 0.08, 0, 1)
    crack = np.clip(1 - (np.minimum.reduce([_sk_line(np, V, c) for c in cracks]) - 0.018) / 0.03, 0, 1) if cracks else 0
    pits = np.minimum.reduce([_sk_pit(np, V, (s * SK_EYE_C[0], SK_EYE_C[1], SK_EYE_C[2]), (-s * 0.2, 1.0, 0.06), SK_EYE, 0.6, 0.9, mirror=s) for s in (-1.0, 1.0)]
                             + [_sk_pit(np, V, (0.0, -1.0, -0.36), (0.0, 1.0, 0.12), SK_NOSE, 0.5, 0.7)])
    inpit = np.clip(1 - (pits + 0.005) / 0.03, 0, 1)
    op = _sk_opening(np, V)
    face = (np.abs(op) < 0.025) & (env > -SK_SHELL - 0.01) & (env < -0.004)          # the broken edge
    hollow = np.abs(_sk_hollow(np, V)) < 0.03
    rim = np.clip(1 - op / 0.8, 0, 1) * np.clip(1 + env / 0.06, 0, 1)                # brown round the break
    wob = np.sin(V[:, 0] * 5.1 + 1.3) * np.sin(V[:, 1] * 4.3 + 0.4) * np.sin(V[:, 2] * 3.7 + 2.1)
    wob2 = np.sin(V[:, 0] * 11.3 + V[:, 2] * 7.1) * np.sin(V[:, 1] * 9.7 - 0.8)
    up = np.clip(V[:, 2] / 0.6, -1, 1)                                     # lit dome, shadowed face
    b = 0.5 + 0.28 * ridge - 0.5 * occ - 0.3 * crack + 0.2 * up + 0.09 * wob + 0.05 * wob2 + 0.06 * N[:, 2]
    b = b + (0.13 + 0.05 * wob - b) * carved                                 # cavities: deep dark brown
    b = b + (0.1 + 0.08 * np.clip(N[:, 2], 0, 1) + 0.03 * wob - b) * inpit
    b = np.where(face, 0.66 + 0.1 * ridge, np.where(hollow, 0.12 + 0.06 * wob, b))
    a = 0.47 + 0.2 * wob + 0.06 * wob2 - 0.3 * np.maximum(rim, np.clip(occ * 1.4 - 0.2, 0, 1) * 0.6)
    a = a + 0.4 * np.clip(-V[:, 2] * 1.2 - 0.2 - 0.25 * N[:, 1] - 0.3 * N[:, 2], 0, 1) * (1 - carved)   # violet glow bouncing up the face
    a = a + (0.12 - a) * np.maximum(carved, inpit)
    a = np.where(face | hollow, 0.1, a)
    return np.clip(a, 0, 1), np.clip(b, 0, 1)


# ---------------------------------------------------------------------------
# shape
# ---------------------------------------------------------------------------
def build(k):
    import bpy
    import bmesh
    from mathutils import Vector as V, Matrix
    from mathutils import noise as mnoise

    math = k.math
    pi = math.pi
    rnd = random.Random(1917)
    coll = bpy.context.collection
    KEY = V((-0.35, -0.45, 0.82)).normalized()

    def clamp(x, a=0.0, b=1.0):
        return min(max(x, a), b)

    # ---------------- atlas addressing ----------------
    def board_uv(a, t, band):
        return (0.75 * clamp(a / U_SPAN, 0.003, 0.997), (band + 0.03 + 0.94 * clamp(t)) / 16)

    def zone_uv(zone, a, b):
        u0, u1 = ZONES[zone]
        return (u0 + (u1 - u0) * (0.03 + 0.94 * clamp(a)), MISC_V0 + (1 - MISC_V0) * (0.03 + 0.94 * clamp(b)))

    def metal_uv(t, s):
        return (0.75 + 0.25 * clamp(t, 0.01, 0.99), 0.375 + 0.625 * clamp(s, 0.01, 0.99))

    DARK = k.swatch_uv("keyhole")
    GEM = k.swatch_uv("gem")

    def lit01(n):
        return clamp((1 - n.dot(KEY)) / 2)

    def posn(p, n, scale=0.1, off=0.5):
        ax = max(range(3), key=lambda i: abs(n[i]))
        a, b = [p[i] for i in range(3) if i != ax]
        return clamp(off + (a * 0.8 + b * 0.55) * scale, 0.02, 0.98)

    def phi_of(p):
        return clamp(math.atan2(p.z - ZC, -p.y), 0.0, pi) if p.z > ZC - 1e-6 else (0.0 if p.y < 0 else pi)

    # glow from the wood onto metal that faces it
    ORBS = [(V((0, -R - 0.5, Z_SEAMLOCK)), 2.6, 0.7), (V((-XE - 0.3, 0, Z_ORB)), 1.9, 0.75), (V((XE + 0.3, 0, Z_ORB)), 1.9, 0.75)]

    def orb_glow(p, n):
        g = 0.0
        for c, rng_, s in ORBS:
            d = c - p
            L = d.length
            if L < rng_ and L > 1e-6:
                g = max(g, s * (1 - L / rng_) * clamp(n.dot(d / L) + 0.3))
        return g

    def metal_fn(tj=0.0, dark=0.0, glow=None, sfun=None):
        def f(p, n, face):
            lt = lit01(n)
            t = 0.03 + 0.62 * lt ** 1.15 + tj + dark * (0.55 + 0.45 * lt)
            # weathering: broad patches of bronze / teal patina, darker toward the ground
            t += 0.16 * mnoise.noise(p * 0.75 + V((3.1, 1.7, 0.4))) + 0.05 * mnoise.noise(p * 2.2) + 0.05 * clamp((5.0 - p.z) / 4.5)
            g = clamp(max(glow(p, n) if glow else 0.0, orb_glow(p, n)))
            t = t + (0.93 - t) * g
            return metal_uv(t, sfun(p, n) if sfun else posn(p, n))
        return f

    def zone_fn(zone, tj=0.0, glow=0.0, bfun=None):
        def f(p, n, face):
            a = clamp(0.08 + 0.85 * lit01(n) + tj)
            return zone_uv(zone, a, bfun(p, n) if bfun else posn(p, n, 0.12))
        return f

    # ---------------- pieces ----------------
    pieces = {}

    def emit(part, bm, uvf=None, smooth_deg=32.0):
        """Finish one bmesh piece: clean, UV (per loop, from face normal + position), smooth by
        angle, and hand it to its part."""
        bm.normal_update()
        bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])
        # triangulate here so exporters cannot create sliver triangles, then drop slivers
        bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
        bm.normal_update()
        for fc in [fc for fc in bm.faces if fc.calc_area() < 2e-6]:
            bm.faces.remove(fc)
        for v in [v for v in bm.verts if not v.link_faces]:
            bm.verts.remove(v)
        layer = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")
        for fc in bm.faces:
            fc.smooth = True
            if uvf is not None:
                n = fc.normal.copy()
                for lp in fc.loops:
                    lp[layer].uv = uvf(lp.vert.co.copy(), n, fc)
        lim = math.radians(smooth_deg)
        for e in bm.edges:
            lf = e.link_faces
            e.smooth = len(lf) == 2 and lf[0].normal.angle(lf[1].normal, 0.0) < lim
        me = bpy.data.meshes.new(part + "_piece")
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(me.name, me)
        coll.objects.link(ob)
        pieces.setdefault(part, []).append(ob)
        return ob

    def finish(part):
        objs = pieces[part]
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        if len(objs) > 1:
            bpy.ops.object.join()
        return bpy.context.view_layer.objects.active

    def bevel(bm, width, segs=2, angle=35.0, profile=0.5):
        bm.normal_update()
        lim = math.radians(angle)
        edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.link_faces[0].normal.angle(e.link_faces[1].normal, 0.0) > lim]
        if edges:
            bmesh.ops.bevel(bm, geom=edges, offset=width, offset_type="OFFSET", segments=segs, profile=profile,
                            affect="EDGES", clamp_overlap=True)
        bm.normal_update()

    def sweep(rings, cap0=True, cap1=True, closed=True, tip=None):
        """Skin rings (lists of Vector, equal length) into a solid; tip = a point to close the
        last ring to a sharp cone. Normals are recalculated outward."""
        bm = bmesh.new()
        vs = [[bm.verts.new(q) for q in ring] for ring in rings]
        n = len(rings[0])
        for a, b in zip(vs, vs[1:]):
            for j in range(n if closed else n - 1):
                jj = (j + 1) % n
                bm.faces.new((a[j], a[jj], b[jj], b[j]))
        if cap0:
            bm.faces.new(list(reversed(vs[0])))
        if tip is not None:
            tv = bm.verts.new(tip)
            for j in range(n):
                bm.faces.new((vs[-1][j], vs[-1][(j + 1) % n], tv))
        elif cap1:
            bm.faces.new(vs[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        return bm

    def box(c, hx, hy, hz, yaw=0.0, jitter=0.0, taper=0.0):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=2.0)
        rot = Matrix.Rotation(yaw, 3, "Z")
        for v in bm.verts:
            x, y, z = v.co
            s = 1 - taper * (z + 1) / 2
            q = V((x * hx * s, y * hy * s, z * hz))
            if jitter:
                q += V((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * jitter
            v.co = rot @ q + V(c)
        return bm

    def aabb(x0, x1, y0, y1, z0, z1, **kw):
        return box(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), (x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2, **kw)

    def ellipsoid(c, rx, ry, rz, useg=10, vseg=7):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=useg, v_segments=vseg, radius=1.0)
        for v in bm.verts:
            v.co = V((v.co.x * rx, v.co.y * ry, v.co.z * rz)) + V(c)
        return bm

    def catmull(pts, n):
        P = [pts[0] + (pts[0] - pts[1])] + list(pts) + [pts[-1] + (pts[-1] - pts[-2])]
        out = []
        for i in range(1, len(P) - 2):
            p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
            for j in range(n):
                t = j / n
                out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
        out.append(pts[-1].copy())
        return out

    def frames(path, up=V((0, 0, 1))):
        T = [(path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized() for i in range(len(path))]
        N = []
        n0 = up - T[0] * up.dot(T[0])
        if n0.length < 1e-4:
            n0 = V((1, 0, 0)) - T[0] * T[0].x
        n0.normalize()
        for i, t in enumerate(T):
            if i:
                n0 = N[-1] - t * N[-1].dot(t)
                n0.normalize()
            N.append(n0)
        return T, N, [t.cross(nn) for t, nn in zip(T, N)]

    def tube(path, radii, sides, flat=1.0, up=V((0, 0, 1)), rot=0.0, cap0=True, tip=False):
        T, N, B = frames(path, up)
        rings = []
        last = len(path) - (1 if tip else 0)
        for i in range(last):
            r = radii[i]
            rings.append([path[i] + N[i] * (r * flat * math.cos(rot + 2 * pi * j / sides)) + B[i] * (r * math.sin(rot + 2 * pi * j / sides)) for j in range(sides)])
        return sweep(rings, cap0=cap0, cap1=not tip, tip=path[-1] if tip else None), (T, N, B)

    def revolve(c, axis, prof, sides=16):
        """Lathe a (radius, height) profile round an axis: sockets, domes."""
        axis = V(axis).normalized()
        u = axis.cross(V((0, 0, 1)))
        if u.length < 1e-4:
            u = axis.cross(V((1, 0, 0)))
        u.normalize()
        w = axis.cross(u)
        rings = [[V(c) + axis * hgt + (u * math.cos(2 * pi * j / sides) + w * math.sin(2 * pi * j / sides)) * r for j in range(sides)] for r, hgt in prof]
        return sweep(rings)

    def lid_y(z):
        """Front surface of the chest (boards / lid) at height z."""
        if z <= ZC:
            return -R
        return -math.sqrt(max(R * R - (z - ZC) ** 2, 0.0))

    # ======================= BASE =======================
    # Base: body boards, bottom rail, the stacked-block legs and ball feet, the lock and side
    # orbs. Lid (opens on a back hinge): barrel boards, the upper end walls, both arch bands,
    # their top blocks and horns, the skull and chain -- everything above the seam swings up.
    B_, BM_ = "Chest_Base", "Chest_Magic"
    L_, LM_ = "Chest_Lid", "Chest_LidMagic"
    bulge = [0.02, 0.0, 0.03, 0.01, 0.0, 0.025, 0.012, 0.0, 0.028, 0.006, 0.02, 0.0, 0.015, 0.03, 0.0, 0.02]

    def board(y_out, y_in, z0, z1, x0, x1, uvf, stations=4):
        """A straight board along x with a slightly wavy outer face, soft chamfers."""
        rings = []
        for i in range(stations):
            x = x0 + (x1 - x0) * i / (stations - 1)
            wob = 0.0 if i in (0, stations - 1) else rnd.uniform(-0.012, 0.012)
            yo = y_out + math.copysign(wob, y_out - y_in)
            rings.append([V((x, y_in, z0)), V((x, yo, z0 + rnd.uniform(-0.01, 0.01))), V((x, yo, z1 + rnd.uniform(-0.01, 0.01))), V((x, y_in, z1))])
        bm = sweep(rings)
        bevel(bm, 0.055, 2)
        return bm

    for side in (-1, 1):
        for i in range(4):
            za, zb = BOARD0 + i * PL + SEAM / 2, BOARD0 + (i + 1) * PL - SEAM / 2
            yo = side * (R + bulge[i + (0 if side < 0 else 4)])
            yi = side * (R - BOARD_T)
            a0 = A_FRONT if side < 0 else A_BACK
            uvf = (lambda p, n, fc, za=za, zb=zb, a0=a0, side=side, i=i:
                   board_uv(side * -p.x + XIN + a0 if side > 0 else p.x + XIN + a0, (p.z - za) / (zb - za), BAND_FRONT + i))
            emit(B_, board(yo, yi, za, zb, -XIN, XIN, uvf, 3), uvf)
        # magic light inside the seams, recessed behind the board faces
        for j in (1, 2, 3):
            zs = BOARD0 + j * PL
            ya, yb = sorted((side * (R - 0.04), side * (R - 0.2)))
            emit(BM_, aabb(-XIN + 0.05, XIN - 0.05, ya, yb, zs - SEAM / 2 - 0.006, zs + SEAM / 2 + 0.006), lambda p, n, fc: GEM)
    # dark floor block inside the body
    emit(B_, aabb(-XIN, XIN, -R + BOARD_T - 0.02, R - BOARD_T + 0.02, FOOT, ZT - FLOOR_DEPTH), lambda p, n, fc: DARK)

    # thick bottom rail (plinth) round the whole base: the boards stop above it
    def rail_fn():
        return metal_fn(tj=0.02, dark=0.12, glow=lambda p, n: 0.0)

    for side in (-1, 1):
        ya, yb = sorted((side * (R + RAIL_OUT), side * (R - 0.3)))
        bm = aabb(-XL0 - 0.1, XL0 + 0.1, ya, yb, FOOT, BOARD0, jitter=0.012)
        bevel(bm, 0.09, 2)
        emit(B_, bm, rail_fn(), 40)
        xa, xb = sorted((side * (XE + RAIL_OUT), side * (XE - 0.3)))
        bm = aabb(xa, xb, -LY_IN - 0.1, LY_IN + 0.1, FOOT, BOARD0, jitter=0.012)
        bevel(bm, 0.09, 2)
        emit(B_, bm, rail_fn(), 40)

    # ---- end walls: the lower part (to the seam) stays with the base, the tombstone top
    #      (from the lid seam up) is part of the lid; each with its own boards ----
    def half_w(z):
        return R if z <= ZC else math.sqrt(max(R * R - (z - ZC) ** 2, 0.0))

    tomb_top = [(-R, ZL), (R, ZL), (R, ZC)] + [(-R * math.cos(pi - pi * i / 16), ZC + R * math.sin(pi - pi * i / 16)) for i in range(1, 16)] + [(-R, ZC)]
    END_Z = [(BOARD0 + j * PL, BOARD0 + (j + 1) * PL) for j in range(4)] + \
            [(ZL + j * (APEX - 0.25 - ZL) / 3, ZL + (j + 1) * (APEX - 0.25 - ZL) / 3) for j in range(3)]
    for sx in (-1, 1):
        xa, xb = sorted((sx * XIN, sx * (XE - 0.2)))
        bm = aabb(xa, xb, -R, R, FOOT, ZT)
        emit(B_, bm, lambda p, n, fc, sx=sx: board_uv(sx * p.y + R + A_BACK, (p.z - FOOT) / (ZT - FOOT), BAND_SPARE))
        xa, xb = sorted((sx * (XLID - 0.1), sx * (XE - 0.2)))
        bm = sweep([[V((x, y, z)) for y, z in tomb_top] for x in (xa, xb)])
        bevel(bm, 0.03, 1, 50)
        emit(L_, bm, lambda p, n, fc, sx=sx: board_uv(sx * p.y + R + A_BACK, (p.z - ZL) / (APEX - ZL), BAND_SPARE))
        for j, (zj0, zj1) in enumerate(END_Z):
            part, mpart = (B_, BM_) if j < 4 else (L_, LM_)
            z0, z1 = zj0 + SEAM / 2, zj1 - SEAM / 2
            if j in (0, 4):
                z0 = zj0 + 0.01
            if j == 3:
                z1 = zj1 - 0.01
            zs = [z0 + (z1 - z0) * q / 2 for q in range(3)]
            outline = [(-half_w(z0), z0), (half_w(z0), z0)] + [(half_w(z), z) for z in zs[1:]] + [(-half_w(z), z) for z in reversed(zs[1:])]
            bz = bulge[(j * 5) % 16] * 0.8
            xo, xi = sx * (XE + bz), sx * (XE - 0.26)
            bm = sweep([[V((x, y, z)) for y, z in outline] for x in sorted((xo, xi))])
            bevel(bm, 0.05, 2)
            emit(part, bm, lambda p, n, fc, sx=sx, z0=z0, z1=z1, j=j: board_uv(sx * p.y + R + A_END, (p.z - z0) / (z1 - z0), BAND_END0 + j))
            if j not in (3, 6):
                zs_ = zj1
                hw = half_w(zs_ + SEAM) - 0.12
                xa2, xb2 = sorted((sx * (XE - 0.08), sx * (XE - 0.24)))
                emit(mpart, aabb(xa2, xb2, -hw, hw, zs_ - SEAM / 2 - 0.006, zs_ + SEAM / 2 + 0.006), lambda p, n, fc: GEM)

    # ---- the two giant arches ----
    def band_glow(sx):
        def g(p, n):
            rho = math.hypot(p.y, p.z - ZC) if p.z > ZC else abs(p.y)
            inner_x = clamp((-n.x * sx - 0.35) / 0.5) * 0.95 * clamp(1 - (rho - R) / 0.75)
            rh = V((0, p.y, p.z - ZC)) if p.z > ZC else V((0, p.y, 0))
            rh = rh.normalized() if rh.length > 1e-6 else V((0, 0, 1))
            inner_r = clamp((-n.dot(rh) - 0.35) / 0.5) * 0.8
            return max(inner_x, inner_r)
        return g

    def leg_glow(sx, sy):
        def g(p, n):
            face_wood = clamp((-n.x * sx - 0.4) / 0.5) * 0.7          # looks at the front/back boards
            face_end = clamp((-n.y * sy - 0.4) / 0.5) * 0.6 * clamp((abs(p.x) - XL0 - 0.3) / 0.6)   # looks at the end panel
            return max(face_wood, face_end) * clamp(1.15 - (p.z - FOOT) / 5)
        return g

    ARCN = 16
    for sx in (-1, 1):
        # the smooth heavy band over the lid end, standing on the leg caps (part of the lid)
        ph1, ph2 = rnd.uniform(0, 6), rnd.uniform(0, 6)
        rings = []
        stations = [(0.0, ZL + 0.01)] + [(pi * i / ARCN, None) for i in range(ARCN + 1)] + [(pi, ZL + 0.01)]
        for ph, zx in stations:
            rh = V((0, -math.cos(ph), math.sin(ph)))
            c = V((0, 0, ZC if zx is None else zx))
            ro = RB_OUT + 0.03 * math.sin(2.2 * ph + ph1) + (0.02 * math.sin(5 * ph + ph2))
            xa = XB0 + 0.02 * math.sin(3 * ph + ph2)
            xb = XB1 + 0.02 * math.sin(2.6 * ph + ph1)
            pin, pout = c + rh * RB_IN, c + rh * ro
            rings.append([V((sx * xa, pin.y, pin.z)), V((sx * xb, pin.y, pin.z)), V((sx * xb, pout.y, pout.z)), V((sx * xa, pout.y, pout.z))])
        bm = sweep(rings)
        bevel(bm, 0.14, 2, 40)
        emit(L_, bm, metal_fn(tj=0.0, glow=band_glow(sx), sfun=lambda p, n: clamp(0.15 + phi_of(p) * 0.2 + p.x * 0.04)), 40)

        # legs: three stacked notched blocks round a core, on a ball foot (base)
        for sy in (-1, 1):
            cx, cy = sx * (XL0 + XL1) / 2, sy * (LY_OUT + LY_IN) / 2
            hx, hy = (XL1 - XL0) / 2, (LY_OUT - LY_IN) / 2
            emit(B_, box((cx, cy, (FOOT + ZT) / 2), hx - 0.16, hy - 0.16, (ZT - FOOT) / 2 - 0.02), metal_fn(dark=0.45), 40)
            for (z0, z1), sc in zip(LEG_Z, (1.0, 0.97, 1.05)):
                bm = box((cx + rnd.uniform(-0.03, 0.03), cy + rnd.uniform(-0.03, 0.03), (z0 + z1) / 2), hx * sc, hy * sc, (z1 - z0) / 2,
                         yaw=math.radians(rnd.uniform(-2.5, 2.5)), jitter=0.022, taper=rnd.uniform(-0.02, 0.03))
                bevel(bm, 0.12, 2)
                emit(B_, bm, metal_fn(tj=rnd.uniform(0.0, 0.05), dark=0.2, glow=leg_glow(sx, sy)), 40)
            emit(B_, ellipsoid((cx, cy, 0.34), 0.42, 0.42, 0.34, 10, 7), metal_fn(dark=0.35), 50)

        # the heavy steel block clamping the arch top (lid): the band runs through it
        x0, x1 = sorted((sx * TB[0], sx * TB[1]))
        bm = aabb(x0, x1, TB[2], TB[3], TB[4], TB[5], jitter=0.02)
        bevel(bm, 0.13, 2)
        emit(L_, bm, zone_fn("iron", 0.26), 40)

        # thick ivory horn growing LOW out of the block's outer side: outward first, then up;
        # an angular dark-steel sheath over its top third with a jagged lower edge
        zr = TB[4] + 0.5
        hp = [V((sx * 3.3, 0.2, zr)), V((sx * 4.3, 0.16, zr + 0.02)), V((sx * 4.95, 0.08, zr + 0.4)), V((sx * 5.25, 0.0, zr + 1.05)),
              V((sx * 5.25, -0.06, zr + 1.7)), V((sx * 5.05, -0.1, zr + 2.15))]
        path = catmull(hp, 4)
        L = [0.0]
        for a, b in zip(path, path[1:]):
            L.append(L[-1] + (b - a).length)
        s_ = [x / L[-1] for x in L]
        rad = [0.72 * (1.0 - 0.12 * clamp(s / 0.2)) * (1 - s) ** 0.55 for s in s_]
        cut = next(i for i, s in enumerate(s_) if s >= 0.7)
        bm, fr = tube(path[:cut + 1], rad[:cut + 1], 10, flat=0.86, up=V((0, 1, 0)))
        emit(L_, bm, lambda p, n, fc: zone_uv("horn", 0.5 + 0.45 * n.dot(V((0, -1, 0))), clamp(min((p - hp[1]).length, 3.0) / 2.4)), 45)
        c0 = next(i for i, s in enumerate(s_) if s >= 0.6)
        cap_path, cap_r = path[c0:], [r * 1.16 + 0.04 for r in rad[c0:]]
        T, N, Bn = frames(cap_path, V((0, 1, 0)))
        rings = []
        for i in range(len(cap_path) - 1):
            ring = []
            for j in range(6):
                a = 2 * pi * j / 6 + 0.3
                q = cap_path[i] + N[i] * (cap_r[i] * 0.86 * math.cos(a)) + Bn[i] * (cap_r[i] * math.sin(a))
                if i == 0:
                    q += T[i] * (0.2 if j % 2 else -0.08)
                ring.append(q)
            rings.append(ring)
        lip = [cap_path[0] + (q - cap_path[0]) * 0.78 for q in rings[0]]
        bm = sweep([lip] + rings, cap0=True, tip=cap_path[-1])
        emit(L_, bm, zone_fn("iron", 0.22), 18)

    # ---- the lock: one thick steel plate traced from the user's sketch (2026-09-28): two short
    #      spikes flanking a U cup at the top, long horizontal wings, square notches underneath
    #      and one long point straight down. A thick raised ring with the glowing orb sits in the
    #      cup, on the lid seam. Sketch pixels, y down; the cup centre is the origin. ----
    LOCK_PX = [
        (248, 180), (270, 190), (298, 194), (310, 220), (325, 248), (338, 220), (350, 196), (375, 193), (397, 185),
        (400, 156), (425, 152), (445, 146), (458, 137), (440, 125), (418, 113), (402, 100), (390, 86), (380, 68),
        (372, 88), (362, 102), (355, 110), (353, 135), (340, 152), (322, 157), (304, 152), (292, 135), (290, 110),
        (283, 102), (273, 88), (265, 68), (255, 86), (243, 100), (228, 113), (206, 125), (188, 137),
        (201, 146), (222, 152), (245, 156)]
    LOCK_TIPS = {(325, 248), (458, 137), (380, 68), (265, 68), (188, 137)}
    LOCK_O, LOCK_W = (322.0, 130.0), 3.6
    LOCK_K = LOCK_W / (458 - 188)

    def lock_plate(cz, he=0.12, hc=0.27, ridge=0.13):
        """Flat plate hugging the chest front. Its top rises from the rim to the centre in
        rings; the centre-to-tip line of every point is lifted into a crease, so each point
        has a lit half and a shadow half. Outer rim bevelled for edge highlights."""
        outline = [((x - LOCK_O[0]) * LOCK_K, -(y - LOCK_O[1]) * LOCK_K) for x, y in LOCK_PX]
        is_tip = [pt in LOCK_TIPS for pt in LOCK_PX]

        def to_w(X, Z, H):
            return V((X, lid_y(cz + Z) - 0.02 - H, cz + Z))

        bm = bmesh.new()
        n = len(outline)
        scales = (1.0, 0.62, 0.3)
        top = []
        for s in scales:
            ring = []
            for (X, Z), tip in zip(outline, is_tip):
                h = he + (hc - he) * (1 - s) / (1 - scales[-1]) + (ridge * math.sin(pi * min(1.0, (1 - s) / 0.75)) if tip and s < 1 else 0.0)
                ring.append(bm.verts.new(to_w(X * s, Z * s, h)))
            top.append(ring)
        back = [bm.verts.new(to_w(X, Z, 0.0)) for X, Z in outline]
        cv = bm.verts.new(to_w(0, 0, hc + 0.02))
        for a, b in zip(top, top[1:]):
            for j in range(n):
                jj = (j + 1) % n
                bm.faces.new((a[j], a[jj], b[jj], b[j]))
        for j in range(n):
            bm.faces.new((top[-1][j], top[-1][(j + 1) % n], cv))
            bm.faces.new((back[j], back[(j + 1) % n], top[0][(j + 1) % n], top[0][j]))
        bm.faces.new(list(reversed(back)))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        rim = set(top[0])
        edges = [e for e in bm.edges if e.verts[0] in rim and e.verts[1] in rim]
        bmesh.ops.bevel(bm, geom=edges, offset=0.035, offset_type="OFFSET", segments=2, profile=0.5, affect="EDGES", clamp_overlap=True)
        bm.normal_update()
        return bm

    def steel_fn(tj=0.0):
        return zone_fn("steel", tj, bfun=lambda p, n: clamp(0.5 + p.x * 0.14 + (p.z - Z_SEAMLOCK) * 0.12))

    emit(B_, lock_plate(Z_SEAMLOCK, he=0.14, hc=0.32, ridge=0.16), steel_fn(0.4), 28)

    def socket(c, axis, R0=0.66):
        """Thick torus-like socket ring, darker steel inside, holding the orb."""
        prof = [(R0, -0.02), (R0 * 1.05, 0.12), (R0 * 0.96, 0.25), (R0 * 0.8, 0.3), (R0 * 0.64, 0.24), (R0 * 0.58, 0.06), (R0 * 0.3, 0.02)]
        return revolve(c, axis, prof, 16)

    def socket_fn(c, axis, R0, tj=0.0):
        axis = V(axis).normalized()

        def f(p, n, fc):
            d = p - c
            rr = (d - axis * d.dot(axis)).length
            inner = rr < R0 * 0.7
            return zone_uv("iron", clamp(0.1 + tj + 0.8 * lit01(n) + (0.35 if inner else 0.0)), posn(p, n, 0.12))
        return f

    # thick raised ring in the cup: outer rim, a bowl, the orb sitting in it like a lens
    RD = 0.68
    c_lock = V((0, -R - 0.02 - 0.2, Z_SEAMLOCK))
    boss = [(RD, -0.02), (RD * 1.05, 0.15), (RD * 0.98, 0.3), (RD * 0.84, 0.38), (RD * 0.7, 0.34), (RD * 0.6, 0.2),
            (RD * 0.5, 0.1), (RD * 0.2, 0.05)]
    emit(B_, revolve(c_lock, (0, -1, 0), boss, 20), socket_fn(c_lock, (0, -1, 0), RD * 0.7, 0.15), 55)
    emit(BM_, ellipsoid(c_lock + V((0, -0.2, 0)), RD * 0.56, 0.24, RD * 0.56, 14, 9), lambda p, n, fc: GEM, 80)
    for sx in (-1, 1):
        cs = V((sx * (XE + 0.02), 0, Z_ORB))
        emit(B_, socket(cs, (sx, 0, 0), 0.56), socket_fn(cs, (sx, 0, 0), 0.56), 40)
        emit(BM_, ellipsoid(cs + V((sx * 0.14, 0, 0)), 0.3, 0.3, 0.3, 12, 8), lambda p, n, fc: GEM, 80)

    # ======================= LID =======================
    L_, LM_ = "Chest_Lid", "Chest_LidMagic"
    NB = 8
    gap = (SEAM / 2) / R
    s_tot = SKIRT + pi * R

    def arc_s(p):
        return (p.z - ZL) if p.z <= ZC else SKIRT + R * phi_of(p)

    for i in range(NB):
        pa, pb = pi * i / NB + (gap if i else 0.0), pi * (i + 1) / NB - (gap if i < NB - 1 else 0.0)
        bo = bulge[i + 3] * 0.8
        prof_o = [(pa + (pb - pa) * q / 3) for q in range(4)]
        outer = [(-(R + bo) * math.cos(a), ZC + (R + bo) * math.sin(a)) for a in prof_o]
        inner = [(-(R - BOARD_T) * math.cos(a), ZC + (R - BOARD_T) * math.sin(a)) for a in reversed(prof_o)]
        if i == 0:
            outer = [(-(R + bo), ZL)] + outer
            inner = inner + [(-(R - BOARD_T), ZL)]
        if i == NB - 1:
            outer = outer + [(R + bo, ZL)]
            inner = [(R - BOARD_T, ZL)] + inner
        sec = outer + inner
        rings = []
        for q in range(4):
            x = -XLID + 2 * XLID * q / 3
            wob = 0.0 if q in (0, 3) else rnd.uniform(-0.012, 0.012)
            rings.append([V((x, y * (1 + wob / R) if j < len(outer) else y, z if j >= len(outer) else ZC + (z - ZC) * (1 + wob / R))) for j, (y, z) in enumerate(sec)])
        bm = sweep(rings)
        bevel(bm, 0.055, 2)
        sa = 0.0 if i == 0 else SKIRT + R * pa
        sb = s_tot if i == NB - 1 else SKIRT + R * pb
        if i == NB - 1:
            sa, sb = SKIRT + R * pa, SKIRT + R * pi + SKIRT
        band_i = BAND_LID0 + i
        a0 = A_FRONT if i == 0 else A_LID

        def uvf(p, n, fc, sa=sa, sb=sb, band_i=band_i, a0=a0, last=(i == NB - 1)):
            s = arc_s(p)
            if last and p.z <= ZC and p.y > 0:
                s = SKIRT + R * pi + (ZC - p.z)
            return board_uv(p.x + XLID + a0, (s - sa) / (sb - sa), band_i)
        emit(L_, bm, uvf)
        if i:
            a = pi * i / NB
            rh = V((0, -math.cos(a), math.sin(a)))
            tg = V((0, math.sin(a), math.cos(a)))
            c = V((0, 0, ZC))
            q = [c + rh * (R - 0.05) + tg * (gap * R + 0.006), c + rh * (R - 0.05) - tg * (gap * R + 0.006),
                 c + rh * (R - BOARD_T + 0.04) - tg * (gap * R + 0.006), c + rh * (R - BOARD_T + 0.04) + tg * (gap * R + 0.006)]
            rings = [[V((x, v.y, v.z)) for v in q] for x in (-XLID + 0.05, XLID - 0.05)]
            emit(LM_, sweep(rings), lambda p, n, fc: GEM)
    # ---- the skull, its own lid part (Chest_LidSkull), recreated from the painting: sculpted as
    #      a signed distance field (skull_env / skull_field above), meshed with surface nets,
    #      snapped onto the exact surface and decimated to soft facets; each vertex picks its
    #      colour from the painted skull table by cavity depth, ridges, the crack and the break.
    #      Long hooked fangs hug the lid's front curve; thick stitch loops close the crack. ----
    import numpy as np
    LS_ = "Chest_LidSkull"
    Msk, tsk = skull_place(np)
    cracks = skull_cracks(np)
    lidclip = (Msk, tsk, ZC, R)
    Vs, Qs = skull_surface(np, cracks, lidclip)
    me = bpy.data.meshes.new("skull_raw")
    me.from_pydata(Vs.tolist(), [], Qs.tolist())
    me.validate()
    ob = bpy.data.objects.new("skull_raw", me)
    coll.objects.link(ob)
    dec = ob.modifiers.new("soft_facets", "DECIMATE")
    dec.ratio = SKULL_TRIS / (2.0 * len(Qs))
    dec.use_collapse_triangulate = True
    me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    sk = bmesh.new()
    sk.from_mesh(me2)
    bpy.data.meshes.remove(me2)
    bmesh.ops.triangulate(sk, faces=sk.faces[:])
    # no slivers: a needle triangle at a crisp rim gets no baked texel and would show black
    for _ in range(4):
        short = {e for e in sk.edges if e.calc_length() < 0.016}
        for fc in sk.faces:
            longest = max(e.calc_length() for e in fc.edges)
            if longest > 0 and 2 * fc.calc_area() / longest < 0.01:
                short.add(min(fc.edges, key=lambda e: e.calc_length()))
        if not short:
            break
        bmesh.ops.collapse(sk, edges=list(short), uvs=False)
        bmesh.ops.dissolve_degenerate(sk, dist=1e-4, edges=sk.edges[:])
        bmesh.ops.triangulate(sk, faces=sk.faces[:])
    sk.normal_update()
    sk.verts.ensure_lookup_table()
    Vd = np.array([v.co[:] for v in sk.verts], np.float32)
    Nd = np.array([v.normal[:] for v in sk.verts], np.float32)
    pa, pb = skull_paint(np, Vd, Nd, cracks, lidclip)
    lay = sk.loops.layers.uv.new("UVMap")
    for fc in sk.faces:
        for lp in fc.loops:
            lp[lay].uv = zone_uv("skull", float(pa[lp.vert.index]), float(pb[lp.vert.index]))
    Mw = Matrix([[float(Msk[r][c]) for c in range(3)] + [float(tsk[r])] for r in range(3)] + [[0.0, 0.0, 0.0, 1.0]])
    Mr = Mw.to_3x3().normalized()
    bmesh.ops.transform(sk, matrix=Mw, verts=sk.verts[:])
    emit(LS_, sk, None, 40)

    fn_bone = lambda Q: skull_field(np, np.asarray(Q, np.float32), cracks, lidclip)[0]
    EYE3 = np.eye(3, dtype=np.float32) * 0.004

    def on_bone(q, lift=0.0):
        """A skull-local point snapped onto the finished bone: world point (lifted along the
        normal) and world normal."""
        def n_env(x):       # normal of the smooth, uncarved skull (no zero gradient in a groove)
            g_ = np.array([skull_env(np, x[None] + EYE3[i])[0] - skull_env(np, x[None] - EYE3[i])[0] for i in range(3)])
            return g_ / max(float(np.linalg.norm(g_)), 1e-9)
        q = np.asarray(q, np.float32)
        Q = skull_project(np, fn_bone, (q + n_env(q) * 0.06)[None].astype(np.float32), 10, cap=0.03)[0]
        nw = (Mr @ V(tuple(float(x) for x in n_env(Q)))).normalized()
        return Mw @ V(tuple(float(x) for x in Q)) + nw * lift, nw

    def lid_push(q, off):
        rv = V((0, q.y, q.z - ZC))
        if q.z > ZC - 0.5 and rv.length < R + off:
            rv = rv.normalized() * (R + off)
            return V((q.x, rv.y, rv.z + ZC))
        return q

    def fang_uv(n, s):
        return zone_uv("mauve", clamp(0.12 + 0.72 * lit01(n)), s)

    def fang(root_l, dir_l, length, r0, curl, lat, side, sides=7):
        """A long claw-fang from the upper jaw: it leaves the jaw forward and down, curls ever
        tighter toward the wood and hugs the lid's front curve, the tip hooking into it."""
        root, _ = on_bone(root_l, -0.03)
        d = (Mr @ V(dir_l)).normalized()
        n = 12
        step = length / n
        radii = [r0 * (1.0 - (i / n) ** 1.2) + 0.005 for i in range(n + 1)]
        xw = (Mr @ V((side, 0.0, 0.0))).normalized()
        pts = [root]
        for i in range(n):
            p = pts[-1]
            rv = V((0, p.y, p.z - ZC)).normalized()
            k_ = step * (0.5 + 1.3 * i / n)
            d = (d - rv * curl * k_ + xw * lat * k_).normalized()
            q = p + d * step
            r_min = R + radii[i + 1] * 0.95 if i < n - 1 else R - 0.04
            if math.hypot(q.y, q.z - ZC) < r_min:
                q = lid_push(q, r_min - R)
                d = (q - p).normalized()
            pts.append(q)
        T_, N_, B_n = frames(pts, V((1, 0, 0)))
        bm = bmesh.new()
        rings = [[bm.verts.new(pts[i] + N_[i] * (radii[i] * 0.84 * math.cos(2 * pi * j / sides)) + B_n[i] * (radii[i] * math.sin(2 * pi * j / sides)))
                  for j in range(sides)] for i in range(n)]
        tipv = bm.verts.new(pts[-1])
        along = {v: i / n for i, ring in enumerate(rings) for v in ring}
        along[tipv] = 1.0
        for a, b in zip(rings, rings[1:]):
            for j in range(sides):
                bm.faces.new((a[j], a[(j + 1) % sides], b[(j + 1) % sides], b[j]))
        for j in range(sides):
            bm.faces.new((rings[-1][j], rings[-1][(j + 1) % sides], tipv))
        bm.faces.new(list(reversed(rings[0])))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.normal_update()
        lay = bm.loops.layers.uv.new("UVMap")
        for fc in bm.faces:
            for lp in fc.loops:
                lp[lay].uv = fang_uv(fc.normal, 0.05 + 0.85 * along[lp.vert] ** 1.8)
        emit(LS_, bm, None, 50)

    # four per side round the U of the jaw: short front fangs, long canines, splayed side
    # claws and a big hook at the back corner -- as painted
    for s in (-1.0, 1.0):
        fang((s * 0.1, -0.93, -0.6), (s * 0.12, -1.1, -1.0), 0.44, 0.12, 2.8, -0.4, s)
        fang((s * 0.26, -0.86, -0.6), (s * 0.45, -1.0, -1.0), 0.62, 0.13, 2.5, -0.9, s)
        fang((s * 0.4, -0.7, -0.6), (s * 0.9, -0.8, -0.9), 0.7, 0.13, 2.4, -1.3, s)
        fang((s * 0.52, -0.46, -0.56), (s * 1.0, -0.45, -0.45), 0.98, 0.145, 2.6, -2.6, s)

    def stitch(q_l, tg_l, span=0.1, rad=0.036):
        """A thick mauve stitch loop across the crack: it leaves the bone on one side, arches
        over the crack and dives back in on the other."""
        c, nw = on_bone(q_l)
        sd = (Mr @ V(tuple(float(x) for x in tg_l))).cross(nw).normalized()
        S = SKULL_SCALE
        pts = [c + sd * (math.cos(th) * span * S) + nw * (math.sin(th) * span * S * 0.75 + 0.01)
               for th in (math.radians(-28 + 236 * k / 10) for k in range(11))]
        bm, _ = tube(pts, [rad * S] * len(pts), 6, up=nw)
        bm.normal_update()
        lay = bm.loops.layers.uv.new("UVMap")
        for fc in bm.faces:
            for lp in fc.loops:
                lp[lay].uv = zone_uv("mauve", clamp(0.3 + 0.7 * lit01(fc.normal)), 0.12)
        emit(LS_, bm, None, 50)

    def crack_at(line, f):
        L = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(line, axis=0), axis=1))])
        t = f * L[-1]
        i = int(np.clip(np.searchsorted(L, t) - 1, 0, len(line) - 2))
        return line[i] + (line[i + 1] - line[i]) * ((t - L[i]) / max(L[i + 1] - L[i], 1e-6)), line[i + 1] - line[i]

    for f in SK_STITCHES:                       # the row of stitches over the top of the dome
        q, tg = crack_at(cracks[0], f)
        stitch(q, tg)
    q, tg = crack_at(cracks[0], SK_STITCH_X)    # the cross stitch on the forehead
    for rot in (0.8, -0.8):
        c_, sn_ = math.cos(rot), math.sin(rot)
        nrm = q / np.linalg.norm(q)
        side = np.cross(tg, nrm)
        stitch(q, tg * c_ + side * sn_ * np.linalg.norm(tg) / max(np.linalg.norm(side), 1e-6), 0.085, 0.034)
    q, tg = crack_at(cracks[2], 0.5)            # the loop over the left brow
    stitch(q, tg, 0.09, 0.036)

    # ---- the chain: chunky 3D links from a staple by the left arch into the broken-open side ----
    A = V((-TB[0] + 0.02, (TB[2] + TB[3]) / 2 - 0.1, TB[5] - 0.45))
    hc, ha = skull_hole(np)
    Bp = Mw @ V(tuple(float(x) for x in hc + ha * 0.3))
    mid = lid_push((A + Bp) / 2 + V((0, 0, -0.1)), 0.14)
    cpath = catmull([A, mid, Bp], 8)

    Lc = [0.0]
    for a, b in zip(cpath, cpath[1:]):
        Lc.append(Lc[-1] + (b - a).length)

    def at(s):
        for i in range(len(Lc) - 1):
            if Lc[i + 1] >= s:
                f = (s - Lc[i]) / max(Lc[i + 1] - Lc[i], 1e-6)
                return cpath[i] + (cpath[i + 1] - cpath[i]) * f, (cpath[i + 1] - cpath[i]).normalized()
        return cpath[-1], (cpath[-1] - cpath[-2]).normalized()

    pitch = 0.3
    nlink = max(3, int(Lc[-1] / pitch))
    for li in range(nlink + 1):
        c, tg = at(min(li * Lc[-1] / nlink, Lc[-1]))
        radial = V((0, c.y, c.z - ZC)).normalized()
        pn = radial - tg * radial.dot(tg)
        pn.normalize()
        if li % 2:
            pn = tg.cross(pn).normalized()
        wv = pn.cross(tg).normalized()
        a_, b_, rr = 0.22, 0.12, 0.07
        loop = []
        for j in range(12):
            th = 2 * pi * j / 12
            loop.append(c + tg * (a_ * math.cos(th)) + wv * (b_ * math.sin(th)))
        rings = []
        for j, q in enumerate(loop):
            tng = (loop[(j + 1) % 12] - loop[j - 1]).normalized()
            ow = (q - c)
            ow = (ow - tng * ow.dot(tng)).normalized()
            e2 = tng.cross(ow)
            rings.append([q + (ow * math.cos(2 * pi * m / 6) + e2 * math.sin(2 * pi * m / 6)) * rr for m in range(6)])
        bm = sweep(rings, cap0=False, cap1=False)
        bm.verts.ensure_lookup_table()
        first, last = [bm.verts[j] for j in range(6)], [bm.verts[11 * 6 + j] for j in range(6)]
        for j in range(6):
            bm.faces.new((last[j], last[(j + 1) % 6], first[(j + 1) % 6], first[j]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        emit(L_, bm, zone_fn("iron", 0.3), 50)
    # staple anchoring the chain to the lid by the arch
    emit(L_, revolve(A - V((0.06, 0, 0)), (1, 0, 0), [(0.2, -0.05), (0.2, 0.05), (0.12, 0.1), (0.1, -0.02)], 10), zone_fn("iron", 0.0), 40)

    # ======================= LIGHT =======================
    G_, F_ = "Chest_Glow", "Chest_Inner"
    ring_o = aabb(-XE + 0.06, XE - 0.06, -R + 0.06, R - 0.06, ZT - 0.03, ZL + 0.03)
    ring_i = aabb(-XIN + 0.18, XIN - 0.18, -R + 0.18, R - 0.18, ZT - 0.2, ZL + 0.2)
    me_i = bpy.data.meshes.new("ri")
    ring_i.to_mesh(me_i)
    ring_i.free()
    # hollow the ring: outer box minus inner box
    me_o = bpy.data.meshes.new("ro")
    ring_o.to_mesh(me_o)
    ring_o.free()
    oo, oi = bpy.data.objects.new("ro", me_o), bpy.data.objects.new("ri", me_i)
    coll.objects.link(oo)
    coll.objects.link(oi)
    mm = oo.modifiers.new("hollow", "BOOLEAN")
    mm.operation, mm.solver, mm.object = "DIFFERENCE", "EXACT", oi
    dg = bpy.context.evaluated_depsgraph_get()
    me_r = bpy.data.meshes.new_from_object(oo.evaluated_get(dg))
    for o in (oo, oi):
        bpy.data.objects.remove(o)
    bm = bmesh.new()
    bm.from_mesh(me_r)
    bpy.data.meshes.remove(me_r)
    emit(G_, bm, lambda p, n, fc: GEM)

    # glowing pool of magic inside, domed toward the middle
    hx_, hy_ = XIN - 0.04, R - BOARD_T - 0.02
    zf = ZT - FLOOR_DEPTH
    pool = [(1.0, zf + 0.02), (0.98, zf + 0.3), (0.8, zf + 0.46), (0.5, zf + 0.56), (0.2, zf + 0.6)]
    rings = [[V((hx_ * s * math.cos(2 * pi * j / 16) * 1.08, hy_ * s * math.sin(2 * pi * j / 16) * 1.08, z)) for j in range(16)] for s, z in pool]
    for r_ in rings:
        for q in r_:
            q.x = clamp(q.x, -hx_, hx_)
            q.y = clamp(q.y, -hy_, hy_)
    emit(F_, sweep(rings), lambda p, n, fc: GEM, 60)

    parts = {}
    for name, kind in ((B_, "textured"), (L_, "textured"), (LS_, "textured"), (G_, "glow"), (F_, "floor"), (BM_, "accent"), (LM_, "accent")):
        parts[name] = (finish(name), kind)
    return {
        "parts": parts,
        # hinge on the base's back top edge: the lid's back-bottom edge pivots on it, so the
        # opened lid rests back against the chest instead of swinging out into the air
        "hinge": (0.0, R + 0.03, (ZT + ZL) / 2),
        "open": {"rotate_x_deg": 102.0},
    }
