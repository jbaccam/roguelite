"""Caption the review contact sheets (system python + Pillow).

    python label_sheets.py

Reads _work/sheet_labels.json (tile layout and captions written by
build_dragon.py) and draws a caption bar into each tile of the sheets in
previews/. Run it after build_dragon.py (full build or DRAGON_STAGE=previews).
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
spec = json.loads((HERE / '_work' / 'sheet_labels.json').read_text())
try:
    FONT = ImageFont.truetype('arial.ttf', 20)
except Exception:  # noqa: BLE001
    FONT = ImageFont.load_default()
GAP = 6
for sheet, s in spec.items():
    p = HERE / 'previews' / sheet
    im = Image.open(p).convert('RGB')
    d = ImageDraw.Draw(im)
    w, h = s['tile']
    for i, lab in enumerate(s['labels']):
        r, c = divmod(i, s['cols'])
        x = GAP + c * (w + GAP)
        y = GAP + r * (h + GAP)
        d.rectangle((x, y, x + w, y + 30), fill=(16, 16, 20))
        d.text((x + 8, y + 5), lab, fill=(235, 235, 235), font=FONT)
    im.save(p)
    print('labelled', sheet, len(s['labels']))
