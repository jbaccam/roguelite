"""Retarget a map boss's sampled clips onto its actual Studio-imported Bone axes (plan F Task 3).

Adapted from mob-production/combat-ready/retarget_studio.py (Bone mode only; the bosses are
skinned). Never assume bone-local rotations survive FBX conversion: reconstruct every pose in
common world coordinates, then solve the imported joints' local Transforms.

Usage: python retarget_boss.py <asset-folder> <id>
  e.g. python retarget_boss.py dragon-boss dragon
Reads  <asset-folder>/exports/game/AnimationData.json and receipts/<id>-receipt.json.
Writes <asset-folder>/exports/game/StudioAnimationData.json and StudioRetargetChecks.json.
Exits non-zero when the maximum reconstruction error is >= 2e-5.
"""
import json, sys, hashlib
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
PLANNING = HERE.parents[2]
RECEIPTS = HERE / 'receipts'
MAX_ERROR = 2e-5


def mat(v):
    m = np.eye(4); m[:3, 3] = v[:3]; m[:3, :3] = np.asarray(v[3:]).reshape(3, 3); return m


def cf(m): return [round(float(x), 7) for x in [*m[:3, 3], *m[:3, :3].flatten()]]


def worlds(bones, transforms=None):
    result = {}
    def rec(n):
        if n in result: return result[n]
        b = bones[n]; parent = b['parent']; base = rec(parent) if parent in bones else np.eye(4)
        result[n] = base @ mat(b['rest']) @ (mat(transforms[n]) if transforms else np.eye(4))
        return result[n]
    for n in bones: rec(n)
    return result


def resolve(folder):
    p = Path(folder)
    return p if p.is_absolute() or p.exists() else PLANNING / folder


def retarget_data(data, imported):
    """Returns (retargeted data, max error). Pure: no file access, for the unit check."""
    bones = {b['name']: {'parent': b['parent'] if b['parent'] in data['bones'] else None, 'rest': b['cframe']} for b in imported['bones']}
    missing = set(data['bones']) - set(bones)
    if missing: raise ValueError(f"{data.get('id')}: missing imported bones {sorted(missing)}")
    original_rest = worlds(data['bones']); actual_rest = worlds(bones)
    original_inv = {n: np.linalg.inv(m) for n, m in original_rest.items()}
    local_inv = {n: np.linalg.inv(mat(b['rest'])) for n, b in bones.items()}
    # Original sample basis (x,z,y) -> confirmed native import basis (-x,z,y).
    reflect = np.diag([-1., 1., 1., 1.]); maximum = 0.
    for clip in data['clips'].values():
        for frame in clip['frames']:
            original_pose = worlds(data['bones'], frame['transforms'])
            desired = {n: reflect @ original_pose[n] @ original_inv[n] @ reflect @ actual_rest[n] for n in bones if n in original_pose}
            for n in bones:
                desired.setdefault(n, actual_rest[n])  # imported-only bones (none expected) hold rest
            frame['transforms'] = {n: cf(local_inv[n] @ (np.linalg.inv(desired[b['parent']]) if b['parent'] else np.eye(4)) @ desired[n]) for n, b in bones.items()}
            actual = worlds(bones, frame['transforms'])
            maximum = max(maximum, max(np.abs(actual[n] - desired[n]).max() for n in bones))
    out = dict(data)
    out['bones'] = bones
    out['coordinateSpace'] = 'Actual Roblox FBX import joint-local Transform; derived from receipt'
    out['rigType'] = 'Bone'
    out['baselineModelScale'] = imported['scale']
    out['authoringScale'] = 1
    return out, maximum


def retarget(folder, id):
    game = resolve(folder) / 'exports' / 'game'
    source = game / 'AnimationData.json'; receipt = RECEIPTS / (id + '-receipt.json')
    for p in (source, receipt):
        if not p.exists(): raise FileNotFoundError(p)
    data = json.loads(source.read_text(encoding='utf-8')); imported = json.loads(receipt.read_text(encoding='utf-8'))
    out, maximum = retarget_data(data, imported)
    out['sourceAnimationHash'] = hashlib.sha256(source.read_bytes()).hexdigest()
    out['importReceiptHash'] = hashlib.sha256(receipt.read_bytes()).hexdigest()
    target = game / 'StudioAnimationData.json'
    target.write_text(json.dumps(out, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    result = {'id': id, 'boneCount': len(out['bones']), 'rigType': 'Bone', 'maxWorldMatrixReconstructionError': float(maximum),
              'passed': bool(maximum < MAX_ERROR), 'sourceAnimationHash': out['sourceAnimationHash'],
              'importReceiptHash': out['importReceiptHash'], 'outputHash': hashlib.sha256(target.read_bytes()).hexdigest()}
    (game / 'StudioRetargetChecks.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(f"{id}: max error {maximum:.3g} {'< 2e-5' if result['passed'] else '>= 2e-5 FAILED'}", flush=True)
    if not result['passed']: sys.exit(1)
    return result


if __name__ == '__main__':
    if len(sys.argv) != 3: sys.exit(__doc__)
    retarget(sys.argv[1], sys.argv[2])
