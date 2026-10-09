"""The ORIGINAL Hammer boss clips, sampled exactly as the legacy client showed them (pure numpy).

A port of hammer-boss/BossMotion.luau (M.sample, M.blend, M.constrainArms), run in the legacy data
space at template scale 1.0. The Luau runs at scale 1.15, but every step is scale-equivariant
(lengths, pivots and the Swing/Spin head-height target all scale together), so 1.0 gives the same
poses divided by 1.15.

Legacy data space: each clip frame holds, per part, a "delta" CFrame in root space (Studio axes,
origin at the HumanoidRootPart). The part sits at delta * BossRest (BossMotion.apply), where BossRest
is the part's rest CFrame relative to the root. Converting a delta to this folder's pose format
(Blender-world deformation D) is D = T(0,0,4.45) C^-1 M C T(0,0,-4.45), with C the (-X, Z, Y) swap.

hammer-boss/charge_runtime.py re-implements the same sampling for the charge clips. It matches
BossMotion.luau for blend and constrainArms, but its rsample leaves out two branches of M.sample:
  - Death: after the blend, every part is overwritten by its plain per-part lerp (then arms solved);
  - Swing/Spin: during [active, finish] the hammer and both hands are lifted so the head centre sits
    4.6 studs above the ground (D.rootHeight below the root).
Both are included here.
"""
import json
import math
from pathlib import Path

import numpy as np

import hm_motion as HM

LEGACY = Path(__file__).resolve().parent.parent / 'hammer-boss' / 'finished' / 'BossData.json'
C4 = np.eye(4)
C4[:3, :3] = HM.C_STUDIO
ATTACKS = {   # BossMotion.M.Attacks (seconds)
    'Slam': {'anticipation': 5 / 30, 'active': 23 / 30, 'finish': 24 / 30, 'duration': 50 / 30},
    'Swing': {'anticipation': 6 / 30, 'active': 19 / 30, 'finish': 25 / 30, 'duration': 54 / 30},
    'Spin': {'anticipation': 6 / 36, 'active': 21 / 36, 'finish': 37 / 36, 'duration': 66 / 36},
}
MIN_FLEX, MAX_FLEX = math.radians(12), math.radians(130)


def mat(v):
    m = np.eye(4)
    m[:3, 3] = v[:3]
    m[:3, :3] = np.asarray(v[3:12], float).reshape(3, 3)
    return m


def unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def hinge_frame(direction, normal):
    y = unit(direction)
    z = unit(normal)
    x = unit(np.cross(y, z))
    M = np.eye(4)
    M[:3, :3] = np.stack([x, y, z], 1)
    return M


class Legacy:
    def __init__(self, path=LEGACY):
        self.d = d = json.loads(Path(path).read_text())
        self.root = d['rootHeight']
        self.head_rest = mat(d['hammerHeadRest'])
        self.grip_pivot = self.head_rest @ HM.tr([-7.3, 0, 0])
        self.clips = {}
        for name, c in d['clips'].items():
            frames = [{p: mat(v) for p, v in fr.items()} for fr in c['frames']]
            self.clips[name] = {'frames': frames, 'fps': c['fps'], 'last': c['lastFrame'],
                                'duration': c['lastFrame'] / c['fps']}
        self.arms = {}
        for side in ('Right', 'Left'):
            j = lambda n: np.array(d['joints'][side + n]['head'], float) - np.array([0, self.root, 0])
            a, b, w = j('UpperArm'), j('LowerArm'), j('Hand')
            u, v = b - a, w - b
            axis = unit(np.cross(u, v))
            self.arms[side] = dict(a=a, b=b, w=w, l1=np.linalg.norm(u), l2=np.linalg.norm(v), axis=axis,
                                   restFlex=math.acos(np.clip(unit(u) @ unit(v), -1, 1)),
                                   frame=hinge_frame(u, axis),
                                   pole=np.array([2.2 if side == 'Right' else -2.2, -3.5, 0.35]))

    # ---------------------------------------------------------------- BossMotion.constrainArms
    def constrain(self, P):
        chest = P['UpperTorso']
        for side, A in self.arms.items():
            hand = P[side + 'Hand']
            shoulder = HM.xf(chest, A['a'])
            wrist = HM.xf(hand, A['w'])
            v = wrist - shoulder
            u = unit(v) if np.linalg.norm(v) > 1e-6 else chest[:3, :3] @ np.array([0, -1.0, 0])
            l1, l2 = A['l1'], A['l2']
            low = math.sqrt(l1 * l1 + l2 * l2 + 2 * l1 * l2 * math.cos(MAX_FLEX))
            high = math.sqrt(l1 * l1 + l2 * l2 + 2 * l1 * l2 * math.cos(MIN_FLEX))
            dist = min(max(np.linalg.norm(v), low), high)
            corrected = shoulder + u * dist
            P[side + 'Hand'] = HM.tr(corrected - wrist) @ hand
            wrist = corrected
            along = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
            pole = chest[:3, :3] @ A['pole']
            pole = pole - u * (pole @ u)
            if np.linalg.norm(pole) < 1e-5:
                pole = chest[:3, :3] @ np.array([1.0, 0, 0])
                pole = pole - u * (pole @ u)
            req = HM.xf(P[side + 'LowerArm'], A['b']) - shoulder
            req = req - u * (req @ u)
            sw = math.atan2(float(u @ np.cross(pole, req)), float(pole @ req))
            sw = max(-math.radians(75), min(math.radians(75), sw))
            bend = HM.axis_angle(u, math.degrees(sw)) @ unit(pole)
            elbow = shoulder + u * along + bend * math.sqrt(max(0.0, l1 * l1 - along * along))
            upper, lower = elbow - shoulder, wrist - elbow
            ax = unit(np.cross(upper, lower))
            rot = hinge_frame(upper, ax) @ np.linalg.inv(A['frame'])
            flex = math.acos(np.clip(unit(upper) @ unit(lower), -1, 1))
            P[side + 'UpperArm'] = HM.tr(shoulder) @ rot @ HM.tr(-A['a'])
            P[side + 'LowerArm'] = (HM.tr(elbow) @ rot @ HM.tf(HM.axis_angle(A['axis'], math.degrees(flex - A['restFlex'])))
                                    @ HM.tr(-A['b']))
        return P

    # ---------------------------------------------------------------- BossMotion.blend
    def blend(self, a, b, t):
        r = {n: HM.cf_lerp(m, b[n], t) for n, m in a.items()}
        ha = HM.rinv(a['UpperTorso']) @ a['Hammer'] @ self.grip_pivot
        hb = HM.rinv(b['UpperTorso']) @ b['Hammer'] @ self.grip_pivot
        r['Hammer'] = r['UpperTorso'] @ HM.cf_lerp(ha, hb, t) @ HM.rinv(self.grip_pivot)
        for n in ('RightHand', 'LeftHand'):
            r[n] = r['Hammer'] @ HM.cf_lerp(HM.rinv(a['Hammer']) @ a[n], HM.rinv(b['Hammer']) @ b[n], t)
        return r

    # ---------------------------------------------------------------- BossMotion.sample
    def sample(self, name, time, looped=False):
        return self.constrain(self.blended(name, time, looped))

    def blended(self, name, time, looped=False):
        """M.sample up to (not including) its final constrainArms."""
        c = self.clips[name]
        if looped:
            time = time % c['duration']
        f = min(max(time * c['fps'], 0.0), c['last'])
        i = int(math.floor(f))
        j = min(i + 1, len(c['frames']) - 1)
        alpha = f % 1.0
        r = self.blend(c['frames'][i], c['frames'][j], alpha)
        if name == 'Death':
            for p, m in c['frames'][i].items():
                r[p] = HM.cf_lerp(m, c['frames'][j][p], alpha)
        a = ATTACKS.get(name)
        if name in ('Swing', 'Spin') and a['active'] <= time <= a['finish']:
            y = (r['Hammer'] @ self.head_rest)[1, 3]
            shift = HM.tr([0, 4.6 - self.root - y, 0])
            for p in ('Hammer', 'RightHand', 'LeftHand'):
                r[p] = shift @ r[p]
        return r

    def reach_project(self, P, iters=60):
        """Move the hammer and both fists together (the paired grip as a unit, as the original
        authoring tool did) until both wrists are inside the arms' hinge-limited reach, so
        constrainArms never has to pull a fist off the haft."""
        P = dict(P)
        for _ in range(iters):
            worst = 0.0
            for side, A in self.arms.items():
                shoulder = HM.xf(P['UpperTorso'], A['a'])
                wrist = HM.xf(P[side + 'Hand'], A['w'])
                v = wrist - shoulder
                l1, l2 = A['l1'], A['l2']
                low = math.sqrt(l1 * l1 + l2 * l2 + 2 * l1 * l2 * math.cos(MAX_FLEX)) + 1e-4
                high = math.sqrt(l1 * l1 + l2 * l2 + 2 * l1 * l2 * math.cos(MIN_FLEX)) - 1e-4
                dist = np.linalg.norm(v)
                corr = unit(v) * (min(max(dist, low), high) - dist)
                worst = max(worst, float(np.linalg.norm(corr)))
                for p in ('Hammer', 'RightHand', 'LeftHand'):
                    P[p] = HM.tr(corr) @ P[p]
            if worst < 1e-7:
                break
        return P

    def head(self, P):
        """BossMotion.head: the hammer head centre frame (root space, Studio axes)."""
        return P['Hammer'] @ self.head_rest

    # ---------------------------------------------------------------- conversions
    def to_D(self, P):
        """Legacy root-space deltas (Studio) -> this folder's poses (Blender-world deformations)."""
        A = HM.tr([0, 0, self.root]) @ C4.T
        B = C4 @ HM.tr([0, 0, -self.root])
        out = {HM.ROOT: np.eye(4)}
        for p, m in P.items():
            out[p] = A @ m @ B
        return out

    def from_D(self, P):
        A = HM.tr([0, 0, self.root]) @ C4.T
        B = C4 @ HM.tr([0, 0, -self.root])
        return {p: HM.rinv(A) @ m @ HM.rinv(B) for p, m in P.items() if p != HM.ROOT}


# ==================================================================== baking for the hand-off
def _grip_drift(rig, D):
    """Max distance from the haft axis to the fist holes (as hm_checks.grip), in studs."""
    o = HM.xf(D['Hammer'], rig.HO)
    a = D['Hammer'][:3, :3] @ rig.HA
    worst = 0.0
    for s in HM.SIDES:
        Dh = D[s + 'Hand']
        c = HM.xf(Dh, rig.HO + rig.HA * rig.grip_rest[s])
        d = Dh[:3, :3] @ rig.HA
        for e in (c + d * rig.hole_half, c - d * rig.hole_half):
            v = e - o
            worst = max(worst, float(np.linalg.norm(v - a * (v @ a))))
    return worst


class Baker:
    """The legacy runtime's poses (BossMotion.sample, constrainArms included) as this folder's D
    poses, at any time, with one repair.

    Between two authored frames BossMotion.blend lerps each fist's pose in hammer space as a
    root-space delta. Where a fist rolls far about the haft between two authored frames, its hole
    cuts a chord off the haft. The original data does this in two places by more than REPAIR
    (0.15 studs, the gap the user accepts on the originals): Swing frames 3-4 (0.40) and Spin frames
    4-5 (0.48), both the right fist rolling ~68 deg in one source frame at the start of the wind-up.
    For every sample inside such an interval (the whole interval, so the fist's path stays smooth)
    the bake interpolates that fist's slide along and roll about the haft instead (screw_hands),
    then solves the arms with constrainArms. Smaller gaps are the original as the user played it and
    are kept (measured in MotionChecks.json). Authored frames never change. Death is never repaired:
    he lets go of the hammer from its first frame."""
    REPAIR = 0.15
    PROBES = 24                              # samples per source interval to find its worst gap

    def __init__(self, rig, legacy=None):
        self.rig = rig
        self.L = legacy or Legacy()
        self.gaps = {}
        self.repaired = {}

    def raw(self, name, t):
        return self.L.to_D(self.L.sample(name, t))

    def interval_gaps(self, name):
        """Worst fist-off-haft gap of the legacy in-betweens, per source interval [i, i+1]."""
        if name not in self.gaps:
            c = self.L.clips[name]
            self.gaps[name] = [max(_grip_drift(self.rig, self.raw(name, (i + a) / c['fps']))
                                   for a in np.arange(1, self.PROBES) / self.PROBES) for i in range(c['last'])]
        return self.gaps[name]

    def pose(self, name, t, label=None):
        c = self.L.clips[name]
        f = min(max(t * c['fps'], 0.0), c['last'])
        if abs(f - round(f)) < 1e-6 or name == 'Death':
            return self.raw(name, t)
        i = min(int(math.floor(f)), c['last'] - 1)
        g = self.interval_gaps(name)[i]
        if g <= self.REPAIR:
            return self.raw(name, t)
        D = self.screw_hands(name, t)
        key = (name, i)
        rec = self.repaired.setdefault(key, {'clip': name, 'sourceFrames': [i, i + 1],
                                             'time': [round(i / c['fps'], 4), round((i + 1) / c['fps'], 4)],
                                             'gripBefore': round(g, 4), 'gripAfter': 0.0})
        rec['gripAfter'] = max(rec['gripAfter'], round(_grip_drift(self.rig, D), 6))
        return D

    def screw_params(self, side, D):
        """(slide, roll deg) of a fist on the haft: inverse of Rig.screw."""
        rig = self.rig
        rel = HM.rinv(D['Hammer']) @ D[side + 'Hand']
        g = rig.grip_rest[side] + float(rig.HA @ (HM.xf(rel, rig.HO) - rig.HO))
        _, roll = HM.swing_twist(rel[:3, :3], rig.HA)
        return g, roll

    def screw_hands(self, name, t):
        """The legacy in-between with each fist's slide along and roll about the haft interpolated
        (instead of BossMotion.blend's root-space lerp of the fist-in-hammer delta, which cuts a
        chord off the haft when the fist rolls far between two frames), then constrainArms."""
        c = self.L.clips[name]
        f = min(max(t * c['fps'], 0.0), c['last'])
        i = int(math.floor(f))
        j = min(i + 1, c['last'])
        a = f - i
        Di, Dj = self.raw(name, i / c['fps']), self.raw(name, j / c['fps'])
        D = self.L.to_D(self.L.blended(name, t))
        for s in HM.SIDES:
            gi, ri = self.screw_params(s, Di)
            gj, rj = self.screw_params(s, Dj)
            r = ri + ((rj - ri + 180) % 360 - 180) * a
            D[s + 'Hand'] = D['Hammer'] @ self.rig.screw(s, gi + (gj - gi) * a, r)
        return self.L.to_D(self.L.constrain(self.L.from_D(D)))

    # ---------------------------------------------------------------- crossfade (combos, seams)
    LEGS = [s + p for s in HM.SIDES for p in ('UpperLeg', 'LowerLeg', 'Foot')]

    def crossfade(self, DA, DB, w):
        """A -> B at weight w (0..1). The torso, head and arms lerp each joint's local Transform
        (slerp rotation, lerp position), so the spine never opens. The legs lerp each part in root
        space, as BossMotion.blend does, so planted feet stay on the ground. The hammer is lerped in
        chest space about the held grip (BossMotion.blend). Each fist's slide along and roll about
        the haft are interpolated (shortest roll), so the fists stay on the haft; the hammer and fists
        move together into the arms' reach, then both arms are re-solved with
        BossMotion.constrainArms, the lerped forearms giving the elbow swivel."""
        rig, L = self.rig, self.L
        LA, LB = HM.joint_locals(rig, DA), HM.joint_locals(rig, DB)
        P = L.from_D(HM.from_locals(rig, {k: HM.cf_lerp(LA[k], LB[k], w) for k in LA}))
        PA, PB = L.from_D(DA), L.from_D(DB)
        for p in self.LEGS:
            P[p] = HM.cf_lerp(PA[p], PB[p], w)
        gp = L.grip_pivot
        ha = HM.rinv(PA['UpperTorso']) @ PA['Hammer'] @ gp
        hb = HM.rinv(PB['UpperTorso']) @ PB['Hammer'] @ gp
        P['Hammer'] = P['UpperTorso'] @ HM.cf_lerp(ha, hb, w) @ HM.rinv(gp)
        D = L.to_D(P)
        for s in HM.SIDES:
            ga, ra = self.screw_params(s, DA)
            gb, rb = self.screw_params(s, DB)
            r = ra + ((rb - ra + 180) % 360 - 180) * w
            D[s + 'Hand'] = D['Hammer'] @ rig.screw(s, ga + (gb - ga) * w, r)
        return L.to_D(L.constrain(L.reach_project(L.from_D(D))))


# ==================================================================== the double Spin
SPIN = ATTACKS['Spin']
REV = SPIN['finish'] - SPIN['active']                 # one active revolution: 16/36 s
SEAM_FADE = 0.1                                       # residual fade at the start of revolution 2


class DoubleSpin:
    """Spin with two full revolutions: the original wind-up, the original active revolution, the
    same revolution again, then the original recovery (everything after the first revolution shifted
    by REV). The original revolution turns the hammer at a constant 810 deg/s, so revolution 2 starts
    at the speed revolution 1 ends with. Its pose after 360 deg is 0.17 studs (mesh points) from the
    pose it started from, so revolution 2 starts exactly on revolution 1's last pose: each joint's
    local residual (L_start^-1 L_end) rides on top of revolution 2 and fades out over SEAM_FADE."""

    def __init__(self, baker, fade=SEAM_FADE):
        self.b, self.fade = baker, fade
        self.duration = SPIN['duration'] + REV
        self.seam = SPIN['finish']
        A = baker.pose('Spin', SPIN['finish'])
        B = baker.pose('Spin', SPIN['active'])
        LA, LB = HM.joint_locals(baker.rig, A), HM.joint_locals(baker.rig, B)
        self.res = {k: HM.rinv(LB[k]) @ LA[k] for k in LA}
        # times in the double clip (seconds): one phase per revolution
        self.revs = [(SPIN['active'], SPIN['finish']), (SPIN['finish'], SPIN['finish'] + REV)]

    def pose(self, t):
        b = self.b
        if t <= SPIN['finish']:
            return b.pose('Spin', t)
        if t <= SPIN['finish'] + REV:
            s = t - SPIN['finish']
            B = b.pose('Spin', SPIN['active'] + s)
            if s >= self.fade:
                return B
            LB = HM.joint_locals(b.rig, B)
            E = HM.from_locals(b.rig, {k: LB[k] @ self.res[k] for k in LB})
            return b.crossfade(E, B, HM.smoother(s / self.fade))
        return b.pose('Spin', t - REV)


# ==================================================================== combos
class Combo:
    """A then B with a crossfade: A plays to cutA, then over `fade` seconds the pose fades from A
    (still playing) to B (starting at cutB), then B plays on. A's recovery after cutA + fade and B's
    wind-up before cutB are trimmed. Times in B shift by cutA - cutB."""

    def __init__(self, baker, A, B, cutA, cutB, fade):
        self.b, self.A, self.B = baker, A, B
        self.cutA, self.cutB, self.fade = cutA, cutB, fade
        self.shift = cutA - cutB
        self.duration = cutA + (B.duration - cutB)

    def pose(self, t):
        if t <= self.cutA:
            return self.A.pose(t)
        tb = t - self.shift
        if t >= self.cutA + self.fade:
            return self.B.pose(tb)
        w = HM.smoother((t - self.cutA) / self.fade)
        return self.b.crossfade(self.A.pose(t), self.B.pose(tb), w)


class Single:
    """One original clip as a timeline source."""

    def __init__(self, baker, name):
        self.b, self.name = baker, name
        self.duration = baker.L.clips[name]['duration']

    def pose(self, t):
        return self.b.pose(self.name, t)


def sample_frames(src, fps):
    n = int(round(src.duration * fps))
    return [src.pose(k / fps) for k in range(n + 1)]
