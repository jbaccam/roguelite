# Play-test analytics and saved stats

**Status:** built 2026-10-02 (`combat/RunAnalytics.luau`) and synced to Studio the same day. Roblox's AnalyticsService only records in the **published** game; in Studio set the Workspace attribute `DebugAnalytics = true` to print each event to the Output instead.

## What gets recorded (Creator Dashboard → Analytics)

| Question | Where to look | Event |
|---|---|---|
| How far do runs get? Where do they stop? | Funnels → **Run** | Started → Wave 5 → 10 → 15 → Won (wave 20). One funnel per run. |
| Which wave do players reach on each map? | Custom → **RunEnd**, split by field 2 (Map) | value = waves cleared (average, max). Roblox doesn't chart progression events yet, so none are sent |
| What kills players? | Custom → **Death** | value = wave; Cause (enemy id such as `crab`, `Boss attack`, `Projectile`), Map, Class |
| How do runs end? | Custom → **RunEnd** | value = waves cleared; Outcome (Victory / Defeat / Left / Disconnected), Map, Class |
| How long are runs? | Custom → **RunMinutes** | value = minutes; Outcome, Map |
| What do players start with? | Custom → **RunStart**, **RunStarter** | value = Gear Power; Map, Class, starting weapon, party size |
| Do they play again? | Custom → **RunStart**, field 3 | `First run`, `Again <10m` (started within 10 minutes of their last run ending, across servers), or `Later` |
| Revives | Custom → **RevivePrompt**, **Revived** | the revive number |
| Emeralds from runs | Economy → source **Gameplay**, item `RunWaves` | the emeralds each wave clear / run end paid |
| Which weapons do the work? | Custom → **WeaponDamage**, split by field 1 (Weapon) | value = damage that weapon dealt in one run; field 2 = its share of the run's damage (`<10%` … `75%+`), field 3 = Map. Armor perks and pets show as `Armor` and `Pet` |
| How much damage is a run? | Custom → **RunDamage** | value = the run's total damage; Outcome, Map, Class. For the plan K Damage daily and Heavy Hitter targets |
| What do players buy? | Custom → **ShopBuy** | value = shards paid; `Weapon - Katana` or `Item - Lucky Sock`, Tier (I–IV), wave band (`1-5` … `21+`) |
| Do they reroll? | Custom → **ShopReroll** | value = shards paid; Shop or Level-up, how it was paid (`Shards`, `Free` = a saved reroll, `Bought` = Robux or a stored one), wave band |
| Which level-ups do they take? | Custom → **LevelPick** | Stat (e.g. `Stat - Max HP`), Class, wave band |
| Does the game run well? | Custom → **FrameRate**, **FrameDips** | one per player per wave: value = average FPS over the wave (FrameDips: seconds under 30 FPS, sent only when there were any); Device (`Phone`, `Tablet`, `Desktop`, `Console`), the most enemies alive in that wave (`0-24` … `100+`), Map |

Admin test runs (the admin panel was used) are not recorded as play-test data.

**Not tracked yet** (from EXECUTION_PLAN_ASTRA.md "Prototype analytics"): the tutorial (there is no tutorial yet). Damage by weapon, passive picks (level-ups and shop items), shop rerolls and purchases, enemy count and frame rate were added on 2026-10-02 (plan J item 7).

**How events are sent (2026-10-02):** every event is queued and sent once a second from RunAnalytics' own thread (a leaving player's right away). Hooks such as `ShopService.onBuy` and `CombatEffectsService.listenDamage` run inside sandboxed scripts, and Roblox runs a directly called function with the caller's capabilities ([script capabilities](https://create.roblox.com/docs/scripting/capabilities)), so they only record. This also covers the wave funnel steps, which came from ShopService's wave clock. Frame rate comes from `RogueliteHUD.client` over the `PerfReport` remote (whole numbers, a known device, one report per 10 s, players in a run only).

## Saved stats that unlock content (already in place, checked 2026-10-02)

- **Best wave per map and difficulty** (`ProfileService.recordProgress`, `bestWaves[runKey]`): saved at every wave clear, Endless waves included, for every run member (downed players too). The map select's wave track and BEST WAVE read it; the results screen shows it with NEW BEST.
- **Wins** (`mapWins[runKey]`): saved when wave 20 clears (Pine Valley's can't clear while the Hammer lives). A Normal win opens Hard, a Hard win opens Nightmare and the next map (`RunSetupRules.difficultyUnlocked` / `mapUnlocked`). The first win per map and difficulty pays its bonus once (FIRST WIN on results).
- **Run emeralds**: paid as each 5-wave milestone clears, so leaving, dying, closing the game or a server shutdown never loses them.
- **Leaderboards** (`LeaderboardService`): lifetime kills, highest wave reached (any map) and time played, in their own DataStore.
- **Quests** (another session's `QuestService`, in progress): lifetime kills, waves, wins, runs and bosses.
- Admin test runs save none of these. Studio never saves (DataStores off), so only the published game proves saving; see LOBBY_AND_MATCH_SERVERS.md §7.
