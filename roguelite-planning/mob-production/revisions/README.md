# Mob mesh revisions

These are actual Blender mesh revisions responding to the rejected first pass. The earlier concept images remain references, not proof of completed mesh quality. Bosses are excluded. Existing user-made Pine Valley zombie masters are preserved.

## Changed direction

- Smaller humanoid heads and longer legs reduce the toy-like proportions.
- Ice Elf rebuilt with fitted coat, split skirt panels, cuffs, layered swept hair, facial planes, ears, fingers, belt hardware and constructed boots.
- Skeletons rebuilt with recessed skull sockets, narrowed jaws, distinct bone shafts, hands and feet.
- Crab/scorpion shells gain carapace divisions, claw teeth, joint details and surface accents.
- Werewolf gains layered fur, muzzle planes and toes; armored mobs gain layered plates, straps, rivets and trim.
- Frost Ghost uses a billowing continuous shroud and hood opening rather than a box head over a cone.
- Materials.png replaces the high-contrast blotchy atlas with restrained material-specific surface variation. The AI-generated atlas is preserved without pixel edits; generation provenance is in MATERIAL_PROMPT.md.

## Files per creature

Model.blend is the editable rigged source. Model.fbx is the rest-pose exchange model. Model.glb contains the five actions. Idle.fbx, Move.fbx, Attack.fbx, Hit.fbx and Death.fbx contain separate simple clips. Preview.png, Back.png, Windup.png and Impact.png are actual Blender renders. Geometry.json, Rig.json and AnimationSamples.json preserve geometry, bind data and sampled animation for inspection. Reference.png is AI concept art and is labeled separately in the review page.

All 18 revised candidates passed the independent Blender/FBX/GLB checks on their final file hashes. See [VALIDATION.md](VALIDATION.md) for the per-mob results. Passing reimport checks does not establish artistic approval, Roblox gameplay readiness, mobile performance or multiplayer behavior. These revisions have not been installed into the live place. Current Studio and server combat integration still require separate validation.

[Open the before/after gallery](review.html). The updated material atlas was generated with the built-in image generation tool; [its prompt is recorded here](MATERIAL_PROMPT.md).

## Reproducible commands

Run Blender in a separate background process with build_revisions.py and `-- <mob-id>`. Ice Elf uses ice-elf/build_ice_elf.py. run_batch.py builds the other revised candidates. refresh_material.py updates a completed revision's packed atlas, interchange files and renders. The parent verify_mobs.py accepts relative identifiers such as revisions/ice-elf.
