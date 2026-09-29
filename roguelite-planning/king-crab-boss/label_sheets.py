"""Label the contact sheets the generator tiles (system python + Pillow).

    python label_sheets.py

Reads the unlabelled copies the generator keeps in _work/raw_<sheet>.png and
writes labelled sheets to previews/, so it can be re-run without stacking
labels. Run it after build_king_crab.py.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
try:
    F = ImageFont.truetype('arial.ttf', 26)
    S = ImageFont.truetype('arial.ttf', 20)
except OSError:
    F = S = ImageFont.load_default()

ROM_FRAMES = list(range(1, 145, 12))
SHEETS = {
    'AttackCheck_Claws': {
        'cols': 5, 'rows': 3,
        'title': 'Claw attack check (posed KingCrab_Rig, BVH clearance in attack-check.json)',
        'cell': lambda r, c: ['rest guard', 'windup', 'impact (jab)', 'pincer open', 'snapped shut'][c]
        + ('  |  ' + ['front', 'three-quarter', 'crusher close-up'][r] if c == 0 else ''),
    },
    'RigTest_ROM': {
        'cols': 4, 'rows': 3,
        'title': 'RigTest_ROM (24 fps, 144 frames): tripod stepping, body bob/tilt, claws, eyes, brows, mouth',
        'cell': lambda r, c: f'frame {ROM_FRAMES[r * 4 + c]}',
    },
    'RigTest_Joints': {
        'cols': 2, 'rows': 2,
        'title': 'Joint close-ups at ROM extremes (rigid exoskeleton, cuffed joints)',
        'cell': lambda r, c: ['right legs, tripod A lifted (f13)', 'left legs, tripod B lifted (f37)',
                              'crusher swung, fingers open (f25)', 'cutter raised (f19)'][r * 2 + c],
    },
    'Turnaround': {
        'cols': 3, 'rows': 2,
        'title': 'Turnaround, rest pose, orthographic, 27-stud frame',
        'cell': lambda r, c: (['front', 'three-quarter', 'side (crab left)', 'back', 'top', ''][r * 3 + c]),
    },
}

for name, spec in SHEETS.items():
    src = HERE / '_work' / f'raw_{name}.png'
    if not src.exists():
        print('missing', src)
        continue
    im = Image.open(src).convert('RGB')
    cw, ch = im.width // spec['cols'], im.height // spec['rows']
    out = Image.new('RGB', (im.width, im.height + 50), (22, 24, 28))
    out.paste(im, (0, 50))
    d = ImageDraw.Draw(out)
    d.text((14, 12), spec['title'], fill=(235, 235, 235), font=F)
    for r in range(spec['rows']):
        for c in range(spec['cols']):
            label = spec['cell'](r, c)
            if not label:
                continue
            x, y = c * cw + 10, 50 + r * ch + 8
            tw = d.textlength(label, font=S)
            d.rectangle((x - 4, y - 3, x + tw + 6, y + 25), fill=(0, 0, 0))
            d.text((x, y), label, fill=(255, 255, 255), font=S)
    out.save(HERE / 'previews' / f'{name}.png')
    print('labelled', name)
