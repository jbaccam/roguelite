"""Hammer boss clips (pure numpy): one function per clip.

Each clip function returns a Clip: per-frame pose dicts (part -> 4x4 D, see hm_motion) plus the
metadata the checks and the hand-off need (planted contacts, impact frame, root motion, timings).
Keys are written in FRAMES of the clip's own rate; Track() makes them curves.

Feel rules (plans/2026-10-03-hammer-brute-rebuild-design.md section 3): clear anticipation holds,
fast eased strikes, weight in the hips and knees, arcs (Hermite/Catmull-Rom keys, never linear
in-betweens), follow-through and settle, and secondary motion that lags the body (head, hammer).
"""
import math

import numpy as np

import hm_motion as HM
from hm_motion import Track

GRIP_CARRY = {'Right': 2.72, 'Left': 8.05}
GRIP_ATTACK = {'Right': 6.55, 'Left': 8.05}
REF_X = 7.3                     # haft point used to place the hammer in keys (between the attack grips)


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


def rest_ref(rig):
    return rig.HO + rig.HA * REF_X


def core_penalty(rig):
    """Soft cost for an elbow/forearm sinking into the chest core deeper than at rest (ArmPlan)."""
    def f(D_chest, r):
        Ci = HM.rinv(D_chest)
        E, W = r['E'], r['W']
        tot = 0.0
        for t in (0.0, 0.35, 0.7):
            p = E * (1 - t) + W[:, None] * t
            loc = p @ Ci[:3, :3].T + Ci[:3, 3]
            q = (loc[..., 0] / 2.25) ** 2 + ((loc[..., 1] + 0.15) / 1.7) ** 2 + ((loc[..., 2] - 6.5) / 2.15) ** 2
            tot = tot + 300 * np.maximum(0, 1.15 - q) ** 2
        return tot
    return f


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


def head_clear(rig, side):
    """Soft cost for the forearm's wrist end pressing into the hammer head deeper than the template
    rest does (the right fist sits right next to the head at the carry grip)."""
    lo, hi = rig.head_box
    A = rig.arm[side]
    pts = cuff_points(rig, side)

    def depth(D_ham, P):
        loc = (HM.xf(HM.rinv(D_ham), P) - rig.HO) @ rig.HR
        d = np.minimum((loc - lo).min(-1), (hi - loc).min(-1))
        return np.maximum(d, 0).max(-1)
    if pts is None:
        return (lambda D_chest, D_ham, g, r: 0.0), 0.0
    rest = float(depth(np.eye(4), pts))

    def f(D_chest, D_ham, g, r):
        Rf, E = r['Rf'], r['E']                                  # (nr,ns,3,3), (nr,ns,3)
        P = np.einsum('rsij,nj->rsni', Rf, pts - A['e0']) + E[:, :, None, :]
        return 60000 * np.maximum(0, depth(D_ham, P) - rest - 0.005) ** 2
    return f, rest


def plan_arms(rig, chests, hammers, slides, start=None, end=None, periodic=False, smooth_w=1.0, extra=None):
    states = {}
    for s in HM.SIDES:
        plan = HM.ArmPlan(rig, s, smooth_w=smooth_w, core=core_penalty(rig))
        frames = [(c, h, sl[s]) for c, h, sl in zip(chests, hammers, slides)]
        st = start[s] if start else None
        en = end[s] if end else None
        ex = extra.get(s) if extra else head_clear(rig, s)[0]
        states[s] = plan.plan(frames, st, en, periodic, ex)
    return [{s: tuple(states[s][k]) for s in HM.SIDES} for k in range(len(chests))]


def assemble(rig, bodies, hammers, slides, feet, arm_states, knee_out=6.0):
    frames, diags = [], []
    for b, h, sl, ft, st in zip(bodies, hammers, slides, feet, arm_states):
        P, d = HM.compose(rig, b, h, sl, st, ft, knee_out)
        frames.append(P)
        diags.append(d)
    return frames, diags


def snap_rest(frames, k):
    frames[k] = {p: np.eye(4) for p in frames[k]}


# ================================================================== SLAM


def hammer_world(rig, yaw, pitch, roll, ref):
    return rig.hammer_pose(HM.hammer_R(yaw, pitch, roll), ref, REF_X)


def chest_params(rig, D_chest, D_ham):
    """(yaw, pitch, roll, ref) of a hammer pose expressed in chest space (the chest's rest frame)."""
    H = HM.rinv(D_chest) @ D_ham
    Rw = H[:3, :3] @ rig.HR                        # hammer-local -> chest-rest world
    F0 = np.array([[0, -1.0, 0], [1.0, 0, 0], [0, 0, 1.0]])
    M = Rw @ np.linalg.inv(F0)                    # = rz(yaw) rx(pitch) F0 rx(roll) F0^-1
    # local x direction gives yaw/pitch: Rw[:,0] = rz(yaw) rx(pitch) (0,1,0)
    d = Rw[:, 0]
    pitch = math.degrees(math.asin(max(-1, min(1, d[2]))))
    yaw = math.degrees(math.atan2(-d[0], d[1]))
    base = HM.hammer_R(yaw, pitch, 0.0)
    rr = base.T @ Rw
    roll = math.degrees(math.atan2(rr[2, 1], rr[1, 1]))
    ref = HM.xf(H, rig.HO + rig.HA * REF_X)
    return np.array([yaw, pitch, roll]), ref


# Slam design. Times in SECONDS. Body channels (see body_from) and the hammer keyed in CHEST space:
# (time, [yaw, pitch, roll], ref point (chest rest frame)), or (time, ('w', angles), world ref) for a
# world pose, or a world target name; the last item is the segment mode (see Track).
SLAM_FPS = 30
SLAM_DESIGN = {
    'duration': 1.4667, 'impact': 0.70,
    'head_impact': [-1.0, -10.8, 2.21],
    'body': {
        'pz': [(0, 0, 'hold'), (0.17, -0.25), (0.30, -0.42), (0.40, -0.56, 'hold'), (0.50, -0.6, 'in'),
               (0.70, -1.0, 'out'), (0.75, -1.08), (0.83, -1.02), (1.0, -0.9), (1.17, -0.6), (1.4667, 0, 'hold')],
        'py': [(0, 0, 'hold'), (0.21, 0.15), (0.40, 0.3, 'hold'), (0.50, 0.32, 'in'), (0.70, 0.95, 'out'),
               (0.79, 0.98), (0.92, 0.92), (1.17, 0.5), (1.4667, 0, 'hold')],
        'pp': [(0, 0, 'hold'), (0.29, -2.0), (0.40, -2.5, 'hold'), (0.50, -2.5, 'in'), (0.70, 14.0, 'out'),
               (0.79, 15.0), (0.96, 13.0), (1.21, 6.0), (1.4667, 0, 'hold')],
        'pyw': [(0, 0, 'hold'), (0.12, -3.0), (0.33, -1.0), (0.50, 0.0, 'in'), (0.70, 0.0), (1.08, -4.0),
                (1.4667, 0, 'hold')],
        'cp': [(0, 0, 'hold'), (0.12, 0.5), (0.27, -4.0), (0.40, -7.0, 'hold'), (0.50, -8.0, 'in'),
               (0.70, 46.0, 'out'), (0.77, 49.0), (0.875, 45.0), (1.04, 35.0), (1.25, 14.0), (1.4667, 0, 'hold')],
        'cy': [(0, 0, 'hold'), (0.12, -5.0), (0.30, -1.5), (0.50, 0.0, 'in'), (0.70, 0.0), (1.08, -8.0),
               (1.4667, 0, 'hold')],
        'cr': [(0, 0, 'hold'), (0.17, -3.0), (0.375, 0.0), (1.4667, 0, 'hold')],
        'hp': [(0, 0, 'hold'), (0.17, -3.0), (0.33, 5.0), (0.46, 8.0), (0.54, 7.0), (0.70, -22.0), (0.79, -26.0),
               (0.92, -21.0), (1.125, -10.0), (1.33, -2.0), (1.4667, 0, 'hold')],
        'hy': [(0, 0, 'hold'), (0.21, 6.0), (0.42, 2.0), (0.70, 0.0), (1.125, 4.0), (1.4667, 0, 'hold')],
    },
    'hammer': [
        (0, [-90.0, 13.0, 0.0], 'rest', 'hold'),
        (0.14, [-55.0, -1.0, 0.0], [1.85, -2.5, 4.85]),
        (0.27, [-14.0, -35.0, 0.0], [0.8, -3.8, 6.75]),
        (0.40, [0.0, -80.0, 0.0], [-1.6, -3.6, 9.3], 'hold'),
        (0.50, [0.0, -84.0, 0.0], [-1.6, -3.5, 9.4], 'hold'),
        (0.6667, 'impact', 'impact', 'hold'),
        (0.70, 'impact', 'impact', 'out'),
        (0.7917, 'bounce', 'bounce', 'hold'),
        (0.875, 'settle', 'settle'),
        (0.96, ('w', [-8.0, -14.0, 0.0]), [-1.5, -4.0, 3.5]),
        (1.083, ('w', [-35.0, -6.0, 0.0]), [-0.5, -3.1, 2.6]),
        (1.208, ('w', [-65.0, 4.0, 0.0]), [2.5, -3.4, 3.4]),
        (1.4667, [-90.0, 13.0, 0.0], 'rest', 'hold'),
    ],
    # world targets: (pitch, yaw, offset of the REF point from its impact position); converted to chest
    # space at their own time ('impact' keyed at 0.667 uses the impact-time chest: the arms lock first)
    'world': {'impact': (0.0, 0.0, [0, 0, 0]), 'bounce': (-7.0, 0.0, [0, 0.05, 0.28]),
              'settle': (-0.8, 0.0, [0, 0, 0.03])},
    'world_at': {'impact': 0.70},
    'slide': [(0, 2.72, 'hold'), (0.08, 3.2), (0.30, 6.55, 'hold'), (0.96, 6.55, 'hold'), (1.33, 2.72, 'hold'), (1.4667, 2.72)],
    'timing': {'warnStart': 0.17, 'recoveryEnd': 1.29},
    'retime': [],
    # (first key, last key, ramp in, ramp out): path keys traversed with a trapezoid speed
    'paths': [(0, 3, 0.23, 0.12)],     # tuned by an in-between drift search (README)
}


def retime(keys, i0, i1, lead=1.0):
    """Re-space the interior keys between keys[i0] and keys[i1] in time so each segment's duration is
    proportional to its hammer rotation (degrees), with the first and last segments stretched by
    `lead` for the ease in/out. keys: list of (t, angles, ref, *mode)."""
    def rot(a, b):
        return HM.rot_angle(HM.hammer_R(*a).T @ HM.hammer_R(*b))
    w = [rot(keys[i][1], keys[i + 1][1]) + 1e-3 for i in range(i0, i1)]
    if len(w) > 1:
        w[0] *= lead
        w[-1] *= lead
    t0, t1 = keys[i0][0], keys[i1][0]
    acc = np.cumsum([0.0] + w)
    out = list(keys)
    for j, i in enumerate(range(i0, i1 + 1)):
        k = list(keys[i])
        k[0] = t0 + (t1 - t0) * acc[j] / acc[-1]
        out[i] = tuple(k)
    return out


def slam_inputs(rig, fps=SLAM_FPS, design=None):
    """Bodies, hammers, slides and feet per frame from the design (no arm planning)."""
    import copy
    d = copy.deepcopy(design or SLAM_DESIGN)
    N = int(round(d['duration'] * fps))
    T = lambda f: f / fps
    tracks = {k: Track([(t, v, *m) for t, v, *m in keys]) for k, keys in d['body'].items()}
    bodies = [body_from(rig, {k: float(tr_(T(f))) for k, tr_ in tracks.items()}) for f in range(N + 1)]
    body_at = lambda t: body_from(rig, {k: float(tr_(t)) for k, tr_ in tracks.items()})
    head_imp = np.array(d['head_impact'], float)
    keys = []
    for t, a, r, *m in d['hammer']:
        if isinstance(a, str):
            pitch, yaw, off = d['world'][a]
            W = hammer_world(rig, yaw, pitch, 0.0, head_imp + np.array([0, REF_X, 0]) + np.array(off, float))
            at = d.get('world_at', {}).get(a, t)
            ang, ref = chest_params(rig, body_at(at)['UpperTorso'], W)
            keys.append((t, list(ang), ref, *m))
        elif isinstance(a, tuple):
            W = hammer_world(rig, *a[1], np.array(r, float))
            ang, ref = chest_params(rig, body_at(t)['UpperTorso'], W)
            keys.append((t, list(ang), ref, *m))
        else:
            keys.append((t, a, rest_ref(rig) if isinstance(r, str) else r, *m))
    for i0, i1, lead in d.get('retime', []):
        keys = retime(keys, i0, i1, lead)
    A = Track([(t, a, *m) for t, a, r, *m in keys])
    R = Track([(t, r, *m) for t, a, r, *m in keys])
    paths = []
    for i0, i1, ra, rb in d.get('paths', []):
        seg = keys[i0:i1 + 1]
        w = [HM.rot_angle(HM.hammer_R(*seg[j][1]).T @ HM.hammer_R(*seg[j + 1][1])) + 2.0 * float(
            np.linalg.norm(np.asarray(seg[j + 1][2]) - np.asarray(seg[j][2]))) for j in range(len(seg) - 1)]
        paths.append((seg[0][0], seg[-1][0],
                      HM.PathTrack([k[1] for k in seg], w, seg[0][0], seg[-1][0], ra, rb),
                      HM.PathTrack([k[2] for k in seg], w, seg[0][0], seg[-1][0], ra, rb)))

    def hammer_at(t):
        for t0, t1, pa, pr in paths:
            if t0 <= t <= t1:
                return pa(t), pr(t)
        return A(t), R(t)
    slideR = Track([(t, v, *m) for t, v, *m in d['slide']])
    hammers, slides, feet = [], [], []
    for f in range(N + 1):
        (yaw, pitch, roll), ref = hammer_at(T(f))
        hammers.append(bodies[f]['UpperTorso'] @ hammer_world(rig, yaw, pitch, roll, ref))
        slides.append({'Right': float(slideR(T(f))), 'Left': 8.05})
        feet.append({sd: np.eye(4) for sd in HM.SIDES})
    return d, N, bodies, hammers, slides, feet


def slam(rig, fps=SLAM_FPS, design=None):
    """Overhead two-hand slam. The head swings round to the front while the right hand slides down
    the haft, a crouch while the hammer rises overhead, a held anticipation at the top, then a fast
    eased drop: the arms bring the hammer over first and the torso whips forward last, landing the
    lower striking face flat on the ground in front at impact. The body compresses, the hammer
    bounces a little, then recovery with overlap (hammer first, torso after, head last).

    The hammer is keyed in CHEST space (it rides the torso like the arms do), so the torso's
    whip carries hands and hammer together and the client's per-joint lerp keeps the grip."""
    d, N, bodies, hammers, slides, feet = slam_inputs(rig, fps, design)
    IMP = int(round(d['impact'] * fps))
    rest = {sd: (0.0, 0.0) for sd in HM.SIDES}
    arm_states = plan_arms(rig, [b['UpperTorso'] for b in bodies], hammers, slides, start=rest, end=rest)
    frames, diags = assemble(rig, bodies, hammers, slides, feet, arm_states)
    snap_rest(frames, 0)
    snap_rest(frames, N)
    planted = [{sd: rig.head[sd + 'Foot'] for sd in HM.SIDES} for _ in range(N + 1)]
    meta = {'impact': IMP, 'planted': planted, 'arm_states': arm_states, 'diags': diags,
            'warnStart': d['timing']['warnStart'], 'activeEnd': IMP / fps,
            'recoveryEnd': d['timing']['recoveryEnd'], 'design': d}
    return Clip('Slam', fps, False, frames, meta)


# ================================================================== shared periodic helpers
def lag_hammer(rig, chest_at, t, H_chest, lam, gain=1.0, eps=1e-3):
    """Hammer that trails the chest: its chest-space pose H_chest is carried by the chest, minus
    gain * lam * (the chest's velocity at the hammer). First-order lag, exactly zero whenever the
    chest is momentarily still (so loop frame 0 stays the template rest)."""
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
IDLE_DESIGN = {'breath': 4.2, 'sink': 0.085, 'shift': 0.15, 'head_nod': -1.5}


def idle(rig, fps=IDLE_FPS, duration=3.0, design=None):
    """Heavy breathing (two breaths), a slow weight shift onto the left leg and back, the head and
    the hammer settling a beat after the body. Frame 0 is the template rest (the shared start pose
    every attack starts and ends on): standing tallest, legs straight, hammer low across the front."""
    dz = dict(IDLE_DESIGN, **(design or {}))
    N = int(round(duration * fps))
    P = duration
    w = lambda t: 0.5 * (1 - math.cos(2 * math.pi * t / P))                 # slow sink + shift
    s1 = lambda t: w(t) * math.sin(2 * math.pi * t / P)                      # asymmetric drift
    b = lambda t: smooth_periodic(t / (P / 2), 0.38)                         # breath (2 per loop)

    def ch(t):
        return {'pz': -dz['sink'] * w(t) - 0.022 * b(t), 'px': dz['shift'] * w(t), 'py': 0.03 * w(t),
                'pr': 1.5 * w(t), 'pp': 0.8 * w(t), 'pyw': -2.0 * s1(t),
                'cp': -dz['breath'] * b(t) + 1.6 * w(t), 'cr': -1.1 * w(t), 'cy': 3.0 * s1(t),
                'hp': 0.0, 'hr': 0.0, 'hy': 0.0}

    def head(t, c):
        # the head counters the chest and trails it (velocity lag), with a slow look to his right
        e = 1e-3
        cp_v = (ch(t + e)['cp'] - ch(t - e)['cp']) / (2 * e)
        cy_v = (ch(t + e)['cy'] - ch(t - e)['cy']) / (2 * e)
        return {'hp': -0.55 * c['cp'] + 0.07 * cp_v + 1.5 * w(t) + dz['head_nod'] * b(t),
                'hy': -0.6 * c['cy'] + 0.075 * cy_v - 3.0 * s1(t), 'hr': 0.5 * w(t)}

    def body_at(t):
        c = ch(t)
        c.update(head(t, c))
        return body_from(rig, c)
    chest_at = lambda t: body_at(t)['UpperTorso']
    bodies, hammers, slides, feet = [], [], [], []
    H_rest = np.eye(4)
    for f in range(N + 1):
        t = f / fps
        bodies.append(body_at(t))
        # the hands carry a third of the chest's motion, a beat late, and lift a little as he sinks
        # (the arms absorb the rest), so the low hammer head never dips toward the ground or his toe
        Hf = lag_hammer(rig, chest_at, t, H_rest, lam=0.25, gain=1.5)
        H = HM.cf_lerp(H_rest, Hf, 0.35)
        hammers.append(HM.tr([0.0, -0.12 * w(t), 0.06 * w(t)]) @ H)
        slides.append(dict(GRIP_CARRY))
        feet.append({sd: np.eye(4) for sd in HM.SIDES})
    rest = {sd: (0.0, 0.0) for sd in HM.SIDES}
    arm_states = plan_arms(rig, [bd['UpperTorso'] for bd in bodies], hammers, slides, start=rest, end=rest)
    frames, diags = assemble(rig, bodies, hammers, slides, feet, arm_states)
    snap_rest(frames, 0)
    snap_rest(frames, N)
    planted = [{sd: rig.head[sd + 'Foot'] for sd in HM.SIDES} for _ in range(N + 1)]
    return Clip('Idle', fps, True, frames, {'planted': planted, 'arm_states': arm_states, 'diags': diags})


# ================================================================== WALK
WALK_FPS = 24
CHASE_SPEED = 20.0
GAME_SCALE = 1.15
WALK_DESIGN = {
    'frames': 16, 'duty': 0.34, 'touchdown_ankle_y': -2.0, 'roll': 0.8, 'heel': 50.0, 'lift': 1.15,
    'pz': (-0.66, 0.17),
    'out_toe': 6.0,
    # carry: the template rest carry, raised and pushed forward in chest space (clear of the knees)
    'carry': {'yaw': -82.0, 'pitch': 2.0, 'ref_offset': [-0.1, -1.3, 1.3]},
    'hammer_lag': 0.09, 'bounce': 0.11, 'tilt': -3.5, 'sway': 2.5,
}


def walk(rig, fps=WALK_FPS, design=None):
    """Lumbering, stomping chase run authored at the in-game chase speed (20 studs/s at scale 1.15,
    so 17.39 studs/s here). Each foot is planted (pinned in the world) for `duty` of the cycle, lands
    flat and rolls up onto the toe edge; the pelvis bobs low at mid-stance, sways over the planted
    foot and turns with the forward leg while the shoulders counter-rotate. The hammer is carried
    low in both hands and bounces a beat after the body."""
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
    carry = hammer_world(rig, cr_['yaw'], cr_['pitch'], 0.0, rest_ref(rig) + np.array(cr_['ref_offset']))
    pivot = rig.HO + rig.HA * REF_X

    def hammer_at(phi, chest):
        lp = phi - d['hammer_lag']
        bounce = d['bounce'] * cyc(lp, 2, mid_r)               # the head dips a beat after each footfall
        turn = HM.rx(d['tilt'] * cyc(lp, 2, mid_r + 0.05)) @ HM.rz(d['sway'] * cyc(lp, 1, 0.05))
        return chest @ HM.tr([0, 0, -bounce]) @ HM.about(HM.xf(carry, pivot), turn) @ carry

    bodies, hammers, slides, feet, planted = [], [], [], [], []
    for f in range(N):
        phi = f / N
        b = body_from(rig, ch(phi))
        bodies.append(b)
        hammers.append(hammer_at(phi, b['UpperTorso']))
        slides.append(dict(GRIP_CARRY))
        ft, pl = {}, {}
        for sd in HM.SIDES:
            ft[sd], pl[sd] = foot(sd, phi)
        feet.append(ft)
        planted.append(pl)
    arm_states = plan_arms(rig, [bd['UpperTorso'] for bd in bodies], hammers, slides, periodic=True)
    frames, diags = assemble(rig, bodies, hammers, slides, feet, arm_states)
    frames.append({p: m.copy() for p, m in frames[0].items()})
    diags.append(diags[0])
    arm_states.append(arm_states[0])
    planted.append(planted[0])
    root = lambda t: np.array([0.0, -v * t, 0.0])
    return Clip('Walk', fps, True, frames, {'planted': planted, 'arm_states': arm_states, 'diags': diags,
                                             'root_motion': root, 'strideLength': stride, 'nominalSpeed': v,
                                             'cycle': T, 'duty': duty})
