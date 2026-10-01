# Penguin pet

Common pet, strong suit **Slow** (belly-slides through enemies and slows them). No glow, no Neon.
**Blender-verified, Studio untested.** `validation-report.json`: PASS for FBX and GLB (Blender 5.2 re-import).

## Design
- Chibi round penguin, 2.29 studs tall, standing on z = 0. Faces Blender -Y (Studio -Z); its left is Blender +X.
- Navy back and head, cream belly and heart-shaped face mask, orange beak that flows out of the face (soft fillet, painted
  mouth crease and nostrils), big glossy painted eyes with two catchlights, soft cheek blush, chunky orange webbed feet.
- Role props, painted colour only (no glow): chunky red and cream knit scarf with a knot and one short tail end on the belly
  (fused into the body part), and snow goggles pushed up on the forehead (thick red strap with stitches and a slider,
  domed icy-blue lenses in cream frames, fused into the head part).
- Low-poly look: each part is one surface from analytic signed-distance volumes joined with smooth unions, meshed on a
  COARSE voxel lattice (the lattice is the mesh, so facets are even and broad), relaxed back onto the surface, flat shaded.
  Painterly texture: brush bands following the form in three value ranges, baked AO, per-facet key light, cool rim.

## Parts and pivots (one 1024 atlas `textures/penguin.png`, one material)
| Part | Tris | Pivot (Blender) | Joint parent | Moves by |
|---|---|---|---|---|
| `Penguin_Body` | 1,748 | (0, 0, 0.80) | root | waddle roll/bob, belly-slide pitch |
| `Penguin_Head` | 2,012 | (0, -0.02, 1.42) | Body | nod, tilt, turn (pivot hidden under the scarf) |
| `Penguin_FlipperL` / `R` | 624 each | (±0.60, 0, 1.18) | Body | flap at the shoulder |
| `Penguin_FootL` / `R` | 508 each | (±0.30, -0.02, 0.38) | Body | waddle swing at the hip |

Total 6,024 triangles (every mesh far under 20k). Overall 2.34 wide (flippers), 1.96 long (beak to tail nub), 2.29 tall.

## Locomotion
`studio-install-data.json` has `"locomotion": "waddle"` and `locomotion_data` with the waddle angles (body roll +/-10,
feet +/-24, flippers out 12-35, head counter-roll) and a `slide_pose` (body pitched 78 forward so the belly is on the
ground, head up 45, flippers swept back, feet trailing). `previews/pose-check.png` shows two waddle steps, a front
waddle, a head tilt/turn and two belly-slide views: no gaps seen at the shoulders, hips or neck.

## Files
`build_penguin.py` (self-contained generator), `penguin.blend`, `exports/fbx/penguin.fbx`, `exports/glb/penguin.glb`,
`textures/penguin.png`, `polygon-report.json`, `studio-install-data.json`, `validate_exports.py`, `validation-report.json`,
`previews/` (`front`, `side`, `threeq`, `back`, `face-closeup`, `pose-check`, `sheet`).
Rebuild: `blender -b --factory-startup --threads 2 --python build_penguin.py` (about 6.5 min, 2048 bake), then
`--python validate_exports.py`. `-- --shape` is a fast vertex-colour look-dev run, `-- --quick --out <dir>` a 1024 bake.

## Open issues
- Not seen in Studio: import, texture colour, pivots and the flat-shaded normals are unchecked.
- Flippers are thick lozenges; from straight on they read a little dark against the navy body.
- The scarf-tail and scarf lower edge paint is slightly soft (mask blend is wide because the mesh is coarse).
- The goggle strap bump is sub-facet, so it is mostly painted rather than modelled.
- Blender-side armature (`Penguin_Rig`) is for previews only; the exports are plain rigid parts, no animation.
