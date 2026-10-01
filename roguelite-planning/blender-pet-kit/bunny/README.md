# Bunny pet

A **Common** pet, strong suit **team healing** (every 10 s it drops a carrot that heals you or the closest hurt teammate; that logic is game code, not here). Rarity only changes flashiness, so there is no glow and no Neon: just the model. Spec: `../../RARITY_GODLY_ARMOR.md` section 11.

**Status: Blender-verified, Studio untested.** FBX and GLB re-import cleanly in Blender 5.2 (`validation-report.json`, PASS). Nothing has been imported into Roblox Studio, so texture colour, pivots and joints there are unchecked.

## Look
- Upright seated chibi bunny: a big round head (about 1.4 studs wide), small chubby body, short arms, chunky hind legs with big feet.
- Cream coat, warmer tan on the back, crown and ear outsides, white belly, muzzle and tail. Pink nose, rosy cheeks.
- Floppy lop ears, thick and pillowy (about 0.2 thick, 0.45 wide). The inner pink faces forward-out.
- Big glossy painted brown eyes with two catchlights over shallow relief (no modelled sockets). Painted philtrum, small "w" mouth and two buck teeth.
- Cheeks, chin and muzzle are fused into the head as one surface. Toes on paws and feet are fused bumps. The tail is a round cotton ball made of fused puffs.
- Role prop: a leather **carrot bandolier** across the chest: stitched strap, three chunky carrots with leafy tops, and a gold buckle. It is fused into `Bunny_Body`.

## Size (1 Blender unit = 1 stud, import 1:1)
Height to the head top 2.16 studs, length 2.0022, width (ear to ear) 1.9136. Sits on z = 0.

## Parts and pivots
Axes: Blender Z-up, faces -Y, its left is +X. Studio = (-x, z, y). Every part has rotation 0, scale 1, origin at its joint pivot, one shared material and one 1024 atlas (`textures/bunny.png`, use as `MeshPart.TextureID`).

| Part | Tris | Pivot (Blender) | Pivot (Studio) | Joint parent |
|---|---|---|---|---|
| Bunny_Body | 2400 | [0.0, 0.1, 0.75] | [0.0, 0.75, 0.1] | (root) |
| Bunny_Head | 1496 | [0.0, -0.05, 1.25] | [0.0, 1.25, -0.05] | Bunny_Body |
| Bunny_EarL | 280 | [0.42, -0.06, 2.0] | [-0.42, 2.0, -0.06] | Bunny_Head |
| Bunny_EarR | 280 | [-0.42, -0.06, 2.0] | [0.42, 2.0, -0.06] | Bunny_Head |
| Bunny_LegFL | 260 | [0.5, -0.04, 1.02] | [-0.5, 1.02, -0.04] | Bunny_Body |
| Bunny_LegFR | 260 | [-0.5, -0.04, 1.02] | [0.5, 1.02, -0.04] | Bunny_Body |
| Bunny_LegBL | 300 | [0.4, 0.22, 0.42] | [-0.4, 0.42, 0.22] | Bunny_Body |
| Bunny_LegBR | 300 | [-0.4, 0.22, 0.42] | [0.4, 0.42, 0.22] | Bunny_Body |
| Bunny_Tail | 186 | [0.0, 0.6, 0.52] | [0.0, 0.52, 0.6] | Bunny_Body |

Total **5762** triangles (every mesh far under 20k).

Motion: head nods/tilts/turns at the neck; ears flop about Studio Z at the ear base; arms and hind legs swing about Studio X; tail wags about Studio Y. See `studio-install-data.json`.

## Method
`build_bunny.py` (self-contained, background Blender 5.2): each part is a signed-distance field (smooth unions), OpenVDB isosurface, quadric decimate, edge-flip tidy, then one atlas. The colour is painted per texel by a numpy rasteriser from world position, normals, SDF ambient occlusion and face/ear/bandolier masks, with icon-style baked lighting (no Cycles).

```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 --python build_bunny.py
... -- --quick --out <absolute dir>   # 1024 raster, three views, no exports
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python validate_exports.py
```

Previews: `previews/sheet.png` (contact sheet), `front`, `side`, `threeq`, `back`, `face-closeup`, `pose-check`.

## Known gaps
- Blender-verified, Studio untested.
- The back and tail read a little dull and cool in the previews (the previews only have a rim light there); the texture itself is warm.
- Pose check shows no joint gaps at trot +/-28, head tilt/turn, ear flop and tail wag, but hind-leg swings lift the whole thigh (it is a seated pose).

## Fix pass 2 (hop, low-poly, painterly)
- **Locomotion is a hop.** Rest pose = the crouch. Hind legs pivot at the hips (inside the thigh), so +175..185 deg extends thigh and foot straight back; arms reach forward and down (-55..-75) to land; ears pitch back (+40..62) when airborne. `studio-install-data.json` has `"locomotion": "hop"` and a `hop` block: four frames (crouch, launch, airborne, land) with per-joint Blender and Studio X angles, durations (0.8 s cycle), `body_up_studs`, suggested hop height 0.9 and length 3.0 studs. `previews/pose-check.png` shows the four frames; no joint gaps.
- **More low-poly.** Decimated harder to about 5.8k tris, flat shading, facet-weighted baked key light, light value posterisation.
- **Painterly texture** as the dog: value blotches plus broad lens-shaped brush strokes that follow the coat flow, AO, soft key, cool rim. Warm cream/tan back and head back, clearly white cotton tail with warm peach shadow.
- **Ears:** flat faces now turn forward/inward and carry the pink lining (inner faces), not the outer edge.
- **Mouth:** thicker philtrum and "w", bigger outlined buck teeth and whisker dots.
