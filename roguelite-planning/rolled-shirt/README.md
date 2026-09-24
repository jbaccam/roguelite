# Bundled designer tee

Original Blender-authored cotton roll and separate fitted shirt panels, September 24, 2026. Style references: `art-references/ART_DIRECTION_USER_2026-09-17.txt`, `MASTER_GAME_DESIGN.md`, `CURRENT_GAME_STRUCTURE.md`, the baby/mutant texture prompts, and the existing cannon model/build script. Soft ivory fabric, broad restrained shade changes, readable folds, exposed rolled ends, and a red **supermeme** text label, as requested by the user. The label uses runtime text; no logo image or Creator Store asset was imported.

- `BundledDesignerTee.blend`, `.fbx`, `.glb`: rolled projectile; 166 triangles. `Preview.png` is its actual Blender render.
- `DesignerTeePanels.blend`, `.fbx`: normalized hollow torso and short sleeve shells, 264 triangles across a torso and two sleeves.
- `build_shirt.py` / `build_garment.py`: regenerate the Blender assets and runtime vertex/face/color data with Blender 5.2.
- `RolledShirtData.luau`, `TeeTorsoData.luau`, `TeeSleeveData.luau`: the same authored geometry consumed by the game. Garment widths/depths fit individual body parts; the neckline uses the head clearance. Each sleeve follows its upper arm independently.

The current place has EditableMesh access disabled. The installed default uses the exact exported triangles as non-colliding local WedgeParts, with no mesh upload required. Roll: 332 parts; garment: 528 geometry parts plus label. Rendering is bounded to 24 concurrent rolls and 40 nearby dressed mobs (120 studs); this is a functional prototype, not a measured hundred-enemy performance target. Templates are reused. An optional MeshPart path exists behind `RogueliteCombat.UseEditableDesignerMeshes=true` for an experience with EditableMesh access enabled; that path was not validated in gameplay here. Current delivery does not change experience security settings.

Gameplay and test evidence: [Designer cannon](../studio-prototype/combat/DESIGNER_CANNON.md).
