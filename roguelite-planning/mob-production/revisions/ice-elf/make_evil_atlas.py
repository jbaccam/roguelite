"""Ice Elf atlas: the shared painted atlas with two tiles the elf never used
repainted, and the skin tile cooled toward the reference's pale ice blue.

python make_evil_atlas.py  ->  EvilAtlas.png (the shared Materials.png is untouched)
Tile indices follow deliver.py's source_tiles (row-major from the top-left).
"""
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
im = Image.open(HERE.parent / 'Materials.png').convert('RGBA')
W = im.size[0] // 4
px = im.load()


def tile(index):
    x0, y0 = (index % 4) * W, (index // 4) * W
    return range(x0, x0 + W), range(y0, y0 + W)


def recolor(index, fn):
    xs, ys = tile(index)
    for y in ys:
        for x in xs:
            r, g, b, a = px[x, y]
            px[x, y] = (*fn(r, g, b), a)


def clamp(v):
    return max(0, min(255, int(v)))


# Skin (shared with the old 'cyan'): keep the painted variation, shift it
# from grey-blue to pale ice blue.
recolor(1, lambda r, g, b: (clamp(r * .86), clamp(g * 1.12 + 4), clamp(b * 1.2 + 8)))
# Teal tile -> 'glow': near-white ice with a faint cyan cast, lightly
# varied so it still reads as painted, used for the pupil-less eyes.
recolor(5, lambda r, g, b: (clamp(196 + (r - 59) * .25), clamp(246 + (g - 89) * .12), 255))
# Coral tile -> 'mark': deep indigo face markings.
recolor(4, lambda r, g, b: (clamp(46 + (r - 176) * .12), clamp(40 + (g - 80) * .12), clamp(92 + (b - 53) * .15)))
im.save(HERE / 'EvilAtlas.png')
print('wrote', HERE / 'EvilAtlas.png')
