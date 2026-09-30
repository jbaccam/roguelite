"""Pharaoh game package (plans/BOSS_GAME_PACKAGE_SPEC.md). Run under Blender 5.2:

    blender -b --factory-startup --python build_game_package.py

Opens the approved Pharaoh.blend (model, textures and rig are NOT modified) and:
  * authors the clips Idle, Walk, Hit, Death, CursedBolts, TombEruption at 24 fps
    as sampled pose_bone.matrix_basis of the 62 deform bones;
  * writes exports/game/AnimationData.json (animate_mobs.py schema) and
    exports/game/BossGameData.json (attack timings, points, directions);
  * exports exports/game/Pharaoh_Studio.fbx (rest mesh + armature, 1024 maps,
    materials Pharaoh_<Section>, textures also copied into Pharaoh_Studio.fbm/);
  * renders previews/GameClips.png and low-res Workbench CursedBolts.mp4 and
    TombEruption.mp4;
  * saves the clips as actions into Pharaoh.blend and writes
    exports/game/GameMotionChecks.json.

Motion discipline (same rules the Cyclops swing needed):
  * the right fist never opens and the Staff bone never moves relative to the
    hand (except the Death release) -> grip closed on the shaft every frame;
  * the staff is aimed with shoulder, elbow, wrist and torso only; wrist
    rotation is capped (<= 18 deg) and arms reach straight at the strike /
    release (elbow flex limits), the raised arm stays in front of the body;
  * planted feet are pinned with analytic two-bone leg IK every frame.
"""
import bpy, math, json, os, shutil, time
import numpy as np
from pathlib import Path
from mathutils import Vector, Matrix, Quaternion

T0 = time.time()
HERE = Path(__file__).resolve().parent
GAME = HERE / 'exports' / 'game'
GAME.mkdir(parents=True, exist_ok=True)
WORK = HERE / '_work'
WORK.mkdir(exist_ok=True)
FPS = 24
NAME = 'Pharaoh'


def log(*a):
    print(f'[{time.time() - T0:7.1f}s]', *a, flush=True)


def export_studio_fbx():
    """Studio import FBX. Mesh OBJECTS keep the name Pharaoh_<Section>: Roblox's
    importer merges a mesh and a bone that share a name (mesh 'Head' vs bone
    'Head' broke the skinning)."""
    global scene, arm
    bpy.ops.wm.open_mainfile(filepath=str(HERE / 'Pharaoh.blend'))
    scene = bpy.context.scene
    arm = bpy.data.objects[NAME + '_Rig']
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_quaternion = Quaternion()
        pb.location = (0, 0, 0)
    fbm = GAME / f'{NAME}_Studio.fbm'
    fbm.mkdir(exist_ok=True)
    meshes = []
    for o in [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith(NAME + '_')]:
        sec = o.name.replace(NAME + '_', '')
        png = HERE / 'textures' / f'{NAME}_{sec}_Color_1024.png'
        shutil.copy2(png, fbm / png.name)
        im = bpy.data.images.load(str(fbm / png.name))
        m = bpy.data.materials.new(f'{NAME}_{sec}')
        m.use_nodes = True
        bs = m.node_tree.nodes.get('Principled BSDF')
        tx = m.node_tree.nodes.new('ShaderNodeTexImage')
        tx.image = im
        m.node_tree.links.new(tx.outputs['Color'], bs.inputs['Base Color'])
        bs.inputs['Roughness'].default_value = 0.85
        if sec == 'EyeGlow':
            m.node_tree.links.new(tx.outputs['Color'], bs.inputs['Emission Color'])
            bs.inputs['Emission Strength'].default_value = 5.0
        o.data.materials.clear()
        o.data.materials.append(m)
        meshes.append(o)
    bpy.ops.object.select_all(action='DESELECT')
    for o in [arm] + meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.fbx(filepath=str(GAME / f'{NAME}_Studio.fbx'), use_selection=True,
                             object_types={'ARMATURE', 'MESH'}, axis_forward='-Z', axis_up='Y',
                             add_leaf_bones=False, use_armature_deform_only=True, bake_anim=False,
                             path_mode='COPY', embed_textures=True, mesh_smooth_type='OFF',
                             use_mesh_modifiers=False)
    log('Studio FBX exported (Pharaoh.blend left unchanged on disk)')


if os.environ.get('STUDIO_ONLY') == '1':          # re-export the Studio FBX only
    export_studio_fbx()
    raise SystemExit(0)

bpy.ops.wm.open_mainfile(filepath=str(HERE / 'Pharaoh.blend'))
scene = bpy.context.scene
scene.render.fps = FPS
arm = bpy.data.objects[NAME + '_Rig']
PB = arm.pose.bones
BONES = [b.name for b in arm.data.bones]
SECTIONS = {o.name.replace(NAME + '_', ''): o for o in bpy.data.objects
            if o.type == 'MESH' and o.name.startswith(NAME + '_')}
for pb in PB:
    pb.rotation_mode = 'QUATERNION'


def mods(on):
    for o in SECTIONS.values():
        for m in o.modifiers:
            if m.type == 'ARMATURE':
                m.show_viewport = on
                m.show_render = on


def upd():
    bpy.context.view_layer.update()


# ------------------------------------------------------------ reference base
ad = arm.animation_data or arm.animation_data_create()


def bind(act):
    ad.action = act
    if act is not None and getattr(act, 'slots', None) and len(act.slots):
        if ad.action_slot is None or ad.action_slot not in list(act.slots):
            ad.action_slot = act.slots[0]


bind(bpy.data.actions['ReferencePose'])
scene.frame_set(1)
BASE = {pb.name: pb.rotation_quaternion.copy() for pb in PB}
bind(None)
for pb in PB:
    pb.rotation_quaternion = Quaternion()
    pb.location = (0, 0, 0)
mods(False)
upd()

REST3 = {b.name: b.matrix_local.to_3x3() for b in arm.data.bones}


def wq(bone, axis, deg):
    """Rotation about a world axis expressed in the bone's rest frame."""
    ax = REST3[bone].inverted() @ Vector(axis)
    return Quaternion(ax.normalized(), math.radians(deg))


def lq(axis, deg):
    return Quaternion(Vector(axis), math.radians(deg))


X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)


# ------------------------------------------------------------ pose containers
def pose_base():
    return {n: [q.copy(), Vector()] for n, q in BASE.items()}


def rot(p, bone, q):
    p[bone][0] = p[bone][0] @ q


def move(p, bone, v):
    """Translate a bone by a WORLD-axis vector (pose location lives in the
    bone's rest frame, unaffected by its own rotation)."""
    p[bone][1] = p[bone][1] + REST3[bone].inverted() @ Vector(v)


def apply(p):
    for n, (q, l) in p.items():
        PB[n].rotation_quaternion = q
        PB[n].location = l


def blend(pa, pb_, s):
    out = {}
    for n in pa:
        qa, la = pa[n]
        qb, lb = pb_[n]
        if qa.dot(qb) < 0:
            qb = -qb
        out[n] = [qa.slerp(qb, s), la.lerp(lb, s)]
    return out


def ease(s):
    s = max(0.0, min(1.0, s))
    return s * s * (3 - 2 * s)


def ease_in(s):
    s = max(0.0, min(1.0, s))
    return s * s


def ease_out(s):
    s = max(0.0, min(1.0, s))
    return 1 - (1 - s) * (1 - s)


def keyed(keys, t):
    """keys: [(time, pose, easing)] -> interpolated pose at t."""
    if t <= keys[0][0]:
        return {n: [v[0].copy(), v[1].copy()] for n, v in keys[0][1].items()}
    for (t0, p0, _), (t1, p1, e) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            return blend(p0, p1, e((t - t0) / max(1e-9, t1 - t0)))
    return {n: [v[0].copy(), v[1].copy()] for n, v in keys[-1][1].items()}


# ------------------------------------------------------------ measurements
def bone_head(n):
    return (arm.matrix_world @ PB[n].head).copy()


def bone_mat(n):
    return (arm.matrix_world @ PB[n].matrix).copy()


STAFF_MESH = SECTIONS['Staff']
_sv = np.empty(len(STAFF_MESH.data.vertices) * 3, np.float32)
STAFF_MESH.data.vertices.foreach_get('co', _sv)
_sv = _sv.reshape(-1, 3)
_Ms = STAFF_MESH.matrix_world
_sv = np.array([list(_Ms @ Vector(v)) for v in _sv])
STAFF_REST = arm.data.bones['Staff'].matrix_local
_Si = np.array(STAFF_REST.inverted())
STAFF_LOCAL = (_Si[:3, :3] @ _sv.T).T + _Si[:3, 3]          # staff verts, Staff-bone space
ly = STAFF_LOCAL[:, 1]
foot_sel = STAFF_LOCAL[ly < ly.min() + 0.02]
STAFF_IMPACT_OFF = Vector((float(foot_sel[:, 0].mean()), float(ly.min()),
                           float(foot_sel[:, 2].mean())))
hook = STAFF_LOCAL[ly > ly.max() - 2.1]
BOLT_OFF = Vector(hook.mean(axis=0).tolist())                # inside the crook's curl


def staff_point(off):
    return bone_mat('Staff') @ off


def staff_min_z():
    M = np.array(bone_mat('Staff'))
    w = (M[:3, :3] @ STAFF_LOCAL.T).T + M[:3, 3]
    return float(w[:, 2].min())


def staff_world_verts(M):
    M = np.array(M)
    return (M[:3, :3] @ STAFF_LOCAL.T).T + M[:3, 3]


# ------------------------------------------------------------ leg IK
LEG = {}
for side in ('Left', 'Right'):
    ul, ll, ft = arm.data.bones[side + 'UpperLeg'], arm.data.bones[side + 'LowerLeg'], \
        arm.data.bones[side + 'Foot']
    H0, K0, A0 = ul.head_local.copy(), ll.head_local.copy(), ll.tail_local.copy()
    d = (A0 - H0).normalized()
    pole = (K0 - H0) - d * (K0 - H0).dot(d)
    if pole.length < 0.05 or pole.normalized().dot(Vector((0, -1, 0))) < 0.2:
        pole = pole.normalized() * 0.3 + Vector((0, -1, 0))
    LEG[side] = dict(L1=(K0 - H0).length, L2=(A0 - K0).length, A0=A0, pole=pole.normalized(),
                     xrest=ul.matrix_local.col[0].xyz.normalized(),
                     foot_rot=ft.matrix_local.to_3x3())


def frame_mat(x, y, head):
    y = y.normalized()
    x = (x - y * x.dot(y)).normalized()
    z = x.cross(y)
    M = Matrix((x, y, z)).transposed().to_4x4()
    M.translation = head
    return M


def leg_ik(side, A, foot_pitch=0.0, foot_yaw=0.0):
    """Place the ankle (LowerLeg tail) exactly at A with a hinge knee."""
    L = LEG[side]
    upd()
    H = PB[side + 'UpperLeg'].head.copy()
    d = A - H
    dist = min(max(d.length, 0.3), L['L1'] + L['L2'] - 1e-4)
    dn = d.normalized()
    n = dn.cross(L['pole'])
    if n.length < 1e-4:
        n = L['xrest'].copy()
    n.normalize()
    u = n.cross(dn).normalized()
    if u.dot(L['pole']) < 0:
        u = -u
    a = (L['L1'] ** 2 - L['L2'] ** 2 + dist ** 2) / (2 * dist)
    h = math.sqrt(max(0.0, L['L1'] ** 2 - a * a))
    K = H + dn * a + u * h
    x = n if n.dot(L['xrest']) > 0 else -n
    PB[side + 'UpperLeg'].matrix = frame_mat(x, K - H, H)
    upd()
    PB[side + 'LowerLeg'].matrix = frame_mat(x, (H + dn * dist) - K, K)
    upd()
    Rf = (Matrix.Rotation(math.radians(foot_yaw), 3, 'Z') @
          Matrix.Rotation(math.radians(foot_pitch), 3, 'X') @ L['foot_rot'])
    M = Rf.to_4x4()
    M.translation = PB[side + 'LowerLeg'].tail.copy()
    PB[side + 'Foot'].matrix = M
    upd()


def pin_feet(targets=None):
    for side in ('Left', 'Right'):
        A = LEG[side]['A0'] if targets is None else targets[side]
        leg_ik(side, A)


# ------------------------------------------------------------ arm solver
def angle_between(a, b):
    return math.degrees(a.angle(b)) if a.length and b.length else 0.0


def elbow_flex(side):
    ua = PB[side + 'UpperArm']
    fa = PB[side + 'LowerArm']
    return angle_between(ua.tail - ua.head, fa.tail - fa.head)


def wrist_deg(side):
    return math.degrees(PB[side + 'Hand'].rotation_quaternion.angle)


ARM_KEYS = ('flex', 'abd', 'horiz', 'hum', 'elbow', 'wrist')


def arm_pose(p, side, prm, torso=None):
    """Right/left arm parameters (deg): shoulder flex (world X), abduction
    (world Y, + = out), humeral rotation (bone Y), elbow (local X, + closes),
    wrist flexion (local X, capped)."""
    s = -1 if side == 'Right' else 1
    ua = side + 'UpperArm'
    # composition order = world rotations applied abduction -> flexion ->
    # horizontal swing (across the chest), then the humeral twist
    rot(p, ua, wq(ua, Z, prm.get('horiz', 0.0)))
    rot(p, ua, wq(ua, X, prm['flex']))
    rot(p, ua, wq(ua, Y, -s * prm['abd']))
    rot(p, ua, lq(Y, prm['hum']))
    rot(p, side + 'LowerArm', lq(X, prm['elbow']))
    rot(p, side + 'Hand', lq(X, prm['wrist']))
    if torso:
        rot(p, 'UpperTorso', wq('UpperTorso', X, torso[0]))
        rot(p, 'UpperTorso', wq('UpperTorso', Z, torso[1]))
        rot(p, 'LowerTorso', wq('LowerTorso', X, torso[0] * 0.35))


def solve(base_pose, side, init, ranges, objective, rounds=4, step=6.0, torso_fixed=None):
    prm = dict(init)

    def score(q):
        p = {n: [v[0].copy(), v[1].copy()] for n, v in base_pose.items()}
        arm_pose(p, side, q, torso_fixed)
        apply(p)
        upd()
        s = objective()
        # discipline penalties
        ef = elbow_flex(side)
        lo, hi = ranges.get('_elbow_total', (5, 130))
        s += max(0.0, lo - ef) * 0.4 + max(0.0, ef - hi) * 0.4
        s += max(0.0, abs(q['wrist']) - 18.0) * 2.0
        return s
    best = score(prm)
    for r in range(rounds):
        stp = step / (2.0 ** r)
        improved = True
        while improved:
            improved = False
            for k in ARM_KEYS:
                lo, hi = ranges[k]
                for dv in (-stp, stp):
                    q = dict(prm)
                    q[k] = min(hi, max(lo, q[k] + dv))
                    s = score(q)
                    if s < best - 1e-6:
                        best, prm, improved = s, q, True
    p = {n: [v[0].copy(), v[1].copy()] for n, v in base_pose.items()}
    arm_pose(p, side, prm, torso_fixed)
    apply(p)
    upd()
    return p, prm, best


RANGES = dict(flex=(-160, 40), abd=(-15, 70), horiz=(-45, 45), hum=(-60, 60), elbow=(-95, 34),
              wrist=(-18, 18))
LRANGES = dict(flex=(-160, 40), abd=(-25, 60), horiz=(-75, 30), hum=(-60, 60), elbow=(-25, 104),
               wrist=(-18, 18))
CHECKS = {'clips': {}}


# ------------------------------------------------------------ secondary motion
CLOTH_FRONT = ('Apron_1', 'Apron_2', 'NemesLappet_L_1', 'NemesLappet_L_2', 'NemesLappet_R_1',
               'NemesLappet_R_2')
CLOTH_BACK = ('NemesTail', 'Kilt_Back')
ENDS = ('BandageEnd_ShoulderL', 'BandageEnd_WristL', 'BandageEnd_FootL')


def cloth_lag(p, pitch_now, pitch_past, sway_now=0.0, sway_past=0.0, gain=0.9):
    """Cloth trails the torso: rotation proportional to recent torso motion."""
    dp = (pitch_now - pitch_past) * gain
    ds = (sway_now - sway_past) * gain
    for n in CLOTH_FRONT + ENDS:
        rot(p, n, wq(n, X, -dp))
        rot(p, n, wq(n, Y, ds * 0.6))
    for n in CLOTH_BACK:
        rot(p, n, wq(n, X, dp * 0.8))
    for n in ('Kilt_L', 'Kilt_R'):
        rot(p, n, wq(n, Y, ds))


# ------------------------------------------------------------ sampling
S = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def cf(m):
    m = S @ m @ S
    return [round(x, 7) for x in [m[0][3], m[1][3], m[2][3], m[0][0], m[0][1], m[0][2],
                                  m[1][0], m[1][1], m[1][2], m[2][0], m[2][1], m[2][2]]]


ANIM = {'id': 'pharaoh', 'fps': FPS,
        'bones': {b.name: {'parent': b.parent.name if b.parent else None,
                           'rest': cf(b.parent.matrix_local.inverted() @ b.matrix_local
                                      if b.parent else b.matrix_local)}
                  for b in arm.data.bones},
        'clips': {}, 'motion': {}}
BASIS = {}          # clip -> list of {bone: Matrix basis}


def record(clip, frames, loop, posefn):
    """posefn(f, t) leaves the rig posed for frame f; its matrix_basis is sampled."""
    out, bases = [], []
    for f in range(frames + 1):
        posefn(f, f / FPS)
        upd()
        b = {n: PB[n].matrix_basis.copy() for n in BONES}
        if loop and f == frames:
            b = {n: m.copy() for n, m in bases[0].items()}
        bases.append(b)
        out.append({'time': round(f / FPS, 6), 'transforms': {n: cf(b[n]) for n in BONES}})
    ANIM['clips'][clip] = {'duration': round(frames / FPS, 6), 'loop': loop, 'frames': out}
    BASIS[clip] = bases
    log('recorded', clip, frames + 1, 'frames')


def pose_from_basis(b):
    for n, m in b.items():
        loc, q, sc = m.decompose()
        PB[n].rotation_quaternion = q
        PB[n].location = loc
    upd()


# =================================================================== IDLE
IDLE_N = 72                       # 3.0 s
STAFF_REST_LIFT = [0.0]           # elbow flex (deg) that seats the staff foot on the ground


def idle_pose(t, amp=1.0):
    p = pose_base()
    w = 2 * math.pi * t / (IDLE_N / FPS)
    br = math.sin(w)
    shift = math.sin(w + 0.6)
    rot(p, 'UpperTorso', wq('UpperTorso', X, -1.4 * br * amp))           # chest heaves
    rot(p, 'UpperTorso', wq('UpperTorso', Y, 0.8 * shift * amp))
    rot(p, 'LowerTorso', wq('LowerTorso', Y, -0.9 * shift * amp))       # weight shift
    move(p, 'HumanoidRootPart', (0.06 * shift * amp, 0, -0.03 * (1 - br) * amp))
    rot(p, 'Head', wq('Head', X, 1.2 * math.sin(w - 0.5) * amp))
    rot(p, 'Jaw', lq(X, 1.5 + 1.5 * math.sin(w - 0.3) * amp))
    rot(p, 'LeftUpperArm', wq('LeftUpperArm', Y, 1.5 * math.sin(w - 0.4) * amp))
    rot(p, 'LeftLowerArm', lq(X, 1.5 * math.sin(w - 0.8) * amp))
    # right arm counter-rotates the chest motion so the planted staff barely moves
    rot(p, 'RightLowerArm', lq(X, STAFF_REST_LIFT[0]))
    rot(p, 'RightUpperArm', wq('RightUpperArm', X, 1.4 * br * amp))
    rot(p, 'RightUpperArm', wq('RightUpperArm', Y, -0.8 * shift * amp))
    lag = math.sin(w - 1.1) * amp                                         # cloth drifts later
    for n in CLOTH_FRONT:
        rot(p, n, wq(n, X, 1.6 * lag))
    for n in CLOTH_BACK + ('Kilt_L', 'Kilt_R'):
        rot(p, n, wq(n, X, -1.2 * lag))
    for n in ENDS:
        rot(p, n, wq(n, Y, 3.0 * math.sin(w - 1.5) * amp))
    return p


def idle_frame(f, t):
    apply(idle_pose(t))
    upd()
    pin_feet()


IDLE0 = None

def seat_staff():
    for d in [x * 0.5 for x in range(0, 17)]:
        STAFF_REST_LIFT[0] = d
        lo = 9e9
        for f in range(0, IDLE_N, 6):
            apply(idle_pose(f / FPS))
            upd()
            lo = min(lo, staff_min_z())
        if lo >= 0.0:
            break
    log('staff seated with elbow lift', STAFF_REST_LIFT[0], 'deg; idle staff min z', round(lo, 3))


seat_staff()


# =================================================================== WALK
WALK_N = 36                       # 1.5 s cycle
WALK_T = WALK_N / FPS
STRIDE = 4.2                      # studs per cycle
SPEED = STRIDE / WALK_T
DUTY = 0.62                       # heavy: long stance, double support
WALK_X = {'Left': 1.62, 'Right': -1.62}
WALK_YC = -0.55


def foot_track(side, t):
    """In-place foot target: planted feet move back at exactly SPEED (so they
    stay still in the world when the boss moves at SPEED); swing lifts and
    swings forward. Left foot lands at phase 0, right at phase 0.5."""
    ph = (t / WALK_T + (0.0 if side == 'Left' else 0.5)) % 1.0
    half = SPEED * DUTY * WALK_T / 2
    x = WALK_X[side]
    z0 = LEG[side]['A0'].z
    if ph < DUTY:
        s = ph / DUTY
        return Vector((x, WALK_YC - half + 2 * half * s, z0)), True, 0.0
    s = (ph - DUTY) / (1 - DUTY)
    e = ease(s)
    y = WALK_YC + half - 2 * half * e
    lift = 0.95 * math.sin(math.pi * s) ** 0.8
    pitch = -18 * math.sin(math.pi * min(1.0, s * 1.3))
    return Vector((x, y, z0 + lift)), False, pitch


def walk_frame(f, t):
    p = pose_base()
    ph = (t / WALK_T) % 1.0
    w = 2 * math.pi * ph
    # body: heavy drop after each foot strike (twice per cycle), side sway
    drop = 0.22 * (0.5 + 0.5 * math.cos(2 * w - 0.9))
    move(p, 'HumanoidRootPart', (0.16 * math.sin(w), 0.0, -0.18 - drop))
    rot(p, 'LowerTorso', wq('LowerTorso', Y, 4.0 * math.sin(w)))
    rot(p, 'LowerTorso', wq('LowerTorso', Z, -5.0 * math.cos(w)))
    rot(p, 'UpperTorso', wq('UpperTorso', Z, 8.0 * math.cos(w)))       # counter twist
    rot(p, 'UpperTorso', wq('UpperTorso', X, 6.0 + 2.0 * math.cos(2 * w)))   # hunched stomp
    rot(p, 'Head', wq('Head', X, -4.0 - 2.0 * math.cos(2 * w - 0.6)))
    rot(p, 'Head', wq('Head', Z, -5.0 * math.cos(w)))
    # left arm swings opposite the left leg; claw loose
    rot(p, 'LeftUpperArm', wq('LeftUpperArm', X, 16.0 * math.cos(w)))
    rot(p, 'LeftLowerArm', lq(X, 10.0 + 6.0 * math.cos(w + 0.5)))
    # right arm carries the staff (lifted clear of the ground) and swings with
    # the arm, opposite the right leg
    rot(p, 'RightUpperArm', wq('RightUpperArm', X, -16.0 - 8.0 * math.cos(w)))
    rot(p, 'RightLowerArm', lq(X, 26.0 + 3.0 * math.cos(w + 0.5)))
    cloth_lag(p, 3.0 * math.cos(2 * w), 3.0 * math.cos(2 * w - 0.9),
              6.0 * math.sin(w), 6.0 * math.sin(w - 0.8))
    for side, s_ in (('Left', 1), ('Right', -1)):
        rot(p, 'Kilt_' + side[0], wq('Kilt_' + side[0], X, -9.0 * math.cos(w) * s_))
    apply(p)
    upd()
    for side in ('Left', 'Right'):
        A, planted, pitch = foot_track(side, t)
        leg_ik(side, A, foot_pitch=pitch)


# =================================================================== HIT
HIT_N = 11                        # 0.458 s


def hit_frame(f, t):
    s = t / (HIT_N / FPS)
    k = math.sin(math.pi * min(1.0, s * 1.6)) * (1 - ease(max(0.0, (s - 0.3) / 0.7))) \
        if s < 1 else 0.0
    k = max(0.0, k)
    p = idle_pose(0.0)
    rot(p, 'UpperTorso', wq('UpperTorso', X, -11.0 * k))                # flinch back
    rot(p, 'LowerTorso', wq('LowerTorso', X, -3.0 * k))
    rot(p, 'Head', wq('Head', X, -12.0 * k))
    rot(p, 'Head', wq('Head', Z, 6.0 * k))
    rot(p, 'Jaw', lq(X, 14.0 * k))
    rot(p, 'LeftUpperArm', wq('LeftUpperArm', Y, 12.0 * k))
    rot(p, 'LeftLowerArm', lq(X, 16.0 * k))
    rot(p, 'RightUpperArm', wq('RightUpperArm', X, -9.0 * k))            # staff tilts, not dug in
    move(p, 'HumanoidRootPart', (0, 0.12 * k, -0.10 * k))
    cloth_lag(p, 11.0 * k, 11.0 * max(0.0, k - 0.35))
    apply(p)
    upd()
    pin_feet()


# =================================================================== ATTACK POSES
def base_with(extra):
    p = idle_pose(0.0)
    for n, qs in extra.items():
        for q in qs:
            rot(p, n, q)
    return p


def solve_bolts():
    """Aim pose: crook raised, arm reaching forward-up, the hook's curl
    pointing at a target 16 studs ahead at chest height."""
    torso = (8.0, 14.0)                    # lean in, turn the staff shoulder forward
    base = base_with({})
    target_up = 10.2

    def obj():
        O = staff_point(BOLT_OFF)
        G = bone_mat('Staff').translation
        D = (O - G).normalized()
        s = abs(O.z - target_up) * 2.0 + (O.y + 7.0) * 0.8 * (O.y > -7.0)
        s += abs(O.x + 2.2) * 0.4
        s += max(0.0, D.dot(Vector((0, -1, 0))) * -1 + 0.55) * 4.0   # staff tilts forward
        s += max(0.0, 0.2 - staff_min_z()) * 4.0
        return s
    rng = dict(RANGES, _elbow_total=(25, 70))
    return solve(base, 'Right', dict(flex=-60, abd=10, horiz=0, hum=0, elbow=-60, wrist=0), rng,
                 obj, torso_fixed=torso)


def solve_tomb(lift):
    """Two-handed staff: vertical in front, foot `lift` studs off the ground."""
    # lean in and turn the chest well to his right, so the LEFT hand can reach
    # across to the shaft held in front of the right hip
    torso = (18.0, -30.0) if lift < 0.5 else (6.0, -26.0)
    base = base_with({})
    move(base, 'HumanoidRootPart', (0, -0.15, -0.55 if lift < 0.5 else 0.10))
    foot_goal = Vector((-1.5, -4.0, max(0.02, lift)))

    def obj():
        F = staff_point(STAFF_IMPACT_OFF)
        D = bone_mat('Staff').to_3x3() @ Vector((0, 1, 0))
        s = (F - foot_goal).length * 3.0
        s += (1 - max(-1.0, min(1.0, D.normalized().dot(Vector((0.05, 0.10, 1)).normalized())))) * 40
        return s
    rng = dict(RANGES, _elbow_total=(12, 60) if lift < 0.5 else (20, 110))
    p, prm, sc = solve(base, 'Right', dict(flex=-45, abd=0, horiz=25, hum=0, elbow=-50, wrist=0),
                       rng, obj, torso_fixed=torso)
    if lift < 0.5:
        # drive the foot exactly onto the ground: drop the whole body the
        # remaining distance (the legs re-bend under leg IK)
        fz = staff_min_z()                  # lowest staff vertex, not just the foot centre
        move(p, 'HumanoidRootPart', (0, 0, -fz - 0.03))
        apply(p)
        upd()
    # left hand joins the shaft ~1.0 stud above the right grip
    G = bone_mat('Staff').translation.copy()
    D = (bone_mat('Staff').to_3x3() @ Vector((0, 1, 0))).normalized()
    goal = G + D * 0.95

    def lobj():
        H = PB['LeftHand'].head.lerp(PB['LeftHand'].tail, 0.55)
        return (H - goal).length * 4.0
    rng2 = dict(LRANGES, _elbow_total=(10, 100))
    log('tomb', lift, 'grip', [round(c, 2) for c in G], 'goal', [round(c, 2) for c in goal],
        'Lshoulder', [round(c, 2) for c in PB['LeftUpperArm'].head],
        'foot', [round(c, 2) for c in staff_point(STAFF_IMPACT_OFF)], 'D', [round(c, 2) for c in D])
    p2, prm2, sc2 = solve(p, 'Left', dict(flex=-70, abd=-10, horiz=-40, hum=0, elbow=30, wrist=0),
                          rng2, lobj)
    # left fingers close round the shaft
    for f in ('Index', 'Middle', 'Ring', 'Pinky'):
        for i, a in ((1, 38), (2, 48), (3, 40)):
            rot(p2, f'Left{f}{i}', lq(X, a))
    rot(p2, 'LeftThumb1', lq(X, 25))
    return p2, dict(right=prm, left=prm2, score=sc, left_score=sc2)


t_s = time.time()
BOLT_POSE, BOLT_PRM, BOLT_SC = solve_bolts()
upd()
BOLT_O = staff_point(BOLT_OFF).copy()
log('bolts aim', {k: round(v, 1) for k, v in BOLT_PRM.items()}, 'score', round(BOLT_SC, 3),
    'origin', [round(c, 2) for c in BOLT_O])
TOMB_LIFT, TOMB_LIFT_PRM = solve_tomb(2.6)
TOMB_HIT, TOMB_HIT_PRM = solve_tomb(0.0)
log('tomb solved', f'{time.time() - t_s:.1f}s', TOMB_LIFT_PRM['score'], TOMB_HIT_PRM['score'],
    TOMB_LIFT_PRM['left_score'], TOMB_HIT_PRM['left_score'])


def recoil(pose, k):
    p = {n: [v[0].copy(), v[1].copy()] for n, v in pose.items()}
    rot(p, 'RightUpperArm', wq('RightUpperArm', X, -6.0 * k))
    rot(p, 'RightLowerArm', lq(X, 6.0 * k))
    rot(p, 'UpperTorso', wq('UpperTorso', X, -6.0 * k))                 # recoil back
    rot(p, 'Head', wq('Head', X, -5.0 * k))
    move(p, 'HumanoidRootPart', (0, 0.10 * k, 0))
    return p


# =================================================================== CURSED BOLTS
BOLT_N = 51                       # 2.125 s
BOLT_T = dict(raise_end=0.45, charge_start=0.45, impact=25 / 24, recoil_peak=1.20, recovered=2.125)
IDLE_START = idle_pose(0.0)


def staff_up(pose, elbow=24.0, flex=-10.0):
    p = {n: [v[0].copy(), v[1].copy()] for n, v in pose.items()}
    rot(p, 'RightLowerArm', lq(X, elbow))
    rot(p, 'RightUpperArm', wq('RightUpperArm', X, flex))
    return p


BOLT_KEYS = [(0.0, IDLE_START, ease), (0.18, staff_up(IDLE_START), ease), (0.45, BOLT_POSE, ease),
             (25 / 24, BOLT_POSE, ease), (1.20, recoil(BOLT_POSE, 1.0), ease_out),
             (1.45, BOLT_POSE, ease), (1.90, staff_up(IDLE_START), ease),
             (2.125, IDLE_START, ease)]


BOLT_PITCH = [(0, 0.0), (0.45, 6.0), (25 / 24, 6.0), (1.20, 10.0), (1.45, 6.0), (1.95, 0.0),
              (2.125, 0.0)]


def bolt_frame(f, t):
    p = keyed(BOLT_KEYS, t)
    if 0.45 < t < 25 / 24:                 # gathering: slight tremble of arm and head
        tr = math.sin(2 * math.pi * 11 * t) * ease((t - 0.45) / 0.3)
        rot(p, 'RightUpperArm', wq('RightUpperArm', X, 0.6 * tr))
        rot(p, 'Head', wq('Head', X, -0.8 * tr))
    cloth_lag(p, scalar_key(BOLT_PITCH, t), scalar_key(BOLT_PITCH, max(0.0, t - 0.15)))
    apply(p)
    upd()
    pin_feet()


# =================================================================== TOMB ERUPTION
TOMB_N = 60                       # 2.5 s
TOMB_IMPACT = 19 / 24
TOMB_KEYS = [(0.0, IDLE_START, ease), (0.20, staff_up(IDLE_START), ease),
             (0.60, TOMB_LIFT, ease), (TOMB_IMPACT, TOMB_HIT, ease_in),
             (1.60, TOMB_HIT, ease), (1.90, staff_up(blend(TOMB_HIT, IDLE_START, 0.4), 22.0, -14.0),
                                       ease),
             (2.28, staff_up(IDLE_START, 10.0, -4.0), ease), (2.50, IDLE_START, ease)]


def scalar_key(keys, t):
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            return v0 + (v1 - v0) * ease((t - t0) / (t1 - t0))
    return keys[-1][1] if t > keys[-1][0] else keys[0][1]


TOMB_PITCH = [(0, 0.0), (0.6, 5.0), (TOMB_IMPACT, -16.0), (1.6, -16.0), (2.3, 0.0), (2.5, 0.0)]


def tomb_frame2(f, t):
    p = keyed(TOMB_KEYS, t)
    if TOMB_IMPACT <= t <= 1.60:
        k = math.sin(math.pi * (t - TOMB_IMPACT) / (1.60 - TOMB_IMPACT))
        tr = math.sin(2 * math.pi * 9 * t) * k
        rot(p, 'UpperTorso', wq('UpperTorso', X, 0.5 * tr))
        rot(p, 'Head', wq('Head', X, 3.0 * k))                           # head bows, channelling
    if TOMB_IMPACT <= t <= TOMB_IMPACT + 0.15:
        j = math.sin(math.pi * (t - TOMB_IMPACT) / 0.15)
        move(p, 'HumanoidRootPart', (0, 0, -0.03 * j))
    cloth_lag(p, scalar_key(TOMB_PITCH, t), scalar_key(TOMB_PITCH, max(0.0, t - 0.15)))
    apply(p)
    upd()
    pin_feet()


# =================================================================== DEATH
DEATH_N = 54                      # 2.25 s
PRONE = None
STAFF_FALL = {}


def death_keys():
    kneel = idle_pose(0.0)
    rot(kneel, 'UpperTorso', wq('UpperTorso', X, 20.0))                # slumps forward
    rot(kneel, 'Head', wq('Head', X, 12.0))
    rot(kneel, 'LeftUpperArm', wq('LeftUpperArm', Y, -8.0))
    rot(kneel, 'LeftLowerArm', lq(X, 12.0))
    move(kneel, 'HumanoidRootPart', (0, -0.3, -1.25))
    stag = idle_pose(0.0)
    rot(stag, 'UpperTorso', wq('UpperTorso', X, -9.0))                 # staggers back
    rot(stag, 'Head', wq('Head', X, -14.0))
    rot(stag, 'Jaw', lq(X, 20.0))
    move(stag, 'HumanoidRootPart', (0, 0.25, -0.25))
    prone = pose_base()
    rot(prone, 'HumanoidRootPart', wq('HumanoidRootPart', X, 86.0))    # face down
    rot(prone, 'UpperTorso', wq('UpperTorso', X, 4.0))
    rot(prone, 'Head', wq('Head', Z, 35.0))
    rot(prone, 'Jaw', lq(X, 16.0))
    for side, s in (('Left', 1), ('Right', -1)):
        rot(prone, side + 'UpperArm', wq(side + 'UpperArm', Y, s * 16.0))
        rot(prone, side + 'LowerArm', lq(X, 8.0))
    for n in ('Apron_1', 'Kilt_Back', 'NemesTail'):
        rot(prone, n, wq(n, X, -6.0))
    return stag, kneel, prone


def lowest_body_z():
    mods(True)
    dg = bpy.context.evaluated_depsgraph_get()
    mz = 9e9
    for sec, o in SECTIONS.items():
        if sec == 'Staff':
            continue
        oe = o.evaluated_get(dg)
        me = oe.to_mesh()
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        M = np.array(oe.matrix_world)
        z = (co @ M[:3, :3].T + M[:3, 3])[:, 2]
        mz = min(mz, float(z.min()))
        oe.to_mesh_clear()
    mods(False)
    return mz


def death_prepare():
    stag, kneel, prone = death_keys()
    # find the prone drop so the lowest vertex just touches the ground
    apply(prone)
    upd()
    mz = lowest_body_z()
    move(prone, 'HumanoidRootPart', (0, 0, -mz + 0.01))
    keys = [(0.0, IDLE_START, ease), (0.30, stag, ease), (0.85, kneel, ease),
            (1.55, prone, ease_in), (1.75, None, ease_out), (2.25, None, ease)]
    # small settle bounce, then hold
    bounce = {n: [v[0].copy(), v[1].copy()] for n, v in prone.items()}
    move(bounce, 'HumanoidRootPart', (0, 0, 0.12))
    keys[4] = (1.72, bounce, ease_out)
    keys[5] = (1.95, prone, ease)
    keys.append((2.25, prone, ease))
    return keys


DEATH_KEYS = None
LEG_RELEASE = (0.85, 1.55)
STAFF_REL = 0.40


def death_frame(f, t):
    p = keyed(DEATH_KEYS, t)
    # fingers of the staff hand open after the release
    k = ease((t - STAFF_REL) / 0.25)
    for fn in ('Index', 'Middle', 'Ring', 'Pinky'):
        for i in (1, 2, 3):
            rot(p, f'Right{fn}{i}', lq(X, -34.0 * k))
    rot(p, 'RightThumb1', lq(X, -20.0 * k))
    apply(p)
    upd()
    # legs: feet stay planted while he buckles, then follow the body down
    if t <= LEG_RELEASE[0]:
        pin_feet()
    elif t < LEG_RELEASE[1]:
        s = ease((t - LEG_RELEASE[0]) / (LEG_RELEASE[1] - LEG_RELEASE[0]))
        pin_feet()
        ik = {n: PB[n].matrix_basis.copy() for side in ('Left', 'Right')
              for n in (side + 'UpperLeg', side + 'LowerLeg', side + 'Foot')}
        for n, m in ik.items():
            l0, q0, s0 = m.decompose()
            q1 = p[n][0]
            if q0.dot(q1) < 0:
                q1 = -q1
            PB[n].rotation_quaternion = q0.slerp(q1, s)
            PB[n].location = l0.lerp(p[n][1], s)
        upd()
    # never through the ground: lift the root by any deficit (checked on the
    # evaluated meshes, so it holds for the skinned surface, not just bones)
    if t > 0.85:
        mz = lowest_body_z()
        if mz < 0.0:
            PB['HumanoidRootPart'].location = PB['HumanoidRootPart'].location + \
                REST3['HumanoidRootPart'].inverted() @ Vector((0, 0, -mz + 0.005))
            upd()
    # the staff: carried until release, then topples outward about its foot
    Mh = bone_mat('Staff')
    if f == 0:
        STAFF_FALL.clear()
    if t <= STAFF_REL:
        STAFF_FALL['carried'] = Mh.copy()
        return
    M0 = STAFF_FALL['carried']
    if 'final' not in STAFF_FALL:
        foot = M0 @ STAFF_IMPACT_OFF
        pivot = Vector((foot.x, foot.y, 0.0))
        R = Matrix.Rotation(math.radians(-86.0), 4, Vector((0, 1, 0)))   # top falls to -X
        Mf = Matrix.Translation(pivot) @ R @ Matrix.Translation(-pivot) @ M0
        lift = -float(staff_world_verts(Mf)[:, 2].min()) + 0.01
        STAFF_FALL.update(pivot=pivot, lift=lift)
        STAFF_FALL['final'] = Matrix.Translation((0, 0, lift)) @ Mf
    s = ease_in(min(1.0, (t - STAFF_REL) / 0.55))
    ang = -86.0 * s
    R = Matrix.Rotation(math.radians(ang), 4, Vector((0, 1, 0)))
    piv = STAFF_FALL['pivot']
    M = Matrix.Translation((0, 0, STAFF_FALL['lift'] * s)) @ Matrix.Translation(piv) @ R @ \
        Matrix.Translation(-piv) @ M0
    PB['Staff'].matrix = arm.matrix_world.inverted() @ M
    upd()


# =================================================================== RUN
IDLE0 = idle_pose(0.0)
record('Idle', IDLE_N, True, idle_frame)
record('Walk', WALK_N, True, walk_frame)
record('Hit', HIT_N, False, hit_frame)
record('CursedBolts', BOLT_N, False, bolt_frame)
record('TombEruption', TOMB_N, False, tomb_frame2)
DEATH_KEYS = death_prepare()
record('Death', DEATH_N, False, death_frame)
ANIM['motion'] = {'strideLength': STRIDE, 'nominalSpeed': round(SPEED, 4)}


# =================================================================== CHECKS
def frame_state(clip, f):
    pose_from_basis(BASIS[clip][f])


def feet_world(clip, f):
    frame_state(clip, f)
    return {s: PB[s + 'LowerLeg'].tail.copy() for s in ('Left', 'Right')}


def check_clip(clip, planted_feet=True):
    n = len(BASIS[clip]) - 1
    c = {'frames': n + 1}
    wr, ef_min, ef_max, stz, drift = 0.0, 999.0, 0.0, 9e9, 0.0
    staff_rel = 0.0
    fingers = 0.0
    f0 = feet_world(clip, 0) if planted_feet else None
    for f in range(n + 1):
        frame_state(clip, f)
        wr = max(wr, wrist_deg('Right'))
        ef = elbow_flex('Right')
        ef_min, ef_max = min(ef_min, ef), max(ef_max, ef)
        stz = min(stz, staff_min_z())
        staff_rel = max(staff_rel, math.degrees(PB['Staff'].rotation_quaternion.angle),
                        PB['Staff'].location.length)
        for fn in ('Index', 'Middle', 'Ring', 'Pinky'):
            for i in (1, 2, 3):
                fingers = max(fingers, math.degrees(
                    PB[f'Right{fn}{i}'].rotation_quaternion.angle))
        if planted_feet:
            fw = {s: PB[s + 'LowerLeg'].tail.copy() for s in ('Left', 'Right')}
            drift = max(drift, max((fw[s] - f0[s]).length for s in fw))
    c.update(maxRightWristDeg=round(wr, 2), rightElbowFlexRange=[round(ef_min, 1), round(ef_max, 1)],
             staffLowestZ=round(stz, 3), staffBoneMaxOffsetFromHand=round(staff_rel, 6),
             rightFingerMaxRotationDeg=round(fingers, 4))
    if planted_feet:
        c['plantedFootDriftMax'] = round(drift, 5)
    return c


for clip in ('Idle', 'Hit', 'CursedBolts', 'TombEruption'):
    CHECKS['clips'][clip] = check_clip(clip)
CHECKS['clips']['Walk'] = check_clip('Walk', planted_feet=False)
tz = []
for f in range(TOMB_N + 1):
    frame_state('TombEruption', f)
    tz.append(round(staff_min_z(), 3))
CHECKS['clips']['TombEruption']['staffMinZPerFrame'] = tz
CHECKS['clips']['Death'] = check_clip('Death', planted_feet=False)
# walk: planted-foot slip in the world frame (foot + travel) during stance
slip = 0.0
for side in ('Left', 'Right'):
    prev = None
    for f in range(WALK_N + 1):
        t = f / FPS
        A, planted, _ = foot_track(side, t)
        frame_state('Walk', f)
        pos = PB[side + 'LowerLeg'].tail.copy()
        world = pos + Vector((0, -SPEED * t, 0))
        if planted and prev is not None and prev[1]:
            slip = max(slip, (world - prev[0]).length)
        prev = (world, planted)
CHECKS['clips']['Walk']['plantedFootWorldSlipPerFrameMax'] = round(slip, 6)
CHECKS['clips']['Walk'].update(strideLength=STRIDE, nominalSpeed=round(SPEED, 4), cycle=WALK_T,
                               duty=DUTY)
# death: lowest point over the clip and in the final pose
dz = []
for f in range(0, DEATH_N + 1, 3):
    frame_state('Death', f)
    dz.append(min(lowest_body_z(), staff_min_z()))
frame_state('Death', DEATH_N)
CHECKS['clips']['Death'].update(lowestZOverClip=round(min(dz), 4),
                                finalLowestZ=round(min(lowest_body_z(), staff_min_z()), 4))
# loops close
for clip in ('Idle', 'Walk'):
    a, b = ANIM['clips'][clip]['frames'][0], ANIM['clips'][clip]['frames'][-1]
    CHECKS['clips'][clip]['loopError'] = max(abs(x - y) for n in a['transforms']
                                            for x, y in zip(a['transforms'][n], b['transforms'][n]))
# non-loop clips start/end on the idle start pose
for clip in ('Hit', 'CursedBolts', 'TombEruption'):
    a = ANIM['clips']['Idle']['frames'][0]['transforms']
    for key, fr in (('startError', 0), ('endError', -1)):
        b = ANIM['clips'][clip]['frames'][fr]['transforms']
        CHECKS['clips'][clip][key] = max(abs(x - y) for n in a for x, y in zip(a[n], b[n]))
b = ANIM['clips']['Death']['frames'][0]['transforms']
a = ANIM['clips']['Idle']['frames'][0]['transforms']
CHECKS['clips']['Death']['startError'] = max(abs(x - y) for n in a for x, y in zip(a[n], b[n]))
log('checks', json.dumps(CHECKS)[:900])


# =================================================================== GAME DATA
def studio(v):
    return [round(-v[0], 4), round(v[2], 4), round(v[1], 4)]


def r4(v):
    return [round(c, 4) for c in v]


frame_state('CursedBolts', round(BOLT_T['impact'] * FPS))
O = staff_point(BOLT_OFF)
aim_target = Vector((O.x * 0.3, -16.0, 3.5))
D = (aim_target - O).normalized()
fan = []
for yaw in (-15.0, 0.0, 15.0):
    fan.append(r4(Matrix.Rotation(math.radians(yaw), 3, 'Z') @ D))
frame_state('TombEruption', round(TOMB_IMPACT * FPS))
Fi = staff_point(STAFF_IMPACT_OFF)
horiz = [math.hypot((o.matrix_world @ v.co).x, (o.matrix_world @ v.co).y)
         for s, o in SECTIONS.items() if s != 'Staff' for v in o.data.vertices]
GD = {'attacks': {
    'CursedBolts': {
        'duration': round(BOLT_N / FPS, 4), 'warnStart': 0.30, 'chargeStart': BOLT_T['charge_start'],
        'impact': round(BOLT_T['impact'], 4), 'activeEnd': round(BOLT_T['impact'], 4), 'recoveryEnd': round(BOLT_N / FPS, 4),
        'boltCount': 3, 'fanSpreadDegrees': 15.0,
        'points': {'BoltOrigin': {'bone': 'Staff', 'offset': r4(BOLT_OFF), 'rootAtImpact': r4(O),
                                  'rootAtImpactStudio': studio(O)}},
        'directionAtImpact': r4(D), 'directionAtImpactStudio': studio(D),
        'fanDirectionsAtImpact': fan, 'fanDirectionsAtImpactStudio': [studio(v) for v in fan],
        'note': 'Aim: the direction points from BoltOrigin toward a target 16 studs ahead at '
                'chest height; the game re-aims at the real target at release.'},
    'TombEruption': {
        'duration': round(TOMB_N / FPS, 4), 'warnStart': 0.35, 'impact': round(TOMB_IMPACT, 4),
        'activeEnd': 1.60, 'channelStart': round(TOMB_IMPACT, 4), 'channelEnd': 1.60,
        'recoveryEnd': 2.30,
        'points': {'StaffImpact': {'bone': 'Staff', 'offset': r4(STAFF_IMPACT_OFF),
                                   'rootAtImpact': r4(Fi), 'rootAtImpactStudio': studio(Fi)}},
        'note': 'Hieroglyph circles open under players during impact..activeEnd (channel).'}},
    'rootHeight': round(arm.data.bones['HumanoidRootPart'].head_local.z, 4),
    'height': None,
    'footprintRadius': round(max(horiz), 3)}
# height from the evaluated rest mesh
mods(True)
for pb in PB:
    pb.rotation_quaternion = Quaternion()
    pb.location = (0, 0, 0)
upd()
top = 0.0
dg = bpy.context.evaluated_depsgraph_get()
for o in SECTIONS.values():
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    top = max(top, max((oe.matrix_world @ v.co).z for v in me.vertices))
    oe.to_mesh_clear()
GD['height'] = round(top, 4)
(GAME / 'AnimationData.json').write_text(json.dumps(ANIM, separators=(',', ':')))
(GAME / 'BossGameData.json').write_text(json.dumps(GD, indent=2))
CHECKS['boltOriginStaffLocal'] = r4(BOLT_OFF)
CHECKS['staffImpactStaffLocal'] = r4(STAFF_IMPACT_OFF)
CHECKS['solver'] = {'CursedBolts': {k: round(v, 2) for k, v in BOLT_PRM.items()},
                    'TombLift': {k: (round(v, 2) if isinstance(v, float) else v)
                                 for k, v in TOMB_LIFT_PRM.items()},
                    'TombHit': {k: (round(v, 2) if isinstance(v, float) else v)
                                for k, v in TOMB_HIT_PRM.items()}}
CHECKS['tombImpactFootZ'] = round(Fi.z, 4)
(GAME / 'GameMotionChecks.json').write_text(json.dumps(CHECKS, indent=2, default=str))
log('wrote AnimationData / BossGameData')

# =================================================================== ACTIONS -> blend
for clip, bases in BASIS.items():
    old = bpy.data.actions.get(clip)
    if old:
        bpy.data.actions.remove(old)
    act = bpy.data.actions.new(clip)
    act.use_fake_user = True
    bind(act)
    for f, b in enumerate(bases):
        for n, m in b.items():
            loc, q, sc = m.decompose()
            PB[n].rotation_quaternion = q
            PB[n].location = loc
            PB[n].keyframe_insert('rotation_quaternion', frame=f + 1)
            PB[n].keyframe_insert('location', frame=f + 1)
    act.frame_range = (1, len(bases))
    if clip == 'CursedBolts':
        act.pose_markers.new('Release').frame = 1 + round(BOLT_T['impact'] * FPS)
    if clip == 'TombEruption':
        act.pose_markers.new('Impact').frame = 1 + round(TOMB_IMPACT * FPS)
bind(bpy.data.actions['ReferencePose'])
scene.frame_set(1)
mods(True)
bpy.ops.wm.save_as_mainfile(filepath=str(HERE / 'Pharaoh.blend'), compress=True)
log('saved blend with game clips')

# =================================================================== PREVIEWS
cam = scene.camera
scene.render.engine = 'BLENDER_WORKBENCH'
sh = scene.display.shading
sh.light = 'STUDIO'
sh.color_type = 'TEXTURE'
sh.show_shadows = True
sh.background_type = 'WORLD'
scene.display.render_aa = '8'
scene.view_settings.view_transform = 'Standard'
cam.data.type = 'ORTHO'
cam.data.ortho_scale = 19.0
cam.location = Vector((20, -26, 11))
cam.rotation_euler = (Vector((-1.2, -1.5, 6.2)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.render.resolution_x, scene.render.resolution_y = 300, 360
scene.render.resolution_percentage = 100
tiles = []
PICK = {'Idle': [0, 18, 36, 54], 'Walk': [0, 9, 18, 27], 'Hit': [0, 3, 6, 11],
        'Death': [0, 10, 22, 34, 44, 54], 'CursedBolts': [0, 11, 20, 25, 29, 51],
        'TombEruption': [0, 14, 19, 30, 42, 60]}
for clip, frames in PICK.items():
    bind(bpy.data.actions[clip])
    for f in frames:
        scene.frame_set(f + 1)
        pth = WORK / f'gc_{clip}_{f:03d}.png'
        scene.render.filepath = str(pth)
        bpy.ops.render.render(write_still=True)
        tiles.append((clip, pth))
rows = []
for clip in PICK:
    rows.append([p for c, p in tiles if c == clip])
cols = max(len(r) for r in rows)
w, h = 300, 360
sheet = np.zeros((len(rows) * h, cols * w, 4), np.float32)
sheet[..., :3] = (0.10, 0.11, 0.13)
sheet[..., 3] = 1
for ri, r in enumerate(rows):
    for ci, p in enumerate(r):
        im = bpy.data.images.load(str(p))
        px = np.array(im.pixels[:], np.float32).reshape(h, w, 4)
        y0 = (len(rows) - 1 - ri) * h
        sheet[y0:y0 + h, ci * w:(ci + 1) * w] = px
        bpy.data.images.remove(im)
img = bpy.data.images.new('GameClips', cols * w, len(rows) * h, alpha=False)
img.pixels.foreach_set(sheet.ravel())
img.filepath_raw = str(HERE / 'previews' / 'GameClips.png')
img.file_format = 'PNG'
img.save()
bpy.data.images.remove(img)
log('GameClips.png')
# low-res mp4 per new attack
scene.render.resolution_x, scene.render.resolution_y = 480, 540
for clip in ('CursedBolts', 'TombEruption'):
    act = bpy.data.actions[clip]
    bind(act)
    scene.frame_start, scene.frame_end = 1, int(act.frame_range[1])
    ims = scene.render.image_settings
    try:
        ims.media_type = 'VIDEO'
    except Exception:
        pass
    ims.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'
    scene.render.filepath = str(HERE / 'previews' / f'{clip}.mp4')
    bpy.ops.render.render(animation=True)
    log('video', clip)

export_studio_fbx()
log('GAME_PACKAGE_DONE')
