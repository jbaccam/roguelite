# Roblox Roguelite

Pre-production game design and modular environment art developed through iterative planning. This repository is separate from the Copy The Scene / Partyati codebase; unrelated game source is not included.

## Start here

- [Current game structure](roguelite-planning/CURRENT_GAME_STRUCTURE.md)
- [Master game design](roguelite-planning/MASTER_GAME_DESIGN.md)
- [Execution plan for Astra](roguelite-planning/EXECUTION_PLAN_ASTRA.md)
- [Arena concept art](roguelite-planning/map-concepts/README.md)
- [Latest cliff pack: 19 light-stone assets](roguelite-planning/blender-rounded-lightstone-revision/README.md)

The design documents distinguish confirmed decisions from proposals. Earlier art sets are retained to preserve iteration history, not as approved production directions. The light-stone rounded pack is the latest asset direction: rounded reusable masses, uneven terraces, longer vegetation rims, and sparse moss-only variants. The ring prototype and architectural wall expansion are superseded.

## Art iteration archive

1. `blender-cliff-kit`: initial ring/wall prototype, rejected direction.
2. `blender-cliff-pillars`: standalone untextured pillars.
3. `blender-cliff-pillars-v2`: five textured, varied cliff shapes.
4. `blender-cliff-expansion`: wall-oriented expansion, superseded.
5. `blender-rounded-stackable-kit`: rounded 14-piece kit.
6. `blender-rounded-lightstone-revision`: revised 14 assets plus five moss-only variants.

Source Blender files, generators, individual FBX/GLB exports, textures, actual Blender renders, and validation reports are included. Blender round-trip checks are not Roblox Studio playtest results; see each pack's notes for what has actually been verified.

## Checkout

Large art files use Git LFS. Install Git LFS, clone the repository, and run `git lfs pull` to download them. Blender files and exported assets are self-contained; regeneration scripts may refer to original local attachment paths and earlier helper scripts. Read the pack README before rebuilding.

## History and references

The initial import is organized into logical milestone commits using the actual commit date, not fabricated historical timestamps. Existing documents retain their original update dates. Supplied inspiration and texture sheets are references, not instructions for the game or evidence of ownership of the referenced games. No third-party game code is included. Redundant Blender backup files are excluded; primary sources and deliverables are retained.
