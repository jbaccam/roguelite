# Godly weapons: Studio import

Installed in Studio on 2026-10-01 as `ReplicatedStorage.RogueliteCombat.WeaponTemplates.36`–`41`.
The ids follow `MonetizationConfig.GodlyWeapons`:

| Id | Weapon | Play scale | Bounds (studs) |
|---|---|---:|---|
| 36 | Reaper's Scythe | 1.15 | 4.35 x 5.81 x 1.05 |
| 37 | Poseidon's Trident | 1.0 | 2.46 x 6.40 x 1.25 |
| 38 | Storm Bow | 1.05 | 0.62 x 5.25 x 1.87 (arrow points -Z) |
| 39 | Shadow Daggers (pair) | 0.9 | 2.99 x 4.10 x 0.31 |
| 40 | Vampire Blade | 1.15 | 3.08 x 5.82 x 0.95 |
| 41 | Ray Gun | 0.9 | 0.52 x 1.70 x 3.08 (muzzle points -Z) |

Each template has:
- a textured `MeshPart` (Plastic, `TextureID` from `studio-asset-ids.json`);
- Neon `_Glow` and `_GlowCore` meshes;
- attachments for VFX: `Grip`, `Tip`, `Muzzle`, `Pearl`, `ArrowRest`, `Nock`, `FloatPivot`, `ThrowPivot` (whichever the weapon has; the daggers have `GripL`/`GripR`).

Blades keep the authored frame: tip +Y, blade in the XY plane. The bow and gun are turned so they shoot toward -Z, like the other gun templates.

The templates change no gameplay until `WeaponCatalog` lists ids 36–41.

## Steps

1. `blender -b --factory-startup --python combine_godly_weapons.py` merges the six `Model.blend` meshes (21 in all) into `Godly_Weapons.fbx` and re-imports it to check names and triangle counts (`combine_report.json`).
2. Upload the six `BaseColor.png` with Studio MCP `upload_image`, and record the ids in `studio-asset-ids.json`.
3. Studio: File › Import (Ctrl+M) `Godly_Weapons.fbx` with default settings. It arrives as `Workspace.Godly_Weapons`, at 100x scale.
4. `python make_install_call.py` writes `install_call.luau`. Run it in the Edit datamodel. It checks every mesh against the install data, builds all six templates, and moves the raw import to `ServerStorage.GodlyWeaponImport`.
5. To re-install (for example with new play scales): run `python make_install_call.py --replace`, then run the call again. It reuses the ServerStorage copy, so no new GUI import is needed.

The importer gave all six textured meshes the same texture, so the per-weapon `TextureID`s from step 2 are required.
