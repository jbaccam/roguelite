"""Re-import the exported Egg Merchant and check it; render the pose check and the sheet.

    blender --background --python validate_merchant.py

Checks (FBX and GLB, each imported into a fresh scene):
  * exactly the 11 part names, nothing else
  * triangle counts match polygon-report-merchant.json; each part < 20k, total <= 18k
  * world-space bounding boxes match the report (proves 1:1 scale and placement)
  * UVs inside 0-1, no zero-area triangles, one UV map
  * object transforms (GLB must be identity; FBX transforms are listed as imported)
Pose check (on the re-imported GLB meshes, using the recorded pivots only):
  right upper arm raised 80 deg (out, 25 deg toward the front), elbow +70 deg with the forearm
  twisted palm-up; head turned 20 deg toward his right. Renders previews/merchant-pose-check.png
  and tiles every preview into previews/merchant-sheet.png.
Writes validation-report-merchant.json. Blender-verified only; says nothing about Studio.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parent
REP = json.loads((ROOT / "polygon-report-merchant.json").read_text())
NAMES = set(REP["parts"])
J = {k: Vector(v["pivot"]) for k, v in REP["joints_blender"].items()}
SPLAY = REP["rest_pose"]["arm_splay_deg"]


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if path.suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    else:
        bpy.ops.import_scene.gltf(filepath=str(path))
    bpy.context.view_layer.update()
    return {o.name.split(".")[0]: o for o in bpy.context.scene.objects if o.type == "MESH"}, \
        [o.name for o in bpy.context.scene.objects]


def is_identity(m, tol=1e-4):
    return all(abs(m[i][j] - (1.0 if i == j else 0.0)) < tol for i in range(4) for j in range(4))


def check(path):
    objs, every = load(path)
    problems, transforms, total = [], {}, 0
    extra = sorted(set(objs) - NAMES)
    missing = sorted(NAMES - set(objs))
    if extra:
        problems.append(f"unexpected meshes {extra}")
    if missing:
        problems.append(f"missing {missing}")
    for name in sorted(NAMES & set(objs)):
        o = objs[name]
        want = REP["parts"][name]
        m = o.data
        m.calc_loop_triangles()
        n = len(m.loop_triangles)
        total += n
        if n != want["triangles"]:
            problems.append(f"{name}: {n} tris, report says {want['triangles']}")
        if n >= 20000:
            problems.append(f"{name}: {n} tris >= 20k")
        ws = [o.matrix_world @ v.co for v in m.vertices]
        lo = [min(v[i] for v in ws) for i in range(3)]
        hi = [max(v[i] for v in ws) for i in range(3)]
        for a, b, tag in ((lo, want["bbox_min"], "min"), (hi, want["bbox_max"], "max")):
            if any(abs(x - y) > 0.005 for x, y in zip(a, b)):
                problems.append(f"{name}: bbox {tag} {[round(x, 3) for x in a]} vs {b}")
        if len(m.uv_layers) != 1:
            problems.append(f"{name}: {len(m.uv_layers)} UV maps")
        uv = m.uv_layers.active
        if not uv or any(not (-1e-4 <= d.uv.x <= 1.0001 and -1e-4 <= d.uv.y <= 1.0001) for d in uv.data):
            problems.append(f"{name}: UV outside 0-1")
        if any(t.area < 1e-8 for t in m.loop_triangles):
            problems.append(f"{name}: zero-area triangles")
        ident = is_identity(o.matrix_world)
        transforms[name] = "identity" if ident else [[round(c, 4) for c in row] for row in o.matrix_world]
        if path.suffix == ".glb" and not ident:
            problems.append(f"{name}: transform not identity")
    if total > 18000:
        problems.append(f"total {total} tris > 18k")
    return {"ok": not problems, "problems": problems, "total_triangles": total, "transforms": transforms,
            "scene_objects": every}


results = {}
for path in (ROOT / "exports/fbx/merchant.fbx", ROOT / "exports/glb/merchant.glb"):
    results[path.suffix[1:]] = check(path)
    print("VALIDATION", path.name, results[path.suffix[1:]]["ok"], results[path.suffix[1:]]["problems"], flush=True)

# ---------------------------------------------------------------------------
# pose check on the GLB meshes (left in the scene by the last load)
# ---------------------------------------------------------------------------
objs, _ = load(ROOT / "exports/glb/merchant.glb")


def about(pivot, R):
    R4 = R.to_matrix().to_4x4() if isinstance(R, Quaternion) else R
    return Matrix.Translation(pivot) @ R4 @ Matrix.Translation(-pivot)


side = -1                                                       # his right arm (-X)
rest_up = Matrix.Rotation(math.radians(-SPLAY * side), 3, "Y")  # build-time splay
a0 = rest_up @ Vector((0, 0, -1))
gamma = math.radians(25)
d = Vector((-math.cos(gamma), -math.sin(gamma), 0))
a1 = Vector((0, 0, -1)) * math.cos(math.radians(80)) + d * math.sin(math.radians(80))
Rs = a0.rotation_difference(a1)
M_up = about(J["Shoulder_R"], Rs)
hinge = (rest_up @ Vector((1, 0, 0))).normalized()
Rflex = Quaternion(hinge, math.radians(-70))
elbow_rest = J["Elbow_R"]
bend_r = REP["rest_pose"]["elbow_bend_deg"]["R"]
fore_rest = (rest_up @ (Matrix.Rotation(math.radians(-bend_r), 3, "X") @ Vector((0, 0, -1)))).normalized()
palm_rest = (rest_up @ Vector((1, 0, 0))).normalized()          # right palm faces the body (+X)
best = None
for k in range(72):
    phi = math.radians(-180 + 5 * k)
    Rt = Quaternion(Rflex @ fore_rest, phi) @ Rflex
    palm = (Rs @ Rt) @ palm_rest
    if best is None or palm.z > best[0]:
        best = (palm.z, phi, Rt)
M_low = M_up @ about(elbow_rest, best[2])
objs["Merchant_UpperArm_R"].matrix_world = M_up
objs["Merchant_LowerArm_R"].matrix_world = M_low
objs["Merchant_Head"].matrix_world = about(J["Neck"], Quaternion((0, 0, 1), math.radians(-20)))
results["pose_check"] = {
    "shoulder_R": {"swing_deg": 80, "toward": "out, 25 deg to the front", "quaternion_wxyz": [round(c, 5) for c in Rs]},
    "elbow_R": {"flex_deg": 70, "twist_deg_for_palm_up": round(math.degrees(best[1]), 1), "palm_up_dot": round(best[0], 3),
                "quaternion_wxyz_in_rest_frame": [round(c, 5) for c in best[2]]},
    "neck": {"turn_deg": 20, "toward": "his right (-X blender / +X studio)"},
    "render": "previews/merchant-pose-check.png",
}

scene = bpy.context.scene
for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        scene.render.engine = engine
        break
    except TypeError:
        continue
scene.render.resolution_x = scene.render.resolution_y = 1024
scene.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("StudioGrey")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.50, 0.50, 0.52, 1)
scene.world = world
sun = bpy.data.objects.new("Preview_Sun", bpy.data.lights.new("Preview_Sun", "SUN"))
sun.data.energy, sun.data.angle, sun.data.color = 3.0, math.radians(14), (1.0, 0.96, 0.9)
sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
scene.collection.objects.link(sun)
fm = bpy.data.meshes.new("Preview_Floor")
fm.from_pydata([(14 * math.cos(2 * math.pi * k / 48), 14 * math.sin(2 * math.pi * k / 48), 0) for k in range(48)], [], [list(range(48))])
mat = bpy.data.materials.new("Preview_Floor")
mat.use_nodes = True
mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.36, 0.36, 0.38, 1)
fm.materials.append(mat)
scene.collection.objects.link(bpy.data.objects.new("Preview_Floor", fm))
cam = bpy.data.objects.new("Preview_Cam", bpy.data.cameras.new("Preview_Cam"))
scene.collection.objects.link(cam)
scene.camera = cam
cam.data.lens = 80
cam.location = Vector((-13.5, -14.5, 6.6))
cam.rotation_euler = (Vector((-0.7, -0.2, 3.9)) - cam.location).to_track_quat("-Z", "Y").to_euler()
scene.render.filepath = str(ROOT / "previews" / "merchant-pose-check.png")
bpy.ops.render.render(write_still=True)

# ---------------------------------------------------------------------------
# sheet: every preview tiled 3 x 2
# ---------------------------------------------------------------------------
import numpy as np  # noqa: E402

tiles = []
for name in ("front", "threeq", "back", "side", "face", "pose-check"):
    im = bpy.data.images.load(str(ROOT / "previews" / f"merchant-{name}.png"))
    w, h = im.size
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]
    a = a.reshape(512, h // 512, 512, w // 512, 4).mean(axis=(1, 3))
    a[..., 3] = 1.0
    tiles.append(a)
canvas = np.zeros((1024, 1536, 4), np.float32)
for i, t in enumerate(tiles):
    r, c = divmod(i, 3)
    canvas[r * 512:(r + 1) * 512, c * 512:(c + 1) * 512] = t
img = bpy.data.images.new("merchant-sheet", 1536, 1024, alpha=True)
img.pixels = canvas[::-1].ravel()
img.filepath_raw = str(ROOT / "previews" / "merchant-sheet.png")
img.file_format = "PNG"
img.save()

results["ok"] = results["fbx"]["ok"] and results["glb"]["ok"]
(ROOT / "validation-report-merchant.json").write_text(json.dumps(results, indent=2))
print("VALIDATION_DONE", results["ok"], flush=True)
