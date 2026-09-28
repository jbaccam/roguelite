"""Approximate the map-select screen from a real Blender hero render.

python make_menu_mock.py pinevalley "PINE VALLEY" [fog_hex]

Blur + fog wash + serif title, like the reference menu screenshots. This is a
presentation mock of how the island reads as a background; it is not UI.
"""
import sys
from pathlib import Path
from PIL import Image, ImageFilter, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
stem, title = sys.argv[1], sys.argv[2]
fog = sys.argv[3] if len(sys.argv) > 3 else "#9fb6c8"

src = Image.open(HERE / "previews" / f"{stem}-hero.png").convert("RGB")
blur = src.filter(ImageFilter.GaussianBlur(7))
wash = Image.new("RGB", src.size, fog)
img = Image.blend(blur, wash, 0.38)

draw = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("C:/Windows/Fonts/georgiab.ttf", 120)
except OSError:
    font = ImageFont.load_default()
w = draw.textlength(title, font=font)
x, y = (img.width - w) / 2, 150
draw.text((x + 4, y + 5), title, font=font, fill=(60, 70, 85))
draw.text((x, y), title, font=font, fill=(236, 236, 232))
out = HERE / "previews" / f"{stem}-menu-mock.png"
img.save(out)
print(out)
