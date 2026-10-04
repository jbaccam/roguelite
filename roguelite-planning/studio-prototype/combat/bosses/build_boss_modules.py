"""Build the map-boss animation modules and MapBossTiming (plan F Task 3).

Based on studio-prototype/combat/build_enemy_animation_modules.py (same 190,000-character
chunking into Frames sub-modules). For each boss it reads
  <asset-folder>/exports/game/StudioAnimationData.json   (retarget_boss.py output) -> BossAnimations/<id>/
  <asset-folder>/exports/game/AnimationData.json         (original clips, for point sampling)
  <asset-folder>/exports/game/BossGameData.json          (attack times and named points)
and writes MapBossTiming.luau. Gameplay points are re-sampled every 1/24 s from warnStart to
recoveryEnd by forward kinematics over the ORIGINAL bones, in the boss's ground frame, Studio axes
(a clip authored at another rate, AnimationData clip "fps", is read at its own frames).

Hammer Brute rebuild (R6, 2026-10-03). All of it is optional, so the other four come out byte-identical:
  phases: a combo's hits in order (BossGameData attacks.<Clip>.phases), each with its own times and
    points. A phase inherits its clip's sampled tracks in the runtime (MapBossService
    X.phaseWindows). A phase point on another bone or offset than the clip's point of that name
    is sampled here, and the phase then carries the clip's tracks plus its own.
  chargeStrideLength: studs per ChargeRun cycle (motion, BossGameData, or attacks.ChargeRun).
  IntroLand and ChargeSlam (the charge's finish slam) need attack timing entries like the attacks;
  Roar, ChargeStart and ChargeRun need durations only (DURATION_ONLY).
Hammer on the old template (R9, 2026-10-04): his clips are re-authored as part poses on the original
16-part Motor6D template (hammer-boss-moves). When <asset-folder>/exports/game/PartPoses.json is
there, partposes_to_motor6d.py first writes StudioAnimationData.json and AnimationData.json from it
and receipts/hammer-old-receipt.json (PART_POSES); the rest of the build is the same. Their
AnimationData carries rootHeight (the template's HumanoidRootPart above its soles), used when
BossGameData has no bodyCentreHeight.

Usage: python build_boss_modules.py [id ...]   (default: every boss in FOLDERS)
A boss whose exports/game package isn't there yet is skipped with a message. MapBossTiming keeps
the entry of every boss not rebuilt in this run, so `python build_boss_modules.py hammer-brute`
adds the Hammer without dropping the other four. Everything is computed and checked before anything
is written: a failed assert, or a MapBossTiming that would lose a boss whose BossAnimations folder
exists (an unreadable MapBossTiming.luau), writes nothing and exits non-zero.
Tests: python test_build_boss_modules.py
"""
import json, math, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
PLANNING = HERE.parents[2]
OUT = HERE / 'BossAnimations'
LIMIT = 190000
FOLDERS = {'king-crab': 'king-crab-boss', 'frost-cyclops': 'frost-cyclops-boss', 'pharaoh': 'pharaoh-boss', 'dragon': 'dragon-boss',
           'hammer-brute': 'hammer-boss-moves'}
# Bosses whose clips arrive as part poses on a Motor6D template: id -> that template's receipt (R9).
PART_POSES = {'hammer-brute': HERE / 'receipts' / 'hammer-old-receipt.json'}
# Mirrors MapBossDefs.ATTACK_CLIPS.
ATTACKS = {
    'king-crab': ['ClawCrush', 'RushStart', 'RushLoop', 'RushEnd', 'BubbleBarrage'],
    'frost-cyclops': ['GroundSlam', 'Stomp'],
    'pharaoh': ['CursedBolts', 'TombEruption'],
    'dragon': ['FireBreath', 'TailWhip', 'FrontStomp'],
    'hammer-brute': ['Slam', 'Swing', 'Spin', 'SwingSpin', 'SpinSlam', 'ChargeStart', 'ChargeRun', 'ChargeSlam', 'IntroLand', 'Roar'],
}
BASIC = ['Idle', 'Walk', 'Hit', 'Death']
# Clips the runtime needs only the durations of (MapBossTiming clips): their attack timing isn't required.
DURATION_ONLY = {'RushStart', 'RushLoop', 'RushEnd', 'ChargeStart', 'ChargeRun', 'Roar'}
PACKAGE = ['StudioAnimationData.json', 'AnimationData.json', 'BossGameData.json']
# Points whose forward direction is stored per sample (bolts, breath, bubbles).
DIRECTED = {('pharaoh', 'CursedBolts'): 'BoltOrigin', ('dragon', 'FireBreath'): 'FireOrigin', ('king-crab', 'BubbleBarrage'): 'BubbleOrigin'}
# Extra sampled bones: (id, clip) -> {point: (bone, offset)}.
EXTRA_POINTS = {('dragon', 'TailWhip'): {'TailMid': ('Tail_5', [0.0, 0.0, 0.0])}}
# Derived points: (id, clip) -> {point: [points averaged per sample]}.
DERIVED = {('dragon', 'FrontStomp'): {'StompCenter': ['LeftFrontImpact', 'RightFrontImpact']}}


def mat(v):
    m = np.eye(4); m[:3, 3] = v[:3]; m[:3, :3] = np.asarray(v[3:]).reshape(3, 3); return m


def worlds(bones, transforms):  # same as retarget_studio.worlds, in the Y/Z-swapped basis
    result = {}
    def rec(n):
        if n in result: return result[n]
        b = bones[n]; parent = b['parent']; base = rec(parent) if parent in bones else np.eye(4)
        result[n] = base @ mat(b['rest']) @ mat(transforms[n]) if n in transforms else base @ mat(b['rest'])
        return result[n]
    for n in bones: rec(n)
    return result


def fps_of(data, clip): return data['clips'][clip].get('fps') or data.get('fps') or 24


def frame_index(frames, t, fps=24): return min(int(round(t * fps)), len(frames) - 1)


def last_sample(frames, fps, t):
    """The last 1/24 s sample at or before both t (rounded up) and the clip's last frame."""
    end = len(frames) - 1 if fps == 24 else int(math.floor((len(frames) - 1) * 24 / fps + 1e-6))
    return min(end, int(math.ceil(t * 24 - 1e-6)))


def sample_point(data, clip, bone, offset, t, cache=None):
    frames = data['clips'][clip]['frames']; i = frame_index(frames, t, fps_of(data, clip))
    w = (cache[i] if cache is not None and i in cache else worlds(data['bones'], frames[i]['transforms']))
    if cache is not None: cache[i] = w
    w = w[bone]
    # offset is Blender bone-local (x,y,z); the basis swap makes it (x,z,y) in this space
    p = w @ np.array([offset[0], offset[2], offset[1], 1.0])
    return [-p[0], p[1], p[2]]          # Studio ground frame (-X, Z, Y) after the swap


def bone_axis(data, clip, bone, t, cache):
    """World rotation of `bone` at clip time t, in the swapped basis."""
    frames = data['clips'][clip]['frames']; i = frame_index(frames, t, fps_of(data, clip))
    if i not in cache: cache[i] = worlds(data['bones'], frames[i]['transforms'])
    return cache[i][bone][:3, :3]


def swap(v): return np.array([v[0], v[2], v[1]], dtype=float)


# -0.0 (the X flip of an exact 0) is kept: writing it as 0.0 would change 144 values in the four bosses'
# installed MapBossTiming (2026-10-03 review M4, left for a deliberate regeneration).
def r6(v): return [round(float(x), 5) for x in v]


def sample_attack(id, clip, data, attack, ground_offset=0.0):
    """Adds samples = {point: [[t,x,y,z],...]} (and dirs for directed points) to one attack.
    ground_offset lifts every point so y is measured from the soles, not the armature's z=0."""
    points = {n: (p['bone'], p['offset']) for n, p in (attack.get('points') or {}).items()}
    points.update(EXTRA_POINTS.get((id, clip), {}))
    frames = data['clips'][clip]['frames']
    first = max(0, int(math.floor(attack['warnStart'] * 24 + 1e-6)))
    last = last_sample(frames, fps_of(data, clip), attack['recoveryEnd'])
    cache = {}; samples = {n: [] for n in points}
    for i in range(first, last + 1):
        t = i / 24
        for n, (bone, offset) in points.items():
            x, y, z = sample_point(data, clip, bone, offset, t, cache)
            samples[n].append([round(t, 5), *r6([x, y + ground_offset, z])])
    for n, sources in DERIVED.get((id, clip), {}).items():
        samples[n] = [[a[0], *r6((np.array(a[1:]) + np.array(b[1:])) / 2)] for a, b in zip(samples[sources[0]], samples[sources[1]])]
    attack['samples'] = samples
    name = DIRECTED.get((id, clip))
    if name:
        bone = points[name][0]
        # The point's forward: the bone-local direction that reproduces the authored
        # directionAtImpact at impact; without one, the bone's local -Y (plan F).
        if attack.get('directionAtImpact'):
            local = bone_axis(data, clip, bone, attack['impact'], cache).T @ swap(attack['directionAtImpact'])
            local /= np.linalg.norm(local)
        else:
            local = swap([0.0, -1.0, 0.0])
        dirs = []
        for i in range(first, last + 1):
            d = bone_axis(data, clip, bone, i / 24, cache) @ local; d /= np.linalg.norm(d)
            dirs.append([round(i / 24, 5), *r6([-d[0], d[1], d[2]])])
        attack['dirs'] = {name: dirs}
    return attack


def lift(points, ground_offset):
    """Points without samples, rootAtImpactStudio measured from the soles (y + ground_offset)."""
    out = {n: {k: v for k, v in p.items() if k != 'samples'} for n, p in (points or {}).items()}
    for p in out.values():
        if 'rootAtImpactStudio' in p: p['rootAtImpactStudio'] = [p['rootAtImpactStudio'][0], round(p['rootAtImpactStudio'][1] + ground_offset, 5), p['rootAtImpactStudio'][2]]
    return out


def check_impact(label, points, samples, t):
    """The runtime interpolates samples; flag a package whose impact point disagrees with its clip
    (e.g. an impact time left on a 30 fps frame that the 24 fps resample doesn't contain)."""
    for n, p in points.items():
        if 'rootAtImpactStudio' not in p: continue
        track = samples[n]
        j = max(1, min(len(track) - 1, next((k for k, s in enumerate(track) if s[0] >= t - 1e-6), len(track) - 1)))
        s0, s1 = track[j - 1], track[j]; f = 0 if s1[0] == s0[0] else min(1, max(0, (t - s0[0]) / (s1[0] - s0[0])))
        at = [u + (v - u) * f for u, v in zip(s0[1:], s1[1:])]; off = max(abs(u - v) for u, v in zip(at, p['rootAtImpactStudio']))
        if off > .25: print(f'WARN {label} {n}: sampled point at impact {t} is {off:.2f} studs from rootAtImpactStudio', flush=True)


def phase_entries(id, clip, data, attack, a, ground_offset):
    """A combo's phases in order (see the header): each phase's own fields and lifted points. A phase
    point the clip already tracks (same name, bone and offset) uses the clip's track; any other is
    sampled over the clip's window, and the phase then carries the clip's tracks plus its own."""
    out, clip_points = [], attack.get('points') or {}
    for i, ph in enumerate(attack.get('phases') or [], 1):
        p = {k: v for k, v in ph.items() if k not in ('points', 'samples')}
        if ph.get('points'):
            p['points'] = lift(ph['points'], ground_offset)
            def same(n, q): c = clip_points.get(n) or {}; return c.get('bone') == q.get('bone') and c.get('offset') == q.get('offset')
            mine = {n: q for n, q in ph['points'].items() if not same(n, q)}
            if mine:
                # Over the clip's own sample window, as sample_attack does.
                first = max(0, int(math.floor(a['warnStart'] * 24 + 1e-6)))
                last = last_sample(data['clips'][clip]['frames'], fps_of(data, clip), a['recoveryEnd'])
                cache, own = {}, {}
                for n, q in mine.items():
                    own[n] = []
                    for k in range(first, last + 1):
                        x, y, z = sample_point(data, clip, q['bone'], q['offset'], k / 24, cache)
                        own[n].append([round(k / 24, 5), *r6([x, y + ground_offset, z])])
                p['samples'] = {**a['samples'], **own}
            check_impact(f'{id} {clip} phase {i}', p['points'], p.get('samples') or a['samples'], p.get('impact', a['impact']))
        out.append(p)
    return out


def timing(id, data, game):
    height = float(game['height'])
    motion = {**(game.get('motion') or {}), **(data.get('motion') or {})}
    entry = {
        # Height of the HumanoidRootPart centre above the ground (armature origin): the package's
        # body centre, else 40% of the height (a root bone on the ground reports 0).
        # A part-pose package's AnimationData has the template's own (R9).
        'rootHeight': float(game['bodyCentreHeight']) if game.get('bodyCentreHeight') else float(data['rootHeight']) if data.get('rootHeight') else max(float(game.get('rootHeight') or 0), round(0.4 * height, 2)),
        'height': height, 'footprintRadius': float(game['footprintRadius']),
        # Soles below the armature's z=0 in every clip (Frost Cyclops); sampled points include it.
        'groundOffset': float(game.get('groundOffset') or 0),
        'strideLength': float(motion['strideLength']),
        'clips': {n: c['duration'] for n, c in data['clips'].items()},
        'attacks': {},
    }
    rush = motion.get('rushStrideLength') or game.get('rushStrideLength') or ((game.get('attacks') or {}).get('RushLoop') or {}).get('strideLength')
    if rush: entry['rushStrideLength'] = float(rush)
    # The Hammer's charge: ChargeRun is paced by the ground he covers (MapBossPresentation).
    charge = motion.get('chargeStrideLength') or game.get('chargeStrideLength') or ((game.get('attacks') or {}).get('ChargeRun') or {}).get('strideLength')
    if charge: entry['chargeStrideLength'] = float(charge)
    for clip, attack in (game.get('attacks') or {}).items():
        if clip not in data['clips'] or 'warnStart' not in attack: continue
        a = {k: v for k, v in attack.items() if k != 'points'}
        a['points'] = lift(attack.get('points'), entry['groundOffset'])
        entry['attacks'][clip] = sample_attack(id, clip, data, a, entry['groundOffset'])
        check_impact(f'{id} {clip}', a['points'], a['samples'], a['impact'])
        if 'phases' in a: a['phases'] = phase_entries(id, clip, data, attack, a, entry['groundOffset'])
    for clip in ATTACKS[id]:
        if clip in DURATION_ONLY: continue
        assert clip in entry['attacks'], f'{id}: BossGameData has no attack timing for {clip}'
    return entry


def render_animations(id, studio):
    """One boss's BossAnimations modules as {path inside BossAnimations/<id>/: source}, and the largest
    module's length. Nothing is written here, so a failed assert leaves the folder as it was."""
    missing = [c for c in BASIC + ATTACKS[id] if c not in studio['clips']]
    assert not missing, f'{id}: missing clips {missing}'
    files = {}
    metadata = {k: v for k, v in studio.items() if k != 'clips'}
    metadata['sourceAnimationAsset'] = FOLDERS[id] + '/exports/game/StudioAnimationData.json'
    raw = json.dumps(metadata, separators=(',', ':'), allow_nan=False)
    assert ']=]' not in raw
    text = '-- Generated by build_boss_modules.py from ' + FOLDERS[id] + '/exports/game/StudioAnimationData.json\n'
    text += 'local data=game:GetService("HttpService"):JSONDecode([=[' + raw + ']=])\ndata.clips={}\n'
    largest = len(text)
    for clip, clip_data in studio['clips'].items():
        raw_clip = json.dumps(clip_data, separators=(',', ':'), allow_nan=False)
        assert ']=]' not in raw_clip
        clip_source = 'return game:GetService("HttpService"):JSONDecode([=[' + raw_clip + ']=])\n'
        if len(clip_source) < LIMIT:
            files[clip + '.luau'] = clip_source; largest = max(largest, len(clip_source))
        else:
            clip_meta = {k: v for k, v in clip_data.items() if k != 'frames'}
            pieces = ['local clip=game:GetService("HttpService"):JSONDecode([=[' + json.dumps(clip_meta, separators=(',', ':')) + ']=])', 'clip.frames={}']
            # Frames per chunk scale with the bone count (the 90-bone Dragon needs smaller chunks).
            frame_chars = max(len(json.dumps(f, separators=(',', ':'))) for f in clip_data['frames']) + 1
            per = max(1, min(20, (LIMIT - 200) // frame_chars))
            for chunk_index, begin in enumerate(range(0, len(clip_data['frames']), per), 1):
                chunk = 'return game:GetService("HttpService"):JSONDecode([=[' + json.dumps(clip_data['frames'][begin:begin + per], separators=(',', ':'), allow_nan=False) + ']=])\n'
                assert len(chunk) < LIMIT, f'{id}/{clip}: a {per}-frame chunk is {len(chunk)} characters'
                chunk_name = 'Frames' + str(chunk_index).zfill(2)
                files[clip + '/' + chunk_name + '.luau'] = chunk; largest = max(largest, len(chunk))
                pieces.append('for _,frame in require(script:WaitForChild("' + chunk_name + '")) do table.insert(clip.frames,frame) end')
            files[clip + '/init.luau'] = '\n'.join(pieces) + '\nreturn clip\n'
        text += 'data.clips.' + clip + '=require(script:WaitForChild("' + clip + '"))\n'
    files['init.luau'] = text + 'return data\n'
    assert largest < LIMIT
    return files, largest


def write_animations(id, files):
    """Writes BossAnimations/<id>/ from render_animations. Stale modules of that boss go first (a clip
    that moved between <Clip>.luau and a <Clip>/ folder, or left the package); nothing outside its
    own folder is touched, and an unchanged module isn't rewritten. Returns the folder's size."""
    assert id in FOLDERS
    target = OUT / id
    assert target.parent == OUT
    target.mkdir(parents=True, exist_ok=True)
    for path in list(target.rglob('*.luau')):
        if path.relative_to(target).as_posix() not in files: path.unlink()
    for folder in sorted((p for p in target.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        if not any(folder.iterdir()): folder.rmdir()
    for rel, text in files.items():
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_text(encoding='utf-8') != text: path.write_text(text, encoding='utf-8')
    return sum(f.stat().st_size for f in target.rglob('*.luau'))


def existing(path=None):
    """MapBossTiming's current entries (in file order), so bosses not rebuilt keep theirs. Only a missing
    file reads as empty; an unreadable or malformed one raises (it must never become an empty table)."""
    path = path or HERE / 'MapBossTiming.luau'
    try:
        text = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return {}
    return json.loads(text[text.index('[=[') + 3:text.rindex(']=]')])


def check_complete(table):
    """Every boss with generated modules (a BossAnimations/<id> folder) keeps its MapBossTiming entry:
    a run that would drop one stops before writing anything."""
    lost = [id for id in FOLDERS if (OUT / id).is_dir() and id not in table]
    if lost: raise SystemExit(f'MapBossTiming would lose {", ".join(lost)} (their BossAnimations exist): nothing written')


def timing_source(table):
    raw = json.dumps(table, separators=(',', ':'), allow_nan=False)
    assert ']=]' not in raw
    source = ('-- Generated by build_boss_modules.py: clip durations and sampled gameplay points per boss.\n'
              '-- Points are {t,x,y,z} in the ground frame (root.CFrame * CFrame.new(0,-rootHeight,0)), Studio axes.\n'
              'return game:GetService("HttpService"):JSONDecode([=[' + raw + ']=])\n')
    assert len(source) < LIMIT, f'MapBossTiming is {len(source)} characters'
    return source


def convert_part_poses(id, game_dir):
    """A part-pose boss (PART_POSES) with its PartPoses.json there: partposes_to_motor6d writes its
    StudioAnimationData.json and AnimationData.json (derived inputs, before anything this build
    writes). A failed conversion stops the build. True when it ran."""
    receipt = PART_POSES.get(id)
    if not receipt or not (game_dir / 'PartPoses.json').exists(): return False
    import partposes_to_motor6d
    try:
        partposes_to_motor6d.convert_package(game_dir.parent.parent, receipt)
    except (ValueError, FileNotFoundError, AssertionError, KeyError) as error:
        raise SystemExit(f'{id}: PartPoses.json not converted ({error}); nothing written')
    return True


def main(ids):
    table, built = existing(), {}
    for id in ids:
        game_dir = PLANNING / FOLDERS[id] / 'exports' / 'game'
        convert_part_poses(id, game_dir)
        missing = [n for n in PACKAGE if not (game_dir / n).exists()]
        if missing:
            kept = ' (its MapBossTiming entry is kept)' if id in table else ''
            print(f'{id}: skipped, {FOLDERS[id]}/exports/game has no {", ".join(missing)} yet{kept}', flush=True)
            continue
        studio = json.loads((game_dir / 'StudioAnimationData.json').read_text(encoding='utf-8'))
        data = json.loads((game_dir / 'AnimationData.json').read_text(encoding='utf-8'))
        game = json.loads((game_dir / 'BossGameData.json').read_text(encoding='utf-8'))
        built[id] = render_animations(id, studio)
        table[id] = timing(id, data, game)
    if not built:
        print('Nothing built; MapBossTiming unchanged', flush=True)
        return
    source = timing_source(table)
    check_complete(table)
    for id, (files, largest) in built.items():
        print(f'{id}: {write_animations(id, files)} bytes, largest module {largest} characters', flush=True)
    (HERE / 'MapBossTiming.luau').write_text(source, encoding='utf-8')
    print(f'MapBossTiming: {len(source)} characters', flush=True)


if __name__ == '__main__':
    main(sys.argv[1:] or list(FOLDERS))
