"""Hammer Brute boss: generator. Run with Blender 5.2 in background mode:

    blender -b --factory-startup --python build_hammer_brute.py

Environment:
    HB_STAGE=probe   geometry + rig + ReferencePose + one reference-camera render
                     and its silhouette mask (the PROBE_ONLY compare loop)
    HB_STAGE=model   probe + textures + the .blend, no preview sheets
    HB_STAGE=full    everything: 2048 bake/paint, actions, every preview, reports
    HB_TEXTURES=0    flat preview colours instead of the baked paint (QUICK shaping runs)
    HB_TEX=1024      master texture size (full stage default 2048)
    HB_SAMPLES       Cycles samples for the reference render

Self-contained: imports only the hb_*.py modules in this folder.
"""
import json
import math
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bpy                      # noqa: E402
import numpy as np              # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import hb_blender as B          # noqa: E402
import hb_design as D           # noqa: E402
import hb_grip as G             # noqa: E402
import hb_parts as FP           # noqa: E402
import hb_pose as PO            # noqa: E402
import hb_weights as WT         # noqa: E402
import hb_paint as PT           # noqa: E402
from hb_camera import RefCam    # noqa: E402
from hb_sdf import Grid, surface_nets, eval_prims, mesh_fn, project_to_surface  # noqa: E402

STAGE = os.environ.get('HB_STAGE', 'full')
TEXTURES = os.environ.get('HB_TEXTURES', '1') == '1'
VOX = float(os.environ.get('HB_VOX', '0.05'))
WORK = HERE / '_work'
WORK.mkdir(exist_ok=True)
T0 = time.time()
NAME = 'HammerBrute'
SIDES = ('Right', 'Left')
SECTIONS = ['Body', 'Head', 'Shirt', 'Gear', 'Trousers', 'Hammer', 'EyeGlow']
SKIN_QUADS = int(os.environ.get('HB_SKIN_QUADS', '4000'))
HAND_TRIS = 3000
BUDGET = {'Shirt': 6200, 'Trousers': 7600, 'Sash': 2600, 'SashTail': 700, 'Buckle': 360, 'Teeth': 520,
          'EyeGlow': 320, 'HammerHead': 2200, 'HammerIron': 260}


def log(*a):
    print('[HB %6.1fs]' % (time.time() - T0), *a, flush=True)


# The design is laid out in the solved reference camera's units. One uniform scale
# about the ground origin (set in build_all from the measured reference-pose crown)
# makes the top of the head exactly D.CROWN = 13.7 studs; the review camera is
# scaled with it, so the reference match is unchanged.
WS = 1.0


def scale_mats(mats, s):
    out = {}
    for b, M in mats.items():
        M2 = M.copy()
        M2[:3, 3] *= s
        out[b] = M2
    return out


class ScaledSkeleton:
    def __init__(self, sk, s):
        self.parent, self.children, self.order = sk.parent, sk.children, sk.order
        self.rest = scale_mats(sk.rest, s)
        self.ref = scale_mats(sk.ref, s)
        self.length = {b: L * s for b, L in sk.length.items()}
        self.design = sk
        self.scale = s


# ============================================================ meshing helpers
def trilinear(g, P):
    x = (P - g.lo) / g.h
    i = np.clip(np.floor(x).astype(int), 0, g.n - 2)
    f = np.clip(x - i, 0, 1)
    v = g.v
    out = np.zeros(len(P))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                out += w * v[i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz]
    return out


def quad_adjacency(Q, n):
    rows = np.concatenate([Q[:, 0], Q[:, 1], Q[:, 2], Q[:, 3], Q[:, 1], Q[:, 2], Q[:, 3], Q[:, 0]])
    cols = np.concatenate([Q[:, 1], Q[:, 2], Q[:, 3], Q[:, 0], Q[:, 0], Q[:, 1], Q[:, 2], Q[:, 3]])
    key = np.unique(rows.astype(np.int64) * n + cols)
    return key // n, key % n


def clean_surface(g, V, Q, iters=3):
    """Laplacian smoothing of the surface-nets stair steps, re-projected onto the
    SDF zero set each pass so features keep their shape."""
    n = len(V)
    rows, cols = quad_adjacency(Q, n)
    deg = np.bincount(rows, minlength=n)
    for _ in range(iters):
        acc = np.zeros_like(V)
        np.add.at(acc, rows, V[cols])
        V = V + 0.5 * (acc / np.maximum(deg, 1)[:, None] - V)
        e = g.h * 0.5
        d = trilinear(g, V)
        grad = np.stack([(trilinear(g, V + np.eye(3)[k] * e) - trilinear(g, V - np.eye(3)[k] * e)) / (2 * e)
                         for k in range(3)], 1)
        gn = np.maximum(np.linalg.norm(grad, axis=1, keepdims=True), 1e-6)
        V = V - grad / gn * (d / gn[:, 0])[:, None]
    return V


def sdf_to_mesh(prims, h, smooth=3, pad=0.3, lo=None, hi=None):
    if lo is None:
        lo = np.full(3, 1e9)
        hi = np.full(3, -1e9)
        for p in prims:
            if p.op != 'union':
                continue
            a, b = p.bounds()
            lo = np.minimum(lo, a)
            hi = np.maximum(hi, b)
        lo, hi = lo - pad, hi + pad
    g = Grid(lo, hi, h)
    g.build(prims)
    V, Q = surface_nets(g)
    if smooth:
        V = clean_surface(g, V, Q, smooth)
    return V, Q


# ================================================================ materials
MAT_COLORS = {'skin': (118, 168, 62), 'tooth': (222, 214, 190), 'shirt': (200, 178, 150), 'strap': (92, 72, 68),
              'iron': (88, 82, 86), 'sash': (118, 34, 44), 'trousers': (74, 68, 84), 'wood': (104, 62, 38),
              'band': (72, 64, 68), 'eye': (250, 250, 246), 'buckle': (150, 148, 152)}


def preview_material(key):
    name = 'HBP_' + key
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*B.srgb(*MAT_COLORS[key]), 1)
    bs.inputs['Roughness'].default_value = 0.9
    if key == 'eye':
        bs.inputs['Emission Color'].default_value = (1, 1, 1, 1)
        bs.inputs['Emission Strength'].default_value = 3.0
    m['paint'] = key
    return m


# ================================================================== geometry
def forearm_cut(side):
    S, E, Tw, Wr, hinge = D.rest_arm(side)
    fa = (Wr - E) / np.linalg.norm(Wr - E)
    A = E + fa * D.L_FORE * 0.74
    return A, A + fa * 0.12, fa


def build_skin(coll):
    """One connected skin mesh: the body (and head) quad-remeshed to broad even
    facets, the head region subdivided and re-projected for the face, and two
    finely meshed hands bridged in at the lower forearm."""
    body = D.body_prims()
    hands = {s: D.hand_prims(s, 'REST') for s in SIDES}
    allp = D.skin_prims(True)
    exact = lambda P: eval_prims(allp, P)
    log('skin sdf ...')
    Vs, Qs = sdf_to_mesh(allp, VOX)
    log('skin raw verts', len(Vs))
    skin = B.mesh_object('Skin', Vs, Qs, coll, [preview_material('skin')])
    how = B.remesh_even(skin, SKIN_QUADS, voxel_sizes=(0.07, 0.09, 0.11), fallback_tris=SKIN_QUADS * 2)
    log('skin remesh', how, len(skin.data.polygons))
    V, F = B.mesh_arrays(skin)
    V = project_to_surface(exact, V, iters=2)
    B.set_coords(skin, V)
    # head region: subdivide twice (9x the facets) and pull onto the exact SDF
    V, F = B.mesh_arrays(skin)
    cent = np.array([V[list(f)].mean(0) for f in F])
    own = WT.ownership(allp, cent)
    hmask = (own.get('head', 0) > 0.30) | ((np.linalg.norm(cent - D.HEAD_C, axis=1) < 1.45) & (cent[:, 2] > 10.9))
    B.faces_subdivide(skin, hmask, cuts=2)
    V, F = B.mesh_arrays(skin)
    near = np.linalg.norm(V - D.HEAD_C, axis=1) < 2.3
    V[near] = project_to_surface(exact, V[near], iters=5)
    B.set_coords(skin, V)
    log('skin with head detail', len(skin.data.polygons))
    # forearm cuts and fine hands
    hand_obs = []
    for side in SIDES:
        A, Bp, fa = forearm_cut(side)
        B.cut_keep(skin, A, fa, -1, region_center=A, region_radius=2.2)
        hp = [p for p in hands[side] if p.op == 'union']
        arm = [p for p in D.arm_prims(side) if p.bone != side + 'UpperArm']
        lo = np.min([p.bounds()[0] for p in hp], axis=0)
        hi = np.max([p.bounds()[1] for p in hp], axis=0)
        lo = np.minimum(lo, Bp - 1.4)
        hi = np.maximum(hi, Bp + 1.4)
        fn = lambda P, pr=hp + arm: eval_prims(pr, P)
        Vh, Qh = mesh_fn(fn, lo - 0.1, hi + 0.1, 0.022)
        ob = B.mesh_object('Hand' + side, Vh, Qh, coll, [preview_material('skin')])
        B.decimate(ob, HAND_TRIS + 1200)
        B.cut_keep(ob, Bp, fa, +1)
        hand_obs.append(ob)
        log('hand', side, B.tri_count(ob))
    skin = B.join([skin] + hand_obs, 'Skin')
    centers = [(forearm_cut(s)[0] + forearm_cut(s)[1]) / 2 for s in SIDES]
    made = B.bridge_open_loops(skin, centers, max_dist=1.6)
    log('bridged faces', made, 'open edges left', B.boundary_edge_count(skin))
    return skin


def build_parts(coll, sk):
    """Clothes, face parts and the hammer as mesh objects in REST world."""
    out = []
    ref = G.solve_reference()
    for p in FP.cloth_parts() + FP.face_parts():
        ob = B.mesh_object(p.name, p.V, p.F, coll, [preview_material(p.mat)])
        key = 'Buckle' if p.name.startswith('Buckle') else 'Teeth' if p.name.startswith('Teeth') else p.name
        if key in BUDGET:
            B.decimate(ob, BUDGET[key])
        ob['part'] = p.name
        ob['bone'] = p.bone or ''
        ob['rule'] = p.rule or ''
        ob['section'] = p.section
        out.append(ob)
        log('part', p.name, B.tri_count(ob))
    Hr = sk.rest['Hammer']
    for p in FP.hammer_parts(ref['s_left']):
        V = p.V @ Hr[:3, :3].T + Hr[:3, 3]
        ob = B.mesh_object(p.name, V, p.F, coll, [preview_material(p.mat)])
        key = 'HammerIron' if p.name.startswith('HammerIron') else p.name
        if key in BUDGET:
            B.decimate(ob, BUDGET[key])
        ob['part'] = p.name
        ob['bone'] = 'Hammer'
        ob['rule'] = ''
        ob['section'] = 'Hammer'
        out.append(ob)
        log('part', p.name, B.tri_count(ob))
    return out


# ======================================================================= rig
def build_rig(coll, sk):
    arm = bpy.data.armatures.new(NAME + '_Rig')
    rig = bpy.data.objects.new(NAME + '_Rig', arm)
    coll.objects.link(rig)
    B.activate(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.edit_bones
    for name in sk.order:
        M = sk.rest[name]
        b = eb.new(name)
        b.head = Vector(M[:3, 3])
        b.tail = Vector(M[:3, 3] + M[:3, 1] * sk.length[name])
        b.align_roll(Vector(M[:3, 2]))
    for name in sk.order:
        par = sk.parent[name]
        if par:
            eb[name].parent = eb[par]
            eb[name].use_connect = False
    # non-deform helpers (excluded from exports)
    ctrl = {}
    for side in SIDES:
        s = side[0]
        w = sk.rest[side + 'Hand'][:3, 3]
        ctrl['IK_Hand_' + s] = (w, w + np.array([0, -0.8, 0]), 'Root', None)
        e = sk.rest[side + 'LowerArm'][:3, 3]
        ctrl['Pole_Elbow_' + s] = (e + np.array([0, 3.0, 0]), e + np.array([0, 3.6, 0]), 'Root', None)
        a = sk.rest[side + 'Foot'][:3, 3]
        ctrl['IK_Foot_' + s] = (a, a + np.array([0, -0.8, 0]), 'Root', None)
        k = sk.rest[side + 'LowerLeg'][:3, 3]
        ctrl['Pole_Knee_' + s] = (k + np.array([0, -3.0, 0]), k + np.array([0, -3.6, 0]), 'Root', None)
    # left-hand grip target riding on the haft, plus the two gameplay points
    Hr = sk.rest['Hammer']
    LH_in_H = np.linalg.inv(sk.ref['Hammer']) @ sk.ref['LeftHand']
    Lg = Hr @ LH_in_H
    ctrl['IK_Grip_L'] = (Lg[:3, 3], Lg[:3, 3] + Lg[:3, 1] * 0.8, 'Hammer', Lg[:3, 2])
    pts = hammer_points()
    for nm in ('HammerFace', 'HammerGrip'):
        p, nrm = pts[nm]
        p = p * WS
        h = Hr[:3, :3] @ p + Hr[:3, 3]
        t = h + Hr[:3, :3] @ nrm * 0.6
        ctrl[nm] = (h, t, 'Hammer', Hr[:3, 1] if nm == 'HammerFace' else Hr[:3, 2])
    for name, (h, t, par, roll) in ctrl.items():
        b = eb.new(name)
        b.head = Vector(h)
        b.tail = Vector(t)
        if roll is not None:
            b.align_roll(Vector(roll))
        b.use_deform = False
        b.parent = eb[par]
    bpy.ops.object.mode_set(mode='OBJECT')
    for side in SIDES:
        s = side[0]
        tgt = 'IK_Grip_L' if side == 'Left' else 'IK_Hand_R'
        c = rig.pose.bones[side + 'LowerArmTwist'].constraints.new('IK')
        c.target, c.subtarget = rig, tgt
        c.pole_target, c.pole_subtarget = rig, 'Pole_Elbow_' + s
        c.chain_count = 3
        c.influence = 0.0
        cr = rig.pose.bones[side + 'Hand'].constraints.new('COPY_ROTATION')
        cr.target, cr.subtarget = rig, tgt
        cr.influence = 0.0
        tw = rig.pose.bones[side + 'LowerArmTwist']
        tw.lock_ik_x = tw.lock_ik_z = True
        la = rig.pose.bones[side + 'LowerArm']
        la.lock_ik_y = la.lock_ik_z = True
        c = rig.pose.bones[side + 'LowerLeg'].constraints.new('IK')
        c.target, c.subtarget = rig, 'IK_Foot_' + s
        c.pole_target, c.pole_subtarget = rig, 'Pole_Knee_' + s
        c.chain_count = 2
        c.influence = 0.0
    rig.show_in_front = True
    arm.display_type = 'OCTAHEDRAL'
    return rig


def hammer_points():
    """HammerFace (centre of the flat striking face + normal) and HammerGrip (on the
    haft axis halfway between the carry grips), in Hammer bone space."""
    ref = G.solve_reference()
    face = np.array([0.0, D.S_RIGHT, D.EYE_OFFSET + D.HEAD_HALF[1]])
    grip = np.array([0.0, (D.S_RIGHT - ref['s_left']) / 2.0, 0.0])
    return {'HammerFace': (face, np.array([0, 0, 1.0])), 'HammerGrip': (grip, np.array([0, 1.0, 0]))}


def key_pose(rig, sk, mats, frame, prev=None):
    from mathutils import Matrix as Mx
    prev = {} if prev is None else prev
    for name in sk.order:
        par = sk.parent[name]
        Mp = mats[name]
        if par:
            basis = np.linalg.inv(sk.rest[name]) @ sk.rest[par] @ np.linalg.inv(mats[par]) @ Mp
        else:
            basis = np.linalg.inv(sk.rest[name]) @ Mp
        pb = rig.pose.bones[name]
        pb.rotation_mode = 'QUATERNION'
        m = Mx([list(r) for r in basis])
        loc, q, sc = m.decompose()
        if name in prev and q.dot(prev[name]) < 0:
            q.negate()
        prev[name] = q.copy()
        pb.location = loc
        pb.rotation_quaternion = q
        pb.scale = (1, 1, 1)
        if frame is not None:
            for prop in ('location', 'rotation_quaternion', 'scale'):
                pb.keyframe_insert(data_path=prop, frame=frame, group=name)
    return prev


def make_action(rig, sk, name, keys, markers=()):
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    rig.animation_data.action = act
    prev = {}
    for fr, P in keys:
        mats = P.m if hasattr(P, 'm') else P
        prev = key_pose(rig, sk, scale_mats(mats, WS), fr, prev)
    for mname, fr in markers:
        mk = act.pose_markers.new(mname)
        mk.frame = fr
    act.frame_range = (keys[0][0], keys[-1][0])
    return act


# ==================================================================== weights
def assign_groups(ob, W, deform):
    n = len(ob.data.vertices)
    names, M, bad = WT.finalize(W, n)
    for g in list(ob.vertex_groups):
        ob.vertex_groups.remove(g)
    for j, bname in enumerate(names):
        if bname not in deform:
            raise RuntimeError(f'{ob.name}: weight for unknown bone {bname}')
        colw = M[:, j]
        nz = np.nonzero(colw > 0)[0]
        if len(nz) == 0:
            continue
        vg = ob.vertex_groups.new(name=bname)
        for w in np.unique(np.round(colw[nz], 4)):
            idx = nz[np.round(colw[nz], 4) == w].tolist()
            vg.add(idx, float(w), 'REPLACE')
    return int(bad.sum()), len(names)


def skin_and_part_weights(skin, parts, rig):
    deform = {b.name for b in rig.data.bones if b.use_deform}
    body = D.body_prims()
    hands = {s: D.hand_prims(s, 'REST') for s in SIDES}
    stats = {}
    V, F = B.mesh_arrays(skin)
    W = WT.skin_weights(V, body, hands)
    W = WT.smooth(W, WT.adjacency(F, len(V)), len(V), iters=4, lam=0.5)
    stats['Skin'] = assign_groups(skin, W, deform)
    for ob in parts:
        V, F = B.mesh_arrays(ob)
        n = len(V)
        bone, rule, name = ob['bone'], ob['rule'], ob['part']
        if bone:
            W = {bone: np.ones(n)}
        elif rule == 'shirt':
            W = WT.shirt_weights(V, body, hands)
            W = WT.smooth(W, WT.adjacency(F, n), n, iters=2, lam=0.4)
        elif rule == 'trousers':
            W = WT.trousers_weights(V, body, hands)
            W = WT.smooth(W, WT.adjacency(F, n), n, iters=2, lam=0.4)
        elif rule == 'sash':
            W = WT.sash_weights(V, body, hands, tail=(name == 'SashTail'))
        elif rule == 'eye':
            W = WT.eye_weights(V)
        else:
            W = WT.nearest_skin(V, body, hands, surface_prims=[p for p in D.torso_prims() if p.op == 'union'])
            W = WT.keep_only(W, ('UpperTorso', 'LowerTorso', 'Belly', 'Head', 'UpperArm'))
        stats[ob.name] = assign_groups(ob, W, deform)
    return stats


def bind(objs, rig):
    for ob in objs:
        ob.parent = rig
        m = ob.modifiers.new('Armature', 'ARMATURE')
        m.object = rig
        m.use_deform_preserve_volume = False


def split_skin(skin):
    """Head faces -> HammerBrute_Head, the rest -> body skin (vertex groups kept)."""
    V, F = B.mesh_arrays(skin)
    cent = np.array([V[list(f)].mean(0) for f in F]) / WS
    own = WT.ownership(D.skin_prims(True), cent)
    is_head = own.get('head', 0) > 0.5
    a = skin.data.attributes.new('hb_head', 'INT', 'FACE')
    a.data.foreach_set('value', is_head.astype(np.int32))
    B.activate(skin)
    head = skin.copy()
    head.data = skin.data.copy()
    head.name = 'HeadSkin'
    skin.users_collection[0].objects.link(head)
    import bmesh
    for ob, keep_head in ((skin, False), (head, True)):
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        lay = bm.faces.layers.int.get('hb_head')
        kill = [f for f in bm.faces if bool(f[lay]) != keep_head]
        bmesh.ops.delete(bm, geom=kill, context='FACES')
        loose = [v for v in bm.verts if not v.link_faces]
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
        bm.to_mesh(ob.data)
        bm.free()
    return skin, head


def join_sections(groups):
    out = {}
    for sec, obs in groups.items():
        if not obs:
            continue
        ob = B.join(obs, f'{NAME}_{sec}') if len(obs) > 1 else obs[0]
        ob.name = f'{NAME}_{sec}'
        ob.data.name = f'{NAME}_{sec}'
        mods = [m for m in ob.modifiers if m.type == 'ARMATURE']
        for m in mods[1:]:
            ob.modifiers.remove(m)
        out[sec] = ob
    return out


# ================================================================== textures
TEX_MASTER = int(os.environ.get('HB_TEX', '2048' if STAGE == 'full' else '1024'))
TEX_DELIVERY = 1024
CAL_PATH = HERE / 'calibration.json'


def load_calibration():
    if CAL_PATH.exists():
        return {k: tuple(v) for k, v in json.loads(CAL_PATH.read_text())['CALIBRATION'].items()}
    return {}


def facet_attribute(ob, seed):
    me = ob.data
    n = len(me.polygons)
    rng = np.random.default_rng(seed)
    face_r = rng.random(n)
    parent = np.arange(len(me.vertices))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for p in me.polygons:
        vs = list(p.vertices)
        r0 = find(vs[0])
        for v in vs[1:]:
            r = find(v)
            if r != r0:
                parent[r] = r0
    roots = np.array([find(p.vertices[0]) for p in me.polygons])
    uniq, inv = np.unique(roots, return_inverse=True)
    isl = rng.random(len(uniq))[inv]
    B.face_attribute(ob, 'facet', 0.6 * face_r + 0.4 * isl)


def bake_material(pass_name, key, img):
    m = bpy.data.materials.new(f'bake_{pass_name}_{key}')
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
        vm = nt.nodes.new('ShaderNodeVectorMath')
        vm.operation = 'MULTIPLY_ADD'
        vm.inputs[1].default_value = (0.5, 0.5, 0.5)
        vm.inputs[2].default_value = (0.5, 0.5, 0.5)
        nt.links.new(geo.outputs['Normal'], vm.inputs[0])
        nt.links.new(vm.outputs[0], em.inputs['Color'])
    elif pass_name == 'A':
        ao = nt.nodes.new('ShaderNodeAmbientOcclusion')
        ao.only_local = True
        ao.inputs['Distance'].default_value = 0.55
        ao.samples = 16
        bev = nt.nodes.new('ShaderNodeBevel')
        bev.samples = 8
        bev.inputs['Radius'].default_value = 0.07
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
    elif pass_name == 'I':
        em.inputs['Color'].default_value = ((PT.MAT_IDS.index(key) + 0.5) / 32.0, 1.0, 0.0, 1.0)
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    nt.nodes.active = tex
    return m


def bake_passes(ob, res, ao_samples):
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    B.enable_gpu()
    keys = [s.material.get('paint', 'skin') for s in ob.material_slots]
    orig = [s.material for s in ob.material_slots]
    B.activate(ob)
    arrays = {}
    for pname, samples in (('P', 1), ('N', 1), ('I', 1), ('A', ao_samples)):
        img = bpy.data.images.new(f'{ob.name}_{pname}', res, res, alpha=False, float_buffer=True)
        img.colorspace_settings.name = 'Non-Color'
        tmp = []
        for i, slot in enumerate(ob.material_slots):
            m = bake_material(pname, keys[i], img)
            slot.material = m
            tmp.append(m)
        scene.cycles.samples = samples
        bpy.ops.object.bake(type='EMIT', margin=16, margin_type='EXTEND', use_clear=True, target='IMAGE_TEXTURES')
        arrays[pname] = B.image_pixels(img)[:, :, :3].copy()
        for m in tmp:
            bpy.data.materials.remove(m)
        bpy.data.images.remove(img)
    for i, slot in enumerate(ob.material_slots):
        slot.material = orig[i]
    return arrays


_CTX = {}


def paint_context(sk):
    """World-space marks for the paint, computed once (REST pose)."""
    if _CTX:
        return _CTX
    body = [p for p in D.skin_prims(True) if p.op == 'union']
    fn = lambda P: eval_prims(body, P)
    from hb_sdf import gradient

    def surf(origin, direction):
        d = np.asarray(direction, float)
        d = d / np.linalg.norm(d)
        ts = np.linspace(0.0, 4.0, 400)
        pts = np.asarray(origin, float)[None] + d[None] * ts[:, None]
        v = fn(pts)
        k = int(np.argmax(v > 0))
        p = pts[max(k - 1, 0)]
        p = project_to_surface(fn, p[None], iters=4)[0]
        return p, gradient(fn, p[None])[0]
    wounds = []

    def arm_wound(side, bone, t, ang, size, drip, seed):
        M = sk.rest[side + bone]
        L = sk.length[side + bone]
        o = M[:3, 3] + M[:3, 1] * L * t
        lat = -1.0 if side == 'Right' else 1.0
        a = math.radians(ang)
        out_dir = np.array([lat, 0, 0])
        out_dir = out_dir - M[:3, 1] * (out_dir @ M[:3, 1])
        out_dir /= np.linalg.norm(out_dir)
        fwd = np.cross(M[:3, 1], out_dir) * lat
        if fwd[1] > 0:
            fwd = -fwd
        d = math.cos(a) * out_dir + math.sin(a) * fwd
        p, n = surf(o, d)
        wounds.append((p, n, M[:3, 1], size, drip, seed))
    arm_wound('Left', 'UpperArm', 0.17, 40, 0.40, 1.1, 101)
    arm_wound('Left', 'LowerArm', 0.85, 55, 0.27, 0.45, 103)
    arm_wound('Right', 'UpperArm', 0.30, 15, 0.34, 0.8, 104)
    arm_wound('Right', 'LowerArm', 0.95, 50, 0.22, 0.35, 105)
    down = np.array([0, 0, -1.0])
    for (o, d, size, drip, seed) in (((-1.1, -1.2, 7.3), (0, -1, 0.05), 0.22, 0.75, 111),
                                     ((1.55, -1.2, 6.7), (0.25, -1, 0), 0.19, 0.55, 112),
                                     ((0.55, -1.2, 5.75), (0, -1, -0.2), 0.12, 0.3, 113)):
        p, n = surf(o, d)
        wounds.append((p, n, down, size, drip, seed))
    # forehead gash high on his left, bleeding down the left side of the face past the eye
    p, n = surf(D.Hd(0.45, -0.3, 0.95), (0.45, -1, 0.55))
    wounds.append((p, n, down, 0.22, 0.9, 121))
    p, n = surf(D.Hd(0.66, -0.5, 0.42), (0.35, -1, 0.0))
    wounds.append((p, n, down, 0.12, 1.6, 122))
    _CTX['wounds'] = wounds
    head_mouth = [p for p in D.head_prims() if p.tag == 'mouth']
    _CTX['mouth'] = head_mouth
    _CTX['head_union'] = [p for p in D.head_prims() if p.op == 'union'] + \
        [p for p in D.torso_prims() if p.tag == 'neck']
    _CTX['eyes'] = FP.eye_centres()
    _CTX['head_c'] = D.HEAD_C
    # blood stains on the shirt and the hammer
    sh = FP.shirt_sdf_fn()
    stains = []
    for (o, d, size, drip, seed) in (((1.35, -1.0, 9.55), (0.1, -1, 0), 0.20, 0.6, 131),
                                     ((-1.0, -1.0, 9.15), (-0.1, -1, 0), 0.17, 0.5, 132),
                                     ((-0.2, -1.0, 8.75), (0, -1, 0), 0.24, 0.0, 135),
                                     ((2.35, -0.5, 7.9), (0.6, -1, 0), 0.14, 0.4, 134)):
        dd = np.asarray(d, float) / np.linalg.norm(d)
        ts = np.linspace(0, 4.5, 450)
        pts = np.asarray(o, float)[None] + dd[None] * ts[:, None]
        v = sh(pts)
        inside = np.nonzero(v < 0)[0]
        k = inside[-1] if len(inside) else 0
        stains.append((pts[k], gradient(sh, pts[k][None])[0], down, size, drip, seed))
    _CTX['shirt_stains'] = stains
    Hr = sk.rest['Hammer']
    hs = []
    c = np.array([0.0, D.S_RIGHT, D.EYE_OFFSET])
    for (lp, ln, size, drip, seed) in (((D.HEAD_HALF[2], -0.6, 1.3), (1.0, 0, 0), 0.30, 0.0, 142),
                                       ((-D.HEAD_HALF[2], 0.4, 1.4), (-1.0, 0, 0), 0.28, 0.0, 143),
                                       ((D.HEAD_HALF[2], 0.9, -1.6), (1.0, 0, 0), 0.12, 0.0, 144)):
        p = Hr[:3, :3] @ (c + np.array(lp)) + Hr[:3, 3]
        n = Hr[:3, :3] @ np.array(ln)
        # in the idle the striking face is down: blood runs toward it (bone +Z)
        hs.append((p, n, Hr[:3, :3] @ np.array([0, 0, 1.0]), size, drip, seed))
    _CTX['hammer_stains'] = [h_ + (3.0,) for h_ in hs]          # elongated smears
    _CTX['hammer_axes'] = Hr[:3, :3]
    fc = Hr[:3, :3] @ (c + np.array([0, 0, D.HEAD_HALF[1]])) + Hr[:3, 3]
    _CTX['hammer_face'] = (fc, Hr[:3, :3] @ np.array([0, 0, 1.0]), Hr[:3, :3] @ np.array([0, 1.0, 0]))
    _CTX['haft_axis'] = Hr[:3, 1]
    return _CTX


def paint_section(sec, arrays, gains, sk):
    ctx = paint_context(sk)
    Pm = arrays['P'] / WS                     # paint in design units
    H, Wd = Pm.shape[:2]
    idm = arrays['I']
    cov = idm[:, :, 1] > 0.5
    mid = np.clip(np.floor(idm[:, :, 0] * 32.0).astype(int), 0, len(PT.MAT_IDS) - 1)
    albedo = np.zeros((H, Wd, 3))
    flatP = Pm[cov]
    flatN = arrays['N'][cov] * 2 - 1
    A = arrays['A'][cov]
    ao, edge, facet = A[:, 0], A[:, 1], A[:, 2]
    mids = mid[cov]
    res = np.zeros((len(flatP), 3))
    for k, key in enumerate(PT.MAT_IDS):
        sel = mids == k
        if not sel.any():
            continue
        P, N_ = flatP[sel], flatN[sel]
        a_, e_, f_ = ao[sel], edge[sel], facet[sel]
        if key == 'skin':
            c = {'wounds': ctx['wounds'], 'speck': 1.0}
            if sec == 'Head':
                c.update({'eyes': ctx['eyes'], 'head_c': ctx['head_c'], 'mouth': ctx['mouth'], 'head_union': ctx['head_union']})
            r = PT.paint_skin(P, N_, a_, e_, f_, gains, c)
        elif key == 'tooth':
            r = PT.paint_tooth(P, a_, e_, f_, gains)
        elif key == 'shirt':
            rim = FP.shirt_region(P)
            r = PT.paint_shirt(P, a_, e_, f_, gains, {'stains': ctx['shirt_stains'], 'rim': rim})
        elif key == 'iron':
            r = PT.paint_iron(P, a_, e_, f_, gains, {'stains': ctx['hammer_stains'], 'axes': ctx['hammer_axes'],
                                                     'face': ctx['hammer_face']},
                              hammer=(sec == 'Hammer'), N=N_ if sec == 'Hammer' else None)
        elif key == 'wood':
            r = PT.paint_wood(P, a_, e_, f_, gains, ctx['haft_axis'])
        elif key == 'eye':
            r = np.tile(PT.col('eye', 'base', gains), (len(P), 1))
        elif key == 'trousers':
            r = PT.paint_generic('trousers', P, a_, e_, f_, gains, 71, patch_scale=1.0, facet_amp=0.12, contrast=1.2,
                                 cavity=0.40, edge_amt=0.30, levels=3)
            r = PT.mix(r, np.tile(PT.col('trousers', 'light', gains), (len(P), 1)),
                       PT.smoothstep(0.58, 0.66, PT.fbm(P, 2.2, 2, 73)) * 0.45)
            r = PT.mix(r, np.tile(PT.col('trousers', 'rim', gains), (len(P), 1)), PT.smoothstep(0.5, 0.15, a_) * 0.4)
        elif key == 'sash':
            r = PT.paint_generic('sash', P, a_, e_, f_, gains, 81, patch_scale=1.3, facet_amp=0.10, cavity=0.45,
                                 edge_amt=0.35, levels=3)
        elif key == 'buckle':
            r = PT.paint_generic('buckle', P, a_, e_, f_, gains, 93, patch_scale=2.0, facet_amp=0.06, cavity=0.45,
                                 edge_amt=0.7, levels=2)
        elif key == 'strap':
            r = PT.paint_generic('strap', P, a_, e_, f_, gains, 91, patch_scale=1.6, facet_amp=0.06, cavity=0.30,
                                 edge_amt=0.55, levels=2)
        elif key == 'band':
            r = PT.paint_generic('band', P, a_, e_, f_, gains, 95, patch_scale=2.0, facet_amp=0.08, cavity=0.30,
                                 edge_amt=0.6, levels=2)
        else:
            r = PT.paint_generic(key, P, a_, e_, f_, gains, 99)
        res[sel] = r
    albedo[cov] = res
    return PT.fill_uncovered(albedo, cov)


def save_texture(name, albedo_lin):
    srgb = PT.lin_to_srgb(albedo_lin)
    H, Wd = srgb.shape[:2]
    img = bpy.data.images.new(name, Wd, H, alpha=False, float_buffer=False)
    img.colorspace_settings.name = 'sRGB'
    B.set_image_pixels(img, np.concatenate([srgb, np.ones((H, Wd, 1))], 2))
    path = HERE / 'textures' / f'{name}.png'
    img.filepath_raw = str(path)
    img.file_format = 'PNG'
    img.save()
    return img, path


def downsample(a, f=2):
    H, Wd = a.shape[:2]
    return a.reshape(H // f, f, Wd // f, f, 3).mean(axis=(1, 3))


ROUGH = {'Body': 0.88, 'Head': 0.86, 'Shirt': 0.95, 'Gear': 0.8, 'Trousers': 0.95, 'Hammer': 0.7, 'EyeGlow': 0.5}


def final_material(sec, img):
    m = bpy.data.materials.new(f'{NAME}_{sec}')
    m.use_nodes = True
    nt = m.node_tree
    bs = nt.nodes.get('Principled BSDF')
    bs.inputs['Roughness'].default_value = ROUGH[sec]
    if 'Specular IOR Level' in bs.inputs:
        bs.inputs['Specular IOR Level'].default_value = 0.25
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    tex.interpolation = 'Linear'
    nt.links.new(tex.outputs['Color'], bs.inputs['Base Color'])
    if sec == 'EyeGlow':
        nt.links.new(tex.outputs['Color'], bs.inputs['Emission Color'])
        bs.inputs['Emission Strength'].default_value = 2.5
    return m


def flat_material(sec, ob):
    """QUICK runs: keep the preview colours but give the section its final name."""
    keys = [s.material.get('paint', 'skin') for s in ob.material_slots]
    return keys


def texture_sections(objs, sk):
    (HERE / 'textures').mkdir(exist_ok=True)
    gains = load_calibration()
    info = {}
    for sec, ob in objs.items():
        facet_attribute(ob, 100 + SECTIONS.index(sec))
        B.smart_uv(ob, angle=66.0, margin=0.008)
        res = TEX_MASTER if sec != 'EyeGlow' else 512
        arrays = bake_passes(ob, res, 24 if STAGE == 'full' else 8)
        albedo = paint_section(sec, arrays, gains, getattr(sk, 'design', sk))
        tag = f'_{res}' if res != TEX_DELIVERY else '_master'
        master, mp = save_texture(f'{NAME}_{sec}_BaseColor{tag}', albedo)
        dl = albedo if res <= TEX_DELIVERY else downsample(albedo, res // TEX_DELIVERY)
        deliv, dp = save_texture(f'{NAME}_{sec}_BaseColor', dl)
        bpy.data.images.remove(deliv)          # delivery maps live in textures/, not in the .blend
        master.pack()
        mat = final_material(sec, master)
        ob.data.materials.clear()
        ob.data.materials.append(mat)
        ob.data.polygons.foreach_set('material_index', np.zeros(len(ob.data.polygons), np.int32))
        info[sec] = {'master': mp.name, 'delivery': dp.name, 'master_px': res,
                     'delivery_px': min(res, TEX_DELIVERY)}
        log('textured', sec, res)
    for m in list(bpy.data.materials):
        if m.name.startswith('HBP_') and m.users == 0:
            bpy.data.materials.remove(m)
    return info


def name_flat_materials(objs):
    """QUICK runs: one material per section named like the mesh (vertex colours off)."""
    for sec, ob in objs.items():
        for i, s in enumerate(ob.material_slots):
            pass


# ===================================================================== review
LAWN = (150, 214, 84)
SKY = (110, 186, 248)


def setup_review():
    rc = RefCam()
    rc.C = rc.C * WS
    coll = B.collection('REVIEW_ONLY')
    cam = bpy.data.objects.new('ReferenceCamera', bpy.data.cameras.new('ReferenceCamera'))
    coll.objects.link(cam)
    B.camera_from_refcam(cam, rc)
    scene = bpy.context.scene
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = 1086, 1448
    scene.render.resolution_percentage = 100
    # sun high and from the viewer's right-front: shadows fall left and back
    sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
    coll.objects.link(sun)
    d = Vector((float(os.environ.get('HB_SUNX', '-0.42')), float(os.environ.get('HB_SUNY', '0.38')), -0.82)).normalized()
    sun.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    sun.data.energy = float(os.environ.get('HB_SUN', '4.4'))
    sun.data.angle = math.radians(8)
    sun.data.color = B.srgb(255, 250, 238)
    fill = bpy.data.objects.new('Fill', bpy.data.lights.new('Fill', 'AREA'))
    coll.objects.link(fill)
    fill.data.energy = float(os.environ.get('HB_FILL', '330'))
    fill.data.size = 16
    fill.data.color = B.srgb(236, 244, 255)
    fill.location = Vector(rc.C) + Vector((-4.0, 6.0, 4.0))
    fill.rotation_euler = (Vector((0, 0, 6.5)) - fill.location).to_track_quat('-Z', 'Y').to_euler()
    me = bpy.data.meshes.new('Ground')
    me.from_pydata([(-90, -90, 0), (90, -90, 0), (90, 90, 0), (-90, 90, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new('Ground', me)
    coll.objects.link(g)
    gm = bpy.data.materials.new('LawnGround')
    gm.use_nodes = True
    nt_g = gm.node_tree
    bs = nt_g.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*B.srgb(*LAWN), 1)
    bs.inputs['Roughness'].default_value = 0.95
    grey = nt_g.nodes.new('ShaderNodeBsdfDiffuse')
    grey.inputs['Color'].default_value = (*B.srgb(176, 176, 176), 1)
    lpg = nt_g.nodes.new('ShaderNodeLightPath')
    mixg = nt_g.nodes.new('ShaderNodeMixShader')
    outg = nt_g.nodes.get('Material Output')
    nt_g.links.new(lpg.outputs['Is Camera Ray'], mixg.inputs[0])
    nt_g.links.new(grey.outputs[0], mixg.inputs[1])
    nt_g.links.new(bs.outputs[0], mixg.inputs[2])
    nt_g.links.new(mixg.outputs[0], outg.inputs['Surface'])
    me.materials.append(gm)
    w = scene.world or bpy.data.worlds.new('World')
    scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    mix = nt.nodes.new('ShaderNodeMixShader')
    cam_bg = nt.nodes.new('ShaderNodeBackground')
    amb = nt.nodes.new('ShaderNodeBackground')
    lp = nt.nodes.new('ShaderNodeLightPath')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs[0])
    nt.links.new(amb.outputs[0], mix.inputs[1])
    nt.links.new(cam_bg.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    cam_bg.inputs[0].default_value = (*B.srgb(*SKY), 1)
    cam_bg.inputs[1].default_value = 1.0
    amb.inputs[0].default_value = (*B.srgb(200, 222, 250), 1)
    amb.inputs[1].default_value = float(os.environ.get('HB_AMB', '0.38'))
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    return cam, g


def render(path, engine='CYCLES', samples=24, mask_path=None):
    scene = bpy.context.scene
    scene.render.engine = engine
    if engine == 'CYCLES':
        B.enable_gpu()
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
        scene.cycles.max_bounces = 4
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    if mask_path:
        ground = bpy.data.objects.get('Ground')
        ground.hide_render = True
        scene.render.engine = 'BLENDER_WORKBENCH'
        scene.display.shading.light = 'FLAT'
        scene.display.shading.color_type = 'SINGLE'
        scene.display.shading.single_color = (1, 1, 1)
        scene.render.film_transparent = True
        scene.render.image_settings.color_mode = 'RGBA'
        scene.render.filepath = str(mask_path)
        bpy.ops.render.render(write_still=True)
        ground.hide_render = False
        scene.render.film_transparent = False
        scene.render.image_settings.color_mode = 'RGB'
        scene.render.engine = engine


# ===================================================================== main
def build_all():
    B.clear_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    coll = B.collection(NAME)
    global WS
    sk = PO.Skeleton()
    log('skeleton', len(sk.order), 'deform bones; REF length error %.2e' % sk.ref_length_err)
    skin = build_skin(coll)
    parts = build_parts(coll, sk)
    # crown of the reference pose (the skull top rides rigidly on the Head bone)
    V, F = B.mesh_arrays(skin)
    top = V[(V[:, 2] > D.HEAD_C[2] + 0.4) & (np.abs(V[:, 0]) < 1.3) & (np.abs(V[:, 1] - D.HEAD_C[1]) < 1.4)]
    Xh = sk.ref['Head'] @ np.linalg.inv(sk.rest['Head'])
    crown = float((top @ Xh[:3, :3].T + Xh[:3, 3])[:, 2].max())
    WS = D.CROWN / crown
    log('reference-pose crown %.4f (design units) -> world scale %.5f' % (crown, WS))
    sk_d = sk
    sk = ScaledSkeleton(sk_d, WS)
    rig = build_rig(coll, sk)
    stats = skin_and_part_weights(skin, parts, rig)
    for ob in [skin] + parts:
        V, F = B.mesh_arrays(ob)
        B.set_coords(ob, V * WS)
    log('weights', stats)
    body_skin, head_skin = split_skin(skin)
    groups = {s: [] for s in SECTIONS}
    groups['Body'].append(body_skin)
    groups['Head'].append(head_skin)
    for ob in parts:
        groups[ob['section']].append(ob)
    bind([o for obs in groups.values() for o in obs], rig)
    objs = join_sections(groups)
    for sec, ob in objs.items():
        log('section', ob.name, B.tri_count(ob))
    return sk, rig, objs, stats


def main():
    sk, rig, objs, stats = build_all()
    tex_info = {}
    if TEXTURES:
        rig.data.pose_position = 'REST'
        tex_info = texture_sections(objs, sk)
        rig.data.pose_position = 'POSE'
    else:
        for sec, ob in objs.items():
            for s in ob.material_slots:
                pass
    rig.animation_data_create()
    ref = PO.Pose(sk.design)
    make_action(rig, sk, 'ReferencePose', [(1, ref), (2, ref)])
    rig.animation_data.action = bpy.data.actions['ReferencePose']
    bpy.context.scene.frame_set(1)
    setup_review()
    if STAGE == 'probe':
        render(WORK / 'probe_render.png', samples=int(os.environ.get('HB_SAMPLES', '24')),
               mask_path=WORK / 'probe_mask.png')
        bpy.ops.wm.save_as_mainfile(filepath=str(WORK / 'stage_probe.blend'))
        log('probe done')
        return
    import hb_deliver as FD
    FD.WS = WS
    FD.full_stage(rig, sk, objs, tex_info, stats, STAGE, make_action)


if __name__ == '__main__':
    main()
