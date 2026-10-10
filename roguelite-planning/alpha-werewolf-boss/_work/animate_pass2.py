"""Blood Moon Alpha: game clips, motion checks and the Studio game package.

    blender -b --factory-startup --threads 4 --python-exit-code 1 --python animate_game.py
    (AW_NORENDER=1 skips the preview frames; compose them with compose_previews.py)

Reads AlphaWolf.blend (build_alpha_werewolf.py). Every clip is authored as a
pose descriptor per 24 fps frame and solved by a small FK/IK solver:
- spine/neck/head/tail/mane/jaw/fingers: FK rotations in character axes;
- arms and legs: two-bone IK whose middle joint is placed on the pole side of
  the root-target line, and whose two bones share one hinge axis, so knees can
  only bend forward, elbows backward, with zero forearm/shin twist;
- feet: planted at the ball (heel lift rotates about the ball), toes flat.
The sampled pose_bone.matrix_basis values are the clip data (AnimationData.json).
All checks run on the exported bases, not on the descriptors.
"""
import bpy, json, math, os, shutil, time, hashlib
from pathlib import Path
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import numpy as np

OUT = Path(__file__).resolve().parent
GAME = OUT / 'exports' / 'game'
GAME.mkdir(parents=True, exist_ok=True)
FRAMES = OUT / '_work' / 'frames'
NAME = 'AlphaWolf'
BOSS_ID = 'alpha-werewolf'
FPS = 24
RENDER = os.environ.get('AW_NORENDER') != '1'
T0 = time.time()


def log(*a):
    print('[ANIM %5.0fs]' % (time.time() - T0), *a, flush=True)


bpy.ops.wm.open_mainfile(filepath=str(OUT / f'{NAME}.blend'))
bpy.context.preferences.filepaths.save_version = 0
scene = bpy.context.scene
rig = bpy.data.objects[NAME + '_Rig']
SECS = {o.name[len(NAME) + 1:]: o for o in bpy.data.objects if o.type == 'MESH' and o.parent == rig}
rig.data.pose_position = 'POSE'
rig.location = (0, 0, 0)
rig.animation_data_create()
rig.animation_data.action = None
for pb in rig.pose.bones:
    pb.rotation_mode = 'QUATERNION'
BN = [b.name for b in rig.data.bones]
PAR = {b.name: (b.parent.name if b.parent else None) for b in rig.data.bones}
REST = {b.name: b.matrix_local.copy() for b in rig.data.bones}
R3 = {n: m.to_3x3() for n, m in REST.items()}
HEAD = {n: m.translation.copy() for n, m in REST.items()}
TAIL = {b.name: b.tail_local.copy() for b in rig.data.bones}
LOC0 = {n: (REST[PAR[n]].inverted() @ REST[n]) if PAR[n] else REST[n].copy() for n in BN}
LOC0I = {n: LOC0[n].inverted() for n in BN}
I3 = Matrix.Identity(3)
I4 = Matrix.Identity(4)
SIDES = (('Left', 1), ('Right', -1))
EPS_SNAP = {}


# ------------------------------------------------------------------ math helpers
def rot(axis, deg):
    return Matrix.Rotation(math.radians(deg), 3, Vector(axis).normalized())


def E(a):
    """(pitch, roll, yaw) in character axes: +pitch leans forward, +roll leans to the
    character's left (+X), +yaw turns to its left."""
    p, r, y = a
    return rot((0, 0, 1), y) @ rot((0, 1, 0), r) @ rot((1, 0, 0), p)


def mir(a, s):
    return (a[0], a[1] * s, a[2] * s)


def mv(v, s):
    return Vector((v[0] * s, v[1], v[2]))


def sm(a, b, x):
    t = max(0., min(1., (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def slerp3(A, B, w):
    return A.to_quaternion().slerp(B.to_quaternion(), w).to_matrix()


def frame(h, y):
    y = y.normalized()
    h = (h - y * h.dot(y)).normalized()
    return Matrix((h, y, h.cross(y))).transposed()


def pchip(ts, ys):
    """Monotone cubic through keys (no overshoot), flat tangents at both ends."""
    ts = np.asarray(ts, float)
    ys = np.asarray(ys, float)
    if ys.ndim == 1:
        ys = ys[:, None]
    h = np.diff(ts)
    dl = np.diff(ys, axis=0) / h[:, None]
    m = np.zeros_like(ys)
    for i in range(1, len(ts) - 1):
        for k in range(ys.shape[1]):
            d0, d1 = dl[i - 1, k], dl[i, k]
            if d0 * d1 > 0:
                w1 = 2 * h[i] + h[i - 1]
                w2 = h[i] + 2 * h[i - 1]
                m[i, k] = (w1 + w2) / (w1 / d0 + w2 / d1)

    def f(t):
        if t <= ts[0]:
            return ys[0].copy()
        if t >= ts[-1]:
            return ys[-1].copy()
        i = int(np.searchsorted(ts, t) - 1)
        u = (t - ts[i]) / h[i]
        h00 = 2 * u ** 3 - 3 * u ** 2 + 1
        h10 = u ** 3 - 2 * u ** 2 + u
        h01 = -2 * u ** 3 + 3 * u ** 2
        h11 = u ** 3 - u ** 2
        return h00 * ys[i] + h10 * h[i] * m[i] + h01 * ys[i + 1] + h11 * h[i] * m[i + 1]
    return f


def ch(ts, vals):
    f = pchip(ts, [np.atleast_1d(np.asarray(v, float)) for v in vals])
    if np.ndim(vals[0]) == 0:
        return lambda t: float(f(t)[0])
    if isinstance(vals[0], Vector):
        return lambda t: Vector(f(t))
    return lambda t: tuple(float(x) for x in f(t))


# ------------------------------------------------------------------ rig constants
def pole0(n1, n2):
    A, B, C = HEAD[n1], HEAD[n2], TAIL[n2]
    dn = (C - A).normalized()
    return ((B - A) - dn * (B - A).dot(dn)).normalized()


LIMBS = {}
for S, s in SIDES:
    for n1, n2 in ((S + 'UpperArm', S + 'Forearm'), (S + 'Thigh', S + 'Shin')):
        A, B, C = HEAD[n1], HEAD[n2], TAIL[n2]
        p0 = pole0(n1, n2)
        h0 = p0.cross(C - A).normalized()
        LIMBS[n1] = dict(n2=n2, L1=(B - A).length, L2=(C - B).length, p0=p0, h0=h0, F1=frame(h0, B - A), F2=frame(h0, C - B))
LAT = {}
BALL = {}
ANK = {}
for S, s in SIDES:
    f = TAIL[S + 'Toes'] - HEAD[S + 'Toes']
    f.z = 0
    LAT[S] = Vector((0, 0, 1)).cross(f.normalized()).normalized()
    BALL[S] = HEAD[S + 'Toes'].copy()
    ANK[S] = HEAD[S + 'Foot'].copy()
FING_AX = {'Left': Vector((0, 1, 0)), 'Right': Vector((0, -1, 0))}   # claws curl toward the palm (medial)
JAW_AX = Vector((1, 0, 0))                                            # + opens
WRIST0 = {S: HEAD[S + 'Hand'].copy() for S, s in SIDES}
REACH = {S: LIMBS[S + 'UpperArm']['L1'] + LIMBS[S + 'UpperArm']['L2'] for S, s in SIDES}


def ik(n1, A, C, pole):
    L = LIMBS[n1]
    L1, L2 = L['L1'], L['L2']
    d = C - A
    dist = max(d.length, 1e-6)
    dn = d / dist
    dc = min(max(dist, abs(L1 - L2) + 1e-4), (L1 + L2) * .9995)
    Cc = A + dn * dc
    a = (L1 * L1 - L2 * L2 + dc * dc) / (2 * dc)
    h = math.sqrt(max(0., L1 * L1 - a * a))
    p = pole - dn * pole.dot(dn)
    if p.length < 1e-6:
        p = L['p0'] - dn * L['p0'].dot(dn)
    p.normalize()
    B = A + dn * a + p * h
    hin = p.cross(dn).normalized()
    return frame(hin, B - A) @ L['F1'].transposed(), frame(hin, Cc - B) @ L['F2'].transposed(), (C - Cc).length


def foot_ball(S, ball, pitch=0., yaw=0., toe=0.):
    """Planted at the ball; +pitch lifts the heel about the ball; toe = world pitch of the toes."""
    Ry = rot((0, 0, 1), yaw)
    lat = Ry @ LAT[S]
    Rf = rot(lat, pitch) @ Ry
    return {'ankle': Vector(ball) + Rf @ (ANK[S] - BALL[S]), 'R': Rf, 'toe': rot(lat, toe) @ Ry, 'yaw': yaw}


def foot_ankle(S, ankle, pitch=0., yaw=0., joint=0.):
    Ry = rot((0, 0, 1), yaw)
    lat = Ry @ LAT[S]
    return {'ankle': Vector(ankle), 'R': rot(lat, pitch) @ Ry, 'toe': rot(lat, pitch - joint) @ Ry, 'yaw': yaw}


def rest_desc():
    d = {'pel': Vector(), 'pelR': (0, 0, 0), 'spine': (0, 0, 0), 'chest': (0, 0, 0), 'neck': (0, 0, 0), 'head': (0, 0, 0),
         'jaw': 0., 'mane': (0, 0, 0), 'tail': [(0, 0, 0)] * 3}
    for S, s in SIDES:
        d['sh' + S] = (0., 0.)
        d['arm' + S] = {'mode': 'chest', 'off': Vector()}
        d['wrist' + S] = (0, 0, 0)
        d['fing' + S] = 0.
        d['foot' + S] = foot_ball(S, BALL[S])
    return d


def solve(d):
    P = {}
    D = {}

    def place(n, delta, t=None):
        D[n] = delta
        if t is None:
            t = P[PAR[n]] @ LOC0[n].translation if PAR[n] else HEAD[n]
        M = (delta @ R3[n]).to_4x4()
        M.translation = t
        P[n] = M
    place('Root', I3)
    place('Pelvis', E(d['pelR']), HEAD['Pelvis'] + d['pel'])
    place('Spine', D['Pelvis'] @ E(d['spine']))
    place('Chest', D['Spine'] @ E(d['chest']))
    place('Neck', D['Chest'] @ E(d['neck']))
    place('Head', D['Neck'] @ E(d['head']))
    place('Jaw', D['Head'] @ rot(JAW_AX, d['jaw']))
    place('Mane', D['Chest'] @ E(d['mane']))
    place('Tail1', D['Pelvis'] @ E(d['tail'][0]))
    place('Tail2', D['Tail1'] @ E(d['tail'][1]))
    place('Tail3', D['Tail2'] @ E(d['tail'][2]))
    Tc = P['Chest'] @ REST['Chest'].inverted()
    info = {'armErr': 0., 'legErr': {}, 'wrist': {}, 'pole': {}, 'shoulder': {}}
    for S, s in SIDES:
        el, pr = d['sh' + S]
        a = d['arm' + S]
        for it in range(2):
            place(S + 'Shoulder', D['Chest'] @ rot((0, -s, 0), el) @ rot((0, 0, -s), pr))
            A = P[S + 'Shoulder'] @ LOC0[S + 'UpperArm'].translation
            if it:
                break
            if a['mode'] == 'chest':
                Cp = Tc @ (WRIST0[S] + a['off'])
            elif a['mode'] == 'dir':
                Cp = A + Vector(a['dir']).normalized() * a['dist']
            else:
                Cp = Vector(a['w']) if a['mode'] == 'abs' else (Tc @ (WRIST0[S] + a['off'])).lerp(Vector(a['w']), a['k'])
            down = (D['Chest'] @ Vector((0, 0, -1)))
            raise_deg = math.degrees((Cp - A).angle(down)) if (Cp - A).length > 1e-6 else 0
            extra = max(0., raise_deg - 70.) * .45                       # clavicle helps above ~70 deg
            info.setdefault('autoClavicleMax', 0.)
            info['autoClavicleMax'] = max(info['autoClavicleMax'], extra)
            el += extra
            fwd = (D['Chest'] @ Vector((0, -1, 0))).dot((Cp - A).normalized())
            pr += max(0., fwd) * extra * .5
        dpole = (D['Chest'] @ LIMBS[S + 'UpperArm']['p0']).normalized()
        mode = a['mode']
        if mode == 'chest':
            C = Tc @ (WRIST0[S] + a['off'])
            pole = (D['Chest'] @ Vector(a['pole'])) if a.get('pole') is not None else dpole
        elif mode == 'mix':
            C = (Tc @ (WRIST0[S] + a['off'])).lerp(Vector(a['w']), a['k'])
            pole = Vector(a['pole']) if a.get('pole') is not None else dpole
        elif mode == 'abs':
            C = Vector(a['w'])
            pole = Vector(a['pole']) if a.get('pole') is not None else dpole
        else:
            C = A + Vector(a['dir']).normalized() * a['dist']
            pole = Vector(a['pole']) if a.get('pole') is not None else dpole
        pw = a.get('pw', 1.0)
        if a.get('pole') is not None and pw < 1:
            pole = dpole.lerp(pole.normalized(), pw)
        Q1, Q2, err = ik(S + 'UpperArm', A, C, pole)
        info['armErr'] = max(info['armErr'], err)
        info['wrist'][S] = C.copy()
        info['pole'][S] = pole.normalized()
        info['shoulder'][S] = A.copy()
        place(S + 'UpperArm', Q1)
        place(S + 'Forearm', Q2)
        place(S + 'ShoulderHelper', slerp3(D[S + 'Shoulder'], Q1, .5))
        place(S + 'ElbowHelper', slerp3(Q1, Q2, .5))
        place(S + 'Hand', D[S + 'Forearm'] @ E(mir(d['wrist' + S], s)))
        place(S + 'Fingers', D[S + 'Hand'] @ rot(FING_AX[S], d['fing' + S]))
        A = P['Pelvis'] @ LOC0[S + 'Thigh'].translation
        f = d['foot' + S]
        pole = rot((0, 0, 1), f['yaw']) @ LIMBS[S + 'Thigh']['p0'] if f.get('pole') is None else Vector(f['pole'])
        Q1, Q2, err = ik(S + 'Thigh', A, f['ankle'], pole)
        info['legErr'][S] = err
        place(S + 'Thigh', Q1)
        place(S + 'Shin', Q2)
        place(S + 'KneeHelper', slerp3(Q1, Q2, .5))
        place(S + 'Foot', f['R'])
        place(S + 'Toes', f['toe'])
    return P, D, info


def to_basis(P):
    return {n: (LOC0I[n] @ P[PAR[n]].inverted() @ P[n]) if PAR[n] else (REST[n].inverted() @ P[n]) for n in BN}


def fk(B):
    P = {}
    for n in BN:
        P[n] = (P[PAR[n]] @ LOC0[n] @ B[n]) if PAR[n] else (REST[n] @ B[n])
    return P


def bdiff(B1, B2):
    return max(max(abs(B1[n][i][j] - B2[n][i][j]) for i in range(4) for j in range(4)) for n in BN)


IDB = {n: I4.copy() for n in BN}


def blend_desc(d1, d2, w, lift=None, arc=None):
    _, _, i1 = solve(d1)
    _, _, i2 = solve(d2)
    d = {}
    for k, a in d1.items():
        b = d2[k]
        if k.startswith('arm'):
            S = k[3:]
            d[k] = {'mode': 'abs', 'w': i1['wrist'][S].lerp(i2['wrist'][S], w), 'pole': i1['pole'][S].lerp(i2['pole'][S], w)}
            if arc and S in arc:
                d[k]['w'] = d[k]['w'] + arc[S] * math.sin(math.pi * w)
        elif k.startswith('foot'):
            d[k] = {'ankle': a['ankle'].lerp(b['ankle'], w), 'R': slerp3(a['R'], b['R'], w), 'toe': slerp3(a['toe'], b['toe'], w),
                    'yaw': a['yaw'] * (1 - w) + b['yaw'] * w}
            if lift and k[4:] in lift:
                d[k]['ankle'] = d[k]['ankle'] + Vector((0, 0, lift[k[4:]] * math.sin(math.pi * w)))
        elif k == 'tail':
            d[k] = [tuple(x * (1 - w) + y * w for x, y in zip(p, q)) for p, q in zip(a, b)]
        elif isinstance(a, Vector):
            d[k] = a.lerp(b, w)
        elif isinstance(a, (int, float)):
            d[k] = a * (1 - w) + b * w
        else:
            d[k] = tuple(x * (1 - w) + y * w for x, y in zip(a, b))
    return d


def step(S, t, t0, t1, a, b, lift, pitch_peak=10., end_pitch=0., start_pitch=0.):
    """A foot step from ball a to ball b between t0 and t1; planted outside."""
    u = sm(t0, t1, t)
    raw = max(0., min(1., (t - t0) / (t1 - t0)))
    ball = Vector(a).lerp(Vector(b), u) + Vector((0, 0, lift * math.sin(math.pi * raw)))
    pitch = start_pitch * (1 - u) + end_pitch * u + pitch_peak * math.sin(math.pi * raw)
    return foot_ball(S, ball, pitch)


# ------------------------------------------------------------------ locomotion (Walk = chase run, ChargeRun)
def run_foot(S, s, phi, C):
    D = C['D']
    zb = BALL[S].z
    xb = s * C['xb']
    if phi < D:
        return foot_ball(S, Vector((xb, C['td'] + C['V'] * C['T'] * phi, zb)), C['toff'] * sm(.40, 1.0, phi / D))
    u = (phi - D) / (1 - D)
    to = foot_ball(S, Vector((xb, C['td'] + C['V'] * C['T'] * D, zb)), C['toff'])['ankle']
    td = foot_ball(S, Vector((xb, C['td'], zb)), 0.)['ankle']
    ks = [(0, to.y, to.z), (.10, to.y + .30, to.z + .72)] + list(C['swing']) + [(.80, td.y - .42, 1.10), (.92, td.y - .22, .80), (1, td.y, td.z)]
    f = pchip([k[0] for k in ks], [(k[1], k[2]) for k in ks])
    y, z = f(u)
    x = to.x * (1 - u) + td.x * u + s * .06 * math.sin(math.pi * u)
    pitch = float(pchip([0, .25, .55, .82, 1], [C['toff'], C['toff'] + 8, 25, -8, 0])(u)[0])
    joint = float(pchip([0, .25, .6, .93, 1], [C['toff'], 34, 12, 12, 0])(u)[0])     # toes stay up while the foot is low
    return foot_ankle(S, (x, y, z), pitch, 0., joint)


def run_desc(t, C):
    T, D = C['T'], C['D']
    d = rest_desc()
    ph = (t / T) % 1.0
    ph2 = (2 * t / T) % 1.0
    comp = math.cos(math.tau * (ph2 - D / 2))
    yaw = C['yaw'] * math.cos(math.tau * ph)
    roll = C['roll'] * math.cos(math.tau * (ph - D / 2))
    d['pel'] = Vector((-C['sway'] * math.cos(math.tau * (ph - D / 2)), C['py'], C['pz'] - C['bob'] * comp))
    d['pelR'] = (C['lean'][0] + C['pitchBob'] * comp, roll, yaw)
    d['spine'] = (C['lean'][1], -.5 * roll, -.7 * yaw)
    d['chest'] = (C['lean'][2] - .5 * C['pitchBob'] * comp, -.3 * roll, -.8 * yaw)
    tot = d['pelR'][0] + d['spine'][0] + d['chest'][0]
    d['neck'] = (C['neck'], -.1 * roll, .25 * yaw)
    d['head'] = (-(tot + C['neck']), -.1 * roll, .25 * yaw)     # eyes level, locked forward
    for S, s in SIDES:
        phi = (ph + (0. if S == 'Right' else .5)) % 1.0           # Right touches down at t = 0
        d['foot' + S] = run_foot(S, s, phi, C)
        th = math.tau * ph + (0 if S == 'Left' else math.pi)     # opposite arm swings forward
        fw = Vector(C['armF'])
        bk = Vector(C['armB'])
        off = (fw + bk) / 2 + (fw - bk) / 2 * math.cos(th) + Vector((0, 0, C['armLift'])) * math.sin(th)
        d['arm' + S] = {'mode': 'chest', 'off': mv(off, s)}
        d['sh' + S] = (C['shE'], C['shP'] * math.cos(th))
        d['fing' + S] = C['fing']
        d['wrist' + S] = C['wrist']
    tb = lambda k: math.cos(math.tau * (ph2 - D / 2) - k)
    ty = lambda k: -C['tailY'] * math.cos(math.tau * ph - k)    # counterbalance the pelvis yaw, later down the chain
    d['tail'] = [(C['tailP'][0] + C['tailB'] * tb(.9), 0, .7 * ty(.7)), (C['tailP'][1] + .7 * C['tailB'] * tb(1.5), 0, ty(1.3)),
                 (C['tailP'][2] + .5 * C['tailB'] * tb(2.1), 0, 1.2 * ty(1.9))]
    d['mane'] = (C['maneB'] * tb(1.2), 0, .4 * C['yaw'] * math.cos(math.tau * ph - 1.0))
    d['jaw'] = C['jaw'] + 2 * math.cos(math.tau * ph2)
    return d


WALK = dict(T=18 / FPS, V=22.0, D=.25, xb=1.05, td=-2.35, toff=55, py=-.10, pz=-.55, bob=.12, sway=.05, yaw=8, roll=4,
            lean=(8, 4, 4), pitchBob=2, neck=-6, swing=[(.30, 1.20, 1.62), (.56, -.55, 1.42)],
            armF=(.05, -1.45, 1.15), armB=(.36, 1.05, .60), armLift=-.15, shE=2, shP=7, fing=26, wrist=(-8, 0, 0),
            tailP=(25, 10, 5), tailB=5, tailY=10, maneB=3, jaw=6)
CHARGE = dict(T=12 / FPS, V=32.0, D=.24, xb=1.05, td=-2.55, toff=60, py=-.50, pz=-.95, bob=.14, sway=.04, yaw=6, roll=3,
              lean=(18, 10, 10), pitchBob=3, neck=-14, swing=[(.28, .95, 1.62), (.56, -.78, 1.20)],
              armF=(-.15, -1.70, 1.20), armB=(.20, 1.35, 1.00), armLift=-.15, shE=4, shP=10, fing=8, wrist=(-12, 0, 0),
              tailP=(45, 12, 6), tailB=6, tailY=12, maneB=5, jaw=12)


# ------------------------------------------------------------------ Idle (3.0 s, Idle start pose = rest)
def idle_desc(t):
    d = rest_desc()
    w1 = math.tau * t / 3.0
    br = math.sin(2 * w1)                 # two heavy breaths per loop
    inh = (1 - math.cos(2 * w1)) / 2      # 0 at t=0
    ws = math.sin(w1)                     # weight shift
    d['pel'] = Vector((.06 * ws, 0, -.03 * inh))
    d['pelR'] = (0, -1.4 * ws, .8 * ws)
    d['spine'] = (-.8 * br, .8 * ws, -.5 * ws)
    d['chest'] = (-1.8 * br, .5 * ws, -.4 * ws)      # chest heaves (arches on the inhale)
    d['neck'] = (.7 * br, -.6 * ws, 0)
    d['head'] = (.9 * br, -.3 * ws, 5 * math.sin(w1))
    d['jaw'] = 3 * inh
    lag = lambda k, a, f=1: a * (math.sin(f * w1 - k) + math.sin(k))
    d['mane'] = (lag(.9, 2.2, 2), lag(.8, 1.2), 0)                 # drifts after the chest
    d['tail'] = [(lag(1.0, 1.5, 2), 0, lag(1.0, 6)), (0, 0, lag(1.6, 8)), (0, 0, lag(2.2, 10))]
    for S, s in SIDES:
        d['sh' + S] = (2.0 * inh, 0)
        d['arm' + S] = {'mode': 'chest', 'off': Vector((0, .04 * br, .06 * inh))}
    d['fingLeft'] = 14 * inh                                          # claws flex
    d['fingRight'] = 12 * (1 - math.cos(math.tau * t)) / 2
    return d


# ------------------------------------------------------------------ Hit (0.4583 s)
def hit_desc(t):
    d = rest_desc()
    END = 11 / FPS

    def env(t, lag=0.):
        x = t - lag
        if x <= 0:
            return 0.
        if x < .083:
            return 1 - (1 - x / .083) ** 2
        return 1 - sm(lag + .083, END, t)
    h = env(t)
    hl = env(t, .05)
    d['pel'] = Vector((0, .18 * h, -.10 * h))
    d['pelR'] = (-4 * h, 0, 3 * h)
    d['spine'] = (-5 * h, 0, 2 * h)
    d['chest'] = (-9 * h, 2 * h, 4 * h)
    d['neck'] = (-6 * h, 0, 0)
    d['head'] = (-10 * h, -4 * h, 8 * h)
    d['jaw'] = 16 * h
    d['armLeft'] = {'mode': 'chest', 'off': Vector((.25, .45, .55)) * h}
    d['armRight'] = {'mode': 'chest', 'off': Vector((-.15, .35, .40)) * h}
    for S, s in SIDES:
        d['sh' + S] = (8 * h, -4 * h)
        d['fing' + S] = 30 * h
    d['mane'] = (-7 * hl, 0, 3 * hl)
    d['tail'] = [(-6 * hl, 0, 12 * hl), (-4 * hl, 0, 10 * hl), (0, 0, 8 * env(t, .09))]
    return d


# ------------------------------------------------------------------ Howl (2.2083 s, peak 1.0 s held to 1.79 s)
HOWL_END = 53 / FPS
HT = [0, .35, .55, 1.0, 1.79, HOWL_END]
HW = {'pel': ch(HT, [Vector((0, 0, 0)), Vector((0, .10, -.42)), Vector((0, .05, -.25)), Vector((0, .06, -.04)), Vector((0, .06, -.04)), Vector((0, 0, 0))]),
      'pelR': ch(HT, [0, 10, 2, -7, -7, 0]), 'spine': ch(HT, [0, 12, 2, -11, -11, 0]), 'chest': ch(HT, [0, 10, 0, -18, -19, 0]),
      'neck': ch(HT, [0, 8, -3, -9, -9, 0]), 'head': ch(HT, [0, 12, -6, -22, -23, 0]), 'jaw': ch(HT, [0, 0, 6, 38, 38, 0]),
      'sh': ch(HT, [(0, 0), (-2, 8), (6, 0), (10, -14), (10, -14), (0, 0)]),
      'arm': ch(HT, [Vector((0, 0, 0)), Vector((-.05, -.55, .45)), Vector((.40, -.20, .60)), Vector((2.0, -.20, 1.45)), Vector((2.0, -.20, 1.55)), Vector((0, 0, 0))]),
      'pw': ch(HT, [0, .3, .7, 1, 1, 0]), 'fing': ch(HT, [0, 40, 25, 0, 0, 0]), 'wrist': ch(HT, [0, 10, 0, -15, -15, 0]),
      't1': ch(HT, [0, -12, 0, 28, 30, 0]), 't2': ch(HT, [0, -6, 0, 14, 15, 0]), 't3': ch(HT, [0, -4, 0, 8, 8, 0]),
      'mane': ch([0, .45, .65, 1.1, 1.85, HOWL_END], [0, 6, 0, 9, 9, 0])}


def howl_desc(t):
    d = rest_desc()
    tr = math.sin(math.tau * 9 * t) * sm(1.0, 1.1, t) * (1 - sm(1.70, 1.79, t))     # held howl tremor
    d['pel'] = HW['pel'](t)
    d['pelR'] = (HW['pelR'](t), 0, 0)
    d['spine'] = (HW['spine'](t), 0, 0)
    d['chest'] = (HW['chest'](t) + .8 * tr, 0, 0)
    d['neck'] = (HW['neck'](t), 0, 0)
    d['head'] = (HW['head'](t) + 1.2 * tr, 0, 0)
    d['jaw'] = HW['jaw'](t) + 3 * tr
    for S, s in SIDES:
        d['sh' + S] = HW['sh'](t)
        d['arm' + S] = {'mode': 'chest', 'off': mv(HW['arm'](t), s), 'pole': mv((.25, .45, -.85), s), 'pw': HW['pw'](t)}
        d['fing' + S] = HW['fing'](t)
        d['wrist' + S] = (HW['wrist'](t), 0, 0)
    d['tail'] = [(HW['t1'](t), 0, 0), (HW['t2'](t), 0, 0), (HW['t3'](t), 0, 0)]
    d['mane'] = (HW['mane'](t), 0, 0)
    return d


# ------------------------------------------------------------------ ClawRake (1.0833 s, impact 0.5 s)
RAKE_END = 26 / FPS
KT = [0, .08, .27, .35, .43, .50, .58, .66, .76, .95, RAKE_END]
A0 = {S: WRIST0[S] - HEAD[S + 'UpperArm'] for S, s in SIDES}
P0L = LIMBS['LeftUpperArm']['p0']
U = lambda *v: Vector(v).normalized()
RK = {'pel': ch(KT, [Vector(v) for v in [(0, 0, 0), (0, .10, -.10), (0, .38, -.28), (0, 0, -.40), (0, -.70, -.52), (0, -1.10, -.60),
                                          (0, -1.18, -.64), (0, -1.16, -.62), (0, -1.02, -.54), (0, -.25, -.12), (0, 0, 0)]]),
      'pelR': ch(KT, [0, 1, -5, 0, 8, 13, 15, 15, 12, 3, 0]), 'spine': ch(KT, [0, 0, -8, -3, 5, 9, 11, 11, 8, 2, 0]),
      'chest': ch(KT, [0, -2, -12, -6, 6, 11, 12, 12, 8, 2, 0]), 'neck': ch(KT, [0, 0, 4, 2, -6, -10, -11, -11, -8, -2, 0]),
      'head': ch(KT, [0, 2, 10, 6, -6, -12, -14, -14, -10, -2, 0]), 'jaw': ch(KT, [0, 6, 22, 24, 28, 30, 26, 20, 14, 4, 0]),
      'sh': ch(KT, [(0, 0), (6, -2), (12, -10), (10, 0), (8, 10), (4, 14), (2, 12), (0, 10), (0, 4), (0, 1), (0, 0)]),
      'dir': ch(KT, [A0['Left'].normalized(), U(.75, .12, -.65), U(.88, .30, .30), U(.72, -.45, .28), U(.25, -.90, .12),
                     U(-.10, -.80, -.59), U(-.04, -.25, -.97), U(.20, .30, -.93), U(.30, .60, -.74), U(.24, .08, -.97),
                     A0['Left'].normalized()]),
      'dist': ch(KT, [A0['Left'].length, 3.05, 2.55, 2.80, 3.10, 3.30, 3.30, 3.25, 3.05, 3.30, A0['Left'].length]),
      'pole': ch(KT, [P0L, U(.6, .5, -.6), U(.40, .45, -.80), U(.35, .75, -.55), U(.25, .80, -.55), U(.15, .75, -.65),
                      U(.15, .80, -.6), U(.2, .8, -.55), U(.2, .85, -.5), U(.3, .6, -.6), P0L]),
      'pw': ch(KT, [0, .5, 1, 1, 1, 1, 1, 1, 1, .5, 0]), 'wrist': ch(KT, [0, 0, 10, 8, 4, 0, -4, -8, -6, 0, 0]),
      'fing': ch(KT, [0, 0, 0, 0, 8, 22, 30, 35, 30, 8, 0]), 't1': ch(KT, [0, 4, 20, 20, 24, 30, 34, 35, 30, 8, 0]),
      'ty': ch(KT, [0, 0, 0, 4, 8, 12, 4, -8, -10, -2, 0]), 'mane': ch(KT, [0, 0, -4, -6, -2, 2, 8, 8, 6, 2, 0]),
      'heelL': ch([0, .40, .50, .70, .90, RAKE_END], [0, 0, 22, 22, 0, 0])}


def rake_desc(t):
    d = rest_desc()
    d['pel'] = RK['pel'](t)
    d['pelR'] = (RK['pelR'](t), 0, 0)
    d['spine'] = (RK['spine'](t), 0, 0)
    d['chest'] = (RK['chest'](t), 0, 0)
    d['neck'] = (RK['neck'](t), 0, 0)
    d['head'] = (RK['head'](t), 0, 0)
    d['jaw'] = RK['jaw'](t)
    for S, s in SIDES:
        dr = RK['dir'](t)
        d['sh' + S] = RK['sh'](t)
        d['arm' + S] = {'mode': 'dir', 'dir': mv(dr, s), 'dist': RK['dist'](t), 'pole': mv(RK['pole'](t), s), 'pw': RK['pw'](t)}
        d['wrist' + S] = (RK['wrist'](t), 0, 0)
        d['fing' + S] = RK['fing'](t)
    d['footLeft'] = foot_ball('Left', BALL['Left'], RK['heelL'](t))
    fwd = BALL['Right'] + Vector((0, -1.55, 0))
    d['footRight'] = (step('Right', t, .30, .46, BALL['Right'], fwd, .32, 12) if t < .62 else
                      step('Right', t, .78, .98, fwd, BALL['Right'], .25, 8))
    t1 = RK['t1'](t)
    ty = RK['ty'](t)
    fade = 1 - sm(.95, RAKE_END, t)
    d['tail'] = [(t1, 0, ty), (.5 * t1, 0, .8 * RK['ty'](t - .05) * fade), (.3 * t1, 0, .6 * RK['ty'](t - .1) * fade)]
    d['mane'] = (RK['mane'](t), 0, 0)
    return d


# ------------------------------------------------------------------ ChargeStart (0.7083 s -> ChargeRun frame 0)
CS_END = 17 / FPS
CT = [0, .18, .33, .50]
CK = {'pel': ch(CT, [Vector((0, 0, 0)), Vector((0, -.40, -.55)), Vector((0, -.62, -.92)), Vector((0, -.66, -.98))]),
      'pelR': ch(CT, [(0, 0, 0), (14, 0, -4), (24, 0, -6), (26, 0, -6)]), 'spine': ch(CT, [(0, 0, 0), (8, 0, 2), (14, 0, 3), (15, 0, 3)]),
      'chest': ch(CT, [(0, 0, 0), (6, 0, 2), (10, 0, 3), (11, 0, 3)]), 'neck': ch(CT, [0, -8, -16, -18]), 'jaw': ch(CT, [0, 8, 14, 18]),
      'shR': ch(CT, [(0, 0), (-2, 6), (-4, 12), (-4, 13)]), 'shL': ch(CT, [(0, 0), (3, -4), (6, -8), (6, -8)]),
      'armL': ch(CT, [Vector((0, 0, 0)), Vector((.10, .60, .40)), Vector((.25, 1.30, .90)), Vector((.25, 1.35, .95))]),
      'kR': ch([0, .18, .36, .50], [0, .45, 1, 1]), 'wR': ch([.18, .33, .50], [Vector((-2.35, -2.70, 2.20)), Vector((-2.25, -3.05, 1.45)), Vector((-2.25, -2.85, 1.45))]),
      'fR': ch(CT, [0, 10, 6, 6]), 'fL': ch(CT, [0, 20, 30, 30]),
      't1': ch([0, .18, .33, .42, .50], [(0, 0, 0), (8, 0, 6), (18, 0, 12), (18, 0, -12), (20, 0, 8)]),
      'mane': ch([0, .24, .40, .50], [0, -4, 8, 6])}
RUN0 = None
CLAW_OFF = {}


def claw_tip(P, S):
    return P[S + 'Fingers'] @ CLAW_OFF[S]


def crouch_desc(t):
    d = rest_desc()
    d['pel'] = CK['pel'](t)
    d['pelR'] = CK['pelR'](t)
    d['spine'] = CK['spine'](t)
    d['chest'] = CK['chest'](t)
    n = CK['neck'](t)
    d['neck'] = (n, 0, 0)
    d['head'] = (-(d['pelR'][0] + d['spine'][0] + d['chest'][0] + n), 0, -(d['pelR'][2] + d['spine'][2] + d['chest'][2]))  # eyes locked forward
    d['jaw'] = CK['jaw'](t)
    d['shRight'] = CK['shR'](t)
    d['shLeft'] = CK['shL'](t)
    d['armLeft'] = {'mode': 'chest', 'off': CK['armL'](t)}
    d['fingRight'] = CK['fR'](t)
    d['fingLeft'] = CK['fL'](t)
    run_r = RUN0['footRight']
    d['footRight'] = step('Right', t, .03, .18, BALL['Right'], run_r['ankle'] + (BALL['Right'] - ANK['Right']), .30, 10)
    if t >= .18:
        d['footRight'] = run_r                    # planted exactly where ChargeRun frame 0 has it
    d['footLeft'] = step('Left', t, .18, .33, BALL['Left'], Vector((1.10, .85, BALL['Left'].z)), .30, 0, 38)
    t1 = CK['t1'](t)
    d['tail'] = [t1, (t1[0] * .8, 0, t1[2] * .8), (t1[0] * .6, 0, t1[2] * .6)]
    d['mane'] = (CK['mane'](t), 0, 0)
    # Right hand: rest -> a light brush of the ground in front of the lead foot.
    k = CK['kR'](t)
    w = CK['wR'](max(t, .18))
    d['armRight'] = {'mode': 'mix', 'off': Vector(), 'w': w, 'k': k, 'pole': Vector((-.5, .6, -.6)), 'pw': k}
    cw = sm(.24, .33, t)
    if cw > 0:
        for _ in range(4):        # lowest claw of the real skinned hand 0.04 above the ground
            P, _, _ = solve(d)
            set_pose(to_basis(P))
            hv = eval_section('Hands')
            low = float(hv[hv[:, 0] < 0][:, 2].min())
            w = w - Vector((0, 0, cw * (low - .04)))
            d['armRight']['w'] = w
    return d


def charge_start_desc(t):
    if t <= .50:
        return crouch_desc(t)
    return blend_desc(crouch_desc(.50), RUN0, sm(.50, CS_END, t), lift={'Left': .45}, arc={'Right': Vector((-.75, 0, .65))})


# ------------------------------------------------------------------ Death (2.2083 s)
DEATH_END = 53 / FPS
DT = [0, .12, .40, .75, 1.05, 1.35, 1.55, 1.85, DEATH_END]
DK = {'pel': ch(DT, [Vector(v) for v in [(0, 0, 0), (0, .25, -.08), (-.05, .45, -.25), (.30, .40, -.85), (1.30, .45, -1.55),
                                          (2.20, .50, -2.35), (2.25, .50, -2.25), (2.25, .50, -2.35), (2.25, .50, -2.35)]]),
      'pelR': ch(DT, [(0, 0, 0), (-6, 0, 4), (-2, -3, 8), (14, 10, 10), (14, 40, 12), (10, 82, 14), (10, 78, 14), (10, 80, 14), (10, 80, 14)]),
      'spine': ch(DT, [(0, 0, 0), (-6, 0, 2), (4, -2, 4), (14, 4, 4), (10, 8, 0), (4, 6, -4), (6, 4, -4), (6, 4, -4), (6, 4, -4)]),
      'chest': ch(DT, [(0, 0, 0), (-10, 2, 4), (4, 0, 2), (16, 4, 2), (8, 6, 0), (0, 4, -6), (2, 2, -6), (2, 2, -6), (2, 2, -6)]),
      'neck': ch(DT, [(0, 0, 0), (-8, 0, 0), (6, 0, 0), (10, 6, 0), (-4, 10, 0), (-6, 18, 0), (-2, 14, 0), (-2, 16, 0), (-2, 16, 0)]),
      'head': ch(DT, [(0, 0, 0), (-14, -4, 10), (8, 4, -6), (14, 4, -4), (0, 8, 0), (-8, 10, 4), (-4, 8, 4), (-4, 8, 4), (-4, 8, 4)]),
      'jaw': ch(DT, [0, 18, 8, 14, 16, 22, 18, 20, 20]),
      'armL': ch(DT, [Vector(v) for v in [(0, 0, 0), (.5, .3, 1.2), (.3, -.3, .4), (.4, -.6, .6), (.4, -1.4, 1.0), (.2, -1.6, .8),
                                           (.2, -1.5, .6), (.2, -1.5, .6), (.2, -1.5, .6)]]),
      'armR': ch(DT, [Vector(v) for v in [(0, 0, 0), (-.6, .4, 1.0), (-.4, -.2, .5), (-.4, -.4, .4), (-.3, -.2, .7), (.9, -1.0, .6),
                                           (1.4, -1.3, .45), (1.6, -1.4, .4), (1.6, -1.4, .4)]]),
      'fing': ch(DT, [0, 0, 30, 25, 10, 15, 20, 20, 20]), 'sh': ch(DT, [(0, 0), (12, -4), (4, 0), (0, 4), (0, 2), (0, 0), (0, 0), (0, 0), (0, 0)]),
      'tail': ch(DT, [(0, 0, 0), (-10, 0, 10), (-14, 0, 0), (-20, 0, -10), (-6, 0, 10), (5, 0, 25), (-5, 0, 30), (0, 0, 30), (0, 0, 30)]),
      'mane': ch([0, .20, .48, .83, 1.13, 1.43, 1.63, 1.93, DEATH_END], [(0, 0, 0), (-8, 0, 3), (4, 0, 0), (8, 3, 0), (4, 6, 0), (-6, 8, 0), (2, 6, 0), (0, 6, 0), (0, 6, 0)])}
DEATH_FOOT = {}


def death_desc(t):
    d = rest_desc()
    d['pel'] = DK['pel'](t)
    d['pelR'] = DK['pelR'](t)
    for k in ('spine', 'chest', 'neck', 'head'):
        d[k] = DK[k](t)
    d['jaw'] = DK['jaw'](t)
    d['armLeft'] = {'mode': 'chest', 'off': DK['armL'](t)}
    d['armRight'] = {'mode': 'chest', 'off': DK['armR'](t)}
    for S, s in SIDES:
        d['fing' + S] = DK['fing'](t)
        d['sh' + S] = DK['sh'](t)
    tl = DK['tail'](t)
    d['tail'] = [tl, (tl[0] * .7, 0, tl[2] * .8), (tl[0] * .5, 0, tl[2] * .6)]
    d['mane'] = DK['mane'](t)
    # Feet: stagger step back with the right, then both release into a relaxed fold that rides the pelvis.
    planted = {'Left': foot_ball('Left', BALL['Left']), 'Right': step('Right', t, .12, .38, BALL['Right'], BALL['Right'] + Vector((-.15, .95, 0)), .30, 8)}
    for S, s in SIDES:
        planted[S]['pole'] = E(d['pelR']) @ LIMBS[S + 'Thigh']['p0']
    Tp = Matrix.Translation(HEAD['Pelvis'] + d['pel']) @ E(d['pelR']).to_4x4() @ Matrix.Translation(-HEAD['Pelvis'])
    relax = {'Left': ANK['Left'] + Vector((.10, -.20, .55)), 'Right': ANK['Right'] + Vector((-.20, -.70, .95))}
    for S, s in SIDES:
        w = sm(.85, 1.60, t) if S == 'Left' else sm(.75, 1.45, t)
        DEATH_FOOT.setdefault(S, {})[round(t * FPS)] = w
        if w <= 0:
            d['foot' + S] = planted[S]
        else:
            Rr = E(d['pelR']) @ rot(LAT[S], -20)
            p = planted[S]
            pr = d['pelR']
            d['foot' + S] = {'ankle': p['ankle'].lerp(Tp @ relax[S], w) + Vector((0, 0, .75 * math.sin(math.pi * w))),
                             'R': slerp3(p['R'], Rr, w * w), 'toe': slerp3(p['toe'], Rr, w * w), 'yaw': 0,
                             'pole': E(pr) @ LIMBS[S + 'Thigh']['p0']}
    return d


# ------------------------------------------------------------------ mesh evaluation
def set_pose(B):
    for pb in rig.pose.bones:
        pb.matrix_basis = B[pb.name]
    bpy.context.view_layer.update()


def eval_verts():
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for sec, o in SECS.items():
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        a = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', a)
        ev.to_mesh_clear()
        out[sec] = a.reshape(-1, 3)
    return out


def eval_section(sec):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = SECS[sec].evaluated_get(dg)
    me = ev.to_mesh()
    a = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', a)
    ev.to_mesh_clear()
    return a.reshape(-1, 3)


def zmin(V):
    return min(float(v[:, 2].min()) for v in V.values())


# Claw tips (lowest rest vertex of each hand's claws) in Fingers space.
set_pose(IDB)
RESTV = eval_verts()
hv = RESTV['Hands']
for S, s in SIDES:
    side = hv[hv[:, 0] * s > 0]
    tip = Vector(side[np.argmin(side[:, 2])])
    CLAW_OFF[S] = REST[S + 'Fingers'].inverted() @ tip
REST_ZMIN = zmin(RESTV)
log('rest zmin', REST_ZMIN, 'claw offsets', {k: [round(x, 3) for x in v] for k, v in CLAW_OFF.items()})


# ------------------------------------------------------------------ sampling
class Clip:
    def __init__(self, name, frames, loop):
        self.name = name
        self.frames = frames
        self.loop = loop
        self.bases = []
        self.meta = {}


CLIPS = {}


def sample(name, frames, fn, loop=False, ground=None):
    c = Clip(name, frames, loop)
    errs = {'arm': 0., 'leg': {'Left': [], 'Right': []}}
    for f in range(frames + 1):
        t = f / FPS
        d = fn(t)
        P, D, info = solve(d)
        if ground:
            for _ in range(8):
                set_pose(to_basis(P))
                zm = zmin(eval_verts())
                dz = ground(t, zm)
                if abs(dz) < 1e-5:
                    break
                d['pel'] = d['pel'] + Vector((0, 0, dz))
                P, D, info = solve(d)
        errs['arm'] = max(errs['arm'], info['armErr'])
        for S, s in SIDES:
            errs['leg'][S].append(info['legErr'][S])
        c.bases.append(to_basis(P))
    c.meta['ikClamp'] = {'armMax': round(errs['arm'], 5), 'legMaxPerFrame': {S: [round(x, 5) for x in v] for S, v in errs['leg'].items()}}
    CLIPS[name] = c
    log('sampled', name, frames + 1, 'frames')
    return c


def death_ground(t, zm):
    # Never below the ground; from ~1.2 s on, rest the body on the ground (no floating).
    g = sm(1.15, 1.35, t)
    if zm < -0.0:
        return -zm if t > .6 else max(0., -zm - .02)
    return -g * zm


RUN0 = run_desc(0.0, CHARGE)
sample('Idle', 72, idle_desc, loop=True)
sample('Walk', 18, lambda t: run_desc(t, WALK), loop=True)
sample('Hit', 11, hit_desc)
sample('Death', 53, death_desc, ground=death_ground)


def smooth_released_legs(c, passes=6):
    for S, s in SIDES:
        fr = [f for f in range(c.frames + 1) if DEATH_FOOT[S].get(f, 0) > 0]
        if len(fr) < 3:
            continue
        lo, hi = fr[0] + 1, min(c.frames - 1, fr[-1])
        for b in (S + 'Thigh', S + 'Shin', S + 'KneeHelper', S + 'Foot', S + 'Toes'):
            for _ in range(passes):
                q = [c.bases[f][b].to_quaternion() for f in range(c.frames + 1)]
                for f in range(lo, hi + 1):
                    a = q[f - 1].slerp(q[f + 1], .5)
                    m = q[f].slerp(a, .5).to_matrix().to_4x4()
                    m.translation = c.bases[f][b].translation
                    c.bases[f][b] = m


smooth_released_legs(CLIPS['Death'])
for f in range(1, CLIPS['Death'].frames + 1):        # nothing below the ground after the smoothing
    B = CLIPS['Death'].bases[f]
    for _ in range(3):
        set_pose(B)
        zm = zmin(eval_verts())
        if zm >= -.004:
            break
        lift = R3['Pelvis'].transposed() @ Vector((0, 0, -zm))
        B['Pelvis'] = Matrix.Translation(lift) @ B['Pelvis']
sample('Howl', 53, howl_desc)
sample('ChargeRun', 12, lambda t: run_desc(t, CHARGE), loop=True)
sample('ChargeStart', 17, charge_start_desc)
sample('ClawRake', 26, rake_desc)

# Snap loops / start-end poses; record the pre-snap error.
SNAP = {}
for name, c in CLIPS.items():
    if c.loop:
        SNAP[name] = {'loopErrorBeforeSnap': round(bdiff(c.bases[0], c.bases[-1]), 6),
                      'startVsIdleStart': round(bdiff(c.bases[0], IDB), 6)}
        if name == 'Idle':          # the Idle start pose IS the rest pose
            c.bases[0] = {n: I4.copy() for n in BN}
        c.bases[-1] = {n: m.copy() for n, m in c.bases[0].items()}
    else:
        SNAP[name] = {'startErrorBeforeSnap': round(bdiff(c.bases[0], IDB), 6)}
        c.bases[0] = {n: I4.copy() for n in BN}
        if name == 'ChargeStart':
            SNAP[name]['endVsChargeRunFrame0BeforeSnap'] = round(bdiff(c.bases[-1], CLIPS['ChargeRun'].bases[0]), 6)
            c.bases[-1] = {n: m.copy() for n, m in CLIPS['ChargeRun'].bases[0].items()}
        elif name != 'Death':
            SNAP[name]['endErrorBeforeSnap'] = round(bdiff(c.bases[-1], IDB), 6)
            c.bases[-1] = {n: I4.copy() for n in BN}
log('snap', json.dumps(SNAP))

# ------------------------------------------------------------------ checks
W = {}
for sec in ('Body', 'Hands', 'Head'):
    o = SECS[sec]
    names = {g.index: g.name for g in o.vertex_groups}
    W[sec] = [names[max(v.groups, key=lambda g: g.weight).group] for v in o.data.vertices]
body = SECS['Body'].data
body.calc_loop_triangles()
TRIS = np.array([lt.vertices[:] for lt in body.loop_triangles], dtype=int)
TORSO_SET = {'Pelvis', 'Spine', 'Chest', 'Neck', 'Head', 'Mane'}
dom = np.array(W['Body'])
is_torso = np.isin(dom, list(TORSO_SET))
torso_tris = TRIS[is_torso[TRIS].all(1)]
leg_mask = np.array([n.endswith(('Thigh', 'Shin')) for n in dom])
leg_tris = TRIS[leg_mask[TRIS].all(1)]
fore_idx = {S: np.where(dom == S + 'Forearm')[0] for S, s in SIDES}
mane_idx = np.where(dom == 'Mane')[0]
hands_idx = {S: np.where(RESTV['Hands'][:, 0] * s > 0)[0] for S, s in SIDES}
snout_idx = np.where(RESTV['Head'][:, 1] < -1.9)[0]
headm = SECS['Head'].data
headm.calc_loop_triangles()
HEAD_TRIS = np.array([lt.vertices[:] for lt in headm.loop_triangles], dtype=int)


# Collision cores in REST space (studs), each carried by its bone; a little inside the
# real surface so only true pass-through counts. Points are moved back into each
# core's rest space with (P[bone] @ REST[bone]^-1)^-1, then tested.
KF = json.loads((OUT / 'manifest.json').read_text())['scaleFromBaseUnits'] / 1.3
TORSO_CORES = [('Pelvis', Vector((0, .05, 3.85)) * KF, Vector((1.10, .74, .62)) * KF), ('Spine', Vector((0, .02, 4.75)) * KF, Vector((1.08, .78, .55)) * KF),
               ('Chest', Vector((0, -.08, 5.85)) * KF, Vector((1.40, .92, .80)) * KF)]
HEAD_CORE = ('Head', Vector((0, -.692, 6.201)) * KF * 1.3, Vector((.66, .60, .52)) * KF)
LEG_CAPS = [(S + b, HEAD[S + b], HEAD[S + c], r * KF) for S, s in SIDES for b, c, r in (('Thigh', 'Shin', .52), ('Shin', 'Foot', .42))]


def to_rest(P, bone, pts):
    M = np.array((P[bone] @ REST[bone].inverted()).inverted())
    return pts @ M[:3, :3].T + M[:3, 3]


def ell_depth(P, core, pts):
    bone, c, a = core
    q = (to_rest(P, bone, pts) - np.array(c)) / np.array(a)
    r = np.sqrt((q ** 2).sum(1))
    return np.clip(1 - r, 0, None) * min(a)


def cap_depth(P, cap, pts):
    bone, A, B, r = cap
    q = to_rest(P, bone, pts)
    A = np.array(A)
    v = np.array(B) - A
    t = np.clip(((q - A) @ v) / (v @ v), 0, 1)
    d = np.linalg.norm(q - (A + t[:, None] * v), axis=1)
    return np.clip(r - d, 0, None)


def pen_sets(V, P):
    arms = np.concatenate([V['Hands']] + [V['Body'][fore_idx[S]] for S, s in SIDES])
    r = {'armsThroughTorso': max(float(ell_depth(P, c, arms).max()) for c in TORSO_CORES),
         'handsThroughLegs': max(float(cap_depth(P, c, V['Hands']).max()) for c in LEG_CAPS),
         'snoutThroughTorso': max(float(ell_depth(P, c, V['Head'][snout_idx]).max()) for c in TORSO_CORES),
         'maneThroughHead': float(ell_depth(P, HEAD_CORE, V['Body'][mane_idx]).max())}
    return r


PEN_REST = pen_sets(RESTV, fk(IDB))
JOINTS = {'Neck': ('Neck', 1.0)}
for S, s in SIDES:
    JOINTS.update({S + 'Shoulder': (S + 'UpperArm', .95), S + 'Elbow': (S + 'Forearm', .80), S + 'Hip': (S + 'Thigh', 1.0),
                   S + 'Knee': (S + 'Shin', .80)})
REGION = {}
for j, (b, r) in JOINTS.items():
    c = np.array(HEAD[b])
    inside = np.linalg.norm(RESTV['Body'] - c, axis=1) < r
    REGION[j] = TRIS[inside[TRIS].all(1)]


def cone_volume(V, tris, c):
    a = V[tris[:, 0]] - c
    b = V[tris[:, 1]] - c
    d = V[tris[:, 2]] - c
    return float(np.einsum('ij,ij->i', a, np.cross(b, d)).sum() / 6)


# Cross-section retention: blend-band skin around each child bone's axis (rigid motion
# leaves it at 1; a pinch/collapse lowers it). Robust where the open-patch cone volume
# cancels out (shoulders).
_bw = []
_names = {g.index: g.name for g in SECS['Body'].vertex_groups}
for v in SECS['Body'].data.vertices:
    _bw.append({_names[g.group]: g.weight for g in v.groups})
SECTION = {}
for S, s in SIDES:
    SECTION.update({S + 'Shoulder': (S + 'UpperArm', (S + 'UpperArm', S + 'ShoulderHelper'), 1.1),
                    S + 'Elbow': (S + 'Forearm', (S + 'Forearm', S + 'ElbowHelper'), .8),
                    S + 'Knee': (S + 'Shin', (S + 'Shin', S + 'KneeHelper'), .8), S + 'Hip': (S + 'Thigh', (S + 'Thigh',), 1.0)})
SECTION['Neck'] = ('Neck', ('Neck',), 1.0)
SEC_IDX = {}
SEC_D0 = {}
for j, (child, grp, r) in SECTION.items():
    c = np.array(HEAD[child])
    idx = [i for i, w in enumerate(_bw) if .15 <= sum(w.get(g, 0) for g in grp) <= .95 and np.linalg.norm(RESTV['Body'][i] - c) < r]
    SEC_IDX[j] = np.array(idx, dtype=int)


def axis_dist(V, P, child, idx):
    o = np.array(P[child].translation)
    d = np.array(P[child].to_3x3().col[1].normalized())
    q = V[idx] - o
    return np.linalg.norm(q - np.outer(q @ d, d), axis=1)


for j in SECTION:
    SEC_D0[j] = float((axis_dist(RESTV['Body'], fk(IDB), SECTION[j][0], SEC_IDX[j]) ** 2).mean())
VOL_REST = {j: cone_volume(RESTV['Body'], REGION[j], np.array(HEAD[b])) for j, (b, r) in JOINTS.items()}
HINGES = {}
for S, s in SIDES:
    HINGES[S + 'Knee'] = (S + 'Thigh', S + 'Shin', LIMBS[S + 'Thigh']['h0'], (-5, 150), False)
    HINGES[S + 'Elbow'] = (S + 'UpperArm', S + 'Forearm', LIMBS[S + 'UpperArm']['h0'], (-5, 150), False)
    HINGES[S + 'Fingers'] = (S + 'Hand', S + 'Fingers', FING_AX[S], (-5, 100), True)
    HINGES[S + 'Toes'] = (S + 'Foot', S + 'Toes', -LAT[S], (-20, 75), True)
HINGES['Jaw'] = ('Head', 'Jaw', JAW_AX, (-2, 45), True)


def hinge(P, par, chd, h0):
    hl = R3[par].transposed() @ h0
    R = P[par].to_3x3()
    h = (R @ hl).normalized()
    yp = R.col[1].normalized()
    yc = P[chd].to_3x3().col[1].normalized()
    bend = math.degrees(math.atan2(yp.cross(yc).dot(h), yp.dot(yc)))
    off = math.degrees(math.asin(max(-1, min(1, yc.dot(h)))))
    return bend, off


P_REST = fk(IDB)
HINGE_REST = {k: hinge(P_REST, a, b, h)[0] for k, (a, b, h, rng_, rel) in HINGES.items()}


def twist(M):
    q = M.to_quaternion()
    a = math.degrees(2 * math.atan2(q.y, q.w))
    return (a + 180) % 360 - 180


PLANTED = {
    'Idle': lambda S, t: True, 'Hit': lambda S, t: True, 'Howl': lambda S, t: True,
    'Walk': lambda S, t: ((t / WALK['T']) + (0 if S == 'Right' else .5)) % 1 < WALK['D'] - 1e-9,
    'ChargeRun': lambda S, t: ((t / CHARGE['T']) + (0 if S == 'Right' else .5)) % 1 < CHARGE['D'] - 1e-9,
    'ClawRake': lambda S, t: True if S == 'Left' else (t <= .30 or .46 <= t <= .78 or t >= .98),
    'ChargeStart': lambda S, t: (t <= .03 or .18 <= t) if S == 'Right' else (t <= .18 or .33 <= t <= .50),
    'Death': lambda S, t: DEATH_FOOT[S].get(round(t * FPS), 1) <= 0 and not (S == 'Right' and .12 < t < .38)}
SPEED = {'Walk': WALK['V'], 'ChargeRun': CHARGE['V']}
CHECKS = {'clips': {}}
WORST = {'hingeMin': {}, 'hingeMax': {}, 'offAxisMaxDeg': 0, 'forearmShinTwistMaxDeg': 0, 'anyBoneTwistMaxDeg': [0, ''],
         'perFrameRotMaxDeg': [0, ''], 'groundMin': [9, ''], 'footDriftMax': [0, ''], 'penetrationMax': [0, ''],
         'volumeMinRatio': [9, '']}
SAMPLES = {}
log('checks')
for name, c in CLIPS.items():
    cm = {'frames': c.frames + 1, 'duration': round(c.frames / FPS, 4), 'loop': c.loop}
    cm.update(SNAP[name])
    hmin = {k: 1e9 for k in HINGES}
    hmax = {k: -1e9 for k in HINGES}
    offmax = 0
    tw = {}
    rotmax = (0, '', 0)
    gmin = (9, 0, '')
    pen = {}
    vol = {j: (9, 0) for j in JOINTS}
    sec = {j: (9, 0) for j in SECTION}
    balls = {S: [] for S, s in SIDES}
    prevq = None
    claw_prev = None
    claw_speed = []
    Ps = []
    for f, B in enumerate(c.bases):
        t = f / FPS
        P = fk(B)
        Ps.append(P)
        for k, (a, b, h, rng_, rel) in HINGES.items():
            bend, off = hinge(P, a, b, h)
            if rel:
                bend -= HINGE_REST[k]
            hmin[k] = min(hmin[k], bend)
            hmax[k] = max(hmax[k], bend)
            if not rel or k == 'Jaw':
                offmax = max(offmax, abs(off - (hinge(P_REST, a, b, h)[1])))
        q = {n: B[n].to_quaternion() for n in BN}
        for n in BN:
            tw[n] = max(tw.get(n, 0), abs(twist(B[n])))
            if prevq is not None:
                ang = math.degrees(prevq[n].rotation_difference(q[n]).angle)
                ang = min(ang, 360 - ang)
                if ang > rotmax[0]:
                    rotmax = (ang, n, f)
        prevq = q
        set_pose(B)
        V = eval_verts()
        zm, zsec = min((float(v[:, 2].min()), k) for k, v in V.items())
        if zm < gmin[0]:
            gmin = (zm, f, zsec)
        ps = pen_sets(V, P)
        for k, v in ps.items():
            if v >= pen.get(k, (0, 0))[0]:
                pen[k] = (v, f)
        for j, (b, r) in JOINTS.items():
            ratio = cone_volume(V['Body'], REGION[j], np.array(P[b].translation)) / VOL_REST[j]
            if ratio < vol[j][0]:
                vol[j] = (ratio, f)
        for j, (child, grp, r) in SECTION.items():
            ratio = float((axis_dist(V['Body'], P, child, SEC_IDX[j]) ** 2).mean()) / SEC_D0[j]
            if ratio < sec[j][0]:
                sec[j] = (ratio, f)
        for S, s in SIDES:
            balls[S].append(Vector(P[S + 'Toes'].translation) + Vector((0, -SPEED.get(name, 0) * t, 0)))
        tips = [claw_tip(P, S) for S, s in SIDES]
        if claw_prev is not None:
            claw_speed.append(max((a - b).length for a, b in zip(tips, claw_prev)) * FPS)
        claw_prev = tips
    # foot drift over planted segments
    drift = {}
    for S, s in SIDES:
        worst = 0.
        ref = None
        for f in range(c.frames + 1):
            if PLANTED[name](S, f / FPS):
                if ref is None:
                    ref = balls[S][f]
                worst = max(worst, (balls[S][f] - ref).length)
            else:
                ref = None
        drift[S] = round(worst, 5)
    cm['hingeDeg'] = {k: [round(hmin[k], 2), round(hmax[k], 2)] for k in HINGES}
    cm['hingeOK'] = all(HINGES[k][3][0] <= hmin[k] and hmax[k] <= HINGES[k][3][1] for k in HINGES)
    cm['hingeOffAxisMaxDeg'] = round(offmax, 3)
    cm['twistMaxDeg'] = {n: round(v, 2) for n, v in tw.items() if v > .05}
    fs = max(tw[n] for n in BN if n.endswith(('Forearm', 'Shin')))
    cm['forearmShinTwistMaxDeg'] = round(fs, 3)
    cm['perFrameRotationMaxDeg'] = {'deg': round(rotmax[0], 2), 'bone': rotmax[1], 'frame': rotmax[2]}
    cm['groundLowest'] = {'z': round(gmin[0], 4), 'frame': gmin[1], 'section': gmin[2], 'ok': gmin[0] >= -.05}
    cm['plantedFootDrift'] = drift
    cm['penetration'] = {k: {'depth': round(v[0], 4), 'frame': v[1]} for k, v in pen.items()}
    cm['jointVolumeMinRatio'] = {j: {'ratio': round(v[0], 4), 'frame': v[1]} for j, v in vol.items()}
    cm['jointSectionMinRatio'] = {j: {'ratio': round(v[0], 4), 'frame': v[1]} for j, v in sec.items()}
    cm['ikClamp'] = {'armMax': c.meta['ikClamp']['armMax'],
                     'legMaxWhilePlanted': round(max([c.meta['ikClamp']['legMaxPerFrame'][S][f] for S, s in SIDES
                                                      for f in range(c.frames + 1) if PLANTED[name](S, f / FPS)] or [0]), 5)}
    if claw_speed:
        k = int(np.argmax(claw_speed))
        cm['clawSpeedPeak'] = {'studsPerSec': round(claw_speed[k], 2), 'betweenFrames': [k, k + 1]}
    CHECKS['clips'][name] = cm
    SAMPLES[name] = Ps
    for k in HINGES:
        WORST['hingeMin'][k] = min(WORST['hingeMin'].get(k, 1e9), round(hmin[k], 2))
        WORST['hingeMax'][k] = max(WORST['hingeMax'].get(k, -1e9), round(hmax[k], 2))
    WORST['offAxisMaxDeg'] = max(WORST['offAxisMaxDeg'], round(offmax, 3))
    WORST['forearmShinTwistMaxDeg'] = max(WORST['forearmShinTwistMaxDeg'], round(fs, 3))
    bt = max(tw.items(), key=lambda x: x[1])
    if bt[1] > WORST['anyBoneTwistMaxDeg'][0]:
        WORST['anyBoneTwistMaxDeg'] = [round(bt[1], 2), f'{name}:{bt[0]}']
    if rotmax[0] > WORST['perFrameRotMaxDeg'][0]:
        WORST['perFrameRotMaxDeg'] = [round(rotmax[0], 2), f'{name}:{rotmax[1]}@{rotmax[2]}']
    if gmin[0] < WORST['groundMin'][0]:
        WORST['groundMin'] = [round(gmin[0], 4), f'{name}@{gmin[1]}']
    dm = max(drift.values())
    if dm > WORST['footDriftMax'][0]:
        WORST['footDriftMax'] = [dm, name]
    for k, v in pen.items():
        if v[0] > WORST['penetrationMax'][0]:
            WORST['penetrationMax'] = [round(v[0], 4), f'{name}:{k}@{v[1]}']
    for j, v in vol.items():
        if v[0] < WORST['volumeMinRatio'][0]:
            WORST['volumeMinRatio'] = [round(v[0], 4), f'{name}:{j}@{v[1]}']
    for j, v in sec.items():
        if v[0] < WORST.setdefault('sectionMinRatio', [9, ''])[0]:
            WORST['sectionMinRatio'] = [round(v[0], 4), f'{name}:{j}@{v[1]}']
    log('checked', name, json.dumps({'hingeOK': cm['hingeOK'], 'drift': drift, 'ground': cm['groundLowest'], 'rot': cm['perFrameRotationMaxDeg']}))
set_pose(IDB)
# Rake reach and timing facts
PI = SAMPLES['ClawRake'][12]
reach = {S: round((Vector(PI[S + 'Hand'].translation) - Vector(PI[S + 'UpperArm'].translation)).length / REACH[S], 4) for S, s in SIDES}
CHECKS['clawRakeReachAtImpact'] = reach
CHECKS['worst'] = WORST
CHECKS['restLowestZ'] = round(REST_ZMIN, 4)
CHECKS['restPenetration'] = {k: round(v, 4) for k, v in PEN_REST.items()}
CHECKS['limits'] = {'kneeElbowDeg': [-5, 150], 'fingersRelDeg': [-5, 100], 'toesRelDeg': [-20, 75], 'jawRelDeg': [-2, 45],
                    'forearmShinTwistDeg': 70, 'perFrameRotationDeg': 45, 'groundTolerance': .05, 'footDrift': .05,
                    'penetration': .05, 'jointVolumeRatio': .85}
CHECKS['notes'] = ['Checks run on the exported matrix_basis samples (forward kinematics), skinned meshes evaluated per frame.',
                   'Penetration = depth of hand/forearm skin points inside posed torso cores (ellipsoids per Pelvis/Spine/Chest) and '
                   'leg capsules (Thigh/Shin), snout points inside the torso cores, and mane points inside the head core. Cores sit '
                   'slightly inside the real surfaces, so 0 = no pass-through. restPenetration lists the rest-pose values.',
                   'Joint volume = cone volume of the skin patch around the joint centre, posed / rest.',
                   'Walk and ChargeRun drift adds the in-place travel (studs/s x t) back before measuring.']
log('worst', json.dumps(WORST))

# ------------------------------------------------------------------ AnimationData.json
S_SWAP = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def cf(m):
    m = S_SWAP @ m @ S_SWAP
    return [round(x, 7) for x in [m[0][3], m[1][3], m[2][3], m[0][0], m[0][1], m[0][2], m[1][0], m[1][1], m[1][2], m[2][0], m[2][1], m[2][2]]]


ORDER = ['Idle', 'Walk', 'Hit', 'Death', 'Howl', 'ChargeStart', 'ChargeRun', 'ClawRake']
anim = {'id': BOSS_ID, 'fps': FPS,
        'bones': {b.name: {'parent': b.parent.name if b.parent else None,
                           'rest': cf(b.parent.matrix_local.inverted() @ b.matrix_local if b.parent else b.matrix_local)}
                  for b in rig.data.bones if b.use_deform},
        'clips': {},
        'motion': {'strideLength': round(WALK['V'] * WALK['T'], 4), 'nominalSpeed': WALK['V'],
                   'chargeStrideLength': round(CHARGE['V'] * CHARGE['T'], 4), 'chargeSpeed': CHARGE['V']}}
for name in ORDER:
    c = CLIPS[name]
    anim['clips'][name] = {'duration': round(c.frames / FPS, 7), 'loop': c.loop,
                           'frames': [{'time': round(f / FPS, 7), 'transforms': {n: cf(B[n]) for n in BN}} for f, B in enumerate(c.bases)]}
(GAME / 'AnimationData.json').write_text(json.dumps(anim, separators=(',', ':')))
log('AnimationData.json written')


# ------------------------------------------------------------------ BossGameData.json
def studio(v):
    return [round(-v[0], 4), round(v[2], 4), round(v[1], 4)]


def r4(v):
    return [round(x, 4) for x in v]


def point(clip, f, bone, offset):
    w = SAMPLES[clip][f][bone] @ Vector(offset)
    return {'bone': bone, 'offset': r4(offset), 'rootAtImpact': r4(w), 'rootAtImpactStudio': studio(w)}


FWD = Vector((0, -1, 0))
game = {'attacks': {}}
fi = 12
pts = {}
for S, s in SIDES:
    pts[S + 'Claw'] = point('ClawRake', fi, S + 'Fingers', CLAW_OFF[S])
    pts[S + 'Forearm'] = point('ClawRake', fi, S + 'Forearm', (0, LIMBS[S + 'UpperArm']['L2'] / 2, 0))
warn_f, act_f = 2, 16
sweep = []
for f in range(fi - 3, act_f + 1):
    e = {'time': round(f / FPS, 4)}
    for k, p in pts.items():
        w = SAMPLES['ClawRake'][f][p['bone']] @ Vector(p['offset'])
        e[k] = r4(w)
        e[k + 'Studio'] = studio(w)
    sweep.append(e)
game['attacks']['ClawRake'] = {'duration': round(26 / FPS, 4), 'warnStart': round(warn_f / FPS, 4), 'impact': round(fi / FPS, 4),
                               'activeEnd': round(act_f / FPS, 4), 'recoveryEnd': round(23 / FPS, 4), 'points': pts,
                               'directionAtImpact': r4(FWD), 'directionAtImpactStudio': studio(FWD), 'sweep': sweep,
                               'reachAtImpact': reach,
                               'note': 'pouncing double rake: claws rise high and wide (0.08-0.30 s), lunge with a right-foot step, '
                                       'both claws rake down through the front at impact and on past the hips (activeEnd). Sweep a '
                                       'capsule between each Claw and Forearm point over the sweep samples. Also the charge finisher: '
                                       'crossfade ~0.1 s from ChargeRun.'}
# Howl mouth point: midway between the upper lip and the opened jaw tip at the peak.
hf = 24
PH = SAMPLES['Howl'][hf]
jaw_tip = TAIL['Jaw']
lip_rest = jaw_tip + Vector((0, -.15, .20))
lip = PH['Head'] @ (REST['Head'].inverted() @ lip_rest)
jt = PH['Jaw'] @ (REST['Jaw'].inverted() @ jaw_tip)
mouth = (lip + jt) / 2
moff = PH['Head'].inverted() @ mouth
Dh = PH['Head'].to_3x3() @ R3['Head'].transposed()
jaw_now = HW['jaw'](hf / FPS)
mdir = (Dh @ rot((1, 0, 0), jaw_now / 2) @ FWD).normalized()
game['attacks']['Howl'] = {'duration': round(53 / FPS, 4), 'warnStart': 0.0, 'impact': round(hf / FPS, 4), 'activeEnd': round(43 / FPS, 4),
                           'recoveryEnd': round(50 / FPS, 4),
                           'points': {'Mouth': {'bone': 'Head', 'offset': r4(moff), 'rootAtImpact': r4(mouth), 'rootAtImpactStudio': studio(mouth)}},
                           'directionAtImpact': r4(mdir), 'directionAtImpactStudio': studio(mdir),
                           'note': 'crouch 0-0.35 s, rears up; peak (buff moment) at impact, jaw open 38 deg, held with a tremor to '
                                   'activeEnd, recovers to the Idle pose. Also the rim intro howl.'}
cs_d = round(17 / FPS, 4)
game['attacks']['ChargeStart'] = {'duration': cs_d, 'warnStart': 0.0, 'impact': cs_d, 'activeEnd': cs_d, 'recoveryEnd': cs_d,
                                  'directionAtImpact': r4(FWD), 'directionAtImpactStudio': studio(FWD),
                                  'note': 'drops into a coiled sprinter crouch (0.33 s), right claws brushing the ground, eyes '
                                          'level; the last frame equals ChargeRun frame 0, so chain straight into ChargeRun.'}
game['attacks']['ChargeRun'] = {'duration': round(12 / FPS, 4), 'loop': True, 'chargeStrideLength': anim['motion']['chargeStrideLength'],
                                'chargeSpeed': CHARGE['V'], 'directionAtImpact': r4(FWD), 'directionAtImpactStudio': studio(FWD),
                                'note': 'in place; the server moves the model along its forward at chargeSpeed (play rate = '
                                        'speed / chargeSpeed). Low bounding biped sprint, feet planted in contact.'}
allv = np.concatenate([v for v in RESTV.values()])
game.update({'rootHeight': 0.0, 'height': round(float(allv[:, 2].max()), 4),
             'footprintRadius': round(float(np.sqrt((allv[:, :2] ** 2).sum(1)).max()), 4),
             'bodyCentreHeight': round((HEAD['Pelvis'].z + HEAD['Neck'].z) / 2, 4),
             'walk': {'strideLength': anim['motion']['strideLength'], 'nominalSpeed': WALK['V']},
             'notes': 'Times in seconds from clip start at 24 fps. Root bone sits on the ground under the pelvis (rootHeight 0). '
                      'Blender axes: +X the alpha\'s left, -Y forward, +Z up; Studio = (-X, Z, Y).'})
(GAME / 'BossGameData.json').write_text(json.dumps(game, indent=2))
CHECKS['motion'] = anim['motion']
(GAME / 'GameChecks.json').write_text(json.dumps(CHECKS, indent=2))
log('BossGameData.json + GameChecks.json written')

# ------------------------------------------------------------------ actions in the .blend
for name in ORDER:
    c = CLIPS[name]
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
    if name == 'ClawRake':
        act.pose_markers.new('Impact').frame = 1 + fi
    if name == 'Howl':
        act.pose_markers.new('Impact').frame = 1 + hf
rig.animation_data.action = None
set_pose(IDB)
log('actions keyed')

# ------------------------------------------------------------------ Studio FBX
FBM = GAME / f'{NAME}_Studio.fbm'
FBM.mkdir(exist_ok=True)
packed = {}
for sec, o in SECS.items():
    src = OUT / 'textures' / f'{NAME}_{sec}_BaseColor_1024.png'
    shutil.copy2(src, FBM / src.name)
    m = bpy.data.materials[f'{NAME}_{sec}']
    node = m.node_tree.nodes['BaseColor']
    packed[sec] = node.image
    node.image = bpy.data.images.load(str(src), check_existing=True)
rig.data.pose_position = 'REST'
for ob in bpy.context.view_layer.objects:
    ob.select_set(False)
rig.select_set(True)
for o in SECS.values():
    o.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.export_scene.fbx(filepath=str(GAME / f'{NAME}_Studio.fbx'), use_selection=True, object_types={'MESH', 'ARMATURE'},
                         bake_anim=False, add_leaf_bones=False, use_armature_deform_only=True, axis_forward='-Z', axis_up='Y',
                         path_mode='COPY', embed_textures=True, use_mesh_modifiers=False, mesh_smooth_type='OFF',
                         primary_bone_axis='Y', secondary_bone_axis='X')
for sec, o in SECS.items():
    bpy.data.materials[f'{NAME}_{sec}'].node_tree.nodes['BaseColor'].image = packed[sec]
rig.data.pose_position = 'POSE'
log('Studio FBX exported')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / f'{NAME}.blend'))
log('blend saved with actions')

# ------------------------------------------------------------------ preview frames (Workbench)
if RENDER:
    FRAMES.mkdir(parents=True, exist_ok=True)
    scene.render.engine = 'BLENDER_WORKBENCH'
    sh = scene.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'TEXTURE'
    sh.background_type = 'VIEWPORT'
    sh.background_color = (.62, .66, .72)
    sh.show_shadows = True
    sh.show_cavity = False
    scene.display.render_aa = '8'
    scene.view_settings.view_transform = 'Standard'
    if hasattr(scene.render.image_settings, 'media_type'):
        scene.render.image_settings.media_type = 'IMAGE'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.resolution_x = scene.render.resolution_y = 320
    scene.render.resolution_percentage = 100
    cam = scene.camera
    cam.data.type = 'ORTHO'
    floor = bpy.data.objects.get('ReviewGround')
    VIEWS = {'tq': (-35, 12.0, Vector((.5, -.8, 4.3))), 'front': (0, 11.5, Vector((0, -.8, 4.5))), 'side': (90, 12.0, Vector((0, -1.6, 4.3)))}

    def shot(clip, f, view):
        ang, ortho, ctr = VIEWS[view]
        R = Matrix.Rotation(math.radians(ang), 3, 'Z')
        cam.location = ctr + R @ Vector((0, -30, 2.5))
        cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z', 'Y').to_euler()
        cam.data.ortho_scale = ortho
        set_pose(CLIPS[clip].bases[f])
        scene.render.filepath = str(FRAMES / f'{clip}_{f:02d}_{view}.png')
        bpy.ops.render.render(write_still=True)
    SHEET = {'Idle': [0, 18, 36, 54], 'Walk': [0, 4, 9, 13], 'Hit': [0, 2, 5, 11], 'Death': [0, 10, 22, 30, 40, 53],
             'Howl': [0, 8, 24, 36, 48], 'ChargeStart': [0, 5, 8, 12, 17], 'ChargeRun': [0, 3, 6, 9], 'ClawRake': [0, 7, 10, 12, 16, 22]}
    jobs = set()
    for clip, fs in SHEET.items():
        for f in fs:
            jobs.add((clip, f, 'tq'))
    for clip, fs in (('ClawRake', [7, 12, 20]), ('Howl', [8, 24, 48])):
        for f in fs:
            jobs.add((clip, f, 'front'))
            jobs.add((clip, f, 'side'))
    for clip, fs in (('ChargeStart', [0, 6, 10, 17]), ('ChargeRun', [0, 3, 6, 9])):
        for f in fs:
            jobs.add((clip, f, 'side'))
            jobs.add((clip, f, 'tq'))
    for j in sorted(jobs):
        shot(*j)
    (FRAMES / 'sheet.json').write_text(json.dumps({'sheet': SHEET}))
    set_pose(IDB)
    log('preview frames rendered', len(jobs))
log('ANIM_COMPLETE')
