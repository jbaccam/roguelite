"""Frost Cyclops boss: generator. Run with Blender 5.2 in background mode:

    blender -b --factory-startup --python build_frost_cyclops.py

Environment:
    FC_STAGE=probe   geometry + rig + ReferencePose + one reference render (fast loop)
    FC_STAGE=full    everything: bake/paint textures, actions, renders, exports, .blend
    FC_VOX=0.05      skin voxel size (studs)

Self-contained: imports only the fc_*.py modules in this folder.
"""
import json
import math
import os
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bpy                      # noqa: E402
import numpy as np              # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import fc_blender as B          # noqa: E402
import fc_design as D           # noqa: E402
import fc_parts as FP           # noqa: E402
import fc_weights as WT         # noqa: E402
import fc_pose as PO            # noqa: E402
from fc_camera import RefCam    # noqa: E402
from fc_sdf import Grid, surface_nets, eval_prims  # noqa: E402

STAGE = os.environ.get('FC_STAGE', 'full')
VOX = float(os.environ.get('FC_VOX', '0.05'))
WORK = HERE / '_work'
WORK.mkdir(exist_ok=True)
T0 = time.time()
NAME = 'FrostCyclops'


def log(*a):
    print('[FC %6.1fs]' % (time.time() - T0), *a, flush=True)


# ============================================================ skin extraction
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
    """Laplacian smoothing of the surface-nets stair steps, re-projected onto
    the SDF zero set each pass so features (brow, lips) keep their shape."""
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


def sdf_to_mesh(prims, h, smooth=3, pad=0.3):
    lo = np.full(3, 1e9)
    hi = np.full(3, -1e9)
    for p in prims:
        if p.op != 'union':
            continue
        a, b = p.bounds()
        lo = np.minimum(lo, a)
        hi = np.maximum(hi, b)
    g = Grid(lo - pad, hi + pad, h)
    g.build(prims)
    V, Q = surface_nets(g)
    if smooth:
        V = clean_surface(g, V, Q, smooth)
    return V, Q


# ================================================================ materials
MAT_COLORS = {       # preview albedo (sRGB) per paint recipe; the baked atlas replaces these
    'skin': (150, 168, 200), 'nail': (170, 184, 210), 'mouth': (40, 26, 34), 'fur': (232, 222, 208),
    'leather': (110, 86, 80), 'loin': (66, 62, 78), 'buckle': (150, 146, 150), 'stone': (170, 164, 164),
    'wood': (108, 80, 68), 'strap': (86, 66, 62), 'eye': (240, 246, 252), 'tooth': (236, 224, 208),
    'lid': (150, 168, 200),
}


def preview_material(key):
    name = 'FC_' + key
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*B.srgb(*MAT_COLORS[key]), 1)
    bs.inputs['Roughness'].default_value = 0.9
    m['paint'] = key
    return m


# ================================================================== geometry
SECTIONS = ['Body', 'Head', 'Eye', 'Fur', 'Gear', 'Club']
TARGET_TRIS = {'Body': 17500, 'Head': 7000, 'Eye': 700, 'Fur': 14000, 'Gear': 7000, 'Club': 5000}


def to_rest(V, attach):
    if attach in ('RightArm', 'LeftArm'):
        side = attach[:-3]
        M = D.rest_arm_rotation(side)
        S = D.J[side + 'UpperArm']
        return (V - S) @ M.T + S
    return V


PART_WEIGHTS = {}          # weights fixed while inverse-skinning a part (reused at bind time)
INVERSE_SKIN = ('MantleTufts', 'MantlePelt')


def mantle_weights_ref(V_ref, ref_body):
    """Skin weights of fur vertices, evaluated against the REFERENCE-pose body.
    The torso share is moved to the Mantle_L/R secondary bones."""
    from fc_parts import normals_at
    d = eval_prims(ref_body, V_ref)
    g = normals_at(ref_body, V_ref)
    W = WT.body_weights(V_ref - g * d[:, None], ref_body, dict(D.J))
    rel = (V_ref - D.TORSO_O) @ D.RT
    left = WT._smoothstep(-0.6, 0.6, rel[:, 0])
    torso = W.pop('UpperTorso', 0) + W.pop('Head', 0)
    W['Mantle_L'] = torso * left
    W['Mantle_R'] = torso * (1 - left)
    W.pop('Belly', None)
    W.pop('LowerTorso', None)
    return W


def inverse_skin(V_ref, W):
    """Rest positions whose linear-blend skinning in the ReferencePose gives back
    V_ref exactly. Only the arm bones differ between REST and REF (a rigid
    rotation of each arm about its shoulder)."""
    n = len(V_ref)
    A = np.tile(np.eye(3), (n, 1, 1))
    t = np.zeros((n, 3))
    tot = np.zeros(n)
    for side in ('Right', 'Left'):
        a = sum(np.broadcast_to(np.asarray(W.get(side + b, 0.0), float), (n,)) for b in ('UpperArm', 'LowerArm', 'Hand'))
        Rinv = D.rest_arm_rotation(side).T
        S = D.J[side + 'UpperArm']
        A += a[:, None, None] * (Rinv - np.eye(3))[None]
        t += a[:, None] * (S - Rinv @ S)[None]
        tot += a
    return np.einsum('nij,nj->ni', np.linalg.inv(A), V_ref - t)


def build_geometry():
    coll = B.collection(NAME)
    rest_body = D.body_prims(rest=True)
    ref_body = D.body_prims(rest=False)
    log('skin sdf ...')
    Vs, Qs = sdf_to_mesh(rest_body, VOX)
    log('skin verts', len(Vs), 'quads', len(Qs))
    skin = B.mesh_object('SkinRaw', Vs, Qs, coll, [preview_material('skin')])
    # detail weighting for the decimation: face, ears, toes keep more polygons
    own = WT.ownership(rest_body, Vs)
    head = own.get('head', 0)
    toes = np.zeros(len(Vs))
    for side in ('Right', 'Left'):
        tp = [p for p in rest_body if p.bone == side + 'Toes']
        dt = np.min([p.sdf(Vs) for p in tp], axis=0)
        toes = np.maximum(toes, 1 - np.clip((dt + 0.1) / 0.5, 0, 1))
    relh = (Vs - D.HEAD_C) @ D.RH
    face = np.clip((-relh[:, 1] - 0.3) / 0.5, 0, 1)
    detail = np.clip(np.maximum(head * (0.2 + 0.8 * face), toes * 0.6), 0, 1)
    vg = skin.vertex_groups.new(name='detail')
    for w in np.unique(np.round(detail, 2)):
        idx = np.nonzero(np.round(detail, 2) == w)[0].tolist()
        if w > 0 and idx:
            vg.add(idx, float(w), 'REPLACE')
    VGF = float(os.environ.get('FC_VGF', '0.02'))
    B.decimate(skin, int(os.environ.get('FC_SKIN_TRIS', '8200')), vgroup='detail' if VGF > 0 else None, vg_factor=VGF)
    log('skin decimated', B.tri_count(skin))
    # split skin into Body / Head sections by face ownership
    V, F = B.mesh_arrays(skin)
    cent = np.array([V[list(f)].mean(0) for f in F])
    own_f = WT.ownership(rest_body, cent)
    is_head = own_f.get('head', 0) > 0.5
    parts_by_section = {s: [] for s in SECTIONS}
    for flag, sec in ((False, 'Body'), (True, 'Head')):
        sel = [f for f, h in zip(F, is_head) if h == flag]
        used = sorted(set(i for f in sel for i in f))
        remap = {o: n for n, o in enumerate(used)}
        ob = B.mesh_object(f'{sec}Skin', V[used], [tuple(remap[i] for i in f) for f in sel], coll,
                           [preview_material('skin')])
        ob['kind'] = 'skin'
        parts_by_section[sec].append(ob)
    bpy.data.objects.remove(skin, do_unlink=True)
    # hands (finer grid)
    for side in ('Right', 'Left'):
        Vh, Qh = sdf_to_mesh(D.hand_prims(side, 'REST'), VOX * 0.6)
        ob = B.mesh_object(f'Hand{side}', Vh, Qh, coll, [preview_material('skin')])
        B.decimate(ob, 1700)
        ob['kind'] = 'hand'
        ob['side'] = side
        parts_by_section['Body'].append(ob)
        log('hand', side, B.tri_count(ob))
    # accessories (built in the reference pose, moved into the rest pose)
    budgets = {'ClubStone': 900, 'Buckle': 360, 'Eyeball': 520, 'EyelidUpper': 420, 'TuskL': 160, 'TuskR': 160,
               'TeethUpper': 360, 'TeethLower': 300, 'MantlePelt': 3200, 'Rivet+9': 40, 'Rivet-9': 40}
    for p in FP.all_parts(ref_body):
        V = p.V if p.name in INVERSE_SKIN else to_rest(p.V, p.attach)
        ob = B.mesh_object(p.name, V, p.F, coll, [preview_material(p.mat if p.mat in MAT_COLORS else 'skin')])
        if p.kind == 'sdf':
            B.decimate(ob, budgets.get(p.name, 600))
        if p.name in INVERSE_SKIN:
            Vref, _ = B.mesh_arrays(ob)
            names, M, bad = WT.finalize(mantle_weights_ref(Vref, ref_body), len(Vref))
            W = {b: M[:, j] for j, b in enumerate(names)}
            PART_WEIGHTS[p.name] = W
            B.set_coords(ob, inverse_skin(Vref, W))
        a_ = ob.data.attributes.new('fc_loin', 'INT', 'POINT')
        a_.data.foreach_set('value', np.full(len(ob.data.vertices), 1 if p.name == 'Loincloth' else 0, np.int32))
        ob['kind'] = 'part'
        ob['part'] = p.name
        ob['bone'] = p.bone or ''
        ob['attach'] = p.attach or ''
        parts_by_section[p.section].append(ob)
    for sec, obs in parts_by_section.items():
        log(sec, [(o.name, B.tri_count(o)) for o in obs])
    return parts_by_section


# ======================================================================= rig
DEFORM = []   # (name, parent)


def build_rig(coll, sk):
    """Armature from the numpy skeleton (fc_pose.Skeleton), in the REST pose."""
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
    # non-deform helpers (excluded from exports): IK targets/poles, eye target, club impact point
    ctrl = {}
    Jr = D.rest_joints()
    for side in ('Right', 'Left'):
        w = Jr[side + 'Hand']
        ctrl['IK_Hand_' + side[0]] = (w, w + np.array([0, 0.8, 0]), 'Root', None)
        e = Jr[side + 'LowerArm']
        ctrl['Pole_Elbow_' + side[0]] = (e + np.array([0, 3.0, 0]), e + np.array([0, 3.6, 0]), 'Root', None)
        a = D.J[side + 'Foot']
        ctrl['IK_Foot_' + side[0]] = (a, a + np.array([0, -0.8, 0]), 'Root', None)
        k = D.J[side + 'LowerLeg']
        ctrl['Pole_Knee_' + side[0]] = (k + np.array([0, -3.0, 0]), k + np.array([0, -3.6, 0]), 'Root', None)
    et = D.J['Eye'] + D.RH @ np.array([0, -6.0, 0])
    ctrl['EyeTarget'] = (et, et + np.array([0, 0, 0.5]), 'Head', None)
    # ClubImpact: centre of the stone's flat striking face, +Y along the face normal
    Xr = sk.rest['Club'] @ np.linalg.inv(sk.ref['Club'])
    Fi = Xr[:3, :3] @ FP.club_impact_point() + Xr[:3, 3]
    nrm = Xr[:3, :3] @ D.club_axis()[1]
    ctrl['ClubImpact'] = (Fi, Fi + nrm * 0.6, 'Club', sk.rest['Club'][:3, 2])
    for name, (h, t, par, roll) in ctrl.items():
        b = eb.new(name)
        b.head = Vector(h)
        b.tail = Vector(t)
        if roll is not None:
            b.align_roll(Vector(roll))
        b.use_deform = False
        b.parent = eb[par]
    bpy.ops.object.mode_set(mode='OBJECT')
    for side in ('Right', 'Left'):
        for chain, tgt, pole in (('LowerArm', 'IK_Hand_', 'Pole_Elbow_'), ('LowerLeg', 'IK_Foot_', 'Pole_Knee_')):
            c = rig.pose.bones[side + chain].constraints.new('IK')
            c.target = rig
            c.subtarget = tgt + side[0]
            c.pole_target = rig
            c.pole_subtarget = pole + side[0]
            c.chain_count = 2
            c.influence = 0.0          # present for animators; FK drives the exported clips
    c = rig.pose.bones['Eye'].constraints.new('DAMPED_TRACK')
    c.target = rig
    c.subtarget = 'EyeTarget'
    c.influence = 0.0
    rig.show_in_front = True
    arm.display_type = 'OCTAHEDRAL'
    return rig


def key_pose(rig, sk, mats, frame, prev=None):
    """Key every deform bone so the armature reaches `mats` (armature space).
    Local (basis) matrices are computed directly: basis = inv(Rest_b) @ Rest_p @
    inv(Pose_p) @ Pose_b. Quaternions are kept hemisphere-continuous with `prev`."""
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
    """keys: [(frame, Pose|mats)]"""
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    rig.animation_data.action = act
    prev = {}
    for fr, P in keys:
        mats = P.m if hasattr(P, 'm') else P
        prev = key_pose(rig, sk, mats, fr, prev)
    for mname, fr in markers:
        mk = act.pose_markers.new(mname)
        mk.frame = fr
    act.frame_range = (keys[0][0], keys[-1][0])
    return act


# ==================================================================== weights
def skin_weights(sections, rig):
    rest_body = D.body_prims(rest=True)
    RJ = D.rest_joints()
    deform = [b.name for b in rig.data.bones if b.use_deform]
    stats = {}
    for sec, obs in sections.items():
        for ob in obs:
            V, F = B.mesh_arrays(ob)
            n = len(V)
            kind = ob.get('kind')
            if kind == 'skin':
                W = WT.body_weights(V, rest_body, RJ)
                adj = WT.adjacency(F, n)
                W = WT.smooth(W, adj, n, iters=5, lam=0.5)
            elif kind == 'hand':
                side = ob['side']
                W = WT.hand_weights(V, D.hand_prims(side, 'REST'), side, RJ)
                adj = WT.adjacency(F, n)
                W = WT.smooth(W, adj, n, iters=2, lam=0.4)
            else:
                W = accessory_weights(ob, V, F, rest_body, RJ)
            names, M, bad = WT.finalize(W, n)
            if bad.any():
                log('WARNING unweighted verts', ob.name, int(bad.sum()))
            for gname in list(ob.vertex_groups):
                ob.vertex_groups.remove(gname)
            for j, bname in enumerate(names):
                if bname not in deform:
                    raise RuntimeError(f'{ob.name}: weight for unknown bone {bname}')
                col = M[:, j]
                nz = np.nonzero(col > 0)[0]
                if len(nz) == 0:
                    continue
                vg = ob.vertex_groups.new(name=bname)
                for w in np.unique(np.round(col[nz], 4)):
                    idx = nz[np.round(col[nz], 4) == w].tolist()
                    vg.add(idx, float(w), 'REPLACE')
            stats[ob.name] = {'verts': n, 'bones': len(names)}
    return stats


def _nearest_skin_weights(V, rest_body, RJ):
    """Weights the body skin would have at these points (projected onto the skin)."""
    from fc_parts import normals_at
    d = eval_prims(rest_body, V)
    g = normals_at(rest_body, V)
    Pn = V - g * d[:, None]
    return WT.body_weights(Pn, rest_body, RJ)


def accessory_weights(ob, V, F, rest_body, RJ):
    name = ob.get('part', ob.name)
    bone = ob.get('bone', '')
    n = len(V)
    if bone:
        return {bone: np.ones(n)}
    if name in PART_WEIGHTS:
        return dict(PART_WEIGHTS[name])
    if name in ('MantleTufts', 'MantlePelt', 'HipFur'):
        W = _nearest_skin_weights(V, rest_body, RJ)
        if name == 'HipFur':
            return W
        # torso share of the mantle moves to the Mantle_L/R secondary bones
        rel = (V - D.TORSO_O) @ D.RT
        left = WT._smoothstep(-0.6, 0.6, rel[:, 0])
        torso = W.pop('UpperTorso', 0) + W.pop('Head', 0) * 1.0
        W['Mantle_L'] = torso * left
        W['Mantle_R'] = torso * (1 - left)
        W.pop('Belly', None)
        W.pop('LowerTorso', None)
        return W
    if name in ('Loincloth', 'BeltTail0', 'BeltTail1'):
        Pb, Nb, Rb = FP.belt_ring(D.body_prims(rest=False))
        c = FP.BELT_C
        rel = (V - c) @ D.RP
        th = np.degrees(np.arctan2(rel[:, 0], -rel[:, 1])) - FP.BELT_FRONT
        th = (th + 180) % 360 - 180
        top = FP.BELT_C[2] - 0.6
        s = np.clip((top - V[:, 2]) / 3.4, 0, 1)
        up = 1 - WT._smoothstep(0.0, 0.22, s)
        mid = WT._smoothstep(0.0, 0.22, s) * (1 - WT._smoothstep(0.35, 0.65, s))
        low = WT._smoothstep(0.35, 0.65, s)
        front = 1 - WT._smoothstep(50, 80, np.abs(th))
        back = WT._smoothstep(105, 135, np.abs(th))
        side = 1 - front - back
        # The side panels below the belt band ride fully on the thighs and the
        # front flap's lower half 60 % on them, so a raised knee lifts the skirt
        # instead of passing through it (checked in AttackMotionChecks: Stomp).
        side_leg, front_leg = 1.0, 0.6
        W = {'LowerTorso': up + side * (mid + low) * (1 - side_leg)}
        W['Loincloth_Front_1'] = front * mid
        W['Loincloth_Front_2'] = front * low * (1 - front_leg)
        W['Loincloth_Back_1'] = back * mid
        W['Loincloth_Back_2'] = back * low
        legL = WT._smoothstep(-0.3, 0.6, rel[:, 0])
        W['LeftUpperLeg'] = side * (mid + low) * side_leg * legL + front * low * front_leg * legL
        W['RightUpperLeg'] = side * (mid + low) * side_leg * (1 - legL) + front * low * front_leg * (1 - legL)
        return W
    return {'LowerTorso': np.ones(n)}


def bind(sections, rig):
    for sec, obs in sections.items():
        for ob in obs:
            ob.parent = rig
            m = ob.modifiers.new('Armature', 'ARMATURE')
            m.object = rig
            m.use_deform_preserve_volume = False


# ================================================================== textures
import fc_paint as PT   # noqa: E402

TEX_MASTER = int(os.environ.get('FC_TEX', '2048'))
TEX_DELIVERY = 1024
CAL_PATH = HERE / 'calibration.json'


def load_calibration():
    if CAL_PATH.exists():
        return {k: tuple(v) for k, v in json.loads(CAL_PATH.read_text())['gains'].items()}
    return {}


def join_sections(sections):
    out = {}
    for sec, obs in sections.items():
        if not obs:
            continue
        ob = B.join(obs, f'{NAME}_{sec}') if len(obs) > 1 else obs[0]
        ob.name = f'{NAME}_{sec}'
        ob.data.name = f'{NAME}_{sec}'
        # keep one Armature modifier
        mods = [m for m in ob.modifiers if m.type == 'ARMATURE']
        for m in mods[1:]:
            ob.modifiers.remove(m)
        out[sec] = ob
    return out


def facet_attribute(ob, seed):
    """Per-face random (plus a per-island random so each fur tuft or strap reads
    as its own painted piece)."""
    me = ob.data
    n = len(me.polygons)
    rng = np.random.default_rng(seed)
    face_r = rng.random(n)
    # islands via union-find over shared vertices
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
    isl_r = rng.random(len(uniq))[inv]
    B.face_attribute(ob, 'facet', 0.55 * face_r + 0.45 * isl_r)


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
        ao.inputs['Distance'].default_value = 0.45
        ao.samples = 16
        bev = nt.nodes.new('ShaderNodeBevel')
        bev.samples = 8
        bev.inputs['Radius'].default_value = 0.06
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


def bake_passes(ob, res):
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    B.enable_gpu()
    keys = [s.material.get('paint', 'skin') for s in ob.material_slots]
    orig = [s.material for s in ob.material_slots]
    B.activate(ob)
    arrays = {}
    for pname, samples in (('P', 1), ('N', 1), ('I', 1), ('A', 24)):
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


def paint_section(sec, ob, arrays, gains):
    Pm = arrays['P']
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
    rest_body = D.body_prims(rest=True)
    for k, key in enumerate(PT.MAT_IDS):
        sel = mids == k
        if not sel.any():
            continue
        P, N_ = flatP[sel], flatN[sel]
        if key == 'skin':
            if sec in ('Body', 'Head'):
                c = PT.paint_skin(P, N_, ao[sel], edge[sel], facet[sel], gains, rest_body)
            else:
                c = PT.paint_generic('skin', P, ao[sel], edge[sel], facet[sel], gains, 1)
        elif key == 'eye':
            fwd = D.RH @ np.array([0, -1.0, 0])
            c = PT.paint_eye(P, D.J['Eye'], fwd, np.array([0, 0, 1.0]), gains, 0.31)
        elif key == 'lid':
            c = PT.paint_lid(P, D.J['Eye'], np.array([0, 0, 1.0]), D.RH @ np.array([0, -1.0, 0]), gains)
        elif key == 'wood':
            _, hdir = D.club_axis()
            hdir = D.rest_arm_rotation('Right') @ hdir
            c = PT.paint_generic('wood', P, ao[sel], edge[sel], facet[sel], gains, 23, streak_axis=hdir,
                                 patch_scale=1.6, contrast=1.3)
        elif key == 'loin':
            c = PT.paint_generic('loin', P, ao[sel], edge[sel], facet[sel], gains, 31, streak_axis=(0, 0, 1),
                                 patch_scale=1.3, contrast=1.3, facet_amp=0.06)
            worn = PT.smoothstep(0.60, 0.70, PT.fbm(P, 1.6, 2, 33))           # lighter worn leather patches
            c = PT.mix(c, c * 1.55, worn * 0.8)
        elif key == 'fur':
            c = PT.paint_generic('fur', P, ao[sel], edge[sel], facet[sel], gains, 41, patch_scale=1.2, contrast=1.0,
                                 facet_amp=0.12, cavity=0.30)
        elif key in ('stone', 'buckle'):
            c = PT.paint_generic(key, P, ao[sel], edge[sel], facet[sel], gains, 51, patch_scale=1.1, contrast=1.1)
            spots = PT.value_noise(P, 14.0, 57)
            c *= (1.0 - 0.22 * PT.smoothstep(0.74, 0.82, spots))[:, None]
        elif key in ('leather', 'strap'):
            c = PT.paint_generic(key, P, ao[sel], edge[sel], facet[sel], gains, 61 + k, facet_amp=0.04,
                                 patch_scale=1.6, contrast=1.1)
        else:
            c = PT.paint_generic(key, P, ao[sel], edge[sel], facet[sel], gains, 61 + k)
        res[sel] = c
    albedo[cov] = res
    albedo = PT.fill_uncovered(albedo, cov)
    return albedo


def save_texture(name, albedo_lin, res):
    srgb = PT.lin_to_srgb(albedo_lin)
    H, Wd = srgb.shape[:2]
    img = bpy.data.images.new(name, Wd, H, alpha=False, float_buffer=False)
    img.colorspace_settings.name = 'sRGB'
    rgba = np.concatenate([srgb, np.ones((H, Wd, 1))], 2)
    B.set_image_pixels(img, rgba)
    path = HERE / 'textures' / f'{name}.png'
    img.filepath_raw = str(path)
    img.file_format = 'PNG'
    img.save()
    return img, path


def downsample(albedo_lin, f=2):
    H, Wd = albedo_lin.shape[:2]
    return albedo_lin.reshape(H // f, f, Wd // f, f, 3).mean(axis=(1, 3))


ROUGH = {'Body': 0.9, 'Head': 0.88, 'Eye': 0.32, 'Fur': 0.95, 'Gear': 0.85, 'Club': 0.9}


def final_material(sec, img):
    m = bpy.data.materials.new(f'{NAME}_{sec}')
    m.use_nodes = True
    nt = m.node_tree
    bs = nt.nodes.get('Principled BSDF')
    bs.inputs['Roughness'].default_value = ROUGH[sec]
    if 'Specular IOR Level' in bs.inputs:
        bs.inputs['Specular IOR Level'].default_value = 0.35 if sec == 'Eye' else 0.2
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    tex.interpolation = 'Linear'
    nt.links.new(tex.outputs['Color'], bs.inputs['Base Color'])
    return m


def texture_sections(objs):
    (HERE / 'textures').mkdir(exist_ok=True)
    gains = load_calibration()
    info = {}
    for sec, ob in objs.items():
        facet_attribute(ob, 100 + SECTIONS.index(sec))
        B.smart_uv(ob, angle=66.0, margin=0.012)
        res = TEX_MASTER if sec not in ('Eye',) else min(TEX_MASTER, 1024)
        arrays = bake_passes(ob, res)
        albedo = paint_section(sec, ob, arrays, gains)
        master, mp = save_texture(f'{NAME}_{sec}_BaseColor_{res}', albedo, res)
        dl = albedo if res <= TEX_DELIVERY else downsample(albedo, res // TEX_DELIVERY)
        deliv, dp = save_texture(f'{NAME}_{sec}_BaseColor', dl, TEX_DELIVERY)
        master.pack()
        mat = final_material(sec, master)
        ob.data.materials.clear()
        ob.data.materials.append(mat)
        ob.data.polygons.foreach_set('material_index', np.zeros(len(ob.data.polygons), np.int32))
        info[sec] = {'master': mp.name, 'delivery': dp.name, 'master_px': res, 'delivery_px': TEX_DELIVERY}
        log('textured', sec, res)
    for m in list(bpy.data.materials):
        if m.name.startswith('FC_') and m.users == 0:
            bpy.data.materials.remove(m)
    return info


# ===================================================================== review
SNOW = (231, 235, 249)
SKY = (150, 190, 238)


def setup_review():
    """Camera, sun, sky and snow ground in a REVIEW_ONLY collection (not exported)."""
    rc = RefCam()
    coll = B.collection('REVIEW_ONLY')
    cam = bpy.data.objects.new('ReferenceCamera', bpy.data.cameras.new('ReferenceCamera'))
    coll.objects.link(cam)
    B.camera_from_refcam(cam, rc)
    scene = bpy.context.scene
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = 1086, 1448
    scene.render.resolution_percentage = 100
    # sun from the viewer's front-left, high: the reference's cast shadows fall
    # to the right of the feet and club, a little behind them
    sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
    coll.objects.link(sun)
    sun_dir = Vector((float(os.environ.get('FC_SUNX', '0.12')), float(os.environ.get('FC_SUNY', '0.30')), -0.95)).normalized()          # direction light travels
    sun.rotation_euler = sun_dir.to_track_quat('-Z', 'Y').to_euler()
    sun.data.energy = float(os.environ.get('FC_SUN', '2.6'))
    sun.data.angle = math.radians(6)
    sun.data.color = B.srgb(255, 250, 240)
    # soft fill from the camera side so the shadow side stays blue, not black
    fill = bpy.data.objects.new('Fill', bpy.data.lights.new('Fill', 'AREA'))
    coll.objects.link(fill)
    fill.data.energy = float(os.environ.get('FC_FILL', '420'))
    fill.data.size = 14
    fill.data.color = B.srgb(230, 236, 255)
    fill.location = Vector(rc.C) + Vector((-3.0, 4.0, 5.0))
    fill.rotation_euler = (Vector((0, 0, 6.5)) - fill.location).to_track_quat('-Z', 'Y').to_euler()
    # snow ground
    me = bpy.data.meshes.new('Ground')
    me.from_pydata([(-80, -80, 0), (80, -80, 0), (80, 80, 0), (-80, 80, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new('Ground', me)
    coll.objects.link(g)
    gm = bpy.data.materials.new('SnowGround')
    gm.use_nodes = True
    bs = gm.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*B.srgb(*SNOW), 1)
    bs.inputs['Roughness'].default_value = 0.95
    me.materials.append(gm)
    # world: plain sky backdrop, sky fill light
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
    amb.inputs[0].default_value = (*B.srgb(196, 208, 232), 1)
    amb.inputs[1].default_value = float(os.environ.get('FC_AMB', '0.50'))
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
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


CLOSEUPS = {'Face': (440, 170, 650, 390), 'FistL': (790, 720, 1070, 1070), 'HandR': (60, 590, 330, 930),
            'Feet': (280, 1100, 960, 1320), 'Belt': (300, 660, 820, 1110), 'Club': (30, 880, 370, 1320)}


def render_closeups(prefix, scale=3, samples=24, which=None):
    """Border-cropped renders of the reference view at `scale`x resolution, so
    details can be inspected from exactly the reference perspective."""
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = samples
    rx, ry = scene.render.resolution_x, scene.render.resolution_y
    scene.render.resolution_percentage = 100 * scale
    scene.render.use_border = True
    scene.render.use_crop_to_border = True
    for name, (x0, y0, x1, y1) in CLOSEUPS.items():
        if which and name not in which:
            continue
        scene.render.border_min_x = x0 / rx
        scene.render.border_max_x = x1 / rx
        scene.render.border_min_y = 1 - y1 / ry
        scene.render.border_max_y = 1 - y0 / ry
        scene.render.filepath = str(prefix) + f'_{name}.png'
        bpy.ops.render.render(write_still=True)
    scene.render.use_border = False
    scene.render.use_crop_to_border = False
    scene.render.resolution_percentage = 100


def build_actions(rig, sk):
    scene = bpy.context.scene
    scene.render.fps = 30
    info = {}
    ref = PO.Pose(sk)
    make_action(rig, sk, 'ReferencePose', [(1, ref), (2, ref)])
    rom = PO.rom_keys(sk)
    step = 8
    make_action(rig, sk, 'RigTest_ROM', [(1 + i * step, p) for i, (lab, p) in enumerate(rom)] +
                [(1 + len(rom) * step, ref)])
    info['RigTest_ROM'] = {'poses': [(1 + i * step, lab) for i, (lab, p) in enumerate(rom)]}
    if os.environ.get('FC_ATTACKS', '1') == '1':
        import fc_motion as MO
        # Ground Slam: every frame keyed from the lever solver (what is checked is what is exported)
        spec = MO.ground_slam_spec(sk)
        frames = MO.lever_frames(sk, spec)
        make_action(rig, sk, 'GroundSlam', [(f, P) for f, P, a in frames], markers=[('Impact', spec['impact'])])
        mid = min((abs((a[0] + 180) % 360 - 180), f) for f, P, a in frames
                  if a is not None and spec['strike'][0] <= f <= spec['strike'][1])[1]
        Pimp = {f: P for f, P, a in frames}[spec['impact']]
        Fi = MO.club_world(Pimp, FP.club_impact_point())[0]
        ns = Pimp.xform('Club')[:3, :3] @ FP.strike_normal()
        info['GroundSlam'] = {'frames': [frames[0][0], frames[-1][0]], 'impact_frame': spec['impact'],
                              'labels': {'carry': 1, 'windup': spec['windup'], 'mid-swing': mid,
                                         'impact': spec['impact'], 'recovery': spec['recovery']},
                              'strike_window': list(spec['strike']),
                              'swing_plane_normal': [round(float(v), 4) for v in spec['n_out']],
                              'club_impact_point_root': [round(float(v), 4) for v in Fi],
                              'strike_face_normal_at_impact': [round(float(v), 4) for v in ns]}
        st = MO.stomp_frames(sk)
        make_action(rig, sk, 'Stomp', [(f, P) for f, P, x in st['frames']], markers=[('Impact', st['impact'])])
        Pst = {f: P for f, P, x in st['frames']}[st['impact']]
        A = D.J['LeftFoot']
        fdir = D.FOOT_DIR['Left']
        sole_ref = np.array([A[0] + fdir[0] * 0.75, A[1] + fdir[1] * 0.75, 0.0])
        sole = Pst.point('LeftFoot', sole_ref)
        info['Stomp'] = {'frames': [st['frames'][0][0], st['frames'][-1][0]], 'impact_frame': st['impact'],
                         'labels': st['labels'],
                         'StompImpact_root': [round(float(v), 4) for v in sole],
                         'StompSpikeDirection_root': [0.0, -1.0, 0.0]}
    return info


def swap_images(objs, tex_info, which):
    """Point each section material at its master (2048) or delivery (1024) map."""
    for sec, ob in objs.items():
        name = tex_info[sec]['master' if which == 'master' else 'delivery']
        img = bpy.data.images.get(Path(name).stem) or bpy.data.images.load(str(HERE / 'textures' / name))
        img.colorspace_settings.name = 'sRGB'
        for n in ob.data.materials[0].node_tree.nodes:
            if n.type == 'TEX_IMAGE':
                n.image = img


def full_stage(rig, sk, objs, tex_info, actions, weight_stats):
    import fc_deliver as FD
    scene = bpy.context.scene
    cam = scene.camera
    PREVIEWS = HERE / 'previews'
    PREVIEWS.mkdir(exist_ok=True)
    rc = RefCam()
    # 1. the reference match, from the posed rig, plus its silhouette mask
    rig.animation_data.action = bpy.data.actions['ReferencePose']
    scene.frame_set(1)
    motion_only = STAGE == 'motion'          # FC_STAGE=motion: attacks, checks, exports, reports only
    if not motion_only:
        render(PREVIEWS / 'Reference_Match.png', samples=int(os.environ.get('FC_SAMPLES', '96')),
               mask_path=WORK / 'render_mask.png')
        render_closeups(PREVIEWS / 'Detail', which=None, samples=48)
    # 2. review renders (a free camera; the reference camera is restored after)
    free = bpy.data.objects.new('ReviewCamera', bpy.data.cameras.new('ReviewCamera'))
    bpy.data.collections['REVIEW_ONLY'].objects.link(free)
    scene.camera = free
    if not motion_only:
        FD.turnaround(free)
        FD.face_closeup(free)
        FD.bone_overlay(free)
        FD.rom_sheet(actions, free)
    atk = FD.attack_sheet(actions, free)
    FD.swing_arcs(actions, free)
    vids = FD.attack_videos(actions, free)
    scene.camera = cam
    B.camera_from_refcam(cam, rc)
    scene.render.resolution_x, scene.render.resolution_y = 1086, 1448
    scene.render.engine = 'CYCLES'
    log('renders done', vids)
    # 3. motion checks on the evaluated rig
    checks = FD.motion_checks(actions)
    (HERE / 'AttackMotionChecks.json').write_text(json.dumps(
        {'note': 'Per-frame checks on the Blender-evaluated rig (the exported animation). Frames are Blender '
                 'frames at 30 fps starting at 1.', 'sheet_poses': atk, 'videos': vids, **checks}, indent=1))
    log('checks passed', checks['passed'], checks['failures'][:12])
    # 4. exports with the 1024 delivery maps embedded
    swap_images(objs, tex_info, 'delivery')
    FD.export_all()
    swap_images(objs, tex_info, 'master')
    # 5. manifest + polygon report
    write_reports(rig, sk, objs, tex_info, actions, weight_stats, checks)
    # 6. the .blend: textures packed, review objects in REVIEW_ONLY
    for img in bpy.data.images:
        if img.source == 'FILE' and not img.packed_file and img.filepath:
            try:
                img.pack()
            except RuntimeError:
                pass
    rig.animation_data.action = bpy.data.actions['ReferencePose']
    scene.frame_start, scene.frame_end = 1, 2
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE / f'{NAME}.blend'), compress=True)
    log('FULL STAGE DONE')


def write_reports(rig, sk, objs, tex_info, actions, weight_stats, checks):
    import fc_deliver as FD
    dg = bpy.context.evaluated_depsgraph_get()
    rig.animation_data.action = bpy.data.actions['ReferencePose']
    bpy.context.scene.frame_set(1)
    dg.update()
    posed = {}
    for sec, ob in objs.items():
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        posed[sec] = np.array([ob.matrix_world @ v.co for v in me.vertices])
        ev.to_mesh_clear()
    allp = np.concatenate(list(posed.values()))
    body_ref = np.concatenate([posed[s] for s in ('Body', 'Head', 'Fur', 'Gear') if s in posed])
    rest = np.concatenate([B.mesh_arrays(ob)[0] for ob in objs.values()])
    sections = {}
    for sec, ob in objs.items():
        me = ob.data
        sections[ob.name] = {'triangles': B.tri_count(ob), 'vertices': len(me.vertices), 'faces': len(me.polygons),
                             'texture_master': tex_info.get(sec, {}).get('master'),
                             'texture_delivery': tex_info.get(sec, {}).get('delivery')}
    Hc = sk.ref['RightHand']
    Cc = sk.ref['Club']
    grip_in_hand = np.linalg.inv(Hc) @ Cc
    Fi = FP.club_impact_point()
    fi_club = np.linalg.inv(Cc) @ np.append(Fi, 1.0)
    h = D.club_axis()[1]
    n_club = np.linalg.inv(Cc)[:3, :3] @ FP.strike_normal()          # flat striking face
    gl = D.grip_local()

    def to_rbx(v):
        return [round(float(-v[0]), 4), round(float(v[2]), 4), round(float(v[1]), 4)]
    attacks = {}
    for k in ('GroundSlam', 'Stomp'):
        if k in actions:
            attacks[k] = dict(actions[k])
    if 'GroundSlam' in attacks:
        attacks['GroundSlam']['ClubImpact_root_at_impact_blender'] = attacks['GroundSlam']['club_impact_point_root']
        attacks['GroundSlam']['ClubImpact_root_at_impact_roblox_xyz'] = to_rbx(attacks['GroundSlam']['club_impact_point_root'])
    if 'Stomp' in attacks:
        attacks['Stomp']['StompImpact_root_roblox_xyz'] = to_rbx(attacks['Stomp']['StompImpact_root'])
        attacks['Stomp']['StompSpikeDirection_roblox_xyz'] = to_rbx(attacks['Stomp']['StompSpikeDirection_root'])
    manifest = {
        'asset': NAME,
        'reference': {'file': 'source/FrostCyclops_reference.webp',
                      'sha256': 'DAAFFA2AE07CF831D8F83242B9A5B72126C30F1AEFA1D2395112BC2B3F6F63A5', 'size': [1086, 1448]},
        'units': "1 Blender unit = 1 Roblox stud; Z up, the character faces -Y, +X is the character's left",
        'dimensions_studs': {
            'height_reference_pose': round(float(body_ref[:, 2].max()), 3),
            'width_reference_pose_incl_club': round(float(np.ptp(allp[:, 0])), 3),
            'depth_reference_pose_incl_club': round(float(np.ptp(allp[:, 1])), 3),
            'height_rest_pose': round(float(rest[:, 2].max()), 3),
            'eye_centre_z': round(float(D.J['Eye'][2]), 3),
            'shoulder_joint_span': round(float(np.linalg.norm(D.J['RightUpperArm'] - D.J['LeftUpperArm'])), 3),
            'haft_radius_grip_stone': list(D.HAFT_R),
            'stone_half_extents': FP.STONE_R.tolist(),
        },
        'bones': [{'name': b, 'parent': sk.parent[b], 'length': round(sk.length[b], 4),
                   'head_rest': [round(float(v), 4) for v in sk.rest[b][:3, 3]]} for b in sk.order],
        'bone_count_deform': len(sk.order),
        'non_deform_helpers_not_exported': [b.name for b in rig.data.bones if not b.use_deform],
        'sections': sections,
        'triangles_total': sum(v['triangles'] for v in sections.values()),
        'club': {
            'grip_point': 'Club bone head = centre of the finger tunnel (haft axis inside the right fist)',
            'club_bone_in_RightHand_space_4x4': [[round(float(x), 5) for x in r] for r in grip_in_hand],
            'grip_centre_hand_local_studs': [round(float(v), 4) for v in gl[0]],
            'haft_direction_hand_local': [round(float(v), 4) for v in gl[1]],
            'club_impact_in_Club_bone_space_blender': [round(float(v), 4) for v in fi_club[:3]],
            'club_impact_normal_in_Club_bone_space_blender': [round(float(v), 4) for v in n_club],
            'note': 'Blender bone space: +Y along the bone (head->tail), X/Z per roll. The ClubImpact helper bone '
                    'in FrostCyclops.blend sits at this point (not exported; deform-only exports).',
            'grip_report': gl[3],
        },
        'attacks': attacks,
        'actions': {a.name: {'frame_range': [int(a.frame_range[0]), int(a.frame_range[1])], 'fps': 30,
                             'markers': {m.name: m.frame for m in a.pose_markers}}
                    for a in bpy.data.actions if a.name in ('ReferencePose', 'RigTest_ROM', 'GroundSlam', 'Stomp')},
        'motion_checks_summary': {k: checks[k]['summary'] for k in ('GroundSlam', 'Stomp')},
        'motion_checks_passed': checks['passed'],
        'textures': {},
        'exports': {},
        'camera_solution': json.loads((HERE / 'source' / 'camera_solution.json').read_text()),
    }
    for p in sorted((HERE / 'textures').glob('*.png')):
        manifest['textures'][p.name] = {'sha256': FD.sha256(p), 'bytes': p.stat().st_size}
    for p in sorted((HERE / 'exports').rglob('*.*')):
        manifest['exports'][p.relative_to(HERE).as_posix()] = {'sha256': FD.sha256(p), 'bytes': p.stat().st_size}
    (HERE / 'manifest.json').write_text(json.dumps(manifest, indent=1, default=str))
    poly = {'sections': sections, 'total_triangles': manifest['triangles_total'],
            'limit_per_mesh': 20000, 'all_under_limit': all(v['triangles'] < 20000 for v in sections.values()),
            'weights': weight_stats}
    (HERE / 'polygon-report.json').write_text(json.dumps(poly, indent=1))


# ====================================================================== main
def main():
    B.clear_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    sections = build_geometry()
    sk = PO.Skeleton()
    log('skeleton', len(sk.order), 'bones; REF length error', sk.ref_length_err)
    rig = build_rig(B.collection(NAME), sk)
    stats = skin_weights(sections, rig)
    bind(sections, rig)
    log('weights', stats)
    objs = join_sections(sections)
    tex_info = {}
    if os.environ.get('FC_TEXTURES', '1') == '1':
        rig.data.pose_position = 'REST'
        tex_info = texture_sections(objs)
        rig.data.pose_position = 'POSE'
    # reference pose
    rig.animation_data_create()
    ACTIONS = build_actions(rig, sk)
    rig.animation_data.action = bpy.data.actions['ReferencePose']
    bpy.context.scene.frame_set(1)
    setup_review()
    if STAGE == 'probe':
        render(WORK / 'probe_render.png', samples=int(os.environ.get('FC_SAMPLES', '16')),
               mask_path=WORK / 'probe_mask.png')
        if os.environ.get('FC_CLOSEUPS'):
            render_closeups(WORK / 'close', which=os.environ['FC_CLOSEUPS'].split(','))
        bpy.ops.wm.save_as_mainfile(filepath=str(WORK / 'stage_probe.blend'))
        log('probe done')
        return
    full_stage(rig, sk, objs, tex_info, ACTIONS, stats)


if __name__ == '__main__':
    main()
