"""Motion checks for the DJ Crab, shared by animate_game.py (source rig) and
validate_exports.py (fresh FBX re-import posed from AnimationData.json).

All checks work from bone rest matrices (armature space), per-frame
matrix_basis dicts and the rigid mesh (every vertex weighted 1.0 to one bone):
- hinge directions: knee/ankle/elbow flex (-5..150 deg), pincer gape
  (-2..55 deg), leg lift and wrist inside rest +-60/75 deg
- twist about each limb bone's own axis vs rest (|twist| <= 70 deg)
- largest armature-space rotation of any bone between consecutive frames
  (<= 45 deg unless named as an intentional snap)
- lowest vertex per frame (>= -0.05)
- planted leg-tip drift (<= 0.05), with root motion for locomotion
- BVH surface overlaps: claws/legs vs shell+gear+eyes, claws vs legs,
  neighbouring legs, eyes vs shell+gear. Pairs already touching at rest
  (attachments) are reported separately.
"""
import math
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

I4 = Matrix.Identity(4)
LEG_TAGS = [f'{s}{i}' for s in 'LR' for i in (1, 2, 3, 4)]


class Skel:
    def __init__(self, rest, parent):
        self.rest, self.par = rest, parent
        order = []

        def visit(n):
            order.append(n)
            for c in sorted(k for k, p in parent.items() if p == n):
                visit(c)
        for n in sorted(k for k, p in parent.items() if p is None):
            visit(n)
        self.order = order
        self.lrest = {n: (rest[parent[n]].inverted() @ rest[n] if parent[n] else rest[n].copy()) for n in order}
        self.rest_inv = {n: rest[n].inverted() for n in order}

    def fk(self, basis):
        P = {}
        for n in self.order:
            B = basis.get(n, I4)
            P[n] = (P[self.par[n]] @ self.lrest[n] @ B) if self.par[n] else (self.lrest[n] @ B)
        return P


def _axis(M, i):
    return Vector((M[0][i], M[1][i], M[2][i])).normalized()


def hinge_angle(Pp, Pc):
    """Signed angle (deg) from the parent's axis to the child's, about the child's X (its hinge)."""
    yp, yc, xc = _axis(Pp, 1), _axis(Pc, 1), _axis(Pc, 0)
    return math.degrees(math.atan2(yp.cross(yc).dot(xc), yp.dot(yc)))


def joint_specs(skel):
    P = skel.fk({})
    specs = []
    for n in skel.order:
        p = skel.par[n]
        if p is None:
            continue
        r = hinge_angle(P[p], P[n])
        if n.startswith('Leg_') and n.endswith('_Carpus'):
            specs.append((n, 'knee', -5.0, 150.0, 1.0))
        elif n.startswith('Leg_') and n.endswith('_Dactyl'):
            specs.append((n, 'ankle', -5.0, 150.0, 1.0))
        elif n.startswith('Leg_') and n.endswith('_Merus'):
            specs.append((n, 'leg_lift', r - 60.0, r + 60.0, 1.0))
        elif n.startswith('Claw_') and n.endswith('_Carpus'):
            specs.append((n, 'elbow', -5.0, 150.0, 1.0))
        elif n.startswith('Claw_') and n.endswith('_Propodus'):
            specs.append((n, 'wrist', r - 75.0, r + 75.0, 1.0))
        elif n.startswith('Claw_') and n.endswith('_Dactyl'):
            specs.append((n, 'pincer_gape', -2.0, 55.0, -1.0))
    return specs


def twist_deg(B):
    q = B.to_quaternion()
    if q.w < 0:
        q.negate()
    t = 2.0 * math.degrees(math.atan2(q.y, q.w))
    return (t + 180.0) % 360.0 - 180.0


class RigidMesh:
    """verts: Nx3 rest positions; faces: list of index tuples; vbone: bone per vertex; vsec: section per vertex."""

    def __init__(self, verts, faces, vbone, vsec):
        self.verts = np.asarray(verts, np.float64)
        self.faces = faces
        self.vbone = np.asarray(vbone)
        self.vsec = np.asarray(vsec)
        self.bones = sorted(set(vbone))
        self.bidx = {b: np.nonzero(self.vbone == b)[0] for b in self.bones}
        self.groups = {}

    def posed(self, skel, P):
        out = np.empty_like(self.verts)
        for b, idx in self.bidx.items():
            M = np.array(P[b] @ skel.rest_inv[b])
            out[idx] = self.verts[idx] @ M[:3, :3].T + M[:3, 3]
        return out

    def add_group(self, name, mask):
        idx = np.nonzero(mask)[0]
        if not len(idx):
            return
        loc = -np.ones(len(self.verts), np.int64)
        loc[idx] = np.arange(len(idx))
        fs = [tuple(int(loc[i]) for i in f) for f in self.faces if all(loc[i] >= 0 for i in f)]
        self.groups[name] = (idx, fs)

    def bvh(self, name, posed):
        idx, fs = self.groups[name]
        return BVHTree.FromPolygons([tuple(v) for v in posed[idx]], fs)


def default_groups(mesh):
    vb, vs = mesh.vbone, mesh.vsec
    mesh.add_group('shell', (vb == 'Body') & (vs == 'Shell'))
    mesh.add_group('gear', np.isin(vs, ['Gear', 'Glow']))
    mesh.add_group('eyes', vs == 'Eyes')
    for t in LEG_TAGS:
        mesh.add_group(f'leg_{t}', np.isin(vb, [f'Leg_{t}_Merus', f'Leg_{t}_Carpus', f'Leg_{t}_Dactyl']))
    for s in 'LR':
        mesh.add_group(f'claw_{s}', np.isin(vb, [f'Claw_{s}_Carpus', f'Claw_{s}_Propodus', f'Claw_{s}_Dactyl']))
        mesh.add_group(f'clawarm_{s}', vb == f'Claw_{s}_Merus')
    pairs = []
    for s in 'LR':
        pairs += [(f'claw_{s}', 'shell'), (f'claw_{s}', 'gear'), (f'claw_{s}', 'eyes'), (f'clawarm_{s}', 'shell'),
                  (f'clawarm_{s}', 'gear'), (f'clawarm_{s}', 'eyes')]
        for i in (1, 2):
            pairs += [(f'claw_{s}', f'leg_{s}{i}'), (f'clawarm_{s}', f'leg_{s}{i}')]
        for i in (1, 2, 3):
            pairs.append((f'leg_{s}{i}', f'leg_{s}{i + 1}'))
    for t in LEG_TAGS:
        pairs += [(f'leg_{t}', 'shell'), (f'leg_{t}', 'gear')]
    pairs += [('claw_L', 'claw_R'), ('eyes', 'shell'), ('eyes', 'gear')]
    return [p for p in pairs if p[0] in mesh.groups and p[1] in mesh.groups]


def leg_tips(skel, P, blen):
    return {t: P[f'Leg_{t}_Dactyl'] @ Vector((0, blen[f'Leg_{t}_Dactyl'], 0)) for t in LEG_TAGS}


def run(skel, mesh, blen, clips, planted, travel=None, snaps=None, every=1, collide=True):
    """clips: {name: {'bases': [basis dicts], 'times': [s]}}; planted(clip, frame, tag) -> bool;
    travel: {clip: Vector studs/s of root motion}; snaps: {clip: {bone: [frames]}} allowed > 45 deg."""
    travel = travel or {}
    snaps = snaps or {}
    specs = joint_specs(skel)
    pairs = default_groups(mesh) if collide else []
    rest_posed = mesh.posed(skel, skel.fk({}))
    rest_contact = {}
    if collide:
        trees = {g: mesh.bvh(g, rest_posed) for g in mesh.groups}
        for a, b in pairs:
            rest_contact[f'{a}|{b}'] = len(trees[a].overlap(trees[b]))
    rep = {'clips': {}, 'rest_contacts': {k: v for k, v in rest_contact.items() if v}}
    joints_all = {}
    for name, c in clips.items():
        bases, times = c['bases'], c['times']
        e = {'frames': len(bases)}
        jr = {}
        viol = []
        tw_worst = (0.0, None, None)
        step_worst = (0.0, None, None)
        low = (9e9, None)
        drift = (0.0, None)
        runs = {t: [] for t in LEG_TAGS}
        overl = {}
        prevP = None
        v = travel.get(name, Vector((0, 0, 0)))
        for f, B in enumerate(bases):
            P = skel.fk(B)
            for (n, kind, lo, hi, sgn) in specs:
                a = sgn * hinge_angle(P[skel.par[n]], P[n])
                mn, mx = jr.get(n, (1e9, -1e9))
                jr[n] = (min(mn, a), max(mx, a))
                if a < lo - 1e-6 or a > hi + 1e-6:
                    viol.append([f, n, kind, round(a, 2)])
            for n, M in B.items():
                if n.startswith(('Leg_', 'Claw_')):
                    tw = abs(twist_deg(M))
                    if tw > tw_worst[0]:
                        tw_worst = (tw, f, n)
            if prevP is not None:
                for n in skel.order:
                    d = math.degrees(prevP[n].to_quaternion().rotation_difference(P[n].to_quaternion()).angle)
                    d = min(d, 360.0 - d)
                    if d > step_worst[0] and f not in snaps.get(name, {}).get(n, []):
                        step_worst = (d, f, n)
            prevP = P
            tips = leg_tips(skel, P, blen)
            for t in LEG_TAGS:
                if planted(name, f, t):
                    runs[t].append(tips[t] + v * times[f])
                else:
                    if len(runs[t]) > 1:
                        dd = max((p - runs[t][0]).length for p in runs[t])
                        if dd > drift[0]:
                            drift = (dd, t)
                    runs[t] = []
            if f % every == 0 or f == len(bases) - 1:
                pv = mesh.posed(skel, P)
                z = float(pv[:, 2].min())
                if z < low[0]:
                    low = (z, f)
                if collide:
                    trees = {g: mesh.bvh(g, pv) for g in mesh.groups}
                    for a, b in pairs:
                        k = f'{a}|{b}'
                        if rest_contact.get(k):
                            continue
                        ov = trees[a].overlap(trees[b])
                        if ov:
                            ia, fa = mesh.groups[a]
                            ib, fb = mesh.groups[b]
                            pa = pv[ia][list(fa[ov[0][0]])].mean(0)
                            pb = pv[ib][list(fb[ov[0][1]])].mean(0)
                            overl.setdefault(k, []).append([f, len(ov), [round(float(x), 2) for x in pa],
                                                            [round(float(x), 2) for x in pb]])
        for t in LEG_TAGS:
            if len(runs[t]) > 1:
                dd = max((p - runs[t][0]).length for p in runs[t])
                if dd > drift[0]:
                    drift = (dd, t)
        e['joint_range_deg'] = {n: [round(a, 1), round(b, 1)] for n, (a, b) in jr.items()}
        e['hinge_violations'] = viol[:20]
        e['hinge_violation_count'] = len(viol)
        e['max_twist_deg'] = [round(tw_worst[0], 2), tw_worst[1], tw_worst[2]]
        e['max_bone_rotation_per_frame_deg'] = [round(step_worst[0], 2), step_worst[1], step_worst[2]]
        e['lowest_point'] = [round(low[0], 4), low[1]]
        e['max_planted_tip_drift'] = [round(drift[0], 4), drift[1]]
        e['overlaps'] = {k: {'frames': len(v_), 'worst': max(v_, key=lambda q: q[1])} for k, v_ in overl.items()}
        rep['clips'][name] = e
        for n, (a, b) in jr.items():
            mn, mx = joints_all.get(n, (1e9, -1e9))
            joints_all[n] = (min(mn, a), max(mx, b))
    kinds = {n: k for (n, k, lo, hi, sg) in specs}
    by_kind = {}
    for n, (a, b) in joints_all.items():
        k = kinds[n]
        mn, mx = by_kind.get(k, (1e9, -1e9))
        by_kind[k] = (min(mn, a), max(mx, b))
    rep['joint_range_by_kind_deg'] = {k: [round(a, 1), round(b, 1)] for k, (a, b) in by_kind.items()}
    rep['joint_limits_deg'] = {k: [round(lo, 1), round(hi, 1)] for (n, k, lo, hi, sg) in specs
                               if n.startswith(('Leg_L1', 'Claw_R'))}
    rep['worst'] = {
        'hinge_violations': sum(e['hinge_violation_count'] for e in rep['clips'].values()),
        'twist_deg': max(e['max_twist_deg'][0] for e in rep['clips'].values()),
        'bone_rotation_per_frame_deg': max(e['max_bone_rotation_per_frame_deg'][0] for e in rep['clips'].values()),
        'lowest_point': min(e['lowest_point'][0] for e in rep['clips'].values()),
        'planted_tip_drift': max(e['max_planted_tip_drift'][0] for e in rep['clips'].values()),
        'overlap_frames': sum(v_['frames'] for e in rep['clips'].values() for v_ in e['overlaps'].values()),
    }
    return rep
