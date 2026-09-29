"""Build source/reference_mask.png: the crab figure in the untouched reference.

System python (numpy, Pillow, OpenCV). Procedure, so the mask can be rebuilt:

1. A generous hand-traced outline polygon (OUTLINE) marks everything that could
   be crab; outside it is definite background.
2. Definite foreground seeds: strongly saturated red pixels inside the outline,
   plus hand-placed seed polygons inside the beige parts (teeth, belly plates,
   claw fingers, leg tips), because beige exoskeleton and warm sand share a hue
   and colour alone cannot separate them.
3. Definite background seeds: hand-placed polygons over sand, sea and sky that
   show through the claw openings and between the legs.
4. OpenCV GrabCut refines the unknown band on colour and edges.
5. The result is cleaned (largest component plus any component overlapping a
   foreground seed; every enclosed pocket filled except the two real
   see-through gaps listed in TRUE_GAPS) and written as 8-bit
   0/255 at the reference's exact 1536 x 1024 size.

The review image source/reference_mask_review.png outlines the mask over the
reference so it can be checked by eye; it was inspected at full size and in
zoomed crops of every leg tip and both claw openings.
"""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REF = HERE / 'source' / 'king-crab-reference.webp'

# Generous outline, clockwise from the big claw's crown. Pixels.
OUTLINE = [
    (300, 218), (372, 250), (415, 290), (428, 288), (520, 228), (575, 240), (636, 158),
    (705, 205), (797, 176), (880, 212), (962, 203), (1010, 262), (1052, 283),
    (1075, 330), (1152, 382), (1150, 440), (1215, 432), (1262, 412), (1340, 440),
    (1420, 520), (1472, 640), (1468, 730), (1432, 812), (1405, 812), (1396, 770),
    (1250, 640), (1252, 700), (1250, 790), (1190, 792), (1172, 730), (1170, 822),
    (1105, 828), (1060, 720), (950, 700), (920, 775), (850, 776), (845, 640),
    (700, 630), (682, 845), (655, 848), (580, 760), (520, 740), (500, 745),
    (450, 820), (300, 820), (292, 815), (232, 815), (190, 780), (100, 700),
    (58, 560), (62, 440), (110, 340), (190, 260),
]

# Definite-foreground seed polygons inside beige or shadowed parts.
FG_SEEDS = [
    [(770, 450), (840, 445), (815, 530), (795, 535)],            # left tooth
    [(860, 450), (920, 450), (885, 530), (870, 535)],            # right tooth
    [(650, 540), (950, 540), (930, 600), (700, 605)],            # belly plates
    [(390, 480), (470, 480), (495, 640), (470, 660), (410, 560)],  # big claw dactyl
    [(1265, 600), (1320, 610), (1360, 700), (1340, 720), (1280, 650)],  # small claw finger
    [(1300, 670), (1345, 690), (1372, 722), (1384, 745), (1366, 738), (1330, 712)],  # its tip
    [(600, 740), (650, 740), (660, 815), (640, 815)],            # leg A tip
    [(1100, 720), (1150, 720), (1125, 800), (1112, 800)],        # leg D tip
    [(870, 730), (905, 730), (880, 755)],                        # leg C tip
    [(1205, 740), (1235, 740), (1222, 770)],                     # leg E tip
    [(245, 780), (280, 780), (265, 800)],                        # leg B tip
    [(760, 415), (800, 415), (795, 436), (768, 436)],            # right stalk cup
    [(905, 425), (938, 425), (935, 446), (908, 446)],            # left stalk cup
    [(560, 380), (800, 400), (820, 430), (600, 440)],            # face under the brows
]

# Definite-background seeds: sand/sea/sky seen through openings.
BG_SEEDS = [
    [(1340, 640), (1385, 650), (1400, 740), (1375, 745)],        # small claw opening
    [(1180, 800), (1260, 800), (1260, 830), (1180, 830)],
    [(930, 780), (1080, 790), (1080, 830), (930, 830)],          # sand between C and D
    [(700, 700), (840, 700), (840, 800), (700, 800)],            # sand under belly
    [(690, 640), (840, 640), (840, 690), (690, 690)],            # sea under belly
    [(500, 760), (560, 760), (560, 780), (500, 780)],
    [(0, 0), (1536, 0), (1536, 150), (0, 150)],                  # sky band
    [(0, 850), (1536, 850), (1536, 1024), (0, 1024)],            # foreground sand
    [(960, 715), (1050, 715), (1050, 760), (960, 760)],          # sand between C and D (upper)
    [(1175, 660), (1195, 660), (1195, 700), (1175, 700)],        # gap between D and E
    [(1270, 690), (1330, 730), (1330, 780), (1270, 780)],        # sand under small claw finger
    [(506, 640), (528, 640), (528, 728), (506, 718)],            # gap between big dactyl and leg A
]

# Enclosed background pockets that are real see-through gaps (sky/sea visible
# through the figure). Every other enclosed pocket is a texture misread (beige
# chips, eye whites) and is filled.
TRUE_GAPS = [(515, 505), (1045, 532)]


def poly_mask(size, polys):
    m = Image.new('L', size, 0)
    d = ImageDraw.Draw(m)
    for p in polys:
        d.polygon(p, fill=255)
    return np.asarray(m) > 0


def main():
    img = np.asarray(Image.open(REF).convert('RGB'))
    h, w = img.shape[:2]
    inside = poly_mask((w, h), [OUTLINE])
    r, g, b = [img[:, :, i].astype(int) for i in range(3)]
    red = (r > 110) & (r > g * 1.45) & (r > b * 1.45) & inside
    fg_seed = poly_mask((w, h), FG_SEEDS) & inside
    bg_seed = poly_mask((w, h), BG_SEEDS)

    gc = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
    gc[inside] = cv2.GC_PR_FGD
    gc[~inside] = cv2.GC_BGD
    gc[bg_seed] = cv2.GC_BGD
    gc[red] = cv2.GC_FGD
    gc[fg_seed] = cv2.GC_FGD
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(cv2.cvtColor(img, cv2.COLOR_RGB2BGR), gc, None, bgd, fgd, 8, cv2.GC_INIT_WITH_MASK)
    mask = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8)

    # Keep the components that belong to the crab.
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    keep = np.zeros_like(mask)
    if n > 1:
        big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        for i in range(1, n):
            comp = lab == i
            if i == big or (comp & fg_seed).any():
                keep[comp] = 1
    # Fill enclosed pockets (beige chips and eye whites misread as sand) except
    # the listed see-through gaps.
    inv = (1 - keep).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(inv, connectivity=4)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])).tolist())
    gaps = {int(lab[y, x]) for x, y in TRUE_GAPS}
    for i in range(1, n):
        if i not in border and i not in gaps:
            keep[lab == i] = 1
    out = (keep * 255).astype(np.uint8)
    Image.fromarray(out).save(HERE / 'source' / 'reference_mask.png')

    # Review overlay: mask edge in cyan over the reference.
    edge = cv2.morphologyEx(out, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    rev = img.copy()
    rev[edge] = (0, 255, 255)
    Image.fromarray(rev).save(HERE / 'source' / 'reference_mask_review.png')
    print('mask pixels', int(keep.sum()), 'fraction', round(float(keep.mean()), 4))


if __name__ == '__main__':
    main()
