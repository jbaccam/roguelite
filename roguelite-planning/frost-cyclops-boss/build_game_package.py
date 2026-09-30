"""Frost Cyclops game package (plans/BOSS_GAME_PACKAGE_SPEC.md). Run in Blender:

    blender -b --factory-startup --python build_game_package.py

Opens FrostCyclops.blend (the approved model, textures and rig are not changed) and:
  1. regenerates the ReferencePose / RigTest_ROM / GroundSlam / Stomp actions from
     fc_motion (Stomp now starts and ends exactly on the idle start pose and keeps
     the reference knee roll), re-runs AttackMotionChecks and re-exports them;
  2. authors Idle, Walk, Hit and Death at 24 fps (fc_gameclips.py); the Death
     pose is solved against the evaluated mesh so it rests on the ground;
  3. resamples GroundSlam and Stomp to 24 fps with their timing in seconds kept;
  4. writes exports/game/AnimationData.json, BossGameData.json and
     FrostCyclops_Studio.fbx (+ .fbm textures), GameClipChecks.json;
  5. renders previews/GameClips.png and a low-res mp4 per new clip.
"""
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bpy                           # noqa: E402
import numpy as np                   # noqa: E402
from mathutils import Matrix         # noqa: E402

NAME = 'FrostCyclops'
BOSS_ID = 'frost-cyclops'
GAME = HERE / 'exports' / 'game'
PREV = HERE / 'previews'
WORK = HERE / '_work'
FPS = 24


def log(*a):
    print('[GP]', *a, flush=True)


bpy.ops.wm.open_mainfile(filepath=str(HERE / f'{NAME}.blend'))
import build_frost_cyclops as BF     # noqa: E402  (function library; main() is not run on import)
import fc_blender as B               # noqa: E402
import fc_deliver as FD              # noqa: E402
import fc_design as D                # noqa: E402
import fc_gameclips as GC            # noqa: E402
import fc_motion as MO               # noqa: E402
import fc_parts as FP                # noqa: E402
import fc_pose as PO                 # noqa: E402

GAME.mkdir(parents=True, exist_ok=True)
WORK.mkdir(exist_ok=True)
scene = bpy.context.scene
rig = bpy.data.objects[f'{NAME}_Rig']
sk = PO.Skeleton()
meshes = {o.name.split('_', 1)[1]: o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith(NAME + '_')}
DEFORM = [b.name for b in rig.data.bones if b.use_deform]
assert set(DEFORM) == set(sk.order), 'rig and skeleton disagree'
err = max(float(np.abs(np.array(rig.data.bones[b].matrix_local) - sk.rest[b]).max()) for b in sk.order)
assert err < 1e-4, err
log('rig matches the skeleton, max rest error', err)

S = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def cf(m):
    m = S @ m @ S
    return [round(x, 7) for x in [m[0][3], m[1][3], m[2][3], m[0][0], m[0][1], m[0][2], m[1][0], m[1][1], m[1][2],
                                  m[2][0], m[2][1], m[2][2]]]


# ---------------------------------------------------------- 1. attack actions
for a in ('ReferencePose', 'RigTest_ROM', 'GroundSlam', 'Stomp', 'Idle', 'Walk', 'Hit', 'Death'):
    if a in bpy.data.actions:
        bpy.data.actions.remove(bpy.data.actions[a])
info = BF.build_actions(rig, sk)
log('attack actions rebuilt')


# ---------------------------------------------------------- helpers
def apply_pose(P):
    """Pose the rig (no keys) and update."""
    rig.animation_data.action = None
    for name in sk.order:
        par = sk.parent[name]
        if par:
            basis = np.linalg.inv(sk.rest[name]) @ sk.rest[par] @ np.linalg.inv(P.m[par]) @ P.m[name]
        else:
            basis = np.linalg.inv(sk.rest[name]) @ P.m[name]
        pb = rig.pose.bones[name]
        pb.rotation_mode = 'QUATERNION'
        loc, q, sc = Matrix([list(r) for r in basis]).decompose()
        pb.location, pb.rotation_quaternion, pb.scale = loc, q, (1, 1, 1)
    bpy.context.view_layer.update()


def mesh_min_z(sections=None, forward_of=None):
    """Lowest evaluated vertex z; with forward_of=y only vertices ahead of y count."""
    dg = bpy.context.evaluated_depsgraph_get()
    best = 1e9
    for sec, ob in meshes.items():
        if sections and sec not in sections:
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        ev.to_mesh_clear()
        co = co.reshape(-1, 3)
        if forward_of is not None:
            co = co[co[:, 1] < forward_of]
        if len(co):
            best = min(best, float(co[:, 2].min()))
    return best


BODY = ['Body', 'Head', 'Eye', 'Fur', 'Gear']

# ---------------------------------------------------------- 2. Death contact solve
samples = PO.club_samples_ref(200)
best = None
for alpha in np.arange(30, 111, 2.0):          # the dropped club lies with its haft on the snow
    G = GC.club_rest_on_ground(sk, samples, alpha)
    pts = (G[:3, :3] @ samples.T).T + G[:3, 3]
    e = abs(pts[:20, 2].min() - D.HAFT_R[0])
    if best is None or e < best[0]:
        best = (e, alpha)
club_alpha = float(best[1])
# rest the decimated club mesh exactly on the snow (the samples are the pre-decimation stone)
fr = GC.death_frames(sk, beta=10.0, club_alpha=club_alpha, samples=samples)
apply_pose(fr[-1])
GC.CLUB_LIFT = -mesh_min_z(['Club'])
kneel_lift = 0.0
n_death = int(round(GC.DEATH_DURATION * FPS))
kneel_frame = int(round(1.05 * FPS))
for it in range(3):
    fr = GC.death_frames(sk, beta=10.0, kneel_lift=kneel_lift, club_alpha=club_alpha, samples=samples)
    apply_pose(fr[kneel_frame])
    z = mesh_min_z(BODY)
    kneel_lift += -z
log('kneel lift', round(kneel_lift, 3))
# topple until the body ahead of the knees (belly, chest, arms) reaches the snow;
# the knees and tucked feet already rest on it
fr = GC.death_frames(sk, beta=10.0, kneel_lift=kneel_lift, club_alpha=club_alpha, samples=samples)
apply_pose(fr[kneel_frame])
knee_y = min(float(np.array(rig.pose.bones[s + 'LowerLeg'].head)[1]) for s in ('Right', 'Left'))
lo, hi = 20.0, 95.0
for it in range(14):
    mid = (lo + hi) / 2
    fr = GC.death_frames(sk, beta=mid, kneel_lift=kneel_lift, club_alpha=club_alpha, samples=samples)
    apply_pose(fr[-1])
    if mesh_min_z(BODY, forward_of=knee_y - 0.8) > 0.0:
        lo = mid
    else:
        hi = mid
beta = lo
fr = GC.death_frames(sk, beta=beta, kneel_lift=kneel_lift, club_alpha=club_alpha, samples=samples)
apply_pose(fr[-1])
log('death topple beta', round(beta, 2), 'final body min z', round(mesh_min_z(BODY), 4))
death_params = {'topple_deg': round(beta, 3), 'kneel_lift': round(kneel_lift, 4), 'club_tip_deg': club_alpha,
                'club_lift': round(GC.CLUB_LIFT, 4)}

# ---------------------------------------------------------- 3. game clip actions (24 fps keys)
clips_np = {
    'Idle': (GC.idle_frames(sk), True),
    'Walk': (GC.walk_frames(sk)[0], True),
    'Hit': (GC.hit_frames(sk), False),
    'Death': (fr, False),
}
walk_planted = GC.walk_frames(sk)[1]
rig.animation_data_create()
for name, (frames, loop) in clips_np.items():
    act = BF.make_action(rig, sk, name, [(i + 1, P) for i, P in enumerate(frames)])
    act['fps'] = FPS
    act['loop'] = loop
log('game clip actions keyed')


def sample_clip(action, n, src_fps, src_last):
    """matrix_basis of every deform bone at 24 fps times 0..n (seconds kept)."""
    rig.animation_data.action = action
    out = []
    for f in range(n + 1):
        t = f / FPS
        fsrc = min(1.0 + t * src_fps, float(src_last))
        fi = int(math.floor(fsrc))
        scene.frame_set(fi, subframe=fsrc - fi)
        bpy.context.view_layer.update()
        out.append({'time': round(t, 7), 'transforms': {b: cf(rig.pose.bones[b].matrix_basis) for b in DEFORM}})
    return out


# ---------------------------------------------------------- 4. AnimationData.json
anim = {'id': BOSS_ID, 'fps': FPS,
        'bones': {b.name: {'parent': b.parent.name if b.parent else None,
                           'rest': cf(b.parent.matrix_local.inverted() @ b.matrix_local if b.parent else b.matrix_local)}
                  for b in rig.data.bones if b.use_deform},
        'clips': {},
        'motion': {'strideLength': GC.WALK_STRIDE, 'nominalSpeed': round(GC.WALK_STRIDE / GC.WALK_CYCLE, 4)}}
for name, (frames, loop) in clips_np.items():
    n = len(frames) - 1
    anim['clips'][name] = {'duration': round(n / FPS, 7), 'loop': loop,
                           'frames': sample_clip(bpy.data.actions[name], n, FPS, n + 1)}
src = {'GroundSlam': 60, 'Stomp': 80}
for name, last in src.items():
    dur_src = (last - 1) / 30.0
    n = int(math.ceil(dur_src * FPS - 1e-9))
    anim['clips'][name] = {'duration': round(n / FPS, 7), 'loop': False,
                           'frames': sample_clip(bpy.data.actions[name], n, 30, last)}
(GAME / 'AnimationData.json').write_text(json.dumps(anim, separators=(',', ':')))
log('AnimationData.json', {k: len(v['frames']) for k, v in anim['clips'].items()})

# ---------------------------------------------------------- checks on the keyed game clips
checks = {'loopErrors': {}, 'startsOnIdleStart': {}, 'walk': {}, 'death': {}, 'nan': {}}
idle0 = anim['clips']['Idle']['frames'][0]['transforms']
for name, c in anim['clips'].items():
    fr0, frN = c['frames'][0]['transforms'], c['frames'][-1]['transforms']
    checks['nan'][name] = any(not math.isfinite(x) for f in c['frames'] for v in f['transforms'].values() for x in v)
    if c['loop']:
        checks['loopErrors'][name] = max(abs(a - b) for n in fr0 for a, b in zip(fr0[n], frN[n]))
    if name in ('GroundSlam', 'Stomp', 'Hit', 'Death'):
        checks['startsOnIdleStart'][name] = {
            'start': max(abs(a - b) for n in fr0 for a, b in zip(fr0[n], idle0[n])),
            'end': (max(abs(a - b) for n in frN for a, b in zip(frN[n], idle0[n]))
                    if name != 'Death' else None)}
# walk: planted-foot drift in world (root advancing at nominalSpeed)
v = GC.WALK_STRIDE / GC.WALK_CYCLE
rig.animation_data.action = bpy.data.actions['Walk']
nW = len(clips_np['Walk'][0]) - 1
for side in ('Right', 'Left'):
    worst, start = 0.0, None
    for f in range(nW + 1):
        scene.frame_set(f + 1)
        p = np.array(rig.pose.bones[side + 'Foot'].head) + np.array([0, -v * f / FPS, 0])
        if walk_planted[f][side]:
            start = p if start is None else start
            worst = max(worst, float(np.linalg.norm(p - start)))
        else:
            start = None
    checks['walk']['plantedFootDrift_' + side] = round(worst, 6)
walk_club = []
for f in range(nW + 1):
    scene.frame_set(f + 1)
    walk_club.append(mesh_min_z(['Club']))
checks['walk']['clubLowestZ'] = round(min(walk_club), 4)
# death: nothing through the ground by more than 0.05. The approved model's soles
# already sit a little below z = 0 in its standing (idle start) pose; that amount is
# reported as groundOffset (the game lifts the model by it) and the check is made
# against the ground at that offset.
rig.animation_data.action = bpy.data.actions['ReferencePose']
scene.frame_set(1)
standing_min = mesh_min_z()
ground_offset = max(0.0, -standing_min)
rig.animation_data.action = bpy.data.actions['Death']
dz = []
for f in range(n_death + 1):
    scene.frame_set(f + 1)
    dz.append(mesh_min_z())
worst_f = int(np.argmin(dz))
scene.frame_set(worst_f + 1)
checks['death_lowest_section'] = {sec: round(mesh_min_z([sec]), 4) for sec in meshes}
checks['death'] = {'minZPerFrame': [round(z, 4) for z in dz], 'minZ': round(min(dz), 4), 'minZFrame': worst_f,
                   'groundOffset': round(ground_offset, 4),
                   'minZRelativeToGround': round(min(dz) + ground_offset, 4),
                   'finalBodyMinZ': round(mesh_min_z(BODY), 4), 'params': death_params}
fails = []
for k, e in checks['loopErrors'].items():
    if e > 1e-4:
        fails.append(f'{k} loop error {e}')
for k, e in checks['startsOnIdleStart'].items():
    if e['start'] > 1e-4 or (e['end'] is not None and e['end'] > 1e-4):
        fails.append(f'{k} does not start/end on the idle start pose {e}')
if any(checks['nan'].values()):
    fails.append('NaN in a clip')
for side in ('Right', 'Left'):
    if checks['walk']['plantedFootDrift_' + side] > 0.01:
        fails.append(f'walk drift {side}')
if checks['death']['minZRelativeToGround'] < -0.05:
    fails.append(f'death below ground {checks["death"]["minZRelativeToGround"]}')
checks['passed'] = not fails
checks['failures'] = fails
(GAME / 'GameClipChecks.json').write_text(json.dumps(checks, indent=1))
log('game clip checks', fails or 'passed')

# ---------------------------------------------------------- 5. BossGameData.json
rig.animation_data.action = bpy.data.actions['ReferencePose']
scene.frame_set(1)
dg = bpy.context.evaluated_depsgraph_get()
pts = []
for sec in BODY:
    ev = meshes[sec].evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    ev.to_mesh_clear()
    pts.append(co.reshape(-1, 3))
pts = np.concatenate(pts)
footprint = float(np.sqrt((pts[:, :2] ** 2).sum(1)).max())


def studio(v):
    return [round(-float(v[0]), 4), round(float(v[2]), 4), round(float(v[1]), 4)]


gs, st = info['GroundSlam'], info['Stomp']
Cc = sk.ref['Club']
club_off = (np.linalg.inv(Cc) @ np.append(FP.club_impact_point(), 1.0))[:3]
Fl = sk.ref['LeftFoot']
A = D.J['LeftFoot']
fdir = D.FOOT_DIR['Left']
sole_ref = np.array([A[0] + fdir[0] * 0.75, A[1] + fdir[1] * 0.75, 0.0])
sole_off = (np.linalg.inv(Fl) @ np.append(sole_ref, 1.0))[:3]
t_imp_gs = (gs['impact_frame'] - 1) / 30.0
t_imp_st = (st['impact_frame'] - 1) / 30.0
game = {
    'attacks': {
        'GroundSlam': {
            'duration': anim['clips']['GroundSlam']['duration'],
            'warnStart': round((8 - 1) / 30.0, 4),            # the club is rising in front (readable windup)
            'impact': round(t_imp_gs, 4),
            'activeEnd': round(t_imp_gs, 4),
            'recoveryEnd': round((59 - 1) / 30.0, 4),
            'points': {'ClubImpact': {'bone': 'Club', 'offset': [round(float(x), 4) for x in club_off],
                                      'rootAtImpact': gs['club_impact_point_root'],
                                      'rootAtImpactStudio': studio(gs['club_impact_point_root'])}},
            'strikeFaceNormalAtImpact': gs['strike_face_normal_at_impact'],
            'strikeFaceNormalAtImpactStudio': studio(gs['strike_face_normal_at_impact'])},
        'Stomp': {
            'duration': anim['clips']['Stomp']['duration'],
            'warnStart': round((10 - 1) / 30.0, 4),           # the slow leg raise is the telegraph
            'impact': round(t_imp_st, 4),
            'activeEnd': round(t_imp_st, 4),
            'recoveryEnd': round((80 - 1) / 30.0, 4),
            'points': {'StompImpact': {'bone': 'LeftFoot', 'offset': [round(float(x), 4) for x in sole_off],
                                       'rootAtImpact': st['StompImpact_root'],
                                       'rootAtImpactStudio': studio(st['StompImpact_root'])}},
            'directionAtImpact': st['StompSpikeDirection_root'],
            'directionAtImpactStudio': studio(st['StompSpikeDirection_root']),
            'spikeLineLength': [20, 25]},
    },
    'rootHeight': round(float(D.J['HumanoidRootPart'][2]), 4),
    'groundOffset': round(ground_offset, 4),
    'height': round(float(pts[:, 2].max()), 4),
    'footprintRadius': round(footprint, 4),
    'walk': {'strideLength': GC.WALK_STRIDE, 'nominalSpeed': round(v, 4), 'cycle': GC.WALK_CYCLE},
    'notes': "Times in seconds from clip start. Offsets are in the named bone's local space (Blender axes, studs); root positions are Blender root space; *Studio vectors use the (-X, Z, Y) mapping. groundOffset: the soles sit this far below z = 0 in the standing pose; raise the model by it so the feet rest on the ground.",
}
(GAME / 'BossGameData.json').write_text(json.dumps(game, indent=1))
log('BossGameData.json written')
import snap_game_timings                                   # noqa: E402  (same folder)
snap_game_timings.snap(log=log)                            # 30 fps times -> whole 24 fps frames

# ---------------------------------------------------------- 6. attack checks + existing exports refreshed
free = bpy.data.objects.get('ReviewCamera') or bpy.data.objects.new('ReviewCamera',
                                                                    bpy.data.cameras.new('ReviewCamera'))
if free.name not in bpy.data.collections['REVIEW_ONLY'].objects:
    bpy.data.collections['REVIEW_ONLY'].objects.link(free)
mchecks = FD.motion_checks(info)
old = json.loads((HERE / 'AttackMotionChecks.json').read_text())
old.update({'GroundSlam': mchecks['GroundSlam'], 'Stomp': mchecks['Stomp'], 'passed': mchecks['passed'],
            'failures': mchecks['failures']})
(HERE / 'AttackMotionChecks.json').write_text(json.dumps(old, indent=1))
log('attack checks', mchecks['passed'], mchecks['failures'][:5])
tex = {sec: {'master': f'{NAME}_{sec}_BaseColor_{2048 if sec != "Eye" else 1024}.png',
             'delivery': f'{NAME}_{sec}_BaseColor.png'} for sec in meshes}
BF.swap_images(meshes, tex, 'delivery')
FD.export_all()

# ---------------------------------------------------------- 7. Studio import FBX
rig.animation_data.action = None
rig.data.pose_position = 'REST'
for pb in rig.pose.bones:
    pb.location, pb.rotation_quaternion, pb.scale = (0, 0, 0), (1, 0, 0, 0), (1, 1, 1)
FD.select_export(True)
fbm = GAME / f'{NAME}_Studio.fbm'
fbm.mkdir(exist_ok=True)
bpy.ops.export_scene.fbx(filepath=str(GAME / f'{NAME}_Studio.fbx'), use_selection=True,
                         object_types={'ARMATURE', 'MESH'}, add_leaf_bones=False, use_armature_deform_only=True,
                         bake_anim=False, axis_forward='-Z', axis_up='Y', apply_unit_scale=True, global_scale=1.0,
                         mesh_smooth_type='OFF', use_mesh_modifiers=False, path_mode='COPY', embed_textures=True)
for sec in meshes:
    shutil.copy2(HERE / 'textures' / tex[sec]['delivery'], fbm / tex[sec]['delivery'])
rig.data.pose_position = 'POSE'
BF.swap_images(meshes, tex, 'master')
log('studio fbx written')

# ---------------------------------------------------------- 8. previews (Workbench, small)
scene.camera = free
FD._workbench(transparent=False)
scene.display.shading.show_shadows = True
tiles = []
for name in ('Idle', 'Walk', 'Hit', 'Death'):
    n = len(clips_np[name][0]) - 1
    for f in sorted(set(int(round(n * k)) for k in (0.0, 0.25, 0.5, 0.75, 1.0))):
        rig.animation_data.action = bpy.data.actions[name]
        scene.frame_set(f + 1)
        FD.aim_camera(free, (-19.0, -25.0, 9.0), (0.0, -1.5, 5.2), lens=40)
        a = FD._render_rgba(WORK / 'gc.png', (300, 340))[:, :, :3]
        FD.draw_text(a, 6, 6, '%s %.2fS' % (name, f / FPS), scale=2, color=(0.1, 0.1, 0.15))
        tiles.append(a)
FD.save_rgb(FD.tile(tiles, 5), PREV / 'GameClips.png')
ff = shutil.which('ffmpeg')
videos = {}
for name in ('Idle', 'Walk', 'Hit', 'Death'):
    n = len(clips_np[name][0]) - 1
    d = WORK / f'gv_{name}'
    d.mkdir(exist_ok=True)
    rig.animation_data.action = bpy.data.actions[name]
    reps = 2 if clips_np[name][1] else 1
    k = 0
    for rpt in range(reps):
        for f in range(n + (0 if rpt < reps - 1 else 1)):
            scene.frame_set(f + 1)
            FD.aim_camera(free, (-19.0, -25.0, 9.0), (0.0, -1.5, 5.2), lens=40)
            a = FD._render_rgba(WORK / 'gv.png', (320, 360))[:, :, :3]
            FD.save_rgb(a, d / ('f%04d.png' % k))
            k += 1
    if ff:
        out = PREV / f'Game_{name}.mp4'
        r = subprocess.run([ff, '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', str(d / 'f%04d.png'),
                            '-pix_fmt', 'yuv420p', '-c:v', 'libx264', '-crf', '24', str(out)],
                           capture_output=True, text=True)
        videos[name] = out.name if r.returncode == 0 else r.stderr[-300:]
log('previews', videos)
scene.render.engine = 'CYCLES'

# ---------------------------------------------------------- 9. save
rig.animation_data.action = bpy.data.actions['ReferencePose']
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(HERE / f'{NAME}.blend'), compress=True)
log('GAME PACKAGE DONE', json.dumps({'death': death_params, 'checks': fails, 'attack': mchecks['failures']}))
