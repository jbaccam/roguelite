# Turtle (Rare, team defense)

Chibi low-poly turtle for the roguelite. Strong suit: every 15 s a shell shield blocks one hit to the owner or a hurt teammate.
Blender-verified, Studio untested.

## Design
- Soft green skin, big round head (about as wide as the shell), cheeks, short chunky elephant legs, tail nub.
- Tall domed shell with rounded hex/pentagon scutes (Voronoi cells, warm light centres fading to dark edges, soft seams).
- Thick brass shield-crest rim around the shell edge, fused into the shell, with painted rivets.
- Role prop: painted-steel knight kettle helm (open face, brass band, nose guard, cheek guards, fused amber crest) fused into the head.
- Rare accent: small painted shield-crest emblem on the helm front (no glow, no Neon).
- Meshing: coarse signed-distance lattice, flat shading, so the facets are broad and even. Painterly texture is baked from
  position-driven paint, AO, soft key, warm shadows and a cool rim, one 1024 atlas (`textures/turtle.png`, use `MeshPart.TextureID`).

## Parts, pivots (Studio axes), triangles
| Part | Parent | Pivot (Studio) | Tris |
|---|---|---|---|
| Turtle_Body (root) | none | 0, 0.80, 0.12 | 1664 |
| Turtle_Head (neck, helm fused) | Body | 0, 0.95, -0.80 | 2664 |
| Turtle_LegFL / FR | Body | -/+0.72, 0.80, -0.36 | 476 each |
| Turtle_LegBL / BR | Body | -/+0.72, 0.80, 0.66 | 476 each |
| Turtle_Tail | Body | 0, 0.62, 0.96 | 236 |
| Total | | | 6468 |

Size 2.44 wide, 3.77 long, 2.29 tall studs, import 1:1, front is Blender -Y (Studio -Z), its left is Studio -X.
Exact values: `polygon-report.json`, `studio-install-data.json`.

## Locomotion (`"locomotion": "plod"`)
`studio-install-data.json > locomotion_data` has Studio-axis angles and offsets per frame:
- `plod`: 4 frames, period 1.4 s, diagonal leg pairs swing +/-16 deg with a 0.10 stud lift, body sway +/-4 deg, head bobs forward 0.12 studs.
- `shield_up`: head pulled back 0.45 studs and pitched down 20 deg, legs half tucked, shell pitched 12 deg forward.
- Studio check still needed: ground contact in shield-up (front legs lifted 0.30, back legs 0.16).

## Files
`build_turtle.py` (generator; `-- --shape` look-dev, `-- --quick --out <dir>`), `turtle.blend`, `exports/fbx/turtle.fbx`,
`exports/glb/turtle.glb`, `validate_exports.py` -> `validation-report.json` (PASS for FBX and GLB), `previews/` (front, side, threeq,
back, face-closeup, pose-check, sheet).
