"""Tomb Warden motion: skeleton, FK/IK and the game clips (pure numpy).

Poses are matrix_basis per deform bone (4x4). The rest pose IS the Idle start
pose, so non-looping clips start and end on identity bases. Feet are pinned
by analytic two-bone IK every frame; the arms use IK wherever a fist has to
land somewhere (ground, chest, the coffin cross) and FK for swings.
"""
import math

import numpy as np

import tw_design as D

FPS = 24
I3 = np.eye(3)


# ------------------------------------------------------------------ maths
def Rx(d):
    c, s = math.cos(math.radians(d)), math.sin(math.radians(d))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Ry(d):
    c, s = math.cos(math.radians(d)), math.sin(math.radians(d))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def Rz(d):
    c, s = math.cos(math.radians(d)), math.sin(math.radians(d))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def rot(pitch=0.0, roll=0.0, yaw=0.0):
    """World-aligned rotation: +pitch bends forward (about +X), +roll leans to
    his left (about +Y), +yaw turns to his left (about +Z)."""
    return Rz(yaw) @ Rx(pitch) @ Ry(roll)


import os as _os
SHOULDER_SHARE = float(_os.environ.get('TW_SHARE', '0.6'))
SHOULDER_MAX = 78.0


def axis_rot(axis, deg):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def m4(R=None, t=None):
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = R
    if t is not None:
        M[:3, 3] = t
    return M


def rot_angle(R):
    return math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(R[:3, :3]) - 1) / 2))))


def quat(R):
    m = R[:3, :3]
    t = np.trace(m)
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        q = np.array([0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s])
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        q = np.array([(m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s])
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        q = np.array([(m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s])
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        q = np.array([(m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s])
    return q / np.linalg.norm(q)


def twist_deg(R, axis=(0, 1, 0)):
    """Swing-twist: twist angle of rotation R about local `axis` (degrees)."""
    q = quat(R)
    a = np.asarray(axis, float)
    p = (q[1:] @ a) * a
    tw = np.array([q[0], *p])
    n = np.linalg.norm(tw)
    if n < 1e-9:
        return 180.0
    tw /= n
    ang = 2 * math.degrees(math.atan2(np.linalg.norm(tw[1:]), tw[0]))
    if ang > 180:
        ang -= 360
    sign = 1.0 if (tw[1:] @ a) >= 0 else -1.0
    return sign * abs(ang)


def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# --------------------------------------------------------------- tracks
class Track:
    """Keyed vector channel. Each key: (time, value, mode) where mode is the
    interpolation INTO that key: 'smooth' (C1 Catmull-Rom, monotone-limited),
    'in' (accelerating, speed peaks at the key), 'out' (decelerating),
    'ease' (smoothstep), 'linear', 'hold'."""

    def __init__(self, keys):
        self.t = np.array([k[0] for k in keys], float)
        self.v = [np.atleast_1d(np.asarray(k[1], float)) for k in keys]
        self.m = [k[2] if len(k) > 2 else 'smooth' for k in keys]
        n = len(keys)
        self.tan = []
        for i in range(n):
            if i == 0 or i == n - 1 or self.m[i] != 'smooth' or self.m[i + 1] != 'smooth':
                self.tan.append(np.zeros_like(self.v[i]))
                continue
            d0 = self.v[i] - self.v[i - 1]
            d1 = self.v[i + 1] - self.v[i]
            m = (self.v[i + 1] - self.v[i - 1]) / (self.t[i + 1] - self.t[i - 1])
            m = np.where(d0 * d1 <= 0, 0.0, m)
            self.tan.append(m)

    def __call__(self, t):
        if t <= self.t[0]:
            return self.v[0].copy()
        if t >= self.t[-1]:
            return self.v[-1].copy()
        i = int(np.searchsorted(self.t, t, side='right') - 1)
        t0, t1 = self.t[i], self.t[i + 1]
        h = t1 - t0
        u = (t - t0) / h
        a, b = self.v[i], self.v[i + 1]
        mode = self.m[i + 1]
        if mode == 'smooth':
            h00 = 2 * u ** 3 - 3 * u ** 2 + 1
            h10 = u ** 3 - 2 * u ** 2 + u
            h01 = -2 * u ** 3 + 3 * u ** 2
            h11 = u ** 3 - u ** 2
            return h00 * a + h10 * h * self.tan[i] + h01 * b + h11 * h * self.tan[i + 1]
        if mode == 'in':
            w = u ** 2.2
        elif mode == 'out':
            w = 1 - (1 - u) ** 2.2
        elif mode == 'ease':
            w = u * u * (3 - 2 * u)
        elif mode == 'hold':
            w = 0.0
        else:
            w = u
        return a + (b - a) * w


def tracks(spec):
    return {k: Track(v) for k, v in spec.items()}


# --------------------------------------------------------------- skeleton
class Skel:
    def __init__(self):
        spec = D.skeleton_spec()
        self.order = [s[0] for s in spec]
        self.parent = {s[0]: s[1] for s in spec}
        self.head = {s[0]: s[2] for s in spec}
        self.tail = {s[0]: s[3] for s in spec}
        self.length = {s[0]: float(np.linalg.norm(s[3] - s[2])) for s in spec}
        self.rest = {s[0]: m4(s[4], s[2]) for s in spec}
        self.lrest = {n: (np.linalg.inv(self.rest[p]) @ self.rest[n] if p else self.rest[n].copy())
                      for n, p in self.parent.items()}
        self.fist_bottom = 1.62         # along the hand axis from the wrist (set from the fist mesh)
        self.fist_center = 0.84
        self.pole_arm, self.pole_leg = {}, {}
        for side in D.SIDES:
            self.pole_arm[side] = self._pole(self.head[side + 'UpperArm'], self.head[side + 'LowerArm'],
                                             self.head[side + 'Hand'])
            self.pole_leg[side] = self._pole(self.head[side + 'UpperLeg'], self.head[side + 'LowerLeg'],
                                             self.head[side + 'Foot'])

    @staticmethod
    def _pole(a, b, c):
        d = unit(c - a)
        e = b - a
        return unit(e - d * (e @ d))

    def identity(self):
        return {n: np.eye(4) for n in self.order}

    def fk(self, B):
        for h, tgt in D.HELPERS.items():
            Hm = np.eye(4)
            Hm[:3, :3] = slerp_R(np.eye(3), B[tgt][:3, :3], 0.5)
            B[h] = Hm
        W = {}
        for n in self.order:
            p = self.parent[n]
            W[n] = (W[p] @ self.lrest[n] if p else self.rest[n]) @ B[n]
        return W

    def frame_of(self, W, name):
        """World matrix the bone would have with an identity basis (parent-driven)."""
        p = self.parent[name]
        return W[p] @ self.lrest[name] if p else self.rest[name]


class Poser:
    """Builds one frame's bases in dependency order."""

    def __init__(self, sk):
        self.sk = sk
        self.B = sk.identity()

    def W(self):
        return self.sk.fk(self.B)

    def rot_world(self, name, R):
        Rr = self.sk.rest[name][:3, :3]
        self.B[name][:3, :3] = Rr.T @ R @ Rr

    def trans_world(self, name, d):
        W = self.W()
        F = self.sk.frame_of(W, name)
        self.B[name][:3, 3] = F[:3, :3].T @ np.asarray(d, float)

    def local_rot(self, name, R):
        self.B[name][:3, :3] = R

    # ---- chest space helpers (targets that ride on the posed UpperTorso)
    def chest_pt(self, p, W=None):
        W = self.W() if W is None else W
        M = W['UpperTorso'] @ np.linalg.inv(self.sk.rest['UpperTorso'])
        return (M @ np.append(p, 1.0))[:3]

    def chest_dir(self, v, W=None):
        W = self.W() if W is None else W
        M = W['UpperTorso'][:3, :3] @ self.sk.rest['UpperTorso'][:3, :3].T
        return M @ np.asarray(v, float)

    def pelvis_dir(self, v, W=None):
        W = self.W() if W is None else W
        M = W['LowerTorso'][:3, :3] @ self.sk.rest['LowerTorso'][:3, :3].T
        return M @ np.asarray(v, float)

    # ---- two-bone IK
    def _two_bone(self, a_name, b_name, root_pos, target, pole, L1, L2):
        d = target - root_pos
        dist = float(np.linalg.norm(d))
        dist = min(max(dist, abs(L1 - L2) + 1e-4), (L1 + L2) * 0.99995)
        dh = unit(d)
        ca = (L1 * L1 + dist * dist - L2 * L2) / (2 * L1 * dist)
        A = math.acos(max(-1.0, min(1.0, ca)))
        p = np.asarray(pole, float) - dh * (np.asarray(pole, float) @ dh)
        p = unit(p)
        E = root_pos + L1 * (math.cos(A) * dh + math.sin(A) * p)
        T = root_pos + dh * dist
        Y1 = unit(E - root_pos)
        Y2 = unit(T - E)
        c = np.cross(Y1, Y2)
        X = unit(c) if np.linalg.norm(c) > 1e-7 else unit(np.cross(Y1, -p))
        R1 = np.stack([X, Y1, np.cross(X, Y1)], 1)
        R2 = np.stack([X, Y2, np.cross(X, Y2)], 1)
        reach = float(np.linalg.norm(target - root_pos)) / (L1 + L2)
        return R1, R2, E, reach

    def arm_ik(self, side, target, pole, end='wrist', twist=0.0, wrist=None):
        sk = self.sk
        ua, la, ha, sh = side + 'UpperArm', side + 'LowerArm', side + 'Hand', side + 'Shoulder'
        self.B[sh] = np.eye(4)
        pre = getattr(self, 'sh_pre', {}).get(side)
        if pre is not None:
            Fs0 = sk.frame_of(self.W(), sh)[:3, :3]
            self.B[sh][:3, :3] = Fs0.T @ pre @ Fs0
        else:
            pre = np.eye(3)
        W = self.W()
        Fu = sk.frame_of(W, ua)
        S = Fu[:3, 3]
        extra = {'wrist': 0.0, 'fistbottom': sk.fist_bottom, 'fistcenter': sk.fist_center}[end]
        R1, R2, E, reach = self._two_bone(ua, la, S, np.asarray(target, float), pole, sk.length[ua],
                                          sk.length[la] + extra)
        # the shoulder (clavicle) takes SHOULDER_SHARE of the upper arm's swing, then the arm is re-solved
        y0, y1 = Fu[:3, 1], R1[:, 1]
        ax = np.cross(y0, y1)
        ang = math.degrees(math.atan2(np.linalg.norm(ax), float(y0 @ y1)))
        if ang > 1e-4:
            Rw = axis_rot(ax, min(SHOULDER_SHARE * ang, SHOULDER_MAX))
            Fs = sk.frame_of(W, sh)[:3, :3]
            self.B[sh][:3, :3] = Fs.T @ Rw @ pre @ Fs
            W = self.W()
            Fu = sk.frame_of(W, ua)
            S = Fu[:3, 3]
            R1, R2, E, reach = self._two_bone(ua, la, S, np.asarray(target, float), pole, sk.length[ua],
                                              sk.length[la] + extra)
        R2 = R2 @ Ry(twist)
        self.B[ua][:3, :3] = Fu[:3, :3].T @ R1
        self.B[la][:3, :3] = (R1 @ sk.lrest[la][:3, :3]).T @ R2
        self.B[ha][:3, :3] = I3 if wrist is None else wrist
        return reach

    def leg_ik(self, side, ankle, pole, foot_R=None, toe=0.0):
        sk = self.sk
        ul, ll, ft, to = side + 'UpperLeg', side + 'LowerLeg', side + 'Foot', side + 'Toes'
        W = self.W()
        Fu = sk.frame_of(W, ul)
        H = Fu[:3, 3]
        R1, R2, E, reach = self._two_bone(ul, ll, H, np.asarray(ankle, float), pole, sk.length[ul], sk.length[ll])
        self.B[ul][:3, :3] = Fu[:3, :3].T @ R1
        self.B[ll][:3, :3] = (R1 @ sk.lrest[ll][:3, :3]).T @ R2
        Rf = sk.rest[ft][:3, :3] if foot_R is None else foot_R
        self.B[ft][:3, :3] = (R2 @ sk.lrest[ft][:3, :3]).T @ Rf
        self.B[to][:3, :3] = Rx(toe)
        return reach


# ------------------------------------------------------------ foot helper
def foot_place(sk, side, offset, pitch=0.0, yaw=0.0, pivot='ball', lift=0.0):
    """Ankle target and foot world rotation for a foot translated by `offset`
    (world) from rest, rotated about its ball (or heel) by pitch/yaw."""
    a = sk.head[side + 'Foot']
    t_ = sk.head[side + 'Toes']
    b = np.array([t_[0], t_[1] - 0.30, 0.0]) if pivot == 'ball' else np.array([a[0], a[1] + 0.55, 0.06])
    Rd = Rz(yaw) @ Rx(pitch)
    ankle = np.asarray(offset, float) + b + Rd @ (a - b) + np.array([0, 0, lift])
    return ankle, Rd @ sk.rest[side + 'Foot'][:3, :3]


def legs_planted(P, offsets=None, pole_turn=0.0):
    sk = P.sk
    for side in D.SIDES:
        off = np.zeros(3) if offsets is None else offsets[side]
        an, R = foot_place(sk, side, off)
        pole = P.pelvis_dir(sk.pole_leg[side]) * 0.6 + sk.pole_leg[side] * 0.4
        P.leg_ik(side, an, pole, R)


def rest_wrist(sk, side):
    return sk.head[side + 'Hand'].copy()


def rest_fistcenter(sk, side):
    return sk.head[side + 'Hand'] + D.hand_rest_dir(side) * sk.fist_center


def cloth(P, sway=0.0, front_extra=0.0, back_extra=0.0):
    """Loincloth flaps: clear the thighs (front swings forward when a thigh
    lifts, back swings back when one extends) plus secondary sway."""
    sk = P.sk
    W = P.W()
    fwd = []
    for side in D.SIDES:
        y = W[side + 'UpperLeg'][:3, 1]
        yl = W['LowerTorso'][:3, :3] @ sk.rest['LowerTorso'][:3, :3].T
        y = yl.T @ y                          # thigh direction in pelvis rest space
        fwd.append(math.degrees(math.atan2(-y[1], -y[2])))
    rest_fwd = [math.degrees(math.atan2(-(unit(sk.tail[s + 'UpperLeg'] - sk.head[s + 'UpperLeg']))[1],
                                        -(unit(sk.tail[s + 'UpperLeg'] - sk.head[s + 'UpperLeg']))[2]))
                for s in D.SIDES]
    lift = max(0.0, max(f - r for f, r in zip(fwd, rest_fwd)))
    ext = max(0.0, max(r - f for f, r in zip(fwd, rest_fwd)))
    drop = max(0.0, float(sk.head['LowerTorso'][2] - W['LowerTorso'][2, 3]))
    front_extra = front_extra + 55.0 * min(1.0, drop / 1.2)
    back_extra = back_extra + 25.0 * min(1.0, drop / 1.2)
    P.rot_world('SashFront1', rot(pitch=-(0.62 * lift + front_extra + sway)))
    P.rot_world('SashFront2', rot(pitch=-(0.25 * lift + 0.6 * sway + 0.5 * front_extra)))
    P.rot_world('SashBack1', rot(pitch=0.55 * ext + back_extra - 0.7 * sway))
    P.rot_world('SashBack2', rot(pitch=0.2 * ext - 0.5 * sway))


# ===================================================================== clips
def frames_of(fn, n):
    return [fn(f / FPS) for f in range(n + 1)]


def b_wave(t, period):
    return 0.5 * (1 - math.cos(2 * math.pi * t / period))


def osc(t, period):
    return math.sin(2 * math.pi * t / period) ** 3


def lagged(t, period, lag):
    """Same breath shape, peaking `lag` seconds later, still zero at t=0."""
    tau = t - lag * b_wave(t, period)
    return b_wave(tau, period)


# ----------------------------------------------------------------- Idle
IDLE_N = 72


def idle_pose(sk, t):
    P = Poser(sk)
    br = b_wave(t, 1.5)
    br_l = lagged(t, 1.5, 0.25)
    br_ll = lagged(t, 1.5, 0.42)
    sw = osc(t, 3.0)
    P.trans_world('HumanoidRootPart', (0.025 * sw, 0, -0.03 * br))
    P.rot_world('HumanoidRootPart', rot(roll=0.8 * sw))
    P.rot_world('LowerTorso', rot(pitch=-0.8 * br))
    P.rot_world('UpperTorso', rot(pitch=-2.4 * br, roll=-1.4 * sw, yaw=1.2 * sw))
    P.rot_world('Head', rot(pitch=2.0 * br_l, yaw=3.0 * osc(t, 3.0)))
    for side in D.SIDES:
        s = D.sgn(side)
        P.rot_world(side + 'UpperArm', rot(pitch=-2.2 * br_l + 1.0 * sw * s, roll=-1.8 * br_l * s))
        P.rot_world(side + 'LowerArm', rot(pitch=-3.0 * br_ll))
        P.rot_world(side + 'Hand', rot(pitch=-1.0 * br_ll))
    legs_planted(P)
    cloth(P, sway=2.5 * br_ll + 1.5 * osc(t + 0.0, 3.0))
    return P.B


# ----------------------------------------------------------------- Walk
WALK_N = 28
WALK_T = WALK_N / FPS
WALK_STRIDE = 5.4 / D.SC          # 5.4 real studs per cycle -> nominalSpeed 4.63 studs/s
STANCE = 0.5
HEEL_OFF = 0.36
WALK_LIFT = 0.40


def walk_foot(sk, side, phase):
    """(ankle target, foot R, toe angle, planted point name or None, contact point)."""
    v = WALK_STRIDE
    yc = -0.5 * v * STANCE                      # ankle contact offset (forward of rest)
    if phase < STANCE:
        off = np.array([0.0, yc + v * phase, 0.0])
        pitch = 17.0 * smoothstep(HEEL_OFF, STANCE, phase) if phase > HEEL_OFF else 0.0
        an, R = foot_place(sk, side, off, pitch=pitch)
        planted = 'ankle' if phase <= HEEL_OFF else 'ball'
        return an, R, -pitch, planted, off
    u = (phase - STANCE) / (1 - STANCE)
    y0 = yc + v * STANCE
    e = u * u * (3 - 2 * u)
    off = np.array([0.0, y0 + (yc - y0) * e, 0.0])      # swing forward to the next contact
    pitch = 17.0 * (1 - smoothstep(0.0, 0.45, u)) - 8.0 * smoothstep(0.35, 0.75, u) * (1 - smoothstep(0.85, 1.0, u))
    lift = WALK_LIFT * math.sin(math.pi * u) ** 0.9
    an, R = foot_place(sk, side, off, pitch=pitch, lift=lift)
    toe = -pitch * (1 - smoothstep(0.0, 0.3, u)) + 8.0 * math.sin(math.pi * u)
    return an, R, toe, None, off


def walk_pose(sk, t):
    P = Poser(sk)
    ph = {'Left': (t / WALK_T) % 1.0, 'Right': (t / WALK_T + 0.5) % 1.0}
    c = 2 * math.pi * t / WALK_T
    bob = -0.30 - 0.10 * math.cos(2 * c)        # lowest on each heavy footfall
    P.trans_world('HumanoidRootPart', (0.20 * math.sin(c - 0.35), 0.0, bob))
    P.rot_world('HumanoidRootPart', rot(pitch=5.0, yaw=-8.0 * math.cos(c), roll=-4.0 * math.sin(c - 0.35)))
    P.rot_world('LowerTorso', rot(pitch=2.0, roll=1.0 * math.sin(c - 0.6)))
    P.rot_world('UpperTorso', rot(pitch=6.0 - 2.5 * math.cos(2 * c - 0.5), yaw=12.0 * math.cos(c - 0.25),
                                  roll=3.0 * math.sin(c - 0.8)))
    P.rot_world('Head', rot(pitch=-3.0 + 1.5 * math.cos(2 * c - 1.0), yaw=-5.0 * math.cos(c - 0.4),
                            roll=-1.5 * math.sin(c - 0.8)))
    for side in D.SIDES:
        s = D.sgn(side)
        # arm swings opposite its leg, the heavy fist trails (lag)
        sw = math.cos(c - 0.55) * (1.0 if side == 'Left' else -1.0)
        P.rot_world(side + 'UpperArm', rot(pitch=20.0 * sw, roll=-(9.0 + 2.0 * math.sin(2 * c)) * s))
        P.rot_world(side + 'LowerArm', rot(pitch=-(6.0 + 9.0 * max(0.0, -math.cos(c - 1.0) *
                                                                   (1.0 if side == 'Left' else -1.0)))))
        P.rot_world(side + 'Hand', rot(pitch=-3.0 * math.cos(c - 1.3) * (1.0 if side == 'Left' else -1.0)))
    planted = {}
    for side in D.SIDES:
        an, R, toe, pl, off = walk_foot(sk, side, ph[side])
        pole = P.pelvis_dir(sk.pole_leg[side])
        P.leg_ik(side, an, pole, R, toe)
        planted[side] = pl
    sway = 3.0 * math.sin(2 * c - 1.2)
    cloth(P, sway=sway)
    return P.B, planted


# ------------------------------------------------------------------ Hit
HIT_N = 11


def hit_pose(sk, t):
    T = tracks({
        'hip': [(0, (0, 0, 0)), (0.10, (0, 0.12, -0.07), 'out'), (0.25, (0, 0.03, -0.02)), (HIT_N / FPS, (0, 0, 0), 'ease')],
        'lt': [(0, (0, 0, 0)), (0.10, (-4, 0, 2), 'out'), (0.25, (1, 0, 0)), (HIT_N / FPS, (0, 0, 0), 'ease')],
        'ut': [(0, (0, 0, 0)), (0.10, (-11, 2, 4), 'out'), (0.25, (3, 0, 0)), (HIT_N / FPS, (0, 0, 0), 'ease')],
        'head': [(0, (0, 0, 0)), (0.125, (-15, -3, -6), 'out'), (0.27, (5, 0, 0)), (HIT_N / FPS, (0, 0, 0), 'ease')],
        'arm': [(0, (0, 0)), (0.125, (-9, 12), 'out'), (0.29, (3, -2)), (HIT_N / FPS, (0, 0), 'ease')],
    })
    P = Poser(sk)
    P.trans_world('HumanoidRootPart', T['hip'](t))
    lt, ut, hd = T['lt'](t), T['ut'](t), T['head'](t)
    P.rot_world('LowerTorso', rot(pitch=lt[0], roll=lt[1], yaw=lt[2]))
    P.rot_world('UpperTorso', rot(pitch=ut[0], roll=ut[1], yaw=ut[2]))
    P.rot_world('Head', rot(pitch=hd[0], roll=hd[1], yaw=hd[2]))
    a = T['arm'](t)
    for side in D.SIDES:
        s = D.sgn(side)
        P.rot_world(side + 'UpperArm', rot(pitch=a[0], roll=-(0.4 * abs(a[0]) + 4.0 * min(1.0, abs(a[0]) / 9.0)) * s))
        P.rot_world(side + 'LowerArm', rot(pitch=-max(0.0, a[1])))
    legs_planted(P)
    cloth(P, sway=-0.5 * a[0])
    return P.B


# ======================================================== attack helpers
def lerp(a, b, w):
    return np.asarray(a, float) + (np.asarray(b, float) - np.asarray(a, float)) * w


def slerp_dir(a, b, w):
    a, b = unit(a), unit(b)
    d = max(-1.0, min(1.0, float(a @ b)))
    om = math.acos(d)
    if om < 1e-5:
        return a
    return unit((math.sin((1 - w) * om) * a + math.sin(w * om) * b) / math.sin(om))


class KeyedArm:
    """IK targets/poles keyed in chest space or world space. Every key is
    converted to world at the current frame before interpolating, so a
    segment can run from a chest-space key to a ground (world) key cleanly."""

    def __init__(self, keys):
        # keys: (time, point, pole, space, mode, twist); mode = interpolation INTO that key
        self.keys = keys
        self.tw = Track([(k[0], [k[5]], k[4]) for k in keys])

    def eval(self, t, to_pt, to_dir):
        ks = self.keys
        n = len(ks)
        if t <= ks[0][0]:
            i, u = 0, 0.0
        elif t >= ks[-1][0]:
            i, u = n - 2, 1.0
        else:
            i = min(max(j for j in range(n) if ks[j][0] <= t), n - 2)
            u = (t - ks[i][0]) / (ks[i + 1][0] - ks[i][0])

        def P(j):
            return to_pt(np.asarray(ks[j][1], float)) if ks[j][3] == 'chest' else np.asarray(ks[j][1], float)

        def Dd(j):
            if isinstance(ks[j][2], str):
                return ks[j][2]
            return to_dir(np.asarray(ks[j][2], float)) if ks[j][3] == 'chest' else np.asarray(ks[j][2], float)

        def tan(j):
            if j == 0 or j == n - 1 or ks[j][4] != 'smooth' or ks[j + 1][4] != 'smooth':
                return np.zeros(3)
            return (P(j + 1) - P(j - 1)) / (ks[j + 1][0] - ks[j - 1][0])

        mode = ks[i + 1][4]
        a, b = P(i), P(i + 1)
        if mode == 'smooth':
            h = ks[i + 1][0] - ks[i][0]
            h00 = 2 * u ** 3 - 3 * u ** 2 + 1
            h10 = u ** 3 - 2 * u ** 2 + u
            h01 = -2 * u ** 3 + 3 * u ** 2
            h11 = u ** 3 - u ** 2
            pt = h00 * a + h10 * h * tan(i) + h01 * b + h11 * h * tan(i + 1)
            w = u * u * (3 - 2 * u)
        else:
            w = float(Track([(0, 0), (1, 1, mode)])(u)[0])
            pt = a + (b - a) * w
        return pt, (Dd(i), Dd(i + 1), w), float(self.tw(t)[0])


def auto_pole(P, side, pt, W):
    """Posterior of the elbow for a swing in the body's sagittal plane: it turns
    with the arm (back when hanging, down when the arm points forward, forward
    overhead), with a small outward flare, so the elbow never swivels."""
    sk = P.sk
    S = sk.frame_of(W, side + 'UpperArm')[:3, 3]
    d = unit(pt - S)
    lat = P.chest_dir(np.array([1.0, 0, 0]), W)
    back = P.chest_dir(np.array([0, 1.0, 0]), W)
    s = D.sgn(side)
    return unit(np.cross(lat, d) + 0.30 * s * lat + 0.20 * back)


def arm_from_keys(P, side, ka, t, end, W=None):
    W = P.W()
    pt, (pa, pb, w), tw = ka.eval(t, lambda q: P.chest_pt(q, W), lambda v: P.chest_dir(v, W))
    pa = auto_pole(P, side, pt, W) if isinstance(pa, str) else pa
    pb = auto_pole(P, side, pt, W) if isinstance(pb, str) else pb
    return P.arm_ik(side, pt, slerp_dir(pa, pb, w), end=end, twist=tw)


def rest_arm_keys(sk, side, end):
    p = {'wrist': rest_wrist(sk, side), 'fistcenter': rest_fistcenter(sk, side),
         'fistbottom': sk.head[side + 'Hand'] + D.hand_rest_dir(side) * sk.fist_bottom}[end]
    return p, sk.pole_arm[side]


# ------------------------------------------------------------- FistSlam
SLAM_N = 46
SLAM = {'warn': 4, 'top': 17, 'release': 19, 'over': 21, 'mid': 23, 'impact': 26, 'hold': 31, 'end': SLAM_N}


def slam_tracks(sk, ground_y=-2.9, fist_x=1.0, impact_z=0.0):
    f = lambda k: SLAM[k] / FPS
    body = tracks({
        'hip': [(0, (0, 0, 0)), (f('warn'), (0, 0.04, -0.14), 'ease'), (f('top'), (0, 0.10, -0.02), 'smooth'),
                (f('release'), (0, 0.12, -0.02), 'smooth'), (f('impact'), (0, -0.15, -0.84), 'in'),
                (f('impact') + 2 / FPS, (0, -0.155, -0.87), 'out'), (f('hold'), (0, -0.15, -0.85), 'ease'),
                (f('hold') + 7 / FPS, (0, -0.03, -0.35), 'smooth'), (f('end'), (0, 0, 0), 'ease')],
        'lt': [(0, (0, 0)), (f('warn'), (5, 0), 'ease'), (f('top'), (-6, 0), 'smooth'), (f('release'), (-7, 0), 'smooth'),
               (f('impact'), (20, 0), 'in'), (f('impact') + 2 / FPS, (22, 0), 'out'), (f('hold'), (20, 0), 'ease'),
               (f('hold') + 7 / FPS, (7, 0), 'smooth'), (f('end'), (0, 0), 'ease')],
        'ut': [(0, (0, 0)), (f('warn'), (6, 0), 'ease'), (f('top'), (-15, 0), 'smooth'),
               (f('release'), (-17, 0), 'smooth'), (f('impact'), (38, 0), 'in'), (f('impact') + 2 / FPS, (41, 0), 'out'),
               (f('hold'), (38, 0), 'ease'), (f('hold') + 7 / FPS, (12, 0), 'smooth'), (f('end'), (0, 0), 'ease')],
        'head': [(0, (0,)), (f('warn'), (4,), 'ease'), (f('top'), (-6,), 'smooth'), (f('release'), (-8,), 'smooth'),
                 (f('impact'), (-24,), 'in'), (f('hold'), (-20,), 'ease'), (f('end'), (0,), 'ease')],
        'cloth': [(0, (0,)), (f('top'), (-4,)), (f('impact'), (6,), 'in'), (f('impact') + 4 / FPS, (-5,)),
                  (f('hold') + 4 / FPS, (2,)), (f('end'), (0,), 'ease')],
    })
    arms = {}
    for side in D.SIDES:
        s = D.sgn(side)
        rp, rpole = rest_arm_keys(sk, side, 'fistbottom')
        top = np.array([1.95 * s, -0.05, 9.5])
        pre = np.array([4.0 * s, -2.1, 2.7])
        mid = np.array([1.9 * s, -3.0, 9.2])
        impact = np.array([fist_x * s, ground_y, impact_z])
        lift = np.array([fist_x * s * 1.6, ground_y + 0.6, 1.1])
        pole_top = np.array([0.35 * s, -0.85, 0.55])
        pole_imp = np.array([0.30 * s, 1.0, 0.25])
        arms[side] = KeyedArm([
            (0.0, rp, rpole, 'chest', 'smooth', 0.0),
            (f('warn'), pre, 'auto', 'chest', 'ease', 0.0),
            (f('top') - 6 / FPS, mid, 'auto', 'chest', 'smooth', 0.0),
            (f('top'), top, 'auto', 'chest', 'smooth', 0.0),
            (f('release'), top + np.array([0, 0.12, 0.10]), 'auto', 'chest', 'smooth', 0.0),
            (f('over'), np.array([1.5 * s, -3.05, 9.3]), 'auto', 'chest', 'smooth', 0.0),
            (f('mid'), np.array([1.15 * s, -4.1, 6.5]), 'auto', 'chest', 'smooth', 0.0),
            (f('impact'), impact, 'auto', 'world', 'in', 0.0),
            (f('hold'), impact + np.array([0, 0, 0.07]), 'auto', 'world', 'out', 0.0),
            (f('hold') + 7 / FPS, lift, 'auto', 'world', 'smooth', 0.0),
            (f('hold') + 12 / FPS, np.array([3.5 * s, -1.6, 2.3]), rpole, 'chest', 'smooth', 0.0),
            (f('end'), rp, rpole, 'chest', 'ease', 0.0)])
    return body, arms


def slam_pose(sk, t, body, arms):
    P = Poser(sk)
    h, lt, ut, hd = body['hip'](t), body['lt'](t), body['ut'](t), body['head'](t)
    P.trans_world('HumanoidRootPart', h)
    P.rot_world('LowerTorso', rot(pitch=lt[0]))
    P.rot_world('UpperTorso', rot(pitch=ut[0]))
    P.rot_world('Head', rot(pitch=hd[0]))
    legs_planted(P)
    reach = {}
    for side in D.SIDES:
        reach[side] = arm_from_keys(P, side, arms[side], t, 'fistbottom')
    cloth(P, sway=float(body['cloth'](t)[0]))
    return P.B, reach


# -------------------------------------------------------------- FistHook
HOOK_N = 31
HOOK = {'warn': 3, 'wind': 8, 'impact': 14, 'follow': 19, 'end': HOOK_N}


def hook_tracks(sk, z_imp=3.35, r_imp=4.9):
    f = lambda k: HOOK[k] / FPS
    body = tracks({
        'hip': [(0, (0, 0, 0)), (f('warn'), (-0.04, 0.02, -0.06), 'ease'), (f('wind'), (-0.22, 0.10, -0.30), 'smooth'),
                (f('impact'), (0.06, -0.12, -0.36), 'in'), (f('follow'), (0.20, -0.10, -0.30), 'out'),
                (f('end'), (0, 0, 0), 'ease')],
        'hipr': [(0, (0, 0)), (f('warn'), (0, -3), 'ease'), (f('wind'), (2, -20), 'smooth'), (f('impact') - 1 / FPS, (4, 6), 'in'),
                 (f('impact'), (5, 14), 'out'), (f('follow'), (4, 24), 'out'), (f('end'), (0, 0), 'ease')],
        'ut': [(0, (0, 0, 0)), (f('warn'), (2, -4, 0), 'ease'), (f('wind'), (6, -27, -4), 'smooth'),
               (f('impact'), (10, 16, 3), 'in'), (f('follow'), (12, 27, 5), 'out'), (f('end'), (0, 0, 0), 'ease')],
        'head': [(0, (0, 0)), (f('wind'), (4, 14), 'smooth'), (f('impact'), (2, -12), 'in'), (f('follow'), (0, -18), 'out'),
                 (f('end'), (0, 0), 'ease')],
        'larm': [(0, (0, 0)), (f('wind'), (-28, 30), 'smooth'), (f('impact'), (18, 8), 'in'), (f('follow'), (24, 10), 'out'),
                 (f('end'), (0, 0), 'ease')],
        'cloth': [(0, (0,)), (f('wind'), (-3,)), (f('impact'), (5,), 'in'), (f('follow') + 3 / FPS, (-3,)), (f('end'), (0,), 'ease')],
        'labd': [(0, (0,)), (f('wind'), (6,)), (f('follow'), (7,)), (f('follow') + 8 / FPS, (6,)), (f('end'), (0,), 'ease')],
    })
    rp, rpole = rest_arm_keys(sk, 'Right', 'fistcenter')
    pole = np.array([0.15, 0.55, -0.82])

    def arc(theta, R, z):
        th = math.radians(theta)
        return np.array([-0.3 + R * math.sin(th), -R * math.cos(th), z])
    keys = [(0.0, rp, rpole, 'world', 'smooth', 0.0),
            (f('warn'), rp + np.array([-0.25, 0.25, 0.25]), rpole, 'world', 'ease', 0.0)]
    # the swing follows the true arc frame by frame (no chords cutting inside it): windup -> impact accelerates,
    # follow-through decelerates; every target stays inside 96% reach
    w0, wi, wf = HOOK['wind'], HOOK['impact'], HOOK['follow']
    for fr in range(w0, wf + 1):
        if fr <= wi:
            u = (fr - w0) / (wi - w0)
            e = u ** 1.8
            th, R, z = -115 + 115 * e, 3.8 + (r_imp - 3.8) * (u * u * (3 - 2 * u)), z_imp + 0.4 * (1 - e)
            pole_k = unit(np.array([-0.25, 0.35, -0.9]) * (1 - e) + np.array([0.15, 0.55, -0.82]) * e)
            tw = 0.0
        else:
            u = (fr - wi) / (wf - wi)
            e = 1 - (1 - u) ** 2
            th, R, z = 12 * e, r_imp + 0.05 * e, z_imp - 0.15 * e
            pole_k = unit(np.array([0.15, 0.55, -0.82]) * (1 - e) + np.array([0.75, 0.15, -0.65]) * e)
            tw = 0.0
        mode = 'smooth' if fr != wi else 'linear'
        keys.append((fr / FPS, arc(th, R, z), pole_k, 'world', mode, tw))
    keys += [((wf + 4) / FPS, np.array([-2.1, -3.9, 5.8]), unit(np.array([-0.5, 0.2, -0.85])), 'chest', 'smooth', 0.0),
             ((wf + 8) / FPS, np.array([-4.0, -2.2, 3.6]), unit(np.array([-0.8, 0.3, -0.55])), 'chest', 'smooth', 0.0),
             (f('end'), rp, rpole, 'world', 'ease', 0.0)]
    hook = KeyedArm(keys)
    return body, hook


def hook_pose(sk, t, body, hook):
    P = Poser(sk)
    h, hr, ut, hd = body['hip'](t), body['hipr'](t), body['ut'](t), body['head'](t)
    P.trans_world('HumanoidRootPart', h)
    P.rot_world('HumanoidRootPart', rot(pitch=hr[0], yaw=hr[1]))
    P.rot_world('UpperTorso', rot(pitch=ut[0], yaw=ut[1], roll=ut[2]))
    P.rot_world('Head', rot(pitch=hd[0], yaw=hd[1]))
    la = body['larm'](t)
    P.rot_world('LeftUpperArm', rot(pitch=la[0], roll=-(0.42 * la[1] + 0.3 * abs(la[0]) + float(body['labd'](t)[0])), yaw=-0.3 * la[1]))
    P.rot_world('LeftLowerArm', rot(pitch=-0.9 * la[1]))
    legs_planted(P)
    reach = arm_from_keys(P, 'Right', hook, t, 'fistcenter')
    cloth(P, sway=float(body['cloth'](t)[0]))
    return P.B, reach


# ------------------------------------------------------------------ Roar
ROAR_N = 38
ROAR = {'chest': 5, 'pull1': 11, 'hit1': 13, 'pull2': 16, 'hit2': 19, 'spread': 25, 'hold': 30, 'end': ROAR_N}


def roar_tracks(sk, contact):
    f = lambda k: ROAR[k] / FPS
    body = tracks({
        'hip': [(0, (0, 0, 0)), (f('chest'), (0, 0.04, -0.02), 'ease'), (f('hit1'), (0, 0.02, -0.08), 'in'),
                (f('pull2'), (0, 0.03, -0.03)), (f('hit2'), (0, 0.02, -0.09), 'in'), (f('spread'), (0, 0.04, -0.02), 'out'),
                (f('hold'), (0, 0.04, -0.03)), (f('end'), (0, 0, 0), 'ease')],
        'ut': [(0, (0,)), (f('chest'), (-14,), 'ease'), (f('pull1'), (-11,)), (f('hit1'), (-6,), 'in'), (f('pull2'), (-12,)),
               (f('hit2'), (-6,), 'in'), (f('spread'), (-16,), 'out'), (f('hold'), (-15,)), (f('end'), (0,), 'ease')],
        'head': [(0, (0,)), (f('chest'), (-22,), 'ease'), (f('hit1'), (-16,)), (f('hit2'), (-18,)), (f('spread'), (-30,), 'out'),
                 (f('hold'), (-28,)), (f('end'), (0,), 'ease')],
        'cloth': [(0, (0,)), (f('chest'), (-3,)), (f('hit1'), (3,), 'in'), (f('hit2'), (3,), 'in'), (f('spread'), (-4,)),
                  (f('end'), (0,), 'ease')],
    })
    arms = {}
    for side in D.SIDES:
        s = D.sgn(side)
        rp, rpole = rest_arm_keys(sk, side, 'fistcenter')
        spread = np.array([3.9 * s, -0.6, 4.0])
        pull = np.array([1.7 * s, -3.15, 5.9])
        hit = contact[side]
        wide = np.array([3.6 * s, -1.0, 5.4])
        pole_out = unit(np.array([0.8 * s, 0.2, -0.55]))
        arms[side] = KeyedArm([
            (0.0, rp, rpole, 'chest', 'smooth', 0.0),
            (f('chest'), spread, unit(np.array([0.5 * s, 0.4, -0.75])), 'chest', 'ease', 0.0),
            (f('pull1'), pull, unit(np.array([0.6 * s, 0.1, -0.8])), 'chest', 'smooth', 0.0),
            (f('hit1'), hit, pole_out, 'chest', 'in', 0.0),
            (f('pull2'), pull, pole_out, 'chest', 'out', 0.0),
            (f('hit2'), hit, pole_out, 'chest', 'in', 0.0),
            (f('hit2') + 2 / FPS, pull + np.array([0.2 * s, 0.3, -0.1]), pole_out, 'chest', 'out', 0.0),
            (f('spread'), wide, unit(np.array([0.5 * s, 0.6, -0.6])), 'chest', 'out', 0.0),
            (f('hold'), wide + np.array([0.1 * s, 0.1, 0.1]), unit(np.array([0.5 * s, 0.6, -0.6])), 'chest', 'smooth', 0.0),
            (f('end'), rp, rpole, 'chest', 'ease', 0.0)])
    return body, arms


def roar_pose(sk, t, body, arms):
    P = Poser(sk)
    P.trans_world('HumanoidRootPart', body['hip'](t))
    P.rot_world('UpperTorso', rot(pitch=float(body['ut'](t)[0])))
    P.rot_world('Head', rot(pitch=float(body['head'](t)[0])))
    legs_planted(P)
    for side in D.SIDES:
        arm_from_keys(P, side, arms[side], t, 'fistcenter')
    cloth(P, sway=float(body['cloth'](t)[0]))
    return P.B


# ----------------------------------------------------------------- Death
DEATH_N = 53


def death_tracks():
    f = lambda x: x / FPS
    return tracks({
        # pelvis world offset; z is re-solved per frame so the body rests on the ground
        'hip': [(0, (0, 0, 0)), (f(5), (0.05, 0.30, -0.10), 'out'), (f(11), (-0.05, 0.40, -0.30)),
                (f(24), (0.0, 0.20, -1.45), 'in'), (f(27), (0.0, 0.15, -1.40), 'out'),
                (f(36), (0.0, -0.20, -1.50)), (f(46), (0.05, -1.00, -2.45), 'in'), (f(DEATH_N), (0.05, -1.05, -2.50), 'out')],
        'lt': [(0, (0, 0, 0)), (f(5), (-6, 2, 0), 'out'), (f(11), (4, -2, 4)), (f(24), (8, 0, 0), 'in'),
               (f(36), (34, 0, 0)), (f(46), (74, 2, 0), 'in'), (f(DEATH_N), (78, 2, 0), 'out')],
        'ut': [(0, (0, 0, 0)), (f(5), (-12, -3, 6), 'out'), (f(11), (10, 2, -4)), (f(24), (12, 0, 0), 'in'),
               (f(36), (26, 0, 0)), (f(46), (12, -4, 6), 'in'), (f(DEATH_N), (10, -5, 7), 'out')],
        'head': [(0, (0, 0)), (f(5), (-18, 8), 'out'), (f(11), (12, -6)), (f(24), (10, 0), 'in'), (f(36), (-12, 0)),
                 (f(46), (-34, 40), 'in'), (f(DEATH_N), (-36, 44), 'out')],
        # legs after the stagger (FK): thigh pitch in WORLD (+ = knee forward), knee flex, foot pitch (+ toe down)
        'thigh': [(f(11), (8,)), (f(24), (0,), 'in'), (f(36), (-4,)), (f(46), (-62,), 'in'), (f(DEATH_N), (-66,), 'out')],
        'knee': [(f(11), (24,)), (f(24), (92,), 'in'), (f(36), (94,)), (f(46), (70,), 'in'), (f(DEATH_N), (64,), 'out')],
        'foot': [(f(11), (6,)), (f(24), (42,), 'in'), (f(36), (44,)), (f(46), (30,)), (f(DEATH_N), (28,), 'out')],
        'cloth': [(0, (0,)), (f(5), (-6,)), (f(24), (8,), 'in'), (f(36), (-4,)), (f(46), (10,), 'in'), (f(DEATH_N), (14,), 'out')],
    })


DEATH_PLANT = 33      # fists reach the ground (frame) when he falls forward onto them


def death_arm_keys(sk, plant):
    """FK-like flail (chest space), then fists to the ground (world), then the
    arms give way and the fists slide out as he collapses."""
    f = lambda x: x / FPS
    arms = {}
    for side in D.SIDES:
        s = D.sgn(side)
        rp, rpole = rest_arm_keys(sk, side, 'fistbottom')
        flail = np.array([3.5 * s, -1.1, 2.5])
        hang = np.array([3.1 * s, -1.1, 1.7])
        reach = np.array([2.6 * s, -2.9, 2.8])
        out = plant[side] + np.array([1.25 * s, -0.35, 0.0])
        arms[side] = KeyedArm([
            (0.0, rp, rpole, 'chest', 'smooth', 0.0),
            (f(5), flail, unit(np.array([0.3 * s, 0.9, -0.3])), 'chest', 'out', 0.0),
            (f(14), hang, rpole, 'chest', 'smooth', 0.0),
            (f(26), reach, unit(np.array([0.4 * s, 0.9, -0.2])), 'chest', 'smooth', 0.0),
            (f(DEATH_PLANT), plant[side], unit(np.array([0.45 * s, 0.9, 0.1])), 'world', 'in', 0.0),
            (f(38), plant[side], unit(np.array([0.5 * s, 0.85, 0.15])), 'world', 'hold', 0.0),
            (f(48), out, unit(np.array([0.9 * s, 0.3, 0.4])), 'world', 'ease', 0.0),
            (f(DEATH_N), out + np.array([0.08 * s, -0.04, 0.0]), unit(np.array([0.9 * s, 0.3, 0.45])), 'world', 'out', 0.0)])
    return arms


def death_pose(sk, t, T, arms=None, lift=0.0):
    fr = t * FPS
    P = Poser(sk)
    h = T['hip'](t)
    P.trans_world('HumanoidRootPart', h + np.array([0, 0, lift]))
    lt, ut, hd = T['lt'](t), T['ut'](t), T['head'](t)
    P.rot_world('LowerTorso', rot(pitch=lt[0], roll=lt[1], yaw=lt[2]))
    P.rot_world('UpperTorso', rot(pitch=ut[0], roll=ut[1], yaw=ut[2]))
    P.rot_world('Head', rot(pitch=hd[0], yaw=hd[1]))
    offs = {'Left': np.zeros(3), 'Right': np.array([0.0, 0.55 * smoothstep(2, 9, fr), 0.0])}
    B_ik = {}
    if fr < 14:
        for side in D.SIDES:
            an, R = foot_place(sk, side, offs[side])
            if side == 'Right' and 2 < fr < 9:
                an = an + np.array([0, 0, 0.28 * math.sin(math.pi * (fr - 2) / 7)])
            P.leg_ik(side, an, P.pelvis_dir(sk.pole_leg[side]), R)
            for b in ('UpperLeg', 'LowerLeg', 'Foot', 'Toes'):
                B_ik[side + b] = P.B[side + b].copy()
    if fr > 11:
        w = smoothstep(11, 14, fr)
        th, kn, fp = float(T['thigh'](t)[0]), float(T['knee'](t)[0]), float(T['foot'](t)[0])
        for side in D.SIDES:
            P.rot_world(side + 'UpperLeg', rot(pitch=-th - lt[0], roll=4.0 * D.sgn(side)))
            P.B[side + 'LowerLeg'][:3, :3] = Rx(kn)
            P.B[side + 'Foot'][:3, :3] = rot_local_x(sk, side + 'Foot', fp)
            P.B[side + 'Toes'][:3, :3] = Rx(-min(fp, 35.0))
            if w < 1.0:
                for b in ('UpperLeg', 'LowerLeg', 'Foot', 'Toes'):
                    P.B[side + b][:3, :3] = slerp_R(B_ik[side + b][:3, :3], P.B[side + b][:3, :3], w)
    if arms is None:
        for side in D.SIDES:
            s = D.sgn(side)
            a = smoothstep(0, 6, fr)
            P.rot_world(side + 'UpperArm', rot(pitch=-14 * a, roll=10 * s * a))
            P.rot_world(side + 'LowerArm', rot(pitch=-18 * a))
    else:
        for side in D.SIDES:
            arm_from_keys(P, side, arms[side], t, 'fistbottom')
    cloth(P, sway=float(T['cloth'](t)[0]))
    return P


def rot_local_x(sk, name, deg):
    """Ankle pitch in the bone's own frame using the world X at rest as axis."""
    Rr = sk.rest[name][:3, :3]
    return Rr.T @ Rx(deg) @ Rr


def slerp_R(A, B, w):
    qa, qb = quat(A), quat(B)
    if qa @ qb < 0:
        qb = -qb
    d = max(-1.0, min(1.0, float(qa @ qb)))
    om = math.acos(d)
    if om < 1e-6:
        q = qa
    else:
        q = (math.sin((1 - w) * om) * qa + math.sin(w * om) * qb) / math.sin(om)
    q = q / np.linalg.norm(q)
    w_, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w_), 2 * (x * z + y * w_)],
                     [2 * (x * y + z * w_), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w_)],
                     [2 * (x * z - y * w_), 2 * (y * z + x * w_), 1 - 2 * (x * x + y * y)]])


# ---------------------------------------------------------------- Emerge
EMERGE_N = 62
EM = {'wake': 12, 'uncross': 18, 'guard': 26, 'step1': 16, 'step1e': 25, 'step2': 23, 'step2e': 37, 'release': 35,
      'step3': 35, 'step3e': 44, 'impact': 46, 'hold': 49, 'rise': 56, 'end': EMERGE_N}
R1_OFF = np.array([D.FEET_IN, D.COFFIN_START[1] + D.CAVITY['front'] + 0.72, D.CAVITY['floor']])   # onto the front lip


def emerge_controls(sk, coffin, plant):
    """Start: standing on the cavity floor (0.8 up), root 3.5 back, feet together,
    shoulders rolled forward and in (the cavity tapers), arms crossed, head bowed
    and turned away from the top fist. The fists stay in a narrow guard in front
    while any wide part is still between the side walls, then plant outside."""
    f = lambda k: EM[k] / FPS
    hy = coffin['hip_y']
    pro, shr = coffin.get('shp', (40.0, 10.0))
    yaw0, roll0 = coffin.get('head_yaw', 0.0), coffin.get('head_roll', 0.0)
    body = tracks({
        'hip': [(0, (0, hy, 0)), (f('wake'), (0, hy, 0.0), 'ease'), (f('uncross'), (0, hy * 0.6, -0.15), 'smooth'),
                (f('step2e'), (0, -0.1, -0.50), 'smooth'), (f('impact'), (0, -0.30, -0.74), 'in'),
                (f('hold'), (0, -0.30, -0.76), 'out'), (f('rise'), (0, 0.0, -0.10), 'smooth'), (f('end'), (0, 0, 0), 'ease')],
        'lt': [(0, (coffin['lt'], 0)), (f('wake'), (coffin['lt'], 0), 'ease'), (29 / FPS, (coffin['lt'], 0)),
               (f('step2e'), (8, 0)), (f('impact'), (22, 0), 'in'), (f('hold'), (24, 0), 'out'),
               (f('rise'), (4, 0)), (f('end'), (0, 0), 'ease')],
        'ut': [(0, (coffin['ut'], 0)), (f('wake'), (coffin['ut'], 0), 'ease'), (29 / FPS, (coffin['ut'], 0)),
               (f('step2e'), (10, 0)), (f('impact'), (30, 0), 'in'), (f('hold'), (32, 0), 'out'),
               (f('rise'), (6, 0)), (f('end'), (0, 0), 'ease')],
        'head': [(0, (coffin['head'], yaw0, roll0)), (f('wake'), (-4, yaw0, roll0), 'ease'),
                 (f('guard') + 6 / FPS, (-6, 0.3 * yaw0, 0.3 * roll0)),
                 (f('step2e'), (-10, -4, 0)), (f('impact'), (-26, 0, 0), 'in'), (f('hold'), (-24, 0, 0), 'out'),
                 (f('end'), (0, 0, 0), 'ease')],
        'shp': [(0, (pro, shr)), (f('release'), (pro * 0.85, shr * 0.8)), (f('release') + 7 / FPS, (0, 0), 'ease'),
                (f('end'), (0, 0), 'hold')],
        'cloth': [(0, (0,)), (f('step1e'), (6,)), (f('step2e'), (-5,)), (f('impact'), (7,), 'in'),
                  (f('rise'), (-3,)), (f('end'), (0,), 'ease')],
    })
    body['hy'] = hy
    arms = {}
    for side in D.SIDES:
        s = D.sgn(side)
        rp, rpole = rest_arm_keys(sk, side, 'fistcenter')
        c = coffin['arms'][side]
        top = side == coffin['top']
        lead = 2 / FPS if top else 0.0
        guard = np.array([1.20 * s, -3.5, 6.4]) if top else np.array([1.30 * s, -3.6, 5.3])
        gpole = unit(np.array([0.22 * s, 0.10, -0.97])) if top else unit(np.array([0.35 * s, -0.2, -0.9]))
        plant_pole = unit(np.array([0.3 * s, 1.0, 0.2]))
        if top:
            early = [(f('uncross') + lead, c['pt'] + np.array([0.3 * s, -1.6, 0.9]), c['pole'], 'chest', 'ease', 0.6 * c['twist']),
                     (f('guard') + lead, guard, gpole, 'chest', 'smooth', 0.0)]
        else:   # stays crossed (elbow inside the tapering walls) until the body is past the front plane
            early = [(22 / FPS, c['pt'] + np.array([0.30 * s, -0.80, -0.80]), unit(np.array([0.35 * s, -0.30, -0.89])), 'chest', 'smooth', c['twist']),
                     (31 / FPS, c['pt'] + np.array([0.85 * s, -1.45, -0.85]), unit(np.array([0.6 * s, -0.1, -0.8])), 'chest', 'smooth', c['twist']),
                     (33 / FPS, c['pt'] + np.array([1.20 * s, -1.90, -0.60]), unit(np.array([0.75 * s, -0.1, -0.65])), 'chest', 'smooth', 0.5 * c['twist']),
                     (35 / FPS, guard, gpole, 'chest', 'smooth', 0.0)]
        arms[side] = KeyedArm([
            (0.0, c['pt'], c['pole'], 'chest', 'smooth', c['twist']),
            (f('wake') + 2 / FPS, c['pt'] + np.array([0, -0.05, 0.05]), c['pole'], 'chest', 'ease', c['twist']),
            *early,
            ((f('release') if top else 37 / FPS), guard + np.array([0.5 * s, -0.6, -0.6]), gpole, 'chest', 'smooth', 0.0),
            (f('impact'), plant[side], plant_pole, 'world', 'in', 0.0),
            (f('hold'), plant[side] + np.array([0, 0, 0.18]), plant_pole, 'world', 'out', 0.0),
            (f('hold') + 3 / FPS, plant[side] + np.array([1.0 * s, 0.0, 1.6]), unit(np.array([0.4 * s, 1.0, 0.0])), 'world', 'smooth', 0.0),
            (f('rise') + 2 / FPS, rp + np.array([0.15 * s, -0.25, 0.25]), rpole, 'chest', 'smooth', 0.0),
            (f('end'), rp, rpole, 'chest', 'ease', 0.0)])
    return body, arms


def emerge_feet(sk, t, hy=0.0):
    """World foot offsets (from each foot's rest spot, final-spot space), swing
    lift and heel-off pitch. Feet start together on the cavity floor (z 0.8);
    a foot leaving the floor stays above the floor height until its heel has
    cleared the front lip, then steps down."""
    fr = t * FPS
    lip = D.COFFIN_START[1] + D.CAVITY['front']           # final-space y of the cavity's front plane
    heel_back = 0.88                                       # heel y relative to the foot offset

    def start(side):
        return np.array([D.FEET_IN * (1 if side == 'Right' else -1), D.COFFIN_START[1] + hy, D.CAVITY['floor']])

    def step(a, b, f0, f1, lift):
        if fr <= f0:
            return a.copy(), 0.0, 0.0
        if fr >= f1:
            return b.copy(), 0.0, 0.0
        u = (fr - f0) / (f1 - f0)
        e = u * u * (3 - 2 * u)
        p = a + (b - a) * e
        if a[2] > b[2] + 1e-6:
            # still above the cavity floor while the heel is behind the lip
            ue = 1.0
            for k in range(1, 201):
                uu = k / 200.0
                ee = uu * uu * (3 - 2 * uu)
                if a[1] + (b[1] - a[1]) * ee + heel_back <= lip - 0.05:
                    ue = uu
                    break
            # toes reach down first (heel stays above the lip), then the foot settles flat on the ground
            toe = 24.0 * smoothstep(0.35, ue, u) * (1 - smoothstep(ue, 1.0, u))
            pre = 0.30 * smoothstep(0.35, ue, u)
            p[2] = a[2] - pre if u <= ue else (a[2] - pre) + (b[2] - (a[2] - pre)) * smoothstep(ue, 1.0, u)
            return p, lift * math.sin(math.pi * u) ** 0.9, 16.0 * (1 - smoothstep(0.0, 0.5, u)) + toe
        return p, lift * math.sin(math.pi * u) ** 0.9, 16.0 * (1 - smoothstep(0.0, 0.5, u))

    def heel(f0, pre=4.0):
        return 10.0 * smoothstep(f0 - pre, f0, fr) if fr <= f0 else 0.0

    r, rl, rp = step(start('Right'), R1_OFF, EM['step1'], EM['step1e'], 0.45)
    rp = rp + heel(EM['step1'])
    if fr > EM['step3'] - 4:
        r, rl, rp = step(R1_OFF, np.zeros(3), EM['step3'], EM['step3e'], 0.25)
        rp = rp + heel(EM['step3'])
    l, ll, lp = step(start('Left'), np.zeros(3), EM['step2'], EM['step2e'], 0.5)
    lp = lp + heel(EM['step2'])
    return {'Left': (l, ll, lp), 'Right': (r, rl, rp)}


def emerge_pose(sk, t, body, arms):
    P = Poser(sk)
    legr = {}
    hy = body['hy']
    feet = emerge_feet(sk, t, hy)
    shift = hy * (1.0 - smoothstep(EM['step1'] / FPS, EM['step2e'] / FPS, t))
    root = 0.5 * (feet['Left'][0] + feet['Right'][0]) - np.array([0.0, shift, 0.0])
    root[0] = 0.0
    P.trans_world('Root', root)
    P.trans_world('HumanoidRootPart', body['hip'](t))
    lt, ut, hd = body['lt'](t), body['ut'](t), body['head'](t)
    P.rot_world('LowerTorso', rot(pitch=lt[0]))
    P.rot_world('UpperTorso', rot(pitch=ut[0]))
    P.rot_world('Head', rot(pitch=hd[0], yaw=hd[1], roll=hd[2]))
    pro, shr = body['shp'](t)
    P.sh_pre = {side: rot(yaw=-pro * D.sgn(side), roll=-shr * D.sgn(side)) for side in D.SIDES}
    for side in D.SIDES:
        off, lift, pitch = feet[side]
        an, R = foot_place(sk, side, off, pitch=pitch, lift=lift)
        legr[side] = P.leg_ik(side, an, P.pelvis_dir(sk.pole_leg[side]), R, toe=-pitch)
    reach = {'leg' + k: v for k, v in legr.items()}
    for side in D.SIDES:
        reach[side] = arm_from_keys(P, side, arms[side], t, 'fistcenter')
    cloth(P, sway=float(body['cloth'](t)[0]))
    return P.B, reach


def emerge_planted(sk, t, hy=0.0):
    feet = emerge_feet(sk, t, hy)
    out = {}
    for side in D.SIDES:
        off, lift, pitch = feet[side]
        moving = any(EM[a] < t * FPS < EM[b] for a, b in
                     ((('step1', 'step1e'), ('step3', 'step3e')) if side == 'Right' else (('step2', 'step2e'),)))
        if moving or lift > 1e-6:
            out[side] = None
        elif pitch > 1e-6:
            out[side] = 'ball'
        else:
            out[side] = 'ankle'
    return out
