"""Writes install_call.luau: studio-install-godly-weapons.luau applied to a cfg built from each
weapon's studio-install-data.json and the uploaded texture ids (studio-asset-ids.json).
Paste or send install_call.luau to Studio's Edit datamodel after the Import 3D.

  python make_install_call.py [--replace]
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GODLY = HERE.parent
TEXTURES = json.loads((HERE / "studio-asset-ids.json").read_text())["textures"]

# id, display name (= WeaponCatalog / MonetizationConfig name), folder, play scale, aim
WEAPONS = [
    ("36", "Reaper's Scythe", "reapers-scythe", 1.15, "blade"),
    ("37", "Poseidon's Trident", "poseidons-trident", 1.0, "blade"),
    ("38", "Storm Bow", "storm-bow", 1.05, "forward"),
    ("39", "Shadow Daggers", "shadow-daggers", 0.9, "blade"),
    ("40", "Vampire Blade", "vampire-blade", 1.15, "blade"),
    ("41", "Ray Gun", "ray-gun", 0.9, "forward"),
]
# Attachment name -> install-data key, put on the weapon's textured mesh.
POINTS = {
    "Grip": "grip_point_studio",
    "FloatPivot": "float_pivot_studio",
    "ThrowPivot": "throw_pivot_studio",
    "Tip": "tip_point_studio",
    "Pearl": "pearl_center_studio",
    "ArrowRest": "arrow_rest_point_studio",
    "Nock": "nocking_point_studio",
    "Muzzle": "muzzle_attachment_studio",
}


def lua(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(round(value, 5))
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "{" + ",".join(lua(v) for v in value) + "}"
    return "{" + ",".join(f"[{json.dumps(k)}]={lua(v)}" for k, v in value.items()) + "}"


weapons = []
for wid, name, folder, scale, aim in WEAPONS:
    data = json.loads((GODLY / folder / "studio-install-data.json").read_text())
    parts = {}
    for part, info in data["parts"].items():
        entry = {"kind": info["kind"], "center": info["center_studio"], "size": info["size_studio"]}
        if info.get("color_rgb"):
            entry["color"] = info["color_rgb"]
        parts[part] = entry
    textured = [p for p, i in data["parts"].items() if i["kind"] == "textured"]
    points = {}
    if "daggers" in data:
        for hand, suffix in (("left_hand", "L"), ("right_hand", "R")):
            points["Grip" + suffix] = {"part": data["daggers"][hand]["parts"][0],
                                       "at": data["daggers"][hand]["grip_point_studio"]}
    for attachment, key in POINTS.items():
        if key in data:
            points[attachment] = {"part": textured[0], "at": data[key]}
    weapons.append({"id": wid, "name": name, "folder": folder, "scale": scale, "aim": aim,
                    "texture": TEXTURES[wid], "textured": textured[0], "parts": parts, "points": points})

cfg = {"import": "Godly_Weapons", "replace": "--replace" in sys.argv, "weapons": weapons}
installer = (HERE / "studio-install-godly-weapons.luau").read_text()
(HERE / "install_call.luau").write_text(
    "local install = (function()\n" + installer + "\nend)()\nreturn install(" + lua(cfg) + ")\n")
print("wrote install_call.luau,", len(weapons), "weapons")
