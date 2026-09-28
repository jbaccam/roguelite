"""Wooden chest (Common tier, 3 keys): the plain workhorse chest. Approved 2026-09-27.

Warm orange planks, dark iron straps and corner guards, a barrel lid with seven boards,
a big hex lock and lantern-gold light leaking from the lid gap. No ornament: every
later tier is a different, grander chest.

Shape reference: the rounded-lid chests the user supplied on 2026-09-27.
Tier files are plain Python at the top level (no bpy / mathutils / numpy imports), so
author_textures.py can read PALETTE from system Python; build(k) runs inside Blender.
"""

NAME = "Wooden"

# sRGB 0-255. GLOW goes on the Roblox Neon parts (seam, keyhole, floor).
GLOW = (255, 184, 64)

# Painted source atlas (author_textures.py); the bake adds the icon lighting on top.
PALETTE = {
    # Warm, saturated planks like the weapon icons (baseball bat, nunchuck handle).
    "wood": (178, 98, 48), "wood_dark": (110, 52, 24), "wood_light": (226, 150, 84),
    "gap": (60, 28, 14),
    # Icon-style iron: dark grey with a cool cast (frying pan, wrecking ball).
    "metal": (66, 70, 82), "metal_dark": (34, 36, 44), "metal_light": (112, 120, 138),
    # Swatches: bolt heads, keyhole / interior dark, gem.
    "rivet": (170, 176, 190), "keyhole": (22, 18, 16), "gem": (255, 214, 120),
}

# ---------------------------------------------------------------------------
# dimensions (studs) -- chunky, slightly exaggerated like the icons
# ---------------------------------------------------------------------------
W, D = 6.0, 4.4          # width (x) and depth (y)
FOOT = 0.42              # feet lift the body off the ground
HB = 2.4                 # body height
ZT = FOOT + HB           # top of the base
GAP = 0.13               # lid gap the glow leaks through
ZL = ZT + GAP            # bottom of the lid
SKIRT = 0.34             # straight part of the lid, under the lid rim band
RISE = 1.95              # arch height above the skirt: a proud, domed lid
ARCH = 7                 # arch boards
XS = 1.8                 # strap centre lines (x = +-XS)
STRAP = 0.64
BAND_H = 0.5
OUT_BAND, OUT_STRAP, OUT_GUARD = 0.13, 0.19, 0.21   # how far metal stands proud of the wood
IN = 0.30                # opening inset: rim band inner edge and inner walls line up here
WALL = OUT_BAND + IN
BOARD_T = 0.24
SEAM = 0.05              # groove between boards
FLOOR_DEPTH = 0.9
PLANK = HB / 4.0         # four boards per body face; also the painted band size
BULGE = [0.02, 0.0, 0.035, 0.01, 0.0, 0.03, 0.015, 0.0, 0.025, 0.005, 0.03, 0.0, 0.01, 0.03, 0.0, 0.02]


def build(k):
    V, math = k.Vector, k.math
    wood_uv = lambda a, b, band: k.primary_uv(a, b, band, PLANK)
    band_uv = lambda a, t, band: k.band_uv(a, t, band, PLANK)
    metal, dark, gem = k.metal, k.dark, k.gem

    def arch():
        return [(-D / 2 * math.cos(math.pi * i / ARCH), ZL + SKIRT + RISE * math.sin(math.pi * i / ARCH)) for i in range(ARCH + 1)]

    # ---------------- base ----------------
    b = k.Builder()
    x0, x1, y0, y1 = -W / 2, W / 2, -D / 2, D / 2
    for fi, face in enumerate(("-y", "+y", "-x", "+x")):
        for i in range(4):
            band = fi * 4 + i
            za, zb = FOOT + i * PLANK + SEAM / 2, FOOT + (i + 1) * PLANK - SEAM / 2
            bulge = BULGE[band]
            if face == "-y":
                box, along = (x0, x1, y0 - bulge, y0 + BOARD_T, za, zb), (lambda p: p.x)
            elif face == "+y":
                box, along = (x0, x1, y1 - BOARD_T, y1 + bulge, za, zb), (lambda p: p.x)
            elif face == "-x":
                box, along = (x0 - bulge, x0 + BOARD_T, y0, y1, za, zb), (lambda p: p.y)
            else:
                box, along = (x1 - BOARD_T, x1 + bulge, y0, y1, za, zb), (lambda p: p.y)
            b.box(*box, lambda p, f, band=band, along=along, za=za, zb=zb: band_uv(along(p), (p.z - za) / (zb - za), band))
    zf = ZT - FLOOR_DEPTH
    b.box(x0 + 0.12, x1 - 0.12, y0 + 0.12, y1 - 0.12, FOOT, zf, dark)
    ix0, ix1, iy0, iy1 = x0 + IN, x1 - IN, y0 + IN, y1 - IN
    corners = [(ix0, iy0), (ix1, iy0), (ix1, iy1), (ix0, iy1)]
    b.begin()
    for i, band in zip(range(4), (1, 9, 5, 13)):
        (ax, ay), (bx, by) = corners[i], corners[(i + 1) % 4]
        pts = [V((bx, by, zf)), V((ax, ay, zf)), V((ax, ay, ZT - BAND_H)), V((bx, by, ZT - BAND_H))]
        along = (lambda p: p.x) if i % 2 == 0 else (lambda p: p.y)
        b.poly(pts, [wood_uv(along(p), p.z - zf, band) for p in pts])
    b.ring(x0 + 0.1, x1 - 0.1, y0 + 0.1, y1 - 0.1, zf, ZT - 0.02, IN - 0.13, dark)   # behind the inner walls
    b.ring(x0 - OUT_BAND, x1 + OUT_BAND, y0 - OUT_BAND, y1 + OUT_BAND, FOOT, FOOT + BAND_H, WALL, metal)
    b.ring(x0 - OUT_BAND, x1 + OUT_BAND, y0 - OUT_BAND, y1 + OUT_BAND, ZT - BAND_H, ZT, WALL, metal)
    g, lip = OUT_GUARD, 0.58
    for sx in (-1, 1):
        for sy in (-1, 1):
            ex, ey = sx * (W / 2 + g), sy * (D / 2 + g)
            ix, iy = sx * (W / 2 - lip), sy * (D / 2 - lip)
            b.box(min(ex, ix), max(ex, ix), min(ey, sy * (D / 2 - 0.02)), max(ey, sy * (D / 2 - 0.02)), FOOT - 0.03, ZT + 0.01, metal)
            b.box(min(ex, sx * (W / 2 - 0.02)), max(ex, sx * (W / 2 - 0.02)), min(ey, iy), max(ey, iy), FOOT - 0.03, ZT + 0.01, metal)
            fx, fy = sx * (W / 2 + g + 0.04), sy * (D / 2 + g + 0.04)
            b.box(min(fx, fx - sx * 0.8), max(fx, fx - sx * 0.8), min(fy, fy - sy * 0.8), max(fy, fy - sy * 0.8), 0.0, FOOT + 0.02, metal)
    for sx in (-1, 1):
        for z in (FOOT + 0.3, ZT - 0.3):
            b.rivet(sx * (W / 2 - 0.2), z, y0 - g)
    for sx in (-1, 1):
        cx = sx * XS
        b.box(cx - STRAP / 2, cx + STRAP / 2, y0 - OUT_STRAP, y0 + 0.02, FOOT - 0.03, ZT + 0.01, metal)
        b.box(cx - STRAP / 2, cx + STRAP / 2, y1 - 0.02, y1 + OUT_STRAP, FOOT - 0.03, ZT + 0.01, metal)
        for z in (FOOT + 0.25, ZT - 0.25):
            b.rivet(cx, z, y0 - OUT_STRAP)
    zc = ZT - 0.02
    b.prism((0, zc), 0.95, 6, y0 - 0.44, y0 - 0.12, metal)
    b.prism((0, zc), 0.64, 6, y0 - 0.56, y0 - 0.43, metal)
    b.box(-0.1, 0.1, y0 - 0.58, y0 - 0.55, zc - 0.28, zc + 0.12, dark)
    b.prism((0, zc + 0.14), 0.14, 8, y0 - 0.58, y0 - 0.55, dark)
    base = b

    # ---------------- lid ----------------
    b = k.Builder()
    prof = arch()
    xo = W / 2 + 0.06
    for i in range(ARCH):
        (ya, za), (yb, zb) = prof[i], prof[i + 1]
        a, c = V((0, ya, za)), V((0, yb, zb))
        along = (c - a).normalized()
        a, c = a + along * SEAM / 2, c - along * SEAM / 2
        n = V((0, -(zb - za), yb - ya)).normalized()
        lift = n * BULGE[i + 3] * 0.8
        o0, o1, i0, i1 = a + lift, c + lift, a - n * BOARD_T, c - n * BOARD_T
        band = 2 + i
        b.begin()
        uvq = lambda ts, xs, band=band: [band_uv(x, t, band) for x, t in zip(xs, ts)]
        L, R = -xo, xo
        quad = lambda P, Q, xa, xb: [V((xa, P.y, P.z)), V((xb, P.y, P.z)), V((xb, Q.y, Q.z)), V((xa, Q.y, Q.z))]
        b.poly(quad(o0, o1, L, R), uvq([0, 0, 1, 1], [L, R, R, L]))
        b.poly(quad(i1, i0, L, R), uvq([1, 1, 0, 0], [L, R, R, L]))
        b.poly(quad(i0, o0, L, R), uvq([0, 0, 0.05, 0.05], [L, R, R, L]))
        b.poly(quad(o1, i1, L, R), uvq([0.95, 0.95, 1, 1], [L, R, R, L]))
        for x, flip in ((L, False), (R, True)):
            e = [V((x, i0.y, i0.z)), V((x, o0.y, o0.z)), V((x, o1.y, o1.z)), V((x, i1.y, i1.z))]
            if flip:
                e.reverse()
            b.poly(e, [band_uv(x, 0.5, band)] * 4)
    b.begin()
    core = [(-D / 2, ZL + 0.02)] + k.offset_profile(prof, -BOARD_T + 0.01) + [(D / 2, ZL + 0.02)]
    xc = W / 2 - 0.01
    for i in range(len(core) - 1):
        (ya, za), (yb, zb) = core[i], core[i + 1]
        b.poly([V((-xc, ya, za)), V((xc, ya, za)), V((xc, yb, zb)), V((-xc, yb, zb))], [k.swatch_uv("dark")] * 4)
    for sx, band in ((-1, 10), (1, 13)):
        pts = [V((sx * xc, y, z)) for y, z in core]
        if sx > 0:
            pts.reverse()
        b.poly(pts, [wood_uv(p.y, p.z - ZL, band) for p in pts])
    under = [V((-xc, -D / 2, ZL + 0.02)), V((-xc, D / 2, ZL + 0.02)), V((xc, D / 2, ZL + 0.02)), V((xc, -D / 2, ZL + 0.02))]
    b.poly(under, [wood_uv(p.x, p.y + D / 2, 8) for p in under])
    b.ring(-W / 2 - OUT_BAND, W / 2 + OUT_BAND, -D / 2 - OUT_BAND, D / 2 + OUT_BAND, ZL, ZL + SKIRT + 0.04, WALL, metal)
    full = [(-D / 2, ZL)] + prof + [(D / 2, ZL)]
    inner, outer = k.offset_profile(full, 0.0), k.offset_profile(full, OUT_STRAP)
    for sx in (-1, 1):
        cx = sx * XS
        xa, xb = cx - STRAP / 2, cx + STRAP / 2
        s = 0.0
        for i in range(len(full) - 1):
            seg = math.hypot(outer[i + 1][0] - outer[i][0], outer[i + 1][1] - outer[i][1])
            oa, ob, ia, ib = outer[i], outer[i + 1], inner[i], inner[i + 1]
            b.poly([V((xa, *oa)), V((xb, *oa)), V((xb, *ob)), V((xa, *ob))],
                   [k.metal_uv(s, 0.2), k.metal_uv(s, 0.2 + STRAP), k.metal_uv(s + seg, 0.2 + STRAP), k.metal_uv(s + seg, 0.2)])
            for xe, flip in ((xa, True), (xb, False)):
                side = [V((xe, *ia)), V((xe, *oa)), V((xe, *ob)), V((xe, *ib))]
                uv = [k.metal_uv(s, 1.0), k.metal_uv(s, 1.2), k.metal_uv(s + seg, 1.2), k.metal_uv(s + seg, 1.0)]
                if not flip:
                    side.reverse()
                    uv.reverse()
                b.poly(side, uv)
            s += seg
        for i in (0, len(full) - 1):
            o, n_ = outer[i], inner[i]
            cap = [V((xa, *n_)), V((xb, *n_)), V((xb, *o)), V((xa, *o))]
            if i == 0:
                cap.reverse()
            b.poly(cap, [k.metal_uv(0, 2.0), k.metal_uv(0, 2.6), k.metal_uv(0.2, 2.6), k.metal_uv(0.2, 2.0)])
        b.rivet(cx, ZL + SKIRT * 0.55, -D / 2 - OUT_STRAP)
    lid = b

    # ---------------- light ----------------
    b = k.Builder()
    inset = 0.06
    b.ring(-W / 2 + inset, W / 2 - inset, -D / 2 + inset, D / 2 - inset, ZT - 0.04, ZL + 0.03, 0.12, gem)
    b.box(-0.07, 0.07, -D / 2 - 0.60, -D / 2 - 0.585, zc - 0.25, zc + 0.10, gem)
    b.prism((0, zc + 0.14), 0.1, 8, -D / 2 - 0.60, -D / 2 - 0.585, gem)
    seam = b
    b = k.Builder()
    fx0, fx1, fy0, fy1 = -W / 2 + IN + 0.01, W / 2 - IN - 0.01, -D / 2 + IN + 0.01, D / 2 - IN - 0.01
    zfl = ZT - FLOOR_DEPTH + 0.05
    b.box(fx0, fx1, fy0, fy1, zfl - 0.04, zfl, gem)      # a slab, not a plane: flat MeshParts import badly
    floor = b

    return {
        "parts": {
            "Chest_Base": (base, "textured"),
            "Chest_Lid": (lid, "textured"),
            "Chest_Glow": (seam, "glow"),
            "Chest_Inner": (floor, "floor"),
        },
        "hinge": (0.0, D / 2 + OUT_BAND, ZL),
        "open": {"rotate_x_deg": 105.0},
    }
