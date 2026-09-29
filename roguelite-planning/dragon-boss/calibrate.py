"""Fold the last colour probe into build_dragon.py's CALIBRATION table.

    python calibrate.py [compare-report.json] [--damp=0.8]

Probes map onto paint recipes (several probes may inform one recipe; their
per-channel ratios are combined as a geometric mean). new_gain = old_gain *
ratio ** damp per channel, where ratio = reference / render in linear light
(from compare_reference.py). Gains are clamped to [0.2, 6.0]; the generator
clamps albedo to 1.0.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
args = [a for a in sys.argv[1:] if not a.startswith('--')]
rep = Path(args[0]) if args else HERE / '_work' / 'cmp' / 'compare-report.json'
damp = 0.8
for a in sys.argv[1:]:
    if a.startswith('--damp='):
        damp = float(a.split('=')[1])
PROBE_TO_RECIPE = {
    'skin': ['skin_lit', 'skin_shadow', 'tail_skin'],
    'skin_head': ['skin_head'],
    'belly': ['belly'],
    'jaw': ['jaw'],
    'membrane': ['membrane'],
    'wingbone': ['wingbone'],
    'obsidian': ['obsidian', 'obsidian_horn'],
}
probes = json.loads(rep.read_text())['colour_probes']
gen = HERE / 'build_dragon.py'
src = gen.read_text()
block = re.search(r'CALIBRATION = \{\n(.*?)\n\}', src, re.S)
out = []
for ln in block.group(1).splitlines():
    m = re.match(r"\s*'([\w]+)': \(([\d.]+), ([\d.]+), ([\d.]+)\),", ln)
    if not m:
        out.append(ln)
        continue
    key = m.group(1)
    g = np.array([float(m.group(i)) for i in (2, 3, 4)])
    ratios = [probes[p]['ratio_ref_over_render'] for p in PROBE_TO_RECIPE.get(key, [])
              if p in probes and probes[p].get('ratio_ref_over_render')]
    if ratios:
        r = np.exp(np.mean(np.log(np.array(ratios)), axis=0))
        g = np.clip(g * r ** damp, 0.2, 6.0)
        print(f'{key:10s} ratio {np.round(r, 3)} -> gain {np.round(g, 3)}')
    out.append(f"    '{key}': ({g[0]:.3f}, {g[1]:.3f}, {g[2]:.3f}),")
src = src[:block.start(1)] + '\n'.join(out) + src[block.end(1):]
gen.write_text(src)
