# Play-test analytics and saved stats

**Status:** built in the repo 2026-10-02 (`combat/RunAnalytics.luau`), not yet synced to Studio. Roblox's AnalyticsService only records in the **published** game; in Studio set the Workspace attribute `DebugAnalytics = true` to print each event to the Output instead.

## What gets recorded (Creator Dashboard → Analytics)

| Question | Where to look | Event |
|---|---|---|
| How far do runs get? Where do they stop? | Funnels → **Run** | Started → Wave 5 → 10 → 15 → Won (wave 20). One funnel per run. |
| Which wave do players reach on each map? | Progression → path `PineValley/Normal` etc. | A "level complete" per wave cleared, a "fail" on the wave of a death |
| What kills players? | Custom → **Death** | value = wave; Cause (enemy id such as `crab`, `Boss attack`, `Projectile`), Map, Class |
| How do runs end? | Custom → **RunEnd** | value = waves cleared; Outcome (Victory / Defeat / Left / Disconnected), Map, Class |
| How long are runs? | Custom → **RunMinutes** | value = minutes; Outcome, Map |
| What do players start with? | Custom → **RunStart**, **RunStarter** | value = Gear Power; Map, Class, starting weapon, party size |
| Do they play again? | Custom → **RunStart**, field 3 | `First run`, `Again <10m` (started within 10 minutes of their last run ending, across servers), or `Later` |
| Revives | Custom → **RevivePrompt**, **Revived** | the revive number |
| Emeralds from runs | Economy → source **Gameplay**, item `RunWaves` | the emeralds each wave clear / run end paid |

Admin test runs (the admin panel was used) are not recorded as play-test data.

**Not tracked yet** (from EXECUTION_PLAN_ASTRA.md "Prototype analytics"): damage by weapon, passive picks, shop rerolls and purchases, enemy count and frame rate, and the tutorial (there is no tutorial yet).

## Saved stats that unlock content (already in place, checked 2026-10-02)

- **Best wave per map and difficulty** (`ProfileService.recordProgress`, `bestWaves[runKey]`): saved at every wave clear, Endless waves included, for every run member (downed players too). The map select's wave track and BEST WAVE read it; the results screen shows it with NEW BEST.
- **Wins** (`mapWins[runKey]`): saved when wave 20 clears (Pine Valley's can't clear while the Hammer lives). A Normal win opens Hard, a Hard win opens Nightmare and the next map (`RunSetupRules.difficultyUnlocked` / `mapUnlocked`). The first win per map and difficulty pays its bonus once (FIRST WIN on results).
- **Run emeralds**: paid as each 5-wave milestone clears, so leaving, dying, closing the game or a server shutdown never loses them.
- **Leaderboards** (`LeaderboardService`): lifetime kills, highest wave reached (any map) and time played, in their own DataStore.
- **Quests** (another session's `QuestService`, in progress): lifetime kills, waves, wins, runs and bosses.
- Admin test runs save none of these. Studio never saves (DataStores off), so only the published game proves saving; see LOBBY_AND_MATCH_SERVERS.md §7.
