"""Procedural attack motion for the Frost Cyclops (pure numpy, 30 fps).

Every frame is generated from a small set of animation parameters and then
keyed densely in Blender, so what is checked here is exactly what is exported.

Club attacks (GroundSlam, IceSpikes) treat the right arm and the club as one
lever in a near-vertical SWING PLANE through the shoulder:
  theta  arm angle in the plane (0 = forward horizontal, +90 = straight up,
         >90 = up and behind the head, <0 = forward-down)
  flex   elbow flexion (deg); the elbow bends only in the swing plane and
         points to the extensor side (never laterally)
  psi    wrist deviation in the plane (deg, + = ulnar, the club tips toward the
         arm line), bounded to +-20
The hand keeps the palm facing the body (back of the hand outward) so the
haft lies in the swing plane; fingers and club are rigid children of the hand,
so the grip can not open. The torso crouches/leans/twists with both feet
pinned by two-bone leg IK.

Stomp uses a hinge-only leg IK (shared knee axis for thigh and shin, no twist)
and pins the standing (right) foot.
"""
import math

import numpy as np

import fc_design as D
import fc_parts as FP
import fc_pose as PO
from fc_sdf import axis_angle

FPS = 30
UP = np.array([0, 0, 1.0])
ARM_L = None


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def ease_in(t, p=2.2):
    t = min(1.0, max(0.0, t))
    return t ** p


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_params(A, B, t):
    return {k: (lerp(np.asarray(A[k], float), np.asarray(B[k], float), t) if k in B else A[k]) for k in A}


# ------------------------------------------------------------ quaternions
def m2q(R):
    t = np.trace(R)
    if t > 0:
        s = math.sqrt(t + 1) * 2
        return np.array([0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s])
    i = int(np.argmax(np.diag(R)))
    if i == 0:
        s = math.sqrt(1 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        return np.array([(R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s])
    if i == 1:
        s = math.sqrt(1 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        return np.array([(R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s])
    s = math.sqrt(1 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
    return np.array([(R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s])


def q2m(q):
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def slerp(qa, qb, t):
    if qa @ qb < 0:
        qb = -qb
    d = float(np.clip(qa @ qb, -1, 1))
    if d > 0.9995:
        q = qa + (qb - qa) * t
        return q / np.linalg.norm(q)
    th = math.acos(d)
    return (math.sin((1 - t) * th) * qa + math.sin(t * th) * qb) / math.sin(th)


def local_of(sk, P):
    L = {}
    for b in sk.order:
        par = sk.parent[b]
        if par:
            L[b] = np.linalg.inv(sk.rest[b]) @ sk.rest[par] @ np.linalg.inv(P.m[par]) @ P.m[b]
        else:
            L[b] = np.linalg.inv(sk.rest[b]) @ P.m[b]
    return L


def compose(sk, L):
    M = {}
    for b in sk.order:
        par = sk.parent[b]
        M[b] = (M[par] @ np.linalg.inv(sk.rest[par]) @ sk.rest[b] @ L[b]) if par else sk.rest[b] @ L[b]
    return M


def blend(sk, PA, PB, t):
    """Per-bone local slerp between two poses (what Blender's quaternion keys do)."""
    LA, LB = local_of(sk, PA), local_of(sk, PB)
    L = {}
    for b in sk.order:
        M = np.eye(4)
        M[:3, :3] = q2m(slerp(m2q(LA[b][:3, :3]), m2q(LB[b][:3, :3]), t))
        M[:3, 3] = LA[b][:3, 3] * (1 - t) + LB[b][:3, 3] * t
        L[b] = M
    P = PO.Pose(sk)
    P.m = compose(sk, L)
    return P


# ------------------------------------------------------------ body setup
def body(sk, prm):
    """Torso/legs/left arm/head from parameters, both feet pinned (REF stance)."""
    P = PO.Pose(sk)
    fwd = np.array([0, -1.0, 0])
    right = np.array([-1.0, 0, 0])
    P.move('HumanoidRootPart', np.asarray(prm.get('shift', (0, 0, 0)), float) + np.array([0, 0, -float(prm['drop'])]))
    P.rot('LowerTorso', right, -float(prm['lean']) * 0.35)
    P.rot('UpperTorso', right, -float(prm['lean']) * 0.65)
    P.rot('UpperTorso', UP, float(prm['twist']))
    P.rot('LowerTorso', fwd, float(prm.get('side', 0.0)))
    for side in ('Right', 'Left'):
        P.plant_leg(side)
    X = np.array([1.0, 0, 0])
    Y = np.array([0, 1.0, 0])
    la = prm.get('larm', (0, 0, 0))
    P.rot('LeftUpperArm', X, float(la[0]))
    P.rot('LeftUpperArm', Y, float(la[1]))
    P.rot_local('LeftLowerArm', [1, 0, 0], float(la[2]))
    P.rot('Head', X, float(prm.get('head', 0.0)))
    P.rot_local('Jaw', [1, 0, 0], float(prm.get('jaw', 0.0)))
    P.rot('Mantle_R', Y, float(prm.get('mantle', 0.0)))
    P.rot('Mantle_L', Y, -float(prm.get('mantle', 0.0)) * 0.5)
    P.rot_local('Belly', [1, 0, 0], float(prm.get('belly', 0.0)))
    return P


def set_bone_frame(P, b, head, y, x_hint):
    """Replace bone b's matrix (head, +Y along y, +X toward x_hint) and carry
    its descendants rigidly."""
    y = D._unit(y)
    x = np.asarray(x_hint, float)
    x = D._unit(x - y * (x @ y))
    z = np.cross(x, y)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = x, y, z, head
    G = M @ np.linalg.inv(P.m[b])
    for d in P.descendants(b):
        P.m[d] = G @ P.m[d]


def arm_lever(P, sk, n_out, theta, flex, psi, roll=0.0):
    """Pose the right arm + hand in the swing plane (normal n_out, through the
    current shoulder). Returns diagnostics."""
    l1, l2 = sk.length['RightUpperArm'], sk.length['RightLowerArm']
    S = P.head('RightUpperArm')
    n = D._unit(n_out)
    f = D._unit(np.cross(UP, n))
    u = np.cross(n, f)
    th = math.radians(theta)
    a = math.cos(th) * f + math.sin(th) * u
    perp_up = -math.sin(th) * f + math.cos(th) * u            # the flexion side of the arm line
    fl = math.radians(max(flex, 3.0))
    d = math.sqrt(l1 * l1 + l2 * l2 + 2 * l1 * l2 * math.cos(fl))
    W = S + a * d
    along = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    hgt = math.sqrt(max(0.0, l1 * l1 - along * along))
    E = S + a * along - perp_up * hgt                          # elbow points to the extensor side
    ua = D._unit(E - S)
    fa = D._unit(W - E)
    hinge = np.cross(ua, fa)
    hinge = D._unit(hinge) if np.linalg.norm(hinge) > 1e-6 else -n
    # keep the REST sign convention (+X rotation = flexion): hinge = u x f
    set_bone_frame(P, 'RightUpperArm', S, ua, hinge)
    set_bone_frame(P, 'RightLowerArm', E, fa, hinge)
    # hand: back of the hand outward (Z = n), fingers along the forearm tipped by psi in the plane
    Yh = axis_angle(n, -psi) @ fa
    Zh = axis_angle(Yh, roll) @ n                  # roll: hand rotation about its own long axis
    Xh = np.cross(Yh, Zh)
    Rh = np.stack([Xh, Yh, Zh], 1)
    cur = P.m['RightHand']
    M = np.eye(4)
    M[:3, :3] = Rh
    M[:3, 3] = W
    G = M @ np.linalg.inv(cur)
    for dd in P.descendants('RightHand'):
        P.m[dd] = G @ P.m[dd]
    return {'shoulder': S, 'elbow': E, 'wrist': W, 'reach': d / (l1 + l2), 'n': n, 'f': f, 'u': u}


# ------------------------------------------------------------ club points
_T0, _F0, _H0 = None, None, None


def club_ref():
    global _T0, _F0, _H0
    if _T0 is None:
        _T0, _F0, _H0 = PO.club_points_ref()
    return _T0, _F0, _H0


def club_world(P, pts_ref):
    X = P.xform('Club')
    return (X[:3, :3] @ np.atleast_2d(pts_ref).T).T + X[:3, 3]


STONE_SAMPLES = None


def stone_samples():
    global STONE_SAMPLES
    if STONE_SAMPLES is None:
        STONE_SAMPLES = PO.club_samples_ref(200)
    return STONE_SAMPLES


def lowest_club_z(P):
    return float(club_world(P, stone_samples())[:, 2].min())


def solve_theta_for_ground(sk, prm, n_out, flex, psi, lo=-80.0, hi=10.0):
    """Arm angle at which the club's lowest point just touches the ground."""
    def z(th):
        P = body(sk, prm)
        arm_lever(P, sk, n_out, th, flex, psi)
        return lowest_club_z(P)
    a, b = lo, hi
    za, zb = z(a), z(b)
    if za > 0 and zb > 0:
        return a if za < zb else b
    # z decreases as theta goes down (toward lo); find the zero crossing
    for _ in range(40):
        m = (a + b) / 2
        if z(m) > 0:
            b = m
        else:
            a = m
    return b


# ================================================================ attacks
EASE = {
    'smooth': smooth,
    'linear': lambda t: min(1.0, max(0.0, t)),
    'in': lambda t: ease_in(t, 1.6),                               # accelerate into the hit
    'fast': lambda t: smooth(min(1.0, t / 0.55)),                  # done by ~mid-segment
    'out': lambda t: 1 - (1 - min(1.0, max(0.0, t))) ** 2,
}


def ref_lever(sk, n_out):
    """Lever parameters (theta, flex, psi, roll, plane normal) reproducing the
    reference carry. The carry arm hangs out to the side, so its plane is the
    plane through the actual shoulder, elbow and wrist."""
    P = PO.Pose(sk)
    S, E, W = P.head('RightUpperArm'), P.head('RightLowerArm'), P.head('RightHand')
    flex = math.degrees(math.acos(np.clip(D._unit(E - S) @ D._unit(W - E), -1, 1)))
    Rref = P.m['RightHand'][:3, :3]
    best = None
    for sgn in (1, -1):
        n = D._unit(np.cross(E - S, W - S)) * sgn
        f = D._unit(np.cross(UP, n))
        u = np.cross(n, f)
        v = W - S
        theta = math.degrees(math.atan2(v @ u, v @ f))
        Q = PO.Pose(sk)
        arm_lever(Q, sk, n, theta, flex, 0.0, 0.0)
        e = np.linalg.norm(Q.head('RightLowerArm') - E)
        if best is None or e < best[0]:
            best = (e, n, theta)
    _, n, theta = best
    best = None
    for psi in np.arange(-40, 40.1, 1.0):
        for roll in np.arange(-180, 180.1, 3.0):
            Q = PO.Pose(sk)
            arm_lever(Q, sk, n, theta, flex, psi, roll)
            e = np.linalg.norm(Q.m['RightHand'][:3, :3] - Rref)
            if best is None or e < best[0]:
                best = (e, psi, roll)
    e0, p0, r0 = best
    for psi in np.arange(p0 - 1, p0 + 1.01, 0.1):
        for roll in np.arange(r0 - 2, r0 + 2.01, 0.2):
            Q = PO.Pose(sk)
            arm_lever(Q, sk, n, theta, flex, psi, roll)
            e = np.linalg.norm(Q.m['RightHand'][:3, :3] - Rref)
            if e < best[0]:
                best = (e, psi, roll)
    return (theta, flex, best[1], best[2], tuple(n))


def lever_frames(sk, spec):
    """Frames from lever keys. Each key: (frame, body_params, (theta, flex, psi), easing dict).
    A key with arm None is the reference carry pose (blended per bone)."""
    ref = PO.Pose(sk)
    keys = spec['keys']
    out = []
    for f in range(keys[0][0], keys[-1][0] + 1):
        for (fa, pa, arma, _), (fb, pb, armb, ez) in zip(keys[:-1], keys[1:]):
            if fa <= f <= fb:
                t = 0.0 if fb == fa else (f - fa) / (fb - fa)
                eb = EASE[ez.get('body', 'smooth')](t)
                if arma is None or armb is None:
                    def mk(p, arm):
                        if arm is None:
                            return ref
                        Q = body(sk, p)
                        arm_lever(Q, sk, arm[4] if len(arm) > 4 else spec['n_out'], *arm[:4])
                        return Q
                    P = blend(sk, mk(pa, arma), mk(pb, armb), eb)
                    arm = None
                else:
                    prm = lerp_params(pa, pb, eb)
                    ra = arma[3] if len(arma) > 3 else 0.0
                    rb = armb[3] if len(armb) > 3 else 0.0
                    na = np.asarray(arma[4] if len(arma) > 4 else spec['n_out'], float)
                    nb = np.asarray(armb[4] if len(armb) > 4 else spec['n_out'], float)
                    en = EASE[ez.get('plane', 'smooth')](t)
                    nn = D._unit(na * (1 - en) + nb * en)
                    arm = (lerp(arma[0], armb[0], EASE[ez.get('theta', 'smooth')](t)),
                           lerp(arma[1], armb[1], EASE[ez.get('flex', 'smooth')](t)),
                           lerp(arma[2], armb[2], EASE[ez.get('psi', 'smooth')](t)),
                           lerp(ra, rb, EASE[ez.get('roll', 'smooth')](t)), tuple(nn))
                    P = body(sk, prm)
                    arm_lever(P, sk, nn, *arm[:4])
                out.append((f, P, arm))
                break
    return out


def ground_slam_spec(sk):
    """Overhead Ground Slam: the arm rises FORWARD through the front (never back) to a high windup with
    the club cocked behind the head (head of the club pointing back and down),
    holds, then the shoulder drives a near-vertical arc; the elbow straightens
    by mid-swing and the wrist stays within +-20 deg while the club accelerates
    (ease-in) into the ground in front of him and to his right."""
    n_out = D._unit(np.array([-1.0, 0.18, 0.0]))
    th0, fl0, ps0, ro0, nref = ref_lever(sk, n_out)
    carry = {'shift': (0, 0, 0), 'drop': 0.0, 'lean': 0.0, 'twist': 0.0, 'side': 0.0, 'larm': (0, 0, 0),
             'head': 0.0, 'jaw': 0.0, 'mantle': 0.0, 'belly': 0.0}
    rise = dict(carry, shift=(0, 0.15, 0), drop=-0.05, lean=-6, twist=-8, larm=(-30, -10, 25), head=4, jaw=8,
                mantle=8)
    wind = dict(carry, shift=(0, 0.40, 0), drop=-0.12, lean=-14, twist=-18, side=-3, larm=(-65, -22, 45),
                head=10, jaw=18, mantle=20)
    cock = dict(wind, shift=(0, 0.45, 0), drop=-0.16, lean=-16, twist=-20, jaw=22)
    impact = dict(carry, shift=(0, -0.45, 0), drop=1.30, lean=32, twist=6, side=2, larm=(-38, 8, 45), head=-14,
                  jaw=24, mantle=-10, belly=6)
    bounce = dict(impact, drop=1.16, lean=28, belly=-5, mantle=6, jaw=20)
    settle = dict(impact, drop=1.24, lean=30, belly=2, mantle=-3, jaw=18)
    lift = dict(carry, shift=(0, -0.1, 0), drop=0.45, lean=10, twist=-2, larm=(-12, 0, 12), jaw=6, mantle=2)
    # Unwrapped arm angles (theta only moves one way per phase). The arm rises
    # FORWARD like an overhead axe chop: carry (-114, carry plane) -> forward
    # (-15) -> straight up beside the head (95) while the elbow bends so the club
    # drops behind the head -> cocked (112, 118) -> strike back over the top and
    # down to th_imp -> recovery to the carry.
    nref = tuple(nref)
    sm = {'body': 'smooth', 'theta': 'smooth', 'flex': 'smooth', 'psi': 'smooth'}
    strike = {'body': 'in', 'theta': 'in', 'flex': 'fast', 'psi': 'smooth'}
    A_carry = (th0, fl0, ps0, ro0, nref)
    # early raise: the arm swings forward in a plane leaning 30 deg outward so the
    # club's pommel clears the thigh and belly, hand rolling to neutral
    f_ax = D._unit(np.cross(UP, n_out))
    A_early = (-70.0, 33.0, 10.0, 0.0, tuple(axis_angle(f_ax, -30.0) @ n_out))
    A_fwd = (-15.0, 38.0, 4.0, 10.0, tuple(n_out))
    A_up = (95.0, 70.0, -2.0, 0.0, tuple(n_out))
    A_wind = (112.0, 82.0, -4.0, 0.0, tuple(n_out))
    A_cock = (118.0, 88.0, -10.0, 0.0, tuple(n_out))
    fl_imp, ps_imp = 6.0, 18.0
    th_imp = solve_theta_for_ground(sk, impact, n_out, fl_imp, ps_imp, lo=-100.0, hi=-20.0)
    A_imp = (th_imp, fl_imp, ps_imp, 0.0, tuple(n_out))
    A_bounce = (th_imp + 5.0, 9.0, 16.0, 0.0, tuple(n_out))
    A_settle = (th_imp + 1.5, 8.0, 17.0, 0.0, tuple(n_out))
    A_lift = (th_imp + 18.0, 30.0, 10.0, -8.0, tuple(D._unit(np.asarray(n_out) * 0.7 + np.asarray(nref) * 0.3)))
    A_lower = (th0 - 12.0, fl0 + 12.0, ps0 - 6.0, ro0 * 0.8, nref)
    side = dict(rise, larm=(-20, -10, 20))
    lift = dict(carry, shift=(0, -0.05, 0), drop=0.40, lean=10, twist=-4, larm=(-8, 0, 8), jaw=6, mantle=2)
    lower = dict(carry, drop=0.10, lean=3, larm=(-3, 0, 3))
    A_carry2 = A_carry
    keys = [(1, carry, None, sm),
            (2, carry, A_carry, sm),
            (5, side, A_early, sm),
            (8, side, A_fwd, sm),
            (13, rise, A_up, sm),
            (17, wind, A_wind, sm),
            (21, cock, A_cock, sm),
            (29, impact, A_imp, strike),
            (32, bounce, A_bounce, sm),
            (36, settle, A_settle, sm),
            (45, lift, A_lift, sm),
            (54, lower, A_lower, sm),
            (59, carry, A_carry2, sm),
            (60, carry, None, sm)]
    return {'name': 'GroundSlam', 'n_out': n_out, 'keys': keys, 'impact': 29, 'strike': (21, 29),
            'windup': 21, 'recovery': 54, 'theta_impact': th_imp}


# ------------------------------------------------------------------ stomp
def leg_hinge(P, sk, side, ankle, pole, foot_R=None):
    """Two-bone leg IK with ONE knee axis shared by thigh and shin (no twist)."""
    ub, lb, fb = side + 'UpperLeg', side + 'LowerLeg', side + 'Foot'
    H = P.head(ub)
    l1, l2 = sk.length[ub], sk.length[lb]
    v = np.asarray(ankle) - H
    d = min(np.linalg.norm(v), l1 + l2 - 1e-4)
    uu = D._unit(v)
    pole = np.asarray(pole, float)
    pole = D._unit(pole - uu * (pole @ uu))
    a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    hgt = math.sqrt(max(0.0, l1 * l1 - a * a))
    K = H + uu * a + pole * hgt
    A = H + uu * d
    th_dir = D._unit(K - H)
    sh_dir = D._unit(A - K)
    hinge = np.cross(pole, uu)                   # perpendicular to the leg plane
    if hinge @ sk.rest[ub][:3, 0] < 0:           # keep the rest X convention
        hinge = -hinge
    set_bone_frame(P, ub, H, th_dir, hinge)
    set_bone_frame(P, lb, K, sh_dir, hinge)
    # foot: world orientation given (flat), placed at the ankle
    Rf = sk.ref[fb][:3, :3] if foot_R is None else foot_R
    M = np.eye(4)
    M[:3, :3] = Rf
    M[:3, 3] = A
    G = M @ np.linalg.inv(P.m[fb])
    for dd in P.descendants(fb):
        P.m[dd] = G @ P.m[dd]
    flexk = math.degrees(math.acos(np.clip(th_dir @ sh_dir, -1, 1)))
    return {'knee': K, 'ankle': A, 'knee_flex': flexk, 'hinge': hinge}


def stomp_frames(sk):
    """Stomp: weight shifts over the right (club-side) foot, the left knee comes
    UP high sumo-style (thigh at or a little above horizontal, out to the side)
    with the shin hanging vertical and the foot directly under the knee, a hold
    with a slight extra rise, then the foot slams straight DOWN and lands sole-flat
    where it lifted from (under the hip, out to the side), toes along the facing.
    The standing foot is pinned; the knee is a one-way hinge (shared thigh/shin
    axis); the loincloth front bones swing up and out with the thigh."""
    A0 = {s_: sk.ref[s_ + 'Foot'][:3, 3].copy() for s_ in ('Right', 'Left')}
    l1, l2 = sk.length['LeftUpperLeg'], sk.length['LeftLowerLeg']
    base = {'shift': (0, 0, 0), 'drop': 0.0, 'lean': 0.0, 'side': 0.0, 'lift': 0.0, 'elev': 0.0,
            'land': (0, 0, 0), 'fyaw': 0.0, 'larm': (0, 0, 0), 'rarm': (0, 0), 'head': 0.0, 'jaw': 0.0,
            'belly': 0.0, 'mantle': 0.0, 'loin': 0.0, 'loin_side': 0.0}
    shift = dict(base, shift=(-0.85, 0.15, 0), drop=0.30, lean=-4, side=-6, larm=(-10, -30, 20), rarm=(-5, 16))
    top = dict(shift, shift=(-1.25, 0.25, 0), drop=0.05, lean=-8, side=-9, lift=1.0, elev=6.0, fyaw=8.0,
               larm=(-35, -70, 30), rarm=(-12, 26), head=4, jaw=10, loin=-35, loin_side=-22)
    top2 = dict(top, elev=12.0, drop=-0.05, lean=-10, head=6, jaw=16, loin=-40, loin_side=-24)
    mid = dict(top, lift=0.45, elev=0.0, drop=0.45, lean=10, larm=(-25, -55, 30), jaw=20, loin=-20, loin_side=-10)
    impact = dict(shift, shift=(-0.85, 0.05, 0), lift=0.0, land=(0.0, 0.0, 0.0), fyaw=8.0, drop=0.95,
                  lean=22, side=-4, larm=(-20, -45, 30), rarm=(-14, 30), head=-14, jaw=22, belly=6, mantle=-8,
                  loin=-16, loin_side=-8)
    bounce = dict(impact, drop=0.85, lean=19, belly=-5, mantle=5, head=-10)
    settle = dict(impact, drop=0.9, lean=20, belly=2, mantle=-2, head=-11)
    step = dict(base, shift=(-0.6, 0.05, 0), drop=0.35, lean=6, lift=0.0, land=(0.0, 0.0, 0.0), fyaw=4.0,
                larm=(-10, -20, 15), rarm=(-5, 12), jaw=6)
    keys = [(1, base, 'smooth'), (10, shift, 'smooth'), (38, top, 'smooth'), (44, top2, 'smooth'),
            (47, mid, 'in'), (50, impact, 'in'), (53, bounce, 'smooth'), (57, settle, 'smooth'),
            (68, step, 'smooth'), (80, base, 'smooth')]
    frames = []
    X = np.array([1.0, 0, 0])
    Y = np.array([0, 1.0, 0])
    fwd = np.array([0, -1.0, 0])
    thigh_dir0 = D._unit(np.array([0.80, -0.60, 0.0]))       # sumo: knee up and OUT to the side, clears the belly
    for f in range(1, keys[-1][0] + 1):
        for (fa, pa, _), (fb, pb, ease) in zip(keys[:-1], keys[1:]):
            if fa <= f <= fb:
                t = (f - fa) / (fb - fa)
                tt = {'smooth': smooth, 'in': ease_in}[ease](t)
                prm = {k: (lerp(np.asarray(pa[k], float), np.asarray(pb[k], float), tt)) for k in pa}
                P = PO.Pose(sk)
                P.move('HumanoidRootPart', np.asarray(prm['shift']) + np.array([0, 0, -float(prm['drop'])]))
                P.rot('LowerTorso', np.array([-1.0, 0, 0]), -float(prm['lean']) * 0.35)
                P.rot('UpperTorso', np.array([-1.0, 0, 0]), -float(prm['lean']) * 0.65)
                P.rot('LowerTorso', fwd, float(prm['side']))
                P.rot('UpperTorso', fwd, -float(prm['side']) * 0.5)
                r = leg_hinge(P, sk, 'Right', A0['Right'], pole=D.FOOT_DIR['Right'])
                # stomping leg: blend a ground target with the raised 90/90 target
                H = P.head('LeftUpperLeg')
                el = math.radians(float(prm['elev']))
                tdir = D._unit(thigh_dir0 * math.cos(el) + UP * math.sin(el))
                raised = H + tdir * l1 * 0.99 + np.array([0, 0, -l2 * 0.99])
                ground = A0['Left'] + np.asarray(prm['land'])
                w = float(prm['lift'])
                tgt = ground * (1 - w) + raised * w
                pole = D._unit(thigh_dir0 + np.array([0, 0, 0.25]))
                yaw = float(prm['fyaw'])
                Rfl = axis_angle(UP, yaw) @ sk.ref['LeftFoot'][:3, :3]
                l = leg_hinge(P, sk, 'Left', tgt, pole=pole, foot_R=Rfl)
                la = prm['larm']
                P.rot('LeftUpperArm', X, float(la[0]))
                P.rot('LeftUpperArm', Y, float(la[1]))
                P.rot_local('LeftLowerArm', [1, 0, 0], float(la[2]))
                ra = prm['rarm']
                P.rot('RightUpperArm', X, float(ra[0]))
                P.rot('RightUpperArm', Y, float(ra[1]))
                P.rot('Head', X, float(prm['head']))
                P.rot_local('Jaw', [1, 0, 0], float(prm['jaw']))
                P.rot_local('Belly', [1, 0, 0], float(prm['belly']))
                P.rot('Mantle_R', Y, float(prm['mantle']))
                P.rot('Mantle_L', Y, -float(prm['mantle']))
                P.rot('Loincloth_Front_1', X, float(prm['loin']))
                P.rot('Loincloth_Front_1', Y, float(prm['loin_side']))
                P.rot('Loincloth_Front_2', X, float(prm['loin']) * 0.4)
                frames.append((f, P, {'right': r, 'left': l}))
                break
    return {'name': 'Stomp', 'frames': frames, 'impact': 50, 'keys': keys,
            'labels': {'weight shift': 10, 'top of raise': 44, 'mid-slam': 48, 'impact': 50, 'recovery': 68}}


# ================================================================ checks
def arm_metrics(P, sk, n_out):
    S = P.head('RightUpperArm')
    E = P.head('RightLowerArm')
    W = P.head('RightHand')
    l1, l2 = sk.length['RightUpperArm'], sk.length['RightLowerArm']
    reach = np.linalg.norm(W - S) / (l1 + l2)
    ua = D._unit(E - S)
    fa = D._unit(W - E)
    flex = math.degrees(math.acos(np.clip(ua @ fa, -1, 1)))
    yh = P.m['RightHand'][:3, 1]
    bend = math.degrees(math.acos(np.clip(yh @ fa, -1, 1)))
    line = D._unit(W - S)
    off = (E - S) - line * ((E - S) @ line)
    n = D._unit(n_out)
    out_of_plane = abs(off @ n) / max(np.linalg.norm(off), 1e-9) if np.linalg.norm(off) > 1e-3 else 0.0
    lateral = float(off @ n)             # + = elbow pointing outward (lateral)
    return {'reach_pct': round(100 * reach, 2), 'elbow_flex': round(flex, 2), 'wrist_bend': round(bend, 2),
            'elbow_out_of_plane': round(out_of_plane, 3), 'elbow_lateral_offset': round(lateral, 3)}


def arm_behind_coronal(P):
    """(degrees the right upper arm points BEHIND the torso's coronal plane,
    hand below shoulder?). Positive = behind (shoulder extension)."""
    S, E, W = P.head('RightUpperArm'), P.head('RightLowerArm'), P.head('RightHand')
    ua = D._unit(E - S)
    fwd = D._unit(P.m['UpperTorso'][:3, 2])
    return math.degrees(math.asin(np.clip(-(ua @ fwd), -1, 1))), bool(W[2] < S[2])


def club_clearance(P, prims):
    S = club_world(P, stone_samples())
    body_ = [q for q in PO.body_prims_posed(P, prims) if not q.bone.startswith(('RightUpperArm', 'RightLowerArm',
                                                                                  'RightHand'))]
    return float(PO.min_clearance(S, body_).min()), float(S[:, 2].min())


def thigh_clearance(P, prims, side='Left'):
    """Gap between the posed thigh surface (capsule, radius tapering 1.30 -> 1.02
    from 40 % of its length to the knee) and the gut (belly prims), in studs.
    The thigh root is excluded: it is blended into the pelvis by construction."""
    ub = side + 'UpperLeg'
    H = P.head(ub)
    K = P.head(side + 'LowerLeg')
    ts = np.linspace(0.4, 1.0, 10)
    pts = np.array([H + (K - H) * t for t in ts])
    rad = 1.30 + (1.02 - 1.30) * (ts - 0.4) / 0.6
    gut = [q for q in PO.body_prims_posed(P, prims) if q.tag in ('belly', 'belly_low')]
    d = PO.min_clearance(pts, gut) - rad
    return float(d.min())


def write_strike(sk=None):
    """Solve the striking-face normal: world DOWN at the Ground Slam impact
    frame, expressed in the club's REFERENCE pose (source/club_strike.json)."""
    import json
    from pathlib import Path
    sk = sk or PO.Skeleton()
    spec = ground_slam_spec(sk)
    fr = {f: P for f, P, a in lever_frames(sk, spec)}
    P = fr[spec['impact']]
    X = P.xform('Club')[:3, :3]
    n = X.T @ np.array([0, 0, -1.0])
    out = Path(__file__).resolve().parent / 'source' / 'club_strike.json'
    out.write_text(json.dumps({'normal_ref_world': [round(float(v), 6) for v in n],
                               'note': 'Striking-face normal in the REFERENCE pose; points straight down at the '
                                       'GroundSlam impact frame. Written by fc_motion.write_strike().'}, indent=1))
    return n


if __name__ == '__main__':
    import sys
    if 'strike' in sys.argv:
        for i in range(3):
            import importlib
            import fc_parts
            importlib.reload(fc_parts)
            STONE_SAMPLES = None
            _T0 = None
            print('strike normal', write_strike())
