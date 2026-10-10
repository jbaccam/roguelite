"""Tomb Warden clip solving (pure numpy): linear-blend skinning of the built
meshes, contact distances in bone rest space, and the solves that pin the
clips to the world: the coffin-fit search for the Emerge start pose, fist
ground contacts (FistSlam, Emerge, Death), chest contacts (Roar) and the
Death ground-rest solve.
"""
import math

import numpy as np

import tw_design as D
import tw_motion as M
import tw_sdf as S

FPS = 24
SIDES = D.SIDES


def xf(Mx, P):
    return P @ Mx[:3, :3].T + Mx[:3, 3]


class Skinner:
    def __init__(self, sk, sections):
        """sections: name -> (V_rest (n,3), idx (n,4) into sk.order, w (n,4))"""
        self.sk = sk
        self.sec = sections
        self.inv_rest = np.stack([np.linalg.inv(sk.rest[b]) for b in sk.order])

    def mats(self, W):
        return np.stack([W[b] for b in self.sk.order]) @ self.inv_rest

    def pose(self, W, names=None):
        Ms = self.mats(W)
        out = {}
        for name in (names or self.sec):
            V, idx, w = self.sec[name]
            acc = np.zeros_like(V)
            for k in range(idx.shape[1]):
                Mk = Ms[idx[:, k]]
                acc += w[:, k, None] * (np.einsum('nij,nj->ni', Mk[:, :3, :3], V) + Mk[:, :3, 3])
            out[name] = acc
        return out


class Ctx:
    def __init__(self, sk, skin, fields, fist_field, dominant):
        self.sk, self.skin = sk, skin
        self.f = fields
        self.ff = fist_field                       # (field, lo, h) of the canonical fist
        self.dom = dominant                        # body vertex -> dominant bone name
        self.head_prims = [p for p in D.body_prims() if p.bone == 'Head'] + \
                          [p for p in D.mask_prims() if p.op == 'union']
        self.forearm = {s: [p for p in D.body_prims() if p.bone == s + 'LowerArm'] for s in SIDES}
        self.forearm_idx = {s: np.where(dominant == s + 'LowerArm')[0] for s in SIDES}
        self.arm_idx = np.where(np.isin(dominant, [s + b for s in SIDES for b in ('Shoulder', 'UpperArm', 'LowerArm')]))[0]
        bp = D.body_prims()
        self.part_prims = {}
        for b in sorted({p.bone for p in bp}):
            if b in ('UpperTorso', 'LowerTorso'):
                continue
            self.part_prims[b] = [p for p in bp if p.bone == b]
        self.part_prims['Head'] = self.part_prims.get('Head', []) + [p for p in D.mask_prims() if p.op == 'union']

    def body_dist(self, Wm, P, side):
        """Signed distance of points P to every body part except `side`'s own
        arm, each part evaluated in its bone's rest space (exact for the rigid
        parts; the mesh was extracted from these same fields). Returns (d, part)."""
        own = {side + 'Shoulder', side + 'UpperArm', side + 'LowerArm', side + 'Hand'}
        best = np.full(len(P), 9.0)
        lab = np.full(len(P), '', dtype=object)
        for bone, mapz in (('UpperTorso', lambda z: z > 4.75), ('LowerTorso', lambda z: z <= 5.0)):
            q = self.to_rest(Wm, bone, P)
            ok = mapz(q[:, 2])
            d = np.where(ok, S.trilinear(self.f['core'], self.f['lo'], self.f['h'], q), 9.0)
            m = d < best
            best[m], lab[m] = d[m], bone
        for bone, prims in self.part_prims.items():
            if bone in own:
                continue
            d = S.eval_prims(prims, self.to_rest(Wm, bone, P))
            m = d < best
            best[m], lab[m] = d[m], bone
        other = 'Right' if side == 'Left' else 'Left'
        d = self.fist_dist(Wm, other, P)
        m = d < best
        best[m], lab[m] = d[m], other + 'Hand'
        return best, lab

    def to_rest(self, W, bone, P):
        return xf(self.sk.rest[bone] @ np.linalg.inv(W[bone]), P)

    def core_dist(self, W, P):
        q = self.to_rest(W, 'UpperTorso', P)
        return S.trilinear(self.f['core'], self.f['lo'], self.f['h'], q)

    def head_dist(self, W, P):
        return S.eval_prims(self.head_prims, self.to_rest(W, 'Head', P))

    def forearm_dist(self, W, side, P):
        return S.eval_prims(self.forearm[side], self.to_rest(W, side + 'LowerArm', P))

    def fist_dist(self, W, side, P):
        q = self.to_rest(W, side + 'Hand', P)
        R, o = D.fist_frame(side)
        loc = (q - o) @ R
        if side == 'Left':
            loc[:, 0] = -loc[:, 0]
        loc = loc / D.FIST_SCALE
        fld, lo, h = self.ff
        inside = np.all((loc > lo + h) & (loc < lo + h * (np.array(fld.shape) - 2)), axis=1)
        d = np.full(len(P), 1.0)
        if inside.any():
            d[inside] = S.trilinear(fld, lo, h, loc[inside])
        return d

    def fist_verts(self, W, side):
        return self.skin.pose(W, [side + 'Fist'])[side + 'Fist']

    def fist_minz(self, W):
        return min(float(self.fist_verts(W, s)[:, 2].min()) for s in SIDES)


# ----------------------------------------------------------------- simple clips
def idle_clip(sk):
    return {'frames': [M.idle_pose(sk, f / FPS) for f in range(M.IDLE_N + 1)], 'loop': True,
            'planted': [{'Left': 'ankle', 'Right': 'ankle'}] * (M.IDLE_N + 1)}


def walk_clip(sk):
    fr, pl = [], []
    for f in range(M.WALK_N + 1):
        B, p = M.walk_pose(sk, f / FPS)
        fr.append(B)
        pl.append(p)
    return {'frames': fr, 'loop': True, 'planted': pl, 'speed': M.WALK_STRIDE / M.WALK_T}


def hit_clip(sk):
    return {'frames': [M.hit_pose(sk, f / FPS) for f in range(M.HIT_N + 1)], 'loop': False,
            'planted': [{'Left': 'ankle', 'Right': 'ankle'}] * (M.HIT_N + 1)}


# -------------------------------------------------------------------- FistSlam
def slam_clip(ctx, log=print):
    """Both fists land with their lowest stone on the ground while the arms
    reach 96.5% (heavy-strike rule >= 95%): solve target depth and z together."""
    sk = ctx.sk
    z, gy = 0.0, -2.9
    tf = M.SLAM['impact'] / FPS
    for it in range(8):
        body, arms = M.slam_tracks(sk, ground_y=gy, impact_z=z)
        B, reach = M.slam_pose(sk, tf, body, arms)
        mz = ctx.fist_minz(sk.fk(B))
        r = min(reach.values())
        z -= mz
        gy -= (0.965 - r) * 4.0
        if abs(mz) < 1e-3 and abs(r - 0.965) < 2e-3:
            break
    body, arms = M.slam_tracks(sk, ground_y=gy, impact_z=z)
    log('slam impact target y/z', round(gy, 3), round(z, 4), 'fist min z', round(mz, 4),
        'reach', {k: round(v, 4) for k, v in reach.items()})
    fr, reaches = [], []
    for f in range(M.SLAM_N + 1):
        B, r = M.slam_pose(sk, f / FPS, body, arms)
        fr.append(B)
        reaches.append(r)
    return {'frames': fr, 'loop': False, 'planted': [{'Left': 'ankle', 'Right': 'ankle'}] * (M.SLAM_N + 1),
            'impact': M.SLAM['impact'], 'reach': reaches, 'impact_z': z, 'impact_y': gy}


# -------------------------------------------------------------------- FistHook
def hook_clip(ctx, log=print):
    sk = ctx.sk
    r_imp = 4.9
    for it in range(8):
        body, hook = M.hook_tracks(sk, r_imp=r_imp)
        B, r = M.hook_pose(sk, M.HOOK['impact'] / FPS, body, hook)
        r_imp += (0.96 - r) * 4.4
        if abs(r - 0.96) < 2e-3:
            break
    body, hook = M.hook_tracks(sk, r_imp=r_imp)
    log('hook impact radius', round(r_imp, 3))
    fr, reaches = [], []
    for f in range(M.HOOK_N + 1):
        B, r = M.hook_pose(sk, f / FPS, body, hook)
        fr.append(B)
        reaches.append(r)
    log('hook reach at impact', round(reaches[M.HOOK['impact']], 4))
    return {'frames': fr, 'loop': False, 'planted': [{'Left': 'ankle', 'Right': 'ankle'}] * (M.HOOK_N + 1),
            'impact': M.HOOK['impact'], 'reach': reaches}


# ------------------------------------------------------------------------ Roar
def roar_clip(ctx, log=print):
    """Fist centres pulled in along the chest normal until the stone just
    touches the chest (gap 0.035 in UpperTorso rest space)."""
    sk = ctx.sk
    s0 = {s: np.array([1.20 * D.sgn(s), -3.1, 5.85]) for s in SIDES}
    c0 = {s: np.array([0.90 * D.sgn(s), -0.62, 5.75]) for s in SIDES}
    lam = {s: 0.5 for s in SIDES}
    tf = M.ROAR['hit1'] / FPS
    for rnd in range(2):
        for side in SIDES:
            lo_, hi_ = 0.0, 1.0
            for it in range(18):
                mid = 0.5 * (lo_ + hi_)
                contact = {s: s0[s] + (c0[s] - s0[s]) * (mid if s == side else lam[s]) for s in SIDES}
                body, arms = M.roar_tracks(sk, contact)
                W = sk.fk(M.roar_pose(sk, tf, body, arms))
                d = float(ctx.core_dist(W, ctx.fist_verts(W, side)).min())
                if d > 0.035:
                    lo_ = mid
                else:
                    hi_ = mid
            lam[side] = lo_
    contact = {s: s0[s] + (c0[s] - s0[s]) * lam[s] for s in SIDES}
    body, arms = M.roar_tracks(sk, contact)
    fr = [M.roar_pose(sk, f / FPS, body, arms) for f in range(M.ROAR_N + 1)]
    gaps = {}
    for key in ('hit1', 'hit2'):
        W = sk.fk(fr[M.ROAR[key]])
        gaps[key] = {s: round(float(ctx.core_dist(W, ctx.fist_verts(W, s)).min()), 4) for s in SIDES}
    log('roar contact lambda', {k: round(v, 3) for k, v in lam.items()}, 'fist-chest gap', gaps)
    return {'frames': fr, 'loop': False, 'planted': [{'Left': 'ankle', 'Right': 'ankle'}] * (M.ROAR_N + 1),
            'contact': {s: contact[s].tolist() for s in SIDES}, 'gaps': gaps}


# ---------------------------------------------------------------------- Emerge
def coffin_eval(ctx, C, plant):
    sk = ctx.sk
    body, arms = M.emerge_controls(sk, C, plant)
    B, reach = M.emerge_pose(sk, 0.0, body, arms)
    W = sk.fk(B)
    V = ctx.skin.pose(W)
    allv = np.concatenate(list(V.values()))
    lo, hi = allv.min(0), allv.max(0)
    pen = {}
    for side in SIDES:
        # same all-parts distance as the delivery check (head, torso, legs, the other arm and fist)
        for key, pts in (('fist', V[side + 'Fist']), ('forearm', V['Body'][ctx.forearm_idx[side]])):
            d, lab = ctx.body_dist(W, pts, side)
            i = int(np.argmin(d))
            pen[f'{key}_{side}_vs_{lab[i]}'] = max(0.0, -float(d[i]))
    span = hi - lo
    cl = D.cavity_clearance(allv, inside_only=True)
    clear = float(cl.min())
    names = np.concatenate([[k] * len(v) for k, v in V.items()])
    worst = (names[int(np.argmin(cl))], np.round(allv[int(np.argmin(cl))], 2).tolist())
    over = max(0.0, 0.04 - clear)
    # arms folded high and tight: top fist at the opposite shoulder, bottom fist high on the opposite pec
    want = {C['top']: np.array([1.3, -1.5, 6.3]), C['bottom']: np.array([1.05, -1.5, 5.45])}
    near = 0.0
    M_ch = W['UpperTorso'] @ np.linalg.inv(sk.rest['UpperTorso'])
    for side in SIDES:
        other_sign = -D.sgn(side)
        target = want[side] * np.array([other_sign, 1, 1])
        near += float(np.linalg.norm(V[side + 'Fist'].mean(0) - xf(M_ch, target[None])[0]))
    # compact start pose: no self-penetration, then the smallest cavity it needs (depth weighs most)
    cost = sum(150.0 * max(0.0, p - (0.0 if k.startswith('forearm') else 0.02)) for k, p in pen.items()) + 10.0 * span[1] + 6.0 * span[0] + 0.4 * near
    return cost, {'pen': pen, 'extent': span.tolist(), 'lo': lo.tolist(), 'hi': hi.tolist(), 'near': near, 'cavityClearance': clear, 'cavityWorst': worst,
                  'reach': reach}


def coffin_params(x, hip_y=0.0):
    """Folded-arm mummy pose: the top (right) forearm crosses high with its fist
    at the left shoulder, the bottom (left) forearm crosses low with its fist
    at the right pec. x = [top xyz, bottom xyz, top pole xyz, bottom pole xyz, top twist, bottom twist]."""
    top, bot = 'Right', 'Left'
    st, sb = D.sgn(top), D.sgn(bot)
    return {'hip_y': hip_y, 'shp': ((x[16], min(x[17], 24.0)) if len(x) > 17 else (40.0, 10.0)), 'lt': -1.0, 'ut': (x[15] if len(x) > 15 else -4.0), 'head': max(10.0, x[14]) if len(x) > 14 else 18.0, 'head_yaw': -22.0, 'head_roll': -12.0, 'top': top, 'bottom': bot,
            'arms': {top: {'pt': np.array([-x[0] * st, x[1], x[2]]), 'pole': M.unit(np.array([x[6] * st, x[7], x[8]])),
                           'twist': x[12] * st},
                     bot: {'pt': np.array([-x[3] * sb, x[4], x[5]]), 'pole': M.unit(np.array([x[9] * sb, x[10], x[11]])),
                           'twist': x[13] * sb}}}


def search_coffin(ctx, plant, log=print):
    """Folded-arm coffin pose. Found by the scans logged in README (start grid + local refinement): a top fist
    at shoulder height is always pinched between the bowed head and the opposite deltoid unless the head is
    turned and slumped away from it; lower fists make the two arms collide. Locked configuration, then the
    pelvis (and feet) are centred in the cavity depth."""
    # shoulders rolled forward and up (the cavity tapers); scan the fist targets, then refine
    best = None
    for tx in (1.0, 1.3, 1.6):
        for tz in (6.6, 7.0):
            for bz in (4.9, 5.3):
                for pro, shr in ((55.0, 25.0), (70.0, 35.0)):
                    for bp in ((1.5, -0.3, -0.5), (0.4, 0.1, -0.9)):
                        x = [tx, -2.1, tz, 0.85, -1.95, bz, 1.2, 0.2, -0.45, *bp, -50.0, -40.0, 12.0, -6.0, pro, shr]
                        c, inf = coffin_eval(ctx, coffin_params(x), plant)
                        if best is None or c < best[0]:
                            best = (c, x)
    cur, x = best
    log('coffin start grid best', round(cur, 3), np.round(x, 2).tolist())
    steps = [0.15] * 6 + [0.25] * 6 + [10.0, 10.0, 2.0, 2.0, 5.0, 5.0]
    for rnd in range(10):
        improved = False
        for i in range(len(x)):
            if steps[i] == 0:
                continue
            for sg in (-1, 1):
                y = list(x)
                y[i] += sg * steps[i]
                c, inf = coffin_eval(ctx, coffin_params(y), plant)
                if c < cur - 1e-6:
                    cur, x, improved = c, y, True
        steps = [st_ * (0.7 if improved else 0.5) for st_ in steps]
    C = coffin_params(x)
    for it in range(3):
        c, info = coffin_eval(ctx, C, plant)
        cy = 0.5 * (info['lo'][1] + info['hi'][1])
        C['hip_y'] += D.COFFIN_START[1] - cy      # centre the depth on the cavity (front -2.25 .. back 2.25)
    c, info = coffin_eval(ctx, C, plant)
    log('coffin refined cost', round(c, 4), 'x', np.round(x, 3).tolist(), 'hip_y', round(C['hip_y'], 3),
        'pen', {k: round(v, 3) for k, v in info['pen'].items() if v > 0}, 'cavity clearance', round(info['cavityClearance'], 4), info['cavityWorst'], 'extent', np.round(info['extent'], 3),
        'lo', np.round(info['lo'], 3), 'hi', np.round(info['hi'], 3))
    C['search_x'] = [round(float(v), 4) for v in x]
    return C, info


def emerge_clip(ctx, log=print):
    sk = ctx.sk
    plant = {s: np.array([2.45 * D.sgn(s), -2.7, 0.9]) for s in SIDES}
    C, cinfo = search_coffin(ctx, plant, log)
    tf = M.EM['impact'] / FPS
    for it in range(4):
        body, arms = M.emerge_controls(sk, C, plant)
        B, reach = M.emerge_pose(sk, tf, body, arms)
        mz = ctx.fist_minz(sk.fk(B))
        for s in SIDES:
            plant[s][2] -= mz
        if abs(mz) < 1e-3:
            break
    # no fist corner below the ground on the way into the plant or during the hold
    for it in range(3):
        body, arms = M.emerge_controls(sk, C, plant)
        lows = [ctx.fist_minz(sk.fk(M.emerge_pose(sk, f / FPS, body, arms)[0])) for f in range(M.EM['impact'] - 3, M.EM['hold'] + 2)]
        dz = -min(lows)
        if dz < 1e-3:
            break
        for s_ in SIDES:
            plant[s_][2] += dz
    body, arms = M.emerge_controls(sk, C, plant)
    fr, pl, reaches = [], [], []
    for f in range(M.EMERGE_N + 1):
        B, r = M.emerge_pose(sk, f / FPS, body, arms)
        fr.append(B)
        reaches.append(r)
        pl.append(M.emerge_planted(sk, f / FPS, C['hip_y']))
    log('emerge plant z', round(plant['Left'][2], 4), 'reach at plant', {k: round(v, 3) for k, v in reaches[M.EM['impact']].items()},
        'max leg reach', {k: round(max(r[k] for r in reaches), 4) for k in ('legLeft', 'legRight')},
        'frames >0.999', [i for i, r in enumerate(reaches) if max(r['legLeft'], r['legRight']) > 0.999])
    return {'frames': fr, 'loop': False, 'planted': pl, 'impact': M.EM['impact'], 'coffin': C, 'coffin_info': cinfo,
            'plant': {s: plant[s].tolist() for s in SIDES}, 'reach': reaches}


# ----------------------------------------------------------------------- Death
def death_clip(ctx, log=print):
    sk = ctx.sk
    T = M.death_tracks()
    n = M.DEATH_N
    body_secs = ['Body', 'Cloth', 'Mask']
    keep = np.ones(len(ctx.skin.sec['Body'][0]), bool)
    keep[ctx.arm_idx] = False

    def lowest(P):
        W = sk.fk(P.B)
        V = ctx.skin.pose(W, body_secs)
        z = [V['Body'][keep][:, 2].min(), V['Cloth'][:, 2].min(), V['Mask'][:, 2].min()]
        return float(min(z))

    # pass 1: pelvis height so the body (not the arms) rests on the ground
    lift = np.zeros(n + 1)
    for f in range(n + 1):
        t = f / FPS
        for it in range(3):
            P = M.death_pose(sk, t, T, None, lift[f])
            z = lowest(P)
            need = -z if f >= 24 else max(0.0, -z - 0.02)
            if abs(need) < 1e-3 or (f < 24 and need <= 0):
                break
            lift[f] += need
    raw = lift.copy()
    sm = lift.copy()
    for f in range(1, n):
        sm[f] = (lift[f - 1] + 2 * lift[f] + lift[f + 1]) / 4
    lift = np.maximum(sm, raw - 0.02)
    lift[:3] = raw[:3]
    # plant points: fists land under the shoulders when he falls forward
    P = M.death_pose(sk, M.DEATH_PLANT / FPS, T, None, lift[M.DEATH_PLANT])
    W = P.W()
    plant = {}
    for s in SIDES:
        sh = W[s + 'UpperArm'][:3, 3]
        plant[s] = np.array([sh[0] + 0.25 * D.sgn(s), sh[1] - 0.95, 0.0])
    for it in range(3):
        arms = M.death_arm_keys(sk, plant)
        P = M.death_pose(sk, M.DEATH_PLANT / FPS, T, arms, lift[M.DEATH_PLANT])
        mz = ctx.fist_minz(P.W())
        for s in SIDES:
            plant[s][2] -= mz
    arms = M.death_arm_keys(sk, plant)
    fr = []
    for f in range(n + 1):
        for it in range(3):
            P = M.death_pose(sk, f / FPS, T, arms, lift[f])
            V = ctx.skin.pose(P.W())
            z = float(min(v[:, 2].min() for v in V.values()))
            if z >= -0.02:
                break
            lift[f] += -z
        fr.append(P.B)
    lows = []
    for f in range(n + 1):
        W = sk.fk(fr[f])
        V = ctx.skin.pose(W)
        lows.append(float(min(v[:, 2].min() for v in V.values())))
    log('death lift range', round(float(lift.min()), 3), round(float(lift.max()), 3), 'lowest any', round(min(lows), 4),
        'at', int(np.argmin(lows)))
    planted = [{'Left': 'ankle' if f <= 11 else None, 'Right': ('ankle' if (f <= 2 or 9 <= f <= 11) else None)}
               for f in range(n + 1)]
    return {'frames': fr, 'loop': False, 'planted': planted, 'lift': lift.tolist(), 'plant': {s: plant[s].tolist() for s in SIDES},
            'lowest': lows}
