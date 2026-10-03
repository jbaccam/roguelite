# First-join tutorial — design

**Status:** Approved design, 2026-10-03. Not built yet.
**Replaces:** the "Recommended tutorial — proposed" section of [LOBBY_AND_FIRST_RUN.md](../LOBBY_AND_FIRST_RUN.md).
**Inspiration:** a reference game's tutorial (20 screenshots the user shared on 2026-10-03). We copy its pacing and guidance style, but use our game's systems.

## Goal

A brand-new player spawns straight into Pine Valley. In about 3 minutes they learn moving, auto-attacks, crystals, levelling, the between-wave shop and a boss. Then a short guided lobby visit teaches chests, upgrading, equipping and Play. After that the player is free.

## Guide style (whole tutorial)

- **The Egg Merchant is the guide.** His portrait sits bottom-left with a dark text box beside it, like the reference. Each line stays on screen until the player does the action, or until it times out for lines with no action.
- **One gliding arrow.** It never disappears and jumps. It eases along a curve from one target to the next, turns to face the new target, and bobs gently while resting. The player's eye should be able to follow it.
- **No paid prompts during the run part.** That means no revive offer and no store.

## Part 1 — the run

The player uses their Roblox avatar, the **Brawler** class, and the **Frying Pan** as the only weapon. The map is Pine Valley.

Tutorial economy:
- The player **starts with 0 crystals**, not 60, so it's clear the money comes from crystals.
- **Each crystal is worth 5** (XP and shards), instead of 1.
- The normal wave bonus still applies (12 + 3 per wave).
- **Health can't go below 1** for the whole run. Hits still show and the bar still drops, but the player can't die. That means no retry or checkpoint logic is needed.

| Beat | What happens | Egg Merchant |
|---|---|---|
| Spawn | First join → loading screen → Pine Valley, with the pan floating beside you | "Welcome to Wavebreaker!" |
| Wave 1 | 6 slow Regular Zombies. The wave ends when all 6 are dead, not on a timer | "Your pan swings by itself. Just move!" then, on the first drop: "Grab the crystals: they're XP *and* money." |
| Break 1 | Leftover crystals fly to you. 30 XP → **Level 2**. The level-up card screen shows 1 card, with the arrow gliding to the cards (any pick is fine). The shop opens with **no timer**. **Offer slot 1 is always a Glock Tier I** (~21 crystals; the player has ~42). The arrow glides to the Glock, then to Ready | "After every wave you can shop. Crystals pay for it." |
| Wave 2 | ~15 zombies, a few of them Baby Zombies. Ends when all are dead | "Survive wave 3 and beat the boss!" |
| Break 2 | 75 XP → **Level 4**, so 2 cards. About 95 crystals. The player shops on their own; the arrow rests on Ready | "Your turn. Buy what you like." |
| Wave 3 | The **boss intro** (below), then the weakened Hammer Zombie Boss plus a few zombies | On his first attack telegraph: "Red circle = move!" |
| Boss dies | Burst. All 50 boss crystals fly straight to the player (rule below). The level bar climbs several levels during the victory | "You beat the boss!" |
| Victory | PINE VALLEY — VICTORY banner, then the results screen. The wave track, reward tiles and level bar fill in step by step. Rewards: **3 Silver Chests + 100 emeralds**. The arrow glides to LOBBY | "Let's go spend that loot." |

### Tutorial boss

- **Same kit as the normal boss, no fixed schedule.** He keeps his normal Slam / Swing / Slam / Spin cycle and his Charge when you kite him. He attacks about every 3 s (`hammer-boss/BossMotion.luau:62-64`), so a 15–30 s fight shows all three moves on its own.
- **650 HP**, a fixed number with no difficulty, party or map scaling. That's about 3.6% of the normal 18,000.

Estimated damage per second at the boss (Brawler: +20% melee, −15% ranged). The pan is assumed to hit about half the time and the Glock about 90% of the time:

| Player | Build | DPS | Time to kill |
|---|---|---|---|
| Weak | Pan I + Glock I, no damage stats | ~22 | ~30 s |
| Typical | Pan I + Glock II + Protein Shake + 1 damage card | ~35 | ~19 s |
| Strong | Pan II + Glock, stands and tanks | ~45 | ~14 s |

These are estimates. After play-tests, check the real boss time with the damage-by-weapon analytics (`PLAYTEST_ANALYTICS.md`) and adjust the one HP number. The class-weapon-fit change (commit c2f348e) may shift the Brawler's Glock damage, so recheck after it lands.

### Boss intro (also used for the normal wave-20 boss)

1. Short rumble and camera shake. A dark shadow grows on the ground in the arena centre.
2. The Hammer Boss drops from the sky as if he super-jumped in and **slams down hammer-first**. Shockwave ring, dust and debris (flat VFX: Neon crescents, painted textures and ground decals, no shaded meshes), and heavy camera shake.
3. A ~3 s camera orbit around him as he straightens up, with a name card: **HAMMER ZOMBIE BOSS**.
4. The camera returns to the player and the boss bar appears. He can't be hurt and doesn't attack until the camera is back.

### Boss crystals fly to players (all runs, not just the tutorial)

The boss's crystals don't land on the ground. They fly straight to players.
- **Solo:** all of them go to the player.
- **Multiplayer:** they split evenly among living players, and any remainder goes round-robin. For example, 50 crystals across 3 players gives 17 / 17 / 16.

### Wave-end crystals fly in (all runs)

When a wave ends, leftover crystals on the ground visibly fly to the nearest living player and count as normal pickups (XP + shards). Today they are silently bagged by `Shards.clear(true)`. This matches what `CURRENT_GAME_STRUCTURE.md` §3 already promises: "drops pull in".

## Part 2 — the lobby

The reward is saved **the moment the boss dies**: 3 Silver Chests + 100 emeralds, granted once per account. The tutorial's **first** Silver Chest always contains **2 Frying Pan copies and 1 armor piece**. The other 2 are normal random rolls.

While a guided step is running, the other bottom buttons are dimmed and can't be clicked.

| Step | Player does | Egg Merchant |
|---|---|---|
| 1. Arrive | Spawn in the lobby plaza. The arrow glides to **Chests** | "Welcome to the lobby! Let's open what you earned." |
| 2. Chests | Silver Chest ×3 is already picked. Arrow on **Open**, then the usual 3-tap open (the seeded chest). Arrow on **Open (2)** for the rest | "Chests give you weapons and armor. Copies make them stronger!" |
| 3. Armory | Arrow → Exit → **Armory** → the Frying Pan card (upgrade-ready badge) → **Upgrade**. Tier I → II costs 2 copies + 60 emeralds, leaving 40 | "Your pan now starts every run stronger." |
| 4. Equip | Arrow glides to the new armor piece → **Equip** | "Armor stays on you every run." |
| 5. Offer | Exit → the **Starter Pack** pops up once, with **No Thanks** | — |
| 6. Free | Arrow on **PLAY** for 10 s or until clicked, then it fades. Tutorial complete | "Now go break some waves!" |

The Starter Pack keeps its approved contents from `MONETIZATION_AND_REWARDS.md`, with **no chests**, unlike the reference. Selling random rewards is not allowed.

## Rules

- **When it starts:** on first join (no `tutorial.done` in the profile), the player goes straight into a solo tutorial run. They never see the lobby first. This applies even when joining a friend; it only takes 3 minutes.
- **Leaving during the run:** next join restarts the tutorial run. No reward has been given yet.
- **Leaving during the lobby part:** next join spawns in the lobby and the guide resumes at the saved step.
- **Paying out once:** rewards are paid only once. There's no replay of the run part for now; "Replay tutorial" from Help is a later idea.
- **Studio:** Studio practice grants no saved rewards, and production DataStores stay off.

## Build pieces

Server (new modules must be **Sandboxed** with copied Capabilities, and must not `WaitForChild('RogueliteRunState')` at load, or the server deadlocks):

1. **Profile:** a `tutorial = {step, done}` field in `ProfileService`. The one-time reward grant, plus the seeded first Silver Chest.
2. **Routing:** a first join with `done ~= true` reserves a match server with `tutorial=true` and teleports there (`MatchService.launch`). In Studio Combined mode it goes straight to the arena.
3. **`TutorialDirector`**, server-side, active only when the match has `tutorial=true`. It drives the run through new, small `ShopService` hooks:
   - per-wave enemy count and roster
   - the wave ends on all-dead instead of the timer
   - no shop timer
   - a forced offer in slot 1
   - starting shards and crystal value
   - boss on wave 3 with a fixed HP
   - the health floor (`Health.server.luau`)
   - publishing `TutorialStep` for the client
4. **Crystals:** the wave-end fly-in, and the boss crystals flying to and splitting between players (`ShardDropService`, all runs).
5. **Boss intro:** the server spawns the boss off-sky with a short invulnerable window; the client handles the drop, slam and camera orbit (all runs).

Client:

6. **`TutorialGuide`:** the Egg Merchant text box and the gliding arrow. It reads `TutorialStep` and points at named GUI targets in the run HUD, shop, cards, results and lobby windows.
7. **Lobby hooks:** a real (not Studio-only) way for the guide to open a `LobbyUI` window and find a button (today `mount` returns `self.Open`, but the HUD throws it away), plus the button dimming.
8. **Results screen:** the step-by-step fill and the tutorial reward tiles.

## Build order

1. An HTML mockup of the Egg Merchant text box and the gliding arrow, served from `roguelite-planning/previews/` and opened through the dev server.
2. Wave-end and boss crystal fly-in (useful in every run on its own).
3. Boss super-jump intro (also useful on its own).
4. `TutorialDirector` + the `ShopService` hooks + the health floor.
5. `TutorialGuide` for the run part.
6. Profile field, reward, seeded chest and first-join routing.
7. The lobby guide steps.

Each step lands with whatever uses it, so Studio never breaks between tasks. Each Studio write still needs its own okay.

## Testing

- **Pure-maths tests** in the existing `*Tests.luau` style:
  - tutorial shards at each shop (~42 and ~95)
  - levels reached (2 after wave 1, 4 after wave 2)
  - the boss-crystal split (50 → 17/17/16)
  - the seeded chest contents
  - the reward paid only once
- **Play-testing:** the user does the play-testing. Edit-mode setup is handed over with notes on what to check: boss kill time, whether the arrow is smooth, and that nobody can die.
