"""Re-import each exported chest and check it against polygon-report-<tier>.json.

    blender --background --python validate_exports.py              # every built tier
    blender --background --python validate_exports.py -- silver    # one tier

Checks per tier: FBX and GLB both hold every part in the report, triangle counts
match, dimensions match within 1%, every UV sits inside 0-1, no zero-area faces.
Writes validation-report-<tier>.json. Blender-verified only; says nothing about Studio.
"""
import json
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parent
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
TIERS = ARGS or sorted(f.stem.replace("polygon-report-", "") for f in ROOT.glob("polygon-report-*.json"))


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if path.suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    else:
        bpy.ops.import_scene.gltf(filepath=str(path))
    return {o.name.split(".")[0]: o for o in bpy.context.scene.objects if o.type == "MESH"}


for tier in TIERS:
    rep = json.loads((ROOT / f"polygon-report-{tier}.json").read_text())
    results = {}
    for path in (ROOT / "exports/fbx" / f"chest-{tier}.fbx", ROOT / "exports/glb" / f"chest-{tier}.glb"):
        problems = []
        objs = load(path)
        for name, want in rep["parts"].items():
            o = objs.get(name)
            if not o:
                problems.append(f"missing {name}")
                continue
            m = o.data
            m.calc_loop_triangles()
            if len(m.loop_triangles) != want["triangles"]:
                problems.append(f"{name}: {len(m.loop_triangles)} tris, report says {want['triangles']}")
            dims = sorted(round(v, 3) for v in o.dimensions)
            ref = sorted(want["dimensions_studs"])
            if any(abs(a - b) > max(0.01, 0.01 * b) for a, b in zip(dims, ref)):
                problems.append(f"{name}: dimensions {dims} vs {ref}")
            uv = m.uv_layers.active
            if uv and any(not (-1e-4 <= d.uv.x <= 1.0001 and -1e-4 <= d.uv.y <= 1.0001) for d in uv.data):
                problems.append(f"{name}: UV outside 0-1")
            if any(p.area < 1e-7 for p in m.polygons):
                problems.append(f"{name}: zero-area faces")
        results[path.suffix[1:]] = {"ok": not problems, "problems": problems}
    (ROOT / f"validation-report-{tier}.json").write_text(json.dumps(results, indent=2))
    print("VALIDATION", tier, json.dumps(results), flush=True)
