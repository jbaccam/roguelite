"""Package the egg kit and the merchant into ONE FBX for a single Studio 3D Import.

Reads only the saved kit files (`egg-kit.blend`, `merchant.blend`); never edits them. Writes
`exports/fbx/egg-merchant-studio.fbx`: an Empty `EggKit` at the origin holding the pedestal and
egg pieces, and an Empty `Merchant` 10 studs to the side holding the merchant's parts. Object
names are kept exactly (Pedestal_*, Egg_*, Merchant_*), so the Studio installer
(`studio-prototype/lobby/InstallEggMerchant.luau`) finds them by name and places each group from
`studio-install-data-egg.json` / `studio-install-data-merchant.json`.

  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python package_studio.py
"""
import bpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GROUPS = [("EggKit", "egg-kit.blend", ("Pedestal_", "Egg_"), 0.0),
          ("Merchant", "merchant.blend", ("Merchant_",), 10.0)]

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
picked = []
for group, blend, prefixes, x in GROUPS:
    with bpy.data.libraries.load(str(ROOT / blend), link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith(prefixes)]
    empty = bpy.data.objects.new(group, None)
    scene.collection.objects.link(empty)
    empty.location = (x, 0, 0)
    picked.append(empty)
    names = []
    for ob in dst.objects:
        if ob is None or ob.type != "MESH":
            continue
        scene.collection.objects.link(ob)
        ob.data.name = ob.name
        ob.parent = empty
        ob.matrix_parent_inverse.identity()
        picked.append(ob)
        names.append(ob.name)
    print("GROUP", group, sorted(names), flush=True)

bpy.context.view_layer.update()
bpy.ops.object.select_all(action="DESELECT")
for ob in picked:
    ob.select_set(True)
bpy.context.view_layer.objects.active = picked[0]
out = ROOT / "exports" / "fbx" / "egg-merchant-studio.fbx"
out.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.fbx(filepath=str(out), use_selection=True, object_types={"MESH", "EMPTY"},
                         axis_forward="-Z", axis_up="Y", path_mode="COPY", embed_textures=True,
                         add_leaf_bones=False)
print("PACKAGED", out, flush=True)
