"""python lab_sheet.py <tag> : reference skull crop | lab renders, one row -> lab_<tag>.png"""
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
REF = Path(r"C:/Users/Jeremiah/AppData/Local/Temp/claude/C--Users-Jeremiah-Documents-ChatGPT-Roblox/26e128a1-a54f-4e27-9b85-1ee1e3c3e2cf/images/19.webp")
tag = sys.argv[1]
import json
from PIL import ImageDraw
ref = Image.open(REF).convert("RGB").crop((900, 235, 1180, 500)).resize((840, 795), Image.LANCZOS)
TGT = {"dome_top": (390, 51), "eye_r": (420, 486), "eye_l": (660, 426), "nose": (576, 525), "jaw": (525, 636)}
keys = json.loads((HERE / "_lab_keys.json").read_text())
ims = [ref]

ims += [Image.open(HERE / f"_lab_{n}.png").convert("RGB") for n in ("34clay", "34col", "front", "side", "top")]
for im, pts, c in ((ims[0], TGT, (255, 60, 60)), (ims[1], keys, (60, 200, 255)), (ims[1], TGT, (255, 60, 60))):
    dr = ImageDraw.Draw(im)
    for k, (x, y) in pts.items():
        dr.ellipse((x - 7, y - 7, x + 7, y + 7), outline=c, width=3)
H = 420
ims = [im.resize((int(im.width * H / im.height), H)) for im in ims]
sheet = Image.new("RGB", (sum(i.width for i in ims) + 8 * (len(ims) - 1), H), (20, 20, 24))
x = 0
for im in ims:
    sheet.paste(im, (x, 0))
    x += im.width + 8
sheet.save(HERE / f"lab_{tag}.png")
print("wrote", HERE / f"lab_{tag}.png")
