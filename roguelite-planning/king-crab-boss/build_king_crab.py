"""Giant King Crab (Beach Cove boss) -- faithful rebuild of the supplied reference.

Run under Blender 5.2, headless:
    blender -b --factory-startup --python build_king_crab.py            # full build
    set KC_MODE=probe  (PowerShell: $env:KC_MODE='probe')                  # fast compare loop

Self-contained on purpose: nothing here exec()s or imports a sibling kit.
The only external inputs are this folder's own source/camera.json (the solved
reference camera, written by solve_camera.py) and the untouched reference image.

Conventions
-----------
* 1 Blender unit = 1 Roblox stud, authored at final size.
* Z up, the crab faces -Y, +X is the crab's LEFT (viewer's right in the
  reference). "_R" parts/bones are the crab's right = viewer's left.
* Two frames matter:
    - the REST pose: body level, legs in a mirror-symmetric stance, claws a
      little relaxed. Meshes are bound here.
    - the REFERENCE pose (action ReferencePose): the body rolled 5.86 deg right
      side up (measured, see solve_camera.py), legs planted where the image
      plants them, claws raised, eyes on the camera.
  Body-mounted parts are authored directly in the level body frame. Leg and
  claw segments are authored in the reference pose (where the image can be
  measured) or in bone-local space, and carried to rest through their bone:
      v_rest = M_rest(bone) @ M_ref(bone)^-1 @ v_ref
  Every exoskeleton segment belongs to exactly one bone (rigid weights).
"""
import bpy, bmesh, math, json, os, random, sys, hashlib, time
import numpy as np
from pathlib import Path
from mathutils import Vector, Matrix, Quaternion, Euler

T0 = time.time()
OUT = Path(__file__).resolve().parent
MODE = os.environ.get('KC_MODE', 'full')
PROBE = MODE == 'probe'
WORK = OUT / '_work'
for sub in ('textures', 'previews', 'exports/fbx', 'exports/glb', '_work'):
    (OUT / sub).mkdir(parents=True, exist_ok=True)
CAM = json.loads((OUT / 'source' / 'camera.json').read_text())
REF_IMG = OUT / 'source' / 'king-crab-reference.webp'
RNG = random.Random(20260928)


def log(*a):
    print(f'[{time.time() - T0:7.1f}s]', *a, flush=True)


# =============================================================== camera maths
# Identical to solve_camera.py so geometry can be placed by back-projecting
# measured reference pixels.
CAM_P = np.array(CAM['camera_location'])
CAM_A = math.radians(CAM['yaw_deg'])
CAM_PH = math.radians(CAM['pitch_deg'])
CAM_F = CAM['f_px']
BODY_ROLL = math.radians(CAM['body_roll_deg'])
ROLL_PIVOT = Vector((0.0, 0.0, CAM['body_roll_pivot_z']))
_d = np.array([math.sin(CAM_A) * math.cos(CAM_PH), math.cos(CAM_A) * math.cos(CAM_PH), math.sin(CAM_PH)])
_r = np.array([math.cos(CAM_A), -math.sin(CAM_A), 0.0])
_u = np.cross(_r, _d)


def img_ray(uv):
    v = _d + _r * (uv[0] - 768) / CAM_F - _u * (uv[1] - 512) / CAM_F
    return v / np.linalg.norm(v)


def px_on_plane(uv, n, c):
    """World point where the ray through reference pixel uv meets plane n.x = c."""
    v = img_ray(uv)
    n = np.asarray(n, float)
    t = (c - n @ CAM_P) / (n @ v)
    return Vector(CAM_P + v * t)


def px_on_plane_pt(uv, n, p0):
    n = np.asarray(n, float)
    return px_on_plane(uv, n, float(n @ np.asarray(p0, float)))


def project(X):
    q = np.asarray(X, float) - CAM_P
    return (768 + CAM_F * (q @ _r) / (q @ _d), 512 - CAM_F * (q @ _u) / (q @ _d))


def cam_dir_from(p):
    v = Vector(CAM_P) - Vector(p)
    return v.normalized()


BODY_REF = (Matrix.Translation(ROLL_PIVOT) @ Matrix.Rotation(BODY_ROLL, 4, 'Y')
            @ Matrix.Translation(-ROLL_PIVOT))
# A positive rotation about +Y lowers +X and lifts -X, which is the measured
# lean: the crab's right side (viewer's left) up.
BODY_REF_INV = BODY_REF.inverted()


# ================================================================ scene reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'NONE'
COLL = scene.collection


def activate(o):
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


# ================================================================== materials
def srgb(*c):
    def lin(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return tuple(lin(v) for v in c)


# Per-channel gains measured by compare_reference.py (reference linear mean /
# render linear mean, per material region). Multiplied in and re-measured each
# pass; the eyedropped colours below stay readable.
CALIBRATION = {
    'red_Body': (1.344, 1.347, 1.373),
    'red_ClawR': (0.658, 0.749, 1.120),
    'red_ClawL': (0.799, 0.979, 1.315),
    'red_Legs': (0.710, 0.916, 1.360),
    'beige_Body': (0.937, 1.047, 1.192),
    'beige_Belly': (0.558, 0.683, 0.907),
    'beige_ClawR': (0.818, 0.991, 1.268),
    'beige_ClawL': (0.700, 0.795, 0.994),
    'beige_Legs': (0.893, 1.169, 1.634),
    'eye': (0.950, 0.887, 0.786),
}


def cal(key, *c):
    g = CALIBRATION.get(key, (1, 1, 1))
    return tuple(min(1.0, v * k) for v, k in zip(srgb(*c), g))


PALETTE = {}


# Eyedropped from the reference (sRGB): lit / mid / shadow / deepest.
BASE_RED = {'red_hi': (240, 112, 76), 'red_mid': (204, 64, 50), 'red_lo': (160, 46, 42),
            'red_deep': (120, 34, 32)}
BASE_BEIGE = {'beige_hi': (240, 206, 168), 'beige_mid': (222, 180, 136), 'beige_lo': (186, 142, 102)}


def palette_for(red_key='red_Body', beige_key='beige_Body'):
    pal = {k: cal(red_key, *v) for k, v in BASE_RED.items()}
    pal.update({k: cal(beige_key, *v) for k, v in BASE_BEIGE.items()})
    pal.update({'eye_white': cal('eye', 252, 250, 242), 'pupil': srgb(26, 20, 20),
                'cavity': srgb(70, 52, 40)})
    return pal


def build_palette():
    PALETTE.update(palette_for())


build_palette()
# Paint recipe: patch density (cells per stud), how strongly up-facing planes
# lean orange / down-facing maroon, the ramp cuts, and the chip threshold.
PAINT = {'cell': 0.80, 'up_bias': 0.32, 'lo_cut': 0.18, 'hi_cut': 0.90, 'chip': 0.62}
if os.environ.get('KC_PAINT'):
    PAINT.update(json.loads(os.environ['KC_PAINT']))
MATS = {}
# Painted feature blobs in REST space, filled in by locate_paint() from pixel
# positions measured on the reference: (centre, radius, strength).
CHIP_BLOBS = []        # beige worn chips on the red shell
# Red paint on beige, body frame (rest == body): the carapace colour running
# down over the tops of the flanking mouth plates, and the small red nick on
# the top of the viewer-left tooth.
STAIN_BLOBS = [((-1.85, -4.62, 5.55), 0.62, 1.0), ((1.85, -4.62, 5.55), 0.62, 1.0),
               ((-2.2, -4.45, 5.62), 0.55, 1.0), ((2.2, -4.45, 5.62), 0.55, 1.0),
               ((-2.9, -4.05, 5.55), 0.7, 1.0), ((2.9, -4.05, 5.55), 0.7, 1.0),
               ((-0.84, -5.10, 5.72), 0.10, 1.0)]


class NodeKit:
    """Small wrapper so the painterly shaders read as recipes."""

    def __init__(self, nt):
        self.nt = nt

    def node(self, kind, **inputs):
        n = self.nt.nodes.new(kind)
        for k, v in inputs.items():
            self.set(n.inputs[k], v)
        return n

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

    def noise(self, vec, scale, detail=2.0, rough=0.5, w=0.0, dist=0.0):
        n = self.nt.nodes.new('ShaderNodeTexNoise')
        n.noise_dimensions = '4D'
        self.set(n.inputs['Vector'], vec)
        n.inputs['Scale'].default_value = scale
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough
        n.inputs['W'].default_value = w
        n.inputs['Distortion'].default_value = dist
        return n

    def warp(self, vec, amount, scale, w=0.0):
        n = self.noise(vec, scale, 2.0, 0.5, w)
        sc = self.vmath('SCALE', n.outputs['Color'], None)
        sc.inputs['Scale'].default_value = amount
        off = self.vmath('SUBTRACT', sc.outputs[0], (amount * 0.5,) * 3)
        return self.vmath('ADD', vec, off.outputs[0]).outputs[0]

    def vmath(self, op, a, b):
        m = self.nt.nodes.new('ShaderNodeVectorMath')
        m.operation = op
        self.set(m.inputs[0], a)
        if b is not None:
            self.set(m.inputs[1], b)
        return m

    def math(self, op, a, b=None, c=None):
        m = self.nt.nodes.new('ShaderNodeMath')
        m.operation = op
        self.set(m.inputs[0], a)
        if b is not None:
            self.set(m.inputs[1], b)
        if c is not None:
            self.set(m.inputs[2], c)
        return m.outputs[0]

    def ramp(self, fac, stops, interp='LINEAR'):
        r = self.nt.nodes.new('ShaderNodeValToRGB')
        r.color_ramp.interpolation = interp
        els = r.color_ramp.elements
        while len(els) > 1:
            els.remove(els[-1])
        for i, (pos, col) in enumerate(stops):
            e = els[0] if i == 0 else els.new(pos)
            e.position = pos
            e.color = (*col, 1) if len(col) == 3 else col
        self.set(r.inputs[0], fac)
        return r.outputs[0]

    def step(self, fac, lo, hi):
        """Smooth threshold -> 0..1."""
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
        self.set(m.inputs[7], b)
        return m.outputs[2]

    def mul_rgb(self, col, fac):
        m = self.nt.nodes.new('ShaderNodeMix')
        m.data_type = 'RGBA'
        m.blend_type = 'MULTIPLY'
        m.clamp_factor = True
        m.inputs['Factor'].default_value = 1.0
        self.set(m.inputs[6], col)
        self.set(m.inputs[7], fac)
        return m.outputs[2]

    def blobs(self, vec, blobs):
        """Union of soft spheres (centre, radius, strength) in rest space."""
        best = None
        for (c, rad, k) in blobs:
            d = self.vmath('DISTANCE', vec, tuple(c)).outputs['Value']
            m = self.nt.nodes.new('ShaderNodeMapRange')
            m.clamp = True
            self.set(m.inputs['Value'], d)
            m.inputs['From Min'].default_value = rad
            m.inputs['From Max'].default_value = rad * 0.35
            m.inputs['To Max'].default_value = k
            best = m.outputs[0] if best is None else self.math('MAXIMUM', best, m.outputs[0])
        return best


def new_mat(name):
    # Rebuilt in place when it already exists, so parts keep their slots when
    # the paint recipe is regenerated after chip positions are measured.
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    if hasattr(m, 'use_nodes') and not m.node_tree:
        m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.name = 'Output'
    bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bs.name = 'BSDF'
    bs.inputs['Roughness'].default_value = 0.88
    for key in ('Specular IOR Level', 'Specular'):
        if key in bs.inputs:
            bs.inputs[key].default_value = 0.14
    em = nt.nodes.new('ShaderNodeEmission')
    em.name = 'BakeEmit'
    nt.links.new(bs.outputs[0], out.inputs['Surface'])
    return m, nt, bs, em


def finish(m, nt, bs, em, col):
    nt.links.new(col, bs.inputs['Base Color'])
    nt.links.new(col, em.inputs['Color'])
    return m


def shell_material(key, pal=None):
    """Red exoskeleton: broad posterised patches of orange, crimson and maroon
    with brushy warped edges, small darker dabs, per-facet tonal shifts, a
    cavity shade, worn beige chips on convex edges and at measured spots."""
    pal = pal or PALETTE
    m, nt, bs, em = new_mat(key)
    K = NodeKit(nt)
    P = K.attr('restP').outputs['Vector']
    facet = K.attr('facet').outputs['Fac']
    N = K.attr('restN').outputs['Vector']
    up = K.vmath('DOT_PRODUCT', N, (0.0, 0.0, 1.0)).outputs['Value']
    # Cellular paint patches: a warped Voronoi gives each ~1-stud patch one
    # flat colour with angular, brushy borders -- the reference's broken
    # posterised strokes. Up-facing planes lean orange and down-facing planes
    # maroon, the hand-painted habit of baking light into the colour.
    Pw = K.warp(K.warp(P, 0.55, 0.8, 1.3), 0.16, 3.4, 4.1)
    vor = K.node('ShaderNodeTexVoronoi')
    vor.voronoi_dimensions = '3D'
    K.set(vor.inputs['Vector'], Pw)
    vor.inputs['Scale'].default_value = PAINT['cell']
    cell = K.node('ShaderNodeSeparateColor')
    K.set(cell.inputs[0], vor.outputs['Color'])
    t = K.math('MULTIPLY_ADD', up, PAINT['up_bias'], cell.outputs['Red'])
    col = K.ramp(t, [(0.0, pal['red_lo']), (PAINT['lo_cut'], pal['red_lo']),
                     (PAINT['lo_cut'] + 0.02, pal['red_mid']), (PAINT['hi_cut'], pal['red_mid']),
                     (PAINT['hi_cut'] + 0.02, pal['red_hi']), (1.6, pal['red_hi'])])
    # medium patches: brushy value shifts inside each plane, not new colours
    vor2 = K.node('ShaderNodeTexVoronoi')
    vor2.voronoi_dimensions = '3D'
    K.set(vor2.inputs['Vector'], K.warp(P, 0.20, 2.6, 7.7))
    vor2.inputs['Scale'].default_value = PAINT['cell'] * 2.4
    cell2 = K.node('ShaderNodeSeparateColor')
    K.set(cell2.inputs[0], vor2.outputs['Color'])
    t2 = K.math('MULTIPLY_ADD', up, PAINT['up_bias'] * 0.5, cell2.outputs['Green'])
    col = K.mix(K.math('MULTIPLY', K.step(t2, 0.86, 0.88), 0.55), col, pal['red_hi'])
    col = K.mix(K.math('MULTIPLY', K.step(t2, 0.16, 0.14), 0.55), col, pal['red_lo'])
    dab = K.noise(K.warp(P, 0.12, 5.0, 9.1), 2.2, 1.5, 0.5, 8.4).outputs['Fac']
    col = K.mix(K.math('MULTIPLY', K.step(dab, 0.72, 0.735), 0.5), col, pal['red_deep'])
    lowf = K.noise(P, 0.22, 2.0, 0.5, 6.2).outputs['Fac']
    lv = K.math('MULTIPLY_ADD', lowf, 0.16, 0.92)
    col = K.mul_rgb(col, K.node('ShaderNodeCombineColor', Red=lv, Green=lv, Blue=lv).outputs[0])
    # per-facet tone: +-7 % value so neighbouring planes read as cut facets
    tone = K.math('MULTIPLY_ADD', facet, 0.18, 0.91)
    col = K.mul_rgb(col, K.node('ShaderNodeCombineColor', Red=tone, Green=tone, Blue=tone).outputs[0])
    # Worn cream chips. A wide Bevel-node mask finds convex edges and corners
    # (AO drops concave creases out), a ragged noise breaks it into irregular
    # patches that run onto the faces, and the measured CHIP_BLOBS add the
    # big chips the reference paints at specific spots. A thin darker rim
    # outlines each chip, as in the reference's painted wear.
    bev = K.node('ShaderNodeBevel')
    bev.inputs['Radius'].default_value = 0.26
    geo = K.node('ShaderNodeNewGeometry')
    dotn = K.vmath('DOT_PRODUCT', bev.outputs['Normal'], geo.outputs['True Normal']).outputs['Value']
    ao_e = K.node('ShaderNodeAmbientOcclusion')
    ao_e.inputs['Distance'].default_value = 0.35
    ao_e.samples = 8
    convex = K.step(ao_e.outputs['AO'], 0.78, 0.95)
    # thresholds sit above the shallow creases between loft rings, so only
    # real corners (>~35 degrees) wear
    edge_w = K.math('MULTIPLY', K.step(K.math('SUBTRACT', 1.0, dotn), 0.035, 0.09), convex)
    ragged = K.noise(K.warp(K.warp(P, 0.45, 2.2, 2.2), 0.12, 7.0, 5.1), 1.35, 4.0, 0.70, 6.6).outputs['Fac']
    field = K.math('MULTIPLY', edge_w, K.math('MULTIPLY_ADD', ragged, 1.7, -0.25))
    lone = K.noise(K.warp(P, 0.3, 3.0, 8.8), 1.1, 3.0, 0.65, 12.2).outputs['Fac']
    field = K.math('MAXIMUM', field, K.math('MULTIPLY_ADD', lone, 1.6, -0.80))
    if CHIP_BLOBS:
        # strong two-scale warp and a ragged multiplier turn the round blobs
        # into torn, angular worn patches
        bl = K.blobs(K.warp(K.warp(P, 0.95, 1.3, 3.9), 0.28, 4.5, 1.7), CHIP_BLOBS)
        field = K.math('MAXIMUM', field, K.math('MULTIPLY', bl, K.math('MULTIPLY_ADD', ragged, 1.6, 0.05)))
    chip = K.step(field, PAINT['chip'], PAINT['chip'] + 0.02)
    rim = K.math('SUBTRACT', K.step(field, PAINT['chip'] - 0.07, PAINT['chip'] - 0.03), chip)
    col = K.mix(K.math('MULTIPLY', rim, 0.55), col, pal['red_deep'])
    edge_lit = K.math('MULTIPLY', K.step(K.math('SUBTRACT', 1.0, dotn), 0.03, 0.08), 0.30)
    col = K.mix(K.math('MULTIPLY', edge_lit, convex), col, pal['red_hi'])
    chip_col = K.mix(K.step(K.noise(P, 4.0, 2.0, 0.5, 1.1).outputs['Fac'], 0.45, 0.6),
                     pal['beige_mid'], pal['beige_hi'])
    col = K.mix(chip, col, chip_col)
    # cavity shade
    ao = K.node('ShaderNodeAmbientOcclusion')
    ao.inputs['Distance'].default_value = 0.7
    ao.samples = 12
    shade = K.math('MULTIPLY_ADD', ao.outputs['AO'], 0.30, 0.70)
    col = K.mul_rgb(col, K.node('ShaderNodeCombineColor', Red=shade, Green=shade, Blue=shade).outputs[0])
    MATS[key] = finish(m, nt, bs, em, col)
    return MATS[key]


def plate_material(key, pal=None):
    """Beige plates, fingers and leg tips: sandy cream with soft lighter and
    darker patches, fine darker grain, red paint stains where measured."""
    pal = pal or PALETTE
    m, nt, bs, em = new_mat(key)
    K = NodeKit(nt)
    P = K.attr('restP').outputs['Vector']
    facet = K.attr('facet').outputs['Fac']
    Pw = K.warp(P, 0.4, 1.4, 2.1)
    broad = K.noise(Pw, 0.9, 2.0, 0.5, 1.7).outputs['Fac']
    col = K.ramp(broad, [(0.0, pal['beige_lo']), (0.40, pal['beige_lo']),
                         (0.43, pal['beige_mid']), (0.60, pal['beige_mid']),
                         (0.63, pal['beige_hi']), (1.0, pal['beige_hi'])])
    grain = K.noise(K.warp(P, 0.08, 8.0, 5.5), 6.5, 1.5, 0.5, 3.2).outputs['Fac']
    col = K.mix(K.math('MULTIPLY', K.step(grain, 0.66, 0.69), 0.6), col, pal['beige_lo'])
    tone = K.math('MULTIPLY_ADD', facet, 0.12, 0.94)
    col = K.mul_rgb(col, K.node('ShaderNodeCombineColor', Red=tone, Green=tone, Blue=tone).outputs[0])
    bev = K.node('ShaderNodeBevel')
    bev.inputs['Radius'].default_value = 0.08
    geo = K.node('ShaderNodeNewGeometry')
    dotn = K.vmath('DOT_PRODUCT', bev.outputs['Normal'], geo.outputs['True Normal']).outputs['Value']
    edge_m = K.step(K.math('SUBTRACT', 1.0, dotn), 0.03, 0.08)
    col = K.mix(K.math('MULTIPLY', edge_m, 0.5), col, pal['beige_hi'])
    if STAIN_BLOBS:
        st = K.blobs(K.warp(P, 0.2, 3.0, 6.1), STAIN_BLOBS)
        col = K.mix(K.step(st, 0.42, 0.47), col, pal['red_mid'])
    ao = K.node('ShaderNodeAmbientOcclusion')
    ao.inputs['Distance'].default_value = 0.6
    ao.samples = 12
    shade = K.math('MULTIPLY_ADD', ao.outputs['AO'], 0.38, 0.62)
    col = K.mul_rgb(col, K.node('ShaderNodeCombineColor', Red=shade, Green=shade, Blue=shade).outputs[0])
    MATS[key] = finish(m, nt, bs, em, col)
    return MATS[key]


EYE_AXES = {}          # side -> (rest centre, pupil axis, radius)


def eye_material(key, side, pal=None):
    """White eyeball with a round black pupil and a small catchlight, painted
    about the eye's rest-space forward axis (the Eye bone rotates it)."""
    pal = pal or PALETTE
    m, nt, bs, em = new_mat(key)
    K = NodeKit(nt)
    P = K.attr('restP').outputs['Vector']
    c, axis, rad = EYE_AXES[side]
    d = K.vmath('NORMALIZE', K.vmath('SUBTRACT', P, tuple(c)).outputs[0], None).outputs[0]
    cosang = K.vmath('DOT_PRODUCT', d, tuple(axis)).outputs['Value']
    pupil = K.step(cosang, 0.905, 0.915)            # ~24 degrees
    hl_axis = (Vector(axis) + Vector((-0.20, 0.0, 0.26))).normalized()
    hl = K.step(K.vmath('DOT_PRODUCT', d, tuple(hl_axis)).outputs['Value'], 0.9955, 0.997)
    white = K.mix(K.step(K.vmath('DOT_PRODUCT', d, (0, 0, -1)).outputs['Value'], -0.2, 0.9),
                  pal['eye_white'], tuple(v * 0.82 for v in pal['eye_white']))
    col = K.mix(pupil, white, pal['pupil'])
    col = K.mix(hl, col, (0.95, 0.95, 0.95))
    bs.inputs['Roughness'].default_value = 0.35
    MATS[key] = finish(m, nt, bs, em, col)
    return MATS[key]


def flat_mat(key, color):
    m, nt, bs, em = new_mat(key)
    K = NodeKit(nt)
    P = K.attr('restP').outputs['Vector']
    n = K.noise(P, 1.5, 2.0, 0.5, 0.4).outputs['Fac']
    col = K.mix(K.step(n, 0.3, 0.7), color, tuple(v * 1.25 for v in color))
    MATS[key] = finish(m, nt, bs, em, col)
    return MATS[key]


SECTION_KEYS = ('Body', 'ClawR', 'ClawL', 'Legs')


def section_material(base, sec):
    """The shared recipe with that section's calibrated palette."""
    key = f'{base}_{sec}'
    red_sec = sec if sec in SECTION_KEYS else 'Body'
    if base.startswith('red'):
        pal = palette_for(f'red_{red_sec}', f'beige_{red_sec}')
        return shell_material(key, pal)
    pal = palette_for(f'red_{red_sec}', f'beige_{sec}')
    return plate_material(key, pal)


def make_materials(sections=False):
    shell_material('red')
    shell_material('red_edge')
    plate_material('beige')
    plate_material('beige_edge')
    if sections:
        for sec in SECTION_KEYS:
            for base in ('red', 'red_edge', 'beige', 'beige_edge'):
                section_material(base, sec)
        for base in ('beige', 'beige_edge'):
            section_material(base, 'Belly')
        for side in EYE_AXES:
            eye_material(f'eye_{side}', side, palette_for())
    flat_mat('dark', PALETTE['cavity'])
    flat_mat('red_dark', PALETTE['red_lo'])
    flat_mat('eye', PALETTE['eye_white'])
    flat_mat('pupil', PALETTE['pupil'])


make_materials()

# ============================================================ mesh utilities
PARTS = []          # dicts: obj, bone, section, space ('rest' or 'ref')


def mesh_object(name, verts, faces, mats, bone, section, space='rest', smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.validate(clean_customdata=False)
    me.update()
    ob = bpy.data.objects.new(name, me)
    COLL.objects.link(ob)
    for k in mats:
        ob.data.materials.append(MATS[k])
    for p in ob.data.polygons:
        p.use_smooth = smooth
    PARTS.append({'obj': ob, 'bone': bone, 'section': section, 'space': space})
    return ob


def hull_object(name, pts, mats, bone, section, space='rest', bevel=0.0, bevel_seg=1,
                bevel_angle=25.0, planar=4.0):
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(Vector(p))
    res = bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=False)
    kill = list({g for g in res['geom_interior'] + res['geom_unused'] if isinstance(g, bmesh.types.BMVert)})
    if kill:
        bmesh.ops.delete(bm, geom=kill, context='VERTS')
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if planar:
        # merge near-coplanar hull triangles into broad hewn planes
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(planar), use_dissolve_boundaries=False,
                                 verts=bm.verts, edges=bm.edges)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    COLL.objects.link(ob)
    for k in mats:
        ob.data.materials.append(MATS[k])
    PARTS.append({'obj': ob, 'bone': bone, 'section': section, 'space': space})
    if bevel > 0:
        bevel_object(ob, bevel, None, bevel_angle)
    for p in ob.data.polygons:
        p.use_smooth = False
    return ob


def bevel_object(ob, width, segments=None, angle=25.0):
    """Soft chamfer. Bevel faces go to material slot 1 (the '_edge' variant),
    which is where worn beige chips and bright rims are painted."""
    md = ob.modifiers.new('chamfer', 'BEVEL')
    md.width = width
    # two segments on the chunky shells give the soft, rounded chamfer the
    # style asks for; thin details keep one
    md.segments = segments if segments is not None else (2 if width >= 0.06 else 1)
    md.limit_method = 'ANGLE'
    md.angle_limit = math.radians(angle)
    md.harden_normals = False
    if len(ob.data.materials) > 1:
        md.material = 1
    activate(ob)
    bpy.ops.object.modifier_apply(modifier=md.name)
    for p in ob.data.polygons:
        p.use_smooth = False


def fix_normals(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()


def ring(center, u, v, rx, ry, n, phase=0.0, jitter=0.0, rnd=None, prof=None):
    """Polygon ring in the plane spanned by u, v (Vectors)."""
    rnd = rnd or RNG
    pts = []
    for k in range(n):
        a = phase + 2 * math.pi * k / n
        cx, cy = math.cos(a), math.sin(a)
        if prof:
            cx, cy = prof(a)
        j = 1.0 + rnd.uniform(-jitter, jitter)
        pts.append(Vector(center) + u * (cx * rx * j) + v * (cy * ry * j))
    return pts


def loft_object(name, rings, mats, bone, section, space='rest', cap0=True, cap1=True,
                apex0=None, apex1=None, bevel=0.0, bevel_angle=25.0):
    n = len(rings[0])
    verts, faces = [], []
    for r in rings:
        verts.extend(r)
    for i in range(len(rings) - 1):
        for k in range(n):
            a = i * n + k
            b = i * n + (k + 1) % n
            faces.append((a, b, b + n, a + n))
    if apex0 is not None:
        verts.append(apex0)
        ai = len(verts) - 1
        for k in range(n):
            faces.append((ai, (k + 1) % n, k))
    elif cap0:
        faces.append(tuple(reversed(range(n))))
    if apex1 is not None:
        verts.append(apex1)
        ai = len(verts) - 1
        base = (len(rings) - 1) * n
        for k in range(n):
            faces.append((ai, base + k, base + (k + 1) % n))
    elif cap1:
        base = (len(rings) - 1) * n
        faces.append(tuple(base + k for k in range(n)))
    ob = mesh_object(name, verts, faces, mats, bone, section, space)
    fix_normals(ob)
    if bevel > 0:
        bevel_object(ob, bevel, None, bevel_angle)
    return ob


def frame_from(origin, y_axis, z_hint):
    """4x4 frame: local Y along y_axis, local Z as close to z_hint as possible."""
    y = Vector(y_axis).normalized()
    z = Vector(z_hint)
    z = (z - y * z.dot(y)).normalized()
    x = y.cross(z).normalized()
    m = Matrix.Identity(4)
    for i in range(3):
        m[i][0], m[i][1], m[i][2] = x[i], y[i], z[i]
        m[i][3] = origin[i]
    return m


def transform_obj(ob, M):
    ob.data.transform(M)
    ob.data.update()


# ============================================================ skeleton spec
# name -> dict(parent, head, tail, z) for REST, plus ref (4x4 world matrix of
# the bone in the reference pose, bone-length preserving).
BONES = {}


def add_bone(name, parent, head, tail, z_hint, deform=True):
    BONES[name] = {'parent': parent, 'head': Vector(head), 'tail': Vector(tail),
                   'z': Vector(z_hint), 'deform': deform, 'ref': None}


def rest_matrix(name):
    b = BONES[name]
    return frame_from(b['head'], b['tail'] - b['head'], b['z'])


def mirror_x(v):
    return Vector((-v[0], v[1], v[2]))


# ------------------------------------------------------------------ body core
add_bone('Root', None, (0, 0, 0), (0, 0, 1.2), (0, -1, 0))
add_bone('Body', 'Root', (0, 0, 5.0), (0, 0, 6.8), (0, -1, 0))
BONES['Body']['ref'] = BODY_REF @ rest_matrix('Body')

# =================================================================== CARAPACE
# The carapace is a steep-fronted shield. The reference shows its top as a big
# lit plane even though the camera sits below it (5.8 studs), which is only
# possible if the top slopes down toward the front at ~25 degrees: from the
# spike ridge (9.35) to the front edge between the eyes (6.6, measured where
# the horizontal ledge under the brows sits). The eyes sit on that edge, the
# brows ride the slope above them.
#
# Plan outline (x >= 0 half, mirrored): (x, y, z of the rim top edge, z of the
# rim's lower edge). Across the front the lower edge drops over the tops of
# the flanking mouth plates; along the sides it is a thin band ending in the
# lateral spine.
OUTLINE = [
    (0.00, -4.66, 6.62, 5.98),
    (1.10, -4.60, 6.66, 5.96),
    (2.15, -4.36, 6.84, 5.52),
    (3.25, -3.70, 7.04, 5.62),
    (4.40, -2.66, 7.22, 6.40),
    (5.35, -1.38, 7.32, 6.80),
    (6.05, 0.00, 7.37, 6.95),
    (5.25, 1.55, 7.46, 7.02),
    (4.40, 2.95, 7.60, 7.05),
    (3.05, 4.05, 7.74, 7.08),
    (1.55, 4.62, 7.84, 7.10),
    (0.00, 4.82, 7.88, 7.10),
]
DOME_TOP = 9.35
DOME_RIDGE_Y = 0.90


def dome(x, y):
    front = 0.50 * (DOME_RIDGE_Y - y) if y < DOME_RIDGE_Y else 0.16 * (y - DOME_RIDGE_Y)
    return DOME_TOP - 0.058 * x * x - front


def full_outline():
    return [(x, y, zt, zb) for (x, y, zt, zb) in OUTLINE] + \
           [(-x, y, zt, zb) for (x, y, zt, zb) in reversed(OUTLINE) if x > 0]


def build_carapace():
    rnd = random.Random(11)
    pts = []
    for (x, y, zt, zb) in full_outline():
        pts.append((x, y, zt))
        pts.append((x * 0.99, y + (0.03 if y < 0 else -0.02), zb))
        # underside, tucked in toward the body core
        pts.append((x * 0.80, y * (0.86 if y < 0 else 0.80), min(zb, 6.5) - 0.50))
    # Domed top: an irregular scatter so the hull breaks into broad, slightly
    # uneven planes rather than a regular grid.
    for gx in np.linspace(-4.8, 4.8, 7):
        for gy in np.linspace(-3.9, 4.0, 6):
            x = gx + rnd.uniform(-0.30, 0.30)
            y = gy + rnd.uniform(-0.25, 0.25)
            if abs(x) / 6.0 + abs(y - 0.2) / 4.9 > 1.0:
                continue
            pts.append((x, y, dome(x, y) + rnd.uniform(-0.05, 0.05)))
    pts.append((0.0, DOME_RIDGE_Y, DOME_TOP))
    hull_object('Carapace', pts, ('red', 'red_edge'), 'Body', 'Body', bevel=0.09, bevel_angle=16)

    # Five spikes, counted on the reference: a tall pair, a small outer pair,
    # and one broad low spike on the midline behind them. Apexes are the
    # camera-solve landmarks; bases sink into the dome.
    spikes = [((-2.81, 0.93, 10.0), 2.55, 0.35, 0), ((2.81, 0.93, 10.0), 2.55, -0.35, 0),
              ((-4.37, 0.49, 8.70), 1.35, 0.2, 10), ((4.37, 0.49, 8.70), 1.65, -0.2, -10),
              ((0.0, 1.46, 10.15), 3.30, 0.0, 0)]
    # base-centre offsets: the reference's spikes lean, their bases spreading
    # toward the midline more than outward
    base_off = [(-0.32, 0.0), (-0.22, 0.0), (0.10, 0.0), (0.0, 0.0), (0.25, 0.0)]
    for i, (apex, base, lean, spin) in enumerate(spikes):
        ax, ay, az = apex
        bx, by = ax + base_off[i][0], ay + base_off[i][1]
        zb = dome(bx, by) - 0.45
        corners = []
        for k in range(4):
            a = math.radians(45 + 90 * k + spin + rnd.uniform(-7, 7))
            rr = base * 0.5 * rnd.uniform(0.92, 1.08)
            corners.append((bx + math.cos(a) * rr, by + math.sin(a) * rr * 0.95, zb))
        tip = (ax + lean * 0.10, ay - 0.08, az)
        hull_object(f'Spike{i}', corners + [tip], ('red', 'red_edge'), 'Body', 'Body',
                    bevel=0.05, bevel_angle=30)


# ====================================================================== FACE
def box_between(name, p0, p1, width, height, mats, bone, section, up=(0, 0, 1), bevel=0.06,
                taper=1.0, space='rest'):
    """Chamfered bar from p0 to p1; `width` across (horizontal), `height` along up."""
    p0, p1 = Vector(p0), Vector(p1)
    ax = (p1 - p0)
    F = frame_from(p0, ax, up)
    L = ax.length
    hw, hh = width / 2, height / 2
    verts = []
    for t, s in ((0.0, 1.0), (L, taper)):
        for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            verts.append(F @ Vector((sx * hw * s, t, sz * hh * s)))
    faces = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    ob = mesh_object(name, verts, faces, mats, bone, section, space)
    fix_normals(ob)
    if bevel:
        bevel_object(ob, bevel, None, 30)
    return ob


FACE = {
    # eye centre, radius; the reference draws the viewer-left (crab-right) eye
    # larger (32.5 px vs 28 px at almost equal depth), so the radii differ.
    'eye_R': ((-1.12, -4.54, 6.92), 0.475),
    'eye_L': ((1.12, -4.54, 6.92), 0.435),
    'cup_R': (-1.00, -4.70, 5.80),
    'cup_L': (1.00, -4.70, 5.82),
    # brows: outer end centre, inner end centre, inner drop centre
    # back-projected brow end centres (see REFERENCE_NOTES.md), un-rolled
    # (pulled 0.17 forward and 0.35 up from the plane-projected values so the
    # brow overhangs only the top of each eye, as drawn)
    'brow_R': ((-2.13, -4.22, 8.10), (-0.50, -4.97, 7.14), (-0.46, -5.02, 6.98)),
    'brow_L': ((1.95, -4.22, 8.14), (0.58, -4.95, 7.22), (0.50, -5.02, 7.04)),
}


def build_face():
    # Brows: chunky bars angled into an angry V, each ending in a short drop at
    # the inner end (the reference's brows read as hockey sticks, not planks).
    for side in ('R', 'L'):
        outer, inner, drop = FACE[f'brow_{side}']
        up = (0, -0.55, 1)
        ext = (Vector(outer) - Vector(inner)).normalized() * 0.12
        box_between(f'Brow_{side}', Vector(outer) + ext, inner, 0.86, 0.84, ('red', 'red_edge'),
                    f'Brow_{side}', 'Body', up=up, bevel=0.09)
        box_between(f'BrowDrop_{side}', Vector(inner) + ext * 0.5, drop, 0.78, 0.78, ('red', 'red_edge'),
                    f'Brow_{side}', 'Body', up=up, bevel=0.09)
        o, i = Vector(outer), Vector(inner)
        add_bone(f'Brow_{side}', 'Body', i + (o - i) * 0.5 + Vector((0, 0.25, -0.1)),
                 o + Vector((0, 0.25, -0.1)), (0, -0.55, 1))

    # Front face under the edge: a short, steep epistome down to the mouth.
    hull_object('Epistome', [(x, y, z) for x in (-1.70, 1.70) for (y, z) in
                             ((-4.44, 6.62), (-4.52, 5.86), (-4.0, 5.86), (-3.9, 6.6))],
                ('red', 'red_edge'), 'Body', 'Body', bevel=0.07)
    box_between('LipRidge', (-0.78, -4.62, 5.98), (0.78, -4.62, 5.98), 0.26, 0.20,
                ('red', 'red_edge'), 'Body', 'Body', bevel=0.05)
    for sx in (-1, 1):
        # the dark pit each eye stalk rises out of
        c0 = Vector((sx * 1.04, -4.36, 6.22))
        loft_object(f'StalkPit_{"R" if sx < 0 else "L"}',
                    [ring(c0 + Vector((0, t, 0)), Vector((1, 0, 0)), Vector((0, 0, 1)), 0.40, 0.46, 10, 0.1)
                     for t in (-0.16, 0.25)], ('dark', 'dark'), 'Body', 'Body')

    # Mouth cavity behind the teeth.
    hull_object('MouthCavity', [(x, y, z) for x in (-1.45, 1.45) for y in (-4.45, -3.6)
                                for z in (4.4, 5.92)], ('dark',), 'Body', 'Body')

    for side, sx in (('R', -1), ('L', 1)):
        eye_c, rad = FACE[f'eye_{side}']
        eye_c = Vector(eye_c)
        cup = Vector(FACE[f'cup_{side}'])
        add_bone(f'EyeStalk_{side}', 'Body', cup, eye_c, (0, -1, 0))
        add_bone(f'Eye_{side}', f'EyeStalk_{side}', eye_c, eye_c + Vector((0, -rad * 1.6, 0)), (0, 0, 1))
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=14, radius=rad, location=eye_c)
        eye = bpy.context.object
        eye.name = f'Eye_{side}'
        eye.data.transform(Matrix.Translation(eye_c))
        eye.location = (0, 0, 0)
        EYE_AXES[side] = (tuple(eye_c), (0.0, -1.0, 0.0), rad)
        eye.data.materials.append(eye_material(f'eye_{side}', side))
        for p in eye.data.polygons:
            p.use_smooth = True
        PARTS.append({'obj': eye, 'bone': f'Eye_{side}', 'section': 'Eyes', 'space': 'rest'})
        eye.select_set(False)
        # stalk from the cup to the eye
        axis = (eye_c - cup)
        F = frame_from(cup, axis, (0, -1, 0))
        X = F.to_3x3() @ Vector((1, 0, 0))
        Z = F.to_3x3() @ Vector((0, 0, 1))
        rings = [ring(cup + axis.normalized() * t, X, Z, r, r, 8, 0.2)
                 for t, r in ((0.10, 0.18), (0.50, 0.19), (axis.length * 0.92, 0.19))]
        loft_object(f'Stalk_{side}', rings, ('red', 'red_edge'), f'EyeStalk_{side}', 'Body', bevel=0.02)
        cr = [ring(cup + axis.normalized() * t, X, Z, r, r, 10, 0.1) for t, r in ((0.20, 0.27), (0.33, 0.28))]
        loft_object(f'StalkCollar_{side}', cr, ('red', 'red_edge'), f'EyeStalk_{side}', 'Body', bevel=0.02)
        cu = [ring(cup + axis.normalized() * t, X, Z, r, r, 10, 0.1)
              for t, r in ((-0.18, 0.21), (-0.02, 0.29), (0.16, 0.31))]
        loft_object(f'StalkCup_{side}', cu, ('beige', 'beige_edge'), f'EyeStalk_{side}', 'Body', bevel=0.02)
        # socket: a dark ring sunk into the carapace edge behind the eye
        sock = [ring(eye_c + Vector((0, t, 0)), Vector((1, 0, 0)), Vector((0, 0.35, 1)).normalized(), rr, rr, 12, 0.13)
                for t, rr in ((0.42, rad * 1.24), (0.16, rad * 1.10))]
        loft_object(f'Socket_{side}', sock, ('red_dark', 'red_dark'), 'Body', 'Body', bevel=0.0)

    # Central mouth plates (maxillipeds): heavy shield-shaped teeth hanging
    # from under the front edge. Each has its own bone so the mouth can open.
    for side, sx in (('R', -1), ('L', 1)):
        top = Vector((sx * 0.62, -4.90, 5.84))
        add_bone(f'Maxilliped_{side}', 'Body', top + Vector((0, 0.30, 0.0)), top + Vector((0, 0.30, -1.4)),
                 (0, -1, 0))
        th = 0.62
        outline2d = [(-0.40, 0.00), (-0.12, 0.08), (0.18, 0.08), (0.46, 0.00), (0.64, -0.22),
                     (0.68, -0.55), (0.56, -0.95), (0.30, -1.38), (0.04, -1.66), (-0.16, -1.44),
                     (-0.48, -0.98), (-0.66, -0.55), (-0.62, -0.20)]
        if sx < 0:
            outline2d = [(-x, z) for (x, z) in outline2d]
        pts = []
        for (ox, oz) in outline2d:
            pts.append(top + Vector((ox, -0.02, oz)))
            pts.append(top + Vector((ox * 0.9, th, oz * 0.97)))
        pts.append(top + Vector((0.02 * sx, -0.24, -0.45)))
        pts.append(top + Vector((0.04 * sx, -0.18, -1.00)))
        hull_object(f'Tooth_{side}', pts, ('beige', 'beige_edge'), f'Maxilliped_{side}', 'Body',
                    bevel=0.07, bevel_angle=22)

    # Flanking mouth plates, their tops tucked under the carapace edge, then a
    # second, wider pair further round under the front-lateral rim.
    for side, sx in (('R', -1), ('L', 1)):
        for j, (x0, x1, z0, z1, y0, turn, dep) in enumerate(((1.28, 2.35, 4.45, 5.72, -4.50, 18, 0.62),
                                                              (2.30, 3.30, 4.30, 5.55, -3.70, 48, 0.7))):
            cx = sx * (x0 + x1) / 2
            ang = math.radians(turn) * sx
            u = Vector((math.cos(ang), math.sin(ang), 0))
            f = Vector((-math.sin(ang), math.cos(ang), 0))
            hw = (x1 - x0) / 2
            pts = []
            for zz, sc in ((z1, 1.08), ((z0 + z1) / 2, 1.0), (z0, 0.62)):
                for s in (-1, 1):
                    for depth in (0.0, dep):
                        pts.append(Vector((cx, y0, zz)) + u * (s * hw * sc) + f * depth)
            pts.append(Vector((cx, y0, (z0 + z1) / 2 + 0.1)) + f * -0.16)
            hull_object(f'MouthPlate{j}_{side}', pts, ('beige', 'beige_edge'), 'Body', 'Body',
                        bevel=0.07, bevel_angle=22)


# ===================================================================== BELLY
def build_belly():
    """Sternum: a deep bowl under the mouth tiled with chunky beige plates.

    The reference lays the plates out in arcs concentric with the mouth -- the
    rows smile upward at the sides -- so each plate is an annulus sector in
    the front (x, z) plane around the mouth centre, wrapped onto the bowl.
    Plates are real geometry (pushed out and chamfered) so the grooves read
    from every angle, not just in the texture."""
    C = Vector((0.0, -1.30, 4.70))
    R = Vector((3.15, 3.45, 1.66))
    MC = Vector((0.0, 0.0, 6.02))          # mouth centre in the front plane

    def surf_xz(x, z, off=0.0):
        u = (x / R.x) ** 2 + ((z - C.z) / R.z) ** 2
        u = min(u, 0.985)
        y = C.y - R.y * math.sqrt(1.0 - u)
        p = Vector((x, y, z))
        n = Vector(((p.x - C.x) / R.x ** 2, (p.y - C.y) / R.y ** 2, (p.z - C.z) / R.z ** 2)).normalized()
        return p + n * off

    def surf(az, el, off=0.0):
        x = math.sin(az) * math.cos(el)
        y = -math.cos(az) * math.cos(el)
        z = math.sin(el)
        n = Vector((x / R.x, y / R.y, z / R.z)).normalized()
        return C + Vector((x * R.x, y * R.y, z * R.z)) + n * off

    core = []
    for az in np.linspace(-math.pi, math.pi, 16, endpoint=False):
        for el in (-1.4, -1.0, -0.55, -0.1, 0.35, 0.8):
            core.append(surf(az, el, -0.06))
    hull_object('BellyCore', core, ('beige',), 'Body', 'Body')

    # (inner radius, outer radius, half-angle from straight down, plate count)
    rows = [(1.30, 2.02, 80, 5), (2.08, 2.66, 70, 4), (2.72, 3.12, 58, 3)]
    rnd = random.Random(5)
    for ri, (r0, r1, half, ncol) in enumerate(rows):
        edges = np.linspace(-math.radians(half), math.radians(half), ncol + 1)
        for ci in range(ncol):
            a0, a1 = edges[ci] + 0.03, edges[ci + 1] - 0.03
            q0, q1 = r0 + 0.04, r1 - 0.04
            pts = []
            lift = 0.17 + rnd.uniform(-0.02, 0.03)
            for a in np.linspace(a0, a1, 4):
                for rr in (q0, (q0 + q1) / 2, q1):
                    x = MC.x + math.sin(a) * rr
                    z = MC.z - math.cos(a) * rr
                    pts.append(surf_xz(x, z, lift if rr != (q0 + q1) / 2 else lift + 0.04))
                    pts.append(surf_xz(x, z, -0.18))
            hull_object(f'BellyPlate{ri}{ci}', pts, ('beige', 'beige_edge'), 'Body', 'Body',
                        bevel=0.06, bevel_angle=16)

    # Body core under the carapace: joins carapace, sternum and leg sockets.
    core2 = []
    for (x, y, zt, zb) in full_outline():
        core2.append((x * 0.72, y * 0.80, 6.7))
        core2.append((x * 0.66, y * 0.72, 4.6))
    core2 += [(0, 0, 3.5), (2.2, 1.5, 3.6), (-2.2, 1.5, 3.6), (0, 3.2, 4.2)]
    hull_object('BodyCore', core2, ('red', 'red_edge'), 'Body', 'Body', bevel=0.06)


# ===================================================================== CLAWS
def px_scale(p):
    """Studs per reference pixel at world point p."""
    q = np.asarray(p, float) - CAM_P
    return float(q @ _d) / CAM_F


def arm_segment(name, p0, p1, r0, r1, mats, bone, section, sides=7, bulge=1.12, z_hint=(0, 0, 1),
                squash=0.9, seed=5, bevel=0.05, space='ref'):
    """Chunky faceted prism between two joints, fattest a third of the way
    along, ends pulled in so they tuck into the neighbouring cuffs."""
    rnd = random.Random(seed)
    p0, p1 = Vector(p0), Vector(p1)
    F = frame_from(p0, p1 - p0, z_hint)
    X = F.to_3x3() @ Vector((1, 0, 0))
    Z = F.to_3x3() @ Vector((0, 0, 1))
    rings = []
    stations = ((0.0, 0.80), (0.10, 1.0), (0.38, bulge), (0.78, 1.0), (1.0, 0.82))
    phase = rnd.uniform(0, 0.5)
    for t, k in stations:
        r = (r0 + (r1 - r0) * t) * k
        c = p0 + (p1 - p0) * t
        rings.append(ring(c, X, Z, r, r * squash, sides, phase, jitter=0.035, rnd=rnd))
    return loft_object(name, rings, mats, bone, section, space=space, bevel=bevel, bevel_angle=25)


def band(name, c, axis, r, length, mats, bone, section, sides=10, space='ref', z_hint=(0, 0, 1)):
    axis = Vector(axis).normalized()
    F = frame_from(Vector(c) - axis * length / 2, axis, z_hint)
    X = F.to_3x3() @ Vector((1, 0, 0))
    Z = F.to_3x3() @ Vector((0, 0, 1))
    c0 = Vector(c) - axis * length / 2
    rings = [ring(c0 + axis * (length * t), X, Z, r * k, r * k, sides, 0.1, jitter=0.02)
             for t, k in ((0.0, 0.92), (0.2, 1.0), (0.8, 1.0), (1.0, 0.92))]
    return loft_object(name, rings, mats, bone, section, space=space, bevel=0.02)


CLAW = {}
CHIP_REF = []          # (ref-world point, radius, bone): chips placed in a claw's own frame

# ------------------------------------------------------------------ chelae
# Both claws are authored in a chela-local frame and then oriented in a
# natural guard (user direction, overriding a literal copy of the reference
# pose for the claws): the long axis F points forward, inward and down about
# 45 degrees off vertical, U is the dactyl side, S = F x U is the dactyl's hinge
# axis. Local coordinates are (f, u, s) in studs from the wrist. The shape
# language is the reference's: a rounded, hewn crescent palm with a heavy
# fixed finger sweeping round its lower lip, a beige movable finger curling
# down to meet it, beige jaw edges; the crusher is stout and blunt, the cutter
# long, slim and serrated.
CHELA = {
    'R': {'kind': 'crusher', 'center': (-7.25, -6.05, 5.05), 'F': (0.55, -0.65, -0.52), 'roll_out': 0.0,
          'palm_c': 2.6, 'coxa': (-3.35, -2.55, 5.30), 'relax': 14.0, 'open_ref': 8.0},
    'L': {'kind': 'cutter', 'center': (6.75, -4.35, 4.95), 'F': (-0.55, -0.65, -0.52), 'roll_out': 0.0,
          'palm_c': 1.6, 'coxa': (3.35, -2.55, 5.20), 'relax': 14.0, 'open_ref': 8.0},
}

CHELA_SHAPE = {
    'crusher': {
        # a chunky club: longer than it is deep, thick through, fingers at the end
        'girdle': [(-0.3, 0.1), (0.1, 1.2), (1.1, 1.65), (2.5, 1.8), (3.9, 1.7), (4.9, 1.3), (5.35, 0.55),
                   (5.2, -0.3), (5.5, -1.05), (5.0, -1.65), (3.6, -1.95), (2.0, -1.95), (0.6, -1.6), (-0.2, -0.8)],
        'half_t': 1.8, 'knuckle': [(4.3, 1.5, 0.6), (4.85, 1.0, 0.9), (2.8, 1.75, 0.55), (2.6, 0.1, 1.0)],
        'hinge': (4.75, 0.9), 'hinge_len': 4.75,
        'pollex': ([(4.0, -1.3), (5.6, -1.35), (6.8, -1.05), (7.7, -0.55), (8.05, -0.08)],
                   [2.0, 1.6, 1.15, 0.72], [2.3, 1.8, 1.3, 0.85]),
        'dactyl': ([(4.65, 0.9), (6.0, 1.05), (7.05, 0.8), (7.8, 0.35), (8.1, -0.1)],
                   [1.75, 1.5, 1.15, 0.7], [1.65, 1.45, 1.1, 0.7]),
        'teeth': 0, 'arm': (1.05, 0.95, 0.90), 'band': 1.00,
        # worn cream chips on the palm's edges and faces (applied to both faces)
        'chips': [((2.2, 1.75, 1.0), 0.75), ((1.1, -1.85, 1.2), 0.8), ((4.3, -1.8, 0.8), 0.6),
                  ((0.3, 1.25, 1.4), 0.6), ((3.3, 0.4, 1.8), 0.55), ((4.9, 1.1, 0.5), 0.5),
                  ((5.4, -0.9, 0.9), 0.45)],
    },
    'cutter': {
        'girdle': [(-0.25, 0.1), (0.1, 1.1), (0.8, 1.55), (1.8, 1.7), (2.7, 1.45), (3.2, 0.9), (3.3, 0.2),
                   (3.4, -0.7), (3.0, -1.3), (2.0, -1.5), (1.0, -1.45), (0.2, -1.1)],
        'half_t': 1.0, 'knuckle': [(2.6, 1.35, 0.45)],
        'hinge': (2.9, 0.75), 'hinge_len': 3.0,
        'pollex': ([(2.5, -0.9), (4.1, -1.05), (5.4, -0.85), (6.4, -0.3), (7.0, 0.4)],
                   [1.35, 1.05, 0.8, 0.55], [1.25, 0.95, 0.72, 0.5]),
        'dactyl': ([(2.8, 0.75), (4.3, 1.0), (5.6, 0.95), (6.5, 0.7), (7.05, 0.9)],
                   [1.05, 0.85, 0.65, 0.42], [0.95, 0.8, 0.6, 0.42]),
        'teeth': 6, 'arm': (0.92, 0.85, 0.80), 'band': 0.88,
        'chips': [((1.5, 1.6, 0.8), 0.55), ((5.0, -1.0, 0.4), 0.4), ((2.4, -1.4, 0.7), 0.5),
                  ((3.1, 0.6, 1.0), 0.4)],
    },
}


def chela_frame(side):
    c = CHELA[side]
    F = Vector(c['F']).normalized()
    out = Vector((-1.0 if side == 'R' else 1.0, 0, 0))
    U0 = Vector((0, 0, 1)) + out * c['roll_out']
    U = (U0 - F * U0.dot(F)).normalized()
    S = F.cross(U).normalized()
    W = Vector(c['center']) - F * c['palm_c']
    return W, F, U, S


def to_ref(W, F, U, S, f, u, s=0.0):
    """Chela-local (f, u, s) in the level body frame -> reference-pose world."""
    return BODY_REF @ (W + F * f + U * u + S * s)


def finger(name, cl, widths, thicks, frame, mats, bone, section, s_off=0.0, sides=6, bevel=0.04, seed=3):
    """Tapered faceted finger along a local (f, u) centreline, width in the
    claw plane and thickness along the hinge axis; ends in a point."""
    W, F, U, S = frame
    rnd = random.Random(seed)
    P = [W + F * f + U * u + S * s_off for (f, u) in cl]
    rings = []
    for i, p in enumerate(P[:-1]):
        t = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized()
        m = S.cross(t).normalized()
        ring_pts = []
        for k in range(sides):
            a = 2 * math.pi * k / sides + math.pi / sides
            ring_pts.append(p + m * (math.cos(a) * widths[i] / 2) + S * (math.sin(a) * thicks[i] / 2 * rnd.uniform(0.95, 1.05)))
        rings.append([BODY_REF @ q for q in ring_pts])
    return loft_object(name, rings, mats, bone, section, space='ref', cap0=True, apex1=BODY_REF @ P[-1],
                       bevel=bevel, bevel_angle=28)


def edge_teeth(name, cl, widths, frame, side_sign, count, size, mats, bone, section, t0=0.25, t1=0.85):
    """Small triangular serrations along one edge of a finger (side_sign +1 =
    the +m edge, i.e. toward +U for a finger running along +F)."""
    W, F, U, S = frame
    P = [W + F * f + U * u for (f, u) in cl]
    L = [0.0]
    for a, b in zip(P[:-1], P[1:]):
        L.append(L[-1] + (b - a).length)
    out = []
    for n in range(count):
        tt = (t0 + (t1 - t0) * n / max(count - 1, 1)) * L[-1]
        j = max(k for k in range(len(L) - 1) if L[k] <= tt)
        fr = (tt - L[j]) / max(L[j + 1] - L[j], 1e-6)
        p = P[j].lerp(P[j + 1], fr)
        t = (P[j + 1] - P[j]).normalized()
        m = S.cross(t).normalized() * side_sign
        w = widths[min(j, len(widths) - 1)] / 2 * 0.92
        base = p + m * w
        sz = size * (1.0 - 0.35 * n / max(count - 1, 1))
        pts = [base + t * sz * 0.5 + S * sz * 0.4, base - t * sz * 0.5 + S * sz * 0.4,
               base + t * sz * 0.5 - S * sz * 0.4, base - t * sz * 0.5 - S * sz * 0.4,
               base - m * 0.1, base + m * sz * 0.9 - t * sz * 0.15]
        out.append(hull_object(f'{name}{n}', [BODY_REF @ q for q in pts], mats, bone, section,
                               space='ref', bevel=0.0))
    return out


def chela_bones(side, coxa0, elbow, wrist, frame, hinge, dac_tip, relax_deg, coxa_len=0.9):
    """Five claw bones. Reference frames come from the design (body-frame
    joints rolled with the body); rest frames = the chain relaxed downward
    about the coxa and un-rolled. Hand and finger bones use Z = U, so local X
    is the finger's hinge axis S (mirror-consistent for the L claw)."""
    W, F, U, S = frame
    pre = f'Claw_{side}_'
    coxa1 = coxa0 + (elbow - coxa0).normalized() * coxa_len
    chain = [('Coxa', 'Body', coxa0, coxa1, Vector((0, 0, 1))),
             ('Merus', 'Coxa', coxa1, elbow, Vector((0, 0, 1))),
             ('Carpus', 'Merus', elbow, wrist, Vector((0, 0, 1))),
             ('Propodus', 'Carpus', wrist, wrist + F * CHELA_SHAPE[CHELA[side]['kind']]['hinge_len'], U),
             ('Dactyl', 'Propodus', hinge, dac_tip, U)]
    out_dir = elbow - coxa0
    out_dir.z = 0
    axis = out_dir.cross(Vector((0, 0, 1))).normalized()
    R = (Matrix.Translation(coxa0) @ Matrix.Rotation(math.radians(relax_deg), 4, axis)
         @ Matrix.Translation(-coxa0))
    for nm, par, a, b, zh in chain:
        M_design = frame_from(a, b - a, zh)                   # level body frame
        M_ref = BODY_REF @ M_design
        M_rest = R @ M_design
        head = M_rest.translation.copy()
        tail = head + M_rest.to_3x3() @ Vector((0, (b - a).length, 0))
        add_bone(pre + nm, (pre + par) if par != 'Body' else 'Body', head, tail,
                 M_rest.to_3x3() @ Vector((0, 0, 1)))
        BONES[pre + nm]['ref'] = M_ref
        BONES[pre + nm]['author'] = M_ref.copy()
        if nm == 'Dactyl':
            o = CHELA[side]['open_ref']
            BONES[pre + nm]['ref'] = (M_ref @ Matrix.Rotation(math.radians(o), 4, 'X'))
    CLAW[side] = {'frame': frame, 'relax': R, 'hinge': hinge, 'coxa1': coxa1, 'elbow': elbow}


def build_chela(side):
    c = CHELA[side]
    shp = CHELA_SHAPE[c['kind']]
    sec = 'ClawR' if side == 'R' else 'ClawL'
    frame = chela_frame(side)
    W, F, U, S = frame
    ssign = 1.0 if side == 'R' else -1.0       # S points outward on R, inward on L
    coxa0 = Vector(c['coxa'])
    out = Vector((-1.0 if side == 'R' else 1.0, 0, 0))
    elbow = coxa0 + (W - coxa0) * 0.52 + out * 0.55 + Vector((0, 0, 0.45))
    hinge = W + F * shp['hinge'][0] + U * shp['hinge'][1]
    dcl = shp['dactyl'][0]
    dac_tip = W + F * dcl[-1][0] + U * dcl[-1][1]
    chela_bones(side, coxa0, elbow, W, frame, hinge, dac_tip, c['relax'])
    pre = f'Claw_{side}_'
    rnd = random.Random(40 if side == 'R' else 41)
    # palm: girdle + two shrunken rings per side + knuckle points
    ht = shp['half_t']
    g = shp['girdle']
    cen_f = sum(p[0] for p in g) / len(g)
    cen_u = sum(p[1] for p in g) / len(g)
    pts = []
    for (f, u) in g:
        pts.append((f + rnd.uniform(-0.05, 0.05), u + rnd.uniform(-0.05, 0.05), rnd.uniform(-0.08, 0.08)))
        for sc, tt in ((0.94, 0.55), (0.80, 0.86), (0.52, 1.0)):
            for sg in (1, -1):
                ff = cen_f + (f - cen_f) * sc * rnd.uniform(0.97, 1.03)
                uu = cen_u + (u - cen_u) * sc * rnd.uniform(0.97, 1.03)
                pts.append((ff, uu, sg * ht * tt * rnd.uniform(0.95, 1.04)))
    for (f, u, t) in shp['knuckle']:
        for sg in (1, -1):
            pts.append((f, u, sg * ht * t))
    hull_object(f'Claw{side}_Palm', [to_ref(W, F, U, S, f, u, s) for (f, u, s) in pts],
                ('red', 'red_edge'), pre + 'Propodus', sec, space='ref', bevel=0.10, bevel_angle=14)
    # fixed finger (red) with a beige bite edge along its top
    pcl, pw, pt = shp['pollex']
    finger(f'Claw{side}_Pollex', pcl, pw, pt, frame, ('red', 'red_edge'), pre + 'Propodus', sec, seed=42)
    ridge_cl = [(f, u + w / 2 - 0.10) for (f, u), w in zip(pcl, pw + [0.0])]
    ridge_cl[-1] = (pcl[-1][0] - 0.05, pcl[-1][1])
    finger(f'Claw{side}_PollexEdge', ridge_cl, [0.42, 0.36, 0.30, 0.22], [t * 0.78 for t in pt], frame,
           ('beige', 'beige_edge'), pre + 'Propodus', sec, sides=6, bevel=0.02, seed=43)
    # movable finger (beige)
    dcl, dw, dt = shp['dactyl']
    finger(f'Claw{side}_Dactyl', dcl, dw, dt, frame, ('beige', 'beige_edge'), pre + 'Dactyl', sec, seed=44)
    if shp['teeth']:
        edge_teeth(f'Claw{side}_DactylTooth', dcl, dw, frame, -1, shp['teeth'], 0.26,
                   ('beige', 'beige_edge'), pre + 'Dactyl', sec, 0.25, 0.80)
        edge_teeth(f'Claw{side}_PollexTooth', ridge_cl, [0.42, 0.36, 0.30, 0.22], frame, 1, shp['teeth'], 0.24,
                   ('beige', 'beige_edge'), pre + 'Propodus', sec, 0.22, 0.78)
    # wrist cuff and arm
    a0, a1, a2 = shp['arm']
    coxa1 = CLAW[side]['coxa1']
    arm_segment(f'Claw{side}_Carpus', BODY_REF @ W, BODY_REF @ elbow, a0, a1, ('red', 'red_edge'),
                pre + 'Carpus', sec, sides=6, bulge=1.10, seed=24)
    band(f'Claw{side}_WristBand', BODY_REF @ (W + (elbow - W).normalized() * 0.15), BODY_REF.to_3x3() @ (elbow - W),
         shp['band'] * 0.92, 0.36, ('beige', 'beige_edge'), pre + 'Carpus', sec)
    band(f'Claw{side}_ElbowBand', BODY_REF @ elbow, BODY_REF.to_3x3() @ (elbow - W), shp['band'], 0.42,
         ('beige', 'beige_edge'), pre + 'Carpus', sec)
    arm_segment(f'Claw{side}_Merus', BODY_REF @ coxa1, BODY_REF @ elbow, a2, a1, ('red', 'red_edge'),
                pre + 'Merus', sec, sides=6, bulge=1.06, seed=25)
    band(f'Claw{side}_CoxaRing', BODY_REF @ (coxa0 + (coxa1 - coxa0) * 0.5), BODY_REF.to_3x3() @ (coxa1 - coxa0),
         shp['band'] * 0.86, 0.8, ('beige', 'beige_edge'), pre + 'Coxa', sec)
    for (f, u, s), r in shp['chips']:
        for sg in (1, -1):
            CHIP_REF.append((to_ref(W, F, U, S, f, u, s * sg), r, pre + 'Propodus'))


def build_crusher():
    build_chela('R')


def build_cutter():
    build_chela('L')


# ====================================================================== LEGS
# Leg index -> body-frame coxa head for the LEFT leg (right legs mirror x).
# Coxa heads sit low on the body's underside: the reference's front-left leg
# leaves the belly's flank at pixel (970, 582) and the rear one at (880, 612).
LEG_ATTACH = {1: Vector((2.52, -2.75, 3.90)), 2: Vector((3.25, -0.55, 3.95)),
              3: Vector((3.10, 0.55, 3.85)), 4: Vector((2.10, 1.20, 3.30))}
# Reference-image targets (pixels) for the legs the image shows. Tip = planted
# ground contact; knee = merus/carpus band; ankle = carpus/dactyl joint.
LEG_TARGETS = {
    'R1': {'knee': (584, 600), 'ankle': (608, 726), 'tip': (665, 835)},
    'R2': {'tip': (262, 803)},
    'L1': {'knee': (1088, 590), 'ankle': (1120, 706), 'tip': (1116, 815)},
    'L2': {'knee': (1193, 652), 'ankle': (1208, 730), 'tip': (1219, 780)},
    'L4': {'knee': (912, 672), 'ankle': (897, 722), 'tip': (864, 765)},
}
HIDDEN_TIPS = {
    'R3': (240, 766), 'R4': (352, 764),        # pixels: behind the big claw's palm
    'L3': Vector((7.3, 2.35, 0.0)),
}
# Knees for legs the image hides (or shows only a tip of): (pixel, plane y).
# Chosen so every segment stays behind the big claw's palm from the
# reference camera -- the gape between palm, finger and leg R1 is open sand.
HIDDEN_KNEES = {'R2': ((330, 520), 0.6), 'R3': ((300, 470), 2.0), 'R4': ((350, 430), 3.4)}
LEG_COXA = 0.85
LEG_TAGS = ['L1', 'L2', 'L3', 'L4', 'R1', 'R2', 'R3', 'R4']


def ground_point(uv):
    return px_on_plane(uv, (0, 0, 1), 0.0)


def leg_ref_chain(tag):
    """Reference-pose joints (world): coxa head, coxa end, knee, ankle, tip."""
    side = tag[0]
    i = int(tag[1])
    sx = 1 if side == 'L' else -1
    a = LEG_ATTACH[i]
    A = BODY_REF @ Vector((a.x * sx, a.y, a.z))
    tg = LEG_TARGETS.get(tag)
    if tg and 'knee' in tg:
        T = ground_point(tg['tip'])
        h = Vector((T.x - A.x, T.y - A.y, 0)).normalized()
        pn = h.cross(Vector((0, 0, 1)))
        K = px_on_plane_pt(tg['knee'], pn, A)
        N = px_on_plane_pt(tg['ankle'], pn, A)
    else:
        T = ground_point(tg['tip']) if tg else HIDDEN_TIPS[tag]
        if not isinstance(T, Vector):
            T = ground_point(T)
        h = Vector((T.x - A.x, T.y - A.y, 0)).normalized()
        span = Vector((T.x - A.x, T.y - A.y, 0)).length
        if tag in HIDDEN_KNEES:
            uv, yp = HIDDEN_KNEES[tag]
            K = px_on_plane(uv, (0, 1, 0), yp)
        else:
            K = A + h * (span * 0.45) + Vector((0, 0, 1.15))
        N = T + (K - T) * 0.30
        N.z = 1.35
    C1 = A + (K - A).normalized() * LEG_COXA
    return [A, C1, K, N, T]




def ik_knee(c1, n, lm, lk, hint):
    """Planar two-link solve: knee at lm from c1 and lk from n, on the side of
    `hint` (the traced knee)."""
    d = n - c1
    dist = min(d.length, (lm + lk) * 0.999)
    dn = d.normalized()
    a = (lm * lm - lk * lk + dist * dist) / (2 * dist)
    hgt = math.sqrt(max(lm * lm - a * a, 0.0))
    perp = hint - c1
    perp = (perp - dn * perp.dot(dn))
    if perp.length < 1e-6:
        perp = Vector((0, 0, 1)) - dn * dn.z
    perp.normalize()
    return c1 + dn * a + perp * hgt


def mirror_frame_z(chain_pts, z_fn):
    """Compute bone Z hints for a chain in the LEFT-leg convention; right-side
    chains are mirrored to the left, solved, and the hints mirrored back, which
    is exactly what Blender's armature symmetrize produces."""
    pass


def leg_z_hints(pts, side):
    """Per-segment Z hint so local X is the knee hinge (horizontal, normal to
    the leg plane) for the left convention; mirrored for right legs."""
    P = [mirror_x(p) for p in pts] if side == 'R' else list(pts)
    h = Vector((P[-1].x - P[0].x, P[-1].y - P[0].y, 0)).normalized()
    hinge = Vector((0, 0, 1)).cross(h).normalized()     # left leg: points rearward
    zs = []
    for a, b in zip(P[:-1], P[1:]):
        y = (b - a).normalized()
        zs.append(hinge.cross(y))
    if side == 'R':
        zs = [mirror_x(z) for z in zs]
    return zs


LEG_SCALE = {1: 1.0, 2: 0.96, 3: 0.92, 4: 0.74}
# The reference draws the far-side legs slimmer than perspective alone
# explains (front-left 0.84 of front-right after depth correction); kept.
LEG_SCALE_TAG = {'R1': 1.0, 'L1': 0.86, 'L2': 0.58, 'L4': 0.56, 'R2': 0.90, 'R3': 0.86,
                 'R4': 0.80, 'L3': 0.80}
LEG_REST_AZ = {1: -38.0, 2: -12.0, 3: 14.0, 4: 40.0}
LEG_INFO = {}


def plan_legs():
    """Leg lengths and poses by least squares.

    One set of segment lengths per leg index (shared by the mirrored pair, so
    the rest skeleton is exactly symmetric), and per leg a planar pose
    (azimuth, merus lift, carpus drop, dactyl drop). The reference pose is fit
    to the traced knee / ankle / tip pixels with the tip on the sand; weak
    priors keep lengths near a crab-like nominal and joints in a natural
    range, which also places the legs the image hides. The rest pose is a
    symmetric planted stance built from the same lengths."""
    BR = np.array(BODY_REF)

    def chain(tag, prm, lens):
        side, i = tag[0], int(tag[1])
        sx = 1.0 if side == 'L' else -1.0
        psi, a1, a2, a3 = prm
        lm, lk, ld = lens
        a = LEG_ATTACH[i]
        A = np.array([a.x * sx, a.y, a.z])
        h = np.array([math.cos(psi) * sx, math.sin(psi), 0.0])
        up = np.array([0.0, 0.0, 1.0])
        c0 = math.radians(-10)
        C1 = A + LEG_COXA * (h * math.cos(c0) + up * math.sin(c0))
        K = C1 + lm * (h * math.cos(a1) + up * math.sin(a1))
        N = K + lk * (h * math.cos(a2) - up * math.sin(a2))
        T = N + ld * (h * math.cos(a3) - up * math.sin(a3))
        P = np.array([A, C1, K, N, T])
        return P @ BR[:3, :3].T + BR[:3, 3]

    def proj(P):
        return np.array([project(p) for p in P])

    def body_psi(tag, T_world):
        side, i = tag[0], int(tag[1])
        sx = 1.0 if side == 'L' else -1.0
        tb = BODY_REF_INV @ Vector(T_world)
        a = LEG_ATTACH[i]
        return math.atan2(tb.y - a.y, (tb.x - a.x * sx) * sx)

    fit_tags = [t for t in LEG_TAGS if t in LEG_TARGETS]
    tips = {t: np.array(ground_point(LEG_TARGETS[t]['tip'])) for t in fit_tags}
    idx_fit = sorted({int(t[1]) for t in fit_tags})
    p0 = []
    for i in idx_fit:
        p0 += list(LEG_NOMINAL[i])
    for t in fit_tags:
        p0 += [body_psi(t, tips[t]), math.radians(25), math.radians(65), math.radians(75)]
    p0 = np.array(p0)

    def unpack(p):
        lens = {i: p[3 * k:3 * k + 3] for k, i in enumerate(idx_fit)}
        base = 3 * len(idx_fit)
        poses = {t: p[base + 4 * k: base + 4 * k + 4] for k, t in enumerate(fit_tags)}
        return lens, poses

    def residuals(p):
        lens, poses = unpack(p)
        r = []
        for t in fit_tags:
            P = chain(t, poses[t], lens[int(t[1])])
            uv = proj(P)
            tg = LEG_TARGETS[t]
            for j, key in ((2, 'knee'), (3, 'ankle'), (4, 'tip')):
                if key in tg:
                    r += list((uv[j] - np.array(tg[key])) / 3.0)
            r.append(P[4, 2] / 0.03)
            r.append(max(0.0, 0.9 - P[2, 2]) / 0.05)          # knee well above ground
            psi, a1, a2, a3 = poses[t]
            r += [(a1 - math.radians(25)) / math.radians(30), (a2 - math.radians(65)) / math.radians(35),
                  (a3 - math.radians(75)) / math.radians(30)]
        for i in idx_fit:
            r += list((lens[i] - np.array(LEG_NOMINAL[i])) / LEG_LEN_SIGMA)
        return np.array(r)

    p = p0.copy()
    lam = 1e-2
    r = residuals(p)
    cost = r @ r
    for _ in range(200):
        J = np.empty((len(r), len(p)))
        for j in range(len(p)):
            dp = p.copy()
            dp[j] += 1e-5
            J[:, j] = (residuals(dp) - r) / 1e-5
        A_ = J.T @ J
        g = J.T @ r
        step = np.linalg.solve(A_ + lam * np.diag(np.diag(A_) + 1e-9), -g)
        pn = p + step
        rn = residuals(pn)
        if rn @ rn < cost:
            p, r, cost = pn, rn, rn @ rn
            lam = max(lam / 3, 1e-7)
        else:
            lam *= 5
            if lam > 1e8:
                break
        if np.linalg.norm(step) < 1e-8:
            break
    lens, poses = unpack(p)
    lens = {i: tuple(float(v) for v in lens[i]) for i in lens}
    lens[3] = tuple(v * 0.98 for v in lens[2])
    report = {}
    for t in fit_tags:
        P = chain(t, poses[t], lens[int(t[1])])
        uv = proj(P)
        report[t] = {k: round(float(np.linalg.norm(uv[j] - np.array(LEG_TARGETS[t][k]))), 1)
                     for j, k in ((2, 'knee'), (3, 'ankle'), (4, 'tip')) if k in LEG_TARGETS[t]}
    log('leg fit px error', json.dumps(report), 'lengths', json.dumps({i: [round(v, 2) for v in l] for i, l in lens.items()}))

    # legs the image hides: same machinery, tip target only, priors do the rest
    def fit_hidden(t):
        T = HIDDEN_TIPS[t]
        T = np.array(ground_point(T) if not isinstance(T, Vector) else T)
        q = np.array([body_psi(t, T), math.radians(25), math.radians(65), math.radians(75)])
        lens_i = lens[int(t[1])]

        def res(q):
            P = chain(t, q, lens_i)
            d = P[4] - T
            return np.array([d[0] / 0.05, d[1] / 0.05, d[2] / 0.03,
                             (q[1] - math.radians(25)) / math.radians(30),
                             (q[2] - math.radians(65)) / math.radians(35),
                             (q[3] - math.radians(75)) / math.radians(30)])
        lam = 1e-2
        rr = res(q)
        for _ in range(100):
            J = np.array([(res(q + e) - rr) / 1e-5 for e in np.eye(4) * 1e-5]).T
            A_ = J.T @ J
            st = np.linalg.solve(A_ + lam * np.diag(np.diag(A_) + 1e-9), -(J.T @ rr))
            rn = res(q + st)
            if rn @ rn < rr @ rr:
                q, rr = q + st, rn
                lam = max(lam / 3, 1e-7)
            else:
                lam *= 5
        return q
    for t in LEG_TAGS:
        if t not in poses:
            poses[t] = fit_hidden(t)

    for tag in LEG_TAGS:
        side, i = tag[0], int(tag[1])
        lm, lk, ld = lens[i]
        ref = [Vector(v) for v in chain(tag, poses[tag], lens[i])]
        # Rest stance = the reference stance made symmetric: the pair's fitted
        # pose parameters averaged (they are expressed mirror-wise), then the
        # carpus drop re-solved so the tip sits on the sand with the body level.
        pair = [poses[s_ + str(i)] for s_ in ('L', 'R')]
        az, a1, a2, a3 = [float(v) for v in np.mean(pair, axis=0)]
        c0 = math.radians(-10)
        att = LEG_ATTACH[i]
        c1z = att.z + LEG_COXA * math.sin(c0)
        s2 = (c1z + lm * math.sin(a1) - ld * math.sin(a3)) / lk
        if s2 > 1.0:                      # cannot reach: lower the merus
            a1 = math.asin(max(-1.0, (lk + ld * math.sin(a3) - c1z) / lm))
            s2 = 1.0
        a2 = math.asin(max(-1.0, min(1.0, s2)))
        BRi = np.array(BODY_REF_INV)
        rest_body = chain('L' + str(i), (az, a1, a2, a3), lens[i]) @ BRi[:3, :3].T + BRi[:3, 3]
        rest = [Vector(v) for v in rest_body]
        if side == 'R':
            rest = [mirror_x(v) for v in rest]
        LEG_INFO[tag] = {'ref': ref, 'rest': rest, 'lens': (LEG_COXA, lm, lk, ld)}
    return lens


# Crab-like nominal segment lengths per leg index (merus, carpus, dactyl);
# the fit may move them, weakly.
LEG_NOMINAL = {1: (2.5, 2.2, 1.7), 2: (2.8, 2.3, 1.65), 3: (2.8, 2.2, 1.6), 4: (2.3, 1.9, 1.45)}
LEG_LEN_SIGMA = float(os.environ.get('KC_LEGSIG', '0.15'))


LEG_SEGS = ('Coxa', 'Merus', 'Carpus', 'Dactyl')


def leg_bones():
    for tag in LEG_TAGS:
        info = LEG_INFO[tag]
        side = tag[0]
        rest, ref = info['rest'], info['ref']
        zr = leg_z_hints(rest, side)
        zf = leg_z_hints(ref, side)
        parent = 'Body'
        for j, seg in enumerate(LEG_SEGS):
            name = f'Leg_{tag}_{seg}'
            add_bone(name, parent, rest[j], rest[j + 1], zr[j])
            BONES[name]['ref'] = frame_from(ref[j], ref[j + 1] - ref[j], zf[j])
            parent = name


def seg_rings(kind, L, sc, rnd):
    """Local-space rings (X hinge, Y along the bone, Z in-plane) for one leg
    segment. Returns (rings, apex or None, material pair)."""
    R = []
    if kind == 'Coxa':
        r = 0.66 * sc
        for y, k in ((-0.20, 0.86), (-0.05, 1.0), (L + 0.05, 1.0), (L + 0.22, 0.86)):
            R.append((y, r * k, r * k * 1.02))
        return R, None, ('beige', 'beige_edge'), 10
    if kind == 'Merus':
        for y, k in ((0.02, 0.78), (0.14 * L, 1.0), (0.40 * L, 1.10), (0.80 * L, 1.0), (L + 0.05, 0.80)):
            R.append((y, 0.82 * sc * k, 0.90 * sc * k))
        return R, None, ('red', 'red_edge'), 6
    if kind == 'Band':
        r = 1.00 * sc
        for y, k in ((-0.30, 0.88), (-0.16, 1.0), (0.26, 1.0), (0.40, 0.88)):
            R.append((y, r * k, r * 1.05 * k))
        return R, None, ('beige', 'beige_edge'), 10
    if kind == 'Carpus':
        for y, k in ((0.08, 0.80), (0.20 * L, 1.0), (0.45 * L, 1.13), (0.82 * L, 1.0), (L + 0.02, 0.74)):
            R.append((y, 1.00 * sc * k, 1.05 * sc * k))
        return R, None, ('red', 'red_edge'), 6
    if kind == 'Dactyl':
        for y, k in ((-0.30, 0.88), (-0.05, 1.0), (0.30 * L, 0.90), (0.66 * L, 0.55)):
            R.append((y, 0.60 * sc * k, 0.66 * sc * k))
        return R, (L, -0.06 * sc), ('beige', 'beige_edge'), 6
    raise ValueError(kind)


def build_leg_meshes(rest_mats):
    for tag in LEG_TAGS:
        side, i = tag[0], int(tag[1])
        sc = LEG_SCALE_TAG[tag]
        lens = LEG_INFO[tag]['lens']
        for j, seg in enumerate(LEG_SEGS):
            bone = f'Leg_{tag}_{seg}'
            kinds = [seg] + (['Band'] if seg == 'Carpus' else [])
            for kind in kinds:
                rnd = random.Random(1000 * i + 10 * j + len(kind))   # same for L and R
                rings_spec, apex, mats, sides = seg_rings(kind, lens[j], sc, rnd)
                # a flat face looks out along the hinge axis (the leg's outer side)
                phase = math.pi / sides + rnd.uniform(-0.12, 0.12)
                rings = []
                for (y, rx, rz) in rings_spec:
                    pts = []
                    for k in range(sides):
                        a = phase + 2 * math.pi * k / sides
                        jit = 1.0 + rnd.uniform(-0.025, 0.025)
                        pts.append(Vector((math.cos(a) * rx * jit, y, math.sin(a) * rz * jit)))
                    rings.append(pts)
                ap = Vector((0.0, apex[0], apex[1])) if apex else None
                if side == 'R':
                    rings = [[Vector((-p.x, p.y, p.z)) for p in r] for r in rings]
                    if ap is not None:
                        ap = Vector((-ap.x, ap.y, ap.z))
                M = rest_mats[bone]
                rings = [[M @ p for p in r] for r in rings]
                ap = M @ ap if ap is not None else None
                loft_object(f'Leg{tag}_{kind}', rings, mats, bone, 'Legs', space='rest',
                            apex1=ap, bevel=0.035, bevel_angle=25)


# ======================================================================= RUN
build_carapace()
build_face()
build_belly()
build_crusher()
build_cutter()
plan_legs()
leg_bones()
log('body and claws built', len(PARTS), 'parts')


# ======================================================================= RIG
def build_armature():
    arm = bpy.data.armatures.new('KingCrab_Rig')
    rig = bpy.data.objects.new('KingCrab_Rig', arm)
    COLL.objects.link(rig)
    activate(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    for name, b in BONES.items():
        eb = arm.edit_bones.new(name)
        eb.head = b['head']
        eb.tail = b['tail']
        eb.align_roll(b['z'])
        eb.use_deform = b['deform']
        if b['parent']:
            eb.parent = arm.edit_bones[b['parent']]
            eb.use_connect = False
    bpy.ops.object.mode_set(mode='OBJECT')
    return rig


def ref_matrices(rig):
    """Reference-pose armature-space matrix for every bone. Bones without an
    explicit reference frame ride rigidly on their parent."""
    rest = {b.name: b.matrix_local.copy() for b in rig.data.bones}
    ref = {}
    for name, b in BONES.items():
        if b['ref'] is not None:
            ref[name] = b['ref']
        elif b['parent']:
            p = b['parent']
            ref[name] = ref[p] @ rest[p].inverted() @ rest[name]
        else:
            ref[name] = rest[name]
        if name.startswith('Eye_') and name[-1] in EYE_GAZE:
            # Aim the painted pupil: the reference's viewer-right eye looks
            # straight into the lens, the viewer-left one glances 20 degrees
            # toward the midline (its pupil sits right of centre).
            c = ref[name].translation.copy()
            fwd = (ref[name].to_3x3() @ Vector((0, 1, 0))).normalized()
            want = (Vector(CAM_P) - c).normalized()
            want = Matrix.Rotation(math.radians(EYE_GAZE[name[-1]]), 3, 'Z') @ want
            q = fwd.rotation_difference(want)
            ref[name] = Matrix.Translation(c) @ q.to_matrix().to_4x4() @ Matrix.Translation(-c) @ ref[name]
    return rest, ref


EYE_GAZE = {'R': 20.0, 'L': 0.0}


def bind_parts(rig, rest, ref):
    frnd = random.Random(77)
    for part in PARTS:
        ob, bone = part['obj'], part['bone']
        if part['space'] == 'ref':
            # geometry was authored in the bone's design frame (== its
            # reference frame unless the reference pose also moves the bone)
            author = BONES[bone].get('author')
            author = author if author is not None else ref[bone]
            transform_obj(ob, rest[bone] @ author.inverted())
        me = ob.data
        # rest-space position drives every procedural pattern, so the posed
        # probe render and the rest-pose bake paint identical texture
        at = me.attributes.new('restP', 'FLOAT_VECTOR', 'POINT')
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get('co', co)
        at.data.foreach_set('vector', co)
        nr = me.attributes.new('restN', 'FLOAT_VECTOR', 'FACE')
        nn = np.empty(len(me.polygons) * 3, np.float32)
        me.polygons.foreach_get('normal', nn)
        nr.data.foreach_set('vector', nn)
        fa = me.attributes.new('facet', 'FLOAT', 'FACE')
        fa.data.foreach_set('value', np.array([frnd.random() for _ in me.polygons], np.float32))
        # per-section calibrated copies of the shared recipes
        for i, mat in enumerate(me.materials):
            if mat and mat.name in ('red', 'red_edge', 'beige', 'beige_edge'):
                sec = part['section'] if part['section'] in SECTION_KEYS else 'Body'
                if mat.name.startswith('beige') and ob.name.startswith('Belly'):
                    sec = 'Belly'
                key = f'{mat.name}_{sec}'
                me.materials[i] = MATS.get(key) or section_material(mat.name, sec)
        vg = ob.vertex_groups.new(name=bone)
        vg.add(list(range(len(ob.data.vertices))), 1.0, 'REPLACE')
        md = ob.modifiers.new('Armature', 'ARMATURE')
        md.object = rig
        ob.parent = rig


def pose_to(rig, mats, action_name=None, frame=1):
    bpy.context.view_layer.update()
    for name in BONES:
        pb = rig.pose.bones[name]
        pb.rotation_mode = 'QUATERNION'
        pb.matrix = mats[name]
        bpy.context.view_layer.update()
    if action_name:
        act = bpy.data.actions.new(action_name)
        rig.animation_data_create()
        rig.animation_data.action = act
        # held on two frames: a one-frame range is exported by the FBX baker
        # as the rest pose
        for name in BONES:
            pb = rig.pose.bones[name]
            for f in (frame, frame + 1):
                pb.keyframe_insert('location', frame=f, group=name)
                pb.keyframe_insert('rotation_quaternion', frame=f, group=name)
        return act


# ============================================================== STAGE / VIEW
def look_basis_camera():
    cam_data = bpy.data.cameras.new('RefCam')
    cam = bpy.data.objects.new('RefCam', cam_data)
    COLL.objects.link(cam)
    cam_data.sensor_fit = 'HORIZONTAL'
    cam_data.sensor_width = 36.0
    cam_data.lens = CAM_F * 36.0 / 1536.0
    cam_data.clip_start = 0.1
    cam_data.clip_end = 500
    R = Matrix(((_r[0], _u[0], -_d[0]), (_r[1], _u[1], -_d[1]), (_r[2], _u[2], -_d[2])))
    cam.matrix_world = Matrix.Translation(Vector(CAM_P)) @ R.to_4x4()
    scene.camera = cam
    return cam


def stage():
    ground = bpy.data.materials.new('Sand')
    ground.use_nodes = True
    gb = ground.node_tree.nodes.get('Principled BSDF')
    gb.inputs['Base Color'].default_value = (*srgb(236, 204, 160), 1)
    gb.inputs['Roughness'].default_value = 1.0
    bpy.ops.mesh.primitive_plane_add(size=600, location=(0, 0, 0))
    floor = bpy.context.object
    floor.name = 'ReviewGround'
    floor.data.materials.append(ground)
    world = bpy.data.worlds.new('World')
    scene.world = world
    world.use_nodes = True
    wnt = world.node_tree
    wnt.nodes.clear()
    wout = wnt.nodes.new('ShaderNodeOutputWorld')
    mix = wnt.nodes.new('ShaderNodeMixShader')
    bg = wnt.nodes.new('ShaderNodeBackground')
    amb = wnt.nodes.new('ShaderNodeBackground')
    lp = wnt.nodes.new('ShaderNodeLightPath')
    wnt.links.new(lp.outputs['Is Camera Ray'], mix.inputs[0])
    wnt.links.new(amb.outputs[0], mix.inputs[1])
    wnt.links.new(bg.outputs[0], mix.inputs[2])
    wnt.links.new(mix.outputs[0], wout.inputs['Surface'])
    bg.inputs[0].default_value = (*srgb(110, 180, 236), 1)
    bg.inputs[1].default_value = 1.0
    amb.inputs[0].default_value = (*srgb(170, 200, 235), 1)
    amb.inputs[1].default_value = LIGHT['sky']
    sun_data = bpy.data.lights.new('Sun', 'SUN')
    sun_data.energy = LIGHT['sun']
    sun_data.angle = math.radians(LIGHT['sun_soft'])
    sun_data.color = srgb(255, 244, 228)
    sun = bpy.data.objects.new('Sun', sun_data)
    COLL.objects.link(sun)
    el, az = math.radians(LIGHT['sun_el']), math.radians(LIGHT['sun_az'])
    # az measured around Z from the camera's view heading: 0 = sun straight
    # behind the subject (back light), negative = behind and to the viewer's
    # left, 180 = from behind the camera.
    base = math.atan2(_d[0], _d[1])
    dirv = Vector((-math.sin(base + az) * math.cos(el), -math.cos(base + az) * math.cos(el), -math.sin(el)))
    sun.rotation_euler = dirv.to_track_quat('-Z', 'Y').to_euler()
    lights = [sun]
    if LIGHT.get('fill', 0) > 0:
        # soft warm fill from the camera side: the reference's front faces
        # stay bright and saturated even where the sun cannot reach
        fd = bpy.data.lights.new('Fill', 'SUN')
        fd.energy = LIGHT['fill']
        fd.angle = math.radians(35)
        fd.color = srgb(255, 236, 214)
        fill = bpy.data.objects.new('Fill', fd)
        COLL.objects.link(fill)
        fel, faz = math.radians(LIGHT.get('fill_el', 25)), math.radians(LIGHT.get('fill_az', 180))
        fdir = Vector((-math.sin(base + faz) * math.cos(fel), -math.cos(base + faz) * math.cos(fel), -math.sin(fel)))
        fill.rotation_euler = fdir.to_track_quat('-Z', 'Y').to_euler()
        if hasattr(fd, 'use_shadow'):
            fd.use_shadow = True
        lights.append(fill)
    return floor, lights, (bg, amb)


# Sun high and behind-left (tops lit, cast shadow falls toward the camera),
# sky fill, and a soft warm fill from the camera side: the reference's front
# faces stay bright and saturated where the sun cannot reach.
LIGHT = {'sun': 4.0, 'sun_el': 70.0, 'sun_az': 175.0, 'sun_soft': 6.0, 'sky': 0.35, 'fill': 0.3}
if os.environ.get('KC_LIGHT'):          # tuning hook for the compare loop
    LIGHT.update(json.loads(os.environ['KC_LIGHT']))


def set_gpu(scene_):
    scene_.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for dev in ('OPTIX', 'CUDA'):
        try:
            prefs.compute_device_type = dev
            prefs.get_devices()
            gpus = [d for d in prefs.devices if d.type == dev]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == dev
                scene_.cycles.device = 'GPU'
                log('cycles device', dev)
                return dev
        except Exception as e:
            log('gpu', dev, 'unavailable', e)
    scene_.cycles.device = 'CPU'
    scene_.render.threads_mode = 'FIXED'
    scene_.render.threads = 5
    return 'CPU'


def render_to(path, w=1536, h=1024, samples=24, rgba=False):
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA' if rgba else 'RGB'
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def render_ids(path):
    """Debug: every part in a unique flat colour, legend in ids.json."""
    eng = scene.render.engine
    scene.render.engine = 'BLENDER_WORKBENCH'
    sh = scene.display.shading
    sh.light = 'FLAT'
    sh.color_type = 'OBJECT'
    sh.background_type = 'VIEWPORT'
    sh.background_color = (0, 0, 0)
    scene.display.render_aa = 'OFF'
    legend = {}
    for i, part in enumerate(PARTS):
        c = ((i * 37) % 251 + 4, (i * 91) % 247 + 4, (i * 53) % 239 + 8)
        part['obj'].color = (*[srgb(v, 0, 0)[0] for v in c], 1)
        legend['%d,%d,%d' % c] = part['obj'].name
    hide = [o for o in bpy.data.objects if o.name.startswith('Review')]
    for o in hide:
        o.hide_render = True
    scene.view_settings.view_transform = 'Standard'
    render_to(path)
    for o in hide:
        o.hide_render = False
    (WORK / 'ids.json').write_text(json.dumps(legend))
    scene.render.engine = eng


def render_clay(path):
    """Debug: grey clay (Workbench studio light) to judge the facets alone."""
    eng = scene.render.engine
    scene.render.engine = 'BLENDER_WORKBENCH'
    sh = scene.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'SINGLE'
    sh.single_color = (0.75, 0.72, 0.70)
    sh.background_type = 'VIEWPORT'
    sh.background_color = (0.3, 0.33, 0.38)
    scene.display.render_aa = '8'
    render_to(path)
    scene.render.engine = eng


def render_mask(path):
    """Flat white-on-black silhouette of the crab from the reference camera."""
    eng = scene.render.engine
    scene.render.engine = 'BLENDER_WORKBENCH'
    sh = scene.display.shading
    sh.light = 'FLAT'
    sh.color_type = 'SINGLE'
    sh.single_color = (1, 1, 1)
    sh.background_type = 'VIEWPORT'
    sh.background_color = (0, 0, 0)
    scene.display.render_aa = '8'
    hide = [o for o in bpy.data.objects if o.name.startswith('Review')]
    for o in hide:
        o.hide_render = True
    scene.view_settings.view_transform = 'Standard'
    scene.render.film_transparent = False
    render_to(path)
    for o in hide:
        o.hide_render = False
    scene.render.engine = eng


# ================================================================ PAINT SPOTS
# Worn beige chips on the red shell, measured on the reference as (pixel,
# radius in pixels). Each is ray-cast from the reference camera onto the posed
# model and carried back to rest space through the bone of the part it hits,
# so the chip is painted into the texture where the image shows it -- no
# reference pixels are used, only positions.
CHIP_PX = [((605, 395), 13), ((1030, 345), 18), ((1095, 385), 12)]


def locate_paint(rest, ref):
    dg = bpy.context.evaluated_depsgraph_get()
    by_name = {part['obj'].name: part for part in PARTS}
    CHIP_BLOBS.clear()
    for uv, rpx in CHIP_PX:
        hit, loc, nrm, idx, ob, mw = scene.ray_cast(dg, Vector(CAM_P), Vector(img_ray(uv)))
        part = by_name.get(ob.name) if hit else None
        if part is None:
            log('chip missed', uv)
            continue
        bone = part['bone']
        p_rest = rest[bone] @ ref[bone].inverted() @ loc
        CHIP_BLOBS.append((tuple(p_rest), rpx * px_scale(loc) * 1.25, 1.0))
    for p_ref, r, bone in CHIP_REF:
        author = BONES[bone].get('author')
        author = author if author is not None else ref[bone]
        CHIP_BLOBS.append((tuple(rest[bone] @ author.inverted() @ p_ref), r, 1.0))


# ================================================================== SECTIONS
SECTIONS = ('Body', 'Eyes', 'ClawR', 'ClawL', 'Legs')
MASTER_RES = 2048
DELIVERY_RES = 1024


def join_sections():
    out = {}
    for sec in SECTIONS:
        obs = [p['obj'] for p in PARTS if p['section'] == sec]
        for ob in bpy.context.view_layer.objects:
            ob.select_set(False)
        for ob in obs:
            ob.select_set(True)
        bpy.context.view_layer.objects.active = obs[0]
        if len(obs) > 1:
            bpy.ops.object.join()
        ob = bpy.context.view_layer.objects.active
        ob.name = f'KingCrab_{sec}'
        ob.data.name = f'KingCrab_{sec}'
        # one Armature modifier survives the join; keep it first and only
        arms = [m for m in ob.modifiers if m.type == 'ARMATURE']
        for m in arms[1:]:
            ob.modifiers.remove(m)
        out[sec] = ob
    return out


def unwrap(ob):
    activate(ob)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(42), island_margin=0.012,
                             area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    try:
        bpy.ops.uv.pack_islands(margin=0.012, rotate=True)
    except Exception as e:
        log('pack_islands fallback', e)
    bpy.ops.object.mode_set(mode='OBJECT')
    ob.data.uv_layers.active.name = 'UVMap'


def bake_section(sec, ob):
    img = bpy.data.images.new(f'KingCrab_{sec}_BaseColor', MASTER_RES, MASTER_RES, alpha=False)
    img.colorspace_settings.name = 'sRGB'
    mats = [m for m in ob.data.materials if m]
    for m in mats:
        nt = m.node_tree
        for n in [n for n in nt.nodes if n.name == 'BakeTarget']:
            nt.nodes.remove(n)
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.name = 'BakeTarget'
        tex.image = img
        nt.nodes.active = tex
        out = nt.nodes['Output']
        nt.links.new(nt.nodes['BakeEmit'].outputs[0], out.inputs['Surface'])
    activate(ob)
    scene.render.bake.margin = 16
    scene.render.bake.margin_type = 'EXTEND'
    scene.render.bake.use_clear = True
    scene.render.bake.target = 'IMAGE_TEXTURES'
    bpy.ops.object.bake(type='EMIT')
    for m in mats:
        nt = m.node_tree
        nt.links.new(nt.nodes['BSDF'].outputs[0], nt.nodes['Output'].inputs['Surface'])
    master = OUT / 'textures' / f'KingCrab_{sec}_BaseColor_{MASTER_RES}.png'
    img.filepath_raw = str(master)
    img.file_format = 'PNG'
    img.save()
    small = img.copy()
    small.name = f'KingCrab_{sec}_BaseColor_{DELIVERY_RES}'
    small.scale(DELIVERY_RES, DELIVERY_RES)
    small.filepath_raw = str(OUT / 'textures' / f'KingCrab_{sec}_BaseColor_{DELIVERY_RES}.png')
    small.file_format = 'PNG'
    small.save()
    return img, small


FINAL = {}


def final_material(sec, img):
    m = bpy.data.materials.new(f'KingCrab_{sec}')
    if hasattr(m, 'use_nodes') and not m.node_tree:
        m.use_nodes = True
    nt = m.node_tree
    bs = nt.nodes.get('Principled BSDF')
    bs.inputs['Roughness'].default_value = 0.35 if sec == 'Eyes' else 0.88
    for key in ('Specular IOR Level', 'Specular'):
        if key in bs.inputs:
            bs.inputs[key].default_value = 0.14
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.name = 'BaseColor'
    tex.image = img
    nt.links.new(tex.outputs['Color'], bs.inputs['Base Color'])
    FINAL[sec] = m
    return m


def assign_final(ob, m):
    ob.data.materials.clear()
    ob.data.materials.append(m)
    for p in ob.data.polygons:
        p.material_index = 0


# ======================================================================= ROM
def euler_q(x=0.0, y=0.0, z=0.0):
    return Euler((math.radians(x), math.radians(y), math.radians(z)), 'XYZ').to_quaternion()


ROM_LEN = 144


def build_rom(rig):
    """RigTest_ROM: every deform bone through a realistic range, on top of the
    rest pose. 24 fps, 6 s. Body bob/tilt; tripod stepping (each leg lifts,
    swings and plants); both claws swing, raise, and open/close; eyestalks
    and eyes look around; brows angry/surprised; mouth plates chew."""
    rig.animation_data.action = None
    act = bpy.data.actions.new('RigTest_ROM')
    act.use_fake_user = True
    rig.animation_data.action = act
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    tripod_a = {'L1', 'R2', 'L3', 'R4'}

    def key(pb, f, q=None, loc=None):
        pb.rotation_quaternion = q if q is not None else Quaternion()
        pb.location = loc if loc is not None else Vector()
        pb.keyframe_insert('rotation_quaternion', frame=f, group=pb.name)
        pb.keyframe_insert('location', frame=f, group=pb.name)

    frames = list(range(1, ROM_LEN + 1, 8))
    for pb in rig.pose.bones:
        n = pb.name
        for f in frames:
            ph = 2 * math.pi * (f - 1) / 48.0          # 2 s cycle
            q, loc = Quaternion(), Vector()
            if n == 'Body':
                # bob and tilt (local X = world X pitch; local Z = world -Y roll)
                loc = Vector((0, 0.18 * math.sin(2 * ph), 0))
                q = euler_q(6 * math.sin(ph), 0, 8 * math.sin(ph + 1.2))
            elif n.startswith('Leg_'):
                tag = n.split('_')[1]
                seg = n.split('_')[2]
                lift = max(0.0, math.sin(ph + (0 if tag in tripod_a else math.pi)))
                swing = math.cos(ph + (0 if tag in tripod_a else math.pi))
                if seg == 'Coxa':
                    q = euler_q(0, 0, 14 * swing)
                elif seg == 'Merus':
                    q = euler_q(-26 * lift, 0, 0)
                elif seg == 'Carpus':
                    q = euler_q(18 * lift, 0, 0)
                elif seg == 'Dactyl':
                    q = euler_q(12 * lift, 0, 0)
            elif n.startswith('Claw_'):
                seg = n.split('_')[2]
                s = math.sin(ph * 0.5)
                c = math.sin(ph)
                if seg == 'Coxa':
                    q = euler_q(0, 0, 10 * s)
                elif seg == 'Merus':
                    # raise freely, lower only a little: a lowered claw meets
                    # the front leg as it lifts (caught by rom_clearance)
                    q = euler_q(-12 * c if c < 0 else -4 * c, 0, 0)
                elif seg == 'Carpus':
                    q = euler_q(10 * s, 0, 0)
                elif seg == 'Propodus':
                    # pitch the hand up while the same-side front leg lifts
                    # beneath it (measured: +X raises the fingers ~1 stud / 10 deg)
                    front = 'L1' if n.split('_')[1] == 'L' else 'R1'
                    lift_f = max(0.0, math.sin(ph + (0 if front in tripod_a else math.pi)))
                    q = euler_q(20 * lift_f, 14 * c, 0)
                elif seg == 'Dactyl':
                    q = euler_q(-30 * max(0.0, math.sin(2 * ph)), 0, 0)   # open, then snap shut
            elif n.startswith('EyeStalk_'):
                q = euler_q(15 * math.sin(ph), 0, 12 * math.cos(ph))
            elif n.startswith('Eye_'):
                q = euler_q(18 * math.sin(2 * ph), 0, 25 * math.cos(ph))
            elif n.startswith('Brow_'):
                q = euler_q(14 * math.sin(ph), 0, 0)
            elif n.startswith('Maxilliped_'):
                q = euler_q(-22 * max(0.0, math.sin(2 * ph + 0.8)), 0, 0)
            key(pb, f, q, loc)
    scene.frame_start, scene.frame_end = 1, ROM_LEN
    return act


# ================================================================== PREVIEWS
REVIEW = None


def review_collection():
    global REVIEW
    if REVIEW is None:
        REVIEW = bpy.data.collections.new('REVIEW_ONLY')
        scene.collection.children.link(REVIEW)
    return REVIEW


def to_review(ob):
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    review_collection().objects.link(ob)


def load_px(path):
    img = bpy.data.images.load(str(path))
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(h, w, 4)


def save_px(arr, path):
    h, w = arr.shape[:2]
    img = bpy.data.images.new('tmp_sheet', w, h, alpha=True)
    img.pixels.foreach_set(arr.astype(np.float32).ravel())
    img.filepath_raw = str(path)
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


def tile(paths, cols, out):
    ims = [load_px(p) for p in paths]
    h, w = ims[0].shape[:2]
    rows = (len(ims) + cols - 1) // cols
    sheet = np.ones((rows * h, cols * w, 4), np.float32) * np.array([0.09, 0.10, 0.12, 1.0])
    for i, im in enumerate(ims):
        r, c = i // cols, i % cols
        y0 = (rows - 1 - r) * h                       # Blender pixels are bottom-up
        sheet[y0:y0 + h, c * w:(c + 1) * w] = im
    save_px(sheet, out)
    save_px(sheet, WORK / f'raw_{Path(out).name}')     # label_sheets.py labels from this copy


def aim_cam(cam, loc, target, lens=None, ortho=None):
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    if ortho:
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = ortho
    else:
        cam.data.type = 'PERSP'
        cam.data.sensor_fit = 'HORIZONTAL'
        cam.data.sensor_width = 36
        cam.data.lens = lens or 50
    cam.data.shift_x = cam.data.shift_y = 0


def neutral_stage(floor, bg_nodes, on=True):
    bg, amb = bg_nodes
    if on:
        bg.inputs[0].default_value = (*srgb(58, 64, 74), 1)
        floor.data.materials[0].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*srgb(92, 96, 104), 1)
    else:
        bg.inputs[0].default_value = (*srgb(110, 180, 236), 1)
        floor.data.materials[0].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*srgb(236, 204, 160), 1)


def bone_meshes(rig):
    """Octahedral stand-ins for the deform bones (renders cannot show an
    armature), coloured by chain, for the Rig_Bones overlay."""
    palette = {'Leg_L': (0.2, 0.8, 1.0), 'Leg_R': (1.0, 0.75, 0.2), 'Claw_L': (0.3, 1.0, 0.4),
               'Claw_R': (1.0, 0.35, 0.8), 'Eye': (1.0, 1.0, 1.0), 'Brow': (1.0, 1.0, 0.3),
               'Max': (0.7, 0.5, 1.0), 'Body': (1.0, 0.3, 0.3), 'Root': (0.6, 0.6, 0.6)}
    obs = []
    dg = bpy.context.evaluated_depsgraph_get()
    for pb in rig.pose.bones:
        if not pb.bone.use_deform:
            continue
        M = rig.matrix_world @ pb.matrix
        L = pb.bone.length
        w = max(0.08, min(0.28, L * 0.12))
        v = [Vector((0, 0, 0)), Vector((0, L, 0)), Vector((w, L * 0.2, 0)), Vector((-w, L * 0.2, 0)),
             Vector((0, L * 0.2, w)), Vector((0, L * 0.2, -w))]
        f = [(0, 2, 4), (0, 4, 3), (0, 3, 5), (0, 5, 2), (1, 4, 2), (1, 3, 4), (1, 5, 3), (1, 2, 5)]
        me = bpy.data.meshes.new('bonevis')
        me.from_pydata([M @ p for p in v], [], f)
        ob = bpy.data.objects.new('BoneVis_' + pb.name, me)
        review_collection().objects.link(ob)
        key = next((k for k in palette if pb.name.startswith(k)), 'Body')
        ob.color = (*palette[key], 1)
        obs.append(ob)
    return obs


# ============================================================== MEASUREMENTS
def world_verts(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    ev.to_mesh_clear()
    co = co.reshape(-1, 3)
    M = np.array(ob.matrix_world)
    return co @ M[:3, :3].T + M[:3, 3]


def measure(secs, label):
    allv = np.concatenate([world_verts(o) for o in secs.values()])
    cr = world_verts(secs['ClawR'])
    cl = world_verts(secs['ClawL'])
    body = world_verts(secs['Body'])
    legs = world_verts(secs['Legs'])
    return {
        'pose': label,
        'height_top_of_spikes': round(float(allv[:, 2].max()), 3),
        'lowest_point': round(float(allv[:, 2].min()), 3),
        'overall_x': [round(float(allv[:, 0].min()), 3), round(float(allv[:, 0].max()), 3)],
        'overall_y': [round(float(allv[:, 1].min()), 3), round(float(allv[:, 1].max()), 3)],
        'claw_to_claw_span_x': round(float(cl[:, 0].max() - cr[:, 0].min()), 3),
        'carapace_width_x': round(float(body[:, 0].max() - body[:, 0].min()), 3),
        'body_length_y': round(float(body[:, 1].max() - body[:, 1].min()), 3),
        'leg_span_x': round(float(legs[:, 0].max() - legs[:, 0].min()), 3),
        'crusher_claw_size': [round(float(v), 3) for v in (cr.max(0) - cr.min(0))],
        'cutter_claw_size': [round(float(v), 3) for v in (cl.max(0) - cl.min(0))],
    }


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


# ==================================================================== EXPORT
def select_only(obs):
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    for ob in obs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]


def set_action(rig, act, frame_range):
    rig.animation_data.action = act
    scene.frame_start, scene.frame_end = frame_range
    scene.frame_set(frame_range[0])


def export_all(rig, secs, acts):
    fbx_dir = OUT / 'exports' / 'fbx'
    glb_dir = OUT / 'exports' / 'glb'
    # Roblox caps textures at 1024: exports carry the delivery maps
    for sec, m in FINAL.items():
        m.node_tree.nodes['BaseColor'].image = bpy.data.images[f'KingCrab_{sec}_BaseColor_{DELIVERY_RES}']
    common = dict(axis_forward='-Z', axis_up='Y', add_leaf_bones=False, use_armature_deform_only=True,
                  primary_bone_axis='Y', secondary_bone_axis='X')
    rig.animation_data.action = None
    rig.data.pose_position = 'REST'
    select_only([rig] + list(secs.values()))
    bpy.ops.export_scene.fbx(filepath=str(fbx_dir / 'KingCrab.fbx'), use_selection=True,
                             object_types={'MESH', 'ARMATURE'}, bake_anim=False, path_mode='COPY',
                             embed_textures=True, use_mesh_modifiers=False, mesh_smooth_type='OFF',
                             **common)
    rig.data.pose_position = 'POSE'
    for name, act, rng in acts:
        set_action(rig, act, rng)
        select_only([rig])
        bpy.ops.export_scene.fbx(filepath=str(fbx_dir / f'KingCrab_{name}.fbx'), use_selection=True,
                                 object_types={'ARMATURE'}, bake_anim=True, bake_anim_use_all_actions=False,
                                 bake_anim_use_nla_strips=False, bake_anim_simplify_factor=0.0,
                                 bake_anim_force_startend_keying=True, **common)
    # glTF: meshes, armature and both actions
    rig.animation_data.action = acts[0][1]
    select_only([rig] + list(secs.values()))
    bpy.ops.export_scene.gltf(filepath=str(glb_dir / 'KingCrab.glb'), export_format='GLB',
                              use_selection=True, export_animations=True,
                              export_animation_mode='ACTIONS', export_skins=True,
                              export_all_influences=False, export_yup=True, export_apply=False)
    for sec, m in FINAL.items():
        m.node_tree.nodes['BaseColor'].image = bpy.data.images[f'KingCrab_{sec}_BaseColor']


# ============================================================ ATTACK CHECK
# Local-space rotations (degrees about bone X / Y / Z) for the claw chains,
# written for the crab's right claw; the left claw mirrors them (Y and Z
# negated), exactly what Blender's pose-flip does with these bone rolls.
# +X raises an arm segment, pitches the hand's tips toward U, opens the finger.
ATTACK_POSES = {
    # guard: the rest carry with the pincer slightly open
    'guard': {'Dactyl': (10, 0, 0)},
    # windup: arm raised and swung back, hand cocked up, pincer open
    'windup': {'Coxa': (16, 0, -20), 'Merus': (20, 0, 0), 'Carpus': (-6, 0, 0), 'Propodus': (22, 0, 0),
               'Dactyl': (30, 0, 0)},
    # impact: arm swung forward and inward, elbow opened, hand levelled so the
    # fingers drive at player height in front of the face; pincer snapping
    'impact': {'Coxa': (-2, 0, 24), 'Merus': (-6, 0, 0), 'Carpus': (10, 0, 0), 'Propodus': (14, 0, 0),
               'Dactyl': (6, 0, 0)},
    'open': {'Dactyl': (38, 0, 0)},
    'shut': {'Dactyl': 'SHUT'},
}
# per-claw overrides (the lighter cutter winds up lower so its hook clears the
# carapace rim)
ATTACK_SIDE = {}
# Windup candidates, most dramatic first; attack_check keeps, per claw, the
# first one whose hand clears body, eyes and legs (BVH overlap = 0).
WINDUP_CANDIDATES = [
    {'Coxa': (16, 0, -20), 'Merus': (20, 0, 0), 'Carpus': (-6, 0, 0), 'Propodus': (22, 0, 0), 'Dactyl': (30, 0, 0)},
    {'Coxa': (18, 0, -8), 'Merus': (16, 0, 0), 'Carpus': (-10, 0, 0), 'Propodus': (20, 0, 0), 'Dactyl': (30, 0, 0)},
    {'Coxa': (20, 0, 0), 'Merus': (12, 0, 0), 'Carpus': (-14, 0, 0), 'Propodus': (18, 0, 0), 'Dactyl': (30, 0, 0)},
    {'Coxa': (14, 0, 6), 'Merus': (14, 0, 0), 'Carpus': (-16, 0, 0), 'Propodus': (16, 0, 0), 'Dactyl': (30, 0, 0)},
    {'Coxa': (12, 0, -10), 'Merus': (8, 0, 0), 'Carpus': (-18, 0, 0), 'Propodus': (14, 0, 0), 'Dactyl': (30, 0, 0)},
    {'Coxa': (8, 0, 0), 'Merus': (6, 0, 0), 'Carpus': (-20, 0, 0), 'Propodus': (12, 0, 0), 'Dactyl': (30, 0, 0)},
]
ATTACK_ORDER = ['guard', 'windup', 'impact', 'open', 'shut']


def bvh_for(ob, dg, keep=None, groups=None):
    from mathutils.bvhtree import BVHTree
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    M = ob.matrix_world
    verts = [M @ v.co for v in me.vertices]
    allowed = None
    if groups:
        allowed = set()
        for g in groups:
            allowed |= group_verts(ob, g)
    polys = [tuple(p.vertices) for p in me.polygons
             if (keep is None or keep(p, verts)) and (allowed is None or all(i in allowed for i in p.vertices))]
    ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys), verts


def group_verts(ob, name):
    gi = ob.vertex_groups[name].index
    return {v.index for v in ob.data.vertices if any(g.group == gi and g.weight > 0.5 for g in v.groups)}


def finger_clash(rig, ob, side):
    """Intersecting triangle pairs between the movable finger and the rest of
    its hand, ignoring the hinge (where the finger root sits in the palm)."""
    dg = bpy.context.evaluated_depsgraph_get()
    dv = group_verts(ob, f'Claw_{side}_Dactyl')
    pv = group_verts(ob, f'Claw_{side}_Propodus')
    hinge = (rig.matrix_world @ rig.pose.bones[f'Claw_{side}_Dactyl'].head)

    def is_d(p, verts):
        c = sum((verts[i] for i in p.vertices), Vector()) / len(p.vertices)
        return all(i in dv for i in p.vertices) and (c - hinge).length > 1.3

    def is_p(p, verts):
        return all(i in pv for i in p.vertices)
    bd, _ = bvh_for(ob, dg, is_d)
    bp, _ = bvh_for(ob, dg, is_p)
    return len(bd.overlap(bp))


def shut_angle(rig, ob, side):
    """Largest closing rotation (negative X) before the finger touches the
    fixed finger, found by bisection on the BVH overlap."""
    pb = rig.pose.bones[f'Claw_{side}_Dactyl']
    lo, hi = 0.0, 40.0
    for _ in range(12):
        mid = (lo + hi) / 2
        pb.rotation_quaternion = euler_q(-mid, 0, 0)
        bpy.context.view_layer.update()
        if finger_clash(rig, ob, side):
            hi = mid
        else:
            lo = mid
    pb.rotation_quaternion = Quaternion()
    return lo


def apply_attack_pose(rig, name, shut):
    for pb in rig.pose.bones:
        pb.rotation_quaternion = Quaternion()
        pb.location = Vector()
    for side in ('R', 'L'):
        for seg, rot in ATTACK_SIDE.get((name, side), ATTACK_POSES[name]).items():
            pb = rig.pose.bones[f'Claw_{side}_{seg}']
            if rot == 'SHUT':
                pb.rotation_quaternion = euler_q(-shut[side], 0, 0)
                continue
            x, y, z = rot
            if side == 'L':
                y, z = -y, -z
            pb.rotation_quaternion = euler_q(x, y, z)
    bpy.context.view_layer.update()


def rom_clearance(rig, secs, rom):
    """BVH overlap of the swinging claw parts against body, eyes and legs at
    every 4th ROM frame (the ROM contact sheet shows only 12 frames)."""
    set_action(rig, rom, (1, ROM_LEN))
    worst = {}
    for f in range(1, ROM_LEN + 1, 4):
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        for side in ('R', 'L'):
            bc, _ = bvh_for(secs['Claw' + side], dg,
                            groups=[f'Claw_{side}_{g}' for g in ('Carpus', 'Propodus', 'Dactyl')])
            for other in ('Body', 'Eyes', 'Legs'):
                n = len(bc.overlap(bvh_for(secs[other], dg)[0]))
                k = f'Claw{side}_vs_{other}'
                if n > worst.get(k, (0, 0))[0]:
                    worst[k] = (n, f)
    return {k: {'overlapping_triangle_pairs': v[0], 'frame': v[1]} for k, v in worst.items()}


def attack_check(rig, secs, cam):
    """Pose the claws through guard / windup / impact / open / shut, render
    front and three-quarter views, and measure clearances with BVH overlap."""
    rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    apply_attack_pose(rig, 'guard', {'R': 0, 'L': 0})
    shut = {s: shut_angle(rig, secs['Claw' + s], s) * 0.97 for s in ('R', 'L')}
    chosen = {}
    for side in ('R', 'L'):
        for ci, cand in enumerate(WINDUP_CANDIDATES):
            ATTACK_SIDE[('windup', side)] = cand
            apply_attack_pose(rig, 'windup', shut)
            dg = bpy.context.evaluated_depsgraph_get()
            bc, _ = bvh_for(secs['Claw' + side], dg,
                            groups=[f'Claw_{side}_{g}' for g in ('Carpus', 'Propodus', 'Dactyl')])
            hits = sum(len(bc.overlap(bvh_for(secs[o], dg)[0])) for o in ('Body', 'Eyes', 'Legs'))
            if hits == 0:
                chosen[side] = ci
                break
        else:
            chosen[side] = None
    act = bpy.data.actions.new('ClawAttack_Check')
    act.use_fake_user = True
    rig.animation_data.action = act
    report = {'shut_angle_deg': {k: round(v, 2) for k, v in shut.items()}, 'windup_candidate': chosen,
              'windup_pose': {k: ATTACK_SIDE[('windup', k)] for k in ('R', 'L')}, 'poses': {}}
    views = [('front', Vector((0, -34, 7.0)), Vector((0, -3.5, 4.6)), 42),
             ('threequarter', Vector((-22, -26, 11)), Vector((-1.0, -3.0, 4.4)), 42),
             ('crusher', Vector((-21, -21, 10)), Vector((-5.5, -5.0, 5.2)), 42)]
    paths = {v[0]: [] for v in views}
    for fi, name in enumerate(ATTACK_ORDER):
        apply_attack_pose(rig, name, shut)
        for pb in rig.pose.bones:
            if pb.name.startswith('Claw_'):
                pb.keyframe_insert('rotation_quaternion', frame=1 + fi * 10, group=pb.name)
        scene.frame_set(1 + fi * 10)
        dg = bpy.context.evaluated_depsgraph_get()
        entry = {}
        for side in ('R', 'L'):
            claw = secs['Claw' + side]
            # the coxa and merus root sit in the body's shoulder socket by
            # design; the parts that swing past body and face are checked
            bc, _ = bvh_for(claw, dg, groups=[f'Claw_{side}_{g}' for g in ('Carpus', 'Propodus', 'Dactyl')])
            for other in ('Body', 'Eyes', 'Legs'):
                bo, _ = bvh_for(secs[other], dg)
                entry[f'Claw{side}_vs_{other}'] = len(bc.overlap(bo))
            entry[f'Claw{side}_finger_vs_hand'] = finger_clash(rig, claw, side)
        report['poses'][name] = entry
        for vname, loc, tgt, lens in views:
            aim_cam(cam, loc, tgt, lens=lens)
            pth = WORK / f'attack_{name}_{vname}.png'
            render_to(pth, 700, 520, samples=32)
            paths[vname].append(pth)
    tile(paths['front'] + paths['threequarter'] + paths['crusher'], len(ATTACK_ORDER),
         OUT / 'previews' / 'AttackCheck_Claws.png')
    (OUT / 'attack-check.json').write_text(json.dumps(report, indent=2))
    for pb in rig.pose.bones:
        pb.rotation_quaternion = Quaternion()
    log('attack check', json.dumps(report))
    return act, report


# ====================================================================== MAIN
def main():
    rig = build_armature()
    rest, ref = ref_matrices(rig)
    build_leg_meshes(rest)
    bind_parts(rig, rest, ref)
    ref_act = pose_to(rig, ref, 'ReferencePose')
    ref_act.use_fake_user = True
    locate_paint(rest, ref)
    make_materials(sections=True)
    cam = look_basis_camera()
    floor, lights, bgn = stage()
    set_gpu(scene)
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    if PROBE:
        render_to(WORK / os.environ.get('KC_OUT', 'probe_render.png'), samples=16)
        if os.environ.get('KC_RENDER_ONLY'):
            return
        render_mask(WORK / 'probe_mask.png')
        render_ids(WORK / 'probe_ids.png')
        render_clay(WORK / 'probe_clay.png')
        for nm, loc, tg in (('threequarter', (-27, -33, 13), (-0.5, -2.5, 4.2)),
                            ('front', (0, -44, 7.5), (0, -3.0, 4.2)),
                            ('side', (40, -6, 8), (0, -3.0, 4.2))):
            aim_cam(cam, Vector(loc), Vector(tg), lens=38)
            render_to(WORK / f'probe_{nm}.png', 900, 640, samples=16)
        log('probe renders written')
        return

    # ------------------------------------------------ sections, UVs, bake
    secs = join_sections()
    rig.data.pose_position = 'REST'          # bake in the bind pose
    floor.hide_render = True
    scene.cycles.samples = 96               # smooth Bevel-node / AO masks in the bake
    for sec, ob in secs.items():
        unwrap(ob)
    for sec, ob in secs.items():
        log('baking', sec)
        img, small = bake_section(sec, ob)
        assign_final(ob, final_material(sec, img))
    floor.hide_render = False
    rig.data.pose_position = 'POSE'
    for ob in [cam, floor] + lights:
        to_review(ob)
    log('baked')

    # ------------------------------------------------ reference match
    set_action(rig, ref_act, (1, 2))
    render_to(OUT / 'previews' / 'Reference_Match.png', samples=128)
    render_mask(WORK / 'final_mask.png')
    dims_ref = measure(secs, 'ReferencePose')
    rom = build_rom(rig)
    rig.data.pose_position = 'REST'
    dims_rest = measure(secs, 'rest')
    rig.data.pose_position = 'POSE'
    log('reference match rendered')
    if os.environ.get('KC_STOP_AFTER_MATCH'):
        return
    if os.environ.get('KC_ATTACK_ONLY'):
        neutral_stage(floor, bgn, False)
        attack_check(rig, secs, cam)
        return

    # ------------------------------------------------ face close-up
    set_action(rig, ref_act, (1, 2))
    face_c = BODY_REF @ Vector((0.0, -4.6, 6.6))
    aim_cam(cam, face_c + Vector((-1.2, -11.5, 0.2)), face_c + Vector((0, 0, -0.3)), lens=60)
    render_to(OUT / 'previews' / 'Face_Closeup.png', 1200, 900, samples=96)

    # ------------------------------------------------ turnaround (rest pose)
    rig.data.pose_position = 'REST'
    neutral_stage(floor, bgn, True)
    tgt = Vector((0.0, -1.2, 4.4))
    views = [('Front', (0, -60, 5.0)), ('ThreeQuarter', (-42, -42, 12.0)), ('Side', (60, 0, 5.0)),
             ('Back', (0, 60, 5.0)), ('Top', (0, -0.01, 60))]
    paths = []
    for name, loc in views:
        aim_cam(cam, Vector(loc), tgt, ortho=27.0)
        pth = WORK / f'turn_{name}.png'
        render_to(pth, 900, 700, samples=48)
        paths.append(pth)
    tile(paths, 3, OUT / 'previews' / 'Turnaround.png')

    # ------------------------------------------------ rig bones overlay (rest)
    bones = bone_meshes(rig)
    aim_cam(cam, Vector((-30, -34, 16)), tgt, ortho=27.0)
    eng = scene.render.engine
    scene.render.engine = 'BLENDER_WORKBENCH'
    sh = scene.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'SINGLE'
    sh.single_color = (0.55, 0.52, 0.50)
    sh.background_type = 'VIEWPORT'
    sh.background_color = (0.07, 0.08, 0.10)
    floor.hide_render = True
    for b in bones:
        b.hide_render = True
    render_to(WORK / 'rig_model.png', 1400, 1000)
    for o in secs.values():
        o.hide_render = True
    for b in bones:
        b.hide_render = False
    sh.color_type = 'OBJECT'
    sh.light = 'FLAT'
    scene.render.film_transparent = True
    render_to(WORK / 'rig_bones.png', 1400, 1000, rgba=True)
    scene.render.film_transparent = False
    for o in secs.values():
        o.hide_render = False
    for b in bones:
        bpy.data.objects.remove(b)
    model = load_px(WORK / 'rig_model.png')
    bonesp = load_px(WORK / 'rig_bones.png')
    a = bonesp[..., 3:4]
    comp = model * 0.55 * (1 - a) + bonesp * a
    comp[..., 3] = 1.0
    save_px(comp, OUT / 'previews' / 'Rig_Bones.png')
    scene.render.engine = eng
    floor.hide_render = False
    rig.data.pose_position = 'POSE'

    # ------------------------------------------------ ROM contact sheet
    neutral_stage(floor, bgn, False)
    set_action(rig, rom, (1, ROM_LEN))
    aim_cam(cam, Vector((-20, -26, 9)), Vector((0, -1.8, 4.0)), lens=45)
    paths = []
    for f in range(1, ROM_LEN + 1, 12):
        scene.frame_set(f)
        pth = WORK / f'rom_{f:03d}.png'
        render_to(pth, 800, 560, samples=24)
        paths.append(pth)
    tile(paths, 4, OUT / 'previews' / 'RigTest_ROM.png')
    # joint close-ups at the extremes: legs at full lift (both tripods),
    # claws swung and fingers open, mouth open
    paths = []
    for f, loc, tg in ((13, (-15, -16, 5), (-5, -1.0, 2.5)), (37, (16, -16, 5), (5, -1.0, 2.5)),
                       (25, (-18, -22, 9), (-6.5, -4.5, 4.5)), (19, (14, -21, 8), (5.5, -3.5, 4.5))):
        scene.frame_set(f)
        aim_cam(cam, Vector(loc), Vector(tg), lens=40)
        pth = WORK / f'romdetail_{f:03d}.png'
        render_to(pth, 800, 560, samples=32)
        paths.append(pth)
    tile(paths, 2, OUT / 'previews' / 'RigTest_Joints.png')
    attack_act, attack_rep = attack_check(rig, secs, cam)
    rom_rep = rom_clearance(rig, secs, rom)
    attack_rep['rom_claw_clearance'] = rom_rep or 'no overlaps at any sampled frame'
    (OUT / 'attack-check.json').write_text(json.dumps(attack_rep, indent=2))
    log('rom clearance', json.dumps(rom_rep))
    log('previews rendered')

    # ------------------------------------------------ pose samples for validation
    samples = {}
    for key, act, f in (('ReferencePose@1', ref_act, 1), ('RigTest_ROM@37', rom, 37)):
        set_action(rig, act, (1, 2) if act is ref_act else (1, ROM_LEN))
        scene.frame_set(f)
        samples[key] = {pb.name: [[round(v, 4) for v in rig.matrix_world @ pb.head],
                                  [round(v, 4) for v in rig.matrix_world @ pb.tail]]
                        for pb in rig.pose.bones if pb.bone.use_deform}

    # ------------------------------------------------ exports
    acts = [('ReferencePose', ref_act, (1, 2)), ('RigTest_ROM', rom, (1, ROM_LEN))]
    export_all(rig, secs, acts)
    set_action(rig, ref_act, (1, 2))
    look_basis_camera_restore(cam)
    log('exported')

    # ------------------------------------------------ reports
    tex = {}
    for f in sorted((OUT / 'textures').glob('*.png')):
        im = bpy.data.images.load(str(f), check_existing=True)
        tex[f.name] = {'sha256': sha(f), 'size': list(im.size)}
    poly = {sec: {'triangles': tri_count(ob), 'vertices': len(ob.data.vertices), 'faces': len(ob.data.polygons),
                  'under_roblox_20k': tri_count(ob) < 20000} for sec, ob in secs.items()}
    poly['total_triangles'] = sum(v['triangles'] for v in poly.values() if isinstance(v, dict))
    (OUT / 'polygon-report.json').write_text(json.dumps(poly, indent=2))
    bones_out = [{'name': b.name, 'parent': b.parent.name if b.parent else None, 'deform': b.use_deform,
                  'head': [round(v, 4) for v in b.head_local], 'tail': [round(v, 4) for v in b.tail_local]}
                 for b in rig.data.bones]
    manifest = {
        'asset': 'KingCrab', 'role': 'Beach Cove map boss', 'units': '1 Blender unit = 1 Roblox stud',
        'front': 'Blender -Y (exported -Z forward, Y up)',
        'reference': {'file': 'source/king-crab-reference.webp', 'sha256': sha(REF_IMG)},
        'camera': {k: CAM[k] for k in ('f_px', 'lens_mm', 'camera_location', 'yaw_deg', 'pitch_deg',
                                       'body_roll_deg')},
        'dimensions': {'reference_pose': dims_ref, 'rest_pose': dims_rest},
        'sections': poly,
        'bones': bones_out, 'deform_bone_count': sum(1 for b in rig.data.bones if b.use_deform),
        'actions': {'ReferencePose': [1, 2], 'RigTest_ROM': [1, ROM_LEN], 'ClawAttack_Check': [1, 41],
                    'fps': scene.render.fps},
        'shading': {sec: ('smooth' if sec == 'Eyes' else 'flat') for sec in secs},
        'pose_samples': samples,
        'textures': tex,
        'calibration': {k: list(v) for k, v in CALIBRATION.items()},
        'lighting': LIGHT, 'paint': PAINT,
    }
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    rig.animation_data.action = ref_act
    try:
        bpy.ops.file.pack_all()
    except Exception as e:
        log('pack_all', e)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'KingCrab.blend'))
    log('KINGCRAB_COMPLETE', json.dumps({'dims_ref': dims_ref, 'tris': poly['total_triangles']}))


def look_basis_camera_restore(cam):
    R = Matrix(((_r[0], _u[0], -_d[0]), (_r[1], _u[1], -_d[1]), (_r[2], _u[2], -_d[2])))
    cam.matrix_world = Matrix.Translation(Vector(CAM_P)) @ R.to_4x4()
    cam.data.type = 'PERSP'
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.sensor_width = 36.0
    cam.data.lens = CAM_F * 36.0 / 1536.0


main()
