"""Fast numpy/PIL preview of the posed dragon from the reference camera.

System python. Builds every part from dragon_design (cached), skins it with
the same weights the Blender build uses, poses it (rest or ReferencePose),
rasterises flat-shaded triangles (painter's algorithm) and scores the
silhouette against source/reference_mask.png. For silhouette iteration only;
every deliverable image is a real Blender render.

    python fast_preview.py [pose=reference|rest] [h=0.14] [out=_work/fast]
"""
import pickle
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import dragon_camera as C
import dragon_design as D
import dragon_pose as PZ
import dragon_rig as RG

HERE = Path(__file__).resolve().parent
ARGS = dict(a.split('=', 1) for a in sys.argv[1:] if '=' in a)
POSE = ARGS.get('pose', 'reference')
H = float(ARGS.get('h', '0.14'))
OUT = HERE / ARGS.get('out', '_work/fast')
COLORS = {'skin': (170, 44, 40), 'skin_head': (175, 48, 42), 'jaw': (200, 150, 100), 'belly': (205, 150, 100),
          'fang': (225, 200, 160), 'mouth': (60, 20, 20), 'obsidian': (60, 46, 52), 'lava': (255, 150, 40),
          'eye': (255, 210, 90), 'wingbone': (160, 45, 40), 'membrane': (215, 100, 45)}


def part_weights(p, prims, n):
    w = p['weights']
    if isinstance(w, str):
        if w == '__prims__':
            W = D.ownership_weights(prims, p['V'])
            W = D.limit_weights(W, n)
            return W
        return {w: np.ones(n)}
    return w


def main():
    t0 = time.time()
    cache = HERE / '_work' / f'parts_h{H:.2f}.pkl'
    src_mtime = max((HERE / f).stat().st_mtime for f in ('dragon_design.py', 'dragon_rig.py', 'dragon_mesh.py'))
    if cache.exists() and cache.stat().st_mtime > src_mtime:
        parts, prims = pickle.loads(cache.read_bytes())
    else:
        parts, prims, _ = D.build_all(H)
        cache.write_bytes(pickle.dumps((parts, prims)))
    sk = RG.Skeleton()
    pose = PZ.reference_pose(sk) if POSE == 'reference' else {}
    tris = []
    for p in parts:
        V = np.asarray(p['V'], float)
        W = part_weights(p, prims, len(V))
        Vp = RG.skin_points(sk, pose, V, W) if pose else V
        T = D.M.polys_to_tris(p['F'])
        col = np.array(COLORS.get(p['mat'], (200, 0, 200)), float)
        tris.append((Vp, T, col, p['mat']))
    L = np.array([-0.35, -0.55, 0.75])
    L /= np.linalg.norm(L)
    polys = []
    for Vp, T, col, mat in tris:
        uv, zc = C.project(Vp)
        a, b, c = Vp[T[:, 0]], Vp[T[:, 1]], Vp[T[:, 2]]
        nrm = np.cross(b - a, c - a)
        nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
        view = (a + b + c) / 3 - C.P
        facing = np.einsum('ij,ij->i', nrm, view) < 0
        lam = np.clip(nrm @ L, 0, 1)
        shade = 0.35 + 0.65 * lam
        if mat in ('lava', 'eye'):
            shade = np.ones_like(shade) * 1.1
        depth = zc[T].mean(1)
        for i in range(len(T)):
            if not facing[i] and mat not in ('membrane',):
                continue
            polys.append((depth[i], uv[T[i]], tuple(int(min(255, v)) for v in col * shade[i])))
    polys.sort(key=lambda x: -x[0])
    img = Image.new('RGB', (C.W, C.H), (40, 40, 48))
    msk = Image.new('L', (C.W, C.H), 0)
    d = ImageDraw.Draw(img)
    dm = ImageDraw.Draw(msk)
    for _, q, col in polys:
        pts = [tuple(x) for x in q]
        d.polygon(pts, fill=col)
        dm.polygon(pts, fill=255)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(OUT) + '_render.png')
    msk.save(str(OUT) + '_mask.png')
    ref = np.asarray(Image.open(HERE / 'source' / 'reference_mask.png')) > 127
    ren = np.asarray(msk) > 127
    iou = (ref & ren).sum() / (ref | ren).sum()
    refimg = np.asarray(Image.open(HERE / 'source' / '4.webp').convert('RGB')).astype(float)
    ov = (refimg * 0.5 + np.asarray(img).astype(float) * 0.5).astype(np.uint8)
    e_ref = ref ^ np.roll(ref, 1, 0) | ref ^ np.roll(ref, 1, 1)
    e_ren = ren ^ np.roll(ren, 1, 0) | ren ^ np.roll(ren, 1, 1)
    ov[e_ref] = (0, 255, 255)
    ov[e_ren] = (255, 0, 255)
    Image.fromarray(ov).save(str(OUT) + '_overlay.png')
    print(f'IoU {iou:.4f}  missing {(ref & ~ren).sum()}  extra {(ren & ~ref).sum()}  polys {len(polys)}  {time.time() - t0:.1f}s')


if __name__ == '__main__':
    main()
