# Plan H: a cooler store, and quests that actually work

Status: the store and quests direction was approved by the user on 2026-10-01 from an HTML mockup with the real icons ("way better"). Changes they asked for:
- No text touching borders or other boxes. Example: "You have 4" under REROLLS sat on the ×5 box.
- The quests page should be "a little fancier and nicer" and should **work fully**.

## Decisions

| Question | Decision |
|---|---|
| Store look | The window, tabs, pills and buttons keep the green theme. Each **offer card gets a saturated colour backdrop** with a glow and rays behind its art. Art is big and sticks out past the card's top edge. |
| Item slots | Coloured by rarity (Godly is dark with a red rim, Legendary gold, Epic purple, Rare blue, Common grey, emeralds green). A name strip runs along the bottom, with the count (×3) in the corner. Godly slots pulse red. |
| Tags | The bouncing lime ribbon is gone. A still tag hangs off the card's top-left edge, and a diagonal sash sits in the top-right corner (BEST VALUE, ONE TIME). |
| Godly Starter | The chosen weapon lifts, glows and gets a ✓; the others go grey. The big art and the name on the right switch to the chosen weapon, so you always see what you're buying. "1 CHOOSE ONE" sits above the row. |
| Card shapes | Wide hero cards (Starter, Godly bundles, Godly Starter, Mega, Ultimate), a pair of half-width cards (Arsenal and VIP) and a row of three tall cards (Quick Open, Rerolls, Banishes). |
| Daily quests | **3 per day** per player, from a pool, with new ones at UTC midnight (the same reset as daily deals). Each pays emeralds; a boss quest also pays a Silver Chest. You press CLAIM to get the reward. |
| Streak | A day counts when you **finish all 3 daily quests** that day. Missing a day sets the streak back to 0. Rewards sit on days 1/3/7/10/15/20/30, and each one waits for CLAIM even if the streak breaks later. After day 30 the track starts again. |
| Weekly tab | Dropped. The tabs are DAILY and ACHIEVEMENTS. |
| Achievements | **Trophy roads**: 8 lifetime stats with 5 tiers each (Beginner → Master), paying emeralds plus a chest per tier. There are also 5 **unlocks**: Thrower, Juggler and Handyman classes, Mjolnir, and a Samurai armor set. |
| Dropped achievements | Molotov / Rocket Launcher (loadout-condition wins), and Tinfoil Antlers / Oven Mitt / Two Straws / Bone Crown (passives can't be locked). They could never be earned, so they're gone. |
| Class you already own | An unlock achievement for a class you already own pays 400 emeralds instead (the class's emerald price). |

## Numbers (QuestConfig)

For comparison:
- A full Normal Pine Valley run pays about 140 emeralds.
- The free daily deal is 200 emeralds.
- A Silver Chest costs 160 emeralds, a Gold Chest 300.

**Daily pool.** Each day rolls two "play" quests and one from the rest. The roll uses the day and the player's id as its seed, so the same player gets the same three all day.

| Quest | Target | Reward |
|---|---|---|
| Survive waves | 10 | 60 |
| Defeat enemies | 300 | 60 |
| Play runs (a run counts at its first cleared wave) | 3 | 50 |
| Defeat a map boss | 1 | 80 + Silver Chest |
| Earn emeralds in runs | 150 | 50 |
| Open chests | 3 | 40 |
| Upgrade any item | 1 | 40 |

**Streak.**

| Day | Reward |
|---|---|
| 1 | 50 emeralds |
| 3 | Silver Chest |
| 7 | Gold Chest |
| 10 | 250 emeralds |
| 15 | 2 Gold Chests |
| 20 | Magical Chest |
| 30 | Legendary Chest |

**Trophy roads.**

| Road | Stat | Targets |
|---|---|---|
| Survivor | waves survived | 25 / 100 / 300 / 1,000 / 3,000 |
| Slayer | enemies defeated | 500 / 2,500 / 10,000 / 50,000 / 200,000 |
| Boss Hunter | map bosses defeated | 1 / 5 / 15 / 50 / 150 |
| Champion | maps won | 1 / 3 / 10 / 25 / 60 |
| Collector | chests opened | 5 / 25 / 100 / 300 / 1,000 |
| Dedicated | best streak | 3 / 7 / 14 / 30 / 60 |
| Upgrader | upgrades | 1 / 5 / 20 / 50 / 120 |
| Questor | daily quests done | 5 / 20 / 60 / 150 / 365 |

Tier rewards:

| Tier | Reward |
|---|---|
| Beginner | 50 emeralds + Silver Chest |
| Intermediate | 120 emeralds + Silver Chest |
| Advanced | 250 emeralds + Gold Chest |
| Expert | 500 emeralds + Magical Chest |
| Master | 1,000 emeralds + Legendary Chest |

**Unlocks.**

| Achievement | Goal | Reward |
|---|---|---|
| Wave Rider | reach wave 10 on Pine Valley (any difficulty) | Thrower |
| Valley Victor | win Pine Valley | Juggler |
| Handy Work | 1,000 kills with Utility weapons | Handyman |
| Frost Breaker | win Frozen Pass | a Mjolnir copy |
| Endless Legend | reach wave 30 on any map | the Samurai set (4 pieces) |

## Where progress comes from (server only)

Test runs (the admin panel was used) and practice targets count nothing.

| Event | Source |
|---|---|
| kill (+ utility kill) | `ZombieDeath.onDeath` listener in RogueliteMeta. It credits `LastDamageUserId`, with the same rules as the leaderboard. The weapon comes from a new `LastWeaponId` that CombatEffectsService sets beside `LastDamageUserId`. |
| boss | the same listener. A map boss (`IsMapBoss`, not `BossPractice`) credits every run member. |
| wave / run / win | `Shop.onWaveCleared` in RogueliteMeta, for each member who isn't down. A run counts the first time a stint clears a wave; a win is wave 20. |
| earn | `ProfileService.settleRun` (what it pays). |
| chest | `ProfileService.openChest` (how many were opened). |
| upgrade | `ProfileService.upgrade`. |

Claims go through `ProfileAction`: `ClaimQuest(i)`, `ClaimStreak(day)`, `ClaimAchievement(road)` (the next tier) and `ClaimUnlock(id)`. The server checks everything and grants through `ProfileService.grant`. Rewards count as earned emeralds.

The client reads one attribute, `ProfileQuests` (JSON). A kill only marks the profile dirty, and dirty profiles are published at most once a second.

## Files

| File | Change |
|---|---|
| `combat/QuestConfig.luau` (new, ReplicatedStorage.RogueliteCombat) | Pools, streak, roads, unlocks, icons, rewards text. Shared by the server and the UI. |
| `combat/QuestService.luau` (new, ServerScriptService) | Pure logic on a profile table: `state`, `event`, `view`, `claim*`. No Instances, so it can be tested. |
| `combat/QuestTests.luau` (new) | Daily roll, progress, claims, streak (including a break), roads, unlocks. |
| `combat/ProfileService.luau` | A `quests` field, events, the throttled `ProfileQuests` publish, and the claim functions. |
| `combat/RogueliteMeta.server.luau` | The kill/boss listener, wave/run/win hooks, and the claim actions. |
| `combat/CombatEffectsService.luau` | Sets `LastWeaponId` beside `LastDamageUserId`. |
| `ui/StoreFX.luau` | `card`, `tile`, `sash`, `tag`, `header` and `title` helpers. |
| `ui/LobbyUI.luau` | The store tabs redrawn with the new helpers, the Quests window rebuilt, and the HUD tracker showing today's quests. |

## Done (2026-10-02, repo; Studio sync waits for the user's okay)

- QuestConfig, QuestService (pure), and QuestTests: 585 checks pass in Studio Edit on fresh copies.
- ProfileService finds QuestService with FindFirstChild and wraps every call in pcall, so quests can never stop a payout, chest open or upgrade. RogueliteMeta's hooks check that the ProfileService functions exist.
- StoreUI, QuestsUI and the StoreFX helpers. The layout audit passes on 6 tabs at 7 screen sizes. Only the shared window chrome is flagged at phone scale.
- Rojo project entries for the four new modules; AssetPreloader preloads QuestConfig's icons.
- The Phoenix and Dragon Scale armor icons in Studio's ArmorCatalog are newer uploads than the repo's ids. That's another session's area; the store reads whatever the catalog has.

## Checks

- QuestTests pass in Studio Edit, run against fresh copies of the modules.
- `UILayoutAudit.sweep` reports 0 problems on all four store tabs and both quest tabs at every device size. This needs Play, so the user runs it or okays a short Play.
- Not testable here: real Robux receipts, DataStore saving, several players sharing a boss kill.
