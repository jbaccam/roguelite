"""The tutorial guide's arrow (TutorialGuideUI): a chunky white arrow with a thick black outline and a
soft drop shadow, pointing up, centred in a 256x256 transparent PNG. The tip is at the top centre
(y = TIP_Y px), which TutorialGuideUI uses to put the tip on its target.
    python make_arrow.py        -> arrow.png next to this file
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

S = 4                    # supersampling
W = H = 256
TIP_Y = 14               # where the tip ends up, in final pixels
OUTLINE = 13             # black outline, final pixels


def shape(scale, grow=0.0):
    """Arrow polygon (pointing up) in pixels at `scale`, grown outward by `grow` px."""
    cx = W / 2
    head_w, head_h = 176, 112
    shaft_w = 78
    top, bottom = TIP_Y + OUTLINE, H - 16 - OUTLINE
    g = grow
    pts = [
        (cx, top - g * 1.6),
        (cx + head_w / 2 + g * 1.4, top + head_h + g * 0.7),
        (cx + shaft_w / 2 + g, top + head_h + g * 0.7),
        (cx + shaft_w / 2 + g, bottom + g),
        (cx - shaft_w / 2 - g, bottom + g),
        (cx - shaft_w / 2 - g, top + head_h + g * 0.7),
        (cx - head_w / 2 - g * 1.4, top + head_h + g * 0.7),
    ]
    return [(x * scale, y * scale) for x, y in pts]


def main():
    big = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    # Drop shadow: the outline shape, offset down-right and blurred.
    shadow = Image.new("RGBA", big.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon([(x + 6 * S, y + 8 * S) for x, y in shape(S, OUTLINE)], fill=(0, 0, 0, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(7 * S))
    big = Image.alpha_composite(big, shadow)
    d = ImageDraw.Draw(big)
    d.polygon(shape(S, OUTLINE), fill=(12, 14, 10, 255))          # outline
    d.polygon(shape(S, 0), fill=(255, 255, 255, 255))             # face
    # A light inner shade on the lower half, so it doesn't read flat.
    shade = Image.new("RGBA", big.size, (0, 0, 0, 0))
    ImageDraw.Draw(shade).polygon(shape(S, 0), fill=(0, 0, 0, 255))
    grad = Image.new("L", big.size, 0)
    gd = ImageDraw.Draw(grad)
    for y in range(big.size[1]):
        k = max(0.0, (y / big.size[1] - 0.55) / 0.45)
        gd.line([(0, y), (big.size[0], y)], fill=int(34 * k))
    mask = Image.composite(grad, Image.new("L", big.size, 0), shade.split()[3])
    tint = Image.new("RGBA", big.size, (120, 140, 150, 255))
    tint.putalpha(mask)
    big = Image.alpha_composite(big, tint)
    out = big.resize((W, H), Image.LANCZOS)
    path = Path(__file__).with_name("arrow.png")
    out.save(path)
    print("wrote", path)


if __name__ == "__main__":
    main()
