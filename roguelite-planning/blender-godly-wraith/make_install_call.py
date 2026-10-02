"""Writes install_call.luau: studio-install-wraith.luau applied to a cfg built from
studio-install-data.json. Run it in Studio's Edit datamodel after importing exports/fbx/Wraith.fbx.

  python make_install_call.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEXTURE = "rbxassetid://109611551567319"  # textures/BaseColor.png, uploaded 2026-10-01 via Studio MCP
data = json.loads((HERE / "studio-install-data.json").read_text())


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


parts = {}
for name, info in data["parts"].items():
    entry = {"kind": info["kind"], "center": info["center_studio"], "size": info["size_studio"]}
    if info.get("color_rgb"):
        entry["color"] = info["color_rgb"]
    if info.get("shoulder_pivot_studio"):
        entry["shoulder"] = info["shoulder_pivot_studio"]
    parts[name] = entry
p = data["points"]
points = {
    "Eyes": {"part": "Wraith_Body", "at": p["eyes_studio"]},
    "Core": {"part": "Wraith_Body", "at": p["core_studio"]},
    "Tail": {"part": "Wraith_Body", "at": p["tail_tip_studio"]},
    "ClawR": {"part": "Wraith_ArmR", "at": p["claw_tip_R_studio"]},
    "ClawL": {"part": "Wraith_ArmL", "at": p["claw_tip_L_studio"]},
}
cfg = {"import": "Wraith", "texture": TEXTURE, "parts": parts, "points": points}
installer = (HERE / "studio-install-wraith.luau").read_text()
(HERE / "install_call.luau").write_text("local install = (function()\n" + installer + "\nend)()\nreturn install(" + lua(cfg) + ")\n")
print("wrote install_call.luau")
