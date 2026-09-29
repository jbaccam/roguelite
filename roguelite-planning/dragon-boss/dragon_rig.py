"""Dragon skeleton, forward kinematics and pose authoring (pure numpy).

Blender world, Z up, the dragon faces -Y, +X is the dragon's LEFT.
Units are Roblox studs (1 Blender unit = 1 stud), authored at final size.

Bones follow Blender's convention: local Y runs head -> tail, local Z is the
roll axis (set from a z_hint, mirrored for L/R pairs so rolls are symmetric).
Pose rotations are stored as bone-local quaternions exactly like Blender's
pose_bone.rotation_quaternion, so an action authored here is keyed 1:1.
"""
import math

import numpy as np

from dragon_mesh import frame_from, rot_axis

SIDES = ('L', 'R')


def mirror(p):
    return np.array([-p[0], p[1], p[2]], float)


# ---------------------------------------------------------------------------
# Rest skeleton. Joint positions for the dragon's LEFT side; the right side is
# mirrored. Values were set from the camera solve (front legs, claw rows) and
# refined in the compare loop (see README pass log).
J = {
    # spine core line (centre of the torso cross-section)
    'root': (0.0, 0.0, 0.0),
    'hips': (0.0, 5.3, 6.4),
    'spine1': (0.0, 3.3, 7.1),
    'spine2': (0.0, 1.3, 7.75),
    'spine3': (0.0, -0.7, 8.2),
    'chest': (0.0, -2.5, 8.45),
    'neck1': (0.0, -3.5, 8.6),
    'neck2': (0.0, -4.5, 8.9),
    'neck3': (0.0, -5.55, 9.2),
    'head': (0.0, -6.15, 10.0),          # head joints are authored in head-design space, see HEAD_XF
    'snout': (0.0, -8.8, 9.45),
    'jaw': (0.0, -5.35, 8.95),
    'chin': (0.0, -8.75, 8.45),
    'brow': (0.3, -7.55, 10.25),
    'brow_t': (0.95, -6.6, 10.55),
    'eye': (0.76, -7.0, 10.16),
    # front leg (left)
    'clav': (1.6, -3.1, 8.3),
    'shoulder': (4.05, -3.9, 6.45),
    'elbow': (4.75, -3.75, 4.0),
    'wrist': (5.05, -3.85, 1.65),
    'palm': (5.2, -4.05, 0.7),
    # hind leg (left)
    'hip': (3.15, 5.2, 5.9),
    'knee': (4.25, 3.95, 3.55),
    'hock': (5.05, 5.95, 1.7),
    'ball': (5.5, 5.25, 0.7),
}
# Wing (left side; mirrored for the right). WING_SPREAD holds the left wing
# of the reference image expressed in the rest frame (solved once by aiming
# every wing bone at its measured joint pixel, see dragon_pose.WING_PIX). The
# rest pose relaxes it: the arm lowered about the root and the fingers folded
# toward the forearm, so the ReferencePose is a small, clean rotation away and
# the membrane never has to blend two very different transforms (no LBS
# collapse along the free edge).
WING_SPREAD = {
    'w_root': (2.15, 0.8, 9.9), 'w_elbow': (4.774, 1.409, 11.221), 'w_wrist': (3.767, 3.193, 15.892),
    'w_hand': (4.24, 3.33, 15.978), 'w_thumb': (2.74, 1.926, 16.657), 'w_f1k': (8.447, 7.605, 15.813),
    'w_f1t': (12.176, 8.1, 10.028), 'w_f2k': (6.596, 5.555, 12.714), 'w_f2t': (9.166, 4.692, 8.044),
}
WING_REST_LOWER = 12.0      # deg the whole wing is lowered about the root (outward-down)
WING_REST_FOLD = 14.0       # deg the fingers fold back toward the forearm about the wrist


def _wing_rest():
    import numpy as _np
    from dragon_mesh import rot_axis as _rot
    ref = {k: _np.array(v, float) for k, v in WING_SPREAD.items()}
    root = ref['w_root']
    Rl = _rot((0, 1.0, 0), WING_REST_LOWER)          # +Y axis: lowers the wing outward (x+ goes down)
    out = {k: root + Rl @ (v - root) for k, v in ref.items()}
    wrist = out['w_wrist']
    n = _np.cross(out['w_f1k'] - wrist, out['w_f2t'] - wrist)
    n /= _np.linalg.norm(n)
    Rf = _rot(n, WING_REST_FOLD)
    for k in ('w_f1k', 'w_f1t', 'w_f2k', 'w_f2t', 'w_hand'):
        out[k] = wrist + Rf @ (out[k] - wrist)
    return {k: tuple(float(x) for x in v) for k, v in out.items()}


J.update(_wing_rest())
# The head is authored in a design space and placed by one similarity
# similarity transform. A rigid landmark fit (9 head landmarks, _work/head_rigid2.py,
# head centred on the midline) gives scale 0.85, pivot (0, -6.55, 9.45), the head
# turned 12.5 deg toward the camera and 17 deg nose-down, rms 19 px.
HEAD_DESIGN_PIVOT = (0.0, -6.15, 10.0)
HEAD_PIVOT = (0.0, -6.55, 9.45)
HEAD_SCALE = 0.85
HEAD_KEYS = ('head', 'snout', 'jaw', 'chin', 'brow', 'brow_t', 'eye')
J_HEAD_DESIGN = {k: J[k] for k in HEAD_KEYS}


def head_xf(P):
    import numpy as _np
    P = _np.asarray(P, float)
    return _np.asarray(HEAD_PIVOT) + HEAD_SCALE * (P - _np.asarray(HEAD_DESIGN_PIVOT))


for _k in HEAD_KEYS:
    J[_k] = tuple(float(x) for x in head_xf(J[_k]))

TOE_ROWS = {   # claw-row centre (left side), splay about Z (deg, outward), claw spacing, scale
    'front': ((5.5, -5.3, 0.08), 12.0, 0.98, 1.12),
    'hind': ((5.85, 4.3, 0.08), 8.0, 0.95, 1.05),
}
TAIL_N = 10
TAIL_LEN = 15.6


def tail_points():
    """Rest tail core line: straight back from the hips, dropping to ~1.5 up."""
    base = np.array([0.0, 6.7, 6.1])
    pts = [np.array(J['hips'], float), base]
    # arc-length spacing shrinking toward the tip
    seg = np.array([1.9, 1.8, 1.7, 1.6, 1.5, 1.4, 1.35, 1.3, 1.25, 1.2])
    seg *= (TAIL_LEN - 1.4) / seg.sum()
    y = base[1]
    for i, s in enumerate(seg):
        t = (i + 1) / len(seg)
        y += s * 0.97
        z = 2.05 + 4.05 * (1 - t) ** 2.1
        pts.append(np.array([0.0, y, z]))
    return pts[1:]          # tail_1 head ... tail tip end (TAIL_N + 1 points)


TOE_FAN = {'front': 13.0, 'hind': 11.0}      # deg between neighbouring toes (fanned foot)


def toe_layout(kind, side):
    """Per toe (1 = inner .. 4 = outer): (base knuckle, mid knuckle, claw base, claw tip).
    Toes fan out from the palm. Built for the left foot and mirrored, so the rig
    is exactly symmetric."""
    c, splay, sp, sc = TOE_ROWS[kind]
    c = np.array(c, float)
    s = math.radians(splay)
    e = np.array([math.cos(s), math.sin(s), 0.0])       # across the row, toward the outer toe
    palm = np.array(J['palm' if kind == 'front' else 'ball'], float)
    toes = []
    for k in range(4):
        a = s + math.radians((k - 1.5) * TOE_FAN[kind])
        fwd = np.array([math.sin(a), -math.cos(a), 0.0])
        lat = (k - 1.5) * sp * sc
        push = (0.4 if k in (1, 2) else 0.0) * sc
        tip = c + lat * e + push * fwd
        claw_base = tip - fwd * 0.6 * sc + np.array([0, 0, 0.74 * sc])
        mid = claw_base - fwd * 0.55 * sc + np.array([0, 0, 0.06 * sc])
        base = palm + lat * 0.62 * e + fwd * 0.1
        base[2] = 0.78 * sc
        pts = (base, mid, claw_base, tip)
        if side == 'R':
            pts = tuple(mirror(p) for p in pts)
        toes.append(pts)
    return toes


def bone_specs():
    """[(name, parent, head, tail, z_hint, deform)] in rest pose."""
    B = []
    j = {k: np.array(v, float) for k, v in J.items()}
    up = np.array([0, 0, 1.0])
    B.append(('Root', None, j['root'], j['root'] + np.array([0, -1.5, 0]), up, True))
    B.append(('Hips', 'Root', j['hips'], j['spine1'], up, True))
    B.append(('Spine_1', 'Hips', j['spine1'], j['spine2'], up, True))
    B.append(('Spine_2', 'Spine_1', j['spine2'], j['spine3'], up, True))
    B.append(('Spine_3', 'Spine_2', j['spine3'], j['chest'], up, True))
    B.append(('Chest', 'Spine_3', j['chest'], j['neck1'], up, True))
    B.append(('Neck_1', 'Chest', j['neck1'], j['neck2'], up, True))
    B.append(('Neck_2', 'Neck_1', j['neck2'], j['neck3'], up, True))
    B.append(('Neck_3', 'Neck_2', j['neck3'], j['head'], up, True))
    B.append(('Head', 'Neck_3', j['head'], j['snout'], up, True))
    B.append(('Jaw', 'Head', j['jaw'], j['chin'], up, True))
    for s in SIDES:
        m = (lambda p: p) if s == 'L' else mirror
        B.append((f'Brow_{s}', 'Head', m(j['brow']), m(j['brow_t']), up, True))
        eye = m(j['eye'])
        B.append((f'Eyelid_{s}', 'Head', eye, eye + np.array([0, -0.55, 0]), up, True))
    # front legs
    for s in SIDES:
        m = (lambda p: p) if s == 'L' else mirror
        out = np.array([1.0 if s == 'L' else -1.0, 0, 0])
        B.append((f'Shoulder_{s}', 'Chest', m(j['clav']), m(j['shoulder']), up, True))
        B.append((f'UpperArm_{s}', f'Shoulder_{s}', m(j['shoulder']), m(j['elbow']), np.array([0, -1.0, 0]), True))
        B.append((f'Forearm_{s}', f'UpperArm_{s}', m(j['elbow']), m(j['wrist']), np.array([0, -1.0, 0]), True))
        B.append((f'Hand_{s}', f'Forearm_{s}', m(j['wrist']), m(j['palm']), up, True))
        for k, (base, mid, cb, tip) in enumerate(toe_layout('front', s)):
            B.append((f'Hand_{s}_Toe{k + 1}_1', f'Hand_{s}', base, mid, up, True))
            B.append((f'Hand_{s}_Toe{k + 1}_2', f'Hand_{s}_Toe{k + 1}_1', mid, cb, up, True))
        del out
    # hind legs
    for s in SIDES:
        m = (lambda p: p) if s == 'L' else mirror
        B.append((f'Thigh_{s}', 'Hips', m(j['hip']), m(j['knee']), np.array([0, -1.0, 0]), True))
        B.append((f'Shin_{s}', f'Thigh_{s}', m(j['knee']), m(j['hock']), np.array([0, -1.0, 0]), True))
        B.append((f'Ankle_{s}', f'Shin_{s}', m(j['hock']), m(j['ball']), np.array([0, -1.0, 0]), True))
        B.append((f'Foot_{s}', f'Ankle_{s}', m(j['ball']), m(j['ball']) + np.array([0, -0.7, 0.02]), up, True))
        for k, (base, mid, cb, tip) in enumerate(toe_layout('hind', s)):
            B.append((f'Foot_{s}_Toe{k + 1}_1', f'Foot_{s}', base, mid, up, True))
            B.append((f'Foot_{s}_Toe{k + 1}_2', f'Foot_{s}_Toe{k + 1}_1', mid, cb, up, True))
    # wings
    for s in SIDES:
        m = (lambda p: p) if s == 'L' else mirror
        fwd = np.array([0, -1.0, 0])
        B.append((f'Wing_{s}_1', 'Spine_2', m(j['w_root']), m(j['w_elbow']), fwd, True))
        B.append((f'Wing_{s}_2', f'Wing_{s}_1', m(j['w_elbow']), m(j['w_wrist']), fwd, True))
        B.append((f'Wing_{s}_3', f'Wing_{s}_2', m(j['w_wrist']), m(j['w_hand']), fwd, True))
        B.append((f'Wing_{s}_Thumb', f'Wing_{s}_3', m(j['w_wrist']) + (m(j['w_hand']) - m(j['w_wrist'])) * 0.3,
                  m(j['w_thumb']), fwd, True))
        B.append((f'Wing_{s}_Finger1_1', f'Wing_{s}_3', m(j['w_hand']), m(j['w_f1k']), fwd, True))
        B.append((f'Wing_{s}_Finger1_2', f'Wing_{s}_Finger1_1', m(j['w_f1k']), m(j['w_f1t']), fwd, True))
        B.append((f'Wing_{s}_Finger2_1', f'Wing_{s}_3', m(j['w_hand']), m(j['w_f2k']), fwd, True))
        B.append((f'Wing_{s}_Finger2_2', f'Wing_{s}_Finger2_1', m(j['w_f2k']), m(j['w_f2t']), fwd, True))
    # tail
    tp = tail_points()
    parent = 'Hips'
    for i in range(TAIL_N):
        name = f'Tail_{i + 1}'
        B.append((name, parent, tp[i], tp[i + 1], up, True))
        parent = name
    tip0 = tp[TAIL_N]
    B.append(('TailTip', parent, tip0, tip0 + (tp[TAIL_N] - tp[TAIL_N - 1]) * 0.9, up, True))
    return B


def roll_axes(specs):
    """Rest matrices (4x4) with mirrored rolls for R bones (z_hint mirrored)."""
    M = {}
    for name, parent, h, t, zh, _ in specs:
        R = frame_from(np.asarray(t) - np.asarray(h), zh)
        m = np.eye(4)
        m[:3, :3] = R
        m[:3, 3] = h
        M[name] = m
    return M


class Skeleton:
    def __init__(self):
        self.specs = bone_specs()
        self.names = [b[0] for b in self.specs]
        self.parent = {b[0]: b[1] for b in self.specs}
        self.head = {b[0]: np.asarray(b[2], float) for b in self.specs}
        self.tail = {b[0]: np.asarray(b[3], float) for b in self.specs}
        self.zhint = {b[0]: np.asarray(b[4], float) for b in self.specs}
        self.deform = {b[0]: b[5] for b in self.specs}
        self.rest = roll_axes(self.specs)
        self.index = {n: i for i, n in enumerate(self.names)}

    def length(self, n):
        return float(np.linalg.norm(self.tail[n] - self.head[n]))

    def fk(self, pose):
        """pose: {bone: (quat wxyz) or dict(q=..., t=...)} bone-local like Blender.
        Returns posed 4x4 world matrices (same convention as pose_bone.matrix)."""
        out = {}
        for n in self.names:
            p = self.parent[n]
            rest = self.rest[n]
            basis = np.eye(4)
            v = pose.get(n)
            if v is not None:
                if isinstance(v, dict):
                    q = v.get('q', (1, 0, 0, 0))
                    basis[:3, 3] = v.get('t', (0, 0, 0))
                else:
                    q = v
                basis[:3, :3] = quat_to_mat(q)
            if p is None:
                out[n] = rest @ basis
            else:
                out[n] = out[p] @ np.linalg.inv(self.rest[p]) @ rest @ basis
        return out

    def skin_mats(self, pose):
        W = self.fk(pose)
        return {n: W[n] @ np.linalg.inv(self.rest[n]) for n in self.names}


# ------------------------------------------------------------- quaternions
def quat_to_mat(q):
    w, x, y, z = q
    n = math.sqrt(w * w + x * x + y * y + z * z)
    w, x, y, z = w / n, x / n, y / n, z / n
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def mat_to_quat(R):
    t = np.trace(R)
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        return np.array([0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s])
    i = int(np.argmax(np.diag(R)))
    if i == 0:
        s = math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        return np.array([(R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s])
    if i == 1:
        s = math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        return np.array([(R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s])
    s = math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
    return np.array([(R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s])


def qmul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return np.array([w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2])


def world_axis_rot(sk, bone, axis_world, deg):
    """Bone-local quaternion for a rotation of `deg` about a world-space axis
    (interpreted in the bone's REST orientation)."""
    R = sk.rest[bone][:3, :3]
    a = R.T @ (np.asarray(axis_world, float) / np.linalg.norm(axis_world))
    return mat_to_quat(rot_axis(a, deg))


def compose(*qs):
    out = np.array([1.0, 0, 0, 0])
    for q in qs:
        out = qmul(out, q)
    return out


def skin_points(sk, pose, P, W):
    """Linear-blend skin points P (n,3) with weights W: {bone: (n,) array}."""
    S = sk.skin_mats(pose)
    out = np.zeros_like(P)
    Ph = np.concatenate([P, np.ones((len(P), 1))], 1)
    tot = np.zeros(len(P))
    for b, w in W.items():
        if b not in S:
            continue
        m = w > 0
        if not m.any():
            continue
        out[m] += w[m, None] * (Ph[m] @ S[b].T)[:, :3]
        tot[m] += w[m]
    return out / np.maximum(tot, 1e-9)[:, None]
