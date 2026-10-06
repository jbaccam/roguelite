# Enemy scaling — October 5, 2026

[Approachable Normal and full-roster audit](NORMAL_BALANCE.md) is authoritative for the final difficulty pass: Normal multiplies catalog HP by 0.60 and damage by 0.75, including bosses. Hard remains 1.60 / 1.30; Nightmare 2.50 / 1.60. Rewards and class debuffs are unchanged.

## Wave scaling and progression

All ordinary enemies use base + per-wave growth * (wave - 1), floored/clamped to waves 1–1000 with NaN handling. The server owns spawn stats. Tank catalog health retains a 50 HP floor. Pine uses the Brotato enemy HP references: Regular 3 + 2 per wave, Baby 1 + 1, Tank 20 + 11 with the floor. This preserves early one-shots and permits successful builds to one-shot late fodder. Our typed damage stats are percentages rather than Brotato's flat weapon-scaled typed values, so this is pacing adaptation, not exact stat parity.

| Native type | Catalog HP W1 / W10 / W20 | Catalog damage W1 / W10 / W20 | Speed |
|---|---|---|---:|
| Regular | 3 / 21 / 41 | 5 / 13.1 / 22.1 | 14 |
| Baby | 1 / 10 / 20 | 5 / 10.4 / 16.4 | 17 |
| Tank | 50 / 119 / 229 | 10 / 23.5 / 38.5 | 11 |

Tanks naturally debut at wave 8 with catalog 97 HP, then difficulty scales it. They deal only a telegraphed slam, never extra contact damage. Gentler damage growth remains appropriate alongside denser swarms. Normal final W20 HP is regular25 / baby12 / tank138; normal tank damage28.875 before armor. Hard/Nightmare ordinary HP is66/103.

Actual no-run-bonus T1 starter damage: Pan24.84, Glock16.56, Staff12.9375. All three one-shot ordinary mobs through wave5. At four affinity weapons and +20 Damage/+15 Attack Speed, T2 Pan48.438/Glock28.152/Staff25.116 each one-shot wave10 regulars. Strong six-slot T4 Gunner with +50 Damage/+30 Ranged Damage/+30 Attack Speed deals85.3875 per Glock hit every0.4014s: one Normal W20 regular hit, two tank hits. Hard requires1/5 and Nightmare2/7 at matched permanent gear power. These are direct-hit mathematical breakpoints, not measured combat throughput.

## Other maps and modifiers

Imported per-wave growth: melee +2HP/+0.9 damage, ranged +1/+0.9, lunge +2.5/+1.1, heavy +11/+1.5, splitter +3/+0.9. Werewolf has +4HP, Frozen Knight+12, Obsidian Ogre+14, Ember Spider+1HP/+0.6damage. Map recommended gear power matches the player's permanent damage/health curve, then difficulty applies once. Multiplayer increases count rather than multiplying each regular mob's HP again.

Regular waves1–20 never scale movement speed. Existing Endless modifiers remain after20: +12% compounded HP per wave, +6% linear damage, at most+10% speed capped at21. Wave30 Normal Pine regular is114 rounded HP/37.32damage. No extra scaling modifier was added.

## Latest movement feedback

Only native Pine zombies slow: Regular16 to14, Baby20 to17, Tank12.5 to11 studs/s. Optional Spitter and all other map enemies retain their speeds. Both Hammer runtimes increase walking chase22 to24; rebuilt Hammer retains +2 enrage, reaching26. Charge speed/travel, attack warnings, HP and damage are unchanged by this movement pass.

Legacy Hammer no longer walks backward whenever a melee player closes inside its preferred reach. It holds ground and starts its existing attack when its normal cooldown permits. This keeps the damage window accessible without adding contact damage or bypassing attack validation. Rebuilt MapBossService already holds ground within its stop range and needed no equivalent change.

## Verification

Run `python roguelite-planning/studio-prototype/combat/run_enemy_scaling_tests.py build/luau-validation/luau.exe` with the official Luau CLI. Real source math runs with Roblox wiring and unused motion dependencies adapted. EnemyScalingTests passed2,517 assertions, NormalBalanceTests942, GearPowerTests74. Coverage includes all21 exact speeds (only native three changed), constant regular-wave speed, wave bounds, immutable catalogs, progression breakpoints and every map/difficulty. Luau compilation passed for changed runtime/tests. No Studio Play test was run by this agent for this movement pass; parent integration records actual sync/tests. See NORMAL_BALANCE for the full weapon audit and damage-unit limitations.

## Normal-wide movement follow-up

The latest [Normal movement table](NORMAL_BALANCE.md#normal-movement-across-all-maps) supersedes earlier statements about unchanged non-Pine runtime speed. All catalog speeds remain the same, but Normal ordinary-enemy chase uses a 0.85 multiplier; Hard/Nightmare use 1. Native final Normal speeds are 11.9 / 14.45 / 9.35. Bosses do not use this multiplier. Verification now passes 4,261 scaling + 942 Normal + 74 gear-power assertions.
