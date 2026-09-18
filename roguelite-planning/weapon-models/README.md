# Weapon reference models

This folder holds the approved Glock and the 35 remaining weapons modeled from the user's supplied reference folder. The original Glock is preserved, not remodeled. Consult `coverage.json` for actual completion and `export_audit.json` for independent reimport checks; an assigned entry in inventory.json alone does not mean the model is complete.

## Review and use

Open `Weapon_Catalog.html` locally for references beside real Blender renders, a name filter, alternate views, and model links. Keep the catalog beside the assets folder so relative images and links work. `Weapon_Review_01.jpg` and subsequent numbered pages provide render-only contact sheets.

Each asset folder contains its model, exports, reference, preview, alternate view, local validation, and notes. Some assemblies use one mesh with named component vertex groups; others retain separate editable meshes. Closed decorative shells intentionally intersect at their attachment surfaces.

Per the user's updated direction, cinder blocks, ducks, kunais, eggs and bowling pins each deliver ONE reusable model, even though the reference shows multiples. Boxing gloves provide separate LeftGlove and RightGlove models. Cards provide an independent Deck, HeartCard, SpadeCard and DiamondCard. The glove/card top-level files are review arrangements of independent objects; use their components/<ComponentName>/Model.blend, Model.fbx or Model.glb files for individual assets with independent pivots. No card is attached to the deck or another card.

`Weapon_Models_Complete.zip` is only produced after all 36 folders have their required deliverables and pass independent delivery verification. Extract the complete ZIP to preserve texture and catalog paths. `Weapon_Overview.jpg` shows all 36 items at once.

## Scope and ownership

| Agent batch | Exclusive assigned weapons |
| --- | --- |
| melee_tools | Frying Pan, Nunchucks, Katana, Kusarigama, Spatula, Baseball Bat, Shovel |
| guns | Draco, Fart Gun, Shotgun, T-Shirt Cannon, Rocket Launcher, Nail Gun, Power Washer |
| magic | Magic Staff, Mjolnir, Excalibur, Pandora's Box, Medusa's Head, Crystal Ball |
| throwables | Boomerang, Kunais, Molotovs, Eggs, Steak, Deck of Cards |
| juggler_utility | Rubber Ducks, Boxing Gloves, Cinder Blocks, Yo-Yo, Bowling Ball, Bowling Pins, Wrecking Ball, Paint Roller, Vacuum Cleaner |

All agents receive `MODELING_BRIEF.md`, which preserves the user's reference-faithfulness requirements and the approved Glock quality bar. Five assignments run in waves because the session supports three concurrent subagents plus the parent. The parent handles catalog creation, unique-reference coverage, and independent review.

These are Blender art deliverables. Studio import, final game scale, mesh collision choices, attacks, animations, weapon tiers, and gameplay integration are separate tasks. Nothing in this batch is automatically inserted into or published from Roblox Studio.

## Articulation update

The nunchucks, kusarigama and wrecking-ball weapon now have rigidly weighted chain rigs. Pandora's Box has a rear-hinged lid rig. No animation clips are included. The rocket launcher is empty and its rocket is an additional independent component. The yo-yo has separate body/ring files and attachment markers for a future Roblox Beam; the fixed modeled cord is removed. See `RIGGING_GUIDE.md` and the per-item rig notes. These updates supersede the original static-only scope for these six items.

## Reproducibility

- `inventory.json`: every original reference filename, item identity, unique index, owner batch, and output path.
- `approved-glock.json`: preserved source of the already approved item.
- `batches/<batch>/`: batch-owned modeling and export scripts.
- `build_catalog.py`: reads completed deliverables, regenerates coverage, HTML and contact sheets; `--zip` creates the final archive only with complete coverage.
- `audit_exports.py`: reimports FBX and GLB in an isolated Blender process, checks geometry/image data, and records findings without modifying assets.
- `verify_delivery.py`: checks unique source coverage, exact reference copies, distinct model files, and independent export results; writes `delivery_verification.json`.

Run scripts with Blender 5.2. Background model processes are independent of the user's existing scene. Standard Python is used for the catalog and file-coverage scripts.
