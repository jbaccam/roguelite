# Cheetah Cub (Epic, speed)

Blender-verified, Studio untested.

**Strong suit:** +move speed, plus a short speed burst after you get hit. The numbers live in the pet balance table.

## Design

- **Look:** a chibi golden-tan cub.
  - Big round head, about as wide as the body.
  - Big glossy amber eyes with two catchlights.
  - Short chunky legs.
- **Markings:**
  - Cream muzzle, chin, chest and belly.
  - Soft rounded black spots, bigger and fewer on the back.
  - Black tear lines from the inner eye corners down to the mouth corners.
- **Ears:** small and round, with dark backs.
- **Mane:** lighter fluffy fur on the nape and shoulders, fused into the body surface.
- **Tail:** long and thick, curling up behind, with dark rings and a dark tip.
- **Role prop:** an electric-blue speed scarf.
  - The collar band is fused into the body.
  - The knot, the long streaming tail and the short hanging tail are their own part.
- **Epic accent:** a small Neon lightning bolt (`CheetahCub_Scarf_Glow`). It is a thin shell 0.016 stud proud of the scarf's outer face, and only the bolt glows.
- **Rest pose:** a mobile, ready-to-run standing stance.

## Method

This is the same family as the Monkey and Penguin:

- Analytic SDF volumes joined with smooth unions.
- Meshed on a coarse voxel lattice, so the facets are broad and even.
- Flat shaded.
- Painted by 3D position and baked to one 1024 atlas: AO, a soft key light, warm shadows and a cool rim.

Run it with `--shape` for fast vertex-colour look-dev. Add `--pose` for the quick pose sheet.

## Parts

Pivots are in Blender coordinates, in studs.

| Part | Pivot (Blender) | Joint parent | Tris |
|---|---|---|---|
| CheetahCub_Body | (0, 0.10, 0.80) | root | 1164 |
| CheetahCub_Head | (0, -0.40, 1.14) neck | Body | 1552 |
| CheetahCub_EarL / EarR | (±0.40, -0.47, 2.02) ear base | Head | 312 each |
| CheetahCub_FrontLegL / R | (±0.30, -0.30, 0.64) shoulder | Body | 436 each |
| CheetahCub_RearLegL / R | (±0.32, 0.50, 0.64) hip | Body | 588 each |
| CheetahCub_Tail | (0, 0.86, 0.86) tail base | Body | 704 |
| CheetahCub_Scarf | (-0.47, -0.30, 1.09) knot | Body | 1252 |
| CheetahCub_Scarf_Glow | same as Scarf, welded | Scarf | 20 |

- **Total:** 7,364 tris.
- **Size:** 2.35 studs tall, 2.95 long and 1.51 wide.

## Install data

`studio-install-data.json` has:

- **Locomotion:** `"locomotion": "gallop"`, with four gallop frames: gather, front reach, stretch and land. The front pair moves together, then the back pair.
- **Extra poses:** `zoom_sprint`, `head_turn` and `tail_flick`.
- **Angles:** each frame gives Studio and Blender angles.
- **Glow:** the glow part's spec.
- **Three `vfx` entries:**
  - `ScarfSpeedTrail`: a Trail.
  - `PawSparks`: a ParticleEmitter on each paw.
  - `SpeedBurst`: a one-shot burst when the after-hit speed burst triggers.

## Validation

`validate_exports.py` re-imports the FBX and the GLB. Both pass (see `validation-report.json`). This check is Blender only.
