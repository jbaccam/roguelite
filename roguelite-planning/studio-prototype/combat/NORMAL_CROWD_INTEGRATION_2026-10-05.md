# Normal difficulty, crowd movement and Hammer pursuit

## Latest: all-map movement, authored spawns and immediate ordinary death

Final source comparison in Studio Edit: **27 of 27 destinations matched**, zero mismatches, place **107877054949326**. Required combat Rojo build passed. Existing map/assets were preserved. No publishing or production reward/DataStore testing occurred.

- Shared Normal movement multiplier is **0.85** for all 21 ordinary enemy types across all five maps, throughout ordinary and boss waves. Hard/Nightmare retain multiplier 1.0. Boss pursuit is separate and retains the faster Hammer changes. Individual enemy identities and attack mechanics remain distinct.
- Shared crowd steering smooths separation corrections and holds a stable side when passing bosses. This applies to all ordinary map mobs using Chase, not only Pine zombies.
- Every map now uses its own roster in authored wave timelines, with scattered individual red-X positions, full warning on relocation and a protected 100-enemy limit. Solo wave 1 budgets 42 arrivals; active boss encounters schedule four adds every eight seconds with a concurrent 20-add cap. These finite schedules supersede the earlier continuous-refill description below and change the available ordinary kill/drop budget.
- Ordinary death no longer anchors a corpse or waits 0.25 seconds for white feedback. The shared death path removes it immediately while independent feedback continues. Authored boss death animations remain. Lava Slime death splitting is synchronous and once-only; cap retirement does not trigger splitting or rewards.

Final offline verification: WaveTimelineTests **13,939 assertions**, all five actual map rosters; EnemyScalingTests **4,261**, NormalBalanceTests **942**, GearPowerTests **74**; crowd tests including **25,956** legacy grid assertions; SpawnDirector, BossPressure and TimelineLifecycle extracted-production tests all passed. Crowd simulation passed smooth correction, stable boss passing and no boss-body penetration; this is kinematic validation, not a measured live visual jitter comparison.

Studio Edit lifecycle testing passed immediate ordinary removal, zero ordinary delay calls, idempotent death notifications and retained 2.9-second boss cleanup. Final Play attempts entered wave 1, but the sessions ended before a complete measured timeline could be collected. **No final full-wave arrival count, cross-map live mob sweep, moving-player crowd feel, multiplayer or complete-run balance result is claimed.** Final console inspection contained only the Studio assistant camera-reset diagnostic. Studio is in Edit with temporary runtime fixtures discarded.

See [wave timelines](WAVE_TIMELINES_2026-10-05.md), [crowd stability](CROWD_STABILITY_2026-10-05.md), and [death feedback](HIT_FLASH_FIX_2026-10-05.md). Historical checks below describe their respective earlier versions.

## Previous: melee access during boss encounters

The follow-up is synchronized to place 107877054949326; all **26** manifest destinations matched source after line-ending normalization. Seven production scripts changed. The required combat Rojo build passed. Studio returned to Edit after the test, discarding all runtime fixtures. No production rewards or DataStores were used.

- [Boss mob pressure](BOSS_MOB_PRESSURE_2026-10-05.md): 20 ordinary mobs solo, 28/36/44 with 2/3/4 living players; 0.65-second group pacing and a 1.5-second refill delay. Excess numbered mobs are removed without kill/drop credit. Explicit practice count overrides retain their requested counts.
- [Melee targeting](MELEE_BOSS_TARGETING_2026-10-05.md): attack-ready melee prioritizes a boss only when its body is in range and passes existing walls, height and targetability checks.
- Pine Valley regular/baby/tank movement is now 14/17/11 (previously 16/20/12.5). Hammer chase is 24 (rebuilt enraged 26). His legacy close-range retreat was removed: he holds ground and attacks with unchanged warning/cooldown/hit rules. Other-map ordinary speeds, HP, damage and charge settings are unchanged in this follow-up.

Actual fresh single-client Studio Play: normal population rules, Pine Valley wave 20, six Tier IV pans, Brawler, God mode, no added items. Observed **20 ordinary mobs**, their speeds **14/17/11**, and Hammer **24 speed / 10,800 HP**. With the test player anchored eight studs in front, the boss moved **zero planar studs** and started one attack during a three-second observation. Enabling the pans for eight seconds produced **69 boss health-loss events**, **5,977.14 boss damage**, last damage weapon **01 (Frying Pan)**, and **19 ordinary mobs remaining**. The player was unanchored afterward. This verifies boss access with adds and absence of backpedaling; it is not a free-moving fight, full run or difficulty benchmark.

TargetGridTests passed **44,748 assertions** in Studio Edit. BossPressureTests passed extracted-source cap, trimming and lifecycle checks; SpawnDirectorTests passed boss pacing/refill checks alongside previous regressions. The movement/scaling suite passed **3,533 assertions**. Play console output was empty. Multiplayer, controller/mobile and full-run balance remain untested.

The previous integration record below describes the earlier version.

Applied to Studio place **107877054949326** using source-only FeatureSync. Seven production scripts changed in this follow-up; the full combat-feedback manifest contains 24 destinations. Existing map, assets, script capabilities and unrelated instances were preserved. The required combat Rojo overlay built successfully. Studio was returned to Edit after testing; runtime QA scripts and overrides were discarded. No publishing or production DataStore test occurred.

## Changes

- [Normal roster balance](NORMAL_BALANCE.md): enemy HP multiplier 1.00 to 0.60; damage 1.00 to 0.75. Applies to every weapon through regular and boss difficulty scaling. Hard, Nightmare, rewards, permanent power and class penalties retain their existing values. The earlier Draco upgrade correction remains. Brawler/Draco is an off-class test case, not a new combo.
- [Crowd steering](CROWD_STEERING_2026-10-05.md): body-aware separation, deterministic escape from exact overlaps, boss sidestepping, bounded movement speed, and separation while following paths. Cosmetic defeated bodies are excluded. The 100-mob ceiling and continuous spawn director remain.
- [Hammer pursuit](bosses/HAMMER_PURSUIT_2026-10-05.md): fixes both boss versions, including the legacy version active in this place. Legacy chase 18 to 22; charge acquisition 70 to 110; speed 30 to 36; maximum travel 75 to 90. The full possible corridor is warned up front, and a missed charge no longer forces an empty slam.

## Verification actually performed

- WeaponBalanceTests: 1,773 assertions passed using fresh sources in Studio Edit.
- EnemyScalingTests, NormalBalanceTests and GearPowerTests: 3,512 assertions passed in the Luau CLI. The roster audit covers all 42 weapon types; direct damage units are not necessarily entire attack cycles.
- EnemySpatialGridTests: 25,956 assertions passed against the new grid in Studio Edit. Actual-module crowd simulation also passed body size, exact overlap, corpse exclusion and boss avoidance checks. SpawnDirectorTests passed after integration.
- Fresh single-client Play, Pine Valley wave 20, God mode, weapons disabled: 63 regulars at 25 HP, 25 babies at 12 HP, 12 tanks at 138 HP, and the Hammer at 10,800 HP. Boss base speed was 22, damage multiplier 0.75, charge speed 36 and warning length 90.
- Stationary crowd observation with 100 ordinary mobs: five new samples contained 34, 27, 29, 28 and 31 unordered mob pairs closer than two studs; 8-9 ordinary mobs were within eight studs of the boss. A previous-version snapshot had 83 close pairs and 18 near the boss. These are observations from separate runs with different timing and positions, not a controlled quantitative performance comparison.
- A finite runtime QA script called the production legacy charge method on a grounded unobstructed lane at 85.000 studs. Charge accepted the target, reported speed 36 and warning length 90. After moving the test player out of the lane, the boss skipped the empty slam and released its anchored root. An initial automatic acquisition fixture failed to obtain a charge in its short deadline; the corrected open-lane fixture verifies the production method, not sustained automatic pursuit of a moving player.
- Gunner practice fixture, six Tier IV Dracos, Gear Power 1, no added items, critical chance overridden to zero: 148 observed nonlethal health changes at 15.180 damage and 132 at 10.626 (pierce falloff) over ten seconds. The practice run-kill counter stayed zero; this is damage-path validation, not a kill-rate benchmark. An earlier setup had reset to the starter build and was excluded from this check.
- Console inspection showed no game script errors; only the Studio assistant's camera-reset diagnostic appeared.

Not tested: a full Normal run, player-driven kiting feel, all weapons in live combat, rebuilt Hammer runtime, multiplayer or mobile frame time. The changes make Normal more forgiving and fix identified movement defects; these checks do not establish final balance.
