"""Build the map-boss animation modules and MapBossTiming (plan F Task 3).

Based on studio-prototype/combat/build_enemy_animation_modules.py (same 190,000-character
chunking into Frames sub-modules). For each boss it reads
  <asset-folder>/exports/game/StudioAnimationData.json   (retarget_boss.py output) -> BossAnimations/<id>/
  <asset-folder>/exports/game/AnimationData.json         (original clips, for point sampling)
  <asset-folder>/exports/game/BossGameData.json          (attack times and named points)
and writes MapBossTiming.luau. Gameplay points are re-sampled every 1/24 s from warnStart to
recoveryEnd by forward kinematics over the ORIGINAL bones, in the boss's ground frame, Studio axes.

Usage: python build_boss_modules.py [id ...]   (default: all four)
"""
import json, math, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
PLANNING = HERE.parents[2]
OUT = HERE / 'BossAnimations'
LIMIT = 190000
FOLDERS = {'king-crab': 'king-crab-boss', 'frost-cyclops': 'frost-cyclops-boss', 'pharaoh': 'pharaoh-boss', 'dragon': 'dragon-boss'}
# Mirrors MapBossDefs.ATTACK_CLIPS.
ATTACKS = {
    'king-crab': ['ClawCrush', 'RushStart', 'RushLoop', 'RushEnd', 'BubbleBarrage'],
    'frost-cyclops': ['GroundSlam', 'Stomp'],
    'pharaoh': ['CursedBolts', 'TombEruption'],
    'dragon': ['FireBreath', 'TailWhip', 'FrontStomp'],
}
BASIC = ['Idle', 'Walk', 'Hit', 'Death']
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


def frame_index(frames, t): return min(int(round(t * 24)), len(frames) - 1)


def sample_point(data, clip, bone, offset, t, cache=None):
    frames = data['clips'][clip]['frames']; i = frame_index(frames, t)
    w = (cache[i] if cache is not None and i in cache else worlds(data['bones'], frames[i]['transforms']))
    if cache is not None: cache[i] = w
    w = w[bone]
    # offset is Blender bone-local (x,y,z); the basis swap makes it (x,z,y) in this space
    p = w @ np.array([offset[0], offset[2], offset[1], 1.0])
    return [-p[0], p[1], p[2]]          # Studio ground frame (-X, Z, Y) after the swap


def bone_axis(data, clip, bone, t, cache):
    """World rotation of `bone` at clip time t, in the swapped basis."""
    frames = data['clips'][clip]['frames']; i = frame_index(frames, t)
    if i not in cache: cache[i] = worlds(data['bones'], frames[i]['transforms'])
    return cache[i][bone][:3, :3]


def swap(v): return np.array([v[0], v[2], v[1]], dtype=float)


def r6(v): return [round(float(x), 5) for x in v]


def sample_attack(id, clip, data, attack, ground_offset=0.0):
    """Adds samples = {point: [[t,x,y,z],...]} (and dirs for directed points) to one attack.
    ground_offset lifts every point so y is measured from the soles, not the armature's z=0."""
    points = {n: (p['bone'], p['offset']) for n, p in (attack.get('points') or {}).items()}
    points.update(EXTRA_POINTS.get((id, clip), {}))
    frames = data['clips'][clip]['frames']
    first = max(0, int(math.floor(attack['warnStart'] * 24 + 1e-6)))
    last = min(len(frames) - 1, int(math.ceil(attack['recoveryEnd'] * 24 - 1e-6)))
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


def timing(id, data, game):
    height = float(game['height'])
    motion = {**(game.get('motion') or {}), **(data.get('motion') or {})}
    entry = {
        # Height of the HumanoidRootPart centre above the ground (armature origin): the package's
        # body centre, else 40% of the height (a root bone on the ground reports 0).
        'rootHeight': float(game['bodyCentreHeight']) if game.get('bodyCentreHeight') else max(float(game.get('rootHeight') or 0), round(0.4 * height, 2)),
        'height': height, 'footprintRadius': float(game['footprintRadius']),
        # Soles below the armature's z=0 in every clip (Frost Cyclops); sampled points include it.
        'groundOffset': float(game.get('groundOffset') or 0),
        'strideLength': float(motion['strideLength']),
        'clips': {n: c['duration'] for n, c in data['clips'].items()},
        'attacks': {},
    }
    rush = motion.get('rushStrideLength') or game.get('rushStrideLength') or ((game.get('attacks') or {}).get('RushLoop') or {}).get('strideLength')
    if rush: entry['rushStrideLength'] = float(rush)
    for clip, attack in (game.get('attacks') or {}).items():
        if clip not in data['clips'] or 'warnStart' not in attack: continue
        a = {k: v for k, v in attack.items() if k != 'points'}
        a['points'] = {n: {k: v for k, v in p.items() if k != 'samples'} for n, p in (attack.get('points') or {}).items()}
        for p in a['points'].values():
            if 'rootAtImpactStudio' in p: p['rootAtImpactStudio'] = [p['rootAtImpactStudio'][0], round(p['rootAtImpactStudio'][1] + entry['groundOffset'], 5), p['rootAtImpactStudio'][2]]
        entry['attacks'][clip] = sample_attack(id, clip, data, a, entry['groundOffset'])
        # The runtime interpolates samples; flag a package whose impact point disagrees with its clip
        # (e.g. an impact time left on a 30 fps frame that the 24 fps resample doesn't contain).
        for n, p in a['points'].items():
            track = a['samples'][n]; t = a['impact']
            j = max(1, min(len(track) - 1, next((k for k, s in enumerate(track) if s[0] >= t - 1e-6), len(track) - 1)))
            s0, s1 = track[j - 1], track[j]; f = 0 if s1[0] == s0[0] else min(1, max(0, (t - s0[0]) / (s1[0] - s0[0])))
            at = [u + (v - u) * f for u, v in zip(s0[1:], s1[1:])]; off = max(abs(u - v) for u, v in zip(at, p['rootAtImpactStudio']))
            if off > .25: print(f'WARN {id} {clip} {n}: sampled point at impact {t} is {off:.2f} studs from rootAtImpactStudio', flush=True)
    for clip in ATTACKS[id]:
        if clip.startswith('Rush'): continue  # rush clips need durations only
        assert clip in entry['attacks'], f'{id}: BossGameData has no attack timing for {clip}'
    return entry


def write_animations(id, studio):
    missing = [c for c in BASIC + ATTACKS[id] if c not in studio['clips']]
    assert not missing, f'{id}: missing clips {missing}'
    target = OUT / id; target.mkdir(parents=True, exist_ok=True)
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
            (target / (clip + '.luau')).write_text(clip_source, encoding='utf-8'); largest = max(largest, len(clip_source))
        else:
            clip_folder = target / clip; clip_folder.mkdir(exist_ok=True)
            clip_meta = {k: v for k, v in clip_data.items() if k != 'frames'}
            pieces = ['local clip=game:GetService("HttpService"):JSONDecode([=[' + json.dumps(clip_meta, separators=(',', ':')) + ']=])', 'clip.frames={}']
            # Frames per chunk scale with the bone count (the 90-bone Dragon needs smaller chunks).
            frame_chars = max(len(json.dumps(f, separators=(',', ':'))) for f in clip_data['frames']) + 1
            per = max(1, min(20, (LIMIT - 200) // frame_chars))
            for chunk_index, begin in enumerate(range(0, len(clip_data['frames']), per), 1):
                chunk = 'return game:GetService("HttpService"):JSONDecode([=[' + json.dumps(clip_data['frames'][begin:begin + per], separators=(',', ':'), allow_nan=False) + ']=])\n'
                assert len(chunk) < LIMIT, f'{id}/{clip}: a {per}-frame chunk is {len(chunk)} characters'
                chunk_name = 'Frames' + str(chunk_index).zfill(2)
                (clip_folder / (chunk_name + '.luau')).write_text(chunk, encoding='utf-8'); largest = max(largest, len(chunk))
                pieces.append('for _,frame in require(script:WaitForChild("' + chunk_name + '")) do table.insert(clip.frames,frame) end')
            (clip_folder / 'init.luau').write_text('\n'.join(pieces) + '\nreturn clip\n', encoding='utf-8')
        text += 'data.clips.' + clip + '=require(script:WaitForChild("' + clip + '"))\n'
    (target / 'init.luau').write_text(text + 'return data\n', encoding='utf-8')
    assert largest < LIMIT
    return sum(f.stat().st_size for f in target.rglob('*.luau')), largest


def main(ids):
    table = {}
    for id in ids:
        game_dir = PLANNING / FOLDERS[id] / 'exports' / 'game'
        studio = json.loads((game_dir / 'StudioAnimationData.json').read_text(encoding='utf-8'))
        data = json.loads((game_dir / 'AnimationData.json').read_text(encoding='utf-8'))
        game = json.loads((game_dir / 'BossGameData.json').read_text(encoding='utf-8'))
        size, largest = write_animations(id, studio)
        table[id] = timing(id, data, game)
        print(f'{id}: {size} bytes, largest module {largest} characters', flush=True)
    raw = json.dumps(table, separators=(',', ':'), allow_nan=False)
    assert ']=]' not in raw
    source = ('-- Generated by build_boss_modules.py: clip durations and sampled gameplay points per boss.\n'
              '-- Points are {t,x,y,z} in the ground frame (root.CFrame * CFrame.new(0,-rootHeight,0)), Studio axes.\n'
              'return game:GetService("HttpService"):JSONDecode([=[' + raw + ']=])\n')
    assert len(source) < LIMIT, f'MapBossTiming is {len(source)} characters'
    (HERE / 'MapBossTiming.luau').write_text(source, encoding='utf-8')
    print(f'MapBossTiming: {len(source)} characters', flush=True)


if __name__ == '__main__':
    main(sys.argv[1:] or list(FOLDERS))
