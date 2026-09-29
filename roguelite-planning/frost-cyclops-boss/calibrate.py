"""Fold the colour-probe ratios from compare-report.json into calibration.json.

    python calibrate.py [report=_work/cmp/compare-report.json] [damp=0.85]

Each paint material's gain is multiplied by the geometric mean of the
reference/render linear ratios of the probe regions that show it, raised to
`damp` and clamped per step, so the loop converges without overshooting. The
build reads calibration.json (the CALIBRATION table), so the eyedropped palette
in fc_paint.py stays readable and the loop stays re-measurable.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
MAP = {
    'skin': ['skin_belly', 'skin_arm_R', 'skin_arm_L', 'skin_leg_L', 'skin_head'],
    'lid': ['skin_belly', 'skin_arm_R', 'skin_arm_L', 'skin_leg_L', 'skin_head'],
    'nail': ['toenails_skin_L'],
    'fur': ['fur_mantle'],
    'leather': ['leather_wrap', 'leather_belt'],
    'loin': ['loincloth'],
    'buckle': ['buckle_stone'],
    'stone': ['club_stone'],
    'wood': ['club_haft'],
    'strap': ['club_strap'],
    'tooth': ['tusk'],
    'eye': ['eye_sclera'],
    'iris': ['eye_iris'],
}


def main():
    args = dict(a.split('=', 1) for a in sys.argv[1:])
    rep = json.loads((HERE / args.get('report', '_work/cmp/compare-report.json')).read_text())
    damp = float(args.get('damp', 0.85))
    cal_p = HERE / 'calibration.json'
    cal = json.loads(cal_p.read_text()) if cal_p.exists() else {'gains': {}, 'history': []}
    step = {}
    for key, probes in MAP.items():
        rs = [rep['probes'][p]['ratio_ref_over_render'] for p in probes
              if 'ratio_ref_over_render' in rep['probes'].get(p, {})]
        if not rs:
            continue
        r = np.exp(np.mean(np.log(np.array(rs)), axis=0))
        r = np.clip(r ** damp, 0.6, 1.6)
        g = np.array(cal['gains'].get(key, [1, 1, 1])) * r
        cal['gains'][key] = [round(float(v), 4) for v in g]
        step[key] = [round(float(v), 3) for v in r]
    cal['history'].append({'iou': rep['silhouette_iou'], 'step': step})
    cal_p.write_text(json.dumps(cal, indent=1))
    print(json.dumps(step, indent=1))


if __name__ == '__main__':
    main()
