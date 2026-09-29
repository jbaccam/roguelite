# Rarity, Godly weapons, armor sets and pets (design, 2026-09-28)

Status: **approved by the user 2026-09-28** (brainstorm session). Nothing here is built yet.
Replaces these parts of [STORE_AND_CHESTS.md](STORE_AND_CHESTS.md): "rarity only means how often
it drops", the chest tier table, the upgrade table, the Godly odds, and the Part 3 outline.

## Why

The user, testing in Studio:

1. "Still getting too many items from chests. It's making it too easy to unlock and upgrade things."
   An earlier pass already cut Gold from 45 to 30 items.
2. "We have 6 items per class and they're all about the same in quality. I can't tell a difference
   between Common, Rare, Epic and Legendary."
3. "We need super legendary stuff, weapons and armor with super rare chances, that players want to
   grind for."
4. "Pets aren't hatched from eggs; they come from chests (maybe a Pet Chest). Remove that text and
   clean up the Armory. Pets give buffs and follow you, all about equally strong with different
   strong suits."

What the code showed:

- A Gold Chest gives 30 copies. The biggest Common stack is usually about ×15, which takes a
  Common from Tier I to Tier III in one chest. A Magical Chest has a 50% chance of a Legendary.
- Glock (Common) does about 17 damage per second and Katana (Legendary) about 19. Rarity only
  changes drop odds.
- Daily deals sell **any** weapon at 15 emeralds a copy, 2–5 copies at a time.
  - Example: "Excalibur ×5 for 75" unlocks a Legendary and takes it to Tier IV.
  - It's also an exploit: a spare Legendary copy is worth 60 emeralds, so you buy at 15 and cash
    in at 60.

## What stays the same (the unlock model; the user confirmed it)

- **In a run, anyone can buy any weapon from the run shop.** Godly weapons are the only
  exception (see below).
- **Your starting weapon must be one you've unlocked.** You also need to own its class, unless
  it's Godly.
- **Only unlocked weapons can be upgraded** (starting tier I–IV, paid with copies).
- **Ways to unlock:**
  - Chests (luck).
  - Daily deals ("item shop sale").
  - Quests. Not built yet, and a later project. Today only classes unlock from goals
    (`RunSetupRules.ClassUnlock`).
- The first copy of a weapon unlocks it at Tier I (`ProfileService.addCopies`). Unchanged.

The hook the user wants: someone buys Excalibur in a run, it's fun and strong, and they want to
unlock it so they can start with it every time.

## Decisions

### 1. Weapon chests: a handful of items, not a flood

| Chest | Emeralds | Items | Rare | Epic | Legendary | Godly | Pity counts |
|---|---:|---:|---|---|---|---|---|
| Wooden | 60 | 3 | 25% chance of 1 | 2% | 0.2% | — | no |
| Silver | 160 | 6 | 1 | 8% | 0.8% | 0.05% | yes |
| Gold | 300 | 10 | 2 | 25% | 3% | 0.2% (1 in 500) | yes |
| Magical | 700 | 18 | 4 | 1 | 10% | 0.6% | yes |
| Legendary (Robux / rewards) | — | 8 | 3 | 1 | 1 guaranteed | 2% | yes |

- Everything else in the chest is Common. Copies of one rarity are still grouped into 1–3 weapons
  (`ChestConfig.group`).
  - Example Gold Chest: ×5 Frying Pan, ×2 Egg, ×1 Glock, ×1 Shotgun, ×1 Kunai, plus a 25% chance
    of an Epic and a 3% chance of a Legendary.
- **Rare can now be a chance** (Wooden 25%). `rollCounts`, `summary` and `odds` must handle a
  fractional `rare` the same way they already handle a fractional `epic`.
- **Pity** (counted on chests with "Pity counts" = yes):
  - Legendary: guaranteed within **50** chests (unchanged).
  - Godly: guaranteed within **150** chests (new counter `pity.Godly`).
- Prices are unchanged. The chest screen's "what's inside" bars and the [i] odds grid are
  generated from `ChestConfig`, so they update automatically. They need a Godly row, and Wooden's
  Rare shows as "25%".

### 2. Upgrade costs (copies spent to raise the starting tier)

| Rarity | I → II | II → III | III → IV | Spare copy after Tier IV |
|---|---:|---:|---:|---:|
| Common | 2 | 6 | 15 | 2 emeralds |
| Rare | 2 | 4 | 8 | 5 |
| Epic | 1 | 2 | 4 | 20 |
| Legendary | 1 | 2 | 3 | 60 |
| Godly | 1 | 1 | 2 | 200 |

### 3. Daily deals (the "item shop sale")

- Slot 1 stays 200 free emeralds.
- Each paid slot first picks a rarity: Common 55%, Rare 35%, Epic 8%, Legendary 2%. Then it picks
  a random weapon of that rarity. **Never Godly.**
- Price per copy: Common 15, Rare 40, Epic 150, Legendary 500.
- Amount: Common 2–5, Rare 1–3, Epic 1, Legendary 1.
- Every price is well above the spare-copy value, so the buy-and-cash-in exploit is gone.

### 4. Rarity means power (a little)

Each weapon has **one rarity forever** (Shotgun is always Rare). Tiers I–IV are separate: they
are the combine upgrades.

| Rarity | Colour | Power* | What it means |
|---|---|---:|---|
| Common | light grey | 100 | One simple attack |
| Rare | blue | 105 | Same weapon, a little better |
| Epic | purple | 110 | A special mechanic |
| Legendary | gold | 120 | The coolest weapon in its class, plus one **extra move** (section 8) and a gold aura |
| Godly | crimson | 135 | No class, super rare, a mechanic nothing else has (section 9) |

\*Damage over the same time, at the same tier. Applied as a damage multiplier on top of each
weapon's authored numbers.

The user said "a little more OP", not "giant". Legendary effects should be a step up but never fill
the screen. For example, Excalibur **shoots beam slashes**. It does not drop giant sword beams from
the sky.

**Rarity changes:**
- **Mjolnir (id 31) moves from Epic to Legendary.** Mage now has 2 Legendaries (Mjolnir and
  Excalibur) and no Epic. That's fine.
- Pools after the change: Common 12, Rare 12, Epic 5, Legendary 7, Godly 6.

**Implementation note:** rarity must live in `WeaponCatalog` (a sandboxed module), because
`CharacterStats` (sandboxed) applies the power multiplier and **cannot require `ChestConfig`**
(unsandboxed). `ChestConfig` then builds its pools from `WeaponCatalog`. An unsandboxed module may
require a sandboxed one.

### 5. The run shop respects rarity

Anyone can still buy any non-Godly weapon in a run, but rarer weapons are harder to find:

| Rarity | How often it's offered | Price |
|---|---:|---:|
| Common | ×1 | ×1 |
| Rare | ×0.75 | ×1.15 |
| Epic | ×0.5 | ×1.4 |
| Legendary | ×0.25 | ×2 |
| Godly | never | — |

- "How often" means `ShopService` `choose()` picks weighted by rarity instead of uniformly.
- "Price" multiplies the catalog `basePrice` (`ShopCatalog` builds weapon entries).
- Godly weapons get **no** `ShopCatalog` entry.
- Also finish the rename already planned in STORE_AND_CHESTS.md, if it isn't done yet:
  `EconomyConfig.TIER_NAMES` becomes `Tier I`–`Tier IV`, so the words Common/Rare/Legendary only
  ever mean rarity.

### 6. Tiers work like Brotato

No renamed forms or new models per tier. The user explicitly dropped the "Extended Mag → Switch"
idea.

- **Every tier:** more damage **and** faster attacks.
  - Damage is ×1.4 per tier.
  - Cooldown multipliers are `{1, .9, .8, .7}` (today they are `{1, .95, .9, .84}` and damage is
    about ×1.5 per tier).
  - Tier IV power lands about where it is today. Upgrades just feel faster.
  - Example Glock: damage 12 / 17 / 24 / 33; seconds between shots 0.72 / 0.65 / 0.58 / 0.50.
- **Exception:** Boxing Gloves keep their user-supplied 8/16/32/64 damage and their own cooldown
  curve (see `WEAPON_BALANCE.md`).
- **Tier IV:** one functional bump per weapon (section 7). Existing per-tier changes stay: Shotgun
  pellets, pierce and bounce growth, Medusa's second shot, Cards' 4th card.

### 7. Tier IV bump per weapon

"Existing" means the weapon already changes at higher tiers in `CharacterStats.weapon()` and keeps
that change.

| Class | Weapon (id) | Tier IV bump |
|---|---|---|
| Brawler | Frying Pan (01) | Bigger swing (+25% reach) |
| Brawler | Nunchucks (02) | +1 hit per combo |
| Brawler | Katana (03) | Wider cut |
| Brawler | Kusarigama (04) | Longer reach |
| Brawler | Spatula (05) | Flips enemies farther (more knockback) |
| Brawler | Baseball Bat (06) | Home runs: a launched enemy damages the enemies it hits |
| Gunner | Glock (00) | 2 bullets per shot |
| Gunner | Draco (07) | Bullets pierce 1 |
| Gunner | Fart Gun (08) | Bigger, longer clouds |
| Gunner | Shotgun (09) | Existing (+1 pellet per tier); at IV pellets also pierce 1 |
| Gunner | T-Shirt Cannon (10) | Existing (pierce); at IV fires 2 shirts |
| Gunner | Rocket Launcher (11) | Bigger blast |
| Thrower | Boomerang (12) | Existing (bounces) only |
| Thrower | Kunai (13) | Existing (pierce); at IV throws 2 |
| Thrower | Molotov (14) | Bigger, longer fire |
| Thrower | Egg (15) | Bigger splash |
| Thrower | Steak (16) | Heals 1 HP per hit |
| Thrower | Deck of Cards (18) | Existing (4th card at III); at IV throws 5 cards |
| Juggler | Rubber Duck (17) | Existing (bounces); at IV +1 duck |
| Juggler | Boxing Gloves (19) | Knockback |
| Juggler | Cinder Block (20) | Short stun |
| Juggler | Yo-Yo (21) | Existing (bounces); at IV longer string |
| Juggler | Bowling Ball (22) | Existing (pierce) only |
| Juggler | Bowling Pin (23) | +1 pin |
| Handyman | Nail Gun (24) | Existing (pierce); at IV 2 nails per shot |
| Handyman | Wrecking Ball (25) | Bigger area |
| Handyman | Shovel (26) | Bigger swing |
| Handyman | Paint Roller (27) | Paint slows enemies |
| Handyman | Vacuum Cleaner (28) | Wider suction cone |
| Handyman | Power Washer (29) | Existing (pierce); at IV pushes enemies back |
| Mage | Magic Staff (30) | 2 orbs |
| Mage | Mjolnir (31) | Lightning jumps to +1 enemy |
| Mage | Excalibur (32) | Bigger slash |
| Mage | Pandora's Box (33) | Bigger blast |
| Mage | Medusa's Head (34) | Existing (2nd shot at II); at IV the slow becomes a short freeze |
| Mage | Crystal Ball (35) | Existing (bounces); at IV lightning jumps to +1 |

Most of these are new fields in `CharacterStats.weapon()` next to `projectileCount`,
`nativePierce` and `nativeBounce`: range, area, knockback, chain count, weapon-native slow and
heal. Stun and freeze are new status effects.

### 8. Legendary extra moves (7 Legendaries)

| Class | Legendary | Extra move |
|---|---|---|
| Brawler | Katana | Every 3rd swing throws a flying slash that cuts through a line of enemies |
| Gunner | Rocket Launcher | Every 4th rocket splits into 3 mini rockets |
| Thrower | Deck of Cards | Every 5th throw is a **Royal Flush**: 5 gold cards that pierce everything |
| Juggler | Bowling Ball | A roll that hits 5+ enemies is a **STRIKE!** with a pin explosion at the end |
| Handyman | Wrecking Ball | Heavy hits send out a ground shockwave ring |
| Mage | Excalibur | Swings shoot golden beam slashes (ranged) |
| Mage | Mjolnir | Every 4th throw calls a lightning strike where it lands |

Every Legendary also gets a gold aura on its floating model.

### 9. Godly weapons (6 at launch; more in updates)

Rules:
- **No class.** Any class can start a run with one. The loadout rule becomes: the weapon is an
  owned weapon of the chosen class, **or** any owned Godly. That affects `RunSetupRules`,
  `ArmoryUI`, `RunSetupUI` and `RogueliteCombat.server` (`starter`).
- **Chest only.** Never in the run shop or daily deals, and never sold directly for Robux.
- **Can't be combined in a run** (no duplicates can be bought), so it stays at the tier its copies
  got it to. That's the reason to keep pulling copies.
- **Power 135,** with its own model, VFX and sound. It gets a Godly reveal in the chest opening:
  screen flash, crimson rays and a server-wide announcement ("X found a Godly weapon!"), as
  already planned in STORE_AND_CHESTS.md.
- Real, recognizable weapons only. See the user's feedback below.

| Godly | Type | What it does |
|---|---|---|
| Reaper's Scythe | Melee | A huge spinning sweep; enemies it kills come back as ghost helpers for 5 seconds |
| Poseidon's Trident | Thrown + melee | Where it lands, a tidal wave rolls out and washes enemies away |
| Storm Bow | Ranged | Each arrow splits into 5 mid-air and rains down on a group |
| Shadow Daggers | Melee | Twin daggers zip from enemy to enemy, hitting up to 5 in a chain |
| Vampire Blade | Melee | Every hit heals you, and kills send red wisps flying into you for extra healing. Uses the existing `LifeSteal`/`LifeStealCap` stats, so healing is capped per second |
| Ray Gun | Ranged | Zappy green blasts; enemies it kills disintegrate in a burst that hits the ones nearby |

Rejected by the user ("these aren't even weapons"): Orbital Laser Remote, Grand Piano, Ice Cream
Truck, Bass Drop Boombox, Golden Frying Pan, Leaf Blower Tornado, Dragon Egg, Black Hole Jar,
Laser Minigun, UFO. Also not picked: Dragon Slayer, Winter's Edge, Railgun, Golden Minigun,
Inferno Axe, Moon Glaive.

The exact damage, cooldown, range and Tier IV bump for each Godly are decided in step 4's own
short spec.

### 10. Armor sets (7)

Armor rules (already decided in `CURRENT_GAME_STRUCTURE.md` / `PROGRESSION_AND_SESSION_FLOW.md`):
- 4 pieces: helmet, chest, legs and boots.
- Each piece has its set's rarity and tiers I–IV, upgraded with copies using the table in
  section 2.
- 2 pieces of a set give a stat bonus; all 4 give the set's perk.
- Pieces come from separate **armor chests**. Weapon and armor chests never mix.

| Set | Rarity | 2 pieces | All 4 pieces |
|---|---|---|---|
| Iron | Common | +4 armor | Take 15% less damage from zombie hits (`ContactReduction` +15) |
| Ninja | Rare | +10% dodge | After you dodge, your next hit is a crit |
| Viking | Rare | +15% melee damage | Under half HP: +30% attack speed |
| Samurai | Epic | +10% crit chance | Crits hit 50% harder (`CritDamage` +50) |
| Spartan | Epic | +6 armor | A shield blocks the first hit every wave (`FirstHitBlock` = 1) |
| Dragon Scale | Legendary | +25 max HP | Hits can set enemies on fire, and fire spreads when they die (`BurnChance`, `BurnSpread`) |
| Phoenix | Godly | Heal 2 HP per second | Once per run, when you die you rise in flames with half HP and blast everything near you |

- The 2- and 4-piece bonuses can use the same shape as the class `two`/`four` tables in
  `CharacterStats.S.Classes`. Most are data only.
- Rejected: Leather, Pirate, Pharaoh, Frost King, Void Walker, and the funny armor sets in
  `BRAINSTORM_FUNNY_GEAR.md`.

### 11. Pets (12) and the Pet Chest

The user, 2026-09-28: pets are **not** hatched from eggs. They come from chests, from a **Pet
Chest** that holds pets only (weapon, armor and pet chests never mix).

- A pet follows you into runs and gives one buff or helper action. **Every pet is equally strong,
  with a different strong suit.** Balance works by a power budget: each pet's Tier I effect is
  tuned to be worth about the same.
- One pet slot. Copies level a pet up (tiers I–IV). The effect numbers grow per tier.
- **Rarity only means rarer and flashier** (glow, trail, idle animation), **never** stronger. The
  user chose this over no rarities. This is the one place where rarity doesn't mean power; it's
  on purpose.
- Rarity below is a first pass; the user can move any pet.

| Pet | Rarity (first pass) | Strong suit | What it does |
|---|---|---|---|
| Golden Retriever | Common | Loot | Runs out and fetches crystals from across the map |
| Bunny | Common | Healing (team) | Every 10 s drops a carrot that heals you or the hurt teammate closest to you |
| Frog | Common | Space | Hops and slams, knocking nearby enemies back |
| Penguin | Common | Slow | Belly-slides through enemies and slows them |
| Fox | Rare | Damage | Pounces on nearby enemies |
| Bee | Rare | Poison | Stings enemies and poisons them (`PoisonChance`) |
| Turtle | Rare | Defense (team) | Every 15 s gives a shell shield that blocks one hit, to you or a hurt teammate |
| Monkey | Rare | Attack speed | +Attack speed. The user said slipping or stunning enemies was too hard, so keep it a plain stat |
| Lucky Cat | Epic | Luck | +`Luck`, so the run shop rolls better tiers more often |
| Owl | Epic | Bosses | Marks the toughest enemy nearby; your hits on it do +20% |
| Cheetah Cub | Epic | Speed | +Move speed, and a short speed burst after you get hit |
| Baby Dragon | Legendary | Fire | Small fire breaths that burn groups (`BurnChance`) |

- Bunny and Turtle are the first things in the game that help **other players**, which makes them
  good co-op picks.
- Pet Chest prices, odds and per-tier numbers are decided in step 6's spec.

### 12. Armory cleanup (small; the user asked for it)

- Remove every "pet egg" wording. Today that's:
  - [ArmoryUI.luau:39-40](studio-prototype/ui/ArmoryUI.luau) (comment).
  - The Pets tab "coming" panel at `ArmoryUI.luau:460-468` ("Pets hatch from pet eggs…",
    "Hatch from pet eggs (pets only)").
  - The pet detail at `ArmoryUI.luau:835-840` ("PET SLOT · COMING WITH PET EGGS").
  - STORE_AND_CHESTS.md Part 4.
  - The new wording: pets come from the **Pet Chest**.
- "Clean up the Armory": the user didn't list specifics. Open the Armory in Studio Play
  (Weapons, Armor and Pets tabs and the detail panel) and fix what's cluttered or confusing.
  Obvious candidates are the long "coming" panels. Run `UILayoutAudit`, then **show the user**
  before calling it done.

### 13. Art: Blender models, R15 fit and rarity looks (user, 2026-09-28)

**What the user asked for:**
- Model the armor, Godly weapons and pets in Blender.
- Armor must **fit the R15 rig players are locked to**, and be "very well designed": good fit,
  curvature, edges, colouring and textures.
- **The rarer it is, the sicker it looks:** more design, VFX and intricacy, and more texture
  (e.g. real scales), "not just Minecraft armor".
- Iron (Common) can be fairly flat, like the ice plate reference. Legendary and Godly should reach
  the level of the lava reference.
- **"Don't copy it directly. Make it look better than this."**

**References** are the user's screenshots of another Roblox game. Use them for style only and
never copy them. They're saved in `art-references/armor-2026-09-28/`:

| File | SHA256 | What it shows |
|---|---|---|
| `ice-plate-armor-reference.png` | `53c85a8b0f3e41d221c5fdc75367e9765c4370c35b369d8765687d51bc569df9` | Low-rarity level: smooth pale-blue chest plates, soft bevelled edges, a raised centre ridge, one diamond gem, and an open face-plate helmet that leaves the hair showing |
| `lava-armor-chest-reference.webp` | `4d0c47f9b67854878e5183aba030c62f19d5925555f21ecd9d7883f8ee952637` | High-rarity level: dark rock plates split by glowing orange crack lines. The same motif runs across helmet, chest, legs, boots, sword and a themed event chest |
| `lava-armor-full-reference.png` | `6cbc08bfac4556956c6dff723a1e4acd9fb31293e57d26995766a30b07952f3c` | The same lava set worn on a blocky R15 avatar: a full crested helmet with a visor slit, diamond gem accents, and pauldrons and bracers following the arm segments |

**The look climbs with rarity** (armor first; weapons and pet flair follow the same idea):

| Rarity | Shape | Surface | Glow / VFX |
|---|---|---|---|
| Common (Iron) | Clean plates, soft bevels, a trim line or rivets | Painterly brushed metal, 2–3 values | None |
| Rare (Ninja, Viking) | Layered plate edges, a second material (leather straps, cloth wraps, fur) | More colour breakup | None |
| Epic (Samurai, Spartan) | Distinctive silhouette pieces (big pauldrons, crest, lamellar rows), engraved trim | Patterned texture (engravings, lacquer) | A subtle glowing accent (a gem) |
| Legendary (Dragon Scale) | **Overlapping scale plates as real geometry** on the chest, shoulders and shins; horns and spines | Painted scales between the modelled ones | Glowing seams and gems, light ember particles |
| Godly (Phoenix) | The most complex silhouette (feather and flame shapes) | The richest pattern | Animated glow plus particles |

All of it stays inside `art-references/ART_DIRECTION_USER_2026-09-17.txt`: stylized low-poly and
painterly, soft bevels, textures give richness while geometry gives shape. Never realistic, never
voxel/Minecraft, never a hyper-detailed sculpt.

**How armor has to fit the R15 body:**

- **The body is fixed.** `AvatarNormalizer.server.luau` gives every player the standard-proportion
  R15 body: default blocky parts, every scale 1, `BodyTypeScale` and `ProportionScale` 0, no layered
  clothing. Classic Shirt/Pants and up to 4 hat, hair or face accessories stay. Armor is authored
  once, for that exact body.
- **Measure the real body; don't guess.** In Studio, read a normalized character's part sizes and
  joint positions. Rebuild that body in Blender as the fitting proxy, at 1:1 studs, and model at
  final size (no upscaling in Studio).
- **Split each piece into rigid meshes, one per R15 part it covers, welded to that part:**

  | Piece | R15 parts |
  |---|---|
  | Helmet | Head |
  | Chest | UpperTorso, LowerTorso, both UpperArms (pauldrons), both LowerArms (bracers) |
  | Legs | Both UpperLegs and LowerLegs (knee guards) |
  | Boots | Both Feet, plus a cuff on the LowerLegs |

- **Joints:** overlap and flare the plates at the shoulders, elbows, hips and knees. There must be
  no gaps and no clipping in idle, walk, run and jump. Check in **Play**, not Edit.
- **Close fit:** chunky enough to read from the game camera, but hugging the body, not a bulky
  shell.
- **Helmet vs hair:** each helmet is either open-face (hair shows, like the ice reference) or full,
  hiding hat and hair accessories while it's worn (like the lava reference). Propose one for the
  sample and let the user decide.

**Roblox technical rules:**
- Colour goes through `MeshPart.TextureID`. SurfaceAppearance with newly uploaded images renders
  blank white in Play.
- Glow comes from separate inset meshes with the Neon material (crack lines, seams, gems), plus an
  optional ParticleEmitter or PointLight. Never from a lighting trick that hides missing geometry.
- **Budgets:**
  - A whole armor set: about 6k triangles for Common, up to about 12k for Legendary or Godly.
  - A weapon: under 8k (as in the weapon brief).
  - A pet: about 5k.
  - Document the reason if you go over.
- **Blender kit convention** (like the other `blender-*` folders):
  - A self-contained generator run in background Blender 5.2.
  - `exports/fbx` + `exports/glb`, `textures/`, real `previews/` renders, a polygon report,
    `validate_exports.py` and a README with provenance.
  - Don't change the user's open Blender scene through MCP.
- **Godly weapon:** follow the deliverables in `weapon-models/MODELING_BRIEF.md`. The approved Glock
  (`item-model-test-glock/`) is the quality bar. There's no reference image, so design from section
  9 with the Godly accent (crimson and obsidian).
- **Pet:** a stylized low-poly animal, cute but cool for ages 8–16.
  - Paint the face into the texture over shallow relief; modelled sockets read as sunglasses.
  - Give it a simple armature (body, head, legs, tail) so step 6 can animate it. No animations yet.

**Style-sample gate. This comes first, and before any other art:**

1. Model **only one of each**:
   - 1 armor set: **Dragon Scale** (Legendary, which shows scales and the top-end detail).
   - 1 weapon: **Reaper's Scythe** (Godly).
   - 1 pet: **Golden Retriever**.

   Swap any of these if the user picks different ones.
2. Show the user:
   - **Blender renders:** front, back and side of each.
   - **An in-Studio Play check:**
     - The Dragon Scale set worn by a normalized R15 display dummy that plays the default walk.
     - The scythe floating next to it.
     - The dog standing beside it.

     Put these only in a `Workspace.StyleSamples` folder near the lobby spawn. No gameplay code, and
     remove the folder after approval. Capture from the Play client.
3. **Stop and wait for the user's approval of the style.** Only then model the other 6 armor sets,
   5 Godly weapons and 11 pets, reusing the approved look.

This art work doesn't depend on the gameplay code, so it can run alongside step 1. The gameplay
for armor, Godly weapons and pets still waits for steps 4–6.

## Pace check

`economy-sims/chest_pace_sim.py` simulates a player who spends every emerald on one chest type.
Emerald income is a **guess**: about 330 per hour at first, rising to about 1,600 per hour on late
maps (including 200 daily emeralds). Median hours played:

| Milestone | Today (Gold) | New (Wooden) | New (Gold) | New (Magical) |
|---|---:|---:|---:|---:|
| Starting weapon to Tier II | 2.7 | 1.5 | 4.3 | 6.0 |
| First Epic | ~0.5 | 5.2 | 2.7 | 2.1 |
| First Legendary | 4.3 | 27 | 14 | 9 |
| First weapon at Tier IV | 5.4 | 9 | 13 | 14 |
| First Godly | — | never | 47 | 74 |
| All 7 Legendaries | — | 350+ | 100 | 93 |
| Every non-Godly weapon at Tier IV | 77 | 600+ | 375 | 336 |

- Cheap chests give more items per emerald (Wooden 1 per 20; Gold 1 per 30). Better chests give
  better odds per item. Both have a job.
- The "Today" column is **before** the daily-deal exploit, which made the real game even faster.
- Target from `PROGRESSION_AND_SESSION_FLOW.md`: first Tier II in about 1 hour, first Tier IV
  after 10–15 hours, full collection after 100+ hours. The new numbers fit.
- Re-check against real income data once runs record it.

## Build order

Each step gets built, synced to Studio, tested in Studio Play and **shown to the user before the
next one starts**. Every step must leave Studio fully working (see "Rules for implementers").

**Art track (runs alongside step 1):** the style-sample gate in section 13. Model one armor set, one
Godly weapon and one pet in Blender, show them, and wait for approval before modeling anything else.
Steps 4–6 use the approved models.

### Step 1: Economy numbers (small; fixes "too easy" right away)
- **`ChestConfig.luau`:**
  - The new chest table (section 1), including a fractional `rare` and a `godly` chance.
  - The upgrade and spare-copy tables (section 2) with Godly added.
  - `GodlyPity = 150`.
  - Mjolnir in the Legendary pool.
  - `Rarities` gains `Godly`, plus a crimson `RarityColor`.
  - **Godly rolls stay off while the Godly pool is empty** (no Godly weapons until step 4), so a
    Godly roll never turns into a missing item.
- **`ProfileService.luau`:**
  - A `pity.Godly` counter next to `pity.Legendary` (migrate old saves: missing means 0).
  - `RANK` gains Godly.
  - `dealList` uses the section 3 rarity-based deals.
- **Chest UI** (`ChestScreenUI`, `ChestStage`, `ChestFX`, `ArmoryUI`, `LobbyUI` deals):
  - Show the fractional Rare ("25%").
  - Show a Godly row and colour once it exists.
  - Show deal prices per rarity.
  - Check every place that loops over `Chests.Rarities` or indexes `RarityColor`.
- **New `ChestConfigTests.luau`** (none exists yet). It checks:
  - Every chest's item count is conserved by `rollCounts` + `group`.
  - `odds()` percentages match a 100,000-roll simulation within tolerance.
  - Both pity counters.
  - Every deal price is higher than that rarity's spare-copy value.
  - Mjolnir is Legendary.
- **Armory cleanup** (section 12): the pet-egg wording goes, and the cleanup gets shown to the
  user.

**Built 2026-09-28** ([plan E](plans/2026-09-28-E-economy-numbers.md)); waiting for the user's
look before step 2. Results in Studio:
- `ChestConfigTests` (Edit): **PASS, 93 checks, 4.2 s**, including `odds()` against a
  100,000-chest simulation per chest kind, both pity counters (with a temporary Godly pool), and
  20,000 rolled deals.
- Server (Play): 10 Gold Chests gave exactly 100 items. `pity.Godly` exists at 0 and stays 0 while
  Godly is off. Every daily deal is priced `amount × DealPrice[rarity]`, above the spare-copy value.
- Client (Play), through the real chest screen: every chest kind opened ×1 and ×10 gives exactly its
  item count (3/6/10/18/8, ×10 = 30/60/100/180/80). The Wooden and Magical odds grids match
  `ChestConfig.odds` (36 cells each, 0 mismatches).
- `UILayoutAudit`, 0 problems each: chest browse, odds overlay, results, Store → Daily, and the
  Armory's Weapons, Armor and Pets tabs.
- **Found, not caused by this step:** upgraded tiers still never reach a run. A Tier II Frying Pan
  starts the run in slot 1 at Tier 1. `STORE_AND_CHESTS.md` Part 0 was never built; nothing reads
  the profile tier at run start.
- Not testable in Studio: DataStore migration of real saves, Robux Legendary Chests,
  PolicyService-restricted accounts.

### Step 2: Rarity power, run-shop rarity, Brotato tiers, Tier IV bumps
- Add `rarity` to each weapon in `WeaponCatalog`, and make `ChestConfig` read its pools from it
  (sandboxing note in section 4).
- Rarity power multiplier in `CharacterStats.weapon()` (section 4).
- Tier rule (section 6). Rewrite the authored `tierDamage` tables to ×1.4 per tier and the default
  `tierCooldown` to `{1,.9,.8,.7}`. Gloves are exempt.
- Tier IV bumps (section 7).
- Rarity-weighted offers and prices in `ShopService`/`ShopCatalog`, and the `TIER_NAMES` rename
  (section 5).
- Update `WeaponBalanceTests`, `ShopTests` and `CharacterStatsTests`. Add a check that each
  weapon's Tier IV damage per second stays within ±10% of today's, before the rarity multiplier.
- Update `WEAPON_BALANCE.md`.

### Step 3: Legendary extra moves (section 8)
- One at a time, each with a gold aura. Reuse the existing VFX modules (`SwingVisuals`,
  `ArcVisuals`, `SpecialWeaponVisuals`, `CombatEffectsService`) and document in `WEAPON_VFX.md`.
- The server owns every hit; visuals are client-only.

### Step 4: Godly weapons (section 9)
- Write a short spec first: stats, Tier IV bumps, models and VFX per Godly.
- Models follow the roguelite art direction (stylized low-poly, painterly, never realistic) and
  the Blender kit convention.
- Loadout rule change for Godly starters.
- **Godly weapons only appear for players who own them** (user, 2026-09-29). They are never shown
  or offered unless unlocked:
  - not in the run shop, level-up offers or drops;
  - not in the Armory weapon grid or class lists.

  The server filters every offer by the player's profile, and the client never lists them. Only
  the chest odds panel shows the Godly *chance*, and it doesn't name any weapon.
- Godly reveal and server announcement in the chest opening.
- Turn Godly chest rolls and pity on.

### Step 5: Armor system and the 7 sets (section 10)
- Its own design pass first:
  - Piece stats per tier.
  - Armor chest tiers and odds.
  - The Armory armor tab (it's a "coming" panel today).
  - Low-poly pieces that fit many Roblox avatars.
  - Whether Phoenix's revive stacks with the Robux Revive (`MonetizationConfig.ReviveLimitPerRun = 1`).
  - A second Common set (Iron is the only Common, so early armor chests would drop almost only Iron).

### Step 6: Pets and the Pet Chest (section 11)
- Its own design pass first:
  - Pet Chest price and odds.
  - Per-tier numbers for all 12 pets, checked against one power budget.
  - Follow and animation behaviour.
  - Team targeting for Bunny and Turtle.
  - Rarity looks.
  - Low-poly pet models in the roguelite art style.
- Pets never go in weapon or armor chests.

## Rules for implementers (from this project's memory and plans)

- **Parallel sessions share this folder.** 2–4 Claude sessions work here at once.
  - Never switch branches.
  - Stage only your own files. No `git add -A`.
  - When this doc was written, other sessions had uncommitted edits in `ShopService.luau`,
    `ChestScreenUI`, `ChestStage`, `ChestFX`, `ArmoryUI`, `LobbyUI`, `UITheme`, `WEAPON_BALANCE.md`
    and `WeaponBalanceTests.luau`. Run `git status` and `git diff` on a file before editing it, and
    never revert someone else's changes.
- **Never break Studio between tasks.** The user play-tests constantly. Land every consumer update
  in the same task as the change it depends on. Before Play, check `get_studio_state`; if Studio
  is already in Play, that's probably the user, so don't stop it.
- **Sandboxing:** a sandboxed script can only require sandboxed modules. New modules that sandboxed
  code requires need `Sandboxed = true` plus Capabilities copied from `CharacterStats`. The full
  list of which modules are sandboxed is in
  `plans/2026-09-28-D-admin-panel.md` → "Conventions".
- **Studio sync** works the way plan D describes: repo files are the source of truth, synced into
  Studio. Use plain `screen_capture` only (never the positioned one; it locks the edit camera).
- **Server authority:** rolls, prices, pity, grants, upgrades and hits all happen on the server.
  The client only asks and draws. Odds shown to players come from the same `ChestConfig` the server
  rolls with.
- **Studio profiles are in memory.** DataStores stay off in Studio; nothing persists. A run where
  the admin panel was used grants nothing (`AdminConfig.isTestRun()`).
- **Monetization:**
  - Godly and Legendary weapons also drop from chests bought with earned emeralds; nothing is
    Robux-only.
  - Robux chest packs stay flagged `random` and hidden where PolicyService restricts paid random
    items.
  - Power is capped: Godly is 135.
- **Commits:** small, meaningful commits straight to `main`, pushed to `origin`
  (github.com/jbaccam/partyati) when a chunk is done.

## Verification (every step)

- Unit tests in the Studio command bar for that step; paste the actual pass counts into the doc.
- Studio Play:
  - Open each chest tier ×1 and ×10.
  - Check the odds grid and the daily deals.
  - Upgrade a weapon in the Armory, then start a run and confirm the upgraded tier in slot 1.
- `UILayoutAudit`: 0 problems on the chest screen, the reveal and the store tabs.
- **Can't be tested in Studio** (say so; never claim these pass): real Robux receipts,
  PolicyService-restricted accounts, DataStore saving, multiple real clients, and the real
  server-wide Godly announcement across servers.

## Not decided yet

- Quests as a way to unlock weapons (a later project).
- Exact Godly stats and effects (step 4 spec).
- Armor piece stats, armor chest odds, and a second Common set (step 5 spec).
- Whether Phoenix's revive stacks with the Robux Revive.
- Pet Chest price and odds, per-tier pet numbers, and final pet rarities (step 6 spec).
- Real emerald income per hour, to re-check the pace table.
