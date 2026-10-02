"""Square the Bow Skeleton's shot to its target (user, 2026-10-01: "skeletons should be square with
what they're shooting at").

The authored Attack holds the bow across the body: hips, chest and skull face forward but the
arrow leaves 53 degrees to the skeleton's right. The game used to turn the whole skeleton 53
degrees away from the player so the arrow would hit, which read as shooting sideways.

This turns the chest (arms, bow and draw hand with it) by that angle about the vertical through
the chest joint while the shot is up, and turns the skull back by the same amount, so the hips,
legs and skull face the target and the arrow leaves straight ahead. The weight eases in while the
bow comes up (0 -> 0.25 s), holds through the release (0.583 s), and eases out as the bow lowers
(0.8 -> 1.25 s). Then projectile.attackFacingYaw becomes 0 and releaseDirectionLocal is
re-measured. Runs once: projectile.squaredYaw records the applied angle.

Edits combat-ready/bow-skeleton/StudioAnimationData.json in place; afterwards run
studio-prototype/combat/build_enemy_animation_modules.py.
"""
import json
import math
from pathlib import Path

import numpy as np

SOURCE = Path(__file__).resolve().parent / 'bow-skeleton' / 'StudioAnimationData.json'
EASE_IN = (0.0, 0.25)
EASE_OUT = (0.8, 1.25)


def cf(v):
    m = np.eye(4)
    m[:3, 3] = v[:3]
    m[:3, :3] = np.array(v[3:12]).reshape(3, 3)
    return m


def components(m):
    return [float(x) for x in list(m[:3, 3]) + list(m[:3, :3].reshape(9))]


def yaw(angle):
    # Roblox CFrame.Angles(0, angle, 0): positive turns -Z (forward) toward -X.
    c, s = math.cos(angle), math.sin(angle)
    m = np.eye(4)
    m[:3, :3] = [[c, 0, s], [0, 1, 0], [-s, 0, c]]
    return m


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def weight(t):
    if t < EASE_OUT[0]:
        return smooth((t - EASE_IN[0]) / (EASE_IN[1] - EASE_IN[0]))
    return 1 - smooth((t - EASE_OUT[0]) / (EASE_OUT[1] - EASE_OUT[0]))


def world(bones, poses, name, cache):
    if name not in cache:
        b = bones[name]
        parent = np.eye(4) if b['parent'] is None else world(bones, poses, b['parent'], cache)
        pivot = parent @ cf(b['rest'])
        cache[name] = (pivot, pivot @ (cf(poses[name]) if name in poses else np.eye(4)))
    return cache[name][1]


def pivot(bones, poses, name):
    cache = {}
    world(bones, poses, name, cache)
    return cache[name][0]


def turned(pose, pivot_frame, angle):
    """The pose that turns the bone's posed frame by `angle` about the model vertical, in place."""
    r = np.eye(4)
    r[:3, :3] = pivot_frame[:3, :3]
    q = np.linalg.inv(r) @ yaw(angle) @ r
    return q @ pose


def release_direction(data, poses):
    p = data['projectile']
    bones = data['bones']
    cache = {}
    hand = world(bones, poses, p['bowHandBone'], cache)
    draw = world(bones, poses, p['drawBone'], cache)
    upper = (hand @ np.append(p['upperStringInHand'], 1))[:3]
    rest = (hand @ np.append(p['arrowRestInHand'], 1))[:3]
    nock = draw[:3, 3] + (upper - draw[:3, 3]) * p['nockFractionAlongUpperString']
    d = rest - nock
    return d / np.linalg.norm(d)


def main():
    data = json.loads(SOURCE.read_text(encoding='utf-8'))
    p = data['projectile']
    if 'squaredYaw' in p:
        print('Already squared by', p['squaredYaw'])
        return
    angle = p['attackFacingYaw']
    bones = data['bones']
    clip = data['clips']['Attack']
    for frame in clip['frames']:
        poses = frame['transforms']
        theta = angle * weight(frame['time'])
        chest_pivot = pivot(bones, poses, 'Chest')
        poses['Chest'] = components(turned(cf(poses['Chest']), chest_pivot, theta))
        head_pivot = pivot(bones, poses, 'Head')  # after the chest turn
        poses['Head'] = components(turned(cf(poses['Head']), head_pivot, -theta))
    release = data['motion']['attackImpact']
    frame = min(clip['frames'], key=lambda f: abs(f['time'] - release))
    direction = release_direction(data, frame['transforms'])
    p['releaseDirectionLocal'] = [float(x) for x in direction]
    p['squaredYaw'] = angle
    p['attackFacingYaw'] = 0
    SOURCE.write_text(json.dumps(data, separators=(',', ':')), encoding='utf-8')
    print(json.dumps({'squaredYaw': angle, 'releaseYawDegrees': math.degrees(math.atan2(-direction[0], -direction[2])),
                      'releaseDirectionLocal': p['releaseDirectionLocal']}))


if __name__ == '__main__':
    main()
