# Portal runs fixed (map=nil), clear START flow, more effects — October 3, 2026

- **Portal runs went back to the lobby:** the trip log (`MatchService`, DataStore `RogueliteTripLog_v1`) showed `launch: map=nil` and then `sent back: map nil could not be set`. `RogueliteLobbyPreview.launch` called `state:finish(index)`, which clears the pad's map and difficulty, before reading `q.map`, and it had done so since plan C. Fixed in 6c7f421: map and difficulty are read first, and `MatchService.launch` refuses a launch without a valid map. The trip log stays: each trip step, with its error, for the last 30 per player. A player sent back sees the reason.
- **START, then READY again:** PLAY → START puts you on a pad that's already counting down. The lobby treated that like stepping on and reopened the setup screen with READY, which looked like a second step. Now (`LobbyUI`) it doesn't reopen on a pad that's counting down (or within 5 s of your own START).
  - The member button says LOCK IN: it only confirms your class; there's no ready check.
  - The top banner says what happens next: STARTING IN 8 (lime) with the map and players, ENTERING PORTAL..., or who's picking the map.
  - Server replies: "Starting in 10s"; "Locked in as Gunner. Starting in 6s" or "... Waiting for the host to start".
- **Skill tree centred (`SkillTreeUI`):** the board, title and info card were centred in the space right of the bonus column, 180 px right of centre at 1920x1080. They're now centred on the screen, with the board band mirroring the column's edge (at least 720 px wide on small phones).
- **Class box lists weapon damage (`RunSetupUI`):** the legend sentence is replaced by "WEAPON DAMAGE AS A GUNNER" plus one chip per class: icon, name and percent, best first, coloured like the badges. "Godly: no change" is on the heading line. Desktop is 3 x 2; phones are 2 across.
- **Free claims and buys get effects:** the Store's DAILY free emeralds, the VIP chest and the deals play the CLAIM effect, flying into the Store's own emerald pill (`StoreUI` → `QuestsUI.claimFX` with a target). In the run shop (`ShopUI`, sandboxed, so it has its own compact copy), a confirmed buy throws 3–5 copies of the bought thing's icon, a Glock or a Spatula, which swoop into the slot it landed in. The card punches and fades over a glow, and the slot bumps (~0.8 s).
- **Studio:** 6c7f421 (the map fix) and then 6e0d885 (7 scripts) synced 2026-10-03 with guarded execute_luau calls. Each script was written only if Studio held its exact previous commit; afterwards all matched.
- **Not run:** no Play test (the user tests).

# Tutorial pacing, one-crystal crystals, LEAVE off the pad — October 3, 2026

Play-test report: zombies still ran in right after loading, level-ups came too fast, crystals gave 5 each, there wasn't enough zombie killing, and LEAVE left you standing on the pad.

- **Crystals worth 1:** the tutorial set each kill's crystal to 5 (`CRYSTAL_VALUE`, `Shards.killValue`). That's gone: one crystal per mob, worth 1, the same as normal runs. The first level-up used to come on the 4th kill.
- **More zombies:** waves are now 24 / 30 / 10 + boss (were 6 / 15 / 4). The numbers still work: 24 kills + 15 for the clear = 39 crystals at shop 1, enough for the guided Glock (24). The first level-up comes at the 20th kill, late in wave 1. Shop 2 has 63 crystals at level 3. `TutorialTests` assert this, and the same walk was checked in Python. `MAX_WAVE_SECONDS` 90 → 180 for the bigger waves.
- **5 s welcome:** `WELCOME_SECONDS` 3 → 5 after the loading screen, before wave 1.
- **Slow loads:** `MatchService`'s 30 s `PARTY_WAIT` counted from joining the server, but a loading screen can last ~33 s, so a slow load could still start wave 1 under it. Now after 30 s it only stops waiting for members who never arrived. Members who are here but still loading are waited on up to `LOAD_WAIT` (45 s).
- **Level-up line:** Eggbert picks "You leveled up!" or "Two level-ups!" from the pending count, not the wave, since each shop now has one card.
- **LEAVE:** it now also moves you just outside the ring, on the side facing the lobby spawn, on the ground found by a raycast. Walk back on to rejoin.
- **Class badges (`RunSetupUI`):** a bare "-5%" read like a discount. Each badge is your damage with that card's class's weapons when playing the class you picked (`CharacterStats.ClassFit`; example as a Mage: Mage +15%, Gunner -5%, Brawler -10%). It now shows "DMG" under the number (`T.fitBadge` with a word), and a 16 px cream line under the class description explains it. It used to be 13 px grey text at the bottom. On phones the card icon moved left so the badge doesn't cover it.
- **Achievements title card (`QuestsUI`):** the ribbon, "TITLE" and the name crowded each other; the card sat up to 14 px below the reward tiles and hung over the NEXT: line; and long names spilled up over TITLE. Now the card has the tiles' top and height, the ribbon is a square on the left, and TITLE and the name are centred together. The name truncates with "..." and the card clips.
- **CLAIM effect (`QuestsUI`, `Q.claimFX`):** once the server confirms a claim, on its own layer above the window (~1 s, flat images and tweens only):
  - the reward slot pops, over a glow-and-rays flash;
  - emeralds splatter out and arc into the HUD counter (6 at 50, up to 12), the counter bumps and "+50" rises off it;
  - chests squash and stretch inside a sparkle ring; title cards get a shine sweep;
  - the lobby tracker's CLAIM flies emeralds into the counter and pops the check.
  The slots are copied at click time because the window redraws on the result. Nothing takes input, and the layer is destroyed at 1.7 s.
- **Studio:** synced 2026-10-03 at b03f62a with one guarded execute_luau call (8 scripts, each guarded on its exact 9589a61 version, which a read-only check had just confirmed). Afterwards all 8 matched b03f62a.
- **Not run:** no Play test (the user tests). The "sent back to the lobby from a match" report isn't diagnosed yet; it needs the live F9 log.

# Parties, the full Armor tab, a bigger air boost — October 3, 2026

- **Parties (user: "when i click play he automatically gets put in a pod with me"):** the Party window now has INVITE on every other player in the server (INVITED while pending, IN YOUR PARTY once in). The invited player gets a card with ACCEPT / DECLINE (60 s) and a badge on the party button. LEAVE PARTY leaves it. Up to 4, a pad's capacity.
  - When anyone in a party steps on a portal or presses PLAY, `RogueliteLobbyPreview` moves the rest of the party standing in the lobby onto that pad (`pullParty`). It does this again when the host presses START, for anyone who joined the party after that. Members don't have to do anything; launch uses their current loadout. A solo pad has no room, so solo stays solo. Someone who pressed LEAVE on that pad isn't pulled back.
  - Rules are in the pure `lobby/PartyState.luau` (beside `QueueState`). State reaches clients as `PartyMembers`, `PartyInviteFrom` and `PartyInviteUntil`, and requests go through the `Party` RemoteEvent on `workspace.RogueliteLobby`.
  - **Known gap:** parties live in one lobby server. After a run, each player returns to a lobby on their own, so you may need to party again.
- **Armor tab:** it only listed sets you own a piece of, so with no armor it showed the old "Armor is coming" placeholder. It now lists every set: owned first, unowned pieces locked, the same as Pets. The placeholder only shows if no armor meshes have loaded ("Armor is loading").
- **Air speed:** `AirSpeedMultiplier` 1.3 → 1.6 (a Brawler goes from 28.6 to 35.2 studs/s in the air). `MovementGuard`'s speed limit uses the same number, so jumping can't trip it.
- **Studio:** synced 2026-10-03 at 10978f8 with one guarded execute_luau call: 5 scripts updated and `RogueliteLobbyPreview.PartyState` created (Sandboxed copied from `QueueState`). Afterwards all 6 matched 10978f8.
  - Studio's `CharacterStats` and `MovementCheck` were still from before ee48545: none of ee48545 (mobs ×5 damage, the client-applied jump boost) had been synced, and Studio's air boost was 1.12. Their only difference from 10978f8 was the air-speed line and a comment, so they were guarded on those exact older versions (0b2b759, f17271d).
  - Studio's older `CharacterService` applies the boost on the server. Its `MovementGuard` allows `MoveSpeed × 1.12 × 1.5 + 16` per second: 53 for a Brawler, who now covers about 35 in the air.
- **Saves reset:** the user asked to reset EggaRowls (341854066) and leavked (109021050) so both play the tutorial fresh. Neither was in a server (no lock). Both `RogueliteProfile_v1` records were backed up to `output/profile-backups/` (untracked) and then removed, and both read back empty.
- **Not run:** no Play test (the user tests).

# Wave 1 waits for the loading screen; loading art shows — October 3, 2026

Play-test report: the tutorial began while the player was still loading. Zombies were already chasing, a few were dead, the player had levelled up, and Eggbert's welcome was missed. Half the loading screens stayed gray.

- **Why wave 1 was early:** a match started wave 1 as soon as each member's character spawned. On the client the loading screen stays up after that, up to about 15 s (menus warming up, then the fade). Meanwhile the pan swung by itself behind the screen. Eggbert's 5 s welcome also typed out and timed out underneath it.
- **Wave 1 now waits:** once the arrival screen has fully faded, `LoadingScreen` fires `RunAction 'Loaded'`, and `RogueliteMeta` sets the player's `ClientLoaded`. `MatchService` starts wave 1 when every member has it, still at most 30 s after the first arrival (`PARTY_WAIT`). The tutorial then waits `WELCOME_SECONDS` (3) more. The Studio tutorial (`TutorialDirector`) waits the same way. Example: the screen clears 9 s after the character spawns, so the welcome shows at 9 s and wave 1 starts at about 12–12.5 s (the server checks twice a second).
- **Eggbert waits too:** `TutorialGuide` hides while `PlayerGui.LoadingScreen` exists, and his welcome clock starts when it's gone.
- **No empty shop before wave 1:** on match servers and in the tutorial, `RogueliteUI` no longer opens the wave-1 shop (wave 1 starts by itself there). A Studio arena start and the admin Waves button still get it, because its GO starts the wave.
- **Why the art was gray:** each art half started at `ImageTransparency` 1 and faded in once `IsLoaded`. Roblox never loads a fully transparent image, so `IsLoaded` stayed false and the art only came in at the 20 s fallback. Shorter screens stayed charcoal the whole time. Checked in Studio Edit with a CoreGui probe: at 1, a label wasn't loaded after 5 s, even right after a successful `PreloadAsync({gui})`. At .995 it loaded in 0.3 s. The halves now start at .995, the same trick `AssetPreloader` uses.
- **Studio:** synced 2026-10-03 at 9a99d1a with one guarded execute_luau call (8 scripts, all or nothing). Each script was written only if Studio's Source still equalled ee48545 and the new source compiled. A read-only dump right before showed all 8 at ee48545. Afterwards every script matched 9a99d1a.
- **Not run:** no Play test (the user tests it).

# Tutorial play-test, round 2: arrows, placement, crystals, chests — October 3, 2026

Spec section: "Play-test fixes, round 2" in `../../plans/2026-10-03-tutorial-design.md`.

- **Arrow height (`TutorialGuideUI`):** screen = AbsolutePosition + the top bar's inset, for every layer. Full-screen layers (IgnoreGuiInset) read their own top-left as (0, -58), and the old code added nothing for them, so arrows sat 58 px high on the level-up cards, chest screen and results.
- **Placement:**
  - `guide.context{avoid, prefer, edges}`. The player's character is always kept clear.
  - The run passes the boss and `edges` (corners and sides only).
  - The chest screen passes the chest models and `prefer` (right of the chest menu).
  - A compact shape (portrait over a 480-wide box) is tried after the wide one at each size.
  - A context change looks for a new spot at once.
- **Crystals (`TutorialGuide.client`):** wave 1 points at the nearest crystal on the ground (arrows can point at world Models now), then at the HUD's `Shards` counter for 7 s after the first pickup.
- **All runs:**
  - Melee reach bonus 0 (`EnemyAttacks`).
  - Boss crystals burst from the boss (`ShardMotion.burst`, `BurstFrom`/`BurstDelay`, a sparkle) and fly 1.4 s later; the wave-end sweep keeps their turn.
  - Pickup VFX in `ShardVisuals.client` (third version, 618c18e, after "make the star look more like the reference images ... starts small gets larger and pops ... clean and nonchalant and smooth"):
    - A star at hip height on the side the crystals came from, a little toward the camera. It grows over 0.15 s, swells a touch, then pops; one or two tiny twinkles join it for bigger hauls.
    - At the pop, shards burst out from a spot riding along with the player, and a faint thin ring spreads.
    - No "+N" ("kinda annoying") and no light on the body.
    - Scaled by how many land within 0.1 s.
- **Chests (`ChestConfig`):** a few items each, each item a rarity roll with a stack by rarity: Silver 1 item, Gold 1–2, Magical 2, Legendary 4. The API is `roll` / `open` / `fill`, plus `chance`, `itemRange`, `itemsText` and `expected`; `rollCounts` and `group` are gone. `ChestScreenUI` and `StoreUI` say items, not copies ("1 item each", "1 item from a Silver Chest"). The tutorial seed replaces the first Silver Chest's roll. `ChestConfigTests` were rewritten with hand-worked summaries. The sim's before/after pace is in RARITY_GODLY_ARMOR.md section 1.
- **Checked (Studio Edit, nothing saved):**
  - every changed file compiles;
  - `TutorialTests` pass 47 checks;
  - `ChestConfigTests` pass 145 checks with 20000 rolls;
  - the guide UI mounted in CoreGui against mock layouts: the lobby box was clear of every panel, the run box went to a corner, and the chest screen used the compact box right of the menu;
  - `ShardMotion.burst` arcs and lands.
- **Studio:** synced 2026-10-03 with `tools/LaunchSync.luau` at 10ace4f (`combat/tutorial-playtest2-sync-map.json`): 11 scripts, all or nothing, each guarded on Studio's exact Source, which still matched ac17bde. Afterwards all 11 matched 10ace4f with Sandboxed unchanged. This also carried deb1bc0's Legendary Chest numbers.
- **Not run:** no Play test of these yet. The pickup VFX and the burst have not been seen in motion.

# Tutorial play-test fixes — October 3, 2026

The user's first play-test of the tutorial. Spec section: "Play-test fixes" in `../../plans/2026-10-03-tutorial-design.md`.

- **Any pick counts (`TutorialGuide.client`):** the first shop moves to GO after any buy, or when the suggested Glock is gone or too dear. The Armory step finishes on any upgrade, or skips when nothing can be upgraded. The Equip step finishes on any armor change. OPEN AGAIN is suggested only for a Silver Chest, and the offer step skips if the store can't open. Lines no longer ask for one particular pick. Admin-panel restarts start every step's state over.
- **Placement (`TutorialGuideUI`):** the arrow's target is never covered. Spots are the corners, middle-left and middle-right, then a 13 × 9 grid farthest-from-centre first. A piece inside the panel it belongs to counts once. The mockup's lobby now has the real lobby's panels and the same rule; there the box sits in the sky right of centre.
- **Eggbert:** the guide's name (`TutorialConfig.GuideName`), on his tag, in his welcome line and on his lobby speech bubble (`EggMerchant`).
- **Victory:** the tutorial's last clear goes to phase `Victory` (`ShopService.finishWave`): no shop, level-up cards or countdown. The HUD reads VICTORY and the guide shows only the banner.
- **All runs:** held players don't attack (`RogueliteCombat`; pets too: `PetService`). A wave boss lands facing the nearest run member (`BossService.spawn`). Melee reach bonus is +0.9 (was +1.5; `EnemyAttacks`). Chests give one item per rarity (`ChestConfig`; Silver about 2 different items, was 4–5).
- **Lobby spawn (Studio only):** `Workspace.RogueliteLobby.LobbySpawn` moved from z 18 to z 4, 14 studs toward the portals, so the camera no longer sits inside `Leaderboards.Leaderboard_Kills`.
- **Checked (Studio Edit, nothing saved):**
  - every changed file compiles;
  - `TutorialTests` pass 46 checks;
  - `ChestConfigTests` pass 137 checks with 20000 rolls, including the new one-item-per-rarity check;
  - different items per chest over 20000 chests: Wooden 1.27, Silver 2.09, Gold 2.29, Magical 3.11, Legendary 4.02;
  - in the mockup, the guide box lands clear of every panel on each screen.
- **Studio:** synced 2026-10-03 with `tools/LaunchSync.luau` at ac17bde (`combat/tutorial-playtest-sync-map.json`): 11 scripts, all or nothing, each guarded on Studio's exact Source, which still matched 7b4e1a4. Afterwards all 11 matched ac17bde with Sandboxed unchanged. The LobbySpawn move was made in Studio Edit (an undo point named "Move LobbySpawn toward the portals"); the Kills board is now 32.9 studs behind it.
- **Not run:** no Play test of these fixes yet.

# First-join tutorial — October 3, 2026

Spec: `../../plans/2026-10-03-tutorial-design.md`. Build steps: `../../plans/2026-10-03-tutorial-build-steps.md`. Mockup: `roguelite-planning/previews/tutorial-guide/guide.html` (dev server).

- **The run:** 3 waves in Pine Valley with the Frying Pan; a guided Glock buy in the first shop; the Hammer Zombie Boss on wave 3 with 650 HP; the player can't die. Run by `combat/TutorialDirector.server.luau` through small guarded hooks (`ShopService.tutorial`, `ShardDropService.killValue`, combat attributes `TutorialRun`, `HammerBossWave`, `TutorialBossHealth`, `WaveNoRespawn`).
- **Every run:** crystals left at wave end fly to the players and count as pickups (`ShardDropService.sweep`). Boss crystals fly straight to the run's players, split evenly. Wave bosses super-jump in: `BossService.INTRO` + `combat/BossIntro.client.luau`, which handle the shadow, fall, shockwave, camera orbit and name card. Players and enemies are held meanwhile (`CinematicUntil`).
- **The guide (`TutorialGuideUI` + `TutorialGuide.client`):** the Egg Merchant's portrait and a typed line, one gliding arrow, and the VICTORY banner. **The box never covers the UI:** each moment it takes the first corner that covers no visible button, panel, picture or text, shrinking if needed. Arrow targets are found by name (`Offer1`/`Choose`, `ShopLayout`/`Offer<n>`/`Buy`, `StartWave`, `BackToLobby`, `Row_Silver`, `Open`, `Claim`, `Again`, `Exit`, `W_01`, `Upgrades`, `UpgradeBig`, `Tab_Armor`, `A_Iron.Helmet`, `Equip`, `Close`, lobby `Bottom`/`Chests`/`Armory`/`Play`). Renaming one of these means updating `TutorialGuide.client`.
- **Lobby part:** progress is saved in `ProfileService` (`tutorial.step`, `ProfileTutorial`). It moves forward only via `ProfileAction 'TutorialStep'`. The guide opens the Store on BUNDLES through LobbyUI's new `GuideOpenWindow` hook.
- **Art:** `assets/tutorial/arrow.png` (`make_arrow.py`) and `assets/tutorial/merchant-portrait.png` (`blender-egg-merchant-kit/render_portrait.py`). Their asset ids go in `TutorialConfig.Asset` once uploaded.
- **Studio:** the admin panel's **Waves** tab has a **Tutorial** section. **Start tutorial** runs the run from the top, **Lobby part** pays the reward and goes straight to the chest/Armory steps, and **End tutorial** goes back to normal play. These work only in the combined Studio server. Alternatively, `Workspace.StudioTutorial = true` before Play starts it on join. Without either, Studio skips the tutorial.
- **Checked (Studio Edit, nothing saved):**
  - every changed file compiles;
  - `TutorialTests` pass 45 checks;
  - the guide UI mounted in CoreGui against a mock lobby: the box chose a clear corner, and the arrow landed under or over each target and turned as it glided.
- **Studio:** synced 2026-10-03 with `tools/LaunchSync.luau` at 5f1ac5c: 16 scripts updated and 5 created, all or nothing. Each update was guarded on Studio's exact Source, and only tutorial commits separated those from HEAD. Afterwards all 21 matched the commit, and the new scripts copied Sandboxed and Capabilities from their neighbours. The art is uploaded (`assets/tutorial/asset-ids.json`).
- **Not run:** no Play test yet.

# No pop-in on first open — October 3, 2026

Menus, the map-select islands and the Armory hall used to appear a beat late the first time. The preloader ran in the background and the loading screen faded before it finished. The islands and hall were also only added to the camera when their screen opened, so the renderer built them on screen.

- **Loading screen waits:** after the character spawns it shows "Getting the menus ready" until `AssetPreloader` sets `PlayerGui.AssetWarmReady`, for at most 10 seconds (`WARM_SECONDS`). It sets `PlayerGui.LoadingScreenUp` while it covers the screen.
- **Stages stay loaded:** `MapSelectBackdrop.Prepare` and `ArmoryStage.Prepare` park the islands and hall in the camera for the whole session (14000 studs from the lobby). Hide no longer removes them. The lock-silhouette Highlights are turned off while map select is closed.
- **One look behind the loading screen:** while `LoadingScreenUp` is set, the preloader points the camera at each island and both Armory shots for 0.15 s each. The renderer then already has their meshes and textures. It hands the camera back afterwards.
- **More images:** the preloader now also reads `EggConfig`, `StatPlates`, `ItemCardUI` (`ReviveIcon`) and the trip art in `ReplicatedFirst.LoadingScreenUI`. After that it fetches `WeaponTemplates`, `PetModels` and `ArmorSets` (match servers skip armor). This doesn't hold the loading screen.
- **Phone memory (launch audit F7):** everything stays resident for the session. That was already true for images, and is now also true for the islands and hall. This still needs an F9 Memory check on a low-end phone.
- **Studio:** synced 2026-10-03 with `tools/SyncPlan.luau` + `ui/no-popin-sync.json` (all five scripts guarded on 1814ff8; afterwards each matched 73a11ab). No play test run yet.

# Colour store and working quests — October 2, 2026

Plan: `../../plans/2026-10-01-H-store-and-quests.md`. The user approved the direction from an HTML mockup ("way better") and asked for no text touching borders, a fancier quests page, and quests that actually work.

- **Store (`StoreUI.luau`, new).** LobbyUI's `builders.Store` now calls `StoreUI.open(screen, ctx, focus)`. The window, tabs and buttons stay in the green theme. Every offer is a saturated colour card (`StoreFX.card`) with a glow and rays behind big art that sticks out past the card's top edge. Item slots are rarity coloured (`StoreFX.tile`), tags hang off a card's top-left edge (`StoreFX.tag`) instead of the bouncing lime ribbon, and diagonal corner sashes say BEST VALUE or ONE TIME (`StoreFX.sash`).
- **Godly Starter.** The chosen Godly lifts, glows and gets a check; the others go grey. The big art and its name switch to the chosen one.
- **Gem piles.** Emerald packs show more gems the bigger the pack is.
- **Quests (`QuestsUI.luau`, new).** Two tabs, DAILY and ACHIEVEMENTS, with claim badges:
  - DAILY has three quest cards (a coloured header, icon, progress and rewards; gold when done, with CLAIM) and a 30-day streak track (reward diamonds, CLAIM under rewards waiting to be claimed).
  - ACHIEVEMENTS has unlocks plus 8 trophy roads with rank diamonds, tier pips, reward slots and CLAIM.
  - The left HUD tracker shows today's three quests.
  - The server side is QuestConfig/QuestService (see the plan).
- **New StoreFX helpers:**
  - `card`, `art`, `tile`, `sash`, `tag`, `header`, `title`, `sub` (white outlined copy for colour cards), `progress` and `check`;
  - `button`, whose caption sits in the middle 70% of the button height so it never touches the border when windows scale down on phones.
- **Checks (Studio Edit, fresh repo copies in CoreGui, not saved in the place):**
  - `UILayoutAudit.run` reports 0 problems on all four store tabs and both quest tabs at 1920x1080, 1366x768, 1280x720, 1024x768, 844x390, 667x375 and 750x369.
  - The only flags left are the shared window chrome (title plate, close X) at phone scale, which every `T.window` has.
  - The windows were also redrawn from a GUI dump in a browser and checked by eye.

# Every screen size and device — September 30, 2026

A friend playing fullscreen 16:9 saw the Armory's loadout slots on top of the item list; in Studio (a wider viewport) it looked fine. Cause: the Armory scaled its left list, slot ring and details panel separately, each pinned to a different screen edge, and their widths (600 + 1000 + 540) are wider than 1920, so they collided at 16:9 and narrower and only separated on wide windows. The whole UI was audited against desktop (16:9, 16:10, 4:3, ultrawide, 4K), tablets and phones, and these rules now apply:

- **Full-screen screens** (Armory, Skill Tree, Chests, Run Setup) lay out on one canvas: `T.canvas(root, onLayout)`. The canvas is the screen divided by one scale (1920x1080 on a 16:9 monitor). Phones keep at least `T.READABLE_SCALE` (0.5) and get a smaller canvas instead (about 1500x740 on an iPhone 14), so each screen lays itself out to fit: lists and detail panels scroll, the Armory goes to two columns and drops the slot ring when there's no room beside the avatar. Never scale groups independently from different screen edges.
- Layout follows the screen's own `Root` frame (`AbsoluteSize`), not `workspace.CurrentCamera.ViewportSize`. Full-screen ScreenGuis use `ScreenInsets = DeviceSafeInsets` (out of phone notches) and keep their top corners below Roblox's top-bar buttons (`L.top`).
- `ArmoryStage.FieldOfView` (and the map-select backdrop) keep the 16:9 horizontal view on narrower screens, so the 3D avatar shrinks with the panels on 4:3 tablets.
- **Text:** `T.label` shrinks text that doesn't fit its box (down to 60% of its size) instead of spilling out.
- **Windows** (`T.window`): on phones they stay at a readable scale and the body scrolls (Settings was drawn at 22% before). The lobby-HUD margin around windows is proportional, so 720p laptops get bigger windows.
- **Lobby HUD:** the right icon column sizes to its buttons, wraps into two columns on short screens and stays above the touch jump button; the queue banner moves under the profile chip when the top centre is too narrow; touch screens get a bigger minimum scale.
- **In-run HUD:** the scale uses height as well as width; the menu launchers, boss bar and item strip are placed so they never overlap (any HUD size setting) and stay clear of the thumbstick and jump button; more than 21 items show a "+N" chip. Shop, level-up and death screens fit phones with 40 px buttons; the death screen's sixth weapon no longer overlaps the Progress column.
- **Touch:** full-screen menus hide the thumbstick and jump button while open (`T.hideTouchControls`).
- **Gamepad:** menus select their first/primary button when opened on a controller (`T.gamepadSelect`), and screens that redraw keep the selection (`T.selectionPath` / `T.restoreSelection`). Skill Tree: right stick pans, bumpers/triggers zoom, X buys. Shop: X toggles. Run Setup: Start/Enter confirms. Chests: A skips the reveal, B backs out one step (odds → results → list).
- **Checking it:** `UILayoutAudit.sweep(PlayerGui.<Screen>.Root)` resizes a screen through every device size and prints overlaps, off-screen pieces, text that doesn't fit, text under 9 px and (phones) buttons under 36 px. For the in-run HUD: `sweep(PlayerGui.RogueliteHUD.SafeArea, PlayerGui.RogueliteHUD.SafeArea.HUD)`. Mark intentional full-screen shades/boards `AuditIgnore`.
- **Syncing:** `SyncUIRuntime.luau` (Edit mode) writes a Studio script only when every line Studio has beyond the last commit is also in the repo file; Studio-only edits are listed and skipped, never overwritten. The first sync (2026-09-30) found Studio-only edits in RogueliteUI (coalesced build-strip redraws), ShopUI (live shard/level balances) and LobbyUI (right column centring); they were ported into the repo before syncing.
- **Synced and compiled in Studio 2026-09-30** (Edit mode; all 14 scripts compile, sandbox flags unchanged). A scope check found no undeclared names in any changed file.
- Checked so far by layout arithmetic at every size in the matrix (scratch models), parse/compile checks and code review. **Not yet checked in Play or on real devices**: the sweep, real phones (safe-area sizes, jump-button position), consoles, and whether Roblox's player list/chat cover the HUD with many players.

# Walk-up stands, pets and armor pieces — September 27, 2026

- **Stands (`StationApproach.luau` → ReplicatedStorage):** no E prompts. All lobby `OpenStation` prompts are disabled in the place and on the client. Each stand has a turning lime dashed ring on the ground in front of its counter, and a floating icon and name above it (ARMORY, LOADOUT, CHESTS, STORE, QUESTS). Walking onto the ring (within 4.2 studs of its centre) opens the stand's window after a quick camera push and a dip to dark. Walking 7.5+ studs away re-arms it. The rings rebuild when stand parts stream in: the place uses streaming, and stands are empty while the player is in the arena. LobbyUI's old prompt handler and 5-stud poll loop were replaced by one `StationApproach.start` call.
- **Armory:** tabs are WEAPONS / ARMOR / PETS (passives removed). Slots: HELMET, CHEST, LEGS and BOOTS on the left; WEAPON, PET, CLASS and UPGRADES on the right. Armor is four pieces with 2- and 4-piece set bonuses (decided 2026-09-27, see PROGRESSION_AND_SESSION_FLOW.md). Armor and pets show "coming" panels until they exist. Panels slide in only when the screen opens or switches view; selecting an item (including the one already selected) no longer replays the slide, and the grid keeps its scroll position. While open, the hall dims (ExposureCompensation −0.3, dais fill 0.35) and ProximityPromptService is off, and both are restored on close.
- Verified in single-client Play: travelled arena → lobby, all 5 rings built after streaming, walking onto the Collection ring opened Loadout with the transition, walking onto the Workshop ring opened the Armory (exposure −0.3, prompts off), a profile redraw left the panels in place, and the Armor tab rendered.

# Full-screen Armory in the 3D armory hall — September 27, 2026

ARMORY (button, Workshop stand, `TestOpenWindow('Armory')`) now opens a full-screen screen instead of the old 940×580 modal. `ArmoryUI.luau` (→ `ReplicatedStorage.ArmoryUI`) draws the UI and `ArmoryStage.luau` (→ `ReplicatedStorage.ArmoryStage`) the 3D stage. Both are plain (not sandboxed) ModuleScripts like LobbyUI. The lobby HUD hides while it is open.

- **Stage:** the timber armory hall from `blender-armory-backdrop` (`ReplicatedStorage.ArmoryBackdrop`) is cloned into the camera at (1600, 420, -14000). A copy of the player's avatar stands on the dais playing their idle animation, with their starting weapon floating at their shoulder. The hall's rack, pegs, shelf, barrel, anvil and crest hold the game's real weapon models (`ArmoryStage.Display`, cloned from `WeaponTemplates` and scaled by their `BoundsSize`). Drag empty screen space to turn the avatar. Without the hall installed, the screen falls back to a blurred, dimmed lobby.
- **Left:** ARMORY panel with WEAPONS / ARMOR / PASSIVES tabs (the Weapons tab carries a red badge with the number of ready upgrades), a MY CLASS filter and square cards: tier corners and badge, icon, name, have/need copies bar, a check on the equipped starter, a bobbing gold arrow when an upgrade is ready, and a padlock with NOT OWNED otherwise.
- **Around the avatar:** CLASS and ARMOR slots on the left, WEAPON (starter) and UPGRADES (n READY, jumps to the first ready weapon's upgrade view) on the right, and a stat plate with the starter's damage at its tier and the class's max health.
- **Right:** details for the selection. Weapons: description built from the catalogue (home class, trait, burn/poison/slow/lightning/blast), damage, attacks per second and range at the owned tier, copies bar, EQUIP AS STARTER (sets `LoadoutClass`/`LoadoutWeapon`, the same preference the Loadout screen sets; the server still validates it at run start), and UPGRADE READY / VIEW UPGRADES. Not owned: where it drops and OPEN CHESTS. Passives: effects and description. Class: buffs and CHANGE CLASS (opens Loadout).
- **Upgrade view:** the avatar fades and the weapon spins over the dais with a tier-coloured light and motes. The left panel lists Tier I–IV with what each adds (from `tierDamage`/`tierCooldown`), copies used and NOW / NEXT / done. The right panel shows stats with green gains for the next tier, the copies bar, "NEED n MORE COPIES", and a large UPGRADE. UPGRADE calls `ProfileAction('Upgrade', id)`, and a success plays a burst and ring in the new tier's colour. BACK returns to the avatar.
- The old modal Armory builder was removed from LobbyUI. Studio backup: `ServerStorage.BeforeArmoryScreen_20260927.LobbyUI`.

# Store polish and level-up BANISH / REROLL bar — September 27, 2026 (fifth pass)

- **Store:** tabs share the width left of the key/emerald pills (never overlap, labels never wrap). Every card has rotating rays + glow behind its art (`StoreFX.luau`, textures `assets/sunburst.png` 75268019571051 and `assets/glow.png` 101092695897243 from `build_assets.py`); art grows and tilts on hover, cards lift, featured buy buttons pulse, hero cards get a shine sweep and ribbons (BEST VALUE, MOST POPULAR, INSANE DEAL, FREE!). Chest packs show "SAVE x%". Removed the "or earn it free" lines and the unfinished Customization row.
- **Level-up:** no BANISH on cards and no shard reroll. A centered bottom bar has **BANISH** (red) and **REROLL** (lime), each showing "N SAVED" or its Robux price. REROLL uses a saved reroll or buys one and rerolls immediately. BANISH uses a saved banish or buys one, then the cards turn red and you click the one to remove (CANCEL to back out). Server: shard `UpgradeReroll` is rejected; a bought Banish is stored as a saved banish. `LevelUpTests.luau` updated.

# Tabbed store, daily deals, banish — September 27, 2026 (fourth pass)

Store tabs, daily deals, bundles, chest packs, codes, Quick Open ×10 and in-run BANISH are described in MONETIZATION_AND_REWARDS.md. Chests window: ×10 toggle (Quick Open or VIP) and a grouped results reveal (NEW! / +3 per weapon).

**Remotes used by sandboxed UI must be sandboxed.** `PurchaseRequest`, `PurchaseResult` and `RunAction` are `Sandboxed=true` with Basic+RemoteEvent capabilities (set in the Rojo project and by RogueliteMeta). Otherwise ShopUI/LevelUpUI clicks fail with "cannot fire ... Sandboxed property set to false".

Verified in Studio Play (single client): free deal claims once; codes redeem once and reject bad codes; ×10 refused without Quick Open, then 5 owned Royal Chests opened in one ×10 (40 drops); packs/bundles granted; a real level-up earned in the arena, then real mouse clicks on BANISH (Melee Damage removed, 5→4) and the stored-reroll button (5→4, no shards spent); layout audit 0 problems on all four store tabs.

# Robux, chests, profile and death screen — September 27, 2026 (third pass)

- **Rarity** keeps the exact green panel; only the corner accents change colour (`panelplain` + tinted `corners` overlay via `T.setTier`).
- **HUD:** shard and crystal-bag counters split the bar width evenly; the user's crystal-bag art (`assets/hud/shard-bag.png`) and emerald (`assets/hud/emerald.png`) replace the stand-ins.
- **Death screen** (`DeathScreenUI.luau`): server marks `RunDown` on death and holds the respawn; the client shows a YOU DIED splash, then stats, equipped weapons, items and progress with REVIVE (Robux, 1 per run: 50% health, 3 s shield, pushes nearby enemies, wave clock paused while solo) and GIVE UP (keeps keys, records best wave, run resets to wave 1).
- **Profile** (`ProfileService.luau`): keys, emeralds, classes, weapon tier + duplicates, owned chests, pity, receipts. In-memory in Studio.
- **Lobby:** Chests window opens chests for keys, emeralds or owned chests and reveals results (NEW!/+1 with have/need bars); Armory UPGRADE and class unlocks call the server; Store buttons prompt real products.
- Verified in Studio Play (single client): death → splash → summary; revive restored 62.5/125 at the death spot with a 3 s shield; second death showed NO REVIVES LEFT; give up reset to wave 1; Robux shop reroll replaced offers without spending shards; bought 550 emeralds, opened a Royal Chest (8 drops), upgraded Frying Pan 2/2 → Tier II 0/4; server rejected upgrade/chest requests without enough duplicates/keys/emeralds; layout audit 0 problems. **Not tested:** real Robux prompts/receipts (needs product IDs and a published game), DataStore saving, PolicyService-restricted accounts, multiple players.

# Rarity frames, upgrade bars and reference store — September 27, 2026 (second pass)

- **Rarity:** `assets/rarity.png` (from `build_assets.py`, uploaded as 83616445506728) has a white ring and white corners, so `ImageColor3` tints only those. `T.setTier(obj,tier)` gives tier II–IV cards and slots a blue/purple/red frame (buttons keep it through hover/disabled); common stays lime. `T.tierBadge` is a solid rarity pill with the numeral; it replaced the loose tier text that read as a stray line.
- **Upgrades:** weapons show `have / need` in a bar (`T.upgradeBar`, gold when ready) plus an UPGRADE button; see PROGRESSION_AND_SESSION_FLOW.md. Profile attribute is now `ProfileWeapons` = `id:tier:held` (was `ProfileCopies`).
- **Square boxes:** Armory weapons/passives, Loadout starters, chest contents and HUD weapon slots are square.
- **Store:** reference layout — featured Starter Pack (gold frame, ONE-TIME OFFER ribbon, content tiles, large price), VIP and Cosmetic Track rows with perk chips, Early Class Unlock / Gems / Customization sections. No products exist yet: price buttons read SOON and explain on click. No fake discounts, nothing random, no keys.
- **Close button:** larger red-framed X (the earlier ✕ glyph does not exist in FredokaOne).
- **Layout audit:** `UILayoutAudit.luau` (→ `ReplicatedStorage.UILayoutAudit`) flags text that does not fit its label or renders outside its box's inner area. In Studio the lobby ScreenGui has a `TestOpenWindow` BindableEvent so the audit can open every window. Result 2026-09-27: 0 problems across the in-run HUD, shop, and all lobby windows/tabs (Play, Loadout, Chests, Armory ×3, Quests ×2, Store, Profile, Party, Settings) with both a fresh and a sample saved profile.

# Green theme HUD, lobby and menus — September 27, 2026

All roguelite UI now builds through `UITheme.luau` (→ `ReplicatedStorage.UITheme`): charcoal nine-slice `panel`/`inset` art with lime corners, lime `button` faces for primary/selected actions, faceted stone end caps, FredokaOne headings and rarity strips (white/blue/purple/red) on cards. Shop, level-up, weapon inventory, stats editor, the Studio combat test panel and the new lobby all use it; the earlier flat Brotato-style cards and blue-gray Gotham test panel are gone.

**UITheme must stay `Sandboxed=true` with the same Capabilities as `ShopUI`.** Sandboxed scripts (ShopUI, LevelUpUI, WeaponInventoryUI, CharacterStatsUI, RogueliteCombat client) cannot require a non-sandboxed module. Rojo does not set this; set it in Studio after a fresh install.

## In-run HUD (`RogueliteUI.luau`)

Upper left: heart/health, potion XP bar, shard and shard-bag counters, and a `LEVEL UP ×n` pill bound to the server's `PendingLevelUps`. Top centre: stone-capped timer and wave. Upper right: the six equipped weapon slots (server `SlotN.WeaponId/Tier`, tier numeral in rarity colour) and up to 16 collected items from the shop snapshot. Right edge: SHOP [B], Studio-only GEAR [I] and STATS [P], and SETTINGS. Bottom centre, while a boss is alive within 600 studs: the boss bar. It uses the player health bar's red fill and orange damage trail (shared `healthTrack` helper) in a wide inset frame with stone caps. The boss name sits on a lime-cornered pill over its top edge (the model's `BossName` attribute, default HAMMER BRUTE). It rises in when the fight starts and sits higher on touch screens. Narrow screens (<720 px) move the weapon strip under the health block.

Settings (session-only LocalPlayer attributes): HUD size (`Setting_HudScale`), screen shake (`Setting_ScreenShake`, read by the combat client) and damage numbers (`Setting_DamageNumbers`; your own damage taken always shows).

## Studio lobby ⇄ arena testing and queue pads — September 27, 2026

`lobby/RogueliteLobbyPreview.server.luau` is now **enabled** in the place and tracks each player's area (`StudioArea`), so respawns stay where you are.

- **Start area:** `workspace.RogueliteLobby.StudioStartArea` (`Arena` default, or `Lobby`) in Properties.
- **Travel:** a LOBBY / ARENA switch sits top-right in both areas (hotkey F8). The server remote `RogueliteLobby.StudioTravel` moves only the caller. Leaving the arena empty mid-wave stops the wave.
- **Queue pads:** the dark "QUEUE n · x / 4" tooltip and E prompt are gone (backup: `ServerStorage.BeforeQueuePads_20260927`). Each pad has a raised light ring and a light column that fades as it rises. The column is four curved beams forming one seamless wall, with the `lobby/build_pad_light.py` fade texture. The earlier flat panels showed vertical seam lines. Both are white when the pad is empty and red while players are on it. A floating counter shows the map, "x/4" and a status line.
- **Pad flow (`QueueState`):** the first player to step on is the **host**, and the full-screen setup opens straight away. While the host chooses, the pad reads "Name is choosing". START sends `RunSetup` ('Start', map, class, weapon, solo). The server checks the map unlock and class/weapon ownership (`RunSetupRules`), then starts a 10 s countdown (3 s if the pad is full or Solo). Anyone else who steps on gets the class step with READY. A queued player can walk and jump inside the pad's ring but can't leave it: the client holds them inside a 7.4-stud circle, and the server puts back anyone more than 11 studs out. LEAVE in the banner is the only way off, and it keeps you out until you step off. If the host leaves, the next player becomes host and gets the map step. A host who doesn't press START within 60 s gives up the pad. Launch shows "Entering...", moves the group to the arena and, if nobody is already fighting, starts a fresh run straight into wave 1. The first shop comes after wave 1.
- **Run setup screen (`RunSetupUI.luau`):** a full-screen, blurred overlay that hides the lobby HUD. **Map step:** big map name, map dots and < > arrows (or the arrow keys), a 0→20 wave track with ELITE 5 / HORDE 10 / ELITE 15 / BOSS 20 filled to your best wave, and reward tiles (keys per 5 waves, first-win keys, Endless). **Class step:** class cards with owned classes first, names centred, and locked classes dimmed with a drawn padlock and "LOCKED" (buy/earn options in the details panel). It also has the starting-weapon grid, and OPEN/SOLO for the host. Stepping onto a pad ends in START/READY, PLAY away from the pads ends in START (the server claims the first empty pad and moves the player onto it), and LOADOUT (and the Collection stand) ends in CONFIRM. The old Play and Loadout windows were removed.
- **Difficulty and backdrop (2026-09-27, queue-screen session):** the map step has Normal / Hard / Nightmare tabs (`RunSetupRules.Difficulties`; Hard needs a Normal win, Nightmare a Hard win, the next map a Hard win). START sends ('Start' or 'Play', map, class, weapon, solo, difficulty); the server validates the tier, stores it on the pad (`Difficulty` attribute, shown on the pad sign) and sets `RogueliteCombat.RunDifficulty`/`RunMap` when the group starts a fresh run. `RogueliteZombieChase` multiplies enemy health/damage, and `RogueliteMeta` multiplies keys and records wins as `PineValley/Hard`. Both steps show the map's mini island behind the screen (`MapSelectBackdrop.luau` → ReplicatedStorage), with a lighter shade; without installed islands it falls back to the old blur.
- **Locked maps (2026-09-27):** a locked map's island is a near-black silhouette (a solid-fill `Highlight` per island, `LockedSilhouette`) against a lightly greyed sky, and the difficulty/reward rows are replaced by a big padlock, LOCKED and the unlock rule. Every padlock (difficulty tabs, class cards, Armory cards) is the `UITheme` `lock` image from `build_assets.py`. Studio backup: `ServerStorage.BeforeLockedMapSilhouette_20260927`. Verified in Studio Play (single client): Beach Cove renders as a black silhouette with LOCKED + WIN PINE VALLEY ON HARD and NEXT disabled; Pine Valley shows the brass padlocks on HARD/NIGHTMARE; console clean.
- **Stands:** each stand's E prompt and walk-up point sits on the front edge of its counter, centred, at chest height. Walking within 5 studs in front of it opens the stand's window once; it opens again after you walk 10+ studs away. `lobby/FixStations.luau` re-aligns a stand's hidden rig (Collision, name sign, pivot, Interaction) to its visuals after a hand move or rotation. It also snaps lantern lenses onto their posts. Re-run it after moving stands. `ApplyPropCollision.luau` makes lobby scenery solid (fences use Box collision, since their knee-high rail can be stepped over) and adds no-climb boxes for arena rocks and logs. Backups are in `ServerStorage.BeforeStationFix`, and each prop's original collision is stored in its `CollisionBefore` attribute.
- **HUD:** the left tracker says QUESTS (was GOALS) and the right button says REWARDS (was AWARDS). All `T.window` modals get a 22 px margin on every side and can scale up to 1.15× on large screens. Content layouts are unchanged.
- Players standing in the lobby do not count toward the arena's "everyone ready" check (`ShopService.living`).

Verified in single-client Play (second pass): walking onto pad 2 opened the map step at full size. NEXT led to the class step (order Brawler, Gunner, Mage, then locked Thrower, Juggler, Handyman with padlocks). START closed the screen, and the server started the countdown ("Pine Valley · Starting in 9s" on the pad and banner). Launch arrived in the arena with the pad back to Idle. Walking to the Collection stand's front opened the class step in Loadout mode. The screenshots show the red ring and fading light column. The console was empty. `QueueState` rules (host, start permission, solo, full-pad 3 s, lock, host handover, 60 s release) were checked in the command bar. Not tested: a second real client as a member (READY) or host handover, the Solo toggle through the UI, touch/controller, and dying in the lobby.

## Lobby (`LobbyUI.luau` + `RogueliteLobbyHUD.client.luau`)

Replaces the text-only `RogueliteLobbyNavigation` preview (which still described removed Workshop/Universal Parts/cases). Visible while the server sets `LobbyPreviewActive`. Profile chip (avatar headshot), party button, keys and gems, a goals tracker, STORE/AWARDS/SETTINGS on the right and CHESTS · ARMORY · PLAY · LOADOUT · QUESTS along the bottom. World stations open the same windows (Collection→Loadout, Workshop→Armory, Rewards→Chests, Quests, Store). Keys: L loadout, C chests, J quests, Esc/B closes.

- **Play:** five-map ladder with unlock rules, Solo/Party, loadout summary with Change, and FIND A PORTAL, which draws a lime guide beam to the nearest open queue pad. A top banner shows the joined portal and a LEAVE button (server `workspace.RogueliteLobby.LeaveQueue`, no arguments, removes only the caller).
- **Loadout:** six classes (locked ones show their achievement), live class buffs, the six home weapons with copy/tier progress, armor slot (no sets yet). Confirm stores `LoadoutClass`/`LoadoutWeapon` as session attributes; server-side loadout validation is not built.
- **Chests, Armory, Quests/Achievements, Store, Profile, Party, Settings** as described in PROGRESSION_AND_SESSION_FLOW.md and MONETIZATION_AND_REWARDS.md. Nothing grants rewards or purchases: chest opening is disabled, store offers read COMING SOON, daily/weekly quests show that they start with saving.

Saved progression contract (for a future profile service; none exists yet): `ProfileLoaded=true`, `ProfileKeys`, `ProfileGems`, `ProfileClasses` (`Brawler,Gunner`), `ProfileCopies` (`00:3,01:1`), `ProfileBestWaves` (`PineValley:12`), `ProfileMapWins` (`PineValley`). Without `ProfileLoaded` the lobby shows a fresh account (Brawler/Gunner/Mage and their signature starters) marked PREVIEW.

## Verification (Studio, single client, 2026-09-27)

Both Rojo builds pass; every changed file parses (StyLua). In Play: HUD, shop, level-up (client-local sample snapshot), settings, lobby HUD and all nine lobby windows rendered; Play → FIND A PORTAL drew the beam; a real E-press on pad 2 queued (banner `PORTAL 2 · 1 / 4`) and LEAVE removed the player server-side (pad count back to 0); console stayed empty. `RogueliteLobbyPreview` remains **disabled** in the place as found — it was enabled only inside the test session. Not tested: multiple real clients, touch/controller input, the Roblox invite prompt, phones below 640 px. The repo `CharacterStatsUI` (mob picker) is newer than Studio and needs the repo `CharacterService` plus a sandboxed `EnemyCatalog`; Studio keeps its previous copy until those are synced. Backups of every replaced script: `ServerStorage.BeforeGreenThemeHUD_20260927`.

## Verification: pad lock, wave 1 first, boss bar, skill tree rings (Studio, single client, 2026-09-28)

After the Studio sync, all six scripts matched the repo byte-for-byte (LF). The combat Rojo project builds, and every changed file parses (StyLua). In Play (Combined role):
- **Pad lock:** the character was queued on pad 1 as host. Walking outward at full speed for 2 s peaked at 7.40 studs from the centre (the limit), and a teleport 4 studs past the edge snapped back to 7.40. It stayed queued. After LEAVE it walked 34 studs away and did not rejoin.
- **Wave 1 first:** a solo START on Pine Valley landed in the arena after 4.4 s in phase `Combat`, wave 1, with 29 s on the clock. Enemies were on and the shop menu was closed. When wave 1 ended, level-up and the shop opened for wave 2.
- **Boss bar:** a practice Hammer boss (1800 HP) showed the bar at bottom centre, 700×96 on a 1574×735 viewport, reading HAMMER BRUTE, 1800 / 1800. At 60% HP the fill dropped and the orange trail drained behind it. Removing the boss hid the bar.
- **Skill tree:** a test copy opened with 0 ripple frames during the opening animation.
- The console had no script errors.

Not tested: multiple real clients on one pad (each client holds its own player; the server check covers everyone), touch and gamepad movement against the ring, and a real wave-20 boss.

# Character stat editor update — September 17, 2026

Stats / Test [P] and the Stats menu tab open the server-owned character editor. It exposes all 45 stat attributes, six classes, suggested weapon builds, healing/damage controls and zombie-count buttons (0–100). The Shop sidebar displays the complete live stat list in a scroll panel. Shop Discount is labeled inactive; non-weapon items and purchasing remain outside this feature. See [implementation and verification](../combat/CHARACTER_STATS.md). Earlier notes about unavailable combat-stat dashes are superseded.

# Live weapon inventory update — September 17, 2026

The Inventory button, I key, and Inventory tab open all 36 reviewed weapon models. Select a numbered slot, then Equip; Remove clears that slot. Weapons (x/6) reflects server state in both Inventory and Shop. Equipping is free, allows duplicate weapons, and is restricted on the server to living players in Studio Practice. The Shop and Upgrades offer cards remain presentation previews. See ../combat/LOADOUT.md for implementation and current test results. WeaponInventoryUI.luau maps to ReplicatedStorage.WeaponInventoryUI. The following notes describe the original HUD/preview slice.

# Roguelite health HUD and UI previews

Targets the separate `roguelite` place 107877054949326. Do not sync the root CopyTheScene Rojo project into this place.

## Runtime mapping

- `RogueliteUI.luau` → `ReplicatedStorage.RogueliteUI` (ModuleScript).
- `RogueliteHUD.client.luau` → `StarterPlayer.StarterPlayerScripts.RogueliteHUD` (LocalScript).

These are first-party presentation scripts. Install through the Studio script editor/tool so normal first-party script capabilities apply; do not create sandboxed script containers lacking the avatar/UI permissions they need.

## Behavior

The HUD binds to the local character's actual Humanoid Health and MaxHealth. HealthChanged, MaxHealth, death, and character lifecycle events update its numeric display, smooth fill, damage trail, and low-health warning. Event connections are removed when the character changes. It neither sets health nor exposes a damage remote. Default Roblox health UI is suppressed to avoid duplication.

XP and gold are intentionally absent. Until a run service exists, the timer displays `--:-- / PRACTICE`. A future server may provide a `ReplicatedStorage.RogueliteRunState` instance with numeric `WaveEndsAt` (server time), numeric `Wave`, and string `Phase` attributes. The HUD computes countdown display from `Workspace:GetServerTimeNow()`; it does not advance waves.

**UI Preview** appears only in Studio. It opens level-up and shop previews. Choose/Inspect provides local selection feedback, Hold keeps shop cards in place during preview rerolls, and reroll rotates sample offers. Back to game closes either menu. No upgrade, item, weapon, currency, XP, or reward is granted. The example values are reference art copy, not approved balance. Stats display actual max HP and movement speed, with unavailable combat stats shown as dashes. Item/weapon slots are empty until authoritative inventory is connected.

Closing a preview hides the overlay, clears controller UI selection, restores the current character Humanoid as camera subject, sets the normal Custom camera, and releases the mouse. The close button is modal only while its menu is visible so first-person players can use the cursor. Menus do not pause multiplayer simulation. Death/respawn closes them.

Layouts respect CoreUISafeInsets and device clipping. Menus reflow from desktop rows to two/single-column scroll layouts; actions remain in a fixed footer. Source images are nine-sliced so borders keep their shape as panels resize. Desktop and mobile test evidence is tracked in `VALIDATION.md`.

## Assets and reproducibility

Run `python build_assets.py` with Pillow to reproduce the editable SVG and PNG artwork. Sources are original vector drawings based on the supplied visual direction. Uploaded image IDs and reference provenance are recorded in `../ASSETS.md`. The local HTTP server used for uploading is not a game dependency.

## Chest screen (2026-09-28)

`ChestScreenUI.luau` (full screen, replaces the old Chests window; `LobbyUI` builder `Chests`, key C,
the Rewards station and the bottom CHESTS button all open it), `ChestStage.luau` (camera, world
labels, opening steps on the chest island) and `ChestFX.luau` (auras, shakes, lid, burst; textures
and sounds). All three are client-only presentation; buying and rolling happen in ProfileService.
Design and flow: `../../STORE_AND_CHESTS.md` ("Built 2026-09-28"). Needs the chest island
(`../lobby/InstallChestIsland.luau`); without it the screen still works over a dimmed lobby.
Studio test hook: `PlayerGui.ChestScreen.TestChest:Fire(cmd, arg)` with cmd `Open`, `Select`,
`SetAmount`, `Begin`, `Advance`, `Claim` or `Close`.
