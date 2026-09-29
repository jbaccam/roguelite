"""Phoenix armor set v2 (Godly), 2026-09-29: the flashiest set in the game, fitted to the normalized R15 body.

Run (background Blender 5.2, never the user's open scene):
  blender -b --factory-startup --threads 4 --python build_phoenix.py
Env:
  QUICK=1      preview colours only: no bake, no exports (fast shape passes; renders previews/quick-*.png)
  VIEWS=a,b    render only these preview names (default: all)
  NOPOSE=1     skip the numeric pose check

v2 design (see README.md): rich brown-shaded gold is the main metal, with crimson/orange enamel inlays
(painted cloisonne flames), engraved sun rays, feather-scallop relief and filigree rims, ruby accents and
only a little ivory. Thick flame feathers (crimson root -> orange -> gold -> hot-yellow tip, painted vane
stripes) layered 2-3 deep everywhere. A sculpted phoenix helm (big hooked beak, heavy brows, glowing eyes,
cheek plumes, a three-layer crest about 1.5 studs tall), big lifted V wings as their own mesh
(Phoenix_Chest_Wings), three-tier pauldron mantles with sun-disc caps and flame crests, a radiant sun core,
feather tassets and a phoenix tail, talon boots. The only set with VFX: two Neon colours (orange glow,
hot-yellow cores), a generous particle/light list in studio-install-data.json and two painted particle
textures in textures/vfx/.

Self-contained: the shared pipeline (proxy loading, charts, shell, horn, loft, gem, painterly bake,
export, previews, pose check, contact sheet) is copied from build_dragon_scale.py, not imported.
Blender axes: +z up, -y = the character's front, +x = the character's LEFT. Studio = (-x, z, y).
"""
import bpy, bmesh, math, json, os, random, time
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from pathlib import Path

T0 = time.time()
ROOT = Path(__file__).resolve().parent
SET = "phoenix"
PREFIX = "Phoenix"
QUICK = os.environ.get("QUICK") == "1"
VIEWS = set(os.environ["VIEWS"].split(",")) if os.environ.get("VIEWS") else None
NOPOSE = os.environ.get("NOPOSE") == "1"
BAKE_SIZE = 1024          # Roblox caps textures at 1024
BAKE_WORK = 1024          # baked directly at the final size (cheaper than Dragon Scale)
for d in ("exports/fbx", "exports/glb", "textures", "previews"):
    (ROOT / d).mkdir(parents=True, exist_ok=True)
RNG = random.Random(11)


def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)


# ---------------------------------------------------------------------------
# The measured body (Studio part-local coordinates in r15-proxy/*.obj)
# ---------------------------------------------------------------------------
PARTS = ["LowerTorso", "UpperTorso", "LeftUpperArm", "LeftLowerArm", "LeftHand", "RightUpperArm",
         "RightLowerArm", "RightHand", "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "RightUpperLeg",
         "RightLowerLeg", "RightFoot"]
HEAD_NECK_ATT = Vector((0, -0.586, 0))             # Head.NeckRigAttachment (Studio, measured)


def s2b(v):
    return Vector((-v[0], v[2], v[1]))


def load_obj(name):
    verts, faces, atts = [], [], {}
    for line in open(ROOT.parent / "r15-proxy" / f"{name}.obj"):
        p = line.split()
        if line.startswith("# att"):
            atts[p[2]] = Vector((float(p[3]), float(p[4]), float(p[5])))
        elif line.startswith("v "):
            verts.append((float(p[1]), float(p[2]), float(p[3])))
        elif line.startswith("f "):
            faces.append([int(i) - 1 for i in p[1:]])
    return {"verts": verts, "faces": faces, "atts": atts}


BODY = {n: load_obj(n) for n in PARTS}
REST = {"LowerTorso": Vector((0, -1, 0)) - BODY["LowerTorso"]["atts"]["RootRigAttachment"]}
JOINT = {}      # child part -> (parent part, attachment name)


def link(parent, child, att):
    REST[child] = REST[parent] + BODY[parent]["atts"][att] - BODY[child]["atts"][att]
    JOINT[child] = (parent, att)


link("LowerTorso", "UpperTorso", "WaistRigAttachment")
for _s in ("Left", "Right"):
    link("UpperTorso", _s + "UpperArm", _s + "ShoulderRigAttachment")
    link(_s + "UpperArm", _s + "LowerArm", _s + "ElbowRigAttachment")
    link(_s + "LowerArm", _s + "Hand", _s + "WristRigAttachment")
    link("LowerTorso", _s + "UpperLeg", _s + "HipRigAttachment")
    link(_s + "UpperLeg", _s + "LowerLeg", _s + "KneeRigAttachment")
    link(_s + "LowerLeg", _s + "Foot", _s + "AnkleRigAttachment")
REST["Head"] = REST["UpperTorso"] + BODY["UpperTorso"]["atts"]["NeckRigAttachment"] - HEAD_NECK_ATT
JOINT["Head"] = ("UpperTorso", "NeckRigAttachment")
HRP_HEIGHT = 3.0                                    # HipHeight 2 + half the root part


def part_pos(name):
    """Blender world position of a body part's centre at rest (feet on z = 0)."""
    return s2b(REST[name]) + Vector((0, 0, HRP_HEIGHT))


def joint_world(child):
    """World position of the joint that moves `child` (the parent's rig attachment)."""
    parent, att = JOINT[child]
    return part_pos(parent) + s2b(BODY[parent]["atts"][att])


# ---------------------------------------------------------------------------
# Materials (bake inputs). Index order is shared by every component.
# ---------------------------------------------------------------------------
MAT_NAMES = ["Ivory", "Feather", "Gold", "Bronze", "Suit", "Dark", "Crimson", "Ruby"]
IVY, FTH, GLD, BRZ, SUIT, DRK, CRM, RBY = range(8)
OBS, SCL = GLD, FTH                                  # names the shared helpers use as defaults
PREVIEW_RGB = {IVY: (236, 226, 206), FTH: (210, 70, 36), GLD: (222, 162, 58), BRZ: (130, 80, 36),
               SUIT: (74, 20, 30), DRK: (26, 12, 14), CRM: (170, 30, 38), RBY: (200, 20, 50)}
GLOW = (255, 150, 40)                                # Neon (Studio Color), warm orange-gold
HOT = (255, 214, 96)                                 # Neon hot yellow: eyes, the sun core, flame cores
# motif kinds painted as relief by the bake (stored per face corner in the "Motif" attribute)
MK_PLATE, MK_FLAME, MK_RADIAL, MK_SCALLOP, MK_FEATHER = 1, 2, 3, 4, 5


def lin(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgba(c, a=1.0):
    return (lin(c[0]), lin(c[1]), lin(c[2]), a)


# ---------------------------------------------------------------------------
# Mesh components. Each component is its own bmesh with its own finishing (bevel width and
# segments, shading); components are finished separately and joined into one mesh per body part.
# Every loop carries a "Detail" colour attribute read by the bake:
#   R = along the element (0 root/base -> 1 tip/free edge)
#   G = across (0..1, 0.5 = keel / centre)
#   B = per-element random (colour jitter)
#   A = zone (scales: 1 top, 0.6 lip, 0.3 rim; horns: ring flag; plates 0)
# ---------------------------------------------------------------------------
class Comp:
    def __init__(self, bevel=0.0, segs=2, angle=30.0, shade="harden", profile=0.5, facet=0.0, mk=None):
        self.bm = bmesh.new()
        self.lay = self.bm.loops.layers.float_color.new("Detail")
        self.lay2 = self.bm.loops.layers.float_color.new("Motif")
        self.vd, self.md = {}, {}
        self.mk = mk                      # default motif kind: a number or {material: kind}
        self.bevel, self.segs, self.angle, self.shade, self.profile, self.facet = bevel, segs, angle, shade, profile, facet

    def v(self, co, d=None, m=None):
        vert = self.bm.verts.new(co)
        if d is not None:
            self.vd[vert] = d
        if m is not None:
            self.md[vert] = m
        return vert

    def f(self, verts, mat, d=None, mk=None):
        try:
            face = self.bm.faces.new(verts)
        except ValueError:
            return None
        face.material_index = mat
        kind = mk if mk is not None else self.mk
        if isinstance(kind, dict):
            kind = kind.get(mat, 0)
        kind = float(kind or 0) * 0.1
        for loop in face.loops:
            loop[self.lay] = d if d is not None else self.vd.get(loop.vert, (0.0, 0.0, 0.0, 0.0))
            mu, mv = self.md.get(loop.vert, (0.0, 0.0))
            loop[self.lay2] = (mu, mv, kind, 1.0)
        return face

    def mirrored(self):
        m = Comp(self.bevel, self.segs, self.angle, self.shade, self.profile, self.facet, self.mk)
        m.bm.free()
        m.bm = self.bm.copy()
        m.lay = m.bm.loops.layers.float_color["Detail"]
        m.lay2 = m.bm.loops.layers.float_color["Motif"]
        bmesh.ops.scale(m.bm, vec=Vector((-1, 1, 1)), verts=m.bm.verts)
        bmesh.ops.reverse_faces(m.bm, faces=m.bm.faces)
        return m


class GlowSet:
    """The two Neon meshes of a piece: o = orange glow, h = hot-yellow cores."""

    def __init__(self, o=None, h=None):
        self.o = o or Comp(shade="flat")
        self.h = h or Comp(shade="flat")

    def mirrored(self):
        return GlowSet(self.o.mirrored(), self.h.mirrored())


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def orient_faces(faces, expect_dir, probe_face):
    """Flip a face group if its probe face points away from expect_dir."""
    if probe_face is not None and probe_face.normal.dot(expect_dir) < 0:
        for f in faces:
            if f is not None:
                f.normal_flip()


# ---------------------------------------------------------------------------
# Charts: (u, v) -> (point on the body offset by the clearance, outward normal), part-local.
# ---------------------------------------------------------------------------
CL = 0.028          # gap between the body and the inside of an armour layer
SUIT_CL = 0.012     # the undersuit hugs the body under the plates


def torso_chart(side, hx=1.0, hy=0.5, hz=0.8, rc=0.12, clear=CL, zbot=None):
    """Front (side -1) or back (+1) face of a box torso; v runs up the face and over the top edge
    (fillet rc, small enough that the proxy's 0.07 chamfer stays inside), so a plate can wrap
    onto the top. u = x."""
    R = rc + clear
    s_c = hz - rc
    arc = math.pi / 2 * R

    def f(u, v):
        if v <= s_c:
            return Vector((u, side * (hy + clear), v)), Vector((0, side, 0))
        if v <= s_c + arc:
            a = (v - s_c) / R
            return (Vector((u, side * ((hy - rc) + R * math.cos(a)), (hz - rc) + R * math.sin(a))),
                    Vector((0, side * math.cos(a), math.sin(a))))
        d = v - s_c - arc
        return Vector((u, side * (hy - rc - d), hz + clear)), Vector((0, 0, 1))
    f.top = s_c + arc          # v where the top face starts
    return f


def limb_chart(hx=0.5, hy=0.5, r=0.13, clear=CL):
    """Around a limb's box section, front -> outer (+x) -> back, skipping the inner face.
    u = arc length (0 at the front-inner edge), v = z. Returns f and the key u stations."""
    R = r + clear
    L_front = 2 * hx - r
    arc = math.pi / 2 * R
    L_outer = 2 * hy - 2 * r
    s1, s2, s3, s4 = L_front, L_front + arc, L_front + arc + L_outer, L_front + 2 * arc + L_outer
    total = s4 + 2 * hx - r

    def f(u, v):
        if u <= s1:
            return Vector((-hx + u, -(hy + clear), v)), Vector((0, -1, 0))
        if u <= s2:
            a = -math.pi / 2 + (u - s1) / R
            c = Vector((hx - r, -(hy - r), 0))
            n = Vector((math.cos(a), math.sin(a), 0))
            return c + n * R + Vector((0, 0, v)), n
        if u <= s3:
            return Vector((hx + clear, -(hy - r) + (u - s2), v)), Vector((1, 0, 0))
        if u <= s4:
            a = (u - s3) / R
            c = Vector((hx - r, hy - r, 0))
            n = Vector((math.cos(a), math.sin(a), 0))
            return c + n * R + Vector((0, 0, v)), n
        return Vector((hx - r - (u - s4), hy + clear, v)), Vector((0, 1, 0))
    f.stations = {"front_in": 0.0, "front_mid": hx, "corner_fo": (s1 + s2) / 2, "outer_mid": (s2 + s3) / 2,
                  "corner_ob": (s3 + s4) / 2, "back_mid": s4 + hx - r, "back_in": total, "total": total,
                  "outer0": s2, "outer1": s3}
    return f


# ---------------------------------------------------------------------------
# Plates: a thick shell from a grid of chart coordinates G[j][i] = (u, v).
#   thick(j, i, u, v)  -> outward thickness at that vertex (bulges, ridges and raised trims)
#   lift(j, i, u, v)   -> inner offset from the chart (layered plates sit on the ones below)
#   mat_fn(j, i)       -> material of outer face j,i ; rim_mat -> material of the side walls
#   flush              -> the inner face lies on the body: drop it (nobody can see it)
# Detail: R = row fraction (0 top/root row -> 1 bottom/free row), G = column fraction.
# ---------------------------------------------------------------------------
def shell(c, chart, G, thick, *, lift=None, wrap=False, mat=OBS, mat_fn=None, rim_mat=None,
          flush=True, rnd=None, det_fn=None, mk=None, muv=None, mscale=(1.0, 1.0)):
    """mk: motif kind for the outer faces (number, {material: kind} or fn(j, i, material)); the motif
    coordinates are the chart (u, v) in studs (muv(j, i, u, v) overrides)."""
    rows, cols = len(G), len(G[0])
    rnd = RNG.random() if rnd is None else rnd
    rim_mat = mat if rim_mat is None else rim_mat
    inner, outer = [], []
    for j in range(rows):
        ri, ro = [], []
        for i in range(cols):
            u, v = G[j][i]
            P, N = chart(u, v)
            lo = lift(j, i, u, v) if lift else 0.0
            t = thick(j, i, u, v) if callable(thick) else thick
            d = det_fn(j, i, u, v) if det_fn else (j / max(1, rows - 1), i / max(1, cols - 1), rnd, 0.0)
            m = muv(j, i, u, v) if muv else (u * mscale[0] + 4.0, v * mscale[1] + 4.0)
            ri.append(c.v(P + N * lo, d, m))
            ro.append(c.v(P + N * (lo + t), d, m))
        inner.append(ri)
        outer.append(ro)
    ucount = cols if wrap else cols - 1
    fo, fi, fr = [], [], []
    for j in range(rows - 1):
        for i in range(ucount):
            i2 = (i + 1) % cols
            m = mat_fn(j, i) if mat_fn else mat
            kv = mk(j, i, m) if callable(mk) else mk
            fo.append(c.f([outer[j][i], outer[j][i2], outer[j + 1][i2], outer[j + 1][i]], m, mk=kv))
            if not flush:
                fi.append(c.f([inner[j][i], inner[j + 1][i], inner[j + 1][i2], inner[j][i2]], DRK, mk=0))
    # rims (side walls): polished, no motif
    edges = []
    for i in range(ucount):
        i2 = (i + 1) % cols
        edges.append((inner[0][i2], inner[0][i], outer[0][i], outer[0][i2]))
        edges.append((inner[-1][i], inner[-1][i2], outer[-1][i2], outer[-1][i]))
    if not wrap:
        for j in range(rows - 1):
            edges.append((inner[j][0], inner[j + 1][0], outer[j + 1][0], outer[j][0]))
            edges.append((inner[j + 1][-1], inner[j][-1], outer[j][-1], outer[j + 1][-1]))
    for q in edges:
        fr.append(c.f(list(q), rim_mat, mk=0))
    # consistent outward winding: probe the middle outer face against the chart normal
    jm, im = (rows - 1) // 2, (ucount) // 2
    probe = fo[jm * ucount + im] if fo else None
    u, v = G[jm][im]
    _, N = chart(u, v)
    c.bm.normal_update()
    if probe is not None and probe.normal.dot(N) < 0:
        for f in fo + fi + fr:
            if f is not None:
                f.normal_flip()
    return outer


def resample(poly, n, closed=True):
    """Resample a 2D polyline (list of (u, v)) to n points evenly by length."""
    pts = [Vector(p) for p in poly]
    if closed:
        pts = pts + [pts[0]]
    seg = [(pts[k + 1] - pts[k]).length for k in range(len(pts) - 1)]
    total = sum(seg)
    out = []
    count = n if closed else n - 1
    for k in range(n):
        d = total * k / count
        acc = 0.0
        for s_i, L in enumerate(seg):
            if acc + L >= d - 1e-9 or s_i == len(seg) - 1:
                t = 0.0 if L < 1e-9 else (d - acc) / L
                out.append(pts[s_i].lerp(pts[s_i + 1], clamp(t)))
                break
            acc += L
    return out


def poly_area(poly):
    return 0.5 * sum(poly[k].x * poly[(k + 1) % len(poly)].y - poly[(k + 1) % len(poly)].x * poly[k].y
                     for k in range(len(poly)))


def inset(poly, dist):
    """Inward offset of a closed 2D polygon; dist may be a number or a per-vertex function."""
    n = len(poly)
    ccw = poly_area(poly) > 0
    out = []
    for k in range(n):
        p0, p1, p2 = poly[k - 1], poly[k], poly[(k + 1) % n]
        e1 = (p1 - p0).normalized()
        e2 = (p2 - p1).normalized()
        n1 = Vector((-e1.y, e1.x)) if ccw else Vector((e1.y, -e1.x))
        n2 = Vector((-e2.y, e2.x)) if ccw else Vector((e2.y, -e2.x))
        m = (n1 + n2)
        m = m.normalized() if m.length > 1e-6 else n1
        cosh = max(0.35, m.dot(n1))
        d = dist(k, p1) if callable(dist) else dist
        out.append(p1 + m * (d / cosh))
    return out


def point_in_poly(p, poly):
    inside = False
    n = len(poly)
    for k in range(n):
        a, b = poly[k], poly[(k + 1) % n]
        if (a.y > p.y) != (b.y > p.y):
            x = a.x + (p.y - a.y) * (b.x - a.x) / (b.y - a.y)
            if x > p.x:
                inside = not inside
    return inside


def dist_to_poly(p, poly):
    best = 1e9
    n = len(poly)
    for k in range(n):
        a, b = poly[k], poly[(k + 1) % n]
        ab = b - a
        t = clamp((p - a).dot(ab) / max(ab.length_squared, 1e-12))
        best = min(best, (a + ab * t - p).length)
    return best


def ring_grid(outer_poly, inner_poly, ts):
    """Rows of a ring plate: each row a closed loop between the inner (t=0) and outer (t=1)
    outlines, which have matching point counts."""
    return [[(lerp(i_.x, o_.x, t), lerp(i_.y, o_.y, t)) for i_, o_ in zip(inner_poly, outer_poly)] for t in ts]


# ---------------------------------------------------------------------------
# The hero scale: a thick kite shield with a bevelled lip, a raised keel and a pointed tip.
# Local: x across [-1, 1], z along the flow [-1 tip, +1 root]. The tip lifts off the surface
# (tilt), so each scale throws an undercut shadow onto the row below.
# ---------------------------------------------------------------------------
KITE = [(-0.52, 1.0), (-1.0, 0.36), (-0.60, -0.44), (0.0, -1.0), (0.60, -0.44), (1.0, 0.36), (0.52, 1.0)]
KITE_C = Vector((0.0, 0.05))


def hero_scale(c, P, N, D, w, h, *, thick=0.045, thick_root=0.018, keel=0.016, tilt=13.0, lip=0.12,
               bow=0.25, sink=0.006, mat=SCL, rnd=None, under=False, root_edge=False, lite=False):
    N = N.normalized()
    U = -(D - N * D.dot(N)).normalized()          # towards the root
    X = N.cross(U).normalized()
    st = math.sin(math.radians(tilt))
    ct = math.cos(math.radians(tilt))
    rnd = RNG.random() if rnd is None else rnd

    def W(x, n, z):
        lift = (1 - z) / 2 * h * st - sink
        return P + X * (x * w / 2) + U * (z * h / 2 * ct) + N * (n + lift - bow * 0.25 * w * x * x)

    def t_at(z):
        return thick_root + (thick - thick_root) * (1 - z) / 2

    def det(x, z, a):
        return ((1 - z) / 2, (x + 1) / 2, rnd, a)

    O = [c.v(W(x, t_at(z), z), det(x, z, 0.95 if lite else 0.6)) for x, z in KITE]
    B = [c.v(W(x, 0.0, z), det(x, z, 0.3)) for x, z in KITE]
    I = []
    if lite:
        I = O
    else:
        for x, z in KITE:
            q = KITE_C + (Vector((x, z)) - KITE_C) * (1 - lip)
            I.append(c.v(W(q.x, t_at(q.y) + 0.008, q.y), det(q.x, q.y, 1.0)))
    kz = (0.78, 0.05, -0.56)
    kh = (0.35, 1.0, 0.85)
    K = [c.v(W(0.0, t_at(z) + 0.008 + keel * k, z), det(0.0, z, 1.0)) for z, k in zip(kz, kh)]
    faces = []
    # top: left half 0-1-2-3, right half 6-5-4-3, keel K0-K1-K2
    faces.append(c.f([I[0], I[1], K[1], K[0]], mat))
    faces.append(c.f([I[1], I[2], K[2], K[1]], mat))
    faces.append(c.f([I[2], I[3], K[2]], mat))
    faces.append(c.f([K[0], K[1], I[5], I[6]], mat))
    faces.append(c.f([K[1], K[2], I[4], I[5]], mat))
    faces.append(c.f([K[2], I[3], I[4]], mat))
    faces.append(c.f([I[6], I[0], K[0]], mat))
    n = len(KITE)
    for k in range(n - (0 if root_edge else 1)):
        k2 = (k + 1) % n
        if not lite:
            faces.append(c.f([O[k], O[k2], I[k2], I[k]], mat))      # bevelled lip
        faces.append(c.f([B[k], B[k2], O[k2], O[k]], mat))          # thickness
    if under:
        faces.append(c.f(B[::-1], DRK))
    c.bm.normal_update()
    probe = faces[1]
    if probe is not None and probe.normal.dot(N) < 0:
        for f in faces:
            if f is not None:
                f.normal_flip()
    return faces


def scale_field(c, surf, origin, flow, across, rows, cols, du, dv, size, *, keep=None, jitter=0.0,
                stagger=True, **kw):
    """Staggered rows of hero scales on a surface.
    surf(u, v) -> (P, N) ; origin/flow/across are 2D chart vectors ; size(u, v, r) -> (w, h).
    Rows advance along `flow` (root row first), columns along `across`."""
    flow = Vector(flow).normalized()
    across = Vector(across).normalized()
    placed = 0
    for r in range(rows):
        off = 0.5 if (stagger and r % 2) else 0.0
        for k in range(-cols, cols + 1):
            p = Vector(origin) + flow * (r * dv) + across * ((k + off) * du)
            if jitter:
                p += Vector((RNG.uniform(-1, 1), RNG.uniform(-1, 1))) * jitter
            if keep and not keep(p, r):
                continue
            w, h = size(p.x, p.y, r)
            P, N = surf(p.x, p.y)
            P2, _ = surf(p.x + flow.x * 0.02, p.y + flow.y * 0.02)
            hero_scale(c, P, N, P2 - P, w, h, **kw)
            placed += 1
    return placed


# ---------------------------------------------------------------------------
# Horns, spikes, claws and fangs: a tapered faceted tube along a curve. R = base->tip.
# rings: every other station bulges (segmented horn), ring stations get A = 1.
# ---------------------------------------------------------------------------
def bezier(p0, p1, p2, p3, t):
    a = 1 - t
    return p0 * a ** 3 + p1 * 3 * a * a * t + p2 * 3 * a * t * t + p3 * t ** 3


def horn(c, pts, r0, *, sides=7, taper=1.0, flat=1.0, rings=0.0, mat=IVY, up=None, rnd=None, r_tip=0.0,
         cap=True):
    """pts: centreline points (base first). r0: base radius. flat: squash the section across
    `up` (blades)."""
    rnd = RNG.random() if rnd is None else rnd
    n = len(pts)
    rings_v = []
    prev = None
    for k, p in enumerate(pts):
        t = k / (n - 1)
        tan = (pts[min(k + 1, n - 1)] - pts[max(k - 1, 0)]).normalized()
        if prev is None:
            ref = up if up is not None else (Vector((0, 0, 1)) if abs(tan.z) < 0.9 else Vector((1, 0, 0)))
            nrm = (ref - tan * ref.dot(tan)).normalized()
        else:
            nrm = (prev - tan * prev.dot(tan)).normalized()
        prev = nrm
        bi = tan.cross(nrm).normalized()
        r = r_tip + (r0 - r_tip) * (1 - t) ** taper
        if rings and 0 < k < n - 1 and k % 2 == 1:
            r *= 1 + rings
        if k == n - 1 and r_tip <= 1e-6:
            rings_v.append([c.v(p, (1.0, 0.5, rnd, 0.0))])
            continue
        ring = []
        for s in range(sides):
            a = 2 * math.pi * s / sides
            q = p + nrm * (math.cos(a) * r) + bi * (math.sin(a) * r * flat)
            ring.append(c.v(q, (t, s / sides, rnd, 1.0 if (rings and k % 2 == 1) else 0.0)))
        rings_v.append(ring)
    faces = []
    for k in range(n - 1):
        A, Bn = rings_v[k], rings_v[k + 1]
        for s in range(sides):
            s2 = (s + 1) % sides
            if len(Bn) == 1:
                faces.append(c.f([A[s], A[s2], Bn[0]], mat))
            else:
                faces.append(c.f([A[s], A[s2], Bn[s2], Bn[s]], mat))
    if cap:
        faces.append(c.f(rings_v[0][::-1], mat))
    if len(rings_v[-1]) > 1:
        faces.append(c.f(rings_v[-1], mat))
    c.bm.normal_update()
    # outward check: first side face normal vs radial direction
    f0 = faces[0]
    if f0 is not None:
        radial = (f0.calc_center_median() - pts[0])
        if f0.normal.dot(radial) < 0:
            for f in faces:
                if f is not None:
                    f.normal_flip()
    return faces


def curve_pts(p0, p1, p2, p3, n):
    return [bezier(p0, p1, p2, p3, k / (n - 1)) for k in range(n)]


def loft(c, rings, mat, cap0=True, cap1=True, closed=True, det=None, outward=None):
    """Quads between consecutive rings of 3D points (same count)."""
    V = []
    for k, ring in enumerate(rings):
        V.append([c.v(p, det(k, s) if det else None) for s, p in enumerate(ring)])
    faces = []
    m = len(rings[0])
    for k in range(len(V) - 1):
        for s in range(m if closed else m - 1):
            s2 = (s + 1) % m
            faces.append(c.f([V[k][s], V[k][s2], V[k + 1][s2], V[k + 1][s]], mat))
    if cap0:
        faces.append(c.f(V[0][::-1], mat))
    if cap1:
        faces.append(c.f(V[-1], mat))
    c.bm.normal_update()
    if outward is not None:
        centre = sum((p for ring in rings for p in ring), Vector()) / (len(rings) * m)
        f0 = faces[0]
        if f0 is not None and f0.normal.dot(f0.calc_center_median() - centre) < 0:
            for f in faces:
                if f is not None:
                    f.normal_flip()
    return faces, V


def gem(c, center, nrm, up, w, h, depth, sides=8, mat=0):
    """Faceted cabochon (glow component: material 0)."""
    n = nrm.normalized()
    up = (up - n * up.dot(n)).normalized()
    rt = up.cross(n).normalized()
    ring = [c.v(center + rt * (math.cos(a) * w / 2) + up * (math.sin(a) * h / 2))
            for a in [2 * math.pi * s / sides for s in range(sides)]]
    mid = [c.v(center + n * depth * 0.72 + rt * (math.cos(a) * w * 0.3) + up * (math.sin(a) * h * 0.3))
           for a in [2 * math.pi * (s + 0.5) / sides for s in range(sides)]]
    top = c.v(center + n * depth)
    faces = []
    for s in range(sides):
        s2 = (s + 1) % sides
        faces.append(c.f([ring[s], ring[s2], mid[s]], mat))
        faces.append(c.f([mid[s], ring[s2], mid[s2]], mat))
        faces.append(c.f([mid[s], mid[s2], top], mat))
    faces.append(c.f(ring[::-1], mat))
    c.bm.normal_update()
    if faces[2] is not None and faces[2].normal.dot(n) < 0:
        for f in faces:
            if f is not None:
                f.normal_flip()
    return faces


def ribbon(c, pts, nrms, widths, *, height=0.012, mat=0):
    """Glowing seam/crack: a tent-shaped strip lying on a surface (points already on it)."""
    L, Cn, R = [], [], []
    for k, (p, n) in enumerate(zip(pts, nrms)):
        tan = (pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]).normalized()
        side = n.cross(tan).normalized()
        w = widths[k]
        L.append(c.v(p + side * w - n * 0.004))
        R.append(c.v(p - side * w - n * 0.004))
        Cn.append(c.v(p + n * height * (w / max(widths))))
    faces = []
    for k in range(len(pts) - 1):
        faces.append(c.f([L[k], L[k + 1], Cn[k + 1], Cn[k]], mat))
        faces.append(c.f([Cn[k], Cn[k + 1], R[k + 1], R[k]], mat))
    c.bm.normal_update()
    n0 = nrms[len(nrms) // 2]
    if faces and faces[len(faces) // 2] is not None and faces[len(faces) // 2].normal.dot(n0) < 0:
        for f in faces:
            if f is not None:
                f.normal_flip()
    return faces


def project(bvh, P, N, back=0.6):
    """Ray from outside along -N onto the geometry in bvh; returns (point, normal) or None."""
    hit = bvh.ray_cast(P + N * back, -N, back * 2.5)
    if hit[0] is None:
        return None
    n = hit[1] if hit[1].dot(N) > 0 else -hit[1]
    return hit[0], n


def crack(glow, bvh, chart, path_uv, w0, w1=0.004, lift_n=0.0, height=0.011, mat=0):
    """A thin raised strip (glow seam or gold filigree) along chart path_uv, projected onto bvh."""
    pts, nrms, ws = [], [], []
    n = len(path_uv)
    for k, (u, v) in enumerate(path_uv):
        P, N = chart(u, v)
        hit = project(bvh, P + N * 0.25, N)
        if hit is None:
            continue
        pts.append(hit[0] + hit[1] * (0.002 + lift_n))
        nrms.append(hit[1])
        ws.append(lerp(w0, w1, k / max(1, n - 1)))
    if len(pts) >= 2:
        ribbon(glow, pts, nrms, ws, height=height, mat=mat)


def subdiv_path(path, per=3):
    out = []
    for k in range(len(path) - 1):
        a, b = Vector(path[k]), Vector(path[k + 1])
        for s in range(per):
            out.append(a.lerp(b, s / per))
    out.append(Vector(path[-1]))
    return [(p.x, p.y) for p in out]


def rivet(c, P, N, r=0.028, h=0.018, sides=6, mat=GLD):
    N = N.normalized()
    a = Vector((0, 0, 1)) if abs(N.z) < 0.9 else Vector((1, 0, 0))
    X = N.cross(a).normalized()
    Y = N.cross(X)
    ring0 = [P + (X * math.cos(2 * math.pi * s / sides) + Y * math.sin(2 * math.pi * s / sides)) * r - N * 0.004
             for s in range(sides)]
    ring1 = [P + (X * math.cos(2 * math.pi * s / sides) + Y * math.sin(2 * math.pi * s / sides)) * r * 0.62 + N * h * 0.8
             for s in range(sides)]
    faces, V = loft(c, [ring0, ring1], mat, cap0=False, cap1=False)
    top = c.v(P + N * h)
    for s in range(sides):
        faces.append(c.f([V[1][s], V[1][(s + 1) % sides], top], mat))
    c.bm.normal_update()
    if faces[0] is not None and faces[0].normal.dot(faces[0].calc_center_median() - P) < 0:
        for f in faces:
            if f is not None:
                f.normal_flip()


# ---------------------------------------------------------------------------
# PIECES. Each builder returns (list of Comp for the armour mesh, Comp for the glow mesh, embers)
# in the part's local space. Left-side builders are mirrored for the right side.
# ---------------------------------------------------------------------------
UP = Vector((0, 0, 1))


def grid(us, vs):
    return [[(u, v) for u in us] for v in vs]


def limb_cols(ch):
    """Column stations around a limb chart that follow its rounded corners."""
    st = ch.stations
    s1 = st["front_mid"] + (st["corner_fo"] - st["front_mid"]) * 0.0
    arc0 = [st["outer0"] - (st["outer0"] - st["corner_fo"]) * 2 + (st["outer0"] - st["corner_fo"]) * 2 * k / 3 for k in range(4)]
    arc1 = [st["outer1"] + (st["corner_ob"] - st["outer1"]) * 2 * k / 3 for k in range(4)]
    return [0.012, st["front_mid"] * 0.5, st["front_mid"]] + arc0 + [st["outer_mid"]] + arc1 +         [st["back_mid"], (st["back_mid"] + st["back_in"]) / 2, st["back_in"] - 0.012]


def undersuit_box(comps, chart, us, vs, rnd=0.5):
    """Dark scale-mail undersuit layer (flush, single surface) that shows in every gap."""
    c = Comp(bevel=0.0, shade="smooth")
    shell(c, chart, grid(us, vs), 0.004, mat=SUIT, rnd=rnd)
    comps.append(c)


def bump(x, y, cx, cy, rx, ry):
    d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
    return max(0.0, 1.0 - d) ** 1.5



# ----- shared charts and plate shapes (from the Dragon Scale kit) -----
PEC_O = [(0.05, 0.64), (0.28, 0.76), (0.60, 0.80), (0.76, 1.04), (0.955, 1.04), (0.965, 0.60),
         (0.935, 0.30), (0.82, 0.05), (0.56, -0.12), (0.28, -0.24), (0.05, -0.34)]
PEC_RECESS = 0.085


def pec_height(x, v):
    """Outer height of the breastplate above the chart (bulged pec, rising to the sternum)."""
    b = 0.13 * bump(x, v, 0.50, 0.30, 0.62, 0.62)
    ridge = 0.06 * clamp(1 - x / 0.30) ** 1.4
    top = smooth((v - 0.62) / 0.3)                      # flatten as it wraps over the shoulder
    return 0.058 + (b + ridge) * (1 - 0.8 * top)


def plate_lift(v):
    """The breastplate's lower edge rides over the top abdominal lame."""
    return 0.075 * smooth((0.12 - v) / 0.25)


LAMES = [  # (half width, top centre v, top side rise, bottom centre v, bottom side rise)
    (0.78, -0.22, 0.34, -0.42, 0.30),
    (0.71, -0.37, 0.26, -0.56, 0.22),
    (0.64, -0.51, 0.19, -0.69, 0.15),
    (0.57, -0.635, 0.12, -0.795, 0.08),
]
LAME_T = 0.05
LAME_R = 0.035       # centre ridge
LAME_GAP = 0.012


def lame_lift_bottom():
    return LAME_T + LAME_R + LAME_GAP



def lt_chart(side, clear=CL):
    def f(u, v):
        return Vector((u, side * (0.5 + clear), v)), Vector((0, side, 0))
    return f


def head_profile(s, clear=0.0):
    """R15 head (rounded cylinder r 0.6, half-height 0.6, top corner r 0.25) as (radius, z) along
    arc length s from the bottom edge."""
    R, rc = 0.6 + clear, 0.25 + clear
    zc = 0.6 - 0.25
    L1 = zc + 0.6
    L2 = math.pi / 2 * rc
    if s <= L1:
        return R, -0.6 + s
    if s <= L1 + L2:
        a = (s - L1) / rc
        return (R - rc) + rc * math.cos(a), zc + rc * math.sin(a)
    t = min(s - L1 - L2, R - rc)
    return (R - rc) - t, 0.6 + clear


HEAD_S_MAX = (0.35 + 0.6) + math.pi / 2 * 0.25 + 0.35


def head_chart(clear=CL):
    L1 = 0.35 + 0.6
    rc = 0.25 + clear

    def f(th, s):
        r, z = head_profile(s, clear)
        st, ct = math.sin(th), math.cos(th)
        if s <= L1:
            n = Vector((st, -ct, 0))
        elif s <= L1 + math.pi / 2 * rc:
            a = (s - L1) / rc
            n = Vector((math.cos(a) * st, -math.cos(a) * ct, math.sin(a)))
        else:
            n = Vector((0, 0, 1))
        return Vector((r * st, -r * ct, z)), n
    return f


def profile_chart(poly, clear=CL):
    """Chart over a 2D profile in the x-z plane (list of (x, z)), extruded along y.
    u = arc length along the profile, v = y."""
    pts = [Vector(p) for p in poly]
    acc = [0.0]
    for k in range(1, len(pts)):
        acc.append(acc[-1] + (pts[k] - pts[k - 1]).length)
    nrm = []
    for k in range(len(pts)):
        t = pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]
        n = Vector((-t.y, t.x)).normalized()        # outward normal of the tangent (x, z)
        nrm.append(n)

    def f(u, v):
        u = clamp(u, 0.0, acc[-1])
        for k in range(len(pts) - 1):
            if acc[k + 1] >= u:
                t = (u - acc[k]) / max(acc[k + 1] - acc[k], 1e-9)
                p = pts[k].lerp(pts[k + 1], t)
                n = nrm[k].lerp(nrm[k + 1], t).normalized()
                return Vector((p.x + n.x * clear, v, p.y + n.y * clear)), Vector((n.x, 0, n.y))
        p, n = pts[-1], nrm[-1]
        return Vector((p.x + n.x * clear, v, p.y + n.y * clear)), Vector((n.x, 0, n.y))
    f.length = acc[-1]
    return f


# ----- Pauldrons (left upper arm; outer = +x) --------------------------------------
PD_O = Vector((0.0, 0.0, 0.03))       # dome centre (arm-local)
PD_R = Vector((0.82, 0.66, 0.74))       # superquadric semi-axes
PD_N = 2.7
PD_SU, PD_TV = 1.30, 0.47               # chart units -> roughly studs


def pd_raw(s, t):
    """Point and normal on the pauldron dome. s: 0 inner top edge -> 1 outer rim; t: -1.4 front ->
    1.4 back. The dome encloses the arm's rounded top corners with ~0.03 to spare."""
    # path over a unit cube: along the top from x=-0.62 to the outer edge, then down the outer face
    top_len, side_len = 1.62, 1.35
    d = s * (top_len + side_len)
    if d <= top_len:
        q = Vector((-0.62 + d, t, 1.0))
    else:
        q = Vector((1.0, t, 1.0 - (d - top_len)))
    dirv = q.normalized()
    k = (abs(dirv.x / PD_R.x) ** PD_N + abs(dirv.y / PD_R.y) ** PD_N + abs(dirv.z / PD_R.z) ** PD_N) ** (-1 / PD_N)
    p = dirv * k
    g = Vector((math.copysign(abs(p.x / PD_R.x) ** (PD_N - 1) / PD_R.x, p.x),
                math.copysign(abs(p.y / PD_R.y) ** (PD_N - 1) / PD_R.y, p.y),
                math.copysign(abs(p.z / PD_R.z) ** (PD_N - 1) / PD_R.z, p.z)))
    return PD_O + p, g.normalized()


def pd_chart(u, v):
    return pd_raw(u / PD_SU, v / PD_TV)



# ---------------------------------------------------------------------------
# THE PHOENIX FEATHER (v2). A thick flame-shaped blade: a lens section with a chamfered top and a raised
# rachis, a rounded root that sinks into what it grows from, the widest point about a third of the way
# out and a pointed tip. The centreline leaves the surface at `rise` degrees and bends by `curl`
# (positive = the tip lifts further off the surface, negative = it sweeps back down along T), with an
# optional sideways lick (`sway`, studs). Detail: R = root->tip, G = across, B = per-feather random,
# A = zone (1 top, 0.6 outline edge, 0.2 underside). Motif U carries the tone (-1 deep crimson .. +1
# golden). With a glow comp the tip (t >= glow_from) is Neon; with a hot comp a hot-yellow flame core
# rides on top of the tip and licks past it.
# ---------------------------------------------------------------------------
FSEC = [(-1.0, 0.30, 0.6), (-0.62, 0.86, 1.0), (0.0, 1.0, 1.0), (0.62, 0.86, 1.0), (1.0, 0.30, 0.6),
        (0.45, 0.0, 0.2), (-0.45, 0.0, 0.2)]          # (across, up, zone)
FST = [0.0, 0.13, 0.28, 0.44, 0.6, 0.74, 0.84, 0.93, 1.0]
FST_M = [0.0, 0.2, 0.42, 0.64, 0.84, 1.0]
FST_S = [0.0, 0.3, 0.6, 0.84, 1.0]


def feather(c, P, N, T, L, W, *, th=0.05, rise=12.0, curl=20.0, sway=0.0, glow=None, glow_from=0.8,
            mat=FTH, rnd=None, sink=0.012, root_w=0.55, belly=0.36, ridge=0.35, tip_th=0.4, st=None,
            tone=0.0, hot=None, hot_from=0.6, tip_pow=0.85):
    N = N.normalized()
    T = (T - N * T.dot(N)).normalized()
    X = T.cross(N).normalized()
    rnd = RNG.random() if rnd is None else rnd
    ts = st or FST
    pts, nrms = [], []
    p = P - N * sink
    prev = 0.0
    for t in ts:
        am = math.radians(rise + curl * ((prev + t) / 2) ** 1.5)
        p = p + (T * math.cos(am) + N * math.sin(am)) * (L * (t - prev))
        a = math.radians(rise + curl * t ** 1.5)
        pts.append(p + X * (sway * t ** 2))
        nrms.append(-T * math.sin(a) + N * math.cos(a))
        prev = t
    mtone = (0.5 + 0.5 * clamp(tone, -1.0, 1.0), 0.0)

    def wid(t):
        if t < belly:
            return W * 0.5 * (root_w + (1 - root_w) * math.sin(math.pi / 2 * t / belly))
        return W * 0.5 * ((1 - t) / (1 - belly)) ** tip_pow

    def hgt(t):
        return th * (1 - (1 - tip_th) * t)

    def ring(cc, k):
        t = ts[k]
        w, h, n = wid(t), hgt(t), nrms[k]
        return [cc.v(pts[k] + X * (ax * w) + n * ((up * (1 + ridge) if ax == 0.0 else up) * h),
                     (t, (ax + 1) / 2, rnd, z), mtone) for ax, up, z in FSEC]

    def build(cc, ks, m, cap_end, tip):
        R = [ring(cc, k) for k in ks]
        faces = []
        n = len(FSEC)
        kind = MK_FEATHER if m == FTH else 0
        for a in range(len(R) - 1):
            for s in range(n):
                s2 = (s + 1) % n
                faces.append(cc.f([R[a][s], R[a][s2], R[a + 1][s2], R[a + 1][s]], m, mk=kind))
        if tip:
            tv = cc.v(pts[-1] + nrms[-1] * (hgt(1.0) * 0.45), (1.0, 0.5, rnd, 1.0), mtone)
            for s in range(n):
                faces.append(cc.f([R[-1][s], R[-1][(s + 1) % n], tv], m, mk=kind))
        faces.append(cc.f(R[0][::-1], m, mk=kind))
        if cap_end:
            faces.append(cc.f(R[-1], m, mk=kind))
        cc.bm.normal_update()
        probe = faces[1]
        if probe is not None and probe.normal.dot(nrms[ks[0]]) < 0:
            for f in faces:
                if f is not None:
                    f.normal_flip()

    last = len(ts) - 1
    if glow is None:
        build(c, list(range(0, last)), mat, False, True)
    else:
        kg = min(next(k for k, t in enumerate(ts) if t >= glow_from), last - 2)
        build(c, list(range(0, kg + 1)), mat, True, False)
        build(glow, list(range(kg, last)), 0, False, True)
    tan = (pts[-1] - pts[-2]).normalized()
    if hot is not None:
        kh = min(next(k for k, t in enumerate(ts) if t >= hot_from), last - 1)
        tdir = (pts[kh + 1] - pts[kh]).normalized()
        feather(hot, pts[kh] + nrms[kh] * (hgt(ts[kh]) * 1.1), nrms[kh], tdir, L * (1.0 - ts[kh]) * 1.5, W * 0.52,
                th=th * 0.5, rise=3.0, curl=curl * 0.5, sway=W * 0.3, mat=0, st=FST_M, sink=0.0, root_w=0.3,
                belly=0.42, ridge=0.2, tip_th=0.3, rnd=rnd)
    return pts[-1], nrms[-1], tan


def feather_field(c, surf, origin, flow, across, rows, cols, du, dv, size, keep=None, **kw):
    """Staggered rows of feathers lying on a surface, flowing along `flow` (root row first).
    size(u, v, row) -> (L, W) or (L, W, tone)."""
    flow = Vector(flow).normalized()
    across = Vector(across).normalized()
    placed = 0
    for r in range(rows):
        off = 0.5 if r % 2 else 0.0
        for k in range(-cols, cols + 1):
            p = Vector(origin) + flow * (r * dv) + across * ((k + off) * du)
            if keep and not keep(p, r):
                continue
            sz = size(p.x, p.y, r)
            P, N = surf(p.x, p.y)
            P2, _ = surf(p.x + flow.x * 0.02, p.y + flow.y * 0.02)
            extra = dict(kw)
            if len(sz) > 2:
                extra["tone"] = sz[2]
            feather(c, P, N, P2 - P, sz[0], sz[1], **extra)
            placed += 1
    return placed


def fxe(kind, pos, direction, **kw):
    d = {"kind": kind, "pos": Vector(pos), "dir": Vector(direction).normalized()}
    d.update(kw)
    return d


def cr_pts(ctrl, n):
    """n samples of a Catmull-Rom curve through the control points (uniform per segment)."""
    pts = [Vector(p) for p in ctrl]
    P = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    segs = len(pts) - 1
    out = []
    for k in range(n):
        t = k / (n - 1) * segs
        i = min(int(t), segs - 1)
        u = t - i
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u +
                          (-p0 + 3 * p1 - 3 * p2 + p3) * u * u * u))
    return out


def disc(c, P, N, up, r, *, thick=0.05, boss=0.04, rays=8, ray_len=0.45, ray_w=0.3, gem_w=0.0, gem_comp=None,
         gem_mat=RBY, mat=GLD, sides=12):
    """Sun disc: a bevelled gold rondel lying on a surface (engraved ring, raised boss) holding a faceted
    gem, ringed by pointed sun rays. Detail R = radius fraction, G = angle fraction (radial motif)."""
    N = N.normalized()
    up = (up - N * up.dot(N)).normalized()
    rt = up.cross(N).normalized()
    prof = [(1.0, -0.3), (1.0, 0.72), (0.9, 1.0), (0.72, 1.0), (0.66, 0.84), (0.6, 1.0), (0.46, 1.25), (0.3, 1.45)]
    angs = [2 * math.pi * s / sides for s in range(sides)]
    rings = [[P + (rt * math.cos(a) + up * math.sin(a)) * (r * rf) +
              N * (thick * min(hf, 1.0) + boss * max(0.0, hf - 1.0) / 0.45) for a in angs] for rf, hf in prof]
    loft(c, rings, mat, cap0=False, cap1=True, det=lambda k, s: (prof[k][0], s / sides, 0.5, 0.0))
    for q in range(rays):
        a = 2 * math.pi * (q + 0.5) / rays
        d = rt * math.cos(a) + up * math.sin(a)
        Lr = r * ray_len * (1.0 if q % 2 == 0 else 0.62)
        pts = [P + d * (r * 0.86) + N * thick * 0.5, P + d * (r * 0.95 + Lr * 0.5) + N * thick * 0.42,
               P + d * (r * 0.95 + Lr) + N * thick * 0.2]
        horn(c, pts, r * ray_w * (1.0 if q % 2 == 0 else 0.8), sides=4, flat=0.42, taper=1.0, mat=mat,
             up=N.cross(d))
    if gem_w > 0:
        gem(gem_comp or c, P + N * (thick + boss * 0.99), N, up, gem_w, gem_w, gem_w * 0.42, sides=8, mat=gem_mat)


FLAME_COL = [255, 150, 40]
T_GLOW = 0.72                    # where a hero feather's Neon tip starts


def top_ray(bvh, x, y):
    hit = bvh.ray_cast(Vector((x, y, 3.0)), Vector((0, 0, -1)), 6.0)
    if hit[0] is None:
        return Vector((x, y, 0.7)), UP.copy()
    return hit[0], (hit[1] if hit[1].z > 0 else -hit[1])


def wa(th):
    """|angle| from the front, for a head-chart angle th in 0..2pi."""
    return abs((th + math.pi) % (2 * math.pi) - math.pi)


def sa(th):
    return (th + math.pi) % (2 * math.pi) - math.pi


# ----- Helmet: the phoenix head ------------------------------------------------------------
def build_head():
    """Gold helm (engraved sun rays, enamel cheek guards and nape, ivory temple band), a big hooked beak
    whose culmen continues the crown keel, heavy brows over deep glowing eyes, cheek plumes and brow tufts,
    and a three-layer swept flame crest (spine ~1.5 studs above the head)."""
    comps, G, fx = [], GlowSet(), []
    hc = head_chart()
    nu = 24
    ths = [2 * math.pi * i / nu for i in range(nu)]          # seam at the front centre, under the beak
    EYE_TH, EYE_Z = math.radians(30), 0.10

    def z_bottom(th):
        return lerp(-0.50, -0.60, smooth((wa(th) - math.radians(40)) / math.radians(45)))
    s_top = HEAD_S_MAX - 0.22
    zrows = [-0.34, -0.20, -0.06, 0.03, 0.11, 0.19, 0.27, 0.35, 0.43]
    arc_s = [0.95 + 0.25 * math.pi / 2 * f for f in (0.45, 0.8, 1.0)]
    top_s = [s_top - 0.1, s_top]
    nz = len(zrows)
    Gr = []
    for j in range(2 + nz + len(arc_s) + len(top_s)):
        row = []
        for th in ths:
            zb = z_bottom(th)
            if j == 0:
                s = zb + 0.6
            elif j == 1:
                s = zb + 0.6 + 0.05
            elif j < 2 + nz:
                s = max(zb + 0.6 + 0.1, zrows[j - 2] + 0.6)
            elif j < 2 + nz + len(arc_s):
                s = arc_s[j - 2 - nz]
            else:
                s = top_s[j - 2 - nz - len(arc_s)]
            row.append((th, s))
        Gr.append(row)

    def socket(th, z):
        return bump(wa(th), z, EYE_TH, EYE_Z, 0.42, 0.15)

    def thick(j, i, th, s):
        r, z = head_profile(s)
        a = wa(th)
        side = smooth((a - math.radians(40)) / math.radians(50))
        t = 0.07 + 0.05 * smooth((z + 0.35) / 0.75) * side                  # cranium flares wider than the jaw
        t += 0.075 * bump(sa(th), z, 0.0, 0.34, 1.0, 0.2)                    # heavy brow mass
        t += 0.1 * bump(a, z, math.radians(84), -0.26, 0.7, 0.3)           # cheek guards
        x = abs(r * math.sin(th))
        if z > 0.55:
            t += 0.05 * max(0.0, 1 - x / 0.36)                              # crown ridge under the crest
        t -= 0.1 * socket(th, z)                                            # deep eye sockets
        if j <= 1:
            t += 0.03                                                        # raised gold rim
        return max(0.022, t)

    def face_zone(j, i):
        th0, s0 = Gr[j][i]
        th1, s1 = Gr[j + 1][(i + 1) % nu]
        if th1 < th0:
            th1 += 2 * math.pi
        return wa((th0 + th1) / 2), (head_profile(s0)[1] + head_profile(s1)[1]) / 2

    def matf(j, i):
        a, z = face_zone(j, i)
        if j == 0:
            return GLD
        if bump(a, z, EYE_TH, EYE_Z, 0.42, 0.15) > 0.25:
            return DRK
        if math.radians(62) < a < math.radians(124) and -0.46 < z < -0.04:
            return CRM                                                       # enamel cheek guards
        return GLD
    helm = Comp(bevel=0.014, segs=2, angle=34, facet=12, mk={GLD: MK_RADIAL, CRM: MK_FLAME, IVY: MK_PLATE})
    shell(helm, hc, Gr, thick, wrap=True, mat_fn=matf, rim_mat=GLD, flush=True, mscale=(0.66, 1.0),
          det_fn=lambda j, i, th, s: (s / HEAD_S_MAX, wa(th) / math.pi, 0.4, 0.0))   # symmetric: no wrap seam
    comps.append(helm)
    bvh = BVHTree.FromBMesh(helm.bm)

    # --- the beak visor: the culmen continues the crown keel, bulges out of the brow and hooks down
    # over the mouth; a lower mandible under it. Roots sunk so it grows out of the helm.
    bk = Comp(bevel=0.012, segs=2, angle=30, mk={GLD: MK_PLATE})
    SEC_B = [(0.0, 0.06), (0.42, -0.02), (0.78, -0.26), (1.0, -0.62), (0.9, -1.0), (0.0, -0.88), (-0.9, -1.0),
             (-1.0, -0.62), (-0.78, -0.26), (-0.42, -0.02)]

    def beak(ctrl, w_fn, d_fn, n=13, mat=GLD):
        pts = cr_pts(ctrl, n)
        rings = []
        for k in range(n):
            t = k / (n - 1)
            tan = (pts[min(k + 1, n - 1)] - pts[max(k - 1, 0)]).normalized()
            U = tan.cross(Vector((1, 0, 0))).normalized()
            w, d = w_fn(t), d_fn(t)
            rings.append([pts[k] + Vector((x * w, 0, 0)) + U * (u * d) for x, u in SEC_B])
        loft(bk, rings, mat, cap0=True, cap1=True, outward=True,
             det=lambda k, s: (k / (n - 1), s / len(SEC_B), 0.35, 0.0))
    beak([Vector((0, -0.40, 0.56)), Vector((0, -0.74, 0.47)), Vector((0, -1.04, 0.32)), Vector((0, -1.22, 0.04)),
          Vector((0, -1.12, -0.30))],
         lambda t: lerp(0.27, 0.02, t ** 1.1), lambda t: lerp(0.7, 0.05, t ** 0.85))
    beak([Vector((0, -0.52, -0.22)), Vector((0, -0.78, -0.27)), Vector((0, -0.95, -0.34)), Vector((0, -1.02, -0.42))],
         lambda t: lerp(0.18, 0.03, t), lambda t: lerp(0.2, 0.04, t), n=7)
    comps.append(bk)

    # --- heavy gold brows from the beak root up and back over the eyes (a fierce V)
    br = Comp(shade="smooth")
    for sg in (1, -1):
        pts = []
        for k in range(8):
            f = k / 7
            P, N = hc(sg * math.radians(lerp(7, 96, f)), lerp(0.25, 0.44, f ** 1.3) + 0.6)
            hit = project(bvh, P, N)
            if hit:
                pts.append(hit[0] + hit[1] * 0.05 + Vector((0, 0, 0.014)))
        horn(br, pts, 0.13, sides=6, flat=0.6, taper=0.8, r_tip=0.026, mat=GLD, up=Vector((0, -0.3, 1)))
    comps.append(br)

    # --- glowing eyes deep in the sockets, angled fierce
    for sg in (1, -1):
        P, N = hc(sg * EYE_TH, EYE_Z + 0.6)
        hit = project(bvh, P + N * 0.1, N)
        if hit:
            gem(G.h, hit[0] + hit[1] * 0.006, hit[1], Vector((-0.55 * sg, 0, 1)), 0.33, 0.13, 0.05, sides=8)

    # --- cheek plumes sweeping back and up, brow tufts flowing into the crest
    cp = Comp(shade="smooth")
    for sg in (1, -1):
        for k, (deg, z, Lf, tone) in enumerate(((74, -0.20, 0.62, -0.25), (88, -0.10, 0.58, -0.05),
                                                (102, 0.0, 0.52, 0.2))):
            P, N = hc(sg * math.radians(deg), z + 0.6)
            hit = project(bvh, P, N)
            if hit:
                feather(cp, hit[0], hit[1], Vector((sg * 0.05, 1.0, 0.5)), Lf, 0.32, th=0.075, rise=14, curl=-16,
                        sink=0.03, tone=tone, st=FST_M, rnd=0.2 + 0.2 * k)
        for k, (deg, z, Lf) in enumerate(((98, 0.40, 0.56), (112, 0.34, 0.48))):
            P, N = hc(sg * math.radians(deg), z + 0.6)
            hit = project(bvh, P, N)
            if hit:
                feather(cp, hit[0], hit[1], Vector((sg * 0.1, 1.0, 0.7)), Lf, 0.28, th=0.07, rise=20, curl=-20,
                        sink=0.03, tone=0.3, st=FST_M)
        for k, (deg, z, Lf) in enumerate(((52, 0.15, 0.64), (62, 0.0, 0.54))):          # gold eye streaks (relief)
            P, N = hc(sg * math.radians(deg), z + 0.6)
            hit = project(bvh, P, N)
            if hit:
                feather(cp, hit[0], hit[1], Vector((sg * 0.2, 1.0, 0.3 - 0.25 * k)), Lf, 0.2, th=0.045, rise=3, curl=-4,
                        sink=0.02, mat=GLD, st=FST_S, root_w=0.7, ridge=0.5)
    # a feather mane flowing down the nape, two graded rows
    for k, (deg, z, Lf) in enumerate(((150, 0.30, 0.52), (180, 0.32, 0.56), (210, 0.30, 0.52), (135, 0.06, 0.46),
                                      (165, 0.08, 0.5), (195, 0.08, 0.5), (225, 0.06, 0.46))):
        P, N = hc(math.radians(deg), z + 0.6)
        hit = project(bvh, P, N)
        if hit:
            feather(cp, hit[0], hit[1], Vector((0, 0.3, -1.0)), Lf, 0.32, th=0.07, rise=10, curl=-14, sink=0.03,
                    tone=0.2 if k < 3 else -0.2, st=FST_M, rnd=0.1 * k)
    comps.append(cp)

    # --- rubies: cheek guards and the forehead
    gm = Comp(bevel=0.004, segs=1, angle=40)
    for sg in (1, -1):
        P, N = hc(sg * math.radians(92), -0.30 + 0.6)
        hit = project(bvh, P + N * 0.1, N)
        if hit:
            gem(gm, hit[0] - hit[1] * 0.004, hit[1], UP, 0.11, 0.11, 0.05, sides=6, mat=RBY)

    # --- the crest: gold keel down the crown, then three layers of big flame feathers rising up and back
    keel = Comp(shade="smooth")
    kp = [top_ray(bvh, 0.0, y)[0] + Vector((0, 0, -0.01)) for y in (-0.56, -0.42, -0.22, -0.02, 0.18, 0.36, 0.52)]
    horn(keel, kp, 0.085, sides=6, flat=0.62, taper=0.0, r_tip=0.055, mat=GLD, up=UP)
    comps.append(keel)
    P, N = top_ray(bvh, 0.0, -0.46)
    gem(gm, P + N * 0.075, (N + Vector((0, -1.0, 0))).normalized(), UP, 0.13, 0.15, 0.05, sides=6, mat=RBY)
    comps.append(gm)
    cr = Comp(shade="smooth")
    for sg in (1, -1):
        for k, (y, Lf) in enumerate(((-0.24, 0.72), (-0.04, 0.88), (0.16, 0.98), (0.36, 0.92))):   # outer layer
            P, Ns = top_ray(bvh, sg * 0.30, y)
            N = (Ns + Vector((sg * 1.1, 0, 0))).normalized()
            feather(cr, P, N, Vector((sg * 0.45, 1.0, 0.0)), Lf, 0.32, th=0.085, rise=46 - 4 * k, curl=-30,
                    sway=sg * 0.04, sink=0.035, tone=-0.1, rnd=0.1 + 0.2 * k)
        for k, (y, Lf) in enumerate(((-0.32, 0.92), (-0.10, 1.16), (0.12, 1.34), (0.32, 1.30))):   # inner layer
            P, Ns = top_ray(bvh, sg * 0.16, y)
            N = (Ns + Vector((sg * 0.55, 0, 0))).normalized()
            feather(cr, P, N, Vector((sg * 0.25, 1.0, 0.0)), Lf, 0.34, th=0.09, rise=66 - 5 * k, curl=-38,
                    sway=sg * 0.03, glow=G.o, glow_from=T_GLOW, sink=0.035, tone=0.1, rnd=0.3 + 0.15 * k)
    tips = []
    for k, (y, Lf, rise, curl) in enumerate(((-0.42, 1.0, 80, -44), (-0.20, 1.34, 78, -44), (0.02, 1.62, 74, -42),
                                              (0.22, 1.78, 66, -40), (0.40, 1.50, 52, -34))):     # spine
        P, N = top_ray(bvh, 0.0, y)
        tip, tn, tt = feather(cr, P + N * 0.04, N, Vector((0, 1.0, 0.0)), Lf, 0.38, th=0.1, rise=rise, curl=curl,
                              glow=G.o, glow_from=T_GLOW, hot=G.h if 1 <= k <= 3 else None, sink=0.04, tone=0.2,
                              rnd=0.5 + 0.1 * k)
        tips.append((tip, tt))
    comps.append(cr)
    for n_, k in enumerate((1, 2, 3)):
        tip, tt = tips[k]
        fx.append(fxe("flame_plume", tip - tt * 0.12, (tt * 0.35 + UP).normalized(), size=(0.8, 1.0, 1.0)[n_],
                      rate=24, name=f"crest_plume_{n_ + 1}", note="flame plume on the crest"))
    return comps, G, fx


# ----- UpperTorso: gold breastplate, plumage, collar, the sun core, back medallion -----------------
def build_breastplate(comps, G, side=-1):
    chart = torso_chart(side)
    O = resample(PEC_O, 20)
    I = inset(O, lambda k, p: 0.10 if p.x < 0.12 else 0.16)
    ts = [0.0, 0.14, 0.62, 0.72, 0.80, 0.90, 1.0]

    def thick(j, i, u, v):
        base = pec_height(u, v)
        if j == 0:
            return base - PEC_RECESS * 0.55
        if j == 3:
            return base + 0.014                     # raised filigree bead
        if j >= 5:
            return base + 0.03 - (0.012 if j == len(ts) - 1 else 0.0)
        return base
    c = Comp(bevel=0.013, segs=2 if side < 0 else 1, angle=34)
    shell(c, chart, ring_grid(O, I, ts), thick, lift=lambda j, i, u, v: plate_lift(v), wrap=True, mat=GLD,
          mk=lambda j, i, m: MK_SCALLOP if j == 1 else 0, rim_mat=GLD, flush=True)
    comps.append(c)
    Fo = inset(I, -0.03)
    ctr = sum(I, Vector((0.0, 0.0))) / len(I)
    Fi = [ctr + (p - ctr) * 0.04 for p in Fo]
    floor = Comp(bevel=0.0, shade="smooth", mk={CRM: MK_FLAME})

    def fthick(j, i, u, v):
        return pec_height(u, v) - PEC_RECESS

    shell(floor, chart, ring_grid(Fo, Fi, [0.0, 0.5, 1.0]), fthick, lift=lambda j, i, u, v: plate_lift(v), wrap=True,
          mat=CRM, rim_mat=DRK)
    comps.append(floor)
    if side < 0:
        def surf(u, v):
            P, N = chart(u, v)
            return P + N * (plate_lift(v) + fthick(0, 0, u, v)), N
        pl = Comp(shade="smooth")
        flow = Vector((0.2, -1.0)).normalized()

        def keep(p, r):
            return point_in_poly(p, I) and dist_to_poly(p, I) > 0.03
        n = feather_field(pl, surf, (0.52, 0.66), flow, (1.0, 0.2), 7, 3, 0.17, 0.145,
                          lambda u, v, r: (0.32, 0.24, 0.45 - 0.09 * r), keep=keep, th=0.058, rise=10, curl=14,
                          st=FST_S, sink=0.006, ridge=0.35)
        comps.append(pl)
        log("plumage feathers", n)


def build_collar(comps, G):
    """Gold filigree gorget across the top of the chest: scalloped feather lobes, rubies, raised rims."""
    chart = torso_chart(-1)
    nu = 20
    us = [-0.56 + 1.12 * i / nu for i in range(nu + 1)]

    def v_bot(u):
        f = (u + 0.56) / (1.12 / 5)
        lobe = 1 - abs(2 * (f % 1.0) - 1) if 0.0 < f < 5.0 else 0.0
        return 0.47 - 0.085 * lobe ** 0.8 + 0.06 * (abs(u) / 0.56) ** 2
    tvs = [0.0, 0.14, 0.5, 0.86, 1.0]
    Gc = [[(u, lerp(v_bot(u), 0.715 - 0.03 * (abs(u) / 0.56) ** 2, t)) for u in us] for t in tvs]
    c = Comp(bevel=0.012, segs=1, angle=32, mk={GLD: MK_PLATE})
    shell(c, chart, Gc, lambda j, i, u, v: pec_height(abs(u), v) + plate_lift(v) + 0.045 + (0.02 if j in (0, 4) else 0.0),
          mat=GLD, rim_mat=GLD, flush=True)
    comps.append(c)
    gm = Comp(bevel=0.004, segs=1, angle=40)
    for q in range(5):
        u = -0.56 + 1.12 * (q + 0.5) / 5
        v = v_bot(u) + 0.08
        P, N = chart(u, v)
        gem(gm, P + N * (pec_height(abs(u), v) + 0.064), N, UP, 0.075, 0.09, 0.035, sides=6, mat=RBY)
    comps.append(gm)


def build_sternum(comps, G, side=-1):
    chart = torso_chart(side)
    c = Comp(bevel=0.012, segs=2, angle=32)
    xs = [-0.08, -0.04, 0.0, 0.04, 0.08]
    vs = [-0.46, -0.34, -0.2, -0.05, 0.05] if side < 0 else [-0.46, -0.34, -0.1, 0.2, 0.45, 0.66, 0.74]

    def thick(j, i, u, v):
        k = 1 - abs(u) / 0.08
        top_fade = 1 - smooth((v - 0.62) / 0.14)
        bot = smooth((v + 0.46) / 0.14)
        return (0.07 + 0.12 * k ** 0.8) * max(0.35, top_fade) * max(0.4, bot)

    shell(c, chart, grid(xs, vs), thick, lift=lambda j, i, u, v: plate_lift(v), mat=GLD, rim_mat=GLD, flush=True)
    comps.append(c)
    if side < 0:
        bvh = BVHTree.FromBMesh(c.bm)
        crack(G.o, bvh, chart, [(0.0, v) for v in (-0.2, -0.26, -0.32, -0.38, -0.44)], 0.012, 0.007)


def build_core(comps, G, fx):
    """The focal point: a big faceted sun gem (hot Neon) in a domed gold rondel gripped by five talons, a
    sunburst of gold ray plates and glowing rays fanning over the chest (none upward: the collar is there)."""
    chart = torso_chart(-1)
    cv = 0.10
    P0, N0 = chart(0.0, cv)

    def circ(r, n=16):
        return [Vector((r * math.cos(2 * math.pi * k / n), cv + r * math.sin(2 * math.pi * k / n))) for k in range(n)]
    c = Comp(bevel=0.012, segs=2, angle=32, mk={GLD: MK_RADIAL})
    shell(c, chart, ring_grid(circ(0.30), circ(0.19), [0.0, 0.3, 0.7, 1.0]),
          lambda j, i, u, v: [0.25, 0.27, 0.24, 0.18][j], wrap=True, mat=GLD, rim_mat=GLD, flush=True)
    shell(c, chart, ring_grid(circ(0.19), circ(0.01), [0.0, 1.0]), 0.2, wrap=True, mat=DRK, rim_mat=DRK, flush=True)
    comps.append(c)
    gp = P0 + N0 * 0.2
    gem(G.h, gp, N0, UP, 0.38, 0.38, 0.16, sides=10)
    rays = Comp(shade="smooth")
    for k, ang in enumerate((15, 45, 135, 165, 195, 225, 255, 285, 315, 345)):
        a = math.radians(ang)
        d = Vector((math.cos(a), 0, math.sin(a)))
        long_ = k % 2 == 0 and ang not in (255, 285)
        feather(rays, P0 + d * 0.27 + N0 * 0.24, N0, d, 0.5 if long_ else 0.34, 0.17 if long_ else 0.13, th=0.05,
                rise=-3, curl=4, mat=GLD, st=FST_S, sink=0.0, root_w=0.8, ridge=0.5)
        a2 = math.radians(ang + 15)
        d2 = Vector((math.cos(a2), 0, math.sin(a2)))
        if ang not in (45, 345, 135):
            gl = [P0 + d2 * (0.3 + 0.08 * q) + N0 * (0.235 - 0.012 * q) for q in range(4)]
            horn(G.o, gl, 0.028, sides=4, flat=0.5, taper=1.0, mat=0, up=N0.cross(d2))
    cl = Comp(shade="smooth")
    for q in range(5):
        a = math.radians(90 + 72 * q)
        d = Vector((math.cos(a), 0, math.sin(a)))
        base = gp + d * 0.22 - N0 * 0.02
        tipp = gp + d * 0.1 + N0 * 0.1
        horn(cl, curve_pts(base, base + N0 * 0.08 + d * 0.03, tipp + N0 * 0.04 + d * 0.02, tipp, 6), 0.034, sides=6,
             taper=1.2, mat=GLD)
    comps += [rays, cl]
    fx.append(fxe("ember_swirl", gp + N0 * 0.14, (0, -1.0, 0.3), rate=16, name="core_ember_swirl",
                  note="embers bursting out and drifting up around the sun core"))
    fx.append(fxe("light", gp + N0 * 0.2, (0, -1, 0), color=[255, 150, 50], range=12, brightness=2.4,
                  name="core_light", note="bright PointLight at the sun core"))


def build_lames_px(comps, side):
    chart = torso_chart(side)
    for k, (hw, tc, ts_, bc, bs) in enumerate(LAMES):
        c = Comp(bevel=0.013, segs=1, angle=34, mk={CRM: MK_FLAME, GLD: MK_PLATE})
        nu = 6
        us = [-1 + 2 * i / nu for i in range(nu + 1)]
        tv = [0.0, 0.55, 0.84, 0.90, 1.0]
        G_ = [[(s_ * hw * lerp(1.0, 0.94, t), lerp(tc + ts_ * s_ * s_, bc + bs * s_ * s_, t)) for s_ in us] for t in tv]

        def thick(j, i, u, v, hw=hw):
            k_ = clamp(1 - abs(u) / (0.22 * hw / 0.8))
            lip = 0.02 if j in (3, 4) else 0.0
            return LAME_T + LAME_R * k_ ** 1.2 + lip - (0.01 if j == 4 else 0.0)

        shell(c, chart, G_, thick, lift=lambda j, i, u, v, tv=tv: lame_lift_bottom() * tv[j] - 0.01,
              mat_fn=lambda j, i: CRM if j == 0 else GLD, rim_mat=GLD, flush=True,
              det_fn=lambda j, i, u, v, tv=tv, nu=nu, k=k: (tv[j], i / nu, 0.3 + 0.1 * k, 0.0))
        comps.append(c)


def build_upper_torso():
    comps, G, fx = [], GlowSet(), []
    for side in (-1, 1):
        undersuit_box(comps, torso_chart(side, clear=SUIT_CL), [-0.99, -0.6, 0, 0.6, 0.99],
                      [-0.8, -0.3, 0.2, 0.6, 0.9, 1.0])
        half = []
        build_breastplate(half, G, side)
        comps += half + [h.mirrored() for h in half]
        build_sternum(comps, G, side)
        build_lames_px(comps, side)
    build_collar(comps, G)
    build_core(comps, G, fx)
    # back medallion: the wings grow from under it
    P, N = torso_chart(1)(0.0, 0.30)
    dc = Comp(bevel=0.01, segs=1, angle=40, mk={GLD: MK_RADIAL})
    disc(dc, P + N * 0.12, N, UP, 0.30, thick=0.09, boss=0.05, rays=12, ray_len=0.55, gem_w=0.2, gem_comp=G.h,
         gem_mat=0)
    comps.append(dc)
    fx.append(fxe("heat_glow", Vector((0, 0, 0)), UP, parent="part", name="chest_heat_glow",
                  note="soft heat shimmer/glow around the upper body"))
    return comps, G, fx


# ----- The wings: their own mesh on UpperTorso ------------------------------------------------------
def build_wings():
    """Big lifted wings in a V behind the player, grown from the back medallion: a segmented gold wing-arm
    with a glowing leading edge, a ruby at the elbow and the wrist, and three feather tiers (long primaries
    fanning from the wrist, secondaries hanging out and down, two rows of coverts) plus scapulars over the
    back. Tips ~1.5 studs above the head, span ~5.3 studs, swept back so the view past the head stays open."""
    comps, G, fx = [], GlowSet(), []
    arm = Comp(shade="smooth")
    gm = Comp(bevel=0.006, segs=1, angle=40, mk={GLD: MK_RADIAL})
    fw = Comp(shade="smooth")
    cv = Comp(shade="smooth")
    e_up = Vector((0, 0.12, 1)).normalized()
    THETA = [(0.0, -100), (0.1, -95), (0.26, -84), (0.36, -76), (0.46, -52), (0.56, -38), (0.66, -27),
             (0.76, -18), (0.86, -10), (0.94, 12), (1.0, 40)]

    def theta_at(t):
        for (t0, a0), (t1, a1) in zip(THETA, THETA[1:]):
            if t <= t1:
                return lerp(a0, a1, (t - t0) / (t1 - t0))
        return THETA[-1][1]
    for sg in (1, -1):
        tag = "l" if sg > 0 else "r"
        e_out = Vector((sg, 0.22, 0)).normalized()
        Nw = Vector((-sg * 0.22, 1.0, -0.12)).normalized()
        ctrl = [Vector((sg * 0.16, 0.60, 0.22)), Vector((sg * 0.62, 1.08, 0.80)), Vector((sg * 1.20, 1.34, 1.54)),
                Vector((sg * 1.60, 1.44, 2.24))]
        A = cr_pts(ctrl, 16)

        def At(t, A=A):
            x = clamp(t) * (len(A) - 1)
            i = min(int(x), len(A) - 2)
            return A[i].lerp(A[i + 1], x - i)

        def Tt(t, At=At):
            return (At(min(1.0, t + 0.02)) - At(max(0.0, t - 0.02))).normalized()

        def fdir(theta, e_out=e_out):
            a = math.radians(theta)
            return e_out * math.cos(a) + e_up * math.sin(a)

        def lead(t, Nw=Nw, sg=sg):
            ld = Nw.cross(Tt(t)).normalized()
            if ld.dot(Vector((sg * 0.4, 0, 1))) < 0:
                ld = -ld
            return At(t) + ld * (lerp(0.105, 0.07, t) * 0.92) + Nw * 0.025

        horn(arm, A, 0.105, sides=7, taper=1.0, r_tip=0.07, rings=0.07, mat=GLD, up=Nw)
        horn(G.o, [lead(0.08 + 0.92 * q / 13) for q in range(14)], 0.026, sides=4, taper=0.0, r_tip=0.02, mat=0)
        disc(gm, At(1.0) + Nw * 0.07, Nw, e_up, 0.14, thick=0.05, boss=0.035, rays=6, ray_len=0.7, gem_w=0.16,
             gem_mat=RBY)
        disc(gm, At(0.667) + Nw * 0.085, Nw, e_up, 0.09, thick=0.04, boss=0.02, rays=0, gem_w=0.1, gem_mat=RBY)
        # primaries: fan from the wrist, glowing tips, hot flame cores on the top three
        tips = []
        for k, (theta, Lf) in enumerate(((80, 1.28), (64, 1.42), (48, 1.42), (32, 1.32), (16, 1.18), (0, 1.04))):
            t = 1.0 - 0.015 * k
            tip, tn, tt = feather(fw, At(t) - Nw * 0.03, Nw, fdir(theta), Lf, 0.44, th=0.09, rise=4, curl=8, tip_pow=0.6, belly=0.42,
                                  sway=0.05 * sg, glow=G.o, glow_from=T_GLOW, hot=G.h if k <= 2 else None,
                                  sink=0.02, tone=0.05, rnd=0.1 * k)
            tips.append((tip, tt))
        # secondaries: hanging out and down along the arm
        for k, (t, Lf) in enumerate(((0.86, 1.1), (0.76, 1.05), (0.66, 1.0), (0.56, 0.95), (0.46, 0.9), (0.36, 0.8),
                                     (0.26, 0.78))):
            feather(fw, At(t), Nw, fdir(theta_at(t)), Lf, 0.42, th=0.08, rise=4, curl=8, sway=0.04 * sg, sink=0.02, st=FST_M, tip_pow=0.6, belly=0.42,
                    tone=-0.15, rnd=0.15 * k)
        # scapulars over the back, between the wings
        for k, (t, Lf) in enumerate(((0.05, 0.74), (0.12, 0.70), (0.19, 0.64))):
            feather(cv, At(t) + Nw * 0.02, Nw, fdir(theta_at(t)), Lf, 0.34, th=0.075, rise=6, curl=10, sink=0.03, tip_pow=0.65,
                    tone=-0.25, st=FST_M)
        # median coverts over the secondaries, lesser coverts on the arm (golden)
        for k, t in enumerate((0.18, 0.30, 0.42, 0.54, 0.66, 0.78, 0.90)):
            d = fdir(theta_at(t))
            feather(cv, At(t) + d * 0.2 + Nw * 0.045, Nw, d, 0.62, 0.36, th=0.075, rise=6, curl=10, sink=0.02, tip_pow=0.65,
                    tone=0.15, st=FST_M, rnd=0.2 + 0.1 * k)
        for k, t in enumerate((0.12, 0.24, 0.36, 0.48, 0.60, 0.72, 0.84, 0.95)):
            feather(cv, At(t) + Nw * 0.08, Nw, fdir(theta_at(t)), 0.46, 0.34, th=0.075, rise=8, curl=12, sink=0.03, tip_pow=0.65,
                    tone=0.4, st=FST_M, rnd=0.3 + 0.08 * k)
        for k in range(3):
            tip, tt = tips[k]
            fx.append(fxe("flame_plume", tip - tt * 0.1, (tt * 0.4 + UP).normalized(), size=0.85 - 0.1 * k, rate=22,
                          name=f"wing_{tag}_tip_plume_{k + 1}", note="flame plume on a wing tip"))
        for k, t in enumerate((0.38, 0.58, 0.78, 0.94)):
            fx.append(fxe("flame_sheet", lead(t), (Nw * 0.7 + UP * 0.6).normalized(), size=0.7, rate=16,
                          name=f"wing_{tag}_edge_{k + 1}", note="trailing flame sheet along the wing's leading edge"))
        fx.append(fxe("embers_rise", At(0.75) + fdir(-20) * 0.5 + Nw * 0.1, UP, rate=14, name=f"wing_{tag}_embers",
                      note="embers rising off the wing"))
    comps += [arm, gm, fw, cv]
    fx.append(fxe("embers_rise", Vector((0, 0.9, 0.2)), UP, rate=10, name="back_embers",
                  note="embers rising from the back medallion"))
    fx.append(fxe("light", Vector((0, 1.5, 1.7)), UP, color=[255, 170, 70], range=10, brightness=1.2,
                  name="wing_light", note="soft second light between the wings"))
    return comps, G, fx


# ----- LowerTorso: enamel belt with rubies, sun buckle, feather tassets, phoenix tail ---------------
def build_lower_torso():
    comps, G, fx = [], GlowSet(), []
    fth = Comp(shade="smooth")
    gems = Comp(bevel=0.004, segs=1, angle=40)
    for side in (-1, 1):
        undersuit_box(comps, lt_chart(side, SUIT_CL), [-0.99, 0, 0.99], [-0.2, 0.0, 0.2])
        ch = lt_chart(side)
        c = Comp(bevel=0.012, segs=1, angle=32, mk={CRM: MK_FLAME})
        us = [-0.985 + 1.97 * i / 10 for i in range(11)]
        vs = [-0.155, -0.14, -0.118, 0.0, 0.118, 0.14, 0.155]

        def thick(j, i, u, v):
            lip = 0.024 if j in (0, 1, 5, 6) else 0.0
            return 0.07 + lip + (0.02 if j == 3 else 0.0) - (0.01 if j in (0, 6) else 0.0)
        shell(c, ch, grid(us, vs), thick, mat_fn=lambda j, i: GLD if j in (0, 5) else CRM, rim_mat=GLD, flush=True)
        comps.append(c)
        for x in (-0.84, -0.62, -0.40, 0.40, 0.62, 0.84):
            P, N = ch(x, 0.0)
            if side < 0:
                gem(gems, P + N * 0.086, N, UP, 0.075, 0.075, 0.036, sides=6, mat=RBY)
            else:
                rivet(gems, P + N * 0.086, N, r=0.032, h=0.024)
        tc = Comp(bevel=0.012, segs=1, angle=34, mk={GLD: MK_PLATE})
        tv = [0.0, 0.5, 0.84, 0.92, 1.0]
        spans = ((0.08, 0.93), (-0.93, -0.08)) if side < 0 else ((-0.66, 0.66),)
        for x0, x1 in spans:
            Gt = [[(lerp(x0, x1, i / 6), lerp(-0.10, -0.26, t)) for i in range(7)] for t in tv]
            shell(tc, ch, Gt, lambda j, i, u, v: 0.05 + (0.018 if j >= 2 else 0.0),
                  lift=lambda j, i, u, v, tv=tv: lerp(0.02, 0.07, tv[j]), mat=GLD, rim_mat=GLD, flush=True)
        comps.append(tc)
        if side < 0:
            # feather tassets over each thigh: a long lower tier (glowing tips) under a short golden tier
            for sgn, (x0, x1) in zip((1, -1), spans):
                mids = []
                for q in range(5):
                    x = lerp(x0 + 0.06, x1 - 0.06, q / 4)
                    P, N = ch(x, -0.18)
                    tip, tn, tt = feather(fth, P + N * 0.07, N, Vector((sgn * 0.1 * (q - 2), 0, -1.0)), 0.62, 0.26,
                                          th=0.065, rise=12, curl=10, sink=0.0, glow=G.o, glow_from=0.8, tone=-0.1, st=FST_M,
                                          rnd=0.2 * q)
                    mids.append((tip, tt))
                for q in range(4):
                    x = lerp(x0 + 0.12, x1 - 0.12, q / 3)
                    P, N = ch(x, -0.22)
                    feather(fth, P + N * 0.12, N, Vector((sgn * 0.08 * (q - 1.5), 0, -1.0)), 0.44, 0.28, th=0.065,
                            rise=14, curl=12, sink=0.0, st=FST_M, tone=0.3, rnd=0.3 + 0.2 * q)
                tip, tt = mids[2]
                fx.append(fxe("flame_lick", tip, (-tt * 0.3 + UP).normalized(), size=0.5, rate=10,
                              name=f"tasset_{'l' if sgn > 0 else 'r'}_lick", note="small flame at the tasset tips"))
        else:
            # the phoenix tail: a long glowing tier under a short golden tier, flaring back
            mids = []
            for q in range(6):
                x = lerp(-0.6, 0.6, q / 5)
                P, N = ch(x, -0.14)
                tip, tn, tt = feather(fth, P + N * 0.07, N, Vector((0.14 * (q - 2.5), 0, -1.0)), 0.78, 0.28, th=0.07,
                                      rise=18, curl=12, sink=0.0, glow=G.o, glow_from=0.74,
                                      hot=G.h if q in (2, 3) else None, tone=-0.1, rnd=0.15 * q)
                mids.append((tip, tt))
            for q in range(5):
                x = lerp(-0.5, 0.5, q / 4)
                P, N = ch(x, -0.20)
                feather(fth, P + N * 0.12, N, Vector((0.12 * (q - 2), 0, -1.0)), 0.5, 0.3, th=0.07, rise=20, curl=12,
                        sink=0.0, st=FST_M, tone=0.3, rnd=0.25 * q)
            tip, tt = mids[2]
            fx.append(fxe("flame_lick", (tip + mids[3][0]) / 2, (-tt * 0.3 + UP).normalized(), size=0.6, rate=12,
                          name="tail_lick", note="flames licking off the phoenix tail"))
    comps += [fth, gems]
    P, N = lt_chart(-1)(0.0, 0.0)
    dc = Comp(bevel=0.01, segs=1, angle=40, mk={GLD: MK_RADIAL})
    disc(dc, P + N * 0.07, N, UP, 0.19, thick=0.06, boss=0.04, rays=10, ray_len=0.55, gem_w=0.15, gem_comp=G.h,
         gem_mat=0)
    comps.append(dc)
    fx.append(fxe("heat_glow", Vector((0, 0, 0)), UP, parent="part", name="waist_heat_glow", size=0.7,
                  note="soft heat glow around the waist and tassets"))
    return comps, G, fx


# ----- Pauldrons (left upper arm; outer = +x) ---------------------------------------------------
def build_upper_arm():
    """Gold dome under a three-tier flame-feather mantle, a gold sun-disc cap with a ruby, a tall flame
    crest sweeping up, out and back (glowing tips); two layered gold-and-enamel arm plates and a feather
    fringe below."""
    comps, G, fx = [], GlowSet(), []
    su = limb_chart(r=0.1, clear=SUIT_CL)
    undersuit_box(comps, su, limb_cols(su), [-0.58, -0.2, 0.2, 0.52])
    lc = limb_chart(r=0.1)
    L = lc.stations
    top = Comp(shade="smooth")
    tc_ = [Vector((x, y, 0.584 + SUIT_CL)) for x, y in ((-0.49, -0.49), (0.49, -0.49), (0.49, 0.49), (-0.49, 0.49))]
    top.f([top.v(p, (0, 0, 0.5, 0)) for p in tc_], SUIT)
    comps.append(top)
    for k, (zt, zb, fl) in enumerate(((0.34, -0.02, 0.12), (0.04, -0.34, 0.15))):
        c = Comp(bevel=0.012, segs=1, angle=34, mk={GLD: MK_PLATE, CRM: MK_FLAME})
        nu = 12
        tvs = [0.0, 0.1, 0.32, 0.68, 0.86, 0.93, 1.0]
        us = [L["total"] * i / nu for i in range(nu + 1)]
        Gp = [[(u, lerp(zt, zb, t)) for u in us] for t in tvs]
        shell(c, lc, Gp, lambda j, i, u, v: 0.05 + (0.02 if (j == 0 or j >= 5) else 0.0),
              lift=lambda j, i, u, v, fl=fl, tvs=tvs: fl * (0.35 + 0.65 * tvs[j] ** 1.3),
              mat_fn=lambda j, i: CRM if j == 2 else GLD, rim_mat=GLD, flush=True)
        comps.append(c)
    ff = Comp(shade="smooth")
    for q in range(4):
        u = L["outer0"] + (L["outer1"] - L["outer0"]) * (q + 0.5) / 4
        P, N = lc(u, -0.28)
        feather(ff, P + N * 0.17, N, Vector((0, 0.15, -1.0)), 0.3, 0.24, th=0.06, rise=30, curl=-6, sink=0.02,
                st=FST_M, tone=-0.1, rnd=0.25 * q)
    P, N = lc(L["outer_mid"], 0.16)
    gem(ff, P + N * 0.128, N, UP, 0.1, 0.1, 0.045, sides=6, mat=RBY)
    comps.append(ff)
    ss = [0.0, 0.10, 0.25, 0.42, 0.60, 0.76, 0.88, 0.95, 0.975, 1.0]
    tt = [-1.85 + 3.7 * i / 12 for i in range(13)]
    Gd = []
    for s_ in ss:
        row = []
        for t_ in tt:
            f = (t_ + 1.85) / 3.7
            hem = 0.05 * max(0.0, 1 - abs(2 * ((f * 3) % 1.0) - 1) ** 1.2) * (s_ - 0.88) / 0.12 if s_ > 0.9 else 0.0
            row.append(((s_ + hem) * PD_SU, t_ * PD_TV))
        Gd.append(row)
    trim_rows = 8

    def dthick(j, i, u, v):
        t_ = abs(v / PD_TV) / 1.85
        rim = j >= trim_rows or t_ > 0.93
        base = 0.075 + 0.025 * (1 - t_ ** 2)
        return base + (0.024 if rim else 0.0) - (0.01 if (j == len(ss) - 1) else 0.0)
    dome = Comp(bevel=0.014, segs=2, angle=32)
    shell(dome, pd_chart, Gd, dthick, mat=GLD, rim_mat=GLD, flush=False,
          mk=lambda j, i, m: 0 if (j >= trim_rows - 1 or i == 0 or i == len(tt) - 2) else MK_PLATE,
          det_fn=lambda j, i, u, v: (ss[j], i / 12, 0.71, 0.0))
    comps.append(dome)

    def dsurf(u, v):
        P, N = pd_chart(u, v)
        return P + N * (0.075 + 0.025 * (1 - (abs(v / PD_TV) / 1.85) ** 2)), N
    # the mantle: three graded tiers flowing down and out over the dome (golden top, deep crimson bottom)
    fth = Comp(shade="smooth")
    for r, (s, n, Lf, Wf, rise, tone) in enumerate(((0.36, 5, 0.46, 0.34, 10, 0.35), (0.54, 5, 0.54, 0.36, 12, 0.05),
                                                     (0.72, 6, 0.62, 0.36, 16, -0.25))):
        for q in range(n):
            t_ = lerp(-1.45, 1.45, (q + 0.5) / n)
            P, N = dsurf(s * PD_SU, t_ * PD_TV)
            P2, _ = dsurf((s + 0.03) * PD_SU, t_ * PD_TV)
            feather(fth, P, N, P2 - P, Lf, Wf, th=0.07, rise=rise, curl=-12, sink=0.02, tone=tone, st=FST_M, tip_pow=0.7,
                    rnd=0.1 * q + 0.3 * r)
    comps.append(fth)
    # the gold sun-disc cap
    dc = Comp(bevel=0.008, segs=1, angle=40, mk={GLD: MK_RADIAL})
    P, N = dsurf(0.2 * PD_SU, 0.0)
    disc(dc, P + N * 0.03, N, Vector((0, -1, 0)), 0.2, thick=0.06, boss=0.035, rays=8, ray_len=0.5, gem_w=0.13,
         gem_mat=RBY)
    comps.append(dc)
    # the flame crest: rising up, out and back, graded in length; glowing tips, hot cores on the tallest
    crest = Comp(shade="smooth")
    tips = []
    for k, (t_, Lf, rise) in enumerate(((-0.62, 0.66, 50), (-0.36, 0.84, 54), (-0.10, 1.00, 58), (0.14, 1.12, 60),
                                        (0.36, 1.18, 60))):
        P, N = dsurf(0.14 * PD_SU, t_ * PD_TV)
        N2 = (N + Vector((0.6, 0, 0.4))).normalized()
        tip, tn, tt_ = feather(crest, P, N2, Vector((0.62, 0.5, 0.25)), Lf, 0.36, th=0.085, rise=rise, curl=-26,
                               sway=0.03, glow=G.o, glow_from=T_GLOW, hot=G.h if k >= 3 else None, sink=0.035,
                               tone=0.15, rnd=0.2 * k)
        tips.append((tip, tt_))
    comps.append(crest)
    ct = (tips[3][0] + tips[4][0]) / 2
    fx.append(fxe("flame_plume", ct - tips[4][1] * 0.1, (tips[4][1] * 0.35 + UP).normalized(), size=0.85, rate=22,
                  name="pauldron_plume", note="flame plume on the pauldron crest"))
    return comps, G, fx


# ----- Vambraces (left lower arm) ------------------------------------------------------------------
def build_lower_arm():
    comps, G, fx = [], GlowSet(), []
    su = limb_chart(r=0.1, clear=SUIT_CL)
    undersuit_box(comps, su, limb_cols(su), [-0.52, 0.0, 0.5])
    lc = limb_chart(r=0.1)
    L = lc.stations
    nu = 12
    us = [L["total"] * i / nu for i in range(nu + 1)]

    def z_hi(u):
        p, _ = lc(u, 0)
        if p.y < -0.3:
            return 0.06 + 0.10 * max(0.0, 1 - abs(p.x - 0.1) / 0.4)
        return lerp(0.10, 0.26 + 0.08 * max(0.0, 1 - abs(p.x) / 0.45), smooth((p.y + 0.3) / 0.8))
    tvs = [0.0, 0.07, 0.12, 0.3, 0.7, 0.88, 0.94, 1.0]
    Gp = [[(u, lerp(-0.47, z_hi(u), t)) for u in us] for t in tvs]
    c = Comp(bevel=0.013, segs=1, angle=30, mk={GLD: MK_PLATE, CRM: MK_FLAME})

    def th(j, i, u, v):
        p, _ = lc(u, 0)
        ridge = 0.03 * max(0.0, 1 - abs(p.y) / 0.25) if p.x > 0.45 else 0.0
        return 0.06 + ridge + (0.022 if j <= 1 else 0.0) + (0.016 if j >= 6 else 0.0)

    def matf(j, i):
        um = (us[i] + us[i + 1]) / 2
        if j <= 1 or j >= 5:
            return GLD
        if j in (3, 4) and L["front_mid"] * 0.6 < um < L["corner_ob"]:
            return CRM
        return GLD
    shell(c, lc, Gp, th, lift=lambda j, i, u, v: 0.10 * (1 - tvs[j] / 0.5) ** 2 if tvs[j] < 0.5 else 0.0,
          mat_fn=matf, rim_mat=GLD, flush=True)
    comps.append(c)
    bvh = BVHTree.FromBMesh(c.bm)
    rib = Comp(shade="smooth")
    for x in (0.2, 0.8):
        pts = []
        for z in (0.16, 0.0, -0.16, -0.30):
            P, N = lc(x, z)
            pts.append(P + N * (0.075 + 0.10 * max(0.0, (-0.2 - z) / 0.3) ** 2))
        horn(rib, pts, 0.028, sides=4, flat=0.6, taper=0.0, r_tip=0.028, mat=GLD, up=Vector((0, -1, 0)))
    P, N = lc(L["outer_mid"], -0.38)
    hit = project(bvh, P + N * 0.3, N)
    if hit:
        gem(rib, hit[0] + hit[1] * 0.004, hit[1], UP, 0.1, 0.1, 0.045, sides=6, mat=RBY)
    comps.append(rib)
    crack(G.o, bvh, lc, [(L["outer_mid"], z) for z in (0.12, 0.0, -0.12, -0.24, -0.3)], 0.012, 0.009)
    fth = Comp(shade="smooth")
    for k, (z, Lf, off, rise, tone) in enumerate(((-0.08, 0.52, 0.06, 30, -0.3), (-0.2, 0.44, 0.06, 30, -0.3),
                                                  (-0.02, 0.46, 0.1, 22, 0.2), (-0.14, 0.40, 0.1, 22, 0.2),
                                                  (-0.26, 0.34, 0.1, 22, 0.2))):
        P, N = lc(L["outer_mid"] + 0.14, z)
        feather(fth, P + N * off, N, Vector((0, 1.0, -0.1)), Lf, 0.24, th=0.055, rise=rise, curl=-8, sink=0.02,
                st=FST_M, tone=tone, rnd=0.2 * k)
    comps.append(fth)
    return comps, G, fx


# ----- Legs ------------------------------------------------------------------------------------------
def build_upper_leg():
    comps, G, fx = [], GlowSet(), []
    su = limb_chart(r=0.1, clear=SUIT_CL)
    undersuit_box(comps, su, limb_cols(su), [-0.6, -0.2, 0.2, 0.6])
    lc = limb_chart(r=0.1)
    L = lc.stations
    nu = 14
    us = [0.025 + (L["corner_ob"] - 0.025) * i / nu for i in range(nu + 1)]

    def z_lo(u):
        p, _ = lc(u, 0)
        return -0.40 - (0.13 * max(0.0, 1 - abs(p.x) / 0.5) if p.y < -0.3 else 0.0)
    # lower cuisse plate (under): gold with a crimson enamel front panel
    tvs = [0.0, 0.07, 0.13, 0.5, 1.0]
    Gp = [[(u, lerp(z_lo(u), 0.06, t)) for u in us] for t in tvs]
    c = Comp(bevel=0.013, segs=1, angle=30, mk={GLD: MK_PLATE, CRM: MK_FLAME})

    def th(j, i, u, v):
        p, _ = lc(u, 0)
        ridge = 0.035 * max(0.0, 1 - abs(p.x) / 0.22) if p.y < -0.3 else 0.0
        return 0.06 + ridge + (0.022 if j <= 1 else 0.0)

    def matf(j, i):
        p, _ = lc((us[i] + us[i + 1]) / 2, 0)
        if p.y < -0.3 and 0.07 < abs(p.x) < 0.34 and j >= 2:
            return CRM
        return GLD
    shell(c, lc, Gp, th, mat_fn=matf, rim_mat=GLD, flush=True)
    comps.append(c)
    # upper cuisse plate (over): embossed feather scallops, its lower lip riding over the plate below
    tv2 = [0.0, 0.5, 0.86, 0.93, 1.0]
    zt = [0.40 if lc(u, 0)[0].y > -0.3 else 0.30 for u in us]
    G2 = [[(u, lerp(zt[i], -0.06, t)) for i, u in enumerate(us)] for t in tv2]
    c2 = Comp(bevel=0.013, segs=1, angle=30, mk={GLD: MK_SCALLOP})
    shell(c2, lc, G2, lambda j, i, u, v: 0.055 + (0.02 if j >= 3 else 0.0),
          lift=lambda j, i, u, v: 0.02 + 0.06 * tv2[j] ** 1.5, mat=GLD, rim_mat=GLD, flush=True,
          mk=lambda j, i, m: MK_SCALLOP if j <= 1 else 0)
    comps.append(c2)
    P, N = lc(L["front_mid"], 0.18)
    gem(c2, P + N * 0.105, N, UP, 0.1, 0.1, 0.045, sides=6, mat=RBY)
    b = Comp(bevel=0.012, segs=1, angle=30, mk={GLD: MK_PLATE})
    ub = [L["corner_ob"] + (L["back_in"] - 0.025 - L["corner_ob"]) * i / 6 for i in range(7)]
    shell(b, lc, [[(u, z) for u in ub] for z in (-0.02, 0.10, 0.30)], 0.05, mat=GLD, rim_mat=GLD, flush=True)
    comps.append(b)
    return comps, G, fx


def build_lower_leg_legs():
    comps, G, fx = [], GlowSet(), []
    su = limb_chart(r=0.1, clear=SUIT_CL)
    undersuit_box(comps, su, limb_cols(su), [-0.3, 0.0, 0.3, 0.55])
    lc = limb_chart(r=0.1)
    L = lc.stations
    nu = 10
    us = [0.025 + (L["corner_ob"] - 0.025) * i / nu for i in range(nu + 1)]
    tvs = [0.0, 0.1, 0.5, 0.85, 1.0]
    Gp = [[(u, lerp(-0.34, 0.30, t)) for u in us] for t in tvs]
    c = Comp(bevel=0.013, segs=1, angle=30, mk={GLD: MK_PLATE, CRM: MK_FLAME})

    def th(j, i, u, v):
        p, _ = lc(u, 0)
        ridge = 0.04 * max(0.0, 1 - abs(p.x) / 0.26) if p.y < -0.3 else 0.0
        return 0.06 + ridge + (0.018 if j in (0, 4) else 0.0)

    def matf(j, i):
        p, _ = lc((us[i] + us[i + 1]) / 2, 0)
        if p.y < -0.3 and abs(p.x) < 0.28 and j in (1, 2):
            return CRM
        return GLD
    shell(c, lc, Gp, th, mat_fn=matf, rim_mat=GLD, flush=True)
    comps.append(c)
    b = Comp(bevel=0.012, segs=1, angle=30, mk={GLD: MK_PLATE})
    ub = [L["corner_ob"] + (L["back_in"] - 0.025 - L["corner_ob"]) * i / 6 for i in range(7)]
    shell(b, lc, [[(u, z) for u in ub] for z in (-0.34, -0.1, 0.06)], 0.05, mat=GLD, rim_mat=GLD, flush=True)
    comps.append(b)
    # knee cop: a gold kite with engraved sun rays, a raised rim and a ruby
    kc = Comp(bevel=0.013, segs=2, angle=32, mk={GLD: MK_PLATE})
    zs = [0.02, 0.06, 0.12, 0.28, 0.44, 0.60, 0.74]
    hws = [0.10, 0.18, 0.28, 0.42, 0.35, 0.20, 0.05]
    nk = 8
    Gk = [[(0.5 + (-1 + 2 * i / nk) * hw, z) for i in range(nk + 1)] for z, hw in zip(zs, hws)]

    def kth(j, i, u, v):
        s_ = abs(-1 + 2 * i / nk)
        return 0.055 + 0.055 * (1 - s_) ** 1.3 + (0.02 if j <= 1 else 0.0)

    def klift(j, i, u, v):
        return 0.10 + 0.08 * smooth((v - 0.2) / 0.4)
    shell(kc, lc, Gk, kth, lift=klift, mat=GLD, rim_mat=GLD, flush=True, mk=lambda j, i, m: 0 if j == 0 else MK_PLATE)
    P, N = lc(0.5, 0.34)
    gem(kc, P + N * (klift(0, 0, 0.5, 0.34) + 0.11), N, UP, 0.12, 0.14, 0.05, sides=6, mat=RBY)
    comps.append(kc)
    sp = Comp(shade="smooth")
    for x in (0.15, 0.85):
        pts = []
        for z in (0.27, 0.05, -0.15, -0.34):
            P, N = lc(x, z)
            pts.append(P + N * 0.075)
        horn(sp, pts, 0.03, sides=4, flat=0.6, taper=0.0, r_tip=0.03, mat=GLD, up=Vector((0, -1, 0)))
    comps.append(sp)
    # feather flare at the knee: two layers on the outer side sweeping back and up
    fth = Comp(shade="smooth")
    for k, (z, Lf, off, rise, tone) in enumerate(((0.36, 0.60, 0.07, 30, -0.3), (0.22, 0.52, 0.07, 30, -0.3),
                                                  (0.42, 0.56, 0.11, 22, 0.25), (0.29, 0.48, 0.11, 22, 0.25),
                                                  (0.16, 0.40, 0.11, 22, 0.25))):
        P, N = lc(L["outer_mid"] - 0.16, z)
        feather(fth, P + N * off, N, Vector((0, 1.0, 0.55)), Lf, 0.25, th=0.058, rise=rise, curl=-8, sink=0.02,
                st=FST_M, tone=tone, rnd=0.2 * k)
    comps.append(fth)
    return comps, G, fx


# ----- Boots -------------------------------------------------------------------------------------------
def build_lower_leg_boots():
    comps, G, fx = [], GlowSet(), []
    lc = limb_chart(r=0.1)
    L = lc.stations
    nu = 12
    us = [0.025 + (L["total"] - 0.05) * i / nu for i in range(nu + 1)]
    tvs = [0.0, 0.08, 0.14, 0.6, 1.0]
    Gp = []
    for t in tvs:
        row = []
        for u in us:
            f = u / L["total"]
            tip = 0.10 * max(0.0, 1 - abs(2 * ((f * 4) % 1.0) - 1) ** 1.2)
            row.append((u, lerp(-0.47, -0.22 + tip, t)))
        Gp.append(row)
    c = Comp(bevel=0.012, segs=1, angle=30, mk={GLD: MK_PLATE, CRM: MK_FLAME})
    shell(c, lc, Gp, lambda j, i, u, v: 0.055 + (0.02 if j <= 1 else 0.0),
          lift=lambda j, i, u, v: 0.10 + 0.05 * tvs[j] ** 2, mat_fn=lambda j, i: CRM if j == 2 else GLD, rim_mat=GLD,
          flush=True)
    comps.append(c)
    fth = Comp(shade="smooth")
    for k, (z, Lf, off, tone) in enumerate(((-0.26, 0.46, 0.13, -0.2), (-0.36, 0.40, 0.16, 0.1), (-0.45, 0.32, 0.18, 0.35))):
        P, N = lc(L["outer_mid"] + 0.12, z)
        feather(fth, P + N * off, N, Vector((0, 1.0, 0.5)), Lf, 0.23, th=0.055, rise=20, curl=-8, sink=0.02,
                st=FST_M, tone=tone, rnd=0.3 * k)
    P, N = lc(L["front_mid"], -0.30)
    gem(fth, P + N * 0.19, N, UP, 0.09, 0.09, 0.04, sides=6, mat=RBY)
    comps.append(fth)
    return comps, G, fx


def build_foot():
    """Talon boots: gold sabaton lames with an enamel middle lame, a gold toe cap with a ruby, three big gold
    talons over the toe, a side talon and a heel spur."""
    comps, G, fx = [], GlowSet(), []
    prof = [(-0.47, 0.15), (-0.2, 0.15), (0.28, 0.15), (0.40, 0.13), (0.47, 0.08), (0.5, 0.0), (0.5, -0.13)]
    pc = profile_chart(prof)
    La = pc.length
    for k, (y0, y1, lift0) in enumerate(((0.52, 0.10, 0.02), (0.14, -0.20, 0.05), (-0.16, -0.45, 0.08))):
        c = Comp(bevel=0.012, segs=1, angle=34, mk={GLD: MK_PLATE, CRM: MK_FLAME})
        us = [La * i / 6 for i in range(7)]
        tvs = [0.0, 0.8, 0.9, 1.0]
        Gp = [[(u, lerp(y0, y1, t)) for u in us] for t in tvs]
        shell(c, pc, Gp, lambda j, i, u, v: 0.05 + (0.018 if j >= 2 else 0.0),
              lift=lambda j, i, u, v, l0=lift0, tvs=tvs: l0 + 0.03 * tvs[j],
              mat_fn=lambda j, i, k=k: (CRM if k == 1 else GLD) if j == 0 else GLD, rim_mat=GLD, flush=True)
        comps.append(c)
    tc = Comp(bevel=0.012, segs=1, angle=30, mk={GLD: MK_PLATE})
    fc = lt_chart(-1)
    xs = [-0.47 + 0.97 * i / 6 for i in range(7)]
    shell(tc, fc, [[(x, z) for x in xs] for z in (-0.14, 0.0, 0.16)], 0.06,
          lift=lambda j, i, u, v: 0.07, mat=GLD, rim_mat=GLD, flush=False)
    P, N = fc(0.02, 0.02)
    gem(tc, P + N * 0.135, N, UP, 0.1, 0.1, 0.045, sides=6, mat=RBY)
    comps.append(tc)
    cl = Comp(shade="smooth")
    for x, s_ in ((-0.30, 0.95), (0.02, 1.1), (0.32, 0.95)):
        b = Vector((x, -0.5 - CL - 0.12, 0.04))
        horn(cl, curve_pts(b, b + Vector((0, -0.14 * s_, 0.05)), b + Vector((0, -0.28 * s_, -0.04)),
                           b + Vector((0, -0.31 * s_, -0.18)), 8), 0.08, sides=6, taper=1.1, mat=GLD)
    b = Vector((0.5 + CL + 0.06, -0.2, 0.05))
    horn(cl, curve_pts(b, b + Vector((0.1, -0.06, 0.02)), b + Vector((0.18, -0.12, -0.04)),
                       b + Vector((0.2, -0.16, -0.12)), 6), 0.055, sides=6, taper=1.1, mat=GLD)
    b = Vector((0.1, 0.5 + CL + 0.03, 0.05))
    horn(cl, curve_pts(b, b + Vector((0, 0.11, 0.0)), b + Vector((0, 0.2, -0.04)), b + Vector((0, 0.26, -0.13)), 6),
         0.06, sides=6, taper=1.0, mat=GLD)
    comps.append(cl)
    return comps, G, fx

# ===========================================================================
# ASSEMBLY
# ===========================================================================
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
coll_armor = bpy.data.collections.new("Armor")
scene.collection.children.link(coll_armor)
coll_proxy = bpy.data.collections.new("R15_Proxy_NotExported")
scene.collection.children.link(coll_proxy)
coll_work = bpy.data.collections.new("Work")
scene.collection.children.link(coll_work)


def make_materials():
    mats = []
    for i, name in enumerate(MAT_NAMES):
        m = bpy.data.materials.new(f"{PREFIX}_{name}")
        nt = m.node_tree
        bs = nt.nodes["Principled BSDF"]
        bs.inputs["Base Color"].default_value = rgba(PREVIEW_RGB[i])
        bs.inputs["Roughness"].default_value = 0.4 if i in (GLD, RBY) else 0.7
        if i == GLD:
            bs.inputs["Metallic"].default_value = 0.5
        if i == FTH:     # preview the per-feather gradient
            at = nt.nodes.new("ShaderNodeAttribute")
            at.attribute_name = "Detail"
            sep = nt.nodes.new("ShaderNodeSeparateColor")
            nt.links.new(at.outputs["Color"], sep.inputs["Color"])
            r = nt.nodes.new("ShaderNodeValToRGB")
            el = r.color_ramp.elements
            stops = [(0.0, (96, 8, 26)), (0.35, (206, 46, 30)), (0.6, (246, 120, 32)), (0.82, (255, 196, 70)),
                     (1.0, (255, 240, 160))]
            el[0].position, el[0].color = stops[0][0], rgba(stops[0][1])
            el[1].position, el[1].color = stops[-1][0], rgba(stops[-1][1])
            for pos, col in stops[1:-1]:
                e = el.new(pos)
                e.color = rgba(col)
            nt.links.new(sep.outputs["Red"], r.inputs["Fac"])
            nt.links.new(r.outputs["Color"], bs.inputs["Base Color"])
        mats.append(m)

    def glow_mat(name, col):
        g = bpy.data.materials.new(name)
        bs = g.node_tree.nodes["Principled BSDF"]
        bs.inputs["Base Color"].default_value = (0, 0, 0, 1)
        bs.inputs["Emission Color"].default_value = rgba(col)
        bs.inputs["Emission Strength"].default_value = 1.6
        return g
    return mats, glow_mat(f"{PREFIX}_Glow", GLOW), glow_mat(f"{PREFIX}_GlowHot", HOT)


MATS, GLOW_MAT, HOT_MAT = make_materials()


def select_only(objs, active=None):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def finish(name, comps, part, materials):
    """Finish each component on its own (bevel with hardened normals, shading), then join them
    into one mesh per body part, placed at the part's rest position."""
    objs = []
    for k, c in enumerate(comps):
        if not len(c.bm.faces):
            c.bm.free()
            continue
        c.bm.normal_update()
        me = bpy.data.meshes.new(f"{name}_c{k}")
        c.bm.to_mesh(me)
        c.bm.free()
        for m in materials:
            me.materials.append(m)
        ob = bpy.data.objects.new(me.name, me)
        coll_work.objects.link(ob)
        flat = c.shade == "flat"
        for p in me.polygons:
            p.use_smooth = not flat
        if c.shade == "smooth":
            me.set_sharp_from_angle(angle=math.radians(48))
        elif c.facet > 0:
            me.set_sharp_from_angle(angle=math.radians(c.facet))
        if c.bevel > 0:
            mod = ob.modifiers.new("Bevel", "BEVEL")
            mod.width = c.bevel
            mod.segments = c.segs
            mod.limit_method = "ANGLE"
            mod.angle_limit = math.radians(c.angle)
            mod.profile = c.profile
            mod.harden_normals = c.shade == "harden"
            mod.use_clamp_overlap = True
        objs.append(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in objs:
        if ob.modifiers:
            new = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
            old = ob.data
            ob.modifiers.clear()
            ob.data = new
            bpy.data.meshes.remove(old)
    if os.environ.get("COMPTRIS"):
        print("  comps", name, sorted(((sum(len(p.vertices) - 2 for p in o.data.polygons)) for o in objs), reverse=True)[:12])
    select_only(objs)
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    for cl in list(ob.users_collection):
        cl.objects.unlink(ob)
    coll_armor.objects.link(ob)
    ob.location = part_pos(part)
    ob["body_part"] = part
    return ob


def finish_glow(name, c, part, mat):
    if not len(c.bm.faces):
        c.bm.free()
        return None
    me = bpy.data.meshes.new(name)
    c.bm.normal_update()
    c.bm.to_mesh(me)
    c.bm.free()
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = False
        p.material_index = 0
    ob = bpy.data.objects.new(name, me)
    coll_armor.objects.link(ob)
    ob.location = part_pos(part)
    ob["body_part"] = part
    return ob


SPEC = [  # (piece, part, builder name, mirrored pair?, mesh label (default: the body part))
    ("Helmet", "Head", "build_head", False, None),
    ("Chest", "UpperTorso", "build_upper_torso", False, None),
    ("Chest", "UpperTorso", "build_wings", False, "Wings"),
    ("Chest", "LowerTorso", "build_lower_torso", False, None),
    ("Chest", "UpperArm", "build_upper_arm", True, None),
    ("Chest", "LowerArm", "build_lower_arm", True, None),
    ("Legs", "UpperLeg", "build_upper_leg", True, None),
    ("Legs", "LowerLeg", "build_lower_leg_legs", True, None),
    ("Boots", "LowerLeg", "build_lower_leg_boots", True, None),
    ("Boots", "Foot", "build_foot", True, None),
]


def mirror_fx(e):
    d = dict(e)
    d["pos"] = Vector((-e["pos"].x, e["pos"].y, e["pos"].z))
    d["dir"] = Vector((-e["dir"].x, e["dir"].y, e["dir"].z))
    return d


armor_objs, glow_objs, FX = [], [], []
for piece, part, bname, pair, label in SPEC:
    builder = globals().get(bname)
    if builder is None:
        continue
    comps, gl, emit = builder()
    if pair:
        sides = [("Left", comps, gl, emit),
                 ("Right", [c.mirrored() for c in comps], gl.mirrored(), [mirror_fx(e) for e in emit])]
    else:
        sides = [("", comps, gl, emit)]
    for side, cs, g, em in sides:
        full = side + part
        base = f"{PREFIX}_{piece}_{label or full}"
        armor_objs.append(finish(base, cs, full, MATS))
        for comp, suffix, mat in ((g.o, "_Glow", GLOW_MAT), (g.h, "_Hot_Glow", HOT_MAT)):
            go = finish_glow(base + suffix, comp, full, mat)
            if go:
                glow_objs.append(go)
        for e in em:
            FX.append(dict(e, part=full, piece=piece,
                           name=(side.lower() + "_" if side else "") + e.get("name", e["kind"])))
    log("built", piece, part, label or "")

for o in list(coll_work.objects):
    bpy.data.objects.remove(o)


def tri_count(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


TRIS = {o.name: tri_count(o) for o in armor_objs + glow_objs}
log("TRIS total", sum(TRIS.values()))
for k, v in sorted(TRIS.items()):
    print("   ", k, v)

# ---------------------------------------------------------------------------
# Body proxy for previews and pose checks (never exported)
# ---------------------------------------------------------------------------
body_mat = bpy.data.materials.new("Proxy_Body")
body_mat.use_nodes = True
body_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = rgba((150, 156, 168))
body_mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
PROXY = {}
for n in PARTS:
    d = BODY[n]
    me = bpy.data.meshes.new("Proxy_" + n)
    me.from_pydata([s2b(v) for v in d["verts"]], [], d["faces"])
    me.materials.append(body_mat)
    ob = bpy.data.objects.new("Proxy_" + n, me)
    coll_proxy.objects.link(ob)
    ob.location = part_pos(n)
    PROXY[n] = ob


_bm = bmesh.new()
for j in range(13):
    r_, z_ = head_profile(HEAD_S_MAX * j / 12)
    for i in range(32):
        a = 2 * math.pi * i / 32
        _bm.verts.new((r_ * math.cos(a), r_ * math.sin(a), z_))
bmesh.ops.convex_hull(_bm, input=_bm.verts)
me = bpy.data.meshes.new("Proxy_Head")
_bm.to_mesh(me)
_bm.free()
me.materials.append(body_mat)
ob = bpy.data.objects.new("Proxy_Head", me)
coll_proxy.objects.link(ob)
ob.location = part_pos("Head")
PROXY["Head"] = ob


# ===========================================================================
# PAINTERLY BAKE: colour + icon lighting in one atlas per group, on unique UVs (the chest kit's
# approved recipe, extended). Baked masks drive the paint: ambient occlusion darkens overlaps and
# crevices, a small-radius occlusion pass finds cavities, the Bevel node finds convex edges for
# painted edge highlights. Obsidian shades toward blue-violet, gold toward warm brown, scales use
# their own root-to-tip gradient with per-scale jitter and painted keel/tip highlights.
# ===========================================================================
KEY = Vector((0.0, -0.55, 0.83)).normalized()       # symmetric: the set looks the same left/right
GLINT = Vector((0.0, -0.42, 0.91)).normalized()
RIM = Vector((0.0, 0.85, 0.35)).normalized()


def atlas_of(o):
    """Six 1024 atlases: helmet, torso (Upper + LowerTorso), wings, arms, legs, boots."""
    if "_Wings" in o.name:
        return "wings"
    piece, part = o.name.split("_")[1], o["body_part"]
    if piece == "Helmet":
        return "helmet"
    if piece == "Chest":
        return "torso" if part.endswith("Torso") else "arms"
    return "legs" if piece == "Legs" else "boots"


class NB:
    """Tiny node-tree builder: every call returns an output socket."""

    def __init__(self, mat):
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.geo = self.nt.nodes.new("ShaderNodeNewGeometry")
        at = self.nt.nodes.new("ShaderNodeAttribute")
        at.attribute_name = "Detail"
        sep = self.nt.nodes.new("ShaderNodeSeparateColor")
        self.nt.links.new(at.outputs["Color"], sep.inputs["Color"])
        self.R, self.G, self.B = sep.outputs["Red"], sep.outputs["Green"], sep.outputs["Blue"]
        self.A = at.outputs["Alpha"]
        at2 = self.nt.nodes.new("ShaderNodeAttribute")
        at2.attribute_name = "Motif"
        sep2 = self.nt.nodes.new("ShaderNodeSeparateColor")
        self.nt.links.new(at2.outputs["Color"], sep2.inputs["Color"])
        self.MU, self.MV, self.MK = sep2.outputs["Red"], sep2.outputs["Green"], sep2.outputs["Blue"]

    def _in(self, sock, val):
        if isinstance(val, bpy.types.NodeSocket):
            self.nt.links.new(val, sock)
        else:
            sock.default_value = val

    def math(self, op, a, b=0.0, c=None, clamp_=False):
        n = self.nt.nodes.new("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp_
        self._in(n.inputs[0], a)
        self._in(n.inputs[1], b)
        if c is not None:
            self._in(n.inputs[2], c)
        return n.outputs[0]

    def lin(self, const, *terms):
        acc = const
        for coef, s in terms:
            acc = self.math("MULTIPLY_ADD", s, coef, acc)
        return acc

    def remap(self, v, a, b, lo, hi, clamp_=True):
        n = self.nt.nodes.new("ShaderNodeMapRange")
        n.clamp = clamp_
        self._in(n.inputs["Value"], v)
        n.inputs["From Min"].default_value, n.inputs["From Max"].default_value = a, b
        n.inputs["To Min"].default_value, n.inputs["To Max"].default_value = lo, hi
        return n.outputs["Result"]

    def smoothstep(self, v, a, b):
        n = self.nt.nodes.new("ShaderNodeMapRange")
        n.interpolation_type = "SMOOTHSTEP"
        self._in(n.inputs["Value"], v)
        n.inputs["From Min"].default_value, n.inputs["From Max"].default_value = a, b
        return n.outputs["Result"]

    def line(self, dist, w):
        """1 on the line (dist 0), falling to 0 at |dist| >= w."""
        return self.math("SUBTRACT", 1.0, self.smoothstep(self.math("ABSOLUTE", dist), 0.0, w))

    def fract(self, x):
        return self.math("FRACT", x)

    def tri(self, x):
        return self.math("SUBTRACT", 1.0, self.math("ABSOLUTE", self.math("MULTIPLY_ADD", x, 2.0, -1.0)))

    def kind(self, k):
        return self.math("COMPARE", self.MK, k * 0.1, 0.04)

    def dot(self, vec_sock, direction):
        n = self.nt.nodes.new("ShaderNodeVectorMath")
        n.operation = "DOT_PRODUCT"
        self.nt.links.new(vec_sock, n.inputs[0])
        n.inputs[1].default_value = Vector(direction).normalized()
        return n.outputs["Value"]

    def vscale(self, vec_sock, sc):
        n = self.nt.nodes.new("ShaderNodeVectorMath")
        n.operation = "MULTIPLY"
        self.nt.links.new(vec_sock, n.inputs[0])
        n.inputs[1].default_value = sc
        return n.outputs["Vector"]

    def noise(self, scale, detail=1.0, rough=0.5, distort=0.2, stretch=(1, 1, 1)):
        n = self.nt.nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        n.inputs["Distortion"].default_value = distort
        self.nt.links.new(self.vscale(self.geo.outputs["Position"], stretch), n.inputs["Vector"])
        return n.outputs["Fac"]

    def ramp(self, fac, stops):
        n = self.nt.nodes.new("ShaderNodeValToRGB")
        el = n.color_ramp.elements
        el[0].position, el[0].color = stops[0][0], rgba(stops[0][1])
        el[1].position, el[1].color = stops[-1][0], rgba(stops[-1][1])
        for pos, col in stops[1:-1]:
            e = el.new(pos)
            e.color = rgba(col)
        self._in(n.inputs["Fac"], fac)
        return n.outputs["Color"]

    def mix(self, fac, a, b, blend="MIX"):
        n = self.nt.nodes.new("ShaderNodeMix")
        n.data_type = "RGBA"
        n.blend_type = blend
        self._in(n.inputs["Factor"], fac)
        self._in(n.inputs[6], a if isinstance(a, bpy.types.NodeSocket) else rgba(a))
        self._in(n.inputs[7], b if isinstance(b, bpy.types.NodeSocket) else rgba(b))
        return n.outputs[2]

    def ao(self, dist, samples=8):
        n = self.nt.nodes.new("ShaderNodeAmbientOcclusion")
        n.samples = samples
        n.inputs["Distance"].default_value = dist
        return n.outputs["AO"]

    def bevel_edge(self, radius):
        bv = self.nt.nodes.new("ShaderNodeBevel")
        bv.samples = 6
        bv.inputs["Radius"].default_value = radius
        d = self.nt.nodes.new("ShaderNodeVectorMath")
        d.operation = "DOT_PRODUCT"
        self.nt.links.new(bv.outputs["Normal"], d.inputs[0])
        self.nt.links.new(self.geo.outputs["Normal"], d.inputs[1])
        return self.remap(d.outputs["Value"], 0.995, 0.86, 0.0, 1.0)

    def bump(self, height, strength=1.0, dist=0.016):
        n = self.nt.nodes.new("ShaderNodeBump")
        n.inputs["Strength"].default_value = strength
        n.inputs["Distance"].default_value = dist
        self._in(n.inputs["Height"], height)
        return n.outputs["Normal"]

    def emit(self, col):
        em = self.nt.nodes.new("ShaderNodeEmission")
        self._in(em.inputs["Color"], col)
        out = self.nt.nodes.new("ShaderNodeOutputMaterial")
        self.nt.links.new(em.outputs["Emission"], out.inputs["Surface"])


def motif_relief(b):
    """Painted relief from the Motif attribute. Returns (H, F, F2, W, ENG, K2): relief height (0.5 flat),
    the enamel flame masks (outer, inner core), the cloisonne wire mask, the engraved-line mask and the
    flame-kind mask. Kinds: 1 plate (border groove + bead + sun rays, from Detail R/G fractions),
    2 flames (stud coords), 3 radial (rays + ring, Detail R radius / G angle), 4 feather scallops (studs)."""
    R, Gc, MU, MV = b.R, b.G, b.MU, b.MV
    k1, k2, k3, k4 = b.kind(MK_PLATE), b.kind(MK_FLAME), b.kind(MK_RADIAL), b.kind(MK_SCALLOP)
    dE = b.math("MINIMUM", b.math("MINIMUM", R, b.math("SUBTRACT", 1.0, R)),
                b.math("MINIMUM", Gc, b.math("SUBTRACT", 1.0, Gc)))
    groove = b.line(b.math("SUBTRACT", dE, 0.12), 0.03)
    bead = b.line(b.math("SUBTRACT", dE, 0.06), 0.018)
    ang = b.math("ARCTAN2", b.math("SUBTRACT", Gc, 0.5), b.math("ADD", R, 0.35))
    rays = b.math("MULTIPLY", b.line(b.math("SINE", b.math("MULTIPLY", ang, 11.0)), 0.2), b.smoothstep(dE, 0.16, 0.22))
    H1 = b.lin(0.5, (-0.42, groove), (0.25, bead), (-0.32, rays))
    eng1 = b.math("MAXIMUM", groove, rays)
    fy = b.fract(b.math("MULTIPLY", MV, 1 / 0.34))
    fx = b.fract(b.math("MULTIPLY_ADD", MU, 1 / 0.26, b.math("MULTIPLY", fy, 0.2)))
    tr = b.tri(fx)
    top = b.math("MULTIPLY_ADD", b.math("POWER", tr, 1.5), 0.6, 0.28)
    d1 = b.math("SUBTRACT", top, fy)
    F = b.smoothstep(d1, -0.015, 0.015)
    tr2 = b.math("MAXIMUM", b.math("MULTIPLY_ADD", tr, 1.7, -0.7), 0.0)
    top2 = b.math("MULTIPLY_ADD", b.math("POWER", tr2, 1.3), 0.45, 0.14)
    F2 = b.math("MULTIPLY", b.smoothstep(b.math("SUBTRACT", top2, fy), -0.015, 0.015), b.smoothstep(tr, 0.4, 0.5))
    W = b.math("MAXIMUM", b.line(d1, 0.028), b.math("MAXIMUM", b.line(fy, 0.03), b.line(b.math("SUBTRACT", 1.0, fy), 0.03)))
    H2 = b.lin(0.5, (0.2, F), (0.1, F2), (0.12, W))
    sec = b.math("SUBTRACT", b.fract(b.math("MULTIPLY_ADD", Gc, 16.0, 0.5)), 0.5)
    rmask = b.math("MULTIPLY", b.smoothstep(R, 0.2, 0.28), b.math("SUBTRACT", 1.0, b.smoothstep(R, 0.84, 0.92)))
    ray3 = b.math("MULTIPLY", b.line(sec, 0.08), rmask)
    ring3 = b.line(b.math("SUBTRACT", R, 0.56), 0.035)
    H3 = b.lin(0.5, (-0.36, ray3), (-0.42, ring3))
    eng3 = b.math("MAXIMUM", ray3, ring3)
    rowi = b.math("FLOOR", b.math("MULTIPLY", MV, 1 / 0.13))
    sx = b.fract(b.math("ADD", b.math("MULTIPLY", MU, 1 / 0.17), b.fract(b.math("MULTIPLY", rowi, 0.5))))
    sy = b.fract(b.math("MULTIPLY", MV, 1 / 0.13))
    cx = b.math("MULTIPLY_ADD", sx, 2.0, -1.0)
    edge = b.math("SUBTRACT", sy, b.math("MULTIPLY", b.math("MULTIPLY", cx, cx), 0.62))
    body = b.smoothstep(edge, -0.02, 0.05)
    H4 = b.lin(0.42, (0.3, b.math("MULTIPLY", body, b.math("MULTIPLY_ADD", sy, -0.7, 1.0))), (-0.26, b.line(edge, 0.035)))
    H = b.lin(0.5, (1.0, b.math("MULTIPLY", k1, b.math("SUBTRACT", H1, 0.5))),
              (1.0, b.math("MULTIPLY", k2, b.math("SUBTRACT", H2, 0.5))),
              (1.0, b.math("MULTIPLY", k3, b.math("SUBTRACT", H3, 0.5))),
              (1.0, b.math("MULTIPLY", k4, b.math("SUBTRACT", H4, 0.5))))
    ENG = b.math("MAXIMUM", b.math("MULTIPLY", k1, eng1), b.math("MULTIPLY", k3, eng3))
    return (H, b.math("MULTIPLY", F, k2), b.math("MULTIPLY", F2, k2), b.math("MULTIPLY", W, k2), ENG, k2, fy)


def build_bake_material(m, idx):
    b = NB(m)
    relief = idx in (GLD, IVY, CRM)
    if relief:
        H, F, F2, W, ENG, K2, FY = motif_relief(b)
        Nrm = b.bump(H, 1.0, 0.016)
        rshade = b.remap(H, 0.12, 0.88, 0.62, 1.12)
    else:
        Nrm = b.geo.outputs["Normal"]
    key = b.math("MAXIMUM", b.dot(Nrm, KEY), 0.0)
    sky = b.math("MULTIPLY_ADD", b.dot(Nrm, UP), 0.5, 0.5)
    light = b.math("ADD", b.math("MULTIPLY_ADD", key, 0.55, 0.14), b.math("MULTIPLY", sky, 0.32))
    ao = b.remap(b.ao(0.35, 8), 0.12, 1.0, 0.22, 1.0)
    cav = b.remap(b.ao(0.07, 8), 0.35, 1.0, 0.45, 1.0)
    occl = b.math("MULTIPLY", ao, cav)
    S = b.math("MULTIPLY", light, occl, clamp_=True)
    patches = b.math("MULTIPLY_ADD", b.noise(1.4, 1.0, 0.4, 0.3), 0.14, -0.07)
    strokes = b.math("MULTIPLY_ADD", b.noise(5.0, 1.5, 0.5, 0.6, (1.0, 1.0, 3.2)), 0.07, -0.035)
    paint = b.math("ADD", patches, strokes)
    edge = b.math("MULTIPLY", b.bevel_edge(0.018), b.smoothstep(ao, 0.55, 0.9))
    glint = b.smoothstep(b.dot(Nrm, GLINT), 0.80, 0.97)
    rim = b.math("MAXIMUM", b.dot(Nrm, RIM), 0.0)
    edge_up = b.math("MULTIPLY", edge, b.math("MULTIPLY_ADD", sky, 0.5, 0.5))

    def tint_shade(base, lo=(46, 30, 72), mid=(172, 150, 160), hi=(255, 244, 230)):
        sh = b.ramp(b.math("ADD", S, b.math("MULTIPLY", paint, 0.6)), [(0.0, lo), (0.5, mid), (1.0, hi)])
        return b.mix(1.0, base, sh, "MULTIPLY")

    def gold_col():
        g = b.ramp(b.math("ADD", S, b.math("MULTIPLY", paint, 0.6)),
                   [(0.0, (36, 14, 8)), (0.18, (84, 38, 14)), (0.36, (150, 78, 24)), (0.54, (206, 128, 40)),
                    (0.70, (236, 172, 62)), (0.84, (252, 214, 118)), (1.0, (255, 244, 200))])
        mid = b.math("SUBTRACT", 1.0, b.math("ABSOLUTE", b.math("MULTIPLY", b.math("SUBTRACT", S, 0.42), 2.6)), clamp_=True)
        g = b.mix(b.math("MULTIPLY", mid, 0.22), g, (220, 92, 26))          # warm orange in the mid-tones
        g = b.mix(b.math("MULTIPLY", glint, 0.5), g, (255, 236, 170), "ADD")
        g = b.mix(b.math("MULTIPLY", edge_up, 0.85), g, (255, 246, 212))
        return g

    if idx == GLD:          # rich gold: brown/orange shading, warm highlights, engraved and embossed relief
        col = gold_col()
        col = b.mix(b.math("MULTIPLY", ENG, 0.45), col, (74, 34, 12))
        col = b.mix(b.math("MULTIPLY", F, 0.12), col, (255, 226, 150), "SCREEN")
        col = b.mix(1.0, col, rshade, "MULTIPLY")
    elif idx == IVY:        # ivory accents: cool lavender shadows, warm cream lights, painted gold filigree
        col = b.ramp(b.math("ADD", S, b.math("MULTIPLY", paint, 0.35)),
                     [(0.0, (92, 84, 112)), (0.2, (156, 146, 166)), (0.38, (198, 188, 192)), (0.55, (216, 204, 192)),
                      (0.72, (229, 217, 199)), (0.88, (237, 227, 208)), (1.0, (243, 235, 218))])
        col = b.mix(b.math("MULTIPLY", rim, 0.18), col, (16, 20, 44), "ADD")
        col = b.mix(b.math("MULTIPLY", ENG, 0.9), col, gold_col())
        col = b.mix(b.math("MULTIPLY", edge_up, 0.6), col, (250, 240, 216))
        col = b.mix(1.0, col, rshade, "MULTIPLY")
    elif idx == FTH:        # feathers: crimson root -> orange -> gold -> hot yellow tip, vane stripes, bright edges
        tone = b.math("MULTIPLY", b.math("MULTIPLY_ADD", b.MU, 2.0, -1.0), b.kind(MK_FEATHER))
        Rt = b.math("MULTIPLY_ADD", tone, 0.3, b.R, clamp_=True)
        base = b.ramp(Rt, [(0.0, (88, 6, 24)), (0.16, (140, 14, 30)), (0.34, (200, 38, 30)), (0.52, (238, 96, 28)),
                           (0.68, (252, 150, 38)), (0.82, (255, 200, 70)), (0.93, (255, 232, 130)), (1.0, (255, 248, 190))])
        base = b.mix(b.math("MULTIPLY", b.B, 0.14), base, (230, 80, 30))
        base = b.mix(1.0, base, b.math("MULTIPLY_ADD", b.B, 0.16, 0.9), "MULTIPLY")
        top = b.smoothstep(b.A, 0.85, 0.95)
        ac = b.math("ABSOLUTE", b.math("SUBTRACT", b.G, 0.5))
        vane = b.math("MULTIPLY", b.math("MULTIPLY", b.smoothstep(ac, 0.07, 0.11),
                                         b.math("SUBTRACT", 1.0, b.smoothstep(ac, 0.2, 0.27))),
                      b.math("MULTIPLY", b.math("SUBTRACT", 1.0, b.smoothstep(b.R, 0.55, 0.85)), top))
        base = b.mix(b.math("MULTIPLY", vane, 0.6), base, (150, 40, 44), "MULTIPLY")
        chev = b.remap(b.math("SINE", b.math("MULTIPLY", b.math("MULTIPLY_ADD", b.R, 10.0, b.math("MULTIPLY", ac, -5.0)),
                                             2 * math.pi)), -1.0, 1.0, 0.86, 1.0)
        base = b.mix(1.0, base, chev, "MULTIPLY")
        rach = b.math("MULTIPLY", b.math("SUBTRACT", 1.0, b.smoothstep(ac, 0.0, 0.04)), top)
        base = b.mix(b.math("MULTIPLY", rach, 0.6), base, (255, 214, 130))
        eb = b.line(b.math("SUBTRACT", b.A, 0.62), 0.18)
        base = b.mix(b.math("MULTIPLY", eb, 0.5), base, (255, 222, 136))
        under = b.math("SUBTRACT", 1.0, b.smoothstep(b.A, 0.3, 0.5))
        base = b.mix(b.math("MULTIPLY", under, 0.4), base, (110, 20, 34))
        col = tint_shade(base, (100, 40, 96), (218, 188, 182), (255, 250, 236))
        col = b.mix(b.math("MULTIPLY", edge_up, 0.5), col, (255, 226, 150))
    elif idx == BRZ:
        col = b.ramp(b.math("ADD", S, b.math("MULTIPLY", paint, 0.6)),
                     [(0.0, (26, 14, 8)), (0.4, (84, 50, 22)), (0.75, (150, 100, 46)), (1.0, (206, 160, 90))])
    elif idx == SUIT:       # dark wine mail undersuit that shows in every gap
        vo = b.nt.nodes.new("ShaderNodeTexVoronoi")
        vo.feature = "F1"
        vo.inputs["Scale"].default_value = 13.0
        b.nt.links.new(b.vscale(b.geo.outputs["Position"], (1.0, 1.0, 1.35)), vo.inputs["Vector"])
        ed = b.nt.nodes.new("ShaderNodeTexVoronoi")
        ed.feature = "DISTANCE_TO_EDGE"
        ed.inputs["Scale"].default_value = 13.0
        b.nt.links.new(b.vscale(b.geo.outputs["Position"], (1.0, 1.0, 1.35)), ed.inputs["Vector"])
        cell = b.ramp(vo.outputs["Distance"], [(0.05, (156, 44, 50)), (0.5, (118, 32, 42)), (0.9, (80, 22, 32))])
        line = b.remap(ed.outputs["Distance"], 0.0, 0.07, 1.0, 0.0)
        base = b.mix(b.math("MULTIPLY", line, 0.8), cell, (44, 12, 22))
        col = tint_shade(base, (26, 20, 38), (140, 124, 134), (250, 236, 228))
    elif idx == CRM:        # crimson/orange enamel with gold cloisonne flames
        base = b.ramp(b.math("ADD", b.noise(3.0, 1.0, 0.5, 0.4), b.math("MULTIPLY", paint, 1.5)),
                      [(0.25, (104, 12, 28)), (0.55, (156, 24, 36)), (0.8, (192, 44, 42))])
        base = b.mix(b.math("MULTIPLY", K2, b.math("MULTIPLY", FY, 0.35)), base, (214, 70, 30))
        base = b.mix(F, base, (246, 122, 30))
        base = b.mix(F2, base, (255, 206, 84))
        col = tint_shade(base, (40, 14, 44), (176, 146, 150), (255, 242, 232))
        col = b.mix(b.math("MULTIPLY", glint, 0.55), col, (255, 220, 200), "ADD")
        col = b.mix(W, col, gold_col())
        col = b.mix(b.math("MULTIPLY", edge_up, 0.45), col, (240, 130, 100))
        col = b.mix(1.0, col, rshade, "MULTIPLY")
    elif idx == RBY:        # ruby accents
        col = b.ramp(S, [(0.0, (40, 0, 12)), (0.35, (124, 6, 28)), (0.62, (214, 24, 52)), (0.84, (255, 92, 104)),
                         (1.0, (255, 214, 214))])
        col = b.mix(b.math("MULTIPLY", glint, 0.9), col, (255, 240, 240), "ADD")
        col = b.mix(b.math("MULTIPLY", edge_up, 0.5), col, (255, 170, 180))
    else:
        col = b.ramp(S, [(0.0, (12, 6, 8)), (1.0, (46, 22, 24))])
    target = b.nt.nodes.new("ShaderNodeTexImage")
    b.nt.nodes.active = target
    b.emit(col)
    return target


def unwrap(objs):
    for o in objs:
        while o.data.uv_layers:
            o.data.uv_layers.remove(o.data.uv_layers[0])
        o.data.uv_layers.new(name="UVMap")
    select_only(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=0.003, correct_aspect=True)
    bpy.ops.uv.pack_islands(rotate=True, margin=0.0025)
    bpy.ops.object.mode_set(mode="OBJECT")


def bake_all(objs):
    groups = {}
    for o in objs:
        groups.setdefault(atlas_of(o), []).append(o)
    targets = [build_bake_material(m, i) for i, m in enumerate(MATS)]
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 16
    scene.render.bake.margin = 16
    scene.render.bake.use_clear = True
    finals = {}
    for proxy in PROXY.values():          # the body darkens the plates' contact edges (AO) during the bake
        proxy.hide_render = False
    for group, members in sorted(groups.items()):
        unwrap(members)
        img = bpy.data.images.new(f"{SET}-{group}-bake", BAKE_WORK, BAKE_WORK, alpha=False)
        for t in targets:
            t.image = img
        select_only(members)
        t0 = time.time()
        bpy.ops.object.bake(type="EMIT")
        path = ROOT / "textures" / f"{SET}-{group}.png"
        img.filepath_raw = str(path)
        img.file_format = "PNG"
        img.save()
        log("baked", group, f"{time.time() - t0:.0f}s", len(members), "meshes")
        fm = bpy.data.materials.new(f"{PREFIX}_{group}")
        nt = fm.node_tree
        bs = nt.nodes["Principled BSDF"]
        bs.inputs["Roughness"].default_value = 0.72
        bs.inputs["Specular IOR Level"].default_value = 0.2
        tx = nt.nodes.new("ShaderNodeTexImage")
        tx.image = bpy.data.images.load(str(path))
        tx.image.name = f"{SET}-{group}.png"
        nt.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
        finals[group] = fm
    for group, members in groups.items():
        for o in members:
            o.data.materials.clear()
            o.data.materials.append(finals[group])
            for p in o.data.polygons:
                p.material_index = 0
    for o in objs + glow_objs:           # bake-only data; Roblox would read it as vertex colour
        for an in ("Detail", "Motif"):
            if an in o.data.color_attributes:
                o.data.color_attributes.remove(o.data.color_attributes[an])
    return groups


GROUPS = None
if not QUICK:
    GROUPS = bake_all(armor_objs)

# ===========================================================================
# EXPORTS, POLYGON REPORT, STUDIO INSTALL DATA
# ===========================================================================


def studio(v):
    return Vector((-v.x, v.z, v.y))


def clean_mesh(o):
    """Drop bevel-clamp slivers (zero-area faces) and vertices no face uses. Custom normals survive."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_area() < 1e-7], context="FACES_ONLY")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(o.data)
    bm.free()


FLAME_TEX, EMBER_TEX = "textures/vfx/flame.png", "textures/vfx/ember.png"


def r3(v):
    return [round(v[0], 3), round(v[1], 3), round(v[2], 3)]


def ns(*kp):
    """NumberSequence keypoints [time, value, envelope]."""
    return [[t, round(v, 3), round(e, 3)] for t, v, e in kp]


def cseq(*kp):
    """ColorSequence keypoints [time, [r, g, b]] (sRGB 0-255)."""
    return [[t, list(c)] for t, c in kp]


def emitter_props(e):
    """Full Roblox ParticleEmitter property values for one vfx entry (cartoon fire, not realistic)."""
    k, s, rate = e["kind"], e.get("size", 1.0), e.get("rate")
    base = {"Enabled": True, "LightEmission": 1, "LightInfluence": 0, "Brightness": 2, "Orientation": "FacingCamera",
            "EmissionDirection": "Top", "LockedToPart": False, "ZOffset": 0.3, "VelocityInheritance": 0,
            "Squash": ns((0, 0, 0), (1, 0, 0))}
    if k == "flame_plume":
        base.update(Texture=FLAME_TEX, Rate=rate or 24, Lifetime=[0.35, 0.65], Speed=[2.4 * s, 3.8 * s],
                    SpreadAngle=[14, 14],
                    Size=ns((0, 0.6 * s, 0.1 * s), (0.25, 1.15 * s, 0.15 * s), (0.7, 0.8 * s, 0.1 * s), (1, 0.15 * s, 0)),
                    Transparency=ns((0, 0.05, 0), (0.55, 0.25, 0), (1, 1, 0)),
                    Squash=ns((0, 0.25, 0), (1, 0.45, 0)),
                    Color=cseq((0, (255, 255, 255)), (0.45, (255, 224, 180)), (1, (255, 120, 70))),
                    Drag=1.6, Acceleration=[0, round(6 * s, 2), 0], Rotation=[-18, 18], RotSpeed=[-45, 45])
    elif k == "flame_sheet":
        base.update(Texture=FLAME_TEX, Rate=rate or 16, Lifetime=[0.3, 0.5], Speed=[1.2 * s, 2.2 * s],
                    SpreadAngle=[18, 6], Orientation="VelocityParallel",
                    Size=ns((0, 0.45 * s, 0.08 * s), (0.3, 0.8 * s, 0.1 * s), (1, 0.1 * s, 0)),
                    Transparency=ns((0, 0.1, 0), (0.6, 0.3, 0), (1, 1, 0)),
                    Squash=ns((0, 0.6, 0), (1, 0.9, 0)),
                    Color=cseq((0, (255, 250, 230)), (0.5, (255, 200, 150)), (1, (255, 110, 70))),
                    Drag=2.4, Acceleration=[0, round(4 * s, 2), 0], Rotation=[-10, 10], RotSpeed=[-20, 20])
    elif k == "flame_lick":
        base.update(Texture=FLAME_TEX, Rate=rate or 10, Lifetime=[0.3, 0.5], Speed=[1.4 * s, 2.2 * s],
                    SpreadAngle=[12, 12],
                    Size=ns((0, 0.35 * s, 0.05 * s), (0.3, 0.6 * s, 0.08 * s), (1, 0.08 * s, 0)),
                    Transparency=ns((0, 0.1, 0), (0.6, 0.3, 0), (1, 1, 0)),
                    Squash=ns((0, 0.3, 0), (1, 0.5, 0)),
                    Color=cseq((0, (255, 255, 255)), (0.5, (255, 214, 170)), (1, (255, 120, 70))),
                    Drag=1.8, Acceleration=[0, 4, 0], Rotation=[-15, 15], RotSpeed=[-30, 30])
    elif k == "embers_rise":
        base.update(Texture=EMBER_TEX, Rate=rate or 14, Lifetime=[1.4, 2.6], Speed=[1.2, 2.4], SpreadAngle=[35, 35],
                    Brightness=3, Size=ns((0, 0.16, 0.04), (0.6, 0.12, 0.03), (1, 0, 0)),
                    Transparency=ns((0, 0, 0), (0.75, 0.15, 0), (1, 1, 0)),
                    Color=cseq((0, (255, 246, 200)), (0.35, (255, 190, 80)), (1, (255, 90, 40))),
                    Drag=0.7, Acceleration=[0, 3, 0], Rotation=[0, 360], RotSpeed=[-120, 120])
    elif k == "ember_swirl":
        base.update(Texture=EMBER_TEX, Rate=rate or 16, Lifetime=[0.9, 1.5], Speed=[1.4, 2.2], SpreadAngle=[180, 180],
                    EmissionDirection="Front", Brightness=3, Size=ns((0, 0.13, 0.03), (0.5, 0.1, 0.02), (1, 0, 0)),
                    Transparency=ns((0, 0, 0), (0.7, 0.2, 0), (1, 1, 0)),
                    Color=cseq((0, (255, 250, 210)), (0.4, (255, 200, 90)), (1, (255, 100, 40))),
                    Drag=3.2, Acceleration=[0, 1.6, 0], Rotation=[0, 360], RotSpeed=[-360, 360])
    elif k == "heat_glow":
        base.update(Texture=EMBER_TEX, Rate=rate or 5, Lifetime=[1.2, 1.8], Speed=[0.2, 0.5], SpreadAngle=[20, 20],
                    LightEmission=0.8, Brightness=1, ZOffset=-0.6, Shape="Box", ShapeStyle="Volume",
                    ShapeInOut="Outward",
                    Size=ns((0, 1.6 * s, 0.3 * s), (0.5, 2.4 * s, 0.4 * s), (1, 2.8 * s, 0)),
                    Transparency=ns((0, 1, 0), (0.3, 0.86, 0), (0.7, 0.9, 0), (1, 1, 0)),
                    Color=cseq((0, (255, 170, 70)), (1, (255, 110, 40))),
                    Drag=0.5, Acceleration=[0, 0.8, 0], Rotation=[0, 360], RotSpeed=[-10, 10])
    for key in ("Speed", "Lifetime"):
        base[key] = [round(x, 3) for x in base[key]]
    return base


def vfx_entry(e):
    p, d = studio(e["pos"]), studio(e["dir"]).normalized()
    ref = Vector((0, 1, 0)) if abs(d.y) < 0.9 else Vector((1, 0, 0))
    ax = ref.cross(d).normalized()
    ent = {"name": e["name"], "kind": e["kind"], "piece": e["piece"], "body_part": e["part"], "note": e.get("note", "")}
    if e["kind"] == "light":
        ent.update({"class": "PointLight", "parent": "attachment", "attachment": {"position": r3(p)},
                    "properties": {"Brightness": e["brightness"], "Range": e["range"], "Color": e["color"],
                                   "Shadows": False}})
        return ent
    ent.update({"class": "ParticleEmitter", "parent": e.get("parent", "attachment")})
    if ent["parent"] == "attachment":
        ent["attachment"] = {"position": r3(p), "secondary_axis": r3(d), "axis": r3(ax)}
    else:
        ent["parent_part"] = f"{PREFIX}_{e['piece']}_{e['part']}"
    ent["properties"] = emitter_props(e)
    return ent


def export():
    objs = armor_objs + glow_objs
    for o in objs:
        clean_mesh(o)
    select_only(objs)
    bpy.ops.export_scene.gltf(filepath=str(ROOT / "exports" / "glb" / f"{SET}.glb"), export_format="GLB",
                              use_selection=True, export_apply=True)
    bpy.ops.export_scene.fbx(filepath=str(ROOT / "exports" / "fbx" / f"{SET}.fbx"), use_selection=True,
                             object_types={"MESH"}, axis_forward="-Z", axis_up="Y", path_mode="COPY",
                             embed_textures=True, add_leaf_bones=False, mesh_smooth_type="OFF")
    report = {"set": SET, "version": 2, "rarity": "Godly", "blender_version": bpy.app.version_string,
              "authoring": "final Roblox stud size; import at 1:1, do not scale", "pieces": {}}
    install = {"set": SET, "version": 2, "helmet": "full", "glow_color_srgb": list(GLOW),
               "glow_hot_color_srgb": list(HOT), "glow_material": "Neon",
               "textured_material": "SmoothPlastic (colour comes from TextureID)",
               "axes": "offset/size/position in Studio part-local axes (x = Blender -x, y = Blender z, z = Blender y)",
               "particle_textures": {"flame": FLAME_TEX, "ember": EMBER_TEX},
               "parts": {}, "vfx": [],
               "vfx_notes": ("Phoenix only. For parent 'attachment': add an Attachment to the character's body_part at "
                             "attachment.position (part-local), set Attachment.Axis = axis and SecondaryAxis = "
                             "secondary_axis, and parent the ParticleEmitter/PointLight to it (EmissionDirection 'Top' "
                             "emits along the attachment's +Y = secondary_axis; 'Front' = all around for the swirl). "
                             "For parent 'part': parent the emitter to that armour MeshPart (Shape Box fills it). "
                             "NumberSequence keypoints are [time, value, envelope]; ColorSequence keypoints are "
                             "[time, [r, g, b]] sRGB 0-255; ranges are [min, max]; Acceleration is world space. "
                             "Upload textures/vfx/*.png and use their asset ids as Texture. At these rates about 300 "
                             "particles are alive per player; halve Rate on low graphics quality. Glow parts: Neon, "
                             "Color = color_srgb.")}
    total = 0
    for o in objs:
        me = o.data
        tris = sum(len(p.vertices) - 2 for p in me.polygons)
        total += tris
        xs = [v.co for v in me.vertices]
        lo = Vector((min(c.x for c in xs), min(c.y for c in xs), min(c.z for c in xs)))
        hi = Vector((max(c.x for c in xs), max(c.y for c in xs), max(c.z for c in xs)))
        centre, size = (lo + hi) / 2, hi - lo
        piece = o.name.split("_")[1]
        kind = "glow" if o.name.endswith("_Glow") else "textured"
        report["pieces"].setdefault(piece, {})[o.name] = {"body_part": o["body_part"], "triangles": tris,
                                                          "vertices": len(me.vertices)}
        sc, ss = studio(centre), studio(size)
        ent = {"piece": piece, "body_part": o["body_part"], "kind": kind,
               "atlas": None if kind == "glow" else f"textures/{SET}-{atlas_of(o)}.png",
               "offset": [round(sc.x, 4), round(sc.y, 4), round(sc.z, 4)],
               "size": [round(abs(ss.x), 4), round(abs(ss.y), 4), round(abs(ss.z), 4)]}
        if kind == "glow":
            ent["color_srgb"] = list(HOT if o.name.endswith("_Hot_Glow") else GLOW)
        install["parts"][o.name] = ent
    for e in FX:
        install["vfx"].append(vfx_entry(e))
    report["triangles_total"] = total
    report["triangles_by_piece"] = {k: sum(v["triangles"] for v in d.values()) for k, d in report["pieces"].items()}
    report["largest_mesh"] = max(((n, v["triangles"]) for d in report["pieces"].values() for n, v in d.items()),
                                 key=lambda x: x[1])
    report["textures"] = {g: f"textures/{SET}-{g}.png ({BAKE_SIZE}x{BAKE_SIZE})" for g in sorted(set(map(atlas_of, armor_objs)))}
    report["vfx_count"] = {k: sum(1 for e in FX if e["kind"] == k) for k in sorted(set(e["kind"] for e in FX))}
    (ROOT / "polygon-report.json").write_text(json.dumps(report, indent=1))
    (ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=1))
    log("EXPORTED", total, "triangles")


if not QUICK:
    export()


# ===========================================================================
# PREVIEW RENDERS (Eevee, bright soft daylight like the chest kit previews)
# ===========================================================================
VFX_DIR = ROOT / "textures" / "vfx"


def make_vfx_textures():
    """Two stylized particle textures painted with numpy: a chunky cartoon flame (512) and an ember (256)."""
    import numpy as np
    VFX_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)

    def smooth_noise(n, cx, cy):
        g = rng.random((cy + 3, cx + 3)).astype(np.float32)
        ys, xs = np.linspace(0, cy, n), np.linspace(0, cx, n)
        y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int)
        fy, fx = ys - y0, xs - x0
        fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
        a, b_ = g[y0][:, x0], g[y0][:, x0 + 1]
        c, d = g[y0 + 1][:, x0], g[y0 + 1][:, x0 + 1]
        top = a + (b_ - a) * fx[None, :]
        bot = c + (d - c) * fx[None, :]
        return top + (bot - top) * fy[:, None]

    def ramp(x, stops):
        x = np.clip(x, 0, 1)
        pos = np.array([p for p, _ in stops], np.float32)
        cols = np.array([c for _, c in stops], np.float32) / 255.0
        return np.stack([np.interp(x, pos, cols[:, k]) for k in range(3)], -1)

    def save(name, rgba_):
        h, w = rgba_.shape[:2]
        img = bpy.data.images.new(name, w, h, alpha=True)
        img.pixels.foreach_set(np.clip(rgba_, 0, 1).astype(np.float32).ravel())
        img.filepath_raw = str(VFX_DIR / name)
        img.file_format = "PNG"
        img.save()
        bpy.data.images.remove(img)

    N = 512
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    u = (xx + 0.5) / N * 2 - 1
    v = (yy + 0.5) / N                       # image rows run bottom-up: v = 0 is the flame's base

    def flame_field(cx0, scale, lean, top, bottom=0.05):
        vv = (v - bottom) / (top - bottom)
        vc = np.clip(vv, 0, 1)
        cx = cx0 + lean * np.sin(vc * 2.6 - 0.4) * vc ** 1.4
        w = scale * np.sin(np.pi * vc ** 0.62) ** 0.85
        w = w + 0.06 * scale * np.sin(vc * 15.0) * np.clip((vc - 0.35) / 0.4, 0, 1) * (1 - vc)
        d = np.abs(u - cx) / np.maximum(w, 1e-4)
        return np.where((vv < 0) | (vv > 1), 9.0, d), vc
    dm, vm = flame_field(0.0, 0.62, 0.10, 0.96)
    dl, _ = flame_field(-0.36, 0.30, -0.07, 0.62, 0.08)
    dr, _ = flame_field(0.34, 0.28, 0.08, 0.70, 0.08)
    d = np.minimum(dm, np.minimum(dl, dr))
    noise = smooth_noise(N, 6, 14) * 0.6 + smooth_noise(N, 14, 34) * 0.4
    heat = np.clip(np.clip(1 - d, 0, 1) ** 0.9 * (1.12 - 0.85 * vm) + (noise - 0.5) * 0.18, 0, 1)
    col = ramp(heat, [(0.0, (226, 62, 22)), (0.22, (250, 120, 28)), (0.45, (255, 176, 46)), (0.68, (255, 222, 110)),
                      (0.85, (255, 246, 190)), (1.0, (255, 255, 240))])
    inside = np.clip((1 - d) / 0.05, 0, 1)
    glow = np.where(d > 1, np.clip(1 - (d - 1) / 0.35, 0, 1) ** 2 * 0.28, 0.0)
    alpha = np.maximum(inside, glow)
    rim = np.where(d <= 1, np.clip(1 - (1 - d) / 0.12, 0, 1), 0.0)
    col = col * (1 - 0.18 * rim[..., None])
    save("flame.png", np.concatenate([col, alpha[..., None]], -1))

    N = 256
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    u = (xx + 0.5) / N * 2 - 1
    v = (yy + 0.5) / N * 2 - 1
    dia = np.abs(u) + np.abs(v)
    rad = np.sqrt(u * u + v * v)
    core = np.clip(1 - dia / 0.42, 0, 1)
    halo = np.clip(1 - rad / 0.95, 0, 1) ** 2.2
    a = np.clip(np.maximum(core ** 0.6, halo * 0.75), 0, 1)
    heat = np.clip(core * 1.2 + halo * 0.45, 0, 1)
    col = ramp(heat, [(0.0, (255, 110, 30)), (0.35, (255, 170, 50)), (0.7, (255, 225, 120)), (1.0, (255, 255, 235))])
    save("ember.png", np.concatenate([col, a[..., None]], -1))
    log("vfx textures painted")


make_vfx_textures()
GLARE = None


def setup_preview_scene():
    global GLARE
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 1000, 1200
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    try:
        scene.eevee.taa_render_samples = 64
        scene.eevee.use_shadows = True
        scene.eevee.use_raytracing = False
    except AttributeError:
        pass
    world = bpy.data.worlds.new("Sky")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.52, 0.70, 0.92, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    scene.world = world
    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun_data.energy = 3.2
    sun_data.angle = math.radians(12)
    sun_data.color = (1.0, 0.96, 0.88)
    sun = bpy.data.objects.new("Sun", sun_data)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), 0, math.radians(-30))
    floor_me = bpy.data.meshes.new("Preview_Floor")
    bmf = bmesh.new()
    bmesh.ops.create_circle(bmf, cap_ends=True, radius=40, segments=96)
    bmf.to_mesh(floor_me)
    bmf.free()
    fm = bpy.data.materials.new("Preview_Floor")
    fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.42, 0.44, 0.45, 1)
    fm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.95
    floor_me.materials.append(fm)
    floor = bpy.data.objects.new("Preview_Floor", floor_me)
    scene.collection.objects.link(floor)
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 70
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    # Neon reads with a soft bloom in Studio; a glare pass hints at it (preview only).
    try:
        ng = bpy.data.node_groups.new("PreviewComp", "CompositorNodeTree")
        rl = ng.nodes.new("CompositorNodeRLayers")
        gl = ng.nodes.new("CompositorNodeGlare")
        gl.inputs["Type"].default_value = "Bloom"
        gl.inputs["Threshold"].default_value = 1.0
        gl.inputs["Strength"].default_value = 0.35
        gl.inputs["Size"].default_value = 0.5
        out = ng.nodes.new("NodeGroupOutput")
        ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
        ng.links.new(gl.outputs[0], out.inputs[0])
        scene.compositing_node_group = ng
        GLARE = gl
    except Exception as ex:          # the preview still renders without bloom
        log("no bloom:", ex)
    return cam, floor, sun


def set_glare(strength, size=0.5):
    if GLARE is not None:
        try:
            GLARE.inputs["Strength"].default_value = strength
            GLARE.inputs["Size"].default_value = size
        except Exception:
            pass


def set_glow(strength):
    for m in (GLOW_MAT, HOT_MAT):
        m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = strength


def shoot(name, loc, target=(0, 0, 3.45), lens=70, res=(1000, 1200), path=None, fov_v=None):
    if VIEWS and name not in VIEWS:
        return None
    if fov_v:
        cam.data.sensor_fit = "VERTICAL"
        cam.data.angle_y = math.radians(fov_v)
    else:
        cam.data.sensor_fit = "AUTO"
        cam.data.lens = lens
    scene.render.resolution_x, scene.render.resolution_y = res
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    out = path or (ROOT / "previews" / f"{'quick-' if QUICK else ''}{name}.png")
    scene.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)
    log("render", name)
    return out


cam, floor, sun = setup_preview_scene()
D = 16.5
shoot("front", (0, -D, 3.9))
shoot("back", (0, D, 3.9))
shoot("side", (D, 0, 3.9))
shoot("threeq", (D * 0.62, -D * 0.78, 5.6))
shoot("close-helm", (3.8, -8.6, 6.3), target=(0, 0, 5.25), lens=80)


# ---------------------------------------------------------------------------
# VFX preview cards: camera-facing quads textured with the painted particle textures at every emitter
# spot (flame plumes, edge sheets, embers, core swirl, heat haze). Preview only, never exported.
# ---------------------------------------------------------------------------
def fx_card_materials():
    out = {}
    for key, fname, strength, amul in (("flame", "flame.png", 5.0, 1.0), ("ember", "ember.png", 7.0, 1.0),
                                       ("haze", "ember.png", 1.4, 0.22)):
        m = bpy.data.materials.new(f"FXCard_{key}")
        nt = m.node_tree
        nt.nodes.clear()
        tx = nt.nodes.new("ShaderNodeTexImage")
        tx.image = bpy.data.images.load(str(VFX_DIR / fname), check_existing=True)
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Strength"].default_value = strength
        nt.links.new(tx.outputs["Color"], em.inputs["Color"])
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        am = nt.nodes.new("ShaderNodeMath")
        am.operation = "MULTIPLY"
        am.inputs[1].default_value = amul
        nt.links.new(tx.outputs["Alpha"], am.inputs[0])
        mx = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(am.outputs[0], mx.inputs[0])
        nt.links.new(tr.outputs[0], mx.inputs[1])
        nt.links.new(em.outputs[0], mx.inputs[2])
        on = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(mx.outputs[0], on.inputs["Surface"])
        try:
            m.surface_render_method = "BLENDED"
        except Exception:
            pass
        out[key] = m
    return out


def build_fx_cards(cam_loc, mats, seed=3):
    rng = random.Random(seed)
    coll = bpy.data.collections.new("FX_Cards_NotExported")
    scene.collection.children.link(coll)
    bms = {k: bmesh.new() for k in mats}
    uvl = {k: bms[k].loops.layers.uv.new("UVMap") for k in mats}
    cam_loc = Vector(cam_loc)

    def card(key, c, size, roll=0.0, stretch=1.0):
        to_cam = (cam_loc - c).normalized()
        rt = Vector((0, 0, 1)).cross(to_cam).normalized()
        up = to_cam.cross(rt).normalized()
        cr, sr = math.cos(roll), math.sin(roll)
        rt, up = rt * cr + up * sr, up * cr - rt * sr
        w, h = size * 0.5, size * 0.5 * stretch
        bm = bms[key]
        vs = [bm.verts.new(c + rt * x * w + up * y * h) for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        f = bm.faces.new(vs)
        for loop, uv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
            loop[uvl[key]].uv = uv

    for e in FX:
        k = e["kind"]
        base = part_pos(e["part"]) + e["pos"]
        d, s = e["dir"], e.get("size", 1.0)
        if k == "flame_plume":
            for off, sz in ((0.0, 1.25), (0.38, 1.0), (0.72, 0.78), (1.0, 0.5)):
                card("flame", base + d * (off * s) + Vector((rng.uniform(-0.06, 0.06), 0, 0)) * s, sz * s * 1.15,
                     math.radians(rng.uniform(-14, 14)), 1.15)
        elif k in ("flame_sheet", "flame_lick"):
            for off, sz in ((0.0, 0.9), (0.4, 0.6)):
                card("flame", base + d * (off * s), sz * s, math.radians(rng.uniform(-18, 18)), 1.2)
        elif k == "embers_rise":
            for q in range(12):
                p = base + d * rng.uniform(0.2, 2.4) + Vector((rng.uniform(-0.5, 0.5), rng.uniform(-0.4, 0.4), 0))
                card("ember", p, rng.uniform(0.09, 0.18), math.radians(45))
        elif k == "ember_swirl":
            for q in range(10):
                a = rng.uniform(0, 2 * math.pi)
                p = base + Vector((math.cos(a) * 0.55, -0.15 + math.sin(a) * 0.25, rng.uniform(-0.3, 0.7)))
                card("ember", p, rng.uniform(0.08, 0.15), math.radians(45))
        elif k == "heat_glow":
            c0 = part_pos(e["part"])
            away = (c0 - cam_loc).normalized()
            for q in range(2):
                card("haze", c0 + away * 0.9 + Vector((rng.uniform(-0.3, 0.3), 0, rng.uniform(0.0, 0.8))), 3.6 * s)
    objs = []
    for key, bm in bms.items():
        me = bpy.data.meshes.new(f"FXCards_{key}")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(mats[key])
        ob = bpy.data.objects.new(me.name, me)
        coll.objects.link(ob)
        objs.append(ob)
    return coll, objs


def remove_fx_cards(coll, objs):
    for o in objs:
        me = o.data
        bpy.data.objects.remove(o)
        bpy.data.meshes.remove(me)
    bpy.data.collections.remove(coll)


CARD_MATS = fx_card_materials()


def game_behind():
    """The gameplay camera: FOV 70 (vertical), 16:9, ~18 studs behind and above the player."""
    if VIEWS and "game-behind" not in VIEWS:
        return
    focus = part_pos("Head") + Vector((0, 0, -0.3))
    pitch = math.radians(24)
    loc = focus + Vector((0, 18 * math.cos(pitch), 18 * math.sin(pitch)))
    coll, objs = build_fx_cards(loc, CARD_MATS)
    set_glow(3.0)
    set_glare(0.5, 0.6)
    shoot("game-behind", loc, target=focus, res=(1600, 900), fov_v=70)
    set_glow(1.6)
    set_glare(0.35, 0.5)
    remove_fx_cards(coll, objs)


game_behind()

# ---------------------------------------------------------------------------
# Hero shot (Cycles): warm key, cool and ember rims, dark slate backdrop, the flame cards at every
# emitter, the core and wing PointLights lit, strong bloom. Preview only.
# ---------------------------------------------------------------------------
HERO_LOC = Vector((-7.6, -13.2, 6.3))


def beauty(name, loc, target, lens=52, res=(1000, 1250)):
    if VIEWS and name not in VIEWS:
        return
    saved = (scene.render.engine, scene.world, sun.hide_render, floor.hide_render)
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    w = bpy.data.worlds.new("Beauty")
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.03, 0.035, 0.06, 1)
    bg.inputs["Strength"].default_value = 1.0
    scene.world = w
    sun.hide_render = True
    lights = []
    spec = [("Key", "AREA", (-4.5, -6.0, 7.0), 850, (1.0, 0.93, 0.84), 4.0),
            ("RimCool", "AREA", (5.5, 5.0, 6.0), 1100, (0.55, 0.68, 1.0), 2.5),
            ("RimEmber", "AREA", (-5.5, 4.5, 3.0), 900, (1.0, 0.45, 0.16), 2.5),
            ("Fill", "AREA", (3.0, -8.0, 2.0), 160, (0.8, 0.85, 1.0), 6.0)]
    for e in FX:
        if e["kind"] == "light":
            spec.append((e["name"], "POINT", tuple(part_pos(e["part"]) + e["pos"]), 40 * e["brightness"],
                         tuple(c / 255 for c in e["color"]), 0.1))
    for lname, kind, pos, energy, col, size in spec:
        ld = bpy.data.lights.new(lname, kind)
        ld.energy = energy
        ld.color = col
        if kind == "AREA":
            ld.size = size
        else:
            ld.shadow_soft_size = size
        lo = bpy.data.objects.new(lname, ld)
        scene.collection.objects.link(lo)
        lo.location = pos
        lo.rotation_euler = (Vector((0, 0, 3.0)) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
        lights.append(lo)
    coll, objs = build_fx_cards(loc, CARD_MATS, seed=5)
    set_glow(7.0)
    set_glare(0.8, 0.7)
    shoot(name, loc, target=target, lens=lens, res=res)
    set_glow(1.6)
    set_glare(0.35, 0.5)
    remove_fx_cards(coll, objs)
    for lo in lights:
        bpy.data.objects.remove(lo)
    scene.render.engine, scene.world, sun.hide_render, floor.hide_render = saved


if not QUICK:
    beauty("hero", tuple(HERO_LOC), (0, 0, 3.7))
scene.render.engine = "BLENDER_EEVEE"

# ---------------------------------------------------------------------------
# Pose check: rotate the proxy's part groups (body + armour) about their rig joints through the
# default R15 walk/run/jump extremes, render a sheet and count interpenetrating triangles
# between armour on different parts and between armour and other parts of the body.
# ---------------------------------------------------------------------------
CHILDREN = {}
for child, (parent, att) in JOINT.items():
    CHILDREN.setdefault(parent, []).append(child)
ARMOR_BY_PART = {}
for o in armor_objs + glow_objs:
    ARMOR_BY_PART.setdefault(o["body_part"], []).append(o)
REST_MW = {o.name: o.matrix_world.copy() for o in list(PROXY.values()) + armor_objs + glow_objs}


def swing(deg):         # + = forward (toward -y) for a limb hanging below its joint
    return Matrix.Rotation(math.radians(-deg), 4, "X")


def spread(deg, side):  # arm raised out to the side
    return Matrix.Rotation(math.radians(-deg if side == "Left" else deg), 4, "Y")


POSES = {
    "idle": {},
    "walk": {"LeftUpperArm": swing(35), "RightUpperArm": swing(-35), "LeftLowerArm": swing(20), "RightLowerArm": swing(20),
             "LeftUpperLeg": swing(-35), "RightUpperLeg": swing(35), "LeftLowerLeg": swing(-35), "RightLowerLeg": swing(-8)},
    "run": {"LeftUpperArm": swing(60), "RightUpperArm": swing(-60), "LeftLowerArm": swing(45), "RightLowerArm": swing(45),
            "LeftUpperLeg": swing(-55), "RightUpperLeg": swing(60), "LeftLowerLeg": swing(-85), "RightLowerLeg": swing(-20)},
    "jump": {"LeftUpperArm": swing(150) @ spread(12, "Left"), "RightUpperArm": swing(150) @ spread(12, "Right"),
             "LeftLowerArm": swing(15), "RightLowerArm": swing(15),
             "LeftUpperLeg": swing(18), "RightUpperLeg": swing(-8), "LeftLowerLeg": swing(-30), "RightLowerLeg": swing(-15)},
    "fall": {"LeftUpperArm": spread(75, "Left"), "RightUpperArm": spread(75, "Right"),
             "LeftUpperLeg": swing(10), "RightUpperLeg": swing(-10)},
    "look_left_60": {"Head": Matrix.Rotation(math.radians(60), 4, "Z")},
    "look_right_60": {"Head": Matrix.Rotation(math.radians(-60), 4, "Z")},
}


def apply_pose(rot):
    world = {}

    def visit(part, M):
        world[part] = M
        for ch in CHILDREN.get(part, []):
            J = joint_world(ch)
            R = rot.get(ch, Matrix.Identity(4))
            visit(ch, M @ Matrix.Translation(J) @ R @ Matrix.Translation(-J))
    visit("LowerTorso", Matrix.Identity(4))
    for part, M in world.items():
        objs = ARMOR_BY_PART.get(part, []) + ([PROXY[part]] if part in PROXY else [])
        for o in objs:
            o.matrix_world = M @ REST_MW[o.name]
    bpy.context.view_layer.update()


def world_bvh(o):
    me = o.data
    mw = o.matrix_world
    verts = [mw @ v.co for v in me.vertices]
    polys = [list(p.vertices) for p in me.polygons]
    return BVHTree.FromPolygons(verts, polys)


def clip_report():
    groups = {}
    for part in set(list(PROXY.keys()) + list(ARMOR_BY_PART.keys())):
        arm = [o for o in ARMOR_BY_PART.get(part, []) if not o.name.endswith("_Glow")]
        groups[part] = {"armor": [world_bvh(o) for o in arm], "body": world_bvh(PROXY[part]) if part in PROXY else None}
    out = {}
    parts = sorted(groups)
    for a in parts:
        for b in parts:
            if a == b:
                continue
            n_body = sum(len(ba.overlap(groups[b]["body"])) for ba in groups[a]["armor"]) if groups[b]["body"] else 0
            n_arm = 0
            if a < b:
                n_arm = sum(len(x.overlap(y)) for x in groups[a]["armor"] for y in groups[b]["armor"])
            if n_body:
                out[f"{a} armour x {b} body"] = n_body
            if n_arm:
                out[f"{a} armour x {b} armour"] = n_arm
    return out


def wing_report():
    """Wings (incl. glow) against every other part's armour and body, and the smallest gap to the helm."""
    wings = [o for o in armor_objs + glow_objs if "_Wings" in o.name]
    if not wings:
        return {}
    verts, polys, off = [], [], 0
    for o in wings:
        mw = o.matrix_world
        verts += [mw @ v.co for v in o.data.vertices]
        polys += [[i + off for i in p.vertices] for p in o.data.polygons]
        off += len(o.data.vertices)
    wb = BVHTree.FromPolygons(verts, polys)
    out = {}
    for part, objs in sorted(ARMOR_BY_PART.items()):
        if part == "UpperTorso":
            continue
        others = [o for o in objs if not o.name.endswith("_Glow")] + ([PROXY[part]] if part in PROXY else [])
        n = sum(len(wb.overlap(world_bvh(o))) for o in others)
        if n:
            out[f"wings x {part}"] = n
    gap = None
    for o in ARMOR_BY_PART.get("Head", []) + [PROXY["Head"]]:
        mw = o.matrix_world
        for vv in o.data.vertices:
            hit = wb.find_nearest(mw @ vv.co)
            if hit[3] is not None and (gap is None or hit[3] < gap):
                gap = hit[3]
    out["helm_to_wings_min_gap_studs"] = round(gap, 3) if gap is not None else None
    return out


if not NOPOSE:
    clip, wingr = {}, {}
    for pname, rot in POSES.items():
        apply_pose(rot)
        clip[pname] = clip_report()
        wingr[pname] = wing_report()
        log("pose", pname, sum(clip[pname].values()), "tri pairs", wingr[pname])
    apply_pose({})
    (ROOT / "pose-check.json").write_text(json.dumps(
        {"method": "part groups rotated about their rig joints (Blender); counts are intersecting triangle pairs",
         "poses_deg": {"walk": "arms +-35, elbows 20, legs +-35, back knee 35",
                       "run": "arms +-60, elbows 45, legs 55/60, back knee 85",
                       "jump": "arms raised 150 forward + 12 out, knees 15-30",
                       "fall": "arms raised 75 out to the sides",
                       "look_left_60 / look_right_60": "head turned 60 degrees about the neck"},
         "totals": {k: sum(v.values()) for k, v in clip.items()},
         "wings": wingr,
         "results": clip}, indent=1))
    log("POSE TOTALS", {k: sum(v.values()) for k, v in clip.items()})


# ---------------------------------------------------------------------------
# Contact sheets (composited in Blender with numpy; no extra tools needed)
# ---------------------------------------------------------------------------
import numpy as np


def load_px(path, w, h):
    im = bpy.data.images.load(str(path), check_existing=False)
    if (im.size[0], im.size[1]) != (w, h):
        im.scale(w, h)
    a = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)


def compose(name, rows, cell_w, gap=12, bg=(0.93, 0.94, 0.96)):
    """rows: list of rows; each row is a list of (path, aspect h/w). Cells in a row share a height."""
    placed, y, W = [], 0, 0
    for row in rows:
        row = [r for r in row if r[0] and Path(r[0]).exists()]
        if not row:
            continue
        hs = max(int(cell_w * asp) for _, asp in row)
        x = gap
        for path, asp in row:
            w_ = cell_w if asp >= 1 else int(hs / asp)
            h_ = int(w_ * asp)
            placed.append((path, x, y + gap, w_, h_))
            x += w_ + gap
        W = max(W, x)
        y += hs + gap
    H = y + gap
    sheet = np.ones((H, W, 4), np.float32)
    sheet[:, :, 0], sheet[:, :, 1], sheet[:, :, 2] = bg
    for path, x, y0, w_, h_ in placed:
        px = load_px(path, w_, h_)
        top = H - y0 - h_                      # Blender image rows run bottom-up
        sheet[top:top + h_, x:x + w_, :] = px
    img = bpy.data.images.new(name, W, H, alpha=False)
    img.pixels.foreach_set(sheet.ravel())
    img.filepath_raw = str(ROOT / "previews" / f"{name}.png")
    img.file_format = "PNG"
    img.save()
    log("sheet", name, W, H)


PV = ROOT / "previews"
PRE = "quick-" if QUICK else ""
if not VIEWS:
    tall = 1.2
    compose(f"{PRE}sheet", [
        [(PV / f"{PRE}front.png", tall), (PV / f"{PRE}threeq.png", tall), (PV / f"{PRE}side.png", tall),
         (PV / f"{PRE}back.png", tall)],
        [(PV / f"{PRE}close-helm.png", tall), (PV / f"{PRE}game-behind.png", 0.5625)] +
        ([] if QUICK else [(PV / "hero.png", 1.25)])], 460)
    compose(f"{PRE}v1-vs-v2", [[(PV / "v1" / "front.png", tall), (PV / f"{PRE}front.png", tall),
                                (PV / "v1" / "threeq.png", tall), (PV / f"{PRE}threeq.png", tall)]], 460)

if not QUICK:
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / f"{SET}.blend"))
log("DONE")
