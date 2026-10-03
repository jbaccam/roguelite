# Current Game Structure

**Status:** Consolidated pre-production plan  
**Updated:** 2026-09-26  
**Scope:** What the game currently is, what content belongs to it, and what still needs design work.

This is the fastest document to read for the complete current plan. [PROGRESSION_AND_SESSION_FLOW.md](PROGRESSION_AND_SESSION_FLOW.md) is authoritative for progression, maps, keys, chests, armor and achievements. The master design and specialist documents contain the deeper reasoning. **Confirmed** items came directly from project direction. **Proposed** items are the strongest current recommendation and can still change.

**Architecture:** Future mobs and combat use server-owned enemy simulation with client-only enemy visuals. See [Enemy simulation and combat architecture](ENEMY_SIMULATION_ARCHITECTURE.md). The Studio prototype already has automatic weapon combat, six weapon slots, crystal shards, run XP, level-up choices and the between-wave shop. Hundreds of enemies remains a performance goal that still needs measurement.

## 1. Game identity

**Confirmed:** A funny, three-dimensional Roblox survivor roguelite played as the player's normal Roblox avatar. There is no roster of replacement heroes. A player picks a class, a starting weapon, armor pieces and a pet, enters one of five maps, automatically attacks crowds, builds up weapons and stats between waves, and tries to survive to wave 20. The player can then keep going in Endless or cash out, and returns to the lobby with keys to open chests.

The comedy comes from using serious and ridiculous equipment together: a Katana beside a Frying Pan, a Glock beside a Fart Gun, or Mjolnir beside a Spatula.

**Session target:** Twenty waves, roughly 15–20 minutes including level-ups and shops. It should be comfortable to play while listening to music or an audiobook. Ordinary enemies should not require precise aiming.

## 2. Complete player journey

```text
First join as Roblox avatar
  -> short guided tutorial with one fixed weapon (three waves + easy boss)
  -> result screen grants keys for one chest
  -> lobby: open first chest, choose class, starting weapon and armor
  -> Pine Valley: survive to wave 20 and beat the Hammer Zombie Boss
  -> Cash Out, or Keep Going into Endless for more keys
  -> keys open chests; duplicate copies raise starting tiers
  -> winning a map on Hard unlocks the next, harder map (Normal / Hard / Nightmare per map)
  -> achievements and quests unlock specific classes, weapons, passives and armor
```

See [Lobby and first-run flow](LOBBY_AND_FIRST_RUN.md) for the tutorial and lobby detail.

## 3. Run structure

### Before entering

The player selects:

1. A class.
2. One owned starting weapon from that class, entering at its saved tier (I–IV).
3. Owned armor pieces: helmet, chestplate, leggings and boots (**confirmed 2026-09-27:** individual pieces, not one outfit).
4. An unlocked map.

### During a run

- The avatar moves freely in an open arena while up to six equipped weapons attack automatically.
- Every mob death drops a blue crystal worth shards and run XP. See [Crystal shard currency](SHARD_CURRENCY.md).
- Level-ups are banked during combat and never interrupt it.
- At the end of each wave, drops pull in. Leftover value goes into the shard bag.
- Banked level-ups resolve as four stat cards (reroll costs shards).
- A four-offer shop sells weapons and passive items. The player can buy, reroll, lock, recycle and combine.
- The map boss on wave 20. (Elite and horde waves were planned for 5, 10 and 15 but not built; their run-setup labels were removed for launch, 2026-10-02.)
- **Win:** The wave 20 boss dies. Then the player can Keep Going into Endless.
- **Loss:** The player keeps the keys earned for waves already passed.

### What resets after a run

Run level and XP, stat choices, extra weapons, in-run weapon tiers, passive items, shards and shard bags, rerolls and locks.

### What saves permanently

Owned weapons and armor with their copy counts / starting tiers, unlocked classes, map wins and best wave per map, keys and unopened chests, achievement and quest progress, unlocked passives, cosmetics and settings.

## 4. Classes and complete weapon roster

There are **six classes with six home weapons each**, for **36 weapons**. Every weapon belongs to exactly one "home" class. A class decides which owned weapons can be the starting weapon and which weapons count toward its affinity bonuses. It does **not** stop the player from buying other classes' weapons during a run.

### Starting access

New accounts own **Brawler, Gunner, and Mage**. **Thrower, Juggler, and Handyman** unlock through early achievements, or through an optional early purchase. The intended pace is one new class within the first few runs.

| Class | Play style | Signature starter | Other home weapons |
| --- | --- | --- | --- |
| **Brawler** | Close-range arcs, orbiting protection, durability | **Frying Pan** | Nunchucks, Katana, Kusarigama, Spatula, Baseball Bat |
| **Gunner** | Fast projectiles, magazines, piercing and spread | **Glock** | Draco, Fart Gun, Shotgun, T-Shirt Cannon, Rocket Launcher |
| **Thrower** | Returning projectiles, volleys, area denial | **Boomerang** | Kunais, Molotovs, Eggs, Steak, Deck of Cards |
| **Juggler** | Orbitals, rebounds, repeated contact and knockback | **Boxing Gloves** | Rubber Ducks, Cinder Blocks, Yo-Yo, Bowling Ball, Bowling Pins |
| **Handyman** | Construction tools, deployables, lanes and utility | **Nail Gun** | Wrecking Ball, Shovel, Paint Roller, Vacuum Cleaner, Power Washer |
| **Mage** | Elemental zones, chain effects, mythic late unlocks | **Magic Staff** | Mjolnir, Excalibur, Pandora's Box, Medusa's Head, Crystal Ball |

### Class and off-class rules

- A class supplies one always-active specialization, even when using off-class weapons.
- Every weapon has one **home class** and two or more **combat tags**.
- Any class may buy any owned weapon during a run.
- Off-class weapons keep their full base behavior and can receive bonuses through shared tags.
- **Two** equipped home-class weapons activate the class's first affinity bonus. **Four** activate its stronger bonus. With six slots, two stay flexible for off-class weapons.
- Example: Nail Gun belongs to Handyman but also has Gun, Rapid and Projectile tags, so a Gunner can roll it and benefit from Gun-tag effects.

**Current class values:** [Character stat implementation](studio-prototype/combat/CHARACTER_STATS.md) is authoritative. It implements six class presets with explicit buffs and debuffs, home-weapon affinity bonuses, and 46 visible stats.

## 5. Weapons, armor and upgrades

### Presentation rule

Equipped weapons stay visible as floating 3D models around the avatar. The avatar holds no weapon and keeps its normal movement animations. Each weapon aims at eligible enemies on its own and attacks on its own cooldown, then recovers to its slot. **Six** slots sit in a fixed arrangement around the avatar and do not orbit. See [FLOATING_WEAPON_PRESENTATION.md](FLOATING_WEAPON_PRESENTATION.md) and [LOADOUT.md](studio-prototype/combat/LOADOUT.md).

### In-run tiers (temporary)

- Up to **six** equipped weapons.
- Two copies of the same weapon and tier combine into the next tier, up to **Tier IV**.
- Every tier changes behavior, silhouette, projectile pattern or utility, not only damage.

The Glock is the approved model for upgrade quality:

| Tier | Form | Behavioral upgrade |
| --- | --- | --- |
| I | Glock | Basic semiautomatic fire |
| II | Glock + Extended Clip | Larger magazine and less reload downtime |
| III | Glock with Switch | Automatic bursts and a denser firing stream |
| IV | Akimbo Switches | Two firing streams with improved crowd coverage |

### Permanent progression (saved)

- **Ownership:** Having one copy of a weapon means you own it. Owned weapons can be the starter (for their class) and appear in run shops.
- **Starting tier:** Copies from chests stack on the same rule as in-run combining: 2 copies = Tier II start, 4 = Tier III, 8 = Tier IV.
- **Armor (confirmed 2026-09-27):** Four piece slots: helmet, chestplate, leggings and boots. Pieces drop from armor chests. Each piece gives defensive stats. Wearing 2 pieces of one set gives its set bonus, and all 4 give its signature perk, so completing a set is a longer grind. Tiers I–IV use the same copy rule per piece.
- **Pets (planned):** One pet slot. Pets hatch from pet eggs (pets only) and follow the player into runs. Copies level them up.

Full rules, chest types, key values and pacing targets: [PROGRESSION_AND_SESSION_FLOW.md](PROGRESSION_AND_SESSION_FLOW.md).

## 6. Between-wave shop

Four offers each intermission. Buy, reroll, lock, recycle, and automatic legal combining. All prices use crystal shards, which are temporary run money and never Robux or saved currency.

The **current implemented rules** are in [Shop gameplay readiness](studio-prototype/combat/SHOP_GAMEPLAY_READINESS.md):

- Shops 1–2 have two weapons and two items. Shops 3–5 guarantee one weapon. Later slots roll 35% weapon / 65% item.
- Owned weapon identities and home classes get a modest pool preference. The general pool always stays available.
- Luck raises tier chances within caps. No paid purchase changes shop odds.

**Still planned:** A player can **Track** one equipped weapon to protect against duplicate starvation. Offer cards will show why they appeared (**DUPLICATE, CLASS, TAG MATCH, WILDCARD**). Tier unlock waves (currently Tier IV from wave 8) need retuning for 20-wave runs.

## 7. Stats and passive items

A **passive** is a temporary shop item that modifies the run without using a weapon slot or attacking on its own. It resets after the run.

The working roster is [PASSIVE_ITEM_MASTER_LIST.md](PASSIVE_ITEM_MASTER_LIST.md): **37 passives**. About 20 are proposed as available from the start. The rest unlock through achievements. Some passives appear on the avatar as hats, glasses or backpacks.

Level-up stat choices are free and happen between waves as four cards. They are separate from shop items.

## 8. Maps, mobs and bosses

The five maps form the difficulty ladder. Each map is harder and pays more keys than the one before. The current roster is maintained in [Map Mob Roster](MAP_MOB_ROSTER.md):

| # | Map | Regular mobs | Dedicated ranged mob | Boss |
| ---: | --- | --- | --- | --- |
| 1 | Pine Valley | Regular Zombie, Baby Zombie, Tank Zombie | Spitter Zombie (later addition) | Hammer Zombie Boss |
| 2 | Beach Cove | Crab, Snake, Hermit Crab, Rock-Throwing Crab | Rock-Throwing Crab | Giant King Crab |
| 3 | Desert Basin | Skeleton, Bow Skeleton, Mummy, Scorpion | Bow Skeleton | Pharaoh |
| 4 | Frozen Pass | Frost Ghost, Werewolf, Frozen Knight, Ice Elf | Ice Elf | Frost Cyclops |
| 5 | Volcanic Crater | Fire Goblin, Ember Spider, Lava Slime, Obsidian Ogre, Ash Shaman | Ash Shaman | Dragon |

All maps are broad outdoor arenas using the regular Roblox camera. About 75–85% of the playable surface stays open, with scenery concentrated on the rim. The prototype's base move speed is 24 studs/second (class modifiers apply; the default Brawler moves at 22). See [LOADOUT.md](studio-prototype/combat/LOADOUT.md). Visual direction sheets are in [map-concepts/README.md](map-concepts/README.md). Castle Fields is a later-content idea outside these five.

## 9. Combat feel, drops and readability

- Target approximately 100 active enemies in stress tests, adjusted for Roblox device performance.
- Every defeated enemy produces its own short impact/death sound. No multikill-announcer aggregation.
- Enemies burst, pop, crumble or dissolve clearly according to creature type.
- Crystals bob, then pull magnetically into the player with a rising pickup sound.
- Attacks need crisp anticipation, hit confirmation and distinct silhouettes.
- Enemy hazards always win the readability hierarchy over friendly effects.

Details: [COMBAT_FEEL_AUDIO_VFX.md](COMBAT_FEEL_AUDIO_VFX.md).

## 10. Lobby structure

A floating-island lobby with a circular connected route and four independent queue portals. See [Lobby and first-run flow](LOBBY_AND_FIRST_RUN.md).

- **Loadout:** class, owned starting weapon (with its tier) and armor. The same interface opens from a button or a world station.
- **Play / portals:** unlocked map, solo or party, queue.
- **Chests:** open chests with keys. Shows contents, odds, pity progress, and which weapon or armor tiered up.
- **Armory:** full-screen room with the avatar on a dais: weapons, armor pieces and pets, copy progress toward the next tier, and how to unlock the missing ones. Slots: helmet, chest, legs, boots, weapon, pet, class.
- **Achievements and quests:** what each goal unlocks and current progress.
- **Customization:** pickup effects, defeat effects, emotes, titles, nameplates, lobby poses and UI themes.
- **Shop:** clearly separated Robux purchases.
- **Practice area:** damage dummies with no persistent rewards.

A returning player should be able to understand their rewards, open a chest and queue again in roughly 30–60 seconds.

## 11. Progression outside runs

- **Map ladder:** Each map has Normal, Hard and Nightmare (enemy buffs, more keys). Winning a map on Hard unlocks the next. Best wave per map and difficulty is recorded, including Endless.
- **Keys and chests:** Keys come from waves survived, scaled by map. Chests give weapon and armor copies, with a pick-your-copy reward every 10th chest of a type.
- **Starting tiers:** Duplicates raise a weapon's or armor set's starting tier up to IV.
- **Achievements:** Deterministic unlocks of specific classes, weapons, passives and armor sets.
- **Quests:** Rotating daily and weekly goals that pay keys. Missing a day loses nothing permanent.
- **Customization collection:** Cosmetics only.

A loss still pays keys for every five-wave milestone reached, so a failed run is never wasted.

## 12. Monetization and purchases

The commercial rule is **pay for convenience, early access to earnable options, a limited revive, and expression. Never pay for random rewards or uncapped power.** Full detail: [MONETIZATION_AND_REWARDS.md](MONETIZATION_AND_REWARDS.md).

| Product | What it provides | Guardrail |
| --- | --- | --- |
| **Gem packs** | Premium currency for the guaranteed catalog | Never spent on keys, chests or anything random |
| **VIP pass** | Extra loadout presets, VIP nameplate, cosmetic set | No key or reward multiplier while chests are random |
| **Early Class Unlock** | Immediate access to an otherwise earnable class | The class stays a sidegrade and earnable through achievements |
| **Starter Pack** | Early class unlock + cosmetics + Gems | One-time, contents stated exactly |
| **Buyable Revive** | Death-screen continue for the current run | One per player per run; first price test around 65 Robux |
| **Customization** | Defeat effects, pickup styles, emotes, titles, nameplates, lobby poses, UI themes | No gameplay effect |

### Never sell

- Keys, chests, chest pity, or anything else that opens a random reward
- Weapon or armor copies / starting tiers (**open question**; default is no)
- Mid-run purchases other than the one revive
- Run XP, shards, rerolls, weapon slots or stronger shop odds
- Paid-exclusive classes, weapons or armor

### Buyable revive flow

When a solo player dies, the run pauses and the death screen shows **REVIVE** and **GIVE UP**. REVIVE opens the Roblox purchase prompt. The server grants the revive only after a validated developer-product receipt.

- One paid revive per player per run.
- Restore 50% max health, grant three seconds of invulnerability, and push nearby enemies outward.
- Resume the same wave, timer, boss health, build, shards and drops.
- A cancelled or failed purchase returns to the death choice without granting anything.
- Revived wins still count and pay normal keys. The result records the revive count for leaderboard filtering.
- Co-op behavior is still to be decided.

## 13. Launch-scope recommendation

**Prototype:** Pine Valley, three classes, six signature weapons, its three zombie types, the Hammer Zombie Boss, the 20-wave loop, banked level-ups and the shop/combine flow.

**Vertical slice:** Two maps, all six classes, 12 weapons (two per class), about 15 passives, 2–3 armor sets, keys and chests, starting tiers, a first batch of achievements, saving, and the lobby loop.

**Content launch target:** Five maps, six classes, 36 weapons, 37 passives, 6–8 armor sets, 21 regular mobs, five bosses, Endless, achievements and quests, cosmetics and the approved monetization catalog. This is a target to work toward, not a requirement for the first public test.

## 14. What is still missing

### Must be decided before the prototype

1. Tier I–IV chains for the six prototype weapons.
2. Pine Valley's 20-wave spawn script and Hammer Zombie Boss kit (elite and horde waves not built).
3. Shop tier-unlock waves and prices retuned for 20 waves.
4. Tutorial weapon and base-class behavior.
5. Final revive price, timeout and co-op behavior.
6. Performance budgets for enemies, projectiles, drops, VFX and audio voices.

### Must be decided before the vertical slice

1. Key values, chest price and pity interval, checked against the pacing targets.
2. Which weapons are owned at the start, which come from chests, and which are achievement-first.
3. The first armor sets, their perks, and the armor/passive-accessory overlap rule.
4. The first achievement and quest list.
5. How much harder each map is, and the intended starting-tier power per map.
6. Solo-only launch versus co-op, party size, and map access for mixed-progress parties.
7. Lobby layout and full UI wireframes.

### Important but not blocking the first build

- Final game title
- Optional odd-jobs-agency story wrapper
- Endless leaderboards and any Endless key cap
- Seasonal events
- Later cross-map enemy remixes and Castle Fields

## 15. Immediate next design order

1. Lock the Tier I–IV chains for the six prototype weapons.
2. Write Pine Valley's 20-wave script and retune the shop for 20 waves.
3. Draft the key/chest economy sheet and check it against the pacing targets.
4. Pick the first armor sets and first achievements.
5. Wireframe the chest screen, Armory and result screen.
