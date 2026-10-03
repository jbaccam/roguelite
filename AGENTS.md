# Roguelite

This is a separate Roblox survivor roguelite, not Copy The Scene. The source under `roguelite-planning/` is authoritative for this project. Do not sync the Copy The Scene root Rojo project into the roguelite Studio place (107877054949326).

Build the current combat overlay with `rojo build roguelite-planning/studio-prototype/combat/default.project.json -o build/RogueliteKatanaCombat.rbxlx`. The overlay does not replace the existing Studio map or unrelated instances. Keep source and Studio edits synchronized, and document which Studio play tests actually ran.

Start with `roguelite-planning/CURRENT_GAME_STRUCTURE.md` for game identity, then the specific prototype README and implementation docs. Keep combat, stat changes, inventory, placement, rewards, and remote actions server validated. Studio practice should not award persistent rewards or use production DataStores.

Stat upgrade image concepts live in `roguelite-planning/STAT_UPGRADE_ART_DIRECTION.md`. Preserve stat IDs and exact effects on cards. Roblox Community Standards prohibit depicting or promoting steroids; use the improvised training humor in that art brief instead.
