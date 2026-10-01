# Baby Dragon (Legendary, fire)

Chibi low-poly baby dragon for the roguelite. Strong suit: small fire breaths that burn groups (`BurnChance`).
Blender-verified, Studio untested.

## Design
- Crimson / red-orange body, big round head (about as wide as the body), short rounded snout flowing out of the face.
- Big glossy amber eyes with two catchlights, a small open toothy smile with two tiny rounded fangs, painted nostrils, soft blush.
- Two short thick curved ivory horns and soft ear fins, fused into the head. A few soft gold bumps fused along the back (no spikes).
- Round cream belly with broad painted scale bands, stubby arms fused to the chest, stubby hind legs, chunky feet with rounded ivory claws.
- Stubby thick bat wings (rounded arm ridge + thick scalloped membrane, peach with painted veins), their own parts pivoting at the shoulders.
- Short thick curled tail with a rounded gold spade, and a Neon flame on the tip.
- Legendary accent: three separate thin-shell Neon `_Glow` parts: cheek ember streaks, flank and chest embers, tail dots plus the tail flame.
  Colour [255, 150, 46]. No extra role prop: the fire is the prop.
- Meshing: coarse signed-distance lattice, flat shading, so the facets are broad and even. Painterly texture baked from position-driven
  paint, AO, soft key, warm shadows and a cool rim, one 1024 atlas (`textures/baby-dragon.png`, use `MeshPart.TextureID`).
- Rest pose: standing upright on both feet, ready to waddle (no sit pose).

## Parts, pivots (Studio axes), triangles
| Part | Parent | Pivot (Studio) | Tris |
|---|---|---|---|
| BabyDragon_Body (root) | none | 0, 0.70, 0.06 | 1868 |
| BabyDragon_Head (neck) | Body | 0, 1.22, -0.10 | 2760 |
| BabyDragon_WingL / WingR (shoulder) | Body | -/+0.26, 1.08, 0.26 | 560 each |
| BabyDragon_LegL / LegR (hip) | Body | -/+0.30, 0.42, 0.08 | 636 each |
| BabyDragon_Tail (tail root) | Body | 0, 0.40, 0.38 | 904 |
| BabyDragon_Cheeks_Glow (weld) | Head | 0, 1.51, -0.35 | 240 |
| BabyDragon_Embers_Glow (weld) | Body | 0, 0.82, -0.09 | 300 |
| BabyDragon_TailFlame_Glow (weld) | Tail | 0, 0.78, 0.97 | 320 |
| Total | | | 8784 |

Size 1.77 wide, 2.13 long, 2.36 tall studs. Import 1:1. The front is Blender -Y (Studio -Z), and its left is Studio -X.
Exact values are in `polygon-report.json` and `studio-install-data.json`.

## Locomotion (`"locomotion": "waddle_glide"`)
`studio-install-data.json > locomotion_data` holds the Studio-axis angles and offsets for each frame:
- `waddle`: 0.55 s step, legs swing +/-22 deg with a 0.07 stud lift, body rolls +/-7 deg, little balance wing flaps and a tail counter-swing.
- `hop_glide`: wings_up -> wings_down -> glide (root up 0.6, pitched 14 deg, wings spread flat, legs tucked) -> land.
- `fire_breath`: nose up 22 deg, head 0.06 studs forward, wings swept back, legs braced, body leaning back 8 deg.
- `tail_swish`: +/-28 deg yaw.

## VFX (`studio-install-data.json > vfx`)
- `fire_breath`: a cone emitter at the mouth (on the head). It runs in bursts while breathing. Colour goes yellow -> orange -> red -> smoke.
  The cone is 5 studs long with an 18 deg half-angle, to match the burn hitbox.
- `ambient_embers`: a few slow sparks drifting up from the upper back and the tail flame. Always on.
- `glide_trail`: a faint ember trail from each wingtip, during glides only.
- `neon_glow`: Neon settings for the three `_Glow` parts, with a gentle pulse and a tail-flame flicker.

## Files
- `build_baby_dragon.py`: the generator.
  - `-- --shape --out <dir>`: look-dev.
  - `-- --quick --out <dir>`: quick bake.
  - `-- --no-hero`: skips the Cycles hero render.
- `baby-dragon.blend`, `exports/fbx/baby-dragon.fbx`, `exports/glb/baby-dragon.glb`.
- `validate_exports.py` -> `validation-report.json`: PASS for FBX, GLB, texture and install data.
- `previews/`: front, side, threeq, back, face-closeup, pose-check, the Cycles `hero` and `sheet`.
