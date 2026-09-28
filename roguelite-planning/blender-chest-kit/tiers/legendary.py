"""Legendary chest (top tier, Robux / rewards): the crown chest.

Built from the Gold chest's shape (the user likes Gold and Silver's shape best) -- rectangular
body, barrel lid, two straps over the lid lining up with the body straps, rim bands, corner
guards, feet, a lock on the seam and light leaking from the lid gap -- ~15% bigger than Gold
and made unmistakably the ultimate chest:

* mostly heavy gold: full-height gold corner pillars, side pilasters, wide ribbed straps,
  double-stepped rim bands and wide lid-end trims, with a gold ridge rail along the lid top;
* a crown: one solid gold wall standing on the frame capitals around the front and both
  ends, leaning outward, its top crenellated with bevelled cube-capped merlons (corners,
  lid ends, front straps and between them). Proud merlons and top/bottom mouldings make
  each bay a recessed panel with a dark cut-out motif and a turquoise. The bays float just
  above the seam so its glow shows beneath, the front centre dips away around the lock,
  and the wall stays outside the lid and its sweep so the lid opens inside the crown;
* glossy red-orange lacquered wood (brighter and more orange than Gold's walnut), each
  panel framed by a painted gold inlay border with diamond corners;
* turquoise gems set into the pillars, crown prongs and bridges, straps and ridge, and one
  big turquoise gem in a stepped gold setting centre-front of the lid;
* a big octagonal gold lock medallion with a large faceted turquoise gem whose core glows;
* outward-curling gold scroll feet;
* dark lips either side of a strong gold-orange seam glow, and a glowing mound of treasure
  (coins, gems, a goblet) that rises up into the open-shell lid.

Tier files are plain Python at the top level (no bpy / mathutils / numpy imports), so
author_textures.py can read PALETTE from system Python; build(k) runs inside Blender.
"""
import math

NAME = "Legendary"

# sRGB 0-255. GLOW goes on the Roblox Neon parts (seam, keyhole, treasure mound);
# ACCENT on the always-on glowing cores of the two big turquoise gems.
GLOW = (255, 170, 40)
ACCENT = (120, 255, 232)

PALETTE = {
    # Glossy vermilion / orange-red lacquered planks with deeper red grain (brighter and
    # more orange than Gold's dark red-brown walnut); wood_light is the lacquer sheen.
    "wood": (204, 66, 28), "wood_dark": (120, 22, 14), "wood_light": (255, 156, 88),
    "gap": (58, 12, 8),
    # Heavy saturated gold: warm yellow-gold, amber shadows, bright highlights.
    "metal": (240, 168, 24), "metal_dark": (170, 82, 6), "metal_light": (255, 234, 118),
    # Swatches: pale gold bolt heads, dark red-brown interior, turquoise gem, bright turquoise
    # gem table, bright coin gold, deep teal.
    "rivet": (255, 228, 130), "keyhole": (46, 12, 8), "gem": (22, 196, 186),
    "swatch4": (150, 255, 236), "swatch5": (255, 210, 72), "swatch6": (0, 96, 110),
}

CHAMFER = 0.07
BAKE = {
    # Warm rim instead of the cool one, so the gold stays gold on the shadow side.
    "rim_color": (1.0, 0.8, 0.5), "rim": 0.15,
    "edge": 0.74, "edge_tint": (1.0, 0.93, 0.66), "edge_tint_mix": 0.55,
}

# ---------------------------------------------------------------------------
# dimensions (studs): Gold scaled ~15%, taller lid, metal thicker
# ---------------------------------------------------------------------------
W, D = 7.4, 5.4
FOOT = 0.66
HB = 2.94
ZT = FOOT + HB
GAP = 0.3
ZL = ZT + GAP
SKIRT = 0.44
RISE = 2.62
ARCH = 7
XS = 2.1
STRAP = 0.9
RIB = 0.36               # raised centre rib on each strap
BAND_H = 0.62
OUT_BAND, STEP = 0.16, 0.08          # rim band, and its raised centre step
OUT_STRAP, OUT_RIB = 0.27, 0.35
IN = 0.36
WALL = OUT_BAND + IN
BOARD_T = 0.28
SEAM = 0.06
LIP = 0.1               # dark lacquer lips either side of the glowing seam
FLOOR_DEPTH = 1.05
PLANK = HB / 4.0
BULGE = [0.02, 0.0, 0.035, 0.01, 0.0, 0.03, 0.015, 0.0, 0.025, 0.005, 0.03, 0.0, 0.01, 0.03, 0.0, 0.02]

# gold frame: corner pillars reach PIL_IN inside each body corner and PIL_OUT outside it;
# side pilasters are SIDE_HALF wide either side of y = 0; lid-end trims reach TRIM_IN inside
PIL_IN, PIL_OUT = 0.25, 0.78
SIDE_HALF = 0.42
TRIM_IN = 0.36
CLEAR = OUT_BAND + STEP + 0.03       # the crown wall stays this far outside the lid band
CROWN_T = 0.36                       # crown wall thickness

# ---------------------------------------------------------------------------
# painted inlay borders (the painter and build() share this layout)
# ---------------------------------------------------------------------------
ZV0, ZV1 = FOOT + BAND_H, ZT - BAND_H           # visible body panel height
_FB = [(-(W / 2 - PIL_IN), -(XS + STRAP / 2)), (-(XS - STRAP / 2), XS - STRAP / 2), (XS + STRAP / 2, W / 2 - PIL_IN)]
_SIDE = [(-(D / 2 - PIL_IN), -SIDE_HALF), (SIDE_HALF, D / 2 - PIL_IN)]
_LID = [(-(W / 2 - TRIM_IN), -(XS + STRAP / 2)), (-(XS - STRAP / 2), XS - STRAP / 2), (XS + STRAP / 2, W / 2 - TRIM_IN)]
_ARCH = [(-D / 2 * math.cos(math.pi * i / ARCH), ZL + SKIRT + RISE * math.sin(math.pi * i / ARCH)) for i in range(ARCH + 1)]
_BOARD = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(_ARCH, _ARCH[1:])]
# band -> (regions along the face, stud height of the band, bottom line?, top line?)
INLAY = {0: (_FB, ZV1 - ZV0, True, True), 1: (_FB, ZV1 - ZV0, True, True),
         2: (_SIDE, ZV1 - ZV0, True, True), 3: (_SIDE, ZV1 - ZV0, True, True)}
for _i in range(ARCH):
    INLAY[4 + _i] = (_LID, _BOARD[_i], _i == 0, _i == ARCH - 1)
INSET, LINE_W, DIAMOND = 0.16, 0.075, 0.13


# ---------------------------------------------------------------------------
# painted source atlas
# ---------------------------------------------------------------------------
def paint_primary(np, rng, w, h, p, tools):
    """Glossy red-orange lacquered wood: grain, soft sheen, darker lower edge, painted plank
    seams on the body panels, and on every panel band a raised-looking gold inlay border
    with diamond corners, laid out to match the gold frame."""
    col, lerp, sn, BANDS = tools["col"], tools["lerp"], tools["smooth_noise"], tools["BANDS"]
    band_h = h / BANDS
    rows = np.arange(h, dtype=np.float32)
    band = np.floor(rows / band_h).astype(int)
    within = (rows - band * band_h) / band_h          # 0 at a band's top edge, 1 at bottom
    W2 = lambda a: np.broadcast_to(a[:, None], (h, w))

    base = np.empty((h, w, 3), np.float32)
    value = rng.uniform(-0.08, 0.08, BANDS)
    for kk in range(BANDS):
        base[band == kk] = col(p["wood"]) * (1 + value[kk])
    patches = sn(h, w, 10, 6, rng) * 0.2 + sn(h, w, 24, 12, rng) * 0.08
    grain = sn(h, w, 90, 6, rng) * 0.16
    base *= (1 + patches + grain)[..., None]
    # painted grain strokes in the deeper red
    for _ in range(110):
        kk = rng.integers(0, BANDS)
        y = int((kk + rng.uniform(0.2, 0.85)) * band_h)
        x0 = int(rng.uniform(0, 0.9) * w)
        ln = int(rng.uniform(80, 260))
        t = np.linspace(0, np.pi, ln)
        a = (np.sin(t) * 0.4)[None, :, None]
        seg = base[y:y + 3, x0:x0 + ln]
        base[y:y + 3, x0:x0 + ln] = seg + (col(p["wood_dark"]) - seg) * a[:, :seg.shape[1]]
    sheen = W2(np.exp(-((within - 0.3) / 0.12) ** 2)) * np.clip(0.7 + sn(h, w, 6, 4, rng) * 1.4, 0.2, 1.0)
    base = lerp(base, col(p["wood_light"]), sheen * 0.5)
    low = W2(np.clip((within - 0.6) / 0.4, 0, 1) ** 1.4)
    base = lerp(base, col(p["wood_dark"]), low * 0.55)
    gap = (within > 0.975) | (within < 0.015)
    base[gap] = col(p["gap"])

    span_u = BANDS * PLANK * 0.75
    a_col = ((np.arange(w, dtype=np.float32) + 0.5) / w) * span_u - span_u / 2
    hi, lo, dk = col(p["metal_light"]), col(p["metal"]) * 0.9, col(p["gap"])
    hw = LINE_W / 2
    for b, (regions, height, bottom, top) in INLAY.items():
        v0, v1 = b / BANDS + 0.006, (b + 1) / BANDS - 0.006
        r0, r1 = int((1 - v1) * h), int(math.ceil((1 - v0) * h))
        rr = np.arange(r0, r1, dtype=np.float32) + 0.5
        s = ((1 - rr / h) - v0) / (v1 - v0) * height          # studs up the band
        A, S = np.meshgrid(a_col, s)
        if b < 4:                                   # body panels: three planks with dark seams
            blk = base[r0:r1]
            for f in (1 / 3, 2 / 3):
                d = S - height * f
                blk[np.abs(d) < 0.025] = col(p["gap"])
                blk[(d > 0.025) & (d < 0.07)] = lerp(blk[(d > 0.025) & (d < 0.07)], col(p["wood_light"]), np.full(int(((d > 0.025) & (d < 0.07)).sum()), 0.4))
            base[r0:r1] = blk
        lit = np.zeros(A.shape, bool)
        shade = np.zeros(A.shape, bool)
        near = np.zeros(A.shape, bool)
        ya = INSET if bottom else -1e9
        yb = height - INSET if top else 1e9
        for a0, a1 in regions:
            xa, xb = a0 + INSET, a1 - INSET
            span = (S > ya - hw) & (S < yb + hw)
            for x in (xa, xb):
                d = A - x
                m = (np.abs(d) < hw) & span
                lit |= m & (d < 0)
                shade |= m & (d >= 0)
                near |= (np.abs(d) < hw + 0.025) & (S > ya - hw - 0.025) & (S < yb + hw + 0.025)
            inx = (A > xa - hw) & (A < xb + hw)
            for y, on in ((ya, bottom), (yb, top)):
                if not on:
                    continue
                d = S - y
                m = (np.abs(d) < hw) & inx
                lit |= m & (d >= 0)
                shade |= m & (d < 0)
                near |= (np.abs(d) < hw + 0.025) & (A > xa - hw - 0.025) & (A < xb + hw + 0.025)
                for x in (xa, xb):
                    dd = np.abs(A - x) + np.abs(S - y)
                    lit |= (dd < DIAMOND) & (S >= y)
                    shade |= (dd < DIAMOND) & (S < y)
                    near |= dd < DIAMOND + 0.035
        blk = base[r0:r1]
        blk[near] = dk
        blk[shade] = lo
        blk[lit] = hi
        base[r0:r1] = blk
    return np.clip(base, 0, 1)


def paint_metal(np, rng, w, h, p, tools):
    """Polished heavy gold: broad bright highlights and amber pools, never washed out."""
    sn, col, lerp = tools["smooth_noise"], tools["col"], tools["lerp"]
    base = np.broadcast_to(col(p["metal"]), (h, w, 3)).copy()
    broad = sn(h, w, 8, 3, rng) * 0.9 + sn(h, w, 20, 8, rng) * 0.3
    t = np.clip(broad, -0.5, 0.5)
    base = lerp(base, col(p["metal_light"]), np.clip(t, 0, None) * 1.1)
    base = lerp(base, col(p["metal_dark"]), np.clip(-t, 0, None) * 0.9)
    return np.clip(base, 0, 1)


# ---------------------------------------------------------------------------
# shape
# ---------------------------------------------------------------------------
def build(k):
    V = k.Vector
    pi = math.pi
    band_uv = lambda a, t, band: k.band_uv(a, t, band, PLANK)
    metal, dark = k.metal, k.dark
    table_uv = k.swatch_uv("swatch4")
    deep_uv = k.swatch_uv("swatch6")
    side_uv = k.swatch_uv("gem")
    coin_face = k.swatch_uv("swatch5")

    def gem_uv(p, f):
        return table_uv if f == "cap1" else (deep_uv if f == "cap0" else side_uv)

    def gold_uv(p, f):
        """Planar metal mapping for lofted pieces that never wraps inside the chest's bounds."""
        return k.metal_uv(0.6 + (p.z + 0.3) * 0.5 + (p.y + 4.2) * 0.4, 0.15 + (p.x + 5.0) * 0.32)

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

    def octagon(r):
        return [(r * math.cos(pi / 8 + j * pi / 4), r * math.sin(pi / 8 + j * pi / 4)) for j in range(8)]

    def gem(b, c, n, r, h, sides=8, rot=pi / 8):
        """Faceted turquoise: girdle, sloped crown, flat table."""
        u, v, n = orient(n)
        b.loft([ring_pts(c - n * 0.03, u, v, r, sides, rot), ring_pts(c + n * (h * 0.35), u, v, r, sides, rot),
                ring_pts(c + n * h, u, v, r * 0.56, sides, rot)], gem_uv, chamfer=0)

    def stud(b, c, n, r):
        """Gold bezel with a turquoise set in it."""
        disc(b, c, n, r, 0.07, 0.05, gold_uv, sides=8, rot=pi / 8, taper=0.86, chamfer=0)
        gem(b, c + V(n).normalized() * 0.06, n, r * 0.68, r * 0.66, sides=6, rot=pi / 2)

    def coin(b, c, n, r=0.3, t=0.085, sides=10, emboss=True):
        disc(b, c, n, r, t / 2, t / 2, gold_uv, sides=sides, chamfer=0)
        if emboss:
            disc(b, c + V(n).normalized() * (t / 2), n, r * 0.62, 0.02, 0.01, lambda p, f: coin_face, sides=sides, chamfer=0)

    def stepped_band(b, x0, x1, y0, y1, z0, z1, wall):
        b.ring(x0 - OUT_BAND, x1 + OUT_BAND, y0 - OUT_BAND, y1 + OUT_BAND, z0, z1, wall, metal)
        m = (z1 - z0) * 0.24
        o = OUT_BAND + STEP
        b.ring(x0 - o, x1 + o, y0 - o, y1 + o, z0 + m, z1 - m, STEP + 0.12, metal)

    full = [(-D / 2, ZL)] + list(_ARCH) + [(D / 2, ZL)]

    def arch_strap(b, xa, xb, off_in, off_out):
        """Metal strip following the lid arch between x = xa..xb (the Wooden strap). The
        arch here is longer than Gold's, so the run is compressed and offset to stay inside
        the metal block (at s = 0 or past its span it would sample the gem swatches)."""
        mu = lambda s_, t_: k.metal_uv(0.4 + s_ * 0.8, t_)
        b.begin()
        inner, outer = k.offset_profile(full, off_in), k.offset_profile(full, off_out)
        s = 0.0
        wdt = xb - xa
        for i in range(len(full) - 1):
            seg = math.hypot(outer[i + 1][0] - outer[i][0], outer[i + 1][1] - outer[i][1])
            oa, ob, ia, ib = outer[i], outer[i + 1], inner[i], inner[i + 1]
            b.poly([V((xa, *oa)), V((xb, *oa)), V((xb, *ob)), V((xa, *ob))],
                   [mu(s, 0.2), mu(s, 0.2 + wdt), mu(s + seg, 0.2 + wdt), mu(s + seg, 0.2)])
            for xe, flip in ((xa, True), (xb, False)):
                side = [V((xe, *ia)), V((xe, *oa)), V((xe, *ob)), V((xe, *ib))]
                uv = [mu(s, 1.0), mu(s, 1.4), mu(s + seg, 1.4), mu(s + seg, 1.0)]
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
            b.poly(cap, [mu(0, 2.0), mu(0, 2.6), mu(0.2, 2.6), mu(0.2, 2.0)])

    def on_arch(t_index, off):
        """Point and outward normal on the lid surface at the middle of full[] segment."""
        prof = k.offset_profile(full, off)
        (ya, za), (yb, zb) = prof[t_index], prof[t_index + 1]
        n = V((0, -(zb - za), yb - ya)).normalized()
        return V((0, (ya + yb) / 2, (za + zb) / 2)), n

    def sweep(b, path, lateral, hw, ht):
        """Chamfered square-section gold bar along a path, lateral axis fixed."""
        lat = V(lateral).normalized()
        ch = min(hw, ht) * 0.35
        sec = [(hw, -ht + ch), (hw, ht - ch), (hw - ch, ht), (-hw + ch, ht), (-hw, ht - ch), (-hw, -ht + ch), (-hw + ch, -ht), (hw - ch, -ht)]
        rings = []
        for i, p in enumerate(path):
            tg = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
            nrm = tg.cross(lat).normalized()          # lat x nrm = tg: faces point outward
            rings.append([p + lat * a + nrm * bb for a, bb in sec])
        b.loft(rings, gold_uv, chamfer=0)

    # ======================= base =======================
    b = k.Builder()
    x0, x1, y0, y1 = -W / 2, W / 2, -D / 2, D / 2
    # one inset lacquer panel per face, framed by the gold and edged with painted inlay
    za, zb = ZV0 - 0.05, ZV1 + 0.05
    tz = lambda p: (p.z - ZV0) / (ZV1 - ZV0)
    b.box(x0, x1, y0, y0 + BOARD_T, za, zb, lambda p, f: band_uv(p.x, tz(p), 0))
    b.box(x0, x1, y1 - BOARD_T, y1, za, zb, lambda p, f: band_uv(p.x, tz(p), 1))
    b.box(x0, x0 + BOARD_T, y0, y1, za, zb, lambda p, f: band_uv(p.y, tz(p), 2))
    b.box(x1 - BOARD_T, x1, y0, y1, za, zb, lambda p, f: band_uv(p.y, tz(p), 3))
    zf = ZT - FLOOR_DEPTH
    b.box(x0 + 0.12, x1 - 0.12, y0 + 0.12, y1 - 0.12, FOOT, zf, dark)
    ix0, ix1, iy0, iy1 = x0 + IN, x1 - IN, y0 + IN, y1 - IN
    corners = [(ix0, iy0), (ix1, iy0), (ix1, iy1), (ix0, iy1)]
    b.begin()
    for i in range(4):
        (ax, ay), (bx, by) = corners[i], corners[(i + 1) % 4]
        pts = [V((bx, by, zf)), V((ax, ay, zf)), V((ax, ay, ZT - BAND_H)), V((bx, by, ZT - BAND_H))]
        along = (lambda p: p.x) if i % 2 == 0 else (lambda p: p.y)
        b.poly(pts, [band_uv(along(p), (p.z - zf) / (ZT - BAND_H - zf), 14) for p in pts])
    b.ring(x0 + 0.1, x1 - 0.1, y0 + 0.1, y1 - 0.1, zf, ZT - 0.02, IN - 0.13, dark)
    # double-stepped gold rim bands, with a dark lacquer lip under the seam
    stepped_band(b, x0, x1, y0, y1, FOOT, FOOT + BAND_H, WALL)
    stepped_band(b, x0, x1, y0, y1, ZT - BAND_H, ZT - LIP, WALL)
    lo_ = OUT_BAND - 0.02
    b.ring(x0 - lo_, x1 + lo_, y0 - lo_, y1 + lo_, ZT - LIP - 0.01, ZT, WALL - 0.07, dark)

    # ---- full-height corner pillars (the crown's corner prongs stand on them) ----
    for sx in (-1, 1):
        for sy in (-1, 1):
            ax0, ax1 = sorted((sx * (W / 2 - PIL_IN), sx * (W / 2 + PIL_OUT)))
            ay0, ay1 = sorted((sy * (D / 2 - PIL_IN), sy * (D / 2 + PIL_OUT)))
            cx, cy = (ax0 + ax1) / 2, (ay0 + ay1) / 2
            b.box(ax0, ax1, ay0, ay1, FOOT - 0.06, ZT - 0.2, metal, chamfer=0.1)
            # raised Aztec rib on both outer faces
            fx = sx * (W / 2 + PIL_OUT)
            fy = sy * (D / 2 + PIL_OUT)
            b.box(*sorted((fx, fx + sx * 0.08)), cy - 0.2, cy + 0.2, FOOT + 0.42, ZT - 0.72, metal, chamfer=0.05)
            b.box(cx - 0.2, cx + 0.2, *sorted((fy, fy + sy * 0.08)), FOOT + 0.42, ZT - 0.72, metal, chamfer=0.05)
            # stepped plinth and capital
            for z0, z1, grow in ((FOOT - 0.16, FOOT + 0.26, 0.09), (ZT - 0.62, ZT - 0.2, 0.06), (ZT - 0.24, ZT + 0.1, 0.13)):
                b.box(ax0 - grow, ax1 + grow, ay0 - grow, ay1 + grow, z0, z1, metal, chamfer=0.1)
            # turquoise on the pillar faces
            if sy < 0:                                  # back faces are never seen
                stud(b, V((cx, fy + sy * 0.08, (FOOT + ZT) / 2 - 0.05)), (0, sy, 0), 0.2)
            stud(b, V((fx + sx * 0.08, cy, (FOOT + ZT) / 2 - 0.05)), (sx, 0, 0), 0.2)

    # ---- side pilasters (the crown's mid-end prongs stand on them) ----
    for sx in (-1, 1):
        fx = sx * (W / 2 + 0.3)
        b.box(*sorted((sx * (W / 2 - 0.05), fx)), -SIDE_HALF, SIDE_HALF, FOOT - 0.03, ZT - 0.2, metal)
        b.box(*sorted((fx, fx + sx * 0.08)), -0.18, 0.18, FOOT + 0.3, ZT - 0.72, metal, chamfer=0.05)
        stud(b, V((fx + sx * 0.08, 0, (FOOT + ZT) / 2 - 0.05)), (sx, 0, 0), 0.22)
        for z0, z1, gx, gy in ((ZT - 0.62, ZT - 0.2, 0.36, SIDE_HALF + 0.06), (ZT - 0.24, ZT + 0.1, PIL_OUT, SIDE_HALF + 0.14)):
            b.box(*sorted((sx * (W / 2 - 0.05), sx * (W / 2 + gx))), -gy, gy, z0, z1, metal, chamfer=0.1)
    # ---- capitals on the front strap tops (the crown's front prongs stand on them) ----
    for sx in (-1, 1):
        cx = sx * XS
        yfront = -(D / 2 + 0.42 + CROWN_T + 0.12)
        for z0, z1, g in ((ZT - 0.62, ZT - 0.2, 0.0), (ZT - 0.24, ZT + 0.1, 0.1)):
            b.box(cx - STRAP / 2 - 0.04 - g, cx + STRAP / 2 + 0.04 + g, yfront - g, y0 - 0.02, z0, z1, metal, chamfer=0.1)

    # ---- the crown: one solid gold wall around the lid ----
    # A thick band stands on the frame capitals around the front and both ends and leans
    # outward as it rises. Its top is crenellated: bevelled, cube-capped merlons at the
    # corners, lid ends, front straps and between them, the wall dipping between merlons.
    # The merlons and mouldings stand proud, so each bay reads as a recessed panel holding
    # a dark cut-out motif and a turquoise. The bays float just above the seam so its glow
    # shows beneath them, and the front centre dips away around the lock. The wall stays
    # outside the lid and its sweep (the back only has the corner merlons' end arms).
    Z0, ZB = ZT + 0.1, ZT + 0.34                  # merlon feet (on capitals), bay underside
    BAY_TOP = ZT + 1.1
    TOP_C, TOP_M, TOP_S, TOP_m = ZT + 1.62, ZT + 1.52, ZT + 1.5, ZT + 1.36
    T = CROWN_T
    lean = lambda z: 0.12 * max(0.0, z - Z0) + 0.1 * max(0.0, z - Z0) ** 2
    XI, YF = W / 2 + CLEAR, D / 2 + 0.42         # inner faces: ends, front
    Y_BACK = D / 2 + PIL_OUT                      # back end of each end wall
    E = 0.07                                      # run of each sloped step

    def stations(segs):
        """segs: (a, b, kind, top) -> [(coord, bot, top, seg_index)]"""
        out_ = []
        for si, (a, b_, kind, top) in enumerate(segs):
            d = 1 if b_ > a else -1
            a2, b2 = a + d * E / 2, b_ - d * E / 2
            if kind == "merlon":
                out_ += [(a2, Z0, top, si), (b2, Z0, top, si)]
            elif kind == "minor":
                out_ += [(a2, ZB, top, si), (b2, ZB, top, si)]
            elif kind == "bay":
                for j in range(4):
                    f = j / 3
                    out_.append((a2 + (b2 - a2) * f, ZB, BAY_TOP - 0.08 * math.sin(pi * f), si))
            else:                                   # "end": dips away beside the lock
                for j in range(4):
                    f = j / 3
                    out_.append((a2 + (b2 - a2) * f, ZB, BAY_TOP - (BAY_TOP - ZB - 0.2) * (1 - math.cos(pi * f / 2)), si))
        return out_

    def wall_ring(P, N, bot, top, inner=0.0, outer=0.0):
        Nv = V((N[0], N[1], 0))
        ib = V((P[0], P[1], bot)) + Nv * (lean(bot) - inner)
        tp = V((P[0], P[1], top)) + Nv * (lean(top) - inner)
        w = T + inner + outer
        return [ib, ib + Nv * w, tp + Nv * w, tp]

    def wound(rings):
        """loft wants each ring wound so its normal points along the direction of travel"""
        r0, r1 = rings[0], rings[1]
        if (r0[1] - r0[0]).cross(r0[3] - r0[0]).dot(r1[0] - r0[0]) < 0:
            return [list(reversed(r)) for r in rings]
        return rings

    def face_at(P, N, z):
        """Point on the wall's outer face and its outward normal."""
        Nv = V((N[0], N[1], 0))
        slope = 0.12 + 0.2 * max(0.0, z - Z0)
        return V((P[0], P[1], z)) + Nv * (lean(z) + T), (Nv.normalized() - V((0, 0, slope))).normalized()

    side_segs = [(Y_BACK, D / 2 - 0.3, "merlon", TOP_C), (D / 2 - 0.3, 1.8, "bay", 0), (1.8, 1.3, "minor", TOP_m),
                 (1.3, 0.4, "bay", 0), (0.4, -0.4, "merlon", TOP_M), (-0.4, -1.3, "bay", 0),
                 (-1.3, -1.8, "minor", TOP_m), (-1.8, -(YF - 0.62), "bay", 0), (-(YF - 0.62), -YF, "merlon", TOP_C)]
    front_segs = [(-XI, -(XI - 0.58), "merlon", TOP_C), (-(XI - 0.58), -(XS + 0.4), "bay", 0),
                  (-(XS + 0.4), -(XS - 0.4), "merlon", TOP_S), (-(XS - 0.4), -1.3, "end", 0)]
    cube_list, gem_list, motif_list = [], [], []
    for sx in (-1, 1):
        st = ([((sx * XI, c), (sx, 0), bo, tp, ("s", si)) for c, bo, tp, si in stations(side_segs)]
              + [((sx * XI, -YF), (sx, -1), Z0, TOP_C, ("c", 0))]
              + [((sx * -c, -YF), (0, -1), bo, tp, ("f", si)) for c, bo, tp, si in stations(front_segs)])
        full_rings = [wall_ring(P, N, bo, tp) for P, N, bo, tp, g in st]
        b.loft(wound(full_rings), gold_uv, chamfer=0.06)
        # mouldings along the top and bottom edges
        b.loft(wound([wall_ring(P, N, tp - 0.17, tp + 0.03, 0.05, 0.09) for P, N, bo, tp, g in st]), gold_uv, chamfer=0)
        b.loft(wound([wall_ring(P, N, bo - 0.03, bo + 0.15, 0.03, 0.09) for P, N, bo, tp, g in st]), gold_uv, chamfer=0)
        # merlons stand proud of the bays
        groups = {}
        for P, N, bo, tp, g in st:
            key = g
            if g == ("s", len(side_segs) - 1) or g == ("c", 0) or g == ("f", 0):
                key = "corner"
            groups.setdefault(key, []).append((P, N, bo, tp))
        for key, pts in groups.items():
            kind = ("merlon" if key == "corner" else
                    (side_segs if key[0] == "s" else front_segs)[key[1]][2])
            if kind not in ("merlon", "minor"):
                continue
            b.loft(wound([wall_ring(P, N, bo, tp - 0.15, -(T - 0.02), 0.09) for P, N, bo, tp in pts]), gold_uv, chamfer=0)
            if key == "corner":
                P, N, tp = (sx * XI, -YF), (sx * 0.72, -0.72), TOP_C
                cube_list.append((P, N, tp, 0.74))
                gem_list.append(face_at(P, N, tp - 0.5) + (0.21,))
            else:
                P0, N0, _, tp = pts[0]
                P1 = pts[-1][0]
                P = ((P0[0] + P1[0]) / 2, (P0[1] + P1[1]) / 2)
                cube_list.append((P, N0, tp, 0.62 if kind == "merlon" else 0.46))
                if kind == "merlon":
                    gem_list.append(face_at(P, N0, tp - 0.5) + (0.2,))
        # a dark cut-out motif with a turquoise in the middle of every bay
        for segs, tag in ((side_segs, "s"), (front_segs, "f")):
            for si, (a0, a1, kind, _) in enumerate(segs):
                if kind != "bay":
                    continue
                c = (a0 + a1) / 2
                P, N = ((sx * XI, c), (sx, 0)) if tag == "s" else ((sx * -c, -YF), (0, -1))
                motif_list.append(face_at(P, N, (ZB + BAY_TOP) / 2 + 0.02) + (min(1.0, abs(a1 - a0) - 0.3),))
    for P, N, top, size in cube_list:
        Nv = V((N[0], N[1], 0))
        c = V((P[0], P[1], top)) + Nv * (lean(top) + T / 2)
        h = size / 2
        b.box(c.x - h, c.x + h, c.y - h, c.y + h, c.z - 0.06, c.z + size * 0.72, metal, chamfer=0.1)
    for c, n, r in gem_list:
        stud(b, c, n, r)
    for c, n, span in motif_list:
        wdt = span / 2
        hexo = [(-wdt, 0.0), (-wdt + 0.16, -0.19), (wdt - 0.16, -0.19), (wdt, 0.0), (wdt - 0.16, 0.19), (-wdt + 0.16, 0.19)]
        plate(b, c, n, hexo, 0.05, 0.03, dark, scale=0.85, taper=0.9, chamfer=0.015)
        stud(b, c + n * 0.03, n, 0.15)

    # ---- wide gold straps with a raised rib and turquoise studs ----
    for sx in (-1, 1):
        cx = sx * XS
        for yf, sgn in ((y0, -1), (y1, 1)):
            ya_, yb_ = sorted((yf - sgn * 0.02, yf + sgn * OUT_STRAP))
            b.box(cx - STRAP / 2, cx + STRAP / 2, ya_, yb_, FOOT - 0.03, ZT - LIP, metal)
            ya_, yb_ = sorted((yf, yf + sgn * OUT_RIB))
            b.box(cx - RIB / 2, cx + RIB / 2, ya_, yb_, FOOT + 0.05, ZT - 0.1, metal)
        stud(b, V((cx, y0 - OUT_RIB, FOOT + HB / 2)), (0, -1, 0), 0.25)

    # ---- outward-curling scroll feet under each pillar ----
    for sx in (-1, 1):
        for sy in (-1, 1):
            o = V((sx, sy, 0)).normalized()
            cp = V((sx * (W / 2 + (PIL_OUT - PIL_IN) / 2), sy * (D / 2 + (PIL_OUT - PIL_IN) / 2), 0))
            prof = [(-0.25, 0.72), (-0.08, 0.46), (0.12, 0.24), (0.4, 0.15), (0.66, 0.17), (0.86, 0.3), (0.92, 0.5),
                    (0.84, 0.66), (0.68, 0.7), (0.6, 0.58), (0.66, 0.47)]
            path = [cp + o * r + V((0, 0, z)) for r, z in prof]
            sweep(b, path, V((-o.y, o.x, 0)), 0.3, 0.15)

    # ---- the lock: a big octagonal medallion straddling the seam ----
    zc = ZT + GAP / 2
    fwd = V((0, -1, 0))
    plate(b, V((0, y0 - 0.02, zc)), fwd, octagon(1.22), OUT_RIB + 0.14, 0.06, gold_uv, taper=0.94)
    plate(b, V((0, y0 - 0.02, zc)), fwd, octagon(1.22), OUT_RIB + 0.3, -0.2, gold_uv, scale=0.78, taper=0.9)
    lock_face = y0 - 0.02 - OUT_RIB - 0.3
    disc(b, V((0, lock_face, zc + 0.12)), fwd, 0.66, 0.1, 0.02, gold_uv, sides=8, rot=pi / 8, taper=0.88, chamfer=0)
    gem(b, V((0, lock_face - 0.08, zc + 0.12)), fwd, 0.54, 0.34)
    gem_front = lock_face - 0.08 - 0.34
    for j in (0, 3, 4, 7):
        a = pi / 8 + j * pi / 4
        b.rivet(1.05 * math.cos(a), zc + 1.05 * math.sin(a), y0 - 0.02 - OUT_RIB - 0.14, 1.1)
    for sx in (-1, 1):
        stud(b, V((sx * 0.98, y0 - 0.02 - OUT_RIB - 0.14, zc + 0.62)), fwd, 0.17)
    b.box(-0.1, 0.1, lock_face - 0.03, lock_face + 0.02, zc - 0.84, zc - 0.56, dark)
    b.prism((0, zc - 0.52), 0.14, 8, lock_face - 0.03, lock_face + 0.02, dark)

    # ---- the treasure mound (seen when open) ----
    # The lid is an open shell underneath, so the mound can rise up into it when closed.
    hx, hy = W / 2 - IN - 0.02, D / 2 - IN - 0.02
    heap = [(1.0, zf + 0.02), (0.97, ZT - 0.5), (0.85, ZT - 0.12), (0.7, ZT + 0.26), (0.5, ZL + 0.3),
            (0.28, ZL + 0.58), (0.1, ZL + 0.72), (0.0, ZL + 0.74)]

    def heap_z(x, y):
        s = max(abs(x) / hx, abs(y) / hy)
        for (sa, za_), (sb, zb_) in zip(heap, heap[1:]):
            if sb <= s <= sa:
                return za_ + (zb_ - za_) * (sa - s) / (sa - sb)
        return heap[-1][1]

    def heap_n(x, y):
        e = 0.1
        return V((-(heap_z(x + e, y) - heap_z(x - e, y)) / (2 * e), -(heap_z(x, y + e) - heap_z(x, y - e)) / (2 * e), 1.0)).normalized()

    def rnd(i):
        return (math.sin(i * 12.9898 + 4.1) * 43758.5453) % 1.0

    i = 0
    for gx in range(8):
        for gy in range(3):
            i += 1
            x = (-0.86 + 1.72 * (gx + 0.2 + 0.6 * rnd(i)) / 8) * hx
            y = (-0.82 + 1.64 * (gy + 0.2 + 0.6 * rnd(i + 50)) / 3) * hy
            n = heap_n(x, y) + V(((rnd(i + 100) - 0.5) * 0.9, (rnd(i + 150) - 0.5) * 0.9, 0))
            coin(b, V((x, y, heap_z(x, y) + 0.03)), n, 0.25 + 0.08 * rnd(i + 200), 0.085, sides=8, emboss=False)
    for x, y, r in ((-0.9, -0.75, 0.3), (1.1, 0.7, 0.26), (-2.1, 0.3, 0.26), (0.2, -1.2, 0.26)):
        gem(b, V((x, y, heap_z(x, y) - 0.04)), heap_n(x, y) + V((0.1 * x, 0.1, 0)), r, r * 0.66, sides=6, rot=0.3)
    # a gold goblet leaning on the top of the pile
    gc, gn = V((0.75, -0.25, heap_z(0.75, -0.25) - 0.05)), V((0.18, -0.22, 1.0)).normalized()
    gu, gv, gn = orient(gn)
    b.loft([ring_pts(gc + gn * z, gu, gv, r, 8) for r, z in ((0.3, 0.0), (0.3, 0.07), (0.09, 0.14), (0.08, 0.36),
                                                            (0.14, 0.44), (0.33, 0.58), (0.37, 0.84), (0.31, 0.88))], gold_uv, chamfer=0)
    base = b

    # ======================= lid =======================
    b = k.Builder()
    prof = list(_ARCH)
    xo = W / 2 + 0.06
    for i in range(ARCH):
        (ya, za), (yb, zb) = prof[i], prof[i + 1]
        a, c = V((0, ya, za)), V((0, yb, zb))
        along = (c - a).normalized()
        a, c = a + along * SEAM / 2, c - along * SEAM / 2
        n = V((0, -(zb - za), yb - ya)).normalized()
        lift = n * BULGE[i + 3] * 0.6
        o0, o1, i0, i1 = a + lift, c + lift, a - n * BOARD_T, c - n * BOARD_T
        band = 4 + i
        # t runs 0..1 along the full board so the painted inlay lines up with the frame
        t0, t1 = (SEAM / 2) / _BOARD[i], 1 - (SEAM / 2) / _BOARD[i]
        b.begin()
        uvq = lambda ts, xs, band=band: [band_uv(x, t, band) for x, t in zip(xs, ts)]
        L, R = -xo, xo
        quad = lambda P, Q, xa, xb: [V((xa, P.y, P.z)), V((xb, P.y, P.z)), V((xb, Q.y, Q.z)), V((xa, Q.y, Q.z))]
        b.poly(quad(o0, o1, L, R), uvq([t0, t0, t1, t1], [L, R, R, L]))
        b.poly(quad(i1, i0, L, R), uvq([t1, t1, t0, t0], [L, R, R, L]))
        b.poly(quad(i0, o0, L, R), uvq([t0, t0, t0 + 0.04, t0 + 0.04], [L, R, R, L]))
        b.poly(quad(o1, i1, L, R), uvq([t1 - 0.04, t1 - 0.04, t1, t1], [L, R, R, L]))
        for x, flip in ((L, False), (R, True)):
            e = [V((x, i0.y, i0.z)), V((x, o0.y, o0.z)), V((x, o1.y, o1.z)), V((x, i1.y, i1.z))]
            if flip:
                e.reverse()
            b.poly(e, [band_uv(0.0, 0.5, 12)] * 4)
    b.begin()
    core = [(-D / 2, ZL + 0.02)] + k.offset_profile(prof, -BOARD_T + 0.01) + [(D / 2, ZL + 0.02)]
    xc = W / 2 - 0.01
    for i in range(len(core) - 1):
        (ya, za), (yb, zb) = core[i], core[i + 1]
        b.poly([V((-xc, ya, za)), V((xc, ya, za)), V((xc, yb, zb)), V((-xc, yb, zb))], [k.swatch_uv("dark")] * 4)
    for sx in (-1, 1):
        pts = [V((sx * xc, y, z)) for y, z in core]
        if sx > 0:
            pts.reverse()
        b.poly(pts, [band_uv(p.y, (p.z - ZL) / (SKIRT + RISE), 12) for p in pts])
    # No underside: the lid is an open shell so the treasure can pile up into it. It is
    # lined inside with inward-facing lacquer (kept clear of the boards so the bake's
    # edge highlight does not catch them), and the ends get inward-facing copies.
    b.begin()
    lining = [(-D / 2 + IN, ZL + 0.02)] + k.offset_profile(prof, -BOARD_T - 0.1)[1:-1] + [(D / 2 - IN, ZL + 0.02)]
    xl = W / 2 - 0.04
    arc = [0.0]
    for (ya, za), (yb, zb) in zip(lining, lining[1:]):
        arc.append(arc[-1] + math.hypot(yb - ya, zb - za))
    for i in range(len(lining) - 1):
        (ya, za), (yb, zb) = lining[i], lining[i + 1]
        ta, tb = arc[i] / arc[-1], arc[i + 1] / arc[-1]
        b.poly([V((-xl, yb, zb)), V((xl, yb, zb)), V((xl, ya, za)), V((-xl, ya, za))],
               [band_uv(-xl, tb, 13), band_uv(xl, tb, 13), band_uv(xl, ta, 13), band_uv(-xl, ta, 13)])
    for sx in (-1, 1):
        pts = [V((sx * xl, y, z)) for y, z in lining]
        if sx < 0:
            pts.reverse()
        b.poly(pts, [band_uv(p.y, (p.z - ZL) / (SKIRT + RISE), 13) for p in pts])
    lo_ = OUT_BAND - 0.02
    b.ring(-W / 2 - lo_, W / 2 + lo_, -D / 2 - lo_, D / 2 + lo_, ZL, ZL + LIP + 0.01, WALL - 0.07, dark)
    stepped_band(b, -W / 2, W / 2, -D / 2, D / 2, ZL + LIP, ZL + SKIRT + 0.04, WALL)
    # straps with a raised rib, wide gold trim edging both lid ends along the arch
    for sx in (-1, 1):
        cx = sx * XS
        arch_strap(b, cx - STRAP / 2, cx + STRAP / 2, 0.0, OUT_STRAP)
        arch_strap(b, cx - RIB / 2, cx + RIB / 2, OUT_STRAP - 0.03, OUT_RIB)
        e0, e1 = sorted((sx * (W / 2 - TRIM_IN), sx * (W / 2 + 0.14)))
        arch_strap(b, e0, e1, -0.3, 0.2)
        for ti in (2, 4):
            c, n = on_arch(ti, OUT_RIB)
            c.x = cx
            stud(b, c, n, 0.23)
    # gold ridge rail along the top board, with turquoise between the straps
    ztop = _ARCH[3][1]
    ry = abs(_ARCH[3][0]) * 0.62
    b.box(-W / 2 + 0.2, W / 2 - 0.2, -ry, ry, ztop - 0.06, ztop + 0.16, metal, chamfer=0.07)
    for x in (-0.9, 0.9):
        stud(b, V((x, 0, ztop + 0.16)), (0, 0, 1), 0.2)
    # big turquoise centre-front of the lid in a stepped octagonal gold setting
    c, n = on_arch(2, 0.0)
    u, v, n = orient(n)
    plate(b, c, n, octagon(0.84), 0.14, 0.3, gold_uv, taper=0.93)
    plate(b, c + n * 0.14, n, octagon(0.84), 0.12, 0.05, gold_uv, scale=0.76, taper=0.9)
    for sx in (-1, 1):
        stud(b, c + n * 0.14 + u * (sx * 0.72), n, 0.13)
    gem(b, c + n * 0.24, n, 0.46, 0.34)
    lid_gem = (c + n * (0.24 + 0.34), n)
    lid = b

    # ======================= glowing gem cores (always on) =======================
    b = k.Builder()
    disc(b, V((0, gem_front, zc + 0.12)), fwd, 0.54 * 0.56 * 0.82, 0.015, 0.01, k.gem, sides=8, rot=pi / 8, chamfer=0)
    jewel = b
    b = k.Builder()
    disc(b, lid_gem[0], lid_gem[1], 0.46 * 0.56 * 0.82, 0.015, 0.01, k.gem, sides=8, rot=pi / 8, chamfer=0)
    lid_jewel = b

    # ======================= light =======================
    b = k.Builder()
    o = OUT_BAND + 0.0
    b.ring(-W / 2 - o, W / 2 + o, -D / 2 - o, D / 2 + o, ZT - 0.01, ZL + 0.01, 0.3, k.gem)
    b.box(-0.075, 0.075, lock_face - 0.045, lock_face - 0.03, zc - 0.82, zc - 0.56, k.gem)
    b.prism((0, zc - 0.52), 0.1, 8, lock_face - 0.045, lock_face - 0.03, k.gem)
    seam = b
    b = k.Builder()
    rect = lambda s: [V((hx * s, -hy * 0.72 * s, 0)), V((hx * s, hy * 0.72 * s, 0)), V((hx * 0.86 * s, hy * s, 0)), V((-hx * 0.86 * s, hy * s, 0)),
                      V((-hx * s, hy * 0.72 * s, 0)), V((-hx * s, -hy * 0.72 * s, 0)), V((-hx * 0.86 * s, -hy * s, 0)), V((hx * 0.86 * s, -hy * s, 0))]
    rings = []
    for s, z in heap:
        ss = max(s, 0.08)
        rings.append([p + V((0, 0, z)) for p in rect(ss)])
    b.loft(rings, k.gem)        # glowing treasure mound
    floor = b

    return {
        "parts": {
            "Chest_Base": (base, "textured"),
            "Chest_Lid": (lid, "textured"),
            "Chest_Glow": (seam, "glow"),
            "Chest_Inner": (floor, "floor"),
            "Chest_Jewel": (jewel, "accent"),
            "Chest_Lid_Jewel": (lid_jewel, "accent"),
        },
        "hinge": (0.0, D / 2 + OUT_BAND, ZL),
        "open": {"rotate_x_deg": 105.0},
    }
