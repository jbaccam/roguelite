"""Combine the six approved Godly weapon models into ONE FBX for a single Studio Import 3D.

Run headless (does not touch any open Blender window):
  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 \
      --python combine_godly_weapons.py

Each weapon's meshes are appended unchanged from its Model.blend (names from its
studio-install-data.json "parts"), moved apart along Blender X so nothing overlaps, and exported
with the same FBX settings the weapon builds used. The Studio installer
(studio-install-godly-weapons.luau) rebuilds every template from the authored install data, so
the spacing here only keeps the import readable.
"""
import json
import shutil
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
GODLY = HERE.parent
OUT_FBX = HERE / "Godly_Weapons.fbx"
REPORT = HERE / "combine_report.json"

# Order = MonetizationConfig.GodlyWeapons order = WeaponCatalog ids 36..41.
WEAPONS = [
    ("36", "reapers-scythe"),
    ("37", "poseidons-trident"),
    ("38", "storm-bow"),
    ("39", "shadow-daggers"),
    ("40", "vampire-blade"),
    ("41", "ray-gun"),
]
SPACING = 9.0  # Blender units (= studs) between weapons

bpy.ops.wm.read_factory_settings(use_empty=True)
report = {"weapons": {}, "fbx": str(OUT_FBX)}

for index, (wid, folder) in enumerate(WEAPONS):
    root = GODLY / folder
    data = json.loads((root / "studio-install-data.json").read_text())
    names = list(data["parts"].keys())
    with bpy.data.libraries.load(str(root / "Model.blend"), link=False) as (src, dst):
        missing = [n for n in names if n not in src.objects]
        assert not missing, f"{folder}: missing objects {missing}"
        dst.objects = names
    tris = {}
    for ob in dst.objects:
        assert ob.type == "MESH", f"{ob.name} is {ob.type}"
        bpy.context.scene.collection.objects.link(ob)
        ob.parent = None
        # Studio X = -Blender x, so step weapons toward -x to lay them out left-to-right in Studio.
        ob.location.x -= index * SPACING
        ob.data.calc_loop_triangles()
        tris[ob.name] = len(ob.data.loop_triangles)
    report["weapons"][wid] = {"folder": folder, "objects": tris, "offset_studio_x": index * SPACING}

# Pack every texture so the FBX embeds it regardless of where the library paths pointed.
for image in bpy.data.images:
    if image.source == "FILE" and not image.packed_file:
        image.filepath = bpy.path.abspath(image.filepath, library=image.library)
        image.pack()
report["images"] = sorted(i.name for i in bpy.data.images)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.fbx(filepath=str(OUT_FBX), use_selection=True, object_types={"MESH"}, axis_forward="-Z",
                         axis_up="Y", path_mode="COPY", embed_textures=True, add_leaf_bones=False,
                         mesh_smooth_type="OFF")

# Re-import the FBX fresh and compare names and triangle counts.
expected = {n: t for w in report["weapons"].values() for n, t in w["objects"].items()}
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(OUT_FBX))
got = {}
for ob in bpy.context.scene.objects:
    if ob.type == "MESH":
        ob.data.calc_loop_triangles()
        got[ob.name] = len(ob.data.loop_triangles)
report["reimport"] = {
    "objects": len(got),
    "names_match": sorted(got) == sorted(expected),
    "triangles_match": all(got.get(n) == t for n, t in expected.items()),
    "total_triangles": sum(got.values()),
}
# The re-import unpacks the embedded textures into Godly_Weapons.fbm; that copy isn't needed.
shutil.rmtree(OUT_FBX.with_suffix(".fbm"), ignore_errors=True)
REPORT.write_text(json.dumps(report, indent=1))
print("COMBINE_REPORT", json.dumps(report["reimport"]))
assert report["reimport"]["names_match"] and report["reimport"]["triangles_match"], "re-import mismatch"
