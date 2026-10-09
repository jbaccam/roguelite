"""Hammer boss Idle and Walk (pure numpy), on the ORIGINAL carry pose.

The attacks are the original clips (hm_legacy.py). They all start and end on the legacy carry pose
(legacy Idle frame 0 through BossMotion.constrainArms): hammer held low across the front, 1.4 studs
forward of the template rest. The new Idle and Walk (approved 2026-10-04: "fine") keep their body
motion and now hold the hammer the way the attacks pick it up:
  - the fists: rigid on the haft in the carry's grip (the carry's fist-in-hammer pose), so the grip
    is exact on every frame and the fists never roll on the haft between Idle/Walk and an attack;
    the hammer and both fists move together into the arms' reach (Legacy.reach_project) where the
    body motion would over-stretch the nearly straight left arm;
  - the arms: BossMotion.constrainArms (the attacks' own arm solve), with the carry's elbows
    carried by the chest giving the swivel;
  - Idle: the hammer is the carry's, with the Idle's own lag and lift on top; the knees bend about
    the carry's own knees; frame 0 IS the carry pose, so Idle <-> attack junctions are exact. The
    right fist slides up to 0.15 studs toward the butt as he sinks (keeps the forearm cuff out of
    the hammer head).
  - Walk: the run leans 19 deg forward and lifts the knees, so the hammer cannot ride in the carry
    pose (its head would go 1.6 studs into the ground and the right foot through it). It keeps the
    approved walk's raised carry, shifted 0.4 studs out to his right with the head tipped up 6 deg
    so the swinging right foot clears it, in the run and in the game's 0.12 s Walk -> attack blend.

Each clip function returns a Clip: per-frame pose dicts (part -> 4x4 D, see hm_motion) plus the
metadata the checks and the hand-off need (planted contacts, root motion, timings). The rejected new
Slam (2026-10-04 sample, "trash") is gone; the Slam is the original.
"""
import math

import numpy as np

import hm_motion as HM
from hm_motion import Track

REF_X = 7.3                     # haft point the hammer's lag and sway turn about (between the grips)


class Clip:
    def __init__(self, name, fps, loop, frames, meta):
        self.name, self.fps, self.loop, self.frames, self.meta = name, fps, loop, frames, meta

    @property
    def duration(self):
        return (len(self.frames) - 1) / self.fps


# ------------------------------------------------------------------ shared helpers
def body_from(rig, ch):
    """Body parts from a channel dict (pelvis offset px/py/pz, pelvis pp/pr/pyw, chest cp/cr/cy,
    head hp/hr/hy; degrees, positive pitch = forward)."""
    g = lambda k: float(ch.get(k, 0.0))
    return HM.body_parts(rig, np.array([g('px'), g('py'), g('pz')]), HM.euler(g('pp'), g('pr'), g('pyw')),
                         HM.euler(g('cp'), g('cr'), g('cy')), HM.euler(g('hp'), g('hr'), g('hy')))


CUFF = {}


def cuff_points(rig, side, meshes=None):
    """Forearm mesh vertices at the wrist end (rest positions), subsampled: the part of the forearm
    that can press into the hammer head next to the fist. Cached; set once from the mesh data."""
    if side not in CUFF and meshes is not None:
        V = meshes[side + 'LowerArm_v']
        loc = (V - rig.HO) @ rig.HR                         # rest hammer-local
        lo, hi = rig.head_box
        q = np.maximum(lo - loc, 0) + np.maximum(loc - hi, 0)
        dist = np.linalg.norm(q, axis=1)
        near = V[np.argsort(dist)[:400]]                    # the forearm surface closest to the head
        CUFF[side] = near[::10] if dist.min() < 1.0 else None
    return CUFF.get(side)


def axis_angle_of(R):
    """(unit axis, angle deg) of a rotation matrix."""
    q = HM.q_of(R)
    if q[0] < 0:
        q = -q
    s = float(np.linalg.norm(q[1:]))
    if s < 1e-12:
        return np.array([1.0, 0, 0]), 0.0
    return q[1:] / s, math.degrees(2 * math.atan2(s, q[0]))


class Carry:
    """The original attacks' start/end pose and how the Idle and Walk hold the hammer in it."""

    def __init__(self, rig, legacy):
        self.rig, self.L = rig, legacy
        self.K = legacy.to_D(legacy.sample('Idle', 0.0))
        K = self.K
        for p in ('LowerTorso', 'UpperTorso', 'Head', 'RightFoot', 'LeftFoot'):
            assert np.abs(K[p] - np.eye(4)).max() < 1e-9, p + ' is not at rest in the carry pose'
        self.hand = {s: HM.rinv(K['Hammer']) @ K[s + 'Hand'] for s in HM.SIDES}
        # The carry's knees: the shin's turn relative to the thigh (it has a 2.8 deg off-axis part
        # about the template's X hinge) and the thigh's X axis (pelvis rest space). Further bending
        # adds a turn about X on top, so the off-axis part stays the carry's own.
        self.knee = {}
        X = np.array([1.0, 0, 0])
        for s in HM.SIDES:
            Lg = rig.leg[s]
            Rk = K[s + 'UpperLeg'][:3, :3].T @ K[s + 'LowerLeg'][:3, :3]
            reach = lambda beta, Rk=Rk, Lg=Lg: float(np.linalg.norm(Lg['a'] + Rk @ HM.rx(beta) @ Lg['b']))
            grid = np.arange(-40.0, 40.01, 0.25)
            lo = float(grid[int(np.argmax([reach(b) for b in grid]))])
            self.knee[s] = {'R': Rk, 'aim': K[s + 'UpperLeg'][:3, :3] @ X, 'reach': reach, 'lo': lo}

    def legs(self, P, side):
        """Thigh and shin for the pelvis and foot in P: the carry's knee bent further (or less)
        about the thigh's X axis to reach, the thigh turned so its X axis follows the pelvis as in the
        carry. Returns (D_thigh, D_shin, reach error)."""
        rig, k = self.rig, self.knee[side]
        Lg = rig.leg[side]
        H = HM.xf(P['LowerTorso'], Lg['h0'])
        A = HM.xf(P[side + 'Foot'], Lg['a0'])
        dist = float(np.linalg.norm(A - H))
        lo, hi = k['lo'], 150.0
        err = 0.0
        if dist >= k['reach'](lo):
            beta, err = lo, dist - k['reach'](lo)
        else:
            for _ in range(60):
                mid = (lo + hi) / 2
                if k['reach'](mid) > dist:
                    lo = mid
                else:
                    hi = mid
            beta = (lo + hi) / 2
        Rrel = k['R'] @ HM.rx(beta)
        Rt = HM.frame_map(Lg['a'] + Rrel @ Lg['b'], np.array([1.0, 0, 0]), A - H, P['LowerTorso'][:3, :3] @ k['aim'])
        Rs = Rt @ Rrel
        D_t = HM.tf(Rt, H - Rt @ Lg['h0'])
        D_s = HM.tf(Rs, H + Rt @ Lg['a'] - Rs @ Lg['k0'])
        return D_t, D_s, err

    def arms(self, P, slide=None):
        """Fists rigid on the hammer as in the carry (slide: optional {side: studs} along the haft,
        toward the butt end), the hammer and fists moved together into the arms' reach, then
        BossMotion.constrainArms with the carry's elbows carried by the chest."""
        L, K = self.L, self.K
        P = dict(P)
        for s in HM.SIDES:
            P[s + 'Hand'] = P['Hammer'] @ HM.tr(self.rig.HA * (slide or {}).get(s, 0.0)) @ self.hand[s]
            for n in ('UpperArm', 'LowerArm'):
                P[s + n] = P['UpperTorso'] @ K[s + n]
        Q = L.reach_project(L.from_D(P))
        moved = float(np.linalg.norm(HM.xf(L.to_D(Q)['Hammer'], self.rig.HO) - HM.xf(P['Hammer'], self.rig.HO)))
        return L.to_D(L.constrain(Q)), moved


def hammer_world(rig, yaw, pitch, roll, ref):
    """Hammer D from hm_motion.hammer_R angles with its REF_X haft point at ref (rest world)."""
    return rig.hammer_pose(HM.hammer_R(yaw, pitch, roll), ref, REF_X)


def snap(frames, k, pose):
    frames[k] = {p: m.copy() for p, m in pose.items()}


def max_diff(A, B):
    return max(float(np.abs(A[p] - B[p]).max()) for p in HM.PARTS)


def lag_hammer(rig, chest_at, t, H_chest, lam, gain=1.0, eps=1e-5):
    """Hammer that trails the chest: its chest-space pose H_chest is carried by the chest, minus
    gain * lam * (the chest's velocity at the hammer). First-order lag, exactly zero whenever the
    chest is momentarily still (so loop frame 0 stays the carry pose)."""
    D0, D1 = chest_at(t - eps), chest_at(t + eps)
    Dt = chest_at(t)
    p_rest = HM.xf(H_chest, rig.HO + rig.HA * REF_X)
    v = (HM.xf(D1, p_rest) - HM.xf(D0, p_rest)) / (2 * eps)
    q = HM.q_of(D1[:3, :3] @ D0[:3, :3].T)
    ang = 2 * math.atan2(np.linalg.norm(q[1:]), q[0])
    axis = q[1:] / max(1e-12, np.linalg.norm(q[1:]))
    w = axis * ang / (2 * eps)                                      # world angular velocity (rad/s)
    k = gain * lam
    p = HM.xf(Dt, p_rest)
    wn = np.linalg.norm(w)
    turn = HM.axis_angle(w, -math.degrees(wn) * k) if wn > 1e-9 else np.eye(3)
    return HM.tr(-v * k) @ HM.about(p, turn) @ Dt @ H_chest


def smooth_periodic(u, rise=0.4):
    """0 at u = 0 and 1 (zero slope), 1 at u = rise: a quick inhale and a slow exhale."""
    u = u % 1.0
    return HM.smooth(u / rise) if u < rise else 1.0 - HM.smooth((u - rise) / (1 - rise))


# ================================================================== IDLE
IDLE_FPS = 24
IDLE_DESIGN = {'breath': 4.2, 'sink': 0.085, 'shift': 0.15, 'head_nod': -1.5, 'slide': 0.15}


def idle(rig, carry, fps=IDLE_FPS, duration=3.0, design=None):
    """Heavy breathing (two breaths), a slow weight shift onto the left leg and back, the head and
    the hammer settling a beat after the body. Frame 0 is the carry pose exactly (the shared start
    and end pose of every original attack)."""
    dz = dict(IDLE_DESIGN, **(design or {}))
    N = int(round(duration * fps))
    period = duration
    w = lambda t: 0.5 * (1 - math.cos(2 * math.pi * t / period))            # slow sink + shift
    s1 = lambda t: w(t) * math.sin(2 * math.pi * t / period)                 # asymmetric drift
    b = lambda t: smooth_periodic(t / (period / 2), 0.38)                    # breath (2 per loop)

    def ch(t):
        return {'pz': -dz['sink'] * w(t) - 0.022 * b(t), 'px': dz['shift'] * w(t), 'py': 0.03 * w(t),
                'pr': 1.5 * w(t), 'pp': 0.8 * w(t), 'pyw': -2.0 * s1(t),
                'cp': -dz['breath'] * b(t) + 1.6 * w(t), 'cr': -1.1 * w(t), 'cy': 3.0 * s1(t),
                'hp': 0.0, 'hr': 0.0, 'hy': 0.0}

    def head(t, c):
        # the head counters the chest and trails it (velocity lag), with a slow look to his right
        e = 1e-5
        cp_v = (ch(t + e)['cp'] - ch(t - e)['cp']) / (2 * e)
        cy_v = (ch(t + e)['cy'] - ch(t - e)['cy']) / (2 * e)
        return {'hp': -0.55 * c['cp'] + 0.07 * cp_v + 1.5 * w(t) + dz['head_nod'] * b(t),
                'hy': -0.6 * c['cy'] + 0.075 * cy_v - 3.0 * s1(t), 'hr': 0.5 * w(t)}

    def body_at(t):
        c = ch(t)
        c.update(head(t, c))
        return body_from(rig, c)
    chest_at = lambda t: body_at(t)['UpperTorso']
    K_H = carry.K['Hammer']
    frames, moved, legerr = [], [], 0.0
    for f in range(N + 1):
        t = f / fps
        pose = {HM.ROOT: np.eye(4), **body_at(t)}
        # the hands carry a third of the chest's motion, a beat late, and lift a little as he sinks
        # (the arms absorb the rest), so the low hammer head never dips toward the ground or his toe
        Hf = lag_hammer(rig, chest_at, t, K_H, lam=0.25, gain=1.5)
        pose['Hammer'] = HM.tr([0.0, -0.12 * w(t), 0.06 * w(t)]) @ HM.cf_lerp(K_H, Hf, 0.35)
        for sd in HM.SIDES:
            pose[sd + 'Foot'] = np.eye(4)
            pose[sd + 'UpperLeg'], pose[sd + 'LowerLeg'], err = carry.legs(pose, sd)
            legerr = max(legerr, err)
        P, m = carry.arms(pose, {'Right': dz['slide'] * w(t)})
        frames.append(P)
        moved.append(m)
    ends = (max_diff(frames[0], carry.K), max_diff(frames[N], carry.K))
    assert max(ends) < 1e-4, 'Idle frame 0 / %d drift from the carry pose: %s' % (N, ends)
    snap(frames, 0, carry.K)
    snap(frames, N, carry.K)
    planted = [{sd: rig.head[sd + 'Foot'] for sd in HM.SIDES} for _ in range(N + 1)]
    return Clip('Idle', fps, True, frames, {'planted': planted, 'reachMove': max(moved), 'legError': legerr,
                                             'endsBeforeSnap': ends})


# ================================================================== WALK
WALK_FPS = 24
CHASE_SPEED = 20.0
GAME_SCALE = 1.15
WALK_DESIGN = {
    'frames': 16, 'duty': 0.34, 'touchdown_ankle_y': -2.0, 'roll': 0.8, 'heel': 50.0, 'lift': 1.15,
    'pz': (-0.66, 0.17),
    'out_toe': 6.0,
    # the approved raised carry (template rest carry raised and pushed forward in chest space,
    # clear of the knees), then shifted out to his right and the head tipped up (clear of the
    # swinging right foot, also through the game's Walk -> attack blend)
    'carry': {'yaw': -82.0, 'pitch': 2.0, 'ref_offset': [-0.1, -1.3, 1.3]},
    'carry_shift': [-0.4, 0.0, 0.0], 'carry_tilt': -6.0,
    'hammer_lag': 0.09, 'bounce': 0.11, 'tilt': -3.5, 'sway': 2.5,
}


def walk(rig, carry, fps=WALK_FPS, design=None):
    """Lumbering, stomping chase run authored at 17.39 studs/s at template scale 1.0 (the 2026-10-04
    sample's 20 studs/s at scale 1.15; the runtime paces it by ground covered, one strideLength per
    cycle, so the game's scale 1.5 and chase speed only change its playback rate). Each foot is planted (pinned in the
    world) for `duty` of the cycle, lands flat and rolls up onto the toe edge; the pelvis bobs low at
    mid-stance, sways over the planted foot and turns with the forward leg while the shoulders
    counter-rotate. The hammer is carried low across the front in the carry pose's grip, raised
    clear of the knees, and bounces and sways a beat after the body."""
    d = dict(WALK_DESIGN, **(design or {}))
    N = d['frames']
    duty = d['duty']
    T = N / fps
    v = CHASE_SPEED / GAME_SCALE
    stride = v * T
    stance = stride * duty
    toe_rest = {sd: np.array([(-1 if sd == 'Right' else 1) * 1.947, rig.pmin[sd + 'Foot'][1], 0.0]) for sd in HM.SIDES}
    ank_rest = {sd: rig.head[sd + 'Foot'] for sd in HM.SIDES}
    ROLL, HEEL, LIFT, out_toe = d['roll'], d['heel'], d['lift'], d['out_toe']

    def foot_flat(sd, toe_y, pitch):
        """Foot D with its toe edge on the ground at root-space y = toe_y, heel raised by pitch."""
        s = -1 if sd == 'Right' else 1
        toe = toe_rest[sd]
        R = HM.rz(s * out_toe) @ HM.rx(pitch)
        return HM.tf(R, np.array([toe[0], toe_y, 0.0]) - R @ toe)

    toe_td = d['touchdown_ankle_y'] + (toe_rest['Right'][1] - ank_rest['Right'][1])

    def contact(sd, u):
        """u in [0, 1] through the contact: the toe edge travels back at v (pinned in the world)."""
        q = max(0.0, (u - (1 - ROLL)) / ROLL)
        return foot_flat(sd, toe_td + stance * u, HEEL * q * q)

    def swing(sd, u):
        """u in [0, 1] through the swing: Hermite ankle path from lift-off to the next touchdown."""
        F0, F1 = contact(sd, 1.0), contact(sd, 0.0)
        a0, a1 = HM.xf(F0, ank_rest[sd]), HM.xf(F1, ank_rest[sd])
        dur = (1 - duty) * T
        e = 1e-4
        v0 = (a0 - HM.xf(contact(sd, 1.0 - e), ank_rest[sd])) / (e * duty * T) * dur
        v1 = np.array([0.0, v * dur * 0.6, -2.6])          # stomp: falling, moving back with the ground
        y = HM.hermite(a0[1], a1[1], v0[1], v1[1], u)
        x = HM.hermite(a0[0], a1[0], 0.0, 0.0, u)
        zk = Track([(0, a0[2]), (0.38, ank_rest[sd][2] + LIFT), (0.78, ank_rest[sd][2] + 0.55), (1.0, a1[2])])
        zk.m[0] = np.asarray(v0[2])
        zk.m[-1] = np.asarray(v1[2])
        z = float(zk(u))
        pitch = float(Track([(0, HEEL), (0.28, 52.0), (0.65, 6.0), (0.88, -9.0), (1.0, 0.0)])(u))
        s = -1 if sd == 'Right' else 1
        R = HM.rz(s * out_toe) @ HM.rx(pitch)
        return HM.tf(R, np.array([x, y, z]) - R @ ank_rest[sd])

    def foot(sd, phi):
        local = (phi - (0.0 if sd == 'Right' else 0.5)) % 1.0
        if local < duty:
            return contact(sd, local / duty), toe_rest[sd]
        return swing(sd, (local - duty) / (1 - duty)), None

    cyc = lambda phi, k, ph: math.cos(2 * math.pi * k * (phi - ph))
    mid_r = duty / 2

    def ch(phi):
        return {
            'pz': d['pz'][0] - d['pz'][1] * cyc(phi, 2, mid_r) - 0.03 * cyc(phi, 1, mid_r),
            'px': -0.13 * cyc(phi, 1, mid_r),
            'py': 0.05 * cyc(phi, 2, mid_r + 0.08),
            'pp': 8.0 + 2.0 * cyc(phi, 2, mid_r + 0.06),
            'pr': -3.0 * cyc(phi, 1, mid_r),
            'pyw': 7.0 * cyc(phi, 1, 0.0),
            'cp': 11.0 + 2.5 * cyc(phi, 2, mid_r + 0.12),
            'cr': 2.2 * cyc(phi, 1, mid_r + 0.05),
            'cy': -9.0 * cyc(phi, 1, 0.04),
            'hp': -12.0 - 2.2 * cyc(phi, 2, mid_r + 0.2),
            'hr': -1.0 * cyc(phi, 1, mid_r + 0.1),
            'hy': 6.0 * cyc(phi, 1, 0.1),
        }

    cr_ = d['carry']
    rest_ref = rig.HO + rig.HA * REF_X
    hold = hammer_world(rig, cr_['yaw'], cr_['pitch'], 0.0, rest_ref + np.array(cr_['ref_offset']))
    pivot = HM.xf(hold, rest_ref)
    hold = HM.tr(d['carry_shift']) @ HM.about(pivot, HM.rx(d['carry_tilt'])) @ hold
    pivot = HM.xf(hold, rest_ref)

    def secondary(phi):
        """The hammer's bounce (the head dips a beat after each footfall) and sway, in chest space."""
        lp = phi - d['hammer_lag']
        bounce = d['bounce'] * cyc(lp, 2, mid_r)
        turn = HM.rx(d['tilt'] * cyc(lp, 2, mid_r + 0.05)) @ HM.rz(d['sway'] * cyc(lp, 1, 0.05))
        return HM.tr([0, 0, -bounce]) @ HM.about(pivot, turn)

    frames, planted, moved = [], [], []
    for f in range(N):
        phi = f / N
        pose = {HM.ROOT: np.eye(4), **body_from(rig, ch(phi))}
        pose['Hammer'] = pose['UpperTorso'] @ secondary(phi) @ hold
        pl = {}
        for sd in HM.SIDES:
            pose[sd + 'Foot'], pl[sd] = foot(sd, phi)
            Dt, Ds, _, _ = HM.leg_ik(rig, sd, pose['LowerTorso'], pose[sd + 'Foot'], 6.0)
            pose[sd + 'UpperLeg'], pose[sd + 'LowerLeg'] = Dt, Ds
        P, m = carry.arms(pose)
        frames.append(P)
        planted.append(pl)
        moved.append(m)
    frames.append({p: m.copy() for p, m in frames[0].items()})
    planted.append(planted[0])
    root = lambda t: np.array([0.0, -v * t, 0.0])
    return Clip('Walk', fps, True, frames, {'planted': planted, 'root_motion': root, 'strideLength': stride,
                                             'nominalSpeed': v, 'cycle': T, 'duty': duty,
                                             'reachMove': max(moved)})
