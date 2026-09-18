# Studio display corrections — September 17, 2026

Place: roguelite, 107877054949326. Only owned weapon displays were changed.

- Cinder block cavity faces inherited the boolean cutter's dark palette tile. `Cinder_Corrected.png` makes that tile the same concrete gray as the body, retaining real lighting and through-holes. Roblox texture: 72121203546781.
- Bowling ball retains the charcoal reference design and dark finger sockets; its body tile is now RGB 105,109,120 so the facets read clearly. Roblox texture: 114276616497392.
- Pandora's multiple exterior/interior materials were merged into one atlas with remapped UVs. Its original two-bone lid rig remains. Roblox texture: 111918451401495.
- Crystal shell, core, and base are separate meshes. Studio shell transparency is 0.38; the solid core is purple Neon. This resolves the opaque merged-shell issue from the initial import.
- Original large showcase remains `Workspace.RogueliteWeaponShowcase`. Added `Workspace.RogueliteWeaponShowcase_PlaySize`: 36 families, each exactly one-third the corresponding large model's dimensions. Small display grid spans X 45–70, Z 500–525, beside spawn; large grid spans X 100–155, Z 460–520. Both have signs and individual labels.
- Components remain independent; displays are anchored for inspection. No attacks or animations were added. These sizes are visual prototypes, not final per-weapon combat balancing.

## Reproduction and source

`fix_utility_textures.py` generates the two corrected palette textures. Run before Blender's `fix_magic_materials.py`, which produces `Magic_Material_Fix.fbx` and the complete `Weapon_Showcase_Corrected.blend` / `.fbx`. The corrected full files are the current import derivatives; original authored assets remain archived unchanged.

Existing-place migration: native import `Magic_Material_Fix.fbx`, then `ApplyShowcaseCorrections.luau`, then `CreatePlaySizeShowcase.luau`. These scripts intentionally reject duplicate small displays. Original replaced models and raw corrected import are retained in `ServerStorage.Weapon_Material_Correction_Backup`. Full corrected FBX uses three W35 meshes; initial `ArrangeShowcase.luau` needs matching corrected import name and the shell/core settings when used for a fresh-place import.

## Verified

- Studio Edit and client Play: 36 families, 44 MeshParts, 31 bones in each display set.
- All 36 small bounding boxes equal their large counterpart divided by three (tolerance 0.005 stud).
- All displayed texture asset fetch statuses reported Success in Play mode.
- Inspected corrected Pandora and block close-ups; inspected both display grids in Play mode.
- Display copies retain independent rigs and components. No multiplayer combat behavior was changed or tested.

Selection correction: enabled CanQuery and cleared Locked on all 88 weapon MeshParts across both display sets. This allows viewport/raycast-based selection, including modeling tools. Anchoring and non-collision settings are preserved. Import scripts now retain these selectable settings.

