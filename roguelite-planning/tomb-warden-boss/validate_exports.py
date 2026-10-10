"""Fresh re-import check of the Tomb Warden game package (Blender 5.2, headless):

    blender -b --factory-startup --python-exit-code 1 --python validate_exports.py

Imports exports/game/TombWarden_Studio.fbx into an empty file and checks it
against AnimationData.json / BossGameData.json / GameChecks.json:
  * meshes TombWarden_<Section>, < 20k triangles each, material named like
    the object with a 1024 map that loads, UVs, flat (faceted) normals;
  * weights: every vertex weighted, <= 4 influences, normalised; rigid parts
    (Mask, EyeGlow, fists) are one bone at 1.0; Root/HumanoidRootPart carry
    no weight; no mesh object shares a name with a bone; no leaf bones;
    no animation in the file;
  * bones and parents equal AnimationData.json, rest matrices equal its
    'rest' entries; height in studs;
  * every clip: frame count = duration*24+1, times, no NaN, loops close,
    non-loop clips start/end on the Idle start pose (Death: start only),
    Emerge root starts at +3.5 back and ends exactly at the origin;
  * clip replay on the RE-IMPORTED rig: the FistSlam / Emerge contact points
    and FistHook points, posed from AnimationData, land on BossGameData's
    rootAtImpact (proves the clip data + rig + points agree);
  * BossGameData timings ordered, required points present;
  * the worst numbers of the generator's per-frame motion checks (GameChecks.json).
Writes validation-report.json; exits non-zero on any failure.
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
GAME = HERE / 'exports' / 'game'
NAME = 'TombWarden'
SECTIONS = ['Body', 'Cloth', 'Mask', 'LeftFist', 'RightFist', 'EyeGlow']
RIGID = {'Mask': 'Head', 'EyeGlow': 'Head', 'LeftFist': 'LeftHand', 'RightFist': 'RightHand'}
CLIPS = ['Idle', 'Walk', 'Hit', 'Death', 'Emerge', 'FistSlam', 'FistHook', 'Roar']
SM = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
report = {'failures': [], 'checks': {}}


def fail(msg):
    report['failures'].append(msg)
    print('FAIL', msg)


def uncf(v):
    m = Matrix(((v[3], v[4], v[5], v[0]), (v[6], v[7], v[8], v[1]), (v[9], v[10], v[11], v[2]), (0, 0, 0, 1)))
    return SM @ m @ SM


anim = json.loads((GAME / 'AnimationData.json').read_text())
game = json.loads((GAME / 'BossGameData.json').read_text())
gchk = json.loads((GAME / 'GameChecks.json').read_text())

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(GAME / f'{NAME}_Studio.fbx'))
rigs = [o for o in bpy.data.objects if o.type == 'ARMATURE']
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
rig = rigs[0] if rigs else None
fbx = {'meshes': {}, 'actions_in_file': [a.name for a in bpy.data.actions]}
if rig is None:
    fail('no armature')
if fbx['actions_in_file']:
    fail(f'animation in the rest FBX: {fbx["actions_in_file"]}')
want = {f'{NAME}_{s}' for s in SECTIONS}
if {o.name for o in meshes} != want:
    fail(f'mesh names {sorted(o.name for o in meshes)}')
bones = {b.name: (b.parent.name if b.parent else None) for b in rig.data.bones}
fbx['bones'] = len(bones)
if bones != {k: v['parent'] for k, v in anim['bones'].items()}:
    fail('bone set / parents differ from AnimationData.json')
leaf = [b for b in bones if b.endswith('_end')]
if leaf:
    fail(f'leaf bones {leaf}')
clash = sorted({o.name for o in meshes} & set(bones))
if clash:
    fail(f'mesh/bone name clash {clash}')
# rest matrices vs AnimationData
rest_err = 0.0
for b in rig.data.bones:
    rl = b.parent.matrix_local.inverted() @ b.matrix_local if b.parent else b.matrix_local
    m = uncf(anim['bones'][b.name]['rest'])
    rest_err = max(rest_err, max(abs(rl[i][j] - m[i][j]) for i in range(3) for j in range(4)))
fbx['restMatrixMaxErrorVsAnimationData'] = round(rest_err, 6)
if rest_err > 1e-3:
    fail(f'rest matrices differ from AnimationData by {rest_err}')
if max(abs(rig.matrix_world[i][j] - (1.0 if i == j else 0.0)) for i in range(4) for j in range(4)) > 1e-4:
    fbx['armatureObjectTransform'] = [list(r) for r in rig.matrix_world]
zmax = -1e9
for o in meshes:
    me = o.data
    sec = o.name.replace(NAME + '_', '')
    tri = sum(len(p.vertices) - 2 for p in me.polygons)
    names = {g.index: g.name for g in o.vertex_groups}
    unw = over4 = badsum = 0
    used = set()
    rigid_ok = True
    for v in me.vertices:
        gs = [g for g in v.groups if g.weight > 1e-6]
        if not gs:
            unw += 1
            continue
        if len(gs) > 4:
            over4 += 1
        if abs(sum(g.weight for g in gs) - 1) > 1e-3:
            badsum += 1
        for g in gs:
            used.add(names[g.group])
        if sec in RIGID and not (len(gs) == 1 and names[gs[0].group] == RIGID[sec] and abs(gs[0].weight - 1) < 1e-4):
            rigid_ok = False
    tex = None
    mats = [m.name for m in me.materials if m]
    for m in me.materials:
        if m and m.node_tree:
            for n in m.node_tree.nodes:
                if n.type == 'TEX_IMAGE' and n.image and n.image.size[0]:
                    tex = list(n.image.size)
    flat = 0
    tot = 0
    cn = me.corner_normals
    for p in me.polygons:
        for li in p.loop_indices:
            tot += 1
            flat += cn[li].vector.dot(p.normal) > 0.9995
    for v in me.vertices:
        zmax = max(zmax, (o.matrix_world @ v.co).z)
    rec = {'triangles': tri, 'materials': mats, 'texture': tex, 'uv_layers': len(me.uv_layers),
           'unweighted': unw, 'over4': over4, 'notNormalised': badsum, 'bonesUsed': sorted(used),
           'rigidSingleBone': (rigid_ok if sec in RIGID else None), 'flatCornerFraction': round(flat / max(tot, 1), 4)}
    fbx['meshes'][o.name] = rec
    if tri >= 20000:
        fail(f'{o.name} {tri} triangles')
    if mats != [o.name]:
        fail(f'{o.name} materials {mats}')
    if tex != [1024, 1024]:
        fail(f'{o.name} texture {tex}')
    if not me.uv_layers:
        fail(f'{o.name} no UVs')
    if unw or over4 or badsum:
        fail(f'{o.name} weights unweighted {unw} over4 {over4} notNormalised {badsum}')
    if sec in RIGID and not rigid_ok:
        fail(f'{o.name} is not rigid to {RIGID[sec]}')
    if used & {'Root', 'HumanoidRootPart'}:
        fail(f'{o.name} weights on Root/HumanoidRootPart')
    if rec['flatCornerFraction'] < 0.98:
        fail(f'{o.name} faceted normals lost')
fbx['totalTriangles'] = sum(m['triangles'] for m in fbx['meshes'].values())
fbx['restHeight'] = round(zmax, 4)
if abs(zmax - game['height']) > 0.05:
    fail(f'height {zmax} vs BossGameData {game["height"]}')
fbm = sorted(p.name for p in (GAME / f'{NAME}_Studio.fbm').glob('*.png'))
fbx['fbm'] = fbm
if not fbm:
    fail('no PNG in .fbm')
report['checks']['TombWarden_Studio.fbx'] = fbx

# ------------------------------------------------------------ AnimationData
ad = {}
I12 = [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]
idle0 = anim['clips']['Idle']['frames'][0]['transforms']
for c in CLIPS:
    if c not in anim['clips']:
        fail(f'clip {c} missing')
        continue
    clip = anim['clips'][c]
    fr = clip['frames']
    n = int(round(clip['duration'] * 24)) + 1
    nan = any(not math.isfinite(x) for f in fr for t in f['transforms'].values() for x in t)
    times = all(abs(f['time'] - i / 24) < 1e-6 for i, f in enumerate(fr))
    allb = all(set(f['transforms']) == set(anim['bones']) for f in fr)
    e = {'frames': len(fr), 'expected': n, 'duration': clip['duration'], 'loop': clip['loop']}
    dif = lambda A, B: max(abs(a - b) for k in A for a, b in zip(A[k], B[k]))
    if clip['loop']:
        e['loopError'] = dif(fr[0]['transforms'], fr[-1]['transforms'])
        if e['loopError'] > 1e-6:
            fail(f'{c} loop does not close {e["loopError"]}')
    elif c != 'Emerge':
        e['startVsIdleStart'] = dif(fr[0]['transforms'], idle0)
        if e['startVsIdleStart'] > 1e-5:
            fail(f'{c} does not start on the Idle start pose')
    if not clip['loop'] and c != 'Death':
        if True:
            e['endVsIdleStart'] = dif(fr[-1]['transforms'], idle0)
            if e['endVsIdleStart'] > 1e-5:
                fail(f'{c} does not end on the Idle start pose')
    if len(fr) != n or nan or not times or not allb:
        fail(f'{c} frames/time/NaN/bones {e} nan={nan} times={times} bones={allb}')
    ad[c] = e
e0 = anim['clips']['Emerge']['frames']
root0 = uncf(e0[0]['transforms']['Root'])
rootN = uncf(e0[-1]['transforms']['Root'])
rest_root = uncf(anim['bones']['Root']['rest'])
w0 = (rest_root @ root0).translation
wN = (rest_root @ rootN).translation
ad['EmergeRootStart'] = [round(x, 5) for x in w0]
ad['EmergeRootEnd'] = [round(x, 5) for x in wN]
if (Vector(w0) - Vector(game['attacks']['Emerge']['rootStart'])).length > 1e-3 or Vector(wN).length > 1e-6:
    fail(f'Emerge root motion start {list(w0)} end {list(wN)}')
ad['idleStartIsRest'] = dif(idle0, {k: I12 for k in idle0})
report['checks']['AnimationData.json'] = ad

# --------------------------------------------------- replay on the reimported rig
rig.animation_data_create()
rig.animation_data.action = None
replay = {}


def pose_frame(clip, f):
    tr = anim['clips'][clip]['frames'][f]['transforms']
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.matrix_basis = uncf(tr[pb.name])
    bpy.context.view_layer.update()


for clip in ('FistSlam', 'FistHook', 'Emerge'):
    a = game['attacks'][clip]
    f = int(round(a['impact'] * 24))
    pose_frame(clip, f)
    errs = {}
    for name, pt in a['points'].items():
        pb = rig.pose.bones[pt['bone']]
        w = rig.matrix_world @ pb.matrix @ Vector(pt['offset'])
        errs[name] = round((w - Vector(pt['rootAtImpact'])).length, 5)
        if errs[name] > 0.01:
            fail(f'{clip} point {name} replays {errs[name]} studs off')
    replay[clip] = {'frame': f, 'pointErrorStuds': errs}
# fist contact on the ground at the slam impact, from the reimported, posed meshes
pose_frame('FistSlam', int(round(game['attacks']['FistSlam']['impact'] * 24)))
dg = bpy.context.evaluated_depsgraph_get()
lows = {}
for o in meshes:
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    lows[o.name] = round(min((o.matrix_world @ v.co).z for v in me.vertices), 4)
    ev.to_mesh_clear()
replay['FistSlamImpactLowestZ'] = lows
report['checks']['replayOnReimportedRig'] = replay

# ------------------------------------------------------------- BossGameData
bg = {}
need = {'FistSlam': ['SlamCenter', 'LeftFist', 'RightFist'], 'FistHook': ['HookFist', 'HookMid'],
        'Emerge': ['LeftFist', 'RightFist']}
for clip, pts in need.items():
    a = game['attacks'].get(clip)
    if a is None:
        fail(f'BossGameData missing {clip}')
        continue
    ts = [a[k] for k in ('warnStart', 'impact', 'activeEnd', 'recoveryEnd')]
    ok = all(x <= y + 1e-6 for x, y in zip(ts, ts[1:])) and ts[-1] <= a['duration'] + 1e-6
    if not ok:
        fail(f'{clip} timings out of order {ts}')
    miss = [p for p in pts if p not in a['points']]
    if miss:
        fail(f'{clip} points missing {miss}')
    bg[clip] = {'timings': ts, 'duration': a['duration'], 'points': sorted(a['points'])}
for k in ('rootHeight', 'height', 'footprintRadius', 'bodyCentreHeight'):
    if k not in game:
        fail(f'BossGameData missing {k}')
    bg[k] = game.get(k)
report['checks']['BossGameData.json'] = bg

# ------------------------------------------------------- generator motion checks
report['checks']['motionChecksWorst'] = gchk['summary']
report['checks']['motionChecksPassed'] = gchk['passed']
report['checks']['motionCheckFailures'] = gchk['failures']
report['checks']['coffinFit'] = gchk['coffinFit']
report['checks']['strikes'] = gchk['strikes']
report['passed'] = not report['failures']
report['note'] = ('Blender-verified, Studio untested. The motion checks run per frame on the Blender-evaluated meshes in the '
                  'generator (GameChecks.json); this file adds the fresh re-import of the Studio FBX.')
(HERE / 'validation-report.json').write_text(json.dumps(report, indent=1, default=str))
print('VALIDATION', 'PASSED' if report['passed'] else 'FAILED %d' % len(report['failures']))
sys.exit(0 if report['passed'] else 1)
