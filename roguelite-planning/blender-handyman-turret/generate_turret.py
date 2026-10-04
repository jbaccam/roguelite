"""Handyman deployable turret, Tiers I-IV: model, paint, bake, render, export.

    blender --background --python generate_turret.py                          # full build
    blender --background --python generate_turret.py -- --quick --out=<dir>   # flat-colour shaping run
    blender --background --python generate_turret.py -- --tiers=2,4           # subset (full or quick)

Self-contained (no sibling kit is imported). Pattern follows blender-chest-kit: every piece is
welded and bevelled on its own, colour comes from a painted atlas, and the final texture is a
baked "icon lighting" colour map (key light x AO x height + cool rim + warm bevel-edge
highlights) on unique UVs, so Roblox MeshPart.TextureID shows the painterly look.

Coordinates: studs, Blender Z up, ground at z = 0, turret faces -Y. After Studio's FBX import
(axis_forward -Z, axis_up Y, then Studio's 180 degree turn about Y seen on the chest, armory and
island kits) a Blender point (x, y, z) lands at Roblox (-x, z, y): the barrels point to -Z, the
model's LookVector.

Parts per tier (unique names, transforms applied, origin = pivot):
    HandymanTurret_T{n}_Base    static stand, pivot at ground centre
    HandymanTurret_T{n}_Head    yaws about the vertical axis, pivot on that axis at the bearing top
    HandymanTurret_T{n}_Barrel  pitches about X / recoils along +Z(Roblox) at its pivot; T4 spins
                                about its forward axis through the same pivot
    HandymanTurret_T4_Glow      Neon seams, eye slits and core; welded to the Head (same pivot)

Writes: textures/HandymanTurret_T{n}.png (1024 baked colour), textures/source/*_paint.png,
exports/fbx|glb/HandymanTurret_T{n}.*, exports/turret-spec.json, polygon-report.json,
previews/HandymanTurret_T{n}_3q.png, previews/lineup.png, previews/hero_T4.png,
previews/icon_T{n}.png.
"""
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    for a in ARGS:
        if a.startswith(f"--{name}="):
            return a.split("=", 1)[1]
    return default


QUICK = "--quick" in ARGS
TIERS = [int(t) for t in arg("tiers", "1,2,3,4").split(",")]
QUICK_OUT = Path(arg("out", str(ROOT / "work")))
BAKE_SIZE, BAKE_SAMPLES = 1024, 8
CHAMFER = 0.05                      # default soft edge, studs
BEVEL_ANGLE = math.radians(32)      # edges sharper than this get the chamfer
SHARP = math.radians(30)            # facets steeper than this stay crisp (visible faceting)
BUDGET = {1: 3000, 2: 4500, 3: 6000, 4: 8000}
for d in ("textures/source", "exports/fbx", "exports/glb", "previews"):
    (ROOT / d).mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------------------------
# palette (sRGB). Game tier colours come from studio-prototype/ui/UITheme.luau (T.Tier, T.TierFill)
# ---------------------------------------------------------------------------------------------
PAL = {
    "gunmetal": ((70, 74, 80), (53, 56, 61), (95, 100, 107)),
    "gunlight": ((112, 118, 126), (90, 95, 102), (142, 148, 155)),
    "steel": ((146, 152, 158), (112, 118, 125), (186, 191, 195)),
    "dark": ((40, 41, 45), (28, 29, 32), (58, 60, 64)),
    "hole": ((18, 18, 20), (12, 12, 14), (26, 26, 28)),
    "yellow": ((255, 194, 34), (234, 156, 20), (255, 224, 104)),
    "orange": ((247, 116, 30), (212, 82, 20), (255, 160, 74)),
    "red": ((214, 48, 42), (168, 32, 32), (240, 94, 74)),
    "brass": ((236, 178, 64), (196, 132, 40), (255, 220, 130)),
    "rust": ((172, 88, 46), (126, 60, 36), (206, 126, 70)),
    "amber": ((255, 162, 30), (238, 118, 18), (255, 214, 110)),
}
CHAR = ((46, 47, 51), (34, 35, 38), (64, 66, 70))
TIER_RGB = {1: (218, 224, 228), 2: (79, 183, 245), 3: (192, 116, 249), 4: (248, 88, 99)}
TIER_FILL = {1: (96, 104, 108), 2: (34, 122, 190), 3: (128, 62, 196), 4: (196, 44, 56)}
GLOW_RGB = TIER_RGB[4]

# ---------------------------------------------------------------------------------------------
# painted source atlas: 12 swatch tiles (256 px) + 4 stripe rows (1024 x 64, stripes run along u)
# ---------------------------------------------------------------------------------------------
ATLAS = 1024
SWATCHES = ["gunmetal", "steel", "yellow", "orange", "dark", "brass", "red", "rust",
            "tier", "amber", "gunlight", "hole"]
STRIPES = {"hazard": 0.34, "tierhaz": 0.34, "nails": 0.13, "vent": 0.18}   # period in studs
STRIPE_SPAN = 5.0                                                       # studs per stripe row
TILES = {}
for _i, _n in enumerate(SWATCHES):
    _c, _r = _i % 4, _i // 4
    TILES[_n] = (_c * 0.25, _r * 0.25, _c * 0.25 + 0.25, _r * 0.25 + 0.25)
for _i, _n in enumerate(STRIPES):
    TILES[_n] = (0.0, 0.75 + _i * 0.0625, 1.0, 0.75 + (_i + 1) * 0.0625)
TILE_NAMES = list(TILES)
TILE_INDEX = {n: i for i, n in enumerate(TILE_NAMES)}


def value_noise(h, w, cy, cx, rng):
    g = rng.random((cy + 2, cx + 2)).astype(np.float32)
    ys = np.linspace(0, cy, h, endpoint=False) + 0.5
    xs = np.linspace(0, cx, w, endpoint=False) + 0.5
    y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int)
    ty, tx = ys - y0, xs - x0
    ty, tx = ty * ty * (3 - 2 * ty), tx * tx * (3 - 2 * tx)
    a, b = g[y0][:, x0], g[y0][:, x0 + 1]
    c, d = g[y0 + 1][:, x0], g[y0 + 1][:, x0 + 1]
    top = a + (b - a) * tx[None, :]
    bot = c + (d - c) * tx[None, :]
    return top + (bot - top) * ty[:, None] - 0.5


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def painterly(h, w, base, dark, light, rng, cells=(3, 3)):
    """Broad soft patches in three value ranges plus faint brush streaks; no fine noise."""
    cy, cx = cells
    n = value_noise(h, w, cy, cx, rng) * 0.75 + value_noise(h, w, cy * 2 + 1, cx * 2 + 1, rng) * 0.32
    n += value_noise(h, w, cy * 4 + 2, max(2, cx), rng) * 0.16
    img = np.broadcast_to(np.array(base, np.float32) / 255, (h, w, 3)).copy()
    img += (np.array(dark, np.float32) / 255 - img) * sstep(0.09, 0.33, -n)[..., None]
    img += (np.array(light, np.float32) / 255 - img) * sstep(0.13, 0.36, n)[..., None]
    return img


def stripe_mask(w, period_px, duty=0.5):
    xs = (np.arange(w * 4, dtype=np.float32) + 0.5) / 4
    return (((xs / period_px) % 1.0) >= duty).astype(np.float32).reshape(w, 4).mean(1)


def tier_pal(t):
    c, f = np.array(TIER_RGB[t], float), np.array(TIER_FILL[t], float)
    return tuple(TIER_RGB[t]), tuple((c + (f - c) * 0.55).astype(int)), tuple((c + (255 - c) * 0.35).astype(int))


def paint_atlas(tier):
    rng = np.random.default_rng(11 + tier)
    img = np.zeros((ATLAS, ATLAS, 3), np.float32)
    pal = dict(PAL, tier=tier_pal(tier))

    def rect(name):
        u0, v0, u1, v1 = TILES[name]
        return slice(int(v0 * ATLAS), int(v1 * ATLAS)), slice(int(u0 * ATLAS), int(u1 * ATLAS))

    for n in SWATCHES:
        ry, rx = rect(n)
        img[ry, rx] = painterly(ry.stop - ry.start, rx.stop - rx.start, *pal[n], rng)
    ppx = ATLAS / STRIPE_SPAN

    def stripe_row(name, a, b, duty=0.5):
        ry, rx = rect(name)
        h, w = ry.stop - ry.start, rx.stop - rx.start
        m = stripe_mask(w, STRIPES[name] * ppx, duty)[None, :, None]
        A = painterly(h, w, *a, rng, cells=(2, 20))
        B = painterly(h, w, *b, rng, cells=(2, 20))
        img[ry, rx] = A + (B - A) * m
        return ry, rx, h, w

    stripe_row("hazard", pal["yellow"], CHAR)
    stripe_row("tierhaz", pal["tier"], CHAR)
    ry, rx, h, w = stripe_row("nails", pal["steel"], pal["dark"], duty=0.66)
    heads = int(h * 0.26)                       # collated nail heads along the top edge
    hm = stripe_mask(w, STRIPES["nails"] * ppx, 0.8)[None, :, None]
    br = painterly(heads, w, *pal["brass"], rng, cells=(1, 16))
    dk = np.array(pal["dark"][0], np.float32) / 255
    img[ry.stop - heads:ry.stop, rx] = br + (dk - br) * hm
    stripe_row("vent", pal["gunmetal"], pal["hole"], duty=0.55)
    return img


def save_png(arr, path, name):
    h, w, _ = arr.shape
    im = bpy.data.images.new(name, w, h, alpha=False)
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = np.clip(arr, 0, 1)
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = str(path)
    im.file_format = "PNG"
    im.save()
    return im


# ---------------------------------------------------------------------------------------------
# mesh builder: pieces are welded + bevelled alone, faces carry a tile, UVs assigned after bevel
# ---------------------------------------------------------------------------------------------
Z = Vector((0, 0, 1))
FWD = Vector((0, -1, 0))
XA = Vector((1, 0, 0))


def V(x, y, z):
    return Vector((x, y, z))


def newell(pts):
    n = Vector((0, 0, 0))
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n.x += (a.y - b.y) * (a.z + b.z)
        n.y += (a.z - b.z) * (a.x + b.x)
        n.z += (a.x - b.x) * (a.y + b.y)
    return n.normalized() if n.length > 1e-12 else Vector((0, 0, 1))


def dirs(angles):
    return [Vector((math.cos(math.radians(a)), math.sin(math.radians(a)), 0)) for a in angles]


class Piece:
    def __init__(self, chamfer, D):
        self.verts, self.faces, self.tiles = [], [], []
        self.chamfer = chamfer
        self.D = Vector(D).normalized() if D is not None else None


class Part:
    """One MeshPart. kind: textured (bevelled + baked) or glow (Neon, flat)."""

    def __init__(self, role, kind="textured"):
        self.role, self.kind, self.pieces = role, kind, []

    @staticmethod
    def _tile(tile, pts, seg):
        if callable(tile):
            return tile(sum(pts, Vector()) / len(pts), newell(pts), seg)
        if isinstance(tile, (list, tuple)):
            return tile[max(0, min(seg, len(tile) - 1))]
        return tile

    def loft(self, rings, tile, cap0=True, cap1=True, chamfer=None, D=None):
        """Skin closed rings (equal length, CCW around the travel direction) into a solid."""
        pc = Piece(chamfer, D)
        self.pieces.append(pc)
        rings = [[Vector(p) for p in r] for r in rings]
        n = len(rings[0])

        def add(pts, t):
            base = len(pc.verts)
            pc.verts += [tuple(p) for p in pts]
            pc.faces.append(list(range(base, base + len(pts))))
            pc.tiles.append(t)

        for s in range(len(rings) - 1):
            a, b = rings[s], rings[s + 1]
            for j in range(n):
                jj = (j + 1) % n
                pts = [a[j], a[jj], b[jj], b[j]]
                if (pts[0] - pts[1]).length < 1e-6:
                    pts = [pts[0], pts[2], pts[3]]
                elif (pts[2] - pts[3]).length < 1e-6:
                    pts = [pts[0], pts[1], pts[2]]
                if len(pts) == 3 and (pts[1] - pts[0]).cross(pts[2] - pts[0]).length < 1e-9:
                    continue
                add(pts, self._tile(tile, pts, s))

        def point(r):
            return max((p - r[0]).length for p in r) < 1e-6

        if cap0 and not point(rings[0]):
            pts = list(reversed(rings[0]))
            add(pts, self._tile(tile if cap0 is True else cap0, pts, 0))
        if cap1 and not point(rings[-1]):
            pts = list(rings[-1])
            add(pts, self._tile(tile if cap1 is True else cap1, pts, len(rings) - 2))
        return pc

    def lathe(self, p0, axis, profile, sides, tile, rot=None, ref=None, cap0=True, cap1=True, chamfer=None, D=None):
        """Faceted solid of revolution: profile = [(distance along axis, radius), ...]."""
        A = Vector(axis).normalized()
        if ref is None:
            ref = Vector((0, 0, 1)) if abs(A.z) < 0.9 else Vector((0, 1, 0))
        U = Vector(ref).cross(A).normalized()
        W = A.cross(U)
        rot = math.pi / sides if rot is None else rot
        rings = []
        for d, r in profile:
            c = Vector(p0) + A * d
            rings.append([c + (U * math.cos(rot + 2 * math.pi * k / sides) + W * math.sin(rot + 2 * math.pi * k / sides)) * r
                          for k in range(sides)])
        return self.loft(rings, tile, cap0, cap1, chamfer, D)

    def box(self, center, size, tile, R=None, taper=(1.0, 1.0), chamfer=None, D=None):
        c = Vector(center)
        sx, sy, sz = (s / 2 for s in size)
        R = R or Matrix.Identity(3)

        def ring(z, k):
            return [c + R @ Vector((x * k[0], y * k[1], z)) for x, y in ((-sx, -sy), (sx, -sy), (sx, sy), (-sx, sy))]
        return self.loft([ring(-sz, (1, 1)), ring(sz, taper)], tile, chamfer=chamfer, D=D)

    def beam(self, p0, p1, w, h, tile, up=(0, 0, 1), w1=None, h1=None, chamfer=None, D=None):
        """Box from p0 to p1: w across (perpendicular to up), h along up."""
        p0, p1 = Vector(p0), Vector(p1)
        A = (p1 - p0).normalized()
        upv = Vector(up).normalized()
        if abs(A.dot(upv)) > 0.98:
            upv = Vector((0, 1, 0)) if abs(A.y) < 0.9 else Vector((1, 0, 0))
        U = upv.cross(A).normalized()
        W = A.cross(U)

        def ring(c, w_, h_):
            return [c + U * x + W * y for x, y in ((w_ / 2, -h_ / 2), (w_ / 2, h_ / 2), (-w_ / 2, h_ / 2), (-w_ / 2, -h_ / 2))]
        return self.loft([ring(p0, w, h), ring(p1, w1 or w, h1 or h)], tile, chamfer=chamfer, D=D)

    def plate(self, outline, frame, thick, tile, off=0.0, chamfer=None, D=None):
        """Thick plate: outline (a, b) in the frame's plane, front face at `off` along its normal."""
        o, A, B, N = frame
        area = sum(outline[i][0] * outline[(i + 1) % len(outline)][1] - outline[(i + 1) % len(outline)][0] * outline[i][1]
                   for i in range(len(outline)))
        pts = outline if area > 0 else list(reversed(outline))
        back = [o + A * a + B * b + N * (off - thick) for a, b in pts]
        front = [o + A * a + B * b + N * off for a, b in pts]
        return self.loft([back, front], tile, chamfer=chamfer, D=D)

    def bolt(self, pos, normal, size=1.0, tile="brass"):
        """Chunky hex bolt head, not bevelled (it is already a faceted dome)."""
        n = Vector(normal).normalized()
        r, h = 0.075 * size, 0.075 * size
        self.lathe(Vector(pos) - n * 0.03, n, [(0, r), (0.03 + h * 0.55, r), (0.03 + h, r * 0.62)], 6, tile,
                   cap0=False, chamfer=0)


def side_frame(s, x_root, z_root, tilt_deg):
    """Plate frame on side s (+1 = +X): a runs along world y, b up the tilted plate, N outward."""
    t = math.radians(tilt_deg)
    A = Vector((0, 1 if s > 0 else -1, 0))
    B = Vector((s * math.sin(t), 0, math.cos(t)))
    return Vector((s * x_root, 0, z_root)), A, B, A.cross(B)


def fpt(frame, s, y, h, off=0.0):
    o, A, B, N = frame
    return o + A * (s * y) + B * h + N * off


def edge_strip(part, frame, s, pts, width, raise_, tile, D=None):
    """Raised strip along a polyline drawn on a plate's front face (pts are (y, h))."""
    N = frame[3]
    for (y0, h0), (y1, h1) in zip(pts, pts[1:]):
        part.beam(fpt(frame, s, y0, h0, raise_ / 2 - 0.02), fpt(frame, s, y1, h1, raise_ / 2 - 0.02),
                  width, raise_ + 0.04, tile, up=N, D=D)


def rebar(part, p0, direction, length, r=0.065):
    prof = [(0, r)]
    d = 0.1
    while d < length * 0.7:
        prof += [(d - 0.025, r), (d, r * 1.3), (d + 0.025, r)]
        d += 0.13
    prof += [(length * 0.78, r * 0.92), (length, 0.0)]
    part.lathe(p0, direction, prof, 6, "rust", chamfer=0)


def bez(p0, p1, p2, t):
    return p0 * (1 - t) ** 2 + p1 * (2 * (1 - t) * t) + p2 * (t * t)


def belt(part, p0, p1, p2, links, w=0.24, thick=0.09, length=0.12):
    """Ammo belt of brass/steel nail clips following a quadratic curve."""
    p0, p1, p2 = Vector(p0), Vector(p1), Vector(p2)
    for i in range(links):
        t = (i + 0.5) / links
        c = bez(p0, p1, p2, t)
        tan = (bez(p0, p1, p2, min(1, t + 0.01)) - bez(p0, p1, p2, max(0, t - 0.01))).normalized()
        part.beam(c - tan * length / 2, c + tan * length / 2, w, thick, "brass" if i % 2 == 0 else "steel",
                  chamfer=0.02)


def housing(H, w, wn, yf, ys, yr, c, z0, z1, z2f, z2r, z3f, z3r, tiles):
    """Chevron-nosed head housing: narrow skirt, vertical belt, sloped brow top (front lower)."""
    out = [(-wn, yf), (wn, yf), (w, ys), (w, yr - c), (w - c, yr), (-(w - c), yr), (-w, yr - c), (-w, ys)]
    cy = (yf + yr) / 2

    def ring(zf, zr, sx=1.0, sy=1.0, dy=0.0):
        pts = []
        for x, y in out:
            Y = cy + (y - cy) * sy + dy
            t = (Y - yf) / (yr - yf)
            pts.append(Vector((x * sx, Y, zf + (zr - zf) * t)))
        return pts
    H.loft([ring(z0, z0, 0.8, 0.86), ring(z1, z1), ring(z2f, z2r), ring(z3f, z3r, 0.84, 0.9, 0.04)],
           list(tiles[:3]), cap0=tiles[0], cap1=tiles[3])
    return lambda y: z3f + (z3r - z3f) * (y - yf) / (yr - yf)


def top_strips(H, top, y0, y1, xt, ty0=None, ty1=None, hw=0.3):
    """Hazard band down the head's centre line and two tier-colour stripes beside it."""
    slope = top(1.0) - top(0.0)
    up = Vector((0, -slope, 1)).normalized()
    H.beam((0, y0, top(y0) + 0.02), (0, y1, top(y1) + 0.02), hw, 0.12, "hazard", up=up, D=(0.62, -0.62, 0.2))
    ty0 = y0 + 0.06 if ty0 is None else ty0
    ty1 = y1 if ty1 is None else ty1
    for x in (-xt, xt):
        H.beam((x, ty0, top(ty0) + 0.02), (x, ty1, top(ty1) + 0.02), 0.09, 0.1, "tier", up=up)


def visor(part, wn, w, yf, ys, z_in, z_out, tile, slit=0.085):
    """Angry eye slits on the two nose flanks, low at the centre, high at the outside."""
    for s in (1, -1):
        a, b = V(s * wn, yf, 0), V(s * w, ys, 0)
        n = Vector((abs(b.y - a.y) * s, -abs(b.x - a.x), 0)).normalized()
        part.beam(a + (b - a) * 0.18 + V(0, 0, z_in) + n * 0.01, a + (b - a) * 0.78 + V(0, 0, z_out) + n * 0.01,
                  slit, 0.06, tile, up=n, chamfer=0.02)


def muzzle(P, x, y, z, r, L, sides=8):
    P.lathe((x, y, z), FWD, [(0, r), (L, r), (L, r * 0.55), (L - min(0.08, L * 0.6), r * 0.55)], sides,
            ["gunmetal", "gunmetal", "hole"], cap1="hole")
    return Vector((x, y - L, z))


def battery(H, y, z, w=0.66, d=0.38, h=0.5):
    H.box((0, y, z), (w, d, h), "dark")
    H.box((0, y + 0.02, z + h / 2 + 0.04), (w + 0.04, d + 0.06, 0.14), "yellow")


def drum_and_belt(H, cx, cy, cz, r, port):
    """Nail drum on the +X side with a hub, bolts, a mount and a belt arcing into the head."""
    H.lathe((cx, cy, cz), XA, [(0, r), (0.42, r), (0.47, r * 0.76)], 10, ["orange", "gunmetal"], cap0="gunmetal",
            cap1="gunmetal")
    H.lathe((cx + 0.47, cy, cz), XA, [(0, 0.17), (0.07, 0.13)], 8, "dark", cap0=False)
    for k in range(3):
        a = math.radians(90 + 120 * k)
        H.bolt((cx + 0.47, cy + math.cos(a) * r * 0.55, cz + math.sin(a) * r * 0.55), XA, 0.8)
    H.beam((cx - 0.25, cy - 0.38, cz), (cx + 0.08, cy, cz), 0.24, 0.3, "gunmetal", w1=0.34, h1=0.4)
    top = V(cx + 0.23, cy - 0.06, cz + r)
    port = Vector(port)
    belt(H, top, V(cx + 0.18, (top.y + port.y) / 2 + 0.1, max(top.z, port.z) + 0.42), port, 8)
    H.box(port + V(-0.02, -0.04, -0.04), (0.32, 0.3, 0.22), "gunmetal")


def tripod(B, yaw, hub_r, hub_z, hub_h, reach, leg_w, leg_h, foot_r, col_r, bear_r, brace=False):
    B.lathe((0, 0, hub_z), Z, [(0, hub_r), (hub_h, hub_r * 0.92)], 8, "gunmetal")
    legs = dirs((90, 210, 330))
    top = hub_z + hub_h * 0.55
    for d in legs:
        B.beam(d * 0.2 + V(0, 0, top), d * (reach - 0.04) + V(0, 0, 0.12), leg_w, leg_h, "gunmetal",
               w1=leg_w * 0.8, h1=leg_h * 0.8)
        B.lathe(d * reach, Z, [(0, foot_r), (0.22, foot_r * 0.86)], 6, "orange")
    if brace:
        pts = [d * 0.2 + V(0, 0, top) + (d * (reach - 0.04) + V(0, 0, 0.12) - d * 0.2 - V(0, 0, top)) * 0.6 for d in legs]
        for i in range(3):
            a, b = pts[i], pts[(i + 1) % 3]
            B.beam(a, b, 0.15, 0.22, "hazard", D=((b - a).normalized() + Z))
    col0 = hub_z + hub_h - 0.05
    col1 = yaw - 0.18
    B.lathe((0, 0, col0), Z, [(0, col_r * 1.28), (0.13, col_r), (col1 - col0 - 0.1, col_r), (col1 - col0, col_r * 1.26)],
            8, "gunlight")
    B.lathe((0, 0, yaw - 0.2), Z, [(0, bear_r * 0.9), (0.08, bear_r), (0.2, bear_r)], 8, ["orange", "tier"])
    for d in dirs((30, 150, 270)):
        B.bolt(d * (hub_r * 0.93) + V(0, 0, hub_z + hub_h * 0.5), d)


def outriggers(B, yaw, body_r, body_z, body_h, reach, beam_s, jack_r, pad_r, col_r, bear_r, spikes=False):
    B.lathe((0, 0, body_z), Z, [(0, body_r * 0.92), (0.1, body_r), (body_h - 0.1, body_r * 0.97), (body_h, body_r * 0.85)],
            8, "gunmetal")
    by = body_z + body_h * 0.55
    for d in dirs((45, 135, 225, 315)):
        B.beam(d * (body_r * 0.5) + V(0, 0, by), d * reach + V(0, 0, by), beam_s, beam_s, "hazard", D=(d + Z))
        f = d * reach
        jz = 0.3
        B.lathe(f + V(0, 0, jz), Z, [(0, jack_r), (by - jz + 0.12, jack_r), (by - jz + 0.18, jack_r * 1.25),
                                    (by - jz + 0.3, jack_r * 1.25), (by - jz + 0.35, jack_r * 0.9)], 8,
                ["gunmetal", "gunmetal", "orange", "orange"])
        B.lathe(f + V(0, 0, 0.08), Z, [(0, jack_r * 0.5), (0.26, jack_r * 0.5)], 6, "steel", cap0=False)
        B.lathe(f, Z, [(0, pad_r), (0.13, pad_r * 0.84)], 4, "orange", rot=0.0)
        if spikes:
            rebar(B, f + V(0, 0, by + 0.2), d * 0.55 + Z, 0.72)
    for d in dirs((0, 90, 180, 270)):
        B.bolt(d * (body_r * 0.62) + V(0, 0, body_z + body_h), Z)
    col0 = body_z + body_h - 0.05
    col1 = yaw - 0.24
    B.lathe((0, 0, col0), Z, [(0, col_r * 1.3), (0.16, col_r), (col1 - col0 - 0.14, col_r * 0.96), (col1 - col0, col_r * 1.28)],
            8, "gunlight")
    B.lathe((0, 0, col0 + (col1 - col0) * 0.42), Z, [(0, col_r * 1.13), (0.2, col_r * 1.13)], 8, "orange")
    B.lathe((0, 0, yaw - 0.26), Z, [(0, bear_r * 0.88), (0.1, bear_r), (0.26, bear_r)], 8, ["orange", "tier"])


def shield(H, s, x_root, z_root, tilt, outline, thick, mounts, housing_w, stripe, bolts, tile="gunmetal"):
    fr = side_frame(s, x_root, z_root, tilt)
    H.plate([(s * y, h) for y, h in outline], fr, thick, tile)
    t = math.radians(tilt)
    for y, z in mounts:
        h = (z - z_root) / math.cos(t)
        H.beam(V(s * (housing_w - 0.14), y, z), fpt(fr, s, y, h, -thick + 0.03), 0.26, 0.22, "gunmetal", w1=0.36, h1=0.32)
    if stripe:
        edge_strip(H, fr, s, stripe, 0.11, 0.06, "tier")
    for y, h in bolts:
        H.bolt(fpt(fr, s, y, h, 0.0), fr[3], 0.9)
    return fr


# ---------------------------------------------------------------------------------------------
# the four tiers
# ---------------------------------------------------------------------------------------------
def tier1():
    """Plain sturdy tripod + one heavy nail-gun head: magazine, battery, hazard stripes."""
    yaw, bp = 2.05, V(0, -0.62, 2.78)
    B, H, P = Part("Base"), Part("Head"), Part("Barrel")
    tripod(B, yaw, hub_r=0.48, hub_z=0.95, hub_h=0.5, reach=1.46, leg_w=0.32, leg_h=0.36, foot_r=0.36,
           col_r=0.29, bear_r=0.56)
    H.lathe((0, 0, yaw), Z, [(0, 0.54), (0.13, 0.5)], 8, "gunmetal")
    H.lathe((0, 0, yaw + 0.11), Z, [(0, 0.38), (0.12, 0.38), (0.24, 0.5)], 8, "gunmetal")
    top = housing(H, 0.64, 0.36, -0.78, -0.3, 0.9, 0.2, 2.32, 2.56, 2.95, 3.12, 3.12, 3.36,
                  ("gunmetal", "yellow", "yellow", "yellow"))
    top_strips(H, top, -0.52, 0.72, 0.27, ty0=-0.42)
    visor(H, 0.36, 0.64, -0.78, -0.3, 2.74, 2.87, "hole")
    # nail magazine down the +X flank (collated nails, heads up)
    H.loft([[V(0.6, -0.52, 2.24), V(0.78, -0.52, 2.24), V(0.78, -0.52, 2.64), V(0.6, -0.52, 2.64)],
            [V(0.6, 0.66, 2.3), V(0.78, 0.66, 2.3), V(0.78, 0.66, 2.7), V(0.6, 0.66, 2.7)]],
           lambda c, n, s: "nails" if abs(n.x) > 0.6 else "gunmetal", D=(0, 1, 0))
    # armour cheek on the -X flank, front edge raked forward
    fr = side_frame(-1, 0.71, 0.0, 0.0)
    H.plate([(-y, z) for y, z in ((-0.05, 2.64), (0.62, 2.64), (0.62, 3.02), (-0.27, 3.02))], fr, 0.12, "gunmetal")
    for y in (0.02, 0.46):
        H.bolt(V(-0.71, y, 2.83), (-1, 0, 0), 0.85)
    battery(H, 1.0, 2.68, 0.66, 0.36, 0.5)
    # barrel: mantlet collar, steel shroud with an orange band, heavy muzzle
    P.lathe((0, -0.5, bp.z), FWD, [(0, 0.3), (0.3, 0.3), (0.36, 0.25)], 8, "gunmetal")
    P.lathe((0, -0.84, bp.z), FWD, [(0, 0.22), (0.66, 0.2)], 8, "steel")
    P.lathe((0, -1.06, bp.z), FWD, [(0, 0.245), (0.12, 0.245)], 8, "orange")
    m = muzzle(P, 0, -1.46, bp.z, 0.27, 0.26)
    return dict(yaw=yaw, barrel=bp, parts={"Base": B, "Head": H, "Barrel": P}, muzzles=[m], spin=False)


def tier2():
    """Armoured head with tilted side shields, twin barrels, red toolbox ammo box."""
    yaw, bp = 2.2, V(0, -0.72, 2.98)
    B, H, P = Part("Base"), Part("Head"), Part("Barrel")
    tripod(B, yaw, hub_r=0.52, hub_z=0.95, hub_h=0.6, reach=1.64, leg_w=0.34, leg_h=0.38, foot_r=0.4,
           col_r=0.33, bear_r=0.64, brace=True)
    H.lathe((0, 0, yaw), Z, [(0, 0.62), (0.14, 0.58)], 8, "gunmetal")
    H.lathe((0, 0, yaw + 0.12), Z, [(0, 0.44), (0.12, 0.44), (0.24, 0.56)], 8, "gunmetal")
    top = housing(H, 0.74, 0.42, -0.9, -0.36, 1.0, 0.24, 2.5, 2.74, 3.18, 3.38, 3.38, 3.66,
                  ("gunmetal", "yellow", "yellow", "yellow"))
    top_strips(H, top, -0.62, 0.82, 0.31, ty0=-0.5)
    visor(H, 0.42, 0.74, -0.9, -0.36, 2.92, 3.06, "hole")
    outline = [(-1.32, 0.04), (-1.0, 0.77), (0.55, 1.28), (0.72, 0.85), (0.55, -0.04)]
    for s in (1, -1):
        shield(H, s, 0.98, 2.66, 10, outline, 0.14, [(-0.25, 3.0), (0.4, 3.0)], 0.74,
               [(-0.96, 0.66), (0.5, 1.13)], [(-0.9, 0.2), (-0.15, 0.2), (0.45, 0.2)])
    # toolbox ammo box, rear +X, with lid, handle and brass latches; nail strip feeds the head
    H.box((0.9, 1.05, 2.66), (0.6, 0.62, 0.44), "red")
    H.box((0.9, 1.05, 2.95), (0.62, 0.64, 0.16), "red", taper=(0.84, 0.8))
    for y in (0.86, 1.24):
        H.beam((0.9, y, 3.0), (0.9, y, 3.18), 0.07, 0.07, "dark", chamfer=0.015)
    H.beam((0.9, 0.83, 3.17), (0.9, 1.27, 3.17), 0.08, 0.08, "dark", chamfer=0.015)
    for y in (0.9, 1.2):
        H.box((1.205, y, 2.84), (0.05, 0.1, 0.13), "brass", chamfer=0.015)
    H.beam((0.78, 0.86, 2.98), (0.5, 0.6, 3.28), 0.2, 0.08, "nails", D=(-0.5, -0.5, 0.6))
    battery(H, 1.12, 2.86, 0.62, 0.38, 0.5)
    # twin barrels on a receiver, bridged by a clamp
    P.box((0, -0.86, bp.z), (0.86, 0.42, 0.5), "gunmetal")
    ms = []
    for x in (-0.21, 0.21):
        P.lathe((x, -1.05, bp.z), FWD, [(0, 0.15), (0.95, 0.14)], 8, "steel")
        P.lathe((x, -1.3, bp.z), FWD, [(0, 0.18), (0.12, 0.18)], 8, "orange")
        ms.append(muzzle(P, x, -1.94, bp.z, 0.19, 0.18))
    P.box((0, -1.7, bp.z), (0.72, 0.14, 0.34), "gunmetal")
    return dict(yaw=yaw, barrel=bp, parts={"Base": B, "Head": H, "Barrel": P}, muzzles=ms, spin=False)


def tier3():
    """Quad barrels, drum + nail belt, outrigger stabiliser feet, warning beacon."""
    yaw, bp = 2.4, V(0, -0.82, 3.2)
    B, H, P = Part("Base"), Part("Head"), Part("Barrel")
    outriggers(B, yaw, body_r=0.66, body_z=0.5, body_h=0.55, reach=1.78, beam_s=0.3, jack_r=0.19, pad_r=0.38,
               col_r=0.37, bear_r=0.72)
    H.lathe((0, 0, yaw), Z, [(0, 0.72), (0.15, 0.68)], 8, "gunmetal")
    H.lathe((0, 0, yaw + 0.13), Z, [(0, 0.5), (0.12, 0.5), (0.25, 0.64)], 8, "gunmetal")
    top = housing(H, 0.82, 0.46, -1.0, -0.4, 1.05, 0.28, 2.72, 2.96, 3.48, 3.7, 3.7, 3.98,
                  ("gunmetal", "gunmetal", "yellow", "yellow"))
    top_strips(H, top, -0.74, 0.3, 0.34, ty0=-0.62, ty1=0.86)
    visor(H, 0.46, 0.82, -1.0, -0.4, 3.16, 3.31, "amber")
    outline = [(-1.45, 0.06), (-1.12, 0.88), (0.6, 1.42), (0.8, 0.9), (0.66, -0.04)]
    for s in (1, -1):
        fr = shield(H, s, 1.06, 2.86, 13, outline, 0.15, [(-0.3, 3.2), (0.45, 3.2)], 0.82,
                    [(-1.06, 0.76), (0.55, 1.29)], [])
        layer = [(-1.12, 0.2), (-0.92, 0.7), (0.38, 1.0), (0.5, 0.16)]
        H.plate([(s * y, h) for y, h in layer], fr, 0.08, "yellow", off=0.06)
        for y, h in ((-0.88, 0.3), (-0.2, 0.3), (0.32, 0.3), (0.2, 0.86)):
            H.bolt(fpt(fr, s, y, h, 0.06), fr[3], 0.85)
    drum_and_belt(H, 0.74, 1.3, 3.1, 0.46, (0.6, 0.48, 3.74))
    battery(H, 1.18, 3.02, 0.62, 0.4, 0.52)
    # warning beacon on the rear deck
    yb = 0.62
    H.lathe((0, yb, top(yb) - 0.04), Z, [(0, 0.21), (0.16, 0.21), (0.21, 0.17)], 8, "gunmetal")
    H.lathe((0, yb, top(yb) + 0.16), Z, [(0, 0.16), (0.14, 0.16), (0.25, 0.1), (0.31, 0.0)], 8, "amber")
    # quad barrels: receiver with a tier band, mid + front clamps
    P.box((0, -0.95, bp.z), (0.9, 0.5, 0.78), "gunmetal")
    P.box((0, -1.06, bp.z), (0.94, 0.1, 0.82), "tier", chamfer=0.03)
    ms = []
    for x in (-0.19, 0.19):
        for dz in (-0.18, 0.18):
            P.lathe((x, -1.15, bp.z + dz), FWD, [(0, 0.13), (1.0, 0.12)], 8, "steel")
            ms.append(muzzle(P, x, -2.08, bp.z + dz, 0.16, 0.14))
    P.box((0, -1.6, bp.z), (0.78, 0.13, 0.74), "gunmetal")
    P.box((0, -2.0, bp.z), (0.74, 0.12, 0.7), "orange")
    return dict(yaw=yaw, barrel=bp, parts={"Base": B, "Head": H, "Barrel": P}, muzzles=ms, spin=False)


def tier4():
    """Gatling cluster, big shield wings, exhausts, rebar spikes, Neon seams/eyes/core."""
    yaw, bp = 2.6, V(0, -0.92, 3.38)
    B, H, P, G = Part("Base"), Part("Head"), Part("Barrel"), Part("Glow", kind="glow")
    outriggers(B, yaw, body_r=0.84, body_z=0.45, body_h=0.74, reach=1.86, beam_s=0.34, jack_r=0.22, pad_r=0.42,
               col_r=0.41, bear_r=0.8, spikes=True)
    H.lathe((0, 0, yaw), Z, [(0, 0.8), (0.16, 0.76)], 8, "gunmetal")
    H.lathe((0, 0, yaw + 0.14), Z, [(0, 0.56), (0.12, 0.56), (0.26, 0.7)], 8, "gunmetal")
    w, wn, yf, ys = 0.9, 0.52, -1.08, -0.44
    top = housing(H, w, wn, yf, ys, 1.1, 0.3, 2.94, 3.18, 3.72, 3.95, 3.95, 4.25,
                  ("gunmetal", "gunmetal", "yellow", "yellow"))
    top_strips(H, top, -0.6, 0.12, 0.36, ty0=-0.58, ty1=0.95)
    # heavy brow over the gatling with a tier-red arrowhead
    R = Matrix.Rotation(math.radians(14), 3, "X")
    bc = V(0, -0.98, 4.04)
    H.box(bc, (1.08, 0.62, 0.26), "gunmetal", R=R, taper=(0.82, 0.86))
    up = R @ Z
    for sx in (-1, 1):
        H.beam(bc + R @ V(sx * 0.36, 0.2, 0.13), bc + R @ V(0, -0.22, 0.13), 0.1, 0.08, "tier", up=up)
    # glowing eye slits on the nose flanks, angled down toward the centre
    visor(G, wn, w, yf, ys, 3.52, 3.66, "hole")
    # wings: thick swept plates, yellow leading-edge armour, red tier stripe, Neon seams, rebar
    outline = [(-1.55, -0.12), (-1.3, 0.75), (-0.45, 1.3), (0.5, 2.3), (0.62, 1.7), (0.88, 0.85), (0.72, -0.15)]
    for s in (1, -1):
        fr = side_frame(s, 0.98, 3.1, 32)
        H.plate([(s * y, h) for y, h in outline], fr, 0.17, "gunmetal")
        for y, z in ((-0.4, 3.35), (0.42, 3.35)):
            hh = (z - 3.1) / math.cos(math.radians(32))
            H.beam(V(s * (w - 0.12), y, z), fpt(fr, s, y, hh, -0.14), 0.28, 0.24, "gunmetal", w1=0.38, h1=0.34)
        edge_strip(H, fr, s, [(-1.24, 0.66), (-0.45, 1.17), (0.42, 2.12)], 0.17, 0.07, "yellow")
        edge_strip(H, fr, s, [(-1.4, 0.06), (0.62, 0.04)], 0.1, 0.05, "tier")
        edge_strip(G, fr, s, [(-1.14, 0.42), (-0.45, 0.9), (0.3, 1.66)], 0.07, 0.06, "hole")
        for y, h in ((-0.95, 0.24), (-0.25, 0.24), (0.42, 0.24)):
            H.bolt(fpt(fr, s, y, h, 0.0), fr[3], 0.9)
        o, A, Bv, N = fr
        for y, h in ((-0.12, 1.62), (0.26, 2.0)):
            rebar(H, fpt(fr, s, y, h - 0.12, -0.085), (Bv + V(0, 0.5, 0) + N * 0.18).normalized(), 0.55, r=0.06)
    # rear exhaust block (vent slats) and twin stacks
    H.box((0, 1.12, 3.45), (0.96, 0.34, 0.62), lambda c, n, s: "vent" if n.y > 0.6 else "gunmetal", D=(0, 0, 1))
    for sx in (-1, 1):
        p0, p1 = V(sx * 0.34, 0.98, 3.5), V(sx * 0.44, 1.66, 4.34)
        L = (p1 - p0).length
        H.lathe(p0, p1 - p0, [(0, 0.15), (L * 0.55, 0.15), (L * 0.6, 0.17), (L * 0.72, 0.17), (L * 0.77, 0.15),
                              (L * 0.9, 0.17), (L, 0.2), (L, 0.12), (L - 0.12, 0.12)], 8,
                ["steel", "orange", "orange", "orange", "steel", "steel", "steel", "hole"], cap1="hole")
    # Neon core on the rear deck inside a hex frame
    yc = 0.55
    H.lathe((0, yc, top(yc) - 0.06), Z, [(0, 0.36), (0.12, 0.36), (0.12, 0.27), (0.07, 0.27)], 6,
            ["gunmetal", "gunmetal", "dark"], cap1="dark")
    G.lathe((0, yc, top(yc) - 0.01), Z, [(0, 0.25), (0.05, 0.25)], 6, "hole")
    drum_and_belt(H, 0.74, 1.4, 3.32, 0.46, (0.66, 0.5, 4.0))
    # gatling: rear hub, spindle, six barrels, mid + front clamps (all symmetric about the spin axis)
    P.lathe((0, -0.78, bp.z), FWD, [(0, 0.4), (0.08, 0.46), (0.4, 0.46), (0.46, 0.4)], 8, ["gunmetal", "orange", "gunmetal"])
    P.lathe((0, -1.2, bp.z), FWD, [(0, 0.11), (1.2, 0.11)], 6, "steel")
    P.lathe((0, -1.66, bp.z), FWD, [(0, 0.42), (0.12, 0.42)], 6, "gunmetal", rot=0.0)
    P.lathe((0, -2.12, bp.z), FWD, [(0, 0.43), (0.14, 0.43)], 6, "tier", rot=0.0)
    ms = []
    for k in range(6):
        a = math.radians(90 + 60 * k)
        x, z = 0.27 * math.cos(a), bp.z + 0.27 * math.sin(a)
        P.lathe((x, -1.2, z), FWD, [(0, 0.095), (1.12, 0.095)], 6, "steel")
        ms.append(muzzle(P, x, -2.3, z, 0.12, 0.1, sides=6))
    return dict(yaw=yaw, barrel=bp, parts={"Base": B, "Head": H, "Barrel": P, "Glow": G}, muzzles=ms, spin=True)


TIER_FN = {1: tier1, 2: tier2, 3: tier3, 4: tier4}

# ---------------------------------------------------------------------------------------------
# realise pieces -> one mesh per part
# ---------------------------------------------------------------------------------------------


def process_piece(pc, bevel):
    bm = bmesh.new()
    for f, t in zip(pc.faces, pc.tiles):
        vs = [bm.verts.new(pc.verts[i]) for i in f]
        face = bm.faces.new(vs)
        face.material_index = TILE_INDEX[t]
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    width = CHAMFER if pc.chamfer is None else pc.chamfer
    if bevel and width > 0:
        cos = [v.co for v in bm.verts]
        span = min(max(c[i] for c in cos) - min(c[i] for c in cos) for i in range(3))
        # tilted plates are thin along their own normal, not along a world axis
        lim = min(span if span > 1e-3 else 1e9, piece_thickness(bm))
        width = min(width, 0.3 * lim)
        edges = [e for e in bm.edges if e.is_manifold and e.calc_face_angle(0.0) > BEVEL_ANGLE]
        if edges:
            bmesh.ops.bevel(bm, geom=edges, offset=width, segments=1, profile=0.5, affect="EDGES",
                            clamp_overlap=True, material=-1)
        bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=list(bm.edges))
    bm.normal_update()
    return bm


def piece_thickness(bm):
    """Smallest extent along the normals of the piece's biggest faces (tilted plates, beams)."""
    best = 1e9
    faces = sorted(bm.faces, key=lambda f: -f.calc_area())[:3]
    for f in faces:
        n = f.normal
        ds = [v.co.dot(n) for v in bm.verts]
        best = min(best, max(ds) - min(ds))
    return best


def assign_uvs(bm, pc):
    uvl = bm.loops.layers.uv.new("UVMap")
    cos = [v.co.copy() for v in bm.verts]
    lo = Vector([min(c[i] for c in cos) for i in range(3)])
    hi = Vector([max(c[i] for c in cos) for i in range(3)])
    ext = hi - lo
    D = pc.D
    if D is None:
        k = max(range(3), key=lambda i: ext[i])
        D = Vector([1.0 if i == k else 0.0 for i in range(3)])
    ds = [c.dot(D) for c in cos]
    dmin = min(ds)
    span = max(STRIPE_SPAN, max(ds) - dmin + 1e-6)
    for f in bm.faces:
        name = TILE_NAMES[f.material_index]
        u0, v0, u1, v1 = TILES[name]
        n = f.normal
        if name in STRIPES:
            W = n.cross(D)
            if W.length < 1e-4:
                W = n.orthogonal()
            W.normalize()
            if W.z < -1e-4 or (abs(W.z) <= 1e-4 and W.x + W.y < 0):
                W = -W
            ws = [l.vert.co.dot(W) for l in f.loops]
            wmin, wr = min(ws), max(max(ws) - min(ws), 1e-4)
            mu, mv = 0.004, (v1 - v0) * 0.14
            for l, wv in zip(f.loops, ws):
                l[uvl].uv = (u0 + mu + (l.vert.co.dot(D) - dmin) / span * (u1 - u0 - 2 * mu),
                             v0 + mv + (wv - wmin) / wr * (v1 - v0 - 2 * mv))
        else:
            ax = max(range(3), key=lambda i: abs(n[i]))
            a, b = ((1, 2), (0, 2), (0, 1))[ax]
            sc = 1.0 / max(ext[a], ext[b], 1.6)
            m = (u1 - u0) * 0.07
            for l in f.loops:
                p = l.vert.co
                l[uvl].uv = (u0 + m + (p[a] - lo[a]) * sc * (u1 - u0 - 2 * m),
                             v0 + m + (p[b] - lo[b]) * sc * (v1 - v0 - 2 * m))
    return uvl


def realize(part, name, pivot, mat, coll):
    Vs, Fs, UVs = [], [], []
    for pc in part.pieces:
        bm = process_piece(pc, part.kind == "textured")
        uvl = assign_uvs(bm, pc) if part.kind == "textured" else None
        bm.verts.index_update()
        off = len(Vs)
        Vs += [tuple(v.co - pivot) for v in bm.verts]
        for f in bm.faces:
            Fs.append([off + v.index for v in f.verts])
            UVs.append([tuple(l[uvl].uv) for l in f.loops] if uvl else [(0.5, 0.5)] * len(f.verts))
        bm.free()
    me = bpy.data.meshes.new(name)
    me.from_pydata(Vs, [], Fs)
    uv = me.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", [c for face in UVs for p in face for c in p])
    me.validate()
    bm = bmesh.new()
    bm.from_mesh(me)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if not e.is_manifold or e.calc_face_angle(math.pi) > SHARP:
            e.smooth = False
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.location = pivot
    return ob


# ---------------------------------------------------------------------------------------------
# materials + bake (chest-kit icon lighting, retuned for a 4-5 stud turret)
# ---------------------------------------------------------------------------------------------
def srgb_lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def source_material(name, image):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bs = nt.nodes.get("Principled BSDF")
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = image
    nt.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 0.8
    return m


def glow_material(name, strength=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = (*[srgb_lin(c) for c in GLOW_RGB], 1)
    bs.inputs["Emission Color"].default_value = (*[srgb_lin(c) for c in GLOW_RGB], 1)
    bs.inputs["Emission Strength"].default_value = strength
    return m


BAKE = {
    "key_dir": (-0.45, -0.6, 0.75), "key_lo": 0.64, "key_hi": 1.16,
    "ao_distance": 0.32, "ao_lo": 0.48,
    "height_lo": 0.84, "height_hi": 1.05,
    "rim_dir": (0.75, 0.55, 0.15), "rim": 0.14, "rim_color": (0.45, 0.62, 1.0),
    "edge": 0.58, "edge_radius": 0.045, "edge_tint": (1.0, 0.93, 0.78), "edge_tint_mix": 0.5,
}


def select_only(objs, active=None):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def bake(mat, objs, src_image, top, out_path):
    P = BAKE
    for o in objs:
        uv = o.data.uv_layers.new(name="BakeUV")
        o.data.uv_layers.active = uv
        uv.active_render = True
    select_only(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(50), island_margin=0.004, correct_aspect=True)
    bpy.ops.uv.pack_islands(rotate=True, margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")

    nt = mat.node_tree
    nt.nodes.clear()
    N, L = nt.nodes.new, nt.links.new
    uvsrc = N("ShaderNodeUVMap")
    uvsrc.uv_map = "UVMap"
    tex = N("ShaderNodeTexImage")
    tex.image = src_image
    L(uvsrc.outputs["UV"], tex.inputs["Vector"])
    geo = N("ShaderNodeNewGeometry")

    def dot_light(direction):
        d = N("ShaderNodeVectorMath")
        d.operation = "DOT_PRODUCT"
        L(geo.outputs["True Normal"], d.inputs[0])
        d.inputs[1].default_value = Vector(direction).normalized()
        c = N("ShaderNodeClamp")
        L(d.outputs["Value"], c.inputs["Value"])
        return c.outputs["Result"]

    def remap(sock, a, b, lo, hi):
        r = N("ShaderNodeMapRange")
        r.inputs["From Min"].default_value, r.inputs["From Max"].default_value = a, b
        r.inputs["To Min"].default_value, r.inputs["To Max"].default_value = lo, hi
        L(sock, r.inputs["Value"])
        return r.outputs["Result"]

    key = remap(dot_light(P["key_dir"]), 0, 1, P["key_lo"], P["key_hi"])
    ao = N("ShaderNodeAmbientOcclusion")
    ao.samples = 16
    ao.inputs["Distance"].default_value = P["ao_distance"]
    aof = remap(ao.outputs["AO"], 0.15, 1.0, P["ao_lo"], 1.0)
    sep = N("ShaderNodeSeparateXYZ")
    L(geo.outputs["Position"], sep.inputs["Vector"])
    height = remap(sep.outputs["Z"], 0.0, top, P["height_lo"], P["height_hi"])
    s1 = N("ShaderNodeMath"); s1.operation = "MULTIPLY"; L(key, s1.inputs[0]); L(aof, s1.inputs[1])
    s2 = N("ShaderNodeMath"); s2.operation = "MULTIPLY"; L(s1.outputs[0], s2.inputs[0]); L(height, s2.inputs[1])
    lit = N("ShaderNodeMix"); lit.data_type = "RGBA"; lit.blend_type = "MULTIPLY"; lit.inputs["Factor"].default_value = 1.0
    L(tex.outputs["Color"], lit.inputs[6])
    grey = N("ShaderNodeCombineColor")
    for i in range(3):
        L(s2.outputs[0], grey.inputs[i])
    L(grey.outputs["Color"], lit.inputs[7])
    rim = remap(dot_light(P["rim_dir"]), 0.2, 1.0, 0.0, P["rim"])
    rimadd = N("ShaderNodeMix"); rimadd.data_type = "RGBA"; rimadd.blend_type = "ADD"
    L(rim, rimadd.inputs["Factor"]); L(lit.outputs[2], rimadd.inputs[6]); rimadd.inputs[7].default_value = (*P["rim_color"], 1)
    bev = N("ShaderNodeBevel"); bev.samples = 8; bev.inputs["Radius"].default_value = P["edge_radius"]
    ed = N("ShaderNodeVectorMath"); ed.operation = "DOT_PRODUCT"
    L(bev.outputs["Normal"], ed.inputs[0]); L(geo.outputs["True Normal"], ed.inputs[1])
    edge = remap(ed.outputs["Value"], 0.985, 0.80, 0.0, P["edge"])
    edge_up = N("ShaderNodeMath"); edge_up.operation = "MULTIPLY"
    L(edge, edge_up.inputs[0]); L(remap(dot_light((-0.3, -0.35, 0.9)), 0, 1, 0.45, 1.0), edge_up.inputs[1])
    tint = N("ShaderNodeMix"); tint.data_type = "RGBA"; tint.inputs["Factor"].default_value = P["edge_tint_mix"]
    L(tex.outputs["Color"], tint.inputs[6]); tint.inputs[7].default_value = (*P["edge_tint"], 1)
    final = N("ShaderNodeMix"); final.data_type = "RGBA"
    L(edge_up.outputs[0], final.inputs["Factor"]); L(rimadd.outputs[2], final.inputs[6]); L(tint.outputs[2], final.inputs[7])
    em = N("ShaderNodeEmission"); L(final.outputs[2], em.inputs["Color"])
    out = N("ShaderNodeOutputMaterial"); L(em.outputs["Emission"], out.inputs["Surface"])

    img = bpy.data.images.new(out_path.stem, BAKE_SIZE, BAKE_SIZE, alpha=False)
    target = N("ShaderNodeTexImage")
    target.image = img
    nt.nodes.active = target
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = BAKE_SAMPLES
    scene.render.bake.margin = 8
    select_only(objs)
    bpy.ops.object.bake(type="EMIT")
    img.filepath_raw = str(out_path)
    img.file_format = "PNG"
    img.save()
    img.filepath = str(out_path)

    nt.nodes.clear()
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bs.inputs["Roughness"].default_value = 0.8
    bs.inputs["Specular IOR Level"].default_value = 0.15
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = img
    nt.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
    o_ = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(bs.outputs["BSDF"], o_.inputs["Surface"])
    for o in objs:
        o.data.uv_layers.remove(o.data.uv_layers["UVMap"])
        o.data.uv_layers["BakeUV"].name = "UVMap"
        o.data.uv_layers["UVMap"].active_render = True
    return img


# ---------------------------------------------------------------------------------------------
# build all tiers
# ---------------------------------------------------------------------------------------------
def roblox(v):
    return [round(-v[0], 4), round(v[2], 4), round(v[1], 4)]


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
built = {}
PARK = 400.0

for t in TIERS:
    src = save_png(paint_atlas(t), ROOT / "textures/source" / f"HandymanTurret_T{t}_paint.png", f"T{t}_paint")
    mat = source_material(f"HandymanTurret_T{t}", src)
    glow = glow_material("HandymanTurret_T4_Glow", 1.0) if t == 4 else None
    coll = bpy.data.collections.new(f"T{t}")
    scene.collection.children.link(coll)
    spec = TIER_FN[t]()
    pivots = {"Base": Vector((0, 0, 0)), "Head": Vector((0, 0, spec["yaw"])), "Barrel": spec["barrel"],
              "Glow": Vector((0, 0, spec["yaw"]))}
    objs = {}
    for role, part in spec["parts"].items():
        objs[role] = realize(part, f"HandymanTurret_T{t}_{role}", pivots[role], glow if part.kind == "glow" else mat, coll)
    bpy.context.view_layer.update()
    textured = [objs[r] for r in ("Base", "Head", "Barrel")]
    top = max((o.matrix_world @ Vector(c)).z for o in objs.values() for c in o.bound_box)
    tex_path = ROOT / "textures" / f"HandymanTurret_T{t}.png"
    if not QUICK:
        bake(mat, textured, src, top, tex_path)
        if glow:
            glow.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 4.0
        select_only(list(objs.values()), objs["Base"])
        bpy.ops.export_scene.fbx(filepath=str(ROOT / "exports/fbx" / f"HandymanTurret_T{t}.fbx"), use_selection=True,
                                 object_types={"MESH"}, axis_forward="-Z", axis_up="Y", path_mode="COPY",
                                 embed_textures=True, add_leaf_bones=False)
        bpy.ops.export_scene.gltf(filepath=str(ROOT / "exports/glb" / f"HandymanTurret_T{t}.glb"), export_format="GLB",
                                  use_selection=True, export_apply=True)
    elif glow:
        glow.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 4.0
    # report + spec data (Roblox axes, studs, relative to the Base pivot)
    info = {"parts": {}, "triangles": {}}
    allpts = []
    for role, o in objs.items():
        me = o.data
        me.calc_loop_triangles()
        pts = [o.matrix_world @ v.co for v in me.vertices]
        allpts += pts
        lo = Vector([min(p[i] for p in pts) for i in range(3)])
        hi = Vector([max(p[i] for p in pts) for i in range(3)])
        c = (lo + hi) / 2
        size = hi - lo
        piv = o.location.copy()
        entry = {"mesh": o.name, "pivot": roblox(piv), "center": roblox(c),
                 "size": [round(size.x, 4), round(size.z, 4), round(size.y, 4)],
                 "pivotOffset": roblox(piv - c), "triangles": len(me.loop_triangles), "vertices": len(me.vertices)}
        if role == "Glow":
            entry["parent"] = "Head"
        info["parts"][role] = entry
        info["triangles"][role] = len(me.loop_triangles)
    info["triangles"]["total"] = sum(v for k, v in info["triangles"].items())
    info["height"] = round(max(p.z for p in allpts), 3)
    info["radius"] = round(max(math.hypot(p.x, p.y) for p in allpts), 3)
    info["muzzles"] = [roblox(m) for m in spec["muzzles"]]
    info["spin"] = spec["spin"]
    built[t] = SimpleNamespace(objs=objs, spec=spec, info=info, mat=mat, tex=tex_path.name)
    for o in objs.values():
        o.location.x += PARK * t          # park so the next tier's bake sees no neighbours
    print(f"TIER_BUILT T{t}", json.dumps(info["triangles"]), "height", info["height"], "radius", info["radius"], flush=True)

# ---------------------------------------------------------------------------------------------
# renders
# ---------------------------------------------------------------------------------------------
for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        scene.render.engine = engine
        break
    except TypeError:
        continue
try:
    scene.eevee.taa_render_samples = 32
except AttributeError:
    pass
scene.view_settings.view_transform = "Standard"
sky = bpy.data.worlds.new("Sky")
sky.use_nodes = True
sky.node_tree.nodes["Background"].inputs["Color"].default_value = (0.52, 0.70, 0.92, 1)
sky.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
icon_world = bpy.data.worlds.new("IconWorld")
icon_world.use_nodes = True
icon_world.node_tree.nodes["Background"].inputs[0].default_value = (0.8, 0.85, 0.95, 1)
icon_world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
sun.data.energy, sun.data.angle, sun.data.color = 3.2, math.radians(12), (1.0, 0.96, 0.88)
sun.rotation_euler = (math.radians(48), 0, math.radians(-38))
scene.collection.objects.link(sun)
icon_sun = bpy.data.objects.new("IconSun", bpy.data.lights.new("IconSun", "SUN"))
icon_sun.data.energy = 1.2
icon_sun.rotation_euler = (math.radians(50), 0, math.radians(-30))
scene.collection.objects.link(icon_sun)
fme = bpy.data.meshes.new("Preview_Floor")
bmf = bmesh.new()
bmesh.ops.create_circle(bmf, cap_ends=True, segments=48, radius=30)
bmf.to_mesh(fme)
bmf.free()
floor = bpy.data.objects.new("Preview_Floor", fme)
fmat = bpy.data.materials.new("Preview_Floor")
fmat.use_nodes = True
fmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.42, 0.44, 0.45, 1)
fme.materials.append(fmat)
scene.collection.objects.link(floor)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.data.clip_end = 1000
scene.collection.objects.link(cam)
scene.camera = cam
VIEW_3Q = Vector((-0.8, -1.0, 0.62))


def place(t, offset):
    for role, o in built[t].objs.items():
        piv = Vector((0, 0, 0)) if role == "Base" else (Vector((0, 0, built[t].spec["yaw"])) if role in ("Head", "Glow")
                                                       else built[t].spec["barrel"])
        o.location = piv + Vector(offset)
        o.hide_render = abs(offset[0]) >= PARK


def park_all():
    for t in built:
        place(t, (PARK * t, 0, 0))


def frame(objs, d, res, lens=50.0, ortho=False, pad=1.1, target=None):
    scene.render.resolution_x, scene.render.resolution_y = res
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    d = Vector(d).normalized()
    R = (-d).to_track_quat("-Z", "Y").to_matrix()
    right, up = R @ Vector((1, 0, 0)), R @ Vector((0, 1, 0))
    xs, ys, zs = [p.dot(right) for p in pts], [p.dot(up) for p in pts], [p.dot(d) for p in pts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    wx, wy = (max(xs) - min(xs)) * pad, (max(ys) - min(ys)) * pad
    aspect = res[0] / res[1]
    centre = right * cx + up * cy + d * ((min(zs) + max(zs)) / 2)
    if target is not None:
        centre = Vector(target)
    cam.rotation_euler = R.to_euler()
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = max(wx, wy * aspect)
        cam.location = centre + d * 60
    else:
        cam.data.type = "PERSP"
        cam.data.lens = lens
        fx = 2 * math.atan(18 / lens) if aspect >= 1 else 2 * math.atan(18 / lens * aspect)
        fy = 2 * math.atan(math.tan(fx / 2) / aspect)
        dist = max(wx / 2 / math.tan(fx / 2), wy / 2 / math.tan(fy / 2)) + (max(zs) - min(zs)) / 2
        cam.location = centre + d * dist


def shoot(path, transparent=False, icon=False):
    scene.render.film_transparent = transparent
    scene.world = icon_world if icon else sky
    sun.hide_render = icon
    icon_sun.hide_render = not icon
    floor.hide_render = icon
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def tier_objs(t):
    return list(built[t].objs.values())


def figure(offset):
    """Plain 5-stud block figure for scale in the lineup."""
    F = Part("Figure", kind="glow")
    ox, oy = offset
    for x in (-0.27, 0.27):
        F.box((ox + x, oy, 1.1), (0.5, 0.5, 2.2), "gunlight")
    F.box((ox, oy, 3.0), (1.6, 0.8, 1.6), "gunlight")
    for x in (-1.05, 1.05):
        F.box((ox + x, oy, 3.0), (0.5, 0.5, 1.6), "gunlight")
    F.box((ox, oy, 4.38), (1.1, 1.1, 1.1), "gunlight")
    m = bpy.data.materials.new("Figure")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.57, 0.6, 1)
    return realize(F, "ScaleFigure", Vector((0, 0, 0)), m, scene.collection)


LINEUP_X = {1: -8.1, 2: -2.9, 3: 2.6, 4: 8.3}
outdir = QUICK_OUT if QUICK else ROOT / "previews"
outdir.mkdir(parents=True, exist_ok=True)

if QUICK:
    park_all()
    for t in built:
        place(t, (LINEUP_X[t], 0, 0))
    objs = [o for t in built for o in tier_objs(t)]
    frame(objs, (-0.45, -1.0, 0.5), (1700, 720), lens=50)
    shoot(outdir / "quick_3q.png")
    frame(objs, (-0.35, -0.75, 1.25), (640, 300), lens=50, pad=1.05)   # ~in-game pixel size, high camera
    shoot(outdir / "quick_gameplay.png")
    frame(objs, (-0.35, -0.75, 1.25), (1600, 750), lens=50, pad=1.05)
    shoot(outdir / "quick_gameplay_big.png")
    frame(objs, (0.5, 1.0, 0.55), (1700, 720), lens=50)
    shoot(outdir / "quick_back.png")
    print("QUICK_DONE", outdir, flush=True)
else:
    for t in built:
        park_all()
        place(t, (0, 0, 0))
        frame(tier_objs(t), VIEW_3Q, (1200, 1000), lens=50, pad=1.15)
        shoot(outdir / f"HandymanTurret_T{t}_3q.png")
        frame(tier_objs(t), VIEW_3Q, (512, 512), ortho=True, pad=1.08)
        shoot(outdir / f"icon_T{t}.png", transparent=True, icon=True)
    park_all()
    if len(built) == 4:
        for t in built:
            place(t, (LINEUP_X[t], 0, 0))
        fig = figure((-12.0, 0.4))
        frame([o for t in built for o in tier_objs(t)] + [fig], (-0.4, -1.0, 0.45), (1800, 820), lens=50, pad=1.06)
        shoot(outdir / "lineup.png")
        fig.hide_render = True
        park_all()
    if 4 in built:
        place(4, (0, 0, 0))
        scene.render.resolution_x, scene.render.resolution_y = 1400, 1050
        cam.data.type = "PERSP"
        cam.data.lens = 35
        cam.location = Vector((-4.8, -8.2, 4.2))      # front-left, head height: both wings rise in a V
        tgt = Vector((0, -0.3, 3.0))
        cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
        try:   # soft bloom on the Neon seams; skipped quietly if this compositor API differs
            ng = bpy.data.node_groups.new("TurretBloom", "CompositorNodeTree")
            ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
            rl = ng.nodes.new("CompositorNodeRLayers")
            gl = ng.nodes.new("CompositorNodeGlare")
            if hasattr(gl, "glare_type"):
                gl.glare_type = "BLOOM"
            elif "Type" in gl.inputs:
                gl.inputs["Type"].default_value = "Bloom"
            for k, v in (("Threshold", 1.6), ("Strength", 0.7), ("Size", 0.6)):
                if k in gl.inputs:
                    gl.inputs[k].default_value = v
            go = ng.nodes.new("NodeGroupOutput")
            ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
            ng.links.new(gl.outputs["Image"], go.inputs[0])
            scene.compositing_node_group = ng
            scene.render.use_compositing = True
        except Exception as exc:  # noqa: BLE001
            print("BLOOM_SKIPPED", exc, flush=True)
        shoot(outdir / "hero_T4.png")
        scene.render.use_compositing = False

    # ---- reports ------------------------------------------------------------------------------
    rep = {"blender_version": bpy.app.version_string,
           "authoring": "final Roblox stud size; import 1:1; never scale beyond +/-15% (baked 0-1 atlas)",
           "budgets": BUDGET, "tiers": {}}
    spec_out = {
        "axes": "Roblox axes, studs, relative to the Base pivot. roblox = (-x, z, y) of Blender. Barrels point to -Z "
                "(the model LookVector) at rest. Studio's FBX importer has turned these kits 180 degrees about Y and once "
                "laid a file on its back: normalise the import with the part centres below (see README).",
        "forward": [0, 0, -1], "up": [0, 1, 0],
        "joints": {"Head": "yaw about +Y through Head.pivot (on the Base centre line)",
                   "Barrel": "pitch about the Head's X axis through Barrel.pivot; recoil along +Z (backwards)",
                   "spin": "when spin is true, the whole Barrel part spins about its own forward (Z) axis through Barrel.pivot"},
        "glow_srgb": list(GLOW_RGB),
        "tiers": {}}
    for t, b in built.items():
        inf = b.info
        rep["tiers"][f"T{t}"] = {
            "triangles": inf["triangles"], "budget": BUDGET[t], "within_budget": inf["triangles"]["total"] <= BUDGET[t],
            "height_studs": inf["height"], "radius_studs": inf["radius"],
            "parts": {r: {k: v for k, v in p.items() if k in ("mesh", "triangles", "vertices", "size")} for r, p in inf["parts"].items()},
            "texture": f"textures/{b.tex} ({BAKE_SIZE}x{BAKE_SIZE}, baked lighting, {BAKE_SAMPLES} samples)"}
        bp = Vector(inf["parts"]["Barrel"]["pivot"])
        spec_out["tiers"][f"T{t}"] = {
            "fbx": f"exports/fbx/HandymanTurret_T{t}.fbx", "glb": f"exports/glb/HandymanTurret_T{t}.glb",
            "texture": b.tex, "icon": f"previews/icon_T{t}.png",
            "parts": inf["parts"], "muzzles": inf["muzzles"],
            "muzzlesFromBarrelPivot": [[round(m[i] - bp[i], 4) for i in range(3)] for m in inf["muzzles"]],
            "muzzleCentre": [round(sum(m[i] for m in inf["muzzles"]) / len(inf["muzzles"]), 4) for i in range(3)],
            "height": inf["height"], "radius": inf["radius"], "triangles": inf["triangles"], "spin": inf["spin"]}
    (ROOT / "polygon-report.json").write_text(json.dumps(rep, indent=2))
    (ROOT / "exports/turret-spec.json").write_text(json.dumps(spec_out, indent=2))
    print("TURRET_READY", json.dumps({f"T{t}": b.info["triangles"]["total"] for t, b in built.items()}), flush=True)
