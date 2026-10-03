# Launch audit — 2026-10-02

A read-only audit of the roguelite before launch. It covers purchases, saving, cheating, server and phone performance, gameplay rules, UI and controls, and place cleanup. Five parallel code reviews and a Studio scan fed it, and the top findings in each area were re-checked against the code. Line numbers are from about noon on 2026-10-02. Other sessions were editing `RogueliteMeta.server.luau` and `ProfileService.luau` at the time, so re-check those before fixing.

**Totals:** 7 must fix before launch, 14 high, 27 medium, 29 low, 4 cleanup (81 findings).

Paths are relative to `roguelite-planning/studio-prototype/` unless they start with `../` or name a doc.

## Decisions needed from you

- ~~**Admin 109021050:**~~ leavked, the user's friend and map builder; kept. (C3)
- **Lucky Cat Luck:** Luck raises run shop odds and comes from emerald-bought eggs. Allow it in writing, or keep Luck pets out of paid eggs? (M12)
- ~~**Run shop weapons:**~~ owned only; new weapons from chests and the daily shop. (G6)
- ~~**Elite and horde waves:**~~ markers removed. (G5)
- **Mid-run Robux rerolls:** The root AGENTS.md says the revive is the only thing bought mid-run, but rerolls and banishes are sold mid-run (your 2026-09-27 decision). Update the rule so future work follows it.

## Must fix before launch

### M1 · Nothing can be bought: every product and pass ID is 0
*Purchases & store*

All 31 developer products and both game passes still have ID 0. On a live server every buy button, including REVIVE R$ 65, shows a price, then answers "Not on sale yet".

**Fix:** Create the products and passes in the Creator Dashboard and paste in the IDs. Add a startup warning for any ID that is 0 or used twice. Until then, hide price buttons on live servers.

**Where:** `combat/MonetizationConfig.luau:12-70`, `combat/RogueliteMeta.server.luau:510-532`

### M2 · Quick Open (149 R$) and VIP "open ×10" sell something everyone already has — **fixed 2026-10-02**
*Purchases & store*

The chest screen lets every player open ×10 or ×100, and the server only checks that the amount is 1, 10 or 100. A free player gets the paid perk, and paying players get nothing for 149 R$. That is a refund and moderation risk.

**Fix:** Either check d.quickOpen or d.vip for ×10/×100 on the server and in the amount button, or remove the Quick Open card and the ×10 wording on VIP.

**Where:** `ui/ChestScreenUI.luau:371-373`, `combat/ProfileService.luau:295-299`, `ui/StoreUI.luau:141,231-236`

### M3 · Starter Pack and VIP daily chest skip the paid-random-items region check — **fixed 2026-10-02**
*Purchases & store*

The Starter Pack holds 2 Legendary Chests but isn't marked random, and the VIP daily chest never checks the region flag. A player in a region that bans paid random items can buy the pack for 49 R$ and open the chests.

**Fix:** Mark StarterPack random=true and hide it for restricted players (or sell them an emerald-only version). In claimVipChest, give restricted players emeralds instead of a chest.

**Where:** `combat/MonetizationConfig.luau:41`, `combat/ProfileService.luau:551-557`, `combat/RogueliteMeta.server.luau:431`

### M4 · Receipts skip the purchase rules, so cheaters can pay less or re-buy one-time packs — **fixed 2026-10-02**
*Purchases & store*

The rules (revive price step, one-time Starter Pack, class already owned, region) are only checked before the prompt. A cheater can prompt a product ID directly. For example: buy Revive1 at 65 R$ every time instead of 130→1040, or buy the 49 R$ Starter Pack (1500 emeralds + 2 Legendary Chests) over and over. This goes live the moment the IDs are filled in.

**Fix:** Re-check the rules inside processReceipt. Give a fair emerald fallback when an item can't be granted. Track the revive Robux paid per run, so a cheaper step can't stand in for a dearer one.

**Where:** `combat/RogueliteMeta.server.luau:427-500`

### S1 · Spamming one purchase request forces a save every half-second — **fixed 2026-10-02**
*Saving data*

Picking a Godly Starter saves the profile on every PurchaseRequest, limited only to once per 0.5 s. One cheater looping it uses about 120 DataStore writes a minute. That drains the server's budget, so other players' saves, receipts and joins start failing.

**Fix:** Don't save in this handler. Keep the pick in memory and save it with the receipt or the 120 s autosave.

**Where:** `combat/RogueliteMeta.server.luau:504,524`, `combat/ProfileService.luau:140-155`

### G1 · No shop timer: one idle player freezes the whole party — **fixed 2026-10-02**
*Gameplay bugs*

The next wave only starts when every living player presses GO and has picked all level-ups. One AFK player in a 4-player party holds everyone in the shop until Roblox kicks them about 20 minutes later. The design doc promises a timer and a safe default pick.

**Fix:** Add a shop deadline (30-45 s). When it runs out, auto-ready everyone and auto-pick any pending level-ups.

**Where:** `combat/ShopService.luau:328-334,618`, `PROGRESSION_AND_SESSION_FLOW.md:237-239`

### L1 · Studio is behind the repo: sync before you publish — **fixed 2026-10-02**
*Place & project cleanup*

Studio doesn't have today's work yet. That's the revive price ladder, analytics, Plan K quests, King Crab boss changes and MapBoss modules. Studio is also ahead in one file: AssetPreloader preloads armor/pet icons and rbxthumb images, which the repo doesn't have. The Phoenix armor icon IDs differ between the two.

**Fix:** Pull Studio's AssetPreloader change into the repo, sync the repo into Studio, and confirm the Phoenix icons. Then publish from Studio.

**Where:** `Studio vs repo diff, 2026-10-02 12:00`, `ui/AssetPreloader.luau`, `combat/ArmorCatalog.luau:39-42`

## High

### M5 · A revive bought too late turns 1040 R$ into 50 emeralds — **fixed 2026-10-02**
*Purchases & store*

If the wave ends while the revive dialog is open, teammates auto-raise the player, and the receipt then pays a flat 50 emeralds (about 5 R$). With a 30 s wave this overlap happens in normal party play. A revive can also be marked delivered when the run ended during the respawn.

**Fix:** Refund about the price paid (robux × 10 emeralds) or keep a revive credit. Have revive() return false if the respawn aborts. Hide REVIVE in the last seconds of a wave when teammates are alive.

**Where:** `combat/RogueliteMeta.server.luau:149,290-298,452-455`

### M6 · Game pass perks can silently fail to apply — **fixed 2026-10-02**
*Purchases & store*

The pass check runs at join, before the profile has loaded, and the grant is thrown away if the profile isn't ready. It's never retried or saved right away. A player who bought VIP on the website can join and not get VIP.

**Fix:** Wait for ProfileLoaded before checking passes, retry a few times, and save after granting. Don't prompt a pass while the profile is missing.

**Where:** `combat/RogueliteMeta.server.luau:507-551,596`

### S2 · If a save fails to load, the player is never told — **fixed 2026-10-02**
*Saving data*

**Done:** store errors are retried for about a minute (2, 4, 6, then 8 s apart). After 2 s of loading the player sees "Loading your save..." (ui/SaveStatus.client.luau); if it still fails, "Couldn't load your save" and, 4 s later, a kick asking them to rejoin. Nothing is ever written over the save. Match servers wait 75 s for the save before a default loadout.

After 3 failed tries (about 3 s) the profile gives up for the whole session. In the lobby every action says "Profile still loading", the party can't launch, and on a match server the player plays 20 waves and earns nothing. Nothing is overwritten, which is good.

**Fix:** Retry with backoff for 30-60 s and show "Couldn't load your save, retrying". If it still fails, kick with a clear message. Make launch name the player whose save isn't loaded.

**Where:** `combat/ProfileLock.luau:8,34-37`, `combat/ProfileService.luau:104-106`, `lobby/MatchService.luau:66,113`

### C1 · No movement checks in the arena, so fly cheaters farm rewards — **fixed 2026-10-02**
*Cheating & admin*

**Done:** `combat/MovementGuard.server.luau` + `MovementCheck.luau` sample each run member 10×/s and snap blatant speed (over 1.5× their own speed + 16 studs a second, 0.4 s in a row), teleports (120+ studs at once), hovering (16+ studs up, not falling, 2.5 s) and leaving the arena walls (1 s) back to the last safe spot. Rewards follow contribution (`Contribution.luau`, the user's formula): each wave's emeralds are base × (0.5 + 0.5 × contributors × share), capped at 2×, 0 for no damage and no kills; 5-wave blocks pay their base × the average multiplier of the waves played. Quest waves/runs/wins and the Highest Wave leaderboard need damage or a kill in that wave.

Waves end on a 30 s timer and pay everyone alive. Nothing checks speed, height or map bounds. A fly or noclip cheater hovers above melee mobs, survives, and collects emeralds, quests, Endless rewards and a Highest Wave leaderboard spot.

**Fix:** Add a server check per player for speed and arena bounds that snaps cheaters back. Only pay a wave to players who dealt damage in it; damage per player is already tallied.

**Where:** `combat/ShopService.luau:362,621`, `combat/RogueliteMeta.server.luau:123-138`, `combat/LeaderboardService.server.luau:112`

### G2 · The Pine Valley boss doesn't count for boss quests or the streak — **fixed 2026-10-02**
*Gameplay bugs*

Boss quests check IsMapBoss, but the Hammer boss only sets IsBoss/IsHammerBoss. A new player who rolls "Defeat a Map Boss" and beats the Hammer boss can't finish it, so they lose their daily streak and Boss Hunter progress.

**Fix:** Count IsHammerBoss too. Consider not rolling the boss daily until the player can reach a boss.

**Where:** `combat/RogueliteMeta.server.luau:159`, `../hammer-boss/BossService.luau:183`

### P1 · Every bullet sends network data every frame — **fixed 2026-10-02**
*Server performance*

**Done:** a bullet sends one Fly row per straight leg and a Land/Drop row where it stops; `BulletFlights` replays the steps on the client into the unchanged visuals.

Each in-flight bullet adds a 17-value row to the Shot remote every Heartbeat. Estimated: a Draco is about 135 rows/s, 15-28 KB/s per client. Four gun builds could reach 50-200 KB/s per client, against a usual budget of about 50.

**Fix:** Send one launch message and one hit/end message per bullet, as rockets and arcs already do. The client already fills in the flight.

**Where:** `combat/StatProjectiles.luau:21-40`, `combat/RogueliteCombat.server.luau:196-201`

### P2 · One remote call per hit, never batched — **fixed 2026-10-02**
*Server performance*

**Done:** non-lethal hits go once a frame per player on the HitFX UnreliableRemoteEvent (packed, under ~760 bytes a message); kills stay reliable and immediate on Hit; damage-over-time ticks show a number but no splat or flash.

Every hit, burn tick, zone tick and chain hit is its own FireAllClients. Late game with 4 players this is an estimated 300-800 calls/s.

**Fix:** Batch Hit like Shot (one array per frame). Use an UnreliableRemoteEvent for cosmetic impacts, and skip impact effects for damage-over-time ticks.

**Where:** `combat/CombatEffectsService.luau:69,81,161`, `combat/UtilityWeapons.luau:42-47`, `combat/SpecialWeapons.luau:121-134`

### P3 · Weapon aim is replicated 30 times a second per weapon — **fixed 2026-10-02**
*Server performance*

**Done:** one packed Attack attribute per attack instead of 12; AimPosition only after a 1.5-stud move (10 Hz max) or a slow drift, never for melee; the client glides between writes.

AimPosition is rewritten almost every tick for every armed slot, and each attack writes 12 more attributes. All of it replicates to every client. Estimated 30-40 KB/s per client.

**Fix:** Only update AimPosition when it moves more than about 1.5 studs, or at 10 Hz. Pack the attack fields into one attribute or one event.

**Where:** `combat/RogueliteCombat.server.luau:292,319-330`

### P4 · Targeting scans every enemy for every weapon, 30 times a second — **fixed 2026-10-02**
*Server performance*

**Done:** one shared enemy snapshot and grid per tick (`TargetGrid.luau`), nearest first with the first clear line; cooling weapons re-search at 10 Hz. Tests: the same pick as the old scan in 2,400 random crowds, 60% fewer line checks.

Each tick, every player rebuilds enemy lists, and every weapon slot (even on cooldown) checks every enemy, raycasting candidates. Estimated with 65 enemies and 24 slots: about 60k API calls and 3k-20k raycasts per second. Likely the biggest Lua cost.

**Fix:** Keep one shared enemy list and use the existing spatial grid. Sort by distance and stop at the first clear shot. Retarget at 10-15 Hz while a weapon is cooling down.

**Where:** `combat/RogueliteCombat.server.luau:227-301`

### P5 · 65-100+ full Humanoid enemies simulated on the server
*Server performance*

**Progress 2026-10-02 (repo only, commit 7cdf115; not in Studio, not measured):** one Heartbeat steps every enemy (EnemyScheduler) instead of one connection each; attacks in progress still update every frame. Think clocks keep their phase (0.1 s on average) and new enemies take the least busy frame: in EnemySchedulerTests the old clocks drifted until all 60 enemies thought on one frame. Enemies more than 90 studs from every player with a clear line think every 0.3 s. Eight unused Humanoid states are off (Running, Jumping, Freefall, Landed stay) and enemy parts have CanTouch off. Before/after numbers wait for a measurement session (tools/MobPerfProbe.luau, tools/MobMotionProbe.luau).

Wave 20 has 65 enemies; Endless reaches 100 at wave 32, plus slime splits. Each is a full R15 Humanoid owned by the server, with most state types still on. This is the known prototype limit and hasn't been measured.

**Fix:** Measure first (see the test list). Turn off unused Humanoid states, slow MoveTo for far enemies, and consider capping Endless at 65 until it's measured.

**Where:** `RogueliteZombieChase.server.luau:350-405,433-564`, `ENEMY_SIMULATION_ARCHITECTURE.md`

### F1 · Every enemy is animated every frame, near or far — **fixed 2026-10-02**
*Phone & client performance*

**Done:** full rate within 60 studs, every 2nd-3rd frame to 90 (big enemies further), last pose held beyond, nothing off-screen; the QA attributes are Studio-only.

The client poses every enemy's bones each frame with no distance or on-screen check. It also writes two attributes per enemy per frame that only a Studio test reads. With 40-100 enemies on a mid-range phone this is the biggest CPU cost.

**Fix:** Skip enemies beyond about 90 studs or off-screen, and update 60-120 stud enemies every 2nd-3rd frame. Wrap the two SetAttribute calls in IsStudio().

**Where:** `RogueliteZombieAnimation.client.luau:70-178`

### F2 · Damage numbers and hit effects are unlimited and rebuilt every hit — **fixed 2026-10-02**
*Phone & client performance*

**Done:** `HitFeedbackVisuals` pools 28 hit numbers (teammates' give way first), 6 damage-taken numbers and 10 hit-flash Highlights; splat bursts are reused.

Each hit creates a part, a BillboardGui, labels, 3 tweens and a Highlight, and every client draws all four players' hits. Estimated at about 100 hits/s in a horde: 1,500-2,000 objects created and destroyed per second and around 30 live Highlights (Roblox caps those at 31). Expect stutter and heat on phones.

**Fix:** Cap and reuse damage numbers (about 25-30). Show only your own hits plus crits and kills. Add a "Reduce effects" setting, and skip Highlights over a budget.

**Where:** `combat/RogueliteCombat.client.luau:251-279`, `combat/MobImpactVisuals.luau:27-54`

### U1 · Settings reset every time you go lobby → match → lobby — **fixed 2026-10-02**
*UI & controls*

**Done:** the five settings are saved in the profile (ProfileAction SaveSettings, sent by `ui/SettingsSync.client.luau` a second after a change, checked and clamped) and set on the player at load, before ProfileLoaded. Run music waits for ProfileLoaded (up to 8 s) before it starts.

Music, sound, HUD size, shake and damage-number settings are stored only for the current server session. A player sets music to 0% in the lobby, presses PLAY, and the match starts at 100%.

**Fix:** Save the five settings in the profile (or pass them in teleport data) and apply them at join, before music starts.

**Where:** `ui/UITheme.luau:405-414`

### U2 · Roblox's player list and chat probably cover the HUD on PC and console — **fixed 2026-10-02**
*UI & controls*

**Done:** RogueliteHUD turns off the PlayerList core GUI on every device (with the health bar). With a keyboard, the TextChatService chat window moves to the middle of the left edge in runs and bottom-left in the lobby; phones keep Roblox's tap-to-open chat. Needs a look in a live game (chat doesn't show in Studio Edit).

Only the default health bar is turned off. The Roblox player list (top right) would sit over the weapon strip, and chat (top left) over health and XP. This comes from reading the code; I haven't seen it in a live game.

**Fix:** Turn off the PlayerList core GUI (the game has its own party UI), and move or restyle chat with TextChatService.

**Where:** `ui/RogueliteHUD.client.luau:50-55`, `ui/RogueliteUI.luau:19,69`

## Medium

### M7 · Prices shown come from the config file, not from Roblox
*Purchases & store*

The store and death screen print prices from MonetizationConfig. If a dashboard product is set to a different price, kids see one price and get charged another.

**Fix:** At startup, read PriceInRobux for each product, show that value, and warn on any mismatch.

**Where:** `combat/MonetizationConfig.luau:1-3`, `ui/StoreUI.luau:61`, `ui/DeathScreenUI.luau:73,143,217`

### M8 · Odds aren't shown on every paid random item — **fixed 2026-10-02**
*Purchases & store*

The Starter Pack and Godly Starter contain chests but sit on the Bundles tab with no SEE ODDS button. Robux rerolls and reroll packs give random results with no odds note.

**Fix:** Add SEE ODDS to every card containing chests, and a short odds note on reroll buttons and packs.

**Where:** `ui/StoreUI.luau:150-218,289`, `ui/ShopUI.luau:240-246`, `ui/LevelUpUI.luau:139-148`

**Progress 2026-10-02:** SEE ODDS is on the Starter Pack, Godly Starter, Mega and Ultimate cards and opens the Legendary Chest odds directly (closing them returns to the store). The run shop and level-up REROLL show each tier's chance from `EconomyConfig.tierOdds` / `LevelUpCatalog.tierOdds`, the same numbers the server rolls with (checked against 200k simulated rolls). Still to build: tappable odds rows with item cards (mockup first).

### S3 · The last save on leave or shutdown only tries once — **fixed 2026-10-02**
*Saving data*

**Done:** the last save is tried up to 4 times (1, 2, 3 s apart), keeping the profile until it saves; a lost lock stops at once. BindToClose waits for every save still running, leave-saves included, up to 27 s.

One DataStore hiccup when a player leaves drops everything since the last 120 s autosave and leaves the session lock stuck for up to 15 s. On shutdown, BindToClose doesn't wait for leave-saves already running.

**Fix:** Retry 3-5 times with backoff, keep the profile until the write succeeds, and make BindToClose wait for saves in progress.

**Where:** `combat/ProfileService.luau:140-164,571-586`, `combat/ProfileLock.luau:46-57`

### C2 · Idling in the shop fills the play-time quest and road — **fixed 2026-10-02**
*Cheating & admin*

**Done:** minutes count per player, only in a wave that isn't paused, alive and not down, with a hit of their own in the last 30 s.

The "minutes" counter ticks for everyone in a run in any phase, including the shop where players can't be hurt. Because there's no shop timer (G1), a player can sit in the first shop for 20 minutes to finish "Play 20 Minutes" and fill the Playtime road (up to about 6,875 emeralds).

**Fix:** Only count a minute during combat while the player is alive and has dealt damage recently.

**Where:** `combat/RogueliteMeta.server.luau:108-116`, `combat/LeaderboardService.server.luau:111`

### C3 · A second admin account, and two admin tools skip the "alone on server" check
*Cheating & admin*

**Progress 2026-10-02:** 109021050 is leavked, the user's friend and map builder: kept, and noted in AdminConfig. The shared alone-on-server check for EditPractice and EquipWeapon is still to do.

AdminConfig lists 341854066 (EggaRowls) and 109021050, which isn't documented anywhere. Admins can grant themselves emeralds on live servers. EditPractice and EquipWeapon also skip the check that stops admin tools in a server with other players, which can void everyone's rewards for that run.

**Fix:** Confirm or remove 109021050. Put the alone-on-server check in one shared function and use it in all three handlers.

**Where:** `combat/AdminConfig.luau:14`, `combat/AdminService.server.luau:156-166`, `combat/CharacterService.luau:250-271`

### G3 · The last-stand clock can run out before a paid revive arrives
*Gameplay bugs*

The clock is held only while the dialog is open plus 5 s. If the receipt or respawn is slow, the run ends as a defeat and the revive falls into the 50-emerald refund.

**Fix:** Keep the clock held until that player's receipt is processed (with a 30-60 s cap). Clear the hold in processReceipt, not when the dialog closes.

**Where:** `combat/RogueliteMeta.server.luau:290-296,398-400,534`

### G4 · Party members who load in late lose their starter weapon and tier
*Gameplay bugs*

Wave 1 starts 30 s after the first player arrives, and the starter swap only works before wave 1. A slow loader gets their class but keeps the default Frying Pan at Tier I, so their Tier III Glock is gone for the run.

**Fix:** Allow the starter swap for any member who hasn't fought yet, or hold late players as downed until the next wave ends (as the doc says).

**Where:** `lobby/MatchService.luau:22,159-160`, `combat/ShopService.luau:230-241`

### G5 · Elite, horde and longer waves are advertised but not built — **fixed 2026-10-02**
*Gameplay bugs*

**Fixed (the user's call: remove them):** run setup's ELITE / HORDE tags are gone (plain ticks at 5, 10, 15 stay, each pays a block of run emeralds; BOSS at 20 stays), and CURRENT_GAME_STRUCTURE.md no longer claims them.

The run-setup screen shows ELITE (5, 15), HORDE (10) and BOSS markers. On the server every wave is 30 s with 8 + 3×(wave-1) enemies, and nothing ever sets IsElite. Endless has no elites or bosses.

**Fix:** Build them, or remove the markers and the doc claims before launch.

**Where:** `lobby/RunSetupRules.luau:68`, `combat/ShopService.luau:314`, `combat/EconomyConfig.luau:6`

### G6 · The run shop sells weapons the player doesn't own — **fixed 2026-10-02**
*Gameplay bugs*

**Fixed (the user's call: owned only):** ShopService offers only weapons in ProfileWeapons or in the player's slots; with no owned weapon left for a weapon slot it offers an item. New weapons unlock from chests and the daily shop, whose Legendary deal is now 800 emeralds a copy (was 500). Checked over 4,000 rolls: no unowned weapon offered.

The docs say only owned weapons appear in the run shop. The code offers every non-Godly weapon, so chest drops only matter for the starter, and "unlock Mjolnir" rewards a weapon already in every shop.

**Fix:** Decide which rule you want. Then filter the shop by ProfileWeapons, or update the docs and reward wording.

**Where:** `combat/ShopService.luau:157-176`, `PROGRESSION_AND_SESSION_FLOW.md:161`

### P6 · Melee hit checks run 120 times a second against every enemy part
*Server performance*

**Progress 2026-10-02 (repo only, commit e788358; not in Studio, not measured):** each enemy is judged once per tick instead of once per returned part, sampling stops once nobody else in reach can be hit, and the gloves' parts are read once. The 120 Hz sampling and the boxes are unchanged, so swings hit the same enemies (MeleeSweepTests: same 5,188 hits; enemy checks 436,981 -> 30,006).

Each swing does about 30 box queries that return every part of every enemy touched. Boxing Gloves also call GetDescendants on each sample.

**Fix:** Query only one hit part per enemy, cache the gloves' parts, and cap sampling at 30-60 Hz.

**Where:** `combat/RogueliteCombat.server.luau:359-389`

### P7 · Enemy projectiles are real server parts moved every frame — **fixed 2026-10-02**
*Server performance*

**Done:** the server keeps each shot's flight and hit test and sends one Launch (and an End if it stops early) on EnemyShot; `EnemyVisuals.client.luau` draws them by server time, pause included.

Each ranged enemy shot clones parts, moves them every frame and replicates every move. Estimated 600-850 updates/s at wave 20.

**Fix:** Send a launch event and draw the projectile on the client. Keep only the server hit test.

**Where:** `combat/EnemyAttacks.luau:189-288`

### P8 · Idle enemy work runs every frame, before the 0.1 s throttle — **fixed 2026-10-02**
*Server performance*

**Done:** a new attack is looked for on the 0.1 s tick (attacks in progress still update every frame); facing is written only after a 2° turn.

Attack updates run per enemy per frame before the throttle check, and facing writes AlignOrientation every frame during attacks. Estimated 60k wasted calls/s at 100 enemies.

**Fix:** Move the idle path inside the 0.1 s tick, and only write facing when the angle changes by more than about 2°.

**Where:** `RogueliteZombieChase.server.luau:456-460`, `combat/EnemyAttacks.luau:101,289-304`, `combat/ZombieAttacks.luau:31`

### P9 · Each enemy's chase tick repeats shared work
*Server performance*

**Progress 2026-10-02 (repo only, commit 2ad238a; not in Studio, not measured):** the players' bodies, the marker and the Freeze/Pause flags are read once per frame for all enemies; separation no longer copies and sorts its neighbours (EnemySpatialGridTests: same push within 1e-5 studs).

Every enemy looks up the map marker and recomputes the nearest player 10 times a second, and separation sorts its neighbours just to keep an old order.

**Fix:** Cache the marker per map, compute players once per tick, and drop the sort.

**Where:** `RogueliteZombieChase.server.luau:416-486`, `combat/EnemySpatialGrid.luau:59`

### P10 · Contact damage checks every enemy for every player
*Server performance*

**Progress 2026-10-02 (repo only, commit 24f21cc; not in Studio, not measured):** each enemy's parts and contact numbers are read once and its position once per tick for all players; players whose timers are running are skipped (ContactTests: the same 97 contacts as the old loop; Instance reads 432,953 -> 5,588).

At 10 Hz each player loops over all enemies with several lookups each, about 18k calls/s with 4 players and 65 enemies.

**Fix:** Use the spatial grid or cached enemy records with a cheap distance test.

**Where:** `combat/CharacterService.luau:284-325`

### P11 · Quest data is re-sent to every client once a second during runs — **fixed 2026-10-02**
*Server performance*

**Done:** while a player is a run member, ProfileQuests waits; each wave clear's settleRun publishes it, and leaving the run catches up.

Kills keep the quest data dirty, and the multi-KB JSON is a player attribute every client receives, though only the lobby reads it.

**Fix:** Don't publish quest data on match servers until wave end or run end, or send it only to its owner.

**Where:** `combat/ProfileService.luau:473-489`, `combat/RogueliteMeta.server.luau:102-117,156-167`

### P12 · Server-only counters are replicated on every hit — **fixed 2026-10-02**
*Server performance*

**Progress 2026-10-02:** enemy-side counters (EnemyHits, LastEnemyDamage/Impact, attack serials, slam counters) moved to server tables. Combat side done too: ConfirmedHits, practice counters and status Until attributes are Studio-only, knockback times are a server table shared with pets, and kill-credit attributes are written only when they change. The bosses' BossHits / LastBossDamage are written only in Studio (a QA test reads them).

LastDamageUserId, ConfirmedHits, LastKnockback, EnemyHits, BossHits and similar attributes change per hit and replicate to all clients, though no client reads them.

**Fix:** Keep them in a server table, and put QA-only counters behind a Studio flag.

**Where:** `combat/CombatEffectsService.luau:66-100`, `combat/EnemyAttacks.luau:166-167`, `combat/ZombieAttacks.luau:79-80`

### P13 · Spawn warning markers tween on the server — **fixed 2026-10-02**
*Server performance*

**Done:** the bars are static; clients pulse them.

Each spawn warning is two neon parts with endlessly repeating server tweens, which replicate Transparency every frame. About 10 run at once at the start of each wave.

**Fix:** Place a static marker (or fire an event) and let the client pulse it.

**Where:** `RogueliteZombieChase.server.luau:221-237`

### F3 · Deck of Cards searches its whole model every frame
*Phone & client performance*

The Deck calls GetDescendants on 3 cards (about 70 GUI parts each) every frame, plus ancestor lookups on every weapon part.

**Fix:** Cache the parts and SurfaceGuis when the weapon binds, and only write values that change.

**Where:** `combat/RogueliteCombat.client.luau:179-192`

### F4 · Opening the shop mid-wave rebuilds it on every crystal — **fixed 2026-10-02**
*Phone & client performance*

**Done (the user's call):** the in-run SHOP button and its B / gamepad X keys are gone; the shop only opens between waves, on its own.

With the shop open during a wave, every shard pickup clears and rebuilds hundreds of UI objects. On a phone that's a hitch per pickup.

**Fix:** Outside the shop phase, only update the balance and button states, or limit full rebuilds to 2 per second.

**Where:** `ui/ShopUI.luau:92-94`, `ui/RogueliteUI.luau:224,319,342`

### F5 · Power Washer and heavy swings build new raycast filters constantly
*Phone & client performance*

The Power Washer makes new RaycastParams every frame, and each heavy swing copies every enemy into a new exclude list.

**Fix:** Keep one cached RaycastParams per effect and rebuild it at most once a second. PetVisuals already does this.

**Where:** `combat/UtilityVisuals.luau:73-77`, `combat/SwingVisuals.luau:74-79`

### F6 · Effect limits are high for phones
*Phone & client performance*

Rubber Duck allows up to 180 flame puffs, each with a Fire object. Fire zones use 7 Fire parts each, 3 per player. Rocket smoke allows 144 puffs, all rewritten every frame.

**Fix:** Lower the caps to about 40 puffs and 24 rocket clouds, use ParticleEmitters, or turn effects down on touch devices.

**Where:** `combat/SpecialWeaponVisuals.luau:15-64`, `combat/RocketVisuals.luau:23,105-121`

### F7 · The lobby preloads everything at join
*Phone & client performance*

Every image from 11 modules, all 5 map islands and the Armory hall with 13 weapons are loaded and kept for the whole session, on phones too. I haven't measured the memory cost.

**Fix:** Load the islands and Armory the first time those screens open. Check F9 Memory on a low-end phone.

**2026-10-03:** Went the other way for feel. Loading on first open is what made islands and icons pop in. The loading screen now waits for the preloader, and the stages stay parked in the camera (`ui/README.md`, "No pop-in on first open"). The phone memory check is still open. If it's too high, skip parking the stages on touch devices.

**Where:** `ui/AssetPreloader.luau:76-133`

### U3 · Controller players can't change the volume
*UI & controls*

The music/SFX sliders only respond to mouse and touch. On console, selecting a slider and pressing A or the d-pad does nothing.

**Fix:** Handle left/right on the d-pad (±5%) while a slider is selected, or use − / + buttons.

**Where:** `ui/UITheme.luau:416-440`

### U4 · Queue pads that stream in late never update the setup screen
*UI & controls*

The lobby only hooks queue listeners to pads that exist when the HUD starts. With streaming on, a far pad can arrive later, and then host handover won't update the setup screen.

**Fix:** Hook pads as they're added (ChildAdded), or set the pads to stream as Persistent.

**Where:** `ui/LobbyUI.luau:~588-591`

### L2 · The Rojo project is missing modules the game needs
*Place & project cleanup*

MatchService, ProfileLock, MapBossService/Defs/Shapes, GodlyWeapons and ShotBatch aren't in default.project.json; Sync scripts install them. A plain rojo build hangs on WaitForChild. ServerScriptService and ReplicatedStorage don't ignore unknown instances, so rojo serve could delete those Studio-installed modules.

**Fix:** Add them to the project file, or set $ignoreUnknownInstances on those nodes and note that the Sync scripts are canonical.

**Where:** `combat/default.project.json`

### L3 · Test models and a default Baseplate are still in Workspace — **fixed 2026-10-02**
*Place & project cleanup*

**Done (the user approved, after saving `Documents/roguelite-archive-2026-10-02.rbxl`):** ZombieVariantPreviews, Zombie_R15_ProvidedTextures_Studio, the 3 stray Log_Master copies (near the world origin, not Pine Valley), the stray 13_Rock_Cluster, the empty folders, the Workspace Lighting folder and the Baseplate (nothing stood on it) are gone. Lantern_Post_41 is anchored, back at its mirrored spot and has its WarmLens again. RogueliteEnvironmentAssets (the evergreen import) stays.

Players can see: ZombieVariantPreviews (baby, mutant and Hammer boss rigs) at about (52, 6, 38), the zombie practice target, 3 stray Log_Master copies and 13_Rock_Cluster around the Pine Valley edge, and a visible 2048×2048 Baseplate at y = -8. There are also empty folders (LukeSandboxTesting, RogueliteWeaponShowcase×2, a Lighting folder). Lobby Lantern_Post_41 is unanchored and unwelded, so it falls or can be pushed.

**Fix:** Delete or move them to ServerStorage. Check whether any map stands on the Baseplate first. Anchor the lantern.

**Where:** `Studio: Workspace (checked 2026-10-02)`

### L4 · ServerStorage holds ~26,000 objects of backups and raw imports — **fixed 2026-10-02**
*Place & project cleanup*

**Done:** 88 old backups, 10 old lobby versions and 19 old raw imports and kits removed (15,519 objects, 515 old scripts) by `tools/CleanupPlace.luau`; ServerStorage is down to about 29,700 objects. Today's 10 backups (another session's map work, still in use) and the imports install scripts still use were kept. Details: plans/2026-10-02-cleanup-manifest.md.

There are 97 "Before…" backup folders (about 10,800 objects and 515 old scripts), three old lobby versions, raw enemy, boss and pet imports, and plugin storage. That makes the place file bigger and server start slower.

**Fix:** Save a copy of the place as an archive .rbxl, then delete the backups from the shipping place.

**Where:** `Studio: ServerStorage (checked 2026-10-02)`

## Low

### M9 · The region check allows purchases until PolicyService answers — **fixed 2026-10-02**
*Purchases & store*

Until the async PolicyService call returns, a player counts as unrestricted. One failed call marks a normal player restricted for the whole session, which hides chest packs from them.

**Fix:** Start everyone as restricted, retry the check 3 times, and only then show chest, egg and pack buttons.

**Where:** `combat/RogueliteMeta.server.luau:49-54`

### M10 · Re-asking for a revive keeps the last stand going forever — **fixed 2026-10-02**
*Purchases & store*

Each Revive request (every 0.5 s) refreshes the hold on the last-stand clock and logs an analytics event, without the player paying. A griefer can keep a fully downed party's run from ever ending.

**Fix:** Cap the hold per death (about 30 s), and don't refresh or log when a prompt is already open.

**Where:** `combat/RogueliteMeta.server.luau:393-400,525-527`

### M11 · Redeem codes are guessable and can't be switched off
*Purchases & store*

RELEASE (300 emeralds), CHESTS and REROLL are compiled into the code. A leaked code can be used once by every alt account, and stopping it needs a new publish.

**Fix:** Add expiry dates or a kill switch, a failed-attempt limit, and less guessable codes.

**Where:** `combat/ProfileService.luau:36-40,558-567`

### M12 · Lucky Cat's Luck raises shop odds and comes from emerald eggs
*Purchases & store*

Lucky Cat's Luck feeds into run shop rarity weights. Eggs cost emeralds, and emeralds are sold for Robux, so money can indirectly improve shop odds. The project rules forbid that.

**Fix:** Decide: allow it and write that down in the monetization doc, or keep Luck pets out of paid eggs.

**Where:** `combat/PetConfig.luau:83-87`, `combat/ShopService.luau:147,160`

### M13 · VIP isn't removed on refund, and the VIP Tag is only visible to the owner
*Purchases & store*

d.vip stays true forever once granted. The advertised "VIP Tag" is a text suffix on the player's own chip that nobody else sees.

**Fix:** Re-check pass ownership at join and clear vip if it's gone. Make the tag visible to others, or reword the card.

**Where:** `ui/StoreUI.luau:231`, `ui/LobbyUI.luau:263`

### S4 · Studio test grants save for real if Studio DataStores are on
*Saving data*

Simulated purchases and +200 emeralds say "not saved", but with EnableStudioDataStores=true they write to the real store. It's off by default.

**Fix:** Turn off simulated grants and DevEmeralds whenever the real store is in use.

**Where:** `combat/ProfileService.luau:43`, `combat/RogueliteMeta.server.luau:511,529-531,589`

### S5 · A failed name lookup shows "Player 123…" on leaderboards until restart
*Saving data*

One failed GetNameFromUserIdAsync caches the placeholder name forever.

**Fix:** Don't cache failures, or retry after about 5 minutes.

**Where:** `combat/LeaderboardService.server.luau:124-128`

### C4 · Armor, pets and upgrades can be changed mid-wave
*Cheating & admin*

WearArmor, EquipPet and Upgrade have no run or phase check, so a player can swap perks during a fight.

**Fix:** Refuse these while the player is in a run.

**Where:** `combat/RogueliteMeta.server.luau:576-578`

### C5 · Everyone can read everyone's profile
*Cheating & admin*

Emeralds, chests, eggs, pity, armor, quests, run results and death info are player attributes, so they replicate to all clients. No secrets are exposed; this is a privacy issue only.

**Fix:** Send owner-only data through a remote to that player instead of attributes.

**Where:** `combat/ProfileService.luau:66-93`

### G7 · A stuck boss can hold wave 20 forever, and a failed boss spawn counts as a win
*Gameplay bugs*

Wave 20 stays open while a boss exists, with no time cap, and map bosses walk straight at players without pathfinding. If the boss fails to spawn (missing ground or template), wave 20 ends at 30 s as a win and pays the first-win bonus. I haven't seen a boss actually get stuck.

**Fix:** Add a hard cap (for example 5 minutes, then respawn or fail), and retry or warn on a failed spawn.

**Where:** `combat/ShopService.luau:598-604,619-621`, `../hammer-boss/BossEncounter.server.luau:17-26`

### G8 · Two respawns at once can leave a player with no body
*Gameplay bugs*

A wave-end auto-rise and a revive receipt can both call rise(). The first one then thinks the run ended and destroys the new character, and auto-spawn is off.

**Fix:** Add a rising flag so only one rise runs at a time.

**Where:** `combat/RogueliteMeta.server.luau:251-260,290-298`

### G9 · Players who are down at wave end miss that wave's pay
*Gameplay bugs*

A player who died mid-wave and is raised at the clear gets no wave shards, emeralds, quests or VICTORY banner. If teammates ready up within 1-2 s, that player can also miss the shop.

**Fix:** Settle emeralds for every member at a clear, and have beginWave wait for respawns in progress.

**Where:** `combat/ShopService.luau:362`, `combat/RogueliteMeta.server.luau:132`

### G10 · Locked shop offers keep their old price
*Gameplay bugs*

A Tier IV weapon locked at wave 3 keeps its wave-3 price until wave 19.

**Fix:** Keep the locked discount, but still apply the wave price increase.

**Where:** `combat/ShopService.luau:107-110`

### G11 · The shop keeps offering new item types when the inventory is full
*Gameplay bugs*

With 16 item types held, the shop still rolls new types that can't be bought.

**Fix:** Leave new types out of the roll when the item inventory is full.

**Where:** `combat/ShopService.luau:157-168,514`

### G12 · "Reach Wave 10" needs wave 10 cleared
*Gameplay bugs*

Dying during wave 10 doesn't count, which may not match what players expect from the quest name.

**Fix:** Count reaching the wave, or rename the quest to "Clear Wave 10".

**Where:** `combat/RogueliteMeta.server.luau:136`

### P14 · Lobby servers run full combat for every player near the dummies
*Server performance*

Lobby attacks are on by default, so ranged starters near practice dummies generate the per-frame bullet traffic from P1 for everyone in range.

**Fix:** Default lobby attacks to off, or only turn them on within a few studs of a dummy.

**Where:** `combat/RogueliteCombat.server.luau:35,94-97`

### P15 · Crystals are real objects, and a boss drops 50 in one frame
*Server performance*

Each kill creates a model and part with attributes. Waves clear them, but 15-25 kills/s means about 20 creates and destroys per second.

**Fix:** Draw crystals on the client from a batched event, or merge them past about 150.

**Where:** `combat/ShardDropService.luau:126-137,167-174`

### P16 · Blocked enemies stand still waiting for a path
*Server performance*

Pathfinding is limited to 10 jobs a second, and a blocked enemy stops until its path arrives. With many enemies behind walls, some wait up to about 10 s.

**Fix:** Prioritise jobs by distance, and keep steering along the old path or straight at the target while waiting.

**Where:** `RogueliteZombieChase.server.luau:58-77,468-470`

### P17 · An enemy type's first shot loads its animation data mid-wave
*Server performance*

The first ranged attack per enemy type requires and compiles its clips during the wave, which can cause a hitch.

**Fix:** Load the map's enemy types at run start.

**Where:** `combat/EnemyAttacks.luau:192`, `combat/EnemyMotion.luau:63-74`

### P18 · Failed shop requests re-send the whole shop to everyone
*Server performance*

A bad request re-publishes the full JSON shop snapshot, which replicates to all clients. Spamming it costs about 8 encodes a second.

**Fix:** Reply only to the requester and throttle failures.

**Where:** `combat/ShopService.luau:105,456`

### P19 · An analytics field can fill up with mob instance names
*Server performance*

When the cause of death isn't known, it falls back to attacker.Name, which can create many distinct values like "Zombie_07".

**Fix:** Strip number suffixes, and check event counts against Roblox's current analytics limits.

**Where:** `combat/RunAnalytics.luau:87`

### F8 · The first pet causes a one-time freeze
*Phone & client performance*

PetRigs (2,987 lines) is loaded inside RenderStepped the first time a pet appears.

**Fix:** Load it with task.defer when the script starts.

**Where:** `combat/PetVisuals.client.luau:37-49`

### U5 · Lobby hotkeys still work inside full-screen screens
*UI & controls*

L/C/J/K/T fire while Armory, Chests, Eggs or the Skill Tree are open. For example, C or J can close a chest reveal mid-animation.

**Fix:** Ignore hotkeys while any full-screen screen is open.

**Where:** `ui/LobbyUI.luau:~499-510`

### U6 · Server request errors make buttons silently do nothing
*UI & controls*

InvokeServer calls aren't wrapped in pcall, so a server error throws on the client with no message.

**Fix:** Use one shared request() helper that returns "Try again". AdminPanelUI already does this.

**Where:** `ui/StoreUI.luau:53,272,392`, `ui/QuestsUI.luau:161,384`, `ui/RunSetupUI.luau:290`, `ui/ArmoryUI.luau:578,639,1073`

### U7 · The HUD can wait forever and never appear
*UI & controls*

Several screens WaitForChild the player's state folder with no timeout. If the server fails to make it, the player has no HUD and no health bar.

**Fix:** Add a timeout of about 20 s, then retry or show "Reconnecting".

**Where:** `ui/ShopUI.luau:69`, `ui/LevelUpUI.luau:39`, `ui/DeathScreenUI.luau:26`, `ui/WeaponInventoryUI.luau:92-94`

### U8 · Dragging the background plays a click
*UI & controls*

Turning the avatar in the Armory or panning the skill tree clicks every time a finger touches down.

**Fix:** Set the NoClickSound attribute on the two drag areas.

**Where:** `ui/ArmoryUI.luau:1704`, `ui/SkillTreeUI.luau:748`

### U9 · The close X is about 32 px on phones
*UI & controls*

Below the 44 px minimum touch size, so it's easy to miss.

**Fix:** Make the X bigger on short screens, or add invisible padding to its hit area.

**Where:** `ui/UITheme.luau:334,347`

### U10 · LEAVE RUN on the death screen is one tap, right next to REVIVE
*UI & controls*

The buttons are about 24 px apart on a phone, so a mis-tap ends the run. The shop's LEAVE RUN already asks for a second tap.

**Fix:** Use the same two-tap confirm here.

**Where:** `ui/DeathScreenUI.luau:145,225`

### U11 · Run setup says armor isn't in the game yet
*UI & controls*

Run setup still reads "Armor: none yet · armor sets arrive with chest rewards".

**Fix:** Show the worn set, or remove the line.

**Where:** `ui/RunSetupUI.luau:284`

## Cleanup

### K1 · Debug flags, test remotes and dev UI ship to players
*Place & project cleanup*

These all ship, but each is gated and the server re-checks it:

- EconomyConfig has DEBUG_CURRENCY_ENABLED = true (only usable in Studio).
- The remotes SetTestOption, StudioTravel, EditPractice and EquipWeapon exist on live servers.
- CardShowcase runs every frame for an empty showcase.
- CharacterStatsUI, UILayoutAudit and AdminPanelUI are sent to every client.
- Admin IDs sit in a module clients can read.

**Fix:** Set the flag to false, only create the test remotes in Studio, delete CardShowcase, and move the dev UI and admin IDs to the server.

**Where:** `combat/EconomyConfig.luau:4`, `combat/default.project.json:311-377,527-528`, `combat/AdminConfig.luau`

### K2 · HTTP requests are enabled only for local sync tools
*Place & project cleanup*

HttpEnabled is on. Only the Studio sync scripts and the untracked tools/ folder use it (localhost, loadstring). No runtime code makes web requests.

**Fix:** Turn HttpEnabled off for the published place if your sync workflow allows it. Keep tools/ out of the place, and confirm LoadStringEnabled is off.

**Where:** `Studio: HttpService.HttpEnabled = true`, `tools/`

### K3 · Design docs contradict the code
*Place & project cleanup*

These docs no longer match the code:

- MONETIZATION_AND_REWARDS.md still has "no paid chests or rerolls" boundaries, which the 2026-09-27 decision replaced.
- Docs say level-up rerolls cost shards; they cost Robux or saved rerolls.
- The Tier IV duplicate filter isn't built.
- "Cash Out or Keep Going" is just Leave Run.
- Beach Cove is described with no boss.
- ui/README says ×10 is refused without Quick Open.

**Fix:** Update the docs once you've decided M2, G5 and G6.

**Where:** `MONETIZATION_AND_REWARDS.md`, `CURRENT_GAME_STRUCTURE.md:52`, `PROGRESSION_AND_SESSION_FLOW.md:104,151`, `LOBBY_AND_MATCH_SERVERS.md`, `studio-prototype/ui/README.md:67`

### K4 · Small dead code
*Place & project cleanup*

This code is unused or misleading:

- pendingArg is written but never read.
- receiptBusy is cleared on PlayerRemoving while a receipt may still be running.
- ConfirmedHits is never read.
- The Hit and Shot entries in InstallKatana/InstallLoadout are leftovers.
- Market.ProcessReceipt is set after about 20 WaitForChild calls, so if one module is missing, receipts are never handled.

**Fix:** Remove the unused code, and assign ProcessReceipt near the top of RogueliteMeta.

**Where:** `combat/RogueliteMeta.server.luau:424,490,521,601`, `combat/CombatEffectsService.luau:78`

## Set up outside the code

- Create the 31 developer products and 2 game passes. Set each dashboard price to the number in MonetizationConfig.
- Fill in the Maturity & Compliance questionnaire (required before players can find the game).
- Set server size. The place says 60; parties are 4. Pick the lobby size you want, and check private-server settings.
- Icon, thumbnails, description, genre and supported devices (phone, tablet, console).
- Check StarterGui.ScreenOrientation. If phones can go portrait, the UI shrinks to about 30% and becomes unreadable.
- Before deleting backups, save an archive copy of the place.

## Test on real servers and devices

None of these have been run. They need published products, several real clients, or real devices.

- Every product and pass with real Robux. Check the price charged matches the price shown.
- Receipt retry: leave mid-purchase, rejoin, and confirm you get exactly one grant. Also buy during a lobby → match teleport.
- Revive ladder 65 → 130 → 260 → 520 → 1040 → 1040, including a purchase confirmed just as the wave ends.
- A game pass bought on the website, then joining several times (M6).
- A region-restricted account: chest packs, Starter Pack, VIP chest, rerolls, banishes, eggs.
- Two real servers: quick rejoin, the 15 s lock takeover, lobby → match → lobby hand-offs, and a shutdown from the Creator Hub.
- 4 real players at waves 5, 15, 20 and Endless 32+. Record F9 Server Jobs, Script Performance, Network KB/s and Memory, with a gun-heavy party and a melee party.
- One player AFK in the shop and at level-up (G1), and a party member who loads in 30 s late (G4).
- A mid-range phone at wave 12+ with 40+ enemies, damage numbers on and off; and phone memory after opening Armory and PLAY.
- PC with 3-4 players: Roblox player list and chat versus the HUD (U2).
- Console on a TV: every lobby window with a gamepad, including the settings sliders.
- An under-13 or non-verified account: rocket explosions fall back cleanly without EditableMesh.

## Checked and looks fine

- Combat is server-authoritative: no remote carries damage, hits, positions or prices.
- Receipt handling: one ProcessReceipt, deduped by PurchaseId, saved before it's acknowledged; nothing is granted without a save.
- Session locking uses UpdateAsync, and a failed load never overwrites a save. Studio DataStores are off by default.
- Shop math: no negative shards, no duplicates from combine or sell, and the 6-slot and Tier IV caps hold.
- Stat clamps: armor, dodge, attack speed and cooldown can't break, with no divide-by-zero.
- Chest and egg odds shown match the server rolls. Daily deals, codes and quest claims can't be claimed twice.
- Dead enemies are destroyed. Per-player state is cleared on leave, and a second run doesn't inherit the first run's state.
- All 15+ ScreenGuis are built once with ResetOnSpawn off. Screen connections are cleaned up on close.
- Muzzle flashes, bullet impacts, boss warnings, shards and pets already pool or cap their effects.
- Rojo build passes, and every Luau file parses.
