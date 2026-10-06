# Draco late-wave damage — October 5, 2026

## Parent Studio integration

Applied to place 107877054949326. Fresh-source WeaponBalanceTests passed all 1,773 assertions in Studio Edit. A fresh Studio Play fixture equipped six Tier IV Dracos on Brawler at Gear Power 1, Damage +32%, Ranged Damage -15%, Projectile Count +1; Crit Chance and Chain Count were set to zero to isolate direct hits. In ten seconds, 471 observed nonlethal health changes each measured 10.491 damage (rounded), confirming the calculated 10.4907. Run kills increased by 122. This stationary dense-crowd test used God mode and is not a controlled before/after kill-rate comparison or evidence of moving-player balance. No persistent rewards were awarded. Console output was empty. Play was stopped and test overrides discarded.

The required combat Rojo build passed. All 18 manifest script destinations matched Studio source after line-ending normalization.

The reported six-Tier-IV-Draco session was Brawler, not Gunner: Damage +32%, Ranged Damage -15%, Gear Power 1, Projectile Count +1, Pierce 0, Attack Speed 0, affinity count 0. Brawler's -15% class fit to Draco also applies. These modifiers explain why six upgraded guns still needed many hits against the current wave-20 fodder.

## Implemented change

Only Draco tier damage growth changes, from 1.4 to 1.55. Its raw tier damage is now **3 / 5 / 7 / 11**, previously **3 / 4 / 6 / 8**. Tier I, range, cooldown, projectile speed, projectile count and all class/gear formulas stay unchanged. Upgrades now cross useful fodder hit thresholds without increasing server projectile work.

| Reported Brawler loadout, Tier IV | Before | After |
| --- | ---: | ---: |
| Noncritical damage per bullet | 7.6296 | 10.4907 |
| Hits to defeat wave-20 regular (41 HP) | 6 | 4 |
| Hits to defeat wave-20 baby (20 HP) | 3 | 2 |
| Hits to defeat wave-20 mutant (229 HP) | 31 | 22 |
| Nominal cooldown per gun | 0.1267 s | 0.1267 s |
| Six guns: nominal triggers/s | 47.36 | 47.36 |
| Six guns with +1 projectile: bullets/s | 94.71 | 94.71 |

These are calculated noncritical direct-hit breakpoints, not measured kills/s. Heartbeat timing, movement, obstruction, spread, targets changing/dying and overlapping target selection reduce practical throughput. Six weapons independently choose their nearest eligible enemy; their firing clocks are staggered, but already-travelling rounds can overkill the same target. There is no GunMotion module or magazine/reload simulation in this source: the server fires on each weapon's cooldown. The 0.16-animation-second recovery does not limit Draco because motion speed scales with cooldown.

For comparison, a six-weapon Gunner at Gear Power 1 with no item/stat gains deals **11.04 → 15.18** per Tier IV Draco bullet. Its class grants Pierce 1, +1 projectile and 10% ranged attack speed, giving a nominal 0.11518 s cooldown and 104.18 bullets/s across six guns. Regular wave-20 enemies take **4 → 3** direct hits, babies **2 → 2**. Those class advantages remain meaningful.

## Verification

- Recalculated the reported Brawler damage, unchanged cadence/shot count and hit breakpoints using the source formulas.
- Added WeaponBalanceTests assertions for that exact Brawler loadout, wave-20 fodder breakpoints, unchanged Tier I/cadence and no extra native pierce/bounce/projectiles. The historical 10% old-DPS constraint has a documented Draco exception for this requested correction.
- `git diff --check` passed (line-ending notices only).
- This agent performed **no Studio tests** and did not modify Studio. Parent integration owns synchronization and actual Play validation. No production DataStores or persistent rewards used.
