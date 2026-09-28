#!/bin/bash
# usage: run_ref.sh <tag> [nobuild] -- paint + full build, then renders through the camera fitted to
# the painting: closed (+ skull close-up) and open (+ side/back hinge views); comparison sheets.
set -e
KIT="C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning/blender-chest-kit"
BL="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
cd "$KIT"
if [ "$2" != "nobuild" ]; then
  python author_textures.py magical > work-magical/paint.log 2>&1
  "$BL" --background --python generate_chest.py -- magical > work-magical/build.log 2>&1 || true
  grep -E "CHEST_READY|Traceback|Error:|File \"" work-magical/build.log | head -20
fi
rm -rf tiers/__pycache__
"$BL" --background --python work-magical/ref_render.py -- "$1" --skull > work-magical/refr.log 2>&1 || true
"$BL" --background --python work-magical/ref_render.py -- "$1_open" --open --side > work-magical/refo.log 2>&1 || true
grep -E "Traceback|Error" work-magical/refr.log work-magical/refo.log | head
rm -rf tiers/__pycache__
cd work-magical && python sheets.py "$1"
echo DONE
