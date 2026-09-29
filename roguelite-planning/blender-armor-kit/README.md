# Armor kit: Dragon Scale (Legendary style sample)

**Status: Blender-verified, Studio untested.** Nothing here has been imported into Roblox Studio or
checked in Play. The fit, clipping and glow notes below come from Blender only.

This is the style sample for the armor sets (`../RARITY_GODLY_ARMOR.md` section 13). It is fitted to
the normalized R15 body every player gets. The look is a dark dragon knight:
- obsidian plates with blue-violet shadows and warm painted edge highlights;
- crimson kite scales built as real geometry;
- gold only on key rims;
- ivory horns, fangs and claws;
- thin molten-amber Neon seams, eyes and gems.

The first version (`build_armor.py`, renders in `previews/old-v1/`) was rejected as "pajamas". This
set is a full rebuild with a new generator.

## Files

| File | What |
|---|---|
| `build_dragon_scale.py` | Self-contained generator (background Blender 5.2). Builds, bakes, exports, renders. `build_armor.py` is the old v1 generator, kept untouched. |
| `dragon-scale.blend` | The built scene: armor, R15 proxy (not exported), preview lights and camera. |
| `exports/fbx/dragon-scale.fbx` | All 26 meshes. `axis_forward -Z`, `axis_up Y`, embedded textures, custom normals. |
| `exports/glb/dragon-scale.glb` | The same meshes as GLB. |
| `textures/dragon-scale-{helmet,torso,arms,legs,boots}.png` | Five 1024×1024 atlases: painted colour with the lighting baked in. `textures/old-v1/` holds stale v1 textures. |
| `polygon-report-dragon-scale.json` | Triangles and vertices per mesh, per piece and in total. |
| `studio-install-data-dragon-scale.json` | For each mesh: piece, body part, kind (textured or glow), atlas, and bbox offset and size from the part centre in Studio axes. Also the ember points. |
| `validate_exports.py`, `validation-report-dragon-scale.json` | Re-imports the FBX and GLB and checks them (see Verification). |
| `pose-check-dragon-scale.json` | Intersecting-triangle counts for idle, walk, run, jump and fall. |
| `previews/` | Current renders (list below). `previews/prev-pass-0530/` holds extra renders from the previous pass: pose sheet, game camera, pauldron, legs and chest close-ups. The helm snout and the back have changed since then. |

Current renders:
- `dragon-scale-sheet.png`
- `-front`, `-back`, `-side`, `-threeq`
- `-close-helm`, `-close-back`
- `-beauty-hero` (Cycles hero shot)

## Rebuild

```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 4 --python build_dragon_scale.py
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python validate_exports.py
```

A full build takes about 8 minutes on 4 threads. The bake is about 5.5 minutes of that (16 samples
at 2048², downsampled to 1024). Environment switches:
- `QUICK=1`: flat preview colours only. No bake and no exports. Takes seconds.
- `VIEWS=front,back,...`: render only these previews.
- `NOPOSE=1`: skip the pose check.
- `POSE_IMG=0`: count pose clipping without rendering the pose images.
- `SHEET=final`: compose the small final sheet.
- `COMPTRIS=1`: print triangles per component.

## Pieces and triangles

One rigid mesh per R15 part it covers, welded to that part. Glow meshes are separate (`*_Glow`).

| Piece | Meshes (body part) | Triangles |
|---|---|---|
| Helmet | Head 6,434 + glow 92 | 6,526 |
| Chest | UpperTorso 10,548; LowerTorso 4,606; Left/RightUpperArm 4,912 each; Left/RightLowerArm 1,561 each; glow 322 | 28,422 |
| Legs | Left/RightUpperLeg 708 each; Left/RightLowerLeg 1,438 each; glow 128 | 4,420 |
| Boots | Left/RightLowerLeg cuff 622 / 620; Left/RightFoot 924 each | 3,090 |
| **Total** | 26 meshes (15 textured, 11 glow) | **42,458** |

**Budget.** The total is 42.5k triangles, over the ~35k target. The largest mesh is the
UpperTorso at 10.5k, well under Roblox's 20k per-mesh cap. The extra detail sits where it shows:
- about 250 modelled kite scales, around 35 triangles each: chest and back panels, pauldron crowns,
  helm crown and sides, shins, bracers;
- four sculpted dragon heads: the helm, both pauldrons and the belt buckle;
- 2-segment hardened bevels on the hero plates.

To get to 35k, the easiest cuts are:
- the lite, lipless scale variant on the back panels and pauldron crowns (about −2k);
- 1-segment bevels on the lames and belt (about −2k);
- fewer helm crown scales (about −1k).

## Studio install notes

- Textured meshes: MeshPart, `TextureID` = the atlas named in the install data (SurfaceAppearance
  renders blank in Play here). Material `SmoothPlastic`. Lighting is baked into the atlas.
- Glow meshes: MeshPart, Material `Neon`, Color sRGB 255,132,30.
- Weld each mesh to its `body_part`. Its bbox centre sits at `offset` from the part centre, in
  Studio part-local axes. Import at 1:1 and do not scale.
- **Ember points** (5, for ParticleEmitters) are Attachments on these parts:
  - helm mouth: Head;
  - dragon heart: UpperTorso;
  - belt-buckle mouth: LowerTorso;
  - each pauldron dragon's mouth: Left/RightUpperArm.

  Positions are in the install data.
- The helm is a full helm. It hides hair and hat accessories while worn.
- The FBX carries custom split normals (hardened bevels). Whether Studio keeps them is untested.

## Fit rules used (the body is fixed)

Modelled at final stud size on the measured R15 proxy (`r15-proxy/*.obj`). The HumanoidRootPart
centre is 3 studs above the feet.
- **Clearance.** Plates sit 0.028 studs off the body. The undersuit layer sits at 0.012.
- **Torso sides.** No thickness beyond the torso side planes (the arms touch them).
- **Legs.** Nothing on the inner leg faces. Leg plates stop 0.025 short of the centre line.
- **Hands.** No LowerTorso side plates. The thigh outer plates start below the hand bottom.
- **Elbows.** The bracer's front stays below the elbow joint. The lowest upper-arm lame flares out
  so the bracer top slides under it.
- **Knees.** The knee cop is an outer layer that rises over the thigh plate. Nothing sits on the
  lower-leg back above the knee.
- **Tassets.** They flare 0.07–0.15 studs away from the thighs.
- **Pauldrons.** They stay outboard of the arm's inner face.

## Verification (Blender only)

- **Export re-import** (`validation-report-dragon-scale.json`). FBX and GLB both OK:
  - 26/26 meshes, and triangle counts match the report;
  - no loose vertices, zero-area faces or vertex-colour layers;
  - UVs inside 0–1;
  - five 1024×1024 images embedded.

  The export step triangulates and removes bevel slivers first. Custom normals survive (checked).
- **Pose check** (`pose-check-dragon-scale.json`). The proxy's part groups are rotated about their
  rig joints. Counts are intersecting triangle pairs.

  | Pose | Pairs | Main contributors |
  |---|---|---|
  | Idle | 713 | Small contact overlaps: helm vs torso plates, knee cop vs thigh lip, last abdominal lame vs belt |
  | Walk (±35°) | 2,118 | Bracer top vs lowest upper-arm lame as the elbow bends (~320 per arm); front tassets vs swinging thigh (~170) |
  | Run (±60°) | 2,722 | Same two areas, larger |
  | Jump (arms up 150°) | 1,467 | The same two areas |
  | Fall (arms 75° out to the sides) | 2,809 | Pauldron domes swing into the helm's horns and frill (~480 per side) |

  Expect some visible clipping at the elbows and tassets while running, and at the pauldrons with
  arms raised sideways. The earlier pose renders are in `previews/prev-pass-0530/pose/`.
- **Not verified:**
  - anything in Studio or Play: welds, TextureID look, Neon bloom, custom-normal import;
  - multi-client appearance;
  - particle placement.

## Known gaps / open decisions

- **Pale body shows in some gaps.** The user kept the previous pass's coverage on purpose. The
  hands have no gauntlets, the inner limb faces have no undersuit, and the neck junction has no
  gorget, so the body shows there.
- **Back panels.** They replaced the crimson wing membrane and its three ivory finger bones. The
  wing-wrist claws above the shoulders stay. Say if the bones should come back over the scales.
- **Helm snout.** It is now one lofted piece with the helm face. In close-ups a soft crease still
  shows where the new cheek planes meet the helm's side.
- **Over budget.** See Pieces and triangles.

## Provenance

Everything is generated procedurally by `build_dragon_scale.py`. No Creator Store or third-party
assets are used.
- The fitting proxy is the R15 body measured in Studio on 2026-09-28 (`r15-proxy/`).
- Style references (`../art-references/armor-2026-09-28/`) were used for level of detail only and
  never copied.

## Changelog

- **v1** (`build_armor.py`): rounded crimson bands and a hood helm. Rejected as "pajamas".
- **Pass 1–2**:
  - new generator;
  - V breastplate with framed kite-scale pec panels and a dragon-heart gem;
  - abdominal lames;
  - belt with a dragon-head buckle;
  - undersuit layer.
- **Pass 3**:
  - superquadric dome pauldrons with scale crowns and dragon heads;
  - full dragon helm with horns, crest, jaw and eyes;
  - painterly bake (AO, cavity and bevel-edge masks);
  - triangle budget trimmed from 60k to about 41k.
- **Pass 4** (build the user reviewed at 05:30):
  - obsidian values darkened;
  - helm crown and side scales;
  - forehead plate;
  - pauldron dragon heads enlarged to face forward;
  - rest-pose clipping fixed: neck guard, leg centre line, bracer vs lames, boot cuff, belt;
  - undersuit follows the rounded limb corners.
- **Pass 5** (this build):
  - helm snout lofted out of the helm face through cheek and brow planes, so it reads as one
    sculpted piece;
  - framed kite-scale panels with gold rims on the backplate;
  - export cleanup, so validation is clean.
