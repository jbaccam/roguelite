"""Fast shape loop (system Python, no Blender): build the sculpt, pose every
primitive rigidly with its bone into REF, project through the solved camera,
rasterise with OpenCV and score the silhouette against source/reference_mask.png.

    python hb_preview.py [voxel=0.07] [cloth=1]

A design aid only (rigid posing, no skin blending). Every delivered preview is a
Blender render of the skinned rig. Writes _work/fast*.png.
"""
import copy
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from hb_camera import RefCam            # noqa: E402
import hb_design as D                    # noqa: E402
import hb_pose as PO                     # noqa: E402
import hb_parts as FP                    # noqa: E402
from hb_sdf import mesh_prims          # noqa: E402

W, H = 1086, 1448
COLORS = {'skin': (120, 170, 66), 'shirt': (196, 172, 146), 'strap': (92, 72, 70), 'iron': (95, 90, 94),
          'sash': (120, 36, 46), 'trousers': (72, 66, 80), 'wood': (110, 66, 40), 'band': (80, 72, 76),
          'tooth': (225, 218, 196), 'eye': (255, 255, 255)}


def posed_prims(prims, sk, pose_m):
    out = []
    for p in prims:
        q = copy.copy(p)
        X = pose_m[p.bone] @ np.linalg.inv(sk.rest[p.bone])
        q.c = X[:3, :3] @ p.c + X[:3, 3]
        if hasattr(q, 'n') and getattr(q, 'kind', '') == 'planes':
            q.n = p.n @ X[:3, :3].T
        else:
            q.R = X[:3, :3] @ p.R
        out.append(q)
    return out


def tris(Q):
    Q = np.asarray(Q)
    return np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])


def blend_torso(V, sk, m):
    """Cloth on the trunk: blend LowerTorso -> UpperTorso by height (as the skin does)."""
    t = np.clip((V[:, 2] - 6.3) / 1.3, 0, 1)
    t = t * t * (3 - 2 * t)
    Xu = m['UpperTorso'] @ np.linalg.inv(sk.rest['UpperTorso'])
    Vu = V @ Xu[:3, :3].T + Xu[:3, 3]
    return V * (1 - t[:, None]) + Vu * t[:, None]


def build(h=0.07, cloth=True):
    t0 = time.time()
    sk = PO.Skeleton()
    m = sk.ref
    parts = {}
    body = posed_prims([p for p in D.body_prims()], sk, m)
    V, Q = mesh_prims(body, h)
    parts['skin'] = (V, tris(Q), 'skin')
    for side in ('Right', 'Left'):
        V, Q = mesh_prims(D.hand_prims(side, 'REF'), h * 0.6)
        parts['hand' + side] = (V, tris(Q), 'skin')
    ref = __import__('hb_grip').solve_reference()
    Hm = m['Hammer']
    for p in FP.hammer_parts(ref['s_left']):
        V = p.V @ Hm[:3, :3].T + Hm[:3, 3]
        F = np.array([f for f in p.F if len(f) == 4]) if all(len(f) == 4 for f in p.F) else None
        T = tris(p.F) if F is not None else np.array([tri for f in p.F for tri in
                                                       [(f[0], f[i], f[i + 1]) for i in range(1, len(f) - 1)]])
        parts[p.name] = (V, T, p.mat)
    if cloth:
        for p in FP.cloth_parts():
            V = blend_torso(p.V, sk, m) if p.section in ('Shirt', 'Gear') else p.V
            T = np.array([tri for f in p.F for tri in [(f[0], f[i], f[i + 1]) for i in range(1, len(f) - 1)]])
            parts[p.name] = (V, T, p.mat)
    for p in FP.face_parts():
        X = m[p.bone or 'Head'] @ np.linalg.inv(sk.rest[p.bone or 'Head'])
        V = p.V @ X[:3, :3].T + X[:3, 3]
        parts[p.name] = (V, tris(p.F), p.mat)
    print('built in %.1fs' % (time.time() - t0), {k: len(v[1]) for k, v in parts.items()})
    return parts


def rasterise(parts, cam, light=np.array([0.45, -0.35, 0.82])):
    light = light / np.linalg.norm(light)
    img = np.zeros((H, W, 3), np.uint8)
    img[:] = (60, 60, 60)
    mask = np.zeros((H, W), np.uint8)
    allt = []
    for name, (v, f, mat) in parts.items():
        uv, depth = cam.project(v)
        a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
        n = np.cross(b - a, c - a)
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        shade = 0.35 + 0.65 * np.clip(n @ light, 0, 1)
        col = np.array(COLORS.get(mat, (180, 180, 180)), float)
        allt.append((uv[f], depth[f].mean(1), shade[:, None] * col[None]))
    P = np.concatenate([a[0] for a in allt])
    Dp = np.concatenate([a[1] for a in allt])
    C = np.concatenate([a[2] for a in allt])
    order = np.argsort(-Dp)
    P = np.round(P[order] * 4).astype(np.int32)
    C = C[order].astype(np.uint8)
    for i in range(len(P)):
        cv2.fillConvexPoly(img, P[i], C[i].tolist(), lineType=cv2.LINE_8, shift=2)
    for i in range(0, len(P), 20000):
        cv2.fillPoly(mask, list(P[i:i + 20000]), 255, lineType=cv2.LINE_8, shift=2)
    return img, mask


def main():
    args = dict(a.split('=') for a in sys.argv[1:])
    h = float(args.get('voxel', 0.07))
    cam = RefCam()
    parts = build(h, cloth=args.get('cloth', '1') == '1')
    img, mask = rasterise(parts, cam)
    ref = cv2.imread(str(HERE / 'source' / 'boss-reference.png'))[:, :, ::-1]
    refm = cv2.imread(str(HERE / 'source' / 'reference_mask.png'), 0)
    a, b = mask > 127, refm > 127
    iou = (a & b).sum() / (a | b).sum()
    (HERE / '_work').mkdir(exist_ok=True)
    cv2.imwrite(str(HERE / '_work' / 'fast_mask.png'), mask)
    ov = (ref.astype(float) * 0.5 + img.astype(float) * 0.5).astype(np.uint8)
    e1 = cv2.morphologyEx(b.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    e2 = cv2.morphologyEx(a.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    ov[e1 > 0] = (0, 255, 0)
    ov[e2 > 0] = (255, 0, 255)
    out = np.concatenate([img, ov], 1)
    cv2.imwrite(str(HERE / '_work' / 'fast.png'), cv2.resize(out, (out.shape[1] // 2, out.shape[0] // 2),
                                                             interpolation=cv2.INTER_AREA)[:, :, ::-1])
    crops = {'hands': [(280, 800, 560, 1080), (760, 720, 1086, 1046)], 'head': [(400, 180, 680, 460)]}
    for k, boxes in crops.items():
        rows = []
        for (x0, y0, x1, y1) in boxes:
            a_ = img[y0:y1, x0:x1]
            b_ = ref[y0:y1, x0:x1]
            sc = 360 / (y1 - y0)
            row = np.concatenate([b_, a_], 1)
            rows.append(cv2.resize(row, (int(row.shape[1] * sc), 360), interpolation=cv2.INTER_AREA))
        wmax = max(r.shape[1] for r in rows)
        rows = [np.pad(r, ((0, 0), (0, wmax - r.shape[1]), (0, 0))) for r in rows]
        cv2.imwrite(str(HERE / '_work' / ('fast_%s.png' % k)), np.concatenate(rows, 0)[:, :, ::-1])
    def runs(m):
        xs = np.nonzero(m)[0]
        if not len(xs):
            return []
        out, st = [], xs[0]
        for a_, b_ in zip(xs[:-1], xs[1:]):
            if b_ > a_ + 6:
                out.append((int(st), int(a_)))
                st = b_
        out.append((int(st), int(xs[-1])))
        return out
    if args.get('rows', '1') == '1':
        for y in range(200, 1300, 30):
            print('y%4d ref %-40s ren %s' % (y, runs(b[y]), runs(a[y])))
    print('IoU %.4f' % iou)


if __name__ == '__main__':
    main()
