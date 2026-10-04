# Crystal shard shop currency — September 22, 2026

Confirmed user decision: the blue crystal shard replaces gold coins as the run's shop currency. The supplied crystal image guides the model. Astra authored the asset in `crystal-shard/` using the approved chunky, softly faceted, painterly low-poly style. The later user-approved presentation adds a restrained cyan glow and light-blue aura to make pickups inviting and visible; this supersedes the original no-aura direction for in-game drops.

Every real mob death during combat creates a blue crystal pickup at the death location. The initial implementation retains the existing economy values: one crystal pickup is worth **2 shards and 2 run XP**, the starting balance is **60 shards**, and survivors receive **12 + completed wave × 3 shards** at wave end. Shop prices, rerolls and sell refunds all use shards. These remain prototype tuning values.

Run XP is awarded only on confirmed magnetic pickup, at 1 XP per shard value. Start at level 1, 0/20 XP; each following level costs 10 more XP (30, 40, etc.). Overflow carries through multiple levels. Level is bounded at 1,000. Spending, debug currency edits, starting shards and wave-clear currency do not change XP. Uncollected drops left at wave end go into the crystal bag and pay out later (see 2026-10-03 below). XP and level are temporary server-owned session state, not account progression; they reset with a new session. Earned levels increment PendingLevelUps for the planned upgrade-choice system; this HUD implementation does not grant stat upgrades or implement choice resolution.

The HUD uses the user's supplied blue shard icon and green potion XP-bar artwork. Image cropping/masking preserves the original frame, potion and faceted fill while replacing baked sample numbers with live XP and level labels. The fill animates to the replicated XP ratio. The shard counter in the shop uses the same supplied icon. See `studio-prototype/combat/RUN_XP.md` for tests and tuning.

The server creates and owns drops, validates living collectors, ownership, PickupRadius and line of sight, and credits each pickup once. Combat kills reserve their drop for the credited player; deaths without an attacker create a public pickup collectable once by the first eligible player. There is no pickup remote and no client-supplied amount. Wave resets and removal of living enemies do not create rewards. Duplicate death callbacks cannot duplicate a drop.

Crystals gently bob ±0.16 studs and turn slowly while resting. Each remains visible for at least 0.3 seconds before the player's PickupRadius can trigger a magnetic pull. The shard accelerates toward the player's current position over 0.42 seconds and is credited only on arrival. The server reserves the collector and checks life, ownership and a clear path throughout the pull; blocked or invalid pulls cancel without credit. Rendering runs smoothly on the client and never awards currency.

Every mob death has its own lightweight server marker; drops are no longer merged at the former 128-drop limit. Each client renders the nearest 128 crystal models, prioritizing active pulls, while all other pickup records remain intact and become visible as the player approaches. Uncollected owned drops are banked for living owners when a wave completes; stopping a Studio test discards outstanding drops. Public uncollected drops clear at wave end. Drops from departed players are removed.

Pickup appeal: pale cyan facets use Neon while deep-blue facets retain their readable shading. A small shadowless cyan light and soft, low-opacity light-blue particle aura follow the bobbing crystal and its magnetic pull. The aura uses Roblox's bundled `smoke_main.dds`, 5 particles/second, and 0.8–1.2-second lifetimes. Clients enable at most 32 nearby auras within 70 studs and 12 lights within 45 studs. All effects belong to the local crystal model and disappear with it on collection. The original mesh exports remain clean geometry; no global lighting or bloom settings are changed.

The random glowing green health-orb drop has been removed completely, including its producer, pickup loop and combat hook. Mobs drop crystals reliably, independent of Luck. PickupRadius and Fridge Magnet now describe crystal attraction; Lucky Sock explicitly describes Luck as reserved for future loot instead of promising removed health drops.

**2026-09-28:** a new, rarer heart pickup replaces that idea (see `heart-pickup/README.md`): 2.5% per real kill plus 0.05% per killer Luck point (capped at 8%), at most 6 on the field, heals 15 HP before Recovery, pulled only by hurt living players inside their PickupRadius (minimum 4 studs), cleared when the wave ends. Bosses, practice targets and slime split children never roll. A defeated hammer boss now showers 50 public crystals worth 4 shards each (200 total) in a 3–14 stud disc; practice bosses still drop nothing.

Shards are temporary session/run money, never persistent account currency or Robux. Studio tests never award persistent currency or wins, and DataStores remain disabled. Older references to persistent account Coins in progression proposals describe a separate lobby economy; they do not authorize coin drops or gold purchases in the run shop.

The mesh exports and Roblox geometry builder share the same shard silhouette and blue/cyan palette. The builder enables immediate runtime use without requiring a new uploaded mesh ID. See the asset README for the distinction between the textured mesh and native runtime geometry.

Verification results are recorded in `studio-prototype/combat/SHARD_TEST_RESULTS.md`. Multiplayer contention with multiple real clients and published-server performance require separate testing.

**2026-09-29 (user playtest: crystals and hearts too easy):**
- A kill crystal is now worth **1 shard and 1 XP** (`EconomyConfig.KILL_SHARDS`). The designer-shirt bonus (+2) and the boss shower (50 × 4) are unchanged.
- Hearts: **1% per kill** plus Luck × 0.02% (cap 3%), at most **3** on the field. **Any** living player in range pulls one, even at full health (it's wasted), and an unclaimed heart **expires after 10 s**, blinking for its last 3 s. Heal stays 15.
- Wave population is now `min(100, 8 + (wave - 1) * 3)`: 8 at wave 1, 35 at wave 10, 65 at wave 20 (was 5 / 23 / 43). Since 2026-10-03 this is only the base; the wave scales it up (below).

**2026-10-03 (play-test round; repo only, syntax-checked, not yet in Studio, not play-tested):**
- **The crystal bag works like Brotato's.** Crystals still on the ground when a wave ends go into their owner's bag at full value. Public ones go to the nearest living player's bag. Next wave, each pickup pays double out of the bag until it's empty. Example: bag 30, you pick up a 5-crystal: +10 shards and 10 XP, bag 25.
  - The bug: `ShardDropService.sweep` picked up every ground crystal at wave end before `clear(true)` could bag it, so the bag always stayed at 0. Now `sweep` only finishes crystals already flying to a player; ground ones are left for `clear(true)`.
  - The tutorial keeps the old fly-in of every crystal (`ShopService` calls `sweep(true)` in tutorial runs). It starts at 0 crystals, and its guided Glock buy needs them.
  - The shop shows a bag icon and amount beside the crystal count, hidden at 0.
- **Ground cap:** at most 50 crystals lie on the ground (`ShardDropService.MAX_GROUND`). Past that, a new kill's value joins the nearest ground crystal with the same owner, so nothing is lost: 60 kills leave 50 crystals worth 60. A public crystal never merges into an owned one.
- **Colours per player.** Each player gets a `CrystalSlot` (the lowest free number, kept until they leave). In runs with 2+ players, a crystal wears its owner's colour: blue, orange, pink, yellow, then round again. Public crystals are white. Solo stays all blue. A diamond in each teammate's colour floats over their name, and yours sits on your shard icon. Only the killer can take a kill's crystal (unchanged).
- **Bigger waves that scale with players** (`EnemyScheduler.population`): `min(100, base × 1.2 × player factor)`, with base `8 + 3 × (wave − 1)` and factor 1 / 1.6 / 2.1 / 2.5 for 1–4 run members who are alive and not downed (checked every second).

  | Wave | 1 | 5 | 10 | 20 |
  | --- | ---: | ---: | ---: | ---: |
  | Solo | 10 | 24 | 42 | 78 |
  | 4 players | 24 | 60 | 100 | 100 |

  The alive cap is still 100. Performance work so far targeted 65 mobs and 100 hasn't been measured: run `tools/MobPerfProbe.luau` at 100 before 4-player groups. Swarm rules: `studio-prototype/combat/REGULAR_ENEMY_READINESS.md`.
- **Waves last 40 s** (`EconomyConfig.WAVE_SECONDS`, was 30; the tutorial keeps its own clock). Enemies refill as they die, so a wave has about a third more kills and crystals. The per-wave shard reward is unchanged.
