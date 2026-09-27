"""Per-mob attack choreography, driven by animate_mobs.py.

Every attack is authored for the specific body and weapon that performs it:
swords slash with the edge leading, the reverse-grip dagger stabs downward,
fists hook or cross, casters conjure in the hand they throw from and the
scorpion strikes forward over its head. Poses are keyed in the chest frame
and solved with two-bone arm IK, so wrist paths and blade orientation are
authored directly instead of emerging from stacked joint angles.

Coordinates are Blender armature space; the character faces -Y. "Lateral"
is measured away from the body on the named side (+X for Right* bones).
"""
import math
from mathutils import Vector, Quaternion, Matrix


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def frame(a, b):
    a = a.normalized()
    b = (b - a * a.dot(b)).normalized()
    return Matrix((a, b, a.cross(b))).transposed()


def hermite(keys, t, field, zero):
    """Non-uniform Catmull-Rom through keyed values. `still` keys stop."""
    times = [k['t'] for k in keys]
    if t <= times[0]:
        return keys[0][field]
    if t >= times[-1]:
        return keys[-1][field]
    i = max(j for j in range(len(keys) - 1) if times[j] <= t)
    a, b = keys[i], keys[i + 1]
    h = b['t'] - a['t']
    u = (t - a['t']) / h

    def tangent(j):
        k = keys[j]
        if k.get('still') or j == 0 or j == len(keys) - 1:
            return zero
        return (keys[j + 1][field] - keys[j - 1][field]) * (h / (keys[j + 1]['t'] - keys[j - 1]['t']))

    m0, m1 = tangent(i), tangent(i + 1)
    h00 = 2 * u ** 3 - 3 * u ** 2 + 1
    h10 = u ** 3 - 2 * u ** 2 + u
    h01 = -2 * u ** 3 + 3 * u ** 2
    h11 = u ** 3 - u ** 2
    return a[field] * h00 + m0 * h10 + b[field] * h01 + m1 * h11


def V(*v):
    return Vector(v)


class Humanoid:
    """Keyed humanoid attack. `g` is the animate_mobs.py namespace."""

    def __init__(self, g, spec):
        self.g = g
        self.spec = spec
        pb = g['pb']
        self.pb = pb
        self.PELVIS, self.CHEST = g['PELVIS'], g['CHEST']
        self.H = g['leg_length']
        self.arms = {}
        for side in ('Left', 'Right'):
            up, fore, hand = side + 'UpperArm', g['name'](side, 'Forearm'), side + 'Hand'
            s0, e0, w0 = (pb[n].bone.head_local.copy() for n in (up, fore, hand))
            self.arms[side] = {'up': up, 'fore': fore, 'hand': hand, 'l1': (e0 - s0).length, 'l2': (w0 - e0).length,
                               'u0': e0 - s0, 'f0': w0 - e0, 'sx': 1 if side == 'Right' else -1}
        # The idle frame the attack starts and ends on.
        g['reset']()
        g['humanoid']('Idle', 0)
        g['bpy'].context.view_layer.update()
        self.idle = {n: p.matrix_basis.copy() for n, p in pb.items()}
        rc = self.chest_rotation()
        self.neutral = {}
        for side, arm in self.arms.items():
            S, E, W = pb[arm['up']].head, pb[arm['fore']].head, pb[arm['hand']].head
            local = rc.inverted() @ (W - S) / self.reach(side)
            d = (W - S).normalized()
            pole = (E - S) - d * d.dot(E - S)
            pole = rc.inverted() @ (pole.normalized() if pole.length > 1e-4 else V(0, 1, 0))
            hand = pb[arm['hand']].matrix.to_3x3() @ pb[arm['hand']].bone.matrix_local.to_3x3().inverted()
            self.neutral[side] = {'w': self.unside(side, local), 'pole': self.unside(side, pole),
                                  'hand': (rc.inverted() @ hand).to_quaternion()}
        self.feet = {side: pb[side + 'Foot'].bone.head_local.copy() + V(0, (.025 if side == 'Left' else -.025) * self.H, 0)
                     for side in ('Left', 'Right')}
        self.wrist_bend = 0.0
        self.diag = []
        self.t = 0
        # Comfortable wrist for each held weapon: the model's rest grip rotated
        # in the blade/forearm plane until the blade sits `grip` degrees from
        # the forearm. Deviations from this relation are the measured bend.
        self.grip = {}
        for side, w in spec['weapon'].items():
            f0 = self.arms[side]['f0'].normalized(); b = V(*w[0]).normalized()
            rest = f0.angle(b)
            self.grip[side] = Quaternion(f0.cross(b).normalized(), -(rest - math.radians(w[2])))
        self.keys = self.expand(spec['keys'])
        self.setup_clearance()
        # Solve elbow/pronation choices once, in frame order, so every sample
        # of the clip (export or preview) reuses the same continuous solution.
        self.count = g['attack_frames']
        self.cache = {}
        self.ref = {}
        self.forced = {}
        self.tips = {}
        for i in range(self.count + 1):
            self.ref = self.cache.get(i - 1, {})
            self.pose(i / self.count, solving=True)
            self.cache[i] = dict(self.solution)
        self.diag = []
        self.wrist_bend = 0.0

    def setup_clearance(self):
        """Sample the held weapon (vertices well clear of the fist) in the hand's
        rest frame, and fit capsule radii for the arm, chest and head so the
        solver can keep a blade out of its own body."""
        g, pb = self.g, self.pb
        import numpy as np
        def group_points(bone):
            pts = []
            for o in g['meshes']:
                grp = o.vertex_groups.get(bone)
                if not grp:
                    continue
                for v in o.data.vertices:
                    if any(x.group == grp.index and x.weight > .5 for x in v.groups):
                        pts.append(o.matrix_world @ v.co)
            return pts
        def seg_dist(p, a, b):
            d = b - a
            t = max(0.0, min(1.0, (p - a).dot(d) / max(d.length_squared, 1e-9)))
            return (p - (a + d * t)).length, t
        def radius(pts, a, b, q=.55):
            ds = sorted(seg_dist(p, a, b)[0] for p in pts)
            return ds[int(len(ds) * q)] if ds else 0
        self.clear = {}
        for side in self.spec['weapon']:
            a = self.arms[side]
            s0, e0, w0 = (pb[n].bone.head_local.copy() for n in (a['up'], a['fore'], a['hand']))
            hand_pts = group_points(a['hand'])
            far = sorted(hand_pts, key=lambda p: (p - w0).length)
            reach = (far[-1] - w0).length if far else 0
            sword = [p - w0 for p in far if (p - w0).length > .20 * reach][::3]
            dense = [p - w0 for p in far if (p - w0).length > .08 * reach]
            self.clear[side] = {'sword': sword, 'dense': dense, 'fore': radius(group_points(a['fore']), e0, w0),
                                'up': radius(group_points(a['up']), s0, e0)}
        c0 = pb[self.CHEST].bone.head_local.copy(); h0 = pb['Head'].bone.head_local.copy()
        head_pts = group_points('Head')
        hc = sum(head_pts, V(0, 0, 0)) / max(1, len(head_pts))
        self.body = {'chest': radius(group_points(self.CHEST), c0, h0, .45), 'headCentre': hc - h0,
                     'head': sorted((p - hc).length for p in head_pts)[int(len(head_pts) * .45)] if head_pts else 0}
        self.seg_dist = seg_dist

    def mesh_inside(self, bone):
        """Point-inside test against the current evaluated mesh of one bone."""
        from mathutils.bvhtree import BVHTree
        g = self.g
        dg = g['bpy'].context.evaluated_depsgraph_get()
        verts, polys = [], []
        for o in g['meshes']:
            grp = o.vertex_groups.get(bone)
            if not grp:
                continue
            own = {v.index for v in o.data.vertices if any(x.group == grp.index and x.weight > .5 for x in v.groups)}
            if not own:
                continue
            e = o.evaluated_get(dg); m = e.to_mesh()
            base = len(verts)
            index = {}
            for i in own:
                index[i] = len(verts); verts.append(o.matrix_world @ m.vertices[i].co)
            for p in m.polygons:
                if all(v in own for v in p.vertices):
                    polys.append([index[v] for v in p.vertices])
            e.to_mesh_clear()
        if not polys:
            return lambda pts: 0
        tree = BVHTree.FromPolygons(verts, polys)
        def test(pts):
            n = 0
            for p in pts:
                loc, nrm, _, dist = tree.find_nearest(p)
                if loc is not None and (p - loc).dot(nrm) < -.002:
                    n += 1
            return n
        return test

    def penetration(self, side, S, E, W, rh, torso):
        c = self.clear.get(side)
        if not c or not c['sword']:
            return 0.0
        a, b = torso
        head_c, head_r = self.head_world, self.body['head']
        total = 0.0
        for q in c['sword']:
            p = W + rh @ q
            d, t = self.seg_dist(p, E, W)
            if t < .8:
                total += max(0.0, c['fore'] + .03 - d) ** 2
            d, t = self.seg_dist(p, S, E)
            total += max(0.0, c['up'] + .03 - d) ** 2
            d, _ = self.seg_dist(p, a, b)
            total += max(0.0, self.body['chest'] + .03 - d) ** 2
            total += max(0.0, head_r + .03 - (p - head_c).length) ** 2
        return total

    def reach(self, side):
        return self.arms[side]['l1'] + self.arms[side]['l2']

    def unside(self, side, v):
        # Stored as (lateral, forward, up) for that side.
        return V(v.x * self.arms[side]['sx'], -v.y, v.z)

    def toworld(self, side, v):
        return V(v.x * self.arms[side]['sx'], -v.y, v.z)

    def chest_rotation(self):
        p = self.pb[self.CHEST]
        return p.matrix.to_3x3() @ p.bone.matrix_local.to_3x3().inverted()

    def expand(self, keys):
        """Fill defaults so every channel is keyed on every key."""
        out = []
        for k in keys:
            e = {'t': k['t'], 'still': k.get('still', False)}
            e['pelvis'] = V(*k.get('pelvis', (0, 0, 0)))
            e['pyaw'] = k.get('pyaw', 0.0)
            e['chest'] = V(*k.get('chest', (0, 0, 0)))
            e['head'] = V(*k.get('head', (0, 0, 0)))
            for side in ('Left', 'Right'):
                a = k.get(side, 'rest')
                n = self.neutral[side]
                if a == 'rest':
                    a = {}
                e[side + 'w'] = V(*a['w']) if 'w' in a else n['w'].copy()
                e[side + 'pole'] = V(*a['pole']) if 'pole' in a else n['pole'].copy()
                e[side + 'aim'] = a.get('blade') is not None
                e[side + 'blade'] = V(*a.get('blade', (0, 0, 1)))
                e[side + 'edge'] = V(*a.get('edge', (1, 0, 0)))
                e[side + 'twist'] = a.get('twist', 0.0)
                e[side + 'flex'] = V(*a.get('flex', (0, 0, 0)))
            for side in ('Left', 'Right'):
                e[side + 'foot'] = V(*k.get(side + 'Foot', (0, 0, 0)))
            out.append(e)
        # A hand aimed in any key is aimed in all keys, using its idle
        # orientation in keys that do not specify an aim.
        for side in ('Left', 'Right'):
            if any(e[side + 'aim'] for e in out):
                rest_blade, rest_edge = self.spec['weapon'][side][:2]
                n = self.neutral[side]['hand']
                for e in out:
                    if not e[side + 'aim']:
                        e[side + 'blade'] = self.unside(side, n @ V(*rest_blade))
                        e[side + 'edge'] = self.unside(side, n @ V(*rest_edge))
                        e[side + 'aim'] = True
        return out

    def arm(self, side, w, pole, blade, edge, aim, twist, flex):
        """Two-bone IK. The elbow direction (and, for held weapons, forearm
        pronation) is searched each frame: the wrist should stay near its
        comfortable grip, the upper arm should roll little from rest, the
        elbow should follow the authored hint, and it should not jump between
        consecutive frames."""
        g, pb, a = self.g, self.pb, self.arms[side]
        g['bpy'].context.view_layer.update()
        rc = self.chest_rotation()
        S = pb[a['up']].head.copy()
        W = S + rc @ self.toworld(side, w) * self.reach(side)
        pref = rc @ self.toworld(side, pole)
        l1, l2 = a['l1'], a['l2']
        d = W - S
        dist = max(abs(l1 - l2) + .001, min(l1 + l2 - .002, d.length))
        dn = d.normalized()
        W = S + dn * dist
        along = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
        height = math.sqrt(max(0, l1 * l1 - along * along))
        e1 = dn.orthogonal().normalized(); e2 = dn.cross(e1)
        pref = pref - dn * pref.dot(dn)
        pref = pref.normalized() if pref.length > 1e-5 else e1
        b0 = V(0, -1, 0)
        u0n, f0 = a['u0'].normalized(), a['f0'].normalized()
        n0 = u0n.cross(b0 - u0n * u0n.dot(b0)).normalized()
        rest_u = frame(a['u0'], b0).inverted()
        rest_f = frame(a['f0'], n0).inverted()
        neutral = self.grip.get(side, Quaternion())
        full = None
        if aim:
            spec = self.spec['weapon'][side]
            rest_blade = V(*spec[0]).normalized()
            bw = (rc @ self.toworld(side, blade)).normalized()
            if len(spec) > 3 and spec[3]:
                # Fully oriented hand (an open palm): fingers and palm normal.
                ew = rc @ self.toworld(side, edge)
                full = (frame(bw, ew) @ frame(rest_blade, V(*spec[1])).inverted()).to_quaternion()
        ref = self.ref.get(side)
        forced = self.forced.get(side)
        # Edge-leading swings: the blade's flat must not face its direction of
        # travel, so a slash lands on the sharpened edge.
        lead = None
        if aim and full is None and len(self.spec['weapon'][side]) > 1:
            width0 = V(*self.spec['weapon'][side][1]).normalized()
            tip = W + bw * self.spec.get('bladeLength', 1.0)
            self.tips[side] = tip
            if ref is not None and len(ref) > 2 and (tip - ref[2]).length > 1e-3:
                lead = (tip - ref[2]).normalized()
        rollw = self.spec.get('rollWeight', .5)
        polew = self.spec.get('poleWeight', 1.0)
        lim = self.spec.get('tauLimit', 90)
        taus = range(-lim, lim + 1, 10) if aim else (0,)
        best = None

        def ang(q):
            x = q.angle
            return min(x, 2 * math.pi - x)
        candidates = [forced[0]] if forced else [e1 * math.cos(math.tau * i / 48) + e2 * math.sin(math.tau * i / 48) for i in range(48)]
        if forced:
            taus = (forced[1],)
        chest_bone, head_bone = pb[self.CHEST], pb['Head']
        torso = (chest_bone.head.copy(), head_bone.head.copy())
        hb = head_bone.matrix.to_3x3() @ head_bone.bone.matrix_local.to_3x3().inverted()
        self.head_world = head_bone.head + hb @ self.body['headCentre']
        # Self-clearance governs wind-up and recovery; inside the strike the
        # edge-first rule wins so the cut never lands flat.
        lo, hi = self.spec.get('strikeWindow', (.40, .64))
        clearw = self.spec.get('clearWeight', 0) if aim and full is None and not (lo <= self.t <= hi) else 0
        for pp in candidates:
            E = S + dn * along + pp * height
            u1, f1, b1 = E - S, W - E, -pp
            ru = (frame(u1, b1) @ rest_u).to_quaternion()
            roll = ang(a['u0'].rotation_difference(u1).inverted() @ ru)
            rf0 = (frame(f1, u1.cross(b1)) @ rest_f).to_quaternion()
            base = rollw * (roll / math.radians(70)) ** 2 + polew * (pp.angle(pref) / math.radians(50)) ** 2
            if ref is not None:
                base += 4 * (pp.angle(ref[0]) / math.radians(20)) ** 2
            for tau in taus:
                cost = base
                if aim:
                    rf = rf0 @ Quaternion(f0, math.radians(tau))
                    if full is not None:
                        bend = ang(rf.inverted() @ full @ neutral.inverted())
                    else:
                        natural = (rf @ neutral) @ rest_blade
                        bend = natural.angle(bw)
                        if clearw:
                            cost += clearw * self.penetration(side, S, E, W, natural.rotation_difference(bw) @ rf @ neutral, torso)
                        if lead is not None:
                            width = (natural.rotation_difference(bw) @ rf @ neutral) @ width0
                            cost += self.spec.get('edgeWeight', 6) * bw.cross(width).normalized().dot(lead) ** 2
                    cost += (bend / math.radians(30)) ** 2 + .3 * (tau / 90) ** 2
                    if ref is not None:
                        cost += 2 * ((tau - ref[1]) / 30) ** 2
                if best is None or cost < best[0]:
                    best = (cost, pp, tau, E, ru, rf0)
        _, pp, tau, E, ru, rf0 = best
        self.solution[side] = (pp.copy(), tau, self.tips.get(side, V(0, 0, 0)).copy())
        if aim:
            rf = rf0 @ Quaternion(f0, math.radians(tau))
            natural = (rf @ neutral) @ rest_blade
            rh = full if full is not None else natural.rotation_difference(bw) @ rf @ neutral
        else:
            rf = rf0 @ Quaternion(f0, math.radians(twist))
            rh = rf.copy()
            if flex.length > 0:
                rh = rh @ Quaternion(f0.cross(b0).normalized(), math.radians(flex.x)) @ Quaternion(b0, math.radians(flex.y))
        if aim and full is None and clearw and self.penetration(side, S, E, W, rh, torso) > 0:
            # Tip the wrist away from the forearm (opening the blade/forearm
            # angle) just far enough for the weapon to clear the arm.
            fdir = (W - E).normalized()
            blade_now = rh @ rest_blade
            hinge = fdir.cross(blade_now)
            if hinge.length > 1e-4:
                hinge.normalize()
                for step in range(1, 9):
                    trial = Quaternion(hinge, math.radians(5 * step)) @ rh
                    if self.penetration(side, S, E, W, trial, torso) == 0:
                        rh = trial
                        break
                else:
                    rh = Quaternion(hinge, math.radians(40)) @ rh
        g['absolute'](a['up'], S, ru)
        g['absolute'](a['fore'], E, rf)
        g['absolute'](a['hand'], W, rh)
        bend = math.degrees(ang(rf.inverted() @ rh @ neutral.inverted())) if aim else 0
        roll = math.degrees(ang(a['u0'].rotation_difference(E - S).inverted() @ ru))
        self.wrist_bend = max(self.wrist_bend, bend)
        flat = 0
        if aim and full is None and lead is not None:
            flat = abs(bw.cross(rh @ V(*self.spec['weapon'][side][1]).normalized()).normalized().dot(lead))
            self.flat_lead = max(getattr(self, 'flat_lead', 0), flat) if self.t > .3 and self.t < .62 else getattr(self, 'flat_lead', 0)
        self.diag.append((self.t, side, round(roll), round(bend), round(flat, 2)))

    def pose(self, t, solving=False):
        g, pb = self.g, self.pb
        self.t = round(t, 3)
        self.solution = {}
        self.tips = {}
        self.forced = {}
        if not solving:
            i = min(self.count, max(0, round(t * self.count)))
            self.ref = self.cache[i]
            if abs(t * self.count - i) < 1e-6:
                # Exact clip frames reuse the solved choice verbatim.
                self.forced = {k: v for k, v in self.cache[i].items()}
        g['reset']()
        for n, m in self.idle.items():
            pb[n].matrix_basis = m
        k = self.keys
        z = V(0, 0, 0)
        pel = hermite(k, t, 'pelvis', z) * self.H
        pel = V(pel.x, -pel.y, pel.z)
        pyaw = hermite(k, t, 'pyaw', 0.0)
        chest = hermite(k, t, 'chest', z)
        head = hermite(k, t, 'head', z)
        base = pb[self.PELVIS].location.copy()
        g['move'](self.PELVIS, pb[self.PELVIS].bone.matrix_local.to_3x3() @ base + pel)
        g['rot'](self.PELVIS, pyaw, (0, 0, 1), True)
        g['rot'](self.CHEST, chest.x, (1, 0, 0), True)
        g['rot'](self.CHEST, chest.y, (0, 0, 1), True)
        g['rot'](self.CHEST, chest.z, (0, 1, 0), True)
        g['rot']('Head', head.x, (1, 0, 0), True)
        g['rot']('Head', head.y, (0, 0, 1), True)
        g['rot']('Head', head.z, (0, 1, 0), True)
        for side in ('Left', 'Right'):
            self.arm(side, hermite(k, t, side + 'w', z), hermite(k, t, side + 'pole', z),
                     hermite(k, t, side + 'blade', z), hermite(k, t, side + 'edge', z), k[0][side + 'aim'],
                     hermite(k, t, side + 'twist', 0.0), hermite(k, t, side + 'flex', z))
        for side in ('Left', 'Right'):
            off = hermite(k, t, side + 'foot', z) * self.H
            g['leg_ik'](side, self.feet[side] + V(0, -off.y, off.z) + V(off.x * (1 if side == 'Right' else -1), 0, 0))
        # Exact idle continuity at both ends of the clip; `settle` eases the
        # recovery into the exact (collision-free) ready pose over a longer tail.
        settle = self.spec.get('settle', .06)
        e = smooth(t / .06) * (1 - smooth((t - (1 - settle)) / settle))
        if e < 1:
            for n, p in pb.items():
                l0, q0, s0 = self.idle[n].decompose()
                l1, q1, s1 = p.matrix_basis.decompose()
                p.matrix_basis = Matrix.LocRotScale(l0.lerp(l1, e), q0.slerp(q1, e), s0.lerp(s1, e))
        g['bpy'].context.view_layer.update()
        self.clear_blended(t)

    def clear_blended(self, t):
        """After any idle blend, tip a weapon hand that would touch its own
        arm or body away from the forearm until it clears."""
        lo, hi = self.spec.get('strikeWindow', (.40, .64))
        if not self.spec.get('clearWeight', 0) or lo <= t <= hi:
            return
        g, pb = self.g, self.pb
        for side, w in self.spec['weapon'].items():
            if len(w) > 3 and w[3]:
                continue
            a = self.arms[side]
            S, E, W = (pb[n].head.copy() for n in (a['up'], a['fore'], a['hand']))
            hp = pb[a['hand']]
            rh = (hp.matrix.to_3x3() @ hp.bone.matrix_local.to_3x3().inverted()).to_quaternion()
            chest_bone, head_bone = pb[self.CHEST], pb['Head']
            torso = (chest_bone.head.copy(), head_bone.head.copy())
            hb = head_bone.matrix.to_3x3() @ head_bone.bone.matrix_local.to_3x3().inverted()
            self.head_world = head_bone.head + hb @ self.body['headCentre']
            count = self.mesh_inside(a['fore'])
            dense = self.clear[side]['dense']
            def hits(q):
                return count([W + q @ p for p in dense])
            now = hits(rh)
            if now == 0:
                continue
            hinge = (W - E).normalized().cross(rh @ V(*w[0]).normalized())
            if hinge.length < 1e-4:
                continue
            hinge.normalize()
            # Smallest tip (either way, up to 30 degrees) that removes the most
            # contact; applied only when it actually improves on the pose.
            best, best_n = rh, now
            for step in range(1, 7):
                for sign in (1, -1):
                    trial = Quaternion(hinge, math.radians(5 * step * sign)) @ rh
                    n = hits(trial)
                    if n < best_n:
                        best, best_n = trial, n
                if best_n == 0:
                    break
            if best is not rh:
                g['absolute'](a['hand'], W, best)
        g['bpy'].context.view_layer.update()


from attack_keys import HUMANOIDS, IMPACT  # noqa: E402  (choreography lives with its data)
