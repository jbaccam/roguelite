"""Fresh re-import check of the Dragon exports. Run under Blender 5.2:

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python validate_exports.py

Imports exports/fbx/Dragon.fbx, both armature-only clip FBXs and
exports/glb/Dragon.glb into empty scenes and checks:
  - mesh / section count and the per-mesh triangle budget (< 20,000);
  - deform bone count, names and hierarchy against manifest.json;
  - every vertex weighted, <= 4 influences, weights normalised;
  - UVs present and textures loading with pixel data;
  - faceted normals preserved (corner normals differ across facet edges);
  - actions present with real bone motion;
  - scale and axes: dimensions in studs match the manifest, the head is at -Y.
Writes validation-report.json next to this script.
"""
import hashlib
import json
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
MAN = json.loads((HERE / 'manifest.json').read_text())
EXPECT_SECTIONS = sorted(v['object'] for v in MAN['sections'].values())
EXPECT_BONES = {b['name']: b['parent'] for b in MAN['bones']}
EXPECT_DIMS = MAN['rest_dimensions']
report = {'files': {}, 'checks': []}


def check(name, ok, **detail):
    report['checks'].append(dict(name=name, ok=bool(ok), **detail))
    print(('PASS ' if ok else 'FAIL ') + name, json.dumps(detail)[:400])


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest().upper()


def mesh_objs():
    return [o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.name.startswith('Icosphere')]


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
    return dict(vertices=len(o.data.vertices), unweighted=unweighted, over4=over4, not_normalised=unnorm,
                worst_sum_error=round(worst, 6))


def faceted_fraction(o):
    """Share of vertices whose corner normals disagree by more than 5 degrees."""
    me = o.data
    cn = me.corner_normals
    per_v = {}
    for li, loop in enumerate(me.loops):
        per_v.setdefault(loop.vertex_index, []).append(Vector(cn[li].vector))
    split = 0
    for vi, ns in per_v.items():
        n0 = ns[0]
        if any(n0.angle(n, 0.0) > 0.0873 for n in ns[1:]):
            split += 1
    return split / max(len(per_v), 1)


def world_bounds(objs):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


def texture_ok(o):
    imgs = []
    for slot in o.material_slots:
        m = slot.material
        if not m or not m.use_nodes:
            continue
        for n in m.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image:
                imgs.append(n.image)
    if not imgs:
        return False, 0
    img = imgs[0]
    return (img.size[0] > 0 and img.has_data), img.size[0]


def action_motion(arm, act):
    """Max angular change (deg) of any bone across the action's frame range."""
    arm.animation_data_create()
    arm.animation_data.action = act
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
    sc = bpy.context.scene
    rest = {}
    sc.frame_set(f0)
    for pb in arm.pose.bones:
        rest[pb.name] = pb.matrix.to_quaternion()
    worst = 0.0
    moving = set()
    for f in range(f0, f1 + 1, max(1, (f1 - f0) // 40)):
        sc.frame_set(f)
        for pb in arm.pose.bones:
            ang = rest[pb.name].rotation_difference(pb.matrix.to_quaternion()).angle * 57.2958
            ang = min(ang, 360.0 - ang)
            if ang > 1.0:
                moving.add(pb.name)
            worst = max(worst, ang)
    return worst, moving


# ------------------------------------------------------------------ FBX rest mesh + rig
fbx = HERE / 'exports' / 'fbx' / 'Dragon.fbx'
reset()
bpy.ops.import_scene.fbx(filepath=str(fbx), use_custom_normals=True, automatic_bone_orientation=False)
report['files']['fbx'] = {'path': 'exports/fbx/Dragon.fbx', 'bytes': fbx.stat().st_size, 'sha256': sha(fbx)}
meshes = mesh_objs()
arm = arm_obj()
names = sorted(o.name for o in meshes)
check('fbx: seven skinned section meshes', names == EXPECT_SECTIONS, found=names, expected=EXPECT_SECTIONS)
tri = {o.name: tris(o) for o in meshes}
check('fbx: every mesh < 20k triangles', all(v < 20000 for v in tri.values()), triangles=tri, total=sum(tri.values()))
bones = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones} if arm else {}
# the FBX importer may re-parent under an extra root; compare names and parents of expected bones
check('fbx: deform bone set matches manifest', set(bones) == set(EXPECT_BONES), count=len(bones),
      expected=len(EXPECT_BONES), missing=sorted(set(EXPECT_BONES) - set(bones))[:10],
      extra=sorted(set(bones) - set(EXPECT_BONES))[:10])
bad_parent = [n for n, p in EXPECT_BONES.items() if n in bones and bones[n] != p]
REST_Q = {b.name: b.matrix_local.to_quaternion() for b in arm.data.bones} if arm else {}
check('fbx: hierarchy matches manifest', not bad_parent, mismatched=bad_parent[:10])
check('fbx: no leaf / control bones exported', not any(n.endswith('_end') or n.startswith(('IK_', 'Pole_')) for n in bones))
ws = {o.name: weight_stats(o, arm) for o in meshes}
check('fbx: every vertex weighted, <=4 influences, normalised',
      all(s['unweighted'] == 0 and s['over4'] == 0 and s['not_normalised'] == 0 for s in ws.values()), stats=ws)
uv = {o.name: len(o.data.uv_layers) for o in meshes}
check('fbx: UVs present', all(v >= 1 for v in uv.values()), uv_layers=uv)
tex = {o.name: texture_ok(o) for o in meshes}
check('fbx: embedded textures load with pixel data', all(t[0] for t in tex.values()),
      textures={k: v[1] for k, v in tex.items()})
fac = {o.name: round(faceted_fraction(o), 3) for o in meshes}
check('fbx: faceted normals preserved (split corner normals)', all(v > 0.2 for v in fac.values()), split_vertex_fraction=fac)
lo, hi = world_bounds(meshes)
dims = [round(hi[i] - lo[i], 3) for i in range(3)]
check('fbx: dimensions in studs match manifest (1 unit = 1 stud, Z up after import)',
      all(abs(a - b) < 0.05 * max(b, 1) for a, b in zip(dims, EXPECT_DIMS)), imported=dims, manifest=EXPECT_DIMS)
if arm:
    head = arm.matrix_world @ arm.data.bones['Head'].head_local
    tail = arm.matrix_world @ arm.data.bones['TailTip'].head_local
    check('fbx: axes preserved (head toward -Y, tail toward +Y, up = +Z)', head.y < -3 and tail.y > 8 and head.z > 8,
          head=[round(v, 2) for v in head], tail_tip=[round(v, 2) for v in tail])

# ------------------------------------------------------------------ FBX clips
ATTACKS = ('FireBreath', 'TailWhip', 'FrontStomp')
for clip in ('ReferencePose', 'RigTest_ROM') + ATTACKS:
    p = HERE / 'exports' / 'fbx' / f'Dragon_{clip}.fbx'
    reset()
    bpy.ops.import_scene.fbx(filepath=str(p), automatic_bone_orientation=False)
    report['files'][f'fbx_{clip}'] = {'path': f'exports/fbx/Dragon_{clip}.fbx', 'bytes': p.stat().st_size, 'sha256': sha(p)}
    a = arm_obj()
    acts = list(bpy.data.actions)
    ok = a is not None and len(acts) >= 1
    worst, moving = action_motion(a, acts[0]) if ok else (0, set())
    check(f'fbx clip {clip}: armature-only, action present', ok and not mesh_objs(),
          bones=len(a.data.bones) if a else 0, actions=[x.name for x in acts])
    if clip == 'RigTest_ROM':
        check(f'fbx clip {clip}: real bone motion across the range', worst > 30 and len(moving) > 60,
              max_rotation_deg=round(worst, 1), bones_moving=len(moving))
    elif clip in ATTACKS:
        n = MAN['attacks'][clip]['frames'][1]
        frames = int(acts[0].frame_range[1] - acts[0].frame_range[0] + 1) if ok else 0
        check(f'fbx clip {clip}: attack motion present, frame count matches manifest',
              worst > 15 and len(moving) > 5 and abs(frames - n) <= 1,
              max_rotation_deg=round(worst, 1), bones_moving=len(moving), frames=frames, manifest_frames=n)
    else:
        # a held pose: compare frame 1 against the armature's rest orientation
        dev = 0.0
        if ok:
            a.animation_data.action = acts[0]
            bpy.context.scene.frame_set(int(acts[0].frame_range[0]))
            for pb in a.pose.bones:
                # compare with the rest orientation from the rest-mesh FBX (the clip file has no bind pose)
                r = REST_Q.get(pb.name, a.data.bones[pb.name].matrix_local.to_quaternion())
                ang = r.rotation_difference(pb.matrix.to_quaternion()).angle * 57.2958
                dev = max(dev, min(ang, 360.0 - ang))
        check(f'fbx clip {clip}: holds a pose that differs from rest', dev > 10, max_deviation_from_rest_deg=round(dev, 1))

# ------------------------------------------------------------------ GLB
glb = HERE / 'exports' / 'glb' / 'Dragon.glb'
reset()
bpy.ops.import_scene.gltf(filepath=str(glb))
report['files']['glb'] = {'path': 'exports/glb/Dragon.glb', 'bytes': glb.stat().st_size, 'sha256': sha(glb)}
meshes = mesh_objs()
arm = arm_obj()
check('glb: section meshes present', len(meshes) == len(EXPECT_SECTIONS), found=sorted(o.name for o in meshes))
check('glb: every mesh < 20k triangles', all(tris(o) < 20000 for o in meshes), triangles={o.name: tris(o) for o in meshes})
gb = {b.name for b in arm.data.bones} if arm else set()
check('glb: deform bones present', set(EXPECT_BONES) <= gb, count=len(gb), missing=sorted(set(EXPECT_BONES) - gb)[:10])
ws = {o.name: weight_stats(o, arm) for o in meshes}
check('glb: every vertex weighted, <=4 influences, normalised',
      all(s['unweighted'] == 0 and s['over4'] == 0 and s['not_normalised'] == 0 for s in ws.values()), stats=ws)
tex = {o.name: texture_ok(o) for o in meshes}
check('glb: textures load', all(t[0] for t in tex.values()), textures={k: v[1] for k, v in tex.items()})
acts = [a.name for a in bpy.data.actions]
need = ('ReferencePose', 'RigTest_ROM') + ATTACKS
check('glb: all five actions present', all(any(n in a for a in acts) for n in need), actions=acts)
rom = [a for a in bpy.data.actions if 'RigTest_ROM' in a.name]
if rom and arm:
    worst, moving = action_motion(arm, rom[0])
    check('glb: ROM action moves the bones', worst > 30 and len(moving) > 60, max_rotation_deg=round(worst, 1),
          bones_moving=len(moving))
lo, hi = world_bounds(meshes)
dims = [round(hi[i] - lo[i], 3) for i in range(3)]
check('glb: dimensions in studs match manifest', all(abs(a - b) < 0.05 * max(b, 1) for a, b in zip(dims, EXPECT_DIMS)),
      imported=dims, manifest=EXPECT_DIMS)

# ------------------------------------------------------------------ attack gameplay data (manifest)
atk = MAN.get('attacks', {})
check('manifest: three attacks with impact frames', all(n in atk and atk[n].get('impact_frame') for n in ATTACKS),
      impact_frames={n: atk.get(n, {}).get('impact_frame') for n in ATTACKS})
check('manifest: FireBreath origin + per-frame breath direction', bool(atk.get('FireBreath', {}).get('FireOrigin'))
      and len(atk.get('FireBreath', {}).get('breath', [])) > 5, frames=len(atk.get('FireBreath', {}).get('breath', [])))
arc = atk.get('TailWhip', {}).get('spade_arc', {})
check('manifest: TailWhip spade arc (sweep >= 200 deg)', 'start_angle_deg' in arc and 'radius_fit' in arc
      and arc.get('sweep_deg', 0) >= 200, start=arc.get('start_angle_deg'), end=arc.get('end_angle_deg'),
      sweep=arc.get('sweep_deg'), radius=arc.get('radius_fit'), pivot=arc.get('pivot'))
ip = atk.get('FrontStomp', {}).get('impact_points', {})
check('manifest: FrontStomp impact points for both front feet', 'Front_L' in ip and 'Front_R' in ip, points=ip)
drift = {n: max(max(d.values()) for d in atk[n]['planted_feet_drift'].values()) for n in ATTACKS if n in atk}
check('attacks: planted feet do not slide (evaluated rig, every frame, < 0.05 studs)',
      all(v < 0.05 for v in drift.values()), max_drift=drift)

# ------------------------------------------------------------------ game package (plans/BOSS_GAME_PACKAGE_SPEC.md)
import math as _m
GAME = HERE / 'exports' / 'game'
anim = json.loads((GAME / 'AnimationData.json').read_text(encoding='utf-8'))
bgd = json.loads((GAME / 'BossGameData.json').read_text(encoding='utf-8'))
studio = GAME / 'Dragon_Studio.fbx'
SMESH = json.loads((GAME / 'StudioMeshes.json').read_text(encoding='utf-8'))['meshes']
S_SWAP = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
POSES = [('rest', None, 0), ('Idle mid', 'Idle', 36), ('Walk mid', 'Walk', 20),
         ('FireBreath impact', 'FireBreath', MAN['attacks']['FireBreath']['impact_frame'] - 1),
         ('TailWhip impact', 'TailWhip', MAN['attacks']['TailWhip']['impact_frame'] - 1),
         ('FrontStomp impact', 'FrontStomp', MAN['attacks']['FrontStomp']['impact_frame'] - 1),
         ('Death end', 'Death', round(anim['clips']['Death']['duration'] * 24))]


def m12(v):
    """AnimationData 12 numbers -> Blender matrix_basis (undo cf = S@m@S)."""
    x, y, z, a, b, c, d, e, f, g, h, i = v
    M = Matrix(((a, b, c, x), (d, e, f, y), (g, h, i, z), (0, 0, 0, 1)))
    return S_SWAP @ M @ S_SWAP


def eval_world(obs):
    deps = bpy.context.evaluated_depsgraph_get()
    out = {}
    for o in obs:
        e = o.evaluated_get(deps)
        me = e.to_mesh()
        co = np.array([v.co[:] for v in me.vertices])
        M = np.array(o.matrix_world)
        out[o.name] = co @ M[:3, :3].T + M[:3, 3]
        e.to_mesh_clear()
    return out


# ---- source: the saved blend, rest + the same action frames
bpy.ops.wm.open_mainfile(filepath=str(HERE / 'Dragon.blend'))
src_rig = bpy.data.objects['Dragon_Rig']
src_obs = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('Dragon_') and o.name != 'RigBonesViz']
deform = {b.name for b in src_rig.data.bones if b.use_deform}
src_issues = {}
for o in src_obs:
    rel = src_rig.matrix_world.inverted() @ o.matrix_world
    groups = {g.index: g.name for g in o.vertex_groups}
    nondeform_groups = sorted(n for n in groups.values() if n not in deform)
    over4 = bad_norm = nd_verts = 0
    for v in o.data.vertices:
        ws = [(groups[g.group], g.weight) for g in v.groups if g.weight > 1e-6]
        if any(n not in deform for n, _ in ws):
            nd_verts += 1
        if len(ws) > 4:
            over4 += 1
        if abs(sum(w for _, w in ws) - 1) > 2e-3:
            bad_norm += 1
    src_issues[o.name] = {'object_matrix_dev': round(max(abs(rel[r][c] - (1 if r == c else 0)) for r in range(4) for c in range(4)), 6),
                          'parent_inverse_dev': round(max(abs(o.matrix_parent_inverse[r][c] - (1 if r == c else 0)) for r in range(4) for c in range(4)), 6),
                          'nondeform_groups': nondeform_groups, 'verts_on_nondeform': nd_verts, 'over4': over4, 'not_normalised': bad_norm}
rig_dev = max(abs(src_rig.matrix_world[r][c] - (1 if r == c else 0)) for r in range(4) for c in range(4))
check('source .blend: armature and every mesh object have identity transforms, no parent-inverse offset',
      rig_dev < 1e-6 and all(s['object_matrix_dev'] < 1e-6 and s['parent_inverse_dev'] < 1e-6 for s in src_issues.values()),
      armature_dev=rig_dev, meshes={k: [v['object_matrix_dev'], v['parent_inverse_dev']] for k, v in src_issues.items()})
check('source .blend: weights only on exported deform bones, <= 4 influences, normalised',
      all(not s['nondeform_groups'] and s['verts_on_nondeform'] == 0 and s['over4'] == 0 and s['not_normalised'] == 0
          for s in src_issues.values()), details=src_issues)
src_rest_local = {b.name: b.matrix_local.copy() for b in src_rig.data.bones if b.use_deform}
src_pose = {}
for label, clip, idx in POSES:
    if clip is None:
        src_rig.animation_data.action = None
        for pb in src_rig.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
        bpy.context.scene.frame_set(1)
    else:
        src_rig.animation_data.action = bpy.data.actions[clip]
        bpy.context.scene.frame_set(idx + 1)
    bpy.context.view_layer.update()
    src_pose[label] = eval_world(src_obs)
src_rig.animation_data.action = None

# ---- the Studio FBX, fresh
reset()
bpy.ops.import_scene.fbx(filepath=str(studio), use_custom_normals=True, automatic_bone_orientation=False)
report['files']['studio_fbx'] = {'path': 'exports/game/Dragon_Studio.fbx', 'bytes': studio.stat().st_size, 'sha256': sha(studio)}
meshes = mesh_objs()
arm = arm_obj()
secs = sorted(o.name for o in meshes)
check('studio fbx: mesh objects as listed in StudioMeshes.json (Dragon_<Section>[_<Piece>])', secs == sorted(SMESH), found=secs)
_bn = {b.name for b in arm.data.bones} if arm else set()
check('studio fbx: no mesh object name equals a bone name (Roblox merges them)', not (set(secs) & _bn), clashes=sorted(set(secs) & _bn))
dims = {}
for o in meshes:
    co = np.array([v.co[:] for v in o.data.vertices])
    M = np.array(arm.matrix_world.inverted() @ o.matrix_world)
    co = co @ M[:3, :3].T + M[:3, 3]
    dims[o.name] = [round(float(x), 3) for x in (co.max(0) - co.min(0))]
check('studio fbx: every MeshPart under the Roblox size cap (2048 at the x100 import = 20.48 studs per axis)',
      all(max(d) < 20.48 for d in dims.values()), dims=dims)
check('studio fbx: every mesh < 20k triangles', all(tris(o) < 20000 for o in meshes), triangles={o.name: tris(o) for o in meshes})
rel_dev = {o.name: round(max(abs((arm.matrix_world.inverted() @ o.matrix_world)[r][c] - (1 if r == c else 0))
                             for r in range(4) for c in range(4)), 6) for o in meshes}
check('studio fbx: every mesh object is identity relative to the armature', all(v < 1e-4 for v in rel_dev.values()), deviation=rel_dev)
names = {b.name for b in arm.data.bones} if arm else set()
check('studio fbx: bone names match AnimationData.json', names == set(anim['bones']), count=len(names),
      missing=sorted(set(anim['bones']) - names)[:8], extra=sorted(names - set(anim['bones']))[:8])
par_bad = [b.name for b in arm.data.bones if (b.parent.name if b.parent else None) != anim['bones'].get(b.name, {}).get('parent', '?')]
check('studio fbx: bone parents match AnimationData.json', not par_bad, mismatched=par_bad[:10])
rest_dev = max(max(abs(a - b) for ra, rb in zip(arm.data.bones[n].matrix_local, src_rest_local[n]) for a, b in zip(ra, rb))
               for n in names)
check('studio fbx: bone rests equal the source rig (bind pose = rest; FBX float precision)', rest_dev < 1e-3, max_matrix_diff=round(rest_dev, 7))
mats = {}
for o in meshes:
    m = o.material_slots[0].material if o.material_slots else None
    img = None
    if m and m.use_nodes:
        img = next((n.image for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image), None)
    mats[o.name] = (m.name if m else None, img.size[0] if img else 0, bool(img and img.has_data))
check('studio fbx: materials Dragon_<Section> with 1024 delivery textures loading',
      all(v[0] == SMESH[k]['material'] and v[1] == 1024 and v[2] for k, v in mats.items()), materials=mats)
check('studio fbx: no animation, no control bones', not bpy.data.actions and not any(n.startswith(('IK_', 'Pole_')) for n in names),
      actions=[a.name for a in bpy.data.actions])
fbm = sorted(p.name for p in (GAME / 'Dragon_Studio.fbm').glob('*.png'))
check('studio fbx: delivery PNGs copied into Dragon_Studio.fbm', len(fbm) == len(MAN['sections']), files=fbm)

# vertex correspondence piece -> source section, by rest position
from mathutils import kdtree
fbx_rest = eval_world(meshes)
maps = {}
for o in meshes:
    sec_obj = f"Dragon_{SMESH[o.name]['section']}"
    S = src_pose['rest'][sec_obj]
    kd = kdtree.KDTree(len(S))
    for i, p in enumerate(S):
        kd.insert(p, i)
    kd.balance()
    idx, dist = [], 0.0
    for p in fbx_rest[o.name]:
        co, j, d = kd.find(p)
        idx.append(j)
        dist = max(dist, d)
    maps[o.name] = (sec_obj, np.array(idx), dist)
rest_match = {k: round(v[2], 6) for k, v in maps.items()}
check('studio fbx: rest vertices equal the source evaluated rest mesh (< 0.01 stud)', max(rest_match.values()) < 0.01,
      max_deviation=rest_match)
head = fbx_rest['Dragon_Head']
report['head_bounds_armature_space'] = {'min': [round(float(x), 3) for x in head.min(0)], 'max': [round(float(x), 3) for x in head.max(0)]}
neck_tip = np.array(src_rest_local['Neck_3'].to_translation()) + (np.array(src_rest_local['Head'].to_translation()) - np.array(src_rest_local['Neck_3'].to_translation()))
check('studio fbx: Dragon_Head sits on the neck (its bounds contain the Neck_3 -> Head joint)',
      all(head.min(0)[k] - 0.5 <= neck_tip[k] <= head.max(0)[k] + 0.5 for k in range(3)),
      head_min=report['head_bounds_armature_space']['min'], head_max=report['head_bounds_armature_space']['max'],
      head_joint=[round(float(x), 3) for x in neck_tip])


def pose_imported(clip, idx):
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    if clip is not None:
        tr = anim['clips'][clip]['frames'][idx]['transforms']
        for pb in arm.pose.bones:
            pb.matrix_basis = m12(tr[pb.name])
    bpy.context.view_layer.update()


def compare(tag):
    table = {}
    for label, clip, idx in POSES:
        pose_imported(clip, idx)
        got = eval_world(meshes)
        row = {}
        for o in meshes:
            sec_obj, idxs, _ = maps[o.name]
            row[o.name] = round(float(np.abs(got[o.name] - src_pose[label][sec_obj][idxs]).max()), 5)
        table[label] = row
    return table


dev_table = compare('as exported')
worst = max(max(r.values()) for r in dev_table.values())
check('studio fbx posed with AnimationData == source .blend posed with the actions (< 0.02 stud, every vertex)',
      worst < 0.02, worst=worst, table=dev_table)
# emulate Roblox: keep the 4 strongest influences per vertex and renormalise
changed = 0
for o in meshes:
    gname = {g.index: g for g in o.vertex_groups}
    for v in o.data.vertices:
        ws = sorted([(g.weight, g.group) for g in v.groups if g.weight > 0], reverse=True)
        keep = ws[:4]
        tot = sum(w for w, _ in keep) or 1.0
        for w, gi in ws[4:]:
            gname[gi].remove([v.index])
            changed += 1
        for w, gi in keep:
            if abs(w / tot - w) > 1e-7:
                gname[gi].add([v.index], w / tot, 'REPLACE')
                changed += 1
dev_table4 = compare('4 influences')
worst4 = max(max(r.values()) for r in dev_table4.values())
check('same comparison after Roblox 4-influence truncation + renormalisation (< 0.02 stud)', worst4 < 0.02,
      worst=worst4, weights_changed=changed)
report['studio_pose_deviation'] = {'as_exported': dev_table, 'roblox_4_influences': dev_table4}
print('DEVIATION TABLE (max |fbx - source| per mesh, studs)')
print('pose'.ljust(20) + ' '.join(k.replace('Dragon_', '')[:14].rjust(14) for k in sorted(dims)))
for label, row in dev_table.items():
    print(label.ljust(20) + ' '.join(f'{row[k]:14.5f}' for k in sorted(dims)))

# ---- Workbench sheet of the re-imported FBX in those poses (front 3/4)
sc = bpy.context.scene
cam_d = bpy.data.cameras.new('CheckCam')
cam_d.lens = 35
cam = bpy.data.objects.new('CheckCam', cam_d)
sc.collection.objects.link(cam)
sc.camera = cam
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'STUDIO'
sh.color_type = 'TEXTURE'
sh.show_shadows = False
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 520, 390, 100
sc.render.image_settings.file_format = 'PNG'
world = bpy.data.worlds.new('W')
world.color = (0.2, 0.2, 0.23)
sc.world = world
c = Vector((0.0, 6.0, 6.0))
d = Vector((0.8, -0.85, 0.34)).normalized()
cam.location = c + d * 52
cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
tmp = HERE / 'previews' / '_studio_tiles'
tmp.mkdir(exist_ok=True)
tiles = []
for label, clip, idx in POSES:
    pose_imported(clip, idx)
    p = tmp / f'{len(tiles):02d}.png'
    sc.render.filepath = str(p)
    bpy.ops.render.render(write_still=True)
    tiles.append((label, p))


def _load(p):
    img = bpy.data.images.load(str(p))
    a = np.zeros(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(a)
    a = a.reshape(img.size[1], img.size[0], 4)[::-1, :, :3].copy()
    bpy.data.images.remove(img)
    return a


def _save(arr, path):
    h, w = arr.shape[:2]
    img = bpy.data.images.new('sheet', w, h, alpha=False)
    rgba = np.concatenate([np.clip(arr[::-1], 0, 1), np.ones((h, w, 1))], 2)
    img.pixels.foreach_set(np.ascontiguousarray(rgba, np.float32).ravel())
    img.filepath_raw = str(path)
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


ims = [_load(p) for _, p in tiles]
th, tw = ims[0].shape[:2]
cols, gap = 4, 6
rows = (len(ims) + cols - 1) // cols
sheet = np.full((rows * th + (rows + 1) * gap, cols * tw + (cols + 1) * gap, 3), 0.06)
for i, im in enumerate(ims):
    r, cc = divmod(i, cols)
    sheet[gap + r * (th + gap):gap + r * (th + gap) + th, gap + cc * (tw + gap):gap + cc * (tw + gap) + tw] = im
_save(sheet, HERE / 'previews' / 'StudioFBX_PoseCheck.png')
_save(ims[0], HERE / 'previews' / 'StudioFBX_RestCheck.png')
report['studio_pose_sheet'] = {'file': 'previews/StudioFBX_PoseCheck.png', 'tiles': [t[0] for t in tiles], 'cols': cols,
                               'tile': [tw, th]}
for _, p in tiles:
    p.unlink()
tmp.rmdir()
need = ['Idle', 'Walk', 'Hit', 'Death', 'FireBreath', 'TailWhip', 'FrontStomp']
check('AnimationData: id, fps and every required clip', anim['id'] == 'dragon' and anim['fps'] == 24 and all(c in anim['clips'] for c in need),
      clips=list(anim['clips']))
bad = {}
for cname, c in anim['clips'].items():
    n = round(c['duration'] * 24) + 1
    nan = any(not _m.isfinite(x) for fr in c['frames'] for tr in fr['transforms'].values() for x in tr)
    closes = True
    if c['loop']:
        a, z = c['frames'][0]['transforms'], c['frames'][-1]['transforms']
        closes = max(abs(p - q) for bn in a for p, q in zip(a[bn], z[bn])) < 1e-4
    bones_ok = all(set(fr['transforms']) == set(anim['bones']) for fr in c['frames'])
    if len(c['frames']) != n or nan or not closes or not bones_ok:
        bad[cname] = {'frames': len(c['frames']), 'expected': n, 'nan': nan, 'loop_closes': closes, 'bones_ok': bones_ok}
check('AnimationData: frame counts, no NaNs, loops close, every bone in every frame', not bad, problems=bad)
idle0 = anim['clips']['Idle']['frames'][0]['transforms']
dev = {}
for a in ('FireBreath', 'TailWhip', 'FrontStomp'):
    fr = anim['clips'][a]['frames']
    dev[a] = round(max(max(abs(p - q) for p, q in zip(idle0[bn], fr[i]['transforms'][bn])) for i in (0, -1) for bn in idle0), 6)
check('attacks start and end on the Idle start pose (< 1e-3)', all(v < 1e-3 for v in dev.values()), max_difference=dev)
dz = bgd['checks']['deathGround']['min_vertex_z']
check('Death: no vertex below z = -0.05', dz >= -0.05, min_vertex_z=dz)
wd = bgd['checks']['walkPlantedDrift']
check('Walk: planted feet follow the ground-locked path (< 0.05 studs)', max(wd.values()) < 0.05, drift=wd,
      stride=anim['motion'])
atk = bgd['attacks']
ok = all(k in atk for k in ('FireBreath', 'TailWhip', 'FrontStomp')) and 'FireOrigin' in atk['FireBreath']['points']     and 'SpadeTip' in atk['TailWhip']['points'] and 'arc' in atk['TailWhip']['points']['SpadeTip']     and {'LeftFrontImpact', 'RightFrontImpact'} <= set(atk['FrontStomp']['points'])     and all(atk[k]['warnStart'] <= atk[k]['impact'] <= atk[k]['activeEnd'] <= atk[k]['recoveryEnd'] <= atk[k]['duration'] + 1e-6 for k in atk)
check('BossGameData: required points and ordered timings', ok,
      timings={k: [v['warnStart'], v['impact'], v['activeEnd'], v['recoveryEnd'], v['duration']] for k, v in atk.items()})

report['summary'] = {'passed': sum(c['ok'] for c in report['checks']), 'total': len(report['checks'])}
(HERE / 'validation-report.json').write_text(json.dumps(report, indent=2))
print('SUMMARY', report['summary'])
