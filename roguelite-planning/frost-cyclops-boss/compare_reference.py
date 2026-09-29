"""Compare a Blender render of the posed rig against the reference. System Python.

    python compare_reference.py [render=previews/Reference_Match.png] [mask=_work/render_mask.png]
                                [out=previews] [tag=]

Writes (into `out`):
  Comparison_SideBySide.png   reference | render
  Comparison_Overlay.png      50% onion skin
  Comparison_Silhouette.png   reference edge (green) vs render edge (magenta) over the render
  Comparison_<Crop>.png       zoomed crops: Face, MantleL, MantleR, HandR, FistL, Club, Belt, Feet
  compare-report.json         silhouette IoU + per-material probe table (lit/mid/shadow and
                              mean-linear per-channel ratio reference/render)
The render mask is the alpha of a flat Workbench render with the ground hidden.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from measure_reference import PROBES, probe      # noqa: E402

CROPS = {
    'Face': (440, 170, 650, 390),
    'MantleR': (200, 210, 520, 580),
    'MantleL': (570, 200, 1000, 630),
    'HandR': (60, 590, 330, 930),
    'FistL': (790, 720, 1070, 1070),
    'Club': (30, 880, 370, 1320),
    'Belt': (300, 660, 820, 1110),
    'Feet': (280, 1100, 960, 1320),
}


def load_rgb(p):
    return np.array(Image.open(p).convert('RGB'))


def load_mask(p):
    im = Image.open(p)
    if im.mode == 'RGBA':
        a = np.array(im)[:, :, 3]
    else:
        a = np.array(im.convert('L'))
    return a > 127


def edge(m):
    m = m.astype(np.uint8)
    return cv2.morphologyEx(m, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0


def label(img, text):
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 8 * len(text) + 12, 20], fill=(20, 22, 28))
    d.text((6, 4), text, fill=(235, 235, 235))
    return img


def main():
    args = dict(a.split('=', 1) for a in sys.argv[1:])
    render_p = HERE / args.get('render', 'previews/Reference_Match.png')
    mask_p = HERE / args.get('mask', '_work/render_mask.png')
    out = HERE / args.get('out', 'previews')
    tag = args.get('tag', '')
    out.mkdir(parents=True, exist_ok=True)
    ref = load_rgb(HERE / 'source' / 'FrostCyclops_reference.webp')
    ren = load_rgb(render_p)
    assert ren.shape == ref.shape, (ren.shape, ref.shape)
    refm = load_mask(HERE / 'source' / 'reference_mask.png')
    renm = load_mask(mask_p)
    inter = (refm & renm).sum()
    union = (refm | renm).sum()
    iou = inter / union
    # side by side
    sbs = Image.new('RGB', (ref.shape[1] * 2 + 30, ref.shape[0] + 30), (20, 22, 28))
    sbs.paste(label(Image.fromarray(ref), 'REFERENCE'), (10, 20))
    sbs.paste(label(Image.fromarray(ren), 'BLENDER RENDER (posed rig)'), (ref.shape[1] + 20, 20))
    sbs.save(out / f'Comparison_SideBySide{tag}.png')
    ov = (ref.astype(float) * 0.5 + ren.astype(float) * 0.5).astype(np.uint8)
    Image.fromarray(ov).save(out / f'Comparison_Overlay{tag}.png')
    sil = ren.copy()
    sil = (sil.astype(float) * 0.75 + 255 * 0.25).astype(np.uint8)
    e1 = cv2.dilate(edge(refm).astype(np.uint8), np.ones((2, 2), np.uint8)) > 0
    e2 = cv2.dilate(edge(renm).astype(np.uint8), np.ones((2, 2), np.uint8)) > 0
    sil[e1] = (0, 200, 0)
    sil[e2] = (230, 0, 230)
    diff = np.zeros_like(ren)
    diff[refm & ~renm] = (0, 170, 255)      # reference only (missing in render)
    diff[renm & ~refm] = (255, 90, 0)       # render only (extra)
    diff[refm & renm] = (60, 60, 60)
    sil_img = np.concatenate([sil, diff], 1)
    Image.fromarray(sil_img).save(out / f'Comparison_Silhouette{tag}.png')
    # crops: reference | render | onion+edges
    for k, (x0, y0, x1, y1) in CROPS.items():
        a = ref[y0:y1, x0:x1]
        b = ren[y0:y1, x0:x1]
        c = ov[y0:y1, x0:x1].copy()
        c[e1[y0:y1, x0:x1]] = (0, 200, 0)
        c[e2[y0:y1, x0:x1]] = (230, 0, 230)
        row = np.concatenate([a, np.full((y1 - y0, 6, 3), 20, np.uint8), b,
                              np.full((y1 - y0, 6, 3), 20, np.uint8), c], 1)
        sc = 560 / (y1 - y0)
        img = Image.fromarray(row).resize((int(row.shape[1] * sc), 560), Image.LANCZOS)
        img.save(out / f'Comparison_{k}{tag}.png')
    # colour probes
    table = {}
    for key, (box, rule) in PROBES.items():
        pr = probe(ref, box, rule)
        pn = probe(ren, box, rule)
        e = {'reference': pr, 'render': pn}
        if pr and pn:
            e['ratio_ref_over_render'] = [round(pr['mean_linear'][i] / max(1e-6, pn['mean_linear'][i]), 3)
                                          for i in range(3)]
            e['worst_channel_pct'] = round(max(abs(1 - r) for r in e['ratio_ref_over_render']) * 100, 1)
        table[key] = e
    rep = {'render': str(render_p.relative_to(HERE)) if HERE in render_p.parents else str(render_p),
           'silhouette_iou': round(float(iou), 4), 'reference_px': int(refm.sum()), 'render_px': int(renm.sum()),
           'probes': table}
    (out / f'compare-report{tag}.json').write_text(json.dumps(rep, indent=1))
    print('IoU %.4f' % iou)
    for k, e in table.items():
        if 'ratio_ref_over_render' in e:
            print('  %-16s ref mid %-15s render mid %-15s ratio %s  worst %.1f%%' % (
                k, e['reference']['mid_srgb'], e['render']['mid_srgb'], e['ratio_ref_over_render'],
                e['worst_channel_pct']))
        else:
            print('  %-16s (no pixels in render)' % k)


if __name__ == '__main__':
    main()
