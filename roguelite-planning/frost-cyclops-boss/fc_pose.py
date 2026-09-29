"""Skeleton, poses and actions for the Frost Cyclops (pure numpy).

Bones are described by armature-space 4x4 matrices (Blender convention: bone
local +Y runs head -> tail; origin at the head). Three sets exist:
  REST  the modelling pose (arms abducted, fingers relaxed)
  REF   the reference pose (image stance, fists closed, club gripped)
  any animated pose: built from REF by FK - rotating a bone about its own head
        carries all its descendants.

Digit bones in REF get their roll by the minimal rotation from their REST frame
(in hand space), so the fingers do not twist when they close.

Actions (frames at 30 fps, Blender frames start at 1):
  ReferencePose  the image stance
  RigTest_ROM    every bone through a realistic range
  GroundSlam, Stomp   generated per frame by fc_motion.py
"""
import math

import numpy as np

import fc_design as D
import fc_parts as FP
from fc_sdf import axis_angle, frame_from

UP = np.array([0, 0, 1.0])


# ================================================================= skeleton
def bone_specs(pose):
    """{bone: (head, tail, z_hint, parent)} in the given pose ('REST'|'REF')."""
    Jr = D.rest_joints() if pose == 'REST' else dict(D.J)
    fwd_t = D.RT @ np.array([0, -1.0, 0])
    S = {}
    S['Root'] = (np.zeros(3), np.array([0, 0, 1.2]), np.array([0, -1.0, 0]), None)
    S['HumanoidRootPart'] = (D.J['HumanoidRootPart'], D.J['HumanoidRootPart'] + np.array([0, 0, 0.9]),
                             np.array([0, -1.0, 0]), 'Root')
    S['LowerTorso'] = (D.J['LowerTorso'], D.J['UpperTorso'], fwd_t, 'HumanoidRootPart')
    S['UpperTorso'] = (D.J['UpperTorso'], D.J['UpperTorso_tail'], fwd_t, 'LowerTorso')
    S['Head'] = (D.J['Head'], D.J['Head_tail'], D.RH @ np.array([0, -1.0, 0]), 'UpperTorso')
    S['Jaw'] = (D.J['Jaw'], D.J['Jaw_tail'], UP, 'Head')
    eye_f = D.RH @ np.array([0, -1.0, 0])
    S['Eye'] = (D.J['Eye'], D.J['Eye'] + eye_f * 0.7, UP, 'Head')
    S['EyelidUpper'] = (D.J['Eye'] + np.array([0, 0, 0.001]), D.J['Eye'] + eye_f * 0.35 + UP * 0.35, eye_f, 'Head')
    S['Brow'] = (D.J['Brow'], D.J['Brow'] + UP * 0.45, eye_f, 'Head')
    S['Belly'] = (D.J['Belly'], D.J['Belly_tail'], UP, 'LowerTorso')
    for side in ('Right', 'Left'):
        s = -1 if side == 'Right' else 1
        M = D.rest_arm_rotation(side) if pose == 'REST' else np.eye(3)
        # elbow hinge: local X of both arm bones = normal of the REF arm plane,
        # so flexion is a pure +X rotation of the forearm
        u = D.J[side + 'LowerArm'] - D.J[side + 'UpperArm']
        f = D.J[side + 'Hand'] - D.J[side + 'LowerArm']
        hinge = M @ D._unit(np.cross(u, f))
        uu, ff = D._unit(M @ u), D._unit(M @ f)
        S[side + 'UpperArm'] = (Jr[side + 'UpperArm'], Jr[side + 'LowerArm'], np.cross(hinge, uu), 'UpperTorso')
        S[side + 'LowerArm'] = (Jr[side + 'LowerArm'], Jr[side + 'Hand'], np.cross(hinge, ff), side + 'UpperArm')
        fj, Rh, W = D.finger_points(side, 'REST' if pose == 'REST' else 'REF')
        knuck = W + Rh @ D._hand_local(side, [0, 1.06, 0])
        S[side + 'Hand'] = (W, knuck, Rh[:, 2], side + 'LowerArm')
        for nm in D.FINGER_NAMES + ['Thumb']:
            for k in range(3):
                b = f'{side}{nm}{k + 1}'
                h0, h1 = fj[b]
                par = side + 'Hand' if k == 0 else f'{side}{nm}{k}'
                y = D._unit(h1 - h0)
                ax = Rh[:, 0] if nm != 'Thumb' else Rh @ (D._hand_local(side, D.THUMB_AXIS) / D.HS_SIDE[side])
                S[b] = (h0, h1, np.cross(ax, y), par)
        fdir = D.FOOT_DIR[side]
        ank = D.J[side + 'Foot']
        ball = np.array([*(ank + fdir * (D.FOOT_LEN - D.TOE_LEN))[:2], 0.35])
        tip = np.array([*(ank + fdir * D.FOOT_LEN)[:2], 0.30])
        S[side + 'UpperLeg'] = (D.J[side + 'UpperLeg'], D.J[side + 'LowerLeg'], np.array([0, -1.0, 0]), 'LowerTorso')
        S[side + 'LowerLeg'] = (D.J[side + 'LowerLeg'], ank, np.array([0, -1.0, 0]), side + 'UpperLeg')
        S[side + 'Foot'] = (ank, ball, UP, side + 'LowerLeg')
        S[side + 'Toes'] = (ball, tip, UP, side + 'Foot')
        mb = D.T(s * 1.55, 0.45, 11.05)
        mt = D.T(s * 3.35, 0.25, 10.55)
        S['Mantle_' + side[0]] = (mb, mt, UP, 'UpperTorso')
    Pb, Nb, Rb = FP.belt_ring(D.body_prims(rest=False))
    n = len(Pb)
    down = np.array([0, 0, -1.0])
    front = Pb[0] + Nb[0] * 0.25 - Rb[:, 2] * FP.BELT_W * 0.45
    back = Pb[n // 2] + Nb[n // 2] * 0.25 - Rb[:, 2] * FP.BELT_W * 0.45
    S['Loincloth_Front_1'] = (front, front + down * 1.2 + Nb[0] * 0.15, Nb[0], 'LowerTorso')
    S['Loincloth_Front_2'] = (front + down * 1.2 + Nb[0] * 0.15, front + down * 2.5 + Nb[0] * 0.2, Nb[0],
                              'Loincloth_Front_1')
    S['Loincloth_Back_1'] = (back, back + down * 1.0 + Nb[n // 2] * 0.1, Nb[n // 2], 'LowerTorso')
    S['Loincloth_Back_2'] = (back + down * 1.0 + Nb[n // 2] * 0.1, back + down * 1.9 + Nb[n // 2] * 0.15,
                             Nb[n // 2], 'Loincloth_Back_1')
    T, h = D.club_axis()
    Rh, W = D.hand_frame('Right', 'REF')
    if pose == 'REST':
        M = D.rest_arm_rotation('Right')
        Sh = D.J['RightUpperArm']
        T = (T - Sh) @ M.T + Sh
        h = M @ h
        Rh = M @ Rh
    S['Club'] = (T, T + h * 1.2, Rh[:, 2], 'RightHand')
    return S


def frame(head, tail, hint):
    y = D._unit(np.asarray(tail) - np.asarray(head))
    z = np.asarray(hint, float)
    z = z - y * (z @ y)
    if np.linalg.norm(z) < 1e-6:
        z = np.cross(y, [1.0, 0, 0])
    z = D._unit(z)
    x = np.cross(y, z)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = x, y, z, head
    return M


class Skeleton:
    def __init__(self):
        self.rest_specs = bone_specs('REST')
        self.ref_specs = bone_specs('REF')
        self.parent = {b: sp[3] for b, sp in self.rest_specs.items()}
        self.children = {b: [c for c, p in self.parent.items() if p == b] for b in self.parent}
        self.order = []

        def walk(b):
            self.order.append(b)
            for c in self.children[b]:
                walk(c)
        walk('Root')
        self.rest = {b: frame(*sp[:3]) for b, sp in self.rest_specs.items()}
        self.length = {b: float(np.linalg.norm(sp[1] - sp[0])) for b, sp in self.rest_specs.items()}
        ref = {b: frame(*sp[:3]) for b, sp in self.ref_specs.items()}
        # digits: minimal rotation from the REST frame, expressed in hand space
        for side in ('Right', 'Left'):
            Hr = self.rest[side + 'Hand']
            Hf = ref[side + 'Hand']
            for nm in D.FINGER_NAMES + ['Thumb']:
                for k in range(3):
                    b = f'{side}{nm}{k + 1}'
                    Lr = np.linalg.inv(Hr) @ self.rest[b]
                    Lf = np.linalg.inv(Hf) @ ref[b]
                    R = _min_rot(Lr[:3, 1], Lf[:3, 1])
                    L = np.eye(4)
                    L[:3, :3] = R @ Lr[:3, :3]
                    L[:3, 3] = Lf[:3, 3]
                    ref[b] = Hf @ L
        self.ref = ref
        # check: every bone keeps its rest length in REF
        self.ref_length_err = max(abs(np.linalg.norm(self.ref_specs[b][1] - self.ref_specs[b][0]) - self.length[b])
                                  for b in self.parent)

    def deform_bones(self):
        return [b for b in self.order]


def _min_rot(a, b):
    a = D._unit(a)
    b = D._unit(b)
    v = np.cross(a, b)
    c = float(a @ b)
    if np.linalg.norm(v) < 1e-9:
        return np.eye(3) if c > 0 else axis_angle(np.cross(a, [1, 0, 0]) if abs(a[0]) < 0.9 else np.cross(a, [0, 1, 0]), 180)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * (1 / (1 + c))


# ==================================================================== poses
class Pose:
    """Armature-space bone matrices; edits propagate to descendants (FK)."""

    def __init__(self, sk, base=None):
        self.sk = sk
        self.m = {b: M.copy() for b, M in (base or sk.ref).items()}

    def copy(self):
        p = Pose(self.sk, self.m)
        return p

    def descendants(self, b):
        out = [b]
        for c in self.sk.children[b]:
            out += self.descendants(c)
        return out

    def head(self, b):
        return self.m[b][:3, 3].copy()

    def rot(self, b, axis, deg, pivot=None):
        """Rotate bone b (and descendants) about a WORLD axis through its head."""
        if abs(deg) < 1e-9:
            return self
        R = np.eye(4)
        R[:3, :3] = axis_angle(axis, deg)
        p = self.head(b) if pivot is None else np.asarray(pivot, float)
        T = np.eye(4)
        T[:3, 3] = p
        Ti = np.eye(4)
        Ti[:3, 3] = -p
        G = T @ R @ Ti
        for d in self.descendants(b):
            self.m[d] = G @ self.m[d]
        return self

    def rot_local(self, b, axis_local, deg):
        """Rotate about an axis given in the bone's CURRENT local frame."""
        ax = self.m[b][:3, :3] @ np.asarray(axis_local, float)
        return self.rot(b, ax, deg)

    def move(self, b, vec):
        T = np.eye(4)
        T[:3, 3] = vec
        for d in self.descendants(b):
            self.m[d] = T @ self.m[d]
        return self

    def xform(self, b, ref=True):
        """World transform taking the bone's REF (or REST) placement to its pose."""
        base = self.sk.ref[b] if ref else self.sk.rest[b]
        return self.m[b] @ np.linalg.inv(base)

    def point(self, b, p_ref):
        X = self.xform(b)
        return X[:3, :3] @ np.asarray(p_ref) + X[:3, 3]

    # ---- two-bone leg IK keeping the foot planted where it was in REF
    def plant_leg(self, side, ankle_target=None, foot_R=None, knee_dir=None):
        ub, lb, fb = side + 'UpperLeg', side + 'LowerLeg', side + 'Foot'
        hip = self.head(ub)
        target = self.sk.ref[fb][:3, 3] if ankle_target is None else np.asarray(ankle_target)
        l1 = self.sk.length[ub]
        l2 = self.sk.length[lb]
        v = target - hip
        d = min(np.linalg.norm(v), l1 + l2 - 1e-4)
        u = D._unit(v)
        pole = D.FOOT_DIR[side] if knee_dir is None else np.asarray(knee_dir)
        pole = D._unit(pole - u * (pole @ u))
        a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
        hgt = math.sqrt(max(0.0, l1 * l1 - a * a))
        knee = hip + u * a + pole * hgt
        # rotate upper leg so its tail hits the knee, then lower leg to the ankle
        self._aim(ub, knee)
        self._aim(lb, hip + u * d)
        # restore the foot's world orientation (planted)
        Rf = self.sk.ref[fb][:3, :3] if foot_R is None else foot_R
        cur = self.m[fb]
        G = np.eye(4)
        G[:3, :3] = Rf @ cur[:3, :3].T
        p = cur[:3, 3]
        T = np.eye(4)
        T[:3, 3] = p
        Ti = np.eye(4)
        Ti[:3, 3] = -p
        GG = T @ G @ Ti
        for dd in self.descendants(fb):
            self.m[dd] = GG @ self.m[dd]
        return self

    def _aim(self, b, target):
        M = self.m[b]
        y = M[:3, 1]
        want = D._unit(np.asarray(target) - M[:3, 3])
        R = _min_rot(y, want)
        ax = np.cross(y, want)
        if np.linalg.norm(ax) < 1e-9:
            return
        ang = math.degrees(math.acos(np.clip(y @ want, -1, 1)))
        self.rot(b, ax, ang)


# ============================================================== club points
def club_points_ref():
    """(grip centre, striking-face centre, striking-face normal) in the REF pose."""
    T, h = D.club_axis()
    return T, FP.club_impact_point(), h


_STONE_CACHE = {}


def club_samples_ref(n_stone=160):
    """Points on the club for clearance and ground checks (REF pose): 30 along
    the haft (pommel to stone) followed by vertices of the actual stone mesh."""
    T, h = D.club_axis()
    pts = [T + h * t for t in np.linspace(-1.38, (D.club_stone_center() - T) @ h, 30)]
    key = tuple(np.round(FP.strike_normal(), 6))
    if key not in _STONE_CACHE:
        stone = [p for p in FP.club_parts() if p.name == 'ClubStone'][0]
        V = stone.V
        idx = np.random.default_rng(1).choice(len(V), size=min(len(V), 900), replace=False)
        _STONE_CACHE.clear()
        _STONE_CACHE[key] = V[idx]
    return np.concatenate([np.array(pts), _STONE_CACHE[key]])


def body_prims_posed(pose, prims_ref, skip_bones=()):
    """Rigidly move each REF primitive with its bone (approximate posed body)."""
    out = []
    for p in prims_ref:
        if p.op != 'union' or p.bone in skip_bones:
            continue
        q = _copy_prim(p)
        X = pose.xform(p.bone)
        q.c = X[:3, :3] @ p.c + X[:3, 3]
        q.R = X[:3, :3] @ p.R
        out.append(q)
    return out


def _copy_prim(p):
    import copy
    return copy.copy(p)


def min_clearance(points, prims):
    from fc_sdf import eval_prims
    v = np.full(len(points), 1e3)
    for p in prims:
        v = np.minimum(v, p.sdf(points))
    return v


# ================================================================== attacks
def base_crouch(pose, drop, lean_fwd, twist=0.0, side_lean=0.0):
    """Lower the pelvis, lean/twist the torso, keep both feet planted."""
    pose.move('HumanoidRootPart', [0, 0, -drop])
    fwd = np.array([0, -1.0, 0])
    right = np.array([-1.0, 0, 0])
    pose.rot('LowerTorso', right, -lean_fwd * 0.35)          # +lean tips the top forward (-Y)
    pose.rot('UpperTorso', right, -lean_fwd * 0.65)
    pose.rot('UpperTorso', UP, twist)
    pose.rot('LowerTorso', fwd, side_lean)
    for side in ('Right', 'Left'):
        pose.plant_leg(side)
    return pose


def elbow_flex(pose, side):
    """Elbow flexion in degrees (0 = straight, + = bent the natural way)."""
    u = pose.m[side + 'UpperArm'][:3, 1]
    f = pose.m[side + 'LowerArm'][:3, 1]
    hinge = pose.m[side + 'LowerArm'][:3, 0]
    return math.degrees(math.atan2(np.cross(u, f) @ hinge, u @ f))



def solve_club_to(pose, target, face_down=1.0, face_fwd=0.0, prims_ref=None, iters=260, seed=0,
                  keep_elbow=None, stone_centre=None, haft_dir=None):
    """Adjust the right arm (shoulder 3 DOF, elbow hinge, wrist 2 DOF) so the
    club's striking face centre lands on `target`. The face normal is pushed
    toward straight down (face_down) tilted forward (face_fwd). The club and
    forearm stay outside the (rigidly posed) body."""
    T0, F0, h0 = club_points_ref()
    samples = club_samples_ref(200)
    stone = samples[30:]
    sh = 'RightUpperArm'
    el = 'RightLowerArm'
    wr = 'RightHand'
    want_n = D._unit(np.array([0, -face_fwd, -face_down]))
    base = pose.copy()
    Rup = base.m[sh][:3, :3]
    hinge = base.m[el][:3, 0]                  # elbow hinge = bone local X
    wx, wz = base.m[wr][:3, 0], base.m[wr][:3, 2]

    def build(x):
        p = base.copy()
        p.rot(sh, Rup[:, 0], x[0])
        p.rot(sh, Rup[:, 1], x[1])
        p.rot(sh, Rup[:, 2], x[2])
        p.rot_local(el, [1, 0, 0], x[3])
        p.rot_local(wr, [1, 0, 0], x[4])
        p.rot_local(wr, [0, 0, 1], x[5])
        return p

    body = [q for q in (prims_ref or []) if q.bone not in ('RightUpperArm', 'RightLowerArm', 'RightHand')
            and not q.bone.startswith('Right') or q.bone in ('RightUpperLeg', 'RightLowerLeg', 'RightFoot', 'RightToes')]

    def cost(x):
        p = build(x)
        F = p.point('Club', F0)
        Xc = p.xform('Club')
        n = Xc[:3, :3] @ h0
        St = (Xc[:3, :3] @ stone.T).T + Xc[:3, 3]
        low = St[np.argmin(St[:, 2])]
        if stone_centre is not None:
            # windup: the stone held at a point, the haft pointing a given way
            Sc = Xc[:3, :3] @ D.club_stone_center() + Xc[:3, 3]
            c = 2.0 * np.sum((Sc - stone_centre) ** 2) + (3.0 * (1 - n @ D._unit(haft_dir)) if haft_dir is not None else 0)
        else:
            # the stone's lowest point touches the ground at the target; the face points down(-forward)
            c = 4.0 * np.sum((low[:2] - target[:2]) ** 2) + 80.0 * (low[2] - target[2]) ** 2 + 2.0 * (1 - n @ want_n)
        # elbow stays a one-way hinge (5..135 deg of flexion); wrist limits
        fl = elbow_flex(p, 'Right')
        c += 0.01 * max(0.0, 5 - fl) ** 2 + 0.01 * max(0.0, fl - 135) ** 2
        c += 0.002 * max(0, abs(x[4]) - 30) ** 2 + 0.002 * max(0, abs(x[5]) - 25) ** 2
        if keep_elbow is not None:
            c += 0.0005 * (x[3] - keep_elbow) ** 2
        if body:
            S = (p.xform('Club')[:3, :3] @ samples.T).T + p.xform('Club')[:3, 3]
            posed = body_prims_posed(p, body)
            d = min_clearance(S, posed)
            c += 30 * np.sum(np.minimum(d - 0.12, 0) ** 2)
            # nothing may sink below the ground
            c += 300 * np.sum(np.minimum(S[:, 2] - 0.0, 0) ** 2)
        return c
    rng = np.random.default_rng(seed)
    best_x, best_c = None, None
    starts = [np.zeros(6), np.array([0, 0, 0, -25, 0, 0.0]), np.array([-40, 0, 0, -20, 0, 0.0])]
    for trial in range(7):
        x = starts[trial] if trial < len(starts) else rng.uniform([-90, -60, -60, -60, -25, -20], [90, 60, 60, 60, 25, 20])
        c = cost(x)
        step = 16.0
        while step > 0.2:
            improved = False
            for i in range(6):
                for sg in (1, -1):
                    y = x.copy()
                    y[i] += sg * step
                    cy = cost(y)
                    if cy < c:
                        x, c, improved = y, cy, True
            if not improved:
                step *= 0.5
        if best_c is None or c < best_c:
            best_x, best_c = x, c
    p = build(best_x)
    return p, best_x, best_c


# =================================================================== ROM
def rom_keys(sk):
    """RigTest_ROM: a pose every 8 frames; each drives a group of bones."""
    X = np.array([1.0, 0, 0])
    Y = np.array([0, 1.0, 0])
    Z = UP
    seq = []

    def P(label, fn):
        p = Pose(sk)
        fn(p)
        seq.append((label, p))

    P('reference', lambda p: None)
    P('arms overhead', lambda p: (p.rot('RightUpperArm', Y, 125), p.rot('LeftUpperArm', Y, -125)))
    P('arms forward', lambda p: (p.rot('RightUpperArm', X, -85), p.rot('LeftUpperArm', X, -85)))
    P('arms back', lambda p: (p.rot('RightUpperArm', X, 40), p.rot('LeftUpperArm', X, 40)))
    P('elbows 130', lambda p: (p.rot_local('RightLowerArm', [1, 0, 0], 105), p.rot_local('LeftLowerArm', [1, 0, 0], 96)))
    P('wrists + hands open', lambda p: _open_hands(p, sk))
    P('hip flex, high knee', lambda p: (p.rot('LeftUpperLeg', X, -75), p.rot_local('LeftLowerLeg', [1, 0, 0], 80)))
    P('deep squat', lambda p: base_crouch(p, drop=1.6, lean_fwd=18))
    P('forward lean', lambda p: base_crouch(p, drop=0.4, lean_fwd=40))
    P('torso twist', lambda p: (p.rot('UpperTorso', Z, 35), p.rot('LowerTorso', Z, 10)))
    P('side bend', lambda p: p.rot('UpperTorso', Y, 22))
    P('head turn + nod', lambda p: (p.rot('Head', Z, 45), p.rot('Head', X, -20)))
    P('jaw open, eye look, blink', lambda p: (p.rot_local('Jaw', [1, 0, 0], 28), p.rot_local('Eye', [0, 0, 1], 25),
                                              p.rot_local('Eye', [1, 0, 0], 12),
                                              p.rot_local('EyelidUpper', [1, 0, 0], 38),
                                              p.rot_local('Brow', [1, 0, 0], -10)))
    P('belly + mantle + loincloth', lambda p: (p.rot_local('Belly', [1, 0, 0], 8), p.rot('Mantle_L', Y, 14),
                                               p.rot('Mantle_R', Y, -14),
                                               p.rot('Loincloth_Front_1', X, -30), p.rot('Loincloth_Front_2', X, -25),
                                               p.rot('Loincloth_Back_1', X, 25), p.rot('Loincloth_Back_2', X, 20)))
    P('overhead club raise', lambda p: (p.rot('RightUpperArm', X, -160), p.rot_local('RightLowerArm', [1, 0, 0], 40)))
    P('toes + feet', lambda p: (p.rot_local('RightToes', [1, 0, 0], 30), p.rot_local('LeftToes', [1, 0, 0], -25),
                                p.rot_local('RightFoot', [1, 0, 0], 20)))
    return seq


def _open_hands(p, sk):
    for side in ('Right', 'Left'):
        p.rot_local(side + 'Hand', [1, 0, 0], 35)
        for nm in D.FINGER_NAMES + ['Thumb']:
            for k in range(3):
                b = f'{side}{nm}{k + 1}'
                # back toward the REST (open) frame relative to the parent
                par = sk.parent[b]
                rel_rest = np.linalg.inv(sk.rest[par]) @ sk.rest[b]
                want = p.m[par] @ rel_rest
                cur = p.m[b]
                G = want @ np.linalg.inv(cur)
                for d in p.descendants(b):
                    p.m[d] = G @ p.m[d]
