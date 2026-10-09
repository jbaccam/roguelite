# Chef, one starter class per weapon, weapon types, items

October 9, 2026. Implements [ROSTER_WEAPONS_CLASSES_MASTER_GUIDE.md](../ROSTER_WEAPONS_CLASSES_MASTER_GUIDE.md). This file records what the user decided on October 9 and the exact rules the code follows. Where the guide calls something a proposal, this file says which way it went.

## Decisions (user, Oct 9)

| Question | Decision |
|---|---|
| Roster | Every ordinary weapon has exactly ONE starter class (the guide's section 3 table). Weapon TYPES are a separate Brotato-style system. Example: Pizza Cutter = melee attack, types Blade + Culinary, starter class Chef. Kunai = ranged, type Thrown (not Blade just because it has a blade). |
| Class bonus | Per weapon, never the whole build. A weapon whose starter class is your class gets +10% damage on that weapon. Off-class weapons get no class penalty of their own; only your class's existing attack-family drawback touches them (Brawler -15% ranged damage makes the Glock weaker, not the build). The old ClassFit matrix and the class two/four home bonuses are removed, not stacked. |
| Chef | Pizza drops, no dash. Dash stays Brawler-only. |
| Godlies | Stay classless any-class starters (the one written exception to "starters must be your class's weapons"). |
| Kusarigama | Moves to Brawler and keeps its melee sweep. |
| Thrower owners | Thrower becomes Chef 1:1: owned Thrower = owned Chef, selected Thrower = selected Chef. Chef takes over Thrower's quest (wave 10 on Pine Valley) and the ClassThrower product (same product id now grants Chef; the user renames it on the Creator dashboard). |
| Play testing | Agents work in Edit mode only. The user play-tests. |
| Items (user's follow-up) | Keep most items. Add direct Melee, Ranged and Elemental damage items. Review Toolbelt next to them. Fix misleading text (Bouncy Ball). Check stream weapons separately. Sets and specialty replace the old class bonuses; measure combined totals on equal-cost builds. |

## Roster (starter class)

| Class | Weapons (id) | Default starter |
|---|---|---|
| Brawler | Nunchucks 02, Katana 03, Kusarigama 04, Baseball Bat 06, Boxing Gloves 19, Cinder Block 20 | Boxing Gloves 19 (was Frying Pan) |
| Gunner | Glock 00, Draco 07, Fart Gun 08, Shotgun 09, T-Shirt Cannon 10, Rocket Launcher 11 | Glock 00 |
| Chef | Frying Pan 01, Spatula 05, Steak 16, Egg 15, Molotov 14, Pizza Cutter 42 | Frying Pan 01 |
| Juggler | Boomerang 12, Kunai 13, Rubber Duck 17, Deck of Cards 18, Yo-Yo 21, Bowling Ball 22, Bowling Pin 23 | Rubber Duck 17 |
| Handyman | Nail Gun 24, Wrecking Ball 25, Shovel 26, Paint Roller 27, Vacuum 28, Power Washer 29 | Nail Gun 24 |
| Mage | Magic Staff 30, Mjolnir 31, Excalibur 32, Pandora's Box 33, Medusa's Head 34, Crystal Ball 35 | Magic Staff 30 |

Class order everywhere (menus, Armory groups, arrows): Brawler, Gunner, Chef, Juggler, Handyman, Mage. Chef takes Thrower's slot.

Pizza Cutter is appended as id `42`. No existing id is reused or renumbered. Any code that treats "id >= 36" as Godly must use the explicit Godly list instead.

## Attack flags stay exactly as they are

Today `elemental` and `utility` are worked out from Mage/Handyman membership. Moving weapons between classes would silently change their damage. So they become authored lists that equal today's values:

- Elemental: 08 Fart Gun, 14 Molotov, 17 Rubber Duck, 30-35 (Mage weapons), 38 Storm Bow, 41 Ray Gun.
- Utility: 05 Spatula, 11 Rocket Launcher, 20 Cinder Block, 24-29 (Handyman weapons).
- Pizza Cutter: neither.

A test pins both lists to these values.

## Specialty

`Specialty = 10` (percent). For each equipped weapon: if `weapon.class == player class`, that weapon's damage x1.10. Godlies never get it. Shown on the weapon card as "Chef specialty: +10% damage" only when it applies, and on the class screen as "+10% damage with Chef weapons".

Example: Brawler with Katana and Glock. Before: Katana +15% (own class) and two/four bonuses; Glock -15% off-class x -15% ranged = about -28%. After: Katana +10% (specialty) plus Brawler's +20% melee buff; Glock -15% (Brawler's ranged drawback only).

## Weapon types

Vocabulary: Blade, Blunt, Gun, Thrown, Explosive, Elemental, Tool, Culinary, Trick. Each ordinary weapon has 1 or 2 types; Godlies have types too (they count toward sets).

Set bonuses count equipped copies (six slots, so six Katanas = Blade 6). Merging copies changes the count right away. Thresholds 2, 3, 4, 5, 6; the value shown is the running total, not an add-on per step. Unless a row says "you", a bonus applies only to weapons of that type.

Types follow what each attack really does ([weapons audit](2026-10-09-roster-audit-weapons.md) section 1), not what the object looks like.

| id | Weapon | Types | | id | Weapon | Types |
|---|---|---|---|---|---|---|
| 00 | Glock | Gun | | 22 | Bowling Ball | Thrown, Trick |
| 01 | Frying Pan | Blunt, Culinary | | 23 | Bowling Pin | Thrown, Trick |
| 02 | Nunchucks | Blunt | | 24 | Nail Gun | Gun, Tool |
| 03 | Katana | Blade | | 25 | Wrecking Ball | Blunt, Tool |
| 04 | Kusarigama | Blade | | 26 | Shovel | Blunt, Tool |
| 05 | Spatula | Blunt, Culinary | | 27 | Paint Roller | Tool |
| 06 | Baseball Bat | Blunt | | 28 | Vacuum Cleaner | Tool |
| 07 | Draco | Gun | | 29 | Power Washer | Tool |
| 08 | Fart Gun | Gun, Elemental | | 30 | Magic Staff | Elemental |
| 09 | Shotgun | Gun | | 31 | Mjolnir | Blunt, Elemental |
| 10 | T-Shirt Cannon | Gun | | 32 | Excalibur | Blade, Elemental |
| 11 | Rocket Launcher | Gun, Explosive | | 33 | Pandora's Box | Elemental, Explosive |
| 12 | Boomerang | Thrown, Trick | | 34 | Medusa's Head | Elemental |
| 13 | Kunai | Thrown | | 35 | Crystal Ball | Elemental |
| 14 | Molotov | Thrown, Explosive | | 36 | Reaper's Scythe | Blade |
| 15 | Egg | Thrown, Culinary | | 37 | Poseidon's Trident | Blade, Thrown |
| 16 | Steak | Blunt, Culinary | | 38 | Storm Bow | Elemental |
| 17 | Rubber Duck | Trick, Elemental | | 39 | Shadow Daggers | Blade |
| 18 | Deck of Cards | Thrown, Trick | | 40 | Vampire Blade | Blade |
| 19 | Boxing Gloves | Blunt | | 41 | Ray Gun | Gun, Elemental |
| 20 | Cinder Block | Blunt, Tool | | 42 | Pizza Cutter | Blade, Culinary |
| 21 | Yo-Yo | Trick | | | | |

Members per type: Blade 8 (4 Godly), Blunt 10, Gun 8, Thrown 8, Explosive 3, Elemental 10, Tool 7, Culinary 5, Trick 6. Every Elemental member already has the elemental flag and every Tool member already has the utility flag, so those sets never promise scaling a weapon can't use.

### Set bonuses (running totals at 2 / 3 / 4 / 5 / 6 equipped)

Every set gives its weapons the same damage curve: **+4 / 7 / 10 / 13 / 15% damage**. A weapon with two types gets only the higher of its two curves, never both. On top, each type has one flavor bonus:

| Type | Flavor bonus | Scope |
|---|---|---|
| Blade | +2 / 4 / 6 / 8 / 10 crit chance | Blade weapons |
| Blunt | +1 / 1 / 2 / 2 / 3 armor | You |
| Gun | +1 projectile from 4 copies | Gun weapons (every Gun member supports extra projectiles) |
| Thrown | +5 / 10 / 15 / 20 / 25% projectile speed | Thrown weapons |
| Explosive | +10 / 20 / 30 / 40 / 50% blast radius | Explosive weapons |
| Elemental | +3 / 6 / 9 / 12 / 15 burn chance | Elemental weapons |
| Tool | +4 / 8 / 12 / 16 / 20 utility power | You (also boosts turrets) |
| Culinary | Hits heal 2 / 3 / 4 / 5 / 6% of their damage | Culinary weapons (existing life-steal cap) |
| Trick | +2 / 4 / 6 / 8 / 10 dodge | You |

Example: Brawler with Katana, Kusarigama, Bat, Gloves, Nunchucks, Cinder Block is Blade 2 and Blunt 4. The Katana gets +10% specialty and +4% damage and +4 crit chance from Blade 2. The Bat gets +10% specialty and +10% damage from Blunt 4. You get +2 armor.

Why one shared curve: the first version gave Blade, Blunt and Tool only crit, armor or utility power, so full Brawler and Handyman rosters came out 13-14% weaker than before while guns gained 5-10%. That pushed balance toward ranged, the opposite of the earlier "ranged weapons dominate" feedback. The curve follows the items audit budget (section 5d): x1.10 specialty times about +15% is today's x1.25-1.28 own-class package.

Only the Gun set grants a projectile, because only its members all support one. No set gives pierce, bounce or range.

Class identity that isn't class fit stays: Handyman's Utility Power gain x1.25 and free turret, Juggler's +15% attack speed buff, Gunner's +10% ranged attack speed, Brawler's dash.

What gets removed: the ClassFit matrix (step 8 of the damage pipeline), each class's `two`/`four` home bonuses, and `AlsoClasses`/`HOME_MOVED`. A pure balance test compares the old and new totals on the same builds (see Testing).

## Chef

Description: "Kitchen fighter: sturdy, heals well, and kills with Chef weapons sometimes drop pizza. Thin armor."

| Buffs | Drawback |
|---|---|
| +15 max HP, +10% melee damage, +25% recovery (more healing from pizza, regen and life steal) | -3 armor |

The drawback never weakens Chef's own weapons, which follows the rule the other classes use. No dash. Class icon: Frying Pan render.

Ability, pizza drops:

- When a Chef player kills an enemy with a Chef weapon, there is an 8% chance a pizza slice drops where the enemy died.
- Any living player in the run who touches it heals 10% of their max HP. The server checks the distance and that the slice is still there; the client only shows it.
- A slice lasts 12 s and blinks for its last 3 s. At most 4 slices per Chef can be on the ground; the oldest goes when a fifth drops. At least 1.5 s between drops per Chef, so fast weapons don't flood the map.
- Slices bob and spin on the client. Flat ground ring decal, no 3D effect meshes.
- Works in Studio practice (healing is not a persistent reward).

## Pizza Cutter (id 42)

| Field | Value |
|---|---|
| Rarity | Legendary (Chef's only Legendary; every other class has at least one) |
| Authored profile | 13 damage, 0.70 s, 10 studs reach (before rarity power: about 18.6 DPS, like Katana and Steak; shorter reach than Katana, faster hits) |
| Kind / attack | Melee SWING. Styles alternate Diagonal and Thrust, which already exist in `WeaponMotion` (Katana uses them). No new arm poses, so no new joint risk |
| Wheel | Spins on its axle while the cutter moves, in the direction it travels, faster during the strike, coasting to a stop at rest. Same per-frame bone/part rotation approach as the Pandora lid, in both the combat client and the Armory showcase |
| Tier IV move | "Rolling Slice": every 4th swing a ghost wheel rolls 20 studs forward along the ground and hits everything in its lane for 60%. Scales with Area Size like the other Legendary moves. Flat painted visual, no shaded effect mesh |
| Types | Blade, Culinary |
| Flags | Not elemental, not utility |

The exact numbers are checked by WeaponBalanceTests against Katana, Steak and the other Legendaries (DPS band and reach) before shipping.

Model: `weapon-models/assets/42-pizza-cutter/`. Separate Wheel mesh spins on its axle while the Handle stays put.

Checklist for a new melee id (weapons audit section 8): catalog entry, template in the weapon templates folder (installed without the "exactly 36" assert that would wipe the Godly templates), held model, showcase model, icon render, journal entry, chest and drop pools, tier and upgrade costs.

## Starter rules

A run can start with weapon W for class K only if the player owns W and either W's starter class is K, or W is Godly. The server rejects anything else. A saved starter that is no longer valid (e.g. Frying Pan on Brawler) resets to the class's default starter.

## Save, product and quest migration

Saves have no version number. Changes are idempotent fix-ups in `ProfileService.load`, the same style as the chest renames and keys-to-emeralds. The Thrower one:

1. `data.classes.Thrower` → `data.classes.Chef = true`, then remove `Thrower`.
2. `data.loadout.class == 'Thrower'` → `'Chef'`.
3. Quest records: `classWins.Thrower` → `classWins.Chef`. `unlocks.WaveRider` stays claimed (its reward is now Chef).
4. If the saved starter is no longer valid for the saved class, reset it to that class's default. Example: Brawler + Frying Pan → Brawler + Boxing Gloves.
5. The existing "every owned class owns its default starter" backfill then grants Frying Pan to Chef owners and Boxing Gloves to Brawler owners. No weapon, copy or tier is ever removed.

Fresh profiles own Brawler, Gunner and Mage with Boxing Gloves, Glock and Magic Staff.

Products: the `ClassThrower` entry keeps its key and product id (deleting it would leave retried receipts stuck as NotProcessedYet forever) and now grants `class='Chef'`. Store text and product images say Chef. The user renames the product on the Creator dashboard.

Quest: WaveRider (wave 10 on Pine Valley) rewards Chef.

Tutorial: Brawler + Boxing Gloves. The seeded upgrade copies and the guide step move from Pan to Gloves. TutorialConfig is shared with the Round 10 session, so that edit goes in as a coordinated hunk.

Fixture tests cover: Thrower only, Juggler only, both, Thrower selected, Brawler + Pan saved, fresh profile, receipts for ClassThrower.

## Items

From the [items audit](2026-10-09-roster-audit-items.md) section 6, adopted as written unless noted.

**New family items** (Tier I, base 16, cap 5, reuse the level-up icons). Names are working names taken from the art; the user can rename them.

| Id | Name | Effect | Offered when |
|---|---|---|---|
| `knee` | Knee of Justice | +12% melee damage | You carry a melee weapon |
| `fingercannon` | Finger Cannon | +12% ranged damage | You carry a non-melee weapon or a throwing hybrid |
| `pocketweather` | Pocket Weather | +10% elemental damage (also all burn and poison) | You carry an elemental weapon or have burn/poison chance |

**Toolbelt** stays the Utility item: +10 Utility Power (was 6), base 16 (was 18), only offered when you carry a utility weapon or own a turret.

**Keep** Protein, Nightmare, Ball and Chain, Crown (they make mixed builds work). Ball and Chain's preference tag becomes Damage only.

**Availability:** Sharp Pencil Tier III → II (base 42). Two Straws Tier IV → III (base 90). Bouncy Ball Tier IV → III (base 80). All stay cap 1.

**Shop preference** stops using classes. 15% of item rolls prefer items that work with what you have equipped (attack family and weapon types, counted by copies), drawing from the rolled tier or lower. Weapon offers prefer weapons that share a type with an equipped copy; the 10% same-weapon merge roll stays. Turret preference folds into the Tool type.

**Text fixes:** every replacement in items audit 6.4 (Bouncy Ball, Sharp Pencil, Two Straws, Battery Pack with its code fix so lightning weapons get +1 target from the first copy, Ketchup, Sock, Penny, Toolbelt, the level-up Melee/Ranged lines, card kind label "Utility" → "Item"). Duck and Washer cards stop claiming bounce/pierce: new traits `spray` and `stream` with their own lines.

**Streams:** Area Size now widens the Duck cone, the Washer width and the Vacuum width, so Hot Sauce helps them. Shop "works with" follows.

Not adopted yet: the optional Ball and Chain melee rework and the level-up pool weighting (wait for play tests).

## UI

Mockups in `roguelite-planning/previews/roster-types-mockup/` first, built from the real nine-slice theme and real icons. Type chips use literal weapon icons (Blade = Katana, Blunt = Bat, Gun = Glock, Thrown = Kunai, Explosive = Rocket, Elemental = Crystal Ball, Tool = Shovel, Culinary = Frying Pan, Trick = Deck of Cards).

- Class screen: role, exact buffs and drawbacks, specialty, ability (Chef pizza, Brawler dash, Handyman turret).
- Armory: still grouped by starter class, arrows follow the visible grid. Detail card shows starter class, types, attack and scaling, specialty.
- Starter picker: only owned weapons of the chosen class plus owned Godlies.
- Shop: weapon offers show types and the set step they would reach.
- In-run stats: a Sets section with active sets, counts and current totals.

## Testing

Pure tests through the project's existing runners; Studio checks in Edit mode only. The user play-tests. Every Studio sync uses the guarded all-or-nothing write.
