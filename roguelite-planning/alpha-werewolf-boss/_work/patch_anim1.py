p = 'animate_game.py'
s = open(p, encoding='utf-8').read()


def rep(a, b):
    global s
    assert a in s, a[:100]
    s = s.replace(a, b, 1)


def cut(a_mark, b_mark, new):
    global s
    a = s.index(a_mark)
    b = s.index(b_mark)
    s = s[:a] + new + s[b:]


# ---- locomotion: gentler heel kick / knee drive (knee <= ~125 deg, smaller per-frame thigh rotation)
rep("lean=(8, 4, 4), pitchBob=2, neck=-6, swing=[(.30, 1.55, 2.15), (.55, -.55, 1.85)],",
    "lean=(8, 4, 4), pitchBob=2, neck=-6, swing=[(.30, 1.35, 1.85), (.56, -.55, 1.55)],")
rep("lean=(18, 10, 10), pitchBob=3, neck=-14, swing=[(.30, 1.20, 2.00), (.55, -.85, 1.60)],",
    "lean=(18, 10, 10), pitchBob=3, neck=-14, swing=[(.28, 1.05, 1.70), (.56, -.80, 1.22)],")

# ---- Hit: every lagged envelope finishes by the last frame
cut("def hit_desc(t):", "# ------------------------------------------------------------------ Howl", '''def hit_desc(t):
    d = rest_desc()
    END = 11 / FPS

    def env(t, lag=0.):
        x = t - lag
        if x <= 0:
            return 0.
        if x < .083:
            return 1 - (1 - x / .083) ** 2
        return 1 - sm(lag + .083, END, t)
    h = env(t)
    hl = env(t, .05)
    d['pel'] = Vector((0, .18 * h, -.10 * h))
    d['pelR'] = (-4 * h, 0, 3 * h)
    d['spine'] = (-5 * h, 0, 2 * h)
    d['chest'] = (-9 * h, 2 * h, 4 * h)
    d['neck'] = (-6 * h, 0, 0)
    d['head'] = (-10 * h, -4 * h, 8 * h)
    d['jaw'] = 16 * h
    d['armLeft'] = {'mode': 'chest', 'off': Vector((.25, .45, .55)) * h}
    d['armRight'] = {'mode': 'chest', 'off': Vector((-.15, .35, .40)) * h}
    for S, s in SIDES:
        d['sh' + S] = (8 * h, -4 * h)
        d['fing' + S] = 30 * h
    d['mane'] = (-7 * hl, 0, 3 * hl)
    d['tail'] = [(-6 * hl, 0, 12 * hl), (-4 * hl, 0, 10 * hl), (0, 0, 8 * env(t, .09))]
    return d


''')

# ---- ClawRake: windup high and WIDE, overhead arc spread over more frames, impact at chest height
cut("KT = [0, .08, .30, .40, .50, .58, .66, .76, .95, RAKE_END]", "def rake_desc(t):", '''KT = [0, .08, .27, .35, .43, .50, .58, .66, .76, .95, RAKE_END]
A0 = {S: WRIST0[S] - HEAD[S + 'UpperArm'] for S, s in SIDES}
P0L = LIMBS['LeftUpperArm']['p0']
U = lambda *v: Vector(v).normalized()
RK = {'pel': ch(KT, [Vector(v) for v in [(0, 0, 0), (0, .10, -.10), (0, .38, -.28), (0, 0, -.40), (0, -.70, -.52), (0, -1.10, -.60),
                                          (0, -1.18, -.64), (0, -1.16, -.62), (0, -1.02, -.54), (0, -.25, -.12), (0, 0, 0)]]),
      'pelR': ch(KT, [0, 1, -5, 0, 8, 13, 15, 15, 12, 3, 0]), 'spine': ch(KT, [0, 0, -8, -3, 5, 9, 11, 11, 8, 2, 0]),
      'chest': ch(KT, [0, -2, -12, -6, 6, 11, 12, 12, 8, 2, 0]), 'neck': ch(KT, [0, 0, 4, 2, -6, -10, -11, -11, -8, -2, 0]),
      'head': ch(KT, [0, 2, 10, 6, -6, -12, -14, -14, -10, -2, 0]), 'jaw': ch(KT, [0, 6, 22, 24, 28, 30, 26, 20, 14, 4, 0]),
      'sh': ch(KT, [(0, 0), (6, -2), (20, -8), (16, 0), (8, 10), (4, 14), (2, 12), (0, 10), (0, 4), (0, 1), (0, 0)]),
      'dir': ch(KT, [A0['Left'].normalized(), U(.70, .10, -.70), U(.80, .22, .55), U(.55, -.35, .75), U(.10, -.90, .25),
                     U(-.10, -.80, -.59), U(-.04, -.25, -.97), U(.20, .30, -.93), U(.30, .60, -.74), U(.24, .08, -.97),
                     A0['Left'].normalized()]),
      'dist': ch(KT, [A0['Left'].length, 3.05, 2.45, 2.70, 3.10, 3.30, 3.30, 3.25, 3.05, 3.30, A0['Left'].length]),
      'pole': ch(KT, [P0L, U(.6, .5, -.6), U(.40, .45, -.80), U(.35, .75, -.55), U(.25, .80, -.55), U(.15, .75, -.65),
                      U(.15, .80, -.6), U(.2, .8, -.55), U(.2, .85, -.5), U(.3, .6, -.6), P0L]),
      'pw': ch(KT, [0, .5, 1, 1, 1, 1, 1, 1, 1, .5, 0]), 'wrist': ch(KT, [0, 0, 10, 8, 4, 0, -4, -8, -6, 0, 0]),
      'fing': ch(KT, [0, 0, 0, 0, 8, 22, 30, 35, 30, 8, 0]), 't1': ch(KT, [0, 4, 20, 20, 24, 30, 34, 35, 30, 8, 0]),
      'ty': ch(KT, [0, 0, 0, 4, 8, 12, 4, -8, -10, -2, 0]), 'mane': ch(KT, [0, 0, -4, -6, -2, 2, 8, 8, 6, 2, 0]),
      'heelL': ch([0, .40, .50, .70, .90, RAKE_END], [0, 0, 22, 22, 0, 0])}


''')
rep("    d['tail'] = [(t1, 0, ty), (.5 * t1, 0, .8 * RK['ty'](t - .05)), (.3 * t1, 0, .6 * RK['ty'](t - .1))]",
    "    fade = 1 - sm(.95, RAKE_END, t)\n    d['tail'] = [(t1, 0, ty), (.5 * t1, 0, .8 * RK['ty'](t - .05) * fade), (.3 * t1, 0, .6 * RK['ty'](t - .1) * fade)]")

# ---- ChargeStart: the brushing hand is placed from the real mesh; pole blends in with k
rep("    d['armRight'] = {'mode': 'mix', 'off': Vector(), 'w': w, 'k': k, 'pole': Vector((-.5, .6, -.6))}\n    cw = sm(.24, .33, t)\n    if cw > 0:\n        for _ in range(3):        # put the claw tips 0.06 above the ground\n            P, _, _ = solve(d)\n            w = w - Vector((0, 0, cw * (claw_tip(P, 'Right').z - .06)))\n            d['armRight']['w'] = w\n    return d",
    """    d['armRight'] = {'mode': 'mix', 'off': Vector(), 'w': w, 'k': k, 'pole': Vector((-.5, .6, -.6)), 'pw': k}
    cw = sm(.24, .33, t)
    if cw > 0:
        for _ in range(4):        # lowest claw of the real skinned hand 0.04 above the ground
            P, _, _ = solve(d)
            set_pose(to_basis(P))
            hv = eval_section('Hands')
            low = float(hv[hv[:, 0] < 0][:, 2].min())
            w = w - Vector((0, 0, cw * (low - .04)))
            d['armRight']['w'] = w
    return d""")

# ---- Death: smoother leg release (pole rotates with the pelvis), the top arm drapes forward onto the ground
rep("      'armR': ch(DT, [Vector(v) for v in [(0, 0, 0), (-.6, .4, 1.0), (-.3, -.2, .4), (0, -.4, .2), (-.4, .3, .8), (-.2, -.4, .3),\n                                           (-.1, -.6, .2), (-.1, -.7, .1), (-.1, -.7, .1)]]),",
    "      'armR': ch(DT, [Vector(v) for v in [(0, 0, 0), (-.6, .4, 1.0), (-.3, -.2, .4), (0, -.4, .2), (-.2, -.2, .7), (.9, -1.0, .6),\n                                           (1.4, -1.3, .45), (1.6, -1.4, .4), (1.6, -1.4, .4)]]),")
rep("        w = sm(.85, 1.25, t) if S == 'Left' else sm(.80, 1.20, t)", "        w = sm(.80, 1.40, t) if S == 'Left' else sm(.75, 1.35, t)")
rep("            rel = {'ankle': Tp @ relax[S], 'R': Rr, 'toe': Rr, 'yaw': 0, 'pole': E(d['pelR']) @ LIMBS[S + 'Thigh']['p0']}\n            p = planted[S]\n            d['foot' + S] = {'ankle': p['ankle'].lerp(rel['ankle'], w), 'R': slerp3(p['R'], Rr, w), 'toe': slerp3(p['toe'], Rr, w), 'yaw': 0,\n                             'pole': (LIMBS[S + 'Thigh']['p0'].lerp(rel['pole'], w)).normalized()}",
    "            p = planted[S]\n            pr = d['pelR']\n            d['foot' + S] = {'ankle': p['ankle'].lerp(Tp @ relax[S], w), 'R': slerp3(p['R'], Rr, w), 'toe': slerp3(p['toe'], Rr, w), 'yaw': 0,\n                             'pole': E((pr[0] * w, pr[1] * w, pr[2] * w)) @ LIMBS[S + 'Thigh']['p0']}")
rep("        if ground:\n            for _ in range(2):", "        if ground:\n            for _ in range(8):")

# ---- mesh helper for one section
rep("def zmin(V):", """def eval_section(sec):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = SECS[sec].evaluated_get(dg)
    me = ev.to_mesh()
    a = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', a)
    ev.to_mesh_clear()
    return a.reshape(-1, 3)


def zmin(V):""")

# ---- penetration: posed collision cores instead of nearest-face signs
cut("def bvh(verts, tris):", "JOINTS = {'Neck': ('Neck', 1.0)}", '''# Collision cores in REST space (studs), each carried by its bone; a little inside the
# real surface so only true pass-through counts. Points are moved back into each
# core's rest space with (P[bone] @ REST[bone]^-1)^-1, then tested.
TORSO_CORES = [('Pelvis', Vector((0, .05, 3.85)), Vector((1.10, .74, .62))), ('Spine', Vector((0, .02, 4.75)), Vector((1.08, .78, .55))),
               ('Chest', Vector((0, -.08, 5.85)), Vector((1.40, .92, .80)))]
HEAD_CORE = ('Head', Vector((0, -.82, 7.75)), Vector((.66, .60, .52)))
LEG_CAPS = [(S + b, HEAD[S + b], HEAD[S + c], r) for S, s in SIDES for b, c, r in (('Thigh', 'Shin', .52), ('Shin', 'Foot', .42))]


def to_rest(P, bone, pts):
    M = np.array((P[bone] @ REST[bone].inverted()).inverted())
    return pts @ M[:3, :3].T + M[:3, 3]


def ell_depth(P, core, pts):
    bone, c, a = core
    q = (to_rest(P, bone, pts) - np.array(c)) / np.array(a)
    r = np.sqrt((q ** 2).sum(1))
    return np.clip(1 - r, 0, None) * min(a)


def cap_depth(P, cap, pts):
    bone, A, B, r = cap
    q = to_rest(P, bone, pts)
    A = np.array(A)
    v = np.array(B) - A
    t = np.clip(((q - A) @ v) / (v @ v), 0, 1)
    d = np.linalg.norm(q - (A + t[:, None] * v), axis=1)
    return np.clip(r - d, 0, None)


def pen_sets(V, P):
    arms = np.concatenate([V['Hands']] + [V['Body'][fore_idx[S]] for S, s in SIDES])
    r = {'armsThroughTorso': max(float(ell_depth(P, c, arms).max()) for c in TORSO_CORES),
         'handsThroughLegs': max(float(cap_depth(P, c, V['Hands']).max()) for c in LEG_CAPS),
         'snoutThroughTorso': max(float(ell_depth(P, c, V['Head'][snout_idx]).max()) for c in TORSO_CORES),
         'maneThroughHead': float(ell_depth(P, HEAD_CORE, V['Body'][mane_idx]).max())}
    return r


PEN_REST = pen_sets(RESTV, fk(IDB))
''')
rep("        ps = pen_sets(V)\n        for k, v in ps.items():\n            extra = float(np.max(v - PEN_REST[k])) if len(v) else 0.\n            if extra > pen.get(k, (0, 0))[0]:\n                pen[k] = (extra, f)",
    "        ps = pen_sets(V, P)\n        for k, v in ps.items():\n            if v >= pen.get(k, (0, 0))[0]:\n                pen[k] = (v, f)")
rep("    cm['penetrationBeyondRest'] = {k: {'depth': round(v[0], 4), 'frame': v[1]} for k, v in pen.items()}",
    "    cm['penetration'] = {k: {'depth': round(v[0], 4), 'frame': v[1]} for k, v in pen.items()}")
rep("                   'Penetration = how much deeper than at rest a test point sits behind the nearest torso/leg/head surface.',",
    "                   'Penetration = depth of hand/forearm skin points inside posed torso cores (ellipsoids per Pelvis/Spine/Chest) and '\n                   'leg capsules (Thigh/Shin), snout points inside the torso cores, and mane points inside the head core. Cores sit '\n                   'slightly inside the real surfaces, so 0 = no pass-through. restPenetration lists the rest-pose values.',")
rep("CHECKS['restLowestZ'] = round(REST_ZMIN, 4)", "CHECKS['restLowestZ'] = round(REST_ZMIN, 4)\nCHECKS['restPenetration'] = {k: round(v, 4) for k, v in PEN_REST.items()}")
# ---- tighter preview framing
rep("    VIEWS = {'tq': (-35, 14.5, Vector((.6, -.6, 4.2))), 'front': (0, 13.0, Vector((0, -.6, 4.4))), 'side': (90, 14.0, Vector((0, -1.2, 4.2)))}",
    "    VIEWS = {'tq': (-35, 12.0, Vector((.5, -.8, 4.3))), 'front': (0, 11.5, Vector((0, -.8, 4.5))), 'side': (90, 12.0, Vector((0, -1.6, 4.3)))}")
open(p, 'w', encoding='utf-8').write(s)
print('anim patched')
