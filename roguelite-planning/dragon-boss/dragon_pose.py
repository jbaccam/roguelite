"""Pose authoring for the Dragon rig (pure numpy): ReferencePose, the attack
check poses and the RigTest_ROM keyframes.

All poses are dicts {bone: quaternion (w, x, y, z)} of bone-local rotations
(Blender's rotation_quaternion) plus an optional Root translation. They are
built with FK so constraints such as "keep the chest where the camera solve
put it" or "plant this foot on its ground target" are solved here, not left
to Blender IK.
"""
import math

import numpy as np

import dragon_camera as C
import dragon_rig as RG
from dragon_mesh import rot_axis
from dragon_rig import compose, mat_to_quat, quat_to_mat, world_axis_rot

# --------------------------------------------------------------- parameters
REF = {
    'bend': 30.0,              # total left bend of the rear body (deg), spread over Hips..Spine_3
    'bend_pitch': 0.0,
    'tail_yaw': [-2, -4, -6, -8, -9, -9, -9, -8, -7, -6],   # per tail bone (neg = curl left)
    'tail_pitch': [0, 0, 0, 1, 2, 4, 6, 8, 10, 12],               # + = raise (about the bone's X)
    # head fitted to 9 head landmarks (_work/head_rigid2.py, rms 19 px): the neck
    # is straight, the head turns 12.5 deg toward the camera and dips 17 deg nose-down
    'neck_yaw': [0.0, 0.0, 0.0],
    'neck_pitch': [0.0, 0.0, 0.0],
    'head_yaw': 12.5,
    'head_pitch': 17.2,
    'head_roll': 0.0,
    'jaw_open': 0.0,
    'front_splay': {'L': 21.6, 'R': -10.6},     # extra outward yaw of the front feet vs rest 12 deg (camera solve: FL 33.6, FR 1.4)
    'tail_tip_pitch': -25.0,
    'tail_tip_roll': 0.0,
    'hind_target': {'L': (6.36, 5.16), 'R': (-6.3, 5.05)},   # claw-row centres on the ground (camera solve)
    'hind_splay': {'L': 5.9, 'R': 9.4},       # camera solve: HL 13.9 out, HR 1.4 in (rest 8 out)
    'front_target': {'L': (5.67, -5.26), 'R': (-5.67, -5.26)},   # claw-row centres (camera solve)
    'chest_yaw': 0.0,
    'shoulder_rot': {'L': (0.0, 0.0), 'R': (-15.0, -15.0)},  # the far (right) shoulder sits in/back   # clavicle (about world Y, about world Z), deg
}

# Wing joint pixels measured on 1.8x gridded crops (bone centre lines; the
# finger tips are the claw bases). The reference raises the wings
# asymmetrically, so each wing aims its own bones at its own pixels; when a
# pixel ray meets the bone's reach sphere twice, the solution closer to the
# bone's current direction is used (least change from rest).
WING_PIX = {
    'L': {'w_elbow': (942, 282), 'w_wrist': (935, 82), 'w_thumb': (835, 27), 'w_f1k': (1236, 118),
          'w_f1t': (1447, 376), 'w_f2k': (1135, 286), 'w_f2t': (1240, 462)},
    'R': {'w_elbow': (378, 445), 'w_wrist': (348, 92), 'w_thumb': (411, 37), 'w_f1k': (172, 140),
          'w_f1t': (72, 392), 'w_f2k': (257, 262), 'w_f2t': (226, 428)},
}
WING_BONES = [('Wing_{s}_1', 'w_elbow'), ('Wing_{s}_2', 'w_wrist'), ('Wing_{s}_Thumb', 'w_thumb'),
              ('Wing_{s}_Finger1_1', 'w_f1k'), ('Wing_{s}_Finger1_2', 'w_f1t'),
              ('Wing_{s}_Finger2_1', 'w_f2k'), ('Wing_{s}_Finger2_2', 'w_f2t')]


def yaw(sk, bone, deg):
    return world_axis_rot(sk, bone, (0, 0, 1), deg)


def local_axis_rot(axis_local, deg):
    return mat_to_quat(rot_axis(axis_local, deg))


def minimal_arc(a, b):
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    v = np.cross(a, b)
    c = float(a @ b)
    if np.linalg.norm(v) < 1e-9:
        return np.eye(3) if c > 0 else rot_axis(np.cross(a, [1, 0, 0]) if abs(a[0]) < 0.9 else np.cross(a, [0, 1, 0]), 180)
    ang = math.degrees(math.atan2(np.linalg.norm(v), c))
    return rot_axis(v, ang)


def aim(sk, pose, bone, target):
    """Rotate `bone` (bone-local, keeping its current local rotation's roll)
    so its tail points at world `target`."""
    W = sk.fk(pose)
    p = sk.parent[bone]
    Mp = W[p] @ np.linalg.inv(sk.rest[p]) @ sk.rest[bone] if p else sk.rest[bone]
    head = Mp[:3, 3]
    cur = pose.get(bone, np.array([1.0, 0, 0, 0]))
    Rcur = Mp[:3, :3] @ quat_to_mat(cur)
    ydir = Rcur[:, 1]
    Rw = minimal_arc(ydir, np.asarray(target) - head)
    Rnew = Rw @ Rcur
    local = Mp[:3, :3].T @ Rnew
    pose[bone] = mat_to_quat(local)
    return pose


def ray_sphere(uv, center, radius, prefer):
    """prefer: 'near', 'far' or a direction vector (pick the hit closest to it)."""
    o = C.P
    d = C.ray(uv)
    oc = o - center
    b = oc @ d
    c = oc @ oc - radius * radius
    disc = b * b - c
    if disc < 0:
        # no intersection: point at bone length toward the ray's closest point
        q = o + d * (-b)
        v = q - center
        return center + v / np.linalg.norm(v) * radius
    s = math.sqrt(disc)
    t1, t2 = -b - s, -b + s
    if isinstance(prefer, str):
        t = t1 if prefer == 'near' else t2
    else:
        p1, p2 = o + d * t1, o + d * t2
        pr = np.asarray(prefer, float)
        a1 = (p1 - center) @ pr
        a2 = (p2 - center) @ pr
        t = t1 if a1 >= a2 else t2
    return o + d * t


def keep_bone_fixed(sk, pose, bone, target=None):
    """Adjust the Root so `bone` ends at `target` (default: its REST world transform)."""
    W = sk.fk(pose)
    tgt = sk.rest[bone] if target is None else target
    Cm = tgt @ np.linalg.inv(W[bone])
    root_rest = sk.rest['Root']
    cur = np.eye(4)
    v = pose.get('Root')
    if isinstance(v, dict):
        cur[:3, :3] = quat_to_mat(v['q'])
        cur[:3, 3] = v['t']
    elif v is not None:
        cur[:3, :3] = quat_to_mat(v)
    basis = np.linalg.inv(root_rest) @ Cm @ root_rest @ cur
    pose['Root'] = {'q': mat_to_quat(basis[:3, :3]), 't': basis[:3, 3].copy()}
    return pose


def two_bone_ik(sk, pose, b1, b2, target, pole_dir):
    """Place the tail of b2 at `target` by rotating b1 and b2 (lengths fixed)."""
    W = sk.fk(pose)
    root = W[b1][:3, 3]
    L1, L2 = sk.length(b1), sk.length(b2)
    d = np.asarray(target) - root
    D = np.clip(np.linalg.norm(d), 1e-4, L1 + L2 - 1e-4)
    dn = d / np.linalg.norm(d)
    pole = np.asarray(pole_dir, float)
    pole = pole - dn * (pole @ dn)
    pole /= np.linalg.norm(pole)
    a = (L1 * L1 + D * D - L2 * L2) / (2 * L1 * D)
    ang = math.acos(np.clip(a, -1, 1))
    knee = root + dn * L1 * math.cos(ang) + pole * L1 * math.sin(ang)
    aim(sk, pose, b1, knee)
    aim(sk, pose, b2, root + dn * D)
    return pose


def set_world_rot(sk, pose, bone, Rworld):
    W = sk.fk(pose)
    p = sk.parent[bone]
    Mp = W[p] @ np.linalg.inv(sk.rest[p]) @ sk.rest[bone]
    pose[bone] = mat_to_quat(Mp[:3, :3].T @ Rworld)
    return pose


def plant_hind(sk, pose, s, target_xy, splay):
    """Plant the hind foot: claw-row centre at target_xy, the foot level, yawed by splay."""
    rest_row = np.array(RG.TOE_ROWS['hind'][0], float)
    if s == 'R':
        rest_row = RG.mirror(rest_row)
    ball = sk.head[f'Foot_{s}']
    hock = sk.head[f'Ankle_{s}']
    Ry = rot_axis((0, 0, 1), splay)
    tgt = np.array([target_xy[0], target_xy[1], rest_row[2]])
    # rigid foot offset (rest): claw row -> ball -> hock, rotated by the splay
    ball_t = tgt + Ry @ (ball - rest_row)
    hock_t = tgt + Ry @ (hock - rest_row)
    knee_rest = sk.head[f'Shin_{s}']
    pole = knee_rest - 0.5 * (sk.head[f'Thigh_{s}'] + hock)
    two_bone_ik(sk, pose, f'Thigh_{s}', f'Shin_{s}', hock_t, Ry @ pole)
    aim(sk, pose, f'Ankle_{s}', ball_t)
    set_world_rot(sk, pose, f'Foot_{s}', Ry @ sk.rest[f'Foot_{s}'][:3, :3])
    return pose


def plant_front(sk, pose, s, target_xy, splay):
    """Plant the front foot: claw-row centre at target_xy, the hand level and
    yawed by `splay` (deg about Z), elbow bending backward."""
    rest_row = np.array(RG.TOE_ROWS['front'][0], float)
    if s == 'R':
        rest_row = RG.mirror(rest_row)
    wrist = sk.head[f'Hand_{s}']
    Ry = rot_axis((0, 0, 1), splay)
    tgt = np.array([target_xy[0], target_xy[1], rest_row[2]])
    wrist_t = tgt + Ry @ (wrist - rest_row)
    elbow_rest = sk.head[f'Forearm_{s}']
    pole = elbow_rest - 0.5 * (sk.head[f'UpperArm_{s}'] + wrist) + np.array([0, 0.4, 0])
    two_bone_ik(sk, pose, f'UpperArm_{s}', f'Forearm_{s}', wrist_t, pole)
    set_world_rot(sk, pose, f'Hand_{s}', Ry @ sk.rest[f'Hand_{s}'][:3, :3])
    return pose


def _qangle(q):
    return 2 * math.degrees(math.acos(min(1.0, abs(float(q[0])) / float(np.linalg.norm(q)))))


def solve_wing(sk, pose, s):
    import itertools
    best = None
    for combo in itertools.product(('near', 'far'), repeat=len(WING_BONES)):
        trial = {k: (dict(v) if isinstance(v, dict) else np.array(v)) for k, v in pose.items()}
        cost = 0.0
        for (bone_t, key), pick in zip(WING_BONES, combo):
            b = bone_t.format(s=s)
            W = sk.fk(trial)
            head = W[b][:3, 3]
            tgt = ray_sphere(WING_PIX[s][key], head, sk.length(b), pick)
            aim(sk, trial, b, tgt)
            cost += _qangle(trial[b])
            if best is not None and cost >= best[0]:
                break
        else:
            if best is None or cost < best[0]:
                best = (cost, trial, combo)
    return best[1]


def reference_pose(sk, P=None):
    P = dict(REF, **(P or {}))
    pose = {}
    # rear body bends left; chest held at its camera-solved rest placement
    B = P['bend']
    pose['Hips'] = yaw(sk, 'Hips', -B)
    for b in ('Spine_1', 'Spine_2', 'Spine_3'):
        pose[b] = yaw(sk, b, B / 3.0)
    # chest held at its rest placement, turned by chest_yaw about its own head
    cp = sk.rest['Chest'][:3, 3]
    T = np.eye(4)
    T[:3, :3] = rot_axis((0, 0, 1), P['chest_yaw'])
    T[:3, 3] = cp - T[:3, :3] @ cp
    keep_bone_fixed(sk, pose, 'Chest', T @ sk.rest['Chest'])
    for i, (y_, p_) in enumerate(zip(P['tail_yaw'], P['tail_pitch'])):
        b = f'Tail_{i + 1}'
        pose[b] = compose(yaw(sk, b, y_), local_axis_rot((1, 0, 0), p_))
    pose['TailTip'] = compose(local_axis_rot((1, 0, 0), P['tail_tip_pitch']), local_axis_rot((0, 1, 0), P['tail_tip_roll']))
    for i, b in enumerate(('Neck_1', 'Neck_2', 'Neck_3')):
        pose[b] = compose(yaw(sk, b, P['neck_yaw'][i]), world_axis_rot(sk, b, (1, 0, 0), P['neck_pitch'][i]))
    pose['Head'] = compose(yaw(sk, 'Head', P['head_yaw']), world_axis_rot(sk, 'Head', (1, 0, 0), P['head_pitch']),
                           world_axis_rot(sk, 'Head', (0, 1, 0), P['head_roll']))
    if P['jaw_open']:
        pose['Jaw'] = local_axis_rot((1, 0, 0), -P['jaw_open'])
    for s in ('L', 'R'):
        sgn = 1 if s == 'L' else -1
        ry, rz = P['shoulder_rot'][s]
        pose[f'Shoulder_{s}'] = compose(wx(sk, f'Shoulder_{s}', (0, 1, 0), ry), wx(sk, f'Shoulder_{s}', (0, 0, 1), rz))
        plant_front(sk, pose, s, P['front_target'][s], sgn * P['front_splay'][s])
        plant_hind(sk, pose, s, P['hind_target'][s], P['hind_splay'][s])
    # wings: every bone aims at its measured joint pixel. Each pixel ray meets
    # the bone's reach sphere twice; all 2^7 near/far combinations are tried and
    # the one with the least total rotation from rest is kept.
    for s in ('L', 'R'):
        pose = solve_wing(sk, pose, s)
    return pose


# =============================================================== animation poses
def wx(sk, b, axis, deg):
    """Bone-local quaternion for `deg` about a world axis (at rest orientation)."""
    return world_axis_rot(sk, b, axis, deg)


def wing_pose(sk, s, spread=0.0, fold=0.0, flap=0.0, forward=0.0):
    """Wing helper. spread>0 opens toward the reference spread, fold>0 folds the
    wing along the flank, flap raises (+) / lowers (-) the whole wing."""
    sgn = 1 if s == 'L' else -1
    q = {}
    # humerus: flap about the body's long axis (Y), sweep forward/back about Z
    q[f'Wing_{s}_1'] = compose(wx(sk, f'Wing_{s}_1', (0, 1, 0), -sgn * (flap + 34 * fold - 10 * spread)),
                               wx(sk, f'Wing_{s}_1', (0, 0, 1), sgn * (forward + 25 * fold)))
    # forearm folds down along the humerus
    q[f'Wing_{s}_2'] = wx(sk, f'Wing_{s}_2', (0, 1, 0), -sgn * (-55 * fold + 8 * spread))
    # fingers fold back toward the forearm (about each finger's own rest X = wing-plane normal-ish)
    for b, amt in ((f'Wing_{s}_Finger1_1', 40), (f'Wing_{s}_Finger2_1', 32), (f'Wing_{s}_Finger1_2', 25),
                   (f'Wing_{s}_Finger2_2', 22)):
        q[b] = local_axis_rot((0, 0, 1), sgn * (amt * fold - 10 * spread))
    q[f'Wing_{s}_Thumb'] = local_axis_rot((1, 0, 0), 20 * fold)
    return q


def leg_lift(sk, side, front, amount):
    """Walk-cycle-like lift: swing forward, bend the knee/elbow, curl the foot."""
    q = {}
    if front:
        q[f'UpperArm_{side}'] = wx(sk, f'UpperArm_{side}', (1, 0, 0), -45 * amount)
        q[f'Forearm_{side}'] = wx(sk, f'Forearm_{side}', (1, 0, 0), 85 * amount)
        q[f'Hand_{side}'] = wx(sk, f'Hand_{side}', (1, 0, 0), -45 * amount)
    else:
        q[f'Thigh_{side}'] = wx(sk, f'Thigh_{side}', (1, 0, 0), -40 * amount)
        q[f'Shin_{side}'] = wx(sk, f'Shin_{side}', (1, 0, 0), 60 * amount)
        q[f'Ankle_{side}'] = wx(sk, f'Ankle_{side}', (1, 0, 0), -35 * amount)
        q[f'Foot_{side}'] = wx(sk, f'Foot_{side}', (1, 0, 0), 25 * amount)
    return q


def toe_curl(sk, amount):
    q = {}
    for hand in ('Hand', 'Foot'):
        for s in ('L', 'R'):
            for k in range(1, 5):
                q[f'{hand}_{s}_Toe{k}_1'] = local_axis_rot((1, 0, 0), -30 * amount)
                q[f'{hand}_{s}_Toe{k}_2'] = local_axis_rot((1, 0, 0), -35 * amount)
    return q


def blink(sk, amount):
    q = {}
    for s in ('L', 'R'):
        q[f'Eyelid_{s}'] = local_axis_rot((1, 0, 0), -38 * amount)
        q[f'Brow_{s}'] = local_axis_rot((1, 0, 0), -8 * amount)
    return q


def neck_pose(sk, yaw_deg=0.0, pitch_deg=0.0, head_yaw=0.0, head_pitch=0.0, extend=0.0):
    q = {}
    for i, b in enumerate(('Neck_1', 'Neck_2', 'Neck_3')):
        q[b] = compose(wx(sk, b, (0, 0, 1), yaw_deg / 3), wx(sk, b, (1, 0, 0), pitch_deg / 3 + (extend * 10 if i == 0 else -extend * 5)))
    q['Head'] = compose(wx(sk, 'Head', (0, 0, 1), head_yaw), wx(sk, 'Head', (1, 0, 0), head_pitch))
    return q


def tail_pose(sk, yaw_deg=0.0, pitch_deg=0.0):
    q = {}
    for i in range(RG.TAIL_N):
        b = f'Tail_{i + 1}'
        w = (i + 1) / RG.TAIL_N
        q[b] = compose(wx(sk, b, (0, 0, 1), yaw_deg / RG.TAIL_N * (0.6 + 0.8 * w)),
                       local_axis_rot((1, 0, 0), pitch_deg / RG.TAIL_N))
    return q


def merge(*ds):
    out = {}
    for d in ds:
        for k, v in d.items():
            out[k] = compose(out[k], v) if k in out and not isinstance(v, dict) else v
    return out


def rom_keys(sk):
    """RigTest_ROM: (frame, pose) keys driving every bone through a realistic range."""
    K = []
    f = 1

    def key(pose, step=12):
        nonlocal f
        K.append((f, pose))
        f += step
    key({})
    # walk-cycle-like leg lifts, one leg at a time
    for side, front in (('L', True), ('R', True), ('L', False), ('R', False)):
        key(leg_lift(sk, side, front, 1.0))
        key({})
    # neck sweep and head turn
    key(neck_pose(sk, yaw_deg=45, head_yaw=20))
    key(neck_pose(sk, yaw_deg=-45, head_yaw=-20))
    key(neck_pose(sk, pitch_deg=-30, head_pitch=-15))
    key(neck_pose(sk, pitch_deg=25, head_pitch=20))
    key({})
    # fire breath: neck extended, head up, jaw open
    key(merge(neck_pose(sk, pitch_deg=-12, head_pitch=-12, extend=1.0), {'Jaw': local_axis_rot((1, 0, 0), -38)}), 16)
    key({})
    # wings: fold -> spread -> flap
    key(fold_wings(sk), 16)
    key(spread_wings(sk), 16)
    key(flap_wings(sk, 30), 10)
    key(flap_wings(sk, -30), 10)
    key(flap_wings(sk, 30), 10)
    key({})
    # tail sweep side to side and up
    key(tail_pose(sk, yaw_deg=70))
    key(tail_pose(sk, yaw_deg=-70))
    key(tail_pose(sk, pitch_deg=45))
    key({})
    # toes curl, blinks
    key(toe_curl(sk, 1.0))
    key(toe_curl(sk, -0.5))
    key({}, 8)
    key(blink(sk, 1.0), 6)
    key({}, 6)
    key(blink(sk, 1.0), 6)
    key({})
    return K


def mirror_quat(q):
    """Left->right bone-local rotation for this rig's mirrored rest frames
    (R frame = mirror(L frame) with local X flipped): (w, x, -y, -z)."""
    w, x, y, z = q
    return np.array([w, x, -y, -z])


def spread_wings(sk):
    """Symmetric full spread: the reference image's left-wing rotations, mirrored onto the right wing."""
    cached = getattr(sk, '_spread_cache', None)
    if cached is not None:
        return {k: np.array(v) for k, v in cached.items()}
    ref = reference_pose(sk)
    out = {}
    for bone_t, _ in WING_BONES:
        bl = bone_t.format(s='L')
        br = bone_t.format(s='R')
        out[bl] = np.array(ref[bl])
        out[br] = mirror_quat(ref[bl])
    sk._spread_cache = {k: np.array(v) for k, v in out.items()}
    return out


def _unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


FOLD_DIRS = {   # left wing, world directions per bone when folded along the flank
    'Wing_L_1': (0.35, 0.45, 0.82),        # humerus up and back
    'Wing_L_2': (0.12, -0.75, -0.42),      # forearm folds forward and down along it
    'Wing_L_Thumb': (0.15, -0.55, 0.82),
    'Wing_L_Finger1_1': (0.22, 0.88, -0.3),
    'Wing_L_Finger1_2': (0.14, 0.9, -0.42),
    'Wing_L_Finger2_1': (0.3, 0.8, -0.5),
    'Wing_L_Finger2_2': (0.2, 0.78, -0.6),
}


def fold_wings(sk):
    """Wings folded along the flanks: humerus up-back, forearm folded forward,
    fingers laid back along the body. Left solved by aiming, right mirrored."""
    pose = {}
    for b in ('Wing_L_1', 'Wing_L_2', 'Wing_L_Thumb', 'Wing_L_Finger1_1', 'Wing_L_Finger1_2',
              'Wing_L_Finger2_1', 'Wing_L_Finger2_2'):
        W = sk.fk(pose)
        head = W[b][:3, 3]
        aim(sk, pose, b, head + _unit(FOLD_DIRS[b]) * sk.length(b))
    out = {}
    for b, q in pose.items():
        out[b] = np.array(q)
        out[b.replace('_L_', '_R_').replace('Wing_L', 'Wing_R')] = mirror_quat(q)
    return out


def flap_wings(sk, deg):
    """Full spread with the whole wing rotated up (+) or down (-) about the body's long axis."""
    out = spread_wings(sk)
    out['Wing_L_1'] = compose(wx(sk, 'Wing_L_1', (0, 1, 0), -deg), out['Wing_L_1'])
    out['Wing_R_1'] = compose(wx(sk, 'Wing_R_1', (0, 1, 0), deg), out['Wing_R_1'])
    return out


# =============================================================== attack actions
# Three boss attacks (user brief): FireBreath, TailWhip, FrontStomp. Each is a
# function of time sampled every KEY_STEP frames; every sample re-plants the
# feet that are on the ground with IK at their rest ground targets, so planted
# feet do not slide (Blender interpolates quaternions between samples 2 frames
# apart). Joint motion is rotation only (plus the Root drop/lift of the
# stomp), so every joint hinges about its own bone.
FPS = 24
KEY_STEP = 2


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def seg(t, a, b):
    """0 before a, eased 0->1 between a and b, 1 after b."""
    return ease((t - a) / max(b - a, 1e-9))


def slerp(q0, q1, w):
    q0 = np.asarray(q0, float)
    q1 = np.asarray(q1, float)
    d = float(q0 @ q1)
    if d < 0:
        q1 = -q1
        d = -d
    if d > 0.9995:
        q = q0 + (q1 - q0) * w
        return q / np.linalg.norm(q)
    th = math.acos(d)
    return (math.sin((1 - w) * th) * q0 + math.sin(w * th) * q1) / math.sin(th)


def scale_quat(q, w):
    return slerp(np.array([1.0, 0, 0, 0]), q, w)


def wing_blend(sk, w_spread=0.0, flap=0.0):
    """Blend rest -> full spread (w_spread), plus a flap rotation (deg)."""
    out = {}
    sp = flap_wings(sk, flap) if w_spread > 0 or flap else {}
    for b, q in sp.items():
        out[b] = scale_quat(q, w_spread) if w_spread < 1 else q
    return out


def plant_all(sk, pose, which=('FL', 'FR', 'HL', 'HR')):
    rest_front = RG.TOE_ROWS['front'][0]
    rest_hind = RG.TOE_ROWS['hind'][0]
    for key in which:
        s = key[1]
        sgn = 1 if s == 'L' else -1
        if key[0] == 'F':
            plant_front(sk, pose, s, (sgn * rest_front[0], rest_front[1]), 0.0)
        else:
            plant_hind(sk, pose, s, (sgn * rest_hind[0], rest_hind[1]), 0.0)
    return pose


# ---- FireBreath: rear the head back and inhale, strike forward low, jaw wide, hold, recover
FIRE = {'frames': 60, 'inhale': (0.0, 0.26), 'strike': (0.26, 0.4), 'hold_end': 0.8, 'impact_frame': 25}


def fire_pose(sk, t):
    a = seg(t, *FIRE['inhale'])
    b = seg(t, *FIRE['strike'])
    r = seg(t, FIRE['hold_end'], 1.0)
    on = (a - b) * (1 - r)                   # inhale weight
    st = b * (1 - r)                         # strike / hold weight
    sway = math.sin(max(0.0, (t - 0.42) / (FIRE['hold_end'] - 0.42)) * 2 * math.pi) if 0.42 < t < FIRE['hold_end'] else 0.0
    neck_pitch = -26 * on + 20 * st          # - raises (rear back), + lowers (strike low)
    head_pitch = -16 * on - 10 * st          # nose up while inhaling, level when breathing
    jaw = 10 * on + 40 * st
    pose = merge(neck_pose(sk, pitch_deg=neck_pitch, head_pitch=head_pitch, extend=st, head_yaw=9 * sway * st,
                           yaw_deg=4 * sway * st),
                 {'Jaw': local_axis_rot((1, 0, 0), -jaw)})
    # chest breath: a slight wing lift on the inhale
    pose.update(wing_blend(sk, 0.25 * on))
    return pose


# ---- TailWhip: coil and twist (tail to the right), fast wide sweep to the left, recover
WHIP = {'frames': 52, 'coil': (0.0, 0.27), 'whip': (0.27, 0.46), 'impact_frame': 23}


def whip_pose(sk, t):
    c = seg(t, *WHIP['coil'])
    w = seg(t, *WHIP['whip'])
    r = seg(t, 0.52, 1.0)
    tail_yaw = (56 * c - 140 * w) * (1 - r) if t < 0.52 else (56 - 140) * (1 - r)
    hips_yaw = (12 * c - 26 * w) * (1 - r) if t < 0.52 else (12 - 26) * (1 - r)
    lift = 10 * min(c + w, 1.0) * (1 - r)
    pose = {'Hips': wx(sk, 'Hips', (0, 0, 1), hips_yaw)}
    for b in ('Spine_1', 'Spine_2', 'Spine_3'):
        pose[b] = wx(sk, b, (0, 0, 1), -hips_yaw / 3.0)
    keep_bone_fixed(sk, pose, 'Chest')
    pose = merge(pose, tail_pose(sk, yaw_deg=tail_yaw, pitch_deg=lift),
                 neck_pose(sk, yaw_deg=-18 * c * (1 - r) + 14 * w * (1 - r), head_yaw=-8 * c * (1 - r)))
    plant_all(sk, pose)
    return pose


# ---- FrontStomp: rear up on the hind legs (front feet leave the ground, wings
# flare), slam both front feet down together sole-flat, body drops, recover
STOMP = {'frames': 48, 'rear': (0.0, 0.33), 'hang_end': 0.44, 'slam_end': 26.0 / 47.0, 'impact_frame': 27}
REAR_DEG = 26.0


def stomp_body(sk, t):
    """Root/hips/tail/head/wings for time t (no front-leg handling)."""
    up = seg(t, *STOMP['rear'])
    sl = seg(t, STOMP['hang_end'], STOMP['slam_end'])
    rec = seg(t, STOMP['slam_end'], 1.0)
    rear = up * (1 - sl)
    drop = sl * (1 - rec)
    hips_pitch = -REAR_DEG * rear + 4 * drop
    pose = {'Root': {'q': np.array([1.0, 0, 0, 0]), 't': np.array([0.0, 0.0, 0.3 * rear - 0.4 * drop])}}
    pose['Hips'] = wx(sk, 'Hips', (1, 0, 0), hips_pitch)
    # the tail keeps its ground clearance: counter-rotate its base
    pose['Tail_1'] = wx(sk, 'Tail_1', (1, 0, 0), -hips_pitch * 0.9)
    pose['Tail_2'] = local_axis_rot((1, 0, 0), 6 * rear)
    pose = merge(pose, neck_pose(sk, pitch_deg=12 * rear - 6 * drop, head_pitch=4 * rear + 8 * drop),
                 {'Jaw': local_axis_rot((1, 0, 0), -(22 * rear + 10 * drop))})
    pose.update(wing_blend(sk, max(rear, 0.6 * drop), flap=22 * rear - 12 * drop))
    return pose


def front_air(sk, pose, w):
    """Front legs lifted and folded (paws up), weight w."""
    for s in ('L', 'R'):
        pose[f'UpperArm_{s}'] = scale_quat(wx(sk, f'UpperArm_{s}', (1, 0, 0), -38), w)
        pose[f'Forearm_{s}'] = scale_quat(wx(sk, f'Forearm_{s}', (1, 0, 0), 78), w)
        pose[f'Hand_{s}'] = scale_quat(wx(sk, f'Hand_{s}', (1, 0, 0), 30), w)
    return pose


def stomp_pose(sk, t):
    pose = stomp_body(sk, t)
    plant_all(sk, pose, ('HL', 'HR'))
    lift_on = seg(t, 0.04, STOMP['rear'][1])
    if t < STOMP['hang_end']:
        front_air(sk, pose, lift_on)
    elif t < STOMP['slam_end']:
        # slam: blend from the folded air pose to the planted, sole-flat IK pose
        w = (t - STOMP['hang_end']) / (STOMP['slam_end'] - STOMP['hang_end'])
        w = w * w                                  # accelerate into the ground
        air = front_air(sk, dict(pose), 1.0)
        planted = plant_all(sk, dict(pose), ('FL', 'FR'))
        for s in ('L', 'R'):
            for b in (f'UpperArm_{s}', f'Forearm_{s}', f'Hand_{s}'):
                pose[b] = slerp(air[b], planted[b], w)
    else:
        plant_all(sk, pose, ('FL', 'FR'))
    return pose


ATTACKS = {
    'FireBreath': (FIRE, fire_pose),
    'TailWhip': (WHIP, whip_pose),
    'FrontStomp': (STOMP, stomp_pose),
}


def attack_keys(sk, name):
    spec, fn = ATTACKS[name]
    n = spec['frames']
    frames = list(range(1, n + 1, KEY_STEP))
    if frames[-1] != n:
        frames.append(n)
    if spec['impact_frame'] not in frames:
        frames = sorted(frames + [spec['impact_frame']])
    return [(f, fn(sk, (f - 1) / (n - 1))) for f in frames]


def attack_phase_frames(name):
    spec, _ = ATTACKS[name]
    n = spec['frames']
    windup = {'FireBreath': 16, 'TailWhip': 14, 'FrontStomp': 20}[name]
    return {'windup': windup, 'impact': spec['impact_frame'], 'recovery': int(n * 0.85)}


def fire_origin_design():
    """Fire origin in the mouth (design space, between palate and jaw floor, near the front)."""
    return np.array([0.0, -8.3, 9.06])


def attack_data(sk, name):
    """Gameplay data per attack, computed with the same FK as the rig (world studs,
    Blender axes: Z up, dragon faces -Y)."""
    spec, fn = ATTACKS[name]
    n = spec['frames']
    out = {'frames': [1, n], 'fps': FPS, 'impact_frame': spec['impact_frame'],
           'impact_time_s': round((spec['impact_frame'] - 1) / FPS, 4)}
    if name == 'FireBreath':
        o_world_rest = np.asarray(RG.head_xf(fire_origin_design()))
        o_local = np.linalg.inv(sk.rest['Head']) @ np.array([*o_world_rest, 1])
        out['FireOrigin'] = {'bone': 'Head', 'local': [round(float(v), 4) for v in o_local[:3]],
                             'rest_world': [round(float(v), 4) for v in o_world_rest]}
        hold = []
        f0 = int(round(1 + FIRE['strike'][1] * (n - 1)))
        f1 = int(round(1 + FIRE['hold_end'] * (n - 1)))
        for f in range(f0, f1 + 1, 2):
            t = (f - 1) / (n - 1)
            pose = fn(sk, t)
            W = sk.fk(pose)
            o = (W['Head'] @ o_local)[:3]
            jaw = abs(2 * math.degrees(math.acos(min(1.0, abs(float(pose['Jaw'][0]))))))
            y = W['Head'][:3, 1]
            z = W['Head'][:3, 2]
            a = math.radians(jaw / 2)
            d = y * math.cos(a) - z * math.sin(a)
            d /= np.linalg.norm(d)
            hold.append({'frame': f, 'origin': [round(float(v), 3) for v in o],
                         'direction': [round(float(v), 4) for v in d]})
        out['hold_frames'] = [f0, f1]
        out['breath'] = hold
    elif name == 'TailWhip':
        pivot = sk.rest['Tail_1'][:3, 3]
        tip_local = np.array([0, 2.6, 0, 1])      # spade point, 2.6 studs along the TailTip bone (dragon_design.spade)
        f0 = int(round(1 + WHIP['whip'][0] * (n - 1)))
        f1 = int(round(1 + WHIP['whip'][1] * (n - 1)))
        pts = []
        for f in range(f0, f1 + 1):
            W = sk.fk(fn(sk, (f - 1) / (n - 1)))
            pts.append((f, (W['TailTip'] @ tip_local)[:3]))
        ang = [math.degrees(math.atan2(p[0] - pivot[0], p[1] - pivot[1])) for _, p in pts]
        rad = [float(np.hypot(p[0] - pivot[0], p[1] - pivot[1])) for _, p in pts]
        out['spade_arc'] = {
            'pivot': [round(float(v), 3) for v in pivot],
            'angle_convention': 'degrees about +Z from +Y (straight back), positive toward +X (dragon left)',
            'start_angle_deg': round(ang[0], 1), 'end_angle_deg': round(ang[-1], 1),
            'radius_mean': round(float(np.mean(rad)), 3), 'radius_min': round(float(min(rad)), 3),
            'radius_max': round(float(max(rad)), 3),
            'height_range': [round(float(min(p[2] for _, p in pts)), 3), round(float(max(p[2] for _, p in pts)), 3)],
            'whip_frames': [f0, f1],
            'samples': [{'frame': f, 'tip': [round(float(v), 3) for v in p]} for f, p in pts[::2]],
        }
    elif name == 'FrontStomp':
        W = sk.fk(fn(sk, (spec['impact_frame'] - 1) / (n - 1)))
        pts = {}
        for s in ('L', 'R'):
            toes = [(W[f'Hand_{s}_Toe{k}_2'] @ np.array([0, 0, 0, 1]))[:3] for k in range(1, 5)]
            palm = W[f'Hand_{s}'] @ np.array([0, sk.length(f'Hand_{s}'), 0, 1])
            c = np.mean(toes, axis=0)
            pts[f'Front_{s}'] = {'palm': [round(float(v), 3) for v in palm[:3]],
                                 'toe_centre': [round(float(v), 3) for v in c],
                                 'ground_point': [round(float(c[0]), 3), round(float(c[1]), 3), 0.0]}
        out['impact_points'] = pts
    return out
