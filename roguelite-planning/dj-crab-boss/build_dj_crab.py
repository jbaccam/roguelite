"""DJ Crab: Beach Cove round-10 leader ("CRAB RAVE"). Model, rig, atlas, rest renders.

Run under Blender 5.2, headless:
    blender -b --factory-startup --python-exit-code 1 --python build_dj_crab.py
    (DJ_QUICK=1 skips the bake and renders flat-colour Workbench checks only)

Self-contained. Reads only the reference sheet's bytes (for its SHA256). All
geometry is procedural; every texture is baked from procedural shaders written
here. 1 Blender unit = 1 stud. The crab faces -Y, +Z is up, its left is +X
(the same frame as king-crab-boss; Studio = (-X, Z, Y)).

Writes
    DJCrab.blend                      model + rig (no clips; animate_game.py adds them)
    textures/DJCrab_Atlas_BaseColor_2048.png  master atlas
    textures/DJCrab_Atlas_BaseColor_1024.png  Roblox delivery atlas (all six sections share it)
    previews/Front.png Back.png Side.png ThreeQuarter.png   rest pose, EEVEE, 1024x768
    manifest.json                     bones, sections, triangles, dimensions, hashes

Construction
- One complete assembled character: carapace, belly/mouth plates, eye stalks,
  8 walking legs, 2 pincer arms, and the DJ gear fitted to the shell.
- The gear is conformed to the shell by ray casting against the carapace mesh:
  straps and the headband lie on the shell (inner face 0.02-0.03 inside it),
  the saddle's underside is the shell surface pushed 0.04 inward, the speakers
  sit 0.02 into the saddle top and the ear cups 0.08 into the shell. Nothing floats.
- Every part is rigid: weighted 1.0 to exactly one bone. Exoskeleton segments
  overlap at cream joint bands (child bone) so bending never opens a gap.
- Sections (mesh objects): DJCrab_Shell, DJCrab_Eyes, DJCrab_Legs,
  DJCrab_Claws, DJCrab_Gear, DJCrab_Glow (LED strips + buttons, for Neon).
"""
import bpy, bmesh, math, json, os, random, hashlib, shutil, time
import numpy as np
from pathlib import Path
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

T0 = time.time()
OUT = Path(__file__).resolve().parent
QUICK = os.environ.get('DJ_QUICK', '0') == '1'
REF = OUT.parent / 'art-references' / 'round-10-modeling-pack-2026-10-09' / '02-dj-crab-complete.png'
for d in ('textures', 'previews', 'exports/game', '_work'):
    (OUT / d).mkdir(parents=True, exist_ok=True)
RNG = random.Random(20261009)
NAME = 'DJCrab'
SECTIONS = ['Shell', 'Eyes', 'Legs', 'Claws', 'Gear', 'Glow']
MASTER_RES, DELIVERY_RES = 2048, 1024


def log(*a):
    print(f'[{time.time() - T0:7.1f}s]', *a, flush=True)


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
COLL = scene.collection


def activate(ob):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def V(*a):
    return Vector(a[0] if len(a) == 1 else a)


# =================================================================== palette
def lin(c):
    def f(x):
        x = x / 255.0
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    return tuple(f(v) for v in c)


# sRGB 0-255, eyedropped from 02-dj-crab-complete.png (lit / mid / shadow areas)
PAL = {
    # warm hues pushed slightly warmer (Studio: blue sky ambient, warm sun, saturation +0.3)
    'shell_lo': (182, 62, 36), 'shell_mid': (222, 92, 54), 'shell_hi': (244, 134, 82),
    'shell_spot': (160, 52, 30), 'shell_rim': (240, 150, 96),
    'leg_lo': (188, 68, 38), 'leg_mid': (228, 100, 56), 'leg_hi': (244, 138, 86),
    'tip_lo': (116, 40, 26), 'tip_mid': (150, 56, 36), 'tip_hi': (180, 80, 50),
    'cream_lo': (204, 158, 108), 'cream_mid': (230, 192, 140), 'cream_hi': (246, 216, 166),
    'seam': (176, 128, 84),
    'eye': (22, 18, 18), 'eye_hl': (250, 244, 226),
    # charcoal kept neutral-warm so it does not drift blue under the sky ambient
    'gear_lo': (40, 38, 36), 'gear_mid': (56, 53, 50), 'gear_hi': (80, 76, 72), 'gear_edge': (104, 98, 92),
    'cone_lo': (22, 21, 20), 'cone_hi': (50, 47, 44),
    'teal_lo': (30, 160, 152), 'teal_mid': (52, 198, 190), 'teal_hi': (120, 228, 220),
    'strap_lo': (182, 138, 88), 'strap_mid': (210, 168, 112), 'strap_hi': (230, 196, 140),
    'strap_edge': (154, 112, 68), 'stitch': (118, 84, 52),
    'buckle_lo': (24, 22, 20), 'buckle_hi': (66, 62, 58),
    'glow_teal': (96, 240, 228), 'glow_orange': (255, 116, 46),
}
FLAT = {  # flat colours for the quick check and viewport
    'shell': 'shell_mid', 'belly': 'cream_mid', 'leg': 'leg_mid', 'tip': 'tip_mid', 'joint': 'cream_hi',
    'claw': 'shell_mid', 'fingertip': 'cream_hi', 'stalk': 'leg_mid', 'eye': 'eye', 'gear': 'gear_mid',
    'cone': 'cone_lo', 'teal': 'teal_mid', 'strap': 'strap_mid', 'buckle': 'buckle_lo',
    'glow_teal': 'glow_teal', 'glow_orange': 'glow_orange',
}


# ================================================================= shaders
class NodeKit:
    def __init__(self, nt):
        self.nt = nt

    def set(self, sock, v):
        if hasattr(v, 'node'):
            self.nt.links.new(v, sock)
        elif isinstance(v, (tuple, list)) and len(v) == 3 and sock.type == 'RGBA':
            sock.default_value = (*v, 1)
        else:
            sock.default_value = v

    def attr(self, name):
        a = self.nt.nodes.new('ShaderNodeAttribute')
        a.attribute_type = 'GEOMETRY'
        a.attribute_name = name
        return a

    def noise(self, vec, scale, detail=2.0, rough=0.5, w=0.0):
        n = self.nt.nodes.new('ShaderNodeTexNoise')
        n.noise_dimensions = '4D'
        self.set(n.inputs['Vector'], vec)
        n.inputs['Scale'].default_value = scale
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough
        n.inputs['W'].default_value = w
        return n.outputs['Fac']

    def voronoi(self, vec, scale, feature='F1', rand=1.0):
        n = self.nt.nodes.new('ShaderNodeTexVoronoi')
        n.voronoi_dimensions = '3D'
        n.feature = feature
        self.set(n.inputs['Vector'], vec)
        n.inputs['Scale'].default_value = scale
        if 'Randomness' in n.inputs:
            n.inputs['Randomness'].default_value = rand
        return n.outputs['Distance']

    def vmath(self, op, a, b=None, out=0):
        m = self.nt.nodes.new('ShaderNodeVectorMath')
        m.operation = op
        self.set(m.inputs[0], a)
        if b is not None:
            self.set(m.inputs[1], b)
        return m.outputs[out]

    def warp(self, vec, amount, scale, w=0.0):
        n = self.nt.nodes.new('ShaderNodeTexNoise')
        n.noise_dimensions = '4D'
        self.set(n.inputs['Vector'], vec)
        n.inputs['Scale'].default_value = scale
        n.inputs['W'].default_value = w
        sc = self.vmath('SCALE', n.outputs['Color'])
        sc.node.inputs['Scale'].default_value = amount
        off = self.vmath('SUBTRACT', sc, (amount * 0.5,) * 3)
        return self.vmath('ADD', vec, off)

    def math(self, op, a, b=None):
        m = self.nt.nodes.new('ShaderNodeMath')
        m.operation = op
        self.set(m.inputs[0], a)
        if b is not None:
            self.set(m.inputs[1], b)
        return m.outputs[0]

    def sep(self, vec):
        s = self.nt.nodes.new('ShaderNodeSeparateXYZ')
        self.set(s.inputs[0], vec)
        return s.outputs

    def ramp(self, fac, stops):
        r = self.nt.nodes.new('ShaderNodeValToRGB')
        r.color_ramp.interpolation = 'LINEAR'
        els = r.color_ramp.elements
        while len(els) > 1:
            els.remove(els[-1])
        for i, (pos, col) in enumerate(stops):
            e = els[0] if i == 0 else els.new(pos)
            e.position = pos
            e.color = (*lin(PAL[col]), 1)
        self.set(r.inputs[0], fac)
        return r.outputs[0]

    def step(self, fac, lo, hi):
        m = self.nt.nodes.new('ShaderNodeMapRange')
        m.clamp = True
        m.interpolation_type = 'SMOOTHSTEP'
        self.set(m.inputs['Value'], fac)
        m.inputs['From Min'].default_value = lo
        m.inputs['From Max'].default_value = hi
        return m.outputs[0]

    def mix(self, fac, a, b):
        m = self.nt.nodes.new('ShaderNodeMix')
        m.data_type = 'RGBA'
        m.blend_type = 'MIX'
        m.clamp_factor = True
        self.set(m.inputs['Factor'], fac)
        self.set(m.inputs[6], a)
        self.set(m.inputs[7], lin(PAL[b]) if isinstance(b, str) else b)
        return m.outputs[2]

    def mul(self, col, fac):
        m = self.nt.nodes.new('ShaderNodeMix')
        m.data_type = 'RGBA'
        m.blend_type = 'MULTIPLY'
        m.clamp_factor = True
        m.inputs['Factor'].default_value = 1.0
        self.set(m.inputs[6], col)
        self.set(m.inputs[7], fac)
        return m.outputs[2]


def new_mat(name):
    m = bpy.data.materials.new(name)
    if hasattr(m, 'use_nodes') and not m.node_tree:
        m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.name = 'Output'
    bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bs.name = 'BSDF'
    bs.inputs['Roughness'].default_value = 0.85
    for key in ('Specular IOR Level', 'Specular'):
        if key in bs.inputs:
            bs.inputs[key].default_value = 0.15
    em = nt.nodes.new('ShaderNodeEmission')
    em.name = 'BakeEmit'
    nt.links.new(bs.outputs[0], out.inputs['Surface'])
    return m, nt, bs, em


def painterly(key):
    """Painterly base-colour recipe per paint key (2-4 value ranges, broad
    patches, facet jitter, top light, low-noise). Returns the material."""
    m, nt, bs, em = new_mat(f'paint_{key}')
    m.diffuse_color = (*lin(PAL[FLAT[key]]), 1)
    K = NodeKit(nt)
    P = K.attr('restP').outputs['Vector']
    facet = K.attr('facet').outputs['Fac']
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    nz = K.sep(geo.outputs['Normal'])[2]
    pz = K.sep(P)[2]
    lit = K.step(nz, 0.15, 0.95)
    jit = K.math('ADD', K.math('MULTIPLY', facet, 0.13), 0.935)

    def shell_like(lo, mid, hi, spot, spot_amt, spot_scale):
        c = K.ramp(K.noise(P, 0.55), [(0.30, lo), (0.50, mid), (0.70, hi)])
        wp = K.warp(P, 0.55, 0.9, 3.0)
        sp = K.step(K.voronoi(wp, spot_scale), 0.46, 0.24)
        sp = K.math('MULTIPLY', sp, K.step(K.noise(P, 1.6, w=7.0), 0.36, 0.52))
        c = K.mix(K.math('MULTIPLY', sp, spot_amt), c, spot)
        c = K.mix(K.math('MULTIPLY', lit, 0.32), c, hi)
        return c

    if key == 'shell':
        c = shell_like('shell_lo', 'shell_mid', 'shell_hi', 'shell_spot', 0.80, 1.25)
        low = K.step(pz, Z_RIM + 0.30, Z_RIM - 0.05)
        c = K.mix(K.math('MULTIPLY', low, 0.28), c, 'shell_lo')
        rim = K.step(K.math('ABSOLUTE', K.math('SUBTRACT', pz, Z_RIM - 0.07)), 0.09, 0.02)
        c = K.mix(K.math('MULTIPLY', rim, 0.40), c, 'shell_rim')
    elif key in ('claw', 'stalk'):
        c = shell_like('shell_lo', 'shell_mid', 'shell_hi', 'shell_spot', 0.75, 1.9)
    elif key == 'leg':
        c = shell_like('leg_lo', 'leg_mid', 'leg_hi', 'shell_spot', 0.35, 3.4)
    elif key == 'tip':
        c = K.ramp(K.noise(P, 1.1), [(0.3, 'tip_lo'), (0.5, 'tip_mid'), (0.72, 'tip_hi')])
        c = K.mix(K.math('MULTIPLY', lit, 0.25), c, 'tip_hi')
    elif key in ('belly', 'joint', 'fingertip'):
        c = K.ramp(K.noise(P, 0.9), [(0.30, 'cream_lo'), (0.5, 'cream_mid'), (0.72, 'cream_hi')])
        if key == 'belly':
            seam = K.step(K.voronoi(K.warp(P, 0.25, 1.2), 2.3, 'DISTANCE_TO_EDGE'), 0.075, 0.025)
            c = K.mix(K.math('MULTIPLY', seam, 0.62), c, 'seam')
            down = K.step(nz, -0.15, -0.9)
            c = K.mix(K.math('MULTIPLY', down, 0.28), c, 'cream_lo')
        c = K.mix(K.math('MULTIPLY', lit, 0.30), c, 'cream_hi')
    elif key == 'eye':
        ec = K.attr('eyeC').outputs['Vector']
        d = K.vmath('NORMALIZE', K.vmath('SUBTRACT', P, ec))
        hl = K.step(K.vmath('DOT_PRODUCT', d, Vector((-0.30, -0.55, 0.78)).normalized(), out=1), 0.88, 0.95)
        hl2 = K.step(K.vmath('DOT_PRODUCT', d, Vector((0.55, -0.70, 0.10)).normalized(), out=1), 0.95, 0.985)
        c = K.mix(hl, lin(PAL['eye']), 'eye_hl')
        c = K.mix(K.math('MULTIPLY', hl2, 0.6), c, 'eye_hl')
        jit = 1.0
    elif key == 'gear':
        c = K.ramp(K.noise(P, 1.1), [(0.32, 'gear_lo'), (0.5, 'gear_mid'), (0.70, 'gear_mid')])
        c = K.mix(K.math('MULTIPLY', lit, 0.45), c, 'gear_hi')
        edge = K.attr('edge').outputs['Fac']
        c = K.mix(K.math('MULTIPLY', edge, 0.55), c, 'gear_edge')
    elif key == 'cone':
        u = K.attr('u').outputs['Fac']
        c = K.ramp(u, [(0.0, 'cone_lo'), (0.55, 'cone_hi'), (0.62, 'cone_lo'), (1.0, 'cone_hi')])
    elif key == 'teal':
        c = K.ramp(K.noise(P, 1.3), [(0.3, 'teal_lo'), (0.5, 'teal_mid'), (0.7, 'teal_mid')])
        c = K.mix(K.math('MULTIPLY', lit, 0.45), c, 'teal_hi')
    elif key == 'strap':
        c = K.ramp(K.noise(P, 1.4), [(0.3, 'strap_lo'), (0.5, 'strap_mid'), (0.7, 'strap_hi')])
        ac = K.math('ABSOLUTE', K.attr('across').outputs['Fac'])
        c = K.mix(K.math('MULTIPLY', K.step(ac, 0.80, 0.98), 0.55), c, 'strap_edge')
        al = K.attr('along').outputs['Fac']
        dash = K.step(K.math('FRACT', K.math('MULTIPLY', al, 7.0)), 0.62, 0.48)
        line = K.step(K.math('ABSOLUTE', K.math('SUBTRACT', ac, 0.64)), 0.075, 0.03)
        c = K.mix(K.math('MULTIPLY', K.math('MULTIPLY', dash, line), 0.7), c, 'stitch')
        c = K.mix(K.math('MULTIPLY', lit, 0.18), c, 'strap_hi')
    elif key == 'buckle':
        c = K.mix(K.math('MULTIPLY', lit, 0.6), lin(PAL['buckle_lo']), 'buckle_hi')
        edge = K.attr('edge').outputs['Fac']
        c = K.mix(K.math('MULTIPLY', edge, 0.5), c, 'buckle_hi')
    elif key in ('glow_teal', 'glow_orange'):
        c = K.mix(K.math('MULTIPLY', lit, 0.25), lin(PAL[key]), (1.0, 0.93, 0.85))
        jit = 1.0
    else:
        raise KeyError(key)
    if not isinstance(jit, float):
        c = K.mul(c, jit)
    nt.links.new(c, bs.inputs['Base Color'])
    nt.links.new(c, em.inputs['Color'])
    if key == 'eye':
        bs.inputs['Roughness'].default_value = 0.25
    return m


MATS = {}


def paint(key):
    if key not in MATS:
        MATS[key] = painterly(key)
    return MATS[key]


# ================================================================= geometry
PARTS = []


def mesh_part(name, verts, faces, mats, bone, section, smooth=False, u=None, across=None, along=None,
              edge=None, eyec=None, recalc=True):
    """One rigid part. mats: one paint key or a per-face list."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    if recalc:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(me)
        bm.free()
    ob = bpy.data.objects.new(name, me)
    COLL.objects.link(ob)
    fm = mats if isinstance(mats, list) else [mats] * len(me.polygons)
    keys = list(dict.fromkeys(fm))
    for k in keys:
        me.materials.append(paint(k))
    me.polygons.foreach_set('material_index', [keys.index(k) for k in fm])
    if smooth:
        me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    nv, nf = len(me.vertices), len(me.polygons)

    def put(nm, vals, typ='FLOAT', dom='POINT'):
        a = me.attributes.new(nm, typ, dom)
        arr = np.asarray(vals, np.float32 if typ != 'INT' else np.int32).ravel()
        a.data.foreach_set('vector' if typ == 'FLOAT_VECTOR' else 'value', arr)

    co = np.empty(nv * 3, np.float32)
    me.vertices.foreach_get('co', co)
    put('restP', co, 'FLOAT_VECTOR')
    put('u', u if u is not None else np.zeros(nv))
    put('across', across if across is not None else np.zeros(nv))
    put('along', along if along is not None else np.zeros(nv))
    put('eyeC', eyec if eyec is not None else np.zeros((nv, 3)), 'FLOAT_VECTOR')
    put('edge', edge if edge is not None else np.zeros(nf), 'FLOAT', 'FACE')
    put('facet', [RNG.random() for _ in range(nf)], 'FLOAT', 'FACE')
    put('section', [SECTIONS.index(section)] * nf, 'INT', 'FACE')
    vg = ob.vertex_groups.new(name=bone)
    vg.add(list(range(nv)), 1.0, 'REPLACE')
    PARTS.append({'obj': ob, 'bone': bone, 'section': section})
    return ob


def superring(c, X, Y, rx, ry, n, ex=2.4, phase=0.0, jit=0.0):
    pts = []
    for k in range(n):
        a = phase + 2 * math.pi * k / n
        ca, sa = math.cos(a), math.sin(a)
        ca = math.copysign(abs(ca) ** (2 / ex), ca)
        sa = math.copysign(abs(sa) ** (2 / ex), sa)
        j = 1 + (RNG.uniform(-jit, jit) if jit else 0.0)
        pts.append(c + X * (rx * ca * j) + Y * (ry * sa * j))
    return pts


def loft(rings, cap0=True, cap1=True, tip0=None, tip1=None):
    """Rings -> (verts, faces, ring_of_vertex). tip0/tip1: apex points instead of caps."""
    n = len(rings[0])
    Vv, F, R = [], [], []
    for i, r in enumerate(rings):
        Vv += [Vector(p) for p in r]
        R += [i] * n
    for i in range(len(rings) - 1):
        for k in range(n):
            F.append((i * n + k, i * n + (k + 1) % n, (i + 1) * n + (k + 1) % n, (i + 1) * n + k))
    last = (len(rings) - 1) * n
    if tip0 is not None:
        Vv.append(Vector(tip0))
        R.append(-1)
        a = len(Vv) - 1
        for k in range(n):
            F.append((a, (k + 1) % n, k))
    elif cap0:
        F.append(tuple(range(n - 1, -1, -1)))
    if tip1 is not None:
        Vv.append(Vector(tip1))
        R.append(len(rings))
        a = len(Vv) - 1
        for k in range(n):
            F.append((last + k, last + (k + 1) % n, a))
    elif cap1:
        F.append(tuple(range(last, last + n)))
    return Vv, F, R


def frame_from(y, x_hint):
    y = Vector(y).normalized()
    x = Vector(x_hint)
    x = (x - y * x.dot(y)).normalized()
    z = x.cross(y)
    return x, y, z


def segment(name, a, b, xaxis, prof, mat, bone, section, n=8, ex=2.4, tip=False, tipmat=None, tip_from=1.1,
            jit=0.025):
    """Loft along a->b. prof: [(u, half_w, half_h)]; width along xaxis, height along x cross y."""
    a, b = Vector(a), Vector(b)
    X, Y, Z = frame_from(b - a, xaxis)
    L = (b - a).length
    rings = [superring(a + Y * (u * L), X, Z, w, h, n, ex, jit=jit) for (u, w, h) in prof]
    Vv, F, R = loft(rings, cap0=True, cap1=not tip, tip1=(b if tip else None))
    us = [prof[r][0] if 0 <= r < len(prof) else (1.0 if r >= len(prof) else 0.0) for r in R]
    fm = mat
    if tipmat:
        fm = []
        for f in F:
            uf = sum(us[i] for i in f) / len(f)
            fm.append(tipmat if uf >= tip_from else mat)
    return mesh_part(name, Vv, F, fm, bone, section, u=us)


def band(name, c, axis, xaxis, r, length, mat, bone, section, n=8):
    c, axis = Vector(c), Vector(axis).normalized()
    X, Y, Z = frame_from(axis, xaxis)
    prof = [(-0.5, 0.86), (-0.2, 1.0), (0.2, 1.0), (0.5, 0.86)]
    rings = [superring(c + Y * (t * length), X, Z, r * k, r * k * 1.06, n, 2.3, jit=0.0) for t, k in prof]
    Vv, F, R = loft(rings)
    return mesh_part(name, Vv, F, mat, bone, section)


def sphere(name, c, r, mat, bone, section, seg=12, rings=8, smooth=True, eyec=None, scale=(1, 1, 1)):
    c = Vector(c)
    Vv = [c + Vector((0, 0, r * scale[2]))]
    for i in range(1, rings):
        th = math.pi * i / rings
        for k in range(seg):
            ph = 2 * math.pi * k / seg
            Vv.append(c + Vector((r * scale[0] * math.sin(th) * math.cos(ph), r * scale[1] * math.sin(th) * math.sin(ph),
                                  r * scale[2] * math.cos(th))))
    Vv.append(c - Vector((0, 0, r * scale[2])))
    F = []
    for k in range(seg):
        F.append((0, 1 + k, 1 + (k + 1) % seg))
    for i in range(rings - 2):
        for k in range(seg):
            a = 1 + i * seg + k
            b = 1 + i * seg + (k + 1) % seg
            F.append((a, a + seg, b + seg, b))
    last = len(Vv) - 1
    base = 1 + (rings - 2) * seg
    for k in range(seg):
        F.append((base + k, last, base + (k + 1) % seg))
    ec = [tuple(eyec)] * len(Vv) if eyec is not None else None
    return mesh_part(name, Vv, F, mat, bone, section, smooth=smooth, eyec=ec)


def torus(name, c, axis, R, r, mat, bone, section, n=16, m=6):
    c, axis = Vector(c), Vector(axis).normalized()
    X, Y, Z = frame_from(axis, Vector((1, 0, 0)) if abs(axis.x) < 0.9 else Vector((0, 1, 0)))
    Vv, F = [], []
    for i in range(n):
        a = 2 * math.pi * i / n
        d = X * math.cos(a) + Z * math.sin(a)
        for j in range(m):
            b = 2 * math.pi * j / m
            Vv.append(c + d * (R + r * math.cos(b)) + Y * (r * math.sin(b)))
    for i in range(n):
        for j in range(m):
            a = i * m + j
            F.append((a, i * m + (j + 1) % m, ((i + 1) % n) * m + (j + 1) % m, ((i + 1) % n) * m + j))
    return mesh_part(name, Vv, F, mat, bone, section)


def bevel_box(hx, hy, hz, bev, segs=2):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * 2 * hx, v.co.y * 2 * hy, v.co.z * 2 * hz))
    bmesh.ops.bevel(bm, geom=list(bm.edges) + list(bm.verts), offset=bev, offset_type='OFFSET', segments=segs,
                    profile=0.5, affect='EDGES', clamp_overlap=True)
    bm.verts.index_update()
    bm.normal_update()
    Vv = [v.co.copy() for v in bm.verts]
    F = [[v.index for v in f.verts] for f in bm.faces]
    N = [f.normal.copy() for f in bm.faces]
    bm.free()
    edge = [0.0 if max(abs(nn.x), abs(nn.y), abs(nn.z)) > 0.995 else 1.0 for nn in N]
    return Vv, F, N, edge


def box_part(name, c, R, hx, hy, hz, bev, mat, bone, section, segs=2, faces_mat=None, panel=None):
    Vv, F, N, edge = bevel_box(hx, hy, hz, bev, segs)
    W = [Vector(c) + R @ v for v in Vv]
    fm = mat
    if faces_mat:
        fm = [faces_mat(N[i], [Vv[j] for j in f]) for i, f in enumerate(F)]
    pan = None
    if panel:
        pan = [panel(v) for v in Vv]
    return mesh_part(name, W, F, fm, bone, section, edge=edge, across=pan)


# ============================================================== carapace
N_SH = 36
ZOFF = -0.35          # the whole body (shell, gear, claws, body bone) sits this much lower than v1
W_SH, D_FRONT, D_REAR, SQ = 1.99, 1.68, 1.84, 2.3
Z_RIM, H_DOME = 2.05 + ZOFF, 0.86
CEN = Vector((0.0, -0.05, 0.0))
TOP_RHO = [0.2, 0.4, 0.58, 0.73, 0.85, 0.93, 0.98, 1.0]
UNDER = [(1.04, Z_RIM - 0.07), (1.0, Z_RIM - 0.20), (0.93, 1.70 + ZOFF), (0.80, 1.55 + ZOFF), (0.60, 1.43 + ZOFF),
         (0.35, 1.35 + ZOFF)]
BOTTOM_Z = 1.32 + ZOFF


def outline(a):
    c, s = math.cos(a), math.sin(a)
    D = D_FRONT if s < 0 else D_REAR
    r = 1.0 / ((abs(c) / W_SH) ** SQ + (abs(s) / D) ** SQ) ** (1 / SQ)
    front = max(0.0, -s) ** 2
    return r * (1 + 0.022 * math.cos(12 * a) + 0.010 * math.sin(7 * a + 0.5) + 0.032 * front * math.cos(18 * a))


def dome_z(rho, a=-math.pi / 2):
    # the rear half is lower and flatter (a deck for the speakers); the peak sits forward
    rear = max(0.0, math.sin(a))
    p = 3.3 + 0.4 * rear
    h = H_DOME - 0.12 * rear * rho ** 1.5
    return Z_RIM + h * max(0.0, 1 - rho ** p) ** 0.55


def belly_z(rho):
    xs = [0.0, 0.35, 0.60, 0.80, 0.93, 1.0]
    zs = [BOTTOM_Z, 1.35 + ZOFF, 1.43 + ZOFF, 1.55 + ZOFF, 1.70 + ZOFF, Z_RIM - 0.20]
    return float(np.interp(rho, xs, zs))


def shell_point(a, rho, z):
    r = outline(a) * rho
    return Vector((CEN.x + r * math.cos(a), CEN.y + r * math.sin(a), z))


def build_carapace():
    rings_top = []
    for rho in TOP_RHO:
        ring = []
        for k in range(N_SH):
            a = 2 * math.pi * k / N_SH + (math.pi / N_SH if TOP_RHO.index(rho) % 2 else 0.0)
            jr = 1 + RNG.uniform(-0.012, 0.012) if rho < 1.0 else 1.0
            p = shell_point(a, rho * jr, dome_z(rho, a) + RNG.uniform(-0.015, 0.015) * (rho < 0.99))
            ring.append(p)
        rings_top.append(ring)
    rings_under = []
    for i, (rho, z) in enumerate(UNDER):
        ring = []
        for k in range(N_SH):
            a = 2 * math.pi * k / N_SH + (math.pi / N_SH if (len(TOP_RHO) + i) % 2 else 0.0)
            ring.append(shell_point(a, rho, z + (RNG.uniform(-0.01, 0.01) if i > 1 else 0.0)))
        rings_under.append(ring)
    rings = rings_top + rings_under
    top = Vector((CEN.x, CEN.y, dome_z(0.0, 0.0)))
    bot = Vector((CEN.x, CEN.y, BOTTOM_Z))
    Vv, F, R = loft(rings, tip0=top, tip1=bot)
    nt = len(TOP_RHO)
    fm = []
    for f in F:
        rs = [R[i] for i in f]
        # faces below the rim lip (ring index >= nt+1) are the cream belly
        fm.append('belly' if min(rs) >= nt + 1 or (min(rs) >= nt + 1 and max(rs) > nt + 1) else 'shell')
    return mesh_part('Carapace', Vv, F, fm, 'Body', 'Shell')


def build_mouth():
    """Cream underside plate under the front rim with a scalloped "smile" lower edge."""
    n = 26
    top, mid, bot = [], [], []
    for k in range(n):
        u = k / (n - 1)
        a = -math.pi / 2 + (u - 0.5) * 0.76
        scal = 0.07 * abs(math.sin(4 * math.pi * u))
        p_top = shell_point(a, 0.99, Z_RIM - 0.24)
        p_mid = shell_point(a, 0.985, Z_RIM - 0.40)
        p_bot = shell_point(a, 0.93, Z_RIM - 0.52 + scal)
        o = Vector((p_top.x, p_top.y, 0)).normalized()
        top.append((p_top + o * 0.02, p_top - o * 0.22))
        mid.append((p_mid + o * 0.06, p_mid - o * 0.22))
        bot.append((p_bot + o * 0.02, p_bot - o * 0.20))
    Vv, F = [], []
    rows = [top, mid, bot]
    for r in rows:
        Vv += [q[0] for q in r]
    for r in rows:
        Vv += [q[1] for q in r]
    no = 3 * n
    for j in range(2):
        for k in range(n - 1):
            a0, a1 = j * n + k, j * n + k + 1
            F.append((a0, a1, a1 + n, a0 + n))
            F.append((no + a0 + n, no + a1 + n, no + a1, no + a0))
    for k in range(n - 1):
        F.append((k + 1, k, no + k, no + k + 1))
        F.append((2 * n + k, 2 * n + k + 1, no + 2 * n + k + 1, no + 2 * n + k))
    for e in (0, n - 1):
        F.append((e, e + n, no + e + n, no + e))
        F.append((e + n, e + 2 * n, no + e + 2 * n, no + e + n))
    mesh_part('SmilePlate', Vv, F, 'belly', 'Body', 'Shell')


# =============================================================== skeleton
BONES = {}   # name -> dict(head, tail, parent, x)


def add_bone(name, parent, head, tail, xaxis):
    head, tail = Vector(head), Vector(tail)
    y = (tail - head).normalized()
    x = Vector(xaxis)
    x = (x - y * x.dot(y)).normalized()
    BONES[name] = {'head': head, 'tail': tail, 'parent': parent, 'x': x, 'z': x.cross(y)}


BODY_C = Vector((0.0, 0.0, 2.15 + ZOFF))
add_bone('Root', None, (0, 0, 0), (0, 0, 1), (1, 0, 0))
add_bone('Body', 'Root', BODY_C, BODY_C + Vector((0, 0, 1)), (1, 0, 0))

# ----------------------------------------------------------------- legs
LEG_AZ = {1: -36.0, 2: -12.0, 3: 13.0, 4: 38.0}
LEG_SC = {1: 0.94, 2: 1.0, 3: 1.0, 4: 0.92}
HIP_RHO = 0.68
LEG_INFO = {}


def build_leg(s, i):
    side = 'L' if s > 0 else 'R'
    tag = f'{side}{i}'
    az = math.radians(LEG_AZ[i])
    a = az if s > 0 else math.pi - az
    o = Vector((math.cos(a), math.sin(a), 0.0))
    sc = LEG_SC[i]
    hip = shell_point(a, HIP_RHO, belly_z(HIP_RHO) - 0.02)
    J1 = hip + o * (0.95 * sc) + Vector((0, 0, -0.16))
    J2 = hip + o * (1.45 * sc) + Vector((0, 0, 0.38))
    J3 = hip + o * (1.88 * sc) + Vector((0, 0, 0.0))
    tip = hip + o * (2.24 * sc)
    tip.z = 0.0
    X = (J2 - J1).cross(J3 - J2).normalized()
    names = [f'Leg_{tag}_{seg}' for seg in ('Coxa', 'Merus', 'Carpus', 'Dactyl')]
    add_bone(names[0], 'Body', hip, J1, X)
    add_bone(names[1], names[0], J1, J2, X)
    add_bone(names[2], names[1], J2, J3, X)
    add_bone(names[3], names[2], J3, tip, X)
    LEG_INFO[tag] = {'hip': hip, 'J1': J1, 'J2': J2, 'J3': J3, 'tip': tip, 'X': X}
    segment(f'{tag}_coxa', hip - (J1 - hip).normalized() * 0.25, J1, X,
            [(0.0, 0.247, 0.26), (0.55, 0.312, 0.325), (1.04, 0.26, 0.273)], 'leg', names[0], 'Legs')
    band(f'{tag}_band1', J1, J2 - J1, X, 0.351, 0.18, 'joint', names[1], 'Legs')
    segment(f'{tag}_merus', J1, J2, X,
            [(-0.05, 0.247, 0.273), (0.12, 0.325, 0.377), (0.5, 0.358, 0.416), (0.88, 0.325, 0.37), (1.05, 0.234, 0.26)],
            'leg', names[1], 'Legs')
    band(f'{tag}_band2', J2, J3 - J2, X, 0.345, 0.18, 'joint', names[2], 'Legs')
    segment(f'{tag}_carpus', J2, J3, X,
            [(-0.06, 0.234, 0.26), (0.15, 0.293, 0.338), (0.5, 0.312, 0.358), (0.85, 0.28, 0.319), (1.05, 0.215, 0.234)],
            'leg', names[2], 'Legs')
    band(f'{tag}_band3', J3, tip - J3, X, 0.305, 0.17, 'joint', names[3], 'Legs')
    mid = J3.lerp(tip, 0.56)
    segment(f'{tag}_propodus', J3, mid, X,
            [(-0.07, 0.215, 0.234), (0.15, 0.26, 0.293), (0.6, 0.267, 0.293), (0.93, 0.234, 0.26), (1.02, 0.202, 0.221)],
            'leg', names[3], 'Legs')
    band(f'{tag}_band4', mid, tip - J3, X, 0.254, 0.12, 'joint', names[3], 'Legs')
    segment(f'{tag}_dactyl', mid, tip, X,
            [(0.0, 0.221, 0.234), (0.16, 0.234, 0.254), (0.5, 0.163, 0.176), (0.86, 0.065, 0.072)],
            'tip', names[3], 'Legs', tip=True)


# ----------------------------------------------------------------- claws
CLAW_INFO = {}
GAPE_REST = 20.0


def build_claw(s):
    side = 'L' if s > 0 else 'R'

    def mx(*v):
        return Vector((s * v[0], v[1], v[2]))
    S = mx(0.84, -1.30, 1.56 + ZOFF)
    M0 = mx(1.20, -1.82, 1.50 + ZOFF)
    E = mx(1.74, -2.22, 1.52 + ZOFF)
    Wr = mx(1.50, -2.62, 1.50 + ZOFF)
    f = mx(-0.30, -0.92, -0.06).normalized()
    upf = (Vector((0, 0, 1)) - f * f.z).normalized()
    side_in = (f.cross(upf)) * s
    rl = math.radians(18)
    up_h = (upf * math.cos(rl) + side_in * math.sin(rl)).normalized()
    side_h = f.cross(up_h).normalized()
    Xe = (E - M0).cross(Wr - E).normalized()
    names = [f'Claw_{side}_{seg}' for seg in ('Coxa', 'Merus', 'Carpus', 'Propodus', 'Dactyl')]
    PALM_L = 1.20
    add_bone(names[0], 'Body', S, M0, Xe)
    add_bone(names[1], names[0], M0, E, Xe)
    add_bone(names[2], names[1], E, Wr, Xe)
    add_bone(names[3], names[2], Wr, Wr + f * PALM_L, Xe)
    D0 = Wr + f * 1.17 + up_h * 0.36
    ang = math.radians(GAPE_REST)
    open_dir = (f * math.cos(ang) + up_h * math.sin(ang)).normalized()
    add_bone(names[4], names[3], D0, D0 + open_dir * 1.09, -side_h)
    CLAW_INFO[side] = {'S': S, 'M0': M0, 'E': E, 'Wr': Wr, 'f': f, 'up': up_h, 'side': side_h, 'D0': D0,
                       'Xe': Xe, 'open_dir': open_dir}
    # meshes: thick arm segments with cream joint bands
    segment(f'Claw{side}_coxa', S - (M0 - S).normalized() * 0.2, M0, Xe,
            [(0.0, 0.22, 0.22), (0.5, 0.28, 0.28), (1.03, 0.23, 0.23)], 'claw', names[0], 'Claws', n=10)
    band(f'Claw{side}_band1', M0, E - M0, Xe, 0.30, 0.20, 'joint', names[1], 'Claws', n=10)
    segment(f'Claw{side}_merus', M0, E, Xe,
            [(-0.06, 0.21, 0.22), (0.15, 0.29, 0.32), (0.5, 0.33, 0.36), (0.85, 0.30, 0.33), (1.06, 0.21, 0.22)],
            'claw', names[1], 'Claws', n=10)
    band(f'Claw{side}_band2', E, Wr - E, Xe, 0.31, 0.20, 'joint', names[2], 'Claws', n=10)
    segment(f'Claw{side}_carpus', E, Wr, Xe,
            [(-0.06, 0.22, 0.23), (0.18, 0.31, 0.32), (0.5, 0.34, 0.35), (0.85, 0.31, 0.32), (1.08, 0.22, 0.23)],
            'claw', names[2], 'Claws', n=10)
    # palm (propodus): broad, flattened wedge, taller on top, pincer plane = (f, up_h)
    prof = [(-0.12, 0.21, 0.24, 0.22), (0.0, 0.32, 0.40, 0.34), (0.28, 0.44, 0.62, 0.46), (0.60, 0.47, 0.70, 0.50),
            (0.94, 0.44, 0.66, 0.48), (1.16, 0.38, 0.60, 0.42), (1.25, 0.32, 0.54, 0.36)]
    rings = [ring2(Wr + f * u, side_h, up_h, w, ht, hb, 14, 2.6) for (u, w, ht, hb) in prof]
    Vv, F, R = loft(rings)
    mesh_part(f'Claw{side}_palm', Vv, F, 'claw', names[3], 'Claws')
    band(f'Claw{side}_wristband', Wr + f * 0.0, f, side_h, 0.32, 0.18, 'joint', names[3], 'Claws', n=10)
    # thick fixed finger (pollex) from the lower front of the palm; spine (u, du, w, h_inner, h_outer)
    pf0 = Wr + f * 1.20 - up_h * 0.16
    spine = [(0.0, 0.0, 0.31, 0.24, 0.31), (0.35, 0.02, 0.29, 0.22, 0.26), (0.67, 0.07, 0.23, 0.17, 0.19),
             (0.94, 0.15, 0.14, 0.11, 0.12)]
    finger(f'Claw{side}_pollex', pf0, f, up_h, side_h, spine, (1.09, 0.23), names[3], +1, (0.17, 0.37, 0.56, 0.76))
    # moving finger (dactyl) hinged at the palm's upper front; authored closed, opened by GAPE_REST
    dspine = [(0.0, 0.0, 0.29, 0.22, 0.29), (0.35, -0.02, 0.26, 0.19, 0.25), (0.67, -0.08, 0.22, 0.14, 0.18),
              (0.94, -0.17, 0.13, 0.10, 0.11)]
    rot = Matrix.Translation(D0) @ Matrix.Rotation(ang, 4, side_h) @ Matrix.Translation(-D0)
    finger(f'Claw{side}_dactyl', D0, f, up_h, side_h, dspine, (1.09, -0.25), names[4], -1, (0.26, 0.46, 0.65, 0.85),
           xf=rot)
    CLAW_INFO[side]['tip_f'] = 2.29
    CLAW_INFO[side]['tip_up'] = 0.07

def ring2(c, X, Y, w, h_pos, h_neg, n, ex=2.4):
    """Superellipse ring with a different half-height above (+Y) and below (-Y)."""
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        ca, sa = math.cos(a), math.sin(a)
        ca = math.copysign(abs(ca) ** (2 / ex), ca)
        sa = math.copysign(abs(sa) ** (2 / ex), sa)
        j = 1 + RNG.uniform(-0.02, 0.02)
        pts.append(c + X * (w * ca * j) + Y * ((h_pos if sa > 0 else h_neg) * sa * j))
    return pts


def finger(name, p0, f, up, sd, spine, tip, bone, inner, teeth_us, xf=None):
    """Thick pincer finger; the biting (inner) edge is cream and carries blunt low-poly teeth.
    inner=+1: biting edge toward +up (fixed finger); -1: toward -up (dactyl)."""
    n = 10
    rings, us = [], []
    for (u, du, w, hi, ho) in spine:
        c = p0 + f * u + up * du
        hp, hn = (hi, ho) if inner > 0 else (ho, hi)
        rings.append(ring2(c, sd, up, w, hp, hn, n, 2.3))
        us.append(u / tip[0])
    tipp = p0 + f * tip[0] + up * tip[1]
    Vv, F, R = loft(rings, cap0=True, tip1=tipp)
    side_val = [math.sin(2 * math.pi * (i % n) / n) * inner if 0 <= R[i] < len(rings) else 0.0 for i in range(len(Vv))]
    uu = [us[r] if 0 <= r < len(us) else 1.0 for r in R]
    fm = []
    for fc in F:
        uf = sum(uu[i] for i in fc) / len(fc)
        sv = sum(side_val[i] for i in fc) / len(fc)
        fm.append('fingertip' if (sv > 0.55 or uf > 0.80) else 'claw')
    for u in teeth_us:
        j = min(range(len(spine) - 1), key=lambda q: abs(spine[q][0] - u) if spine[q][0] <= u else 9)
        t = (u - spine[j][0]) / (spine[j + 1][0] - spine[j][0])
        du = spine[j][1] + (spine[j + 1][1] - spine[j][1]) * t
        hi = spine[j][3] + (spine[j + 1][3] - spine[j][3]) * t
        w = spine[j][2] + (spine[j + 1][2] - spine[j][2]) * t
        base = p0 + f * u + up * (du + inner * hi * 0.82)
        b0 = len(Vv)
        Vv += [base - f * 0.06 + sd * (w * 0.40), base - f * 0.06 - sd * (w * 0.40),
               base + f * 0.06 - sd * (w * 0.40), base + f * 0.06 + sd * (w * 0.40),
               base + up * (inner * 0.085)]
        uu += [0.9] * 5
        F += [(b0, b0 + 1, b0 + 4), (b0 + 1, b0 + 2, b0 + 4), (b0 + 2, b0 + 3, b0 + 4), (b0 + 3, b0, b0 + 4),
              (b0 + 3, b0 + 2, b0 + 1, b0)]
        fm += ['fingertip'] * 5
    if xf is not None:
        Vv = [xf @ v for v in Vv]
    return mesh_part(name, Vv, F, fm, bone, 'Claws', u=uu)


EYE_INFO = {}


def build_eyes(s):
    side = 'L' if s > 0 else 'R'
    x, y = s * 0.48, -1.22
    a = math.atan2(y - CEN.y, x - CEN.x)
    rho = math.hypot(x - CEN.x, y - CEN.y) / outline(a)
    B = Vector((x, y, dome_z(rho, a)))
    d = Vector((s * 0.16, -0.26, 1.0)).normalized()
    E = B + d * 0.66
    X = Vector((1, 0, 0))
    add_bone(f'EyeStalk_{side}', 'Body', B, E, X)
    EYE_INFO[side] = {'B': B, 'E': E, 'd': d}
    segment(f'EyeStalk{side}', B - d * 0.30, B + d * 0.48, X,
            [(0.0, 0.17, 0.17), (0.30, 0.18, 0.18), (0.45, 0.15, 0.15), (0.8, 0.13, 0.13), (1.0, 0.135, 0.135)],
            'stalk', f'EyeStalk_{side}', 'Shell', n=8)
    sphere(f'Eye{side}', E, 0.30, 'eye', f'EyeStalk_{side}', 'Eyes', seg=14, rings=9, eyec=E,
           scale=(1.0, 0.95, 1.08))


# ================================================================= gear
SHELL_BVH = None


def shell_bvh(ob):
    me = ob.data
    vs = [v.co.copy() for v in me.vertices]
    fs = [tuple(p.vertices) for p in me.polygons]
    return BVHTree.FromPolygons(vs, fs)


def hit(origin, direction):
    loc, nrm, idx, dist = SHELL_BVH.ray_cast(Vector(origin), Vector(direction).normalized(), 30.0)
    if loc is None:
        raise RuntimeError(f'ray missed the shell from {tuple(origin)}')
    return loc, nrm


def smooth_normals(ns, it=2):
    ns = [n.copy() for n in ns]
    for _ in range(it):
        ns = [((ns[max(i - 1, 0)] + ns[i] * 2 + ns[min(i + 1, len(ns) - 1)]).normalized()) for i in range(len(ns))]
    return ns


def strap(name, pts, nrms, width, t_out, t_in, mat, buckle_at=(), bev=0.022, cap_in=True):
    """A band lying on the shell; the inner face is t_in inside the surface."""
    nrms = smooth_normals(nrms)
    rings, al, ac = [], [], []
    s_acc = 0.0
    w = width / 2
    prof = [(-w, -t_in), (-w, t_out - bev), (-w + bev, t_out), (w - bev, t_out), (w, t_out - bev), (w, -t_in)]
    frames = []
    for i, p in enumerate(pts):
        tg = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        n = (nrms[i] - tg * nrms[i].dot(tg)).normalized()
        sd = tg.cross(n).normalized()
        if i:
            s_acc += (p - pts[i - 1]).length
        rings.append([p + sd * a + n * b for a, b in prof])
        al += [s_acc] * len(prof)
        ac += [a / w for a, b in prof]
        frames.append((p, tg, n, sd))
    Vv, F, R = loft(rings)
    ob = mesh_part(name, Vv, F, mat, 'Body', 'Gear', along=al, across=ac)
    for k, bi in enumerate(buckle_at):
        p, tg, n, sd = frames[bi]
        Rm = Matrix((sd, tg, n)).transposed()
        box_part(f'{name}_buckle{k}', p + n * (t_out + 0.005), Rm, w + 0.05, 0.10, 0.045, 0.025, 'buckle',
                 'Body', 'Gear', segs=1)
    return ob


def surface_path(guides, centre_fn, offset=0.0):
    """Project guide points onto the shell along rays from outside toward centre_fn(guide)."""
    pts, ns = [], []
    for g in guides:
        g = Vector(g)
        c = centre_fn(g)
        d = (g - c)
        d = d.normalized() if d.length > 1e-6 else Vector((0, 0, 1))
        p, n = hit(c + d * 8.0, -d)
        pts.append(p + n * offset)
        ns.append(n)
    return pts, ns


def buckle_index(pts, dist):
    acc = 0.0
    for i in range(len(pts) - 1, 0, -1):
        acc += (pts[i] - pts[i - 1]).length
        if acc >= dist:
            return i - 1
    return 1


def harness(name, y_top, y_end, x_end_sign_pts=33):
    # from the left rim over the top (under the saddle) to the right rim
    out_pts, out_ns = [], []
    K = x_end_sign_pts
    thetas = np.linspace(-1.0, 1.0, K)
    guides = []
    for t in thetas:
        th = t * math.radians(112)
        y = y_top + (y_end - y_top) * abs(t) ** 1.5
        guides.append(Vector((3.0 * math.sin(th), y, 1.80 + ZOFF + 3.0 * math.cos(th))))
    pts, ns = surface_path(guides, lambda g: Vector((0, g.y, 1.80 + ZOFF)))
    # keep the strap on the carapace: trim where the hit drops below the rim bulge
    keep = [i for i, p in enumerate(pts) if p.z >= Z_RIM - 0.02]
    i0, i1 = keep[0], keep[-1]
    pts, ns = pts[i0:i1 + 1], ns[i0:i1 + 1]
    # both ends finish on the rim bulge and sink straight into the shell (clear of the legs below the lip)
    for end in (0, -1):
        p, n = pts[end], ns[end]
        inward = Vector((-p.x, 0, 0)).normalized() * 0.12
        if end == 0:
            pts.insert(0, p + inward)
            ns.insert(0, n)
        else:
            pts.append(p + inward)
            ns.append(n)
    bi1 = buckle_index(pts, 0.42)
    bi0 = len(pts) - 1 - buckle_index(pts[::-1], 0.42)
    return strap(name, pts, ns, 0.30, 0.06, 0.03, 'strap', buckle_at=(bi0, bi1))


GEAR = {}


def build_gear(carapace):
    global SHELL_BVH
    SHELL_BVH = shell_bvh(carapace)

    # ---------------- speakers (cones face backward, +Y), tilted to follow the rear slope
    hx, hy = 0.60, 0.50
    spk = {}
    for s in (1, -1):
        Rm = (Matrix.Rotation(math.radians(6 * s), 3, 'Y') @ Matrix.Rotation(math.radians(-8), 3, 'X'))
        cxy = Vector((s * 0.67, 0.86, 0.0))
        spk[s] = {'R': Rm, 'cxy': cxy}
    # solve heights: lowest saddle thickness 0.10, speaker tops at 4.20
    hz = 0.66
    for _ in range(6):
        zc = {}
        for s, sp in spk.items():
            need = -1e9
            for gx in np.linspace(-hx, hx, 7):
                for gy in np.linspace(-hy, hy, 7):
                    off = sp['R'] @ Vector((gx, gy, -hz))
                    q = sp['cxy'] + Vector((off.x, off.y, 0))
                    p, n = hit(Vector((q.x, q.y, 9.0)), Vector((0, 0, -1)))
                    need = max(need, p.z + 0.09 - off.z)
            zc[s] = need
        tops = [zc[s] + max((sp['R'] @ Vector((gx, gy, hz))).z for gx in (-hx, hx) for gy in (-hy, hy))
                for s, sp in spk.items()]
        err = 4.20 + ZOFF - max(tops)
        if abs(err) < 0.002:
            break
        hz += err / 2.0
    z_common = max(zc.values())
    for s, sp in spk.items():
        sp['c'] = Vector((sp['cxy'].x, sp['cxy'].y, z_common))
        sp['hz'] = hz
    log('speaker half-height', round(hz, 3), 'centre z', round(z_common, 3))
    GEAR['speakers'] = {s: {'c': list(sp['c']), 'hz': hz} for s, sp in spk.items()}

    for s, sp in spk.items():
        Rm, c = sp['R'], sp['c']
        side = 'L' if s > 0 else 'R'

        box_part(f'Speaker{side}', c, Rm, hx, hy, hz, 0.13, 'gear', 'Body', 'Gear', segs=2)
        back = c + Rm @ Vector((0, hy, 0.0))
        axis = Rm @ Vector((0, 1, 0))
        Xs, Ys, Zs = frame_from(axis, Rm @ Vector((1, 0, 0)))
        # bezel ring, dish, teal dust cap
        torus(f'Speaker{side}_bezel', back + axis * 0.035, axis, 0.46, 0.06, 'gear', 'Body', 'Gear', n=18, m=6)
        rings = [superring(back + axis * r_off, Xs, Zs, r, r, 18, 2.0) for r, r_off in
                 ((0.46, 0.03), (0.34, 0.012), (0.22, 0.01))]
        Vv, F, R = loft(rings, cap0=False, cap1=True)
        mesh_part(f'Speaker{side}_cone', Vv, F, 'cone', 'Body', 'Gear', u=[[0.0, 0.6, 1.0][r] for r in R])
        sphere(f'Speaker{side}_cap', back + axis * 0.02, 0.19, 'teal', 'Body', 'Gear', seg=12, rings=5,
               smooth=False, scale=(1, 1, 1))
        # LED strips on the outer side face, button on top (Glow section)
        for k, zz in enumerate((0.20, -0.20)):
            lc = c + Rm @ Vector((s * (hx - 0.005), 0.16, zz * hz / 0.66))
            box_part(f'LED{side}{k}', lc, Rm, 0.035, 0.08, 0.17 * hz / 0.66, 0.02, 'glow_teal', 'Body', 'Glow',
                     segs=1)
        bc = c + Rm @ Vector((0.0, 0.16, hz - 0.005))
        box_part(f'Button{side}', bc, Rm, 0.15, 0.07, 0.045, 0.025, 'glow_orange', 'Body', 'Glow', segs=1)
        sp['back'] = back

    # ---------------- saddle: rounded-rect pad, underside = shell - 0.04, top = speaker bottom planes
    def top_z(x, y):
        s = 1 if x >= 0 else -1
        sp = spk[s]
        # plane through the speaker's bottom face (0.02 below so the box sits 0.02 into it)
        n = sp['R'] @ Vector((0, 0, 1))
        p0 = sp['c'] + sp['R'] @ Vector((0, 0, -sp['hz'] + 0.02))
        return p0.z - (n.x * (x - p0.x) + n.y * (y - p0.y)) / n.z

    M = 44
    x0, x1, y0, y1, rc = -1.36, 1.36, 0.28, 1.45, 0.24

    def rrect(k, scl):
        # point k of M on a rounded rectangle, scaled about its centre
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        hw, hh = (x1 - x0) / 2, (y1 - y0) / 2
        t = 2 * math.pi * k / M
        ca, sa = math.cos(t), math.sin(t)
        ex = 6.0
        px = math.copysign(abs(ca) ** (2 / ex), ca) * hw
        py = math.copysign(abs(sa) ** (2 / ex), sa) * hh
        return Vector((cx + px * scl, cy + py * scl, 0))

    def ground(q, depth):
        p, n = hit(Vector((q.x, q.y, 9.0)), Vector((0, 0, -1)))
        return p.z - depth
    rings = []
    for scl in (0.25, 0.6, 0.9, 0.97):
        rings.append([Vector((q.x, q.y, top_z(q.x, q.y))) for q in (rrect(k, scl) for k in range(M))])
    rings.append([Vector((q.x, q.y, top_z(q.x, q.y) - 0.05)) for q in (rrect(k, 1.0) for k in range(M))])
    for scl in (1.0, 0.92, 0.55):
        rings.append([Vector((q.x, q.y, ground(q, 0.04 if scl == 1.0 else 0.08))) for q in (rrect(k, scl) for k in range(M))])
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    topc = Vector((cx, cy, top_z(cx + 1e-3, cy)))
    botc = Vector((cx, cy, ground(Vector((cx, cy, 0)), 0.08)))
    Vv, F, R = loft(rings, tip0=topc, tip1=botc)
    # tan padded saddle: darker piping on the top edge, a stitch line just inside it
    across = [(1.0 if r in (3, 4, 5) else (0.0 if r in (-1, 0, 1) else 0.5)) for r in R]
    along = [(i % M) / M * 7.4 for i in range(len(R))]
    mesh_part('Saddle', Vv, F, 'strap', 'Body', 'Gear', across=across, along=along)
    thick = min(top_z(q.x, q.y) - ground(q, 0.0) for q in (rrect(k, s_) for k in range(M) for s_ in (0.6, 0.9, 1.0)))
    GEAR['saddle_min_thickness'] = round(thick, 3)

    # ---------------- harness straps (pass under the saddle, buckles near the rim)
    harness('StrapFront', 0.45, 0.06)
    harness('StrapRear', 1.12, 0.95)

    # ---------------- headphones: ear cups on the upper front sides, band hugging the shell
    cups = {}
    for s in (1, -1):
        side = 'L' if s > 0 else 'R'
        g = Vector((s * 1.55, -0.70, 2.55 + ZOFF))
        c0 = Vector((0, -0.70, 1.9 + ZOFF))
        p, n = hit(c0 + (g - c0).normalized() * 8, -(g - c0).normalized())
        ax = (n + Vector((0, -0.45, 0.05))).normalized()
        Xc, Yc, Zc = frame_from(ax, Vector((0, 0, 1)))
        prof = [(-0.14, 0.42), (0.0, 0.46), (0.24, 0.46), (0.33, 0.40)]
        rings = [superring(p + ax * t, Xc, Zc, r, r, 16, 2.0) for t, r in prof]
        Vv, F, R = loft(rings)
        edge = [1.0 if min(R[i] for i in f) >= 2 and max(R[i] for i in f) == 3 and len(f) == 4 else 0.0 for f in F]
        mesh_part(f'EarCup{side}', Vv, F, 'gear', 'Body', 'Gear', edge=edge)
        torus(f'EarPad{side}', p + ax * 0.32, ax, 0.35, 0.105, 'teal', 'Body', 'Gear', n=16, m=6)
        rings = [superring(p + ax * t, Xc, Zc, r, r, 12, 2.0) for t, r in ((0.28, 0.22), (0.40, 0.22), (0.44, 0.16))]
        Vv, F, R = loft(rings)
        mesh_part(f'EarCap{side}', Vv, F, 'gear', 'Body', 'Gear')
        cups[s] = {'p': p, 'ax': ax}
    GEAR['cups'] = {s: [round(v, 3) for v in c['p']] for s, c in cups.items()}
    # thick charcoal headband arching ~0.6 above the shell top between the cups, in front of the speakers;
    # its ends run into the cups (connected, nothing floats)
    shell_top = max(dome_z(0.0, 0.0), max(p.z for p in (cups[1]['p'], cups[-1]['p'])))
    yb = -0.62
    apex = dome_z(0.0, 0.0) + 0.62
    e0 = {sd: cups[sd]['p'] + cups[sd]['ax'] * 0.10 + Vector((0, 0, 0.22)) for sd in (1, -1)}
    pts, ns = [], []
    K = 27
    for k in range(K):
        u = k / (K - 1)
        th = math.pi * u
        x = -math.cos(th)
        end = e0[-1] if x < 0 else e0[1]
        px = end.x * abs(x)
        pz = end.z + (apex - end.z) * math.sin(th) ** 0.8
        py = end.y + (yb - end.y) * math.sin(th) ** 0.6
        pts.append(Vector((px, py, pz)))
    for k, p in enumerate(pts):
        tg = (pts[min(k + 1, K - 1)] - pts[max(k - 1, 0)]).normalized()
        out = Vector((0, 0, 1)) - tg * tg.z
        ns.append(out.normalized() if out.length > 1e-6 else Vector((0, 0, 1)))
    strap('Headband', pts, ns, 0.34, 0.12, 0.12, 'gear', bev=0.06)
    GEAR['headband_apex_above_shell_top'] = round(apex - dome_z(0.0, 0.0), 3)
    # front harness straps: from under the saddle, forward past the headband to the front rim (read from the front)
    for s in (1, -1):
        a = Vector((s * 0.62, 0.42, 3.0 + ZOFF))
        b = Vector((s * 1.10, -1.62, Z_RIM))
        guides = [a.lerp(b, t) for t in np.linspace(0.0, 1.0, 21)]
        pts, ns = surface_path(guides, lambda g: Vector((g.x * 0.3, g.y * 0.3, 1.6 + ZOFF)))
        keep = [i for i, p in enumerate(pts) if p.z >= Z_RIM - 0.02]
        pts, ns = pts[:keep[-1] + 1], ns[:keep[-1] + 1]
        p, n = pts[-1], ns[-1]
        pts.append(p - Vector((p.x, p.y, 0)).normalized() * 0.12)
        ns.append(n)
        strap(f'FrontStrap{"L" if s > 0 else "R"}', pts, ns, 0.24, 0.055, 0.03, 'strap',
              buckle_at=(buckle_index(pts, 0.40),))
    # chin straps: from under each cup down to the rim, buckle near the rim
    for s in (1, -1):
        side = 'L' if s > 0 else 'R'
        a = cups[s]['p']
        b = Vector((s * 2.02, -0.86, Z_RIM - 0.05))
        guides = [a.lerp(b, t) for t in np.linspace(0.0, 1.0, 13)]
        pts, ns = surface_path(guides, lambda g: Vector((0, g.y, 1.80 + ZOFF)))
        keep = [i for i, p in enumerate(pts) if p.z >= Z_RIM - 0.02]
        pts, ns = pts[:keep[-1] + 1], ns[:keep[-1] + 1]
        p, n = pts[-1], ns[-1]
        pts.append(p + Vector((-p.x, 0, 0)).normalized() * 0.12)
        ns.append(n)
        strap(f'ChinStrap{side}', pts, ns, 0.22, 0.055, 0.03, 'strap', buckle_at=(buckle_index(pts, 0.36),))


# ================================================================= build
log('building geometry')
carapace = build_carapace()
build_mouth()
for s in (1, -1):
    build_eyes(s)
for s in (1, -1):
    for i in (1, 2, 3, 4):
        build_leg(s, i)
for s in (1, -1):
    build_claw(s)
build_gear(carapace)
log('parts', len(PARTS))


def build_armature():
    arm = bpy.data.armatures.new(f'{NAME}_Rig')
    rig = bpy.data.objects.new(f'{NAME}_Rig', arm)
    COLL.objects.link(rig)
    activate(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    for name, b in BONES.items():
        eb = arm.edit_bones.new(name)
        eb.head, eb.tail = b['head'], b['tail']
        eb.align_roll(b['z'])
        eb.use_deform = True
        if b['parent']:
            eb.parent = arm.edit_bones[b['parent']]
            eb.use_connect = False
    bpy.ops.object.mode_set(mode='OBJECT')
    # verify the hinge axes landed on local X
    worst = 0.0
    for b in arm.bones:
        x = b.matrix_local.to_3x3().col[0]
        worst = max(worst, (x - BONES[b.name]['x']).length)
    log('bone X-axis max error', round(worst, 6))
    assert worst < 1e-3, 'bone roll did not reproduce the hinge axes'
    return rig


rig = build_armature()

# ================================================================= renders
REVIEW = bpy.data.collections.new('REVIEW_ONLY')
COLL.children.link(REVIEW)


def review(ob):
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    REVIEW.objects.link(ob)
    return ob


bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
ground = review(bpy.context.object)
ground.name = 'ReviewGround'
gm = bpy.data.materials.new('ReviewGround')
if hasattr(gm, 'use_nodes') and not gm.node_tree:
    gm.use_nodes = True
gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*lin((168, 166, 166)), 1)
gm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 1.0
gm.diffuse_color = (*lin((168, 166, 166)), 1)
ground.data.materials.append(gm)
world = bpy.data.worlds.new('ReviewWorld')
scene.world = world
if hasattr(world, 'use_nodes') and not world.node_tree:
    world.use_nodes = True
bg = world.node_tree.nodes['Background']
# approximates the game light: light-blue sky fill plus a warm sun
bg.inputs[0].default_value = (0.55, 0.70, 0.95, 1)
bg.inputs[1].default_value = 0.65
sun_d = bpy.data.lights.new('ReviewSun', 'SUN')
sun_d.color = (1.0, 0.90, 0.76)
sun_d.energy = 3.6
sun_d.angle = math.radians(14)
sun = review(bpy.data.objects.new('ReviewSun', sun_d))
sun.rotation_euler = (math.radians(42), 0, math.radians(-28))
cam_d = bpy.data.cameras.new('ReviewCam')
cam = bpy.data.objects.new('ReviewCam', cam_d)
REVIEW.objects.link(cam)
scene.camera = cam
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'


def aim(loc, tgt, lens=50):
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam_d.lens = lens


def render(path, w=1024, h=768, engine='EEVEE'):
    if engine == 'EEVEE':
        for eid in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
            try:
                scene.render.engine = eid
                break
            except TypeError:
                continue
        try:
            scene.eevee.taa_render_samples = 32
        except Exception:
            pass
    else:
        scene.render.engine = 'BLENDER_WORKBENCH'
        sh = scene.display.shading
        sh.light = 'STUDIO'
        sh.color_type = 'MATERIAL'
        sh.show_shadows = True
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    if hasattr(scene.render.image_settings, 'media_type'):
        scene.render.image_settings.media_type = 'IMAGE'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


TGT = Vector((0, -0.6, 1.6))
VIEWS = {
    'Front': ((0.0, -15.5, 3.6), TGT),
    'Back': ((0.0, 15.5, 4.2), Vector((0, -0.2, 2.0))),
    'Side': ((-15.5, -0.4, 3.0), Vector((0, -0.4, 1.9))),
    'ThreeQuarter': ((-10.5, -11.5, 5.4), TGT),
}

# ---------------------------------------------------- join, unwrap, bake, split
bpy.context.view_layer.update()
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects:
    if ob.name in bpy.context.view_layer.objects:
        ob.select_set(False)
objs = [p['obj'] for p in PARTS]
for ob in objs:
    ob.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.join()
allob = bpy.context.view_layer.objects.active
allob.name = f'{NAME}_All'
log('joined', len(allob.data.vertices), 'verts', sum(len(p.vertices) - 2 for p in allob.data.polygons), 'tris')

if QUICK:
    import sys
    for k, (loc, tgt) in VIEWS.items():
        aim(loc, tgt, 50)
        render(OUT / '_work' / f'quick_{k}.png', 800, 600, engine='WORKBENCH')
    co = np.empty(len(allob.data.vertices) * 3, np.float32)
    allob.data.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    log('quick dims', 'top', float(co[:, 2].max()), 'x', float(co[:, 0].min()), float(co[:, 0].max()),
        'y', float(co[:, 1].min()), float(co[:, 1].max()), 'footprint', float(np.sqrt((co[:, :2] ** 2).sum(1)).max()))
    log('quick GEAR', json.dumps({k: (v if not isinstance(v, dict) else str(v)) for k, v in GEAR.items()}))
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / '_work' / 'DJCrab_quick.blend'))
    log('QUICK_DONE')
    sys.exit(0)

activate(allob)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(50), island_margin=0.004, area_weight=0.0, correct_aspect=True,
                         scale_to_bounds=False)
bpy.ops.uv.pack_islands(margin=0.006, rotate=True)
bpy.ops.object.mode_set(mode='OBJECT')
allob.data.uv_layers.active.name = 'UVMap'
log('unwrapped')

ATLAS_2048 = OUT / 'textures' / f'{NAME}_Atlas_BaseColor_{MASTER_RES}.png'
ATLAS_1024 = OUT / 'textures' / f'{NAME}_Atlas_BaseColor_{DELIVERY_RES}.png'


def set_gpu():
    scene.render.engine = 'CYCLES'
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        for kind in ('OPTIX', 'CUDA'):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
                if any(d.type == kind for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = d.type == kind
                    scene.cycles.device = 'GPU'
                    return kind
            except Exception:
                continue
    except Exception:
        pass
    scene.cycles.device = 'CPU'
    return 'CPU'


if not QUICK:
    log('cycles device', set_gpu())
    scene.cycles.samples = 6
    img = bpy.data.images.new(f'{NAME}_Atlas_BaseColor', MASTER_RES, MASTER_RES, alpha=False)
    img.colorspace_settings.name = 'sRGB'
    for m in allob.data.materials:
        nt = m.node_tree
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.name = 'BakeTarget'
        tex.image = img
        nt.nodes.active = tex
        nt.links.new(nt.nodes['BakeEmit'].outputs[0], nt.nodes['Output'].inputs['Surface'])
    activate(allob)
    scene.render.bake.margin = 10
    scene.render.bake.margin_type = 'EXTEND'
    scene.render.bake.use_clear = True
    scene.render.bake.target = 'IMAGE_TEXTURES'
    bpy.ops.object.bake(type='EMIT')
    img.filepath_raw = str(ATLAS_2048)
    img.file_format = 'PNG'
    img.save()
    small = img.copy()
    small.scale(DELIVERY_RES, DELIVERY_RES)
    small.filepath_raw = str(ATLAS_1024)
    small.file_format = 'PNG'
    small.save()
    bpy.data.images.remove(small)
    bpy.data.images.remove(img)
    log('baked atlas')

delivery = bpy.data.images.load(str(ATLAS_1024)) if ATLAS_1024.exists() else None
if delivery:
    delivery.name = f'{NAME}_Atlas_BaseColor_{DELIVERY_RES}'
    delivery.pack()


def final_material(sec):
    m = bpy.data.materials.new(f'{NAME}_{sec}')
    if hasattr(m, 'use_nodes') and not m.node_tree:
        m.use_nodes = True
    nt = m.node_tree
    bs = nt.nodes.get('Principled BSDF')
    bs.inputs['Roughness'].default_value = 0.3 if sec == 'Eyes' else 0.85
    for key in ('Specular IOR Level', 'Specular'):
        if key in bs.inputs:
            bs.inputs[key].default_value = 0.15
    if delivery:
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.name = 'BaseColor'
        tex.image = delivery
        nt.links.new(tex.outputs['Color'], bs.inputs['Base Color'])
    return m


paint_index = {}
me = allob.data
sec_attr = np.empty(len(me.polygons), np.int32)
me.attributes['section'].data.foreach_get('value', sec_attr)
old_idx = np.empty(len(me.polygons), np.int32)
me.polygons.foreach_get('material_index', old_idx)
old_mats = [m.name for m in me.materials]
finals = [final_material(sec) for sec in SECTIONS]
me.materials.clear()
for m in finals:
    me.materials.append(m)
me.polygons.foreach_set('material_index', sec_attr)
me.update()
activate(allob)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.separate(type='MATERIAL')
bpy.ops.object.mode_set(mode='OBJECT')
SECS = {}
for ob in [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith(f'{NAME}_All')]:
    mats = [m for m in ob.data.materials if m]
    used = {p.material_index for p in ob.data.polygons}
    if not ob.data.polygons:
        bpy.data.objects.remove(ob)
        continue
    mi = used.pop()
    sec = ob.data.materials[mi].name.replace(f'{NAME}_', '')
    ob.data.materials.clear()
    ob.data.materials.append(bpy.data.materials[f'{NAME}_{sec}'])
    for p in ob.data.polygons:
        p.material_index = 0
    ob.name = ob.data.name = f'{NAME}_{sec}'
    # drop empty vertex groups
    counts = {g.index: 0 for g in ob.vertex_groups}
    for v in ob.data.vertices:
        for g in v.groups:
            if g.weight > 0:
                counts[g.group] += 1
    empty = [g.name for g in ob.vertex_groups if counts[g.index] == 0]
    for nm in empty:
        ob.vertex_groups.remove(ob.vertex_groups[nm])
    assert all(v.groups for v in ob.data.vertices), f'unweighted vertices in {ob.name}'
    md = ob.modifiers.new('Armature', 'ARMATURE')
    md.object = rig
    ob.parent = rig
    SECS[sec] = ob
log('sections', sorted(SECS))
assert set(SECS) == set(SECTIONS), SECS.keys()


# ================================================================= measure
def world_verts(ob):
    co = np.empty(len(ob.data.vertices) * 3, np.float32)
    ob.data.vertices.foreach_get('co', co)
    return co.reshape(-1, 3)


allv = np.concatenate([world_verts(o) for o in SECS.values()])
shellv = world_verts(SECS['Shell'])
dims = {
    'height': round(float(allv[:, 2].max()), 4),
    'lowest': round(float(allv[:, 2].min()), 4),
    'overall_x': [round(float(allv[:, 0].min()), 4), round(float(allv[:, 0].max()), 4)],
    'overall_y': [round(float(allv[:, 1].min()), 4), round(float(allv[:, 1].max()), 4)],
    'footprint_radius': round(float(np.sqrt((allv[:, :2] ** 2).sum(1)).max()), 4),
    'shell_width': round(float(shellv[:, 0].max() - shellv[:, 0].min()), 4),
    'shell_length': round(float(shellv[:, 1].max() - shellv[:, 1].min()), 4),
    'shell_top': round(float(shellv[:, 2].max()), 4),
    'regular_crab_shell_width': 2.738,
    'speaker_top': round(float(world_verts(SECS['Gear'])[:, 2].max()), 4),
    'body_centre_height': BODY_C.z,
}
dims['shell_width_ratio_vs_regular_crab'] = round(dims['shell_width'] / 2.738, 3)
log('dims', json.dumps(dims))
tris = {sec: sum(len(p.vertices) - 2 for p in ob.data.polygons) for sec, ob in SECS.items()}
log('tris', tris, 'total', sum(tris.values()))

for k, (loc, tgt) in VIEWS.items():
    aim(loc, tgt, 50)
    render(OUT / 'previews' / f'{k}.png')
log('rest renders done')

# ================================================================= save + manifest
aim(*VIEWS['ThreeQuarter'], 50)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'DJCrab.blend'))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper() if Path(p).exists() else None


manifest = {
    'asset': 'DJ Crab (Beach Cove round-10 leader, CRAB RAVE)', 'boss_id': 'dj-crab',
    'units': '1 Blender unit = 1 stud', 'axes': 'faces -Y, +Z up, crab left = +X; Studio = (-X, Z, Y)',
    'reference': {'path': str(REF.relative_to(OUT.parent)).replace('\\', '/'), 'sha256': sha(REF)},
    'dimensions': dims,
    'sections': {sec: {'triangles': tris[sec], 'vertices': len(SECS[sec].data.vertices),
                       'material': f'{NAME}_{sec}'} for sec in SECTIONS},
    'total_triangles': sum(tris.values()),
    'shading': {'Eyes': 'smooth'},
    'bones': [{'name': b.name, 'parent': b.parent.name if b.parent else None, 'deform': b.use_deform,
               'head': [round(v, 4) for v in b.head_local], 'tail': [round(v, 4) for v in b.tail_local]}
              for b in rig.data.bones],
    'gear': GEAR,
    'textures': {p.name: sha(p) for p in (ATLAS_2048, ATLAS_1024) if p.exists()},
    'legs': {t: {k: [round(x, 4) for x in v] for k, v in d.items()} for t, d in LEG_INFO.items()},
    'claws': {t: {k: ([round(x, 4) for x in v] if hasattr(v, '__len__') else v) for k, v in d.items()} for t, d in CLAW_INFO.items()},
    'eyes': {t: {k: [round(x, 4) for x in v] for k, v in d.items()} for t, d in EYE_INFO.items()},
    'rest_gape_deg': GAPE_REST,
    'claw_tip_f': 2.29, 'claw_tip_up': 0.07, 'claw_palm_centre': [0.0, 0.62, 0.05], 'zoff': ZOFF,
}
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=1))
log('BUILD_COMPLETE', json.dumps({'tris': tris, 'total': sum(tris.values())}))
