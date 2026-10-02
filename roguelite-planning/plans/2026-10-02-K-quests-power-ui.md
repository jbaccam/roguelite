# Plan K: quests screen, more quests, 10-level achievements, Power plate

Status: design approved by the user on 2026-10-02 from an HTML mockup with the real icons ("this looks alot better"). One change: the Power icon is a **flexed bicep**, not a lightning bolt ("a lightning bolt looks like charge or battery").

This is part 1 of a 4-part UI request (same day):

| Part | What | Status |
|---|---|---|
| 1 | Quests screen, left tracker, more daily quests, 10-level achievements, Power plate | this plan |
| 2 | Pause screen: solo freezes the game; in multiplayer it only freezes once everyone has paused | next |
| 3 | Player profile: click a player to see their gear and lifetime stats | later |
| 4 | Titles over heads, earned from achievement levels, picked on your profile | after 1 and 3 |

Ground rules (plan J, memory): repo first, then ask "push it to Studio?"; no Play sessions without asking; other sessions edit LobbyUI, ProfileService, RogueliteMeta and ArmoryUI, so change those with anchored hunks and commit HEAD + your own hunks only; every new UI must pass `UILayoutAudit` at every device size.

## What the user asked for

- The streak sat under the quest cards, so you had to scroll to see it. It goes to the top.
- The quests window felt squished.
- The left-side quest tracker could look better (reference: a light list with an icon, a bar and the reward on the right).
- More daily quests, and more quests in general.
- Achievements that stay after you claim them and come back harder (reference: "Inferno Veteran (5/10)"). Ours already did this with 5 tiers, but the screen didn't make it obvious.
- "idk wtf power means but its not fit right on its icon or look good in the armory."
- They'll AI-generate any icons we need.

## Decisions

| Question | Decision |
|---|---|
| Daily quests per day | **4** (user's pick). Each day rolls 3 run quests + 1 of any kind. |
| Streak rule | A day counts once **all 4** are finished. Everything else stays as plan H (milestones 1/3/7/10/15/20/30, each waits for CLAIM, the track repeats after 30). |
| Daily pool | 7 → 16 kinds (table below). No "play with a friend" quest: a solo player could never finish it, and it would break their streak. |
| Achievement levels | 5 → **10** per road, shown as **Slayer (4/10)**. Claiming one brings the same row back with the next goal. |
| Level names | Rookie, Beginner, Intermediate, Skilled, Advanced, Expert, Elite, Master, Grandmaster, Legend. Each level is also a future title ("Slayer Skilled", part 4). |
| Roads | 8 → **15**: the 8 we have, plus Playtime, Hatcher, Rich, Runner, Heavy Hitter, Leveler and Achiever. |
| Old saves | Levels already claimed carry over by their goal number (each old target is also a new one), so nobody loses a claim or claims the same reward twice. |
| Quests window | About 40% bigger: content 1480 × 840 (was 1100 × 640). Streak strip on top, 4 tall cards in a row. Achievements are wide rows. The frame is very slightly see-through (ImageTransparency .05, Quests only). |
| Left tracker | 4 see-through rows, each with the quest icon in a round well, the name, a slim bar with "1 / 3" and the reward chip on the right. A finished quest glows gold and shows its own CLAIM button, which claims without opening the window. A streak line ("5 DAY STREAK · 1 / 4 today") sits under them, then OPEN QUESTS with the red count badge. |
| Power plate | One plate: bicep icon, "POWER" small, the number big, and a **?** button. The `+x% dmg +y% hp` line moves into the **?** card. |
| Power card (the ?) | "What is Power? Your gear's levels added up. Better gear = more Power = more damage and health in runs." Then your gear adding up (starter weapon tier, armor tiers, pet tier) to "= POWER 6", "+60% damage · +30% health", and each map's recommended Power. |
| Icons | The user makes them (list at the end). Until each one arrives, the code uses the fallback in the icon table, so nothing waits on art. |

## Daily pool (QuestConfig.Daily)

Run quests (`play=true`) need a real run. Lobby quests don't. Each day: three picks among run quests, then one pick among all that are left, by weight. The seed is the day and the user id, as in plan H.

| id | Title | Stat | Target | Reward | Weight | Kind |
|---|---|---|---:|---|---:|---|
| Waves | Survive 10 Waves | waves | 10 | 60 | 3 | run |
| Kills | Defeat 300 Enemies | kills | 300 | 60 | 3 | run |
| Runs | Play 3 Runs | runs | 3 | 50 | 3 | run |
| Earn | Earn 150 Emeralds | earn | 150 | 50 | 2 | run |
| Boss | Defeat a Map Boss | bosses | 1 | 80 + Silver Chest | 1 | run |
| DeepRun | Reach Wave 10 in One Run | deepRuns | 1 | 60 | 2 | run |
| Minutes | Play 20 Minutes | minutes | 20 | 50 | 2 | run |
| Levels | Level Up 15 Times | levels | 15 | 50 | 2 | run |
| Shards | Collect 300 Shards | shards | 300 | 50 | 2 | run |
| Melee | Defeat 150 Enemies with Melee | meleeKills | 150 | 60 | 2 | run |
| Ranged | Defeat 150 Enemies with Ranged | rangedKills | 150 | 60 | 2 | run |
| Buys | Buy 5 Shop Items | buys | 5 | 50 | 2 | run |
| Damage | Deal 50,000 Damage | damage | 50,000 | 60 | 2 | run |
| Chests | Open 3 Chests | chests | 3 | 40 | 2 | lobby |
| Upgrade | Upgrade Any Item | upgrades | 1 | 40 | 2 | lobby |
| Hatch | Hatch an Egg | eggs | 1 | 40 | 1 | lobby |

A typical day pays about 220 emeralds (170 before). For scale: the free daily deal is 200, and a full Normal Pine Valley run is about 140.

**Damage and Shards targets are first guesses.** Check them against play-test numbers once RunAnalytics has damage per run (plan J item 7); a daily should take about one or two runs.

## New stats and where they're counted (server only, real runs only)

Test runs (admin panel used) and practice count nothing, as in plan H. "Real run" means the same check the kill listener already uses.

| Stat | Counted when | Where |
|---|---|---|
| minutes | +1 for each minute a player spends in a real run (any phase, down or alive) | a 60 s loop in RogueliteMeta over `Shop.members` |
| deepRuns | +1 when a member clears wave 10 in a run (once per stint) | RogueliteMeta's wave-cleared hook, beside `waves` |
| levels | +1 per run level gained | new `Shop.onLevelUp(p, gained)` hook (ShopService is sandboxed; RogueliteMeta listens, like `onWaveCleared`) |
| shards | + shards picked up | new `Shop.onShards(p, n)` hook where collected shards are credited |
| buys | +1 per shop item bought | new `Shop.onBuy(p, id)` hook |
| meleeKills / rangedKills | with `kills`, by the killing weapon's `kind` (`Melee`, or anything else for ranged) | the existing kill listener (`LastWeaponId`) |
| damage | damage dealt by the player's hits, summed per player and sent once a second | `CombatEffectsService.hit` adds to a per-player tally; RogueliteMeta flushes it to `questEvent` |
| eggs | + eggs hatched | `ProfileService.openEgg` |

`runs`, `waves`, `kills`, `bosses`, `wins`, `earn`, `chests`, `upgrades`, `quests` and `utilityKills` stay as plan H built them.

## Achievements: 15 roads × 10 levels

Old targets (plan H) are all kept inside the new lists, so old saves convert exactly.

| Road | Stat | Targets (levels 1 → 10) |
|---|---|---|
| Survivor | waves | 10, 25, 100, 300, 600, 1,000, 2,000, 3,000, 5,000, 10,000 |
| Slayer | kills | 100, 500, 2,500, 10,000, 25,000, 50,000, 100,000, 200,000, 500,000, 1,000,000 |
| Boss Hunter | bosses | 1, 3, 5, 15, 30, 50, 100, 150, 300, 500 |
| Champion | wins | 1, 2, 3, 5, 10, 25, 40, 60, 100, 200 |
| Collector | chests | 3, 5, 25, 50, 100, 300, 500, 1,000, 2,000, 5,000 |
| Dedicated | best streak | 2, 3, 5, 7, 14, 21, 30, 45, 60, 100 |
| Upgrader | upgrades | 1, 3, 5, 10, 20, 35, 50, 80, 120, 200 |
| Questor | daily quests done | 3, 5, 20, 40, 60, 100, 150, 250, 365, 600 |
| Playtime (new) | minutes in runs | 30 min, 1 h, 3 h, 6 h, 10 h, 20 h, 40 h, 75 h, 150 h, 300 h |
| Hatcher (new) | eggs | 1, 3, 5, 10, 25, 50, 100, 200, 350, 500 |
| Rich (new) | earn | 500, 1,500, 5,000, 10,000, 25,000, 50,000, 100,000, 200,000, 400,000, 1,000,000 |
| Runner (new) | runs | 3, 10, 25, 50, 100, 200, 350, 500, 750, 1,000 |
| Heavy Hitter (new) | damage | 50K, 250K, 1M, 3M, 10M, 30M, 100M, 300M, 1B, 3B |
| Leveler (new) | levels | 10, 50, 150, 400, 1,000, 2,000, 4,000, 7,500, 12,000, 20,000 |
| Achiever (new) | levels claimed on other roads + unlocks claimed | 3, 10, 20, 30, 45, 60, 80, 100, 120, 145 |

Achiever's 145 is everything else: 14 roads × 10 levels + 5 unlocks. Heavy Hitter's targets get the same play-test check as the Damage daily.

**Level rewards** (the same on every road):

| Level | Name | Reward |
|---:|---|---|
| 1 | Rookie | 25 emeralds |
| 2 | Beginner | 50 + Silver Chest |
| 3 | Intermediate | 100 + Silver Chest |
| 4 | Skilled | 200 + Gold Chest |
| 5 | Advanced | 300 + Gold Chest |
| 6 | Expert | 500 + Magical Chest |
| 7 | Elite | 700 + Magical Chest |
| 8 | Master | 1,000 + Legendary Chest |
| 9 | Grandmaster | 1,500 + Legendary Chest |
| 10 | Legend | 2,500 + 2 Legendary Chests |

The first three levels of all 15 roads pay 2,625 emeralds and 30 Silver Chests in total, against 1,360 and 16 for the first two tiers of plan H's 8 roads. That's more up front, on purpose: early levels should come quickly. Re-run the economy sim (`economy-sims/`) with the new daily and early-level payouts before outside testers.

**Old save conversion.** `quests.roadsVersion` is new. A save without it converts each road's old tier number to the level whose target equals that old tier's target, using `QuestConfig.LegacyRoadTargets`. Example: Slayer old tier 3 (10,000 kills) → new level 4 claimed. Levels skipped in between are not paid; the old tiers already paid more. Then `roadsVersion=2`. Unlocks are unchanged.

| Old tier → new level | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Survivor | 2 | 3 | 4 | 6 | 8 |
| Slayer | 2 | 3 | 4 | 6 | 8 |
| Boss Hunter | 1 | 3 | 4 | 6 | 8 |
| Champion | 1 | 3 | 5 | 6 | 8 |
| Collector | 2 | 3 | 5 | 6 | 8 |
| Dedicated | 2 | 4 | 5 | 7 | 9 |
| Upgrader | 1 | 3 | 5 | 7 | 9 |
| Questor | 2 | 3 | 5 | 7 | 9 |

## Screens

### Quests window (QuestsUI)

- `T.window(..., 1480, 840, nil, {large=true, seeThrough=.05})`. `seeThrough` is a new option in `T.window` that only sets the frame's ImageTransparency; other windows don't pass it.
- **Tabs:** DAILY and ACHIEVEMENTS (64 tall), each with its icon and red count badge, as now.
- **Daily tab, top to bottom:**
  1. **Streak strip** (ember card, 150 tall): the flame with the day count on it, "DAY STREAK", "Best: n days", and a "TODAY: n / 4 DONE" pill. The 7-milestone track fills the rest. A milestone waiting for its reward glows and has a CLAIM button under it; the next one glows orange.
  2. "DAILY QUESTS" header, "New quests in hh:mm:ss".
  3. **4 cards in a row** (448 tall): colour title band, art with rays, progress bar, REWARDS tiles, and an IN PROGRESS / CLAIM / CLAIMED button. A finished card turns gold with a "COMPLETE!" tag and a shine. A claimed card turns steel with a check.
- **Achievements tab:**
  - Header, the line "Claim one and it levels up to a harder goal with a bigger reward.", and the total bar "n / 155 complete" (150 levels + 5 unlocks).
  - **Rows** (124 tall) are sorted ready → in progress → done. Each row has:
    - a rank diamond in the level's colour, with the stat icon on it;
    - "**Slayer (4/10)**" and a chip with the level name;
    - the goal and a progress bar;
    - 10 small level pips;
    - the reward tiles and a TITLE tile ("Slayer Skilled") that previews part 4;
    - CLAIM, or the percent done.
  - A finished road shows "Legend · DONE".
  - Unlocks keep their own section, drawn as the same rows without the (n/10).
- **Level colours:** Rookie grey, Beginner bronze, Intermediate silver, Skilled gold, Advanced emerald, Expert blue, Elite purple, Master red. Grandmaster is dark with a gold rim, and Legend dark red with a pulsing red rim (like Godly item slots).
- Everything else works as plan H: every CLAIM is a `ProfileAction` the server checks.

### Left tracker (LobbyUI)

The tracker stays at the same spot under the emeralds, 372 wide. It shows the header ("DAILY QUESTS" with the time to reset), the 4 rows, the streak line and OPEN QUESTS. The CLAIM on a finished row calls `ProfileAction ClaimQuest(i)` directly. Clicking anywhere else on the tracker opens the window, as now. The rows sit on dark strips at about 50–80% opacity, so the world shows through.

### Armory Power plate (ArmoryUI)

- **Plate row under the dais:** Damage, Health and Power plates, 680 wide in total (196 + 196 + 264, gaps of 12), scaled down to fit when the slot ring is narrower.
- **Power plate:** lime face, bicep icon, "POWER", the number, and a **?** button.
- **? card:** opens beside the plate, and a click anywhere else closes it. It gets its numbers from a new `RunSetupRules.powerParts(player, weapon)`, which returns `{weapon=, armor=, pet=, total=}` (the same sum as `R.power`).
- **Map select** shows the same bicep icon in front of "Your power n · recommended m".

## Files

| File | Change |
|---|---|
| `combat/QuestConfig.luau` | 16-quest pool, `DailyCount=4`, 3 run + 1 any roll, 15 roads × 10 targets, 10 level names, rewards and colours, `LegacyRoadTargets`, new stats, new icons with fallbacks, `short(n)` (25K, 1.2M) and `hours(min)` formatting |
| `combat/QuestService.luau` | Roll of 4, old save conversion (`roadsVersion`), Achiever as a derived stat, streak needs all 4 |
| `combat/QuestTests.luau` | Roll (3 run + 1 any, same all day), conversion for every road and tier, 10-level claims, Achiever, the new stats, streak with 4 |
| `combat/ShopService.luau` | `onLevelUp`, `onShards` and `onBuy` hooks (anchored hunks) |
| `combat/CombatEffectsService.luau` | Per-player damage tally in `hit` (anchored hunk) |
| `combat/RogueliteMeta.server.luau` | Minutes loop, deepRuns, melee/ranged kills, damage flush, the shop hooks (anchored hunks) |
| `combat/ProfileService.luau` | `eggs` event in `openEgg` (anchored hunk) |
| `lobby/RunSetupRules.luau` | `powerParts` |
| `ui/UITheme.luau` | `T.window` `seeThrough` option |
| `ui/QuestsUI.luau` | Window, streak strip, 4 cards, achievement rows |
| `ui/LobbyUI.luau` | Tracker (anchored hunks) |
| `ui/ArmoryUI.luau` | Power plate and ? card (anchored hunks) |
| `ui/RunSetupUI.luau` | Bicep icon beside the power line |
| `ui/AssetPreloader.luau` | Preload the new icons |
| `GEAR_POWER.md`, plan H | Point at this plan where they describe the plate and the 5 tiers |

## Checks

- QuestTests pass on fresh copies in Studio Edit.
- The windows are built in Edit from fresh repo modules into CoreGui (memory: "Preview UI without Play"), with `UILayoutAudit.run` at 1920×1080, 1366×768, 2560×1080, 844×390 and 1024×768. Only the shared window chrome may be flagged at phone scale.
- `UILayoutAudit.sweep` in Play on the Quests tabs, the lobby HUD and the Armory. This needs Play, so the user runs it or okays a short Play.
- Not testable here: real DataStore conversion of an old save (checked in QuestTests on old-shaped tables instead), several players sharing a boss kill.

## Icons the user is making

512 × 512, transparent background, the same stylized look as the upgrade icons. Each one is uploaded and swapped into `QuestConfig.Icons` / `T.Asset`; until then the fallback shows.

| Icon | Used for | Fallback until it arrives |
|---|---|---|
| Flexed bicep (strength) | Power plate, ? card, map select | no icon, text only |
| Streak flame | Streak strip, tracker streak line, Dedicated | Elemental Damage flame |
| Clock | Play 20 Minutes, Playtime | Move Speed wings |
| Sword burst | Deal Damage, Heavy Hitter | Damage fist |

Parts 2–4 need: a pause button (two bars on a round stone) and a name tag / ribbon for titles.

## Built (repo, 2026-10-02)

Build steps: [2026-10-02-K-build-steps.md](2026-10-02-K-build-steps.md). The commits, in order:

| Commit | What |
|---|---|
| 6e8abdd, f660fc4 | Dev tools: anchored hunks, local dev server, fresh module loader, GUI dump and browser viewer |
| d8e03b9 | QuestConfig (16 dailies, 4 a day, 15 roads × 10 levels), QuestService (old-save conversion, Achiever), QuestTests |
| 91817fd | Run stats: level-ups, shards, buys, damage (plan J's hooks), minutes, wave 10, melee/ranged kills, eggs |
| 6531636 | `CharacterStats.gearParts`, `RunSetupRules.powerParts` |
| 405a292 | StatPlates in the Armory: DAMAGE, HEALTH, POWER and the "What is Power?" card |
| bb00288 | QuestsUI: the bigger window, streak strip, 4 cards, 10-level rows, `Q.tracker`; `T.window` gains `seeThrough` |
| 5903928 | LobbyUI uses the new tracker |
| d215dfa | `tools/SyncPlan.luau` and the plan K manifest |

**Checks in Studio Edit (fresh repo copies, no Play):**
- QuestTests: **1,223 checks pass**.
- Every changed script compiles.
- `gearParts.total` equals `gearPower` on three sample profiles.
- `UILayoutAudit.run`:
  - the Quests window has 0 problems at 1920×1080 and 1366×768;
  - at 1024×768 and 844×390, only the shared window chrome (title plate, close X) is flagged;
  - the tracker and the Power plates with their card have 0 problems.
- The Studio sync's dry run passes:
  - 3 modules updated, StatPlates created;
  - 13 hunks across 7 scripts, every anchor found once;
  - the module guards match commit 7fd7cea.

**Not done yet:**
- The Studio write. It waits for the user's okay.
- The bicep icon for Power. `StatPlates.PowerIcon` and map select get it when it arrives.
- Play tests (the checklist in the build steps, Task 12).
- Re-running the economy sim with the new daily and early-level payouts.
- Checking the Damage and Shards targets against play-test numbers.

