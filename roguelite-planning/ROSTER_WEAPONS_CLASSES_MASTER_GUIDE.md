# Roster, weapons, classes, and asset master guide

Updated October 9, 2026. Project: **Wavebreaker: Survive the Swarm**. Correct Studio place: **107877054949326**.

This guide consolidates the user's requested redesign and the source audit. It is a specification and implementation checklist, **not a claim that the redesign is already implemented**. Older Thrower/class-tag tables describe the existing game and must not override the newer direction below.

## 1. Decision status

### User requirements to preserve

- Replace the overlapping Thrower role with Chef and retain Juggler as the intended redesign direction. Do not simply rename Thrower or stack its entire bonus package onto Juggler.
- Add **Pizza Cutter**, accepted by the user, as Chef's sixth direct weapon.
- **All starter weapons must be direct weapons of the selected character class.** Do not add a broad Blade starter whitelist for Chef just because a weapon has a blade.
- Classes must remain capable of useful off-class builds during the run. Direct specialty weapons should receive a stronger class benefit, with explicit descriptions.
- Separate character classes from universal weapon types/set bonuses, taking inspiration from the supplied Brotato reference.
- Audit actual attacks and existing item effects before assigning weapon types or numerical bonuses. Kunai is thrown/ranged; Deck of Cards must not lose its thrown identity merely because it is a trick weapon.
- Consider the existing class-organized Armory. Preserve understandable browsing, starter selection, and upgrade ownership.
- Dash eligibility is a character-class rule, not a melee-starter or equipped-weapon loophole.
- Rubber Duck and Power Washer need bursts, actual downtime, gravity-influenced effects, and natural oldest-first effect expiry after emission stops.
- New asset concepts must match the existing low-poly weapon collection.

### Working proposals, not final numerical design

- The detailed single-home roster in section 3 is the current proposed baseline. The user has not separately approved every reassignment.
- The term **signature class** below means the direct class relationship used for starter eligibility, Armory organization, and specialty benefits. The user has not approved this exact data schema or UI terminology.
- Chef as a melee sustain class, Chef receiving dash, its healing-food ability, and Brawler changing default starter to Boxing Gloves are proposals.
- Exact weapon-type assignments, set bonuses, class buffs/debuffs, item additions, rarity, prices, unlocks, and migration compensation remain to be designed and tested.
- Kusarigama's possible thrown-chain behavior has been raised; no specific replacement attack has been approved.

## 2. What exists now versus what is pending

**Update, October 9 night:** implemented and synced to Studio. See [CHEF_ROSTER_2026-10-09.md](studio-prototype/combat/CHEF_ROSTER_2026-10-09.md) for what was built, which tests ran and the play-test list, and [the design decisions](plans/2026-10-09-chef-roster-weapon-types-design.md). The table below is the pre-implementation snapshot.

Source checked October 9 still lists **Brawler, Gunner, Thrower, Juggler, Handyman, Mage**. Chef and Pizza Cutter are not in the runtime catalog.

| Work | Current status |
|---|---|
| Brawler-only dash, independent of starter | Implemented previously; client/server eligibility checks and build passed |
| Class/weapon damage explanations and larger desktop menus | Implemented previously; recorded responsive tests passed |
| Armory arrows follow the visible class-grouped order | Implemented previously |
| Duck/washer burst changes | Source and Studio sync completed October 6; compile/timing checks and build passed |
| Duck/washer live visual validation | Pending: Studio stopped responding during Play start; no claim of a passed live test |
| Remove Thrower/add Chef | Pending |
| Pizza Cutter model, attack, icon, catalog entry | Pending; 2D concept exists |
| Universal weapon-set system | Pending |
| Redesigned starter rules, specialty bonuses, item pool and save migration | Pending |

Recorded implementation details: [menu clarity](studio-prototype/ui/MENU_CLARITY_2026-10-06.md), [Duck bursts](studio-prototype/combat/DUCK_BURSTS_2026-10-06.md), [Washer bursts](studio-prototype/combat/WASHER_BURSTS_2026-10-06.md).

## 3. Proposed direct-class roster

These are **direct class assignments**, not weapon-set tags and not restrictions on mid-run purchases. This baseline gives each ordinary weapon one home; intentional shared homes can be reconsidered, but should not be added merely because a class could hold the object.

| Character | Direct weapons / eligible starters when owned | Count | Intended distinction |
|---|---|---:|---|
| Brawler | **Nunchucks, Katana, Kusarigama, Baseball Bat, Boxing Gloves, Cinder Block** | 6 | Tough melee, knockback, dash |
| Gunner | **Glock, Draco, Fart Gun, Shotgun, T-Shirt Cannon, Rocket Launcher** | 6 | Direct ranged fire |
| Juggler | **Boomerang, Kunai, Rubber Duck, Deck of Cards, Yo-Yo, Bowling Ball, Bowling Pin** | 7 | Unusual attacks, mobility, trick weapons; not every member is literally thrown |
| Chef | **Frying Pan, Spatula, Steak, Egg, Molotov, Pizza Cutter** | 6 | Melee-focused food/kitchen arsenal; recovery playstyle proposed |
| Handyman | **Nail Gun, Wrecking Ball, Shovel, Paint Roller, Vacuum Cleaner, Power Washer** | 6 | Tools, utility, turrets |
| Mage | **Magic Staff, Mjolnir, Excalibur, Pandora's Box, Medusa's Head, Crystal Ball** | 6 | Magic and elemental effects |

**Update, October 10:** Excalibur moved from Mage to **Brawler** (Brawler 7, Mage 5 until the planned spellbook). Pizza drops are a Chef class ability for every Chef weapon, not a Pizza Cutter one. See the Oct 10 section of [CHEF_ROSTER_2026-10-09.md](studio-prototype/combat/CHEF_ROSTER_2026-10-09.md).

Total: **37 ordinary weapons after Pizza Cutter**, versus 36 now. With the existing six Godlies, the complete catalog would contain **43 weapons**. Juggler having seven does not require inventing extra weapons for every other class.

Chef has **four melee weapons** (Pan, Spatula, Steak, proposed Cutter) and **two ranged/throwing weapons** (Egg, Molotov). Molotov is the least direct culinary fit; retain that as an explicit design question rather than claiming every assignment is settled.

Existing Godlies: Reaper's Scythe, Poseidon's Trident, Storm Bow, Shadow Daggers, Vampire Blade, Ray Gun. Keep their models, IDs, ownership and upgrades. **Starter policy needs reconciliation:** today owned Godlies can start with any class, while the user's newest rule requires direct-class starters. Do not silently preserve an exception or invent Godly class memberships. Resolve that mapping/policy before shipping starter validation.

## 4. Separate four concepts

| Concept | Responsibility |
|---|---|
| Character class | Base stats, drawbacks, ability, specialty benefit |
| Direct/signature class relationship | Eligible owned starters and class-based Armory grouping |
| Attack behavior and damage scaling | Melee/ranged/blast/hybrid behavior, actual compatible stats and modifiers |
| Universal weapon types | Equipped-set counts and bonuses available to all characters |

Examples of proposed presentation: **Pizza Cutter: Chef specialty; Culinary / Blade**. **Deck of Cards: Juggler specialty; Thrown / Trick**. **Kunai: Juggler specialty; Thrown**. Examples are not a finalized tag matrix.

An off-class weapon bought during a run still receives its compatible player stats and universal set bonuses. The stronger specialty benefit must be explicit and must not make off-class builds nonviable. Do not introduce both the old class-fit multiplier and a new replacement specialty multiplier by accident.

The old +15% own-class / cross-class percentage matrix and 2/4 home-weapon bonuses require a deliberate replacement plan. Preserve chosen character identity, but do not automatically stack all old bonuses with new 2–6 weapon sets.

## 5. Actual attack audit: constraints on weapon tags

| Weapon | Current mechanics | Rule for the redesign |
|---|---|---|
| Kunai | Ranged thrown projectile; extra copies, pierce and bounce supported | Thrown is appropriate. A melee-damage Blade bonus would not improve its direct damage |
| Deck of Cards | Ranged staggered curved volley; targeting, pierce and bounce | Represent thrown attacks even if a second Trick tag is retained |
| Kusarigama | Currently melee in damage/attack logic; articulated chain | Decide whether to retain its melee sweep or implement an outward chain/weight throw and return. Do not infer mechanics from appearance alone |
| Mjolnir | Melee/elemental scaling with a returning throw | Treat as an explicit hybrid; do not change scaling accidentally when retagging |
| Rubber Duck | Ranged/elemental fire spray | Not an ordinary thrown projectile; no extra-copy/pierce/bounce support currently |
| Power Washer | Ranged/utility stream | No extra-copy/pierce/bounce support currently |
| Guns | Straight projectile fire | No bounce; preserve the prior straight-gunfire fix |
| Returning throws | Pierce/bounce supported; extra copies generally excluded | Set bonuses must remain useful without creating duplicate returning weapons |

**Kusarigama options:** an extending chain-weight attack with a controlled return is a plausible direction using the existing chain rig. Full sickle release is a separate, more involved design. Range limits, near-player hits, wall collision, damage timing, hit frequency, and return behavior need specification and tests. A full real-world disarm simulation is not implied by this request.

## 6. Weapon types and set bonuses: design rules

Candidate vocabulary discussed: Blade, Blunt, Gun, Thrown, Trick, Culinary, Tool, Elemental, Explosive. **This list is provisional.** Some are attack families and some are themes; use multiple tags only where the combination is understandable and the effects are useful.

- A weapon may contribute to more than one set, but avoid tags added only to inflate synergy.
- Plan cumulative total bonuses at 2, 3, 4, 5 and 6 equipped weapons. Show current total and next threshold. Exact values are not chosen.
- Count equipped copies, not unique names, if following the intended six-slot set system. Merging copies changes the equipped count and must recalculate immediately.
- Every set member must have a meaningful use for its set bonus. Do not grant melee-only damage to a ranged Kunai, extra projectiles to a stream, or bounce to a straight gun.
- Do not assume all Thrown weapons support the same modifiers; returning throws and zone projectiles differ.
- Separate thematic set identity from elemental/utility damage flags. Preserve existing elemental and utility support through an explicit authored mapping.
- Choose whether a bonus changes global player stats or only tagged weapon attacks, and display that scope plainly. This is not yet settled.

## 7. Item support and balance work

The source audit found **46 passive/utility shop items plus four turret items**. Counts below are distinct positive-effect items; categories overlap and do not count penalties as benefits.

| Effect | Existing supporting shop items |
|---|---:|
| General damage | 4 |
| Attack speed | 3 |
| Direct melee damage | 0 |
| Direct ranged damage | 0 |
| Direct elemental damage | 0 |
| Utility Power | 1 (Toolbelt) |
| Range | 1 |
| Crit chance / crit damage | 1 each |
| Extra projectiles / pierce / bounce | 1 each |
| Explosion damage / area | 1 each |
| Burn / slow / poison / lightning support | 3 / 2 / 2 / 3 |
| Healing | 4 |

All four specialized damage families already have level-up upgrades: 8/12/18/25%. Zero dedicated shop items does not mean zero progression. Burn/poison proc items can support many characters; they are not exclusively Mage items. Shop preference tags are not effect definitions: an item tagged Melee can still grant general damage.

Required balance work:

1. Build a weapon-to-effective-stat matrix from actual launchers/damage code, including tier-IV special behavior.
2. Count usable item choices by early/mid/late wave bands, tier, price, copy cap, and probability of being offered—not just by raw catalog count.
3. Design comparable support for melee, ranged, elemental and utility builds. Proposed new passive items need names/art only after exact effects are chosen.
4. Audit stream-compatible upgrades separately; adding three projectile items does not support Duck/Washer.
5. Compare off-specialty and on-specialty builds using the same budget, tiers and item access. Record damage per hit, effective attacks per second, crowd coverage, healing/proc rate, and hits to kill.
6. Include Normal, Hard and Nightmare, map power matching, and one-to-four-player encounters. Test early starters as well as six tier-IV weapons; do not tune around only a fully upgraded Draco build.

Equal access to useful upgrades is the objective. Equal item counts alone are not evidence of balance. The final added/rebalanced item list and numerical targets remain open.

## 8. Rubber Duck and Power Washer changes

Implemented source behavior awaiting the recorded live validation:

- **Duck:** three short flame pulses, fixed burst heading, minimum 0.78-second cycle; high attack speed cannot erase the rest. Released particles move independently, fall under mild gravity, and expire by age. Damage compensation targets previous nominal sustained DPS; proc opportunities may differ and need measurement.
- **Washer:** 0.8 seconds full pressure, 0.2 seconds trickle, 0.4 seconds refill. Water retains its trajectory after turning/shutoff and falls; low pressure emits smaller, slower drops. No persistent beam snapping off. Damage uses a normalized pressure envelope; actual tick integration needs live verification.
- Existing duck and washer meshes are reused. The Armory showcase was updated to use the new behavior. Vacuum remains continuous.

Studio Play validation must check six equipped copies, turns, target loss, pause, death, selling/replacing weapons, multiple players, gravity, natural expiry, wall behavior, frame cost, and displayed attack information. Pure tests do not establish visual quality or live DPS balance.

## 9. UI, progression and save migration

- Keep Armory class grouping meaningful using direct class ownership. Preserve previous/next order matching the visible grid. Show weapon types separately on detail cards.
- Class screen explains role, exact buffs/drawbacks, specialty bonus, and dash. Starter screen shows only owned eligible direct weapons; server rejects invalid requests.
- Shop leads with weapon types, attack/scaling information, current set progress, and explicit specialty effect. Avoid ambiguous +/- percentages.
- Replace Thrower references throughout menus, shop weighting, quests, gifts, products, tutorial, admin choices, journal and tests—not just the visible class name.
- Preserve every existing weapon ID, copy count, tier and saved record. Append a new stable Pizza Cutter ID; do not repurpose an existing weapon ID.
- Migrate saved Thrower class selections and entitlements explicitly. Handle players owning Thrower, Juggler, or both; preserve the value of prior unlocks/purchases. Exact grant/compensation policy needs a decision.
- Preserve historical receipt handling for the existing ClassThrower product. Do not reuse its receipt mapping for Chef without a deliberate entitlement policy.
- Choose Chef's unlock, default starter and price, and revise Thrower's wave-10 quest reward. If Pan becomes Chef's direct starter, resolve the current Pan tutorial/default Brawler loadout rather than leaving an invalid starter.
- Studio practice must never award persistent rewards or use production DataStores.

## 10. Model and image asset list

| Asset | Needed? | Work |
|---|---|---|
| **Pizza Cutter weapon** | Yes for the proposed Chef roster | New low-poly mesh, texture, separate rotating wheel/axle pivot, grip/root, hit geometry, icon render and showcase |
| Chef healing-food pickup | Optional; ability not approved | Pizza-slice concept supplied; only model it if the chosen ability requires a pickup |
| Chef character body | No | Players use their Roblox avatars; class does not imply a new character model |
| Chef class icon | Yes when implemented | Reuse/render the selected signature weapon; an extra hat/body model is not required |
| Pan, Spatula, Steak, Egg, Molotov | Reuse | Existing models; update catalog relationships and UI metadata |
| Duck and Power Washer | Reuse | Burst VFX/behavior changes, not replacement meshes |
| Kusarigama | Reuse first | Existing chain rig; additional rig/export work only if the approved attack needs it |
| Weapon-type icons | Needed for chosen types | Small UI assets, not 3D models; finalize vocabulary first |
| New passive-item artwork | Pending item design | Usually card icons, not held weapon models; exact list not yet chosen |

**Minimum new 3D model count: one—Pizza Cutter.** Two if a distinct Chef food pickup is selected. Existing weapons should not be rebuilt solely because they change class.

Art direction: chunky low-poly silhouettes, restrained facets, warm wooden handles, muted gray metal, simple base-color textures, readable shape at gameplay size. No sudden switch to photorealism, intricate ornamental fantasy detail, or neon sci-fi treatment. Pizza Cutter needs a separate wheel that rotates without moving the handle. AI sheets are visual concepts, not validated orthographic blueprints or exportable models.

### Original asset sources and reference images

- [Complete existing weapon reference sheet](weapon-models/Weapon_Overview.jpg)
- [Melee/kitchen reference sheet: Pan, Spatula, Katana, Kusarigama](weapon-models/Weapon_Review_01.jpg)
- [Existing weapon asset directory and import documentation](weapon-models/README.md)
- [Rigging/component guide](weapon-models/RIGGING_GUIDE.md)
- [Frying Pan source](weapon-models/assets/01-frying-pan/README.md)
- [Spatula source](weapon-models/assets/05-spatula/README.md)
- [Steak source](weapon-models/assets/16-steak/README.md)
- [Egg source](weapon-models/assets/15-eggs/README.md)
- [Molotov source](weapon-models/assets/14-molotovs/README.md)
- [Kusarigama source](weapon-models/assets/04-kusarigama/README.md)
- [Duck source](weapon-models/assets/17-rubber-ducks/README.md)
- [Power Washer source](weapon-models/assets/29-power-washer/README.md)

Those per-asset folders contain existing source/export/render files as documented by their README. Reuse the actual working Studio assets; older asset-preparation notes are not proof of the current import state.

### Generated concepts and provenance

Generated October 9 with the built-in image-generation tool, using the original review sheets above as style references. No 3D asset was generated or imported.

- [Pizza Cutter concept sheet](weapon-models/concepts/chef-2026-10-09/pizza-cutter-concept.png)
- [Optional Chef pizza-slice pickup concept](weapon-models/concepts/chef-2026-10-09/optional-chef-pickup-concept.png)
- [Exact generation prompts and reference paths](weapon-models/concepts/chef-2026-10-09/generation-prompts.json)

![Pizza Cutter modeling concept](weapon-models/concepts/chef-2026-10-09/pizza-cutter-concept.png)

![Optional Chef pickup concept—not an approved ability](weapon-models/concepts/chef-2026-10-09/optional-chef-pickup-concept.png)

## 11. Implementation order and acceptance checks

1. Finalize direct roster, Godly starter policy, class specialty scope, Chef ability, Kusarigama behavior and universal type vocabulary.
2. Author independent attack/scaling flags before removing existing class memberships. In particular, current Mage/Handyman memberships help determine Elemental/Utility flags; dropping them blindly would change damage.
3. Add data and calculation tests for signatures, allowed starters, type counts, duplicate/merged weapons, hybrid scaling, unsupported modifiers, and off-class builds.
4. Implement Chef, weapon sets and class bonuses together with the agreed item-support changes. All effects and remote actions remain server-validated.
5. Build/import Pizza Cutter and wire its tiers, hit cadence, spinning-wheel animation, drop pool, copies, upgrade costs, icon, journal and showcase.
6. Update Armory, selection screens, shop and tutorial. Preserve responsive desktop/mobile readability and real grid navigation order.
7. Implement and test save/product/quest migration using fixtures. Old purchases and equipment must not disappear.
8. Run comparative damage/kill-time and acquisition simulations, then actual solo/co-op Studio playtests. Document test conditions, not just a pass count.
9. Sync only the roguelite overlay to place 107877054949326; preserve the map and unrelated instances. Build with `rojo build roguelite-planning/studio-prototype/combat/default.project.json -o build/RogueliteKatanaCombat.rbxlx`.

No new balance percentages, final passive items, Chef healing mechanic, or Godly exception should be inferred as approved solely from an example in this guide.

## 12. Implementation source map

| Area | Current source |
|---|---|
| Weapon identity, tiers and flags | [WeaponCatalog](studio-prototype/combat/WeaponCatalog.luau) |
| Class buffs, fit, dash, compatible stats, damage | [CharacterStats](studio-prototype/combat/CharacterStats.luau) |
| Starter validation and class unlocks | [RunSetupRules](studio-prototype/lobby/RunSetupRules.luau) |
| Item effects and compatibility text | [ShopCatalog](studio-prototype/combat/ShopCatalog.luau) |
| Shop offer selection | [ShopService](studio-prototype/combat/ShopService.luau) |
| Level-up offense support | [LevelUpCatalog](studio-prototype/combat/LevelUpCatalog.luau) |
| Saved ownership and default signatures | [ProfileService](studio-prototype/combat/ProfileService.luau) |
| Paid class products and receipts | [MonetizationConfig](studio-prototype/combat/MonetizationConfig.luau), [RogueliteMeta](studio-prototype/combat/RogueliteMeta.server.luau) |
| Unlock quests | [QuestConfig](studio-prototype/combat/QuestConfig.luau) |
| Menus | [RunSetupUI](studio-prototype/ui/RunSetupUI.luau), [ArmoryUI](studio-prototype/ui/ArmoryUI.luau), [ShopUI](studio-prototype/ui/ShopUI.luau) |
| Throws / cards / stream attacks | [SpecialWeapons](studio-prototype/combat/SpecialWeapons.luau), [ArcProjectiles](studio-prototype/combat/ArcProjectiles.luau), [UtilityWeapons](studio-prototype/combat/UtilityWeapons.luau) |

External inspiration supplied by the user: [Brotato weapon classes](https://brotato.wiki.spellsandguns.com/Weapon_Classes). The pasted table is reference material, not a direction to copy its numerical bonuses or shop probabilities into this game's differently scaled stats.
