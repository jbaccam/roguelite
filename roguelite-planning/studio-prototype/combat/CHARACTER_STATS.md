# Character stats and Studio practice editor

Implemented September 17, 2026. This is the authoritative prototype stat/class implementation; numeric values remain balance tuning. Non-weapon shop passives and purchases are outside this change.

## Controls

- **Stats / Test [P]** opens the character editor; the Stats tab is also available from Inventory and Shop.
- Select one of six classes. Class selection clears manual overrides. Equip class build fills four slots with a suggested loadout; other weapons still work.
- Edit effective stat values with minus/plus or type a value and press Enter. An asterisk marks an override. Reset stat edits restores class and affinity values. Heal and Test 20 contact damage exercise sustain and defenses.
- Zombie buttons change the shared practice target by 1 or 10, from 0 to 100. Z toggles spawning. Changing target replaces the wave; killed enemies return after three seconds. Zero clears it without stale replacements.
- Changes are server validated, rate limited, living-player and Studio Practice only. Nothing awards persistent currency or wins.

## Stats and weapon integration

CharacterStats.luau now defines 46 visible attributes with defaults, caps, descriptions and calculation rules. Shop Discount and Shop Price Modifier are active in the server-owned economy. Purchased passive/utility items contribute bonuses and penalties before debug overrides and safety caps. See the SHOP / ECONOMY SYSTEM section in the master design document.

CharacterService mirrors effective values as `Stat_<id>` on the avatar and its replicated player-state folder. Humanoid MaxHealth and WalkSpeed receive actual values. Armor/contact reduction/dodge/first-hit blocking modify incoming zombie attacks. An empty StarterCharacterScripts.Health prevents Roblox default regeneration from bypassing our regeneration and Recovery rules. Life steal uses actual damage and a per-second healing cap.

All 36 weapons consume general damage, compatible melee/ranged/elemental/utility damage, critical chance/multiplier, attack cadence and range. Elemental and Utility tags come from WeaponCatalog. Projectiles use server swept collision and bounded travel, size, extra shot counts, unique-target piercing and bounces. Added piercing hits multiply damage by 0.7; bounces multiply it by 0.6. Explosives use area and explosion bonuses; piercing/bounce do not apply to explosions. Lightning never recursively triggers itself. Burn/poison/slow have bounded durations and stacking; burn spreading cannot propagate a second generation. Boss/elite damage requires the relevant enemy attribute. Slow and knockback have reduced boss effects.

**Which weapons use the weapon-only stats (2026-10-03).** One rule, `CharacterStats.usesStat`, answers this for the server's launchers (through `CharacterStats.shotStat`), the run shop's offers and the cards' "Works with" line, so they can't disagree.
- Extra shots: guns, staffs, cards, throws that don't come back, rockets, Pandora's Box and the Storm Bow.
- Pierce and bounce: bullets, cards, and throws that aren't fire or gas (Boomerang, Mjolnir and the Trident included).
- None of them: melee swings, the Rubber Duck's spray, the Vacuum and the Power Washer.
- Extra swings (`ExtraSwings`, added 2026-10-10, 0 to 2): melee swings only, the Mjolnir and Trident swings included but not their throws, and not the Shadow Daggers. After a swing stops hitting, the weapon swings again, back the other way, for 60% damage (`CharacterStats.ExtraSwing`, `extraSwings`, `extraSwingTimes`). The server sweeps it like any swing. Source: Windshield Wiper ([shop notes](SHOP_GAMEPLAY_READINESS.md#windshield-wiper-and-stronger-coupons-2026-10-10)).
- Example: Two Straws gives a Glock 2 bullets and a Frying Pan nothing; Windshield Wiper gives the Frying Pan a second swing and the Glock nothing.
- Lightning and area stats also count your own sources: with Battery Pack, every weapon chains lightning, so Tinfoil Antlers helps them all.

Attack range moves melee reach without rescaling the equipped mesh. Authored model sizes, including the katana scale 0.013698526658117772, are preserved. Projectile Size changes projectile collision/visuals, not the equipped weapon model.

Pickup Radius and Luck apply to rare heart drops (`HeartDropService`, retuned 2026-09-29): 1% per real kill plus Luck × 0.02%, capped at 3%; a heart heals 15 HP before Recovery, is pulled by any living player within max(4, Pickup Radius) (wasted at full health), and expires after 10 s. (The original 15%/8 HP green orb was removed on 2026-09-22.) XP, currency, shop odds and purchases remain deferred. Utility Power applies to existing Handyman weapons. (This change added no summon; since 2026-10-03 the Handyman builds a turret, see Class abilities below.)

## Normalized avatars

`AvatarNormalizer.server.luau` (September 27, 2026) turns off `CharacterAutoLoads` and spawns every character from a sanitized copy of the player's HumanoidDescription. Height, width, depth and head scale are set to 1, and body type and proportion to 0. Body-part meshes are set to 0, so the rig uses classic R15 limbs, with no Rthro, dynamic-head or custom body shapes. Animation-pack IDs are also set to 0, so the default R15 animations play. Layered clothing is removed. Up to four rigid hat, hair or face accessories are kept, along with body colours, classic shirt/pants/T-shirt and face. This keeps armor, shirts, floating weapons and animations on the body proportions they were authored for.

The script also handles respawns after death, using `Players.RespawnTime`. Any character loaded another way (for example a plain `LoadCharacter` in a test) is replaced with a normalized one. Game Settings > Avatar should stay on R15; the script warns if a spawn comes out R6. Studio Play check: no reload loop, H=1, BodyType=0, height 5.5 studs, stats still applied, and correct on first spawn, after a foreign reload and after death. Several different real avatars in a live server have not been tested.

## Classes

Every class retains access to every weapon. Two/four home weapons grant additive affinity bonuses, subject to caps. Duplicate home weapons count toward affinity.

**Weapons in several classes (2026-10-04, [design](../../plans/2026-10-04-multi-class-weapons-design.md)).** Every non-Godly weapon lists 1–3 classes in `WeaponCatalog` (`classes`; the first is its old home, and `home` stays as that first class for older code). Godly weapons list none, as before.
- **Set bonuses** count a weapon for every class in its list. Example: two Kusarigamas (Juggler, Thrower) give a Juggler or a Thrower the 2-weapon bonus.
- **Utility Power and the Utility tag** (and the `utilityKills` quest) apply when Handyman is anywhere in the list, so the Spatula, Rocket Launcher and Cinder Block now take Utility Power. Elemental follows a listed Mage the same way (no weapon changed).
- **Starting weapon:** any owned weapon whose list includes the class, with no cap of six (`RunSetupRules.classWeapons` / `validLoadout`). A saved starter that no longer fits falls back to the class's signature weapon.
- **Run shop:** the "same class" weighting matches an offer that shares any class with a carried weapon.

| Class | Weapons (signature first; ² = listed second) | Count |
| --- | --- | --- |
| Brawler | Frying Pan, Nunchucks, Katana, Baseball Bat, Boxing Gloves, Cinder Block, Bowling Pin², Shovel², Excalibur² | 9 |
| Gunner | Glock, Draco, Fart Gun, Shotgun, T-Shirt Cannon, Rocket Launcher, Nail Gun² | 7 |
| Thrower | Boomerang, Kunai, Molotov, Egg, Steak, Deck of Cards, Kusarigama², T-Shirt Cannon², Rubber Duck², Bowling Ball², Mjolnir² | 11 |
| Juggler | Rubber Duck, Kusarigama, Spatula, Yo-Yo, Bowling Ball, Bowling Pin, Boomerang², Egg², Deck of Cards², Boxing Gloves² | 10 |
| Handyman | Nail Gun, Wrecking Ball, Shovel, Paint Roller, Vacuum Cleaner, Power Washer, Spatula², Rocket Launcher², Cinder Block² | 9 |
| Mage | Magic Staff, Mjolnir, Excalibur, Pandora's Box, Medusa's Head, Crystal Ball, Fart Gun², Molotov² | 8 |

The design's table was written from the homes before the 2026-10-03 Brawler ↔ Juggler swap. The four swapped weapons follow that swap so their first class stays today's home: Kusarigama is Juggler, Thrower (design: Brawler, Thrower), Spatula Juggler, Handyman (Brawler, Handyman), Boxing Gloves Brawler, Juggler (Juggler, Brawler), Cinder Block Brawler, Handyman (Juggler, Handyman). So Brawler has 9 and Juggler 10 (design: 10 and 9).

Rebalanced 2026-10-03 so no class is plainly worse: each has 3–4 buffs and 1–3 drawbacks, and a drawback never weakens the class's own weapons (Thrower lost −10% attack speed, Juggler's damage penalty went from −15% to −10%, Handyman lost −2 speed and −5 crit). Gunner's faster ranged attacks are data now (`rangedAttackSpeed`) and shown with its buffs.

| Class | Base buffs | Base drawbacks | 2 home weapons | 4 home weapons (additional) |
| --- | --- | --- | --- | --- |
| Brawler | +25 HP, +3 Armor, +20% melee, +8 knockback | −2 movement speed, −15% ranged | +15% melee, +2 Armor | 5% life steal |
| Gunner | +20% ranged, +35% projectile speed, +5 critical points, +10% ranged attack speed | −15 HP, −15% melee | +1 pierce | +1 projectile |
| Thrower | +25% range, +1 bounce, +15% ranged | −2 Armor, −10% melee | +15% ranged | +1 projectile |
| Juggler | +3 movement speed, +15% attack speed, +12 knockback | −10% general damage | +15% range, +5 knockback | +1 bounce, +15% attack speed |
| Handyman | +15% utility, +20% area, +1 HP/s regeneration (Engineer since 2026-10-04: Utility Power gains ×1.25, Damage gains ×0.5; the +5% damage went) | −10 HP | 10% cooldown reduction | +20% utility (counts +25) |
| Mage | +25% elemental, +30% duration, 15% burn chance, +1 chain target | −20 HP, −2 Armor, −10% melee | +15% elemental | +1 burn-spread target |

**Class weapon fit (2026-10-03).** On top of the table, every equipped weapon gets its own damage change from how close its home class is to yours: own class **+15%**, then one number per pair of classes (the same both ways). Godly weapons are unchanged. It stacks with the class stats. Values: `CharacterStats.ClassFit`. Since 2026-10-04 a weapon in several classes uses the **best** of them (`CharacterStats.classFit`): a Gunner with the Nail Gun (Handyman, Gunner) gets +15%, where it was 0; a Brawler with the Kusarigama (Juggler, Thrower) gets −5. The cards show every class ("THROWER · JUGGLER · RANGED") and the badge shows the best fit.

| Your class → weapon's class | Brawler | Gunner | Thrower | Juggler | Handyman | Mage |
| --- | --- | --- | --- | --- | --- | --- |
| Brawler | **+15** | −15 | −5 | −5 | 0 | −10 |
| Gunner | −15 | **+15** | 0 | −5 | 0 | −5 |
| Thrower | −5 | 0 | **+15** | 0 | 0 | −5 |
| Juggler | −5 | −5 | 0 | **+15** | 0 | −5 |
| Handyman | 0 | 0 | 0 | 0 | **+15** | −5 |
| Mage | −10 | −5 | −5 | −5 | −5 | **+15** |

Why: Handyman is handy with anything (0 with everyone but Mage, and everyone can use its tools). Gunner, Thrower and Juggler all fire or toss things. Fists vs guns is the one opposite pair. Mage weapons are the strongest and most specialised, so Mage pays the most outside its own class. Example: a Brawler's Glock takes −15% and the Brawler's −15% ranged, about −28% in total (Brotato's Brawler is −50 ranged, so this is gentler). Where players see it (2026-10-03, shared pieces in `UITheme`: `statColumns`, `homeRows`, `fitTiles`, `fitBadge`, `tag`, `section`):

- **Armory, class details:** Always on (buffs | drawbacks), the 2 / 4 home weapon bonuses, and the class's row as six tiles (each class's starter icon and number, own class framed in lime).
- **Run setup, choosing a class:** the details panel shows buffs | drawbacks and the home weapon bonuses; every class card gets a badge with the number for the picked class. Cards are 140 tall (were 150) so the 470 × 380 panel fits every class without scrolling.
- **Item card (chest odds):** class and type tags under the image, and a "Damage by class" strip (the weapon's column, the loadout's class tagged YOU).
- **Run shop:** the class tag under the name, and a fit bar ("−15%  ·  OFF-CLASS"). Narrow phone cards step down: class only, then an icon tag with the class in the bar.
- Colours everywhere: lime = your class, cream = 0%, reds for −5 / −10 / −15.

Layout checks (Studio Edit, UILayoutAudit, no Play): the item card at 7 screen sizes; the Armory and run-setup panels for all six classes at 1080p, 768p and phone scale; the shop tag and bar at card widths 156–300 and scales 1 / .7 / .55. The full Armory, run-setup and shop screens were not opened in Play. Studio sync, 2026-10-03: CharacterStats, WeaponCatalog, ProfileService, RunSetupRules, RogueliteLobbyPreview (server), UITheme, ArmoryUI, ItemCardUI, RunSetupUI and ShopUI written from commit 0b2b759, each only after checking Studio still held the expected earlier version. No Play test has run on it yet.

These prototype choices supersede the older proposal that classes need no drawbacks. Distinct orbital/return animations and deployables remain separate weapon-kit work; this change applies class statistics to the existing attack styles.

## Class abilities (2026-10-03)

Two classes got an ability from the play-test round. Repo only, syntax-checked: not yet in Studio, not play-tested.

**Melee dash** (play-test: "dash for melee based characters", so melee builds can close in).
- **Who:** Brawlers always; any other class only when its starting weapon is melee, e.g. a Mage who starts with Excalibur (`CharacterStats.dashes`).
- **How:** Q, gamepad X, or the DASH button (bottom right on keyboard and gamepad; beside the jump button on touch). It works on the ground and in the air.
- **Numbers** (`CharacterStats.Dash`): 20 studs in 0.18 s (111 studs/s), then 3 s cooldown. No damage and no invulnerability.
- **Server checks:** the client moves its own body and sends `RunAction 'Dash'`. `RogueliteMeta` approves it (class or starter, cooldown, mid-wave or sandbox, not paused, not held) and stamps `DashAt`. `MovementGuard` then allows 26 extra studs for 1.5 s. For 0.6 s after a dash, enemy hits use the player's seen position up to 20 studs ahead ([HIT_FAIRNESS.md](HIT_FAIRNESS.md#round-4-melee-from-a-jump-and-the-dash-2026-10-03)).

**Turrets (turret items since 2026-10-04).** Turrets are run-shop items any class can buy (Nail Turret, Twin Nailer, Quad Nailer, Gatling Rig; up to 10 each, 30 on the server). They are placed for you on a ring at every wave start; there is no BUILD button or turret upgrade any more. The Handyman is Brotato's Engineer: a free Nail Turret each run, a tighter ring (4–8 studs), turret items 20% off, Utility Power gains ×1.25 and Damage gains ×0.5 (`CharacterStats.gained`). Turrets can't be destroyed. Rules and numbers: [HANDYMAN_TURRET.md](HANDYMAN_TURRET.md). Art: `roguelite-planning/blender-handyman-turret/`. The class description reads "Engineer: starts with a Nail Turret. Turrets spawn close to you. Utility Power gains +25%. Damage gains halved."

## Armor in plain words (2026-10-10)

Play-test: "I'm a little confused what armor does and where to see it." Two things share the name:

- **The Armor stat** cuts the damage of every hit you take (zombie contact, enemy swings and shots, slams, bosses): damage ÷ (1 + Armor ÷ 15), so the cut is Armor ÷ (Armor + 15). Each point does a bit less than the one before. Negative Armor (Chef −3, Mage −2) makes hits bigger: × (1 + |Armor| ÷ 15). Example: Armor 10, a 20-damage hit does 12 (40% less).
- **Armor pieces** (helmet, chest, legs, boots from chests) have no stat by themselves. Each worn piece adds its tier to Gear Power (+12% damage, +6% health per point). 2 pieces of one set give the set's bonus, all 4 add its perk ([RARITY_GODLY_ARMOR.md](../RARITY_GODLY_ARMOR.md#armor-clarity-2026-10-10)).

| Armor | −5 | −3 | −2 | 0 | 1 | 2 | 3 | 5 | 8 | 10 | 15 | 20 | 30 | 45 | 100 (cap) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Damage you take | 33% more | 20% more | 13% more | full | 6% less | 12% less | 17% less | 25% less | 35% less | 40% less | 50% less | 57% less | 67% less | 75% less | 87% less |
| A 20-damage hit | 26.7 | 24 | 22.7 | 20 | 18.8 | 17.6 | 16.7 | 15 | 13 | 12 | 10 | 8.6 | 6.7 | 5 | 2.6 |

**What was confusing.** Every screen showed Armor as a bare number ("Armor 3") with no unit, and the only explanation was the formula in the Studio stat editor. Contact resistance and First-hit blocks (Iron and Spartan 4-piece, Burial Mask) were never shown in a run. In a run nothing said which armor you wore or whether its set bonus was on. The Armory showed a set's "2 PIECES / 4 PIECES" lines at Tier I numbers, never whether they were on, and nothing said a single piece does nothing alone.

**The rule now: players never do the sum.** Armor always shows as a percent. Helpers in CharacterStats (pure, tested in ArmorSetTests):
- `armorPercent(a)`: 8 → 35, −3 → −20 (the same sum as `incoming`).
- `statNote` / `statLabel`: "Armor · you take 35% less damage", "you take 20% more damage"; nil for every other stat and for 0.
- `armorChange(a, d)`: "25% → 32% less damage" (from a to a + d).
- `armorSetLines(wearing, tiers, armor)`: one row per worn set, {count, two, four} with on, need (pieces still to put on) and the line at its real tier numbers. With the live Armor, a line that adds Armor says what it does from there: "+2 Armor (25% → 32% less damage)".

Where it shows (UI reads the server's Stat_ attributes and ProfileWearing / ProfileArmor only; mockup: `previews/armor-clarity-mockup/`):
- **Pause screen (P):** a new ARMOR group in STATS, each worn set with its 2 / 4 piece lines, ON or "n MORE"; a muted line under Armor ("you take 32% less damage from every hit"); Contact resistance and First-hit blocks under DEFENSE when you have them.
- **Run shop and level-up stat lists:** the Armor label reads "Armor · you take 35% less damage". Item cards and the inventory detail add the change to Armor lines ("Armor: +2 (25% → 32% less damage)"; an owned copy shows from your Armor without it). The Armor level-up card does the same.
- **Armory, Armor tab:** two lines over the slot filter (how sets work; "Your Armor: 7, so you take 32% less damage" plus a 5 / 15 / 30 reference on PC), then a WEARING line ("Iron 3/4 (2-piece on) · Ninja 1/4"). The piece detail's 2 / 4 PIECES rows say ON or WEAR n MORE with the real numbers, and one line says what a piece does alone (Gear Power).

Analysis: the formula is fine for balance (diminishing, no cap problems), but a number with no unit reads like nothing. One point is worth about 6% at 0 Armor and about 1% at 30, so showing the before → after percent on anything that adds Armor answers "is this worth it" directly. Not changed: the Studio stat editor (CharacterStatsUI) keeps its formula help; the chest / item card (ItemCardUI) keeps plain "+2 Armor" (no live value in its tier table).

Checks: ArmorSetTests 209 checks (Luau CLI on the real CharacterStats, incl. every set × tier agreeing with `armorBonus`), roster / shop / Armory navigation runners pass, every changed module compiles. Repo only: not synced to Studio, no Studio Play test, and the screens were checked in the HTML mockup (PC 1920 × 1080 and phone 844 × 390), not in Studio.

## Verification

- CharacterStatsTests.luau: **2,283 assertions passed** in an actual server Script during Studio Play, covering all classes/weapons, avatar application, affinity calculations, invalid/nonfinite/fractional inputs, phase and rate rejection, defenses, regeneration, Recovery, life-steal caps, critical/boss damage, status ticks, poison caps, chains, burn spread, reset and healing.
- StatProjectileTests.luau: actual swept-projectile tests passed for piercing and bounce falloff, unique targets, wall occlusion, projectile size, travel speed and rocket splash.
- Actual client controls: class selection changed Gunner HP to 85 and ranged bonus to 20%; Damage plus updated the UI and avatar attribute to 10. A client remote set Damage to 40; malformed requests were exercised separately.
- Zombie target 25 produced 25 enemies; zero cleared them and remained empty after replacement delay.
- Practice health-drop checks passed for Recovery healing and in-range/out-of-range pickup behavior.
- Authored katana scale verified after removing an erroneous ScaleTo call. RPG render fidelity is handled separately by FixRocketMuzzle.luau.
- Rojo combat and root packaging passed. Studio source and repository are synchronized.

Tests execute in the normal server Script context. Requiring stateful modules directly from the Studio assistant execution context gives a separate module cache and cannot inspect the live CharacterService state. Initial test-harness failures were corrected (a status threshold and a test-target folder outside the normal enemy occlusion exclusion).

Multiple real clients, published-game access restrictions, high-latency stress, final class balance, and maximum-population device performance remain unverified. Studio testing does not demonstrate those passed.
