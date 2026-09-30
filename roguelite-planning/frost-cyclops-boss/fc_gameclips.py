"""Game clips for the Frost Cyclops at 24 fps (pure numpy): Idle, Walk, Hit, Death.

Every generator returns a list of fc_pose.Pose objects, one per frame 0..N
(armature space; the rig sits at the origin, so this is also root space).
Idle frame 0 is exactly the reference pose, which is also the first and last
frame of both attacks, so every clip can blend in and out.
"""
import math

import numpy as np

import fc_design as D
import fc_motion as MO
import fc_pose as PO
from fc_sdf import axis_angle

FPS = 24
UP = np.array([0, 0, 1.0])
X = np.array([1.0, 0, 0])
Y = np.array([0, 1.0, 0])
RIGHT = np.array([-1.0, 0, 0])          # the character's right
FWD = np.array([0, -1.0, 0])


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def lag(w, phi):
    """sin(w - phi) shifted so it is exactly 0 at w = 0 (periodic)."""
    return math.sin(w - phi) + math.sin(phi)


def pin_legs(P, sk, ankles=None, feet=None):
    """Hinge-IK both legs back onto their ankles (reference ankles by default)."""
    out = {}
    for side in ('Right', 'Left'):
        A = sk.ref[side + 'Foot'][:3, 3] if ankles is None else ankles[side]
        out[side] = MO.leg_hinge(P, sk, side, A, foot_R=None if feet is None else feet[side])
    return out


# ------------------------------------------------------------------ Idle
IDLE_DURATION = 3.0


def idle_frames(sk):
    n = int(round(IDLE_DURATION * FPS))
    frames = []
    for f in range(n + 1):
        t = f / n
        w = 2 * math.pi * t
        b = math.sin(2 * w)                                 # two heavy breaths per cycle
        P = PO.Pose(sk)
        P.move('HumanoidRootPart', [0.07 * math.sin(w), 0.0, -0.035 * (1 - math.cos(2 * w)) / 2])
        P.rot('LowerTorso', FWD, 1.3 * math.sin(w))          # slow weight shift side to side
        P.rot('UpperTorso', FWD, -0.8 * math.sin(w))
        P.rot('UpperTorso', RIGHT, -1.1 * b)                 # chest rises with the breath
        P.rot('UpperTorso', UP, 1.2 * math.sin(w))
        pin_legs(P, sk)
        P.rot('Head', RIGHT, 1.4 * lag(2 * w, 0.5))
        P.rot('Head', UP, 2.0 * math.sin(w))
        P.rot_local('Jaw', [1, 0, 0], 2.5 * (1 - math.cos(2 * w)) / 2)
        P.rot_local('Belly', [1, 0, 0], 2.2 * lag(2 * w, 0.7))            # secondary, a little late
        P.rot('Mantle_R', Y, 1.6 * lag(2 * w, 0.9))
        P.rot('Mantle_L', Y, -1.6 * lag(2 * w, 0.9))
        P.rot('Loincloth_Front_1', X, 2.0 * lag(w, 1.1))
        P.rot('Loincloth_Back_1', X, -1.5 * lag(w, 1.1))
        P.rot('LeftUpperArm', X, 1.8 * lag(w, 0.6))
        P.rot('RightUpperArm', X, 1.0 * lag(w, 0.6))
        # keep the resting stone off the snow while the body sinks and sways
        P.rot_local('RightLowerArm', [1, 0, 0], 7.0 * (1 - math.cos(2 * w)) / 2 + 5.0 * (1 - math.cos(w)) / 2)
        blink = math.exp(-((t - 0.56) / 0.018) ** 2)
        P.rot_local('EyelidUpper', [1, 0, 0], 38.0 * blink)
        frames.append(P)
    return frames


# ------------------------------------------------------------------ Walk
WALK_CYCLE = 1.5            # seconds per full cycle (two steps)
WALK_STRIDE = 4.5           # studs travelled per cycle
STANCE = 0.62               # fraction of the cycle each foot is planted
CROUCH = 0.55
BOB = 0.15
LIFT = 0.55


def walk_foot(sk, side, p):
    """Ankle target (root space) and planted flag for phase p in [0, 1)."""
    A0 = sk.ref[side + 'Foot'][:3, 3]
    L = WALK_STRIDE * STANCE                                  # foot travel while planted
    y0 = 0.05
    if p < STANCE:
        q = p / STANCE
        return np.array([A0[0], y0 - L / 2 + L * q, A0[2]]), True
    q = (p - STANCE) / (1 - STANCE)
    return np.array([A0[0], y0 + L / 2 - L * smooth(q), A0[2] + LIFT * math.sin(math.pi * q) ** 1.2]), False


def walk_frames(sk):
    n = int(round(WALK_CYCLE * FPS))
    frames, planted = [], []
    # walking feet: the right foot turned in from its 52 deg stance toe-out to ~22 deg, the left straight
    feet = {'Right': axis_angle(UP, 30.0) @ sk.ref['RightFoot'][:3, :3],
            'Left': axis_angle(UP, -8.0) @ sk.ref['LeftFoot'][:3, :3]}
    offs = {'Right': 0.0, 'Left': 0.5}
    for f in range(n + 1):
        t = (f % n) / n
        w = 2 * math.pi * t
        P = PO.Pose(sk)
        # pelvis: lowest at each heel strike (t = 0, 0.5), sways over the planted foot
        sway = -0.28 * math.sin(w)                           # + toward the character's left
        P.move('HumanoidRootPart', [sway, 0.0, -CROUCH + BOB * (1 - math.cos(4 * math.pi * t)) / 2])
        P.rot('LowerTorso', UP, -5.0 * math.sin(w))          # swing-side hip leads
        P.rot('LowerTorso', FWD, 2.5 * math.sin(w))
        P.rot('UpperTorso', RIGHT, -6.0 - 1.5 * math.cos(4 * math.pi * t))     # leaning into the walk
        P.rot('UpperTorso', UP, 8.0 * math.sin(w))            # chest counter-rotates
        P.rot('UpperTorso', FWD, -1.5 * math.sin(w))
        ank, pl = {}, {}
        for side in ('Right', 'Left'):
            ank[side], pl[side] = walk_foot(sk, side, (t + offs[side]) % 1.0)
        pin_legs(P, sk, ankles=ank, feet=feet)
        # arms: left fist swings against the left leg; the club arm carries the club a little raised
        P.rot('LeftUpperArm', X, -16.0 * math.cos(w))        # opposite to the left leg
        P.rot_local('LeftLowerArm', [1, 0, 0], 8.0 - 6.0 * math.cos(w))
        P.rot('RightUpperArm', X, 5.0 * math.cos(w) - 6.0)
        P.rot('RightUpperArm', Y, 14.0)                      # club carried out beside the right leg
        P.rot_local('RightLowerArm', [1, 0, 0], 26.0)
        P.rot('Head', RIGHT, 2.0 * lag(4 * math.pi * t, 0.8))
        P.rot('Head', UP, 4.0 * math.sin(w))
        P.rot_local('Belly', [1, 0, 0], 3.0 * lag(4 * math.pi * t, 1.0))      # gut follows the bob, late
        P.rot('Mantle_R', Y, 2.5 * lag(4 * math.pi * t, 1.2))
        P.rot('Mantle_L', Y, -2.5 * lag(4 * math.pi * t, 1.2))
        P.rot('Loincloth_Front_1', X, 7.0 * lag(w, 0.9))
        P.rot('Loincloth_Back_1', X, -6.0 * lag(w, 0.9))
        frames.append(P)
        planted.append(pl)
    return frames, planted


# ------------------------------------------------------------------ Hit
HIT_DURATION = 11 / FPS


def hit_frames(sk):
    n = int(round(HIT_DURATION * FPS))
    frames = []
    for f in range(n + 1):
        t = f / n
        e = math.sin(math.pi * t ** 0.55)                    # fast recoil, slower return, 0 at both ends
        e2 = math.sin(math.pi * t ** 0.8)
        P = PO.Pose(sk)
        P.move('HumanoidRootPart', [0.0, 0.18 * e, -0.08 * e])
        P.rot('UpperTorso', RIGHT, 9.0 * e)                  # rocked back
        P.rot('UpperTorso', UP, -5.0 * e)
        pin_legs(P, sk)
        P.rot('Head', RIGHT, 12.0 * e)
        P.rot_local('Jaw', [1, 0, 0], 16.0 * e)
        P.rot_local('EyelidUpper', [1, 0, 0], 20.0 * e)
        P.rot('LeftUpperArm', X, -12.0 * e)
        P.rot_local('Belly', [1, 0, 0], -4.0 * e2)
        P.rot('Mantle_R', Y, 5.0 * e2)
        P.rot('Mantle_L', Y, -5.0 * e2)
        frames.append(P)
    return frames


# ------------------------------------------------------------------ Death
DEATH_DURATION = 2.5
TOE_ROLL = 25.0             # degrees the kneeling feet roll up onto their toes
KNEEL_DROP = 1.50           # pelvis drop that puts the knees on the snow (fine-tuned against the mesh in Blender)
KNEEL_FWD = 0.5             # pelvis travel forward as he drops
KNEEL_FOOT_BACK = 1.45      # kneeling ankle behind the hip
KNEEL_FOOT_OUT = 0.15
KNEEL_ANKLE_BELOW_HIP = 1.52
ARM_FWD = 60.0              # arms reach forward as he falls
ARM_OUT = 35.0
CLUB_LIFT = 0.0             # set from the evaluated club mesh so it rests exactly on the snow


def _open_right_hand(P, sk, k):
    """Blend the right fingers toward their relaxed REST shape (k = 0..1)."""
    for nm in D.FINGER_NAMES + ['Thumb']:
        for j in range(3):
            b = 'Right%s%d' % (nm, j + 1)
            par = sk.parent[b]
            rel_rest = np.linalg.inv(sk.rest[par]) @ sk.rest[b]
            rel_cur = np.linalg.inv(P.m[par]) @ P.m[b]
            q = MO.slerp(MO.m2q(rel_cur[:3, :3]), MO.m2q(rel_rest[:3, :3]), k)
            R = np.eye(4)
            R[:3, :3] = MO.q2m(q)
            R[:3, 3] = rel_cur[:3, 3]
            want = P.m[par] @ R
            G = want @ np.linalg.inv(P.m[b])
            for d in P.descendants(b):
                P.m[d] = G @ P.m[d]


def club_rest_on_ground(sk, samples, alpha):
    """World matrix of the dropped club lying on the snow: tipped from its REF
    placement by `alpha` about a horizontal axis through the stone's lowest
    point, then lifted so its lowest point touches z = 0."""
    pts = samples                                             # REF world samples
    low = pts[np.argmin(pts[:, 2])]
    T, h = D.club_axis()
    axis = D._unit(np.cross(UP, -h))                          # tips the grip end down and back
    R = axis_angle(axis, alpha)
    G = np.eye(4)
    G[:3, :3] = R
    G[:3, 3] = low - R @ low
    moved = (R @ pts.T).T + G[:3, 3]
    G[2, 3] -= moved[:, 2].min() - CLUB_LIFT
    return G                                                  # applied on top of the REF club matrix


def death_frames(sk, beta=65.0, kneel_lift=0.0, prone_lift=0.0, club_alpha=60.0, samples=None):
    """Death: recoil, the club slips out of the opening hand and falls, he drops
    to his knees (shins on the snow), then topples forward about the knees onto
    his belly, arms spilling out, head turned; a small settle.
    beta, kneel_lift, prone_lift and club_alpha are solved in Blender so the
    evaluated mesh rests on (not in) the ground."""
    n = int(round(DEATH_DURATION * FPS))
    samples = PO.club_samples_ref(200) if samples is None else samples
    l1 = sk.length['LeftUpperLeg']
    l2 = sk.length['LeftLowerLeg']

    def kneel_pose(k, topple, arms, head, hand_open):
        """k: 0 standing -> 1 kneeling; topple: forward angle about the knees."""
        P = PO.Pose(sk)
        drop = KNEEL_DROP * k - kneel_lift * k
        P.move('HumanoidRootPart', [0.0, -KNEEL_FWD * k, -drop])
        P.rot('UpperTorso', RIGHT, -14.0 * k)                 # slumps forward
        P.rot('LowerTorso', RIGHT, 4.0 * k)
        # legs: he drops onto his knees with the toes tucked under. The pelvis
        # comes down and forward over the knees; each ankle rises and moves back
        # behind its knee while the foot rolls about its lateral axis so the toe
        # ball stays on the snow.
        for side in ('Right', 'Left'):
            ub, lb, fb, tb = side + 'UpperLeg', side + 'LowerLeg', side + 'Foot', side + 'Toes'
            A_stand = sk.ref[fb][:3, 3]
            if k < 1e-6:
                MO.leg_hinge(P, sk, side, A_stand)
                continue
            s = -1 if side == 'Right' else 1
            fdir = D.FOOT_DIR[side]
            axis = D._unit(np.cross(UP, fdir))
            # kneeling ankle: behind and below the (already lowered) hip, so the
            # thigh hangs about vertical and the knee lands under the hip
            A_kn = P.head(ub) + np.array([s * KNEEL_FOOT_OUT, KNEEL_FOOT_BACK, -KNEEL_ANKLE_BELOW_HIP])
            A_t = A_stand * (1 - k) + A_kn * k
            R = axis_angle(axis, TOE_ROLL * k)
            Rf = R @ sk.ref[fb][:3, :3]
            MO.leg_hinge(P, sk, side, A_t, pole=np.array([s * 0.35, -1.0, 0.0]), foot_R=Rf, pole_weight=k)
            P.rot(tb, axis, -TOE_ROLL * k)                   # toes stay flat on the snow
        # topple forward about the knees; shins and feet stay where they are
        if topple > 0:
            keep = {b: P.m[b].copy() for b in ('RightLowerLeg', 'RightFoot', 'RightToes',
                                               'LeftLowerLeg', 'LeftFoot', 'LeftToes')}
            pivot = (P.head('RightLowerLeg') + P.head('LeftLowerLeg')) / 2
            P.rot('LowerTorso', RIGHT, -topple, pivot=pivot)      # forward about the knees
            P.move('HumanoidRootPart', [0, 0, prone_lift * min(1.0, topple / max(beta, 1e-6))])
            for b, m in keep.items():
                P.m[b] = m
        # arms: the left arm swings out and forward, the empty right arm falls out to the side
        # arms reach forward as he falls; the reach grows with the topple so they
        # end stretched out ahead along the snow rather than propping him up
        fwd_arm = (ARM_FWD + 0.9 * max(0.0, topple)) * arms
        P.rot('LeftUpperArm', X, -fwd_arm)
        P.rot('LeftUpperArm', Y, -ARM_OUT * arms)
        P.rot('RightUpperArm', X, -fwd_arm)
        P.rot('RightUpperArm', Y, ARM_OUT * arms)
        # the front flap trails back between the thighs instead of digging in
        flap = max(0.0, topple) + 35.0 * k
        P.rot('Loincloth_Front_1', RIGHT, -flap)
        P.rot('Loincloth_Front_2', RIGHT, -0.4 * flap)
        P.rot('Head', UP, 28.0 * head)
        P.rot('Head', RIGHT, 10.0 * head)                     # face lifted off the snow
        P.rot_local('Jaw', [1, 0, 0], 14.0 * head)
        P.rot_local('EyelidUpper', [1, 0, 0], 30.0 * head)
        _open_right_hand(P, sk, hand_open)
        return P

    frames = []
    for f in range(n + 1):
        tt = f / FPS
        recoil = math.sin(math.pi * min(1.0, tt / 0.3)) if tt < 0.3 else 0.0
        k = smooth((tt - 0.25) / 0.75)                        # 0.25 s -> 1.0 s: to the knees
        fall = ((tt - 1.1) / 0.8)                             # 1.1 s -> 1.9 s: topple (accelerating)
        fall = 0.0 if fall <= 0 else (1.0 if fall >= 1 else fall ** 1.8)
        settle = 0.0
        if tt > 1.9:
            u = (tt - 1.9) / 0.6
            settle = 0.06 * math.sin(math.pi * min(1.0, u)) * (1 - min(1.0, u))
        topple = beta * (fall - settle)
        arms = smooth((tt - 0.9) / 0.9)
        head = smooth((tt - 1.3) / 0.7)
        hand_open = smooth((tt - 0.15) / 0.3)
        P = kneel_pose(k, topple, arms, head, hand_open)
        if recoil:
            P.rot('UpperTorso', RIGHT, 7.0 * recoil)
            P.rot('Head', RIGHT, 10.0 * recoil)
        # secondary follow-through on the landing
        if tt > 1.8:
            u = min(1.0, (tt - 1.8) / 0.5)
            wob = math.sin(math.pi * u) * (1 - u)
            P.rot_local('Belly', [1, 0, 0], -6.0 * wob)
            P.rot('Mantle_R', Y, 6.0 * wob)
            P.rot('Mantle_L', Y, -6.0 * wob)
        # the club: carried until 0.25 s, then falls (ease-in) and lies on the snow
        c = smooth((tt - 0.25) / 0.45) if tt > 0.25 else 0.0
        cg = c ** 1.6
        if c > 0:
            # it tips over about the stone resting on the snow (never below it)
            ground = club_rest_on_ground(sk, samples, club_alpha * cg) @ sk.ref['Club']
            held = P.m['Club']
            wgt = min(1.0, cg / 0.15)
            M = np.eye(4)
            M[:3, :3] = MO.q2m(MO.slerp(MO.m2q(held[:3, :3]), MO.m2q(ground[:3, :3]), wgt))
            M[:3, 3] = held[:3, 3] * (1 - wgt) + ground[:3, 3] * wgt
            P.m['Club'] = M
        frames.append(P)
    return frames
