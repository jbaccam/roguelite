"""Build source/reference_mask.png: the figure-plus-staff silhouette of the reference.

Run with system python (needs opencv-python, numpy, Pillow):
    python make_reference_mask.py

Method: OpenCV GrabCut seeded from a generous hand-drawn hull (probable
foreground), interior scribbles (definite foreground) and background scribbles
on the sky, the far cliffs, the sand between the legs and the gap between the
staff and the leg. After segmentation, components smaller than 3,000 px are
dropped and enclosed background holes smaller than 1,500 px are filled (the
glowing eye sockets and a dark collar tile were mis-labelled as sky). The one
large enclosed hole kept is the real gap between the staff and the right leg.
Every region was then checked against the image in zoomed contour overlays.
"""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
SRC = HERE / 'source' / 'Pharaoh_Reference.webp'
OUT = HERE / 'source' / 'reference_mask.png'

img = np.asarray(Image.open(SRC).convert('RGB'))[:, :, ::-1].copy()
H, W = img.shape[:2]
mask = np.full((H, W), cv2.GC_BGD, np.uint8)
hull = np.array([(45, 40), (300, 40), (300, 280), (360, 160), (500, 120), (620, 130),
                 (760, 300), (800, 360), (960, 420), (1040, 700), (1045, 1060),
                 (990, 1070), (980, 1375), (690, 1380), (640, 1160), (500, 1150),
                 (490, 1330), (270, 1340), (270, 1370), (140, 1370), (130, 800),
                 (60, 780), (40, 300)], np.int32)
cv2.fillPoly(mask, [hull], cv2.GC_PR_FGD)
FG = [[(540, 200), (545, 350)], [(420, 500), (700, 500)], [(400, 600), (720, 600)],
      [(450, 700), (650, 700)], [(520, 760), (520, 1000)], [(350, 850), (750, 850)],
      [(360, 1000), (360, 1250)], [(760, 1000), (760, 1300)], [(160, 300), (160, 500)],
      [(180, 780), (200, 1300)], [(120, 560), (220, 680)], [(880, 700), (1000, 780)],
      [(880, 880), (950, 980)], [(420, 280), (460, 330)], [(650, 280), (700, 330)],
      [(130, 90), (240, 70)], [(260, 150), (262, 230)], [(820, 1300), (930, 1330)],
      [(280, 1260), (420, 1280)], [(80, 200), (80, 250)], [(300, 640), (300, 700)]]
for a, b in FG:
    cv2.line(mask, a, b, cv2.GC_FGD, 6)
BG = [[(300, 0), (1086, 0)], [(0, 0), (0, 1448)], [(1080, 0), (1080, 1448)],
      [(0, 1440), (1086, 1440)], [(700, 150), (900, 150)], [(850, 250), (850, 330)],
      [(1060, 500), (1060, 1000)], [(560, 1180), (620, 1330)], [(530, 1350), (650, 1400)],
      [(100, 850), (100, 1300)], [(10, 450), (40, 700)], [(170, 180), (200, 230)],
      [(330, 180), (360, 240)], [(270, 700), (270, 760)], [(1010, 1100), (1010, 1400)],
      [(600, 1250), (640, 1400)]]
for a, b in BG:
    cv2.line(mask, a, b, cv2.GC_BGD, 5)
bgd = np.zeros((1, 65), np.float64)
fgd = np.zeros((1, 65), np.float64)
cv2.grabCut(img, mask, None, bgd, fgd, 8, cv2.GC_INIT_WITH_MASK)
m = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
n, lab, st, _ = cv2.connectedComponentsWithStats(m)
keep = np.zeros_like(m)
for i in range(1, n):
    if st[i, cv2.CC_STAT_AREA] > 3000:
        keep[lab == i] = 255
inv = (keep == 0).astype(np.uint8)
n, lab, st, _ = cv2.connectedComponentsWithStats(inv, connectivity=4)
for i in range(1, n):
    if st[i, cv2.CC_STAT_AREA] < 1500:
        keep[lab == i] = 255
cv2.imwrite(str(OUT), keep)
print('reference mask', OUT, 'figure pixels', int((keep > 0).sum()))
