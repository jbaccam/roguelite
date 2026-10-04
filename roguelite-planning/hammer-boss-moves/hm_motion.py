"""Hammer boss motion library (pure numpy; no Blender).

Space: Blender axes of the original model (Z up, -Y forward, +X = the boss's left), studs, template
scale 1.0. The ground is z = 0 and the HumanoidRootPart pivot (0, 0, 4.45) never moves; every pose is
a dict  part -> 4x4 "deformation" D  (rest-space point -> posed point), so the rest pose is all
identities and a part's CFrame relative to HumanoidRootPart is D @ rest centre.

Contents
  rotations / rigid transforms, quaternion slerp and Roblox's CFrame:Lerp
  curves: eases, keyed Hermite tracks with strike/hold segments, overshoot, settle, lag
  Rig: joints, lengths and hinge axes read from the model
  IK: one-axis knee hinge to a planted foot, one-axis elbow hinge with a swivel, the two-hand haft
      constraint (each hand = hammer * screw about the haft axis: slide + roll)
  ArmSolver: whole-clip (roll, swivel) planning per hand (dynamic programming on a grid, then a
      smoothing refinement), so the wrists stay straight and the elbows never pop
  client lerp: per-joint Motor6D Transform interpolation exactly as EnemyMotion.sample/blend do it
"""
import math

import numpy as np

DEG = math.pi / 180.0
ROOT = 'HumanoidRootPart'
# Motor6D tree of the template (child -> parent); pivots are the rest bone heads.
JOINTS = [('LowerTorso', ROOT), ('UpperTorso', 'LowerTorso'), ('Head', 'UpperTorso'),
          ('RightUpperArm', 'UpperTorso'), ('RightLowerArm', 'RightUpperArm'), ('RightHand', 'RightLowerArm'),
          ('LeftUpperArm', 'UpperTorso'), ('LeftLowerArm', 'LeftUpperArm'), ('LeftHand', 'LeftLowerArm'),
          ('RightUpperLeg', 'LowerTorso'), ('RightLowerLeg', 'RightUpperLeg'), ('RightFoot', 'RightLowerLeg'),
          ('LeftUpperLeg', 'LowerTorso'), ('LeftLowerLeg', 'LeftUpperLeg'), ('LeftFoot', 'LeftLowerLeg'),
          ('Hammer', ROOT)]
PARTS = [c for c, _ in JOINTS]
SIDES = ('Right', 'Left')


# =============================================================== rotations and rigid transforms
def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.where(n < 1e-12, 1.0, n)


def axis_angle(axis, deg):
    a = unit(axis)
    t = deg * DEG
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * (K @ K)


def axis_angle_batch(axis, rad):
    """Rotations about one fixed axis for an array of angles (radians): (n, 3, 3)."""
    a = unit(axis)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    s, c = np.sin(rad)[:, None, None], np.cos(rad)[:, None, None]
    return np.eye(3)[None] + s * K[None] + (1 - c) * (K @ K)[None]


def rx(d): return axis_angle((1, 0, 0), d)
def ry(d): return axis_angle((0, 1, 0), d)
def rz(d): return axis_angle((0, 0, 1), d)


def tf(R=None, t=None):
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = R
    if t is not None:
        M[:3, 3] = t
    return M


def tr(v): return tf(None, v)


def about(p, R):
    """4x4 rotation R about pivot p."""
    p = np.asarray(p, float)
    return tf(R, p - R @ p)


def rinv(M):
    R = M[:3, :3]
    return tf(R.T, -R.T @ M[:3, 3])


def xf(M, p):
    """Transform point(s) p (..., 3) by 4x4 M."""
    p = np.asarray(p, float)
    return p @ M[:3, :3].T + M[:3, 3]


def rot_angle(R):
    return math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(R) - 1) / 2))))


def frame_map(a_from, b_from, a_to, b_to):
    """Rotation taking direction a_from exactly onto a_to and b_from's part perpendicular to a_from onto
    b_to's part perpendicular to a_to."""
    def basis(a, b):
        x = unit(a)
        y = unit(b - x * (b @ x))
        return np.stack([x, y, np.cross(x, y)], 1)
    return basis(a_to, b_to) @ basis(a_from, b_from).T


def q_of(R):
    t = np.trace(R)
    if t > 0:
        s = math.sqrt(t + 1) * 2
        q = [0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s]
    else:
        i = int(np.argmax(np.diag(R)))
        if i == 0:
            s = math.sqrt(1 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
            q = [(R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s]
        elif i == 1:
            s = math.sqrt(1 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
            q = [(R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s]
        else:
            s = math.sqrt(1 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
            q = [(R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s]
    q = np.array(q)
    return q / np.linalg.norm(q)


def R_of(q):
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def slerp(q0, q1, t):
    if q0 @ q1 < 0:
        q1 = -q1
    d = float(np.clip(q0 @ q1, -1, 1))
    if d > 0.99995:
        q = q0 + (q1 - q0) * t
        return q / np.linalg.norm(q)
    th = math.acos(d)
    return (math.sin((1 - t) * th) * q0 + math.sin(t * th) * q1) / math.sin(th)


def cf_lerp(A, B, t):
    """Roblox CFrame:Lerp on 4x4 rigid transforms: linear position, shortest-arc slerp rotation."""
    return tf(R_of(slerp(q_of(A[:3, :3]), q_of(B[:3, :3]), t)), A[:3, 3] * (1 - t) + B[:3, 3] * t)


def swing_twist(R, axis):
    """(swing deg, signed twist deg) of rotation R about a unit axis."""
    a = unit(axis)
    swing = math.degrees(math.acos(max(-1.0, min(1.0, float(a @ (R @ a))))))
    q = q_of(R)
    p = a * (q[1:] @ a)
    tw = np.array([q[0], *p])
    n = np.linalg.norm(tw)
    if n < 1e-9:
        return swing, 180.0
    tw /= n
    twist = 2 * math.degrees(math.atan2(float(tw[1:] @ a), tw[0]))
    twist = (twist + 180) % 360 - 180
    return swing, twist


def hinge_metrics(R_rel, axis):
    """For a relative rotation that should be a hinge about `axis` (unit, parent rest frame):
    (signed hinge angle deg, off-axis deg) via a twist-swing split about the axis."""
    sw, tw = swing_twist(R_rel, axis)
    return tw, sw


# =============================================================== curves
def clamp01(u): return min(1.0, max(0.0, u))
def smooth(u): u = clamp01(u); return u * u * (3 - 2 * u)
def smoother(u): u = clamp01(u); return u * u * u * (u * (6 * u - 15) + 10)
def ease_in(u, p=2.0): return clamp01(u) ** p
def ease_out(u, p=2.0): return 1 - (1 - clamp01(u)) ** p


def hermite(p0, p1, m0, m1, u):
    u2, u3 = u * u, u * u * u
    return (2 * u3 - 3 * u2 + 1) * p0 + (u3 - 2 * u2 + u) * m0 + (-2 * u3 + 3 * u2) * p1 + (u3 - u2) * m1


class Track:
    """Keyed curve through (time, value[, mode]) keys; value may be a scalar or a vector.

    The mode on a key shapes the segment that LEAVES it:
      'spline' (default)  cubic Hermite; interior keys keep their velocity (Catmull-Rom tangents)
      'hold'              Hermite with zero velocity at both ends (an eased move or a held pose)
      'in'  / 'in3'       accelerate into the next key and hit it at full speed (u^2 / u^3): strikes
      'out'               fast start, decelerating into the next key
      'lin'               constant speed
    A key whose next segment is 'hold' or that ends a 'hold'/'out' segment has zero velocity, so a
    'spline' neighbour flows into it smoothly. `period` makes the tangents wrap (loops).
    """

    def __init__(self, keys, period=None):
        self.t = [float(k[0]) for k in keys]
        self.v = [np.asarray(k[1], float) for k in keys]
        self.mode = [k[2] if len(k) > 2 else 'spline' for k in keys]
        self.period = period
        n = len(keys)
        flat = [False] * n
        for i in range(n):
            if self.mode[i] in ('hold', 'in', 'in3'):
                flat[i] = True
            if i > 0 and self.mode[i - 1] in ('hold', 'out'):
                flat[i] = True
        self.m = []
        for i in range(n):
            if flat[i]:
                self.m.append(np.zeros_like(self.v[i]))
            elif 0 < i < n - 1:
                self.m.append((self.v[i + 1] - self.v[i - 1]) / (self.t[i + 1] - self.t[i - 1]))
            elif period is not None and n > 2:
                # wrap: last key == first key + period
                a, b = (self.v[1], self.t[1]), (self.v[-2], self.t[-2] - period)
                self.m.append((a[0] - b[0]) / (a[1] - b[1]))
            else:
                self.m.append(np.zeros_like(self.v[i]))

    def __call__(self, t):
        if self.period is not None:
            t = self.t[0] + (t - self.t[0]) % self.period
        if t <= self.t[0]:
            return self.v[0].copy()
        if t >= self.t[-1]:
            return self.v[-1].copy()
        i = max(k for k in range(len(self.t) - 1) if self.t[k] <= t)
        t0, t1 = self.t[i], self.t[i + 1]
        h = t1 - t0
        u = (t - t0) / h
        v0, v1 = self.v[i], self.v[i + 1]
        mode = self.mode[i]
        if mode == 'lin':
            return v0 + (v1 - v0) * u
        if mode == 'in':
            return v0 + (v1 - v0) * u * u
        if mode == 'in3':
            return v0 + (v1 - v0) * u * u * u
        if mode == 'out':
            return v0 + (v1 - v0) * (1 - (1 - u) ** 2)
        return hermite(v0, v1, self.m[i] * h, self.m[i + 1] * h, u)


def trapezoid(u, a=0.3, b=0.3):
    """Progress 0..1 over normalised time u with a smooth speed ramp up over [0, a], constant speed,
    and a smooth ramp down over [1-b, 1] (no speed bumps: even turning in the middle)."""
    u = clamp01(u)
    vmax = 1.0 / (1.0 - 0.5 * (a + b))
    # ramp shape: speed = vmax * smoothstep(u / a); its integral over [0, x] is vmax * a * I(x / a)
    I = lambda x: x ** 3 - 0.5 * x ** 4          # integral of 3x^2 - 2x^3
    if u < a:
        return vmax * a * I(u / a)
    pa = vmax * a * 0.5
    if u <= 1 - b:
        return pa + vmax * (u - a)
    pm = pa + vmax * (1 - b - a)
    x = (u - (1 - b)) / b
    return pm + vmax * b * (x - I(x))


class PathTrack:
    """Values along a path, keyed by path position s (0..1), traversed by a timing curve s(t).
    Keys are placed at s proportional to `weights` (e.g. each segment's turning angle), so the
    traversal speed follows the timing curve: even turning, no bumps at the keys."""

    def __init__(self, values, weights, t0, t1, a=0.3, b=0.3):
        acc = np.cumsum([0.0] + list(weights))
        s = acc / acc[-1]
        self.track = Track([(float(si), v) for si, v in zip(s, values)])
        self.t0, self.t1, self.a, self.b = t0, t1, a, b

    def __call__(self, t):
        return self.track(trapezoid((t - self.t0) / (self.t1 - self.t0), self.a, self.b))


def settle(t, amp, freq, zeta):
    """Damped oscillation starting at amplitude `amp` (a bounce or a jiggle after an impact)."""
    if t < 0:
        return 0.0
    w = 2 * math.pi * freq
    return amp * math.exp(-zeta * w * t) * math.cos(w * math.sqrt(max(1e-6, 1 - zeta * zeta)) * t)


def follow(times, target, freq=2.5, zeta=0.55, x0=None):
    """Second-order follower (spring-damper) of a sampled target signal: the trailing head or the
    hammer that settles a beat after the body. Semi-implicit Euler with 8 sub-steps per sample."""
    target = [np.asarray(v, float) for v in target]
    x = target[0].copy() if x0 is None else np.asarray(x0, float).copy()
    v = np.zeros_like(x)
    w = 2 * math.pi * freq
    out = [x.copy()]
    for k in range(1, len(times)):
        dt = (times[k] - times[k - 1]) / 8
        for j in range(8):
            a = (j + 1) / 8
            tg = target[k - 1] * (1 - a) + target[k] * a
            v += (w * w * (tg - x) - 2 * zeta * w * v) * dt
            x += v * dt
        out.append(x.copy())
    return out


# =============================================================== rig
class Rig:
    """Joint pivots, lengths, hinge axes and the hammer frame, read from the model (rig.json)."""

    def __init__(self, data):
        B = data['bones']
        self.head = {n: np.array(b['head'], float) for n, b in B.items()}
        self.tail = {n: np.array(b['tail'], float) for n, b in B.items()}
        self.center = {n: np.array(p['center'], float) for n, p in data['parts'].items()}
        self.pmin = {n: np.array(p['min'], float) for n, p in data['parts'].items()}
        self.pmax = {n: np.array(p['max'], float) for n, p in data['parts'].items()}
        self.pivot = {c: self.head[c] for c, _ in JOINTS}
        self.parent = dict(JOINTS)
        # hammer: head centre O, haft axis A (head -> butt), hammer-local frame HT (x along the haft)
        self.HO = self.head['Hammer'].copy()
        self.HA = unit(self.tail['Hammer'] - self.head['Hammer'])
        y = np.array([0.0, 1.0, 0.0])
        y = unit(y - self.HA * (y @ self.HA))
        self.HR = np.stack([self.HA, y, np.cross(self.HA, y)], 1)     # hammer-local -> rest world
        self.grip_rest = {s: float((self.head[s + 'Hand'] - self.HO) @ self.HA) for s in SIDES}
        # hammer geometry in hammer-local coordinates (measured from the mesh, see README)
        self.head_box = (np.array([-1.555, -1.268, -2.21]), np.array([1.555, 1.155, 2.21]))
        self.shaft = (1.555, 8.575, 0.45)      # x from, x to, max radius (iron bands)
        self.hole_half = 0.8                   # half the fist width along the haft
        # arms
        self.arm = {}
        for s in SIDES:
            a0, e0, w0 = self.head[s + 'UpperArm'], self.head[s + 'LowerArm'], self.head[s + 'Hand']
            ua, fa = e0 - a0, w0 - e0
            l1, l2 = np.linalg.norm(ua), np.linalg.norm(fa)
            h = unit(np.cross(ua, fa))
            u = unit(w0 - a0)
            perp = (e0 - a0) - u * ((e0 - a0) @ u)
            self.arm[s] = dict(s0=a0, e0=e0, w0=w0, l1=l1, l2=l2, h=h, ua=unit(ua), fa=unit(fa),
                               flex0=math.degrees(math.acos(np.clip(unit(ua) @ unit(fa), -1, 1))),
                               pole=unit(perp))
        # legs: knee hinge about the pelvis X axis (bends forward only)
        self.leg = {}
        for s in SIDES:
            h0, k0, a0 = self.head[s + 'UpperLeg'], self.head[s + 'LowerLeg'], self.head[s + 'Foot']
            self.leg[s] = dict(h0=h0, k0=k0, a0=a0, a=k0 - h0, b=a0 - k0, axis=np.array([1.0, 0, 0]),
                               l1=np.linalg.norm(k0 - h0), l2=np.linalg.norm(a0 - k0))
        # foot block (sole at z = 0) from the mesh bounds
        self.foot_box = {s: (self.pmin[s + 'Foot'], self.pmax[s + 'Foot']) for s in SIDES}

    # ---- hammer helpers
    def hammer_pose(self, R_world, ref_world, ref_x):
        """D of the hammer whose local axes are R_world (hammer-local -> world) and whose haft point
        at local x = ref_x sits at ref_world."""
        R = R_world @ self.HR.T
        p_rest = self.HO + self.HA * ref_x
        return tf(R, np.asarray(ref_world, float) - R @ p_rest)

    def haft_point(self, D_ham, x):
        return xf(D_ham, self.HO + self.HA * x)

    def screw(self, side, g, roll_deg):
        """Hand pose relative to the hammer: slide to grip g, roll about the haft."""
        return tr(self.HA * (g - self.grip_rest[side])) @ about(self.HO, axis_angle(self.HA, roll_deg))

    def hand_pose(self, D_ham, side, g, roll_deg):
        return D_ham @ self.screw(side, g, roll_deg)


def hammer_R(yaw=0.0, pitch=0.0, roll=0.0):
    """Hammer-local -> world rotation. Canonical (0, 0, 0): head straight ahead of the boss, haft
    level pointing back at him (local x = +Y), striking face local -z facing the ground. pitch turns
    about the world X axis (positive lifts the butt end / drops the head), yaw about Z, roll about the
    haft. The template rest is (yaw -90, pitch 13, roll 0)."""
    F0 = np.array([[0, -1.0, 0], [1.0, 0, 0], [0, 0, 1.0]])   # columns: local x->+Y, y->-X, z->+Z
    return rz(yaw) @ rx(pitch) @ F0 @ rx(roll)


# =============================================================== IK
def leg_ik(rig, side, D_pelvis, D_foot, knee_out=0.0):
    """Thigh and shin D for a hip carried by the pelvis and an ankle carried by the foot. One knee
    axis (the rest X axis in thigh space): returns (D_thigh, D_shin, knee_deg, reach_error)."""
    L = rig.leg[side]
    H = xf(D_pelvis, L['h0'])
    A = xf(D_foot, L['a0'])
    dist = np.linalg.norm(A - H)
    a, b, ax = L['a'], L['b'], L['axis']

    def reach(phi):
        return np.linalg.norm(a + axis_angle(ax, phi) @ b)
    lo, hi = 0.0, 160.0
    err = 0.0
    if dist >= reach(lo):
        phi = lo
        err = dist - reach(lo)
    elif dist <= reach(hi):
        phi = hi
        err = reach(hi) - dist
    else:
        for _ in range(60):
            mid = (lo + hi) / 2
            if reach(mid) > dist:
                lo = mid
            else:
                hi = mid
        phi = (lo + hi) / 2
    v_rest = a + axis_angle(ax, phi) @ b
    # the knee axis tracks the pelvis turned part-way toward the foot, plus a little splay
    Rp, Rf = D_pelvis[:3, :3], D_foot[:3, :3]
    s = -1 if side == 'Right' else 1
    want = unit(Rp @ ax + Rf @ ax)
    want = rz(-s * knee_out) @ want
    Rt = frame_map(v_rest, ax, A - H, want)
    Rs = Rt @ axis_angle(ax, phi)
    K = H + Rt @ a
    D_t = tf(Rt, H - Rt @ L['h0'])
    D_s = tf(Rs, K - Rs @ L['k0'])
    return D_t, D_s, phi, err


def arm_eval(rig, side, D_chest, D_ham, g, rolls, swivels):
    """Vectorised arm solve over a grid of hand rolls (deg, shape nr) x elbow swivels (deg, ns).
    Returns a dict of (nr, ns) arrays: ok (reachable within the hinge), flex, bend, twist, plus the
    elbow points and the rotations needed to build the pose."""
    A = rig.arm[side]
    rolls = np.atleast_1d(np.asarray(rolls, float))
    swivels = np.atleast_1d(np.asarray(swivels, float))
    nr, ns = len(rolls), len(swivels)
    Rc = D_chest[:3, :3]
    S = xf(D_chest, A['s0'])
    # hands for every roll
    Rroll = axis_angle_batch(rig.HA, rolls * DEG)                                  # (nr,3,3)
    slide = rig.HA * (g - rig.grip_rest[side])
    w_local = (Rroll @ (A['w0'] - rig.HO)) + rig.HO + slide                         # rest-hammer space
    W = w_local @ D_ham[:3, :3].T + D_ham[:3, 3]                                    # (nr,3)
    R_hand = D_ham[:3, :3][None] @ Rroll                                            # (nr,3,3)
    v = W - S
    L = np.linalg.norm(v, axis=1)
    u = v / L[:, None]
    l1, l2 = A['l1'], A['l2']
    c = np.clip((L * L - l1 * l1 - l2 * l2) / (2 * l1 * l2), -1, 1)
    flex = np.degrees(np.arccos(c))                                                 # 0 = straight
    along = (l1 * l1 - l2 * l2 + L * L) / (2 * L)
    height = np.sqrt(np.maximum(0, l1 * l1 - along * along))
    p = Rc @ A['pole']
    nref = p[None] - u * (u @ p)[:, None]
    nref = unit(nref)
    bref = np.cross(u, nref)
    sw = swivels * DEG
    n = np.cos(sw)[None, :, None] * nref[:, None] + np.sin(sw)[None, :, None] * bref[:, None]   # (nr,ns,3)
    E = S[None, None] + u[:, None] * along[:, None, None] + n * height[:, None, None]
    ac = unit(E - S)
    fc = unit(W[:, None] - E)
    hc = unit(np.cross(n, np.broadcast_to(u[:, None], n.shape)))                   # n x u
    # R_upper maps (ua, h, ua x h) -> (ac, hc, ac x hc)
    Bt = np.stack([ac, hc, np.cross(ac, hc)], -1)                                    # (nr,ns,3,3)
    Br = np.stack([A['ua'], A['h'], np.cross(A['ua'], A['h'])], 1)
    Ru = Bt @ Br.T
    dflex = flex - A['flex0']
    Rh = axis_angle_batch(A['h'], dflex * DEG)                                       # (nr,3,3)
    Rf = Ru @ Rh[:, None]
    Rw = np.swapaxes(Rf, -1, -2) @ R_hand[:, None]                                   # forearm -> hand
    b = A['fa']
    Rb = Rw @ b
    bend = np.degrees(np.arccos(np.clip(Rb @ b, -1, 1)))
    # twist about the forearm axis (swing-twist): angle of the remaining rotation about b
    # take an orthogonal vector e, remove the swing, and measure its turn about b
    e = unit(np.cross(b, np.array([0.0, 0, 1.0]) if abs(b[2]) < 0.9 else np.array([1.0, 0, 0])))
    Re = Rw @ e
    # swing that takes Rb back onto b
    cross = np.cross(Rb, b)
    sn = np.linalg.norm(cross, axis=-1)
    k = cross / np.where(sn < 1e-9, 1, sn)[..., None]
    ang = np.arctan2(sn, np.clip(Rb @ b, -1, 1))
    # Rodrigues on Re about k by ang
    cosA, sinA = np.cos(ang)[..., None], np.sin(ang)[..., None]
    Re2 = Re * cosA + np.cross(k, Re) * sinA + k * (np.sum(k * Re, -1, keepdims=True)) * (1 - cosA)
    twist = np.degrees(np.arctan2(np.sum(np.cross(e, Re2) * b, -1), np.clip(Re2 @ e, -1, 1)))
    ok = (flex >= 12.0) & (flex <= 130.0)
    return dict(ok=np.broadcast_to(ok[:, None], (nr, ns)), flex=np.broadcast_to(flex[:, None], (nr, ns)),
                bend=bend, twist=twist, E=E, W=W, S=S, Ru=Ru, Rf=Rf, R_hand=R_hand, L=L,
                swivel=np.broadcast_to(swivels[None], (nr, ns)))


def arm_pose(rig, side, D_chest, D_ham, g, roll, swivel):
    """(D_upper, D_fore, D_hand, metrics) for one roll / swivel."""
    A = rig.arm[side]
    r = arm_eval(rig, side, D_chest, D_ham, g, [roll], [swivel])
    Ru, Rf = r['Ru'][0, 0], r['Rf'][0, 0]
    S, E = r['S'], r['E'][0, 0]
    D_u = tf(Ru, S - Ru @ A['s0'])
    D_f = tf(Rf, E - Rf @ A['e0'])
    D_h = rig.hand_pose(D_ham, side, g, roll)
    m = {k: float(r[k][0, 0]) for k in ('flex', 'bend', 'twist')}
    m['ok'] = bool(r['ok'][0, 0])
    return D_u, D_f, D_h, m


# =============================================================== whole-clip arm planning
class ArmPlan:
    """Plans (roll, swivel) per frame for one hand over a clip.

    Local cost (per frame): wrist bend and twist (rest-relative, degrees), elbow swivel, soft limit
    walls (bend 30, twist 30, swivel 68, flex 16..126) and a forearm-vs-belly core term. The path cost
    adds the squared per-frame change, so the elbow plane and the hand's roll on the haft move
    smoothly: no pops. Solved by dynamic programming on a 3-degree grid, then refined on a fine grid
    with neighbours fixed (Gauss-Seidel), with optional fixed start/end states (Idle frame 0)."""

    ROLLS = np.arange(-180.0, 180.01, 3.0)
    SWIV = np.arange(-72.0, 72.01, 3.0)

    def __init__(self, rig, side, smooth_w=1.0, max_step=21.0, core=None):
        self.rig, self.side = rig, side
        self.w = smooth_w
        self.max_step = max_step
        self.core = core

    def local(self, D_chest, D_ham, g, rolls, swivels, extra=None):
        r = arm_eval(self.rig, self.side, D_chest, D_ham, g, rolls, swivels)
        bend, twist, flex = r['bend'], r['twist'], r['flex']
        sw = r['swivel']
        c = bend ** 2 + 0.6 * twist ** 2 + 0.01 * sw ** 2
        c = c + 400 * np.maximum(0, bend - 30) ** 2 + 400 * np.maximum(0, np.abs(twist) - 30) ** 2
        c = c + 400 * np.maximum(0, np.abs(sw) - 68) ** 2
        c = c + 400 * np.maximum(0, 16 - flex) ** 2 + 400 * np.maximum(0, flex - 126) ** 2
        if self.core is not None:
            c = c + self.core(D_chest, r)
        if extra is not None:
            c = c + extra(D_chest, D_ham, g, r)
        c = np.where(r['ok'], c, 1e9)
        return c

    def plan(self, frames, start=None, end=None, periodic=False, extra=None):
        """frames: list of (D_chest, D_ham, g). start/end: fixed (roll, swivel) or None. periodic:
        the frames are one loop (last frame == first excluded); planned over two laps, the second
        lap kept, then refined with wrapped neighbours."""
        if periodic:
            n = len(frames)
            two = self.plan(frames + frames, None, None, False, extra)
            states = two[n:].copy()
            return self.refine(frames, states, None, None, True, extra)
        R, Sv = self.ROLLS, self.SWIV
        nr, ns = len(R), len(Sv)
        K = len(frames)
        costs = [self.local(D_c, D_h, g, R, Sv, extra) for D_c, D_h, g in frames]
        step = int(round(self.max_step / 3.0))
        offs = [(dr, ds) for dr in range(-step, step + 1) for ds in range(-step, step + 1)]
        INF = 1e18

        def run(first_cost):
            acc = first_cost.copy()
            back = []
            for k in range(1, K):
                best = np.full((nr, ns), INF)
                arg = np.zeros((nr, ns, 2), int)
                for dr, ds in offs:
                    # state (i, j) at k comes from (i - dr, j - ds) at k - 1
                    src = np.full((nr, ns), INF)
                    i0, i1 = max(0, dr), nr + min(0, dr)
                    j0, j1 = max(0, ds), ns + min(0, ds)
                    src[i0:i1, j0:j1] = acc[i0 - dr:i1 - dr, j0 - ds:j1 - ds]
                    tc = self.w * 9.0 * (dr * dr + ds * ds)
                    cand = src + tc
                    m = cand < best
                    best = np.where(m, cand, best)
                    arg[m] = (dr, ds)
                acc = best + costs[k]
                back.append(arg)
            return acc, back

        def first(fixed):
            fc = costs[0].copy()
            if fixed is not None:
                i = int(np.argmin(np.abs(R - fixed[0])))
                j = int(np.argmin(np.abs(Sv - fixed[1])))
                mask = np.full((nr, ns), INF)
                mask[i, j] = 0
                fc = fc + mask
            return fc

        acc, back = run(first(start))
        if end is not None:
            i = int(np.argmin(np.abs(R - end[0])))
            j = int(np.argmin(np.abs(Sv - end[1])))
            pen = np.full((nr, ns), INF)
            pen[i, j] = 0
            acc = acc + pen
        idx = np.unravel_index(int(np.argmin(acc)), acc.shape)
        path = [idx]
        for arg in reversed(back):
            i, j = path[-1]
            dr, ds = arg[i, j]
            path.append((i - dr, j - ds))
        path.reverse()
        states = np.array([[R[i], Sv[j]] for i, j in path], float)
        if start is not None:
            states[0] = start
        if end is not None:
            states[-1] = end
        return self.refine(frames, states, start, end, periodic, extra)

    def refine(self, frames, states, start, end, periodic, extra, sweeps=6):
        K = len(frames)
        fine = np.arange(-2.0, 2.01, 0.5)
        lam = self.w
        for sweep in range(sweeps):
            for k in range(K):
                if (k == 0 and start is not None) or (k == K - 1 and end is not None):
                    continue
                D_c, D_h, g = frames[k]
                r0, s0 = states[k]
                rr, ss = r0 + fine, s0 + fine
                c = self.local(D_c, D_h, g, rr, ss, extra)
                nb = []
                if k > 0:
                    nb.append(states[k - 1])
                elif periodic:
                    nb.append(states[K - 1])
                if k < K - 1:
                    nb.append(states[k + 1])
                elif periodic:
                    nb.append(states[0])
                for q in nb:
                    c = c + lam * ((rr[:, None] - q[0]) ** 2 + (ss[None, :] - q[1]) ** 2)
                # curvature: keep second differences small (fluid, not linear steps)
                i, j = np.unravel_index(int(np.argmin(c)), c.shape)
                states[k] = (rr[i], ss[j])
        return states


# =============================================================== pose assembly
def compose(rig, body, hammer, slides, arm_states, feet, knee_out=6.0):
    """Full pose from body parts (LowerTorso, UpperTorso, Head), the hammer D, slides and arm states
    {side: (roll, swivel)} and feet D. Returns (pose dict, diagnostics)."""
    P = {ROOT: np.eye(4), 'Hammer': hammer}
    P.update(body)
    diag = {}
    for s in SIDES:
        Dt, Ds, knee, err = leg_ik(rig, s, body['LowerTorso'], feet[s], knee_out)
        P[s + 'UpperLeg'], P[s + 'LowerLeg'], P[s + 'Foot'] = Dt, Ds, feet[s]
        diag['knee_' + s] = knee
        diag['legerr_' + s] = err
        roll, sw = arm_states[s]
        Du, Df, Dh, m = arm_pose(rig, s, body['UpperTorso'], hammer, slides[s], roll, sw)
        P[s + 'UpperArm'], P[s + 'LowerArm'], P[s + 'Hand'] = Du, Df, Dh
        diag['arm_' + s] = m
    return P, diag


def body_parts(rig, pelvis_t, pelvis_rot, chest_rot, head_rot):
    """LowerTorso / UpperTorso / Head D from a pelvis offset + rotation (about the pelvis pivot) and
    local rotations about the waist and the neck."""
    D_lt = tr(pelvis_t) @ about(rig.pivot['LowerTorso'], pelvis_rot)
    D_ut = D_lt @ about(rig.pivot['UpperTorso'], chest_rot)
    D_hd = D_ut @ about(rig.pivot['Head'], head_rot)
    return {'LowerTorso': D_lt, 'UpperTorso': D_ut, 'Head': D_hd}


def euler(pitch=0.0, roll=0.0, yaw=0.0):
    """Body rotation: yaw (Z) then roll (forward axis -Y) then pitch (X; positive pitches forward)."""
    return rz(yaw) @ axis_angle((0, -1, 0), roll) @ rx(pitch)


# =============================================================== client lerp (EnemyMotion)
def joint_locals(rig, P):
    """Motor6D.Transform of every joint (Blender axes): T(-q) * D_parent^-1 * D_child * T(q)."""
    out = {}
    for c, p in JOINTS:
        q = rig.pivot[c]
        out[c] = tr(-q) @ rinv(P[p]) @ P[c] @ tr(q)
    return out


def from_locals(rig, L):
    P = {ROOT: np.eye(4)}
    for c, p in JOINTS:
        q = rig.pivot[c]
        P[c] = P[p] @ tr(q) @ L[c] @ tr(-q)
    return P


def lerp_pose(rig, PA, PB, t, LA=None, LB=None):
    LA = LA or joint_locals(rig, PA)
    LB = LB or joint_locals(rig, PB)
    return from_locals(rig, {c: cf_lerp(LA[c], LB[c], t) for c in LA})


# =============================================================== Studio mapping
C_STUDIO = np.array([[-1.0, 0, 0], [0, 0, 1.0], [0, 1.0, 0]])   # Blender (x, y, z) -> Studio (-x, z, y)


def studio_pose(rig, P, part):
    """The part's CFrame relative to HumanoidRootPart, Studio axes: 12 numbers (x, y, z, R00..R22)."""
    D = P[part]
    c = xf(D, rig.center[part]) - rig.head[ROOT]
    pos = C_STUDIO @ c
    R = C_STUDIO @ D[:3, :3] @ C_STUDIO.T
    return [*pos, *R.flatten()]
