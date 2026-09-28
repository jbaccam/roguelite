# Generates the Skill Tree icon: a faceted low-poly four-point sparkle star in the
# game's icon style (thick ink outline, 2-4 value facets, lime/gold palette).
# Output: skill-tree.png (512x512, transparent). Rendered at 4x and downsampled for clean edges.
from PIL import Image, ImageDraw, ImageFilter
import math

S = 2048
INK = (16, 22, 12, 255)

def star(cx, cy, R, r, rot=0.0):
    pts = []
    for i in range(8):
        a = rot + i * math.pi / 4 - math.pi / 2
        rad = R if i % 2 == 0 else r
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    return pts

def blend(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)

def draw_star(img, cx, cy, R, r, light, mid, dark, outline):
    d = ImageDraw.Draw(img)
    pts = star(cx, cy, R, r)
    # Ink outline: the silhouette drawn larger underneath.
    grow = star(cx, cy, R + outline * 1.25, r + outline, 0)
    d.polygon(grow, fill=INK)
    d.polygon(pts, fill=mid)
    # Facets: every point is split down its spine into a lit and a shaded half.
    # Light comes from the upper left, so faces turned that way are brighter.
    for i in range(0, 8, 2):
        tip = pts[i]
        left = pts[(i - 1) % 8]
        right = pts[(i + 1) % 8]
        c = (cx, cy)
        a = math.atan2(tip[1] - cy, tip[0] - cx)
        lit_left = math.cos(a - math.pi / 2 - math.radians(-135)) > 0
        m = (cx + (tip[0] - cx) * .42, cy + (tip[1] - cy) * .42)
        a_side, b_side = (light, mid) if lit_left else (mid, dark)
        d.polygon([c, m, left], fill=blend(a_side, (255, 255, 255, 255), .18))
        d.polygon([m, tip, left], fill=a_side)
        d.polygon([c, m, right], fill=blend(b_side, (0, 0, 0, 255), .10))
        d.polygon([m, tip, right], fill=b_side)
    # Small bright core facet.
    core = star(cx, cy, r * 0.62, r * 0.36, math.pi / 4)
    d.polygon(core, fill=(250, 255, 214, 255))

img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
# Soft lime halo behind the star (kept subtle so the icon still reads on charcoal).
halo = Image.new('RGBA', (S, S), (0, 0, 0, 0))
hd = ImageDraw.Draw(halo)
hd.ellipse([S * .2, S * .2, S * .8, S * .8], fill=(160, 245, 60, 110))
halo = halo.filter(ImageFilter.GaussianBlur(S * .07))
img.alpha_composite(halo)

LIGHT = (214, 255, 128, 255)
MID = (145, 232, 36, 255)
DARK = (70, 150, 18, 255)
draw_star(img, S * .47, S * .53, S * .41, S * .175, LIGHT, MID, DARK, S * .036)
# Two small companion sparkles (gold), like a twinkle.
GL, GM, GD = (255, 238, 150, 255), (255, 203, 64, 255), (205, 140, 30, 255)
draw_star(img, S * .80, S * .20, S * .125, S * .052, GL, GM, GD, S * .024)
draw_star(img, S * .83, S * .77, S * .08, S * .034, GL, GM, GD, S * .02)

img = img.resize((512, 512), Image.LANCZOS)
img.save('skill-tree.png')
print('ok', img.size)
