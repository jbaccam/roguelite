"""Spartan armor set (Epic): a hoplite hero in polished bronze and crimson, fitted to the normalized
R15 body. Self-contained (the pipeline is copied from build_dragon_scale.py, never imported).

Run (background Blender 5.2, never the user's open scene):
  blender -b --factory-startup --threads 2 --python build_spartan.py
Env:
  QUICK=1      flat preview colours only: no bake, no exports (fast shape passes)
  QDIR=<dir>   where QUICK renders go (default previews/quick)
  NOPOSE=1     skip the numeric pose check

Design: a Corinthian bronze helm (cheek guards, eye openings, nose guard) with a tall, chunky
crimson horsehair crest fused into a bronze holder; a cartoon muscle cuirass with rolled neck and
waist edges; a short rigid crimson cape over the shoulders; rounded bronze shoulder domes over a row
of leather pteruges; a pteruges skirt; bronze vambraces and greaves with sculpted calves; leather
thigh bands; sandal-boots with criss-cross straps and a bronze toe plate; a painted lambda on the
belt boss. No glow, no particles.

Blender axes: +z up, -y = the character's front, +x = the character's LEFT.
Studio axes = (-x, z, y) of Blender.
"""
import bpy, bmesh, math, json, os, random, time
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from pathlib import Path

T0 = time.time()
ROOT = Path(__file__).resolve().parent
KIT = ROOT.parent                     # blender-armor-kit (read only: the measured R15 proxy)
SET = "spartan"
PREFIX = "Spartan"
QUICK = os.environ.get("QUICK") == "1"
NOPOSE = os.environ.get("NOPOSE") == "1"
BAKE_SIZE = 1024                      # Roblox caps textures at 1024; baked directly at this size
BAKE_SAMPLES = 8
for d in ("exports/fbx", "exports/glb", "textures", "previews"):
    (ROOT / d).mkdir(parents=True, exist_ok=True)
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
MAT_NAMES = ["Bronze", "Crimson", "Leather", "Suit", "Dark", "Emblem"]
BRZ, CRM, LTH, SUIT, DRK, EMB = range(6)
PREVIEW_RGB = {BRZ: (200, 138, 62), CRM: (158, 30, 36), LTH: (116, 72, 40), SUIT: (78, 34, 34),
               DRK: (24, 18, 18), EMB: (172, 34, 38)}


def lin(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgba(c, a=1.0):
    return (lin(c[0]), lin(c[1]), lin(c[2]), a)


# ---------------------------------------------------------------------------
# Mesh components (each finished on its own, then joined per body part). "Detail" colour per loop:
#   R = along the element (0 root/top -> 1 tip) or height fraction, G = across,
#   B = per-element random, A = zone flag (crest grooves; dark leather)
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


def bump(x, y, cx, cy, rx, ry):
    d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
    return max(0.0, 1.0 - d) ** 1.5


# ---------------------------------------------------------------------------
# Charts: (u, v) -> (point on the body offset by the clearance, outward normal), part-local.
# ---------------------------------------------------------------------------
CL = 0.028          # gap between the body and the inside of an armour layer
SUIT_CL = 0.012     # the undersuit hugs the body under the plates


def torso_chart(side, hx=1.0, hy=0.5, hz=0.8, rc=0.12, clear=CL):
    """Front (side -1) or back (+1) face of a box; v runs up the face, over the top fillet and
    onto the top face. u = x."""
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


def wrap_chart(hx=1.0, hy=0.5, hz=0.8, rc=0.12, clear=CL):
    """Up the back face, over the back fillet, across the top, over the front fillet, down the
    front face (the cape's chart). u = x."""
    R = rc + clear
    s_c = hz - rc
    arc = math.pi / 2 * R
    top = 2 * (hy - rc)

    def f(u, v):
        if v <= s_c:
            return Vector((u, hy + clear, v)), Vector((0, 1, 0))
        if v <= s_c + arc:
            a = (v - s_c) / R
            return Vector((u, (hy - rc) + R * math.cos(a), s_c + R * math.sin(a))), Vector((0, math.cos(a), math.sin(a)))
        if v <= s_c + arc + top:
            d = v - s_c - arc
            return Vector((u, (hy - rc) - d, hz + clear)), Vector((0, 0, 1))
        if v <= s_c + 2 * arc + top:
            a = (v - s_c - arc - top) / R
            return (Vector((u, -(hy - rc) - R * math.sin(a), s_c + R * math.cos(a))),
                    Vector((0, -math.sin(a), math.cos(a))))
        e = v - (s_c + 2 * arc + top)
        return Vector((u, -(hy + clear), s_c - e)), Vector((0, -1, 0))
    f.top0, f.top1, f.front0 = s_c + arc, s_c + arc + top, s_c + 2 * arc + top
    return f


def limb_chart(hx=0.5, hy=0.5, r=0.13, clear=CL):
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


# Shoulder dome (left upper arm; outer = +x): a superquadric that encloses the arm's rounded top
PD_O = Vector((0.0, 0.0, 0.03))
PD_R = Vector((0.82, 0.66, 0.74))
PD_N = 2.7
PD_SU, PD_TV = 1.30, 0.47


def pd_raw(s, t):
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
# Geometry helpers (copied from the Dragon Scale kit)
# ---------------------------------------------------------------------------
def shell(c, chart, G, thick, *, lift=None, wrap=False, mat=BRZ, mat_fn=None, rim_mat=None,
          flush=True, rnd=None, det_fn=None, inner_mat=DRK):
    """A thick plate from a grid of chart coordinates G[j][i] = (u, v)."""
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
                fi.append(c.f([inner[j][i], inner[j + 1][i], inner[j + 1][i2], inner[j][i2]], inner_mat))
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


def horn(c, pts, r0, *, sides=7, taper=1.0, flat=1.0, mat=BRZ, up=None, rnd=None, r_tip=0.0, cap=True):
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
    if f0 is not None and f0.normal.dot(f0.calc_center_median() - pts[0]) < 0:
        for f in faces:
            if f is not None:
                f.normal_flip()
    return faces


def tube(c, pts, r, sides=8, mat=BRZ):
    """Rolled edge: a round bead of constant radius along pts."""
    return horn(c, pts, r, sides=sides, taper=0.0, r_tip=r, mat=mat)


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


def flip_if(faces, probe, direction):
    if probe is not None and probe.normal.dot(direction) < 0:
        for f in faces:
            if f is not None:
                f.normal_flip()


def frame(N):
    N = N.normalized()
    a = Vector((0, 0, 1)) if abs(N.z) < 0.9 else Vector((1, 0, 0))
    X = N.cross(a).normalized()
    return X, N.cross(X), N


def rivet(c, P, N, r=0.028, h=0.018, sides=6, mat=BRZ):
    X, Y, N = frame(N)
    ring0 = [P + (X * math.cos(2 * math.pi * s / sides) + Y * math.sin(2 * math.pi * s / sides)) * r - N * 0.004
             for s in range(sides)]
    ring1 = [P + (X * math.cos(2 * math.pi * s / sides) + Y * math.sin(2 * math.pi * s / sides)) * r * 0.62 + N * h * 0.8
             for s in range(sides)]
    faces, V = loft(c, [ring0, ring1], mat, cap0=False, cap1=False)
    top = c.v(P + N * h)
    for s in range(sides):
        faces.append(c.f([V[1][s], V[1][(s + 1) % sides], top], mat))
    c.bm.normal_update()
    flip_if(faces, faces[0], faces[0].calc_center_median() - P if faces[0] else N)


def disc(c, P, N, r, h, mat=BRZ, sides=14, up=None):
    """A flat bronze boss with a rolled rim; returns its face frame (X, Y, N, face centre)."""
    X, Y, N = frame(N)
    if up is not None:
        Y = (up - N * up.dot(N)).normalized()
        X = Y.cross(N).normalized()

    def ring(rr, hh):
        return [P + (X * math.cos(2 * math.pi * s / sides) + Y * math.sin(2 * math.pi * s / sides)) * rr + N * hh
                for s in range(sides)]
    faces, _ = loft(c, [ring(r, -0.004), ring(r, h * 0.62), ring(r * 0.87, h), ring(r * 0.75, h * 0.8)], mat,
                    cap0=False, cap1=True)
    flip_if(faces, faces[-1], N)
    return X, Y, N, P + N * (h * 0.8)


def slab(c, P, X, Y, N, lx, ly, h, mat):
    cs = [P + X * sx * lx + Y * sy * ly for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    faces, _ = loft(c, [[q - N * 0.003 for q in cs], [q + N * h for q in cs]], mat, cap0=False, cap1=True)
    flip_if(faces, faces[-1], N)


def grid(us, vs):
    return [[(u, v) for u in us] for v in vs]


def limb_cols(ch):
    """Column stations around a limb chart that follow its rounded corners."""
    st = ch.stations
    arc0 = [st["outer0"] - (st["outer0"] - st["corner_fo"]) * 2 + (st["outer0"] - st["corner_fo"]) * 2 * k / 3 for k in range(4)]
    arc1 = [st["outer1"] + (st["corner_ob"] - st["outer1"]) * 2 * k / 3 for k in range(4)]
    return [0.012, st["front_mid"] * 0.5, st["front_mid"]] + arc0 + [st["outer_mid"]] + arc1 + \
        [st["back_mid"], (st["back_mid"] + st["back_in"]) / 2, st["back_in"] - 0.012]


def undersuit_box(comps, chart, us, vs, rnd=0.5):
    """Dark crimson linen tunic (flush, single surface) that shows in every gap."""
    c = Comp(bevel=0.0, shade="smooth")
    shell(c, chart, grid(us, vs), 0.004, mat=SUIT, rnd=rnd)
    comps.append(c)


def strip(c, chart, u0, u1, v_top, v_end, lift_fn, thick, mat=LTH, rows=(0.0, 0.45, 0.8, 0.93, 1.0), ncol=4,
          flag=0.0):
    """A leather strip hanging from v_top to a rounded end at v_end; lift_fn(v) flares it out."""
    r = (u1 - u0) / 2
    uc = (u0 + u1) / 2
    rnd = RNG.random()
    G = []
    for t in rows:
        row = []
        for i in range(ncol + 1):
            u = lerp(u0, u1, i / ncol)
            vb = v_end + r - math.sqrt(max(0.0, r * r - (u - uc) ** 2))
            row.append((u, lerp(v_top, vb, t)))
        G.append(row)
    shell(c, chart, G, thick, lift=lambda j, i, u, v: lift_fn(v), mat=mat,
          det_fn=lambda j, i, u, v: (j / (len(rows) - 1), i / ncol, rnd, flag))


def strap(c, chart, a, b, w, thick, lift_fn=None, mat=LTH, n=3, flag=0.0):
    """A straight leather strap between chart points a and b."""
    a, b = Vector(a), Vector(b)
    d = (b - a).normalized()
    p = Vector((-d.y, d.x)) * (w / 2)
    G = [[tuple(a + (b - a) * (j / n) + p * s) for s in (-1, 1)] for j in range(n + 1)]
    rnd = RNG.random()
    shell(c, chart, G, thick, lift=(lambda j, i, u, v: lift_fn(j / n)) if lift_fn else None, mat=mat,
          det_fn=lambda j, i, u, v: (j / n, i, rnd, flag))


# ===========================================================================
# PIECES. Each builder returns a list of Comp in the part's local space. Left-side builders are
# mirrored for the right side.
# ===========================================================================
UP = Vector((0, 0, 1))


# ----- Helmet: Corinthian helm with a crimson horsehair crest ------------------
def ang(th):
    th = th % (2 * math.pi)
    return th if th <= math.pi else 2 * math.pi - th


H_L1, H_L2 = 0.95, math.pi / 2 * (0.25 + CL)
H_SMAX = H_L1 + H_L2 + 0.35


def build_head():
    comps = []
    hc = head_chart()

    # dark liner behind the eye openings and the mouth slit
    li = Comp(shade="smooth")
    shell(li, head_chart(SUIT_CL), [[(lerp(-0.95, 0.95, i / 8), z + 0.6) for i in range(9)]
                                    for z in (-0.57, -0.3, 0.0, 0.24)], 0.004, mat=DRK)
    comps.append(li)

    # lower shell: cheek guards and neck guard, a T-shaped face opening at the front
    def th_in(z):                    # half-angle of the opening: mouth slit below, eyes above
        return lerp(0.085, 0.60, smooth((z + 0.20) / 0.15))

    def z_bot(th):                   # rolled lower edge with the classic notch under the ear
        notch = max(0.0, 1 - ((ang(th) - 1.55) / 0.34) ** 2) ** 1.3
        return -0.565 + 0.21 * notch
    ZTOP = 0.20
    zr = [-0.565, -0.54, -0.48, -0.38, -0.27, -0.19, -0.12, -0.04, 0.05, 0.13, 0.20]
    fr = [(z - zr[0]) / (ZTOP - zr[0]) for z in zr]
    NC = 26
    G = []
    for j, zn in enumerate(zr):
        t0 = th_in(zn)
        row = []
        for i in range(NC + 1):
            th = lerp(t0, 2 * math.pi - t0, i / NC)
            row.append((th, lerp(z_bot(th), ZTOP, fr[j]) + 0.6))
        G.append(row)

    def th_b(j, i, th, s):
        z = s - 0.6
        a = ang(th)
        t = 0.052 + 0.042 * bump(a, z, 0.62, -0.30, 0.55, 0.28)         # sculpted cheek guards
        if j <= 1:
            t += 0.02                                                  # rolled lower edge
        if i <= 1 or i >= NC - 1:
            t += 0.016                                                 # raised rim round the opening
        return t

    def lift_b(j, i, th, s):
        return 0.075 * smooth((ang(th) - 1.85) / 0.8) * (1 - fr[j]) ** 2  # neck guard flares out
    c = Comp(bevel=0.014, segs=2, angle=30)
    shell(c, hc, G, th_b, lift=lift_b, mat=BRZ)
    comps.append(c)

    # dome with a heavy brow band arching over the eyes
    ss = [0.76, 0.79, 0.84, 0.95, H_L1 + H_L2 * 0.4, H_L1 + H_L2 * 0.75, H_L1 + H_L2,
          H_L1 + H_L2 + 0.12, H_L1 + H_L2 + 0.24, H_SMAX - 0.02]
    ND = 28
    Gd = [[(-math.pi + 2 * math.pi * i / ND, s) for i in range(ND)] for s in ss]

    def th_d(j, i, th, s):
        a = ang(th)
        z = head_profile(s, CL)[1]
        front = 1 - smooth((a - 0.9) / 0.6)
        t = 0.058
        if j <= 2:
            t += 0.034 * front + 0.014 * (1 - front)
        t += 0.022 * bump(a, z, 0.34, 0.215, 0.30, 0.09)
        return t
    cd = Comp(bevel=0.014, segs=2, angle=30)
    shell(cd, hc, Gd, th_d, wrap=True, mat=BRZ)
    comps.append(cd)

    # nose guard with a centre ridge
    cn = Comp(bevel=0.01, segs=2, angle=30)
    zs = [-0.17, -0.14, -0.05, 0.05, 0.14, 0.20]
    ws = [0.075, 0.072, 0.058, 0.055, 0.065, 0.075]
    shell(cn, hc, [[(lerp(-w, w, i / 2), z + 0.6) for i in range(3)] for z, w in zip(zs, ws)],
          lambda j, i, th, s: 0.066 - 0.012 * abs(i - 1), mat=BRZ)
    comps.append(cn)

    # temple rivets on the brow band
    rv = Comp(shade="smooth")
    for th in (1.2, 1.62, -1.2, -1.62):
        P, N = hc(th, 0.6 + 0.195)
        rivet(rv, P + N * 0.07, N, r=0.032, h=0.022)
    comps.append(rv)

    # crest: a thick rounded horsehair mass with broad combed grooves, fused into a bronze holder
    SF, SB = 0.86, 0.60

    def base(u):
        th = 0.0 if u < 0 else math.pi
        s = H_SMAX - abs(u) * (H_SMAX - (SF if u < 0 else SB))
        P, N = hc(th, s)
        return P + N * 0.056, N
    HK = [(-1.0, 0.11), (-0.62, 0.29), (-0.2, 0.41), (0.25, 0.43), (0.62, 0.35), (1.0, 0.18)]
    WK = [(-1.0, 0.14), (-0.5, 0.235), (0.3, 0.255), (1.0, 0.19)]

    def keyed(K, x):
        for (x0, y0), (x1, y1) in zip(K, K[1:]):
            if x <= x1:
                return lerp(y0, y1, smooth((x - x0) / (x1 - x0)))
        return K[-1][1]
    NP = 20
    us = [-1 + 2 * k / (NP - 1) for k in range(NP)]
    endsc = {0: 0.42, 1: 0.8, NP - 2: 0.8, NP - 1: 0.42}
    X = Vector((1, 0, 0))
    sec = []
    for q in range(21):
        psi = -math.pi / 2 + math.pi * q / 20
        g = 0.5 - 0.5 * math.cos(10 * psi)          # 5 rounded ridges, 4 broad grooves
        rr = 1 - 0.07 * g
        sec.append(((abs(math.cos(psi)) ** 0.42) * rr, math.sin(psi) * (1 + 0.14 * math.cos(psi)) * rr, g))
    A0 = 0.035
    rings, hrings, nrms = [], [], []
    for k, u in enumerate(us):
        P, N = base(u)
        f = endsc.get(k, 1.0)
        h, w = keyed(HK, u) * f, keyed(WK, u) * (0.6 + 0.4 * f)
        ring = [P + N * (A0 + a * h) + X * (b * w) for a, b, g in sec]
        ring += [P + X * (0.5 * w), P - X * (0.5 * w)]
        rings.append(ring)
        W = 0.915 * w + 0.035
        hrings.append([P + N * a + X * b for a, b in ((-0.012, -W), (0.045, -W - 0.012), (0.074, -W + 0.016),
                                                        (0.074, W - 0.016), (0.045, W + 0.012), (-0.012, W))])
        nrms.append(N)

    def det(k, s):
        if s < len(sec):
            return (sec[s][0], k / (NP - 1), 0.5, sec[s][2])
        return (0.0, k / (NP - 1), 0.5, 0.0)
    cc = Comp(shade="smooth")
    faces, _ = loft(cc, rings, CRM, det=det)
    m = len(rings[0])
    flip_if(faces, faces[(NP // 2) * m + 10], nrms[NP // 2])
    comps.append(cc)
    ch_ = Comp(bevel=0.008, segs=2, angle=30)
    faces, _ = loft(ch_, hrings, BRZ)
    flip_if(faces, faces[(NP // 2) * 6 + 2], nrms[NP // 2])
    comps.append(ch_)
    return comps


# ----- UpperTorso: muscle cuirass + cape ----------------------------------------
NECK_LO = 0.58


def neckline(u, hi):
    return NECK_LO + (hi - NECK_LO) * smooth((abs(u) - 0.55) / 0.30)


def waist_flare(v):
    return 0.035 * smooth((-0.55 - v) / 0.24)


def cuirass_front_th(u, v):
    x = abs(u)
    t = 0.05
    ry = 0.30 if v > 0.34 else 0.21                     # crisp lower pec edge
    t += 0.10 * bump(x, v, 0.46, 0.34, 0.44, ry)          # pecs
    for cy in (0.02, -0.25, -0.51):
        t += 0.042 * bump(x, v, 0.19, cy, 0.16, 0.115)    # abs, 2 x 3 blocks
    if v < 0.55:
        t -= 0.022 * max(0.0, 1 - x / 0.05)               # centre groove
    return lerp(t, 0.05, smooth((v - 0.60) / 0.25))


def cuirass_back_th(u, v):
    x = abs(u)
    t = 0.05 + 0.045 * bump(x, v, 0.45, 0.30, 0.34, 0.30)
    if v < 0.6:
        t -= 0.015 * max(0.0, 1 - x / 0.05)
    return lerp(t, 0.05, smooth((v - 0.60) / 0.25))


CAPE_LIFT = 0.10


def cape_lift(u, v, wc):
    amp = 0.09 * smooth((0.40 - v) / 1.05)
    fold = amp * (0.5 + 0.5 * math.cos(2 * math.pi * u / 0.48))
    flare = 0.05 * smooth((0.35 - v) / 1.0)
    over = 0.03 * max(0.0, 1 - abs(v - (wc.top0 - 0.116)) / 0.2) + 0.03 * max(0.0, 1 - abs(v - (wc.top1 + 0.116)) / 0.2)
    return CAPE_LIFT + fold + flare + over


def build_upper_torso():
    comps = []
    for side in (-1, 1):
        sc_ = torso_chart(side, clear=SUIT_CL)
        lim = sc_.top + 0.36

        def suit_top(u):
            v = 0.6
            while v < lim:
                nv = min(lim, v + 0.01)
                P, _ = sc_(u, nv)
                if P.z >= 0.775 and P.x * P.x + P.y * P.y < 0.64 ** 2:
                    break
                v = nv
            return v
        uu = [-0.99, -0.88, -0.77, -0.68, -0.6, -0.5, -0.3, 0.0, 0.3, 0.5, 0.6, 0.68, 0.77, 0.88, 0.99]
        su_ = Comp(shade="smooth")
        shell(su_, sc_, [[(u, lerp(0.2, suit_top(u), t)) for u in uu] for t in (0.0, 0.3, 0.55, 0.72, 0.86, 1.0)],
              0.004, mat=SUIT, rnd=0.5)
        comps.append(su_)

    # front plate
    ch = torso_chart(-1)
    hi = ch.top + 0.37
    us = [-0.975 + 1.95 * i / 20 for i in range(21)]
    tv = [j / 19 for j in range(20)]
    G = [[(u, lerp(-0.79, neckline(u, hi), t)) for u in us] for t in tv]
    c = Comp(bevel=0.014, segs=2, angle=30)
    shell(c, ch, G, lambda j, i, u, v: cuirass_front_th(u, v), lift=lambda j, i, u, v: waist_flare(v), mat=BRZ)
    comps.append(c)
    rt = Comp(shade="smooth")
    pts = []
    for k in range(19):
        u = lerp(-0.94, 0.94, k / 18)
        v = neckline(u, hi) - 0.012
        P, N = ch(u, v)
        pts.append(P + N * (waist_flare(v) + cuirass_front_th(u, v) - 0.004))
    tube(rt, pts, 0.034, sides=7)
    pts = []
    for u in (-0.94, 0.94):
        P, N = ch(u, -0.772)
        pts.append(P + N * (waist_flare(-0.772) + 0.05 - 0.006))
    tube(rt, pts, 0.036)

    # back plate (mostly under the cape)
    cb = torso_chart(1)
    hib = cb.top + 0.34
    us = [-0.975 + 1.95 * i / 12 for i in range(13)]
    tv = [j / 11 for j in range(12)]
    G = [[(u, lerp(-0.79, neckline(u, hib), t)) for u in us] for t in tv]
    c = Comp(bevel=0.014, segs=2, angle=30)
    shell(c, cb, G, lambda j, i, u, v: cuirass_back_th(u, v), lift=lambda j, i, u, v: waist_flare(v), mat=BRZ)
    comps.append(c)
    pts = []
    for u in (-0.94, 0.94):
        P, N = cb(u, -0.772)
        pts.append(P + N * (waist_flare(-0.772) + 0.05 - 0.006))
    tube(rt, pts, 0.036)
    comps.append(rt)

    # cape: from over the shoulders down to the lower back, broad sculpted folds, clear of the helm
    wc = wrap_chart()
    vmax = wc.top0 + 0.46

    def ok(u, v):
        P, N = wc(u, v)
        Q = P + N * cape_lift(u, v, wc)
        return Q.z < 0.76 or Q.x * Q.x + Q.y * Q.y >= 0.80 ** 2

    def v_end(u):
        lim = min(vmax, 0.60 + 3.0 * smooth((abs(u) - 0.40) / 0.45))
        v = 0.55
        while v < lim:
            nv = min(lim, v + 0.01)
            if not ok(u, nv):
                break
            v = nv
        return v
    half = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.69, 0.75, 0.78, 0.80, 0.84, 0.90, 0.97]
    us = [-x for x in reversed(half[1:])] + half
    ends = [v_end(u) for u in us]
    tv = [0, 0.05, 0.15, 0.27, 0.39, 0.51, 0.63, 0.75, 0.86, 0.95, 1.0]
    hem = lambda u: -0.70 - 0.05 * (0.5 + 0.5 * math.cos(2 * math.pi * u / 0.48))
    G = [[(u, lerp(hem(u), ve, t)) for u, ve in zip(us, ends)] for t in tv]

    def cth(j, i, u, v):
        t = 0.045
        if j >= len(tv) - 2:
            t += 0.028          # rolled collar
        if j <= 1:
            t += 0.018          # weighted hem
        return t
    cp = Comp(bevel=0.012, segs=1, angle=34)
    shell(cp, wc, G, cth, lift=lambda j, i, u, v: cape_lift(u, v, wc), mat=CRM, flush=False, inner_mat=CRM)
    comps.append(cp)
    # bronze disc clasps on top of each shoulder, tipped toward the front
    cl = Comp(bevel=0.006, segs=2, angle=30)
    for u in (-0.885, 0.885):
        v = wc.top0 + 0.36
        P, N = wc(u, v)
        disc(cl, P + N * (cape_lift(u, v, wc) + 0.06), Vector((0, -0.6, 0.8)), 0.085, 0.04)
    comps.append(cl)
    return comps


# ----- LowerTorso: belt, lambda boss, pteruges ------------------------------------
def build_lower_torso():
    comps = []
    for side in (-1, 1):
        undersuit_box(comps, lt_chart(side, SUIT_CL), [-0.99, 0, 0.99], [-0.2, 0.0, 0.2])
        ch = lt_chart(side)
        belt = Comp(bevel=0.01, segs=1, angle=32)
        us = [-0.985 + 1.97 * i / 10 for i in range(11)]
        shell(belt, ch, grid(us, (0.0, 0.018, 0.157, 0.175)), lambda j, i, u, v: 0.058 + (0.01 if j in (1, 2) else 0.0),
              mat=LTH, det_fn=lambda j, i, u, v: (j / 3, i / 10, 0.4, 0.45))
        comps.append(belt)
        st = Comp(shade="smooth")
        for x in ((-0.84, -0.60, -0.36, 0.36, 0.60, 0.84) if side < 0 else ()):
            P, N = ch(x, 0.08)
            rivet(st, P + N * 0.066, N, r=0.03, h=0.022)
        # pteruges: four strips a side, flaring 0.07 -> 0.14 away from the thighs
        sc = Comp(bevel=0.009, segs=1, angle=34)
        for sgn in (1, -1):
            x0, x1 = (0.035, 0.97) if sgn > 0 else (-0.97, -0.035)
            pitch = (x1 - x0) / 4
            for k in range(4):
                a = x0 + pitch * k + 0.008
                b = a + pitch - 0.016
                lf = lambda v: 0.02 + 0.12 * (0.03 - v) / 0.59
                strip(sc, ch, a, b, 0.03, -0.56, lf, 0.034, rows=(0.0, 0.55, 0.88, 1.0))
                if side < 0:
                    P, N = ch((a + b) / 2, -0.42)
                    rivet(st, P + N * (lf(-0.42) + 0.034), N, r=0.028, h=0.02)
        comps += [sc, st]
    # buckle: a bronze boss with a small painted lambda
    bk = Comp(bevel=0.006, segs=2, angle=30)
    P, N = lt_chart(-1)(0.0, 0.08)
    X, Y, N, F = disc(bk, P + N * 0.064, N, 0.095, 0.034, up=UP)
    comps.append(bk)
    em = Comp(shade="flat")
    for sgn in (-1, 1):
        foot = Vector((sgn * 0.046, -0.052))
        apex = Vector((0.0, 0.056))
        d = apex - foot
        mid = (apex + foot) / 2
        dx = (X * d.x + Y * d.y).normalized()
        slab(em, F + X * mid.x + Y * mid.y, dx, N.cross(dx).normalized(), N, d.length / 2, 0.012, 0.006, EMB)
    comps.append(em)
    return comps


# ----- Arms --------------------------------------------------------------------
def build_upper_arm():
    comps = []
    su = limb_chart(r=0.1, clear=SUIT_CL)
    undersuit_box(comps, su, limb_cols(su), [-0.58, -0.30, -0.05, 0.3, 0.56])
    # rounded bronze shoulder dome with a raised ring and rolled rims
    ss = [0.0, 0.08, 0.24, 0.40, 0.5, 0.545, 0.59, 0.72, 0.86, 0.95, 1.0]
    ts = [-1.4 + 2.8 * i / 12 for i in range(13)]
    G = [[(s * PD_SU, t * PD_TV) for t in ts] for s in ss]

    def th(j, i, u, v):
        s = u / PD_SU
        t_ = 0.05 + 0.032 * max(0.0, 1 - abs(s - 0.545) / 0.05)
        if j >= len(ss) - 2:
            t_ += 0.03
        if j <= 1:
            t_ += 0.016
        if i <= 1 or i >= len(ts) - 2:
            t_ += 0.02
        return t_
    d = Comp(bevel=0.014, segs=2, angle=30)
    shell(d, pd_chart, G, th, mat=BRZ)
    comps.append(d)
    # leather arm band and a row of pteruges under the dome
    lc = limb_chart(r=0.1)
    L = lc.stations
    u0, u1 = L["front_mid"] - 0.05, L["back_mid"] + 0.05
    bd = Comp(bevel=0.008, segs=1, angle=34)
    shell(bd, lc, [[(lerp(u0 - 0.03, u1 + 0.03, i / 16), v) for i in range(17)] for v in (-0.04, -0.025, 0.065, 0.08)],
          lambda j, i, u, v: 0.05, lift=lambda j, i, u, v: 0.004, mat=LTH,
          det_fn=lambda j, i, u, v: (j / 3, i / 16, 0.3, 0.45))
    comps.append(bd)
    sc = Comp(bevel=0.009, segs=1, angle=34)
    stud = Comp(shade="smooth")
    n = 8
    pitch = (u1 - u0) / n
    lf = lambda v: 0.012 + 0.07 * smooth((-0.04 - v) / 0.33)
    for k in range(n):
        a = u0 + pitch * k + 0.01
        b = a + pitch - 0.02
        strip(sc, lc, a, b, -0.02, -0.37, lf, 0.03, rows=(0.0, 0.55, 0.88, 1.0))
    comps.append(sc)
    return comps


def build_lower_arm():
    comps = []
    lc = limb_chart(r=0.1)
    L = lc.stations
    nu = 12
    us = [0.02 + (L["total"] - 0.04) * i / nu for i in range(nu + 1)]

    def z_hi(u):
        p, _ = lc(u, 0)
        if p.y < -0.3:                                   # front: below the elbow joint
            return 0.06 + 0.10 * max(0.0, 1 - abs(p.x - 0.1) / 0.4)
        return lerp(0.10, 0.18 + 0.06 * max(0.0, 1 - abs(p.x) / 0.45), smooth((p.y + 0.3) / 0.8))
    tvs = [0.0, 0.06, 0.12, 0.35, 0.65, 0.88, 0.94, 1.0]
    G = [[(u, lerp(-0.46, z_hi(u), t)) for u in us] for t in tvs]

    def th(j, i, u, v):
        p, _ = lc(u, 0)
        ridge = 0.03 * max(0.0, 1 - abs(p.y) / 0.25) if p.x > 0.45 else 0.0
        return 0.055 + ridge + (0.022 if j <= 1 else 0.0) + (0.02 if j >= 6 else 0.0)
    c = Comp(bevel=0.013, segs=2, angle=30)
    shell(c, lc, G, th, lift=lambda j, i, u, v: 0.05 * (1 - tvs[j] / 0.35) ** 2 if tvs[j] < 0.35 else 0.0, mat=BRZ)
    comps.append(c)
    return comps


# ----- Legs ----------------------------------------------------------------------
def build_upper_leg():
    comps = []
    su = limb_chart(r=0.1, clear=SUIT_CL)
    undersuit_box(comps, su, limb_cols(su), [-0.60, -0.30, -0.05, 0.2, 0.40])
    lc = limb_chart(r=0.1)
    L = lc.stations
    cols = limb_cols(lc)
    c = Comp(bevel=0.009, segs=1, angle=34)
    shell(c, lc, grid(cols, (-0.17, -0.15, -0.01, 0.01)), lambda j, i, u, v: 0.04 + (0.008 if j in (1, 2) else 0.0),
          mat=LTH, det_fn=lambda j, i, u, v: (j / 3, i / 16, 0.6, 0.3))
    comps.append(c)
    b = Comp(bevel=0.006, segs=2, angle=30)
    P, N = lc(L["outer_mid"], -0.08)
    disc(b, P + N * 0.044, N, 0.07, 0.032, up=UP)
    comps.append(b)
    st = Comp(shade="smooth")
    for u in (0.3, 0.75, L["back_mid"] - 0.25, L["back_mid"] + 0.2):
        P, N = lc(u, -0.08)
        rivet(st, P + N * 0.046, N, r=0.026, h=0.018)
    comps.append(st)
    return comps


def build_greave():
    comps = []
    lc = limb_chart(r=0.1)
    L = lc.stations
    nu = 14
    us = [0.025 + (L["back_in"] - 0.05) * i / nu for i in range(nu + 1)]

    def z_hi(u):
        p, _ = lc(u, 0)
        if p.y < -0.3:
            return 0.46 - 0.10 * (abs(p.x) / 0.5) ** 2
        return lerp(0.36, 0.05, smooth((p.y + 0.3) / 0.75))
    tv = [0.0, 0.05, 0.1, 0.22, 0.36, 0.5, 0.63, 0.75, 0.86, 0.93, 1.0]
    G = [[(u, lerp(-0.26, z_hi(u), t)) for u in us] for t in tv]

    def th(j, i, u, v):
        p, _ = lc(u, 0)
        t = 0.05
        if p.y < -0.3:
            t += 0.022 * max(0.0, 1 - abs(p.x) / 0.22)               # shin ridge
            t += 0.07 * bump(p.x, v, 0.0, 0.33, 0.38, 0.15)          # knee dome
        t += 0.065 * bump(u, v, L["back_mid"] - 0.12, -0.04, 0.42, 0.2)   # calf
        t += 0.03 * bump(u, v, L["corner_ob"], -0.02, 0.3, 0.18)
        if j <= 1 or j >= len(tv) - 2:
            t += 0.02                                                 # rolled edges
        return t
    c = Comp(bevel=0.014, segs=2, angle=30)
    shell(c, lc, G, th, lift=lambda j, i, u, v: 0.012 * (1 - tv[j]) ** 2, mat=BRZ)
    comps.append(c)
    return comps


# ----- Boots ---------------------------------------------------------------------
def build_sandal_cuff():
    comps = []
    lc = limb_chart(r=0.1)
    L = lc.stations
    cols = limb_cols(lc)
    band = Comp(bevel=0.008, segs=1, angle=34)
    shell(band, lc, grid(cols, (-0.33, -0.315, -0.265, -0.25)), lambda j, i, u, v: 0.036 + (0.008 if j in (1, 2) else 0.0),
          mat=LTH, det_fn=lambda j, i, u, v: (j / 3, i / 16, 0.2, 0.4))
    comps.append(band)
    sa, sb = Comp(bevel=0.006, segs=1, angle=40), Comp(bevel=0.006, segs=1, angle=40)
    n = 5
    span = L["back_in"] - 0.06
    for k in range(n):
        c0 = 0.03 + span * (k + 0.5) / n
        hw = span / n * 0.42
        strap(sa, lc, (c0 - hw, -0.33), (c0 + hw, -0.50), 0.066, 0.024)
        strap(sb, lc, (c0 + hw, -0.33), (c0 - hw, -0.50), 0.066, 0.024,
              lift_fn=lambda t: 0.006 + 0.026 * (1 - abs(2 * t - 1)) ** 0.6)
    comps += [sa, sb]
    ank = Comp(bevel=0.006, segs=1, angle=40)
    shell(ank, lc, grid(cols, (-0.525, -0.475)), 0.03, lift=lambda j, i, u, v: 0.03, mat=LTH,
          det_fn=lambda j, i, u, v: (j, i / 16, 0.7, 0.4))
    comps.append(ank)
    return comps


def build_foot():
    comps = []
    fc = limb_chart(hx=0.5, hy=0.5, r=0.1)
    L = fc.stations
    cols = limb_cols(fc)
    sole = Comp(bevel=0.01, segs=1, angle=34)
    shell(sole, fc, grid(cols, (-0.15, -0.135, -0.09, -0.075)), lambda j, i, u, v: 0.042 + (0.01 if j in (1, 2) else 0.0),
          mat=LTH, det_fn=lambda j, i, u, v: (j / 3, i / 16, 0.3, 0.85))
    comps.append(sole)
    # bronze toe plate over the front of the foot, rolled top edge
    tc = Comp(bevel=0.012, segs=2, angle=30)
    ft = torso_chart(-1, hx=0.5, hy=0.5, hz=0.15, rc=0.08)
    xs = [-0.46 + 0.93 * i / 8 for i in range(9)]
    vend = 0.075
    vs = [-0.068, -0.05, -0.005, 0.035, vend - 0.022, vend]
    shell(tc, ft, grid(xs, vs),
          lambda j, i, u, v: 0.048 + 0.022 * (1 - ((u - 0.005) / 0.47) ** 2) + (0.018 if j >= 4 else 0.0) + (0.012 if j == 0 else 0.0),
          lift=lambda j, i, u, v: 0.012, mat=BRZ)
    comps.append(tc)
    # heel strap and a criss-cross on the outer side
    st = Comp(bevel=0.006, segs=1, angle=40)
    shell(st, fc, [[(lerp(L["outer_mid"], L["back_in"] - 0.03, i / 8), v) for i in range(9)] for v in (-0.05, 0.03)],
          0.026, lift=lambda j, i, u, v: 0.004, mat=LTH)
    strap(st, fc, (L["outer0"] - 0.06, -0.065), (L["outer_mid"] + 0.12, 0.075), 0.06, 0.022)
    strap(st, fc, (L["outer0"] - 0.06, 0.075), (L["outer_mid"] + 0.12, -0.065), 0.06, 0.022,
          lift_fn=lambda t: 0.006 + 0.026 * (1 - abs(2 * t - 1)) ** 0.6)
    comps.append(st)
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
        bs.inputs["Roughness"].default_value = 0.4 if i == BRZ else 0.75
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
    ("Legs", "LowerLeg", build_greave, True),
    ("Boots", "LowerLeg", build_sandal_cuff, True),
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
# Body proxy for previews, the bake's contact AO and pose checks (never exported)
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
# PAINTERLY BAKE: colour + icon lighting in one atlas per group, on unique UVs. Baked masks drive the
# paint: AO darkens overlaps and crevices (under strips and the cape), a cavity pass, and the Bevel
# node finds convex edges for painted edge highlights. Bronze shades to brown (never flat yellow) with
# a broad hammered gradient; shadows lean cool, highlights warm.
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
    return "legs"                       # greaves, thigh bands and sandals share one atlas


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

    def voronoi(self, scale):
        n = self.nt.nodes.new("ShaderNodeTexVoronoi")
        n.feature = "SMOOTH_F1"
        n.inputs["Scale"].default_value = scale
        self.nt.links.new(self.geo.outputs["Position"], n.inputs["Vector"])
        return n.outputs["Distance"]

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
    strokes = b.math("MULTIPLY_ADD", b.noise(5.0, 1.5, 0.5, 0.6, (1.0, 1.0, 3.2)), 0.07, -0.035)
    paint = b.math("ADD", patches, strokes)
    edge = b.math("MULTIPLY", b.bevel_edge(0.018), b.smoothstep(ao, 0.55, 0.9))
    glint = b.smoothstep(b.dot(Nrm, GLINT), 0.80, 0.97)
    rim = b.math("MAXIMUM", b.dot(Nrm, RIM), 0.0)
    edge_up = b.math("MULTIPLY", edge, b.math("MULTIPLY_ADD", sky, 0.5, 0.5))
    deep = b.math("SUBTRACT", 1.0, b.smoothstep(occl, 0.3, 0.75))

    def tint_shade(base, lo=(40, 22, 44), mid=(160, 140, 146), hi=(255, 244, 232)):
        sh = b.ramp(b.math("ADD", S, b.math("MULTIPLY", paint, 0.6)), [(0.0, lo), (0.5, mid), (1.0, hi)])
        return b.mix(1.0, base, sh, "MULTIPLY")

    if idx == BRZ:
        hammer = b.remap(b.voronoi(6.5), 0.0, 0.7, -0.035, 0.035)
        f = b.math("ADD", b.math("ADD", S, b.math("MULTIPLY", paint, 0.8)), hammer)
        col = b.ramp(f, [(0.0, (28, 14, 8)), (0.2, (62, 32, 14)), (0.4, (110, 60, 24)), (0.58, (156, 94, 38)),
                         (0.74, (196, 132, 58)), (0.88, (226, 172, 94)), (1.0, (246, 206, 140))])
        col = b.mix(b.math("MULTIPLY", glint, 0.34), col, (255, 214, 140), "ADD")
        col = b.mix(b.math("MULTIPLY", rim, 0.16), col, (40, 46, 74), "ADD")
        col = b.mix(b.math("MULTIPLY", deep, 0.35), col, (42, 30, 44))
        col = b.mix(b.math("MULTIPLY", edge_up, 0.55), col, (244, 200, 128))
    elif idx == CRM:
        base = b.ramp(b.math("ADD", b.noise(2.5, 1.0, 0.5, 0.3), b.math("MULTIPLY", paint, 1.2)),
                      [(0.2, (96, 14, 24)), (0.5, (150, 26, 34)), (0.8, (188, 46, 44))])
        base = b.mix(b.math("MULTIPLY", b.A, 0.55), base, (62, 8, 18))                       # crest grooves
        ridge = b.math("MULTIPLY", b.smoothstep(b.R, 0.55, 1.0), b.math("SUBTRACT", 1.0, b.A))
        base = b.mix(b.math("MULTIPLY", ridge, 0.28), base, (216, 72, 60))
        col = tint_shade(base, (40, 14, 40), (152, 122, 132), (255, 236, 224))
        col = b.mix(b.math("MULTIPLY", edge_up, 0.3), col, (240, 112, 92))
    elif idx == LTH:
        base = b.ramp(b.math("ADD", b.math("MULTIPLY_ADD", paint, 1.5, 0.35), b.math("MULTIPLY", b.B, 0.3)),
                      [(0.2, (64, 36, 18)), (0.5, (108, 64, 34)), (0.8, (146, 96, 54))])
        base = b.mix(b.math("MULTIPLY", b.R, 0.22), base, (156, 106, 62))
        base = b.mix(b.math("MULTIPLY", b.A, 0.6), base, (40, 24, 16))
        col = tint_shade(base, (40, 24, 36), (160, 138, 136), (255, 240, 226))
        col = b.mix(b.math("MULTIPLY", edge_up, 0.45), col, (206, 156, 104))
    elif idx == SUIT:
        base = b.ramp(b.math("ADD", b.noise(3.0, 1.0, 0.5, 0.3), paint),
                      [(0.25, (56, 20, 24)), (0.6, (82, 30, 32)), (0.9, (104, 40, 38))])
        col = tint_shade(base, (30, 18, 34), (146, 124, 132), (250, 236, 228))
    elif idx == EMB:
        base = b.ramp(b.math("ADD", b.noise(6.0, 1.0, 0.5, 0.2), paint), [(0.3, (150, 24, 32)), (0.7, (186, 40, 42))])
        col = tint_shade(base, (60, 20, 40), (190, 170, 170), (255, 244, 236))
    else:
        col = b.ramp(S, [(0.0, (12, 8, 10)), (1.0, (38, 26, 28))])
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
    scene.cycles.samples = BAKE_SAMPLES
    scene.render.bake.margin = 12
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
    report = {"set": SET, "rarity": "Epic", "blender_version": bpy.app.version_string,
              "authoring": "final Roblox stud size; import at 1:1, do not scale", "pieces": {}}
    install = {"set": SET, "glow_color_srgb": None, "glow_material": None, "helmet": "full",
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
PV = ROOT / "previews"
OUT = Path(os.environ.get("QDIR") or (PV / "quick")) if QUICK else PV
OUT.mkdir(parents=True, exist_ok=True)
RES = (500, 600) if QUICK else (1000, 1200)


def setup_preview_scene():
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = RES
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
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam


def shoot(name, loc, target=(0, 0, 2.75), lens=70):
    cam.data.lens = lens
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    out = OUT / f"{name}.png"
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
shoot("close-helm", (3.2, -7.6, 5.5), target=(0, 0, 4.95), lens=100)

# ---------------------------------------------------------------------------
# Pose check (numeric only): rotate the proxy's part groups (body + armour) about their rig joints
# through the default R15 walk/run/jump extremes and count intersecting triangle pairs between
# armour on different parts and between armour and other parts of the body.
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
            n_arm = sum(len(x.overlap(y)) for x in groups[a]["armor"] for y in groups[b]["armor"]) if a < b else 0
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
        log("pose", pname, sum(clip[pname].values()), "tri pairs",
            sorted(clip[pname].items(), key=lambda kv: -kv[1])[:5])
    apply_pose({})
    if not QUICK:
        (ROOT / "pose-check.json").write_text(json.dumps(
            {"method": "part groups rotated about their rig joints (Blender); counts are intersecting triangle pairs",
             "poses_deg": {"walk": "arms +-35, elbows 20, legs +-35, back knee 35",
                           "run": "arms +-60, elbows 45, legs 55/60, back knee 85",
                           "jump": "arms raised 150 forward + 12 out, knees 15-30",
                           "fall": "arms raised 75 out to the sides"},
             "totals": {k: sum(v.values()) for k, v in clip.items()},
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


def compose(path, rows, cell_w, gap=12, bg=(0.93, 0.94, 0.96)):
    placed, y, W = [], 0, 0
    for row in rows:
        row = [r for r in row if Path(r[0]).exists()]
        if not row:
            continue
        hs = max(int(cell_w * asp) for _, asp in row)
        x = gap
        for p, asp in row:
            w_, h_ = cell_w, int(cell_w * asp)
            placed.append((p, x, y + gap, w_, h_))
            x += w_ + gap
        W = max(W, x)
        y += hs + gap
    H = y + gap
    sheet = np.ones((H, W, 4), np.float32)
    sheet[:, :, 0], sheet[:, :, 1], sheet[:, :, 2] = bg
    for p, x, y0, w_, h_ in placed:
        top = H - y0 - h_
        sheet[top:top + h_, x:x + w_, :] = load_px(p, w_, h_)
    img = bpy.data.images.new("sheet", W, H, alpha=False)
    img.pixels.foreach_set(sheet.ravel())
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    log("sheet", path, W, H)


tall = 1.2
compose(OUT / "sheet.png", [[(OUT / "front.png", tall), (OUT / "threeq.png", tall), (OUT / "side.png", tall)],
                            [(OUT / "back.png", tall), (OUT / "close-helm.png", tall)]], 460 if not QUICK else 340)

if not QUICK:
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / f"{SET}.blend"))
log("DONE")
