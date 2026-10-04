"""Hammer boss motion checks (pure numpy). Every authored frame, plus the client's own in-between
frames (per-joint Motor6D Transform CFrame:Lerp at 120 Hz) and the 0.12 s clip blends.

The exact mesh-against-mesh test is supplied by the caller (build_moves.py passes a mathutils BVH
overlap); without it only the analytic hammer-solid test runs (quick iteration outside Blender).

Definitions (all rest-relative, because the rest pose is the template the meshes were sculpted in):
  elbow      flex = angle between upper-arm and forearm lines (rest 56.5 R / 60.7 L); hinge axis =
             the rest arm-plane normal carried by the upper arm; off-axis = the swing part of
             upper^-1 * forearm about that axis
  knee       hinge angle about the pelvis X axis carried by the thigh (rest 0, positive = the knee
             forward); off-axis as for the elbow
  wrist      forearm^-1 * hand: bend = swing of the rest forearm axis, twist = turn about it
  swivel     the elbow plane's turn about the shoulder->wrist line, from its rest direction carried
             by the chest
  grip       distance from the haft axis to both ends of each fist's grip hole (hole centre +-0.8
             along the hole axis); slide = the hole centre's coordinate along the haft
  spikes     per-frame change of the swivel and of the spine joints' (LowerTorso, UpperTorso, Head)
             Motor6D rotations
"""
import math

import numpy as np

import hm_motion as HM

LIMITS = {
    'elbowFlex': (12.0, 130.0), 'hingeOffAxis': 2.0, 'kneeHinge': (0.0, 150.0), 'wristBend': 35.0,
    'wristTwist': 35.0, 'swivel': 75.0, 'spikeStep': 20.0, 'grip': 0.05, 'gripBetween': 0.08,
    'footDrift': 0.01, 'ground': -0.05, 'impactFace': 0.03, 'shaftCore': 1.0, 'loop': 1e-6,
    'slide': (2.45, 8.10),
}
HAND_PARTS = ('RightHand', 'LeftHand')
BODY_PARTS = [p for p in HM.PARTS if p not in ('Hammer',) + HAND_PARTS]


# ------------------------------------------------------------------ single-pose metrics
def grip(rig, P):
    out = {}
    D = P['Hammer']
    o = HM.xf(D, rig.HO)
    a = D[:3, :3] @ rig.HA
    for s in HM.SIDES:
        Dh = P[s + 'Hand']
        c = HM.xf(Dh, rig.HO + rig.HA * rig.grip_rest[s])
        d = Dh[:3, :3] @ rig.HA
        worst = 0.0
        for e in (c + d * rig.hole_half, c - d * rig.hole_half):
            v = e - o
            worst = max(worst, float(np.linalg.norm(v - a * (v @ a))))
        out[s] = {'drift': worst, 'slide': float((c - o) @ a)}
    return out


def arms(rig, P):
    out = {}
    for s in HM.SIDES:
        A = rig.arm[s]
        Du, Df, Dh, Dc = P[s + 'UpperArm'], P[s + 'LowerArm'], P[s + 'Hand'], P['UpperTorso']
        S, E, W = HM.xf(Du, A['s0']), HM.xf(Df, A['e0']), HM.xf(Dh, A['w0'])
        flex = math.degrees(math.acos(np.clip(HM.unit(E - S) @ HM.unit(W - E), -1, 1)))
        Rrel = Du[:3, :3].T @ Df[:3, :3]
        hinge, off = HM.hinge_metrics(Rrel, A['h'])
        Rw = Df[:3, :3].T @ Dh[:3, :3]
        bend, twist = HM.swing_twist(Rw, A['fa'])
        u = HM.unit(W - S)
        p = Dc[:3, :3] @ A['pole']
        nref = HM.unit(p - u * (p @ u))
        n = HM.unit((E - S) - u * ((E - S) @ u))
        sw = math.degrees(math.atan2(float(np.cross(nref, n) @ u), float(nref @ n)))
        gap = max(float(np.linalg.norm(HM.xf(Du, A['e0']) - HM.xf(Df, A['e0']))),
                  float(np.linalg.norm(HM.xf(Df, A['w0']) - HM.xf(Dh, A['w0']))),
                  float(np.linalg.norm(HM.xf(Dc, A['s0']) - HM.xf(Du, A['s0']))))
        out[s] = {'flex': flex, 'offAxis': off, 'bend': bend, 'twist': twist, 'swivel': sw, 'gap': gap,
                  'hinge': hinge}
    return out


def legs(rig, P):
    out = {}
    for s in HM.SIDES:
        L = rig.leg[s]
        Dt, Ds, Df, Dp = P[s + 'UpperLeg'], P[s + 'LowerLeg'], P[s + 'Foot'], P['LowerTorso']
        knee, off = HM.hinge_metrics(Dt[:3, :3].T @ Ds[:3, :3], L['axis'])
        ankle = HM.rot_angle(Ds[:3, :3].T @ Df[:3, :3])
        gap = max(float(np.linalg.norm(HM.xf(Dp, L['h0']) - HM.xf(Dt, L['h0']))),
                  float(np.linalg.norm(HM.xf(Dt, L['k0']) - HM.xf(Ds, L['k0']))),
                  float(np.linalg.norm(HM.xf(Ds, L['a0']) - HM.xf(Df, L['a0']))))
        out[s] = {'knee': knee, 'offAxis': off, 'ankle': ankle, 'gap': gap}
    return out


def spine_gap(rig, P):
    g = 0.0
    for c, p in (('UpperTorso', 'LowerTorso'), ('Head', 'UpperTorso')):
        q = rig.pivot[c]
        g = max(g, float(np.linalg.norm(HM.xf(P[p], q) - HM.xf(P[c], q))))
    return g


def shaft_core(rig, P):
    """Smallest torso-core value of the haft (chest rest frame ellipsoid, 1 = on its surface)."""
    xs = np.linspace(rig.shaft[0], rig.shaft[1], 41)
    pts = HM.xf(P['Hammer'], rig.HO + rig.HA * xs[:, None])
    loc = HM.xf(HM.rinv(P['UpperTorso']), pts)
    q = (loc[:, 0] / 2.25) ** 2 + ((loc[:, 1] + 0.15) / 1.7) ** 2 + ((loc[:, 2] - 6.5) / 2.15) ** 2
    return float(q.min())


def hammer_solid_depth(rig, P, meshes, parts=None):
    """Deepest body vertex inside the hammer's solid (head box + haft cylinder), per body part,
    in studs. Hands excluded (they hold the haft)."""
    Hi = HM.rinv(P['Hammer'])
    lo, hi = rig.head_box
    x0, x1, rad = rig.shaft
    out = {}
    for part in (parts or BODY_PARTS):
        V = meshes[part + '_v']
        M = Hi @ P[part]
        p = HM.xf(M, V) - rig.HO
        loc = p @ rig.HR             # hammer-local
        inb = np.all((loc > lo) & (loc < hi), axis=1)
        d_box = np.minimum((loc - lo).min(1), (hi - loc).min(1))
        r = np.hypot(loc[:, 1], loc[:, 2])
        ins = (loc[:, 0] > x0) & (loc[:, 0] < x1) & (r < rad)
        d_sh = np.minimum(rad - r, np.minimum(loc[:, 0] - x0, x1 - loc[:, 0]))
        depth = 0.0
        if inb.any():
            depth = max(depth, float(d_box[inb].max()))
        if ins.any():
            depth = max(depth, float(d_sh[ins].max()))
        out[part] = depth
    return out


def lowest(rig, P, meshes, parts=None):
    z = {}
    for part in (parts or HM.PARTS):
        V = meshes[part + '_v']
        z[part] = float(HM.xf(P[part], V)[:, 2].min())
    return z


def strike_face(rig, P, face_z=-2.21):
    """z of the four corners of a striking face (hammer-local z = face_z) and its outward normal."""
    lo, hi = rig.head_box
    corners = np.array([[x, y, face_z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1])])
    w = HM.xf(P['Hammer'], rig.HO + corners @ rig.HR.T)
    n = P['Hammer'][:3, :3] @ rig.HR @ np.array([0, 0, np.sign(face_z)])
    return w, n


# ------------------------------------------------------------------ clip sampling (EnemyMotion)
def sample(rig, clip, t):
    """EnemyMotion.sample: clip = {'times', 'locals', 'loop', 'duration'}; returns joint locals."""
    T = clip['times']
    if clip['loop']:
        t = t % clip['duration']
    else:
        t = min(max(t, 0.0), clip['duration'])
    lo, hi = 0, len(T) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if T[mid] <= t:
            lo = mid
        else:
            hi = mid - 1
    a, b = lo, min(lo + 1, len(T) - 1)
    al = 0.0 if T[b] <= T[a] else min(1.0, max(0.0, (t - T[a]) / (T[b] - T[a])))
    LA, LB = clip['locals'][a], clip['locals'][b]
    return {c: HM.cf_lerp(LA[c], LB[c], al) for c in LA}


def blend(LA, LB, alpha):
    return {c: HM.cf_lerp(LA[c], LB[c], alpha) for c in LB}


def as_clip(rig, frames, fps, loop):
    return {'times': [k / fps for k in range(len(frames))], 'locals': [HM.joint_locals(rig, P) for P in frames],
            'loop': loop, 'duration': (len(frames) - 1) / fps}


# ------------------------------------------------------------------ per-pose bundle
def pose_metrics(rig, P, meshes=None, overlap=None, solid=True):
    m = {'grip': grip(rig, P), 'arms': arms(rig, P), 'legs': legs(rig, P), 'spineGap': spine_gap(rig, P),
         'shaftCore': shaft_core(rig, P)}
    if meshes is not None and solid:
        m['solid'] = hammer_solid_depth(rig, P, meshes)
    if overlap is not None:
        m['overlap'] = overlap(P)
    return m


def spine_rot(rig, P):
    L = HM.joint_locals(rig, P)
    return {c: L[c][:3, :3] for c in ('LowerTorso', 'UpperTorso', 'Head')}


def check_clip(rig, name, frames, fps, loop, meshes, overlap=None, planted=None, impact=None,
               idle0=None, root_motion=None):
    """All per-frame checks of one clip. planted: per frame {side: foot-local contact point or None};
    root_motion(t) -> world offset of the root (the walk travels forward); impact: frame index where
    the striking face must lie flat on the ground."""
    res = {'frames': len(frames), 'fps': fps}
    worst = {k: 0.0 for k in ('grip', 'hingeOffAxis', 'wristBend', 'wristTwist', 'swivel', 'jointGap',
                              'kneeOffAxis', 'solidDepth', 'footDrift', 'swivelStep', 'spineStep',
                              'ankle')}
    worst.update({'elbowMin': 999.0, 'elbowMax': 0.0, 'kneeMin': 999.0, 'kneeMax': 0.0, 'shaftCore': 999.0,
                  'ground': 999.0, 'slideMin': 999.0, 'slideMax': -999.0})
    where = {}
    prev_sw, prev_spine, prev_contact = None, None, {}
    overlaps = []

    def bump(key, val, k, mode='max'):
        if (mode == 'max' and val > worst[key]) or (mode == 'min' and val < worst[key]):
            worst[key] = val
            where[key] = k

    for k, P in enumerate(frames):
        m = pose_metrics(rig, P, meshes, overlap)
        for s in HM.SIDES:
            g, a, l = m['grip'][s], m['arms'][s], m['legs'][s]
            bump('grip', g['drift'], k)
            bump('slideMin', g['slide'], k, 'min')
            bump('slideMax', g['slide'], k)
            bump('elbowMin', a['flex'], k, 'min')
            bump('elbowMax', a['flex'], k)
            bump('hingeOffAxis', a['offAxis'], k)
            bump('wristBend', a['bend'], k)
            bump('wristTwist', abs(a['twist']), k)
            bump('swivel', abs(a['swivel']), k)
            bump('jointGap', max(a['gap'], l['gap'], m['spineGap']), k)
            bump('kneeMin', l['knee'], k, 'min')
            bump('kneeMax', l['knee'], k)
            bump('kneeOffAxis', l['offAxis'], k)
            bump('ankle', l['ankle'], k)
        bump('shaftCore', m['shaftCore'], k, 'min')
        if 'solid' in m:
            bump('solidDepth', max(m['solid'].values()), k)
        if 'overlap' in m and m['overlap']:
            overlaps.append({'frame': k, 'pairs': m['overlap']})
        z = lowest(rig, P, meshes)
        bump('ground', min(z.values()), k, 'min')
        sw = {s: m['arms'][s]['swivel'] for s in HM.SIDES}
        sp = spine_rot(rig, P)
        if prev_sw is not None:
            bump('swivelStep', max(abs(sw[s] - prev_sw[s]) for s in HM.SIDES), k)
            bump('spineStep', max(HM.rot_angle(prev_spine[c].T @ sp[c]) for c in sp), k)
        prev_sw, prev_spine = sw, sp
        if planted is not None:
            off = root_motion(k / fps) if root_motion else np.zeros(3)
            for s in HM.SIDES:
                c = planted[k].get(s)
                if c is None:
                    prev_contact.pop(s, None)
                    continue
                w = HM.xf(P[s + 'Foot'], c) + off
                if s in prev_contact and np.allclose(prev_contact[s][0], c):
                    bump('footDrift', float(np.linalg.norm(w - prev_contact[s][1])), k)
                prev_contact[s] = (np.asarray(c), w)
    res['worst'] = worst
    res['where'] = where
    res['overlaps'] = overlaps[:20]
    res['overlapFrames'] = len(overlaps)
    if impact is not None:
        w, n = strike_face(rig, frames[impact])
        res['impactFaceZ'] = [float(v) for v in w[:, 2]]
        res['impactFaceNormal'] = [float(v) for v in n]
    if loop:
        res['loopClose'] = max(float(np.abs(frames[-1][p] - frames[0][p]).max()) for p in HM.PARTS)
    if idle0 is not None:
        res['startVsIdle0'] = max(float(np.abs(frames[0][p] - idle0[p]).max()) for p in HM.PARTS)
        res['endVsIdle0'] = max(float(np.abs(frames[-1][p] - idle0[p]).max()) for p in HM.PARTS)
    return res


def check_between(rig, poses, meshes=None, overlap=None, every=1):
    """The same grip / hinge / wrist / hammer-solid checks on interpolated poses (a list of pose dicts
    with labels). Returns the worst values and where."""
    worst = {'grip': 0.0, 'hingeOffAxis': 0.0, 'kneeOffAxis': 0.0, 'wristBend': 0.0, 'wristTwist': 0.0,
             'solidDepth': 0.0, 'elbowMin': 999.0, 'elbowMax': 0.0, 'shaftCore': 999.0, 'jointGap': 0.0,
             'kneeMin': 999.0, 'slideMin': 999.0, 'slideMax': -999.0}
    where = {}
    overlaps = []

    def bump(key, val, lab, mode='max'):
        if (mode == 'max' and val > worst[key]) or (mode == 'min' and val < worst[key]):
            worst[key] = val
            where[key] = lab

    for i, (lab, P) in enumerate(poses):
        g = grip(rig, P)
        a = arms(rig, P)
        l = legs(rig, P)
        for s in HM.SIDES:
            bump('grip', g[s]['drift'], lab)
            bump('slideMin', g[s]['slide'], lab, 'min')
            bump('slideMax', g[s]['slide'], lab)
            bump('hingeOffAxis', a[s]['offAxis'], lab)
            bump('kneeOffAxis', l[s]['offAxis'], lab)
            bump('wristBend', a[s]['bend'], lab)
            bump('wristTwist', abs(a[s]['twist']), lab)
            bump('elbowMin', a[s]['flex'], lab, 'min')
            bump('elbowMax', a[s]['flex'], lab)
            bump('kneeMin', l[s]['knee'], lab, 'min')
            bump('jointGap', max(a[s]['gap'], l[s]['gap']), lab)
        bump('shaftCore', shaft_core(rig, P), lab, 'min')
        if meshes is not None and i % every == 0:
            d = hammer_solid_depth(rig, P, meshes)
            bump('solidDepth', max(d.values()), lab)
        if overlap is not None and i % every == 0:
            o = overlap(P)
            if o:
                overlaps.append({'at': lab, 'pairs': o})
    return {'samples': len(poses), 'worst': worst, 'where': where, 'overlaps': overlaps[:20],
            'overlapSamples': len(overlaps)}


def resample(rig, clip, rate=120):
    """The client's in-between poses of one clip at `rate` Hz (labelled by time)."""
    out = []
    n = int(round(clip['duration'] * rate))
    for i in range(n + 1):
        t = i / rate
        out.append((f't={t:.4f}', HM.from_locals(rig, sample(rig, clip, t))))
    return out


def blends(rig, src, dst, src_starts, length=0.12, rate=120, dst_start=0.0, hold_src=False):
    """src -> dst 0.12 s cross-blends as the client does them (both clips keep playing, alpha ramps),
    for several src phases. Returns labelled poses."""
    out = []
    n = int(round(length * rate))
    for t0 in src_starts:
        for i in range(n + 1):
            tau = i / rate
            a = sample(rig, src, t0 if hold_src else t0 + tau)
            b = sample(rig, dst, dst_start + tau)
            out.append((f'src@{t0:.3f}+{tau:.4f}', HM.from_locals(rig, blend(a, b, tau / length))))
    return out
