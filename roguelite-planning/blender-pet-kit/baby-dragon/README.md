# Baby Dragon (Legendary, fire, flyer)

Chibi low-poly baby dragon for the roguelite, inspired by the Clash Royale baby dragon's design language (own model).
Strong suit: small fire breaths that burn groups (`BurnChance`). Blender-verified, Studio untested.

## Design (rework after the owner's notes: designed masses, judged by the side silhouette)
- **Head:** big, a rounded wedge / bean from the side (scaled 1.12 about the neck for chibi proportions).
  - A wide, boxy, rounded muzzle pushes clearly forward, with two nostril bumps on top.
  - A toothy overbite with two modelled ivory fangs over a cream lower jaw.
  - Big round amber eyes with two catchlights, set high and wide under soft brow ridges.
  - Thick ivory horns sweep back; small ear fins.
- **Body:** a pear that tapers into a short thick neck.
  - A low pot belly with five MODELLED cream belly plates (raised bands with grooves).
  - Haunches: the thighs are fused into the hips with fillets.
  - Soft bumps run down the spine. No arms.
- **Wings:** big bat wings (about 2x the first pass).
  - A thick arm, a wrist thumb and 3 finger struts.
  - A thick, scalloped peach membrane.
  - Spread and raised, so they read from the front, side and back.
- **Tail:** a thick root that continues the body line, tapering to a rounded gold spade with a Neon flame.
- **Legs:** short, chunky shins and feet with 3 rounded ivory claws. They pivot at the knee, which is hidden inside the fused thigh.
- **Neon embers:** five separate thin-shell `_Glow` parts, colour [255, 150, 46]:
  - cheek streaks;
  - ember tops on the spine bumps;
  - streaks on each wing arm;
  - tail dots plus the tail flame.

  There are no chest or belly embers.
- **Meshing:** a fine signed-distance grid, decimated and relaxed (edge flips plus smoothing projected back onto the surface), flat shaded.
- **Texture:** painterly, baked to one 1024 atlas (`textures/baby-dragon.png`, use `MeshPart.TextureID`).
- **Rest pose:** stands on z = 0 with the wings spread. The game hovers it 1.5 studs up. The presentation renders show it hovering mid-beat.

## Parts, pivots (Studio axes), triangles
| Part | Parent | Pivot (Studio) | Tris |
|---|---|---|---|
| BabyDragon_Body (root) | none | 0, 0.72, 0.04 | 2500 |
| BabyDragon_Head (neck) | Body | 0, 1.34, -0.13 | 2900 |
| BabyDragon_WingL / WingR (shoulder) | Body | -/+0.22, 1.08, 0.16 | 950 each |
| BabyDragon_LegL / LegR (knee) | Body | -/+0.34, 0.36, -0.08 | 300 each |
| BabyDragon_Tail (tail root) | Body | 0, 0.52, 0.30 | 620 |
| BabyDragon_Cheeks_Glow (weld) | Head | 0, 1.64, -0.39 | 240 |
| BabyDragon_Back_Glow (weld) | Body | 0, 0.88, 0.52 | 180 |
| BabyDragon_WingL_Glow / WingR_Glow (weld) | WingL / WingR | -/+0.38, 1.39, 0.21 | 120 each |
| BabyDragon_TailFlame_Glow (weld) | Tail | 0, 0.75, 1.04 | 320 |
| Total | | | 9500 |

Size 2.49 wide (wings), 2.49 long, 2.44 tall studs. Import 1:1. The front is Blender -Y (Studio -Z), and its left is Studio -X.

## Locomotion (`"locomotion": "fly"`)
`studio-install-data.json > locomotion_data` holds Studio-axis angles and offsets per frame. Flight frames are relative to the hovering root.
- `wingbeat`: 0.8 s, big and slow: wings_up (+30) -> hover_mid -> wings_down (-55) -> hover_mid, with a body bob of +0.10 / -0.08.
- `glide`: the wings flatten and spread, the body pitches 12 deg nose-down and the legs tuck.
- `fire_breath`: nose up 20 deg, wings swept back, legs braced forward, body leaning back 10 deg.
- `tail_swish` and `head_turn`.
- `landing_waddle_extra`: a short grounded waddle with the wings half folded.

## VFX (`studio-install-data.json > vfx`)
- `fire_breath`: a cone emitter at the mouth (on the head). It runs in bursts while breathing.
  - Colour goes yellow -> orange -> red -> smoke.
  - The cone is 5 studs long with an 18 deg half-angle, to match the burn hitbox.
- `ambient_embers`: slow sparks drifting up from the spine embers and the tail flame. Always on.
- `flight_trail`: a faint ember trail from two tip attachments per wing, always on while flying and stronger in glides.
- `neon_glow`: Neon settings for the five `_Glow` parts.

## Files
- `build_baby_dragon.py`: the generator.
  - `-- --shape --out <dir>`: look-dev.
  - `-- --quick --out <dir>`: quick bake.
  - `-- --no-hero`: skips the Cycles hero render.
- `baby-dragon.blend`, `exports/fbx/baby-dragon.fbx`, `exports/glb/baby-dragon.glb`.
- `validate_exports.py` -> `validation-report.json`: PASS for FBX, GLB, texture and install data.
- `previews/`: front, side, threeq, back, face-closeup, pose-check, the Cycles `hero` and `sheet`.
