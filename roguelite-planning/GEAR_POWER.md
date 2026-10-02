# Gear Power: harder maps, matched by better gear

**Status:** built 2026-10-02 and synced to Studio the same day (GearPowerTests: 78 checks pass on the Studio scripts). Not play-tested yet. Asked for by the user on 2026-10-01: "every map gets harder, but as players go onto harder maps they get better and higher-level gear, and once their gear reaches the map's level it should feel like the same difficulty as the first map."

## The rule in one example

Your **Power** is the sum of the tiers of the gear you bring into a run:

| Gear | Counts |
|---|---|
| Starting weapon | its tier (I = 1 … IV = 4) |
| Each worn armor piece (4 slots) | its tier, 0 if the slot is empty |
| Equipped pet | its tier, 0 with no pet |

Example: a Tier II Frying Pan and four Tier I Iron pieces = 2 + 4 = **Power 6**.

Each point above 1 gives **+12% damage** (every hit, burn, poison, pet and armor blast) and **+6% max health** in runs. Power 6 = ×1.6 damage and ×1.3 health.

A fresh account has Power 1 (a Tier I starter, no armor, no pet). The highest is 24 (Tier IV everything); without pets, 20.

## Each map recommends a Power

| Map | Recommended Power | Enemy health | Enemy damage | Boss health (Normal, solo) |
|---|---:|---:|---:|---:|
| Pine Valley | 1 | ×1 | ×1 | 18,000 (Hammer) |
| Beach Cove | 5 | ×1.48 | ×1.24 | 26,640 |
| Desert Basin | 9 | ×1.96 | ×1.48 | 35,280 |
| Frozen Pass | 13 | ×2.44 | ×1.72 | 43,920 |
| Volcanic Crater | 17 | ×2.92 | ×1.96 | 52,560 |

Enemies on a map get exactly the extra health a player at its recommended Power has extra damage for, and the extra damage they have extra health for. So a player whose Power matches the map kills enemies just as fast and survives just as many hits as a fresh player in Pine Valley. Above the recommended Power the map gets easier; below it, harder.

- +4 Power per map is about one more tier on every slot.
- Difficulty still multiplies on top (Hard ×1.6 health ×1.3 damage, Nightmare ×2.5 / ×1.6). Each map's Normal stays under the previous map's Hard, so beating a map on Hard (the unlock rule) also prepares you for the next one.
- Bosses: each map boss's authored health already climbed the ladder (King Crab 21,000 … Dragon 31,500). `bossBase` divides that climb out so the Power curve replaces it instead of stacking on it.
- The old "enemy health starts N waves ahead" head start is gone. Early waves on later maps are no longer a wall; a good starter makes them quick.

## Where it shows

- **Map select (Run Setup):** "Your power 6 · recommended 9" in lime when you meet it, gold when you don't.
- **Armory:** a POWER plate under the dais with the damage and health bonus.
- **In runs:** the Gear power stat (Stats panel, Extra tab).

## Better gear on harder maps

Later maps already pay more emeralds per five waves (20, 40, 60, 80, 100 on Normal; ×1.5 Hard, ×2 Nightmare), so pushing harder maps buys more chests and upgrades. That is how Power keeps pace with the ladder.

**Still to check with real data:** whether players actually reach about Power 5, 9, 13 and 17 around the time each map unlocks. The pace target (first Tier II in about an hour, first Tier IV in 10–15 hours) suggests yes, but it's untested. If players arrive under-powered, lower the map's `power` in `RunSetupRules.Maps`; enemies follow automatically.

## Code

- `CharacterStats`: `GearPower` stat, `gearPower(get, weapon)`, `powerDamage(p)`, `powerHealth(p)`, `ownedTier(text, id)`.
- `CharacterService.refresh`: computes Power from the profile attributes and applies the health part as a max-health percent.
- `CombatEffectsService.hit`: applies the damage part to every hit.
- `RunSetupRules.Maps[].power` / `bossBase`, `enemyScale`, `bossScale(id, players, mapId)`, `power(player, weapon)`.
- `ShopService`: the loadout starter enters the run at its owned tier (`starterTier`), so Armory upgrades now matter in runs.
- Checks: `combat/GearPowerTests.luau`, 78 checks passing on 2026-10-02 (Edit-mode harness on unparented copies, Studio's real MapBossDefs).
