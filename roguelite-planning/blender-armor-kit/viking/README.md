# Armor kit: Viking (Rare)

**Status: Blender-verified, Studio untested.** Nothing here has been imported into Roblox Studio or checked in Play.

A Norse raider, fitted to the normalized R15 body (`../r15-proxy/`). Rare rarity: more character than Common Iron, with one accent colour (blue-dyed wool). No glow, no particles, no lights.

## Design

- **Helmet (`"open"`):** a rounded iron cap on the Head, two riveted bronze bands crossing on top with a centre boss, a bronze brim band with a rivet row, a tapered nasal guard, and two chunky ivory horns growing from bronze sockets. The cap stands 0.06 studs off the head and the face is open, so hair fits.
- **Chest:**
  - dark leather jerkin on UpperTorso with four vertical iron strips (bronze rivets in rows) and a blue wool collar showing at the V neck;
  - **fur mantle**: one rounded-rectangle ring of fur around the shoulders and upper back, with an open chest V and scalloped hem, fused into a single mass (no shards or spikes);
  - fur caps over both UpperArms, a leather armband on each upper arm, and blue wool sleeves;
  - a wide leather belt with a big round bronze buckle painted with a knotwork braid, plus two bronze knotwork clasps and a slack chain on the mantle;
  - leather bracers with two iron bands on the lower arms. Hands stay bare.
- **Legs:** blue wool trousers, criss-cross leather leg bindings and a simple iron knee guard with bronze rivets.
- **Boots:** leather boot on each Foot; a leather shaft with a rounded fur roll cuff on each LowerLeg.
- **Palette:** warm brown/grey fur (dark roots, lighter tips), dark oiled leather, iron grey, bronze with brown shading, ivory horn, blue wool as the one accent. Cool shadows and warm highlights are baked in.
- **Craft:** 1-2 segment bevels, painted edge highlights on the bevels, baked AO in the overlaps, a painterly gradient inside each piece.

## Files

| File | What |
|---|---|
| `build_viking.py` | Self-contained generator (background Blender 5.2). Env: `QUICK=1` (flat colours, no bake/export), `VIEWS=a,b`, `NOPOSE=1`, `POSE_IMG=1`, `COMPTRIS=1`, `EXTRA=1` (extra close-ups to `previews/_tmp`). |
| `viking.blend` | The built scene (armor, proxy, preview lights). |
| `exports/fbx/viking.fbx`, `exports/glb/viking.glb` | 15 meshes. FBX: `axis_forward -Z`, `axis_up Y`, embedded textures. |
| `textures/viking-{helmet,body,legs}.png` | Three 1024x1024 atlases (baked at 1024, 8 samples). |
| `polygon-report.json`, `studio-install-data.json` | Triangles per mesh; per-mesh atlas, body part, offset and size. `"helmet": "open"`, `glow_color_srgb: null`. |
| `validate_exports.py`, `validation-report.json` | Re-imports the FBX and GLB and checks them. |
| `pose-check.json` | Intersecting-triangle counts per pose. |
| `previews/` | `viking-front/back/side/threeq/close-helm.png` and `sheet.png`. |

Rebuild: `"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 --python build_viking.py`
(about one minute; the bake is about 45 seconds).

## Triangles

| Piece | Meshes | Triangles |
|---|---|---|
| Helmet | Head 3,142 | 3,142 |
| Chest | UpperTorso 3,306; LowerTorso 1,362; Left/RightUpperArm 1,028 each; Left/RightLowerArm 796 each | 8,316 |
| Legs | Left/RightUpperLeg 244 each; Left/RightLowerLeg 838 each | 2,164 |
| Boots | Left/RightLowerLeg cuff 604 each; Left/RightFoot 630 each | 2,468 |
| **Total** | 15 meshes | **16,090** |

Largest mesh: UpperTorso at 3,306 (limit 20k). Atlases: helmet (1 mesh), body (6 meshes), legs (8 meshes).

## Studio install notes

- MeshPart, `TextureID` = the atlas in the install data, Material `SmoothPlastic`. Weld each mesh to its `body_part`; its bbox centre is at `offset` from the part centre in Studio axes. Import at 1:1.
- Set the helmet mode to `open`: the face shows and hair must stay visible.
- The FBX carries custom split normals (hardened bevels). Whether Studio keeps them is untested.

## Verification (Blender only)

- **Export re-import** (`validation-report.json`): FBX and GLB both OK. 15/15 meshes, triangle counts match, no loose vertices or zero-area faces, no vertex-colour layers, UVs inside 0-1, three 1024x1024 images.
- **Pose check** (`pose-check.json`, intersecting triangle pairs; no pose images):

  | Pose | Pairs | Main contributors |
  |---|---|---|
  | Idle | 1,144 | Mantle top vs the Head body (155, constant in every pose); boot cuff / knee guard vs trousers (about 120 per leg) |
  | Walk | 1,912 | Lower-arm bracer vs upper-arm armour at the elbow (about 150-180 per arm) |
  | Run | 2,490 | Same elbow overlap (about 200 per arm); LowerTorso belt vs the thigh body (167) |
  | Jump | 1,860 | Mantle vs Head; leg cuff vs trousers; elbows |
  | Fall (arms out 75 deg) | 2,112 | Helm horns/sockets vs the upper-arm fur caps (about 197 per side) |

  Expect small visible clipping at the elbows and knees while running, and the horns brushing the fur caps with arms raised to the side.

## Known gaps

- The fur mantle reads as a smooth, thick pelt with a scalloped hem; it has no fibre-level modelling by design. A small flap of hem near each side of the chest V is still slightly ragged in close-ups.
- The horn rings are subtle facets; they are not strongly ringed.
- The boots are plain boxes with a toe cap and a fur roll; there is no sole or lacing geometry.
- Tri total (16.1k) is at the top of the 14-16k target.
- Not verified: anything in Studio or Play (welds, TextureID look, custom-normal import, multi-client appearance).

## Provenance

Everything is generated procedurally by `build_viking.py`. No Creator Store or third-party assets. The pipeline (proxy loading, shells, bake, export) is copied from `../build_dragon_scale.py`.
