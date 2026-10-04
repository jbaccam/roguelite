"""Fold the colour-probe ratios from a compare report into calibration.json.

    python calibrate.py [report=_work/cmp/compare-report.json] [damp=0.85]

Each paint material's gain in the CALIBRATION table is multiplied by the
geometric mean of the reference/render linear ratios of the probe regions that
show it, raised to `damp` and clamped per step, so the loop converges without
overshooting. The build reads calibration.json, so the eyedropped palette in
hb_paint.py stays readable and the loop stays re-measurable.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
# Probes used per material. Left out on purpose (recorded in the README): the
# suspender, buckle and sash boxes do not land on those parts in the render (the
# straps and buckles sit a few pixels off the reference's, and the sash is in the
# belly's shadow); skin_head and skin_deltoid_L are dominated by the reference's
# strong key light and by a wound.
MAP = {
    'skin': ['skin_belly', 'skin_arm_R', 'skin_forearm_L', 'skin_foot_L'],
    'shirt': ['shirt'],
    'iron': ['hammer_iron'],
    'trousers': ['trousers'],
    'wood': ['haft_wood'],
    'band': ['haft_band'],
    'tooth': ['teeth'],
}


def main():
    args = dict(a.split('=', 1) for a in sys.argv[1:])
    rep = json.loads((HERE / args.get('report', '_work/cmp/compare-report.json')).read_text())
    damp = float(args.get('damp', 0.85))
    cal_p = HERE / 'calibration.json'
    cal = json.loads(cal_p.read_text())
    step = {}
    for key, probes in MAP.items():
        rs = [rep['probes'][p]['ratio_ref_over_render'] for p in probes
              if 'ratio_ref_over_render' in rep['probes'].get(p, {})]
        if not rs:
            continue
        r = np.exp(np.mean(np.log(np.array(rs)), axis=0))
        r = np.clip(r ** damp, 0.6, 1.6)
        g = np.array(cal['CALIBRATION'].get(key, [1, 1, 1])) * r
        cal['CALIBRATION'][key] = [round(float(v), 4) for v in g]
        step[key] = [round(float(v), 3) for v in r]
    cal['history'].append({'iou': rep['silhouette_iou'], 'step': step})
    cal_p.write_text(json.dumps(cal, indent=1))
    print(json.dumps(step, indent=1))


if __name__ == '__main__':
    main()
