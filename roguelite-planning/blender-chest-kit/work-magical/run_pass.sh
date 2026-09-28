#!/bin/bash
# usage: run_pass.sh <tag>   -- paint, full build, main compare render + skull / lock close-ups
set -e
KIT="C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning/blender-chest-kit"
BL="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
cd "$KIT"
python author_textures.py magical > work-magical/paint.log 2>&1
"$BL" --background --python generate_chest.py -- magical > work-magical/build.log 2>&1 || true
grep -E "CHEST_READY|Traceback|Error:|File \"" work-magical/build.log | head -20
rm -rf tiers/__pycache__
"$BL" --background --python work-magical/compare_render.py -- "$1" > work-magical/cmp.log 2>&1 || true
"$BL" --background --python work-magical/compare_render.py -- "$1_skull" --cam 32 10 6.5 50 6.9 -0.8 > /dev/null 2>&1 || true
"$BL" --background --python work-magical/compare_render.py -- "$1_lockf" --cam 0 0 5.2 50 3.85 -2.2 > /dev/null 2>&1 || true
"$BL" --background --python work-magical/compare_render.py -- "$1_lock34" --cam 32 8 5.6 50 3.95 -2.2 > /dev/null 2>&1 || true
"$BL" --background --python work-magical/compare_render.py -- "$1_open" --open --cam 34 24 20 42 4.8 > /dev/null 2>&1 || true
cd work-magical && python compose.py "cmp_$1.png" "render_$1.png" "render_$1_open.png" > /dev/null
python - "$1" <<'PY'
import sys
from PIL import Image
t = sys.argv[1]
T = r"C:/Users/Jeremiah/AppData/Local/Temp/claude/C--Users-Jeremiah-Documents-ChatGPT-Roblox/26e128a1-a54f-4e27-9b85-1ee1e3c3e2cf"
ref = Image.open(T + "/images/19.webp").convert("RGB")
ims = [ref.crop((900, 220, 1180, 520)), Image.open(f"render_{t}_skull.png"),
       (lambda a: (lambda w: (w.paste(a, (0, 0), a), w)[1])(Image.new("RGB", a.size, (255, 255, 255))))(Image.open(T + "/images/23.png").convert("RGBA")).crop((150, 30, 500, 280)), Image.open(f"render_{t}_lockf.png"),
       Image.open(T + "/scratchpad/star_zoom.png").convert("RGB").crop((0, 0, 840, 840)), Image.open(f"render_{t}_lock34.png")]
H = 380
ims = [im.resize((int(im.width * H / im.height), H)) for im in ims]
sheet = Image.new("RGB", (sum(i.width for i in ims) + 10 * len(ims), H), (20, 20, 24))
x = 0
for im in ims:
    sheet.paste(im, (x, 0)); x += im.width + 10
sheet.save(f"close_{t}.png")
PY
echo DONE
