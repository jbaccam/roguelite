"""Creature attack choreography, driven by animate_mobs.py.

Body motion is keyed, then planted legs are re-solved to their resting tips
so feet never slide while the body lunges. Named bones take keyed
(pitch, yaw, roll) degrees added to rest. The scorpion tail is solved as a
planar constant-curvature arc whose stinger tip reaches a keyed target, so
the strike travels forward over the head instead of curling into it.
Forward is -Y; body offsets are (lateral, forward, up) in authoring units.
"""
import math
from mathutils import Vector, Quaternion, Matrix
from attack_design import hermite, smooth, V


class Creature:
    def __init__(self, g, spec):
        self.g, self.spec, self.pb = g, spec, g['pb']
        self.keys = []
        bones = set()
        for k in spec['keys']:
            bones |= set(k.get('bones', {}))
        for k in spec['keys']:
            e = {'t': k['t'], 'still': k.get('still', False), 'body': V(*k.get('body', (0, 0, 0))),
                 'brot': V(*k.get('brot', (0, 0, 0))), 'tip': V(0, *k['tip']) if 'tip' in k else None,
                 'lift': V(0, *k.get('lift', (0, 0)))}
            for b in bones:
                e['b:' + b] = V(*k.get('bones', {}).get(b, (0, 0, 0)))
            self.keys.append(e)
        self.bones = sorted(bones)
        self.tail = None
        if 'tail' in spec:
            self.setup_tail()

    def setup_tail(self):
        pb, g = self.pb, self.g
        names = self.spec['tail']
        pts = [pb[n].bone.head_local.copy() for n in names]
        tip = None
        for o in g['meshes']:
            grp = o.vertex_groups.get(names[-1])
            if not grp:
                continue
            for v in o.data.vertices:
                if any(x.group == grp.index and x.weight > .5 for x in v.groups):
                    p = o.matrix_world @ v.co
                    if tip is None or (p - pts[-1]).length > (tip - pts[-1]).length:
                        tip = p
        pts.append(tip)
        body = pb['Body'].bone.head_local.copy()
        # Work in the body's rest frame, (forward, up) = (-y, z).
        self.tail = {'names': names, 'rest': [V(0, -(p.y - body.y), p.z - body.z) for p in pts],
                     'len': [(pts[i + 1] - pts[i]).length for i in range(len(names))]}
        r = self.tail['rest']
        self.tail['restAngles'] = [math.atan2(r[i + 1].y - r[i].y, r[i + 1].z - r[i].z) for i in range(len(names))]
        # Rest keys use the exact rest tip.
        for e in self.keys:
            if e['tip'] is None:
                e['tip'] = V(0, r[-1].y, r[-1].z)

    def arc(self, a, b):
        """Joint positions for segment angles a + b*i (angle 0 = up, +forward)."""
        r, L = self.tail['rest'], self.tail['len']
        p = [r[0].copy()]
        for i, l in enumerate(L):
            ang = a + b * i
            p.append(p[-1] + V(0, math.sin(ang), math.cos(ang)) * l)
        return p

    def solve_tail(self, target):
        # Newton on (base angle, curvature) from a rest-like start.
        ra = self.tail['restAngles']
        a, b = ra[0], (ra[-1] - ra[0]) / (len(ra) - 1)
        for _ in range(40):
            tip = self.arc(a, b)[-1]
            err = V(0, target.y - tip.y, target.z - tip.z)
            if err.length < 1e-5:
                break
            h = 1e-4
            ta = self.arc(a + h, b)[-1]; tb = self.arc(a, b + h)[-1]
            j = [[(ta.y - tip.y) / h, (tb.y - tip.y) / h], [(ta.z - tip.z) / h, (tb.z - tip.z) / h]]
            det = j[0][0] * j[1][1] - j[0][1] * j[1][0]
            if abs(det) < 1e-9:
                break
            da = (j[1][1] * err.y - j[0][1] * err.z) / det
            db = (-j[1][0] * err.y + j[0][0] * err.z) / det
            s = min(1, .4 / max(abs(da), abs(db), 1e-9))
            a += da * s; b += db * s
        return a, b

    def pose(self, t):
        g, pb, k = self.g, self.pb, self.keys
        g['reset']()
        z = V(0, 0, 0)
        body = hermite(k, t, 'body', z)
        brot = hermite(k, t, 'brot', z)
        g['move']('Body', V(body.x, -body.y, body.z))
        g['rot']('Body', brot.x, (1, 0, 0))
        g['rot']('Body', brot.y, (0, 0, 1), True)
        g['rot']('Body', brot.z, (0, 1, 0), True)
        g['bpy'].context.view_layer.update()
        lift = hermite(k, t, 'lift', z)
        front = self.spec.get('liftLegs', ())
        for n in pb.keys():
            if 'Leg' in n and n.endswith('Upper'):
                target = g['leg_tips'][n.replace('Upper', 'Lower')].copy()
                if n in front:
                    target += V(0, -lift.y, lift.z)
                g['crawler_leg'](n, target)
        for b in self.bones:
            r = hermite(k, t, 'b:' + b, z)
            g['rot'](b, r.x, (1, 0, 0))
            g['rot'](b, r.y, (0, 0, 1), True)
            g['rot'](b, r.z, (0, 1, 0), True)
        if self.tail:
            self.pose_tail(hermite(k, t, 'tip', z))
        e = smooth(t / .06) * (1 - smooth((t - .94) / .06))
        if e < 1:
            for n, p in pb.items():
                l1, q1, s1 = p.matrix_basis.decompose()
                p.matrix_basis = Matrix.LocRotScale(l1 * e, Quaternion().slerp(q1, e), s1)
        g['bpy'].context.view_layer.update()

    def pose_tail(self, target):
        g, pb, T = self.g, self.pb, self.tail
        a, b = self.solve_tail(target)
        pts = self.arc(a, b)
        g['bpy'].context.view_layer.update()
        body = pb['Body']
        rb = (body.matrix.to_3x3() @ body.bone.matrix_local.to_3x3().inverted())
        origin = body.head
        def world(p):
            return origin + rb @ V(0, -p.y, p.z)
        rest = T['rest']
        for i, n in enumerate(T['names']):
            r0 = V(0, -(rest[i + 1].y - rest[i].y), rest[i + 1].z - rest[i].z)
            d1 = rb @ V(0, -(pts[i + 1].y - pts[i].y), pts[i + 1].z - pts[i].z)
            g['absolute'](n, world(pts[i]), r0.rotation_difference(d1))
        self.last_tail = [world(p) for p in pts]


CREATURES = {
    # Tail strike: the scorpion rears its front, spreads and opens its
    # pincers and coils the tail high over its back, then drives the stinger
    # forward over its own head into the target in front, the body dipping
    # into the lunge. Tip targets are (forward, up) from the body joint.
    'scorpion': {'tail': ['Tail0', 'Tail1', 'Tail2', 'Tail3', 'Tail4', 'Tail5', 'Tail6'], 'keys': [
        {'t': 0},
        {'t': .20, 'body': (0, -.04, .05), 'brot': (-4, 0, 0), 'tip': (-.35, 2.35),
         'bones': {'LeftArm': (0, -10, 0), 'RightArm': (0, 10, 0), 'LeftPincer': (0, 18, 0), 'RightPincer': (0, -18, 0)}},
        {'t': .38, 'still': True, 'body': (0, -.10, .12), 'brot': (-9, 0, 0), 'tip': (-.55, 2.65),
         'bones': {'LeftArm': (-10, -18, 0), 'RightArm': (-10, 18, 0), 'LeftPincer': (0, 30, 0), 'RightPincer': (0, -30, 0),
                   'LeftClaw': (-8, 0, 0), 'RightClaw': (-8, 0, 0)}},
        {'t': .44, 'body': (0, .10, .06), 'brot': (-2, 0, 0), 'tip': (.60, 2.95)},
        {'t': .48, 'body': (0, .22, -.02), 'brot': (5, 0, 0), 'tip': (2.10, 2.35),
         'bones': {'LeftArm': (4, 6, 0), 'RightArm': (4, -6, 0), 'LeftPincer': (0, -4, 0), 'RightPincer': (0, 4, 0)}},
        {'t': .56, 'still': True, 'body': (0, .26, -.05), 'brot': (7, 0, 0), 'tip': (2.55, 1.75),
         'bones': {'LeftArm': (4, 6, 0), 'RightArm': (4, -6, 0), 'LeftPincer': (0, -4, 0), 'RightPincer': (0, 4, 0)}},
        {'t': .76, 'body': (0, .10, 0), 'brot': (2, 0, 0), 'tip': (.20, 2.30)},
        {'t': 1},
    ]},
    # Pincer jab: the crab raises its right claw with the pincer gaping, jabs
    # it forward and snaps it shut, the left claw held up as a guard.
    'crab': {'keys': [
        {'t': 0},
        {'t': .38, 'still': True, 'body': (0, -.08, .06), 'brot': (-6, -8, 0),
         'bones': {'RightArm': (-22, 18, 0), 'RightClaw': (-18, 0, 0), 'RightPincer': (0, -34, 0),
                   'LeftArm': (-16, -10, 0), 'LeftClaw': (-10, 0, 0)}},
        {'t': .49, 'body': (0, .20, -.02), 'brot': (5, 6, 0),
         'bones': {'RightArm': (-6, -14, 0), 'RightClaw': (-2, 0, 0), 'RightPincer': (0, 6, 0),
                   'LeftArm': (-14, -8, 0), 'LeftClaw': (-8, 0, 0)}},
        {'t': .60, 'still': True, 'body': (0, .22, -.03), 'brot': (6, 8, 0),
         'bones': {'RightArm': (-4, -16, 0), 'RightClaw': (0, 0, 0), 'RightPincer': (0, 6, 0),
                   'LeftArm': (-12, -6, 0), 'LeftClaw': (-6, 0, 0)}},
        {'t': 1},
    ]},
    # Scissor clamp: the hermit crab hunkers into its shell, swings both big
    # claws wide open, then clamps them together in front of it.
    'hermit-crab': {'keys': [
        {'t': 0},
        {'t': .40, 'still': True, 'body': (0, -.12, -.04), 'brot': (-5, 0, 0),
         'bones': {'LeftArm': (-12, -34, 0), 'RightArm': (-12, 34, 0), 'LeftClaw': (-10, -10, 0), 'RightClaw': (-10, 10, 0),
                   'LeftPincer': (0, 30, 0), 'RightPincer': (0, -30, 0)}},
        {'t': .54, 'body': (0, .18, -.02), 'brot': (4, 0, 0),
         'bones': {'LeftArm': (2, 22, 0), 'RightArm': (2, -22, 0), 'LeftClaw': (2, 12, 0), 'RightClaw': (2, -12, 0),
                   'LeftPincer': (0, -4, 0), 'RightPincer': (0, 4, 0)}},
        {'t': .66, 'still': True, 'body': (0, .20, -.03), 'brot': (5, 0, 0),
         'bones': {'LeftArm': (2, 24, 0), 'RightArm': (2, -24, 0), 'LeftClaw': (2, 13, 0), 'RightClaw': (2, -13, 0),
                   'LeftPincer': (0, -4, 0), 'RightPincer': (0, 4, 0)}},
        {'t': 1},
    ]},
    # Rearing bite: the spider lifts its front legs and body with fangs
    # spread, then drops forward onto the target and snaps the fangs shut.
    'ember-spider': {'liftLegs': ('LeftLeg0Upper', 'RightLeg0Upper'), 'keys': [
        {'t': 0},
        {'t': .36, 'still': True, 'body': (0, -.18, .30), 'brot': (-16, 0, 0), 'lift': (.25, .75),
         'bones': {'LeftFang': (-26, -14, 0), 'RightFang': (-26, 14, 0)}},
        {'t': .46, 'body': (0, .30, .05), 'brot': (6, 0, 0), 'lift': (.45, .25),
         'bones': {'LeftFang': (-10, -6, 0), 'RightFang': (-10, 6, 0)}},
        {'t': .50, 'body': (0, .42, -.08), 'brot': (12, 0, 0), 'lift': (.40, .05),
         'bones': {'LeftFang': (18, 10, 0), 'RightFang': (18, -10, 0)}},
        {'t': .60, 'still': True, 'body': (0, .44, -.10), 'brot': (13, 0, 0), 'lift': (.35, 0),
         'bones': {'LeftFang': (20, 10, 0), 'RightFang': (20, -10, 0)}},
        {'t': .82, 'body': (0, .12, 0), 'brot': (3, 0, 0), 'lift': (.08, .08)},
        {'t': 1},
    ]},
    # One-two: the ghost jabs with the left mitten, then throws the right as
    # it surges forward, the body twisting behind each punch.
    'frost-ghost': {'keys': [
        {'t': 0},
        {'t': .28, 'still': True, 'body': (0, -.10, .04), 'brot': (-6, 0, 0),
         'bones': {'LeftArm': (-35, 0, 0), 'RightArm': (-35, 0, 0), 'Head': (4, 0, 0)}},
        {'t': .38, 'body': (0, .08, 0), 'brot': (4, 14, 0),
         'bones': {'LeftArm': (-88, 8, 0), 'RightArm': (-30, 0, 0), 'Head': (-2, -8, 0)}},
        {'t': .44, 'body': (0, .06, 0), 'brot': (2, 0, 0),
         'bones': {'LeftArm': (-45, 0, 0), 'RightArm': (-55, 0, 0)}},
        {'t': .50, 'body': (0, .26, -.02), 'brot': (8, -18, 0),
         'bones': {'LeftArm': (-30, 0, 0), 'RightArm': (-95, -10, 0), 'Head': (-4, 12, 0)}},
        {'t': .60, 'still': True, 'body': (0, .28, -.03), 'brot': (9, -20, 0),
         'bones': {'LeftArm': (-28, 0, 0), 'RightArm': (-92, -10, 0), 'Head': (-4, 12, 0)}},
        {'t': 1},
    ]},
}
IMPACT = {'scorpion': .48, 'crab': .49, 'hermit-crab': .54, 'ember-spider': .50, 'frost-ghost': .50}
