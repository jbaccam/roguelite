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
- There is no pizza-slice icon yet; the Chef ability row uses the Pizza Cutter icon.
- Weapon names for the three new items are working names from the level-up art.
