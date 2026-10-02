"""Egg Merchant NPC: rigid-part Roblox blocky character for Motor6D animation.

    blender --background --python build_merchant.py -- [--preview] [--quick]

    --quick    flat key colours, no bake, no export: shaping renders into --out (default scratch)
    --preview  full bake + the preview renders, but no export
    (none)     full bake, previews, FBX/GLB export, reports, merchant.blend

The painted source atlas (textures/merchant.png) is painted by THIS file run under system
Python (numpy + Pillow): `python build_merchant.py --paint`. The Blender run calls that itself.

Style: ../art-references/ART_DIRECTION_USER_2026-09-17.txt + the chest kit's baked icon
lighting (painted atlas x per-facet key light x soft local AO x height gradient + cool rim +
bright bevel edges), baked onto unique UVs into textures/merchant-baked.png (1024).
Reference: ../art-references/egg-merchant/egg-merchant-concept-v1.png (hooded merchant).
The reference's image-left side is built as the character's LEFT throughout (egg hand,
bedroll, hip pouch, hood patch, tan cuff), so the design is a consistent mirror of the sheet.

Units: studs at final size. Blender Z-up, soles on z=0, facing -Y, character's left = +X.
Studio = (-x, z, y) of Blender. Rigid parts only (no armature); joints are recorded pivots.
Self-contained: helpers adapted from blender-chest-kit/generate_chest.py, nothing imported.
"""
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEX = ROOT / "textures"
ATLAS = 2048            # painted source atlas
BAKE_SIZE = 1024        # Roblox caps textures at 1024
ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]

# ---------------------------------------------------------------------------
# palette: key -> (base, dark, light) sRGB
# ---------------------------------------------------------------------------
PALETTE = {
    "skin": ((228, 156, 94), (204, 128, 74), (244, 184, 124)),
    "face": ((228, 156, 94), (204, 128, 74), (244, 184, 124)),
    "hair": ((116, 66, 34), (82, 44, 22), (156, 98, 54)),
    "coat": ((95, 120, 55), (70, 92, 40), (128, 150, 74)),
    "coat_in": ((66, 84, 37), (50, 65, 29), (84, 104, 47)),
    "shirt": ((240, 230, 206), (208, 194, 164), (252, 247, 232)),
    "trousers": ((102, 66, 46), (76, 48, 34), (132, 90, 62)),
    "glove": ((66, 48, 40), (46, 34, 28), (94, 72, 58)),
    "lace": ((130, 78, 40), (98, 56, 28), (162, 102, 58)),
    "leather": ((150, 88, 50), (112, 62, 34), (186, 120, 72)),
    "boot": ((134, 78, 46), (100, 56, 32), (168, 106, 64)),
    "sole": ((78, 56, 42), (58, 40, 30), (102, 76, 58)),
    "tan": ((220, 184, 126), (182, 142, 90), (240, 212, 158)),
    "olive": ((106, 126, 60), (80, 98, 44), (136, 154, 80)),
    "patch": ((214, 172, 106), (176, 132, 76), (236, 202, 140)),
    "bedroll": ((120, 132, 82), (90, 100, 60), (152, 162, 106)),
    "bedroll_end": ((104, 114, 70), (78, 86, 52), (132, 142, 90)),
    "wood": ((168, 100, 56), (128, 72, 40), (200, 134, 82)),
    "wood_band": ((136, 78, 44), (102, 56, 30), (166, 104, 62)),
    "straw": ((238, 188, 76), (204, 146, 48), (252, 220, 130)),
    "straw_dark": ((210, 156, 58), (174, 120, 40), (232, 186, 90)),
    "egg": ((245, 236, 214), (224, 210, 186), (253, 249, 238)),
    "spot": ((84, 174, 178), (62, 144, 154), (120, 202, 200)),
    "gold": ((240, 188, 62), (192, 130, 30), (255, 230, 126)),
    "iron": ((86, 84, 92), (62, 60, 68), (124, 122, 130)),
    "dark": ((80, 52, 34), (60, 38, 26), (100, 68, 44)),
    "steel": ((156, 156, 164), (116, 116, 124), (196, 196, 204)),
}
KEYS = list(PALETTE)

# Atlas regions on an 8x8 grid (col0, row0, col1, row1; rows count up from v=0),
# with the stud span one region covers (u, v) and a mapping mode.
REGIONS = {
    "face": (0, 6, 2, 8, 0, 0, "face"),
    "skin": (2, 7, 3, 8, 1.4, 1.4, "tile"),
    "hair": (3, 7, 4, 8, 1.2, 1.2, "tile"),
    "coat_in": (4, 7, 5, 8, 2.0, 2.0, "tile"),
    "gold": (5, 7, 6, 8, 0.9, 0.9, "tile"),
    "iron": (6, 7, 7, 8, 0.9, 0.9, "tile"),
    "spot": (7, 7, 8, 8, 0.9, 0.9, "tile"),
    "coat": (2, 5, 4, 7, 3.0, 3.0, "tile"),
    "shirt": (4, 5, 6, 7, 2.6, 2.6, "tile"),
    "trousers": (6, 5, 7, 7, 1.4, 2.8, "tile"),
    "glove": (7, 5, 8, 6, 1.2, 1.2, "tile"),
    "lace": (7, 6, 8, 7, 1.0, 1.0, "tile"),
    "leather": (0, 4, 2, 6, 2.6, 2.6, "tile"),
    "boot": (2, 4, 3, 5, 1.6, 1.6, "tile"),
    "sole": (3, 4, 4, 5, 1.6, 1.6, "tile"),
    "tan": (4, 4, 5, 5, 1.4, 1.4, "tile"),
    "olive": (5, 4, 6, 5, 1.4, 1.4, "tile"),
    "patch": (6, 4, 7, 5, 0, 0, "fit"),
    "bedroll": (7, 4, 8, 5, 1.6, 1.6, "tile"),
    "wood": (0, 0, 1, 4, 1.0, 4.2, "tile"),
    "wood_band": (1, 3, 4, 4, 4.4, 1.47, "tile"),
    "straw": (1, 1, 3, 3, 1.6, 1.6, "tile"),
    "egg": (3, 1, 5, 3, 1.4, 1.4, "tile"),
    "straw_dark": (4, 3, 5, 4, 1.2, 1.2, "tile"),
    "dark": (5, 3, 6, 4, 2.2, 2.2, "tile"),
    "bedroll_end": (6, 3, 7, 4, 1.0, 1.0, "tile"),
    "steel": (7, 3, 8, 4, 0.9, 0.9, "tile"),
}
# The head's flat front maps 1:1 onto the face region (studs).
FX0, FX1, FZ0, FZ1 = -0.72, 0.72, 4.89, 6.15


# ---------------------------------------------------------------------------
# texture painting (system Python: numpy + Pillow)
# ---------------------------------------------------------------------------
def paint_atlas():
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(20261002)
    C = ATLAS // 8

    def smooth_noise(h, w, cy, cx):
        grid = rng.random((cy + 3, cx + 3)).astype(np.float32)
        im = Image.fromarray((grid * 255).astype(np.uint8), "L")
        big = im.resize((int(w * (cx + 3) / cx), int(h * (cy + 3) / cy)), Image.BICUBIC)
        a = np.asarray(big, dtype=np.float32) / 255.0
        oy, ox = (a.shape[0] - h) // 2, (a.shape[1] - w) // 2
        return a[oy:oy + h, ox:ox + w] - 0.5

    def col(c):
        return np.array(c, np.float32) / 255.0

    def tone(key, t):
        """t in about -0.5..0.5: negative toward dark, positive toward light (soft posterised)."""
        base, dark, light = (col(c) for c in PALETTE[key])
        t = np.clip(t, -0.5, 0.5)
        q = np.round(t * 4) / 4                       # 2-4 broad value steps, half blended
        t = t * 0.55 + q * 0.45
        out = np.broadcast_to(base, t.shape + (3,)).copy()
        pos = np.clip(t, 0, None)[..., None] * 2
        neg = np.clip(-t, 0, None)[..., None] * 2
        out = out + (light - out) * pos * 0.8
        out = out + (dark - out) * neg * 0.8
        return out

    def broad(key, h, w, amt=0.55):
        t = smooth_noise(h, w, 4, 4) * amt + smooth_noise(h, w, 9, 9) * amt * 0.35
        return tone(key, t)

    def folds(key, h, w, nf=7, amt=0.75):
        """Cloth: long soft vertical folds + broad patches + a few painted strokes."""
        t = smooth_noise(h, w, 2, nf) * amt + smooth_noise(h, w, 5, 5) * 0.3
        img = tone(key, t)
        light = col(PALETTE[key][2])
        for _ in range(int(w / 40)):
            x = int(rng.uniform(0, w - 8))
            y0 = int(rng.uniform(0, h * 0.5)); y1 = int(min(h, y0 + rng.uniform(h * 0.3, h * 0.7)))
            prof = np.sin(np.linspace(0, np.pi, y1 - y0))[:, None, None] * 0.28
            img[y0:y1, x:x + 6] += (light - img[y0:y1, x:x + 6]) * prof
        return img

    def grain(key, h, w, vertical=True):
        if not vertical:
            return np.transpose(grain(key, w, h, True), (1, 0, 2))
        t = smooth_noise(h, w, 3, int(w / 9)) * 0.55 + smooth_noise(h, w, 6, 4) * 0.35
        img = tone(key, t)
        dark = col(PALETTE[key][1])
        for _ in range(int(w / 10)):
            x = int(rng.uniform(2, w - 4)); y0 = int(rng.uniform(0, h * 0.8))
            ln = int(rng.uniform(h * 0.12, h * 0.35)); y1 = min(h, y0 + ln)
            a = (np.sin(np.linspace(0, np.pi, y1 - y0)) * 0.4)[:, None, None]
            img[y0:y1, x:x + 3] += (dark - img[y0:y1, x:x + 3]) * a
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        for _ in range(max(1, h // 300)):
            cx, cy = rng.uniform(0.2, 0.8) * w, rng.uniform(0.1, 0.9) * h
            d = np.sqrt(((xx - cx) / 10) ** 2 + ((yy - cy) / 22) ** 2)
            img += (dark - img) * (np.clip(1 - d, 0, 1) ** 0.8 * 0.55)[..., None]
        return img

    def wraps(key, h, w):
        """Wrapped cloth: diagonal bands, each lit on top with a dark lower edge."""
        img = broad(key, h, w, 0.35)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        ph = ((yy + xx * 0.35) / 34.0) % 1.0
        dark, light = col(PALETTE[key][1]), col(PALETTE[key][2])
        img += (light - img) * (np.clip(1 - ph / 0.25, 0, 1) * 0.35)[..., None]
        img += (dark - img) * (np.clip((ph - 0.82) / 0.18, 0, 1) * 0.75)[..., None]
        return img

    def streaky(key, h, w):
        t = smooth_noise(h, w, 3, 22) * 0.6 + smooth_noise(h, w, 5, 5) * 0.35
        return tone(key, t)

    def patch(h, w):
        img = broad("patch", h, w, 0.4)
        st = col((86, 52, 30))
        m, L, g, th = 22, 16, 10, 5
        for i in range(m, w - m - L, L + g):          # top / bottom dashes
            img[m:m + th, i:i + L] = st; img[h - m - th:h - m, i:i + L] = st
        for j in range(m, h - m - L, L + g):          # left / right dashes
            img[j:j + L, m:m + th] = st; img[j:j + L, w - m - th:w - m] = st
        return img

    def face(h, w):
        img = broad("face", h, w, 0.25)
        X = FX0 + (np.arange(w, dtype=np.float32) + 0.5) / w * (FX1 - FX0)
        Z = FZ1 - (np.arange(h, dtype=np.float32) + 0.5) / h * (FZ1 - FZ0)
        XX, ZZ = np.meshgrid(X, Z)
        aa = 0.0045

        def seg_d(ax, az, bx, bz):
            px, pz = XX - ax, ZZ - az
            dx, dz = bx - ax, bz - az
            t = np.clip((px * dx + pz * dz) / (dx * dx + dz * dz), 0, 1)
            return np.hypot(px - dx * t, pz - dz * t), t

        def stroke(pts, r0, r1):
            """Tapered thick stroke through points (radius r0 at start, r1 at end)."""
            cov = np.zeros_like(XX)
            n = len(pts) - 1
            for k in range(n):
                d, t = seg_d(*pts[k], *pts[k + 1])
                r = r0 + (r1 - r0) * ((k + t) / n)
                cov = np.maximum(cov, np.clip((r - d) / aa + 0.5, 0, 1))
            return cov

        def bez(p0, p1, p2, n=14):
            return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                     (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in np.linspace(0, 1, n)]

        def ell(cx, cz, rx, rz):
            d = np.sqrt(((XX - cx) / rx) ** 2 + ((ZZ - cz) / rz) ** 2)
            return np.clip((1 - d) * min(rx, rz) / aa + 0.5, 0, 1)

        ink = col((36, 22, 18))
        # soft warm cheeks
        for cx in (-0.33, 0.35):
            d = np.sqrt(((XX - cx) / 0.13) ** 2 + ((ZZ - 5.33) / 0.07) ** 2)
            img += (col((238, 136, 96)) - img) * (np.clip(1 - d, 0, 1) ** 1.5 * 0.28)[..., None]
        # brows: viewer-left low and angled in (determined), viewer-right raised and arched (sly)
        cov = stroke(bez((-0.45, 5.735), (-0.30, 5.745), (-0.10, 5.655)), 0.040, 0.058)
        cov = np.maximum(cov, stroke(bez((0.11, 5.715), (0.27, 5.835), (0.46, 5.765)), 0.058, 0.036))
        # eyes: viewer-left narrowed by a lid line, viewer-right open
        eyeL = ell(-0.265, 5.50, 0.080, 0.100) * np.clip((5.565 + (XX + 0.265) * 0.35 - ZZ) / aa + 0.5, 0, 1)
        eyeR = ell(0.275, 5.515, 0.080, 0.108)
        cov = np.maximum(cov, np.maximum(eyeL, eyeR))
        cov = np.maximum(cov, stroke([(-0.345, 5.565), (-0.19, 5.540)], 0.013, 0.010))   # lid
        # sly closed smirk, curling up at the viewer-right end, with a dimple
        cov = np.maximum(cov, stroke(bez((-0.20, 5.285), (0.02, 5.175), (0.235, 5.315)), 0.020, 0.030))
        cov = np.maximum(cov, stroke(bez((0.265, 5.345), (0.300, 5.300), (0.270, 5.255)), 0.016, 0.012))
        img += (ink - img) * cov[..., None]
        hl = np.maximum(ell(-0.29, 5.525, 0.024, 0.026), ell(0.250, 5.550, 0.026, 0.028))
        hl = np.maximum(hl, ell(0.30, 5.47, 0.012, 0.012))
        img += (col((255, 255, 255)) - img) * hl[..., None]
        return img

    painters = {
        "face": face, "patch": patch,
        "coat": lambda h, w: folds("coat", h, w, 8), "coat_in": lambda h, w: folds("coat_in", h, w, 6),
        "shirt": lambda h, w: folds("shirt", h, w, 7, 0.6), "trousers": lambda h, w: folds("trousers", h, w, 4),
        "bedroll": lambda h, w: folds("bedroll", h, w, 5), "hair": lambda h, w: folds("hair", h, w, 9, 0.9),
        "wood": lambda h, w: grain("wood", h, w, True), "wood_band": lambda h, w: grain("wood_band", h, w, False),
        "tan": lambda h, w: wraps("tan", h, w), "olive": lambda h, w: wraps("olive", h, w),
        "straw": lambda h, w: streaky("straw", h, w), "straw_dark": lambda h, w: streaky("straw_dark", h, w),
        "gold": lambda h, w: broad("gold", h, w, 0.8), "spot": lambda h, w: broad("spot", h, w, 0.3),
        "egg": lambda h, w: broad("egg", h, w, 0.4), "skin": lambda h, w: broad("skin", h, w, 0.25),
    }
    img = np.zeros((ATLAS, ATLAS, 3), np.float32)
    for key, (c0, r0, c1, r1, *_rest) in REGIONS.items():
        x0, x1, y0, y1 = c0 * C, c1 * C, (8 - r1) * C, (8 - r0) * C
        f = painters.get(key, lambda h, w, k=key: broad(k, h, w))
        img[y0:y1, x0:x1] = f(y1 - y0, x1 - x0)
    TEX.mkdir(exist_ok=True)
    out = TEX / "merchant.png"
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB").save(out)
    print("wrote", out)


try:
    import bpy  # noqa: F401
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False

if not IN_BLENDER:
    if "--paint" in ARGV:
        paint_atlas()
    sys.exit(0)

# ===========================================================================
# Blender side
# ===========================================================================
import bmesh  # noqa: E402
from mathutils import Matrix, Vector, Quaternion  # noqa: E402

QUICK = "--quick" in ARGV
PREVIEW = "--preview" in ARGV
OUT = Path(ARGV[ARGV.index("--out") + 1]) if "--out" in ARGV else ROOT / "previews"
SHARP = math.radians(30)
CHAMFER = 0.06
KIDX = {k: i for i, k in enumerate(KEYS)}


def rot(axis, deg, pivot=(0, 0, 0)):
    """4x4 rotation about an axis ('X'/'Y'/'Z' or a vector) through a pivot."""
    p = Vector(pivot)
    R = Matrix.Rotation(math.radians(deg), 4, axis if isinstance(axis, str) else Vector(axis).normalized())
    return Matrix.Translation(p) @ R @ Matrix.Translation(-p)


def newell(pts):
    n = Vector((0, 0, 0))
    for a, b in zip(pts, pts[1:] + pts[:1]):
        n.x += (a.y - b.y) * (a.z + b.z); n.y += (a.z - b.z) * (a.x + b.x); n.z += (a.x - b.x) * (a.y + b.y)
    return n.normalized() if n.length > 1e-9 else Vector((0, 0, 1))


class Piece:
    """One closed solid: welded on creation, normals recalculated, bevelled alone."""

    def __init__(self, chamfer, segs):
        self.verts, self.index, self.faces, self.keys = [], {}, [], []
        self.chamfer, self.segs = chamfer, segs

    def vid(self, p):
        k = (round(p[0], 5), round(p[1], 5), round(p[2], 5))
        if k not in self.index:
            self.index[k] = len(self.verts)
            self.verts.append(Vector(p))
        return self.index[k]


class Part:
    """Collects pieces for one rigid part. Every primitive starts a new piece.
    key is an atlas key or a callable(points, r, j) -> key."""

    def __init__(self, name):
        self.name, self.pieces, self.M = name, [], None

    def begin(self, chamfer=None, segs=1):
        self.pc = Piece(CHAMFER if chamfer is None else chamfer, segs)
        self.pieces.append(self.pc)
        return self.pc

    def poly(self, pts, key, r=0, j=0):
        pts = [Vector(p) for p in pts]
        if self.M is not None:
            pts = [self.M @ p for p in pts]
        ids = []
        for p in pts:
            i = self.pc.vid(p)
            if i not in ids:
                ids.append(i)
        if len(ids) < 3:
            return
        k = key(pts, r, j) if callable(key) else key
        self.pc.faces.append(ids)
        self.pc.keys.append(k)

    def box(self, x0, x1, y0, y1, z0, z1, key, M=None, chamfer=None, segs=1):
        self.begin(chamfer, segs)
        self.M = M
        c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        for ids in ((0, 1, 5, 4), (2, 3, 7, 6), (3, 0, 4, 7), (1, 2, 6, 5), (3, 2, 1, 0), (4, 5, 6, 7)):
            self.poly([c[i] for i in ids], key)
        self.M = None

    def boxc(self, cx, cy, cz, sx, sy, sz, key, **kw):
        self.box(cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, cz - sz / 2, cz + sz / 2, key, **kw)

    def loft(self, rings, key, cap0=True, cap1=True, strip=False, M=None, chamfer=None, segs=1):
        """Skin rings (equal length, closed) into a solid. strip=True closes the ends of
        horseshoe rings (outer path + reversed inner path) with quads instead of n-gons."""
        self.begin(chamfer, segs)
        self.M = M
        n = len(rings[0])
        for r in range(len(rings) - 1):
            a, b = rings[r], rings[r + 1]
            for j in range(n):
                jj = (j + 1) % n
                self.poly([a[j], a[jj], b[jj], b[j]], key, r, j)
        for end, ring in ((cap0, rings[0]), (cap1, rings[-1])):
            if not end:
                continue
            tag = -1 if ring is rings[0] else -2
            if strip:
                m = n // 2
                for j in range(m - 1):
                    self.poly([ring[j], ring[j + 1], ring[n - 2 - j], ring[n - 1 - j]], key, tag, j)
            else:
                self.poly(list(ring), key, tag, 0)
        self.M = None


def rrect(rx, ry, rc, nc=3, cx=0.0, cy=0.0):
    """Rounded rectangle (x, y) points, counter-clockwise seen from +Z."""
    rc = min(rc, rx * 0.999, ry * 0.999)
    pts = []
    for (sx, sy, a0) in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
        ox, oy = cx + sx * (rx - rc), cy + sy * (ry - rc)
        for k in range(nc + 1):
            a = math.radians(a0 + 90 * k / nc)
            pts.append((ox + rc * math.cos(a), oy + rc * math.sin(a)))
    return pts


def ring_z(pts2, z, dz=None):
    return [Vector((x, y, z + (dz[i] if dz else 0))) for i, (x, y) in enumerate(pts2)]


def rrect_path(rx, ry, rc, fracs, cx=0.0, cy=0.0):
    """Points on a rounded rectangle at perimeter fractions, starting at the front centre
    (0, -ry) and running counter-clockwise (toward +X first)."""
    dense = []
    rc = min(rc, rx * 0.999, ry * 0.999)
    dense.append((0.0, -ry))
    corners = ((1, -1, 270), (1, 1, 0), (-1, 1, 90), (-1, -1, 180))
    for sx, sy, a0 in corners:
        ox, oy = sx * (rx - rc), sy * (ry - rc)
        for k in range(17):
            a = math.radians(a0 + 90 * k / 16)
            dense.append((ox + rc * math.cos(a), oy + rc * math.sin(a)))
    dense.append((0.0, -ry))
    cum = [0.0]
    for a, b in zip(dense, dense[1:]):
        cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total = cum[-1]
    out = []
    for f in fracs:
        s = (f % 1.0) * total
        i = max(0, min(len(cum) - 2, next(k for k in range(len(cum) - 1) if cum[k + 1] >= s)))
        t = (s - cum[i]) / max(1e-9, cum[i + 1] - cum[i])
        a, b = dense[i], dense[i + 1]
        out.append((cx + a[0] + (b[0] - a[0]) * t, cy + a[1] + (b[1] - a[1]) * t))
    return out


def circle(r, n, rot0=0.0):
    return [(r * math.cos(rot0 + 2 * math.pi * k / n), r * math.sin(rot0 + 2 * math.pi * k / n)) for k in range(n)]


def frame_to(p0, p1):
    """Matrix taking local Z to the segment p0->p1 (origin at p0)."""
    d = Vector(p1) - Vector(p0)
    q = Vector((0, 0, 1)).rotation_difference(d.normalized())
    return Matrix.Translation(Vector(p0)) @ q.to_matrix().to_4x4(), d.length


def zigzag(n, deep, shallow=0.0, seed=1, jitter=0.35):
    """Chunky tattered hem offsets: alternating deep/shallow with irregular depth."""
    import random
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        base = deep if i % 2 == 0 else shallow
        out.append(base * (1 + rnd.uniform(-jitter, jitter)) if base else rnd.uniform(0, deep * 0.15))
    return out


# ---------------------------------------------------------------------------
# part -> mesh object (bevel per piece with bmesh), atlas UVs from keys
# ---------------------------------------------------------------------------
def bevel_piece(pc):
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in pc.verts]
    for ids, key in zip(pc.faces, pc.keys):
        try:
            f = bm.faces.new([vs[i] for i in ids])
        except ValueError:
            continue
        f.material_index = KIDX[key]
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if pc.chamfer > 0 and len(bm.verts) > 3:
        lo = [min(v.co[i] for v in bm.verts) for i in range(3)]
        hi = [max(v.co[i] for v in bm.verts) for i in range(3)]
        span = min(h - l for h, l in zip(hi, lo))
        width = min(pc.chamfer, 0.3 * span) if span > 1e-3 else pc.chamfer
        edges = [e for e in bm.edges if e.is_manifold and e.calc_face_angle(0) > math.radians(32)]
        if edges and width > 1e-4:
            res = bmesh.ops.bevel(bm, geom=edges, offset=width, offset_type="OFFSET", segments=pc.segs,
                                  profile=0.5, affect="EDGES", clamp_overlap=True)
            new = set(res["faces"])
            for _ in range(3):                      # bevel faces take the key of a neighbouring face
                for f in list(new):
                    near = [g.material_index for e in f.edges for g in e.link_faces if g not in new]
                    if near:
                        f.material_index = max(set(near), key=near.count)
                        new.discard(f)
            bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges)
    bm.verts.index_update()
    verts = [v.co.copy() for v in bm.verts]
    faces = [([v.index for v in f.verts], f.material_index) for f in bm.faces]
    bm.free()
    return verts, faces


MATS = {}


def key_materials():
    for k in KEYS:
        m = bpy.data.materials.new(f"Merchant_Key_{k}")
        m.use_nodes = True
        bs = m.node_tree.nodes.get("Principled BSDF")
        bs.inputs["Base Color"].default_value = (*[srgb_to_linear(c) for c in PALETTE[k][0]], 1)
        bs.inputs["Roughness"].default_value = 0.8
        MATS[k] = m


def srgb_to_linear(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def build_object(part, post=None):
    allv, allf, allk = [], [], []
    for pc in part.pieces:
        if not pc.faces:
            continue
        verts, faces = bevel_piece(pc)
        base = len(allv)
        allv += verts
        for ids, k in faces:
            allf.append([base + i for i in ids])
            allk.append(k)
    mesh = bpy.data.meshes.new(part.name + "_Mesh")
    mesh.from_pydata(allv, [], allf)
    for k in KEYS:
        mesh.materials.append(MATS[k])
    for poly, k in zip(mesh.polygons, allk):
        poly.material_index = k
    mesh.validate()
    if post is not None:
        mesh.transform(post)
    mesh.update()
    obj = bpy.data.objects.new(part.name, mesh)
    COLL.objects.link(obj)
    mesh.shade_smooth()
    mesh.set_sharp_from_angle(angle=SHARP)
    return obj


def region_uv(key, pts, n):
    c0, r0, c1, r1, su, sv, mode = REGIONS[key]
    m = 4 / ATLAS
    u0, v0, u1, v1 = c0 / 8 + m, r0 / 8 + m, c1 / 8 - m, r1 / 8 - m
    if mode == "face":
        return [(u0 + (p.x - FX0) / (FX1 - FX0) * (u1 - u0), v0 + (p.z - FZ0) / (FZ1 - FZ0) * (v1 - v0)) for p in pts]
    ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
    if az >= max(ax, ay):
        ab = [(p.x, p.y if n.z > 0 else -p.y) for p in pts]
    elif ax >= ay:
        ab = [(p.y if n.x > 0 else -p.y, p.z) for p in pts]
    else:
        ab = [(-p.x if n.y > 0 else p.x, p.z) for p in pts]
    out = [[0.0, 0.0] for _ in pts]
    for axis, span in ((0, su), (1, sv)):
        vals = [q[axis] for q in ab]
        lo, hi = min(vals), max(vals)
        if mode == "fit":
            t = [(v - lo) / (hi - lo) if hi - lo > 1e-6 else 0.5 for v in vals]
        else:
            if hi - lo > span:
                t = [(v - lo) / (hi - lo) for v in vals]
            else:
                shift = math.floor(((lo + hi) / 2) / span) * span
                a = [v - shift for v in vals]
                if min(a) < 0:
                    a = [v - min(a) for v in a]
                if max(a) > span:
                    a = [v - (max(a) - span) for v in a]
                t = [v / span for v in a]
        for i, tv in enumerate(t):
            out[i][axis] = tv
    return [(u0 + a * (u1 - u0), v0 + b * (v1 - v0)) for a, b in out]


def assign_atlas_uvs(obj):
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        key = KEYS[poly.material_index]
        pts = [me.vertices[me.loops[li].vertex_index].co for li in poly.loop_indices]
        for li, u in zip(poly.loop_indices, region_uv(key, pts, poly.normal)):
            uv.data[li].uv = u


# ===========================================================================
# the character (studs; Blender Z-up, facing -Y, character's left = +X)
# ===========================================================================
NECK = Vector((0, 0, 4.85))
WAIST = Vector((0, 0, 2.95))
PACK = Vector((0, 0.62, 4.2))
SPLAY = 8.0                         # arms hang 8 degrees outward
BEND = {1: 22.0, -1: 12.0}          # elbow bend at rest (left holds the egg forward)
EGG_LOCAL = Vector((1.8, -0.80, 2.80))


def shoulder(side):
    return Vector((1.8 * side, 0, 4.28))


def elbow_rest(side):
    return Vector((1.8 * side, 0, 3.62))


def hip(side):
    return Vector((0.6 * side, 0, 2.3))


def M_upper(side):
    return rot("Y", -SPLAY * side, shoulder(side))


def M_lower(side):
    return M_upper(side) @ rot("X", -BEND[side], elbow_rest(side))


def gold_buckle(P, cx, cz, yf, w, h, t=0.075, d=0.07, M=None):
    """Bevelled buckle frame facing -Y at depth yf (front) with a centre pin."""
    W = M
    P.box(cx - w / 2, cx + w / 2, yf, yf + d, cz + h / 2 - t, cz + h / 2, "gold", M=W, chamfer=0.022)
    P.box(cx - w / 2, cx + w / 2, yf, yf + d, cz - h / 2, cz - h / 2 + t, "gold", M=W, chamfer=0.022)
    P.box(cx - w / 2, cx - w / 2 + t, yf, yf + d, cz - h / 2 + t * 0.5, cz + h / 2 - t * 0.5, "gold", M=W, chamfer=0.022)
    P.box(cx + w / 2 - t, cx + w / 2, yf, yf + d, cz - h / 2 + t * 0.5, cz + h / 2 - t * 0.5, "gold", M=W, chamfer=0.022)
    P.box(cx - 0.022, cx + 0.022, yf + d * 0.15, yf + d, cz - h / 2 + t * 0.6, cz + h / 2 - t * 0.6, "gold", M=W, chamfer=0.012)


def pouch(P, x0, x1, y0, y1, z0, z1, face, clasp_key="gold"):
    """Leather pouch with an overhanging flap and a gold clasp. face: '-y', '+x' or '-x'."""
    P.box(x0, x1, y0, y1, z0, z1, "leather", chamfer=0.07)
    fz0 = z0 + (z1 - z0) * 0.55
    if face == "-y":
        P.box(x0 - 0.03, x1 + 0.03, y0 - 0.05, y1 - 0.02, fz0, z1 + 0.05, "leather", chamfer=0.05)
        P.boxc((x0 + x1) / 2, y0 - 0.07, fz0 + 0.04, 0.15, 0.06, 0.17, clasp_key, chamfer=0.02)
    else:
        sx = 1 if face == "+x" else -1
        xo = x1 if sx > 0 else x0
        P.box(min(xo + 0.05 * sx, xo - 0.3 * sx), max(xo + 0.05 * sx, xo - 0.3 * sx), y0 - 0.03, y1 + 0.03, fz0, z1 + 0.05, "leather", chamfer=0.05)
        P.boxc(xo + 0.07 * sx, (y0 + y1) / 2, fz0 + 0.04, 0.06, 0.15, 0.17, clasp_key, chamfer=0.02)


def arch(W, zb, zs, zt, K=10, p=2.4):
    pts = [(-W, zb)]
    for k in range(K + 1):
        x = -W * math.cos(math.pi * k / K)
        u = min(1.0, abs(x) / W)
        pts.append((x, zs + (zt - zs) * max(0.0, 1 - u ** p) ** (1 / p)))
    pts.append((W, zb))
    return pts


def build_head():
    P = Part("Merchant_Head")
    lv = [(4.90, 0.60, 0.52, 0.26), (4.96, 0.68, 0.60, 0.21), (5.06, 0.70, 0.62, 0.20),
          (5.98, 0.70, 0.62, 0.20), (6.08, 0.67, 0.59, 0.22), (6.13, 0.58, 0.50, 0.24)]

    def face_key(pts, r, j):
        c = sum(pts, Vector()) / len(pts)
        return "face" if abs(newell(pts).y) > 0.8 and c.y < -0.4 else "skin"
    P.loft([ring_z(rrect(rx, ry, rc), z) for z, rx, ry, rc in lv], face_key, chamfer=0)
    P.loft([ring_z(rrect(0.36, 0.32, 0.12), z) for z in (4.60, 4.98)], "skin", chamfer=0)
    # chunky fringe under the hood rim, zigzag tips
    out = [(0.70, 6.17), (0.70, 5.90), (0.52, 5.80), (0.38, 5.93), (0.18, 5.82), (0.02, 5.95),
           (-0.16, 5.83), (-0.34, 5.94), (-0.52, 5.82), (-0.70, 5.92), (-0.70, 6.17)]
    P.loft([[Vector((x, y, z)) for x, z in out] for y in (-0.69, -0.40)], "hair", chamfer=0.03)
    for sx in (1, -1):
        P.boxc(0.64 * sx, -0.42, 5.90, 0.16, 0.34, 0.40, "hair", chamfer=0.04)
    # hood: arch cross-sections lofted front (-Y) to back, a thick shell open at the face
    secs = [  # y, outer W, inner W, leg bottom, outer (zs, zt, p), inner (zs, zt, p)
        (-0.80, 0.88, 0.73, 4.80, (5.62, 6.24, 2.2), (5.60, 6.04, 2.2)),
        (-0.55, 0.94, 0.77, 4.79, (5.78, 6.36, 2.4), (5.78, 6.22, 2.6)),
        (-0.05, 0.96, 0.79, 4.78, (5.80, 6.38, 2.4), (5.80, 6.25, 2.6)),
        (0.45, 0.94, 0.77, 4.78, (5.74, 6.32, 2.4), (5.74, 6.20, 2.6)),
        (0.78, 0.84, 0.52, 4.80, (5.55, 6.16, 2.2), (5.45, 5.86, 2.2)),
        (0.95, 0.64, 0.12, 4.86, (5.35, 5.90, 2.0), (5.30, 5.45, 2.0)),
    ]
    rings = []
    for y, wo, wi, zb, (zso, zto, po), (zsi, zti, pi) in secs:
        o = arch(wo, zb, zso, zto, 10, po)
        i = arch(wi, zb, zsi, zti, 10, pi)
        rings.append([Vector((x, y, z)) for x, z in o + i[::-1]])
    m = len(rings[0]) // 2

    def hood_key(pts, r, j):
        if r < 0:
            return "coat"
        return "coat_in" if m <= j <= 2 * m - 2 else "coat"
    P.loft(rings, hood_key, strip=True, chamfer=0.035)
    # pointed tip falling back
    path = [(0, 0.36, 6.02, 0.34), (0, 0.66, 6.18, 0.26), (0, 0.86, 6.16, 0.17), (0, 0.95, 5.95, 0.0)]
    trings = []
    for k, (x, y, z, r) in enumerate(path):
        a = Vector(path[max(0, k - 1)][:3])
        b = Vector(path[min(len(path) - 1, k + 1)][:3])
        t = (b - a).normalized()
        side = Vector((1, 0, 0))
        up = t.cross(side).normalized()
        c = Vector((x, y, z))
        trings.append([c + side * r * math.cos(2 * math.pi * q / 6 + 0.3) + up * r * 0.72 * math.sin(2 * math.pi * q / 6 + 0.3) for q in range(6)])
    P.loft(trings, "coat", cap1=False, chamfer=0.03)
    # stitched tan patch on the left side of the hood
    P.boxc(0.945, -0.12, 5.34, 0.075, 0.52, 0.44, "patch", M=rot("X", 10, (0.945, -0.12, 5.34)), chamfer=0.022)
    return P


def build_torso():
    P = Part("Merchant_Torso")
    lv = [(2.86, 1.15, 0.55, 0.14), (2.92, 1.20, 0.60, 0.16), (4.74, 1.20, 0.60, 0.16), (4.84, 1.12, 0.52, 0.14)]
    P.loft([ring_z(rrect(rx, ry, rc), z) for z, rx, ry, rc in lv], "coat", chamfer=0)
    # cream shirt in the V opening of the coat, green lapels over its edges
    v = [(-0.30, 2.90), (0.30, 2.90), (0.46, 4.80), (-0.46, 4.80)]
    P.loft([[Vector((x, y, z)) for x, z in v] for y in (-0.665, -0.55)], "shirt", chamfer=0.03)
    for sx in (1, -1):
        lap = [(0.26 * sx, 2.90), (0.52 * sx, 2.90), (0.70 * sx, 4.82), (0.42 * sx, 4.82)]
        P.loft([[Vector((x, y, z)) for x, z in lap] for y in (-0.715, -0.56)], "coat", chamfer=0.04)
    # collar slit + criss-cross laces
    P.box(-0.025, 0.025, -0.69, -0.64, 3.92, 4.62, "dark", chamfer=0.01)
    for zc in (4.04, 4.32):
        for a in (38, -38):
            P.boxc(0, -0.69, zc, 0.36, 0.05, 0.06, "lace", M=rot("Y", a, (0, -0.69, zc)), chamfer=0.018)
    P.boxc(-0.07, -0.71, 3.86, 0.05, 0.04, 0.22, "lace", M=rot("Y", -12, (-0.07, -0.71, 3.86)), chamfer=0.015)
    P.boxc(0.07, -0.71, 3.84, 0.05, 0.04, 0.26, "lace", M=rot("Y", 15, (0.07, -0.71, 3.84)), chamfer=0.015)
    # backpack shoulder straps: front, over the shoulder, down the back; gold buckles
    for sx in (1, -1):
        x0, x1 = sorted((0.58 * sx, 0.88 * sx))
        P.box(x0, x1, -0.80, -0.62, 2.95, 4.86, "leather", chamfer=0.04)
        P.box(x0, x1, -0.80, 0.78, 4.70, 4.86, "leather", chamfer=0.04)
        P.box(x0, x1, 0.58, 1.08, 3.80, 4.86, "leather", chamfer=0.04)
        gold_buckle(P, 0.73 * sx, 3.95, -0.88, 0.42, 0.36)
    # chunky cowl draped round the neck with a tattered zigzag hem
    n = len(rrect(1, 1, 0.3, 6))
    zz = zigzag(n, 0.20, 0.0, seed=7)
    # collar sits below the head (top 4.90 = chin line), so the whole face block stays clear
    cow = [ring_z(rrect(0.38, 0.34, 0.15, 6), 4.90), ring_z(rrect(1.00, 0.82, 0.35, 6), 4.90),
           ring_z(rrect(1.14, 0.90, 0.38, 6), 4.76), ring_z(rrect(1.22, 0.96, 0.40, 6), 4.50, [-d for d in zz]),
           ring_z(rrect(0.95, 0.70, 0.30, 6), 4.44)]
    P.loft(cow, "coat", chamfer=0)
    return P


def build_hips():
    P = Part("Merchant_Hips")
    lv = [(2.22, 1.10, 0.52, 0.14), (2.30, 1.16, 0.58, 0.16), (3.02, 1.16, 0.58, 0.16)]
    P.loft([ring_z(rrect(rx, ry, rc), z) for z, rx, ry, rc in lv], "trousers", chamfer=0)
    P.loft([ring_z(rrect(1.28, 0.70, 0.30), z) for z in (2.74, 3.10)], "leather", chamfer=0.04)
    P.box(-0.42, 0.42, -0.66, -0.56, 2.32, 2.80, "shirt", chamfer=0.03)
    gold_buckle(P, 0.0, 2.92, -0.84, 0.66, 0.54, t=0.12, d=0.12)
    P.box(0.30, 0.56, -0.76, -0.69, 2.80, 3.04, "leather", chamfer=0.025)
    # long coat skirt: open-front horseshoe shell with a chunky tattered hem
    M_ = 34
    t = 0.11
    lv = [(3.00, 1.24, 0.66, 0.30, 0.28), (2.62, 1.30, 0.72, 0.32, 0.30), (2.05, 1.40, 0.82, 0.36, 0.36), (1.62, 1.48, 0.90, 0.38, 0.44)]
    zz = zigzag(M_, 0.26, 0.0, seed=3)
    zz[0] = zz[-1] = 0.0
    rings = []
    for k, (z, rx, ry, rc, gx) in enumerate(lv):
        L = 4 * (rx + ry) - (8 - 2 * math.pi) * rc
        a = gx / L
        fr = [a + (1 - 2 * a) * q / (M_ - 1) for q in range(M_)]
        o = rrect_path(rx, ry, rc, fr)
        i = rrect_path(rx - t, ry - t, max(0.05, rc - t), fr)
        dz = zz if k == len(lv) - 1 else [0.0] * M_
        rings.append([Vector((x, y, z - dz[q])) for q, (x, y) in enumerate(o)] +
                     [Vector((x, y, z - dz[M_ - 1 - q])) for q, (x, y) in enumerate(i[::-1])])

    def skirt_key(pts, r, j):
        return "coat_in" if r >= 0 and M_ <= j <= 2 * M_ - 2 else "coat"
    P.loft(rings, skirt_key, strip=True, chamfer=0.03)
    pouch(P, 0.66, 1.20, -1.00, -0.70, 2.12, 2.74, "-y")
    P.box(0.82, 1.04, -0.78, -0.70, 2.66, 3.12, "leather", chamfer=0.025)
    pouch(P, -1.50, -1.22, -0.30, 0.30, 2.20, 2.70, "-x")
    return P


def build_upper_arm(side):
    P = Part("Merchant_UpperArm_" + ("L" if side > 0 else "R"))
    cx = 1.8 * side
    lv = [(3.50, 0.50, 0.20), (3.58, 0.57, 0.22), (4.30, 0.58, 0.22), (4.55, 0.54, 0.24), (4.75, 0.42, 0.20), (4.86, 0.22, 0.10)]
    P.loft([ring_z(rrect(r, r, rc, 3, cx), z) for z, r, rc in lv], "shirt", chamfer=0)
    # green coat shoulder cap, a ball around the shoulder pivot, tattered hem
    n = len(rrect(1, 1, 0.3, 5))
    zz = zigzag(n, 0.20, 0.0, seed=11 if side > 0 else 12)
    cap = [ring_z(rrect(0.40, 0.40, 0.18, 5, cx), 4.08), ring_z(rrect(0.64, 0.64, 0.28, 5, cx), 3.98, [-d for d in zz]),
           ring_z(rrect(0.655, 0.655, 0.30, 5, cx), 4.32), ring_z(rrect(0.60, 0.60, 0.30, 5, cx), 4.62),
           ring_z(rrect(0.45, 0.45, 0.26, 5, cx), 4.83), ring_z(rrect(0.21, 0.21, 0.10, 5, cx), 4.93)]
    P.loft(cap, "coat", chamfer=0)
    return P, M_upper(side)


def build_lower_arm(side):
    P = Part("Merchant_LowerArm_" + ("L" if side > 0 else "R"))
    cx = 1.8 * side
    inward = -side
    lv = [(3.30, 0.52, 0.20), (3.62, 0.53, 0.20), (3.80, 0.47, 0.20), (3.95, 0.33, 0.15), (4.02, 0.14, 0.06)]
    P.loft([ring_z(rrect(r, r, rc, 3, cx), z) for z, r, rc in lv], "shirt", chamfer=0)
    # leather bracer with rolled lips and a dark strap
    P.loft([ring_z(rrect(0.59, 0.59, 0.22, 3, cx), z) for z in (2.92, 3.40)], "leather", chamfer=0.05)
    P.loft([ring_z(rrect(0.635, 0.635, 0.24, 3, cx), z) for z in (3.33, 3.47)], "leather", chamfer=0.045)
    P.loft([ring_z(rrect(0.612, 0.612, 0.23, 3, cx), z) for z in (3.10, 3.21)], "lace", chamfer=0.03)
    # fingerless glove
    P.loft([ring_z(rrect(0.54, 0.50, 0.18, 3, cx), z) for z in (2.58, 2.94)], "glove", chamfer=0.05)
    if side < 0:
        # relaxed open hand, palm toward the body: four finger blocks front to back + thumb
        for k, zb in enumerate((2.30, 2.25, 2.27, 2.33)):
            y0 = -0.45 + k * 0.235
            P.box(cx - 0.40, cx + 0.40, y0, y0 + 0.20, zb, 2.64, "skin", chamfer=0.05)
        P.boxc(cx + inward * 0.18, -0.60, 2.68, 0.34, 0.24, 0.34, "skin", M=rot("X", 12, (cx, -0.6, 2.68)), chamfer=0.06)
    else:
        # palm forward, fingers curled under the egg, thumb along its side
        for k in range(4):
            x0 = cx - 0.45 + k * 0.235
            P.box(x0, x0 + 0.20, -0.46, -0.12, 2.40, 2.64, "skin", chamfer=0.05)
            P.box(x0, x0 + 0.20, -1.00 + 0.03 * (k % 2), -0.36, 2.30, 2.50, "skin", chamfer=0.05)
            P.box(x0, x0 + 0.20, -1.08 + 0.03 * (k % 2), -0.88, 2.38, 2.64 - 0.03 * k, "skin", chamfer=0.05)
        P.boxc(cx + side * 0.36, -0.70, 2.92, 0.22, 0.52, 0.24, "skin", M=rot("X", -10, (cx + side * 0.36, -0.7, 2.92)), chamfer=0.06)
    return P, M_lower(side)


def build_leg(side):
    P = Part("Merchant_Leg_" + ("L" if side > 0 else "R"))
    cx = 0.6 * side
    lv = [(0.80, 0.53, 0.18), (2.30, 0.55, 0.18), (2.55, 0.50, 0.20), (2.74, 0.36, 0.18), (2.84, 0.18, 0.10)]
    P.loft([ring_z(rrect(r, r, rc, 3, cx), z) for z, r, rc in lv], "trousers", chamfer=0)
    boot = [(0.14, 0.60, 0.70, 0.26, -0.10), (0.62, 0.60, 0.70, 0.26, -0.10), (0.80, 0.57, 0.60, 0.24, -0.02), (0.98, 0.56, 0.58, 0.22, 0.0)]
    P.loft([ring_z(rrect(rx, ry, rc, 3, cx, cy), z) for z, rx, ry, rc, cy in boot], "boot", chamfer=0.04)
    P.loft([ring_z(rrect(rx, ry, rc, 3, cx, -0.10), z) for z, rx, ry, rc in ((0.0, 0.62, 0.73, 0.26), (0.17, 0.64, 0.75, 0.27))], "sole", chamfer=0.03)
    key = "tan" if side > 0 else "olive"
    top = 1.40 if side > 0 else 1.30
    P.loft([ring_z(rrect(0.64, 0.64, 0.24, 3, cx), z) for z in (0.86, 1.16)], key, chamfer=0.045)
    P.loft([ring_z(rrect(0.62, 0.62, 0.24, 3, cx), z) for z in (1.10, top)], key, chamfer=0.045,
           M=rot("Z", 6 * side, (cx, 0, 1.2)))
    return P, None


def egg(P, center, height, M=None, seed=1, segs=12):
    """Faceted spotted egg: alternating ring offsets give irregular facets; spots are
    clusters of facets (polygonal teal patches like the reference)."""
    import random
    rnd = random.Random(seed)
    R = height * 0.37
    ts = [0.0, 0.08, 0.19, 0.33, 0.48, 0.63, 0.77, 0.90, 1.0]
    spots = []
    for _ in range(7):
        z = rnd.uniform(-0.75, 0.85)
        a = rnd.uniform(0, 2 * math.pi)
        spots.append((Vector((math.sqrt(1 - z * z) * math.cos(a), math.sqrt(1 - z * z) * math.sin(a), z)), rnd.uniform(0.30, 0.44)))
    rings = []
    for i, t in enumerate(ts):
        z = -height / 2 + height * t
        r = R * math.sqrt(max(0.0, 1 - (2 * t - 1) ** 2)) * (1 + 0.13 * (1 - 2 * t))
        off = (math.pi / segs) * (i % 2)
        ring = []
        for k in range(segs):
            a = off + 2 * math.pi * k / segs
            rr = r * (1 + rnd.uniform(-0.04, 0.04)) if 0 < i < len(ts) - 1 else 0.0
            ring.append(Vector((rr * math.cos(a), rr * math.sin(a), z)))
        rings.append(ring)
    W = Matrix.Translation(Vector(center)) @ (M if M is not None else Matrix.Identity(4))
    P.begin(chamfer=0)
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for k in range(segs):
            kk = (k + 1) % segs
            quad = [a[k], a[kk], b[kk], b[k]]
            c = sum(quad, Vector()) / 4
            d = Vector((c.x / R, c.y / R, c.z / (height / 2))).normalized()
            key = "spot" if any(d.angle(s) < rad for s, rad in spots) else "egg"
            P.poly([W @ q for q in quad], key)


def build_hand_egg():
    P = Part("Merchant_HandEgg")
    egg(P, EGG_LOCAL, 0.90, rot("Y", 8), seed=5, segs=12)
    return P, M_lower(1)


def bolt(P, p, n, r=0.08):
    """Hex bolt head on a surface at p with outward normal n."""
    F, _ = frame_to(Vector(p), Vector(p) + Vector(n))
    rings = [[F @ Vector((x, y, h)) for x, y in circle(rr, 6, 0.5)] for rr, h in ((r, -0.02), (r, 0.035), (r * 0.6, 0.065))]
    P.loft(rings, "iron", chamfer=0)


def build_pack():
    """Merchant crate-basket: square-ish crate of horizontal slats with gaps, chunky corner
    posts, two iron bands with steel bolts, two vertical leather shoulder straps with gold
    buckles on the back, heaped straw holding six spotted eggs, bedroll and lower pouches."""
    import random
    rnd = random.Random(42)
    P = Part("Merchant_Pack")
    HW, HD, Z0, Z1 = 1.20, 0.70, 3.75, 6.68          # rim ~0.3 above the hood top
    YF = 1.04                                        # front face clears the hood back
    CY = YF + HD
    YB = CY + HD
    P.box(-0.75, 0.75, 0.58, YF + 0.04, 3.62, 4.75, "leather", chamfer=0.07)    # back pad against the torso
    P.box(-(HW - 0.12), HW - 0.12, YF + 0.12, YB - 0.12, Z0 + 0.05, Z1 - 0.10, "dark", chamfer=0.04)
    P.box(-(HW - 0.02), HW - 0.02, YF, YF + 0.14, Z0, Z1 - 0.05, "wood", chamfer=0.05)
    n, gap = 7, 0.06
    sh = (Z1 - Z0 - (n - 1) * gap) / n
    for i in range(n):                                                           # horizontal slats
        z0 = Z0 + i * (sh + gap)
        j = rnd.uniform(-0.02, 0.02)
        P.box(-(HW - 0.10), HW - 0.10, YB - 0.13, YB, z0 + j, z0 + sh + j, "wood", chamfer=0.05)
        for sx in (1, -1):
            xa, xb = sorted(((HW - 0.13) * sx, HW * sx))
            P.box(xa, xb, YF + 0.10, YB - 0.10, z0 - j, z0 + sh - j, "wood", chamfer=0.05)
    for sx in (1, -1):                                                           # chunky corner posts
        for yc in (YF + 0.06, YB - 0.06):
            P.boxc((HW - 0.02) * sx, yc, (Z0 + Z1) / 2 + 0.03, 0.28, 0.28, Z1 - Z0 + 0.16, "wood_band", chamfer=0.06)
    bands = (Z0 + 0.42, Z1 - 0.78)
    for zb in bands:                                                             # two iron bands, steel bolts
        P.loft([ring_z(rrect(HW + 0.05, HD + 0.05, 0.10, 3, 0, CY), z) for z in (zb, zb + 0.22)], "iron", chamfer=0.035)
        zc = zb + 0.11
        for x in (-0.95, 0.0, 0.95):
            bolt(P, (x, YB + 0.05, zc), (0, 1, 0), r=0.075)
        for sx in (1, -1):
            for y in (CY - 0.36, CY + 0.36):
                bolt(P, ((HW + 0.05) * sx, y, zc), (sx, 0, 0), r=0.075)
    for sx in (1, -1):                                                           # vertical shoulder straps
        xa, xb = sorted((0.42 * sx, 0.70 * sx))
        P.box(xa, xb, YB + 0.0, YB + 0.12, Z0 - 0.06, Z1 + 0.04, "leather", chamfer=0.035)
        P.box(xa, xb, YB - 0.30, YB + 0.12, Z1 - 0.04, Z1 + 0.10, "leather", chamfer=0.035)
        gold_buckle(P, 0.56 * sx, (Z0 + Z1) / 2 + 0.12, -(YB + 0.19), 0.36, 0.32, M=Matrix.Diagonal((1, -1, 1, 1)))
    pouch(P, -(HW + 0.34), -(HW - 0.02), CY - 0.36, CY + 0.34, Z0 + 0.15, Z0 + 0.95, "-x")
    pouch(P, HW - 0.02, HW + 0.32, CY - 0.32, CY + 0.30, Z0 + 0.18, Z0 + 0.88, "+x")
    # heaped straw: a mound plus chunky pointed petal clumps
    RX, RY = HW - 0.08, HD - 0.06
    P.loft([ring_z(rrect(rx, ry, rc, 3, 0, CY), z) for z, rx, ry, rc in
            ((Z1 - 0.30, RX, RY, 0.30), (Z1 + 0.08, RX * 0.97, RY * 0.95, 0.30), (Z1 + 0.24, RX * 0.74, RY * 0.7, 0.28),
             (Z1 + 0.32, RX * 0.3, RY * 0.28, 0.12))], "straw_dark", chamfer=0)

    def petal(base, d, length, wid, thick, tang):
        d = Vector(d).normalized()
        tang = (Vector(tang) - d * Vector(tang).dot(d)).normalized()
        nrm = d.cross(tang).normalized()
        rings = []
        for t, wf in ((0.0, 0.45), (0.35, 1.0), (0.70, 0.72), (1.0, 0.0)):
            c = Vector(base) + d * length * t
            rings.append([c + tang * wid * wf * 0.5, c + nrm * thick * wf * 0.5, c - tang * wid * wf * 0.5, c - nrm * thick * wf * 0.5])
        P.loft(rings, "straw", cap1=False, chamfer=0)

    for k in range(30):
        f = (k + rnd.uniform(-0.2, 0.2)) / 30
        (bx, by), = rrect_path(RX, RY, 0.30, [f], 0, CY)
        out = Vector((bx / RX ** 2, (by - CY) / RY ** 2, 0)).normalized()
        el = math.radians(rnd.uniform(30, 60))
        d = out * math.cos(el) + Vector((0, 0, math.sin(el)))
        petal((bx * 0.93, CY + (by - CY) * 0.92, Z1 - 0.06), d, rnd.uniform(0.44, 0.64), rnd.uniform(0.27, 0.35), 0.10, Vector((-out.y, out.x, 0)))
    for k in range(16):
        a = rnd.uniform(0, 2 * math.pi)
        rr = rnd.uniform(0.25, 0.9)
        b = Vector((math.cos(a) * rr * RX * 0.9, CY + math.sin(a) * rr * RY * 0.85, Z1 + 0.14))
        tilt = Vector((math.cos(a), math.sin(a), 0)) * rnd.uniform(0.3, 0.8)
        petal(b, tilt + Vector((0, 0, 1)), rnd.uniform(0.34, 0.48), rnd.uniform(0.24, 0.32), 0.09, Vector((-math.sin(a), math.cos(a), 0)))
    # six spotted eggs bulging above the rim: a lower row toward his back, a higher row behind
    eggs = ((-0.76, CY - 0.30, Z1 + 0.14, 1.00, (1, 0.3, 0), 15, 21), (0.02, CY - 0.32, Z1 + 0.18, 1.04, (1, 0, 0), -9, 22),
            (0.78, CY - 0.28, Z1 + 0.14, 0.98, (1, -0.2, 0), -14, 23), (-0.70, CY + 0.30, Z1 + 0.28, 1.04, (0.3, 1, 0), -16, 24),
            (0.06, CY + 0.32, Z1 + 0.32, 1.08, (1, 0.2, 0), 10, 25), (0.80, CY + 0.30, Z1 + 0.26, 1.02, (0.2, 1, 0), 15, 26))
    for (x, y, z, h, ax, ang, sd) in eggs:
        egg(P, (x, y, z), h, rot(ax, ang), seed=sd)
    # olive bedroll strapped on the left side, spiral ends front and back
    R = 0.45
    BZ = 5.55
    BX = HW + 0.12 + R - 0.08
    y0, y1 = YF - 0.04, YB + 0.04
    roll = [[Vector((BX + x, y, BZ + z)) for x, z in circle(r, 14)] for y, r in ((y0, 0.40), (y0 + 0.04, R), (y1 - 0.04, R), (y1, 0.40))]

    def roll_key(pts, r, j):
        return "bedroll_end" if r < 0 else "bedroll"
    P.loft(roll, roll_key, chamfer=0)
    for yc, out in ((y0 - 0.005, -1), (y1 + 0.005, 1)):
        rings = []
        for q in range(40):
            th = 2 * math.pi * 2.2 * q / 39
            r = 0.05 + 0.31 * q / 39
            rad = Vector((math.cos(th), 0, math.sin(th)))
            p = Vector((BX, yc, BZ)) + rad * r
            o = Vector((0, out, 0))
            rings.append([p + rad * 0.035 - o * 0.01, p - rad * 0.035 - o * 0.01, p - rad * 0.035 + o * 0.045, p + rad * 0.035 + o * 0.045])
        P.loft(rings, "bedroll", chamfer=0)
    for yc in (y0 + 0.30, y1 - 0.30):
        P.loft([[Vector((BX + x, y, BZ + z)) for x, z in circle(R + 0.04, 14)] for y in (yc - 0.07, yc + 0.07)], "leather", chamfer=0.03)
        P.box(HW - 0.05, BX - 0.2, yc - 0.07, yc + 0.07, BZ - 0.05, BZ + 0.05, "leather", chamfer=0.02)   # strap to the crate
    return P, None


# ===========================================================================
# bake (adapted from blender-chest-kit/generate_chest.py), renders, export
# ===========================================================================
BAKE = {
    "key_dir": (-0.45, -0.6, 0.75), "key_lo": 0.66, "key_hi": 1.16,
    "ao_distance": 0.35, "ao_lo": 0.62,          # local AO only: parts rotate, so no cross-part shadows
    "height_lo": 0.86, "height_hi": 1.05,
    "rim_dir": (0.75, 0.55, 0.15), "rim": 0.14, "rim_color": (0.45, 0.62, 1.0),
    "edge": 0.50, "edge_radius": 0.05, "edge_tint": (1.0, 0.93, 0.8), "edge_tint_mix": 0.55,
}
FACE_BOOST = 5.0     # the painted face gets this much more texel density than the rest


def select_only(objs, active=None):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def bake(objs, top, keys):
    P = BAKE
    for o in objs:
        uv = o.data.uv_layers.new(name="BakeUV")
        o.data.uv_layers.active = uv
    select_only(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(62), island_margin=0.006, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    # give the painted face a big island of its own: planar x/z, FACE_BOOST x the average density
    a3 = auv = 0.0
    for o in objs:
        me = o.data
        uv = me.uv_layers["BakeUV"].data
        for p in me.polygons:
            if keys[o.name][p.index] == KIDX["face"]:
                continue
            a3 += p.area
            u = [uv[li].uv for li in p.loop_indices]
            auv += abs(sum(u[k].x * u[(k + 1) % len(u)].y - u[(k + 1) % len(u)].x * u[k].y for k in range(len(u)))) / 2
    s = math.sqrt(auv / a3) * FACE_BOOST
    head = next(o for o in objs if o.name == "Merchant_Head")
    me = head.data
    uv = me.uv_layers["BakeUV"].data
    for p in me.polygons:
        if keys[head.name][p.index] == KIDX["face"]:
            for li in p.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                uv[li].uv = ((co.x - FX0) * s, (co.z - FZ0) * s)
    select_only(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, margin=0.006)
    bpy.ops.object.mode_set(mode="OBJECT")

    mat = bpy.data.materials.new("MerchantAtlas")
    mat.use_nodes = True
    for o in objs:
        o.data.materials.clear()
        o.data.materials.append(mat)
        for p in o.data.polygons:
            p.material_index = 0
    nt = mat.node_tree
    nt.nodes.clear()
    N = nt.nodes.new
    L = nt.links.new
    uvsrc = N("ShaderNodeUVMap"); uvsrc.uv_map = "UVMap"
    tex = N("ShaderNodeTexImage"); tex.image = bpy.data.images.load(str(TEX / "merchant.png")); tex.interpolation = "Linear"
    L(uvsrc.outputs["UV"], tex.inputs["Vector"])
    geo = N("ShaderNodeNewGeometry")

    def dot_light(direction):
        d = N("ShaderNodeVectorMath"); d.operation = "DOT_PRODUCT"
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
    ao = N("ShaderNodeAmbientOcclusion"); ao.samples = 16; ao.only_local = True
    ao.inputs["Distance"].default_value = P["ao_distance"]
    aof = remap(ao.outputs["AO"], 0.15, 1.0, P["ao_lo"], 1.0)
    sep = N("ShaderNodeSeparateXYZ"); L(geo.outputs["Position"], sep.inputs["Vector"])
    height = remap(sep.outputs["Z"], 0.0, max(top, 1.0), P["height_lo"], P["height_hi"])
    shade = N("ShaderNodeMath"); shade.operation = "MULTIPLY"; L(key, shade.inputs[0]); L(aof, shade.inputs[1])
    shade2 = N("ShaderNodeMath"); shade2.operation = "MULTIPLY"; L(shade.outputs[0], shade2.inputs[0]); L(height, shade2.inputs[1])
    lit = N("ShaderNodeMix"); lit.data_type = "RGBA"; lit.blend_type = "MULTIPLY"; lit.inputs["Factor"].default_value = 1.0
    L(tex.outputs["Color"], lit.inputs[6])
    grey = N("ShaderNodeCombineColor")
    for i in range(3):
        L(shade2.outputs[0], grey.inputs[i])
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

    img = bpy.data.images.new("merchant-baked", BAKE_SIZE, BAKE_SIZE, alpha=False)
    target = N("ShaderNodeTexImage"); target.image = img
    nt.nodes.active = target
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 16
    scene.render.bake.margin = 3
    select_only(objs)
    bpy.ops.object.bake(type="EMIT")
    path = TEX / "merchant-baked.png"
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()

    nt.nodes.clear()
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bs.inputs["Roughness"].default_value = 0.78
    bs.inputs["Specular IOR Level"].default_value = 0.15
    tx = nt.nodes.new("ShaderNodeTexImage"); tx.image = img
    nt.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])
    mat.name = "MerchantBaked"
    for o in objs:
        o.data.uv_layers.remove(o.data.uv_layers["UVMap"])
        o.data.uv_layers["BakeUV"].name = "UVMap"
    return path


def stage():
    """Soft neutral grey studio: grey world, warm key sun, grey floor disc, camera."""
    scene = bpy.context.scene
    for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    scene.render.resolution_x = scene.render.resolution_y = 1024
    scene.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("StudioGrey")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.50, 0.50, 0.52, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    scene.world = world
    sun_data = bpy.data.lights.new("Preview_Sun", "SUN")
    sun_data.energy = 3.0
    sun_data.angle = math.radians(14)
    sun_data.color = (1.0, 0.96, 0.9)
    sun = bpy.data.objects.new("Preview_Sun", sun_data)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
    fm = bpy.data.meshes.new("Preview_Floor")
    fm.from_pydata([(14 * math.cos(a), 14 * math.sin(a), 0) for a in [2 * math.pi * k / 48 for k in range(48)]], [], [list(range(48))])
    floor = bpy.data.objects.new("Preview_Floor", fm)
    scene.collection.objects.link(floor)
    mat = bpy.data.materials.new("Preview_Floor")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.36, 0.36, 0.38, 1)
    fm.materials.append(mat)
    cam = bpy.data.objects.new("Preview_Cam", bpy.data.cameras.new("Preview_Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam, [sun, floor, cam]


def shoot(cam, path, loc, target, lens=80):
    cam.data.lens = lens
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


VIEWS = {
    "front": ((0, -19.5, 4.3), (0, 0, 3.8), 80),
    "threeq": ((-11.5, -15.5, 6.4), (0, 0.3, 3.75), 80),
    "back": ((4.5, 19.0, 5.2), (0, 0.6, 3.85), 80),
    "side": ((19.5, 0.4, 4.3), (0, 0.4, 3.8), 80),
    "face": ((-1.15, -5.2, 5.95), (0, -0.3, 5.5), 85),
}


def make_sheet(paths, out, cols=3, cell=512):
    import numpy as np
    tiles = []
    for p in paths:
        im = bpy.data.images.load(str(p))
        w, h = im.size
        a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]      # top-down
        f = h // cell
        a = a[:cell * f, :cell * f].reshape(cell, f, cell, f, 4).mean(axis=(1, 3))
        a[..., 3] = 1.0
        tiles.append(a)
        bpy.data.images.remove(im)
    rows = math.ceil(len(tiles) / cols)
    canvas = np.ones((rows * cell, cols * cell, 4), np.float32) * np.array([0.73, 0.73, 0.74, 1.0], np.float32)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        canvas[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell] = t
    img = bpy.data.images.new("sheet", cols * cell, rows * cell, alpha=True)
    img.pixels = canvas[::-1].ravel()
    img.filepath_raw = str(out)
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


# ===========================================================================
# main
# ===========================================================================
def to_studio(v):
    return [round(-v[0], 4) + 0.0, round(v[2], 4) + 0.0, round(v[1], 4) + 0.0]


subprocess.run([sys.executable if not IN_BLENDER else "python", str(Path(__file__).resolve()), "--paint"], check=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
COLL = bpy.data.collections.new("Merchant")
bpy.context.scene.collection.children.link(COLL)
key_materials()

SPECS = [
    (build_head(), None), (build_torso(), None), (build_hips(), None), build_pack(),
    build_upper_arm(1), build_upper_arm(-1), build_lower_arm(1), build_lower_arm(-1),
    build_leg(1), build_leg(-1), build_hand_egg(),
]
OBJS = {}
for P_, M_ in SPECS:
    o = build_object(P_, M_)
    assign_atlas_uvs(o)
    OBJS[o.name] = o
KEYS_BY_OBJ = {n: [p.material_index for p in o.data.polygons] for n, o in OBJS.items()}

JOINTS = {
    "Neck": ("Merchant_Torso", "Merchant_Head", NECK),
    "Waist": ("Merchant_Hips", "Merchant_Torso", WAIST),
    "Pack": ("Merchant_Torso", "Merchant_Pack", PACK),
    "Shoulder_L": ("Merchant_Torso", "Merchant_UpperArm_L", shoulder(1)),
    "Shoulder_R": ("Merchant_Torso", "Merchant_UpperArm_R", shoulder(-1)),
    "Elbow_L": ("Merchant_UpperArm_L", "Merchant_LowerArm_L", M_upper(1) @ elbow_rest(1)),
    "Elbow_R": ("Merchant_UpperArm_R", "Merchant_LowerArm_R", M_upper(-1) @ elbow_rest(-1)),
    "Hip_L": ("Merchant_Hips", "Merchant_Leg_L", hip(1)),
    "Hip_R": ("Merchant_Hips", "Merchant_Leg_R", hip(-1)),
    "HandEgg": ("Merchant_LowerArm_L", "Merchant_HandEgg", M_lower(1) @ EGG_LOCAL),
}


def tris(o):
    o.data.calc_loop_triangles()
    return len(o.data.loop_triangles)


def bbox(o):
    vs = [v.co for v in o.data.vertices]
    return Vector([min(v[i] for v in vs) for i in range(3)]), Vector([max(v[i] for v in vs) for i in range(3)])


TOP = max(bbox(o)[1].z for o in OBJS.values())
TRIS = {n: tris(o) for n, o in OBJS.items()}
print("MERCHANT_TRIS", sum(TRIS.values()), json.dumps(TRIS), "top", round(TOP, 3),
      "hood_top", round(bbox(OBJS["Merchant_Head"])[1].z, 3), flush=True)

if QUICK:
    OUT.mkdir(parents=True, exist_ok=True)
    cam, _helpers = stage()
    bpy.context.scene.render.resolution_x = bpy.context.scene.render.resolution_y = 768
    shots = []
    for name in ("front", "threeq", "back", "side"):
        loc, tgt, lens = VIEWS[name]
        shoot(cam, OUT / f"quick-{name}.png", loc, tgt, lens)
        shots.append(OUT / f"quick-{name}.png")
    make_sheet(shots, OUT / "quick-sheet.png", cols=2, cell=384)
    print("QUICK_DONE", OUT / "quick-sheet.png", flush=True)
    sys.exit(0)

baked = bake(list(OBJS.values()), TOP, KEYS_BY_OBJ)
cam, helpers = stage()
for name, (loc, tgt, lens) in VIEWS.items():
    shoot(cam, ROOT / "previews" / f"merchant-{name}.png", loc, tgt, lens)

if not PREVIEW:
    parts = list(OBJS.values())
    select_only(parts, OBJS["Merchant_Torso"])
    bpy.ops.export_scene.gltf(filepath=str(ROOT / "exports/glb/merchant.glb"), export_format="GLB",
                              use_selection=True, export_apply=True)
    select_only(parts, OBJS["Merchant_Torso"])
    bpy.ops.export_scene.fbx(filepath=str(ROOT / "exports/fbx/merchant.fbx"), use_selection=True,
                             object_types={"MESH"}, axis_forward="-Z", axis_up="Y", path_mode="COPY",
                             embed_textures=True, add_leaf_bones=False)
    report = {
        "asset": "Egg Merchant NPC", "blender_version": bpy.app.version_string,
        "authoring": "final Roblox stud size; import at 1:1, do not scale. Blender Z-up, facing -Y, soles on z=0",
        "texture": f"textures/{baked.name} ({BAKE_SIZE}x{BAKE_SIZE}, baked icon lighting, one atlas for every part)",
        "rest_pose": {"arm_splay_deg": SPLAY, "elbow_bend_deg": {"L": BEND[1], "R": BEND[-1]}},
        "joints_blender": {k: {"parent": a, "child": b, "pivot": [round(c, 4) for c in p]} for k, (a, b, p) in JOINTS.items()},
        "parts": {}, "height_studs": round(bbox(OBJS["Merchant_Head"])[1].z, 3), "top_with_pack": round(TOP, 3),
    }
    for n, o in OBJS.items():
        lo, hi = bbox(o)
        uv = o.data.uv_layers["UVMap"].data
        us, vs = [d.uv.x for d in uv], [d.uv.y for d in uv]
        report["parts"][n] = {"triangles": TRIS[n], "vertices": len(o.data.vertices),
                              "bbox_min": [round(c, 4) for c in lo], "bbox_max": [round(c, 4) for c in hi],
                              "dimensions_studs": [round(c, 4) for c in (hi - lo)],
                              "uv_range": [round(min(us), 4), round(max(us), 4), round(min(vs), 4), round(max(vs), 4)]}
    report["total_triangles"] = sum(TRIS.values())
    (ROOT / "polygon-report-merchant.json").write_text(json.dumps(report, indent=2))
    studio = {"axis": "studio = (-x, z, y) of blender; front = -Z", "parts": {}, "joints": {},
              "height": report["height_studs"], "top_with_pack": report["top_with_pack"], "root": "Merchant_Hips",
              "texture": "textures/merchant-baked.png (TextureID on every MeshPart)"}
    for n, o in OBJS.items():
        lo, hi = bbox(o)
        c, d = (lo + hi) / 2, hi - lo
        studio["parts"][n] = {"centre": to_studio(c), "size": [round(d.x, 4), round(d.z, 4), round(d.y, 4)], "tris": TRIS[n]}
    for k, (a, b, p) in JOINTS.items():
        studio["joints"][k] = {"parent": a, "child": b, "pivot": to_studio(p)}
    (ROOT / "studio-install-data-merchant.json").write_text(json.dumps(studio, indent=2))
    for h in helpers:
        bpy.data.objects.remove(h, do_unlink=True)
    for im in bpy.data.images:
        if im.users and (im.source == "FILE" or im.is_dirty):
            im.pack()
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "merchant.blend"))
print("MERCHANT_READY", sum(TRIS.values()), flush=True)
