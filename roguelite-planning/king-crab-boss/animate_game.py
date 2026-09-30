"""King Crab game package: clips, timing data and the Studio import FBX.

Run under Blender 5.2, headless, after build_king_crab.py:
    blender -b --factory-startup --python animate_game.py

Self-contained. It opens this folder's KingCrab.blend (the approved model, rig
and textures, none of which change), authors the game clips at 24 fps and
writes, per plans/BOSS_GAME_PACKAGE_SPEC.md:
    exports/game/AnimationData.json    sampled matrix_basis per bone per frame
    exports/game/BossGameData.json     attack timings, hit points, strides
    exports/game/GameChecks.json       foot drift, ground clearance, IK error
    exports/game/KingCrab_Studio.fbx   rest mesh + deform armature, 1024 maps
    exports/game/KingCrab_Studio.fbm/  the same PNGs beside it
    previews/GameClips.png, previews/ClawCrush.mp4, Rush.mp4, BubbleBarrage.mp4
and saves the clips as actions in KingCrab.blend.

How the motion is made
- Poses are composed per frame as matrix_basis values. The body is posed as a
  world-space move/turn about its centre; claws and face use local rotations.
- Every leg is solved each frame by damped least squares on an analytic FK of
  its 4-bone chain (warm-started from the previous frame), so planted feet
  stay exactly where they were put. Locomotion clips are in place: planted
  feet move backward at the travel speed, so in the world (root moving at
  nominalSpeed) they do not slide. The residual is logged as foot drift.
- The crusher's ClawCrush arc is solved the same way for position and
  orientation of the hand, so the palm follows a real arc and lands flat.
- Non-looping clips start and end exactly on the Idle start pose (the rest
  pose); looping clips close exactly.
"""
import bpy, json, math, os, shutil, time
import numpy as np
from pathlib import Path
from mathutils import Vector, Matrix, Euler, Quaternion

T0 = time.time()
OUT = Path(__file__).resolve().parent
GAME = OUT / 'exports' / 'game'
GAME.mkdir(parents=True, exist_ok=True)
WORK = OUT / '_work'
WORK.mkdir(exist_ok=True)
FPS = 24
BOSS = 'KingCrab'
BOSS_ID = 'king-crab'


def log(*a):
    print(f'[{time.time() - T0:7.1f}s]', *a, flush=True)


bpy.ops.wm.open_mainfile(filepath=str(OUT / 'KingCrab.blend'))
scene = bpy.context.scene
scene.render.fps = FPS
rig = bpy.data.objects['KingCrab_Rig']
SECTIONS = ('Body', 'Eyes', 'ClawR', 'ClawL', 'Legs')
SECS = {s: bpy.data.objects[f'KingCrab_{s}'] for s in SECTIONS}
rig.animation_data_create()
rig.animation_data.action = None
rig.data.pose_position = 'POSE'
rig.location = (0, 0, 0)
for pb in rig.pose.bones:
    pb.rotation_mode = 'QUATERNION'
    pb.matrix_basis = Matrix.Identity(4)

# ------------------------------------------------------------------ rest data
ORDER = []


def _visit(b):
    ORDER.append(b.name)
    for c in b.children:
        _visit(c)


for b in rig.data.bones:
    if b.parent is None:
        _visit(b)
PAR = {b.name: (b.parent.name if b.parent else None) for b in rig.data.bones}
REST = {b.name: b.matrix_local.copy() for b in rig.data.bones}
LREST = {n: (REST[PAR[n]].inverted() @ REST[n] if PAR[n] else REST[n].copy()) for n in ORDER}
BLEN = {b.name: b.length for b in rig.data.bones}
I4 = Matrix.Identity(4)


def rotm(x=0.0, y=0.0, z=0.0):
    return Euler((x, y, z), 'XYZ').to_matrix().to_4x4()


def fk(basis):
    P = {}
    for n in ORDER:
        B = basis.get(n, I4)
        P[n] = (P[PAR[n]] @ LREST[n] @ B) if PAR[n] else (LREST[n] @ B)
    return P


def smooth(t, a=0.0, b=1.0):
    if b <= a:
        return 1.0 if t >= b else 0.0
    x = min(1.0, max(0.0, (t - a) / (b - a)))
    return x * x * (3 - 2 * x)


def lerp(a, b, t):
    return a + (b - a) * t


BODY_PIVOT = REST['Body'].translation.copy()


def body_basis(off=(0, 0, 0), yaw=0.0, pitch=0.0, roll=0.0):
    """Body moved/turned in armature space about its centre.
    pitch > 0 = nose down; roll > 0 = crab's right (-X) side up; yaw > 0 = CCW."""
    D = (Matrix.Translation(Vector(off)) @ Matrix.Translation(BODY_PIVOT) @ rotm(0, 0, yaw)
         @ rotm(pitch, 0, 0) @ rotm(0, roll, 0) @ Matrix.Translation(-BODY_PIVOT))
    return REST['Body'].inverted() @ D @ REST['Body']


# ------------------------------------------------------------------- leg IK
LEG_TAGS = ['L1', 'L2', 'L3', 'L4', 'R1', 'R2', 'R3', 'R4']
GROUP_A = {'L1', 'R2', 'L3', 'R4'}
LEG_W = np.array([1.2, 1.0, 1.5, 1.5, 1.2])


def leg_chain(tag):
    return [f'Leg_{tag}_{s}' for s in ('Coxa', 'Merus', 'Carpus', 'Dactyl')]


def leg_fk(Pbody, tag, p, joints=False):
    c, m, k, d = leg_chain(tag)
    M = Pbody @ LREST[c] @ rotm(p[1], 0, p[0])
    M = M @ LREST[m] @ rotm(p[2], 0, 0)
    M = M @ LREST[k] @ rotm(p[3], 0, 0)
    knee = M.translation.copy()
    M = M @ LREST[d] @ rotm(p[4], 0, 0)
    ankle = M.translation.copy()
    tip, dd = M @ Vector((0, BLEN[d], 0)), (M.to_3x3() @ Vector((0, 1, 0)))
    if joints:
        return tip, dd, knee, ankle
    return tip, dd


def leg_basis(p):
    return [rotm(p[1], 0, p[0]), rotm(p[2], 0, 0), rotm(p[3], 0, 0), rotm(p[4], 0, 0)]


REST_BODY_P = fk({})['Body']
JOINT_MIN = {}
RT = {}
D0 = {}
for tag in LEG_TAGS:
    tp, dd, kn, an = leg_fk(REST_BODY_P, tag, [0] * 5, joints=True)
    RT[tag] = tp
    D0[tag] = dd.z
    JOINT_MIN[tag] = min(1.0, kn.z - 0.1, an.z - 0.1)


def lm(res, p0, iters=25, lam=1e-3):
    p = np.array(p0, float)
    r = res(p)
    cost = r @ r
    for _ in range(iters):
        J = np.empty((len(r), len(p)))
        for j in range(len(p)):
            dp = p.copy()
            dp[j] += 1e-4
            J[:, j] = (res(dp) - r) / 1e-4
        A = J.T @ J
        g = J.T @ r
        step = np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-9), -g)
        pn = p + step
        rn = res(pn)
        cn = rn @ rn
        if cn < cost:
            p, r, cost = pn, rn, cn
            lam = max(lam / 4, 1e-9)
            if np.linalg.norm(step) < 1e-7:
                break
        else:
            lam *= 6
            if lam > 1e8:
                break
    return p


# Leg shells are ~0.6-0.8 thick: keep knees and ankles off the sand. The floor
# sits just under each leg's own rest joint heights, so the rest pose is free.


def solve_leg(Pbody, tag, target, p0, dw=0.35, floor=0.0):
    target = Vector(target)

    def res(p):
        tip, dd, knee, ankle = leg_fk(Pbody, tag, p, joints=True)
        r = [(tip.x - target.x) / 0.004, (tip.y - target.y) / 0.004, (tip.z - target.z) / 0.004]
        r += list(p / LEG_W)
        r.append((dd.z - D0[tag]) / dw)
        jm = max(JOINT_MIN.get(tag, 0.0), floor)
        r.append(max(0.0, jm - knee.z) / 0.01)
        r.append(max(0.0, jm - ankle.z) / 0.01)
        return np.array(r)
    return lm(res, p0, iters=60)


# ---------------------------------------------------------------- claw IK
PALM_C = {'R': 2.6, 'L': 1.6}           # palm centre along the hand bone (build_king_crab CHELA)


def claw_chain(side):
    return [f'Claw_{side}_{s}' for s in ('Coxa', 'Merus', 'Carpus', 'Propodus')]


def claw_fk(Pbody, side, q):
    c, m, k, h = claw_chain(side)
    M = Pbody @ LREST[c] @ rotm(q[0], 0, q[1])
    M = M @ LREST[m] @ rotm(q[2], 0, q[3])
    M = M @ LREST[k] @ rotm(q[4], 0, 0)
    M = M @ LREST[h] @ rotm(q[5], q[6], q[7])
    return M


def claw_basis(q):
    return [rotm(q[0], 0, q[1]), rotm(q[2], 0, q[3]), rotm(q[4], 0, 0), rotm(q[5], q[6], q[7])]


def solve_claw(Pbody, side, pos, rot3, q0):
    pos = Vector(pos)

    def res(q):
        M = claw_fk(Pbody, side, q)
        palm = M @ Vector((0, PALM_C[side], 0))
        r = [(palm.x - pos.x) / 0.01, (palm.y - pos.y) / 0.01, (palm.z - pos.z) / 0.01]
        e = (rot3.transposed() @ M.to_3x3()).to_quaternion()
        if e.w < 0:
            e.negate()
        ax = Vector((e.x, e.y, e.z)) * 2.0
        r += [ax.x / 0.03, ax.y / 0.03, ax.z / 0.03]
        r += list(q / 1.6)
        return np.array(r)
    return lm(res, q0, iters=40)


def orient(x_axis, y_axis):
    """Rotation whose local X is x_axis and local Y is (orthogonalised) y_axis."""
    X = Vector(x_axis).normalized()
    Y = Vector(y_axis)
    Y = (Y - X * Y.dot(X)).normalized()
    Z = X.cross(Y)
    M = Matrix.Identity(3)
    for i in range(3):
        M[i][0], M[i][1], M[i][2] = X[i], Y[i], Z[i]
    return M


MX = Matrix(((-1, 0, 0), (0, 1, 0), (0, 0, 1)))


def mirror_rot(R):
    return MX @ R @ MX


def mirror_pos(v):
    return Vector((-v[0], v[1], v[2]))


REST_P = fk({})
REST_PALM = {s: REST_P[f'Claw_{s}_Propodus'] @ Vector((0, PALM_C[s], 0)) for s in ('R', 'L')}
REST_HAND_ROT = {s: REST_P[f'Claw_{s}_Propodus'].to_3x3() for s in ('R', 'L')}


# ------------------------------------------------------------ mesh sampling
def set_pose(basis):
    for pb in rig.pose.bones:
        pb.matrix_basis = basis.get(pb.name, I4)
    bpy.context.view_layer.update()


def section_verts(sec):
    dg = bpy.context.evaluated_depsgraph_get()
    ob = SECS[sec]
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    ev.to_mesh_clear()
    co = co.reshape(-1, 3)
    M = np.array(ob.matrix_world)
    return co @ M[:3, :3].T + M[:3, 3]


def min_z(secs=SECTIONS):
    return {s: float(section_verts(s)[:, 2].min()) for s in secs}


_legs = SECS['Legs']
_coxa_groups = {g.index for g in _legs.vertex_groups if g.name.endswith('_Coxa')}
COXA_MASK = np.array([any(g.group in _coxa_groups and g.weight > 0.5 for g in v.groups) for v in _legs.data.vertices])


def coxa_min_z():
    return float(section_verts('Legs')[COXA_MASK][:, 2].min())


# --------------------------------------------------------------- locomotion
WALK_T, WALK_DUTY, WALK_E, WALK_H = 1.5, 0.55, 1.5, 0.85
WALK_V = WALK_E / (WALK_DUTY * WALK_T)
RUSH_T, RUSH_DUTY, RUSH_E, RUSH_H = 0.5, 0.5, 1.1, 0.7
RUSH_V = RUSH_E / (RUSH_DUTY * RUSH_T)
TRAVEL = Vector((0, -1, 0))                 # walk forward; the rush also heads here with the body turned
RUSH_YAW = math.radians(90)                 # crab's right side (-X) turned to lead along -Y
RUSH_DROP = 0.45
RT_ROT = {t: Matrix.Rotation(RUSH_YAW, 4, 'Z') @ RT[t] for t in LEG_TAGS}


def foot_cycle(tag, phase, neutral, E, h, duty):
    ph = (phase + (0.0 if tag in GROUP_A else 0.5)) % 1.0
    if ph < duty:
        u = ph / duty
        return neutral + TRAVEL * (E / 2 - E * u), True
    u = (ph - duty) / (1 - duty)
    s = smooth(u)
    return neutral + TRAVEL * (-E / 2 + E * s) + Vector((0, 0, h * math.sin(math.pi * u))), False


def step_between(p0, p1, t, a, b, h=0.8):
    if t <= a:
        return p0.copy()
    if t >= b:
        return p1.copy()
    u = (t - a) / (b - a)
    return p0.lerp(p1, smooth(u)) + Vector((0, 0, h * math.sin(math.pi * u)))


# ------------------------------------------------------------- mouth signs
def _tooth_tip(side, x, z):
    b = {f'Maxilliped_{side}': rotm(x, 0, z)}
    P = fk(b)
    return P[f'Maxilliped_{side}'] @ Vector((0, BLEN[f'Maxilliped_{side}'], 0))


MAXI_SIGN = {}
for side in ('R', 'L'):
    t0 = _tooth_tip(side, 0, 0)
    sx = 1.0 if _tooth_tip(side, 0.3, 0).y < t0.y else -1.0          # tip swings forward = opens
    sz = 1.0 if abs(_tooth_tip(side, 0, 0.3).x) > abs(t0.x) else -1.0  # tip swings outward
    MAXI_SIGN[side] = (sx, sz)


def mouth(o):
    """Mouth plates open by o (0..1)."""
    out = {}
    for side in ('R', 'L'):
        sx, sz = MAXI_SIGN[side]
        out[f'Maxilliped_{side}'] = rotm(sx * 0.62 * o, 0, sz * 0.30 * o)
    return out


def claws_fk(side_rot):
    """side_rot: {'R': {'Coxa': (x, y, z) rad, ...}} with L mirrored (y, z negated)."""
    out = {}
    for side, segs in side_rot.items():
        for seg, (x, y, z) in segs.items():
            if side == 'L':
                y, z = -y, -z
            out[f'Claw_{side}_{seg}'] = rotm(x, y, z)
    return out


def both_claws(segs):
    return claws_fk({'R': segs, 'L': segs})


# ------------------------------------------------------------ pose composer
class Clip:
    def __init__(self, name, duration, loop):
        self.name, self.duration, self.loop = name, duration, loop
        self.frames = int(round(duration * FPS))
        self.bases = []
        self.stance = []            # per frame: {tag: (planted?, target)}
        self.meta = {}


LEG_STATE = {}
CLAW_STATE = {}


def pose_frame(body, legs, extra=None, claw_ik=None, dw=0.35, leg_blend=1.0, floor=0.0):
    """body: body_basis matrix; legs: {tag: target}; extra: {bone: basis};
    claw_ik: {side: (palm_pos, hand_rot3, blend)}."""
    B = {'Body': body}
    Pbody = fk({'Body': body})['Body']
    for tag, target in legs.items():
        p = solve_leg(Pbody, tag, target, LEG_STATE.get(tag, np.zeros(5)), dw, floor)
        LEG_STATE[tag] = p
        for n, m in zip(leg_chain(tag), leg_basis(p * leg_blend)):
            B[n] = m
    if extra:
        B.update(extra)
    if claw_ik:
        for side, (pos, rot3, blend) in claw_ik.items():
            q = solve_claw(Pbody, side, pos, rot3, CLAW_STATE.get(side, np.zeros(8)))
            CLAW_STATE[side] = q
            for n, m in zip(claw_chain(side), claw_basis(q * blend)):
                B[n] = m
    return B


def pinned():
    return {t: RT[t] for t in LEG_TAGS}


# ---------------------------------------------------------------- the clips
def clip_idle():
    c = Clip('Idle', 3.0, True)
    for f in range(c.frames + 1):
        s = f / c.frames
        w1, w2 = 2 * math.pi * s, 4 * math.pi * s
        body = body_basis((0.06 * math.sin(w1), 0.0, 0.07 * math.sin(w2)),
                          pitch=0.012 * math.sin(w2 + 0.5) - 0.012 * math.sin(0.5), roll=0.015 * math.sin(w1))
        ex = both_claws({'Merus': (0.05 * (math.sin(w2 - 0.8) + math.sin(0.8)), 0, 0),
                         'Propodus': (0.04 * (math.sin(w2 - 1.2) + math.sin(1.2)), 0, 0),
                         'Dactyl': (0.06 * (0.5 - 0.5 * math.cos(w2)), 0, 0)})
        ex.update(mouth(0.12 * (0.5 - 0.5 * math.cos(w2))))
        ex['Eye_R'] = rotm(0.08 * math.sin(w2), 0, 0.15 * math.sin(w1))
        ex['Eye_L'] = rotm(0.08 * math.sin(w2), 0, 0.15 * math.sin(w1))
        ex['EyeStalk_R'] = rotm(0.04 * math.sin(w1 - 0.5) + 0.04 * math.sin(0.5), 0, 0)
        ex['EyeStalk_L'] = rotm(0.04 * math.sin(w1 - 0.9) + 0.04 * math.sin(0.9), 0, 0)
        c.bases.append(pose_frame(body, pinned(), ex))
        c.stance.append({t: (True, RT[t]) for t in LEG_TAGS})
    return c


def clip_walk():
    c = Clip('Walk', WALK_T, True)
    for f in list(range(c.frames)) + list(range(c.frames + 1)):   # first cycle primes the IK
        if f == 0:
            c.bases, c.stance = [], []
        s = f / c.frames
        w1, w2 = 2 * math.pi * s, 4 * math.pi * s
        body = body_basis((0.05 * math.sin(w1), 0.0, -0.12 * (0.5 - 0.5 * math.cos(w2))),
                          pitch=0.015 * math.sin(w2), roll=0.035 * math.sin(w1))
        legs, st = {}, {}
        for tag in LEG_TAGS:
            tgt, planted = foot_cycle(tag, s, RT[tag], WALK_E, WALK_H, WALK_DUTY)
            legs[tag] = tgt
            st[tag] = (planted, tgt)
        ex = claws_fk({'R': {'Coxa': (0, 0, 0.05 * math.sin(w1)), 'Merus': (0.05 * math.sin(w1 + 0.5), 0, 0)},
                       'L': {'Coxa': (0, 0, -0.05 * math.sin(w1)), 'Merus': (-0.05 * math.sin(w1 + 0.5), 0, 0)}})
        ex['Eye_R'] = rotm(0, 0, 0.06 * math.sin(w1))
        ex['Eye_L'] = rotm(0, 0, 0.06 * math.sin(w1))
        c.bases.append(pose_frame(body, legs, ex))
        c.stance.append(st)
    c.meta = {'speed': WALK_V, 'stride': WALK_V * WALK_T}
    return c


def clip_hit():
    c = Clip('Hit', 11 / FPS, False)
    for f in range(c.frames + 1):
        u = f / c.frames
        e = math.sin(math.pi * u) * (1 - u) ** 0.6 * 1.6
        body = body_basis((0.0, 0.35 * e, 0.12 * e), pitch=-0.09 * e, roll=0.04 * e)
        ex = both_claws({'Merus': (0.25 * e, 0, 0), 'Dactyl': (0.35 * e, 0, 0)})
        ex.update(mouth(0.3 * e))
        ex['Brow_R'] = rotm(-0.25 * e, 0, 0)
        ex['Brow_L'] = rotm(-0.25 * e, 0, 0)
        ex['EyeStalk_R'] = rotm(-0.3 * e, 0, 0)
        ex['EyeStalk_L'] = rotm(-0.3 * e, 0, 0)
        c.bases.append(pose_frame(body, pinned(), ex))
        c.stance.append({t: (True, RT[t]) for t in LEG_TAGS})
    return c


def clip_bubbles():
    c = Clip('BubbleBarrage', 2.5, False)
    t_imp, t_end = 0.6, 2.0
    for f in range(c.frames + 1):
        t = f / FPS
        o = smooth(t, 0.1, 0.5) - smooth(t, 2.0, 2.35)
        p = 0.0
        if t_imp <= t <= t_end:
            p = math.sin(3 * math.pi * (t - t_imp) / (t_end - t_imp)) ** 2
        body = body_basis((0.0, 0.10 * p, 0.15 * o + 0.20 * p), pitch=-0.03 * o - 0.06 * p)
        ex = both_claws({'Merus': (0.12 * o, 0, 0), 'Dactyl': (0.3 * o, 0, 0)})
        ex.update(mouth(o))
        ex['EyeStalk_R'] = rotm(-0.2 * o, 0, 0)
        ex['EyeStalk_L'] = rotm(-0.2 * o, 0, 0)
        ex['Brow_R'] = rotm(0.15 * o, 0, 0)
        ex['Brow_L'] = rotm(0.15 * o, 0, 0)
        c.bases.append(pose_frame(body, pinned(), ex))
        c.stance.append({t_: (True, RT[t_]) for t_ in LEG_TAGS})
    c.meta = {'warnStart': 0.2, 'impact': t_imp, 'activeEnd': t_end, 'recoveryEnd': 2.35}
    return c


CRUSH = {'impact_f': 29, 'Pi': Vector((-3.2, -10.0, 1.9)), 'Pw': Vector((-8.6, 0.6, 10.8)),
         'Pc': Vector((-9.0, -7.6, 9.4)), 'R1_back': Vector((-1.2, 1.5, 0.0))}
RI = orient((0.0, 0.0, -1.0), (0.3, -1.0, 0.0))             # impact: outer face down, fingers forward
# The strike is a hammer chop: the hand is carried rigidly by the arm's swing about the shoulder.
# The windup hand is the impact hand swung back up to the windup palm (fingers up and back), and
# during the strike the hand only follows the swing from there (swing_rot). An independently
# authored windup orientation made the IK corkscrew the upper arm ~180 degrees in the last frames
# before impact to reach the impact orientation (the user: "his arm would rip out of his shell").
SHOULDER_R = REST_P['Claw_R_Coxa'].translation.copy()


def swing_rot(a, b):
    """Rotation carrying the shoulder->a direction onto shoulder->b (shortest arc, no twist)."""
    return (Vector(a) - SHOULDER_R).normalized().rotation_difference((Vector(b) - SHOULDER_R).normalized()).to_matrix()


# The windup (Pw) and the arc's control point (Pc) lie in the vertical plane through the shoulder
# and the impact point: the claw is raised overhead, cocked slightly back, and chopped straight
# down, so the shoulder only pitches. (The earlier Pw out to the side made the arm circle round
# the shoulder on the way down.)
_FWD = Vector((CRUSH['Pi'].x - SHOULDER_R.x, CRUSH['Pi'].y - SHOULDER_R.y, 0.0)).normalized()
CRUSH['Pw'] = SHOULDER_R + _FWD * -1.5 + Vector((0, 0, 9.0))
CRUSH['Pc'] = SHOULDER_R + _FWD * 6.0 + Vector((0, 0, 8.0))
RW = swing_rot(CRUSH['Pi'], CRUSH['Pw']) @ RI              # windup: the impact hand, swung up and back


def crush_pose(f, Pi):
    t = f / FPS
    ti = CRUSH['impact_f'] / FPS
    w = smooth(t, 0.25, 1.0)
    sm = min(1.0, max(0.0, (t - 1.0) / (ti - 1.0)))
    u = sm * sm                                       # accelerating strike
    r = smooth(t, 1.5, 2.2)
    settle = smooth(t, 0.0, 0.25) * (1 - w)
    # body: back and up for the windup, forward, down and crusher-side down at impact
    wu = dict(pitch=-0.12, roll=0.07, off=(0.0, 0.25, 0.25))
    im = dict(pitch=0.12, roll=-0.08, off=(0.0, -0.35, -0.40))
    k = u if t < ti else 1.0
    pitch = lerp(wu['pitch'] * w, im['pitch'], k) * (1 - r)
    roll = lerp(wu['roll'] * w, im['roll'], k) * (1 - r)
    off = tuple(lerp(wu['off'][i] * w, im['off'][i], k) * (1 - r) for i in range(3))
    off = (off[0], off[1], off[2] - 0.10 * settle)
    body = body_basis(off, pitch=pitch, roll=roll)
    # crusher palm path
    if t < 1.0:
        pos = REST_PALM['R'].lerp(CRUSH['Pw'], w)
        rot = REST_HAND_ROT['R'].to_quaternion().slerp(RW.to_quaternion(), w).to_matrix()
    elif t < ti:
        a, b, cc = CRUSH['Pw'], CRUSH['Pc'], Pi
        pos = a * (1 - u) ** 2 + b * 2 * u * (1 - u) + cc * u * u
        # carried by the swing (lands on RI up to the landing correction of Pi's height), with a
        # slerp to RI over the last 15% so the palm still lands exactly flat
        carried = swing_rot(a, pos) @ RW
        rot = carried.to_quaternion().slerp(RI.to_quaternion(), smooth(u, 0.85, 1.0)).to_matrix()
    else:
        pos = Pi.lerp(REST_PALM['R'], r)
        rot = RI.to_quaternion().slerp(REST_HAND_ROT['R'].to_quaternion(), r).to_matrix()
    blend = 1.0 - smooth(t, 2.05, 2.25)
    cut = claws_fk({'L': {'Coxa': (0.10 * w * (1 - r), 0, -0.15 * w * (1 - k) * (1 - r)),
                          'Merus': (0.15 * w * (1 - r), 0, 0), 'Dactyl': (0.2 * w * (1 - r), 0, 0)},
                    'R': {'Dactyl': (0.5 * w * (1 - k) * (1 - r), 0, 0)}})
    cut.update(mouth(0.35 * (smooth(t, ti - 0.1, ti) * (1 - smooth(t, 1.5, 1.9)))))
    cut['Brow_R'] = rotm(0.2 * w * (1 - r), 0, 0)
    cut['Brow_L'] = rotm(0.2 * w * (1 - r), 0, 0)
    return body, pos, rot, blend, cut


def crush_legs(t):
    """All feet planted, except the front-right leg, which steps back out of
    the crusher's path during the windup and returns in the recovery."""
    legs = pinned()
    back = RT['R1'] + CRUSH['R1_back']
    legs['R1'] = (step_between(RT['R1'], back, t, 0.35, 0.75, 0.9) if t < 1.6
                  else step_between(back, RT['R1'], t, 1.6, 2.0, 0.9))
    return legs


def clip_crush():
    c = Clip('ClawCrush', 2.25, False)
    Pi = CRUSH['Pi'].copy()
    # land the palm flat: measure the claw's lowest point at impact, adjust
    for _ in range(3):
        CLAW_STATE.clear()
        LEG_STATE.clear()
        for f in range(CRUSH['impact_f'] + 1):
            body, pos, rot, blend, cut = crush_pose(f, Pi)
            B = pose_frame(body, crush_legs(f / FPS), cut, {'R': (pos, rot, blend)})
        set_pose(B)
        mz = min_z(('ClawR',))['ClawR']
        if abs(mz - 0.02) < 0.01:
            break
        Pi = Pi + Vector((0, 0, 0.02 - mz))
    CLAW_STATE.clear()
    LEG_STATE.clear()
    for f in range(c.frames + 1):
        body, pos, rot, blend, cut = crush_pose(f, Pi)
        legs = crush_legs(f / FPS)
        c.bases.append(pose_frame(body, legs, cut, {'R': (pos, rot, blend)}))
        c.stance.append({t: (None, legs[t]) for t in LEG_TAGS})
    ti = CRUSH['impact_f'] / FPS
    c.meta = {'warnStart': 0.25, 'impact': ti, 'activeEnd': ti + 1 / FPS, 'recoveryEnd': 1.95,
              'Pi': Pi}
    return c


def rush_loop_pose(s):
    w1, w2 = 2 * math.pi * s, 4 * math.pi * s
    body = body_basis((0.0, 0.0, -RUSH_DROP - 0.06 * (0.5 - 0.5 * math.cos(w2))), yaw=RUSH_YAW,
                      roll=0.03 * math.sin(w1))
    legs, st = {}, {}
    for tag in LEG_TAGS:
        tgt, planted = foot_cycle(tag, s, RT_ROT[tag], RUSH_E, RUSH_H, RUSH_DUTY)
        legs[tag] = tgt
        st[tag] = (planted, tgt)
    ex = both_claws({'Merus': (0.28 + 0.04 * math.sin(w2), 0, 0), 'Propodus': (0.18, 0, 0),
                     'Coxa': (0, 0, 0.04 * math.sin(w1))})
    return body, legs, st, ex


def clip_rush_loop():
    c = Clip('RushLoop', RUSH_T, True)
    for f in list(range(c.frames)) * 2 + list(range(c.frames + 1)):   # two priming cycles
        if f == 0:
            c.bases, c.stance = [], []
        body, legs, st, ex = rush_loop_pose(f / c.frames)
        c.bases.append(pose_frame(body, legs, ex))
        c.stance.append(st)
    c.meta = {'speed': RUSH_V, 'stride': RUSH_V * RUSH_T}
    return c


def clip_rush_start():
    c = Clip('RushStart', 21 / FPS, False)
    _, legs_end, _, ex_end = rush_loop_pose(0.0)
    for f in range(c.frames + 1):
        t = f / FPS
        T = c.duration
        b = smooth(t, 0.0, 0.35 * T / 0.875)
        g = smooth(t, 0.05, 0.4)
        w = smooth(t, 0.35, T)
        body = body_basis((0.0, 0.08 * math.sin(math.pi * b), -RUSH_DROP * b), yaw=RUSH_YAW * w)
        legs = {}
        yaw_at = lambda tt: RUSH_YAW * smooth(tt, 0.35, T)
        for tag in LEG_TAGS:
            if tag in GROUP_A:
                mid = Matrix.Rotation(yaw_at(0.60), 4, 'Z') @ RT[tag]
                legs[tag] = (step_between(RT[tag], mid, t, 0.35, 0.50, 0.7) if t < 0.62
                             else step_between(mid, legs_end[tag], t, 0.62, 0.77, 0.7))
            else:
                mid = Matrix.Rotation(yaw_at(0.72), 4, 'Z') @ RT[tag]
                legs[tag] = (step_between(RT[tag], mid, t, 0.47, 0.62, 0.7) if t < 0.74
                             else step_between(mid, legs_end[tag], t, 0.74, T, 0.7))
        ex = both_claws({'Merus': (0.28 * g, 0, 0), 'Propodus': (0.18 * g, 0, 0)})
        c.bases.append(pose_frame(body, legs, ex))
        c.stance.append({tag: (None, legs[tag]) for tag in LEG_TAGS})
    return c


def clip_rush_end():
    c = Clip('RushEnd', 21 / FPS, False)
    _, legs0, _, _ = rush_loop_pose(0.0)
    T = c.duration
    for f in range(c.frames + 1):
        t = f / FPS
        k = smooth(t, 0.0, 0.3)
        w = 1.0 - smooth(t, 0.3, T - 0.03)
        drop = RUSH_DROP * (1.0 - smooth(t, 0.3, T - 0.03))
        lurch = 0.18 * math.sin(math.pi * k)
        body = body_basis((0.0, -lurch * (1 - smooth(t, 0.3, 0.6)), -drop), yaw=RUSH_YAW * w,
                          roll=-0.06 * math.sin(math.pi * k))
        legs = {}
        yaw_at = lambda tt: RUSH_YAW * (1.0 - smooth(tt, 0.3, T - 0.03))
        for tag in LEG_TAGS:
            if tag in GROUP_A:
                mid = Matrix.Rotation(yaw_at(0.50), 4, 'Z') @ RT[tag]
                legs[tag] = (step_between(legs0[tag], mid, t, 0.28, 0.45, 0.7) if t < 0.59
                             else step_between(mid, RT[tag], t, 0.59, 0.74, 0.7))
            else:
                mid0 = RT_ROT[tag]
                mid = Matrix.Rotation(yaw_at(0.65), 4, 'Z') @ RT[tag]
                if t < 0.42:
                    legs[tag] = step_between(legs0[tag], mid0, t, 0.0, 0.2, 0.6)
                elif t < 0.71:
                    legs[tag] = step_between(mid0, mid, t, 0.42, 0.59, 0.7)
                else:
                    legs[tag] = step_between(mid, RT[tag], t, 0.71, T - 0.02, 0.7)
        g = 1.0 - smooth(t, 0.3, 0.8)
        ex = both_claws({'Merus': (0.28 * g, 0, 0), 'Propodus': (0.18 * g, 0, 0)})
        c.bases.append(pose_frame(body, legs, ex))
        c.stance.append({tag: (None, legs[tag]) for tag in LEG_TAGS})
    return c


DEATH = {'drop': 2.6}


def death_pose(t, drop):
    st = smooth(t, 0.0, 0.45)
    cl = smooth(t, 0.35, 1.55)
    cl_in = cl * cl * (3 - 2 * cl)                        # accelerate into the ground
    bounce = 0.0
    if t > 1.55:
        bounce = 0.10 * math.sin(math.pi * min(1.0, (t - 1.55) / 0.35)) * (1 - smooth(t, 1.55, 2.0))
    body = body_basis((0.0, 0.25 * math.sin(math.pi * st) * (1 - cl), -drop * cl_in + bounce),
                      pitch=0.08 * cl_in, roll=-0.08 * cl_in)
    legs = {}
    for tag in LEG_TAGS:
        radial = Vector((RT[tag].x, RT[tag].y, 0)).normalized()
        # tips curl just off the sand: short dactyls would otherwise drag the ankle shells under
        legs[tag] = RT[tag] + radial * (2.6 * cl) + Vector((0, 0, 0.6 * cl - RT[tag].z * cl))
    # claws: flatten early, lie on the sand beside the body
    fl = smooth(t, 0.3, 1.0)
    lo = smooth(t, 0.6, 1.6)
    claw_ik = {}
    for side, sgn in (('R', -1.0), ('L', 1.0)):
        rest_p = REST_PALM[side]
        final = Vector((rest_p.x + sgn * 1.2, rest_p.y + 0.4, DEATH.get(f'palm_z_{side}', 1.9)))
        rot_final = RI if side == 'R' else mirror_rot(RI)
        pos = rest_p.lerp(Vector((final.x, final.y, rest_p.z + 0.6)), fl).lerp(final, lo)
        rot = REST_HAND_ROT[side].to_quaternion().slerp(rot_final.to_quaternion(), fl).to_matrix()
        claw_ik[side] = (pos, rot, 1.0)
    ex = {}
    ex.update(mouth(0.45 * cl))
    ex['EyeStalk_R'] = rotm(0.55 * cl, 0, 0.1 * cl)
    ex['EyeStalk_L'] = rotm(0.55 * cl, 0, -0.1 * cl)
    ex['Brow_R'] = rotm(-0.2 * cl, 0, 0)
    ex['Brow_L'] = rotm(-0.2 * cl, 0, 0)
    return body, legs, ex, claw_ik


def death_floor(t):
    # splayed legs lie nearly flat, so a shell hangs its full radius (~1 stud)
    # below its joints: raise the joint floor as the legs spread
    return 1.5 * smooth(t, 0.3, 1.0)


def clip_death():
    c = Clip('Death', 2.25, False)
    # final drop: rest the sternum just above the sand
    drop = DEATH['drop']
    for _ in range(4):
        LEG_STATE.clear()
        CLAW_STATE.clear()
        for tt in np.linspace(0.0, c.duration, 12):
            body, legs, ex, cik = death_pose(tt, drop)
            B = pose_frame(body, legs, ex, cik, dw=0.8, floor=death_floor(tt))
        set_pose(B)
        mz = min_z()
        for side in ('R', 'L'):
            DEATH[f'palm_z_{side}'] = DEATH.get(f'palm_z_{side}', 1.9) + (0.03 - mz['Claw' + side])
        # the leg-root rings hang lower than the sternum: they touch first
        err = min(mz['Body'], coxa_min_z()) - 0.03
        if abs(err) < 0.02 and all(abs(mz['Claw' + s] - 0.03) < 0.03 for s in 'RL'):
            break
        drop = drop + err
    DEATH['drop'] = drop
    LEG_STATE.clear()
    CLAW_STATE.clear()
    for f in range(c.frames + 1):
        body, legs, ex, cik = death_pose(f / FPS, drop)
        c.bases.append(pose_frame(body, legs, ex, cik, dw=0.8, floor=death_floor(f / FPS)))
        c.stance.append({})
    return c


# -------------------------------------------------------------- build clips
def finalize(c):
    """Loops close exactly; non-loop clips start and end on the rest pose."""
    ident = {n: I4.copy() for n in ORDER}
    if c.loop:
        c.meta['loop_error_before_snap'] = max(
            max(abs(a - b) for ra, rb in zip(c.bases[0].get(n, I4), c.bases[-1].get(n, I4)) for a, b in zip(ra, rb))
            for n in ORDER)
        c.bases[-1] = {n: m.copy() for n, m in c.bases[0].items()}
    elif c.name in ('RushStart', 'RushEnd'):
        # the rush chain: RushStart ends on RushLoop's first frame, RushEnd starts there
        loop0 = CLIPS['RushLoop'].bases[0]
        a = ident if c.name == 'RushStart' else loop0
        z = loop0 if c.name == 'RushStart' else ident
        c.meta['start_error_before_snap'] = max(
            max(abs(p - q) for ra, rb in zip(c.bases[0].get(n, I4), a.get(n, I4)) for p, q in zip(ra, rb))
            for n in ORDER)
        c.meta['end_error_before_snap'] = max(
            max(abs(p - q) for ra, rb in zip(c.bases[-1].get(n, I4), z.get(n, I4)) for p, q in zip(ra, rb))
            for n in ORDER)
        c.bases[0] = {n: m.copy() for n, m in a.items()}
        c.bases[-1] = {n: m.copy() for n, m in z.items()}
    elif c.name != 'Death':
        c.meta['start_error_before_snap'] = max(
            max(abs(a - b) for ra, rb in zip(c.bases[0].get(n, I4), I4) for a, b in zip(ra, rb)) for n in ORDER)
        c.meta['end_error_before_snap'] = max(
            max(abs(a - b) for ra, rb in zip(c.bases[-1].get(n, I4), I4) for a, b in zip(ra, rb)) for n in ORDER)
        c.bases[0] = dict(ident)
        c.bases[-1] = dict(ident)
    else:
        c.bases[0] = dict(ident)
    for B in c.bases:
        for n in ORDER:
            B.setdefault(n, I4.copy())


builders = [clip_idle, clip_walk, clip_hit, clip_death, clip_crush, clip_rush_loop, clip_rush_start,
            clip_rush_end, clip_bubbles]
CLIPS = {}
LOOP0_STATE = {}
for fn in builders:
    LEG_STATE.clear()
    CLAW_STATE.clear()
    if fn is clip_rush_end:
        LEG_STATE.update({k: v.copy() for k, v in LOOP0_STATE.items()})
    c = fn()
    if fn is clip_rush_loop:
        # leg solutions at loop frame 0 (after a primed cycle) warm-start RushEnd
        for f in range(c.frames + 1):
            body, legs, st, ex = rush_loop_pose(f / c.frames)
            pose_frame(body, legs, ex)
        LOOP0_STATE = {k: v.copy() for k, v in LEG_STATE.items()}
    finalize(c)
    CLIPS[c.name] = c
    log('clip', c.name, c.frames + 1, 'frames')


# ------------------------------------------------------------------ checks
def armature_tips(B):
    P = fk(B)
    return {t: P[f'Leg_{t}_Dactyl'] @ Vector((0, BLEN[f'Leg_{t}_Dactyl'], 0)) for t in LEG_TAGS}


checks = {'clips': {}}
for name, c in CLIPS.items():
    ent = {'frames': c.frames + 1, 'duration': round(c.duration, 4)}
    speed = c.meta.get('speed', 0.0)
    ik_err = 0.0
    drift = 0.0
    runs = {t: [] for t in LEG_TAGS}
    for f, B in enumerate(c.bases):
        if not c.stance[f]:
            continue
        tips = armature_tips(B)
        for tag in LEG_TAGS:
            planted, target = c.stance[f][tag]
            e_ = (tips[tag] - target).length
            if e_ > ik_err:
                ik_err = e_
                ent['max_ik_error_at'] = [f, tag]
            if planted is None:        # scripted steps: planted = target did not move since last frame
                prev = c.stance[f - 1][tag][1] if f > 0 and c.stance[f - 1] else None
                planted = prev is not None and (prev - target).length < 1e-6
            # world position with the root travelling at the clip speed
            world = tips[tag] + TRAVEL * (speed * f / FPS)
            if planted:
                runs[tag].append(world)
            else:
                if len(runs[tag]) > 1:
                    drift = max(drift, max((p - runs[tag][0]).length for p in runs[tag]))
                runs[tag] = []
    for tag in LEG_TAGS:
        if len(runs[tag]) > 1:
            drift = max(drift, max((p - runs[tag][0]).length for p in runs[tag]))
    ent['max_ik_tip_error_studs'] = round(ik_err, 4)
    ent['max_planted_foot_drift_studs'] = round(drift, 4)
    for k in ('loop_error_before_snap', 'start_error_before_snap', 'end_error_before_snap'):
        if k in c.meta:
            ent[k] = round(c.meta[k], 5)
    checks['clips'][name] = ent

# ground clearance for Death (every frame) and ClawCrush (every frame)
for name in ('Death', 'ClawCrush'):
    worst = (9.0, None, None)
    for f, B in enumerate(CLIPS[name].bases):
        set_pose(B)
        mz = min_z()
        s = min(mz, key=mz.get)
        if mz[s] < worst[0]:
            worst = (mz[s], f, s)
    checks['clips'][name]['lowest_point_studs'] = round(worst[0], 4)
    checks['clips'][name]['lowest_point_frame'] = worst[1]
    checks['clips'][name]['lowest_point_section'] = worst[2]
    checks['clips'][name]['ground_ok'] = worst[0] >= -0.05


# claw vs body/eyes clearance during ClawCrush (BVH, sampled every frame)
def bvh(sec, groups=None):
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    ob = SECS[sec]
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    verts = [ob.matrix_world @ v.co for v in me.vertices]
    allowed = None
    if groups:
        gi = {ob.vertex_groups[g].index for g in groups}
        allowed = {v.index for v in ob.data.vertices if any(g.group in gi and g.weight > 0.5 for g in v.groups)}
    polys = [tuple(p.vertices) for p in me.polygons if allowed is None or all(i in allowed for i in p.vertices)]
    ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


hits = {}
for f, B in enumerate(CLIPS['ClawCrush'].bases):
    set_pose(B)
    bc = bvh('ClawR', ['Claw_R_Carpus', 'Claw_R_Propodus', 'Claw_R_Dactyl'])
    for o in ('Body', 'Eyes', 'Legs'):
        n = len(bc.overlap(bvh(o)))
        if n:
            hits.setdefault(o, []).append((f, n))
checks['clips']['ClawCrush']['crusher_overlaps'] = {k: v for k, v in hits.items()} or 'none'
log('checks', json.dumps(checks))

# --------------------------------------------------------- AnimationData.json
S = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def cf(m):
    m = S @ m @ S
    return [round(x, 7) for x in [m[0][3], m[1][3], m[2][3], m[0][0], m[0][1], m[0][2], m[1][0], m[1][1],
                                  m[1][2], m[2][0], m[2][1], m[2][2]]]


anim = {'id': BOSS_ID, 'fps': FPS,
        'bones': {b.name: {'parent': b.parent.name if b.parent else None,
                           'rest': cf(b.parent.matrix_local.inverted() @ b.matrix_local if b.parent else b.matrix_local)}
                  for b in rig.data.bones if b.use_deform},
        'clips': {},
        'motion': {'strideLength': round(WALK_V * WALK_T, 4), 'nominalSpeed': round(WALK_V, 4),
                   'rushStrideLength': round(RUSH_V * RUSH_T, 4), 'rushSpeed': round(RUSH_V, 4)}}
DEFORM = [b.name for b in rig.data.bones if b.use_deform]
for name, c in CLIPS.items():
    anim['clips'][name] = {'duration': round(c.frames / FPS, 7), 'loop': c.loop,
                           'frames': [{'time': round(f / FPS, 7),
                                       'transforms': {n: cf(B[n]) for n in DEFORM}}
                                      for f, B in enumerate(c.bases)]}
(GAME / 'AnimationData.json').write_text(json.dumps(anim, separators=(',', ':')))
log('AnimationData.json written')

# ----------------------------------------------------------- Blender actions
for name, c in CLIPS.items():
    old = bpy.data.actions.get(name)
    if old:
        bpy.data.actions.remove(old)
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    rig.animation_data.action = act
    for f, B in enumerate(c.bases):
        for pb in rig.pose.bones:
            pb.matrix_basis = B[pb.name]
            pb.keyframe_insert('location', frame=f + 1, group=pb.name)
            pb.keyframe_insert('rotation_quaternion', frame=f + 1, group=pb.name)
    if name == 'ClawCrush':
        act.pose_markers.new('Impact').frame = 1 + CRUSH['impact_f']
    if name == 'BubbleBarrage':
        act.pose_markers.new('ReleaseStart').frame = 1 + round(0.6 * FPS)
        act.pose_markers.new('ReleaseEnd').frame = 1 + round(2.0 * FPS)
rig.animation_data.action = None
for pb in rig.pose.bones:
    pb.matrix_basis = I4
log('actions keyed')


# ------------------------------------------------------- BossGameData.json
def studio(v):
    return [round(-v[0], 4), round(v[2], 4), round(v[1], 4)]


def r4(v):
    return [round(x, 4) for x in v]


def point_at(clip, frame, bone, offset):
    P = fk(CLIPS[clip].bases[frame])[bone]
    w = P @ Vector(offset)
    return {'bone': bone, 'offset': r4(offset), 'rootAtImpact': r4(w), 'rootAtImpactStudio': studio(w)}


game = {'attacks': {}}
cm = CLIPS['ClawCrush'].meta
fi = CRUSH['impact_f']
pt = point_at('ClawCrush', fi, 'Claw_R_Propodus', (0.0, PALM_C['R'], 0.0))
pt['groundPointAtImpact'] = [pt['rootAtImpact'][0], pt['rootAtImpact'][1], 0.0]
pt['groundPointAtImpactStudio'] = studio(Vector(pt['groundPointAtImpact']))
game['attacks']['ClawCrush'] = {'duration': round(CLIPS['ClawCrush'].frames / FPS, 4),
                                'warnStart': cm['warnStart'], 'impact': round(cm['impact'], 4),
                                'activeEnd': round(cm['activeEnd'], 4), 'recoveryEnd': cm['recoveryEnd'],
                                'points': {'ClawImpact': pt},
                                'note': 'crusher palm lands flat; ClawImpact is the palm centre (about 1.8 studs up, '
                                        'the palm half-thickness); groundPointAtImpact is directly below it'}
bm = CLIPS['BubbleBarrage'].meta
bfi = round(bm['impact'] * FPS)
mouth_rest = Vector((0.0, -4.95, 5.15))
off = REST['Body'].inverted() @ mouth_rest
bp = point_at('BubbleBarrage', bfi, 'Body', tuple(off))
Pb = fk(CLIPS['BubbleBarrage'].bases[bfi])['Body']
d = (Pb.to_3x3() @ Vector((0, math.sin(math.radians(10)), math.cos(math.radians(10))))).normalized()
game['attacks']['BubbleBarrage'] = {'duration': round(CLIPS['BubbleBarrage'].frames / FPS, 4),
                                    'warnStart': bm['warnStart'], 'impact': bm['impact'],
                                    'activeEnd': bm['activeEnd'], 'recoveryEnd': bm['recoveryEnd'],
                                    'points': {'BubbleOrigin': bp},
                                    'directionAtImpact': r4(d), 'directionAtImpactStudio': studio(d),
                                    'pumps': [round(bm['impact'] + (k + 0.5) * (bm['activeEnd'] - bm['impact']) / 3, 4)
                                              for k in range(3)]}
travel = TRAVEL
for name, extra in (('RushStart', {'warnStart': 0.0, 'impact': round(CLIPS['RushStart'].frames / FPS, 4),
                                   'activeEnd': round(CLIPS['RushStart'].frames / FPS, 4),
                                   'recoveryEnd': round(CLIPS['RushStart'].frames / FPS, 4),
                                   'note': 'braces low, claws up, turns 90 deg so his right side leads; '
                                           'chains into RushLoop at its end'}),
                    ('RushLoop', {'loop': True, 'rushStrideLength': round(RUSH_V * RUSH_T, 4),
                                  'rushSpeed': round(RUSH_V, 4),
                                  'note': 'in place; move the model along directionAtImpact at rushSpeed '
                                          '(the crab travels along his local -X, his right side, which the '
                                          'RushStart turn points along the model forward)'}),
                    ('RushEnd', {'warnStart': 0.0, 'impact': 0.0, 'activeEnd': 0.3,
                                 'recoveryEnd': round(CLIPS['RushEnd'].frames / FPS, 4),
                                 'note': 'skid stop (0-0.3 s) then turns back to face forward and returns to Idle'})):
    e = {'duration': round(CLIPS[name].frames / FPS, 4)}
    e.update(extra)
    if name != 'RushEnd':
        e['directionAtImpact'] = r4(travel)
        e['directionAtImpactStudio'] = studio(travel)
    game['attacks'][name] = e
allv = np.concatenate([section_verts(s) for s in SECTIONS])
set_pose({})
allv = np.concatenate([section_verts(s) for s in SECTIONS])
game.update({'rootHeight': 0.0, 'height': round(float(allv[:, 2].max()), 4),
             'footprintRadius': round(float(np.sqrt((allv[:, :2] ** 2).sum(1)).max()), 4),
             'bodyCentreHeight': round(BODY_PIVOT.z, 4),
             'walk': {'strideLength': anim['motion']['strideLength'], 'nominalSpeed': anim['motion']['nominalSpeed']},
             'notes': 'Times in seconds from clip start at 24 fps. Root bone sits on the ground under the body '
                      'centre (rootHeight 0). Blender axes: +X crab left, -Y forward, +Z up; Studio = (-X, Z, Y).'})
(GAME / 'BossGameData.json').write_text(json.dumps(game, indent=2))
checks['motion'] = anim['motion']
checks['crusher_impact_target'] = r4(cm['Pi'])
checks['death_final_drop'] = round(DEATH['drop'], 4)
(GAME / 'GameChecks.json').write_text(json.dumps(checks, indent=2))
log('BossGameData.json written')

# ------------------------------------------------------------ Studio FBX
FBM = GAME / 'KingCrab_Studio.fbm'
FBM.mkdir(exist_ok=True)
for sec in SECTIONS:
    src = OUT / 'textures' / f'KingCrab_{sec}_BaseColor_1024.png'
    shutil.copy2(src, FBM / src.name)
    m = bpy.data.materials[f'KingCrab_{sec}']
    m.node_tree.nodes['BaseColor'].image = bpy.data.images.load(str(src), check_existing=True)
rig.animation_data.action = None
rig.data.pose_position = 'REST'
names = {}
for sec, ob in SECS.items():
    # Objects keep their KingCrab_<Section> names: Roblox's importer merges a
    # mesh and a bone that share a name, and a section is called Body.
    names[sec] = ob.name
for ob in bpy.context.view_layer.objects:
    ob.select_set(False)
rig.select_set(True)
for ob in SECS.values():
    ob.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.export_scene.fbx(filepath=str(GAME / 'KingCrab_Studio.fbx'), use_selection=True,
                         object_types={'MESH', 'ARMATURE'}, bake_anim=False, add_leaf_bones=False,
                         use_armature_deform_only=True, axis_forward='-Z', axis_up='Y',
                         path_mode='COPY', embed_textures=True, use_mesh_modifiers=False,
                         mesh_smooth_type='OFF', primary_bone_axis='Y', secondary_bone_axis='X')
for sec, ob in SECS.items():
    ob.name = names[sec]
    bpy.data.materials[f'KingCrab_{sec}'].node_tree.nodes['BaseColor'].image = \
        bpy.data.images[f'KingCrab_{sec}_BaseColor']
rig.data.pose_position = 'POSE'
log('Studio FBX exported')

# ---------------------------------------------------------------- previews
review = [o for o in bpy.data.objects if o.users_collection and o.users_collection[0].name == 'REVIEW_ONLY']
floor = bpy.data.objects.get('ReviewGround')
cam = scene.camera
scene.render.engine = 'BLENDER_WORKBENCH'
sh = scene.display.shading
sh.light = 'STUDIO'
sh.color_type = 'TEXTURE'
sh.background_type = 'VIEWPORT'
sh.background_color = (0.30, 0.34, 0.40)
sh.show_shadows = True
scene.display.render_aa = '8'
scene.view_settings.view_transform = 'Standard'
if floor:
    floor.hide_render = False


def aim(loc, tgt, lens):
    cam.location = loc
    cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.type = 'PERSP'
    cam.data.lens = lens
    cam.data.shift_x = cam.data.shift_y = 0


def render_png(path, w, h):
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    if hasattr(scene.render.image_settings, 'media_type'):
        scene.render.image_settings.media_type = 'IMAGE'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def load_px(path):
    img = bpy.data.images.load(str(path))
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(h, w, 4)


def save_px(arr, path):
    h, w = arr.shape[:2]
    img = bpy.data.images.new('sheet_tmp', w, h, alpha=True)
    img.pixels.foreach_set(arr.astype(np.float32).ravel())
    img.filepath_raw = str(path)
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


aim(Vector((-21, -27, 11)), Vector((0, -1.8, 4.0)), 40)
ROW_CLIPS = ['Idle', 'Walk', 'Hit', 'Death', 'ClawCrush', 'RushStart', 'RushLoop', 'RushEnd', 'BubbleBarrage']
tiles = []
sel_frames = {}
for name in ROW_CLIPS:
    c = CLIPS[name]
    n = c.frames if c.loop else c.frames + 1
    if name == 'ClawCrush':
        fr = [0, 16, 24, CRUSH['impact_f'], 42, c.frames]
    elif name == 'BubbleBarrage':
        fr = [0, 10, 18, 30, 44, c.frames]
    else:
        fr = sorted({round(k * (n - 1) / 5) for k in range(6)})
    sel_frames[name] = fr
    row = []
    for f in fr[:6]:
        set_pose(CLIPS[name].bases[f])
        p = WORK / f'gc_{name}_{f:03d}.png'
        render_png(p, 400, 280)
        row.append(load_px(p))
    while len(row) < 6:
        row.append(np.ones_like(row[0]) * np.array([0.09, 0.1, 0.12, 1.0]))
    tiles.append(row)
h, w = tiles[0][0].shape[:2]
sheet = np.ones((h * len(tiles), w * 6, 4), np.float32)
for r, row in enumerate(tiles):
    for k, im in enumerate(row):
        y0 = (len(tiles) - 1 - r) * h
        sheet[y0:y0 + h, k * w:(k + 1) * w] = im
save_px(sheet, OUT / 'previews' / 'GameClips.png')
save_px(sheet, WORK / 'raw_GameClips.png')
(WORK / 'gameclips_frames.json').write_text(json.dumps(sel_frames))
log('GameClips.png rendered')


# mp4s: key a temporary action from the sampled bases (rig object translated
# along the travel direction during RushLoop so the feet can be seen to stick)
def render_mp4(name, seq, locs, cam_loc, cam_tgt, lens):
    act = bpy.data.actions.new(f'_preview_{name}')
    rig.animation_data.action = act
    for f, B in enumerate(seq):
        for pb in rig.pose.bones:
            pb.matrix_basis = B[pb.name]
            pb.keyframe_insert('location', frame=f + 1, group=pb.name)
            pb.keyframe_insert('rotation_quaternion', frame=f + 1, group=pb.name)
        rig.location = locs[f]
        rig.keyframe_insert('location', frame=f + 1)
    scene.frame_start, scene.frame_end = 1, len(seq)
    aim(cam_loc, cam_tgt, lens)
    scene.render.resolution_x, scene.render.resolution_y = 480, 320
    if hasattr(scene.render.image_settings, 'media_type'):
        scene.render.image_settings.media_type = 'VIDEO'
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'
    tmp = WORK / f'mp4_{name}_'
    scene.render.filepath = str(tmp)
    bpy.ops.render.render(animation=True)
    made = sorted(WORK.glob(f'mp4_{name}_*'))
    if made:
        shutil.move(str(made[-1]), str(OUT / 'previews' / f'{name}.mp4'))
    rig.animation_data.action = None
    if rig.animation_data:
        for fc_owner in (rig,):
            pass
    bpy.data.actions.remove(act)
    rig.location = (0, 0, 0)
    try:
        rig.animation_data_clear()
        rig.animation_data_create()
    except Exception:
        pass


zero = Vector((0, 0, 0))
crush_seq = CLIPS['ClawCrush'].bases
render_mp4('ClawCrush', crush_seq, [zero] * len(crush_seq), Vector((-24, -30, 12)), Vector((-1.5, -3.5, 4.0)), 38)
bub = CLIPS['BubbleBarrage'].bases
render_mp4('BubbleBarrage', bub, [zero] * len(bub), Vector((-14, -30, 9)), Vector((0, -3.0, 4.5)), 45)
seq, locs = [], []
seq += CLIPS['RushStart'].bases[:-1]
locs += [zero] * (len(CLIPS['RushStart'].bases) - 1)
x = 0.0
for k in range(4):
    for f, B in enumerate(CLIPS['RushLoop'].bases[:-1]):
        seq.append(B)
        locs.append(TRAVEL * (RUSH_V * (k * RUSH_T + f / FPS)))
end_off = TRAVEL * (RUSH_V * 4 * RUSH_T)
seq += CLIPS['RushEnd'].bases
locs += [end_off] * len(CLIPS['RushEnd'].bases)
render_mp4('Rush', seq, locs, Vector((-36, -12, 10)), Vector((0, -11, 3.5)), 30)
log('mp4s rendered')

scene.frame_start, scene.frame_end = 1, 250
scene.render.engine = 'CYCLES'
if hasattr(scene.render.image_settings, 'media_type'):
    scene.render.image_settings.media_type = 'IMAGE'
scene.render.image_settings.file_format = 'PNG'
rig.animation_data.action = bpy.data.actions.get('ReferencePose')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'KingCrab.blend'))
log('GAME_PACKAGE_COMPLETE', json.dumps({k: v.get('max_planted_foot_drift_studs') for k, v in checks['clips'].items()}))
