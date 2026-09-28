"""Queue-pad light column texture: white, opaque at the bottom, fading to clear at the top.

Used as Beam.Texture on the four curved beams that form each pad's light column. A beam maps
the image's vertical axis along its length (around the ring) and the horizontal axis across its
width, which is vertical here, so the fade runs left to right: x=0 is the top of the column.
Run with Pillow:
    python build_pad_light.py
Output: lobby/assets/pad-light-column.png. The uploaded asset id is recorded in ../ASSETS.md.
"""
from pathlib import Path
from PIL import Image

W, H = 256, 16
OUT = Path(__file__).parent / 'assets' / 'pad-light-column.png'


EDGE = 3  # clear pixels at the bottom edge: beams wrap textures, so a solid edge bleeds into the top


def alpha(x):
    if x >= W - EDGE:
        return 0
    t = x / (W - 1 - EDGE)  # 0 at the top of the column, 1 at the bottom
    if t > 0.94:  # a slightly brighter lip where the column meets the ring
        return 255
    return round(255 * 0.78 * t ** 1.8)


img = Image.new('RGBA', (W, H))
for x in range(W):
    a = alpha(x)
    for y in range(H):
        img.putpixel((x, y), (255, 255, 255, a))
OUT.parent.mkdir(exist_ok=True)
img.save(OUT)
print('wrote', OUT)
