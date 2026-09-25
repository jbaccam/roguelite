"""Package only native-import-retargeted clips; never use unverified FBX axes."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent.parent / 'mob-production' / 'combat-ready'
OUT = HERE / 'EnemyAnimations'
OUT.mkdir(exist_ok=True)
tuning = {}
receipts = []
for source in sorted(SOURCE.glob('*/StudioAnimationData.json')):
    data = json.loads(source.read_text(encoding='utf-8'))
    enemy_id = data['id']
    assert source.parent.name == enemy_id
    assert all(name in data['clips'] for name in ['Idle', 'Move', 'Attack'])
    target = OUT / enemy_id
    target.mkdir(exist_ok=True)
    stale = OUT / (enemy_id + '.luau')
    if stale.exists():
        stale.unlink()  # Only this generator's old flat output, not a user asset.
    metadata = {k: v for k, v in data.items() if k != 'clips'}
    manifest = json.loads((source.parent / 'manifest.json').read_text(encoding='utf-8'))
    metadata['sourceImportAsset'] = 'mob-production/' + manifest['source'].replace('\\', '/') + '/Model.fbx'
    metadata['sourceAnimationAsset'] = 'mob-production/combat-ready/' + enemy_id + '/Model.blend'
    raw = json.dumps(metadata, separators=(',', ':'), allow_nan=False)
    assert ']=]' not in raw
    text = '-- Generated from combat-ready/' + enemy_id + '/StudioAnimationData.json\n'
    text += 'local data=game:GetService("HttpService"):JSONDecode([=[' + raw + ']=])\ndata.clips={}\n'
    for clip, clip_data in data['clips'].items():
        raw_clip = json.dumps(clip_data, separators=(',', ':'), allow_nan=False)
        assert ']=]' not in raw_clip
        clip_source = 'return game:GetService("HttpService"):JSONDecode([=[' + raw_clip + ']=])\n'
        if len(clip_source) < 190000:
            (target / (clip + '.luau')).write_text(clip_source, encoding='utf-8')
        else:
            clip_folder = target / clip
            clip_folder.mkdir(exist_ok=True)
            clip_meta = {k:v for k,v in clip_data.items() if k != 'frames'}
            pieces = ['local clip=game:GetService("HttpService"):JSONDecode([=[' + json.dumps(clip_meta, separators=(',', ':')) + ']=])', 'clip.frames={}']
            for chunk_index, begin in enumerate(range(0, len(clip_data['frames']), 20), 1):
                chunk = json.dumps(clip_data['frames'][begin:begin+20], separators=(',', ':'), allow_nan=False)
                assert len(chunk) < 190000
                chunk_name = 'Frames' + str(chunk_index).zfill(2)
                (clip_folder / (chunk_name + '.luau')).write_text('return game:GetService("HttpService"):JSONDecode([=[' + chunk + ']=])\n', encoding='utf-8')
                pieces.append('for _,frame in require(script:WaitForChild("' + chunk_name + '")) do table.insert(clip.frames,frame) end')
            (clip_folder / 'init.luau').write_text('\n'.join(pieces) + '\nreturn clip\n', encoding='utf-8')
        text += 'data.clips.' + clip + '=require(script:WaitForChild("' + clip + '"))\n'
    (target / 'init.luau').write_text(text + 'return data\n', encoding='utf-8')
    tuning[enemy_id] = data['motion']
    receipts.append({'id': enemy_id, 'bytes': sum(f.stat().st_size for f in target.rglob('*.luau')), 'bones': len(data['bones'])})
raw_tuning = json.dumps(tuning, separators=(',', ':'), allow_nan=False)
(HERE / 'EnemyMotionTuning.luau').write_text(
    '-- Generated authored-motion metadata; gameplay speeds live in EnemyCatalog.\n'
    'return game:GetService("HttpService"):JSONDecode([=[' + raw_tuning + ']=])\n', encoding='utf-8')
print(json.dumps({'count': len(receipts), 'modules': receipts}))
