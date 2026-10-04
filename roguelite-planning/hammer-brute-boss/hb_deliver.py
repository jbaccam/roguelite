"""Full-stage renders, checks and reports for the Hammer Brute (runs inside Blender).

Called from build_hammer_brute.py when HB_STAGE=model|full. Every image written
here is a real Blender render of the posed, skinned rig. Only the preview set
asked for is produced: Reference_Match, Turnaround, Face_Closeup, Grip_Closeup,
Rig_Bones and RigTest_ROM (Comparison_SideBySide comes from compare_reference.py).
"""
import hashlib
import json
import math
import os
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

import hb_blender as B
import hb_design as D
import hb_grip as G
import hb_parts as FP
import hb_pose as PO

HERE = Path(__file__).resolve().parent
PREV = HERE / 'previews'
WORK = HERE / '_work'
NAME = 'HammerBrute'
WS = 1.0          # world scale from the build (final studs per design unit)


def log(*a):
    print('[HBD]', *a, flush=True)


def aim_camera(cam, loc, target, lens=50.0, ortho=None):
    cam.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    if ortho:
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = ortho
    else:
        cam.data.type = 'PERSP'
        cam.data.lens = lens
    cam.data.sensor_fit = 'AUTO'
    cam.data.sensor_width = 36.0
    cam.data.shift_x = cam.data.shift_y = 0.0
    cam.data.clip_start = 0.3
    cam.data.clip_end = 400


def render_to(path, res, samples=16, engine='CYCLES'):
    sc = bpy.context.scene
    sc.render.engine = engine
    if engine == 'CYCLES':
        B.enable_gpu()
        sc.cycles.samples = samples
        sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return path


def load_rgb(path):
    img = bpy.data.images.load(str(path), check_existing=False)
    a = B.image_pixels(img)[::-1, :, :3].copy()
    bpy.data.images.remove(img)
    return a


def save_rgb(arr, path):
    h, w = arr.shape[:2]
    img = bpy.data.images.new(Path(path).stem, w, h, alpha=False)
    img.colorspace_settings.name = 'sRGB'
    B.set_image_pixels(img, np.concatenate([arr[::-1], np.ones((h, w, 1))], 2))
    img.filepath_raw = str(path)
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


# 5x7 bitmap font for sheet labels (so no external image library is needed)
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
    '+': '00000001000010011111001000010000000', '(': '00010001000100001000010000010000010',
    ')': '01000001000001000010000100010001000', '%': '11000110010001000100010001001100011',
    ',': '00000000000000000000001100010001000', '=': '00000000001111100000111110000000000',
}


def draw_text(arr, x, y, text, scale=2, color=(1.0, 1.0, 0.6)):
    for ch in text.upper():
        g = _FONT.get(ch, _FONT[' '])
        for r in range(7):
            for c in range(5):
                if g[r * 5 + c] == '1':
                    y0, x0 = y + r * scale, x + c * scale
                    arr[y0:y0 + scale, x0:x0 + scale] = color
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


def rig_obj():
    return bpy.data.objects[NAME + '_Rig']


def meshes():
    return [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith(NAME + '_')]


def set_action(name, frame):
    rig = rig_obj()
    rig.animation_data.action = bpy.data.actions[name]
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()


def posed_bone_mats(rig):
    return {pb.name: np.array(rig.matrix_world @ pb.matrix) for pb in rig.pose.bones}


def evaluated_verts(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    ev.to_mesh_clear()
    V = co.reshape(-1, 3)
    M = np.array(ob.matrix_world)
    return V @ M[:3, :3].T + M[:3, 3]


# ------------------------------------------------------------------ sheets
def turnaround(cam):
    set_action('ReferencePose', 1)
    tiles = []
    tgt = (-0.8, -1.2, 6.6)
    for lab, loc in (('FRONT', (-0.8, -44, 6.6)), ('THREE-QUARTER', (-31, -32, 9.0)), ('SIDE', (-44, -1.2, 6.6)),
                     ('BACK', (-0.8, 42, 6.6))):
        aim_camera(cam, loc, tgt, ortho=17.6)
        p = render_to(WORK / ('turn_%s.png' % lab), (640, 760), samples=32)
        t = load_rgb(p)
        draw_text(t, 10, 10, lab, scale=3)
        tiles.append(t)
    save_rgb(tile(tiles, 4), PREV / 'Turnaround.png')


def face_closeup(cam, sk):
    set_action('ReferencePose', 1)
    mats = posed_bone_mats(rig_obj())
    X = mats['Head'] @ np.linalg.inv(sk.rest['Head'])
    c = X[:3, :3] @ (D.Hd(0.0, -0.9, -0.15) * WS) + X[:3, 3]
    fwd = X[:3, :3] @ np.array([0, -1.0, 0])
    aim_camera(cam, c + fwd * 8.0 + np.array([0, 0, 0.6]), c, lens=70)
    render_to(PREV / 'Face_Closeup.png', (900, 900), samples=48)


def grip_closeup(cam):
    """Both hands on the haft from two angles each (REF / idle frame 0)."""
    set_action('ReferencePose', 1)
    mats = posed_bone_mats(rig_obj())
    tiles = []
    for side in ('Right', 'Left'):
        Hm = mats[side + 'Hand']
        c = Hm[:3, 3] + Hm[:3, :3] @ np.array([0, 0.85, -0.45])
        side_out = np.array([-1.0 if side == 'Right' else 1.0, 0, 0])
        h = mats['Hammer'][:3, 1]
        inner = -h if side == 'Right' else h
        views = (('front low', c + np.array([0, -7.0, -1.6]) + side_out * 0.6),
                 ('along the haft', c + inner * 6.0 + np.array([0, -3.2, 1.4])))
        for lab, loc in views:
            aim_camera(cam, loc, c, lens=60)
            p = render_to(WORK / ('grip_%s_%s.png' % (side, lab[:5])), (620, 620), samples=40)
            t = load_rgb(p)
            draw_text(t, 8, 8, '%s HAND - %s' % (side.upper(), lab.upper()), scale=2)
            tiles.append(t)
    save_rgb(tile(tiles, 4), PREV / 'Grip_Closeup.png')


def bone_overlay(cam):
    set_action('ReferencePose', 1)
    rig = rig_obj()
    mats = posed_bone_mats(rig)
    V, F = [], []
    for b in rig.data.bones:
        if not b.use_deform:
            continue
        M = mats[b.name]
        L = b.length
        h = M[:3, 3]
        y, x, z = M[:3, 1], M[:3, 0], M[:3, 2]
        w = min(0.16, 0.1 * L + 0.03)
        base = len(V)
        V += [h, h + y * L * 0.2 + x * w, h + y * L * 0.2 + z * w, h + y * L * 0.2 - x * w, h + y * L * 0.2 - z * w,
              h + y * L]
        for a, c in ((1, 2), (2, 3), (3, 4), (4, 1)):
            F.append((base, base + a, base + c))
            F.append((base + 5, base + c, base + a))
    me = bpy.data.meshes.new('BoneViz')
    me.from_pydata([tuple(v) for v in V], [], F)
    ob = bpy.data.objects.new('BoneViz', me)
    bpy.data.collections['REVIEW_ONLY'].objects.link(ob)
    sc = bpy.context.scene
    aim_camera(cam, (-0.8, -44, 6.6), (-0.8, -1.2, 6.6), ortho=17.6)
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'TEXTURE'
    ob.hide_render = True
    p1 = render_to(WORK / 'bones_model.png', (820, 980), engine='BLENDER_WORKBENCH')
    hidden = []
    for o in bpy.data.objects:
        if o.type == 'MESH' and o is not ob and not o.hide_render:
            o.hide_render = True
            hidden.append(o)
    ob.hide_render = False
    sc.display.shading.color_type = 'SINGLE'
    sc.display.shading.single_color = (1.0, 0.55, 0.1)
    sc.render.film_transparent = True
    sc.render.image_settings.color_mode = 'RGBA'
    sc.render.filepath = str(WORK / 'bones_only.png')
    bpy.ops.render.render(write_still=True)
    sc.render.film_transparent = False
    sc.render.image_settings.color_mode = 'RGB'
    for o in hidden:
        o.hide_render = False
    ob.hide_render = True
    a = load_rgb(p1)
    img = bpy.data.images.load(str(WORK / 'bones_only.png'))
    bo = B.image_pixels(img)[::-1].copy()
    bpy.data.images.remove(img)
    al = bo[:, :, 3:4]
    comp = a * (1 - al * 0.95) * 0.75 + bo[:, :, :3] * al * 0.95
    n = sum(1 for b in rig.data.bones if b.use_deform)
    draw_text(comp, 10, 10, 'DEFORM SKELETON (%d BONES) OVER MODEL - REFERENCE POSE' % n, scale=2)
    save_rgb(comp, PREV / 'Rig_Bones.png')
    sc.display.shading.color_type = 'TEXTURE'


def rom_sheet(info, cam):
    tiles = []
    for f, lab in info['poses']:
        set_action('RigTest_ROM', f)
        aim_camera(cam, (-15.0, -24.0, 8.5), (-0.6, -1.6, 6.9), lens=50)
        p = render_to(WORK / ('rom_%03d.png' % f), (420, 500), samples=16)
        t = load_rgb(p)
        draw_text(t, 6, 6, ('F%d %s' % (f, lab))[:30], scale=2)
        tiles.append(t)
    save_rgb(tile(tiles, 4), PREV / 'RigTest_ROM.png')


# ------------------------------------------------------------------ checks
def name_clash_check(rig):
    bones = {b.name for b in rig.data.bones}
    mesh_names = {o.name for o in meshes()} | {o.data.name for o in meshes()}
    mats = {m.name for o in meshes() for m in o.data.materials}
    return {'mesh_names': sorted(mesh_names), 'clashes_with_bones': sorted(mesh_names & bones),
            'material_clashes_with_bones': sorted(mats & bones),
            'materials_named_like_meshes': all(len(o.data.materials) == 1 and o.data.materials[0].name == o.name
                                               for o in meshes())}


def weight_check(rig):
    deform = {b.name for b in rig.data.bones if b.use_deform}
    out = {}
    for ob in meshes():
        n = len(ob.data.vertices)
        cnt = np.zeros(n, int)
        tot = np.zeros(n)
        gi = {g.index: g.name for g in ob.vertex_groups}
        unknown = set()
        for v in ob.data.vertices:
            for g in v.groups:
                if g.weight > 0:
                    cnt[v.index] += 1
                    tot[v.index] += g.weight
                    if gi[g.group] not in deform:
                        unknown.add(gi[g.group])
        out[ob.name] = {'vertices': n, 'max_influences': int(cnt.max()), 'unweighted': int((cnt == 0).sum()),
                        'max_sum_error': round(float(np.abs(tot - 1).max()), 5), 'non_deform_groups': sorted(unknown)}
    return out


def grip_world_check(sk):
    """Every phalanx's closest approach to the haft surface on the posed rig in
    the reference pose (both hands)."""
    set_action('ReferencePose', 1)
    mats = posed_bone_mats(rig_obj())
    H = mats['Hammer']
    o = H[:3, 3]
    h = H[:3, 1]
    out = {}
    for side in ('Right', 'Left'):
        rows = {}
        for i, nm in enumerate(D.FINGER_NAMES + ['Thumb']):
            segs = []
            for k in range(3):
                b = '%s%s%d' % (side, nm, k + 1)
                M = mats[b]
                L = sk.length[b]
                if nm == 'Thumb':
                    r0, r1 = (r * WS for r in D.THUMB_RAD[k])
                else:
                    r0 = D.SEG_RAD[k] * D.FINGER_RAD_SCALE[i] * WS
                    r1 = D.SEG_RAD[min(k + 1, 2)] * D.FINGER_RAD_SCALE[i] * WS
                best = 9.0
                for t in np.linspace(0.15, 1.0, 18):
                    p = M[:3, 3] + M[:3, 1] * L * t
                    v = p - o
                    d = np.linalg.norm(v - h * (v @ h))
                    best = min(best, d - D.HAFT_R * WS - (r0 + (r1 - r0) * t))
                segs.append(round(float(best), 4))
            rows[nm] = segs
        out[side] = rows
    win = G.CONTACT_WINDOW
    out['fingers_all_in_window'] = all(win[0] <= g <= win[1] for s in ('Right', 'Left')
                                       for nm in D.FINGER_NAMES for g in out[s][nm])
    out['window'] = list(win)
    return out


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()


# ------------------------------------------------------------------ stages
def grip_summary(sk):
    ref = G.solve_reference()
    w = WS
    sL = ref['s_left']
    RH_in_H = np.linalg.inv(sk.ref['Hammer']) @ sk.ref['RightHand']
    LH_in_H = np.linalg.inv(sk.ref['Hammer']) @ sk.ref['LeftHand']
    return {
        'note': 'Distances s are measured along the haft from the hammer-head centre toward the butt. Hammer bone '
                'space: origin = right carry grip on the haft axis, +Y toward the head, +Z = striking-face normal. '
                'Both thumbs point at the head (a sledgehammer grip), so the right hand can slide down to the '
                'left one for Slam/Swing/Spin without regripping.',
        'units': 'final studs (design units x world_scale %.5f)' % w,
        'haft_radius': round(D.HAFT_R * w, 4),
        'carry_grips': {
            'right': {'s': round(D.S_RIGHT * w, 4), 'hammer_bone_y': 0.0},
            'left': {'s': round(sL * w, 4), 'hammer_bone_y': round((D.S_RIGHT - sL) * w, 4)},
            'distance_between': round((sL - D.S_RIGHT) * w, 4),
        },
        'butt_end': {'s': round((sL + 1.55) * w, 4), 'hammer_bone_y': round((D.S_RIGHT - sL - 1.55) * w, 4)},
        'attack_grip_range_right_hand': {
            's': [round(D.S_RIGHT * w, 4), round(D.S_RIGHT_ATTACK_MAX * w, 4)],
            'hammer_bone_y': [0.0, round((D.S_RIGHT - D.S_RIGHT_ATTACK_MAX) * w, 4)],
            'how': 'Slide the right hand toward the butt by translating the Hammer bone along its own +Y relative to '
                   'RightHand: Hammer_in_RightHand(slide) = Hammer_in_RightHand(0) @ Translate(0, slide, 0), '
                   'slide in [0, %.3f].' % ((D.S_RIGHT_ATTACK_MAX - D.S_RIGHT) * w),
        },
        'left_hand_stays_at': 'the left carry grip (the butt end) in every attack; IK_Grip_L rides on the Hammer bone',
        'iron_bands': {'s': [round(b * w, 4) for b in D.BANDS], 'raise': round(D.BAND_RAISE * w, 4),
                       'note': 'Near-flush (raised %.2f) so a sliding fist stays inside the -0.03 contact window.'
                               % D.BAND_RAISE},
        'collar_s': [round(c * w, 4) for c in D.COLLAR], 'butt_cap_raise': round(D.CAP_RAISE * w, 4),
        'Hammer_in_RightHand_4x4': [[round(float(x), 5) for x in r] for r in np.linalg.inv(RH_in_H)],
        'LeftHand_in_Hammer_4x4': [[round(float(x), 5) for x in r] for r in LH_in_H],
        'reference_wrists': {s: {'flex_deg': round(ref['wrist_flex_' + s], 2), 'deviation_deg': round(ref['wrist_dev_' + s], 2),
                                 'elbow_flex_deg': round(ref['elbow_flex_' + s], 2)} for s in ('Right', 'Left')},
    }


def write_grip_summary(sk, world):
    p = HERE / 'source' / 'grip_solution.json'
    data = json.loads(p.read_text())
    data['summary'] = grip_summary(sk)
    data['summary']['reference_pose_contact_measured_on_rig'] = world
    p.write_text(json.dumps(data, indent=1))
    return data['summary']


def write_reports(rig, sk, objs, tex_info, stats, checks, rom_info):
    set_action('ReferencePose', 1)
    posed = {sec: evaluated_verts(ob) for sec, ob in objs.items()}
    allp = np.concatenate(list(posed.values()))
    body_ref = np.concatenate([posed[s] for s in ('Body', 'Head', 'Shirt', 'Gear', 'Trousers') if s in posed])
    rest = np.concatenate([B.mesh_arrays(ob)[0] for ob in objs.values()])
    sections = {}
    for sec, ob in objs.items():
        sections[ob.name] = {'triangles': B.tri_count(ob), 'vertices': len(ob.data.vertices),
                             'faces': len(ob.data.polygons), 'material': ob.data.materials[0].name,
                             'texture_master': tex_info.get(sec, {}).get('master'),
                             'texture_delivery': tex_info.get(sec, {}).get('delivery')}
    import build_hammer_brute as BH   # noqa: F401  (hammer_points lives there)
    pts = BH.hammer_points()
    ref = G.solve_reference()
    manifest = {
        'asset': NAME,
        'reference': {'file': 'source/boss-reference.png',
                      'sha256': 'B401488FE31019B7D2179CBCF652D17082BA92E1B5ED7AD2BF2D5A64736CA6F6', 'size': [1086, 1448]},
        'units': "1 Blender unit = 1 Roblox stud; Z up, the character faces -Y, +X is the character's left",
        'dimensions_studs': {
            'top_of_head_reference_pose': round(float(body_ref[:, 2].max()), 3),
            'top_of_head_rest_pose': round(float(rest[:, 2].max()), 3),
            'width_reference_pose_incl_hammer': round(float(np.ptp(allp[:, 0])), 3),
            'depth_reference_pose_incl_hammer': round(float(np.ptp(allp[:, 1])), 3),
            'lowest_point_reference_pose': round(float(allp[:, 2].min()), 3),
            'world_scale_applied': round(WS, 5),
            'shoulder_joint_span': round(float(2 * D.SHOULDER[0] * WS), 3),
            'arm_lengths_upper_fore': [round(D.L_UPPER * WS, 3), round(D.L_FORE * WS, 3)],
            'hammer_head_half_extents_along_haft_strike_side': [round(float(v) * WS, 3) for v in D.HEAD_HALF],
            'haft_radius': round(D.HAFT_R * WS, 3),
            'haft_length_head_centre_to_butt': round((ref['s_left'] + 1.55) * WS, 3),
        },
        'points_in_Hammer_bone_space_blender': {
            'HammerFace': {'position': [round(float(v) * WS, 4) for v in pts['HammerFace'][0]],
                           'normal': [round(float(v), 4) for v in pts['HammerFace'][1]],
                           'note': 'centre of the FLAT striking face (the face that lands in a Slam)'},
            'HammerGrip': {'position': [round(float(v) * WS, 4) for v in pts['HammerGrip'][0]],
                           'note': 'on the haft axis halfway between the two carry grips'},
            'axes': 'Hammer bone: +Y along the haft toward the head, +Z = striking-face normal, X = Y x Z; origin '
                    '= right carry grip (centre of the right finger tunnel)',
            'helper_bones_in_blend': ['HammerFace', 'HammerGrip'],
        },
        'grip': json.loads((HERE / 'source' / 'grip_solution.json').read_text())['summary'],
        'bones': [{'name': b, 'parent': sk.parent[b], 'length': round(sk.length[b], 4),
                   'head_rest': [round(float(v), 4) for v in sk.rest[b][:3, 3]]} for b in sk.order],
        'bone_count_deform': len(sk.order),
        'non_deform_helpers_not_exported': [b.name for b in rig.data.bones if not b.use_deform],
        'hinge_conventions': {'LowerArm': '+X rotation = elbow flexion (both sides)',
                              'LowerLeg': '+X rotation = knee flexion (both sides)',
                              'fingers_and_thumbs': '+X rotation = curl toward the palm',
                              'Jaw': '+X opens', 'EyelidUpper': '+X closes',
                              'LowerArmTwist': 'roll about Y; share forearm roll ~50/50 with Hand'},
        'idle_start_pose': 'ReferencePose action, frame 1 (= RigTest_ROM frame 1)',
        'sections': sections,
        'triangles_total': sum(v['triangles'] for v in sections.values()),
        'actions': {a.name: {'frame_range': [int(a.frame_range[0]), int(a.frame_range[1])],
                             'markers': {m.name: m.frame for m in a.pose_markers}}
                    for a in bpy.data.actions if a.name in ('ReferencePose', 'RigTest_ROM')},
        'rig_test_rom': rom_info,
        'checks': checks,
        'textures': {},
        'camera_solution': json.loads((HERE / 'source' / 'camera_solution.json').read_text()),
    }
    for p in sorted((HERE / 'textures').glob('*.png')):
        manifest['textures'][p.name] = {'sha256': sha256(p), 'bytes': p.stat().st_size}
    (HERE / 'manifest.json').write_text(json.dumps(manifest, indent=1, default=str))
    poly = {'sections': {k: v['triangles'] for k, v in sections.items()},
            'total_triangles': manifest['triangles_total'], 'limit_per_mesh': 20000,
            'all_under_limit': all(v['triangles'] < 20000 for v in sections.values()),
            'weights': stats}
    (HERE / 'polygon-report.json').write_text(json.dumps(poly, indent=1, default=str))
    return manifest


def full_stage(rig, sk, objs, tex_info, stats, stage, make_action):
    scene = bpy.context.scene
    PREV.mkdir(exist_ok=True)
    skd = getattr(sk, 'design', sk)          # poses are solved in design units, scaled when keyed
    seq = PO.rom_keys(skd)
    step = 8
    ref = PO.Pose(skd)
    make_action(rig, sk, 'RigTest_ROM', [(1 + i * step, p) for i, (lab, p, inf) in enumerate(seq)] +
                [(1 + len(seq) * step, ref)])
    rom_info = {'poses': [(1 + i * step, lab) for i, (lab, p, inf) in enumerate(seq)],
                'metrics': {lab: _clean(inf) for lab, p, inf in seq}}
    cam = scene.camera
    if stage == 'full':
        set_action('ReferencePose', 1)
        import build_hammer_brute as BH
        BH.render(PREV / 'Reference_Match.png', samples=int(os.environ.get('HB_SAMPLES', '96')),
                  mask_path=WORK / 'render_mask.png')
        free = bpy.data.objects.new('ReviewCamera', bpy.data.cameras.new('ReviewCamera'))
        bpy.data.collections['REVIEW_ONLY'].objects.link(free)
        scene.camera = free
        turnaround(free)
        face_closeup(free, sk)
        grip_closeup(free)
        bone_overlay(free)
        rom_sheet(rom_info, free)
        scene.camera = cam
        scene.render.resolution_x, scene.render.resolution_y = 1086, 1448
        scene.render.engine = 'CYCLES'
        log('renders done')
    checks = {'names': name_clash_check(rig), 'weights': weight_check(rig), 'grip_reference_pose': grip_world_check(sk)}
    write_grip_summary(sk, checks['grip_reference_pose'])
    write_reports(rig, sk, objs, tex_info, stats, checks, rom_info)
    for img in bpy.data.images:
        if img.source == 'FILE' and not img.packed_file and img.filepath:
            try:
                img.pack()
            except RuntimeError:
                pass
    rig.animation_data.action = bpy.data.actions['ReferencePose']
    scene.frame_start, scene.frame_end = 1, 2
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE / f'{NAME}.blend'), compress=True)
    log('STAGE DONE', stage, json.dumps(checks['names']), checks['grip_reference_pose']['fingers_all_in_window'])


def _clean(d):
    out = {}
    for k, v in (d or {}).items():
        if isinstance(v, dict):
            out[k] = _clean(v)
        elif isinstance(v, (float, int, bool, str)):
            out[k] = round(v, 3) if isinstance(v, float) else v
        elif isinstance(v, (list, tuple)):
            out[k] = [round(float(x), 3) for x in v]
    return out
