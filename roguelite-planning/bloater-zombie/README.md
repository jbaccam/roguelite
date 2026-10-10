# Bloater zombie (Pine Valley round 10, "POP GOES THE ZOMBIE")

**Status: Blender-verified, Studio untested after the 2026-10-09 remodel.** The earlier version was imported to Studio, and its import matched Blender within 2e-6. The remodel has not been imported, installed or play tested.

This is the yellow exploding zombie. It follows the Baby/Mutant native zombie contract: 15 rigid R15 sections that `ZombieMotion` / `NativeEnemyFeet` animate in code on Motor6Ds, plus one extra `EyeGlow` mesh. It has no skinning and no clip files.

## Files

| File | What it is |
| --- | --- |
| `build_bloater.py` | Self-contained generator. It writes the model, the atlas, FBX, import data, `Model.blend` and every preview. |
| `Model.blend` | Editable source: 16 meshes on a rigid preview rig (`BloaterZombie_Rig`, 16 bones), with the texture packed. |
| `BloaterZombie_Import.fbx` + `.fbm/` | Mesh-only Studio import with the atlas embedded. It uses the same settings as `BabyZombie_Import.fbx`: plain section names, each origin at its joint head, no armature, `axis_forward -Z`, `axis_up Y`, one material, UV layer `PaintedAtlas`. |
| `textures/BaseColor.png` | 1024² base-colour atlas, painted from 3D position so it has no seams, with 14 px bleed. |
| `bloater-import-data.json` | `{"Bloater": {height, joints, parts}}` in the `ZombieImportData` schema and in Studio space (Blender (x,y,z) → (−x, z, y)). It also has `extras.EyeGlow`, `rootHeight` and `inflate`. |
| `verify_bloater.py` → `verification.json` | Re-imports the FBX into a fresh file, reopens `Model.blend`, and runs every check. |
| `previews/` | Front, Back, Side, ThreeQuarter, Hero, Inflated (rest vs 1.3×), Lineup (Baby, Bloater, Mutant). These are Blender EEVEE renders, not the concept sheet. All seven were re-rendered after the 2026-10-09 remodel. The preview light is a warm sun plus a light-blue sky world fill, roughly like Roblox's sky ambient, so the renders predict the in-game hue. Re-render all with `build_bloater.py` (no args); `-- renders=Front,Inflated` limits it and `-- renders=none` skips them. |

Reproduce from the repo root:
```powershell
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' -b --threads 4 --python-exit-code 1 --python roguelite-planning/bloater-zombie/build_bloater.py
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' -b --threads 4 --python-exit-code 1 --python roguelite-planning/bloater-zombie/verify_bloater.py
```

## Provenance

- Reference: `art-references/round-10-modeling-pack-2026-10-09/01-exploding-zombie.png`, SHA256 `515a00a723b37d9856611b1938e4e981fda2a6b9a9e63bb486e0bd3ca13b1712`. It was used by eye for shape and palette only. No pixels or geometry were copied from it.
- Geometry is original procedural work made from implicit surfaces with smooth-union fillets. The torso is meshed with surface nets on a 0.26 grid, which handles the deltoid overhangs. Head, limbs, hands and feet are sampled on bevel-aware cube lattices for soft two-facet bevels. The rag vest and shorts are closed cloth shells with rounded hanging tongues.
- The texture is original numpy painting: warm orange-yellow skin with small scattered ochre spots, pale amber blisters with a soft painted gloss, brown rags, bone teeth and the face. No image generation or photos were used.
- `BaseColor.png` SHA256 `7bfd0eaebc6185d64226543d7a6c95c8398727c9d3fe4ecd28ab7f9a78b26a17`. `BloaterZombie_Import.fbx` SHA256 `362b7055cad165dd5df50886ac82961e0865541a7d125b4ba42eb380aab56866`.

## Remodel (2026-10-09)

After seeing the first version in Studio, the user said the shoulders looked flat, the neck was awkwardly long, and the body was a ball ("looks like a puffer fish", "split apart"). Changes:

- **No neck.** The head sits straight down in the shoulders. Its underside is buried about 0.15 to 0.2 in a hidden seat on top of the torso. The head is bigger and chunkier: a 1.50 × 1.24 × 1.38 box, 1.90 wide including the cheeks. The puffed cheek lobes rest on the shoulder tops. The neck pivot sits at the back of the skull base (4.88, 0.20 back). When the head is thrown back 16°, the back of the head no longer drops into the collar.
- **Shoulders.** Sloping trapezius rolls run from under the head into round deltoid masses (r 0.46), fused into the torso with smooth fillets. The shoulder joint is the deltoid centre. Each upper arm tapers into the deltoid, so its top stays hidden when it swings.
- **Pear torso, not a ball.** The belly is widest in its lower third (3.96 wide, 3.6 deep at z 2.0 to 2.6), with a narrower upper chest above it. The sag hangs forward, ahead of the thighs. The underside over the legs sits at about 1.75, so a 26° thigh swing clears it even at 1.3×. A full lower back covers the shorts' rounded top. This is narrower than the brief's "≈4.6 belly", on purpose: the reference proportions plus the "puffer fish" feedback.
- **Blisters** are low swellings (height 0.12 to 0.15) with soft fillets, painted pale amber only a little lighter than the skin.
- **Thick limbs.** Upper arms are about 0.76 thick, forearms 0.70, with chunky hands. Lower legs are 0.84, shorts 1.04 to 1.12, and the block feet have a sole lip. The sleeves were removed.
- **Vest.** A shawl on the neck, trapezius and upper back. It hugs the skin 0.06 proud, with tongues on the chest sides and the back.
- **Shoulder caps (follow-up pass).** In game the arms are always rolled 22 to 76° outward, so a static rag on the outside of the shoulder was always cut by the arm. The rag over each deltoid is now a cap carried by the UpperArm. It is a shell on the deltoid sphere, which is centred on the shoulder joint, so it stays snug in every arm pose. It overlaps the vest edge and its feathered hem drops down the outside of the shoulder in 3 ragged tongues. The tongues stop just above where the arm block leaves the deltoid. There is no horizontal shelf.
- **Colour for the game's light.** In Studio the old mustard read lime and the white teeth read blue. The skin is now warmer (240,182,50) with ochre spots, the teeth are bone (228,212,170), and the rags are warm brown. In the sky-fill previews the skin reads yellow next to the green Baby and Mutant.

## Size and triangles

Height 6.00, ground 0.000. The belly is 3.96 wide × 3.59 deep at its widest band. The UpperTorso box, including the deltoids, is 4.53 wide. The head is 1.90 wide including the cheeks and 1.40 tall, with about 1.18 visible above the seat.

Total: 7,864 triangles (target 4–8k). Every mesh is far below the 20k limit.

| Section | Tris | Section | Tris |
| --- | --- | --- | --- |
| UpperTorso (torso, blisters, vest) | 2972 | Left/Right UpperArm (with shoulder cap) | 704 each |
| Head (with cheeks, brow, teeth) | 1084 | Left/Right LowerArm | 188 each |
| LowerTorso (shorts seat) | 180 | Left/Right Hand (palm, 4 fingers, thumb) | 302 each |
| EyeGlow (2 eyes) | 96 | Left/Right UpperLeg (rag shorts, rounded top) | 256 each |
| | | Left/Right LowerLeg | 156 each |
| | | Left/Right Foot (with sole lip) | 160 each |

## Joints (Studio space, as in `bloater-import-data.json`)

Every motor frame is axis-aligned, like Baby and Mutant: the installer uses `CFrame.new(head)`. So the hinge for elbows, wrists, knees and ankles is the part-frame X axis. Each upper arm hangs about 33° out from its deltoid, and each forearm about 24° out.

| Joint (motor) | Part | Parent | Head (x, y, z) |
| --- | --- | --- | --- |
| Root | LowerTorso | HumanoidRootPart | (0, 1.62, 0.12) |
| Waist | UpperTorso | LowerTorso | (0, 2.05, 0.05) |
| Neck | Head | UpperTorso | (0, 4.88, 0.20) |
| L/R Shoulder | UpperArm | UpperTorso | (∓1.80, 3.88, 0.02) |
| L/R Elbow | LowerArm | UpperArm | (∓2.33, 3.09, −0.02) |
| L/R Wrist | Hand | LowerArm | (∓2.58, 2.58, −0.12) |
| L/R Hip | UpperLeg | LowerTorso | (∓0.66, 1.62, 0.12) |
| L/R Knee | LowerLeg | UpperLeg | (∓0.66, 1.00, 0.10) |
| L/R Ankle | Foot | LowerLeg | (∓0.66, 0.40, 0.06) |

`inflate.center` (UpperTorso part centre) is (0, 3.246, −0.579). `rootHeight` is 1.62.

## Installer notes (`InstallZombieVariants.luau` left unchanged)

- Add `Bloater = <bloater-import-data.json>.Bloater` to the import data. The installer's 15-section count and its alignment fit ignore `EyeGlow`, because `EyeGlow` is not in `parts`.
- Root: `rootHeight` = 1.62. `InstallBloater.luau` uses root size (2.4, 2, 1.6), which gives HipHeight 0.62.
- `EyeGlow`: clone it like the other sections, place it at `extras.EyeGlow.center`, and weld it to Head. Set `Material = Neon`, `CanCollide = false`, `Massless = true`.
- Inflation, as the runtime contract assumes and the checks use: UpperTorso `Size *= s` about its centre (`inflate.center`). Shoulder and Neck `C0` are multiplied by `s`. Head `Size *= 1.08`. Scale the EyeGlow weld offset and size by 1.08 too, or the eyes sink.

## Checks (`verification.json`, status PASS)

- **Package:** 15 sections + EyeGlow with exact names. No open edges and no degenerate faces. UVs within 0–1. One material and the `PaintedAtlas` UV layer. The 1024 texture loads from the FBX and from the packed `.blend`.
- **Placement:** ground 0.000, height 6.00. Origins match the joints within 1e-3. Import-data bounds match the FBX within 1e-6. The `.fbm` copy is identical to the texture.
- **Head seat (new, replaces the hidden-neck check):** the head's lowest 0.30 (underside and cheek bottoms) is the seat. Seated means some of the seat is inside the body: 69/114 vertices at rest and 83/114 at 1.3×, so no neck gap opens. Everything above the seat (face, eyes, teeth, cheek sides) must clear the body: 0.137 at rest and 0.065 at 1.3×.
- **Belly clearance** (minimum gap; no intersecting triangles and no vertices inside):

  | Part | Rest | 1.3× |
  | --- | --- | --- |
  | Upper arms below the deltoid seat (more than 45% of the way to the elbow) | 0.105 | 0.098 |
  | Hands | 0.445 | 0.451 |
  | Forearms | 0.183 | 0.238 |
  | EyeGlow | 0.625 | 0.593 |

  Targets are ≥0.05 at rest and ≥0 at 1.3×. The arm seat fraction went from 0.30 to 0.45 because the round deltoid now covers the upper arm's top.
- **Arm pose sweep (generic reach):** 288 poses (shoulder −30…110°, elbow 0–40°, roll ±7°, rest and inflated). Zero collisions; smallest gap 0.019.
- **Game pose sweep (`ZombieMotion.bloater` ranges, new):** Motor Transform = `CFrame.Angles` in each motor's axis-aligned frame. The swell is applied the way `Round10World` does it: about the Waist joint, with the Head at 1.08. Each sweep runs at rest and at 1.3×, over corners plus mid samples.
  - **Arms:** 288 poses. Shoulder X −6/10/28, Z out 22.4/29.6/72.4/75.6 (walk plus brace, with the tremble), elbow 8/17/26, wrist −4/10. The arm blocks touch neither the skin nor the vest. Smallest gap to the skin is 0.112, to the vest 0.055. The shoulder caps overlap the vest edge by design (rag over rag; listed as info only).
  - **Head:** 18 poses. Neck X 0/8/16, Z ±4. Zero contacts above the seat (smallest gap 0.012), and the head stays seated (at least 52/114).
  - **Legs:** 240 poses. Waist (0,0,0) and (9/−4, ±3, ±8), hip X −18/4/26 with Z +1/−7, knee 0/−36. Zero shorts poke-through on top of the belly. Zero exposed shorts or seat tops. Zero hem or visible shin points inside the belly. The hem stays at least 0.092 below the belly, worst at 1.3× with the waist at (9,3,8) and the hip at X −18, Z −7.
- **Eyes:** 90% of straight-on rays hit EyeGlow before the head. The threshold was raised from 30% to 60%.

## Known issues

1. **Belly drops when inflated.** At 1.3× the belly grows down over the shorts, and the swollen shoulders rise around the cheeks and swallow the shoulder caps, so the head sinks in. This is left as is: it reads as swelling.
2. **Shoulder caps move with the arms.** In the walk pose (arms rolled out about 26°), each cap rides up onto the shoulder top over the vest edge. When braced, it tucks into the swollen shoulder. Cap and vest are both brown rag, and where they overlap the cap sits on top of the vest. This was checked in scratch renders of the walk and braced poses.
3. **Not checked in Studio.** The importer and the in-game colour have not been checked after the remodel. The blue sky fill in the previews only approximates Studio's ambient and ColorCorrection.
4. **Narrower than the brief.** The belly is 3.96 wide, not the brief's ≈4.6, as described under Remodel.
