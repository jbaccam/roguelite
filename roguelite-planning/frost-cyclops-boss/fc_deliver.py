"""Full-stage renders, checks and exports for the Frost Cyclops (runs inside Blender).

Called from build_frost_cyclops.py when FC_STAGE=full. Everything rendered here
is a real Blender render of the posed, skinned rig.
"""
import hashlib
import json
import math
import os
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

import fc_blender as B
import fc_design as D
import fc_parts as FP
import fc_pose as PO

HERE = Path(__file__).resolve().parent
PREV = HERE / 'previews'
WORK = HERE / '_work'
NAME = 'FrostCyclops'


def log(*a):
    print('[FCD]', *a, flush=True)


# ------------------------------------------------------------------ helpers
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
    w, h = img.size
    a = B.image_pixels(img)[::-1, :, :3].copy()      # top row first
    bpy.data.images.remove(img)
    return a


def save_rgb(arr, path):
    h, w = arr.shape[:2]
    img = bpy.data.images.new(Path(path).stem, w, h, alpha=False)
    img.colorspace_settings.name = 'sRGB'
    rgba = np.concatenate([arr[::-1], np.ones((h, w, 1))], 2)
    B.set_image_pixels(img, rgba)
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
    out = {}
    for pb in rig.pose.bones:
        out[pb.name] = np.array(rig.matrix_world @ pb.matrix)
    return out


# ----------------------------------------------------------- impact marker
def impact_marker():
    ob = bpy.data.objects.get('ImpactMarker')
    if ob:
        return ob
    n = 32
    V = [(math.cos(2 * math.pi * k / n) * r, math.sin(2 * math.pi * k / n) * r, 0.01) for r in (0.35, 0.55) for k in range(n)]
    F = [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    me = bpy.data.meshes.new('ImpactMarker')
    me.from_pydata(V, [], F)
    ob = bpy.data.objects.new('ImpactMarker', me)
    bpy.data.collections['REVIEW_ONLY'].objects.link(ob)
    m = bpy.data.materials.new('ImpactMarker')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    o = nt.nodes.new('ShaderNodeOutputMaterial')
    e = nt.nodes.new('ShaderNodeEmission')
    e.inputs['Color'].default_value = (0.1, 0.9, 1.0, 1)
    e.inputs['Strength'].default_value = 3.0
    nt.links.new(e.outputs[0], o.inputs['Surface'])
    me.materials.append(m)
    ob.hide_render = True
    return ob


# -------------------------------------------------------------- attack sheets
def _grip_cam(mats):
    grip = mats['Club'][:3, 3]
    Xh = mats['RightHand']
    out_dir = Vector(Xh[:3, 2]) * 0.9 + Vector((0.0, -0.8, 0.35))
    loc = Vector(grip) + out_dir.normalized() * 7.5
    return loc, Vector(grip) + Vector(Xh[:3, 1]) * 0.3


def attack_sheet(info, cam):
    """AttackCheck_Club.png (GroundSlam: carry / windup / mid-swing / impact /
    recovery x front, three-quarter, grip close-up) and AttackCheck_Stomp.png
    (weight shift / top of raise / mid-slam / impact / recovery x front, 3/4, side)."""
    rig = rig_obj()
    marker = impact_marker()
    out = {}
    for act, fname, views in (('GroundSlam', 'AttackCheck_Club.png', ('front', '3q', 'grip')),
                              ('Stomp', 'AttackCheck_Stomp.png', ('front', '3q', 'side'))):
        labs = info[act]['labels']
        order = (['carry', 'windup', 'mid-swing', 'impact', 'recovery'] if act == 'GroundSlam'
                 else ['weight shift', 'top of raise', 'mid-slam', 'impact', 'recovery'])
        rows = []
        for lab in order:
            f = labs[lab]
            set_action(act, f)
            mats = posed_bone_mats(rig)
            ip = info[act]['club_impact_point_root'] if act == 'GroundSlam' else info[act]['StompImpact_root']
            marker.location = (ip[0], ip[1], 0.0)
            marker.hide_render = lab != 'impact'
            tiles = []
            for v in views:
                if v == 'front':
                    aim_camera(cam, (-1.4, -34.0, 7.0), (-1.2, -2.5, 6.4), lens=52)
                elif v == '3q':
                    aim_camera(cam, (-22.0, -22.0, 9.5), (-1.2, -2.5, 6.2), lens=52)
                elif v == 'side':
                    aim_camera(cam, (-32.0, -2.0, 7.0), (0.0, -1.5, 6.2), lens=52)
                else:
                    loc, tgt = _grip_cam(mats)
                    aim_camera(cam, loc, tgt, lens=50)
                p = render_to(WORK / ('atk_%s_%s_%s.png' % (act, lab.replace(' ', '_'), v)), (380, 440),
                              samples=12)
                t = load_rgb(p)
                draw_text(t, 8, 8, '%s %s F%d' % (act, lab, f), scale=2)
                tiles.append(t)
            marker.hide_render = True
            gap = np.full((440, 6, 3), 0.08)
            row = tiles[0]
            for t in tiles[1:]:
                row = np.concatenate([row, gap, t], 1)
            rows.append(row)
            out['%s:%s' % (act, lab)] = {
                'frame': f,
                'club_impact_bone_root': [round(float(x), 4) for x in mats['ClubImpact'][:3, 3]],
                'grip_point_root': [round(float(x), 4) for x in mats['Club'][:3, 3]]}
        sheet = np.concatenate(rows, 0)
        head = np.zeros((40, sheet.shape[1], 3))
        head[:] = 0.05
        title = 'GROUND SLAM - FRONT / 3-4 / GRIP' if act == 'GroundSlam' else 'STOMP - FRONT / 3-4 / SIDE'
        draw_text(head, 10, 10, title + '  (CYAN RING = IMPACT POINT)', scale=3)
        save_rgb(np.concatenate([head, sheet], 0), PREV / fname)
    return out


def _workbench(transparent=False):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'TEXTURE'
    sc.display.shading.show_shadows = False
    sc.render.film_transparent = transparent
    sc.render.image_settings.color_mode = 'RGBA' if transparent else 'RGB'


def _render_rgba(path, res):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(str(path), check_existing=False)
    a = B.image_pixels(img)[::-1].copy()
    bpy.data.images.remove(img)
    if a.shape[2] == 3:
        a = np.concatenate([a, np.ones(a.shape[:2] + (1,))], 2)
    return a


def swing_arcs(info, cam):
    """Side-view ghost strips: every frame from windup to impact overlaid, older
    frames fainter (Workbench renders of the posed rig)."""
    ground = bpy.data.objects.get('Ground')
    ground.hide_render = True
    _workbench(transparent=True)
    specs = (('GroundSlam', list(range(info['GroundSlam']['labels']['windup'],
                                       info['GroundSlam']['impact_frame'] + 1))),
             ('Stomp', list(range(info['Stomp']['labels']['top of raise'], info['Stomp']['impact_frame'] + 1))))
    for act, frames in specs:
        if act == 'GroundSlam':
            aim_camera(cam, (-38.0, -3.0, 8.0), (-2.0, -2.5, 7.0), lens=40)
        else:
            aim_camera(cam, (-34.0, -3.0, 6.0), (0.0, -1.5, 5.5), lens=45)
        res = (1100, 900)
        comp = np.zeros((res[1], res[0], 3))
        comp[:] = (0.93, 0.95, 0.99)
        n = len(frames)
        for i, f in enumerate(frames):
            set_action(act, f)
            a = _render_rgba(WORK / ('arc_%s_%03d.png' % (act, f)), res)
            k = 0.25 + 0.75 * (i / max(1, n - 1)) ** 1.5
            al = a[:, :, 3:4] * k
            comp = comp * (1 - al) + a[:, :, :3] * al
        draw_text(comp, 12, 12, '%s SWING ARC - SIDE VIEW - FRAMES %d-%d (FAINT = EARLIER)' % (act, frames[0], frames[-1]),
                  scale=2, color=(0.1, 0.1, 0.15))
        save_rgb(comp, PREV / ('SwingArc_%s.png' % act))
    ground.hide_render = False
    bpy.context.scene.render.film_transparent = False
    bpy.context.scene.render.image_settings.color_mode = 'RGB'


def attack_videos(info, cam):
    """Workbench frames (three-quarter + side, side by side) -> mp4 at normal
    speed followed by half speed."""
    import shutil
    import subprocess
    ffmpeg = shutil.which('ffmpeg')
    _workbench(transparent=False)
    bpy.context.scene.display.shading.show_shadows = True
    made = {}
    for act in ('GroundSlam', 'Stomp'):
        f0, f1 = info[act]['frames']
        d = WORK / ('video_%s' % act)
        d.mkdir(exist_ok=True)
        for f in range(f0, f1 + 1):
            set_action(act, f)
            aim_camera(cam, (-20.0, -24.0, 10.0), (-1.2, -2.8, 6.0), lens=38)
            a = _render_rgba(WORK / 'v_a.png', (560, 600))[:, :, :3]
            aim_camera(cam, (-32.0, -3.0, 7.5), (-1.0, -2.5, 6.0), lens=38)
            b = _render_rgba(WORK / 'v_b.png', (560, 600))[:, :, :3]
            fr = np.concatenate([a, np.full((600, 4, 3), 0.1), b], 1)
            draw_text(fr, 10, 10, '%s F%d' % (act, f), scale=2, color=(0.1, 0.1, 0.15))
            save_rgb(fr, d / ('f%04d.png' % f))
        if ffmpeg:
            out = PREV / ('%s.mp4' % act)
            cmd = [ffmpeg, '-y', '-loglevel', 'error',
                   '-framerate', '30', '-start_number', str(f0), '-i', str(d / 'f%04d.png'),
                   '-framerate', '30', '-start_number', str(f0), '-i', str(d / 'f%04d.png'),
                   '-filter_complex', '[0:v]setpts=PTS-STARTPTS[a];[1:v]setpts=2*(PTS-STARTPTS)[b];'
                   '[a][b]concat=n=2:v=1[v]', '-map', '[v]', '-r', '30', '-pix_fmt', 'yuv420p',
                   '-c:v', 'libx264', '-crf', '20', str(out)]
            r = subprocess.run(cmd, capture_output=True, text=True)
            made[act] = {'mp4': out.name if r.returncode == 0 else None, 'ffmpeg_error': r.stderr[-400:]}
        else:
            made[act] = {'mp4': None, 'ffmpeg_error': 'ffmpeg not found'}
    bpy.context.scene.render.engine = 'CYCLES'
    return made


# ------------------------------------------------------------------- ROM
def rom_sheet(info, cam):
    tiles = []
    for f, lab in info['RigTest_ROM']['poses']:
        set_action('RigTest_ROM', f)
        aim_camera(cam, (-16.0, -26.0, 8.0), (0.0, -1.0, 5.6), lens=42)
        p = render_to(WORK / f'rom_{f:03d}.png', (340, 420), samples=12)
        t = load_rgb(p)
        draw_text(t, 6, 6, f'F{f} {lab}', scale=2)
        tiles.append(t)
    sheet = tile(tiles, 4)
    save_rgb(sheet, PREV / 'RigTest_ROM.png')


# ------------------------------------------------------------ turnaround
def turnaround(cam):
    set_action('ReferencePose', 1)
    tiles = []
    for lab, loc in (('FRONT', (0, -40, 6.5)), ('THREE-QUARTER', (-28, -28, 8)), ('SIDE', (-40, 0, 6.5)),
                     ('BACK', (0, 40, 6.5))):
        aim_camera(cam, loc, (-0.6, -1.0, 6.4), ortho=16.6)
        p = render_to(PREV / f'Turnaround_{lab.title().replace("-", "")}.png', (620, 760), samples=32)
        t = load_rgb(p)
        draw_text(t, 10, 10, lab, scale=3)
        tiles.append(t)
    save_rgb(tile(tiles, 4), PREV / 'Turnaround.png')


def face_closeup(cam):
    set_action('ReferencePose', 1)
    Hc = D.Hd(0.0, -1.0, -0.2)
    fwd = D.RH @ np.array([0, -1.0, 0])
    aim_camera(cam, Hc + fwd * 7.5 + np.array([0.0, 0.0, 0.4]), Hc, lens=70)
    render_to(PREV / 'Face_Closeup.png', (900, 900), samples=48)


# ------------------------------------------------------------- bone overlay
def bone_overlay(cam):
    """Workbench render of the model with the deform skeleton drawn over it
    (octahedral bone meshes built from the evaluated pose)."""
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
        w = min(0.18, 0.1 * L + 0.03)
        base = len(V)
        V += [h, h + y * L * 0.2 + x * w, h + y * L * 0.2 + z * w, h + y * L * 0.2 - x * w, h + y * L * 0.2 - z * w, h + y * L]
        for a, c in ((1, 2), (2, 3), (3, 4), (4, 1)):
            F.append((base, base + a, base + c))
            F.append((base + 5, base + c, base + a))
    me = bpy.data.meshes.new('BoneViz')
    me.from_pydata([tuple(v) for v in V], [], F)
    ob = bpy.data.objects.new('BoneViz', me)
    bpy.data.collections['REVIEW_ONLY'].objects.link(ob)
    sc = bpy.context.scene
    aim_camera(cam, (0, -40, 6.5), (-0.6, -1.0, 6.4), ortho=16.6)
    # pass 1: model, textured, flat light
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'TEXTURE'
    ob.hide_render = True
    p1 = render_to(WORK / 'bones_model.png', (760, 940), engine='BLENDER_WORKBENCH')
    # pass 2: bones only
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
    for o in hidden:
        o.hide_render = False
    ob.hide_render = True
    a = load_rgb(p1)
    img = bpy.data.images.load(str(WORK / 'bones_only.png'))
    bo = B.image_pixels(img)[::-1].copy()
    bpy.data.images.remove(img)
    al = bo[:, :, 3:4]
    comp = a * 0.55 * (1 - al) + bo[:, :, :3] * al + a * 0.45 * (1 - al) * 0.0
    comp = a * (1 - al * 0.95) * 0.75 + bo[:, :, :3] * al * 0.95
    draw_text(comp, 10, 10, 'DEFORM SKELETON OVER MODEL (REFERENCEPOSE)', scale=2)
    save_rgb(comp, PREV / 'Rig_Bones.png')
    sc.display.shading.color_type = 'TEXTURE'


# ---------------------------------------------------------------- checks
def motion_checks(info):
    """Per-frame checks on the Blender-EVALUATED rig (what is exported).

    GroundSlam: arm reach %, elbow flex, wrist bend, elbow out of the swing plane,
    club-body clearance, club lowest z, grip rigidity (digits vs club).
    Stomp: knee flex both legs, knee twist, standing-foot drift, thigh-gut
    clearance, loincloth vertices vs the thigh, club lowest z.
    The limits asserted are written next to the numbers."""
    import fc_motion as MO
    rig = rig_obj()
    sk = PO.Skeleton()
    prims = D.body_prims(rest=False)
    digits = [b for b in sk.order if b.startswith('Right') and any(n in b for n in D.FINGER_NAMES + ['Thumb'])]
    gear = bpy.data.objects[NAME + '_Gear']
    loin_idx = None
    if 'fc_loin' in gear.data.attributes:
        v = np.zeros(len(gear.data.vertices), np.int32)
        gear.data.attributes['fc_loin'].data.foreach_get('value', v)
        loin_idx = np.nonzero(v == 1)[0]
    res = {}
    fails = []
    gs = info['GroundSlam']
    n_out = np.array(gs['swing_plane_normal'])
    s0, s1 = gs['strike_window']
    mid = gs['labels']['mid-swing']
    rows = []
    for f in range(gs['frames'][0], gs['frames'][1] + 1):
        set_action('GroundSlam', f)
        mats = posed_bone_mats(rig)
        P = PO.Pose(sk)
        P.m = {b: mats[b] for b in sk.order}
        m = MO.arm_metrics(P, sk, n_out)
        c, z = MO.club_clearance(P, prims)
        drift = 0.0
        for b in digits:
            rel = np.linalg.inv(mats['Club']) @ mats[b]
            rel0 = np.linalg.inv(sk.ref['Club']) @ sk.ref[b]
            drift = max(drift, float(np.linalg.norm(rel[:3, 3] - rel0[:3, 3])))
        behind, below = MO.arm_behind_coronal(P)
        row = {'frame': f, 'upper_arm_behind_coronal_deg': round(behind, 2), 'hand_below_shoulder': below}
        row.update({k: float(v) for k, v in m.items()})
        row.update({'club_body_clearance': round(c, 3), 'club_lowest_z': round(z, 3),
                    'grip_digit_drift': round(drift, 6)})
        rows.append(row)
        if s0 <= f <= s1:
            if row['wrist_bend'] > 20.5:
                fails.append('GroundSlam f%d: wrist bend %.1f' % (f, row['wrist_bend']))
            if row['elbow_out_of_plane'] > 0.05:
                fails.append('GroundSlam f%d: elbow leaves the swing plane %.3f' % (f, row['elbow_out_of_plane']))
        if mid <= f <= s1:
            if row['elbow_flex'] > 15.0:
                fails.append('GroundSlam f%d: elbow flex %.1f' % (f, row['elbow_flex']))
            if row['reach_pct'] < 95.0:
                fails.append('GroundSlam f%d: reach %.1f' % (f, row['reach_pct']))
        if below and behind > 20.0:
            fails.append('GroundSlam f%d: upper arm %.1f deg behind the coronal plane with the hand low' % (f, behind))
        if c < -0.02:
            fails.append('GroundSlam f%d: club-body clearance %.3f' % (f, c))
        if z < -0.03:
            fails.append('GroundSlam f%d: club below ground %.3f' % (f, z))
        if drift > 1e-3:
            fails.append('GroundSlam f%d: grip drift %.5f' % (f, drift))
    win = [r for r in rows if s0 <= r['frame'] <= s1]
    mwin = [r for r in rows if mid <= r['frame'] <= s1]
    res['GroundSlam'] = {
        'limits': {'strike_window_frames': [s0, s1], 'mid_swing_frame': mid,
                   'wrist_bend_max_deg_in_strike': 20, 'elbow_out_of_plane_max_in_strike': 0.05,
                   'elbow_flex_max_deg_mid_to_impact': 15, 'reach_min_pct_mid_to_impact': 95,
                   'club_body_clearance_min': -0.02, 'club_lowest_z_min': -0.03,
                   'upper_arm_behind_coronal_max_deg_while_hand_below_shoulder': 20},
        'summary': {
            'max_upper_arm_behind_coronal_deg_hand_below_shoulder':
                max([r['upper_arm_behind_coronal_deg'] for r in rows if r['hand_below_shoulder']] or [0.0]),
            'strike_max_wrist_bend': max(r['wrist_bend'] for r in win),
            'strike_max_elbow_out_of_plane': max(r['elbow_out_of_plane'] for r in win),
            'mid_to_impact_max_elbow_flex': max(r['elbow_flex'] for r in mwin),
            'mid_to_impact_min_reach_pct': min(r['reach_pct'] for r in mwin),
            'min_club_body_clearance': min(r['club_body_clearance'] for r in rows),
            'min_club_lowest_z': min(r['club_lowest_z'] for r in rows),
            'club_lowest_z_at_impact': [r['club_lowest_z'] for r in rows if r['frame'] == gs['impact_frame']][0],
            'max_grip_digit_drift': max(r['grip_digit_drift'] for r in rows)},
        'frames': rows}
    st = info['Stomp']
    rows = []
    RF0 = sk.ref['RightFoot'][:3, 3]
    dg = bpy.context.evaluated_depsgraph_get()
    for f in range(st['frames'][0], st['frames'][1] + 1):
        set_action('Stomp', f)
        mats = posed_bone_mats(rig)
        P = PO.Pose(sk)
        P.m = {b: mats[b] for b in sk.order}
        row = {'frame': f}
        for side in ('Left', 'Right'):
            H, K, A = P.head(side + 'UpperLeg'), P.head(side + 'LowerLeg'), P.head(side + 'Foot')
            t, sh = D._unit(K - H), D._unit(A - K)
            row['knee_flex_' + side] = round(math.degrees(math.acos(np.clip(t @ sh, -1, 1))), 2)
            row['knee_twist_' + side] = round(MO.knee_twist(P, sk, side), 2)
        row['standing_foot_drift'] = round(float(np.linalg.norm(P.head('RightFoot') - RF0)), 6)
        Kl, Al = P.head('LeftLowerLeg'), P.head('LeftFoot')
        row['foot_ahead_of_knee'] = round(float((Al - Kl) @ np.array([0, -1.0, 0])), 3)
        row['thigh_elevation_deg'] = round(math.degrees(math.asin(np.clip(
            D._unit(Kl - P.head('LeftUpperLeg'))[2], -1, 1))), 2)
        row['stomp_foot_from_lift_spot'] = round(float(np.linalg.norm((Al - sk.ref['LeftFoot'][:3, 3])[:2])), 3)
        row['thigh_gut_clearance'] = round(MO.thigh_clearance(P, prims), 3)
        c, z = MO.club_clearance(P, prims)
        row['club_lowest_z'] = round(z, 3)
        if loin_idx is not None and len(loin_idx):
            ev = gear.evaluated_get(dg)
            me = ev.to_mesh()
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get('co', co)
            ev.to_mesh_clear()
            V = co.reshape(-1, 3)[loin_idx]
            H, K = P.head('LeftUpperLeg'), P.head('LeftLowerLeg')
            ab = K - H
            tt = np.clip(((V - H) @ ab) / (ab @ ab), 0, 1)
            dist = np.linalg.norm(V - (H + tt[:, None] * ab), axis=1)
            rad = np.where(tt < 0.4, 1.30, 1.30 + (1.02 - 1.30) * (tt - 0.4) / 0.6)
            sel = tt > 0.3
            row['loincloth_thigh_clearance'] = round(float((dist - rad)[sel].min()) if sel.any() else 9.0, 3)
        rows.append(row)
        if row['standing_foot_drift'] > 1e-3:
            fails.append('Stomp f%d: standing foot drift %.5f' % (f, row['standing_foot_drift']))
        if row['knee_twist_Left'] > 1.0:
            fails.append('Stomp f%d: knee twist %.2f' % (f, row['knee_twist_Left']))
        if row['thigh_gut_clearance'] < -0.05:
            fails.append('Stomp f%d: thigh into gut %.3f' % (f, row['thigh_gut_clearance']))
        if row['club_lowest_z'] < -0.03:
            fails.append('Stomp f%d: club below ground %.3f' % (f, row['club_lowest_z']))
        if row['foot_ahead_of_knee'] > 0.15:
            fails.append('Stomp f%d: foot swings ahead of the knee %.3f' % (f, row['foot_ahead_of_knee']))
        if row.get('loincloth_thigh_clearance', 9.0) < 0.0:
            fails.append('Stomp f%d: thigh passes through the loincloth %.3f' % (f, row['loincloth_thigh_clearance']))
    top = st['labels']['top of raise']
    res['Stomp'] = {
        'limits': {'standing_foot_drift_max': 0.001, 'knee_twist_max_deg': 1.0, 'thigh_gut_clearance_min': -0.05,
                   'club_lowest_z_min': -0.03, 'foot_ahead_of_knee_max': 0.15,
                   'loincloth_thigh_clearance_min': 0.0},
        'summary': {
            'max_thigh_elevation_deg': max(r['thigh_elevation_deg'] for r in rows),
            'max_foot_ahead_of_knee': max(r['foot_ahead_of_knee'] for r in rows),
            'foot_from_lift_spot_at_impact': [r['stomp_foot_from_lift_spot'] for r in rows
                                              if r['frame'] == st['impact_frame']][0],
            'max_knee_flex_Left': max(r['knee_flex_Left'] for r in rows),
            'knee_flex_Left_at_top': [r['knee_flex_Left'] for r in rows if r['frame'] == top][0],
            'knee_flex_Left_at_impact': [r['knee_flex_Left'] for r in rows if r['frame'] == st['impact_frame']][0],
            'max_knee_twist_Left': max(r['knee_twist_Left'] for r in rows),
            'max_standing_foot_drift': max(r['standing_foot_drift'] for r in rows),
            'min_thigh_gut_clearance': min(r['thigh_gut_clearance'] for r in rows),
            'min_loincloth_thigh_clearance': min(r.get('loincloth_thigh_clearance', 9.0) for r in rows),
            'min_club_lowest_z': min(r['club_lowest_z'] for r in rows)},
        'frames': rows}
    res['passed'] = not fails
    res['failures'] = fails
    return res


# ---------------------------------------------------------------- exports
def select_export(with_meshes=True):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    rig = rig_obj()
    rig.select_set(True)
    if with_meshes:
        for o in meshes():
            o.select_set(True)
    bpy.context.view_layer.objects.active = rig


def export_all():
    rig = rig_obj()
    (HERE / 'exports' / 'fbx').mkdir(parents=True, exist_ok=True)
    (HERE / 'exports' / 'glb').mkdir(parents=True, exist_ok=True)
    common = dict(use_selection=True, add_leaf_bones=False, use_armature_deform_only=True, axis_forward='-Z',
                  axis_up='Y', apply_unit_scale=True, global_scale=1.0, mesh_smooth_type='OFF',
                  use_mesh_modifiers=False, primary_bone_axis='Y', secondary_bone_axis='X')
    # rest mesh + armature + embedded textures
    rig.animation_data.action = None
    rig.data.pose_position = 'REST'
    for pb in rig.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.scale = (1, 1, 1)
    select_export(True)
    bpy.ops.export_scene.fbx(filepath=str(HERE / 'exports/fbx' / f'{NAME}.fbx'), object_types={'ARMATURE', 'MESH'},
                             bake_anim=False, path_mode='COPY', embed_textures=True, **common)
    rig.data.pose_position = 'POSE'
    # armature-only clips
    sc = bpy.context.scene
    for act in ('ReferencePose', 'RigTest_ROM', 'GroundSlam', 'Stomp'):
        a = bpy.data.actions[act]
        rig.animation_data.action = a
        sc.frame_start, sc.frame_end = int(a.frame_range[0]), int(a.frame_range[1])
        select_export(False)
        bpy.ops.export_scene.fbx(filepath=str(HERE / 'exports/fbx' / f'{NAME}_{act}.fbx'), object_types={'ARMATURE'},
                                 bake_anim=True, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
                                 bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0,
                                 bake_anim_step=1.0, **common)
    # GLB: meshes, armature and every action
    rig.animation_data.action = bpy.data.actions['ReferencePose']
    sc.frame_start, sc.frame_end = 1, 2
    select_export(True)
    kw = dict(filepath=str(HERE / 'exports/glb' / f'{NAME}.glb'), export_format='GLB', use_selection=True,
              export_yup=True, export_apply=False, export_skins=True, export_def_bones=True,
              export_animations=True, export_animation_mode='ACTIONS', export_image_format='AUTO',
              export_materials='EXPORT', export_force_sampling=True)
    try:
        bpy.ops.export_scene.gltf(**kw)
    except TypeError:
        kw.pop('export_animation_mode')
        bpy.ops.export_scene.gltf(**kw)
    log('exports written')


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()
