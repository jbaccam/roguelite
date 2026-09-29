"""Compare a Blender render of the posed Dragon rig against the reference.

System python (numpy + Pillow). Usage:
    python compare_reference.py [render.png] [render_mask.png] [--out=previews] [--quick]

Outputs (in --out, default previews/):
  Comparison_SideBySide.png   reference | render at identical framing
  Comparison_Overlay.png      50 % onion skin
  Comparison_Silhouette.png   reference mask edge (cyan) and render mask edge
                              (magenta) over the reference, IoU in the corner
  Crop_<part>.png             zoomed reference / render pairs (head, jaw, wings,
                              chest plates, feet, spikes and glow, tail spade)
  compare-report.json         IoU and per-material colour probes

Colour probes: each material is a box (fractions of the frame; the render
reproduces the reference framing) plus a colour rule that isolates that
material in both images independently, inside both figure masks. The ratio is
reference / render per channel in linear light; 0.92..1.08 is the target.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
REF = HERE / 'source' / '4.webp'
REF_MASK = HERE / 'source' / 'reference_mask.png'

args = [a for a in sys.argv[1:] if not a.startswith('--')]
flags = [a for a in sys.argv[1:] if a.startswith('--')]
RENDER = Path(args[0]) if len(args) > 0 else HERE / 'previews' / 'Reference_Match.png'
RMASK = Path(args[1]) if len(args) > 1 else HERE / '_work' / 'final_mask.png'
OUTDIR = HERE / 'previews'
for f in flags:
    if f.startswith('--out='):
        OUTDIR = Path(f.split('=', 1)[1])
        if not OUTDIR.is_absolute():
            OUTDIR = HERE / OUTDIR
QUICK = '--quick' in flags
OUTDIR.mkdir(parents=True, exist_ok=True)


def lin(a):
    a = a / 255.0
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def to_srgb(v):
    v = np.clip(v, 0, 1)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * v ** (1 / 2.4) - 0.055) * 255


ref = np.asarray(Image.open(REF).convert('RGB')).astype(np.float64)
ren = np.asarray(Image.open(RENDER).convert('RGB')).astype(np.float64)
H, W = ref.shape[:2]
assert ren.shape[:2] == (H, W), f'render must be {W}x{H}, got {ren.shape[1]}x{ren.shape[0]}'
mref = np.asarray(Image.open(REF_MASK).convert('L')) > 127
mren = np.asarray(Image.open(RMASK).convert('L')) > 127
inter = (mref & mren).sum()
union = (mref | mren).sum()
iou = inter / union
report = {'silhouette_iou': round(float(iou), 4), 'ref_pixels': int(mref.sum()), 'render_pixels': int(mren.sum()),
          'missing_px': int((mref & ~mren).sum()), 'extra_px': int((mren & ~mref).sum())}

try:
    FONT = ImageFont.truetype('arial.ttf', 22)
    SMALL = ImageFont.truetype('arial.ttf', 16)
except Exception:  # noqa: BLE001
    FONT = SMALL = ImageFont.load_default()


def edge(m):
    e = np.zeros_like(m)
    e[1:-1, 1:-1] = m[1:-1, 1:-1] & ~(m[:-2, 1:-1] & m[2:, 1:-1] & m[1:-1, :-2] & m[1:-1, 2:])
    t = e.copy()
    t[1:] |= e[:-1]
    t[:, 1:] |= e[:, :-1]
    return t


sil = (ref * 0.55).astype(np.uint8)
dm = mref & ~mren
de = mren & ~mref
sil[dm] = (sil[dm] * 0.4 + np.array([0, 110, 140])).clip(0, 255)
sil[de] = (sil[de] * 0.4 + np.array([150, 0, 110])).clip(0, 255)
sil[edge(mref)] = (0, 255, 255)
sil[edge(mren)] = (255, 0, 255)
im = Image.fromarray(sil)
d = ImageDraw.Draw(im)
d.rectangle((0, 0, 600, 64), fill=(0, 0, 0))
d.text((10, 6), f'silhouette IoU {iou:.4f}', fill=(255, 255, 255), font=FONT)
d.text((10, 36), 'cyan = reference   magenta = render   teal = missing   purple = extra', fill=(200, 200, 200), font=SMALL)
im.save(OUTDIR / 'Comparison_Silhouette.png')

# ------------------------------------------------------------- colour probes
# box = (x0, y0, x1, y1) as frame fractions; rule on sRGB 0..255 arrays.
REGIONS = {
    # keys match the generator's CALIBRATION table
    'skin_lit': ((0.45, 0.40, 0.60, 0.62),          # the near shoulder / upper arm, lit upper planes
                 lambda r, g, b: (r > 120) & (r > 2.2 * g) & (r > 2.2 * b)),
    'skin_shadow': ((0.17, 0.60, 0.29, 0.80),       # the far (right) front leg, mostly shade
                    lambda r, g, b: (r > 70) & (r < 170) & (r > 2.2 * g) & (r > 2.0 * b)),
    'skin_head': ((0.24, 0.17, 0.37, 0.31),         # brow, snout and cheek
                  lambda r, g, b: (r > 110) & (r > 2.0 * g) & (r > 1.9 * b)),
    'belly': ((0.28, 0.40, 0.46, 0.66),             # chest chevron plates
              lambda r, g, b: (r > 120) & (g > 0.52 * r) & (g < 0.85 * r) & (b < 0.72 * r)),
    'jaw': ((0.23, 0.29, 0.34, 0.36),               # beige lower jaw
            lambda r, g, b: (r > 120) & (g > 0.52 * r) & (b < 0.72 * r)),
    'membrane': ((0.62, 0.13, 0.90, 0.40),          # left wing membrane
                 lambda r, g, b: (r > 150) & (g > 0.28 * r) & (g < 0.62 * r) & (b < 0.36 * r)),
    'wingbone': ((0.56, 0.02, 0.84, 0.12),          # left wing leading bones
                 lambda r, g, b: (r > 90) & (r > 2.0 * g) & (r > 1.9 * b)),
    'obsidian': ((0.46, 0.80, 0.66, 0.93),          # near front foot claws
                 lambda r, g, b: (np.maximum(np.maximum(r, g), b) < 120) & (r >= b)),
    'obsidian_horn': ((0.27, 0.08, 0.49, 0.22),     # horns against the sky
                      lambda r, g, b: (np.maximum(np.maximum(r, g), b) < 125)),
    'tail_skin': ((0.66, 0.66, 0.90, 0.76),         # red tail top
                  lambda r, g, b: (r > 110) & (r > 2.0 * g) & (r > 1.9 * b)),
}
probes = {}
for key, ((x0, y0, x1, y1), rule) in REGIONS.items():
    sl = (slice(int(y0 * H), int(y1 * H)), slice(int(x0 * W), int(x1 * W)))
    entry = {}
    means = {}
    for tag, img, msk in (('reference', ref, mref), ('render', ren, mren)):
        box = img[sl].reshape(-1, 3)
        mb = msk[sl].reshape(-1)
        sel = rule(box[:, 0], box[:, 1], box[:, 2]) & mb
        if sel.sum() < 150:
            entry[tag] = None
            continue
        m_lin = lin(box[sel]).mean(axis=0)
        means[tag] = m_lin
        entry[tag] = {'pixels': int(sel.sum()), 'srgb_of_linear_mean': [int(round(v)) for v in to_srgb(m_lin)]}
    if len(means) == 2:
        entry['ratio_ref_over_render'] = [round(float(a / max(b, 1e-6)), 3) for a, b in zip(means['reference'], means['render'])]
        entry['worst_channel_pct'] = round(float(np.max(np.abs(np.array(entry['ratio_ref_over_render']) - 1)) * 100), 1)
    probes[key] = entry
report['colour_probes'] = probes
(OUTDIR / 'compare-report.json').write_text(json.dumps(report, indent=2))
print('IoU', report['silhouette_iou'], 'missing', report['missing_px'], 'extra', report['extra_px'])
for k, e in probes.items():
    r = e.get('reference')
    n = e.get('render')
    print(f"  {k:14s} ref {r['srgb_of_linear_mean'] if r else None}  render {n['srgb_of_linear_mean'] if n else None}"
          f"  ratio {e.get('ratio_ref_over_render')}  worst {e.get('worst_channel_pct')}%")
if QUICK:
    sys.exit(0)

sbs = Image.new('RGB', (W * 2 + 30, H + 70), (22, 24, 28))
sbs.paste(Image.fromarray(ref.astype(np.uint8)), (10, 60))
sbs.paste(Image.fromarray(ren.astype(np.uint8)), (W + 20, 60))
d = ImageDraw.Draw(sbs)
d.text((14, 18), 'REFERENCE (supplied image, unchanged)', fill=(230, 230, 230), font=FONT)
d.text((W + 24, 18), f'BLENDER RENDER of the posed Dragon_Rig   silhouette IoU {iou:.3f}', fill=(230, 230, 230), font=FONT)
sbs.save(OUTDIR / 'Comparison_SideBySide.png')
Image.fromarray((ref * 0.5 + ren * 0.5).astype(np.uint8)).save(OUTDIR / 'Comparison_Overlay.png')

CROPS = {
    'HeadHornsEye': (330, 60, 780, 380),
    'JawFangs': (340, 220, 560, 380),
    'WingLeft': (800, 0, 1510, 560),
    'WingRight': (20, 20, 480, 520),
    'ChestPlates': (380, 330, 800, 800),
    'FrontFeet': (140, 760, 1010, 950),
    'HindFoot': (940, 780, 1180, 910),
    'SpikesGlow': (560, 180, 1360, 760),
    'TailSpade': (1150, 560, 1510, 820),
}
for name, (x0, y0, x1, y1) in CROPS.items():
    a = Image.fromarray(ref[y0:y1, x0:x1].astype(np.uint8))
    b = Image.fromarray(ren[y0:y1, x0:x1].astype(np.uint8))
    s = min(2.0, 900 / (x1 - x0))
    a = a.resize((int((x1 - x0) * s), int((y1 - y0) * s)), Image.LANCZOS)
    b = b.resize(a.size, Image.LANCZOS)
    c = Image.new('RGB', (a.width * 2 + 30, a.height + 50), (22, 24, 28))
    c.paste(a, (10, 40))
    c.paste(b, (a.width + 20, 40))
    dd = ImageDraw.Draw(c)
    dd.text((12, 10), f'{name}: reference', fill=(230, 230, 230), font=SMALL)
    dd.text((a.width + 22, 10), 'render', fill=(230, 230, 230), font=SMALL)
    c.save(OUTDIR / f'Crop_{name}.png')
