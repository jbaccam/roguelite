"""Measure the Frost Cyclops reference. System Python (Pillow, numpy, OpenCV).

    python measure_reference.py

Writes, all derived from source/FrostCyclops_reference.webp (never modified):
  source/reference_mask.png          figure silhouette (255 = figure, club included)
  source/reference_measurements.json landmarks, silhouette spans, colour probes
  previews/Reference_Landmarks.png   the landmarks drawn on the reference, for checking

How the mask is made (documented in README): OpenCV GrabCut, initialised with a
rectangle around the figure (x 40..1065, y 175..1310), 8 iterations, then a second
4-iteration pass with the eye forced to foreground (GrabCut classes the white
sclera as snow otherwise). Holes smaller than 400 px are filled and islands
smaller than 400 px removed. The result was checked edge-by-edge in zoomed
overlays (arm/torso gaps, crotch gap, feet, club, far arm) before being accepted.
The seed is fixed, so the mask is reproducible.
"""
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
SRC = HERE / 'source' / 'FrostCyclops_reference.webp'
W, H = 1086, 1448


def srgb_to_lin(c):
    c = np.asarray(c, dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def build_mask(bgr):
    cv2.setRNGSeed(20260928)
    mask = np.zeros(bgr.shape[:2], np.uint8)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(bgr, mask, (40, 175, 1025, 1135), bgd, fgd, 8, cv2.GC_INIT_WITH_RECT)
    cv2.ellipse(mask, (543, 268), (34, 24), 0, 0, 360, int(cv2.GC_FGD), -1)
    cv2.grabCut(bgr, mask, None, bgd, fgd, 4, cv2.GC_INIT_WITH_MASK)
    m = ((mask == 1) | (mask == 3)).astype(np.uint8)
    # remove small islands
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= 400
    m = keep[lab].astype(np.uint8)
    # fill small holes
    inv = 1 - m
    n, lab, stats, _ = cv2.connectedComponentsWithStats(inv, 4)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < 400:
            m[lab == i] = 1
    return m


# Landmarks read off zoomed, gridded crops of the reference (pixel x, y).
# "R"/"L" are the CHARACTER's right/left: character-right is on the viewer's left.
LANDMARKS = {
    'head_top': (541, 185),
    'head_top_left_corner': (484, 203),
    'head_top_right_corner': (590, 200),
    'head_side_R_at_eye': (477, 268),
    'head_side_L_at_eye': (603, 262),
    'ear_R_outer': (463, 266),
    'ear_L_outer': (624, 252),
    'brow_notch': (539, 240),
    'brow_R_outer': (485, 240),
    'brow_L_outer': (597, 236),
    'eye_center': (542, 263),
    'eye_sclera_left': (517, 268),
    'eye_sclera_right': (567, 266),
    'eye_sclera_bottom': (542, 284),
    'iris_center': (542, 263),
    'pupil_center': (542, 263),
    'mouth_corner_R': (497, 330),
    'mouth_corner_L': (600, 322),
    'mouth_top_mid': (545, 306),
    'mouth_bottom_mid': (548, 323),
    'tusk_R_tip': (508, 298),
    'tusk_R_base': (507, 328),
    'tusk_L_tip': (583, 290),
    'tusk_L_base': (594, 319),
    'chin_bottom': (545, 371),
    'jaw_R_corner': (492, 350),
    'jaw_L_corner': (616, 345),
    'mantle_R_outer_tip': (222, 405),
    'mantle_R_top_inner': (440, 238),
    'mantle_R_lowest_tip': (330, 556),
    'mantle_L_top_tip': (680, 222),
    'mantle_L_outer_tip': (981, 440),
    'mantle_L_lowest_tip': (723, 605),
    'sternum_top': (505, 420),
    'pec_R_lower_edge': (440, 505),
    'pec_L_lower_edge': (560, 505),
    'belly_left_edge': (343, 620),
    'belly_right_edge': (765, 620),
    'navel': (487, 690),
    'belt_R_end_top': (345, 690),
    'belt_L_end_top': (770, 677),
    'buckle_center': (487, 766),
    'buckle_left': (425, 766),
    'buckle_right': (548, 766),
    'buckle_top': (487, 718),
    'buckle_bottom': (487, 815),
    'loincloth_front_tip': (548, 1090),
    'arm_R_outer_max': (135, 590),
    'wrap_R_top_left': (113, 621),
    'wrap_R_bottom_left': (85, 778),
    'wrap_R_center': (180, 700),
    'hand_R_center': (175, 820),
    'hand_R_bottom': (170, 900),
    'haft_exit_below_hand': (205, 900),
    'club_head_center': (190, 1150),
    'club_head_left': (52, 1110),
    'club_head_right': (338, 1160),
    'club_head_top': (175, 995),
    'club_head_bottom': (215, 1300),
    'arm_L_outer_max': (1052, 700),
    'wrap_L_top_center': (947, 740),
    'wrap_L_bottom_center': (947, 880),
    'fist_L_center': (928, 960),
    'fist_L_bottom': (960, 1046),
    'knee_R': (400, 1010),
    'knee_L': (745, 1040),
    'foot_R_toe_bottom': (395, 1248),
    'foot_R_left': (310, 1240),
    'foot_R_right': (492, 1225),
    'foot_L_toe_bottom': (760, 1290),
    'foot_L_left': (655, 1285),
    'foot_L_right': (925, 1280),
    'toenail_R_big_width': (53, 0),
    'toenail_L_big_width': (57, 0),
}

# Material probe boxes (x0, y0, x1, y1) plus a colour rule on sRGB 0..255.
PROBES = {
    'skin_belly': ((400, 560, 640, 690), lambda r, g, b: (b > r + 20) & (b > 90)),
    'skin_arm_L': ((880, 520, 1030, 720), lambda r, g, b: (b > r + 20) & (b > 90)),
    'skin_arm_R': ((110, 480, 240, 600), lambda r, g, b: (b > r + 20) & (b > 90)),
    'skin_leg_L': ((650, 1060, 840, 1180), lambda r, g, b: (b > r + 20) & (b > 90)),
    'skin_head': ((480, 195, 600, 245), lambda r, g, b: (b > r + 15) & (b > 90)),
    'fur_mantle': ((640, 280, 960, 520), lambda r, g, b: (r >= b) & (r > 150)),
    'leather_wrap': ((860, 745, 1030, 860), lambda r, g, b: (r > b + 8) & (r < 170)),
    'leather_belt': ((580, 690, 760, 740), lambda r, g, b: (r > b + 5) & (r < 160)),
    'loincloth': ((440, 830, 545, 1000), lambda r, g, b: (r < 130) & (b < 130) & (g < 115)),
    'buckle_stone': ((440, 730, 530, 805), lambda r, g, b: (abs(r - b) < 25) & (r > 90)),
    'club_stone': ((60, 1040, 330, 1280), lambda r, g, b: (abs(r - b) < 18) & (abs(r - g) < 18) & (r > 95)),
    'club_haft': ((175, 870, 250, 990), lambda r, g, b: (r > b + 12) & (r < 180)),
    'club_strap': ((110, 1100, 300, 1280), lambda r, g, b: (r > b + 10) & (r < 140)),
    'eye_sclera': ((518, 266, 566, 283), lambda r, g, b: (r > 200) & (g > 200)),
    'eye_iris': ((530, 262, 555, 275), lambda r, g, b: (b > r + 60) & (g > r + 30)),
    'tusk': ((500, 300, 515, 325), lambda r, g, b: (r > 170) & (r > b)),
    'toenails_skin_L': ((660, 1215, 910, 1285), lambda r, g, b: (b > r + 15) & (b > 100)),
    'snow_ground': ((520, 1330, 1000, 1440), lambda r, g, b: (r > 150)),
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
    for y in range(180, 1310, 20):
        row = np.nonzero(m[y])[0]
        if len(row):
            # list the separate runs on this row
            runs, start = [], row[0]
            for a, b in zip(row[:-1], row[1:]):
                if b != a + 1:
                    runs.append([int(start), int(a)])
                    start = b
            runs.append([int(start), int(row[-1])])
            spans[y] = runs
    fig = {
        'bbox': [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
        'area_px': int(m.sum()),
    }
    probes = {k: probe(rgb, box, rule) for k, (box, rule) in PROBES.items()}
    out = {
        'reference': 'source/FrostCyclops_reference.webp',
        'size': [W, H],
        'figure': fig,
        'landmarks_px': LANDMARKS,
        'row_spans_px': spans,
        'probes': probes,
        'probe_boxes': {k: v[0] for k, v in PROBES.items()},
    }
    (HERE / 'source' / 'reference_measurements.json').write_text(json.dumps(out, indent=1))

    # landmark check image
    vis = bgr.copy()
    edge = cv2.morphologyEx(m, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    vis[edge > 0] = (0, 0, 255)
    for k, (x, y) in LANDMARKS.items():
        if y == 0:
            continue
        cv2.circle(vis, (x, y), 4, (0, 255, 255), -1)
        cv2.putText(vis, k, (x + 5, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (0, 255, 0), 1)
    for k, (box, _) in PROBES.items():
        cv2.rectangle(vis, box[:2], box[2:], (255, 128, 0), 1)
    (HERE / 'previews').mkdir(exist_ok=True)
    cv2.imwrite(str(HERE / 'previews' / 'Reference_Landmarks.png'), vis)
    print(json.dumps({'figure': fig, 'probes': probes}, indent=1))


if __name__ == '__main__':
    main()
