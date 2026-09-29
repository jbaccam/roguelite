"""Viking armor set (Rare): a Norse raider, fitted to the normalized R15 body.

Run (background Blender 5.2, never the user's open scene):
  blender -b --factory-startup --threads 2 --python build_viking.py
Env:  QUICK=1 (flat colours, no bake/export)  VIEWS=a,b  NOPOSE=1  POSE_IMG=0  COMPTRIS=1

Design (README.md): thick fur mantle fused into a rounded-rectangle ring around the shoulders and
upper back, fur caps over the upper arms, dark leather jerkin with riveted iron strips, wide belt
with a round bronze knotwork buckle, blue-wool undertunic/trousers as the one accent colour,
criss-cross leather leg bindings, iron knee guards, fur-rolled boots, an open horned iron helm.
Everything is modelled at final stud size on the measured R15 proxy (../r15-proxy). No glow.
Blender axes: +z up, -y = the character's front, +x = the character's LEFT; Studio = (-x, z, y).
"""
import bpy, bmesh, math, json, os, random, time
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from pathlib import Path

T0 = time.time()
ROOT = Path(__file__).resolve().parent
SET = "viking"
PREFIX = "Viking"
QUICK = os.environ.get("QUICK") == "1"
VIEWS = set(os.environ["VIEWS"].split(",")) if os.environ.get("VIEWS") else None
NOPOSE = os.environ.get("NOPOSE") == "1"
BAKE_SIZE = 1024          # Roblox caps textures at 1024
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
MAT_NAMES = ["Fur", "Leather", "Iron", "Bronze", "Ivory", "Wool", "Dark"]
FUR, LEA, IRN, BRZ, IVY, WOL, DRK = range(7)
PREVIEW_RGB = {FUR: (128, 98, 72), LEA: (78, 50, 32), IRN: (104, 110, 118), BRZ: (170, 116, 52),
               IVY: (226, 210, 176), WOL: (40, 76, 128), DRK: (22, 16, 16)}


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
def shell(c, chart, G, thick, *, lift=None, wrap=False, mat=IRN, mat_fn=None, rim_mat=None,
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


def rivet(c, P, N, r=0.028, h=0.018, sides=6, mat=BRZ):
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
    """Blue wool layer (flush, single surface) that shows in every gap."""
    c = Comp(bevel=0.0, shade="smooth")
    shell(c, chart, grid(us, vs), 0.004, mat=WOL, rnd=rnd)
    comps.append(c)


def bump(x, y, cx, cy, rx, ry):
    d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
    return max(0.0, 1.0 - d) ** 1.5


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


def sweep(c, pts, section, *, up=None, mat=IRN, cap=True, scale_fn=None, det=None):
    """Sweep a closed 2D section [(a, b)] along pts (a along the frame normal, b along the binormal)."""
    rings = []
    prev = None
    n = len(pts)
    for k, p in enumerate(pts):
        tan = (pts[min(k + 1, n - 1)] - pts[max(k - 1, 0)]).normalized()
        ref = prev if prev is not None else (up if up is not None else Vector((0, 0, 1)))
        nrm = (ref - tan * ref.dot(tan)).normalized()
        prev = nrm
        bi = tan.cross(nrm).normalized()
        sc = scale_fn(k / (n - 1)) if scale_fn else 1.0
        rings.append([p + nrm * a * sc + bi * b * sc for a, b in section])
    faces, V = loft(c, rings, mat, cap0=cap, cap1=cap, det=det)
    f0 = faces[0]
    ctr = sum(rings[0], Vector()) / len(rings[0])
    ctr1 = sum(rings[1], Vector()) / len(rings[1])
    if f0 is not None and f0.normal.dot(f0.calc_center_median() - (ctr + ctr1) / 2) < 0:
        for f in faces:
            if f is not None:
                f.normal_flip()
    return faces


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



# ===========================================================================
# VIKING helpers
# ===========================================================================
def lobe(f, k):
    """Hanging scallop 0..1 over k lobes per unit f: rounded, with a soft floor at the joins."""
    x = (f * k) % 1.0
    return 0.25 + 0.75 * math.sin(math.pi * x) ** 0.6


def hashf(i):
    return (i * 0.6180339887) % 1.0


def surf_hit(bvh, P, N, back=0.5):
    """Ray from outside along -N onto the geometry in bvh; (point, normal) or None."""
    hit = bvh.ray_cast(P + N * back, -N, back * 2.5)
    if hit[0] is None:
        return None
    n = hit[1] if hit[1].dot(N) > 0 else -hit[1]
    return hit[0], n


def lathe(c, center, nrm, up, prof, sides=16, mat=BRZ, rmax=None):
    """Revolve prof [(radius, height, zone)] about the axis nrm through center. Detail: R = radius
    fraction, G = angle, A = zone (1 = painted knotwork field, 0.8 = banded trim)."""
    n = Vector(nrm).normalized()
    u = (Vector(up) - n * Vector(up).dot(n)).normalized()
    rt = u.cross(n).normalized()
    rmax = rmax or max(p[0] for p in prof)
    V = []
    for (r, h, a) in prof:
        V.append([c.v(center + n * h + (rt * math.cos(2 * math.pi * s / sides) + u * math.sin(2 * math.pi * s / sides)) * r,
                      (r / rmax, s / sides, 0.5, a)) for s in range(sides)])
    faces = []
    for k in range(len(V) - 1):
        for s in range(sides):
            s2 = (s + 1) % sides
            faces.append(c.f([V[k][s], V[k][s2], V[k + 1][s2], V[k + 1][s]], mat))
    faces.append(c.f(V[0][::-1], mat))
    top = c.f(V[-1], mat)
    faces.append(top)
    c.bm.normal_update()
    if top is not None and top.normal.dot(n) < 0:
        for f in faces:
            if f is not None:
                f.normal_flip()
    return faces


def strip(c, chart, u0, u1, z0, z1, lift, thick, mat=IRN, nz=2, nu=2):
    """A raised strip on a chart (iron strips on the jerkin, bands)."""
    G = [[(lerp(u0, u1, i / nu), lerp(z0, z1, j / nz)) for i in range(nu + 1)] for j in range(nz + 1)]
    return shell(c, chart, G, lambda j, i, u, v: thick + (0.012 if i == nu // 2 and nu > 1 else 0.0),
                 lift=lambda j, i, u, v: lift, mat=mat, rim_mat=mat, flush=True)


# ----- the fur mantle: one rounded ring around the torso -------------------------
def ring_chart(hx=0.965, hy=0.5 + CL, r=0.16):
    """Closed rounded-rectangle ring around the torso. u = arc length from the front centre toward
    +x (the character's left); v = z. Returns f(u, v) -> (point, outward normal); f.length."""
    a, b = hx - r, hy - r

    def line(p0, p1, n):
        p0, p1 = Vector(p0), Vector(p1)
        return ((p1 - p0).length, lambda t: (p0.x + (p1.x - p0.x) * t, p0.y + (p1.y - p0.y) * t, n[0], n[1]))

    def arc(c_, a0, a1):
        return (abs(a1 - a0) * r, lambda t: (c_[0] + r * math.cos(a0 + (a1 - a0) * t), c_[1] + r * math.sin(a0 + (a1 - a0) * t),
                                             math.cos(a0 + (a1 - a0) * t), math.sin(a0 + (a1 - a0) * t)))
    segs = [line((0, -hy), (a, -hy), (0, -1)), arc((a, -b), -math.pi / 2, 0), line((hx, -b), (hx, b), (1, 0)),
            arc((a, b), 0, math.pi / 2), line((a, hy), (-a, hy), (0, 1)), arc((-a, b), math.pi / 2, math.pi),
            line((-hx, b), (-hx, -b), (-1, 0)), arc((-a, -b), math.pi, 1.5 * math.pi), line((-a, -hy), (0, -hy), (0, -1))]
    total = sum(s[0] for s in segs)

    def f(u, v):
        u %= total
        for L_, fn in segs:
            if u <= L_ + 1e-9:
                x, y, nx, ny = fn(u / L_ if L_ > 0 else 0.0)
                return Vector((x, y, v)), Vector((nx, ny, 0))
            u -= L_
        x, y, nx, ny = segs[-1][1](1.0)
        return Vector((x, y, v)), Vector((nx, ny, 0))
    f.length = total
    return f


def mantle_shape(x, y):
    """(hem z, top z) of the fur mantle over the torso ring point (x, y)."""
    w = abs(x)
    rr = math.hypot(x, y)
    top = 0.80 + 0.20 * smooth((rr - 0.55) / 0.5)          # dips under the head, swells over the shoulders
    front = 0.80 - 0.58 * smooth((w - 0.20) / 0.60)         # open V at the chest, pelts draping at the sides
    back = -0.12 + 0.55 * smooth((w - 0.55) / 0.45)         # deep over the upper back
    wf, wb = smooth((-y - 0.05) / 0.30), smooth((y - 0.05) / 0.30)
    ws = max(0.0, 1.0 - wf - wb)
    hem = (wf * front + wb * back + ws * 0.36) / max(1e-6, wf + wb + ws)
    return hem, top


def build_mantle(c, ring, NC=64, K=8):
    P = ring.length
    g = [0.0, 0.08, 0.26, 0.5, 0.74, 0.92, 1.0]
    tp = [0.07, 0.13, 0.17, 0.20, 0.20, 0.15, 0.06]
    lf = [0.0, 0.0, 0.0, 0.0, 0.0, -0.03, -0.10]
    hemA, topA, sideA, clumpA = [], [], [], []
    for i in range(NC):
        p, _ = ring(P * i / NC, 0)
        hem, top = mantle_shape(p.x, p.y)
        f = i / NC
        hem -= (0.16 if abs(p.y) > 0.3 else 0.07) * lobe(f, K)
        hemA.append(min(hem, top - 0.14))
        topA.append(top)
        sideA.append(1.0 - 0.85 * smooth((abs(p.x) - 0.62) / 0.36))
        clumpA.append(0.80 + 0.40 * lobe(f, K))
    G = [[(P * i / NC, lerp(hemA[i], topA[i], g[j])) for i in range(NC)] for j in range(len(g))]
    shell(c, ring, G, lambda j, i, u, v: max(0.03, tp[j] * sideA[i] * clumpA[i]),
          lift=lambda j, i, u, v: lf[j], wrap=True, mat=FUR, flush=True,
          det_fn=lambda j, i, u, v: (1.0 - g[j], i / NC, hashf(int(i / NC * K)), 0.0))


BUCKLE = [(0.235, 0.0, 0), (0.235, 0.045, 0), (0.21, 0.068, 0), (0.175, 0.062, 0), (0.158, 0.03, 0), (0.15, 0.028, 1),
          (0.06, 0.028, 1), (0.056, 0.048, 0), (0.03, 0.072, 0), (0.012, 0.08, 0)]
CLASP = [(0.125, 0.0, 0), (0.125, 0.03, 0), (0.105, 0.048, 0), (0.09, 0.03, 1), (0.04, 0.03, 1), (0.036, 0.05, 0),
         (0.012, 0.062, 0)]


# ----- UpperTorso ----------------------------------------------------------------
def build_upper_torso():
    comps = []
    for side in (-1, 1):
        undersuit_box(comps, torso_chart(side, clear=SUIT_CL), [-0.99, -0.6, 0, 0.6, 0.99],
                      [-0.8, -0.3, 0.2, 0.6, 0.9, 1.0])
        ch = torso_chart(side)
        # leather jerkin panel
        j = Comp(bevel=0.012, segs=2, angle=30)
        top = 0.66 if side < 0 else 0.50
        us = [-0.86 + 1.72 * i / 6 for i in range(7)]
        vs = [-0.78, -0.72, -0.4, 0.0, 0.35, top]
        shell(j, ch, grid(us, vs), lambda jj, ii, u, v: 0.05 + (0.012 if jj <= 1 else 0.0), mat=LEA, rim_mat=LEA, flush=True)
        comps.append(j)
        # vertical riveted iron strips
        st = Comp(bevel=0.008, segs=2, angle=32)
        rv = Comp(shade="smooth")
        xs = (-0.64, -0.24, 0.24, 0.64) if side < 0 else (-0.66, -0.30, 0.30, 0.66)
        z0, z1 = -0.70, (0.44 if side < 0 else -0.30)
        rows = (-0.58, -0.34, -0.10, 0.14, 0.36) if side < 0 else (-0.62, -0.44)
        for x in xs:
            strip(st, ch, x - 0.06, x + 0.06, z0, z1, 0.05, 0.03)
            for z in rows:
                if side < 0 and z > mantle_shape(x, -0.5)[0] - 0.14:
                    continue
                P, N = ch(x, z)
                rivet(rv, P + N * 0.08, N, r=0.03, h=0.02, sides=6, mat=BRZ)
        comps += [st, rv]
    # the fur mantle (one ring, fused) with bronze knotwork clasps and a slack chain
    m = Comp(bevel=0.0, shade="smooth")
    ring = ring_chart()
    build_mantle(m, ring)
    bvh = BVHTree.FromBMesh(m.bm)
    comps.append(m)
    br = Comp(shade="smooth")
    pts = []
    for sg in (-1, 1):
        h = surf_hit(bvh, Vector((sg * 0.38, -0.9, 0.60)), Vector((0, -1, 0.0)), back=0.4)
        if h is None:
            h = (Vector((sg * 0.38, -0.66, 0.60)), Vector((0, -1, 0)))
        lathe(br, h[0] + h[1] * -0.015, h[1], UP, CLASP, sides=14, mat=BRZ)
        pts.append(h[0] + h[1] * 0.03)
    mid = (pts[0] + pts[1]) / 2 + Vector((0, -0.02, -0.11))
    horn(br, [pts[0], pts[0].lerp(mid, 0.5), mid, mid.lerp(pts[1], 0.5), pts[1]], 0.022, sides=5, taper=0.0, r_tip=0.022, mat=BRZ)
    comps.append(br)
    return comps, [], []


# ----- LowerTorso: belt and buckle --------------------------------------------------
def lt_chart(side, clear=CL):
    def f(u, v):
        return Vector((u, side * (0.5 + clear), v)), Vector((0, side, 0))
    return f


def build_lower_torso():
    comps = []
    for side in (-1, 1):
        undersuit_box(comps, lt_chart(side, SUIT_CL), [-0.99, 0, 0.99], [-0.2, 0.0, 0.2])
        ch = lt_chart(side)
        b = Comp(bevel=0.012, segs=2, angle=32)
        us = [-0.985 + 1.97 * i / 8 for i in range(9)]
        vs = [-0.17, -0.15, -0.05, 0.05, 0.15, 0.185]
        shell(b, ch, grid(us, vs), lambda j, i, u, v: 0.06 + (0.018 if j in (0, 1, 4, 5) else 0.0) - (0.008 if j in (0, 5) else 0.0),
              mat=LEA, rim_mat=LEA, flush=True)
        comps.append(b)
        rv = Comp(shade="smooth")
        for x in ((-0.90, -0.72, -0.54, 0.54, 0.72, 0.90) if side < 0 else (-0.9, -0.66, -0.42, -0.18, 0.18, 0.42, 0.66, 0.9)):
            P, N = ch(x, 0.0)
            rivet(rv, P + N * 0.085, N, r=0.03, h=0.02, sides=6, mat=BRZ)
        comps.append(rv)
    P, N = lt_chart(-1)(0.0, 0.0)
    bk = Comp(shade="smooth")
    lathe(bk, P + N * 0.086, Vector((0, -1, 0)), UP, BUCKLE, sides=22, mat=BRZ)
    comps.append(bk)
    return comps, [], []


# ----- Upper arm: blue wool sleeve, leather armband, fur cap fused over the shoulder -----
def build_upper_arm():
    comps = []
    su = limb_chart(r=0.1, clear=SUIT_CL)
    undersuit_box(comps, su, limb_cols(su), [-0.58, -0.3, 0.0, 0.3, 0.52])
    top = Comp(shade="smooth")
    tc_ = [Vector((x, y, 0.584 + SUIT_CL)) for x, y in ((-0.49, -0.49), (0.49, -0.49), (0.49, 0.49), (-0.49, 0.49))]
    top.f([top.v(p, (0, 0, 0.5, 0)) for p in tc_], WOL)
    comps.append(top)
    lc = limb_chart(r=0.1)
    L = lc.stations
    band = Comp(bevel=0.01, segs=2, angle=32)
    nu = 14
    us = [L["total"] * i / nu for i in range(nu + 1)]
    vs = [-0.34, -0.30, -0.16, -0.12]
    shell(band, lc, [[(u, z) for u in us] for z in vs], lambda j, i, u, v: 0.05 if j in (1, 2) else 0.03,
          lift=lambda j, i, u, v: 0.012, mat=LEA, rim_mat=LEA, flush=True)
    comps.append(band)
    rv = Comp(shade="smooth")
    for u in (L["front_mid"], L["outer_mid"], L["back_mid"]):
        P, N = lc(u, -0.23)
        rivet(rv, P + N * 0.075, N, r=0.03, h=0.02, sides=6, mat=BRZ)
    comps.append(rv)
    # the fur cap: big rounded clumps with a scalloped hem, fused over the shoulder dome
    ss = [-0.04, 0.05, 0.16, 0.30, 0.46, 0.62, 0.76, 0.88, 0.96, 1.0]
    tprof = [0.04, 0.09, 0.13, 0.15, 0.15, 0.14, 0.13, 0.11, 0.08, 0.04]
    NT = 16
    tt = [-1.85 + 3.7 * i / NT for i in range(NT + 1)]
    G = []
    for s_ in ss:
        row = []
        for t_ in tt:
            f = (t_ + 1.85) / 3.7
            ext = 0.07 * (lobe(f, 3) - 0.16) * smooth((s_ - 0.80) / 0.2) if s_ > 0.85 else 0.0
            row.append(((s_ + ext) * PD_SU, t_ * PD_TV))
        G.append(row)
    cap = Comp(bevel=0.0, shade="smooth")
    shell(cap, pd_chart, G, lambda j, i, u, v: max(0.035, tprof[j] * (0.88 + 0.26 * lobe((i / NT), 3))), mat=FUR, rim_mat=FUR,
          flush=True, det_fn=lambda j, i, u, v: (min(1.0, (ss[j] + 0.04) / 1.04), i / NT, hashf(int(i / NT * 3) + 5), 0.0))
    comps.append(cap)
    return comps, [], []


# ----- Bracers: wool sleeve, leather bracer with two iron bands --------------------------
def build_lower_arm():
    comps = []
    su = limb_chart(r=0.1, clear=SUIT_CL)
    undersuit_box(comps, su, limb_cols(su), [-0.52, -0.2, 0.2, 0.5])
    lc = limb_chart(r=0.1)
    L = lc.stations
    nu = 14
    us = [L["total"] * i / nu for i in range(nu + 1)]

    def z_hi(u):
        p, _ = lc(u, 0)
        if p.y < -0.3:
            return 0.04 + 0.05 * max(0.0, 1 - abs(p.x - 0.1) / 0.4)
        return lerp(0.08, 0.14, smooth((p.y + 0.3) / 0.8))
    tvs = [0.0, 0.5, 1.0]
    Gb = [[(u, lerp(-0.47, z_hi(u), t)) for u in us] for t in tvs]
    br = Comp(bevel=0.011, segs=1, angle=30)
    shell(br, lc, Gb, lambda j, i, u, v: 0.05 + (0.012 if j == 1 else 0.0), lift=lambda j, i, u, v: 0.008, mat=LEA,
          rim_mat=LEA, flush=True)
    comps.append(br)
    ib = Comp(bevel=0.008, segs=1, angle=30)
    rv = Comp(shade="smooth")
    for lo, hi in ((0.0, 0.16), (0.84, 1.0)):                # the iron bands hug the two ends
        Gi = [[(u, lerp(lerp(-0.47, z_hi(u), lo), lerp(-0.47, z_hi(u), hi), t)) for u in us] for t in (0.0, 1.0)]
        shell(ib, lc, Gi, 0.03, lift=lambda j, i, u, v: 0.064, mat=IRN, rim_mat=IRN, flush=True)
        zc = lerp(-0.47, 0.06, (lo + hi) / 2)
        for u in (L["front_mid"] * 0.6, L["outer_mid"]):
            P, N = lc(u, zc)
            rivet(rv, P + N * 0.098, N, r=0.024, h=0.016, sides=6, mat=BRZ)
    comps += [ib, rv]
    return comps, [], []


# ----- Helmet: open horned iron cap ------------------------------------------------------
def build_head():
    comps = []
    hc = head_chart(clear=0.06)
    nu = 20
    ths = [-math.pi + 2 * math.pi * i / nu for i in range(nu)]
    KEYS = [(0.0, 0.34), (0.61, 0.32), (1.40, 0.10), (2.09, -0.06), (math.pi, -0.24)]

    def brim_z(th):
        a = abs(th)
        for k in range(len(KEYS) - 1):
            if a <= KEYS[k + 1][0]:
                return lerp(KEYS[k][1], KEYS[k + 1][1], smooth((a - KEYS[k][0]) / (KEYS[k + 1][0] - KEYS[k][0])))
        return KEYS[-1][1]
    rc = 0.31
    s_end = 0.95 + math.pi / 2 * rc + 0.29
    FR = [0.16, 0.32, 0.5, 0.66, 0.8, 0.9, 1.0]
    G = []
    for j in range(len(FR) + 2):
        row = []
        for th in ths:
            sb = brim_z(th) + 0.6
            if j == 0:
                s = sb
            elif j == 1:
                s = sb + 0.07
            else:
                s = lerp(sb + 0.07, s_end, FR[j - 2])
            row.append((th, s))
        G.append(row)
    helm = Comp(bevel=0.014, segs=2, angle=34, facet=12)
    outer = shell(helm, hc, G, lambda j, i, th, s: 0.085 + (0.022 if j <= 1 else 0.0), wrap=True,
                  mat_fn=lambda j, i: BRZ if j == 0 else IRN, rim_mat=BRZ, flush=True)
    capf = helm.f(outer[-1][::-1], IRN)
    helm.bm.normal_update()
    if capf is not None and capf.normal.z < 0:
        capf.normal_flip()
    comps.append(helm)
    bvh = BVHTree.FromBMesh(helm.bm)
    C0 = Vector((0, 0, 0.1))

    def hitdir(d):
        h = bvh.ray_cast(C0 + d * 2.5, -d, 4.0)
        if h[0] is None:
            return C0 + d * 0.75, d
        n = h[1] if h[1].dot(d) > 0 else -h[1]
        return h[0], n
    # two riveted bronze bands crossing on top
    bands, rv = Comp(bevel=0.008, segs=1, angle=32), Comp(shade="smooth")
    for k, (axis, e0, e1) in enumerate((("y", 18, 204), ("x", 0, 180))):
        pts, nrms = [], []
        for q in range(15):
            e = math.radians(lerp(e0, e1, q / 14))
            d = Vector((0, -math.cos(e), math.sin(e))) if axis == "y" else Vector((math.cos(e), 0, math.sin(e)))
            p, n = hitdir(d)
            off = 0.028 + 0.014 * k
            pts.append(p + n * off)
            nrms.append(n)
        nn = len(pts)
        sweep(bands, pts, [(-0.03, -0.10), (0.03, -0.10), (0.03, 0.10), (-0.03, 0.10)], up=nrms[0], mat=BRZ,
              det=lambda kk, s: (kk / (nn - 1), s / 4.0, 0.5, 0.8))
        for q in (2, 4, 10, 12):
            rivet(rv, pts[q] + nrms[q] * 0.03, nrms[q], r=0.028, h=0.02, sides=6, mat=BRZ)
    comps += [bands, rv]
    tp_, tn_ = hitdir(Vector((0, 0, 1)))
    boss = Comp(shade="smooth")
    lathe(boss, tp_ + tn_ * 0.05, tn_, Vector((0, -1, 0)), [(0.10, 0.0, 0), (0.10, 0.03, 0), (0.07, 0.055, 0), (0.025, 0.07, 0)],
          sides=12, mat=BRZ)
    comps.append(boss)
    # brim rivets in a neat row
    rr = Comp(shade="smooth")
    for i in range(0, nu, 2):
        th = ths[i]
        if abs(th) < 0.3:
            continue
        P, N = hc(th, brim_z(th) + 0.6 + 0.035)
        rivet(rr, P + N * 0.105, N, r=0.024, h=0.016, sides=6, mat=BRZ)
    comps.append(rr)
    # nasal guard: a tapered iron plate standing off the face, fused into the brim
    def plane(u, v):
        return Vector((u, -0.69, v)), Vector((0, -1, 0))
    hw = [0.055, 0.075, 0.09, 0.10, 0.11]
    vz = [-0.03, 0.05, 0.16, 0.28, 0.40]
    Gn = [[(hw[j] * k, vz[j]) for k in (-1, -0.5, 0, 0.5, 1)] for j in range(5)]
    ng = Comp(bevel=0.01, segs=1, angle=34)
    shell(ng, plane, Gn, lambda j, i, u, v: 0.03 + 0.03 * (1 - abs(u) / max(hw[j], 1e-3)) + (0.012 if j == 0 else 0.0), mat=IRN,
          rim_mat=IRN, flush=True)
    comps.append(ng)
    # bronze sockets and the two ivory horns
    for sg in (1, -1):
        so = Comp(bevel=0.008, segs=2, angle=34)
        horn(so, [Vector((sg * 0.68, 0.0, 0.36)), Vector((sg * 0.80, 0.0, 0.36)), Vector((sg * 0.90, 0.0, 0.36))], 0.20, sides=10,
             taper=0.0, r_tip=0.20, mat=BRZ, up=UP)
        horn(so, [Vector((sg * 0.88, 0.0, 0.36)), Vector((sg * 0.92, 0.0, 0.36)), Vector((sg * 0.95, 0.0, 0.36))], 0.225, sides=10,
             taper=0.0, r_tip=0.225, mat=BRZ, up=UP)
        comps.append(so)
        hh = Comp(shade="smooth")
        pts = curve_pts(Vector((sg * 0.86, 0.02, 0.36)), Vector((sg * 1.26, 0.0, 0.30)), Vector((sg * 1.38, -0.02, 0.78)),
                        Vector((sg * 1.14, -0.06, 1.18)), 9)
        horn(hh, pts, 0.195, sides=7, taper=0.85, rings=0.10, mat=IVY, up=Vector((0, -1, 0)))
        comps.append(hh)
    return comps, [], []


# ----- Legs -------------------------------------------------------------------------------
def build_upper_leg():
    comps = []
    lc = limb_chart(r=0.1)
    L = lc.stations
    nu = 16
    us = [0.02 + (L["back_in"] - 0.04) * i / nu for i in range(nu + 1)]
    vs = [-0.60, -0.50, -0.2, 0.15, 0.5, 0.58]
    c = Comp(bevel=0.0, shade="smooth")
    shell(c, lc, [[(u, z) for u in us] for z in vs],
          lambda j, i, u, v: 0.03 + 0.035 * math.sin(math.pi * min(1, max(0, (v + 0.6) / 1.18))) ** 0.8 + (0.03 if j == 1 else 0.0),
          lift=lambda j, i, u, v: 0.0, mat=WOL, rim_mat=WOL, flush=True)
    comps.append(c)
    return comps, [], []


def build_lower_leg_legs():
    comps = []
    lc = limb_chart(r=0.1)
    L = lc.stations
    nu = 16
    us = [0.02 + (L["back_in"] - 0.04) * i / nu for i in range(nu + 1)]
    vs = [-0.56, -0.3, 0.0, 0.3, 0.58]
    c = Comp(bevel=0.0, shade="smooth")
    shell(c, lc, [[(u, z) for u in us] for z in vs], 0.04, mat=WOL, rim_mat=WOL, flush=True)
    comps.append(c)
    # criss-cross leather bindings: two rows of X's around the shin
    bn = Comp(bevel=0.0, shade="smooth")
    zb, zt = -0.10, 0.10
    for m in range(4):
        u0 = 0.05 + 0.40 * m
        for k, (za, zb_) in enumerate(((zb, zt), (zt, zb))):
            ts = [q / 5 for q in range(6)]
            Gs = [[(lerp(u0, u0 + 0.42, t), lerp(za, zb_, t) + (jj - 0.5) * 0.075) for t in ts] for jj in (0, 1)]
            shell(bn, lc, Gs, 0.028, lift=lambda j, i, u, v, k=k: 0.045 + 0.018 * k, mat=LEA, rim_mat=LEA, flush=True)
    comps.append(bn)
    # simple iron knee guard, a rounded pillow with a bronze rivet
    kg = Comp(bevel=0.012, segs=2, angle=32)
    zs = [0.12, 0.18, 0.30, 0.44, 0.54]
    hws = [0.16, 0.30, 0.36, 0.30, 0.16]
    nk = 8
    Gk = [[(0.5 + (-1 + 2 * i / nk) * hw, z) for i in range(nk + 1)] for z, hw in zip(zs, hws)]
    shell(kg, lc, Gk, lambda j, i, u, v: 0.04 + 0.05 * (1 - abs(-1 + 2 * i / nk)) ** 1.2 * (1 - abs(j - 2) / 3.2),
          lift=lambda j, i, u, v: 0.045, mat=IRN, rim_mat=IRN, flush=True)
    comps.append(kg)
    kb = BVHTree.FromBMesh(kg.bm)
    rv = Comp(shade="smooth")
    for u, z, r_ in ((0.5, 0.33, 0.04), (0.5 - 0.2, 0.22, 0.026), (0.5 + 0.2, 0.22, 0.026), (0.5 - 0.2, 0.44, 0.026), (0.5 + 0.2, 0.44, 0.026)):
        P, N = lc(u, z)
        h = surf_hit(kb, P + N * 0.3, N, back=0.2)
        if h:
            rivet(rv, h[0], h[1], r=r_, h=r_ * 0.7, sides=6, mat=BRZ)
    comps.append(rv)
    return comps, [], []


# ----- Boots: leather boot on the foot, fur-rolled cuff on the shin ------------------------------
def build_lower_leg_boots():
    comps = []
    lc = limb_chart(r=0.1)
    L = lc.stations
    nu = 20
    us = [0.02 + (L["back_in"] - 0.04) * i / nu for i in range(nu + 1)]
    sh = Comp(bevel=0.01, segs=1, angle=34)
    shell(sh, lc, [[(u, z) for u in us] for z in (-0.57, -0.48, -0.32, -0.24)], 0.055, mat=LEA, rim_mat=LEA, flush=True)
    comps.append(sh)
    zs = [-0.44, -0.39, -0.32, -0.24, -0.17]
    tp = [0.045, 0.10, 0.135, 0.12, 0.06]
    fr = Comp(bevel=0.0, shade="smooth")
    shell(fr, lc, [[(u, z) for u in us] for z in zs], lambda j, i, u, v: tp[j] * (0.85 + 0.3 * lobe(u / L["total"], 6)),
          mat=FUR, rim_mat=FUR, flush=True,
          det_fn=lambda j, i, u, v: (1.0 - j / 4.0 * 0.85, i / nu, hashf(int(u / L["total"] * 6) + 9), 0.0))
    comps.append(fr)
    return comps, [], []


def build_foot():
    comps = []
    prof = [(-0.47, 0.15), (-0.2, 0.15), (0.28, 0.15), (0.40, 0.13), (0.47, 0.08), (0.5, 0.0), (0.5, -0.13)]
    pc = profile_chart(prof)
    La = pc.length
    c = Comp(bevel=0.012, segs=2, angle=30)
    us = [La * i / 8 for i in range(9)]
    ys = [0.46, 0.34, 0.0, -0.3, -0.42]
    G = [[(u, y) for u in us] for y in ys]
    shell(c, pc, G, lambda j, i, u, v: 0.06 + (0.015 if j in (0, 4) else 0.0), lift=lambda j, i, u, v: 0.03,
          mat_fn=lambda j, i: DRK if u_frac(i, us, La) > 0.9 else LEA, rim_mat=LEA, flush=True)
    comps.append(c)
    tc = Comp(bevel=0.012, segs=2, angle=30)
    fc = lt_chart(-1)
    xs = [-0.47 + 0.97 * i / 6 for i in range(7)]
    shell(tc, fc, [[(x, z) for x in xs] for z in (-0.14, 0.0, 0.16)], 0.06, lift=lambda j, i, u, v: 0.07, mat=LEA, rim_mat=LEA,
          flush=False)
    comps.append(tc)
    rv = Comp(shade="smooth")
    for y in (-0.22, -0.06, 0.10):
        P, N = pc(0.0 + La * 0.28, y)
        rivet(rv, P + N * (0.03 + 0.06), N, r=0.028, h=0.018, sides=6, mat=BRZ)
    comps.append(rv)
    return comps, [], []


def u_frac(i, us, La):
    return us[i] / La


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
    """Preview materials; the bake replaces them. Fur and ivory preview their root-to-tip gradient."""
    mats = []
    for i, name in enumerate(MAT_NAMES):
        m = bpy.data.materials.new(f"{PREFIX}_{name}")
        nt = m.node_tree
        bs = nt.nodes["Principled BSDF"]
        bs.inputs["Base Color"].default_value = rgba(PREVIEW_RGB[i])
        bs.inputs["Roughness"].default_value = 0.4 if i in (BRZ, IRN) else 0.75
        if i in (FUR, IVY):
            at = nt.nodes.new("ShaderNodeAttribute")
            at.attribute_name = "Detail"
            sep = nt.nodes.new("ShaderNodeSeparateColor")
            nt.links.new(at.outputs["Color"], sep.inputs["Color"])
            r = nt.nodes.new("ShaderNodeValToRGB")
            stops = {FUR: [(0.0, (52, 36, 26)), (0.5, (120, 92, 66)), (1.0, (206, 180, 146))],
                     IVY: [(0.0, (110, 84, 62)), (0.5, (204, 186, 150)), (1.0, (246, 238, 214))]}[i]
            el = r.color_ramp.elements
            el[0].position, el[0].color = stops[0][0], rgba(stops[0][1])
            el[1].position, el[1].color = stops[-1][0], rgba(stops[-1][1])
            e = el.new(stops[1][0])
            e.color = rgba(stops[1][1])
            nt.links.new(sep.outputs["Red"], r.inputs["Fac"])
            nt.links.new(r.outputs["Color"], bs.inputs["Base Color"])
        mats.append(m)
    return mats


MATS = make_materials()
GLOW_MAT = None
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
armor_objs, glow_objs, EMBERS = [], [], []
for piece, part, bname, pair in SPEC:
    comps, gl, embers = globals()[bname]()
    sides = [("Left", comps), ("Right", [c.mirrored() for c in comps])] if pair else [("", comps)]
    for side, cs in sides:
        full = side + part
        armor_objs.append(finish(f"{PREFIX}_{piece}_{full}", cs, full, MATS))
    log("built", piece, part)

for o in list(coll_work.objects):
    bpy.data.objects.remove(o)


def tri_count(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


TRIS = {o.name: tri_count(o) for o in armor_objs}
log("TRIS total", sum(TRIS.values()))
for k, v in sorted(TRIS.items()):
    print("   ", k, v)

# ---------------------------------------------------------------------------
# Body proxy for previews, the bake's contact AO and pose checks (never exported)
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
# PAINTERLY BAKE (colour + baked lighting in one atlas per group, unique UVs, 1024 direct)
# ===========================================================================
KEY = Vector((0.0, -0.55, 0.83)).normalized()       # symmetric: the set looks the same left/right
GLINT = Vector((0.0, -0.42, 0.91)).normalized()
RIM = Vector((0.0, 0.85, 0.35)).normalized()
ATLAS = {"Helmet": "helmet", "Chest": "body", "Legs": "legs", "Boots": "legs"}


def atlas_of(o):
    return ATLAS[o.name.split("_")[1]]


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
    ao = b.remap(b.ao(0.35, 8), 0.15, 1.0, 0.30, 1.0)
    cav = b.remap(b.ao(0.07, 8), 0.35, 1.0, 0.55, 1.0)
    S = b.math("MULTIPLY", light, b.math("MULTIPLY", ao, cav), clamp_=True)
    patches = b.math("MULTIPLY_ADD", b.noise(1.4, 1.0, 0.4, 0.3), 0.14, -0.07)
    strokes = b.math("MULTIPLY_ADD", b.noise(5.0, 1.5, 0.5, 0.6, (1.0, 1.0, 3.2)), 0.07, -0.035)
    paint = b.math("ADD", patches, strokes)
    edge = b.math("MULTIPLY", b.bevel_edge(0.018), b.smoothstep(ao, 0.55, 0.9))
    glint = b.smoothstep(b.dot(Nrm, GLINT), 0.80, 0.97)
    edge_up = b.math("MULTIPLY", edge, b.math("MULTIPLY_ADD", sky, 0.5, 0.5))

    def tint_shade(base, lo=(34, 28, 52), mid=(168, 154, 156), hi=(255, 244, 228)):     # cool shadows, warm lights
        sh = b.ramp(b.math("ADD", S, b.math("MULTIPLY", paint, 0.6)), [(0.0, lo), (0.5, mid), (1.0, hi)])
        return b.mix(1.0, base, sh, "MULTIPLY")

    if idx == FUR:
        base = b.ramp(b.R, [(0.0, (46, 31, 23)), (0.26, (104, 78, 56)), (0.60, (162, 132, 102)), (1.0, (220, 196, 162))])
        base = b.mix(b.math("MULTIPLY", b.B, 0.5), base, (124, 116, 108))                          # grey-brown clump jitter
        fibre = b.math("MULTIPLY_ADD", b.noise(9.0, 1.0, 0.5, 0.3, (1.0, 1.0, 0.28)), 0.8, 0.6)    # strokes flowing down
        base = b.mix(1.0, base, fibre, "MULTIPLY")
        col = tint_shade(base, (30, 24, 46), (160, 146, 146), (255, 244, 226))
        col = b.mix(b.math("MULTIPLY", b.smoothstep(b.R, 0.78, 1.0), 0.22), col, (238, 218, 184))    # lighter tipped edge
        col = b.mix(b.math("MULTIPLY", edge_up, 0.18), col, (236, 214, 180))
    elif idx == LEA:
        col = b.ramp(b.math("ADD", S, paint), [(0.0, (14, 9, 8)), (0.25, (36, 22, 15)), (0.5, (66, 41, 26)),
                                                (0.75, (104, 66, 40)), (1.0, (150, 102, 62))])
        col = b.mix(b.math("MULTIPLY", glint, 0.30), col, (168, 120, 74), "ADD")
        col = b.mix(b.math("MULTIPLY", edge_up, 0.55), col, (176, 124, 78))
    elif idx == IRN:
        col = b.ramp(b.math("ADD", S, paint), [(0.0, (12, 14, 22)), (0.25, (36, 40, 50)), (0.5, (72, 78, 90)),
                                                (0.75, (116, 124, 136)), (1.0, (176, 184, 194))])
        col = b.mix(b.math("MULTIPLY", glint, 0.32), col, (150, 158, 172), "ADD")
        col = b.mix(b.math("MULTIPLY", edge_up, 0.75), col, (206, 214, 222))
    elif idx == BRZ:
        col = b.ramp(b.math("ADD", S, b.math("MULTIPLY", paint, 0.6)),
                     [(0.0, (34, 18, 8)), (0.25, (80, 44, 18)), (0.5, (138, 88, 34)), (0.72, (190, 132, 58)),
                      (0.9, (224, 174, 94)), (1.0, (246, 214, 140))])
        # broad painted knotwork: a two-strand braid on the buckle/clasp fields (A = 1), ticks on band trim (A = 0.8)
        w1 = b.math("ABSOLUTE", b.math("SINE", b.math("MULTIPLY", b.math("ADD", b.math("MULTIPLY", b.R, 1.5), b.math("MULTIPLY", b.G, 6.0)), 6.28318)))
        w2 = b.math("ABSOLUTE", b.math("SINE", b.math("MULTIPLY", b.math("SUBTRACT", b.math("MULTIPLY", b.R, 1.5), b.math("MULTIPLY", b.G, 6.0)), 6.28318)))
        braid = b.math("MAXIMUM", b.math("SUBTRACT", 1.0, b.smoothstep(w1, 0.08, 0.38)), b.math("SUBTRACT", 1.0, b.smoothstep(w2, 0.08, 0.38)))
        field = b.smoothstep(b.A, 0.85, 0.95)
        band = b.math("MULTIPLY", b.smoothstep(b.A, 0.7, 0.75), b.math("SUBTRACT", 1.0, b.smoothstep(b.A, 0.85, 0.9)))
        tick = b.smoothstep(b.math("ABSOLUTE", b.math("SINE", b.math("MULTIPLY", b.R, 31.4))), 0.86, 0.98)
        col = b.mix(b.math("MULTIPLY", b.math("MULTIPLY", field, braid), 1.0), col, (54, 28, 12))
        col = b.mix(b.math("MULTIPLY", b.math("MULTIPLY", band, tick), 0.7), col, (60, 32, 14))
        col = b.mix(b.math("MULTIPLY", glint, 0.42), col, (255, 226, 160), "ADD")
        col = b.mix(b.math("MULTIPLY", edge_up, 0.8), col, (250, 222, 150))
    elif idx == IVY:
        base = b.ramp(b.R, [(0.0, (120, 92, 70)), (0.22, (190, 168, 134)), (0.6, (234, 222, 192)), (1.0, (252, 246, 232))])
        base = b.mix(b.math("MULTIPLY", b.smoothstep(b.A, 0.5, 1.0), 0.42), base, (110, 82, 60))       # dark grooves at the rings
        col = tint_shade(base, (58, 50, 78), (176, 166, 172), (255, 250, 240))
        col = b.mix(b.math("MULTIPLY", edge_up, 0.4), col, (255, 252, 240))
    elif idx == WOL:
        base = b.ramp(b.math("ADD", S, b.math("MULTIPLY", paint, 0.8)),
                      [(0.0, (14, 24, 50)), (0.3, (30, 54, 96)), (0.6, (48, 84, 136)), (0.85, (82, 122, 174)), (1.0, (132, 168, 206))])
        weave = b.math("MULTIPLY_ADD", b.noise(40.0, 0.0, 0.5, 0.0, (1.0, 1.0, 0.3)), 0.24, 0.88)
        col = b.mix(1.0, base, weave, "MULTIPLY")
        col = b.mix(b.math("MULTIPLY", edge_up, 0.25), col, (150, 190, 232))
    else:
        col = b.ramp(S, [(0.0, (10, 8, 10)), (1.0, (38, 28, 28))])
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
    scene.render.bake.margin = 16
    scene.render.bake.use_clear = True
    finals = {}
    for proxy in PROXY.values():          # the body darkens the plates' contact edges (AO) during the bake
        proxy.hide_render = False
    for group, members in sorted(groups.items()):
        unwrap(members)
        img = bpy.data.images.new(f"{SET}-{group}-bake", BAKE_SIZE, BAKE_SIZE, alpha=False)
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
            if "Detail" in o.data.color_attributes:        # bake-only data; Roblox would read it as vertex colour
                o.data.color_attributes.remove(o.data.color_attributes["Detail"])
    return groups


GROUPS = None
if not QUICK:
    GROUPS = bake_all(armor_objs)


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
    objs = armor_objs
    for o in objs:
        clean_mesh(o)
    select_only(objs)
    bpy.ops.export_scene.gltf(filepath=str(ROOT / "exports" / "glb" / f"{SET}.glb"), export_format="GLB",
                              use_selection=True, export_apply=True)
    bpy.ops.export_scene.fbx(filepath=str(ROOT / "exports" / "fbx" / f"{SET}.fbx"), use_selection=True,
                             object_types={"MESH"}, axis_forward="-Z", axis_up="Y", path_mode="COPY",
                             embed_textures=True, add_leaf_bones=False, mesh_smooth_type="OFF")
    report = {"set": SET, "rarity": "Rare", "blender_version": bpy.app.version_string,
              "authoring": "final Roblox stud size; import at 1:1, do not scale", "pieces": {}}
    install = {"set": SET, "helmet": "open", "glow_color_srgb": None, "glow_material": None,
               "textured_material": "SmoothPlastic (colour comes from TextureID)",
               "axes": "offset/size in Studio part-local axes (x = Blender -x, y = Blender z, z = Blender y)",
               "parts": {}}
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
        report["pieces"].setdefault(piece, {})[o.name] = {"body_part": o["body_part"], "triangles": tris, "vertices": len(me.vertices)}
        sc, ss = studio(centre), studio(size)
        install["parts"][o.name] = {"piece": piece, "body_part": o["body_part"], "kind": "textured",
                                    "atlas": f"textures/{SET}-{atlas_of(o)}.png",
                                    "offset": [round(sc.x, 4), round(sc.y, 4), round(sc.z, 4)],
                                    "size": [round(abs(ss.x), 4), round(abs(ss.y), 4), round(abs(ss.z), 4)]}
    report["triangles_total"] = total
    report["triangles_by_piece"] = {k: sum(v["triangles"] for v in d.values()) for k, d in report["pieces"].items()}
    report["largest_mesh"] = max(((n, v["triangles"]) for d in report["pieces"].values() for n, v in d.items()), key=lambda x: x[1])
    report["textures"] = {g: f"textures/{SET}-{g}.png ({BAKE_SIZE}x{BAKE_SIZE})" for g in sorted(set(map(atlas_of, armor_objs)))}
    (ROOT / "polygon-report.json").write_text(json.dumps(report, indent=1))
    (ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=1))
    log("EXPORTED", total, "triangles")


if not QUICK:
    export()


# ===========================================================================
# PREVIEW RENDERS (Eevee, bright soft daylight)
# ===========================================================================
def setup_preview_scene():
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 1000, 1200
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    try:
        scene.eevee.taa_render_samples = 48
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
    fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.42, 0.44, 0.45, 1)
    floor_me.materials.append(fm)
    floor = bpy.data.objects.new("Preview_Floor", floor_me)
    scene.collection.objects.link(floor)
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 70
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam, floor, sun


def shoot(name, loc, target=(0, 0, 2.75), lens=70, res=(1000, 1200), path=None):
    if VIEWS and name not in VIEWS:
        return None
    cam.data.lens = lens
    scene.render.resolution_x, scene.render.resolution_y = res
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    out = path or (ROOT / "previews" / f"{SET}-{name}.png")
    scene.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)
    log("render", name)
    return out


cam, floor, sun = setup_preview_scene()
D = 15.0
shoot("front", (0, -D, 3.3))
shoot("back", (0, D, 3.3))
shoot("side", (D, 0, 3.3))
shoot("threeq", (D * 0.62, -D * 0.78, 5.0))
shoot("close-helm", (3.4, -8.6, 5.7), target=(0, 0, 4.95), lens=100)
if os.environ.get("EXTRA") == "1":
    tmp = ROOT / "previews" / "_tmp"
    tmp.mkdir(exist_ok=True)
    shoot("x-chest", (-2.4, -9.5, 4.0), target=(0, 0, 3.3), lens=100, path=tmp / "x-chest.png")
    shoot("x-back", (-3.0, 9.6, 4.2), target=(0, 0, 3.4), lens=100, path=tmp / "x-back.png")
    shoot("x-legs", (4.2, -9.2, 1.6), target=(0, 0, 1.2), lens=100, path=tmp / "x-legs.png")

# ---------------------------------------------------------------------------
# Pose check (numbers only unless POSE_IMG=1): part groups rotated about their rig joints
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
    clip = {}
    for pname, rot in POSES.items():
        apply_pose(rot)
        clip[pname] = clip_report()
        log("pose", pname, sum(clip[pname].values()), "tri pairs")
    apply_pose({})
    (ROOT / "pose-check.json").write_text(json.dumps(
        {"method": "part groups rotated about their rig joints (Blender); counts are intersecting triangle pairs",
         "poses_deg": {"walk": "arms +-35, elbows 20, legs +-35, back knee 35",
                       "run": "arms +-60, elbows 45, legs 55/60, back knee 85",
                       "jump": "arms raised 150 forward + 12 out, knees 15-30",
                       "fall": "arms raised 75 out to the sides"},
         "results": clip}, indent=1))

# ---------------------------------------------------------------------------
# Contact sheet (composited in Blender with numpy)
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
if not VIEWS:
    tall = 1.2
    compose("sheet", [
        [(PV / f"{SET}-front.png", tall), (PV / f"{SET}-threeq.png", tall), (PV / f"{SET}-side.png", tall),
         (PV / f"{SET}-back.png", tall), (PV / f"{SET}-close-helm.png", tall)],
    ], 400)

bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / f"{SET}.blend"))
log("DONE")
