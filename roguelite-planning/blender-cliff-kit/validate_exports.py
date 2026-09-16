"""Headlessly re-import generated cliff exports and write validation-report.json."""

from __future__ import annotations

import json
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parent
EXPECTED_STEMS = {
    "cliff-straight",
    "cliff-curve45",
    "cliff-curve22",
    "cliff-pillarmesa",
    "cliff-steppedterrace",
    "cliff-arch",
    "sample-circular-arena",
}


def clear_objects():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def stats():
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    return {
        "mesh_objects": len(meshes),
        "vertices": sum(len(obj.data.vertices) for obj in meshes),
        "triangles": sum(sum(max(0, len(poly.vertices) - 2) for poly in obj.data.polygons) for obj in meshes),
    }


report = {"blender_version": bpy.app.version_string, "files": {}, "passed": True, "missing": []}
for extension, subdir in (("fbx", "fbx"), ("glb", "glb")):
    folder = ROOT / "exports" / subdir
    present = {path.stem for path in folder.glob(f"*.{extension}")}
    missing = sorted(EXPECTED_STEMS - present)
    report["missing"].extend([f"{subdir}/{name}.{extension}" for name in missing])
    for path in sorted(folder.glob(f"*.{extension}")):
        clear_objects()
        if extension == "fbx":
            bpy.ops.import_scene.fbx(filepath=str(path))
        else:
            bpy.ops.import_scene.gltf(filepath=str(path))
        current = stats()
        current["bytes"] = path.stat().st_size
        current["ok"] = current["mesh_objects"] > 0 and current["triangles"] > 0 and current["bytes"] > 0
        report["files"][str(path.relative_to(ROOT))] = current
        report["passed"] = report["passed"] and current["ok"]

report["passed"] = report["passed"] and not report["missing"]
(ROOT / "validation-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
if not report["passed"]:
    raise SystemExit(1)

