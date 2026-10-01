# Baby Dragon (Legendary, fire, flyer)

Chibi low-poly baby dragon for the roguelite, inspired by the Clash Royale baby dragon's design language (own model).
Strong suit: small fire breaths that burn groups (`BurnChance`). Blender-verified, Studio untested.

## Design (designed masses, judged by the side silhouette)
- **Head:** big, a rounded wedge / bean from the side (scaled 1.12 about the neck).
  - A wide, boxy, rounded muzzle pushes forward, with two nostril bumps on top.
  - A toothy overbite with two modelled ivory fangs over a cream lower jaw.
  - Big round amber eyes with two catchlights, set high and wide under soft brows.
  - Thick ivory horns sweep back; small ear fins.
- **Body:** a pear that tapers into a short thick neck.
  - A low pot belly with five clean modelled cream belly plates.
  - Haunches: the thighs are fused into the hips.
  - Soft shoulder bulges and soft spine bumps.
- **Arms** (`ArmL` / `ArmR`): short and chunky, with a thick upper arm, a visible elbow bend, a forearm held forward in
  front of the belly, a cream underside / palm and a hand with 3 rounded ivory claws.
  - The arm-top ball is centred on the shoulder pivot and buried in the shoulder bulge, so there is no seam when it rotates.
  - From the side there is a clear gap between the forearm and the belly.
- **Wings:** big bat wings.
  - A thick arm, a wrist thumb and 3 finger struts as smooth rounded tubes.
  - The membrane is a clean procedural outline with smooth scallop arcs, given thickness (solidify 0.05) with a 2-segment bevelled rim.
  - The wing silhouette is never voxelised or decimated.
- **Tail:** a thick root continuing the body line, tapering to a rounded gold spade with a Neon flame.
- **Legs:** short chunky shins and feet with 3 rounded claws, pivoting at the knee inside the fused thigh.
- **Neon embers:** five separate thin-shell `_Glow` parts — cheeks, spine-bump tops, each wing arm, tail dots plus the
  tail flame. Nothing glows on the chest or belly.
- **Meshing:** body, head, tail, legs, arms and struts are fine signed-distance surfaces, decimated and relaxed.
  - The belly plates are lofted bands on the belly surface with an exact quarter-circle rim profile (no decimation).
- **Shading:**
  - Big surfaces are flat shaded (broad facets).
  - Faces at folds sharper than 24 deg (rims, tubes, bevels, plate rims) are smooth shaded, so edges read soft.
  - The bake skips the facet-key lighting on those smooth faces.
- **Texture:** one 1024 atlas (`textures/baby-dragon.png`, use `MeshPart.TextureID`).
- **Rest pose:** stands on z = 0. The game hovers it 1.5 studs up, and the presentation renders show it hovering mid-beat.

## Parts, pivots (Studio axes), triangles
| Part | Parent | Pivot (Studio) | Tris |
|---|---|---|---|
| BabyDragon_Body (root, incl. 1080-tri belly plates) | none | 0, 0.72, 0.04 | 2880 |
| BabyDragon_Head (neck) | Body | 0, 1.34, -0.13 | 2450 |
| BabyDragon_WingL / WingR (shoulder; 720 struts + 616 membrane) | Body | -/+0.22, 1.08, 0.16 | 1336 each |
| BabyDragon_ArmL / ArmR (shoulder) | Body | -/+0.30, 1.00, -0.10 | 380 each |
| BabyDragon_LegL / LegR (knee) | Body | -/+0.34, 0.36, -0.08 | 300 each |
| BabyDragon_Tail (tail root) | Body | 0, 0.52, 0.30 | 620 |
| BabyDragon_Cheeks_Glow (weld) | Head | | 240 |
| BabyDragon_Back_Glow (weld) | Body | | 180 |
| BabyDragon_WingL_Glow / WingR_Glow (weld) | WingL / WingR | | 120 each |
| BabyDragon_TailFlame_Glow (weld) | Tail | | 320 |
| Total | | | 10962 |

Size 2.52 wide (wings), 2.49 long, 2.45 tall studs. Import 1:1. The front is Blender -Y (Studio -Z), and its left is Studio -X.
Exact glow pivots are in `studio-install-data.json`.

## Locomotion (`"locomotion": "fly"`)
`studio-install-data.json > locomotion_data` holds Studio-axis angles and offsets per frame. Flight frames are relative to the hovering root.
- `wingbeat`: 0.8 s: wings_up -> hover_mid -> wings_down -> hover_mid.
  - The arms stay tucked: hover 6 deg, up-beat 0, down-beat 12.
- `glide`: wings flat and spread, arms tucked back along the sides, body 12 deg nose-down.
- `fire_breath`: nose up 20 deg, arms braced forward, wings swept back, legs braced, body leaning back.
- `tail_swish` and `head_turn`.
- `landing_waddle_extra`: a grounded waddle, with the arms swinging opposite the legs.

## VFX (`studio-install-data.json > vfx`)
- `fire_breath`: a cone emitter at the mouth. It runs in bursts. Colour goes yellow -> orange -> red -> smoke. The cone is 5 studs long with an 18 deg half-angle.
- `ambient_embers`: always on, from the spine embers and the tail flame.
- `flight_trail`: from two tip attachments per wing, while flying.
- `neon_glow`: Neon settings for the five `_Glow` parts.

## Files
- `build_baby_dragon.py`: the generator.
  - `-- --shape --out <dir>`: look-dev, which includes wing-edge and belly close-ups.
  - `-- --quick --out <dir>`: quick bake.
  - `-- --no-hero`: skips the Cycles hero render.
- `baby-dragon.blend`, `exports/fbx/baby-dragon.fbx` (smoothing exported per face), `exports/glb/baby-dragon.glb`.
- `validate_exports.py` -> `validation-report.json`: PASS for FBX, GLB, texture and install data.
- `previews/`: front, side, threeq, back, face-closeup, closeup-wing-edge, closeup-belly, pose-check, hero, sheet.
