"""Phoenix armor set (Godly), 2026-09-29: a radiant firebird knight fitted to the normalized R15 body.

Run (background Blender 5.2, never the user's open scene):
  blender -b --factory-startup --threads 2 --python build_phoenix.py
Env:
  QUICK=1      preview colours only: no bake, no exports (fast shape passes; renders previews/quick-*.png)
  VIEWS=a,b    render only these preview names (default: all)
  NOPOSE=1     skip the numeric pose check
  POSE_IMG=0   pose check numbers only, no pose images

Design (see README.md): ivory-white plates with brown-shaded gold trims over a dark wine undersuit;
thick flame-shaped feathers (crimson -> orange -> gold at the tips) in clean graded rows on the helm
crest, pauldrons, folded back wings, tasset hems, vambraces, knees and ankles; a hooked gold beak visor
with glowing eyes; a round sun-core gem in a gold claw setting. The only set with VFX: orange-gold Neon
feather tips, core, eyes and a few seams, plus a "vfx" list (flames, embers, one PointLight) in
studio-install-data.json for Studio to add as particles/light.

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
MAT_NAMES = ["Ivory", "Feather", "Gold", "Bronze", "Suit", "Dark", "Crimson"]
IVY, FTH, GLD, BRZ, SUIT, DRK, CRM = range(7)
OBS, SCL = IVY, FTH                                  # names the shared helpers use as defaults
PREVIEW_RGB = {IVY: (232, 222, 204), FTH: (200, 60, 36), GLD: (214, 160, 66), BRZ: (140, 90, 44),
               SUIT: (70, 26, 34), DRK: (26, 14, 16), CRM: (150, 30, 38)}
GLOW = (255, 150, 40)                                # Neon (Studio Color), warm orange-gold


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
    def __init__(self, bevel=0.0, segs=2, angle=30.0, shade="harden", profile=0.5, facet=0.0):
        self.bm = bmesh.new()
        self.lay = self.bm.loops.layers.float_color.new("Detail")
        self.vd = {}
        self.bevel, self.segs, self.angle, self.shade, self.profile, self.facet = bevel, segs, angle, shade, profile, facet

    def v(self, co, d=None):
        vert = self.bm.verts.new(co)
        if d is not None:
            self.vd[vert] = d
        return vert

    def f(self, verts, mat, d=None):
        try:
            face = self.bm.faces.new(verts)
        except ValueError:
            return None
        face.material_index = mat
        for k, loop in enumerate(face.loops):
            dd = d if d is not None else self.vd.get(loop.vert, (0.0, 0.0, 0.0, 0.0))
            loop[self.lay] = dd
        return face

    def mirrored(self):
        m = Comp(self.bevel, self.segs, self.angle, self.shade, self.profile, self.facet)
        m.bm.free()
        m.bm = self.bm.copy()
        m.lay = m.bm.loops.layers.float_color["Detail"]
        bmesh.ops.scale(m.bm, vec=Vector((-1, 1, 1)), verts=m.bm.verts)
        bmesh.ops.reverse_faces(m.bm, faces=m.bm.faces)
        return m


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
          flush=True, rnd=None, det_fn=None):
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
            ri.append(c.v(P + N * lo, d))
            ro.append(c.v(P + N * (lo + t), d))
        inner.append(ri)
        outer.append(ro)
    ucount = cols if wrap else cols - 1
    fo, fi, fr = [], [], []
    for j in range(rows - 1):
        for i in range(ucount):
            i2 = (i + 1) % cols
            m = mat_fn(j, i) if mat_fn else mat
            fo.append(c.f([outer[j][i], outer[j][i2], outer[j + 1][i2], outer[j + 1][i]], m))
            if not flush:
                fi.append(c.f([inner[j][i], inner[j + 1][i], inner[j + 1][i2], inner[j][i2]], DRK))
    # rims (side walls)
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
        fr.append(c.f(list(q), rim_mat))
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


def crack(glow, bvh, chart, path_uv, w0, w1=0.004, lift_n=0.0, height=0.011):
    """A thin molten crack/seam along chart path_uv, projected onto whatever is in bvh."""
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
        ribbon(glow, pts, nrms, ws, height=height)


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
# THE PHOENIX FEATHER. A thick flame-shaped blade: a lens section with a chamfered top and a raised
# rachis, a rounded root that sinks into what it grows from, the widest point about a third of the
# way out and a pointed tip. The centreline leaves the surface at `rise` degrees and bends by `curl`
# (positive = the tip lifts further off the surface, negative = it sweeps back down along T), with an
# optional sideways lick (`sway`, studs). Detail: R = root->tip, G = across, B = per-feather random,
# A = zone (1 top, 0.6 outline edge, 0.2 underside). With a glow comp, the last part of the feather
# (t >= glow_from) is built in the glow mesh instead: a Neon tip.
# ---------------------------------------------------------------------------
FSEC = [(-1.0, 0.30, 0.6), (-0.62, 0.86, 1.0), (0.0, 1.0, 1.0), (0.62, 0.86, 1.0), (1.0, 0.30, 0.6),
        (0.45, 0.0, 0.2), (-0.45, 0.0, 0.2)]          # (across, up, zone)
FST = [0.0, 0.13, 0.28, 0.44, 0.6, 0.74, 0.84, 0.93, 1.0]
FST_M = [0.0, 0.2, 0.42, 0.64, 0.84, 1.0]
FST_S = [0.0, 0.3, 0.6, 0.84, 1.0]


def feather(c, P, N, T, L, W, *, th=0.05, rise=12.0, curl=20.0, sway=0.0, glow=None, glow_from=0.8,
            mat=FTH, rnd=None, sink=0.012, root_w=0.55, belly=0.36, ridge=0.35, tip_th=0.4, st=None):
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

    def wid(t):
        if t < belly:
            return W * 0.5 * (root_w + (1 - root_w) * math.sin(math.pi / 2 * t / belly))
        return W * 0.5 * ((1 - t) / (1 - belly)) ** 0.85

    def hgt(t):
        return th * (1 - (1 - tip_th) * t)

    def ring(cc, k):
        t = ts[k]
        w, h, n = wid(t), hgt(t), nrms[k]
        return [cc.v(pts[k] + X * (ax * w) + n * ((up * (1 + ridge) if ax == 0.0 else up) * h),
                     (t, (ax + 1) / 2, rnd, z)) for ax, up, z in FSEC]

    def build(cc, ks, m, cap_end, tip):
        R = [ring(cc, k) for k in ks]
        faces = []
        n = len(FSEC)
        for a in range(len(R) - 1):
            for s in range(n):
                s2 = (s + 1) % n
                faces.append(cc.f([R[a][s], R[a][s2], R[a + 1][s2], R[a + 1][s]], m))
        if tip:
            tv = cc.v(pts[-1] + nrms[-1] * (hgt(1.0) * 0.45), (1.0, 0.5, rnd, 1.0))
            for s in range(n):
                faces.append(cc.f([R[-1][s], R[-1][(s + 1) % n], tv], m))
        faces.append(cc.f(R[0][::-1], m))
        if cap_end:
            faces.append(cc.f(R[-1], m))
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
    return pts[-1], nrms[-1]


def feather_field(c, surf, origin, flow, across, rows, cols, du, dv, size, keep=None, **kw):
    """Staggered rows of feathers lying on a surface, flowing along `flow` (root row first)."""
    flow = Vector(flow).normalized()
    across = Vector(across).normalized()
    placed = 0
    for r in range(rows):
        off = 0.5 if r % 2 else 0.0
        for k in range(-cols, cols + 1):
            p = Vector(origin) + flow * (r * dv) + across * ((k + off) * du)
            if keep and not keep(p, r):
                continue
            L_, W_ = size(p.x, p.y, r)
            P, N = surf(p.x, p.y)
            P2, _ = surf(p.x + flow.x * 0.02, p.y + flow.y * 0.02)
            feather(c, P, N, P2 - P, L_, W_, **kw)
            placed += 1
    return placed


def fxe(kind, pos, direction, **kw):
    d = {"kind": kind, "pos": Vector(pos), "dir": Vector(direction).normalized()}
    d.update(kw)
    return d


FLAME_COL = [255, 150, 40]


# ----- Helmet: the phoenix head ------------------------------------------------------------
def build_head():
    comps, glow, fx = [], Comp(shade="flat"), []
    hc = head_chart()
    nu = 20
    ths = [-math.pi + 2 * math.pi * i / nu for i in range(nu)]
    SLIT = math.radians(58)
    Z0, Z1 = 0.045, 0.255                                    # the dark visor slit (eyes)

    def z_bottom(th):
        return lerp(-0.52, -0.605, smooth((abs(th) - math.radians(40)) / math.radians(45)))
    s_top = HEAD_S_MAX - 0.22
    zrows = [-0.30, -0.12, 0.0, Z0, Z1, 0.30, 0.42]
    arc_s = [0.95 + 0.25 * math.pi / 2 * f for f in (0.45, 0.8, 1.0)]
    top_s = [s_top - 0.1, s_top]
    G = []
    for j in range(2 + len(zrows) + len(arc_s) + len(top_s)):
        row = []
        for th in ths:
            zb = z_bottom(th)
            if j == 0:
                s = zb + 0.6
            elif j == 1:
                s = zb + 0.6 + 0.045
            elif j < 2 + len(zrows):
                s = max(zb + 0.6 + 0.09, zrows[j - 2] + 0.6)
            elif j < 2 + len(zrows) + len(arc_s):
                s = arc_s[j - 2 - len(zrows)]
            else:
                s = top_s[j - 2 - len(zrows) - len(arc_s)]
            row.append((th, s))
        G.append(row)

    def thick(j, i, th, s):
        r, z = head_profile(s)
        a = abs(th)
        side = smooth((a - math.radians(40)) / math.radians(50))
        t = 0.06 + 0.06 * smooth((z + 0.35) / 0.75) * side               # cranium flares wider than the jaw
        t += 0.045 * bump(th, z, 0.0, 0.40, 1.0, 0.22)                     # brow mass
        t += 0.05 * bump(a, z, math.radians(82), -0.14, 0.6, 0.26)         # cheek guards
        x = abs(r * math.sin(th))
        if z > 0.55:
            t += 0.06 * max(0.0, 1 - x / 0.36)                             # crown ridge under the crest
        if a < SLIT + 0.01 and Z0 - 0.005 < z < Z1 + 0.005:
            t = 0.022                                                      # recessed visor slit
        elif a < SLIT + 0.33 and (-0.01 < z < Z0 or Z1 < z < 0.31):
            t += 0.02                                                      # raised gold frame
        if j <= 1:
            t += 0.022
        return t

    def matf(j, i):
        th0, s0 = G[j][i]
        th1, s1 = G[j + 1][(i + 1) % nu]
        z0, z1 = head_profile(s0)[1], head_profile(s1)[1]
        a = max(abs(th0), abs(th1)) if abs(th0 - th1) < math.pi else math.pi
        zlo, zhi = min(z0, z1), max(z0, z1)
        if j == 0:
            return GLD
        if a < SLIT + 0.01 and zlo >= Z0 - 0.005 and zhi <= Z1 + 0.005:
            return DRK
        if a < SLIT + 0.33 and zlo >= -0.01 and zhi <= 0.31:
            return GLD
        return IVY
    helm = Comp(bevel=0.014, segs=2, angle=34, facet=12)
    shell(helm, hc, G, thick, wrap=True, mat_fn=matf, rim_mat=GLD, flush=True)
    comps.append(helm)
    bvh = BVHTree.FromBMesh(helm.bm)
    cap = Comp(bevel=0.01, segs=2, angle=32)
    ring = [Vector((math.cos(a) * 0.2, math.sin(a) * 0.24, 0.6 + CL + 0.13)) for a in [2 * math.pi * k / 10 for k in range(10)]]
    ring2 = [Vector((p.x * 0.4, p.y * 0.5, p.z + 0.03)) for p in ring]
    loft(cap, [ring, ring2], IVY, cap0=False, cap1=True, outward=True)
    comps.append(cap)

    # --- the beak visor: a hooked gold beak growing out of the brow, over the middle of the slit
    bk = Comp(bevel=0.01, segs=2, angle=30)
    SEC_B = [(0.0, 0.0), (0.5, -0.12), (0.92, -0.5), (0.8, -1.0), (0.0, -0.74), (-0.8, -1.0), (-0.92, -0.5),
             (-0.5, -0.12)]

    def beak(bp, w_fn, d_fn, flip=False, n=11):
        rings = []
        for k in range(n):
            t = k / (n - 1)
            p = bezier(*bp, t)
            tan = (bezier(*bp, min(1.0, t + 0.01)) - bezier(*bp, max(0.0, t - 0.01))).normalized()
            X = Vector((-1, 0, 0)) if flip else Vector((1, 0, 0))
            U = tan.cross(X).normalized()
            w, d = w_fn(t), d_fn(t)
            rings.append([p + X * (x * w) + U * (u * d) for x, u in SEC_B])
        loft(bk, rings, GLD, cap0=True, cap1=True, outward=True)
    beak([Vector((0, -0.58, 0.44)), Vector((0, -0.90, 0.40)), Vector((0, -1.10, 0.14)), Vector((0, -1.02, -0.20))],
         lambda t: lerp(0.25, 0.012, t ** 1.25), lambda t: lerp(0.38, 0.03, t ** 1.05))
    beak([Vector((0, -0.64, -0.06)), Vector((0, -0.78, -0.10)), Vector((0, -0.88, -0.13)), Vector((0, -0.94, -0.10))],
         lambda t: lerp(0.15, 0.02, t), lambda t: lerp(0.12, 0.03, t), flip=True, n=6)
    comps.append(bk)

    # --- glowing eyes in the slit, angled fierce (outer corner up), with gold brow ridges above
    for sg in (1, -1):
        th = math.radians(27) * sg
        r = 0.6 + CL + 0.022
        n0 = Vector((math.sin(th), -math.cos(th), 0.0))
        c0 = Vector((r * math.sin(th), -r * math.cos(th), 0.15))
        gem(glow, c0 + n0 * 0.004, n0, Vector((-0.42 * sg, 0, 1)), 0.25, 0.085, 0.035, sides=8)
    br = Comp(shade="smooth")
    for sg in (1, -1):
        pts = []
        for k in range(7):
            f = k / 6
            P, N = hc(sg * math.radians(lerp(12, 84, f)), lerp(0.30, 0.44, f ** 1.6) + 0.6)
            hit = project(bvh, P, N)
            if hit:
                pts.append(hit[0] + hit[1] * 0.018 + Vector((0, 0, 0.012)))
        horn(br, pts, 0.05, sides=5, flat=0.6, taper=0.7, r_tip=0.014, mat=GLD, up=Vector((0, -0.3, 1)))
    comps.append(br)

    # --- the crest: a gold keel down the crown, graded rows of big flame feathers rising up and back
    def top_pt(x, y):
        hit = bvh.ray_cast(Vector((x, y, 2.5)), Vector((0, 0, -1)), 5.0)
        if hit[0] is None:
            return Vector((x, y, 0.7)), UP.copy()
        return hit[0], (hit[1] if hit[1].z > 0 else -hit[1])
    keel = Comp(shade="smooth")
    kp = [top_pt(0.0, y)[0] + Vector((0, 0, -0.005)) for y in (-0.56, -0.42, -0.24, -0.04, 0.16, 0.36, 0.52)]
    horn(keel, kp, 0.075, sides=6, flat=0.6, taper=0.0, r_tip=0.05, mat=GLD, up=UP)
    comps.append(keel)
    cr = Comp(shade="smooth")
    tips = []
    for sg in (1, -1):
        for k, (y, Lf, Wf) in enumerate(((-0.40, 0.56, 0.24), (-0.20, 0.72, 0.27), (0.02, 0.88, 0.29),
                                         (0.22, 1.0, 0.30), (0.40, 1.08, 0.30))):
            P, Ns = top_pt(sg * 0.14, y)
            N = (Ns + Vector((sg * 0.95, 0, 0.0))).normalized()
            feather(cr, P, N, Vector((sg * 0.28, 1.0, 0.0)), Lf, Wf, th=0.075, rise=44 - 2 * k, curl=-24,
                    sway=sg * 0.03, glow=glow, sink=0.03)
    for k, (y, Lf, Wf) in enumerate(((-0.48, 0.62, 0.20), (-0.26, 0.84, 0.23), (-0.02, 1.02, 0.25), (0.22, 1.18, 0.25))):
        P, N = top_pt(0.0, y)
        tip, _ = feather(cr, P + N * 0.05, N, Vector((0, 1.0, 0.0)), Lf, Wf, th=0.085, rise=56 - 3 * k, curl=-28,
                         glow=glow, sink=0.03)
        tips.append(tip)
    # plumes at the temples sweeping back around the head
    for sg in (1, -1):
        for k, (deg, z, Lf) in enumerate(((96, 0.40, 0.62), (108, 0.30, 0.70), (120, 0.20, 0.74))):
            P, N = hc(sg * math.radians(deg), z + 0.6)
            hit = project(bvh, P, N)
            if hit:
                feather(cr, hit[0], hit[1], Vector((0, 1.0, 0.12)), Lf, 0.32, th=0.065, rise=4, curl=-30,
                        sway=0.0, sink=0.025)
    comps.append(cr)
    c_tip = sum(tips[1:], Vector()) / 3
    fx.append(fxe("flame", c_tip + Vector((0, -0.10, -0.12)), (0, 0.55, 1.0), color=FLAME_COL, size=1.0, rate=16,
                  note="helm crest"))
    return comps, glow, fx


# ----- UpperTorso: ivory breastplate, plumage inlays, the sun core, folded wings on the back -----
def build_breastplate(comps, glow, side=-1):
    chart = torso_chart(side)
    O = resample(PEC_O, 24)

    def inset_d(k, p):
        if p.x < 0.12:
            return 0.075
        if p.y > 0.7:
            return 0.12
        return 0.11
    I = inset(O, inset_d)
    ts = [0.0, 0.12, 0.55, 0.74, 0.80, 1.0]
    trim_from = 4

    def thick(j, i, u, v):
        base = pec_height(u, v)
        if j == 0:
            return base - PEC_RECESS * 0.55
        if j >= trim_from:
            return base + 0.024 - (0.01 if j == len(ts) - 1 else 0.0)
        return base

    def matf(j, i):
        return GLD if j >= trim_from - 1 else IVY
    c = Comp(bevel=0.014, segs=2 if side < 0 else 1, angle=34)
    shell(c, chart, ring_grid(O, I, ts), thick, lift=lambda j, i, u, v: plate_lift(v), wrap=True, mat_fn=matf,
          rim_mat=GLD, flush=True)
    comps.append(c)
    Fo = inset(I, -0.03)
    ctr = sum(I, Vector((0.0, 0.0))) / len(I)
    Fi = [ctr + (p - ctr) * 0.04 for p in Fo]
    floor = Comp(bevel=0.0, shade="smooth")

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
        flow = Vector((0.16, -1.0)).normalized()

        def keep(p, r):
            if (p - Vector((0.0, 0.30))).length < 0.36:
                return False
            return point_in_poly(p, I) and dist_to_poly(p, I) > 0.035
        n = feather_field(pl, surf, (0.52, 0.90), flow, (1.0, 0.16), 7, 3, 0.19, 0.155,
                          lambda u, v, r: (0.28, 0.2), keep=keep, th=0.036, rise=8, curl=16, st=FST_S, sink=0.004,
                          ridge=0.3)
        comps.append(pl)
        log("plumage feathers", n)


def build_sternum(comps, glow, side=-1):
    chart = torso_chart(side)
    c = Comp(bevel=0.012, segs=2, angle=32)
    xs = [-0.08, -0.04, 0.0, 0.04, 0.08]
    vs = [-0.46, -0.34, -0.1, 0.2, 0.45, 0.66, 0.74]

    def thick(j, i, u, v):
        k = 1 - abs(u) / 0.08
        top_fade = 1 - smooth((v - 0.62) / 0.14)
        bot = smooth((v + 0.46) / 0.14)
        return (0.07 + 0.12 * k ** 0.8) * max(0.35, top_fade) * max(0.4, bot)

    shell(c, chart, grid(xs, vs), thick, lift=lambda j, i, u, v: plate_lift(v), mat=GLD if side < 0 else IVY,
          rim_mat=GLD, flush=True)
    comps.append(c)
    if side < 0:
        bvh = BVHTree.FromBMesh(c.bm)
        crack(glow, bvh, chart, [(0.0, v) for v in (0.04, -0.06, -0.16, -0.26, -0.36, -0.44)], 0.011, 0.006)


def build_core(comps, glow, fx):
    """The focal point: a round sun gem in a domed gold rondel, gripped by four talons, with a
    sunburst of gold flame rays."""
    chart = torso_chart(-1)
    cv = 0.30
    P0, N0 = chart(0.0, cv)

    def circ(r, n=16):
        return [Vector((r * math.cos(2 * math.pi * k / n), cv + r * math.sin(2 * math.pi * k / n))) for k in range(n)]
    c = Comp(bevel=0.012, segs=2, angle=32)
    shell(c, chart, ring_grid(circ(0.25), circ(0.16), [0.0, 0.3, 0.7, 1.0]),
          lambda j, i, u, v: [0.21, 0.225, 0.2, 0.15][j], wrap=True, mat=GLD, rim_mat=GLD, flush=True)
    shell(c, chart, ring_grid(circ(0.16), circ(0.01), [0.0, 1.0]), 0.17, wrap=True, mat=DRK, rim_mat=DRK, flush=True)
    comps.append(c)
    gp = P0 + N0 * 0.17
    gem(glow, gp, N0, UP, 0.30, 0.30, 0.11, sides=10)
    rays = Comp(shade="smooth")
    for k in range(8):
        a = 2 * math.pi * k / 8 + math.pi / 8
        d = Vector((math.cos(a), 0, math.sin(a)))
        P = P0 + d * 0.21 + N0 * 0.13
        long_ = k % 2 == 0
        feather(rays, P, N0, d, 0.27 if long_ else 0.2, 0.12 if long_ else 0.1, th=0.045, rise=-14, curl=6,
                mat=GLD, st=FST_S, sink=0.0, root_w=0.75, ridge=0.45)
    cl = Comp(shade="smooth")
    for ang in (45, 135, 225, 315):
        a = math.radians(ang)
        d = Vector((math.cos(a), 0, math.sin(a)))
        base = gp + d * 0.19 - N0 * 0.01
        tipp = gp + d * 0.085 + N0 * 0.085
        horn(cl, curve_pts(base, base + N0 * 0.07 + d * 0.03, tipp + N0 * 0.03 + d * 0.02, tipp, 6), 0.03, sides=6,
             taper=1.2, mat=GLD)
    comps += [rays, cl]
    fx.append(fxe("embers", gp + N0 * 0.12, (0, -0.25, 1.0), color=[255, 176, 70], size=0.1, rate=3,
                  note="core: a few slow sparks"))
    fx.append(fxe("light", gp + N0 * 0.18, (0, -1, 0), color=FLAME_COL, range=9, brightness=1.4,
                  note="the only light on the set: PointLight at the sun core"))


def build_lames_px(comps, side):
    chart = torso_chart(side)
    for k, (hw, tc, ts_, bc, bs) in enumerate(LAMES):
        c = Comp(bevel=0.013, segs=2 if side < 0 else 1, angle=34)
        nu = 6
        us = [-1 + 2 * i / nu for i in range(nu + 1)]
        tv = [0.0, 0.55, 0.84, 0.90, 1.0]
        G = [[(s_ * hw * lerp(1.0, 0.94, t), lerp(tc + ts_ * s_ * s_, bc + bs * s_ * s_, t)) for s_ in us] for t in tv]

        def thick(j, i, u, v, hw=hw):
            k_ = clamp(1 - abs(u) / (0.22 * hw / 0.8))
            lip = 0.02 if j in (3, 4) else 0.0
            return LAME_T + LAME_R * k_ ** 1.2 + lip - (0.01 if j == 4 else 0.0)

        shell(c, chart, G, thick, lift=lambda j, i, u, v, tv=tv: lame_lift_bottom() * tv[j] - 0.01,
              mat_fn=lambda j, i: GLD if j >= 2 else IVY, rim_mat=GLD, flush=True,
              det_fn=lambda j, i, u, v, tv=tv, nu=nu, k=k: (tv[j], i / nu, 0.3 + 0.1 * k, 0.0))
        comps.append(c)


def build_wing(comps, glow, fx, sg):
    """A folded wing on the backplate: a gold wing-arm rising from the shoulder blade to a wrist just
    above the shoulder line; coverts over secondaries over primaries hanging down behind the back;
    two alula flames rising from the wrist (the wing tip)."""
    R0, R1 = Vector((sg * 0.30, 0.60, 0.30)), Vector((sg * 0.42, 0.88, 0.76))
    R2, W0 = Vector((sg * 0.62, 1.02, 1.22)), Vector((sg * 0.80, 1.00, 1.46))

    def A(t):
        return bezier(R0, R1, R2, W0, t)
    arm = Comp(shade="smooth")
    horn(arm, curve_pts(R0, R1, R2, W0, 9), 0.085, sides=7, taper=0.0, r_tip=0.062, rings=0.08, mat=GLD)
    rivet(arm, Vector((sg * 0.28, 0.5 + CL + 0.07, 0.28)), Vector((0, 1, 0)), r=0.12, h=0.07, sides=8)
    comps.append(arm)
    fw = Comp(shade="smooth")
    Nw = Vector((sg * 0.28, 1.0, 0.12)).normalized()
    for k, t in enumerate((0.12, 0.30, 0.48, 0.66, 0.84)):                      # secondaries
        feather(fw, A(t) + Vector((0, -0.02, -0.02)), Nw, Vector((-sg * 0.2, -0.06, -1.0)), lerp(0.70, 0.94, k / 4),
                0.26, th=0.06, rise=4, curl=10, sway=-sg * 0.025, sink=0.0, st=FST_M)
    for k in range(3):                                                           # primaries (outermost)
        t = (0.92, 0.97, 1.0)[k]
        feather(fw, A(t) + Vector((sg * 0.03, -0.07, -0.03)), Nw, Vector((sg * (0.12 - 0.13 * k), -0.05, -1.0)),
                (1.22, 1.10, 0.98)[k], 0.27, th=0.062, rise=3, curl=9, sway=sg * 0.03, glow=glow, sink=0.0)
    for k, t in enumerate((0.22, 0.42, 0.62, 0.82)):                             # coverts on top
        feather(fw, A(t) + Vector((0, 0.05, 0.035)), Nw, Vector((-sg * 0.18, -0.04, -1.0)), 0.44, 0.25, th=0.055,
                rise=6, curl=14, sink=0.0, st=FST_M)
    tips = []
    for k in range(2):                                                           # the alula: flames rising at the wrist
        tip, _ = feather(fw, W0 + Vector((0, 0.0, -0.03)), Nw, Vector((sg * (0.32 + 0.22 * k), 0.4, 1.0)),
                         (0.72, 0.56)[k], 0.27, th=0.065, rise=4, curl=20, sway=0.0, glow=glow, sink=0.02)
        tips.append(tip)
    comps.append(fw)
    fx.append(fxe("flame", tips[0] + Vector((-sg * 0.02, -0.03, -0.08)), (sg * 0.3, 0.45, 1.0), color=FLAME_COL,
                  size=0.6, rate=10, note="wing tip"))


def build_upper_torso():
    comps, glow, fx = [], Comp(shade="flat"), []
    for side in (-1, 1):
        undersuit_box(comps, torso_chart(side, clear=SUIT_CL), [-0.99, -0.6, 0, 0.6, 0.99],
                      [-0.8, -0.3, 0.2, 0.6, 0.9, 1.0])
        half = []
        build_breastplate(half, glow, side)
        comps += half + [h.mirrored() for h in half]
        build_sternum(comps, glow, side)
        build_lames_px(comps, side)
    build_core(comps, glow, fx)
    for sg in (1, -1):
        build_wing(comps, glow, fx, sg)
    fx.append(fxe("embers", Vector((0.0, 0.85, 0.45)), (0, 0.35, 1.0), color=[255, 170, 60], size=0.12, rate=6,
                  note="gentle rising embers between the wings"))
    return comps, glow, fx


# ----- LowerTorso: crimson belt, sun buckle, ivory tassets with feather hems -----------------
def build_lower_torso():
    comps, glow, fx = [], Comp(shade="flat"), []
    fth = Comp(shade="smooth")
    for side in (-1, 1):
        undersuit_box(comps, lt_chart(side, SUIT_CL), [-0.99, 0, 0.99], [-0.2, 0.0, 0.2])
        ch = lt_chart(side)
        c = Comp(bevel=0.012, segs=2, angle=32)
        us = [-0.985 + 1.97 * i / 8 for i in range(9)]
        vs = [-0.155, -0.14, -0.118, 0.0, 0.118, 0.14, 0.155]

        def thick(j, i, u, v):
            lip = 0.024 if j in (0, 1, 5, 6) else 0.0
            return 0.07 + lip + (0.02 if j == 3 else 0.0) - (0.01 if j in (0, 6) else 0.0)
        shell(c, ch, grid(us, vs), thick, mat_fn=lambda j, i: GLD if j in (0, 5) else CRM, rim_mat=GLD, flush=True)
        comps.append(c)
        st = Comp(shade="smooth")
        for x in (-0.84, -0.62, -0.40, 0.40, 0.62, 0.84):
            P, N = ch(x, 0.0)
            rivet(st, P + N * 0.086, N, r=0.032, h=0.024)
        comps.append(st)
        for sgn in (1, -1):
            x0, x1 = (0.08, 0.93) if sgn > 0 else (-0.93, -0.08)
            specs = ((-0.10, -0.33, 0.02, 0.07, False), (-0.27, -0.48, 0.085, 0.14, True))
            for top, bot, l0, l1, gold_ in specs:
                tc = Comp(bevel=0.012, segs=1, angle=34)
                nu = 6
                tv = [0.0, 0.5, 0.86, 0.92, 1.0]
                G = [[(lerp(x0, x1, i / nu), lerp(top, bot, t)) for i in range(nu + 1)] for t in tv]
                xm = (x0 + x1) / 2
                shell(tc, ch, G, lambda j, i, u, v, xm=xm: 0.05 + (0.018 if j >= 3 else 0.0) +
                      0.03 * max(0.0, 1 - abs(u - xm) / 0.2) ** 1.2,
                      lift=lambda j, i, u, v, l0=l0, l1=l1, tv=tv: lerp(l0, l1, tv[j] ** 1.2),
                      mat_fn=lambda j, i, g=gold_: GLD if (g and j >= 2) else IVY, rim_mat=GLD if gold_ else IVY,
                      flush=True)
                comps.append(tc)
            # feather hem: four flame feathers growing from under the lower tasset, flaring out
            for q in range(4):
                x = lerp(x0 + 0.12, x1 - 0.12, q / 3)
                P, N = ch(x, -0.43)
                feather(fth, P + N * 0.10, N, Vector((sgn * 0.08 * (q - 1.5), 0, -1.0)), 0.40, 0.29, th=0.05,
                        rise=16, curl=14, sink=0.0, st=FST_M, rnd=0.2 + 0.2 * q)
    comps.append(fth)
    # sun buckle: a small gold rondel with a crimson enamel centre and six short rays
    P, N = lt_chart(-1)(0.0, 0.0)
    bc = Comp(bevel=0.01, segs=2, angle=32)

    def circ(r, n=12):
        return [Vector((r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n))) for k in range(n)]
    ch = lt_chart(-1)
    shell(bc, ch, ring_grid(circ(0.15), circ(0.09), [0.0, 0.5, 1.0]), lambda j, i, u, v: [0.14, 0.145, 0.12][j],
          wrap=True, mat=GLD, rim_mat=GLD, flush=True)
    shell(bc, ch, ring_grid(circ(0.09), circ(0.01), [0.0, 1.0]), 0.15, wrap=True, mat=CRM, rim_mat=GLD, flush=True)
    comps.append(bc)
    ry = Comp(shade="smooth")
    for k in range(6):
        a = 2 * math.pi * k / 6 + math.pi / 6
        d = Vector((math.cos(a), 0, math.sin(a)))
        feather(ry, P + d * 0.13 + N * 0.1, N, d, 0.13, 0.08, th=0.035, rise=-10, curl=0, mat=GLD, st=FST_S, sink=0.0,
                root_w=0.75)
    comps.append(ry)
    return comps, glow, fx


# ----- Pauldrons (left upper arm; outer = +x) ---------------------------------------------------
def build_upper_arm():
    comps, glow, fx = [], Comp(shade="flat"), []
    su = limb_chart(r=0.1, clear=SUIT_CL)
    undersuit_box(comps, su, limb_cols(su), [-0.58, -0.2, 0.2, 0.52])
    lc = limb_chart(r=0.1)
    L = lc.stations
    top = Comp(shade="smooth")
    tc_ = [Vector((x, y, 0.584 + SUIT_CL)) for x, y in ((-0.49, -0.49), (0.49, -0.49), (0.49, 0.49), (-0.49, 0.49))]
    top.f([top.v(p, (0, 0, 0.5, 0)) for p in tc_], SUIT)
    comps.append(top)
    for k, (zt, zb, fl, gold_) in enumerate(((0.40, 0.02, 0.13, False), (0.10, -0.24, 0.10, False),
                                             (-0.16, -0.50, 0.17, True))):
        c = Comp(bevel=0.012, segs=1, angle=34)
        nu = 12
        tvs = [0.0, 0.55, 0.86, 0.92, 1.0]
        us = [L["total"] * i / nu for i in range(nu + 1)]
        G = [[(u, lerp(zt, zb, t)) for u in us] for t in tvs]
        shell(c, lc, G, lambda j, i, u, v: 0.05 + (0.018 if j >= 3 else 0.0),
              lift=lambda j, i, u, v, fl=fl, tvs=tvs: fl * (0.35 + 0.65 * tvs[j] ** 1.3),
              mat_fn=lambda j, i, g=gold_: GLD if (g and j >= 2) else IVY, rim_mat=GLD if gold_ else IVY, flush=True)
        comps.append(c)
    ss = [0.0, 0.10, 0.25, 0.42, 0.60, 0.76, 0.88, 0.95, 0.975, 1.0]
    tt = [-1.85 + 3.7 * i / 12 for i in range(13)]
    G = []
    for s_ in ss:
        row = []
        for t_ in tt:
            f = (t_ + 1.85) / 3.7
            hem = 0.05 * max(0.0, 1 - abs(2 * ((f * 3) % 1.0) - 1) ** 1.2) * (s_ - 0.88) / 0.12 if s_ > 0.9 else 0.0
            row.append(((s_ + hem) * PD_SU, t_ * PD_TV))
        G.append(row)
    trim_rows = 8

    def dthick(j, i, u, v):
        t_ = abs(v / PD_TV) / 1.85
        rim = j >= trim_rows or t_ > 0.93
        base = 0.075 + 0.025 * (1 - t_ ** 2)
        return base + (0.024 if rim else 0.0) - (0.01 if (j == len(ss) - 1) else 0.0)

    def dmat(j, i):
        edge_t = i == 0 or i == len(tt) - 2
        return GLD if (j >= trim_rows - 1 or edge_t) else IVY
    dome = Comp(bevel=0.014, segs=2, angle=32)
    shell(dome, pd_chart, G, dthick, mat_fn=dmat, rim_mat=GLD, flush=False,
          det_fn=lambda j, i, u, v: (ss[j], i / 12, 0.71, 0.0))
    comps.append(dome)

    def dsurf(u, v):
        P, N = pd_chart(u, v)
        return P + N * (0.075 + 0.025 * (1 - (abs(v / PD_TV) / 1.85) ** 2)), N
    fth = Comp(shade="smooth")
    tips = []
    # a mantle of flame feathers in staggered rows flowing down and out over the dome, wrapping its curve
    def keep(p, r):
        return p.x < 0.86 * PD_SU and abs(p.y) < 1.72 * PD_TV
    n = feather_field(fth, dsurf, (0.30 * PD_SU, 0.0), (1.0, 0.0), (0.0, 1.0), 5, 4, 0.2, 0.19,
                      lambda u, v, r: (0.44, 0.31), keep=keep, th=0.05, rise=6, curl=-22, st=FST_S, sink=0.01,
                      ridge=0.3)
    log("pauldron mantle feathers", n)
    # the flame crest along the top of the shoulder, overlapping and sweeping up and back (rear tips glow)
    for k, (t_, Lf) in enumerate(((-1.3, 0.62), (-0.8, 0.74), (-0.3, 0.86), (0.2, 0.98), (0.7, 1.10))):
        P, N = dsurf(0.24 * PD_SU, t_ * PD_TV)
        g = glow if k >= 3 else None
        tip, _ = feather(fth, P, N, Vector((0.42, 1.0, 0.0)), Lf, 0.36, th=0.072, rise=22 + 4 * k, curl=-10, sway=0.03,
                         glow=g, sink=0.03, rnd=0.2 * k)
        if g is not None:
            tips.append(tip)
    comps.append(fth)
    ct = sum(tips, Vector()) / len(tips)
    fx.append(fxe("flame", ct + Vector((0.0, -0.12, -0.1)), (0.15, 0.55, 1.0), color=FLAME_COL, size=0.8, rate=12,
                  note="pauldron flame crest"))
    return comps, glow, fx


# ----- Vambraces (left lower arm) ------------------------------------------------------------------
def build_lower_arm():
    comps, glow, fx = [], Comp(shade="flat"), []
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
    tvs = [0.0, 0.07, 0.12, 0.5, 0.88, 0.94, 1.0]
    G = [[(u, lerp(-0.47, z_hi(u), t)) for u in us] for t in tvs]
    c = Comp(bevel=0.013, segs=2, angle=30)

    def th(j, i, u, v):
        p, _ = lc(u, 0)
        ridge = 0.03 * max(0.0, 1 - abs(p.y) / 0.25) if p.x > 0.45 else 0.0
        return 0.06 + ridge + (0.022 if j <= 1 else 0.0) + (0.016 if j >= 5 else 0.0)
    shell(c, lc, G, th, lift=lambda j, i, u, v: 0.10 * (1 - tvs[j] / 0.5) ** 2 if tvs[j] < 0.5 else 0.0,
          mat_fn=lambda j, i: GLD if (j <= 1 or j >= 4) else IVY, rim_mat=GLD, flush=True)
    comps.append(c)
    bvh = BVHTree.FromBMesh(c.bm)
    rib = Comp(shade="smooth")
    for x in (0.2, 0.8):
        pts = []
        for z in (0.16, 0.0, -0.16, -0.30):
            P, N = lc(x, z)
            pts.append(P + N * (0.075 + 0.10 * max(0.0, (-0.2 - z) / 0.3) ** 2))
        horn(rib, pts, 0.028, sides=4, flat=0.6, taper=0.0, r_tip=0.028, mat=GLD, up=Vector((0, -1, 0)))
    comps.append(rib)
    crack(glow, bvh, lc, [(L["outer_mid"], z) for z in (0.12, 0.0, -0.12, -0.24, -0.34)], 0.011, 0.009)
    fth = Comp(shade="smooth")
    for k, (z, Lf) in enumerate(((0.06, 0.46), (-0.06, 0.40), (-0.18, 0.34))):
        P, N = lc(L["outer_mid"] + 0.14, z)
        feather(fth, P + N * 0.075, N, Vector((0, 1.0, -0.15)), Lf, 0.21, th=0.05, rise=22, curl=-8, sink=0.02,
                st=FST_M)
    comps.append(fth)
    return comps, glow, fx


# ----- Legs ------------------------------------------------------------------------------------------
def build_upper_leg():
    comps, glow, fx = [], Comp(shade="flat"), []
    su = limb_chart(r=0.1, clear=SUIT_CL)
    undersuit_box(comps, su, limb_cols(su), [-0.6, -0.2, 0.2, 0.6])
    lc = limb_chart(r=0.1)
    L = lc.stations
    nu = 14
    us = [0.025 + (L["corner_ob"] - 0.025) * i / nu for i in range(nu + 1)]

    def z_hi(u):
        p, _ = lc(u, 0)
        return 0.26 if p.y < -0.3 else lerp(0.26, 0.40, smooth((p.y + 0.3) / 0.3))

    def z_lo(u):
        p, _ = lc(u, 0)
        if p.y < -0.3:
            return -0.40 - 0.13 * max(0.0, 1 - abs(p.x) / 0.5)
        return -0.40
    tvs = [0.0, 0.07, 0.13, 0.5, 1.0]
    G = [[(u, lerp(z_lo(u), z_hi(u), t)) for u in us] for t in tvs]
    c = Comp(bevel=0.013, segs=2, angle=30)

    def th(j, i, u, v):
        p, _ = lc(u, 0)
        ridge = 0.035 * max(0.0, 1 - abs(p.x) / 0.22) if p.y < -0.3 else 0.0
        return 0.06 + ridge + (0.022 if j <= 1 else 0.0)

    def matf(j, i):
        p, _ = lc((us[i] + us[i + 1]) / 2, 0)
        return GLD if (j == 0 or (p.y < -0.3 and abs(p.x) < 0.09)) else IVY
    shell(c, lc, G, th, lift=lambda j, i, u, v: 0.03 * (1 - tvs[j]), mat_fn=matf, rim_mat=GLD, flush=True)
    comps.append(c)
    b = Comp(bevel=0.012, segs=2, angle=30)
    ub = [L["corner_ob"] + (L["back_in"] - 0.025 - L["corner_ob"]) * i / 6 for i in range(7)]
    shell(b, lc, [[(u, z) for u in ub] for z in (-0.02, 0.10, 0.30)], 0.05, mat=IVY, rim_mat=GLD, flush=True)
    comps.append(b)
    return comps, glow, fx


def build_lower_leg_legs():
    comps, glow, fx = [], Comp(shade="flat"), []
    su = limb_chart(r=0.1, clear=SUIT_CL)
    undersuit_box(comps, su, limb_cols(su), [-0.3, 0.0, 0.3, 0.55])
    lc = limb_chart(r=0.1)
    L = lc.stations
    nu = 10
    us = [0.025 + (L["corner_ob"] - 0.025) * i / nu for i in range(nu + 1)]
    tvs = [0.0, 0.5, 0.9, 1.0]
    G = [[(u, lerp(-0.34, 0.30, t)) for u in us] for t in tvs]
    c = Comp(bevel=0.013, segs=2, angle=30)

    def th(j, i, u, v):
        p, _ = lc(u, 0)
        ridge = 0.04 * max(0.0, 1 - abs(p.x) / 0.26) if p.y < -0.3 else 0.0
        return 0.06 + ridge

    def matf(j, i):
        p, _ = lc((us[i] + us[i + 1]) / 2, 0)
        return GLD if (p.y < -0.3 and abs(p.x) < 0.1) else IVY
    shell(c, lc, G, th, mat_fn=matf, rim_mat=GLD, flush=True)
    comps.append(c)
    b = Comp(bevel=0.012, segs=2, angle=30)
    ub = [L["corner_ob"] + (L["back_in"] - 0.025 - L["corner_ob"]) * i / 6 for i in range(7)]
    shell(b, lc, [[(u, z) for u in ub] for z in (-0.34, -0.1, 0.06)], 0.05, mat=IVY, rim_mat=GLD, flush=True)
    comps.append(b)
    # knee cop: an ivory kite rising over the thigh plate, gold lower edge
    kc = Comp(bevel=0.013, segs=2, angle=32)
    zs = [0.02, 0.06, 0.12, 0.28, 0.44, 0.60, 0.74]
    hws = [0.10, 0.18, 0.28, 0.42, 0.35, 0.20, 0.05]
    nu = 8
    Gk = [[(0.5 + (-1 + 2 * i / nu) * hw, z) for i in range(nu + 1)] for z, hw in zip(zs, hws)]

    def kth(j, i, u, v):
        s_ = abs(-1 + 2 * i / nu)
        return 0.055 + 0.055 * (1 - s_) ** 1.3 + (0.02 if j <= 1 else 0.0)
    shell(kc, lc, Gk, kth, lift=lambda j, i, u, v: 0.10 + 0.08 * smooth((v - 0.2) / 0.4),
          mat_fn=lambda j, i: GLD if j == 0 else IVY, rim_mat=GLD, flush=True)
    comps.append(kc)
    sp = Comp(shade="smooth")
    for x in (0.15, 0.85):
        pts = []
        for z in (0.27, 0.05, -0.15, -0.34):
            P, N = lc(x, z)
            pts.append(P + N * 0.075)
        horn(sp, pts, 0.03, sides=4, flat=0.6, taper=0.0, r_tip=0.03, mat=GLD, up=Vector((0, -1, 0)))
    comps.append(sp)
    # feather flare at the knee: three plumes on the outer side sweeping back and up
    fth = Comp(shade="smooth")
    for k, (z, Lf) in enumerate(((0.40, 0.58), (0.27, 0.49), (0.14, 0.39))):
        P, N = lc(L["outer_mid"] - 0.16, z)
        feather(fth, P + N * 0.085, N, Vector((0, 1.0, 0.55)), Lf, 0.23, th=0.056, rise=24, curl=-8, sink=0.02,
                st=FST_M)
    comps.append(fth)
    return comps, glow, fx


# ----- Boots -------------------------------------------------------------------------------------------
def build_lower_leg_boots():
    comps, glow, fx = [], Comp(shade="flat"), []
    lc = limb_chart(r=0.1)
    L = lc.stations
    nu = 12
    us = [0.025 + (L["total"] - 0.05) * i / nu for i in range(nu + 1)]
    tvs = [0.0, 0.08, 0.14, 0.6, 1.0]
    G = []
    for t in tvs:
        row = []
        for u in us:
            f = u / L["total"]
            tip = 0.10 * max(0.0, 1 - abs(2 * ((f * 4) % 1.0) - 1) ** 1.2)
            row.append((u, lerp(-0.47, -0.22 + tip, t)))
        G.append(row)
    c = Comp(bevel=0.012, segs=2, angle=30)
    shell(c, lc, G, lambda j, i, u, v: 0.055 + (0.02 if j <= 1 else 0.0),
          lift=lambda j, i, u, v: 0.10 + 0.05 * tvs[j] ** 2, mat_fn=lambda j, i: GLD if j == 0 else IVY, rim_mat=GLD,
          flush=True)
    comps.append(c)
    fth = Comp(shade="smooth")
    for z, Lf in ((-0.30, 0.44), (-0.43, 0.35)):
        P, N = lc(L["outer_mid"] + 0.12, z)
        feather(fth, P + N * 0.15, N, Vector((0, 1.0, 0.5)), Lf, 0.21, th=0.05, rise=20, curl=-8, sink=0.02,
                st=FST_M)
    comps.append(fth)
    return comps, glow, fx


def build_foot():
    comps, glow, fx = [], Comp(shade="flat"), []
    prof = [(-0.47, 0.15), (-0.2, 0.15), (0.28, 0.15), (0.40, 0.13), (0.47, 0.08), (0.5, 0.0), (0.5, -0.13)]
    pc = profile_chart(prof)
    La = pc.length
    for k, (y0, y1, lift0) in enumerate(((0.52, 0.10, 0.02), (0.14, -0.20, 0.05), (-0.16, -0.45, 0.08))):
        c = Comp(bevel=0.012, segs=1, angle=34)
        us = [La * i / 6 for i in range(7)]
        tvs = [0.0, 0.8, 0.9, 1.0]
        G = [[(u, lerp(y0, y1, t)) for u in us] for t in tvs]
        shell(c, pc, G, lambda j, i, u, v: 0.05 + (0.018 if j >= 2 else 0.0),
              lift=lambda j, i, u, v, l0=lift0, tvs=tvs: l0 + 0.03 * tvs[j], mat_fn=lambda j, i: GLD if j >= 1 else IVY,
              rim_mat=GLD, flush=True)
        comps.append(c)
    tc = Comp(bevel=0.012, segs=2, angle=30)
    fc = lt_chart(-1)
    xs = [-0.47 + 0.97 * i / 6 for i in range(7)]
    shell(tc, fc, [[(x, z) for x in xs] for z in (-0.14, 0.0, 0.16)], 0.06,
          lift=lambda j, i, u, v: 0.07, mat=IVY, rim_mat=GLD, flush=False)
    comps.append(tc)
    cl = Comp(shade="smooth")
    for x, s_ in ((-0.30, 0.9), (0.02, 1.0), (0.32, 0.9)):
        b = Vector((x, -0.5 - CL - 0.12, 0.03))
        horn(cl, curve_pts(b, b + Vector((0, -0.12 * s_, 0.03)), b + Vector((0, -0.22 * s_, -0.05)),
                           b + Vector((0, -0.25 * s_, -0.17)), 7), 0.066, sides=6, taper=1.1, mat=GLD)
    b = Vector((0.1, 0.5 + CL + 0.03, 0.05))
    horn(cl, curve_pts(b, b + Vector((0, 0.11, 0.0)), b + Vector((0, 0.2, -0.04)), b + Vector((0, 0.26, -0.13)), 6),
         0.055, sides=6, taper=1.0, mat=GLD)
    comps.append(cl)
    return comps, glow, fx


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
        pass  # nodes are on by default in 5.x
        nt = m.node_tree
        bs = nt.nodes["Principled BSDF"]
        bs.inputs["Base Color"].default_value = rgba(PREVIEW_RGB[i])
        bs.inputs["Roughness"].default_value = 0.45 if i in (GLD, OBS) else 0.7
        if i in (FTH,):     # preview the per-feather gradient
            at = nt.nodes.new("ShaderNodeAttribute")
            at.attribute_name = "Detail"
            sep = nt.nodes.new("ShaderNodeSeparateColor")
            nt.links.new(at.outputs["Color"], sep.inputs["Color"])
            r = nt.nodes.new("ShaderNodeValToRGB")
            el = r.color_ramp.elements
            stops = {FTH: [(0.0, (110, 14, 30)), (0.45, (206, 50, 34)), (0.72, (244, 130, 40)), (1.0, (255, 206, 100))]}[i]
            el[0].position, el[0].color = stops[0][0], rgba(stops[0][1])
            el[1].position, el[1].color = stops[-1][0], rgba(stops[-1][1])
            for pos, col in stops[1:-1]:
                e = el.new(pos)
                e.color = rgba(col)
            nt.links.new(sep.outputs["Red"], r.inputs["Fac"])
            nt.links.new(r.outputs["Color"], bs.inputs["Base Color"])
        mats.append(m)
    g = bpy.data.materials.new(f"{PREFIX}_Glow")
    pass
    bs = g.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = (0, 0, 0, 1)
    bs.inputs["Emission Color"].default_value = rgba(GLOW)
    bs.inputs["Emission Strength"].default_value = 1.5
    return mats, g


MATS, GLOW_MAT = make_materials()


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


def finish_glow(name, c, part):
    if not len(c.bm.faces):
        c.bm.free()
        return None
    me = bpy.data.meshes.new(name)
    c.bm.normal_update()
    c.bm.to_mesh(me)
    c.bm.free()
    me.materials.append(GLOW_MAT)
    for p in me.polygons:
        p.use_smooth = False
        p.material_index = 0
    ob = bpy.data.objects.new(name, me)
    coll_armor.objects.link(ob)
    ob.location = part_pos(part)
    ob["body_part"] = part
    return ob


SPEC = [  # (piece, part, builder name, mirrored pair?)
    ("Helmet", "Head", "build_head", False),
    ("Chest", "UpperTorso", "build_upper_torso", False),
    ("Chest", "LowerTorso", "build_lower_torso", False),
    ("Chest", "UpperArm", "build_upper_arm", True),
    ("Chest", "LowerArm", "build_lower_arm", True),
    ("Legs", "UpperLeg", "build_upper_leg", True),
    ("Legs", "LowerLeg", "build_lower_leg_legs", True),
    ("Boots", "LowerLeg", "build_lower_leg_boots", True),
    ("Boots", "Foot", "build_foot", True),
]
def mirror_fx(e):
    d = dict(e)
    d["pos"] = Vector((-e["pos"].x, e["pos"].y, e["pos"].z))
    d["dir"] = Vector((-e["dir"].x, e["dir"].y, e["dir"].z))
    return d


armor_objs, glow_objs, FX = [], [], []
for piece, part, bname, pair in SPEC:
    builder = globals().get(bname)
    if builder is None:
        continue
    comps, gl, embers = builder()
    if pair:
        sides = [("Left", comps, gl, embers),
                 ("Right", [c.mirrored() for c in comps], gl.mirrored(),
                  [mirror_fx(e) for e in embers])]
    else:
        sides = [("", comps, gl, embers)]
    for side, cs, g, em in sides:
        full = side + part
        armor_objs.append(finish(f"{PREFIX}_{piece}_{full}", cs, full, MATS))
        go = finish_glow(f"{PREFIX}_{piece}_{full}_Glow", g, full)
        if go:
            glow_objs.append(go)
        for e in em:
            FX.append(dict(e, part=full, piece=piece))
    log("built", piece, part)

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
ATLAS = {"Helmet": "helmet", "UpperTorso": "torso", "LowerTorso": "torso", "UpperArm": "arms", "LowerArm": "arms",
         "Legs": "legs", "Boots": "boots"}


def atlas_of(o):
    piece = o.name.split("_")[1]
    part = o["body_part"]
    if piece == "Helmet":
        return "helmet"
    if piece == "Chest":
        for k in ("UpperTorso", "LowerTorso", "UpperArm", "LowerArm"):
            if part.endswith(k):
                return ATLAS[k]
    return ATLAS[piece]


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

    def ao(self, dist, samples=16):
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

    def emit(self, col):
        em = self.nt.nodes.new("ShaderNodeEmission")
        self._in(em.inputs["Color"], col)
        out = self.nt.nodes.new("ShaderNodeOutputMaterial")
        self.nt.links.new(em.outputs["Emission"], out.inputs["Surface"])


def build_bake_material(m, idx):
    b = NB(m)
    Nrm = b.geo.outputs["Normal"]
    key = b.math("MAXIMUM", b.dot(Nrm, KEY), 0.0)
    sky = b.math("MULTIPLY_ADD", b.dot(Nrm, UP), 0.5, 0.5)
    light = b.math("ADD", b.math("MULTIPLY_ADD", key, 0.52, 0.16), b.math("MULTIPLY", sky, 0.32))
    ao = b.remap(b.ao(0.35, 16), 0.15, 1.0, 0.30, 1.0)
    cav = b.remap(b.ao(0.07, 16), 0.35, 1.0, 0.55, 1.0)
    occl = b.math("MULTIPLY", ao, cav)
    S = b.math("MULTIPLY", light, occl, clamp_=True)
    patches = b.math("MULTIPLY_ADD", b.noise(1.4, 1.0, 0.4, 0.3), 0.14, -0.07)
    strokes = b.math("MULTIPLY_ADD", b.noise(5.0, 1.5, 0.5, 0.6, (1.0, 1.0, 3.2)), 0.07, -0.035)
    paint = b.math("ADD", patches, strokes)
    edge = b.math("MULTIPLY", b.bevel_edge(0.018), b.smoothstep(ao, 0.55, 0.9))
    glint = b.smoothstep(b.dot(Nrm, GLINT), 0.80, 0.97)
    rim = b.math("MAXIMUM", b.dot(Nrm, RIM), 0.0)
    edge_up = b.math("MULTIPLY", edge, b.math("MULTIPLY_ADD", sky, 0.5, 0.5))

    def tint_shade(base, lo=(40, 26, 60), mid=(170, 150, 158), hi=(255, 246, 236)):
        sh = b.ramp(b.math("ADD", S, b.math("MULTIPLY", paint, 0.6)), [(0.0, lo), (0.5, mid), (1.0, hi)])
        return b.mix(1.0, base, sh, "MULTIPLY")

    if idx == IVY:          # ivory-white: cool lavender shadows, warm cream lights, painted warm edges
        col = b.ramp(b.math("ADD", S, b.math("MULTIPLY", paint, 0.35)),
                     [(0.0, (92, 84, 112)), (0.2, (156, 146, 166)), (0.38, (198, 188, 192)), (0.55, (216, 204, 192)),
                      (0.72, (229, 217, 199)), (0.88, (237, 227, 208)), (1.0, (243, 235, 218))])
        col = b.mix(b.math("MULTIPLY", b.R, 0.12), col, (214, 186, 156), "MULTIPLY")
        col = b.mix(b.math("MULTIPLY", rim, 0.18), col, (16, 20, 44), "ADD")
        col = b.mix(b.math("MULTIPLY", edge_up, 0.6), col, (250, 240, 216))
    elif idx == GLD:        # gold: brown shading, never flat yellow
        col = b.ramp(b.math("ADD", S, b.math("MULTIPLY", paint, 0.6)),
                     [(0.0, (46, 24, 10)), (0.25, (104, 60, 22)), (0.48, (172, 114, 40)), (0.68, (218, 162, 64)),
                      (0.85, (244, 206, 112)), (1.0, (255, 238, 178))])
        col = b.mix(b.math("MULTIPLY", glint, 0.45), col, (255, 236, 170), "ADD")
        col = b.mix(b.math("MULTIPLY", edge_up, 0.85), col, (255, 246, 210))
    elif idx == FTH:        # feathers: crimson root -> orange -> gold tip, pale rachis, darker underside
        base = b.ramp(b.R, [(0.0, (96, 10, 28)), (0.2, (150, 20, 34)), (0.42, (204, 46, 34)), (0.62, (236, 100, 34)),
                            (0.8, (250, 156, 46)), (1.0, (255, 204, 92))])
        base = b.mix(b.math("MULTIPLY", b.B, 0.16), base, (226, 76, 30))
        base = b.mix(1.0, base, b.math("MULTIPLY_ADD", b.B, 0.2, 0.88), "MULTIPLY")
        top = b.smoothstep(b.A, 0.85, 0.95)
        rach = b.math("MULTIPLY", b.math("SUBTRACT", 1.0, b.smoothstep(b.math("ABSOLUTE", b.math("SUBTRACT", b.G, 0.5)), 0.0, 0.09)), top)
        base = b.mix(b.math("MULTIPLY", rach, 0.5), base, (255, 200, 120))
        under = b.math("SUBTRACT", 1.0, b.smoothstep(b.A, 0.3, 0.5))
        base = b.mix(b.math("MULTIPLY", under, 0.55), base, (70, 12, 28))
        col = tint_shade(base, (92, 36, 78), (214, 180, 176), (255, 248, 232))
        col = b.mix(b.math("MULTIPLY", edge_up, 0.45), col, (255, 220, 150))
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
    elif idx == CRM:        # crimson enamel / leather
        base = b.ramp(b.math("ADD", b.noise(3.0, 1.0, 0.5, 0.4), b.math("MULTIPLY", paint, 1.5)),
                      [(0.25, (100, 14, 28)), (0.55, (154, 26, 36)), (0.8, (190, 48, 44))])
        vein = b.smoothstep(b.math("ABSOLUTE", b.math("SUBTRACT", b.noise(4.0, 2.0, 0.5, 0.2, (1, 1, 2.2)), 0.5)), 0.03, 0.0)
        base = b.mix(b.math("MULTIPLY", vein, 0.5), base, (66, 8, 20))
        col = tint_shade(base, (34, 12, 40), (150, 120, 136), (255, 238, 228))
        col = b.mix(b.math("MULTIPLY", edge_up, 0.5), col, (236, 120, 96))
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
    scene.cycles.samples = 8
    scene.render.bake.margin = 24
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
        img.scale(BAKE_SIZE, BAKE_SIZE)
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
            if "Detail" in o.data.color_attributes:        # bake-only data; Roblox would read it as vertex colour
                o.data.color_attributes.remove(o.data.color_attributes["Detail"])
    for o in glow_objs:
        if "Detail" in o.data.color_attributes:
            o.data.color_attributes.remove(o.data.color_attributes["Detail"])
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
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_area() < 1e-8], context="FACES_ONLY")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(o.data)
    bm.free()


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
    report = {"set": SET, "rarity": "Godly", "blender_version": bpy.app.version_string,
              "authoring": "final Roblox stud size; import at 1:1, do not scale", "pieces": {}}
    install = {"set": SET, "helmet": "full", "glow_color_srgb": list(GLOW), "glow_material": "Neon",
               "textured_material": "SmoothPlastic (colour comes from TextureID)",
               "axes": "offset/size in Studio part-local axes (x = Blender -x, y = Blender z, z = Blender y)",
               "parts": {}, "vfx": [],
               "vfx_notes": ("Phoenix only. position/direction are part-local Studio axes: put an Attachment "
                             "at position on the body part and point the emitter along direction. flame = "
                             "ParticleEmitter (LightEmission 1, Lifetime 0.4-0.7, Size shrinking from size to 0, "
                             "Speed ~2, SpreadAngle ~15); embers = small ParticleEmitter (Lifetime 1.5-2.5, Speed "
                             "0.8-1.5, slight Acceleration up); light = one PointLight (Shadows off).")}
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
        install["parts"][o.name] = {"piece": piece, "body_part": o["body_part"], "kind": kind,
                                    "atlas": None if kind == "glow" else f"textures/{SET}-{atlas_of(o)}.png",
                                    "offset": [round(sc.x, 4), round(sc.y, 4), round(sc.z, 4)],
                                    "size": [round(abs(ss.x), 4), round(abs(ss.y), 4), round(abs(ss.z), 4)]}
    for e in FX:
        p, d = studio(e["pos"]), studio(e["dir"])
        ent = {"kind": e["kind"], "body_part": e["part"], "piece": e["piece"],
               "position": [round(p.x, 3), round(p.y, 3), round(p.z, 3)],
               "direction": [round(d.x, 3), round(d.y, 3), round(d.z, 3)], "color": e["color"]}
        for k in ("size", "rate", "range", "brightness", "note"):
            if k in e:
                ent[k] = e[k]
        install["vfx"].append(ent)
    report["triangles_total"] = total
    report["triangles_by_piece"] = {k: sum(v["triangles"] for v in d.values()) for k, d in report["pieces"].items()}
    report["largest_mesh"] = max(((n, v["triangles"]) for d in report["pieces"].values() for n, v in d.items()),
                                 key=lambda x: x[1])
    report["textures"] = {g: f"textures/{SET}-{g}.png ({BAKE_SIZE}x{BAKE_SIZE})" for g in sorted(set(map(atlas_of, armor_objs)))}
    (ROOT / "polygon-report.json").write_text(json.dumps(report, indent=1))
    (ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=1))
    log("EXPORTED", total, "triangles")


if not QUICK:
    export()


# ===========================================================================
# PREVIEW RENDERS (Eevee, bright soft daylight like the chest kit previews)
# ===========================================================================
def setup_preview_scene():
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
    bmesh.ops.create_circle(bmf, cap_ends=True, radius=12, segments=64)
    bmf.to_mesh(floor_me)
    bmf.free()
    fm = bpy.data.materials.new("Preview_Floor")
    pass
    fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.42, 0.44, 0.45, 1)
    floor_me.materials.append(fm)
    floor = bpy.data.objects.new("Preview_Floor", floor_me)
    scene.collection.objects.link(floor)
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 70
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    # Neon reads with a soft bloom in Studio; a light glare pass hints at it (preview only).
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
    except Exception as ex:          # the preview still renders without bloom
        log("no bloom:", ex)
    return cam, floor, sun


def shoot(name, loc, target=(0, 0, 2.75), lens=70, res=(1000, 1200), path=None):
    if VIEWS and name not in VIEWS:
        return None
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
D = 15.0
shoot("front", (0, -D, 3.4))
shoot("back", (0, D, 3.4))
shoot("side", (D, 0, 3.4))
shoot("threeq", (D * 0.62, -D * 0.78, 5.0))
shoot("close-helm", (3.6, -8.2, 6.0), target=(0, 0, 5.0), lens=92)

# ---------------------------------------------------------------------------
# Hero shot (Cycles): warm key, cool and ember rims, dark slate backdrop. The flames are shown as
# simple emissive flame-lick meshes at the vfx flame positions and the core PointLight is lit; both
# exist only for this render and are never exported (Studio adds the real particles and light).
# ---------------------------------------------------------------------------
HERO_LOC = Vector((-6.2, -11.2, 4.9))


def build_preview_flames():
    coll = bpy.data.collections.new("FX_Preview_NotExported")
    scene.collection.children.link(coll)
    mats = []
    for nm, col, strength in (("FlameOuter", (255, 92, 22), 7.0), ("FlameInner", (255, 208, 104), 11.0)):
        m = bpy.data.materials.new(nm)
        bs = m.node_tree.nodes["Principled BSDF"]
        bs.inputs["Base Color"].default_value = (0, 0, 0, 1)
        bs.inputs["Emission Color"].default_value = rgba(col)
        bs.inputs["Emission Strength"].default_value = strength
        mats.append(m)
    objs = []
    for e in FX:
        if e["kind"] != "flame":
            continue
        s, d = e["size"], e["dir"]
        wpos = part_pos(e["part"]) + e["pos"]
        to_cam = (HERO_LOC - wpos).normalized()
        N = (to_cam - d * to_cam.dot(d)).normalized()
        side = d.cross(N).normalized()
        for layer, (sc_, mi) in enumerate(((1.0, 0), (0.62, 1))):
            c = Comp(shade="smooth")
            for k, (ang, ln) in enumerate(((-24, 0.72), (0, 1.0), (22, 0.8))):
                T = d * math.cos(math.radians(ang)) + side * math.sin(math.radians(ang))
                feather(c, e["pos"] + N * (0.04 * layer) - d * 0.03, N, T, s * ln * sc_, s * 0.42 * sc_,
                        th=s * 0.08 * sc_, rise=0, curl=0, sway=s * 0.1 * (1 if k % 2 else -1), mat=0, st=FST_M,
                        sink=0.0, root_w=0.7, belly=0.3, rnd=0.5)
            me = bpy.data.meshes.new(f"FlamePreview_{e['part']}_{len(objs)}")
            c.bm.to_mesh(me)
            c.bm.free()
            me.materials.append(mats[mi])
            ob = bpy.data.objects.new(me.name, me)
            coll.objects.link(ob)
            ob.location = part_pos(e["part"])
            ob.hide_render = True
            objs.append(ob)
    return objs


def beauty(name, loc, target, lens=60, res=(1000, 1250)):
    if VIEWS and name not in VIEWS:
        return
    saved = (scene.render.engine, scene.world, sun.hide_render)
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    w = bpy.data.worlds.new("Beauty")
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.035, 0.045, 0.07, 1)
    bg.inputs["Strength"].default_value = 1.0
    scene.world = w
    sun.hide_render = True
    lights = []
    core = next((e for e in FX if e["kind"] == "light"), None)
    for lname, kind, pos, energy, col, size in (
            ("Key", "AREA", (-4.5, -6.0, 7.0), 850, (1.0, 0.93, 0.84), 4.0),
            ("RimCool", "AREA", (5.5, 5.0, 6.0), 1200, (0.55, 0.68, 1.0), 2.5),
            ("RimEmber", "AREA", (-5.5, 4.5, 3.0), 900, (1.0, 0.45, 0.16), 2.5),
            ("Fill", "AREA", (3.0, -8.0, 2.0), 160, (0.8, 0.85, 1.0), 6.0),
            ("Core", "POINT", tuple(part_pos(core["part"]) + core["pos"]) if core else (0, -1, 3.5), 45,
             tuple(c / 255 for c in GLOW), 0.1)):
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
    flames = build_preview_flames()
    for o in flames:
        o.hide_render = False
    GLOW_MAT.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 6.0
    shoot(name, loc, target=target, lens=lens, res=res)
    GLOW_MAT.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 1.5
    for lo in lights:
        bpy.data.objects.remove(lo)
    for o in flames:
        o.hide_render = True
    scene.render.engine, scene.world, sun.hide_render = saved


if not QUICK:
    beauty("hero", tuple(HERO_LOC), (0, 0, 3.35), lens=62)
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


if not NOPOSE:
    if os.environ.get("POSE_IMG") != "0":
        (ROOT / "previews" / "pose").mkdir(exist_ok=True)
    pose_imgs = []
    clip = {}
    labels = []
    for pname, rot in POSES.items():
        apply_pose(rot)
        clip[pname] = clip_report()
        log("pose", pname, sum(clip[pname].values()), "tri pairs")
        for vname, loc in (() if os.environ.get("POSE_IMG") == "0" else (("side", (13.5, -2.0, 3.2)), ("front", (5.0, -13.0, 3.6)))):
            p = shoot(f"pose-{pname}-{vname}", loc, target=(0, 0, 2.9), lens=58, res=(560, 700),
                      path=ROOT / "previews" / "pose" / f"{SET}-pose-{pname}-{vname}.png")
            if p:
                pose_imgs.append(p)
                labels.append(f"{pname} {vname}")
    apply_pose({})
    (ROOT / "pose-check.json").write_text(json.dumps(
        {"method": "part groups rotated about their rig joints (Blender); counts are intersecting triangle pairs",
         "poses_deg": {"walk": "arms +-35, elbows 20, legs +-35, back knee 35",
                       "run": "arms +-60, elbows 45, legs 55/60, back knee 85",
                       "jump": "arms raised 150 forward + 12 out, knees 15-30",
                       "fall": "arms raised 75 out to the sides"},
         "totals": {k: sum(v.values()) for k, v in clip.items()},
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
    row2 = [(PV / f"{PRE}close-helm.png", tall)] + ([] if QUICK else [(PV / "hero.png", 1.25)])
    compose(f"{PRE}sheet", [
        [(PV / f"{PRE}front.png", tall), (PV / f"{PRE}threeq.png", tall), (PV / f"{PRE}side.png", tall),
         (PV / f"{PRE}back.png", tall)], row2], 460)

if not QUICK:
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / f"{SET}.blend"))
log("DONE")

