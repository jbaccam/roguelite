"""bpy helpers for the Frost Cyclops generator (Blender 5.2, background mode)."""
import math

import bpy
import numpy as np
from mathutils import Matrix, Vector


def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.armatures,
                  bpy.data.actions, bpy.data.cameras, bpy.data.lights, bpy.data.node_groups):
        for item in list(block):
            block.remove(item)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)


def collection(name, parent=None):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    par = parent or bpy.context.scene.collection
    if c.name not in [x.name for x in par.children]:
        par.children.link(c)
    return c


def mesh_object(name, V, F, coll, mats=None, face_mat=None):
    me = bpy.data.meshes.new(name)
    V = np.asarray(V, float)
    F = [tuple(int(i) for i in f) for f in F]
    me.from_pydata(V.tolist(), [], F)
    me.validate(clean_customdata=False)
    me.update()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    for m in mats or []:
        me.materials.append(m)
    if face_mat is not None:
        me.polygons.foreach_set('material_index', np.asarray(face_mat, np.int32))
    me.polygons.foreach_set('use_smooth', np.zeros(len(me.polygons), bool))
    return ob


def activate(ob):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def apply_modifiers(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)
    return ob


def decimate(ob, target_tris, vgroup=None, vg_factor=1.0, planar=None):
    ntri = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    if ntri > target_tris:
        m = ob.modifiers.new('decimate', 'DECIMATE')
        m.decimate_type = 'COLLAPSE'
        m.ratio = max(1e-4, target_tris / ntri)
        m.use_collapse_triangulate = True
        if vgroup:
            m.vertex_group = vgroup
            m.vertex_group_factor = vg_factor
            # Blender adds collapse cost where the (inverted) weight is LOW, so invert:
            # detail weight 1 -> protected, 0 -> decimated normally.
            m.invert_vertex_group = True
        apply_modifiers(ob)
    if planar:
        m = ob.modifiers.new('planar', 'DECIMATE')
        m.decimate_type = 'DISSOLVE'
        m.angle_limit = math.radians(planar)
        m.use_dissolve_boundaries = False
        apply_modifiers(ob)
    ob.data.polygons.foreach_set('use_smooth', np.zeros(len(ob.data.polygons), bool))
    return ob


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def mesh_arrays(ob):
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get('co', co)
    faces = [tuple(p.vertices) for p in me.polygons]
    return co.reshape(n, 3), faces


def set_coords(ob, V):
    ob.data.vertices.foreach_set('co', np.asarray(V, float).ravel())
    ob.data.update()


def join(objs, name):
    activate(objs[0])
    for o in objs:
        o.select_set(True)
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def face_attribute(ob, name, values, domain='FACE', dtype='FLOAT'):
    me = ob.data
    if name in me.attributes:
        me.attributes.remove(me.attributes[name])
    a = me.attributes.new(name, dtype, domain)
    a.data.foreach_set('value', np.asarray(values, np.float32))
    return a


def smart_uv(ob, angle=66.0, margin=0.006):
    activate(ob)
    if not ob.data.uv_layers:
        ob.data.uv_layers.new(name='UVMap')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, area_weight=0.0,
                             scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    bpy.ops.object.mode_set(mode='OBJECT')


def frame_matrix(head, y_axis, z_hint):
    y = Vector(y_axis).normalized()
    z = Vector(z_hint)
    z = (z - y * z.dot(y)).normalized()
    x = y.cross(z)
    M = Matrix((x, y, z)).transposed().to_4x4()
    M.translation = Vector(head)
    return M


def camera_from_refcam(cam_ob, rc):
    R = Vector(rc.R)
    U = Vector(rc.U)
    F = Vector(rc.F)
    M = Matrix((R, U, -F)).transposed().to_4x4()
    M.translation = Vector(rc.C)
    cam_ob.matrix_world = M
    cam_ob.data.sensor_fit = 'VERTICAL'
    cam_ob.data.sensor_height = 36.0
    cam_ob.data.lens = rc.f * 36.0 / 1448.0
    cam_ob.data.shift_x = 0.0
    cam_ob.data.shift_y = 0.0
    cam_ob.data.clip_start = 0.5
    cam_ob.data.clip_end = 500.0


def enable_gpu():
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
    except KeyError:
        return 'CPU'
    for dev_type in ('OPTIX', 'CUDA'):
        try:
            prefs.compute_device_type = dev_type
            prefs.get_devices()
            ok = False
            for d in prefs.devices:
                d.use = d.type == dev_type
                ok = ok or d.use
            if ok:
                bpy.context.scene.cycles.device = 'GPU'
                return dev_type
        except Exception:
            continue
    bpy.context.scene.cycles.device = 'CPU'
    return 'CPU'


def srgb(*c):
    def lin(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return tuple(lin(v) for v in c)


def image_pixels(img):
    w, h = img.size
    buf = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(buf)
    return buf.reshape(h, w, 4)


def set_image_pixels(img, arr):
    img.pixels.foreach_set(np.ascontiguousarray(arr, np.float32).ravel())
    img.update()
