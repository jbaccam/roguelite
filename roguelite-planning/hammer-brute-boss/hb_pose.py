"""Skeleton, poses and the range-of-motion keys for the Hammer Brute (pure numpy).

Bones are armature-space 4x4 matrices (Blender convention: bone local +Y runs
head -> tail, origin at the head). Two fixed sets exist:
  REST  the bind pose (hb_design: A-pose arms, relaxed fingers, upright head)
  REF   the reference stance = idle frame 0 (head tilted, the hammer held low
        across the hips, fists closed on the haft); from hb_grip.solve_reference
Any other pose is built from REF by FK (rotating a bone about its own head
carries all its descendants) plus the analytic arm / leg IK below.

Hinge conventions (both sides):
  +X rotation of LowerArm  = elbow flexion      (X = cross(upper, fore))
  +X rotation of LowerLeg  = knee flexion       (X = cross(thigh, shin))
  +X rotation of finger/thumb bones = curl toward the palm
  +X rotation of Jaw = open, of EyelidUpper = close
  LowerArmTwist and Hand share the forearm roll (TWIST_SHARE on the twist bone).
"""
import math

import numpy as np

import hb_design as D
from hb_sdf import axis_angle

UP = np.array([0, 0, 1.0])
FWD = np.array([0, -1.0, 0])
TWIST_SHARE = 0.5
THUMB_AX = (0.30, 0.20, 0.93)


def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def frame(head, tail, zhint):
    y = unit(np.asarray(tail, float) - np.asarray(head, float))
    z = np.asarray(zhint, float)
    z = z - y * (z @ y)
    if np.linalg.norm(z) < 1e-6:
        z = np.cross(y, [1.0, 0, 0])
    z = unit(z)
    x = np.cross(y, z)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = x, y, z, head
    return M


def frame_x(head, tail, xaxis):
    y = unit(np.asarray(tail, float) - np.asarray(head, float))
    x = np.asarray(xaxis, float)
    x = unit(x - y * (x @ y))
    z = np.cross(x, y)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = x, y, z, head
    return M


def mat(R, t):
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = t
    return M


def T(v):
    M = np.eye(4)
    M[:3, 3] = v
    return M


def _min_rot(a, b):
    a = unit(a)
    b = unit(b)
    v = np.cross(a, b)
    c = float(a @ b)
    if np.linalg.norm(v) < 1e-9:
        return np.eye(3) if c > 0 else axis_angle(np.cross(a, [1, 0, 0]) if abs(a[0]) < 0.9 else np.cross(a, [0, 1, 0]), 180)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * (1 / (1 + c))


def curl_axis_local(side, nm):
    """Hand-local axis about which a POSITIVE rotation curls this digit."""
    cR = np.array([-1.0, 0, 0]) if nm != 'Thumb' else -unit(THUMB_AX)
    if side == 'Right':
        return cR
    return -D.mirror_local('Left', cR)


def twist_angle(R):
    """Twist (deg) about local Y of a rotation matrix (swing-twist split)."""
    w = math.sqrt(max(0.0, 1 + R[0, 0] + R[1, 1] + R[2, 2])) / 2
    if w < 1e-6:
        return 180.0
    qy = (R[0, 2] - R[2, 0]) / (4 * w)
    return math.degrees(2 * math.atan2(qy, w))


# ================================================================= skeleton
def _shirt_bones():
    import hb_parts as FP
    return FP.shirt_bone_points()


def bone_specs_rest():
    """{bone: (4x4 REST matrix, parent, length)}."""
    J = D.J
    S = {}

    def add(name, M, parent, length):
        S[name] = (M, parent, float(length))
    add('Root', frame(J['Root'], J['Root'] + UP * 1.2, FWD), None, 1.2)
    add('HumanoidRootPart', frame(J['HumanoidRootPart'], J['HumanoidRootPart'] + UP * 0.9, FWD), 'Root', 0.9)
    add('LowerTorso', frame(J['LowerTorso'], J['UpperTorso'], FWD), 'HumanoidRootPart',
        np.linalg.norm(J['UpperTorso'] - J['LowerTorso']))
    add('UpperTorso', frame(J['UpperTorso'], J['UpperTorso_tail'], FWD), 'LowerTorso',
        np.linalg.norm(J['UpperTorso_tail'] - J['UpperTorso']))
    add('Head', frame(J['Head'], J['Head_tail'], FWD), 'UpperTorso', np.linalg.norm(J['Head_tail'] - J['Head']))
    add('Jaw', frame(J['Jaw'], J['Jaw_tail'], -UP), 'Head', np.linalg.norm(J['Jaw_tail'] - J['Jaw']))
    add('Brow', frame(J['Brow'], J['Brow'] + UP * 0.45, FWD), 'Head', 0.45)
    lid_t = J['EyelidUpper'] + FWD * 0.35 + UP * 0.25
    add('EyelidUpper', frame(J['EyelidUpper'], lid_t, -UP), 'Head', np.linalg.norm(lid_t - J['EyelidUpper']))
    add('Belly', frame(J['Belly'], J['Belly_tail'], UP), 'LowerTorso', np.linalg.norm(J['Belly_tail'] - J['Belly']))
    sb = _shirt_bones()
    for name, (h, t, par) in sb.items():
        add(name, frame(h, t, FWD if 'Front' in name else -FWD), par, np.linalg.norm(np.asarray(t) - np.asarray(h)))
    for side in ('Right', 'Left'):
        Sh, E, Tw, Wr, hinge = D.rest_arm(side)
        add(side + 'UpperArm', frame_x(Sh, E, hinge), 'UpperTorso', D.L_UPPER)
        add(side + 'LowerArm', frame_x(E, Tw, hinge), side + 'UpperArm', D.L_FORE * D.TWIST_AT)
        add(side + 'LowerArmTwist', frame_x(Tw, Wr, hinge), side + 'LowerArm', D.L_FORE * (1 - D.TWIST_AT))
        Rh, W = D.rest_hand_frame(side)
        add(side + 'Hand', frame(W, W + Rh[:, 1] * 1.1, Rh[:, 2]), side + 'LowerArmTwist', 1.1)
        joints = D.finger_rest_points(side)
        for nm in D.FINGER_NAMES + ['Thumb']:
            pts = [Rh @ p + W for p in joints[nm]]
            ax = Rh @ curl_axis_local(side, nm)
            for k in range(3):
                b = f'{side}{nm}{k + 1}'
                par = side + 'Hand' if k == 0 else f'{side}{nm}{k}'
                add(b, frame_x(pts[k], pts[k + 1], ax), par, np.linalg.norm(pts[k + 1] - pts[k]))
        # legs
        hip, knee, ank = J[side + 'UpperLeg'], J[side + 'LowerLeg'], J[side + 'Foot']
        kh = unit(np.cross(knee - hip, ank - knee))
        add(side + 'UpperLeg', frame_x(hip, knee, kh), 'LowerTorso', np.linalg.norm(knee - hip))
        add(side + 'LowerLeg', frame_x(knee, ank, kh), side + 'UpperLeg', np.linalg.norm(ank - knee))
        fd = D.foot_dir(side)
        ball = ank + fd * (D.FOOT['front'] - D.FOOT['ball'])
        ball[2] = 0.45
        tip = ank + fd * D.FOOT['front']
        tip[2] = 0.42
        add(side + 'Foot', frame(ank, ball, UP), side + 'LowerLeg', np.linalg.norm(ball - ank))
        add(side + 'Toes', frame(ball, tip, UP), side + 'Foot', np.linalg.norm(tip - ball))
    return S


def reference_hammer():
    import hb_grip as G
    ref = G.solve_reference()
    Gr = np.array(ref['grip_R'])
    h = np.array(ref['haft_dir_to_head'])
    n = np.array(ref['n_strike'])
    return frame(Gr, Gr + h * 1.2, n)


class Skeleton:
    def __init__(self):
        import hb_grip as G
        spec = bone_specs_rest()
        self.parent = {b: s[1] for b, s in spec.items()}
        self.length = {b: s[2] for b, s in spec.items()}
        self.rest = {b: s[0] for b, s in spec.items()}
        # Hammer: REST = carried rigidly from REF by the right hand
        ref = G.solve_reference()
        Href = reference_hammer()
        Rr = np.array(ref['hand_frame_Right'])
        HandR_ref = frame(np.array(ref['wrist_Right']), np.array(ref['wrist_Right']) + Rr[:, 1] * 1.1, Rr[:, 2])
        self.rest['Hammer'] = self.rest['RightHand'] @ np.linalg.inv(HandR_ref) @ Href
        self.parent['Hammer'] = 'RightHand'
        self.length['Hammer'] = 1.2
        self.children = {b: [c for c, p in self.parent.items() if p == b] for b in self.parent}
        self.order = []

        def walk(b):
            self.order.append(b)
            for c in self.children[b]:
                walk(c)
        walk('Root')
        self.ref = self._build_ref(ref, Href, HandR_ref)
        self.ref_length_err = max(abs(np.linalg.norm(self._tail(self.ref, b) - self.ref[b][:3, 3]) - self.length[b])
                                  for b in self.order)

    def _tail(self, mats, b):
        return mats[b][:3, 3] + mats[b][:3, 1] * self.length[b]

    def _build_ref(self, ref, Href, HandR_ref):
        P = Pose(self, self.rest)
        P.apply('UpperTorso', D.ref_upper_torso())
        hr = D.HEAD_REF
        Rh = axis_angle(UP, hr['yaw']) @ axis_angle([0, 1.0, 0], hr['roll']) @ axis_angle([1.0, 0, 0], hr['pitch'])
        P.rot_matrix('Head', Rh)
        for side in ('Right', 'Left'):
            Sh = np.array(ref['shoulder_' + side])
            E = np.array(ref['elbow_' + side])
            W = np.array(ref['wrist_' + side])
            Rt = np.array(ref['hand_frame_' + side])
            P.set_arm(side, E, Rt, W)
            # digits: the solved grip, each bone turned by the minimal rotation from
            # its REST orientation in hand space (no twist when the fist closes)
            import hb_grip as G
            gj = G.grip_joints_local(side)
            Hr = self.rest[side + 'Hand']
            Hf = P.m[side + 'Hand']
            for nm in D.FINGER_NAMES + ['Thumb']:
                for k in range(3):
                    b = f'{side}{nm}{k + 1}'
                    Lr = np.linalg.inv(Hr) @ self.rest[b]
                    p0 = gj[nm][k]
                    p1 = gj[nm][k + 1]
                    y = unit(p1 - p0)
                    R = _min_rot(Lr[:3, 1], y) @ Lr[:3, :3]
                    Lf = mat(R, p0)
                    # hand-local coordinates are the hand bone frame with origin at the wrist
                    P.m[b] = Hf @ Lf
        P.m['Hammer'] = Href.copy()
        return P.m

    def deform_bones(self):
        return list(self.order)


# ==================================================================== poses
class Pose:
    """Armature-space bone matrices; edits propagate to descendants (FK)."""

    def __init__(self, sk, base=None):
        self.sk = sk
        self.m = {b: M.copy() for b, M in (base if base is not None else sk.ref).items()}

    def copy(self):
        return Pose(self.sk, self.m)

    def descendants(self, b):
        out = [b]
        for c in self.sk.children[b]:
            out += self.descendants(c)
        return out

    def head(self, b):
        return self.m[b][:3, 3].copy()

    def tail(self, b):
        return self.m[b][:3, 3] + self.m[b][:3, 1] * self.sk.length[b]

    def apply(self, b, G, children=True):
        for d in (self.descendants(b) if children else [b]):
            self.m[d] = G @ self.m[d]
        return self

    def rot(self, b, axis, deg, pivot=None):
        if abs(deg) < 1e-9:
            return self
        p = self.head(b) if pivot is None else np.asarray(pivot, float)
        return self.apply(b, T(p) @ mat(axis_angle(axis, deg), np.zeros(3)) @ T(-p))

    def rot_matrix(self, b, R, pivot=None):
        p = self.head(b) if pivot is None else np.asarray(pivot, float)
        return self.apply(b, T(p) @ mat(R, np.zeros(3)) @ T(-p))

    def rot_local(self, b, axis_local, deg):
        return self.rot(b, self.m[b][:3, :3] @ np.asarray(axis_local, float), deg)

    def move(self, b, vec):
        return self.apply(b, T(vec))

    def set_world(self, b, M, children=True):
        return self.apply(b, M @ np.linalg.inv(self.m[b]), children)

    def xform(self, b, ref=True):
        base = self.sk.ref[b] if ref else self.sk.rest[b]
        return self.m[b] @ np.linalg.inv(base)

    def point(self, b, p_ref):
        X = self.xform(b)
        return X[:3, :3] @ np.asarray(p_ref) + X[:3, 3]

    # ------------------------------------------------------------- arms
    def set_arm(self, side, E, Rt, W):
        """Put the arm chain exactly on elbow E and hand frame (Rt, W). The elbow
        stays a pure hinge; the forearm roll is shared TWIST_SHARE / rest between
        LowerArmTwist and Hand (relative to the REST forearm-hand relation)."""
        sk = self.sk
        ub, lb, tb, hb = side + 'UpperArm', side + 'LowerArm', side + 'LowerArmTwist', side + 'Hand'
        S = self.head(ub)
        u = unit(E - S)
        f = unit(W - E)
        hx = np.cross(u, f)
        if np.linalg.norm(hx) < 1e-4:
            hx = self.m[lb][:3, 0]
        hinge = unit(hx)
        self.set_world(ub, frame_x(S, E, hinge))
        Tw = E + f * D.L_FORE * D.TWIST_AT
        self.set_world(lb, frame_x(E, Tw, hinge))
        Rf = self.m[lb][:3, :3]
        rel_rest = np.linalg.inv(sk.rest[lb][:3, :3]) @ sk.rest[hb][:3, :3]
        need = Rf.T @ Rt
        tau = twist_angle(need @ rel_rest.T)
        Rtw = Rf @ axis_angle([0, 1.0, 0], tau * TWIST_SHARE)
        self.set_world(tb, mat(Rtw, Tw))
        self.set_world(hb, mat(Rt, W))
        return tau

    def reach(self, side, Rt, W, swivels=None, body=None):
        """Analytic arm IK to the hand frame (Rt, W): searches the elbow swivel for the
        straightest wrist with the elbow kept outside the trunk; returns metrics."""
        import hb_grip as G
        S = self.head(side + 'UpperArm')
        lat = np.array([-1.0 if side == 'Right' else 1.0, 0, 0])
        u = unit(W - S)
        p1 = unit(lat - u * (lat @ u)) if abs(lat @ u) < 0.98 else unit(np.cross(u, FWD))
        p2 = unit(np.cross(u, p1))
        if p2 @ np.array([0, 1.0, 0]) < 0:
            p2 = -p2
        best = None
        for w in (np.arange(-120, 181, 6) if swivels is None else swivels):
            pole = math.cos(math.radians(w)) * p1 + math.sin(math.radians(w)) * p2
            E, ok = G.two_bone(S, W, D.L_UPPER, D.L_FORE, pole)
            F = unit(W - E)
            fl, dv = G.wrist_angles(F, Rt)
            torso_c = self.head('UpperTorso')
            out = (E - torso_c) @ lat
            flex = math.degrees(math.acos(np.clip(unit(E - S) @ F, -1, 1)))
            # forearm roll this elbow placement would need (spread over twist bone + hand)
            hx = np.cross(unit(E - S), F)
            hinge = unit(hx) if np.linalg.norm(hx) > 1e-4 else self.m[side + 'LowerArm'][:3, 0]
            Rf = frame_x(E, E + F, hinge)[:3, :3]
            lb, hb = side + 'LowerArm', side + 'Hand'
            rel_rest = np.linalg.inv(self.sk.rest[lb][:3, :3]) @ self.sk.rest[hb][:3, :3]
            tau = twist_angle((Rf.T @ Rt) @ rel_rest.T)
            c = fl ** 2 + 1.5 * dv ** 2 + 400 * max(0, 2.9 - out) ** 2 + (0 if ok else 1e5)
            c += 0.05 * max(0.0, abs(tau) - 35.0) ** 2
            c += 50 * max(0, flex - 140) ** 2
            if body is not None:
                c += body(E)
            if best is None or c < best[0]:
                best = (c, E, fl, dv, ok, flex)
        c, E, fl, dv, ok, flex = best
        tau = self.set_arm(side, E, Rt, W)
        return {'cost': c, 'wrist_flex': fl, 'wrist_dev': dv, 'reach_ok': ok, 'elbow_flex': flex, 'twist': tau}

    # ------------------------------------------------------------- hammer
    def hold_hammer(self, H, slide=0.0):
        """Both hands to the hammer placed at H (Hammer bone world matrix), the right
        hand slid `slide` studs from its carry grip toward the butt."""
        sk = self.sk
        RH_in_H = np.linalg.inv(sk.ref['Hammer']) @ sk.ref['RightHand']
        LH_in_H = np.linalg.inv(sk.ref['Hammer']) @ sk.ref['LeftHand']
        Rt = H @ T([0, -slide, 0]) @ RH_in_H
        Lt = H @ LH_in_H
        mr = self.reach('Right', Rt[:3, :3], Rt[:3, 3])
        ml = self.reach('Left', Lt[:3, :3], Lt[:3, 3])
        self.set_world('Hammer', H)
        return mr, ml

    # ------------------------------------------------------------- legs
    def plant_leg(self, side, ankle_target=None, foot_R=None, knee_dir=None):
        ub, lb, fb = side + 'UpperLeg', side + 'LowerLeg', side + 'Foot'
        hip = self.head(ub)
        target = self.sk.ref[fb][:3, 3] if ankle_target is None else np.asarray(ankle_target)
        l1, l2 = self.sk.length[ub], self.sk.length[lb]
        v = target - hip
        d = min(np.linalg.norm(v), l1 + l2 - 1e-4)
        u = unit(v)
        pole = D.foot_dir(side) if knee_dir is None else np.asarray(knee_dir, float)
        pole = unit(pole - u * (pole @ u))
        a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
        hgt = math.sqrt(max(0.0, l1 * l1 - a * a))
        knee = hip + u * a + pole * hgt
        ank = hip + u * d
        hinge = unit(np.cross(knee - hip, ank - knee))
        Rf_old = self.m[fb][:3, :3].copy()
        self.set_world(ub, frame_x(hip, knee, hinge))
        self.set_world(lb, frame_x(knee, ank, hinge))
        Rf = self.sk.ref[fb][:3, :3] if foot_R is None else foot_R
        self.set_world(fb, mat(Rf, self.head(fb)))
        return self


# ================================================================= helpers
def lowest_hammer_z(pose):
    import hb_parts as FP
    X = pose.m['Hammer']
    pts = FP.hammer_corner_points()
    W = (X[:3, :3] @ pts.T).T + X[:3, 3]
    return float(W[:, 2].min())


def hammer_frame(G_mid, h, n, slide):
    """Hammer bone world matrix from the point midway between the hands, the haft
    direction toward the head and the striking-face normal."""
    import hb_grip as G
    ref = G.solve_reference()
    yL = -(ref['s_left'] - D.S_RIGHT)
    m_y = (-slide + yL) / 2
    h = unit(h)
    n = unit(n - h * (n @ h))
    o = np.asarray(G_mid, float) - h * m_y
    return frame(o, o + h, n)


def hammer_resting(face_xy, dir_xy):
    """Hammer set down: standing on its flat striking face with the haft sloping
    back to the ground (bone Y toward the head along dir_xy, rising 12 deg)."""
    a = math.radians(12.1)
    d = unit([dir_xy[0], dir_xy[1], 0.0])
    h = unit(d * math.cos(a) + UP * math.sin(a))
    z = unit(-UP - h * (-UP @ h))
    face = np.array([face_xy[0], face_xy[1], 0.0])
    o = face - h * D.S_RIGHT - z * (D.EYE_OFFSET + D.HEAD_HALF[1])
    M = frame(o, o + h, z)
    import hb_parts as FP
    pts = FP.hammer_corner_points()
    low = float(((M[:3, :3] @ pts.T).T + M[:3, 3])[:, 2].min())
    M[2, 3] -= low - 0.02
    return M


def solve_hold(pose, G_mid, h, n, slide, search=True, ground=None):
    """Place the hammer near the intent (G_mid, h, n) and solve both arms; a small
    search over the hand-midpoint, the haft direction and the roll keeps both
    wrists inside their limits."""
    def build(dx):
        hh = unit(axis_angle(UP, dx[3]) @ axis_angle(np.cross(h, UP) if abs(unit(h) @ UP) < 0.95 else [1, 0, 0], dx[4]) @ h)
        nn = axis_angle(hh, dx[5]) @ n
        return hammer_frame(np.asarray(G_mid) + dx[:3], hh, nn, slide)

    def cost(dx):
        p = pose.copy()
        H = build(dx)
        mr, ml = p.hold_hammer(H, slide)
        c = 0.0
        for m in (mr, ml):
            c += max(0, abs(m['wrist_flex']) - 30) ** 2 * 4 + max(0, abs(m['wrist_dev']) - 22) ** 2 * 6
            c += 0.02 * (m['wrist_flex'] ** 2 + 1.5 * m['wrist_dev'] ** 2) + (0 if m['reach_ok'] else 1e4)
            c += 0.05 * max(0, m['elbow_flex'] - 135) ** 2
            c += 0.004 * max(0.0, abs(m['twist']) - 45.0) ** 2
        c += 2.0 * float(np.sum(dx[:3] ** 2)) + 0.002 * float(np.sum(dx[3:] ** 2))
        if ground is not None:
            z = lowest_hammer_z(p)
            c += 200 * (z - ground) ** 2 if ground > -1 else 200 * max(0, -z) ** 2
        return c
    x = np.zeros(6)
    if search:
        c = cost(x)
        steps = np.array([0.4, 0.4, 0.4, 12.0, 12.0, 20.0])
        while steps.max() > 0.5:
            improved = False
            for i in range(6):
                for sg in (1, -1):
                    y = x.copy()
                    y[i] += sg * steps[i]
                    cy = cost(y)
                    if cy < c:
                        x, c, improved = y, cy, True
            if not improved:
                steps = steps * 0.5
    H = build(x)
    mr, ml = pose.hold_hammer(H, slide)
    return {'Right': mr, 'Left': ml, 'adjust': x.tolist()}


def base_crouch(pose, drop, lean_fwd, twist=0.0, side_lean=0.0, back=0.0):
    pose.move('HumanoidRootPart', [0, back, -drop])
    right = np.array([-1.0, 0, 0])
    pose.rot('LowerTorso', right, -lean_fwd * 0.35)
    pose.rot('UpperTorso', right, -lean_fwd * 0.65)
    if twist:
        pose.rot('LowerTorso', UP, twist * 0.3)
        pose.rot('UpperTorso', UP, twist * 0.7)
    if side_lean:
        pose.rot('LowerTorso', FWD, side_lean)
    for side in ('Right', 'Left'):
        pose.plant_leg(side)
    return pose


def open_hand(p, side, wrist_ext=0.0):
    sk = p.sk
    if wrist_ext:
        p.rot_local(side + 'Hand', [1, 0, 0], -wrist_ext)
    for nm in D.FINGER_NAMES + ['Thumb']:
        for k in range(3):
            b = f'{side}{nm}{k + 1}'
            par = sk.parent[b]
            rel_rest = np.linalg.inv(sk.rest[par]) @ sk.rest[b]
            p.set_world(b, p.m[par] @ rel_rest)
    for nm in D.FINGER_NAMES:
        for k in range(3):
            p.rot_local(f'{side}{nm}{k + 1}', [1, 0, 0], -REST_OPEN[k])
    return p


REST_OPEN = (12.0, 16.0, 8.0)       # straighten the relaxed REST fingers a little more


def elbow_flex(pose, side):
    u = pose.m[side + 'UpperArm'][:3, 1]
    f = pose.m[side + 'LowerArm'][:3, 1]
    hinge = pose.m[side + 'LowerArm'][:3, 0]
    return math.degrees(math.atan2(np.cross(u, f) @ hinge, u @ f))


# =================================================================== ROM
def rom_keys(sk):
    """RigTest_ROM: the extreme poses the attack clips will reach, plus checks of
    the face, belly and shirt bones. Returns [(label, Pose, metrics)]."""
    seq = []
    X = np.array([1.0, 0, 0])
    Y = np.array([0, 1.0, 0])
    ref = Pose(sk)
    H0 = ref.m['Hammer']
    import hb_grip as G
    gref = G.solve_reference()
    n0 = np.array(gref['n_strike'])
    att = D.S_RIGHT_ATTACK_MAX - D.S_RIGHT

    def P(label, fn):
        p = Pose(sk)
        info = fn(p) or {}
        seq.append((label, p, info))

    P('idle (reference)', lambda p: None)

    def overhead(p):
        # top of the slam: the hammer lifted overhead in the barbell grip, slightly
        # behind the head, the flat face still pointing down for the two-hand slam
        base_crouch(p, drop=0.15, lean_fwd=-10)
        sh = (p.head('RightUpperArm') + p.head('LeftUpperArm')) / 2
        return solve_hold(p, sh + np.array([-0.4, 0.5, 4.2]), unit([-1.0, 0.0, -0.05]), np.array([0, 0, -1.0]), 0.0)
    P('overhead two-hand slam (top)', overhead)

    def impact(p):
        base_crouch(p, drop=1.2, lean_fwd=30)
        return solve_hold(p, np.array([-0.5, -5.2, 3.0]), unit([-1.0, -0.1, 0.0]), np.array([0, 0, -1.0]), 0.0,
                          ground=0.0)
    P('slam impact (face flat on ground)', impact)

    def spin(p):
        base_crouch(p, drop=0.6, lean_fwd=6, twist=-38)
        sh = p.head('RightUpperArm')
        h = unit([-0.30, 0.70, 0.65])          # haft up over the right shoulder, head behind
        return solve_hold(p, sh + np.array([1.4, -1.7, -2.0]), h, unit(np.cross(UP, h)), 0.0)
    P('spin wind-up (over right shoulder)', spin)

    def charge(p):
        base_crouch(p, drop=1.2, lean_fwd=34, back=0.4)
        hip = (p.head('RightUpperLeg') + p.head('LeftUpperLeg')) / 2
        return solve_hold(p, hip + np.array([0.3, -3.2, -0.7]), unit([-1.0, -0.25, -0.12]), np.array([0, 0, -1.0]),
                          0.0, ground=-2)
    P('charge crouch', charge)

    def squat(p):
        base_crouch(p, drop=1.9, lean_fwd=22)
        hip = (p.head('RightUpperLeg') + p.head('LeftUpperLeg')) / 2
        return solve_hold(p, hip + np.array([0.4, -3.4, -0.6]), unit([-0.96, -0.2, -0.15]), np.array([0, 0, -1.0]), 0.0,
                          ground=-2)
    P('deep squat', squat)

    def forward(p):
        sh = (p.head('RightUpperArm') + p.head('LeftUpperArm')) / 2
        return solve_hold(p, sh + np.array([0.0, -5.6, -0.6]), unit([-1.0, 0.0, 0.0]), np.array([0, 0, -1.0]), 0.0)
    P('arms forward', forward)

    def twist(p):
        p.rot('LowerTorso', UP, 12)
        p.rot('UpperTorso', UP, 33)
        for side in ('Right', 'Left'):
            p.plant_leg(side)
        return {}
    P('torso twist', twist)

    def death(p):
        # kneeling: knees on the ground, shins back along the ground, torso slumped
        p.move('HumanoidRootPart', [0, 0.7, -2.15])
        p.rot('LowerTorso', -X, 6)
        p.rot('UpperTorso', -X, 22)
        p.rot('Head', -X, 18)
        for side in ('Right', 'Left'):
            hip = p.head(side + 'UpperLeg')
            s = -1 if side == 'Right' else 1
            knee = np.array([hip[0] + s * 0.25, hip[1] - 1.0, 0.95])
            l1 = sk.length[side + 'UpperLeg']
            v = unit(knee - hip)
            knee = hip + v * l1
            ank = knee + unit([0, 1.0, -0.08]) * sk.length[side + 'LowerLeg']
            hinge = unit(np.cross(knee - hip, ank - knee))
            p.set_world(side + 'UpperLeg', frame_x(hip, knee, hinge))
            p.set_world(side + 'LowerLeg', frame_x(knee, ank, hinge))
            Rf = axis_angle(X, -80) @ sk.ref[side + 'Foot'][:3, :3]
            p.set_world(side + 'Foot', mat(Rf, p.head(side + 'Foot')))
        # arms hang, hands open, the hammer dropped on the ground beside him
        for side in ('Right', 'Left'):
            Sh = p.head(side + 'UpperArm')
            s = -1 if side == 'Right' else 1
            W = Sh + np.array([s * 0.9, -1.8, -6.0])
            R = p.m[side + 'Hand'][:3, :3]
            down = unit(W - Sh)
            R2 = _min_rot(R[:, 1], down) @ R
            p.reach(side, R2, W)
            open_hand(p, side)
        Hd = hammer_resting(np.array([-5.6, -4.6]), unit([-0.45, -0.9, 0]))
        p.set_world('Hammer', Hd)
        return {}
    P('death kneel (hammer dropped)', death)

    def fists_open(p):
        Hg = hammer_resting(np.array([-6.2, -1.8]), unit([0.15, -1.0, 0]))
        for side in ('Right', 'Left'):
            Sh = p.head(side + 'UpperArm')
            s = -1 if side == 'Right' else 1
            W = Sh + np.array([s * 1.6, -3.2, -4.6])
            R = p.m[side + 'Hand'][:3, :3]
            R2 = _min_rot(R[:, 2], unit([s * 0.4, 0.3, 0.85])) @ R
            p.reach(side, R2, W)
            open_hand(p, side, wrist_ext=10)
        p.set_world('Hammer', Hg)
        return {}
    P('fists open (hammer set down)', fists_open)

    def face(p):
        p.rot('Head', UP, 32)
        p.rot('Head', X, -14)
        p.rot_local('Jaw', [1, 0, 0], 22)
        p.rot_local('Brow', [1, 0, 0], 12)
        p.rot_local('EyelidUpper', [1, 0, 0], 30)
        return {}
    P('head turn, jaw open, brow, blink', face)

    def secondary(p):
        p.rot_local('Belly', [1, 0, 0], -9)
        p.rot_local('Shirt_Front_1', [1, 0, 0], 18)
        p.rot_local('Shirt_Front_2', [1, 0, 0], 22)
        p.rot_local('Shirt_Back', [1, 0, 0], 16)
        return {}
    P('belly + shirt bones', secondary)
    return seq
