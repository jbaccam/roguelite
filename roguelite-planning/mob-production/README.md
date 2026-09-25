# Regular mob production

Current animation/setup delivery: [`combat-ready/README.md`](combat-ready/README.md).
This preserves the latest finished meshes and adds combat stances, revised
motion, verified exchange files and retargeted Studio bone samples. The older
status notes below describe the modeling passes and are retained as history.

Status: the first pass and the `revisions/` pass were rejected for insufficient reference fidelity, incorrect proportions, and broken grips. The nine specifically flagged mobs have new, separately authored reconstructions in `reference-rebuilds/`; use `reference-rebuilds/review.html`. These remain visual candidates, not approved or game-ready assets. Bosses are excluded.

## Art sources reviewed

- `../art-references/ART_DIRECTION_USER_2026-09-17.txt`: full project art brief, geometry, textures, characters and lighting.
- `../MASTER_GAME_DESIGN.md`: confirmed art direction, combat authority and performance requirements.
- `../MAP_MOB_ROSTER.md` and `../CURRENT_GAME_STRUCTURE.md`: latest mob assignments and simple behaviors.
- `../BRAINSTORM_MOBS_BOSSES.md`: historical behavior concepts; latest roster supersedes old names.
- `../COMBAT_FEEL_AUDIO_VFX.md`: readable anticipation, attacks, hit/death feedback.
- `../map-concepts/README.md` and `../MODULAR_CLIFF_KIT.md`: environment palette and scale context.
- `../STAT_UPGRADE_ART_DIRECTION.md`: related UI art; not a creature modeling specification.
- `../weapon-models/MODELING_BRIEF.md` and `../weapon-models/RIGGING_GUIDE.md`: established reference fidelity and export checks. Their old task-specific ownership, delegation and scope instructions do not govern this request.
- `../baby-mutant-zombies/README.md`, `../baby-mutant-zombies/source-art/PROMPTS.md`, `../regular-zombie-matte/README.md`, `../studio-prototype/combat/ZOMBIE_VARIANTS.md`: existing approved zombie pipeline and current matte palette.
- `../ENEMY_SIMULATION_ARCHITECTURE.md`: server-owned combat and client presentation requirements.

The unrelated facility-blockout art direction and Copy The Scene pavilion palette do not define these roguelite creatures.

## Deliverable standard

One AI-generated modeling reference per regular mob; preserve existing approved zombie masters. New Blender assets require authored geometry, UV/base-color textures, armature and skin weights, simple idle/move/attack/hit/death clips, separate projectile assets where applicable, clean FBX/GLB exports and actual Blender preview renders. Review reference fidelity, deformations, weights, topology, texture paths, scale, axes and reimported animations. Never label generated concept art as a render of a completed mesh.

Runtime attacks remain server-authoritative. Studio import/play verification, multiplayer and device performance must be reported separately from Blender validation. No production-readiness claim until the relevant checks have actually passed.

## Current state

- Art and pipeline review completed.
- Reference sheets have been generated using the built-in image generation tool.
- The latest nine reconstructions, baked textures, custom rigs, five clips and exchange files are under `reference-rebuilds/`. The other mobs have not been rebuilt in this correction pass.
- Independent exchange-file checks are recorded per mob with file hashes in `validation.json` when complete. These do not substitute for Studio import or gameplay validation.
- Existing user-made Pine Valley zombie masters are preserved. Studio integration and live combat verification remain pending.

## User correction

The previous Blender passes did not faithfully reconstruct the reference sheets. Do not propagate their generic geometry. Improve proportion, silhouette, facial construction, clothing layers, hands/feet, materials and meaningful detail. Export validity is not visual acceptance. Preserve rejected files for comparison; current work goes in `reference-rebuilds/`.
