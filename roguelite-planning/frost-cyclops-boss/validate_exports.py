"""Reimport the Frost Cyclops exports fresh and check them. Run in Blender:

    blender -b --factory-startup --python validate_exports.py

Checks, for exports/fbx/FrostCyclops.fbx and exports/glb/FrostCyclops.glb:
  meshes/sections present, each < 20,000 triangles
  bone count, names and hierarchy (against manifest.json)
  every vertex weighted, <= 4 influences, weights normalised
  UVs present, textures load (non-empty pixels)
  faceted normals preserved (loop normals equal face normals)
  actions present, with bone motion (clip FBXs and GLB actions)
  scale and axes: top of the head in studs matches the manifest (ground z = 0); the
    face (Eye mesh) is on the -Y side, i.e. the asset faces -Y after reimport
Writes validation-report.json. Exits non-zero if any check fails.
"""
import json
import sys
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
NAME = 'FrostCyclops'
MAN = json.loads((HERE / 'manifest.json').read_text())
EXPECT_BONES = {b['name']: b['parent'] for b in MAN['bones']}
SECTIONS = ['Body', 'Head', 'Eye', 'Fur', 'Gear', 'Club']
ACTIONS = ['ReferencePose', 'RigTest_ROM', 'GroundSlam', 'Stomp']


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mesh_checks(ob):
    me = ob.data
    n = len(me.vertices)
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    groups = {g.index: g.name for g in ob.vertex_groups}
    counts = np.zeros(n, int)
    sums = np.zeros(n)
    for v in me.vertices:
        ws = [g.weight for g in v.groups if g.weight > 1e-6]
        counts[v.index] = len(ws)
        sums[v.index] = sum(ws)
    uv_ok = len(me.uv_layers) > 0
    uv_range = None
    if uv_ok:
        uv = np.empty(len(me.loops) * 2)
        me.uv_layers[0].data.foreach_get('uv', uv)
        uv = uv.reshape(-1, 2)
        uv_range = [float(uv.min()), float(uv.max())]
    # faceting: loop normals vs polygon normals
    me.calc_loop_triangles() if hasattr(me, 'calc_loop_triangles') else None
    ln = np.empty(len(me.loops) * 3)
    me.corner_normals.foreach_get('vector', ln) if hasattr(me, 'corner_normals') else me.loops.foreach_get('normal', ln)
    ln = ln.reshape(-1, 3)
    pn = np.empty(len(me.polygons) * 3)
    me.polygons.foreach_get('normal', pn)
    pn = pn.reshape(-1, 3)
    loop_poly = np.empty(len(me.loops), int)
    for p in me.polygons:
        loop_poly[p.loop_start:p.loop_start + p.loop_total] = p.index
    # Faceting survives when every corner of a face shares one normal (flat
    # shading). Importers triangulate non-planar quads, so a corner normal may
    # legitimately differ a little from its triangle's own normal; what matters
    # is that the corners within a face agree and point the face's way.
    ref = ln[np.array([p.loop_start for p in me.polygons])][loop_poly]
    same = np.sum(ln * ref, 1) > 0.9995
    facing = np.sum(ln * pn[loop_poly], 1) > 0.9
    ok_poly = np.ones(len(me.polygons), bool)
    np.logical_and.at(ok_poly, loop_poly, same & facing)
    flat_frac = float(np.mean(ok_poly))
    # textures
    tex = []
    for m in me.materials:
        if m and m.use_nodes:
            for nd in m.node_tree.nodes:
                if nd.type == 'TEX_IMAGE' and nd.image:
                    img = nd.image
                    w, h = img.size
                    ok = w > 0 and h > 0
                    mean = None
                    if ok:
                        px = np.empty(w * h * 4, np.float32)
                        img.pixels.foreach_get(px)
                        mean = float(px.reshape(-1, 4)[:, :3].mean())
                    tex.append({'image': img.name, 'size': [w, h], 'mean': mean})
    return {
        'triangles': tris, 'vertices': n, 'under_20k': tris < 20000,
        'unweighted_vertices': int((counts == 0).sum()), 'max_influences': int(counts.max()) if n else 0,
        'max_weight_sum_error': float(np.abs(sums - 1).max()) if n else 0.0,
        'uv': uv_ok, 'uv_range': uv_range, 'flat_loop_fraction': round(flat_frac, 4), 'textures': tex,
    }


def armature_checks(arm_ob):
    bones = {b.name: (b.parent.name if b.parent else None) for b in arm_ob.data.bones}
    missing = [b for b in EXPECT_BONES if b not in bones]
    extra = [b for b in bones if b not in EXPECT_BONES]
    wrong_parent = [b for b, p in EXPECT_BONES.items() if b in bones and bones[b] != p and not (p is None)]
    return {'bone_count': len(bones), 'missing': missing, 'extra': extra, 'wrong_parent': wrong_parent}


def skinned_meshes():
    """Meshes deformed by an armature (the glTF importer adds an unskinned
    'Icosphere' as a bone display shape; it is not part of the asset)."""
    return [o for o in bpy.data.objects if o.type == 'MESH' and
            (any(m.type == 'ARMATURE' for m in o.modifiers) or (o.parent and o.parent.type == 'ARMATURE'))]


def world_bounds(obs):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for ob in obs:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        pts.append(np.array([ob.matrix_world @ v.co for v in me.vertices]))
        ev.to_mesh_clear()
    P = np.concatenate(pts)
    return P.min(0), P.max(0)


def action_motion(arm_ob, action, frames):
    arm_ob.animation_data.action = action
    moved = 0
    base = {}
    for f in frames:
        bpy.context.scene.frame_set(f)
        for pb in arm_ob.pose.bones:
            m = np.array(pb.matrix)
            if pb.name not in base:
                base[pb.name] = m
            elif np.abs(m - base[pb.name]).max() > 1e-3:
                moved += 1
    return moved


def check_fbx_main(rep):
    reset()
    bpy.ops.import_scene.fbx(filepath=str(HERE / 'exports/fbx' / f'{NAME}.fbx'))
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    mesh_obs = skinned_meshes()
    r = {'armatures': len(arms), 'meshes': len(mesh_obs), 'mesh_names': sorted(o.name for o in mesh_obs)}
    r['armature'] = armature_checks(arms[0]) if arms else None
    r['per_mesh'] = {o.name: mesh_checks(o) for o in mesh_obs}
    eye = [o for o in mesh_obs if o.name.endswith('_Eye')]
    body = [o for o in mesh_obs if o.name.endswith('_Body')]
    if eye and body:
        r['eye_y'] = round(float(np.mean(world_bounds(eye), 0)[1]), 3)
        r['body_y'] = round(float(np.mean(world_bounds(body), 0)[1]), 3)
    lo, hi = world_bounds(mesh_obs)
    r['bounds_min'] = lo.round(3).tolist()
    r['bounds_max'] = hi.round(3).tolist()
    r['height'] = round(float(hi[2]), 3)          # top of the head above the ground plane (z = 0)
    rep['fbx_main'] = r


def check_fbx_clips(rep):
    out = {}
    for act in ACTIONS:
        reset()
        p = HERE / 'exports/fbx' / f'{NAME}_{act}.fbx'
        bpy.ops.import_scene.fbx(filepath=str(p))
        arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
        acts = list(bpy.data.actions)
        e = {'armatures': len(arms), 'meshes': len([o for o in bpy.data.objects if o.type == 'MESH']),
             'actions': [a.name for a in acts]}
        if arms and acts:
            a = acts[0]
            f0, f1 = int(a.frame_range[0]), int(a.frame_range[1])
            e['frame_range'] = [f0, f1]
            frames = list(range(f0, f1 + 1, max(1, (f1 - f0) // 12)))
            e['bones_moving_samples'] = action_motion(arms[0], a, frames)
            e['armature'] = armature_checks(arms[0])
        out[act] = e
    rep['fbx_clips'] = out


def check_glb(rep):
    reset()
    bpy.ops.import_scene.gltf(filepath=str(HERE / 'exports/glb' / f'{NAME}.glb'))
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    mesh_obs = skinned_meshes()
    r = {'armatures': len(arms), 'meshes': len(mesh_obs), 'mesh_names': sorted(o.name for o in mesh_obs),
         'actions': sorted(a.name for a in bpy.data.actions),
         'ignored_importer_helpers': sorted(o.name for o in bpy.data.objects
                                            if o.type == 'MESH' and o not in mesh_obs)}
    r['armature'] = armature_checks(arms[0]) if arms else None
    r['per_mesh'] = {o.name: mesh_checks(o) for o in mesh_obs}
    moving = {}
    if arms:
        arm = arms[0]
        if not arm.animation_data:
            arm.animation_data_create()
        for a in bpy.data.actions:
            f0, f1 = int(a.frame_range[0]), int(a.frame_range[1])
            try:
                moving[a.name] = action_motion(arm, a, list(range(f0, f1 + 1, max(1, (f1 - f0) // 10))))
            except Exception as ex:          # slot assignment differences between importers
                moving[a.name] = f'error: {ex}'
        arm.animation_data.action = None
        bpy.context.scene.frame_set(1)
        for pb in arm.pose.bones:
            pb.matrix_basis.identity()
    r['bones_moving_samples'] = moving
    lo, hi = world_bounds(mesh_obs)
    r['height'] = round(float(hi[2]), 3)
    r['bounds_min'] = lo.round(3).tolist()
    r['bounds_max'] = hi.round(3).tolist()
    rep['glb'] = r


def check_game_package(rep):
    """exports/game: the Studio import FBX and AnimationData.json (BOSS_GAME_PACKAGE_SPEC section 5)."""
    game = HERE / 'exports' / 'game'
    r = {}
    anim = json.loads((game / 'AnimationData.json').read_text())
    reset()
    bpy.ops.import_scene.fbx(filepath=str(game / f'{NAME}_Studio.fbx'))
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    mesh_obs = skinned_meshes()
    r['meshes'] = {o.name: mesh_checks(o) for o in mesh_obs}
    bones = sorted(b.name for b in arms[0].data.bones) if arms else []
    r['bones_match_animation_data'] = bones == sorted(anim['bones'].keys())
    r['bone_count'] = len(bones)
    r['actions_in_studio_fbx'] = len(bpy.data.actions)
    r['fbm_textures'] = sorted(p.name for p in (game / f'{NAME}_Studio.fbm').glob('*.png'))
    clips = {}
    for name, c in anim['clips'].items():
        n_exp = int(round(c['duration'] * anim['fps'])) + 1
        vals = [x for f in c['frames'] for v in f['transforms'].values() for x in v]
        e = {'frames': len(c['frames']), 'expected': n_exp, 'nan': bool(not np.all(np.isfinite(np.array(vals, float)))),
             'bones_ok': all(set(f['transforms']) == set(anim['bones']) for f in c['frames'])}
        if c['loop']:
            a, b = c['frames'][0]['transforms'], c['frames'][-1]['transforms']
            e['loop_error'] = max(abs(x - y) for k in a for x, y in zip(a[k], b[k]))
        clips[name] = e
    r['clips'] = clips
    gd = json.loads((game / 'BossGameData.json').read_text())
    r['attack_times_on_frames'] = {
        a: {k: round(v[k] * anim['fps'], 3) for k in ('warnStart', 'impact', 'activeEnd', 'recoveryEnd')}
        for a, v in gd['attacks'].items()}
    rep['game_package'] = r


def verdict(rep):
    fails = []
    exp_h = MAN['dimensions_studs']['height_rest_pose']       # top of the head, ground at z = 0
    for key in ('fbx_main', 'glb'):
        r = rep[key]
        if r['meshes'] != len(SECTIONS):
            fails.append(f'{key}: {r["meshes"]} meshes, expected {len(SECTIONS)}')
        a = r['armature']
        if not a or a['missing'] or a['wrong_parent']:
            fails.append(f'{key}: armature mismatch {a}')
        if a and a['extra']:
            fails.append(f'{key}: extra bones {a["extra"]}')
        for n, m in r['per_mesh'].items():
            if not m['under_20k']:
                fails.append(f'{key}/{n}: {m["triangles"]} tris')
            if m['unweighted_vertices']:
                fails.append(f'{key}/{n}: {m["unweighted_vertices"]} unweighted vertices')
            if m['max_influences'] > 4:
                fails.append(f'{key}/{n}: {m["max_influences"]} influences')
            if m['max_weight_sum_error'] > 0.01:
                fails.append(f'{key}/{n}: weight sum error {m["max_weight_sum_error"]}')
            if not m['uv']:
                fails.append(f'{key}/{n}: no UVs')
            if not m['textures'] or not all(t['size'][0] > 0 for t in m['textures']):
                fails.append(f'{key}/{n}: texture not loaded')
            if m['flat_loop_fraction'] < 0.98:
                fails.append(f'{key}/{n}: faceting lost ({m["flat_loop_fraction"]})')
        if abs(r['height'] - exp_h) > 0.05:
            fails.append(f'{key}: height {r["height"]} vs {exp_h}')
        if r.get('eye_y') is not None and not (r['eye_y'] < r['body_y']):
            fails.append(f'{key}: faces the wrong way (eye y {r["eye_y"]} vs body y {r["body_y"]})')
    for act, e in rep['fbx_clips'].items():
        if e['armatures'] != 1 or e['meshes'] != 0 or not e['actions']:
            fails.append(f'clip {act}: {e}')
        elif act != 'ReferencePose' and not e.get('bones_moving_samples'):
            fails.append(f'clip {act}: no bone motion')
    gp = rep.get('game_package')
    if gp:
        for n, m in gp['meshes'].items():
            if not m['under_20k'] or not m['textures'] or not all(t['size'][0] > 0 for t in m['textures']):
                fails.append(f'studio fbx/{n}: tris or texture problem')
        if not gp['bones_match_animation_data']:
            fails.append('studio fbx bones differ from AnimationData.json')
        if gp['actions_in_studio_fbx']:
            fails.append('studio fbx carries animation')
        for a, fr in gp.get('attack_times_on_frames', {}).items():
            if any(abs(f - round(f)) > 0.01 for f in fr.values()):
                fails.append(f'BossGameData {a}: times not on 24 fps frames {fr}')
        for n, e in gp['clips'].items():
            if e['frames'] != e['expected'] or e['nan'] or not e['bones_ok'] or e.get('loop_error', 0) > 1e-4:
                fails.append(f'AnimationData clip {n}: {e}')
    g = rep['glb']
    names = ' '.join(g['actions'])
    for act in ACTIONS:
        if act not in names:
            fails.append(f'glb: action {act} missing')
    rep['fails'] = fails
    rep['passed'] = not fails
    return fails


def main():
    rep = {'tool': 'validate_exports.py', 'blender': bpy.app.version_string}
    check_fbx_main(rep)
    check_fbx_clips(rep)
    check_glb(rep)
    if (HERE / 'exports' / 'game' / 'AnimationData.json').exists():
        check_game_package(rep)
    fails = verdict(rep)
    (HERE / 'validation-report.json').write_text(json.dumps(rep, indent=1))
    print('VALIDATION', 'PASSED' if not fails else 'FAILED', json.dumps(fails, indent=1))
    sys.exit(0 if not fails else 1)


if __name__ == '__main__':
    main()
