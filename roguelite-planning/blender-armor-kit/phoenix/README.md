# Phoenix armor set v2 (Godly)

**Blender-verified, Studio untested.** Rebuilt 2026-09-29 in Blender 5.2 (background mode). v1 renders are in
`previews/v1/`; `previews/v1-vs-v2.png` shows v1 front | v2 front | v1 threeq | v2 threeq.

## What changed from v1
The owner said v1 was less cool than Dragon Scale: a plain white texture, tiny wings, thin feathers, a small beak and minimal VFX.
- **Colour:** rich gold is now the main metal. It is shaded brown/orange with warm highlights, never flat yellow.
  - Deep crimson/orange enamel inlays carry painted gold cloisonné flames.
  - The rubies are new.
  - Ivory is almost gone.
- **Surface detail on every plate.** The bake paints relief through a bump-lit "Motif" pass:
  - engraved border grooves with a raised bead;
  - sun-ray engravings;
  - embossed feather scallops (breastplate, thighs);
  - radial engravings on the discs;
  - enamel flame panels.

  The real-geometry relief is:
  - the filigree bead and rims;
  - gold eye-streak feathers on the helm;
  - sunburst ray plates on the chest.

  The bake also has stronger AO and cavity shading, plus painted edge highlights.
- **Feathers:** every feather is thick and rounded, layered 2–3 deep in graded rows.
  - Each one carries the gradient: crimson root → orange → gold → hot-yellow tip.
  - Each one has painted vane stripes, a gold rachis, chevron barbs and a bright edge.
  - A per-feather tone runs from golden (top tiers) to deep crimson (lower tiers).
- **Helm:**
  - a big hooked beak (projects ~0.5 studs; its culmen continues the crown keel);
  - heavy gold V-brows over deep sockets, with large hot-yellow eyes;
  - enamel cheek guards with rubies;
  - cheek plumes, brow tufts and a nape mane;
  - a three-layer crest of 21 feathers, with the spine 1.24 studs above the head (measured).
- **Wings (new mesh `Phoenix_Chest_Wings`, body_part UpperTorso).** They grow from a gold back medallion.
  - Structure: a segmented gold wing-arm with a glowing leading edge, and rubies at the elbow and wrist.
  - 31 feathers per wing: 6 primaries with Neon tips and hot flame cores, 7 secondaries, 15 coverts and 3 scapulars.
  - Silhouette: a V, with tips 1.21 studs above the head and a 4.94 stud span (measured from the export bounds).
- **Pauldrons:**
  - a gold dome;
  - a three-tier mantle (16 feathers);
  - a gold sun-disc cap with a ruby;
  - a 5-feather flame crest sweeping up, out and back.
- **Chest:**
  - a radiant sun core: a hot Neon gem, five talons, 10 gold ray plates and 7 glowing rays;
  - plumage in the pec recesses;
  - a scalloped gold collar with 5 rubies;
  - enamel abdominal lames.
- **Waist and legs:**
  - Two-tier feather tassets and a glowing two-tier phoenix tail.
  - Layered gold-and-enamel thigh plates and greaves.
  - Feather flares at the elbows, knees and ankles.
  - Talon boots with 3 big gold claws, a side talon and a heel spur.
- **VFX:** two Neon colours (orange 255,150,40 and hot yellow 255,214,96) and a 30-entry particle/light list (below).

## Triangles (47,886 total; 6 atlases at 1024)
| Mesh | Textured | _Glow | _Hot_Glow |
|---|---|---|---|
| Helmet_Head | 5,730 | 520 | 264 |
| Chest_UpperTorso | 10,242 | 170 | 68 |
| Chest_Wings | 6,512 | 696 | 408 |
| Chest_LowerTorso | 4,194 | 500 | 166 |
| Chest_Left/RightUpperArm (each) | 4,248 | 200 | 136 |
| Chest_Left/RightLowerArm (each) | 920 | 16 | – |
| Legs_Left/RightUpperLeg (each) | 960 | – | – |
| Legs_Left/RightLowerLeg (each) | 1,244 | – | – |
| Boots_Left/RightLowerLeg | 545 / 543 | – | – |
| Boots_Left/RightFoot (each) | 940 | – | – |

- **By piece:** Helmet 6,514 · Chest 33,996 · Legs 4,408 · Boots 2,968.
- **Largest mesh:** UpperTorso, 10,242 (under the 20k limit).
- **Atlases:** `textures/phoenix-{helmet,torso,wings,arms,legs,boots}.png`, baked at 1024 with 16 samples.

## VFX (`studio-install-data.json` → `"vfx"`)
Each entry has:
- full ParticleEmitter properties (see `vfx_notes` in the JSON for how to apply them);
- the attachment `position`, `secondary_axis` and `axis` in part-local Studio axes;
- its `body_part` and `piece`.

The entries:
- **Flame plumes (11):** 3 on the crest, 1 on each pauldron, and 3 on the top primaries of each wing.
- **Flame sheet (8):** 4 along each wing's leading edge, VelocityParallel.
- **Flame licks (3):** the two front tassets and the tail.
- **Rising embers (3):** each wing and the back medallion.
- **Ember swirl (1):** around the sun core.
- **Heat glow (2):** soft Box-volume glow on the UpperTorso and LowerTorso armour.
- **PointLights (2):** the core (Brightness 2.4, Range 12) and a soft one between the wings (Brightness 1.2, Range 10).

Particle textures are painted with numpy in the generator:
- `textures/vfx/flame.png` (512): a chunky cartoon flame, white-yellow core → orange → transparent edge;
- `textures/vfx/ember.png` (256).

Budget: about 300 particles are alive per player; the notes say to halve Rate on low graphics quality.

## Previews
- Eevee: `front`, `back`, `side`, `threeq`, `close-helm`.
- `game-behind`: FOV 70, 16:9, 18 studs behind and above, with flame cards.
- `hero`: Cycles, dark backdrop. It shows emissive flame/ember cards at every emitter spot, both lights and bloom.
- `sheet.png` combines them.

The flame cards exist only in the preview scenes; they are never exported.

## Pose check (intersecting triangle pairs; v1 in brackets)
| Pose | v2 | v1 |
|---|---|---|
| idle | 936 | 1,148 |
| walk | 3,295 | 2,537 |
| run | 3,822 | 3,877 |
| jump | 2,249 | 1,734 |
| fall | 4,561 | 3,691 |
| head turn +60° | 944 | – |
| head turn −60° | 928 | – |

- **Wings:** they touch no other part's armour or body in any pose. The smallest helm-to-wings gap is 0.249 studs in every pose, including both head turns.
- **Biggest pairs:**
  - walk/jump/fall: tassets vs thighs, up to 833 in the jump;
  - fall (arms 75° out): each pauldron crest swings into the helm, ~534 each;
  - run: vambrace vs upper-arm plates, ~225 per side;
  - rest: the helm rim vs the collar, 140.

## Files
- `build_phoenix.py`: a self-contained generator (the Dragon Scale pipeline is copied, not imported). Env options:
  - `QUICK=1`: flat colours, no bake.
  - `NOPOSE=1`: skip the pose check.
  - `VIEWS=a,b`: render only these views.
- `exports/fbx/phoenix.fbx` and `exports/glb/phoenix.glb`.
- `phoenix.blend`.
- `polygon-report.json`, `studio-install-data.json` and `pose-check.json`.
- `validate_exports.py` → `validation-report.json`: FBX, GLB and install data all pass (re-import, triangle counts, UVs in 0–1, no loose vertices or slivers, vfx completeness).

## Known issues / left to do
- **Helm texture seam.** A blocky noise patch shows on the helm's face beside the beak. The helm's painted-ray coordinate wrapped at the front centre. `build_phoenix.py` is already fixed (the coordinate is now symmetric), but the shipped textures predate the fix. One re-run of the generator (~3.5 min) clears it.
- **Sliver cleanup.** The shipped exports had 615 near-zero-area faces removed from UpperTorso after the bake. They were the tiny centre rings of the pec floors and the core disc, hidden under the plumage and the gem. The generator's `clean_mesh` now uses the same 1e-7 threshold.
- **Fall and tasset clipping.** The fall pose and the tassets clip more than v1, because the crests and tails are bigger.
- **Crest height.** The crest reaches 1.24 studs above the head, a little under the ~1.5 target.
- **Hero crest.** In the hero render the crest plumes' flame cards hide most of the helm crest.
- **Studio:** untested. Particle look, the attachment axes and Neon bloom still need a Studio pass.
