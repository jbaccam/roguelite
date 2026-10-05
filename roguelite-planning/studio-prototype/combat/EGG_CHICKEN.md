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

- Pecks go through `CombatEffectsService.hit`. The owner must be alive and not downed, with weapons on, and in a live wave. Otherwise the chicken pops. Pausing holds its lifetime and movement; delayed pecks recheck the owner, pause state, target distance and line of sight.
- A practice throw's chicken only pecks practice targets, the same rule as the egg itself.
- Enemies ignore chickens. Chicken parts can't be queried and use the enemy collision group, so a chicken never blocks shots, enemy swings or line-of-sight checks.
- A chicken with nothing to peck trots back to its owner.
- Like the enemies, the chicken's Humanoid body is floored at 4 mass and it hops steps taller than its legs (see `ZOMBIE_VARIANTS.md`).
- Studio only: the `TestChickenChance` attribute on `ReplicatedStorage.RogueliteCombat` (0–1) overrides the hatch chance for testing.
- Chance is **1 in 8 at every tier**; tier increases peck damage through the egg's damage. Each landed egg is a separate roll, including extra projectile eggs. Missed rolls are expected; cancelled flights do not hatch. Contact and range expiry in the same simulation step count as one landing.
- Hatches use `GroundContact` to find real walkable ground, excluding all players, enemies, chickens and untagged Humanoid/lobby dummies. A hatch with no valid floor is declined.

## Files

- `EggChickens.luau`: server module `ServerScriptService.EggChickens`. It must stay `Sandboxed = true` with `SpecialWeapons`' Capabilities, because sandboxed `SpecialWeapons` requires it.
- `ChickenTemplate.luau`: server helper with the same sandbox capabilities; builds a cached, unparented fallback rig if the imported template is absent or incomplete. It has the existing six animation joints, cream body/wing panels, two three-toed feet, mismatched eyes, comb, beak and tongue. Only its invisible root collides. No runtime avatar appearance permission, image upload, or external asset is required.
- `GroundContact.luau`: shared floor probing used by hatchlings and both sides of bowling-ball presentation/collision.
- `SpecialWeapons.luau`: calls `chickens:landed(r.d, r.position)` when a flight lands (`returnOrEnd`).
- `RogueliteChickens.client.luau`: waddle, flap and peck on the rig's Motor6Ds, the shell burst on hatching, and the swell and feather explosion.
- `InstallEggChicken.luau`: after a Studio **File > Import 3D** of `../../blender-derp-chicken/exports/fbx/derp-chicken.fbx`, it builds:
  - `ServerStorage.RogueliteAllies.EggChicken` (Humanoid rig; joints `Body`, `Neck`, `LeftWing`/`RightWing`, `LeftHip`/`RightHip`);
  - `ReplicatedStorage.RogueliteCombat.ChickenFeather`.
- Art: `../../blender-derp-chicken/` (Blender 5.2 headless build, exports, atlas, previews, validation).

## October 4 correction

The missing imported template was confirmed again in Studio. Successful rolls previously returned without creating anything. The reviewed import still takes priority, but a complete procedural fallback now makes hatching work without it. The fallback stays outside the live world; only its clones become tagged hatchlings. Placement uses an authored `GroundOffset` or imported model bounds, without reading privileged `Humanoid.HipHeight`.

`GroundedWeaponsTests` checks the fallback's joints, bounded geometry, feet, collision/query policy, cloning and floor placement without touching the live DataModel. `CommittedThrowTests` exercises the actual egg-flight contact/range-expiry race. The root integration report records the actual Play hatch, movement, peck and expiry checks; source assertions alone are not a live hatching claim.

Actual follow-up Studio Play: a 55-second isolated fixture using production modules produced **34 fallback hatches**, **185 pecks**, **5.19 studs** maximum travel and **3** maximum simultaneously active chickens for its owner, with an empty console after the display-capability fix. The final sample at 52 seconds still had one chicken; automatic fixture cleanup at 55 seconds was confirmed. That sample does **not** prove the last chicken's natural expiry at its exact deadline. Play was stopped afterward; no persistent rewards or player inventory were changed.

For a deterministic **Studio practice** check, temporarily set `RogueliteCombat.TestChickenChance = 1`, equip Egg and attack a practice dummy. Confirm tagged `RogueliteChicken` models appear on the floor, their owner matches, their wings/feet animate, and pecks lower the dummy health. With ongoing throws, a fourth hatch should pop the oldest. Stop throwing to observe the last chicken swell at 8 seconds and disappear 0.35 seconds later. Restore the attribute after the check. This override is ignored outside Studio, and practice must never award persistent rewards.

## Historical status (2026-09-29; superseded)

- 2026-09-29 user report "the chicken isn't spawning": confirmed the cause below. The Play console showed the missing-template warning; `ServerStorage.RogueliteAllies` doesn't exist.

- Scripts are synced into Studio Edit. `EggChickens` loads and the client script compiles.
- The FBX is **not imported yet**, so the template is missing. Until it's installed, eggs hatch nothing and the server warns once: `EggChickens: ServerStorage.RogueliteAllies.EggChicken is missing`.
- Not play-tested. The user is testing it.
- Multiple clients untested.
