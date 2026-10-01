# Frog pet

A **Common** pet, strong suit **space / knockback**: it hops and slams, knocking nearby enemies back.
No glow, no Neon. Common rarity means just a good model. Built by `build_frog.py` (self-contained;
the fused-surface, bake, painter, export and preview code is adapted from the Golden Retriever generator).

**Status: Blender-verified, Studio untested.** FBX and GLB re-import cleanly (`validation-report.json`: PASS).
Nothing has been imported into Roblox Studio, so the TextureID, pivots and joints are unchecked there.

## Look

- Chibi, chunky, low-poly: a wide friendly head, big domed eyes fused into the top of the head, a wide smile,
  a cream-green chin and belly, big powerful folded hind legs and short front legs with rounded toe pads.
- **Faceted on purpose.** Each part is one fused surface (voxel union, smoothed), then meshed on a coarse
  even lattice so the facets are broad and about the same size (cut-gemstone planes), and the vertices are
  projected back onto the fine shape so the silhouette keeps its detail. The skin is flat-shaded; the belt
  keeps soft normals. `--mesh quadric` gives the older adaptive collapse for comparison.
- **Painted, not modelled, face:** big glossy irises with an amber lower glow and two catchlights, white
  sclera, a darker lid ring, a smile line (also a shallow groove), nostril dots and blush cheeks.
- **Painterly texture:** broad brush strokes that wrap round the body and head and run along the limbs,
  2-4 soft value steps, baked AO, key light and a cool rim. Belly and chin are cream-green, darker green
  blotches on the back and head, lighter yellow-green toe pads.
- **Role prop, a championship belt:** a chunky leather strap around the waist with gold studs and stitched
  edges, and a wide oval gold plate at the front (with a darker rim, raised boss and red jewel) and a small gold plate on each hip.
  Painted colour, not glow. The belt is part of the body mesh (its own shell, not fused).

## Size (1 Blender unit = 1 stud, import 1:1, do not scale)

Height 2.09, length 2.38 (toes to rump), width 2.26. Feet stand on z = 0.

## Parts, pivots and triangles

Six rigid mesh parts sharing one material and one 1024 atlas (`textures/frog.png`), one TextureID for all.
Rotation 0, scale 1, each origin on its joint pivot. L/R are the frog's own sides: its left is Blender +X
(Studio -X). Studio axes are (-x, z, y) of Blender; the frog faces Studio -Z.

| Part | Tris | Pivot (Blender) | Pivot (Studio) | Joint parent | Moves by |
|---|---|---|---|---|---|
| Frog_Body | 1808 | (0, 0.10, 0.75) | (0, 0.75, 0.10) | root | hop lift, pitch, squash; belt included |
| Frog_Head | 2076 | (0, -0.25, 0.95) | (0, 0.95, -0.25) | Body | nod / tilt / turn at the neck |
| Frog_LegFL / FR | 624 each | (+-0.40, -0.40, 0.76) | (-+0.40, 0.76, -0.40) | Body | shoulder swing about Studio X |
| Frog_LegBL / BR | 1092 each | (+-0.56, 0.42, 0.72) | (-+0.56, 0.72, 0.42) | Body | hip kick about Studio X |
| **Total** | **7316** | | | | |

Hind legs include haunch, knee, shank and the big webbed-style foot with three toe bulbs; front legs
include arm, elbow, hand and three toe bulbs.

## Hop locomotion

`studio-install-data.json` has `"locomotion": "hop"`, `locomotion_notes` and `hop_frames` (crouch, launch,
apex, slam) with per-frame body lift, body pitch, head pitch, hind-leg and front-leg pitch in degrees
about Studio X (same on L and R), and rough timings. Launch swings the hind legs back about 137 degrees
(relative to the body) so they trail behind; slam is the landing squash. `previews/pose-check.png` shows
crouch, launch and slam from the side and the front 3/4, plus head tilt / turn and a launch seen from behind.
No gaps open at the hips, shoulders or neck.

## Files

`build_frog.py`, `frog.blend`, `exports/fbx/frog.fbx`, `exports/glb/frog.glb`, `textures/frog.png`,
`previews/` (`threeq`, `front`, `side`, `back`, `face-closeup`, `pose-check`, `sheet`),
`polygon-report.json`, `studio-install-data.json`, `validate_exports.py`, `validation-report.json`.

Rebuild: `blender.exe -b --factory-startup --threads 4 --python build_frog.py` (about 3 min; the 2048
bake dominates). Shape check: `-- --flat --out <dir>`; fast texture check: `-- --quick --out <dir>`.
Re-validate: `--python validate_exports.py`.
