"""Reconcile the delivered files with their independent validation receipts."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
def read(path):
    return json.loads(path.read_text(encoding='utf-8'))
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

report = {}
for directory in sorted(root.iterdir()):
    if not (directory / 'AnimationData.json').is_file():
        continue
    animation = read(directory / 'AnimationChecks.json')
    exchange = read(directory / 'ExchangeChecks.json')
    retarget = read(directory / 'StudioRetargetChecks.json')
    checks = {'geometryAndMotion': animation['passed'], 'exchangeImports': exchange['passed'], 'studioRetarget': retarget['passed']}
    checked_files = 0
    for recorded in (animation['fileHashes'], exchange['sha256']):
        for name, expected in recorded.items():
            checks['hash:' + name] = digest(directory / name) == expected
            checked_files += 1
    for file, key in [('AnimationData.json','sourceAnimationHash'), ('StudioAnimationData.json','outputHash')]:
        checks['retarget:' + file] = digest(directory / file) == retarget[key]
    checks['importReceipt'] = digest(root.parent / 'studio-import' / (directory.name + '-receipt.json')) == retarget['importReceiptHash']
    report[directory.name] = {'passed': all(checks.values()), 'checkedFiles': checked_files + 3, 'failures': [name for name, passed in checks.items() if not passed], 'runtimePayloadHash': retarget['outputHash']}

assert len(report) == 18, f'Expected 18 custom enemies, found {len(report)}'
result = {'scope': '18 custom regular enemies; native Pine Valley templates verified by runtime integration', 'passed': all(entry['passed'] for entry in report.values()), 'models': report}
(root / 'DeliveryChecks.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
assert result['passed'], 'Delivery files changed since their validation receipts'
