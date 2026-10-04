"""Hammer boss moves: the generator.

  blender -b --factory-startup --python build_moves.py               all: clips, checks, exports, actions, previews
  blender -b --factory-startup --python build_moves.py -- extract    dump the rest rig + meshes to .cache/
  blender -b --factory-startup --python build_moves.py -- data       clips, checks, exports, actions (no renders)
  python build_moves.py post                                          labels, contact sheet, mp4s (run by 'all')

(blender = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")

Works on the COPY ./HammerBoss.blend (never the original in hammer-boss/finished). The motion maths
is pure numpy in hm_motion.py / hm_clips.py / hm_checks.py; this file reads the model, supplies the
exact mesh-against-mesh BVH test (mathutils.bvhtree), writes the hand-off files, keys Blender actions
(HB_Idle, HB_Walk, HB_Slam) into the copy, and renders the Eevee previews (ffmpeg H.264).
"""
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
CACHE = HERE / '.cache'
BLEND = HERE / 'HammerBoss.blend'
GAME = HERE / 'exports' / 'game'
PREVIEWS = HERE / 'previews'
FRAMES = CACHE / 'frames'
MANIFEST = HERE.parent / 'hammer-boss' / 'finished' / 'studio-asset-manifest.json'
PARTS = ['LowerTorso', 'UpperTorso', 'Head', 'RightUpperArm', 'RightLowerArm', 'RightHand', 'LeftUpperArm',
         'LeftLowerArm', 'LeftHand', 'RightUpperLeg', 'RightLowerLeg', 'RightFoot', 'LeftUpperLeg', 'LeftLowerLeg',
         'LeftFoot', 'Hammer']
PREVIEW_HZ = 60

try:
    import bpy
    from mathutils import Matrix
    from mathutils.bvhtree import BVHTree
except ImportError:            # the 'post' stage runs under system Python
    bpy = None


def stage_arg():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    return a[0] if a else 'all'


def log(*a):
    print('[moves]', *a, flush=True)


# ================================================================== extract (Blender)
def extract():
    """Rest rig and meshes, exactly as stored in the .blend (rest position, world space)."""
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    rig = bpy.data.objects['HammerBoss_Rig']
    rig.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    bones = {b.name: {'head': list(b.head_local), 'tail': list(b.tail_local),
                      'parent': b.parent.name if b.parent else None} for b in rig.data.bones}
    parts, arrays = {}, {}
    for name in PARTS:
        ob = bpy.data.objects[name]
        me = ob.data
        mw = np.array(ob.matrix_world)
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        v = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
        me.calc_loop_triangles()
        tri = np.empty(len(me.loop_triangles) * 3, dtype=np.int32)
        me.loop_triangles.foreach_get('vertices', tri)
        arrays[name + '_v'] = v
        arrays[name + '_t'] = tri.reshape(-1, 3)
        lo, hi = v.min(0), v.max(0)
        parts[name] = {'center': list((lo + hi) / 2), 'min': list(lo), 'max': list(hi), 'verts': len(v),
                       'tris': int(len(tri) // 3)}
    rig.data.pose_position = 'POSE'
    CACHE.mkdir(exist_ok=True)
    (CACHE / 'rig.json').write_text(json.dumps({'bones': bones, 'parts': parts}, indent=1))
    np.savez_compressed(CACHE / 'meshes.npz', **arrays)
    log('extract ok', len(bones), 'bones', len(parts), 'parts')


def load():
    import hm_motion as HM
    import hm_clips as CL
    data = json.loads((CACHE / 'rig.json').read_text())
    meshes = dict(np.load(CACHE / 'meshes.npz'))
    rig = HM.Rig(data)
    for s in HM.SIDES:
        CL.cuff_points(rig, s, meshes)
    return rig, meshes


# ================================================================== clips
def build_clips(rig):
    import hm_clips as CL
    t0 = time.time()
    clips = {'Idle': CL.idle(rig), 'Walk': CL.walk(rig), 'Slam': CL.slam(rig)}
    log('clips built in %.1fs' % (time.time() - t0), {k: (len(c.frames), c.fps) for k, c in clips.items()})
    return clips


# ================================================================== exact mesh overlap (Blender BVH)
def bvh_overlap(rig, meshes):
    """overlap(P) -> {part: overlapping triangle pairs} for the hammer against every body section
    except the two fists, using each section's BVH in its own rest frame and the hammer moved into it."""
    import hm_motion as HM
    trees = {}
    for p in PARTS:
        if p in ('Hammer', 'RightHand', 'LeftHand'):
            continue
        V, T = meshes[p + '_v'], meshes[p + '_t']
        trees[p] = BVHTree.FromPolygons([tuple(v) for v in V], [tuple(t) for t in T], all_triangles=True)
    HV, HT = meshes['Hammer_v'], [tuple(t) for t in meshes['Hammer_t']]
    lo = HV.min(0) - 0.6
    hi = HV.max(0) + 0.6

    def overlap(P):
        out = {}
        for p, tree in trees.items():
            Q = HM.rinv(P[p]) @ P['Hammer']
            hv = HV @ Q[:3, :3].T + Q[:3, 3]
            pv = meshes[p + '_v']
            # quick reject: bounding boxes
            if (hv.min(0) > meshes[p + '_v'].max(0)).any() or (hv.max(0) < pv.min(0)).any():
                continue
            ht = BVHTree.FromPolygons([tuple(v) for v in hv], HT, all_triangles=True)
            n = len(tree.overlap(ht))
            if n:
                out[p] = n
        return out
    return overlap


# ================================================================== exports
def studio12(rig, P, part):
    import hm_motion as HM
    return [round(float(x), 7) for x in HM.studio_pose(rig, P, part)]


def partposes(rig, clips):
    out = {'fps': 24, 'rootHeight': 4.45, 'parts': PARTS,
           'coordinateSpace': 'each part CFrame relative to HumanoidRootPart, Studio axes, template scale 1.0, '
                              '[x,y,z,R00,R01,R02,R10,R11,R12,R20,R21,R22] (CFrame:GetComponents order)',
           'clips': {}}
    for name, c in clips.items():
        frames = [{'time': round(k / c.fps, 6), 'poses': {p: studio12(rig, P, p) for p in PARTS}}
                  for k, P in enumerate(c.frames)]
        out['clips'][name] = {'duration': round(c.duration, 6), 'loop': c.loop, 'fps': c.fps, 'frames': frames}
    w = clips['Walk'].meta
    out['motion'] = {'strideLength': round(w['strideLength'], 4), 'nominalSpeed': round(w['nominalSpeed'], 4),
                     'walkCycle': round(w['cycle'], 4),
                     'note': 'Walk authored at template scale 1.0 for the in-game chase speed 20 at scale 1.15: '
                             'playback rate = (ground speed / model scale) / nominalSpeed'}
    return out


def axis_proof(rig, idle0):
    """Idle frame 0 (as exported) against the template's own part CFrames relative to its root."""
    man = json.loads(MANIFEST.read_text())
    cf = {e['properties']['Name']['v']: e['properties']['CFrame']['v'] for e in man if e['class'] in ('Part', 'MeshPart')}
    root = np.array(cf['HumanoidRootPart'], float)
    worst_p, worst_r, rows = 0.0, 0.0, {}
    for p in PARTS:
        m = np.array(cf[p], float)
        rel = m[:3] - root[:3]                       # both rotations are identity in the template
        got = np.array(idle0[p], float)
        dp = float(np.abs(got[:3] - rel).max())
        dr = float(np.abs(got[3:] - np.array(m[3:])).max())
        worst_p, worst_r = max(worst_p, dp), max(worst_r, dr)
        rows[p] = round(dp, 7)
    return {'maxPositionError': worst_p, 'maxRotationError': worst_r, 'limit': 0.001,
            'pass': bool(worst_p <= 0.001 and worst_r <= 0.001), 'perPart': rows,
            'source': 'hammer-boss/finished/studio-asset-manifest.json (template HammerBoss_NPC as installed)'}


def gamedata(rig, clips, meshes):
    import hm_motion as HM
    s = clips['Slam']
    imp = s.meta['impact']
    P = s.frames[imp]
    lo, hi = rig.head_box
    face_local = np.array([0.0, (lo[1] + hi[1]) / 2, lo[2]])          # centre of the lower striking face
    grip_x = (2.72 + 8.05) / 2
    pts = {'HammerFace': rig.HO + rig.HR @ face_local, 'HammerGrip': rig.HO + rig.HA * grip_x}
    c = rig.center['Hammer']
    points = {}
    for n, p in pts.items():
        off = HM.C_STUDIO @ (p - c)                                    # Hammer part space (rest: identity rotation)
        w = HM.xf(P['Hammer'], p)                                      # Blender ground frame (z up from the soles)
        points[n] = {'bone': 'Hammer', 'part': 'Hammer', 'offset': [round(float(v), 5) for v in off],
                     'rootAtImpact': [round(float(v), 5) for v in w],
                     'rootAtImpactStudio': [round(float(v), 5) for v in HM.C_STUDIO @ w]}
    body = np.concatenate([meshes[p + '_v'] for p in PARTS if p != 'Hammer'])
    height = float(max(meshes[p + '_v'][:, 2].max() for p in PARTS))
    foot = float(np.sqrt((body[:, :2] ** 2).sum(1)).max())
    w, n = __import__('hm_checks').strike_face(rig, P)
    normal = n / np.linalg.norm(n)
    return {
        'attacks': {'Slam': {
            'clip': 'Slam', 'fps': s.fps, 'duration': round(s.duration, 6),
            'warnStart': round(s.meta['warnStart'], 4), 'impact': round(imp / s.fps, 6),
            'activeEnd': round(imp / s.fps, 6), 'recoveryEnd': round(s.meta['recoveryEnd'], 4),
            'points': points,
            'strikeFaceNormalAtImpact': [round(float(v), 5) for v in normal],
            'strikeFaceNormalAtImpactStudio': [round(float(v), 5) for v in HM.C_STUDIO @ normal]}},
        'rootHeight': 4.45, 'bodyCentreHeight': 4.45, 'height': round(height, 4),
        'footprintRadius': round(foot, 4), 'groundOffset': 0.0,
        'motion': partposes_motion(clips),
        'notes': 'Template scale 1.0 (the map-boss def scales the model 1.15). Times in seconds from clip start; '
                 'Slam is a 30 fps clip (impact on frame 21 = 0.700 s). Point offsets are in the Hammer PART\'s own '
                 'Studio space (bone "Hammer" in the part-pose AnimationData). rootAtImpact: Blender axes, origin on '
                 'the ground under the HumanoidRootPart (z up from the soles); rootAtImpactStudio: the same point in '
                 'Studio axes (-X, Z, Y), y up from the soles. HammerGrip is on the haft axis midway between the '
                 'carry grips (2.72 / 8.05 along the haft). footprintRadius: body sections only (the hammer is not '
                 'part of the body shell). groundOffset 0: the soles rest on z = 0.'}


def partposes_motion(clips):
    w = clips['Walk'].meta
    return {'strideLength': round(w['strideLength'], 4), 'nominalSpeed': round(w['nominalSpeed'], 4)}


# ================================================================== checks
def run_checks(rig, meshes, clips, overlap):
    import hm_motion as HM
    import hm_checks as HC
    L = HC.LIMITS
    t0 = time.time()
    idle0 = clips['Idle'].frames[0]
    rest_cuff = HC.hammer_solid_depth(rig, idle0, meshes)
    report = {'limits': L, 'definitions': HC.__doc__.split('Definitions')[1].strip(), 'clips': {}, 'between': {}}
    summary = []

    def add(check, clip, value, limit, ok, where=None):
        summary.append({'check': check, 'clip': clip, 'value': round(float(value), 4) if value is not None else None,
                        'limit': limit, 'pass': bool(ok), **({'at': where} if where is not None else {})})

    def contact_rule(per_part_pairs, depth):
        """Hammer vs body: no overlap except the template's own right-forearm cuff contact (it is in
        the rest pose itself, Idle frame 0), allowed up to that depth + 0.05."""
        bad = {}
        for p, n in per_part_pairs.items():
            allowed = rest_cuff.get(p, 0.0) > 0 and depth.get(p, 0.0) <= rest_cuff[p] + 0.05
            if not allowed:
                bad[p] = n
        return bad

    for name, c in clips.items():
        res = HC.check_clip(rig, name, c.frames, c.fps, c.loop, meshes, overlap=None,
                            planted=c.meta.get('planted'), impact=c.meta.get('impact'),
                            root_motion=c.meta.get('root_motion'), idle0=idle0 if name == 'Slam' else None)
        # exact overlap per frame
        bad_frames, cuff = [], 0.0
        for k, P in enumerate(c.frames):
            pairs = overlap(P)
            depth = HC.hammer_solid_depth(rig, P, meshes)
            cuff = max(cuff, depth.get('RightLowerArm', 0.0))
            bad = contact_rule(pairs, depth)
            if bad:
                bad_frames.append({'frame': k, 'pairs': bad})
        res['hammerOverlap'] = {'badFrames': bad_frames[:20], 'badFrameCount': len(bad_frames),
                                'rightCuffDepth': cuff, 'rightCuffDepthAtRest': rest_cuff.get('RightLowerArm', 0.0)}
        report['clips'][name] = res
        w, wh = res['worst'], res['where']
        add('elbow flex min (deg)', name, w['elbowMin'], L['elbowFlex'][0], w['elbowMin'] >= L['elbowFlex'][0], wh.get('elbowMin'))
        add('elbow flex max (deg)', name, w['elbowMax'], L['elbowFlex'][1], w['elbowMax'] <= L['elbowFlex'][1], wh.get('elbowMax'))
        add('elbow off-axis (deg)', name, w['hingeOffAxis'], L['hingeOffAxis'], w['hingeOffAxis'] <= L['hingeOffAxis'])
        add('knee off-axis (deg)', name, w['kneeOffAxis'], L['hingeOffAxis'], w['kneeOffAxis'] <= L['hingeOffAxis'])
        add('knee bends forward only: min hinge (deg)', name, w['kneeMin'], 0.0, w['kneeMin'] >= -0.01)
        add('knee max (deg)', name, w['kneeMax'], 150.0, w['kneeMax'] <= 150.0)
        add('wrist bend (deg)', name, w['wristBend'], L['wristBend'], w['wristBend'] <= L['wristBend'], wh.get('wristBend'))
        add('wrist twist (deg)', name, w['wristTwist'], L['wristTwist'], w['wristTwist'] <= L['wristTwist'], wh.get('wristTwist'))
        add('shoulder swivel (deg)', name, w['swivel'], L['swivel'], w['swivel'] <= L['swivel'], wh.get('swivel'))
        add('swivel step per frame (deg)', name, w['swivelStep'], L['spikeStep'], w['swivelStep'] <= L['spikeStep'], wh.get('swivelStep'))
        add('spine step per frame (deg)', name, w['spineStep'], L['spikeStep'], w['spineStep'] <= L['spikeStep'], wh.get('spineStep'))
        add('grip: haft through both fist holes (studs)', name, w['grip'], L['grip'], w['grip'] <= L['grip'])
        add('grip slide stays on the haft', name, None, L['slide'], L['slide'][0] <= w['slideMin'] and w['slideMax'] <= L['slide'][1])
        add('joint gap (studs)', name, w['jointGap'], 1e-4, w['jointGap'] <= 1e-4)
        add('hammer vs body: BVH overlap frames', name, len(bad_frames), 0, not bad_frames)
        add('shaft outside torso core (min)', name, w['shaftCore'], L['shaftCore'], w['shaftCore'] >= L['shaftCore'])
        add('planted foot drift per frame (studs)', name, w['footDrift'], L['footDrift'], w['footDrift'] <= L['footDrift'], wh.get('footDrift'))
        add('lowest point above ground (studs)', name, w['ground'], L['ground'], w['ground'] >= L['ground'], wh.get('ground'))
        if c.loop:
            add('loop closes (max |last - first|)', name, res['loopClose'], L['loop'], res['loopClose'] <= L['loop'])
        if name == 'Slam':
            add('starts on Idle frame 0', name, res['startVsIdle0'], L['loop'], res['startVsIdle0'] <= L['loop'])
            add('ends on Idle frame 0', name, res['endVsIdle0'], L['loop'], res['endVsIdle0'] <= L['loop'])
            fz = res['impactFaceZ']
            add('impact: striking face flat on z = 0 (max |z| of its corners)', name, max(abs(z) for z in fz), L['impactFace'],
                max(abs(z) for z in fz) <= L['impactFace'])
        log('checked', name, '%.1fs' % (time.time() - t0))

    # ---- the client's in-between frames (120 Hz) and blends
    comp = {n: HC.as_clip(rig, c.frames, c.fps, c.loop) for n, c in clips.items()}
    sets = {n: HC.resample(rig, comp[n], 120) for n in clips}
    idle_phases = [i * 0.25 for i in range(12)]
    sets['Idle->Slam (0.12 s)'] = HC.blends(rig, comp['Idle'], comp['Slam'], idle_phases)
    sets['Slam->Idle (0.12 s, Slam held)'] = HC.blends(rig, comp['Slam'], comp['Idle'], [comp['Slam']['duration']],
                                                       hold_src=True)
    sets['Slam->Idle (0.12 s, Slam playing)'] = HC.blends(rig, comp['Slam'], comp['Idle'],
                                                          [comp['Slam']['duration'] - 0.12])
    info = {}
    walk_phases = [i * comp['Walk']['duration'] / 8 for i in range(8)]
    info['Walk->Slam (0.12 s, information)'] = HC.blends(rig, comp['Walk'], comp['Slam'], walk_phases)
    for label, poses in list(sets.items()) + list(info.items()):
        b = HC.check_between(rig, poses, meshes, overlap=None, every=1)
        bad = []
        for lab, P in poses:
            pairs = overlap(P)
            if pairs:
                depth = HC.hammer_solid_depth(rig, P, meshes)
                bb = contact_rule(pairs, depth)
                if bb:
                    bad.append({'at': lab, 'pairs': bb})
        b['hammerOverlapBad'] = bad[:20]
        b['hammerOverlapBadCount'] = len(bad)
        report['between'][label] = b
        w = b['worst']
        if label in info:
            continue
        add('in-between grip (studs)', label, w['grip'], L['gripBetween'], w['grip'] <= L['gripBetween'], b['where'].get('grip'))
        add('in-between hammer vs body: BVH overlap samples', label, len(bad), 0, not bad)
        add('in-between elbow off-axis (deg)', label, w['hingeOffAxis'], L['hingeOffAxis'], w['hingeOffAxis'] <= L['hingeOffAxis'])
        add('in-between knee off-axis (deg)', label, w['kneeOffAxis'], L['hingeOffAxis'], w['kneeOffAxis'] <= L['hingeOffAxis'])
        add('in-between elbow flex range (deg)', label, w['elbowMin'], L['elbowFlex'],
            L['elbowFlex'][0] <= w['elbowMin'] and w['elbowMax'] <= L['elbowFlex'][1])
        add('in-between wrist bend (deg)', label, w['wristBend'], L['wristBend'], w['wristBend'] <= L['wristBend'])
        log('in-between', label, 'samples', len(poses), 'grip %.4f' % w['grip'], 'bad overlaps', len(bad))
    report['summary'] = summary
    report['allPass'] = all(r['pass'] for r in summary)
    report['seconds'] = round(time.time() - t0, 1)
    return report


# ================================================================== Blender: actions
def bone_basis(rig_ob, P):
    """pose_bone.matrix_basis per bone from part deformations D (armature = world, rig at identity)."""
    import hm_motion as HM
    out = {}
    for b in rig_ob.data.bones:
        rest = np.array(b.matrix_local)
        D = P.get(b.name, np.eye(4)) if b.name != 'HumanoidRootPart' else np.eye(4)
        Dp = np.eye(4) if b.parent is None else (P.get(b.parent.name, np.eye(4)) if b.parent.name != 'HumanoidRootPart' else np.eye(4))
        out[b.name] = np.linalg.inv(rest) @ HM.rinv(Dp) @ D @ rest
    return out


def key_actions(rig_ob, clips):
    rig_ob.animation_data_create()
    for name, c in clips.items():
        act_name = 'HB_' + name
        if act_name in bpy.data.actions:
            bpy.data.actions.remove(bpy.data.actions[act_name])
        rig_ob.animation_data.action = None
        prev = {}
        for k, P in enumerate(c.frames):
            basis = bone_basis(rig_ob, P)
            for bn, M in basis.items():
                pb = rig_ob.pose.bones[bn]
                pb.rotation_mode = 'QUATERNION'
                m = Matrix(M.tolist())
                loc, q, sc = m.decompose()
                if bn in prev and q.dot(prev[bn]) < 0:
                    q.negate()
                prev[bn] = q.copy()
                pb.location = loc
                pb.rotation_quaternion = q
                pb.scale = (1, 1, 1)
                for prop in ('location', 'rotation_quaternion'):
                    pb.keyframe_insert(prop, frame=k + 1, group=bn)
        act = rig_ob.animation_data.action
        act.name = act_name
        act.use_fake_user = True
        act['fps'] = c.fps
        act['frames'] = len(c.frames)
        act['source'] = 'hammer-boss-moves/build_moves.py'
        log('keyed', act_name, len(c.frames), 'frames')
    rig_ob.animation_data.action = None


# ================================================================== Blender: previews
def apply_pose(rig_ob, P):
    basis = bone_basis(rig_ob, P)
    for bn, M in basis.items():
        rig_ob.pose.bones[bn].matrix_basis = Matrix(M.tolist())


def preview_scene():
    sc = bpy.context.scene
    for ob in list(bpy.data.objects):
        if ob.type in ('LIGHT', 'CAMERA') or ob.name == 'RENDER_STAGE_ONLY':
            ob.hide_render = True
            ob.hide_viewport = True
    col = bpy.data.collections.get('MovesPreview') or bpy.data.collections.new('MovesPreview')
    if col.name not in sc.collection.children:
        sc.collection.children.link(col)
    # grass ground with soft variation (motion cues for the run)
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, 0))
    g = bpy.context.active_object
    g.name = 'MovesGround'
    for c in g.users_collection:
        c.objects.unlink(g)
    col.objects.link(g)
    m = bpy.data.materials.new('MovesGrass')
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = 0.95
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 0.35
    noise.inputs['Detail'].default_value = 6.0
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.09, 0.26, 0.035, 1)
    ramp.color_ramp.elements[1].color = (0.20, 0.42, 0.07, 1)
    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    g.data.materials.append(m)
    # soft sky
    w = bpy.data.worlds.new('MovesSky')
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.50, 0.70, 0.95, 1)
    bg.inputs['Strength'].default_value = 0.75
    sc.world = w
    # key (sun) and fill (area)
    key = bpy.data.lights.new('MovesKey', 'SUN')
    key.energy = 3.4
    key.angle = math.radians(10)
    ko = bpy.data.objects.new('MovesKey', key)
    ko.rotation_euler = (math.radians(52), 0, math.radians(-38))
    col.objects.link(ko)
    fill = bpy.data.lights.new('MovesFill', 'AREA')
    fill.energy = 2200
    fill.size = 22
    fill.specular_factor = 0.15
    fo = bpy.data.objects.new('MovesFill', fill)
    fo.location = (16, -18, 22)
    col.objects.link(fo)
    look_at(fo, (0, -2, 5))
    cam = bpy.data.cameras.new('MovesCam')
    cam.lens = 40
    co = bpy.data.objects.new('MovesCam', cam)
    col.objects.link(co)
    sc.camera = co
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    try:
        sc.eevee.taa_render_samples = 24
        sc.eevee.use_shadows = True
    except AttributeError:
        pass
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = -0.15
    return co


def look_at(ob, target):
    from mathutils import Vector
    d = Vector(target) - ob.location
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = d.to_track_quat('-Z', 'Y')


def place_cam(co, target, yaw_deg, dist, height, lens=40):
    from mathutils import Vector
    a = math.radians(yaw_deg)
    # yaw 0 = straight in front of him (he faces -Y); positive = round to his right side (-X)
    co.location = Vector((target[0] - dist * math.sin(a), target[1] - dist * math.cos(a), height))
    co.data.lens = lens
    look_at(co, target)


def render(path):
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def preview_samples(clips):
    """Client-interpolated poses (EnemyMotion.sample, per-joint CFrame lerp) at PREVIEW_HZ, with the
    in-game 0.12 s blends around the Slam: what the game will actually show."""
    import hm_checks as HC
    import hm_motion as HM
    rig, _ = load()
    comp = {n: HC.as_clip(rig, c.frames, c.fps, c.loop) for n, c in clips.items()}
    seqs = {}
    hz = PREVIEW_HZ
    seqs['Idle'] = [HM.from_locals(rig, HC.sample(rig, comp['Idle'], i / hz)) for i in range(int(3.0 * hz))]
    walk_t = 3 * comp['Walk']['duration']
    v = clips['Walk'].meta['nominalSpeed']
    seqs['Walk'] = [(HM.from_locals(rig, HC.sample(rig, comp['Walk'], i / hz)), -v * i / hz) for i in range(int(round(walk_t * hz)))]
    lead, tail = 0.3, 0.6
    sl = []
    for i in range(int(round((lead + comp['Slam']['duration'] + tail) * hz))):
        t = i / hz
        if t < lead:
            L = HC.sample(rig, comp['Idle'], 3.0 - lead + t)
            if t > lead - 0.12:                       # blend Idle -> Slam as the client does
                a = (t - (lead - 0.12)) / 0.12
                L = HC.blend(L, HC.sample(rig, comp['Slam'], 0.0), a)
        elif t < lead + comp['Slam']['duration']:
            L = HC.sample(rig, comp['Slam'], t - lead)
        else:
            u = t - lead - comp['Slam']['duration']
            L = HC.sample(rig, comp['Idle'], u)
            if u < 0.12:
                L = HC.blend(HC.sample(rig, comp['Slam'], comp['Slam']['duration']), L, u / 0.12)
        sl.append(HM.from_locals(rig, L))
    seqs['Slam'] = sl
    seqs['_slam_lead'] = lead
    return rig, seqs


def render_previews(clips):
    rig, seqs = preview_samples(clips)
    rig_ob = bpy.data.objects['HammerBoss_Rig']
    rig_ob.animation_data_clear()
    co = preview_scene()
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    t0 = time.time()
    views = {'Idle': ((-0.6, -1.4, 5.8), 32, 31, 7.8, 40), 'Slam': ((-0.8, -4.4, 9.0), 46, 38, 10.0, 35),
             'Walk': ((0.0, -1.5, 5.6), -50, 31, 7.2, 38)}
    for name in ('Idle', 'Walk', 'Slam'):
        out = FRAMES / name
        out.mkdir(parents=True, exist_ok=True)
        tgt, yaw, dist, hgt, lens = views[name]
        for i, item in enumerate(seqs[name]):
            if name == 'Walk':
                P, dy = item
                rig_ob.location = (0, dy, 0)
                place_cam(co, (tgt[0], tgt[1] + dy, tgt[2]), yaw, dist, hgt, lens)
            else:
                P = item
                rig_ob.location = (0, 0, 0)
                place_cam(co, tgt, yaw, dist, hgt, lens)
            apply_pose(rig_ob, P)
            bpy.context.view_layer.update()
            render(out / ('%04d.png' % i))
        log('rendered', name, len(seqs[name]), 'frames', '%.0fs' % (time.time() - t0))
    rig_ob.location = (0, 0, 0)
    # attack check sheet: wind-up top, mid-drop, impact, recovery; front 3/4 + a fist-on-haft close-up
    import hm_motion as HM
    s = clips['Slam']
    picks = [('wind-up top', 0.45), ('mid-drop', 0.60), ('impact', 0.70), ('recovery', 1.0)]
    out = FRAMES / 'check'
    out.mkdir(parents=True, exist_ok=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 800, 600
    meta = []
    _, meshes = load()
    for j, (label, t) in enumerate(picks):
        k = int(round(t * s.fps))
        P = s.frames[k]
        apply_pose(rig_ob, P)
        bpy.context.view_layer.update()
        # wide: frame the posed body + hammer (front 3/4 from his right)
        pts = np.concatenate([HM.xf(P[p], meshes[p + '_v'][::7]) for p in PARTS])
        lo, hi = pts.min(0), pts.max(0)
        c = (lo + hi) / 2
        ext = float(max(hi[2] - lo[2], np.linalg.norm((hi - lo)[:2]) * 0.8))
        lens = 32
        dist = 1.25 * ext / (2 * math.tan(math.atan(12 / lens))) + 2.0
        place_cam(co, tuple(c), 46, dist, c[2] + 1.5, lens)
        render(out / ('wide_%d.png' % j))
        # close-up of both fists on the haft, from his left-front and above
        grip = (HM.xf(P['Hammer'], rig.HO + rig.HA * s.meta['design']['slide'][0][1]) * 0 +
                HM.xf(P['RightHand'], rig.head['RightHand']) + HM.xf(P['LeftHand'], rig.head['LeftHand'])) / 2
        place_cam(co, tuple(grip), -35, 9.5, grip[2] + 3.5, 42)
        render(out / ('close_%d.png' % j))
        meta.append({'label': label, 'time': round(k / s.fps, 3), 'frame': k})
    (out / 'meta.json').write_text(json.dumps(meta))
    log('attack check renders done', '%.0fs' % (time.time() - t0))


# ================================================================== post (system Python): labels, sheet, mp4
def post():
    from PIL import Image, ImageDraw, ImageFont
    PREVIEWS.mkdir(exist_ok=True)
    try:
        font = ImageFont.truetype('arial.ttf', 26)
        small = ImageFont.truetype('arial.ttf', 20)
    except OSError:
        font = small = ImageFont.load_default()

    def label(img, text, sub=None):
        d = ImageDraw.Draw(img, 'RGBA')
        w = d.textlength(text, font=font) + 28
        d.rounded_rectangle((16, 14, 16 + w, 54 + (26 if sub else 0)), 8, fill=(0, 0, 0, 120))
        d.text((30, 20), text, font=font, fill=(255, 255, 255, 255))
        if sub:
            d.text((30, 50), sub, font=small, fill=(225, 235, 225, 255))
        return img

    titles = {'Idle': 'Idle  (3.0 s loop, 24 fps)', 'Walk': 'Walk  (chase run, 0.667 s cycle, 24 fps)',
              'Slam': 'Slam  (1.467 s, 30 fps, impact 0.70 s)'}
    for name in ('Idle', 'Walk', 'Slam'):
        src = sorted((FRAMES / name).glob('*.png'))
        tmp = CACHE / ('video_' + name)
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        n = 0
        # normal speed: every other 60 Hz sample at 30 fps; half speed: every sample at 30 fps
        half = src if name != 'Walk' else src[: int(len(src) * 2 / 3)]
        for speed, seq in (('normal speed', src[::2]), ('half speed', half)):
            for p in seq:
                im = Image.open(p).convert('RGB')
                label(im, titles[name], speed + '  -  client-interpolated poses (per-joint lerp)').save(tmp / ('%05d.png' % n))
                n += 1
        mp4 = PREVIEWS / (name + '.mp4')
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '30', '-i', str(tmp / '%05d.png'),
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '24', '-preset', 'slow', '-movflags',
                        '+faststart', str(mp4)], check=True)
        print('[moves] wrote', mp4, '%.1f MB' % (mp4.stat().st_size / 1e6), flush=True)
    # attack check sheet
    chk = FRAMES / 'check'
    meta = json.loads((chk / 'meta.json').read_text())
    W, H = 800, 600
    sheet = Image.new('RGB', (W * 4, H * 2 + 70), (24, 30, 26))
    d = ImageDraw.Draw(sheet)
    d.text((20, 18), 'Hammer boss Slam: attack check (front 3/4 above, fists on the haft below)', font=font,
           fill=(240, 245, 240))
    for j, m in enumerate(meta):
        for r, kind in enumerate(('wide', 'close')):
            im = Image.open(chk / ('%s_%d.png' % (kind, j))).convert('RGB')
            label(im, '%s  t=%.2f s (frame %d)' % (m['label'], m['time'], m['frame']) if r == 0 else 'grip close-up')
            sheet.paste(im, (j * W, 70 + r * H))
    sheet.save(PREVIEWS / 'AttackCheck_Slam.png')
    print('[moves] wrote', PREVIEWS / 'AttackCheck_Slam.png', flush=True)


# ================================================================== main
def main(stage):
    if stage == 'post':
        post()
        return
    if stage == 'extract' or not (CACHE / 'rig.json').exists():
        extract()
        if stage == 'extract':
            return
    rig, meshes = load()
    clips = build_clips(rig)
    GAME.mkdir(parents=True, exist_ok=True)
    pp = partposes(rig, clips)
    proof = axis_proof(rig, pp['clips']['Idle']['frames'][0]['poses'])
    log('axis proof: Idle frame 0 vs template rest, max position error %.2e, rotation %.2e' %
        (proof['maxPositionError'], proof['maxRotationError']))
    (GAME / 'PartPoses.json').write_text(json.dumps(pp, separators=(',', ':')))
    gd = gamedata(rig, clips, meshes)
    (GAME / 'BossGameData.json').write_text(json.dumps(gd, indent=1))
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    overlap = bvh_overlap(rig, meshes)
    checks = run_checks(rig, meshes, clips, overlap)
    checks['axisProof'] = proof
    checks['allPass'] = checks['allPass'] and proof['pass']
    checks['generated'] = time.strftime('%Y-%m-%d %H:%M')
    (HERE / 'MotionChecks.json').write_text(json.dumps(checks, indent=1, default=float))
    fails = [r for r in checks['summary'] if not r['pass']]
    log('checks: %d rows, %d failing' % (len(checks['summary']), len(fails)))
    for r in fails:
        log('  FAIL', r)
    rig_ob = bpy.data.objects['HammerBoss_Rig']
    key_actions(rig_ob, clips)
    rig_ob['MovesActions'] = 'HB_Idle (24 fps), HB_Walk (24 fps), HB_Slam (30 fps); old Boss_* actions untouched'
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    log('saved', BLEND.name)
    if stage == 'all':
        render_previews(clips)
        subprocess.run(['python', str(Path(__file__).resolve()), 'post'], check=True)


if __name__ == '__main__':
    main(stage_arg())
