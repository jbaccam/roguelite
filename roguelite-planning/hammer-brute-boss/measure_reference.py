"""Measure the Hammer Brute reference. System Python (Pillow, numpy, OpenCV).

    python measure_reference.py

Writes, all derived from source/boss-reference.png (never modified):
  source/reference_mask.png          figure silhouette (255 = figure, hammer included)
  source/reference_measurements.json landmarks, silhouette spans, colour probes
  _work/Reference_Landmarks.png      landmarks + probe boxes drawn on the reference (diagnostic)

How the mask is made (documented in source/REFERENCE_NOTES.md): OpenCV GrabCut,
initialised with a rectangle around the figure plus hand-placed seeds. The skin
is green on a green lawn, so the seeds matter: definite-foreground strokes run
down the body, limbs, feet, hammer and haft; definite-background bands cover the
open lawn below and between the feet, the sky and the far cliffs/trees. Then 6
more iterations with the mask, islands under 400 px removed and holes under
400 px filled. The RNG seed is fixed, so the mask is reproducible.
"""
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
SRC = HERE / 'source' / 'boss-reference.png'
W, H = 1086, 1448
RECT = (20, 200, 1050, 1080)          # x, y, w, h


def srgb_to_lin(c):
    c = np.asarray(c, dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


# Seeds: polylines (x, y) with a stroke width. Placed well inside the figure / the background.
FG_STROKES = [
    ([(538, 240), (538, 400), (540, 520), (545, 700), (548, 840)], 40),        # head -> sash
    ([(300, 420), (290, 560), (300, 700), (380, 900), (400, 1000)], 40),        # right arm -> fist
    ([(830, 430), (880, 560), (900, 700), (920, 860)], 40),                     # left arm -> fist
    ([(440, 640), (660, 640)], 60), ([(440, 760), (660, 760)], 60),             # belly
    ([(200, 900), (180, 1050), (230, 1200)], 50),                                # hammer head
    ([(480, 985), (840, 900)], 18),                                              # haft
    ([(470, 920), (470, 1080), (450, 1190)], 30),                                # right leg + foot
    ([(700, 920), (800, 1060), (850, 1210)], 40),                                # left leg + foot
    ([(770, 1220), (950, 1215)], 20),                                            # left foot block
]
BG_STROKES = [
    ([(0, 1295), (1086, 1295)], 30), ([(0, 1420), (1086, 1420)], 60),          # lawn below the feet
    ([(600, 1200), (680, 1200)], 30),                                            # lawn between the feet
    ([(1060, 950), (1060, 1250)], 20), ([(1000, 1000), (1000, 1100)], 14),      # lawn right of the left leg
    ([(40, 260), (300, 260)], 40), ([(780, 250), (1080, 250)], 40),             # sky / cliffs beside the head
    ([(30, 400), (130, 700)], 30), ([(1060, 380), (1070, 760)], 20),            # cliffs / trees beside the arms
    ([(15, 820), (15, 1250)], 10),                                               # far left edge
    ([(60, 800), (200, 800)], 26),                                               # log behind the hammer
]


def build_mask(bgr):
    cv2.setRNGSeed(20261003)
    mask = np.zeros(bgr.shape[:2], np.uint8)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(bgr, mask, RECT, bgd, fgd, 6, cv2.GC_INIT_WITH_RECT)
    for pts, w in FG_STROKES:
        cv2.polylines(mask, [np.array(pts, np.int32)], False, int(cv2.GC_FGD), w)
    for pts, w in BG_STROKES:
        cv2.polylines(mask, [np.array(pts, np.int32)], False, int(cv2.GC_BGD), w)
    cv2.grabCut(bgr, mask, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
    m = ((mask == 1) | (mask == 3)).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= 400
    m = keep[lab].astype(np.uint8)
    inv = 1 - m
    n, lab, stats, _ = cv2.connectedComponentsWithStats(inv, 4)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < 400:
            m[lab == i] = 1
    return m


# Landmarks read off zoomed, ruled crops of the reference (pixel x, y).
# "R"/"L" are the CHARACTER's right/left: character-right is on the viewer's left.
LANDMARKS = {
    'head_top_back': (538, 214),
    'head_top_front_edge': (538, 250),
    'head_side_R': (458, 300),
    'head_side_L': (619, 290),
    'eye_R': (501, 331),
    'eye_L': (577, 313),
    'nose': (540, 345),
    'mouth_corner_R': (513, 373),
    'mouth_corner_L': (607, 357),
    'chin_bottom': (548, 412),
    'buckle_R': (381, 454),
    'buckle_L': (705, 440),
    'navel': (545, 770),
    'deltoid_R_outer': (212, 500),
    'deltoid_L_outer': (958, 470),
    'deltoid_R_top': (320, 372),
    'deltoid_L_top': (802, 348),
    'elbow_R_outer': (210, 700),
    'elbow_L_outer': (1000, 720),
    'fist_R_center': (395, 941),
    'fist_L_center': (928, 880),
    'haft_at_fist_R': (480, 985),
    'haft_at_fist_L': (840, 897),
    'haft_butt_end': (1043, 870),
    'haft_band_1': (657, 938),
    'haft_band_2': (726, 922),
    'haft_band_3': (793, 906),
    'hammer_bottom_corner': (175, 1268),
    'hammer_top_right_corner': (300, 838),
    'hammer_boss_left': (32, 1075),
    'foot_L_front_bottom_left': (752, 1263),
    'foot_L_front_bottom_right': (968, 1252),
    'foot_L_top_back': (860, 1152),
    'foot_R_front_bottom': (470, 1225),
    'foot_R_right_edge': (528, 1200),
    'trouser_hem_L': (830, 1100),
    'trouser_hem_R': (448, 1121),
    'sash_center': (560, 855),
}

# Material probe boxes (x0, y0, x1, y1) plus a colour rule on sRGB 0..255.
GREEN = lambda r, g, b: (g > r + 25) & (g > b + 45) & (g < 236)
PROBES = {
    'skin_belly': ((430, 640, 670, 830), GREEN),
    'skin_deltoid_L': ((760, 390, 930, 540), GREEN),
    'skin_arm_R': ((225, 560, 350, 650), GREEN),
    'skin_forearm_L': ((850, 700, 990, 790), GREEN),
    'skin_head': ((480, 225, 600, 290), GREEN),
    'skin_foot_L': ((760, 1190, 950, 1245), lambda r, g, b: (g > r + 25) & (g > b + 45) & (g < 205)),
    'shirt': ((430, 495, 640, 570), lambda r, g, b: (r > 120) & (r > g) & (g > b) & (r - b < 90)),
    'suspender': ((358, 360, 410, 415), lambda r, g, b: (r < 140) & (abs(r - g) < 30) & (g > b - 15) & (r > 40)),
    'buckle': ((352, 428, 410, 482), lambda r, g, b: (abs(r - b) < 25) & (abs(r - g) < 25) & (r > 70)),
    'sash': ((430, 846, 700, 868), lambda r, g, b: (r > g + 15) & (r > b + 5)),
    'trousers': ((820, 1000, 905, 1090), lambda r, g, b: (r < 130) & (b >= g - 6) & (g < r + 12)),
    'hammer_iron': ((150, 960, 320, 1140), lambda r, g, b: (abs(r - b) < 22) & (abs(r - g) < 22)),
    'haft_wood': ((490, 950, 610, 985), lambda r, g, b: (r > g + 15) & (g > b) & (r > 50)),
    'haft_band': ((625, 905, 675, 950), lambda r, g, b: (r < 120) & (abs(r - b) < 30)),
    'blood_skin': ((840, 400, 920, 480), lambda r, g, b: (r > g + 50) & (r > b + 40)),
    'eye_white': ((496, 325, 515, 342), lambda r, g, b: (r > 200) & (g > 200) & (b > 200)),
    'teeth': ((525, 362, 570, 385), lambda r, g, b: (r > 170) & (g > 160) & (b > 120)),
    'lawn': ((560, 1300, 1000, 1440), lambda r, g, b: (g > 180)),
}


def probe(rgb, box, rule):
    x0, y0, x1, y1 = box
    sub = rgb[y0:y1, x0:x1].reshape(-1, 3).astype(np.float64)
    m = rule(sub[:, 0], sub[:, 1], sub[:, 2])
    sel = sub[m]
    if len(sel) < 30:
        return None
    lum = sel @ np.array([0.2126, 0.7152, 0.0722])
    order = np.argsort(lum)
    n = len(sel)

    def pick(lo, hi):
        s = sel[order[int(lo * n):max(int(lo * n) + 1, int(hi * n))]]
        return [int(round(v)) for v in s.mean(axis=0)]
    lin_mean = srgb_to_lin(sel).mean(axis=0)
    return {
        'pixels': int(n),
        'shadow_srgb': pick(0.03, 0.15),
        'mid_srgb': pick(0.45, 0.55),
        'lit_srgb': pick(0.85, 0.97),
        'mean_linear': [round(float(v), 5) for v in lin_mean],
    }


def main():
    rgb = np.array(Image.open(SRC).convert('RGB'))
    assert rgb.shape == (H, W, 3), rgb.shape
    bgr = rgb[:, :, ::-1].copy()
    m = build_mask(bgr)
    Image.fromarray((m * 255).astype(np.uint8)).save(HERE / 'source' / 'reference_mask.png')
    ys, xs = np.nonzero(m)
    spans = {}
    for y in range(200, 1300, 20):
        row = np.nonzero(m[y])[0]
        if len(row):
            runs, start = [], row[0]
            for a, b in zip(row[:-1], row[1:]):
                if b != a + 1:
                    runs.append([int(start), int(a)])
                    start = b
            runs.append([int(start), int(row[-1])])
            spans[y] = runs
    fig = {'bbox': [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], 'area_px': int(m.sum())}
    probes = {k: probe(rgb, box, rule) for k, (box, rule) in PROBES.items()}
    out = {
        'reference': 'source/boss-reference.png',
        'size': [W, H],
        'figure': fig,
        'landmarks_px': LANDMARKS,
        'row_spans_px': spans,
        'probes': probes,
        'probe_boxes': {k: v[0] for k, v in PROBES.items()},
    }
    (HERE / 'source' / 'reference_measurements.json').write_text(json.dumps(out, indent=1))
    vis = bgr.copy()
    edge = cv2.morphologyEx(m, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    vis[edge > 0] = (255, 0, 255)
    for k, (x, y) in LANDMARKS.items():
        if y == 0:
            continue
        cv2.circle(vis, (x, y), 4, (0, 255, 255), -1)
        cv2.putText(vis, k, (x + 5, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (255, 255, 255), 1)
    for k, (box, _) in PROBES.items():
        cv2.rectangle(vis, box[:2], box[2:], (255, 128, 0), 1)
        cv2.putText(vis, k, (box[0], box[1] - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 160, 0), 1)
    (HERE / '_work').mkdir(exist_ok=True)
    cv2.imwrite(str(HERE / '_work' / 'Reference_Landmarks.png'), vis)
    print(json.dumps({'figure': fig, 'probes': {k: (v['mid_srgb'], v['pixels']) if v else None
                                                for k, v in probes.items()}}, indent=1))


if __name__ == '__main__':
    main()
