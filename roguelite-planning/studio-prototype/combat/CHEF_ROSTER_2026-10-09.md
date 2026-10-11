# Chef, weapon types and items: what was built (October 9, 2026)

Design: [plans/2026-10-09-chef-roster-weapon-types-design.md](../../plans/2026-10-09-chef-roster-weapon-types-design.md). Balance numbers: [plans/2026-10-09-roster-balance-results.md](../../plans/2026-10-09-roster-balance-results.md).

## What changed

- **Classes:** Brawler, Gunner, Chef, Juggler, Handyman, Mage. Thrower is gone; Chef takes its slot, quest (wave 10 on Pine Valley) and Robux product.
- **One starter class per weapon.** A run starts only with a weapon of your class or an owned Godly. Brawler's default is now the Baseball Bat (Oct 10; it was Boxing Gloves for a day); Chef's is the Frying Pan. Every starter is its class's Common weapon, so the Bat became Common and the Gloves Rare.
- **Specialty:** your class's weapons get +10% damage on that weapon only. The old class-fit matrix and 2/4 home bonuses are gone.
- **Weapon types and sets:** Blade, Blunt, Gun, Thrown, Explosive, Elemental, Tool, Culinary, Trick. Every set gives its weapons +4/7/10/13/15% damage at 2-6 copies (a weapon in two sets takes the higher), plus one flavor bonus (Blade crit, Blunt armor, Gun +1 projectile from 4, Thrown projectile speed, Explosive radius, Elemental burn chance, Tool utility power, Culinary heal-on-hit, Trick dodge).
- **Chef:** +15 max HP, +10% melee, +25% recovery, -3 armor. Kills with Chef weapons have an 8% chance to drop a pizza slice that heals any player 10% max HP (x recovery).
- **Pizza Cutter (id 42):** Chef Legendary melee. Criss-cross Diagonal slices then a Thrust; the wheel spins with the cut and coasts. Tier IV Rolling Slice: every 4th swing a ghost wheel rolls 20 studs for 60%.
- **Items:** Knee of Justice (+12% melee), Finger Cannon (+12% ranged), Pocket Weather (+10% elemental), Toolbelt +10 utility power; Pencil, Straws and Bouncy Ball one tier earlier; shop offers follow your equipped weapons and types; misleading card text fixed; Area Size widens the Duck, Washer and Vacuum.
- **Saves:** Thrower becomes Chef; invalid saved starters reset to the class default (Brawler + Pan becomes Brawler + Bat; a saved Brawler + Gloves stays); Brawler owners get the Bat; nothing is ever removed. The tutorial runs as Brawler + Baseball Bat.
- **UI:** class screen (specialty, ability rows), Armory cards (starter class, type chips), shop offers (set step a buy reaches), Sets in the shop stats column and pause screen. Pizza Cutter uses the user's icon.

## What actually ran

- Luau CLI: roster runner (ClassTag 636, WeaponType 1313, RunSetupValidation 31, Showcase 1182, GearPower 265, NormalBalance 955, RosterBalance 338), shop runner (571 + Duck 33 + Washer 34), ChefPizzaTests 1527, QuestTests 2173, GiftTests 135, TutorialTests 74, ProfileMigrationTests 163. EnemyScalingTests: all pass except the Round 10 session's bloater speed check.
- Studio Edit, read-only: LegendaryMoves 123, Turret 2222, Journal 2037, ChestConfig, WeaponBalance 1727, RunSetupLayoutTests 60 scenarios, ArmoryExperienceTests 2055, WeaponJournalLayoutTests 41136, ChefPizzaTests 1527 (after the sync). UI layout audits at 1920x1080, 1366x768, 844x390, 750x369, 667x375 on CoreGui previews.
- Oct 10 Bat starter change, Luau CLI only: roster runner (ClassTag 636, WeaponType 1315, RunSetupValidation 32, Showcase 1182, GearPower 265, NormalBalance 955, RosterBalance 338), shop runner (571 + 33 + 34), ChefPizzaTests 1527, EnemyScalingTests 4491 (bloater check skipped; it is the Round 10 session's), TutorialTests 75, ProfileMigrationTests 175, QuestTests 2173, GiftTests 135, ChestConfigTests 145, WeaponBalanceTests 1727. Rojo build OK. No Studio run.
- Not run: anything needing Play (CharacterStatsTests, ShopTests, ShopLayoutTests, ArcAttack), real multiplayer, live feel. No Play session was started.

## Studio state

- Synced 2026-10-09 23:3x to place 107877054949326 with one guarded write: 39 scripts at commit 84c3904 (each Studio copy matched its git base exactly; no other session's commits were in between) plus new ChefPizza, ChefPizzaService and ChefPizzaVisuals (sandboxed, capabilities copied from siblings). All re-read equal.
- Installed: `RogueliteCombat.WeaponTemplates['42']` (Pizza Cutter, 3.8 studs, TextureID 92867308963249) and `RogueliteCombat.PickupTemplates.PizzaSlice` (TextureID 136977119080245). Raw imports kept in ServerStorage (PizzaCutterImport, PizzaSliceImport).
- Saved with Ctrl+S afterwards (no dialog appeared).

## What to try (play-test)

1. Lobby: class row reads Brawler, Gunner, Chef, Juggler, Handyman, Mage. Old Thrower owners see Chef unlocked.
2. Brawler starts with the Baseball Bat; Frying Pan is not offered for Brawler. Boxing Gloves show as Rare. Chef offers Pan, Spatula, Steak, Egg, Molotov, Pizza Cutter (if owned) and owned Godlies.
3. Pizza Cutter: wheel spins during each slice and coasts to a stop, handle never moves; slices criss-cross then push. Admin-give a Tier IV copy and watch every 4th swing roll a ghost wheel.
4. As Chef, kill with Chef weapons: slices drop now and then (Studio: set attribute `TestPizzaChance=1` on ReplicatedStorage.RogueliteCombat to force), heal on touch with a bite sound, blink at 9 s, vanish at 12 s, max 4.
5. Shop: weapon cards show types and the set step; Knee of Justice / Finger Cannon / Pocket Weather appear only for builds that can use them. Stats column and pause screen show Sets.
6. Tutorial: plays as Brawler with the Baseball Bat ("Your bat swings by itself"); the upgrade step uses two Bats.
7. Duck / Washer: with Hot Sauce (Area Size) the spray looks and hits wider.

## Known follow-ups

- Rename product 3716086758 on the Creator Dashboard to "Chef Class" with `ui/assets/store-products/29-ClassThrower.png`.
- 6-gun Gunner is +10% single-target vs before (kept: the old free pierce is gone).
- There is no pizza-slice icon yet; the Chef ability row uses the Chef class icon (Frying Pan) since Oct 10 (it was the Pizza Cutter's, which made the drops look like a Cutter perk).
- Mage has no Epic weapon (Common Staff and Crystal Ball, Rare Pandora and Medusa, Legendary Mjolnir). That was already true; with Excalibur gone Mage also has only one Legendary and 5 weapons. The planned spellbook is the natural Epic (or a second Legendary).
- Weapon names for the three new items are working names from the level-up art.

## October 10: pizza for every Chef weapon, Excalibur to Brawler

User: "The chef pizza roller drops pizza slices, but I need to make it universal for all his weapons" and "I should make a spellbook for the mage and move Excalibur to others."

**Pizza drops are a Chef class ability.** The code already rolled for every Chef weapon; the class screen's PIZZA DROPS row showed the Pizza Cutter icon, which read as a Cutter perk. Now:

- `ChefPizza.isChefWeapon` decides by the weapon's class tag only (`d.class`, the `WeaponCatalog.inClass` rule). The hard-coded id fallback list is gone, so a weapon moved into or out of Chef moves its drops with it.
- Numbers, the same for all six (Pan, Spatula, Steak, Egg, Molotov, Pizza Cutter): 8% per kill (about 1 in 12), at least 1.5 s apart per Chef, at most 4 slices per Chef on the ground, 12 s lifetime (blinks the last 3 s), heals the grabber 10% of max HP x Recovery (Chef's +25% makes 150 max HP heal 18.75). The Cutter never had its own rate, so there is no per-weapon bonus. No strength buff (the friend's "strengthens you" idea is not built).
- A non-Chef with a Chef weapon (bought in the shop) gets no drops, the same rule as specialty. Godlies, turrets and bloater kills never drop.
- Server side, unchanged: `ChefPizzaService` decides on enemy death from `LastDamageUserId` / `LastWeaponId`; `HeartDropService` runs the pickup with the distance check. Same pizza-slice model for every weapon.
- Class screen: the row reads "8% chance (about 1 in 12) on a kill with any Chef weapon; heals 10% of max health" with the Frying Pan (Chef class) icon.

**Excalibur (32) moved Mage -> Brawler.** It is a melee sword swing (type Blade); Brawler is the melee class with the Katana and Kusarigama and +20% melee, and Excalibur was a Brawler weapon before Oct 9. Types (Blade, Elemental), elemental flag, Legendary beam and numbers are unchanged. Brawler 7 weapons (like Juggler; the starter grid already sizes for 7 + the Godly slot), Mage 5. Owned copies, tiers and saves are untouched; a saved Mage + Excalibur starter resets to the Magic Staff on load (existing `ProfileService` rule), and Brawlers who own it can now start with it. Godly slot and shop pools are not class based, so they are unchanged.

Ran (Luau CLI only, no Studio, no Play): ChefPizzaTests 1644 (was 1527; adds every catalog weapon by class tag), roster runner (WeaponClassTag 644, WeaponType 1315, RunSetupValidation 32, Showcase 1182, GearPower 265, NormalBalance 955, RosterBalance 338; Mage roster row now 5 weapons, new printed "Brawler + Excalibur" row 0.941 / 0.936), shop runner 571 + 33 + 34 in a scratch copy with other sessions' uncommitted EconomyConfig / LevelUpCatalog / ShopPreferenceTests / CharacterStats edits set back to HEAD (the live tree fails "shop wave 20, no Luck tier 3" from those edits, not this change). Rojo build OK. Updated but not run (need Studio): RunSetupLayoutTests (pizza line text + icon), CharacterStatsTests (Brawler 7, Mage 5).

Studio: not synced. Files to push: WeaponCatalog, ChefPizza, RunSetupUI (+ the test modules).

## October 10: Molotov rework

User (play-test): "Molotovs are kinda shit. Increase radius and maybe change the actual fire, it looks weird. An initial bigger AoE that gets smaller could be good."

- **Gameplay** (server, `SpecialWeapons` + `SpecialMotion.Fire`): the fire lands at 7.2 studs (was 4.5 flat), holds 0.4 s, then burns down to 3.6 by its 4 s end. Ticks read the radius at that moment, 45% of a hit every 0.4 s (was 40%); the first tick is a 100% ignition over the full 7.2. Up to 4 fires per player (was 3). Hit, cooldown, tiers, burn and Area Size / Duration scaling are unchanged; the Fart Gun's cloud is unchanged.
- **Numbers:** crowd output x2.3 to x2.5 per tier (Tier I 442 -> 1,010 damage x stud² per second, Tier IV 1,909 -> 4,809). It goes from the weakest area weapon to level with the Fart Gun at Tier I, past it from Tier II, and stays under Pandora's Box at every tier. Single target is about the same (it is the Chef's crowd weapon; Pan, Spatula and Steak stay the duelists). Full tables: [WEAPON_BALANCE.md, Molotov fire rework](WEAPON_BALANCE.md#molotov-fire-rework-2026-10-10).
- **Look** (design sheet: https://claude.ai/artifact/NBgiUUT7Ee3gDMfwWhMEA8): no more Roblox `Fire` instances on neon balls. A scorch decal, a painted fire-pool decal that shrinks with the server radius, upright flipbook flame tongues on its rim and inside, embers, and on landing an amber-rimmed ring out to 7.2 plus the existing glass shards. A glassy clink and a low whoomp play when it lands (`RogueliteSounds`, the existing kit pitched). Details: [WEAPON_VFX.md](WEAPON_VFX.md#molotov-fire-october-10-2026).
- **Ran:** `run_fire_zone_tests.py` (FireZoneTests 453 checks, new), roster runner, ChefPizzaTests 1644, `run_vfxkit_tests.py` 90, shop runner (ShopPreference 5979, Duck 33, Washer 34), `check_vfx_cleanup_order.py` 0 problems, luau-compile on every touched file, Rojo build OK. No Studio run and no Play test: the fire's look and feel are untested in game.
- **Studio:** not synced. Scripts to push: `SpecialMotion`, `SpecialWeapons`, `SpecialWeaponVisuals`, `ThrownVisuals` (RogueliteCombat), `WeaponShowcaseStage` (UI), `RogueliteSounds` (StarterPlayerScripts). Asset to upload: `weapon-models/assets/14-molotovs/vfx/textures/MolotovFirePool.png`, then put its id in `ThrownVisuals.FireTextures.Pool` (until then the pool is three flat discs in the same colours).
