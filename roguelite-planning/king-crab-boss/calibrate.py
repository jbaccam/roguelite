"""Fold the last colour probe into the generator's CALIBRATION table.

    python calibrate.py [compare-report.json] [--damp=0.8]

new_gain = old_gain * ratio ** damp, per channel, per material_section key.
The ratio is reference/render in linear light from compare_reference.py.
Gains are clamped to [0.3, 5.0]; the generator also clamps albedo to 1.0.
"""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
args = [a for a in sys.argv[1:] if not a.startswith('--')]
rep = Path(args[0]) if args else HERE / 'previews' / 'compare-report.json'
damp = 0.8
for a in sys.argv[1:]:
    if a.startswith('--damp='):
        damp = float(a.split('=')[1])
probes = json.loads(rep.read_text())['colour_probes']
gen = HERE / 'build_king_crab.py'
src = gen.read_text()
block = re.search(r'CALIBRATION = \{\n(.*?)\n\}', src, re.S)
lines = block.group(1).splitlines()
out = []
for ln in lines:
    m = re.match(r"\s*'([\w]+)': \(([\d.]+), ([\d.]+), ([\d.]+)\),", ln)
    if not m:
        out.append(ln)
        continue
    key = m.group(1)
    g = [float(m.group(i)) for i in (2, 3, 4)]
    r = probes.get(key, {}).get('ratio_ref_over_render')
    if r:
        g = [min(5.0, max(0.3, gi * ri ** damp)) for gi, ri in zip(g, r)]
    out.append(f"    '{key}': ({g[0]:.3f}, {g[1]:.3f}, {g[2]:.3f}),")
    print(key, r, '->', [round(v, 3) for v in g])
src = src[:block.start(1)] + '\n'.join(out) + src[block.end(1):]
gen.write_text(src)
