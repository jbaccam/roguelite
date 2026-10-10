"""Compose the Workbench frames rendered by animate_game.py into the preview sheets.
System python + Pillow:  python compose_previews.py
Writes previews/GameClips.png, Attack_ClawRake.png, Attack_Howl.png, Charge.png.
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
FR = OUT / '_work' / 'frames'
PREV = OUT / 'previews'
FPS = 24
CELL = 200
try:
    FONT = ImageFont.truetype('arialbd.ttf', 15)
    SMALL = ImageFont.truetype('arial.ttf', 12)
except OSError:
    FONT = SMALL = ImageFont.load_default()


def cell(clip, f, view, label=None):
    im = Image.open(FR / f'{clip}_{f:02d}_{view}.png').convert('RGB').resize((CELL, CELL), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    d.text((6, CELL - 18), label or f'{f / FPS:.2f}s (f{f})', fill=(20, 20, 24), font=SMALL)
    return im


def sheet(rows, path, title):
    cols = max(len(r[1]) for r in rows)
    lw = 110
    W = lw + cols * CELL
    H = 34 + len(rows) * CELL
    out = Image.new('RGB', (W, H), (236, 238, 242))
    d = ImageDraw.Draw(out)
    d.text((10, 8), title, fill=(20, 20, 24), font=FONT)
    for i, (label, cells) in enumerate(rows):
        y = 34 + i * CELL
        d.text((8, y + CELL // 2 - 8), label, fill=(20, 20, 24), font=FONT)
        for j, im in enumerate(cells):
            out.paste(im, (lw + j * CELL, y))
    out.save(path)
    print('wrote', path, out.size)


SHEET = json.loads((FR / 'sheet.json').read_text())['sheet']
order = ['Idle', 'Walk', 'Hit', 'Death', 'Howl', 'ChargeStart', 'ChargeRun', 'ClawRake']
sheet([(c, [cell(c, f, 'tq') for f in SHEET[c]]) for c in order], PREV / 'GameClips.png',
      'Blood Moon Alpha - game clips (front 3/4, Workbench, 24 fps)')
for clip, fs, names in (('ClawRake', [7, 12, 20], ['windup', 'impact', 'recovery']), ('Howl', [8, 24, 48], ['crouch', 'peak (impact)', 'recovery'])):
    rows = [(v.capitalize(), [cell(clip, f, v, f'{n} {f / FPS:.2f}s') for f, n in zip(fs, names)]) for v in ('front', 'side')]
    sheet(rows, PREV / f'Attack_{clip}.png', f'{clip}: windup / impact / recovery')
rows = []
for view in ('side', 'tq'):
    cells = [cell('ChargeStart', f, view, f'Start {f / FPS:.2f}s') for f in [0, 6, 10, 17]]
    cells += [cell('ChargeRun', f, view, f'Run {f / FPS:.2f}s') for f in [0, 3, 6, 9]]
    rows.append(('Side' if view == 'side' else '3/4', cells))
sheet(rows, PREV / 'Charge.png', 'ChargeStart (coil, hand brushes the ground) -> ChargeRun loop')
