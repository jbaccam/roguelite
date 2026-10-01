# Fox pet

**Rare** pet, strong suit **damage** (pounces on nearby enemies). Chibi orange fox with cream muzzle, cheeks,
chest and tail tip, dark socks, big dark-tipped ears with cream inner fluff, a huge fused tail plume, a crimson scarf and
one small painted bone-claw charm (the Rare accent: painted, no glow, no Neon).

**Status: Blender-verified, Studio untested.** FBX and GLB re-import cleanly (`validation-report.json`: PASS). Nothing has
been imported into Roblox Studio, so import, texture colour, pivots and joints there are unchecked.
Brief: `../PET_BRIEF.md`. Generator: `build_fox.py` (self-contained; the fused-surface, painter, bake and export
method is the approved Golden Retriever pipeline, copied in).

## Look

- Low-poly on purpose (owner feedback): every furry part is ONE fused surface (voxel SDF union, smooth, decimate), then
  relaxed so the facets are broad and even, and shaded flat. Soft rounded forms, painterly texture on top.
- Face painted over shallow relief: big glossy amber eyes with two catchlights, a short confident brow, a small modelled
  nose with painted shine, a philtrum and a sly little smile (the fox's left corner lifts), whisker dots.
- The muzzle grows out of the head (broad base narrowing to the nose, small lower jaw), no stuck-on beak.
- Ears are thick, their own parts: orange outside, dark tips, a shallow dish with a cream fluff tuft growing out of it.
- Tail: one voxel-unioned plume swept along a soft S-curve, swelling to a big brush; the cream tip is blended by colour only.
  Its own part, pivot at the base.
- Colour is painted by 3D position, so it is continuous across every join: orange coat with rust back, broad brush strokes
  in 2-4 values, cream bib/belly/muzzle/lower cheeks, dark socks, baked AO and key light with cool shadows and rim.
- Role prop, part `Fox_Scarf`: a crimson scarf (band on the body, knot plus two tie ends with a cream band as a separate
  dangling part) and the claw charm on a cord ring.

## Size (1 Blender unit = 1 stud, import 1:1, do not scale)

Height 2.5804 (ear tips), length nose to tail 3.4113, width 1.4104 (chibi pass: head 1.2x, eyes 1.34x, legs about 20% shorter and chunkier, tail about 1.7x volume, knit scarf).
Paws stand on z = 0. Checked against a 5-stud R15 block figure in `previews/scale-vs-5stud-r15.png`.

## Parts and pivots

Ten rigid mesh parts, one material, one 1024 atlas (`textures/fox.png`), rotation 0 and scale 1, each origin on its joint
pivot. L/R are the fox's own; its left is Blender +X = Studio -X. Studio = (-x, z, y) of Blender; the fox faces Studio -Z.

| Part | Tris | Pivot (Blender) | Pivot (Studio) | Joint parent |
|---|---|---|---|---|
| Fox_Body | 1118 | (0.0, 0.0, 0.86) | (0.0, 0.86, 0.0) | (root) |
| Fox_Head | 1273 | (0.0, -0.52, 1.18) | (0.0, 1.18, -0.52) | Fox_Body |
| Fox_EarL | 240 | (0.36, -0.66, 1.97) | (-0.36, 1.97, -0.66) | Fox_Head |
| Fox_EarR | 240 | (-0.36, -0.66, 1.97) | (0.36, 1.97, -0.66) | Fox_Head |
| Fox_LegFL | 330 | (0.23, -0.25, 0.64) | (-0.23, 0.64, -0.25) | Fox_Body |
| Fox_LegFR | 330 | (-0.23, -0.25, 0.64) | (0.23, 0.64, -0.25) | Fox_Body |
| Fox_LegBL | 380 | (0.26, 0.28, 0.66) | (-0.26, 0.66, 0.28) | Fox_Body |
| Fox_LegBR | 380 | (-0.26, 0.28, 0.66) | (0.26, 0.66, 0.28) | Fox_Body |
| Fox_Tail | 900 | (0.0, 0.4, 0.8) | (0.0, 0.8, 0.4) | Fox_Body |
| Fox_Scarf | 366 | (0.294, -0.6281, 0.9396) | (-0.294, 0.9396, -0.6281) | Fox_Body |

**Total 5557 triangles** (brief for Rare was 6-10k; this is lower on purpose for the low-poly look).
Suggested motions are in `studio-install-data.json` (`suggested_motion`).

## Files

`build_fox.py`, `fox.blend`, `exports/fbx/fox.fbx` (axis_forward -Z, axis_up Y, texture embedded), `exports/glb/fox.glb`,
`textures/fox.png`, `previews/` (front, side, threeq, back, face-closeup, pose-check, scale-vs-5stud-r15, `sheet.png`),
`polygon-report.json`, `studio-install-data.json`, `validate_exports.py`, `validation-report.json`.

Rebuild: `"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 --python build_fox.py`
(about 8 minutes with 2 threads; `-- --quick --out <dir>` is a 70 s iteration mode). Validate with `validate_exports.py`.

## Studio notes

Use `MeshPart.TextureID` with the atlas (SurfaceAppearance renders blank in Play). The fur parts are flat-shaded, so the FBX
carries split normals; if Studio smooths them, the baked facet lighting in the texture still shows the facets.
