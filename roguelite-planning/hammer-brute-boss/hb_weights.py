"""Skin weights for the Hammer Brute (pure numpy).

Skin (body + head + hands, one connected mesh): every sculpt primitive carries
the bone that owns it. At each vertex the soft arg-min of the primitive
distances gives group ownership (torso, neck, head, arms, hands, legs); limb
groups are split along their bone chains with smooth blends at the joints (the
forearm is spread over LowerArm and LowerArmTwist with a wide blend so wrist
roll twists the whole forearm instead of pinching the wrist); the result is
smoothed over the mesh graph, cut to 4 influences and normalised.

Accessories use explicit rules: the shirt, straps, sash and trousers take the
weights of the nearest skin (projected onto the body) plus their own bones
(Shirt_* on the hem); buckles and teeth are rigid; the hammer is 100% Hammer.
"""
import numpy as np

import hb_design as D

MAX_INF = 4


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def chain_split(P, joints, blend):
    """(len(P), n) weights along a polyline of joints with +-blend at interior joints."""
    n = len(joints) - 1
    best_d = np.full(len(P), np.inf)
    best_s = np.zeros(len(P))
    acc = 0.0
    starts = []
    for i in range(n):
        a, b = joints[i], joints[i + 1]
        ab = b - a
        L = np.linalg.norm(ab)
        t = np.clip(((P - a) @ ab) / (L * L), 0, 1)
        d = np.linalg.norm(P - (a + t[:, None] * ab), axis=1)
        m = d < best_d
        best_d[m] = d[m]
        best_s[m] = acc + t[m] * L
        starts.append(acc)
        acc += L
    starts.append(acc)
    W = np.zeros((len(P), n))
    for i in range(n):
        w = np.ones(len(P))
        if i > 0:
            w *= _smoothstep(starts[i] - blend[i - 1], starts[i] + blend[i - 1], best_s)
        if i < n - 1:
            w *= 1 - _smoothstep(starts[i + 1] - blend[i], starts[i + 1] + blend[i], best_s)
        W[:, i] = w
    return W / np.maximum(W.sum(1, keepdims=True), 1e-9)


GROUP_OF = {}
for b in ('UpperTorso', 'LowerTorso', 'Belly'):
    GROUP_OF[b] = 'torso'
for b in ('Head', 'Jaw', 'Brow', 'EyelidUpper'):
    GROUP_OF[b] = 'head'
for _s in ('Right', 'Left'):
    for b in ('UpperArm', 'LowerArm', 'LowerArmTwist'):
        GROUP_OF[_s + b] = 'arm' + _s
    GROUP_OF[_s + 'Hand'] = 'hand' + _s
    for nm in D.FINGER_NAMES + ['Thumb']:
        for k in (1, 2, 3):
            GROUP_OF[f'{_s}{nm}{k}'] = 'hand' + _s
    for b in ('UpperLeg', 'LowerLeg', 'Foot', 'Toes'):
        GROUP_OF[_s + b] = 'leg' + _s


def ownership(prims, P, tau=0.16):
    groups = {}
    Dl, tags = [], []
    for p in prims:
        if p.op != 'union':
            continue
        Dl.append(p.sdf(P))
        tags.append('neck' if p.tag == 'neck' else GROUP_OF.get(p.bone, 'torso'))
    Dm = np.array(Dl)
    E = np.exp(-(Dm - Dm.min(0)) / tau)
    for g in set(tags):
        idx = [i for i, t in enumerate(tags) if t == g]
        groups[g] = E[idx].sum(0)
    tot = sum(groups.values())
    return {g: v / tot for g, v in groups.items()}


def skin_weights(P, prims, hand_prims):
    """REST skin vertices P -> {bone: weights}. `prims` = body prims (no hands),
    `hand_prims` = {side: hand prims in REST}."""
    allp = list(prims) + hand_prims['Right'] + hand_prims['Left']
    own = ownership(allp, P)
    J = D.J
    out = {}

    def add(bone, w):
        out[bone] = out.get(bone, 0) + w
    z = P[:, 2]
    # trunk: lower/upper by height; the belly bone owns the front of the gut
    tw = own.get('torso', 0)
    t_up = _smoothstep(6.4, 7.9, z)
    rel = P - J['Belly']
    dist = np.sqrt((rel[:, 0] / 2.9) ** 2 + (rel[:, 2] / 1.9) ** 2)
    front = _smoothstep(0.0, -1.2, rel[:, 1])
    w_belly = (1 - _smoothstep(0.35, 1.05, dist)) * front * 0.9
    add('Belly', tw * w_belly)
    add('UpperTorso', tw * (1 - w_belly) * t_up)
    add('LowerTorso', tw * (1 - w_belly) * (1 - t_up))
    # neck: upper torso -> head
    nw = own.get('neck', 0)
    tn = _smoothstep(10.75, 11.45, z)
    add('Head', nw * tn)
    add('UpperTorso', nw * (1 - tn))
    # head: jaw / brow / lid by their primitives
    hw = own.get('head', 0)
    hp = [p for p in prims if GROUP_OF.get(p.bone) == 'head' and p.op == 'union']
    Dh = np.array([p.sdf(P) for p in hp])
    Eh = np.exp(-(Dh - Dh.min(0)) / 0.06)
    Eh /= Eh.sum(0)
    hb = {}
    for i, p in enumerate(hp):
        hb[p.bone] = hb.get(p.bone, 0) + Eh[i]
    # upper eyelid: the skin over the top of each socket
    lid = np.zeros(len(P))
    for s in (-1, 1):
        c = D.Hd(s * 0.45, -1.10, 0.10)
        q = (P - c) / np.array([0.34, 0.30, 0.22])
        lid = np.maximum(lid, (1 - _smoothstep(0.55, 1.0, np.linalg.norm(q, axis=1))) * _smoothstep(-0.02, 0.10, P[:, 2] - c[2] + 0.05))
    head_rest = sum(hb.values())
    for b, w in hb.items():
        add(b, hw * w * (1 - lid * 0.85))
    add('EyelidUpper', hw * lid * 0.85 * head_rest)
    # arms: shoulder -> elbow -> twist joint -> wrist
    for side in ('Right', 'Left'):
        aw = own.get('arm' + side, 0)
        S, E, Tw, Wr, hinge = D.rest_arm(side)
        Wc = chain_split(P, [S, E, Tw, Wr], [0.50, 0.95])
        add(side + 'UpperArm', aw * Wc[:, 0])
        add(side + 'LowerArm', aw * Wc[:, 1])
        add(side + 'LowerArmTwist', aw * Wc[:, 2])
        # hands: digit primitives own the fingers; the wrist blends into the twist bone
        hwg = own.get('hand' + side, 0)
        hpr = [p for p in hand_prims[side] if p.op == 'union']
        Dm = np.array([p.sdf(P) for p in hpr])
        Em = np.exp(-(Dm - Dm.min(0)) / 0.045)
        Em /= Em.sum(0)
        hbones = {}
        for i, p in enumerate(hpr):
            hbones[p.bone] = hbones.get(p.bone, 0) + Em[i]
        fa = (Wr - Tw) / np.linalg.norm(Wr - Tw)
        s_ = (P - Wr) @ fa
        t = _smoothstep(-0.70, 0.25, s_)
        hand = hbones.pop(side + 'Hand', 0)
        add(side + 'Hand', hwg * hand * t)
        add(side + 'LowerArmTwist', hwg * hand * (1 - t))
        for b, w in hbones.items():
            add(b, hwg * w)
        # legs: hip -> knee -> ankle -> foot
        lw = own.get('leg' + side, 0)
        fd = D.foot_dir(side)
        A = J[side + 'Foot']
        Wl = chain_split(P, [J[side + 'UpperLeg'], J[side + 'LowerLeg'], A, A + fd * 2.2], [0.45, 0.32])
        toes = (P - A) @ fd
        tt = _smoothstep(D.FOOT['front'] - D.FOOT['ball'] - 0.25, D.FOOT['front'] - D.FOOT['ball'] + 0.25, toes)
        foot = Wl[:, 2]
        add(side + 'UpperLeg', lw * Wl[:, 0])
        add(side + 'LowerLeg', lw * Wl[:, 1])
        add(side + 'Foot', lw * foot * (1 - tt))
        add(side + 'Toes', lw * foot * tt)
    return out


def adjacency(F, n):
    rows, cols = [], []
    for f in F:
        k = len(f)
        for i in range(k):
            a, b = f[i], f[(i + 1) % k]
            rows += [a, b]
            cols += [b, a]
    key = np.unique(np.array(rows, np.int64) * n + np.array(cols, np.int64))
    return key // n, key % n


def smooth(weights, adj, n, iters=4, lam=0.5, locked=None):
    rows, cols = adj
    deg = np.bincount(rows, minlength=n).astype(float)
    names = list(weights)
    M = np.stack([np.broadcast_to(np.asarray(weights[b], float), (n,)).copy() for b in names], 1)
    for _ in range(iters):
        acc = np.zeros_like(M)
        np.add.at(acc, rows, M[cols])
        new = M + lam * (acc / np.maximum(deg, 1)[:, None] - M)
        if locked is not None:
            new[locked] = M[locked]
        M = new
    return {b: M[:, i] for i, b in enumerate(names)}


def finalize(weights, n, max_inf=MAX_INF, floor=0.01):
    names = list(weights)
    M = np.stack([np.broadcast_to(np.asarray(weights[b], float), (n,)) for b in names], 1).copy()
    M[M < floor] = 0
    if M.shape[1] > max_inf:
        idx = np.argsort(-M, axis=1)[:, max_inf:]
        np.put_along_axis(M, idx, 0.0, axis=1)
    s = M.sum(1, keepdims=True)
    bad = s[:, 0] <= 1e-9
    M = M / np.maximum(s, 1e-9)
    return names, M, bad


# ============================================================ accessories
def nearest_skin(V, prims, hand_prims, surface_prims=None, max_iter=6):
    """Weights of the skin under each accessory vertex (projected onto the body)."""
    from hb_sdf import eval_prims, project_to_surface
    sp = surface_prims if surface_prims is not None else prims
    fn = lambda P: eval_prims(sp, P)
    Pn = project_to_surface(fn, V, offset=0.0, iters=max_iter)
    return skin_weights(Pn, prims, hand_prims)


def shirt_weights(V, prims, hand_prims):
    import hb_parts as FP
    W = nearest_skin(V, prims, hand_prims, surface_prims=[p for p in D.torso_prims() if p.op == 'union'])
    th = FP._cyl(V)
    above = V[:, 2] - FP.shirt_hem_z(th)
    front = 1 - _smoothstep(45, 75, np.abs(th))
    back = _smoothstep(110, 140, np.abs(th))
    f2 = (1 - _smoothstep(0.05, 0.55, above)) * front
    f1 = _smoothstep(0.05, 0.55, above) * (1 - _smoothstep(0.65, 1.25, above)) * front
    bk = (1 - _smoothstep(0.1, 1.0, above)) * back
    share = np.clip(f1 + f2 + bk, 0, 0.85)
    tot = np.maximum(f1 + f2 + bk, 1e-9)
    out = {b: w * (1 - share) for b, w in W.items()}
    out['Shirt_Front_1'] = share * f1 / tot
    out['Shirt_Front_2'] = share * f2 / tot
    out['Shirt_Back'] = share * bk / tot
    return out


def keep_only(W, allowed):
    return {b: w for b, w in W.items() if b in allowed or any(b.endswith(a) for a in allowed)}


LEG_TORSO = ('LowerTorso', 'UpperLeg', 'LowerLeg', 'Foot')


def trousers_weights(V, prims, hand_prims):
    import hb_parts as FP
    W = nearest_skin(V, prims, hand_prims, surface_prims=FP.soft_legs())
    for b in ('Belly', 'UpperTorso'):
        W['LowerTorso'] = W.get('LowerTorso', 0) + W.pop(b, 0)
    W = keep_only(W, LEG_TORSO)
    tot = sum(W.values())
    W['LowerTorso'] = W['LowerTorso'] + np.where(tot < 0.05, 1.0, 0.0)
    return W


def sash_weights(V, prims, hand_prims, tail=False):
    import hb_parts as FP
    if tail:
        lt = _smoothstep(4.9, 3.6, V[:, 2]) * 0.55
        return {'LowerTorso': 1 - lt, 'LeftUpperLeg': lt}
    W = nearest_skin(V, prims, hand_prims, surface_prims=FP.soft_waist())
    b = W.pop('Belly', 0)
    W['LowerTorso'] = W.get('LowerTorso', 0) + b
    return keep_only(W, LEG_TORSO + ('UpperTorso',))


def eye_weights(V):
    lid = np.zeros(len(V))
    import hb_parts as FP
    for c in FP.eye_centres():
        q = V - c
        lid = np.maximum(lid, _smoothstep(-0.01, 0.06, q[:, 2]) * (np.linalg.norm(q, axis=1) < 0.4))
    return {'Head': 1 - lid, 'EyelidUpper': lid}
