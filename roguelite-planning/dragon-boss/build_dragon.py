"""Dragon boss generator. Run headless under Blender 5.2:

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python build_dragon.py

Environment:
    DRAGON_STAGE = probe | full        (default full)
        probe: geometry + rig + weights + ReferencePose + flat preview materials,
               renders _work/probe_render.png and _work/probe_mask.png (~1-2 min)
        full:  + baked painterly textures, all previews, actions, exports, manifest,
               Dragon.blend
    DRAGON_SAMPLES   Cycles samples for previews (default 64)
    DRAGON_ZOOM      comma list of close-up crops to also render in probe mode

Self-contained: imports only the dragon_* modules in this folder. Blender world,
Z up, the dragon faces -Y, +X is the dragon's left; 1 unit = 1 Roblox stud.
"""
import json
import shutil
import math
import os
import sys
import time
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Quaternion, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dragon_camera as CAM  # noqa: E402
import dragon_design as D  # noqa: E402
import dragon_pose as PZ  # noqa: E402
import dragon_rig as RG  # noqa: E402

STAGE = os.environ.get('DRAGON_STAGE', 'full')
PROBE = STAGE == 'probe'
WORK = HERE / '_work'
WORK.mkdir(exist_ok=True)
T0 = time.time()
NAME = 'Dragon'
SECTIONS = ['Body', 'Head', 'Wings', 'Belly', 'Obsidian', 'LavaGlow', 'EyeGlow']
BODY_TRIS = int(os.environ.get('DRAGON_BODY_TRIS', '14000'))


def log(*a):
    print('[DRAGON %6.1fs]' % (time.time() - T0), *a, flush=True)


# ----------------------------------------------------------------- scene utils
def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.armatures, bpy.data.actions):
        for it in list(coll):
            coll.remove(it)


def activate(ob):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def make_mesh(name, V, F, coll=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in V], [], [list(map(int, f)) for f in F])
    me.validate(clean_customdata=False)
    me.update()
    ob = bpy.data.objects.new(name, me)
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


def recalc_normals(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()


def flat(ob):
    for p in ob.data.polygons:
        p.use_smooth = False


def apply_mods(ob):
    activate(ob)
    for m in list(ob.modifiers):
        if m.type == 'ARMATURE':
            continue
        bpy.ops.object.modifier_apply(modifier=m.name)


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def set_weights(ob, W):
    n = len(ob.data.vertices)
    if isinstance(W, str):
        g = ob.vertex_groups.get(W) or ob.vertex_groups.new(name=W)
        g.add(list(range(n)), 1.0, 'REPLACE')
        return
    for b, w in W.items():
        w = np.asarray(w, float)
        idx = np.nonzero(w > 1e-4)[0]
        if len(idx) == 0:
            continue
        g = ob.vertex_groups.get(b) or ob.vertex_groups.new(name=b)
        for i in idx:
            g.add([int(i)], float(w[i]), 'REPLACE')


def get_weights(ob):
    """{group name: (n,) array} from an object's vertex groups."""
    n = len(ob.data.vertices)
    names = {g.index: g.name for g in ob.vertex_groups}
    W = {nm: np.zeros(n) for nm in names.values()}
    for v in ob.data.vertices:
        for ge in v.groups:
            W[names[ge.group]][v.index] = ge.weight
    return W


def normalize_limit(ob, k=4):
    """Every vertex: <= k influences, weights normalised to 1."""
    W = get_weights(ob)
    Wl = D.limit_weights(W, len(ob.data.vertices), k=k, floor=0.01)
    for g in list(ob.vertex_groups):
        ob.vertex_groups.remove(g)
    set_weights(ob, Wl)


# ------------------------------------------------------------------ materials
PREVIEW_COLORS = {'skin': (150, 38, 34), 'skin_head': (155, 40, 35), 'jaw': (205, 150, 102), 'belly': (210, 158, 108),
                  'fang': (228, 205, 165), 'mouth': (70, 18, 16), 'obsidian': (58, 44, 50), 'lava': (255, 140, 30),
                  'eye': (255, 205, 90), 'wingbone': (150, 40, 36), 'membrane': (225, 105, 42)}


def srgb_lin(c):
    c = np.asarray(c, float) / 255.0
    return tuple(np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4))


def preview_material(key):
    name = 'PRV_' + key
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bs = nt.nodes.get('Principled BSDF')
    col = srgb_lin(PREVIEW_COLORS.get(key, (255, 0, 255)))
    bs.inputs['Base Color'].default_value = (*col, 1)
    bs.inputs['Roughness'].default_value = 0.85
    if key in ('lava', 'eye'):
        bs.inputs['Emission Color'].default_value = (*col, 1)
        bs.inputs['Emission Strength'].default_value = 4.0
    m['paint'] = key
    return m


# ------------------------------------------------------------------ geometry
def build_parts(coll):
    parts, prims, grid = D.build_all(float(os.environ.get('DRAGON_H', '0.08')))
    log('design parts', len(parts))
    objs = []
    for p in parts:
        ob = make_mesh(p['name'], p['V'], p['F'], coll)
        ob['section'] = p['section']
        ob['mat'] = p['mat']
        if p.get('sdf'):
            W = D.ownership_weights(prims, np.asarray(p['V'], float))
            W = D.limit_weights(W, len(p['V']), k=4, floor=0.01)
            W = D.smooth_weights(W, p['F'], len(p['V']), iters=4)
            set_weights(ob, W)
            recalc_normals(ob)
            # the SDF masses are planar-faceted already; quadric collapse keeps
            # those planes and strips the dense sampling down to the budget
            m = ob.modifiers.new('decimate', 'DECIMATE')
            m.decimate_type = 'COLLAPSE'
            m.ratio = min(1.0, BODY_TRIS / max(tri_count(ob), 1))
            m.use_collapse_triangulate = True
            apply_mods(ob)
            facet_normals(ob, grid)
        else:
            set_weights(ob, p['weights'])
            recalc_normals(ob)
            if p.get('bevel'):
                w, seg, ang = p['bevel']
                bev = ob.modifiers.new('bevel', 'BEVEL')
                bev.width = w
                bev.segments = seg
                bev.limit_method = 'ANGLE'
                bev.angle_limit = math.radians(ang)
                bev.miter_outer = 'MITER_ARC'
                bev.harden_normals = False
                apply_mods(ob)
        if not p.get('sdf'):
            flat(ob)
        ob.data.materials.append(preview_material(p['mat']))
        objs.append(ob)
    return objs, prims


def facet_normals(ob, grid):
    """Shade every face with the SDF gradient at its centroid. Inside a facet the
    plane-max SDF is linear, so all faces of one facet get exactly that plane's
    normal (clean flat facets whatever the triangulation); across facet edges
    the sampled gradient turns over ~1 voxel, which reads as a soft bevel.
    Stored as custom split normals (exported to FBX, used by Roblox)."""
    me = ob.data
    n = len(me.polygons)
    cen = np.zeros(n * 3)
    me.polygons.foreach_get('center', cen)
    cen = cen.reshape(-1, 3)
    e = grid.h * 0.9
    g = np.stack([(grid.sample(cen + np.eye(3)[k] * e) - grid.sample(cen - np.eye(3)[k] * e)) / (2 * e)
                  for k in range(3)], 1)
    fn = np.zeros(n * 3)
    me.polygons.foreach_get('normal', fn)
    fn = fn.reshape(-1, 3)
    gl = np.linalg.norm(g, axis=1, keepdims=True)
    g = np.where(gl > 1e-6, g / np.maximum(gl, 1e-9), fn)
    # never flip a face's shading against its geometry
    flip = np.einsum('ij,ij->i', g, fn) < 0.2
    g[flip] = fn[flip]
    for p in me.polygons:
        p.use_smooth = True
    loop_n = np.zeros((len(me.loops), 3))
    for p in me.polygons:
        loop_n[p.loop_start:p.loop_start + p.loop_total] = g[p.index]
    me.normals_split_custom_set([tuple(v) for v in loop_n])
    me.update()


def jitter_facets(ob, amount):
    """Slight random vertex offsets so facets read hand-cut, not machine-regular."""
    rng = np.random.default_rng(7)
    co = np.zeros(len(ob.data.vertices) * 3)
    ob.data.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    nrm = np.zeros(len(ob.data.vertices) * 3)
    ob.data.vertices.foreach_get('normal', nrm)
    nrm = nrm.reshape(-1, 3)
    co += nrm * rng.normal(0, amount, (len(co), 1))
    ob.data.vertices.foreach_set('co', co.ravel())
    ob.data.update()


def join_sections(objs, coll):
    out = {}
    groups = {sec: [o for o in objs if o.get('section') == sec] for sec in SECTIONS}
    for sec in SECTIONS:
        members = groups[sec]
        if not members:
            continue
        activate(members[0])
        for o in members:
            o.select_set(True)
        bpy.context.view_layer.objects.active = members[0]
        bpy.ops.object.join()
        ob = bpy.context.view_layer.objects.active
        ob.name = f'{NAME}_{sec}'
        ob.data.name = f'{NAME}_{sec}'
        normalize_limit(ob, 4)
        out[sec] = ob
        log('section', sec, 'tris', tri_count(ob), 'verts', len(ob.data.vertices))
    return out


# ------------------------------------------------------------------ armature
def build_armature(coll):
    sk = RG.Skeleton()
    arm = bpy.data.armatures.new(f'{NAME}_Rig')
    rig = bpy.data.objects.new(f'{NAME}_Rig', arm)
    coll.objects.link(rig)
    activate(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = {}
    for name, parent, h, t, zh, deform in sk.specs:
        b = arm.edit_bones.new(name)
        b.head = Vector(h)
        b.tail = Vector(t)
        b.align_roll(Vector(zh))
        b.use_deform = deform
        if parent:
            b.parent = eb[parent]
            b.use_connect = False
        eb[name] = b
    # IK controls (non-deform), excluded from export
    for s in ('L', 'R'):
        for leg, tipb in (('Hand', f'Hand_{s}'), ('Foot', f'Foot_{s}')):
            c = arm.edit_bones.new(f'IK_{leg}_{s}')
            h = eb[tipb].head.copy()
            c.head = Vector((h.x, h.y, 0.0))
            c.tail = Vector((h.x, h.y - 1.2, 0.0))
            c.use_deform = False
            c.parent = eb['Root']
            pole = arm.edit_bones.new(f'Pole_{leg}_{s}')
            mid = eb['Forearm_' + s].head if leg == 'Hand' else eb['Shin_' + s].head
            pole.head = mid + Vector((0, -3.0, 0))
            pole.tail = pole.head + Vector((0, -0.6, 0))
            pole.use_deform = False
            pole.parent = eb['Root']
    bpy.ops.object.mode_set(mode='OBJECT')
    # verify rest matrices match the numpy skeleton (same FK convention)
    err = 0.0
    for name in sk.names:
        m = np.array(rig.data.bones[name].matrix_local)
        err = max(err, float(np.abs(m - sk.rest[name]).max()))
    log('armature bones', len(arm.bones), 'max rest-matrix mismatch vs numpy', round(err, 6))
    # IK constraints driven by a rig property (0 = FK as authored, 1 = IK)
    rig['ik_legs'] = 0.0
    for s in ('L', 'R'):
        for leg, b, chain in (('Hand', f'Forearm_{s}', 2), ('Foot', f'Shin_{s}', 2)):
            pb = rig.pose.bones[b]
            c = pb.constraints.new('IK')
            c.target = rig
            c.subtarget = f'IK_{leg}_{s}'
            c.pole_target = rig
            c.pole_subtarget = f'Pole_{leg}_{s}'
            c.chain_count = chain
            fc = c.driver_add('influence')
            fc.driver.type = 'AVERAGE'
            v = fc.driver.variables.new()
            v.targets[0].id = rig
            v.targets[0].data_path = '["ik_legs"]'
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    return rig, sk


def bind(sections, rig):
    for sec, ob in sections.items():
        ob.parent = rig
        m = ob.modifiers.new('Armature', 'ARMATURE')
        m.object = rig
        m.use_deform_preserve_volume = False


def apply_pose(rig, pose, frame=None, action=None):
    for pb in rig.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    for b, v in pose.items():
        pb = rig.pose.bones[b]
        if isinstance(v, dict):
            pb.rotation_quaternion = Quaternion(tuple(v['q']))
            pb.location = Vector(tuple(v['t']))
        else:
            pb.rotation_quaternion = Quaternion(tuple(v))
    if frame is not None:
        for pb in rig.pose.bones:
            if not rig.data.bones[pb.name].use_deform:
                continue
            pb.keyframe_insert('rotation_quaternion', frame=frame, group=pb.name)
            if pb.name == 'Root':
                pb.keyframe_insert('location', frame=frame, group=pb.name)
    bpy.context.view_layer.update()


def check_fk(rig, sk, pose):
    W = sk.fk(pose)
    err = 0.0
    for n in sk.names:
        err = max(err, float(np.abs(np.array(rig.pose.bones[n].matrix) - W[n]).max()))
    return err


# ------------------------------------------------------------------ camera, lights, renders
def setup_camera():
    s = CAM.blender_camera_settings()
    cd = bpy.data.cameras.new('RefCam')
    cd.lens = s['lens']
    cd.sensor_width = 36.0
    cd.sensor_fit = 'HORIZONTAL'
    cd.shift_y = s['shift_y']
    cd.clip_start = 0.1
    cd.clip_end = 400
    cam = bpy.data.objects.new('RefCam', cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = s['location']
    cam.rotation_euler = s['rotation_euler']
    bpy.context.scene.camera = cam
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = CAM.W, CAM.H
    sc.render.resolution_percentage = 100
    return cam


def set_gpu():
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for dev_type in ('OPTIX', 'CUDA'):
        try:
            prefs.compute_device_type = dev_type
            prefs.get_devices()
            devs = [d for d in prefs.devices if d.type == dev_type]
            if devs:
                for d in prefs.devices:
                    d.use = d.type == dev_type
                sc.cycles.device = 'GPU'
                log('cycles device', dev_type)
                return dev_type
        except Exception as e:  # noqa: BLE001
            log('gpu', dev_type, 'failed', e)
    sc.cycles.device = 'CPU'
    return 'CPU'


def render_mask(path, objs):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'FLAT'
    sc.display.shading.color_type = 'SINGLE'
    sc.display.shading.single_color = (1, 1, 1)
    sc.display.shading.show_backface_culling = False
    sc.render.film_transparent = False
    world = sc.world or bpy.data.worlds.new('W')
    sc.world = world
    sc.display.shading.background_type = 'WORLD' if hasattr(sc.display.shading, 'background_type') else None
    world.color = (0, 0, 0)
    sc.view_settings.view_transform = 'Standard'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'BW'
    hidden = [o for o in sc.objects if o.type == 'MESH' and o not in objs]
    for o in hidden:
        o.hide_render = True
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    for o in hidden:
        o.hide_render = False
    sc.render.image_settings.color_mode = 'RGB'


def setup_lights():
    """Warm dusky volcanic light: warm key sun from camera-left/front (shadows fall
    right and back, as in the reference), lilac-dusk sky fill, orange rim from
    the lava behind. Camera rays see a flat dusk backdrop colour instead."""
    sc = bpy.context.scene
    world = bpy.data.worlds.get('DragonWorld') or bpy.data.worlds.new('DragonWorld')
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    sky = nt.nodes.new('ShaderNodeBackground')
    sky.inputs['Color'].default_value = (*srgb_lin((186, 168, 212)), 1)
    sky.inputs['Strength'].default_value = LIGHT['sky']
    back = nt.nodes.new('ShaderNodeBackground')
    back.inputs['Color'].default_value = (*srgb_lin((150, 122, 134)), 1)
    back.inputs['Strength'].default_value = 1.0
    lp = nt.nodes.new('ShaderNodeLightPath')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs[0])
    nt.links.new(sky.outputs[0], mix.inputs[1])
    nt.links.new(back.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    sc.world = world
    for n, (energy, rot, col, ang) in {
        'Sun_Key': (LIGHT['sun'], (math.radians(90 - LIGHT['sun_el']), 0, math.radians(LIGHT['sun_az'])), (255, 226, 196), 8.0),
        'Sun_Rim': (LIGHT['rim'], (math.radians(62), 0, math.radians(150)), (255, 140, 70), 12.0),
        'Sun_Fill': (LIGHT['fill'], (math.radians(70), 0, math.radians(-30)), (200, 190, 230), 30.0),
    }.items():
        ld = bpy.data.lights.get(n) or bpy.data.lights.new(n, 'SUN')
        ld.energy = energy
        ld.color = srgb_lin(col)
        ld.angle = math.radians(ang)
        ob = bpy.data.objects.get(n) or bpy.data.objects.new(n, ld)
        if ob.name not in sc.collection.objects:
            sc.collection.objects.link(ob)
        ob.rotation_euler = rot
    return world


LIGHT = {'sun': 4.6, 'sun_el': 50.0, 'sun_az': -40.0, 'rim': 2.0, 'fill': 0.45, 'sky': 0.95}


def ground_and_backdrop():
    me = bpy.data.meshes.new('Ground')
    s = 80
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new('Ground', me)
    bpy.context.scene.collection.objects.link(g)
    m = bpy.data.materials.new('GroundStone')
    m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*srgb_lin((122, 104, 110)), 1)
    bs.inputs['Roughness'].default_value = 0.95
    me.materials.append(m)
    return g, None
    me2 = bpy.data.meshes.new('Backdrop')
    me2.from_pydata([(-80, 60, -1), (80, 60, -1), (80, 60, 80), (-80, 60, 80)], [], [(0, 1, 2, 3)])
    b = bpy.data.objects.new('Backdrop', me2)
    bpy.context.scene.collection.objects.link(b)
    m2 = bpy.data.materials.new('BackdropDusk')
    m2.use_nodes = True
    nt = m2.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*srgb_lin((150, 120, 130)), 1)
    em.inputs['Strength'].default_value = 1.0
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    me2.materials.append(m2)
    b.visible_shadow = False
    return g, b


def render_color(path, samples=48, engine='CYCLES'):
    sc = bpy.context.scene
    if engine == 'CYCLES':
        set_gpu()
        sc.cycles.samples = samples
        sc.cycles.use_denoising = True
        try:
            sc.cycles.denoiser = 'OPTIX'
        except Exception:  # noqa: BLE001
            pass
        sc.cycles.max_bounces = 4
    else:
        sc.render.engine = engine
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


# =================================================================== textures
import dragon_paint as PT  # noqa: E402

# Per-recipe linear gains folded in by calibrate.py from the compare loop
# (reference / render per channel, damped). Keys = paint recipes.
CALIBRATION = {
    'skin': (1.194, 2.028, 1.858),
    'skin_head': (2.130, 4.021, 2.438),
    'jaw': (1.507, 1.734, 1.072),
    'belly': (1.558, 1.847, 1.384),
    'fang': (1.000, 1.000, 1.000),
    'mouth': (1.000, 1.000, 1.000),
    'obsidian': (0.916, 1.173, 1.179),
    'lava': (1.000, 1.000, 1.000),
    'eye': (1.000, 1.000, 1.000),
    'wingbone': (0.995, 1.354, 1.113),
    'membrane': (0.812, 0.799, 0.517),
}
MASTER_RES = int(os.environ.get('DRAGON_TEX', '2048'))
DELIVERY_RES = 1024
TEXDIR = HERE / 'textures'


def facet_random(ob):
    """Per-face random that is shared by every triangle of one planar facet
    (faces grouped by quantised shading normal + coarse position)."""
    me = ob.data
    n = len(me.polygons)
    cen = np.zeros(n * 3)
    me.polygons.foreach_get('center', cen)
    cen = cen.reshape(-1, 3)
    nrm = np.zeros((n, 3))
    if me.has_custom_normals:
        ln = np.zeros(len(me.loops) * 3)
        me.corner_normals.foreach_get('vector', ln)
        ln = ln.reshape(-1, 3)
        for p in me.polygons:
            nrm[p.index] = ln[p.loop_start]
    else:
        fn = np.zeros(n * 3)
        me.polygons.foreach_get('normal', fn)
        nrm = fn.reshape(-1, 3)
    key = np.concatenate([np.round(nrm * 14), np.floor(cen / 0.9)], 1).astype(np.int64)
    h = (key[:, 0] * 73856093) ^ (key[:, 1] * 19349663) ^ (key[:, 2] * 83492791) ^ \
        (key[:, 3] * 2654435761) ^ (key[:, 4] * 97531) ^ (key[:, 5] * 1234577)
    r = (h % 10007) / 10007.0
    att = me.attributes.get('facet') or me.attributes.new('facet', 'FLOAT', 'FACE')
    att.data.foreach_set('value', r.astype(np.float32))


def unwrap(ob):
    activate(ob)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(62), island_margin=0.009, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def bake_mat(pass_name, rid, img):
    m = bpy.data.materials.new(f'bake_{pass_name}_{rid}')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    if pass_name == 'P':
        nt.links.new(geo.outputs['Position'], em.inputs['Color'])
    elif pass_name == 'N':
        nt.links.new(geo.outputs['Normal'], em.inputs['Color'])
    elif pass_name == 'A':
        ao = nt.nodes.new('ShaderNodeAmbientOcclusion')
        ao.only_local = True
        ao.samples = 16
        ao.inputs['Distance'].default_value = 0.6
        bev = nt.nodes.new('ShaderNodeBevel')
        bev.samples = 8
        bev.inputs['Radius'].default_value = 0.07
        dot = nt.nodes.new('ShaderNodeVectorMath')
        dot.operation = 'DOT_PRODUCT'
        nt.links.new(bev.outputs['Normal'], dot.inputs[0])
        nt.links.new(geo.outputs['Normal'], dot.inputs[1])
        edge = nt.nodes.new('ShaderNodeMath')
        edge.operation = 'MULTIPLY_ADD'
        edge.inputs[1].default_value = -5.0
        edge.inputs[2].default_value = 5.0
        edge.use_clamp = True
        nt.links.new(dot.outputs['Value'], edge.inputs[0])
        cmb = nt.nodes.new('ShaderNodeCombineXYZ')
        nt.links.new(ao.outputs['AO'], cmb.inputs[0])
        nt.links.new(edge.outputs[0], cmb.inputs[1])
        at = nt.nodes.new('ShaderNodeAttribute')
        at.attribute_type = 'GEOMETRY'
        at.attribute_name = 'facet'
        nt.links.new(at.outputs['Fac'], cmb.inputs[2])
        nt.links.new(cmb.outputs[0], em.inputs['Color'])
    elif pass_name == 'I':
        em.inputs['Color'].default_value = ((rid + 1) / 32.0, 1.0, 0.0, 1.0)
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    nt.nodes.active = tex
    return m


def image_pixels(img):
    a = np.zeros(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(img.size[1], img.size[0], 4)


def set_image_pixels(img, arr):
    img.pixels.foreach_set(np.ascontiguousarray(arr, np.float32).ravel())
    img.update()


def bake_passes(ob, res):
    sc = bpy.context.scene
    set_gpu()
    sc.render.bake.use_selected_to_active = False
    activate(ob)
    keys = [s.material.get('paint', 'skin') for s in ob.material_slots]
    orig = [s.material for s in ob.material_slots]
    out = {}
    for pname, samples in (('P', 1), ('N', 1), ('I', 1), ('A', 24)):
        img = bpy.data.images.new(f'{ob.name}_{pname}', res, res, alpha=True, float_buffer=True)
        img.colorspace_settings.name = 'Non-Color'
        tmp = []
        for i, slot in enumerate(ob.material_slots):
            m = bake_mat(pname, PT.RECIPES.index(keys[i]), img)
            slot.material = m
            tmp.append(m)
        sc.cycles.samples = samples
        bpy.ops.object.bake(type='EMIT', margin=16, margin_type='EXTEND', use_clear=True, target='IMAGE_TEXTURES')
        out[pname] = image_pixels(img).copy()
        for m in tmp:
            bpy.data.materials.remove(m)
        bpy.data.images.remove(img)
    for i, slot in enumerate(ob.material_slots):
        slot.material = orig[i]
    return out


def seg_dist(P, segs):
    best = np.full(len(P), 1e9)
    for a, b in segs:
        a = np.asarray(a, float)
        b = np.asarray(b, float)
        ab = b - a
        t = np.clip(((P - a) @ ab) / max(ab @ ab, 1e-9), 0, 1)
        d = np.linalg.norm(P - (a + t[:, None] * ab), axis=1)
        best = np.minimum(best, d)
    return best


def paint_extras(recipe, P, sk):
    ex = {}
    if recipe in ('skin', 'skin_head') and D.SPINE_LINE:
        L = np.array(D.SPINE_LINE)
        ex['spine'] = seg_dist(P, list(zip(L[:-1], L[1:])))
    if recipe == 'membrane':
        segs = []
        for s in ('L', 'R'):
            for b in ('Wing_{s}_1', 'Wing_{s}_2', 'Wing_{s}_Finger1_1', 'Wing_{s}_Finger1_2', 'Wing_{s}_Finger2_1',
                      'Wing_{s}_Finger2_2'):
                b = b.format(s=s)
                segs.append((sk.head[b], sk.tail[b]))
        ex['bone_dist'] = seg_dist(P, segs)
    if recipe == 'mouth':
        ex['throat'] = np.linalg.norm(P - np.asarray(RG.head_xf((0, -5.6, 9.05))), axis=1)
    if recipe == 'eye':
        e = np.array(RG.J['eye'])
        eL = np.linalg.norm(P - e, axis=1)
        eR = np.linalg.norm(P - RG.mirror(e), axis=1)
        ex['eye_r'] = np.minimum(eL, eR)
    return ex


def paint_section(sec, ob, passes, sk):
    Pm, Nm, Im, Am = passes['P'], passes['N'], passes['I'], passes['A']
    res = Pm.shape[0]
    cov = Im[:, :, 1] > 0.5
    rid = np.clip(np.round(Im[:, :, 0] * 32.0 - 1).astype(int), 0, len(PT.RECIPES) - 1)
    out = np.zeros((res, res, 3))
    for r_i, recipe in enumerate(PT.RECIPES):
        m = cov & (rid == r_i)
        if not m.any():
            continue
        P = Pm[m][:, :3]
        N = Nm[m][:, :3]
        A = Am[m]
        col = PT.paint(recipe, P, N, A[:, 0], A[:, 1], A[:, 2], extra=paint_extras(recipe, P, sk),
                       gains=CALIBRATION.get(recipe, (1, 1, 1)))
        out[m] = col
    # fill uncovered texels with the section's mean colour (no black seams at mip levels)
    if (~cov).any() and cov.any():
        out[~cov] = out[cov].mean(0)
    return out


def save_texture(name, lin, res):
    srgb = PT.lin_to_srgb(lin)
    img = bpy.data.images.new(name, res, res, alpha=False)
    rgba = np.concatenate([srgb, np.ones(srgb.shape[:2] + (1,))], 2)
    set_image_pixels(img, rgba)
    path = TEXDIR / f'{name}.png'
    img.filepath_raw = str(path)
    img.file_format = 'PNG'
    img.save()
    return img, path


def downsample(lin, f):
    h, w, c = lin.shape
    return lin.reshape(h // f, f, w // f, f, c).mean((1, 3))


FINAL = {}


def final_material(sec, img):
    m = bpy.data.materials.new(f'{NAME}_{sec}')
    m.use_nodes = True
    nt = m.node_tree
    bs = nt.nodes.get('Principled BSDF')
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    tex.interpolation = 'Linear'
    nt.links.new(tex.outputs['Color'], bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.82 if sec != 'Obsidian' else 0.62
    bs.inputs['Specular IOR Level'].default_value = 0.35
    if sec in ('LavaGlow', 'EyeGlow'):
        nt.links.new(tex.outputs['Color'], bs.inputs['Emission Color'])
        bs.inputs['Emission Strength'].default_value = GLOW_STRENGTH[sec]
    return m


GLOW_STRENGTH = {'LavaGlow': 1.8, 'EyeGlow': 2.4}


def texture_sections(sections, rig, sk):
    TEXDIR.mkdir(exist_ok=True)
    rig.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    tex_info = {}
    for sec, ob in sections.items():
        facet_random(ob)
        unwrap(ob)
        passes = bake_passes(ob, MASTER_RES)
        lin = paint_section(sec, ob, passes, sk)
        master, mpath = save_texture(f'{NAME}_{sec}_BaseColor_2048', lin, MASTER_RES)
        _, dpath = save_texture(f'{NAME}_{sec}_BaseColor', downsample(lin, MASTER_RES // DELIVERY_RES), DELIVERY_RES)
        master.pack()
        m = final_material(sec, master)
        ob.data.materials.clear()
        ob.data.materials.append(m)
        FINAL[sec] = m
        tex_info[sec] = {'master': mpath.name, 'delivery': dpath.name}
        log('textured', sec)
    rig.data.pose_position = 'POSE'
    bpy.context.view_layer.update()
    return tex_info


# =================================================================== actions
def make_action(rig, name, keys, fps=24):
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    rig.animation_data_create()
    rig.animation_data.action = act
    for frame, pose in keys:
        apply_pose(rig, pose, frame=frame)
    return act


def set_action(rig, act):
    rig.animation_data_create()
    rig.animation_data.action = act
    fr = act.frame_range
    bpy.context.scene.frame_start = int(fr[0])
    bpy.context.scene.frame_end = int(fr[1])


# =================================================================== review scene
REVIEW = None


def review_collection():
    global REVIEW
    if REVIEW is None:
        REVIEW = bpy.data.collections.new('REVIEW_ONLY')
        bpy.context.scene.collection.children.link(REVIEW)
    return REVIEW


def to_review(ob):
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    review_collection().objects.link(ob)


def load_px(path):
    img = bpy.data.images.load(str(path))
    a = image_pixels(img)[::-1, :, :3].copy()
    bpy.data.images.remove(img)
    return a


def save_px(arr, path):
    h, w = arr.shape[:2]
    img = bpy.data.images.new('tmp_save', w, h, alpha=False)
    rgba = np.concatenate([np.clip(arr[::-1], 0, 1), np.ones((h, w, 1))], 2)
    set_image_pixels(img, rgba)
    img.filepath_raw = str(path)
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


def tile(paths, cols, out, gap=6):
    ims = [load_px(p) for p in paths]
    h, w = ims[0].shape[:2]
    rows = (len(ims) + cols - 1) // cols
    sheet = np.full((rows * h + (rows + 1) * gap, cols * w + (cols + 1) * gap, 3), 0.06)
    for i, im in enumerate(ims):
        r, c = divmod(i, cols)
        y = gap + r * (h + gap)
        x = gap + c * (w + gap)
        sheet[y:y + h, x:x + w] = im
    save_px(sheet, out)


def aim_cam(cam, loc, target, lens=None, ortho=None, shift_y=0.0):
    cam.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cd = cam.data
    cd.shift_y = shift_y
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    else:
        cd.type = 'PERSP'
        cd.lens = lens or 50


def render_to(path, w, h, samples=48):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = w, h
    render_color(path, samples=samples)
    sc.render.resolution_x, sc.render.resolution_y = CAM.W, CAM.H


def bone_mesh_object(rig):
    """Octahedral bone shapes at the current pose (for the rig overlay)."""
    V, F = [], []
    for pb in rig.pose.bones:
        if not rig.data.bones[pb.name].use_deform:
            continue
        m = rig.matrix_world @ pb.matrix
        L = pb.length
        r = max(0.06, L * 0.1)
        loc = [(0, 0, 0), (r, L * 0.18, 0), (0, L * 0.18, r), (-r, L * 0.18, 0), (0, L * 0.18, -r), (0, L, 0)]
        o = len(V)
        V += [tuple(m @ Vector(p)) for p in loc]
        F += [[o, o + 1, o + 2], [o, o + 2, o + 3], [o, o + 3, o + 4], [o, o + 4, o + 1],
              [o + 5, o + 2, o + 1], [o + 5, o + 3, o + 2], [o + 5, o + 4, o + 3], [o + 5, o + 1, o + 4]]
    ob = make_mesh('RigBonesViz', V, F)
    m = bpy.data.materials.new('BoneViz')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (0.1, 0.9, 1.0, 1)
    em.inputs['Strength'].default_value = 2.0
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    ob.data.materials.append(m)
    return ob


def measure(sections):
    pts = []
    for ob in sections.values():
        deps = bpy.context.evaluated_depsgraph_get()
        e = ob.evaluated_get(deps)
        me = e.to_mesh()
        co = np.array([tuple(ob.matrix_world @ v.co) for v in me.vertices])
        e.to_mesh_clear()
        pts.append(co)
    P = np.concatenate(pts)
    return P


def export_all(rig, sections, acts):
    fbxdir = HERE / 'exports' / 'fbx'
    glbdir = HERE / 'exports' / 'glb'
    fbxdir.mkdir(parents=True, exist_ok=True)
    glbdir.mkdir(parents=True, exist_ok=True)
    review = [o for o in bpy.data.objects if REVIEW and o.name in REVIEW.objects]
    meshes = list(sections.values())

    def select(obs):
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for o in obs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = rig
    common = dict(use_selection=True, apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE',
                  axis_forward='-Z', axis_up='Y', add_leaf_bones=False, use_armature_deform_only=True,
                  primary_bone_axis='Y', secondary_bone_axis='X', mesh_smooth_type='OFF',
                  use_mesh_modifiers=False)
    # rest mesh + armature + embedded textures (no animation)
    rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    select(meshes + [rig])
    bpy.ops.export_scene.fbx(filepath=str(fbxdir / f'{NAME}.fbx'), object_types={'ARMATURE', 'MESH'},
                             path_mode='COPY', embed_textures=True, bake_anim=False, **common)
    # armature-only clips
    for act in acts:
        set_action(rig, act)
        select([rig])
        bpy.ops.export_scene.fbx(filepath=str(fbxdir / f'{NAME}_{act.name}.fbx'), object_types={'ARMATURE'},
                                 bake_anim=True, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
                                 bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0, **common)
    # GLB with both actions as NLA tracks
    rig.animation_data.action = None
    for tr in list(rig.animation_data.nla_tracks):
        rig.animation_data.nla_tracks.remove(tr)
    for act in acts:
        tr = rig.animation_data.nla_tracks.new()
        tr.name = act.name
        st = tr.strips.new(act.name, int(act.frame_range[0]), act)
        st.name = act.name
        tr.mute = False
    select(meshes + [rig])
    bpy.ops.export_scene.gltf(filepath=str(glbdir / f'{NAME}.glb'), export_format='GLB', use_selection=True,
                              export_animations=True, export_animation_mode='NLA_TRACKS', export_skins=True,
                              export_def_bones=True, export_normals=True, export_apply=False, export_yup=True)
    for tr in list(rig.animation_data.nla_tracks):
        rig.animation_data.nla_tracks.remove(tr)
    for o in review:
        o.hide_set(False)


def sha(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


# =================================================================== previews
def turnaround(rig, sk, cam, sections):
    """Front / side / back / 3-4 / top, wings spread (symmetric spread pose)."""
    apply_pose(rig, PZ.spread_wings(sk))
    P = measure(sections)
    c = 0.5 * (P.min(0) + P.max(0))
    size = float((P.max(0) - P.min(0)).max())
    views = [('front', (0, -1, 0.12)), ('side', (1, 0, 0.08)), ('back', (0, 1, 0.12)), ('three_quarter', (0.8, -0.9, 0.35)),
             ('top', (0.0001, -0.02, 1))]
    paths = []
    for name, dvec in views:
        dvec = Vector(dvec).normalized()
        aim_cam(cam, Vector(c) + dvec * 60, c, ortho=size * 1.08)
        p = WORK / f'turn_{name}.png'
        render_to(p, 900, 700, samples=int(os.environ.get('DRAGON_SAMPLES', '48')))
        paths.append(p)
    tile(paths, 5, HERE / 'previews' / 'Turnaround.png')
    SHEETS['Turnaround.png'] = {'cols': 5, 'tile': [900, 700], 'labels': [n for n, _ in views]}
    return paths


def restore_ref_cam(cam):
    s = CAM.blender_camera_settings()
    cam.data.type = 'PERSP'
    cam.data.lens = s['lens']
    cam.data.shift_y = s['shift_y']
    cam.location = s['location']
    cam.rotation_euler = s['rotation_euler']


def head_closeup(rig, pose, cam):
    apply_pose(rig, pose)
    W = rig.matrix_world @ rig.pose.bones['Head'].matrix
    hc = W @ Vector((0, 1.3, 0.2))
    aim_cam(cam, Vector(CAM.P) + (hc - Vector(CAM.P)) * 0.62, hc, lens=60)
    render_to(HERE / 'previews' / 'Head_Closeup.png', 1200, 900, samples=int(os.environ.get('DRAGON_SAMPLES', '64')))


def rig_bones_overlay(rig, sk, cam, sections):
    """Rest pose model (dimmed) with the deform bones drawn on top, front and side."""
    apply_pose(rig, {})
    P = measure(sections)
    c = 0.5 * (P.min(0) + P.max(0))
    size = float((P.max(0) - P.min(0)).max())
    bones = bone_mesh_object(rig)
    to_review(bones)
    out = []
    for name, dvec in (('front', (0.55, -1, 0.3)), ('side', (1, 0.05, 0.15))):
        dvec = Vector(dvec).normalized()
        aim_cam(cam, Vector(c) + dvec * 60, c, ortho=size * 1.05)
        bones.hide_render = True
        pm = WORK / f'bones_model_{name}.png'
        render_to(pm, 1000, 760, samples=24)
        for o in sections.values():
            o.hide_render = True
        g = bpy.data.objects.get('Ground')
        if g:
            g.hide_render = True
        bones.hide_render = False
        sc = bpy.context.scene
        sc.render.film_transparent = True
        sc.render.image_settings.color_mode = 'RGBA'
        pb = WORK / f'bones_only_{name}.png'
        sc.render.resolution_x, sc.render.resolution_y = 1000, 760
        sc.cycles.samples = 8
        sc.render.filepath = str(pb)
        bpy.ops.render.render(write_still=True)
        sc.render.film_transparent = False
        sc.render.image_settings.color_mode = 'RGB'
        sc.render.resolution_x, sc.render.resolution_y = CAM.W, CAM.H
        for o in sections.values():
            o.hide_render = False
        if g:
            g.hide_render = False
        img = bpy.data.images.load(str(pb))
        a = image_pixels(img)[::-1].copy()
        bpy.data.images.remove(img)
        base = load_px(pm) * 0.5
        al = a[:, :, 3:4]
        comp = base * (1 - al) + a[:, :, :3] * al
        po = WORK / f'bones_comp_{name}.png'
        save_px(comp, po)
        out.append(po)
    bones.hide_render = True
    tile(out, 2, HERE / 'previews' / 'Rig_Bones.png')


SHEETS = {}      # sheet file -> tile layout + captions (drawn by label_sheets.py, system python)


def rom_sheet(rig, cam, act, sections, keys):
    """One tile per non-rest ROM key, seen from a high front-3/4 camera."""
    set_action(rig, act)
    P = measure(sections)
    c = Vector(0.5 * (P.min(0) + P.max(0)))
    dvec = Vector((0.45, -1.0, 0.55)).normalized()
    aim_cam(cam, c + dvec * 46, c + Vector((0, 0, 1.0)), lens=35)
    paths, labels = [], []
    for f, label in keys:
        bpy.context.scene.frame_set(f)
        p = WORK / f'rom_{f:04d}.png'
        render_to(p, 520, 390, samples=16)
        paths.append(p)
        labels.append(f'f{f} {label}')
    tile(paths, 7, HERE / 'previews' / 'RigTest_ROM.png')
    SHEETS['RigTest_ROM.png'] = {'cols': 7, 'tile': [520, 390], 'labels': labels}
    rig.animation_data.action = None


def planted_intervals(name, f0, f1):
    """Frames during which each foot is planted, per attack."""
    if name == 'TailWhip':
        return PZ.whip_planted_intervals()
    if name == 'FrontStomp':
        imp = PZ.ATTACKS[name][0]['impact_frame']
        return {'FL': [(imp, f1)], 'FR': [(imp, f1)], 'HL': [(f0, f1)], 'HR': [(f0, f1)]}
    return {k: [(f0, f1)] for k in ('FL', 'FR', 'HL', 'HR')}


def planted_slide(rig, act, name):
    """Max horizontal/vertical drift (studs) of each foot while planted, over every
    frame of an attack, measured on the evaluated rig (after Blender's
    interpolation), relative to where the foot was when it was planted."""
    sc = bpy.context.scene
    set_action(rig, act)
    probes = {'FL': 'Hand_L_Toe2_2', 'FR': 'Hand_R_Toe2_2', 'HL': 'Foot_L_Toe2_2', 'HR': 'Foot_R_Toe2_2'}
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
    pos = {}
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        pos[f] = {k: (rig.matrix_world @ rig.pose.bones[b].head).copy() for k, b in probes.items()}
    worst = {k: [0.0, 0.0] for k in probes}
    for k, ivs in planted_intervals(name, f0, f1).items():
        for (a, b) in ivs:
            ref = pos[a][k]
            for f in range(a, b + 1):
                p = pos[f][k]
                worst[k][0] = max(worst[k][0], ((p.x - ref.x) ** 2 + (p.y - ref.y) ** 2) ** 0.5)
                worst[k][1] = max(worst[k][1], abs(p.z - ref.z))
    rig.animation_data.action = None
    return {k: {'max_horizontal': round(v[0], 4), 'max_vertical': round(v[1], 4)} for k, v in worst.items()}


ATTACK_VIEWS = {
    'default': (('front', (0.0, -1.0, 0.22), 44.0), ('3/4', (0.85, -0.8, 0.34), 48.0)),
    'TailWhip': (('front, high', (0.0, -1.0, 0.85), 52.0), ('3/4, high', (0.85, -0.8, 0.95), 56.0)),
}


def attack_tiles(rig, cam, sections, name):
    """Render windup / impact / recovery x (front, 3/4) for one attack; returns paths, labels."""
    sc = bpy.context.scene
    apply_pose(rig, {})
    P = measure(sections)
    c = Vector(0.5 * (P.min(0) + P.max(0))) + Vector((0, 0, 0.5))
    act = bpy.data.actions[name]
    set_action(rig, act)
    ph = PZ.attack_phase_frames(name)
    paths, labels = [], []
    for view, dvec, dist in ATTACK_VIEWS.get(name, ATTACK_VIEWS['default']):
        for phase in ('windup', 'impact', 'recovery'):
            sc.frame_set(ph[phase])
            dv = Vector(dvec).normalized()
            aim_cam(cam, c + dv * dist, c, lens=35)
            p = WORK / f'atk_{name}_{phase}_{view.replace("/", "").replace(", ", "_")}.png'
            render_to(p, 480, 360, samples=16)
            paths.append(p)
            labels.append(f'{name} {phase} f{ph[phase]} ({view})')
    rig.animation_data.action = None
    apply_pose(rig, {})
    return paths, labels


def attack_sheet(rig, sk, cam, sections):
    """AttackCheck: FireBreath / TailWhip / FrontStomp at windup, impact and
    recovery, front and 3/4 (one row per attack)."""
    paths, labels = [], []
    for name in PZ.ATTACKS:
        p, l = attack_tiles(rig, cam, sections, name)
        paths += p
        labels += l
    tile(paths, 6, HERE / 'previews' / 'AttackCheck.png')
    SHEETS['AttackCheck.png'] = {'cols': 6, 'tile': [480, 360], 'labels': labels}


def attack_videos(rig, cam, sections, only=None):
    """Short low-res Workbench mp4 per attack (3/4 view, textured, 24 fps)."""
    sc = bpy.context.scene
    apply_pose(rig, {})
    P = measure(sections)
    c = Vector(0.5 * (P.min(0) + P.max(0))) + Vector((0, 0, 0.5))
    made = []
    for name in PZ.ATTACKS:
        if only and name not in only:
            continue
        act = bpy.data.actions[name]
        set_action(rig, act)
        dv = Vector((0.8, -0.85, 0.34 if name != 'TailWhip' else 0.9)).normalized()
        aim_cam(cam, c + dv * (50 if name != 'TailWhip' else 58), c, lens=35)
        sc.render.engine = 'BLENDER_WORKBENCH'
        sh = sc.display.shading
        sh.light = 'STUDIO'
        sh.color_type = 'TEXTURE'
        sh.show_shadows = True
        sc.render.resolution_x, sc.render.resolution_y = 640, 360
        sc.render.fps = PZ.FPS
        try:
            sc.render.image_settings.media_type = 'VIDEO'
        except Exception:  # noqa: BLE001
            pass
        sc.render.image_settings.file_format = 'FFMPEG'
        sc.render.ffmpeg.format = 'MPEG4'
        sc.render.ffmpeg.codec = 'H264'
        try:
            sc.render.ffmpeg.constant_rate_factor = 'MEDIUM'
        except Exception:  # noqa: BLE001
            pass
        out = HERE / 'previews' / f'Attack_{name}.mp4'
        for old in (HERE / 'previews').glob(f'Attack_{name}*.mp4'):
            old.unlink()
        sc.render.filepath = str(HERE / 'previews' / f'Attack_{name}_')
        bpy.ops.render.render(animation=True)
        got = sorted((HERE / 'previews').glob(f'Attack_{name}_*.mp4'))
        if got:
            got[-1].replace(out)
            made.append(out.name)
        log('video', name, out.exists())
    try:
        sc.render.image_settings.media_type = 'IMAGE'
    except Exception:  # noqa: BLE001
        pass
    sc.render.image_settings.file_format = 'PNG'
    sc.render.resolution_x, sc.render.resolution_y = CAM.W, CAM.H
    rig.animation_data.action = None
    return made


def make_attack_actions(rig, sk):
    acts = []
    info = {}
    for name in PZ.ATTACKS:
        act = make_action(rig, name, PZ.attack_keys(sk, name))
        mk = act.pose_markers.new('Impact')
        mk.frame = PZ.ATTACKS[name][0]['impact_frame']
        acts.append(act)
        rig.animation_data.action = None
        data = PZ.attack_data(sk, name)
        data['phase_frames'] = PZ.attack_phase_frames(name)
        data['planted_feet_drift'] = planted_slide(rig, act, name)
        data['planted_feet'] = {'FireBreath': 'all four', 'FrontStomp': 'hind feet throughout; front feet from the impact frame on',
                                'TailWhip': 'front feet throughout; hind feet between their steps (see hind_steps / planted_intervals)'}[name]
        info[name] = data
        log('attack', name, 'impact', data['impact_frame'], 'drift', data['planted_feet_drift'])
    return acts, info


def write_sheet_labels():
    (WORK / 'sheet_labels.json').write_text(json.dumps(SHEETS, indent=1))


def rom_key_labels(sk):
    names = ['rest', 'front L leg lift', 'rest', 'front R leg lift', 'rest', 'hind L leg lift', 'rest',
             'hind R leg lift', 'rest', 'neck sweep L + head turn', 'neck sweep R + head turn', 'neck up',
             'neck down', 'rest', 'fire breath (jaw open, neck out)', 'rest', 'wings folded', 'wings spread',
             'flap up', 'flap down', 'flap up', 'rest', 'tail sweep L', 'tail sweep R', 'tail up', 'rest',
             'toes curl', 'toes spread', 'rest', 'blink', 'rest', 'blink', 'rest']
    keys = PZ.rom_keys(sk)
    return [(k[0], n) for k, n in zip(keys, names) if n != 'rest']


def write_reports(rig, sk, sections, tex_info, ref_pose_dims, attacks_info=None):
    polys = {sec: tri_count(ob) for sec, ob in sections.items()}
    (HERE / 'polygon-report.json').write_text(json.dumps({
        'sections_triangles': polys, 'total_triangles': sum(polys.values()),
        'limit_per_mesh': 20000, 'all_under_limit': all(v < 20000 for v in polys.values())}, indent=2))
    apply_pose(rig, {})
    P = measure(sections)
    bones = [{'name': n, 'parent': sk.parent[n], 'deform': True,
              'head': [round(float(x), 4) for x in sk.head[n]], 'tail': [round(float(x), 4) for x in sk.tail[n]]}
             for n in sk.names]
    ctrl = [{'name': b.name, 'parent': b.parent.name if b.parent else None, 'deform': False}
            for b in rig.data.bones if not b.use_deform]
    texs = []
    for sec, t in tex_info.items():
        for k in ('master', 'delivery'):
            p = TEXDIR / t[k]
            texs.append({'section': sec, 'file': f'textures/{t[k]}', 'size': MASTER_RES if k == 'master' else DELIVERY_RES,
                         'sha256': sha(p)})
    man = {
        'name': NAME, 'units': '1 Blender unit = 1 Roblox stud', 'facing': '-Y (Blender), Z up',
        'reference': {'file': 'source/4.webp', 'sha256': 'CD8ABD3A2B750906F0989BE291A6EE97732FDB4EBAA3234A8ACC884A12363006'},
        'rest_bounds_min': [round(float(v), 3) for v in P.min(0)], 'rest_bounds_max': [round(float(v), 3) for v in P.max(0)],
        'rest_dimensions': [round(float(v), 3) for v in (P.max(0) - P.min(0))],
        'reference_pose_measurements': ref_pose_dims,
        'sections': {sec: {'object': ob.name, 'triangles': tri_count(ob), 'vertices': len(ob.data.vertices)}
                     for sec, ob in sections.items()},
        'deform_bones': len(bones), 'bones': bones, 'control_bones': ctrl,
        'textures': texs,
        'actions': [a.name for a in bpy.data.actions if a.use_fake_user],
        'attacks': attacks_info or {},
        'animation_notes': 'Actions at 24 fps. Each attack action carries an Impact pose marker in the .blend; '
                           'FBX/GLB do not carry markers, so the impact frame/time and gameplay points are listed '
                           'here (Blender world studs: Z up, dragon faces -Y, +X = dragon left).',
    }
    (HERE / 'manifest.json').write_text(json.dumps(man, indent=2))




def reference_measurements(rig, sk, sections):
    P = measure(sections)
    W = {pb.name: rig.matrix_world @ pb.matrix for pb in rig.pose.bones}
    thumbs = []
    for s in 'LR':
        pb = rig.pose.bones[f'Wing_{s}_Thumb']
        thumbs.append(round(float((W[pb.name] @ Vector((0, pb.length, 0))).z), 3))
    snout = W['Head'] @ Vector((0, rig.pose.bones['Head'].length, 0))
    tail_tip = W['TailTip'] @ Vector((0, rig.pose.bones['TailTip'].length, 0))
    return {'height_max': round(float(P[:, 2].max()), 3), 'wing_thumb_tip_heights': thumbs,
            'snout_tip': [round(float(v), 3) for v in snout], 'tail_tip': [round(float(v), 3) for v in tail_tip]}


def full_main():
    clear_scene()
    sc = bpy.context.scene
    coll = bpy.data.collections.new(NAME)
    sc.collection.children.link(coll)
    objs, prims = build_parts(coll)
    sections = join_sections(objs, coll)
    rig, sk = build_armature(coll)
    bind(sections, rig)
    tex_info = texture_sections(sections, rig, sk)
    ref = PZ.reference_pose(sk)
    act_ref = make_action(rig, 'ReferencePose', [(1, ref), (2, ref)])
    act_rom = make_action(rig, 'RigTest_ROM', PZ.rom_keys(sk))
    rig.animation_data.action = None
    atk_acts, attacks_info = make_attack_actions(rig, sk)
    apply_pose(rig, ref)
    log('FK check (Blender vs numpy) max abs', round(check_fk(rig, sk, ref), 6))
    cam = setup_camera()
    setup_lights()
    g, _ = ground_and_backdrop()
    for o in [cam, g] + [o for o in bpy.data.objects if o.type == 'LIGHT']:
        to_review(o)
    (HERE / 'previews').mkdir(exist_ok=True)
    set_action(rig, act_ref)
    sc.frame_set(1)
    render_color(HERE / 'previews' / 'Reference_Match.png', samples=int(os.environ.get('DRAGON_FINAL_SAMPLES', '128')))
    render_mask(WORK / 'final_mask.png', list(sections.values()))
    ref_dims = reference_measurements(rig, sk, sections)
    log('reference-pose measurements', ref_dims)
    rig.animation_data.action = None
    if os.environ.get('DRAGON_LOOP') == '1':
        bpy.ops.wm.save_as_mainfile(filepath=str(WORK / 'loop.blend'))
        log('loop mode: stop after Reference_Match (saved _work/loop.blend)')
        return
    if os.environ.get('DRAGON_SKIP_EXTRAS') != '1':
        head_closeup(rig, ref, cam)
        restore_ref_cam(cam)
        turnaround(rig, sk, cam, sections)
        rig_bones_overlay(rig, sk, cam, sections)
        rom_sheet(rig, cam, act_rom, sections, rom_key_labels(sk))
        attack_sheet(rig, sk, cam, sections)
        attack_videos(rig, cam, sections)
        write_sheet_labels()
        restore_ref_cam(cam)
    export_all(rig, sections, [act_ref, act_rom] + atk_acts)
    write_reports(rig, sk, sections, tex_info, ref_dims, attacks_info)
    set_action(rig, act_ref)
    sc.frame_set(1)
    restore_ref_cam(cam)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE / f'{NAME}.blend'), compress=True)
    log('full build done')


# ------------------------------------------------------------------ main
def main():
    clear_scene()
    sc = bpy.context.scene
    coll = bpy.data.collections.new(NAME)
    sc.collection.children.link(coll)
    objs, prims = build_parts(coll)
    sections = join_sections(objs, coll)
    rig, sk = build_armature(coll)
    bind(sections, rig)
    pose = PZ.reference_pose(sk)
    apply_pose(rig, pose)
    log('FK check (Blender vs numpy) max abs', round(check_fk(rig, sk, pose), 6))
    setup_camera()
    render_mask(WORK / 'probe_mask.png', list(sections.values()))
    setup_lights()
    ground_and_backdrop()
    render_color(WORK / 'probe_render.png', samples=int(os.environ.get('DRAGON_SAMPLES', '24')))
    total = sum(tri_count(o) for o in sections.values())
    log('total tris', total)
    if not PROBE:
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE / f'{NAME}.blend'))
    log('done')


def attack_update_main(names):
    """DRAGON_STAGE=attack DRAGON_ATTACK=TailWhip: rebuild one (or more) attack
    actions in the saved Dragon.blend and re-deliver only what depends on them:
    the clip FBX, the GLB (all actions), manifest attacks.<name>, that attack's
    row of AttackCheck.png and its mp4. The model, rig, other actions and the
    rest-mesh FBX are untouched."""
    global REVIEW
    bpy.ops.wm.open_mainfile(filepath=str(HERE / f'{NAME}.blend'))
    REVIEW = bpy.data.collections.get('REVIEW_ONLY')
    rig = bpy.data.objects[f'{NAME}_Rig']
    sections = {s: bpy.data.objects[f'{NAME}_{s}'] for s in SECTIONS if f'{NAME}_{s}' in bpy.data.objects}
    cam = bpy.data.objects['RefCam']
    sk = RG.Skeleton()
    rig.animation_data_create()
    rig.animation_data.action = None
    man = json.loads((HERE / 'manifest.json').read_text())
    for name in names:
        old = bpy.data.actions.get(name)
        if old:
            bpy.data.actions.remove(old)
        act = make_action(rig, name, PZ.attack_keys(sk, name))
        mk = act.pose_markers.new('Impact')
        mk.frame = PZ.ATTACKS[name][0]['impact_frame']
        rig.animation_data.action = None
        data = PZ.attack_data(sk, name)
        data['phase_frames'] = PZ.attack_phase_frames(name)
        data['planted_feet_drift'] = planted_slide(rig, act, name)
        data['planted_feet'] = {'FireBreath': 'all four', 'FrontStomp': 'hind feet throughout; front feet from the impact frame on',
                                'TailWhip': 'front feet throughout; hind feet between their steps (see hind_steps / planted_intervals)'}[name]
        man.setdefault('attacks', {})[name] = data
        log('attack', name, 'impact', data['impact_frame'], 'drift', data['planted_feet_drift'])
    man['actions'] = [a.name for a in bpy.data.actions if a.use_fake_user]
    (HERE / 'manifest.json').write_text(json.dumps(man, indent=2))
    # exports: the changed clips + the GLB with every action
    fbxdir = HERE / 'exports' / 'fbx'
    common = dict(use_selection=True, apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE',
                  axis_forward='-Z', axis_up='Y', add_leaf_bones=False, use_armature_deform_only=True,
                  primary_bone_axis='Y', secondary_bone_axis='X', mesh_smooth_type='OFF', use_mesh_modifiers=False)

    def select(obs):
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for o in obs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = rig
    for name in names:
        act = bpy.data.actions[name]
        set_action(rig, act)
        select([rig])
        bpy.ops.export_scene.fbx(filepath=str(fbxdir / f'{NAME}_{name}.fbx'), object_types={'ARMATURE'},
                                 bake_anim=True, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
                                 bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0, **common)
    order = ['ReferencePose', 'RigTest_ROM'] + list(PZ.ATTACKS)
    acts = [bpy.data.actions[n] for n in order if n in bpy.data.actions]
    rig.animation_data.action = None
    for tr in list(rig.animation_data.nla_tracks):
        rig.animation_data.nla_tracks.remove(tr)
    for act in acts:
        tr = rig.animation_data.nla_tracks.new()
        tr.name = act.name
        st = tr.strips.new(act.name, int(act.frame_range[0]), act)
        st.name = act.name
    for pb in rig.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    select(list(sections.values()) + [rig])
    bpy.ops.export_scene.gltf(filepath=str(HERE / 'exports' / 'glb' / f'{NAME}.glb'), export_format='GLB',
                              use_selection=True, export_animations=True, export_animation_mode='NLA_TRACKS',
                              export_skins=True, export_def_bones=True, export_normals=True, export_apply=False,
                              export_yup=True)
    for tr in list(rig.animation_data.nla_tracks):
        rig.animation_data.nla_tracks.remove(tr)
    # previews: that attack's AttackCheck row (pasted into the existing sheet) + its mp4
    sheet = HERE / 'previews' / 'AttackCheck.png'
    img = load_px(sheet)
    labels = []
    gap, tw, th = 6, 480, 360
    for r, name in enumerate(PZ.ATTACKS):
        if name in names:
            paths, labs = attack_tiles(rig, cam, sections, name)
            for c, p in enumerate(paths):
                y = gap + r * (th + gap)
                x = gap + c * (tw + gap)
                img[y:y + th, x:x + tw] = load_px(p)
        else:
            ph = PZ.attack_phase_frames(name)
            labs = [f'{name} {phase} f{ph[phase]} ({view})' for view, _, _ in ATTACK_VIEWS.get(name, ATTACK_VIEWS['default'])
                    for phase in ('windup', 'impact', 'recovery')]
        labels += labs
    save_px(img, sheet)
    SHEETS['AttackCheck.png'] = {'cols': 6, 'tile': [tw, th], 'labels': labels}
    write_sheet_labels()
    attack_videos(rig, cam, sections, only=names)
    set_action(rig, bpy.data.actions['ReferencePose'])
    bpy.context.scene.frame_set(1)
    restore_ref_cam(cam)
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE / f'{NAME}.blend'), compress=True)
    log('attack update done', names)


GAME_DIR = HERE / 'exports' / 'game'
S_SWAP = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def cf12(m):
    """AnimationData 12-number transform: S@m@S (Y/Z swap), [x,y,z,R00..R22], 7 places."""
    m = S_SWAP @ m @ S_SWAP
    return [round(x, 7) for x in [m[0][3], m[1][3], m[2][3], m[0][0], m[0][1], m[0][2], m[1][0], m[1][1], m[1][2],
                                  m[2][0], m[2][1], m[2][2]]]


def to_studio(v):
    return [round(-float(v[0]), 4), round(float(v[2]), 4), round(float(v[1]), 4)]


def evaluated_min_z(sections):
    deps = bpy.context.evaluated_depsgraph_get()
    mz = 1e9
    for ob in sections.values():
        e = ob.evaluated_get(deps)
        me = e.to_mesh()
        co = np.zeros(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        M = np.array(ob.matrix_world)
        z = co @ M[2, :3] + M[2, 3]
        mz = min(mz, float(z.min()))
        e.to_mesh_clear()
    return mz


def ground_clearance_pass(rig, act, sections, floor=-0.05):
    """Raise the Root per frame so no vertex goes below `floor` (keys every frame)."""
    sc = bpy.context.scene
    set_action(rig, act)
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
    worst = 0.0
    lifts = {}
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        mz = evaluated_min_z(sections)
        if mz < floor:
            pb = rig.pose.bones['Root']
            lift = floor - mz
            pb.location = pb.location + Vector((0, 0, lift))
            pb.keyframe_insert('location', frame=f, group='Root')
            lifts[f] = round(lift, 4)
            bpy.context.view_layer.update()
            sc.frame_set(f)
            mz = evaluated_min_z(sections)
        worst = min(worst, mz)
    rig.animation_data.action = None
    return {'min_vertex_z': round(worst, 4), 'root_lifts': lifts}


def clip_min_z(rig, act, sections, step=2):
    sc = bpy.context.scene
    set_action(rig, act)
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
    worst = 1e9
    for f in list(range(f0, f1 + 1, step)) + [f1]:
        sc.frame_set(f)
        worst = min(worst, evaluated_min_z(sections))
    rig.animation_data.action = None
    return round(worst, 4)


def walk_drift(rig, act):
    """Planted-foot error vs the ideal ground-locked path (in-place walk: planted
    feet move backward at exactly the walk speed)."""
    sc = bpy.context.scene
    set_action(rig, act)
    n = PZ.GAME_CLIPS['Walk'][0]
    probes = {'FL': 'Hand_L_Toe2_2', 'FR': 'Hand_R_Toe2_2', 'HL': 'Foot_L_Toe2_2', 'HR': 'Foot_R_Toe2_2'}
    rest = {k: rig.data.bones[b].head_local.copy() for k, b in probes.items()}
    worst = {k: 0.0 for k in probes}
    for f in range(n + 1):
        sc.frame_set(f + 1)
        t = f / n
        for k, b in probes.items():
            dx, dy, lift, planted = PZ.walk_foot(k, t)
            if not planted:
                continue
            exp = rest[k] + Vector((dx, dy, 0.0))
            worst[k] = max(worst[k], (rig.pose.bones[b].head - exp).length)
    rig.animation_data.action = None
    return {k: round(v, 4) for k, v in worst.items()}


def sample_clip(rig, act, n_intervals, loop):
    sc = bpy.context.scene
    set_action(rig, act)
    deform = [pb for pb in rig.pose.bones if rig.data.bones[pb.name].use_deform]
    frames = []
    for f in range(n_intervals + 1):
        sc.frame_set(f + 1)
        frames.append({'time': round(f / 24, 7), 'transforms': {pb.name: cf12(pb.matrix_basis) for pb in deform}})
    rig.animation_data.action = None
    return {'duration': round(n_intervals / 24, 7), 'loop': loop, 'frames': frames}


def workbench_setup(w, h):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'TEXTURE'
    sh.show_shadows = True
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100


def game_clips_sheet(rig, cam, sections, names):
    sc = bpy.context.scene
    apply_pose(rig, {})
    P = measure(sections)
    c = Vector(0.5 * (P.min(0) + P.max(0))) + Vector((0, 0, 0.5))
    dv = Vector((0.8, -0.85, 0.34)).normalized()
    paths, labels = [], []
    for name in names:
        act = bpy.data.actions[name]
        set_action(rig, act)
        n = int(act.frame_range[1] - act.frame_range[0])
        picks = sorted({1 + round(n * u) for u in (0.0, 0.25, 0.5, 0.75, 1.0)})
        if name == 'Hit':
            picks = [1, 3, 5, 8, n + 1]
        for f in picks[:5]:
            sc.frame_set(f)
            aim_cam(cam, c + dv * (50 if name != 'Death' else 54), c, lens=35)
            workbench_setup(400, 300)
            sc.render.image_settings.file_format = 'PNG'
            p = WORK / f'game_{name}_{f:03d}.png'
            sc.render.filepath = str(p)
            bpy.ops.render.render(write_still=True)
            paths.append(p)
            labels.append(f'{name} f{f - 1} ({(f - 1) / 24:.2f}s)')
        rig.animation_data.action = None
    tile(paths, 5, HERE / 'previews' / 'GameClips.png')
    SHEETS['GameClips.png'] = {'cols': 5, 'tile': [400, 300], 'labels': labels}
    sc.render.resolution_x, sc.render.resolution_y = CAM.W, CAM.H


def clip_video(rig, cam, sections, name):
    sc = bpy.context.scene
    apply_pose(rig, {})
    P = measure(sections)
    c = Vector(0.5 * (P.min(0) + P.max(0))) + Vector((0, 0, 0.5))
    act = bpy.data.actions[name]
    set_action(rig, act)
    dv = Vector((0.8, -0.85, 0.34)).normalized()
    aim_cam(cam, c + dv * 52, c, lens=35)
    workbench_setup(640, 360)
    sc.render.fps = 24
    try:
        sc.render.image_settings.media_type = 'VIDEO'
    except Exception:  # noqa: BLE001
        pass
    sc.render.image_settings.file_format = 'FFMPEG'
    sc.render.ffmpeg.format = 'MPEG4'
    sc.render.ffmpeg.codec = 'H264'
    out = HERE / 'previews' / f'Clip_{name}.mp4'
    for old in (HERE / 'previews').glob(f'Clip_{name}*.mp4'):
        old.unlink()
    sc.render.filepath = str(HERE / 'previews' / f'Clip_{name}_')
    bpy.ops.render.render(animation=True)
    got = sorted((HERE / 'previews').glob(f'Clip_{name}_*.mp4'))
    if got:
        got[-1].replace(out)
    try:
        sc.render.image_settings.media_type = 'IMAGE'
    except Exception:  # noqa: BLE001
        pass
    sc.render.image_settings.file_format = 'PNG'
    sc.render.resolution_x, sc.render.resolution_y = CAM.W, CAM.H
    rig.animation_data.action = None
    return out.exists()


def point_entry(rig, bone, offset_local, frame):
    """Point on `bone` (local offset, Blender axes) in root/armature space at `frame`."""
    bpy.context.scene.frame_set(frame)
    M = rig.pose.bones[bone].matrix
    p = M @ Vector(offset_local)
    return {'bone': bone, 'offset': [round(float(v), 4) for v in offset_local],
            'rootAtImpact': [round(float(v), 4) for v in p], 'rootAtImpactStudio': to_studio(p)}


def boss_game_data(rig, sk, man, sections):
    sc = bpy.context.scene
    A = man['attacks']
    out = {'attacks': {}}
    tsec = lambda f: round((f - 1) / 24, 4)      # action frame -> seconds from clip start
    # FireBreath
    fb = A['FireBreath']
    act = bpy.data.actions['FireBreath']
    set_action(rig, act)
    imp = fb['impact_frame']
    off = fb['FireOrigin']['local']
    e = {'duration': tsec(fb['frames'][1]), 'warnStart': tsec(7), 'impact': tsec(imp),
         'activeEnd': tsec(fb['hold_frames'][1]), 'recoveryEnd': tsec(fb['frames'][1]),
         'points': {'FireOrigin': point_entry(rig, 'Head', off, imp)}}
    samples = []
    for s in fb['breath']:
        samples.append({'time': tsec(s['frame']), 'root': s['origin'], 'dir': s['direction'],
                         'rootStudio': to_studio(s['origin']), 'dirStudio': to_studio(s['direction'])})
    e['points']['FireOrigin']['samples'] = samples
    d0 = fb['breath'][0]['direction']
    e['directionAtImpact'] = d0
    e['directionAtImpactStudio'] = to_studio(d0)
    out['attacks']['FireBreath'] = e
    # TailWhip
    tw = A['TailWhip']
    act = bpy.data.actions['TailWhip']
    set_action(rig, act)
    imp = tw['impact_frame']
    arc = tw['spade_arc']
    e = {'duration': tsec(tw['frames'][1]), 'warnStart': tsec(8), 'impact': tsec(imp),
         'activeEnd': tsec(arc['end_frame']), 'recoveryEnd': tsec(66),
         'points': {'SpadeTip': point_entry(rig, 'TailTip', (0.0, 2.6, 0.0), imp)}}
    e['points']['SpadeTip']['arc'] = {
        'pivot': arc['pivot'], 'pivotStudio': to_studio(arc['pivot']),
        'startAngleDeg': arc['start_angle_deg'], 'endAngleDeg': arc['end_angle_deg'], 'sweepDeg': arc['sweep_deg'],
        'radius': arc['radius_fit'], 'radiusMax': arc['radius_max'], 'heightRange': arc['height_range'],
        'startTime': tsec(arc['start_frame']), 'endTime': tsec(arc['end_frame']),
        'angleConvention': 'Blender axes: degrees about +Z from +Y (straight back), positive toward +X (dragon left). '
                           'In Studio axes (-X, Z, Y): about +Y from +Z, positive toward -X.'}
    bpy.context.scene.frame_set(imp)
    W = rig.pose.bones['TailTip'].matrix
    tip = W @ Vector((0, 2.6, 0))
    bpy.context.scene.frame_set(imp + 1)
    tip2 = rig.pose.bones['TailTip'].matrix @ Vector((0, 2.6, 0))
    dv = (tip2 - tip).normalized()
    e['directionAtImpact'] = [round(float(v), 4) for v in dv]
    e['directionAtImpactStudio'] = to_studio(dv)
    out['attacks']['TailWhip'] = e
    # FrontStomp
    fs = A['FrontStomp']
    act = bpy.data.actions['FrontStomp']
    set_action(rig, act)
    imp = fs['impact_frame']
    pts = {}
    for s, key in (('L', 'LeftFrontImpact'), ('R', 'RightFrontImpact')):
        g = fs['impact_points'][f'Front_{s}']['ground_point']
        bpy.context.scene.frame_set(imp)
        Mh = rig.pose.bones[f'Hand_{s}'].matrix
        local = Mh.inverted() @ Vector(g)
        pts[key] = point_entry(rig, f'Hand_{s}', tuple(local), imp)
    e = {'duration': tsec(fs['frames'][1]), 'warnStart': tsec(8), 'impact': tsec(imp), 'activeEnd': tsec(imp),
         'recoveryEnd': tsec(40), 'points': pts}
    out['attacks']['FrontStomp'] = e
    rig.animation_data.action = None
    # body metrics (rest pose)
    apply_pose(rig, {})
    Pw = measure(sections)
    out['rootHeight'] = 0.0
    out['rootNote'] = ('The Root bone sits on the ground under the body centre (z = 0); the Hips joint is at '
                       f"{round(float(sk.head['Hips'][2]), 3)} studs.")
    out['hipsHeight'] = round(float(sk.head['Hips'][2]), 3)
    out['height'] = round(float(Pw[:, 2].max()), 3)
    # footprint: body, legs and head only (vertices mostly weighted to wing / tail bones excluded)
    rad = 0.0
    for ob in sections.values():
        names = {g.index: g.name for g in ob.vertex_groups}
        M = ob.matrix_world
        for v in ob.data.vertices:
            if not v.groups:
                continue
            gmax = max(v.groups, key=lambda g: g.weight)
            nm = names[gmax.group]
            if nm.startswith(('Wing_', 'Tail')):
                continue
            w = M @ v.co
            rad = max(rad, (w.x ** 2 + w.y ** 2) ** 0.5)
    out['footprintRadius'] = round(rad, 3)
    out['footprintNote'] = 'max horizontal distance from the origin of body/leg/head vertices (wings and tail excluded)'
    out['wingspanRest'] = round(float(Pw[:, 0].max() - Pw[:, 0].min()), 3)
    out['lengthRest'] = round(float(Pw[:, 1].max() - Pw[:, 1].min()), 3)
    return out


def studio_fbx(rig, sections):
    """exports/game/Dragon_Studio.fbx: rest mesh + deform armature, one mesh per section
    named after the section, materials Dragon_<Section> on the 1024 delivery maps."""
    GAME_DIR.mkdir(parents=True, exist_ok=True)
    fbm = GAME_DIR / f'{NAME}_Studio.fbm'
    fbm.mkdir(exist_ok=True)
    rig.animation_data.action = None
    for tr in list(rig.animation_data.nla_tracks):
        rig.animation_data.nla_tracks.remove(tr)
    apply_pose(rig, {})
    swapped = []
    for sec, ob in sections.items():
        src = TEXDIR / f'{NAME}_{sec}_BaseColor.png'
        img = bpy.data.images.load(str(src))
        img.name = f'{NAME}_{sec}_BaseColor'
        m = ob.data.materials[0]
        m.name = f'{NAME}_{sec}'
        tex = [n for n in m.node_tree.nodes if n.type == 'TEX_IMAGE'][0]
        swapped.append((ob, ob.name, tex, tex.image))
        tex.image = img
        ob.name = sec
        shutil.copy2(src, fbm / src.name)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in list(sections.values()) + [rig]:
        o.select_set(True)
    bpy.context.view_layer.objects.active = rig
    path = GAME_DIR / f'{NAME}_Studio.fbx'
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, object_types={'ARMATURE', 'MESH'},
                             apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE', axis_forward='-Z',
                             axis_up='Y', add_leaf_bones=False, use_armature_deform_only=True, bake_anim=False,
                             primary_bone_axis='Y', secondary_bone_axis='X', mesh_smooth_type='OFF',
                             use_mesh_modifiers=False, path_mode='COPY', embed_textures=True)
    for ob, name, tex, old in swapped:
        ob.name = name
        tex.image = old
    return path


def game_main():
    """DRAGON_STAGE=game: the Studio game package (see plans/BOSS_GAME_PACKAGE_SPEC.md)."""
    global REVIEW
    bpy.ops.wm.open_mainfile(filepath=str(HERE / f'{NAME}.blend'))
    REVIEW = bpy.data.collections.get('REVIEW_ONLY')
    rig = bpy.data.objects[f'{NAME}_Rig']
    sections = {s: bpy.data.objects[f'{NAME}_{s}'] for s in SECTIONS if f'{NAME}_{s}' in bpy.data.objects}
    cam = bpy.data.objects['RefCam']
    sk = RG.Skeleton()
    rig.animation_data_create()
    rig.animation_data.action = None
    for tr in list(rig.animation_data.nla_tracks):
        rig.animation_data.nla_tracks.remove(tr)
    man = json.loads((HERE / 'manifest.json').read_text(encoding='utf-8'))
    checks = {}
    # attacks re-keyed at 24 fps so their first/last frames are exactly the rest (= Idle start) pose
    for name in PZ.ATTACKS:
        old = bpy.data.actions.get(name)
        if old:
            bpy.data.actions.remove(old)
        act = make_action(rig, name, PZ.attack_keys(sk, name))
        act.pose_markers.new('Impact').frame = PZ.ATTACKS[name][0]['impact_frame']
        rig.animation_data.action = None
        data = PZ.attack_data(sk, name)
        data['phase_frames'] = PZ.attack_phase_frames(name)
        data['planted_feet_drift'] = planted_slide(rig, act, name)
        data['planted_feet'] = {'FireBreath': 'all four', 'FrontStomp': 'hind feet throughout; front feet from the impact frame on',
                                'TailWhip': 'front feet throughout; hind feet between their steps (see hind_steps / planted_intervals)'}[name]
        man['attacks'][name] = data
        log('attack', name, 'drift', data['planted_feet_drift'])
    # new game clips
    for name, (n, loop) in PZ.GAME_CLIPS.items():
        old = bpy.data.actions.get(name)
        if old:
            bpy.data.actions.remove(old)
        act = make_action(rig, name, PZ.game_clip_keys(sk, name))
        rig.animation_data.action = None
        log('clip', name, n, 'frames')
    checks['deathGround'] = ground_clearance_pass(rig, bpy.data.actions['Death'], sections)
    checks['walkPlantedDrift'] = walk_drift(rig, bpy.data.actions['Walk'])
    checks['clipMinVertexZ'] = {n: clip_min_z(rig, bpy.data.actions[n], sections) for n in ('Idle', 'Walk', 'Hit', 'Death')}
    log('checks', checks)
    # AnimationData.json
    GAME_DIR.mkdir(parents=True, exist_ok=True)
    bones = {}
    for b in rig.data.bones:
        if not b.use_deform:
            continue
        bones[b.name] = {'parent': b.parent.name if b.parent else None,
                         'rest': cf12(b.parent.matrix_local.inverted() @ b.matrix_local if b.parent else b.matrix_local)}
    clips = {}
    for name, (n, loop) in PZ.GAME_CLIPS.items():
        clips[name] = sample_clip(rig, bpy.data.actions[name], n, loop)
    for name in PZ.ATTACKS:
        n = PZ.ATTACKS[name][0]['frames'] - 1
        clips[name] = sample_clip(rig, bpy.data.actions[name], n, False)
    stride = PZ.walk_stride()
    walk_dur = PZ.GAME_CLIPS['Walk'][0] / 24
    anim = {'id': 'dragon', 'fps': 24, 'bones': bones, 'clips': clips,
            'motion': {'strideLength': round(stride, 4), 'nominalSpeed': round(stride / walk_dur, 4)}}
    (GAME_DIR / 'AnimationData.json').write_text(json.dumps(anim, separators=(',', ':')), encoding='utf-8')
    # BossGameData.json
    bgd = boss_game_data(rig, sk, man, sections)
    bgd['motion'] = anim['motion']
    bgd['clips'] = {n: {'duration': c['duration'], 'loop': c['loop'], 'frames': len(c['frames'])} for n, c in clips.items()}
    bgd['checks'] = checks
    (GAME_DIR / 'BossGameData.json').write_text(json.dumps(bgd, indent=2), encoding='utf-8')
    man['actions'] = [a.name for a in bpy.data.actions if a.use_fake_user]
    man['game_package'] = {'animation_data': 'exports/game/AnimationData.json', 'boss_game_data': 'exports/game/BossGameData.json',
                           'studio_fbx': f'exports/game/{NAME}_Studio.fbx', 'checks': checks, 'motion': anim['motion']}
    (HERE / 'manifest.json').write_text(json.dumps(man, indent=2), encoding='utf-8')
    # clip FBXs (armature only) for the attacks and the new clips, GLB with every action
    fbxdir = HERE / 'exports' / 'fbx'
    common = dict(use_selection=True, apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE',
                  axis_forward='-Z', axis_up='Y', add_leaf_bones=False, use_armature_deform_only=True,
                  primary_bone_axis='Y', secondary_bone_axis='X', mesh_smooth_type='OFF', use_mesh_modifiers=False)

    def select(obs):
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for o in obs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = rig
    for name in list(PZ.ATTACKS) + list(PZ.GAME_CLIPS):
        set_action(rig, bpy.data.actions[name])
        select([rig])
        bpy.ops.export_scene.fbx(filepath=str(fbxdir / f'{NAME}_{name}.fbx'), object_types={'ARMATURE'},
                                 bake_anim=True, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
                                 bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0, **common)
    order = ['ReferencePose', 'RigTest_ROM'] + list(PZ.GAME_CLIPS) + list(PZ.ATTACKS)
    rig.animation_data.action = None
    for nme in order:
        act = bpy.data.actions[nme]
        tr = rig.animation_data.nla_tracks.new()
        tr.name = nme
        st = tr.strips.new(nme, int(act.frame_range[0]), act)
        st.name = nme
    apply_pose(rig, {})
    select(list(sections.values()) + [rig])
    bpy.ops.export_scene.gltf(filepath=str(HERE / 'exports' / 'glb' / f'{NAME}.glb'), export_format='GLB',
                              use_selection=True, export_animations=True, export_animation_mode='NLA_TRACKS',
                              export_skins=True, export_def_bones=True, export_normals=True, export_apply=False,
                              export_yup=True)
    for tr in list(rig.animation_data.nla_tracks):
        rig.animation_data.nla_tracks.remove(tr)
    # previews: GameClips.png + one mp4 per new clip
    game_clips_sheet(rig, cam, sections, list(PZ.GAME_CLIPS))
    write_sheet_labels()
    for name in PZ.GAME_CLIPS:
        log('video', name, clip_video(rig, cam, sections, name))
    # save the blend (new actions), then write the Studio FBX from the saved state
    set_action(rig, bpy.data.actions['ReferencePose'])
    bpy.context.scene.frame_set(1)
    restore_ref_cam(cam)
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE / f'{NAME}.blend'), compress=True)
    rig.animation_data.action = None
    log('studio fbx', studio_fbx(rig, sections))
    log('game package done')


def previews_main():
    """DRAGON_STAGE=previews: reopen Dragon.blend and re-render the review sheets
    only (head close-up, turnaround, ROM sheet, AttackCheck). The model, rig,
    actions and exports are not touched and the .blend is not re-saved."""
    global REVIEW
    bpy.ops.wm.open_mainfile(filepath=str(HERE / f'{NAME}.blend'))
    REVIEW = bpy.data.collections.get('REVIEW_ONLY')
    rig = bpy.data.objects[f'{NAME}_Rig']
    sections = {s: bpy.data.objects[f'{NAME}_{s}'] for s in SECTIONS if f'{NAME}_{s}' in bpy.data.objects}
    cam = bpy.data.objects['RefCam']
    sk = RG.Skeleton()
    act_rom = bpy.data.actions['RigTest_ROM']
    rig.animation_data.action = None
    head_closeup(rig, PZ.reference_pose(sk), cam)
    restore_ref_cam(cam)
    turnaround(rig, sk, cam, sections)
    rom_sheet(rig, cam, act_rom, sections, rom_key_labels(sk))
    attack_sheet(rig, sk, cam, sections)
    attack_videos(rig, cam, sections)
    write_sheet_labels()
    log('previews re-rendered')


if __name__ == '__main__':
    if PROBE:
        main()
    elif STAGE == 'previews':
        previews_main()
    elif STAGE == 'game':
        game_main()
    elif STAGE == 'attack':
        attack_update_main([a for a in os.environ.get('DRAGON_ATTACK', 'TailWhip').split(',') if a])
    else:
        full_main()

