"""Compare a Blender render of the posed King Crab rig against the reference.

System python (numpy + Pillow; OpenCV only for edge drawing). Usage:
    python compare_reference.py [render.png] [render_mask.png] [--out previews] [--quick]

Outputs (in --out, default previews/):
  Comparison_SideBySide.png   reference | render at identical framing
  Comparison_Overlay.png      50 % onion skin
  Comparison_Silhouette.png   reference mask edge (cyan) and render mask edge
                              (magenta) over the reference, IoU in the corner
  Crop_<part>.png             zoomed reference/render pairs for every region
                              judged on (eyes/brows, mouth, both claws, legs,
                              rim spikes)
  compare-report.json         IoU, per-material colour probes and ratios

Colour probes: each material is a box (fractions of the frame; the render
reproduces the reference framing) plus a colour rule that picks that material
out of whatever else shares the box, applied to both images independently.
The ratio is reference/render per channel in linear light; within 0.92..1.08
is the target (the "~8 % per channel" bar).
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
REF = HERE / 'source' / 'king-crab-reference.webp'
REF_MASK = HERE / 'source' / 'reference_mask.png'

args = [a for a in sys.argv[1:] if not a.startswith('--')]
flags = [a for a in sys.argv[1:] if a.startswith('--')]
RENDER = Path(args[0]) if len(args) > 0 else HERE / 'previews' / 'Reference_Match.png'
RMASK = Path(args[1]) if len(args) > 1 else HERE / '_work' / 'final_mask.png'
OUTDIR = HERE / 'previews'
for f in flags:
    if f.startswith('--out='):
        OUTDIR = Path(f.split('=', 1)[1])
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
# Region IoUs. Both claws were deliberately re-posed into an animation-ready
# guard on the user's instruction, so the silhouette is also scored with the
# claw regions (boxes in reference pixels) excluded from both masks.
CRUSHER_BOXES = [(0, 200, 525, 830)]
CUTTER_BOXES = [(1150, 400, 1536, 830)]   # also covers leg L2, which the cutter now hangs in front of


def box_mask(boxes):
    m = np.zeros_like(mref)
    for x0, y0, x1, y1 in boxes:
        m[y0:y1, x0:x1] = True
    return m


def iou_outside(boxes):
    keep = ~box_mask(boxes)
    a, b = mref & keep, mren & keep
    return round(float((a & b).sum() / max((a | b).sum(), 1)), 4)


report = {'silhouette_iou': round(float(iou), 4),
          'silhouette_iou_excluding_crusher': iou_outside(CRUSHER_BOXES),
          'silhouette_iou_excluding_both_claws': iou_outside(CRUSHER_BOXES + CUTTER_BOXES),
          'ref_pixels': int(mref.sum()), 'render_pixels': int(mren.sum()),
          'missing_px': int((mref & ~mren).sum()), 'extra_px': int((mren & ~mref).sum())}

try:
    FONT = ImageFont.truetype('arial.ttf', 22)
    SMALL = ImageFont.truetype('arial.ttf', 16)
except Exception:
    FONT = SMALL = ImageFont.load_default()


def edge(m):
    e = np.zeros_like(m)
    e[1:-1, 1:-1] = m[1:-1, 1:-1] & ~(m[:-2, 1:-1] & m[2:, 1:-1] & m[1:-1, :-2] & m[1:-1, 2:])
    # thicken
    t = e.copy()
    t[1:] |= e[:-1]
    t[:, 1:] |= e[:, :-1]
    return t


# silhouette overlay
sil = (ref * 0.55).astype(np.uint8)
diff_missing = mref & ~mren
diff_extra = mren & ~mref
sil[diff_missing] = (sil[diff_missing] * 0.4 + np.array([0, 110, 140])).clip(0, 255)
sil[diff_extra] = (sil[diff_extra] * 0.4 + np.array([150, 0, 110])).clip(0, 255)
sil[edge(mref)] = (0, 255, 255)
sil[edge(mren)] = (255, 0, 255)
im = Image.fromarray(sil)
d = ImageDraw.Draw(im)
d.rectangle((0, 0, 560, 64), fill=(0, 0, 0))
d.text((10, 6), f'silhouette IoU {iou:.4f}', fill=(255, 255, 255), font=FONT)
d.text((10, 36), 'cyan = reference   magenta = render   teal fill = missing   purple fill = extra',
       fill=(200, 200, 200), font=SMALL)
im.save(OUTDIR / 'Comparison_Silhouette.png')

# colour probes: box (x0, y0, x1, y1 as frame fractions) + rule on sRGB 0..255
REGIONS = {
    # keys match the generator's CALIBRATION table (material_section)
    # lit orange-red top of the carapace, left of the spikes
    'red_Body': ((0.28, 0.27, 0.46, 0.36),
                 lambda r, g, b: (r > 150) & (r > g * 1.6) & (g > b * 1.05)),
    # the big claw's shell (all red on its broad face)
    'red_ClawR': ((0.06, 0.30, 0.26, 0.72),
                  lambda r, g, b: (r > 90) & (r > g * 1.7) & (r > b * 1.7)),
    # the small claw's shell and hook
    'red_ClawL': ((0.80, 0.42, 0.96, 0.78),
                  lambda r, g, b: (r > 90) & (r > g * 1.7) & (r > b * 1.7)),
    # walking-leg shell (front legs; right edge stops short of the re-posed
    # cutter claw, which now hangs in front of the crab's front-left leg)
    'red_Legs': ((0.35, 0.57, 0.68, 0.74),
                 lambda r, g, b: (r > 90) & (r > g * 1.7) & (r > b * 1.7)),
    # beige mouth plates / teeth
    'beige_Body': ((0.48, 0.42, 0.62, 0.53),
                   lambda r, g, b: (r > 150) & (g > 110) & (r - b > 45) & (r - b < 120) & (r < g * 1.45)),
    # beige sternum plates
    'beige_Belly': ((0.42, 0.53, 0.62, 0.61),
                    lambda r, g, b: (r > 90) & (g > 60) & (r - b > 30) & (r < g * 1.5)),
    # the big claw's beige finger
    'beige_ClawR': ((0.23, 0.44, 0.34, 0.68),
                    lambda r, g, b: (r > 140) & (g > 100) & (r - b > 40) & (r < g * 1.5)),
    # the small claw's beige finger
    'beige_ClawL': ((0.81, 0.57, 0.91, 0.74),
                    lambda r, g, b: (r > 140) & (g > 100) & (r - b > 40) & (r < g * 1.5)),
    # leg tips (front-right and mid legs, outside the cutter's cast shadow)
    'beige_Legs': ((0.37, 0.70, 0.68, 0.82),
                   lambda r, g, b: (r > 120) & (g > 90) & (r - b > 35) & (r < g * 1.5)),
    # eye whites
    'eye': ((0.48, 0.31, 0.53, 0.38),
            lambda r, g, b: (r > 200) & (g > 190) & (b > 160)),
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
print(json.dumps(report, indent=1))

if QUICK:
    sys.exit(0)

# side by side
sbs = Image.new('RGB', (W * 2 + 30, H + 70), (22, 24, 28))
sbs.paste(Image.fromarray(ref.astype(np.uint8)), (10, 60))
sbs.paste(Image.fromarray(ren.astype(np.uint8)), (W + 20, 60))
d = ImageDraw.Draw(sbs)
d.text((14, 18), 'REFERENCE (supplied image, unchanged)', fill=(230, 230, 230), font=FONT)
d.text((W + 24, 18), f'BLENDER RENDER of the posed KingCrab_Rig   silhouette IoU {iou:.3f}', fill=(230, 230, 230), font=FONT)
sbs.save(OUTDIR / 'Comparison_SideBySide.png')

# onion skin
Image.fromarray((ref * 0.5 + ren * 0.5).astype(np.uint8)).save(OUTDIR / 'Comparison_Overlay.png')

# zoomed crops
CROPS = {
    'EyesBrows': (680, 240, 1010, 460),
    'Mouth': (600, 380, 1020, 640),
    'BigClaw': (50, 210, 560, 830),
    'SmallClaw': (1010, 400, 1480, 830),
    'LegsLeft': (450, 500, 960, 850),
    'LegsRight': (820, 520, 1260, 830),
    'RimSpikes': (410, 150, 1160, 420),
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
