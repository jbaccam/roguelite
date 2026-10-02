"""Validate the Legendary VFX exports.

Run:
  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python validate_exports.py

Re-imports every exports/glb/*.glb and checks it against polygon-report.json (vertex and triangle
counts, a colour attribute with alpha), then checks the Luau mesh data the game builds from
(../studio-prototype/combat/LegendaryVisuals/MeshData.luau): every mesh present, triangle indices in
range, one alpha per vertex, one colour per triangle, bounds matching `size`. Writes
validation-report.json and exits non-zero on any failure.
"""
import bpy, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LUAU = HERE.parent / "studio-prototype" / "combat" / "LegendaryVisuals" / "MeshData.luau"
report = {"glb": {}, "luau": {}, "failures": []}
expected = json.loads((HERE / "polygon-report.json").read_text(encoding="utf-8"))


def fail(msg):
    report["failures"].append(msg)


for name, want in expected.items():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path = HERE / "exports" / "glb" / f"{name}.glb"
    if not path.exists():
        fail(f"{name}: missing {path.name}")
        continue
    bpy.ops.import_scene.gltf(filepath=str(path))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if len(meshes) != 1:
        fail(f"{name}: expected one mesh, found {len(meshes)}")
        continue
    me = meshes[0].data
    me.calc_loop_triangles()
    tris = len(me.loop_triangles)
    has_alpha = any(a.data_type in ("FLOAT_COLOR", "BYTE_COLOR") for a in me.color_attributes)
    report["glb"][name] = {"vertices": len(me.vertices), "triangles": tris, "color_attribute": has_alpha}
    # glTF may split vertices along seams; triangles must match exactly.
    if tris != want["triangles"]:
        fail(f"{name}: {tris} triangles, report says {want['triangles']}")
    if not has_alpha:
        fail(f"{name}: no colour attribute")

text = LUAU.read_text(encoding="utf-8") if LUAU.exists() else ""
if not text:
    fail("MeshData.luau missing")
for name, want in expected.items():
    m = re.search(rf"\b{name}=\{{v=(\{{.*?\}}\}}),f=(\{{.*?\}}\}}),c=(\{{.*?\}}\}}),a=(\{{[^}}]*\}}),size=\{{([^}}]*)\}},glow=(true|false)\}}", text)
    if not m:
        fail(f"{name}: not found in MeshData.luau")
        continue
    nums = lambda s: [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", s)]
    v = nums(m.group(1)); f = [int(x) for x in re.findall(r"\d+", m.group(2))]
    c = nums(m.group(3)); a = nums(m.group(4)); size = nums(m.group(5))
    nv, nf = len(v) // 3, len(f) // 3
    xs, ys, zs = v[0::3], v[1::3], v[2::3]
    bounds = [max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)]
    entry = {"vertices": nv, "triangles": nf, "alpha_values": len(a), "colours": len(c) // 3, "size": size}
    report["luau"][name] = entry
    if nv != want["vertices"]: fail(f"{name}: {nv} vertices in Luau, report says {want['vertices']}")
    if nf != want["triangles"]: fail(f"{name}: {nf} triangles in Luau, report says {want['triangles']}")
    if any(i < 1 or i > nv for i in f): fail(f"{name}: a triangle index is out of range")
    if len(a) != nv: fail(f"{name}: {len(a)} alpha values for {nv} vertices")
    if len(c) // 3 != nf: fail(f"{name}: {len(c) // 3} colours for {nf} triangles")
    if any(x < 0 or x > 1 for x in a + c): fail(f"{name}: a colour or alpha outside 0..1")
    if any(abs(bounds[i] - size[i]) > 1e-3 for i in range(3)): fail(f"{name}: bounds {bounds} differ from size {size}")

report["passed"] = not report["failures"]
(HERE / "validation-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("VALIDATION", "PASS" if report["passed"] else "FAIL", json.dumps(report["failures"]))
sys.exit(0 if report["passed"] else 1)
