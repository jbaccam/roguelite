"""Samurai armor set (Epic): an o-yoroi warlord in lacquered lamellar armour.

Run (background Blender 5.2, never the user's open scene):
  blender -b --factory-startup --threads 2 --python build_samurai.py
Env:
  QUICK=1        flat preview colours only: no bake, no exports (fast shape passes)
  VIEWS=a,b      render only these preview names
  NOPOSE=1       skip the numeric pose check
  PREVIEW_DIR=.. write previews somewhere else (quick passes go to a scratch folder)

Design: deep crimson lacquer kozane rows with painted gold cord lacing and raised gold knots,
black lacquer trims and top plates, brown-shaded gold, a dark navy cloth / mail undersuit.
Kabuto with a ribbed dome, a flared four-lame shikoro whose front edges turn back (fukigaeshi),
a chunky gold crescent maedate on a gold boss, and a fierce crimson menpo with a moustache ridge.
Every piece is modelled at final stud size around the normalized R15 body (../r15-proxy/*.obj).
One rigid mesh per R15 part it covers. Self-contained: the pipeline parts are copied from
build_dragon_scale.py (charts, shell, horn, loft, rivet, gem, finish, bake, export, previews).

Blender axes: +z up, -y = the character's front, +x = the character's LEFT.
Studio axes = (-x, z, y) of Blender.
"""
import bpy, bmesh, math, json, os, random, time
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from pathlib import Path

T0 = time.time()
ROOT = Path(__file__).resolve().parent
KIT = ROOT.parent
SET = "samurai"
PREFIX = "Samurai"
QUICK = os.environ.get("QUICK") == "1"
VIEWS = set(os.environ["VIEWS"].split(",")) if os.environ.get("VIEWS") else None
NOPOSE = os.environ.get("NOPOSE") == "1"
PV = Path(os.environ.get("PREVIEW_DIR", str(ROOT / "previews")))
BAKE_SIZE = 1024          # Roblox caps textures at 1024; baked directly at final size
for d in ("exports/fbx", "exports/glb", "textures"):
    (ROOT / d).mkdir(parents=True, exist_ok=True)
PV.mkdir(parents=True, exist_ok=True)
RNG = random.Random(7)


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
JOINT = {}


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
HRP_HEIGHT = 3.0


def part_pos(name):
    return s2b(REST[name]) + Vector((0, 0, HRP_HEIGHT))


def joint_world(child):
    parent, att = JOINT[child]
    return part_pos(parent) + s2b(BODY[parent]["atts"][att])


# ---------------------------------------------------------------------------
# Materials (bake inputs). Index order is shared by every component.
# ---------------------------------------------------------------------------
MAT_NAMES = ["Lacquer", "BlackLacquer", "Gold", "Cloth", "Mail", "Dark"]
LAC, BLK, GLD, CLO, MAIL, DRK = range(6)
PREVIEW_RGB = {LAC: (150, 24, 36), BLK: (30, 30, 40), GLD: (214, 160, 66), CLO: (34, 42, 84),
               MAIL: (48, 52, 74), DRK: (14, 12, 18)}


def lin(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgba(c, a=1.0):
    return (lin(c[0]), lin(c[1]), lin(c[2]), a)


# ---------------------------------------------------------------------------
# Mesh components (copied from the Dragon Scale pipeline). "Detail" colour attribute per loop:
#   R = row fraction (0 top -> 1 free/bottom edge), or 0.5 + z/8 for metric mail
#   G = 0.5 + across/8 (metric: the painted lacing and the mail rings repeat in studs)
#   B = per-element random, A = zone (0.5 = laced kozane plate)
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
            loop[self.lay] = d if d is not None else self.vd.get(loop.vert, (0.0, 0.0, 0.0, 0.0))
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


CL = 0.028          # gap between the body and the inside of an armour layer
SUIT_CL = 0.012     # the undersuit hugs the body under the plates
UP = Vector((0, 0, 1))


def torso_chart(side, hx=1.0, hy=0.5, hz=0.8, rc=0.12, clear=CL):
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


def limb_chart(hx=0.5, hy=0.5, r=0.13, clear=CL):
    """Around a limb's box section, front -> outer (+x) -> back, skipping the inner face."""
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


def profile_chart(poly, clear=CL):
    """Chart over a 2D profile in the x-z plane, extruded along y. u = arc length, v = y."""
    pts = [Vector(p) for p in poly]
    acc = [0.0]
    for k in range(1, len(pts)):
        acc.append(acc[-1] + (pts[k] - pts[k - 1]).length)
    nrm = []
    for k in range(len(pts)):
        t = pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]
        nrm.append(Vector((-t.y, t.x)).normalized())

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


def plane_x_chart(x0):
    """The +x side face of a box (u = y, v = z)."""
    def f(u, v):
        return Vector((x0, u, v)), Vector((1.0, 0.0, 0.0))
    return f


def lt_chart(side, clear=CL):
    def f(u, v):
        return Vector((u, side * (0.5 + clear), v)), Vector((0, side, 0))
    return f


def shell(c, chart, G, thick, *, lift=None, wrap=False, mat=BLK, mat_fn=None, rim_mat=None,
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
        for f in fo + fi + fr:
            if f is not None:
                f.normal_flip()
    return outer


def bezier(p0, p1, p2, p3, t):
    a = 1 - t
    return p0 * a ** 3 + p1 * 3 * a * a * t + p2 * 3 * a * t * t + p3 * t ** 3


def curve_pts(p0, p1, p2, p3, n):
    return [bezier(p0, p1, p2, p3, k / (n - 1)) for k in range(n)]


def horn(c, pts, r0, *, sides=7, taper=1.0, flat=1.0, rings=0.0, mat=GLD, up=None, rnd=None, r_tip=0.0,
         cap=True):
    """Tapered faceted tube along a curve (cords, crest, moustache, tassels)."""
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
            ring.append(c.v(q, (t, s / sides, rnd, 0.0)))
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
    f0 = faces[0]
    if f0 is not None:
        radial = (f0.calc_center_median() - pts[0])
        if f0.normal.dot(radial) < 0:
            for f in faces:
                if f is not None:
                    f.normal_flip()
    return faces


def loft(c, rings, mat, cap0=True, cap1=True, closed=True, det=None):
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
    return faces, V


def gem(c, center, nrm, up, w, h, depth, sides=8, mat=GLD):
    """Faceted cabochon: gold bosses, rosettes and the mon badges."""
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


def bump(x, y, cx, cy, rx, ry):
    d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
    return max(0.0, 1.0 - d) ** 1.5


def grid(us, vs):
    return [[(u, v) for u in us] for v in vs]


def limb_cols(ch):
    st = ch.stations
    arc0 = [st["outer0"] - (st["outer0"] - st["corner_fo"]) * 2 + (st["outer0"] - st["corner_fo"]) * 2 * k / 3 for k in range(4)]
    arc1 = [st["outer1"] + (st["corner_ob"] - st["outer1"]) * 2 * k / 3 for k in range(4)]
    return [0.012, st["front_mid"] * 0.5, st["front_mid"]] + arc0 + [st["outer_mid"]] + arc1 + \
        [st["back_mid"], (st["back_mid"] + st["back_in"]) / 2, st["back_in"] - 0.012]


# ---------------------------------------------------------------------------
# Samurai building blocks
# ---------------------------------------------------------------------------
def undersuit(comps, chart, us, vs, mat=CLO, metric=False, rnd=0.5):
    """Dark navy cloth (or mail) layer hugging the body; it shows in every gap between plates."""
    c = Comp(bevel=0.0, shade="smooth")
    det = (lambda j, i, u, v: (0.5 + v / 8.0, 0.5 + u / 8.0, rnd, 0.0)) if metric else None
    shell(c, chart, grid(us, vs), 0.004, mat=mat, rnd=rnd, det_fn=det)
    comps.append(c)


def knot(kc, chart, u, v, off, r=0.032):
    """Raised gold cord knot: a small diamond pyramid on the plate surface."""
    P, N = chart(u, v)
    rivet(kc, P + N * (off - 0.003), N, r=r, h=r * 0.78, sides=4, mat=GLD)


def kozane(comps, chart, top, bot, ua, ub, *, nu=12, lift=(0.0, 0.07), bulge=None, thick=0.05, lip=0.018,
           mat=LAC, segs=2, tv=(0.0, 0.5, 0.84, 0.92, 1.0), laced=True, gold_hem=False, knots=(),
           kc=None, knot_r=0.032, flush=True, rnd=None, bevel=0.012):
    """One lamellar row: a bevelled plate strip whose free edge lifts over the next row, with a
    rolled lip. Lacing is painted by the bake from the metric G coordinate."""
    c = Comp(bevel=bevel, segs=segs, angle=34)
    rnd = RNG.random() if rnd is None else rnd
    ua_f = ua if callable(ua) else (lambda t, a=ua: a)
    ub_f = ub if callable(ub) else (lambda t, b=ub: b)
    G = [[(lerp(ua_f(t), ub_f(t), i / nu), lerp(top, bot, t)) for i in range(nu + 1)] for t in tv]
    nl = len(tv)

    def th(j, i, u, v):
        return thick + (lip if j >= nl - 3 else 0.0) - (0.008 if j == nl - 1 else 0.0)

    def lf(j, i, u, v):
        return lerp(lift[0], lift[1], tv[j]) + (bulge(u, v) if bulge else 0.0)
    A = 0.5 if (laced and mat == LAC) else 0.0
    shell(c, chart, G, th, lift=lf, mat_fn=(lambda j, i: GLD if (gold_hem and j >= nl - 3) else mat),
          rim_mat=GLD if gold_hem else mat, flush=flush,
          det_fn=lambda j, i, u, v: (tv[j], 0.5 + u / 8.0, rnd, A))
    comps.append(c)
    for ku, kt in knots:
        v = lerp(top, bot, kt)
        off = lerp(lift[0], lift[1], kt) + (bulge(ku, v) if bulge else 0.0) + thick
        knot(kc, chart, ku, v, off, knot_r)
    return c


def tile(comps, chart, u0, u1, top, bot, lift, *, nu=3, mat=LAC, thick=0.045, lip=0.014, segs=1):
    """A small lacquered plate (haidate tiles)."""
    c = Comp(bevel=0.011, segs=segs, angle=34)
    tv = [0.0, 0.7, 1.0]
    G = [[(lerp(u0, u1, i / nu), lerp(top, bot, t)) for i in range(nu + 1)] for t in tv]
    shell(c, chart, G, lambda j, i, u, v: thick + (lip if j == 2 else 0.0),
          lift=lambda j, i, u, v: lerp(lift[0], lift[1], tv[j]), mat=mat, rim_mat=mat, flush=True)
    comps.append(c)


def bow(c, P, N, up, s=1.0, tails=0.45, r=0.028, root=0.06, mat=GLD, lite=False):
    """Gold cord bow (agemaki style): two loops, two tails with tassels, a knot sunk into the plate."""
    N = N.normalized()
    up = (up - N * up.dot(N)).normalized()
    X = up.cross(N).normalized()

    def W(x, z, n=0.0):
        return P + X * (x * s) + up * (z * s) + N * (n * s)
    nl, nt, sd = (4, 5, 5) if lite else (6, 7, 6)
    for sg in (1, -1):
        loop = (curve_pts(W(0, 0), W(sg * 0.10, 0.15), W(sg * 0.30, 0.13), W(sg * 0.27, -0.01), nl) +
                curve_pts(W(sg * 0.27, -0.01), W(sg * 0.25, -0.11), W(sg * 0.10, -0.07), W(0, 0), nl)[1:])
        horn(c, loop, r * s, sides=sd, taper=0.0, r_tip=r * s, mat=mat, up=N, cap=False)
        tail = curve_pts(W(0, -0.02), W(sg * 0.05, -0.14, 0.01), W(sg * 0.10, -tails * 0.62, 0.02),
                         W(sg * 0.15, -tails, 0.03), nt)
        horn(c, tail, r * 1.1 * s, sides=sd, taper=0.7, r_tip=r * 0.8 * s, mat=mat, up=N)
        e = tail[-1]
        d = (tail[-1] - tail[-2]).normalized()
        horn(c, [e - d * 0.01 * s, e + d * 0.05 * s, e + d * 0.12 * s], 0.024 * s, sides=sd, taper=1.0,
             r_tip=0.055 * s, mat=mat, up=N)
    horn(c, [P - N * root, P + N * 0.02 * s, P + N * 0.055 * s], 0.065 * s, sides=8, taper=0.0, r_tip=0.05 * s,
         mat=mat, up=up)


# ----- UpperTorso: the do ----------------------------------------------------
DO_ROWS = [(0.42, 0.10, 0.985, 0.975), (0.15, -0.19, 0.975, 0.95), (-0.14, -0.48, 0.95, 0.92),
           (-0.43, -0.79, 0.92, 0.89)]          # (top v, bottom v, half width top, half width bottom)
DO_LIFT = (0.0, 0.075)


def do_bulge(u, v):
    """Rounded barrel front: rows stand further off the flat torso at the centre."""
    return 0.05 * (1.0 - min(1.0, abs(u)) ** 2)


def build_upper_torso():
    comps = []
    kc = Comp(shade="smooth")
    gc = Comp(shade="flat")
    for side in (-1, 1):
        undersuit(comps, torso_chart(side, clear=SUIT_CL), [-0.99, -0.6, 0.0, 0.6, 0.99],
                  [-0.8, -0.3, 0.2, 0.6, 0.9, 1.0])
        for sx in (-1, 1):
            undersuit(comps, torso_chart(side, clear=SUIT_CL), [sx * 0.46, sx * 0.72, sx * 0.99], [0.95, 1.1, 1.267])
        ch = torso_chart(side)
        segs = 2 if side < 0 else 1
        for k, (top, bot, wt, wb) in enumerate(DO_ROWS):
            kozane(comps, ch, top, bot, (lambda t, a=wt, b=wb: -lerp(a, b, t)), (lambda t, a=wt, b=wb: lerp(a, b, t)),
                   nu=8, lift=DO_LIFT, bulge=do_bulge, segs=segs, gold_hem=(k == len(DO_ROWS) - 1), kc=kc,
                   knots=((-0.62, 0.5), (0.62, 0.5)))
        # muna-ita: black top plate with raised gold bands, riding over the first row
        mc = Comp(bevel=0.012, segs=segs, angle=34)
        vs = [0.36, 0.39, 0.42, 0.59, 0.62, 0.66]
        us = [-0.66 + 1.32 * i / 10 for i in range(11)]

        def mlift(j, i, u, v):
            return do_bulge(u, v) + lerp(0.065, 0.02, (v - 0.36) / 0.30)
        shell(mc, ch, grid(us, vs), lambda j, i, u, v: 0.055 + (0.016 if j in (0, 1, 4, 5) else 0.0), lift=mlift,
              mat_fn=lambda j, i: GLD if j in (0, 4) else BLK, rim_mat=GLD, flush=True)
        comps.append(mc)
        for x in (-0.40, 0.40):
            P, N = ch(x, 0.505)
            gem(gc, P + N * (mlift(0, 0, x, 0.505) + 0.05), N, UP, 0.10, 0.10, 0.035, sides=8, mat=GLD)
        # watagami: shoulder straps over the top, black with gold edges
        for sx in (-1, 1):
            sc_ = Comp(bevel=0.012, segs=1, angle=34)
            us = [sx * 0.67, sx * 0.70, sx * 0.93, sx * 0.96]
            vs = [0.33, 0.42, 0.52, 0.62, 0.70, 0.78, 0.86, 0.95, 1.1, 1.29]

            def slift(j, i, u, v):
                return (do_bulge(u, v) + 0.075) * smooth((0.64 - v) / 0.22)
            shell(sc_, ch, grid(us, vs), 0.05, lift=slift, mat_fn=lambda j, i: BLK if j >= 0 and i == 1 else GLD,
                  rim_mat=GLD, flush=True)
            comps.append(sc_)
            knot(kc, ch, sx * 0.815, 0.46, slift(0, 0, sx * 0.815, 0.46) + 0.05, 0.03)
        if side > 0:            # agemaki bow on the back
            P, N = ch(0.0, 0.20)
            bc = Comp(shade="smooth")
            bow(bc, P + N * 0.23, N, UP, s=1.0, tails=0.50, root=0.10)
            comps.append(bc)
    comps += [kc, gc]
    return comps


# ----- LowerTorso: belt and kusazuri --------------------------------------------
KUSA = [(-0.13, -0.33, 0.92, 0.94, 0.0, 0.07), (-0.28, -0.47, 0.94, 0.96, 0.02, 0.095),
        (-0.42, -0.60, 0.96, 0.985, 0.045, 0.12)]
SIDE_KUSA = [(-0.22, -0.38, 0.40, 0.42, 0.03, 0.085), (-0.34, -0.51, 0.42, 0.44, 0.035, 0.105),
             (-0.47, -0.64, 0.44, 0.46, 0.055, 0.12)]


def build_lower_torso():
    comps = []
    kc = Comp(shade="smooth")
    for side in (-1, 1):
        undersuit(comps, lt_chart(side, SUIT_CL), [-0.99, 0, 0.99], [-0.2, 0.0, 0.2])
        ch = lt_chart(side)
        c = Comp(bevel=0.012, segs=2 if side < 0 else 1, angle=32)
        us = [-0.985 + 1.97 * i / 8 for i in range(9)]
        vs = [-0.165, -0.15, -0.125, 0.125, 0.15, 0.165]
        shell(c, ch, grid(us, vs), lambda j, i, u, v: 0.062 + (0.02 if j in (0, 1, 4, 5) else 0.0) -
              (0.008 if j in (0, 5) else 0.0), mat_fn=lambda j, i: GLD if j in (0, 4) else BLK, rim_mat=GLD, flush=True)
        comps.append(c)
        for k, (top, bot, wt, wb, l0, l1) in enumerate(KUSA):
            kozane(comps, ch, top, bot, (lambda t, a=wt, b=wb: -lerp(a, b, t)), (lambda t, a=wt, b=wb: lerp(a, b, t)),
                   nu=8, lift=(l0, l1), segs=2 if side < 0 else 1, gold_hem=(k == 2), flush=(k < 2),
                   tv=(0.0, 0.84, 0.92, 1.0))
    # side panels below the hands (left, mirrored for the right)
    half = []
    hk = Comp(shade="smooth")
    sch = plane_x_chart(1.0 + CL)
    for k, (top, bot, wt, wb, l0, l1) in enumerate(SIDE_KUSA):
        kozane(half, sch, top, bot, (lambda t, a=wt, b=wb: -lerp(a, b, t)), (lambda t, a=wt, b=wb: lerp(a, b, t)),
               nu=4, lift=(l0, l1), segs=1, gold_hem=(k == 2), flush=(k < 2), tv=(0.0, 0.84, 0.92, 1.0))
    half.append(hk)
    comps += half + [h.mirrored() for h in half]
    # front belt knot
    P, N = lt_chart(-1)(0.0, 0.0)
    bc = Comp(shade="smooth")
    bow(bc, P + N * 0.11, N, UP, s=0.5, tails=0.30, root=0.09, lite=True)
    comps += [bc, kc]
    return comps


# ----- Head: kabuto and menpo ------------------------------------------------------
def head_profile(s, clear=0.0):
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


DOME_R, DOME_ZB, DOME_H, DOME_N = 0.74, 0.06, 0.62, 2.6


def dome_raw(th, ph):
    """Superellipse bowl (hachi): th around (0 = front), ph from the rim (0) toward the crown."""
    e = 2.0 / DOME_N
    c, s = math.cos(ph), math.sin(ph)
    r = DOME_R * c ** e
    z = DOME_ZB + DOME_H * s ** e
    nr = (r / DOME_R) ** (DOME_N - 1) / DOME_R
    nz = ((z - DOME_ZB) / DOME_H) ** (DOME_N - 1) / DOME_H
    return (Vector((r * math.sin(th), -r * math.cos(th), z)),
            Vector((nr * math.sin(th), -nr * math.cos(th), nz)).normalized())


def cone_chart(zt, zb, rt, rb):
    """A flared shikoro lame: u = angle around the head, v = z."""
    h = zt - zb
    nn = Vector((h, rb - rt)).normalized()

    def f(u, v):
        r = lerp(rt, rb, (zt - v) / h)
        return (Vector((r * math.sin(u), -r * math.cos(u), v)),
                Vector((nn.x * math.sin(u), -nn.x * math.cos(u), nn.y)))
    return f


SHK_F, SHK_H, SHK_DZ = 0.13, 0.165, 0.125      # flare, lame height, step between lames
MEN = math.radians(64)                           # menpo half angle


def men_zt(th):
    """Top edge: a peak over the nose bridge falling outward, so the eye slits slant like a scowl."""
    a = abs(th) / MEN
    return 0.06 - 0.16 * clamp(a / 0.5) + 0.07 * smooth((a - 0.5) / 0.5)


def mouth_warp(th, t):
    """Pull the mouth corners down into a snarl."""
    return -0.05 * min(1.0, (th / 0.33) ** 2) * max(0.0, 1.0 - ((t - 0.37) / 0.2) ** 2)


def men_zb(th):
    return -0.68 + 0.15 * smooth(abs(th) / MEN)


def men_th(th, z):
    """Sculpted menpo height: nose ridge, cheekbones, a jutting chin, a recessed snarl."""
    zc = -0.435 - 0.05 * min(1.0, (th / 0.33) ** 2)
    return (0.035 + 0.095 * bump(th, z, 0.0, -0.20, 0.24, 0.26)
            + 0.035 * bump(abs(th), z, 0.62, -0.20, 0.34, 0.17)
            + 0.045 * bump(th, z, 0.0, -0.60, 0.42, 0.12)
            - 0.03 * bump(th, z, 0.0, zc, 0.36, 0.05))


def build_head():
    comps = []
    kc = Comp(shade="smooth")
    gc = Comp(shade="flat")
    # hood under the helmet (navy), dark in the eye band so the face never shows
    hc = head_chart(clear=SUIT_CL)
    nh = 16
    ths = [-math.pi + 2 * math.pi * i / nh for i in range(nh)]
    ss = [0.0, 0.2, 0.40, 0.52, 0.66, 0.78, 0.95, 1.12, 1.30, HEAD_S_MAX - 0.05]
    hood = Comp(shade="smooth")
    shell(hood, hc, [[(t, s) for t in ths] for s in ss], 0.004, wrap=True,
          mat_fn=lambda j, i: DRK if (j in (3, 4) and abs(ths[i] + math.pi / nh) < math.radians(72)) else CLO)
    comps.append(hood)
    # hachi: ribbed black dome over a raised gold band; gold tehen rosette at the crown
    ncol = 32
    dth_ = [2 * math.pi * i / ncol for i in range(ncol)]
    phs = [math.radians(a) for a in (0, 4, 7, 14, 24, 36, 48, 60, 70, 78)]

    def dthick(j, i, u, v):
        if j <= 1:
            return 0.078
        fade = 1.0 - smooth((v - math.radians(56)) / math.radians(20))
        return 0.05 + (0.034 * fade if i % 2 == 0 else 0.0)
    dome = Comp(bevel=0.011, segs=2, angle=40, facet=30)
    shell(dome, dome_raw, [[(t, p) for t in dth_] for p in phs], dthick, wrap=True,
          mat_fn=lambda j, i: GLD if j == 0 else BLK, rim_mat=GLD, flush=True)
    comps.append(dome)
    e = 2.0 / DOME_N
    top_r = DOME_R * math.cos(math.radians(78)) ** e
    top_z = DOME_ZB + DOME_H * math.sin(math.radians(78)) ** e
    gem(gc, Vector((0, 0, top_z + 0.03)), UP, Vector((0, -1, 0)), 2 * top_r + 0.10, 2 * top_r + 0.10, 0.09,
        sides=12, mat=GLD)
    # mabizashi: the visor over the brow, gold lip
    def visor_chart(th, t):
        r = lerp(0.745, 0.98, t)
        z = lerp(0.115, 0.0, t)
        nn = Vector((0.115, 0.235)).normalized()
        return Vector((r * math.sin(th), -r * math.cos(th), z)), Vector((nn.x * math.sin(th), -nn.x * math.cos(th), nn.y))
    vis = Comp(bevel=0.01, segs=1, angle=34)
    vt = [0.0, 0.5, 0.82, 1.0]
    vth = [math.radians(-62 + 124 * i / 10) for i in range(11)]
    shell(vis, visor_chart, [[(t, tv) for t in vth] for tv in vt], lambda j, i, u, v: 0.042 + (0.016 if j >= 2 else 0.0),
          mat_fn=lambda j, i: GLD if j == 2 else BLK, rim_mat=GLD, flush=False)
    comps.append(vis)
    # shikoro: four flared crimson lames around the back, each tucked inside the one above
    step = SHK_F * SHK_DZ / SHK_H - 0.05
    th_a, th_b = math.radians(68), math.radians(292)
    for k in range(4):
        zt = 0.08 - SHK_DZ * k
        rt = 0.765 + step * k
        kozane(comps, cone_chart(zt, zt - SHK_H, rt, rt + SHK_F), zt, zt - SHK_H, th_a, th_b, nu=16, lift=(0.0, 0.0),
               segs=2, gold_hem=(k == 3), flush=(k < 3), tv=(0.0, 0.84, 0.92, 1.0), kc=kc,
               knots=[(math.radians(a), 0.45) for a in (122, 180, 238)])
    # fukigaeshi: the front ends of the shikoro turned back into flaps with a gold mon (left, mirrored)
    beta = math.radians(12)
    U = Vector((math.cos(beta), math.sin(beta), 0.0))
    Nf = Vector((math.sin(beta), -math.cos(beta), 0.0))
    H = Vector((0.72, -0.36, 0.0))
    FW = 0.34

    def fk_chart(u, v):
        f = u / FW
        return H + U * u + Vector((0, 0, v)) - Nf * (0.05 * f * f), (Nf + U * (0.33 * f)).normalized()
    half = []
    fk = Comp(bevel=0.011, segs=1, angle=34)
    nu = 5
    tvs = [0.0, 0.12, 0.88, 1.0]

    def ftop(u):
        return 0.15 - 0.05 * (u / FW) ** 2

    def fbot(u):
        return -0.22 + 0.07 * (u / FW) ** 2
    G = [[(FW * i / nu, lerp(fbot(FW * i / nu), ftop(FW * i / nu), t)) for i in range(nu + 1)] for t in tvs]
    shell(fk, fk_chart, G, 0.055, mat_fn=lambda j, i: GLD if (j in (0, 2) or i == nu - 1) else BLK, rim_mat=GLD,
          flush=False)
    half.append(fk)
    mon = Comp(shade="flat")
    P, N = fk_chart(0.14, -0.03)
    gem(mon, P + N * 0.064, N, UP, 0.12, 0.12, 0.04, sides=8, mat=GLD)
    half.append(mon)
    comps += half + [h.mirrored() for h in half]
    # menpo: fierce crimson face mask, dark snarl, black moustache ridge
    mc = head_chart(clear=CL + 0.01)
    nth = 18
    mths = [-MEN + 2 * MEN * i / nth for i in range(nth + 1)]
    mtv = [0.0, 0.08, 0.2, 0.30, 0.345, 0.40, 0.52, 0.66, 0.82, 1.0]
    G = [[(t, lerp(men_zb(t), men_zt(t), tv) + mouth_warp(t, tv) + 0.6) for t in mths] for tv in mtv]
    menpo = Comp(bevel=0.012, segs=2, angle=36, facet=28)
    shell(menpo, mc, G, lambda j, i, u, v: men_th(u, v - 0.6),
          mat_fn=lambda j, i: DRK if (j == 4 and abs((mths[i] + mths[i + 1]) / 2) < 0.33) else LAC, rim_mat=BLK,
          flush=True, det_fn=lambda j, i, u, v: (mtv[j], 0.5, 0.35, 0.0))
    comps.append(menpo)
    mo = Comp(shade="smooth")
    for sg in (1, -1):
        path = [(0.0, -0.365), (0.12, -0.37), (0.24, -0.39), (0.34, -0.43), (0.41, -0.49), (0.45, -0.56)]
        pts = []
        for a, z in path:
            P, N = mc(sg * a, z + 0.6)
            pts.append(P + N * (men_th(sg * a, z) + 0.012))
        horn(mo, pts, 0.045, sides=6, flat=0.55, taper=0.8, r_tip=0.012, mat=BLK)
    comps.append(mo)
    # maedate: chunky gold crescent rising from a gold boss on the brow
    cr = Comp(bevel=0.008, segs=2, angle=40)
    for sg in (1, -1):
        pts = curve_pts(Vector((0.0, -0.86, 0.22)), Vector((sg * 0.26, -0.90, 0.24)), Vector((sg * 0.60, -0.86, 0.46)),
                        Vector((sg * 0.74, -0.62, 1.00)), 11)
        horn(cr, pts, 0.11, sides=8, flat=0.42, taper=0.9, r_tip=0.02, mat=GLD, up=UP)
    comps.append(cr)
    gem(gc, Vector((0, -0.80, 0.22)), Vector((0, -1, 0.22)).normalized(), UP, 0.30, 0.26, 0.13, sides=8, mat=GLD)
    comps += [kc, gc]
    return comps


# ----- Sode (left upper arm; outer = +x) --------------------------------------------
SODE = []
_a = 0.04
for _top, _bot in ((0.36, 0.12), (0.16, -0.10), (-0.06, -0.32), (-0.28, -0.52)):
    SODE.append((_top, _bot, _a, _a + 0.10))
    _a += 0.034
SODE_W = [(0.66, 0.68), (0.68, 0.70), (0.70, 0.72), (0.72, 0.74)]


def build_upper_arm():
    comps = []
    su = limb_chart(r=0.1, clear=SUIT_CL)
    undersuit(comps, su, limb_cols(su), [-0.58, -0.2, 0.2, 0.52], mat=MAIL, metric=True)
    top = Comp(shade="smooth")
    tc_ = [Vector((x, y, 0.584 + SUIT_CL)) for x, y in ((-0.49, -0.49), (0.49, -0.49), (0.49, 0.49), (-0.49, 0.49))]
    top.f([top.v(p, (0, 0, 0.5, 0)) for p in tc_], MAIL)
    comps.append(top)
    kc = Comp(shade="smooth")
    # kanmuri-ita: black top plate bent over the shoulder, gold edges, gold rosette
    pc = profile_chart([(-0.28, 0.584), (0.26, 0.584), (0.40, 0.56), (0.48, 0.49), (0.5, 0.40), (0.5, 0.26)])
    us = [0.0, 0.05, 0.25, 0.50, 0.66, 0.80, 0.92, pc.length - 0.035, pc.length]
    vs = [-0.70 + 1.40 * i / 8 for i in range(9)]
    nj = len(us)

    def klift(j, i, u, v):
        return 0.12 * smooth((u - 0.50) / 0.40)

    def kth(j, i, u, v):
        return 0.062 + (0.015 if (j <= 1 or j >= nj - 2 or i in (0, 8)) else 0.0)
    kan = Comp(bevel=0.012, segs=2, angle=32)
    shell(kan, pc, [[(u, v) for v in vs] for u in us], kth, lift=klift,
          mat_fn=lambda j, i: GLD if (j == 0 or j >= nj - 2 or i in (0, 7)) else BLK, rim_mat=GLD, flush=True)
    comps.append(kan)
    gc = Comp(shade="flat")
    P, N = pc(0.72, 0.0)
    gem(gc, P + N * (klift(0, 0, 0.72, 0) + 0.07), N, Vector((0, -1, 0)), 0.15, 0.15, 0.05, sides=8, mat=GLD)
    comps.append(gc)
    # a black kote plate on the front of the upper arm, above the elbow
    lc = limb_chart(r=0.1)
    fp = Comp(bevel=0.011, segs=1, angle=32)
    us = [0.14 + 0.64 * i / 4 for i in range(5)]
    shell(fp, lc, grid(us, [-0.24, -0.215, 0.165, 0.19]), lambda j, i, u, v: 0.05 + 0.016 * (1 - abs(2 * i / 4 - 1)),
          mat_fn=lambda j, i: GLD if j in (0, 2) else BLK, rim_mat=GLD, flush=True)
    comps.append(fp)
    # four crimson laced lames hanging on the outer side, flaring out, gold hem on the last
    sch = plane_x_chart(0.5 + CL)
    for k, ((top_, bot, l0, l1), (wt, wb)) in enumerate(zip(SODE, SODE_W)):
        kozane(comps, sch, top_, bot, (lambda t, a=wt, b=wb: -lerp(a, b, t)), (lambda t, a=wt, b=wb: lerp(a, b, t)),
               nu=8, lift=(l0, l1), segs=2, gold_hem=(k == 3), flush=(k < 3), kc=kc, knots=((-0.36, 0.5), (0.36, 0.5)),
               tv=(0.0, 0.84, 0.92, 1.0))
    comps.append(kc)
    return comps


# ----- Kote (left lower arm) ----------------------------------------------------------
def build_lower_arm():
    comps = []
    su = limb_chart(r=0.1, clear=SUIT_CL + 0.006)
    undersuit(comps, su, limb_cols(su), [-0.52, -0.1, 0.3, 0.5], mat=MAIL, metric=True)
    lc = limb_chart(r=0.1)
    L = lc.stations
    kc = Comp(shade="smooth")
    # wrist cuff: black lacquer with raised gold bands, flaring at the wrist
    c = Comp(bevel=0.012, segs=2, angle=32)
    us = [0.025 + (L["total"] - 0.05) * i / 10 for i in range(11)]
    vs = [-0.49, -0.47, -0.44, -0.37, -0.345, -0.32]
    shell(c, lc, grid(us, vs), lambda j, i, u, v: 0.055 + (0.018 if j in (0, 1, 4, 5) else 0.0),
          lift=lambda j, i, u, v: 0.03 * (1 - (v + 0.49) / 0.17), mat_fn=lambda j, i: GLD if j in (0, 4) else BLK,
          rim_mat=GLD, flush=True)
    comps.append(c)
    # ikada: three small plates down the outer forearm with mail showing between them
    for zt, zb in ((0.30, 0.13), (0.09, -0.08), (-0.12, -0.29)):
        p = Comp(bevel=0.011, segs=1, angle=32)
        us = [L["outer0"] - 0.16 + (L["outer1"] - L["outer0"] + 0.32) * i / 6 for i in range(7)]
        shell(p, lc, grid(us, [zb, zb + 0.025, zt - 0.025, zt]),
              lambda j, i, u, v: 0.05 + 0.014 * (1 - abs(2 * i / 6 - 1)), mat_fn=lambda j, i: GLD if j in (0, 2) else BLK,
              rim_mat=GLD, flush=True)
        comps.append(p)
        knot(kc, lc, L["outer_mid"], (zt + zb) / 2, 0.064, 0.03)
    # tsutsu: one long black splint on the front of the forearm, below the elbow
    p = Comp(bevel=0.011, segs=1, angle=32)
    us = [0.14 + 0.64 * i / 4 for i in range(5)]
    shell(p, lc, grid(us, [-0.30, -0.275, 0.095, 0.12]), lambda j, i, u, v: 0.05 + 0.016 * (1 - abs(2 * i / 4 - 1)),
          mat_fn=lambda j, i: GLD if j in (0, 2) else BLK, rim_mat=GLD, flush=True)
    comps.append(p)
    comps.append(kc)
    return comps


# ----- Haidate (left upper leg) -----------------------------------------------------
HAI = [(0.10, -0.06, 0.0, 0.05), (-0.02, -0.18, 0.005, 0.07), (-0.14, -0.30, 0.025, 0.09)]


def build_upper_leg():
    comps = []
    su = limb_chart(r=0.1, clear=SUIT_CL)
    undersuit(comps, su, limb_cols(su), [-0.6, -0.2, 0.2, 0.6])
    lc = limb_chart(r=0.1)
    L = lc.stations
    kc = Comp(shade="smooth")
    ncol, gap, u0, u1 = 5, 0.03, 0.03, L["corner_ob"]
    w = (u1 - u0 - gap * (ncol - 1)) / ncol
    for r, (zt, zb, l0, l1) in enumerate(HAI):
        for k in range(ncol):
            a = u0 + k * (w + gap)
            tile(comps, lc, a, a + w, zt, zb, (l0, l1), nu=4 if k == 2 else 3)
            if r == 0:
                knot(kc, lc, a + w / 2, lerp(zt, zb, 0.3), lerp(l0, l1, 0.3) + 0.045, 0.026)
    comps.append(kc)
    return comps


# ----- Suneate (left lower leg) ------------------------------------------------------
def build_lower_leg_legs():
    comps = []
    su = limb_chart(r=0.1, clear=SUIT_CL + 0.006)
    undersuit(comps, su, limb_cols(su), [-0.40, -0.1, 0.25, 0.55], mat=MAIL, metric=True)
    lc = limb_chart(r=0.1)
    L = lc.stations
    kc = Comp(shade="smooth")
    # three vertical black splints over the mail, gold ends and a centre ridge
    for uc in (0.45, L["corner_fo"], L["outer_mid"]):
        c = Comp(bevel=0.012, segs=1, angle=32)
        us = [uc - 0.14 + 0.28 * i / 4 for i in range(5)]
        vs = [-0.36, -0.335, -0.30, 0.16, 0.195, 0.22]
        shell(c, lc, grid(us, vs), lambda j, i, u, v: 0.05 + (0.022 if i == 2 else 0.0) + (0.012 if j in (0, 1, 4, 5) else 0.0),
              mat_fn=lambda j, i: GLD if j in (0, 4) else BLK, rim_mat=GLD, flush=True)
        comps.append(c)
    # tateage knee cop: crimson, rising over the thigh tiles' lower edge, gold hem
    kcp = Comp(bevel=0.013, segs=2, angle=32)
    zs = [0.20, 0.23, 0.27, 0.36, 0.43, 0.46]
    hws = [0.36, 0.37, 0.38, 0.34, 0.24, 0.12]
    nu = 8
    Gk = [[(0.5 + (-1 + 2 * i / nu) * hw, z) for i in range(nu + 1)] for z, hw in zip(zs, hws)]
    shell(kcp, lc, Gk, lambda j, i, u, v: 0.05 + 0.03 * (1 - abs(-1 + 2 * i / nu)) ** 1.3 + (0.014 if j <= 1 else 0.0),
          lift=lambda j, i, u, v: lerp(0.088, 0.03, (v - 0.20) / 0.26), mat_fn=lambda j, i: GLD if j == 0 else LAC,
          rim_mat=BLK, flush=True)
    comps.append(kcp)
    knot(kc, lc, 0.5, 0.32, lerp(0.088, 0.03, 0.46) + 0.08, 0.03)
    comps.append(kc)
    return comps


# ----- Boots: lacquered cuff with a gold cord tie, and the foot ------------------------------
def build_lower_leg_boots():
    comps = []
    lc = limb_chart(r=0.1)
    L = lc.stations
    c = Comp(bevel=0.012, segs=2, angle=32)
    nu = 10
    us = [0.025 + (L["total"] - 0.05) * i / nu for i in range(nu + 1)]
    shell(c, lc, grid(us, [-0.597, -0.575, -0.46, -0.435, -0.41]), lambda j, i, u, v: 0.05 + (0.016 if j >= 3 else 0.0),
          mat_fn=lambda j, i: GLD if j == 3 else BLK, rim_mat=GLD, flush=True)
    comps.append(c)
    cc = Comp(shade="smooth")
    pts = []
    for u in us:
        P, N = lc(u, -0.515)
        pts.append(P + N * 0.062)
    horn(cc, pts, 0.02, sides=5, taper=0.0, r_tip=0.02, mat=GLD, up=UP)
    P, N = lc(L["outer_mid"], -0.515)
    bow(cc, P + N * 0.09, N, UP, s=0.42, tails=0.26, root=0.055, lite=True)
    comps.append(cc)
    return comps


def build_foot():
    comps = []
    lc = limb_chart(r=0.1)
    L = lc.stations
    c = Comp(bevel=0.012, segs=2, angle=32)
    nu = 12
    us = [0.025 + (L["total"] - 0.05) * i / nu for i in range(nu + 1)]
    vs = [-0.15, -0.135, -0.10, -0.075, 0.02, 0.045]

    def th(j, i, u, v):
        P, _ = lc(u, 0)
        toe = 0.035 * max(0.0, 1 - abs(P.x) / 0.42) if P.y < -0.45 else 0.0
        return (0.075 if j <= 2 else 0.058) + (toe if 3 <= j <= 4 else 0.0)
    shell(c, lc, grid(us, vs), th, mat_fn=lambda j, i: DRK if j <= 1 else BLK, rim_mat=BLK,
          flush=True)
    comps.append(c)
    # gold cord crossing the instep
    cc = Comp(shade="smooth")
    for a, b in (((0.12, 0.0), (0.88, -0.09)), ((0.12, -0.09), (0.88, 0.0))):
        pts = []
        for k in range(6):
            t = k / 5
            u, z = lerp(a[0], b[0], t), lerp(a[1], b[1], t)
            P, N = lc(u, z)
            toe = 0.035 * max(0.0, 1 - abs(P.x) / 0.42)
            pts.append(P + N * (0.058 + toe * smooth((z + 0.075) / 0.03) + 0.008))
        horn(cc, pts, 0.017, sides=5, taper=0.0, r_tip=0.017, mat=GLD)
    P, N = lc(0.5, -0.045)
    rivet(cc, P + N * 0.09, N, r=0.035, h=0.026, sides=4, mat=GLD)
    comps.append(cc)
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
        bs.inputs["Roughness"].default_value = 0.4 if i in (GLD, LAC, BLK) else 0.75
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


SPEC = [  # (piece, part, builder, mirrored pair?)
    ("Helmet", "Head", build_head, False),
    ("Chest", "UpperTorso", build_upper_torso, False),
    ("Chest", "LowerTorso", build_lower_torso, False),
    ("Chest", "UpperArm", build_upper_arm, True),
    ("Chest", "LowerArm", build_lower_arm, True),
    ("Legs", "UpperLeg", build_upper_leg, True),
    ("Legs", "LowerLeg", build_lower_leg_legs, True),
    ("Boots", "LowerLeg", build_lower_leg_boots, True),
    ("Boots", "Foot", build_foot, True),
]
armor_objs = []
for piece, part, builder, pair in SPEC:
    comps = builder()
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
# Body proxy for previews and pose checks (never exported)
# ---------------------------------------------------------------------------
body_mat = bpy.data.materials.new("Proxy_Body")
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
# PAINTERLY BAKE (Dragon Scale recipe, cheaper: 1024 direct, 8 samples). Baked masks drive the
# paint: AO darkens overlaps between rows, a small-radius AO finds cavities, the Bevel node finds
# convex edges for painted highlights. Crimson shades toward cool purple and lifts to warm
# orange-red; gold shades toward brown; lacing cords and mail rings are painted from metric coords.
# ===========================================================================
KEY = Vector((0.0, -0.55, 0.83)).normalized()
GLINT = Vector((0.0, -0.42, 0.91)).normalized()
RIM = Vector((0.0, 0.85, 0.35)).normalized()


def atlas_of(o):
    piece = o.name.split("_")[1]
    part = o["body_part"]
    if piece == "Helmet":
        return "helmet"
    if piece == "Chest":
        return "torso" if part.endswith("Torso") else "arms"
    return "legs"


class NB:
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

    def mail(self):
        """Kusari rings in staggered rows, 0.125 studs apart (from the metric R/G coords)."""
        U = self.math("MULTIPLY", self.G, 64.0)
        V = self.math("MULTIPLY", self.R, 64.0)
        odd = self.math("MODULO", self.math("FLOOR", V), 2.0)
        U2 = self.math("MULTIPLY_ADD", odd, 0.5, U)
        qx = self.math("SUBTRACT", self.math("FRACT", U2), 0.5)
        qy = self.math("SUBTRACT", self.math("FRACT", V), 0.5)
        cx = self.nt.nodes.new("ShaderNodeCombineXYZ")
        self.nt.links.new(qx, cx.inputs["X"])
        self.nt.links.new(qy, cx.inputs["Y"])
        ln = self.nt.nodes.new("ShaderNodeVectorMath")
        ln.operation = "LENGTH"
        self.nt.links.new(cx.outputs["Vector"], ln.inputs[0])
        d = self.math("ABSOLUTE", self.math("SUBTRACT", ln.outputs["Value"], 0.31))
        return self.math("SUBTRACT", 1.0, self.smoothstep(d, 0.035, 0.075))

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
    occl = b.math("MULTIPLY", ao, cav)
    S = b.math("MULTIPLY", light, occl, clamp_=True)
    patches = b.math("MULTIPLY_ADD", b.noise(1.4, 1.0, 0.4, 0.3), 0.14, -0.07)
    strokes = b.math("MULTIPLY_ADD", b.noise(5.0, 1.5, 0.5, 0.6, (1.0, 1.0, 3.2)), 0.07, -0.035)
    paint = b.math("ADD", patches, strokes)
    edge = b.math("MULTIPLY", b.bevel_edge(0.018), b.smoothstep(ao, 0.55, 0.9))
    glint = b.smoothstep(b.dot(Nrm, GLINT), 0.80, 0.97)
    rim = b.math("MAXIMUM", b.dot(Nrm, RIM), 0.0)
    edge_up = b.math("MULTIPLY", edge, b.math("MULTIPLY_ADD", sky, 0.5, 0.5))

    def tint_shade(base, lo=(30, 24, 52), mid=(176, 168, 186), hi=(255, 246, 234)):
        sh = b.ramp(b.math("ADD", S, b.math("MULTIPLY", paint, 0.6)), [(0.0, lo), (0.5, mid), (1.0, hi)])
        return b.mix(1.0, base, sh, "MULTIPLY")

    if idx == LAC:
        col = b.ramp(b.math("ADD", S, paint), [(0.0, (30, 6, 26)), (0.2, (62, 9, 30)), (0.42, (108, 14, 32)),
                                               (0.62, (150, 24, 36)), (0.8, (188, 44, 42)), (1.0, (230, 100, 72))])
        col = b.mix(1.0, col, b.math("MULTIPLY_ADD", b.B, 0.14, 0.93), "MULTIPLY")        # per-row value jitter
        laced = b.math("MULTIPLY", b.smoothstep(b.A, 0.35, 0.45), b.math("SUBTRACT", 1.0, b.smoothstep(b.A, 0.6, 0.7)))
        d = b.math("ABSOLUTE", b.math("SUBTRACT", b.math("FRACT", b.math("MULTIPLY", b.G, 24.0)), 0.5))
        cord = b.math("SUBTRACT", 1.0, b.smoothstep(d, 0.05, 0.075))
        cord = b.math("MULTIPLY", cord, b.smoothstep(b.R, 0.03, 0.10))   # cords start under the row above
        seam = b.smoothstep(d, 0.45, 0.49)                              # kozane scale edges between cords
        cordcol = b.ramp(b.math("ADD", S, b.math("MULTIPLY", paint, 0.5)),
                         [(0.0, (30, 14, 6)), (0.35, (82, 46, 16)), (0.6, (138, 92, 34)), (0.82, (184, 136, 62)),
                          (1.0, (222, 182, 108))])
        col = b.mix(b.math("MULTIPLY", b.math("MULTIPLY", laced, seam), 0.4), col, (26, 4, 14))
        col = b.mix(b.math("MULTIPLY", laced, cord, clamp_=True), col, cordcol)
        col = b.mix(b.math("MULTIPLY", glint, 0.35), col, (120, 70, 60), "ADD")
        col = b.mix(b.math("MULTIPLY", rim, 0.22), col, (18, 14, 46), "ADD")
        col = b.mix(b.math("MULTIPLY", edge_up, 0.7), col, (250, 160, 124))
    elif idx == BLK:
        col = b.ramp(b.math("ADD", S, paint), [(0.0, (5, 5, 10)), (0.28, (11, 11, 20)), (0.48, (20, 20, 32)),
                                               (0.66, (32, 32, 46)), (0.84, (50, 49, 64)), (1.0, (76, 72, 88))])
        col = b.mix(b.math("MULTIPLY", glint, 0.4), col, (96, 84, 84), "ADD")
        col = b.mix(b.math("MULTIPLY", rim, 0.3), col, (12, 18, 44), "ADD")
        col = b.mix(b.math("MULTIPLY", edge_up, 0.75), col, (160, 144, 142))
    elif idx == GLD:
        col = b.ramp(b.math("ADD", S, b.math("MULTIPLY", paint, 0.6)),
                     [(0.0, (46, 24, 10)), (0.25, (104, 60, 22)), (0.48, (172, 114, 40)), (0.68, (218, 162, 64)),
                      (0.85, (244, 206, 112)), (1.0, (255, 238, 178))])
        col = b.mix(b.math("MULTIPLY", glint, 0.45), col, (255, 236, 170), "ADD")
        col = b.mix(b.math("MULTIPLY", edge_up, 0.85), col, (255, 246, 210))
    elif idx == CLO:
        weave = b.noise(38.0, 1.0, 0.5, 0.0, (1.0, 1.0, 4.0))
        base = b.ramp(b.math("ADD", b.math("MULTIPLY", weave, 0.18), b.math("MULTIPLY_ADD", paint, 1.2, 0.41)),
                      [(0.2, (22, 28, 60)), (0.5, (34, 44, 90)), (0.8, (50, 62, 118))])
        col = tint_shade(base)
    elif idx == MAIL:
        ring = b.mail()
        base = b.ramp(b.math("ADD", paint, 0.5), [(0.3, (16, 20, 42)), (0.7, (26, 32, 64))])
        base = tint_shade(base)
        iron = b.ramp(b.math("ADD", S, paint), [(0.0, (12, 12, 20)), (0.5, (50, 54, 70)), (0.8, (84, 88, 104)),
                                                (1.0, (120, 118, 128))])
        col = b.mix(b.math("MULTIPLY", ring, 0.7), base, iron)
    else:
        col = b.ramp(S, [(0.0, (4, 4, 8)), (1.0, (30, 26, 36))])
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
    for proxy in PROXY.values():
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
        bs.inputs["Specular IOR Level"].default_value = 0.05    # matte, closer to SmoothPlastic
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
            if "Detail" in o.data.color_attributes:
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
    report = {"set": SET, "rarity": "Epic", "blender_version": bpy.app.version_string,
              "authoring": "final Roblox stud size; import at 1:1, do not scale", "pieces": {}}
    install = {"set": SET, "glow_color_srgb": None, "helmet": "full",
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
        scene.eevee.taa_render_samples = 16 if QUICK else 64
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
    return cam


def shoot(name, loc, target=(0, 0, 2.85), lens=70, res=(1000, 1200)):
    if VIEWS and name not in VIEWS:
        return None
    cam.data.lens = lens
    scene.render.resolution_x, scene.render.resolution_y = res
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    out = PV / f"{name}.png"
    scene.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)
    log("render", name)
    return out


cam = setup_preview_scene()
D = 15.0
shoot("front", (0, -D, 3.3))
shoot("back", (0, D, 3.3))
shoot("side", (D, 0, 3.3))
shoot("threeq", (D * 0.62, -D * 0.78, 5.0))
shoot("close-helm", (3.0, -7.4, 5.5), target=(0, 0, 4.85), lens=100)
if QUICK:
    shoot("q-helm-front", (0.0, -7.0, 4.7), target=(0, 0, 4.75), lens=110)
    shoot("q-legs", (4.2, -9.2, 1.9), target=(0, 0, 1.6), lens=90)

# ---------------------------------------------------------------------------
# Pose check (numbers only): rotate the proxy's part groups (body + armour) about their rig
# joints through the default R15 walk/run/jump extremes and count intersecting triangle pairs.
# ---------------------------------------------------------------------------
CHILDREN = {}
for child, (parent, att) in JOINT.items():
    CHILDREN.setdefault(parent, []).append(child)
ARMOR_BY_PART = {}
for o in armor_objs:
    ARMOR_BY_PART.setdefault(o["body_part"], []).append(o)
REST_MW = {o.name: o.matrix_world.copy() for o in list(PROXY.values()) + armor_objs}


def swing(deg):
    return Matrix.Rotation(math.radians(-deg), 4, "X")


def spread(deg, side):
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
        for o in ARMOR_BY_PART.get(part, []) + ([PROXY[part]] if part in PROXY else []):
            o.matrix_world = M @ REST_MW[o.name]
    bpy.context.view_layer.update()


def world_bvh(o):
    mw = o.matrix_world
    return BVHTree.FromPolygons([mw @ v.co for v in o.data.vertices], [list(p.vertices) for p in o.data.polygons])


def clip_report():
    groups = {}
    for part in set(list(PROXY.keys()) + list(ARMOR_BY_PART.keys())):
        groups[part] = {"armor": [world_bvh(o) for o in ARMOR_BY_PART.get(part, [])],
                        "body": world_bvh(PROXY[part]) if part in PROXY else None}
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
         "totals": {p: sum(v.values()) for p, v in clip.items()},
         "results": clip}, indent=1))

# ---------------------------------------------------------------------------
# Contact sheet (composited with numpy)
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
            w_ = cell_w
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
        top = H - y0 - h_
        sheet[top:top + h_, x:x + w_, :] = px
    img = bpy.data.images.new(name, W, H, alpha=False)
    img.pixels.foreach_set(sheet.ravel())
    img.filepath_raw = str(PV / f"{name}.png")
    img.file_format = "PNG"
    img.save()
    log("sheet", name, W, H)


tall = 1.2
compose("sheet", [[(PV / "front.png", tall), (PV / "threeq.png", tall), (PV / "side.png", tall),
                   (PV / "back.png", tall), (PV / "close-helm.png", tall)]], 400)
if QUICK:
    compose("q-close", [[(PV / "q-helm-front.png", tall), (PV / "q-legs.png", tall), (PV / "threeq.png", tall)]], 520)

if not QUICK:
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / f"{SET}.blend"))
log("DONE")
