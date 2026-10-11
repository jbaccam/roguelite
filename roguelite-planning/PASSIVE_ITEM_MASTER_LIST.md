# Passive item master list

Updated: 2026-09-23. Current working roster: **37 temporary shop passives**, separate from the 36 weapons and from free level-up stat upgrades. This catalog supersedes earlier brainstorm lists; unlisted brainstorm candidates are not in the roster.

**2026-10-03 (implemented shop, repo only):** the run shop (`ShopCatalog`) now has **44 items**: these 37 plus seven player buffs (Banana Peel, Couch Cushion, Lucky Penny, Chicken Soup, Roller Skates, Metal Detector, Vitamin Gummies). Marshmallow, Peas, Stinky Sock, Oven Mitt and Ice Cube now cause their own status, and Bone Crown also adds 5% damage, so the numbers below for those rows are out of date. Current numbers: [Shop gameplay readiness](studio-prototype/combat/SHOP_GAMEPLAY_READINESS.md).

**2026-10-10 (repo only, not in Studio, not play-tested):** two play-test changes. **Windshield Wiper** (new, row 38) is the melee answer to Two Straws: every melee swing swings again, back the other way, for 60% damage. **Grandma's Coupons** now take 10% off per copy, up to 3 copies (was 5% per copy, up to 5). Details and numbers: [Shop gameplay readiness](studio-prototype/combat/SHOP_GAMEPLAY_READINESS.md#windshield-wiper-and-stronger-coupons-2026-10-10).

The user approved the simpler direction and requested a few spooky/science additions, including Tooth Fairy's Teeth Collection. The five additions selected here are working selections; all numeric values are starting proposals awaiting balance tests, not implemented mechanics. Existing healing/status concepts retain their intended behavior with unresolved numbers explicitly marked TBD.

## Rules

- Mostly straightforward build benefits; occasional modest drawbacks and a small set of major attack modifiers. Funny or strange art does not require random mechanics.
- Some passives appear as avatar accessories. This updates the earlier invisible-passive direction. Worn armor sets now also exist (see PROGRESSION_AND_SESSION_FLOW.md); the rule for which renders when a passive accessory and an armor piece share a spot is still open. Appearance is illustrative; it does not confer a second bonus. Duplicate copies need not duplicate their visible accessory.
- **Unlocks (2026-09-26 proposal):** About 20 passives are in the run shop pool from the start; the rest unlock through achievements (e.g. Tinfoil Antlers, Grandma's Oven Mitt, Two Straws One Juice Box, Bone Crown). Locked passives never appear in shops.
- Items reset after the run and do not consume active weapon slots. Prices, rarity, copy caps and final stacking rules remain to be tuned unless a proposed cap is stated below.
- Damage means the general damage multiplier called Power in the older master stat proposal. Critical Chance uses percentage points: +4 points changes 10% to 14%. Armor and Luck use stat points. Critical Damage bonuses below add percentage points to the critical damage multiplier.
- Projectile count, bounce, pierce, attack range, area radius and status modifiers apply only to compatible attacks; tooltips must identify affected equipped weapons. No free projectile from a melee swipe, and no bounce recursion or unlimited repeated targets.
- Status amplifiers do not grant the status themselves. Final status proc rates, tick values, stacking and boss slow rules still require specification. The Recovery versus separate regeneration/life-steal stat decision remains open.
- No new Accuracy, enemy-attention, Curse or Harvesting systems are implied by these items.

## Straight bonuses — 15

| # | Item | Proposed effect | Avatar appearance |
| ---: | --- | --- | --- |
| 1 | Protein Shake | +8% Damage | — |
| 2 | Emergency Cheese | +5 Max HP | — |
| 3 | Emotional Support Potato | +8 Max HP and +10% Pickup Radius | Potato on back |
| 4 | Crocs in Sport Mode | +6% Movement Speed | Footwear; working name, final branding unresolved |
| 5 | Sweaty Headband | +8% Attack Speed | Headband |
| 6 | Comically Large Glasses | +15% Attack Range | Glasses |
| 7 | Pot Lid | +2 Armor | Hat |
| 8 | Lucky Sock | +10 Luck | Belt accessory |
| 9 | Fridge Magnet | +25% Pickup Radius | — |
| 10 | Grandma's Coupon Stash | −10% new shop offer prices per copy, up to 3 copies (30% at most). Was −5% per copy, 5 copies (2026-10-10) | — |
| 11 | Emotional Support Ketchup | +15% Explosion Damage | — |
| 12 | Hot Sauce | +15% Explosion and Status-Area Radius | — |
| 13 | Microwaved Marshmallow | +20% Burn Damage | — |
| 14 | Freezer-Burned Peas | +25% Slow Duration | — |
| 15 | Stinky Sock in a Bag | +20% Poison Damage | Belt accessory |

## Modest tradeoffs — 5

| # | Item | Proposed effect | Avatar appearance |
| ---: | --- | --- | --- |
| 16 | Energy Drink | +15% Attack Speed; −3 Max HP | — |
| 17 | Safety Helmet | +3 Armor; −3% Movement Speed | Hard hat |
| 18 | Broken Glasses | +6 points Critical Chance; −10% Attack Range | Cracked glasses |
| 19 | A Literal Ball and Chain | +15% Damage; −5% Movement Speed | Small ankle accessory; not the Wrecking Ball weapon |
| 20 | School Backpack Full of Rocks | +12 Max HP; −4% Movement Speed | Backpack |

## Special build modifiers — 6

| # | Item | Proposed effect | Proposed limit / appearance |
| ---: | --- | --- | --- |
| 21 | Two Straws, One Juice Box | +1 projectile per eligible weapon attack | 1 copy; highest rarity; inventory only |
| 22 | Government-Issued Bouncy Ball | +1 enemy bounce; added bounce deals 60% of original hit damage | 1 copy; Tier 4; inventory only |
| 23 | Suspiciously Sharp Pencil | +1 enemy pierced; added piercing hit deals 70% of original hit damage | 1 copy; inventory only |
| 24 | Tinfoil Antlers | Lightning chains hit +1 enemy | 2 copies; head accessory |
| 25 | Grandma's Oven Mitt | When a burning enemy dies, its burn spreads to +1 nearby enemy | 1 copy; belt accessory; propagation rules TBD |
| 26 | Bubble Wrap Vest | Block the first damaging hit each wave | 1 copy; Tier 4; torso accessory |
| 38 | Windshield Wiper (2026-10-10) | Every melee swing swings again, back the other way, for 60% damage; a 2nd copy adds a 2nd extra swing (1 on very fast weapons) | 2 copies; Tier 3, base 80; melee builds only; inventory only; needs its own icon |

Bounce/pierce reductions affect the added hit, not all player damage. Interactions with weapons' existing bounce/pierce falloff require a single defined calculation before implementation; do not silently apply two falloff penalties.

## Existing healing and status foundations — 6

| # | Item | Retained effect | Numbers still to specify |
| ---: | --- | --- | --- |
| 27 | Bandage Roll | Passive health regeneration | HP per second; healing stat model |
| 28 | Vampire Fang | Heal for a percentage of damage dealt, with a healing-per-second cap | Percentage and cap |
| 29 | Lighter | Hits can ignite enemies | Proc chance, burn damage and duration |
| 30 | Ice Cube | Hits can briefly slow enemies | Proc chance, slow strength and duration |
| 31 | Battery Pack | Every set number of hits releases a short lightning chain | Hit count, damage, target count; secondary hits cannot recursively trigger it |
| 32 | Toxic Barrel | Hits can apply stacking poison | Proc chance, tick damage, duration and stack cap |

These remain inventory-only for now. They preserve prior planned support for healing, burn, slow, lightning and poison rather than silently dropping it during the consolidation.

## Selected spooky/science additions — 5

| # | Item | Proposed effect | Visual / avatar appearance |
| ---: | --- | --- | --- |
| 33 | Tooth Fairy's Teeth Collection | +15 points Critical Damage | Jar of collected stylized teeth; inventory only |
| 34 | Bottled Nightmare | +12% Damage; −3 Max HP | Tiny shadow face in a corked bottle; inventory only |
| 35 | Cracked Burial Mask | +2 Armor and +10% contact resistance | Stone mask with a glowing crack; face accessory |
| 36 | Alien Battery | +6% Attack Speed and +15% lightning-chain damage | Strange power cell; inventory only |
| 37 | Bone Crown | +15% Damage to Elites and Bosses | Chunky fictional creature bones; head accessory |

Manager Badge was removed because it duplicated Bone Crown's elite/boss bonus. Cracked Burial Mask and Alien Battery now have distinct defensive and lightning roles in the implemented shop.

## Consolidated names

- Running Shoes → Crocs in Sport Mode.
- Horseshoe → Lucky Sock.
- Coupon Book → Grandma's Coupon Stash.
- Charcoal → Microwaved Marshmallow (burn damage focus).
- Snow Globe → Freezer-Burned Peas (slow duration focus).
- Lightning Rod → Tinfoil Antlers.
- Jar of Teeth → Tooth Fairy's Teeth Collection.
- Split Pupil, Echo Skull, Alien Vertebra and Storm Parasite were alternate identities for existing modifiers, not additional roster entries. Other unselected brainstorm ideas remain outside this catalog.

## Regular level-up upgrades — separate from shop items

Free XP-earned stat choices are resolved between waves before the shop. They have no attached penalties and do not create wearable objects. Values below are proposed, not copied assumptions about the implemented stat system.

| Stat | Common | Uncommon | Rare | Legendary |
| --- | ---: | ---: | ---: | ---: |
| Max HP | +3 | +6 | +9 | +12 |
| Damage | +5% | +8% | +12% | +16% |
| Attack Speed | +5% | +8% | +12% | +16% |
| Critical Chance | +2 points | +4 points | +6 points | +8 points |
| Armor | +1 | +2 | +3 | +4 |
| Movement Speed | +3% | +5% | +7% | +9% |
| Pickup Radius | +10% | +20% | +30% | +40% |
| Luck | +5 | +10 | +15 | +20 |

Extra projectile, bounce and pierce remain item/weapon modifiers, not generic level-up cards. Healing upgrade values await resolution of the healing stat model. The vertical slice selects roughly 12–15 passives from this 37-item roster; no modeling or gameplay implementation is authorized merely by this catalog update.
