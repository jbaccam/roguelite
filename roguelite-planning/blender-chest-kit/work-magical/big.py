"""python big.py : painting skull area | lab clay | lab colour, wider framing, one row -> _lab_big.png"""
from pathlib import Path
from PIL import Image
HERE = Path(__file__).resolve().parent
REF = r"C:/Users/Jeremiah/AppData/Local/Temp/claude/C--Users-Jeremiah-Documents-ChatGPT-Roblox/26e128a1-a54f-4e27-9b85-1ee1e3c3e2cf/images/19.webp"
ims = [Image.open(REF).convert("RGB").crop((900, 235, 1180, 500)).resize((840, 795), Image.LANCZOS),
       Image.open(HERE / "_lab_34clay.png").convert("RGB"), Image.open(HERE / "_lab_34col.png").convert("RGB")]
H = 600
ims = [im.resize((int(im.width * H / im.height), H)) for im in ims]
s = Image.new("RGB", (sum(i.width for i in ims) + 16, H))
x = 0
for im in ims:
    s.paste(im, (x, 0)); x += im.width + 8
s.save(HERE / "_lab_big.png")
