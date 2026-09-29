"""Skin weights for the Frost Cyclops (pure numpy).

Body/hand skin: every sculpt primitive carries the bone that owns it. At each
final vertex we measure how strongly each primitive group owns the surface
(soft arg-min of the primitive distances), then split limb groups along their
bone chains with smooth blends at the joints, smooth the result over the mesh
graph, keep the 4 largest influences and normalise.

Accessories use explicit rules (rigid parts are 100% one bone; the fur and the
loincloth follow the nearest skin plus their own secondary bones).
"""
import numpy as np

import fc_design as D

MAX_INF = 4


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def chain_split(P, joints, blend):
    """Weights along a chain of points [j0, j1, ..., jn] (n segments).

    Returns (len(P), n) weights: each vertex projects onto the polyline; around
    each interior joint the two segments blend over +-blend studs."""
    n = len(joints) - 1
    W = np.zeros((len(P), n))
    # arc-length parameter of the closest point on the polyline
    best_d = np.full(len(P), np.inf)
    best_s = np.zeros(len(P))
    acc = 0.0
    starts = []
    for i in range(n):
        a, b = joints[i], joints[i + 1]
        ab = b - a
        L = np.linalg.norm(ab)
        t = np.clip(((P - a) @ ab) / (L * L), 0, 1)
        q = a + t[:, None] * ab
        d = np.linalg.norm(P - q, axis=1)
        m = d < best_d
        best_d[m] = d[m]
        best_s[m] = acc + t[m] * L
        starts.append(acc)
        acc += L
    starts.append(acc)
    for i in range(n):
        lo = starts[i]
        hi = starts[i + 1]
        w = np.ones(len(P))
        if i > 0:
            w *= _smoothstep(lo - blend[i - 1], lo + blend[i - 1], best_s)
        if i < n - 1:
            w *= 1 - _smoothstep(hi - blend[i], hi + blend[i], best_s)
        W[:, i] = w
    s = W.sum(1, keepdims=True)
    return W / np.maximum(s, 1e-9)


GROUP_OF = {}
for b in ('UpperTorso', 'LowerTorso', 'Belly'):
    GROUP_OF[b] = 'torso'
for b in ('Head', 'Jaw', 'Brow', 'Eye', 'EyelidUpper'):
    GROUP_OF[b] = 'head'
for side in ('Right', 'Left'):
    for b in ('UpperArm', 'LowerArm'):
        GROUP_OF[side + b] = 'arm' + side
    for b in ('UpperLeg', 'LowerLeg', 'Foot', 'Toes'):
        GROUP_OF[side + b] = 'leg' + side


def ownership(prims, P, tau=0.18):
    """Soft ownership per group: exp(-(d_i - d_min)/tau) summed per group."""
    groups = {}
    D_ = []
    tags = []
    for p in prims:
        if p.op != 'union':
            continue
        D_.append(p.sdf(P))
        tags.append(GROUP_OF.get(p.bone, 'torso') if p.tag != 'neck' else 'neck')
    D_ = np.array(D_)
    dmin = D_.min(0)
    E = np.exp(-(D_ - dmin) / tau)
    for g in set(tags):
        idx = [i for i, t in enumerate(tags) if t == g]
        groups[g] = E[idx].sum(0)
    tot = sum(groups.values())
    return {g: v / tot for g, v in groups.items()}


def body_weights(P, prims, pose_joints):
    """Weights for the continuous body skin (rest pose positions P)."""
    J = pose_joints
    own = ownership(prims, P)
    out = {}

    def add(bone, w):
        out[bone] = out.get(bone, 0) + w

    # torso: lower / upper by height, belly by distance from the belly centre
    z = P[:, 2]
    t_up = _smoothstep(6.3, 7.6, z)
    belly_c = J['Belly']
    rel = (P - belly_c) @ D.RT
    dist = np.sqrt((rel[:, 0] / 2.4) ** 2 + (rel[:, 2] / 1.8) ** 2)
    front = _smoothstep(0.2, -0.9, rel[:, 1])          # only the front of the gut
    w_belly = (1 - _smoothstep(0.35, 1.05, dist)) * front * 0.85
    tw = own.get('torso', 0)
    add('Belly', tw * w_belly)
    add('UpperTorso', tw * (1 - w_belly) * t_up)
    add('LowerTorso', tw * (1 - w_belly) * (1 - t_up))
    # neck: blend upper torso -> head
    nw = own.get('neck', 0)
    tn = _smoothstep(10.35, 11.0, z)
    add('Head', nw * tn)
    add('UpperTorso', nw * (1 - tn))
    # head: jaw / brow by their primitives
    hw = own.get('head', 0)
    hp = [p for p in prims if GROUP_OF.get(p.bone) == 'head' and p.op == 'union']
    Dh = np.array([p.sdf(P) for p in hp])
    Eh = np.exp(-(Dh - Dh.min(0)) / 0.06)
    Eh /= Eh.sum(0)
    for i, p in enumerate(hp):
        add(p.bone, hw * Eh[i])
    # arms and legs: chain splits
    for side in ('Right', 'Left'):
        aw = own.get('arm' + side, 0)
        ch = [J[side + 'UpperArm'], J[side + 'LowerArm'], J[side + 'Hand']]
        W = chain_split(P, ch, [0.42])
        add(side + 'UpperArm', aw * W[:, 0])
        add(side + 'LowerArm', aw * W[:, 1])
        lw = own.get('leg' + side, 0)
        toe_p = [p for p in prims if p.bone == side + 'Toes']
        dt = np.min([p.sdf(P) for p in toe_p], axis=0)
        toe_w = 1 - _smoothstep(-0.05, 0.12, dt)
        ch = [J[side + 'UpperLeg'], J[side + 'LowerLeg'], J[side + 'Foot'], J[side + 'Foot'] + D.FOOT_DIR[side] * 2.0]
        W = chain_split(P, ch, [0.40, 0.30])
        # the "segment" past the ankle is the foot itself
        foot = W[:, 2]
        add(side + 'UpperLeg', lw * W[:, 0])
        add(side + 'LowerLeg', lw * W[:, 1])
        add(side + 'Foot', lw * foot * (1 - toe_w))
        add(side + 'Toes', lw * foot * toe_w)
    return out


def hand_weights(P, prims, side, pose_joints):
    """Hand mesh: palm -> Hand, finger primitives -> finger bones, wrist blends
    into the forearm (the wrap hides the seam)."""
    out = {}
    un = [p for p in prims if p.op == 'union']
    Dm = np.array([p.sdf(P) for p in un])
    E = np.exp(-(Dm - Dm.min(0)) / 0.05)
    E /= E.sum(0)
    for i, p in enumerate(un):
        out[p.bone] = out.get(p.bone, 0) + E[i]
    # wrist: blend into the forearm above the wrist joint
    J = pose_joints
    W = J[side + 'Hand']
    fa = W - J[side + 'LowerArm']
    fa /= np.linalg.norm(fa)
    s = (P - W) @ fa                  # negative = up the forearm
    t = _smoothstep(-0.55, 0.15, s)
    hand = out.get(side + 'Hand', 0)
    out[side + 'Hand'] = hand * t
    out[side + 'LowerArm'] = out.get(side + 'LowerArm', 0) + hand * (1 - t)
    return out


def adjacency(F, n):
    """Vertex neighbour lists (as a sparse row/col pair) from polygon faces."""
    rows, cols = [], []
    for f in F:
        k = len(f)
        for i in range(k):
            a, b = f[i], f[(i + 1) % k]
            rows += [a, b]
            cols += [b, a]
    rows = np.array(rows)
    cols = np.array(cols)
    key = rows * n + cols
    key = np.unique(key)
    return key // n, key % n


def smooth(weights, adj, n, iters=4, lam=0.5, locked=None):
    rows, cols = adj
    deg = np.bincount(rows, minlength=n).astype(float)
    names = list(weights)
    M = np.stack([np.broadcast_to(np.asarray(weights[b], float), (n,)).copy() for b in names], 1)
    for _ in range(iters):
        acc = np.zeros_like(M)
        np.add.at(acc, rows, M[cols])
        avg = acc / np.maximum(deg, 1)[:, None]
        new = M + lam * (avg - M)
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
