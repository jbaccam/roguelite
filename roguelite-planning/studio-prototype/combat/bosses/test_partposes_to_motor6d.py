"""Checks for partposes_to_motor6d.py and its build_boss_modules hook (Hammer on the old template, R9,
2026-10-04). Reads the repo, writes nothing outside a temporary folder.
    python test_partposes_to_motor6d.py      (or: python -m pytest test_partposes_to_motor6d.py)
The legacy checks use receipts/hammer-old-receipt.json (the Studio dump), or, before it exists, a
receipt made from hammer-boss/finished/studio-asset-manifest.json the way DumpMotorReceipt.luau makes
one (bind names Boss_<Part>, as EnemyMotion.bind names the old template's joints).
"""
import contextlib, io, json, math, re, sys, tempfile
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import partposes_to_motor6d as C  # noqa: E402
import build_boss_modules as B  # noqa: E402

MANIFEST = C.PLANNING / 'hammer-boss' / 'finished' / 'studio-asset-manifest.json'
HEAD_OFFSET = [3.2153332, 0, 0.0562501]  # the hammer head in the Hammer part's space (Boss_Hammer C1)


def bind_name(name, attributes=None):  # DumpMotorReceipt.luau / EnemyMotion.bind
    return (attributes or {}).get('EnemyBone') or (name[:-len('Motor6D')] if name.endswith('Motor6D') else name)


def receipt_from_manifest():
    entries = json.loads(MANIFEST.read_text(encoding='utf-8')); by = {e['id']: e for e in entries}
    name = lambda i: by[i]['properties']['Name']['v']
    root = next(e for e in entries if e['properties']['Name']['v'] == C.ROOT)
    inv = np.linalg.inv(C.mat(root['properties']['CFrame']['v'])); parts, motors = [], []
    for e in entries:
        pr = e['properties']
        if e['class'] in ('Part', 'MeshPart'):
            parts.append({'name': pr['Name']['v'], 'class': e['class'], 'size': pr['Size']['v'], 'cframe': C.cf(inv @ C.mat(pr['CFrame']['v']))})
        elif e['class'] == 'Motor6D':
            attrs = {k: v['v'] for k, v in (e['attributes'] or {}).items()}
            motors.append({'name': pr['Name']['v'], 'bindName': bind_name(pr['Name']['v'], attrs), 'part0': name(pr['Part0']['v']), 'part1': name(pr['Part1']['v']),
                           'c0': pr['C0']['v'], 'c1': pr['C1']['v']})
    return {'id': 'HammerBoss_NPC', 'scale': 1, 'parts': parts, 'motors': motors}


def receipt():
    return json.loads(C.RECEIPT.read_text(encoding='utf-8')) if C.RECEIPT.exists() else receipt_from_manifest()


def legacy():
    return json.loads(C.LEGACY.read_text(encoding='utf-8'))


def quiet(f, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()) as out:
        return f(*a, **k), out.getvalue()


def raises(f, *a, match=''):
    try:
        f(*a)
    except (ValueError, AssertionError, SystemExit) as error:
        return match in str(error)
    return False


def rotation(rng):
    q = rng.normal(size=4); q /= np.linalg.norm(q); w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def rigid(rng, spread=3.):
    m = np.eye(4); m[:3, :3] = rotation(rng); m[:3, 3] = rng.normal(size=3) * spread; return m


# A small turned rig named like the old template: Root -> Hips -> Chest -> Arm, and Root -> Tool.
NAMES = [('Hips', C.ROOT), ('Chest', 'Hips'), ('Arm', 'Chest'), ('Tool', C.ROOT)]


def synthetic(rng):
    parts = [{'name': C.ROOT, 'class': 'Part', 'size': [2, 2, 1], 'cframe': C.IDENTITY}]
    parts += [{'name': n, 'class': 'MeshPart', 'size': [1, 3, 1], 'cframe': C.cf(rigid(rng))} for n, _ in NAMES]
    motors = [{'name': 'Boss_' + n, 'bindName': bind_name('Boss_' + n), 'part0': p, 'part1': n, 'c0': C.cf(rigid(rng)), 'c1': C.cf(rigid(rng))} for n, p in NAMES]
    frames = [{'time': k / 24, 'poses': {n: C.cf(rigid(rng)) for n, _ in NAMES}} for k in range(5)]
    return {'scale': 1, 'parts': parts, 'motors': motors}, {'fps': 24, 'clips': {'Idle': {'duration': 4 / 24, 'loop': True, 'frames': frames}}}


def copy(x): return json.loads(json.dumps(x))


def test_synthetic_round_trip():
    rec, poses = synthetic(np.random.default_rng(7))
    studio, data, checks = C.convert(poses, rec, {'strideLength': 4}, None)
    assert checks['passed'] and checks['maxCornerError'] < 1e-5, checks
    # T by hand for one joint: P1 = P0 * C0 * T * C1^-1.
    m = {x['bindName']: x for x in rec['motors']}['Boss_Chest']; f = poses['clips']['Idle']['frames'][2]['poses']
    T = C.mat(studio['clips']['Idle']['frames'][2]['transforms']['Boss_Chest'])
    rebuilt = C.mat(f['Hips']) @ C.mat(m['c0']) @ T @ np.linalg.inv(C.mat(m['c1']))
    assert np.abs(rebuilt - C.mat(f['Chest'])).max() < 1e-5
    assert set(studio['clips']['Idle']['frames'][0]['transforms']) == {'Boss_Hips', 'Boss_Chest', 'Boss_Arm', 'Boss_Tool'}
    assert studio['bones']['Boss_Arm']['parent'] == 'Boss_Chest' and studio['bones']['Boss_Hips']['parent'] is None
    assert studio['rigType'] == 'Motor6D' and data['bones']['Arm'] == {'parent': 'Root', 'rest': C.IDENTITY}


def test_rejects_broken_input():
    rec, poses = synthetic(np.random.default_rng(3)); height = C.rig(rec)[2]
    gone = copy(poses); del gone['clips']['Idle']['frames'][1]['poses']['Arm']
    extra = copy(poses); extra['clips']['Idle']['frames'][1]['poses']['Shield'] = C.IDENTITY
    skew = copy(poses); skew['clips']['Idle']['frames'][1]['poses']['Arm'] = [0, 0, 0, 1, .2, 0, 0, 1, 0, 0, 0, 1]
    # A rotation off by 1e-5 is past rounding (POSE_TOLERANCE 2e-6): refused, not snapped.
    near = copy(poses); near['clips']['Idle']['frames'][1]['poses']['Arm'][4] += 1e-5
    rooted = copy(poses); rooted['clips']['Idle']['frames'][1]['poses'][C.ROOT] = [0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]
    still = copy(poses); still['clips']['Idle']['frames'][1]['poses'][C.ROOT] = C.IDENTITY
    one = copy(poses); one['clips']['Idle']['frames'] = one['clips']['Idle']['frames'][:1]
    for bad, match in ((gone, 'missing'), (extra, 'not in the template'), (skew, 'not a rotation'), (near, 'not a rotation'), (rooted, 'identity'), (one, 'fewer than 2')):
        assert raises(C.convert, bad, rec, {}, None, match=match), match
    C.convert(still, rec, {}, None)
    assert raises(C.convert, poses, rec, {}, height + .2, match='root height') and C.convert(poses, rec, {}, height + .01)


def test_round_trip_measures_the_supplied_poses():
    # The gate compares the rebuilt parts with the matrices AS SUPPLIED: with the pose tolerance opened
    # up, a rotation 1e-3 off (about 1.5e-3 studs on a 3-stud part's corners) fails the round trip
    # instead of passing on its snapped copy.
    rec, poses = synthetic(np.random.default_rng(5))
    near = copy(poses); near['clips']['Idle']['frames'][2]['poses']['Arm'][4] += 1e-3
    saved = C.POSE_TOLERANCE
    try:
        C.POSE_TOLERANCE = 1e-2
        assert raises(C.convert, near, rec, {}, None, match='round trip')
    finally:
        C.POSE_TOLERANCE = saved


def test_max_error_gate():
    rec, poses = synthetic(np.random.default_rng(11)); saved = C.MAX_ERROR
    try:
        C.MAX_ERROR = 1e-12
        assert raises(C.convert, poses, rec, {}, None, match='round trip')
    finally:
        C.MAX_ERROR = saved


def test_rig_rejects_bad_receipts():
    rec, _ = synthetic(np.random.default_rng(13))
    def edited(f): r = copy(rec); f(r); return r
    def motor(r, n): return next(m for m in r['motors'] if m['part1'] == n)
    cases = {
        'driven by two': edited(lambda r: r['motors'].append(dict(motor(r, 'Arm'), name='Boss_Arm2', bindName='Boss_Arm2'))),
        'two joints bind as': edited(lambda r: motor(r, 'Tool').update(bindName='Boss_Arm')),
        'not reachable': edited(lambda r: motor(r, 'Hips').update(part0='Chest')),          # Hips <-> Chest cycle
        'not reachable ': edited(lambda r: motor(r, 'Tool').update(part0='Ghost')),         # Part0 outside the tree
        'no HumanoidRootPart': edited(lambda r: r.__setitem__('parts', [p for p in r['parts'] if p['name'] != C.ROOT])),
        'scale is 1.15': edited(lambda r: r.__setitem__('scale', 1.15)),
        'scale is None': edited(lambda r: r.pop('scale')),
    }
    for match, r in cases.items():
        assert raises(C.rig, r, match=match.strip()), match


def test_frame_key_variants():
    rec, poses = synthetic(np.random.default_rng(17)); outs = []
    for key in ('poses', 'parts', 'transforms', None):
        p = copy(poses)
        for f in p['clips']['Idle']['frames']:
            parts = f.pop('poses')
            if key: f[key] = parts
            else: f.update(parts)
        outs.append(json.dumps(C.convert(p, rec, {}, None)[:2]))
    assert len(set(outs)) == 1


def test_deterministic():
    rec = receipt(); poses = C.legacy_poses(legacy(), rec)
    one, two = (json.dumps(C.convert(poses, rec, {}, None)) for _ in range(2))
    assert one == two and not re.search(r'-0\.0[,\]]', one)
    with tempfile.TemporaryDirectory() as tmp:
        game = Path(tmp) / 'boss' / 'exports' / 'game'; game.mkdir(parents=True)
        (game / 'PartPoses.json').write_text(json.dumps(poses), encoding='utf-8'); (Path(tmp) / 'r.json').write_text(json.dumps(rec), encoding='utf-8')
        a, b = (quiet(C.package, Path(tmp) / 'boss', Path(tmp) / 'r.json')[0][1] for _ in range(2))
        assert a == b and not any((game / n).exists() for n in C.OUTPUTS)  # package() writes nothing


def test_legacy_round_trip():
    # The real data: the old clips' part CFrames (pose * BossRest, BossMotion.apply) come back through
    # the template's C0/C1 within 1e-4 studs (centres and box corners), against the supplied and the
    # unrounded ones, keyed by the template's own joint names (Boss_<Part>).
    rec = receipt(); checks = C.legacy_check(C.RECEIPT) if C.RECEIPT.exists() else None
    poses = C.legacy_poses(legacy(), rec); studio, data, conv = C.convert(poses, rec, {}, None)
    checks = checks or conv
    assert conv['passed'] and conv['jointCount'] == 16 and conv['clipCount'] == len(legacy()['clips']), conv
    assert max(conv['maxCentreError'], conv['maxCornerError']) < C.MAX_ERROR, conv
    assert abs(conv['rootHeight'] - legacy()['rootHeight']) < 1e-3, conv
    parts = {m['part1'] for m in rec['motors']}
    assert set(studio['bones']) == {'Boss_' + p for p in parts} == set(studio['clips']['Idle']['frames'][0]['transforms'])
    joints, box, _ = C.rig(rec); unrounded = 0.
    for name, clip in C.legacy_poses(legacy(), rec, exact=True)['clips'].items():
        for frame, out in zip(clip['frames'], studio['clips'][name]['frames']):
            Q = {C.ROOT: np.eye(4)}
            for j in joints: Q[j['part1']] = Q[j['part0']] @ j['c0'] @ C.mat(out['transforms'][j['name']]) @ np.linalg.inv(j['c1'])
            for p, m in frame['parts'].items(): unrounded = max(unrounded, float(np.abs((Q[p] - m) @ C.corners(box[p]['size'])).max()))
    assert unrounded < C.MAX_ERROR, unrounded
    print(f'  legacy round trip: centre {conv["maxCentreError"]:.2e}, corner {conv["maxCornerError"]:.2e}, vs unrounded {unrounded:.2e} studs over {conv["frameCount"]} frames')


def test_points_in_ground_frame():
    # build_boss_modules samples a part bone's offset (Studio part space) where the old runtime has it:
    # the hammer head (BossMotion.head: pose.Hammer * hammerHeadRest) plus the root height.
    rec = receipt(); boss = legacy(); _, data, _ = C.convert(C.legacy_poses(boss, rec), rec, {}, None)
    rest = {p['name']: C.mat(p['cframe']) for p in rec['parts']}
    head = C.mat(boss['hammerHeadRest']); offset = (np.linalg.inv(rest['Hammer']) @ head)[:3, 3]
    assert np.abs(offset - HEAD_OFFSET).max() < 1e-4, offset
    worst = 0.
    for clip in ('Slam', 'Swing', 'Spin'):
        frames = boss['clips'][clip]['frames']; fps = boss['clips'][clip]['fps']
        for i, frame in enumerate(frames):
            want = (C.mat(frame['Hammer']) @ head)[:3, 3] + [0, boss['rootHeight'], 0]
            got = B.sample_point(data, clip, 'Hammer', list(offset), i / fps)
            worst = max(worst, float(np.abs(np.array(got) - want).max()))
    assert worst < 1e-4, worst
    assert abs(data['rootHeight'] - data['bones']['Root']['rest'][1]) < 1e-9 and abs(data['rootHeight'] - 4.45) < 1e-3


def test_renders_like_the_other_bosses():
    # The Motor6D package goes through build_boss_modules.render_animations unchanged, with the same
    # top-level keys as a Bone package.
    rec = receipt(); studio, _, _ = C.convert(C.legacy_poses(legacy(), rec), rec, {'strideLength': 4}, None)
    crab = json.loads((C.PLANNING / 'king-crab-boss' / 'exports' / 'game' / 'StudioAnimationData.json').read_text(encoding='utf-8'))
    assert set(crab) - {'sourceAnimationHash', 'importReceiptHash'} == set(studio)
    B.ATTACKS['legacy-test'], B.FOLDERS['legacy-test'] = ['Slam', 'Swing', 'Spin', 'ChargeStart', 'ChargeRun'], 'hammer-boss'
    try:
        files, largest = B.render_animations('legacy-test', studio)
    finally:
        del B.ATTACKS['legacy-test'], B.FOLDERS['legacy-test']
    assert 'init.luau' in files and largest < B.LIMIT and any(k.startswith('Idle') for k in files)
    frame = studio['clips']['Slam']['frames'][23]
    assert all(len(v) == 12 and all(math.isfinite(x) for x in v) for v in frame['transforms'].values())


# --- build_boss_modules.main on a temporary planning folder -------------------------------------
def attack(clip, fps, impact, active, last):
    return {'duration': last / fps, 'warnStart': .1, 'impact': impact / fps, 'activeEnd': active / fps, 'recoveryEnd': last / fps,
            'points': {'HammerFace': {'bone': 'Hammer', 'offset': HEAD_OFFSET}}}


@contextlib.contextmanager
def sandbox(clips=None, with_receipt=True):
    """A planning folder with one part-pose boss 'x-test' (the legacy clips as PartPoses), and the
    build's outputs pointed into it. Yields (tmp, game folder)."""
    rec, boss = receipt(), legacy(); poses = C.legacy_poses(boss, rec)
    if clips: poses['clips'] = {k: v for k, v in poses['clips'].items() if k in clips}
    poses['motion'] = {'strideLength': 4, 'nominalSpeed': 4.5}
    game_data = {'height': 11.92, 'footprintRadius': 4, 'bodyCentreHeight': 4.45,
                 'attacks': {'Slam': attack('Slam', 30, 23, 24, 50), 'Swing': attack('Swing', 30, 19, 25, 54), 'Spin': attack('Spin', 36, 21, 37, 66)}}
    saved = {k: getattr(B, k) for k in ('PLANNING', 'HERE', 'OUT', 'FOLDERS', 'PART_POSES', 'ATTACKS')}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp); game = tmp / 'boss' / 'exports' / 'game'; game.mkdir(parents=True)
        (game / 'PartPoses.json').write_text(json.dumps(poses), encoding='utf-8')
        (game / 'BossGameData.json').write_text(json.dumps(game_data), encoding='utf-8')
        if with_receipt: (tmp / 'receipt.json').write_text(json.dumps(rec), encoding='utf-8')
        try:
            B.PLANNING, B.HERE, B.OUT = tmp, tmp, tmp / 'BossAnimations'
            B.FOLDERS = {'x-test': 'boss'}; B.PART_POSES = {'x-test': tmp / 'receipt.json'}; B.ATTACKS = {'x-test': ['Slam', 'Swing', 'Spin']}
            yield tmp, game
        finally:
            for k, v in saved.items(): setattr(B, k, v)


def test_main_builds_a_part_pose_boss():
    with sandbox() as (tmp, game):
        _, printed = quiet(B.main, ['x-test'], False)
        assert (tmp / 'BossAnimations' / 'x-test' / 'init.luau').exists() and (tmp / 'MapBossTiming.luau').exists(), printed
        entry = B.existing(tmp / 'MapBossTiming.luau')['x-test']
        assert entry['rootHeight'] == 4.45 and set(entry['attacks']) == {'Slam', 'Swing', 'Spin'}
        assert all((game / n).exists() for n in C.OUTPUTS) and json.loads((game / 'StudioRetargetChecks.json').read_text())['passed']
        # The Slam's sampled head at impact is where the old runtime put it (+ the root height).
        boss = legacy()
        # Every 1/24 s sample is the old runtime's head on the 30 fps frame the build reads.
        for got in entry['attacks']['Slam']['samples']['HammerFace']:
            k = int(round(round(got[0] * 24) / 24 * 30)); frame = boss['clips']['Slam']['frames'][k]  # as frame_index reads i / 24
            want = (C.mat(frame['Hammer']) @ C.mat(boss['hammerHeadRest']))[:3, 3] + [0, 4.45, 0]
            assert np.abs(np.array(got[1:]) - want).max() < 1e-4, (got, want)


def test_main_missing_receipt():
    # A plain run skips the boss (and writes nothing); naming it stops the run.
    with sandbox(with_receipt=False) as (tmp, game):
        _, printed = quiet(B.main, ['x-test'], False)
        assert 'x-test: skipped (receipt / clips incomplete' in printed and 'Nothing built' in printed, printed
        assert not (tmp / 'MapBossTiming.luau').exists() and not any((game / n).exists() for n in C.OUTPUTS)
        assert raises(quiet, B.main, ['x-test'], True, match='not converted')


def test_main_incomplete_clips():
    # Receipt there, but only Idle, Walk and Slam authored (the moves sample): skipped in a plain run,
    # an error when named; either way nothing is written, not even the derived package files.
    with sandbox(clips={'Idle', 'Walk', 'Slam'}) as (tmp, game):
        _, printed = quiet(B.main, ['x-test'], False)
        assert 'x-test: skipped (receipt / clips incomplete' in printed and 'missing clips' in printed, printed
        assert raises(quiet, B.main, ['x-test'], True, match='missing clips')
        assert not (tmp / 'MapBossTiming.luau').exists() and not (tmp / 'BossAnimations').exists() and not any((game / n).exists() for n in C.OUTPUTS)


def test_convert_part_poses_hook():
    with sandbox() as (tmp, game):
        outputs, studio, data = B.convert_part_poses('x-test', game)
        assert set(outputs) == set(C.OUTPUTS) and data['rootHeight'] == 4.45 and not any((game / n).exists() for n in C.OUTPUTS)
        assert B.convert_part_poses('king-crab', game) is None
    assert B.FOLDERS['hammer-brute'] == 'hammer-boss-moves' and B.PART_POSES['hammer-brute'] == C.RECEIPT


if __name__ == '__main__':
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn(); print('PASS', name)
            except Exception as error:  # noqa: BLE001
                failed += 1; print('FAIL', name, repr(error)[:300])
    print(f'{failed} failed')
    sys.exit(1 if failed else 0)
