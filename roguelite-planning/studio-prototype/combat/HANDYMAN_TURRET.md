# Handyman turret

Added 2026-10-03. User: "make Handyman able to build a turret … that can be upgraded, and implement it into the game so it's balanced."

**Status: repo only.** Nothing has been synced to Studio, and no Studio test or Play test has run. The turret models are made (`roguelite-planning/blender-handyman-turret`) but not imported. Until they are installed the whole feature stays off: no turrets, no BUILD button, no shop upgrade, and one warning in the server output.

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
- **It can't be destroyed,** and it doesn't block enemies or players.
- **It holds fire** between waves, while the run is paused, during a boss entrance, while you are down, and when your weapons are switched off.
- **It goes away** when you leave the run (lobby, results, disconnect), when the run resets, or if you end up 500+ studs from it (another arena). It never shows in the lobby.
- **Multiplayer:** each Handyman has their own turret.

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

## Server authority and performance

- **The server decides everything:** placement, targeting, damage, tier, upgrades and cooldown.
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
- **Clients** draw the models, turn the head, pitch the barrel, add recoil, spin and flashes. They skip turrets more than 250 studs from the camera, and freeze them while the run is paused.
- **Sounds** come from `RogueliteSounds`, reusing the kit:
  - each nail: the pistol pop, higher and quieter
  - a build: a thud and a metal tick
  - a tier up: the upgrade chime

## Admin panel

The Player tab has a **Handyman turret** section, using the AdminService action `Turret`:

- **Give turret:** builds one at you now, whatever your class, for this run.
- **Tier I–IV:** sets your turret's tier for this run.
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

## Not done / judgment calls

- **Gamepad R1, keyboard B.** Pad X went to the dash. R1 is otherwise only the death screen's spectate cycle, and BUILD is hidden while you are dead.
- **Ranged damage and attack speed apply,** not only Utility Power. The turret is treated as a ranged Utility weapon, so there is one shared calculation.
- **Stat items count for it,** but the shop's "Works with" line on item cards lists only carried weapons, so it doesn't name the turret.
- **No second turret at Tier IV.** The gatling fits the spinning barrel model and keeps one turret per player.
- **Knockback** from items pushes enemies away from the owner, not from the turret (shared CombatEffectsService code). The turret has no knockback of its own.
- **`AdminConfigTests` was already stale:** it expects 15 actions, and the place had 18 before `Turret`. It wasn't updated here.
