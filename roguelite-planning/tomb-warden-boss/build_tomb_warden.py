"""Tomb Warden generator (Blender 5.2, headless):

    blender -b --factory-startup --threads 4 --python-exit-code 1 --python build_tomb_warden.py

TW_STAGE=shape  geometry + rig + weights + flat-colour shape review (fast loop)
TW_STAGE=motion shape + clip solves + motion checks (no bake, no exports)
TW_STAGE=full   (default) everything: one atlas bake, clips, checks, game
                package, previews and TombWarden.blend.

Self-contained: imports only the tw_*.py modules in this folder.
"""
import json
import math
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bpy                                   # noqa: E402
import numpy as np                           # noqa: E402
from mathutils import Matrix, Vector         # noqa: E402

import tw_design as D                        # noqa: E402
import tw_motion as M                        # noqa: E402
import tw_paint as PT                        # noqa: E402
import tw_sdf as S                           # noqa: E402
import tw_solve as SV                        # noqa: E402

STAGE = os.environ.get('TW_STAGE', 'full')
NAME = 'TombWarden'
SECTIONS = ['Body', 'Cloth', 'Mask', 'LeftFist', 'RightFist', 'EyeGlow']
TARGET_TRIS = {'Body': 7600, 'Mask': 1300, 'LeftFist': 1800, 'RightFist': 1800}
TEX_MASTER, TEX_DELIVERY = 2048, 1024
WORK = HERE / '_work'
TEXD = HERE / 'textures'
PREV = HERE / 'previews'
for d in (WORK, TEXD, PREV):
    d.mkdir(exist_ok=True)
T0 = time.time()


def log(*a):
    print('[TW %6.1fs]' % (time.time() - T0), *a, flush=True)


# ============================================================== bpy helpers
def collection(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(c)
    return c


def activate(ob):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def new_mesh(name, V, F, col):
    V = np.asarray(V, float) * D.SC                     # design units -> real studs at the Blender boundary
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in V], [], [tuple(map(int, f)) for f in F])
    me.update()
    me.validate()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob


def decimate(ob, target):
    n = tris(ob)
    if n <= target:
        return
    activate(ob)
    md = ob.modifiers.new('dec', 'DECIMATE')
    md.decimate_type = 'COLLAPSE'
    md.ratio = target / n
    md.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=md.name)


def dverts(ob):
    """Mesh vertices in design units."""
    return verts(ob) / D.SC


def verts(ob):
    a = np.empty(len(ob.data.vertices) * 3)
    ob.data.vertices.foreach_get('co', a)
    return a.reshape(-1, 3)


def edges(ob):
    a = np.empty(len(ob.data.edges) * 2, np.int64)
    ob.data.edges.foreach_get('vertices', a)
    return a.reshape(-1, 2)


def flat_mat(name, rgb):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*PT.srgb_to_lin(rgb), 1.0)
    return m


# ================================================================= geometry
def build_body(col):
    prims = D.body_prims()
    lo, hi = S.bounds_of(prims, 0.35)
    lo[2] = -0.25
    h = 0.05
    g = S.Grid(lo, hi, h)
    body0 = g.field_of(prims)
    torso0 = g.field_of([p for p in prims if p.tag == 'torso'])
    core_prims = [p for p in prims if p.tag == 'torso' or (p.tag == 'neck' and p.bone == 'UpperTorso')]
    core0 = g.field_of(core_prims)
    P = g.points()
    sash = D.sash_sdf(P).astype(np.float32)
    waist = D.waist_sdf(P).astype(np.float32)
    flap = D.flap_sdf(P).astype(np.float32)
    F = body0.copy()
    F = S.smin(F, np.maximum(torso0 - D.RAISE['sash'], sash), 0.03)
    F = S.smin(F, np.maximum(torso0 - D.RAISE['waist'], waist), 0.03)
    F = S.smin(F, np.maximum(body0 - (D.RAISE['flap'] + D.RAISE['flap_hem'] * D.flap_hem(P)).astype(np.float32), flap), 0.03)
    F = np.maximum(F, -P[..., 2]).astype(np.float32)
    core = S.smin(core0, np.maximum(core0 - D.RAISE['sash'], sash), 0.03)
    core = S.smin(core, np.maximum(core0 - D.RAISE['waist'], waist), 0.03).astype(np.float32)
    del P, sash, waist, flap
    V, Q = S.mesh_field(F, lo, h, smooth=3)
    log('body surface nets', len(V), 'verts', len(Q), 'quads')
    # sculpted bandage wraps: shingled helical lips, displaced along the field normal
    grp, _ = D.band_groups_of(prims, V)
    Ng = S.field_grad(F, lo, h, V)
    Ng /= np.maximum(np.linalg.norm(Ng, axis=1, keepdims=True), 1e-9)
    disp = np.zeros(len(V))
    for gname in np.unique(grp):
        if gname not in D.BAND_GROUPS:
            continue
        sel = grp == gname
        pA, pBe, topA, sA, sB = D.wrap_layers(V[sel], gname)
        disp[sel] = D.BAND_GROUPS[gname]['h'] * (np.maximum(pA, pBe) - 0.72)
    b0 = S.trilinear(body0, lo, h, V)
    keep = 1.0 - PT.smoothstep(0.02, 0.045, b0)
    keep *= PT.smoothstep(0.06, 0.14, V[:, 2])
    under_mask = (np.abs(V[:, 0]) < 0.92) & (V[:, 1] < -0.76) & (V[:, 2] > 6.95)
    keep[under_mask] = 0.0
    V = V + Ng * (disp * keep)[:, None]
    V[:, 2] = np.maximum(V[:, 2], 0.0)
    ob = new_mesh(f'{NAME}_Body', V, Q, col)
    decimate(ob, TARGET_TRIS['Body'])
    Vb = verts(ob)
    Vb[:, 2] = np.maximum(Vb[:, 2], 0.0)       # collapse decimation can nudge sole vertices below the ground
    ob.data.vertices.foreach_set('co', Vb.ravel())
    ob.data.update()
    log('Body', tris(ob), 'tris')
    return ob, {'prims': prims, 'lo': lo, 'h': h, 'body0': body0, 'torso0': torso0, 'core': core, 'F': F}


def build_fists(col):
    fp = D.fist_prims_local()
    lo, hi = S.bounds_of(fp, 0.12)
    h = 0.028
    g = S.Grid(lo, hi, h)
    Ff = g.field_of(fp)
    V, Q = S.mesh_field(Ff, lo, h, smooth=2)
    out = {}
    for side in D.SIDES:
        Vw = D.fist_to_world(side, V)
        Qs = Q[:, ::-1] if side == 'Left' else Q
        ob = new_mesh(f'{NAME}_{side}Fist', Vw, Qs, col)
        decimate(ob, TARGET_TRIS[side + 'Fist'])
        out[side + 'Fist'] = ob
        log(side + 'Fist', tris(ob), 'tris')
    return out, (Ff, lo, h)


def build_mask(col):
    mp = D.mask_prims()
    lo, hi = S.bounds_of(mp, 0.1)
    h = 0.022
    g = S.Grid(lo, hi, h)
    Fm = g.field_of(mp)
    V, Q = S.mesh_field(Fm, lo, h, smooth=2)
    ob = new_mesh(f'{NAME}_Mask', V, Q, col)
    decimate(ob, TARGET_TRIS['Mask'])
    log('Mask', tris(ob), 'tris')
    return ob


def build_eyes(col):
    obs = []
    for e, ang in zip(D.MASK_EYES, (14.0, -14.0)):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=6, radius=1.0, location=tuple(e * D.SC))
        o = bpy.context.active_object
        o.scale = (0.13 * D.SC, 0.07 * D.SC, 0.092 * D.SC)
        o.rotation_euler = (0.0, math.radians(ang), 0.0)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        for c in o.users_collection:
            c.objects.unlink(o)
        col.objects.link(o)
        obs.append(o)
    activate(obs[0])
    for o in obs:
        o.select_set(True)
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = ob.data.name = f'{NAME}_EyeGlow'
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for p in ob.data.polygons:
        p.use_smooth = False
    return ob


def build_cloth(col):
    Vs, Fs, off = [], [], 0
    for front in (True, False):
        V, F = D.flap_surface(front)
        Vs.append(V)
        Fs += [tuple(i + off for i in f) for f in F]
        off += len(V)
    ob = new_mesh(f'{NAME}_Cloth', np.concatenate(Vs), Fs, col)
    return ob


# ====================================================================== rig
def build_rig(col, sk):
    arm = bpy.data.armatures.new(NAME + '_Rig')
    rig = bpy.data.objects.new(NAME + '_Rig', arm)
    col.objects.link(rig)
    activate(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    for name, par, head, tail, R in D.skeleton_spec():
        eb = arm.edit_bones.new(name)
        eb.head = Vector(head * D.SC)
        eb.tail = Vector(tail * D.SC)
        eb.align_roll(Vector(R[:, 2]))
        if par:
            eb.parent = arm.edit_bones[par]
        eb.use_connect = False
        eb.use_deform = True
    bpy.ops.object.mode_set(mode='OBJECT')
    def scaled(Mx):
        Mx = Mx.copy()
        Mx[:3, 3] *= D.SC
        return Mx
    err = max(float(np.abs(np.array(rig.data.bones[n].matrix_local) - scaled(sk.rest[n])).max()) for n in sk.order)
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    arm.display_type = 'STICK'
    log('rig', len(arm.bones), 'bones, max rest error vs design', err)
    assert err < 1e-4, err
    return rig, err


# =================================================================== weights
def body_weights(ob, prims, sk, iters=14, sigma=0.07):
    V = dverts(ob)
    bones = sorted({p.bone for p in prims})
    Dm = np.full((len(bones), len(V)), 1e3)
    for p in prims:
        i = bones.index(p.bone)
        Dm[i] = np.minimum(Dm[i], p.sdf(V))
    dmin = Dm.min(0)
    Wt = np.exp(-(Dm - dmin) / sigma)
    Wt[(Dm - dmin) > 5 * sigma] = 0.0
    Wt /= Wt.sum(0, keepdims=True)
    E = edges(ob)
    n = len(V)
    rows = np.concatenate([E[:, 0], E[:, 1]])
    cols = np.concatenate([E[:, 1], E[:, 0]])
    deg = np.bincount(rows, minlength=n).astype(float)
    for _ in range(iters):
        acc = np.zeros_like(Wt)
        np.add.at(acc.T, rows, Wt.T[cols])
        Wt = 0.5 * Wt + 0.5 * acc / np.maximum(deg, 1)[None]
    # the clavicle helper owns the deltoid cap only: fade its weight into the upper arm below it
    for side in D.SIDES:
        sh, ua = side + 'Shoulder', side + 'UpperArm'
        if sh in bones and ua in bones:
            a0 = D.J('shoulder', side)
            d = D.unit(D.J('elbow', side) - a0)
            tt = (V - a0) @ d
            fade = np.clip((tt + 0.10) / 0.45, 0, 1)
            fade = fade * fade * (3 - 2 * fade)
            move = Wt[bones.index(sh)] * fade
            Wt[bones.index(sh)] -= move
            Wt[bones.index(ua)] += move
            # armpit: no torso weight inside the upper-arm capsule below the shoulder (it pinched the raised arm)
            L = float(np.linalg.norm(D.J('elbow', side) - a0))
            radial = np.linalg.norm((V - a0) - np.outer(tt, d), axis=1)
            inside = (tt > 0.0) & (tt < L) & (radial < 0.98)
            f2 = np.clip((tt - 0.05) / 0.45, 0, 1) * inside
            for tb in ('UpperTorso', sh):
                if tb in bones:
                    mv = Wt[bones.index(tb)] * f2
                    Wt[bones.index(tb)] -= mv
                    Wt[bones.index(ua)] += mv
    # split each limb joint's blend between parent | half-helper | child (piecewise linear in the blend coordinate)
    Wt = list(Wt)
    for h, child in D.HELPERS.items():
        par = D.HELPER_PARENT_OF_BLEND[h]
        if par not in bones or child not in bones:
            continue
        ip, ic = bones.index(par), bones.index(child)
        wp, wc = Wt[ip], Wt[ic]
        tot = wp + wc
        b = np.where(tot > 1e-9, wc / np.maximum(tot, 1e-9), 0.0)
        bones.append(h)
        Wt[ip] = tot * np.clip(1 - 2 * b, 0, 1)
        Wt[ic] = tot * np.clip(2 * b - 1, 0, 1)
        Wt.append(tot * (1 - np.abs(2 * b - 1)))
    Wt = np.array(Wt)
    return bones, Wt.T


def top4(bones, Wt, sk):
    order = np.argsort(-Wt, axis=1)[:, :4]
    w = np.take_along_axis(Wt, order, 1)
    w[w < 0.01] = 0.0
    w /= w.sum(1, keepdims=True)
    idx = np.array([[sk.order.index(bones[j]) for j in row] for row in order])
    return idx, w


def rigid(n, bone, sk):
    idx = np.zeros((n, 4), int)
    idx[:, 0] = sk.order.index(bone)
    w = np.zeros((n, 4))
    w[:, 0] = 1.0
    return idx, w


def cloth_weights(V, sk):
    n = len(V)
    idx = np.zeros((n, 4), int)
    w = np.zeros((n, 4))
    for i, p in enumerate(V):
        z = p[2]
        a, b = ('SashFront1', 'SashFront2') if p[1] < 0 else ('SashBack1', 'SashBack2')
        lt = PT.smoothstep(3.62, 3.90, np.array([z]))[0]
        lo_ = PT.smoothstep(3.0, 2.4, np.array([z]))[0] * (1 - lt)
        mid = max(0.0, 1.0 - lt - lo_)
        names = ['LowerTorso', a, b]
        vals = [lt, mid, lo_]
        for k, (nm, vv) in enumerate(zip(names, vals)):
            idx[i, k] = sk.order.index(nm)
            w[i, k] = vv
    w /= w.sum(1, keepdims=True)
    return idx, w


def bind(ob, rig, idx, w, sk):
    groups = {}
    for b in np.unique(idx[w > 0]):
        groups[int(b)] = ob.vertex_groups.new(name=sk.order[int(b)])
    for i in range(len(idx)):
        for k in range(4):
            if w[i, k] > 0:
                groups[int(idx[i, k])].add([i], float(w[i, k]), 'REPLACE')
    md = ob.modifiers.new('Armature', 'ARMATURE')
    md.object = rig
    ob.parent = rig


# ================================================================== textures
def smart_uv(ob):
    activate(ob)
    if not ob.data.uv_layers:
        ob.data.uv_layers.new(name='UVMap')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(70.0), island_margin=0.002, area_weight=0.0,
                             scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def scale_uv(ob, s):
    uv = ob.data.uv_layers.active.data
    a = np.empty(len(uv) * 2)
    uv.foreach_get('uv', a)
    a = a * s
    uv.foreach_set('uv', a)


def atlas_uvs(objs):
    for ob in objs.values():
        smart_uv(ob)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for ob in objs.values():
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs['Body']
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode='OBJECT')
    for sec, s in (('Mask', 1.45), ('LeftFist', 1.2), ('RightFist', 1.2), ('EyeGlow', 1.0), ('Cloth', 1.0)):
        scale_uv(objs[sec], s)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True, scale=True, margin=0.003)
    bpy.ops.object.mode_set(mode='OBJECT')


def facet_attribute(ob, seed):
    me = ob.data
    rng = np.random.default_rng(seed)
    vals = rng.random(len(me.polygons)).astype(np.float32)
    if 'facet' in me.attributes:
        me.attributes.remove(me.attributes['facet'])
    a = me.attributes.new('facet', 'FLOAT', 'FACE')
    a.data.foreach_set('value', vals)


def enable_gpu():
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'OPTIX'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == 'OPTIX'
        bpy.context.scene.cycles.device = 'GPU'
        return 'OPTIX'
    except Exception:
        bpy.context.scene.cycles.device = 'CPU'
        return 'CPU'


def bake_material(pass_name, img):
    m = bpy.data.materials.new(f'bake_{pass_name}')
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
    elif pass_name == 'C':
        em.inputs['Color'].default_value = (1, 1, 1, 1)
    elif pass_name == 'A':
        ao = nt.nodes.new('ShaderNodeAmbientOcclusion')
        ao.only_local = True
        ao.samples = 16
        ao.inputs['Distance'].default_value = 0.45
        bev = nt.nodes.new('ShaderNodeBevel')
        bev.samples = 8
        bev.inputs['Radius'].default_value = 0.05
        dot = nt.nodes.new('ShaderNodeVectorMath')
        dot.operation = 'DOT_PRODUCT'
        nt.links.new(bev.outputs['Normal'], dot.inputs[0])
        nt.links.new(geo.outputs['Normal'], dot.inputs[1])
        inv = nt.nodes.new('ShaderNodeMath')
        inv.operation = 'MULTIPLY_ADD'
        inv.inputs[1].default_value = -6.0
        inv.inputs[2].default_value = 6.0
        inv.use_clamp = True
        nt.links.new(dot.outputs['Value'], inv.inputs[0])
        at = nt.nodes.new('ShaderNodeAttribute')
        at.attribute_type = 'GEOMETRY'
        at.attribute_name = 'facet'
        cmb = nt.nodes.new('ShaderNodeCombineXYZ')
        nt.links.new(ao.outputs['AO'], cmb.inputs[0])
        nt.links.new(inv.outputs[0], cmb.inputs[1])
        nt.links.new(at.outputs['Fac'], cmb.inputs[2])
        nt.links.new(cmb.outputs[0], em.inputs['Color'])
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    nt.nodes.active = tex
    return m


def bake_object(ob, res):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    activate(ob)
    arrays = {}
    for pname, samples in (('C', 1), ('P', 1), ('N', 1), ('A', 24)):
        img = bpy.data.images.new(f'bake_{pname}', res, res, alpha=False, float_buffer=True)
        img.colorspace_settings.name = 'Non-Color'
        m = bake_material(pname, img)
        ob.data.materials.clear()
        ob.data.materials.append(m)
        sc.cycles.samples = samples
        bpy.ops.object.bake(type='EMIT', margin=0, use_clear=True, target='IMAGE_TEXTURES')
        a = np.empty(res * res * 4, np.float32)
        img.pixels.foreach_get(a)
        arrays[pname] = a.reshape(res, res, 4)[:, :, :3].copy()
        ob.data.materials.clear()
        bpy.data.materials.remove(m)
        bpy.data.images.remove(img)
    return arrays


def poly_dist(P2, poly):
    pp = S.PolyPrism((0, 0, 0), poly, 1.0)
    return pp._poly_sdf(P2[:, 0], P2[:, 1])


def paint_object(sec, arr, info):
    cov = arr['C'][:, :, 0] > 0.5
    P = arr['P'][cov].astype(float) / D.SC            # paint in design units
    N = arr['N'][cov].astype(float)
    A = arr['A'][cov].astype(float)
    ao, edge, facet = A[:, 0], A[:, 1], A[:, 2]
    if sec == 'Body':
        lo, h = info['lo'], info['h']
        b0 = S.trilinear(info['body0'], lo, h, P)
        t0 = S.trilinear(info['torso0'], lo, h, P)
        raised = b0 > 0.055
        flap_d = D.flap_sdf(P)
        sash_d = D.sash_sdf(P)
        waist_d = D.waist_sdf(P)
        flap_r = raised & (flap_d < 0.03)
        sash_r = raised & ~flap_r & (sash_d < 0.03) & (t0 > 0.05)
        waist_r = raised & ~flap_r & ~sash_r & (waist_d < 0.03)
        cav = (np.abs(P[:, 0]) < 0.86) & (P[:, 1] < -0.82) & (P[:, 2] > 6.98) & (P[:, 2] < 8.62) & ~raised
        band = ~(flap_r | sash_r | waist_r | cav)
        col = np.zeros((len(P), 3))
        grp, _ = D.band_groups_of(info['prims'], P[band])
        col[band] = PT.paint_bandage(P[band], N[band], ao[band], edge[band], facet[band], grp)
        border = PT.smoothstep(-0.10, -0.01, sash_d)
        col[sash_r] = PT.paint_teal(P[sash_r], N[sash_r], ao[sash_r], edge[sash_r], facet[sash_r], border=border[sash_r])
        # belt: a darker teal wrap with one clean overlap edge running round it (two turns of cloth)
        wz = P[waist_r, 2] - D.waist_center(P[waist_r]) - 0.06 * np.sin(np.arctan2(P[waist_r, 1], P[waist_r, 0]) * 1.0 + 0.8)
        lap = PT.smoothstep(0.03, -0.01, np.abs(wz) - 0.01)
        col[waist_r] = PT.paint_teal(P[waist_r], N[waist_r], ao[waist_r], edge[waist_r], facet[waist_r],
                                     border=PT.smoothstep(-0.10, -0.01, waist_d[waist_r]), folds=lap, tone=0.86)
        hemf = np.maximum(D.flap_hem(P[flap_r]), 0.35 * PT.smoothstep(-0.07, -0.005, flap_d[flap_r]))
        col[flap_r] = PT.paint_flapcloth(P[flap_r], N[flap_r], ao[flap_r], edge[flap_r], facet[flap_r], hemf)
        col[cav] = PT.paint_cavity(P[cav], N[cav], ao[cav], edge[cav], facet[cav])
        log('body regions texels', {'bandage': int(band.sum()), 'sash': int(sash_r.sum()), 'waist': int(waist_r.sum()),
                                    'flap': int(flap_r.sum()), 'cavity': int(cav.sum())})
    elif sec == 'Cloth':
        hem = np.where(P[:, 1] < 0, PT.smoothstep(2.3, 1.55, P[:, 2]), PT.smoothstep(2.6, 1.95, P[:, 2]))
        fold = 0.5 - 0.5 * np.sin(2.6 * np.pi * P[:, 0] / 0.75 + 0.5 + 0.8 * PT.fbm(P, 1.2, 2, seed=47))
        fold = PT.smoothstep(0.55, 0.95, fold) * PT.smoothstep(3.9, 2.6, P[:, 2])
        col = PT.paint_teal(P, N, ao, edge, facet, hem=hem, folds=fold)
    elif sec == 'Mask':
        d2 = np.abs(poly_dist(P[:, [0, 2]], D.MASK_BREAK))
        fresh = (d2 < 0.08) & (np.abs(N[:, 1]) < 0.65) & (P[:, 1] > -1.45)
        col = PT.paint_stone(P, N, ao, edge, facet, fresh=fresh.astype(float), seed=51)
    elif sec in ('LeftFist', 'RightFist'):
        col = PT.paint_stone(P, N, ao, edge, facet, seed=61 if sec == 'LeftFist' else 71)
    else:
        col = PT.paint_eye(P, N)
    return cov, col


def texture_all(objs, info):
    enable_gpu()
    atlas_uvs(objs)
    res = TEX_MASTER
    albedo = np.zeros((res, res, 3))
    covered = np.zeros((res, res), bool)
    for k, (sec, ob) in enumerate(objs.items()):
        facet_attribute(ob, 300 + k)
        arr = bake_object(ob, res)
        cov, col = paint_object(sec, arr, info)
        cov = cov & ~covered
        full = np.zeros((res, res, 3))
        full[arr['C'][:, :, 0] > 0.5] = col
        albedo[cov] = full[cov]
        covered |= cov
        log('baked + painted', sec, int(cov.sum()), 'texels')
    albedo = PT.fill_uncovered(albedo, covered)
    coverage = float(covered.mean())

    def save(arr_lin, name):
        srgb = PT.lin_to_srgb(arr_lin)
        H, Wd = srgb.shape[:2]
        img = bpy.data.images.new(name, Wd, H, alpha=False)
        img.colorspace_settings.name = 'sRGB'
        img.pixels.foreach_set(np.concatenate([srgb, np.ones((H, Wd, 1))], 2).astype(np.float32).ravel())
        img.filepath_raw = str(TEXD / f'{name}.png')
        img.file_format = 'PNG'
        img.save()
        return img

    master = save(albedo, f'{NAME}_BaseColor_{res}')
    deliv_lin = albedo.reshape(TEX_DELIVERY, res // TEX_DELIVERY, TEX_DELIVERY, res // TEX_DELIVERY, 3).mean((1, 3))
    deliv = save(deliv_lin, f'{NAME}_BaseColor')
    bpy.data.images.remove(master)
    deliv.reload()
    for sec, ob in objs.items():
        m = bpy.data.materials.new(f'{NAME}_{sec}')
        m.use_nodes = True
        nt = m.node_tree
        bs = nt.nodes.get('Principled BSDF')
        bs.inputs['Roughness'].default_value = 0.9 if sec != 'EyeGlow' else 0.5
        if 'Specular IOR Level' in bs.inputs:
            bs.inputs['Specular IOR Level'].default_value = 0.2
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = deliv
        tex.interpolation = 'Linear'
        nt.links.new(tex.outputs['Color'], bs.inputs['Base Color'])
        if sec == 'EyeGlow':
            nt.links.new(tex.outputs['Color'], bs.inputs['Emission Color'])
            bs.inputs['Emission Strength'].default_value = 2.5
        nt.nodes.active = tex
        ob.data.materials.clear()
        ob.data.materials.append(m)
    log('atlas coverage', round(coverage, 3))
    return {'master': f'{NAME}_BaseColor_{res}.png', 'delivery': f'{NAME}_BaseColor.png', 'coverage': round(coverage, 4)}


# ====================================================================== main
def shape_review(objs, path):
    import tw_deliver as DL
    cols = {'Body': (232, 214, 176), 'Cloth': (58, 142, 132), 'Mask': (200, 124, 70), 'LeftFist': (200, 124, 70),
            'RightFist': (200, 124, 70), 'EyeGlow': (255, 180, 40)}
    for sec, ob in objs.items():
        ob.data.materials.clear()
        ob.data.materials.append(flat_mat('flat_' + sec, cols[sec]))
    DL.setup_review_scene()
    tiles = []
    for view in ('Front', 'Side', 'ThreeQuarter', 'Back'):
        tiles.append(DL.workbench_view(view, (420, 520), color='MATERIAL'))
    DL.save_rgb(DL.tile(tiles, 4), path)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 24
    col = collection(NAME)
    sk = M.Skel()
    body, info = build_body(col)
    fists, fist_field = build_fists(col)
    mask = build_mask(col)
    eyes = build_eyes(col)
    cloth = build_cloth(col)
    objs = {'Body': body, 'Cloth': cloth, 'Mask': mask, 'LeftFist': fists['LeftFist'], 'RightFist': fists['RightFist'],
            'EyeGlow': eyes}
    rig, rig_err = build_rig(col, sk)
    # fist effector offsets along the hand axis, measured on the mesh
    for side in D.SIDES:
        L = SV.xf(np.linalg.inv(sk.rest[side + 'Hand']), dverts(objs[side + 'Fist']))
        sk.fist_bottom = float(np.percentile(L[:, 1], 99.5))
        sk.fist_center = float(L[L[:, 1] > 0.3][:, 1].mean())
    log('fist effector bottom/centre', round(sk.fist_bottom, 3), round(sk.fist_center, 3))
    bones, Wt = body_weights(body, info['prims'], sk)
    dominant = np.array([D.HELPERS.get(b, b) for b in np.array(bones)[np.argmax(Wt, 1)]])
    sec_w = {'Body': top4(bones, Wt, sk)}
    sec_w['Cloth'] = cloth_weights(dverts(cloth), sk)
    sec_w['Mask'] = rigid(len(mask.data.vertices), 'Head', sk)
    sec_w['EyeGlow'] = rigid(len(eyes.data.vertices), 'Head', sk)
    for side in D.SIDES:
        sec_w[side + 'Fist'] = rigid(len(objs[side + 'Fist'].data.vertices), side + 'Hand', sk)
    for sec, ob in objs.items():
        bind(ob, rig, *sec_w[sec], sk)
    skin = SV.Skinner(sk, {sec: (dverts(ob), *sec_w[sec]) for sec, ob in objs.items()})
    ctx = SV.Ctx(sk, skin, {'lo': info['lo'], 'h': info['h'], 'core': info['core']}, fist_field, dominant)
    tri = {sec: tris(ob) for sec, ob in objs.items()}
    log('triangles', tri, 'total', sum(tri.values()))
    state = {'sk': sk, 'rig': rig, 'objs': objs, 'info': info, 'ctx': ctx, 'skin': skin, 'sec_w': sec_w,
             'dominant': dominant, 'tris': tri, 'rig_err': rig_err}
    if STAGE == 'shape':
        shape_review(objs, WORK / 'shape_review.png')
        log('SHAPE DONE')
        return
    clips = {
        'Idle': SV.idle_clip(sk), 'Walk': SV.walk_clip(sk), 'Hit': SV.hit_clip(sk),
        'FistSlam': SV.slam_clip(ctx, log), 'FistHook': SV.hook_clip(ctx, log), 'Roar': SV.roar_clip(ctx, log),
        'Emerge': SV.emerge_clip(ctx, log), 'Death': SV.death_clip(ctx, log)}
    state['clips'] = clips
    import tw_deliver as DL
    DL.key_actions(state)
    checks = DL.motion_checks(state, log)
    state['checks'] = checks
    (WORK / 'motion_checks_preview.json').write_text(json.dumps(DL.summary(checks), indent=1))
    (WORK / 'motion_checks_full.json').write_text(json.dumps({k: {kk: vv for kk, vv in c.items() if kk != 'fistSpeed'} for k, c in checks.items()}, indent=1, default=str))
    if STAGE == 'motion':
        shape_review(objs, WORK / 'shape_review.png')
        DL.game_clips_sheet(state, WORK / 'GameClips_flat.png', color='MATERIAL')
        DL.setup_review_scene()
        box = DL.cavity_wire()
        DL.set_frame(rig, 'Emerge', 0)
        DL.VIEWS['CF'] = ((0.0, -24.0, 4.7), (0.0, 3.5, 4.6), 60)
        DL.VIEWS['CS'] = ((-24.0, 3.5, 4.7), (0.0, 3.5, 4.6), 60)
        DL.VIEWS['CT'] = ((0.0, 3.0, 30.0), (0.0, 3.5, 4.0), 50)
        DL.save_rgb(DL.tile([DL.workbench_view(v, (420, 480), color='MATERIAL') for v in ('CF', 'CS', 'CT')], 3),
                    WORK / 'coffin_pose.png')
        if os.environ.get('TW_DEBUG_RENDER'):
            tiles = []
            for clip, fr, side in (('FistSlam', 18, 'Left'), ('FistHook', 18, 'Right'), ('Idle', 0, 'Left')):
                DL.set_frame(rig, clip, fr)
                bpy.context.view_layer.update()
                J = np.array(rig.matrix_world @ rig.pose.bones[side + 'UpperArm'].head)
                for d in ((0, -7, 1.5), (-7 if side == 'Right' else 7, 0, 1.0)):
                    DL.VIEWS['DB'] = (tuple((J + np.array(d)) / 1.0), tuple(J), 45)
                    k = D.SC
                    DL.VIEWS['DB'] = (tuple((J + np.array(d)) / k), tuple(J / k), 45)
                    tiles.append(DL.workbench_view('DB', (360, 360), color='SINGLE'))
            DL.save_rgb(DL.tile(tiles, 6), WORK / 'shoulder_debug.png')
        DL.rest_pose(rig)
        log('MOTION DONE')
        return
    DL.rest_pose(rig)
    rig.data.pose_position = 'REST'
    state['tex'] = texture_all(objs, info)
    rig.data.pose_position = 'POSE'
    DL.deliver(state, log)
    log('BUILD DONE')


if __name__ == '__main__':
    main()
