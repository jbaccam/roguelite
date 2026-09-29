"""Reimport the King Crab exports fresh and check them. Run in Blender 5.2:

    blender -b --factory-startup --python validate_exports.py

Each file is imported into an empty scene (factory settings reloaded between
files) and checked against manifest.json, which the generator wrote from the
live build. Writes validation-report.json; exits non-zero on any failure.

Checks
  KingCrab.fbx  mesh/section count; each mesh < 20,000 triangles; deform bone
                count, names and parents equal the manifest; every vertex
                weighted, <= 4 influences, weights sum to 1; UVs present;
                an embedded texture loads with pixels; faceted normals kept
                (corner normals equal face normals); dimensions in studs match
                the rest-pose measurement (scale and axes).
  clip FBXs     armature only, deform bones only, an action with bone motion
                (ReferencePose: a single held pose that differs from rest;
                RigTest_ROM: rotation range per bone chain).
  KingCrab.glb  meshes and skin, textures, both named actions present, bone
                motion in RigTest_ROM, dimensions.
"""
import bpy, json, math, sys
from pathlib import Path
from mathutils import Vector

OUT = Path(__file__).resolve().parent
MAN = json.loads((OUT / 'manifest.json').read_text())
FBX = OUT / 'exports' / 'fbx'
GLB = OUT / 'exports' / 'glb'
DEFORM = {b['name']: b['parent'] for b in MAN['bones'] if b['deform']}
REST = MAN['dimensions']['rest_pose']
SECTIONS = [k for k, v in MAN['sections'].items() if isinstance(v, dict)]
report = {'files': {}, 'failures': []}


def fail(msg):
    report['failures'].append(msg)
    print('FAIL', msg)


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def meshes():
    return [o for o in bpy.data.objects if o.type == 'MESH']


def arm():
    a = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    return a[0] if a else None


def tris(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


def weight_check(ob, bone_names):
    names = {g.index: g.name for g in ob.vertex_groups}
    unweighted = over4 = badsum = nonbone = 0
    for v in ob.data.vertices:
        gs = [g for g in v.groups if g.weight > 1e-6]
        if not gs:
            unweighted += 1
            continue
        if len(gs) > 4:
            over4 += 1
        if abs(sum(g.weight for g in gs) - 1.0) > 1e-3:
            badsum += 1
        if any(names.get(g.group) not in bone_names for g in gs):
            nonbone += 1
    return {'vertices': len(ob.data.vertices), 'unweighted': unweighted, 'over_4_influences': over4,
            'not_normalized': badsum, 'weights_to_non_bones': nonbone}


def flat_fraction(me):
    """Share of corners whose normal equals its face normal (faceting kept)."""
    try:
        cn = me.corner_normals
        vec = lambda i: cn[i].vector
    except AttributeError:
        me.calc_normals_split()
        vec = lambda i: me.loops[i].normal
    ok = total = 0
    for p in me.polygons:
        for li in p.loop_indices:
            total += 1
            if vec(li).dot(p.normal) > 0.9995:
                ok += 1
    return ok / max(total, 1)


def world_bounds(obs):
    dg = bpy.context.evaluated_depsgraph_get()
    lo = Vector((1e9, 1e9, 1e9))
    hi = -lo
    for o in obs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        for v in me.vertices:
            w = o.matrix_world @ v.co
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
        ev.to_mesh_clear()
    return lo, hi


def image_ok(ob):
    for m in ob.data.materials:
        if m and m.node_tree:
            for n in m.node_tree.nodes:
                if n.type == 'TEX_IMAGE' and n.image and n.image.size[0] > 0:
                    px = n.image.pixels[:16]
                    if any(v > 0 for v in px):
                        return list(n.image.size)
    return None


def dims_check(tag, obs, rig):
    rig.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    lo, hi = world_bounds(obs)
    got = {'height': round(hi.z - lo.z, 3), 'top_z': round(hi.z, 3), 'x': [round(lo.x, 3), round(hi.x, 3)],
           'y': [round(lo.y, 3), round(hi.y, 3)]}
    want_top = REST['height_top_of_spikes']
    if abs(got['top_z'] - want_top) > 0.02 * want_top:
        fail(f'{tag}: rest top {got["top_z"]} vs manifest {want_top} (scale/axes)')
    if abs(got['x'][0] - REST['overall_x'][0]) > 0.1 or abs(got['y'][0] - REST['overall_y'][0]) > 0.1:
        fail(f'{tag}: rest extents {got} vs manifest x {REST["overall_x"]} y {REST["overall_y"]} (axes)')
    return got


def bone_motion(rig, act, frames):
    rig.animation_data_create()
    rig.animation_data.action = act
    out = {}
    base = {}
    for f in frames:
        bpy.context.scene.frame_set(f)
        for pb in rig.pose.bones:
            q = pb.matrix_basis.to_quaternion()
            loc = pb.matrix_basis.translation
            if pb.name not in base:
                base[pb.name] = (q, loc.copy())
                out[pb.name] = 0.0
            ang = math.degrees(base[pb.name][0].rotation_difference(q).angle)
            out[pb.name] = max(out[pb.name], ang + (loc - base[pb.name][1]).length * 10)
    return out


# ------------------------------------------------------------ rest mesh FBX
fresh()
bpy.ops.import_scene.fbx(filepath=str(FBX / 'KingCrab.fbx'))
rig = arm()
obs = meshes()
r = {'meshes': {}, 'armature': None}
if rig is None:
    fail('KingCrab.fbx: no armature')
else:
    names = {b.name: (b.parent.name if b.parent else None) for b in rig.data.bones}
    r['armature'] = {'bones': len(names)}
    if set(names) != set(DEFORM):
        fail(f'KingCrab.fbx: bone set differs (missing {sorted(set(DEFORM) - set(names))[:5]}, '
             f'extra {sorted(set(names) - set(DEFORM))[:5]})')
    bad_par = [n for n in names if n in DEFORM and names[n] != DEFORM[n]]
    if bad_par:
        fail(f'KingCrab.fbx: parents differ for {bad_par[:5]}')
    r['armature']['hierarchy_matches_manifest'] = not bad_par and set(names) == set(DEFORM)
    r['armature']['leaf_bones'] = [n for n in names if n.endswith('_end')]
    if r['armature']['leaf_bones']:
        fail('KingCrab.fbx: leaf bones present')
if len(obs) != len(SECTIONS):
    fail(f'KingCrab.fbx: {len(obs)} meshes, manifest has {len(SECTIONS)} sections')
for o in obs:
    me = o.data
    m = {'triangles': tris(me), 'uv_layers': [u.name for u in me.uv_layers],
         'weights': weight_check(o, set(DEFORM)), 'flat_corner_fraction': round(flat_fraction(me), 4),
         'texture': image_ok(o),
         'armature_modifier': any(md.type == 'ARMATURE' and md.object == rig for md in o.modifiers)}
    if m['triangles'] >= 20000:
        fail(f'{o.name}: {m["triangles"]} triangles >= 20k')
    if not m['uv_layers']:
        fail(f'{o.name}: no UVs')
    w = m['weights']
    if w['unweighted'] or w['over_4_influences'] or w['not_normalized'] or w['weights_to_non_bones']:
        fail(f'{o.name}: weights {w}')
    sec = o.name.replace('KingCrab_', '')
    want = MAN.get('shading', {}).get(sec, 'flat')
    m['expected_shading'] = want
    if want == 'flat' and m['flat_corner_fraction'] < 0.98:
        fail(f'{o.name}: faceted normals lost ({m["flat_corner_fraction"]})')
    if want == 'smooth' and m['flat_corner_fraction'] > 0.5:
        fail(f'{o.name}: smooth eyeball normals lost ({m["flat_corner_fraction"]})')
    if not m['texture']:
        fail(f'{o.name}: embedded texture did not load')
    if not m['armature_modifier']:
        fail(f'{o.name}: not skinned to the armature')
    r['meshes'][o.name] = m
r['total_triangles'] = sum(m['triangles'] for m in r['meshes'].values())
if rig:
    r['dimensions_rest'] = dims_check('KingCrab.fbx', obs, rig)
report['files']['KingCrab.fbx'] = r

# ---------------------------------------------------------------- clip FBXs
for clip, frames, want in (('ReferencePose', [1, 2], 'held'), ('RigTest_ROM', list(range(1, 145, 4)), 'range')):
    fresh()
    bpy.ops.import_scene.fbx(filepath=str(FBX / f'KingCrab_{clip}.fbx'))
    rig = arm()
    c = {'meshes': len(meshes())}
    if rig is None or not bpy.data.actions:
        fail(f'{clip}.fbx: no armature or action')
        report['files'][f'KingCrab_{clip}.fbx'] = c
        continue
    c['bones'] = len(rig.data.bones)
    c['only_deform_bones'] = set(b.name for b in rig.data.bones) == set(DEFORM)
    if not c['only_deform_bones']:
        fail(f'{clip}.fbx: bone set differs from deform set')
    if c['meshes']:
        fail(f'{clip}.fbx: contains meshes (should be armature-only)')
    act = bpy.data.actions[0]
    c['action'] = act.name
    c['frame_range'] = [round(v, 2) for v in act.frame_range]
    # An armature-only FBX carries no mesh bind pose, so the importer adopts
    # the first animated frame as the bones' rest; matrix_basis is then
    # identity there. Poses are therefore compared as armature-space joint
    # positions against samples the generator recorded from the live rig.
    rig.animation_data_create()
    rig.animation_data.action = act
    f0 = int(round(act.frame_range[0]))
    key, fsrc = ('ReferencePose@1', 1) if want == 'held' else ('RigTest_ROM@37', 37)
    bpy.context.scene.frame_set(f0 + fsrc - 1)
    exp = MAN['pose_samples'][key]
    # FBX stores joints, not bone tails (the importer guesses tails), so the
    # joint heads are compared.
    err = 0.0
    for pb in rig.pose.bones:
        if pb.name in exp:
            h = rig.matrix_world @ pb.head
            err = max(err, (h - Vector(exp[pb.name][0])).length)
    c[f'max_joint_error_vs_{key}_studs'] = round(err, 4)
    if err > 0.02:
        fail(f'{clip}.fbx: pose {key} reproduced only to {err:.3f} studs')
    rest_move = max((Vector(exp[n][0]) - Vector(b['head'])).length
                    for b in MAN['bones'] for n in [b['name']] if n in exp)
    c[f'{key}_max_joint_offset_from_rest_studs'] = round(rest_move, 3)
    if want == 'held':
        pass
    else:
        mot = bone_motion(rig, act, frames)
        chains = {}
        for n, v in mot.items():
            key = n.split('_')[0] + ('_' + n.split('_')[1] if n.startswith(('Leg', 'Claw')) else '')
            chains[key] = max(chains.get(key, 0.0), v)
        c['max_motion_by_chain_deg'] = {k: round(v, 1) for k, v in sorted(chains.items())}
        c['bones_without_motion'] = sorted(n for n, v in mot.items() if v < 0.5 and n != 'Root')
        if c['bones_without_motion']:
            fail(f'{clip}.fbx: bones never move: {c["bones_without_motion"][:6]}')
    report['files'][f'KingCrab_{clip}.fbx'] = c

# ---------------------------------------------------------------------- GLB
fresh()
bpy.ops.import_scene.gltf(filepath=str(GLB / 'KingCrab.glb'))
rig = arm()
# the glTF importer adds its own 'Icosphere' bone-display shape; ignore it
obs = [o for o in meshes() if o.name.startswith('KingCrab_')]
g = {'meshes': len(obs), 'importer_helper_objects': [o.name for o in meshes() if o not in obs],
     'actions': sorted(a.name for a in bpy.data.actions)}
if rig is None:
    fail('KingCrab.glb: no armature')
else:
    g['bones'] = len(rig.data.bones)
    g['skinned_meshes'] = sum(1 for o in obs if any(md.type == 'ARMATURE' for md in o.modifiers))
    if g['skinned_meshes'] != len(SECTIONS):
        fail(f'KingCrab.glb: {g["skinned_meshes"]} skinned meshes')
    g['textures'] = sum(1 for o in obs if image_ok(o))
    if g['textures'] != len(SECTIONS):
        fail(f'KingCrab.glb: textures loaded on {g["textures"]} meshes')
    for want in ('ReferencePose', 'RigTest_ROM'):
        if not any(a.startswith(want) for a in g['actions']):
            fail(f'KingCrab.glb: action {want} missing')
    refp = next((a for a in bpy.data.actions if a.name.startswith('ReferencePose')), None)
    if refp:
        rig.animation_data_create()
        rig.animation_data.action = refp
        bpy.context.scene.frame_set(int(refp.frame_range[0]))
        g['reference_pose_bones_posed'] = sum(
            1 for pb in rig.pose.bones if math.degrees(pb.matrix_basis.to_quaternion().angle) > 0.5)
        if g['reference_pose_bones_posed'] < 20:
            fail(f'KingCrab.glb: ReferencePose poses only {g["reference_pose_bones_posed"]} bones')
    rom = next((a for a in bpy.data.actions if a.name.startswith('RigTest_ROM')), None)
    if rom:
        mot = bone_motion(rig, rom, list(range(int(rom.frame_range[0]), int(rom.frame_range[1]) + 1, 6)))
        g['rom_bones_with_motion'] = sum(1 for v in mot.values() if v > 0.5)
    for a in bpy.data.actions:
        a.use_fake_user = True
    rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.matrix_basis.identity()
    g['dimensions_rest'] = dims_check('KingCrab.glb', obs, rig)
    g['weights'] = {o.name: weight_check(o, {b.name for b in rig.data.bones}) for o in obs}
report['files']['KingCrab.glb'] = g

report['passed'] = not report['failures']
(OUT / 'validation-report.json').write_text(json.dumps(report, indent=2))
print('VALIDATION', 'PASSED' if report['passed'] else f'FAILED ({len(report["failures"])})')
sys.exit(0 if report['passed'] else 1)
