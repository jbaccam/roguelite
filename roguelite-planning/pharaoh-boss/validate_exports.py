"""Fresh re-import check of the Pharaoh exports. Run under Blender 5.2:

    blender -b --factory-startup --python validate_exports.py

Imports exports/fbx/Pharaoh.fbx, both armature-only clip FBXs, and
exports/glb/Pharaoh.glb into empty scenes. It checks:
  - mesh/section counts and per-mesh triangle budget (< 20,000);
  - bone count, names and hierarchy against manifest.json (deform bones);
  - every vertex weighted, <= 4 influences, weights normalised;
  - UVs present and textures loading with pixel data;
  - faceted (split) normals preserved;
  - actions present with real bone motion;
  - scale and axes: standing height in studs and the front facing -Y.

Writes validation-report.json next to this script.
"""
import bpy, json, math, hashlib
from pathlib import Path
from mathutils import Vector

HERE = Path(__file__).resolve().parent
MAN = json.loads((HERE / 'manifest.json').read_text())
EXPECT_SECTIONS = sorted(v['object'] for v in MAN['sections'].values())
EXPECT_BONES = {b['name']: b['parent'] for b in MAN['bones'] if b['deform']}
REST_TOP = MAN['dimensions']['height_rest_top']
report = {'files': {}, 'checks': []}


def check(name, ok, **detail):
    report['checks'].append(dict(name=name, ok=bool(ok), **detail))
    print(('PASS ' if ok else 'FAIL ') + name, json.dumps(detail)[:300])


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()


def mesh_objs():
    # the glTF importer adds an 'Icosphere' bone-display shape; it is not content
    return [o for o in bpy.context.scene.objects if o.type == 'MESH'
            and not o.name.startswith('Icosphere')]


def arm_obj():
    a = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
    return a[0] if a else None


def tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def weight_stats(o, arm):
    bones = set(b.name for b in arm.data.bones) if arm else set()
    names = {vg.index: vg.name for vg in o.vertex_groups}
    unweighted = over4 = unnorm = 0
    worst = 0.0
    for v in o.data.vertices:
        ws = [g.weight for g in v.groups if g.weight > 1e-6 and names.get(g.group) in bones]
        if not ws:
            unweighted += 1
            continue
        if len(ws) > 4:
            over4 += 1
        s = sum(ws)
        worst = max(worst, abs(1 - s))
        if abs(1 - s) > 2e-3:
            unnorm += 1
    return dict(vertices=len(o.data.vertices), unweighted=unweighted, over4=over4,
                not_normalised=unnorm, worst_sum_error=round(worst, 6))


def split_normal_fraction(o):
    """Share of vertices whose corner normals disagree by more than 5 degrees:
    > 0 means per-face (faceted/soft-faceted) normals survived the round trip."""
    me = o.data
    try:
        lnorms = [l.normal.copy() for l in me.loops]
    except Exception:
        lnorms = [Vector(cn.vector) for cn in me.corner_normals]
    by_v = {}
    for l, n in zip(me.loops, lnorms):
        by_v.setdefault(l.vertex_index, []).append(n)
    split = 0
    for ns in by_v.values():
        if any(ns[0].angle(n, 0) > math.radians(5) for n in ns[1:]):
            split += 1
    return round(split / max(1, len(by_v)), 4)


def texture_status(objs):
    imgs = set()
    for o in objs:
        for slot in o.material_slots:
            m = slot.material
            if m and m.node_tree:
                for nd in m.node_tree.nodes:
                    if nd.type == 'TEX_IMAGE' and nd.image:
                        imgs.add(nd.image)
    out = []
    for im in imgs:
        ok = im.size[0] > 0 and im.size[1] > 0 and len(im.pixels) > 0
        out.append(dict(name=im.name, size=list(im.size), has_pixels=ok))
    return out


def action_motion(act, arm):
    moving = set()
    for fc in act.fcurves if hasattr(act, 'fcurves') else []:
        vals = [k.co[1] for k in fc.keyframe_points]
        if vals and max(vals) - min(vals) > 1e-3:
            moving.add(fc.data_path.split('"')[1] if '"' in fc.data_path else fc.data_path)
    if not moving and arm is not None:
        # layered (5.x) actions: sample the pose instead
        arm.animation_data_create()
        arm.animation_data.action = act
        sc = bpy.context.scene
        f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
        snaps = {}
        for f in range(f0, f1 + 1, 6):
            sc.frame_set(f)
            for pb in arm.pose.bones:
                snaps.setdefault(pb.name, []).append(pb.matrix.copy())
        for n, ms in snaps.items():
            if any((m.to_translation() - ms[0].to_translation()).length > 1e-3 or
                   m.to_quaternion().rotation_difference(ms[0].to_quaternion()).angle > 1e-3
                   for m in ms[1:]):
                moving.add(n)
    return sorted(moving)


# ------------------------------------------------------------------ FBX mesh
fbx = HERE / 'exports' / 'fbx' / 'Pharaoh.fbx'
reset()
bpy.ops.import_scene.fbx(filepath=str(fbx))
report['files']['fbx'] = dict(path=str(fbx.relative_to(HERE)), sha256=sha(fbx))
ms = mesh_objs()
arm = arm_obj()
names = sorted(o.name for o in ms)
check('fbx: six mesh sections', len(ms) == len(EXPECT_SECTIONS) and names == EXPECT_SECTIONS,
      found=names)
check('fbx: every mesh < 20,000 triangles', all(tris(o) < 20000 for o in ms),
      triangles={o.name: tris(o) for o in ms}, total=sum(tris(o) for o in ms))
bones = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones} if arm else {}
check('fbx: armature present', arm is not None)
check('fbx: bone count/names = deform bones in manifest', set(bones) == set(EXPECT_BONES),
      count=len(bones), expected=len(EXPECT_BONES),
      missing=sorted(set(EXPECT_BONES) - set(bones)), extra=sorted(set(bones) - set(EXPECT_BONES)))
check('fbx: hierarchy matches', all(bones.get(k) == v for k, v in EXPECT_BONES.items()),
      mismatches=[k for k, v in EXPECT_BONES.items() if bones.get(k) != v])
check('fbx: no leaf/end bones', not any(n.endswith('_end') or n.endswith('.end') for n in bones))
ws = {o.name: weight_stats(o, arm) for o in ms}
check('fbx: every vertex weighted, <=4 influences, normalised',
      all(v['unweighted'] == 0 and v['over4'] == 0 and v['not_normalised'] == 0
          for v in ws.values()), stats=ws)
check('fbx: UVs present on every mesh', all(len(o.data.uv_layers) > 0 for o in ms),
      uv_layers={o.name: len(o.data.uv_layers) for o in ms})
tx = texture_status(ms)
check('fbx: embedded textures load', len(tx) >= len(ms) and all(t['has_pixels'] for t in tx),
      textures=tx)
sn = {o.name: split_normal_fraction(o) for o in ms}
check('fbx: faceted split normals preserved', all(v > 0.2 for v in sn.values()),
      split_vertex_fraction=sn)
allz = [o.matrix_world @ v.co for o in ms for v in o.data.vertices]
top = max(v.z for v in allz)
bot = min(v.z for v in allz)
check('fbx: scale/axes (rest top height in studs, feet on Z=0)',
      abs(top - REST_TOP) < 0.05 and abs(bot) < 0.25, top=round(top, 3), bottom=round(bot, 3),
      expected_top=REST_TOP)
# the face (eye glow) must sit at -Y (front)
eye = [o for o in ms if o.name.endswith('EyeGlow')]
if eye:
    ey = sum((eye[0].matrix_world @ v.co for v in eye[0].data.vertices), Vector()) / len(eye[0].data.vertices)
    check('fbx: character faces -Y', ey.y < -0.8, eye_centre=[round(c, 3) for c in ey])

# ------------------------------------------------------------------ FBX clips
for clip in ('ReferencePose', 'RigTest_ROM'):
    p = HERE / 'exports' / 'fbx' / f'Pharaoh_{clip}.fbx'
    reset()
    bpy.ops.import_scene.fbx(filepath=str(p))
    report['files'][f'fbx_{clip}'] = dict(path=str(p.relative_to(HERE)), sha256=sha(p))
    a = arm_obj()
    acts = list(bpy.data.actions)
    check(f'clip {clip}: armature only', a is not None and not mesh_objs(),
          meshes=len(mesh_objs()))
    check(f'clip {clip}: bones match', a is not None and
          set(b.name for b in a.data.bones) == set(EXPECT_BONES))
    if clip == 'ReferencePose':
        # a held pose: check it differs from rest (both upper arms rotated back)
        a.animation_data.action = acts[0]
        bpy.context.scene.frame_set(int(acts[0].frame_range[0]))
        rot = {pb.name: round(math.degrees(pb.matrix_basis.to_quaternion().angle), 3)
               for pb in a.pose.bones if pb.matrix_basis.to_quaternion().angle > 1e-3}
        check(f'clip {clip}: action present, pose differs from rest (arms)',
              len(acts) >= 1 and {'LeftUpperArm', 'RightUpperArm'} <= set(rot),
              actions=[x.name for x in acts], frame_range=[list(x.frame_range) for x in acts],
              rotated_bones_deg=rot)
    else:
        mv = action_motion(acts[0], a) if acts else []
        check(f'clip {clip}: action present with bone motion', len(acts) >= 1 and len(mv) >= 40,
              actions=[x.name for x in acts],
              frame_range=[list(x.frame_range) for x in acts], moving_bones=len(mv))

# ------------------------------------------------------------------ GLB
glb = HERE / 'exports' / 'glb' / 'Pharaoh.glb'
reset()
bpy.ops.import_scene.gltf(filepath=str(glb))
report['files']['glb'] = dict(path=str(glb.relative_to(HERE)), sha256=sha(glb))
ms = mesh_objs()
arm = arm_obj()
check('glb: mesh sections', len(ms) == len(EXPECT_SECTIONS), found=sorted(o.name for o in ms))
check('glb: skinned to one armature', arm is not None and
      all(any(m.type == 'ARMATURE' for m in o.modifiers) for o in ms))
gb = set(b.name for b in arm.data.bones) if arm else set()
check('glb: deform bones present', set(EXPECT_BONES) <= gb, count=len(gb),
      missing=sorted(set(EXPECT_BONES) - gb))
acts = {a.name: a for a in bpy.data.actions}
have = [n for n in acts if 'ReferencePose' in n or 'RigTest_ROM' in n]
check('glb: both actions present', any('ReferencePose' in n for n in acts) and
      any('RigTest_ROM' in n for n in acts), actions=sorted(acts))
rom = [a for n, a in acts.items() if 'RigTest_ROM' in n]
if rom:
    mv = action_motion(rom[0], arm)
    check('glb: ROM action moves bones', len(mv) >= 40, moving_bones=len(mv))
ws = {o.name: weight_stats(o, arm) for o in ms}
check('glb: weights valid', all(v['unweighted'] == 0 and v['over4'] == 0 for v in ws.values()),
      stats=ws)
tx = texture_status(ms)
check('glb: textures load', len(tx) >= 1 and all(t['has_pixels'] for t in tx), textures=tx)
if arm:
    arm.animation_data_create()
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()
    bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
zs = []
for o in ms:
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    zs += [(oe.matrix_world @ v.co).z for v in me.vertices]
    oe.to_mesh_clear()
check('glb: scale (rest top height in studs)', abs(max(zs) - REST_TOP) < 0.05,
      top=round(max(zs), 3), expected_top=REST_TOP)

# ------------------------------------------------------------------ GAME PACKAGE
GAME = HERE / 'exports' / 'game'
studio_fbx = GAME / 'Pharaoh_Studio.fbx'
anim = json.loads((GAME / 'AnimationData.json').read_text())
gdata = json.loads((GAME / 'BossGameData.json').read_text())
reset()
bpy.ops.import_scene.fbx(filepath=str(studio_fbx))
report['files']['studio_fbx'] = dict(path=str(studio_fbx.relative_to(HERE)), sha256=sha(studio_fbx))
ms = mesh_objs()
arm = arm_obj()
secs = sorted(o.name for o in ms)
check('studio fbx: one mesh per section, named Pharaoh_<Section>',
      secs == sorted('Pharaoh_' + s for s in ['Bandages', 'Body', 'EyeGlow', 'Head', 'Staff', 'Waist']),
      found=secs)
bone_names = set(bb.name for bb in arm.data.bones) if arm else set()
check('studio fbx: no mesh object name equals a bone name (Roblox merges them)',
      not (set(secs) & bone_names), collisions=sorted(set(secs) & bone_names))
check('studio fbx: every mesh < 20,000 triangles', all(tris(o) < 20000 for o in ms),
      triangles={o.name: tris(o) for o in ms})
check('studio fbx: materials Pharaoh_<Section>', all(
    [s.material.name.split('.')[0] for s in o.material_slots] == [o.name.split('.')[0]] for o in ms),
      materials={o.name: [s.material.name for s in o.material_slots] for o in ms})
tx = texture_status(ms)
check('studio fbx: 1024 base-colour maps load', len(tx) >= 6 and all(
    t['has_pixels'] and t['size'] == [1024, 1024] for t in tx), textures=tx)
fbm = sorted(p.name for p in (GAME / 'Pharaoh_Studio.fbm').glob('*.png'))
check('studio fbx: textures copied to Pharaoh_Studio.fbm', len(fbm) == 6, files=fbm)
sb = {bb.name: (bb.parent.name if bb.parent else None) for bb in arm.data.bones} if arm else {}
check('studio fbx: bones match AnimationData (names + parents)',
      sb == {n: v['parent'] for n, v in anim['bones'].items()}, count=len(sb),
      missing=sorted(set(anim['bones']) - set(sb)), extra=sorted(set(sb) - set(anim['bones'])))
check('studio fbx: no animation', len(bpy.data.actions) == 0, actions=[a.name for a in bpy.data.actions])
ws = {o.name: weight_stats(o, arm) for o in ms}
check('studio fbx: weights valid', all(v['unweighted'] == 0 and v['over4'] == 0 and
                                       v['not_normalised'] == 0 for v in ws.values()), stats=ws)
need = ['Idle', 'Walk', 'Hit', 'Death', 'CursedBolts', 'TombEruption']
check('AnimationData: id/fps/clips', anim['id'] == 'pharaoh' and anim['fps'] == 24 and
      all(c in anim['clips'] for c in need), clips=sorted(anim['clips']))
clipres = {}
for name, c in anim['clips'].items():
    n = len(c['frames'])
    exp = round(c['duration'] * 24) + 1
    nan = any(math.isnan(x) or math.isinf(x) for fr in c['frames'] for v in fr['transforms'].values()
              for x in v)
    bones_ok = all(set(fr['transforms']) == set(anim['bones']) for fr in c['frames'])
    loop_err = None
    if c['loop']:
        a, z = c['frames'][0]['transforms'], c['frames'][-1]['transforms']
        loop_err = max(abs(x - y) for k in a for x, y in zip(a[k], z[k]))
    clipres[name] = dict(frames=n, expected=exp, nan=nan, bonesComplete=bones_ok, loop=c['loop'],
                         loopError=loop_err)
check('AnimationData: frame counts = duration*24+1, no NaN, all bones, loops close',
      all(r['frames'] == r['expected'] and not r['nan'] and r['bonesComplete'] and
          (not r['loop'] or r['loopError'] < 1e-6) for r in clipres.values()), clips=clipres)
check('AnimationData: motion has strideLength and nominalSpeed',
      anim['motion'].get('strideLength', 0) > 0 and anim['motion'].get('nominalSpeed', 0) > 0,
      motion=anim['motion'])
att = gdata['attacks']
check('BossGameData: CursedBolts BoltOrigin + release direction, TombEruption StaffImpact',
      'BoltOrigin' in att['CursedBolts']['points'] and 'directionAtImpact' in att['CursedBolts']
      and 'StaffImpact' in att['TombEruption']['points'] and
      all(0 <= a['warnStart'] <= a['impact'] <= a['activeEnd'] <= a['recoveryEnd'] <= a['duration']
          + 1e-6 for a in att.values()),
      timings={k: [v['warnStart'], v['impact'], v['activeEnd'], v['recoveryEnd'], v['duration']]
               for k, v in att.items()})

report['summary'] = dict(passed=sum(c['ok'] for c in report['checks']),
                         failed=sum(not c['ok'] for c in report['checks']),
                         blender=bpy.app.version_string)
(HERE / 'validation-report.json').write_text(json.dumps(report, indent=2))
print('VALIDATION', json.dumps(report['summary']))
