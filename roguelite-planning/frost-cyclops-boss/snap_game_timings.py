"""Snap BossGameData.json attack times to whole 24 fps frames (pure numpy, no Blender).

The attacks are authored at 30 fps, so their impact times fall between the frames
AnimationData.json actually plays. This picks the 24 fps frame where contact really
happens (the lowest ClubImpact / StompImpact point near the authored impact), rounds
warnStart / recoveryEnd to the nearest frame, and recomputes rootAtImpact(+Studio) and
the strike-face normal by forward kinematics on AnimationData.json at that frame.

    python snap_game_timings.py            # rewrite exports/game/BossGameData.json
    python snap_game_timings.py --dry      # print only
build_game_package.py calls snap() right after it writes BossGameData.json.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
GAME = HERE / 'exports' / 'game'
S = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], float)
CONTACT_TOL = 0.02          # studs: frames this close to the window's lowest point count as "in contact"


def uncf(v):
    """Inverse of animate_mobs cf(): 12 numbers (Y/Z-swapped) -> Blender 4x4."""
    m = np.eye(4)
    m[:3, 3] = v[:3]
    m[:3, :3] = np.array(v[3:]).reshape(3, 3)
    return S @ m @ S


def fk(anim, clip, frame):
    """Armature-space (root space, Blender axes) pose matrix of every bone at a clip frame."""
    bones = anim['bones']
    tr = anim['clips'][clip]['frames'][frame]['transforms']
    out = {}

    def get(b):
        if b not in out:
            p = bones[b]['parent']
            base = get(p) if p else np.eye(4)
            out[b] = base @ uncf(bones[b]['rest']) @ uncf(tr[b])
        return out[b]
    for b in bones:
        get(b)
    return out


def studio(v):
    return [round(-float(v[0]), 4), round(float(v[2]), 4), round(float(v[1]), 4)]


def contact_frame(anim, clip, bone, offset, t_authored, fps):
    """Earliest 24 fps frame near the authored impact whose point is at the window's lowest height."""
    f0 = t_authored * fps
    lo, hi = max(0, int(np.floor(f0)) - 1), min(len(anim['clips'][clip]['frames']) - 1, int(np.ceil(f0)) + 1)
    z = {f: float((fk(anim, clip, f)[bone] @ np.append(offset, 1.0))[2]) for f in range(lo, hi + 1)}
    zmin = min(z.values())
    return min(f for f in z if z[f] <= zmin + CONTACT_TOL), z


def snap(dry=False, log=print):
    anim = json.loads((GAME / 'AnimationData.json').read_text())
    game = json.loads((GAME / 'BossGameData.json').read_text())
    fps = anim['fps']
    snap_t = lambda t: round(round(t * fps) / fps, 4)
    report = {}
    for clip, atk in game['attacks'].items():
        (pname, pt), = atk['points'].items()
        off = np.array(pt['offset'], float)
        f, zs = contact_frame(anim, clip, pt['bone'], off, atk['impact'], fps)
        pose = fk(anim, clip, f)
        p = (pose[pt['bone']] @ np.append(off, 1.0))[:3]
        t_imp = round(f / fps, 4)
        report[clip] = {'authoredImpact': atk['impact'], 'frame': f, 'impact': t_imp,
                        'heightByFrame': {k: round(v, 3) for k, v in zs.items()}}
        atk['warnStart'] = snap_t(atk['warnStart'])
        atk['impact'] = t_imp
        atk['activeEnd'] = t_imp
        atk['recoveryEnd'] = snap_t(atk['recoveryEnd'])
        pt['rootAtImpact'] = [round(float(x), 4) + 0.0 for x in p]
        pt['rootAtImpactStudio'] = studio(p)
        if 'strikeFaceNormalAtImpact' in atk:
            ref = fk(anim, 'Idle', 0)[pt['bone']][:3, :3]          # Idle frame 0 is the REFERENCE pose
            n_ref = np.array(json.loads((HERE / 'source' / 'club_strike.json').read_text())['normal_ref_world'])
            n = pose[pt['bone']][:3, :3] @ (ref.T @ n_ref)
            n /= np.linalg.norm(n)
            atk['strikeFaceNormalAtImpact'] = [round(float(x), 4) + 0.0 for x in n]
            atk['strikeFaceNormalAtImpactStudio'] = studio(n)
        report[clip].update({k: atk[k] for k in ('warnStart', 'activeEnd', 'recoveryEnd')})
        report[clip]['rootAtImpact'] = pt['rootAtImpact']
    game['notes'] = game['notes'].split(' All times are whole')[0] + \
        ' All times are whole 24 fps frames of AnimationData.json; impact is the frame the hit point actually touches down.'
    log(json.dumps(report, indent=1))
    if not dry:
        (GAME / 'BossGameData.json').write_text(json.dumps(game, indent=1))
    return report


if __name__ == '__main__':
    snap(dry='--dry' in sys.argv)
