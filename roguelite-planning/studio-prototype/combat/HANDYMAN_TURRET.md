# Turrets (turret items and the Engineer Handyman)

**Later October 4 correction:** placement now projects edge/corner players toward useful interior ground, uses arena height instead of jump height, and rejects spots with no verified floor. The ring/count/item rules below remain; references to an airborne fallback or a ring centered exactly on a rim player are superseded. See [combat feedback corrections](PLAYTEST_COMBAT_FIXES_2026-10-04.md).

**2026-10-03:** the Handyman got a nail turret: one per Handyman, moved with BUILD, upgraded in the shop.

**2026-10-04: turret items.** It is now Brotato's turrets. Design: [plans/2026-10-04-turret-items-engineer-design.md](../../plans/2026-10-04-turret-items-engineer-design.md); plan: [plans/2026-10-04-turret-items-engineer-plan.md](../../plans/2026-10-04-turret-items-engineer-plan.md). The user asked:
- "make the turrets scale in the amount of them and don't have the player place them, let them be automatically placed";
- "take direct inspiration from Brotato";
- "let's not let mobs destroy the turrets";
- "I don't want to make more turret models".

**Status:** done in the repo only. It is not synced to Studio, no Studio tests have run, and it has not been play-tested.

**What changed on 2026-10-04:**
- **Removed:**
  - BUILD: B, R1, the on-screen button and RunAction `BuildTurret`;
  - the automatic one turret per Handyman;
  - the shop's UPGRADE TURRET (ShopAction `UpgradeTurret`);
  - the admin Give / Tier I–IV / Break buttons.
- **Turrets can't be destroyed again.** The layer commit 9f6e956 added is gone:
  - turret health, the HP bar, the hit flash, the break burst and crunch, and BROKEN with its rebuild;
  - mobs targeting turrets (`HandymanTurret.posts / nearer`, and the turret branches in `RogueliteZombieChase`, `EnemyAttacks` and `ZombieAttacks`).

  Those three mob scripts are back to their text before 9f6e956.
- **No new models:** the four items use the existing T1–T4 templates.

## How it plays

- **Turrets are shop items.** Each copy you own is one more turret. Any class can buy them.

| Item | Item tier | Model | Each cycle | Cooldown | DPS | Pierce | Base price |
|---|---|---|---|---|---|---|---|
| Nail Turret (`turret_nail`) | I | T1 | 4 | 0.80 s | 5.0 | 0 | 24 |
| Twin Nailer (`turret_twin`) | II | T2 | 6 | 0.72 s | 8.3 | 1 | 46 |
| Quad Nailer (`turret_quad`) | III | T3 | 8 | 0.64 s | 12.5 | 1 | 85 |
| Gatling Rig (`turret_gatling`) | IV | T4 | 3 nails of 3.67 | 0.56 s | 19.6 | 2 | 150 |

- **Placed for you at every wave start, on a ring around you:**
  - The ring is 8–14 studs out, or 4–8 for a Handyman.
  - The turrets are at even angles with a little jitter, and at least 5 studs apart.
  - Each one faces where you face.
  - The first spot is straight ahead of you.
- **During a wave they follow you** (2026-10-10, see [Follow](#follow-2026-10-10)): a turret you leave out of its range packs into the ground and rebuilds ahead of you.
  - Turrets added mid-wave (the admin panel, Scrap Magnet) go to free spots on a ring around where you are then.
  - Items you buy in the shop show up at the next wave start.
- **Ground:**
  - Each spot is ray-cast down to solid, fairly flat floor within 4 studs of your feet, inside the arena circle (the spawn marker's `SpawnAreaCenter` / `SpawnAreaRadius`), with a clear line from you.
  - If a spot fails, it tries half as far out, then your own spot.
  - Example: a ring spot 12 studs out over a cliff edge becomes 6 studs out on the same line.
- **They shoot by themselves.**
  - Each fires nails at the nearest enemy in range that it can see.
  - The head turns toward its target, the barrel pitches, kicks back on each nail, and shows a flat muzzle flash.
  - The Gatling Rig's six-barrel cluster spins.
- **Each nail counts as yours:**
  - kill credit and crystals
  - run contribution and the "damage by source" analytics (source `Turret`)
  - the `utilityKills` quest stat
  - your status items (see Numbers)
- **They can't be destroyed,** and they block nothing: mobs and players walk through them. Mobs ignore them.
- **They hold fire** between waves, while the run is paused, during a boss entrance, while you are down, and when your weapons are switched off.
- **They go away** when you leave the run (lobby, results, disconnect) or the run resets. If you end up 500+ studs from them (another arena), they are placed around you again. They never show in the lobby.

## Follow (2026-10-10)

The user asked: "There should be disassemble and reassemble animations for turrets going down and rebuilding as they follow the Handyman around. They should rebuild when he moves outside of their attack range. Make grey smoke animations and make it come out of the ground or something, like it's being assembled." Before this, turrets never moved mid-wave. Design: [plan §1.5](../../plans/2026-10-10-playtest-abilities-sniper-items-plan.md#15-handyman-turrets-handyman-only-and-they-follow-him).

**Status:** built in the repo only. Pure rules tested outside Studio (`run_turret_tests.py`). Not synced to Studio, no Play test.

**Rules** (server, `HandymanTurretService`; numbers in `HandymanTurret`):
- **Left behind:** mid-wave, a turret whose owner is farther than its range (25 studs, measured flat) packs up. Range is the turret's real range from `HandymanTurret.weapon`; Attack range doesn't stretch it.
- **Pack:** 0.35 s (`PACK_TIME`), no fire. Then it **rebuilds**: 0.5 s (`BUILD_TIME`), no fire. Each move is 0.85 s offline.
- **Where it lands:** a free spot on the band's outer edge (8 studs for a Handyman, 14 for others), 5+ studs from the turrets standing. The ring is centred on you, led along your run by 0.25 s of your speed (at most 6 studs), and the spot nearest your heading is tried first. Standing still, it uses your facing. Same ground and sight checks as every placement. With no ground found it stands back up where it was.
- **Limits:** at most 2 of a player's turrets moving (packing or rebuilding) at once (`FOLLOW_AT_ONCE`), the farthest first. Each waits 1.5 s after it lands before it can move again (`FOLLOW_COOLDOWN`). Scrap Magnet's temporary turrets follow the same rule.
- **Not moving:** between waves, while the run is paused, and before the wave's placement. A turret caught packing when the wave ends stands up near you. The 30-turret server cap, the 10-per-player cap and the 500-stud re-place are unchanged.
- It keeps its Folder and Index, so clients re-pose the same turret.

**Example:** you run straight at 24 studs/s with 5 turrets. A turret 25+ studs behind packs, and 0.35 s later lands about 8 + 6 = **14 studs ahead** of where the server sees you (the server sees players ~0.2 s late, so about 9 ahead of you). It is offline 0.85 s. Only 2 move at once, so **at least 3 of 5 fire** while you run, and all 5 once you stop.

**Replication** (no new remotes): `PackAt` (server time it started packing) is set on the turret's Folder. The rebuild clears it and writes the usual `Position`, `Yaw` and `BuiltAt`.

**What you see** (`HandymanTurret.client`; flat painted effects through `VfxKit`, counts × ClientQuality):
- **Pack (0.35 s):** the barrel folds down, the head drops onto the base, then the head and the base shrink and sink into the ground. Grey smoke puffs (the `SmokePuff` flipbook) burst out at the base, with a grey dust ring (`ShockwaveRing` decal) spreading on the ground and a second small dust puff as the base goes under. Then it is hidden until the rebuild.
- **Rebuild (0.5 s):** a grey smoke column billows out of the ground with a low dust skirt and a dust ring. Then the base rises out of the ground, then the head, then the barrel snaps up, each with a small overshoot. A warm star spark (`ImpactStar`) and a few Neon sparks show as the head locks and again as the barrel locks. The head spins one turn into its aim.
- **Sound** (`RogueliteSounds`, the same kit): a quick high metal ratchet as it packs. The rebuild's clunk is delayed 0.36 s to the head lock, a little lighter and higher than a wave-start clunk.
- The wave-start placement keeps its lime ring pop.

**Files and Studio sync** (all four already exist in Studio, so their Sandboxed settings stay; no new requires in the sandboxed server script, no new remotes):
- `RS.RogueliteCombat.HandymanTurret` (ModuleScript): `PACK_TIME`, `BUILD_TIME`, `FOLLOW_AT_ONCE`, `FOLLOW_COOLDOWN`, `FOLLOW_LEAD`, `moving`, `leftBehind`, `followRing`, `followCenter`. Sync it first: both scripts below read these.
- `SSS.HandymanTurretService` (Script): `free()` (split out of `add()`), `pack`, `rebuild`, `follow`, the fire-loop skip, and `stand()` clearing `PackAt`.
- `StarterPlayerScripts.HandymanTurret` (LocalScript): the animations; it now also requires `ClientQuality`.
- `RogueliteSounds` (LocalScript): the pack ratchet and the delayed rebuild clunk.
- Tests: `TurretTests` (no Play), also `python run_turret_tests.py <luau.exe>` outside Studio.

**Not done / judgment calls:**
- The plan's 20-stud threshold became the real range (25), as the user said "outside of their attack range".
- The rebuild is 0.5 s, not the old 0.35 s pop, so the build animation can read. Wave-start placements keep 0.35 s.
- "Handyman only" for turret items (plan §1.5, first half) is not part of this change.

## Numbers

**Brotato's structure rule:** a turret's damage is its base × (1 + Utility Power).
- Example: +30% Utility Power makes a Nail Turret's nail 4 × 1.3 = **5.2**.
- **Ignored:**
  - Damage, Melee / Ranged damage, Attack speed, Cooldown reduction, Crit and Life steal;
  - the class-fit +15%;
  - Knockback (its push would start at your body, not the turret);
  - Attack range, projectile speed and size. Range is 25 studs for every turret.
- **Applied:**
  - Extra projectiles (Two Straws: +1 nail per shot);
  - Pierce and Bounce (through `CharacterStats.shotStat`);
  - burn, slow, poison and lightning procs on direct hits (burn ticks use Elemental damage but not Damage);
  - Boss damage;
  - your gear power's damage share (see the judgment calls).
- **How the server does it:** `HandymanTurret.weapon` builds the definition. Its hit stats (`turretStats`) are your stats with the ignored ones set to 0. The definition is marked `structure`, so `CombatEffectsService` never gives it the Ninja set's dodge crit and never life-steals from it.

**Balance:** each tier is 40–50% of the average class ranged weapon of the same tier (`TurretTests` checks this against `WeaponCatalog`):
- Tier I: 5.0 vs 11.2 DPS
- Tier II: 8.3 vs 17.2
- Tier III: 12.5 vs 27.4
- Tier IV: 19.6 vs 43.2

25 studs is shorter than the ranged average (28.8) and the Nail Gun's 30.

**The Gatling Rig** fires 3 nails each cycle, each a third as strong, one third of the cooldown apart, each at the nearest enemy then, with a ±3° spray. It does the same DPS but covers a crowd better.

**Worked example (Handyman, design §8):**

| Wave | Turrets | Utility Power | Turret DPS (sum) |
|---|---|---|---|
| 1 | 1 Nail (free) | +15% | 5.75 |
| 5 | 3 Nail | +30% | 19.5 |
| 10 | 4 Nail + 1 Twin | +45% | 41.1 |
| 15 | 6 Nail + 2 Twin + 1 Quad | +70% | 100.6 |

A Gunner with 2 Nail Turrets and no Utility Power gets 10 DPS.

## Items and the shop

**Prices:** the normal `EconomyConfig.price`, with wave inflation and your discounts. Example: a Nail Turret is 24 + 5 + 24 × 5 × 10% = **41** at wave 5.

**Limits:**
- 10 turrets per player. At 10 the shop stops offering turret items to you, and a buy or an admin grant is refused ("You already have 10 turrets").
- 30 turrets on the server, Scrap Magnet's included. At a wave start the 30 are shared out fairly (`HandymanTurret.share`): one each in turn, best turrets first. Example: 4 players with 10 each get 8, 8, 7 and 7. Someone arriving later gets what is left.

**Shop weighting**, like Handyman weapons: a Handyman, or anyone carrying a Handyman-class weapon, gets 15% of item offers from the structure items (the four turrets, Scrap Magnet, Toolbelt), plus the early-wave class bonus. Example: 30% on wave 1.

**Selling:** items can't be sold in this game (only weapons recycle), so turret items can't either.

**Support items:**
- **Scrap Magnet** (tier II, 40, its own red horseshoe icon `rbxassetid://119978395020560`, `ui/assets/shop/magnet.png`; it shared the Fridge Magnet's blue tile until 2026-10-10):
  - Each 40 crystals you pick up in a wave builds a temporary Nail Turret near you, up to 3 a wave per copy.
  - It counts crystals before the crystal bag's bonus.
  - Temporary turrets last until the wave ends, don't count toward your 10, and do count toward the server's 30.
  - Example: 2 copies and 130 crystals give 3 temporary turrets.
- **Toolbelt** (tier I, 18, the Utility Power level-up art): +6% Utility Power.

## Handyman = Brotato's Engineer

- **Utility Power:** +15 to start. Every Utility Power gain from items, level-up cards and set bonuses counts × 1.25.
  - Example: a +12 card gives him +15.
  - His four-weapon set bonus (+20) counts +25.
- **Damage:** positive Damage gains count × 0.5, and his +5% Damage buff is gone.
  - Example: an item with +10% Damage gives him +5%.
  - A loss (−3) isn't halved.
- **How gains work** (`CharacterStats.gained`): a class's `gain` multiplies what its set bonuses, items, level-ups, skills, armour and pets add to a stat, when that adds up to more than 0. His base and his own class buffs aren't gains.
- **Free turret:** he starts every run owning 1 Nail Turret item, which counts toward his 10.
  - Until the run starts (wave 1's shop, or the sandbox), it follows his class. A match server sets the class after the run state exists, so picking Handyman adds it and picking another class takes it back.
  - Someone who joins a run in progress as a Handyman gets it too.
- **Ring:** 4–8 studs ("structures spawn close to each other"). With 9 or 10 turrets the extras go on a second ring 5 studs further out: 8 at 8 studs, then 2 at 13.
- **Price:** structure items (the four turrets, Scrap Magnet and Toolbelt) cost him 20% less. Example: a wave-5 Nail Turret is 32, not 41.
- **Unchanged:** Area +20%, Regen +1, Max HP −10, and two home weapons' 10% cooldown reduction.
- **Class description:** "Engineer: starts with a Nail Turret. Turrets spawn close to you. Utility Power gains +25%. Damage gains halved."

## Server authority and performance

- **The server decides everything:** who has turrets (their items), where they stand, and what they shoot and when.
  - Clients send nothing for turrets. RunAction `BuildTurret` has no listener any more.
  - ShopService ignores ShopAction `UpgradeTurret` quietly: no message and no revision change.
- **Placement:**
  - Ground and sight rays run only when turrets are placed: at a wave start, for a mid-wave addition, or for a follow move (at most 2 a player at once).
  - Each spot tries at most 3 points with 2 rays each.
- **Targeting:**
  - Runs at 10 Hz from one TargetGrid snapshot per tick, built only while a turret is firing.
  - A turret picks a target again only when a nail is due that tick, or every 0.3 s for its aim, so 30 idle-ish turrets don't each cast every tick.
  - It takes the nearest allowed enemy in range with one line-of-sight ray. A boss is measured to its nearest body box, like for weapons.
- **Fire rate:** each turret keeps its own clock, with at most two nails per tick, so the average rate is exact. Nothing is banked across a hold.
- **Nails:**
  - They are a second `StatProjectiles` instance whose projectile keys start at 2^30, so clients never mix them up with weapon bullets.
  - Their `slotIndex` is 100 + the turret's Index, so clients know which turret fired. It never matches a weapon slot.
  - They use the Nail Gun's projectile look (`ProjectileStyleVisuals.Styles.Turret`).
- **Replication:** there are no server parts and no server CFrame writes. Each turret is a Folder in `workspace.RogueliteTurrets` named `UserId_n`, with these attributes:
  - `OwnerUserId` and `Index` (1–10 from items, 11 up for Scrap Magnet's)
  - `Tier`, `Position`, `Yaw` and `Temp`
  - `BuiltAt`, the server time it was placed. The client pops it in.
  - `Aim`, written at most 5 times a second when the target moves 1.5+ studs
  - `PackAt`, the server time it started packing up to follow you; cleared when it stands again
  - Folders are reused by Index from wave to wave.
- **Clients:**
  - They draw the models, turn the heads, pitch the barrels, and add recoil, spin and flashes.
  - They skip turrets more than 250 studs from the camera.
  - They pose idle turrets (no nail for 1.5 s) at 20 Hz instead of every frame.
  - They freeze everything while the run is paused.
- **Sounds** come from `RogueliteSounds`, reusing the kit:
  - each nail: the pistol pop, higher and quieter. It is its own sound kind (`turret`, 4 per 0.25 s), so 30 turrets never crowd out weapon sounds.
  - each placement: a thud and a metal tick
  - a tier change on the same Index: the upgrade chime

## Admin panel

The Player tab has a **Turrets** section, using the AdminService action `Turret`:
- **Give Nail / Give Twin / Give Quad / Give Gatling** (`Give 1–4`):
  - Adds one of that item to your run inventory through `ShopService.adminItem`, so the 10 limit holds.
  - In a wave or the sandbox it stands at once. In the shop it comes with the next wave.
- **Clear turrets:** your turret items go, and every standing turret goes now. Other players' turrets come back at the next wave.

The generic **Give item** grid lists the turret items, Scrap Magnet and Toolbelt too.

## Files

- **Rewritten:**
  - `HandymanTurret.luau`: the rules and numbers (items, the Brotato rule, ring maths, caps, Scrap Magnet, Engineer rules).
  - `HandymanTurretService.server.luau`: the server.
  - `HandymanTurret.client.luau`: the drawing. BUILD is gone.
  - `TurretTests.luau`
  - this doc
- **Small hooks:**
  - `ShopCatalog`: the 6 items, built from `HandymanTurret`.
  - `ShopService`:
    - `offerPrice` (the Handyman discount) in rolls and reprices;
    - the 10-cap in offers, buys and `adminItem`;
    - the structure weighting;
    - the free Nail Turret (`freeTurret` in `newState` and `onStatsChanged`);
    - `onShards` passes the crystals;
    - `UpgradeTurret` is ignored;
    - the snapshot's `turret` row is gone.
  - `ShopTests`
  - `CharacterStats`: the Handyman entry, `gained` and `resolve`.
  - `CombatEffectsService`: `d.structure` means no dodge crit and no life steal.
  - `RogueliteSounds`: the turret sound kind; the break crunch is gone.
  - `AdminConfig`, `AdminService`, `AdminPanelUI` and `AdminConfigTests`.
  - `ShopUI`: UPGRADE TURRET is gone.
  - `CHARACTER_STATS.md`, `README.md` and `SHOP_GAMEPLAY_READINESS.md`: one line each.
- **Back to before 9f6e956:** `RogueliteZombieChase.server.luau`, `EnemyAttacks.luau` and `ZombieAttacks.luau`.
- **Unchanged:**
  - `InstallHandymanTurret.luau` and the T1–T4 templates
  - `StatProjectiles` (`firstKey`) and `ProjectileStyleVisuals` (the nail look)
  - `RogueliteMeta` (`utilityKills`) and `RunAnalytics` (the `Turret` source)
  - `default.project.json`. There are no new modules or remotes.

## Studio steps (each needs the user's okay)

1. **Sync scripts.** All of them already exist in Studio, so their Sandboxed settings stay as they are:
   - `HandymanTurret` must be in `RS.RogueliteCombat` before the new `ShopCatalog`. ShopCatalog looks it up with `pcall`, so without it there are just no turret items.
   - The scripts: `HandymanTurret`, `HandymanTurretService`, the `HandymanTurret` LocalScript, `ShopCatalog`, `ShopService`, `CharacterStats`, `CombatEffectsService`, `RogueliteZombieChase`, `EnemyAttacks`, `ZombieAttacks`, `RogueliteSounds`, `AdminConfig`, `AdminService`, `AdminPanelUI` and `ShopUI`.
   - `AdminConfig` and `AdminService` go together.
   - `CharacterStats`, `ShopService` and `ShopUI` also carry the multi-class weapons work. Sync them with it.
2. **Tests, in Edit with no Play:**
   - `TurretTests(HandymanTurret, TargetGrid, WeaponCatalog, CharacterStats, EconomyConfig, ShopCatalog)`. The call is in its header.
   - `AdminConfigTests(AdminConfig, EnemyCatalog, ShopCatalog)`.
3. **Tests in Play:** `ShopTests`, as a temporary server Script.
4. **Play-test (the user):** see the checklist in the report, or:
   - **A Handyman run:**
     - Wave 1 has one Nail Turret 4–8 studs away, facing you.
     - A Nail Turret offer reads 20% under the Gunner's price.
     - Buying two more gives 3 turrets at wave 2, on the ring and 5+ studs apart.
   - **A Gunner:** no free turret. A bought Nail Turret stands 8–14 studs out.
   - **Admin:** Give Gatling mid-wave makes it stand at once and spin. Clear turrets removes them.
   - **Scrap Magnet:** 40 crystals in a wave makes a temporary Nail Turret appear. It's gone in the shop.
   - **Mobs ignore turrets** and walk through them.
   - **Pause** freezes them.
   - **A phone:** the shop's right column has no UPGRADE TURRET row, and there's no BUILD button.

## Not done / judgment calls

- **Gear power still counts** for turret damage, as it does for every hit (`CombatEffectsService`). The design's formula names only Utility Power, but later maps' enemies are tougher by exactly the gear-power share (`RunSetupRules.enemyScale`). Without it, turrets would fall behind there.
- **Status procs use your chances but not Damage.** Burn ticks scale with Elemental and Burn damage only, since Damage is ignored for structures.
- **Knockback, Attack range and projectile speed/size are ignored too**, beyond the design's list. Range is fixed at 25 ("range 25 studs for every turret"). Knockback pushes from the owner's body (shared code), which is wrong for a turret.
- **Weighting by "favoured":** the design says turret items get "the Handyman class weighting, like Handyman weapons". So it is the weapon same-class rule (15% + early bonus) applied to the structure items, for a Handyman or anyone carrying a Handyman-class weapon.
- **The free turret follows class changes only before the run starts.** After wave 1 starts, admin class changes don't add or remove it.
- **Fallback spots can be closer than 5 studs** to another turret (half radius, or your own spot). That is rare: only over cliffs, walls or the arena edge.
- **Scrap Magnet counts crystals before the bag bonus** (a boss crystal of value 4 counts 4). A temporary turret blocked by the server's 30 is built later in the wave if room appears.
- **Clear turrets also removes your turret items.** Otherwise they would come straight back at the next wave.
- **No sell for turret items:** the game has no item selling, so "they sell like any item" means not at all.
- **Studio may lag the repo.** Diff Studio against the repo before debugging a play-test report.
