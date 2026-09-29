"""Ninja armor set (Rare): a shinobi in layered dark cloth, black lacquered leather and gunmetal splints.

Run (background Blender 5.2, never the user's open scene):
  blender -b --factory-startup --threads 2 --python build_ninja.py
Env:
  QUICK=1      flat preview colours only: no bake, no exports (fast shape passes)
  VIEWS=a,b    render only these preview names (default: front, back, side, threeq, close-helm + sheet)
  NOPOSE=1     skip the numeric pose check
  DBG=1        extra debug close-ups into previews/_dbg (not a deliverable)

Self-contained: it reads only the measured body proxy (../r15-proxy/*.obj) and writes only into this folder.
Blender axes: +z up, -y = the character's front, +x = the character's LEFT. Studio = (-x, z, y) of Blender.
Every piece is modelled at final stud size on the normalized R15 body. One rigid mesh per R15 part.
"""
import bpy, bmesh, math, json, os, random, time
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from pathlib import Path

T0 = time.time()
ROOT = Path(__file__).resolve().parent
PROXY_DIR = ROOT.parent / "r15-proxy"
SET = "ninja"
PREFIX = "Ninja"
QUICK = os.environ.get("QUICK") == "1"
VIEWS = set(os.environ["VIEWS"].split(",")) if os.environ.get("VIEWS") else None
NOPOSE = os.environ.get("NOPOSE") == "1"
DBG = os.environ.get("DBG") == "1"
BAKE_SIZE = 1024          # Roblox caps textures at 1024; baked directly at that size
for d in ("exports/fbx", "exports/glb", "textures", "previews"):
    (ROOT / d).mkdir(parents=True, exist_ok=True)
if DBG:
    (ROOT / "previews" / "_dbg").mkdir(parents=True, exist_ok=True)
RNG = random.Random(23)


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
    for line in open(PROXY_DIR / f"{name}.obj"):
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
    parent, att = JOINT[child]
    return part_pos(parent) + s2b(BODY[parent]["atts"][att])


# ---------------------------------------------------------------------------
# Materials (bake inputs). Index order is shared by every component.
# ---------------------------------------------------------------------------
MAT_NAMES = ["Cloth", "Wrap", "Crimson", "Steel", "Leather", "Dark"]
CLO, WRP, CRM, STL, LTH, DRK = range(6)
PREVIEW_RGB = {CLO: (44, 48, 92), WRP: (78, 86, 122), CRM: (172, 30, 44), STL: (60, 68, 88),
               LTH: (16, 16, 26), DRK: (14, 14, 26)}


def lin(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgba(c, a=1.0):
    return (lin(c[0]), lin(c[1]), lin(c[2]), a)


# ---------------------------------------------------------------------------
# Mesh components. Every loop carries a "Detail" colour attribute read by the bake:
#   R = along the element (row fraction), G = across (column fraction), B = per-element random, A = 0
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
        for loop in face.loops:
            dd = d if d is not None else self.vd.get(loop.vert, (0.5, 0.5, 0.5, 0.0))
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


def wave(x, pitch, phase=0.0):
    """0..1 soft ridge wave."""
    return 0.5 + 0.5 * math.cos(2 * math.pi * (x / pitch + phase))


def bump(x, y, cx, cy, rx, ry):
    d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
    return max(0.0, 1.0 - d) ** 1.5


def bump1(x, c, hw):
    d = abs(x - c) / hw
    return 0.0 if d >= 1 else (1 - d * d) ** 2


UP = Vector((0, 0, 1))

# ---------------------------------------------------------------------------
# Charts: (u, v) -> (point on the body offset by the clearance, outward normal), part-local.
# ---------------------------------------------------------------------------
CL = 0.028          # gap between the body and the inside of an armour layer
SUIT_CL = 0.012     # the undersuit hugs the body under the plates


def torso_chart(side, hx=1.0, hy=0.5, hz=0.8, rc=0.12, clear=CL):
    """Front (side -1) or back (+1) face of a box torso; v runs up the face and over the top edge."""
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
    f.top = s_c + arc
    return f


def limb_chart(hx=0.5, hy=0.5, r=0.1, clear=CL):
    """Around a limb's box section, front -> outer (+x) -> back, skipping the inner face.
    u = arc length (0 at the front-inner edge), v = z."""
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


def cols_uniform(ch, n=13, edge=0.02):
    tot = ch.stations["total"]
    return [edge + (tot - 2 * edge) * k / (n - 1) for k in range(n)]


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


def s_of_z(z):
    """Head chart arc length for a height z on the front/sides (z from -0.6 to 0.6)."""
    rc = 0.25 + CL
    if z <= 0.35:
        return z + 0.6
    return 0.95 + rc * math.asin(min(1.0, (z - 0.35) / rc))


def wrap_ang(th):
    return (th + math.pi) % (2 * math.pi) - math.pi


# ---------------------------------------------------------------------------
# Shells: a thick shell from a grid of chart coordinates G[j][i] = (u, v).
#   thick(j, i, u, v) -> outward thickness ; lift(j, i, u, v) -> inner offset from the chart
#   mat_fn(j, i) -> material of outer face j,i ; rim_mat -> material of the side walls
# ---------------------------------------------------------------------------
def shell(c, chart, G, thick, *, lift=None, wrap=False, mat=CLO, mat_fn=None, rim_mat=None, rnd=None):
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
            d = (j / max(1, rows - 1), i / max(1, cols - 1), rnd, 0.0)
            ri.append(c.v(P + N * lo, d))
            ro.append(c.v(P + N * (lo + t), d))
        inner.append(ri)
        outer.append(ro)
    ucount = cols if wrap else cols - 1
    fo, fr = [], []
    for j in range(rows - 1):
        for i in range(ucount):
            i2 = (i + 1) % cols
            m = mat_fn(j, i) if mat_fn else mat
            fo.append(c.f([outer[j][i], outer[j][i2], outer[j + 1][i2], outer[j + 1][i]], m))
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
    jm, im = (rows - 1) // 2, ucount // 2
    probe = fo[jm * ucount + im] if fo else None
    u, v = G[jm][im]
    _, N = chart(u, v)
    c.bm.normal_update()
    if probe is not None and probe.normal.dot(N) < 0:
        for f in fo + fr:
            if f is not None:
                f.normal_flip()
    return outer


def grid(us, vs):
    return [[(u, v) for u in us] for v in vs]


def bezier(p0, p1, p2, p3, t):
    a = 1 - t
    return p0 * a ** 3 + p1 * 3 * a * a * t + p2 * 3 * a * t * t + p3 * t ** 3


def curve_pts(p0, p1, p2, p3, n):
    return [bezier(p0, p1, p2, p3, k / (n - 1)) for k in range(n)]


def loft(c, rings, mat, cap0=True, cap1=True, closed=True, outward=None):
    V = [[c.v(p) for p in ring] for ring in rings]
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


def sweep(c, pts, section, *, up=None, mat=CLO, cap=True, scale_fn=None):
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
    faces, V = loft(c, rings, mat, cap0=cap, cap1=cap)
    f0 = faces[0]
    ctr = sum(rings[0], Vector()) / len(rings[0])
    ctr1 = sum(rings[1], Vector()) / len(rings[1])
    if f0 is not None and f0.normal.dot(f0.calc_center_median() - (ctr + ctr1) / 2) < 0:
        for f in faces:
            if f is not None:
                f.normal_flip()
    return faces


def se_section(a, b, n=10, p=3.0):
    """Rounded-rectangle (superellipse) section with half sizes a, b."""
    out = []
    for k in range(n):
        t = 2 * math.pi * k / n
        cs, sn = math.cos(t), math.sin(t)
        out.append((a * math.copysign(abs(cs) ** (2 / p), cs), b * math.copysign(abs(sn) ** (2 / p), sn)))
    return out


def blob(c, ctr, radii, mat, ax=None, sides=8, lats=(-72, -36, 0, 36, 72)):
    """A soft ellipsoid lump (knots)."""
    ax = ax or (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
    rings = []
    for la in lats:
        a = math.radians(la)
        rr, zz = math.cos(a), math.sin(a)
        rings.append([ctr + ax[0] * radii[0] * rr * math.cos(2 * math.pi * s / sides) +
                      ax[1] * radii[1] * rr * math.sin(2 * math.pi * s / sides) + ax[2] * radii[2] * zz
                      for s in range(sides)])
    loft(c, rings, mat, cap0=True, cap1=True, outward=True)


def rivet(c, P, N, r=0.028, h=0.018, sides=6, mat=STL):
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


def splints(c, chart, centres, z0, z1, hw, lift_fn, thick=0.03, mat=STL):
    """A row of vertical steel splints (kote / kyahan bars), rounded ends, crowned faces."""
    rows = [(z0, hw * 0.62), (z0 + 0.022, hw), (0.5 * (z0 + z1), hw), (z1 - 0.022, hw), (z1, hw * 0.62)]
    for u0 in centres:
        G = [[(u0 - w + 2 * w * i / 2, z) for i in range(3)] for z, w in rows]
        shell(c, chart, G, lambda j, i, u, v, u0=u0: thick * (0.7 if j in (0, 4) else 1.0) +
              0.012 * (1 - ((u - u0) / hw) ** 2), lift=lambda j, i, u, v: lift_fn(u, v), mat=mat)


# ---------------------------------------------------------------------------
# PIECES. Each builder returns the list of Comp for one body part (left side; right is mirrored).
# ---------------------------------------------------------------------------
# ----- Hood (Head): cloth hood, forehead plate on a crimson headband, face mask with an eye slit ------
def cap_t(th, z):
    """Hood cloth thickness at head angle th (0 = front) and height z."""
    th = wrap_ang(th)
    back = math.pi - abs(th)
    t = 0.07
    t += 0.085 * bump(back, z, 0.0, 0.30, 1.2, 0.46)              # gathered cloth mass at the back
    t += 0.085 * bump(abs(th), z, 0.0, 0.62, 1.5, 0.34)            # crown puff
    seam = max(0.0, 1 - abs(math.sin(th)) / 0.16) ** 1.5
    t += 0.022 * seam * smooth((z - 0.30) / 0.25)                # soft crown seam front to back
    return t


def build_head():
    comps = []
    hc = head_chart()
    TS = math.radians(48)                 # half angle of the eye-slit wedge on the front
    ZB, ZT = -0.04, 0.27                  # eye slit bottom / top
    nu = 18
    ths = [-math.pi + 2 * math.pi * i / nu for i in range(nu)]

    def zof(s):
        return head_profile(s, CL)[1]

    # 1. crown cap over everything above the slit
    s_rows = [s_of_z(0.26), 0.95, 1.06, 1.17, 1.3867, 1.55]
    cap = Comp(bevel=0.014, segs=1, angle=58, shade="smooth")
    outer = shell(cap, hc, [[(th, s) for th in ths] for s in s_rows],
                  lambda j, i, th, s: cap_t(th, zof(s)) - (0.02 if j == 0 else 0.0), wrap=True, mat=CLO)
    fill = cap.f(list(outer[-1]), CLO)
    cap.bm.normal_update()
    if fill is not None and fill.normal.z < 0:
        fill.normal_flip()
    comps.append(cap)

    # 2. hood sides and back, from the neck rim up under the cap (open at the eye wedge)
    ns = 16
    span = 2 * math.pi - 2 * TS
    ths2 = [TS + span * i / ns for i in range(ns + 1)]
    zs2 = [-0.60, -0.572, -0.50, -0.25, 0.05, 0.31]
    side = Comp(bevel=0.014, segs=1, angle=58, shade="smooth")
    shell(side, hc, [[(th, s_of_z(z)) for th in ths2] for z in zs2],
          lambda j, i, th, s: [0.05, 0.085, 0.066, 0.064, 0.066, 0.07][j] +
          0.03 * bump(math.pi - abs(wrap_ang(th)), zof(s), 0.0, -0.10, 1.0, 0.45), mat=CLO)
    comps.append(side)

    # 3. face mask: wrapped cloth over the lower face, rolled top edge, soft diagonal folds
    TM = TS + 0.10
    nm = 12
    ths3 = [-TM + 2 * TM * i / nm for i in range(nm + 1)]
    zs3 = [-0.47, -0.44, -0.33, -0.22, -0.12, -0.065, -0.035]

    def mask_t(j, i, th, s):
        z = zs3[j]
        t = 0.088 + [-0.03, 0.005, 0, 0, 0, 0.026, 0.008][j]
        t += 0.024 * bump(th, z, 0.0, -0.20, 0.55, 0.22)                        # nose and cheek volume
        t += 0.016 * wave(z + 0.45 * th, 0.34) * smooth((z + 0.44) / 0.1) * smooth((-0.03 - z) / 0.03)
        edge = smooth((abs(th) - TS * 0.7) / (TM - TS * 0.7))                  # blend into the hood at the sides
        return 0.064 + (t - 0.064) * (1 - edge)
    mask = Comp(bevel=0.014, segs=1, angle=58, shade="smooth")
    shell(mask, hc, [[(th, s_of_z(z)) for th in ths3] for z in zs3], mask_t, mat=WRP)
    comps.append(mask)
    # neck scarf: a thick wrapped collar around the lower hood and mask edge (breaks the drum outline)
    scarf = Comp(bevel=0.014, segs=1, angle=58, shade="smooth")
    zsc = [-0.625, -0.595, -0.52, -0.45, -0.415]
    tsc = [0.05, 0.11, 0.125, 0.11, 0.05]
    ths_s = [-math.pi + 2 * math.pi * i / 16 for i in range(16)]
    shell(scarf, hc, [[(th, s_of_z(z)) for th in ths_s] for z in zsc],
          lambda j, i, th, s: tsc[j] + (0.016 * wave(th + 2.0 * zsc[j], 0.85) if 0 < j < 4 else 0.0), wrap=True, mat=CLO)
    comps.append(scarf)

    # 4. crimson hood lining: piping around the eye slit
    pip = Comp(shade="smooth")
    rho_t, rho_z = 0.10, 0.07
    path = []
    for z in (ZT, 0.16, 0.05):
        path.append((-TS, z))
    cth, cz = -TS + rho_t, ZB + rho_z
    for a in (180, 225, 270):
        path.append((cth + rho_t * math.cos(math.radians(a)), cz + rho_z * math.sin(math.radians(a))))
    for k in range(1, 4):
        path.append((lerp(cth, -cth, k / 4), ZB))
    for a in (270, 315, 360):
        path.append((-cth + rho_t * math.cos(math.radians(a)), cz + rho_z * math.sin(math.radians(a))))
    for z in (0.05, 0.16, ZT):
        path.append((TS, z))
    pts = []
    for th, z in path:
        z = clamp(z, -0.6, 0.55)
        P, N = hc(th, s_of_z(z))
        pts.append(P + N * (0.064 + 0.028 * smooth((0.10 - z) / 0.12)))
    p0N = hc(path[0][0], s_of_z(path[0][1]))[1]
    sweep(pip, pts, se_section(0.03, 0.03, 5, 2.0), up=p0N, mat=CRM)
    comps.append(pip)

    # 5. crimson headband around the head, following the hood
    band = Comp(bevel=0.012, segs=1, angle=58, shade="smooth")
    bz = [0.29, 0.315, 0.39, 0.46, 0.495]
    bt = [0.03, 0.05, 0.046, 0.05, 0.03]
    shell(band, hc, [[(th, s_of_z(z)) for th in ths] for z in bz], lambda j, i, th, s: bt[j],
          lift=lambda j, i, th, s: cap_t(th, zof(s)) - 0.008, wrap=True, mat=CRM)
    comps.append(band)

    # 6. hachigane: gunmetal forehead plate, rounded corners, crowned centre, two rivets
    plate = Comp(bevel=0.011, segs=1, angle=34)
    prow = [(0.300, 0.40), (0.322, 0.50), (0.385, 0.55), (0.455, 0.50), (0.480, 0.40)]
    ncol = 7
    Gp = [[(-hw + 2 * hw * i / (ncol - 1), s_of_z(z)) for i in range(ncol)] for z, hw in prow]
    shell(plate, hc, Gp, lambda j, i, th, s: 0.042 + 0.022 * max(0.0, 1 - abs(th) / 0.56) ** 1.2 * (1 if 0 < j < 4 else 0.5),
          lift=lambda j, i, th, s: cap_t(th, zof(s)) + 0.03, mat=STL)
    for th in (-0.42, 0.42):
        P, N = hc(th, s_of_z(0.39))
        rivet(plate, P + N * (cap_t(th, 0.39) + 0.03 + 0.05), N, r=0.024, h=0.02)
    comps.append(plate)

    # 7. the knot at the back with two short, thick rounded tails blended into it
    Pk, Nk = hc(math.pi, s_of_z(0.40))
    C = Pk + Nk * (cap_t(math.pi, 0.40) + 0.046 + 0.06)
    kn = Comp(shade="smooth")
    blob(kn, C, (0.16, 0.11, 0.11), CRM, sides=8)
    blob(kn, C + Vector((0.0, 0.01, -0.08)), (0.11, 0.09, 0.09), CRM, sides=8)
    for sg in (-1, 1):
        pth = curve_pts(C + Vector((0, 0.02, -0.03)), C + Vector((sg * 0.10, 0.06, -0.14)),
                        C + Vector((sg * 0.19, 0.05, -0.32)), C + Vector((sg * 0.24, 0.0, -0.56)), 7)
        sweep(kn, pth, se_section(0.065, 0.125, 8, 3.0), up=Vector((0, 1, 0)), mat=CRM,
              scale_fn=lambda t: 1.0 - 0.16 * t if t < 0.95 else 0.45)
    comps.append(kn)
    return comps


# ----- UpperTorso: cross-over cloth tunic, leather chest guard, crimson sash ------------------------
def e_top(v):
    """Lapel edge of the top (wearer's left) panel: from the neck down across to the wearer's right hip."""
    v = min(v, 0.78)
    return 0.14 - (0.78 - v) * 0.55


def e_und(v):
    """Lapel edge of the under (wearer's right) panel."""
    v = min(v, 0.78)
    return min(0.62, -0.28 + (0.78 - v) * 0.55)


def pooch(v):
    return 0.028 * bump1(v, -0.30, 0.17)          # cloth bunching just above the sash


def build_upper_torso():
    comps = []
    for side in (-1, 1):
        ch = torso_chart(side)
        vmax = ch.top + 0.38
        under = Comp(shade="smooth")
        shell(under, torso_chart(side, clear=SUIT_CL), grid([-0.99, -0.5, 0, 0.5, 0.99],
                                                               [-0.8, -0.3, 0.2, 0.6, 0.9, vmax]), 0.004, mat=DRK)
        comps.append(under)
        NV = 9
        vs = [-0.8 + (vmax + 0.8) * k / (NV - 1) for k in range(NV)]
        if side < 0:
            F_UND = [0, 0.14, 0.28, 0.42, 0.56, 0.7, 0.84, 0.92, 0.96, 1.0]
            F_TOP = [0, 0.05, 0.1, 0.22, 0.36, 0.5, 0.65, 0.8, 0.9, 1.0]
            cu = Comp(bevel=0.016, segs=1, angle=58, shade="smooth")
            shell(cu, ch, [[(lerp(-0.99, e_und(v), f), v) for f in F_UND] for v in vs],
                  lambda j, i, u, v: 0.04 + 0.014 * wave(u - 0.55 * v, 0.6) + (0.02 if i >= 7 else 0.0) + pooch(v),
                  mat_fn=lambda j, i: WRP if i >= 7 else CLO, mat=CLO)
            comps.append(cu)
            ct = Comp(bevel=0.016, segs=1, angle=58, shade="smooth")
            shell(ct, ch, [[(lerp(e_top(v), 0.99, f), v) for f in F_TOP] for v in vs],
                  lambda j, i, u, v: 0.045 + 0.034 * wave(u - 0.55 * v, 0.62) * smooth((u - e_top(v)) / 0.16) * smooth((v + 0.5) / 0.25) +
                  (0.02 if i <= 1 else 0.0) + pooch(v),
                  lift=lambda j, i, u, v: 0.025, mat_fn=lambda j, i: WRP if i <= 1 else CLO, mat=CLO)
            comps.append(ct)
            # lacquered leather chest guard: two lames, the lower one overlapping the upper
            for (rows, lift_, t0) in (
                    ([(0.20, 0.28), (0.235, 0.32), (0.30, 0.33), (0.37, 0.32), (0.42, 0.26)], 0.075, 0.05),
                    ([(-0.08, 0.17), (-0.05, 0.25), (0.03, 0.28), (0.14, 0.29), (0.225, 0.29)], 0.095, 0.05)):
                g = Comp(bevel=0.012, segs=1, angle=34)
                nc = 7
                G = [[(-hw + 2 * hw * i / (nc - 1), v) for i in range(nc)] for v, hw in rows]
                lower = rows[0][0] < 0.0
                shell(g, ch, G, lambda j, i, u, v, lower=lower, t0=t0, rows=rows:
                      t0 * (0.62 if (lower and j == len(rows) - 1) else 1.0) +
                      0.02 * (1 - (u / rows[j][1]) ** 2) + (0.012 if j == 0 else 0.0),
                      lift=lambda j, i, u, v, l=lift_: l, mat=LTH)
                comps.append(g)
        else:
            cb = Comp(bevel=0.016, segs=1, angle=58, shade="smooth")
            F = [k / 9 for k in range(10)]
            shell(cb, ch, [[(lerp(-0.99, 0.99, f), v) for f in F] for v in vs],
                  lambda j, i, u, v: 0.045 + 0.026 * wave(u * (0.85 + 0.25 * (v + 0.8)), 0.6) + pooch(v),
                  lift=lambda j, i, u, v: 0.0, mat=CLO)
            comps.append(cb)
            for (rows, lift_) in (([(0.16, 0.26), (0.20, 0.30), (0.27, 0.31), (0.34, 0.30), (0.38, 0.24)], 0.075),
                                  ([(-0.10, 0.16), (-0.07, 0.23), (0.0, 0.26), (0.10, 0.27), (0.19, 0.27)], 0.095)):
                g = Comp(bevel=0.012, segs=1, angle=34)
                G = [[(-hw + 2 * hw * i / 6, v) for i in range(7)] for v, hw in rows]
                lower = rows[0][0] < 0.0
                shell(g, ch, G, lambda j, i, u, v, lower=lower, rows=rows:
                      0.05 * (0.62 if (lower and j == len(rows) - 1) else 1.0) + 0.02 * (1 - (u / rows[j][1]) ** 2) +
                      (0.012 if j == 0 else 0.0), lift=lambda j, i, u, v, l=lift_: l, mat=LTH)
                comps.append(g)
        # crimson sash: its top part wraps the bottom of the tunic
        sc = Comp(bevel=0.015, segs=1, angle=58, shade="smooth")
        svs = [-0.80, -0.775, -0.70, -0.61, -0.552, -0.52]
        st = [0.06, 0.06, 0.06, 0.066, 0.085, 0.062]
        F = [k / 9 for k in range(10)]
        shell(sc, ch, [[(lerp(-0.99, 0.99, f), v) for f in F] for v in svs],
              lambda j, i, u, v: st[j] + (0.010 * wave(v + 0.3 * u, 0.2) if 0 < j < 4 else 0.0),
              lift=lambda j, i, u, v: 0.05, mat=CRM)
        comps.append(sc)
    return comps


# ----- LowerTorso: the wide sash and its knot at the wearer's left hip ------------------------------
def build_lower_torso():
    comps = []
    for side in (-1, 1):
        ch = lt_chart(side)
        under = Comp(shade="smooth")
        shell(under, lt_chart(side, SUIT_CL), grid([-0.99, 0, 0.99], [-0.2, 0.0, 0.2]), 0.004, mat=DRK)
        comps.append(under)
        us = [-0.985 + 1.97 * i / 9 for i in range(10)]
        vs = [-0.2, -0.185, -0.12, -0.02, 0.09, 0.17, 0.2]
        base = [0.06, 0.10, 0.11, 0.112, 0.11, 0.11, 0.11]
        c = Comp(bevel=0.015, segs=1, angle=58, shade="smooth")
        shell(c, ch, grid(us, vs), lambda j, i, u, v: base[j] + (0.010 * wave(v + 0.3 * u, 0.2) if 0 < j < 6 else 0.0),
              mat=CRM)
        comps.append(c)
    # the knot: chunky, on the front of the left hip (x stays inside the torso side plane), two short tails
    kn = Comp(shade="smooth")
    C = Vector((0.64, -(0.5 + CL + 0.11 + 0.07), -0.01))
    blob(kn, C, (0.18, 0.105, 0.14), CRM, sides=8)
    blob(kn, C + Vector((0.0, -0.01, -0.09)), (0.12, 0.09, 0.09), CRM, sides=8)
    tails = (
        [C + Vector((0.05, 0.0, -0.06)), C + Vector((0.09, -0.05, -0.20)), C + Vector((0.14, -0.10, -0.34)),
         C + Vector((0.18, -0.13, -0.46))],
        [C + Vector((-0.05, 0.0, -0.06)), C + Vector((-0.08, -0.07, -0.22)), C + Vector((-0.06, -0.14, -0.36)),
         C + Vector((-0.02, -0.17, -0.48))])
    for pts4 in tails:
        pth = curve_pts(pts4[0], pts4[1], pts4[2], pts4[3], 6)
        sweep(kn, pth, se_section(0.036, 0.085, 8, 3.0), up=Vector((0, -1, 0)), mat=CRM,
              scale_fn=lambda t: 1.0 - 0.12 * t if t < 0.94 else 0.45)
    comps.append(kn)
    return comps


# ----- Upper arm: gathered cloth sleeve, cloth skirt and leather cap shoulder guard (2 layers) -------
PD_O = Vector((0.0, 0.0, 0.03))       # guard dome centre (arm-local)
PD_R = Vector((0.74, 0.63, 0.68))     # superquadric semi-axes: encloses the arm's rounded top corners
PD_N = 3.6
PD_SU, PD_TV = 1.30, 0.47


def pd_raw(s, t):
    """Point and normal on the guard dome. s: 0 inner top edge -> 1 outer rim; t: -1.4 front -> 1.4 back."""
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


def sleeve_lift(v):
    if v >= -0.30:
        return 0.02 + 0.045 * bump1(v, 0.05, 0.36)
    return 0.02 + 0.055 * smooth((-0.30 - v) / 0.2)


def build_upper_arm():
    comps = []
    lc = limb_chart()
    cols = cols_uniform(lc)
    rows = [0.55, 0.32, 0.12, -0.06, -0.20, -0.30, -0.36, -0.44, -0.52]
    sv = Comp(bevel=0.016, segs=1, angle=58, shade="smooth")
    shell(sv, lc, [[(u, v) for u in cols] for v in rows],
          lambda j, i, u, v: 0.045 + 0.013 * wave(u, 0.72) * bump1(v, 0.0, 0.5) + (0.02 if j == len(rows) - 2 else 0.0)
          - (0.012 if j == len(rows) - 1 else 0.0),
          lift=lambda j, i, u, v: sleeve_lift(v), mat=CLO)
    comps.append(sv)
    # crimson cord gathering the sleeve above the elbow
    cd = Comp(bevel=0.0, shade="smooth")
    shell(cd, lc, [[(u, v) for u in cols] for v in (-0.328, -0.30, -0.272)], lambda j, i, u, v: (0.022, 0.04, 0.022)[j],
          lift=lambda j, i, u, v: 0.05, mat=CRM)
    comps.append(cd)
    # guard layer 1: slate cloth skirt over the sleeve top, rolled hem
    ss = [0.0, 0.14, 0.30, 0.46, 0.60, 0.72, 0.80, 0.86]
    tt = [-1.75 + 3.5 * i / 12 for i in range(13)]
    dB = Comp(bevel=0.014, segs=1, angle=58, shade="smooth")
    shell(dB, pd_chart, [[(s_ * PD_SU, t_ * PD_TV) for t_ in tt] for s_ in ss],
          lambda j, i, u, v: 0.048 + 0.02 * (1 - (abs(v / PD_TV) / 1.75) ** 2) + [0, 0, 0, 0, 0, 0.004, 0.022, -0.006][j],
          mat=WRP)
    comps.append(dB)
    # guard layer 2: black lacquered leather cap on top, rolled rim
    sa = [0.0, 0.10, 0.24, 0.38, 0.50, 0.58, 0.64]
    ta = [-1.35 + 2.7 * i / 10 for i in range(11)]
    dA = Comp(bevel=0.014, segs=1, angle=34)
    shell(dA, pd_chart, [[(s_ * PD_SU, t_ * PD_TV) for t_ in ta] for s_ in sa],
          lambda j, i, u, v: 0.05 + 0.02 * (1 - (abs(v / PD_TV) / 1.35) ** 2) + [0, 0, 0, 0, 0.004, 0.02, -0.006][j],
          lift=lambda j, i, u, v: 0.056, mat=LTH)
    comps.append(dA)
    return comps


# ----- Lower arm: wrapped bracer with three steel splints (kote) ------------------------------------
def build_lower_arm():
    comps = []
    lc = limb_chart()
    L = lc.stations
    cols = cols_uniform(lc)

    def z_hi(u):
        p, _ = lc(u, 0)
        if p.y < -0.3:                                           # front: stays below the elbow joint
            return 0.06 + 0.05 * max(0.0, 1 - abs(p.x - 0.1) / 0.4)
        return lerp(0.10, 0.28, smooth((p.y + 0.3) / 0.8))
    nrow = 11
    G = [[(u, lerp(-0.47, z_hi(u), j / (nrow - 1))) for u in cols] for j in range(nrow)]
    br = Comp(bevel=0.013, segs=1, angle=58, shade="smooth")

    def th(j, i, u, v):
        t = 0.043 + 0.018 * wave(v, 0.17)
        if j == 1 or j == nrow - 2:
            t += 0.014
        return t - (0.012 if j in (0, nrow - 1) else 0.0)
    shell(br, lc, G, th, mat=WRP)
    comps.append(br)
    cd = Comp(bevel=0.0, shade="smooth")
    shell(cd, lc, [[(u, v) for u in cols] for v in (-0.462, -0.435, -0.408)], lambda j, i, u, v: (0.02, 0.035, 0.02)[j],
          lift=lambda j, i, u, v: 0.05, mat=CRM)
    comps.append(cd)
    st = Comp(bevel=0.01, segs=1, angle=34)
    splints(st, lc, [0.72, 1.0, 1.28], -0.385, -0.02, 0.066, lambda u, v: 0.058, thick=0.03)
    comps.append(st)
    return comps


# ----- Legs: loose trousers tapering into wrapped shins (kyahan) with steel splints and a knee pad ---
def build_upper_leg():
    comps = []
    lc = limb_chart()
    cols = cols_uniform(lc, 13, 0.03)
    zhi = 0.40

    def z_lo(u):
        p, _ = lc(u, 0)
        return lerp(-0.43, -0.38, smooth(p.y / 0.5))
    tvs = [0.0, 0.09, 0.26, 0.46, 0.68, 0.86, 1.0]

    def puff(t):
        return 0.11 * (t ** 0.8) * (1 - t ** 3)
    c = Comp(bevel=0.016, segs=1, angle=58, shade="smooth")
    shell(c, lc, [[(u, lerp(z_lo(u), zhi, t)) for u in cols] for t in tvs],
          lambda j, i, u, v: [0.036, 0.056, 0.048, 0.048, 0.048, 0.048, 0.04][j] +
          0.014 * wave(u, 0.6) * smooth(tvs[j] * 3),
          lift=lambda j, i, u, v: 0.012 + puff(tvs[j]), mat=CLO)
    comps.append(c)
    return comps


def build_lower_leg_legs():
    comps = []
    lc = limb_chart()
    cols = cols_uniform(lc, 13, 0.03)
    # kyahan: clean wrapped bands from the ankle cuff up to the knee tie
    nrow = 10
    z0, z1 = -0.30, 0.08
    wr = Comp(bevel=0.013, segs=1, angle=58, shade="smooth")

    def th(j, i, u, v):
        t = 0.045 + 0.018 * wave(v, 0.14)
        if j == 1 or j == nrow - 2:
            t += 0.012
        return t - (0.012 if j in (0, nrow - 1) else 0.0)
    shell(wr, lc, [[(u, lerp(z0, z1, j / (nrow - 1))) for u in cols] for j in range(nrow)], th,
          lift=lambda j, i, u, v: 0.012, mat=WRP)
    comps.append(wr)
    # trousers gathering in over the knee: loose at the top, tied at the shin
    def z_top(u):
        p, _ = lc(u, 0)
        return lerp(0.50, 0.36, smooth((p.y + 0.1) / 0.5))
    tvs = [0.0, 0.12, 0.3, 0.55, 0.8, 1.0]
    tr = Comp(bevel=0.016, segs=1, angle=58, shade="smooth")
    shell(tr, lc, [[(u, lerp(0.08, z_top(u), t)) for u in cols] for t in tvs],
          lambda j, i, u, v: 0.042 + 0.012 * wave(u, 0.6) * smooth(tvs[j] * 3) - (0.008 if j == 0 else 0.0),
          lift=lambda j, i, u, v: 0.008 + 0.05 * tvs[j] ** 0.8, mat=CLO)
    comps.append(tr)
    cd = Comp(bevel=0.0, shade="smooth")
    shell(cd, lc, [[(u, v) for u in cols] for v in (0.048, 0.076, 0.104)], lambda j, i, u, v: (0.024, 0.04, 0.024)[j],
          lift=lambda j, i, u, v: 0.046, mat=CRM)
    comps.append(cd)
    # three steel splints down the shin
    st = Comp(bevel=0.01, segs=1, angle=34)
    splints(st, lc, [0.31, 0.5, 0.69], -0.285, 0.035, 0.062, lambda u, v: 0.05, thick=0.03)
    comps.append(st)
    # small lacquered knee pad
    kp = Comp(bevel=0.012, segs=1, angle=34)
    krows = [(0.17, 0.08), (0.21, 0.15), (0.30, 0.19), (0.42, 0.19), (0.52, 0.15), (0.585, 0.07)]
    Gk = [[(0.5 - hw + 2 * hw * i / 6, z) for i in range(7)] for z, hw in krows]
    shell(kp, lc, Gk, lambda j, i, u, v: 0.05 + 0.024 * max(0.0, 1 - abs(u - 0.5) / krows[j][1]) ** 1.2 - (0.014 if j in (0, 5) else 0.0),
          lift=lambda j, i, u, v: 0.115, mat=LTH)
    comps.append(kp)
    return comps


# ----- Boots: tabi with a split toe, wrapped cuff -------------------------------------------------
def build_lower_leg_boots():
    comps = []
    lc = limb_chart()
    cols = cols_uniform(lc, 13, 0.03)
    zs = [-0.545, -0.52, -0.45, -0.395, -0.345, -0.30]
    wr = Comp(bevel=0.013, segs=1, angle=58, shade="smooth")
    shell(wr, lc, [[(u, z) for u in cols] for z in zs],
          lambda j, i, u, v: [0.036, 0.062, 0.05, 0.062, 0.05, 0.036][j], lift=lambda j, i, u, v: 0.03, mat=WRP)
    comps.append(wr)
    return comps


def foot_ring(y, x_in, x_out, z_bot, z_top, n=12, p=4.0):
    cx, cz = (x_in + x_out) / 2, (z_bot + z_top) / 2
    a, b = (x_out - x_in) / 2, (z_top - z_bot) / 2
    pts = []
    for k in range(n):
        t = 2 * math.pi * k / n
        cs, sn = math.cos(t), math.sin(t)
        pts.append(Vector((cx + a * math.copysign(abs(cs) ** (2 / p), cs), y, cz + b * math.copysign(abs(sn) ** (2 / p), sn))))
    return pts


def build_foot():
    comps = []
    XI, XO, ZB = -0.47, 0.578, -0.15
    main_st = [(0.585, -0.34, 0.44, -0.06, 0.11), (0.55, -0.44, 0.535, -0.11, 0.175), (0.42, XI, XO, ZB, 0.20),
               (0.10, XI, XO, ZB, 0.205), (-0.20, XI, XO, ZB, 0.20), (-0.30, XI, XO, ZB, 0.195), (-0.45, XI, XO, ZB, 0.19)]
    body = Comp(bevel=0.012, segs=1, angle=58, shade="smooth")
    loft(body, [foot_ring(y, xi, xo, zb, zt) for y, xi, xo, zb, zt in main_st], CLO, outward=True)
    comps.append(body)
    # the split toe: a big-toe lobe and a four-toe lobe with a cleft between them
    lobeA = [(-0.30, -0.47, -0.20, ZB, 0.19), (-0.45, -0.47, -0.20, ZB, 0.19), (-0.57, -0.46, -0.215, -0.14, 0.16),
             (-0.665, -0.40, -0.26, -0.10, 0.115)]
    lobeB = [(-0.30, -0.105, XO, ZB, 0.19), (-0.45, -0.105, XO, ZB, 0.19), (-0.57, -0.09, 0.55, -0.14, 0.16),
             (-0.665, -0.05, 0.47, -0.10, 0.115)]
    toes = Comp(bevel=0.01, segs=1, angle=58, shade="smooth")
    for lobe in (lobeA, lobeB):
        loft(toes, [foot_ring(y, xi, xo, zb, zt, n=12, p=3.4) for y, xi, xo, zb, zt in lobe], CLO, outward=True)
    comps.append(toes)
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
        bs.inputs["Roughness"].default_value = 0.4 if i in (STL, LTH) else 0.75
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
        print("  comps", name, [sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs])
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
armor_objs = []
for piece, part, bname, pair in SPEC:
    comps = globals()[bname]()
    if pair:
        sides = [("Left", comps), ("Right", [c.mirrored() for c in comps])]
    else:
        sides = [("", comps)]
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
# Body proxy for previews, the bake's contact occlusion and the pose check (never exported)
# ---------------------------------------------------------------------------
body_mat = bpy.data.materials.new("Proxy_Body")
body_mat.use_nodes = True
body_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = rgba((214, 176, 150))
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
# PAINTERLY BAKE: colour + soft lighting in one atlas per group, on unique UVs.
# Baked masks drive the paint: ambient occlusion darkens overlaps and folds, a small-radius occlusion
# pass finds cavities, the Bevel node finds convex edges for painted edge highlights. Cloth shades toward
# blue-violet, steel is gunmetal with cool glints, leather is black lacquer, crimson is the only warm hue.
# ===========================================================================
KEY = Vector((0.0, -0.55, 0.83)).normalized()       # symmetric: the set looks the same left/right
GLINT = Vector((0.0, -0.42, 0.91)).normalized()
RIM = Vector((0.0, 0.85, 0.35)).normalized()


def atlas_of(o):
    piece = o.name.split("_")[1]
    if piece == "Helmet":
        return "helmet"
    if piece == "Chest":
        return "torso"
    return "legs"


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

    def pos_z(self):
        n = self.nt.nodes.new("ShaderNodeSeparateXYZ")
        self.nt.links.new(self.geo.outputs["Position"], n.inputs["Vector"])
        return n.outputs["Z"]

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
    ao = b.remap(b.ao(0.35), 0.15, 1.0, 0.30, 1.0)
    cav = b.remap(b.ao(0.07), 0.35, 1.0, 0.55, 1.0)
    occl = b.math("MULTIPLY", ao, cav)
    S = b.math("MULTIPLY", light, occl, clamp_=True)
    patches = b.math("MULTIPLY_ADD", b.noise(1.4, 1.0, 0.4, 0.3), 0.14, -0.07)
    strokes = b.math("MULTIPLY_ADD", b.noise(6.0, 1.5, 0.5, 0.6, (1.0, 1.0, 3.4)), 0.07, -0.035)
    paint = b.math("ADD", patches, strokes)
    edge = b.math("MULTIPLY", b.bevel_edge(0.018), b.smoothstep(ao, 0.55, 0.9))
    glint = b.smoothstep(b.dot(Nrm, GLINT), 0.80, 0.97)
    rim = b.math("MAXIMUM", b.dot(Nrm, RIM), 0.0)
    edge_up = b.math("MULTIPLY", edge, b.math("MULTIPLY_ADD", sky, 0.5, 0.5))
    jit = b.math("MULTIPLY_ADD", b.B, 0.22, 0.89)            # per-element value jitter 0.89..1.11
    SP = b.math("ADD", S, paint)
    if idx == CLO:
        col = b.ramp(SP, [(0.0, (6, 6, 16)), (0.22, (14, 15, 36)), (0.42, (25, 28, 60)), (0.62, (40, 44, 84)),
                          (0.82, (62, 68, 112)), (1.0, (96, 102, 148))])
        col = b.mix(1.0, col, jit, "MULTIPLY")
        col = b.mix(b.math("MULTIPLY", rim, 0.25), col, (26, 30, 78), "ADD")
        col = b.mix(b.math("MULTIPLY", edge_up, 0.5), col, (172, 168, 196))
        sole = b.math("SUBTRACT", 1.0, b.smoothstep(b.pos_z(), 0.05, 0.085))      # black lacquered tabi sole
        col = b.mix(b.math("MULTIPLY", sole, 0.95), col, (10, 10, 18))
    elif idx == WRP:
        col = b.ramp(SP, [(0.0, (12, 13, 24)), (0.25, (30, 34, 54)), (0.5, (58, 64, 88)), (0.75, (92, 98, 124)),
                          (1.0, (136, 142, 166))])
        col = b.mix(1.0, col, jit, "MULTIPLY")
        col = b.mix(b.math("MULTIPLY", edge_up, 0.55), col, (206, 208, 226))
    elif idx == CRM:
        col = b.ramp(SP, [(0.0, (40, 4, 16)), (0.3, (96, 12, 30)), (0.6, (168, 26, 42)), (0.85, (214, 58, 58)),
                          (1.0, (240, 110, 90))])
        col = b.mix(1.0, col, jit, "MULTIPLY")
        col = b.mix(b.math("MULTIPLY", edge_up, 0.5), col, (250, 150, 128))
    elif idx == STL:
        col = b.ramp(b.math("ADD", S, b.math("MULTIPLY", paint, 0.7)),
                     [(0.0, (8, 10, 18)), (0.3, (26, 30, 44)), (0.55, (52, 60, 80)), (0.8, (92, 104, 128)),
                      (1.0, (150, 166, 192))])
        col = b.mix(b.math("MULTIPLY", glint, 0.5), col, (196, 210, 232), "ADD")
        col = b.mix(b.math("MULTIPLY", edge_up, 0.85), col, (214, 224, 240))
    elif idx == LTH:
        col = b.ramp(SP, [(0.0, (3, 3, 8)), (0.35, (10, 10, 20)), (0.6, (22, 24, 42)), (0.85, (40, 44, 70)),
                          (1.0, (64, 70, 104))])
        col = b.mix(b.math("MULTIPLY", glint, 0.55), col, (120, 132, 190), "ADD")
        col = b.mix(b.math("MULTIPLY", rim, 0.3), col, (14, 18, 40), "ADD")
        col = b.mix(b.math("MULTIPLY", edge_up, 0.6), col, (128, 138, 178))
    else:
        col = b.ramp(S, [(0.0, (5, 5, 12)), (1.0, (26, 28, 48))])
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
    report = {"set": SET, "rarity": "Rare", "blender_version": bpy.app.version_string,
              "authoring": "final Roblox stud size; import at 1:1, do not scale", "pieces": {}}
    install = {"set": SET, "rarity": "Rare", "helmet": "hood", "glow_color_srgb": None,
               "textured_material": "SmoothPlastic (colour comes from TextureID)",
               "axes": "offset/size in Studio part-local axes (x = Blender -x, y = Blender z, z = Blender y)",
               "parts": {}, "embers": []}
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
    report["textures"] = {g: f"textures/{SET}-{g}.png ({BAKE_SIZE}x{BAKE_SIZE})" for g in sorted(set(map(atlas_of, objs)))}
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
shoot("close-helm", (3.2, -7.6, 5.4), target=(0, 0, 4.72), lens=110)
if DBG:
    dd = ROOT / "previews" / "_dbg"
    for nm, loc, tg, ln in (("dbg-hips", (-3.4, -8.2, 3.0), (0.2, 0, 2.2), 105),
                            ("dbg-boots", (3.6, -7.4, 1.6), (0, 0, 0.9), 100),
                            ("dbg-back-helm", (-3.0, 7.6, 5.4), (0, 0, 4.6), 105),
                            ("dbg-arm", (7.0, -5.5, 3.6), (1.5, 0, 3.0), 105)):
        shoot(nm, loc, target=tg, lens=ln, path=dd / f"{nm}.png")

# ---------------------------------------------------------------------------
# Pose check: rotate the proxy's part groups (body + armour) about their rig joints through the default
# R15 walk/run/jump extremes and count interpenetrating triangles (numbers only, no pose renders).
# ---------------------------------------------------------------------------
CHILDREN = {}
for child, (parent, att) in JOINT.items():
    CHILDREN.setdefault(parent, []).append(child)
ARMOR_BY_PART = {}
for o in armor_objs:
    ARMOR_BY_PART.setdefault(o["body_part"], []).append(o)
REST_MW = {o.name: o.matrix_world.copy() for o in list(PROXY.values()) + armor_objs}


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
        arm = ARMOR_BY_PART.get(part, [])
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


def own_body_report():
    """Armour triangles poking into the body part they are welded to (fit/clearance sanity)."""
    out = {}
    for part, objs in ARMOR_BY_PART.items():
        if part in PROXY:
            n = sum(len(world_bvh(o).overlap(world_bvh(PROXY[part]))) for o in objs)
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
    own = own_body_report()
    log("own-part intersections (idle)", own)
    (ROOT / "pose-check.json").write_text(json.dumps(
        {"method": "part groups rotated about their rig joints (Blender); counts are intersecting triangle pairs; "
                   "'armour x body' is one part's armour against another part's body, 'armour x armour' is armour on "
                   "different parts",
         "poses_deg": {"walk": "arms +-35, elbows 20, legs +-35, back knee 35",
                       "run": "arms +-60, elbows 45, legs 55/60, back knee 85",
                       "jump": "arms raised 150 forward + 12 out, knees 15-30",
                       "fall": "arms raised 75 out to the sides"},
         "totals": {k: sum(v.values()) for k, v in clip.items()},
         "armour_into_own_body_part_idle": own,
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
if not VIEWS or "sheet" in VIEWS:
    tall = 1.2
    compose("sheet", [
        [(PV / f"{SET}-front.png", tall), (PV / f"{SET}-threeq.png", tall), (PV / f"{SET}-side.png", tall),
         (PV / f"{SET}-back.png", tall)],
        [(PV / f"{SET}-close-helm.png", tall)],
    ], 460)

bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / f"{SET}.blend"))
log("DONE")
