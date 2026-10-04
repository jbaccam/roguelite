"""Checks for build_boss_modules.py (Hammer Brute rebuild R6 review, 2026-10-03). Reads the repo, writes
nothing outside a temporary folder.
    python test_build_boss_modules.py      (or: python -m pytest test_build_boss_modules.py)
"""
import contextlib, io, json, re, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_boss_modules as B  # noqa: E402


def test_existing_round_trip():
    # Re-dumping today's MapBossTiming through existing() gives the same file, byte for byte: a
    # one-boss run keeps the other bosses' entries exactly as they were.
    on_disk = (HERE / 'MapBossTiming.luau').read_text(encoding='utf-8')
    assert B.timing_source(B.existing()) == on_disk


def test_existing_only_missing_is_empty():
    with tempfile.TemporaryDirectory() as tmp:
        assert B.existing(Path(tmp) / 'MapBossTiming.luau') == {}
        for bad in ('return nil\n', 'return game:GetService("HttpService"):JSONDecode([=[{"king-crab":{"rootHeight":4,]=])\n'):
            path = Path(tmp) / 'MapBossTiming.luau'; path.write_text(bad, encoding='utf-8')
            try:
                B.existing(path)
            except ValueError:
                continue
            raise AssertionError('a malformed MapBossTiming read as a table: ' + bad[:30])


def test_check_complete():
    B.check_complete(B.existing())  # today's file covers every BossAnimations folder
    try:
        B.check_complete({k: v for k, v in B.existing().items() if k != 'dragon'})
    except SystemExit as stop:
        assert 'dragon' in str(stop)
    else:
        raise AssertionError('a table without the dragon passed')


def test_attacks_match_lua():
    # build_boss_modules.ATTACKS mirrors MapBossDefs.ATTACK_CLIPS.
    text = (HERE / 'MapBossDefs.luau').read_text(encoding='utf-8')
    block = text[text.index('D.ATTACK_CLIPS='):]
    block = block[:block.index('\nfunction ')]
    lua = {anim: re.findall(r"'([^']+)'", body) for anim, body in re.findall(r"\['([^']+)'\]=\{([^}]*)\}", block)}
    assert lua == B.ATTACKS, (lua, B.ATTACKS)


def test_last_sample_at_30_fps():
    frames30 = [None] * 31  # 1 s at 30 fps
    assert B.last_sample(frames30, 30, 1.0) == 24 and B.last_sample(frames30, 30, .5) == 12
    assert B.last_sample([None] * 25, 24, 1.0) == 24


# A two-bone rig whose Hammer bone slides +X one stud per 24 fps frame: a point at Blender offset
# (ox, oy, oz) on it is at Studio ground frame (-(k + ox), oz + groundOffset, oy) on frame k.
def synthetic(attack):
    ident = [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]
    frames = [{'time': k / 24, 'transforms': {'Hammer': [k, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]}} for k in range(25)]
    clip = {'duration': 1.0, 'loop': False, 'frames': frames}
    data = {'id': 'synthetic', 'fps': 24, 'bones': {'Root': {'parent': None, 'rest': ident}, 'Hammer': {'parent': 'Root', 'rest': ident}},
            'clips': {'Idle': clip, 'Combo': clip}, 'motion': {'strideLength': 13, 'nominalSpeed': 20, 'chargeStrideLength': 17}}
    game = {'height': 13.7, 'rootHeight': 5, 'footprintRadius': 4, 'groundOffset': .5, 'attacks': {'Combo': attack}}
    return data, game


FACE = {'bone': 'Hammer', 'offset': [1, 0, 0], 'rootAtImpactStudio': [-13, 0, 0]}        # at impact .5 (k = 12)
GRIP = {'bone': 'Hammer', 'offset': [0, 2, 0], 'rootAtImpactStudio': [-19.2, 0, 2]}      # at impact .8 (k = 19.2)


def combo(grip=GRIP):
    return {'duration': 1.0, 'warnStart': .25, 'impact': .5, 'activeEnd': .9, 'recoveryEnd': 1.0, 'points': {'HammerFace': dict(FACE)},
            'phases': [{'warnStart': .25, 'impact': .5, 'activeEnd': .6, 'points': {'HammerFace': dict(FACE)}},
                       {'warnStart': .25, 'impact': .8, 'activeEnd': .9, 'points': {'HammerFace': dict(FACE, rootAtImpactStudio=[-20.2, 0, 0]), 'HammerGrip': dict(grip)}},
                       {'warnStart': .25, 'impact': .85, 'activeEnd': .9}]}


def run_timing(attack):
    B.ATTACKS['synthetic'] = ['Combo']
    try:
        data, game = synthetic(attack)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            entry = B.timing('synthetic', data, game)
        return entry, out.getvalue()
    finally:
        del B.ATTACKS['synthetic']


def test_phase_entries():
    entry, printed = run_timing(combo())
    a = entry['attacks']['Combo']; p1, p2, p3 = a['phases']
    face = a['samples']['HammerFace']
    assert entry['chargeStrideLength'] == 17
    # The clip's track: frames 6 (warnStart .25) to 24 (recoveryEnd 1), measured from the soles.
    assert [s[0] for s in face] == [round(k / 24, 5) for k in range(6, 25)] and face[6] == [.5, -13.0, .5, 0.0]
    # Phase 1: same point as the clip, so no samples of its own (it inherits the clip's at runtime).
    assert 'samples' not in p1 and p1['points']['HammerFace']['rootAtImpactStudio'] == [-13, .5, 0] and p1['impact'] == .5
    # Phase 2: HammerGrip isn't tracked by the clip, so it carries the clip's tracks plus its own.
    assert set(p2['samples']) == {'HammerFace', 'HammerGrip'} and p2['samples']['HammerFace'] == face
    assert all(s[1:] == [-float(round(s[0] * 24)), .5, 2.0] for s in p2['samples']['HammerGrip'])
    # Phase 3: times only.
    assert p3 == {'warnStart': .25, 'impact': .85, 'activeEnd': .9}
    assert 'WARN' not in printed, printed
    # A phase point that disagrees with its clip is flagged (here 1 stud off).
    _, printed = run_timing(combo(dict(GRIP, rootAtImpactStudio=[-18.2, 0, 2])))
    assert 'WARN synthetic Combo phase 2 HammerGrip' in printed, printed


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
