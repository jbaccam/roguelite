"""Derp chicken: a small, goofy, blocky chicken ally for the roguelite.

When the player's thrown Egg lands it sometimes hatches this chicken, which runs over and pecks
enemies. This script makes only the art asset. It is self-contained (no code from sibling kits).

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python build_chicken.py
    ... --python build_chicken.py -- --no-previews      # skip the preview renders

Writes (all inside this folder):
    derp-chicken.blend
    textures/derp-chicken-atlas.png     one painted 1024x1024 atlas shared by all six parts
    exports/fbx/derp-chicken.fbx        six rigid mesh objects, origins at their joint pivots
    exports/glb/derp-chicken.glb
    polygon-report.json                 triangles per part and in total, sizes, pivots
    studio-install-data.json            per part: bbox centre, size and joint pivot in Studio axes
    previews/*.png                      real Blender (Cycles) renders

Coordinates: Blender Z-up, 1 unit = 1 stud (model at final size, import 1:1), feet bottom at
z = 0, the chicken faces -Y, and its own left is +X. Blender (x, y, z) -> Studio (-x, z, y), so
Studio front is -Z and the chicken's left is Studio -X.

Style: stylized low-poly (see ../art-references/ART_DIRECTION_USER_2026-09-17.txt). Minecraft-
chicken proportions built from chunky soft-bevelled boxes with slight taper, big googly eyes
with mismatched pupils, and a painterly low-noise atlas (broad patches, lighter top, warmer
cream underside, soft cream crease shadows, a few big feather patches on the wings).

Texture method: the six parts are unwrapped together into one atlas, Cycles bakes world
position, normal, a per-face colour-zone id and ambient occlusion into float images, and numpy
paints the final colours from those maps. Painting from 3D position keeps patches continuous
across UV seams.
"""
import json
import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

T0 = time.time()
ROOT = Path(__file__).resolve().parent
TEX_DIR = ROOT / "textures"
PREV_DIR = ROOT / "previews"
FBX_PATH = ROOT / "exports" / "fbx" / "derp-chicken.fbx"
GLB_PATH = ROOT / "exports" / "glb" / "derp-chicken.glb"
ATLAS_PATH = TEX_DIR / "derp-chicken-atlas.png"
BLEND_PATH = ROOT / "derp-chicken.blend"
ATLAS = 1024
SMOOTH_ANGLE = 28.0     # shade-smooth-by-angle limit: the 2-segment bevels (30 deg steps) stay faceted
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SKIP_PREVIEWS = "--no-previews" in ARGS

for d in (TEX_DIR, PREV_DIR, FBX_PATH.parent, GLB_PATH.parent):
    d.mkdir(parents=True, exist_ok=True)


def log(*a):
    print(f"[chicken {time.time() - T0:6.1f}s]", *a, flush=True)


def rad(v):
    return tuple(math.radians(x) for x in v)


# colour zones, stored per face and baked so the painter knows what each texel is
Z_BODY, Z_HEAD, Z_WING, Z_BEAK, Z_LEG, Z_RED, Z_EYE, Z_PUPIL, Z_TONGUE, Z_FEATHER = range(1, 11)

# ---------------------------------------------------------------------------------------------
# proportions (studs)
# ---------------------------------------------------------------------------------------------
HIP_Z = 0.55            # body underside / hip joints
LEG_X = 0.30            # hips at x = +-0.30, y = 0
NECK = (0.0, -0.55, 1.38)
SHOULDER = (0.61, -0.36, 1.44)   # left wing hinge (top-front); the right wing mirrors x

# the loose feather (death "pop" burst piece): length along Y (quill end at -Y), width X,
# thickness Z. It rests beside the chicken in the export, far enough away that no AO is shared.
FEATHER_AT = Vector((1.45, 0.30, 0.04))
FEATHER_VANE_Y0, FEATHER_VANE_LEN, FEATHER_QUILL = -0.195, 0.47, 0.08


def feather_spine_x(s):
    """In-plane curve of the feather's spine (feather-local x) at vane fraction s."""
    return 0.035 * s * s


def feather_arch_z(s):
    return 0.02 * (1.0 - (2.0 * s - 1.0) ** 2)


# ---------------------------------------------------------------------------------------------
# geometry helpers: every piece is built, bevelled on its own, then tagged with its zone
# ---------------------------------------------------------------------------------------------
def box_corners(w, d, h, top=(1.0, 1.0, 0.0, 0.0), front=(1.0, 1.0, 0.0)):
    """Eight corners of a box centred on the origin, order b0..b3 (bottom) then t0..t3, each
    ring (-x,-y) (+x,-y) (+x,+y) (-x,+y). top = (sx, sy, dx, dy) scales/shifts the top face;
    front = (sx, sz, dz) tapers/droops the -Y face (beaks, toes)."""
    out = []
    for zs in (-1, 1):
        for xs, ys in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            x, y, z = xs * w / 2, ys * d / 2, zs * h / 2
            if zs > 0:
                x, y = x * top[0] + top[2], y * top[1] + top[3]
            if ys < 0:
                x, z = x * front[0], z * front[1] + front[2]
            out.append(Vector((x, y, z)))
    return out


def placed(corners, offset=(0, 0, 0), rot=(0, 0, 0), at=(0, 0, 0)):
    m = Matrix.Translation(at) @ Euler(rad(rot)).to_matrix().to_4x4() @ Matrix.Translation(offset)
    return [m @ c for c in corners]


class Part:
    def __init__(self, name, pivot, joint, kind="rig"):
        self.name, self.pivot, self.joint, self.kind = name, Vector(pivot), joint, kind
        self.bm = bmesh.new()
        self.zl = self.bm.faces.layers.float.new("zone")
        self.pupils = []

    def _close(self, zone, bevel=0.0, segments=2, angle=30.0):
        bm = self.bm
        new = [f for f in bm.faces if f[self.zl] == 0.0]
        bmesh.ops.recalc_face_normals(bm, faces=new)
        bm.normal_update()
        if bevel > 0:
            edges = {e for f in new for e in f.edges}
            edges = [e for e in edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(angle)]
            if edges:
                bmesh.ops.bevel(bm, geom=edges, offset=bevel, offset_type="OFFSET", segments=segments,
                                profile=0.5, affect="EDGES", clamp_overlap=True)
        for f in bm.faces:
            if f[self.zl] == 0.0:
                f[self.zl] = float(zone)

    def box8(self, c, zone, bevel, segments=2):
        v = [self.bm.verts.new(p) for p in c]
        for idx in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self.bm.faces.new([v[i] for i in idx])
        self._close(zone, bevel, segments)

    def block(self, w, d, h, zone, bevel, segments=2, top=(1, 1, 0, 0), front=(1, 1, 0),
              offset=(0, 0, 0), rot=(0, 0, 0), at=(0, 0, 0)):
        self.box8(placed(box_corners(w, d, h, top, front), offset, rot, at), zone, bevel, segments)

    def loft(self, rings, zone, tip):
        """Skin equal-sized point rings into a solid: a cap on the first ring, a fan to `tip`."""
        bm = self.bm
        vs = [[bm.verts.new(p) for p in ring] for ring in rings]
        k = len(rings[0])
        for a, b in zip(vs, vs[1:]):
            for i in range(k):
                j = (i + 1) % k
                bm.faces.new([a[i], a[j], b[j], b[i]])
        bm.faces.new(vs[0][::-1])
        t = bm.verts.new(tip)
        for i in range(k):
            bm.faces.new([vs[-1][i], vs[-1][(i + 1) % k], t])
        self._close(zone)

    def ellipsoid(self, center, radii, forward, zone, useg=12, vseg=8):
        """Low-poly ellipsoid whose pole (local Z) points along `forward`."""
        q = Vector(forward).normalized().to_track_quat("Z", "Y")
        m = Matrix.Translation(center) @ q.to_matrix().to_4x4() @ Matrix.Diagonal((*radii, 1.0))
        bmesh.ops.create_uvsphere(self.bm, u_segments=useg, v_segments=vseg, radius=1.0, matrix=m)
        self._close(zone)

    def slab_yz(self, outline, x0, x1, zone, bevel, segments=2, hinge=None, tilt_y=0.0):
        """A flat slab: the (y, z) outline extruded from x0 to x1, optionally tilted about a
        Y-parallel axis through `hinge`."""
        bm = self.bm
        a = [bm.verts.new((x0, y, z)) for y, z in outline]
        b = [bm.verts.new((x1, y, z)) for y, z in outline]
        n = len(outline)
        bm.faces.new(a[::-1])
        bm.faces.new(b)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new([a[i], a[j], b[j], b[i]])
        if tilt_y:
            bmesh.ops.rotate(bm, cent=hinge, matrix=Matrix.Rotation(math.radians(tilt_y), 3, "Y"), verts=a + b)
        self._close(zone, bevel, segments)

    def to_object(self, material):
        bm = self.bm
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])
        bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
        me = bpy.data.meshes.new(self.name)
        bm.to_mesh(me)
        bm.free()
        me.transform(Matrix.Translation(-self.pivot))      # origin = joint pivot
        me.materials.append(material)
        ob = bpy.data.objects.new(self.name, me)
        ob.location = self.pivot
        bpy.context.scene.collection.objects.link(ob)
        return ob


# ---------------------------------------------------------------------------------------------
# the chicken
# ---------------------------------------------------------------------------------------------
def build_body():
    p = Part("Chicken_Body", (0, 0, HIP_Z), "hip-line centre (the root part; waddle/bob pivot)")
    # chunky body: slightly wider on top, back end a little lower and narrower than the chest
    p.box8([Vector(c) for c in (
        (-0.58, -0.55, 0.52), (0.58, -0.55, 0.52), (0.56, 0.92, 0.56), (-0.56, 0.92, 0.56),
        (-0.66, -0.63, 1.62), (0.66, -0.63, 1.62), (0.63, 1.03, 1.56), (-0.63, 1.03, 1.56))],
        Z_BODY, bevel=0.14)
    # stubby stepped tail tuft at the back top
    p.block(0.78, 0.36, 0.64, Z_BODY, 0.10, top=(0.78, 0.85, 0, 0), offset=(0, 0, 0.32),
            rot=(-24, 0, 0), at=(0, 0.88, 1.28))
    p.block(0.46, 0.28, 0.40, Z_BODY, 0.07, top=(0.75, 0.8, 0, 0), offset=(0, 0, 0.20),
            rot=(-38, 0, 6), at=(0.04, 1.00, 1.60))
    return p


def head_face_y(z):
    """y of the head's (slightly forward-leaning) front face at height z."""
    return -1.10 - 0.02 * (z - 1.22) / 1.18


def eyeball_and_pupil(p, x, z, yaw, radii, protrude, pupil_dir, pupil_r):
    f = Vector((math.sin(math.radians(yaw)), -math.cos(math.radians(yaw)), 0.0))
    face = Vector((x, head_face_y(z), z))
    centre = face + f * (protrude - radii[2])
    p.ellipsoid(centre, radii, f, Z_EYE, useg=12, vseg=8)
    # pupil: a flattened black lens sitting on the eyeball surface in direction pupil_dir
    # (eye-local: x = chicken's left, y = up, z = forward)
    rot = f.to_track_quat("Z", "Y").to_matrix()
    d = Vector(pupil_dir).normalized()
    a, b, c = radii
    t = 1.0 / math.sqrt((d.x / a) ** 2 + (d.y / b) ** 2 + (d.z / c) ** 2)
    pl = d * t
    nl = Vector((pl.x / a ** 2, pl.y / b ** 2, pl.z / c ** 2)).normalized()
    pw, nw = centre + rot @ pl, (rot @ nl).normalized()
    p.ellipsoid(pw - nw * 0.03, (pupil_r, pupil_r, 0.06), nw, Z_PUPIL, useg=10, vseg=6)
    p.pupils.append({"centre": pw, "normal": nw, "r": pupil_r})


def build_head():
    p = Part("Chicken_Head", NECK, "neck point (peck/bob pivot)")
    # tall Minecraft-style head, leaning forward a touch
    p.block(0.90, 0.76, 1.18, Z_HEAD, 0.12, top=(0.97, 1.0, 0, -0.02), offset=(0, 0, 0.59), at=(0, -0.72, 1.22))
    # derp eyes: different sizes, the left (+X) pupil looks up-and-out, the right one down-and-in
    eyeball_and_pupil(p, 0.235, 2.02, 16, (0.25, 0.26, 0.20), 0.14, (0.60, 0.75, 1.0), 0.105)
    eyeball_and_pupil(p, -0.245, 2.06, -16, (0.205, 0.215, 0.165), 0.13, (0.62, -0.55, 1.0), 0.09)
    # beak, slightly open, with a tongue flopping out of one side
    p.block(0.44, 0.42, 0.20, Z_BEAK, 0.045, front=(0.60, 0.62, -0.035), offset=(0, -0.21, 0), at=(0, -1.04, 1.64))
    p.block(0.34, 0.30, 0.10, Z_BEAK, 0.03, front=(0.62, 0.60, 0), offset=(0, -0.15, 0), rot=(16, 0, 0), at=(0, -1.06, 1.50))
    p.block(0.14, 0.30, 0.05, Z_TONGUE, 0.022, top=(0.9, 1, 0, 0), front=(0.85, 1, 0), offset=(0, -0.15, 0),
            rot=(22, 0, 28), at=(0.03, -1.06, 1.54))
    # wattle under the beak, comb of three lumps on top
    p.block(0.24, 0.16, 0.30, Z_RED, 0.06, top=(1.15, 1.0, 0, 0), offset=(0, 0, -0.15), at=(0, -1.16, 1.48))
    for y, h, rx in ((-0.92, 0.22, 12), (-0.72, 0.28, 0), (-0.52, 0.20, -12)):
        p.block(0.17, 0.22, h, Z_RED, 0.06, top=(0.85, 0.8, 0, 0), offset=(0, 0, h / 2), rot=(rx, -6, 0), at=(0.03, y, 2.34))
    return p


WING_OUTLINE = [(-0.36, 1.46), (0.44, 1.46), (0.66, 1.31), (0.50, 1.23), (0.60, 1.07),
                (0.40, 1.00), (0.30, 0.86), (-0.22, 0.86), (-0.42, 0.98), (-0.46, 1.30)]


def build_wing(side):
    s = 1 if side == "L" else -1
    hinge = Vector((s * SHOULDER[0], SHOULDER[1], SHOULDER[2]))
    p = Part(f"Chicken_Wing{side}", hinge, "top-front shoulder hinge (flap about the front-back axis)")
    p.slab_yz(WING_OUTLINE, s * 0.60, s * 0.72, Z_WING, 0.035, hinge=hinge, tilt_y=5.0 * s)
    return p


def build_leg(side):
    s = 1 if side == "L" else -1
    x = s * LEG_X
    p = Part(f"Chicken_Leg{side}", (x, 0, HIP_Z), "hip point at the body underside (swing about the side axis)")
    p.block(0.13, 0.13, 0.58, Z_LEG, 0.03, segments=1, at=(x, 0.0, 0.33))
    p.block(0.20, 0.20, 0.07, Z_LEG, 0.025, segments=1, at=(x, 0.01, 0.035))
    for a in (-32, 0, 32):
        p.block(0.10, 0.30, 0.065, Z_LEG, 0.022, segments=1, front=(0.7, 0.8, 0.0),
                offset=(0, -0.15, 0.0325), rot=(0, 0, a), at=(x, -0.02, 0.0))
    return p


# vane stations: (fraction along the vane, half-width left, half-width right, spine thickness);
# the dip at 0.58 is a cartoon split on one side
FEATHER_STATIONS = [(0.00, 0.035, 0.035, 0.050), (0.14, 0.080, 0.088, 0.052), (0.34, 0.100, 0.112, 0.050),
                    (0.52, 0.100, 0.110, 0.046), (0.58, 0.098, 0.066, 0.045), (0.64, 0.094, 0.100, 0.044),
                    (0.82, 0.066, 0.070, 0.038), (0.96, 0.026, 0.024, 0.028)]


def build_feather():
    """One loose cartoon feather: a hexagonal-section vane (thick raised spine, thin soft rim),
    gently curved in plane and arched, plus a short quill. Origin = its bbox centre."""
    p = Part("Chicken_Feather", (0, 0, 0), "bbox centre (standalone burst piece, not part of the rig)", kind="feather")
    o = FEATHER_AT
    rings = []
    for s, wl, wr, t in FEATHER_STATIONS:
        y = FEATHER_VANE_Y0 + s * FEATHER_VANE_LEN
        xs, z0, e = feather_spine_x(s), feather_arch_z(s), min(0.006, t / 4)
        rings.append([o + Vector(v) for v in ((xs - wl, y, z0 + e), (xs, y, z0 + t / 2), (xs + wr, y, z0 + e),
                                               (xs + wr, y, z0 - e), (xs, y, z0 - t * 0.35), (xs - wl, y, z0 - e))])
    tip = o + Vector((feather_spine_x(1.0), FEATHER_VANE_Y0 + FEATHER_VANE_LEN, feather_arch_z(1.0)))
    p.loft(rings, Z_FEATHER, tip)
    # quill: a short tapered stem poking out of the vane base
    p.block(0.032, FEATHER_QUILL + 0.03, 0.032, Z_FEATHER, 0.0, front=(0.65, 0.65, 0.0),
            offset=(0, -(FEATHER_QUILL + 0.03) / 2, 0), at=o + Vector((0, FEATHER_VANE_Y0 + 0.03, 0)))
    xs = [v.co for v in p.bm.verts]
    p.pivot = Vector([(min(c[k] for c in xs) + max(c[k] for c in xs)) / 2 for k in range(3)])
    return p


# ---------------------------------------------------------------------------------------------
# texture painting (numpy), driven by baked position / normal / zone / AO maps
# ---------------------------------------------------------------------------------------------
_rng = np.random.default_rng(20260928)
_PERM = np.concatenate([_rng.permutation(256)] * 2)
_VALS = _rng.random(256)


def vnoise(p, freq, seed=0):
    """Smooth 3D value noise in 0..1 (trilinear with smoothstep), p: (M, 3) studs."""
    q = p * freq + seed * 17.31
    i = np.floor(q).astype(np.int64)
    f = q - i
    u = f * f * (3 - 2 * f)
    out = np.zeros(len(p))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (u[:, 0] if dx else 1 - u[:, 0]) * (u[:, 1] if dy else 1 - u[:, 1]) * (u[:, 2] if dz else 1 - u[:, 2])
                h = _VALS[_PERM[_PERM[_PERM[(i[:, 0] + dx) & 255] + ((i[:, 1] + dy) & 255)] + ((i[:, 2] + dz) & 255)]]
                out += w * h
    return out


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def rgb(*c):
    return np.array(c, dtype=np.float64) / 255.0


def lerp(a, b, t):
    return a + (b - a) * np.asarray(t)[..., None]


# palette (sRGB); clean and warm: the game adds +0.3 saturation in Studio
FEATHER_HI = rgb(255, 253, 244)
FEATHER = rgb(251, 246, 232)
FEATHER_MID = rgb(245, 234, 208)
FEATHER_UNDER = rgb(240, 222, 186)
FEATHER_SHADOW = rgb(230, 206, 166)
WING_PATCH = rgb(241, 226, 194)
BEAK = (rgb(252, 172, 46), rgb(255, 210, 100), rgb(226, 126, 32))    # base, light, dark
LEG = (rgb(247, 160, 44), rgb(255, 198, 94), rgb(212, 114, 32))
RED = (rgb(226, 54, 50), rgb(246, 104, 88), rgb(178, 32, 44))
TONGUE = (rgb(242, 116, 140), rgb(252, 158, 176), rgb(200, 72, 104))
EYE_WHITE, EYE_SHADE = rgb(253, 253, 250), rgb(220, 225, 238)
PUPIL, GLINT = rgb(30, 28, 36), rgb(255, 255, 255)
QUILL = rgb(236, 214, 170)

# big soft feather patches on the wings, as ellipses in (y, z): centre, radii, angle (deg)
WING_PATCHES = [((0.50, 1.28), (0.20, 0.080), -28), ((0.44, 1.10), (0.20, 0.080), -22),
                ((0.20, 0.96), (0.24, 0.085), -8)]


def paint(P, N, zone, ao, pupils):
    M = len(P)
    col = np.tile(FEATHER, (M, 1))
    up, down = np.clip(N[:, 2], 0, 1), np.clip(-N[:, 2], 0, 1)
    occl = np.clip((1.0 - ao) * 1.4, 0, 1)
    n = 0.65 * vnoise(P, 1.7) + 0.35 * vnoise(P, 3.6, seed=1)
    levels = 0.5 * (sstep(0.40, 0.47, n) + sstep(0.56, 0.63, n))     # 3 broad value ranges

    feather = np.isin(zone, (Z_BODY, Z_HEAD, Z_WING)) | (zone == 0)
    c = lerp(FEATHER_MID, FEATHER, levels)
    c = lerp(c, FEATHER_HI, 0.6 * up ** 1.5)
    c = lerp(c, FEATHER_UNDER, 0.65 * down + 0.3 * sstep(1.05, 0.55, P[:, 2]))
    wing = zone == Z_WING
    for (cy, cz), (ry, rz), ang in WING_PATCHES:
        a = math.radians(ang)
        dy, dz = P[:, 1] - cy, P[:, 2] - cz
        u = (dy * math.cos(a) + dz * math.sin(a)) / ry
        v = (-dy * math.sin(a) + dz * math.cos(a)) / rz
        m = sstep(1.0, 0.65, np.sqrt(u * u + v * v)) * wing
        c = lerp(c, WING_PATCH, 0.8 * m)
    c = lerp(c, FEATHER_HI, 0.35 * wing * sstep(1.30, 1.42, P[:, 2]))            # lighter wing coverts
    tail = (zone == Z_BODY) & (P[:, 1] > 0.95)
    c = lerp(c, FEATHER_MID, 0.5 * tail * sstep(1.55, 1.9, P[:, 2]))              # creamier tail tips
    c = lerp(c, FEATHER_SHADOW, 0.85 * occl)
    col[feather] = c[feather]

    # loose feather: creamier toward the quill, lighter tip, a soft warm spine line
    fz = zone == Z_FEATHER
    if fz.any():
        lp = P - np.array(FEATHER_AT)
        s = np.clip((lp[:, 1] - FEATHER_VANE_Y0) / FEATHER_VANE_LEN, 0, 1)
        cf = lerp(FEATHER_MID, FEATHER, levels)
        cf = lerp(cf, FEATHER_HI, 0.5 * up ** 1.5)
        cf = lerp(cf, FEATHER_UNDER, np.clip(0.3 * sstep(0.35, 0.0, s) + 0.5 * down, 0, 1))
        cf = lerp(cf, FEATHER_HI, 0.3 + 0.35 * sstep(0.5, 1.0, s))
        spine = sstep(0.02, 0.008, np.abs(lp[:, 0] - feather_spine_x(s))) * sstep(0.9, 0.6, s)
        spine = np.maximum(spine, (lp[:, 1] < FEATHER_VANE_Y0 + 0.01).astype(float))
        cf = lerp(cf, QUILL, 0.7 * spine)
        cf = lerp(cf, FEATHER_SHADOW, 0.85 * occl)
        col[fz] = cf[fz]

    def solid(z, pal, patch=0.05):
        base, light, dark = pal
        s = 0.5 + 0.5 * N[:, 2]
        cc = lerp(dark, base, sstep(0.05, 0.55, s))
        cc = lerp(cc, light, 0.75 * sstep(0.62, 1.0, s))
        cc = lerp(cc, dark, 0.75 * occl)
        cc = cc * (1.0 - patch + 2 * patch * levels)[:, None]
        sel = zone == z
        col[sel] = cc[sel]

    solid(Z_BEAK, BEAK)
    solid(Z_LEG, LEG)
    solid(Z_RED, RED)
    solid(Z_TONGUE, TONGUE)

    eye = zone == Z_EYE
    ce = lerp(np.tile(EYE_WHITE, (M, 1)), EYE_SHADE, np.clip(0.8 * sstep(0.1, -0.7, N[:, 2]) + 0.9 * occl, 0, 1))
    col[eye] = ce[eye]

    pup = zone == Z_PUPIL
    cp = np.tile(PUPIL, (M, 1))
    for pu in pupils:        # one soft catchlight per pupil, up and to the viewer's left
        cen, nrm, r = np.array(pu["centre"]), np.array(pu["normal"]), pu["r"]
        want = np.array((-0.55, 0.0, 0.85))
        tang = want - nrm * want.dot(nrm)
        tang /= np.linalg.norm(tang)
        spot = cen + tang * 0.42 * r + nrm * 0.03
        dist = np.linalg.norm(P - spot, axis=1)
        cp = lerp(cp, GLINT, sstep(0.36 * r, 0.24 * r, dist))
    col[pup] = cp[pup]
    return np.clip(col, 0, 1)


# ---------------------------------------------------------------------------------------------
# scene setup, build, unwrap
# ---------------------------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

mat = bpy.data.materials.new("DerpChicken_Atlas")
mat.use_nodes = True

builders = [build_body(), build_head(), build_wing("L"), build_wing("R"), build_leg("L"), build_leg("R"),
            build_feather()]
pupils = [pu for b in builders for pu in b.pupils]
meta = {b.name: {"pivot": b.pivot.copy(), "joint": b.joint, "kind": b.kind} for b in builders}
objs = [b.to_object(mat) for b in builders]
parts = {o.name: o for o in objs}
rig = {n: o for n, o in parts.items() if meta[n]["kind"] == "rig"}
feather_obj = parts["Chicken_Feather"]
log("built", {o.name: len(o.data.polygons) for o in objs})


def select_only(obs, active=None):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or obs[0]


select_only(objs)
bpy.ops.object.shade_smooth_by_angle(angle=math.radians(SMOOTH_ANGLE), keep_sharp_edges=True)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(50), island_margin=0.006, area_weight=0.0,
                         correct_aspect=True, scale_to_bounds=False)
bpy.ops.uv.pack_islands(rotate=True, margin=0.006)
bpy.ops.object.mode_set(mode="OBJECT")
for o in objs:
    o.data.uv_layers.active.name = "UVMap"
log("unwrapped")

# ---------------------------------------------------------------------------------------------
# bake data maps, paint the atlas
# ---------------------------------------------------------------------------------------------
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.render.bake.use_selected_to_active = False
nt = mat.node_tree


def bake_pass(kind, samples):
    nt.nodes.clear()
    N_, L_ = nt.nodes.new, nt.links.new
    geo = N_("ShaderNodeNewGeometry")
    em = N_("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    out = N_("ShaderNodeOutputMaterial")
    L_(em.outputs["Emission"], out.inputs["Surface"])
    if kind in ("pos", "nrm"):
        m = N_("ShaderNodeVectorMath")
        m.operation = "MULTIPLY_ADD"
        L_(geo.outputs["Position" if kind == "pos" else "Normal"], m.inputs[0])
        m.inputs[1].default_value = (0.125,) * 3 if kind == "pos" else (0.5,) * 3
        m.inputs[2].default_value = (0.5,) * 3
        L_(m.outputs["Vector"], em.inputs["Color"])
    else:
        at = N_("ShaderNodeAttribute")
        at.attribute_type = "GEOMETRY"
        at.attribute_name = "zone"
        dz = N_("ShaderNodeMath")
        dz.operation = "MULTIPLY"
        L_(at.outputs["Fac"], dz.inputs[0])
        dz.inputs[1].default_value = 1.0 / 16.0
        ao = N_("ShaderNodeAmbientOcclusion")
        ao.samples = 16
        ao.inputs["Distance"].default_value = 0.35
        comb = N_("ShaderNodeCombineXYZ")
        L_(dz.outputs["Value"], comb.inputs["X"])
        L_(ao.outputs["AO"], comb.inputs["Y"])
        L_(comb.outputs["Vector"], em.inputs["Color"])
    img = bpy.data.images.new(f"bake_{kind}", ATLAS, ATLAS, alpha=True, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    tn = N_("ShaderNodeTexImage")
    tn.image = img
    nt.nodes.active = tn
    scene.cycles.samples = samples
    select_only(objs)
    bpy.ops.object.bake(type="EMIT", margin=8, margin_type="EXTEND", use_clear=True)
    arr = np.empty(ATLAS * ATLAS * 4, np.float32)
    img.pixels.foreach_get(arr)
    bpy.data.images.remove(img)
    return arr.reshape(-1, 4)


pos = bake_pass("pos", 1)
nrm = bake_pass("nrm", 1)
zao = bake_pass("zone_ao", 24)
log("baked data maps")
P = (pos[:, :3].astype(np.float64) - 0.5) * 8.0
Nrm = nrm[:, :3].astype(np.float64) * 2.0 - 1.0
Nrm /= np.maximum(np.linalg.norm(Nrm, axis=1), 1e-6)[:, None]
zone = np.rint(zao[:, 0] * 16.0).astype(np.int64)
AO = np.clip(zao[:, 1].astype(np.float64), 0, 1)
colour = paint(P, Nrm, zone, AO, pupils)
rgba = np.concatenate([colour, np.ones((len(colour), 1))], axis=1).astype(np.float32)
atlas = bpy.data.images.new("derp-chicken-atlas-src", ATLAS, ATLAS, alpha=False)
atlas.pixels.foreach_set(rgba.ravel())
atlas.filepath_raw = str(ATLAS_PATH)
atlas.file_format = "PNG"
atlas.save()
bpy.data.images.remove(atlas)
log("painted", ATLAS_PATH.name, "zones used:", sorted(set(np.unique(zone).tolist())))

# final material: the painted atlas only (Roblox: one TextureID shared by all seven MeshParts)
nt.nodes.clear()
tex_img = bpy.data.images.load(str(ATLAS_PATH), check_existing=False)
tex_img.name = "derp-chicken-atlas"
bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
bs.inputs["Roughness"].default_value = 0.85
bs.inputs["Specular IOR Level"].default_value = 0.2
tx = nt.nodes.new("ShaderNodeTexImage")
tx.image = tex_img
nt.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
out = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])
for o in objs:
    if "zone" in o.data.attributes:
        o.data.attributes.remove(o.data.attributes["zone"])

# ---------------------------------------------------------------------------------------------
# reports
# ---------------------------------------------------------------------------------------------
bpy.context.view_layer.update()


def studio(v):
    return [round(-v[0], 4) + 0.0, round(v[2], 4) + 0.0, round(v[1], 4) + 0.0]    # + 0.0 drops "-0.0"


def studio_size(v):
    return [round(v[0], 4), round(v[2], 4), round(v[1], 4)]


def world_bounds(o):
    ws = [o.matrix_world @ v.co for v in o.data.vertices]
    return (Vector([min(w[k] for w in ws) for k in range(3)]), Vector([max(w[k] for w in ws) for k in range(3)]))


report = {"asset": "derp-chicken", "blender_version": bpy.app.version_string,
          "authoring": "final Roblox stud size (1 Blender unit = 1 stud); import at 1:1, do not scale",
          "axes": "Blender Z-up, front -Y, chicken's left +X; feet bottom z = 0",
          "texture": f"textures/{ATLAS_PATH.name} ({ATLAS}x{ATLAS}, shared by every part)",
          "parts": {}}
lo_all, hi_all = Vector((1e9,) * 3), Vector((-1e9,) * 3)
for name, o in parts.items():
    me = o.data
    me.calc_loop_triangles()
    uv = me.uv_layers.active.data
    us, vs = [d.uv.x for d in uv], [d.uv.y for d in uv]
    lo, hi = world_bounds(o)
    if name in rig:
        lo_all = Vector([min(lo_all[k], lo[k]) for k in range(3)])
        hi_all = Vector([max(hi_all[k], hi[k]) for k in range(3)])
    report["parts"][name] = {
        "kind": meta[name]["kind"],
        "triangles": len(me.loop_triangles), "vertices": len(me.vertices),
        "dimensions_studs": [round(v, 4) for v in o.dimensions],
        "bbox_min": [round(v, 4) for v in lo], "bbox_max": [round(v, 4) for v in hi],
        "pivot": [round(v, 4) for v in o.location], "pivot_is": meta[name]["joint"],
        "uv_range": [round(min(us), 4), round(max(us), 4), round(min(vs), 4), round(max(vs), 4)],
        "min_face_area": round(min(p.area for p in me.polygons), 8),
    }
report["total_triangles"] = sum(p["triangles"] for p in report["parts"].values())
report["rig_triangles"] = sum(p["triangles"] for n, p in report["parts"].items() if n in rig)
report["feather_triangles"] = report["parts"]["Chicken_Feather"]["triangles"]
size = hi_all - lo_all
report["overall"] = {"scope": "chicken rig only (the loose feather is excluded)", "bbox_min": [round(v, 4) for v in lo_all], "bbox_max": [round(v, 4) for v in hi_all],
                     "height_studs": round(size.z, 4), "length_studs": round(size.y, 4), "width_studs": round(size.x, 4),
                     "body_length_studs": round(parts["Chicken_Body"].dimensions.y, 4)}
(ROOT / "polygon-report.json").write_text(json.dumps(report, indent=2))

body_pivot = parts["Chicken_Body"].location.copy()
motion = {
    "Chicken_Body": "root part; waddle = small roll about Studio Z (front-back) and bob in Studio Y",
    "Chicken_Head": "peck = pitch about Studio X (side-to-side axis) through the neck point",
    "Chicken_WingL": "flap = rotate about Studio Z (front-back axis) through the shoulder hinge, tip swinging out/up",
    "Chicken_WingR": "flap = rotate about Studio Z (front-back axis) through the shoulder hinge, tip swinging out/up",
    "Chicken_LegL": "walk = swing about Studio X (side-to-side axis) through the hip point",
    "Chicken_LegR": "walk = swing about Studio X (side-to-side axis) through the hip point",
    "Chicken_Feather": "not part of the rig: clone it many times for the death 'pop' feather burst",
}
install = {
    "asset": "derp-chicken",
    "axis": "studio = (-x, z, y) of blender; Blender front -Y = Studio front -Z",
    "units": "studs; the model is at final size, import 1:1 and do not scale",
    "sides": "L/R are the chicken's own left/right; its left is Blender +X = Studio -X",
    "origin": "all positions are relative to the model origin = ground point (Blender world origin): the "
              "hip-line centre dropped to the feet bottom",
    "ground_point": studio((0.0, 0.0, 0.0)),
    "overall_size": studio_size(size),
    "overall_center": studio((lo_all + hi_all) / 2),
    "texture": f"textures/{ATLAS_PATH.name}",
    "texture_note": "one shared atlas; every MeshPart uses the same TextureID",
    "body_pivot_convention": "Chicken_Body pivot = centre of the hip line (not the body bbox centre)",
    "rest_rotation": "every part has identity rotation relative to the model at rest",
    "overall_scope": "overall_size / overall_center / ground_point cover the six rig parts only",
    "feather_note": "Chicken_Feather (kind 'feather') is a standalone burst piece exported beside the chicken; "
                    "do not weld or Motor6D it to the rig. Origin = its bbox centre; length along Studio Z "
                    "(quill end toward -Z, tip toward +Z), width along X, thickness along Y (lies flat at rest)",
    "parts": {},
}
for name, o in parts.items():
    lo, hi = world_bounds(o)
    install["parts"][name] = {
        "kind": meta[name]["kind"],
        "center": studio((lo + hi) / 2),
        "size": studio_size(hi - lo),
        "pivot": studio(o.location),
        "pivot_is": meta[name]["joint"],
        "suggested_motion": motion[name],
    }
    if name in rig:
        install["parts"][name]["pivot_from_body_pivot"] = studio(o.location - body_pivot)
(ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=2))
log("reports written; total tris", report["total_triangles"], "rig", report["rig_triangles"],
    "feather", report["feather_triangles"], "feather dims", tuple(round(v, 3) for v in feather_obj.dimensions),
    "rig size (w, len, h)",
    tuple(round(v, 3) for v in (size.x, size.y, size.z)))

# ---------------------------------------------------------------------------------------------
# export + save
# ---------------------------------------------------------------------------------------------
select_only(objs, parts["Chicken_Body"])
bpy.ops.export_scene.gltf(filepath=str(GLB_PATH), export_format="GLB", use_selection=True, export_apply=True)
select_only(objs, parts["Chicken_Body"])
bpy.ops.export_scene.fbx(filepath=str(FBX_PATH), use_selection=True, object_types={"MESH"},
                         axis_forward="-Z", axis_up="Y", path_mode="COPY", embed_textures=True,
                         add_leaf_bones=False)
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH), relative_remap=True)
log("exported + saved")

# ---------------------------------------------------------------------------------------------
# previews: Cycles, shadow-catcher floor, composited onto a clean light-grey background
# ---------------------------------------------------------------------------------------------
if SKIP_PREVIEWS:
    log("previews skipped")
    raise SystemExit(0)

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 96
scene.cycles.use_denoising = True
scene.render.film_transparent = True
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"

world = bpy.data.worlds.new("SoftStudio")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.93, 0.95, 1.0, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.5
scene.world = world


def add_sun(name, energy, rot, angle, color, shadows=True):
    L = bpy.data.lights.new(name, "SUN")
    L.energy, L.angle, L.color = energy, math.radians(angle), color
    L.use_shadow = shadows
    ob = bpy.data.objects.new(name, L)
    ob.rotation_euler = rad(rot)
    scene.collection.objects.link(ob)
    return ob


add_sun("Key", 0.62, (42, 0, -32), 14, (1.0, 0.97, 0.92))
add_sun("Fill", 0.22, (70, 0, 40), 30, (0.92, 0.95, 1.0), shadows=False)

floor_me = bpy.data.meshes.new("Preview_Floor")
fb = bmesh.new()
bmesh.ops.create_grid(fb, x_segments=1, y_segments=1, size=60)
fb.to_mesh(floor_me)
fb.free()
floor = bpy.data.objects.new("Preview_Floor", floor_me)
floor.is_shadow_catcher = True
scene.collection.objects.link(floor)


def simple_mat(name, c):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*c, 1)
    b.inputs["Roughness"].default_value = 0.8
    return m


# 5-stud Roblox player stand-in (grey capsule, 1.8 wide) + labels, only for the scale renders
cap_me = bpy.data.meshes.new("Preview_PlayerStandIn")
cb = bmesh.new()
bmesh.ops.create_uvsphere(cb, u_segments=24, v_segments=16, radius=0.9)
for v in cb.verts:
    if v.co.z > 0:
        v.co.z += 3.2
    v.co.z += 0.9
cb.to_mesh(cap_me)
cb.free()
for poly in cap_me.polygons:
    poly.use_smooth = True
cap_me.materials.append(simple_mat("StandInGrey", (0.36, 0.37, 0.39)))
capsule = bpy.data.objects.new("Preview_PlayerStandIn", cap_me)
scene.collection.objects.link(capsule)
label_mat = simple_mat("LabelInk", (0.05, 0.05, 0.06))


def label(text, loc, size, yaw):
    cu = bpy.data.curves.new("Label", "FONT")
    cu.body, cu.size, cu.align_x, cu.extrude = text, size, "CENTER", 0.004
    cu.materials.append(label_mat)
    ob = bpy.data.objects.new("Preview_Label", cu)
    ob.location, ob.rotation_euler = loc, (math.radians(90), 0, yaw)
    scene.collection.objects.link(ob)
    return ob


cam = bpy.data.objects.new("PreviewCam", bpy.data.cameras.new("PreviewCam"))
scene.collection.objects.link(cam)
scene.camera = cam
BG = np.array((0.86, 0.865, 0.875))


def composite(path):
    img = bpy.data.images.load(str(path), check_existing=False)
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    a = a.reshape(-1, 4)
    al = a[:, 3:4]
    rgb_ = a[:, :3] * al + BG * (1 - al)
    outp = np.concatenate([rgb_, np.ones_like(al)], axis=1).astype(np.float32)
    bpy.data.images.remove(img)
    o = bpy.data.images.new("comp", w, h, alpha=False)
    o.pixels.foreach_set(outp.ravel())
    o.filepath_raw, o.file_format = str(path), "PNG"
    o.save()
    bpy.data.images.remove(o)


def shoot(filename, loc, target, lens=85, ortho=None, res=(1200, 1200), extras=(), feather=False, chicken=True):
    for ob in scene.objects:
        if ob.name.startswith("Preview_") and ob is not floor:
            ob.hide_render = ob not in extras
    for ob in rig.values():
        ob.hide_render = not chicken
    feather_obj.hide_render = not feather
    cam.data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cam.data.ortho_scale = ortho
    else:
        cam.data.lens = lens
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.resolution_x, scene.render.resolution_y = res
    path = PREV_DIR / filename
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    composite(path)
    log("rendered", filename)


def around(target, direction, dist):
    return Vector(target) + Vector(direction).normalized() * dist


tgt = (0, -0.12, 1.28)
shoot("front.png", around(tgt, (0, -1, 0.10), 11.5), tgt)
shoot("side.png", around(tgt, (1, 0, 0.10), 12.5), tgt)
shoot("three-quarter.png", around(tgt, (-0.62, -0.78, 0.40), 12.0), tgt)
shoot("back-three-quarter.png", around(tgt, (0.7, 0.7, 0.45), 12.0), tgt)

# true scale: orthographic, chicken at the origin, 5-stud capsule beside it
capsule.location = (3.0, 0.4, 0.0)
view = Vector((-0.30, -1.0, 0.16)).normalized()
yaw = math.atan2(view.x, -view.y)
chick_h = report["overall"]["height_studs"]
extras = (capsule,
          label("5-stud Roblox player stand-in", (3.0, 0.4, 5.35), 0.30, yaw),
          label(f"derp chicken {chick_h:.2f} studs", (0.0, -0.1, 2.95), 0.30, yaw))
shoot("scale-vs-5stud-player.png", Vector((1.5, 0.1, 2.6)) + view * 40, (1.5, 0.1, 2.6), ortho=7.6,
      res=(1400, 1200), extras=extras)

# the loose feather, true size, lying on the ground by the chicken's feet (moved for the preview only)
rest = feather_obj.matrix_world.copy()
feather_obj.location = (-0.95, -1.05, 0.03)
feather_obj.rotation_euler = rad((0, 0, 38))
ft = (-0.35, -0.55, 0.85)
shoot("feather-next-to-chicken.png", around(ft, (-0.55, -0.85, 0.62), 9.5), ft, feather=True)
# close-up of the feather alone (chicken hidden), tilted so both the top and the rim read
feather_obj.location = (0.0, 0.0, 0.16)
feather_obj.rotation_euler = rad((0, -24, 30))
shoot("feather-closeup.png", around((0, 0, 0.16), (-0.45, -0.75, 0.75), 2.3), (0, 0, 0.14), feather=True,
      chicken=False, res=(1000, 1000))
feather_obj.matrix_world = rest

# gameplay-style camera: high angle, 70 deg vertical FOV (Roblox default), ~18 studs away, 16:9
capsule.location = (2.6, 2.2, 0.0)
cam.data.sensor_fit = "VERTICAL"
cam.data.sensor_height = 24.0
gl_view = Vector((0.25, -0.8, 1.0)).normalized()
g_yaw = math.atan2(gl_view.x, -gl_view.y)
extras = (capsule, label("5-stud player stand-in", (3.1, 0.75, 0.02), 0.35, g_yaw))
extras[1].rotation_euler = (0, 0, g_yaw)     # lie flat on the ground in front of the capsule
shoot("gameplay-view.png", Vector((1.2, 1.0, 1.0)) + gl_view * 18.0, (1.2, 1.0, 1.0),
      lens=12.0 / math.tan(math.radians(35)), res=(1600, 900), extras=extras)
log("done")
