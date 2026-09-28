"""Side-by-side: reference crop | our render(s).   python compose.py out.png render_a.png [render_b.png ...]"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REF = Path(r"C:/Users/Jeremiah/AppData/Local/Temp/claude/C--Users-Jeremiah-Documents-ChatGPT-Roblox/26e128a1-a54f-4e27-9b85-1ee1e3c3e2cf/images/19.webp")

out = HERE / sys.argv[1]
ims = [Image.open(REF).convert("RGB").crop((580, 130, 1380, 950))] + [Image.open(HERE / a).convert("RGB") for a in sys.argv[2:]]
H = 820
ims = [im.resize((int(im.width * H / im.height), H)) for im in ims]
sheet = Image.new("RGB", (sum(im.width for im in ims) + 10 * (len(ims) - 1), H), (20, 20, 24))
x = 0
for im in ims:
    sheet.paste(im, (x, 0))
    x += im.width + 10
d = ImageDraw.Draw(sheet)
d.text((10, 10), "reference", fill=(255, 255, 255))
d.text((ims[0].width + 20, 10), "ours", fill=(255, 255, 255))
sheet.save(out)
print("wrote", out)
