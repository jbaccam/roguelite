# Handyman turret

Added 2026-10-03. User: "make Handyman able to build a turret … that can be upgraded, and implement it into the game so it's balanced."

**Status (2026-10-04): installed in Studio, not play-tested with the models yet.**
- Scripts synced 2026-10-03. `TurretTests` passed in Edit (114 checks). In Play, admin Give refused cleanly ("models are not installed") before the import.
- The four FBX files went through Import 3D (Import Queue, Studio Default, creator EggaRowls = the game owner). The importer read the FBX's centimetres as studs, so every part came in exactly 100× (T1 base 205 studs instead of 2.05). Each model was scaled by exactly 0.01 about its pivot; that is a unit fix, not a re-scale of the art.
- `InstallHandymanTurret` then reported all four tiers `ok`: scale fix 1.000, turn (0,0,0), fit error 0, muzzles 1/2/4/6. Templates: `ReplicatedStorage.RogueliteCombat.HandymanTurrets.T1-T4`. The colour maps came in as TextureIDs.
- Icons uploaded: `H.Icons` holds `previews/icon_T1-4.png`.
- Turrets turn on at the next server start (Play).

**2026-10-04: mobs can break it** (user: "lets let mobs destroy it"). Done in the repo only. It is not synced to Studio, no Studio tests have run, and it has not been play-tested. See [Health and breaking](#health-and-breaking).

## How it plays

- **Handyman only.** It is a class ability, not a weapon slot. The class description now says so.
- **Built for you.** When a wave (or the admin sandbox) starts and you have no turret, one is built 3.5 studs in front of you, on the ground, facing where you face.
- **BUILD moves it.** Press **B** (keyboard), **R1** (gamepad) or the on-screen **BUILD** button, and the turret is rebuilt where you stand. Then BUILD waits **8 s**.
  - The button shows the turret, its key and the seconds left.
  - With a keyboard or gamepad it sits in the bottom-right corner, left of the melee DASH button. On touch screens it sits just above the jump button.
  - It moves out of the way of the HUD's menu column and the boss bar.
  - Taken keys it avoids: Q / pad X (dash), E / pad Y (revive), P (pause), pad B (back).
- **It shoots by itself.** It fires nails at the nearest enemy in range that it can see. The head turns toward its target, the barrel pitches, kicks back on each nail, and shows a flat muzzle flash. Tier IV's six-barrel cluster spins.
- **Each nail counts as yours.** Nails go through the normal damage path, so these all count for you:
  - crits, burn, poison, slow and lightning from your items
  - kill credit and crystals
  - run contribution and the "damage by source" analytics (source `Turret`)
  - the `utilityKills` quest stat
- **Mobs can break it** (below). It doesn't block enemies or players.
- **It holds fire** between waves, while the run is paused, during a boss entrance, while you are down, and when your weapons are switched off.
- **It goes away** when you leave the run (lobby, results, disconnect), when the run resets, or if you end up 500+ studs from it (another arena). It never shows in the lobby.
- **Multiplayer:** each Handyman has their own turret.

## Health and breaking

Added 2026-10-04. All the numbers are in `HandymanTurret.luau` (`HEALTH`, `HEALTH_PER_WAVE`, `HEALTH_TIER`, `REBUILD_DELAY`, `LOW_HEALTH`), so they are easy to retune once the turret's cost is decided.

### Health

- **Formula:** Tier I has 60 + 15 per wave after the first. Each tier above I multiplies that by 1.5.
- **Gear power:** it also gets the owner's gear power health share (+6% per point above 1), like the owner's own max health. A later map's mobs hit harder by exactly that share (`RunSetupRules.enemyScale`), so the turret lasts as long there. A fresh account in Pine Valley gets the table below unchanged.
- **Armour:** the owner's Armor and Contact resistance cut each hit, as they do for the player (`CharacterStats.incoming`). Example: 11 damage with 5 armour is 11 / (1 + 5/15) = 8.25.
- **No player-only defences:** dodge, the first-hit block, the pet shield and the zombies' shared 0.3 s swing gap don't protect it.
- **No regeneration** during a wave. Every wave starts it at full health for that wave, like players (`ShopService` refills them).

| Tier | Wave 1 | Wave 5 | Wave 10 | Wave 20 |
|---|---|---|---|---|
| I | 60 | 120 | 195 | 345 |
| II | 90 | 180 | 293 | 518 |
| III | 135 | 270 | 439 | 776 |
| IV | 203 | 405 | 658 | 1,164 |

Tier I takes about 11 hits from a regular zombie of the same wave (5 + 1.5 damage per wave, one hit every 0.8 s):

| Wave | Zombie hit | Hits to break | One zombie | Three | Ten |
|---|---|---|---|---|---|
| 1 | 5 | 12 | 9.0 s | 3.2 s | 1.0 s |
| 5 | 11 | 11 | 8.2 s | 2.9 s | 0.9 s |
| 10 | 18.5 | 11 | 8.2 s | 2.8 s | 0.8 s |
| 20 | 33.5 | 11 | 8.2 s | 2.7 s | 0.8 s |

So it holds a few seconds against a small group, and a swarm breaks it in about a second.

### Who attacks it

- **Wave mobs whose nearest target it is.** A mob picks the turret when the turret is closer than every living player. The distance is measured on the ground to the turret's edge, as to a body. A turret between you and a swarm soaks their hits and pulls them off you.
  - Example: a zombie 10 studs from you and 6 from your turret goes for the turret. You step to 5 studs from it, and it comes back to you.
  - Several turrets and several players work the same way: the mob picks the nearest of all of them.
- **Melee mobs** walk to its edge and use their normal swing, with the same reach, arc and damage as against a player.
- **Lunging mobs** (snake, scorpion) dash at it.
- **Ranged mobs** (spitter, rock crab, bow skeleton…) stop at their range and shoot it. A shot aimed at the turret can still hit a player who steps in front of it.
- **The Mutant's slam** hits every standing turret inside its ground circle, whoever it was aimed at.
- **Bosses don't hit it yet.** Their attack code (`combat/bosses/`) was mid-remodel. Adding it later means one loop over `HandymanTurret.posts` in each boss hit test, like the Mutant's.
- **Other attacks don't hit it:** a swing or shot aimed at a player, and body bumps.

### Breaking and rebuilding

- **At 0 HP it breaks:** the model goes with a short flat burst (an orange ground ring, amber sparks, a dust puff, all gone in half a second) and a crunch (the thud and blunt hit pitched down, with a shotgun crackle). Nothing is left behind. It stops firing and is no longer a target.
- **BUILD again:** 5 s after the break, or sooner if its own 8 s cooldown ends first (`H.rebuildAt`). Building puts a fresh full-HP turret where you stand, and starts the usual 8 s cooldown.
  - Examples: broken 1 s after a move → BUILD in 5 s, not 7. Broken 4 s after a move → BUILD in 4 s. Not moved recently → BUILD right away.
- **The next wave** rebuilds a broken turret at your position, like the wave-start build.
- **BUILD on a standing turret** still moves it, and it keeps its damage. Moving isn't a repair.

### What you see

- **Health bar:** a small bar (58 × 10 px, the same size on phones) over each turret. It is lime, and red under 30%.
- **Hit flash:** each hit flashes the bar and the model white for 0.1 s.
- **BUILD button:** while the turret is broken and can't be rebuilt yet, the button turns charcoal, reads **BROKEN** in red, greys the turret icon and counts down the seconds. When it can be rebuilt, it is lime **BUILD** again with the ready pop.

### Balance effect

- **Less damage in a swarm.** The turret used to add about +8% damage at best (see Balance). Now a swarm that reaches it breaks it in about a second. It then does nothing until you rebuild it (5–8 s) or the next wave starts. Placed in the open with a swarm on it, it loses most of that uptime.
- **A decoy.** In exchange, each turret's life soaks about 11 hits that would have been aimed at the Handyman. At wave 10 a Tier I turret absorbs 195 damage, about twice a fresh Handyman's 90 HP, and pulls mobs off you while it lasts.
- **Placement matters.** The best place is between you and the swarm, or where mobs reach it one or two at a time. Upgrades now also make it tougher (×1.5 health per tier).
- **No trim to the class.** Check this in play-tests before changing the numbers. The usual levers are `HEALTH` and `REBUILD_DELAY`.

## Numbers

The turret counts as a ranged Handyman Utility weapon. Every bonus a Nail Gun gets also applies to it: Damage, Ranged damage, Utility Power, the Handyman's own-class +15%, Attack speed, Cooldown reduction, Attack range and Projectile speed. Extra projectiles, Pierce and Bounce also apply, through the shared rule `CharacterStats.usesStat`, so the turret is a bullet weapon there.

Its tiers step like the weapons' (`WeaponCatalog.TierGrowth` and `TierCooldown`): damage ×1.4 per tier, cooldown ×1 / 0.9 / 0.8 / 0.7.

The table shows each tier before character bonuses. "vs ranged" compares it with the average class ranged weapon at the same tier (22 weapons, Godly left out, single target, after the 2026-10-03 melee vs ranged pass).

| Tier | Damage per cycle | Cooldown | DPS | Nails per cycle | Pierce | Range | vs ranged |
|---|---|---|---|---|---|---|---|
| I | 4 | 0.80 s | 5.0 | 1 | 0 | 25 | 45% (avg 11.2) |
| II | 6 | 0.72 s | 8.3 | 1 | 1 | 25 | 48% (avg 17.2) |
| III | 8 | 0.64 s | 12.5 | 1 | 1 | 25 | 46% (avg 27.4) |
| IV | 11 (3 × 3.67) | 0.56 s (a nail every 0.187 s) | 19.6 | 3 | 2 | 25 | 46% (avg 43.2) |

- **Tier IV is a gatling.** Each cycle fires 3 nails, each a third as strong, one third of the cooldown apart. Each nail goes at the nearest enemy at that moment with a ±3° spray. The damage per second is the same; it just covers a crowd better.
- **Range: 25 studs.** That is shorter than the class ranged weapons' average (28.8) and the Nail Gun's (30), both after the ranged range cut.

### Upgrades

You buy upgrades in the run shop between waves. **UPGRADE TURRET** sits above LEAVE RUN, for Handymen only, and reads like `TURRET → II · 32` with the crystal icon.

- **Price:** each step costs what one more weapon copy of your current tier costs, because combining two copies is how a weapon steps up a tier. That is the middle of the tier's weapon price band: **18 / 42 / 77** for II / III / IV.
- On top of that come the shop's usual wave inflation and your discounts (`EconomyConfig.price`).
- The tier belongs to the run: a new run starts at Tier I, and a rejoin keeps it.

| Upgrade | Base | Wave 3 | Wave 5 | Wave 8 | Wave 10 | Wave 14 |
|---|---|---|---|---|---|---|
| I → II | 18 | 26 | 32 | 40 | 46 | 57 |
| II → III | 42 | 57 | 68 | 83 | 94 | 114 |
| III → IV | 77 | 103 | 120 | 146 | 164 | 198 |

### Worked example

A Handyman on wave 5 with the class buffs and two home weapons (+5% Damage, +15% Utility Power, own class +15%, 10% cooldown reduction):

- **Tier I nail:** 4 × 1.05 × 1.15 × 1.15 = **5.55** damage, every 0.8 × 0.9 = **0.72 s**. That is **7.7 DPS**, or two nails for an 11 HP wave-5 zombie.
- **Upgrade to Tier II:** 18 + 5 + 18 × 5 × 10% = **32 shards**. The nail becomes 8.33 damage every 0.648 s, which is **12.9 DPS**, and it pierces one enemy.
- **Tier IV, for comparison:** 3.67 × 1.389 = 5.09 per nail every 0.168 s, which is **30.3 DPS**.

## Balance

- **Target:** 40–50% of a ranged weapon of the same tier, and it lands at 45–48%. The turret is extra damage on top of six weapon slots, so a Handyman with six weapons gains about 0.46 / 6 ≈ **+8%** damage.
- **Only where it stands.** It covers a 25-stud circle and can only move every 8 s. When the Handyman kites away from it, it does nothing, so the real gain is lower than +8%.
- **Price:** about one weapon copy per tier. Early on, that is worse value than buying a new weapon. It is never a must-buy, but it is always offered and never needs a slot.
- **Compared with the other classes:** Gunner gets +20% ranged damage, +10% ranged attack speed and +1 projectile at four home weapons. Mage gets +25% elemental damage and +30% duration. Handyman's own buffs are the mildest offence (+5% damage, +15% to Handyman weapons only), and the turret's +8% doesn't make it clearly stronger.
- **No Handyman buff was trimmed.** If play-tests show otherwise, the first thing to trim is the class's +5% Damage.
- **Since 2026-10-04 mobs can break it,** so that +8% is now a best case, and the turret is also a decoy. See [Balance effect](#balance-effect).

## Server authority and performance

- **The server decides everything:** placement, targeting, damage, health, breaking, tier, upgrades and cooldown.
- **BUILD** is `RunAction` `BuildTurret`. No new remote; RogueliteMeta's handler ignores the action.
  - It is checked by `HandymanTurret.canBuild`: installed, Handyman (or an admin turret), run member, not in the lobby, alive, not down, phase Combat or Practice, not paused or held, off cooldown.
  - It is limited to one request every 0.25 s.
- **The upgrade** is ShopService's `UpgradeTurret` action. It is checked by `HandymanTurret.canUpgrade`: installed, Handyman, below Tier IV, enough shards, and the tier the button showed (so a stale double-click can't buy twice). ShopService's own checks also apply: shop phase, revision, rate limit, alive in the run.
- **Targeting** runs at 10 Hz. It uses one TargetGrid snapshot per tick, built only while a turret is firing, and picks the nearest allowed enemy in range with one line-of-sight ray. A boss is measured to its nearest body box, like for weapons.
- **Fire rate** keeps the turret's own clock, with at most two nails per tick, so the average rate is exact. Nothing is banked across a hold.
- **Nails** are a second `StatProjectiles` instance whose projectile keys start at 2^30, so clients never mix them up with weapon bullets. They use the Nail Gun's projectile look (`ProjectileStyleVisuals.Styles.Turret`).
- **Replication:** there are no server parts and no server CFrame writes. Each turret is a Folder in `workspace.RogueliteTurrets`:
  - `Position`, `Yaw`, `Tier`, `BuiltAt` and `ReadyAt`
  - `Aim`, written at most 5 times a second when the target moves 1.5+ studs
  - `Health` (to 0.1, written when a hit changes it), `MaxHealth`, and `Broken` (server time it broke; nil while standing)
- **Mob hits (2026-10-04):** no new remote or module, and no cross-sandbox calls. They work like this:
  - The sandboxed service keeps one plain table per turret in `HandymanTurret.posts` (`H.newPost`). It holds `Position` (the turret's middle), `Parent` (its Folder), `hp`, `pad` (its half-width past a player's 0.75) and `taken`.
  - `RogueliteZombieChase` (unsandboxed) passes that table to a mob as its target when `HandymanTurret.nearer` picks it. That is one extra line per mob per think, a loop over at most a few turrets, with no raycasts of its own.
  - `EnemyAttacks` and `ZombieAttacks` attack the table as they would a player's root. A hit only adds to `taken`.
  - Every frame the service takes `taken` off, with the owner's armour (`H.takeHit`). It drops hits between waves and while the run is held, like `CharacterService.contact`.
  - Broken or removed turrets have `hp` 0, so mobs drop them on their next think.
- **Clients** draw the models, turn the head, pitch the barrel, add recoil, spin and flashes. They skip turrets more than 250 studs from the camera, and freeze them while the run is paused.
- **Sounds** come from `RogueliteSounds`, reusing the kit:
  - each nail: the pistol pop, higher and quieter
  - a build: a thud and a metal tick
  - a tier up: the upgrade chime
  - a break: a crunch (the thud and blunt hit pitched down, a quiet shotgun crackle)

## Admin panel

The Player tab has a **Handyman turret** section, using the AdminService action `Turret`:

- **Give turret:** builds one at you now, whatever your class, for this run.
- **Tier I–IV:** sets your turret's tier for this run.
- **Break turret** (2026-10-04): your turret drops to 0 HP now, as if mobs broke it. Use it to see the burst, the BROKEN button and the rebuild.
- **Clear turrets:** removes every turret. None comes back until the next wave or that player's BUILD.

## Files

- New:
  - `HandymanTurret.luau`: rules and numbers.
  - `HandymanTurretService.server.luau`: the server.
  - `HandymanTurret.client.luau`: drawing and BUILD.
  - `InstallHandymanTurret.luau`: the Studio installer.
  - `TurretTests.luau`
  - this doc
- Edited with small hooks:
  - `ShopService` (`UpgradeTurret` and the snapshot's `turret` row) and `ShopUI` (the button)
  - `StatProjectiles` (`firstKey`)
  - `ProjectileStyleVisuals` (the nail style alias)
  - `RogueliteMeta` (`utilityKills`)
  - `RunAnalytics` (the `Turret` source name)
  - `RogueliteSounds`
  - `AdminConfig`, `AdminService`, `AdminPanelUI`
  - `CharacterStats` (the Handyman description)
  - `default.project.json`
- Edited for mobs breaking it (2026-10-04):
  - `RogueliteZombieChase.server.luau`: a look-up of `HandymanTurret` and one `Turret.nearer` line after the nearest-player pick
  - `EnemyAttacks.luau`: a turret target can start an attack (reach + pad); swings, lunges and shots aimed at it can hit it (`hitTurret`)
  - `ZombieAttacks.luau`: the Mutant slams a turret target, and a slam hits every turret in its circle
  - `RogueliteSounds` (the crunch), `AdminConfig` and `AdminPanelUI` (Break turret)

## Studio steps (each needs the user's okay)

1. **Import:** File > Import 3D, default settings, scale 1:1, for `blender-handyman-turret/exports/fbx/HandymanTurret_T1.fbx` … `T4.fbx`.
   - Upload `textures/HandymanTurret_T{n}.png` if the import has no colour map.
   - Upload `previews/icon_T{n}.png` and paste the four ids into `HandymanTurret.Icons`. Until then the BUILD button shows a live view of the model.
2. **Install:** run `InstallHandymanTurret.luau` (its header has the command). Pass `{textures = {...}}` if you uploaded the textures.
   - It matches each part to the spec's centres and sizes with a 90° turn search, and refuses an import more than 15% off size.
   - It sets the Head, Barrel and Glow pivots from the spec, the Muzzle attachments from `muzzlesFromBarrelPivot`, and T4's `MuzzleCentre`.
   - Check that every line of its report says `ok`.
3. **Sync scripts:** `HandymanTurret` must be in RS.RogueliteCombat **before** the new ShopService, though ShopService still loads without it.
   - New ModuleScript `ReplicatedStorage.RogueliteCombat.HandymanTurret`: **Sandboxed = true, Capabilities copied from CharacterStats** (ShopService requires it).
   - New Script `ServerScriptService.HandymanTurretService`: **Sandboxed = true, Capabilities copied from SSS.RogueliteCombat**.
   - New LocalScript `StarterPlayer.StarterPlayerScripts.HandymanTurret`: unsandboxed, like PetVisuals.
   - Then sync the edited files listed above. AdminConfig and AdminService go together: AdminService asserts that every action has a handler.
4. **Tests (Studio Edit, no Play):** `TurretTests(HandymanTurret, TargetGrid, WeaponCatalog, CharacterStats, EconomyConfig)`. The call is in its header.
5. **Play-test (the user):**
   - A Handyman run: the turret appears at wave 1, BUILD moves it with an 8 s cooldown, and the shop button upgrades it.
   - Tier IV spins.
   - Pause freezes it.
   - Another class gets no button.
   - Phone layout: BUILD above the jump button, clear of DASH.

**For the 2026-10-04 breaking change**, sync `HandymanTurret`, `HandymanTurretService`, the `HandymanTurret` LocalScript, `TurretTests`, `EnemyAttacks`, `ZombieAttacks`, `RogueliteZombieChase`, `RogueliteSounds`, `AdminConfig` and `AdminPanelUI`. All of them already exist in Studio, so their Sandboxed settings stay as they are. `HandymanTurret` must load before the chase script uses it, but the chase only looks it up, so a missing one just means mobs ignore turrets. Then:
- **Tests:** re-run `TurretTests` in Edit. `EnemyShotTests` should still pass, because the stubs have no turret.
- **Play-test (the user):**
  - Admin panel > Player > Give turret, and stand behind it with mobs coming. They should go for the turret, the bar should drop and flash, and it should turn red under 30%.
  - Let it break: you should see the burst and hear the crunch, and the button should read BROKEN with a 5 s countdown. BUILD then puts a fresh full-HP turret at you.
  - **Break turret** does the same without waiting for mobs.
  - The next wave rebuilds a broken turret.
  - A spitter shoots it, and a Mutant's slam hits it.
  - Tier IV has 1.5³ ≈ 3.4× Tier I's health.

## Not done / judgment calls

- **Gamepad R1, keyboard B.** Pad X went to the dash. R1 is otherwise only the death screen's spectate cycle, and BUILD is hidden while you are dead.
- **Ranged damage and attack speed apply,** not only Utility Power. The turret is treated as a ranged Utility weapon, so there is one shared calculation.
- **Stat items count for it,** but the shop's "Works with" line on item cards lists only carried weapons, so it doesn't name the turret.
- **No second turret at Tier IV.** The gatling fits the spinning barrel model and keeps one turret per player.
- **Knockback** from items pushes enemies away from the owner, not from the turret (shared CombatEffectsService code). The turret has no knockback of its own.
- **`AdminConfigTests` was already stale:** it expects 15 actions, and the place had 18 before `Turret`. It wasn't updated here.
- **Breaking (2026-10-04):**
  - **Gear power share added** to the requested formula, so a later map's mobs, which hit harder by that share, don't break it faster than Pine Valley's.
  - **Not scaled by difficulty or Endless.** On Hard (×1.3 enemy damage) or past wave 20 (Endless damage, ×1.6 at wave 30), it breaks sooner, the same as players feel it.
  - **The zombies' shared 0.3 s swing gap is a player-only defence,** so a ring of zombies hits the turret with every swing.
  - **Only area attacks hit it collaterally** (the Mutant's slam). A swing or shot aimed at a player doesn't hit a turret beside them.
  - **Bosses don't hit it yet,** because `combat/bosses/` was mid-remodel.
  - **Admin God protects you, not your turret,** so you can watch it break while testing.
  - **Moving keeps its damage,** and every new wave refills it. A broken one is rebuilt at full HP.
  - **The health state lives on each turret,** not the player, and mob targeting takes any number of turrets. This is so a later "several turrets per player" (Turret Kit) carries over.
