# Monkey pet

Rare pet, strong suit **attack speed** (a plain +attack speed stat). One small painted accent, no glow, no Neon.
**Blender-verified, Studio untested.** `validation-report.json`: PASS for FBX and GLB (Blender 5.2 re-import).

## Design
- Chibi knuckle-walking monkey, 2.33 studs tall, 2.16 wide, 2.43 long (nose to tail curl), feet and fists on z = 0.
  Faces Blender -Y (Studio -Z); its left is Blender +X. The rest pose in the mesh is the natural stance (crouch on all fours).
- Warm brown fur, heart-shaped tan face mask with a muzzle that flows out of the face, big glossy painted eyes with two
  catchlights, big round ears (set out at eye level, turned slightly forward) with tan inner, painted open grin and nose, soft cheek blush, big hands (tan fingers with grooves),
  short chunky legs with three-toe feet, thick soft tail that curls over at the end (tan-ish tip).
- Role props: teal sweatband with white edge lines and a short tied knot with two flared ends (fused into the head part) and
  teal wrist wraps with a white stripe on both wrists (fused into the arm parts). Rare accent: a painted amber lightning
  bolt on the headband (texture only).
- Low-poly look like the Penguin: every part is one surface from signed-distance volumes meshed on a coarse voxel lattice
  (broad even facets), flat shaded. Painterly texture: brush bands in several value ranges, baked AO, per-facet key light,
  warm shadows, cool rim.

## Parts and pivots (one 1024 atlas `textures/monkey.png`, one material)
| Part | Tris | Pivot (Blender) | Joint parent | Moves by |
|---|---|---|---|---|
| `Monkey_Body` | 912 | (0, 0.05, 0.90) | root | bob, lean, roll; tips back for the hype pose |
| `Monkey_Head` | 2,200 | (0, -0.20, 1.36) | Body | nod, tilt, turn (neck hidden under chin and chest) |
| `Monkey_ArmL` / `R` | 812 each | (+-0.56, -0.05, 1.18) | Body | swing and raise at the shoulder |
| `Monkey_LegL` / `R` | 668 each | (+-0.40, 0.26, 0.70) | Body | swing at the hip |
| `Monkey_Tail` | 648 | (0, 0.62, 0.72) | Body | curl / wave from the base inside the rump |

Total 6,720 triangles (every mesh far under 20k).

## Locomotion
`studio-install-data.json` has `"locomotion": "scamper"` and `locomotion_data`: scamper frames A/B (diagonal gait, body bob,
tail counter-swing), `hype_pose` (stands on hind legs, fists pumped), `head_turn` and `tail_curl`, each as Blender bone angles
and as Studio angles. `previews/pose-check.png` shows scamper A and B, scamper from the front, the hype pose, a head
turn/tilt and the tail curl: no gaps seen at the shoulders, hips, neck or tail base.

## Files
`build_monkey.py` (self-contained generator), `monkey.blend`, `exports/fbx/monkey.fbx`, `exports/glb/monkey.glb`,
`textures/monkey.png`, `polygon-report.json`, `studio-install-data.json`, `validate_exports.py`, `validation-report.json`,
`previews/` (`front`, `side`, `threeq`, `back`, `face-closeup`, `pose-check`, `sheet`).
Rebuild: `blender -b --factory-startup --threads 2 --python build_monkey.py` (about 5.5 min, 2048 bake), then
`--python validate_exports.py`. `-- --shape [--pose]` is a fast vertex-colour look-dev run, `-- --quick --out <dir>` a 1024 bake.

## Open issues
- Not seen in Studio: import, texture colour, pivots and the flat-shaded normals are unchecked.
- The headband and wrist wraps are less than one lattice cell proud of the fur, so they are mostly painted with a slight bulge.
- The tail curl pose frame is a suggestion; the tail is a single rigid part (no bend along its length).
- Blender-side armature (`Monkey_Rig`) is for previews only; the exports are plain rigid parts, no animation.
