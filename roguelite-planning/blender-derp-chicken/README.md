# Derp chicken

A small, goofy, blocky chicken for the roguelite. When the player's thrown **Egg** weapon lands it
sometimes hatches this chicken, which runs over and pecks enemies (like Minecraft's egg and chick).
When it expires it pops and shoots out feathers, using the loose `Chicken_Feather` piece.

This folder holds only the art asset: the model, exports, texture and previews. There is no Studio
or game code here.

**Status: Blender-verified, Studio untested.** The exports re-import cleanly in Blender 5.2
(`validation-report.json`). Nothing has been imported into Roblox Studio yet, so the import,
texture, pivots and animation in Studio are all unchecked.

## Look

- Style follows `../art-references/ART_DIRECTION_USER_2026-09-17.txt`. It has Minecraft-chicken
  proportions, but every block has soft 2-segment bevels, a slight taper and a painterly texture,
  so it is not pure voxel art.
- Derp: big googly eyes as real geometry. The eyes are different sizes. The left pupil looks up and
  out, and the right pupil looks down and in. Each pupil is a black lens that stands out from the
  eyeball and has a small painted catchlight. The beak hangs slightly open with a pink tongue
  flopping out of one side.
- Colours: warm white and cream feathers (the shadows are cream, never grey), orange-yellow beak and
  legs, and a red comb and wattle. Colours are kept clean because Studio adds +0.3 saturation.

## Size (1 Blender unit = 1 stud, import 1:1, do not scale)

| | Studs |
|---|---|
| Height, foot bottom to comb top | 2.62 |
| Length, beak tip to tail tuft | 2.78 |
| Width, wing to wing | 1.44 |
| Body block length (without / with the tail tuft) | 1.66 / 1.94 |
| Loose feather (length x width x thickness) | 0.55 x 0.22 x 0.06 |

For comparison, a Roblox player is about 5 studs tall. See `previews/scale-vs-5stud-player.png`.

## Parts

All seven parts are separate rigid mesh objects. They share **one material and one texture**,
`textures/derp-chicken-atlas.png` (1024x1024), so every MeshPart gets the same TextureID. All
transforms and bevels are applied: rotation is 0, scale is 1, and each origin is the joint pivot.

L and R mean the chicken's own left and right. Its left is Blender +X, which is Studio -X.

| Part | Tris | Pivot (origin) | Blender pivot (x, y, z) | Moves by |
|---|---|---|---|---|
| `Chicken_Body` | 324 | Centre of the hip line (root part) | (0, 0, 0.55) | Waddle roll and bob |
| `Chicken_Head` | 1,396 | Neck point | (0, -0.55, 1.38) | Peck: pitch about the side-to-side axis |
| `Chicken_WingL` / `R` | 276 each | Top-front shoulder hinge | (±0.61, -0.36, 1.44) | Flap about the front-back axis |
| `Chicken_LegL` / `R` | 220 each | Hip point at the body underside | (±0.30, 0, 0.55) | Swing about the side-to-side axis |
| `Chicken_Feather` | 106 | Its own bbox centre | (1.46, 0.30, 0.05) | Not part of the rig; clone it for the burst |

- The chicken rig is 2,712 triangles, and 2,818 with the feather. `polygon-report.json` has the
  exact counts, sizes, bounding boxes and UV ranges.
- **Body pivot:** the hip-line centre, not the body's bounding-box centre.
- **Head:** includes the beak, tongue, comb, wattle and both eyes and pupils, merged.
- **Model origin:** the Blender world origin, which is the hip-line centre dropped to the feet
  bottom (z = 0). The chicken faces Blender -Y, which is Studio -Z.
- **Feather:** a small cartoon feather with a thick raised spine, a thin soft rim, a gentle curve
  and a short quill. In the export it lies on the ground beside the chicken's left foot, 0.6 studs
  clear, so the two never touch or share baked shadow. It is not parented to anything.

## Studio install data

`studio-install-data.json` gives every value in **Studio axes**: Blender (x, y, z) becomes Studio
(-x, z, y), the same conversion as `../blender-chest-kit/package_studio.py`. It lists:

- `ground_point`, `overall_size` and `overall_center` for the six rig parts. The feather is not
  included in these.
- For each part: `kind` (`rig` or `feather`), `center` and `size` of its bounding box, `pivot`
  (joint point), `pivot_from_body_pivot` (rig parts only, for Motor6D offsets), and a
  `suggested_motion` note.

All positions are relative to the model origin (the ground point). An installer can place each
MeshPart at `origin * CFrame.new(center)` and set `PivotOffset = CFrame.new(pivot - center)`. That
works whatever Studio's importer does with mesh origins. No installer script exists yet.

## Rebuild

```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python build_chicken.py
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python validate_exports.py
```

- `build_chicken.py` builds everything from scratch and uses no code from sibling kits. It writes
  `derp-chicken.blend`, the atlas, both exports, `polygon-report.json`,
  `studio-install-data.json` and the previews.
- It takes about 5 minutes, most of it Cycles preview renders. Add `-- --no-previews` to skip the
  renders (about 15 seconds).
- Texture method:
  1. All seven parts are unwrapped together into one atlas.
  2. Cycles bakes world position, normal, a per-face colour zone and ambient occlusion into float
     maps.
  3. numpy paints the final colours from those maps.

  Because the painting works from 3D position, the broad patches continue across UV seams. The
  painting has three soft value ranges, a lighter top, a warmer cream underside, cream crease
  shadows and a few big soft feather patches on the wings. It adds no fine lines or noise.
- `validate_exports.py` re-imports the FBX and the GLB and checks them against
  `polygon-report.json`. It checks:
  - exactly the 7 named objects;
  - triangle count per part;
  - world bounding box, dimensions and pivot per part;
  - UVs inside 0–1;
  - no zero-area triangles;
  - one shared 1024x1024 image.

  It writes `validation-report.json`.

## Previews (real Blender Cycles renders)

- `previews/front.png`, `side.png`, `three-quarter.png` and `back-three-quarter.png`.
- `previews/scale-vs-5stud-player.png`: an orthographic, true-scale render next to a grey 5-stud
  capsule. The capsule is labelled in the image as a player stand-in.
- `previews/feather-next-to-chicken.png`: the loose feather at true size by the chicken's feet.
- `previews/feather-closeup.png`: the feather alone, close up.
- `previews/gameplay-view.png`: a rough guess at a high gameplay camera (70° vertical FOV, about
  18 studs away) next to the labelled 5-stud stand-in. The real game camera was not measured.

The renders use a shadow-catcher floor composited onto light grey. The stand-in capsule and labels
exist only in the renders, not in the exports or the `.blend`.

## Open questions

- It has not been seen in Studio. Roblox's lighting and +0.3 saturation will shift the creams and
  orange. Judge the colour there.
- Studio's FBX importer may re-centre mesh origins. The install data is written so pivots can be
  set explicitly either way.
- The tongue flops out on the chicken's left. It is small and may not read from a high gameplay
  camera.
