# Plan M: feats, weekly quests and bigger achievement rewards

Status: design approved by the user on 2026-10-02 ("Looks good, go on"). UI waits on an HTML mockup with the real icons (memory: UI mockup first).

## What the user asked for

"We need more achievements and quests that give more emeralds than 25, like how Clash of Clans has harder quests that give more emeralds." They also asked how much rewards and goals grow from one level to the next.

**Why it felt like 25.** Every road starts at level 1 (25 emeralds), and a row only shows its current level. A new player sees 15 rows that all say 25. Bigger rewards exist (level 10 pays 2,500 + 2 Legendary Chests) but sit out of sight. Daily quests pay 40–80.

**How roads scale today.** Rewards are the same on every road: 25, 50, 100, 200, 300, 500, 700, 1,000, 1,500, 2,500, plus a chest from level 2. Goals grow faster than rewards. On Survivor (about 15 waves a run), levels 1 and 2 take one run each, level 3 takes 5 more, level 4 takes 13 more, and level 10 takes about 660 runs in total. From level 1 to 10 the goal grows about 1,000× and the reward 100×.

The user picked all three additions:

| Part | What |
|---|---|
| A | **Feats**: 12 one-time hard challenges, 300–1,500 emeralds + a chest each |
| B | **Weekly quests**: 3 a week, 300 each, the hard one 600 + a Gold Chest |
| C | **Road fixes**: level 1 pays 50, rows show the next level's reward, 4 new roads |

Ground rules (plans J/K, memory): repo first, then ask "push it to Studio?"; no Play sessions without asking; other sessions edit ProfileService, RogueliteMeta, LobbyUI and QuestsUI, so change those with anchored hunks and commit HEAD + your own hunks only; every new UI passes `UILayoutAudit` at every device size.

## Numbers to compare against

- A full Normal Pine Valley run pays about 140 emeralds. A Volcanic Crater Nightmare win pays about 800.
- Silver Chest 160, Gold Chest 300, Magical Chest 700, a pet egg 250.
- Doing every daily quest pays about 220 a day, or 1,500 a week.
- Emerald packs sell 100 emeralds for 99 R$, so big free payouts go to skill, not just time played.

## A. Feats

One-time challenges in a new **FEATS** section of the Achievements tab, between the roads and UNLOCKS. Each pays once, by stars:

| Stars | Reward |
|---|---|
| ★ | 300 emeralds + Silver Chest |
| ★★ | 750 emeralds + Gold Chest |
| ★★★ | 1,500 emeralds + Magical Chest |

| id | Name | Goal | Stars | Goal in QuestConfig |
|---|---|---|---|---|
| LoneWolf | Lone Wolf | Win a map solo | ★ | `{win='*',solo=true}` |
| StepItUp | Step It Up | Win any map on Hard | ★ | `{win='*',diff='Hard'}` |
| JackOfAllTrades | Jack of All Trades | Win with 3 different classes | ★ | `{classes=3}` |
| Untouchable | Untouchable | Win a map without going down | ★★ | `{win='*',flawless=true}` |
| LoneLegend | Lone Legend | Win solo on Hard | ★★ | `{win='*',diff='Hard',solo=true}` |
| NightmareWalker | Nightmare Walker | Win any map on Nightmare | ★★ | `{win='*',diff='Nightmare'}` |
| DeepDiver | Deep Diver | Reach wave 40 on any map | ★★ | `{best='*',wave=40}` |
| Abyss | Abyss | Reach wave 50 on any map | ★★★ | `{best='*',wave=50}` |
| NightShift | Night Shift | Reach wave 30 on Nightmare | ★★★ | `{best='*',diff='Nightmare',wave=30}` |
| MasterOfAll | Master of All | Win with all 6 classes | ★★★ | `{classes=6}` |
| FlawlessNightmare | Flawless Nightmare | Win on Nightmare without going down | ★★★ | `{win='*',diff='Nightmare',flawless=true}` |
| DragonSlayer | Dragon Slayer | Win Volcanic Crater on Nightmare | ★★★ | `{win='VolcanicCrater',diff='Nightmare'}` |

All 12 pay 11,400 emeralds + 3 Silver, 4 Gold and 5 Magical Chests.

**Rules.**
- `diff` means that difficulty or harder: a Nightmare win counts for "on Hard". No `diff` means any difficulty.
- **Solo**: you were the only member of the run at every wave clear, from wave 1 to the win. Someone joining late, or a party member leaving partway, means it wasn't solo.
- **Without going down**: you never died during the run, from wave 1 to the win. A death counts even when a revive (bought or not) or a phoenix item brings you back, so no purchase can earn a no-down feat.
- Solo and no-down also need the stint to start at wave 1 (`m.joined==1`), so joining a run at wave 19 doesn't count.
- **Classes**: the class you won with (`Characters.states[p].class`). Brawler, Gunner and Mage are free. Thrower, Juggler and Handyman are earned from unlocks (or bought early), so Master of All never requires a purchase.
- Feats from saved records count right away: Step It Up, Nightmare Walker and Dragon Slayer read `mapWins`, and Deep Diver, Abyss and Night Shift read `bestWaves`. Solo, no-down and class feats count from this release on, since nothing recorded them before.
- Waves 40 and 50 are first guesses. Check them against the Highest Wave leaderboard after launch.

## B. Weekly quests

A **WEEKLY** tab between DAILY and ACHIEVEMENTS (plan H dropped an empty one; this one has real quests). 3 quests a week, new ones every **Monday 00:00 UTC**:

- **2 normal quests**, 300 emeralds each. Each takes about 5–8 runs.
- **1 hard quest**, 600 emeralds + a Gold Chest.

A full week pays 1,200 emeralds + a Gold Chest.

**Normal pool** (300 each):

| id | Title | Stat | Target |
|---|---|---|---:|
| Wins | Win 3 Maps | wins | 3 |
| Bosses | Defeat 5 Map Bosses | bosses | 5 |
| Waves | Survive 100 Waves | waves | 100 |
| Runs | Play 10 Runs | runs | 10 |
| Hours | Play 2 Hours | minutes | 120 |
| DeepRuns | Reach Wave 10 in 5 Runs | deepRuns | 5 |
| Dailies | Finish 12 Daily Quests | quests | 12 |
| Levels | Level Up 100 Times | levels | 100 |
| Chests | Open 10 Chests | chests | 10 |

**Hard pool** (600 + Gold Chest). `needs` = what the player must have unlocked when the week rolls:

| id | Title | Stat | Target | needs |
|---|---|---|---:|---|
| HardWins | Win 3 Maps on Hard | hardWins | 3 | Hard (a Normal win on any map) |
| Nightmare | Win a Map on Nightmare | nightmareWins | 1 | Nightmare (a Hard win on any map) |
| Flawless | Win Without Going Down | flawlessWins | 1 | — |
| BossHunt | Defeat 12 Map Bosses | bosses | 12 | — |
| WinMany | Win 8 Maps | wins | 8 | — |
| Endless | Reach Wave 25 in One Run | wave25Runs | 1 | — |

**Rules.**
- Week number = `(day+3)//7`, with `day` from `MonetizationConfig.day()` (UTC days). Day 0 (1970-01-01) was a Thursday, so each week starts on a Monday.
- The roll is seeded by week and user id, like the daily roll: 2 picks from the normal pool, then 1 from the hard quests the player qualifies for. The list is **saved** when the week rolls (`st.week`, `st.weekList`), so unlocking Hard on Wednesday never changes this week's quests.
- Progress counts from when the week rolls. The daily quests' `quests` stat feeds Weekly "Finish 12 Daily Quests" when a daily quest is claimed.
- A weekly quest waits for CLAIM until the week ends. Unclaimed ones are lost at the reset, like dailies.
- Weekly quests don't affect the daily streak.

## C. Road changes

- **Level 1 pays 50** (was 25). Players who already claimed level 1 keep what they got; there is no top-up.
- Each row shows the next level: "NEXT: 100 + Silver Chest". A finished road shows nothing there.
- **4 new roads** (15 → 19):

| id | Name | Stat | Targets (levels 1 → 10) |
|---|---|---|---|
| Bruiser | Bruiser | meleeKills | 50, 250, 1,000, 5,000, 12,500, 25,000, 50,000, 100,000, 250,000, 500,000 |
| Sharpshooter | Sharpshooter | rangedKills | 50, 250, 1,000, 5,000, 12,500, 25,000, 50,000, 100,000, 250,000, 500,000 |
| ShardHoarder | Shard Hoarder | shards | 300, 1,500, 5,000, 15,000, 40,000, 100,000, 200,000, 400,000, 750,000, 1,500,000 |
| WeeklyWarrior | Weekly Warrior | weeklies | 1, 3, 6, 10, 20, 35, 52, 80, 120, 156 |

Shard Hoarder's targets are guesses, like the Shards daily (plan K); check them against RunAnalytics. Weekly Warrior's 156 is a year of weekly quests.

- **Achiever** now counts feats too. Its total is 18 other roads × 10 + 5 unlocks + 12 feats = **197**. New targets: 3, 10, 25, 40, 60, 85, 110, 140, 170, 197.
- The Achievements total bar becomes "n / 207 complete" (19 roads × 10 + 12 feats + 5 unlocks). QuestsUI already adds this up from the config.

Not in this plan: changing existing road targets (for example, Slayer's 1,000,000 kills). That waits for real kills-per-run numbers.

## New stats (server only, real runs only)

Test runs (admin panel used) and practice count nothing, the same as every quest stat today.

| Stat | Counted when | Where |
|---|---|---|
| hardWins | a win on Hard or Nightmare | `questWin` |
| nightmareWins | a win on Nightmare | `questWin` |
| flawlessWins | a win without going down (rules above) | `questWin` |
| wave25Runs | a living member clears wave 25 (once per stint) | RogueliteMeta wave-clear hook, beside `deepRuns` |
| weeklies | a weekly quest is claimed | `QuestService.claimWeekly` |

Saved beside the stats:
- `st.wonWith = {solo=rank, flawless=rank}`: the hardest difficulty (1 Normal, 2 Hard, 3 Nightmare) won solo / without going down.
- `st.classWins = {Brawler=true, ...}`: classes won with. Derived stat `classesWon` = how many.
- `st.feats = {[id]=true}`: feats claimed.
- `st.week`, `st.weekList`, `st.weekProgress`, `st.weekClaimed`.

## Server flow

**RogueliteMeta (anchored hunks):**
1. `wentDown[p]=m.stint` at the top of the death handler, **before** the phoenix check (so a phoenix save still counts as going down). It's cleared with the player's other tables on leave.
2. `soloBroken[p]=m.stint` at any wave clear where `Shop.memberCount()>1`.
3. At the win clear (`wavesPassed==WinWave`), for each living member: `Profiles.questWin(p,{diff=difficulty(),solo=m.joined==1 and soloBroken[p]~=m.stint and Shop.memberCount()==1,flawless=m.joined==1 and wentDown[p]~=m.stint,class=Characters.states[p] and Characters.states[p].class})`.
4. `if wavesPassed==25 then questEvent(p,'wave25Runs',1) end` beside the `deepRuns` line.
5. ProfileAction `ClaimWeekly` (number 1–3) and `ClaimFeat` (string, ≤40 chars), beside `ClaimUnlock`.

**ProfileService (anchored hunks):** `P.questWin` (skips test runs, like `P.questEvent`), `P.claimWeekly`, `P.claimFeat`, and `weekResetIn` in the view: `((7-(day+3)%7)-1)*86400 + Money.secondsToReset()`.

**QuestService:**
- `S.state` sets up the new fields and rolls the week when `st.week` changes (hard pick filtered by `d.mapWins`).
- `S.event` also adds to this week's quests that count that stat. `claimQuest` feeds `quests` to the weekly quests the same way.
- `S.win(d,day,userId,info)`: counts hardWins/nightmareWins/flawlessWins, raises `wonWith`, adds the class.
- Goal progress (now shared by unlocks and feats) understands `diff`, `solo`, `flawless` and `classes`.
- `S.claimWeekly`, `S.claimFeat` (pays `Q.FeatRewards[stars]`), Achiever counts feats, `S.claimable` and `S.view` include weekly and feats.

## Screens (HTML mockup first, then build)

- **Tabs:** DAILY · WEEKLY · ACHIEVEMENTS, each with its red count badge. `valid()` accepts `Weekly` again.
- **Weekly tab:** "WEEKLY QUESTS" header and "New quests in 3d 04h". 3 tall cards like the daily ones, wider. The hard card gets a HARD tag and a darker ember band.
- **Achievements tab:** road rows get the NEXT line. Then FEATS: the same rows, with 1–3 stars instead of (n/10), sorted ready → in progress → done. Then UNLOCKS, as now.
- **Lobby tracker:** unchanged, but the OPEN QUESTS badge counts weekly and feat claims too.

**Icons.** The user makes them; until each arrives the code uses the fallback.

| Needed | Fallback |
|---|---|
| Feat star | a drawn diamond |
| Weekly tab / Weekly Warrior (calendar with a 7) | calendar (`bestStreak`) |
| Solo (lone wolf) | profile |
| No-down (shield with heart) | heart |
| Nightmare (horned skull or dark moon) | bosses |
| Classes (three masks) | achievements |

## Files

| File | Change |
|---|---|
| `combat/QuestConfig.luau` | Weekly pools, Feats + FeatRewards, 4 roads, level 1 = 50, Achiever targets, new stats and icons |
| `combat/QuestService.luau` | Week roll/progress/claim, `win`, feat goals and claim, Achiever, claimable, view |
| `combat/QuestTests.luau` | Tests below |
| `combat/ProfileService.luau` | `questWin`, `claimWeekly`, `claimFeat`, `weekResetIn` (anchored hunks) |
| `combat/RogueliteMeta.server.luau` | wentDown, soloBroken, questWin at the win, wave25Runs, two ProfileActions (anchored hunks) |
| `ui/QuestsUI.luau` | Weekly tab, FEATS section, NEXT line, counts |
| `ui/AssetPreloader.luau` | Nothing: it already preloads every `QuestConfig` image |

## Checks

- **QuestTests** (fresh copies in Studio Edit): weekly roll is 2 normal + 1 hard and the same all week; Monday is the boundary; the hard pick respects `needs`; a saved list doesn't change after unlocking Hard; weekly progress, claim, double claim and `weeklies`; a claimed daily feeds the Dailies weekly. Feats: each goal kind; Nightmare counts for Hard; retroactive feats from `mapWins`/`bestWaves`; solo/no-down only through `win`; classes; each feat pays its stars once. Achiever counts feats; level 1 pays 50; the new roads claim.
- **Server rules in a real run** (needs Play, so the user runs it or okays a short Play): a death followed by a revive blocks the no-down feat; a party run never counts as solo.
- **Two real clients**: party → not solo. Note it in the test log; never claim it passed without evidence.
- **UI**: built in Edit from fresh repo modules into CoreGui, with `UILayoutAudit.run` at 1920×1080, 1366×768, 2560×1080, 844×390 and 1024×768.
- **Economy**: re-run `economy-sims/chest_pace_sim.py` with weekly income added (+1,200/week + a Gold Chest).
