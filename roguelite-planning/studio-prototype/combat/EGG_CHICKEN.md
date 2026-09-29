# Egg chickens

A landing Egg (weapon `15`) has a 1 in 8 chance to hatch a derpy chicken, like Minecraft's thrown eggs. The chicken:

- runs at the nearest enemy and pecks it;
- pops into a burst of feathers after 8 s.

## Numbers (`EggChickens.luau`, table `C`)

| Setting | Value |
|---|---|
| Hatch chance per landed egg | 1/8 (`Chance`) |
| Lifetime | 8 s, then a 0.35 s swell and a feather pop |
| Chickens per player | 3; a 4th hatch pops the oldest early |
| Chickens per server | 24 |
| Peck | 40% of the egg hit that hatched it, every 0.7 s, as a secondary hit (no crit, knockback or status procs) |
| Speed / sight | 22 studs/s, targets within 45 studs |

Example at tier 1: the egg hits for 10, so a peck does 4. A chicken that pecks for its whole life does about 11 pecks, or 44 damage.

## Rules

- Pecks go through `CombatEffectsService.hit`. The owner must be alive, with weapons on, and in a live wave. Otherwise the chicken pops.
- A practice throw's chicken only pecks practice targets, the same rule as the egg itself.
- Enemies ignore chickens. Chicken parts can't be queried and use the enemy collision group, so a chicken never blocks shots, enemy swings or line-of-sight checks.
- A chicken with nothing to peck trots back to its owner.
- Like the enemies, the chicken's Humanoid body is floored at 4 mass and it hops steps taller than its legs (see `ZOMBIE_VARIANTS.md`).
- Studio only: the `TestChickenChance` attribute on `ReplicatedStorage.RogueliteCombat` (0–1) overrides the hatch chance for testing.

## Files

- `EggChickens.luau`: server module `ServerScriptService.EggChickens`. It must stay `Sandboxed = true` with `SpecialWeapons`' Capabilities, because sandboxed `SpecialWeapons` requires it.
- `SpecialWeapons.luau`: calls `chickens:landed(r.d, r.position)` when a flight lands (`returnOrEnd`).
- `RogueliteChickens.client.luau`: waddle, flap and peck on the rig's Motor6Ds, the shell burst on hatching, and the swell and feather explosion.
- `InstallEggChicken.luau`: after a Studio **File > Import 3D** of `../../blender-derp-chicken/exports/fbx/derp-chicken.fbx`, it builds:
  - `ServerStorage.RogueliteAllies.EggChicken` (Humanoid rig; joints `Body`, `Neck`, `LeftWing`/`RightWing`, `LeftHip`/`RightHip`);
  - `ReplicatedStorage.RogueliteCombat.ChickenFeather`.
- Art: `../../blender-derp-chicken/` (Blender 5.2 headless build, exports, atlas, previews, validation).

## Status (2026-09-29)

- 2026-09-29 user report "the chicken isn't spawning": confirmed the cause below. The Play console showed the missing-template warning; `ServerStorage.RogueliteAllies` doesn't exist.

- Scripts are synced into Studio Edit. `EggChickens` loads and the client script compiles.
- The FBX is **not imported yet**, so the template is missing. Until it's installed, eggs hatch nothing and the server warns once: `EggChickens: ServerStorage.RogueliteAllies.EggChicken is missing`.
- Not play-tested. The user is testing it.
- Multiple clients untested.
