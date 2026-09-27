"""Stage explicit regular-enemy source updates for Studio execute_luau installation."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
records = []
for name in ['EnemyCatalog', 'EnemyMotion', 'EnemyMotionTuning', 'EnemyHeldProjectiles', 'EnemyProjectileVisuals', 'NativeEnemyFeet', 'EnemyTests', 'ZombieMotion']:
    records.append({'target': 'Shared', 'path': [name], 'class': 'ModuleScript', 'source': (HERE / (name + '.luau')).read_text(encoding='utf-8-sig')})
for name, source, target, cls in [
    ('EnemyAttacks', HERE / 'EnemyAttacks.luau', 'Server', 'ModuleScript'),
    ('RogueliteZombieChase', HERE.parent / 'RogueliteZombieChase.server.luau', 'Server', 'Script'),
    ('RogueliteZombieAnimation', HERE.parent / 'RogueliteZombieAnimation.client.luau', 'Client', 'LocalScript'),
]:
    records.append({'target': target, 'path': [name], 'class': cls, 'source': source.read_text(encoding='utf-8-sig')})
requested = set(sys.argv[1:])
for source in sorted((HERE / 'EnemyAnimations').rglob('*.luau')):
    relative = source.relative_to(HERE / 'EnemyAnimations')
    if relative.parts[0] not in requested and source.name != 'init.luau':
        continue
    parts = list(relative.parts[:-1])
    if source.stem != 'init':
        parts.append(source.stem)
    records.append({'target': 'Shared', 'path': ['EnemyAnimations'] + parts, 'class': 'ModuleScript', 'source': source.read_text(encoding='utf-8')})
target = ROOT / 'build' / 'regular-enemy-runtime-install.json'
target.write_text(json.dumps(records), encoding='utf-8')
print(json.dumps({'records': len(records), 'bytes': target.stat().st_size, 'file': str(target)}))
