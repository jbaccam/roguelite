"""Checks for partposes_to_motor6d.py (Hammer on the old template, R9, 2026-10-04). Reads the repo,
writes nothing outside a temporary folder.
    python test_partposes_to_motor6d.py      (or: python -m pytest test_partposes_to_motor6d.py)
The legacy checks use receipts/hammer-old-receipt.json (the Studio dump), or, before it exists, a
receipt made from hammer-boss/finished/studio-asset-manifest.json.
"""
import contextlib, io, json, math, sys, tempfile
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import partposes_to_motor6d as C  # noqa: E402
import build_boss_modules as B  # noqa: E402

MANIFEST = C.PLANNING / 'hammer-boss' / 'finished' / 'studio-asset-manifest.json'


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
            motors.append({'name': pr['Name']['v'], 'bindName': pr['Name']['v'], 'part0': name(pr['Part0']['v']), 'part1': name(pr['Part1']['v']),
                           'c0': pr['C0']['v'], 'c1': pr['C1']['v']})
    return {'id': 'HammerBoss_NPC', 'scale': 1, 'parts': parts, 'motors': motors}


def receipt():
    return json.loads(C.RECEIPT.read_text(encoding='utf-8')) if C.RECEIPT.exists() else receipt_from_manifest()


def legacy():
    return json.loads(C.LEGACY.read_text(encoding='utf-8'))


def rotation(rng):
    q = rng.normal(size=4); q /= np.linalg.norm(q); w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def rigid(rng, spread=3.):
    m = np.eye(4); m[:3, :3] = rotation(rng); m[:3, 3] = rng.normal(size=3) * spread; return m


# A small chain with turned joints: Root -> Hips -> Chest -> Arm, and Root -> Tool (a branch on the root).
def synthetic(rng):
    names = [('Hips', C.ROOT), ('Chest', 'Hips'), ('Arm', 'Chest'), ('Tool', C.ROOT)]
    parts = [{'name': C.ROOT, 'class': 'Part', 'size': [2, 2, 1], 'cframe': C.IDENTITY}]
    parts += [{'name': n, 'class': 'MeshPart', 'size': [1, 3, 1], 'cframe': C.cf(rigid(rng))} for n, _ in names]
    motors = [{'name': n + 'Motor6D', 'bindName': n, 'part0': p, 'part1': n, 'c0': C.cf(rigid(rng)), 'c1': C.cf(rigid(rng))} for n, p in names]
    frames = [{'time': k / 24, 'parts': {n: C.cf(rigid(rng)) for n, _ in names}} for k in range(5)]
    return {'scale': 1, 'parts': parts, 'motors': motors}, {'fps': 24, 'clips': {'Idle': {'duration': 4 / 24, 'loop': True, 'frames': frames}}}


def test_synthetic_round_trip():
    rec, poses = synthetic(np.random.default_rng(7))
    studio, data, checks = C.convert(poses, rec, {'strideLength': 4}, rec_height(rec))
    assert checks['passed'] and checks['maxCornerError'] < 1e-5, checks
    # T by hand for one joint: P1 = P0 * C0 * T * C1^-1.
    m = {x['bindName']: x for x in rec['motors']}['Chest']; f = poses['clips']['Idle']['frames'][2]['parts']
    T = C.mat(studio['clips']['Idle']['frames'][2]['transforms']['Chest'])
    rebuilt = C.mat(f['Hips']) @ C.mat(m['c0']) @ T @ np.linalg.inv(C.mat(m['c1']))
    assert np.abs(rebuilt - C.mat(f['Chest'])).max() < 1e-5
    assert set(studio['clips']['Idle']['frames'][0]['transforms']) == {'Hips', 'Chest', 'Arm', 'Tool'}
    assert studio['bones']['Arm']['parent'] == 'Chest' and studio['bones']['Hips']['parent'] is None
    assert studio['rigType'] == 'Motor6D' and data['bones']['Arm'] == {'parent': 'Root', 'rest': C.IDENTITY}


def rec_height(rec):
    return C.rig(rec)[2]


def test_rejects_broken_input():
    rec, poses = synthetic(np.random.default_rng(3))
    def fails(p, r=rec, height=None):
        try:
            C.convert(p, r, {}, height)
        except ValueError:
            return True
        return False
    gone = json.loads(json.dumps(poses)); del gone['clips']['Idle']['frames'][1]['parts']['Arm']
    extra = json.loads(json.dumps(poses)); extra['clips']['Idle']['frames'][1]['parts']['Shield'] = C.IDENTITY
    skew = json.loads(json.dumps(poses)); skew['clips']['Idle']['frames'][1]['parts']['Arm'] = [0, 0, 0, 1, .2, 0, 0, 1, 0, 0, 0, 1]
    rooted = json.loads(json.dumps(poses)); rooted['clips']['Idle']['frames'][1]['parts'][C.ROOT] = [0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]
    still = json.loads(json.dumps(poses)); still['clips']['Idle']['frames'][1]['parts'][C.ROOT] = C.IDENTITY
    assert fails(gone) and fails(extra) and fails(skew) and fails(rooted) and not fails(still)
    assert fails(poses, height=rec_height(rec) + .2) and not fails(poses, height=rec_height(rec) + .01)


def test_legacy_round_trip():
    # The real data: the old clips' part CFrames (pose * BossRest, BossMotion.apply) come back through
    # the template's C0/C1 within 1e-4 studs (centres and box corners), against the exact and the raw ones.
    rec = receipt(); poses = C.legacy_poses(legacy(), rec)
    studio, data, checks = C.convert(poses, rec, {}, None)
    assert checks['passed'] and checks['jointCount'] == 16 and checks['clipCount'] == len(legacy()['clips']), checks
    assert max(checks['maxCentreError'], checks['maxCornerError']) < C.MAX_ERROR, checks
    assert abs(checks['rootHeight'] - legacy()['rootHeight']) < .01, checks
    assert set(studio['bones']) == {m['bindName'] for m in rec['motors']}
    joints, parts, _ = C.rig(rec); raw = 0.
    for name, clip in poses['clips'].items():
        for frame, out in zip(clip['frames'], studio['clips'][name]['frames']):
            Q = {C.ROOT: np.eye(4)}
            for j in joints: Q[j['part1']] = Q[j['part0']] @ j['c0'] @ C.mat(out['transforms'][j['name']]) @ np.linalg.inv(j['c1'])
            for p, v in frame['parts'].items(): raw = max(raw, float(np.abs((Q[p] - C.mat(v)) @ C.corners(parts[p]['size'])).max()))
    assert raw < C.MAX_ERROR, raw
    print(f'  legacy round trip: centre {checks["maxCentreError"]:.2e}, corner {checks["maxCornerError"]:.2e}, vs raw {raw:.2e} studs over {checks["frameCount"]} frames')


def test_points_in_ground_frame():
    # build_boss_modules samples a part bone's offset (Studio part space) where the old runtime has it:
    # the hammer head (BossMotion.head: pose.Hammer * hammerHeadRest) plus the root height.
    rec = receipt(); boss = legacy(); _, data, _ = C.convert(C.legacy_poses(boss, rec), rec, {}, None)
    rest = {p['name']: C.mat(p['cframe']) for p in rec['parts']}
    head = C.mat(boss['hammerHeadRest']); offset = (np.linalg.inv(rest['Hammer']) @ head)[:3, 3]
    worst = 0.
    for clip in ('Slam', 'Swing', 'Spin'):
        frames = boss['clips'][clip]['frames']; fps = boss['clips'][clip]['fps']
        for i, frame in enumerate(frames):
            want = (C.mat(frame['Hammer']) @ head)[:3, 3] + [0, boss['rootHeight'], 0]
            got = B.sample_point(data, clip, 'Hammer', list(offset), i / fps)
            worst = max(worst, float(np.abs(np.array(got) - want).max()))
    assert worst < 1e-5, worst
    assert data['rootHeight'] == data['bones']['Root']['rest'][1]


def test_renders_like_the_other_bosses():
    # The Motor6D package goes through build_boss_modules.render_animations unchanged, with the same
    # top-level keys as a Bone package (plus nothing the client needs to know about).
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


def test_build_converts_part_poses():
    # build_boss_modules runs the converter for a PART_POSES boss whose PartPoses.json is there, and
    # leaves every other package alone.
    rec = receipt(); poses = C.legacy_poses(legacy(), rec)
    poses['clips'] = {k: poses['clips'][k] for k in ('Idle', 'Slam')}; poses['motion'] = {'strideLength': 4, 'nominalSpeed': 4.5}
    with tempfile.TemporaryDirectory() as tmp:
        game = Path(tmp) / 'boss' / 'exports' / 'game'; game.mkdir(parents=True)
        (game / 'PartPoses.json').write_text(json.dumps(poses), encoding='utf-8')
        (Path(tmp) / 'receipt.json').write_text(json.dumps(rec), encoding='utf-8')
        B.PART_POSES['x-test'] = Path(tmp) / 'receipt.json'
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                assert B.convert_part_poses('x-test', game)
            assert not B.convert_part_poses('king-crab', game)
        finally:
            del B.PART_POSES['x-test']
        studio = json.loads((game / 'StudioAnimationData.json').read_text(encoding='utf-8'))
        data = json.loads((game / 'AnimationData.json').read_text(encoding='utf-8'))
        assert set(studio['clips']) == {'Idle', 'Slam'} and studio['motion']['strideLength'] == 4 and data['rootHeight'] == 4.45
        assert json.loads((game / 'StudioRetargetChecks.json').read_text(encoding='utf-8'))['passed']
        # The timing reads that root height when BossGameData has no bodyCentreHeight.
        B.ATTACKS['x-test'] = []
        try:
            entry = B.timing('x-test', data, {'height': 11.92, 'footprintRadius': 4})
        finally:
            del B.ATTACKS['x-test']
        assert entry['rootHeight'] == 4.45 and entry['strideLength'] == 4
    assert B.FOLDERS['hammer-brute'] == 'hammer-boss-moves'


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
