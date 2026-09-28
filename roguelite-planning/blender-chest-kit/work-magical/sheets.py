"""python sheets.py <tag>: comparison sheets from ref_render outputs.
cmp_<tag>.png   painting chest crop | ours closed | ours open   (same fitted-camera frame)
skull_<tag>.png painting skull box x3 | ours skull box x3 (box follows our skull)"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REF = Image.open(r"C:/Users/Jeremiah/AppData/Local/Temp/claude/C--Users-Jeremiah-Documents-ChatGPT-Roblox/26e128a1-a54f-4e27-9b85-1ee1e3c3e2cf/images/19.webp").convert("RGB")
t = sys.argv[1]
BOX = (560, 60, 1400, 980)


def row(ims, H, labels, out):
    ims = [im.resize((int(im.width * H / im.height), H), Image.LANCZOS) for im in ims]
    sheet = Image.new("RGB", (sum(i.width for i in ims) + 10 * (len(ims) - 1), H), (20, 20, 24))
    x = 0
    d = ImageDraw.Draw(sheet)
    for im, lb in zip(ims, labels):
        sheet.paste(im, (x, 0))
        d.text((x + 8, 8), lb, fill=(255, 255, 255))
        x += im.width + 10
    sheet.save(HERE / out)


closed = Image.open(HERE / f"ref_{t}.png").convert("RGB").crop(BOX)
opened = Image.open(HERE / f"ref_{t}_open.png").convert("RGB").crop(BOX)
row([REF.crop(BOX), closed, opened], 900, ["reference", "ours (fitted camera)", "ours open"], f"cmp_{t}.png")
row([REF.crop((900, 235, 1180, 500)).resize((840, 795), Image.LANCZOS), Image.open(HERE / f"ref_{t}_skull.png").convert("RGB")], 795,
    ["reference skull", "ours, same camera"], f"skull_{t}.png")
row([Image.open(HERE / f"ref_{t}_open_side.png").convert("RGB"), Image.open(HERE / f"ref_{t}_open_back.png").convert("RGB")], 700,
    ["open, side (ortho)", "open, back 3/4"], f"hinge_{t}.png")
print("sheets", t)
