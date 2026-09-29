"""Dragon Scale armor set (Legendary style sample), fitted to the normalized R15 body.

Run (background Blender 5.2, never the user's open scene):
  blender -b --factory-startup --threads 4 --python build_armor.py
Env:
  QUICK=1   flat preview colours, no bake and no exports (fast shape passes)

Every piece is modelled at final Roblox stud size around the real R15 body that
AvatarNormalizer gives every player (r15-proxy/*.obj, measured in Studio 2026-09-28).
One rigid mesh per R15 part it covers, so each welds to that part and moves with it.

Blender axes: +z up, -y = the character's front, +x = the character's LEFT.
Studio axes = (-x, z, y) of Blender (same as the chest kit).
"""
import bpy, bmesh, math, json, os, random
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SET = "dragon-scale"
PREFIX = "DragonScale"
QUICK = os.environ.get("QUICK") == "1"
BAKE_SIZE = 1024
for d in ("exports/fbx", "exports/glb", "textures", "previews"):
    (ROOT / d).mkdir(parents=True, exist_ok=True)
random.seed(7)

# ---------------------------------------------------------------------------
# The measured body
# ---------------------------------------------------------------------------
PARTS = ["LowerTorso", "UpperTorso", "LeftUpperArm", "LeftLowerArm", "LeftHand", "RightUpperArm",
         "RightLowerArm", "RightHand", "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "RightUpperLeg",
         "RightLowerLeg", "RightFoot"]
HEAD_SIZE = Vector((1.1962, 1.2029, 1.1979))       # Studio; the head mesh can't be read (permissions)
HEAD_NECK_ATT = Vector((0, -0.586, 0))             # Head.NeckRigAttachment (Studio, measured)


def s2b(v):
    return Vector((-v[0], v[2], v[1]))


def load_obj(name):
    verts, faces, atts, size = [], [], {}, None
    for line in open(ROOT / "r15-proxy" / f"{name}.obj"):
        p = line.split()
        if line.startswith("# att"):
            atts[p[2]] = Vector((float(p[3]), float(p[4]), float(p[5])))
        elif line.startswith("# ") and " size " in line:
            size = Vector((float(p[3]), float(p[4]), float(p[5])))
        elif line.startswith("v "):
            verts.append((float(p[1]), float(p[2]), float(p[3])))
        elif line.startswith("f "):
            faces.append([int(i) - 1 for i in p[1:]])
    return {"verts": verts, "faces": faces, "atts": atts, "size": size}


BODY = {n: load_obj(n) for n in PARTS}
# Rest pose (Studio, relative to HumanoidRootPart) from the rig attachments.
REST = {"LowerTorso": Vector((0, -1, 0)) - BODY["LowerTorso"]["atts"]["RootRigAttachment"]}


def link(parent, child, att):
    REST[child] = REST[parent] + BODY[parent]["atts"][att] - BODY[child]["atts"][att]


link("LowerTorso", "UpperTorso", "WaistRigAttachment")
for s in ("Left", "Right"):
    link("UpperTorso", s + "UpperArm", s + "ShoulderRigAttachment")
    link(s + "UpperArm", s + "LowerArm", s + "ElbowRigAttachment")
    link(s + "LowerArm", s + "Hand", s + "WristRigAttachment")
    link("LowerTorso", s + "UpperLeg", s + "HipRigAttachment")
    link(s + "UpperLeg", s + "LowerLeg", s + "KneeRigAttachment")
    link(s + "LowerLeg", s + "Foot", s + "AnkleRigAttachment")
REST["Head"] = REST["UpperTorso"] + BODY["UpperTorso"]["atts"]["NeckRigAttachment"] - HEAD_NECK_ATT
HRP_HEIGHT = 3.0                                    # HipHeight 2 + half the root part


def part_pos(name):
    """Blender world position of a body part's centre at rest (feet on z = 0)."""
    return s2b(REST[name]) + Vector((0, 0, HRP_HEIGHT))


# ---------------------------------------------------------------------------
# Materials. Bake inputs; the finished set uses one baked atlas.
# ---------------------------------------------------------------------------
MAT_NAMES = ["Scale", "Plate", "Gold", "Ivory", "Dark", "Belly", "Hide"]
SCALE, PLATE, GOLD, IVORY, DARK, BELLY, HIDE = range(7)
FLAT = {  # sRGB: the colour each surface reads as before lighting
    SCALE: (184, 36, 40),      # crimson scales: the set's signature colour
    PLATE: (66, 20, 28),       # dark dragon-hide plates underneath (painted scales in the bake)
    GOLD: (222, 166, 64),      # trim on the main plates only
    IVORY: (234, 220, 188),    # horns, spikes, claws, fangs
    DARK: (34, 20, 24),        # insides
    BELLY: (208, 138, 58),     # bronze belly scutes
    HIDE: (176, 34, 40),       # big crimson plates, painted scales in the bake
}
GLOW = (255, 132, 30)                                # Neon (Studio Color), molten amber


def lin(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgba(c):
    return (lin(c[0]), lin(c[1]), lin(c[2]), 1.0)


def make_materials():
    mats = []
    for i, name in enumerate(MAT_NAMES):
        m = bpy.data.materials.new(f"{PREFIX}_{name}")
        m.use_nodes = True
        bs = m.node_tree.nodes["Principled BSDF"]
        bs.inputs["Base Color"].default_value = rgba(FLAT[i])
        bs.inputs["Roughness"].default_value = 0.55 if i == GOLD else 0.75
        mats.append(m)
    g = bpy.data.materials.new(f"{PREFIX}_Glow")
    g.use_nodes = True
    bs = g.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = (0, 0, 0, 1)
    bs.inputs["Emission Color"].default_value = rgba(GLOW)
    bs.inputs["Emission Strength"].default_value = 4.0
    return mats, g


# ---------------------------------------------------------------------------
# Geometry helpers (all write into a bmesh in part-local space)
# ---------------------------------------------------------------------------
CL = 0.025          # gap between the body and the inside of a plate


def grid_shell(bm, P, thick, *, wrap=False, out_hint=Vector((0, -1, 0)), mat_out=PLATE,
               mat_in=DARK, mat_rim=GOLD, bevel=0.018, seg=1, inner=True):
    """Plate from a grid of inner-surface points P[row][col], thickened outward, rim bevelled.
    Rim and bevel faces get mat_rim (gold trim by default)."""
    # Tag layer first: adding a layer later would invalidate face references held below.
    tag = bm.faces.layers.int.get("inner_face") or bm.faces.layers.int.new("inner_face")
    rows, cols = len(P), len(P[0])

    def at(j, i):
        i = i % cols if wrap else max(0, min(cols - 1, i))
        return P[max(0, min(rows - 1, j))][i]

    N = [[None] * cols for _ in range(rows)]
    for j in range(rows):
        for i in range(cols):
            n = (at(j, i + 1) - at(j, i - 1)).cross(at(j + 1, i) - at(j - 1, i))
            N[j][i] = n.normalized() if n.length > 1e-9 else Vector((0, 0, 1))
    jm, im = rows // 2, cols // 2
    hint = out_hint(P[jm][im]) if callable(out_hint) else out_hint
    sign = 1.0 if N[jm][im].dot(hint) >= 0 else -1.0
    iv = [[bm.verts.new(P[j][i]) for i in range(cols)] for j in range(rows)]
    outer = [[bm.verts.new(P[j][i] + N[j][i] * sign * thick) for i in range(cols)] for j in range(rows)]
    fo, fi, fr = [], [], []
    ucount = cols if wrap else cols - 1
    for j in range(rows - 1):
        for i in range(ucount):
            i2 = (i + 1) % cols
            q = [outer[j][i], outer[j][i2], outer[j + 1][i2], outer[j + 1][i]]
            qi = [iv[j][i], iv[j][i2], iv[j + 1][i2], iv[j + 1][i]]
            fo.append(bm.faces.new(q if sign > 0 else q[::-1]))
            fi.append(bm.faces.new(qi[::-1] if sign > 0 else qi))

    def rim(a, b, c, d):
        fr.append(bm.faces.new([a, b, c, d]))

    for i in range(ucount):
        i2 = (i + 1) % cols
        rim(iv[0][i], iv[0][i2], outer[0][i2], outer[0][i])
        rim(iv[-1][i2], iv[-1][i], outer[-1][i], outer[-1][i2])
    if not wrap:
        for j in range(rows - 1):
            rim(iv[j + 1][0], iv[j][0], outer[j][0], outer[j + 1][0])
            rim(iv[j][-1], iv[j + 1][-1], outer[j + 1][-1], outer[j][-1])
    allf = fo + fi + fr
    bmesh.ops.recalc_face_normals(bm, faces=allf)
    for f in fo:
        f.material_index = mat_out
    for f in fi:
        f.material_index = mat_in
        f[tag] = 0 if inner else 1
    for f in fr:
        f.material_index = mat_rim
    if bevel > 0:
        outset = set(fo)
        edges = {e for f in fr for e in f.edges if any(lf in outset for lf in e.link_faces)}
        res = bmesh.ops.bevel(bm, geom=list(edges), offset=bevel, offset_type="OFFSET", segments=seg,
                              profile=0.5, affect="EDGES", clamp_overlap=True)
        for f in res["faces"]:
            f.material_index = mat_rim
    if not inner:            # flush on the body: nobody can ever see the inside, so drop it
        bm.faces.ensure_lookup_table()
        doomed = [f for f in bm.faces if f[tag] == 1]
        bmesh.ops.delete(bm, geom=doomed, context="FACES_ONLY")
    return fo


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def hem_wave(t, count):
    """0 at the cusps, 1 at each tip: `count` rounded-point tips across t in [0, 1]."""
    f = (t * count) % 1.0
    return max(0.0, 1.0 - abs(2 * f - 1) ** 1.3)


def superellipse(u, v, n):
    """Square (u, v) in [-1, 1]^2 onto a rounded rectangle; n higher = squarer corners."""
    m = max(abs(u), abs(v))
    if m < 1e-9:
        return 0.0, 0.0
    r = (abs(u) ** n + abs(v) ** n) ** (1.0 / n)
    return u * m / r, v * m / r


def front_plate(bm, x0, x1, z0, z1, depth, *, side=-1, bulge=0.04, bulge_v=0.35, nu=7, nv=5, n=5.0,
                thick=0.06, zfun=None, xfun=None, hem=None, **kw):
    """Plate on a body face that points along y (side=-1 front, +1 back). depth = inner surface
    distance from the part centre. zfun(t_u) -> (z0, z1) lets the top/bottom edges vary;
    xfun(t_v) -> (x0, x1) lets the sides vary (kite and shield shapes)."""
    P = []
    for j in range(nv + 1):
        row = []
        for i in range(nu + 1):
            u, v = -1 + 2 * i / nu, -1 + 2 * j / nv
            uu, vv = superellipse(u, v, n)
            tu, tv = (uu + 1) / 2, (vv + 1) / 2
            a, b = zfun(tu) if zfun else (z0, z1)
            xa, xb = xfun(tv) if xfun else (x0, x1)
            x = lerp(xa, xb, tu)
            z = lerp(a, b, tv)
            if hem:                      # pointed scale-like tips along the bottom edge
                z -= hem[1] * hem_wave(tu, hem[0]) * (1 - tv) ** 2
            y = side * (depth + bulge * (1 - uu * uu) * (1 - bulge_v * vv * vv))
            row.append(Vector((x, y, z)))
        P.append(row)
    return grid_shell(bm, P, thick, out_hint=Vector((0, side, 0)), **kw)


def band_path(hx, hy, r, sides, clear, steps=3):
    """Points and outward normals around a box cross-section (x-y), fillet radius r, covering the
    listed faces in order, e.g. ('front', 'outer', 'back') for a left limb (outer = +x)."""
    pts = []
    cx, cy = hx - r, hy - r
    seq = {"front": ((-hx, -hy), (cx, -hy)), "outer": ((hx, -cy), (hx, cy)), "back": ((cx, hy), (-hx, hy))}
    corners = {("front", "outer"): (Vector((cx, -cy)), -90, 0), ("outer", "back"): (Vector((cx, cy)), 0, 90)}
    for k, s in enumerate(sides):
        a, b = seq[s]
        for t in range(steps + (0 if k + 1 < len(sides) else 1)):
            f = t / steps
            p = Vector((lerp(a[0], b[0], f), lerp(a[1], b[1], f)))
            nrm = {"front": Vector((0, -1)), "outer": Vector((1, 0)), "back": Vector((0, 1))}[s]
            pts.append((p + nrm * clear, nrm))
        if k + 1 < len(sides):
            c, a0, a1 = corners[(s, sides[k + 1])]
            for t in range(4):
                ang = math.radians(lerp(a0, a1, t / 4))
                nrm = Vector((math.cos(ang), math.sin(ang)))
                pts.append((c + nrm * (r + clear), nrm))
    return pts


def band(bm, hx, hy, r, sides, z_lo, z_hi, *, clear=CL, flare_lo=0.0, flare_hi=0.0, nv=4, thick=0.06, steps=3, **kw):
    """Plate wrapped around a limb's faces. z_lo/z_hi may be callables of (path fraction, point)."""
    path = band_path(hx, hy, r, sides, clear, steps)
    acc = [0.0]
    for k in range(1, len(path)):
        acc.append(acc[-1] + (path[k][0] - path[k - 1][0]).length)
    P = []
    for j in range(nv + 1):
        tv = j / nv
        row = []
        for i, (p, nrm) in enumerate(path):
            f = acc[i] / acc[-1]
            lo = z_lo(f, p) if callable(z_lo) else z_lo
            hi = z_hi(f, p) if callable(z_hi) else z_hi
            push = flare_lo * (1 - tv) ** 2 + flare_hi * tv ** 2
            q = p + nrm * push
            row.append(Vector((q.x, q.y, lerp(lo, hi, tv))))
        P.append(row)
    return grid_shell(bm, P, thick, out_hint=lambda q: Vector((q.x, q.y, 0)), **kw)


def tube(bm, pts, radii, sides=6, mat=IVORY, cap=True):
    """Tapered tube along a centreline (horns, spikes, claws, glowing bars). A radius of 0 ends in
    a point."""
    rings, nrm = [], None
    for k, p in enumerate(pts):
        t = (pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]).normalized()
        if nrm is None:
            a = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
            nrm = t.cross(a).normalized()
        else:
            nrm = (nrm - t * nrm.dot(t)).normalized()
        b = t.cross(nrm)
        if radii[k] <= 1e-5:
            rings.append([bm.verts.new(p)])
        else:
            rings.append([bm.verts.new(p + (nrm * math.cos(2 * math.pi * s / sides) + b * math.sin(2 * math.pi * s / sides)) * radii[k])
                          for s in range(sides)])
    faces = []
    for k in range(len(rings) - 1):
        A, B = rings[k], rings[k + 1]
        for s in range(sides):
            s2 = (s + 1) % sides
            if len(B) == 1:
                faces.append(bm.faces.new([A[s], A[s2], B[0]]))
            elif len(A) == 1:
                faces.append(bm.faces.new([A[0], B[s2], B[s]]))
            else:
                faces.append(bm.faces.new([A[s], A[s2], B[s2], B[s]]))
    if cap and len(rings[0]) > 1:
        faces.append(bm.faces.new(rings[0][::-1]))
    if len(rings[-1]) > 1:
        faces.append(bm.faces.new(rings[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    for f in faces:
        f.material_index = mat
    return faces


def arc_pts(p0, p1, bend, n=4):
    """Points from p0 to p1 bowed sideways by the vector `bend` at the middle."""
    return [p0.lerp(p1, t) + bend * math.sin(math.pi * t) for t in [k / n for k in range(n + 1)]]


def horn(bm, base, tip, bend, r0, sides=6, n=5, mat=IVORY):
    pts = arc_pts(base, tip, bend, n)
    radii = [r0 * (1 - (k / n)) ** 1.15 for k in range(n + 1)]
    return tube(bm, pts, radii, sides, mat)


# One scale: pointed at the bottom, rounded top, a keel ridge. Local: x across, z along the flow,
# -y outward. Open-backed (it always sits on a plate).
SCALE_OUT = [(0, 1.0), (0.96, 0.55), (1.0, 0.0), (0.86, -0.48), (0.5, -0.84), (0, -1.02),
             (-0.5, -0.84), (-0.86, -0.48), (-1.0, 0.0), (-0.96, 0.55)]
SCALE_TRIS = [("A", 1, 0), ("A", 2, 1), ("A", "B", 2), ("B", 3, 2), ("B", 4, 3), ("B", 5, 4),
              ("B", 6, 5), ("B", 7, 6), ("B", 8, 7), ("A", 8, "B"), ("A", 9, 8), ("A", 0, 9)]
SCALE_RIM = range(2, 8)      # the top tucks under the row above, so only the exposed edge gets a rim


def add_scale(bm, M, w, h, *, thick=0.022, ridge=0.014, curve=0.16, mat=SCALE):
    def L(x, z, y):
        return M @ Vector((x * w / 2, y + curve * x * x * w * 0.25, z * h / 2))

    front = [bm.verts.new(L(x, z, -thick)) for x, z in SCALE_OUT]
    back = [bm.verts.new(L(x, z, 0.0)) for x, z in SCALE_OUT]
    A = bm.verts.new(L(0, 0.3, -thick - ridge))
    B = bm.verts.new(L(0, -0.45, -thick - ridge * 0.8))
    key = {"A": A, "B": B}
    faces = [bm.faces.new([key[k] if isinstance(k, str) else front[k] for k in tri]) for tri in SCALE_TRIS]
    n = len(SCALE_OUT)
    for k in SCALE_RIM:
        k2 = (k + 1) % n
        faces.append(bm.faces.new([front[k], front[k2], back[k2], back[k]]))
    for f in faces:
        f.material_index = mat
    return faces


def surface_frame(pos, nrm, up_hint, tilt=14.0, lift=0.006):
    n = nrm.normalized()
    up = up_hint - n * up_hint.dot(n)
    if up.length < 1e-4:
        up = Vector((0, 1, 0)) - n * n.y
    up.normalize()
    right = up.cross(n).normalized()
    up = n.cross(right).normalized()
    R = Matrix(((right.x, -n.x, up.x), (right.y, -n.y, up.y), (right.z, -n.z, up.z)))
    T = R @ Matrix.Rotation(math.radians(-tilt), 3, "X")
    return Matrix.Translation(pos + n * lift) @ T.to_4x4()


def scale_rows(bm, bvh, rays, w, h, up_hint=Vector((0, 0, 1)), tilt=14.0, **kw):
    """rays: iterable of (origin, direction). Each hit on the piece so far gets one scale."""
    placed = 0
    for ray in rays:
        origin, direction = ray[0], ray[1]
        hit, nrm, _, _ = bvh.ray_cast(origin, direction.normalized(), 4.0)
        if hit is None:
            continue
        if nrm.dot(direction) > 0:
            nrm = -nrm
        uh = ray[2] if len(ray) > 2 else (up_hint(hit) if callable(up_hint) else up_hint)
        add_scale(bm, surface_frame(hit, nrm, uh, tilt), w, h, **kw)
        placed += 1
    return placed


def grid_rays(xs_rows, zs, y_from, direction):
    """Front/back-facing scale rows: xs_rows[k] are the x positions of row k at height zs[k]."""
    for xs, z in zip(xs_rows, zs):
        for x in xs:
            yield Vector((x, y_from, z)), direction


def staggered(x0, x1, count, row):
    step = (x1 - x0) / count
    off = step / 2 if row % 2 else 0.0
    n = count + (0 if row % 2 else 1)
    return [x0 + off + step * i for i in range(n) if x0 - 1e-6 <= x0 + off + step * i <= x1 + 1e-6]


def gem(bm, center, nrm, up, w, h, depth, sides=8):
    """Faceted almond/cabochon for Neon: a ring plus a raised centre, flat back."""
    n = nrm.normalized()
    up = (up - n * up.dot(n)).normalized()
    rt = up.cross(n).normalized()
    ring = [bm.verts.new(center + rt * (math.cos(a) * w / 2) + up * (math.sin(a) * h / 2))
            for a in [2 * math.pi * s / sides for s in range(sides)]]
    mid = [bm.verts.new(center + n * depth * 0.7 + rt * (math.cos(a) * w / 4) + up * (math.sin(a) * h / 4))
           for a in [2 * math.pi * (s + 0.5) / sides for s in range(sides)]]
    top = bm.verts.new(center + n * depth)
    faces = []
    for s in range(sides):
        s2 = (s + 1) % sides
        faces.append(bm.faces.new([ring[s], ring[s2], mid[s]]))
        faces.append(bm.faces.new([mid[s], ring[s2], mid[s2]]))
        faces.append(bm.faces.new([mid[s], mid[s2], top]))
    faces.append(bm.faces.new(ring[::-1]))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def bezel(bm, center, nrm, up, w, h, width=0.035, depth=0.03, sides=10, mat=GOLD):
    """Gold ring around a gem."""
    n = nrm.normalized()
    up = (up - n * up.dot(n)).normalized()
    rt = up.cross(n).normalized()
    P = []
    for j, (sw, lift) in enumerate(((w / 2 + width, 0.0), (w / 2 + width * 0.45, depth), (w / 2, depth * 0.6))):
        sh = sw * h / w
        P.append([center + n * lift + rt * (math.cos(a) * sw) + up * (math.sin(a) * sh)
                  for a in [2 * math.pi * s / sides for s in range(sides)]])
    verts = [[bm.verts.new(p) for p in row] for row in P]
    faces = []
    for j in range(len(verts) - 1):
        for s in range(sides):
            s2 = (s + 1) % sides
            faces.append(bm.faces.new([verts[j][s], verts[j][s2], verts[j + 1][s2], verts[j + 1][s]]))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    for f in faces:
        f.material_index = mat
    return faces


def mirror_bm(bm):
    """Copy of a left-side piece for the right side (mirror across x)."""
    m = bm.copy()
    bmesh.ops.scale(m, vec=Vector((-1, 1, 1)), verts=m.verts)
    bmesh.ops.reverse_faces(m, faces=m.faces)
    return m


# ---------------------------------------------------------------------------
# The pieces. Each builder returns (armour bmesh, glow bmesh) in the part's local space.
# Look (RARITY_GODLY_ARMOR.md section 13, Legendary): dark dragon-hide plates carry painted
# scales; modelled crimson scales sit on the chest, back, shoulders and shins; plate edges end in
# pointed scale-like hems instead of straight lines; gold trims only the main plates; ivory horns
# and spikes; molten-amber Neon seams and eyes.
# ---------------------------------------------------------------------------
UP = Vector((0, 0, 1))
SEAM = 0.026          # glowing seam radius


def seam(gl, pts, r=SEAM):
    tube(gl, pts, [r] * len(pts), sides=4, mat=0)


def rows_of(z_list, x0, x1, count, keep=lambda x, z: True):
    rows, zs = [], []
    for r, z in enumerate(z_list):
        rows.append([x for x in staggered(x0, x1, count, r) if keep(x, z)])
        zs.append(z)
    return rows, zs


def build_upper_torso():
    bm, gl = bmesh.new(), bmesh.new()
    hx, hy, hz = 1.0, 0.5, 0.8
    for side in (-1, 1):   # dark hide base, front and back
        front_plate(bm, -0.985, 0.985, -0.80, 0.86, hy + CL, side=side, bulge=0.035, nu=8, nv=5, n=7,
                    thick=0.05, mat_out=PLATE, mat_rim=PLATE, bevel=0.012, inner=False)
    # Shoulder yoke: a ring from the neck opening out to the torso's top edge.
    P, nu, rows = [], 24, 2
    for j in range(rows + 1):
        t = j / rows
        row = []
        for i in range(nu):
            a = 2 * math.pi * i / nu
            c, s = math.cos(a), math.sin(a)
            ex, ey = superellipse(c, s, 8)
            outer = Vector((ex * (hx - 0.012), ey * (hy + CL + 0.02), 0))
            q = Vector((c * 0.56, s * 0.43, 0)).lerp(outer, t)
            q.z = hz + CL + 0.025 * math.sin(math.pi * t)
            row.append(q)
        P.append(row)
    grid_shell(bm, P, 0.06, wrap=True, out_hint=UP, mat_out=PLATE, mat_rim=PLATE, bevel=0.012, inner=False)
    P = [[Vector((math.cos(a) * rx, math.sin(a) * ry, z)) for a in [2 * math.pi * i / 20 for i in range(20)]]
         for rx, ry, z in ((0.56, 0.43, hz + CL + 0.03), (0.585, 0.455, hz + 0.15), (0.60, 0.47, hz + 0.18))]
    grid_shell(bm, P, 0.05, wrap=True, out_hint=lambda q: Vector((q.x, q.y, 0)), mat_out=GOLD, mat_rim=GOLD,
               mat_in=DARK, bevel=0.01, inner=False)

    base = hy + CL + 0.05
    # Pectorals: squared crimson plates, a shallow V below with scale-tip hems, gold rim.
    for sgn in (1, -1):
        xa, xb = (0.075, 0.975) if sgn > 0 else (-0.975, -0.075)

        def zf(t, sgn=sgn):
            c = t if sgn > 0 else 1 - t          # 0 at the centre line, 1 at the outer edge
            return lerp(0.04, 0.24, c), 0.89
        front_plate(bm, xa, xb, 0, 0, base + 0.005, side=-1, bulge=0.07, bulge_v=0.5, nu=6, nv=4, n=9,
                    thick=0.075, zfun=zf, hem=(3, 0.07), mat_out=HIDE, mat_rim=GOLD, bevel=0.02, inner=False)
        seam(gl, [Vector((sgn * x, -(base + 0.035), lerp(0.04, 0.24, x / 0.975) - 0.03)) for x in (0.1, 0.4, 0.7, 0.96)])
    for k, (za, zb) in enumerate(((-0.02, -0.21), (-0.20, -0.40), (-0.39, -0.59), (-0.58, -0.80))):
        half = lerp(0.36, 0.27, k / 3)
        front_plate(bm, -half, half, zb, za, base + 0.004 + 0.004 * k, side=-1, bulge=0.06, bulge_v=0.0,
                    nu=6, nv=2, n=6, thick=0.06, hem=(3, 0.035), mat_out=BELLY, mat_rim=GOLD, bevel=0.016, inner=False)
        y = -(base + 0.03)
        seam(gl, [Vector((-half * 0.9, y, zb + 0.004)), Vector((0, y - 0.035, zb - 0.01)), Vector((half * 0.9, y, zb + 0.004))])
    eye = Vector((0, -(base + 0.13), 0.47))
    bezel(bm, eye + Vector((0, 0.03, 0)), Vector((0, -1, 0)), UP, 0.24, 0.32, width=0.055, depth=0.05)
    gem(gl, eye, Vector((0, -1, 0)), UP, 0.24, 0.32, 0.065)
    tube(bm, [eye + Vector((0, -0.058, -0.11)), eye + Vector((0, -0.07, 0)), eye + Vector((0, -0.058, 0.11))],
         [0.0, 0.022, 0.0], sides=4, mat=DARK)
    tube(bm, [Vector((0, -(base + 0.04), 0.90)), Vector((0, -(base + 0.10), 0.72)), Vector((0, -(base + 0.1), 0.20)),
              Vector((0, -(base + 0.05), 0.02))], [0.05, 0.05, 0.05, 0.035], sides=4, mat=GOLD)
    # Back: crimson shoulder-blade plates, a glowing V, shingled scales, a spine of ivory spikes.
    for sgn in (1, -1):
        xa, xb = (0.06, 0.97) if sgn > 0 else (-0.97, -0.06)

        def zb(t, sgn=sgn):
            c = t if sgn > 0 else 1 - t
            return lerp(0.06, 0.28, c), 0.86
        front_plate(bm, xa, xb, 0, 0, base + 0.005, side=1, bulge=0.06, bulge_v=0.5, nu=6, nv=4, n=9,
                    thick=0.07, zfun=zb, hem=(3, 0.07), mat_out=HIDE, mat_rim=GOLD, bevel=0.02, inner=False)
        seam(gl, [Vector((sgn * x, base + 0.035, lerp(0.06, 0.28, x / 0.97) - 0.035)) for x in (0.1, 0.4, 0.7, 0.96)])
    bvh = BVHTree.FromBMesh(bm)
    rows, zs = rows_of((0.13, -0.06, -0.25, -0.44, -0.63), -0.99, 0.99, 6,
                       keep=lambda x, z: abs(x) > (0.43 if z < 0.0 else 0.66))
    scale_rows(bm, bvh, grid_rays(rows, zs, -2.0, Vector((0, 1, 0))), 0.37, 0.34, tilt=12)
    rows, zs = rows_of((-0.02, -0.20, -0.38, -0.56, -0.73), -0.99, 0.99, 6, keep=lambda x, z: abs(x) > 0.08)
    scale_rows(bm, bvh, grid_rays(rows, zs, 2.0, Vector((0, -1, 0))), 0.37, 0.35, tilt=12)
    for k, z in enumerate((0.70, 0.40, 0.08, -0.24, -0.54)):
        y = base + 0.07
        h = lerp(0.32, 0.16, k / 4)
        horn(bm, Vector((0, y - 0.05, z)), Vector((0, y + h, z + h * 0.6)), Vector((0, 0.02, -0.02)), 0.085 - 0.008 * k, sides=4, n=3)
    return bm, gl


def build_lower_torso():
    bm, gl = bmesh.new(), bmesh.new()
    hy = 0.5
    for side in (-1, 1):
        front_plate(bm, -0.99, 0.99, -0.2, 0.2, hy + CL, side=side, bulge=0.02, bulge_v=0.0, nu=8, nv=2, n=8,
                    thick=0.07, mat_out=PLATE, mat_rim=GOLD, bevel=0.014, inner=False)
    d = hy + CL + 0.07
    # Tassets over the thighs, front and back (not the sides: the hands hang there): a dark upper
    # lame and a crimson lower lame with pointed tips and a gold edge. Flared so a swinging thigh
    # passes underneath.
    for side in (-1, 1):
        bottom = -0.50 if side < 0 else -0.42
        for sgn in (1, -1):
            xa, xb = (0.07, 0.93) if sgn > 0 else (-0.93, -0.07)
            for za, zb2, mat, rim, extra, tips in ((0.08, bottom + 0.20, PLATE, PLATE, 0.0, 0),
                                                   (bottom + 0.26, bottom, HIDE, GOLD, 0.025, 2)):
                P = []
                nu, nv = (8 if tips else 4), 2
                for j in range(nv + 1):
                    tv = j / nv
                    row = []
                    for i in range(nu + 1):
                        tu = i / nu
                        z = lerp(zb2, za, tv)
                        if tips:
                            z -= 0.09 * hem_wave(tu, tips) * (1 - tv) ** 2
                        depth_t = max(0.0, min(1.0, (0.08 - z) / (0.08 - bottom)))
                        flare = 0.12 * depth_t ** 1.4 + extra
                        edge = 1 - (2 * tu - 1) ** 4
                        row.append(Vector((lerp(xa, xb, tu), side * (d - 0.01 + flare + 0.03 * edge), z)))
                    P.append(row)
                grid_shell(bm, P, 0.045, out_hint=Vector((0, side, 0)), mat_out=mat, mat_rim=rim, bevel=0.012)
    c = Vector((0, -(d + 0.03), 0.0))
    rings = []
    for sx, sz, lift in ((0.25, 0.20, 0.0), (0.22, 0.17, 0.05), (0.12, 0.10, 0.08)):
        rings.append([c + Vector((math.cos(a) * sx * (1.15 if math.sin(a) > 0 else 1.0), -lift, math.sin(a) * sz))
                      for a in [2 * math.pi * i / 6 + math.pi / 2 for i in range(6)]])
    verts = [[bm.verts.new(p) for p in row] for row in rings]
    faces = [bm.faces.new([verts[j][s], verts[j][(s + 1) % 6], verts[j + 1][(s + 1) % 6], verts[j + 1][s]])
             for j in range(2) for s in range(6)]
    faces += [bm.faces.new(verts[2]), bm.faces.new(verts[0][::-1])]
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    for f in faces:
        f.material_index = GOLD
    for sgn in (1, -1):
        horn(bm, c + Vector((sgn * 0.15, -0.03, 0.12)), c + Vector((sgn * 0.30, 0.0, 0.30)), Vector((sgn * 0.02, 0, 0)), 0.04, sides=5, n=3)
        gem(gl, c + Vector((sgn * 0.08, -0.08, 0.035)), Vector((sgn * 0.25, -1, 0.1)), UP, 0.08, 0.05, 0.022, sides=6)
    return bm, gl


def build_upper_arm():
    """Left pauldron (outer = +x): a domed crimson cap with shingled scales, pointed hems and a big
    horn, over two dark lames."""
    bm, gl = bmesh.new(), bmesh.new()
    hx, top = 0.5, 0.584

    def lame(z_top_inner, corner_r, z_bottom, off, y_half, thick, mat, rim, crown=0.0, swell=0.0, tips=3, tip_d=0.08, inner=True):
        prof = []
        cx, cz = hx - corner_r, z_top_inner - corner_r
        if z_top_inner > top:
            for t in (0.0, 0.35, 0.7):
                prof.append((Vector((lerp(-hx + 0.03, cx, t), z_top_inner + off)), Vector((0, 1))))
        for t in range(4):
            a = math.radians(lerp(90, 0, t / 3))
            n = Vector((math.cos(a), math.sin(a)))
            prof.append((Vector((cx, cz)) + n * (corner_r + off), n))
        for t in range(1, 3):
            prof.append((Vector((hx + off, lerp(cz, z_bottom, t / 2))), Vector((1, 0))))
        P = []
        nv = 2 * tips
        for j in range(nv + 1):
            v = -1 + 2 * j / nv
            cup = v ** 4
            row = []
            for k, (p, n) in enumerate(prof):
                q = p + n * (0.035 * (1 - cup) - 0.03 * cup)
                q = q + Vector((swell * (1 - v * v) * max(0.0, n.x), crown * (1 - v * v) * max(0.0, n.y)))
                z = q.y - 0.06 * cup
                if k == len(prof) - 1:           # pointed hem along the bottom edge
                    z -= tip_d * hem_wave((v + 1) / 2, tips)
                elif k == len(prof) - 2:
                    z -= tip_d * 0.25 * hem_wave((v + 1) / 2, tips)
                row.append(Vector((q.x, v * y_half, z)))
            P.append(row)
        return grid_shell(bm, P, thick, out_hint=lambda q: Vector((q.x + 0.2, 0, q.z - 0.2)), mat_out=mat,
                          mat_rim=rim, bevel=0.018, inner=inner)

    # Rerebrace: the upper arm's front, outer side and back down to just above the elbow, so the
    # shoulder shows no bare arm from the front. The inside of the elbow stays open for bending.
    band(bm, hx, 0.5, 0.14, ("front", "outer", "back"), lambda f, p: -0.29 - 0.05 * hem_wave(f, 5), 0.46,
         clear=0.02, nv=3, thick=0.04, steps=5, mat_out=PLATE, mat_rim=GOLD, bevel=0.012, inner=False)
    lame(-0.36, 0.14, -0.24, CL + 0.02, 0.545, 0.055, PLATE, GOLD, tip_d=0.07, inner=False)
    lame(-0.10, 0.16, 0.02, CL + 0.04, 0.56, 0.06, PLATE, PLATE, tip_d=0.07, inner=False)
    lame(top + 0.001, 0.34, 0.20, CL + 0.05, 0.595, 0.08, HIDE, GOLD, crown=0.13, swell=0.06, tip_d=0.10)
    seam(gl, [Vector((hx + 0.138, y, 0.105)) for y in (-0.5, -0.25, 0.0, 0.25, 0.5)])
    bvh = BVHTree.FromBMesh(bm)
    rays = []
    cxz = Vector((hx - 0.34, top + 0.021 - 0.34))
    for r, ang in enumerate((78, 52, 26)):
        a = math.radians(ang)
        n = Vector((math.cos(a), 0, math.sin(a)))
        up = Vector((-math.sin(a), 0, math.cos(a)))
        for y in staggered(-0.44, 0.44, 3, r):
            o = Vector((cxz.x, y, cxz.y)) + n * 2.0
            rays.append((o, -n, up))
    for y in staggered(-0.40, 0.40, 3, 1):
        rays.append((Vector((-0.12, y, 3.0)), Vector((0, 0, -1)), Vector((-1, 0, 0))))
    scale_rows(bm, bvh, rays, 0.33, 0.30, tilt=10)
    horn(bm, Vector((0.10, -0.02, top + 0.16)), Vector((0.52, 0.46, top + 0.86)), Vector((0.07, -0.10, 0.04)), 0.105, sides=6, n=6)
    for y in (-0.28, 0.26):
        horn(bm, Vector((0.36, y, top + 0.05)), Vector((0.58, y + 0.08, top + 0.26)), Vector((0.02, 0, 0)), 0.045, sides=5, n=3)
    return bm, gl


def build_lower_arm():
    """Left bracer (outer = +x): front/outer/back with a pointed top, an elbow cop at the back, a
    flared gold wrist, a glowing vein between gold rails, ivory spikes."""
    bm, gl = bmesh.new(), bmesh.new()
    hx, hy = 0.5, 0.5

    def z_hi(f, p):
        # Below the elbow joint (0.259) at the front, with a point at the front middle; rising
        # over the elbow at the back as a cop with its own point.
        front = 0.12 + 0.09 * max(0.0, 1 - abs(p.x) / 0.35) if p.y < -0.3 else None
        back = 0.40 + 0.12 * max(0.0, 1 - abs(p.x) / 0.4)
        if front is not None:
            return front
        return lerp(0.14, back, smooth((p.y + 0.3) / 0.8))
    band(bm, hx, hy, 0.14, ("front", "outer", "back"), -0.46, z_hi, flare_lo=0.05, nv=4, thick=0.065,
         mat_out=PLATE, mat_rim=PLATE, bevel=0.016, inner=False)
    band(bm, hx, hy, 0.14, ("front", "outer", "back"), lambda f, p: -0.52 - 0.05 * hem_wave(f, 5), -0.38,
         clear=CL + 0.07, flare_lo=0.04, nv=1, steps=5, thick=0.04, mat_out=GOLD, mat_rim=GOLD, bevel=0.01)
    xo = hx + CL + 0.065
    for y in (-0.075, 0.075):
        tube(bm, [Vector((xo, y, 0.17)), Vector((xo + 0.02, y, -0.1)), Vector((xo + 0.015, y, -0.37))], [0.028] * 3, sides=4, mat=GOLD)
    seam(gl, [Vector((xo, 0, 0.16)), Vector((xo + 0.012, 0, -0.1)), Vector((xo + 0.008, 0, -0.36))], r=0.03)
    horn(bm, Vector((0.02, hy + CL + 0.06, 0.40)), Vector((0.06, hy + 0.38, 0.26)), Vector((0, 0.02, 0.05)), 0.075, sides=5, n=4)
    for z in (0.04, -0.18):
        horn(bm, Vector((xo + 0.02, 0.1, z)), Vector((xo + 0.16, 0.27, z - 0.06)), Vector((0, 0, 0.02)), 0.035, sides=4, n=3)
    return bm, gl


def build_upper_leg():
    """Left cuisse (outer = +x): front and outer from under the tassets to a point over the knee; a
    back plate kept above the knee-bend zone; a glowing seam down the outer side."""
    bm, gl = bmesh.new(), bmesh.new()

    def z_hi(f, p):
        return 0.24 if p.y < -0.3 else lerp(0.24, 0.02, smooth((p.y + 0.35) / 0.3))   # outer side starts below the hand

    def z_lo(f, p):
        if p.y < -0.3:                        # front: a V pointing down to the knee
            return -0.36 - 0.12 * max(0.0, 1 - abs(p.x) / 0.5)
        return -0.36
    band(bm, 0.5, 0.5, 0.12, ("front", "outer"), z_lo, z_hi, nv=4, thick=0.065, mat_out=PLATE,
         mat_rim=GOLD, bevel=0.016, inner=False)
    front_plate(bm, -0.47, 0.49, -0.08, 0.24, 0.5 + CL, side=1, bulge=0.03, bulge_v=0.0, nu=6, nv=2, n=6,
                thick=0.055, hem=(3, 0.05), mat_out=PLATE, mat_rim=PLATE, bevel=0.014, inner=False)
    xo = 0.5 + CL + 0.068
    seam(gl, [Vector((xo, 0.0, 0.0)), Vector((xo + 0.01, 0.0, -0.18)), Vector((xo, 0.0, -0.34))])
    return bm, gl


def build_lower_leg_legs():
    """Left knee + greave (Legs piece): a crimson diamond over the knee with a keel and an ivory
    spike; a dark greave with shingled shin scales and a glowing seam; a calf plate below the
    knee-bend zone."""
    bm, gl = bmesh.new(), bmesh.new()

    def g_hi(f, p):
        return 0.26 if p.y < -0.3 else 0.30
    band(bm, 0.5, 0.5, 0.12, ("front", "outer"), lambda f, p: -0.30 - 0.06 * hem_wave(f, 4), g_hi, nv=3, steps=5,
         thick=0.06, mat_out=PLATE, mat_rim=GOLD, bevel=0.015, inner=False)
    front_plate(bm, -0.47, 0.49, -0.30, 0.06, 0.5 + CL, side=1, bulge=0.03, bulge_v=0.0, nu=6, nv=2, n=6,
                thick=0.05, hem=(3, 0.05), mat_out=PLATE, mat_rim=PLATE, bevel=0.012, inner=False)
    d = 0.5 + CL + 0.09

    def diamond(tv):
        w = 0.34 * max(0.0, 1 - abs(2 * tv - 1.1)) ** 0.75 + 0.02
        return -w + 0.02, w + 0.02
    front_plate(bm, 0, 0, 0.14, 0.72, d, side=-1, bulge=0.06, bulge_v=0.3, nu=4, nv=4, n=9, thick=0.07,
                xfun=diamond, mat_out=HIDE, mat_rim=GOLD, bevel=0.02)
    keel_y = -(d + 0.06 + 0.07)
    tube(bm, [Vector((0.02, keel_y + 0.03, 0.66)), Vector((0.02, keel_y - 0.005, 0.44)), Vector((0.02, keel_y + 0.03, 0.2))],
         [0.0, 0.035, 0.0], sides=4, mat=SCALE)
    horn(bm, Vector((0.02, keel_y + 0.02, 0.40)), Vector((0.02, keel_y - 0.16, 0.50)), Vector((0, 0, 0.03)), 0.05, sides=5, n=3)
    bvh = BVHTree.FromBMesh(bm)
    rows, zs = rows_of((0.12, -0.02, -0.16), -0.44, 0.44, 3)
    scale_rows(bm, bvh, grid_rays(rows, zs, -2.0, Vector((0, 1, 0))), 0.31, 0.29, tilt=12)
    xo = 0.5 + CL + 0.062
    seam(gl, [Vector((xo, 0.0, 0.24)), Vector((xo + 0.01, 0.0, 0.0)), Vector((xo, 0.0, -0.26))])
    return bm, gl


def build_lower_leg_boots():
    """Left boot cuff (Boots piece on the lower leg): a flared crimson shaft whose top ends in
    pointed scale tips, gold-edged."""
    bm, gl = bmesh.new(), bmesh.new()
    band(bm, 0.5, 0.5, 0.12, ("front", "outer", "back"), -0.51, lambda f, p: -0.30 + 0.10 * hem_wave(f, 6),
         clear=CL + 0.07, flare_lo=0.05, flare_hi=0.05, nv=2, steps=5, thick=0.055, mat_out=HIDE, mat_rim=GOLD, bevel=0.014)
    return bm, gl


def build_foot():
    """Left boot shell (Boots piece on the foot): top, toe, outer side and heel; ivory claws."""
    bm, gl = bmesh.new(), bmesh.new()
    hx, hy, hz = 0.5, 0.5, 0.15
    prof = []
    r = 0.10
    for t in (0.0, 0.5):
        prof.append((Vector((lerp(-hx + 0.03, hx - r, t), hz + CL)), Vector((0, 1))))
    for t in range(4):
        a = math.radians(lerp(90, 0, t / 3))
        n = Vector((math.cos(a), math.sin(a)))
        prof.append((Vector((hx - r, hz - r)) + n * (r + CL), n))
    prof.append((Vector((hx + CL, -hz + 0.02)), Vector((1, 0))))
    P = [[Vector((p.x, lerp(-0.42, 0.52, j / 4), p.y)) for p, n in prof] for j in range(5)]
    grid_shell(bm, P, 0.06, out_hint=lambda q: Vector((q.x + 0.3, 0, q.z)), mat_out=PLATE, mat_rim=PLATE, bevel=0.014, inner=False)
    front_plate(bm, -0.47, 0.52, -0.13, 0.21, hy + CL - 0.02, side=-1, bulge=0.06, bulge_v=0.3, nu=6, nv=3, n=4,
                thick=0.065, mat_out=HIDE, mat_rim=GOLD, bevel=0.016)
    front_plate(bm, -0.47, 0.52, -0.10, 0.21, hy + CL, side=1, bulge=0.03, bulge_v=0.3, nu=4, nv=2, n=4,
                thick=0.05, mat_out=PLATE, mat_rim=PLATE, bevel=0.014, inner=False)
    for x in (-0.28, 0.02, 0.32):
        base = Vector((x, -(hy + CL + 0.07), -0.05))
        horn(bm, base, base + Vector((0, -0.16, -0.08)), Vector((0, -0.01, 0.035)), 0.05, sides=5, n=3)
    seam(gl, [Vector((0.5 + CL + 0.065, y, -0.02)) for y in (-0.4, -0.1, 0.2, 0.45)], r=0.02)
    return bm, gl


def head_profile(s):
    """Inflated R15 head (rounded cylinder r 0.6, half-height 0.6, top corner r 0.25) as (radius, z)
    along arc length s from the bottom edge."""
    R, rc = 0.6 + CL, 0.25 + CL
    zc = 0.6 - 0.25
    L1 = zc + 0.6
    L2 = math.pi / 2 * rc
    if s <= L1:
        return R, -0.6 + s
    if s <= L1 + L2:
        a = (s - L1) / rc
        return (R - rc) + rc * math.cos(a), zc + rc * math.sin(a)
    t = min(s - L1 - L2, R - rc - 0.02)
    return (R - rc) - t, 0.6 + CL


HEAD_S_MAX = (0.35 + 0.6) + math.pi / 2 * (0.25 + CL) + (0.6 + CL - 0.25 - CL - 0.02)


def build_head():
    """Dragon helm: the player wears a dragon's head. The face shows through its open jaws, between
    the upper snout and the lower jaw plates; hair and hats are hidden."""
    bm, gl = bmesh.new(), bmesh.new()

    def z_bottom(th):
        a = abs(math.degrees(th))
        return lerp(0.26, lerp(-0.40, -0.47, smooth((a - 100) / 80)), smooth((a - 34) / 20))

    nu, nv = 24, 6
    P = []
    for j in range(nv + 1):
        t = j / nv
        row = []
        for i in range(nu):
            th = -math.pi + 2 * math.pi * i / nu
            s = lerp(z_bottom(th) + 0.6, HEAD_S_MAX, t ** 0.9)
            r, z = head_profile(s)
            row.append(Vector((r * math.sin(th), -r * math.cos(th), z)))
        P.append(row)
    grid_shell(bm, P, 0.07, wrap=True, out_hint=lambda q: Vector((q.x, q.y, q.z * 0.5)), mat_out=HIDE,
               mat_rim=GOLD, bevel=0.016, inner=False)
    # Neck-guard lames at the back: two overlapping crimson bands with pointed scale hems.
    for za, zb, off, rim in ((0.14, -0.16, 0.085, PLATE), (-0.10, -0.50, 0.11, GOLD)):
        P = []
        cols = 16
        for j in range(3):
            tv = j / 2
            row = []
            for i in range(cols + 1):
                th = math.radians(lerp(96, 264, i / cols))
                f = i / cols
                z = lerp(zb - 0.09 * hem_wave(f, 8) * (1 - tv) ** 2, za, tv)
                rr = 0.6 + CL + off + 0.05 * (1 - tv) ** 2
                row.append(Vector((rr * math.sin(th), -rr * math.cos(th), z)))
            P.append(row)
        grid_shell(bm, P, 0.045, out_hint=lambda q: Vector((q.x, q.y, 0)), mat_out=HIDE, mat_rim=rim, bevel=0.012)
    # Upper snout over the brow, with brow ridges over its eyes.
    secs = []
    for y, w, top, bot in ((-0.54, 0.86, 0.62, 0.22), (-0.72, 0.70, 0.54, 0.235), (-0.88, 0.52, 0.45, 0.25), (-1.0, 0.34, 0.37, 0.265)):
        secs.append([Vector((x, y, z)) for x, z in ((-w / 2, bot), (-w / 2 * 0.94, lerp(bot, top, 0.62)), (-w / 4, top), (0, top + 0.035),
                                                   (w / 4, top), (w / 2 * 0.94, lerp(bot, top, 0.62)), (w / 2, bot), (0, bot - 0.02))])
    verts = [[bm.verts.new(p) for p in ring] for ring in secs]
    faces = [bm.faces.new([verts[k][s], verts[k][(s + 1) % 8], verts[k + 1][(s + 1) % 8], verts[k + 1][s]])
             for k in range(len(verts) - 1) for s in range(8)]
    faces += [bm.faces.new(verts[0][::-1]), bm.faces.new(verts[-1])]
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    for f in faces:
        f.material_index = HIDE
    bev = bmesh.ops.bevel(bm, geom=list({e for f in faces for e in f.edges}), offset=0.012, segments=1,
                          affect="EDGES", clamp_overlap=True)
    for f in bev["faces"]:
        f.material_index = HIDE
    tube(bm, [Vector((-0.44, -0.58, 0.245)), Vector((-0.2, -0.66, 0.235)), Vector((0, -0.68, 0.23)), Vector((0.2, -0.66, 0.235)),
              Vector((0.44, -0.58, 0.245))], [0.032] * 5, sides=4, mat=GOLD)
    for sgn in (1, -1):
        # brow ridge
        tube(bm, [Vector((sgn * 0.12, -0.72, 0.56)), Vector((sgn * 0.27, -0.66, 0.60)), Vector((sgn * 0.42, -0.56, 0.60))],
             [0.03, 0.05, 0.02], sides=5, mat=SCALE)
        # Lower fangs along the cheek guard's front edge, pointing up and in (the dragon's jaw).
        for zt, ln in ((-0.36, 0.10), (-0.20, 0.085), (-0.04, 0.07)):
            a_ = math.radians(34 + 20 * smooth((0.26 - zt) / 0.66)) * sgn
            rr = 0.6 + CL + 0.05
            base = Vector((rr * math.sin(a_), -rr * math.cos(a_) - 0.015, zt))
            tube(bm, [base, base + Vector((-sgn * ln * 0.55, -0.02, ln * 0.55))], [0.026, 0.0], sides=4, mat=IVORY)
        for x, ln in ((0.25, 0.10), (0.34, 0.085)):
            base = Vector((sgn * x, -0.70 - (0.34 - x) * 0.6, 0.235))
            tube(bm, [base, base + Vector((0, -0.005, -ln))], [0.024, 0.0], sides=4, mat=IVORY)
        tube(bm, [Vector((sgn * 0.08, -0.99, 0.38)), Vector((sgn * 0.09, -1.02, 0.39))], [0.035, 0.0], sides=5, mat=DARK)
        gem(gl, Vector((sgn * 0.31, -0.66, 0.47)), Vector((sgn * 0.85, -0.3, 0.3)), Vector((0, 0.4, 1)), 0.20, 0.085, 0.03, sides=6)
        horn(bm, Vector((sgn * 0.40, -0.18, 0.52)), Vector((sgn * 0.74, 0.90, 1.02)), Vector((sgn * 0.18, -0.10, 0.18)), 0.12, sides=6, n=6)
        horn(bm, Vector((sgn * 0.60, 0.12, 0.05)), Vector((sgn * 0.76, 0.70, 0.0)), Vector((sgn * 0.06, 0, 0.07)), 0.07, sides=5, n=4)
        for z, ln in ((0.22, 0.34), (0.05, 0.28), (-0.12, 0.22)):   # ear frill
            th = math.radians(100) * sgn
            base = Vector((0.66 * math.sin(th), -0.66 * math.cos(th), z))
            horn(bm, base, base + Vector((sgn * ln * 0.55, ln * 0.8, -0.02)), Vector((0, 0, 0.03)), 0.045, sides=4, n=3)
    for y, h in ((-0.18, 0.21), (0.06, 0.19), (0.30, 0.16), (0.50, 0.12)):
        z = head_profile(HEAD_S_MAX - 0.02 - max(0, abs(y) - 0.3) * 0.8)[1] + 0.06
        horn(bm, Vector((0, y, z - 0.03)), Vector((0, y + h * 0.9, z + h * 0.8)), Vector((0, 0.02, -0.02)), 0.07, sides=5, n=3)
    return bm, gl


# ---------------------------------------------------------------------------
# Assemble
# ---------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
mats, glow_mat = make_materials()
coll_armor = bpy.data.collections.new("Armor"); scene.collection.children.link(coll_armor)
coll_proxy = bpy.data.collections.new("R15_Proxy_NotExported"); scene.collection.children.link(coll_proxy)


def to_object(name, bm, part, materials, coll):
    bm.normal_update()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in materials:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.location = part_pos(part)
    ob["body_part"] = part
    return ob


PIECES = []   # (piece, body part, builder, mirrored?)
SPEC = [
    ("Helmet", "Head", build_head),
    ("Chest", "UpperTorso", build_upper_torso),
    ("Chest", "LowerTorso", build_lower_torso),
    ("Chest", "UpperArm", build_upper_arm),
    ("Chest", "LowerArm", build_lower_arm),
    ("Legs", "UpperLeg", build_upper_leg),
    ("Legs", "LowerLeg", build_lower_leg_legs),
    ("Boots", "LowerLeg", build_lower_leg_boots),
    ("Boots", "Foot", build_foot),
]
armor_objs, glow_objs = [], []
for piece, part, builder in SPEC:
    bm, gl = builder()
    sides = [("Left", bm, gl), ("Right", mirror_bm(bm), mirror_bm(gl))] if part in ("UpperArm", "LowerArm", "UpperLeg", "LowerLeg", "Foot") else [("", bm, gl)]
    for side, b, g in sides:
        full = side + part
        armor_objs.append(to_object(f"{PREFIX}_{piece}_{full}", b, full, mats, coll_armor))
        if len(g.faces):
            glow_objs.append(to_object(f"{PREFIX}_{piece}_{full}_Glow", g, full, [glow_mat], coll_armor))
        else:
            g.free()

# Body proxy for previews (never exported).
body_mat = bpy.data.materials.new("Proxy_Body")
body_mat.use_nodes = True
body_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = rgba((150, 156, 168))
for n in PARTS:
    d = BODY[n]
    me = bpy.data.meshes.new("Proxy_" + n)
    me.from_pydata([s2b(v) for v in d["verts"]], [], d["faces"])
    me.materials.append(body_mat)
    ob = bpy.data.objects.new("Proxy_" + n, me)
    coll_proxy.objects.link(ob)
    ob.location = part_pos(n)
bm = bmesh.new()
for j in range(9):
    s = HEAD_S_MAX * j / 8
    r, z = head_profile(s)
    r -= CL
    z = z - CL if z > 0.5 else z
    for i in range(24):
        a = 2 * math.pi * i / 24
        bm.verts.new((r * math.cos(a), r * math.sin(a), z))
bm.verts.ensure_lookup_table()
bmesh.ops.convex_hull(bm, input=bm.verts)
me = bpy.data.meshes.new("Proxy_Head")
bm.to_mesh(me)
bm.free()
me.materials.append(body_mat)
ob = bpy.data.objects.new("Proxy_Head", me)
coll_proxy.objects.link(ob)
ob.location = part_pos("Head")
# A simple face on the proxy head so the helm's open face can be judged (preview only).
face_mat = bpy.data.materials.new("Proxy_Face")
face_mat.use_nodes = True
face_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1)
fb = bmesh.new()
for sgn in (1, -1):
    tube(fb, [Vector((sgn * 0.17, -0.605, 0.02)), Vector((sgn * 0.17, -0.605, 0.16))], [0.045, 0.045], sides=8, mat=0)
tube(fb, [Vector((x, -0.60 - 0.02 * (1 - (x / 0.2) ** 2), -0.2 - 0.07 * (1 - (x / 0.2) ** 2))) for x in (-0.2, -0.1, 0, 0.1, 0.2)],
     [0.02] * 5, sides=6, mat=0)
fme = bpy.data.meshes.new("Proxy_Face")
fb.to_mesh(fme)
fb.free()
fme.materials.append(face_mat)
fo = bpy.data.objects.new("Proxy_Face", fme)
coll_proxy.objects.link(fo)
fo.location = part_pos("Head")

for o in armor_objs + glow_objs:
    for p in o.data.polygons:
        p.use_smooth = False
tris = {o.name: sum(len(p.vertices) - 2 for p in o.data.polygons) for o in armor_objs + glow_objs}
print("TRIS total", sum(tris.values()))
for k, v in sorted(tris.items()):
    print("  ", k, v)

# ---------------------------------------------------------------------------
# Painterly bake: colour + icon lighting in one atlas on unique UVs (the chest kit's recipe).
# The base colour does the work (art direction): broad low-noise patches, 2-4 values per
# material, painted scales on the dark plates, darkened creases, bright bevel edges.
# ---------------------------------------------------------------------------
BAKE = {"key_dir": (-0.45, -0.6, 0.75), "key_lo": 0.64, "key_hi": 1.16, "ao_distance": 0.22, "ao_lo": 0.42,
        "rim_dir": (0.7, 0.6, 0.25), "rim": 0.14, "rim_color": (0.55, 0.62, 1.0),
        "edge": 0.5, "edge_radius": 0.022, "edge_tint": (1.0, 0.88, 0.7), "edge_tint_mix": 0.45}
ATLAS = {"Helmet": "helmet", "Chest": "chest", "Legs": "legs", "Boots": "legs"}   # piece -> atlas


def select_only(objs, active=None):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def albedo(nt, idx):
    """Painterly base colour socket for one material."""
    N, L = nt.nodes.new, nt.links.new
    geo = N("ShaderNodeNewGeometry")

    def scaled(sx, sy, sz):
        m = N("ShaderNodeVectorMath")
        m.operation = "MULTIPLY"
        L(geo.outputs["Position"], m.inputs[0])
        m.inputs[1].default_value = (sx, sy, sz)
        return m.outputs["Vector"]

    def noise(scale, detail=1.5, rough=0.45, distortion=0.25, vec=None):
        n = N("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        n.inputs["Distortion"].default_value = distortion
        L(vec or geo.outputs["Position"], n.inputs["Vector"])
        return n.outputs["Fac"]

    def ramp(fac, stops):
        r = N("ShaderNodeValToRGB")
        el = r.color_ramp.elements
        el[0].position, el[0].color = stops[0][0], rgba(stops[0][1])
        el[1].position, el[1].color = stops[-1][0], rgba(stops[-1][1])
        for pos, col in stops[1:-1]:
            e = el.new(pos)
            e.color = rgba(col)
        L(fac, r.inputs["Fac"])
        return r.outputs["Color"]

    if idx == SCALE:
        return ramp(noise(2.4), [(0.30, (142, 24, 34)), (0.52, (186, 38, 42)), (0.72, (220, 70, 54))])
    def painted_scales(sx, sz, stops, line_col, line_w=0.06):
        """Painted scales: Voronoi cells lighter in the middle, dark outlines, broad patches."""
        vec = scaled(sx, sx, sz)
        vo = N("ShaderNodeTexVoronoi")
        vo.feature = "F1"
        L(vec, vo.inputs["Vector"])
        cells = ramp(vo.outputs["Distance"], stops)
        ed = N("ShaderNodeTexVoronoi")
        ed.feature = "DISTANCE_TO_EDGE"
        L(vec, ed.inputs["Vector"])
        line = N("ShaderNodeMapRange")
        line.inputs["From Min"].default_value, line.inputs["From Max"].default_value = 0.0, line_w
        line.inputs["To Min"].default_value, line.inputs["To Max"].default_value = 0.8, 0.0
        L(ed.outputs["Distance"], line.inputs["Value"])
        mix = N("ShaderNodeMix")
        mix.data_type = "RGBA"
        L(line.outputs["Result"], mix.inputs["Factor"])
        L(cells, mix.inputs[6])
        mix.inputs[7].default_value = rgba(line_col)
        patch = N("ShaderNodeMix")
        patch.data_type = "RGBA"
        patch.blend_type = "MULTIPLY"
        L(noise(0.9, detail=0.5), patch.inputs["Factor"])
        L(mix.outputs[2], patch.inputs[6])
        patch.inputs[7].default_value = rgba((236, 216, 214))
        return patch.outputs[2]

    if idx == PLATE:
        return painted_scales(2.6, 3.1, [(0.05, (98, 32, 40)), (0.55, (74, 22, 31)), (0.95, (54, 15, 23))], (40, 11, 18), 0.035)
    if idx == HIDE:
        return painted_scales(3.3, 3.9, [(0.05, (206, 54, 52)), (0.55, (178, 38, 43)), (0.95, (146, 27, 36))], (118, 20, 31), 0.035)
    if idx == GOLD:
        return ramp(noise(3.0), [(0.32, (176, 118, 40)), (0.55, (222, 166, 64)), (0.74, (250, 214, 122))])
    if idx == IVORY:
        return ramp(noise(3.5), [(0.35, (206, 184, 146)), (0.6, (234, 220, 188)), (0.78, (248, 242, 222))])
    if idx == BELLY:
        return ramp(noise(2.8, vec=scaled(1.0, 1.0, 3.0)), [(0.35, (178, 108, 44)), (0.55, (210, 140, 60)), (0.75, (236, 176, 88))])
    return ramp(noise(3.0), [(0.4, (30, 16, 20)), (0.6, (44, 24, 28))])


def build_bake_material(m, idx, img, top):
    nt = m.node_tree
    nt.nodes.clear()
    N, L = nt.nodes.new, nt.links.new
    base = albedo(nt, idx)
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

    def mul(a, b):
        m_ = N("ShaderNodeMath")
        m_.operation = "MULTIPLY"
        L(a, m_.inputs[0])
        L(b, m_.inputs[1])
        return m_.outputs[0]

    key = remap(dot_light(BAKE["key_dir"]), 0, 1, BAKE["key_lo"], BAKE["key_hi"])
    ao = N("ShaderNodeAmbientOcclusion")
    ao.samples = 16
    ao.inputs["Distance"].default_value = BAKE["ao_distance"]
    aof = remap(ao.outputs["AO"], 0.15, 1.0, BAKE["ao_lo"], 1.0)
    sep = N("ShaderNodeSeparateXYZ")
    L(geo.outputs["Position"], sep.inputs["Vector"])
    height = remap(sep.outputs["Z"], 0.0, top, 0.86, 1.04)
    shade = mul(mul(key, aof), height)
    lit = N("ShaderNodeMix")
    lit.data_type = "RGBA"
    lit.blend_type = "MULTIPLY"
    lit.inputs["Factor"].default_value = 1.0
    L(base, lit.inputs[6])
    grey = N("ShaderNodeCombineColor")
    for i in range(3):
        L(shade, grey.inputs[i])
    L(grey.outputs["Color"], lit.inputs[7])
    rim = remap(dot_light(BAKE["rim_dir"]), 0.2, 1.0, 0.0, BAKE["rim"])
    rimadd = N("ShaderNodeMix")
    rimadd.data_type = "RGBA"
    rimadd.blend_type = "ADD"
    L(rim, rimadd.inputs["Factor"])
    L(lit.outputs[2], rimadd.inputs[6])
    rimadd.inputs[7].default_value = (*BAKE["rim_color"], 1)
    bev = N("ShaderNodeBevel")
    bev.samples = 8
    bev.inputs["Radius"].default_value = BAKE["edge_radius"]
    ed = N("ShaderNodeVectorMath")
    ed.operation = "DOT_PRODUCT"
    L(bev.outputs["Normal"], ed.inputs[0])
    L(geo.outputs["True Normal"], ed.inputs[1])
    edge = remap(ed.outputs["Value"], 0.985, 0.80, 0.0, BAKE["edge"])
    edge_up = mul(edge, remap(dot_light((-0.3, -0.35, 0.9)), 0, 1, 0.45, 1.0))
    tint = N("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.inputs["Factor"].default_value = BAKE["edge_tint_mix"]
    L(base, tint.inputs[6])
    tint.inputs[7].default_value = (*BAKE["edge_tint"], 1)
    final = N("ShaderNodeMix")
    final.data_type = "RGBA"
    L(edge_up, final.inputs["Factor"])
    L(rimadd.outputs[2], final.inputs[6])
    L(tint.outputs[2], final.inputs[7])
    em = N("ShaderNodeEmission")
    L(final.outputs[2], em.inputs["Color"])
    out = N("ShaderNodeOutputMaterial")
    L(em.outputs["Emission"], out.inputs["Surface"])
    target = N("ShaderNodeTexImage")
    target.image = img
    nt.nodes.active = target


def bake(objs, group):
    """One atlas per armour group so each gets the full 1024 texels Roblox allows."""
    path = ROOT / "textures" / f"{SET}-{group}.png"
    for o in objs:
        uv = o.data.uv_layers.new(name="UVMap")
        o.data.uv_layers.active = uv
    select_only(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(52), island_margin=0.003, correct_aspect=True)
    bpy.ops.uv.pack_islands(rotate=True, margin=0.003)
    bpy.ops.object.mode_set(mode="OBJECT")
    img = bpy.data.images.new(f"{SET}-{group}-bake", 2048, 2048, alpha=False)
    top = 5.6
    for i, m in enumerate(mats):
        build_bake_material(m, i, img, top)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.render.bake.margin = 16
    select_only(objs)
    bpy.ops.object.bake(type="EMIT")
    img.scale(BAKE_SIZE, BAKE_SIZE)            # Roblox caps textures at 1024; downsampling smooths it
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    final = bpy.data.materials.new(f"{PREFIX}_{group}")
    final.use_nodes = True
    nt = final.node_tree
    bs = nt.nodes["Principled BSDF"]
    bs.inputs["Roughness"].default_value = 0.72
    bs.inputs["Specular IOR Level"].default_value = 0.2
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = bpy.data.images.load(str(path))
    nt.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
    return final


def bake_all(objs):
    finals = {}
    groups = {}
    for o in objs:
        groups.setdefault(ATLAS[o.name.split("_")[1]], []).append(o)
    for group, members in groups.items():
        finals[group] = bake(members, group)
    for group, members in groups.items():         # swap materials only after every group is baked
        for o in members:
            o.data.materials.clear()
            o.data.materials.append(finals[group])
            for p in o.data.polygons:
                p.material_index = 0


if not QUICK:
    bake_all(armor_objs)

# ---------------------------------------------------------------------------
# Exports, polygon report, Studio install data
# ---------------------------------------------------------------------------
GROUND_IN_STUDIO = -HRP_HEIGHT       # HumanoidRootPart centre is 3 studs above the feet


def studio(v):
    return Vector((-v.x, v.z, v.y))


def export():
    objs = armor_objs + glow_objs
    select_only(objs)
    bpy.ops.export_scene.gltf(filepath=str(ROOT / "exports" / "glb" / f"{SET}.glb"), export_format="GLB",
                              use_selection=True, export_apply=True)
    bpy.ops.export_scene.fbx(filepath=str(ROOT / "exports" / "fbx" / f"{SET}.fbx"), use_selection=True,
                             object_types={"MESH"}, axis_forward="-Z", axis_up="Y", path_mode="COPY",
                             embed_textures=True, add_leaf_bones=False)
    report, install = {"set": SET, "rarity": "Legendary", "pieces": {}}, {"set": SET, "glow_color": GLOW, "parts": {}}
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
                                    "atlas": None if kind == "glow" else f"textures/{SET}-{ATLAS[piece]}.png",
                                    "offset": [round(sc.x, 4), round(sc.y, 4), round(sc.z, 4)],
                                    "size": [round(abs(ss.x), 4), round(abs(ss.y), 4), round(abs(ss.z), 4)]}
    report["triangles_total"] = total
    report["textures"] = {g: f"textures/{SET}-{g}.png ({BAKE_SIZE}x{BAKE_SIZE})" for g in sorted(set(ATLAS.values()))}
    (ROOT / f"polygon-report-{SET}.json").write_text(json.dumps(report, indent=1))
    (ROOT / f"studio-install-data-{SET}.json").write_text(json.dumps(install, indent=1))
    print("EXPORTED", total, "triangles")


if not QUICK:
    export()

# ---------------------------------------------------------------------------
# Preview renders
# ---------------------------------------------------------------------------
for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        scene.render.engine = engine
        break
    except TypeError:
        continue
scene.render.resolution_x, scene.render.resolution_y = 1000, 1200
scene.view_settings.view_transform = "Standard"
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
bmesh.ops.create_circle(bmf, cap_ends=True, radius=8, segments=48)
bmf.to_mesh(floor_me)
bmf.free()
fm = bpy.data.materials.new("Preview_Floor")
fm.use_nodes = True
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.42, 0.44, 0.45, 1)
floor_me.materials.append(fm)
floor = bpy.data.objects.new("Preview_Floor", floor_me)
scene.collection.objects.link(floor)
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 70
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam


def shoot(name, loc, target=(0, 0, 2.75)):
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = str(ROOT / "previews" / f"{SET}-{name}.png")
    bpy.ops.render.render(write_still=True)


D = 15.0
shoot("front", (0, -D, 3.3))
shoot("back", (0, D, 3.3))
shoot("side", (D, 0, 3.3))
shoot("threeq", (D * 0.62, -D * 0.78, 5.0))
cam_data.lens = 110
shoot("close-head", (4.5, -8.5, 5.6), target=(0, 0, 4.55))
shoot("close-torso", (-5.5, -9.5, 4.6), target=(0, 0, 3.6))
shoot("close-legs", (5.0, -9.5, 2.2), target=(0, 0, 1.2))
shoot("close-back", (-5.0, 9.5, 4.2), target=(0, 0, 3.3))
cam_data.lens = 70
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / f"{SET}.blend"))
print("DONE")
