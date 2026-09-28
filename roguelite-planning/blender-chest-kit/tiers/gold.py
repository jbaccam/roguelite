"""Gold chest (15 keys): the royal chest.

Same chest as the approved Wooden one -- rectangular plank body, barrel lid, two straps over
the lid lining up with the body straps, rim bands, corner guards, feet, a lock on the seam
and light leaking from the lid gap -- about 7% bigger and made from richer stuff:

* dark walnut / royal red-brown lacquered boards with a glossy sheen stripe;
* saturated gold everywhere the Wooden chest has iron;
* double-stepped rim bands and ribbed, wider straps set with ruby studs;
* chunky gold corner caps with scroll bosses on the body and lid corners;
* gold lion-paw feet instead of block feet;
* a gold crest medallion with a big ruby on the front of the lid, gold trim along the lid ends;
* a big shield lock plate with a faceted ruby;
* gold coins jammed in the lid gap (they stay with the base) and a glowing gold heap inside.

Tier files are plain Python at the top level (no bpy / mathutils / numpy imports), so
author_textures.py can read PALETTE from system Python; build(k) runs inside Blender.
"""

NAME = "Gold"

# sRGB 0-255. GLOW goes on the Roblox Neon parts (seam, keyhole, treasure heap).
GLOW = (255, 196, 60)

PALETTE = {
    # Dark walnut / royal red-brown lacquered boards.
    "wood": (122, 46, 32), "wood_dark": (64, 18, 14), "wood_light": (178, 84, 54),
    "gap": (30, 8, 6), "sheen": (232, 146, 108),
    # Saturated yellow gold: amber shadows, pale butter highlights.
    "metal": (236, 162, 26), "metal_dark": (150, 74, 8), "metal_light": (255, 226, 100),
    # Swatches: pale gold bolt heads, dark keyhole/interior, ruby, bright ruby table,
    # bright coin gold, deep ruby.
    "rivet": (255, 226, 132), "keyhole": (34, 10, 8), "gem": (208, 20, 46),
    "swatch4": (255, 96, 108), "swatch5": (255, 208, 70), "swatch6": (118, 6, 24),
}

CHAMFER = 0.065
BAKE = {
    # Warm rim instead of the cool one, so the gold stays gold on the shadow side.
    "rim_color": (1.0, 0.82, 0.55), "rim": 0.14,
    "edge": 0.70, "edge_tint": (1.0, 0.9, 0.62), "edge_tint_mix": 0.52,
}

# ---------------------------------------------------------------------------
# dimensions (studs): the Wooden chest scaled ~7%, metal a little thicker
# ---------------------------------------------------------------------------
W, D = 6.4, 4.7
FOOT = 0.54
HB = 2.56
ZT = FOOT + HB
GAP = 0.14
ZL = ZT + GAP
SKIRT = 0.38
RISE = 2.08
ARCH = 7
XS = 1.95
STRAP = 0.82
RIB = 0.34               # raised centre rib on each strap
BAND_H = 0.56
OUT_BAND, STEP = 0.14, 0.07          # rim band, and its raised centre step
OUT_STRAP, OUT_RIB = 0.25, 0.32
OUT_GUARD, OUT_CAP = 0.22, 0.34
IN = 0.32
WALL = OUT_BAND + IN
BOARD_T = 0.26
SEAM = 0.055
FLOOR_DEPTH = 0.95
PLANK = HB / 4.0
BULGE = [0.02, 0.0, 0.035, 0.01, 0.0, 0.03, 0.015, 0.0, 0.025, 0.005, 0.03, 0.0, 0.01, 0.03, 0.0, 0.02]


# ---------------------------------------------------------------------------
# painted source atlas
# ---------------------------------------------------------------------------
def paint_primary(np, rng, w, h, p, tools):
    """Lacquered walnut boards: the Wooden plank painter, darker and redder, plus a soft
    glossy sheen stripe along each board broken into long patches."""
    sn, col, lerp, BANDS = tools["smooth_noise"], tools["col"], tools["lerp"], tools["BANDS"]
    band_h = h / BANDS
    rows = np.arange(h, dtype=np.float32)
    band = np.floor(rows / band_h).astype(int)
    within = (rows - band * band_h) / band_h
    base = np.empty((h, w, 3), np.float32)
    value = rng.uniform(-0.07, 0.07, BANDS)
    warmth = rng.uniform(-0.04, 0.04, BANDS)
    for k in range(BANDS):
        base[band == k] = col(p["wood"]) * (1 + value[k]) * np.array([1 + warmth[k], 1, 1 - warmth[k]])
    patches = sn(h, w, 10, 7, rng) * 0.18 + sn(h, w, 22, 14, rng) * 0.06
    grain = sn(h, w, 90, 6, rng) * 0.12
    base *= (1 + patches + grain)[..., None]
    top = (np.clip(1 - within / 0.14, 0, 1) ** 1.5)[:, None]
    bottom = (np.clip((within - 0.6) / 0.4, 0, 1) ** 1.6)[:, None]
    base = lerp(base, col(p["wood_light"]), top * 0.5)
    base = lerp(base, col(p["wood_dark"]), bottom * 0.6)
    # lacquer sheen
    sheen = np.exp(-((within - 0.3) / 0.1) ** 2)[:, None]
    mask = np.clip(sn(h, w, 14, 4, rng) * 2.4 + 0.5, 0, 1)
    base = lerp(base, col(p["sheen"]), sheen * mask * 0.5)
    gap = (within > 0.955) | (within < 0.012)
    base[gap] = col(p["gap"])
    for k in range(BANDS):
        for _ in range(rng.integers(0, 2)):
            x = int(rng.uniform(0.15, 0.85) * w)
            y0, y1 = int(k * band_h + 2), int((k + 1) * band_h - 3)
            base[y0:y1, x:x + 7] = col(p["gap"])
            base[y0:y1, x + 7:x + 12] = lerp(base[y0:y1, x + 7:x + 12], col(p["wood_light"]), np.full((y1 - y0, 5), 0.35))
    for _ in range(80):
        k = rng.integers(0, BANDS)
        y = int((k + rng.uniform(0.45, 0.85)) * band_h)
        x0 = int(rng.uniform(0, 0.9) * w)
        ln = int(rng.uniform(60, 220))
        t = np.linspace(0, np.pi, ln)
        a = (np.sin(t) * 0.35)[None, :, None]
        seg = base[y:y + 3, x0:x0 + ln]
        base[y:y + 3, x0:x0 + ln] = seg + (col(p["wood_dark"]) - seg) * a[:, :seg.shape[1]]
    return np.clip(base, 0, 1)


def paint_metal(np, rng, w, h, p, tools):
    """Polished gold: broad butter-yellow highlights and amber pools, no streaks."""
    sn, col, lerp = tools["smooth_noise"], tools["col"], tools["lerp"]
    base = np.broadcast_to(col(p["metal"]), (h, w, 3)).copy()
    broad = sn(h, w, 8, 3, rng) * 0.9 + sn(h, w, 20, 8, rng) * 0.3
    t = np.clip(broad, -0.5, 0.5)
    base = lerp(base, col(p["metal_light"]), np.clip(t, 0, None) * 1.0)
    base = lerp(base, col(p["metal_dark"]), np.clip(-t, 0, None) * 0.75)
    return np.clip(base, 0, 1)


# ---------------------------------------------------------------------------
# shape
# ---------------------------------------------------------------------------
def build(k):
    V, math = k.Vector, k.math
    wood_uv = lambda a, b, band: k.primary_uv(a, b, band, PLANK)
    band_uv = lambda a, t, band: k.band_uv(a, t, band, PLANK)
    metal, dark = k.metal, k.dark
    ruby = k.swatch("gem")
    ruby_table = k.swatch_uv("swatch4")
    ruby_deep = k.swatch_uv("swatch6")
    coin_face = k.swatch_uv("swatch5")
    pi = math.pi

    def gem_uv(p, f):
        return ruby_table if f == "cap1" else (ruby_deep if f == "cap0" else k.swatch_uv("gem"))

    def gold_uv(p, f):
        """Planar metal mapping for lofted pieces that never wraps (k.metal wraps at x=0.2,
        y=-1.5 and flips axis at |x|=|y|, which left dark seams on tilted discs)."""
        return k.metal_uv(1.0 + (p.z + 0.5) * 0.55 + (p.y + 3.0) * 0.45, 0.2 + (p.x + 3.8) * 0.4)

    def orient(n):
        n = V(n).normalized()
        u = V((0, 0, 1)).cross(n)
        if u.length < 1e-4:
            u = V((1, 0, 0))
        u.normalize()
        return u, n.cross(u), n

    def ring_pts(c, u, v, r, sides, rot=0.0, su=1.0, sv=1.0):
        return [c + u * (r * su * math.cos(rot + 2 * pi * j / sides)) + v * (r * sv * math.sin(rot + 2 * pi * j / sides)) for j in range(sides)]

    def disc(b, c, n, r, front, back, uvf, sides=8, rot=0.0, taper=1.0, chamfer=None, su=1.0, sv=1.0):
        """Round boss / coin: prism along n (front = proud of c)."""
        u, v, n = orient(n)
        b.loft([ring_pts(c - n * back, u, v, r, sides, rot, su, sv), ring_pts(c + n * front, u, v, r * taper, sides, rot, su, sv)], uvf, chamfer=chamfer)

    def plate(b, c, n, outline, front, back, uvf, scale=1.0, taper=0.9, chamfer=None):
        """Flat plate from a convex CCW (u, v) outline, standing proud along n."""
        u, v, n = orient(n)
        ring = lambda s, off: [c + n * off + u * (x * s) + v * (y * s) for x, y in outline]
        b.loft([ring(scale, -back), ring(scale * taper, front)], uvf, chamfer=chamfer)

    def gem(b, c, n, r, h, sides=6, rot=0.0):
        """Faceted ruby: girdle, sloped crown, flat table."""
        u, v, n = orient(n)
        b.loft([ring_pts(c - n * 0.03, u, v, r, sides, rot), ring_pts(c + n * (h * 0.35), u, v, r, sides, rot),
                ring_pts(c + n * h, u, v, r * 0.55, sides, rot)], gem_uv, chamfer=0)

    def stud(b, c, n, r):
        """Gold bezel with a ruby set in it."""
        disc(b, c, n, r, 0.06, 0.04, gold_uv, sides=8, rot=pi / 8, taper=0.86, chamfer=0)
        gem(b, c + V(n).normalized() * 0.05, n, r * 0.66, r * 0.62, rot=pi / 2)

    def blob(b, c, rx, ry, rz, uvf, seg=8, rings=4, rot=0.0):
        R = [[V((c.x, c.y, c.z - rz))] * seg]
        for i in range(1, rings):
            ph = -pi / 2 + pi * i / rings
            R.append([V((c.x + rx * math.cos(ph) * math.cos(rot + 2 * pi * j / seg), c.y + ry * math.cos(ph) * math.sin(rot + 2 * pi * j / seg),
                         c.z + rz * math.sin(ph))) for j in range(seg)])
        R.append([V((c.x, c.y, c.z + rz))] * seg)
        b.loft(R, uvf, cap0=False, cap1=False, chamfer=0)

    def coin(b, c, n, r=0.3, t=0.085, sides=10, emboss=True, bevel=True):
        disc(b, c, n, r, t / 2, t / 2, gold_uv, sides=sides, chamfer=0)
        if emboss:
            disc(b, c + V(n).normalized() * (t / 2), n, r * 0.62, 0.02, 0.01, lambda p, f: coin_face, sides=sides, chamfer=0)

    def stepped_band(b, x0, x1, y0, y1, z0, z1, wall):
        b.ring(x0 - OUT_BAND, x1 + OUT_BAND, y0 - OUT_BAND, y1 + OUT_BAND, z0, z1, wall, metal)
        m = (z1 - z0) * 0.24
        o = OUT_BAND + STEP
        b.ring(x0 - o, x1 + o, y0 - o, y1 + o, z0 + m, z1 - m, STEP + 0.12, metal)

    def arch():
        return [(-D / 2 * math.cos(pi * i / ARCH), ZL + SKIRT + RISE * math.sin(pi * i / ARCH)) for i in range(ARCH + 1)]

    full = [(-D / 2, ZL)] + arch() + [(D / 2, ZL)]

    def arch_strap(b, xa, xb, off_in, off_out):
        """Metal strip following the lid arch between x = xa..xb (the Wooden strap)."""
        b.begin()
        inner, outer = k.offset_profile(full, off_in), k.offset_profile(full, off_out)
        s = 0.0
        wdt = xb - xa
        for i in range(len(full) - 1):
            seg = math.hypot(outer[i + 1][0] - outer[i][0], outer[i + 1][1] - outer[i][1])
            oa, ob, ia, ib = outer[i], outer[i + 1], inner[i], inner[i + 1]
            b.poly([V((xa, *oa)), V((xb, *oa)), V((xb, *ob)), V((xa, *ob))],
                   [k.metal_uv(s, 0.2), k.metal_uv(s, 0.2 + wdt), k.metal_uv(s + seg, 0.2 + wdt), k.metal_uv(s + seg, 0.2)])
            for xe, flip in ((xa, True), (xb, False)):
                side = [V((xe, *ia)), V((xe, *oa)), V((xe, *ob)), V((xe, *ib))]
                uv = [k.metal_uv(s, 1.0), k.metal_uv(s, 1.4), k.metal_uv(s + seg, 1.4), k.metal_uv(s + seg, 1.0)]
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

    def on_arch(t_index, off):
        """Point and outward normal on the lid surface at the middle of full[] segment."""
        prof = k.offset_profile(full, off)
        (ya, za), (yb, zb) = prof[t_index], prof[t_index + 1]
        n = V((0, -(zb - za), yb - ya)).normalized()
        return V((0, (ya + yb) / 2, (za + zb) / 2)), n

    def volute(b, c, n, r, toward, segs=9, turns=1.05, w=0.13, h=0.12):
        """Scroll: a chunky gold bar curling inward, lying on a surface facing n. The tail
        starts on the side away from `toward` and the curl winds toward the centre."""
        u, v, n = orient(n)
        t = V(toward).normalized()
        th0 = math.atan2(-t.dot(v), -t.dot(u))
        spin = 1 if (u.cross(t)).dot(n) >= 0 else -1
        path = []
        for i in range(segs + 1):
            f = i / segs
            th = th0 + spin * 2 * pi * turns * f
            rr = r * (1 - 0.7 * f)
            path.append(c + u * (rr * math.cos(th)) + v * (rr * math.sin(th)))
        rings = []
        for i, p in enumerate(path):
            tg = (path[min(i + 1, segs)] - path[max(i - 1, 0)]).normalized()
            a = tg.cross(n).normalized()
            bb = -n
            ww = w * (1 - 0.3 * i / segs) / 2
            q = p + n * (h / 2 - 0.03)
            rings.append([q + a * ww - bb * (h / 2), q + a * ww + bb * (h / 2), q - a * ww + bb * (h / 2), q - a * ww - bb * (h / 2)])
        b.loft(rings, gold_uv, chamfer=0)

    # ======================= base =======================
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
    b.ring(x0 + 0.1, x1 - 0.1, y0 + 0.1, y1 - 0.1, zf, ZT - 0.02, IN - 0.13, dark)
    # double-stepped gold rim bands
    stepped_band(b, x0, x1, y0, y1, FOOT, FOOT + BAND_H, WALL)
    stepped_band(b, x0, x1, y0, y1, ZT - BAND_H, ZT, WALL)
    # corner guards (full height) + chunky corner caps with scroll bosses, top and bottom
    g, lip = OUT_GUARD, 0.6
    for sx in (-1, 1):
        for sy in (-1, 1):
            ex, ey = sx * (W / 2 + g), sy * (D / 2 + g)
            ix, iy = sx * (W / 2 - lip), sy * (D / 2 - lip)
            b.box(min(ex, ix), max(ex, ix), min(ey, sy * (D / 2 - 0.02)), max(ey, sy * (D / 2 - 0.02)), FOOT - 0.03, ZT + 0.01, metal)
            b.box(min(ex, sx * (W / 2 - 0.02)), max(ex, sx * (W / 2 - 0.02)), min(ey, iy), max(ey, iy), FOOT - 0.03, ZT + 0.01, metal)
            cx_, cy_ = sx * (W / 2 + OUT_CAP), sy * (D / 2 + OUT_CAP)
            reach = 0.78
            for z0, z1 in ((FOOT - 0.06, FOOT + 0.66), (ZT - 0.66, ZT + 0.04)):
                jx, jy = sx * (W / 2 - reach), sy * (D / 2 - reach)
                b.box(min(cx_, jx), max(cx_, jx), min(cy_, sy * (D / 2 - 0.02)), max(cy_, sy * (D / 2 - 0.02)), z0, z1, metal, chamfer=0.12)
                b.box(min(cx_, sx * (W / 2 - 0.02)), max(cx_, sx * (W / 2 - 0.02)), min(cy_, jy), max(cy_, jy), z0, z1, metal, chamfer=0.12)
                zm = (z0 + z1) / 2
                up = 1 if z0 > FOOT else -1
                volute(b, V((jx + sx * 0.3, cy_, zm)), (0, sy, 0), 0.27, (sx, 0, 0))
                if up > 0:
                    volute(b, V((cx_, jy + sy * 0.3, zm)), (sx, 0, 0), 0.27, (0, sy, 0))
    # wide gold straps with a raised rib and ruby studs
    for sx in (-1, 1):
        cx = sx * XS
        for yf, sgn in ((y0, -1), (y1, 1)):
            ya_, yb_ = sorted((yf - sgn * 0.02, yf + sgn * OUT_STRAP))
            b.box(cx - STRAP / 2, cx + STRAP / 2, ya_, yb_, FOOT - 0.03, ZT + 0.01, metal)
            ya_, yb_ = sorted((yf, yf + sgn * OUT_RIB))
            b.box(cx - RIB / 2, cx + RIB / 2, ya_, yb_, FOOT + 0.05, ZT - 0.05, metal)
        stud(b, V((cx, y0 - OUT_RIB, FOOT + HB / 2)), (0, -1, 0), 0.24)
    # lion-paw feet
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = sx * (W / 2 - 0.02), sy * (D / 2 - 0.02)
            rings = []
            for z, r in ((0.0, 0.42), (0.2, 0.5), (FOOT + 0.12, 0.36)):
                rings.append([V((px + r * math.cos(2 * pi * j / 8), py + r * math.sin(2 * pi * j / 8), z)) for j in range(8)])
            b.loft(rings, gold_uv, chamfer=0)
            a0 = math.atan2(sy * 0.8, sx)
            for da in (-0.62, 0.0, 0.62):
                a = a0 + da
                tx, ty = px + 0.47 * math.cos(a), py + 0.47 * math.sin(a)
                blob(b, V((tx, ty, 0.17)), 0.21, 0.21, 0.17, gold_uv, seg=7, rings=4, rot=a)
    # the lock: a big shield plate straddling the seam, stepped, with a faceted ruby
    zc = ZT + 0.02
    shield = [(0.0, -1.15), (0.62, -0.86), (1.0, -0.3), (1.02, 0.5), (0.78, 0.82), (-0.78, 0.82), (-1.02, 0.5), (-1.0, -0.3), (-0.62, -0.86)]
    fwd = V((0, -1, 0))
    plate(b, V((0, y0 - 0.02, zc)), fwd, shield, OUT_RIB + 0.14, 0.06, gold_uv, scale=1.0, taper=0.93)
    plate(b, V((0, y0 - 0.02, zc)), fwd, shield, OUT_RIB + 0.28, -0.2, gold_uv, scale=0.76, taper=0.9)
    for sx in (-1, 1):
        disc(b, V((sx * 1.0, y0 - 0.1, zc + 0.5)), fwd, 0.3, OUT_RIB + 0.1, 0.0, gold_uv, sides=10, taper=0.9, chamfer=0)
        volute(b, V((sx * 1.0, y0 - 0.1 - OUT_RIB - 0.1, zc + 0.5)), fwd, 0.25, (sx, 0, 0))
    lock_front = y0 - 0.02 - OUT_RIB - 0.28
    gem(b, V((0, lock_front + 0.02, zc + 0.16)), fwd, 0.4, 0.3, sides=8, rot=pi / 8)
    b.box(-0.09, 0.09, lock_front - 0.03, lock_front + 0.02, zc - 0.78, zc - 0.44, dark)
    b.prism((0, zc - 0.4), 0.13, 8, lock_front - 0.03, lock_front + 0.02, dark)
    # coins jammed in the lid gap: some stick out of the gap resting on the rim band's top
    # edge, some have slid out and lean against the band below them
    yb = y0 - OUT_BAND - STEP                      # front of the band step
    for x, yaw, tilt, r, dz in ((-1.3, 0.25, 1.12, 0.34, 0.03), (-1.86, -0.45, 1.0, 0.31, 0.05), (1.34, -0.3, 1.18, 0.35, 0.03),
                                (2.2, 0.2, 1.08, 0.3, 0.06)):
        n = V((math.sin(yaw) * 0.6, -math.cos(tilt), math.sin(tilt))).normalized()
        coin(b, V((x, yb - 0.1, ZT + dz)), n, r)
    for x, lean in ((-1.16, 0.3), (1.62, -0.35)):
        n = V((lean, -math.cos(0.32), math.sin(0.32))).normalized()
        coin(b, V((x, yb - 0.17, ZT - 0.24)), n, 0.33)
    # treasure heap coins (seen when open)
    hx, hy = W / 2 - IN - 0.02, D / 2 - IN - 0.02
    heap = [(1.0, zf + 0.02), (0.96, ZT - 0.34), (0.75, ZT - 0.16), (0.45, ZT - 0.04), (0.18, ZT + 0.03), (0.0, ZT + 0.05)]

    def heap_z(x, y):
        s = max(abs(x) / hx, abs(y) / hy)
        for (sa, za), (sb, zb) in zip(heap, heap[1:]):
            if sb <= s <= sa:
                return za + (zb - za) * (sa - s) / (sa - sb)
        return heap[-1][1]

    for x, y, tx, ty in ((-1.6, -0.5, 0.3, 0.2), (-0.7, 0.3, -0.2, 0.3), (0.2, -0.4, 0.25, -0.2), (1.1, 0.35, -0.3, 0.1),
                         (1.8, -0.3, 0.2, 0.25), (-2.1, 0.45, 0.1, -0.3), (0.5, 0.75, 0.3, 0.3), (-0.2, -0.9, -0.1, 0.35),
                         (2.3, 0.6, -0.25, -0.2), (-1.2, -1.1, 0.2, 0.3), (-0.3, 0.0, 0.1, -0.2), (0.7, -0.05, -0.2, 0.1),
                         (-1.1, 0.0, 0.25, 0.0), (0.0, 0.5, -0.1, -0.3), (1.4, -0.9, -0.3, 0.3), (-2.3, -0.5, 0.35, 0.2),
                         (1.3, 0.95, 0.2, -0.3), (-1.6, 1.05, -0.2, -0.3)):
        # keep every coin under the closed lid's underside (ZL): nothing pokes through it
        rise = 0.28 * math.hypot(tx, ty) / math.sqrt(tx * tx + ty * ty + 1) + 0.04
        coin(b, V((x, y, min(heap_z(x, y) + 0.04, ZL - 0.03 - rise))), V((tx, ty, 1.0)), 0.28, 0.08, sides=8, emboss=False, bevel=False)
    base = b

    # ======================= lid =======================
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
    stepped_band(b, -W / 2, W / 2, -D / 2, D / 2, ZL, ZL + SKIRT + 0.04, WALL)
    # straps with a raised rib, and gold trim edging both lid ends along the arch
    for sx in (-1, 1):
        cx = sx * XS
        arch_strap(b, cx - STRAP / 2, cx + STRAP / 2, 0.0, OUT_STRAP)
        arch_strap(b, cx - RIB / 2, cx + RIB / 2, OUT_STRAP - 0.03, OUT_RIB)
        e0, e1 = sorted((sx * (W / 2 - 0.26), sx * (W / 2 + 0.13)))
        arch_strap(b, e0, e1, -0.3, 0.18)
        for ti in (2, 4):
            c, n = on_arch(ti, OUT_RIB)
            c.x = cx
            stud(b, c, n, 0.22)
    # chunky corner caps on the lid band
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx_, cy_ = sx * (W / 2 + OUT_CAP - 0.04), sy * (D / 2 + OUT_CAP - 0.04)
            jx, jy = sx * (W / 2 - 0.62), sy * (D / 2 - 0.62)
            z0, z1 = ZL - 0.02, ZL + SKIRT + 0.16
            b.box(min(cx_, jx), max(cx_, jx), min(cy_, sy * (D / 2 - 0.02)), max(cy_, sy * (D / 2 - 0.02)), z0, z1, metal, chamfer=0.11)
            b.box(min(cx_, sx * (W / 2 - 0.02)), max(cx_, sx * (W / 2 - 0.02)), min(cy_, jy), max(cy_, jy), z0, z1, metal, chamfer=0.11)
            zm = (z0 + z1) / 2
            volute(b, V((jx + sx * 0.27, cy_, zm)), (0, sy, 0), 0.22, (sx, 0, 0), w=0.12, h=0.11)
    # crest medallion on the front of the lid: rosette with a big ruby
    c, n = on_arch(2, 0.0)
    u, v, n = orient(n)
    disc(b, c, n, 0.64, 0.13, 0.3, gold_uv, sides=12, rot=pi / 12, taper=0.92)
    disc(b, c + n * 0.13, n, 0.48, 0.1, 0.05, gold_uv, sides=12, rot=pi / 12, taper=0.86, chamfer=0)
    gem(b, c + n * 0.2, n, 0.34, 0.3, sides=8, rot=pi / 8)
    # a crown rising from the top of the medallion, rubies on its three points
    cc = c + v * 0.6
    plate(b, cc, n, [(-0.6, -0.12), (0.6, -0.12), (0.64, 0.2), (-0.64, 0.2)], 0.14, 0.4, gold_uv, taper=0.9)
    for px, ph, hw in ((-0.44, 0.6, 0.21), (0.0, 0.78, 0.24), (0.44, 0.6, 0.21)):
        plate(b, cc, n, [(px - hw, 0.12), (px + hw, 0.12), (px + 0.08, ph), (px - 0.08, ph)], 0.12, 0.62, gold_uv, taper=0.85, chamfer=0.04)
        gem(b, cc + u * px + v * (ph - 0.16) + n * 0.1, n, 0.1, 0.1, sides=6)
    lid = b

    # ======================= light =======================
    b = k.Builder()
    inset = 0.06
    b.ring(-W / 2 + inset, W / 2 - inset, -D / 2 + inset, D / 2 - inset, ZT - 0.04, ZL + 0.03, 0.12, k.gem)
    b.box(-0.07, 0.07, lock_front - 0.045, lock_front - 0.03, zc - 0.75, zc - 0.44, k.gem)
    b.prism((0, zc - 0.4), 0.095, 8, lock_front - 0.045, lock_front - 0.03, k.gem)
    seam = b
    b = k.Builder()
    rect = lambda s: [V((hx * s, -hy * 0.72 * s, 0)), V((hx * s, hy * 0.72 * s, 0)), V((hx * 0.86 * s, hy * s, 0)), V((-hx * 0.86 * s, hy * s, 0)),
                      V((-hx * s, hy * 0.72 * s, 0)), V((-hx * s, -hy * 0.72 * s, 0)), V((-hx * 0.86 * s, -hy * s, 0)), V((hx * 0.86 * s, -hy * s, 0))]
    rings = []
    for s, z in heap:
        ss = max(s, 0.08)
        rings.append([p + V((0, 0, z)) for p in rect(ss)])
    b.loft(rings, k.gem)        # glowing gold heap
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
