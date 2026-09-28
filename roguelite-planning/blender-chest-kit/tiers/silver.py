"""Silver chest (Rare tier, 8 keys): "the knight's chest".

The Wooden chest's shape, upgraded: same rectangular body, barrel lid, two straps lining
up over lid and body, rim bands, corner guards, feet, a lock on the seam and light leaking
from the lid gap -- about 4% bigger and heavier. What makes it the Rare chest is built into
the chest itself:

* boards painted a rich cobalt with lighter worn edges instead of bare planks;
* polished steel instead of dark iron: thicker bands with a raised bead on the seam collar,
  thicker straps with a raised centre rib and neat rows of steel rivets;
* armoured corner plates, each face carrying a raised diamond boss set with a sapphire;
* a steel ridge rail along the top of the lid and steel end frames following the arch;
* a shield-shaped crest lock with a blue enamel field and a big faceted sapphire above
  the keyhole;
* stepped steel feet and a cool blue glow.

Nothing floats above it, and it stays plain enough (no crowns, wings or crystals) to leave
room for Gold, Magical and Legendary.

Tier files are plain Python at the top level (no bpy / mathutils / numpy imports), so
author_textures.py can read PALETTE from system Python; build(k) runs inside Blender.
"""

NAME = "Silver"

# sRGB 0-255. GLOW goes on the Roblox Neon parts (seam, keyhole, floor).
GLOW = (80, 175, 255)

# Painted source atlas (author_textures.py); the bake adds the icon lighting on top.
PALETTE = {
    # Cobalt-painted boards: deep steel-blue paint, darker lower edge, pale worn edges.
    "wood": (42, 76, 150), "wood_dark": (18, 32, 80), "wood_light": (98, 140, 202),
    "gap": (10, 16, 40),
    # Polished steel: mid blue-grey with a real value range (not white, not lavender).
    "metal": (106, 115, 132), "metal_dark": (50, 55, 68), "metal_light": (168, 178, 196),
    # Swatches: rivet heads, keyhole / interior dark, sapphire, enamel, sapphire table, bezel.
    "rivet": (150, 160, 178), "keyhole": (14, 18, 34), "gem": (30, 80, 226),
    "swatch4": (20, 36, 94), "swatch5": (120, 190, 255), "swatch6": (74, 82, 98),
}

# Deeper shadow planes and cool, bright bevel highlights: polished, not bleached.
BAKE = {
    "key_lo": 0.55, "key_hi": 1.08, "rim": 0.12, "rim_color": (0.55, 0.68, 0.95),
    "edge": 0.66, "edge_tint": (0.86, 0.93, 1.0), "edge_tint_mix": 0.55,
}


def paint_primary(np, rng, w, h, p, tools):
    """Cobalt-painted boards: broad brushy value patches, a pale lit top edge, a dark lower
    edge and chipped lighter paint along the edges. No knots: the paint covers the wood."""
    smooth_noise, col, lerp, BANDS = tools["smooth_noise"], tools["col"], tools["lerp"], tools["BANDS"]
    band_h = h / BANDS
    rows = np.arange(h, dtype=np.float32)
    band = np.floor(rows / band_h).astype(int)
    within = (rows - band * band_h) / band_h
    base = np.empty((h, w, 3), np.float32)
    value = rng.uniform(-0.09, 0.09, BANDS)
    for k in range(BANDS):
        base[band == k] = col(p["wood"]) * (1 + value[k])
    patches = smooth_noise(h, w, 10, 7, rng) * 0.22 + smooth_noise(h, w, 24, 16, rng) * 0.08
    brush = smooth_noise(h, w, 80, 5, rng) * 0.10                   # soft strokes along the board
    base *= (1 + patches + brush)[..., None]
    top = (np.clip(1 - within / 0.2, 0, 1) ** 1.4)[:, None]
    bottom = (np.clip((within - 0.6) / 0.4, 0, 1) ** 1.5)[:, None]
    base = lerp(base, col(p["wood_light"]), top * 0.55)
    base = lerp(base, col(p["wood_dark"]), bottom * 0.6)
    # Chipped, lighter paint along both board edges.
    edge = np.maximum(np.clip(1 - within / 0.26, 0, 1), np.clip((within - 0.8) / 0.2, 0, 1))[:, None]
    chips = np.clip((smooth_noise(h, w, 48, 12, rng) - 0.06) * 4, 0, 1)
    base = lerp(base, col(p["wood_light"]) * 1.08, np.clip(chips * edge * 0.55, 0, 1))
    gap = (within > 0.955) | (within < 0.012)
    base[gap] = col(p["gap"])
    for k in range(BANDS):
        for _ in range(rng.integers(0, 2)):
            x = int(rng.uniform(0.15, 0.85) * w)
            y0, y1 = int(k * band_h + 2), int((k + 1) * band_h - 3)
            base[y0:y1, x:x + 7] = col(p["gap"])
            base[y0:y1, x + 7:x + 12] = lerp(base[y0:y1, x + 7:x + 12], col(p["wood_light"]), np.full((y1 - y0, 5), 0.4))
    return np.clip(base, 0, 1)


def paint_metal(np, rng, w, h, p, tools):
    """Polished steel: broad light and dark patches with a stronger swing than the iron."""
    smooth_noise, col, lerp = tools["smooth_noise"], tools["col"], tools["lerp"]
    base = np.broadcast_to(col(p["metal"]), (h, w, 3)).copy()
    broad = smooth_noise(h, w, 7, 3, rng) * 1.0 + smooth_noise(h, w, 18, 7, rng) * 0.35
    t = np.clip(broad, -0.5, 0.5) * 2
    base = lerp(base, col(p["metal_light"]), np.clip(t, 0, None) * 0.55)
    base = lerp(base, col(p["metal_dark"]), np.clip(-t, 0, None) * 0.45)
    # A few soft polish glints running across the bands and straps (every ~2.5 studs).
    rows = np.arange(h, dtype=np.float32)
    glint = np.zeros(h, np.float32)
    for c in rng.uniform(0, h, 6):
        glint = np.maximum(glint, np.exp(-((rows - c) / (h * 0.025)) ** 2))
    wobble = np.clip(1 + smooth_noise(h, w, 6, 4, rng) * 1.2, 0, 1)
    base = lerp(base, col(p["metal_light"]) * 1.05, glint[:, None] * wobble * 0.45)
    return np.clip(base, 0, 1)

# ---------------------------------------------------------------------------
# dimensions (studs) -- the Wooden chest's proportions, ~4% bigger, heavier metal
# ---------------------------------------------------------------------------
W, D = 6.24, 4.58        # width (x) and depth (y)
FOOT = 0.46              # feet lift the body off the ground
HB = 2.5                 # body height
ZT = FOOT + HB           # top of the base
GAP = 0.13               # lid gap the glow leaks through
ZL = ZT + GAP            # bottom of the lid
SKIRT = 0.36             # straight part of the lid, under the lid rim band
RISE = 2.02              # arch height above the skirt
ARCH = 7                 # arch boards
XS = 1.84                # strap centre lines (x = +-XS)
STRAP = 0.74
BAND_H = 0.56
OUT_BAND, OUT_STRAP, OUT_GUARD = 0.15, 0.24, 0.28   # how far metal stands proud of the boards
BEAD, BEAD_H = 0.06, 0.16                           # raised bead along the seam collar bands
RIB, RIB_W = 0.08, 0.24                             # raised centre rib on every strap
IN = 0.30                # opening inset: rim band inner edge and inner walls line up here
WALL = OUT_BAND + IN
BOARD_T = 0.25
SEAM = 0.05              # groove between boards
FLOOR_DEPTH = 0.92
PLANK = HB / 4.0         # four boards per body face; also the painted band size
BULGE = [0.02, 0.0, 0.035, 0.01, 0.0, 0.03, 0.015, 0.0, 0.025, 0.005, 0.03, 0.0, 0.01, 0.03, 0.0, 0.02]


def build(k):
    V, math = k.Vector, k.math
    wood_uv = lambda a, b, band: k.primary_uv(a, b, band, PLANK)
    band_uv = lambda a, t, band: k.band_uv(a, t, band, PLANK)
    metal, dark, gem = k.metal, k.dark, k.gem
    rivet_sw, enamel, table, bezel = k.swatch("rivet"), k.swatch("swatch4"), k.swatch_uv("swatch5"), k.swatch("swatch6")
    gem_uv = k.swatch_uv("gem")

    def arch():
        return [(-D / 2 * math.cos(math.pi * i / ARCH), ZL + SKIRT + RISE * math.sin(math.pi * i / ARCH)) for i in range(ARCH + 1)]

    # ---------------- small oriented pieces (studs, bosses, gems) ----------------
    def basis(n):
        n = V(n).normalized()
        t1 = V((0, 0, 1)).cross(n) if abs(n.z) < 0.9 else V((1, 0, 0)).cross(n)
        t1.normalize()
        return n, t1, n.cross(t1)

    def ring_at(c, n, r, sides, rot=0.0):
        n, t1, t2 = basis(n)
        return [V(c) + (t1 * math.cos(rot + j * 2 * math.pi / sides) + t2 * math.sin(rot + j * 2 * math.pi / sides)) * r
                for j in range(sides)]

    def stud(b, c, n, r=0.12, h=0.1, sides=6):
        """Domed steel rivet head standing out of a surface along n (not bevelled: cheap)."""
        n = V(n).normalized()
        c = V(c) - n * 0.01
        rings = [ring_at(c, n, r, sides, math.pi / sides), ring_at(c + n * h * 0.5, n, r, sides, math.pi / sides),
                 ring_at(c + n * h, n, r * 0.6, sides, math.pi / sides)]
        b.loft(rings, rivet_sw, cap0=False, chamfer=0.0)

    def sapphire(b, c, n, r, h, sides=8):
        """Faceted gem: pavilion into the setting, girdle, twisted crown up to a pale table."""
        n = V(n).normalized()
        c = V(c)
        rings = [ring_at(c, n, r * 0.8, sides), ring_at(c + n * h * 0.32, n, r, sides),
                 ring_at(c + n * h, n, r * 0.52, sides, math.pi / sides)]
        b.loft(rings, lambda p, t: table if t == "cap1" else gem_uv, cap0=False, chamfer=0.0)

    def diamond_boss(b, c, n, r, h):
        """Raised steel diamond (square pyramid frustum turned 45 deg) with a sapphire on top."""
        n = V(n).normalized()
        c = V(c) - n * 0.02
        rings = [ring_at(c, n, r, 4, math.pi / 2 * 0), ring_at(c + n * h, n, r * 0.62, 4)]
        b.loft(rings, lambda p, t: k.metal_uv(p.x + p.y + 10, p.z + 10), cap0=False, chamfer=0.03)
        sapphire(b, c + n * (h - 0.01), n, r * 0.46, 0.15)

    def plate(b, pts2d, y_front, y_back, uvf, chamfer=None):
        """Extrude a convex outline given counter-clockwise in (x, z) toward -Y."""
        back = [V((x, y_back, z)) for x, z in pts2d]
        front = [V((x, y_front, z)) for x, z in pts2d]
        b.loft([back, front], uvf, chamfer=chamfer)

    def arch_band(b, full, xa, xb, off_in, off_out):
        """A steel band following the lid profile, like the Wooden straps (offsets in studs)."""
        inner, outer = k.offset_profile(full, off_in), k.offset_profile(full, off_out)
        b.begin()
        s = 0.0
        w = xb - xa
        for i in range(len(full) - 1):
            seg = math.hypot(outer[i + 1][0] - outer[i][0], outer[i + 1][1] - outer[i][1])
            oa, ob, ia, ib = outer[i], outer[i + 1], inner[i], inner[i + 1]
            b.poly([V((xa, *oa)), V((xb, *oa)), V((xb, *ob)), V((xa, *ob))],
                   [k.metal_uv(s, 0.2), k.metal_uv(s, 0.2 + w), k.metal_uv(s + seg, 0.2 + w), k.metal_uv(s + seg, 0.2)])
            b.poly([V((xa, *ib)), V((xb, *ib)), V((xb, *ia)), V((xa, *ia))],
                   [k.metal_uv(s + seg, 1.6), k.metal_uv(s + seg, 1.6 + w), k.metal_uv(s, 1.6 + w), k.metal_uv(s, 1.6)])
            dep = off_out - off_in
            for xe, flip in ((xa, True), (xb, False)):
                side = [V((xe, *ia)), V((xe, *oa)), V((xe, *ob)), V((xe, *ib))]
                uv = [k.metal_uv(s, 1.0), k.metal_uv(s, 1.0 + dep), k.metal_uv(s + seg, 1.0 + dep), k.metal_uv(s + seg, 1.0)]
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
            b.poly(cap, [k.metal_uv(0, 2.0), k.metal_uv(0, 2.0 + w), k.metal_uv(0.2, 2.0 + w), k.metal_uv(0.2, 2.0)])
        return inner, outer

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
    # Thick steel rim bands; the seam collar carries a raised bead.
    ob = OUT_BAND
    b.ring(x0 - ob, x1 + ob, y0 - ob, y1 + ob, FOOT, FOOT + BAND_H, WALL, metal)
    b.ring(x0 - ob, x1 + ob, y0 - ob, y1 + ob, ZT - BAND_H, ZT, WALL, metal)
    zb_mid = ZT - BAND_H * 0.5
    b.ring(x0 - ob - BEAD, x1 + ob + BEAD, y0 - ob - BEAD, y1 + ob + BEAD, zb_mid - BEAD_H / 2, zb_mid + BEAD_H / 2, BEAD + 0.1, metal, chamfer=0.035)
    # Armoured corner plates: L-shaped steel with a diamond boss and sapphire on each face.
    g, lip = OUT_GUARD, 0.74
    zmid = (FOOT + ZT) / 2
    for sx in (-1, 1):
        for sy in (-1, 1):
            ex, ey = sx * (W / 2 + g), sy * (D / 2 + g)
            ix, iy = sx * (W / 2 - lip), sy * (D / 2 - lip)
            b.box(min(ex, ix), max(ex, ix), min(ey, sy * (D / 2 - 0.02)), max(ey, sy * (D / 2 - 0.02)), FOOT - 0.04, ZT + 0.02, metal)
            b.box(min(ex, sx * (W / 2 - 0.02)), max(ex, sx * (W / 2 - 0.02)), min(ey, iy), max(ey, iy), FOOT - 0.04, ZT + 0.02, metal)
            # stepped steel feet: a block on a wider plinth
            fx, fy = sx * (W / 2 + g + 0.05), sy * (D / 2 + g + 0.05)
            b.box(min(fx, fx - sx * 0.86), max(fx, fx - sx * 0.86), min(fy, fy - sy * 0.86), max(fy, fy - sy * 0.86), 0.12, FOOT + 0.02, metal)
            px, py = fx + sx * 0.06, fy + sy * 0.06
            b.box(min(px, px - sx * 0.98), max(px, px - sx * 0.98), min(py, py - sy * 0.98), max(py, py - sy * 0.98), 0.0, 0.16, metal)
            # front / back face of the plate
            cxg = (ex + ix) / 2
            diamond_boss(b, (cxg, ey, zmid), (0, sy, 0), 0.4, 0.13)
            # side face of the plate
            cyg = (ey + iy) / 2
            diamond_boss(b, (ex, cyg, zmid), (sx, 0, 0), 0.4, 0.13)
            for z in (FOOT + 0.3, ZT - 0.3):
                stud(b, (cxg, ey, z), (0, sy, 0))
                stud(b, (ex, cyg, z), (sx, 0, 0))
    # Straps with a raised centre rib and a rivet row down each side of it.
    for sx in (-1, 1):
        cx = sx * XS
        for yf, ys in ((y0 - OUT_STRAP, -1), (y1 + OUT_STRAP, 1)):
            b.box(cx - STRAP / 2, cx + STRAP / 2, min(yf, yf - ys * (OUT_STRAP + 0.02)), max(yf, yf - ys * (OUT_STRAP + 0.02)),
                  FOOT - 0.04, ZT + 0.02, metal)
            b.box(cx - RIB_W / 2, cx + RIB_W / 2, min(yf + ys * RIB, yf - ys * 0.02), max(yf + ys * RIB, yf - ys * 0.02),
                  FOOT + 0.02, ZT - 0.02, metal, chamfer=0.04)
        for dx in (-0.23, 0.23):
            for z in (FOOT + 0.3, zmid, ZT - 0.3):
                stud(b, (cx + dx, y0 - OUT_STRAP, z), (0, -1, 0), r=0.1, h=0.09)
    # Rivet row on the lower band, front and sides.
    for x in (-1.05, -0.38, 0.38, 1.05):
        stud(b, (x, y0 - ob, FOOT + BAND_H / 2), (0, -1, 0), r=0.1, h=0.09)
    for sx in (-1, 1):
        for y in (-0.62, 0.0, 0.62):
            stud(b, (sx * (W / 2 + ob), y, FOOT + BAND_H / 2), (sx, 0, 0), r=0.1, h=0.09)

    # Shield crest lock straddling the seam.
    zc = ZT - 0.02

    def shield(w, top, sh, bot, peak):
        left = [(-w / 2, sh)]
        for j in range(1, 5):
            t = j / 5
            # quadratic curve from the shoulder down to the point
            x = (1 - t) ** 2 * (-w / 2) + 2 * (1 - t) * t * (-w / 2) + t * t * 0
            z = (1 - t) ** 2 * sh + 2 * (1 - t) * t * (bot + (sh - bot) * 0.3) + t * t * bot
            left.append((x, z))
        right = [(-x, z) for x, z in reversed(left)]
        return [(-w / 2 + 0.1, top), (-w / 2, top - 0.1)] + left + [(0, bot)] + right + [(w / 2, top - 0.1), (w / 2 - 0.1, top), (0, top + peak)]

    shield_uv = lambda p, t: k.metal_uv(p.x + 10.0, p.z + 10.0)
    outer_sh = shield(1.96, zc + 0.94, zc - 0.22, zc - 1.28, 0.14)
    plate(b, outer_sh, y0 - 0.5, y0 - 0.12, shield_uv, chamfer=0.07)
    inner_sh = shield(1.56, zc + 0.76, zc - 0.2, zc - 1.02, 0.1)
    plate(b, inner_sh, y0 - 0.58, y0 - 0.46, enamel, chamfer=0.03)
    gz = zc + 0.3
    b.prism((0, gz), 0.38, 8, y0 - 0.66, y0 - 0.54, bezel, rot=math.pi / 8, chamfer=0.03)
    sapphire(b, (0, y0 - 0.64, gz), (0, -1, 0), 0.32, 0.26)
    kz = zc - 0.42
    b.prism((0, kz + 0.02), 0.26, 8, y0 - 0.62, y0 - 0.54, bezel, rot=math.pi / 8, chamfer=0.025)
    b.box(-0.075, 0.075, y0 - 0.645, y0 - 0.615, kz - 0.2, kz + 0.02, dark, chamfer=0.0)
    b.prism((0, kz + 0.06), 0.11, 8, y0 - 0.645, y0 - 0.615, dark, chamfer=0.0)
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
    # Lid collar band with its own bead, matching the body's seam collar.
    b.ring(-W / 2 - ob, W / 2 + ob, -D / 2 - ob, D / 2 + ob, ZL, ZL + SKIRT + 0.04, WALL, metal)
    zs = ZL + (SKIRT + 0.04) * 0.5
    b.ring(-W / 2 - ob - BEAD, W / 2 + ob + BEAD, -D / 2 - ob - BEAD, D / 2 + ob + BEAD, zs - BEAD_H / 2, zs + BEAD_H / 2, BEAD + 0.1, metal, chamfer=0.035)
    full = [(-D / 2, ZL)] + prof + [(D / 2, ZL)]
    # Straps with a centre rib.
    for sx in (-1, 1):
        cx = sx * XS
        inner, outer = arch_band(b, full, cx - STRAP / 2, cx + STRAP / 2, 0.0, OUT_STRAP)
        arch_band(b, full, cx - RIB_W / 2, cx + RIB_W / 2, OUT_STRAP - 0.02, OUT_STRAP + RIB)
        for dx in (-0.23, 0.23):
            stud(b, (cx + dx, -D / 2 - OUT_STRAP, ZL + SKIRT * 0.5), (0, -1, 0), r=0.1, h=0.09)
            for i in (2, 6):
                (ya, za), (yb, zb) = outer[i], outer[i + 1]
                n = V((0, -(zb - za), yb - ya)).normalized()
                stud(b, (cx + dx, (ya + yb) / 2, (za + zb) / 2), n, r=0.1, h=0.09)
    # Steel end frames following the arch on both lid ends (they hide the board ends).
    for sx in (-1, 1):
        xa, xb = (W / 2 - 0.36, W / 2 + 0.25) if sx > 0 else (-W / 2 - 0.25, -W / 2 + 0.36)
        arch_band(b, full, xa, xb, -0.32, OUT_STRAP)
        mid = k.offset_profile(full, -0.04)
        xf = sx * (W / 2 + 0.25)
        for i in (2, 4, 6):
            stud(b, (xf, (mid[i][0] + mid[i + 1][0]) / 2, (mid[i][1] + mid[i + 1][1]) / 2), (sx, 0, 0), r=0.1, h=0.09)
        # the end panel inside the frame carries the same diamond boss as the corners
        diamond_boss(b, (sx * (W / 2 - 0.01), 0.0, ZL + 1.2), (sx, 0, 0), 0.36, 0.12)
    # Ridge rail along the top of the barrel, running under the straps into the end frames.
    ztop = prof[3][1] + BULGE[6] * 0.8
    xr = W / 2 - 0.2
    sec = [(-0.27, ztop - 0.04), (0.27, ztop - 0.04), (0.2, ztop + 0.12), (0.0, ztop + 0.2), (-0.2, ztop + 0.12)]
    b.loft([[V((-xr, y, z)) for y, z in sec], [V((xr, y, z)) for y, z in sec]],
           lambda p, t: k.metal_uv(p.x + 10.0, p.y + p.z + 10.0), chamfer=0.04)
    lid = b

    # ---------------- light ----------------
    b = k.Builder()
    inset = 0.06
    b.ring(-W / 2 + inset, W / 2 - inset, -D / 2 + inset, D / 2 - inset, ZT - 0.04, ZL + 0.03, 0.12, gem)
    b.box(-0.05, 0.05, y0 - 0.665, y0 - 0.65, kz - 0.17, kz + 0.02, gem)
    b.prism((0, kz + 0.06), 0.08, 8, y0 - 0.665, y0 - 0.65, gem)
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
