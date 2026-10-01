"""Ray Gun: Godly ranged weapon (RARITY_GODLY_ARMOR.md section 9: "Zappy green blasts; enemies it
kills disintegrate in a burst that hits the ones nearby").

Run in background Blender 5.2 only (never the user's open scene):
  blender -b --factory-startup --threads 2 --python build_ray_gun.py

Environment switches (all optional):
  MODE=quick     build the model (flat colours) and render review shots only (no bake, no exports)
  MODE=full      (default) build, bake the painted texture, export, validate, render the brief's set
  OUT=<dir>      where quick renders go (default: this folder)
  GLOW_S/CORE_S  emission strengths of the two Neon meshes in the renders

Pipeline copied (not imported) from ../reapers-scythe/build_reapers_scythe.py: bmesh helpers, bevel +
weighted-normal finish, painterly bake to one 1024 BaseColor.png, catalogue stage, compose, validation.

Design (owner's direction 2026-09-30: the Call of Duty Zombies ray gun language, reference/ref1 + ref2,
translated to our chunky stylised low-poly, no logos or text): deep crimson painted-metal body with worn
edges and gold lightning-bolt inlays (our own bolt shape); a big round dial housing at the rear as the
focal piece (cream gauge face, red / yellow painted arc bands, a glowing green charge arc, tick marks,
sculpted needle, gold bezel and hub, raised rim teeth); two pointed rear spikes, a lower spike and a
loop handle out of the housing; a glowing green glass energy chamber with pale-hot crackles and three
leaning dark-steel coil rings; side vent modules (steel rails over glowing vent lines), a knurled
knob and a toggle; a gunmetal barrel with gold rings and an antenna mast with a gold loop; a swept
crimson fin with a bolt inlay; a flared crimson muzzle cone with gold bands and studs, a green mouth
and an emitter bead; a big ribbed black grip in a crimson frame and a sweeping trigger guard.

Extra switches: MODE=bakecheck (cheap 1024 bake + two check renders into OUT, no exports),
COMP_DEBUG=emit|glare (compositor debug output), AURA_GAIN (glow halo gain).

Axes: Blender +z up, the barrel points along -x, the gun is mirror-symmetric across y = 0.
1 Blender unit = 1 Roblox stud after SCALE. Studio axes are (-x, z, y) of Blender.
"""
import bpy, bmesh, math, json, os, sys, time
import numpy as np
from mathutils import Vector, Matrix
from pathlib import Path

T0 = time.time()
ROOT = Path(__file__).resolve().parent
NAME = "RayGun"
MODE = os.environ.get("MODE", "full")
OUT = Path(os.environ.get("OUT", str(ROOT)))
OUT.mkdir(parents=True, exist_ok=True)
BAKE_SIZE = 1024
SCALE = 0.75                 # authored units -> studs (hero size ~3.2 studs long; play size set in Studio)
BLEED_K, BLEED_STRENGTH = 0.18, 0.25
GLOW_S = float(os.environ.get("GLOW_S", "0.55"))
CORE_S = float(os.environ.get("CORE_S", "0.8"))


def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)


def V(*a):
    return Vector(a)


# ---------------------------------------------------------------------------
# Palette. Slot index = material index on every textured mesh.
# (name, flat colour, painterly ramp sRGB, bevel-edge highlight tint)
# ---------------------------------------------------------------------------
PAL = [
    ("Crimson", (130, 10, 28), [(0.28, (88, 6, 20)), (0.52, (130, 9, 28)), (0.8, (172, 20, 38))], (232, 96, 92)),
    ("Gold", (220, 160, 52), [(0.3, (120, 72, 20)), (0.52, (200, 142, 46)), (0.8, (252, 214, 118))], (255, 214, 120)),
    ("Steel", (52, 58, 70), [(0.28, (24, 28, 36)), (0.52, (52, 58, 70)), (0.8, (104, 114, 132))], (150, 168, 196)),
    ("Rubber", (26, 26, 32), [(0.3, (12, 12, 16)), (0.55, (28, 28, 34)), (0.8, (52, 52, 60))], (110, 110, 124)),
    ("Cream", (232, 214, 168), [(0.3, (196, 170, 120)), (0.55, (232, 214, 168)), (0.8, (250, 238, 204))], (255, 250, 232)),
    ("DialRed", (196, 36, 34), [(0.3, (140, 20, 22)), (0.55, (196, 36, 34)), (0.8, (232, 72, 58))], (255, 150, 130)),
    ("DialYellow", (236, 196, 72), [(0.3, (196, 148, 40)), (0.55, (236, 196, 72)), (0.8, (252, 228, 132))], (255, 246, 190)),
    ("Socket", (18, 8, 10), [(0.4, (10, 4, 6)), (0.75, (30, 12, 14))], (90, 40, 40)),
]
M_CRIM, M_GOLD, M_STEEL, M_RUB, M_CREAM, M_DRED, M_DYEL, M_SOCK = range(len(PAL))
GLOW = (16, 255, 40)         # Roblox Neon, hot saturated green (the ability colour)
CORE = (140, 255, 110)       # Roblox Neon, pale-hot plasma green (crackles, emitter bead)


def lin(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgba(c, a=1.0):
    return (lin(c[0]), lin(c[1]), lin(c[2]), a)


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------------------
# bmesh primitives (from the scythe pipeline)
# ---------------------------------------------------------------------------
def loft(bm, rings, closed=True, caps=True, mat=0, recalc=True):
    vr = [[bm.verts.new(p) for p in r] if isinstance(r, (list, tuple)) else [bm.verts.new(r)] for r in rings]
    faces = []
    for A, B in zip(vr, vr[1:]):
        if len(A) == 1 and len(B) == 1:
            continue
        n = max(len(A), len(B))
        for s in (range(n) if closed else range(n - 1)):
            s2 = (s + 1) % n
            if len(B) == 1:
                f = [A[s], A[s2], B[0]]
            elif len(A) == 1:
                f = [A[0], B[s2], B[s]]
            else:
                f = [A[s], A[s2], B[s2], B[s]]
            faces.append(bm.faces.new(f))
    if closed and caps:
        if len(vr[0]) > 2:
            faces.append(bm.faces.new(vr[0][::-1]))
        if len(vr[-1]) > 2:
            faces.append(bm.faces.new(vr[-1]))
    for f in faces:
        f.material_index = mat
    if recalc:
        bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def frames(pts, up=V(0, 1, 0)):
    n = len(pts)
    T = []
    for k in range(n):
        a, b = pts[max(k - 1, 0)], pts[min(k + 1, n - 1)]
        T.append((b - a).normalized())
    nn = T[0].cross(up)
    if nn.length < 1e-5:
        nn = T[0].cross(V(1, 0, 0))
    nn.normalize()
    N = []
    for t in T:
        nn = nn - t * nn.dot(t)
        if nn.length < 1e-6:
            nn = t.cross(up)
        nn.normalize()
        N.append(nn.copy())
    B = [t.cross(v) for t, v in zip(T, N)]
    return T, N, B


def tube(bm, pts, radii, sides=8, mat=0, flat=1.0, phase=0.0, up=V(0, 1, 0), caps=True):
    """Tube along a centreline. radii entries: r, or (r_normal, r_binormal); 0 = pointed end."""
    T, N, B = frames(pts, up)
    sec = [(math.cos(phase + 2 * math.pi * s / sides), math.sin(phase + 2 * math.pi * s / sides)) for s in range(sides)]
    rings = []
    for k, p in enumerate(pts):
        r = radii[k]
        ra, rb = (r, r * flat) if not isinstance(r, (tuple, list)) else r
        if ra <= 1e-6 and rb <= 1e-6:
            rings.append(p.copy())
            continue
        rings.append([p + N[k] * a * ra + B[k] * b * rb for a, b in sec])
    return loft(bm, rings, mat=mat, caps=caps)


def basis(x, y, z):
    return Matrix((x, y, z)).transposed().to_4x4()


AX = 1.55     # barrel axis height (authored units)


def MX():
    """Barrel frame: local z -> world -x (toward the muzzle), local x -> world up, local y -> world y."""
    return Matrix.Translation(V(0, 0, AX)) @ basis(V(0, 0, 1), V(0, 1, 0), V(-1, 0, 0))


def lathe(bm, prof, sides=16, M=None, mat=0, sy=1.0, mat_fn=None):
    """Surface of revolution about local +z (default: the barrel axis); prof = [(radius, t)]."""
    M = M or MX()
    phase = math.pi / sides
    rings = []
    for r, z in prof:
        if r <= 1e-6:
            rings.append(M @ V(0, 0, z))
        else:
            rings.append([M @ V(r * math.cos(phase + 2 * math.pi * s / sides), r * sy * math.sin(phase + 2 * math.pi * s / sides), z)
                          for s in range(sides)])
    faces = loft(bm, rings, mat=mat)
    if mat_fn:
        for f in faces:
            f.material_index = mat_fn(f.calc_center_median())
    return faces


def disc(bm, t0, t1, r, ch=0.025, sides=16, sy=1.0, mat=0):
    lathe(bm, [(0, t0), (r - ch, t0), (r, t0 + ch), (r, t1 - ch), (r - ch, t1), (0, t1)], sides, mat=mat, sy=sy)


def torus(bm, M, R, r, nmaj=20, nmin=6, mat=0, rz=None):
    rings = []
    for i in range(nmaj):
        a = 2 * math.pi * i / nmaj + math.pi / nmaj
        rad = V(math.cos(a), math.sin(a), 0)
        rings.append([M @ (rad * (R + r * math.cos(2 * math.pi * j / nmin)) + V(0, 0, (rz or r) * math.sin(2 * math.pi * j / nmin)))
                      for j in range(nmin)])
    faces = loft(bm, rings + [rings[0]], caps=False, mat=mat, recalc=False)
    vs = list({v for f in faces for v in f.verts})
    bmesh.ops.remove_doubles(bm, verts=vs, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=[f for f in bm.faces])


def plane_pts(poly, origin, au, av, an, d):
    return [origin + au * u + av * v + an * d for u, v in poly]


def prism(bm, poly, origin, au, av, an, d0, d1, mat=0):
    return loft(bm, [plane_pts(poly, origin, au, av, an, d0), plane_pts(poly, origin, au, av, an, d1)], mat=mat)


def frame_ring(bm, outer, inner, origin, au, av, an, d0, d1, mat=0):
    """Raised trim frame: outer wall, front face annulus, inner wall (back hidden in the body)."""
    return loft(bm, [plane_pts(outer, origin, au, av, an, d0), plane_pts(outer, origin, au, av, an, d1),
                     plane_pts(inner, origin, au, av, an, d1), plane_pts(inner, origin, au, av, an, d0)], caps=False, mat=mat)


def rrect(w, h, c, seg=3):
    pts = []
    for cx, cy, a0 in ((w / 2 - c, h / 2 - c, 0), (-w / 2 + c, h / 2 - c, 90), (-w / 2 + c, -h / 2 + c, 180), (w / 2 - c, -h / 2 + c, 270)):
        for k in range(seg + 1):
            a = math.radians(a0 + 90 * k / seg)
            pts.append((cx + c * math.cos(a), cy + c * math.sin(a)))
    return pts


def shrink(poly, k, dv=0.0):
    cu = sum(p[0] for p in poly) / len(poly)
    cv = sum(p[1] for p in poly) / len(poly)
    return [(cu + (u - cu) * k, cv + (v - cv) * k + dv) for u, v in poly]


# ---------------------------------------------------------------------------
# Scene objects, materials, modifiers
# ---------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.save_version = 0
scene = bpy.context.scene
ASSET = bpy.data.collections.new("ASSET export geometry")
REVIEW = bpy.data.collections.new("REVIEW not exported")
WORK = bpy.data.collections.new("WORK helpers")
for c in (ASSET, REVIEW, WORK):
    scene.collection.children.link(c)

MATS = []
for name, flat_c, ramp, edge in PAL:
    m = bpy.data.materials.new(f"{NAME}_{name}")
    m.use_nodes = True
    bs = m.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = rgba(flat_c)
    bs.inputs["Roughness"].default_value = 0.3 if name in ("Gold", "Steel") else 0.5
    if name in ("Gold", "Steel"):
        bs.inputs["Metallic"].default_value = 0.55
    MATS.append(m)


def emit_mat(name, col, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = (0, 0, 0, 1)
    bs.inputs["Emission Color"].default_value = rgba(col)
    bs.inputs["Emission Strength"].default_value = strength
    return m


GLOW_MAT = emit_mat(f"{NAME}_Glow", GLOW, GLOW_S)
CORE_MAT = emit_mat(f"{NAME}_GlowCore", CORE, CORE_S)
PARTS = []


def new_bm():
    return bmesh.new()


def make_obj(name, bm, kind="tex", smooth=False, coll=None):
    bm.normal_update()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if kind == "tex":
        for m in MATS:
            me.materials.append(m)
    elif kind == "glow":
        me.materials.append(GLOW_MAT)
    elif kind == "core":
        me.materials.append(CORE_MAT)
    for p in me.polygons:
        p.use_smooth = smooth
    ob = bpy.data.objects.new(name, me)
    (coll or ASSET).objects.link(ob)
    ob["kind"] = kind
    if kind != "fig":
        PARTS.append(ob)
    return ob


def add_bevel(ob, width, segs=2, angle=30.0, profile=0.55, harden=True):
    m = ob.modifiers.new("Bevel", "BEVEL")
    m.width = width
    m.segments = segs
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle)
    m.profile = profile
    m.use_clamp_overlap = True
    m.harden_normals = harden and segs > 1
    m.miter_outer = "MITER_ARC"
    return m


def add_wn(ob):
    m = ob.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
    m.keep_sharp = True
    m.weight = 50
    m.mode = "FACE_AREA"
    return m


def hard(ob, width=0.014, segs=2, angle=30.0):
    for p in ob.data.polygons:
        p.use_smooth = True
    add_bevel(ob, width, segs=segs, angle=angle)
    add_wn(ob)
    return ob


def soft(ob, width=0.01, angle=32.0):
    add_bevel(ob, width, segs=1, angle=angle, harden=False)
    return ob


def flat(ob):
    """Round parts (tori, studs): smooth shading + weighted normals, no bevel (keeps triangles down)."""
    for p in ob.data.polygons:
        p.use_smooth = True
    add_wn(ob)
    return ob


def select_only(objs, active=None):
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def apply_mods(ob):
    select_only([ob])
    for m in list(ob.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=m.name)
        except RuntimeError as e:
            log("modifier apply failed", ob.name, m.name, e)
            ob.modifiers.remove(m)


# ---------------------------------------------------------------------------
# The ray gun. Side profile traced from the owner's reference (reference/ref1), re-proportioned chunky.
# Barrel axis along -x at z = AX; t = distance toward the muzzle (t = -x) for barrel-axis lathes.
# ---------------------------------------------------------------------------
XA, YA, ZA = V(1, 0, 0), V(0, 1, 0), V(0, 0, 1)
DIAL_C = V(1.45, 0, 1.64)     # dial housing centre (focal piece)
DIAL_R, DIAL_W = 0.465, 0.27
GRIP_TOP, GRIP_BOT = V(1.17, 0, 1.22), V(1.33, 0, 0.08)
GRIP_AXIS = (GRIP_BOT - GRIP_TOP).normalized()
MUZZLE_T = 2.23
O = V(0, 0, 0)


def MYs(c, s=1):
    """Dial frame for side s: local z -> world y*s, local x -> world z, local y -> world x*s."""
    return Matrix.Translation(c) @ basis(V(0, 0, 1), V(s, 0, 0), V(0, s, 0))


def MXt(t, tilt=0.0):
    """Ring frame on the barrel axis at t (ring plane = world YZ), optionally leaned about y."""
    return Matrix.Translation(V(-t, 0, AX)) @ Matrix.Rotation(math.radians(tilt), 4, "Y") @ basis(V(0, 0, 1), V(0, 1, 0), V(-1, 0, 0))


def poly_area(poly):
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))


def offset(poly, d, clamp=2.2):
    """Inward offset of a 2D polygon by d (miter, clamped at sharp tips)."""
    ccw = poly_area(poly) > 0
    n = len(poly)
    out = []
    for i in range(n):
        p0, p1, p2 = Vector(poly[i - 1]), Vector(poly[i]), Vector(poly[(i + 1) % n])
        e1, e2 = (p1 - p0).normalized(), (p2 - p1).normalized()
        n1 = Vector((-e1.y, e1.x)) if ccw else Vector((e1.y, -e1.x))
        n2 = Vector((-e2.y, e2.x)) if ccw else Vector((e2.y, -e2.x))
        b = n1 + n2
        if b.length < 1e-6:
            b = n1
        b.normalize()
        L = d / max(0.2, b.dot(n1))
        L = min(L, d * clamp)
        q = p1 + b * L
        out.append((q.x, q.y))
    return out


def lens(bm, poly, origin, au, av, an, e, t, d, mat=0):
    """Plate with a chamfered (lens / diamond-ish) section: outline at +-e, inset (by d) flat faces at +-t."""
    ins = offset(poly, d)
    return loft(bm, [plane_pts(ins, origin, au, av, an, -t), plane_pts(poly, origin, au, av, an, -e),
                     plane_pts(poly, origin, au, av, an, e), plane_pts(ins, origin, au, av, an, t)], mat=mat)


def sector(r0, r1, a0, a1, n=8):
    a0, a1 = math.radians(a0), math.radians(a1)
    outer = [(r1 * math.cos(a0 + (a1 - a0) * k / n), r1 * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]
    inner = [(r0 * math.cos(a0 + (a1 - a0) * k / n), r0 * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]
    return outer + inner[::-1] if r0 > 1e-6 else outer + [(0.0, 0.0)]


def rot2(poly, ang, du=0.0, dv=0.0):
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    return [(du + u * c - v * s, dv + u * s + v * c) for u, v in poly]


# our own lightning bolt: broad tail, two zig-zags, needle point at +u (unit length)
BOLT = [(0.00, 0.06), (0.42, 0.17), (0.38, 0.075), (1.00, 0.13), (0.57, -0.045), (0.61, 0.035), (0.04, -0.07)]


def bolt(p0, p1, h=1.0):
    d = Vector(p1) - Vector(p0)
    L = d.length
    ang = math.degrees(math.atan2(d.y, d.x))
    return rot2([(u * L, v * L * h) for u, v in BOLT], ang, p0[0], p0[1])


def build_muzzle():
    bm = new_bm()      # crimson flared cone, recessed mouth
    lathe(bm, [(0.0, 1.30), (0.15, 1.30), (0.162, 1.34), (0.213, 1.56), (0.263, 1.78), (0.291, 1.83), (0.293, 1.89),
               (0.274, 1.91), (0.224, 1.91), (0.207, 1.87), (0.0, 1.87)], 16, mat=M_CRIM,
          mat_fn=lambda c: M_SOCK if (-c.x > 1.86 and math.hypot(c.y, c.z - AX) < 0.212) else M_CRIM)
    hard(make_obj("MuzzleCone", bm), 0.008, segs=2)
    bm = new_bm()      # gold bands + studs + bead rod collar
    for t0, r in ((1.37, 0.18), (1.76, 0.272)):
        lathe(bm, [(0.0, t0), (r, t0), (r + 0.018, t0 + 0.018), (r + 0.018, t0 + 0.042), (r, t0 + 0.06), (0.0, t0 + 0.06)], 16, mat=M_GOLD)
    for k in range(8):
        a = 2 * math.pi * (k + 0.5) / 8
        rd = V(math.cos(a), math.sin(a), 0)
        base = MX() @ (rd * 0.222 + V(0, 0, 1.585))
        nrm = (MX().to_3x3() @ (rd * 0.95 + V(0, 0, -0.25))).normalized()
        side = nrm.cross(V(1, 0, 0)).normalized()
        M = Matrix.Translation(base) @ basis(side, nrm.cross(side), nrm)
        lathe(bm, [(0.0, -0.02), (0.042, -0.02), (0.042, 0.012), (0.03, 0.036), (0.0, 0.046)], 8, M=M, mat=M_GOLD)
    flat(make_obj("MuzzleGold", bm))
    bm = new_bm()      # emitter rod
    lathe(bm, [(0.0, 1.84), (0.06, 1.84), (0.06, 1.90), (0.038, 1.93), (0.032, 2.08), (0.045, 2.10), (0.0, 2.11)], 8, mat=M_STEEL)
    hard(make_obj("EmitterRod", bm), 0.006, segs=1)
    bm = new_bm()
    lathe(bm, [(0.0, 1.865), (0.192, 1.865), (0.192, 1.885), (0.0, 1.885)], 16, mat=0)                 # mouth glow disc
    make_obj("MouthGlow", bm, kind="glow")
    bm = new_bm()
    lathe(bm, [(0, 2.07), (0.05, 2.08), (0.08, 2.13), (0.075, 2.18), (0.045, 2.215), (0, MUZZLE_T)], 10, mat=0)   # bead
    make_obj("EmitterBead", bm, kind="core")


def build_barrel():
    bm = new_bm()
    lathe(bm, [(0.0, 0.58), (0.105, 0.58), (0.105, 1.33), (0.0, 1.33)], 12, mat=M_STEEL)
    # antenna: steel mast from a clamp on the barrel, gold loop on top (ring plane = world YZ)
    lathe(bm, [(0.0, -0.05), (0.07, -0.05), (0.07, 0.05), (0.0, 0.05)], 10, M=Matrix.Translation(V(-1.29, 0, AX + 0.08)), mat=M_STEEL)
    tube(bm, [V(-1.29, 0, AX + 0.1), V(-1.29, 0, AX + 0.45), V(-1.29, 0, AX + 0.73)], [0.036, 0.031, 0.027], sides=6, mat=M_STEEL,
         up=V(1, 0, 0))
    hard(make_obj("Barrel", bm), 0.008, segs=1)
    bm = new_bm()
    for t0 in (1.20, 1.04):
        torus(bm, MXt(t0), 0.118, 0.034, 16, 6, mat=M_GOLD)
    torus(bm, Matrix.Translation(V(-1.29, 0, AX + 0.83)) @ basis(V(0, 1, 0), V(0, 0, 1), V(1, 0, 0)), 0.095, 0.026, 14, 6, mat=M_GOLD)
    lathe(bm, [(0.0, -0.06), (0.05, -0.06), (0.05, 0.0), (0.0, 0.0)], 8, M=Matrix.Translation(V(-1.29, 0, AX + 0.72)), mat=M_GOLD)
    flat(make_obj("BarrelGold", bm))


FIN = [(-1.18, 1.72), (-0.60, 2.06), (-0.40, 2.16), (-0.47, 2.02), (-0.60, 1.82), (-0.55, 1.72)]
CREST = [(0.50, 1.84), (0.58, 1.97), (0.95, 2.06), (1.40, 2.14), (1.92, 2.27), (1.76, 2.11), (1.62, 1.98), (1.40, 1.84)]
GRIP = [(0.86, 1.36), (0.88, 1.15), (0.93, 0.80), (0.99, 0.45), (1.02, 0.22), (0.98, 0.10), (1.04, 0.0), (1.30, -0.02),
        (1.60, 0.0), (1.69, 0.08), (1.67, 0.24), (1.57, 0.60), (1.49, 0.95), (1.45, 1.20), (1.47, 1.36)]


def build_fins():
    bm, bmg = new_bm(), new_bm()
    lens(bm, FIN, O, XA, ZA, YA, 0.028, 0.07, 0.05, mat=M_CRIM)
    lens(bm, CREST, O, XA, ZA, YA, 0.11, 0.2, 0.06, mat=M_CRIM)
    hard(make_obj("Fins", bm), 0.008, segs=2)
    for s in (1, -1):
        prism(bmg, bolt((-1.02, 1.80), (-0.56, 2.03), 1.15), O, XA, ZA, YA * s, 0.062, 0.079, mat=M_GOLD)
        prism(bmg, bolt((0.70, 1.95), (1.62, 2.13), 0.8), O, XA, ZA, YA * s, 0.19, 0.212, mat=M_GOLD)
    soft(make_obj("FinBolts", bmg), 0.004)


def build_core_body():
    bm = new_bm()
    # nose dome (crimson) in front of the glass
    lathe(bm, [(0.0, 0.34), (0.315, 0.34), (0.335, 0.40), (0.325, 0.48), (0.28, 0.575), (0.21, 0.655), (0.125, 0.70), (0.0, 0.72)], 16, mat=M_CRIM)
    # cradle under the glass: U-section trough
    U = [(-0.335, 1.58), (-0.335, 1.30), (-0.27, 1.20), (0.27, 1.20), (0.335, 1.30), (0.335, 1.58), (0.279, 1.58), (0.24, 1.50),
         (0.15, 1.41), (0.0, 1.37), (-0.15, 1.41), (-0.24, 1.50), (-0.279, 1.58)]
    prism(bm, U, V(0, 0, 0), YA, ZA, -XA, 0.40, -0.52, mat=M_CRIM)
    # lower receiver block (trigger housing), stepped nose
    prism(bm, [(-0.24, 1.32), (-0.24, 1.14), (-0.16, 1.05), (0.84, 1.05), (0.90, 1.14), (0.90, 1.32)], O, XA, ZA, YA, -0.235, 0.235, mat=M_CRIM)
    prism(bm, [(-0.30, 1.30), (-0.30, 1.10), (-0.22, 1.02), (0.02, 1.02), (0.06, 1.10), (0.06, 1.30)], O, XA, ZA, YA, -0.26, 0.26, mat=M_CRIM)
    # side panel (knob / toggle block) and the dial housing disc
    prism(bm, [(0.48, 1.20), (1.16, 1.20), (1.20, 1.28), (1.20, 1.88), (1.12, 1.96), (0.56, 1.96), (0.48, 1.88)], O, XA, ZA, YA, -0.27, 0.27, mat=M_CRIM)
    lathe(bm, [(0.0, -DIAL_W), (DIAL_R - 0.05, -DIAL_W), (DIAL_R, -DIAL_W + 0.05), (DIAL_R, DIAL_W - 0.05), (DIAL_R - 0.05, DIAL_W), (0.0, DIAL_W)],
          28, M=MYs(DIAL_C), mat=M_CRIM)
    hard(make_obj("Body", bm), 0.012, segs=2)

    bm = new_bm()      # steel collars at both ends of the glass, coil rings
    lathe(bm, [(0.0, 0.30), (0.30, 0.30), (0.33, 0.32), (0.33, 0.38), (0.30, 0.40), (0.0, 0.40)], 16, mat=M_STEEL)
    lathe(bm, [(0.0, -0.58), (0.30, -0.58), (0.325, -0.56), (0.325, -0.50), (0.30, -0.48), (0.0, -0.48)], 16, mat=M_STEEL)
    hard(make_obj("ChamberCollars", bm), 0.006, segs=1)
    bm = new_bm()
    for t0, tilt in ((0.13, 12), (-0.12, 12), (-0.36, 12)):
        torus(bm, MXt(t0, tilt), 0.31, 0.045, 18, 6, mat=M_STEEL)
    flat(make_obj("CoilRings", bm))

    bm = new_bm()      # gold trim: cradle rim caps, pinstripes, rivets
    for s in (1, -1):
        prism(bm, rrect(0.86, 0.035, 0.012, 1), V(0.07, 0, 1.59), XA, ZA, YA * s, 0.27, 0.343, mat=M_GOLD)
        prism(bm, bolt((-0.36, 1.29), (0.22, 1.47), 1.0), O, XA, ZA, YA * s, 0.32, 0.352, mat=M_GOLD)
        prism(bm, [(-0.27, 1.06), (-0.245, 1.06), (-0.245, 1.25), (-0.27, 1.25)], O, XA, ZA, YA * s, 0.25, 0.275, mat=M_GOLD)
        for p in (V(0.16, 0, 1.17), V(0.72, 0, 1.13), V(1.48, 0, 0.12)):
            lathe(bm, [(0.0, 0.0), (0.042, 0.0), (0.042, 0.02), (0.028, 0.036), (0.0, 0.042)], 8,
                  M=MYs(p + V(0, s * (0.235 if p.z < 0.5 else 0.23), 0), s), mat=M_GOLD)
    flat(make_obj("GoldTrim", bm))

    bm = new_bm()      # the glowing glass chamber
    lathe(bm, [(0.0, -0.54), (0.288, -0.54), (0.288, 0.36), (0.0, 0.36)], 14, mat=0)
    make_obj("GlassChamber", bm, kind="glow")
    bm = new_bm()      # pale-hot crackles crawling over the glass
    for ang, seed in ((90, 0), (32, 1), (148, -1)):
        a0 = math.radians(ang)
        pts = []
        n = 11
        for k in range(n + 1):
            t = 0.30 - (0.84 * k / n)
            zz = (0.16 if (k % 2) else -0.16) * (1 if seed >= 0 else -1) * (0.6 if k in (0, n) else 1.0)
            a = a0 + zz
            pts.append(MX() @ V(0.29 * math.cos(a), 0.29 * math.sin(a), t))
        T, Nn, B = frames(pts)
        rd = (pts[n // 2] - V(pts[n // 2].x, 0, AX)).normalized()
        tube(bm, pts, [(0.022, 0.012)] * (n + 1), sides=4, mat=0, up=rd, phase=math.pi / 4)
    make_obj("Crackles", bm, kind="core")


def build_dial():
    bmc, bmt, bms, bmk, bmglow = new_bm(), new_bm(), new_bm(), new_bm(), new_bm()
    c = DIAL_C
    for s in (1, -1):
        an = YA * s
        prism(bmc, sector(0.0, 0.335, -12, 192, 14), c, XA, ZA, an, 0.25, 0.278, mat=M_CREAM)
        prism(bmc, sector(0.215, 0.315, 122, 186, 6), c, XA, ZA, an, 0.265, 0.289, mat=M_DRED)
        prism(bmc, sector(0.215, 0.315, 64, 122, 6), c, XA, ZA, an, 0.265, 0.289, mat=M_DYEL)
        prism(bmglow, sector(0.215, 0.315, -6, 64, 7), c, XA, ZA, an, 0.265, 0.292)
        for k in range(13):           # tick marks
            a = -6 + k * 16
            prism(bmt, rot2([(-0.026, -0.009), (0.026, -0.009), (0.026, 0.009), (-0.026, 0.009)], a, 0.19 * math.cos(math.radians(a)),
                             0.19 * math.sin(math.radians(a))), c, XA, ZA, an, 0.265, 0.286, mat=M_STEEL)
        # needle: tapered diamond pointing into the green zone
        nd = rot2([(-0.075, 0.0), (0.0, 0.036), (0.315, 0.0), (0.0, -0.036)], 38)
        lens(bmk, nd, c + an * 0.306, XA, ZA, an, 0.006, 0.016, 0.012, mat=M_STEEL)
        lathe(bmk, [(0.0, 0.26), (0.078, 0.26), (0.078, 0.31), (0.064, 0.328), (0.0, 0.328)], 12, M=MYs(c, s), mat=M_STEEL)
        lathe(bms, [(0.0, 0.32), (0.044, 0.32), (0.044, 0.34), (0.032, 0.352), (0.0, 0.355)], 10, M=MYs(c, s), mat=M_GOLD)
        torus(bms, MYs(c + an * 0.28, s), 0.343, 0.024, 28, 5, mat=M_GOLD)
        for a in (222, 254, 286, 318):     # raised teeth on the lower rim
            prism(bmc, sector(0.37, 0.445, a - 11, a + 11, 3), c, XA, ZA, an, 0.25, 0.298, mat=M_CRIM)
    hard(make_obj("DialFace", bmc), 0.006, segs=1)
    flat(make_obj("DialGold", bms))
    flat(make_obj("DialTicks", bmt))
    hard(make_obj("DialSteel", bmk), 0.004, segs=1)
    make_obj("DialGlow", bmglow, kind="glow")


def build_panel_details():
    bmr, bmk, bmv, bmglow = new_bm(), new_bm(), new_bm(), new_bm()
    for s in (1, -1):
        an = YA * s
        # knob (knurled steel, gold cap) and toggle switch
        prof = [(0.0, 0.25), (0.085, 0.25), (0.085, 0.305), (0.075, 0.33), (0.045, 0.338), (0.0, 0.338)]
        lathe(bmk, prof, 10, M=MYs(V(0.66, 0, 1.79), s), mat=M_STEEL)
        lathe(bmr, [(0.0, 0.335), (0.04, 0.335), (0.04, 0.345), (0.0, 0.35)], 8, M=MYs(V(0.66, 0, 1.79), s), mat=M_GOLD)
        prism(bmv, rrect(0.10, 0.17, 0.02, 1), V(0.90, 0, 1.79), XA, ZA, an, 0.25, 0.283, mat=M_SOCK)
        tube(bmk, [V(0.90, s * 0.27, 1.74), V(0.915, s * 0.31, 1.82), V(0.93, s * 0.33, 1.87)], [0.026, 0.024, 0.022], sides=6, mat=M_STEEL)
        lathe(bmr, [(0, -0.035), (0.03, -0.03), (0.036, 0.0), (0.03, 0.03), (0, 0.035)], 8,
              M=Matrix.Translation(V(0.932, s * 0.333, 1.885)), mat=M_GOLD)
        # vent module: crimson frame, dark slot, glowing vent lines, three steel rails
        vc = V(0.70, 0, 1.465)
        frame_ring(bmr, rrect(0.88, 0.30, 0.05, 2), rrect(0.80, 0.23, 0.03, 2), vc, XA, ZA, an, 0.26, 0.365, mat=M_CRIM)
        prism(bmv, rrect(0.82, 0.25, 0.03, 1), vc, XA, ZA, an, 0.26, 0.338, mat=M_SOCK)
        for dz in (0.035, -0.035):
            prism(bmglow, rrect(0.76, 0.03, 0.012, 1), vc + V(0, 0, dz), XA, ZA, an, 0.32, 0.348)
        for dz in (0.072, 0.0, -0.072):
            prism(bmk, rrect(0.92, 0.036, 0.012, 1), vc + V(0, 0, dz), XA, ZA, an, 0.31, 0.385, mat=M_STEEL)
    hard(make_obj("PanelBits", bmk), 0.006, segs=1)
    hard(make_obj("VentFrames", bmr), 0.008, segs=1)
    soft(make_obj("VentSlots", bmv), 0.005)
    make_obj("VentGlow", bmglow, kind="glow")


def build_spikes():
    bm = new_bm()
    # lower spike (centre) and a mid pair, needle points, out of the back of the dial housing
    for a, b, r0 in ((V(1.80, 0, 1.63), V(2.36, 0, 1.66), 0.07), (V(1.74, 0.12, 1.92), V(2.22, 0.15, 2.14), 0.058),
                     (V(1.74, -0.12, 1.92), V(2.22, -0.15, 2.14), 0.058)):
        d = (b - a)
        tube(bm, [a, a + d * 0.25, a + d * 0.6, a + d * 0.85, b], [r0, r0 * 0.92, r0 * 0.7, r0 * 0.42, 0], sides=6, mat=M_STEEL, up=V(0, 0, 1))
        tube(bm, [a + d * 0.05, a + d * 0.12, a + d * 0.2], [r0 + 0.03, r0 + 0.035, r0 + 0.02], sides=6, mat=M_STEEL, up=V(0, 0, 1))
    # upper loop handle (staple), legs rising out of the crest
    lp = [V(1.56, 0, 1.98), V(1.62, 0, 2.30), V(1.64, 0, 2.40), V(1.70, 0, 2.44), V(1.80, 0, 2.43), V(1.84, 0, 2.36), V(1.80, 0, 2.02)]
    tube(bm, lp, [0.04] * len(lp), sides=6, mat=M_STEEL, up=V(0, 1, 0))
    hard(make_obj("Spikes", bm), 0.006, segs=1)


def build_grip():
    bm, bmr = new_bm(), new_bm()
    lens(bm, GRIP, O, XA, ZA, YA, 0.14, 0.185, 0.045, mat=M_CRIM)
    ins = offset(GRIP[1:-1], 0.075)
    for s in (1, -1):
        prism(bmr, ins, O, XA, ZA, YA * s, 0.12, 0.212, mat=M_RUB)
        for k in range(7):            # chunky ribs across the grip
            z = 0.27 + k * 0.125
            u = GRIP_TOP.lerp(GRIP_BOT, (GRIP_TOP.z - z) / (GRIP_TOP.z - GRIP_BOT.z))
            prism(bmr, rrect(0.36 - 0.012 * (6 - k), 0.05, 0.02, 1), V(u.x + 0.02, 0, z), XA, ZA, YA * s, 0.2, 0.238, mat=M_RUB)
    hard(make_obj("GripFrame", bm), 0.01, segs=2)
    hard(make_obj("GripRubber", bmr), 0.008, segs=1)
    bm = new_bm()      # trigger guard sweeping from the front block to the grip heel
    gp = [V(0.02, 0, 1.12), V(0.04, 0, 0.92), V(0.13, 0, 0.66), V(0.30, 0, 0.42), V(0.52, 0, 0.24), V(0.78, 0, 0.13), V(1.06, 0, 0.10)]
    tube(bm, gp, [(0.048, 0.08)] * len(gp), sides=8, mat=M_CRIM, phase=math.pi / 8)
    hard(make_obj("TriggerGuard", bm), 0.008, segs=1)
    bm = new_bm()
    lens(bm, [(0.72, 1.08), (0.84, 1.08), (0.82, 0.97), (0.76, 0.87), (0.66, 0.82), (0.70, 0.90), (0.72, 0.98)], O, XA, ZA, YA, 0.02, 0.045, 0.02, mat=M_STEEL)
    hard(make_obj("Trigger", bm), 0.005, segs=1)


def build_all():
    build_muzzle()
    build_barrel()
    build_fins()
    build_core_body()
    build_dial()
    build_panel_details()
    build_spikes()
    build_grip()


build_all()
log("built", len(PARTS), "parts")


def clean_degenerate(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])
    bad = [f for f in bm.faces if f.calc_area() < 1e-9]
    if bad:
        bmesh.ops.delete(bm, geom=bad, context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(o.data)
    bm.free()


def apply_all():
    for o in list(PARTS):
        wn = [m for m in o.modifiers if m.type == "WEIGHTED_NORMAL"]
        for m in wn:
            o.modifiers.remove(m)
        if o.modifiers:
            apply_mods(o)
        clean_degenerate(o)
        if wn:
            add_wn(o)
            apply_mods(o)


apply_all()


def tri_count(objs):
    tot = {}
    for o in objs:
        o.data.calc_loop_triangles()
        tot[o.name] = len(o.data.loop_triangles)
    return tot


TRIS = tri_count(PARTS)
log("TRIS total", sum(TRIS.values()), sorted(TRIS.items(), key=lambda kv: -kv[1]))

# authored units -> studs; origin: grip-bottom level at z = 0
pts0 = [o.matrix_world @ v.co for o in PARTS for v in o.data.vertices]
Z0 = min(p.z for p in pts0)


def XF(p):
    return (Vector(p) - V(0, 0, Z0)) * SCALE


for o in PARTS:
    o.data.transform(Matrix.Scale(SCALE, 4) @ Matrix.Translation(V(0, 0, -Z0)))
    o.data.update()
AXS = (AX - Z0) * SCALE


# ---------------------------------------------------------------------------
# Review rendering: the weapon catalogue's own stage (copied from the scythe), plus a yaw so the
# gun shows its dish muzzle in the 3/4 catalogue shot the way the catalogue guns do.
# ---------------------------------------------------------------------------
def world_bounds(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in objs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = o.matrix_world
        pts.extend([mw @ v.co for v in me.vertices])
        ev.to_mesh_clear()
    return pts


def setup_comp(bloom=0.45):
    """Highlight bloom on the image + a wide saturated aura glared from the Emission pass only, added back on
    top (Roblox Neon blooms in game; the aura must not wash the grey stage)."""
    scene.view_layers[0].use_pass_emit = True
    tree = bpy.data.node_groups.get("ReviewComp") or bpy.data.node_groups.new("ReviewComp", "CompositorNodeTree")
    tree.nodes.clear()
    if not tree.interface.items_tree:
        tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = tree.nodes.new("CompositorNodeRLayers")
    out = tree.nodes.new("NodeGroupOutput")
    if bloom <= 0:
        tree.links.new(rl.outputs["Image"], out.inputs[0])
        scene.compositing_node_group = tree
        return
    g = tree.nodes.new("CompositorNodeGlare")
    g.inputs["Type"].default_value = "Bloom"
    g.inputs["Quality"].default_value = "High"
    g.inputs["Threshold"].default_value = 0.9
    g.inputs["Strength"].default_value = 0.25
    g.inputs["Size"].default_value = 0.5
    tree.links.new(rl.outputs["Image"], g.inputs["Image"])
    aura = []
    gain = float(os.environ.get("AURA_GAIN", "1.2"))
    for typ, size, k in (("Fog Glow", 0.6, 5.0), ("Bloom", 0.85, 4.0)):
        f = tree.nodes.new("CompositorNodeGlare")       # Strength is a 0..1 factor: amplify the glare after
        f.inputs["Type"].default_value = typ
        f.inputs["Quality"].default_value = "High"
        f.inputs["Threshold"].default_value = 0.0
        f.inputs["Strength"].default_value = 1.0
        f.inputs["Saturation"].default_value = 1.0
        f.inputs["Size"].default_value = size
        tree.links.new(rl.outputs["Emission"], f.inputs["Image"])
        sc_ = tree.nodes.new("ShaderNodeVectorMath")
        sc_.operation = "SCALE"
        sc_.inputs["Scale"].default_value = bloom * k * gain
        tree.links.new(f.outputs["Glare"], sc_.inputs[0])
        aura.append(sc_.outputs["Vector"])
    cur = g.outputs["Image"]
    for a_ in aura:
        m = tree.nodes.new("ShaderNodeMix")
        m.data_type = "RGBA"
        m.blend_type = "ADD"
        m.inputs["Factor"].default_value = 1.0
        tree.links.new(cur, m.inputs[6])
        tree.links.new(a_, m.inputs[7])
        cur = m.outputs[2]
    dbg = os.environ.get("COMP_DEBUG", "")
    tree.links.new({"emit": rl.outputs["Emission"], "glare": aura[0]}.get(dbg, cur), out.inputs[0])
    scene.compositing_node_group = tree


STAGE = {}


def clear_stage():
    for o in list(REVIEW.objects):
        bpy.data.objects.remove(o, do_unlink=True)


def catalog_stage(objs, angle, camvec, res=1000, samples=24, ortho_pad=1.18, world=0.0509, floor=True, extra_objs=(), yaw=0.0):
    clear_stage()
    saved = {o.name: o.matrix_world.copy() for o in objs}
    rot = Matrix.Rotation(math.radians(angle), 4, "Y") @ Matrix.Rotation(math.radians(yaw), 4, "Z")
    for o in objs:
        o.matrix_world = rot @ saved[o.name]
    bpy.context.view_layer.update()
    coords = world_bounds(objs)
    minz = min(c.z for c in coords)
    for o in objs:
        o.location.z -= minz
    bpy.context.view_layer.update()
    coords = world_bounds(list(objs) + list(extra_objs))
    mn = [min(c[i] for c in coords) for i in range(3)]
    mx = [max(c[i] for c in coords) for i in range(3)]
    center = Vector([(mn[i] + mx[i]) * 0.5 for i in range(3)])
    extent = max(mx[2] - mn[2], mx[0] - mn[0])
    cd = bpy.data.cameras.new("Review camera")
    cam = bpy.data.objects.new("Review camera", cd)
    REVIEW.objects.link(cam)
    cam.location = center + Vector(camvec) * extent / 5

    def point(o, p):
        o.rotation_euler = (Vector(p) - o.location).to_track_quat("-Z", "Y").to_euler()

    point(cam, center)
    cd.type = "ORTHO"
    bpy.context.view_layer.update()
    inv = cam.rotation_euler.to_matrix().transposed()
    pc = [inv @ (v - center) for v in coords]
    cd.ortho_scale = max(max(v[j] for v in pc) - min(v[j] for v in pc) for j in (0, 1)) * ortho_pad
    cd.clip_end = 500
    scene.camera = cam
    for name, off, power, sz in [("Key", (-4, -6, 9), 1000, 5), ("Fill", (5, -3, 6), 700, 4), ("Rim", (2, 5, 8), 1100, 4)]:
        ld = bpy.data.lights.new(name, "AREA")
        lo = bpy.data.objects.new(name, ld)
        REVIEW.objects.link(lo)
        lo.location = center + Vector(off) * extent / 5
        ld.energy = power * (extent / 5) ** 2
        ld.shape = "DISK"
        ld.size = sz * extent / 5
        point(lo, center)
    if floor:
        fme = bpy.data.meshes.new("Review floor")
        fme.from_pydata([(-100, -100, -0.04), (100, -100, -0.04), (100, 100, -0.04), (-100, 100, -0.04)], [], [(0, 1, 2, 3)])
        fo = bpy.data.objects.new("Review floor (not exported)", fme)
        REVIEW.objects.link(fo)
        fm = bpy.data.materials.get("Neutral floor") or bpy.data.materials.new("Neutral floor")
        fm.diffuse_color = (0.115, 0.12, 0.135, 1)
        fm.use_nodes = True
        fme.materials.append(fm)
    w = scene.world or bpy.data.worlds.new("World")
    scene.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (world, world, world, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
    scene.render.image_settings.file_format = "PNG"
    STAGE.update(center=center, extent=extent, cam=cam)

    def restore():
        for o in objs:
            o.matrix_world = saved[o.name]
        bpy.context.view_layer.update()

    return restore


def render(path):
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    log("rendered", Path(path).name)


PREVIEW_YAW = 28.0
VIEWS = {"Front": (0, -15, 1.2), "Back": (0, 15, 1.2), "Side": (-15, 0, 1.2)}

if MODE == "quick":
    setup_comp(0.6)
    objs = list(PARTS)
    r = catalog_stage(objs, 0, (1.6, -15, 6.2), res=700, samples=16, yaw=PREVIEW_YAW)
    render(OUT / "q_preview.png")
    r()
    for nm in os.environ.get("QSHOTS", "Front,Side").split(","):
        r = catalog_stage(objs, 0, VIEWS[nm], res=600, samples=12)
        render(OUT / f"q_{nm.lower()}.png")
        r()
    log("QUICK DONE")
    sys.exit(0)


# ===========================================================================
# FULL MODE: join, UV, painted masks, bake, export, render, validate
# ===========================================================================
def join(objs, name):
    select_only(objs)
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


_by_kind = {k: [o for o in PARTS if o["kind"] == k] for k in ("tex", "glow", "core")}
PART_TRIS = dict(TRIS)
body = join(_by_kind["tex"], NAME)
glow_ob = join(_by_kind["glow"], f"{NAME}_Glow")
core_ob = join(_by_kind["core"], f"{NAME}_GlowCore")
FINAL = [body, glow_ob, core_ob]
for o in FINAL:
    while o.data.uv_layers:
        o.data.uv_layers.remove(o.data.uv_layers[0])
    for a in [a.name for a in o.data.color_attributes]:
        o.data.color_attributes.remove(o.data.color_attributes[a])
for o, m in ((glow_ob, GLOW_MAT), (core_ob, CORE_MAT)):
    o.data.materials.clear()
    o.data.materials.append(m)
    for p in o.data.polygons:
        p.material_index = 0

body.data.uv_layers.new(name="UVMap")
select_only([body])
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(52), island_margin=0.003, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
bpy.ops.uv.pack_islands(rotate=True, margin=0.003)
bpy.ops.object.mode_set(mode="OBJECT")
for o in (glow_ob, core_ob):
    o.data.uv_layers.new(name="UVMap")
    select_only([o])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.01)
    bpy.ops.object.mode_set(mode="OBJECT")
log("uv done")


def corner_arrays(me):
    nl, npoly = len(me.loops), len(me.polygons)
    vi = np.empty(nl, np.int32)
    me.loops.foreach_get("vertex_index", vi)
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    pn = np.empty(npoly * 3, np.float32)
    me.polygons.foreach_get("normal", pn)
    pm = np.empty(npoly, np.int32)
    me.polygons.foreach_get("material_index", pm)
    lt = np.empty(npoly, np.int32)
    me.polygons.foreach_get("loop_total", lt)
    lp = np.repeat(np.arange(npoly), lt)
    return co[vi], pn.reshape(-1, 3)[lp], pm[lp]


def np_smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


P, NRM, MI = corner_arrays(body.data)
NL = len(P)
paint = np.ones((NL, 3), np.float32)
ZT = float(P[:, 2].max())
for mi, lo_, hi_ in ((M_CRIM, 0.62, 0.5), (M_STEEL, 0.75, 0.4), (M_RUB, 0.8, 0.35)):
    sel = MI == mi
    if sel.any():
        t = np_smooth(0.0, ZT, P[sel][:, 2])
        paint[sel] *= (lo_ + hi_ * t)[:, None]

gP, gA, gC = [], [], []
for ob, col in ((glow_ob, GLOW), (core_ob, CORE)):
    me = ob.data
    c = np.empty(len(me.polygons) * 3, np.float32)
    me.polygons.foreach_get("center", c)
    a = np.empty(len(me.polygons), np.float32)
    me.polygons.foreach_get("area", a)
    gP.append(c.reshape(-1, 3))
    gA.append(a)
    gC.append(np.tile(np.array(rgba(GLOW)[:3], np.float32), (len(a), 1)))   # bleed light is the saturated green
gP, gA, gC = np.concatenate(gP), np.concatenate(gA), np.concatenate(gC)
bleed = np.zeros((NL, 3), np.float32)
for i0 in range(0, NL, 1500):
    i1 = min(NL, i0 + 1500)
    Ld = gP[None, :, :] - P[i0:i1, None, :]
    d = np.linalg.norm(Ld, axis=2) + 1e-6
    wrap = np.clip(np.einsum("cgk,ck->cg", Ld, NRM[i0:i1]) / d * 0.75 + 0.25, 0, 1)
    w = gA[None, :] * wrap * np.exp(-d / 0.06) / (d * d + 0.03 ** 2)
    bleed[i0:i1] = w @ gC
bleed = (1 - np.exp(-BLEED_K * bleed)) * BLEED_STRENGTH
bleed[MI == M_CRIM] *= 0.4          # green light on red paint reads as mud: keep it faint
for nm, arr in (("Paint", paint), ("Bleed", bleed)):
    at = body.data.color_attributes.new(nm, "FLOAT_COLOR", "CORNER")
    at.data.foreach_set("color", np.concatenate([arr, np.ones((NL, 1), np.float32)], axis=1).ravel())
log("masks done")

KEY_DIR = V(-0.45, -0.6, 0.75).normalized()
RIM_DIR = V(0.7, 0.6, 0.25).normalized()
ZTOP = max(p.z for p in world_bounds([body]))
# painted chrome: environment bands by facet normal z (warm ground, dark horizon line, bright cool sky)
METAL_BANDS = {
    M_GOLD: [(0.0, (62, 32, 8)), (0.30, (124, 72, 20)), (0.44, (170, 108, 30)), (0.485, (92, 50, 12)), (0.535, (250, 200, 86)),
             (0.64, (206, 140, 40)), (0.85, (236, 178, 66)), (1.0, (255, 220, 120))],
    M_STEEL: [(0.0, (30, 28, 30)), (0.30, (48, 46, 48)), (0.44, (60, 60, 66)), (0.485, (12, 14, 22)), (0.535, (120, 134, 158)),
              (0.64, (40, 48, 64)), (0.85, (70, 82, 104)), (1.0, (118, 132, 156))],
}


def build_bake_shader(idx, mat, img):
    name, flat_c, ramp, edge_c = PAL[idx]
    nt = mat.node_tree
    nt.nodes.clear()
    N, L = nt.nodes.new, nt.links.new

    def val(v):
        n = N("ShaderNodeValue")
        n.outputs[0].default_value = v
        return n.outputs[0]

    def math_(op, a, b):
        n = N("ShaderNodeMath")
        n.operation = op
        for i, x in enumerate((a, b)):
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                L(x, n.inputs[i])
        return n.outputs[0]

    def remap(sock, a, b, lo, hi):
        r = N("ShaderNodeMapRange")
        r.inputs["From Min"].default_value, r.inputs["From Max"].default_value = a, b
        r.inputs["To Min"].default_value, r.inputs["To Max"].default_value = lo, hi
        L(sock, r.inputs["Value"])
        return r.outputs["Result"]

    def mix(a, b, fac, blend="MIX"):
        m = N("ShaderNodeMix")
        m.data_type = "RGBA"
        m.blend_type = blend
        for sock, x in ((m.inputs[6], a), (m.inputs[7], b)):
            if isinstance(x, tuple):
                sock.default_value = x
            else:
                L(x, sock)
        if isinstance(fac, (int, float)):
            m.inputs["Factor"].default_value = fac
        else:
            L(fac, m.inputs["Factor"])
        return m.outputs[2]

    def grey(sock):
        c = N("ShaderNodeCombineColor")
        for i in range(3):
            L(sock, c.inputs[i])
        return c.outputs[0]

    def ramp_node(stops, fac):
        rp = N("ShaderNodeValToRGB")
        el = rp.color_ramp.elements
        el[0].position, el[0].color = stops[0][0], rgba(stops[0][1])
        el[1].position, el[1].color = stops[-1][0], rgba(stops[-1][1])
        for p_, c_ in stops[1:-1]:
            e = el.new(p_)
            e.color = rgba(c_)
        L(fac, rp.inputs["Fac"])
        return rp.outputs["Color"]

    geo = N("ShaderNodeNewGeometry")
    pos = geo.outputs["Position"]
    tn = geo.outputs["True Normal"]

    def dot_light(d):
        v = N("ShaderNodeVectorMath")
        v.operation = "DOT_PRODUCT"
        L(tn, v.inputs[0])
        v.inputs[1].default_value = d
        return math_("MAXIMUM", v.outputs["Value"], 0.0)

    n1 = N("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = 2.4
    n1.inputs["Detail"].default_value = 2.0
    n1.inputs["Roughness"].default_value = 0.45
    n1.inputs["Distortion"].default_value = 0.35
    L(pos, n1.inputs["Vector"])
    n2 = N("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 7.0
    n2.inputs["Detail"].default_value = 1.0
    L(pos, n2.inputs["Vector"])
    nmix = math_("ADD", n1.outputs["Fac"], math_("MULTIPLY", math_("SUBTRACT", n2.outputs["Fac"], 0.5), 0.4))
    base = ramp_node(ramp, nmix)
    pa = N("ShaderNodeAttribute")
    pa.attribute_name = "Paint"
    if idx in METAL_BANDS:
        sn = N("ShaderNodeSeparateXYZ")
        L(tn, sn.inputs["Vector"])
        nz = math_("ADD", math_("MULTIPLY", sn.outputs["Z"], 0.5), 0.5)
        wob = math_("MULTIPLY", math_("SUBTRACT", n1.outputs["Fac"], 0.5), 0.06)      # painterly wobble of the band
        bands = ramp_node(METAL_BANDS[idx], math_("ADD", nz, wob))
        albedo = mix(bands, grey(remap(n2.outputs["Fac"], 0.3, 0.7, 0.94, 1.05)), 1.0, "MULTIPLY")
        light_lo, light_hi = 0.78, 1.15
    else:
        albedo = base
        light_lo, light_hi = 0.56, 1.2
        if idx in (M_CRIM, M_DRED):      # glossy painted metal: a warm sheen on up-facing facets
            sn = N("ShaderNodeSeparateXYZ")
            L(tn, sn.inputs["Vector"])
            albedo = mix(albedo, rgba((206, 64, 58)), remap(sn.outputs["Z"], 0.5, 0.95, 0.0, 0.26))
    albedo = mix(albedo, pa.outputs["Color"], 1.0, "MULTIPLY")
    k = dot_light(KEY_DIR)
    light = remap(k, 0.0, 1.0, light_lo, light_hi)
    tint = mix((0.9, 0.92, 1.06, 1), (1.05, 1.0, 0.95, 1), k)
    ao = N("ShaderNodeAmbientOcclusion")
    ao.samples = 16
    ao.inputs["Distance"].default_value = 0.2
    aof = remap(ao.outputs["AO"], 0.2, 1.0, 0.5, 1.0)
    cav = N("ShaderNodeAmbientOcclusion")
    cav.samples = 16
    cav.inputs["Distance"].default_value = 0.035
    cavf = remap(cav.outputs["AO"], 0.35, 1.0, 0.6, 1.0)
    sep = N("ShaderNodeSeparateXYZ")
    L(pos, sep.inputs["Vector"])
    height = remap(sep.outputs["Z"], 0.0, ZTOP, 0.92, 1.05)
    shade = math_("MULTIPLY", math_("MULTIPLY", light, aof), math_("MULTIPLY", cavf, height))
    lit = mix(mix(albedo, tint, 1.0, "MULTIPLY"), grey(shade), 1.0, "MULTIPLY")
    rim = remap(dot_light(RIM_DIR), 0.25, 1.0, 0.0, 0.07)
    lit = mix(lit, (0.55, 0.6, 0.75, 1), rim, "ADD")
    bev = N("ShaderNodeBevel")
    bev.samples = 8
    bev.inputs["Radius"].default_value = 0.012
    ed = N("ShaderNodeVectorMath")
    ed.operation = "DOT_PRODUCT"
    L(bev.outputs["Normal"], ed.inputs[0])
    L(tn, ed.inputs[1])
    e = remap(ed.outputs["Value"], 0.99, 0.84, 0.0, 1.0)
    convex = remap(cav.outputs["AO"], 0.86, 0.97, 0.0, 1.0)
    efac = math_("MULTIPLY", math_("MULTIPLY", e, convex), remap(k, 0.0, 1.0, 0.5, 0.9))
    ecol = mix(albedo, rgba(edge_c), 0.65)
    lit = mix(lit, mix(ecol, grey(val(1.2)), 1.0, "MULTIPLY"), efac)
    if idx == M_CRIM:      # worn paint: chips on exposed edges show bare steel
        n3 = N("ShaderNodeTexNoise")
        n3.inputs["Scale"].default_value = 16.0
        n3.inputs["Detail"].default_value = 3.0
        L(pos, n3.inputs["Vector"])
        chip = math_("MULTIPLY", efac, remap(n3.outputs["Fac"], 0.58, 0.66, 0.0, 1.0))
        lit = mix(lit, rgba((150, 136, 132)), math_("MULTIPLY", chip, 0.6))
    ba = N("ShaderNodeAttribute")
    ba.attribute_name = "Bleed"
    lit = mix(lit, ba.outputs["Color"], 1.0, "ADD")
    em = N("ShaderNodeEmission")
    L(lit, em.inputs["Color"])
    out = N("ShaderNodeOutputMaterial")
    L(em.outputs["Emission"], out.inputs["Surface"])
    target = N("ShaderNodeTexImage")
    target.image = img
    nt.nodes.active = target


CHECK = MODE == "bakecheck"      # cheap bake + one preview into OUT, no exports
BAKE_RES = 1024 if CHECK else 2048
TEXDIR = OUT if CHECK else ROOT
bake_img = bpy.data.images.new(f"{NAME}_bake", BAKE_RES, BAKE_RES, alpha=False)
for i, m in enumerate(MATS):
    build_bake_shader(i, m, bake_img)
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 10 if CHECK else 40
scene.render.bake.margin = 16
select_only([body])
t_b = time.time()
bpy.ops.object.bake(type="EMIT")
log(f"bake {time.time() - t_b:.0f}s")
px = np.empty(BAKE_RES * BAKE_RES * 4, np.float32)
bake_img.pixels.foreach_get(px)
px = px.reshape(BAKE_RES, BAKE_RES, 4)
f = BAKE_RES // BAKE_SIZE
small = px.reshape(BAKE_SIZE, f, BAKE_SIZE, f, 4).mean(axis=(1, 3))
tex_img = bpy.data.images.new(f"{NAME}_BaseColor_tmp", BAKE_SIZE, BAKE_SIZE, alpha=False)
tex_img.pixels.foreach_set(small.ravel())
tex_img.filepath_raw = str(TEXDIR / "BaseColor.png")
tex_img.file_format = "PNG"
tex_img.save()
bpy.data.images.remove(bake_img)
bpy.data.images.remove(tex_img)
tex_img = bpy.data.images.load(str(TEXDIR / "BaseColor.png"))
tex_img.name = f"{NAME}_BaseColor"
tex_img.pack()

final_mat = bpy.data.materials.new(f"{NAME}_Baked")
final_mat.use_nodes = True
bs = final_mat.node_tree.nodes["Principled BSDF"]
bs.inputs["Roughness"].default_value = 0.55
bs.inputs["Specular IOR Level"].default_value = 0.3
tx = final_mat.node_tree.nodes.new("ShaderNodeTexImage")
tx.image = tex_img
final_mat.node_tree.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
body.data.materials.clear()
body.data.materials.append(final_mat)
for p in body.data.polygons:
    p.material_index = 0
for nm in ("Paint", "Bleed"):
    body.data.color_attributes.remove(body.data.color_attributes[nm])
for m in MATS:
    bpy.data.materials.remove(m)
log("texture done")
if CHECK:
    setup_comp(0.6)
    r = catalog_stage(FINAL, 0, (1.6, -15, 6.2), res=700, samples=20, yaw=PREVIEW_YAW)
    render(OUT / "check_preview.png")
    r()
    r = catalog_stage(FINAL, 0, VIEWS["Back"], res=600, samples=16)
    render(OUT / "check_back.png")
    sys.exit(0)

select_only(FINAL, body)
bpy.ops.export_scene.gltf(filepath=str(ROOT / "Model.glb"), export_format="GLB", use_selection=True, export_apply=True)
bpy.ops.export_scene.fbx(filepath=str(ROOT / "Model.fbx"), use_selection=True, object_types={"MESH"}, axis_forward="-Z",
                         axis_up="Y", path_mode="COPY", embed_textures=True, add_leaf_bones=False, mesh_smooth_type="OFF")
log("exported")


def mesh_stats(ob):
    me = ob.data
    me.calc_loop_triangles()
    bm = bmesh.new()
    bm.from_mesh(me)
    loose = sum(1 for v in bm.verts if not v.link_faces)
    zero = sum(1 for f in bm.faces if f.calc_area() < 1e-9)
    nonman = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    co = np.array([tuple(v.co) for v in me.vertices])
    mn, mx = co.min(axis=0), co.max(axis=0)
    return {"triangles": len(me.loop_triangles), "vertices": len(me.vertices), "loose_vertices": loose,
            "zero_area_faces": zero, "non_manifold_edges": nonman, "bounds_min": [round(float(x), 4) for x in mn],
            "bounds_max": [round(float(x), 4) for x in mx]}


def studio(v):
    return [round(-float(v[0]), 4), round(float(v[2]), 4), round(float(v[1]), 4)]


def studio_size(v):
    return [round(float(v[0]), 4), round(float(v[2]), 4), round(float(v[1]), 4)]


STATS = {o.name: mesh_stats(o) for o in FINAL}
GRIP = XF(GRIP_TOP.lerp(GRIP_BOT, 0.55))
MUZZLE = XF(V(-MUZZLE_T, 0, AX))
COIL = XF(V(0.09, 0, AX))
allmn = np.min([s["bounds_min"] for s in STATS.values()], axis=0)
allmx = np.max([s["bounds_max"] for s in STATS.values()], axis=0)
tex_c = (np.array(STATS[NAME]["bounds_min"]) + np.array(STATS[NAME]["bounds_max"])) / 2


def rel(p):
    return studio(np.array(tuple(p)) - tex_c)


install = {
    "name": NAME, "blender_version": bpy.app.version_string, "status": "Blender-verified, Studio untested",
    "units": "1 Blender unit = 1 stud, authored at hero size (about 3.2 studs long); suggested play scale 0.65-0.7 "
             "(about 2.1-2.3 studs long in a 5-stud R15 hand)",
    "axes": "Studio = (-x, z, y) of Blender; FBX exported with axis_forward=-Z, axis_up=Y. The barrel points along Blender -x "
            "= Studio +X in the exported frame.",
    "texture": f"BaseColor.png {BAKE_SIZE}x{BAKE_SIZE}, baked painted lighting; use MeshPart.TextureID (not SurfaceAppearance)",
    "parts": {},
    "grip_point_studio": studio(GRIP),
    "grip_point_relative_to_textured_center": rel(GRIP),
    "grip_axis_studio_down": studio(GRIP_AXIS),
    "muzzle_attachment_studio": studio(MUZZLE),
    "muzzle_attachment_relative_to_textured_center": rel(MUZZLE),
    "muzzle_direction_studio": [1.0, 0.0, 0.0],
    "chamber_light_point_relative_to_textured_center": rel(COIL),
    "notes": ["Every MeshPart imports centred on its own bounding box: place each at its center_studio relative to a shared "
              "model origin (Blender origin = grip-bottom level, on the gun's mirror plane).",
              "grip_point = middle of the ribbed black grip on its axis (hand attachment). The grip is raked back about 8 degrees; "
              "grip_axis_studio_down points from the top of the grip to the pommel.",
              "muzzle_attachment = tip of the emitter bead in front of the flared muzzle: put an Attachment named Muzzle here, "
              "facing muzzle_direction_studio; projectiles and the muzzle flash spawn from it."],
}
for o in FINAL:
    st = STATS[o.name]
    mn, mx = np.array(st["bounds_min"]), np.array(st["bounds_max"])
    kind = "textured" if o is body else "glow"
    part = {"kind": kind, "center_studio": studio((mn + mx) / 2), "size_studio": studio_size(mx - mn), "triangles": st["triangles"]}
    if o is glow_ob:
        part.update(material="Neon", color_rgb=list(GLOW),
                    note="hot green: glass energy chamber, muzzle mouth, dial charge arc, side vent lines")
    elif o is core_ob:
        part.update(material="Neon", color_rgb=list(CORE), note="pale-hot plasma: crackles on the glass, emitter bead")
    else:
        part.update(material="SmoothPlastic (or Plastic), Color white", texture_id="BaseColor.png")
    install["parts"][o.name] = part
install["vfx_notes"] = [
    "Blast projectile (spawn at the Muzzle attachment, travel along muzzle_direction): a Neon ball 0.7 studs, Color (16,255,40), "
    "with an inner Neon ball 0.35 studs Color (140,255,110); a Trail (Color (16,255,40) -> (10,120,40), Lifetime 0.12, "
    "WidthScale 1 -> 0, LightEmission 1, Transparency 0.1 -> 1) and a PointLight Color (16,255,40), Brightness 2, Range 8. "
    "Suggested speed 120-150 studs/s; on impact a small burst: ParticleEmitter Burst 8, Color (140,255,110) -> (16,255,40), "
    "Size 0.5 -> 0, Lifetime 0.15-0.25, Speed 6-10, SpreadAngle 180, LightEmission 1.",
    "Muzzle flash per shot: at the Muzzle attachment, ParticleEmitter Burst 6, Color (140,255,110) -> (16,255,40), "
    "Size 0.9 -> 0, Lifetime 0.08-0.12, Speed 3-6, SpreadAngle 25, LightEmission 1, LockedToPart true; plus a flat Neon "
    "ring (the dish's emitter ring echo) scaling 0.6 -> 1.6 studs while Transparency 0.2 -> 1 over 0.12 s.",
    "Disintegrate burst on kill (the ability): at the dead enemy's HumanoidRootPart. Tween every enemy part to Material "
    "Neon, Color (16,255,40), Transparency 0 -> 1 over 0.3 s while it shrinks to 60%. At the same moment spawn a Neon "
    "sphere shell Color (16,255,40), Transparency 0.35 -> 1, growing from 1 stud to the burst's hit diameter (2 x the "
    "splash radius set in the Godly spec, about 8-10 studs across) over 0.25 s, so players see exactly what the burst hits. "
    "Particles: ParticleEmitter Burst 30 square 'pixel' bits (a small square texture), Color (140,255,110) -> (16,255,40) "
    "-> (10,90,30), Size 0.45 -> 0, Lifetime 0.5-0.9, Speed 10-18, SpreadAngle 180, Drag 4, Acceleration (0,4,0), "
    "RotSpeed -180..180, LightEmission 1; plus a PointLight Color (16,255,40), Brightness 3 -> 0 over 0.3 s, Range 12.",
    "Chained enemies hit by the burst: a short zap Beam from the burst centre to each one (Color (16,255,40), Width 0.4, "
    "LightEmission 1, CurveSize0/1 random +-2, visible 0.1 s) and a Burst 6 of the same pixel bits on them.",
    "Idle: PointLight at chamber_light_point, Color (16,255,40), Brightness 1.5, Range 6; a slow ParticleEmitter on the glass "
    "chamber, Rate 6, Color (16,255,40), Size 0.15 -> 0, Lifetime 0.3, Speed 0.5, LightEmission 1 (sparks crawling the coil).",
]
(ROOT / "studio-install-data.json").write_text(json.dumps(install, indent=1))
log("stats", {k: v["triangles"] for k, v in STATS.items()}, "total", sum(v["triangles"] for v in STATS.values()))

# ---------------------------------------------------------------------------
# Renders: Preview, Front, Back, Side, Scale, Hero (the brief's set only)
# ---------------------------------------------------------------------------
setup_comp(0.6)


def shoot_catalog(name, angle, camvec, samples=32, res=1000, yaw=0.0):
    r = catalog_stage(FINAL, angle, camvec, samples=samples, res=res, yaw=yaw)
    render(ROOT / name)
    r()


shoot_catalog("Preview.png", 0, (1.6, -15, 6.2), samples=48, yaw=PREVIEW_YAW)
for nm, vec in VIEWS.items():
    shoot_catalog(f"{nm}.png", 0, vec)

# scale shot: a 5-stud grey R15 block figure beside the gun (gun shown at its authored hero size)
fig_bm = new_bm()
gb = world_bounds(FINAL)
FX = max(p.x for p in gb) + 1.9
for c, sz in (((FX - 0.5, 0, 1.0), (1.0, 1.0, 2.0)), ((FX + 0.5, 0, 1.0), (1.0, 1.0, 2.0)), ((FX, 0, 3.0), (2.0, 1.0, 2.0)),
              ((FX - 1.5, 0, 3.0), (1.0, 1.0, 2.0)), ((FX + 1.5, 0, 3.0), (1.0, 1.0, 2.0)), ((FX, 0, 4.5), (1.15, 1.15, 1.0))):
    hx, hy, hz = sz[0] / 2, sz[1] / 2, sz[2] / 2
    cc = V(*c)
    loft(fig_bm, [[cc + V(-hx, -hy, -hz), cc + V(hx, -hy, -hz), cc + V(hx, hy, -hz), cc + V(-hx, hy, -hz)],
                  [cc + V(-hx, -hy, hz), cc + V(hx, -hy, hz), cc + V(hx, hy, hz), cc + V(-hx, hy, hz)]])
fig = make_obj("R15 block figure 5 studs (not exported)", fig_bm, kind="fig", coll=WORK)
fm = bpy.data.materials.new("Figure grey")
fm.use_nodes = True
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.38, 0.38, 0.4, 1)
fig.data.materials.clear()
fig.data.materials.append(fm)
add_bevel(fig, 0.06, segs=2, angle=40)
r = catalog_stage(FINAL, 0, (0.6, -15, 2.5), samples=32, extra_objs=[fig])
render(ROOT / "Scale.png")
r()
bpy.data.objects.remove(fig, do_unlink=True)


def hero(name, cam_loc, target, lens=50, res=(1400, 1100), samples=96):
    clear_stage()
    w = scene.world
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.012, 0.02, 0.024, 1)
    cd = bpy.data.cameras.new("Hero camera")
    cam = bpy.data.objects.new("Hero camera", cd)
    REVIEW.objects.link(cam)
    cd.lens = lens
    cam.location = cam_loc
    cam.rotation_euler = (target - cam_loc).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    for nm, off, col, en, sz in (("Hero key", V(-3, -5, 6), (0.95, 0.9, 0.85), 1500, 4),
                                 ("Hero rim green", V(3, 5, 4), (0.15, 1.0, 0.3), 1800, 3),
                                 ("Hero rim steel", V(-4, 4, 4), (0.6, 0.75, 1.0), 800, 3),
                                 ("Hero fill teal", V(2, -4, 0.0), (0.3, 0.8, 0.8), 160, 4)):
        ld = bpy.data.lights.new(nm, "AREA")
        ld.color = col
        ld.energy = en
        ld.size = sz
        lo = bpy.data.objects.new(nm, ld)
        REVIEW.objects.link(lo)
        lo.location = target + off
        lo.rotation_euler = (target - lo.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Punchy"
    except TypeError:
        pass
    setup_comp(0.8)
    render(ROOT / name)
    scene.view_settings.look = "None"
    setup_comp(0.6)


gb = world_bounds(FINAL)
gmn = V(*[min(p[i] for p in gb) for i in range(3)])
gmx = V(*[max(p[i] for p in gb) for i in range(3)])
gc = (gmn + gmx) / 2
hero("Hero.png", gc + V(-3.0, -4.6, 1.5), gc + V(-0.15, 0, -0.05), lens=50)

catalog_stage(FINAL, 0, VIEWS["Front"])
for o in FINAL:
    o.select_set(True)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "Model.blend"))
log("blend saved")


# ---------------------------------------------------------------------------
# Contact sheet + catalogue comparison (Blender-composited image planes with labels)
# ---------------------------------------------------------------------------
def compose(tiles, cols, cell, out_path, label_px=46, title=None, bg=(238, 237, 235)):
    sc = bpy.data.scenes.new("Compose")
    rows = math.ceil(len(tiles) / cols)
    title_px = 64 if title else 0
    Wpx, Hpx = cols * cell, rows * (cell + label_px) + title_px
    U = 0.01

    def emit_img_mat(img):
        m = bpy.data.materials.new("cmp_" + img.name)
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = img
        e = nt.nodes.new("ShaderNodeEmission")
        o = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(t.outputs["Color"], e.inputs["Color"])
        nt.links.new(e.outputs["Emission"], o.inputs["Surface"])
        return m

    tm = bpy.data.materials.new("cmp_text")
    tm.use_nodes = True
    tm.node_tree.nodes.clear()
    e = tm.node_tree.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (0.02, 0.02, 0.02, 1)
    o = tm.node_tree.nodes.new("ShaderNodeOutputMaterial")
    tm.node_tree.links.new(e.outputs["Emission"], o.inputs["Surface"])

    def text(body_, x, y, size):
        cu = bpy.data.curves.new("cmp_label", "FONT")
        cu.body = body_
        cu.size = size * U
        cu.align_x = "CENTER"
        cu.align_y = "CENTER"
        ob = bpy.data.objects.new("cmp_label", cu)
        ob.data.materials.append(tm)
        ob.location = (x, y, 0.01)
        sc.collection.objects.link(ob)

    for i, (path, label) in enumerate(tiles):
        if not Path(path).exists():
            continue
        rr, cc = divmod(i, cols)
        img = bpy.data.images.load(str(path), check_existing=False)
        w, h = img.size
        s_ = min((cell - 12) / w, (cell - 12) / h)
        pw, ph = w * s_ * U / 2, h * s_ * U / 2
        cx = (cc * cell + cell / 2 - Wpx / 2) * U
        cy = (Hpx / 2 - title_px - rr * (cell + label_px) - cell / 2) * U
        me = bpy.data.meshes.new("cmp_plane")
        me.from_pydata([(cx - pw, cy - ph, 0), (cx + pw, cy - ph, 0), (cx + pw, cy + ph, 0), (cx - pw, cy + ph, 0)], [], [(0, 1, 2, 3)])
        uv = me.uv_layers.new(name="UVMap")
        for li, c_ in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
            uv.data[li].uv = c_
        me.materials.append(emit_img_mat(img))
        ob = bpy.data.objects.new("cmp_plane", me)
        sc.collection.objects.link(ob)
        text(label, cx, cy - (cell / 2 + label_px * 0.45) * U, 24)
    if title:
        text(title, 0, (Hpx / 2 - title_px / 2) * U, 30)
    cd = bpy.data.cameras.new("cmp_cam")
    cd.type = "ORTHO"
    cd.ortho_scale = max(Wpx, Hpx) * U
    cam = bpy.data.objects.new("cmp_cam", cd)
    cam.location = (0, 0, 10)
    sc.collection.objects.link(cam)
    sc.camera = cam
    wd = bpy.data.worlds.new("cmp_world")
    wd.use_nodes = True
    wd.node_tree.nodes["Background"].inputs["Color"].default_value = rgba(bg)
    sc.world = wd
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = Wpx, Hpx
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = str(out_path)
    sc.render.film_transparent = False
    bpy.ops.render.render(write_still=True, scene=sc.name)
    log("composed", Path(out_path).name)


ASSETS = ROOT.parents[1] / "assets"
compose([(ROOT / "Preview.png", "Ray Gun (Godly, new)"), (ASSETS / "32-excalibur" / "Preview.png", "Excalibur"),
         (ASSETS / "31-mjolnir" / "Preview.png", "Mjolnir"), (ASSETS / "34-medusas-head" / "Preview.png", "Medusa's Head"),
         (ASSETS / "08-fart-gun" / "Preview.png", "Fart Gun (closest catalogue gun)")],
        5, 600, ROOT / "Compare_Catalog.png", title="Catalogue framing: Godly Ray Gun beside the current top tier and the Fart Gun")
compose([(ROOT / "Preview.png", "Preview (catalogue 3/4)"), (ROOT / "Front.png", "Front (left side)"),
         (ROOT / "Back.png", "Back (right side)"), (ROOT / "Side.png", "Side (muzzle-on)"),
         (ROOT / "Hero.png", "Hero (Cycles, dark stage)"), (ROOT / "Scale.png", "Scale: 5-stud R15 block figure"),
         (ROOT / "BaseColor.png", "BaseColor.png (1024, baked)")],
        4, 560, ROOT / "Sheet.png", title="Ray Gun - Godly ranged (Blender renders, Studio untested)")

# ---------------------------------------------------------------------------
# Validation (reimport both exports into a fresh file)
# ---------------------------------------------------------------------------
report = {
    "name": NAME, "blender_version": bpy.app.version_string, "authored_scale_factor": SCALE,
    "meshes": {k: v for k, v in STATS.items()},
    "part_triangles_before_join": PART_TRIS,
    "total_triangles": sum(v["triangles"] for v in STATS.values()),
    "total_vertices": sum(v["vertices"] for v in STATS.values()),
    "mesh_count": len(FINAL),
    "materials": {NAME: final_mat.name, f"{NAME}_Glow": GLOW_MAT.name, f"{NAME}_GlowCore": CORE_MAT.name},
    "texture": {"file": "BaseColor.png", "size": list(tex_img.size), "packed_in_blend": bool(tex_img.packed_file),
                "uv_layers": [l.name for l in body.data.uv_layers]},
    "bounds_blender_min": [round(float(x), 4) for x in allmn], "bounds_blender_max": [round(float(x), 4) for x in allmx],
    "bounds_studio_size": studio_size(allmx - allmn),
}
uvd = np.empty(len(body.data.loops) * 2, np.float32)
body.data.uv_layers["UVMap"].data.foreach_get("uv", uvd)
report["texture"]["uv_range"] = [round(float(uvd.min()), 4), round(float(uvd.max()), 4)]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(ROOT / "Model.glb"))
g = [o for o in bpy.data.objects if o.type == "MESH"]
for o in g:
    o.data.calc_loop_triangles()
report["glb_reimport"] = {"meshes": len(g), "triangles": sum(len(o.data.loop_triangles) for o in g),
                          "names": sorted(o.name for o in g),
                          "images": sorted(f"{i.name} {i.size[0]}x{i.size[1]}" for i in bpy.data.images if i.size[0] > 0)}
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(ROOT / "Model.fbx"))
g = [o for o in bpy.data.objects if o.type == "MESH"]
for o in g:
    o.data.calc_loop_triangles()
imgs = [i for i in bpy.data.images if i.source == "FILE"]
report["fbx_reimport"] = {"meshes": len(g), "triangles": sum(len(o.data.loop_triangles) for o in g),
                          "names": sorted(o.name for o in g),
                          "embedded_images": sorted(f"{i.name} {i.size[0]}x{i.size[1]}" for i in imgs),
                          "dimensions_after_axis_conversion": {o.name: [round(x, 3) for x in o.dimensions] for o in g}}
report["checks"] = {
    "loose_vertices_total": sum(v["loose_vertices"] for v in STATS.values()),
    "zero_area_faces_total": sum(v["zero_area_faces"] for v in STATS.values()),
    "glb_triangles_match": report["glb_reimport"]["triangles"] == report["total_triangles"],
    "fbx_triangles_match": report["fbx_reimport"]["triangles"] == report["total_triangles"],
    "every_mesh_under_20k": all(v["triangles"] < 20000 for v in STATS.values()),
}
report["notes"] = [
    "Non-manifold edge counts are expected: the textured mesh is many closed shells that overlap by design (ribs on the "
    "receiver, fins sunk into the body, prongs into the dish), and the meter frames/torus are open where hidden.",
    "Studio import, Neon look and in-game scale are untested (no Studio access in this task).",
]
(ROOT / "validation.json").write_text(json.dumps(report, indent=1))
log("VALIDATION", json.dumps(report["checks"]), "tris", report["total_triangles"])
log("DONE")
