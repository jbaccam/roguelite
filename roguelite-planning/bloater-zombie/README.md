# Bloater zombie (Pine Valley round 10, "POP GOES THE ZOMBIE")

**Status: Blender-verified, Studio untested.** No Studio import, upload, install or play test has been done.

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
| `previews/` | Front, Back, Side, ThreeQuarter, Hero, Inflated (rest vs 1.3×), Lineup (Baby, Bloater, Mutant). These are Blender EEVEE renders, not the concept sheet. Front and Inflated show the current arms. Back, Side, ThreeQuarter, Hero and Lineup are from the build before the arm fix (arms about 0.2 narrower). Re-render all with `build_bloater.py` (no args); `-- renders=Front,Inflated` limits it. |

Reproduce from the repo root:
```powershell
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' -b --threads 4 --python-exit-code 1 --python roguelite-planning/bloater-zombie/build_bloater.py
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' -b --threads 4 --python-exit-code 1 --python roguelite-planning/bloater-zombie/verify_bloater.py
```

## Provenance

- Reference: `art-references/round-10-modeling-pack-2026-10-09/01-exploding-zombie.png`, SHA256 `515a00a723b37d9856611b1938e4e981fda2a6b9a9e63bb486e0bd3ca13b1712`. It was used by eye for shape and palette only. No pixels or geometry were copied from it.
- Geometry is original procedural work: implicit surfaces with smooth-union fillets (cheeks, brow, shoulders and blisters are fused), sampled on bevel-aware cube lattices for soft two-facet bevels. The rag vest, shorts and sleeves are closed cloth shells with rounded hanging tongues, not sawtooth.
- The texture is original numpy painting: mustard skin with ochre blotches, amber blisters with painted gloss, brown rags, and the face. No image generation or photos were used.
- `BaseColor.png` SHA256 `30a6d32d10cedba6a38dc69f8105e65c68e8e70ef533e3944321d4f00ec1f765`. `BloaterZombie_Import.fbx` SHA256 `028adde86616a5dd7e011079aa8ee37d8593b12ceb23e2d9eb0162d34f5fe6bd`.

## Size and triangles

Height 6.00. Belly 4.56 wide × 4.29 deep at its middle. The UpperTorso box including the shoulder masses is 5.25 wide.

Total: 7,540 triangles (target 4–8k). Every mesh is far below the 20k limit.

| Section | Tris | Section | Tris |
| --- | --- | --- | --- |
| UpperTorso (belly, blisters, vest) | 2984 | Left/Right UpperArm (with sleeve cap) | 412 each |
| Head (with cheeks, brow, teeth, neck seat) | 1324 | Left/Right LowerArm | 156 each |
| LowerTorso (shorts seat) | 180 | Left/Right Hand (palm, 4 fingers, thumb) | 302 each |
| EyeGlow (2 eyes) | 96 | Left/Right UpperLeg (rag shorts) | 320 each |
| | | Left/Right LowerLeg | 156 each |
| | | Left/Right Foot | 132 each |

## Joints (Studio space, as in `bloater-import-data.json`)

Every motor frame is axis-aligned, like Baby and Mutant: the installer uses `CFrame.new(head)`. So the hinge for elbows, wrists, knees and ankles is the part-frame X axis. Legs and forearms hang nearly vertical, so an X rotation flexes them forward or back cleanly. Each upper arm hangs about 35° out from its shoulder mass.

| Joint (motor) | Part | Parent | Head (x, y, z) |
| --- | --- | --- | --- |
| Root | LowerTorso | HumanoidRootPart | (0, 1.55, 0.05) |
| Waist | UpperTorso | LowerTorso | (0, 1.98, 0) |
| Neck | Head | UpperTorso | (0, 4.78, −0.06) |
| L/R Shoulder | UpperArm | UpperTorso | (∓2.47, 4.12, 0.02) |
| L/R Elbow | LowerArm | UpperArm | (∓2.98, 3.40, −0.02) |
| L/R Wrist | Hand | LowerArm | (∓3.10, 2.80, −0.10) |
| L/R Hip | UpperLeg | LowerTorso | (∓0.63, 1.55, 0.05) |
| L/R Knee | LowerLeg | UpperLeg | (∓0.64, 0.90, 0) |
| L/R Ankle | Foot | LowerLeg | (∓0.645, 0.36, −0.02) |

## Installer notes (`InstallZombieVariants.luau` left unchanged)

- Add `Bloater = <bloater-import-data.json>.Bloater` to the import data. The installer's 15-section count and its alignment fit ignore `EyeGlow`, because `EyeGlow` is not in `parts`.
- Root: `rootHeight` = 1.55. Suggested root size (2.4, 2.0, 2.0), which gives HipHeight 0.55. The installer hard-codes the Baby/Mutant values, so the Bloater needs its own branch.
- `EyeGlow`: clone it like the other sections, place it at `extras.EyeGlow.center`, and weld it to Head. Set `Material = Neon`, `CanCollide = false`, `Massless = true`.
- Inflation, as the runtime contract assumes and the checks use: UpperTorso `Size *= s` about its centre (`inflate.center`). Shoulder and Neck `C0` are multiplied by `s`. Head `Size *= 1.08`. Scale the EyeGlow weld offset and size by 1.08 too, or the eyes sink.

## Checks (`verification.json`, status PASS)

- **Package:** 15 sections + EyeGlow with exact names. No open edges and no degenerate faces. UVs within 0–1. 1024 texture loads from the FBX and from the packed `.blend`.
- **Placement:** ground 0.000. Origins match the joints within 1e-3. Import-data bounds match the FBX within 1e-6. The `.fbm` copy is identical to the texture.
- **Belly clearance** (minimum gap; no intersecting triangles and no vertices inside):

  | Part | Rest | 1.3× |
  | --- | --- | --- |
  | Upper arms below the fused shoulder seat (more than 30% of the way to the elbow) | 0.106 | 0.038 |
  | Hands | 0.663 | 0.707 |
  | Forearms | 0.359 | 0.292 |
  | EyeGlow | 0.75 | 0.76 |
  | Head (excluding the hidden neck seat) | 0.109 | 0.091 |

  Targets are ≥0.05 at rest and ≥0 at 1.3× for the arms, and ≥0.05 for the head. Each upper arm's top 26% is meant to sit inside the shoulder mass, so it is fused, not floating. Inside tests use ray parity, which stays correct next to the thin vest shell.
- **Arm pose sweep:** 288 poses (shoulder −30…110°, elbow 0–40°, roll ±7°, rest and inflated). Zero collisions; smallest gap 0.154.
- **Eyes:** 70% of straight-on rays hit EyeGlow before the head.

## Known issues

Arm fix (2026-10-09): the shoulders moved out 0.22, and the elbows and wrists moved out 0.20, so the hands are the same shape, just translated. The shoulder masses moved out 0.08 so the arms stay fused. The sleeve caps now fit about 0.04 proud of the arm. The hidden neck mound top was lowered by 0.06 to open the head gap at 1.3×. The head itself did not move, and the height is still 6.00.

1. **Belly drops when inflated.** At 1.3× the belly underside drops about 0.5 studs and covers the shorts. This is left as is: the runtime raises the torso as it inflates.
2. **Not checked in Studio.** Shading and importer behaviour in Studio have not been checked. The custom normals come from the implicit surfaces.
