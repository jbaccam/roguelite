"""Compare a Blender render of the posed rig against the reference. System Python.

    python compare_reference.py [render=previews/Reference_Match.png] [mask=_work/render_mask.png]
                                [out=previews] [diag=_work/cmp] [tag=]

Writes:
  <out>/Comparison_SideBySide<tag>.png   reference | render (the delivered comparison)
  <diag>/Comparison_Silhouette.png       reference edge (green) vs render edge (magenta) + a diff
                                         (diagnostics only, not a delivered preview)
  <diag>/compare-report.json             silhouette IoU + per-region colour table
The render mask is the alpha of a flat Workbench render with the ground hidden.

Colour rule: each probe is a region box plus a colour rule (measure_reference.PROBES),
applied to both images; the mid band (45-55th luminance percentile) and the
mean-linear per-channel ratio reference/render are compared. Never single pixels.
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


def load_rgb(p):
    return np.array(Image.open(p).convert('RGB'))


def load_mask(p):
    im = Image.open(p)
    a = np.array(im)[:, :, 3] if im.mode == 'RGBA' else np.array(im.convert('L'))
    return a > 127


def edge(m):
    return cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0


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
    diag = HERE / args.get('diag', '_work/cmp')
    tag = args.get('tag', '')
    out.mkdir(parents=True, exist_ok=True)
    diag.mkdir(parents=True, exist_ok=True)
    ref = load_rgb(HERE / 'source' / 'boss-reference.png')
    ren = load_rgb(render_p)
    assert ren.shape == ref.shape, (ren.shape, ref.shape)
    refm = load_mask(HERE / 'source' / 'reference_mask.png')
    renm = load_mask(mask_p)
    iou = (refm & renm).sum() / (refm | renm).sum()
    sbs = Image.new('RGB', (ref.shape[1] * 2 + 30, ref.shape[0] + 30), (20, 22, 28))
    sbs.paste(label(Image.fromarray(ref), 'REFERENCE'), (10, 20))
    sbs.paste(label(Image.fromarray(ren), 'BLENDER RENDER (posed rig, IoU %.3f)' % iou), (ref.shape[1] + 20, 20))
    sbs.save(out / f'Comparison_SideBySide{tag}.png')
    sil = (ren.astype(float) * 0.75 + 255 * 0.25).astype(np.uint8)
    e1 = cv2.dilate(edge(refm).astype(np.uint8), np.ones((2, 2), np.uint8)) > 0
    e2 = cv2.dilate(edge(renm).astype(np.uint8), np.ones((2, 2), np.uint8)) > 0
    sil[e1] = (0, 200, 0)
    sil[e2] = (230, 0, 230)
    diff = np.zeros_like(ren)
    diff[refm & ~renm] = (0, 170, 255)
    diff[renm & ~refm] = (255, 90, 0)
    diff[refm & renm] = (60, 60, 60)
    Image.fromarray(np.concatenate([sil, diff], 1)).resize((ref.shape[1], ref.shape[0] // 2)).save(
        diag / 'Comparison_Silhouette.png')
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
    rep = {'render': str(render_p.name), 'silhouette_iou': round(float(iou), 4), 'reference_px': int(refm.sum()),
           'render_px': int(renm.sum()), 'reference_only_px': int((refm & ~renm).sum()),
           'render_only_px': int((renm & ~refm).sum()), 'probes': table}
    (diag / 'compare-report.json').write_text(json.dumps(rep, indent=1))
    print('IoU %.4f' % iou)
    for k, e in table.items():
        if 'ratio_ref_over_render' in e:
            print('  %-16s ref mid %-15s render mid %-15s ratio %s  worst %.1f%%' % (
                k, e['reference']['mid_srgb'], e['render']['mid_srgb'], e['ratio_ref_over_render'],
                e['worst_channel_pct']))
        else:
            print('  %-16s (no pixels in %s)' % (k, 'render' if e['reference'] else 'reference'))


if __name__ == '__main__':
    main()
