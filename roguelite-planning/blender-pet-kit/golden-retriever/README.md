# Golden Retriever pet

The style-sample pet for the roguelite: a **Common** pet whose strong suit is **Loot** (it runs out
and fetches crystals). It follows the player into runs. Rarity only changes flashiness, so a Common
pet has no glow and no Neon parts, just the model. Spec: `../../RARITY_GODLY_ARMOR.md` sections 11
and 13.

This folder holds only the art asset: the model, exports, texture and previews. There is no Studio
or game code here.

**Status: Blender-verified, Studio untested.** The exports re-import cleanly in Blender 5.2
(`validation-report.json`, PASS for FBX and GLB). Nothing has been imported into Roblox Studio, so
the import, texture colour, pivots and joints in Studio are all unchecked.

## Look

Style follows `../../art-references/ART_DIRECTION_USER_2026-09-17.txt`: stylized low-poly, chunky
readable silhouette, soft faceting, painterly low-noise baked texture.

- **Proportions:** a chibi puppy. Big round head, short chunky legs, big paws with four modelled
  toes and dark toe beans, an up-curled plume tail.
- **Fur is fused into the coat.** Each furry part (body, head, legs, tail) is ONE smooth surface:
  - body: the chest ruff and belly fringe are the coat growing outward, ending in a soft hem with
    a few broad waves;
  - legs: the paw, toes and the feathering on the back of the forearm / thigh are fused into the
    leg with fillets;
  - head: the muzzle, lower jaw and cheeks flow out of the skull (gentle stop, no seam) and the
    open smiling mouth is carved into that surface;
  - tail: one plume, thickest along the front, fuller and cream on the feathered back edge, ending
    in a soft point.

  Colour is painted by 3D position and a fur-length gradient, so there is no colour step at any
  join.
- **Face, painted over shallow relief** (modelled sockets read as sunglasses in this project):
  - big glossy brown eyes with two catchlights;
  - arched brows;
  - a black modelled nose with a painted shine and nostrils;
  - an open happy mouth with a dark interior;
  - a round pink tongue with a centre groove;
  - lip and smile lines and whisker dots.
- **Loot adventurer kit:**
  - a red polka-dot bandana (knot on the dog's left);
  - a gold ring with a blue crystal tag on the collar (a separate part, so it can dangle);
  - a small leather satchel on the dog's right flank, with loot crystals peeking out, carried by a
    girth strap with a gold buckle.

  The crystals match the game's crystal shard. They are painted colour, not glow.
- **Colour:**
  - warm gold coat;
  - darker honey along the back, crown and tail top, and toward the ear tips;
  - cream muzzle, cheeks, chest, belly and lower legs;
  - broad painted brush strokes following the fur direction;
  - cool shadows in the crevices.

  Lighting is baked into the texture icon-style, like the approved chest kit: per-facet key light,
  AO, cool shadows and a cool rim.
- **Head variants:** two were tried early (`--variant A|B`). A has a shorter muzzle and cream brow
  spots, B a slightly longer muzzle and arched brown brows. **B is kept**, because A's brow spots
  vanished at any distance.

## Size (1 Blender unit = 1 stud, import 1:1, do not scale)

| | Studs |
|---|---|
| Height to the head top | 2.22 |
| Length, nose to tail plume | 2.68 |
| Width, ear to ear | 1.30 |

The paws stand on z = 0. The pad domes reach 0.0008 below it, which is negligible. A Roblox player
is about 5 studs tall; see `previews/scale-vs-5stud-r15.png`.

## Parts and pivots

There are ten rigid mesh parts. They share **one material and one 1024x1024 texture**
(`textures/golden-retriever.png`), so every MeshPart uses the same TextureID. Rotation is 0,
scale is 1, and each object's origin is its joint pivot. L and R are the dog's own left and right;
its left is Blender +X, which is Studio -X. Studio axes are (-x, z, y) of Blender, so the dog faces
Studio -Z.

| Part | Tris | Pivot (Blender) | Pivot (Studio) | Pivot from body pivot (Studio) | Joint parent | Moves by |
|---|---|---|---|---|---|---|
| `Retriever_Body` | 4,534 | (0, 0, 0.96) | (0, 0.96, 0) | (0, 0, 0) | root | bob, small roll |
| `Retriever_Head` | 1,967 | (0, -0.54, 1.36) | (0, 1.36, -0.54) | (0, 0.40, -0.54) | Body | nod, tilt, turn at the neck |
| `Retriever_EarL` / `R` | 412 each | (±0.36, -0.74, 2.05) | (∓0.36, 2.05, -0.74) | (∓0.36, 1.09, -0.74) | Head | flop at the ear root |
| `Retriever_LegFL` / `FR` | 730 each | (±0.25, -0.32, 0.92) | (∓0.25, 0.92, -0.32) | (∓0.25, -0.04, -0.32) | Body | swing at the shoulder |
| `Retriever_LegBL` / `BR` | 818 each | (±0.26, 0.36, 0.96) | (∓0.26, 0.96, 0.36) | (∓0.26, 0, 0.36) | Body | swing at the hip |
| `Retriever_Tail` | 1,150 | (0, 0.62, 1.16) | (0, 1.16, 0.62) | (0, 0.20, 0.62) | Body | wag at the tail root |
| `Retriever_CrystalTag` | 210 | (0, -0.917, 1.129) | (0, 1.129, -0.917) | (0, 0.169, -0.917) | Body | dangle from the collar ring |

- **Total: 11,781 triangles.** That is over the first ~5k brief on purpose, because the raised
  detail brief allowed about 12k. Every part is far below Roblox's 20k per-mesh cap.
- `polygon-report.json` has the exact counts, bounding boxes, UV ranges and pivots.
- `studio-install-data.json` gives, per part and in Studio axes:
  - `center` and `size`;
  - `pivot` and `pivot_from_body_pivot`;
  - `joint_parent` and a `suggested_motion` note;
  - plus `ground_point`, `overall_size` and `overall_center` for the whole model.

  Suggested rig: one Motor6D per part, with Part0 = joint parent, Part1 = the part and C0/C1 at
  the pivot. An installer can place each MeshPart at `origin * CFrame.new(center)` and set
  `PivotOffset = CFrame.new(pivot - center)`, whatever Studio's importer does with mesh origins.
  No installer script exists yet.
- **Joints overlap so rotations show no gaps.** The leg tops, neck, ear roots and tail root sit
  inside their parent. `previews/pose-check.png` rotates each part about its own pivot:
  - trot ±28°;
  - gallop reach ±30°;
  - head tilt 22° with an 18° nod;
  - head up 22° with a 28° turn;
  - tail wag 30°;
  - ear flop 20-25°;
  - tag swing 30°.
- **Armature:** the `.blend` also has a Blender armature (`Retriever_Rig`, one bone per part at its
  pivot, parts bone-parented) used for the pose previews. The FBX and GLB export only the plain
  rigid mesh parts, with no armature. No animations are included.

## Rebuild

```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 4 --python build_golden_retriever.py
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python validate_exports.py
```

- `build_golden_retriever.py` builds everything from scratch and uses no code from sibling kits.
  - It writes `golden-retriever.blend`, the texture, both exports, `polygon-report.json`,
    `studio-install-data.json` and the previews.
  - A full run takes about 5 minutes with `--threads 4`.
  - `-- --quick --out <dir>` is the iteration mode: a 1024 bake, a few Eevee views and no exports.
  - `-- --no-previews` skips the renders.
- **Geometry:**
  - Base forms are lofts of superellipse rings.
  - Fused fur: each furry part's base lofts and fur volumes become signed distance fields
    (OpenVDB, bundled with Blender), joined with smooth unions (real fillets), meshed, decimated,
    then evened out on the surface so no sliver triangles are left.
  - The satchel, buckle and tag parts have 2-3 segment soft bevels.
  - Shading uses smooth-by-angle plus weighted normals.
  - Every closed shell is checked for outward normals.
  - Faces buried inside another shell of the *same* part are deleted, since they can never be seen
    in any pose. Buried faces are never culled against other parts, so poses cannot expose holes.
- **Texture method:**
  1. All parts are unwrapped into one atlas. The face gets a denser cylindrical island.
  2. Cycles bakes these maps at 2048: world position, smooth and per-face normals,
     zone/part/fur-gradient attributes, two AO radii, pointiness and a bevel-edge mask.
  3. numpy paints the colour and the baked icon lighting from those maps, then downsamples the
     result to 1024.

  Because the painting is driven by 3D position, colours continue across UV seams and across the
  fur-shell roots.
- `validate_exports.py` re-imports the FBX and the GLB and checks them against the reports:
  - exactly the ten named parts;
  - triangle count per part;
  - world bounding box and dimensions per part;
  - each origin on its pivot;
  - UVs inside 0-1;
  - no zero-area triangles;
  - one shared 1024 image;
  - height and length inside the brief;
  - the install data matches the pivots in Studio axes.

  It writes `validation-report.json`.

## Previews (real Blender 5.2 Eevee renders)

- `three-quarter.png`, `front.png`, `side.png`, `back.png`
- `face-closeup.png`, `face-side.png`
- `scale-vs-5stud-r15.png`: true-scale orthographic, beside a grey 5-stud R15 block figure. The
  figure and labels exist only in the render.
- `gameplay-view.png`: a guess at a high game camera, 70° vertical FOV about 16 studs away. The real
  camera was not measured.
- `pose-check.png`: the joint pose sheet.
- `golden-retriever-sheet.png`: the contact sheet.

The Cycles hero shots from earlier passes were removed, because they showed the old spiky fur.

## Provenance

Everything is generated procedurally by `build_golden_retriever.py`: geometry, texture and
previews. No external models, images or Creator Store assets are used. Design references were:

- the project art direction file;
- the approved chest kit's baked icon lighting (`../../blender-chest-kit/`), for the look;
- the derp chicken kit (`../../blender-derp-chicken/`), for the part and pivot convention;
- the game's crystal shard (`../../crystal-shard/`), for the crystal shape and colour only.

## Open issues

- **Not seen in Studio.** Roblox lighting and the game's +0.3 saturation will shift the golds and
  creams; judge the colour there.
- The FBX importer may re-centre mesh origins. The install data is written so pivots can be set
  explicitly either way.
- The leg feathering flaps are thin and read best from the side. From straight behind, the pants
  are subtle.
- The back of the head is a plain painted dome. A crown tuft and a nape fringe were tried and
  looked like a comb and like plates, so they were dropped.
- The bandana dots render as short dashes on the slanted cloth.
- The mouth reads as an open panting smile. In a pure side view the jaw still looks a little
  duck-billed.
- The texture has baked directional lighting (key from the front-left). A pet that turns around in
  game keeps that baked light direction.

## Changelog

- **2026-09-29, blend pass.** The owner said the add-ons looked thrown together (a dinosaur-plate
  tail, a beak-like snout, rough fur flaps). Every add-on is now fused into its part as one smooth
  surface; see "Fur is fused into the coat" above. Rig, pivots, names, palette, eyes, nose,
  bandana, satchel and tag are unchanged. `validate_exports.py` passes.
  - Re-rendered this pass: `side.png`, `three-quarter.png`, and the new `closeup-tail.png` and
    `closeup-face-side.png`. `front.png`, `back.png`, `face-*.png`, `scale-vs-5stud-r15.png`,
    `gameplay-view.png`, `pose-check.png` and the sheet still show the previous version (a full
    run without `-- --views-min` regenerates them). The previous previews are kept in
    `previews/before-blend-pass/`.

