"""Compare a Reference_Match render with the supplied reference (system python).

    python compare_reference.py [render.png] [render_mask.png] [out_dir] [--tag T]

Defaults: previews/Reference_Match.png, previews/Reference_Match_mask.png, previews/.
Needs numpy, Pillow and OpenCV (cv2).

Writes:
  Comparison_SideBySide.png   reference | render
  Comparison_Overlay.png      50 % onion skin
  Comparison_Silhouette.png   reference mask edge (red) over render mask edge (cyan)
  Crop_<name>.png             zoomed crop pairs (reference left, render right)
  compare_report.json         silhouette IoU and per-material colour probes

Colour probes: each material is a region box (fractions of the frame, valid
because the render reproduces the reference framing) plus a colour rule that
isolates that material inside the box in BOTH images. The report prints mean
sRGB and the per-channel linear ratio reference/render; those ratios are what
the CALIBRATION table in build_pharaoh.py multiplies in.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
REF = HERE / 'source' / 'Pharaoh_Reference.webp'
REF_MASK = HERE / 'source' / 'reference_mask.png'

args = [a for a in sys.argv[1:] if not a.startswith('--')]
tag = ''
if '--tag' in sys.argv:
    tag = sys.argv[sys.argv.index('--tag') + 1]
    args = [a for a in args if a != tag]
RENDER = Path(args[0]) if len(args) > 0 else HERE / 'previews' / 'Reference_Match.png'
RMASK = Path(args[1]) if len(args) > 1 else HERE / 'previews' / 'Reference_Match_mask.png'
OUT = Path(args[2]) if len(args) > 2 else HERE / 'previews'
OUT.mkdir(parents=True, exist_ok=True)

ref = np.asarray(Image.open(REF).convert('RGB')).astype(np.float32)
ren = np.asarray(Image.open(RENDER).convert('RGB')).astype(np.float32)
H, W = ref.shape[:2]
assert ren.shape[:2] == (H, W), f'render must be {W}x{H}, got {ren.shape[1]}x{ren.shape[0]}'
mref = np.asarray(Image.open(REF_MASK).convert('L')) > 127
mren = np.asarray(Image.open(RMASK).convert('L')) > 127


def lin(a):
    a = a / 255.0
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


# ------------------------------------------------------------ silhouette IoU
inter = (mref & mren).sum()
union = (mref | mren).sum()
iou = float(inter) / float(union)
only_ref = mref & ~mren
only_ren = mren & ~mref

# ------------------------------------------------------------ colour probes
# (box as fractions x0, y0, x1, y1; rule on sRGB 0-255 arrays)
RULES = {
    'skin': lambda r, g, b: (abs(r - g) < 22) & (r - b > 15) & (r - b < 60) & (g - b > 10) & (r < 200) & (r > 55),
    'bone': lambda r, g, b: (abs(r - g) < 22) & (r - b > 15) & (r - b < 70) & (r > 60),
    'bandage': lambda r, g, b: (r > 150) & (r - b > 35) & (r - b < 95) & (r - g < 45) & (g - b > 20),
    'gold': lambda r, g, b: (r - b > 90) & (g - b > 45) & (r > 110),
    'blue': lambda r, g, b: (b > r + 25) & (b > g + 15),
    'brown': lambda r, g, b: (r - b > 60) & (r - g > 35) & (r < 190) & (g < 140),
    'gem': lambda r, g, b: (b > r + 40) & (g > r + 20),
}
PX = lambda x0, y0, x1, y1: (x0 / W, y0 / H, x1 / W, y1 / H)
PROBES = {
    'skin': [PX(470, 620, 575, 658), PX(630, 580, 720, 630), PX(300, 980, 420, 1045),
             PX(680, 940, 790, 1010), PX(500, 370, 600, 405), PX(90, 530, 240, 690),
             PX(820, 850, 1010, 1040), PX(700, 1260, 960, 1360)],
    'bone': [PX(480, 236, 625, 370)],
    'bandage': [PX(350, 480, 760, 680), PX(740, 380, 1000, 700), PX(280, 1020, 480, 1140),
                PX(650, 990, 880, 1150), PX(290, 880, 800, 1140)],
    'gold': [PX(340, 380, 790, 560), PX(390, 660, 720, 765), PX(120, 280, 240, 1340),
             PX(810, 660, 1030, 870), PX(280, 1125, 480, 1200), PX(670, 1120, 885, 1230)],
    'blue': [PX(350, 160, 760, 400), PX(380, 745, 800, 1020), PX(120, 280, 240, 1340),
             PX(810, 660, 1030, 870)],
    'brown': [PX(395, 688, 720, 738)],
    'gem': [PX(488, 678, 560, 750)],
}


def probe(img, mask, key):
    sel = []
    for x0, y0, x1, y1 in PROBES[key]:
        a, b, c, d = int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)
        p = img[b:d, a:c]
        m = mask[b:d, a:c]
        ok = RULES[key](p[..., 0], p[..., 1], p[..., 2]) & m
        sel.append(p[ok])
    px = np.concatenate(sel) if sel else np.zeros((0, 3))
    if len(px) < 150:
        return None
    return {'n': int(len(px)), 'srgb': [int(v) for v in px.mean(0).round()],
            'linear': [float(v) for v in lin(px).mean(0)]}


report = {'render': str(RENDER), 'silhouette_iou': round(iou, 4),
          'ref_only_px': int(only_ref.sum()), 'render_only_px': int(only_ren.sum()),
          'probes': {}}
print(f'SILHOUETTE IoU {iou:.4f}  (ref-only {only_ref.sum()} px, render-only {only_ren.sum()} px)')
print(f"{'material':9s} {'reference':>16s} {'render':>16s}   ratio(lin R,G,B)   worst%")
for key in PROBES:
    a = probe(ref, mref, key)
    b = probe(ren, mren, key)
    e = {'reference': a, 'render': b}
    if a and b:
        ratio = [a['linear'][i] / max(1e-6, b['linear'][i]) for i in range(3)]
        srgb_err = [abs(a['srgb'][i] - b['srgb'][i]) / max(1, a['srgb'][i]) * 100 for i in range(3)]
        e['ratio_linear'] = [round(v, 3) for v in ratio]
        e['srgb_err_pct'] = [round(v, 1) for v in srgb_err]
        e['worst_pct'] = round(max(srgb_err), 1)
        print(f"{key:9s} {str(a['srgb']):>16s} {str(b['srgb']):>16s}   "
              f"{e['ratio_linear']}   {e['worst_pct']}")
    else:
        print(f'{key:9s} insufficient pixels ref={bool(a)} render={bool(b)}')
    report['probes'][key] = e

# ------------------------------------------------------------ images
ref_im = Image.fromarray(ref.astype(np.uint8))
ren_im = Image.fromarray(ren.astype(np.uint8))


def label(im, text):
    d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype('arial.ttf', 26)
    except Exception:
        f = ImageFont.load_default()
    d.rectangle((0, 0, 20 + 15 * len(text), 40), fill=(20, 22, 28))
    d.text((10, 6), text, fill=(240, 240, 240), font=f)
    return im


sbs = Image.new('RGB', (W * 2 + 20, H), (20, 22, 28))
sbs.paste(label(ref_im.copy(), 'REFERENCE'), (0, 0))
sbs.paste(label(ren_im.copy(), 'BLENDER RENDER'), (W + 20, 0))
sbs.save(OUT / f'Comparison_SideBySide{tag}.png')
Image.blend(ref_im, ren_im, 0.5).save(OUT / f'Comparison_Overlay{tag}.png')

edge_ref = cv2.Canny(mref.astype(np.uint8) * 255, 50, 150) > 0
edge_ren = cv2.Canny(mren.astype(np.uint8) * 255, 50, 150) > 0
k = np.ones((3, 3), np.uint8)
edge_ref = cv2.dilate(edge_ref.astype(np.uint8), k) > 0
edge_ren = cv2.dilate(edge_ren.astype(np.uint8), k) > 0
sil = (0.35 * ren).astype(np.uint8)
sil[only_ref] = (sil[only_ref] * 0.5 + np.array([120, 0, 0])).astype(np.uint8)
sil[only_ren] = (sil[only_ren] * 0.5 + np.array([0, 90, 120])).astype(np.uint8)
sil[edge_ref] = (255, 60, 60)
sil[edge_ren] = (60, 230, 255)
Image.fromarray(sil).save(OUT / f'Comparison_Silhouette{tag}.png')

CROPS = {
    'Face_Uraeus': (440, 120, 660, 380),
    'Nemes_Collar': (330, 140, 790, 560),
    'Belt_Gem': (380, 640, 740, 780),
    'Kilt_Apron': (280, 740, 820, 1160),
    'Hand_Right_Grip': (50, 500, 340, 800),
    'Hand_Left': (780, 780, 1060, 1060),
    'Staff_Hook': (40, 30, 310, 310),
    'Staff_Foot': (120, 1160, 300, 1360),
    'Feet': (220, 1080, 980, 1380),
    'Torso': (230, 380, 800, 780),
    'Arm_Left': (700, 360, 1060, 1060),
}
for name, (x0, y0, x1, y1) in CROPS.items():
    a = ref_im.crop((x0, y0, x1, y1))
    b = ren_im.crop((x0, y0, x1, y1))
    s = min(3.0, 700.0 / max(x1 - x0, y1 - y0))
    sz = (int((x1 - x0) * s), int((y1 - y0) * s))
    a = a.resize(sz, Image.LANCZOS)
    b = b.resize(sz, Image.LANCZOS)
    c = Image.new('RGB', (sz[0] * 2 + 12, sz[1]), (20, 22, 28))
    c.paste(a, (0, 0))
    c.paste(b, (sz[0] + 12, 0))
    c.save(OUT / f'Crop_{name}{tag}.png')

(OUT / f'compare_report{tag}.json').write_text(json.dumps(report, indent=2))
