# Armor kit: Ninja (Rare)

**Status: Blender-verified, Studio untested.** Nothing here has been imported into Roblox Studio or checked
in Play. Fit, clipping and texture notes come from Blender only.

A shinobi in layered dark cloth, black lacquered leather and a few gunmetal steel splints. Crimson is the
one accent colour (sash, cords, headband and hood lining). No glow, no gold, no particles, no lights.

## Design

- **Helmet (`"hood"` mode).** A cloth hood over the whole head, so hair and hats are hidden. The face shows
  only through an eye slit.
  - Steel forehead plate (hachigane) with two rivets, tied on by a crimson headband.
  - The headband knot sits at the back, with two short, thick, rounded tails blended into it.
  - A slate face mask covers the lower face, with a rolled top edge.
  - A crimson lining pipes the eye slit.
  - A thick wrapped neck scarf breaks the round head outline.
- **Chest.**
  - A cross-over wrapped cloth tunic on the UpperTorso, with soft fold ridges and a lighter lapel trim. The
    V-neck shows the dark undershirt. The back has its own soft folds.
  - A small lacquered leather chest guard of two overlapping lames (a matching small one on the back).
  - A wide crimson sash across the UpperTorso and LowerTorso, with a chunky knot and two short tails on the
    front of the wearer's left hip. The knot stays inside the torso side planes, so the swinging hands never
    touch it.
  - Upper arms: a gathered cloth sleeve tied with a crimson cord above the elbow, a slate cloth guard layer,
    and a black leather cap layer over the shoulder.
  - Lower arms: bands of wrapped cloth (bracers) with three steel splints (kote) and a crimson wrist cord.
- **Legs.** Loose trousers puffed at the thigh, gathering over the knee and tied with a crimson cord into
  wrapped shins (kyahan). Three steel splints run down each shin, with a small leather knee pad.
- **Boots.** Tabi-style: a dark cloth boot on each Foot with a split toe (a big-toe lobe and a four-toe lobe
  with a cleft between them), and a wrapped cuff on the LowerLeg. The sole is painted black in the atlas.
- **Craft.** Cloth edges are thick and rounded (1-segment bevels, soft shading). Steel and leather have
  1-segment hardened bevels with a painted edge highlight. Baked AO sits in every fold and overlap, and
  each piece has a painterly gradient with cool blue-violet shadows.

## Files

| File | What |
|---|---|
| `build_ninja.py` | Self-contained generator (background Blender 5.2). It reads only `../r15-proxy/*.obj`. |
| `ninja.blend` | The built scene: armor, R15 proxy (not exported), preview lights and camera. |
| `exports/fbx/ninja.fbx`, `exports/glb/ninja.glb` | 15 meshes. FBX uses `axis_forward -Z`, `axis_up Y` and embedded textures. |
| `textures/ninja-{helmet,torso,legs}.png` | Three 1024x1024 atlases, baked with 8 samples. |
| `polygon-report.json`, `studio-install-data.json` | Triangle counts. Install data for Studio (`"helmet": "hood"`, no glow parts). |
| `validate_exports.py`, `validation-report.json` | Re-imports the FBX and GLB and checks them. |
| `pose-check.json` | Intersecting-triangle counts for idle, walk, run, jump and fall (numbers only, no pose images). |
| `previews/` | `front`, `back`, `side`, `threeq`, `close-helm` and `sheet.png`. |

Atlases: `helmet` (Head), `torso` (UpperTorso, LowerTorso, all arm meshes) and `legs` (leg and boot meshes).

## Rebuild

```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 --python build_ninja.py
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python validate_exports.py
```

A full build takes about one minute. Switches: `QUICK=1` (flat colours, no bake or export), `VIEWS=a,b`,
`NOPOSE=1`, `DBG=1` (extra close-ups into `previews/_dbg`).

## Triangles

| Piece | Meshes (body part) | Triangles |
|---|---|---|
| Helmet | Head 2,274 | 2,274 |
| Chest | UpperTorso 2,094; LowerTorso 904; Left/RightUpperArm 1,134 each; Left/RightLowerArm 844 each | 6,954 |
| Legs | Left/RightUpperLeg 328 each; Left/RightLowerLeg 1,294 each | 3,244 |
| Boots | Left/RightLowerLeg cuff 292 each; Left/RightFoot 470 each | 1,524 |
| **Total** | 15 meshes | **13,996** |

Largest single mesh: Ninja_Helmet_Head at 2,274 (Roblox cap is 20k).

## Studio install notes

- Every mesh is a MeshPart with `TextureID` set to the atlas named in `studio-install-data.json`. Material
  `SmoothPlastic`; the lighting is baked into the atlas. There are no Neon or glow meshes.
- Weld each mesh to its `body_part`. The bbox centre sits at `offset` from the part centre in Studio
  part-local axes. Import at 1:1 and do not scale.
- The hood hides hair and hats. Set the helmet mode to `hood`: the eye slit lets the player's own eyes show.
- The FBX carries custom split normals (from the hardened bevels). Whether Studio keeps them is untested.

## Fit rules used

Modelled at final stud size on the measured R15 proxy. Plates and cloth sit 0.028 studs off the body (0.012
for the undershirt). Nothing sits on the inner leg or arm faces, nothing sticks out past the torso side
planes, and the LowerTorso has no side plates where the hands swing. The bracer front stays below the elbow
joint. The sleeve cuff flares so the bracer top slides under it. The back of the thigh trousers and the back
of the calf both stop about 0.02 studs short of the knee joint (this closes the pale back-of-knee gap, but
those two ends can touch when the knee bends far).

## Verification (Blender only)

- **Export re-import** (`validation-report.json`): FBX and GLB both OK. 15/15 meshes, triangle counts match,
  no loose vertices or zero-area faces, no vertex-colour layers, UVs inside 0-1, three 1024x1024 images.
- **Pose check** (`pose-check.json`): intersecting triangle pairs after rotating the proxy's part groups
  about their rig joints.

  | Pose | Pairs |
  |---|---|
  | Idle | 1,793 |
  | Walk | 2,640 |
  | Run | 3,364 |
  | Jump | 2,321 |
  | Fall | 2,773 |

  About 970 of the idle pairs are static contacts that are by design: the hood and scarf overlapping the
  tunic top, and the sash meeting itself at the waist. The rise while moving comes from the bracer against
  the sleeve cuff and the shoulder guards against the torso.
- **Not verified:** anything in Studio or Play (welds, TextureID look, custom-normal import), multi-client
  appearance, and the look of the eye slit against real faces.

## Known gaps

- The hands are bare, and the inner faces of the arms and legs are bare (fit rules), so a little of the pale
  body shows there.
- The hood follows the R15 head, which is a round drum, so it reads slightly bucket-like from the front.
  The scarf, headband and tails are what break it up.
- The atlases were baked at 1024 with 8 samples, so there is slight grain in the ambient occlusion.
- The back leather guard is black on dark cloth and reads as a dark patch at a distance.

## Provenance

Everything is generated procedurally by `build_ninja.py`. No Creator Store or third-party assets.
