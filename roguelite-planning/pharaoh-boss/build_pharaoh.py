"""Pharaoh boss (Desert Basin): faithful rebuild of the supplied reference.

Run headless with Blender 5.2:
    blender -b --factory-startup --python build_pharaoh.py -- [flags]

Environment / flags
    STAGE=sculpt   build geometry with preview materials and render only the
                   reference-match frame (fast iteration loop)
    STAGE=full     (default) sculpt, bake textures, rig, skin, actions, renders,
                   exports and the packed .blend
    PROBE_ONLY=1   with STAGE=full: stop after the Reference_Match render
    SAMPLES=n      Cycles samples for review renders

Self-contained on purpose: nothing here imports or exec()s a sibling kit.

Conventions
    1 Blender unit = 1 Roblox stud. The character faces -Y, Z is up, +X is the
    character's LEFT (viewer-right in the front view). The reference camera is
    the one solved by camera_solve.py (source/camera_solve.json).

    Almost every visible outline is TRACED from the reference in pixel space and
    unprojected through that solved camera onto a chosen depth plane
    (`W(u, v, y)`), so the silhouette matches by construction and the depth
    choices keep the 3D model plausible from every other angle.
"""
import bpy, bmesh, math, json, os, sys, random, time, hashlib, zlib
import numpy as np
from pathlib import Path
from mathutils import Vector, Matrix, Quaternion, Euler
from mathutils.bvhtree import BVHTree

T0 = time.time()
HERE = Path(__file__).resolve().parent
STAGE = os.environ.get('STAGE', 'full')
PROBE_ONLY = os.environ.get('PROBE_ONLY') == '1'
SAMPLES = int(os.environ.get('SAMPLES', '48'))
WORK = HERE / '_work'
for d in ('textures', 'previews', 'exports/fbx', 'exports/glb', '_work'):
    (HERE / d).mkdir(parents=True, exist_ok=True)
random.seed(20260928)
NAME = 'Pharaoh'


def log(*a):
    print(f'[{time.time() - T0:7.1f}s]', *a, flush=True)


# ----------------------------------------------------------------- camera
CAM = json.loads((HERE / 'source' / 'camera_solve.json').read_text())
IMG_W, IMG_H = CAM['image']
FPX = CAM['focal_px']
PITCH = math.radians(CAM['pitch_up_deg'])
CAM_LOC = Vector(CAM['camera_location'])
PP = Vector(CAM['principal_point'])
CF = Vector((0, math.cos(PITCH), math.sin(PITCH)))      # forward
CU = Vector((0, -math.sin(PITCH), math.cos(PITCH)))     # up
CR = Vector((1, 0, 0))                                 # right


def W(u, v, y):
    """World point on the plane Y = y that the reference pixel (u, v) sees."""
    d = CF + CR * ((u - PP.x) / FPX) - CU * ((v - PP.y) / FPX)
    t = (y - CAM_LOC.y) / d.y
    return CAM_LOC + d * t


def WR(u, v):
    """Unit ray direction through pixel (u, v)."""
    return (CF + CR * ((u - PP.x) / FPX) - CU * ((v - PP.y) / FPX)).normalized()


def P2(p):
    """Project a world point to reference pixels (u, v)."""
    d = Vector(p) - CAM_LOC
    zc = d.dot(CF)
    return (PP.x + FPX * d.dot(CR) / zc, PP.y - FPX * d.dot(CU) / zc)


def pxs(y):
    """Approximate pixels per stud on the depth plane y."""
    return FPX / ((y - CAM_LOC.y) * math.cos(PITCH))


# ----------------------------------------------------------------- scene reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'NONE'
PARTS = []          # dicts: obj, section, weight rule, material key


def link(o, coll=None):
    (coll or scene.collection).objects.link(o)
    return o


def activate(o):
    for s in bpy.context.selected_objects:
        s.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def mesh_obj(name, verts, faces, mat=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate(clean_customdata=False)
    me.update()
    o = bpy.data.objects.new(name, me)
    link(o)
    if mat is not None:
        o.data.materials.append(mat)
    for p in o.data.polygons:
        p.use_smooth = smooth
    return o


def recalc_normals(o, inside=False):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if inside:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(o.data)
    bm.free()


def apply_mods(o):
    activate(o)
    for m in list(o.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=m.name)
        except Exception as e:
            log('modifier apply failed', o.name, m.name, e)
            o.modifiers.remove(m)


def bevel(o, width, segments=1, angle=35.0, mat_index=None, harden=False, clamp=True):
    md = o.modifiers.new('bevel', 'BEVEL')
    md.width = width
    md.segments = segments
    md.limit_method = 'ANGLE'
    md.angle_limit = math.radians(angle)
    md.use_clamp_overlap = clamp
    md.harden_normals = False
    if mat_index is not None:
        md.material = mat_index
    apply_mods(o)
    return o


def flat(o):
    for p in o.data.polygons:
        p.use_smooth = False


def part(o, section, weight, mat_key=None, **kw):
    """Register a finished piece. weight: ('skin',) | ('rigid', bone) |
    ('transfer',) | ('chain', [bones], axis_points) | ('kilt', ...)"""
    d = dict(obj=o, section=section, weight=weight, mat=mat_key)
    d.update(kw)
    PARTS.append(d)
    return o


def chamfer_box(name, center, size, mat, bevel_w=0.08, segments=1, rot=None,
                taper=None, angle=30.0, edge_mat_index=None):
    """Beveled box. `rot` is a Matrix/Euler/Quaternion; `taper` = (sx, sy) scale
    applied to the top (+Z local) face for frustum shapes."""
    sx, sy, sz = size
    v = [Vector((x * sx / 2, y * sy / 2, z * sz / 2)) for z in (-1, 1) for y in (-1, 1)
         for x in (-1, 1)]
    if taper:
        for p in v[4:]:
            p.x *= taper[0]
            p.y *= taper[1]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    o = mesh_obj(name, v, f, mat)
    recalc_normals(o)
    if bevel_w > 0:
        bevel(o, bevel_w, segments, angle, edge_mat_index)
    M = Matrix.Identity(4)
    if rot is not None:
        M = (rot.to_matrix() if hasattr(rot, 'to_matrix') else rot).to_4x4()
    o.data.transform(Matrix.Translation(Vector(center)) @ M)
    flat(o)
    return o


def basis_from(x_axis, up_hint=Vector((0, 0, 1))):
    """Rotation matrix whose local X points along x_axis, Z roughly up_hint."""
    x = Vector(x_axis).normalized()
    z = Vector(up_hint) - x * x.dot(up_hint)
    if z.length < 1e-6:
        z = Vector((0, 1, 0)) - x * x.y
    z.normalize()
    y = z.cross(x)
    return Matrix((x, y, z)).transposed()


def extrude_poly(name, pts3, normal_dir, thickness, mat, bevel_w=0.0, segments=1,
                 angle=30.0, bulge=0.0):
    """Extrude a closed planar-ish 3D outline by `thickness` along -normal_dir
    (away from the viewer). bulge pushes the front cap's interior outward."""
    n = len(pts3)
    nd = Vector(normal_dir).normalized()
    front = [Vector(p) for p in pts3]
    back = [p - nd * thickness for p in front]
    verts = front + back
    faces = []
    bm = bmesh.new()
    vf = [bm.verts.new(p) for p in front]
    vb = [bm.verts.new(p) for p in back]
    bm.faces.new(vf)
    bm.faces.new(list(reversed(vb)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((vf[i], vb[i], vb[j], vf[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # triangulate caps robustly for concave outlines
    caps = [f for f in bm.faces if len(f.verts) > 4]
    if caps:
        bmesh.ops.triangulate(bm, faces=caps, quad_method='BEAUTY', ngon_method='EAR_CLIP')
    if bulge:
        c = sum(front, Vector()) / n
        for v in vf:
            pass
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    link(o)
    o.data.materials.append(mat)
    if bevel_w > 0:
        bevel(o, bevel_w, segments, angle)
    flat(o)
    return o


def uv_outline(pts_uv, depth, normal=None):
    """Trace in reference pixels -> 3D points on the plane Y=depth (or a tilted
    plane through the first point with the given normal)."""
    if normal is None:
        return [W(u, v, depth) for u, v in pts_uv]
    n = Vector(normal).normalized()
    p0 = W(pts_uv[0][0], pts_uv[0][1], depth)
    out = []
    for u, v in pts_uv:
        d = WR(u, v)
        t = (p0 - CAM_LOC).dot(n) / d.dot(n)
        out.append(CAM_LOC + d * t)
    return out


def loft(name, rings, mat, closed=True, cap_start=True, cap_end=True):
    """Rings: list of equal-length lists of 3D points."""
    k = len(rings[0])
    verts = [p for r in rings for p in r]
    faces = []
    for i in range(len(rings) - 1):
        for j in range(k if closed else k - 1):
            a = i * k + j
            b = i * k + (j + 1) % k
            faces.append((a, b, b + k, a + k))
    if closed and cap_start:
        faces.append(tuple(reversed(range(k))))
    if closed and cap_end:
        faces.append(tuple((len(rings) - 1) * k + j for j in range(k)))
    o = mesh_obj(name, verts, faces, mat)
    recalc_normals(o)
    return o


def ring_pts(center, axis, radius, sides, phase=0.0, ref=None, scale=(1.0, 1.0),
             jitter=0.0, rnd=None):
    ax = Vector(axis).normalized()
    ref = Vector(ref) if ref is not None else (Vector((0, 0, 1)) if abs(ax.z) < 0.9
                                               else Vector((0, -1, 0)))
    u = (ref - ax * ax.dot(ref)).normalized()
    w = ax.cross(u)
    pts = []
    for i in range(sides):
        a = phase + i * 2 * math.pi / sides
        r = radius * (1 + (rnd.uniform(-jitter, jitter) if rnd else 0))
        pts.append(Vector(center) + u * (math.cos(a) * r * scale[0]) + w * (math.sin(a) * r * scale[1]))
    return pts


# ================================================================= materials
def srgb(*c):
    def lin(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return tuple(lin(v) for v in c)


# Per-channel gains, measured: reference linear mean / render linear mean per
# material region (compare_reference.py prints them). Multiply the printed
# scales in and rebuild; the eyedropped constants below stay readable.
CALIBRATION = {   # pass-2 gains measured from the baked Reference_Match
    'skin':    (0.944, 0.925, 0.935),
    'bone':    (0.998, 1.109, 1.182),
    'bandage': (0.937, 0.994, 1.056),
    'gold':    (0.949, 1.040, 0.801),
    'blue':    (0.690, 0.935, 1.063),
    'brown':   (1.022, 1.228, 1.193),
    'gem':     (0.476, 1.115, 1.515),
    'slate':   (0.850, 0.945, 1.000),
}


def cal(key, *c):
    g = CALIBRATION.get(key, (1, 1, 1))
    return tuple(min(1.0, v * k) for v, k in zip(srgb(*c), g))


class NT:
    """Tiny node-tree builder for the procedural painterly materials."""

    def __init__(self, mat):
        self.m = mat
        self.nt = mat.node_tree
        self.n = self.nt.nodes
        self.l = self.nt.links

    def node(self, t, **props):
        nd = self.n.new(t)
        for k, v in props.items():
            setattr(nd, k, v)
        return nd

    def link(self, a, b):
        self.l.new(a, b)

    def math(self, op, a, b=None, c=None, clamp=False):
        nd = self.node('ShaderNodeMath', operation=op)
        nd.use_clamp = clamp
        for i, x in enumerate((a, b, c)):
            if x is None:
                continue
            if hasattr(x, 'node'):
                self.link(x, nd.inputs[i])
            else:
                nd.inputs[i].default_value = x
        return nd.outputs[0]

    def maprange(self, x, a, b, c=0.0, d=1.0, interp='LINEAR'):
        nd = self.node('ShaderNodeMapRange', clamp=True, interpolation_type=interp)
        self.link(x, nd.inputs['Value'])
        nd.inputs['From Min'].default_value = a
        nd.inputs['From Max'].default_value = b
        nd.inputs['To Min'].default_value = c
        nd.inputs['To Max'].default_value = d
        return nd.outputs['Result']

    def mix(self, fac, a, b, blend='MIX'):
        nd = self.node('ShaderNodeMix', data_type='RGBA', blend_type=blend)
        nd.clamp_result = True
        socks = [s for s in nd.inputs if s.type == 'RGBA']
        facs = [s for s in nd.inputs if s.name == 'Factor' and s.type == 'VALUE']
        if hasattr(fac, 'node'):
            self.link(fac, facs[0])
        else:
            facs[0].default_value = fac
        for s, x in zip(socks[:2], (a, b)):
            if hasattr(x, 'node'):
                self.link(x, s)
            else:
                s.default_value = (*x, 1.0)
        return [s for s in nd.outputs if s.type == 'RGBA'][0]

    def scale_col(self, col, fac):
        """col * fac (fac a scalar socket)."""
        cmb = self.node('ShaderNodeCombineColor')
        for i in range(3):
            self.link(fac, cmb.inputs[i])
        return self.mix(1.0, col, cmb.outputs[0], 'MULTIPLY')

    def noise(self, vec, scale, detail=2.0, rough=0.5, w=0.0, out='Fac'):
        nd = self.node('ShaderNodeTexNoise', noise_dimensions='4D')
        nd.inputs['Scale'].default_value = scale
        nd.inputs['Detail'].default_value = detail
        nd.inputs['Roughness'].default_value = rough
        nd.inputs['W'].default_value = w
        self.link(vec, nd.inputs['Vector'])
        return nd.outputs[out]

    def ramp(self, fac, stops, interp='LINEAR'):
        nd = self.node('ShaderNodeValToRGB')
        cr = nd.color_ramp
        cr.interpolation = interp
        while len(cr.elements) > 1:
            cr.elements.remove(cr.elements[-1])
        for i, (pos, col) in enumerate(stops):
            e = cr.elements[0] if i == 0 else cr.elements.new(pos)
            e.position = pos
            e.color = (*col, 1.0) if len(col) == 3 else col
        self.link(fac, nd.inputs['Fac'])
        return nd.outputs['Color']

    def geo(self, out):
        return self.node('ShaderNodeNewGeometry').outputs[out]

    def attr(self, name, out='Fac'):
        return self.node('ShaderNodeAttribute', attribute_name=name).outputs[out]

    def vmath(self, op, a, b=None, scale=None):
        nd = self.node('ShaderNodeVectorMath', operation=op)
        self.link(a, nd.inputs[0])
        if b is not None:
            if hasattr(b, 'node'):
                self.link(b, nd.inputs[1])
            else:
                nd.inputs[1].default_value = b
        if scale is not None:
            nd.inputs['Scale'].default_value = scale
        if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE'):
            return nd.outputs['Value']
        return nd.outputs['Vector']

    def sep(self, vec, comp='Z'):
        nd = self.node('ShaderNodeSeparateXYZ')
        self.link(vec, nd.inputs[0])
        return nd.outputs[comp]


MATS = {}


def new_mat(key):
    m = bpy.data.materials.new(f'{NAME}_{key}')
    m.use_nodes = True
    m.node_tree.nodes.clear()
    return m


def finish_mat(m, nt, color, rough=0.9, spec=0.25, emit=None, emit_strength=0.0):
    out = nt.node('ShaderNodeOutputMaterial')
    bs = nt.node('ShaderNodeBsdfPrincipled')
    bs.name = 'BSDF'
    nt.link(color, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = rough
    if 'Specular IOR Level' in bs.inputs:
        bs.inputs['Specular IOR Level'].default_value = spec
    if emit is not None:
        nt.link(emit, bs.inputs['Emission Color'])
        bs.inputs['Emission Strength'].default_value = emit_strength
    nt.link(bs.outputs['BSDF'], out.inputs['Surface'])
    # dormant emission node carrying the same colour, wired in only for bakes
    em = nt.node('ShaderNodeEmission')
    em.name = 'BAKE_EMIT'
    nt.link(color, em.inputs['Color'])
    return m


def edge_mask(nt, radius=0.04, lo=0.015, hi=0.20):
    """Convex-edge mask from the Bevel node (rounded normal vs true normal)."""
    bv = nt.node('ShaderNodeBevel', samples=8)
    bv.inputs['Radius'].default_value = radius
    dot = nt.vmath('DOT_PRODUCT', bv.outputs['Normal'], nt.geo('Normal'))
    inv = nt.math('SUBTRACT', 1.0, dot)
    # only convex edges: pointiness > 0.5 means convex
    pt = nt.maprange(nt.geo('Pointiness'), 0.50, 0.56)
    return nt.math('MULTIPLY', nt.maprange(inv, lo, hi), pt)


def cavity_mask(nt, dist=0.22, lo=0.45, hi=1.0):
    ao = nt.node('ShaderNodeAmbientOcclusion', samples=12, only_local=True)
    ao.inputs['Distance'].default_value = dist
    return nt.maprange(ao.outputs['AO'], lo, hi)     # 0 = occluded, 1 = open


def painterly(key, base, dark, light, *, patch_scale=0.9, speck=None, speck_col=None,
              edge_col=None, edge_amt=0.55, cav_col=None, cav_amt=0.6, facet_amt=0.12,
              rough=0.88, spec=0.25, streak=None, extra=None, emit=None, emit_strength=0.0):
    """Shared painterly recipe: broad value patches (three soft values), per-facet
    tone jitter, lighter convex edges, softly darkened cavities, sparse flecks.
    Noise runs in world space so its density is constant in studs."""
    m = new_mat(key)
    nt = NT(m)
    pos = nt.geo('Position')
    warp = nt.noise(pos, patch_scale * 1.7, 2.0, 0.5, 3.1, out='Color')
    p2 = nt.vmath('ADD', pos, nt.vmath('SCALE', warp, scale=0.35))
    n1 = nt.noise(p2, patch_scale, 3.0, 0.55, 1.3)
    col = nt.ramp(n1, [(0.32, dark), (0.50, base), (0.70, light)], 'EASE')
    fr = nt.attr('facet_rand')
    col = nt.scale_col(col, nt.math('MULTIPLY_ADD', fr, facet_amt * 2, 1.0 - facet_amt))
    if streak is not None:
        # lengthwise weave streaks along a local attribute direction
        st = nt.noise(nt.vmath('MULTIPLY', pos, streak), 4.0, 2.0, 0.5, 7.7)
        col = nt.mix(nt.maprange(st, 0.50, 0.78, 0.0, 0.30), col, dark)
    if cav_col is not None:
        inv = nt.math('SUBTRACT', 1.0, cavity_mask(nt))
        col = nt.mix(nt.math('MULTIPLY', inv, cav_amt), col, cav_col)
    if edge_col is not None:
        col = nt.mix(nt.math('MULTIPLY', edge_mask(nt), edge_amt), col, edge_col)
    if speck is not None:
        sp = nt.noise(nt.vmath('ADD', pos, nt.vmath('SCALE', warp, scale=0.08)), speck, 2.0, 0.5, 5.3)
        col = nt.mix(nt.maprange(sp, 0.71, 0.77, 0.0, 0.8), col, speck_col or dark)
    if extra is not None:
        col = extra(nt, col, pos)
    finish_mat(m, nt, col, rough, spec, emit, emit_strength)
    MATS[key] = m
    return m


def flat_mat(key, color, rough=0.9, emit=0.0):
    m = new_mat(key)
    nt = NT(m)
    rgb = nt.node('ShaderNodeRGB')
    rgb.outputs[0].default_value = (*color, 1)
    if emit:
        finish_mat(m, nt, rgb.outputs[0], rough, 0.2, emit=rgb.outputs[0], emit_strength=emit)
    else:
        finish_mat(m, nt, rgb.outputs[0], rough, 0.2)
    MATS[key] = m
    return m


def strip_edges(nt, col, pos):
    """Soft darker line along both edges of every bandage strip (strip_v is
    the across-strip coordinate written by ribbon(); 0 elsewhere)."""
    sv = nt.math('ABSOLUTE', nt.attr('strip_v'))
    k = nt.maprange(sv, 0.72, 1.0, 0.0, 0.55)
    return nt.mix(k, col, cal('bandage', 150, 136, 118))


def build_materials():
    painterly('skin', cal('skin', 142, 142, 110), cal('skin', 108, 110, 82),
              cal('skin', 168, 168, 134), patch_scale=0.85, speck=9.0,
              speck_col=cal('skin', 70, 70, 52), edge_col=cal('skin', 190, 188, 156),
              edge_amt=0.45, cav_col=cal('skin', 60, 62, 48), cav_amt=0.55, facet_amt=0.10)
    painterly('bone', cal('bone', 156, 151, 125), cal('bone', 124, 120, 98),
              cal('bone', 194, 187, 158), patch_scale=1.6, speck=11.0,
              speck_col=cal('bone', 96, 86, 62), edge_col=cal('bone', 226, 214, 178),
              edge_amt=0.55, cav_col=cal('bone', 70, 62, 42), cav_amt=0.65, facet_amt=0.08)
    painterly('teeth', cal('bone', 226, 206, 166), cal('bone', 196, 176, 138),
              cal('bone', 240, 226, 190), patch_scale=3.0, edge_col=cal('bone', 246, 236, 206),
              edge_amt=0.5, cav_col=cal('bone', 110, 90, 60), cav_amt=0.5, facet_amt=0.05)
    painterly('bandage', cal('bandage', 226, 206, 170), cal('bandage', 198, 180, 150),
              cal('bandage', 242, 228, 198), patch_scale=1.3, speck=14.0,
              speck_col=cal('bandage', 132, 116, 96), edge_col=cal('bandage', 248, 238, 214),
              edge_amt=0.35, cav_col=cal('bandage', 132, 124, 116), cav_amt=0.55, facet_amt=0.025,
              streak=(1.0, 1.0, 1.0), extra=strip_edges)
    painterly('gold', cal('gold', 214, 158, 64), cal('gold', 176, 122, 44),
              cal('gold', 236, 186, 88), patch_scale=1.2, speck=12.0,
              speck_col=cal('gold', 140, 96, 36), edge_col=cal('gold', 252, 214, 120),
              edge_amt=0.75, cav_col=cal('gold', 110, 70, 26), cav_amt=0.6, facet_amt=0.07,
              rough=0.62, spec=0.45)
    painterly('blue', cal('blue', 66, 82, 138), cal('blue', 52, 66, 114),
              cal('blue', 84, 100, 160), patch_scale=1.1, speck=12.0,
              speck_col=cal('blue', 40, 50, 86), edge_col=cal('blue', 104, 120, 176),
              edge_amt=0.5, cav_col=cal('blue', 28, 36, 64), cav_amt=0.55, facet_amt=0.07)
    painterly('slate', cal('slate', 104, 112, 122), cal('slate', 86, 94, 104),
              cal('slate', 124, 134, 140), patch_scale=1.5, edge_col=cal('slate', 140, 150, 154),
              edge_amt=0.45, cav_col=cal('slate', 44, 48, 60), cav_amt=0.5, facet_amt=0.07)
    painterly('brown', cal('brown', 156, 106, 46), cal('brown', 124, 82, 34),
              cal('brown', 178, 126, 58), patch_scale=1.4, speck=10.0,
              speck_col=cal('brown', 96, 62, 24), edge_col=cal('brown', 196, 142, 70),
              edge_amt=0.4, cav_col=cal('brown', 80, 50, 18), cav_amt=0.5, facet_amt=0.06)
    painterly('gem', cal('gem', 52, 104, 148), cal('gem', 36, 78, 112),
              cal('gem', 84, 140, 184), patch_scale=2.0, edge_col=cal('gem', 150, 196, 224),
              edge_amt=0.6, facet_amt=0.22, rough=0.35, spec=0.6)
    flat_mat('dark', srgb(18, 18, 16), 0.95)
    flat_mat('eye', srgb(244, 253, 255), 0.5, emit=6.0)
    flat_mat('eye_halo', srgb(96, 200, 226), 0.5, emit=1.6)


# ================================================================= skeleton
# Joint positions in the reference pose, from reference pixels + a depth
# choice (Y). These drive the body sculpt AND the rig, so the bones sit inside
# the forms they deform.
def J(u, v, y):
    return W(u, v, y)


JOINT = {
    'pelvis': J(548, 830, 0.0),
    'spine': J(548, 650, 0.1),
    'neck': J(548, 418, 0.25),
    'head': J(550, 362, -0.15),
    'shoulder_R': J(305, 482, 0.15),
    'elbow_R': J(274, 688, 0.35),
    'wrist_R': J(168, 670, -1.95),
    'hand_R': J(160, 612, -2.55),
    'shoulder_L': J(790, 466, 0.15),
    'elbow_L': J(893, 652, 0.35),
    'wrist_L': J(950, 868, -0.25),
    'hand_L': J(925, 950, -0.45),
    'hip_R': J(452, 878, 0.1),
    'knee_R': J(372, 1045, -0.05),
    'ankle_R': J(370, 1188, 0.66),
    'hip_L': J(646, 878, -0.3),
    'knee_L': J(742, 1030, -1.05),
    'ankle_L': J(782, 1203, -1.87),
}


def jv(name):
    return JOINT[name].copy()


def lerp(a, b, t):
    return Vector(a).lerp(Vector(b), t)


# ================================================================= body sculpt
# Metaball field: an isolated element's visible surface sits at k * radius
# (stiffness 2, threshold 0.6 -> k = sqrt(1 - 0.3^(1/3)) = 0.575). Elements
# are specified by their VISIBLE semi-axes and converted here.
STIFF = 3.2      # higher stiffness = tighter blends, more distinct muscle masses


def mb_k(s):
    return math.sqrt(1.0 - (0.6 / s) ** (1.0 / 3.0))


def mb_ellipsoid(mb, center, semi, rot=None, stiff=None, neg=False):
    s = stiff or STIFF
    el = mb.elements.new(type='ELLIPSOID')
    el.co = Vector(center)
    el.radius = 1.0 / mb_k(s)
    el.size_x, el.size_y, el.size_z = semi
    el.stiffness = s
    el.use_negative = neg
    if rot is not None:
        el.rotation = rot.to_quaternion() if hasattr(rot, 'to_quaternion') else rot
    return el


def mb_capsule(mb, a, b, radius, stiff=None):
    s = stiff or STIFF
    a, b = Vector(a), Vector(b)
    el = mb.elements.new(type='CAPSULE')
    el.co = (a + b) / 2
    el.radius = radius / mb_k(s)
    el.size_x = max(0.001, (b - a).length / 2)
    el.stiffness = s
    el.rotation = basis_from(b - a).to_quaternion()
    return el


def mb_ball(mb, c, r, stiff=None):
    s = stiff or STIFF
    el = mb.elements.new(type='BALL')
    el.co = Vector(c)
    el.radius = r / mb_k(s)
    el.stiffness = s
    return el


def limb_frame(a, b, fwd=Vector((0, -1, 0))):
    """Rotation whose local Z runs a->b and local -Y faces `fwd`."""
    z = (Vector(b) - Vector(a)).normalized()
    y = -(fwd - z * z.dot(fwd))
    if y.length < 1e-5:
        y = Vector((1, 0, 0)) - z * z.x
    y.normalize()
    x = y.cross(z)
    return Matrix((x, y, z)).transposed()


def build_body_field():
    """Distinct muscle masses (high stiffness so they meet in creases rather
    than melting together), sized from the reference: deltoid balls, huge
    biceps, blocky pecs and abs, thick forearms, heavy thighs."""
    mb = bpy.data.metaballs.new('BodyField')
    mb.resolution = 0.07
    mb.render_resolution = 0.07
    mb.threshold = 0.6
    M = 6.0   # stiffness for the named muscle masses
    # --- torso ---------------------------------------------------------------
    mb_ellipsoid(mb, (0, 0.22, 8.10), (1.80, 1.30, 1.42))            # ribcage
    mb_ellipsoid(mb, (0, 0.80, 8.45), (1.75, 0.84, 1.10))            # upper back
    for s in (-1, 1):
        mb_ellipsoid(mb, (s * 0.95, -0.92, 8.18), (1.02, 0.62, 0.76),
                     Euler((0, s * math.radians(-14), 0)), stiff=M)   # pectorals
        mb_ellipsoid(mb, (s * 0.88, 0.34, 8.98), (0.90, 0.70, 0.42))  # trapezius (low)
        mb_ellipsoid(mb, (s * 1.40, 0.35, 7.45), (0.78, 0.96, 1.05))  # lats
        mb_ellipsoid(mb, (s * 0.72, 0.80, 4.95), (0.85, 0.70, 0.78))  # glutes
        for z in (7.28, 6.86):
            mb_ellipsoid(mb, (s * 0.40, -1.26, z), (0.36, 0.26, 0.20), stiff=M)  # abs
    mb_ellipsoid(mb, (0, -0.18, 6.75), (1.56, 1.20, 1.06))           # abdomen
    mb_ellipsoid(mb, (0, 0.05, 5.35), (1.70, 1.28, 0.98))            # pelvis
    mb_capsule(mb, (0, 0.20, 9.10), (0, -0.20, 10.30), 0.64)         # neck
    # --- arms ------------------------------------------------------------------
    ARMS = {'R': dict(delt=(1.02, 1.05, 0.98), up=0.86, bi=(0.86, 0.72, 1.00), fore=0.84),
            'L': dict(delt=(1.08, 1.10, 1.02), up=0.96, bi=(1.02, 0.84, 1.08), fore=0.88)}
    for side in ('R', 'L'):
        s = -1 if side == 'R' else 1
        A = ARMS[side]
        sh, el, wr = jv('shoulder_' + side), jv('elbow_' + side), jv('wrist_' + side)
        up = limb_frame(sh, el)
        mb_ellipsoid(mb, sh + up @ Vector((s * 0.12, 0.0, -0.10)), A['delt'], up, stiff=M)
        mb_capsule(mb, sh, el, A['up'])
        mb_ellipsoid(mb, lerp(sh, el, 0.56) + up @ Vector((0, -0.30, 0)), A['bi'], up,
                     stiff=M)                                         # biceps
        mb_ellipsoid(mb, lerp(sh, el, 0.46) + up @ Vector((0, 0.32, 0)),
                     (A['bi'][0] * 0.92, A['bi'][1] * 0.9, A['bi'][2]), up, stiff=M)
        mb_ball(mb, el, 0.74)
        fo = limb_frame(el, wr)
        mb_capsule(mb, el, lerp(el, wr, 0.5), A['fore'])
        mb_capsule(mb, lerp(el, wr, 0.5), wr, A['fore'] * 0.80)
        mb_ellipsoid(mb, lerp(el, wr, 0.30), (A['fore'] * 1.05, A['fore'], 0.95), fo, stiff=M)
        mb_ball(mb, wr, 0.58)
    # --- legs ------------------------------------------------------------------
    for side in ('R', 'L'):
        hp, kn, an = jv('hip_' + side), jv('knee_' + side), jv('ankle_' + side)
        th = limb_frame(hp, kn)
        mb_capsule(mb, hp, kn, 0.92)
        mb_ellipsoid(mb, lerp(hp, kn, 0.42) + th @ Vector((0, -0.22, 0)),
                     (0.88, 0.78, 1.00), th, stiff=M)                 # quads
        mb_ball(mb, kn, 0.78, stiff=M)
        sh_ = limb_frame(kn, an)
        mb_capsule(mb, kn, an, 0.70)
        mb_ellipsoid(mb, lerp(kn, an, 0.32) + sh_ @ Vector((0, 0.20, 0)),
                     (0.76, 0.74, 0.86), sh_, stiff=M)                # calf
        mb_ball(mb, an, 0.62)
    o = bpy.data.objects.new('BodyField', mb)
    link(o)
    return o


def field_to_mesh(o, name, voxel=0.045, target_faces=6000, planar_deg=0.0):
    dg = bpy.context.evaluated_depsgraph_get()
    oe = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(oe)
    body = bpy.data.objects.new(name, me)
    link(body)
    bpy.data.objects.remove(o)
    activate(body)
    rm = body.modifiers.new('remesh', 'REMESH')
    rm.mode = 'VOXEL'
    rm.voxel_size = voxel
    apply_mods(body)
    ratio = min(1.0, target_faces / max(1, len(body.data.polygons)))
    dm = body.modifiers.new('decimate', 'DECIMATE')
    dm.decimate_type = 'COLLAPSE'
    dm.ratio = ratio
    apply_mods(body)
    if planar_deg > 0:
        dm = body.modifiers.new('planar', 'DECIMATE')
        dm.decimate_type = 'DISSOLVE'
        dm.angle_limit = math.radians(planar_deg)
        apply_mods(body)
    flat(body)
    return body


def rock(name, center, semi, rot=None, subdiv=2, jitter=0.04, seed=0):
    """Faceted ellipsoid mass: a low-subdivision icosphere, scaled, rotated and
    jittered so its facets read as carved stone rather than a smooth ball."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    rnd = random.Random(seed or (zlib.crc32(name.encode()) & 0xffff))   # stable across runs
    R = Matrix.Identity(3)
    if rot is not None:
        R = rot.to_matrix() if hasattr(rot, 'to_matrix') else Matrix(rot).to_3x3()
    for v in bm.verts:
        p = Vector((v.co.x * semi[0], v.co.y * semi[1], v.co.z * semi[2]))
        p += Vector([rnd.uniform(-jitter, jitter) * s for s in semi])
        v.co = Vector(center) + R @ p
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    link(o)
    return o


def tube(name, a, b, ra, rb, sides=10, seed=0):
    rnd = random.Random(seed or (zlib.crc32(name.encode()) & 0xffff))   # stable across runs
    ra_ = ring_pts(a, Vector(b) - Vector(a), ra, sides, 0.3)
    rb_ = ring_pts(b, Vector(b) - Vector(a), rb, sides, 0.3)
    o = loft(name, [ra_, rb_], None)
    return o


DELT_C = {}


def build_body():
    """Carved-stone anatomy: every muscle is its own faceted mass and the masses
    are UNIONED (voxel remesh), not blended, so deltoid, biceps, pecs and abs
    meet in creases like the reference instead of melting into sausages."""
    pieces = []
    add = pieces.append
    add(rock('ribcage', (0, 0.22, 8.10), (1.78, 1.28, 1.40), subdiv=3))
    add(rock('upperback', (0, 0.82, 8.45), (1.72, 0.82, 1.08), subdiv=3))
    add(rock('abdomen', (0, -0.16, 6.78), (1.52, 1.16, 1.02), subdiv=3))
    add(rock('pelvis', (0, 0.05, 5.35), (1.68, 1.26, 0.98), subdiv=3))
    for s in (-1, 1):
        add(rock(f'pec{s}', (s * 0.96, -0.96, 8.20), (1.04, 0.62, 0.76),
                 Euler((0, s * math.radians(-14), s * math.radians(8)))))
        add(rock(f'trap{s}', (s * 0.86, 0.34, 8.96), (0.90, 0.72, 0.44)))
        # the torso is yawed toward his right, so his left flank shows wider
        add(rock(f'lat{s}', (s * (1.32 if s > 0 else 1.12), 0.40, 7.55),
                 (0.74 if s > 0 else 0.62, 0.90, 0.95)))
        add(rock(f'glute{s}', (s * 0.72, 0.80, 4.95), (0.85, 0.70, 0.78)))
        add(rock(f'oblique{s}', (s * 1.10, -0.28, 6.40), (0.50, 0.80, 0.70)))
        for r_, z in enumerate((7.30, 6.90, 6.50)):
            ab = chamfer_box(f'abs{s}{r_}', (s * 0.40, -1.20 - 0.02 * r_, z), (0.66, 0.40, 0.36),
                             None, 0.10, 1)
            add(ab)
    add(tube('neck', (0, 0.22, 9.05), (0, -0.20, 10.35), 0.66, 0.62, 10))
    ARMS = {'R': dict(delt=(0.86, 0.96, 0.92), up=(0.80, 0.72), bi=(0.80, 0.70, 0.96),
                      fore=(0.72, 0.56)),
            'L': dict(delt=(0.96, 1.02, 1.00), up=(1.02, 0.92), bi=(1.12, 0.90, 1.10),
                      fore=(0.88, 0.66))}
    for side in ('R', 'L'):
        s = -1 if side == 'R' else 1
        A = ARMS[side]
        sh, el, wr = jv('shoulder_' + side), jv('elbow_' + side), jv('wrist_' + side)
        up = limb_frame(sh, el)
        # deltoid balls placed in world space from the reference: the left
        # one centred ~(850, 460) px, the right one on the shoulder joint
        dc = W(830, 452, 0.15) if side == 'L' else sh + Vector((0.28, 0.0, 0.32))
        DELT_C[side] = dc.copy()
        add(rock(f'delt{side}', dc, A['delt'], up))
        add(tube(f'uparm{side}', sh, el, A['up'][0], A['up'][1]))
        add(rock(f'biceps{side}', lerp(sh, el, 0.58) + up @ Vector((0, -0.26, 0)), A['bi'], up))
        add(rock(f'triceps{side}', lerp(sh, el, 0.46) + up @ Vector((0, 0.30, 0)),
                 (A['bi'][0] * 0.9, A['bi'][1] * 0.88, A['bi'][2]), up))
        add(rock(f'elbow{side}', el, (0.64, 0.66, 0.66) if side == 'R' else (0.80, 0.78, 0.78)))
        fo = limb_frame(el, wr)
        add(tube(f'forearm{side}', el, wr, A['fore'][0], A['fore'][1]))
        add(rock(f'foremass{side}', lerp(el, wr, 0.30), (A['fore'][0] * 1.05, A['fore'][0], 0.92), fo))
        add(rock(f'wrist{side}', wr, (0.50, 0.50, 0.50)))
    for side in ('R', 'L'):
        hp, kn, an = jv('hip_' + side), jv('knee_' + side), jv('ankle_' + side)
        th = limb_frame(hp, kn)
        add(tube(f'thigh{side}', hp, kn, 1.00, 0.88))
        add(rock(f'quad{side}', lerp(hp, kn, 0.42) + th @ Vector((0, -0.22, 0)), (0.88, 0.78, 1.00), th))
        add(rock(f'knee{side}', kn, (0.86, 0.86, 0.80)))
        sh_ = limb_frame(kn, an)
        add(tube(f'shin{side}', kn, an, 0.92 if side == 'L' else 0.94,
                 0.82 if side == 'L' else 0.82))
        add(rock(f'calf{side}', lerp(kn, an, 0.32) + sh_ @ Vector((0, 0.20, 0)), (0.76, 0.74, 0.86), sh_))
        add(rock(f'ankle{side}', an, (0.70, 0.70, 0.66)))
    for p in pieces:
        activate(p)
    bpy.ops.object.select_all(action='DESELECT')
    for p in pieces:
        p.select_set(True)
    bpy.context.view_layer.objects.active = pieces[0]
    bpy.ops.object.join()
    body = bpy.context.object
    body.name = 'Body_Skin'
    body.data.name = 'Body_Skin'
    rm = body.modifiers.new('union', 'REMESH')
    rm.mode = 'VOXEL'
    rm.voxel_size = 0.045
    apply_mods(body)
    dm = body.modifiers.new('decimate', 'DECIMATE')
    dm.decimate_type = 'COLLAPSE'
    dm.ratio = min(1.0, 6200 / max(1, len(body.data.polygons)))
    apply_mods(body)
    flat(body)
    body.data.materials.clear()
    body.data.materials.append(MATS['skin'])
    part(body, 'Body', ('skin',), 'skin')
    return body


# ================================================================= traced slabs
def slab(name, pts_uv, y_front, thick, mat, bevel_w=0.02, segments=1, normal=None,
         angle=40.0, rev=False):
    """A piece whose front outline is traced in reference pixels. The outline is
    unprojected onto a plane through Y=y_front (optionally tilted by `normal`,
    which points toward the viewer) and extruded `thick` away from the viewer."""
    pts = uv_outline(pts_uv, y_front, normal)
    nd = Vector(normal).normalized() if normal is not None else Vector((0, -1, 0))
    if rev:
        pts = list(reversed(pts))
    return extrude_poly(name, pts, nd, thick, mat, bevel_w, segments, angle)


def face_z(v, y=-1.3):
    return W(550, v, y).z


# ================================================================= head
FACE_Y = -1.30          # front plane of the skull's maxilla / forehead


def boolean_cut(target, cutters, delete=True):
    """Carve cutters out of target (EXACT solver). Cutter materials transfer to
    the carved walls, which is how the sockets, nose and mouth pits go dark."""
    for c in cutters:
        md = target.modifiers.new('carve', 'BOOLEAN')
        md.operation = 'DIFFERENCE'
        md.solver = 'EXACT'
        md.object = c
        if hasattr(md, 'material_mode'):
            md.material_mode = 'TRANSFER'
        c.hide_render = True
        c.hide_viewport = True
    apply_mods(target)
    if delete:
        for c in cutters:
            bpy.data.objects.remove(c)
    flat(target)
    return target


def build_head():
    bone, dark, teeth = MATS['bone'], MATS['dark'], MATS['teeth']
    # --- skull base: lofted chamfered sections, wide at the cheekbones and
    # narrowing to the maxilla; the brow band and dome cover everything above
    # (image row, half width, face set-back, cheek plane depth, ridge)
    secs = [(246, 0.76, 0.00, 0.20, 0.05), (262, 0.80, 0.00, 0.22, 0.06),
            (286, 0.84, 0.02, 0.30, 0.08), (302, 0.80, 0.03, 0.34, 0.08),
            (316, 0.66, 0.06, 0.26, 0.06), (330, 0.60, 0.07, 0.22, 0.05),
            (342, 0.55, 0.08, 0.20, 0.04)]
    rings = []
    for v, hx, back, ck, rg in secs:
        z = face_z(v, FACE_Y)
        y0, y1 = FACE_Y + back, 0.55
        rings.append([Vector(p) for p in (
            (0.0, y0 - rg, z), (hx * 0.46, y0, z), (hx * 0.86, y0 + ck * 0.45, z),
            (hx, y0 + ck, z), (hx - 0.06, y1 - 0.2, z), (hx * 0.6, y1, z), (-hx * 0.6, y1, z),
            (-hx + 0.06, y1 - 0.2, z), (-hx, y0 + ck, z), (-hx * 0.86, y0 + ck * 0.45, z),
            (-hx * 0.46, y0, z))])
    base = loft('Skull', rings, bone)
    bevel(base, 0.05, 1, 25)
    cut = []
    def ell(cx, cy, rx, ry, tilt, n=16):
        t = math.radians(tilt)
        return [(cx + math.cos(2 * math.pi * i / n) * rx * math.cos(t)
                 - math.sin(2 * math.pi * i / n) * ry * math.sin(t),
                 cy + math.cos(2 * math.pi * i / n) * rx * math.sin(t)
                 + math.sin(2 * math.pi * i / n) * ry * math.cos(t)) for i in range(n)]
    for nm, pts, dep in (
            ('SocketL', ell(515.5, 277.5, 26.0, 15.5, 8), 0.42),
            ('SocketR', ell(583.0, 275.0, 26.0, 15.5, -8), 0.42),
            ('Nose', [(550, 281), (557, 288), (561, 303), (553, 301), (550, 297),
                      (547, 301), (539, 303), (543, 288)], 0.26),
            ('Mouth', [(519, 315), (534, 313), (550, 314), (566, 313), (581, 315),
                       (586, 328), (584, 341), (552, 342), (521, 341), (518, 328)], 0.30)):
        c = slab(nm + 'Cut', pts, FACE_Y - 0.4, 0.4 + dep, dark, 0.0)
        cut.append(c)
    boolean_cut(base, cut)
    part(base, 'Head', ('rigid', 'Head'), 'bone')
    # --- proud bone around the pits ---------------------------------------
    # brow slabs: heavy, sloping down to the centre (the angry V); they
    # overhang the sockets
    for nm, pts in (('BrowL', [(480, 239), (505, 241), (532, 249), (547, 258), (548, 270),
                               (534, 272), (514, 267), (496, 266), (481, 269), (475, 254)]),
                    ('BrowR', [(609, 233), (619, 242), (624, 256), (616, 266), (590, 267),
                               (570, 270), (551, 271), (550, 258), (566, 247), (588, 237)])):
        b = slab(nm, pts, FACE_Y - 0.24, 0.62, bone, 0.13, 2, angle=25.0)
        part(b, 'Head', ('rigid', 'Head'), 'bone')
    # nose bridge between the brows
    fh = slab('NoseBridge', [(540, 252), (550, 255), (560, 252), (557, 262), (553, 280),
                             (547, 280), (543, 262)], FACE_Y - 0.05, 0.3, bone, 0.02, 1)
    part(fh, 'Head', ('rigid', 'Head'), 'bone')
    # cheekbone plates: angled planes flush with the skull's sides
    for nm, pts, nx in (('CheekL', [(476, 283), (492, 287), (501, 298), (500, 310), (488, 313),
                                    (478, 305)], -0.55),
                        ('CheekR', [(626, 282), (611, 286), (602, 297), (603, 309), (615, 312),
                                    (625, 304)], 0.55)):
        c = slab(nm, pts, FACE_Y + 0.07, 0.40, bone, 0.05, 1, angle=25.0, normal=(nx, -1, 0.1))
        part(c, 'Head', ('rigid', 'Head'), 'bone')
    # --- teeth set into the mouth pit ---------------------------------------
    upper = [(523, 537), (538, 551.5), (552.3, 566), (567, 578.3), (578.8, 582.5)]
    lower = [(522.3, 528.4), (528.9, 537.2), (538, 552), (553, 566.4), (567, 575.6),
             (576, 583)]
    for i, (a, b_) in enumerate(upper):
        pts = [(a + 0.35, 316.4), (b_ - 0.35, 316.4), (b_ - 0.35, 328.8), (a + 0.35, 328.8)]
        t = slab(f'ToothU{i}', pts, FACE_Y - 0.08, 0.38, teeth, 0.013, 1)
        part(t, 'Head', ('rigid', 'Head'), 'teeth')
    for i, (a, b_) in enumerate(lower):
        pts = [(a + 0.35, 329.3), (b_ - 0.35, 329.3), (b_ - 0.35, 339.4), (a + 0.35, 339.4)]
        t = slab(f'ToothL{i}', pts, FACE_Y - 0.06, 0.38, teeth, 0.012, 1)
        part(t, 'Head', ('rigid', 'Jaw'), 'teeth')
    # --- mandible: a chunky block with a squared chin ------------------------
    jw = slab('Jaw', [(498, 340), (517, 344), (552, 346), (588, 344), (598, 340), (597, 351),
                      (590, 361), (575, 366), (550, 367), (522, 366), (510, 362), (501, 351)],
              FACE_Y - 0.06, 1.05, bone, 0.07, 2)
    part(jw, 'Head', ('rigid', 'Jaw'), 'bone')
    # --- eye glows (own section, EyeGlow) at the bottom of the socket pits --
    def almond(cx, cy, rx, ry, tilt_deg, n=14):
        t = math.radians(tilt_deg)
        pts = []
        for i in range(n):
            a_ = 2 * math.pi * i / n
            x, y = math.cos(a_) * rx, math.sin(a_) * ry * (1.0 if math.sin(a_) > 0 else 0.85)
            pts.append((cx + x * math.cos(t) - y * math.sin(t), cy + x * math.sin(t) + y * math.cos(t)))
        return pts
    for nm, (cx, cy, tilt) in (('EyeL', (519.8, 280.6, 12)), ('EyeR', (580.4, 276.8, -12))):
        h = slab(nm + 'Halo', almond(cx, cy, 13.5, 9.5, tilt), FACE_Y + 0.05, 0.04,
                 MATS['eye_halo'], 0.0)
        part(h, 'EyeGlow', ('rigid', 'Head'), 'eye_halo')
        e = slab(nm, almond(cx, cy, 9.0, 6.4, tilt), FACE_Y - 0.01, 0.05, MATS['eye'], 0.012, 1)
        part(e, 'EyeGlow', ('rigid', 'Head'), 'eye')


# ================================================================= nemes
def row_lerp(table, v):
    """Piecewise-linear lookup in a [(v, value), ...] table (v ascending)."""
    if v <= table[0][0]:
        return table[0][1]
    for (a, x), (b, y) in zip(table, table[1:]):
        if a <= v <= b:
            return x + (y - x) * (v - a) / (b - a)
    return table[-1][1]


# Traced per side (reference px): face edge, front crease, outer silhouette.
WING = {
    'L': dict(face=[(236, 482), (280, 474), (378, 478)],
              crease=[(236, 446), (250, 440), (377, 423)],
              outer=[(236, 402), (250, 396), (300, 374), (350, 353), (378, 346)],
              rows=[228, 243, 278, 313, 351, 380], cols='BGBGB'),
    'R': dict(face=[(232, 615), (290, 628), (374, 626)],
              crease=[(232, 648), (245, 650), (370, 683)],
              outer=[(232, 699), (250, 707), (300, 734), (350, 758), (374, 762)],
              rows=[224, 234, 265, 300, 336, 374], cols='BGBGB'),
}
WING_Y = dict(face=-1.02, crease=-0.96, outer=-0.32)


def wing_section(v_by_side):
    """Closed hood cross-section at image rows (vL, vR): outer shell around the
    back, inner shell against the head. Returns a list of 3D points."""
    out = {}
    for side, v in v_by_side.items():
        w = WING[side]
        f = W(row_lerp(w['face'], v), v, WING_Y['face'])
        c = W(row_lerp(w['crease'], v), v, WING_Y['crease'])
        o = W(row_lerp(w['outer'], v), v, WING_Y['outer'])
        s = -1 if side == 'L' else 1
        z = (f.z + c.z + o.z) / 3
        f.z = c.z = o.z = z
        back_o = Vector((o.x - s * 0.20, 0.95, z))
        back_c = Vector((s * 1.02, 1.62, z))
        inner_f = Vector((f.x - s * 0.05, WING_Y['face'] + 0.12, z))
        inner_m = Vector((s * 0.86, 0.55, z))
        inner_b = Vector((s * 0.58, 1.22, z))
        out[side] = dict(f=f, c=c, o=o, bo=back_o, bc=back_c, i_f=inner_f, i_m=inner_m,
                         i_b=inner_b, z=z)
    L, R = out['L'], out['R']
    zb = (L['z'] + R['z']) / 2
    backmid = Vector((0, 1.76, zb))
    innermid = Vector((0, 1.34, zb))
    loop = [L['f'], L['c'], L['o'], L['bo'], L['bc'], backmid, R['bc'], R['bo'], R['o'],
            R['c'], R['f'], R['i_f'], R['i_m'], R['i_b'], innermid, L['i_b'], L['i_m'],
            L['i_f']]
    return loop


def band_solid(name, loop_top, loop_bot, mat, bevel_w=0.035):
    o = loft(name, [loop_top, loop_bot], mat, closed=True)
    bevel(o, bevel_w, 1, 30.0)
    flat(o)
    return o


def build_nemes():
    gold, blue = MATS['gold'], MATS['blue']
    col = {'G': gold, 'B': blue}
    # --- wings: stacked stripe bands, lofted between traced rows ---------
    rl, rr = WING['L']['rows'], WING['R']['rows']
    for i in range(len(rl) - 1):
        top = wing_section({'L': rl[i] + 0.25, 'R': rr[i] + 0.25})
        bot = wing_section({'L': rl[i + 1] - 0.25, 'R': rr[i + 1] - 0.25})
        k = WING['L']['cols'][i]
        o = band_solid(f'NemesWing{i}', top, bot, col[k], 0.022)
        part(o, 'Head', ('rigid', 'Head'), 'gold' if k == 'G' else 'blue')
    # --- back flap: continues the stripes down the back of the neck ------
    zb0 = wing_section({'L': rl[-1], 'R': rr[-1]})[5].z
    flap_rows = [zb0, zb0 - 0.34, zb0 - 0.68, zb0 - 1.02, zb0 - 1.30]
    for i in range(len(flap_rows) - 1):
        za, zb_ = flap_rows[i] - 0.015, flap_rows[i + 1] + 0.015
        rings = []
        for z, spread in ((za, 1.0 - 0.06 * i), (zb_, 1.0 - 0.06 * (i + 1))):
            ring = []
            for a in np.linspace(-1, 1, 9):
                ang = a * math.radians(62)
                r_o, r_i = 1.32 * spread, 1.06 * spread
                ring.append(Vector((math.sin(ang) * r_o * 1.25, 0.55 + math.cos(ang) * r_o, z)))
            for a in np.linspace(1, -1, 9):
                ang = a * math.radians(62)
                r_i = 1.02 * spread
                ring.append(Vector((math.sin(ang) * r_i * 1.2, 0.50 + math.cos(ang) * r_i, z)))
            rings.append(ring)
        k = 'G' if i % 2 == 0 else 'B'
        o = band_solid(f'NemesBack{i}', rings[0], rings[1], col[k], 0.03)
        part(o, 'Head', ('rigid', 'Head'), 'gold' if k == 'G' else 'blue')
    # --- tail (queue): tapered, banded, hangs down the upper back ---------
    zt = flap_rows[-1]
    tail_pts = [Vector((0, 1.62, zt + 0.25)), Vector((0, 1.72, zt - 0.35)),
                Vector((0, 1.78, zt - 0.95)), Vector((0, 1.80, zt - 1.45))]
    rad = [0.30, 0.26, 0.21, 0.14]
    TAIL_PTS[:] = [p.copy() for p in tail_pts]
    for i in range(len(tail_pts) - 1):
        r0 = ring_pts(tail_pts[i], tail_pts[i + 1] - tail_pts[i], rad[i], 8, math.pi / 8)
        r1 = ring_pts(tail_pts[i + 1], tail_pts[i + 1] - tail_pts[i], rad[i + 1], 8, math.pi / 8)
        k = 'B' if i % 2 == 0 else 'G'
        o = loft(f'NemesTail{i}', [r0, r1], col[k])
        bevel(o, 0.025, 1, 30)
        flat(o)
        part(o, 'Head', ('rigid', 'NemesTail'), 'gold' if k == 'G' else 'blue')
    # --- dome: radial stripes from the brow band over the crown ----------
    base_loop = wing_section({'L': rl[0], 'R': rr[0]})
    zb = base_loop[0].z
    crown = W(548, 158, 0.15)
    ztop = crown.z
    # outline widths from the reference mask silhouette rows (at depth ~0.1)
    sil = [(158, 512, 589), (176, 463, 643), (200, 428, 671), (224, 415, 686),
           (zb, None, None)]
    n_rows = 7
    # stripe boundaries (degrees, 0 = front, + toward the character's left)
    # Measured on the reference at row 200: gold centre (under the cobra) spans
    # about +-12.5 deg, then blue to +-27, gold to +-46, blue (running down into
    # the wing's corner stripe); the back continues the alternation.
    edges = [-180, -150, -118, -88, -64, -46, -27, -12.5, 12.5, 27, 46, 64, 88, 118, 150, 180]
    mids = [abs(round((edges[i] + edges[i + 1]) / 2, 3)) for i in range(len(edges) - 1)]
    rank = sorted(set(mids))
    cols = ['G' if rank.index(m) % 2 == 0 else 'B' for m in mids]

    def dome_pt(ang_deg, t):
        """t=0 at the brow line, 1 at the crown."""
        a = math.radians(ang_deg)
        # base ellipse: front just behind the brow band, sides at the wing tops
        rx0, ry_f, ry_b, cy0 = 1.56, 1.18, 1.78, 0.30
        ry0 = ry_f if math.cos(a) > 0 else ry_b
        e = math.sin(math.pi / 2 * t)
        sq = (1 - t ** 1.6) ** 0.62
        x = math.sin(a) * rx0 * sq
        y = cy0 - math.cos(a) * (ry0 * sq) + (crown.y - cy0) * t * 0.0
        z = zb + (ztop - zb) * (1 - (1 - t) ** 1.9)
        return Vector((x, y, z))

    for i in range(len(edges) - 1):
        a0, a1 = edges[i] + 0.9, edges[i + 1] - 0.9
        steps = max(2, int(abs(a1 - a0) / 8))
        angs = list(np.linspace(a0, a1, steps + 1))
        rows = []
        for t in np.linspace(0.0, 0.985, n_rows):
            rows.append([dome_pt(a, t) for a in angs])
        # inner surface (offset toward the centre) makes it a solid shell
        verts, faces = [], []
        nr, nc = len(rows), len(angs)
        for r in rows:
            verts += r
        cen = Vector((0, 0.30, zb))
        for r in rows:
            for p in r:
                d = (p - Vector((0, 0.30, p.z)))
                q = p - d.normalized() * 0.16 - Vector((0, 0, 0.10))
                verts.append(q)
        off = nr * nc
        for a in range(nr - 1):
            for b in range(nc - 1):
                v0 = a * nc + b
                faces.append((v0, v0 + 1, v0 + nc + 1, v0 + nc))
                faces.append((off + v0, off + v0 + nc, off + v0 + nc + 1, off + v0 + 1))
        for a in range(nr - 1):
            for b in (0, nc - 1):
                v0 = a * nc + b
                faces.append((v0, v0 + nc, off + v0 + nc, off + v0))
        for b in range(nc - 1):
            faces.append((b, off + b, off + b + 1, b + 1))
            v0 = (nr - 1) * nc + b
            faces.append((v0, v0 + 1, off + v0 + 1, off + v0))
        k = cols[i]
        o = mesh_obj(f'NemesDome{i}', verts, faces, col[k])
        recalc_normals(o)
        bevel(o, 0.03, 1, 35)
        flat(o)
        part(o, 'Head', ('rigid', 'Head'), 'gold' if k == 'G' else 'blue')
    # crown cap closes the tiny hole at the top
    cap = chamfer_box('NemesCrown', dome_pt(0, 0.985) + Vector((0, 0.38, 0.02)), (0.32, 0.9, 0.08),
                      gold, 0.02)
    part(cap, 'Head', ('rigid', 'Head'), 'gold')
    # --- gold brow band across the forehead ------------------------------
    bpts_top, bpts_bot = [], []
    for u in np.linspace(474, 626, 13):
        vt = 225 + 3 * abs(u - 550) / 76
        vb = 248 + 2 * abs(u - 550) / 76
        yd = FACE_Y + 0.02 + 0.30 * ((u - 550) / 76) ** 2
        bpts_top.append(W(u, vt, yd))
        bpts_bot.append(W(u, vb, yd))
    verts, faces = [], []
    n = len(bpts_top)
    for p in bpts_top + bpts_bot:
        verts.append(p)
    for p in bpts_top + bpts_bot:
        verts.append(p + Vector((0, 0.42, 0)))
    for i in range(n - 1):
        faces.append((i, i + 1, n + i + 1, n + i))                         # front
        faces.append((2 * n + i, 3 * n + i, 3 * n + i + 1, 2 * n + i + 1))  # back
        faces.append((i, 2 * n + i, 2 * n + i + 1, i + 1))                 # top
        faces.append((n + i, n + i + 1, 3 * n + i + 1, 3 * n + i))         # bottom
    faces.append((0, n, 3 * n, 2 * n))
    faces.append((n - 1, 2 * n + n - 1, 3 * n + n - 1, n + n - 1))
    bb = mesh_obj('BrowBand', verts, faces, gold)
    recalc_normals(bb)
    bevel(bb, 0.035, 1, 30)
    flat(bb)
    part(bb, 'Head', ('rigid', 'Head'), 'gold')
    # --- lappets: four stacked stripe blocks per side ---------------------
    LAP = {
        'L': dict(rows=[(376, 412.5, 'G'), (412.5, 445, 'B'), (445, 482.5, 'G'),
                        (482.5, 521, 'B')],
                  x=[(376, 418, 482), (521, 415, 470)], y=(-0.98, -2.02)),
        'R': dict(rows=[(368, 396, 'G'), (396, 427, 'B'), (427, 461.5, 'G'), (461.5, 502, 'B')],
                  x=[(368, 617, 681), (502, 617, 671)], y=(-0.98, -1.98)),
    }
    for side, spec in LAP.items():
        v0, v1 = spec['rows'][0][0], spec['rows'][-1][1]
        for j, (a, b, k) in enumerate(spec['rows']):
            def edge(v):
                t = (v - spec['x'][0][0]) / (spec['x'][1][0] - spec['x'][0][0])
                xl = spec['x'][0][1] + (spec['x'][1][1] - spec['x'][0][1]) * t
                xr = spec['x'][0][2] + (spec['x'][1][2] - spec['x'][0][2]) * t
                yy = spec['y'][0] + (spec['y'][1] - spec['y'][0]) * ((v - v0) / (v1 - v0)) ** 0.8
                return xl, xr, yy
            xl0, xr0, y0 = edge(a)
            xl1, xr1, y1 = edge(b)
            fr = [W(xl0, a, y0), W(xr0, a, y0), W(xr1, b, y1), W(xl1, b, y1)]
            # thickness backward (toward +Y) with a slight inward taper
            th = 0.34
            bk = [p + Vector((0, th, 0)) for p in fr]
            verts = fr + bk
            faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3),
                     (3, 7, 4, 0)]
            o = mesh_obj(f'Lappet{side}{j}', verts, faces, col[k])
            recalc_normals(o)
            bevel(o, 0.028, 1, 30)
            flat(o)
            bone = f'NemesLappet_{side}_1' if j < 2 else f'NemesLappet_{side}_2'
            part(o, 'Head', ('rigid', bone), 'gold' if k == 'G' else 'blue')


# ================================================================= uraeus
def build_uraeus():
    """Gold cobra rising from the brow band. Traced hood outline (reference px),
    built as relief: hood plate, raised rim, recessed belly with scute ridges,
    a domed head with a downward snout, and two dark eyes."""
    gold, dark = MATS['gold'], MATS['dark']
    hood = [(511.5, 163), (518, 150), (527, 144), (542, 140.5), (557, 142.5), (569, 148),
            (576, 157), (579, 171), (577, 186), (573, 203), (566, 220), (561, 232),
            (527, 232), (521, 219), (514, 200), (510, 182)]
    n = (0, -1, 0.18)
    yb = FACE_Y - 0.10
    h = slab('UraeusHood', hood, yb, 0.22, gold, 0.05, 2, normal=n)
    part(h, 'Head', ('rigid', 'Head'), 'gold')
    # raised rim: the hood outline minus an inset, as a separate proud band
    cx = sum(u for u, _ in hood) / len(hood)
    cy = sum(v for _, v in hood) / len(hood)
    inset = [(cx + (u - cx) * 0.80, cy + (v - cy) * 0.86) for u, v in hood]
    rim_pts = hood + [hood[0]] + [inset[0]] + list(reversed(inset))
    belly = [(530, 176), (554, 176), (557, 196), (553, 215), (547, 229), (537, 229),
             (531, 215), (527, 196)]
    bl = slab('UraeusBelly', belly, yb - 0.03, 0.06, gold, 0.018, 1, normal=n)
    part(bl, 'Head', ('rigid', 'Head'), 'gold')
    for i, v in enumerate(np.linspace(180, 224, 6)):
        half = 11.5 - i * 1.0
        pts = [(542 - half, v), (542 + half, v), (542 + half - 0.8, v + 4.6),
               (542 - half + 0.8, v + 4.6)]
        s = slab(f'UraeusScute{i}', pts, yb - 0.06, 0.04, gold, 0.012, 1, normal=n)
        part(s, 'Head', ('rigid', 'Head'), 'gold')
    # hood rim ridge: thin slabs along the upper outline
    for i in range(len(hood) - 1):
        (u0, v0), (u1, v1) = hood[i], hood[i + 1]
        (w0, x0), (w1, x1) = inset[i], inset[i + 1]
        quad = [(u0, v0), (u1, v1), (w1 * 0.3 + u1 * 0.7, x1 * 0.3 + v1 * 0.7),
                (w0 * 0.3 + u0 * 0.7, x0 * 0.3 + v0 * 0.7)]
        r = slab(f'UraeusRim{i}', quad, yb - 0.035, 0.05, gold, 0.0, normal=n, rev=True)
        part(r, 'Head', ('rigid', 'Head'), 'gold')
    # head: domed, snout pointing down over the upper hood
    head = [(524, 150), (533, 145), (551, 145), (560, 150), (562, 159), (556, 167),
            (550, 176), (542, 181), (534, 176), (528, 167), (522, 159)]
    hd = slab('UraeusHead', head, yb - 0.13, 0.20, gold, 0.045, 2, normal=(0, -1, 0.35))
    part(hd, 'Head', ('rigid', 'Head'), 'gold')
    for nm, (u, v) in (('UraeusEyeL', (526.5, 156.5)), ('UraeusEyeR', (557.5, 156.5))):
        c = W(u, v, yb - 0.17)
        e = rock(nm, c, (0.05, 0.035, 0.045), subdiv=1, jitter=0.0)
        e.data.materials.append(dark)
        flat(e)
        part(e, 'Head', ('rigid', 'Head'), 'dark')


# ================================================================= collar
CLEAR = []   # (name, grid rows of points, clearance): body is conformed under these


def collar_frame():
    """Usekh collar: a draped surface around the neck. P(theta, s): theta 0 =
    front, + toward the character's left; s = distance along the drape.

    The drape angle runs from alpha_in at the neck to alpha_out at the rim, so
    over the shoulders the collar first rises onto the trapezius/deltoid and
    then rolls down. His left shoulder is raised (the arm hangs out wide) and
    his right is dropped forward over the staff grip, as in the reference."""
    RIN = 0.80
    # theta, s_out, alpha_in, alpha_out  (degrees below horizontal)
    CL = [(0, 2.16, 50, 68), (35, 2.06, 38, 62), (70, 1.80, -10, 42), (95, 1.66, -18, 40),
          (125, 1.58, 8, 45), (155, 1.55, 32, 55), (180, 1.55, 38, 60)]
    CR = [(0, 2.16, 50, 68), (35, 2.06, 40, 64), (70, 1.76, 6, 48), (95, 1.62, 2, 44),
          (125, 1.58, 14, 48), (155, 1.55, 32, 55), (180, 1.55, 38, 60)]

    def ease_lerp(tab, a, i):
        # smoothstep between control angles: zero slope at every node, so the
        # front of the collar is a round U instead of a V
        for (a0, *v0), (a1, *v1) in zip(tab, tab[1:]):
            if a0 <= a <= a1:
                t = (a - a0) / (a1 - a0)
                t = t * t * (3 - 2 * t)
                return v0[i - 1] + (v1[i - 1] - v0[i - 1]) * t
        return tab[-1][i]

    def ctrl(th):
        t = ((th + 180) % 360) - 180
        tab = CL if t >= 0 else CR
        a = abs(t)
        return tuple(ease_lerp(tab, a, i) for i in (1, 2, 3))

    def base_z(th):
        a = math.radians(th)
        return 9.62 + 0.20 * (1 - math.cos(a)) / 2 + 0.10 * abs(math.sin(a))

    def P(th, s, lift=0.0):
        a = math.radians(th)
        h = Vector((math.sin(a), -math.cos(a), 0))
        base = Vector((h.x * RIN * 1.10, 0.10 + h.y * RIN * (1.0 if h.y < 0 else 0.9),
                       base_z(th)))
        s_out, a_in, a_out = ctrl(th)
        steps = 10
        p = base.copy()
        al = math.radians(a_in)
        for i in range(steps):
            f = (i + 0.5) / steps * s / max(s_out, 1e-6)
            al = math.radians(a_in + (a_out - a_in) * min(1.0, f) ** 1.4)
            p += (h * math.cos(al) + Vector((0, 0, -math.sin(al)))) * (s / steps)
        nrm = (h * math.sin(al) + Vector((0, 0, math.cos(al)))).normalized()
        return p + nrm * lift, nrm

    def ctrl_s(th):
        return (ctrl(th)[0], 0)
    return P, ctrl_s


def surface_tile(name, P, th0, th1, f0, f1, ctrl, thick, mat, lift, nu=3, nv=2,
                 bevel_w=0.028):
    """A beveled tile covering theta [th0, th1] and drape fraction [f0, f1]."""
    top, bot = [], []
    for j in range(nv + 1):
        f = f0 + (f1 - f0) * j / nv
        for i in range(nu + 1):
            th = th0 + (th1 - th0) * i / nu
            s = f * ctrl(th)[0]
            p, n = P(th, s, lift)
            top.append(p)
            bot.append(p - n * thick)
    k = nu + 1
    verts = top + bot
    off = len(top)
    faces = []
    for j in range(nv):
        for i in range(nu):
            a = j * k + i
            faces.append((a, a + 1, a + k + 1, a + k))
            faces.append((off + a, off + a + k, off + a + k + 1, off + a + 1))
    for j in range(nv):
        for i in (0, nu):
            a = j * k + i
            faces.append((a, a + k, off + a + k, off + a))
    for i in range(nu):
        a = i
        faces.append((a, off + a, off + a + 1, a + 1))
        a = nv * k + i
        faces.append((a, a + 1, off + a + 1, off + a))
    o = mesh_obj(name, verts, faces, mat)
    recalc_normals(o)
    if bevel_w:
        bevel(o, bevel_w, 1, 30)
    flat(o)
    return o


COLLAR_RINGS = [  # (f0, f1, tiles around 360, material cycle)
    (0.00, 0.21, 14, ('gold',)),
    (0.21, 0.62, 16, ('blue', 'slate', 'blue')),
    (0.62, 0.95, 26, ('gold',)),
]


def build_collar():
    P, ctrl = collar_frame()
    for ri, (f0, f1, n, cyc) in enumerate(COLLAR_RINGS):
        step = 360.0 / n
        gap = 1.1 if ri < 2 else 0.8
        for t in range(n):
            th0 = -180 + t * step + gap / 2 + step / 2
            th1 = th0 + step - gap
            key = cyc[t % len(cyc)]
            o = surface_tile(f'Collar{ri}_{t}', P, th0, th1, f0 + 0.008, f1 - 0.008, ctrl,
                             0.13, MATS[key], 0.10 + 0.012 * ri, nu=2, nv=2)
            part(o, 'Head', ('rigid', 'UpperTorso'), key)
    # raised outer rim (one continuous lip)
    rim = []
    for th in np.linspace(-180, 180, 73)[:-1]:
        ring = []
        for f, lift in ((0.945, 0.12), (1.0, 0.14), (1.0, 0.02), (0.945, 0.0)):
            p, nn = P(th, f * ctrl(th)[0], lift + 0.02)
            ring.append(p)
        rim.append(ring)
    verts = [p for r in rim for p in r]
    faces = []
    m = len(rim)
    for i in range(m):
        j = (i + 1) % m
        for k in range(4):
            a, b = i * 4 + k, i * 4 + (k + 1) % 4
            c, d = j * 4 + (k + 1) % 4, j * 4 + k
            faces.append((a, b, c, d))
    o = mesh_obj('CollarRim', verts, faces, MATS['gold'])
    recalc_normals(o)
    bevel(o, 0.02, 1, 30)
    flat(o)
    part(o, 'Head', ('rigid', 'UpperTorso'), 'gold')
    sheet = []
    for th in np.linspace(-180, 180, 49)[:-1]:
        sheet.append([P(th, f * ctrl(th)[0], 0.0)[0] for f in np.linspace(0, 1.0, 8)])
    CLEAR.append(('collar', sheet, 0.02))


# ================================================================= belt
BELT_YAW = math.radians(-12.0)
BELT_Z = (5.64, 5.90, 6.40, 6.66)


def waist_pt(th, z, off=0.0, a=1.62, b=1.46, p=2.6):
    """Superellipse around the waist in the pelvis frame (yawed)."""
    t = math.radians(th)
    s, c = math.sin(t), math.cos(t)
    x = (a + off) * math.copysign(abs(s) ** (2 / p), s)
    y = -(b + off) * math.copysign(abs(c) ** (2 / p), c)
    cy, sy = math.cos(BELT_YAW), math.sin(BELT_YAW)
    return Vector((x * cy - y * sy, x * sy + y * cy + 0.02, z))


def closed_profile_band(name, profile, mat, ptfn, n=48, bevel_w=0.03):
    """Band swept around a closed loop. profile: [(z, radial offset)] as a closed
    polygon in the (offset, z) plane; ptfn(theta, z, off) -> world point."""
    ths = np.linspace(-180, 180, n + 1)[:-1]
    rings = [[ptfn(th, z, off) for (z, off) in profile] for th in ths]
    k = len(profile)
    verts = [p for r in rings for p in r]
    faces = []
    for i in range(n):
        j = (i + 1) % n
        for q in range(k):
            a, b = i * k + q, i * k + (q + 1) % k
            c, d = j * k + (q + 1) % k, j * k + q
            faces.append((a, b, c, d))
    o = mesh_obj(name, verts, faces, mat)
    recalc_normals(o)
    if bevel_w:
        bevel(o, bevel_w, 1, 30)
    flat(o)
    return o


def build_belt():
    z0, z1, z2, z3 = BELT_Z
    top = closed_profile_band('BeltTop', [(z3, 0.17), (z2, 0.17), (z2, -0.10), (z3, -0.10)],
                              MATS['gold'], waist_pt)
    part(top, 'Waist', ('rigid', 'LowerTorso'), 'gold')
    mid = closed_profile_band('BeltMid', [(z2 + 0.01, 0.085), (z1 - 0.01, 0.085),
                                          (z1 - 0.01, -0.10), (z2 + 0.01, -0.10)],
                              MATS['brown'], waist_pt, bevel_w=0.012)
    part(mid, 'Waist', ('rigid', 'LowerTorso'), 'brown')
    bot = closed_profile_band('BeltBot', [(z1, 0.17), (z0, 0.17), (z0, -0.10), (z1, -0.10)],
                              MATS['gold'], waist_pt)
    part(bot, 'Waist', ('rigid', 'LowerTorso'), 'gold')
    CLEAR.append(('belt', [[waist_pt(th, z, 0.0) for z in np.linspace(z0 - 0.1, z3 + 0.1, 5)]
                           for th in np.linspace(-180, 180, 49)[:-1]], 0.03))
    # medallion plate, setting ring and faceted gem
    plate = [(463, 686), (480, 669), (517, 663), (555, 665), (588, 680), (590, 728),
             (563, 757), (492, 759), (470, 738)]
    yp = -1.74
    pl = slab('MedallionPlate', plate, yp, 0.20, MATS['gold'], 0.035, 2)
    part(pl, 'Waist', ('rigid', 'LowerTorso'), 'gold')
    c = W(524, 713, yp - 0.05)

    def ring_fn(th, z, off):
        a = math.radians(th)
        r = 0.37 + off
        return c + Vector((math.cos(a) * r, -(z), math.sin(a) * r))
    ring = closed_profile_band('MedallionRing', [(0.0, -0.07), (0.07, -0.01), (0.07, 0.07),
                                                  (0.0, 0.10), (-0.08, 0.07), (-0.08, -0.07)],
                               MATS['gold'], ring_fn, n=20, bevel_w=0.0)
    part(ring, 'Waist', ('rigid', 'LowerTorso'), 'gold')
    gc = c + Vector((0, 0.02, 0))
    rg = 0.30
    base_ring = [gc + Vector((math.cos(a) * rg, 0.0, math.sin(a) * rg))
                 for a in np.linspace(0, 2 * math.pi, 11)[:-1] + math.pi / 10]
    apex = gc + Vector((0, -0.15, 0))
    back = gc + Vector((0, 0.10, 0))
    verts = base_ring + [apex, back]
    faces = [(i, (i + 1) % 10, 10) for i in range(10)] + [((i + 1) % 10, i, 11) for i in range(10)]
    gem = mesh_obj('Gem', verts, faces, MATS['gem'])
    recalc_normals(gem)
    flat(gem)
    part(gem, 'Waist', ('rigid', 'LowerTorso'), 'gem')


# ================================================================= kilt
KILT_TOP = 5.62
KILT_A = [(0.0, 1.86), (0.42, 2.14), (0.85, 2.38), (1.28, 2.58), (1.71, 2.70), (2.14, 2.80),
          (2.60, 2.84), (9.0, 2.84)]
KILT_B = [(0.0, 1.58), (0.42, 1.74), (0.85, 1.88), (1.28, 1.98), (1.71, 2.06), (2.14, 2.10),
          (9.0, 2.12)]
KILT_P = 2.5
KILT_YAW = math.radians(-12.0)


def kilt_ab(z):
    d = max(0.0, KILT_TOP - z)
    return row_lerp(KILT_A, d), row_lerp(KILT_B, d)


def kilt_local_to_world(x, y, z):
    c, s = math.cos(KILT_YAW), math.sin(KILT_YAW)
    return Vector((x * c - y * s, x * s + y * c + 0.05, z))


def kilt_world_to_local(p):
    c, s = math.cos(-KILT_YAW), math.sin(-KILT_YAW)
    x, y = p.x, p.y - 0.05
    return x * c - y * s, x * s + y * c, p.z


def kilt_pt(th, z, off=0.0):
    a, b = kilt_ab(z)
    t = math.radians(th)
    s, c = math.sin(t), math.cos(t)
    x = (a + off) * math.copysign(abs(s) ** (2 / KILT_P), s)
    y = -(b + off) * math.copysign(abs(c) ** (2 / KILT_P), c)
    return kilt_local_to_world(x, y, z)


def kilt_F(p, off):
    x, y, z = kilt_world_to_local(p)
    a, b = kilt_ab(z)
    return abs(x / (a + off)) ** KILT_P + abs(y / (b + off)) ** KILT_P - 1.0


def kilt_hit(u, v, off):
    """(theta_deg, z) where the camera ray through (u, v) meets the kilt proxy
    (offset outward by off). Grazing rays past the silhouette clamp to it."""
    d = WR(u, v)
    ts = np.linspace(10.0, 40.0, 601)
    prev = None
    best = None
    hit = None
    for t in ts:
        p = CAM_LOC + d * float(t)
        f = kilt_F(p, off)
        if best is None or f < best[0]:
            best = (f, float(t))
        if prev is not None and prev > 0 >= f:
            lo, hi = float(t) - float(ts[1] - ts[0]), float(t)
            for _ in range(30):
                mid = (lo + hi) / 2
                if kilt_F(CAM_LOC + d * mid, off) > 0:
                    lo = mid
                else:
                    hi = mid
            hit = CAM_LOC + d * hi
            break
        prev = f
    if hit is None:
        hit = CAM_LOC + d * best[1]
    x, y, z = kilt_world_to_local(hit)
    a, b = kilt_ab(z)
    sx = max(-1.0, min(1.0, x / (a + off)))
    sy = max(-1.0, min(1.0, -y / (b + off)))
    ss = math.copysign(abs(sx) ** (KILT_P / 2), sx)
    cc = math.copysign(abs(sy) ** (KILT_P / 2), sy)
    return math.degrees(math.atan2(ss, cc)), z


def point_in_poly(q, poly):
    x, y = q
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def cdt_panel(name, poly_tz, off, thick, mat, spacing=0.21, fn=None, bevel_w=0.022):
    """Mesh a (theta_deg, z) outline on the kilt proxy: constrained Delaunay in
    an isotropic (arc, z) plane with interior points, then solidify inward."""
    from mathutils.geometry import delaunay_2d_cdt
    R = 2.3
    pts2 = [Vector((math.radians(t) * R, z)) for t, z in poly_tz]
    n = len(pts2)
    poly2 = [(p.x, p.y) for p in pts2]
    xs = [p.x for p in pts2]
    zs = [p.y for p in pts2]
    inner = []
    for gx in np.arange(min(xs) + spacing / 2, max(xs), spacing):
        for gz in np.arange(min(zs) + spacing / 2, max(zs), spacing):
            q = (float(gx), float(gz))
            if point_in_poly(q, poly2) and \
                    min((Vector(q) - p).length for p in pts2) > spacing * 0.45:
                inner.append(Vector(q))
    allp = pts2 + inner
    edges = [(i, (i + 1) % n) for i in range(n)]
    vout, eout, fout, _, _, _ = delaunay_2d_cdt(allp, edges, [list(range(n))], 1, 1e-6)
    verts = []
    for q in vout:
        th = math.degrees(q.x / R)
        verts.append(fn(th, q.y, off) if fn else kilt_pt(th, q.y, off))
    o = mesh_obj(name, verts, [tuple(f) for f in fout], mat)
    recalc_normals(o)
    me = o.data
    score = 0
    for pgn in me.polygons:
        c = pgn.center
        score += 1 if pgn.normal.dot(Vector((c.x, c.y - 0.05, 0))) > 0 else -1
    if score < 0:
        recalc_normals(o, inside=True)
    sol = o.modifiers.new('solid', 'SOLIDIFY')
    sol.thickness = thick
    sol.offset = -1.0
    sol.use_even_offset = False
    apply_mods(o)
    if bevel_w:
        bevel(o, bevel_w, 1, 30)
    flat(o)
    return o


def torn(poly_tz, i0, i1, depth=0.22, width=0.30, seed=1):
    """Replace the outline stretch i0..i1 (along a hem) with saw teeth."""
    rnd = random.Random(seed)
    a, b = poly_tz[i0], poly_tz[i1]
    R = 2.3
    L = math.hypot(math.radians(b[0] - a[0]) * R, b[1] - a[1])
    n = max(2, int(L / width))
    teeth = []
    for k in range(1, 2 * n):
        t = k / (2 * n)
        th = a[0] + (b[0] - a[0]) * t
        z = a[1] + (b[1] - a[1]) * t
        if k % 2 == 1:
            z -= depth * rnd.uniform(0.55, 1.35)
        else:
            z += depth * rnd.uniform(0.0, 0.25)
        teeth.append((th, z))
    return poly_tz[:i0 + 1] + teeth + poly_tz[i1:]


KILT_LAYERS = dict(skirt=0.00, inner=0.035, strip=0.07, outer=0.09, border=0.115,
                   apron_gold=0.075, apron=0.095)


def kilt_trace(name, poly_uv, layer, mat_key, weight, torn_edges=(), thick=0.07,
               bevel_w=0.022, seed=3):
    off = KILT_LAYERS[layer]
    tz = [kilt_hit(u, v, off) for u, v in poly_uv]
    for (i0, i1, dep, wid) in sorted(torn_edges, key=lambda e: -e[0]):
        tz = torn(tz, i0, i1, dep, wid, seed)
    o = cdt_panel(name, tz, off, thick, MATS[mat_key], bevel_w=bevel_w)
    part(o, 'Waist', weight, mat_key)
    return o


def build_kilt():
    kw = ('kilt',)
    # base cream skirt, all the way round, with a torn hem
    hem = []
    for th in np.linspace(-180, 180, 73):
        a = abs(th)
        if a < 30:
            z = 3.05
        elif a < 60:
            z = 3.05 + (a - 30) / 30 * 0.68
        elif a < 115:
            z = 3.73 - (a - 60) / 55 * 0.08
        else:
            z = 3.65 - (a - 115) / 65 * 0.25
        hem.append((th, z))
    rnd = random.Random(7)
    teeth = []
    for i in range(len(hem) - 1, 0, -1):
        (t0, z0), (t1, z1) = hem[i], hem[i - 1]
        teeth.append((t0, z0))
        teeth.append(((t0 + t1) / 2 + rnd.uniform(-1, 1),
                      (z0 + z1) / 2 - rnd.uniform(0.12, 0.30)))
    poly = [(-180, KILT_TOP), (180, KILT_TOP)] + teeth + [(-180, hem[0][1])]
    o = cdt_panel('KiltSkirt', poly, KILT_LAYERS['skirt'], 0.07, MATS['bandage'])
    part(o, 'Waist', kw, 'bandage')
    # --- viewer-left (character's right) ---------------------------------
    kilt_trace('KiltOuterR', [(333, 757), (447, 756), (441, 766), (405, 836), (293, 916),
                              (296, 884), (308, 840), (320, 800)], 'outer', 'blue', kw)
    kilt_trace('KiltBorderR', [(446, 756), (457, 764), (411, 851), (297, 934), (291, 914),
                               (404, 835)], 'border', 'gold', kw)
    kilt_trace('KiltInnerR', [(402, 772), (452, 768), (448, 1000), (437, 1004), (386, 972),
                              (390, 880)], 'inner', 'blue', kw)
    kilt_trace('KiltInnerHemR', [(383, 966), (447, 998), (445, 1011), (380, 978)], 'strip',
               'gold', kw)
    kilt_trace('KiltStripR', [(440, 759), (474, 759), (471, 870), (466, 1000), (461, 1044),
                              (447, 1052), (436, 1030), (432, 950)], 'strip', 'bandage', kw)
    # --- centre apron: gold backing (trims + chevron), blue panel on top -----
    kilt_trace('ApronGold', [(470, 758), (572, 758), (572, 950), (521, 1053), (470, 950)],
               'apron_gold', 'gold', ('chain', 'apron'), thick=0.06)
    kilt_trace('ApronBlue', [(480, 758), (562, 758), (562, 946), (521, 1022), (480, 946)],
               'apron', 'blue', ('chain', 'apron'), thick=0.05, bevel_w=0.015)
    kilt_trace('UnderApron', [(478, 990), (564, 990), (562, 1060), (556, 1100), (548, 1090),
                              (541, 1136), (531, 1105), (518, 1141), (507, 1102), (494, 1118),
                              (486, 1070)], 'inner', 'bandage', ('chain', 'apron'))
    # --- viewer-right (character's left) ----------------------------------
    kilt_trace('KiltStripL', [(566, 759), (605, 758), (606, 870), (604, 1000), (600, 1108),
                              (592, 1100), (582, 1125), (571, 1104), (561, 1120), (557, 1030),
                              (561, 900)], 'strip', 'bandage', kw)
    kilt_trace('KiltInnerL', [(600, 765), (626, 760), (663, 935), (666, 982), (611, 1002),
                              (604, 900)], 'inner', 'blue', kw)
    kilt_trace('KiltInnerHemL', [(606, 996), (665, 976), (668, 988), (612, 1009)], 'strip',
               'gold', kw)
    kilt_trace('KiltOuterL', [(628, 746), (765, 749), (781, 880), (800, 916), (657, 832),
                              (637, 790)], 'outer', 'blue', kw)
    kilt_trace('KiltBorderL', [(613, 747), (628, 746), (658, 826), (801, 911), (803, 926),
                               (651, 844), (611, 752)], 'border', 'gold', kw)

    # --- back tail: hangs behind, seen between the legs -------------------
    # back tail: hangs from inside the rear of the skirt, seen between the
    # legs; traced from the reference (tip at 624, 1146) on a plane behind the
    # thighs, its top tucked up inside the skirt
    tail = [(588, 930), (672, 930), (668, 1000), (660, 1062), (646, 1112), (624, 1148),
            (606, 1110), (596, 1052), (590, 1000)]
    o = slab('KiltBackTail', tail, 1.15, 0.08, MATS['blue'], 0.02, 1, normal=(0, -1, -0.25))
    part(o, 'Waist', ('chain', 'back'), 'blue')
    CLEAR.append(('kilt', [[kilt_pt(th, z, -0.02) for z in np.linspace(3.2, KILT_TOP, 8)]
                           for th in np.linspace(-180, 180, 49)[:-1]], 0.04))


# ================================================================= staff
STAFF_FOOT = W(218.4, 1340, -2.0)
STAFF_FOOT.z = 0.0
STAFF_GRIP = W(173.3, 610, -2.55)          # staff axis point inside the right fist
STAFF_DIR = (STAFF_GRIP - STAFF_FOOT).normalized()
STAFF_W = 0.44                           # square section, seen corner-on (~40 deg)
STAFF_ROLL = math.radians(40.0)


def staff_t_at_row(v):
    """Distance along the staff axis whose image row is v (bisection)."""
    lo, hi = 0.0, 14.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if P2(STAFF_FOOT + STAFF_DIR * mid)[1] > v:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def staff_plane_point(u, v):
    """Unproject (u, v) onto the plane holding the staff axis and world X (the
    crook curls in that plane, facing the camera)."""
    n = STAFF_DIR.cross(Vector((1, 0, 0))).normalized()
    d = WR(u, v)
    t = (STAFF_FOOT - CAM_LOC).dot(n) / d.dot(n)
    return CAM_LOC + d * t


def square_section(w, cham=0.22):
    """Octagon: a square of side w with chamfered corners (fraction cham)."""
    h = w / 2
    c = w * cham
    return [(h, -h + c), (h, h - c), (h - c, h), (-h + c, h), (-h, h - c), (-h, -h + c),
            (-h + c, -h), (h - c, -h)]


def sweep_rings(pts, section, roll=0.0, up=Vector((1, 0, 0))):
    """Mitred rings of `section` along pts (bisector frames, constant width)."""
    rings = []
    n = len(pts)
    for i, p in enumerate(pts):
        t0 = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        u = (up - t0 * t0.dot(up)).normalized()
        w = t0.cross(u)
        cr, sr = math.cos(roll), math.sin(roll)
        u2, w2 = u * cr + w * sr, -u * sr + w * cr
        k, bn = 1.0, None
        if 0 < i < n - 1:
            a_ = (pts[i] - pts[i - 1]).normalized()
            b_ = (pts[i + 1] - pts[i]).normalized()
            k = 1.0 / max(0.5, math.cos(a_.angle(b_) / 2))
            d = b_ - a_
            if d.length > 1e-6:
                bn = (d - t0 * t0.dot(d)).normalized()
        ring = []
        for x, y in section:
            q = u2 * x + w2 * y
            if bn is not None:
                q = q + bn * (q.dot(bn) * (k - 1.0))
            ring.append(p + q)
        rings.append(ring)
    return rings


def sweep(name, pts, section, mat, roll=0.0, up=Vector((1, 0, 0)), caps=True):
    """Loft `section` (2D, in the plane normal to the path) along pts with
    mitred rings (bisector frames) and a fixed roll about the path."""
    rings = []
    n = len(pts)
    for i, p in enumerate(pts):
        t0 = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        u = (up - t0 * t0.dot(up)).normalized()
        w = t0.cross(u)
        cr, sr = math.cos(roll), math.sin(roll)
        u2, w2 = u * cr + w * sr, -u * sr + w * cr
        # mitre scale: keep the section width constant through bends
        k = 1.0
        if 0 < i < n - 1:
            a = (pts[i] - pts[i - 1]).normalized()
            b = (pts[i + 1] - pts[i]).normalized()
            k = 1.0 / max(0.5, math.cos(a.angle(b) / 2))
        ring = []
        for x, y in section:
            q = u2 * x + w2 * y
            # stretch only the component in the bend plane
            if k != 1.0:
                bend_n = (b - a)
                if bend_n.length > 1e-6:
                    bn = (bend_n - t0 * t0.dot(bend_n)).normalized()
                    q = q + bn * (q.dot(bn) * (k - 1.0))
            ring.append(p + q)
        rings.append(ring)
    return loft(name, rings, mat, closed=True, cap_start=caps, cap_end=caps)


STAFF_BANDS = [  # image rows along the shaft, top to bottom; the crook is separate
    (296, 'G'), (345.5, 'B'), (414, 'G'), (465.5, 'B'), (740.5, 'G'), (798.5, 'B'),
    (940.5, 'G'), (997, 'B'), (1228, 'G')]
# crook centre line traced from the reference (px): a gold S-bend leaving the
# shaft up and to the left, the arc over the top, then down to the tip
HOOK_C = [(154, 300), (150, 284), (139, 262), (120, 238), (100, 212), (86, 180), (82, 145),
          (89, 112), (108, 92), (140, 79), (180, 77), (216, 88), (243, 113), (257, 147),
          (261, 186), (261, 226), (260, 262), (260, 272)]
# band boundaries along the crook (reference px), from the shaft outward:
# G | B | G | B | G | B | G
HOOK_BOUNDS = [(86, 176), (84, 122), (178, 77), (236, 104), (261, 184), (261, 228)]
HOOK_COLS = 'GBGBGBG'


def build_staff():
    gold, blue = MATS['gold'], MATS['blue']
    col = {'G': gold, 'B': blue}
    sec = square_section(STAFF_W)
    # shaft bands
    tops = [staff_t_at_row(v) for v, _ in STAFF_BANDS]
    edges = [staff_t_at_row(290)] + tops
    for i, (v, k) in enumerate(STAFF_BANDS):
        t_hi = edges[i]
        t_lo = edges[i + 1]
        a = STAFF_FOOT + STAFF_DIR * (t_lo + 0.006)
        b = STAFF_FOOT + STAFF_DIR * (t_hi - 0.006)
        o = sweep(f'Shaft{i}', [a, b], sec, col[k], STAFF_ROLL)
        bevel(o, 0.018, 1, 30)
        flat(o)
        part(o, 'Staff', ('rigid', 'Staff'), 'gold' if k == 'G' else 'blue')
    # foot block: square frustum, same roll, engraved later in paint
    t_top = staff_t_at_row(1228)
    foot_pts = [STAFF_FOOT + STAFF_DIR * t for t in (0.0, t_top)]
    rings = []
    for p, wdt in zip(foot_pts, (0.74, 0.54)):
        u = (Vector((1, 0, 0)) - STAFF_DIR * STAFF_DIR.x).normalized()
        w = STAFF_DIR.cross(u)
        cr, sr = math.cos(STAFF_ROLL), math.sin(STAFF_ROLL)
        u2, w2 = u * cr + w * sr, -u * sr + w * cr
        rings.append([p + u2 * x + w2 * y for x, y in square_section(wdt, 0.10)])
    o = loft('StaffFoot', rings, gold)
    bevel(o, 0.03, 1, 30)
    flat(o)
    part(o, 'Staff', ('rigid', 'Staff'), 'gold')
    collar = sweep('StaffFootCollar', [foot_pts[1] - STAFF_DIR * 0.02, foot_pts[1] + STAFF_DIR * 0.07],
                   square_section(0.50, 0.15), gold, STAFF_ROLL)
    bevel(collar, 0.015, 1, 30)
    flat(collar)
    part(collar, 'Staff', ('rigid', 'Staff'), 'gold')
    # the crook: a polygonal arc in the camera-facing plane through the axis,
    # swept as one mitred tube and split into its colour bands
    guide = [staff_plane_point(u, v) for u, v in HOOK_C]
    guide[0] = STAFF_FOOT + STAFF_DIR * staff_t_at_row(296)
    # coarse resampling keeps the crook as chunky straight facets, like the
    # reference's blocky bands, rather than a smooth tube
    hook = catmull(guide, 0.30)
    upv = STAFF_DIR.cross(Vector((1, 0, 0))).normalized()
    rings = sweep_rings(hook, square_section(STAFF_W * 1.18), STAFF_ROLL, upv)
    cuts = [0]
    for u, v in HOOK_BOUNDS:
        q = staff_plane_point(u, v)
        cuts.append(min(range(len(hook)), key=lambda i: (hook[i] - q).length))
    cuts.append(len(hook) - 1)
    for i in range(len(cuts) - 1):
        k = HOOK_COLS[i]
        seg = loft(f'Crook{i}', rings[cuts[i]:cuts[i + 1] + 1], col[k])
        bevel(seg, 0.014, 1, 30)
        flat(seg)
        part(seg, 'Staff', ('rigid', 'Staff'), 'gold' if k == 'G' else 'blue')


# ================================================================= bands
def limb_ring(name, a, b, r0, r1, mat, sides=12, roll=0.0, bevel_w=0.03, inner=0.12):
    """Thick beveled ring around the limb axis a->b (tapered r0 -> r1)."""
    ax = (Vector(b) - Vector(a))
    outer_a = ring_pts(a, ax, r0, sides, roll)
    outer_b = ring_pts(b, ax, r1, sides, roll)
    inner_b = ring_pts(b, ax, r1 - inner, sides, roll)
    inner_a = ring_pts(a, ax, r0 - inner, sides, roll)
    rings = [outer_a, outer_b, inner_b, inner_a]
    verts = [p for r in rings for p in r]
    faces = []
    for q in range(4):
        q2 = (q + 1) % 4
        for i in range(sides):
            j = (i + 1) % sides
            faces.append((q * sides + i, q * sides + j, q2 * sides + j, q2 * sides + i))
    o = mesh_obj(name, verts, faces, mat)
    recalc_normals(o)
    if bevel_w:
        bevel(o, bevel_w, 1, 30)
    flat(o)
    return o


def build_bands():
    gold, blue = MATS['gold'], MATS['blue']
    # ankle bands (plain gold rings above each foot)
    for side, host in (('R', 'RightLowerLeg'), ('L', 'LeftLowerLeg')):
        kn, an = jv('knee_' + side), jv('ankle_' + side)
        ax = (kn - an).normalized()
        c = an + ax * (0.46 if side == 'R' else 0.14)
        rb = 1.06 if side == 'R' else 1.02
        o = limb_ring(f'AnkleBand{side}', c - ax * 0.26, c + ax * 0.26, rb, rb, gold, 14,
                      bevel_w=0.035, inner=0.22)
        part(o, 'Waist', ('rigid', host), 'gold')
    # left forearm bracer: rims plus alternating gold/blue panels
    el, wr = jv('elbow_L'), jv('wrist_L')
    ax = (wr - el).normalized()
    top = W(930, 655, -0.10)
    t0 = (top - el).dot(ax)
    L = 1.90
    p0 = el + ax * t0
    p1 = el + ax * (t0 + L)
    r0, r1 = 1.14, 1.16
    rim_h = 0.30
    o = limb_ring('BracerTopRim', p0, p0 + ax * rim_h, r0, r0 - 0.01, gold, 16, bevel_w=0.035,
                  inner=0.25)
    part(o, 'Waist', ('rigid', 'LeftLowerArm'), 'gold')
    o = limb_ring('BracerBotRim', p1 - ax * rim_h, p1, r1 + 0.01, r1, gold, 16, bevel_w=0.035,
                  inner=0.25)
    part(o, 'Waist', ('rigid', 'LeftLowerArm'), 'gold')
    n = 12
    for i in range(n):
        a0 = (i + 0.04) * 2 * math.pi / n
        a1 = (i + 0.96) * 2 * math.pi / n
        k = 'B' if i % 2 == 0 else 'G'
        q0, q1 = p0 + ax * (rim_h + 0.02), p1 - ax * (rim_h + 0.02)
        rr0, rr1 = r0 - 0.07, r1 - 0.07
        ref = Vector((0, -1, 0))
        pts = []
        for (c, rr) in ((q0, rr0), (q1, rr1)):
            u = (ref - ax * ax.dot(ref)).normalized()
            w = ax.cross(u)
            for a in (a0, (a0 + a1) / 2, a1):
                pts.append(c + (u * math.cos(a) + w * math.sin(a)) * rr)
        inner_pts = [c for c in pts]
        th = 0.14
        outer = pts
        innerp = []
        for j, pp in enumerate(pts):
            c = q0 if j < 3 else q1
            d = (pp - c)
            d = d - ax * ax.dot(d)
            innerp.append(pp - d.normalized() * th)
        verts = outer + innerp
        faces = [(0, 1, 4, 3), (1, 2, 5, 4), (6, 9, 10, 7), (7, 10, 11, 8), (0, 3, 9, 6),
                 (2, 8, 11, 5), (0, 6, 7, 1), (1, 7, 8, 2), (3, 4, 10, 9), (4, 5, 11, 10)]
        o = mesh_obj(f'BracerPanel{i}', verts, faces, blue if k == 'B' else gold)
        recalc_normals(o)
        bevel(o, 0.025, 1, 30)
        flat(o)
        part(o, 'Waist', ('rigid', 'LeftLowerArm'), 'blue' if k == 'B' else 'gold')
    # right wrist cuff: a thick gold ring seen nearly end-on, blue inlays outside
    el, wr = jv('elbow_R'), jv('wrist_R')
    ax = (wr - el).normalized()
    # fitted round the forearm just behind the wrist (not round the fist)
    c1 = wr - ax * 0.04
    c0 = wr - ax * 0.92
    o = limb_ring('CuffR', c0, c1, 1.00, 1.14, gold, 16, bevel_w=0.05, inner=0.36)
    part(o, 'Waist', ('rigid', 'RightLowerArm'), 'gold')
    for i, a in enumerate((140, 180, 220)):
        ang = math.radians(a)
        ref = Vector((0, 0, 1))
        u = (ref - ax * ax.dot(ref)).normalized()
        w = ax.cross(u)
        dirv = u * math.cos(ang) + w * math.sin(ang)
        c = (c0 + c1) / 2 + dirv * 1.09
        o = chamfer_box(f'CuffInlay{i}', c, (0.62, 0.30, 0.05), blue, 0.015,
                        rot=basis_from(ax, dirv))
        part(o, 'Waist', ('rigid', 'RightLowerArm'), 'blue')


# ================================================================= hands
def seg_box(name, a, b, width, thick, mat, up, bevel_w=0.07):
    """Chamfered block spanning a->b; `up` sets the block's thickness axis."""
    ax = Vector(b) - Vector(a)
    L = ax.length
    rot = basis_from(ax, up)
    return chamfer_box(name, (Vector(a) + Vector(b)) / 2, (L + thick * 0.35, width, thick), mat,
                       bevel_w, 1, rot=rot)


FINGERS = ('Index', 'Middle', 'Ring', 'Pinky')
HAND_JOINTS = {}      # side -> finger -> joint points (bones are built from these)
FOOT_JOINTS = {}      # side -> (ankle, toe root, toe tip)
GRIP = {}             # solved right-hand grip frame (see solve_right_grip)


def solve_right_grip():
    """Natural hammer grip on the staff, solved before anything is sculpted.

    The staff runs through the centre of the finger tunnel (STAFF_GRIP). The
    hand continues straight out of the forearm (no bent wrist): the palm sits
    on the outer side of the shaft facing the body, the four fingers curl
    round the front of the shaft and the thumb closes over the index finger
    from the inner side. The wrist joint is therefore derived from the grip
    and the elbow (iterated so forearm and metacarpals stay collinear), and
    written back into JOINT['wrist_R'] so the body and rig use it.
    """
    c, D = STAFF_GRIP.copy(), STAFF_DIR.copy()
    el = jv('elbow_R')
    m = (c - el).normalized()
    for _ in range(8):
        n = D.cross(m)
        if n.x < 0:
            n = -n
        n.normalize()
        d = m.cross(n)
        if d.dot(D) < 0:
            d = -d
        wr = c - m * GRIP_PALM_LEN - n * GRIP_PALM_OFF - d * 0.10
        m = (wr - el).normalized()
    n = D.cross(m)
    if n.x < 0:
        n = -n
    n.normalize()
    d = m.cross(n)
    if d.dot(D) < 0:
        d = -d
    m2 = (m - D * D.dot(m)).normalized()          # forward, square to the shaft
    n2 = D.cross(m2)
    if n2.x < 0:
        n2 = -n2
    GRIP.update(c=c, D=D, m=m, n=n, d=d, m2=m2, n2=n2.normalized(), wrist=wr, elbow=el)
    JOINT['wrist_R'] = wr.copy()


GRIP_PALM_LEN = 1.02      # tunnel centre back to the wrist, along the forearm
GRIP_PALM_OFF = 0.50      # palm centre line sits this far outboard of the shaft
GRIP_RHO = 0.465          # nominal finger centre-line radius round the shaft axis
SHAFT_CORNER_R = math.hypot(0.22, 0.22 - 0.44 * 0.22)   # square shaft, chamfered corner
FINGER_R = 0.195          # finger half-thickness (finger inner surface ~ rho - r)


def octa_section(rw, rh, sides=8, cham=0.42):
    """Chunky finger cross-section: a rectangle rw x rh with chamfered corners."""
    cw, ch = rw * (1 - cham), rh * (1 - cham)
    return [(rw, -ch), (rw, ch), (cw, rh), (-cw, rh), (-rw, ch), (-rw, -ch), (-cw, -rh),
            (cw, -rh)]


def finger_tube(name, pts, radii, up_fn, mat, sides=8, cap_scale=0.55):
    """One continuous faceted finger along `pts` (dense path), with per-point
    radii (rw, rh) and a per-point 'up' vector (the finger's width axis).
    Both ends are closed by a shrunken cap ring so the tip reads rounded."""
    rings = []
    n = len(pts)
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        up = up_fn(i)
        u = (up - t * t.dot(up)).normalized()
        w = t.cross(u)
        rw, rh = radii[i]
        rings.append([p + u * x + w * y for x, y in octa_section(rw, rh, sides)])
    # rounded ends
    t_end = (pts[-1] - pts[-2]).normalized()
    t_beg = (pts[1] - pts[0]).normalized()
    tip = [pts[-1] + t_end * radii[-1][1] * 0.55 + (q - pts[-1]) * cap_scale for q in rings[-1]]
    base = [pts[0] - t_beg * radii[0][1] * 0.40 + (q - pts[0]) * cap_scale for q in rings[0]]
    o = loft(name, [base] + rings + [tip], mat)
    flat(o)
    return o


def preset_weights(o, fn):
    """Assign weights now: fn(world_point) -> {bone: weight}."""
    for v in o.data.vertices:
        for g, w in fn(o.matrix_world @ v.co).items():
            if w <= 1e-5:
                continue
            vg = o.vertex_groups.get(g) or o.vertex_groups.new(name=g)
            vg.add([v.index], w, 'ADD')


def chain_weights(joints, bones, blend=0.07):
    """Weights along a joint chain [j0, j1, ..., jk] for bones [parent, b1..bk]:
    a point is projected on the polyline; across each joint the weight blends
    over +-blend studs so the finger bends without tearing."""
    segs = list(zip(joints[:-1], joints[1:]))
    lens = [(b - a).length for a, b in segs]
    cum = [0.0]
    for L_ in lens:
        cum.append(cum[-1] + L_)

    def fn(p):
        best = None
        for i, (a, b) in enumerate(segs):
            ab = b - a
            t = max(0.0, min(1.0, (p - a).dot(ab) / max(1e-9, ab.length_squared)))
            dist = (a + ab * t - p).length
            s = cum[i] + t * lens[i]
            if best is None or dist < best[0]:
                best = (dist, s)
        s = best[1]
        w = {}
        # bones[0] owns everything before joint 0 (the palm side)
        edges = cum[:-1]                   # start of each segment -> bone i+1
        own = 0
        for i, e in enumerate(edges):
            if s >= e:
                own = i + 1
        w[bones[own]] = 1.0
        # blend with the previous bone near the joint at edges[own-1]
        if own >= 1:
            e = edges[own - 1]
            k = smoothstep(-blend, blend, s - e)
            w = {}
            w[bones[own]] = w.get(bones[own], 0.0) + k
            w[bones[own - 1]] = w.get(bones[own - 1], 0.0) + (1 - k)
        return w
    return fn


def build_hand_R():
    """Right fist closed round the staff (see solve_right_grip)."""
    skin = MATS['skin']
    G = GRIP
    c, D, m, n, d, m2, n2 = G['c'], G['D'], G['m'], G['n'], G['d'], G['m2'], G['n2']
    wr = G['wrist']

    def L(a, b_, h):          # palm frame: along forearm, inward, up
        return c + m * a + n * b_ + d * h

    # --- palm: one loft from the wrist to the knuckle line --------------
    secs = [  # (along m, centre n, half-width along d (lo, hi), half-thickness)
        (-GRIP_PALM_LEN - 0.10, -GRIP_PALM_OFF, (-0.50, 0.40), 0.26),
        (-0.80, -GRIP_PALM_OFF, (-0.62, 0.50), 0.27),
        (-0.45, -0.50, (-0.86, 0.60), 0.25),
        (-0.16, -0.50, (-0.98, 0.64), 0.23),
        (0.00, -0.46, (-0.96, 0.62), 0.20)]
    rings = []
    for a, bn, (lo, hi), th in secs:
        ring = []
        for k in range(12):
            ang = 2 * math.pi * (k + 0.5) / 12
            x, y = math.cos(ang), math.sin(ang)
            hh = (hi if y > 0 else -lo) * (abs(y) ** 0.55)
            ring.append(L(a, bn + math.copysign(abs(x) ** 0.7, x) * th,
                          math.copysign(hh, y) + (hi + lo) * 0.0))
        rings.append(ring)
    palm = loft('RPalm', rings, skin)
    flat(palm)
    j_mcp = {}
    # --- fingers: arcs round the shaft in planes square to it ------------
    SPEC = {  # height along shaft, start angle, forward offset, radius scale, rho
        'Index': (0.44, -112, 0.0, 1.00, GRIP_RHO),
        'Middle': (0.03, -103, 0.0, 1.04, GRIP_RHO),
        'Ring': (-0.38, -95, 0.0, 0.98, GRIP_RHO),
        'Pinky': (-0.73, -86, 0.0, 0.84, GRIP_RHO)}
    JOINT_ANG = (-40, 28, 92)
    for fname, (h, a0, fo, rs, rho) in SPEC.items():
        j0 = JOINT_ANG
        angs = [a0, (a0 + j0[0]) / 2, j0[0], (j0[0] + j0[1]) / 2, j0[1], (j0[1] + j0[2]) / 2,
                j0[2]]
        pts, radii = [], []
        for a in angs:
            # knuckles slightly fatter than the shafts between them
            bump = max(math.exp(-((a - ja) / 9.0) ** 2) for ja in (a0 + 4,) + JOINT_ANG[:2])
            taper = 1.0 - 0.14 * (a - a0) / (JOINT_ANG[-1] - a0)
            rw_, rh_ = (0.215 * rs * taper * (1 + 0.08 * bump),
                        0.195 * rs * taper * (1 + 0.08 * bump))
            # centre line = shaft corner radius + contact allowance + the
            # finger's own half-thickness, so every finger's inner face lies
            # on the shaft (chord sag between samples ~0.02 is allowed for)
            r_ = SHAFT_CORNER_R + 0.022 + rh_
            p = (c + m2 * (math.cos(math.radians(a)) * r_ + fo)
                 + n2 * (math.sin(math.radians(a)) * r_) + D * h)
            pts.append(p)
            radii.append((rw_, rh_))
        o = finger_tube(f'R{fname}', pts, radii, lambda i: D, skin)
        joints = []
        for a in (a0 + 2, JOINT_ANG[0], JOINT_ANG[1], JOINT_ANG[2]):
            r_ = SHAFT_CORNER_R + 0.022 + 0.19 * rs
            joints.append(c + m2 * (math.cos(math.radians(a)) * r_ + fo) +
                          n2 * (math.sin(math.radians(a)) * r_) + D * h)
        HAND_JOINTS.setdefault('R', {})[fname] = joints
        preset_weights(o, chain_weights(joints, ['RightHand', f'Right{fname}1',
                                                  f'Right{fname}2', f'Right{fname}3']))
        part(o, 'Body', ('preset',), 'skin')
    # --- thumb: from the thenar behind the shaft, closing over the index ---
    tj = [L(-0.62, -0.36, 0.40), L(-0.54, 0.12, 0.64), L(-0.04, 0.68, 0.60),
          L(0.34, 0.64, 0.52)]
    path = [tj[0], tj[1], (tj[1] + tj[2]) / 2, tj[2], (tj[2] + tj[3]) / 2, tj[3]]
    radii = [(0.26, 0.23), (0.25, 0.22), (0.25, 0.22), (0.24, 0.21), (0.23, 0.20), (0.21, 0.19)]
    th = finger_tube('RThumb', path, radii, lambda i: d, skin)
    HAND_JOINTS['R']['Thumb'] = tj
    preset_weights(th, chain_weights(tj, ['RightHand', 'RightThumb1', 'RightThumb2',
                                          'RightThumb2']))
    part(th, 'Body', ('preset',), 'skin')
    # thenar pad fills the web between thumb and palm
    tp = rock('RThenar', L(-0.52, -0.22, 0.30), (0.30, 0.24, 0.28), subdiv=2, jitter=0.02)
    tp.data.materials.append(skin)
    flat(tp)
    preset_weights(tp, lambda p: {'RightHand': 0.7, 'RightThumb1': 0.3})
    part(tp, 'Body', ('preset',), 'skin')
    preset_weights(palm, lambda p: (lambda k: {'RightHand': k, 'RightLowerArm': 1 - k})(
        smoothstep(-0.10, 0.18, (p - wr).dot(m))))
    part(palm, 'Body', ('preset',), 'skin')


def build_hand_L():
    """Open, slightly clawed left hand: palm continuous with the wrist, four
    chunky fingers curling toward the palm, thumb set apart and forward."""
    skin = MATS['skin']
    first_part = len(PARTS)
    el, wr = jv('elbow_L'), jv('wrist_L')
    m = (wr - el).normalized()                       # down the forearm
    n = Vector((-0.55, 0.83, 0.0))                    # palm faces back and in
    n = (n - m * m.dot(n)).normalized()
    a_ = n.cross(m)                                   # index -> pinky, across
    if a_.x < 0:
        a_ = -a_

    def L(u, v, w):        # along forearm, index->pinky, palm-ward
        return wr + m * u + a_ * v + n * w

    PL = 0.86
    secs = [(-0.10, (-0.50, 0.40), 0.25), (0.25, (-0.66, 0.46), 0.25),
            (0.58, (-0.86, 0.50), 0.23), (PL, (-0.88, 0.50), 0.20)]
    rings = []
    for u, (lo, hi), th in secs:
        ring = []
        for k in range(12):
            ang = 2 * math.pi * (k + 0.5) / 12
            x, y = math.cos(ang), math.sin(ang)
            hh = (hi if y > 0 else -lo) * (abs(y) ** 0.55)
            ring.append(L(u, math.copysign(hh, y), math.copysign(abs(x) ** 0.7, x) * th))
        rings.append(ring)
    palm = loft('LPalm', rings, skin)
    flat(palm)
    preset_weights(palm, lambda p: (lambda k: {'LeftHand': k, 'LeftLowerArm': 1 - k})(
        smoothstep(-0.10, 0.18, (p - wr).dot(m))))
    part(palm, 'Body', ('preset',), 'skin')
    SPEC = {  # lateral offset, lengths, curl per joint (deg), spread (deg), radius scale
        'Index': (-0.66, (0.42, 0.34, 0.28), (22, 50, 40), -12, 1.00),
        'Middle': (-0.32, (0.46, 0.36, 0.28), (24, 52, 40), -5, 1.04),
        'Ring': (0.02, (0.42, 0.34, 0.26), (26, 52, 38), 2, 0.98),
        'Pinky': (0.32, (0.34, 0.28, 0.22), (28, 50, 36), 8, 0.84)}
    for fname, (lat, lens, curl, spread, rs) in SPEC.items():
        p = L(PL - 0.08, lat, 0.02)
        dirv = (Quaternion(n, math.radians(spread)) @ m).normalized()
        joints = [p.copy()]
        for L_, cdeg in zip(lens, curl):
            ax = dirv.cross(n).normalized()          # curling bends toward the palm
            dirv = (Quaternion(ax, -math.radians(cdeg)) @ dirv).normalized()
            if dirv.dot(n) < 0:                      # make sure we curl palm-ward
                dirv = (Quaternion(ax, math.radians(2 * cdeg)) @ dirv).normalized()
            p = p + dirv * L_
            joints.append(p.copy())
        path = [joints[0], (joints[0] + joints[1]) / 2, joints[1], (joints[1] + joints[2]) / 2,
                joints[2], (joints[2] + joints[3]) / 2, joints[3]]
        radii = [(0.17 * rs * (1 - 0.12 * i / 6), 0.205 * rs * (1 - 0.14 * i / 6))
                 for i in range(7)]
        o = finger_tube(f'L{fname}', path, radii, lambda i: a_, skin)
        HAND_JOINTS.setdefault('L', {})[fname] = joints
        preset_weights(o, chain_weights(joints, ['LeftHand', f'Left{fname}1', f'Left{fname}2',
                                                  f'Left{fname}3']))
        part(o, 'Body', ('preset',), 'skin')
    # thumb: from the thenar at the front of the palm, down, forward and in
    tj = [L(0.04, -0.62, 0.05), L(0.26, -1.16, 0.00), L(0.54, -1.60, 0.05),
          L(0.84, -1.78, 0.10)]
    path = [tj[0], tj[1], (tj[1] + tj[2]) / 2, tj[2], (tj[2] + tj[3]) / 2, tj[3]]
    radii = [(0.25, 0.22), (0.25, 0.22), (0.24, 0.21), (0.23, 0.20), (0.22, 0.19), (0.20, 0.18)]
    th = finger_tube('LThumb', path, radii, lambda i: n, skin)
    HAND_JOINTS['L']['Thumb'] = tj
    preset_weights(th, chain_weights(tj, ['LeftHand', 'LeftThumb1', 'LeftThumb2', 'LeftThumb2']))
    part(th, 'Body', ('preset',), 'skin')
    tp = rock('LThenar', L(0.30, -0.36, 0.14), (0.28, 0.26, 0.24), subdiv=2, jitter=0.02)
    tp.data.materials.append(skin)
    flat(tp)
    preset_weights(tp, lambda p: {'LeftHand': 0.7, 'LeftThumb1': 0.3})
    part(tp, 'Body', ('preset',), 'skin')
    # the reference's open hand is big (a brute's claw): scale the finished
    # hand about the wrist; joints scale with it so the bones still fit
    S = HAND_L_SCALE
    shift = Vector((0.0, 0.0, 0.0))       # hook for fitting; zero = measured hand as built
    for p in PARTS[first_part:]:
        for v in p['obj'].data.vertices:
            v.co = wr + (v.co - wr) * S + shift
    for f, js in HAND_JOINTS['L'].items():
        HAND_JOINTS['L'][f] = [wr + (j - wr) * S + shift for j in js]


HAND_L_SCALE = 1.0


# ================================================================= feet
FOOT_AXIS = {}
FOOT_WRAP_AXIS = {}


def build_feet():
    skin = MATS['skin']
    spec = {
        # side: toe-front centre (image px, depth), yaw of the foot (deg, 0 = -Y)
        'L': dict(front=(836, 1330, -3.02), yaw=8.0, host='LeftFoot', toes='LeftToes'),
        'R': dict(front=(282, 1290, -0.55), yaw=-42.0, host='RightFoot', toes='RightToes'),
    }
    for side, sp in spec.items():
        an = jv('ankle_' + side)
        tip = W(*sp['front'])
        yaw = math.radians(sp['yaw'])
        fwd = Vector((math.sin(yaw), -math.cos(yaw), 0))
        lat = Vector((math.cos(yaw), math.sin(yaw), 0))
        # foot body: heel under the ankle to the toe roots
        heel = Vector((an.x, an.y, 0.0)) - fwd * 0.55
        toe_root = Vector((tip.x, tip.y, 0.0)) - fwd * 0.62
        L = (toe_root - heel).length
        c = (heel + toe_root) / 2 + Vector((0, 0, 0.62))
        FOOT_AXIS[side] = (heel + Vector((0, 0, 0.55)) - fwd * 0.3,
                           toe_root + Vector((0, 0, 0.45)) + fwd * 0.2)
        fcen = (heel + toe_root) / 2
        FOOT_WRAP_AXIS[side] = (fcen + Vector((0, 0, 2.2)), fcen, fwd.copy())
        FOOT_JOINTS[side] = (an.copy(), toe_root + Vector((0, 0, 0.40)),
                             toe_root + Vector((0, 0, 0.36)) + fwd * 0.72)
        o = chamfer_box(f'Foot{side}', c + Vector((0, 0, -0.08)), (2.20, L + 0.2, 1.10), skin, 0.20,
                        1, rot=basis_from(lat, Vector((0, 0, 1))), taper=(0.90, 0.80))
        part(o, 'Body', ('rigid', sp['host']), 'skin')
        # four blocky toes: big toe on the inner side
        inner = -1 if side == 'L' else 1       # the inner side is toward the midline
        widths = [0.62, 0.60, 0.58, 0.50]
        offs = [-0.90, -0.29, 0.31, 0.87]
        for ti in range(4):
            w_ = widths[ti]
            hgt = [0.86, 0.84, 0.80, 0.70][ti]
            back = [0.04, 0.0, 0.06, 0.18][ti]
            base = toe_root + lat * (offs[ti] * (-inner)) + Vector((0, 0, hgt / 2))
            ctr = base + fwd * (0.36 - back)
            t = chamfer_box(f'Toe{side}{ti}', ctr, (w_, 0.92 - back, hgt), skin, 0.11,
                            1, rot=basis_from(lat, Vector((0, 0, 1))), taper=(0.94, 0.90))
            part(t, 'Body', ('rigid', sp['toes']), 'skin')


# ================================================================= bandages
_SKIN_BVH = {}


def skin_bvh():
    """BVH over every skin surface (body, palms, feet) for projecting wraps."""
    if 'bvh' in _SKIN_BVH:
        return _SKIN_BVH['bvh']
    verts, faces = [], []
    for p in PARTS:
        if p['mat'] != 'skin':
            continue
        o = p['obj']
        base = len(verts)
        mw = o.matrix_world
        verts += [mw @ v.co for v in o.data.vertices]
        faces += [[base + i for i in pg.vertices] for pg in o.data.polygons]
    _SKIN_BVH['bvh'] = BVHTree.FromPolygons(verts, faces, epsilon=0.0)
    return _SKIN_BVH['bvh']


def catmull(pts, ds=0.10):
    """Uniform Catmull-Rom through pts, resampled at ~ds spacing."""
    P = [Vector(p) for p in pts]
    if len(P) < 3:
        P = [P[0], P[0].lerp(P[-1], 0.5), P[-1]]
    ext = [P[0] + (P[0] - P[1])] + P + [P[-1] + (P[-1] - P[-2])]
    dense = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(12):
            t = k / 12
            t2, t3 = t * t, t * t * t
            dense.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                                (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    dense.append(P[-1])
    out = [dense[0]]
    acc = 0.0
    for a, b in zip(dense, dense[1:]):
        acc += (b - a).length
        if acc >= ds:
            out.append(b)
            acc = 0.0
    if (out[-1] - dense[-1]).length > ds * 0.3:
        out.append(dense[-1])
    return out


def project_path(pts, mode='nearest', axis=None, max_r=3.0, clamp_r=None, taut=True,
                 closed=False):
    """Snap path samples to the skin. 'nearest' uses closest point; 'axis' casts
    from the limb axis outward (robust near the armpits and crotch). With
    `taut`, axis-mode radii are relaxed upward so the strip bridges creases
    (between the pecs, under a deltoid) the way a pulled bandage does."""
    bvh = skin_bvh()
    out = []
    radial = []
    for p in pts:
        hit = None
        if mode == 'axis' and axis is not None:
            a, b = axis
            ab = (b - a)
            t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
            q = a + ab * t
            d = p - q
            d = d - ab.normalized() * d.dot(ab.normalized())
            if d.length > 1e-6:
                loc, nrm, idx, dist = bvh.ray_cast(q, d.normalized(), max_r)
                if loc is not None:
                    n = nrm if nrm.dot(d) > 0 else -nrm
                    if clamp_r is not None and dist > clamp_r:
                        # the ray ran on into a neighbouring mass (a deltoid,
                        # the chest): stop inside it so the strip tucks under
                        loc, n = q + d.normalized() * clamp_r, d.normalized()
                        dist = clamp_r
                    hit = (loc, n)
                    radial.append((len(out), q, d.normalized(), dist))
        if hit is None and mode == 'axis' and axis is not None:
            a, b_ = axis
            ab = (b_ - a)
            t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
            q = a + ab * t
            d = p - q
            d = d - ab.normalized() * d.dot(ab.normalized())
            if d.length > 1e-6:
                rr = clamp_r if clamp_r is not None else d.length
                hit = (q + d.normalized() * rr, d.normalized())
                radial.append((len(out), q, d.normalized(), rr))
        if hit is None:
            loc, nrm, idx, dist = bvh.find_nearest(p, 3.0)
            if loc is None:
                hit = (p, Vector((0, 0, 1)))
            else:
                n = nrm if nrm.dot(p - loc) >= 0 or (p - loc).length < 1e-5 else -nrm
                hit = (loc, n)
        out.append(hit)
    if taut and mode == 'axis' and len(radial) == len(out) and len(out) > 4:
        rs = [r[3] for r in radial]
        n_ = len(rs)
        for _ in range(10):
            new = rs[:]
            for i in range(n_):
                if not closed and (i == 0 or i == n_ - 1):
                    continue
                a_, b_ = rs[(i - 1) % n_], rs[(i + 1) % n_]
                new[i] = max(rs[i], 0.5 * (a_ + b_))
            rs = new
        out = [(q + d * r, out[i][1]) for (i, q, d, _), r in zip(radial, rs)]
    return out


def ribbon(name, samples, width, thick, off, mat, tear=(True, True), seed=0, widths=None,
           hang=None, across=4):
    """Clean flat strip over projected samples [(loc, normal)].

    The centre path, its normals and its width direction are all smoothed, and
    each cross-row is pushed out as a whole (never bent point by point) when
    the skin bulges under it, so strip edges stay straight like pulled linen.
    Ends can be torn into uneven points; `hang` appends a free hanging tail
    [(point, normal)...] that is not pushed."""
    rnd = random.Random(seed)
    bvh = skin_bvh()
    samples = smooth_samples(samples, iters=8, win=4)
    pts = [(loc + nrm * off, nrm, True) for loc, nrm in samples]
    if hang:
        pts += [(p, nrm, False) for p, nrm in hang]
    n = len(pts)
    K = across
    # width directions, smoothed along the path
    wvs = []
    for i, (p, nrm, snap) in enumerate(pts):
        t = (pts[min(i + 1, n - 1)][0] - pts[max(i - 1, 0)][0])
        if t.length < 1e-6:
            t = Vector((0, 0, 1))
        t.normalize()
        wv = nrm.cross(t)
        wvs.append(wv.normalized() if wv.length > 1e-6 else Vector((1, 0, 0)))
    for _ in range(3):
        wvs = [wvs[0]] + [(wvs[i - 1] + wvs[i] * 2 + wvs[i + 1]).normalized()
                          for i in range(1, n - 1)] + [wvs[-1]]
    ph = rnd.uniform(0, 6.28)
    # 1) lay a flat grid across the path, 2) snap every grid point onto the
    # skin, 3) relax the grid (along and across) so skin noise cannot crumple
    # it, 4) never let it sink below the skin, 5) lift by the layer offset
    grid, H = [], []
    for i, (p, nrm, snap) in enumerate(pts):
        w = (widths[i] if widths else width) * (1 + 0.04 * math.sin(ph + i * 0.35))
        base = p - nrm * off if snap else p
        row = [base + wvs[i] * ((-1 + 2 * k / (K - 1)) * w / 2) for k in range(K)]
        hs = [0.0] * K
        if snap:
            for k, q in enumerate(row):
                loc, fn, idx, dist = bvh.ray_cast(q + nrm * 0.6, -nrm, 1.3)
                if loc is not None and abs((loc - q).dot(nrm)) < 0.5:
                    hs[k] = (loc - q).dot(nrm)
            hs = upper_hull(hs)
        grid.append(row)
        H.append(hs)
    snapflags = [s for _, _, s in pts]
    # relax only the height field: the strip keeps its width and straight
    # lateral layout while bumps in the skin are smoothed out of it
    for _ in range(6):
        newH = [h[:] for h in H]
        for i in range(n):
            if not snapflags[i]:
                continue
            for k in range(K):
                acc, cnt = H[i][k] * 2, 2
                for di, dk in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    ii, kk = i + di, k + dk
                    if 0 <= ii < n and 0 <= kk < K and snapflags[ii]:
                        acc += H[ii][kk]
                        cnt += 1
                newH[i][k] = acc / cnt
        H = newH
    grid = [[q + pts[i][1] * H[i][k] for k, q in enumerate(row)] for i, row in enumerate(grid)]
    rows = []
    for i, (p, nrm, snap) in enumerate(pts):
        row = grid[i]
        if snap:
            fixed = []
            for q in row:
                loc, fn, idx, dist = bvh.find_nearest(q, 0.8)
                if loc is not None:
                    fnn = fn if fn.dot(nrm) > 0 else -fn
                    if (q - loc).dot(fnn) < 0:
                        q = loc
                fixed.append(q + nrm * off)
            row = fixed
        rows.append((row, nrm))
    # torn ends: shear the end rows so each end is an uneven point
    for end, nxt in ((0, 1), (n - 1, n - 2)):
        if (tear[0] if end == 0 else tear[1]) and n > 3:
            row, nrm = rows[end]
            nrow = rows[nxt][0]
            cut = [rnd.uniform(0.0, 0.9) for _ in range(K)]
            cut[rnd.randrange(K)] = 0.0
            rows[end] = ([row[k].lerp(nrow[k], cut[k]) for k in range(K)], nrm)
    top = [q for row, _ in rows for q in row]
    bot = [q - nrm * thick for row, nrm in rows for q in row]
    verts = top + bot
    o3 = len(top)
    faces = []
    for i in range(n - 1):
        for k in range(K - 1):
            a_ = i * K + k
            faces.append((a_, a_ + K, a_ + K + 1, a_ + 1))
            faces.append((o3 + a_, o3 + a_ + 1, o3 + a_ + K + 1, o3 + a_ + K))
        faces.append((i * K, o3 + i * K, o3 + i * K + K, i * K + K))
        j = i * K + K - 1
        faces.append((j, j + K, o3 + j + K, o3 + j))
    for k in range(K - 1):
        faces.append((k, k + 1, o3 + k + 1, o3 + k))
        j = (n - 1) * K + k
        faces.append((j, o3 + j, o3 + j + 1, j + 1))
    o = mesh_obj(name, verts, faces, mat)
    recalc_normals(o)
    flat(o)
    # across-strip coordinate (-1..1) per vertex: the bandage shader paints a
    # soft darker line along both edges, as in the reference's overlaps
    at = o.data.attributes.new('strip_v', 'FLOAT', 'POINT')
    vals = [(-1 + 2 * (i % K) / (K - 1)) for i in range(len(top))] * 2
    at.data.foreach_set('value', vals)
    return o


def upper_hull(hs):
    """Upper convex envelope of heights sampled evenly across a strip: linen
    bridges grooves across its width but still follows a convex (rounded)
    surface such as a deltoid, instead of sitting on it as a flat plank."""
    n = len(hs)
    out = list(hs)
    for i in range(n):
        for j in range(i + 2, n):
            for k in range(i + 1, j):
                t = (k - i) / (j - i)
                out[k] = max(out[k], hs[i] + (hs[j] - hs[i]) * t)
    return out


def smooth_samples(samples, iters=4, win=3):
    """Relax a projected path: smooth positions, re-snap them to the skin and
    average normals over a window, so decimated-mesh facet noise cannot twist
    the ribbon."""
    if len(samples) < 5:
        return samples
    bvh = skin_bvh()
    pos = [p.copy() for p, _ in samples]
    for _ in range(iters):
        pos = [pos[0]] + [(pos[i - 1] + pos[i] * 2 + pos[i + 1]) / 4
                          for i in range(1, len(pos) - 1)] + [pos[-1]]
    out = []
    nr = [n for _, n in samples]
    for i, p in enumerate(pos):
        loc, nrm, idx, dist = bvh.find_nearest(p, 1.0)
        if loc is None or (p - loc).dot(nrm if nrm.dot(samples[i][1]) > 0 else -nrm) > 0:
            loc = p                                  # above the skin: keep (bridge)
        acc = Vector()
        for j in range(max(0, i - win), min(len(nr), i + win + 1)):
            acc += nr[j]
        out.append((loc, acc.normalized() if acc.length > 1e-6 else nr[i]))
    return out


def torso_loop(name, zc, sx, sy, width, off, seed, phase=0.0):
    """Sash round the torso on the plane z = zc + sx*x + sy*y, projected from
    the torso's vertical axis so it hugs the chest and back."""
    guide = []
    N = 64
    for i in range(N + 1):
        ph = phase + 2 * math.pi * i / N
        h = Vector((math.sin(ph), -math.cos(ph), 0))
        x, y = 1.9 * h.x, 1.5 * h.y
        z = zc + sx * x + sy * y
        guide.append(Vector((h.x * 2.2, 0.15 + h.y * 2.2, z)))
    samples = project_path(guide, 'axis', (Vector((0, 0.15, 3.0)), Vector((0, 0.15, 12.0))),
                           clamp_r=2.05, closed=True)
    o = ribbon(name, samples, width, 0.05, off, MATS['bandage'], (False, False), seed)
    part(o, 'Body', ('transfer',), 'bandage')
    return o


WRAP_N = [0]


def helix_wrap(name, a, b, s0, s1, turns, th0, width, r=1.0, off=0.05, thick=0.05,
               tear=(True, True), ref=Vector((0, -1, 0)), hang=None, weight=('transfer',),
               seed=None, lean=0.0, tilt=0.0, clamp=1.25, taut=True):
    """Wrap around limb axis a->b from axial fraction s0 to s1 over `turns`
    turns starting at angle th0 (deg, 0 = toward `ref`)."""
    a, b = Vector(a), Vector(b)
    ax = (b - a).normalized()
    u = (ref - ax * ax.dot(ref)).normalized()
    w = ax.cross(u)
    Lax = (b - a).length
    n = max(8, int(abs(turns) * 2 * math.pi * r / 0.19))
    guide = []
    for i in range(n + 1):
        t = i / n
        ang = math.radians(th0) + turns * 2 * math.pi * t
        s = s0 + (s1 - s0) * t
        # "lean" bows the wrap along the axis on the front, making X crossings
        s += lean * math.cos(ang) + tilt * math.sin(ang)
        c = a + ax * (s * Lax)
        guide.append(c + (u * math.cos(ang) + w * math.sin(ang)) * r)
    samples = project_path(guide, 'axis', (a - ax * 0.5, b + ax * 0.5),
                           clamp_r=r * clamp, taut=taut)
    WRAP_N[0] += 1
    hp = hang(samples) if hang else None
    if hp and weight[0] == 'trail':
        TRAIL_PTS[weight[1]] = (samples[-1][0].copy(), hp[-1][0].copy())
    o = ribbon(name, samples, width, thick, off, MATS['bandage'], tear,
               seed if seed is not None else WRAP_N[0] * 13, hang=hp)
    part(o, 'Body', weight, 'bandage')
    return o


def image_strip(name, uv_pts, depth_hint, width, off=0.06, thick=0.05, back=None,
                tear=(True, True), weight=('transfer',), seed=5):
    """Strip whose visible centre line is traced in reference pixels: camera
    rays through the trace hit the skin; optional `back` guide points (3D)
    carry the strip round the back of the body."""
    bvh = skin_bvh()
    guide = []
    for u, v in uv_pts:
        d = WR(u, v)
        loc, nrm, idx, dist = bvh.ray_cast(CAM_LOC, d, 60.0)
        guide.append(loc if loc is not None else W(u, v, depth_hint))
    if back:
        guide += [Vector(p) for p in back]
    pts = catmull(guide, 0.09)
    samples = project_path(pts, 'nearest')
    o = ribbon(name, samples, width, thick, off, MATS['bandage'], tear, seed)
    part(o, 'Body', weight, 'bandage')
    return o


def hang_tail(length=0.9, n=5, twist=0.3, out=0.15, side=Vector((0, 0, 0))):
    """Returns a hang function: continue the strip off its last sample and let
    it droop down under gravity with a small twist."""
    def fn(samples):
        loc, nrm = samples[-1]
        p = loc + nrm * 0.06
        prev = samples[-2][0]
        d = (loc - prev).normalized()
        pts = []
        for i in range(1, n + 1):
            t = i / n
            dirv = (d * (1 - t) * 0.7 + Vector((0, 0, -1)) * (0.4 + t) + nrm * out + side).normalized()
            p = p + dirv * (length / n)
            p.z = max(p.z, 0.06)          # never through the ground
            nr = (nrm * math.cos(twist * t) + d.cross(nrm) * math.sin(twist * t)).normalized()
            pts.append((p.copy(), nr))
        return pts
    return fn


def build_bandages():
    J_ = jv
    # --- chest X: two wide straps; the "/" strap lies on top -------------
    torso_loop('ChestBandA', 7.50, -0.385, 0.10, 0.58, 0.07, 21)
    torso_loop('ChestBandB', 7.55, 0.48, 0.10, 0.60, 0.15, 22)
    # --- arms: wide overlapping wraps; each later wrap rides a little higher
    # (off) so overlaps layer cleanly. Table: segment, s0, s1, turns, start
    # angle, width, radius guess, extra kwargs.
    # Wraps are tilted rings round a limb segment: centre (axial fraction),
    # tilt (axial shift at the sides, so the ring reads as a diagonal from the
    # front), turns (a little over 1 so the torn end overlaps), start angle,
    # width, radius guess. Opposite tilts make the reference's X crossings.
    ARM = {
        'R': [('up', 0.40, 0.14, 1.08, 200, 0.52, 1.05, {}),
              ('up', 0.60, -0.16, 1.08, 120, 0.50, 1.05, {}),
              ('arm', 0.70, 0.24, 1.08, 180, 0.56, 1.1, {}),
              ('arm', 0.90, -0.18, 1.08, 220, 0.52, 1.1, {}),
              ('fore', 0.36, 0.20, 1.08, 80, 0.52, 0.9, {})],
        'L': [('up', 0.38, -0.14, 1.08, 160, 0.54, 1.05, {}),
              ('up', 0.58, 0.16, 1.02, 215, 0.52, 1.05,
               dict(hang=hang_tail(0.95, 7, 0.45, 0.10),
                    weight=('trail', 'BandageEnd_ShoulderL'))),
              ('arm', 0.58, -0.26, 1.08, 180, 0.58, 1.15, {}),
              ('arm', 0.74, 0.26, 1.08, 130, 0.54, 1.15, {}),
              ('arm', 0.93, -0.12, 1.08, 200, 0.52, 1.1, {}),
              ('fore', 1.08, 0.10, 1.08, 60, 0.48, 0.8, {}),
              ('fore', 1.22, -0.14, 1.02, 150, 0.46, 0.8,
               dict(hang=hang_tail(0.60, 5, 0.6, 0.12), weight=('trail', 'BandageEnd_WristL')))],
    }
    for side, table in ARM.items():
        sh, el, wr = J_('shoulder_' + side), J_('elbow_' + side), J_('wrist_' + side)
        sgn = -1 if side == 'R' else 1
        dc = DELT_C[side]
        ua = (el - sh).normalized()
        segs = {'up': (dc - ua * 1.1, dc + ua * 1.1), 'arm': (sh, el), 'fore': (el, wr)}
        for k, (seg, sc, tilt, turns, th0, wdt, r, kw) in enumerate(table):
            a_, b_ = segs[seg]
            extra = dict(clamp=1.0, taut=False) if seg == 'up' else {}
            helix_wrap(f'Wrap{side}{k}', a_, b_, sc, sc + 0.03, turns, th0, wdt, r=r,
                       off=0.05 + 0.045 * (k % 3), seed=31 + k + (0 if side == 'R' else 20),
                       tilt=tilt, tear=(False, True), **extra, **kw)
    # --- legs: X-crossing wraps round the knee and upper shin ---------------
    LEG = {
        'R': [('shin', 0.08, 0.26, 1.08, 200, 0.56), ('shin', 0.24, -0.26, 1.08, 100, 0.54),
              ('thigh', 0.92, 0.10, 1.08, 150, 0.52)],
        'L': [('shin', 0.10, -0.28, 1.08, 120, 0.58), ('shin', 0.22, 0.28, 1.08, 200, 0.56),
              ('shin', 0.38, 0.02, 1.08, 60, 0.52)],
    }
    for side, table in LEG.items():
        hp, kn, an = J_('hip_' + side), J_('knee_' + side), J_('ankle_' + side)
        segs = {'thigh': (hp, kn), 'shin': (kn, an)}
        for k, (seg, sc, tilt, turns, th0, wdt) in enumerate(table):
            a_, b_ = segs[seg]
            helix_wrap(f'WrapLeg{side}{k}', a_, b_, sc, sc + 0.03, turns, th0, wdt, r=1.05,
                       off=0.05 + 0.045 * k, seed=71 + k + (0 if side == 'R' else 10),
                       tilt=tilt, tear=(False, True))
    # --- feet: rings round a vertical axis through the middle of each foot;
    # `lean` drops the front of the ring onto the instep just above the toes
    # while the back rides round the ankle; `tilt` crosses two of them
    for side in ('R', 'L'):
        top, bot, fwd = FOOT_WRAP_AXIS[side]
        seedb = 61 if side == 'R' else 65
        FW = [(0.45, 0.03, 0.10, 0.50, {}),
              (0.47, 0.03, -0.10, 0.48,
               dict(hang=hang_tail(0.35, 4, 0.5, 0.35),
                    weight=('trail', 'BandageEnd_FootL')) if side == 'L' else {}),
              (0.555, 0.03, 0.0, 0.44, {})]
        for k, (sc, lean, tilt, wdt, kw) in enumerate(FW):
            helix_wrap(f'WrapFoot{side}{k}', top, bot, sc, sc + 0.02, 1.06, 170, wdt, r=1.0,
                       off=0.05 + 0.04 * k, seed=seedb + k, lean=lean, tilt=tilt,
                       tear=(False, True), ref=fwd, **kw)


# ================================================================= conform
def sheet_bvh(grid, center_fn):
    """BVH over a (rows x cols) point grid; returns bvh and an outward sign fn."""
    verts = [p for row in grid for p in row]
    nr, nc = len(grid), len(grid[0])
    faces = []
    closed = True
    for i in range(nr if closed else nr - 1):
        i2 = (i + 1) % nr
        for j in range(nc - 1):
            faces.append((i * nc + j, i2 * nc + j, i2 * nc + j + 1, i * nc + j + 1))
    return BVHTree.FromPolygons(verts, faces, epsilon=0.0), verts, faces


def conform_body(body):
    """Push skin that pokes through a garment's underside back beneath it, with
    a small clearance, so collar/belt/kilt never show skin through them."""
    me = body.data
    co = [v.co.copy() for v in me.vertices]
    moved = 0
    touched = set()
    for name, grid, clr in CLEAR:
        bvh, verts, faces = sheet_bvh(grid, None)
        for i, v in enumerate(co):
            loc, nrm, idx, dist = bvh.find_nearest(v, 0.9)
            if loc is None:
                continue
            if name == 'collar':
                radial = Vector((loc.x, loc.y - 0.1, 0.35))
            else:
                radial = Vector((loc.x, loc.y - 0.05, 0.0))
            if nrm.dot(radial) < 0:
                nrm = -nrm
            d = v - loc
            sd = d.dot(nrm)
            if d.length > 1e-4 and abs(d.normalized().dot(nrm)) < 0.55:
                continue          # beside the sheet's edge, not under it
            if sd > -clr:
                co[i] = v - nrm * (sd + clr)
                moved += 1
                touched.add(i)
    # relax the moved skin and a one-ring border so no ridge or spike is left
    # where the push stops at a garment's edge
    nb = [set() for _ in me.vertices]
    for ed in me.edges:
        a_, b_ = ed.vertices
        nb[a_].add(b_)
        nb[b_].add(a_)
    region = set(touched)
    for i in list(touched):
        region |= nb[i]
    for _ in range(4):
        new = {}
        for i in region:
            if nb[i]:
                avg = sum((co[j] for j in nb[i]), Vector()) / len(nb[i])
                new[i] = co[i].lerp(avg, 0.5)
        for i, c in new.items():
            co[i] = c
    for v, c in zip(me.vertices, co):
        v.co = c
    me.update()
    log('conform moved', moved, 'body verts')


# ================================================================= soft facets
def soften_facets(o, amount=0.42):
    """Custom split normals halfway between the flat face normal and the smooth
    vertex normal: facets stay visible but their edges read soft, which is the
    reference's carved-stone skin. Exported as split normals."""
    me = o.data
    vn = [Vector() for _ in me.vertices]
    for pg in me.polygons:
        for vi in pg.vertices:
            vn[vi] += pg.normal * pg.area
    vn = [v.normalized() if v.length > 0 else Vector((0, 0, 1)) for v in vn]
    ln = [None] * len(me.loops)
    for pg in me.polygons:
        pg.use_smooth = True
        for li in pg.loop_indices:
            vi = me.loops[li].vertex_index
            ln[li] = (pg.normal * (1 - amount) + vn[vi] * amount).normalized()
    me.normals_split_custom_set([tuple(v) for v in ln])


# ================================================================= facet attr
def add_facet_rand(o, seed=0):
    """Per-face random value, read by the painterly shaders as tone jitter."""
    me = o.data
    if 'facet_rand' in me.attributes:
        me.attributes.remove(me.attributes['facet_rand'])
    at = me.attributes.new('facet_rand', 'FLOAT', 'FACE')
    rnd = np.random.default_rng(seed + len(me.polygons))
    at.data.foreach_set('value', rnd.random(len(me.polygons)).astype(np.float32))


# ================================================================= review stage
REVIEW = None


def review_collection():
    global REVIEW
    if REVIEW is None:
        REVIEW = bpy.data.collections.new('REVIEW_ONLY')
        scene.collection.children.link(REVIEW)
    return REVIEW


def setup_render(engine='CYCLES', samples=32, res=(IMG_W, IMG_H)):
    scene.render.engine = engine
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    if engine == 'CYCLES':
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
        scene.cycles.max_bounces = 6
        prefs = bpy.context.preferences.addons['cycles'].preferences
        ok = False
        for dev in ('OPTIX', 'CUDA'):
            try:
                prefs.compute_device_type = dev
                prefs.get_devices()
                for d in prefs.devices:
                    d.use = d.type == dev
                if any(d.use for d in prefs.devices):
                    ok = True
                    break
            except Exception:
                continue
        scene.cycles.device = 'GPU' if ok and os.environ.get('FORCE_CPU') != '1' else 'CPU'
        if scene.cycles.device == 'CPU':
            scene.render.threads_mode = 'FIXED'
            scene.render.threads = 5
        try:
            scene.cycles.denoiser = 'OPTIX' if ok else 'OPENIMAGEDENOISE'
        except Exception:
            pass


def make_camera():
    cd = bpy.data.cameras.new('RefCam')
    cd.sensor_fit = 'AUTO'
    cd.sensor_width = 36.0
    cd.lens = FPX * 36.0 / max(IMG_W, IMG_H)
    cd.clip_start = 0.1
    cd.clip_end = 2000
    cam = bpy.data.objects.new('RefCam', cd)
    link(cam, review_collection())
    rot = Matrix((CR, CU, -CF)).transposed()
    cam.matrix_world = Matrix.Translation(CAM_LOC) @ rot.to_4x4()
    scene.camera = cam
    return cam


SUN_DIR = Vector((0.62, 0.30, 0.72)).normalized()   # toward the sun


def make_lights():
    col = review_collection()
    sd = bpy.data.lights.new('Sun', 'SUN')
    sd.energy = 3.3
    sd.angle = math.radians(6.0)
    sd.color = srgb(255, 250, 242)
    sun = bpy.data.objects.new('Sun', sd)
    link(sun, col)
    sun.rotation_euler = (-SUN_DIR).to_track_quat('-Z', 'Y').to_euler()
    ad = bpy.data.lights.new('FrontFill', 'AREA')
    ad.energy = 1500
    ad.size = 16
    ad.color = srgb(255, 252, 248)
    fill = bpy.data.objects.new('FrontFill', ad)
    link(fill, col)
    fill.location = (-6, -26, 9)
    fill.rotation_euler = (Vector((0, 0, 6)) - fill.location).to_track_quat('-Z', 'Y').to_euler()
    world = bpy.data.worlds.new('ReviewWorld')
    scene.world = world
    world.use_nodes = True
    wn = world.node_tree
    wn.nodes.clear()
    out = wn.nodes.new('ShaderNodeOutputWorld')
    mixs = wn.nodes.new('ShaderNodeMixShader')
    lp = wn.nodes.new('ShaderNodeLightPath')
    bg_cam = wn.nodes.new('ShaderNodeBackground')
    bg_amb = wn.nodes.new('ShaderNodeBackground')
    bg_cam.inputs[1].default_value = 1.0
    tc = wn.nodes.new('ShaderNodeTexCoord')
    sepw = wn.nodes.new('ShaderNodeSeparateXYZ')
    wn.links.new(tc.outputs['Window'], sepw.inputs[0])
    rmp = wn.nodes.new('ShaderNodeValToRGB')
    cr = rmp.color_ramp
    cr.elements[0].position = 0.60
    cr.elements[0].color = (*srgb(228, 190, 150), 1)
    cr.elements[1].position = 0.84
    cr.elements[1].color = (*srgb(122, 184, 248), 1)
    wn.links.new(sepw.outputs['Y'], rmp.inputs[0])
    wn.links.new(rmp.outputs[0], bg_cam.inputs[0])
    bg_amb.inputs[0].default_value = (*srgb(204, 218, 238), 1)
    bg_amb.inputs[1].default_value = 1.0
    wn.links.new(lp.outputs['Is Camera Ray'], mixs.inputs[0])
    wn.links.new(bg_amb.outputs[0], mixs.inputs[1])
    wn.links.new(bg_cam.outputs[0], mixs.inputs[2])
    wn.links.new(mixs.outputs[0], out.inputs['Surface'])


def make_ground():
    m = bpy.data.materials.new('ReviewSand')
    m.use_nodes = True
    nt = NT(m)
    nt.n.clear()
    pos = nt.geo('Position')
    n = nt.noise(pos, 0.35, 3.0, 0.55, 2.0)
    col = nt.ramp(n, [(0.35, srgb(236, 184, 112)), (0.6, srgb(246, 196, 124)),
                      (0.8, srgb(250, 206, 136))], 'EASE')
    finish_mat(m, nt, col, 0.95, 0.2)
    me = bpy.data.meshes.new('ReviewGround')
    s = 400
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new('ReviewGround', me)
    link(g, review_collection())
    g.data.materials.append(m)
    return g


def render_to(path, samples=None):
    if samples is not None and scene.render.engine == 'CYCLES':
        scene.cycles.samples = samples
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    log('rendered', path)


def render_mask(path):
    """Figure silhouette: workbench flat white, ground hidden, black world."""
    g = bpy.data.objects.get('ReviewGround')
    if g:
        g.hide_render = True
    eng = scene.render.engine
    scene.render.engine = 'BLENDER_WORKBENCH'
    sh = scene.display.shading
    sh.light = 'FLAT'
    sh.color_type = 'SINGLE'
    sh.single_color = (1, 1, 1)
    sh.background_type = 'VIEWPORT'
    sh.background_color = (0, 0, 0)
    scene.display.render_aa = '8'
    wcol = scene.world.color[:] if scene.world else None
    if scene.world:
        scene.world.color = (0, 0, 0)
    scene.view_settings.view_transform = 'Standard'
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    scene.render.engine = eng
    if g:
        g.hide_render = False
    if wcol is not None:
        scene.world.color = wcol
    log('mask', path)


ZOOMS = {'face': (440, 120, 660, 380), 'fistR': (50, 500, 340, 800),
         'handL': (780, 780, 1060, 1060), 'feet': (220, 1080, 980, 1380),
         'torso': (230, 380, 800, 780), 'kilt': (280, 740, 820, 1160)}


def render_zoom(tag, scale=3, samples=24, outdir=None):
    """Render one reference-pixel region at `scale`x through the reference
    camera (border crop), for side-by-side detail comparison."""
    u0, v0, u1, v1 = ZOOMS[tag]
    r = scene.render
    keep = (r.resolution_percentage, r.use_border, r.use_crop_to_border,
            r.border_min_x, r.border_max_x, r.border_min_y, r.border_max_y)
    r.resolution_percentage = int(100 * scale)
    r.use_border = True
    r.use_crop_to_border = True
    r.border_min_x, r.border_max_x = u0 / IMG_W, u1 / IMG_W
    r.border_min_y, r.border_max_y = 1 - v1 / IMG_H, 1 - v0 / IMG_H
    render_to((outdir or WORK) / f'zoom_{tag}.png', samples)
    (r.resolution_percentage, r.use_border, r.use_crop_to_border, r.border_min_x,
     r.border_max_x, r.border_min_y, r.border_max_y) = keep


def review_views(outdir, prefix='view', res=(600, 800), samples=16):
    """Orthographic front / side / back / three-quarter checks."""
    cam = scene.camera
    keep = (cam.matrix_world.copy(), cam.data.type, cam.data.ortho_scale,
            scene.render.resolution_x, scene.render.resolution_y)
    scene.render.resolution_x, scene.render.resolution_y = res
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = 15.5
    tgt = Vector((-0.5, 0, 6.4))
    for tag, loc in (('front', (0, -40, 6.4)), ('side', (40, 0, 6.4)), ('back', (0, 40, 6.4)),
                     ('threequarter', (28, -28, 9.0)), ('left', (-40, 0, 6.4))):
        cam.location = Vector(loc)
        cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
        render_to(outdir / f'{prefix}_{tag}.png', samples)
    cam.matrix_world, cam.data.type, cam.data.ortho_scale = keep[0], keep[1], keep[2]
    scene.render.resolution_x, scene.render.resolution_y = keep[3], keep[4]


# ================================================================= rig
RIG = NAME + '_Rig'
BONES = {}            # name -> dict(head, tail, parent, deform, hinge)
TRAIL_PTS = {}        # bandage trailing-end bone -> (root, tip)
TAIL_PTS = []         # nemes tail centre line
CORE_SKIN_BONES = ['LowerTorso', 'UpperTorso', 'Head',
                   'LeftUpperArm', 'LeftLowerArm', 'LeftHand',
                   'RightUpperArm', 'RightLowerArm', 'RightHand',
                   'LeftUpperLeg', 'LeftLowerLeg', 'LeftFoot',
                   'RightUpperLeg', 'RightLowerLeg', 'RightFoot']


def bdef(name, head, tail, parent, hinge=None, deform=True):
    BONES[name] = dict(head=Vector(head), tail=Vector(tail), parent=parent, hinge=hinge,
                       deform=deform)


def flex_axis(d_parent, d_child, fallback):
    """Hinge axis such that a positive rotation about it closes the joint."""
    h = d_parent.cross(d_child)
    if h.length < 0.15:
        h = Vector(fallback)
    h.normalize()
    probe = Quaternion(h, math.radians(5)) @ d_child
    if probe.angle(-d_parent) > d_child.angle(-d_parent):
        h = -h
    return h


def obj_centroid(name):
    o = bpy.data.objects[name]
    return sum((o.matrix_world @ v.co for v in o.data.vertices), Vector()) / len(o.data.vertices)


def plan_bones():
    BONES.clear()
    pel, spi, nek, hed = jv('pelvis'), jv('spine'), jv('neck'), jv('head')
    lat = Vector((1, 0, 0))
    bdef('Root', (0, 0, 0), (0, 0, 1.0), None, hinge=lat)
    hrp = Vector((0, 0.05, 5.2))
    bdef('HumanoidRootPart', hrp, hrp + Vector((0, 0, 0.6)), 'Root', hinge=lat)
    bdef('LowerTorso', Vector((0, 0.05, 4.75)), Vector((0, 0.10, 6.65)), 'HumanoidRootPart',
         hinge=lat)
    bdef('UpperTorso', Vector((0, 0.10, 6.65)), Vector((0, 0.22, 9.45)), 'LowerTorso', hinge=lat)
    bdef('Head', Vector((0, 0.10, 9.62)), Vector((0, -0.05, 11.9)), 'UpperTorso', hinge=lat)
    jaw_h = Vector((0, -0.35, face_z(330, FACE_Y) + 0.05))
    bdef('Jaw', jaw_h, Vector((0, FACE_Y - 0.05, face_z(362, FACE_Y))), 'Head', hinge=lat)
    for side, S in (('L', 'Left'), ('R', 'Right')):
        sh, el, wr = jv('shoulder_' + side), jv('elbow_' + side), jv('wrist_' + side)
        ua, fa = (el - sh).normalized(), (wr - el).normalized()
        h = flex_axis(ua, fa, lat)
        bdef(f'{S}UpperArm', sh, el, 'UpperTorso', hinge=h)
        bdef(f'{S}LowerArm', el, wr, f'{S}UpperArm', hinge=h)
        # hand bone: wrist -> knuckle line
        fj = HAND_JOINTS[side]
        knuckles = sum((fj[f][0] for f in FINGERS), Vector()) / 4
        bdef(f'{S}Hand', wr, knuckles, f'{S}LowerArm', hinge=h)
        for f in FINGERS + ('Thumb',):
            pts = fj[f]
            nseg = 3 if f != 'Thumb' else 2
            for si in range(nseg):
                a_, b_ = pts[si], pts[si + 1]
                d0 = (pts[1] - pts[0]).normalized()
                d1 = (pts[2] - pts[1]).normalized()
                hf = flex_axis(d0, d1, h)
                parent = f'{S}Hand' if si == 0 else f'{S}{f}{si}'
                bdef(f'{S}{f}{si + 1}', a_, b_, parent, hinge=hf)
    for side, S in (('L', 'Left'), ('R', 'Right')):
        hp, kn, an = jv('hip_' + side), jv('knee_' + side), jv('ankle_' + side)
        th, sh_ = (kn - hp).normalized(), (an - kn).normalized()
        # knee flexion moves the shin back: test against the forward direction
        hk = flex_axis(th, sh_, lat)
        probe = Quaternion(hk, math.radians(5)) @ sh_
        if probe.dot(Vector((0, -1, 0))) > sh_.dot(Vector((0, -1, 0))):
            hk = -hk
        bdef(f'{S}UpperLeg', hp, kn, 'LowerTorso', hinge=hk)
        bdef(f'{S}LowerLeg', kn, an, f'{S}UpperLeg', hinge=hk)
        a_, root, tip = FOOT_JOINTS[side]
        bdef(f'{S}Foot', an, root, f'{S}LowerLeg', hinge=hk)
        bdef(f'{S}Toes', root, tip, f'{S}Foot', hinge=hk)
    # nemes lappets (two bones each, following the stripe blocks) and tail
    for side in ('L', 'R'):
        c = [obj_centroid(f'Lappet{side}{j}') for j in range(4)]
        top = c[0] + (c[0] - c[1]) * 0.55
        mid = (c[1] + c[2]) / 2
        bot = c[3] + (c[3] - c[2]) * 0.55
        bdef(f'NemesLappet_{side}_1', top, mid, 'Head', hinge=lat)
        bdef(f'NemesLappet_{side}_2', mid, bot, f'NemesLappet_{side}_1', hinge=lat)
    bdef('NemesTail', TAIL_PTS[0], TAIL_PTS[-1], 'Head', hinge=lat)
    # kilt: front apron chain, both sides, back tail
    top = kilt_pt(0, KILT_TOP - 0.05, 0.10)
    tip = W(521, 1052, -2.15)
    midp = top.lerp(tip, 0.5)
    bdef('Apron_1', top, midp, 'LowerTorso', hinge=lat)
    bdef('Apron_2', midp, tip, 'Apron_1', hinge=lat)
    for side, th_ in (('L', 95), ('R', -95)):
        bdef(f'Kilt_{side}', kilt_pt(th_, KILT_TOP - 0.05, -0.25), kilt_pt(th_, 3.55, 0.0),
             'LowerTorso', hinge=Vector((0, -1, 0)))
    bdef('Kilt_Back', kilt_pt(171, KILT_TOP - 0.05, -0.1), kilt_pt(171, 2.3, 0.05),
         'LowerTorso', hinge=lat)
    # trailing bandage ends
    host = {'BandageEnd_ShoulderL': 'LeftUpperArm', 'BandageEnd_WristL': 'LeftLowerArm',
            'BandageEnd_FootL': 'LeftFoot'}
    for bn, (root, tipp) in TRAIL_PTS.items():
        bdef(bn, root, tipp, host[bn], hinge=lat)
    # staff: child of the right hand; grip point = the staff axis in the fist
    bdef('Staff', STAFF_GRIP, STAFF_GRIP + STAFF_DIR * 2.0, 'RightHand',
         hinge=Vector((1, 0, 0)))


def build_armature():
    plan_bones()
    ad = bpy.data.armatures.new(RIG)
    ad.display_type = 'OCTAHEDRAL'
    arm = bpy.data.objects.new(RIG, ad)
    link(arm)
    activate(arm)
    bpy.ops.object.mode_set(mode='EDIT')
    ebs = ad.edit_bones
    for name, d in BONES.items():
        eb = ebs.new(name)
        eb.head, eb.tail = d['head'], d['tail']
        eb.use_deform = d['deform']
        eb.use_connect = False
    for name, d in BONES.items():
        eb = ebs[name]
        if d['parent']:
            eb.parent = ebs[d['parent']]
        # roll: local X = the flexion/hinge axis -> Z = X x Y
        y = (eb.tail - eb.head).normalized()
        h = d['hinge'] - y * y.dot(d['hinge'])
        if h.length < 1e-4:
            h = Vector((0, 0, 1)) - y * y.z
        h.normalize()
        eb.align_roll(h.cross(y))
    bpy.ops.object.mode_set(mode='OBJECT')
    arm.data.pose_position = 'POSE'
    arm.show_in_front = True
    return arm


# ----------------------------------------------------------------- weights
def set_rigid(o, bone):
    vg = o.vertex_groups.get(bone) or o.vertex_groups.new(name=bone)
    vg.add(range(len(o.data.vertices)), 1.0, 'REPLACE')


def heat_weights(o, arm):
    """Blender bone-heat weights for the unioned skin, core body bones only."""
    keep = {}
    for bn in arm.data.bones:
        keep[bn.name] = bn.use_deform
        bn.use_deform = bn.name in CORE_SKIN_BONES
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    for bn in arm.data.bones:
        bn.use_deform = keep[bn.name]
    # parenting added an Armature modifier and parent; keep the weights only
    o.parent = None
    for m in list(o.modifiers):
        if m.type == 'ARMATURE':
            o.modifiers.remove(m)
    o.matrix_world = Matrix.Identity(4)
    empty = [vg.name for vg in o.vertex_groups]
    return empty


def weight_table(o):
    """Per-vertex {group: weight} dictionary."""
    names = {vg.index: vg.name for vg in o.vertex_groups}
    out = []
    for v in o.data.vertices:
        out.append({names[g.group]: g.weight for g in v.groups if g.weight > 1e-5})
    return out


class SkinSource:
    """Every skin surface (unioned body + rigid palms, fingers, feet, toes)
    with its per-vertex weights, for transferring weights onto bandages."""

    def __init__(self, objs):
        self.verts, self.faces, self.w = [], [], []
        for o in objs:
            base = len(self.verts)
            wt = weight_table(o)
            self.verts += [o.matrix_world @ v.co for v in o.data.vertices]
            self.w += wt
            self.faces += [[base + i for i in pg.vertices] for pg in o.data.polygons]
        self.bvh = BVHTree.FromPolygons(self.verts, self.faces, epsilon=0.0)

    def sample(self, p):
        loc, nrm, fi, dist = self.bvh.find_nearest(p, 5.0)
        if loc is None:
            return {}, 9e9
        f = self.faces[fi]
        # inverse-distance blend of the face's corner weights
        acc, tot = {}, 0.0
        for vi in f:
            d = (self.verts[vi] - loc).length + 1e-4
            k = 1.0 / d
            tot += k
            for g, w in self.w[vi].items():
                acc[g] = acc.get(g, 0.0) + w * k
        return {g: w / tot for g, w in acc.items()}, dist


def assign(o, table):
    for v, wd in zip(o.data.vertices, table):
        for g, w in wd.items():
            vg = o.vertex_groups.get(g) or o.vertex_groups.new(name=g)
            vg.add([v.index], w, 'REPLACE')


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def kilt_weights(o, mode):
    out = []
    for v in o.data.vertices:
        p = o.matrix_world @ v.co
        x, y, z = kilt_world_to_local(p)
        if mode == 'apron':
            u = max(0.0, min(1.0, (KILT_TOP - z) / (KILT_TOP - 2.2)))
            lt = max(0.0, 1.0 - u * 4.0)
            w = {'LowerTorso': lt, 'Apron_1': (1 - lt) * (1 - u), 'Apron_2': (1 - lt) * u}
        elif mode == 'back':
            u = max(0.0, min(1.0, (KILT_TOP - z) / (KILT_TOP - 2.3)))
            lt = max(0.0, 1.0 - u * 3.0)
            w = {'LowerTorso': lt, 'Kilt_Back': 1 - lt}
        else:
            t = max(0.0, min(1.0, (KILT_TOP - z) / (KILT_TOP - 3.2)))
            lt = (1 - t) ** 2
            s = 0.5 + 0.5 * max(-1.0, min(1.0, x / 0.7))
            rest = 1 - lt
            w = {'LowerTorso': lt,
                 'Kilt_L': rest * 0.72 * s, 'Kilt_R': rest * 0.72 * (1 - s),
                 'LeftUpperLeg': rest * 0.28 * s, 'RightUpperLeg': rest * 0.28 * (1 - s)}
        out.append({k: val for k, val in w.items() if val > 1e-4})
    return out


def fill_unweighted(o, src):
    """Any vertex left without a deform weight (heat weighting occasionally
    misses a few verts in tight creases) copies the nearest weighted vertex of
    the same mesh, or the skin source as a last resort."""
    from mathutils.kdtree import KDTree
    names = {vg.index: vg.name for vg in o.vertex_groups}
    bones = set(b.name for b in bpy.data.objects[RIG].data.bones)
    weighted, empty = [], []
    for v in o.data.vertices:
        if any(g.weight > 1e-5 and names.get(g.group) in bones for g in v.groups):
            weighted.append(v.index)
        else:
            empty.append(v.index)
    if not empty:
        return
    if weighted:
        kd = KDTree(len(weighted))
        for i, vi in enumerate(weighted):
            kd.insert(o.data.vertices[vi].co, i)
        kd.balance()
    for vi in empty:
        v = o.data.vertices[vi]
        if weighted:
            co, i, d = kd.find(v.co)
            src_v = o.data.vertices[weighted[i]]
            table = {names[g.group]: g.weight for g in src_v.groups if names.get(g.group) in bones}
        else:
            table, _ = src.sample(o.matrix_world @ v.co)
        for g, w in table.items():
            vg = o.vertex_groups.get(g) or o.vertex_groups.new(name=g)
            vg.add([vi], w, 'REPLACE')
    log('filled', len(empty), 'unweighted verts on', o.name)


def normalize_limit(o, limit=4):
    """At most `limit` influences per vertex, weights summing to 1."""
    names = {vg.index: vg.name for vg in o.vertex_groups}
    groups = {vg.name: vg for vg in o.vertex_groups}
    for v in o.data.vertices:
        ws = sorted(((g.weight, names[g.group]) for g in v.groups if g.weight > 1e-6), reverse=True)
        keep = ws[:limit]
        tot = sum(w for w, _ in keep)
        for g in list(v.groups):
            groups[names[g.group]].remove([v.index])
        if tot <= 0:
            continue
        for w, n in keep:
            groups[n].add([v.index], w / tot, 'REPLACE')


def skin_all(arm):
    body = bpy.data.objects['Body_Skin']
    heat_weights(body, arm)
    # rigid, kilt and chain parts first (the skin source needs rigid skin parts)
    for p in PARTS:
        o, rule = p['obj'], p['weight']
        if o is body or not o.data:
            continue
        if rule[0] == 'rigid':
            set_rigid(o, rule[1])
        elif rule[0] == 'kilt':
            assign(o, kilt_weights(o, 'side'))
        elif rule[0] == 'chain':
            assign(o, kilt_weights(o, rule[1]))
    src_objs = [body] + [p['obj'] for p in PARTS if p['mat'] == 'skin' and p['obj'] is not body]
    src = SkinSource(src_objs)
    for p in PARTS:
        o, rule = p['obj'], p['weight']
        if rule[0] in ('transfer', 'trail'):
            table = []
            for v in o.data.vertices:
                wd, dist = src.sample(o.matrix_world @ v.co)
                if rule[0] == 'trail':
                    k = smoothstep(0.10, 0.40, dist)
                    wd = {g: w * (1 - k) for g, w in wd.items()}
                    wd[rule[1]] = wd.get(rule[1], 0.0) + k
                table.append(wd)
            assign(o, table)
    for p in PARTS:
        fill_unweighted(p['obj'], src)
        normalize_limit(p['obj'], 4)
    log('skinned', len(PARTS), 'parts')


# ----------------------------------------------------------------- posing
def pose_rot_world(pb, axis_world, angle_deg):
    """Rotate a pose bone about a world axis through its head (pose space)."""
    arm = pb.id_data
    M = pb.matrix.copy()
    head = M.to_translation()
    ax = (arm.matrix_world.inverted().to_3x3() @ Vector(axis_world)).normalized()
    R = Matrix.Translation(head) @ Quaternion(ax, math.radians(angle_deg)).to_matrix().to_4x4() \
        @ Matrix.Translation(-head)
    pb.matrix = R @ M
    bpy.context.view_layer.update()


REST_SPREAD = {'LeftUpperArm': ((0, 1, 0), -9.0), 'RightUpperArm': ((0, 1, 0), 9.0)}


def apply_rest_pose(arm):
    """Rest = the reference stance with both arms lifted slightly off the body
    (cleaner armpit weights). Mesh is baked through the armature, then the pose
    becomes the new rest; ReferencePose rotates the arms back."""
    activate(arm)
    bpy.ops.object.mode_set(mode='POSE')
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    for bn, (ax, ang) in REST_SPREAD.items():
        pose_rot_world(arm.pose.bones[bn], ax, ang)
    bpy.ops.object.mode_set(mode='OBJECT')
    for o in SECTIONS.values():
        md = o.modifiers.new('Armature', 'ARMATURE')
        md.object = arm
        activate(o)
        bpy.ops.object.modifier_apply(modifier=md.name)
    activate(arm)
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    # record the reference-pose local rotations (the inverse of the spread)
    ref = {}
    activate(arm)
    bpy.ops.object.mode_set(mode='POSE')
    for bn, (ax, ang) in REST_SPREAD.items():
        pb = arm.pose.bones[bn]
        pose_rot_world(pb, ax, -ang)
        ref[bn] = pb.rotation_quaternion.copy()
        pb.rotation_quaternion = Quaternion()
    bpy.ops.object.mode_set(mode='OBJECT')
    return ref


def bind(arm):
    for o in SECTIONS.values():
        o.parent = arm
        o.matrix_parent_inverse = arm.matrix_world.inverted()
        md = o.modifiers.new('Armature', 'ARMATURE')
        md.object = arm
        md.use_deform_preserve_volume = False


# ================================================================= sections
SECTION_ORDER = ['Body', 'Bandages', 'Head', 'Waist', 'Staff', 'EyeGlow']
SECTIONS = {}
ROUGH = {'gold': 0.52, 'gem': 0.35, 'blue': 0.80, 'slate': 0.82, 'brown': 0.80,
         'eye': 0.5, 'eye_halo': 0.5}


def section_of(p):
    if p['section'] == 'Body' and p['mat'] == 'bandage':
        return 'Bandages'
    return p['section']


def join_sections():
    groups = {}
    for p in PARTS:
        groups.setdefault(section_of(p), []).append(p['obj'])
    for sec in SECTION_ORDER:
        objs = [o for o in groups.get(sec, []) if o.name in bpy.data.objects]
        if not objs:
            continue
        bpy.ops.object.select_all(action='DESELECT')
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        if len(objs) > 1:
            bpy.ops.object.join()
        o = bpy.context.view_layer.objects.active
        o.name = f'{NAME}_{sec}'
        o.data.name = f'{NAME}_{sec}'
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        bm.to_mesh(o.data)
        bm.free()
        o.data.validate(verbose=False)
        SECTIONS[sec] = o
    log('sections', {k: len(v.data.polygons) for k, v in SECTIONS.items()})


def tri_count(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def unwrap(o):
    activate(o)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(58), island_margin=0.006,
                             area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    try:
        bpy.ops.uv.pack_islands(rotate=True, margin=0.006)
    except Exception as e:
        log('pack failed', e)
    bpy.ops.object.mode_set(mode='OBJECT')


def bake_sections(size=2048):
    """Bake each section's procedural painterly colour (and a roughness map)
    through EMIT into its own atlas; then swap to one plain textured material."""
    setup_render('CYCLES', 16)
    scene.render.bake.margin = 16
    scene.render.bake.use_clear = True
    ground = bpy.data.objects.get('ReviewGround')
    if ground:
        ground.hide_render = True
    out = {}
    for sec, o in SECTIONS.items():
        unwrap(o)
        for kind in ('Color', 'Rough'):
            img = bpy.data.images.new(f'{NAME}_{sec}_{kind}', size, size, alpha=False)
            if kind == 'Rough':
                img.colorspace_settings.name = 'Non-Color'
            wiring = []
            for slot in o.material_slots:
                m = slot.material
                nt = m.node_tree
                nd = nt.nodes.new('ShaderNodeTexImage')
                nd.name = 'BAKE_TARGET'
                nd.image = img
                nt.nodes.active = nd
                outn = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
                em = nt.nodes.get('BAKE_EMIT')
                prev = outn.inputs['Surface'].links[0].from_socket
                if kind == 'Color':
                    nt.links.new(em.outputs[0], outn.inputs['Surface'])
                else:
                    key = m.name.replace(f'{NAME}_', '')
                    r = ROUGH.get(key, 0.90)
                    em2 = nt.nodes.new('ShaderNodeEmission')
                    em2.name = 'BAKE_ROUGH'
                    em2.inputs['Color'].default_value = (r, r, r, 1)
                    nt.links.new(em2.outputs[0], outn.inputs['Surface'])
                wiring.append((nt, outn, prev, nd))
            activate(o)
            t = time.time()
            bpy.ops.object.bake(type='EMIT')
            log('baked', sec, kind, f'{time.time() - t:.1f}s')
            for nt, outn, prev, nd in wiring:
                nt.links.new(prev, outn.inputs['Surface'])
                nt.nodes.remove(nd)
                r2 = nt.nodes.get('BAKE_ROUGH')
                if r2:
                    nt.nodes.remove(r2)
            path = HERE / 'textures' / f'{NAME}_{sec}_{kind}.png'
            img.filepath_raw = str(path)
            img.file_format = 'PNG'
            img.save()
            out[(sec, kind)] = img
    if ground:
        ground.hide_render = False
    # final materials: one per section
    for sec, o in SECTIONS.items():
        m = bpy.data.materials.new(f'{NAME}_{sec}_Mat')
        m.use_nodes = True
        nt = m.node_tree
        bs = nt.nodes.get('Principled BSDF')
        tc = nt.nodes.new('ShaderNodeTexImage')
        tc.image = out[(sec, 'Color')]
        tc.interpolation = 'Linear'
        tr = nt.nodes.new('ShaderNodeTexImage')
        tr.image = out[(sec, 'Rough')]
        nt.links.new(tc.outputs['Color'], bs.inputs['Base Color'])
        nt.links.new(tr.outputs['Color'], bs.inputs['Roughness'])
        if 'Specular IOR Level' in bs.inputs:
            bs.inputs['Specular IOR Level'].default_value = 0.30
        if sec == 'EyeGlow':
            nt.links.new(tc.outputs['Color'], bs.inputs['Emission Color'])
            bs.inputs['Emission Strength'].default_value = 7.0
        o.data.materials.clear()
        o.data.materials.append(m)
        for pg in o.data.polygons:
            pg.material_index = 0
    # 1024 Roblox delivery copies (Roblox caps uploads at 1024)
    for (sec, kind), img in out.items():
        small = img.copy()
        small.scale(1024, 1024)
        small.filepath_raw = str(HERE / 'textures' / f'{NAME}_{sec}_{kind}_1024.png')
        small.file_format = 'PNG'
        small.save()
        bpy.data.images.remove(small)
    for img in out.values():
        img.pack()
    for m in list(bpy.data.materials):
        if m.users == 0:
            bpy.data.materials.remove(m)


# ================================================================= actions
FPS = 24


def local_q(arm, bone, axis, angle_deg, space='world'):
    """Local rotation for `bone` about an axis given in world space (relative to
    the bone's rest frame) or in the bone's own local space."""
    if space == 'local':
        ax = Vector(axis)
    else:
        M = arm.data.bones[bone].matrix_local.to_3x3()
        ax = M.inverted() @ Vector(axis)
    return Quaternion(ax.normalized(), math.radians(angle_deg))


def deform_bones(arm):
    return [b.name for b in arm.data.bones if b.use_deform]


def key_pose(arm, frame, pose):
    """pose: bone -> list of (axis, deg, space). Bones not listed return to rest
    (or to the base pose already folded into `pose`)."""
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        q = Quaternion()
        for axis, deg, space in pose.get(pb.name, []):
            q = q @ local_q(arm, pb.name, axis, deg, space)
        pb.rotation_quaternion = q
        pb.location = (0, 0, 0)
        pb.keyframe_insert('rotation_quaternion', frame=frame)
        pb.keyframe_insert('location', frame=frame)


def new_action(arm, name):
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act
    return act


def make_actions(arm):
    X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
    ref = {bn: [(ax, -ang, 'world')] for bn, (ax, ang) in REST_SPREAD.items()}
    act_ref = new_action(arm, 'ReferencePose')
    key_pose(arm, 1, ref)
    key_pose(arm, 2, ref)
    act_ref.frame_range = (1, 2)
    # ---- RigTest_ROM: every bone through a realistic range -----------------
    act_rom = new_action(arm, 'RigTest_ROM')
    fingers = {s: [f'{s}{f}{i}' for f in FINGERS for i in (1, 2, 3)] +
               [f'{s}Thumb1', f'{s}Thumb2'] for s in ('Left', 'Right')}
    L = lambda deg: (X, deg, 'local')           # hinge flexion (local X)
    keys = []

    def add(name, pose):
        keys.append((name, pose))
    add('rest', {})
    # right arm overhead uses the solved staff-raise arm so the staff clears the
    # head; the left arm goes fully overhead
    ov = SOLVED_ATTACKS['overhead']['pose']
    add('arms overhead', {'LeftUpperArm': [(Y, -145, 'world')],
                          'RightUpperArm': ov['RightUpperArm'],
                          'RightLowerArm': ov['RightLowerArm'], 'RightHand': ov['RightHand']})
    add('arms forward', {'LeftUpperArm': [(X, -85, 'world')],
                         'RightUpperArm': [(X, -60, 'world')]})
    add('arms back', {'LeftUpperArm': [(X, 40, 'world')],
                      'RightUpperArm': [(X, 45, 'world')]})
    # elbow keys are relative to rest (rest flex: right 96 deg, left 26 deg), so
    # these reach 130 deg flexion and ~0-16 deg (near straight)
    add('elbows 130', {'LeftLowerArm': [L(104)], 'RightLowerArm': [L(34)],
                       'LeftUpperArm': [(X, -30, 'world')]})
    add('elbows open', {'LeftLowerArm': [L(-25)], 'RightLowerArm': [L(-80)]})
    add('wrists + fist', dict({'LeftHand': [L(40)], 'RightHand': [L(-35)]},
                              **{b: [L(70)] for s in fingers for b in fingers[s]}))
    add('wrists + open', dict({'LeftHand': [L(-35)], 'RightHand': [L(30)]},
                              **{b: [L(-18)] for s in fingers for b in fingers[s]}))
    add('hip flex', {'LeftUpperLeg': [(X, -60, 'world')], 'RightUpperLeg': [(X, 25, 'world')]})
    add('high knee', {'LeftUpperLeg': [(X, -95, 'world')], 'LeftLowerLeg': [L(110)],
                      'LeftFoot': [L(-20)], 'LeftToes': [L(-25)]})
    add('high knee R', {'RightUpperLeg': [(X, -90, 'world')], 'RightLowerLeg': [L(105)],
                        'RightFoot': [L(20)], 'RightToes': [L(25)]})
    add('torso twist', {'UpperTorso': [(Z, 32, 'world')], 'LowerTorso': [(Z, 10, 'world')]})
    add('torso bend', {'UpperTorso': [(X, -32, 'world')], 'LowerTorso': [(X, -12, 'world')]})
    add('torso side', {'UpperTorso': [(Y, 22, 'world')]})
    add('head turn + jaw', {'Head': [(Z, 50, 'world')], 'Jaw': [L(24)]})
    add('head nod', {'Head': [(X, -28, 'world')], 'Jaw': [L(10)]})
    add('headdress swing', {'NemesLappet_L_1': [(X, -30, 'world')],
                            'NemesLappet_L_2': [(X, -25, 'world')],
                            'NemesLappet_R_1': [(X, 25, 'world')],
                            'NemesLappet_R_2': [(X, 20, 'world')],
                            'NemesTail': [(X, 30, 'world')]})
    add('kilt swing', {'Apron_1': [(X, -30, 'world')], 'Apron_2': [(X, -25, 'world')],
                       'Kilt_L': [(Y, 22, 'world')], 'Kilt_R': [(Y, -22, 'world')],
                       'Kilt_Back': [(X, 30, 'world')],
                       'BandageEnd_ShoulderL': [(X, -40, 'world')],
                       'BandageEnd_WristL': [(Y, 35, 'world')],
                       'BandageEnd_FootL': [(X, 30, 'world')]})
    add('staff raise', SOLVED_ATTACKS['overhead']['pose'])
    add('staff slam', SOLVED_ATTACKS['slam']['pose'])
    add('staff thrust', SOLVED_ATTACKS['thrust']['pose'])
    add('rest', {})
    step = 12
    for i, (nm, pose) in enumerate(keys):
        key_pose(arm, 1 + i * step, pose)
    act_rom.frame_range = (1, 1 + (len(keys) - 1) * step)
    ROM_KEYS.clear()
    ROM_KEYS.extend((1 + i * step, nm) for i, (nm, _) in enumerate(keys))
    arm.animation_data.action = act_ref
    scene.frame_set(1)
    return act_ref, act_rom


ROM_KEYS = []


# ================================================================= review renders
def bind_action(arm, act):
    ad = arm.animation_data or arm.animation_data_create()
    ad.action = act
    if act is not None and hasattr(ad, 'action_slot') and getattr(act, 'slots', None):
        if ad.action_slot is None or ad.action_slot not in list(act.slots):
            ad.action_slot = act.slots[0]


def set_action(arm, name, frame=1):
    bind_action(arm, bpy.data.actions[name])
    scene.frame_set(frame)
    bpy.context.view_layer.update()


def cam_look(cam, loc, target, ortho=None, lens=None):
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    if ortho:
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = ortho
    else:
        cam.data.type = 'PERSP'
        if lens:
            cam.data.lens = lens


def tile_images(paths, cols, out_path, labels=None, bg=(0.10, 0.11, 0.13)):
    imgs = [bpy.data.images.load(str(p)) for p in paths]
    w, h = imgs[0].size
    rows = (len(imgs) + cols - 1) // cols
    sheet = np.zeros((rows * h, cols * w, 4), np.float32)
    sheet[..., :3] = bg
    sheet[..., 3] = 1
    for i, im in enumerate(imgs):
        px = np.array(im.pixels[:], np.float32).reshape(h, w, 4)
        r, c = i // cols, i % cols
        y0 = (rows - 1 - r) * h
        sheet[y0:y0 + h, c * w:(c + 1) * w] = px
    out = bpy.data.images.new('sheet', cols * w, rows * h, alpha=False)
    out.pixels.foreach_set(sheet.ravel())
    out.filepath_raw = str(out_path)
    out.file_format = 'PNG'
    out.save()
    for im in imgs:
        bpy.data.images.remove(im)
    bpy.data.images.remove(out)


def bone_sticks(arm):
    """Temporary octahedral bone mesh at the current pose (Cycles cannot draw
    armature overlays)."""
    dg = bpy.context.evaluated_depsgraph_get()
    verts, faces, cols = [], [], []
    palette = {'spine': (0.95, 0.85, 0.2), 'L': (0.2, 0.8, 1.0), 'R': (1.0, 0.35, 0.3),
               'cloth': (0.7, 0.4, 1.0), 'staff': (0.3, 1.0, 0.4)}
    for pb in arm.pose.bones:
        if not pb.bone.use_deform:
            continue
        h = arm.matrix_world @ pb.head
        t = arm.matrix_world @ pb.tail
        d = t - h
        L_ = d.length
        if L_ < 1e-4:
            continue
        y = d.normalized()
        x = y.orthogonal().normalized()
        z = y.cross(x)
        r = min(0.12, L_ * 0.12)
        base = len(verts)
        m = h + y * (L_ * 0.18)
        verts += [h, m + x * r, m + z * r, m - x * r, m - z * r, t]
        faces += [(base, base + 1, base + 2), (base, base + 2, base + 3), (base, base + 3, base + 4),
                  (base, base + 4, base + 1), (base + 5, base + 2, base + 1),
                  (base + 5, base + 3, base + 2), (base + 5, base + 4, base + 3),
                  (base + 5, base + 1, base + 4)]
        n = pb.name
        k = ('staff' if n == 'Staff' else 'L' if n.startswith('Left') or n.endswith('_L')
             or n.endswith('L') and 'Bandage' in n else 'R' if n.startswith('Right')
             or n.endswith('_R') else 'cloth' if any(s in n for s in ('Kilt', 'Apron', 'Nemes',
                                                                          'Bandage')) else 'spine')
        cols += [k] * 8
    o = mesh_obj('RigBones_viz', verts, faces)
    for k, c in palette.items():
        m = bpy.data.materials.new('bonecol_' + k)
        m.use_nodes = True
        bs = m.node_tree.nodes.get('Principled BSDF')
        bs.inputs['Base Color'].default_value = (*c, 1)
        bs.inputs['Emission Color'].default_value = (*c, 1)
        bs.inputs['Emission Strength'].default_value = 1.5
        o.data.materials.append(m)
    keys = list(palette.keys())
    for pg, k in zip(o.data.polygons, cols):
        pg.material_index = keys.index(k)
    return o


def ghost_sections(on):
    for sec, o in SECTIONS.items():
        m = o.data.materials[0]
        bs = m.node_tree.nodes.get('Principled BSDF')
        bs.inputs['Alpha'].default_value = 0.28 if on else 1.0


def render_reviews(arm):
    cam = scene.camera
    keep = cam.matrix_world.copy(), cam.data.lens, cam.data.type
    P = HERE / 'previews'
    # turnaround (reference pose), orthographic
    set_action(arm, 'ReferencePose')
    scene.render.resolution_x, scene.render.resolution_y = 600, 800
    tgt = Vector((-0.6, 0, 6.5))
    paths = []
    for tag, loc in (('front', (0, -40, 6.5)), ('side', (40, 0, 6.5)), ('back', (0, 40, 6.5)),
                     ('threequarter', (28, -28, 9.5))):
        cam_look(cam, loc, tgt, ortho=15.8)
        pth = WORK / f'turn_{tag}.png'
        render_to(pth, 32)
        paths.append(pth)
    tile_images(paths, 4, P / 'Turnaround.png')
    # face close-up
    scene.render.resolution_x, scene.render.resolution_y = 1000, 1000
    cam_look(cam, (0.9, -9.5, 11.2), (0, -0.9, 10.75), lens=85)
    render_to(P / 'Face_CloseUp.png', 64)
    # rig bones overlay (front + side), reference pose
    viz = bone_sticks(arm)
    ghost_sections(True)
    scene.render.resolution_x, scene.render.resolution_y = 600, 800
    bp = []
    for tag, loc in (('front', (0, -40, 6.5)), ('side', (40, 0, 6.5))):
        cam_look(cam, loc, tgt, ortho=15.8)
        pth = WORK / f'bones_{tag}.png'
        render_to(pth, 24)
        bp.append(pth)
    tile_images(bp, 2, P / 'Rig_Bones.png')
    ghost_sections(False)
    bpy.data.objects.remove(viz)
    # RigTest_ROM contact sheet: one tile per key pose, three-quarter view
    set_action(arm, 'RigTest_ROM')
    scene.render.resolution_x, scene.render.resolution_y = 360, 480
    rp = []
    for f, nm in ROM_KEYS:
        scene.frame_set(f)
        cam_look(cam, (24, -30, 9.5), (-0.3, 0, 6.8), ortho=17.5)
        pth = WORK / f'rom_{f:03d}.png'
        render_to(pth, 16)
        rp.append(pth)
    tile_images(rp, 6, P / 'RigTest_ROM.png')
    set_action(arm, 'ReferencePose')
    cam.matrix_world, cam.data.lens, cam.data.type = keep
    scene.render.resolution_x, scene.render.resolution_y = IMG_W, IMG_H


# ================================================================= attack pose solver
SOLVED_ATTACKS = {}


def _pose_from_params(p, ref):
    """Build a pose dict from joint parameters (degrees). Right arm: shoulder
    flex (world X), abduction (world Y), elbow flex, wrist deviation; torso
    bend/twist. Limits are applied by the caller's parameter ranges."""
    X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
    L = lambda deg: (X, deg, 'local')
    pose = {k: list(v) for k, v in ref.items()}
    pose['RightUpperArm'] = [(Y, -9 + p['abd'], 'world'), (X, p['flex'], 'world')]
    pose['RightLowerArm'] = [L(p['elbow'])]
    pose['RightHand'] = [L(p['wrist'])]
    pose['UpperTorso'] = [(X, p['bend'], 'world'), (Z, p['twist'], 'world')]
    pose['LowerTorso'] = [(X, p['bend'] * 0.4, 'world'), (Z, p['twist'] * 0.35, 'world')]
    return pose


def _staff_line(arm):
    pb = arm.pose.bones['Staff']
    M = arm.matrix_world @ pb.matrix
    g = M.to_translation()
    d = (M.to_3x3() @ Vector((0, 1, 0))).normalized()
    t_foot = (STAFF_GRIP - STAFF_FOOT).length
    top_len = 13.9 - t_foot
    return g, d, g - d * t_foot, g + d * top_len


def _seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(1e-9, ab.length_squared)))
    return (a + ab * t - p).length


def _clearance(arm, g, d, foot, top):
    """Proxy body clearance of the staff (studs): torso and neck capsules,
    head sphere, legs, left arm. The fist region is excluded."""
    P = lambda n, tail=False: arm.matrix_world @ (arm.pose.bones[n].tail if tail
                                                  else arm.pose.bones[n].head)
    caps = [(P('LowerTorso'), P('UpperTorso', True), 2.05),
            (P('Head'), P('Head', True), 1.55),
            (P('LeftUpperLeg'), P('LeftLowerLeg', True), 1.15),
            (P('RightUpperLeg'), P('RightLowerLeg', True), 1.15),
            (P('LeftUpperArm'), P('LeftLowerArm', True), 1.15),
            (P('RightUpperArm'), P('RightUpperArm', True), 1.0)]
    worst = 9e9
    for k in range(41):
        q = foot.lerp(top, k / 40)
        if (q - g).length < 1.1:
            continue
        for a, b, r in caps:
            worst = min(worst, _seg_dist(q, a, b) - r)
    return worst


def solve_attack(arm, name, init, ranges, objective, rounds=3, step=5):
    """Coordinate-descent over joint parameters within anatomical ranges."""
    ref = {bn: [(ax, -ang, 'world')] for bn, (ax, ang) in REST_SPREAD.items()}
    p = dict(init)

    def score(pp):
        apply_pose(arm, _pose_from_params(pp, ref))
        g, d, foot, top = _staff_line(arm)
        clr = _clearance(arm, g, d, foot, top)
        s = objective(g, d, foot, top)
        if clr < 0.35:
            s += (0.35 - clr) * 40.0
        return s, clr
    best, bclr = score(p)
    for r in range(rounds):
        stp = step if r < rounds - 1 else step / 2.5
        for k, (lo, hi) in ranges.items():
            v = lo
            while v <= hi + 1e-6:
                q = dict(p)
                q[k] = v
                s, c = score(q)
                if s < best:
                    best, bclr, p = s, c, q
                v += stp
    pose = _pose_from_params(p, ref)
    apply_pose(arm, pose)
    g, d, foot, top = _staff_line(arm)
    SOLVED_ATTACKS[name] = dict(params={k: round(v, 1) for k, v in p.items()},
                                pose=pose, grip=[round(c, 3) for c in g],
                                staff_dir=[round(c, 3) for c in d],
                                foot=[round(c, 3) for c in foot], top=[round(c, 3) for c in top],
                                proxy_clearance=round(bclr, 3), score=round(best, 3))
    log('solved', name, SOLVED_ATTACKS[name]['params'], 'clearance', round(bclr, 3))
    return pose


def solve_attacks(arm):
    """Overhead raise, ground slam and crook thrust, solved against the real rig."""
    mods = [(o, m) for o in SECTIONS.values() for m in o.modifiers if m.type == 'ARMATURE']
    for o, m in mods:
        m.show_viewport = False
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = None
    R = dict(flex=(-175, 40), abd=(-10, 80), elbow=(-65, 40), wrist=(-28, 28),
             bend=(-25, 12), twist=(-25, 25))
    # overhead: fist as high as possible, staff clear of head and body
    R_over = dict(R, bend=(-14, 8), twist=(-20, 20))
    solve_attack(arm, 'overhead', dict(flex=-120, abd=10, elbow=0, wrist=0, bend=0, twist=0),
                 R_over,
                 lambda g, d, foot, top: -g.z * 1.0 + max(0.0, 10.5 - top.z) * 0.5
                 + max(0.0, 11.0 - max(foot.z, top.z)) * 0.3)
    # slam: staff foot driven into the ground in front, fist at chest height
    R_slam = dict(R, bend=(8, 25), twist=(-20, 10))
    solve_attack(arm, 'slam', dict(flex=-30, abd=15, elbow=0, wrist=0, bend=15, twist=-5),
                 R_slam,
                 lambda g, d, foot, top: abs(foot.z - 0.15) * 3.0 + abs(foot.y + 4.6) * 1.2
                 + abs(foot.x + 3.9) * 0.6 + abs(g.z - 5.8) * 0.6)
    # thrust: crook end leading forward at chest height, staff near level
    solve_attack(arm, 'thrust', dict(flex=-40, abd=5, elbow=-50, wrist=0, bend=-8, twist=-12), R,
                 lambda g, d, foot, top: top.y * 0.6 + abs(top.z - 8.5) * 0.8
                 + abs(d.z - 0.25) * 4.0 + abs(top.x + 1.5) * 0.2)
    for o, m in mods:
        m.show_viewport = True
    ref = {bn: [(ax, -ang, 'world')] for bn, (ax, ang) in REST_SPREAD.items()}
    apply_pose(arm, ref)
    (HERE / 'AttackPoses.json').write_text(json.dumps(
        {k: {kk: vv for kk, vv in v.items() if kk != 'pose'} for k, v in SOLVED_ATTACKS.items()},
        indent=2))


# ================================================================= attack check
ATTACK_POSES = None


def attack_poses():
    """Staff attack key poses: the right arm/torso come from solve_attacks
    (aimed against the real rig with anatomical joint ranges); secondary
    motion (head, left arm, legs, apron) is layered on. The Staff bone never
    rotates relative to the hand, so the fist stays closed on the shaft."""
    X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
    L = lambda deg: (X, deg, 'local')
    ref = {bn: [(ax, -ang, 'world')] for bn, (ax, ang) in REST_SPREAD.items()}
    base_left = ref['LeftUpperArm']

    def with_extra(key, extra):
        pose = {k: list(v) for k, v in SOLVED_ATTACKS[key]['pose'].items()}
        for k, v in extra.items():
            pose[k] = pose.get(k, []) + v if k == 'LeftUpperArm' else v
        return pose
    return [
        ('Rest (reference pose)', dict(ref)),
        ('Staff raised overhead', with_extra('overhead', {
            'Head': [(X, 8, 'world')], 'LeftUpperArm': [(X, 18, 'world')]})),
        ('Staff slammed down', with_extra('slam', {
            'Head': [(X, 10, 'world')], 'LeftUpperArm': [(Y, -18, 'world')],
            'RightUpperLeg': [(X, -16, 'world')], 'RightLowerLeg': [L(22)],
            'Apron_1': [(X, -10, 'world')]})),
        ('Forward thrust, crook first', with_extra('thrust', {
            'LeftUpperArm': [(X, 24, 'world')],
            'LeftUpperLeg': [(X, -18, 'world')], 'LeftLowerLeg': [L(16)]})),
    ]


def apply_pose(arm, pose):
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        q = Quaternion()
        for axis, deg, space in pose.get(pb.name, []):
            q = q @ local_q(arm, pb.name, axis, deg, space)
        pb.rotation_quaternion = q
        pb.location = (0, 0, 0)
    bpy.context.view_layer.update()


def evaluated_verts(o):
    dg = bpy.context.evaluated_depsgraph_get()
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    vs = [oe.matrix_world @ v.co for v in me.vertices]
    tris = [tuple(t.vertices) for t in me.loop_triangles] if me.loop_triangles else []
    if not tris:
        me.calc_loop_triangles()
        tris = [tuple(t.vertices) for t in me.loop_triangles]
    oe.to_mesh_clear()
    return vs, tris


def staff_frame(arm):
    pb = arm.pose.bones['Staff']
    M = arm.matrix_world @ pb.matrix
    return M


def grip_metrics(arm, tag):
    """Finger/palm contact with the shaft, measured in the Staff bone's frame:
    radial distance of every finger vertex from the shaft axis minus the
    shaft's corner radius (negative = the finger surface dips into the
    shaft's corner chamfer)."""
    body = SECTIONS['Body']
    vs, _ = evaluated_verts(body)
    M = staff_frame(arm)
    Mi = M.inverted()
    groups = {vg.index: vg.name for vg in body.vertex_groups}
    out = {}
    corner_r = math.hypot(STAFF_W / 2, STAFF_W / 2 - STAFF_W * 0.22)
    for f in FINGERS:
        names = {f'Right{f}1', f'Right{f}2', f'Right{f}3'}
        rad, loc_pts = [], []
        for v, p in zip(body.data.vertices, vs):
            w = sum(g.weight for g in v.groups if groups[g.group] in names)
            if w < 0.5:
                continue
            q = Mi @ p
            rad.append(math.hypot(q.x, q.z))
            loc_pts.append(q)
        if not rad:
            continue
        out[f] = dict(min_surface_clearance=round(min(rad) - corner_r, 4),
                      inner_radius=round(min(rad), 4), n=len(rad))
        GRIP_LOCAL.setdefault(f, loc_pts)
    # rigid-attachment drift vs the rest measurement
    drift = 0.0
    for f in FINGERS:
        names = {f'Right{f}1', f'Right{f}2', f'Right{f}3'}
        cur = []
        for v, p in zip(body.data.vertices, vs):
            w = sum(g.weight for g in v.groups if groups[g.group] in names)
            if w >= 0.5:
                cur.append(Mi @ p)
        for a_, b_ in zip(GRIP_LOCAL[f], cur):
            drift = max(drift, (a_ - b_).length)
    out['max_finger_drift_in_staff_frame'] = round(drift, 6)
    return out


GRIP_LOCAL = {}


RIGHT_ARM_BONES = None


def staff_body_clearance():
    """Minimum distance from the staff surface to every body surface that is
    not carried by the right arm (torso, head, legs, kilt, left arm), and the
    number of staff vertices that end up inside those surfaces."""
    global RIGHT_ARM_BONES
    if RIGHT_ARM_BONES is None:
        arm = bpy.data.objects[RIG]
        keep = set()
        for bn in arm.data.bones:
            x = bn
            while x is not None:
                if x.name == 'RightUpperArm':
                    keep.add(bn.name)
                    break
                x = x.parent
        RIGHT_ARM_BONES = keep
    svs, _ = evaluated_verts(SECTIONS['Staff'])
    worst, worst_where, inside = 9e9, None, 0
    for sec in ('Body', 'Bandages', 'Waist', 'Head'):
        o = SECTIONS[sec]
        vs, tris = evaluated_verts(o)
        names = {vg.index: vg.name for vg in o.vertex_groups}
        carried = []
        for v in o.data.vertices:
            carried.append(sum(g.weight for g in v.groups
                               if names.get(g.group) in RIGHT_ARM_BONES) > 0.5)
        tri_keep = [t for t in tris if not any(carried[i] for i in t)]
        if not tri_keep:
            continue
        bvh = BVHTree.FromPolygons(vs, tri_keep, epsilon=0.0)
        for p in svs:
            loc, nrm, idx, dist = bvh.find_nearest(p, 50.0)
            if loc is None:
                continue
            if (p - loc).dot(nrm) < 0 and dist < 0.6:
                inside += 1
            if dist < worst:
                worst, worst_where = dist, sec
    return dict(min_distance_to_body=round(worst, 4), nearest_section=worst_where,
                staff_verts_inside_body=inside)


HAND_CENTER = [Vector()]


def attack_check(arm):
    P = HERE / 'previews'
    cam = scene.camera
    keep = cam.matrix_world.copy(), cam.data.lens, cam.data.type, cam.data.ortho_scale
    arm.animation_data.action = None
    report = {'poses': []}
    fronts, closes = [], []
    GRIP_LOCAL.clear()
    for i, (name, pose) in enumerate(attack_poses()):
        apply_pose(arm, pose)
        M = staff_frame(arm)
        HAND_CENTER[0] = M.to_translation()
        gm = grip_metrics(arm, name)
        sc = staff_body_clearance()
        report['poses'].append(dict(pose=name, grip=gm, staff=sc))
        # full-body front view
        scene.render.resolution_x, scene.render.resolution_y = 520, 700
        cam_look(cam, (-4, -34, 7.5), (-0.6, 0, 7.0), ortho=19.5)
        pf = WORK / f'atk_front_{i}.png'
        render_to(pf, 24)
        fronts.append(pf)
        # grip close-up, from the front-outer side of the fist
        g = M.to_translation()
        axis = M.to_3x3() @ Vector((0, 1, 0))
        side = axis.cross(Vector((0, 0, 1)))
        if side.length < 0.2:
            side = Vector((1, 0, 0))
        eye = g + Vector((-2.6, -4.6, 1.2))
        cam_look(cam, eye, g, lens=70)
        pc = WORK / f'atk_close_{i}.png'
        render_to(pc, 32)
        closes.append(pc)
    tile_images(fronts + closes, 4, P / 'AttackCheck_Staff.png')
    set_action(arm, 'ReferencePose')
    cam.matrix_world, cam.data.lens, cam.data.type, cam.data.ortho_scale = keep
    scene.render.resolution_x, scene.render.resolution_y = IMG_W, IMG_H
    report['note'] = ('Staff bone is never rotated relative to RightHand; finger drift is '
                      'measured in the Staff bone frame. Negative surface clearance means the '
                      'finger surface dips into the chamfered corner of the square shaft.')
    (HERE / 'GripChecks.json').write_text(json.dumps(report, indent=2))
    log('attack check', json.dumps(report)[:400])


# ================================================================= exports
def export_all(arm):
    E = HERE / 'exports'
    meshes = list(SECTIONS.values())

    def sel(objs):
        bpy.ops.object.select_all(action='DESELECT')
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
    # rest mesh + armature + embedded textures (no animation)
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_quaternion = Quaternion()
        pb.location = (0, 0, 0)
    scene.frame_set(1)
    sel([arm] + meshes)
    common = dict(use_selection=True, add_leaf_bones=False, axis_forward='-Z', axis_up='Y',
                  use_armature_deform_only=True, mesh_smooth_type='OFF',
                  use_mesh_modifiers=False, bake_space_transform=False)
    bpy.ops.export_scene.fbx(filepath=str(E / 'fbx' / f'{NAME}.fbx'),
                             object_types={'ARMATURE', 'MESH'}, bake_anim=False,
                             path_mode='COPY', embed_textures=True, **common)
    for act in ('ReferencePose', 'RigTest_ROM'):
        A = bpy.data.actions[act]
        bind_action(arm, A)
        f0, f1 = int(A.frame_range[0]), int(A.frame_range[1])
        # The FBX exporter writes each bone node's transform from the pose at
        # the CURRENT frame, and an armature-only FBX has no bind pose, so the
        # importer takes that as the rest pose. The current frame must show
        # the true rest pose: a held clip (ReferencePose) gets a temporary rest
        # key one frame before its range, removed again after export.
        temp_key = False
        if act == 'ReferencePose':
            for pb in arm.pose.bones:
                pb.rotation_quaternion = Quaternion()
                pb.location = (0, 0, 0)
                pb.keyframe_insert('rotation_quaternion', frame=f0 - 1)
                pb.keyframe_insert('location', frame=f0 - 1)
            temp_key = True
        scene.frame_start, scene.frame_end = f0, f1
        scene.render.fps = FPS
        scene.frame_set(f0 - 1 if temp_key else f0)
        sel([arm])
        bpy.ops.export_scene.fbx(filepath=str(E / 'fbx' / f'{NAME}_{act}.fbx'),
                                 object_types={'ARMATURE'}, bake_anim=True,
                                 bake_anim_use_all_actions=False,
                                 bake_anim_use_nla_strips=False, bake_anim_simplify_factor=0.0,
                                 bake_anim_use_all_bones=True, **common)
        if temp_key:
            for pb in arm.pose.bones:
                pb.keyframe_delete('rotation_quaternion', frame=f0 - 1)
                pb.keyframe_delete('location', frame=f0 - 1)
            A.frame_range = (f0, f1)
    arm.animation_data.action = None
    scene.frame_start, scene.frame_end = 1, int(bpy.data.actions['RigTest_ROM'].frame_range[1])
    sel([arm] + meshes)
    bpy.ops.export_scene.gltf(filepath=str(E / 'glb' / f'{NAME}.glb'), export_format='GLB',
                              use_selection=True, export_animations=True,
                              export_animation_mode='ACTIONS', export_skins=True,
                              export_def_bones=True, export_yup=True, export_apply=False,
                              export_normals=True, export_image_format='AUTO')
    arm.animation_data.action = bpy.data.actions['ReferencePose']
    scene.frame_set(1)
    log('exported')


# ================================================================= main
def build_sculpt():
    build_materials()
    solve_right_grip()
    for fn in BUILDERS:
        t = time.time()
        fn()
        log('built', fn.__name__, f'{time.time() - t:.1f}s')
    conform_body(bpy.data.objects['Body_Skin'])
    for p in PARTS:
        if p['mat'] == 'skin' and p['obj'].name == 'Body_Skin':
            soften_facets(p['obj'], 0.58)
    for fn in POST_BUILDERS:
        t = time.time()
        fn()
        log('built', fn.__name__, f'{time.time() - t:.1f}s')
    for i, p in enumerate(PARTS):
        add_facet_rand(p['obj'], i * 7919)


BUILDERS = [build_body, build_head, build_nemes, build_uraeus, build_collar, build_belt,
            build_kilt, build_staff, build_bands, build_hand_R, build_hand_L, build_feet]
POST_BUILDERS = [build_bandages]


def write_reports(arm):
    polys = {}
    for sec, o in SECTIONS.items():
        polys[o.name] = dict(triangles=tri_count(o), vertices=len(o.data.vertices),
                             faces=len(o.data.polygons))
    total = sum(v['triangles'] for v in polys.values())
    (HERE / 'polygon-report.json').write_text(json.dumps(
        dict(sections=polys, total_triangles=total, per_mesh_limit=20000,
             all_under_limit=all(v['triangles'] < 20000 for v in polys.values())), indent=2))
    allv = [o.matrix_world @ v.co for o in SECTIONS.values() for v in o.data.vertices]
    body = [o.matrix_world @ v.co for s, o in SECTIONS.items() if s != 'Staff'
            for v in o.data.vertices]
    staff = [SECTIONS['Staff'].matrix_world @ v.co for v in SECTIONS['Staff'].data.vertices]
    tex = []
    for f in sorted((HERE / 'textures').glob('*.png')):
        tex.append(dict(file=f'textures/{f.name}',
                        sha256=hashlib.sha256(f.read_bytes()).hexdigest().upper()))
    hb = arm.data.bones['RightHand']
    grip_local = hb.matrix_local.inverted() @ STAFF_GRIP
    man = dict(
        asset=NAME, units='1 Blender unit = 1 Roblox stud', front='-Y (Blender)', up='+Z',
        reference=dict(file='source/Pharaoh_Reference.webp',
                       sha256='BDB705682E45F1C0B2C9BF03BE73091A6C3202D56C4F90FA904E8B1E79253D8A',
                       camera=CAM),
        pose_measured='rest pose (arms spread 9 deg) unless noted',
        dimensions=dict(
            height_rest_top=round(max(v.z for v in body), 3),
            width_x=round(max(v.x for v in body) - min(v.x for v in body), 3),
            depth_y=round(max(v.y for v in body) - min(v.y for v in body), 3),
            staff_length=round((max(staff, key=lambda v: v.z) - STAFF_FOOT).length, 3),
            staff_top_z=round(max(v.z for v in staff), 3),
            staff_width=STAFF_W),
        staff_grip=dict(world_reference_pose=[round(c, 4) for c in STAFF_GRIP],
                        staff_bone_head='Staff bone head = grip point on the staff axis',
                        offset_in_RightHand_rest_space=[round(c, 4) for c in grip_local],
                        staff_axis_world=[round(c, 4) for c in STAFF_DIR],
                        staff_foot_world=[round(c, 4) for c in STAFF_FOOT]),
        bones=[dict(name=bn.name, parent=bn.parent.name if bn.parent else None,
                    deform=bn.use_deform,
                    head=[round(c, 4) for c in bn.head_local],
                    tail=[round(c, 4) for c in bn.tail_local]) for bn in arm.data.bones],
        sections={s: dict(object=o.name, triangles=tri_count(o)) for s, o in SECTIONS.items()},
        textures=tex,
        actions=['ReferencePose', 'RigTest_ROM'],
        rom_keys=[dict(frame=f, pose=n) for f, n in ROM_KEYS],
    )
    (HERE / 'manifest.json').write_text(json.dumps(man, indent=2))


def main():
    build_sculpt()
    make_camera()
    make_lights()
    make_ground()
    setup_render('CYCLES', 24 if STAGE == 'sculpt' else SAMPLES)
    if STAGE == 'sculpt':
        render_to(WORK / 'probe.png')
        render_mask(WORK / 'probe_mask.png')
        if os.environ.get('VIEWS') == '1':
            review_views(WORK)
        for tag in [t for t in os.environ.get('ZOOM', '').split(',') if t]:
            render_zoom(tag)
        bpy.ops.wm.save_as_mainfile(filepath=str(WORK / 'sculpt.blend'))
        log('SCULPT_DONE')
        return
    arm = build_armature()
    skin_all(arm)
    join_sections()
    bake_sections(int(os.environ.get('TEX', '2048')))
    apply_rest_pose(arm)
    bind(arm)
    solve_attacks(arm)
    make_actions(arm)
    setup_render('CYCLES', SAMPLES)
    set_action(arm, 'ReferencePose')
    render_to(HERE / 'previews' / 'Reference_Match.png')
    render_mask(HERE / 'previews' / 'Reference_Match_mask.png')
    if PROBE_ONLY:
        bpy.ops.wm.save_as_mainfile(filepath=str(WORK / 'probe_full.blend'))
        log('PROBE_DONE')
        return
    render_reviews(arm)
    attack_check(arm)
    export_all(arm)
    write_reports(arm)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE / f'{NAME}.blend'), compress=True)
    log('FULL_DONE')

main()
