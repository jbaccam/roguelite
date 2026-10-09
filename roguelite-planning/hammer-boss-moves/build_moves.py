"""Hammer boss moves: the generator.

  blender -b --factory-startup --python build_moves.py               all: clips, checks, exports, actions, previews
  blender -b --factory-startup --python build_moves.py -- extract    dump the rest rig + meshes to .cache/
  blender -b --factory-startup --python build_moves.py -- data       clips, checks, exports, actions (no renders)
  blender -b --factory-startup --python build_moves.py -- render     previews only
  python build_moves.py post                                          labels and mp4s (run by 'all')

(blender = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")

Works on the COPY ./HammerBoss.blend (never the original in hammer-boss/finished). The motion maths
is pure numpy in hm_motion.py / hm_legacy.py / hm_clips.py / hm_checks.py; this file reads the model,
supplies the exact mesh-against-mesh BVH test (mathutils.bvhtree), writes the hand-off files, keys
Blender actions (HB_<clip>) into the copy, and renders the Eevee previews (ffmpeg H.264).

Clips (exports/game/PartPoses.json):
  Idle, Walk     24 fps, the 2026-10-04 sample's motion on the original carry grip (hm_clips.py)
  Slam, Swing, Hit, Death, ChargeStart, ChargeRun
                 60 fps bakes of the ORIGINAL clips exactly as BossMotion.sample showed them
                 (constrainArms included; hm_legacy.Baker, two in-between intervals repaired)
  Spin           60 fps, the original Spin with its active revolution played twice (hm_legacy.DoubleSpin)
  SwingSpin      Swing -> double Spin, SpinSlam double Spin -> Slam (hm_legacy.Combo crossfades)
"""
import json
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
CACHE = HERE / '.cache'
BLEND = HERE / 'HammerBoss.blend'
GAME = HERE / 'exports' / 'game'
PREVIEWS = HERE / 'previews'
FRAMES = CACHE / 'frames'
PLANNING = HERE.parent
MANIFEST = PLANNING / 'hammer-boss' / 'finished' / 'studio-asset-manifest.json'
LEGACY_DATA = PLANNING / 'hammer-boss' / 'finished' / 'BossData.json'
CHARGE_RUNTIME = PLANNING / 'hammer-boss' / 'charge_runtime.py'
BOSSES = PLANNING / 'studio-prototype' / 'combat' / 'bosses'
RECEIPT = BOSSES / 'receipts' / 'hammer-old-receipt.json'
PARTS = ['LowerTorso', 'UpperTorso', 'Head', 'RightUpperArm', 'RightLowerArm', 'RightHand', 'LeftUpperArm',
         'LeftLowerArm', 'LeftHand', 'RightUpperLeg', 'RightLowerLeg', 'RightFoot', 'LeftUpperLeg', 'LeftLowerLeg',
         'LeftFoot', 'Hammer']
FPS = 60
PREVIEW_HZ = 60
GAME_SCALE = 1.5                  # MapBossDefs scale (2026-10-09); everything here is authored at 1.0
LOOPS = {'Idle', 'Walk', 'ChargeRun'}
ORIGINAL = ['Slam', 'Swing', 'Hit', 'Death', 'ChargeStart', 'ChargeRun']
# combo: (A, B, cutA, cutB, fade) in 1/60 s. Chosen by a pose-distance search over A's recovery and
# B's wind-up that keeps the hammer head >= 5 studs from its carry spot (never through idle) and the
# crossfade no faster than the attacks' own sweeps (README "Combos").
COMBOS = {'SwingSpin': ('Swing', 'Spin', 78, 15, 12), 'SpinSlam': ('Spin', 'Slam', 96, 7, 12)}
CLIPS = ['Idle', 'Walk', 'Slam', 'Swing', 'Spin', 'SwingSpin', 'SpinSlam', 'Hit', 'Death', 'ChargeStart', 'ChargeRun']
ATTACKS = ['Slam', 'Swing', 'Spin', 'SwingSpin', 'SpinSlam']
SOURCES = {'Slam': ['Slam'], 'Swing': ['Swing'], 'Spin': ['Spin'], 'SwingSpin': ['Swing', 'Spin'],
           'SpinSlam': ['Spin', 'Slam'], 'Hit': ['Hit'], 'Death': ['Death'], 'ChargeStart': ['ChargeStart'],
           'ChargeRun': ['ChargeRun']}
WAVE = {'length': 26.0, 'bursts': 9, 'gap': 0.05, 'pop': 0.08, 'hold': 0.14, 'crumble': 0.38}

try:
    import bpy
    from mathutils import Matrix
    from mathutils.bvhtree import BVHTree
except ImportError:            # the 'post' stage runs under system Python
    bpy = None


def stage_arg():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    return a[0] if a else 'all'


def log(*a):
    print('[moves]', *a, flush=True)


def r(x, n=6):
    return round(float(x), n) + 0.0


# ================================================================== extract (Blender)
def extract():
    """Rest rig and meshes, exactly as stored in the .blend (rest position, world space)."""
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    rig = bpy.data.objects['HammerBoss_Rig']
    rig.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    bones = {b.name: {'head': list(b.head_local), 'tail': list(b.tail_local),
                      'parent': b.parent.name if b.parent else None} for b in rig.data.bones}
    parts, arrays = {}, {}
    for name in PARTS:
        ob = bpy.data.objects[name]
        me = ob.data
        mw = np.array(ob.matrix_world)
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        v = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
        me.calc_loop_triangles()
        tri = np.empty(len(me.loop_triangles) * 3, dtype=np.int32)
        me.loop_triangles.foreach_get('vertices', tri)
        arrays[name + '_v'] = v
        arrays[name + '_t'] = tri.reshape(-1, 3)
        lo, hi = v.min(0), v.max(0)
        parts[name] = {'center': list((lo + hi) / 2), 'min': list(lo), 'max': list(hi), 'verts': len(v),
                       'tris': int(len(tri) // 3)}
    rig.data.pose_position = 'POSE'
    CACHE.mkdir(exist_ok=True)
    (CACHE / 'rig.json').write_text(json.dumps({'bones': bones, 'parts': parts}, indent=1))
    np.savez_compressed(CACHE / 'meshes.npz', **arrays)
    log('extract ok', len(bones), 'bones', len(parts), 'parts')


def load():
    import hm_motion as HM
    import hm_clips as CL
    data = json.loads((CACHE / 'rig.json').read_text())
    meshes = dict(np.load(CACHE / 'meshes.npz'))
    rig = HM.Rig(data)
    for s in HM.SIDES:
        CL.cuff_points(rig, s, meshes)
    return rig, meshes


# ================================================================== clips and timing
def build_clips(rig):
    import hm_clips as CL
    import hm_legacy as LG
    t0 = time.time()
    L = LG.Legacy()
    B = LG.Baker(rig, L)
    carry = CL.Carry(rig, L)
    src = {n: LG.Single(B, n) for n in ORIGINAL}
    src['Spin'] = LG.DoubleSpin(B)
    for name, (a, b, ca, cb, fd) in COMBOS.items():
        src[name] = LG.Combo(B, src[a], src[b], ca / FPS, cb / FPS, fd / FPS)
    clips = {'Idle': CL.idle(rig, carry), 'Walk': CL.walk(rig, carry)}
    for name in CLIPS[2:]:
        clips[name] = CL.Clip(name, FPS, name in LOOPS, LG.sample_frames(src[name], FPS), {'source': src[name]})
    log('clips built in %.1fs' % (time.time() - t0), {k: (len(c.frames), c.fps) for k, c in clips.items()})
    log('repaired legacy intervals', list(B.repaired.values()))
    return {n: clips[n] for n in CLIPS}, src, B, carry


def attack_phases(src):
    """Per attack clip: its hits in order as (label, impact, activeEnd), seconds from clip start."""
    import hm_legacy as LG
    A = LG.ATTACKS
    sw, sp, sl = A['Swing'], A['Spin'], A['Slam']
    revs = [('spin 1', sp['active'], sp['finish']), ('spin 2', sp['finish'], sp['finish'] + LG.REV)]
    slam = [('slam circle', sl['active'], sl['active']), ('rubble wave', sl['active'], sl['active'])]
    swing = [('swing', sw['active'], sw['finish'])]
    sh = lambda ph, d: [(n, a + d, b + d) for n, a, b in ph]
    return {'Slam': slam, 'Swing': swing, 'Spin': revs,
            'SwingSpin': swing + sh(revs, src['SwingSpin'].shift),
            'SpinSlam': revs + sh(slam, src['SpinSlam'].shift)}


# ================================================================== exact mesh overlap (Blender BVH)
def bvh_overlap(rig, meshes):
    """overlap(P) -> {part: overlapping triangle pairs} for the hammer against every body section
    except the two fists, using each section's BVH in its own rest frame and the hammer moved into it."""
    import hm_motion as HM
    trees = {}
    for p in PARTS:
        if p in ('Hammer', 'RightHand', 'LeftHand'):
            continue
        V, T = meshes[p + '_v'], meshes[p + '_t']
        trees[p] = BVHTree.FromPolygons([tuple(v) for v in V], [tuple(t) for t in T], all_triangles=True)
    HV, HT = meshes['Hammer_v'], [tuple(t) for t in meshes['Hammer_t']]

    def overlap(P):
        out = {}
        for p, tree in trees.items():
            Q = HM.rinv(P[p]) @ P['Hammer']
            hv = HV @ Q[:3, :3].T + Q[:3, 3]
            pv = meshes[p + '_v']
            if (hv.min(0) > pv.max(0)).any() or (hv.max(0) < pv.min(0)).any():
                continue
            ht = BVHTree.FromPolygons([tuple(v) for v in hv], HT, all_triangles=True)
            n = len(tree.overlap(ht))
            if n:
                out[p] = n
        return out
    return overlap


# ================================================================== exports
def studio12(rig, P, part):
    import hm_motion as HM
    return [round(float(x), 7) + 0.0 for x in HM.studio_pose(rig, P, part)]


def motion_data(clips):
    import hm_legacy as LG
    w = clips['Walk'].meta
    L = LG.Legacy()
    charge = L.d['chargeSpeed'] * L.clips['ChargeRun']['duration']      # 16 studs per clip second (planted feet)
    return {'strideLength': r(w['strideLength'], 4), 'nominalSpeed': r(w['nominalSpeed'], 4),
            'walkCycle': r(w['cycle'], 4), 'chargeStrideLength': r(charge, 4)}


def partposes(rig, clips):
    out = {'fps': 24, 'rootHeight': 4.45, 'parts': PARTS,
           'coordinateSpace': 'each part CFrame relative to HumanoidRootPart, Studio axes, template scale 1.0, '
                              '[x,y,z,R00,R01,R02,R10,R11,R12,R20,R21,R22] (CFrame:GetComponents order)',
           'clips': {}}
    for name, c in clips.items():
        frames = [{'time': r(k / c.fps), 'poses': {p: studio12(rig, P, p) for p in PARTS}} for k, P in enumerate(c.frames)]
        out['clips'][name] = {'duration': r(c.duration), 'loop': c.loop, 'fps': c.fps, 'frames': frames}
    out['motion'] = dict(motion_data(clips), note=(
        'Template scale 1.0. Walk: strideLength studs per cycle (the runtime advances it by ground covered), '
        'nominalSpeed its authored speed. ChargeRun: chargeStrideLength studs per cycle (planted feet move '
        'back at 16 studs per clip second). The game scales the model by 1.5.'))
    return out


def gamedata(rig, clips, src, phases, meshes):
    import hm_motion as HM
    pts = {'HammerFace': rig.HO.copy(),                                   # legacy head point: BossMotion.head
           'HammerGrip': rig.HO + rig.HA * ((2.72 + 8.05) / 2)}           # haft axis, midway between the grips
    c = rig.center['Hammer']
    offsets = {n: [r(v, 5) for v in HM.C_STUDIO @ (p - c)] for n, p in pts.items()}

    def points(name, t):
        P = src[name].pose(t)
        out = {}
        for n, p in pts.items():
            w = HM.xf(P['Hammer'], p)                 # ground frame (z up from the soles), Blender axes
            out[n] = {'bone': 'Hammer', 'part': 'Hammer', 'offset': offsets[n],
                      'rootAtImpactStudio': [r(v, 5) for v in HM.C_STUDIO @ w]}
        return out

    attacks = {}
    for name in ATTACKS:
        ph = phases[name]
        d = clips[name].duration
        a = {'clip': name, 'fps': FPS, 'duration': r(d), 'warnStart': 0.0, 'impact': r(ph[0][1]),
             'activeEnd': r(ph[-1][2]), 'recoveryEnd': r(d), 'points': points(name, ph[0][1])}
        if len(ph) > 1:
            a['phases'] = [{'label': n, 'warnStart': 0.0, 'impact': r(i), 'activeEnd': r(e), 'points': points(name, i)}
                           for n, i, e in ph]
        attacks[name] = a
    body = np.concatenate([meshes[p + '_v'] for p in PARTS if p != 'Hammer'])
    height = float(max(meshes[p + '_v'][:, 2].max() for p in PARTS))
    foot = float(np.sqrt((body[:, :2] ** 2).sum(1)).max())
    return {
        'attacks': attacks,
        'rootHeight': 4.45, 'bodyCentreHeight': 4.45, 'height': r(height, 4), 'footprintRadius': r(foot, 4),
        'groundOffset': 0.0, 'authoredScale': 1.0,
        'motion': {k: v for k, v in motion_data(clips).items() if k != 'walkCycle'},
        'notes': ('Authored at template scale 1.0; the game scales the model by 1.5 (MapBossDefs). Times in seconds '
                  'from clip start; every clip is 60 fps except Idle and Walk (24). Every warning starts at commit '
                  '(warnStart 0). phases: the hits in order (Slam: slam circle, rubble wave; Spin: one per '
                  'revolution; SwingSpin: swing, spin 1, spin 2; SpinSlam: spin 1, spin 2, slam circle, rubble '
                  'wave); the top-level impact is the first phase\'s, activeEnd the last phase\'s. A rubble wave '
                  'phase has its slam circle\'s times. Points: HammerFace is the legacy head point '
                  '(BossMotion.head: hammerHeadRest, the head centre), HammerGrip the haft axis midway between '
                  'the carry grips (2.72 / 8.05 along the haft), both as offsets in the Hammer part\'s own Studio '
                  'space; rootAtImpactStudio is that point at the (phase) impact, Studio axes, y up from the soles. '
                  'footprintRadius: body sections only. The intro sky-drop and the Charge finish play the Slam '
                  '(no IntroLand, Roar or ChargeSlam clips).')}


# ================================================================== proofs
def mat12(v):
    m = np.eye(4)
    m[:3, 3] = v[:3]
    m[:3, :3] = np.asarray(v[3:12], float).reshape(3, 3)
    return m


def box(size):
    h = np.asarray(size, float) / 2
    return np.array([[x * h[0], y * h[1], z * h[2], 1.0] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]).T


def axis_proof(rig):
    """The template rest pose (all identities) through studio_pose against the template's own part
    CFrames relative to its root (studio-asset-manifest.json): the Blender -> Studio mapping."""
    import hm_motion as HM
    man = json.loads(MANIFEST.read_text())
    cf = {e['properties']['Name']['v']: e['properties']['CFrame']['v'] for e in man if e['class'] in ('Part', 'MeshPart')}
    root = np.array(cf['HumanoidRootPart'], float)
    rest = {p: np.eye(4) for p in PARTS}
    worst_p = worst_r = 0.0
    for p in PARTS:
        m = np.array(cf[p], float)
        got = np.array(HM.studio_pose(rig, rest, p))
        worst_p = max(worst_p, float(np.abs(got[:3] - (m[:3] - root[:3])).max()))
        worst_r = max(worst_r, float(np.abs(got[3:] - m[3:]).max()))
    return {'maxPositionError': worst_p, 'maxRotationError': worst_r, 'limit': 0.001,
            'pass': bool(worst_p <= 0.001 and worst_r <= 0.001),
            'source': 'hammer-boss/finished/studio-asset-manifest.json (template HammerBoss_NPC as installed)'}


def legacy_proof(rig, clips, pp, baker):
    """The exported 60 fps frames (PartPoses.json numbers) against BossMotion.sample at the same time,
    as part CFrames (legacy delta * BossRest from the template receipt), compared on each part's box
    corners like partposes_to_motor6d. Authored frames: times on the original's own frames.
    In-betweens: every other baked frame, except the repaired intervals and the double Spin's
    0.1 s seam fade (listed)."""
    import hm_legacy as LG
    rec = json.loads(RECEIPT.read_text())
    rest = {p['name']: mat12(p['cframe']) for p in rec['parts']}
    size = {p['name']: box(p['size']) for p in rec['parts']}
    L = baker.L
    sp = LG.ATTACKS['Spin']
    out = {'authoredFrames': 0, 'maxErrorAuthored': 0.0, 'inBetweenFrames': 0, 'maxErrorInBetween': 0.0,
           'perClip': {}, 'repairedFrames': [], 'seamFadeFrames': 0}
    for name in ORIGINAL + ['Spin']:
        c = L.clips[name]
        worst_a = worst_b = 0.0
        for k, fr in enumerate(pp['clips'][name]['frames']):
            t = k / FPS
            if name == 'Spin':
                if t <= sp['finish'] + 1e-9:
                    ts = t
                elif t >= sp['finish'] + LG.SEAM_FADE - 1e-9:
                    ts = t - LG.REV
                else:
                    out['seamFadeFrames'] += 1
                    continue
            else:
                ts = t
            f = min(max(ts * c['fps'], 0.0), c['last'])
            authored = abs(f - round(f)) < 1e-6
            i = min(int(math.floor(f)), c['last'] - 1)
            if not authored and name != 'Death' and (name, i) in baker.repaired:
                out['repairedFrames'].append({'clip': name, 'frame': k, 'sourceTime': r(ts, 4)})
                continue
            P = L.sample(name, ts)
            err = 0.0
            for p in PARTS:
                want = P[p] @ rest[p]
                got = mat12(fr['poses'][p])
                err = max(err, float(np.abs((got - want) @ size[p]).max()))
            if authored:
                worst_a = max(worst_a, err)
                out['authoredFrames'] += 1
            else:
                worst_b = max(worst_b, err)
                out['inBetweenFrames'] += 1
        out['perClip'][name] = {'authored': worst_a, 'inBetween': worst_b}
        out['maxErrorAuthored'] = max(out['maxErrorAuthored'], worst_a)
        out['maxErrorInBetween'] = max(out['maxErrorInBetween'], worst_b)
    out['limit'] = 1e-4
    out['pass'] = bool(out['maxErrorAuthored'] < 1e-4 and out['maxErrorInBetween'] < 1e-4)
    return out


def port_crosscheck(baker):
    """hm_legacy.Legacy against hammer-boss/charge_runtime.py (an independent mathutils port of
    BossMotion.sample used to validate the charge in 2026-09/10), at 60 fps over every clip: the
    frame blend (rblend vs Legacy.blended) and the full sample after constrainArms (rsample vs
    Legacy.sample). That port leaves out Death's plain per-part lerp and the Swing/Spin head lift;
    the lift is zero in this data (the clips already hold the head at 4.6), and Death is compared on
    its authored frames only. mathutils works in float32, so the reference carries ~1e-5 rounding,
    which the arm solve amplifies on the nearly straight left arm (elbow height ~ sqrt(l1^2 - x^2))."""
    L = baker.L
    d = json.loads(LEGACY_DATA.read_text())
    g = {'d': d}
    exec(compile(CHARGE_RUNTIME.read_text(), str(CHARGE_RUNTIME), 'exec'), g)
    pre = post = 0.0
    n, at = 0, None
    for name, c in L.clips.items():
        for k in range(int(round(c['duration'] * FPS)) + 1):
            t = k / FPS
            f = min(max(t * c['fps'], 0.0), c['last'])
            if name == 'Death' and abs(f - round(f)) > 1e-6:
                continue
            i = int(math.floor(f))
            Bb = g['rblend'](g['FR'][name][i], g['FR'][name][min(i + 1, c['last'])], f % 1.0)
            A = L.blended(name, t)
            pre = max(pre, max(float(np.abs(A[p] - np.array(Bb[p])).max()) for p in A))
            A = L.sample(name, t)
            Bm = g['rsample'](name, t)
            e = max(float(np.abs(A[p] - np.array(Bm[p])).max()) for p in A)
            if e > post:
                post, at = e, '%s t=%.4f' % (name, t)
            n += 1
    return {'samples': n, 'maxDifferenceFrameBlend': pre, 'maxDifferenceAfterConstrainArms': post, 'worstAt': at,
            'pass': bool(pre < 1e-3 and post < 5e-3), 'limits': [1e-3, 5e-3],
            'reference': 'hammer-boss/charge_runtime.py rblend / rsample (mathutils, float32)'}


def studio_convert(pp):
    sys.path.insert(0, str(BOSSES))
    import partposes_to_motor6d as C
    receipt = json.loads(RECEIPT.read_text())
    studio, data, checks = C.convert(pp, receipt, pp.get('motion'), pp.get('rootHeight'))
    return {k: checks[k] for k in ('jointCount', 'clipCount', 'frameCount', 'maxCentreError', 'maxCornerError',
                                   'worstAt', 'limit', 'passed', 'rootHeight')} | {
        'clips': {n: {'frames': len(c['frames']), 'fps': c.get('fps'), 'loop': c['loop'], 'duration': c['duration']}
                  for n, c in studio['clips'].items()},
        'receipt': 'studio-prototype/combat/bosses/receipts/hammer-old-receipt.json', 'wroteFiles': False}


# ================================================================== checks
def pose_points(P, meshes, parts=None, step=5):
    import hm_motion as HM
    return np.concatenate([HM.xf(P[p], meshes[p + '_v'][::step]) for p in (parts or PARTS)])


def pose_distance(P, Q, meshes, parts=None):
    return float(np.linalg.norm(pose_points(P, meshes, parts) - pose_points(Q, meshes, parts), axis=1).max())


def run_checks(rig, meshes, clips, src, baker, carry, overlap):
    import hm_motion as HM
    import hm_checks as HC
    import hm_legacy as LG
    Lm = HC.LIMITS
    t0 = time.time()
    rest = {p: np.eye(4) for p in PARTS}
    rest_cuff = HC.hammer_solid_depth(rig, rest, meshes)

    def contact_bad(P):
        """Hammer vs body: no overlap except the template's own right-forearm cuff contact (in its
        rest pose), allowed up to that depth + 0.05."""
        pairs = overlap(P)
        if not pairs:
            return {}
        depth = HC.hammer_solid_depth(rig, P, meshes)
        return {p: n for p, n in pairs.items() if not (rest_cuff.get(p, 0) > 0 and depth.get(p, 0) <= rest_cuff[p] + 0.05)}

    report = {'limits': Lm, 'definitions': HC.__doc__.split('Definitions')[1].strip(), 'clips': {}, 'between': {},
              'seams': {}, 'legacyReference': {}}
    summary = []

    def add(check, clip, value, limit, ok, where=None, exception=None):
        row = {'check': check, 'clip': clip, 'value': None if value is None else r(value, 4), 'limit': limit, 'pass': bool(ok)}
        if where is not None:
            row['at'] = where
        if exception and not ok:
            row['exception'] = exception
        summary.append(row)

    # ---- what the legacy client showed (BossMotion.sample at 60 Hz over each original) and the carry
    L = baker.L
    ref = {}
    for name in ['Slam', 'Swing', 'Spin', 'Hit', 'Death', 'ChargeStart', 'ChargeRun']:
        c = L.clips[name]
        fr = [L.to_D(L.sample(name, k / FPS)) for k in range(int(round(c['duration'] * FPS)) + 1)]
        res = HC.check_clip(rig, name, fr, FPS, False, meshes)
        res['worst']['bvhFrames'] = sum(1 for P in fr if contact_bad(P))
        res['worst']['cuffDepth'] = max(HC.hammer_solid_depth(rig, P, meshes, ['RightLowerArm'])['RightLowerArm'] for P in fr)
        res['worst']['gripBetween'] = max(baker.interval_gaps(name))
        ref[name] = res['worst']
    kres = HC.check_clip(rig, 'carry', [carry.K, carry.K], 24, False, meshes)
    ref['carry'] = kres['worst']
    ref['carry']['bvhFrames'] = 0
    report['legacyReference'] = {n: {k: r(v, 4) for k, v in w.items()} for n, w in ref.items()}
    log('legacy reference done %.1fs' % (time.time() - t0))

    def exc(name, key, value, mode='max'):
        """The value is the original's (or the carry pose's) own: the legacy authored frames reach it."""
        srcs = SOURCES.get(name) or ['carry']
        vals = [ref[s][key] for s in srcs if key in ref[s]]
        if not vals:
            return None
        rv = max(vals) if mode == 'max' else min(vals)
        if key == 'bvhFrames':
            ok = rv > 0
            tol = 0
        else:
            tol = max(0.02 * abs(rv), {'ground': 0.005, 'shaftCore': 0.05}.get(key, 0.5))
            ok = value <= rv + tol if mode == 'max' else value >= rv - tol
        what = 'as the legacy client showed it' if name in SOURCES else 'the original carry pose'
        return '%s: %.3f (%s)' % (what, rv, '/'.join(srcs)) if ok else None

    comp = {n: HC.as_clip(rig, c.frames, c.fps, c.loop) for n, c in clips.items()}
    for name, c in clips.items():
        res = HC.check_clip(rig, name, c.frames, c.fps, c.loop, meshes, planted=c.meta.get('planted'),
                            root_motion=c.meta.get('root_motion'))
        samples = HC.resample(rig, comp[name], 120)
        btw = HC.check_between(rig, samples, meshes)
        bad = []
        for lab, P in samples:
            b = contact_bad(P)
            if b:
                bad.append({'at': lab, 'pairs': b})
        res['hammerOverlap120Hz'] = {'badSamples': len(bad), 'first': bad[:12]}
        report['clips'][name] = res
        report['between'][name] = btw
        w, wh, bw = res['worst'], res['where'], btw['worst']
        death = name == 'Death'
        add('elbow flex min (deg)', name, min(w['elbowMin'], bw['elbowMin']), Lm['elbowFlex'][0],
            min(w['elbowMin'], bw['elbowMin']) >= Lm['elbowFlex'][0] - 0.01, wh.get('elbowMin'), exc(name, 'elbowMin', w['elbowMin'], 'min'))
        add('elbow flex max (deg)', name, max(w['elbowMax'], bw['elbowMax']), Lm['elbowFlex'][1],
            max(w['elbowMax'], bw['elbowMax']) <= Lm['elbowFlex'][1] + 0.01, wh.get('elbowMax'), exc(name, 'elbowMax', w['elbowMax']))
        v = max(w['hingeOffAxis'], bw['hingeOffAxis'])
        add('elbow off-axis, frames + 120 Hz (deg)', name, v, Lm['hingeOffAxis'], v <= Lm['hingeOffAxis'], None, exc(name, 'hingeOffAxis', v))
        v = max(w['kneeOffAxis'], bw['kneeOffAxis'])
        add('knee off-axis, frames + 120 Hz (deg)', name, v, Lm['hingeOffAxis'], v <= Lm['hingeOffAxis'], None, exc(name, 'kneeOffAxis', v))
        add('knee bends forward only: min hinge (deg)', name, w['kneeMin'], 0.0, w['kneeMin'] >= -0.01, wh.get('kneeMin'), exc(name, 'kneeMin', w['kneeMin'], 'min'))
        add('knee max (deg)', name, w['kneeMax'], 150.0, w['kneeMax'] <= 150.0, None, exc(name, 'kneeMax', w['kneeMax']))
        e = exc(name, 'wristBend', w['wristBend'])
        if name == 'Walk' and not e:
            e = ('the run holds the fists in the carry grip (the carry pose itself: %.1f); chosen over rolling the '
                 'fists so the Walk -> attack blend keeps the grip' % ref['carry']['wristBend'])
        add('wrist bend (deg)', name, w['wristBend'], Lm['wristBend'], w['wristBend'] <= Lm['wristBend'], wh.get('wristBend'), e)
        add('wrist twist (deg)', name, w['wristTwist'], Lm['wristTwist'], w['wristTwist'] <= Lm['wristTwist'], wh.get('wristTwist'), exc(name, 'wristTwist', w['wristTwist']))
        add('shoulder swivel (deg)', name, w['swivel'], Lm['swivel'], w['swivel'] <= Lm['swivel'], wh.get('swivel'), exc(name, 'swivel', w['swivel']))
        sstep = Lm['spikeStep'] * (24.0 / c.fps)          # the 24 fps limit per 1/24 s, scaled to the clip's frame
        add('swivel step per frame (deg)', name, w['swivelStep'], round(sstep, 2), w['swivelStep'] <= sstep, wh.get('swivelStep'),
            exc(name, 'swivelStep', w['swivelStep']))
        add('spine step per frame (deg)', name, w['spineStep'], round(sstep, 2), w['spineStep'] <= sstep, wh.get('spineStep'),
            exc(name, 'spineStep', w['spineStep']))
        if not death:
            kept = max(g for s_ in SOURCES.get(name, []) for g in baker.interval_gaps(s_) if g <= LG.Baker.REPAIR) if name in SOURCES else 0
            e = None
            if name in SOURCES and w['grip'] <= LG.Baker.REPAIR:
                e = "a legacy in-between frame (the original's own gap, kept: up to %.3f; accepted up to %.2f)" % (kept, LG.Baker.REPAIR)
            add('grip: haft through both fist holes, frames (studs)', name, w['grip'], Lm['grip'], w['grip'] <= Lm['grip'], wh.get('grip'), e)
            gb = bw['grip']
            e = None
            if gb > Lm['gripBetween'] and name in SOURCES and gb <= LG.Baker.REPAIR:
                e = "the original's own in-between gap (kept up to %.3f; accepted up to %.2f)" % (kept, LG.Baker.REPAIR)
            elif gb > Lm['gripBetween'] and 'Slam' in SOURCES.get(name, []):
                e = ("NOT within the 0.15 rule: the game's per-joint lerp halfway between two exact 60 fps frames of "
                     "the original slam drop (the hammer turns ~75 deg in 1/60 s), for 1/120 s at full swing speed")
            add('grip: 120 Hz in-betweens (studs)', name, gb, Lm['gripBetween'], gb <= Lm['gripBetween'], btw['where'].get('grip'), e)
            add('grip slide stays on the haft', name, None, Lm['slide'],
                Lm['slide'][0] <= min(w['slideMin'], bw['slideMin']) and max(w['slideMax'], bw['slideMax']) <= Lm['slide'][1])
        v = max(w['jointGap'], bw['jointGap'])
        add('joint gap (studs)', name, v, 1e-4, v <= 1e-4, wh.get('jointGap'), exc(name, 'jointGap', w['jointGap']))
        add('hammer vs body: BVH overlap samples (120 Hz)', name, len(bad), 0, not bad, bad[0]['at'] if bad else None,
            exc(name, 'bvhFrames', 0.5) if bad else None)
        add('shaft outside torso core (min)', name, min(w['shaftCore'], bw['shaftCore']), Lm['shaftCore'],
            min(w['shaftCore'], bw['shaftCore']) >= Lm['shaftCore'], None, exc(name, 'shaftCore', min(w['shaftCore'], bw['shaftCore']), 'min'))
        if c.meta.get('planted'):
            add('planted foot drift per frame (studs)', name, w['footDrift'], Lm['footDrift'], w['footDrift'] <= Lm['footDrift'], wh.get('footDrift'))
        e = exc(name, 'ground', w['ground'], 'min')
        if not e and name in COMBOS and w['ground'] >= -0.1:
            ca, fd = COMBOS[name][2], COMBOS[name][4]
            if ca <= wh.get('ground', -1) <= ca + fd:
                e = ("a crossfade frame: the shin's back edge (it reaches below and behind the ankle) dips %.3f for a "
                     "few frames while the legs blend in root space; the feet stay on the ground" % -w['ground'])
        add('lowest point above ground (studs)', name, w['ground'], Lm['ground'], w['ground'] >= Lm['ground'], wh.get('ground'), e)
        if c.loop:
            add('loop closes (max |last - first|)', name, res['loopClose'], Lm['loop'], res['loopClose'] <= Lm['loop'])
        log('checked', name, 'samples', len(samples), 'grip120 %.4f' % bw['grip'], 'bvh bad', len(bad), '%.1fs' % (time.time() - t0))

    # ---- seams
    seams = report['seams']
    K = carry.K
    idle0 = clips['Idle'].frames[0]
    j = {}
    for name in ATTACKS + ['ChargeStart', 'Hit']:
        f = clips[name].frames
        j[name] = {'start': pose_distance(idle0, f[0], meshes)}
        if name in ATTACKS:
            j[name]['end'] = pose_distance(f[-1], idle0, meshes)
    seams['Idle<->attack junction (mesh points, studs)'] = j
    worst = max(max(v.values()) for v in j.values())
    add('Idle frame 0 = attack first/last frame (mesh points)', 'Idle<->attacks', worst, 0.01, worst <= 0.01)
    # double Spin seam (revolution 1 -> 2) and the combo crossfades: speed and continuity
    def window_stats(clip, t0_, t1_):
        f = clip.frames
        k0, k1 = max(1, int(round(t0_ * FPS))), min(len(f) - 1, int(round(t1_ * FPS)))
        pts = [pose_points(f[k], meshes) for k in range(k0 - 1, k1 + 2) if k < len(f)]
        step = [float(np.linalg.norm(pts[i + 1] - pts[i], axis=1).max()) for i in range(len(pts) - 1)]
        acc = [float(np.linalg.norm(pts[i + 2] - 2 * pts[i + 1] + pts[i], axis=1).max()) for i in range(len(pts) - 2)]
        return step, acc
    ds = src['Spin']
    s_in, a_in = window_stats(clips['Spin'], ds.seam - 0.05, ds.seam + LG.SEAM_FADE + 0.05)
    s_rev, a_rev = window_stats(clips['Spin'], LG.ATTACKS['Spin']['active'] + 0.05, ds.seam - 0.05)
    A37, B21 = baker.pose('Spin', LG.ATTACKS['Spin']['finish']), baker.pose('Spin', LG.ATTACKS['Spin']['active'])
    seams['Spin: revolution 1 -> 2'] = {
        'seamTime': r(ds.seam), 'residualAfter360 (mesh points)': r(pose_distance(A37, B21, meshes), 4),
        'fade': LG.SEAM_FADE, 'maxStepPerFrameAtSeam': r(max(s_in), 4), 'maxStepPerFrameInRevolution1': r(max(s_rev), 4),
        'maxAccelPerFrame2AtSeam': r(max(a_in), 4), 'maxAccelPerFrame2InRevolution1': r(max(a_rev), 4)}
    add('Spin seam: step per frame vs revolution 1 (ratio)', 'Spin', max(s_in) / max(s_rev), 1.05, max(s_in) <= 1.05 * max(s_rev))
    head0 = HM.xf(K['Hammer'], rig.HO)
    for name, (a, b, ca, cb, fd) in COMBOS.items():
        cA = ca / FPS
        st, ac = window_stats(clips[name], cA, cA + fd / FPS)
        sA, aA = window_stats(clips[a], cA - 0.2, cA + fd / FPS)
        sB, aB = window_stats(clips[b], cb / FPS, cb / FPS + fd / FPS + 0.2)
        mind = min(float(np.linalg.norm(HM.xf(clips[name].frames[k]['Hammer'], rig.HO) - head0))
                   for k in range(ca, ca + fd + 1))
        bad = [k for k in range(ca, ca + fd + 1) if contact_bad(clips[name].frames[k])]
        g = max(max(v['drift'] for v in HC.grip(rig, clips[name].frames[k]).values()) for k in range(ca, ca + fd + 1))
        seams[name + ' crossfade'] = {
            'A': a, 'B': b, 'cutA': r(cA), 'cutB': r(cb / FPS), 'fade': r(fd / FPS), 'shift': r(src[name].shift),
            'maxStepPerFrameInFade': r(max(st), 4), 'maxStepPerFrameA': r(max(sA), 4), 'maxStepPerFrameB': r(max(sB), 4),
            'maxAccelInFade': r(max(ac), 4), 'gripInFade': r(g, 6), 'bvhBadFramesInFade': len(bad),
            'hammerHeadMinDistanceFromCarry': r(mind, 3)}
        add('%s crossfade: hammer head stays off the carry spot (studs)' % name, name, mind, 3.0, mind >= 3.0)
        add('%s crossfade: speed vs the attacks\' own sweeps (ratio)' % name, name,
            max(st) / max(max(s) for s in (sA, sB, [0.0])), 1.5, max(st) <= 1.5 * max(max(sA), max(sB)))
    # runtime blends (MapBossPresentation: from the HELD last pose, 0.12 s into an attack, 0.16 s into Idle/Walk)
    idle_phases = [i * 0.25 for i in range(12)]
    walk_phases = [i * comp['Walk']['duration'] / 16 for i in range(16)]
    sets = {}
    for name in ATTACKS + ['ChargeStart']:
        sets['Idle->%s (0.12 s, Idle held)' % name] = HC.blends(rig, comp['Idle'], comp[name], idle_phases, hold_src=True)
        sets['Walk->%s (0.12 s, Walk held)' % name] = HC.blends(rig, comp['Walk'], comp[name], walk_phases, hold_src=True)
    for name in ATTACKS:
        sets['%s->Idle (0.16 s, end held)' % name] = HC.blends(rig, comp[name], comp['Idle'], [comp[name]['duration']], 0.16, hold_src=True)
    info = {'Slam->Walk (0.16 s, end held), information': HC.blends(
                rig, comp['Slam'], comp['Walk'], [comp['Slam']['duration']], 0.16, hold_src=True),
            'ChargeRun->Slam (0.12 s, run held), information': HC.blends(
                rig, comp['ChargeRun'], comp['Slam'], [i * comp['ChargeRun']['duration'] / 8 for i in range(8)], hold_src=True)}
    for label, poses in list(sets.items()) + list(info.items()):
        b = HC.check_between(rig, poses, meshes)
        bad = [{'at': lab, 'pairs': bb} for lab, P in poses for bb in [contact_bad(P)] if bb]
        b['hammerOverlapBad'] = bad[:12]
        b['hammerOverlapBadCount'] = len(bad)
        report['between'][label] = b
        if label in info:
            continue
        w = b['worst']
        walk = label.startswith('Walk->')
        e = ('NOT fixed by data: the run holds the hammer ~3 studs higher than the carry and leans 19 deg; the '
             'runtime blends each joint separately from the held run pose, so the fists drift off the haft mid-blend '
             '(README)') if walk else ("NOT fixed by data: the runtime's per-joint blend from the held pose into a fast "
                                       "attack start (the hammer follows its own root joint, the fists the arm chain)")
        add('in-blend grip (studs)', label, w['grip'], Lm['gripBetween'], w['grip'] <= Lm['gripBetween'], b['where'].get('grip'), e)
        att = [n for n in label.split(' ')[0].split('->') if n not in ('Idle', 'Walk')][0]
        e = None
        if bad:
            cuff = max(HC.hammer_solid_depth(rig, P, meshes, ['RightLowerArm'])['RightLowerArm'] for _, P in poses)
            rc = max(ref[s_]['cuffDepth'] for s_ in SOURCES[att])
            if all(set(x['pairs']) == {'RightLowerArm'} for x in bad) and cuff <= rc + 0.06:
                e = ("the attack's own early right-forearm cuff contact beside the fist (depth %.3f in the blend; the "
                     "original attack alone reaches %.3f)" % (cuff, rc))
        add('in-blend hammer vs body: BVH overlap samples', label, len(bad), 0, not bad, bad[0]['at'] if bad else None, e)
        v = max(w['hingeOffAxis'], w['kneeOffAxis'])
        add('in-blend elbow/knee off-axis (deg)', label, v, Lm['hingeOffAxis'], v <= Lm['hingeOffAxis'], None, exc(att, 'kneeOffAxis', v))
    # the walk's carry vs the carry pose, in chest space (what the Walk -> attack blend has to move)
    cs = lambda P: pose_points({p: HM.rinv(P['UpperTorso']) @ P[p] for p in ('Hammer', 'RightHand', 'LeftHand')}, meshes,
                               ['Hammer', 'RightHand', 'LeftHand'])
    off = [float(np.linalg.norm(cs(P) - cs(K), axis=1).max()) for P in clips['Walk'].frames]
    seams['Walk carry vs carry pose (chest space, hammer + fists)'] = {'min': r(min(off), 3), 'max': r(max(off), 3)}
    report['summary'] = summary
    report['allPass'] = all(x['pass'] for x in summary)
    report['allPassOrDocumented'] = all(x['pass'] or 'exception' in x for x in summary)
    report['failingWithoutException'] = [x for x in summary if not x['pass'] and 'exception' not in x]
    report['seconds'] = round(time.time() - t0, 1)
    return report


# ================================================================== Blender: actions
def bone_basis(rig_ob, P):
    """pose_bone.matrix_basis per bone from part deformations D (armature = world, rig at identity)."""
    import hm_motion as HM
    out = {}
    for b in rig_ob.data.bones:
        rest = np.array(b.matrix_local)
        D = P.get(b.name, np.eye(4)) if b.name != 'HumanoidRootPart' else np.eye(4)
        Dp = np.eye(4) if b.parent is None else (P.get(b.parent.name, np.eye(4)) if b.parent.name != 'HumanoidRootPart' else np.eye(4))
        out[b.name] = np.linalg.inv(rest) @ HM.rinv(Dp) @ D @ rest
    return out


def key_actions(rig_ob, clips):
    rig_ob.animation_data_create()
    for a in [a for a in bpy.data.actions if a.name.startswith('HB_') and a.name[3:] not in clips]:
        bpy.data.actions.remove(a)
    for name, c in clips.items():
        act_name = 'HB_' + name
        if act_name in bpy.data.actions:
            bpy.data.actions.remove(bpy.data.actions[act_name])
        rig_ob.animation_data.action = None
        prev = {}
        for k, P in enumerate(c.frames):
            for bn, M in bone_basis(rig_ob, P).items():
                pb = rig_ob.pose.bones[bn]
                pb.rotation_mode = 'QUATERNION'
                loc, q, sc = Matrix(M.tolist()).decompose()
                if bn in prev and q.dot(prev[bn]) < 0:
                    q.negate()
                prev[bn] = q.copy()
                pb.location = loc
                pb.rotation_quaternion = q
                pb.scale = (1, 1, 1)
                for prop in ('location', 'rotation_quaternion'):
                    pb.keyframe_insert(prop, frame=k + 1, group=bn)
        act = rig_ob.animation_data.action
        act.name = act_name
        act.use_fake_user = True
        act['fps'] = c.fps
        act['frames'] = len(c.frames)
        act['source'] = 'hammer-boss-moves/build_moves.py'
    log('keyed', len(clips), 'actions')
    rig_ob.animation_data.action = None


# ================================================================== Blender: previews
def apply_pose(rig_ob, P):
    for bn, M in bone_basis(rig_ob, P).items():
        rig_ob.pose.bones[bn].matrix_basis = Matrix(M.tolist())


def preview_scene():
    sc = bpy.context.scene
    for ob in list(bpy.data.objects):
        if ob.type in ('LIGHT', 'CAMERA') or ob.name == 'RENDER_STAGE_ONLY':
            ob.hide_render = True
            ob.hide_viewport = True
    col = bpy.data.collections.get('MovesPreview') or bpy.data.collections.new('MovesPreview')
    if col.name not in sc.collection.children:
        sc.collection.children.link(col)
    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, 0))
    g = bpy.context.active_object
    g.name = 'MovesGround'
    for c in g.users_collection:
        c.objects.unlink(g)
    col.objects.link(g)
    m = bpy.data.materials.new('MovesGrass')
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = 0.95
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 0.35
    noise.inputs['Detail'].default_value = 6.0
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.09, 0.26, 0.035, 1)
    ramp.color_ramp.elements[1].color = (0.20, 0.42, 0.07, 1)
    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    g.data.materials.append(m)
    w = bpy.data.worlds.new('MovesSky')
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.50, 0.70, 0.95, 1)
    bg.inputs['Strength'].default_value = 0.75
    sc.world = w
    key = bpy.data.lights.new('MovesKey', 'SUN')
    key.energy = 3.4
    key.angle = math.radians(10)
    ko = bpy.data.objects.new('MovesKey', key)
    ko.rotation_euler = (math.radians(52), 0, math.radians(-38))
    col.objects.link(ko)
    fill = bpy.data.lights.new('MovesFill', 'AREA')
    fill.energy = 2200
    fill.size = 22
    fill.specular_factor = 0.15
    fo = bpy.data.objects.new('MovesFill', fill)
    fo.location = (16, -18, 22)
    col.objects.link(fo)
    look_at(fo, (0, -2, 5))
    cam = bpy.data.cameras.new('MovesCam')
    cam.lens = 40
    co = bpy.data.objects.new('MovesCam', cam)
    col.objects.link(co)
    sc.camera = co
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'
    try:
        sc.eevee.taa_render_samples = 24
        sc.eevee.use_shadows = True
    except AttributeError:
        pass
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = -0.15
    return co, col


def look_at(ob, target):
    from mathutils import Vector
    d = Vector(target) - ob.location
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = d.to_track_quat('-Z', 'Y')


def place_cam(co, target, yaw_deg, dist, height, lens=40):
    from mathutils import Vector
    a = math.radians(yaw_deg)
    # yaw 0 = straight in front of him (he faces -Y); positive = round to his right side (-X)
    co.location = Vector((target[0] - dist * math.sin(a), target[1] - dist * math.cos(a), height))
    co.data.lens = lens
    look_at(co, target)


def render(path):
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


# ---- rubble wave mock (Slam and SpinSlam previews only; not game data)
def rubble_build(col, rig, meshes, origin):
    """A line of faceted dirt and rock bursts racing forward (-Y) from origin (the slam's head on the
    ground), each taller than the last: knee height to 1.5x his height over WAVE['length'] studs."""
    import bmesh
    rng = np.random.default_rng(11)
    dirt = bpy.data.materials.new('RubbleDirt')
    dirt.use_nodes = True
    dirt.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.30, 0.18, 0.08, 1)
    dirt.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 1.0
    rock = bpy.data.materials.new('RubbleRock')
    rock.use_nodes = True
    rock.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.36, 0.35, 0.34, 1)
    rock.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9
    knee = float(rig.head['RightLowerLeg'][2])
    tall = 1.5 * float(max(meshes[p + '_v'][:, 2].max() for p in PARTS))
    n = WAVE['bursts']
    bursts = []
    for k in range(n):
        u = k / (n - 1)
        h = knee + (tall - knee) * u ** 1.15
        wdt = 1.2 + 0.24 * h
        y = origin[1] - 1.5 - WAVE['length'] * u
        chunks = []
        specs = [(0.0, 0.0, 0.5 * wdt, 0.45 * wdt, h, 0.0, rock if k % 2 else dirt)]
        for j in range(5):
            a = rng.uniform(0, 2 * math.pi)
            dist = wdt * rng.uniform(0.45, 0.7)
            specs.append((math.cos(a) * dist, math.sin(a) * dist, wdt * rng.uniform(0.22, 0.34), wdt * rng.uniform(0.2, 0.3),
                          h * rng.uniform(0.25, 0.55), a, dirt if j % 2 else rock))
        for (dx, dy, sx, sy, hz, a, mat) in specs:
            bm = bmesh.new()
            bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
            for v in bm.verts:
                v.co.x *= 1 + rng.uniform(-0.22, 0.22)
                v.co.y *= 1 + rng.uniform(-0.22, 0.22)
                v.co.z *= 1 + rng.uniform(-0.15, 0.15)
            me = bpy.data.meshes.new('RubbleChunk')
            bm.to_mesh(me)
            bm.free()
            for poly in me.polygons:
                poly.use_smooth = False
            me.materials.append(mat)
            ob = bpy.data.objects.new('RubbleChunk', me)
            col.objects.link(ob)
            ob.hide_render = True
            chunks.append({'ob': ob, 'base': (origin[0] + dx, y + dy), 'size': (sx, sy, hz / 2), 'h': hz, 'out': a,
                           'spin': rng.uniform(-1, 1)})
        bursts.append({'t': WAVE['gap'] * k, 'h': h, 'chunks': chunks})
    return bursts


def rubble_pose(bursts, t):
    """Set every chunk for time t after the slam impact; True if any is visible."""
    from mathutils import Euler
    pop, hold, crumble = WAVE['pop'], WAVE['hold'], WAVE['crumble']
    any_on = False
    for b in bursts:
        tau = t - b['t']
        for c in b['chunks']:
            ob = c['ob']
            if tau < 0 or tau > pop + hold + crumble:
                ob.hide_render = True
                continue
            rise = 1 - (1 - min(1.0, tau / pop)) ** 3
            u = min(1.0, max(0.0, (tau - pop - hold) / crumble))
            sx, sy, sz = c['size']
            s = 1 - 0.5 * u
            hz = c['h']
            z = hz / 2 - (1 - rise) * (hz + 0.4) - u * u * hz * 1.15
            out = c['out']
            drift = 0.6 * u * sx
            ob.location = (c['base'][0] + math.cos(out) * drift, c['base'][1] + math.sin(out) * drift, z)
            tilt = math.radians(8 + 30 * u) if c is not b['chunks'][0] else math.radians(22 * u)
            ob.rotation_euler = Euler((tilt * math.sin(out), -tilt * math.cos(out), c['spin'] * 0.4 + u * c['spin']), 'XYZ')
            ob.scale = (sx * s, sy * s, sz * (1 - 0.35 * u))
            ob.hide_render = z + sz < 0.02
            any_on = any_on or not ob.hide_render
    return any_on


def preview_sequences(rig, clips, phases):
    """What the game shows: each clip sampled per joint (EnemyMotion.sample) at 60 Hz, with the
    runtime's switches blended from the held last pose (0.12 s into an attack, 0.16 s into Idle)."""
    import hm_checks as HC
    import hm_motion as HM
    comp = {n: HC.as_clip(rig, c.frames, c.fps, c.loop) for n, c in clips.items()}
    v = clips['Walk'].meta['nominalSpeed']
    plans = {'Slam': ('Idle', 0.4, 0.5), 'Spin': ('Walk', 0.6667, 0.4), 'SwingSpin': ('Idle', 0.3, 0.4),
             'SpinSlam': ('Idle', 0.3, 0.5)}
    seqs = {}
    for name, (lead_clip, lead, tail) in plans.items():
        d = comp[name]['duration']
        hz = PREVIEW_HZ
        held = end = None
        out = []
        for i in range(int(round((lead + d + tail) * hz)) + 1):
            t = i / hz
            y = 0.0
            if t < lead - 1e-9:
                if lead_clip == 'Idle':
                    Lc = HC.sample(rig, comp['Idle'], (3.0 - lead + t) % 3.0)
                else:
                    Lc = HC.sample(rig, comp['Walk'], t)
                    y = v * (lead - t)
                held = Lc
            elif t <= lead + d + 1e-9:
                ta = t - lead
                Lc = HC.sample(rig, comp[name], ta)
                if ta < 0.12:
                    Lc = HC.blend(held, Lc, ta / 0.12)
                end = Lc
            else:
                u = t - lead - d
                Lc = HC.sample(rig, comp['Idle'], u)
                if u < 0.16:
                    Lc = HC.blend(end, Lc, u / 0.16)
            out.append({'P': HM.from_locals(rig, Lc), 'y': y, 't': t - lead})
        slam_t = [ph[1] for ph in phases[name] if ph[0] == 'slam circle']
        seqs[name] = {'frames': out, 'wave': slam_t[0] if slam_t else None, 'lead': lead}
    return seqs


VIEWS = {'Slam': ((-1.0, -14.0, 7.0), 70, 48, 14.0, 32), 'SpinSlam': ((-1.0, -14.0, 7.0), 70, 48, 14.0, 32),
         'Spin': ((0.0, -1.0, 5.5), 35, 36, 13.0, 35), 'SwingSpin': ((0.0, -1.0, 5.5), 35, 36, 13.0, 35)}


def render_previews(rig, meshes, clips, src, phases):
    import hm_motion as HM
    seqs = preview_sequences(rig, clips, phases)
    rig_ob = bpy.data.objects['HammerBoss_Rig']
    rig_ob.animation_data_clear()
    co, col = preview_scene()
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    # the wave starts where the slam's head meets the ground (same in Slam and SpinSlam)
    imp = phases['Slam'][0][1]
    head = HM.xf(src['Slam'].pose(imp)['Hammer'], rig.HO)
    bursts = rubble_build(col, rig, meshes, (float(head[0]), float(head[1])))
    t0 = time.time()
    meta = {}
    for name, sq in seqs.items():
        out = FRAMES / name
        out.mkdir(parents=True, exist_ok=True)
        tgt, yaw, dist, hgt, lens = VIEWS[name]
        place_cam(co, tgt, yaw, dist, hgt, lens)
        flags = []
        for i, f in enumerate(sq['frames']):
            rig_ob.location = (0, f['y'], 0)
            apply_pose(rig_ob, f['P'])
            on = rubble_pose(bursts, f['t'] - sq['wave']) if sq['wave'] is not None else False
            flags.append(bool(on))
            bpy.context.view_layer.update()
            render(out / ('%04d.png' % i))
        meta[name] = {'wave': flags, 'frames': len(flags)}
        rubble_pose(bursts, -1.0)
        log('rendered', name, len(flags), 'frames', '%.0fs' % (time.time() - t0))
    rig_ob.location = (0, 0, 0)
    (FRAMES / 'meta.json').write_text(json.dumps(meta))


# ================================================================== post (system Python): labels, mp4
def post():
    from PIL import Image, ImageDraw, ImageFont
    PREVIEWS.mkdir(exist_ok=True)
    try:
        font = ImageFont.truetype('arial.ttf', 26)
        small = ImageFont.truetype('arial.ttf', 20)
    except OSError:
        font = small = ImageFont.load_default()
    meta = json.loads((FRAMES / 'meta.json').read_text())

    def label(img, text, sub=None, tag=None):
        d = ImageDraw.Draw(img, 'RGBA')
        w = max(d.textlength(text, font=font), d.textlength(sub or '', font=small)) + 28
        d.rounded_rectangle((16, 14, 16 + w, 54 + (26 if sub else 0)), 8, fill=(0, 0, 0, 120))
        d.text((30, 20), text, font=font, fill=(255, 255, 255, 255))
        if sub:
            d.text((30, 50), sub, font=small, fill=(225, 235, 225, 255))
        if tag:
            tw = d.textlength(tag, font=font) + 28
            d.rounded_rectangle((1264 - tw, 14, 1264, 54), 8, fill=(90, 50, 15, 170))
            d.text((1278 - tw, 20), tag, font=font, fill=(255, 225, 190, 255))
        return img

    titles = {'Slam': 'Slam  (original, 1.67 s, impact 0.77 s)',
              'Spin': 'Spin x2  (original revolution twice, 2.28 s)',
              'SwingSpin': 'SwingSpin  (Swing -> double Spin, 3.33 s)',
              'SpinSlam': 'SpinSlam  (double Spin -> Slam, 3.15 s, slam 2.25 s)'}
    lead = {'Slam': 'from Idle', 'Spin': 'from the Walk', 'SwingSpin': 'from Idle', 'SpinSlam': 'from Idle'}
    for name in titles:
        src = sorted((FRAMES / name).glob('*.png'))
        flags = meta[name]['wave']
        tmp = CACHE / ('video_' + name)
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        n = 0
        for speed, idx in (('normal speed', range(0, len(src), 2)), ('half speed', range(len(src)))):
            for i in idx:
                im = Image.open(src[i]).convert('RGB')
                label(im, titles[name], '%s  -  %s, then back to Idle; game blends' % (speed, lead[name]),
                      'rubble wave (mock)' if flags[i] else None).save(tmp / ('%05d.png' % n))
                n += 1
        mp4 = PREVIEWS / (name + '.mp4')
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '30', '-i', str(tmp / '%05d.png'),
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '24', '-preset', 'slow', '-movflags',
                        '+faststart', str(mp4)], check=True)
        print('[moves] wrote', mp4, '%.1f MB' % (mp4.stat().st_size / 1e6), flush=True)


# ================================================================== main
def main(stage):
    if stage == 'post':
        post()
        return
    if stage == 'extract' or not (CACHE / 'rig.json').exists():
        extract()
        if stage == 'extract':
            return
    rig, meshes = load()
    clips, src, baker, carry = build_clips(rig)
    phases = attack_phases(src)
    if stage == 'render':                     # previews only (the data stage already ran)
        bpy.ops.wm.open_mainfile(filepath=str(BLEND))
        render_previews(rig, meshes, clips, src, phases)
        subprocess.run(['python', str(Path(__file__).resolve()), 'post'], check=True)
        return
    GAME.mkdir(parents=True, exist_ok=True)
    pp = partposes(rig, clips)
    (GAME / 'PartPoses.json').write_text(json.dumps(pp, separators=(',', ':')))
    gd = gamedata(rig, clips, src, phases, meshes)
    (GAME / 'BossGameData.json').write_text(json.dumps(gd, indent=1))
    proofs = {'axisProof': axis_proof(rig), 'legacyBake': legacy_proof(rig, clips, pp, baker),
              'portCrossCheck': port_crosscheck(baker), 'studioConvert': studio_convert(pp),
              'repairedIntervals': list(baker.repaired.values()),
              'idleFrame0VsCarry': clips['Idle'].meta['endsBeforeSnap']}
    log('proofs', json.dumps({k: v for k, v in proofs.items() if k != 'studioConvert'}, default=float)[:1500])
    log('studio convert', proofs['studioConvert']['passed'], proofs['studioConvert']['maxCornerError'])
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    overlap = bvh_overlap(rig, meshes)
    checks = run_checks(rig, meshes, clips, src, baker, carry, overlap)
    checks.update(proofs)
    checks['generated'] = time.strftime('%Y-%m-%d %H:%M')
    (HERE / 'MotionChecks.json').write_text(json.dumps(checks, indent=1, default=float))
    fails = [x for x in checks['summary'] if not x['pass']]
    log('checks: %d rows, %d failing (%d without a documented exception)' % (
        len(checks['summary']), len(fails), len(checks['failingWithoutException'])))
    for x in checks['failingWithoutException']:
        log('  FAIL', x)
    rig_ob = bpy.data.objects['HammerBoss_Rig']
    key_actions(rig_ob, clips)
    rig_ob['MovesActions'] = ', '.join('HB_%s (%d fps)' % (n, c.fps) for n, c in clips.items()) + '; old Boss_* actions untouched'
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    log('saved', BLEND.name)
    if stage == 'all':
        render_previews(rig, meshes, clips, src, phases)
        subprocess.run(['python', str(Path(__file__).resolve()), 'post'], check=True)


if __name__ == '__main__':
    main(stage_arg())
