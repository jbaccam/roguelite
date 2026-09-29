"""Fast shape loop (system Python): build the sculpt in the REFERENCE pose with
numpy only, project it through the solved camera, rasterise with OpenCV and
score the silhouette against source/reference_mask.png.

    python fc_preview.py [voxel=0.07] [out=_work/fast.png]

This is a design aid only. The deliverable previews are real Blender renders.
"""
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fc_camera import RefCam                           # noqa: E402
import fc_design as D                                   # noqa: E402
from fc_sdf import Grid, surface_nets                   # noqa: E402

W, H = 1086, 1448


def mesh_from_prims(prims, h, pad=0.3):
    lo = np.full(3, 1e9)
    hi = np.full(3, -1e9)
    for p in prims:
        if p.op != 'union':
            continue
        a, b = p.bounds()
        lo = np.minimum(lo, a)
        hi = np.maximum(hi, b)
    g = Grid(lo - pad, hi + pad, h)
    g.build(prims)
    v, q = surface_nets(g)
    tris = np.concatenate([q[:, [0, 1, 2]], q[:, [0, 2, 3]]])
    return v, tris


def build_reference_parts(h=0.07):
    parts = {}
    t = time.time()
    body = D.body_prims(rest=False)
    parts['skin'] = mesh_from_prims(body, h)
    for side in ('Right', 'Left'):
        parts['hand' + side] = mesh_from_prims(D.hand_prims(side, 'REF'), h * 0.6)
    try:
        import fc_parts as FP
        for name, (v, f, mat) in FP.all_parts_reference().items():
            parts[name] = (v, f)
            MATS[name] = mat
    except ImportError:
        pass
    print('built in %.1fs' % (time.time() - t), {k: len(v[1]) for k, v in parts.items()})
    return parts


MATS = {}
COLORS = {
    'skin': (150, 170, 205), 'handRight': (150, 170, 205), 'handLeft': (150, 170, 205),
    'stone': (170, 165, 165), 'wood': (120, 85, 65), 'strap': (95, 70, 60), 'leather': (110, 85, 75),
    'eye': (240, 245, 250), 'tooth': (235, 222, 205), 'lid': (140, 160, 195), 'fur': (230, 218, 200),
    'loin': (75, 65, 80), 'buckle': (150, 148, 150), 'default': (180, 180, 180),
}


def rasterise(parts, cam, colors=None, light=np.array([-0.45, -0.55, 0.70])):
    colors = colors or {}
    light = light / np.linalg.norm(light)
    img = np.zeros((H, W, 3), np.uint8)
    img[:] = (60, 60, 60)
    mask = np.zeros((H, W), np.uint8)
    allt = []
    for name, (v, f) in parts.items():
        uv, depth = cam.project(v)
        a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
        n = np.cross(b - a, c - a)
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        shade = 0.35 + 0.65 * np.clip(n @ light, 0, 1)
        col = np.array(colors.get(name, COLORS.get(name, COLORS.get(MATS.get(name, 'default'), (180, 180, 180)))), float)
        d = depth[f].mean(1)
        for i in range(len(f)):
            pass
        allt.append((uv[f], d, shade[:, None] * col[None]))
    P = np.concatenate([a[0] for a in allt])
    Dp = np.concatenate([a[1] for a in allt])
    C = np.concatenate([a[2] for a in allt])
    order = np.argsort(-Dp)
    P = np.round(P[order] * 4).astype(np.int32)     # 2 bits subpixel
    C = C[order].astype(np.uint8)
    for i in range(len(P)):
        cv2.fillConvexPoly(img, P[i], C[i].tolist(), lineType=cv2.LINE_8, shift=2)
    for i in range(0, len(P), 20000):
        cv2.fillPoly(mask, list(P[i:i + 20000]), 255, lineType=cv2.LINE_8, shift=2)
    return img, mask


def score(mask, ref_mask):
    a = mask > 127
    b = ref_mask > 127
    inter = (a & b).sum()
    union = (a | b).sum()
    return inter / union


def overlay(ref_rgb, img, mask, ref_mask):
    out = (ref_rgb.astype(float) * 0.5 + img.astype(float) * 0.5).astype(np.uint8)
    e1 = cv2.morphologyEx((ref_mask > 127).astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    e2 = cv2.morphologyEx((mask > 127).astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    out[e1 > 0] = (0, 255, 0)
    out[e2 > 0] = (255, 0, 255)
    return out


def main():
    args = dict(a.split('=') for a in sys.argv[1:])
    h = float(args.get('voxel', 0.07))
    out = HERE / args.get('out', '_work/fast.png')
    cam = RefCam()
    parts = build_reference_parts(h)
    img, mask = rasterise(parts, cam)
    ref = np.array(__import__('PIL.Image', fromlist=['Image']).open(HERE / 'source' / 'FrostCyclops_reference.webp').convert('RGB'))
    (HERE / '_work').mkdir(exist_ok=True)
    refm = cv2.imread(str(HERE / 'source' / 'reference_mask.png'), 0)
    iou = score(mask, refm)
    cv2.imwrite(str(out.parent / 'fast_mask.png'), mask)
    ov = overlay(ref, img, mask, refm)
    cv2.imwrite(str(out), np.concatenate([img, ov], 1)[:, :, ::-1])
    crops = {'head': (430, 170, 660, 400), 'handR': (40, 580, 360, 1000), 'fistL': (780, 700, 1070, 1070),
             'club': (30, 850, 380, 1320), 'feet': (280, 1080, 960, 1320)}
    for k, (x0, y0, x1, y1) in crops.items():
        a = img[y0:y1, x0:x1]
        b = ref[y0:y1, x0:x1]
        c = ov[y0:y1, x0:x1]
        sc = 600 / (y1 - y0)
        tri = np.concatenate([b, a, c], 1)
        tri = cv2.resize(tri, (int(tri.shape[1] * sc), 600), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(out.parent / f'fast_{k}.png'), tri[:, :, ::-1])
    # landmark check
    for k, (p, target) in D.design_landmarks().items():
        uv, _ = cam.project(p)
        print(f'  {k:14s} proj=({uv[0,0]:6.1f},{uv[0,1]:6.1f}) target={target} err=({uv[0,0]-target[0]:+5.1f},{uv[0,1]-target[1]:+5.1f})')
    print('IoU %.4f' % iou)


if __name__ == '__main__':
    main()
