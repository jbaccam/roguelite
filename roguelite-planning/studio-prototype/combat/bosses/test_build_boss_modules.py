"""Checks for build_boss_modules.py (Hammer Brute rebuild R6 review, 2026-10-03). Reads the repo, writes
nothing outside a temporary folder.
    python test_build_boss_modules.py      (or: python -m pytest test_build_boss_modules.py)
"""
import contextlib, io, json, math, re, sys, tempfile
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


def test_wave_phase_contract():
    # Rubble waves (2026-10-09): the baker writes the Slam's wave as its own phase with the circle's times,
    # [circle, wave] (SpinSlam: [rev1, rev2, circle, wave]). Both pass through with those times and the
    # clip's HammerFace track (no samples of their own), which MapBossService X.phaseWindows reads by index.
    slam = {'duration': 1.0, 'warnStart': .25, 'impact': .5, 'activeEnd': .5, 'recoveryEnd': 1.0, 'points': {'HammerFace': dict(FACE)},
            'phases': [{'warnStart': .25, 'impact': .5, 'activeEnd': .5, 'points': {'HammerFace': dict(FACE)}},
                       {'warnStart': .25, 'impact': .5, 'activeEnd': .5, 'points': {'HammerFace': dict(FACE)}}]}
    entry, printed = run_timing(slam)
    circle, wave = entry['attacks']['Combo']['phases']
    assert circle == wave and {k: circle[k] for k in ('warnStart', 'impact', 'activeEnd')} == {'warnStart': .25, 'impact': .5, 'activeEnd': .5}
    assert 'samples' not in wave and wave['points']['HammerFace']['rootAtImpactStudio'] == [-13, .5, 0]
    assert 'WARN' not in printed, printed
    # The clip list the runtime plays (MapBossDefs.ATTACK_CLIPS): no IntroLand, Roar or ChargeSlam.
    assert B.BASIC + B.ATTACKS['hammer-brute'] == ['Idle', 'Walk', 'Hit', 'Death', 'Slam', 'Swing', 'Spin', 'SwingSpin', 'SpinSlam', 'ChargeStart', 'ChargeRun']



def test_four_bosses_rebuild_byte_identical():
    # Clips without their own fps keep the 1/24 s grid and no key-time samples (2026-10-09): the four
    # bosses' entries rebuilt from their packages equal today's MapBossTiming, byte for byte.
    table = B.existing()
    for id in ('king-crab', 'frost-cyclops', 'pharaoh', 'dragon'):
        game_dir = B.PLANNING / B.FOLDERS[id] / 'exports' / 'game'
        data = json.loads((game_dir / 'AnimationData.json').read_text(encoding='utf-8'))
        game = json.loads((game_dir / 'BossGameData.json').read_text(encoding='utf-8'))
        with contextlib.redirect_stdout(io.StringIO()):
            entry = B.timing(id, data, game)
        assert json.dumps(entry, separators=(',', ':')) == json.dumps(table[id], separators=(',', ':')), id


# A Hammer bone turning a quarter turn every 60 fps frame in the Studio X-Y plane (k*90 degrees on frame
# k, so off-frame times need the blended pose): a point 1 stud out along bone X stays 1 stud from the
# pivot, at (-cos, sin, 0) of t*60*90 degrees.
def spinning(fps=60, n=13):
    ident = [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]
    def rz(k):  # about the swapped basis' z (Blender z = Studio up)
        c, s = math.cos(k * math.pi / 2), math.sin(k * math.pi / 2)
        return [0, 0, 0, c, -s, 0, s, c, 0, 0, 0, 1]
    frames = [{'time': k / fps, 'transforms': {'Hammer': rz(k)}} for k in range(n)]
    clip = {'duration': (n - 1) / fps, 'loop': False, 'fps': fps, 'frames': frames}
    return {'id': 'synthetic', 'fps': 24, 'bones': {'Root': {'parent': None, 'rest': ident}, 'Hammer': {'parent': 'Root', 'rest': ident}},
            'clips': {'Combo': clip}}


def test_own_fps_sample_times():
    # A 60 fps clip: every 1/60 s from warnStart to recoveryEnd, plus each key time of the attack and its
    # phases that falls between two frames (.105, .1375); on-frame ones (.05) and ones outside (.5) add nothing.
    data = spinning()
    attack = {'warnStart': .05, 'impact': .105, 'activeEnd': .15, 'recoveryEnd': .2,
              'phases': [{'warnStart': .05, 'impact': .1375, 'activeEnd': .5}]}
    times = B.sample_times(data, 'Combo', attack)
    assert [round(t, 5) for t in times] == sorted([round(k / 60, 5) for k in range(3, 13)] + [.105, .1375]), times
    # Capped at MAX_HZ: a 120 fps clip samples every 1/60 s (plus its key times).
    data120 = spinning(120, 25)
    assert [round(t, 5) for t in B.sample_times(data120, 'Combo', {'warnStart': 0, 'impact': .1, 'activeEnd': .1, 'recoveryEnd': .2})] == [round(k / 60, 5) for k in range(13)]
    # No own fps: the 1/24 s grid only, key times ignored.
    del data['clips']['Combo']['fps']
    assert B.sample_times(data, 'Combo', dict(attack, warnStart=0, recoveryEnd=.5)) == [k / 24 for k in range(0, 13)]


def test_own_fps_key_sample_is_exact():
    # The key-time sample poses the bone between its frames: at t = 1.5/60 the point is at 135 degrees on
    # the unit circle (the chord's lerp would sit 0.29 studs inside it), and the impact track reads it exactly.
    data = spinning()
    attack = {'warnStart': 0, 'impact': 1.5 / 60, 'activeEnd': 2 / 60, 'recoveryEnd': .2, 'points': {'HammerFace': {'bone': 'Hammer', 'offset': [1, 0, 0]}}}
    B.sample_attack('synthetic', 'Combo', data, attack)
    track = attack['samples']['HammerFace']
    assert len(track) == 14 and [s[0] for s in track] == sorted(s[0] for s in track)
    at = next(s for s in track if s[0] == round(1.5 / 60, 5))
    a = math.radians(135)
    assert max(abs(u - v) for u, v in zip(at[1:], [-math.cos(a), math.sin(a), 0])) < 1e-4, at
    # On-frame samples are the frames themselves: frame 1 is a quarter turn.
    assert next(s for s in track if s[0] == round(1 / 60, 5))[1:] == B.r6([-0.0, 1, 0])

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
