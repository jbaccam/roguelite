# October 5 combat feedback implementation

**Current follow-up:** [Normal difficulty, actual crowd steering and Hammer pursuit](NORMAL_CROWD_INTEGRATION_2026-10-05.md) are synchronized to Studio, with fresh Play checks recorded. This supersedes earlier Normal HP values and spawn-only crowd corrections. Class debuffs remain intact; Normal now applies 0.60 HP / 0.75 damage across regular enemies and bosses.

**Latest follow-up:** [Continuous spawn distribution](SWARM_DISTRIBUTION_2026-10-05.md) supersedes the larger 6–8-mob packets below: groups of 2–4 now arrive on one shared 0.22-second schedule, rotating around current player positions. [Draco tuning](DRACO_TUNING_2026-10-05.md) raises its Tier IV raw damage from 8 to 11. All 18 manifest destinations are synchronized to Studio. Fresh Play verified all eight spawn sectors, 2–4-mob ordinary cohorts, and the expected 10.491 direct-hit damage in the reported Brawler setup. WeaponBalanceTests passed 1,773 assertions in Edit; the spawn director suite and required Rojo build passed. This was a stationary God-mode combat fixture, not a full run, multiplayer or persistence test. Studio returned to Edit after testing. Earlier verification records below describe the prior integration.

**Status: source synchronized to Studio after the fodder-scaling correction; combat build passed.** The first implementation had no Studio connection. The follow-up synchronized all 16 scripts, passed 2,496 scaling checks in Edit and performed a single-client startup/runtime-number smoke test. No combat waves, published-place changes, or production DataStore tests ran. The combat overlay preserves the existing map and unrelated instances; the root Copy The Scene project is not involved.

Five dedicated subagents handled the requested tasks, followed by an integration review.

## Changes

- [Straight gunfire](STRAIGHT_GUNFIRE_2026-10-05.md): guns no longer ricochet, rockets no longer weave or retarget, grazing pierces remain collinear, and tracers no longer bend toward a moving client muzzle. Shotgun spread is multiple independent straight shots. Throwing/magic rebound remains available. Turret eligibility and regression expectations were updated too.
- [Rewards](RUN_REWARDS_2026-10-05.md): Restart opens the reward receipt; Play Again and lobby return wait for a successful save and a short reward reveal. The animated emerald total includes first-win rewards, shows the wallet balance, and distinguishes saved, retrying, Studio-only and test-run status. Retries write the already-settled profile without granting twice. Permanent collection and emeralds survive replay; the temporary run build resets.
- [Larger swarms](SWARM_PRESSURE_2026-10-05.md): solo wave 1/5/10/20 occupancy targets are 19/48/84/100, groups contain 6–8 mobs, and larger packets refill faster and closer. Full spawn warnings remain. Missing ordinary-wave slots repair automatically; tutorial/no-respawn counts remain protected.
- [Enemy scaling](ENEMY_SCALING.md): health grows by a flat amount per wave, differentiated by enemy role and tuned against actual upgraded weapon output. Standard-run movement speeds stay unchanged. Following the user correction, wave-20 regular/baby/tank HP is 41/20/229. Starter Pan/Glock/Staff damage exceeds regular HP through wave 5; strong builds may one-shot ordinary late fodder. Contact damage grows more gently to account for increased crowd density. Existing map, difficulty and Endless multipliers remain.
- [White hit feedback](HIT_FLASH_FIX_2026-10-05.md): a larger bounded pool supports swarm-wide hits, including damage-over-time. White holds for 80 ms and fades over 100 ms. Ordinary lethal targets remain inert for 250 ms so the lethal hit can flash, with immediate reward settlement and removal from live targeting.

## Verification actually performed

| Check | Result | Scope |
| --- | --- | --- |
| Official Luau 0.741 compilation | 25 changed/new scripts passed | Source compilation; not Roblox runtime execution |
| Existing EnemySchedulerTests | 187,712 assertions passed | Actual scheduler/test source in CLI; seeded PRNG substitute for Roblox Random |
| Rocket trajectory sampling | 36,720 assertions passed | Actual RocketMotion across 360 headings and 51 distances |
| EnemyScalingTests | 2,496 assertions passed | Actual catalog, weapon/stat and scaling modules with minimal dependency stubs |
| Reward receipt checks | 26 assertions passed | Extracted production settlement/receipt functions; mocked profile transport, clocks and task scheduling |
| HitFeedbackTests | 246 assertions passed | Actual pool selection and timing code with service stubs |
| ZombieDeath lifecycle | 6 assertions passed | Actual death module with model/service stubs |
| Whitespace validation | Passed | `git diff --check` |
| Combat Rojo overlay | Follow-up build passed after the separate ShopUI edit was corrected | Required combat project only |

Studio-dependent projectile collision, shop and turret integration suites have updated expectations but were not run. Visual review, real save failures/rejoin persistence, multiplayer replication, mobile rendering cost, a complete 20-wave run, and sustained 100-enemy pressure remain unverified. Offline checks do not establish final gameplay balance or device performance.

The successful build generated `build/RogueliteKatanaCombat.rbxlx`. After a comment-only scheduler cleanup, the final rebuild detected a concurrent change outside this task: `ui/ShopUI.luau` contained invalid UTF-8 (byte `0xB7` in its GODLY label). It was left untouched to preserve that separate edit. All **16 production script destinations** in this task's sync manifest independently passed UTF-8 decoding and official Luau compilation afterward. The separate ShopUI edit subsequently regained valid encoding; the overlay was rebuilt successfully after the fodder correction.

## Studio integration completed

`combat-feedback-2026-10-05-sync.json` lists changed production scripts at their combat-project destinations for `tools/FeatureSync.luau`. It excludes test fixtures. Use the existing source-only synchronization workflow against place **107877054949326**, preserving instance capabilities, maps, templates and unrelated work. Do not open or synchronize the root Copy The Scene project into that place.

Build with:

```powershell
rojo build roguelite-planning/studio-prototype/combat/default.project.json -o build/RogueliteKatanaCombat.rbxlx
```

After connecting Studio, verify six mixed guns with Pierce/Bounce bonuses while turning and moving, ordinary and lethal multi-target hit flashes, wave 10/20 swarm pressure, and results → save status → Play Again. Studio testing must use in-memory profiles; real DataStore fault/rejoin validation needs a separate approved test environment.

Follow-up Play coverage: one client started in the lobby; the server confirmed regular HP at waves 1/2/3/5/10/20 and starter damage 24.84 (Pan), 16.56 (Glock), 12.9375 (Staff). Console output was empty. Play stopped after the checks. This did not test actual hits, a full wave, visual effects, or rewards replay. See ENEMY_SCALING.md for corrected tuning.

## Apply-everything verification

On the explicit request to apply everything, regenerated the sync manifest from every changed production Luau file mapped by the combat Rojo project: **17 destinations** (including the pending ShopUI update). Source-only FeatureSync applied one remaining difference, created no instances, and verified all 17 destinations byte-equal after newline normalization. Existing maps, templates, capabilities and unrelated instances were preserved. Combat overlay build passed.

Ran a fresh single-client Studio Play startup: server assertions confirmed 3/41 regular HP on waves 1/20, 84 solo enemies requested on wave 10, and disabled Glock bounce; client assertions confirmed the 128-flash pool, 80ms hold, and presence of results/shop UI modules. Console output was empty. Stopped Play afterward and left Studio in Edit mode. These are startup/configuration checks, not full combat/rewards/persistence playthroughs. No production DataStores, persistent rewards, or publishing were used.

## Hit colours (2026-10-10)

Play-testers asked for coloured hit markers per element, a crit colour, and turret damage told apart. The server decides all three in `CombatEffectsService.hit` and sends them in the hit flags byte's spare high nibble (`ShotBatch.style` / `unstyle`), so a HitFX record stays 18 bytes plus its id. Kills on the reliable `Hit` remote carry the same number as a 10th argument; a missing or malformed one reads as a plain hit.

Fill says who or how; an element adds a coloured outline (`UIStroke`, 2 px, made once per pooled number):

| Style | Fill | Outline | Size |
|---|---|---|---|
| Plain hit | cream 255,246,218 | dark text stroke 28,22,20 | 1x |
| Crit | hot red 255,64,48, ends in `!` | white 255,255,255 | 1.3x |
| Handyman turret | steel 176,190,204 | dark text stroke | 0.85x |
| Burn tick (fire) | orange 255,140,40 | ember 150,40,10 | 1x |
| Frost (the hit that lands a slow) | 228,246,255 | blue 30,120,235 | 1x |
| Poison tick | 226,255,196 | deep green 36,120,24 | 1x |
| Lightning (chain, Mjolnir strike) | pale yellow 255,250,170 | electric cyan 0,190,220 | 1x |
| Damage taken | red 235,72,72 (unchanged) | unchanged | unchanged |

Crit or turret with an element keeps the crit/turret fill and size and adds the element outline. Turrets never crit; if both arrived, the turret look wins. Only numbers of the same style merge (0.2 s window), so a crit or a burn never folds into a plain number.

Tests: `python roguelite-planning/studio-prototype/combat/run_hit_feedback_tests.py build/luau-validation/luau.exe` (HitFeedbackTests 362 checks, CombatWireTests 2449 checks, with engine stubs). No Studio sync and no Play test was run for this change.

**Revision, same day (user: "gold on crits and peach on fire is kinda odd"; ice, poison and turret kept).** The table above is the current look: crits went from gold to hot red with a white outline, fire from peach on orange to a real orange on an ember outline, lightning from violet to an electric cyan outline. A crit is close in hue to damage taken (235,72,72), but damage taken shows only over your own character, with a `-`, a bigger size and a dark red outline, so they don't meet.

**Impact streaks take the colour too.** `MobImpactVisuals` tints the white streak atlas (`ImageColor3`, no new art) with `HitFeedbackVisuals.sparkColor`: the element's hue wins (fire 255,140,40, frost 120,200,255, poison 120,220,70, lightning 255,245,140), else turret steel, else crit red; a plain hit stays white. Burn and poison ticks, which drew no streaks before, now draw a small 3-ray puff in their colour (still throttled to one impact per enemy per 0.07 s). Example: a Medusa hit shows a blue-outlined number and pale blue shards; a crit with a plain Katana shows a red `42!` with red shards. Tests: HitFeedbackTests 369 checks (sparkColor order and every element), CombatWireTests 2449.
