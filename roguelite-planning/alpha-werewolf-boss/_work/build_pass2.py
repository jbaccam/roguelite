"""Blood Moon Alpha (Frozen Pass round-10 leader): sculpt, bake, rig, turnaround.

Blender 5.2 background, run from this folder:
    blender -b --factory-startup --threads 4 --python-exit-code 1 --python build_alpha_werewolf.py
    (AW_QUICK=1: coarse voxels, no cavity pass, Workbench shape-check renders only)

Then animate_game.py (clips, checks, game package) and validate_exports.py.

Base: the regular werewolf (mob-production/reference-rebuilds/build_werewolf.py).
Its helpers are copied here, nothing is imported or exec'd from sibling folders.
Authored in werewolf-scale base units, then scaled by K = 1.3 so 1 unit = 1 stud.
Axes: faces -Y, +Z up, anatomical Left at +X (matches king-crab-boss and
frost-cyclops-boss; the regular werewolf names its bones the other way round).
Reference: art-references/round-10-modeling-pack-2026-10-09/05-alpha-werewolf.png
"""
import bpy, bmesh, math, random, json, os, hashlib, time
from pathlib import Path
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

OUT = Path(__file__).resolve().parent
K = 1.27     # raised head + bigger ears keep the ear tips at ~1.3x the regular werewolf
QUICK = os.environ.get('AW_QUICK') == '1'
NAME = 'AlphaWolf'
rng = random.Random(1310)
T0 = time.time()


def log(*a):
    print('[AW %5.0fs]' % (time.time() - T0), *a, flush=True)


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.save_version = 0
scene = bpy.context.scene

# ------------------------------------------------------------------ palette
# sRGB albedo. Sampled from the sheet (k-means of figure pixels), then lifted and
# kept clean/saturated because Studio adds +0.3 saturation and the sheet is lit grey.
# Studio light is a warm sun + strong blue sky ambient + saturation +0.3, and the
# Blood Moon event adds a red tint: whites are ivory/bone and charcoals lean warm so
# nothing drifts blue or lime.
COL = {'fur': (104, 52, 44), 'mane': (48, 40, 38), 'cream': (222, 196, 164), 'inner': (214, 180, 156),
       'brow': (50, 42, 40), 'claw': (34, 28, 26), 'nose': (30, 25, 24), 'eye': (255, 150, 30),
       'pupil': (20, 12, 10), 'fang': (228, 212, 178), 'mouth': (84, 26, 32), 'tongue': (150, 56, 62),
       'shorts': (62, 55, 52), 'belt': (106, 72, 46), 'buckle': (62, 48, 38)}


def srgb(c):
    return tuple(((v / 255 + .055) / 1.055) ** 2.4 for v in c)


MATS = {}


def paint(key, layers=(), variation=.09, scale=.85):
    """Clean colour fields: the base colour and optional layers mixed by soft
    per-vertex masks (e.g. ManeMask, CreamMask), so boundaries are gradients, not
    per-face speckles. Then broad painterly value patches (object-space noise),
    the baked Cavity attribute, a per-lobe Clump tint and a little top light.
    Baked to the section's 1024 map later."""
    name = 'AW_' + key + ''.join('+' + k for k, a in layers)
    if name in MATS:
        return MATS[name]
    color = srgb(COL[key])
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = (*color, 1)
    nt = m.node_tree
    n = nt.nodes
    l = nt.links
    p = n.get('Principled BSDF')
    p.inputs['Roughness'].default_value = .86
    p.inputs['Specular IOR Level'].default_value = .15

    def vm(op, a=None, b=None):
        v = n.new('ShaderNodeVectorMath')
        v.operation = op
        for i, x in ((0, a), (1, b)):
            if x is None:
                continue
            if isinstance(x, tuple):
                v.inputs[i].default_value = x
            else:
                l.new(x, v.inputs[i])
        return v

    def attr(name_):
        at = n.new('ShaderNodeAttribute')
        at.attribute_name = name_
        at.attribute_type = 'GEOMETRY'
        return at.outputs['Fac']

    cur = vm('ADD', tuple(color), (0, 0, 0)).outputs['Vector']
    for k, a in layers:
        diff = vm('SUBTRACT', tuple(srgb(COL[k])), cur)
        sc = vm('SCALE', diff.outputs['Vector'])
        l.new(attr(a), sc.inputs['Scale'])
        cur = vm('ADD', cur, sc.outputs['Vector']).outputs['Vector']

    def scaled(cur, fac):
        s_ = vm('SCALE', cur)
        l.new(fac, s_.inputs['Scale'])
        return s_.outputs['Vector']

    tc = n.new('ShaderNodeTexCoord')
    noise = n.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = scale
    noise.inputs['Detail'].default_value = 1.5
    noise.inputs['Roughness'].default_value = .5
    l.new(tc.outputs['Object'], noise.inputs['Vector'])
    mp = n.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (7.0, 7.0, 1.4)          # strokes run down the body
    l.new(tc.outputs['Object'], mp.inputs['Vector'])
    stroke = n.new('ShaderNodeTexNoise')
    stroke.inputs['Scale'].default_value = 2.2
    stroke.inputs['Detail'].default_value = 2.0
    stroke.inputs['Roughness'].default_value = .55
    l.new(mp.outputs['Vector'], stroke.inputs['Vector'])
    for src, lo, hi, a, b in [(noise.outputs['Fac'], 1 - variation, 1 + variation, .32, .68),
                              (stroke.outputs['Fac'], .93, 1.07, .35, .65),
                              (attr('Cavity'), .72, 1.0, 0, 1), (attr('Clump'), .93, 1.07, -1, 1), (attr('Tip'), 1.0, 1.20, 0, 1)]:
        r = n.new('ShaderNodeMapRange')
        r.inputs['From Min'].default_value = a
        r.inputs['From Max'].default_value = b
        r.inputs['To Min'].default_value = lo
        r.inputs['To Max'].default_value = hi
        l.new(src, r.inputs['Value'])
        cur = scaled(cur, r.outputs['Result'])
    geo = n.new('ShaderNodeNewGeometry')
    sep = n.new('ShaderNodeSeparateXYZ')
    l.new(geo.outputs['Normal'], sep.inputs[0])
    r = n.new('ShaderNodeMapRange')
    r.inputs['From Min'].default_value = .25
    r.inputs['From Max'].default_value = 1
    r.inputs['To Min'].default_value = 1
    r.inputs['To Max'].default_value = 1.07
    l.new(sep.outputs['Z'], r.inputs['Value'])
    cur = scaled(cur, r.outputs['Result'])
    l.new(cur, p.inputs['Base Color'])
    MATS[name] = m
    return m


for k in COL:
    paint(k)


# ------------------------------------------------------------------ geometry helpers
# (copied from mob-production/reference-rebuilds/meshlib.py and build_werewolf.py)
def finish(o, name, m=None):
    o.name = name
    if m:
        o.data.materials.clear()
        o.data.materials.append(m)
    return o


def mesh(name, v, f, m):
    me = bpy.data.meshes.new(name)
    me.from_pydata(v, [], f)
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(me)
    bm.free()
    return finish(o, name, m)


def active(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def applied(o):
    active(o)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return o


def ell(name, p, s, m, segments=24, rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=p)
    o = bpy.context.object
    o.scale = s
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(o, name, m)


def cube(name, p, s, m, bevel=.1):
    bpy.ops.mesh.primitive_cube_add(size=1, location=p)
    o = bpy.context.object
    o.dimensions = s
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = o.modifiers.new('Round', 'BEVEL')
        mod.width = bevel
        mod.segments = 3
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return finish(o, name, m)


def tube(name, points, radii, m, n=12):
    pts = [Vector(p) for p in points]
    v = []
    previous = None
    for i, p in enumerate(pts):
        tangent = (pts[min(i + 1, len(pts) - 1)] - pts[max(0, i - 1)]).normalized()
        if previous is None:
            ref = Vector((1, 0, 0)) if abs(tangent.x) < .9 else Vector((0, 1, 0))
            u = (ref - tangent * tangent.dot(ref)).normalized()
        else:
            u = (previous - tangent * tangent.dot(previous)).normalized()
        w = tangent.cross(u).normalized()
        previous = u
        rr = radii[i] if isinstance(radii, list) else radii
        rx, ry = rr if isinstance(rr, tuple) else (rr, rr)
        for k in range(n):
            a = k * math.tau / n
            v.append(p + u * math.cos(a) * rx + w * math.sin(a) * ry)
    f = [tuple(range(n - 1, -1, -1))]
    for j in range(len(pts) - 1):
        for k in range(n):
            f.append((j * n + k, j * n + (k + 1) % n, (j + 1) * n + (k + 1) % n, (j + 1) * n + k))
    f.append(tuple(range((len(pts) - 1) * n, len(pts) * n)))
    return mesh(name, v, f, m)


def join(objects, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    o = bpy.context.object
    o.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return o


def cut(o, cutter):
    bpy.context.view_layer.objects.active = o
    mod = o.modifiers.new('Carve', 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    mod.object = cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def flat(o):
    for p in o.data.polygons:
        p.use_smooth = False


def clean(o):
    """Collapse decimation fins and non-manifold pinches (from build_werewolf.py)."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    for _ in range(8):
        bm.verts.index_update()
        seen = {}
        fins = []
        for f in bm.faces:
            k = tuple(sorted(v.index for v in f.verts))
            if k in seen:
                fins.append(list(f.verts))
            else:
                seen[k] = f
        if not fins:
            break
        for vs in fins:
            vs = [v for v in vs if v.is_valid]
            if len(vs) > 1:
                bmesh.ops.pointmerge(bm, verts=vs, merge_co=sum((v.co for v in vs), Vector()) / len(vs))
        bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-7)
    for _ in range(6):
        bad = [e for e in bm.edges if not e.is_manifold]
        if not bad:
            break
        for e in bad:
            if e.is_valid:
                bmesh.ops.pointmerge(bm, verts=list(e.verts), merge_co=(e.verts[0].co + e.verts[1].co) / 2)
        bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=1e-7)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bm.to_mesh(o.data)
    bm.free()
    o.data.validate()
    flat(o)
    return o


def manifold_report(objects):
    bad = {}
    for o in objects:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        n = sum(not e.is_manifold for e in bm.edges)
        bm.free()
        if n:
            bad[o.name] = n
    return bad


def fuse_to(objects, name, key, voxel, triangles, smooth=2, factor=.5):
    """Voxel-remesh union (smooth fillets between every add-on), relax, decimate."""
    o = join(objects, name)
    o.data.remesh_voxel_size = voxel * (1.3 if QUICK else 1)
    active(o)
    bpy.ops.object.voxel_remesh()
    if smooth:
        mod = o.modifiers.new('Fillet blend', 'SMOOTH')
        mod.factor = factor
        mod.iterations = smooth
        bpy.ops.object.modifier_apply(modifier=mod.name)
    o.data.calc_loop_triangles()
    count = len(o.data.loop_triangles)
    if count > triangles:
        mod = o.modifiers.new('Faceted topology', 'DECIMATE')
        mod.ratio = triangles / count
        bpy.ops.object.modifier_apply(modifier=mod.name)
    finish(o, name, paint(key))
    clean(o)
    return o


def copy_of(objects, name):
    copies = []
    for o in objects:
        c = o.copy()
        c.data = o.data.copy()
        bpy.context.collection.objects.link(c)
        copies.append(c)
    return join(copies, name)


def bvh_of(o):
    return BVHTree.FromObject(o, bpy.context.evaluated_depsgraph_get())


def set_materials(o, keys):
    o.data.materials.clear()
    for k in keys:
        o.data.materials.append(paint(k))
    return {k: i for i, k in enumerate(keys)}


def set_attr(o, name, values):
    a = o.data.attributes.get(name) or o.data.attributes.new(name, 'FLOAT', 'POINT')
    a.data.foreach_set('value', values)


class Builder:
    """Accumulates many small closed solids into one mesh object."""

    def __init__(self):
        self.v = []
        self.f = []

    def add(self, verts, faces):
        k = len(self.v)
        self.v += [tuple(p) for p in verts]
        self.f += [tuple(i + k for i in face) for face in faces]

    def make(self, name, key):
        return mesh(name, self.v, self.f, paint(key))


CLUMPS = {}   # builder id -> [(root, value)] for the per-clump Clump tint


def clump(b, root, normal, flow, L, W, T, lift=.2, bend=.16, sink=.07, lock=False):
    """One SOFT fur clump: a thick rounded teardrop lying along the surface, rooted
    below it, tapering to a blunt rounded tip that curls slightly away. Thin
    diamond shards read as blades/scales (rejected 2026-10-01), so the tip ring
    stays wide and the voxel fuse rounds it into a lobe."""
    T = max(T * 1.9, .46 * W)
    lift *= .6
    bend *= .7
    n = Vector(normal).normalized()
    d = Vector(flow)
    d = d - n * d.dot(n)
    if d.length < 1e-4:
        d = Vector((0, 0, -1)) - n * (-n.z)
    d.normalize()
    s = n.cross(d).normalized()
    base = Vector(root) - n * sink
    verts = []
    faces = []
    rings = []
    m = 6
    prof = ([(0, .78, .76), (.22, 1, 1), (.50, .86, .88), (.74, .58, .62), (.90, .36, .40)] if lock else
            [(0, .74, .76), (.24, 1, 1), (.52, .92, .9), (.76, .68, .66), (.92, .40, .40)])
    if lock:
        # small random twist of the flow so the locks don't line up like shingles
        d = (d + s * rng.uniform(-.22, .22)).normalized()
        s = n.cross(d).normalized()
    for t, wf, tf in prof:
        c = base + d * (L * t) + n * (L * (lift * t + bend * t * t) + sink * min(1, t * 3.2))
        tang = (d + n * (lift + 2 * bend * t)).normalized()
        up = tang.cross(s).normalized()
        i = len(verts)
        for k in range(m):
            a = k * math.tau / m
            co = math.cos(a)
            si = math.sin(a)
            verts.append(c + s * co * W * .5 * wf + up * si * T * tf * (.55 if si > 0 else .3))
        rings.append(i)
    verts.append(base + d * L * (.965 if lock else .985) + n * (L * (lift + bend) + sink))
    tip = len(verts) - 1
    for a, c in zip(rings, rings[1:]):
        for k in range(m):
            faces.append((a + k, a + (k + 1) % m, c + (k + 1) % m, c + k))
    last = rings[-1]
    for k in range(m):
        faces.append((last + k, last + (k + 1) % m, tip))
    faces.append(tuple(rings[0] + k for k in range(m - 1, -1, -1)))
    b.add(verts, faces)
    CLUMPS.setdefault(id(b), []).append((Vector(root) + d * L * .4, rng.uniform(-1, 1), verts[tip]))


def lobe(b, root, normal, flow, L, W, sink=.16, lift=.10, droop=.03):
    """One SOFT fur lobe: a thick round-sectioned teardrop, mostly buried in the
    surface it grows from, with a broad rounded tip. Overlapping lobes are
    pre-fused and smoothed into one continuous mass: no slabs, no sheet edges.
    (Thin shards/locks read as blades, scales or feathers: rejected.)"""
    n = Vector(normal).normalized()
    d = Vector(flow)
    d = d - n * d.dot(n)
    if d.length < 1e-4:
        d = Vector((0, 0, -1)) - n * (-n.z)
    d.normalize()
    s = n.cross(d).normalized()
    base = Vector(root) - n * sink
    verts = []
    faces = []
    rings = []
    m = 8
    for t, wf in [(0, .60), (.18, .92), (.40, 1.0), (.62, .95), (.80, .78), (.92, .52), (.985, .22)]:
        c = base + d * (L * t) + n * (sink * min(1, t * 2.5) + L * (lift * t - droop * t * t))
        i = len(verts)
        for k in range(m):
            a = k * math.tau / m
            verts.append(c + s * math.cos(a) * W * .5 * wf + n * math.sin(a) * W * .36 * wf)
        rings.append(i)
    verts.append(base + d * L + n * (sink + L * (lift - droop)))
    tip = len(verts) - 1
    for a, c in zip(rings, rings[1:]):
        for k in range(m):
            faces.append((a + k, a + (k + 1) % m, c + (k + 1) % m, c + k))
    last = rings[-1]
    for k in range(m):
        faces.append((last + k, last + (k + 1) % m, tip))
    faces.append(tuple(rings[0] + k for k in range(m - 1, -1, -1)))
    b.add(verts, faces)
    CLUMPS.setdefault(id(b), []).append((Vector(root) + d * L * .4, rng.uniform(-1, 1), verts[tip]))


def prefuse(objects, name, voxel, iters, factor=.6):
    """Voxel union + strong relax, no decimation: one soft continuous mass."""
    o = join(objects, name)
    o.data.remesh_voxel_size = voxel * (1.3 if QUICK else 1)
    active(o)
    bpy.ops.object.voxel_remesh()
    mod = o.modifiers.new('Soft mass', 'SMOOTH')
    mod.factor = factor
    mod.iterations = iters
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return o


def relax_attr(o, vals, iters=2, keep=.5):
    import numpy as _np
    v = _np.asarray(vals, float)
    e = _np.array([list(ed.vertices) for ed in o.data.edges], dtype=int)
    src = _np.concatenate((e[:, 0], e[:, 1]))
    dst = _np.concatenate((e[:, 1], e[:, 0]))
    deg = _np.bincount(src, minlength=len(v))
    for _ in range(iters):
        acc = _np.zeros_like(v)
        _np.add.at(acc, src, v[dst])
        v = keep * v + (1 - keep) * acc / _np.maximum(1, deg)
    return [float(x) for x in v]


def loft(name, levels, key, side=1, exponent=.85, shape=None, n=48):
    """Rings of (z, cx, cy, half-width, front depth, back depth); -Y is forward."""
    rings = []
    for j in range(len(levels) - 1):
        p0 = levels[max(0, j - 1)]
        p1 = levels[j]
        p2 = levels[j + 1]
        p3 = levels[min(len(levels) - 1, j + 2)]
        for k in range(3):
            t = k / 3
            rings.append([.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (-a + 3 * b - 3 * c + d) * t * t * t)
                          for a, b, c, d in zip(p0, p1, p2, p3)])
    rings.append(levels[-1])
    verts = []
    for z, cx, cy, rx, front, back in rings:
        for k in range(n):
            a = k * math.tau / n
            co = math.cos(a)
            si = math.sin(a)
            x = side * (cx + rx * math.copysign(abs(co) ** exponent, co))
            y = cy + (back if si >= 0 else front) * math.copysign(abs(si) ** exponent, si)
            if shape:
                x, y = shape(x, y, z, co, si)
            verts.append((x, y, z))
    faces = ([tuple(range(n - 1, -1, -1))] +
             [(j * n + k, j * n + (k + 1) % n, (j + 1) * n + (k + 1) % n, (j + 1) * n + k)
              for j in range(len(rings) - 1) for k in range(n)] +
             [tuple(range((len(rings) - 1) * n, len(rings) * n))])
    return mesh(name, verts, faces, paint(key))


def loft_y(name, levels, key, exponent=.72, n=32):
    """Snout/jaw sections along -Y: (y, cz, half-width, top height, bottom height)."""
    verts = []
    for y, cz, hw, top, bottom in levels:
        for k in range(n):
            a = k * math.tau / n
            co = math.cos(a)
            si = math.sin(a)
            verts.append((hw * math.copysign(abs(co) ** exponent, co), y,
                          cz + (top if si >= 0 else bottom) * math.copysign(abs(si) ** exponent, si)))
    m = len(levels)
    faces = ([tuple(range(n))] +
             [(j * n + (k + 1) % n, j * n + k, (j + 1) * n + k, (j + 1) * n + (k + 1) % n) for j in range(m - 1) for k in range(n)] +
             [tuple(range(m * n - 1, (m - 1) * n - 1, -1))])
    return mesh(name, verts, faces, paint(key))


def bar(name, a, b, height, depth, key, forward=Vector((0, -1, 0)), bevel=.03):
    a = Vector(a)
    b = Vector(b)
    ax = (b - a).normalized()
    fw = (forward - ax * forward.dot(ax)).normalized()
    up = ax.cross(fw).normalized()
    if up.z < 0:
        up = -up
    vs = []
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    for p in (a, b):
        for su in (-1, 1):
            for sf in (-1, 1):
                vs.append(p + up * su * height / 2 + fw * sf * depth / 2)
    o = mesh(name, vs, f, paint(key))
    if bevel:
        active(o)
        mod = o.modifiers.new('Chamfer', 'BEVEL')
        mod.width = bevel
        mod.segments = 1
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return o


def smooth01(a, b, x):
    t = max(0., min(1., (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ body (base units)
def torso_shape(x, y, z, co, si):
    ax = abs(x)
    front = max(0, -si) ** 3
    rear = max(0, si) ** 3
    pec = .21 * math.exp(-((ax - .62) / .46) ** 2 - ((z - 4.72) / .36) ** 2)
    abdomen = sum(.04 * math.exp(-((ax - .19) / .14) ** 2 - ((z - zz) / .12) ** 2) for zz in (3.70, 3.95, 4.20))
    y -= front * (pec + abdomen + .03 * math.exp(-(x / .38) ** 2 - ((z - 3.85) / .26) ** 2))
    y += rear * (.17 * math.exp(-((ax - 1.0) / .40) ** 2 - ((z - 4.55) / .48) ** 2) +
                 .14 * math.exp(-((ax - .55) / .40) ** 2 - ((z - 5.15) / .26) ** 2))
    y -= rear * .05 * math.exp(-(x / .14) ** 2)
    return x, y


# (z, cx, cy, half-width, front, back). Broader than the regular werewolf: wide
# lats/pecs, thick traps, hunched neck forward.
TORSO = [(2.78, 0, .05, .92, .58, .64), (2.96, 0, .05, 1.02, .62, .72), (3.30, 0, .04, .98, .64, .72),
         (3.65, 0, .02, .95, .70, .70), (4.00, 0, 0, 1.06, .80, .72), (4.40, 0, -.04, 1.12, .88, .80),
         (4.80, 0, -.07, 1.36, .90, .88), (5.10, 0, -.10, 1.42, .82, .92), (5.35, 0, -.16, 1.12, .66, .88),
         (5.58, 0, -.26, .72, .52, .70), (5.80, 0, -.38, .50, .42, .48), (6.04, 0, -.50, .42, .36, .40)]
# Arms hang well clear of the ribs below the armpit (gap >= 0.15) so the skin can split.
ARM = [(2.46, 2.16, -.06, .34, .34, .34), (2.66, 2.14, -.05, .40, .42, .40), (2.95, 2.09, -.03, .50, .54, .50),
       (3.30, 2.02, .02, .54, .57, .54), (3.68, 1.94, .08, .45, .48, .50), (4.02, 1.86, .08, .46, .54, .50),
       (4.38, 1.78, .05, .50, .60, .56), (4.72, 1.68, .02, .58, .62, .60), (5.02, 1.54, -.02, .60, .60, .62),
       (5.26, 1.30, -.04, .46, .46, .52)]
LEG = [(.44, .88, .16, .31, .31, .31), (.70, .88, .13, .36, .34, .38), (1.00, .87, .05, .42, .40, .50),
       (1.34, .86, -.03, .46, .46, .54), (1.70, .84, -.09, .43, .48, .47), (2.05, .79, -.05, .47, .52, .53),
       (2.40, .72, -.01, .53, .56, .58), (2.75, .65, .03, .55, .58, .60), (3.05, .58, .05, .52, .56, .58)]

# Bones in base units (anatomical Left = +X).
BONES = {'Pelvis': [(0, .06, 2.92), (0, .04, 3.45), 'Root'], 'Spine': [(0, .04, 3.45), (0, 0, 4.10), 'Pelvis'],
         'Chest': [(0, 0, 4.10), (0, -.14, 5.18), 'Spine'], 'Neck': [(0, -.14, 5.18), (0, -.48, 5.86), 'Chest'],
         'Head': [(0, -.48, 5.86), (0, -.76, 6.64), 'Neck'], 'Jaw': [(0, -.76, 5.36), (0, -1.60, 5.27), 'Head'],
         'Mane': [(0, .30, 5.25), (0, .80, 4.60), 'Chest'],
         'Tail1': [(0, .64, 3.10), (0, 1.10, 2.72), 'Pelvis'], 'Tail2': [(0, 1.10, 2.72), (0, 1.36, 2.22), 'Tail1'],
         'Tail3': [(0, 1.36, 2.22), (0, 1.48, 1.62), 'Tail2']}
for side, s in [('Left', 1), ('Right', -1)]:
    BONES.update({
        side + 'Shoulder': [(s * .32, -.06, 5.02), (s * 1.54, 0, 5.05), 'Chest'],
        side + 'UpperArm': [(s * 1.54, 0, 5.05), (s * 1.93, .10, 3.78), side + 'Shoulder'],
        side + 'Forearm': [(s * 1.93, .10, 3.78), (s * 2.16, -.06, 2.50), side + 'UpperArm'],
        side + 'Hand': [(s * 2.16, -.06, 2.50), (s * 2.19, -.10, 2.00), side + 'Forearm'],
        side + 'Fingers': [(s * 2.19, -.10, 2.00), (s * 2.15, -.16, 1.50), side + 'Hand'],
        side + 'Thigh': [(s * .60, .06, 2.92), (s * .84, -.10, 1.72), 'Pelvis'],
        side + 'Shin': [(s * .84, -.10, 1.72), (s * .88, .16, .50), side + 'Thigh'],
        side + 'Foot': [(s * .88, .16, .50), (s * .92, -.44, .20), side + 'Shin'],
        side + 'Toes': [(s * .92, -.44, .20), (s * .94, -.95, .14), side + 'Foot']})
# Half-angle helpers: each sits on its joint and rotates halfway between its two
# neighbours; the middle of each skin blend band rides it, so a 120 deg bend becomes
# two 60 deg blends and the joint keeps its mass (no collapse, no candy wrapper).
for side, s in [('Left', 1), ('Right', -1)]:
    for hname, joint, child, parent in (('ShoulderHelper', 'UpperArm', 'UpperArm', 'Shoulder'), ('ElbowHelper', 'Forearm', 'Forearm', 'UpperArm'),
                                        ('KneeHelper', 'Shin', 'Shin', 'Thigh')):
        h, t, _ = BONES[side + joint]
        d = (Vector(t) - Vector(h)).normalized()
        BONES[side + hname] = [h, tuple(Vector(h) + d * .30), side + parent]
# Toe-out of the paws (8 deg about the ankle) also turns the Foot/Toes bones.
for side, s in [('Left', 1), ('Right', -1)]:
    A = Vector(BONES[side + 'Foot'][0])
    R = Matrix.Rotation(math.radians(s * 8), 3, 'Z')
    for b in (side + 'Foot', side + 'Toes'):
        h, t, p = BONES[b]
        BONES[b] = [tuple(A + R @ (Vector(h) - A)), tuple(A + R @ (Vector(t) - A)), p]

log('body lofts')
base = [loft('Torso', TORSO, 'fur', shape=torso_shape, n=56)]
for s in [-1, 1]:
    base.append(loft('Arm', ARM, 'fur', side=s))
    base.append(loft('Leg', LEG, 'fur', side=s))
mane_base = [ell('Mane crown', (0, .14, 5.84), (1.30, .74, .86), paint('mane'), 32, 20),
             ell('Mane hump', (0, .52, 5.00), (1.48, .72, 1.05), paint('mane'), 32, 20),
             ell('Mane flare', (0, .40, 6.16), (1.00, .50, .52), paint('mane'), 28, 16)]
for s in [-1, 1]:
    mane_base.append(ell('Mane shoulder', (s * 1.05, .12, 5.30), (.70, .62, .58), paint('mane'), 24, 14))
probe = copy_of(base + mane_base, 'PROBE')
bv = bvh_of(probe)


def hit(origin, direction):
    loc, nor, i, d = bv.ray_cast(Vector(origin), Vector(direction).normalized(), 30)
    return (loc, nor) if loc is not None else (None, None)


mane_b = Builder()
fur_b = Builder()
bib_b = Builder()


def pair(fn):
    r = {'l': rng.uniform(-1, 1)}
    for s in [-1, 1]:
        fn(s, r)


def placed(b, origin, direction, flow, L, W, T, lift=.2, bend=.16, need=None):
    p, nrm = hit(origin, direction)
    if p is None or (need and not need(p)):
        return
    clump(b, p, nrm, flow, L, W, T, lift, bend)


def VHW(z):
    """Half-width of the cream chest V."""
    return max(0, .80 * (z - 3.85) / 1.30)


# Mane: an inverted shield of layered leaf clumps from the crown to mid-back (regular
# werewolf language, bigger and fuller), flaring up behind the head and over the shoulders.
for j, (z, hw) in enumerate([(6.42, .70), (6.22, 1.05), (6.00, 1.26), (5.78, 1.42), (5.56, 1.52), (5.34, 1.55),
                             (5.12, 1.50), (4.90, 1.40), (4.68, 1.22), (4.46, 1.00), (4.24, .74), (4.04, .44)]):
    step = .34
    offset = 0 if j % 2 else step / 2
    for x in [x for x in [offset + k * step for k in range(7)] if x <= hw + .01]:
        L = .70 + .16 * min(1, max(0, (z - 4) / 1.8))
        r = rng.uniform(-1, 1)
        up = z > 6.1                                   # top rows flare up and back behind the head
        for s_ in ([1] if x < .01 else [-1, 1]):
            fl = (s_ * x * .3, .60, .20) if up else (s_ * x * .28, .40, -1)
            placed(mane_b, (s_ * x, 6, z), (0, -1, 0), fl, L * (1 + .08 * r), .54, .17, .24, .20)
for x in [.62, .98, 1.32]:
    for y in [-.12, .22, .55]:
        pair(lambda s, r, x=x, y=y: placed(mane_b, (s * x, y, 9), (0, 0, -1), (s * .75, .3, -.55), .68 + .05 * r['l'], .52, .17, .22, .18,
                                          need=lambda p: p.z > 5.0))
for z in [5.26, 5.04, 4.82, 4.62]:
    for dx in [.12, .40, .66]:
        x = VHW(z) + dx
        if x > 1.36:
            continue
        pair(lambda s, r, z=z, x=x: placed(mane_b, (s * x, -5, z), (0, 1, 0), (s * .30, -.25, -1), .60, .50, .16, .16, .14,
                                          need=lambda p: p.z > 4.45))
# Cream chest bib: broad pale clumps lying flat in a V, rows overlapping downward.
for j, z in enumerate([5.14, 4.90, 4.66, 4.42, 4.18, 3.98]):
    hw = VHW(z)
    step = .34
    offset = 0 if j % 2 == 0 or hw < .2 else step / 2
    for x in [x for x in [offset + k * step for k in range(5)] if x <= hw + .02]:
        for s in ([1] if x < .01 else [-1, 1]):
            placed(bib_b, (s * x, -5, z), (0, 1, 0), (s * x * .15, -.2, -1), .62, .56, .11, .08, .10)
# Russet: layered clumps over the shoulders and upper arms ...
for z in [5.00, 4.76, 4.52, 4.28]:
    for y in [-.30, -.02, .26]:
        pair(lambda s, r, z=z, y=y: placed(fur_b, (s * 6, y, z), (-s, 0, 0), (s * .45, .05 * y, -1), .52 + .04 * r['l'], .46, .15, .16, .14))
# ... tufts at the elbows and outer forearms ...
for z in [3.94, 3.72]:
    for o in [-.15, .15]:
        pair(lambda s, r, z=z, o=o: placed(fur_b, (s * (1.93 + o), 5, z), (0, -1, 0), (s * .35, .75, -.7), .54, .48, .15, .22, .18))
for z in [3.36, 3.04]:
    for y in [-.22, .14]:
        pair(lambda s, r, z=z, y=y: placed(fur_b, (s * 6, y, z), (-s, 0, 0), (s * .6, .1, -1), .66 + .05 * r['l'], .50, .15, .22, .17))


def cuff(axis, z, count, L, W, skip_inner=False):
    for k in range(count):
        a = (k + .5 * (round(z * 10) % 2)) * math.tau / count
        for s in [-1, 1]:
            c = Vector((s * axis[0], axis[1], z))
            r = Vector((s * math.cos(a), math.sin(a), 0))
            if skip_inner and r.x * s < -.75:
                continue
            placed(fur_b, c + r * .9, -r, Vector((0, 0, -1)) + r * .35, L, W, .13, .18, .14)


# ... shaggy forearm and calf cuffs (layered rings) ...
for z in [3.30, 3.02, 2.76]:
    cuff((2.06, -.03), z, 9, .52, .44)
cuff((2.16, -.05), 2.62, 9, .42, .40)
for z in [1.36, 1.08]:
    cuff((.87, .02), z, 8, .50, .44, skip_inner=True)
cuff((.88, .15), .66, 9, .40, .38)
for o in [-.15, .15]:
    pair(lambda s, r, o=o: placed(fur_b, (s * (.84 + o), -5, 1.74), (0, 1, 0), (s * .2, -.2, -1), .42, .40, .12, .14, .12))
# ... and sparse locks on the back below the mane.
for x in [.30, .72]:
    pair(lambda s, r, x=x: placed(fur_b, (s * x, 5, 3.74), (0, -1, 0), (s * .3, .4, -1), .42, .40, .13, .14, .12))

mane_c = mane_b.make('Mane clumps', 'mane')
fur_c = fur_b.make('Fur clumps', 'fur')
bib_c = bib_b.make('Bib clumps', 'cream')
body_clumps = CLUMPS.get(id(mane_b), []) + CLUMPS.get(id(fur_b), []) + CLUMPS.get(id(bib_b), [])
src_mane = copy_of(mane_base + [mane_c], 'SRC_mane')
src_bib = copy_of([bib_c], 'SRC_bib')
src_other = copy_of(base + [fur_c], 'SRC_other')
log('fusing body skin')
skin = fuse_to(base + mane_base + [mane_c, fur_c, bib_c], 'AlphaWolf_Body', 'fur', .022, 11000, 4, .55)
skin.data.materials.clear()
skin.data.materials.append(paint('fur', (('mane', 'ManeMask'), ('cream', 'CreamMask'))))
tm = bvh_of(src_mane)
tb_ = bvh_of(src_bib)
to = bvh_of(src_other)
mane_m = []
cream_m = []
for v in skin.data.vertices:
    c = v.co
    nrm = v.normal
    dm = tm.find_nearest(c)[3]
    db = tb_.find_nearest(c)[3]
    do = to.find_nearest(c)[3]
    mane_m.append(smooth01(.02, -.02, dm - min(db, do)))
    vz = (smooth01(-.015, .015, VHW(c.z) - abs(c.x)) * smooth01(-.02, -.30, nrm.y) * smooth01(3.80, 3.98, c.z) *
          smooth01(5.45, 5.30, c.z))
    cream_m.append(max(vz, smooth01(.02, -.02, db - min(dm, do))))
cream_m = [c * (1 - m_) for c, m_ in zip(cream_m, mane_m)]
set_attr(skin, 'ManeMask', mane_m)
set_attr(skin, 'CreamMask', cream_m)
for o in (src_mane, src_bib, src_other, probe):
    bpy.data.objects.remove(o, do_unlink=True)
log('SKIN tris', len(skin.data.polygons))

# ------------------------------------------------------------------ head
log('head')
CR = Vector((0, -.62, 5.98))
cran = applied(ell('Cranium', CR, (.57, .52, .45), paint('fur'), 14, 9))
for v in cran.data.vertices:
    if v.co.y < -.98:
        v.co.y = -.98 + (v.co.y + .98) * .45
    if v.co.z > 6.30:
        v.co.z = 6.30 + (v.co.z - 6.30) * .55
hp = [cran, ell('Brow ridge', (0, -.98, 5.93), (.44, .14, .10), paint('fur'), 14, 8)]
snout = loft_y('Snout', [(-.92, 5.57, .38, .28, .29), (-1.22, 5.53, .33, .23, .25), (-1.52, 5.52, .27, .19, .19),
                         (-1.76, 5.54, .20, .14, .13)], 'fur', .6, 16)
hp.append(snout)
muzzle_parts = [snout]
for s in [-1, 1]:
    j = ell('Jowl', (s * .21, -1.34, 5.39), (.18, .30, .11), paint('fur'), 16, 10)
    c = ell('Cheek', (s * .40, -.88, 5.62), (.26, .30, .28), paint('fur'), 16, 10)
    hp += [j, c]
    muzzle_parts.append(j)

EARS = {}


def ear(s, notch):
    B = Vector((s * .40, -.56, 6.12))
    T = Vector((s * .76, -.62, 7.00))
    up = (T - B)
    h = up.length
    up.normalize()
    fwd = Vector((s * .12, -1, 0)).normalized()
    fwd = (fwd - up * fwd.dot(up)).normalized()
    side = up.cross(fwd).normalized()          # +X-ish for both ears
    hw = .37
    out = 1 if s > 0 else -1                   # outer edge sign along `side`
    pts = [(-hw, -.12), (hw, -.12), (hw * .86, .30 * h), (hw * .58, .58 * h), (0, h), (-hw * .58, .58 * h), (-hw * .86, .30 * h)]
    if notch:
        # A torn V bitten out of the outer edge just below the tip (sheet: left ear).
        pts = [(-hw * out, -.12), (hw * out, -.12), (hw * .86 * out, .30 * h), (hw * .64 * out, .52 * h),
               (hw * .16 * out, .62 * h), (hw * .40 * out, .72 * h), (0, h), (-hw * .58 * out, .58 * h), (-hw * .86 * out, .30 * h)]
        if out < 0:
            pts = pts[::-1]
    front = [B + side * u + up * v for u, v in pts]
    cen = sum(front, Vector()) / len(front)
    back = [cen + (p - cen) * .86 + (-fwd) * .15 for p in front]
    n = len(pts)
    bm = bmesh.new()
    fv = [bm.verts.new(p) for p in front]
    bv_ = [bm.verts.new(p) for p in back]
    bm.faces.new(fv)
    bm.faces.new(bv_[::-1])
    for k in range(n):
        bm.faces.new((fv[k], bv_[k], bv_[(k + 1) % n], fv[(k + 1) % n]))
    bmesh.ops.triangulate(bm, faces=list(bm.faces), quad_method='BEAUTY', ngon_method='EAR_CLIP')
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    me = bpy.data.meshes.new('Ear')
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new('Ear', me)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(paint('fur'))
    EARS[s] = (B, up, side, fwd, h, hw)
    return o


for s in [-1, 1]:
    hp.append(ear(s, notch=(s > 0)))
hprobe = copy_of(hp, 'HPROBE')
hbv = bvh_of(hprobe)
hb = Builder()     # russet cheek clumps
hm = Builder()     # charcoal face ruff + crown


def hplace(b, origin, direction, flow, L, W, T, lift=.2, bend=.14, need=None):
    loc, nor, i, d = hbv.ray_cast(Vector(origin), Vector(direction).normalized(), 10)
    if loc is None or (need and not need(loc)):
        return
    clump(b, loc, nor, flow, L, W, T, lift, bend)


for s in [-1, 1]:
    for root, flow, L in [((.55, -.80, 5.62), (.85, .35, -.35), .44), ((.52, -.72, 5.44), (.7, .35, -.7), .42),
                          ((.56, -.66, 5.80), (.8, .4, 0), .38), ((.46, -.90, 5.33), (.5, .2, -.9), .36)]:
        clump(hb, Vector((s * root[0], root[1], root[2])), Vector((s, -.3, 0)), Vector((s * flow[0], flow[1], flow[2])), L, .34, .14, .15, .12)
    # Face ruff: layered charcoal leaf clumps flaring out and back from behind the cheeks.
    for z in [6.14, 5.92, 5.70, 5.48, 5.28]:
        for y in [-.50, -.28, -.06]:
            big = 1.12 if 5.5 < z < 6.0 else .96
            hplace(hm, (s * 3, y, z), (-s, 0, 0), (s * .80, .35, -.45), .62 * big, .50, .17, .2, .15, need=lambda p: abs(p.x) < 1.0)
    for y in [-.66, -.42]:
        clump(hm, Vector((s * .30, y, 5.30)), Vector((s * .4, -.2, -1)), Vector((s * .25, .1, -1)), .56, .46, .16, .15, .12)
for y in [-.30, -.04]:
    for x in [0, .28]:
        for s in ([1] if x < .01 else [-1, 1]):
            hplace(hm, (s * x, y, 9), (0, 0, -1), (s * x * .5, 1, .1), .60, .48, .16, .3, .15)
hplace(hb, (0, -.76, 9), (0, 0, -1), (0, 1, .1), .38, .34, .13, .25, .12)
head_clumps = CLUMPS.get(id(hb), []) + CLUMPS.get(id(hm), [])
cheek_c = hb.make('Cheek clumps', 'fur')
ruff = hm.make('Face ruff', 'mane')
hp += [cheek_c, ruff]
muzzle_src = copy_of(muzzle_parts, 'SRC_muzzle')
ruff_src = copy_of([ruff], 'SRC_ruff')
fur_src = copy_of([o for o in hp if o not in muzzle_parts and o != ruff], 'SRC_headfur')
bpy.data.objects.remove(hprobe, do_unlink=True)
head = fuse_to(hp, 'AlphaWolf_Head', 'fur', .014, 2500, 2, .45)
head.data.materials.clear()
head.data.materials.append(paint('fur', (('mane', 'ManeMask'), ('cream', 'CreamMask'), ('inner', 'InnerMask'), ('mouth', 'MouthMask'))))
mt = bvh_of(muzzle_src)
rt = bvh_of(ruff_src)
ft = bvh_of(fur_src)


def inner_ear(c, nrm):
    for s, (B, up, side, fwd, h, hw) in EARS.items():
        if nrm.dot(fwd) < .35:
            continue
        rel = c - B
        u = rel.dot(side)
        v = rel.dot(up)
        dep = rel.dot(fwd)
        if dep < -.08 or v < .12 * h or v > .86 * h:
            continue
        tri = [Vector((-hw, 0)), Vector((hw, 0)), Vector((0, h))]
        cen = sum(tri, Vector((0, 0))) / 3
        tri = [cen + (t - cen) * .66 for t in tri]
        q = Vector((u, v))

        def sd(p1, p2):
            return (p2.x - p1.x) * (q.y - p1.y) - (p2.y - p1.y) * (q.x - p1.x)
        d1, d2, d3 = sd(tri[0], tri[1]), sd(tri[1], tri[2]), sd(tri[2], tri[0])
        if not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0)):
            return True
    return False


masks = {'ManeMask': [], 'CreamMask': [], 'InnerMask': [], 'MouthMask': []}
for v in head.data.vertices:
    c = v.co
    nrm = v.normal
    dm = mt.find_nearest(c)[3]
    dr = rt.find_nearest(c)[3]
    df = ft.find_nearest(c)[3]
    masks['InnerMask'].append(1.0 if inner_ear(c, nrm) else 0.0)
    masks['ManeMask'].append(smooth01(.025, -.025, dr - min(dm, df)))
    masks['CreamMask'].append(max(smooth01(.03, -.03, dm - df) * smooth01(-.74, -.86, c.y),
                                  smooth01(-.80, -.90, c.y) * smooth01(5.70, 5.60, c.z) * smooth01(.62, .50, abs(c.x))))
    masks['MouthMask'].append(smooth01(.20, .14, abs(c.x)) * smooth01(-.86, -.94, c.y) * smooth01(-.45, -.70, nrm.z) *
                              smooth01(5.42, 5.36, c.z))
for k in masks:
    masks[k] = relax_attr(head, masks[k], 1)
masks['CreamMask'] = [c * (1 - r) * (1 - i) for c, r, i in zip(masks['CreamMask'], masks['ManeMask'], masks['InnerMask'])]
for k, vals in masks.items():
    set_attr(head, k, vals)
for o in (muzzle_src, ruff_src, fur_src):
    bpy.data.objects.remove(o, do_unlink=True)
set_attr(head, 'JawMask', [0.0] * len(head.data.vertices))
log('HEAD tris', len(head.data.polygons))

# Lower jaw: a separate hinged solid (Jaw bone) tucked under the snout.
jaw_parts = [loft_y('Lower jaw', [(-.78, 5.27, .34, .10, .13), (-1.10, 5.24, .30, .09, .12), (-1.42, 5.24, .22, .08, .10),
                                   (-1.64, 5.26, .14, .06, .07)], 'cream', .6, 16),
             ell('Chin', (0, -1.40, 5.17), (.17, .20, .09), paint('cream'), 14, 8)]
jaw = fuse_to(jaw_parts, 'Jaw piece', 'cream', .012, 420, 2, .4)
jaw.data.materials.clear()
jaw.data.materials.append(paint('cream', (('mouth', 'MouthMask'), ('tongue', 'TongueMask'))))
mo = [smooth01(.30, .60, v.normal.z) * smooth01(5.24, 5.30, v.co.z) * smooth01(.24, .16, abs(v.co.x)) for v in jaw.data.vertices]
to_ = [m_ * smooth01(.13, .08, abs(v.co.x)) * smooth01(-.80, -.90, v.co.y) for m_, v in zip(mo, jaw.data.vertices)]
set_attr(jaw, 'MouthMask', relax_attr(jaw, mo, 1))
set_attr(jaw, 'TongueMask', relax_attr(jaw, to_, 1))
features = []
jaw_feats = [jaw]
for s in [-1, 1]:
    jaw_feats.append(tube('Lower fang', [(s * .17, -1.46, 5.28), (s * .175, -1.48, 5.36), (s * .18, -1.50, 5.45)],
                          [(.05, .045), (.035, .03), (.005, .005)], paint('fang'), 6))
for o in jaw_feats:
    set_attr(o, 'JawMask', [1.0] * len(o.data.vertices))

hbt = bvh_of(head)


def head_hit(x, z):
    loc, nor, i, d = hbt.ray_cast(Vector((x, -5, z)), Vector((0, 1, 0)), 10)
    return loc, nor


def almond(name, center, forward, w, h, depth, roll, key, dome=.5):
    f = Vector(forward).normalized()
    X = (-f).cross(Vector((0, 0, 1))).normalized()
    Z = X.cross(-f).normalized()
    ring = []
    n = 14
    cr = math.cos(roll)
    sr = math.sin(roll)
    for k in range(n):
        a = k * math.tau / n
        u = w * math.copysign(abs(math.cos(a)) ** 1.5, math.cos(a))
        v = h * math.sin(a)
        ring.append((u * cr - v * sr, u * sr + v * cr))
    verts = ([Vector(center) + X * u + Z * v + f * depth * .5 for u, v in ring] +
             [Vector(center) + X * u + Z * v - f * depth * .5 for u, v in ring] + [Vector(center) + f * depth * (.5 + dome)])
    faces = ([(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)] + [(k, 2 * n, (k + 1) % n) for k in range(n)] +
             [tuple(range(2 * n - 1, n - 1, -1))])
    return mesh(name, verts, faces, paint(key))


glow = []
for s in [-1, 1]:
    p, nrm = head_hit(s * .31, 5.80)
    f = (nrm.normalized() + Vector((s * .3, -1, 0)).normalized()).normalized()
    roll = s * math.radians(17)
    features.append(almond('Eye socket', p + f * .002, f, .185, .110, .035, roll, 'brow', .2))
    glow.append(almond('Eye glow', p + f * .019, f, .152, .086, .028, roll, 'eye', .45))
    features.append(almond('Pupil', p + f * .042 + Vector((-s * .014, 0, -.004)), f, .036, .070, .014, 0, 'pupil', .3))
    a, _ = head_hit(s * .09, 5.86)
    b, _ = head_hit(s * .50, 6.04)
    features.append(bar('Heavy brow', a + Vector((0, -.06, .0)), b + Vector((s * .05, -.05, .03)), .19, .25, 'brow', bevel=.045))
    fang = [(s * .27, -1.47, 5.42), (s * .285, -1.54, 5.27), (s * .275, -1.53, 5.08)]
    features.append(tube('Upper fang', fang, [(.095, .078), (.065, .055), (.008, .008)], paint('fang'), 6))
p, nrm = head_hit(0, 5.63)
c = p + Vector((0, -.02, .03))
nose = applied(ell('Nose', c, (.21, .15, .12), paint('nose'), 12, 8))
for v in nose.data.vertices:
    if v.co.z > c.z:
        v.co.z = c.z + (v.co.z - c.z) * .7
    else:
        v.co.x = c.x + (v.co.x - c.x) * (1 - .35 * (c.z - v.co.z) / .12)
features.append(nose)
for o in features:
    set_attr(o, 'JawMask', [0.0] * len(o.data.vertices))
    flat(o)
head = join([head, *features, *jaw_feats], 'AlphaWolf_Head')
eyeglow = join(glow, 'AlphaWolf_EyeGlow')
# The bigger mane swallowed the head a little: enlarge the head 7% about a high
# pivot so the ear tips stay at ~1.3x the regular werewolf. The Jaw hinge follows.
HS = 1.07
HP = Vector((0, -.45, 6.25))
Mh = Matrix.Translation(HP) @ Matrix.Scale(HS, 4) @ Matrix.Translation(-HP)
for o in (head, eyeglow):
    o.data.transform(Mh)
    o.data.update()
    flat(o)
BONES['Jaw'] = [tuple(HP + (Vector(p) - HP) * HS) for p in BONES['Jaw'][:2]] + ['Head']
HO = Vector((0, -.06, .24))          # more face and neck above the shoulders (sheet)
for o in (head, eyeglow):
    o.data.transform(Matrix.Translation(HO))
    o.data.update()
BONES['Jaw'] = [tuple(Vector(p) + HO) for p in BONES['Jaw'][:2]] + ['Head']


# ------------------------------------------------------------------ hands, paws, tail
def claw_tube(tip, d, inward, length=.34, r0=(.09, .075)):
    base = tip - d * .05
    return tube('Claw', [base, base + d * length * .45 + inward * .02, base + d * length * .85 + inward * .10],
                [r0, (r0[0] * .62, r0[1] * .62), (.006, .006)], paint('claw'), 6)


def hand(s):
    cx = s * 2.18
    palm = applied(cube('Palm', (cx, -.08, 2.22), (.50, .80, .62), paint('fur'), .12))
    for v in palm.data.vertices:
        t = (2.53 - v.co.z) / .62
        v.co.y = -.08 + (v.co.y + .08) * (.84 + .26 * t)
        v.co.x = cx + (v.co.x - cx) * (.95 + .10 * t)
    parts = [palm]
    finger_parts = []
    claws = []
    inw = Vector((-s, 0, 0))
    for y, L in [(-.31, .42), (-.10, .47), (.10, .45), (.29, .38)]:
        k = Vector((s * 2.20, y - .08, 1.98))
        q = L / .45
        pts = [k + Vector((0, 0, .10)), k + Vector((-s * .03, 0, -.17 * q)), k + Vector((-s * .09, 0, -.31 * q)), k + Vector((-s * .16, 0, -.41 * q))]
        f = tube('Finger', pts, [.158, .148, .130, .108], paint('fur'), 10)
        parts.append(f)
        finger_parts.append(f)
        claws.append(claw_tube(pts[-1], (pts[-1] - pts[-2]).normalized(), inw))
    th = [Vector((s * 2.06, -.44, 2.30)), Vector((s * 1.99, -.55, 2.14)), Vector((s * 1.95, -.59, 1.98))]
    thumb = tube('Thumb', th, [.15, .135, .115], paint('fur'), 10)
    parts.append(thumb)
    thumb_claw = claw_tube(th[-1], (th[-1] - th[-2]).normalized(), inw, .28, (.08, .066))
    fsrc = copy_of(finger_parts, 'SRC_fingers')
    psrc = copy_of([palm, thumb], 'SRC_palm')
    o = fuse_to(parts, 'Hand', 'fur', .014, 960, 2, .45)
    ftree = bvh_of(fsrc)
    ptree = bvh_of(psrc)
    fm = []
    for v in o.data.vertices:
        df = ftree.find_nearest(v.co)[3]
        dp = ptree.find_nearest(v.co)[3]
        fm.append(1.0 if (df < dp and v.co.z < 2.12) else 0.0)
    set_attr(o, 'FingerMask', fm)
    bpy.data.objects.remove(fsrc, do_unlink=True)
    bpy.data.objects.remove(psrc, do_unlink=True)
    for c in claws:
        set_attr(c, 'FingerMask', [1.0] * len(c.data.vertices))
    set_attr(thumb_claw, 'FingerMask', [0.0] * len(thumb_claw.data.vertices))
    return [o] + claws + [thumb_claw]


def paw(s):
    A = Vector((s * .88, .16, .50))
    parts = [ell('Ankle', A + Vector((0, -.02, -.06)), (.32, .32, .28), paint('fur'))]
    parts += [cube('Paw', (s * .91, -.22, .24), (.70, .92, .48), paint('fur'), .16),
              ell('Heel', (s * .90, .24, .22), (.32, .30, .22), paint('fur'))]
    claws = []
    for o in [-.33, -.11, .11, .33]:
        c = Vector((s * .91 + o, -.72 + .06 * abs(o) / .33, .19))
        parts.append(ell('Toe', c, (.17, .23, .19), paint('fur')))
        b = c + Vector((0, -.18, .06))
        claws.append(tube('Toe claw', [b, b + Vector((0, -.15, -.02)), b + Vector((0, -.27, -.15))],
                          [(.078, .064), (.054, .047), (.006, .006)], paint('claw'), 6))
    R = Matrix.Translation(A) @ Matrix.Rotation(math.radians(s * 8), 4, 'Z') @ Matrix.Translation(-A)
    for o in parts + claws:
        o.matrix_world = R @ o.matrix_world
        applied(o)
    foot = fuse_to(parts, 'Paw', 'fur', .016, 660, 2, .45)
    return [foot] + claws


limbs_h = []
limbs_f = []
for s in [-1, 1]:
    limbs_h += hand(s)
    limbs_f += paw(s)
hands = join(limbs_h, 'AlphaWolf_Hands')
feet = join(limbs_f, 'AlphaWolf_Feet')
for o in (hands, feet):
    flat(o)
log('HANDS', len(hands.data.polygons), 'FEET', len(feet.data.polygons))

TP = [Vector(p) for p in [(0, .62, 3.12), (0, .90, 2.95), (0, 1.14, 2.66), (0, 1.32, 2.30), (0, 1.44, 1.92), (0, 1.50, 1.60)]]
TR = [.20, .34, .40, .38, .30, .14]
tail_parts = [tube('Tail core', TP, TR, paint('mane'), 12)]
tb = Builder()
for i in range(1, len(TP)):
    tan = (TP[i] - TP[i - 1]).normalized()
    u = Vector((1, 0, 0))
    w = tan.cross(u)
    for k, t in enumerate((.25, .75)):
        c = TP[i - 1].lerp(TP[i], t)
        rad = TR[i - 1] * (1 - t) + TR[i] * t
        L = .52 + .22 * math.sin(math.pi * min(1, (i - 1 + t) / 4.2))
        for a in range(6):
            ang = math.radians(a * 60 + 30 * ((i * 2 + k) % 2))
            r = u * math.cos(ang) + w * math.sin(ang)
            clump(tb, c + r * rad * .8, r, tan + r * .15, L, .50, .14, .14, .10)
for a in [0, 120, 240]:
    r = Vector((math.cos(math.radians(a)), 0, math.sin(math.radians(a))))
    clump(tb, TP[-1] + Vector((0, -.02, .06)) + r * .05, r + Vector((0, .2, -1)), Vector((0, .25, -1)), .40, .36, .13, .12, .08)
tail_clumps = CLUMPS.get(id(tb), [])
tail_parts.append(tb.make('Tail clumps', 'mane'))
tail = fuse_to(tail_parts, 'AlphaWolf_Tail', 'mane', .016, 1600, 3, .5)
tail.data.materials.clear()
tail.data.materials.append(paint('mane', (('cream', 'CreamMask'),)))


def chain_param(p, pts):
    """Arc-length parameter (0..1) of the nearest point on a polyline."""
    best = (1e9, 0)
    lengths = [(b - a).length for a, b in zip(pts, pts[1:])]
    total = sum(lengths)
    acc = 0
    for (a, b), L in zip(zip(pts, pts[1:]), lengths):
        v = b - a
        t = max(0, min(1, (p - a).dot(v) / v.length_squared))
        d = (p - (a + v * t)).length
        if d < best[0]:
            best = (d, (acc + t * L) / total)
        acc += L
    return best[1]


set_attr(tail, 'CreamMask', [smooth01(.66, .72, chain_param(v.co, TP)) for v in tail.data.vertices])
log('TAIL', len(tail.data.polygons))

# ------------------------------------------------------------------ torn shorts and belt
seat = loft('Shorts seat', [(2.76, 0, .05, 1.00, .64, .70), (2.96, 0, .05, 1.12, .68, .80), (3.25, 0, .04, 1.08, .70, .80),
                            (3.58, 0, .02, 1.03, .75, .76)], 'shorts', exponent=.8)
cloth = [seat]
left_teeth = []
for s in [-1, 1]:
    n = 28
    verts = []
    rings = [(2.85, .64, .04, .62, .66), (2.55, .70, .02, .61, .65), (2.30, .74, 0, .60, .64), (2.08, .77, -.02, .58, .62), None]
    if s < 0:
        for k in range(n):
            down = (k % 2 == 0)
            mag = rng.uniform(.10, .22) if down else rng.uniform(0, .05)
            if down and rng.random() < .2:
                mag += .12
            left_teeth.append(mag if down else -mag)
        teeth = left_teeth
    else:
        teeth = [left_teeth[(n // 2 - k) % n] for k in range(n)]
    for ring in rings:
        for k in range(n):
            a = k * math.tau / n
            co = math.cos(a)
            si = math.sin(a)
            if ring is None:
                z, cx, cy, rx, ry = 1.96 - teeth[k] + .03 * math.sin(a * 3), .78, -.02, .58, .62
            else:
                z, cx, cy, rx, ry = ring
            verts.append((s * cx + rx * co, cy + ry * si, z))
    faces = [(j * n + k, j * n + (k + 1) % n, (j + 1) * n + (k + 1) % n, (j + 1) * n + k) for j in range(len(rings) - 1) for k in range(n)]
    leg = mesh('Shorts leg', verts, faces, paint('shorts'))
    active(leg)
    mod = leg.modifiers.new('Cloth thickness', 'SOLIDIFY')
    mod.thickness = .065
    mod.offset = 1
    bpy.ops.object.modifier_apply(modifier=mod.name)
    c, size, through = (((-.62, -.62, 2.20), (.17, .6, .12), 'y') if s < 0 else ((1.30, -.10, 2.14), (.6, .15, .11), 'x'))
    kk = applied(cube('Tear', c, size, None, 0))
    for v in kk.data.vertices:
        if v.co.z > c[2]:
            if through == 'y':
                v.co.x = c[0] + (v.co.x - c[0]) * .15
            else:
                v.co.y = c[1] + (v.co.y - c[1]) * .15
    cut(leg, kk)
    cloth.append(leg)
shorts = fuse_to(cloth, 'AlphaWolf_Shorts', 'shorts', .012, 1350, 1, .4)


def band(name, z0, z1, rx, front, back, thick, key, n=56):
    verts = []
    for z, grow in [(z0, 0), (z1, 0), (z1, thick), (z0, thick)]:
        for k in range(n):
            a = k * math.tau / n
            co = math.cos(a)
            si = math.sin(a)
            verts.append(((rx + grow) * math.copysign(abs(co) ** .82, co), .02 + ((back if si >= 0 else front) + grow) * math.copysign(abs(si) ** .82, si), z))
    faces = [(r * n + k, r * n + (k + 1) % n, ((r + 1) % 4) * n + (k + 1) % n, ((r + 1) % 4) * n + k) for r in range(4) for k in range(n)]
    return mesh(name, verts, faces, paint(key))


belt = band('Belt', 3.42, 3.64, 1.03, .78, .78, .07, 'belt')
buckle = cube('Buckle', (0, -.875, 3.53), (.34, .08, .28), paint('buckle'), .025)
shorts = join([shorts, belt, buckle], 'AlphaWolf_Shorts')
flat(shorts)
log('SHORTS', len(shorts.data.polygons))

FINALS = {'Body': skin, 'Head': head, 'EyeGlow': eyeglow, 'Hands': hands, 'Feet': feet, 'Tail': tail, 'Shorts': shorts}
bad = manifold_report([skin, tail])
if bad:
    log('WARNING non-manifold', bad)

# Per-clump tint (base units, before scaling).
for sec, cl in [('Body', body_clumps), ('Head', head_clumps), ('Tail', tail_clumps)]:
    o = FINALS[sec]
    kd = KDTree(len(cl))
    kt = KDTree(len(cl))
    for i, (p, val, tip) in enumerate(cl):
        kd.insert(p, i)
        kt.insert(tip, i)
    kd.balance()
    kt.balance()
    vals = []
    tips = []
    for v in o.data.vertices:
        co, i, d = kd.find(v.co)
        vals.append(cl[i][1] * max(0, 1 - d / .55) if i is not None else 0)
        co, i, d = kt.find(v.co)
        tips.append(max(0., 1 - d / .24) if i is not None else 0)
    set_attr(o, 'Clump', vals)
    set_attr(o, 'Tip', tips)
for sec in ['EyeGlow', 'Hands', 'Feet', 'Shorts']:
    o = FINALS[sec]
    set_attr(o, 'Clump', [0.0] * len(o.data.vertices))
    set_attr(o, 'Tip', [0.0] * len(o.data.vertices))

# ------------------------------------------------------------------ final scale (studs)
SCALE = Matrix.Scale(K, 4)
for o in FINALS.values():
    o.data.transform(SCALE)
    o.data.update()
BONES_STUDS = {n: [tuple(Vector(h) * K), tuple(Vector(t) * K), p] for n, (h, t, p) in BONES.items()}


# ------------------------------------------------------------------ cavity (baked AO-like attribute)
def cavity(objects, rays=32, reach=.45):
    bm = bmesh.new()
    for o in objects:
        bm.from_mesh(o.data)
    tree = BVHTree.FromBMesh(bm)
    bm.free()
    g = math.pi * (3 - math.sqrt(5))
    dirs = []
    for i in range(rays):
        z = 1 - (i + .5) / rays
        r = math.sqrt(1 - z * z)
        dirs.append(Vector((r * math.cos(g * i), r * math.sin(g * i), math.sqrt(z))))
    for o in objects:
        me = o.data
        vals = []
        for v in me.vertices:
            n = v.normal.normalized()
            t = n.orthogonal().normalized()
            b = n.cross(t)
            origin = v.co + n * .015
            occ = 0
            for d in dirs:
                loc, _, _, dist = tree.ray_cast(origin, t * d.x + b * d.y + n * d.z, reach)
                if loc is not None:
                    occ += 1 - dist / reach * .5
            vals.append(max(0, 1 - occ / rays * 1.25))
        set_attr(o, 'Cavity', vals)


objs = list(FINALS.values())
if QUICK:
    for o in objs:
        set_attr(o, 'Cavity', [1.0] * len(o.data.vertices))
else:
    log('cavity')
    cavity(objs)
set_attr(eyeglow, 'Cavity', [1.0] * len(eyeglow.data.vertices))
TRIS = {}
for sec, o in FINALS.items():
    o.data.calc_loop_triangles()
    TRIS[NAME + '_' + sec] = len(o.data.loop_triangles)
log('TRIANGLES', sum(TRIS.values()), json.dumps(TRIS))


# ------------------------------------------------------------------ review stage helpers
def stage_collection():
    st = bpy.data.collections.get('REVIEW_ONLY')
    if not st:
        st = bpy.data.collections.new('REVIEW_ONLY')
        scene.collection.children.link(st)
    return st


def staged(o):
    for c in list(o.users_collection):
        c.objects.unlink(o)
    stage_collection().objects.link(o)
    return o


def aim(o, target):
    o.rotation_euler = (Vector(target) - o.location).to_track_quat('-Z', 'Y').to_euler()


if QUICK:
    # Shape + colour-field check: low-sample Cycles (shows the mask-mixed colours).
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 12
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = 'Standard'
    scene.world = bpy.data.worlds.new('Quick sky')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (*srgb((176, 186, 200)), 1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .8
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
    sun = staged(bpy.context.object)
    sun.data.energy = 3.2
    sun.rotation_euler = (math.radians(50), 0, math.radians(-30))
    bpy.ops.object.camera_add()
    cam = staged(bpy.context.object)
    scene.camera = cam
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = 10.5
    scene.render.resolution_x = 520
    scene.render.resolution_y = 600
    for label, ang in [('Front', 0), ('Side', 90), ('ThreeQuarter', 30), ('Back', 180)]:
        R = Matrix.Rotation(math.radians(ang), 3, 'Z')
        cam.location = R @ Vector((0, -20, 4.6))
        aim(cam, (0, 0, 4.6))
        scene.render.filepath = str(OUT / '_work' / f'quick_{label}.png')
        bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / '_work' / 'quick.blend'))
    log('QUICK_DONE')
    import sys
    sys.exit(0)

# ------------------------------------------------------------------ UVs and per-section 1024 bake
SECTION_KEY = {'Body': 'fur', 'Head': 'fur', 'EyeGlow': 'eye', 'Hands': 'fur', 'Feet': 'fur', 'Tail': 'mane', 'Shorts': 'shorts'}
prefs = bpy.context.preferences.addons['cycles'].preferences
gpu = False
for dev_type in ('OPTIX', 'CUDA'):
    try:
        prefs.compute_device_type = dev_type
        prefs.get_devices()
        devs = [d for d in prefs.devices if d.type == dev_type]
        if devs:
            for d in prefs.devices:
                d.use = d.type in (dev_type, 'CPU')
            gpu = True
            break
    except Exception:
        pass
scene.render.engine = 'CYCLES'
scene.cycles.device = 'GPU' if gpu else 'CPU'
scene.cycles.samples = 1
scene.render.bake.margin = 8
scene.render.bake.use_clear = False     # keep the section colour in unused texture space
TEX = OUT / 'textures'
IMAGES = {}
for sec, o in FINALS.items():
    active(o)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.004, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(rotate=True, margin=.004)
    bpy.ops.object.mode_set(mode='OBJECT')
    img = bpy.data.images.new(f'{NAME}_{sec}_BaseColor', width=1024, height=1024, alpha=False)
    img.generated_color = (*srgb(COL[SECTION_KEY[sec]]), 1)
    for m in o.data.materials:
        nt = m.node_tree
        node = nt.nodes.get('BakeTarget') or nt.nodes.new('ShaderNodeTexImage')
        node.name = 'BakeTarget'
        node.image = img
        for x in nt.nodes:
            x.select = False
        node.select = True
        nt.nodes.active = node
    active(o)
    bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, margin=8, use_clear=False)
    path = TEX / f'{NAME}_{sec}_BaseColor_1024.png'
    img.filepath_raw = str(path)
    img.file_format = 'PNG'
    img.save()
    img.pack()
    IMAGES[sec] = img
    log('baked', sec)

# Replace the procedural materials with one delivery material per section.
for sec, o in FINALS.items():
    m = bpy.data.materials.new(f'{NAME}_{sec}')
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')
    p.inputs['Roughness'].default_value = .86
    p.inputs['Specular IOR Level'].default_value = .15
    t = nt.nodes.new('ShaderNodeTexImage')
    t.name = 'BaseColor'
    t.image = IMAGES[sec]
    nt.links.new(t.outputs['Color'], p.inputs['Base Color'])
    if sec == 'EyeGlow':
        nt.links.new(t.outputs['Color'], p.inputs['Emission Color'])
        p.inputs['Emission Strength'].default_value = 2.5
    o.data.materials.clear()
    o.data.materials.append(m)
    for poly in o.data.polygons:
        poly.material_index = 0
for m in list(MATS.values()):
    bpy.data.materials.remove(m)

# ------------------------------------------------------------------ armature
log('rig')
arm = bpy.data.armatures.new(NAME + '_Rig')
rig = bpy.data.objects.new(NAME + '_Rig', arm)
scene.collection.objects.link(rig)
active(rig)
bpy.ops.object.mode_set(mode='EDIT')
root = arm.edit_bones.new('Root')
root.head = (0, 0, 0)
root.tail = (0, 0, .4)
for name, (h, t, p) in BONES_STUDS.items():
    eb = arm.edit_bones.new(name)
    eb.head = h
    eb.tail = t
for name, (h, t, p) in BONES_STUDS.items():
    arm.edit_bones[name].parent = arm.edit_bones[p]
    arm.edit_bones[name].use_connect = False
for eb in arm.edit_bones:
    eb.use_deform = True
    eb.roll = 0
bpy.ops.object.mode_set(mode='OBJECT')
rig.show_in_front = True
BNAMES = [b.name for b in arm.bones]
IDX = {n: i for i, n in enumerate(BNAMES)}
import numpy as np


def write_weights(o, W):
    """W: (verts, bones) array. Keep the 4 largest, normalise."""
    for g in list(o.vertex_groups):
        o.vertex_groups.remove(g)
    groups = [o.vertex_groups.new(name=n) for n in BNAMES]
    for i, row in enumerate(W):
        top = np.argsort(row)[-4:]
        top = [j for j in top if row[j] > 1e-4]
        tot = float(sum(row[j] for j in top))
        if tot <= 0:
            raise RuntimeError('unweighted vertex in ' + o.name)
        for j in top:
            groups[j].add([i], float(row[j] / tot), 'REPLACE')


def laplace(o, W, iters, keep=.5):
    e = np.array([list(ed.vertices) for ed in o.data.edges], dtype=int)
    src = np.concatenate((e[:, 0], e[:, 1]))
    dst = np.concatenate((e[:, 1], e[:, 0]))
    deg = np.bincount(src, minlength=len(W))[:, None]
    for _ in range(iters):
        acc = np.zeros_like(W)
        np.add.at(acc, src, W[dst])
        W = keep * W + (1 - keep) * acc / np.maximum(1, deg)
    return W


def interp(pts, z):
    if z <= pts[0][0]:
        return pts[0][1]
    for (z0, a), (z1, b) in zip(pts, pts[1:]):
        if z <= z1:
            return a + (b - a) * (z - z0) / (z1 - z0)
    return pts[-1][1]


# Torso/arm split: midway between the rib/hip surface and the arm's inner surface,
# widening into a broad blend over the deltoid.
ARM_SPLIT = [(2.2, 1.42), (3.0, 1.40), (3.4, 1.26), (4.0, 1.22), (4.4, 1.19), (5.1, 1.24)]
ARM_BLEND = [(2.2, .08), (4.2, .10), (5.1, .40)]


def body_weights(o):
    mane = [d.value for d in o.data.attributes['ManeMask'].data]
    W = np.zeros((len(o.data.vertices), len(BNAMES)))
    for v in o.data.vertices:
        x, y, z = v.co / K
        side = 'Left' if x > 0 else 'Right'
        ax = abs(x)
        a0 = interp(ARM_SPLIT, z)
        arm_f = smooth01(a0, a0 + interp(ARM_BLEND, z), ax) if z > 2.2 else 0.0
        if mane[v.index] > .5 and z > 4.6:
            arm_f *= .12          # the mane rides the shoulders/chest, never the raised arm
        leg = 1 - smooth01(2.84, 3.10, z)
        spine = smooth01(3.15, 3.65, z)
        chest = smooth01(3.90, 4.45, z)
        neck = smooth01(5.30, 5.62, z) * smooth01(-.05, -.35, y)
        neck = max(neck, smooth01(5.55, 5.85, z))
        headw = smooth01(5.95, 6.30, z)
        torso = {'Pelvis': 1 - spine, 'Spine': spine * (1 - chest), 'Chest': chest * (1 - neck), 'Neck': neck * (1 - headw), 'Head': neck * headw}
        trap = smooth01(.55, 1.10, ax) * smooth01(4.85, 5.30, z) * .5 * (1 - neck)
        if mane[v.index] > .5:
            trap = max(trap, .6 * smooth01(.5, 1.0, ax) * smooth01(4.6, 5.0, z) * (1 - neck))
        torso = {k: val * (1 - trap) for k, val in torso.items()}
        torso[side + 'Shoulder'] = trap
        mw = smooth01(4.25, 4.90, z) * smooth01(.0, .45, y) * (1 - smooth01(5.9, 6.3, z))
        if mane[v.index] > .5:
            mw = max(mw, .55 * smooth01(4.4, 4.9, z) * smooth01(-.1, .3, y))
        mw = min(mw, .75)
        torso = {k: val * (1 - mw) for k, val in torso.items()}
        torso['Mane'] = mw
        knee = smooth01(1.58, 1.86, z)
        foot = 1 - smooth01(.46, .64, z)
        legs = {side + 'Thigh': knee * (1 - foot), side + 'Shin': (1 - knee) * (1 - foot), side + 'Foot': foot}
        hip_blend = smooth01(2.62, 3.05, z) * .3
        legs = {k: val * (1 - hip_blend) for k, val in legs.items()}
        legs['Pelvis'] = hip_blend
        handw = 1 - smooth01(2.44, 2.70, z)
        upper_t = smooth01(3.64, 3.92, z) * (1 - handw)
        shoulder = upper_t * smooth01(4.70, 5.24, z) * .85
        arms = {side + 'Shoulder': shoulder, side + 'UpperArm': upper_t - shoulder,
                side + 'Forearm': (1 - smooth01(3.64, 3.92, z)) * (1 - handw), side + 'Hand': handw}
        row = {}
        for k, val in torso.items():
            row[k] = row.get(k, 0) + val * (1 - arm_f) * (1 - leg)
        for k, val in legs.items():
            row[k] = row.get(k, 0) + val * (1 - arm_f) * leg
        for k, val in arms.items():
            row[k] = row.get(k, 0) + val * arm_f
        def split(a_set, b, helper, mask=1.):
            wa = sum(row.get(a, 0) for a in a_set)
            wb = row.get(b, 0)
            tot = wa + wb
            if tot < 1e-6 or mask <= 0:
                return
            u = wb / tot
            h = 4 * u * (1 - u) * tot * .85 * mask
            for a in a_set:
                row[a] = row.get(a, 0) * (1 - h / tot)
            row[b] = wb * (1 - h / tot)
            row[helper] = row.get(helper, 0) + h
        split([side + 'Thigh'], side + 'Shin', side + 'KneeHelper')
        split([side + 'UpperArm'], side + 'Forearm', side + 'ElbowHelper')
        split(['Chest', 'Spine', 'Neck', 'Mane', side + 'Shoulder'], side + 'UpperArm', side + 'ShoulderHelper', smooth01(4.2, 4.6, z))
        for k, val in row.items():
            W[v.index, IDX[k]] += val
    W = laplace(o, W, 2, .6)
    return W


def rigid(o, fn):
    W = np.zeros((len(o.data.vertices), len(BNAMES)))
    for v in o.data.vertices:
        for k, val in fn(v).items():
            W[v.index, IDX[k]] += val
    return W


log('weights')
Wb = body_weights(skin)
write_weights(skin, Wb)
jm = [d.value for d in head.data.attributes['JawMask'].data]
write_weights(head, rigid(head, lambda v: {'Jaw': 1.0} if jm[v.index] > .5 else {'Head': 1.0}))
write_weights(eyeglow, rigid(eyeglow, lambda v: {'Head': 1.0}))
fmask = [d.value for d in hands.data.attributes['FingerMask'].data]


def hand_w(v):
    side = 'Left' if v.co.x > 0 else 'Right'
    if fmask[v.index] > .5:
        f = smooth01(2.12 * K, 1.96 * K, v.co.z)
        return {side + 'Fingers': f, side + 'Hand': 1 - f}
    return {side + 'Hand': 1.0}


write_weights(hands, rigid(hands, hand_w))
BALL = {s: Vector(BONES_STUDS[s + 'Toes'][0]) for s in ('Left', 'Right')}
FOOTDIR = {s: (Vector(BONES_STUDS[s + 'Toes'][1]) - Vector(BONES_STUDS[s + 'Toes'][0])).normalized() for s in ('Left', 'Right')}


def foot_w(v):
    side = 'Left' if v.co.x > 0 else 'Right'
    d = (v.co - BALL[side]).dot(FOOTDIR[side])
    f = smooth01(-.08 * K, .10 * K, d)
    return {side + 'Toes': f, side + 'Foot': 1 - f}


write_weights(feet, rigid(feet, foot_w))
TPS = [Vector(p) * K for p in [(0, .64, 3.10), (0, 1.10, 2.72), (0, 1.36, 2.22), (0, 1.48, 1.62)]]


def tail_w(v):
    t = chain_param(v.co, TPS)            # 0..1 along Tail1..Tail3
    a = smooth01(.26, .44, t)
    b = smooth01(.58, .76, t)
    return {'Tail1': 1 - a, 'Tail2': a * (1 - b), 'Tail3': b}


Wt = laplace(tail, rigid(tail, tail_w), 3)
write_weights(tail, Wt)
# Shorts: averaged weights of the 6 nearest skin vertices, then relaxed.
kd = KDTree(len(skin.data.vertices))
for v in skin.data.vertices:
    kd.insert(v.co, v.index)
kd.balance()
Ws = np.zeros((len(shorts.data.vertices), len(BNAMES)))
for v in shorts.data.vertices:
    near = kd.find_n(v.co, 6)
    tot = 0
    for co, i, d in near:
        w = 1 / max(d, .02)
        Ws[v.index] += Wb[i] * w
        tot += w
    Ws[v.index] /= tot
Ws = laplace(shorts, Ws, 3)
write_weights(shorts, Ws)
for sec, o in FINALS.items():
    o.parent = rig
    mod = o.modifiers.new('Armature', 'ARMATURE')
    mod.object = rig
for o in FINALS.values():
    o.data.update()

# ------------------------------------------------------------------ manifest + save
rest_lo = Vector((1e9, 1e9, 1e9))
rest_hi = -rest_lo
for o in FINALS.values():
    for v in o.data.vertices:
        rest_lo = Vector(map(min, rest_lo, v.co))
        rest_hi = Vector(map(max, rest_hi, v.co))
ref = OUT / 'source' / '05-alpha-werewolf.png'
manifest = {'id': 'alpha-werewolf', 'name': 'Blood Moon Alpha', 'units': 'studs (1 Blender unit = 1 stud)', 'scaleFromBaseUnits': K,
            'axes': 'faces -Y, +Z up, anatomical Left at +X; Studio = (-X, Z, Y)',
            'reference': {'path': 'source/05-alpha-werewolf.png', 'sha256': hashlib.sha256(ref.read_bytes()).hexdigest()},
            'dimensions': {'min': [round(x, 4) for x in rest_lo], 'max': [round(x, 4) for x in rest_hi],
                           'height': round(rest_hi.z, 4)},
            'triangles': TRIS, 'totalTriangles': sum(TRIS.values()),
            'bones': [{'name': b.name, 'parent': b.parent.name if b.parent else None, 'head': [round(x, 4) for x in b.head_local],
                       'tail': [round(x, 4) for x in b.tail_local], 'deform': b.use_deform} for b in arm.bones],
            'sections': {sec: {'object': o.name, 'material': f'{NAME}_{sec}', 'texture': f'textures/{NAME}_{sec}_BaseColor_1024.png'}
                         for sec, o in FINALS.items()},
            'textures': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(TEX.glob('*.png'))}}
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2))
log('height', rest_hi.z, 'bounds', list(rest_lo), list(rest_hi))

# Review stage (excluded from export by collection).
scene.world = bpy.data.worlds.new('Studio sky')
scene.world.use_nodes = True
bg = scene.world.node_tree.nodes['Background']
bg.inputs[0].default_value = (.55, .70, .95, 1)     # Studio-like blue sky ambient
bg.inputs[1].default_value = .55
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, 0))
floor = staged(bpy.context.object)
floor.name = 'ReviewGround'
fm_ = bpy.data.materials.new('ReviewGround')
fm_.use_nodes = True
fm_.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*srgb((168, 166, 160)), 1)
fm_.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .95
floor.data.materials.append(fm_)
lights = []
for pos, power, size, col in [((-6, -9, 11), 2400, 8, (1, .90, .76)), ((9, -4, 5), 500, 7, (.9, .95, 1)), ((3, 10, 9), 1100, 6, (1, .97, .92))]:
    bpy.ops.object.light_add(type='AREA', location=pos)
    L = staged(bpy.context.object)
    L.data.energy = power
    L.data.size = size
    L.data.color = col
    lights.append((L, Vector(pos)))
bpy.ops.object.camera_add()
cam = staged(bpy.context.object)
cam.name = 'ReviewCam'
scene.camera = cam
center = Vector((0, 0, 4.6))


def view(angle, distance=30, ortho=11.0, height=4.6):
    R = Matrix.Rotation(math.radians(angle), 3, 'Z')
    for L, p in lights:
        L.location = R @ p
        aim(L, center)
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = ortho
    cam.location = R @ Vector((0, -distance, height))
    aim(cam, Vector((0, 0, height)))


scene.render.engine = 'CYCLES'
scene.cycles.samples = 64
scene.cycles.use_denoising = True
scene.view_settings.view_transform = 'Standard'
if hasattr(scene.render.image_settings, 'media_type'):
    scene.render.image_settings.media_type = 'IMAGE'
scene.render.image_settings.file_format = 'PNG'
scene.render.resolution_percentage = 100
rig.data.pose_position = 'REST'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / f'{NAME}.blend'))
log('saved blend')

PREV = OUT / 'previews'
scene.render.resolution_x = 900
scene.render.resolution_y = 1024
for angle, label in [(0, 'Front'), (180, 'Back'), (90, 'Side'), (35, 'ThreeQuarter')]:
    view(angle)
    scene.render.filepath = str(PREV / f'{label}.png')
    bpy.ops.render.render(write_still=True)
# Hero: low perspective 3/4 with a warm key.
cam.data.type = 'PERSP'
cam.data.lens = 50
R = Matrix.Rotation(math.radians(-32), 3, 'Z')
for L, p in lights:
    L.location = R @ p
    aim(L, center)
cam.location = Vector((-7.5, -12.5, 2.6))
aim(cam, Vector((0, 0, 4.9)))
scene.render.resolution_x = 1024
scene.render.resolution_y = 1024
scene.render.filepath = str(PREV / 'Hero.png')
bpy.ops.render.render(write_still=True)

# Scale check beside the regular werewolf (appended read-only from its delivery blend).
src = OUT.parent / 'mob-production' / 'combat-ready' / 'werewolf' / 'Model.blend'
with bpy.data.libraries.load(str(src), link=False) as (data_from, data_to):
    data_to.objects = [n for n in data_from.objects if n in ('Rig', 'Werewolf fur skin', 'Head_Geometry', 'LeftHand_Geometry', 'LeftFoot_Geometry',
                                                              'RightHand_Geometry', 'RightFoot_Geometry', 'Tail_Geometry', 'Torn shorts')]
ww = []
for o in data_to.objects:
    if o is None:
        continue
    stage_collection().objects.link(o)
    ww.append(o)
wrig = next(o for o in ww if o.type == 'ARMATURE')
wrig.location = (3.7, 0, 0)
if wrig.animation_data:
    wrig.animation_data.action = None
wrig.data.pose_position = 'REST'
rig.location = (-3.0, 0, 0)
view(20, ortho=13.5, height=4.8)
scene.render.resolution_x = 1024
scene.render.resolution_y = 800
scene.render.filepath = str(PREV / 'ScaleCompare.png')
bpy.ops.render.render(write_still=True)
ww_h = max((o.matrix_world @ v.co).z for o in ww if o.type == 'MESH' for v in o.data.vertices)
for o in ww:
    bpy.data.objects.remove(o, do_unlink=True)
rig.location = (0, 0, 0)
manifest['scaleCheck'] = {'regularWerewolfHeight': round(ww_h, 4), 'alphaHeight': round(rest_hi.z, 4), 'ratio': round(rest_hi.z / ww_h, 4)}
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2))
view(35)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / f'{NAME}.blend'))
log('BUILD_COMPLETE', json.dumps(manifest['scaleCheck']))
