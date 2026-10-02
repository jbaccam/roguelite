# Reference rebuild candidates

These nine mobs replace the rejected generic constructions for visual review. They are **not an identical reproduction of the AI sheets**, and have not received user approval or Studio gameplay validation. Original concept images remain in the parent mob directories. The earlier meshes remain available for comparison.

Open `review.html` through the existing local server at `http://127.0.0.1:8814/reference-rebuilds/review.html`.

| Mob | Reconstruction |
|---|---|
| Snake | Continuous swept skin with a stable frame, individual dorsal scales, curved belly scutes, a separate head, jaw and fangs; 16 articulated spine segments. |
| Rock Throwing Crab | Custom carapace, eight articulated legs and raised pincers enclosing a stone. The held stone is a separate mesh; `RockProjectile.fbx` and `.glb` contain its standalone geometry. |
| Skeleton | Rebuilt skull and ribs, angular bone shafts, a palm behind the sword handle, four bent fingers and an opposing thumb. |
| Bow Skeleton | Visible flax string with a weighted draw point, timed raise/draw/release motion, shoulder cloth and quiver. Separate textured arrow asset; no permanent arrow in the character's hand. Release begins at frame 15. |
| Fire Goblin | Short, broad body, bare arms and feet, pointed ears, sleeveless torn tunic; tapered steel dagger with a raised ridge, honed edges, swept guard, wrapped grip and pommel. |
| Lava Slime | Asymmetric molten body with irregular raised basalt chunks, conforming facial geometry, two deforming body bones. |
| Obsidian Ogre | Continuous chest, deeper torso and large upper back/traps; integrated thigh/knee/shin forms, solid mitten fists with a tucked thumb, broad flat-ended feet and a projecting underbite. |
| Ash Shaman | Deep, enclosed hood with a shaped opening, bent elbows, robe sleeves and cuffs, individually modeled fingers around the staff. |
| Spitter Zombie | Heavy abdomen, swollen cheeks, open mouth, uneven teeth, fitted tattered shirt and shorts, continuous skin. |

## Files per mob

- `Sculpt.blend`: procedural, editable modeling source with neutral review lighting.
- `Model.blend`: rig, baked UV texture, mesh and five actions. The `REVIEW_ONLY` collection holds the camera, lights and floor; it is excluded from exports.
- `Model.fbx`: rest mesh, skeleton and embedded base-color texture.
- `Model.glb`: textured mesh and five named animation clips.
- `animations/{Idle,Move,Attack,Hit,Death}.fbx`: armature-only clips at 24 fps.
- `BaseColor.png`: unique 2048-square baked atlas.
- `Normal.png`: Ogre-only 2048-square tangent-space stone surface map, included in the revised materials and GLB.
- `Rigged.png`, `Attack.png`: actual renders of the baked rig, not AI artwork. `Preview/Front/Side/Back.png` show the procedural sculpture. Grip and movement details are included where rendered.
- `Rig.json`: geometry counts, skin checks and intended attack event timing.
- `ExchangeChecks.json`: fresh FBX/GLB reimport checks and hashes of the tested files.

## Validation and remaining work

The exchange checks verify actual reimported mesh counts, bones, normalized weights with at most four influences, UVs, a loaded texture and bone motion in every FBX clip. Source checks require closed geometry and fewer than 20,000 triangles per exported mesh. Some characters use multiple meshes and have substantially higher total triangle counts; arena population performance and LODs still need testing.

Visual inspection covered rest, attack and grip renders, with sampled movement/death poses. These checks do not establish exact reference fidelity, intersection-free motion throughout every frame, or gameplay correctness. The materials, facial likenesses, surface treatment and some anatomy still differ from the concept sheets.

No Studio content or gameplay code was changed. Import scale, live animations, server-owned hit timing, projectile spawning/release, collision, multiplayer and device performance remain unverified. The existing user-made Pine Valley zombies and boss files are preserved. The other regular mobs were not revised in this nine-mob pass.

## Rebuilding

Run each `build_*.py` using Blender 5.2 in background mode. `build_skeletons.py` takes `-- skeleton` or `-- bow-skeleton`. Then run `rig_export.py -- <mob>`, `polish_rig.py -- <mob>`, and `verify_exports.py -- <mob>`. The sculpture scripts specify different shapes and joint positions; `meshlib.py` contains geometric helpers, not a shared humanoid body template. `make_review.py` regenerates the comparison page.

Keep the source review renders and baked rig renders clearly labeled. Never replace them with the target AI images to imply greater mesh fidelity.

## Hand and stone correction

The Skeleton, Bow Skeleton, Fire Goblin and Ash Shaman grips have been rebuilt with the palm behind the handle, four bent fingers and an opposing thumb. The Goblin's forearms taper into exposed wrists rather than swallowing the hands. The archer's drawing hand is empty; stored arrows remain in the quiver. These simple hands are weighted to the hand bones; individual finger animation is not provided.

The Ogre has harder chest planes, a rough stone material baked to color and normal maps, separate thumb shapes, squared toe ends and a stronger lower jaw. Earlier files are preserved under `history/before-hand-stone-correction/`. This correction affects five mobs; the other four reference rebuilds are unchanged.

## Ogre volume rebuild (supersedes the preceding Ogre hand/stone pass)

The separate finger blocks, attached chest plates and round knee primitives were rejected. `ogre_anatomy.py`, called by `build_ogre.py`, now constructs continuous torso and limb surfaces from interpolated anatomical sections. Pectorals and upper-back mass are shaped directly into that skin; the limb roots are blended into the torso. The two fists are solid chamfered mittens with one tucked thumb, without individual finger blocks.

At the sampled chest section, depth increased from 1.834 to 2.506 source units (36.7%). Body geometry increased from 7,388 to 19,694 triangles. The upper back and traps slope from the thick torso into the neck, and the knees transition continuously between thigh and shin. `VolumeChecks.json` records the measurements. The belt and hanging hide were refitted to the larger body. Earlier files remain under `history/before-ogre-volume-rebuild/`.

The Ogre's skin weights now use anatomical torso/limb regions, with blended shoulders, elbows and knees. This prevents the broader chest from inheriting upper-arm weights simply because it is close to the shoulder bones. The revised rig is sampled in rest, attack, movement and death poses.

## Dagger and shooting correction

The Goblin's dagger has a new diamond-section blade, narrow cutting bevels, a pointed taper and a swept guard. Its orientation is superseded by the transverse hand grip described below.

The Bow Skeleton has a thicker, light flax string, attached at both bow tips and weighted to `BowDraw` at its center. `Attack` raises the bow, pulls the string with the right hand, releases at frame 15 and returns to rest. The source clip runs at 24 fps; release time is `(15-1)/24`, approximately 0.583 seconds after playback starts. Blender action markers name Draw, FullDraw and Release; importers may require recreating these markers from the frame numbers.

`bow-skeleton/ArrowProjectile.{blend,fbx,glb}` contains a separate 1.90-unit arrow with a wooden shaft, three feather vanes and a steel head. `ArrowBaseColor.png` is its packed 512-square atlas. Its source-space origin is the nock and its forward axis is local -Y. It is not permanently attached to the character.

`ShootingDemo.blend` combines the actual rig with that separate arrow for an animated demonstration. `Shooting.gif` is slowed for inspection. The demonstration arrow appears during draw, leaves the string at release and flies forward. `ShootingChecks.json` records string-to-hand contact and the evaluated string geometry; `ArrowChecks.json` records fresh FBX/GLB arrow imports. Gameplay spawning, damage and Studio integration are outside this requested animation-and-asset correction.

In the demonstration, the arrow's nock sits 22% along the upper string segment, above the drawing fingers. Its shaft passes 0.34 source units above the bow grip and 0.18 units beside the stave. It does not pass through the bow hand or through the wooden bow. These attachment offsets are also recorded in `ShootingChecks.json`.

## Fire Goblin hand anatomy, revision 6

The rectangular palms and stacked finger bars were replaced. `goblin_hands.py` builds a continuous wrist/palm loft, four curled finger pads with staggered knuckles, and an opposing thumb with a connected web. Both hands are blended into the body skin, removing the overlapping wrist pieces. Shallow underside creases separate the finger pads without dividing the fist into loose blocks.

The right grip is transverse to the palm. The dagger points diagonally outward and down, with its wrapped handle inside a carved contact channel. Its blade design is retained. The palm and finger regions follow the hand bones; the narrow wrists blend into the forearm weights. There are no individually animated fingers.

`HandAnatomyChecks.json` measures connected skin, manifold geometry and sampled clearance around the wrapped handle. Front, palm and side close-ups show the actual baked mesh. The prior Goblin files are preserved in `history/before-goblin-hand-anatomy-6/`.

`GripMotionChecks.json` checks 375 contact-surface vertices on every integer frame of all five clips. Their maximum deviation from the dagger hand's rigid transform is below 0.000001 source units. Fresh FBX/GLB import checks pass; Roblox Studio import remains untested.

## Bow Skeleton drawing wrist, revision 7

The drawing hand previously used an independent upright rotation, causing a sharp bend below the forearm during the shot. `straight_draw_arm` in `rig_export.py` now solves to the finger contact point using the forearm and aligned hand as one effective reach segment. The wrist stays connected at the forearm tip, and its direction follows the forearm. Alignment blends in while raising the bow and blends back to rest while lowering it.

`ShootingChecks.json` measures wrist alignment and joint continuity at quarter-frame intervals from frame 7 through frame 20, covering draw, release and follow-through. It also checks string contact and string return. `DrawWristDetail.png` and `ReleaseWristDetail.png` show the actual animated mesh. The shot preview and exchange files are refreshed; the separate arrow asset is retained. Earlier files are archived under `history/before-bow-straight-wrist-7/`.

## Werewolf reference rebuild (2026-10-01)

Rebuilt from the user's sheets in `../../art-references/werewolf-redesign/` (turnaround plus head/hands/combat-stance details). It replaces the blocky `revisions/werewolf` model, which stays as history. `build_werewolf.py` is self-contained, and `werewolf_compare.py` composes `werewolf/Compare.png`: the sheet on top and sheet-matched ortho renders below, at 0.01 units per pixel, ground at y=770. It also prints colour probes. Mane, muzzle, shorts and belt land within 2–10% of the sheet. The bib renders about 18% brighter.

- **Body.** One fused, faceted fur skin, skinned with blended weights: torso, arms and legs are lofted muscle sections, plus the dark mane hump and face ruff, the pale chest bib, and soft fur clumps at the shoulders, biceps, elbows, forearms, wrist and ankle cuffs, knees and calves. Everything is voxel-merged, smoothed and decimated. Face colours come from the nearest source piece, so the mane/bib edges follow the clump outlines.
- **Fur style.** Fur clumps are thick rounded teardrops. Thin diamond shards were rejected as "blades/daggers/scales", and a dense clump coat on the limbs read as rocks. Limbs stay smooth muscle with tufts only where the sheet breaks the silhouette.
- **Rigid pieces.** The angular head is fused (cranium, brow ridge, box snout, jaw, cheeks, ears, cheek tufts), with an inset light inner ear and a cut mouth line. Almond amber eyes with slit pupils, heavy V brows, a rounded nose and upper fangs are separate rigid parts. Hands (palm, four thick fingers and thumb) and paws (four toes) are fused, with separate claws. The tail is fused and bushy.
- **Shorts.** Torn shorts, with rips cut before the merge, plus belt and buckle. They take nearest-skin weights.
- **Triangles.** 25,510 total: skin 13,488, head 2,816, each hand 1,460, each paw 1,076, tail 1,300, shorts 2,834. Every mesh is under 20k.
- **Rig.** The bones follow the Ogre naming (Pelvis/Chest/Head/…/Tail). `polish_rig.py` has a werewolf region block. `ManeMask`, a vertex attribute written by the build, keeps the face ruff on Chest/Head.
- **Mesh cleanup.** Blender's glTF exporter calls `mesh.validate()` on the *source* mesh. That deletes duplicate back-to-back faces left by decimation at pinched tips and opened pinholes in `Model.blend`. `clean()` collapses those fins and leftover non-manifold edges to points, and the build refuses to save non-manifold meshes.
- **Verification.** `Rig.json` shows 0 failures and `ExchangeChecks.json` passes (fresh FBX/GLB re-import, 4 influences, normalized weights, texture loaded). `combat-ready/werewolf` was re-animated with the existing claw-rake choreography: loops close exactly, opposing limbs pass, and the planted-ankle error is 1.8e-7. Lean was reduced from 14° to 8° because the hunch is sculpted, and the tail sways.

Blender-verified only. Studio import, retargeting and in-game appearance are untested; Studio's +0.3 saturation will push the lavender grey bluer.
