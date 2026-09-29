"""Iron armor set (Common): a sturdy young squire's kit, fitted to the normalized R15 body.

Run (background Blender 5.2, never the user's open scene):
  blender -b --factory-startup --threads 2 --python build_iron.py
Env:
  QUICK=1      flat preview colours only: no bake, no exports (fast shape passes)
  VIEWS=a,b    render only these preview names (default: all)
  NOPOSE=1     skip the numeric pose check
  SAMPLES=n    bake samples (default 8)

Design (see README.md): cool brushed steel plates over a tan quilted gambeson, dark warm leather for
belt, straps and boots. No gold, gems, glow, spikes or scales. Every piece is modelled at final stud
size around the real R15 body (../r15-proxy/*.obj, measured in Studio 2026-09-28). One rigid mesh per
R15 part it covers. The generator is self-contained: the shared pipeline pieces (body proxy, charts,
shell plates, painterly bake, export, preview) are copied from the Dragon Scale generator.

Blender axes: +z up, -y = the character's front, +x = the character's LEFT.
Studio axes = (-x, z, y) of Blender.
"""
import bpy, bmesh, math, json, os, random, time
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from pathlib import Path

T0 = time.time()
ROOT = Path(__file__).resolve().parent
KIT = ROOT.parent                      # blender-armor-kit/ (r15-proxy lives here, read only)
SET = "iron"
PREFIX = "Iron"
QUICK = os.environ.get("QUICK") == "1"
VIEWS = set(os.environ["VIEWS"].split(",")) if os.environ.get("VIEWS") else None
NOPOSE = os.environ.get("NOPOSE") == "1"
BAKE_SIZE = 1024                       # Roblox caps textures at 1024; baked directly at that size
SAMPLES = int(os.environ.get("SAMPLES", "8"))
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
    for line in open(KIT / "r15-proxy" / f"{name}.obj"):
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
MAT_NAMES = ["Steel", "Leather", "Gambeson", "Dark"]
STL, LTH, GAM, DRK = range(4)
PREVIEW_RGB = {STL: (156, 166, 182), LTH: (86, 54, 32), GAM: (178, 150, 108), DRK: (34, 30, 30)}

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
def shell(c, chart, G, thick, *, lift=None, wrap=False, mat=STL, mat_fn=None, rim_mat=None,
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

def bezier(p0, p1, p2, p3, t):
    a = 1 - t
    return p0 * a ** 3 + p1 * 3 * a * a * t + p2 * 3 * a * t * t + p3 * t ** 3


def horn(c, pts, r0, *, sides=7, taper=1.0, flat=1.0, rings=0.0, mat=LTH, up=None, rnd=None, r_tip=0.0,
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
def rivet(c, P, N, r=0.028, h=0.018, sides=5, mat=STL):
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
    """Dark scale-mail undersuit layer (flush, single surface) that shows in every gap."""
    c = Comp(bevel=0.0, shade="smooth")
    shell(c, chart, grid(us, vs), 0.004, mat=GAM, rnd=rnd)
    comps.append(c)

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

# Shoulder dome (superquadric shell over the arm's top and outer face). Sized so that the arm's
# rounded top corners stay inside it (checked numerically at build time).
PD_O = Vector((0.0, 0.0, 0.10))
PD_R = Vector((0.72, 0.66, 0.68))
PD_N = 3.0
PD_SU, PD_TV = 1.30, 0.47
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


def _dome_fit():
    worst = 0.0
    for (x, y, z) in (s2b(v) for v in BODY["LeftUpperArm"]["verts"]):
        if z < 0.0:
            continue
        f = (abs((x - PD_O.x) / PD_R.x) ** PD_N + abs((y - PD_O.y) / PD_R.y) ** PD_N +
             abs((z - PD_O.z) / PD_R.z) ** PD_N) ** (1 / PD_N)
        worst = max(worst, f)
    return worst


log("shoulder dome fit (must be < 1):", round(_dome_fit(), 3))


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def outward(c, faces, centre):
    c.bm.normal_update()
    for f in faces:
        if f is not None and f.normal.dot(f.calc_center_median() - centre) < 0:
            f.normal_flip()


def box(c, ctr, hx, hy, hz, mat):
    ctr = Vector(ctr)
    V = [c.v(ctr + Vector((sx * hx, sy * hy, sz * hz)), (0.5, 0.5, 0.5, 0.0))
         for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)]
    quads = ((0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5))
    faces = [c.f([V[i] for i in q], mat) for q in quads]
    outward(c, faces, ctr)
    return faces


def tube_loop(c, pts, r, mat, sides=6):
    """A closed round roll following a loop of points (rolled brim)."""
    n = len(pts)
    rings = []
    for k, p in enumerate(pts):
        tan = (pts[(k + 1) % n] - pts[k - 1]).normalized()
        nrm = (UP - tan * UP.dot(tan)).normalized()
        bi = tan.cross(nrm).normalized()
        rings.append([c.v(p + (nrm * math.cos(2 * math.pi * s / sides) + bi * math.sin(2 * math.pi * s / sides)) * r,
                          (k / n, s / sides, 0.5, 0.0)) for s in range(sides)])
    faces = []
    for k in range(n):
        A, B = rings[k], rings[(k + 1) % n]
        for s in range(sides):
            faces.append(c.f([A[s], A[(s + 1) % sides], B[(s + 1) % sides], B[s]], mat))
    c.bm.normal_update()
    for idx, f in enumerate(faces):
        k = idx // sides
        if f is not None and f.normal.dot(f.calc_center_median() - (pts[k] + pts[(k + 1) % n]) / 2) < 0:
            f.normal_flip()


def ridge_sweep(c, pts, w, h, sink, mat):
    """A soft half-round ridge along an open path over a surface (path runs front to back)."""
    X = Vector((1, 0, 0))
    arc = [math.pi * k / 4 for k in range(5)]
    rings = []
    for k, p in enumerate(pts):
        tan = (pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]).normalized()
        nrm = X.cross(tan).normalized()
        ring = [p + X * (w * math.cos(a)) + nrm * (h * math.sin(a)) for a in arc]
        ring += [p - X * (w * 0.9) - nrm * sink, p + X * (w * 0.9) - nrm * sink]
        rings.append(ring)
    return loft(c, rings, mat, outward=True)


def lite_cols(ch):
    """Coarser column stations around a limb chart (two segments per rounded corner)."""
    c = limb_cols(ch)
    return [c[i] for i in (0, 2, 3, 5, 6, 7, 8, 9, 11, 12, 14)]


def rivets_on(rv, chart, spots, hfn, r=0.026, h=0.02):
    for (u, v) in spots:
        P, N = chart(u, v)
        rivet(rv, P + N * hfn(u, v), N, r=r, h=h, mat=STL)


# ---------------------------------------------------------------------------
# HELMET (Head): rounded kettle / nasal helm. Dome, one ridge front to back, rolled brim, short nasal.
# ---------------------------------------------------------------------------
def build_head():
    comps = []
    CLH = 0.07                               # the dome stands off the skull: room for hair
    hc = head_chart(clear=CLH)
    s_max = 0.95 + math.pi / 2 * (0.25 + CLH) + 0.35
    s_top = s_max - 0.05
    nu = 16
    ths = [-math.pi + 2 * math.pi * i / nu for i in range(nu)]

    def s_edge(th):                           # brim line: high over the brow, low at the sides and back
        w = smooth((abs(th) - 0.45) / 0.85)
        return 0.6 + lerp(0.20, -0.14, w)
    ts = [0.0, 0.06, 0.26, 0.5, 0.72, 0.88, 1.0]
    G = [[(th, lerp(s_edge(th), s_top, t)) for th in ths] for t in ts]
    dome = Comp(bevel=0.012, segs=1, angle=32)
    outer = shell(dome, hc, G, lambda j, i, u, v: 0.048 + (0.02 if j <= 1 else 0.0), wrap=True, mat=STL,
                  rim_mat=STL, flush=True)
    cap = dome.f(list(outer[-1]), STL)
    dome.bm.normal_update()
    if cap is not None and cap.normal.z < 0:
        cap.normal_flip()
    comps.append(dome)
    # rolled brim: a round roll all the way round the dome edge
    br = Comp(shade="smooth")
    pts = []
    for th in ths:
        P, N = hc(th, s_edge(th))
        pts.append(P + N * 0.034)
    tube_loop(br, pts, 0.042, STL, sides=6)
    comps.append(br)
    # the single ridge, front to back over the crown
    rg = Comp(shade="smooth")
    sf = s_edge(0.0)
    sb = s_edge(math.pi)
    path = []
    for k in range(5):
        P, N = hc(0.0, sf + (s_top - sf) * k / 4)
        path.append(P + N * 0.048)
    for k in range(1, 5):
        P, N = hc(math.pi, s_top - (s_top - sb) * k / 4)
        path.append(P + N * 0.048)
    ridge_sweep(rg, path, 0.062, 0.05, 0.035, STL)
    comps.append(rg)
    # short nasal bar from the brim down over the nose
    rings = []
    for z, w in zip((0.215, 0.10, -0.02, -0.12, -0.175), (0.05, 0.05, 0.05, 0.055, 0.066)):
        P, N = hc(0.0, z + 0.6)
        cN = P + N * 0.028
        rings.append([cN + Vector((sx * w, 0, 0)) + N * (sy * 0.02) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    nb = Comp(shade="flat")
    loft(nb, rings, STL, outward=True)
    comps.append(nb)
    # rivets in a neat row above the brim, each side
    rv = Comp(shade="smooth")
    for sg in (-1, 1):
        for deg in (60, 110):
            th = sg * math.radians(deg)
            P, N = hc(th, s_edge(th) + 0.15)
            rivet(rv, P + N * 0.048, N, r=0.026, h=0.02, mat=STL)
    comps.append(rv)
    return comps


# ---------------------------------------------------------------------------
# CHEST
# ---------------------------------------------------------------------------
def ut_vtop(ch, u, front=True):
    """Top edge of the body plate: a scooped neckline in the middle, rising onto the shoulder top."""
    k = smooth((abs(u) - 0.30) / 0.42)
    return lerp(0.615 if front else 0.66, ch.top + 0.05, k)


def ut_vbot(u):
    return -0.615 + 0.10 * (abs(u) / 0.86) ** 2


def build_upper_torso():
    comps = []
    for side in (-1, 1):
        front = side < 0
        # quilted gambeson: the neck stays below the head's underside (no overlap with the head)
        sch = torso_chart(side, rc=0.05, clear=SUIT_CL)
        sus = [-0.99, -0.62, -0.3, 0.0, 0.3, 0.62, 0.99]

        def sv(u, t):
            return lerp(-0.8, lerp(0.75, 0.85, smooth((abs(u) - 0.35) / 0.3)), t)
        gc = Comp(bevel=0.0, shade="smooth")
        shell(gc, sch, [[(u, sv(u, t)) for u in sus] for t in (0.0, 0.35, 0.8, 0.92, 1.0)], 0.004, mat=GAM, flush=True)
        comps.append(gc)
        ch = torso_chart(side, rc=0.05)
        us = [-0.86, -0.62, -0.4, -0.2, 0.0, 0.2, 0.4, 0.62, 0.86]
        ts = [0.0, 0.07, 0.32, 0.6, 0.86, 1.0]
        amp, ridge_a = (0.105, 0.05) if front else (0.055, 0.03)

        def height(t, u, roll=False):
            edge = math.sin(math.pi * clamp(t)) ** 0.6
            bulge = amp * max(0.0, 1 - (u / 0.9) ** 2) ** 1.1 * edge
            ridge = ridge_a * max(0.0, 1 - abs(u) / 0.24) ** 1.5 * edge
            return 0.045 + bulge + ridge + (0.018 if roll else 0.0)

        G = [[(u, lerp(ut_vbot(u), ut_vtop(ch, u, front), t)) for u in us] for t in ts]
        c = Comp(bevel=0.012, segs=1, angle=32)
        shell(c, ch, G, lambda j, i, u, v: height(ts[j], u, j in (0, len(ts) - 1) or i in (0, len(us) - 1)),
              mat=STL, rim_mat=STL, flush=True)
        comps.append(c)
        # rolled neck edge
        pts = []
        for k in range(7):
            u = -0.84 + 1.68 * k / 6
            v = ut_vtop(ch, u, front)
            P, N = ch(u, v)
            pts.append(P + N * (height(1.0, u, True) * 0.55))
        tb = Comp(shade="smooth")
        horn(tb, pts, 0.034, sides=5, taper=0.0, r_tip=0.034, mat=STL)
        comps.append(tb)
        # rivets: a neat row along the bottom edge and two at each armhole
        rv = Comp(shade="smooth")

        def tv(u, t):
            return lerp(ut_vbot(u), ut_vtop(ch, u, front), t)
        spots = [(u, tv(u, 0.09)) for u in ((-0.56, -0.28, 0.0, 0.28, 0.56) if front else (-0.5, 0.0, 0.5))]
        if front:
            spots += [(sg * 0.74, tv(sg * 0.74, t)) for sg in (-1, 1) for t in (0.55,)]
        rivets_on(rv, ch, spots, lambda u, v: height(clamp((v - ut_vbot(u)) / (ut_vtop(ch, u, front) - ut_vbot(u))), u))
        comps.append(rv)
    return comps


def build_lower_torso():
    comps = []
    for side in (-1, 1):
        undersuit_box(comps, lt_chart(side, SUIT_CL), [-0.99, 0, 0.99], [-0.2, 0.0, 0.2])
        ch = lt_chart(side)
        us = [-0.86 + 1.72 * i / 4 for i in range(5)]
        # leather belt
        c = Comp(bevel=0.010, segs=1, angle=34)
        shell(c, ch, [[(u, v) for u in us] for v in (-0.235, -0.22, -0.10, -0.085)],
              lambda j, i, u, v: 0.052 + (0.010 if j in (0, 3) else 0.0), lift=lambda j, i, u, v: 0.004,
              mat=LTH, rim_mat=LTH, flush=True)
        comps.append(c)
        # two plain abdomen bands, each lapping over the one below (gaps show the gambeson)
        rv = Comp(shade="smooth")
        for (v0, v1, l_hem, l_top) in ((-0.10, 0.055, 0.075, 0.03), (0.035, 0.19, 0.085, 0.05)):
            fr = [0.0, 0.12, 0.88, 1.0]
            vs = [lerp(v0, v1, f) for f in fr]
            b = Comp(bevel=0.010, segs=1, angle=34)
            shell(b, ch, [[(u, v) for u in us] for v in vs],
                  lambda j, i, u, v: 0.04 + (0.012 if j <= 1 else 0.0),
                  lift=lambda j, i, u, v, fr=fr, a=l_hem, z=l_top: lerp(a, z, fr[j]),
                  mat=STL, rim_mat=STL, flush=True)
            comps.append(b)
            rivets_on(rv, ch, ([(-0.72, lerp(v0, v1, 0.5)), (0.72, lerp(v0, v1, 0.5))] if side < 0 else []),
                      lambda u, v, a=l_hem, z=l_top, v0=v0, v1=v1: lerp(a, z, (v - v0) / (v1 - v0)) + 0.04)
        rivets_on(rv, ch, ([(-0.62, -0.16), (0.62, -0.16)] if side < 0 else []), lambda u, v: 0.056)
        comps.append(rv)
        if side < 0:
            # one plain square steel buckle
            bk = Comp(shade="flat")
            P, N = ch(0.0, -0.17)
            cy = P.y + N.y * 0.067
            hw, hh, th_, hy = 0.07, 0.065, 0.014, 0.019
            box(bk, (-hw + th_, cy, -0.17), th_, hy, hh, STL)
            box(bk, (hw - th_, cy, -0.17), th_, hy, hh, STL)
            box(bk, (0.0, cy, -0.17 + hh - th_), hw - 2 * th_, hy, th_, STL)
            box(bk, (0.0, cy, -0.17 - hh + th_), hw - 2 * th_, hy, th_, STL)
            box(bk, (0.02, cy, -0.17), hw - 2 * th_ - 0.02, hy * 0.7, 0.008, STL)
            comps.append(bk)
    return comps


def build_upper_arm():
    comps = []
    su = limb_chart(r=0.05, clear=SUIT_CL)
    undersuit_box(comps, su, lite_cols(su), [-0.334, 0.55])
    top = Comp(shade="smooth")
    tc_ = [Vector((x, y, 0.584 + SUIT_CL)) for x, y in ((-0.49, -0.49), (0.49, -0.49), (0.49, 0.49), (-0.49, 0.49))]
    top.f([top.v(p, (0, 0, 0.5, 0)) for p in tc_], GAM)
    comps.append(top)
    lc = limb_chart(r=0.05)
    L = lc.stations
    # one lame under the shoulder plate; it flares at the hem so the vambrace top slides under it
    us = lite_cols(lc)
    tvs = [0.0, 0.88, 1.0]
    zt, zb, fl = -0.10, -0.46, 0.11
    c = Comp(bevel=0.011, segs=1, angle=32)
    shell(c, lc, [[(u, lerp(zt, zb, t)) for u in us] for t in tvs], lambda j, i, u, v: 0.045 + (0.016 if j >= 1 else 0.0),
          lift=lambda j, i, u, v: fl * (0.35 + 0.65 * tvs[j] ** 1.3), mat=STL, rim_mat=STL, flush=True)
    comps.append(c)
    # the rounded shoulder plate
    ss = [0.0, 0.16, 0.36, 0.58, 0.78, 0.92, 1.0]
    NT = 8
    tt = [-1.75 + 3.5 * i / NT for i in range(NT + 1)]
    G = [[(s_ * PD_SU, t_ * PD_TV) for t_ in tt] for s_ in ss]

    def dthick(j, i, u, v):
        t_ = abs(v / PD_TV) / 1.75
        return 0.06 + 0.03 * (1 - t_ ** 2) + (0.018 if j >= len(ss) - 2 else 0.0)
    dome = Comp(bevel=0.013, segs=1, angle=32)
    shell(dome, pd_chart, G, dthick, mat=STL, rim_mat=STL, flush=True)
    comps.append(dome)
    rv = Comp(shade="smooth")
    for t_ in (-0.9, 0.0, 0.9):
        P, N = pd_chart(0.90 * PD_SU, t_ * PD_TV)
        rivet(rv, P + N * (0.06 + 0.03 * (1 - (abs(t_) / 1.75) ** 2)), N, r=0.026, h=0.02, mat=STL)
    comps.append(rv)
    return comps


def build_lower_arm():
    comps = []
    su = limb_chart(r=0.05, clear=SUIT_CL)
    undersuit_box(comps, su, lite_cols(su), [-0.52, 0.259])
    lc = limb_chart(r=0.05)
    L = lc.stations
    us = lite_cols(lc)

    def z_hi(u):
        p, _ = lc(u, 0)
        if p.y < -0.3:                                   # front: below the elbow joint, gently peaked
            return 0.06 + 0.10 * max(0.0, 1 - abs(p.x - 0.1) / 0.4)
        return lerp(0.10, 0.26 + 0.08 * max(0.0, 1 - abs(p.x) / 0.45), smooth((p.y + 0.3) / 0.8))
    tvs = [0.0, 0.1, 0.9, 1.0]                            # 0 = wrist, 1 = top
    G = [[(u, lerp(-0.47, z_hi(u), t)) for u in us] for t in tvs]
    c = Comp(bevel=0.011, segs=1, angle=32)
    shell(c, lc, G, lambda j, i, u, v: 0.055 + (0.016 if j in (0, 3) else 0.0),
          lift=lambda j, i, u, v: 0.03 * (1 - tvs[j] / 0.4) if tvs[j] < 0.4 else 0.0, mat=STL, rim_mat=STL, flush=True)
    comps.append(c)
    # one leather strap
    cols = lite_cols(lc)
    st = Comp(bevel=0.008, segs=1, angle=40)
    shell(st, lc, [[(u, z) for u in cols] for z in (-0.14, -0.04)], 0.03, lift=lambda j, i, u, v: 0.052,
          mat=LTH, rim_mat=LTH, flush=True)
    comps.append(st)
    rv = Comp(shade="smooth")
    fm = L["front_mid"]
    spots = [(fm + dx, z_hi(fm + dx) - 0.045) for dx in (-0.2, 0.0, 0.2)]
    rivets_on(rv, lc, spots, lambda u, v: 0.06)
    comps.append(rv)
    return comps


# ---------------------------------------------------------------------------
# LEGS
# ---------------------------------------------------------------------------
def build_upper_leg():
    comps = []
    su = limb_chart(r=0.05, clear=SUIT_CL)
    undersuit_box(comps, su, lite_cols(su), [-0.401, 0.421])
    lc = limb_chart(r=0.05)
    L = lc.stations
    nu = 8
    us = [0.025 + (L["corner_ob"] - 0.025) * i / nu for i in range(nu + 1)]     # front + outer

    def z_hi(u):
        p, _ = lc(u, 0)
        return 0.24 if p.y < -0.3 else lerp(0.24, 0.28, smooth((p.y + 0.3) / 0.3))
    tvs = [0.0, 0.1, 0.9, 1.0]                                                     # 0 = bottom edge
    G = [[(u, lerp(-0.36, z_hi(u), t)) for u in us] for t in tvs]
    c = Comp(bevel=0.011, segs=1, angle=32)

    def th(j, i, u, v):
        p, _ = lc(u, 0)
        ridge = 0.032 * max(0.0, 1 - abs(p.x) / 0.24) if p.y < -0.3 else 0.0
        return 0.055 + ridge + (0.016 if j in (0, 3) else 0.0)
    shell(c, lc, G, th, lift=lambda j, i, u, v: 0.03 * (1 - tvs[j]), mat=STL, rim_mat=STL, flush=True)
    comps.append(c)
    rv = Comp(shade="smooth")
    fm = L["front_mid"]
    rivets_on(rv, lc, [(fm + dx, z_hi(fm + dx) - 0.05) for dx in (-0.2, 0.0, 0.2)], lambda u, v: 0.066)
    comps.append(rv)
    return comps


def build_lower_leg_legs():
    comps = []
    su = limb_chart(r=0.05, clear=SUIT_CL)
    undersuit_box(comps, su, lite_cols(su), [-0.34, 0.379])
    lc = limb_chart(r=0.05)
    L = lc.stations

    def ridge(u):
        p, _ = lc(u, 0)
        return 0.04 * max(0.0, 1 - abs(p.x) / 0.26) if p.y < -0.3 else 0.0
    # shin greave: front + outer, a soft shin ridge and a rolled bottom edge
    nu = 8
    us = [0.025 + (L["corner_ob"] - 0.025) * i / nu for i in range(nu + 1)]
    tvs = [0.0, 0.10, 0.55, 1.0]
    c = Comp(bevel=0.011, segs=1, angle=32)
    shell(c, lc, [[(u, lerp(-0.24, 0.30, t)) for u in us] for t in tvs],
          lambda j, i, u, v: 0.06 + ridge(u) + (0.018 if j == 0 else 0.0), mat=STL, rim_mat=STL, flush=True)
    comps.append(c)
    # one leather strap all the way round, resting on the greave in front and on the padding behind
    cols = lite_cols(lc)

    def slift(j, i, u, v):
        if u <= L["corner_ob"]:
            return 0.06 + ridge(u) - 0.004
        return lerp(0.06, 0.012, smooth((u - L["corner_ob"]) / 0.25))
    st = Comp(bevel=0.008, segs=1, angle=40)
    shell(st, lc, [[(u, z) for u in cols] for z in (-0.05, 0.05)], 0.03, lift=slift, mat=LTH, rim_mat=LTH, flush=True)
    comps.append(st)
    rv = Comp(shade="smooth")
    fm = L["front_mid"]
    rivets_on(rv, lc, [(fm - 0.17, -0.185), (fm + 0.17, -0.185)], lambda u, v: 0.072)
    comps.append(rv)
    # rounded knee cop rising over the thigh plate
    kc = Comp(bevel=0.012, segs=1, angle=32)
    phis = [-72, -36, 0, 36, 72]
    zc, bz, ah = 0.38, 0.36, 0.36
    nu = 8
    Gk = []
    for ph in phis:
        z = zc + bz * math.sin(math.radians(ph))
        hw = ah * math.cos(math.radians(ph))
        Gk.append([(0.5 + (-1 + 2 * i / nu) * hw, z) for i in range(nu + 1)])

    def kth(j, i, u, v):
        s_ = abs(-1 + 2 * i / nu)
        return 0.045 + 0.11 * (1 - s_ ** 2) * math.cos(math.radians(phis[j])) + \
            (0.012 if (j in (0, len(phis) - 1) or i in (0, nu)) else 0.0)

    def klift(j, i, u, v):
        return 0.11 + 0.08 * smooth((v - 0.2) / 0.4)
    shell(kc, lc, Gk, kth, lift=klift, mat=STL, rim_mat=STL, flush=True)
    comps.append(kc)
    rk = Comp(shade="smooth")
    for sg in (-1, 1):
        u, z = 0.5 + sg * 0.29, zc
        rivets_on(rk, lc, [(u, z)], lambda u, v: klift(0, 0, u, v) + 0.045 + 0.11 * (1 - 0.8 ** 2))
    comps.append(rk)
    return comps


def build_lower_leg_boots():
    comps = []
    lc = limb_chart(r=0.05)
    cols = lite_cols(lc)
    sh = Comp(bevel=0.010, segs=1, angle=34)
    shell(sh, lc, [[(u, z) for u in cols] for z in (-0.47, -0.36)], 0.05, lift=lambda j, i, u, v: 0.012,
          mat=LTH, rim_mat=LTH, flush=True)
    comps.append(sh)
    cf = Comp(bevel=0.010, segs=1, angle=34)
    zs = (-0.40, -0.34, -0.31)
    shell(cf, lc, [[(u, z) for u in cols] for z in zs], lambda j, i, u, v: 0.045 + (0.012 if j == 2 else 0.0),
          lift=lambda j, i, u, v: 0.065, mat=LTH, rim_mat=LTH, flush=True)
    comps.append(cf)
    # the roll at the cuff's top edge
    pts = []
    for u in cols:
        P, N = lc(u, -0.31)
        pts.append(P + N * 0.092)
    tb = Comp(shade="smooth")
    horn(tb, pts, 0.032, sides=5, taper=0.0, r_tip=0.032, mat=LTH)
    comps.append(tb)
    return comps


def build_foot():
    comps = []
    prof = [(-0.47, 0.15), (-0.2, 0.15), (0.28, 0.15), (0.40, 0.13), (0.47, 0.08), (0.5, 0.0), (0.5, -0.13)]
    pc = profile_chart(prof)
    La = pc.length
    fs = [0.0, 0.2, 0.5, 0.72, 0.85, 0.93, 1.0]
    ys = [0.50, 0.30, 0.02, -0.34]                                            # heel -> just behind the toe cap
    c = Comp(bevel=0.011, segs=1, angle=34)
    shell(c, pc, [[(La * f, y) for f in fs] for y in ys], 0.05, mat_fn=lambda j, i: DRK if i >= 5 else LTH,
          mat=LTH, rim_mat=LTH, flush=True)
    comps.append(c)
    # steel toe cap: a rounded cap lofted over the toe
    tc = Comp(shade="smooth")
    cx, cz, A, B = 0.05, 0.065, 0.53, 0.195
    stations = [(-0.28, 1.0), (-0.34, 1.0), (-0.46, 1.0), (-0.52, 0.9), (-0.56, 0.68), (-0.585, 0.3)]
    sides = 10
    rings = []
    for y, sc in stations:
        ring = []
        for k in range(sides):
            a = 2 * math.pi * k / sides
            ca, sa = math.cos(a), math.sin(a)
            x = cx + A * sc * math.copysign(abs(ca) ** (2 / 3.0), ca)
            z = cz + B * sc * math.copysign(abs(sa) ** (2 / 3.0), sa)
            ring.append(Vector((x, y, max(z, -0.13))))
        rings.append(ring)
    loft(tc, rings, STL, cap0=True, cap1=True, outward=True)
    comps.append(tc)
    rv = Comp(shade="smooth")
    for x in (-0.18, 0.05, 0.28):
        z = cz + B * max(0.0, 1 - (abs(x - cx) / A) ** 3) ** (1 / 3.0)
        rivet(rv, Vector((x, -0.31, z)), Vector((0, 0, 1)), r=0.026, h=0.02, mat=STL)
    comps.append(rv)
    return comps


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
        bs = m.node_tree.nodes["Principled BSDF"]
        bs.inputs["Base Color"].default_value = rgba(PREVIEW_RGB[i])
        bs.inputs["Roughness"].default_value = 0.45 if i == STL else 0.75
        mats.append(m)
    return mats


MATS = make_materials()
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
armor_objs, glow_objs = [], []           # Iron has no glow meshes: glow_objs stays empty
for piece, part, bname, pair in SPEC:
    comps = globals()[bname]()
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

# Body proxy for previews and pose checks (never exported)
body_mat = bpy.data.materials.new("Proxy_Body")
body_mat.use_nodes = True
body_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = rgba((96, 100, 112))
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
# PAINTERLY BAKE: colour + baked lighting in one atlas per group, on unique UVs. Baked masks drive the
# paint: ambient occlusion darkens overlaps and crevices, a small-radius occlusion pass finds
# cavities, the Bevel node finds convex edges for painted edge highlights. Steel shades toward cool
# blue-grey, leather toward warm dark brown, the gambeson carries a painted quilt pattern.
# ===========================================================================
KEY = Vector((0.0, -0.55, 0.83)).normalized()       # symmetric: the set looks the same left/right
GLINT = Vector((0.0, -0.42, 0.91)).normalized()
RIM = Vector((0.0, 0.85, 0.35)).normalized()


def atlas_of(o):
    return "body" if o.name.split("_")[1] == "Chest" else "gear"


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
    rim = b.math("MAXIMUM", b.dot(Nrm, RIM), 0.0)
    light = b.math("ADD", b.math("ADD", b.math("MULTIPLY_ADD", key, 0.52, 0.16), b.math("MULTIPLY", sky, 0.32)),
                   b.math("MULTIPLY", rim, 0.26))
    ao = b.remap(b.ao(0.35, SAMPLES), 0.15, 1.0, 0.30, 1.0)
    cav = b.remap(b.ao(0.07, SAMPLES), 0.35, 1.0, 0.55, 1.0)
    occl = b.math("MULTIPLY", ao, cav)
    S = b.math("MULTIPLY", light, occl, clamp_=True)
    patches = b.math("MULTIPLY_ADD", b.noise(1.4, 1.0, 0.4, 0.3), 0.14, -0.07)
    strokes = b.math("MULTIPLY_ADD", b.noise(5.0, 1.5, 0.5, 0.6, (1.0, 1.0, 3.2)), 0.07, -0.035)
    paint = b.math("ADD", patches, strokes)
    edge = b.math("MULTIPLY", b.bevel_edge(0.018), b.smoothstep(ao, 0.55, 0.9))
    glint = b.smoothstep(b.dot(Nrm, GLINT), 0.80, 0.97)
    edge_up = b.math("MULTIPLY", edge, b.math("MULTIPLY_ADD", sky, 0.5, 0.5))
    jit = b.math("MULTIPLY_ADD", b.B, 0.16, 0.92)               # per-plate value jitter

    def tint_shade(base, lo, mid, hi):
        sh = b.ramp(b.math("ADD", S, b.math("MULTIPLY", paint, 0.6)), [(0.0, lo), (0.5, mid), (1.0, hi)])
        return b.mix(1.0, base, sh, "MULTIPLY")

    if idx == STL:
        brush = b.math("MULTIPLY_ADD", b.noise(7.0, 2.0, 0.6, 0.1, (3.0, 3.0, 0.45)), 0.20, -0.10)
        col = b.ramp(b.math("ADD", S, b.math("ADD", b.math("MULTIPLY", paint, 0.7), brush)),
                     [(0.0, (22, 28, 44)), (0.22, (48, 58, 78)), (0.42, (84, 94, 112)), (0.6, (120, 130, 146)),
                      (0.78, (160, 168, 182)), (1.0, (208, 214, 224))])
        col = b.mix(1.0, col, jit, "MULTIPLY")
        col = b.mix(b.math("MULTIPLY", glint, 0.20), col, (255, 244, 226), "ADD")
        col = b.mix(b.math("MULTIPLY", rim, 0.18), col, (14, 24, 52), "ADD")
        scuff = b.math("MULTIPLY", edge, b.smoothstep(b.noise(11.0, 2.0, 0.6, 0.4), 0.48, 0.62))
        col = b.mix(b.math("MULTIPLY", edge_up, 0.60), col, (226, 232, 240))
        col = b.mix(b.math("MULTIPLY", scuff, 0.45), col, (232, 236, 242))
        pit = b.smoothstep(b.noise(30.0, 1.0, 0.5, 0.2), 0.70, 0.78)
        col = b.mix(b.math("MULTIPLY", pit, 0.18), col, (40, 50, 68))
    elif idx == LTH:
        grain = b.math("MULTIPLY_ADD", b.noise(16.0, 2.0, 0.6, 0.3), 0.12, -0.06)
        col = b.ramp(b.math("ADD", S, b.math("ADD", b.math("MULTIPLY", paint, 0.9), grain)),
                     [(0.0, (12, 7, 5)), (0.25, (32, 18, 10)), (0.5, (60, 36, 19)), (0.72, (90, 56, 29)),
                      (0.9, (120, 78, 43)), (1.0, (148, 102, 60))])
        col = b.mix(1.0, col, jit, "MULTIPLY")
        col = b.mix(b.math("MULTIPLY", glint, 0.09), col, (220, 170, 110), "ADD")
        col = b.mix(b.math("MULTIPLY", rim, 0.20), col, (10, 16, 36), "ADD")
        col = b.mix(b.math("MULTIPLY", edge_up, 0.45), col, (168, 122, 76))
    elif idx == GAM:
        sp = b.nt.nodes.new("ShaderNodeSeparateXYZ")
        b.nt.links.new(b.geo.outputs["Position"], sp.inputs["Vector"])
        X, Y, Z = sp.outputs["X"], sp.outputs["Y"], sp.outputs["Z"]
        h = b.math("ADD", X, Y)
        K = 9.5
        d1 = b.math("SINE", b.math("MULTIPLY", b.math("ADD", h, Z), K))
        d2 = b.math("SINE", b.math("MULTIPLY", b.math("SUBTRACT", h, Z), K))
        puff = b.math("MULTIPLY_ADD", b.math("MULTIPLY", d1, d2), 0.5, 0.5)
        near = b.math("MINIMUM", b.math("ABSOLUTE", d1), b.math("ABSOLUTE", d2))
        seam = b.math("SUBTRACT", 1.0, b.smoothstep(near, 0.0, 0.2))
        base = b.ramp(b.math("ADD", puff, b.math("MULTIPLY", paint, 0.8)),
                      [(0.0, (138, 112, 80)), (0.5, (188, 160, 118)), (1.0, (226, 204, 164))])
        base = b.mix(b.math("MULTIPLY", seam, 0.75), base, (108, 82, 56))
        base = b.mix(1.0, base, jit, "MULTIPLY")
        col = tint_shade(base, (56, 50, 70), (152, 142, 144), (255, 246, 236))
        col = b.mix(b.math("MULTIPLY", edge_up, 0.25), col, (232, 208, 164))
    else:
        col = b.ramp(S, [(0.0, (10, 8, 8)), (1.0, (52, 40, 34))])
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
    scene.cycles.samples = SAMPLES
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


if not QUICK:
    bake_all(armor_objs)

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
    objs = armor_objs
    for o in objs:
        clean_mesh(o)
    select_only(objs)
    bpy.ops.export_scene.gltf(filepath=str(ROOT / "exports" / "glb" / f"{SET}.glb"), export_format="GLB",
                              use_selection=True, export_apply=True)
    bpy.ops.export_scene.fbx(filepath=str(ROOT / "exports" / "fbx" / f"{SET}.fbx"), use_selection=True,
                             object_types={"MESH"}, axis_forward="-Z", axis_up="Y", path_mode="COPY",
                             embed_textures=True, add_leaf_bones=False, mesh_smooth_type="OFF")
    report = {"set": SET, "rarity": "Common", "blender_version": bpy.app.version_string,
              "authoring": "final Roblox stud size; import at 1:1, do not scale", "pieces": {}}
    install = {"set": SET, "rarity": "Common", "helmet": "open", "glow_color_srgb": None, "glow_material": None,
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
        report["pieces"].setdefault(piece, {})[o.name] = {"body_part": o["body_part"], "triangles": tris,
                                                          "vertices": len(me.vertices)}
        sc, ss = studio(centre), studio(size)
        install["parts"][o.name] = {"piece": piece, "body_part": o["body_part"], "kind": "textured",
                                    "atlas": f"textures/{SET}-{atlas_of(o)}.png",
                                    "offset": [round(sc.x, 4), round(sc.y, 4), round(sc.z, 4)],
                                    "size": [round(abs(ss.x), 4), round(abs(ss.y), 4), round(abs(ss.z), 4)]}
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
# PREVIEW RENDERS (Eevee, bright soft daylight like the other kits)
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
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.60, 0.74, 0.90, 1)
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
    out = path or (ROOT / "previews" / f"{name}.png")
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
shoot("close-helm", (3.2, -7.6, 5.4), target=(0, 0, 4.72), lens=110)

# ---------------------------------------------------------------------------
# Numeric pose check (no pose images): rotate the proxy's part groups about their rig joints and
# count interpenetrating triangle pairs. Also counts armour poking into its own body part at rest.
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


def self_clip():
    out = {}
    for part, objs in ARMOR_BY_PART.items():
        if part not in PROXY:
            continue
        pb = world_bvh(PROXY[part])
        n = sum(len(world_bvh(o).overlap(pb)) for o in objs)
        if n:
            out[part] = n
    return out


if not NOPOSE:
    clip = {}
    for pname, rot in POSES.items():
        apply_pose(rot)
        clip[pname] = clip_report()
        log("pose", pname, sum(clip[pname].values()), "tri pairs")
    apply_pose({})
    own = self_clip()
    log("armour x own body at rest:", own)
    (ROOT / "pose-check.json").write_text(json.dumps(
        {"method": "part groups rotated about their rig joints (Blender); counts are intersecting triangle pairs",
         "poses_deg": {"walk": "arms +-35, elbows 20, legs +-35, back knee 35",
                       "run": "arms +-60, elbows 45, legs 55/60, back knee 85",
                       "jump": "arms raised 150 forward + 12 out, knees 15-30",
                       "fall": "arms raised 75 out to the sides"},
         "armour_into_own_body_at_rest": own, "results": clip}, indent=1))

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
tall = 1.2
compose("sheet", [[(PV / "front.png", tall), (PV / "threeq.png", tall), (PV / "side.png", tall),
                   (PV / "back.png", tall), (PV / "close-helm.png", tall)]], 400)

bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / f"{SET}.blend"))
log("DONE")
