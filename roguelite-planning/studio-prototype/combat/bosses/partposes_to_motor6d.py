"""Hammer Brute on the old template (R9, 2026-10-04): part poses -> Motor6D.Transform clips.

The Hammer keeps the original 16-part Motor6D template (ServerStorage.RogueliteNPCs.HammerBoss_NPC,
installed as Hammer_NPC), so his re-authored clips arrive as part poses, not bone deltas
(plans/2026-10-03-hammer-brute-rebuild-design.md, "Change of plan").

Inputs
  <asset-folder>/exports/game/PartPoses.json (hammer-boss-moves):
      {"fps": 24, "rootHeight"?: 4.45, "motion": {...}?, "clips": {"<Clip>": {"duration": s, "loop": bool,
        "fps"?: n, "frames": [{"time": s, "poses": {"<Part>": [12]}}]}}}
      Each part's CFrame relative to HumanoidRootPart, Studio axes, template scale 1.0, as
      [x,y,z,R00,R01,R02,R10,R11,R12,R20,R21,R22] (CFrame:GetComponents order). A frame may put the
      parts under "poses", "parts" or "transforms", or be the {part: [12]} table itself.
  receipts/hammer-old-receipt.json: the read-only Studio dump of HammerBoss_NPC (DumpMotorReceipt.luau):
      the model scale (it must be 1.0, the part poses' scale), every part's CFrame relative to
      HumanoidRootPart and size, every Motor6D's Part0, Part1, C0, C1 and the name EnemyMotion.bind
      gives it (bindName: the EnemyBone attribute, else the name minus "Motor6D"; the old template's
      joints are Boss_<Part>).
  BossGameData.json (optional here): its motion if PartPoses has none, and bodyCentreHeight, which
      must match the template's root height.

Outputs (same folder), read by build_boss_modules.py exactly like the other bosses' packages:
  StudioAnimationData.json  Motor6D.Transform per joint (keyed by bind name) per frame; rigType Motor6D.
                            The client plays it through EnemyMotion.bind/apply, and scales the
                            translations by GetScale()/EnemyBaselineModelScale like any rig.
  AnimationData.json        for gameplay point sampling (build_boss_modules.sample_point): a Root bone
                            at the root height (so samples are in the ground frame, y from the soles)
                            and one bone per part under it with rest identity. A part bone's local
                            axes are that part's own Studio axes: a BossGameData point
                            {"bone": "Hammer", "offset": [x,y,z]} is the offset in the Hammer part's
                            Studio space (the hand-off's HammerFace/HammerGrip), no Blender swap.
                            rootHeight (the Root bone's height, the same number): the build's
                            MapBossTiming rootHeight when BossGameData has no bodyCentreHeight.
  StudioRetargetChecks.json the round-trip error below.

Maths. Roblox puts Part1 at P1 = P0 * C0 * T * C1^-1 (P0, P1 the parts' CFrames, here relative to the
HumanoidRootPart, which is the identity), so T = C0^-1 * P0^-1 * P1 * C1. Each supplied rotation may
be off a true rotation by POSE_TOLERANCE at most (rounding; more is a broken export) and is made
exact first. Every frame is then rebuilt forward from the root through the receipt's C0/C1 with the
rounded T as written, and the part centres and box corners must come back within MAX_ERROR studs of
the SUPPLIED matrices. Everything is computed and checked before any file is written: a failure
raises and writes nothing.
build_boss_modules' basis: its sample_point returns F * w * [o0, o2, o1] with F = diag(-1, 1, 1)
(its Y/Z-swapped Blender basis is Studio with X flipped). A part bone's world w = Root * F*P*S
(S swaps Y and Z) then gives Root * P * [o0, o1, o2]: the part-space offset in the ground frame.

Usage
  python partposes_to_motor6d.py [asset-folder [receipt]]   default hammer-boss-moves, receipts/hammer-old-receipt.json
  python partposes_to_motor6d.py --legacy [receipt]         round-trip the legacy clips (hammer-boss/finished/BossData.json)
build_boss_modules.py converts in memory for hammer-brute when PartPoses.json is there, and writes
these files with the rest of its output.
Tests: python test_partposes_to_motor6d.py
"""
import hashlib, json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
PLANNING = HERE.parents[2]
RECEIPT = HERE / 'receipts' / 'hammer-old-receipt.json'
FOLDER = 'hammer-boss-moves'
LEGACY = PLANNING / 'hammer-boss' / 'finished' / 'BossData.json'
ID = 'hammer-brute'
ROOT = 'HumanoidRootPart'
MAX_ERROR = 1e-4          # studs, rebuilt part centres and box corners vs the supplied part poses
POSE_TOLERANCE = 2e-6     # a supplied rotation's largest entry off the nearest rotation (legacy data: 8.6e-7)
ROOT_HEIGHT_TOLERANCE = .05
LEGACY_LOOPS = {'Idle', 'Walk', 'ChargeRun'}
OUTPUTS = ('StudioAnimationData.json', 'AnimationData.json', 'StudioRetargetChecks.json')
F = np.diag([-1., 1., 1., 1.])
S = np.array([[1., 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
IDENTITY = [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]


def mat(v):
    m = np.eye(4); m[:3, 3] = v[:3]; m[:3, :3] = np.asarray(v[3:], dtype=float).reshape(3, 3); return m


# + 0.0 turns -0.0 into 0.0, so the output never depends on the sign of a rounded zero.
def cf(m): return [round(float(x), 7) + 0.0 for x in [*m[:3, 3], *m[:3, :3].flatten()]]


def rigid(m, label='', tolerance=None):
    """m with its rotation replaced by the nearest rotation (polar decomposition). A matrix more than
    `tolerance` (default POSE_TOLERANCE) from a rotation (or a reflection) is a broken export, not rounding."""
    tolerance = POSE_TOLERANCE if tolerance is None else tolerance
    u, _, vt = np.linalg.svd(m[:3, :3]); r = u @ vt
    off = float(np.abs(r - m[:3, :3]).max())
    if np.linalg.det(r) < 0 or off > tolerance:
        raise ValueError(f'{label}: not a rotation (off by {off:.3g}, limit {tolerance:g})')
    out = m.copy(); out[:3, :3] = r; return out


def corners(size):
    h = np.asarray(size, dtype=float) / 2
    return np.array([[x * h[0], y * h[1], z * h[2], 1.] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]).T


def rig(receipt):
    """The template's joint tree from the receipt: joints in parent-first order, each
    {name (bind name), motor, part0, part1, parent (joint name or None), c0, c1}, the parts
    {name: {cframe, size, mesh}}, and the root height (HumanoidRootPart centre above the lowest mesh
    point). Raises ValueError for a receipt this can't drive: a model scale other than 1.0, no root,
    a part driven by two Motor6Ds, two joints with one bind name, or a joint the root can't reach (a
    cycle, or a Part0 outside the tree)."""
    scale = receipt.get('scale')
    if not isinstance(scale, (int, float)) or abs(scale - 1) > 1e-6:
        raise ValueError(f'receipt model scale is {scale}, not 1.0: the part poses and C0/C1 must be at the template\'s authored scale')
    parts = {p['name']: {'cframe': mat(p['cframe']), 'size': p['size'], 'mesh': p.get('class') == 'MeshPart'} for p in receipt['parts']}
    if ROOT not in parts: raise ValueError('receipt has no HumanoidRootPart')
    motors = [m for m in receipt['motors'] if m.get('part0') and m.get('part1')]
    by_part1, names = {}, {}
    for m in motors:
        if m['part1'] in by_part1: raise ValueError(f"{m['part1']} is driven by two Motor6Ds")
        if m['bindName'] in names: raise ValueError(f"two joints bind as {m['bindName']}")
        by_part1[m['part1']] = m; names[m['bindName']] = m
    order, placed = [], {ROOT}
    while len(order) < len(motors):
        ready = [m for m in motors if m['part1'] not in placed and m['part0'] in placed]
        if not ready: raise ValueError(f'Motor6Ds not reachable from the root: {sorted(m["part1"] for m in motors if m["part1"] not in placed)}')
        for m in sorted(ready, key=lambda m: m['bindName']):
            order.append({'name': m['bindName'], 'motor': m['name'], 'part0': m['part0'], 'part1': m['part1'],
                          'parent': by_part1[m['part0']]['bindName'] if m['part0'] in by_part1 else None,
                          'c0': mat(m['c0']), 'c1': mat(m['c1'])})
            placed.add(m['part1'])
    low = min((parts[n]['cframe'] @ corners(p['size']))[1].min() for n, p in parts.items() if p['mesh']) if any(p['mesh'] for p in parts.values()) else 0
    return order, parts, -float(low)


def frame_parts(frame):
    for key in ('poses', 'parts', 'transforms'):
        if isinstance(frame.get(key), dict): return frame[key]
    return {k: v for k, v in frame.items() if k != 'time'}


def read_poses(poses):
    """PartPoses as {clip: {duration, loop, fps, frames: [(time, raw, exact)]}}: each frame's parts as
    supplied (raw 4x4) and with exact rotations (rigid)."""
    fps = poses.get('fps') or 24; out = {}
    for name, clip in poses['clips'].items():
        rate = clip.get('fps') or fps; frames = []
        for i, frame in enumerate(clip['frames']):
            t = frame.get('time', i / rate); parts = frame_parts(frame)
            # Poses are relative to the root, so a root entry can only be the identity (root motion
            # isn't part of a clip: the server moves the root).
            if ROOT in parts and np.abs(mat(parts[ROOT]) - np.eye(4)).max() > 1e-4: raise ValueError(f'{name} frame {i}: {ROOT} is not the identity')
            raw = {p: mat(v) for p, v in parts.items() if p != ROOT}
            frames.append((t, raw, {p: rigid(m, f'{name} frame {i} {p}') for p, m in raw.items()}))
        if len(frames) < 2: raise ValueError(f'{name}: fewer than 2 frames')
        out[name] = {'duration': clip.get('duration', (len(frames) - 1) / rate), 'loop': bool(clip.get('loop')), 'fps': clip.get('fps'), 'frames': frames}
    return out


def convert(poses, receipt, motion=None, root_height=None):
    """(StudioAnimationData, AnimationData, checks) from PartPoses and the receipt. Pure: no file access.
    Raises ValueError when the receipt can't be driven (rig), a frame's parts don't match the template,
    a pose isn't a rotation, or the round trip is >= MAX_ERROR."""
    joints, parts, receipt_height = rig(receipt)
    root_height = receipt_height if root_height is None else root_height
    if abs(root_height - receipt_height) > ROOT_HEIGHT_TOLERANCE:
        raise ValueError(f'root height {root_height} is not the template\'s {receipt_height:.3f} (HumanoidRootPart above the soles)')
    height = round(float(root_height), 5) + 0.0  # the Root bone's height and rootHeight, the same number
    clips = read_poses(poses)
    fps = poses.get('fps') or 24
    wanted = sorted(j['part1'] for j in joints)
    inv = lambda m: np.linalg.inv(m)
    c0i = {j['name']: inv(j['c0']) for j in joints}; c1i = {j['name']: inv(j['c1']) for j in joints}
    box = {n: corners(p['size']) for n, p in parts.items()}
    s_clips, d_clips, worst, worst_at, frames_total = {}, {}, {'centre': 0., 'corner': 0.}, None, 0
    for name, clip in clips.items():
        s_frames, d_frames = [], []
        for i, (t, raw, P) in enumerate(clip['frames']):
            missing, extra = set(wanted) - set(P), set(P) - set(wanted)
            if missing or extra: raise ValueError(f'{name} frame {i}: parts missing {sorted(missing)}, not in the template {sorted(extra)}')
            P = {ROOT: np.eye(4), **P}
            T = {j['name']: cf(rigid(c0i[j['name']] @ inv(P[j['part0']]) @ P[j['part1']] @ j['c1'], f'{name} frame {i} {j["name"]}', 1e-5)) for j in joints}
            Q = {ROOT: np.eye(4)}
            for j in joints: Q[j['part1']] = Q[j['part0']] @ j['c0'] @ mat(T[j['name']]) @ c1i[j['name']]
            # Against the matrices as supplied, not the exact ones: a pose that isn't quite a rotation
            # shows up here as the error it puts on the part's corners.
            for p in wanted:
                centre = float(np.abs(Q[p][:3, 3] - raw[p][:3, 3]).max()); corner = float(np.abs((Q[p] - raw[p]) @ box[p]).max())
                if max(centre, corner) > max(worst.values()): worst_at = f'{name} frame {i} {p}'
                worst['centre'] = max(worst['centre'], centre); worst['corner'] = max(worst['corner'], corner)
            s_frames.append({'time': round(float(t), 6) + 0.0, 'transforms': T})
            d_frames.append({'time': round(float(t), 6) + 0.0, 'transforms': {p: cf(F @ P[p] @ S) for p in wanted}})
            frames_total += 1
        meta = {'duration': clip['duration'], 'loop': clip['loop'], **({'fps': clip['fps']} if clip['fps'] else {})}
        s_clips[name] = {**meta, 'frames': s_frames}; d_clips[name] = {**meta, 'frames': d_frames}
    error = max(worst.values())
    checks = {'id': ID, 'rigType': 'Motor6D', 'jointCount': len(joints), 'clipCount': len(clips), 'frameCount': frames_total,
              'maxCentreError': worst['centre'], 'maxCornerError': worst['corner'], 'worstAt': worst_at,
              'limit': MAX_ERROR, 'poseTolerance': POSE_TOLERANCE, 'passed': bool(error < MAX_ERROR), 'rootHeight': height}
    if error >= MAX_ERROR: raise ValueError(f'round trip {error:.3g} studs at {worst_at} (limit {MAX_ERROR})')
    motion = motion or {}
    studio = {'id': ID, 'fps': fps,
              'bones': {j['name']: {'parent': j['parent'], 'rest': cf(j['c0'] @ c1i[j['name']]), 'part0': j['part0'], 'part1': j['part1'], 'motor': j['motor']} for j in joints},
              'clips': s_clips, 'motion': motion,
              'coordinateSpace': 'Motor6D.Transform per joint (EnemyMotion.bind name): C0^-1 * P0^-1 * P1 * C1 from HumanoidRootPart-relative part poses and the template receipt',
              'rigType': 'Motor6D', 'baselineModelScale': 1, 'authoringScale': 1}
    data = {'id': ID, 'fps': fps,
            'bones': {'Root': {'parent': None, 'rest': [0, height, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]},
                      **{p: {'parent': 'Root', 'rest': IDENTITY} for p in wanted}},
            'clips': d_clips, 'motion': motion, 'rootHeight': height,
            'coordinateSpace': 'build_boss_modules basis (Studio with X flipped); Root at the HumanoidRootPart height; a part bone = F*P*S, so point offsets are in the part\'s own Studio space'}
    return studio, data, checks


def legacy_poses(boss_data, receipt, exact=False):
    """The old runtime's clips (hammer-boss/finished/BossData.json) as PartPoses. BossMotion stores a
    root-space delta per part and puts the part at pose * BossRest (BossMotion.apply), where BossRest
    is the part's rest CFrame relative to the HumanoidRootPart, i.e. the receipt's. Raw authored frames:
    the old runtime's own fixes on top (constrainArms, the tool-space blend, the sweep lift) aren't data.
    exact: the products as 4x4 arrays (unrounded), for comparing against."""
    rest = {p['name']: mat(p['cframe']) for p in receipt['parts']}
    clips = {}
    for name, clip in boss_data['clips'].items():
        fps = clip['fps']
        frames = [{'time': i / fps, 'parts': {p: (mat(v) @ rest[p]) if exact else cf(mat(v) @ rest[p]) for p, v in frame.items()}} for i, frame in enumerate(clip['frames'])]
        clips[name] = {'duration': clip['lastFrame'] / fps, 'loop': name in LEGACY_LOOPS, 'fps': fps, 'frames': frames}
    return {'fps': 30, 'clips': clips}


def sha(data): return hashlib.sha256(data).hexdigest()


def resolve(folder):
    p = Path(folder)
    return p if p.is_absolute() or p.exists() else PLANNING / folder


def package(folder=FOLDER, receipt_path=RECEIPT):
    """Reads and converts <folder>/exports/game/PartPoses.json. Writes nothing: returns (game folder,
    {output name: bytes}, studio, data, checks). Raises FileNotFoundError or ValueError."""
    game = resolve(folder) / 'exports' / 'game'; source = game / 'PartPoses.json'; receipt_path = Path(receipt_path)
    for p in (source, receipt_path):
        if not p.exists(): raise FileNotFoundError(f'missing {p}')
    source_bytes, receipt_bytes = source.read_bytes(), receipt_path.read_bytes()
    poses = json.loads(source_bytes.decode('utf-8')); receipt = json.loads(receipt_bytes.decode('utf-8'))
    gd = game / 'BossGameData.json'; gd = json.loads(gd.read_text(encoding='utf-8')) if gd.exists() else {}
    motion = poses.get('motion') or gd.get('motion')
    height = poses.get('rootHeight') or gd.get('bodyCentreHeight')
    studio, data, checks = convert(poses, receipt, motion, float(height) if height else None)
    if not motion: print(f'{ID}: WARN no motion (strideLength, nominalSpeed, chargeStrideLength) in PartPoses or BossGameData', flush=True)
    studio['sourceAnimationHash'] = checks['sourceAnimationHash'] = sha(source_bytes)
    studio['importReceiptHash'] = checks['importReceiptHash'] = sha(receipt_bytes)
    s_bytes = json.dumps(studio, separators=(',', ':'), allow_nan=False).encode('utf-8')
    d_bytes = json.dumps(data, separators=(',', ':'), allow_nan=False).encode('utf-8')
    checks['outputHash'] = sha(s_bytes)
    outputs = dict(zip(OUTPUTS, (s_bytes, d_bytes, json.dumps(checks, indent=2).encode('utf-8'))))
    return game, outputs, studio, data, checks


def write_package(game, outputs):
    """Writes package()'s outputs (exact bytes); an unchanged file isn't rewritten."""
    for name, data in outputs.items():
        path = game / name
        if not path.exists() or path.read_bytes() != data: path.write_bytes(data)


def convert_package(folder=FOLDER, receipt_path=RECEIPT):
    """package(), then its three files: nothing is written unless all of it converted and checked."""
    game, outputs, _, _, checks = package(folder, receipt_path)
    write_package(game, outputs)
    print(f"{ID}: {checks['frameCount']} frames, {checks['jointCount']} joints, round trip {max(checks['maxCentreError'], checks['maxCornerError']):.3g} studs (< {MAX_ERROR})", flush=True)
    return checks


def legacy_check(receipt_path=RECEIPT):
    receipt = json.loads(Path(receipt_path).read_text(encoding='utf-8'))
    boss = json.loads(LEGACY.read_text(encoding='utf-8'))
    poses = legacy_poses(boss, receipt)
    studio, _, checks = convert(poses, receipt, {}, None)
    # Also against the legacy products before any rounding (pose * BossRest as 4x4 arrays).
    joints, parts, _ = rig(receipt); exact = legacy_poses(boss, receipt, exact=True); raw = 0.
    for name, clip in exact['clips'].items():
        for frame, out in zip(clip['frames'], studio['clips'][name]['frames']):
            Q = {ROOT: np.eye(4)}
            for j in joints: Q[j['part1']] = Q[j['part0']] @ j['c0'] @ mat(out['transforms'][j['name']]) @ np.linalg.inv(j['c1'])
            for p, m in frame['parts'].items(): raw = max(raw, float(np.abs((Q[p] - m) @ corners(parts[p]['size'])).max()))
    checks['maxErrorVsUnroundedLegacy'] = raw
    return checks


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--legacy' in sys.argv:
        print(json.dumps(legacy_check(*(args[:1] or [RECEIPT])), indent=1))
    else:
        convert_package(*args[:2])
