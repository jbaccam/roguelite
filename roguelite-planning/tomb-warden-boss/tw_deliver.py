"""Tomb Warden delivery (bpy): actions, Blender-evaluated motion checks, game
package JSON (plans/BOSS_GAME_PACKAGE_SPEC.md), the Studio FBX and the small
preview set from the round-10 brief.
"""
import hashlib
import json
import math
import shutil
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

import tw_design as D
import tw_motion as M

HERE = Path(__file__).resolve().parent
NAME = 'TombWarden'
BOSS_ID = 'tomb-warden'
FPS = 24
GAME = HERE / 'exports' / 'game'
PREV = HERE / 'previews'
WORK = HERE / '_work'
CLIP_ORDER = ['Idle', 'Walk', 'Hit', 'Death', 'Emerge', 'FistSlam', 'FistHook', 'Roar']
SMAT = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def cf(m):
    m = SMAT @ m @ SMAT
    return [round(x, 7) for x in [m[0][3], m[1][3], m[2][3], m[0][0], m[0][1], m[0][2], m[1][0], m[1][1], m[1][2],
                                  m[2][0], m[2][1], m[2][2]]]


def studio(v):
    return [round(-float(v[0]), 4), round(float(v[2]), 4), round(float(v[1]), 4)]


def r4(v):
    return [round(float(x), 4) for x in v]


# ================================================================ images
_FONT = {
    'A': '01110100011000111111100011000110001', 'B': '11110100011000111110100011000111110',
    'C': '01110100011000010000100001000101110', 'D': '11110100011000110001100011000111110',
    'E': '11111100001000011110100001000011111', 'F': '11111100001000011110100001000010000',
    'G': '01110100011000010111100011000101111', 'H': '10001100011000111111100011000110001',
    'I': '01110001000010000100001000010001110', 'J': '00111000100001000010000101001001100',
    'K': '10001100101010011000101001001010001', 'L': '10000100001000010000100001000011111',
    'M': '10001110111010110101100011000110001', 'N': '10001100011100110101100111000110001',
    'O': '01110100011000110001100011000101110', 'P': '11110100011000111110100001000010000',
    'Q': '01110100011000110001101011001001101', 'R': '11110100011000111110101001001010001',
    'S': '01111100001000001110000010000111110', 'T': '11111001000010000100001000010000100',
    'U': '10001100011000110001100011000101110', 'V': '10001100011000110001100010101000100',
    'W': '10001100011000110101101011010101010', 'X': '10001100010101000100010101000110001',
    'Y': '10001100010101000100001000010000100', 'Z': '11111000010001000100010001000011111',
    '0': '01110100011001110101110011000101110', '1': '00100011000010000100001000010001110',
    '2': '01110100010000100010001000100011111', '3': '11111000100010000010000011000101110',
    '4': '00010001100101010010111110001000010', '5': '11111100001111000001000011000101110',
    '6': '00110010001000011110100011000101110', '7': '11111000010001000100010000100001000',
    '8': '01110100011000101110100011000101110', '9': '01110100011000101111000010001001100',
    ' ': '0' * 35, '-': '00000000000000011111000000000000000', '.': '00000000000000000000000000110001100',
    '/': '00001000010001000100010001000010000', ':': '00000011000110000000011000110000000',
}


def draw_text(arr, x, y, text, scale=2, color=(0.1, 0.1, 0.12)):
    for ch in text.upper():
        g = _FONT.get(ch, _FONT[' '])
        for r in range(7):
            for c in range(5):
                if g[r * 5 + c] == '1':
                    arr[y + r * scale:y + (r + 1) * scale, x + c * scale:x + (c + 1) * scale] = color
        x += 6 * scale
    return arr


def tile(images, cols, pad=6, bg=(0.08, 0.09, 0.11)):
    h = max(i.shape[0] for i in images)
    w = max(i.shape[1] for i in images)
    rows = math.ceil(len(images) / cols)
    out = np.zeros((rows * (h + pad) + pad, cols * (w + pad) + pad, 3))
    out[:] = bg
    for k, im in enumerate(images):
        r, c = divmod(k, cols)
        out[pad + r * (h + pad):pad + r * (h + pad) + im.shape[0], pad + c * (w + pad):pad + c * (w + pad) + im.shape[1]] = im
    return out


def save_rgb(arr, path):
    h, w = arr.shape[:2]
    img = bpy.data.images.new(Path(path).stem, w, h, alpha=False)
    img.colorspace_settings.name = 'sRGB'
    rgba = np.concatenate([np.clip(arr[::-1], 0, 1), np.ones((h, w, 1))], 2)
    img.pixels.foreach_set(rgba.astype(np.float32).ravel())
    img.filepath_raw = str(path)
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


_RN = [0]


def render_rgb(path, res):
    if Path(path).name == 'wb.png':
        _RN[0] += 1
        path = Path(path).with_name('wb_%04d.png' % _RN[0])
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(str(path), check_existing=False)
    a = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(a)
    a = a.reshape(img.size[1], img.size[0], 4)[::-1, :, :3].copy()
    bpy.data.images.remove(img)
    if Path(path).name.startswith('wb_'):
        try:
            Path(path).unlink()
        except OSError:
            pass
    return a


# ========================================================= review scene
VIEWS = {
    'Front': ((0.0, -27.0, 4.6), (0.0, 0.0, 4.25), 85),
    'Back': ((0.0, 27.0, 4.6), (0.0, 0.0, 4.25), 85),
    'Side': ((-27.0, 0.0, 4.6), (0.0, 0.0, 4.25), 85),
    'ThreeQuarter': ((-15.5, -21.5, 7.0), (0.0, 0.0, 4.1), 85),
    'Hero': ((-11.0, -17.0, 2.6), (1.6, 0.0, 4.4), 42),
    'Clip': ((-19.0, -25.0, 9.0), (0.0, -0.8, 3.8), 70),
    'ClipSide': ((-27.0, -1.0, 5.0), (0.0, -0.8, 3.8), 52),
    'ClipFront': ((-6.0, -28.0, 6.0), (0.0, -0.8, 3.8), 52),
    'Coffin': ((-27.0, -21.0, 13.0), (0.0, 2.4, 5.4), 50),
}


def review_collection():
    c = bpy.data.collections.get('REVIEW_ONLY')
    if c is None:
        c = bpy.data.collections.new('REVIEW_ONLY')
        bpy.context.scene.collection.children.link(c)
    return c


def setup_review_scene():
    sc = bpy.context.scene
    col = review_collection()
    cam = bpy.data.objects.get('ReviewCamera')
    if cam is None:
        cam = bpy.data.objects.new('ReviewCamera', bpy.data.cameras.new('ReviewCamera'))
        col.objects.link(cam)
        cam.data.clip_start, cam.data.clip_end = 0.5, 300
    sc.camera = cam
    if bpy.data.objects.get('Ground') is None:
        me = bpy.data.meshes.new('Ground')
        s = 60.0
        me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
        g = bpy.data.objects.new('Ground', me)
        col.objects.link(g)
        m = bpy.data.materials.new('GroundMat')
        m.diffuse_color = (0.62, 0.56, 0.46, 1)
        m.use_nodes = True
        bs = m.node_tree.nodes.get('Principled BSDF')
        bs.inputs['Base Color'].default_value = (0.52, 0.45, 0.34, 1)
        bs.inputs['Roughness'].default_value = 1.0
        me.materials.append(m)
    if sc.world is None:
        sc.world = bpy.data.worlds.new('World')
    sc.world.color = (0.55, 0.70, 0.95)
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.show_shadows = True
    sc.display.shading.shadow_intensity = 0.35
    sc.view_settings.view_transform = 'Standard'
    return cam


def aim(view):
    cam = bpy.context.scene.camera
    loc, tgt, lens = VIEWS[view]
    k = D.SC if view not in ('Coffin',) else 1.0
    loc, tgt = tuple(np.array(loc) * k), tuple(np.array(tgt) * k)
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.type = 'PERSP'
    cam.data.lens = lens
    cam.data.sensor_fit = 'AUTO'
    cam.data.sensor_width = 36.0


def workbench_view(view, res, color='TEXTURE'):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.color_type = color
    sc.render.film_transparent = False
    aim(view)
    return render_rgb(WORK / 'wb.png', res)


def cycles_setup():
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'OPTIX'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == 'OPTIX'
        sc.cycles.device = 'GPU'
    except Exception:
        sc.cycles.device = 'CPU'
    sc.cycles.samples = 64
    sc.cycles.use_denoising = True
    w = sc.world
    w.use_nodes = True
    bg = w.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value = (0.55, 0.70, 0.95, 1)   # Studio-like blue sky fill
    bg.inputs['Strength'].default_value = 0.85
    col = review_collection()
    if bpy.data.objects.get('Sun') is None:
        sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
        sun.data.energy = 3.4
        sun.data.color = (1.0, 0.90, 0.76)   # warm sun
        sun.data.angle = math.radians(8)
        sun.rotation_euler = (math.radians(48), math.radians(-18), math.radians(-32))
        col.objects.link(sun)
        fill = bpy.data.objects.new('Fill', bpy.data.lights.new('Fill', 'AREA'))
        fill.data.energy = 900
        fill.data.size = 12
        fill.location = (14, -12, 10)
        fill.rotation_euler = (Vector((0, 0, 4)) - Vector(fill.location)).to_track_quat('-Z', 'Y').to_euler()
        col.objects.link(fill)
        rim = bpy.data.objects.new('Rim', bpy.data.lights.new('Rim', 'AREA'))
        rim.data.energy = 700
        rim.data.size = 8
        rim.location = (-6, 16, 12)
        rim.rotation_euler = (Vector((0, 0, 5)) - Vector(rim.location)).to_track_quat('-Z', 'Y').to_euler()
        col.objects.link(rim)


# ================================================================ actions
def key_actions(st):
    rig, sk = st['rig'], st['sk']
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
    rig.animation_data_create()
    for name in CLIP_ORDER:
        clip = st['clips'][name]
        old = bpy.data.actions.get(name)
        if old:
            bpy.data.actions.remove(old)
        act = bpy.data.actions.new(name)
        act.use_fake_user = True
        rig.animation_data.action = act
        prev = {}
        for f, B in enumerate(clip['frames']):
            sk.fk(B)
            for n in sk.order:
                pb = rig.pose.bones[n]
                Bm_ = B[n].copy()
                Bm_[:3, 3] *= D.SC                      # translations to real studs
                loc, q, _ = Matrix(Bm_.tolist()).decompose()
                if n in prev and q.dot(prev[n]) < 0:
                    q.negate()
                prev[n] = q.copy()
                pb.location = loc
                pb.rotation_quaternion = q
                pb.scale = (1, 1, 1)
                pb.keyframe_insert('location', frame=f + 1, group=n)
                pb.keyframe_insert('rotation_quaternion', frame=f + 1, group=n)
        act.use_frame_range = True
        act.frame_start, act.frame_end = 1, len(clip['frames'])
        act['fps'] = FPS
        act['loop'] = bool(clip['loop'])
    rig.animation_data.action = None


def set_frame(rig, clip, f):
    act = bpy.data.actions[clip]
    if rig.animation_data.action != act:
        rig.animation_data.action = act
    bpy.context.scene.frame_set(f + 1)


def rest_pose(rig):
    rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.location, pb.rotation_quaternion, pb.scale = (0, 0, 0), (1, 0, 0, 0), (1, 1, 1)
    bpy.context.view_layer.update()


def eval_verts(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for sec, ob in objs.items():
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        a = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', a)
        ev.to_mesh_clear()
        out[sec] = a.reshape(-1, 3)
    return out


def loop_tris(ob):
    me = ob.data
    me.calc_loop_triangles()
    a = np.empty(len(me.loop_triangles) * 3, np.int64)
    me.loop_triangles.foreach_get('vertices', a)
    return a.reshape(-1, 3)


def bone_mats(rig):
    return {pb.name: np.array(pb.matrix) for pb in rig.pose.bones}


def bone_basis(rig):
    return {pb.name: np.array(pb.matrix_basis) for pb in rig.pose.bones}


# ================================================================= checks
HINGES = {'LeftElbow': ('LeftUpperArm', 'LeftLowerArm'), 'RightElbow': ('RightUpperArm', 'RightLowerArm'),
          'LeftKnee': ('LeftUpperLeg', 'LeftLowerLeg'), 'RightKnee': ('RightUpperLeg', 'RightLowerLeg')}
TWIST_BONES = ['LeftLowerArm', 'RightLowerArm', 'LeftLowerLeg', 'RightLowerLeg', 'LeftHand', 'RightHand']


def hinge_angle(Wm, a, b):
    Ya, Yb, Xa = Wm[a][:3, 1], Wm[b][:3, 1], Wm[a][:3, 0]
    c = np.cross(Ya, Yb)
    return math.degrees(math.atan2(float(c @ Xa), float(Ya @ Yb)))


def joint_regions(st):
    """Body triangles in each joint's blend zone (both bones weighted > 0.10,
    within 1.3 studs of the joint), and the bone whose head is the joint."""
    sk = st['sk']
    idx, w = st['sec_w']['Body']
    V = st['skin'].sec['Body'][0]
    T = loop_tris(st['objs']['Body'])

    def region(a, b, joint, c=None):
        names = [a, b] + ([c] if c else []) + ([joint + 'Half'] if joint + 'Half' in sk.order else [])
        ws = [(w * (idx == sk.order.index(n))).sum(1) for n in names]
        n_on = sum((x > 0.10).astype(int) for x in ws)
        vin = (n_on >= 2) & (np.linalg.norm(V - sk.head[joint], axis=1) < 1.3)
        return T[vin[T].sum(1) >= 2]
    out = {}
    for s_ in D.SIDES:
        out[s_ + 'Shoulder'] = (region('UpperTorso', s_ + 'UpperArm', s_ + 'UpperArm', s_ + 'Shoulder'), s_ + 'UpperArm')
        out[s_ + 'Elbow'] = (region(s_ + 'UpperArm', s_ + 'LowerArm', s_ + 'LowerArm'), s_ + 'LowerArm')
        out[s_ + 'Hip'] = (region('LowerTorso', s_ + 'UpperLeg', s_ + 'UpperLeg'), s_ + 'UpperLeg')
        out[s_ + 'Knee'] = (region(s_ + 'UpperLeg', s_ + 'LowerLeg', s_ + 'LowerLeg'), s_ + 'LowerLeg')
    out['Neck'] = (region('UpperTorso', 'Head', 'Head'), 'Head')
    return out


def hull_area(P2):
    P2 = sorted(set(map(tuple, np.round(P2, 6))))
    if len(P2) < 3:
        return 0.0

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in P2:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(P2):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    h = np.array(lo[:-1] + up[:-1])
    x, y = h[:, 0], h[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


SECTION = {  # joint: (bone at the joint, parent-direction rule, radius)
    'Shoulder': 1.1, 'Elbow': 0.80, 'Hip': 1.1, 'Knee': 0.95, 'Neck': 1.6}


def joint_plane(sk, Wm, key):
    """Joint centre and the bisector plane normal between the limb coming in and going out."""
    if key == 'Neck':
        # the gorilla build has no neck: at the head joint the surface is the trap mass, so the section takes the
        # whole trap ring (radius 1.6) on the bisector of the chest and head axes; a 0.9 radius only caught a
        # front sliver (rest area 0.46) whose size swung with the plane tilt
        J = Wm['Head'][:3, 3] + Wm['Head'][:3, 1] * 0.25 * D.SC
        return J, M.unit(Wm['UpperTorso'][:3, 1] + Wm['Head'][:3, 1]), SECTION['Neck']
    side, kind = ('Left', key[4:]) if key.startswith('Left') else ('Right', key[5:])
    if kind == 'Shoulder':           # upper-arm root section, just below the deltoid
        J = Wm[side + 'UpperArm'][:3, 3] + Wm[side + 'UpperArm'][:3, 1] * 1.0 * D.SC
        return J, M.unit(Wm[side + 'UpperArm'][:3, 1]), SECTION[kind]
    if kind == 'Elbow':
        J = Wm[side + 'LowerArm'][:3, 3]
        return J, M.unit(Wm[side + 'UpperArm'][:3, 1] + Wm[side + 'LowerArm'][:3, 1]), SECTION[kind]
    if kind == 'Hip':                # thigh root section
        J = Wm[side + 'UpperLeg'][:3, 3] + Wm[side + 'UpperLeg'][:3, 1] * 0.55 * D.SC
        return J, M.unit(Wm[side + 'UpperLeg'][:3, 1]), SECTION[kind]
    J = Wm[side + 'LowerLeg'][:3, 3]
    return J, M.unit(Wm[side + 'UpperLeg'][:3, 1] + Wm[side + 'LowerLeg'][:3, 1]), SECTION['Knee']


LIMB = {'Shoulder': ('Shoulder', 'UpperArm'), 'Elbow': ('UpperArm', 'LowerArm'),
        'Hip': ('LowerTorso', 'UpperLeg'), 'Knee': ('UpperLeg', 'LowerLeg', 'Foot'), 'Neck': ('UpperTorso', 'Head')}


def limb_mask(dom, key):
    if key == 'Neck':
        names = LIMB['Neck']
    else:
        side, kind = ('Left', key[4:]) if key.startswith('Left') else ('Right', key[5:])
        names = tuple(n if n in ('UpperTorso', 'LowerTorso') else side + n for n in LIMB[kind])
    return np.isin(dom, names)


def cross_section(V, T, J, n, R, allowed=None):
    R = R * D.SC
    """Convex area of the body mesh sliced by the plane (J, n), limited to the joint's own limb
    triangles within R of J."""
    # every limb triangle the plane cuts, then only the cut points within R of the joint. (Requiring whole
    # triangles inside R made the ring depend on triangle size: long decimated triangles behind the knee
    # dropped out and the slice lost a quarter of its outline.)
    near = np.linalg.norm(V - J, axis=1) < 2.0 * R
    if allowed is not None:
        near &= allowed
    Tn = T[near[T].all(1)]
    d = (V - J) @ n
    pts = []
    for e0, e1 in ((0, 1), (1, 2), (2, 0)):
        a, b = Tn[:, e0], Tn[:, e1]
        da, db = d[a], d[b]
        m = (da > 0) != (db > 0)
        t = da[m] / (da[m] - db[m])
        pts.append(V[a[m]] + (V[b[m]] - V[a[m]]) * t[:, None])
    P = np.concatenate(pts) if pts else np.zeros((0, 3))
    P = P[np.linalg.norm(P - J, axis=1) < R]
    if len(P) < 3:
        return 0.0
    u = M.unit(np.cross(n, (1, 0, 0) if abs(n[0]) < 0.9 else (0, 1, 0)))
    v = np.cross(n, u)
    Q = P - J
    return hull_area(np.stack([Q @ u, Q @ v], 1))


def cone_volume(V, T, J):
    a, b, c = V[T[:, 0]] - J, V[T[:, 1]] - J, V[T[:, 2]] - J
    return float(np.einsum('ij,ij->i', a, np.cross(b, c)).sum() / 6.0)


def mesh_volume(V, T):
    a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    return float(np.einsum('ij,ij->i', a, np.cross(b, c)).sum() / 6.0)


def motion_checks(st, log):
    rig, sk, objs = st['rig'], st['sk'], st['objs']
    dom = st['dominant']
    ctx = st['ctx']
    body_T = loop_tris(objs['Body'])
    tri_lab = {'Body': dom[body_T[:, 0]], 'Mask': np.full(len(loop_tris(objs['Mask'])), 'Head'),
               'Cloth': np.full(len(loop_tris(objs['Cloth'])), 'LowerTorso'),
               'LeftFist': np.full(len(loop_tris(objs['LeftFist'])), 'LeftHand'),
               'RightFist': np.full(len(loop_tris(objs['RightFist'])), 'RightHand')}
    tri_idx = {sec: loop_tris(objs[sec]) for sec in tri_lab}
    forearm_v = {s: np.where(dom == s + 'LowerArm')[0] for s in D.SIDES}
    regions = joint_regions(st)
    rest_pose(rig)
    V0 = eval_verts(objs)
    vol0 = mesh_volume(V0['Body'], body_T)
    Wm0 = bone_mats(rig)
    rad0 = {k: cone_volume(V0['Body'], spec[0], Wm0[spec[1]][:3, 3]) for k, spec in regions.items()}
    lm = {k: limb_mask(dom, k) for k in regions}
    sec0 = {k: cross_section(V0['Body'], body_T, *joint_plane(sk, Wm0, k), allowed=lm[k]) for k in regions}
    for k in regions:
        if sec0[k] < 1e-3:          # the limb-only slice missed (labels): fall back to the unrestricted slice
            lm[k] = None
            sec0[k] = cross_section(V0['Body'], body_T, *joint_plane(sk, Wm0, k))
    log('rest joint sections', {k: round(v, 3) for k, v in sec0.items()})
    out = {}
    for name in CLIP_ORDER:
        clip = st['clips'][name]
        n = len(clip['frames'])
        c = {'frames': n, 'duration': round((n - 1) / FPS, 7), 'loop': clip['loop']}
        ground = []
        pen = {'fist_vs_body': (0.0, None, None), 'fist_vs_other_arm': (0.0, None, None),
               'forearm_vs_body': (0.0, None, None)}
        hinge = {k: [1e9, -1e9] for k in HINGES}
        twist = {k: 0.0 for k in TWIST_BONES}
        dmax = (0.0, None, None)
        vol = [1e9, -1e9]
        radmin = {k: (9.0, None) for k in regions}
        secmin = {k: (9.0, None) for k in regions}
        contact = {s: [] for s in D.SIDES}
        prevB = None
        fistc = {s: [] for s in D.SIDES}
        for f in range(n):
            set_frame(rig, name, f)
            V = eval_verts(objs)
            Wm = bone_mats(rig)
            Bm = bone_basis(rig)
            if name == 'Emerge':
                av = np.concatenate([V['Body'], V['LeftFist'], V['RightFist'], V['Cloth'], V['Mask']])
                cl = D.cavity_clearance_real(av)
                j = int(np.argmin(cl))
                lab = (str(dom[j]) if j < len(dom) else ['LeftFist', 'RightFist', 'Cloth', 'Mask'][int(np.searchsorted(
                    np.cumsum([len(V['LeftFist']), len(V['RightFist']), len(V['Cloth']), len(V['Mask'])]), j - len(dom), side='right'))])
                c.setdefault('wallProfile', []).append((f, round(float(cl[j]), 3), lab, [round(float(q), 2) for q in av[j]]))
            allz = {sec: float(v[:, 2].min()) for sec, v in V.items()}
            low = min(allz, key=allz.get)
            ground.append((allz[low], low))
            for k, (a, b) in HINGES.items():
                ang = hinge_angle(Wm, a, b)
                hinge[k] = [min(hinge[k][0], ang), max(hinge[k][1], ang)]
            for b in TWIST_BONES:
                twist[b] = max(twist[b], abs(M.twist_deg(Bm[b][:3, :3])))
            if prevB is not None:
                for b in sk.order:
                    ang = M.rot_angle(prevB[b][:3, :3].T @ Bm[b][:3, :3])
                    if ang > dmax[0]:
                        dmax = (ang, b, f)
            prevB = Bm
            for s in D.SIDES:
                t_ = sk.head[s + 'Toes']
                piv = np.array([t_[0], t_[1] - 0.30, 0.0]) * D.SC
                rf = sk.rest[s + 'Foot'].copy()
                rf[:3, 3] *= D.SC
                Mf = Wm[s + 'Foot'] @ np.linalg.inv(rf)
                contact[s].append((Wm[s + 'Foot'][:3, 3].copy(), Mf[:3, :3] @ piv + Mf[:3, 3]))
                fistc[s].append(V[s + 'Fist'].mean(0))
            # limbs through the body: signed distance of fist / forearm vertices to every
            # body part except the limb's own arm, each part in its bone's rest space
            Wd = {b: m.copy() for b, m in Wm.items()}
            for m in Wd.values():
                m[:3, 3] /= D.SC
            for s_ in D.SIDES:
                for key, pts in (('fist', V[s_ + 'Fist']), ('forearm', V['Body'][forearm_v[s_]])):
                    d, lab = ctx.body_dist(Wd, pts / D.SC, s_)
                    d = d * D.SC
                    i = int(np.argmin(d))
                    if d[i] < 0:
                        isarm = str(lab[i]).endswith(('Arm', 'Hand'))
                        k2 = ('fist_vs_other_arm' if isarm else 'fist_vs_body') if key == 'fist' else \
                             ('fist_vs_other_arm' if isarm else 'forearm_vs_body')
                        if -d[i] > pen[k2][0]:
                            pen[k2] = (float(-d[i]), f, s_ + ' ' + key + ' vs ' + str(lab[i]))
            if f % 2 == 0 or f == n - 1:
                v = mesh_volume(V['Body'], body_T) / vol0
                vol = [min(vol[0], v), max(vol[1], v)]
                for k, spec in regions.items():
                    r = cone_volume(V['Body'], spec[0], Wm[spec[1]][:3, 3]) / rad0[k] if abs(rad0[k]) > 1e-6 else 1.0
                    if r < radmin[k][0]:
                        radmin[k] = (r, f)
                    r2 = cross_section(V['Body'], body_T, *joint_plane(sk, Wm, k), allowed=lm[k]) / sec0[k]
                    if r2 < secmin[k][0]:
                        secmin[k] = (r2, f)
        gz = [g[0] for g in ground]
        wf = int(np.argmin(gz))
        c['ground'] = {'minZ': round(min(gz), 4), 'frame': wf, 'section': ground[wf][1]}
        c['penetration'] = {k: {'depth': round(v[0], 4), 'frame': v[1], 'against': v[2]} for k, v in pen.items()}
        c['hingeDeg'] = {k: [round(a, 2), round(b, 2)] for k, (a, b) in hinge.items()}
        c['twistDeg'] = {k: round(v, 2) for k, v in twist.items()}
        c['maxBoneStepDeg'] = {'deg': round(dmax[0], 2), 'bone': dmax[1], 'frame': dmax[2]}
        c['jointSectionRetentionNote'] = 'convex area of the joint section (cut points within the joint radius) / rest (gate >= 0.85)'
        c['bodyVolumeRatio'] = [round(vol[0], 4), round(vol[1], 4)]
        c['jointSectionRetention'] = {k: {'ratio': round(v[0], 4), 'frame': v[1]} for k, v in secmin.items()}
        c['jointConeVolumeInfo'] = {k: {'ratio': round(v[0], 4), 'frame': v[1]} for k, v in radmin.items()}
        # planted-foot drift (world): the walk is in place, the world moves under it at nominalSpeed
        speed = clip.get('speed', 0.0)
        drift = {}
        for s in D.SIDES:
            worst, start, prev_kind = 0.0, None, None
            for f in range(n):
                kind = clip['planted'][f][s]
                if kind is None:
                    start, prev_kind = None, None
                    continue
                p = contact[s][f][0 if kind == 'ankle' else 1] + np.array([0, -speed * D.SC * f / FPS, 0])
                if start is None or kind != prev_kind:
                    start = p
                    if prev_kind == 'ankle' and kind == 'ball':
                        start = p
                worst = max(worst, float(np.linalg.norm(p - start)))
                prev_kind = kind
            drift[s] = round(worst, 5)
        c['plantedFootDrift'] = drift
        c['fistSpeed'] = {s: [round(float(np.linalg.norm(fistc[s][f + 1] - fistc[s][f])) * FPS, 3) for f in range(n - 1)]
                          for s in D.SIDES}
        out[name] = c
        log('checks', name, 'ground', c['ground'], 'pen', c['penetration'],
            'drift', drift, 'step', c['maxBoneStepDeg'], 'hinge', c['hingeDeg'])
    rest_pose(rig)
    return out


def summary(ch):
    s = {}
    s['groundMinZ'] = min((c['ground']['minZ'], k) for k, c in ch.items())
    s['fistPenetration'] = max((c['penetration']['fist_vs_body']['depth'], k) for k, c in ch.items())
    s['armArmPenetration'] = max((c['penetration']['fist_vs_other_arm']['depth'], k) for k, c in ch.items())
    s['forearmPenetration'] = max((c['penetration']['forearm_vs_body']['depth'], k) for k, c in ch.items())
    s['hingeMin'] = min((min(v[0] for v in c['hingeDeg'].values()), k) for k, c in ch.items())
    s['hingeMax'] = max((max(v[1] for v in c['hingeDeg'].values()), k) for k, c in ch.items())
    s['twistMax'] = max((max(c['twistDeg'][b] for b in TWIST_BONES[:4]), k) for k, c in ch.items())
    s['boneStepMax'] = max((c['maxBoneStepDeg']['deg'], k, c['maxBoneStepDeg']['bone']) for k, c in ch.items())
    s['footDriftMax'] = max((max(c['plantedFootDrift'].values()), k) for k, c in ch.items())
    s['jointRetentionMin'] = min((min(v['ratio'] for v in c['jointSectionRetention'].values()), k) for k, c in ch.items())
    s['bodyVolumeRatio'] = [min(c['bodyVolumeRatio'][0] for c in ch.values()), max(c['bodyVolumeRatio'][1] for c in ch.values())]
    return s


# ======================================================== game clip sheets
def game_clips_sheet(st, path, color='TEXTURE'):
    rig = st['rig']
    setup_review_scene()
    picks = {'Idle': 5, 'Walk': 5, 'Hit': 5, 'Death': 5, 'Emerge': 6, 'FistSlam': 6, 'FistHook': 6, 'Roar': 6}
    tiles = []
    rows = []
    for name in CLIP_ORDER:
        n = len(st['clips'][name]['frames']) - 1
        k = picks[name]
        fr = sorted(set(int(round(n * i / (k - 1))) for i in range(k)))
        if name == 'FistSlam':
            fr = [0, M.SLAM['warn'], M.SLAM['top'], M.SLAM['impact'], M.SLAM['hold'], n]
        if name == 'FistHook':
            fr = [0, M.HOOK['wind'], M.HOOK['impact'] - 2, M.HOOK['impact'], M.HOOK['follow'], n]
        if name == 'Emerge':
            fr = [0, M.EM['wake'], M.EM['step1e'], M.EM['step2e'], M.EM['impact'], n]
        row = []
        for f in fr:
            set_frame(rig, name, f)
            a = workbench_view('Clip', (240, 250), color=color)
            draw_text(a, 5, 5, '%s %.2fS' % (name, f / FPS), scale=2)
            row.append(a)
        while len(row) < 6:
            row.append(np.full_like(row[0], 0.08))
        tiles += row
    rest_pose(rig)
    save_rgb(tile(tiles, 6, pad=4), path)


def strip(st, clip, frames, labels, views, path, extra=None):
    rig = st['rig']
    tiles = []
    for view in views:
        for f, lab in zip(frames, labels):
            set_frame(rig, clip, f)
            a = workbench_view(view, (330, 330), color='TEXTURE')
            draw_text(a, 6, 6, '%s %s %.2fS' % (lab, view.replace('Clip', ''), f / FPS), scale=2)
            tiles.append(a)
    rest_pose(rig)
    save_rgb(tile(tiles, len(frames)), path)


PROPS_BLEND = HERE.parent / 'round10-props' / 'round10-props.blend'
PROPS_FBX = HERE.parent / 'round10-props' / 'exports' / 'Sarcophagus.fbx'


def coffin_mesh(part='Body'):
    """The round10-props Sarcophagus (exports/Sarcophagus.fbx, read-only import): the body at the coffin origin
    (EMERGE_OUT behind the final spot) and the lid fallen open, flat on the ground in front of it."""
    if bpy.data.objects.get('Sarcophagus_Body') is None and PROPS_FBX.exists():
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=str(PROPS_FBX))
        col = review_collection()
        for o in set(bpy.data.objects) - before:
            for c in list(o.users_collection):
                c.objects.unlink(o)
            col.objects.link(o)
            o.hide_render = True
        bpy.context.view_layer.update()
        body, lid = bpy.data.objects.get('Sarcophagus_Body'), bpy.data.objects.get('Sarcophagus_Lid')
        T = Matrix.Translation(Vector(tuple(D.COFFIN_START_REAL)))
        if lid is not None:
            h = Vector((0.0, D.LID_HINGE_Y, 0.0))
            opn = Matrix.Translation(h) @ Matrix.Rotation(math.radians(90.0), 4, 'X') @ Matrix.Translation(-h)
            lid.matrix_world = T @ opn @ lid.matrix_world
        body.matrix_world = T @ body.matrix_world
        bpy.context.view_layer.update()
    return bpy.data.objects.get('Sarcophagus_' + part)


def coffin_bvh(part='Body'):
    ob = coffin_mesh(part)
    if ob is None:
        return None
    dg = bpy.context.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).to_mesh()
    V = [ob.matrix_world @ v.co for v in me.vertices]
    P = [list(f.vertices) for f in me.polygons]
    return BVHTree.FromPolygons(V, P)


def _inside(bvh, p):
    """Ray-parity inside test (majority of three directions) on the closed coffin shell."""
    votes = 0
    for d in (Vector((1, 0.013, 0.007)).normalized(), Vector((-0.011, 1, 0.017)).normalized(),
              Vector((0.009, -0.012, 1)).normalized()):
        o, n = Vector(p), 0
        for _ in range(64):
            hit = bvh.ray_cast(o, d, 100.0)
            if hit[0] is None:
                break
            n += 1
            o = hit[0] + d * 1e-4
        votes += n % 2
    return votes >= 2


def coffin_signed(bvh, pts, deep=0.5):
    """Signed distance of points to the coffin stone (negative = inside the stone). The sign comes from a
    ray-parity test, only needed within `deep` of the surface (walls 0.55-0.8 thick, the lid slab 1.257)."""
    out = np.empty(len(pts))
    for i, p in enumerate(pts):
        loc, nrm, fi, dist = bvh.find_nearest(Vector(p))
        out[i] = -dist if (dist < deep and _inside(bvh, p)) else dist
    return out


def cavity_wire():
    col = review_collection()
    ob = bpy.data.objects.get('CoffinCavityBox')
    if ob:
        return ob
    cm = coffin_mesh()
    if cm is not None:
        m = bpy.data.materials.new('CavityWire')
        m.diffuse_color = (1.0, 0.25, 0.05, 1)
        out = None
        for part, name in (('Body', 'CoffinCavityBox'), ('Lid', 'CoffinLidWire')):
            src = coffin_mesh(part)
            if src is None:
                continue
            ob = src.copy()
            ob.name = name
            col.objects.link(ob)
            md = ob.modifiers.new('wire', 'WIREFRAME')
            md.thickness = 0.05
            ob.data = ob.data.copy()
            ob.data.materials.clear()
            ob.data.materials.append(m)
            ob.hide_render = False
            out = out or ob
        return out
    lo, hi = D.cavity_box()
    vs = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me = bpy.data.meshes.new('CoffinCavityBox')
    me.from_pydata(vs, [], fs)
    ob = bpy.data.objects.new('CoffinCavityBox', me)
    col.objects.link(ob)
    md = ob.modifiers.new('wire', 'WIREFRAME')
    md.thickness = 0.06
    m = bpy.data.materials.new('CavityWire')
    m.diffuse_color = (1.0, 0.25, 0.05, 1)
    me.materials.append(m)
    return ob


# ================================================================ deliver
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()


def anim_data(st):
    rig, sk = st['rig'], st['sk']
    bones = {b.name: {'parent': b.parent.name if b.parent else None,
                      'rest': cf(b.parent.matrix_local.inverted() @ b.matrix_local if b.parent else b.matrix_local)}
             for b in rig.data.bones if b.use_deform}
    clips = {}
    err = 0.0
    for name in CLIP_ORDER:
        clip = st['clips'][name]
        frames = []
        for f in range(len(clip['frames'])):
            set_frame(rig, name, f)
            tr = {}
            for pb in rig.pose.bones:
                mb = pb.matrix_basis
                tr[pb.name] = cf(mb)
                ref = clip['frames'][f][pb.name].copy()
                ref[:3, 3] *= D.SC
                err = max(err, float(np.abs(np.array(mb) - ref).max()))
            frames.append({'time': round(f / FPS, 7), 'transforms': tr})
        clips[name] = {'duration': round((len(frames) - 1) / FPS, 7), 'loop': bool(clip['loop']), 'frames': frames}
    rest_pose(rig)
    w = st['clips']['Walk']
    anim = {'id': BOSS_ID, 'fps': FPS, 'bones': bones, 'clips': clips,
            'motion': {'strideLength': round(M.WALK_STRIDE * D.SC, 4), 'nominalSpeed': round(M.WALK_STRIDE * D.SC / M.WALK_T, 4)}}
    return anim, err


def clip_closure(anim):
    out = {}
    I12 = [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]
    for name, c in anim['clips'].items():
        f0, fN = c['frames'][0]['transforms'], c['frames'][-1]['transforms']
        e = {}
        if c['loop']:
            e['loopError'] = max(abs(a - b) for k in f0 for a, b in zip(f0[k], fN[k]))
        else:
            if name != 'Emerge':      # the intro starts in the coffin pose by design; it ends on the Idle start pose
                e['startVsIdleStart'] = max(abs(a - b) for k in f0 for a, b in zip(f0[k], anim['clips']['Idle']['frames'][0]['transforms'][k]))
            if name != 'Death':
                e['endVsIdleStart'] = max(abs(a - b) for k in fN for a, b in zip(fN[k], anim['clips']['Idle']['frames'][0]['transforms'][k]))
        e['idleStartIsRest'] = max(abs(a - b) for k in anim['clips']['Idle']['frames'][0]['transforms']
                                   for a, b in zip(anim['clips']['Idle']['frames'][0]['transforms'][k], I12))
        out[name] = {k: round(v, 8) for k, v in e.items()}
    return out


def point_rec(rig, bone, world):
    Mx = rig.pose.bones[bone].matrix
    off = Mx.inverted() @ Vector(world)
    return {'bone': bone, 'offset': r4(off), 'rootAtImpact': r4(world), 'rootAtImpactStudio': studio(world)}


def contact_point(V):
    z = V[:, 2]
    sel = V[z < z.min() + 0.06]
    p = sel.mean(0)
    p[2] = float(z.min())
    return p


def boss_data(st, anim):
    rig, sk, objs = st['rig'], st['sk'], st['objs']
    attacks = {}
    # FistSlam
    f = M.SLAM['impact']
    set_frame(rig, 'FistSlam', f)
    V = eval_verts(objs)
    cl, cr = contact_point(V['LeftFist']), contact_point(V['RightFist'])
    mid = 0.5 * (cl + cr)
    mid[2] = 0.0
    attacks['FistSlam'] = {
        'duration': anim['clips']['FistSlam']['duration'], 'warnStart': round(M.SLAM['warn'] / FPS, 4),
        'impact': round(f / FPS, 4), 'activeEnd': round(f / FPS, 4), 'recoveryEnd': round(45 / FPS, 4),
        'points': {'SlamCenter': point_rec(rig, 'Root', mid), 'LeftFist': point_rec(rig, 'LeftHand', cl),
                   'RightFist': point_rec(rig, 'RightHand', cr)},
        'directionAtImpact': [0.0, 0.0, -1.0], 'directionAtImpactStudio': studio((0, 0, -1)),
        'impactRadiusHint': round(float(np.linalg.norm(cl[:2] - cr[:2]) / 2 + 1.6), 3)}
    # FistHook
    fi = M.HOOK['impact']
    samples = []
    for ff in range(fi - 2, 18):
        set_frame(rig, 'FistHook', ff)
        V = eval_verts(objs)
        fc = V['RightFist'].mean(0)
        la = rig.pose.bones['RightLowerArm']
        hm = la.head + (la.tail - la.head) * 0.5
        samples.append({'time': round(ff / FPS, 4), 'HookFist': r4(fc), 'HookMid': r4(hm),
                        'HookFistStudio': studio(fc), 'HookMidStudio': studio(hm)})
    set_frame(rig, 'FistHook', fi - 1)
    p0 = eval_verts({'R': objs['RightFist']})['R'].mean(0)
    set_frame(rig, 'FistHook', fi + 1)
    p1 = eval_verts({'R': objs['RightFist']})['R'].mean(0)
    dirv = (p1 - p0) / max(np.linalg.norm(p1 - p0), 1e-9)
    set_frame(rig, 'FistHook', fi)
    V = eval_verts(objs)
    fc = V['RightFist'].mean(0)
    la = rig.pose.bones['RightLowerArm']
    hm = np.array(la.head + (la.tail - la.head) * 0.5)
    attacks['FistHook'] = {
        'duration': anim['clips']['FistHook']['duration'], 'warnStart': round(M.HOOK['warn'] / FPS, 4),
        'impact': round(fi / FPS, 4), 'activeEnd': round(17 / FPS, 4), 'recoveryEnd': round(29 / FPS, 4),
        'points': {'HookFist': point_rec(rig, 'RightHand', fc), 'HookMid': point_rec(rig, 'RightLowerArm', hm)},
        'capsuleRadius': round(0.85 * D.SC, 3),
        'directionAtImpact': r4(dirv), 'directionAtImpactStudio': studio(dirv),
        'sweep': samples}
    # Emerge
    fe = M.EM['impact']
    set_frame(rig, 'Emerge', fe)
    V = eval_verts(objs)
    cl, cr = contact_point(V['LeftFist']), contact_point(V['RightFist'])
    mid = 0.5 * (cl + cr)
    mid[2] = 0.0
    lo, hi = D.cavity_box()
    attacks['Emerge'] = {
        'duration': anim['clips']['Emerge']['duration'], 'warnStart': round(38 / FPS, 4), 'impact': round(fe / FPS, 4),
        'activeEnd': round(fe / FPS, 4), 'recoveryEnd': anim['clips']['Emerge']['duration'],
        'points': {'EmergeCenter': point_rec(rig, 'Root', mid), 'LeftFist': point_rec(rig, 'LeftHand', cl),
                   'RightFist': point_rec(rig, 'RightHand', cr)},
        'eyesWake': round(M.EM['wake'] / FPS, 4),
        'rootStart': r4(D.ROOT_START_REAL), 'rootStartStudio': studio(D.ROOT_START_REAL), 'rootEnd': [0.0, 0.0, 0.0],
        'coffinOrigin': r4(D.COFFIN_START_REAL), 'coffinOriginStudio': studio(D.COFFIN_START_REAL),
        'emergeOut': D.EMERGE_OUT,
        'coffinCavity': {'floorZ': D.CAVITY_REAL['floor'], 'frontY': D.CAVITY_REAL['front'], 'backY': D.CAVITY_REAL['back'],
                         'ceilingZ': D.CAVITY_REAL['ceiling'], 'maxWidth': D.CAVITY_REAL['width_at_shoulder'],
                         'lidHingeY': D.LID_HINGE_Y, 'lidTopZ': D.LID_TOP_Z,
                         'source': 'round10-props exports/Sarcophagus.fbx + props-manifest.json (fourth pass 2026-10-10)',
                         'frame': 'coffin space, origin = cavity floor centre at ground level'},
        'steps': [{'foot': 'Right', 'start': round(M.EM['step1'] / FPS, 4), 'land': round(M.EM['step1e'] / FPS, 4)},
                  {'foot': 'Left', 'start': round(M.EM['step2'] / FPS, 4), 'land': round(M.EM['step2e'] / FPS, 4)},
                  {'foot': 'Right', 'start': round(M.EM['step3'] / FPS, 4), 'land': round(M.EM['step3e'] / FPS, 4)}],
        'stepsNote': 'Right foot forward to the front edge of the cavity floor, left foot over the rim down to the ground, '
                     'right foot down beside it at the final spot, then the fist plant.'}
    rest_pose(rig)
    V = eval_verts(objs)
    allv = np.concatenate(list(V.values()))
    body_T = loop_tris(objs['Body'])
    Vb = V['Body']
    a, b, c = Vb[body_T[:, 0]], Vb[body_T[:, 1]], Vb[body_T[:, 2]]
    vol = np.einsum('ij,ij->i', a, np.cross(b, c)) / 6.0
    cz = float(((a + b + c)[:, 2] / 4.0 * vol).sum() / vol.sum())
    game = {
        'attacks': attacks,
        'actions': {'Roar': {'duration': anim['clips']['Roar']['duration'], 'chestHits': [round(M.ROAR['hit1'] / FPS, 4),
                                                                                         round(M.ROAR['hit2'] / FPS, 4)],
                             'enrage': True, 'hits': False}},
        'rootHeight': round(float(sk.head['HumanoidRootPart'][2]) * D.SC, 4),
        'designScale': D.SC,
        'height': round(float(allv[:, 2].max()), 4),
        'footprintRadius': round(float(np.sqrt((allv[:, :2] ** 2).sum(1)).max()), 4),
        'bodyCentreHeight': round(cz, 4),
        'groundOffset': round(max(0.0, -float(allv[:, 2].min())), 4),
        'walk': {'strideLength': round(M.WALK_STRIDE * D.SC, 4), 'nominalSpeed': round(M.WALK_STRIDE * D.SC / M.WALK_T, 4),
                 'cycle': round(M.WALK_T, 4), 'note': 'feet stay planted up to playback 2.6x -> 2.6 * nominalSpeed'},
        'notes': "Times in seconds from clip start (whole 24 fps frames of AnimationData.json). Offsets are in the named bone's "
                 "local space (Blender axes, studs); root positions are model root space (Blender axes, the boss's final spot "
                 "at the origin); *Studio vectors use the (-X, Z, Y) mapping. FistHook: sweep a capsule of capsuleRadius between "
                 "HookFist and HookMid over impact..activeEnd (sampled per frame in 'sweep'). Emerge starts with the root emergeOut (4.9) "
                 "studs behind (+Y Blender / +Z Studio) and 0.8 up, standing on the coffin's cavity floor, steps down out of the "
                 "open front and ends exactly at the origin; eyesWake is when "
                 "the EyeGlow Neon should fade in.",
    }
    return game


def export_studio_fbx(st, tex):
    rig, objs = st['rig'], st['objs']
    rest_pose(rig)
    rig.data.pose_position = 'REST'
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    rig.select_set(True)
    for ob in objs.values():
        ob.select_set(True)
    bpy.context.view_layer.objects.active = rig
    GAME.mkdir(parents=True, exist_ok=True)
    fbx = GAME / f'{NAME}_Studio.fbx'
    bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, object_types={'ARMATURE', 'MESH'},
                             add_leaf_bones=False, use_armature_deform_only=True, bake_anim=False, axis_forward='-Z',
                             axis_up='Y', apply_unit_scale=True, global_scale=1.0, mesh_smooth_type='OFF',
                             use_mesh_modifiers=False, primary_bone_axis='Y', secondary_bone_axis='X',
                             path_mode='COPY', embed_textures=True)
    fbm = GAME / f'{NAME}_Studio.fbm'
    fbm.mkdir(exist_ok=True)
    shutil.copy2(HERE / 'textures' / tex['delivery'], fbm / tex['delivery'])
    rig.data.pose_position = 'POSE'
    return fbx


def append_mummy():
    p = HERE.parent / 'mob-production' / 'combat-ready' / 'mummy' / 'Model.blend'
    if not p.exists():
        return None
    with bpy.data.libraries.load(str(p), link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n not in ('Plane', 'Camera', 'Area', 'Area.001', 'Area.002')]
    col = review_collection()
    root = bpy.data.objects.new('MummyCompare', None)
    col.objects.link(root)
    for o in dst.objects:
        if o is None:
            continue
        col.objects.link(o)
        if o.parent is None:
            o.parent = root
    root.location = (4.9 * D.SC, 0.6, 0.0)
    root.rotation_euler = (0, 0, math.radians(-12))
    return root


def deliver(st, log):
    rig, objs = st['rig'], st['objs']
    GAME.mkdir(parents=True, exist_ok=True)
    anim, samp_err = anim_data(st)
    log('AnimationData sampled; max |action - solved basis|', samp_err)
    (GAME / 'AnimationData.json').write_text(json.dumps(anim, separators=(',', ':')))
    closure = clip_closure(anim)
    game = boss_data(st, anim)
    (GAME / 'BossGameData.json').write_text(json.dumps(game, indent=1))
    ch = st['checks']
    em = st['clips']['Emerge']
    # coffin fit, measured on the evaluated meshes at Emerge frame 0
    set_frame(rig, 'Emerge', 0)
    V = eval_verts(objs)
    allv = np.concatenate(list(V.values()))
    names = np.concatenate([[k] * len(v) for k, v in V.items()])
    prof = D.cavity_clearance_real(allv, inside_only=True)
    i0 = int(np.argmin(prof))
    bvh = coffin_bvh('Body')
    bvh_lid = coffin_bvh('Lid')
    real0 = coffin_signed(bvh, allv) if bvh else None
    frames, lid_frames = [], []
    worst = (9.0, None, None, None)
    worst_wall = (9.0, None, None, None)
    worst_lid = (9.0, None, None, None)
    for f in range(len(em['frames'])):
        set_frame(rig, 'Emerge', f)
        Vf = eval_verts(objs)
        av = np.concatenate(list(Vf.values()))
        nm = np.concatenate([[k] * len(v) for k, v in Vf.items()])
        d = coffin_signed(bvh, av) if bvh else D.cavity_clearance_real(av)
        j = int(np.argmin(d))
        frames.append(round(float(d[j]), 4))
        if d[j] < worst[0]:
            worst = (float(d[j]), f, str(nm[j]), r4(av[j]))
        dw = np.where(av[:, 2] > D.CAVITY_REAL['floor'] + 0.2, d, 9.0)      # walls, rim, ceiling (not the soles on the floor)
        j = int(np.argmin(dw))
        if dw[j] < worst_wall[0]:
            worst_wall = (float(dw[j]), f, str(nm[j]), r4(av[j]))
        if bvh_lid is not None:
            dl = coffin_signed(bvh_lid, av, deep=0.7)
            j = int(np.argmin(dl))
            lid_frames.append(round(float(dl[j]), 4))
            if dl[j] < worst_lid[0]:
                worst_lid = (float(dl[j]), f, str(nm[j]), r4(av[j]))
    vlo, vhi = allv.min(0), allv.max(0)
    sides = {'x': np.abs(allv[:, 0]) - D.cavity_halfwidth_real(allv[:, 2])}
    # cavity the start pose needs, in cavity space: origin = root start (cavity floor centre), heights from the floor
    CL = 0.12
    rel = allv - D.ROOT_START_REAL
    need = []
    for z0 in np.arange(0.0, float(rel[:, 2].max()) + 1e-6, 0.5):
        sel = (rel[:, 2] >= z0) & (rel[:, 2] < z0 + 0.5)
        if sel.any():
            q = rel[sel]
            need.append({'zFrom': round(float(z0), 2), 'zTo': round(float(z0) + 0.5, 2),
                         'halfWidth': round(float(np.abs(q[:, 0]).max()) + CL, 3),
                         'minX': round(float(q[:, 0].min()) - CL, 3), 'maxX': round(float(q[:, 0].max()) + CL, 3),
                         'frontY': round(float(q[:, 1].min()) - CL, 3), 'backY': round(float(q[:, 1].max()) + CL, 3),
                         'depth': round(float(q[:, 1].max() - q[:, 1].min()) + 2 * CL, 3)})
    req = {'clearance': CL, 'height': round(float(rel[:, 2].max()) + CL, 3),
           'maxHalfWidth': round(float(np.abs(rel[:, 0]).max()) + CL, 3),
           'frontY': round(float(rel[:, 1].min()) - CL, 3), 'backY': round(float(rel[:, 1].max()) + CL, 3),
           'depth': round(float(rel[:, 1].max() - rel[:, 1].min()) + 2 * CL, 3),
           'byHeight': need,
           'frame': 'cavity space: origin = Emerge rootStart (cavity floor centre, 0.8 above ground, emergeOut behind the final '
                    'spot); +X his left, -Y the open front he steps out of, Z up from the cavity floor. Blender axes, studs; '
                    'Studio = (-x, z, y).',
           'note': 'Emerge frame 0 start pose (evaluated meshes) + 0.12 clearance each side, 0.5-stud height bands.'}
    rest_pose(rig)
    Vi = np.concatenate(list(eval_verts(objs).values()))
    req['idleBackYFromFinalSpot'] = round(float(Vi[:, 1].max()), 3)
    req['idleNote'] = ('Idle pose back extent (final-spot space). The coffin front face must stay behind it plus clearance, '
                       'i.e. coffin front face y >= this + 0.12. Fourth-pass coffin at emergeOut 4.9: front rim face at '
                       '+%.2f.' % (D.EMERGE_OUT + D.CAVITY_REAL['front']))
    coffin = {'cavity': 'round10-props Sarcophagus fourth pass (exports/Sarcophagus.fbx): cavity floor z 0.8, front rim plane '
                        'y -2.90, back +2.90, ceiling 12.7, up to 7.0 wide (coffin space); coffin origin at the boss final '
                        'spot + (0, %.1f, 0); lid fallen open flat in front (hinge y -4.157 coffin space, top 1.257 high)' % D.EMERGE_OUT,
              'rootStart': r4(D.ROOT_START_REAL), 'poseMin': r4(vlo), 'poseMax': r4(vhi), 'poseSize': r4(vhi - vlo),
              'startMinClearanceProfile': round(float(prof[i0]), 4), 'startMinClearanceAt': [str(names[i0]), r4(allv[i0])],
              'startMinSideWallClearance': round(float(-sides['x'].max()), 4),
              'startMinClearanceRealMesh': (round(float(real0.min()), 4) if real0 is not None else None),
              'clipMinClearanceRealMesh': {'value': round(worst[0], 4), 'frame': worst[1], 'section': worst[2], 'at': worst[3]},
              'clipMinClearancePerFrame': frames,
              'clipMinWallRimClearance': {'value': round(worst_wall[0], 4), 'frame': worst_wall[1], 'section': worst_wall[2],
                                          'at': worst_wall[3], 'note': 'points more than 0.2 above the cavity floor: walls, '
                                          'rim and ceiling only (the overall minimum is the soles standing on the floor)'},
              'lidMinClearance': {'value': round(worst_lid[0], 4), 'frame': worst_lid[1], 'section': worst_lid[2], 'at': worst_lid[3]},
              'lidClearancePerFrame': lid_frames,
              'fits': bool(prof[i0] > -0.02 and (real0 is None or real0.min() > -0.02)),
              'startPenetration': {k: round(v, 4) for k, v in em['coffin_info']['pen'].items()},
              'requiredCavity': req,
              'note': 'Clearance is signed distance to the coffin stone (negative = inside the stone). Feet standing on the '
                      'cavity floor read ~0 (contact).'}
    rest_pose(rig)
    # strike quality at impacts
    strike = {}
    sk = st['sk']

    def strike_rec(clip, f, sides, end):
        set_frame(rig, clip, f)
        Wm = bone_mats(rig)
        Bm = bone_basis(rig)
        rec = {}
        for s in sides:
            shp = Wm[s + 'UpperArm'][:3, 3]
            wr = Wm[s + 'Hand'][:3, 3]
            ext = (sk.fist_bottom if end == 'fistbottom' else sk.fist_center) * D.SC
            eff = wr + Wm[s + 'Hand'][:3, 1] * ext
            L = (sk.length[s + 'UpperArm'] + sk.length[s + 'LowerArm']) * D.SC + ext
            el = Wm[s + 'LowerArm'][:3, 3]
            d = (eff - shp) / np.linalg.norm(eff - shp)
            e = el - shp
            e = e - d * (e @ d)
            e = e / max(np.linalg.norm(e), 1e-9)
            chest = Wm['UpperTorso'][:3, :3] @ sk.rest['UpperTorso'][:3, :3].T
            ec = chest.T @ e
            rec[s] = {'reach': round(float(np.linalg.norm(eff - shp) / L), 4),
                      'wristBendDeg': round(M.rot_angle(Bm[s + 'Hand'][:3, :3]), 3),
                      'elbowDeg': round(hinge_angle(Wm, s + 'UpperArm', s + 'LowerArm'), 2),
                      'elbowPoleChest': {'back': round(float(ec[1]), 3), 'down': round(float(-ec[2]), 3),
                                         'out': round(float(ec[0] * D.sgn(s)), 3)}}
        return rec

    strike['FistSlam'] = strike_rec('FistSlam', M.SLAM['impact'], D.SIDES, 'fistbottom')
    strike['FistHook'] = strike_rec('FistHook', M.HOOK['impact'], ['Right'], 'fistcenter')
    strike['Emerge'] = strike_rec('Emerge', M.EM['impact'], D.SIDES, 'fistbottom')
    sp = ch['FistSlam']['fistSpeed']['Left']
    strike['FistSlam']['fistSpeedPeakFrame'] = int(np.argmax(sp[:M.SLAM['impact'] + 1])) + 1
    sp = ch['FistHook']['fistSpeed']['Right']
    strike['FistHook']['fistSpeedPeakFrame'] = int(np.argmax(sp[:M.HOOK['follow']])) + 1
    rest_pose(rig)
    summ = summary(ch)
    fails = []
    if summ['groundMinZ'][0] < -0.05:
        fails.append(f'ground penetration {summ["groundMinZ"]}')
    if summ['fistPenetration'][0] > 0.05:
        fails.append(f'fist through body {summ["fistPenetration"]}')
    if summ['forearmPenetration'][0] > 0.05:
        fails.append(f'forearm through body {summ["forearmPenetration"]}')
    if summ['armArmPenetration'][0] > 0.05:
        fails.append(f'arm through arm {summ["armArmPenetration"]}')
    if summ['hingeMin'][0] < -5 or summ['hingeMax'][0] > 150:
        fails.append(f'hinge range {summ["hingeMin"]} {summ["hingeMax"]}')
    if summ['twistMax'][0] > 70:
        fails.append(f'twist {summ["twistMax"]}')
    if summ['boneStepMax'][0] > 45:
        fails.append(f'bone step {summ["boneStepMax"]}')
    if summ['footDriftMax'][0] > 0.05:
        fails.append(f'foot drift {summ["footDriftMax"]}')
    if summ['jointRetentionMin'][0] < 0.85:
        fails.append(f'joint section retention {summ["jointRetentionMin"]}')
    for k, e in closure.items():
        for kk, v in e.items():
            if v > 1e-5:
                fails.append(f'{k} {kk} {v}')
    # walls, rim and floor of the real (fourth-pass) coffin body: every Emerge frame (soles standing on the floor read ~0)
    if coffin['startMinClearanceRealMesh'] is not None and coffin['startMinClearanceRealMesh'] < -0.03:
        fails.append(f'coffin start pose in the stone {coffin["startMinClearanceRealMesh"]}')
    if coffin['clipMinClearanceRealMesh']['value'] < -0.03:
        fails.append(f'Emerge through the coffin walls/rim {coffin["clipMinClearanceRealMesh"]}')
    coffin['gate'] = ('body (walls, rim, floor): gated at -0.03 every frame. Lid: reported, see lidNote.')
    y0, y1 = D.EMERGE_OUT + D.LID_HINGE_Y, D.EMERGE_OUT + D.LID_HINGE_Y - 13.5
    coffin['lidNote'] = ('The open lid lies flat in front of the coffin, its top %.3f above the ground, covering final-spot '
                         'y %.2f to %.2f. The final spot (emergeOut %.1f) is on it, and Emerge ends in the Idle pose standing on '
                         'the ground (root at the origin), so the last footfalls and the fist plant are inside the lid slab '
                         'by up to its thickness. No root travel that ends on the ground can avoid that; the lid needs to lie '
                         'flush with the ground (its open frame lowered %.3f) or out of the exit path.'
                         % (D.LID_TOP_Z, y0, y1, D.EMERGE_OUT, D.LID_TOP_Z))
    for clip, rec in strike.items():
        if clip == 'Emerge':
            continue
        for s, r in rec.items():
            if isinstance(r, dict) and r['reach'] < 0.95:
                fails.append(f'{clip} {s} reach {r["reach"]}')
    checks = {'summary': summ, 'clips': ch, 'closure': closure, 'coffinFit': coffin, 'strikes': strike,
              'contacts': {'FistSlamImpactTargetZ': round(st['clips']['FistSlam']['impact_z'], 4),
                           'RoarFistChestGap': st['clips']['Roar']['gaps'], 'DeathPlant': st['clips']['Death']['plant'],
                           'EmergePlant': em['plant']},
              'deathLift': [round(x, 4) for x in st['clips']['Death']['lift']],
              'sampledVsSolvedMaxError': samp_err, 'passed': not fails, 'failures': fails,
              'notes': 'Blender-evaluated (armature modifier) meshes, every frame of every clip at 24 fps. '
                       'Penetration = signed distance of every Blender-evaluated fist / forearm vertex to every body part '
                       'except the limb\'s own arm, each part evaluated in its bone\'s rest space from the sculpt fields the '
                       'mesh was extracted from (bandage relief +-0.03 not included). jointSectionRetention = convex area of the posed body '
                       'mesh cut by the joint bisector plane (triangles within ~1 stud of the joint) / rest, every 2nd frame. '
                       'jointConeVolumeInfo (cone from the joint to the blend-zone triangles) is kept for information only: '
                       'it counts a normally closing elbow/knee crease as lost volume, so it is not used as the gate.'}
    (GAME / 'GameChecks.json').write_text(json.dumps(checks, indent=1, default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o)))
    log('game checks', 'PASSED' if not fails else fails)
    fbx = export_studio_fbx(st, st['tex'])
    log('studio fbx', fbx)
    renders(st, log)
    manifest(st, game, checks)
    for a in bpy.data.actions:
        a.use_fake_user = True
    rest_pose(rig)
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE / f'{NAME}.blend'), compress=True, relative_remap=True)
    log('saved', HERE / f'{NAME}.blend')


def renders(st, log):
    rig, objs = st['rig'], st['objs']
    setup_review_scene()
    rest_pose(rig)
    game_clips_sheet(st, PREV / 'GameClips.png')
    strip(st, 'FistSlam', [M.SLAM['top'], M.SLAM['impact'], 37], ['WINDUP', 'IMPACT', 'RECOVER'], ['ClipFront', 'ClipSide'],
          PREV / 'Attack_FistSlam.png')
    strip(st, 'FistHook', [M.HOOK['wind'], M.HOOK['impact'], M.HOOK['follow'] + 4], ['WINDUP', 'IMPACT', 'RECOVER'],
          ['ClipFront', 'ClipSide'], PREV / 'Attack_FistHook.png')
    box = cavity_wire()
    tiles = []
    for f in (0, M.EM['wake'], M.EM['step1e'], M.EM['step2e'], M.EM['impact'], M.EMERGE_N):
        set_frame(rig, 'Emerge', f)
        a = workbench_view('Coffin', (330, 330), color='TEXTURE')
        draw_text(a, 6, 6, 'EMERGE %.2fS' % (f / FPS), scale=2)
        tiles.append(a)
    save_rgb(tile(tiles, 3), PREV / 'Emerge.png')
    for n in ('CoffinCavityBox', 'CoffinLidWire'):
        if bpy.data.objects.get(n):
            bpy.data.objects[n].hide_render = True
    rest_pose(rig)
    log('workbench previews done')
    cycles_setup()
    for view, res in (('Front', (820, 1000)), ('Back', (820, 1000)), ('Side', (820, 1000)), ('ThreeQuarter', (820, 1000))):
        aim(view)
        render_rgb(PREV / f'{view}.png', res)
    mum = append_mummy()
    aim('Hero')
    render_rgb(PREV / 'Hero.png', (1024, 800))
    if mum is not None:
        for o in [mum] + list(mum.children_recursive):
            o.hide_render = True
    log('cycles renders done (mummy appended for Hero: %s)' % (mum is not None))


def manifest(st, game, checks):
    sk, objs = st['sk'], st['objs']
    ref = HERE.parent / 'art-references' / 'round-10-modeling-pack-2026-10-09' / '04-tomb-warden.png'
    man = {
        'asset': NAME, 'bossId': BOSS_ID, 'units': '1 Blender unit = 1 stud; faces -Y, +Z up, his left = +X',
        'reference': {'path': 'art-references/round-10-modeling-pack-2026-10-09/04-tomb-warden.png', 'sha256': sha(ref)},
        'sections': {sec: {'object': ob.name, 'triangles': st['tris'][sec], 'material': f'{NAME}_{sec}'} for sec, ob in objs.items()},
        'triangles_total': int(sum(st['tris'].values())),
        'bones': [{'name': n, 'parent': sk.parent[n], 'head': r4(sk.head[n] * D.SC), 'length': round(sk.length[n] * D.SC, 4)} for n in sk.order],
        'rigid': {'Mask': 'Head', 'EyeGlow': 'Head', 'LeftFist': 'LeftHand', 'RightFist': 'RightHand'},
        'textures': st['tex'], 'height': game['height'], 'footprintRadius': game['footprintRadius'],
        'exports': {p.name: sha(p) for p in sorted(GAME.glob('*.*')) if p.is_file()},
        'fist': {'bottomAlongHand': round(sk.fist_bottom * D.SC, 4), 'centreAlongHand': round(sk.fist_center * D.SC, 4)},
        'designScale': D.SC,
        'checksPassed': checks['passed'],
    }
    (HERE / 'manifest.json').write_text(json.dumps(man, indent=1))
