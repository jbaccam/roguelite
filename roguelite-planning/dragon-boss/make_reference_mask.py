"""Build source/reference_mask.png: the dragon figure in the untouched reference.

System python (numpy, Pillow, OpenCV). The procedure, so the mask can be rebuilt:

1. Colour candidates. Pixels that are dragon-coloured: crimson skin
   (r > 1.6 g, r > 1.4 b), membrane orange (r > 150, g/r 0.30-0.56, b < 0.42 r)
   and plate beige. The lava falls behind both wing tips share the membrane hue,
   so they are removed with the LAVA polygons (they are brighter and bluer:
   r ~ 252, b ~ 80-95 against the membrane's r ~ 170-230, b ~ 25-50).
2. Obsidian parts (horns, dorsal spikes, claws, wing claws, tail spade) are
   charcoal like the background rocks, so colour cannot find them. They are
   hand-traced as OBSIDIAN polygons, measured on 2-3.5x gridded crops.
3. A generous region = the dilated candidates plus the obsidian polygons, minus
   the BG_SEEDS polygons (sky, cliffs and floor seen through the figure: under
   both wings, between the legs, under the tail, around the horns).
4. OpenCV GrabCut refines the unknown band on colour and edges, with definite
   foreground = eroded colour candidates + obsidian cores and definite
   background = outside the generous region.
5. Clean-up: keep the component(s) touching the foreground seeds, fill enclosed
   pockets except the real see-through gaps (TRUE_GAPS), and write 8-bit 0/255
   at the reference's exact 1536 x 1024.

source/reference_mask_review.png outlines the mask in cyan over the reference;
it was inspected at full size and in zoomed crops (wing tips, horns, feet,
tail spade, the gaps under the belly).
"""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REF = HERE / 'source' / '4.webp'

# Lava falls and glowing pools in the background (definite background).
LAVA = [
    [(0, 180), (150, 180), (150, 760), (0, 760)],                       # left falls (behind right wing tip)
    [(1395, 150), (1536, 150), (1536, 780), (1395, 780)],               # right falls (behind left wing tip)
    [(0, 700), (330, 700), (330, 790), (0, 790)],                       # lava pool band left
    [(1150, 740), (1536, 740), (1536, 800), (1150, 800)],               # lava band right
]
# Exceptions carved back out of LAVA (the dragon overlaps these boxes).
LAVA_KEEP = [
    [(152, 175), (160, 175), (160, 362), (118, 375), (98, 395), (78, 440), (48, 474), (38, 468), (62, 398), (97, 287)],  # right wing leading bone + claw
    [(1380, 320), (1420, 330), (1470, 370), (1498, 472), (1480, 480), (1440, 422), (1405, 377)],  # left wing finger-1 bone + claw
    [(1395, 600), (1480, 670), (1480, 700), (1420, 790), (1395, 780)],  # tail spade
    [(1150, 740), (1395, 740), (1395, 800), (1150, 800)],               # tail underside
    [(262, 700), (330, 700), (330, 790), (262, 790)],                   # right front leg
]

# Zones where charcoal obsidian parts sit (horns, dorsal spikes, wing claws,
# foot claws, tail spade). Obsidian shares its colour with the background
# rocks, so dark pixels only count as dragon inside these zones. The zones
# are generous; the colour rule (dark, r > b + 3, r > g + 8) and GrabCut find
# the actual edge.
# rule 'sky': against bright pink sky, anything with max channel < 150 is obsidian.
# rule 'cliff': against pale lilac cliffs, obsidian is darker and redder (max < 118, r >= b).
# rule 'floor': against the grey floor, obsidian is redder than the stone (r > b + 3, r > g + 8).
OBS_ZONES = [
    ('sky', [(395, 85), (760, 80), (760, 130), (700, 215), (560, 215), (395, 205)]),        # horns
    ('sky', [(620, 200), (725, 195), (800, 265), (835, 330), (830, 385), (760, 380), (625, 300)]),  # neck spikes
    ('cliff', [(870, 440), (1000, 500), (1150, 630), (1350, 685), (1352, 742), (1150, 722), (1000, 612), (870, 522)]),  # back/tail spikes
    ('cliff', [(1310, 595), (1495, 680), (1425, 800), (1370, 762), (1330, 640)]),           # tail spade
    ('sky', [(828, 12), (922, 18), (922, 102), (850, 92)]),                                 # left wing thumb claw
    ('sky', [(333, 25), (422, 25), (412, 122), (333, 112)]),                                # right wing thumb claw
    ('cliff', [(1428, 355), (1502, 440), (1497, 482), (1428, 432)]),                        # left wing f1 claw
    ('cliff', [(1222, 428), (1272, 428), (1272, 548), (1222, 548)]),                        # left wing f2 claw
    ('cliff', [(28, 378), (98, 378), (92, 442), (28, 492)]),                                # right wing f1 claw
    ('cliff', [(198, 428), (252, 428), (248, 512), (198, 512)]),                            # right wing f2 claw
    ('floor', [(150, 828), (362, 828), (362, 922), (150, 917)]),                            # claws FR
    ('floor', [(505, 818), (662, 818), (662, 892), (505, 892)]),                            # claws HR
    ('floor', [(700, 838), (1006, 838), (1006, 946), (700, 946)]),                          # claws FL
    ('floor', [(958, 833), (1162, 833), (1162, 902), (958, 902)]),                          # claws HL
]
# Where beige plate colour counts as dragon (jaw, fangs, chest, belly, tail
# underside). Outside these the pink clouds would pass the beige rule.
BEIGE_ZONE = [
    [(340, 250), (600, 250), (640, 330), (800, 560), (820, 760), (700, 800), (480, 760), (400, 600), (340, 380)],
    [(980, 700), (1400, 690), (1400, 830), (980, 830)],
]

# Definite background seen through or around the figure.
BG_SEEDS = [
    [(0, 0), (1536, 0), (1536, 18), (0, 18)],                            # sky strip
    [(0, 950), (1536, 950), (1536, 1024), (0, 1024)],                    # foreground floor
    [(95, 380), (150, 360), (200, 380), (215, 470), (200, 540), (140, 560), (100, 480)],   # under right wing panel 1
    [(250, 470), (320, 450), (335, 520), (320, 600), (260, 600)],        # under right wing panel 2
    [(1265, 360), (1320, 352), (1390, 380), (1400, 470), (1330, 560), (1270, 520)],  # under left wing panel 1
    [(1080, 520), (1180, 500), (1250, 540), (1270, 620), (1150, 660), (1090, 600)],  # between left wing and tail
    [(740, 60), (860, 40), (880, 150), (840, 260), (770, 240), (745, 150)],          # sky between horn and left wing arm
    [(420, 20), (740, 20), (730, 70), (600, 90), (440, 85)],             # sky above head
    [(430, 720), (500, 730), (505, 800), (440, 830)],                    # between right front leg and belly/hind foot
    [(660, 800), (700, 795), (705, 850), (665, 850)],                    # between hind foot and left front foot
    [(1180, 820), (1536, 820), (1536, 950), (1180, 950)],                # floor right
    [(0, 790), (150, 790), (150, 950), (0, 950)],                        # floor left
    [(330, 930), (700, 930), (700, 950), (330, 950)],                    # floor near
    [(420, 880), (500, 880), (500, 930), (420, 930)],
    [(1000, 900), (1180, 900), (1180, 950), (1000, 950)],
    [(505, 790), (560, 790), (560, 822), (505, 822)],                    # floor behind the far hind foot
    [(655, 880), (705, 880), (705, 930), (655, 930)],                    # floor between hind and near front foot
    [(1000, 893), (1160, 890), (1160, 925), (1000, 925)],
    [(782, 285), (828, 292), (834, 326), (800, 334), (786, 320)],        # cliff between neck spike 2 and the left wing humerus
    [(101, 400), (126, 385), (126, 462), (97, 466)],                     # cliff right of the right wing finger-1 claw
    [(1395, 392), (1420, 392), (1437, 420), (1432, 440), (1395, 435)],   # lit cliff inside the left wing tip                # floor under the near hind claws
    [(700, 800), (750, 800), (745, 845), (700, 850)],                    # gap left of the near front leg
    [(1160, 830), (1200, 830), (1200, 900), (1160, 900)],                # floor right of the near hind foot
    [(140, 915), (700, 915), (700, 930), (140, 930)],                    # floor strip under the front feet
    [(447, 706), (470, 702), (538, 768), (552, 798), (545, 820), (505, 822), (442, 830), (424, 800), (432, 760)],  # under the belly
    [(648, 882), (702, 878), (702, 905), (648, 905)],                    # floor right of the far hind foot
    [(713, 790), (728, 790), (728, 838), (713, 842)],                    # gap between far hind shin and near front leg
    [(412, 830), (505, 830), (510, 900), (405, 905)],                    # floor between right front foot and far hind foot
]

# Definite foreground: thin tips GrabCut would otherwise shave off.
FG_SEEDS = [
    [(1466, 420), (1478, 418), (1487, 466), (1482, 468)],     # left wing finger-1 claw tip
    [(1245, 480), (1255, 480), (1256, 528), (1250, 528)],     # left wing finger-2 claw tip
    [(50, 430), (62, 425), (46, 462), (43, 460)],             # right wing finger-1 claw tip
    [(214, 460), (224, 460), (216, 495), (213, 495)],         # right wing finger-2 claw tip
    [(846, 28), (870, 35), (890, 60), (880, 66)],             # left wing thumb claw
    [(404, 40), (408, 44), (380, 90), (372, 86)],             # right wing thumb claw
    [(700, 104), (718, 96), (712, 120), (690, 130)],          # near big horn tip
    [(522, 104), (538, 97), (530, 120), (515, 126)],          # far big horn tip
    [(1330, 612), (1360, 622), (1380, 650), (1350, 640)],     # tail spade upper barb
    [(1440, 682), (1470, 684), (1440, 720), (1425, 715)],     # tail spade point
]

# Enclosed background pockets that are real see-through gaps.
TRUE_GAPS = []


def poly_mask(size, polys):
    m = Image.new('L', size, 0)
    d = ImageDraw.Draw(m)
    for p in polys:
        d.polygon(p, fill=255)
    return np.asarray(m) > 0


def main():
    img = np.asarray(Image.open(REF).convert('RGB'))
    h, w = img.shape[:2]
    size = (w, h)
    r, g, b = [img[:, :, i].astype(int) for i in range(3)]
    red = (r > 70) & (r > g * 1.6) & (r > b * 1.4)
    orange = (r > 150) & (g > 0.30 * r) & (g < 0.56 * r) & (b < 0.42 * r)
    beige = (r > 140) & (g > 0.55 * r) & (g < 0.85 * r) & (b < 0.72 * r) & (r - b > 50)
    beige &= poly_mask(size, BEIGE_ZONE)
    mx = np.maximum(np.maximum(r, g), b)
    rules = {'sky': mx < 150,
             'cliff': (mx < 118) & (r >= b),
             'floor': (mx < 115) & (r > b + 3) & (r > g + 8)}
    obs = np.zeros((h, w), bool)
    for rule, poly in OBS_ZONES:
        obs |= rules[rule] & poly_mask(size, [poly])
    lava = poly_mask(size, LAVA) & ~poly_mask(size, LAVA_KEEP)
    bg_seed = poly_mask(size, BG_SEEDS) | lava
    cand = (red | orange | beige | obs) & ~bg_seed
    cand8 = cv2.morphologyEx(cand.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    generous = (cv2.dilate(cand8, np.ones((21, 21), np.uint8)) > 0) & ~bg_seed
    sure_fg = (cv2.erode(cand8, np.ones((7, 7), np.uint8)) > 0) & ~bg_seed
    sure_fg |= poly_mask(size, FG_SEEDS)
    generous |= sure_fg

    gc = np.full((h, w), cv2.GC_BGD, np.uint8)
    gc[generous] = cv2.GC_PR_FGD
    gc[sure_fg] = cv2.GC_FGD
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(cv2.cvtColor(img, cv2.COLOR_RGB2BGR), gc, None, bgd, fgd, 8, cv2.GC_INIT_WITH_MASK)
    mask = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    keep = np.zeros_like(mask)
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    for i in range(1, n):
        if i == big or stats[i, cv2.CC_STAT_AREA] > 3000:
            keep[lab == i] = 1
    inv = (1 - keep).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(inv, connectivity=4)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])).tolist())
    gaps = {int(lab[y, x]) for x, y in TRUE_GAPS}
    for i in range(1, n):
        if i not in border and i not in gaps and stats[i, cv2.CC_STAT_AREA] < 6000:
            comp = lab == i
            if not (comp & bg_seed).any():       # a pocket holding known background stays open
                keep[comp] = 1
    out = (keep * 255).astype(np.uint8)
    Image.fromarray(out).save(HERE / 'source' / 'reference_mask.png')

    edge = cv2.morphologyEx(out, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    rev = img.copy()
    rev[edge] = (0, 255, 255)
    Image.fromarray(rev).save(HERE / 'source' / 'reference_mask_review.png')
    print('mask pixels', int(keep.sum()), 'fraction', round(float(keep.mean()), 4))


if __name__ == '__main__':
    main()
