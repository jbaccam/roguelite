"""DJ Crab game package: clips at 124 BPM, timing data and the Studio import FBX.

Run under Blender 5.2, headless, after build_dj_crab.py:
    blender -b --factory-startup --python-exit-code 1 --python animate_game.py
    (DJ_QUICK=1: clips + checks only, no export or renders)

Opens DJCrab.blend (model, rig and atlas unchanged), authors the clips at
24 fps and writes, per plans/BOSS_GAME_PACKAGE_SPEC.md:
    exports/game/AnimationData.json   sampled matrix_basis per bone per frame (cf() Y/Z swap)
    exports/game/BossGameData.json    attack timings, points, strides, beat data
    exports/game/GameChecks.json      IK error, drift, loops, hinge/twist/rotation, ground, overlaps
    exports/game/DJCrab_Studio.fbx    rest mesh + deform armature, 1024 atlas (+ DJCrab_Studio.fbm/)
    previews/GameClips.png, Attack_ClawSlam.png, Attack_BeatCommand.png, Intro.png, Hero.png
and saves the clips as actions in DJCrab.blend.

Motion
- Body poses are world-space moves/turns about the body centre. Every leg is
  solved every frame by damped least squares (5 params: coxa swing, merus
  lift, knee, ankle) with joint-limit penalties, so planted tips stay put.
- Claws are solved for palm position + hand orientation (7 params: coxa and
  merus as pure swings, elbow hinge, wrist swing), so no bone carries twist;
  the movable finger (Dactyl) is a pure hinge driven by the gape.
- Music: 124 BPM, beat = 0.48387 s. Idle is exactly 8 beats (3.871 s): frames
  0..92 at 1/24 s plus a closure frame at 3.871 s equal to frame 0.
- Non-loop clips start and end on the Idle start pose (the rest pose).
"""
import bpy, json, math, os, shutil, sys, time
import numpy as np
from pathlib import Path
from mathutils import Vector, Matrix, Euler, Quaternion

T0 = time.time()
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT))
import motion_checks as MC

GAME = OUT / 'exports' / 'game'
GAME.mkdir(parents=True, exist_ok=True)
WORK = OUT / '_work'
WORK.mkdir(exist_ok=True)
PREV = OUT / 'previews'
QUICK = os.environ.get('DJ_QUICK', '0') == '1'
FPS = 24
NAME, BOSS_ID = 'DJCrab', 'dj-crab'
BPM = 124.0
BEAT = 60.0 / BPM
IDLE_T = 8 * BEAT


def log(*a):
    print(f'[{time.time() - T0:7.1f}s]', *a, flush=True)


bpy.ops.wm.open_mainfile(filepath=str(OUT / 'DJCrab.blend'))
scene = bpy.context.scene
scene.render.fps = FPS
rig = bpy.data.objects[f'{NAME}_Rig']
SECTIONS = ['Shell', 'Eyes', 'Legs', 'Claws', 'Gear', 'Glow']
SECS = {s: bpy.data.objects[f'{NAME}_{s}'] for s in SECTIONS}
MAN = json.loads((OUT / 'manifest.json').read_text())
GAPE_REST = MAN['rest_gape_deg']
rig.animation_data_create()
rig.animation_data.action = None
rig.data.pose_position = 'POSE'
rig.location = (0, 0, 0)
for pb in rig.pose.bones:
    pb.rotation_mode = 'QUATERNION'
    pb.matrix_basis = Matrix.Identity(4)

REST = {b.name: b.matrix_local.copy() for b in rig.data.bones}
PAR = {b.name: (b.parent.name if b.parent else None) for b in rig.data.bones}
SK = MC.Skel(REST, PAR)
ORDER, LREST, fk = SK.order, SK.lrest, SK.fk
BLEN = {b.name: b.length for b in rig.data.bones}
I4 = Matrix.Identity(4)


def rotm(x=0.0, y=0.0, z=0.0):
    return Euler((x, y, z), 'XYZ').to_matrix().to_4x4()


def swing(a, b):
    """Rotation about an axis in the bone's XZ plane: zero twist about the bone axis."""
    ang = math.hypot(a, b)
    if ang < 1e-10:
        return I4.copy()
    return Matrix.Rotation(ang, 4, Vector((a / ang, 0.0, b / ang)))


def smooth(t, a, b):
    if b <= a:
        return 1.0 if t >= b else 0.0
    x = min(1.0, max(0.0, (t - a) / (b - a)))
    return x * x * (3 - 2 * x)


def lerp(a, b, t):
    return a + (b - a) * t


def axis(M, i):
    return Vector((M[0][i], M[1][i], M[2][i])).normalized()


BODY_PIVOT = REST['Body'].translation.copy()


def bodyD(off=(0, 0, 0), yaw=0.0, pitch=0.0, roll=0.0):
    """Armature-space body delta about its centre. pitch > 0 nose down; roll > 0 crab's right (-X) up."""
    return (Matrix.Translation(Vector(off)) @ Matrix.Translation(BODY_PIVOT) @ rotm(0, 0, yaw)
            @ rotm(pitch, 0, 0) @ rotm(0, roll, 0) @ Matrix.Translation(-BODY_PIVOT))


# --------------------------------------------------------------- rigid mesh
def rigid_mesh():
    Vs, F, VB, VS = [], [], [], []
    base = 0
    for sec, ob in SECS.items():
        me = ob.data
        names = {g.index: g.name for g in ob.vertex_groups}
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        Mw = np.array(ob.matrix_world)
        Vs.append(co @ Mw[:3, :3].T + Mw[:3, 3])
        for v in me.vertices:
            g = max(v.groups, key=lambda g: g.weight)
            VB.append(names[g.group])
            VS.append(sec)
        F += [tuple(base + i for i in p.vertices) for p in me.polygons]
        base += len(me.vertices)
    return MC.RigidMesh(np.concatenate(Vs), F, VB, VS)


MESH = rigid_mesh()
SEC_IDX = {s: np.nonzero(MESH.vsec == s)[0] for s in SECTIONS}


def posed(B):
    return MESH.posed(SK, fk(B))


# ------------------------------------------------------------------- LM
def lm(res, p0, iters=40, lam=1e-3, max_step=None):
    p = np.array(p0, float)
    r = res(p)
    cost = r @ r
    for _ in range(iters):
        J = np.empty((len(r), len(p)))
        for j in range(len(p)):
            dp = p.copy()
            dp[j] += 1e-5
            J[:, j] = (res(dp) - r) / 1e-5
        A = J.T @ J
        g = J.T @ r
        step = np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-9), -g)
        if max_step is not None:
            nrm = np.linalg.norm(step)
            if nrm > max_step:
                step *= max_step / nrm
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


def lim(val, lo, hi, s=0.5):
    return max(0.0, lo - val) / s + max(0.0, val - hi) / s


# ------------------------------------------------------------------ legs
LEG_TAGS = MC.LEG_TAGS
GROUP_A = {'L1', 'R2', 'L3', 'R4'}


def leg_chain(tag):
    return [f'Leg_{tag}_{s}' for s in ('Coxa', 'Merus', 'Carpus', 'Dactyl')]


def leg_fk(Pbody, tag, p):
    c, m, k, d = leg_chain(tag)
    M = Pbody @ LREST[c] @ swing(p[1], p[0])
    M = M @ LREST[m] @ rotm(p[2], 0, 0)
    M = M @ LREST[k] @ rotm(p[3], 0, 0)
    knee = M.translation.copy()
    M = M @ LREST[d] @ rotm(p[4], 0, 0)
    ankle = M.translation.copy()
    return M @ Vector((0, BLEN[d], 0)), M.to_3x3() @ Vector((0, 1, 0)), knee, ankle


def leg_basis(p):
    return [swing(p[1], p[0]), rotm(p[2], 0, 0), rotm(p[3], 0, 0), rotm(p[4], 0, 0)]


P0 = fk({})
RT, D0, KNEE0, ANK0 = {}, {}, {}, {}
for tag in LEG_TAGS:
    c, m, k, d = leg_chain(tag)
    tp, dd, kn, an = leg_fk(P0['Body'], tag, np.zeros(5))
    RT[tag], D0[tag] = tp, dd.z
    KNEE0[tag] = MC.hinge_angle(P0[m], P0[k])
    ANK0[tag] = MC.hinge_angle(P0[k], P0[d])
JMIN = 0.62
LEG_W = np.array([0.9, 0.4, 1.4, 1.4, 1.4])
# rim clearance: the carapace outline (same function as build_dj_crab.py)
ZO = MAN.get('zoff', 0.0)
W_SH, D_FRONT, D_REAR, SQ, Z_RIM = 1.99, 1.68, 1.84, 2.3, 2.05 + ZO
CEN = Vector((0.0, -0.05, 0.0))


def outline(a):
    c, s_ = math.cos(a), math.sin(a)
    D_ = D_FRONT if s_ < 0 else D_REAR
    r = 1.0 / ((abs(c) / W_SH) ** SQ + (abs(s_) / D_) ** SQ) ** (1 / SQ)
    front = max(0.0, -s_) ** 2
    return r * (1 + 0.022 * math.cos(12 * a) + 0.010 * math.sin(7 * a + 0.5) + 0.032 * front * math.cos(18 * a))


def rim_excess(q):
    """Height of a body-local point if it is inside the zone under/around the rim lip, else 0."""
    a = math.atan2(q.y - CEN.y, q.x - CEN.x)
    if math.hypot(q.x - CEN.x, q.y - CEN.y) > outline(a) * 1.04 + 0.55:
        return 0.0
    return q.z


def merus_pts(Pbody, tag, p):
    c, m, k, d = leg_chain(tag)
    M = Pbody @ LREST[c] @ swing(p[1], p[0])
    j1 = (M @ LREST[m]).translation.copy()
    kn = leg_fk(Pbody, tag, p)[2]
    return [j1, j1.lerp(kn, 0.25), j1.lerp(kn, 0.5)]


RIM_Z = {}
for tag in LEG_TAGS:
    RIM_Z[tag] = [max(1.59 + ZO, rim_excess(q) + 0.02) for q in merus_pts(P0['Body'], tag, np.zeros(5))]


def solve_leg(Pbody, tag, target, p0, floor=None, dw=0.35, Dinv=None):
    jm = JMIN if floor is None else floor
    p_prev = np.array(p0, float)

    def res(p):
        tip, dd, kn, an = leg_fk(Pbody, tag, p)
        r = [(tip.x - target.x) / 0.0012, (tip.y - target.y) / 0.0012, (tip.z - target.z) / 0.0012]
        r += list(p / LEG_W)
        r.append((dd.z - D0[tag]) / dw)
        r.append(max(0.0, jm - kn.z) / 0.01)
        r.append(max(0.0, jm - an.z) / 0.01)
        r.append(lim(KNEE0[tag] + math.degrees(p[3]), 4.0, 140.0))
        r.append(lim(ANK0[tag] + math.degrees(p[4]), 4.0, 140.0))
        r.append(lim(math.degrees(p[2]), -50.0, 50.0))
        r.append(lim(math.degrees(p[1]), -30.0, 30.0) + lim(math.degrees(p[0]), -45.0, 45.0))
        if Dinv is not None:
            for q, zmax in zip(merus_pts(Pbody, tag, p), RIM_Z[tag]):
                r.append(max(0.0, rim_excess(Dinv @ q) - zmax) / 0.0015)
        r += list((p - p_prev) / 0.6)
        return np.array(r)
    return lm(res, p0, iters=60)


# ----------------------------------------------------------------- claws
def claw_chain(side):
    return [f'Claw_{side}_{s}' for s in ('Coxa', 'Merus', 'Carpus', 'Propodus')]


def claw_fk(Pbody, side, q):
    c, m, k, h = claw_chain(side)
    M = Pbody @ LREST[c] @ swing(q[0], q[1])
    M = M @ LREST[m] @ swing(q[2], q[3])
    M = M @ LREST[k] @ rotm(q[4], 0, 0)
    return M @ LREST[h] @ swing(q[5], q[6])


def claw_basis(q):
    return [swing(q[0], q[1]), swing(q[2], q[3]), rotm(q[4], 0, 0), swing(q[5], q[6])]


PALM_LOCAL = Vector(MAN['claw_palm_centre'])
CLAW_W = np.array([0.30, 0.30, 2.2, 2.2, 1.6, 1.0, 0.8])
REST_PROP = {s: REST[f'Claw_{s}_Propodus'] for s in 'LR'}
REST_F = {s: axis(REST_PROP[s], 1) for s in 'LR'}
SIDE_H = {s: -axis(REST[f'Claw_{s}_Dactyl'], 0) for s in 'LR'}
REST_U = {s: SIDE_H[s].cross(REST_F[s]).normalized() for s in 'LR'}
REST_PALM = {s: REST_PROP[s] @ PALM_LOCAL for s in 'LR'}
TIP_LOCAL = {s: REST_PROP[s].inverted() @ (REST_PROP[s].translation + REST_F[s] * MAN['claw_tip_f']
                                             + REST_U[s] * MAN['claw_tip_up']) for s in 'LR'}
ELB0 = {s: MC.hinge_angle(P0[f'Claw_{s}_Merus'], P0[f'Claw_{s}_Carpus']) for s in 'LR'}


def segdist(p1, q1, p2, q2):
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a, e, f = d1.dot(d1), d2.dot(d2), d2.dot(r)
    c = d1.dot(r)
    b = d1.dot(d2)
    den = a * e - b * b
    s_ = min(1.0, max(0.0, (b * f - c * e) / den)) if den > 1e-12 else 0.0
    t = (b * s_ + f) / e
    if t < 0.0:
        t, s_ = 0.0, min(1.0, max(0.0, -c / a))
    elif t > 1.0:
        t, s_ = 1.0, min(1.0, max(0.0, (b - c) / a))
    return ((p1 + d1 * s_) - (p2 + d2 * t)).length


def claw_segs(Pbody, side, q):
    c, m, k, h = claw_chain(side)
    M = Pbody @ LREST[c] @ swing(q[0], q[1])
    M1 = M @ LREST[m] @ swing(q[2], q[3])
    M2 = M1 @ LREST[k] @ rotm(q[4], 0, 0)
    M3 = M2 @ LREST[h] @ swing(q[5], q[6])
    m0, e_, w_ = M1.translation, M2.translation, M3.translation
    return [(m0.copy(), e_, 0.33), (e_, w_, 0.34), (w_, M3 @ Vector((0, 1.30, 0)), 0.58)]


LEG_SEGS = {}


def leg_segs(Pbody, tag, p):
    c, m, k, d = leg_chain(tag)
    M = Pbody @ LREST[c] @ swing(p[1], p[0])
    M1 = M @ LREST[m] @ rotm(p[2], 0, 0)
    M2 = M1 @ LREST[k] @ rotm(p[3], 0, 0)
    M3 = M2 @ LREST[d] @ rotm(p[4], 0, 0)
    return [(M1.translation.copy(), M2.translation.copy(), 0.37), (M2.translation.copy(), M3.translation.copy(), 0.33)]


# shell + gear envelope (body-local): carapace outline x1.04 horizontally, dome + 0.35 vertically
H_DOME = 0.86
CUR = {'Dinv': Matrix.Identity(4)}


def dome_z(rho, a):
    rear = max(0.0, math.sin(a))
    pz = 3.3 + 0.4 * rear
    h = H_DOME - 0.12 * rear * rho ** 1.5
    return Z_RIM + h * max(0.0, 1 - min(rho, 1.0) ** pz) ** 0.55


def env_pen(q, r):
    a = math.atan2(q.y - CEN.y, q.x - CEN.x)
    R = outline(a)
    rxy = math.hypot(q.x - CEN.x, q.y - CEN.y)
    rho = rxy / R
    top = (dome_z(rho, a) if rho < 1.0 else Z_RIM) + 0.35
    if q.z < 1.25 + ZO - r:
        return 0.0
    return max(0.0, min(R * 1.04 + r - rxy, top + r - q.z))


def claw_env_samples(Pbody, side, q):
    segs = claw_segs(Pbody, side, q)
    pts = []
    for k, (a0, a1, rr) in enumerate(segs):
        ts = (0.35, 0.7, 1.0) if k == 0 else ((0.0, 0.5, 1.0) if k == 1 else (0.3, 0.7))
        pts += [(a0.lerp(a1, t), rr) for t in ts]
    return pts


ENV0 = {sd: [env_pen(pt, rr) for pt, rr in claw_env_samples(P0['Body'], sd, np.zeros(7))] for sd in 'LR'}

CLEAR0 = {}
for side in 'LR':
    for i in (1, 2):
        tag = f'{side}{i}'
        for a_i, (a0, a1, ra) in enumerate(claw_segs(P0['Body'], side, np.zeros(7))):
            for b_i, (b0, b1, rb) in enumerate(leg_segs(P0['Body'], tag, np.zeros(5))):
                CLEAR0[(side, tag, a_i, b_i)] = min(ra + rb + 0.04, segdist(a0, a1, b0, b1) - 0.01)


def solve_claw(Pbody, side, pos, rot3, q0, ow=0.06):
    q_prev = np.array(q0, float)
    legs = {f'{side}{i}': LEG_SEGS.get(f'{side}{i}') for i in (1, 2)}

    def res(q):
        M = claw_fk(Pbody, side, q)
        palm = M @ PALM_LOCAL
        r = [(palm.x - pos.x) / 0.006, (palm.y - pos.y) / 0.006, (palm.z - pos.z) / 0.006]
        e = (rot3.transposed() @ M.to_3x3()).to_quaternion()
        if e.w < 0:
            e.negate()
        r += [2 * e.x / ow, 2 * e.y / ow, 2 * e.z / ow]
        r += list(q / CLAW_W)
        r.append(lim(ELB0[side] + math.degrees(q[4]), 8.0, 140.0))
        r.append(lim(math.degrees(math.hypot(q[0], q[1])), 0.0, 25.0))
        r.append(lim(math.degrees(math.hypot(q[5], q[6])), 0.0, 65.0))
        r.append(lim(math.degrees(math.hypot(q[2], q[3])), 0.0, 125.0))
        cs = claw_segs(Pbody, side, q)
        for tag, segs in legs.items():
            if segs is None:
                continue
            for a_i, (a0, a1, ra) in enumerate(cs):
                for b_i, (b0, b1, rb) in enumerate(segs):
                    r.append(max(0.0, CLEAR0[(side, tag, a_i, b_i)] - segdist(a0, a1, b0, b1)) / 0.004)
        Dinv = CUR['Dinv']
        for (pt, rr), e0 in zip(claw_env_samples(Pbody, side, q), ENV0[side]):
            r.append(max(0.0, env_pen(Dinv @ pt, rr) - e0) / 0.004)
        r += list((q - q_prev) / 0.35)
        return np.array(r)
    return lm(res, q0, iters=50, max_step=0.12)


def frame3(f, u):
    f = Vector(f).normalized()
    u = Vector(u)
    u = (u - f * u.dot(f)).normalized()
    return Matrix((f, u, f.cross(u))).transposed()


def mir(v, side):
    v = Vector(v)
    return Vector((-v.x, v.y, v.z)) if side == 'L' else v


RPOS, RF, RU = REST_PALM['R'].copy(), REST_F['R'].copy(), REST_U['R'].copy()


def claw_target(side, pos, fwd, up, D=None):
    """Targets are authored for the right claw (crab's right, -X) and mirrored for the left.
    D: body delta to carry body-relative targets with the body."""
    pos, fwd, up = mir(pos, side), mir(fwd, side), mir(up, side)
    if D is not None:
        pos = D @ pos
        R = D.to_3x3()
        fwd, up = R @ fwd, R @ up
    rot = frame3(fwd, up) @ frame3(REST_F[side], REST_U[side]).transposed() @ REST_PROP[side].to_3x3()
    return pos, rot


def gape_basis(g):
    return rotm(math.radians(GAPE_REST - g), 0, 0)


def stalk_basis(tilt=0.0, side=0.0, slide=0.0):
    return Matrix.Translation(Vector((0, slide, 0))) @ swing(tilt, side)


def stalks(tilt=0.0, side=0.0, slide=0.0, spread=0.0):
    return {'EyeStalk_R': stalk_basis(tilt, side - spread, slide), 'EyeStalk_L': stalk_basis(tilt, side + spread, slide)}


# ------------------------------------------------------------ pose composer
class Clip:
    def __init__(self, name, duration, loop, times=None):
        self.name, self.loop = name, loop
        if times is None:
            n = int(round(duration * FPS))
            times = [f / FPS for f in range(n + 1)]
            duration = n / FPS
        self.times, self.duration = times, duration
        self.bases, self.stance, self.claw_err, self.meta = [], [], [], {}


LEG_STATE, CLAW_STATE, CLAW_TGT = {}, {}, {}


def pose_frame(D, legs, extra=None, claws=None, floor=None, claw_q=None):
    body = REST['Body'].inverted() @ D @ REST['Body']
    B = {'Body': body}
    Pbody = D @ REST['Body']
    Dinv = D.inverted()
    CUR['Dinv'] = Dinv
    LEG_SEGS.clear()
    for tag, target in legs.items():
        p = solve_leg(Pbody, tag, target, LEG_STATE.get(tag, np.zeros(5)), floor, Dinv=Dinv)
        LEG_STATE[tag] = p
        LEG_SEGS[tag] = leg_segs(Pbody, tag, p)
        for n, m in zip(leg_chain(tag), leg_basis(p)):
            B[n] = m
    err = 0.0
    for side, (pos, rot3) in (claws or {}).items():
        # track the target continuously: sub-step from the previous frame's target (no branch flips)
        q = CLAW_STATE.get(side, np.zeros(7))
        prev = CLAW_TGT.get(side)
        steps = 5 if prev is not None else 1
        for k in range(1, steps + 1):
            if prev is not None:
                u = k / steps
                p_k = prev[0].lerp(pos, u)
                r_k = prev[1].to_quaternion().slerp(rot3.to_quaternion(), u).to_matrix()
            else:
                p_k, r_k = pos, rot3
            q = solve_claw(Pbody, side, p_k, r_k, q)
        CLAW_TGT[side] = (pos.copy(), rot3.copy())
        CLAW_STATE[side] = q
        for n, m in zip(claw_chain(side), claw_basis(q)):
            B[n] = m
        err = max(err, (claw_fk(Pbody, side, q) @ PALM_LOCAL - pos).length)
    for side, q in (claw_q or {}).items():
        # project the interpolated pose: same hand pose, clearance terms active (keeps the arc, resolves contacts)
        M = claw_fk(Pbody, side, q)
        q = solve_claw(Pbody, side, M @ PALM_LOCAL, M.to_3x3(), q)
        for n, m in zip(claw_chain(side), claw_basis(q)):
            B[n] = m
    if extra:
        B.update(extra)
    return B, err


def planted_legs():
    return {t: RT[t] for t in LEG_TAGS}


def add(c, B, err, stance):
    c.bases.append(B)
    c.claw_err.append(err)
    c.stance.append(stance)


def keyval(t, keys):
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * smooth(t, t0, t1)
    return keys[-1][1]


def claw_keys(t, keys):
    """keys: [(t, pos, fwd, up, gape)] in R-space; smoothstep between keys."""
    if t <= keys[0][0]:
        k = keys[0]
        return k[1], k[2], k[3], k[4]
    for a, b in zip(keys, keys[1:]):
        if t <= b[0]:
            u = smooth(t, a[0], b[0])
            return (a[1].lerp(b[1], u), a[2].lerp(b[2], u).normalized(), a[3].lerp(b[3], u).normalized(),
                    a[4] + (b[4] - a[4]) * u)
    k = keys[-1]
    return k[1], k[2], k[3], k[4]


V = Vector


# ================================================================ clips
def clip_idle():
    times = [f / FPS for f in range(93)] + [IDLE_T]
    c = Clip('Idle', IDLE_T, True, times)
    for t in times:
        ph = (t / BEAT) % 8.0 if t < IDLE_T - 1e-9 else 0.0
        k = int(math.floor(ph + 1e-9))
        u = ph - k
        lift = math.sin(math.pi * u ** 1.4)          # body rises between beats, drops onto each beat
        D = bodyD((0, 0, 0.10 * lift), yaw=0.035 * math.sin(math.pi * ph / 2), pitch=-0.025 * lift,
                  roll=0.045 * math.sin(math.pi * ph))
        claws, ex = {}, {}
        for side in 'RL':
            mine = (k % 2 == 0) if side == 'R' else (k % 2 == 1)
            a = math.sin(math.pi * u ** 1.6) if mine else 0.0   # pump up, strike down on the beat
            pos = RPOS + V((-0.06, -0.12, 0.72)) * a
            fwd = (RF + V((0, 0, 1.3)) * a).normalized()
            claws[side] = claw_target(side, pos, fwd, RU, D)
            ex[f'Claw_{side}_Dactyl'] = gape_basis(GAPE_REST + 14 * a)
        ex.update(stalks(tilt=-0.06 * lift, side=0.16 * math.sin(math.pi * ph / 2), spread=0.05 * math.sin(math.pi * ph)))
        B, err = pose_frame(D, planted_legs(), ex, claws)
        add(c, B, err, {tg: True for tg in LEG_TAGS})
    c.meta = {'beats': 8, 'beat': BEAT}
    return c


WALK_N, WALK_DUTY, WALK_E, WALK_H = 12, 0.5, 0.70, 0.26     # fast scuttle: 0.5 s cycle, stride 1.40
WALK_T = WALK_N / FPS
WALK_V = WALK_E / (WALK_DUTY * WALK_T)
TRAVEL = V((0, -1, 0))


def foot_cycle(tag, s):
    ph = (s + (0.0 if tag in GROUP_A else 0.5)) % 1.0
    if ph < WALK_DUTY:
        u = ph / WALK_DUTY
        return RT[tag] + TRAVEL * (WALK_E / 2 - WALK_E * u), True
    u = (ph - WALK_DUTY) / (1 - WALK_DUTY)
    return RT[tag] + TRAVEL * (-WALK_E / 2 + WALK_E * smooth(u, 0, 1)) + V((0, 0, WALK_H * math.sin(math.pi * u))), False


def clip_walk():
    c = Clip('Walk', WALK_T, True)
    for f in list(range(WALK_N)) + list(range(WALK_N + 1)):     # first cycle primes the IK
        if f == 0:
            c.bases, c.stance, c.claw_err = [], [], []
        s = f / WALK_N
        w1, w2 = 2 * math.pi * s, 4 * math.pi * s
        D = bodyD((0.04 * math.sin(w1), 0.0, -0.05 * (0.5 - 0.5 * math.cos(w2))), yaw=0.07 * math.sin(w1),
                  pitch=0.02 * math.sin(w2), roll=0.035 * math.sin(w1))
        legs, st = {}, {}
        for tag in LEG_TAGS:
            legs[tag], st[tag] = foot_cycle(tag, s)
        claws, ex = {}, {}
        for side, ph in (('R', 0.0), ('L', math.pi)):
            pos = RPOS + V((0, 0.10 * math.sin(w1 + ph), 0.18 + 0.05 * math.cos(w1 + ph)))
            claws[side] = claw_target(side, pos, (RF + V((0, 0, 0.3))).normalized(), RU, D)
            ex[f'Claw_{side}_Dactyl'] = gape_basis(16.0)
        ex.update(stalks(tilt=0.05 * math.sin(w2), side=0.08 * math.sin(w1)))
        B, err = pose_frame(D, legs, ex, claws)
        add(c, B, err, st)
    c.meta = {'speed': WALK_V, 'stride': WALK_V * WALK_T}
    return c


def clip_hit():
    c = Clip('Hit', 11 / FPS, False)
    for t in c.times:
        u = t / c.duration
        e = math.sin(math.pi * u) * (1 - u) ** 0.6 * 1.6
        D = bodyD((0.0, 0.30 * e, 0.12 * e), pitch=-0.10 * e, roll=0.05 * e)
        claws, ex = {}, {}
        for side in 'RL':
            pos = RPOS + V((0.10, 0.25, 0.35)) * e
            claws[side] = claw_target(side, pos, (RF + V((0, 0.2, 0.5)) * e).normalized(), RU, D)
            ex[f'Claw_{side}_Dactyl'] = gape_basis(GAPE_REST + 15 * e)
        ex.update(stalks(tilt=-0.35 * e, spread=0.10 * e))
        B, err = pose_frame(D, planted_legs(), ex, claws)
        add(c, B, err, {tg: True for tg in LEG_TAGS})
    return c


# ------------------------------------------------------ keypose claws
# Big gestures are keyposed: each claw keypose is solved once by IK (continued from the previous
# key, with the leg-clearance terms active), then the clip interpolates in joint space. Joint-space
# arcs cannot flip IK branches between frames; impact keys still land exactly on their targets.
def legs_at(D):
    Pbody = D @ REST['Body']
    Dinv = D.inverted()
    CUR['Dinv'] = Dinv
    LEG_SEGS.clear()
    for tag in LEG_TAGS:
        p = solve_leg(Pbody, tag, RT[tag], np.zeros(5), None, Dinv=Dinv)
        LEG_SEGS[tag] = leg_segs(Pbody, tag, p)


def solve_key(side, key, D, q0, world=False, steps=12):
    pos, fwd, up = key
    legs_at(D)
    Pbody = D @ REST['Body']
    tp, tr = claw_target(side, pos, fwd, up, None if world else D)
    M = claw_fk(Pbody, side, q0)
    sp, sr = M @ PALM_LOCAL, M.to_3x3().to_quaternion()
    q = np.array(q0, float)
    for k in range(1, steps + 1):
        u = k / steps
        q = solve_claw(Pbody, side, sp.lerp(tp, u), sr.slerp(tr.to_quaternion(), u).to_matrix(), q)
    return q, (claw_fk(Pbody, side, q) @ PALM_LOCAL - tp).length


def ease_in(pw):
    return lambda u: u ** pw


def interp_q(t, keys, eases=None):
    eases = eases or {}
    if t <= keys[0][0]:
        return keys[0][1]
    for i, (ka, kb) in enumerate(zip(keys, keys[1:])):
        if t <= kb[0] + 1e-9:
            u = min(1.0, max(0.0, (t - ka[0]) / (kb[0] - ka[0])))
            u = eases[i](u) if i in eases else u * u * (3 - 2 * u)
            return ka[1] + (kb[1] - ka[1]) * u
    return keys[-1][1]


Z7 = np.zeros(7)

# ---------------------------------------------------------- BeatCommand
BC = {'impact_f': 18}
BC_RAISE = (V((-1.62, -2.30, 3.02 + ZO)), V((0.05, -0.20, 1.0)).normalized(), V((0.70, -0.70, 0.0)))
BC_HOLD = (V((-1.62, -2.40, 3.06 + ZO)), V((0.08, -0.36, 1.0)).normalized(), V((0.70, -0.70, 0.0)))
BC_POINT = (V((-1.05, -3.25, 2.48 + ZO)), V((0.10, -1.0, -0.02)).normalized(), V((0.40, 0.0, 0.92)))
BC_TUCK = (RPOS + V((0.05, 0.10, 0.22)), RF, RU)


def bc_body(t):
    ti = BC['impact_f'] / FPS
    w1 = smooth(t, 0.0, 0.28)
    k = smooth(t, 0.55, ti)
    r = smooth(t, 0.95, 1.30)
    return bodyD((0.0, -0.14 * k * (1 - r), -0.02 * k * (1 - r)), pitch=(-0.06 * w1 * (1 - k) + 0.035 * k) * (1 - r),
                 roll=0.04 * w1 * (1 - r))


def clip_beat_command():
    c = Clip('BeatCommand', 32 / FPS, False)
    ti = BC['impact_f'] / FPS
    qR, e1 = solve_key('R', BC_RAISE, bc_body(0.28), Z7)
    qH, e2 = solve_key('R', BC_HOLD, bc_body(0.50), qR)
    qP, e3 = solve_key('R', BC_POINT, bc_body(ti), qH, world=True)
    qT, e4 = solve_key('L', BC_TUCK, bc_body(0.30), Z7)
    keysR = [(0.0, Z7), (0.28, qR), (0.50, qH), (ti, qP), (0.95, qP), (1.30, Z7)]
    keysL = [(0.0, Z7), (0.30, qT), (0.95, qT), (1.30, Z7)]
    err = max(e1, e2, e3, e4)
    for f, t in enumerate(c.times):
        D = bc_body(t)
        w1 = smooth(t, 0.0, 0.28)
        k = smooth(t, 0.55, ti)
        r = smooth(t, 0.95, 1.30)
        g = keyval(t, [(0.0, GAPE_REST), (0.28, 38.0), (0.50, 42.0), (16 / FPS, 42.0)])
        if f == 17:
            g = 20.0
        elif f >= 18:
            g = keyval(t, [(ti, 0.0), (0.95, 3.0), (1.30, GAPE_REST)])
        lt = smooth(t, 0.05, 0.30) * (1 - r)
        ex = {'Claw_R_Dactyl': gape_basis(g), 'Claw_L_Dactyl': gape_basis(GAPE_REST - 6 * lt)}
        ex.update(stalks(tilt=(-0.14 * w1 * (1 - k) + 0.18 * k) * (1 - r), side=0.10 * w1 * (1 - k) * (1 - r)))
        B, _ = pose_frame(D, planted_legs(), ex,
                          claw_q={'R': interp_q(t, keysR, {2: ease_in(1.7)}), 'L': interp_q(t, keysL)})
        add(c, B, err, {tg: True for tg in LEG_TAGS})
    c.meta = {'warnStart': 0.10, 'impact': ti, 'activeEnd': ti, 'recoveryEnd': 1.20}
    return c


# ------------------------------------------------------------- ClawSlam
SL = {'impact_f': 20, 'wind_t': 0.5417, 'z_imp': 0.62}
SL_WIND = (V((-1.60, -2.30, 3.62 + ZO)), V((-0.10, 0.30, 0.95)).normalized(), V((0.25, -0.85, 0.45)))


def slam_impact():
    return (V((-1.15, -3.62, SL['z_imp'])), V((0.15, -0.95, -0.28)).normalized(), V((0.35, 0.0, 0.94)))


REAR = dict(off=V((0, 0.10, 0.30)), pitch=-0.20)
HIT = dict(off=V((0, -0.18, -0.08)), pitch=0.05)


def sl_body(t):
    ti = SL['impact_f'] / FPS
    tw = SL['wind_t']
    a = smooth(t, 0.15, 0.46)
    if t <= tw:
        off, pitch = REAR['off'] * a + V((0, 0.02, 0.04)) * smooth(t, 0.46, tw), REAR['pitch'] * a
    elif t <= ti:
        u = ((t - tw) / (ti - tw)) ** 1.2
        r0 = REAR['off'] + V((0, 0.02, 0.04))
        off, pitch = r0.lerp(HIT['off'], u), lerp(REAR['pitch'], HIT['pitch'], u)
    else:
        bb = math.sin(math.pi * min(1.0, (t - ti) / 0.20)) if t < ti + 0.20 else 0.0
        r = smooth(t, 1.0, 1.50)
        off, pitch = HIT['off'] * (1 - r) + V((0, 0, 0.07 * bb)), HIT['pitch'] * (1 - r) - 0.03 * bb
    return bodyD(tuple(off), pitch=pitch)


def slam_keys(sides='RL'):
    ti = SL['impact_f'] / FPS
    tw = SL['wind_t']
    out = {}
    for sd in sides:
        qW, e1 = solve_key(sd, SL_WIND, sl_body(0.46), Z7, world=True)
        qW2, e2 = solve_key(sd, (SL_WIND[0] + V((0, 0.05, 0.05)), SL_WIND[1], SL_WIND[2]), sl_body(tw), qW, world=True)
        qI, e3 = solve_key(sd, slam_impact(), sl_body(ti), qW2, world=True)
        out[sd] = ([(0.0, Z7), (0.15, Z7), (0.46, qW), (tw, qW2), (ti, qI), (1.0, qI), (1.50, Z7)], max(e1, e2, e3))
    return out


def calibrate_slam():
    """Land the claws: lowest claw vertex 0.02 above the sand at impact."""
    ti = SL['impact_f'] / FPS
    for _ in range(5):
        keys = slam_keys('RL')
        LEG_STATE.clear()
        B, _ = pose_frame(sl_body(ti), planted_legs(), {}, claw_q={sd: keys[sd][0][4][1] for sd in 'RL'})
        zc = float(posed(B)[SEC_IDX['Claws'], 2].min())
        SL['z_imp'] += 0.02 - zc
        if abs(zc - 0.02) < 0.006:
            break


def clip_claw_slam():
    c = Clip('ClawSlam', 39 / FPS, False)
    ti = SL['impact_f'] / FPS
    tw = SL['wind_t']
    keys = slam_keys('RL')
    err = max(v[1] for v in keys.values())
    for f, t in enumerate(c.times):
        D = sl_body(t)
        a = smooth(t, 0.15, 0.46)
        g = keyval(t, [(0.15, GAPE_REST), (0.46, 35.0), (tw, 35.0), (ti, 4.0), (1.0, 4.0), (1.50, GAPE_REST)])
        ex = {f'Claw_{sd}_Dactyl': gape_basis(g) for sd in 'RL'}
        kk = smooth(t, tw, ti)
        ex.update(stalks(tilt=(-0.15 * a * (1 - kk) + 0.25 * kk) * (1 - smooth(t, 1.0, 1.5)), spread=0.08 * kk))
        cq = {sd: interp_q(t, keys[sd][0], {3: ease_in(1.2)}) for sd in 'RL'}
        B, _ = pose_frame(D, planted_legs(), ex, claw_q=cq)
        add(c, B, err, {tg: True for tg in LEG_TAGS})
    c.meta = {'warnStart': 0.15, 'impact': ti, 'activeEnd': ti, 'recoveryEnd': 1.40}
    return c


# -------------------------------------------------------------- Bombard
BB = {'signal_f': 14}
BB_UP = (V((-1.42, -2.45, 3.10 + ZO)), V((0.15, -0.30, 1.0)).normalized(), V((0.70, -0.70, 0.0)))
BB_DN = (V((-1.32, -2.88, 2.55 + ZO)), V((0.20, -0.65, 0.72)).normalized(), V((0.55, -0.30, 0.75)))


def bb_body(t):
    ts = BB['signal_f'] / FPS
    z = keyval(t, [(0.0, 0.0), (0.25, 0.10), (0.40, 0.0), (ts, 0.14), (0.75, 0.0), (1.10, 0.0)])
    pitch = keyval(t, [(0.0, 0.0), (0.25, -0.05), (0.40, 0.0), (ts, -0.06), (0.75, 0.0)])
    return bodyD((0, 0, z), pitch=pitch), z


def clip_bombard():
    c = Clip('Bombard', 29 / FPS, False)
    ts = BB['signal_f'] / FPS
    up2 = (BB_UP[0] + V((0, 0, 0.08)), BB_UP[1], BB_UP[2])
    keys, err = {}, 0.0
    for sd in 'RL':
        q1, e1 = solve_key(sd, BB_UP, bb_body(0.25)[0], Z7)
        q2, e2 = solve_key(sd, BB_DN, bb_body(0.40)[0], q1)
        q3, e3 = solve_key(sd, up2, bb_body(ts)[0], q2)
        keys[sd] = [(0.0, Z7), (0.25, q1), (0.40, q2), (ts, q3), (0.75, q2), (1.10, Z7)]
        err = max(err, e1, e2, e3)
    for t in c.times:
        D, z = bb_body(t)
        g = keyval(t, [(0.0, GAPE_REST), (0.25, 36.0), (0.40, 18.0), (ts, 40.0), (0.75, 18.0), (1.10, GAPE_REST)])
        ex = {f'Claw_{sd}_Dactyl': gape_basis(g) for sd in 'RL'}
        ex.update(stalks(tilt=-1.2 * z, side=0.08 * math.sin(2 * math.pi * t / 1.2)))
        B, _ = pose_frame(D, planted_legs(), ex, claw_q={sd: interp_q(t, keys[sd]) for sd in 'RL'})
        add(c, B, err, {tg: True for tg in LEG_TAGS})
    c.meta = {'warnStart': 0.10, 'impact': ts, 'activeEnd': ts, 'recoveryEnd': 1.00, 'pumps': [0.25, round(ts, 4)]}
    return c


# ---------------------------------------------------------------- Intro
IN = {'snap_f': 48, 'pulses': [0.40 + k * BEAT for k in range(4)]}
IN_CROUCH = (V((-1.25, -2.55, 1.78 + ZO)), V((0.15, -0.75, 0.60)).normalized(), V((0.50, 0.0, 0.85)))
IN_READY = (V((-1.10, -2.85, 2.70 + ZO)), V((0.20, -0.55, 0.80)).normalized(), V((0.75, -0.55, 0.20)))
IN_WIDE = (V((-2.25, -2.60, 2.85 + ZO)), V((-0.65, -0.30, 0.70)).normalized(), V((0.20, -0.95, 0.25)))


def in_body(t):
    ts = IN['snap_f'] / FPS
    z = keyval(t, [(0.0, -0.12), (1.15, -0.12), (1.80, 0.05), (ts, 0.05), (2.40, 0.10), (3.0, 0.0)])
    for k, pz in enumerate(IN['pulses']):
        x = (t - pz) / 0.18
        if 0.0 <= x <= 1.0:
            z -= (0.05 + 0.01 * k) * math.sin(math.pi * x)
    if ts <= t <= ts + 0.15:
        z -= 0.03 * math.sin(math.pi * (t - ts) / 0.15)
    pitch = keyval(t, [(0.0, 0.05), (1.15, 0.05), (1.80, 0.0), (ts, 0.04), (2.40, -0.08), (3.0, 0.0)])
    return bodyD((0, 0, z), pitch=pitch)


def clip_intro():
    c = Clip('Intro', 72 / FPS, False)
    ts = IN['snap_f'] / FPS
    keys, err = {}, 0.0
    for sd in 'RL':
        q0, e0 = solve_key(sd, IN_CROUCH, in_body(0.0), Z7)
        q1, e1 = solve_key(sd, IN_READY, in_body(1.80), q0)
        q2, e2 = solve_key(sd, IN_WIDE, in_body(2.40), q1)
        keys[sd] = [(0.0, q0), (1.15, q0), (1.80, q1), (ts, q1), (2.40, q2), (3.0, Z7)]
        err = max(err, e0, e1, e2)
    for f, t in enumerate(c.times):
        D = in_body(t)
        if f <= 46:
            g = keyval(t, [(0.0, 2.0), (1.15, 2.0), (1.80, 45.0)])
        elif f <= IN['snap_f']:
            g = 22.0 if f == 47 else 0.0
        else:
            g = keyval(t, [(ts, 0.0), (2.40, 32.0), (3.0, GAPE_REST)])
        ex = {f'Claw_{sd}_Dactyl': gape_basis(g) for sd in 'RL'}
        tilt = keyval(t, [(0.0, 0.10), (1.0, 0.10), (1.12, 0.16), (1.30, 0.0), (2.0, 0.0), (2.40, -0.06), (3.0, 0.0)])
        slide = keyval(t, [(0.0, -0.24), (1.0, -0.24), (1.10, 0.0)])
        ex.update(stalks(tilt=tilt, slide=slide, spread=keyval(t, [(0.0, 0.0), (1.12, 0.12), (1.3, 0.0)])))
        B, _ = pose_frame(D, planted_legs(), ex, claw_q={sd: interp_q(t, keys[sd]) for sd in 'RL'})
        add(c, B, err, {tg: True for tg in LEG_TAGS})
    c.meta = {'warnStart': 0.0, 'impact': ts, 'activeEnd': ts, 'recoveryEnd': 3.0,
              'pulses': [round(pz, 4) for pz in IN['pulses']], 'eyestalkPop': 1.0, 'victory': 2.4}
    return c


# ---------------------------------------------------------------- Death
DEATH = {'drop': 0.95, 'claw_z': 0.55}


def death_pose(t):
    st = smooth(t, 0.0, 0.30)
    cl = smooth(t, 0.30, 1.20)
    cl_in = cl * cl
    bounce = 0.06 * math.sin(math.pi * min(1.0, (t - 1.2) / 0.3)) if 1.2 < t < 1.5 else 0.0
    D = bodyD((0.0, 0.25 * math.sin(math.pi * st) * (1 - cl) + 0.10 * cl,
               0.15 * math.sin(math.pi * st) * (1 - cl) - DEATH['drop'] * cl_in + bounce),
              pitch=-0.12 * math.sin(math.pi * st) * (1 - cl) + 0.05 * cl, roll=-0.05 * cl)
    legs = {}
    for tag in LEG_TAGS:
        radial = V((RT[tag].x, RT[tag].y, 0)).normalized()
        legs[tag] = RT[tag] + radial * (1.2 * cl) + V((0, 0, 0.32 * cl))
    final = (V((-1.50, -3.00, DEATH['claw_z'])), V((0.20, -0.95, -0.10)).normalized(), V((0.30, 0.0, 0.95)))
    claws = {}
    for s in 'RL':
        pa = mir(RPOS + V((0, 0.05, 0.25)) * math.sin(math.pi * st) * (1 - cl), s)
        fa = mir(RF, s)
        D0_ = bodyD((0.0, 0.25 * math.sin(math.pi * st), 0.15 * math.sin(math.pi * st)), pitch=-0.12 * math.sin(math.pi * st))
        start_pos = D0_ @ pa
        start_f = D0_.to_3x3() @ fa
        start_u = D0_.to_3x3() @ mir(RU, s)
        k = smooth(t, 0.30, 1.10)
        pos = start_pos.lerp(mir(final[0], s), k)
        fwd = start_f.lerp(mir(final[1], s), k).normalized()
        up = start_u.lerp(mir(final[2], s), k).normalized()
        rot = frame3(fwd, up) @ frame3(REST_F[s], REST_U[s]).transposed() @ REST_PROP[s].to_3x3()
        claws[s] = (pos, rot)
    g = keyval(t, [(0.0, GAPE_REST), (0.30, 35.0), (1.20, 25.0), (1.62, 25.0), (1.70, 6.0), (1.80, 25.0)])
    ex = {f'Claw_{s}_Dactyl': gape_basis(g) for s in 'RL'}
    ex.update(stalks(tilt=-0.2 * math.sin(math.pi * st) * (1 - cl) + 0.75 * smooth(t, 0.6, 1.4),
                     spread=0.25 * smooth(t, 0.6, 1.4)))
    return D, legs, ex, claws, keyval(t, [(0.3, JMIN), (1.2, 0.46)])


def death_claw_keys():
    """Claws keyposed: a short flail (body-relative), then flat on the sand beside the face (world)."""
    keys, err = {}, 0.0
    flail = (RPOS + V((0, 0.05, 0.25)), RF, RU)
    for sd in 'LR':
        Df = death_pose(0.15)[0]
        qF, e1 = solve_key(sd, flail, Df, Z7)
        final = (V((-1.50, -3.00, DEATH['claw_z'])), V((0.20, -0.95, -0.10)).normalized(), V((0.30, 0.0, 0.95)))
        qE, e2 = solve_key(sd, final, death_pose(2.0)[0], qF, world=True)
        keys[sd] = [(0.0, Z7), (0.15, qF), (0.30, qF), (1.20, qE), (2.0, qE)]
        err = max(err, e1, e2)
    return keys, err


def death_frames(c):
    LEG_STATE.clear()
    CLAW_STATE.clear()
    CLAW_TGT.clear()
    keys, err = death_claw_keys()
    out = []
    for t in c.times:
        D, legs, ex, _, fl = death_pose(t)
        B, _ = pose_frame(D, legs, ex, floor=fl, claw_q={sd: interp_q(t, keys[sd]) for sd in 'LR'})
        out.append(B)
    return out, err


def clip_death():
    c = Clip('Death', 48 / FPS, False)
    # calibrate on the whole clip: lowest shell/gear/eye point and lowest claw point 0.02 above the sand
    vb = MESH.vbone
    root_parts = np.array([str(b).endswith('_Coxa') or str(b).endswith('Claw_L_Merus') or str(b).endswith('Claw_R_Merus')
                           for b in vb])
    body_idx = np.concatenate([SEC_IDX[s_] for s_ in ('Shell', 'Gear', 'Glow', 'Eyes', 'Legs')] + [np.nonzero(root_parts)[0]])
    hand_idx = np.nonzero(np.isin(vb, [f'Claw_{x}_{y}' for x in 'LR' for y in ('Carpus', 'Propodus', 'Dactyl')]))[0]
    for _ in range(4):
        frames, err = death_frames(c)
        pvs = [posed(B) for B in frames]
        zo = min(float(pv[body_idx, 2].min()) for pv in pvs)
        zc = min(float(pv[hand_idx, 2].min()) for t, pv in zip(c.times, pvs) if t >= 1.2)
        DEATH['drop'] += zo - 0.02
        DEATH['claw_z'] = min(1.0, max(0.3, DEATH['claw_z'] + 0.03 - zc))
        if abs(zo - 0.02) < 0.012 and abs(zc - 0.03) < 0.012:
            break
    frames, err = death_frames(c)
    for B in frames:
        add(c, B, err, {tg: False for tg in LEG_TAGS})
    return c


# --------------------------------------------------------------- build
def finalize(c):
    ident = {n: I4.copy() for n in ORDER}

    def diff(A, Bm):
        return max(max(abs(a - b) for ra, rb in zip(A.get(n, I4), Bm.get(n, I4)) for a, b in zip(ra, rb)) for n in ORDER)
    if c.loop:
        c.meta['loop_error_before_snap'] = diff(c.bases[0], c.bases[-1])
        if c.name == 'Idle':
            # Idle frame 0 is the Idle start pose = the rest pose the attacks start and end on
            c.meta['start_error_before_snap'] = diff(c.bases[0], ident)
            c.bases[0] = dict(ident)
        c.bases[-1] = {n: m.copy() for n, m in c.bases[0].items()}
    elif c.name == 'Intro':
        # the cinematic starts crouched (by design); it ends on the Idle start pose
        c.meta['end_error_before_snap'] = diff(c.bases[-1], ident)
        c.bases[-1] = dict(ident)
    elif c.name != 'Death':
        c.meta['start_error_before_snap'] = diff(c.bases[0], ident)
        c.meta['end_error_before_snap'] = diff(c.bases[-1], ident)
        c.bases[0] = dict(ident)
        c.bases[-1] = dict(ident)
    else:
        c.meta['start_error_before_snap'] = diff(c.bases[0], ident)
        c.bases[0] = dict(ident)
    for B in c.bases:
        for n in ORDER:
            B.setdefault(n, I4.copy())


calibrate_slam()
log('slam impact palm z', round(SL['z_imp'], 4))
CLIPS = {}
for fn in (clip_idle, clip_walk, clip_hit, clip_death, clip_beat_command, clip_claw_slam, clip_bombard, clip_intro):
    LEG_STATE.clear()
    CLAW_STATE.clear()
    CLAW_TGT.clear()
    c = fn()
    finalize(c)
    CLIPS[c.name] = c
    log('clip', c.name, len(c.bases), 'frames', round(c.duration, 4), 's', 'claw IK err', round(max(c.claw_err), 4))
log('death drop', round(DEATH['drop'], 4), 'claw z', round(DEATH['claw_z'], 4))


# ---------------------------------------------------------------- checks
def ik_tip_error(c):
    worst = 0.0
    for f, B in enumerate(c.bases):
        P = fk(B)
        tips = MC.leg_tips(SK, P, BLEN)
        for t in LEG_TAGS:
            if c.stance[f].get(t):
                worst = max(worst, (tips[t] - (RT[t] if c.name != 'Walk' else foot_cycle(t, f / WALK_N)[0])).length)
    return worst


def planted(clip, f, tag):
    return bool(CLIPS[clip].stance[f].get(tag))


SNAPS = {'BeatCommand': {'Claw_R_Dactyl': [17, 18]},
         'Intro': {'Claw_R_Dactyl': [47, 48], 'Claw_L_Dactyl': [47, 48]}}
mc = MC.run(SK, MESH, BLEN, {n: {'bases': c.bases, 'times': c.times} for n, c in CLIPS.items()}, planted,
            travel={'Walk': TRAVEL * WALK_V}, snaps=SNAPS)
checks = {'source': 'animate_game.py on DJCrab.blend (source rig)', 'clips': {}}
for name, c in CLIPS.items():
    e = {'frames': len(c.bases), 'duration': round(c.duration, 4),
         'max_ik_tip_error_studs': round(ik_tip_error(c), 4),
         'max_claw_ik_palm_error_studs': round(max(c.claw_err), 4)}
    for k in ('loop_error_before_snap', 'start_error_before_snap', 'end_error_before_snap'):
        if k in c.meta:
            e[k] = round(c.meta[k], 5)
    e.update(mc['clips'][name])
    checks['clips'][name] = e
checks['rest_contacts'] = mc['rest_contacts']
checks['joint_range_by_kind_deg'] = mc['joint_range_by_kind_deg']
checks['joint_limits_deg'] = mc['joint_limits_deg']
checks['worst'] = mc['worst']
checks['intentional_snaps'] = SNAPS
log('checks worst', json.dumps(mc['worst']))
for n, e in checks['clips'].items():
    log(n, 'ik', e['max_ik_tip_error_studs'], 'drift', e['max_planted_tip_drift'], 'low', e['lowest_point'],
        'hinge', e['hinge_violation_count'], 'twist', e['max_twist_deg'], 'rot', e['max_bone_rotation_per_frame_deg'],
        'overlaps', json.dumps(e['overlaps']))
log('rest contacts', json.dumps(mc['rest_contacts']))


# ---------------------------------------------------------- reach at impact
def reach(clip, f, side):
    P = fk(CLIPS[clip].bases[f])
    s = P[f'Claw_{side}_Merus'].translation
    palm = P[f'Claw_{side}_Propodus'] @ PALM_LOCAL
    chain = sum(BLEN[f'Claw_{side}_{x}'] for x in ('Merus', 'Carpus')) + PALM_LOCAL.y
    return (palm - s).length / chain


checks['slam_reach_at_impact'] = {s: round(reach('ClawSlam', SL['impact_f'], s), 3) for s in 'RL'}
checks['beatcommand_reach_at_impact'] = round(reach('BeatCommand', BC['impact_f'], 'R'), 3)
checks['death_final'] = {'drop': round(DEATH['drop'], 4), 'claw_palm_z': round(DEATH['claw_z'], 4)}
checks['slam_palm_z'] = round(SL['z_imp'], 4)

# ------------------------------------------------------ AnimationData.json
S = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def cf(m):
    m = S @ m @ S
    return [round(x, 7) for x in [m[0][3], m[1][3], m[2][3], m[0][0], m[0][1], m[0][2], m[1][0], m[1][1],
                                  m[1][2], m[2][0], m[2][1], m[2][2]]]


DEFORM = [b.name for b in rig.data.bones if b.use_deform]
anim = {'id': BOSS_ID, 'fps': FPS,
        'bones': {b.name: {'parent': b.parent.name if b.parent else None,
                           'rest': cf(b.parent.matrix_local.inverted() @ b.matrix_local if b.parent else b.matrix_local)}
                  for b in rig.data.bones if b.use_deform},
        'clips': {},
        'motion': {'strideLength': round(WALK_V * WALK_T, 4), 'nominalSpeed': round(WALK_V, 4)}}
for name, c in CLIPS.items():
    anim['clips'][name] = {'duration': round(c.duration, 7), 'loop': c.loop,
                           'frames': [{'time': round(t, 7), 'transforms': {n: cf(B[n]) for n in DEFORM}}
                                      for t, B in zip(c.times, c.bases)]}
anim['clips']['Idle']['beats'] = 8
anim['clips']['Idle']['note'] = ('8 beats at 124 BPM: frames 0-92 at 1/24 s, then a closure frame at 3.8709677 s '
                                 'equal to frame 0 (the loop is exactly 8 beats, not 93/24 s)')
(GAME / 'AnimationData.json').write_text(json.dumps(anim, separators=(',', ':')))
log('AnimationData.json written')


# ------------------------------------------------------- BossGameData.json
def studio(v):
    return [round(-v[0], 4), round(v[2], 4), round(v[1], 4)]


def r4(v):
    return [round(x, 4) for x in v]


def point_at(clip, frame, bone, offset):
    P = fk(CLIPS[clip].bases[frame])[bone]
    w = P @ Vector(offset)
    return {'bone': bone, 'offset': r4(offset), 'rootAtImpact': r4(w), 'rootAtImpactStudio': studio(w)}


gear = MESH.verts[SEC_IDX['Gear']]
top_z = float(gear[:, 2].max())
tops = gear[gear[:, 2] > top_z - 0.03]
SPEAKER_TOP_REST = V((0.0, float(tops[:, 1].mean()), top_z))
SPK_OFF = REST['Body'].inverted() @ SPEAKER_TOP_REST


def attack_entry(name, extra=None):
    c = CLIPS[name]
    m = c.meta
    e = {'duration': round(c.duration, 4), 'warnStart': round(m['warnStart'], 4), 'impact': round(m['impact'], 4),
         'activeEnd': round(m['activeEnd'], 4), 'recoveryEnd': round(m['recoveryEnd'], 4), 'points': {}}
    e.update(extra or {})
    return e


game = {'attacks': {}}
fi = BC['impact_f']
e = attack_entry('BeatCommand', {'note': 'right pincer raised like a conductor, held a beat, swept forward and snapped '
                                         'shut pointing ahead at impact; no damage, orders the crab reinforcements to rush'})
e['points']['CommandClaw'] = point_at('BeatCommand', fi, 'Claw_R_Propodus', tuple(TIP_LOCAL['R']))
Ph = fk(CLIPS['BeatCommand'].bases[fi])['Claw_R_Propodus']
d = axis(Ph, 1)
dh = V((d.x, d.y, 0)).normalized()
e['directionAtImpact'], e['directionAtImpactStudio'] = r4(dh), studio(dh)
e['handDirectionAtImpact3D'] = r4(d)
game['attacks']['BeatCommand'] = e

fi = SL['impact_f']
e = attack_entry('ClawSlam', {'note': 'rears up, both claws high and back (windup 0.15-0.625 s), slams both down in front '
                                      'at impact, body bounces; spawn the expanding ground ring at SlamCenter on impact'})
for side, nm in (('L', 'LeftClaw'), ('R', 'RightClaw')):
    e['points'][nm] = point_at('ClawSlam', fi, f'Claw_{side}_Propodus', tuple(TIP_LOCAL[side]))
mid = (V(e['points']['LeftClaw']['rootAtImpact']) + V(e['points']['RightClaw']['rootAtImpact'])) / 2
mid.z = 0.0
e['points']['SlamCenter'] = {'bone': 'Root', 'offset': r4(REST['Root'].inverted() @ mid), 'rootAtImpact': r4(mid),
                             'rootAtImpactStudio': studio(mid), 'note': 'ground point midway between the claw tips'}
game['attacks']['ClawSlam'] = e

fi = BB['signal_f']
e = attack_entry('Bombard', {'note': 'both claws pump overhead twice (crowd hype); the bombardment signal is the second pump',
                             'pumps': CLIPS['Bombard'].meta['pumps']})
e['points']['SpeakerTop'] = point_at('Bombard', fi, 'Body', tuple(SPK_OFF))
game['attacks']['Bombard'] = e

fi = IN['snap_f']
e = attack_entry('Intro', {'note': 'cinematic power-up: crouched and still, speakers thump (body pulses) from 0.4 s, '
                                   'eyestalks pop up at 1.0 s, both claws snap shut on the accent at exactly 2.0 s (impact), '
                                   'claws thrown wide at 2.4 s, settles to the Idle start pose at 3.0 s',
                           'pulses': CLIPS['Intro'].meta['pulses'], 'eyestalkPop': 1.0, 'victoryPose': 2.4})
e['points']['SpeakerTop'] = point_at('Intro', fi, 'Body', tuple(SPK_OFF))
game['attacks']['Intro'] = e

allv = MESH.verts
game.update({
    'rootHeight': 0.0, 'height': round(float(allv[:, 2].max()), 4),
    'footprintRadius': round(float(np.sqrt((allv[:, :2] ** 2).sum(1)).max()), 4),
    'bodyCentreHeight': round(BODY_PIVOT.z, 4),
    'walk': {'strideLength': anim['motion']['strideLength'], 'nominalSpeed': anim['motion']['nominalSpeed'],
             'gait': 'alternating tetrapod groups', 'groupA': sorted(GROUP_A), 'duty': WALK_DUTY,
             'groupBPhaseOffset': 0.5},
    'music': {'bpm': BPM, 'beatSeconds': round(BEAT, 7), 'track': 'Syn Cole - Feel Good (beat grid TBD in Studio)'},
    'idle': {'loopSeconds': round(IDLE_T, 7), 'beats': 8, 'beatTimes': [round(k * BEAT, 4) for k in range(8)],
             'bodyDownOnEveryBeat': True, 'rightClawStrikesOnBeats': [1, 3, 5, 7], 'leftClawStrikesOnBeats': [2, 4, 6, 8],
             'note': 'start the Idle loop on a beat; frame 0 is a downbeat'},
    'notes': 'Times in seconds from clip start at 24 fps. Root bone sits on the ground under the body centre '
             '(rootHeight 0). Blender axes: +X crab left, -Y forward, +Z up; Studio = (-X, Z, Y). Headphones, '
             'speakers, straps and saddle are rigid on Body (not separate damage targets). Glow pieces: DJCrab_Glow.'})
(GAME / 'BossGameData.json').write_text(json.dumps(game, indent=2))
checks['motion'] = anim['motion']
(GAME / 'GameChecks.json').write_text(json.dumps(checks, indent=2))
log('BossGameData.json + GameChecks.json written')

# posed vertex samples for the validator's skinning comparison (3 frames per clip)
samples = {}
for name, c in CLIPS.items():
    fr = sorted({0, len(c.bases) // 2, len(c.bases) - 1})
    samples[name] = {str(f): posed(c.bases[f]).astype(np.float32).tolist() for f in fr}
order_info = {s: len(SEC_IDX[s]) for s in SECTIONS}
(WORK / 'posed_samples.json').write_text(json.dumps({'sections': SECTIONS, 'counts': order_info, 'samples': samples}))

if QUICK:
    log('QUICK_DONE')
    sys.exit(0)

# ----------------------------------------------------------- Blender actions
for name, c in CLIPS.items():
    old = bpy.data.actions.get(name)
    if old:
        bpy.data.actions.remove(old)
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    rig.animation_data.action = act
    for t, B in zip(c.times, c.bases):
        for pb in rig.pose.bones:
            pb.matrix_basis = B[pb.name]
            pb.keyframe_insert('location', frame=1 + t * FPS, group=pb.name)
            pb.keyframe_insert('rotation_quaternion', frame=1 + t * FPS, group=pb.name)
    if name in ('BeatCommand', 'ClawSlam', 'Bombard', 'Intro'):
        act.pose_markers.new('Impact').frame = 1 + round(c.meta['impact'] * FPS)
rig.animation_data.action = None
for pb in rig.pose.bones:
    pb.matrix_basis = I4
log('actions keyed')

# ---------------------------------------------------------------- Studio FBX
FBM = GAME / f'{NAME}_Studio.fbm'
FBM.mkdir(exist_ok=True)
atlas = OUT / 'textures' / f'{NAME}_Atlas_BaseColor_1024.png'
shutil.copy2(atlas, FBM / atlas.name)
img = bpy.data.images.load(str(atlas), check_existing=True)
keep = {}
for sec in SECTIONS:
    m = bpy.data.materials[f'{NAME}_{sec}']
    node = m.node_tree.nodes['BaseColor']
    keep[sec] = node.image
    node.image = img
rig.data.pose_position = 'REST'
bpy.context.view_layer.update()
for ob in bpy.context.view_layer.objects:
    ob.select_set(False)
rig.select_set(True)
for ob in SECS.values():
    ob.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.export_scene.fbx(filepath=str(GAME / f'{NAME}_Studio.fbx'), use_selection=True,
                         object_types={'MESH', 'ARMATURE'}, bake_anim=False, add_leaf_bones=False,
                         use_armature_deform_only=True, axis_forward='-Z', axis_up='Y',
                         path_mode='COPY', embed_textures=True, use_mesh_modifiers=False,
                         mesh_smooth_type='OFF', primary_bone_axis='Y', secondary_bone_axis='X')
for sec in SECTIONS:
    bpy.data.materials[f'{NAME}_{sec}'].node_tree.nodes['BaseColor'].image = keep[sec]
rig.data.pose_position = 'POSE'
log('Studio FBX exported')

# ------------------------------------------------------------------ previews
cam = scene.camera
ground = bpy.data.objects.get('ReviewGround')
world = scene.world
if world and world.node_tree:
    world.node_tree.nodes['Background'].inputs[0].default_value = (0.55, 0.70, 0.95, 1)
    world.node_tree.nodes['Background'].inputs[1].default_value = 0.65
sun = bpy.data.objects.get('ReviewSun')
if sun:
    sun.data.color = (1.0, 0.90, 0.76)
    sun.data.energy = 3.6


def set_pose(B):
    for pb in rig.pose.bones:
        pb.matrix_basis = B.get(pb.name, I4)
    bpy.context.view_layer.update()


def aim(loc, tgt, lens):
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.type = 'PERSP'
    cam.data.lens = lens


def workbench():
    scene.render.engine = 'BLENDER_WORKBENCH'
    sh = scene.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'TEXTURE'
    sh.show_shadows = True
    sh.show_cavity = False
    scene.display.render_aa = '8'


def eevee():
    for eid in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
        try:
            scene.render.engine = eid
            break
        except TypeError:
            continue
    try:
        scene.eevee.taa_render_samples = 32
    except Exception:
        pass


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
    im = bpy.data.images.load(str(path))
    w, h = im.size
    a = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)


def save_px(arr, path):
    h, w = arr.shape[:2]
    im = bpy.data.images.new('sheet_tmp', w, h, alpha=True)
    im.pixels.foreach_set(arr.astype(np.float32).ravel())
    im.filepath_raw = str(path)
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)


def sheet(rows, path):
    h, w = rows[0][0].shape[:2]
    cols = max(len(r) for r in rows)
    out = np.ones((h * len(rows), w * cols, 4), np.float32) * np.array([0.12, 0.12, 0.14, 1.0])
    for r, row in enumerate(rows):
        for k, im in enumerate(row):
            y0 = (len(rows) - 1 - r) * h
            out[y0:y0 + h, k * w:(k + 1) * w] = im
    save_px(out, path)


FRONT34 = (V((-11.5, -13.5, 5.6)), V((0, -1.0, 1.7)), 58)
SIDE = (V((-16.5, -1.2, 2.9)), V((0, -1.2, 1.7)), 55)
labels = {}
eevee()
try:
    scene.eevee.taa_render_samples = 16
except Exception:
    pass
rows = []
for name in ('Idle', 'Walk', 'Hit', 'Death', 'BeatCommand', 'ClawSlam', 'Bombard', 'Intro'):
    c = CLIPS[name]
    n = len(c.bases) - (1 if c.loop else 0)
    if name == 'BeatCommand':
        fr = [0, 7, 12, 16, BC['impact_f'], 26]
    elif name == 'ClawSlam':
        fr = [0, 8, 15, 18, SL['impact_f'], 30]
    elif name == 'Bombard':
        fr = [0, 6, 10, BB['signal_f'], 18, 26]
    elif name == 'Intro':
        fr = [0, 24, 30, 45, IN['snap_f'], 58]
    else:
        fr = sorted({round(k * (n - 1) / 5) for k in range(6)})
    labels[name] = [round(c.times[f], 3) for f in fr]
    aim(*FRONT34)
    row = []
    for f in fr:
        set_pose(c.bases[f])
        p = WORK / f'gc_{name}_{f:03d}.png'
        render_png(p, 256, 192)
        row.append(load_px(p))
    rows.append(row)
sheet(rows, PREV / 'GameClips.png')
log('GameClips.png')

for name, fr in (('ClawSlam', [15, SL['impact_f'], 32]), ('BeatCommand', [12, BC['impact_f'], 28])):
    rows = []
    for view in (FRONT34, SIDE):
        aim(*view)
        row = []
        for f in fr:
            set_pose(CLIPS[name].bases[f])
            p = WORK / f'atk_{name}_{f:03d}.png'
            render_png(p, 400, 300)
            row.append(load_px(p))
        rows.append(row)
    sheet(rows, PREV / f'Attack_{name}.png')
    labels[f'Attack_{name}'] = [round(CLIPS[name].times[f], 3) for f in fr]
log('attack strips')

fr = [0, 10, 24, 27, 44, IN['snap_f'], 58, 72]
aim(V((-9.5, -12.0, 4.6)), V((0, -1.0, 2.0)), 50)
row = []
for f in fr:
    set_pose(CLIPS['Intro'].bases[f])
    p = WORK / f'intro_{f:03d}.png'
    render_png(p, 300, 225)
    row.append(load_px(p))
sheet([row[:4], row[4:]], PREV / 'Intro.png')
labels['Intro_strip'] = [round(CLIPS['Intro'].times[f], 3) for f in fr]
log('Intro strip')

eevee()
try:
    scene.eevee.taa_render_samples = 32
except Exception:
    pass
set_pose(CLIPS['Intro'].bases[58])
aim(V((-4.0, -13.0, 3.3)), V((0, -1.2, 2.05)), 42)
render_png(PREV / 'Hero.png', 1024, 768)
set_pose({})
log('Hero.png')
(WORK / 'sheet_labels.json').write_text(json.dumps(labels, indent=1))

aim(V((-10.5, -11.5, 5.4)), V((0, -0.6, 1.9)), 50)
scene.frame_start, scene.frame_end = 1, 96
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'DJCrab.blend'))
log('GAME_PACKAGE_COMPLETE')
