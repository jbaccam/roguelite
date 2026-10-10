"""Re-import the DJ Crab game package fresh and check it. Run in Blender 5.2:

    blender -b --factory-startup --python-exit-code 1 --python validate_exports.py

Writes validation-report.json and exits non-zero on any failure.

DJCrab_Studio.fbx (fresh factory scene)
  six DJCrab_<Section> meshes, each < 20k triangles, materials named like the
  mesh with the 1024 atlas loaded, UVs present, every vertex weighted to exactly
  one bone at 1.0 (rigid parts; <= 4 influences, normalized), the gear/glow on
  Body, Root carries no weights, no mesh object named like a bone, no leaf
  bones, no animation, bones + parents + parent-relative rest equal
  AnimationData.json, faceted normals kept (smooth eyes), rest dimensions equal
  the manifest, .fbm PNG present.
Skinning truth
  the re-imported rig is posed from AnimationData.json (matrix_basis back
  through cf) and the depsgraph-evaluated vertices are compared with the
  source rig's posed vertices (3 frames per clip).
Motion (every frame of every clip, on the re-imported rig and meshes)
  hinge directions, twist, frame-to-frame rotation, lowest point, planted tip
  drift, BVH overlaps (see motion_checks.py).
AnimationData.json / BossGameData.json
  clips, frame counts, times, NaNs, loop closure, attacks start/end on the
  Idle start pose (Intro: ends only; Death: starts only), Idle = 8 beats at
  124 BPM, required points, ordered timings, Intro snap at exactly 2.0 s.
"""
import bpy, json, math, sys
import numpy as np
from pathlib import Path
from mathutils import Matrix, Vector

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT))
import motion_checks as MC

GAMED = OUT / 'exports' / 'game'
NAME = 'DJCrab'
SECTIONS = ['Shell', 'Eyes', 'Legs', 'Claws', 'Gear', 'Glow']
MAN = json.loads((OUT / 'manifest.json').read_text())
anim = json.loads((GAMED / 'AnimationData.json').read_text())
gd = json.loads((GAMED / 'BossGameData.json').read_text())
gc = json.loads((GAMED / 'GameChecks.json').read_text())
BEAT = 60.0 / 124.0
report = {'files': {}, 'failures': [], 'status': 'Blender-verified, Studio untested'}


def fail(msg):
    report['failures'].append(msg)
    print('FAIL', msg, flush=True)


S = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def uncf(v):
    m = Matrix(((v[3], v[4], v[5], v[0]), (v[6], v[7], v[8], v[1]), (v[9], v[10], v[11], v[2]), (0, 0, 0, 1)))
    return S @ m @ S


def tris(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


def flat_fraction(me):
    cn = me.corner_normals
    ok = total = 0
    for p in me.polygons:
        for li in p.loop_indices:
            total += 1
            ok += cn[li].vector.dot(p.normal) > 0.9995
    return ok / max(total, 1)


def image_size(ob):
    for m in ob.data.materials:
        if m and m.node_tree:
            for n in m.node_tree.nodes:
                if n.type == 'TEX_IMAGE' and n.image and n.image.size[0] > 0:
                    if any(v > 0 for v in n.image.pixels[:4096]):
                        return list(n.image.size)
    return None


# ------------------------------------------------------------- fresh import
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(GAMED / f'{NAME}_Studio.fbx'))
rig = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
obs = {o.name: o for o in bpy.data.objects if o.type == 'MESH'}
st = {'meshes': {}, 'actions_in_file': [a.name for a in bpy.data.actions]}
want = {f'{NAME}_{s}' for s in SECTIONS}
if set(obs) != want:
    fail(f'mesh names {sorted(obs)} != {sorted(want)}')
if st['actions_in_file']:
    fail('FBX contains animation')
if rig is None:
    fail('no armature')
    raise SystemExit(1)
bones = {b.name: (b.parent.name if b.parent else None) for b in rig.data.bones}
st['bones'] = len(bones)
st['bone_names'] = sorted(bones)
if set(bones) != set(anim['bones']) or any(anim['bones'][n]['parent'] != p for n, p in bones.items() if n in anim['bones']):
    fail('bones/parents differ from AnimationData.json')
st['leaf_bones'] = [n for n in bones if n.endswith('_end')]
if st['leaf_bones']:
    fail('leaf bones present')
clash = sorted(set(obs) & set(bones))
st['mesh_bone_name_clashes'] = clash
if clash:
    fail(f'mesh names equal bone names: {clash}')
# parent-relative rest equals AnimationData
rest_err = 0.0
for b in rig.data.bones:
    m = b.parent.matrix_local.inverted() @ b.matrix_local if b.parent else b.matrix_local
    a = anim['bones'][b.name]['rest']
    mm = uncf(a)
    rest_err = max(rest_err, max(abs(m[i][j] - mm[i][j]) for i in range(3) for j in range(4)))
st['rest_matrix_max_error_vs_AnimationData'] = round(rest_err, 6)
if rest_err > 1e-3:
    fail(f'bone rest differs from AnimationData ({rest_err})')
st['armature_object_identity'] = all(abs(rig.matrix_world[i][j] - (1.0 if i == j else 0.0)) < 1e-5
                                     for i in range(4) for j in range(4))
weighted_bones = set()
for name, o in obs.items():
    me = o.data
    gnames = {g.index: g.name for g in o.vertex_groups}
    unweighted = multi = notone = nonbone = 0
    vb = []
    for v in me.vertices:
        gs = [g for g in v.groups if g.weight > 1e-6]
        if not gs:
            unweighted += 1
            vb.append(None)
            continue
        if len(gs) > 1:
            multi += 1
        if abs(sum(g.weight for g in gs) - 1.0) > 1e-3 or len(gs) > 4:
            notone += 1
        g = max(gs, key=lambda g: g.weight)
        if gnames.get(g.group) not in bones:
            nonbone += 1
        vb.append(gnames.get(g.group))
        weighted_bones.add(gnames.get(g.group))
    sec = name.replace(f'{NAME}_', '')
    e = {'triangles': tris(me), 'vertices': len(me.vertices), 'uv_layers': [u.name for u in me.uv_layers],
         'materials': [m.name for m in me.materials if m], 'texture': image_size(o),
         'unweighted': unweighted, 'multi_influence': multi, 'not_normalized_or_over4': notone,
         'weights_to_non_bones': nonbone, 'bones_used': sorted({b for b in vb if b}),
         'flat_corner_fraction': round(flat_fraction(me), 4),
         'armature_modifier': any(md.type == 'ARMATURE' and md.object == rig for md in o.modifiers)}
    if e['triangles'] >= 20000:
        fail(f'{name}: {e["triangles"]} triangles')
    if not e['uv_layers']:
        fail(f'{name}: no UVs')
    if e['materials'] != [name]:
        fail(f'{name}: materials {e["materials"]}')
    if e['texture'] != [1024, 1024]:
        fail(f'{name}: texture {e["texture"]}')
    if unweighted or multi or notone or nonbone:
        fail(f'{name}: weights {e}')
    if sec in ('Gear', 'Glow') and e['bones_used'] != ['Body']:
        fail(f'{name}: gear not rigid on Body ({e["bones_used"]})')
    if sec == 'Eyes':
        if e['flat_corner_fraction'] > 0.5:
            fail('Eyes lost smooth normals')
    elif e['flat_corner_fraction'] < 0.98:
        fail(f'{name}: faceted normals lost ({e["flat_corner_fraction"]})')
    if not e['armature_modifier']:
        fail(f'{name}: not skinned to the armature')
    st['meshes'][name] = e
st['root_has_weights'] = 'Root' in weighted_bones
if st['root_has_weights']:
    fail('Root bone carries weights')
st['total_triangles'] = sum(e['triangles'] for e in st['meshes'].values())
allv = np.concatenate([np.array([o.matrix_world @ v.co for v in o.data.vertices]) for o in obs.values()])
dims = {'height': round(float(allv[:, 2].max()), 4), 'lowest': round(float(allv[:, 2].min()), 4),
        'footprint_radius': round(float(np.sqrt((allv[:, :2] ** 2).sum(1)).max()), 4),
        'x': [round(float(allv[:, 0].min()), 4), round(float(allv[:, 0].max()), 4)],
        'y': [round(float(allv[:, 1].min()), 4), round(float(allv[:, 1].max()), 4)]}
st['rest_dimensions'] = dims
md = MAN['dimensions']
if abs(dims['height'] - md['height']) > 0.01 or abs(dims['y'][0] - md['overall_y'][0]) > 0.01 or \
        abs(dims['x'][1] - md['overall_x'][1]) > 0.01:
    fail(f'rest dimensions {dims} differ from manifest (scale/axes)')
fbm = sorted(p.name for p in (GAMED / f'{NAME}_Studio.fbm').glob('*.png'))
st['fbm_pngs'] = fbm
if not fbm:
    fail('no PNG in DJCrab_Studio.fbm')
report['files'][f'{NAME}_Studio.fbx'] = st

# ------------------------------------------------- re-imported skeleton/mesh
# FBX stores joints, not tails: Blender's importer guesses tails and marks bones "connected", which
# makes it ignore pose translation (Roblox Bone CFrames are unaffected). Unconnect before posing and
# take bone lengths (leg-tip points) from the manifest.
st['bones_marked_connected_by_importer'] = sum(1 for b in rig.data.bones if b.use_connect)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
for eb in rig.data.edit_bones:
    eb.use_connect = False
bpy.ops.object.mode_set(mode='OBJECT')
REST = {b.name: rig.matrix_world @ b.matrix_local for b in rig.data.bones}
PAR = dict(bones)
SK = MC.Skel(REST, PAR)
BLEN = {b['name']: (Vector(b['tail']) - Vector(b['head'])).length for b in MAN['bones']}
Vs, F, VB, VS = [], [], [], []
base = 0
for sec in SECTIONS:
    o = obs[f'{NAME}_{sec}']
    gnames = {g.index: g.name for g in o.vertex_groups}
    Vs.append(np.array([o.matrix_world @ v.co for v in o.data.vertices]))
    for v in o.data.vertices:
        VB.append(gnames[max(v.groups, key=lambda g: g.weight).group])
        VS.append(sec)
    F += [tuple(base + i for i in p.vertices) for p in o.data.polygons]
    base += len(o.data.vertices)
MESH = MC.RigidMesh(np.concatenate(Vs), F, VB, VS)
CLIPS = {n: {'bases': [{b: uncf(t) for b, t in fr['transforms'].items()} for fr in c['frames']],
             'times': [fr['time'] for fr in c['frames']]} for n, c in anim['clips'].items()}

# ------------------------------------------------------------ skinning truth
samples_p = OUT / '_work' / 'posed_samples.json'
sk = {'compared_frames': 0, 'max_vertex_error_vs_source': None, 'max_vertex_error_rigid_model': 0.0}
if samples_p.exists():
    smp = json.loads(samples_p.read_text())
    worst = 0.0
    worst_rigid = 0.0
    rig.data.pose_position = 'POSE'
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    for clip, frs in smp['samples'].items():
        for f, verts in frs.items():
            B = CLIPS[clip]['bases'][int(f)]
            for pb in rig.pose.bones:
                pb.matrix_basis = B[pb.name]
            bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            ev = []
            for sec in SECTIONS:
                o = obs[f'{NAME}_{sec}']
                e_ = o.evaluated_get(dg)
                me = e_.to_mesh()
                ev.append(np.array([o.matrix_world @ v.co for v in me.vertices]))
                e_.to_mesh_clear()
            ev = np.concatenate(ev)
            src = np.array(verts)
            worst = max(worst, float(np.abs(ev - src).max()))
            worst_rigid = max(worst_rigid, float(np.abs(ev - MESH.posed(SK, SK.fk(B))).max()))
            sk['compared_frames'] += 1
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    sk['max_vertex_error_vs_source'] = round(worst, 5)
    sk['max_vertex_error_rigid_model'] = round(worst_rigid, 5)
    if worst > 0.005:
        fail(f'posed re-import differs from the source rig by {worst:.4f} studs')
else:
    fail('posed_samples.json missing (run animate_game.py first)')
report['skinning_truth'] = sk

# ------------------------------------------------------------------ motion
walk = gd['walk']
GA = set(walk['groupA'])
nwalk = len(CLIPS['Walk']['bases']) - 1


def planted(clip, f, tag):
    if clip == 'Death':
        return False
    if clip == 'Walk':
        ph = (f / nwalk + (0.0 if tag in GA else walk['groupBPhaseOffset'])) % 1.0
        return ph < walk['duty']
    return True


snaps = gc.get('intentional_snaps', {})
mc = MC.run(SK, MESH, BLEN, CLIPS, planted, travel={'Walk': Vector((0, -walk['nominalSpeed'], 0))},
            snaps={k: {b: list(v) for b, v in d.items()} for k, d in snaps.items()})
report['motion'] = mc
w = mc['worst']
if w['hinge_violations']:
    fail(f'hinge violations: {w["hinge_violations"]}')
if w['twist_deg'] > 70:
    fail(f'twist {w["twist_deg"]}')
if w['bone_rotation_per_frame_deg'] > 45:
    fail(f'frame-to-frame rotation {w["bone_rotation_per_frame_deg"]}')
if w['lowest_point'] < -0.05:
    fail(f'below ground {w["lowest_point"]}')
if w['planted_tip_drift'] > 0.05:
    fail(f'tip drift {w["planted_tip_drift"]}')
report['overlap_summary'] = {n: e['overlaps'] for n, e in mc['clips'].items() if e['overlaps']}

# --------------------------------------------------------- AnimationData
REQ = ['Idle', 'Walk', 'Hit', 'Death', 'BeatCommand', 'ClawSlam', 'Bombard', 'Intro']
ad = {'id': anim.get('id'), 'fps': anim.get('fps'), 'motion': anim.get('motion'), 'clips': {}}
if anim.get('id') != 'dj-crab' or anim.get('fps') != 24:
    fail('AnimationData id/fps')
REST12 = [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]


def is_rest(tr):
    return all(max(abs(a - b) for a, b in zip(t, REST12)) < 1e-6 for t in tr.values())


for n in REQ:
    if n not in anim['clips']:
        fail(f'clip {n} missing')
for name, c in anim['clips'].items():
    fr = c['frames']
    n = int(round(c['duration'] * 24)) + 1
    exp_t = [i / 24 for i in range(n)]
    if name == 'Idle':
        exp_t[-1] = c['duration']
    e = {'frames': len(fr), 'expected': n, 'duration': c['duration'], 'loop': c['loop'],
         'nan': any(not math.isfinite(v) for f in fr for t in f['transforms'].values() for v in t),
         'times_ok': len(fr) == n and all(abs(f['time'] - t) < 1e-6 for f, t in zip(fr, exp_t)),
         'bones_ok': all(set(f['transforms']) == set(anim['bones']) for f in fr)}
    if c['loop']:
        e['loop_close_error'] = max(abs(a - b) for k in fr[0]['transforms']
                                    for a, b in zip(fr[0]['transforms'][k], fr[-1]['transforms'][k]))
        if e['loop_close_error'] > 1e-6:
            fail(f'{name} loop does not close')
    else:
        if name != 'Intro':
            e['starts_on_idle_start'] = is_rest(fr[0]['transforms'])
            if not e['starts_on_idle_start']:
                fail(f'{name} does not start on the Idle start pose')
        if name != 'Death':
            e['ends_on_idle_start'] = is_rest(fr[-1]['transforms'])
            if not e['ends_on_idle_start']:
                fail(f'{name} does not end on the Idle start pose')
    if e['nan'] or not e['times_ok'] or not e['bones_ok'] or len(fr) != n:
        fail(f'{name}: {e}')
    ad['clips'][name] = e
if abs(anim['clips']['Idle']['duration'] - 8 * BEAT) > 1e-5:
    fail('Idle is not 8 beats')
if is_rest(anim['clips']['Idle']['frames'][0]['transforms']) is False:
    fail('Idle frame 0 is not the rest pose')
report['files']['AnimationData.json'] = ad

# --------------------------------------------------------- BossGameData
g = {}
need = {'BeatCommand': ['CommandClaw'], 'ClawSlam': ['SlamCenter', 'LeftClaw', 'RightClaw'],
        'Bombard': ['SpeakerTop'], 'Intro': ['SpeakerTop']}
for name, pts in need.items():
    a = gd['attacks'].get(name)
    if not a:
        fail(f'BossGameData: {name} missing')
        continue
    ts = [a[k] for k in ('warnStart', 'impact', 'activeEnd', 'recoveryEnd')]
    ordered = all(x <= y + 1e-6 for x, y in zip(ts, ts[1:])) and ts[-1] <= a['duration'] + 1e-6
    miss = [p for p in pts if p not in a.get('points', {})]
    g[name] = {'timings': ts, 'ordered': ordered, 'points': sorted(a.get('points', {})), 'missing': miss,
               'duration_matches_clip': abs(a['duration'] - anim['clips'][name]['duration']) < 1e-3}
    if not ordered or miss or not g[name]['duration_matches_clip']:
        fail(f'BossGameData {name}: {g[name]}')
    for pn, pv in a.get('points', {}).items():
        if pv['bone'] not in anim['bones']:
            fail(f'{name}.{pn} bone {pv["bone"]} not exported')
        # recompute the point from the re-imported rig at the impact frame
        fi = round(a['impact'] * 24)
        P = SK.fk(CLIPS[name]['bases'][fi])
        wv = P[pv['bone']] @ Vector(pv['offset'])
        err = (wv - Vector(pv['rootAtImpact'])).length
        g[name][f'{pn}_recomputed_error'] = round(err, 4)
        if err > 0.01 and pn != 'SlamCenter':
            fail(f'{name}.{pn} does not match the re-imported rig ({err:.4f})')
if abs(gd['attacks']['Intro']['impact'] - 2.0) > 1e-9:
    fail('Intro snap is not at exactly 2.0 s')
for k in ('rootHeight', 'height', 'footprintRadius', 'bodyCentreHeight'):
    if k not in gd:
        fail(f'BossGameData {k} missing')
g['dimensions'] = {k: gd.get(k) for k in ('rootHeight', 'height', 'footprintRadius', 'bodyCentreHeight')}
g['walk'] = gd.get('walk')
report['files']['BossGameData.json'] = g

# ----------------------------------------------------------------- summary
report['summary'] = {
    'meshes': {n: e['triangles'] for n, e in st['meshes'].items()}, 'total_triangles': st['total_triangles'],
    'bones': st['bones'], 'worst': w, 'skinning_truth_max_error': sk['max_vertex_error_vs_source'],
    'joint_range_by_kind_deg': mc['joint_range_by_kind_deg'],
    'source_checks_worst': gc.get('worst'),
}
report['passed'] = not report['failures']
(OUT / 'validation-report.json').write_text(json.dumps(report, indent=1))
print('VALIDATION', 'PASS' if report['passed'] else 'FAIL', json.dumps(report['summary']), flush=True)
if report['failures']:
    sys.exit(1)
