# Store and chests rework (design, 2026-09-27)

Status: proposed, waiting for user review. Replaces the chest and currency parts of
MONETIZATION_AND_REWARDS.md and PROGRESSION_AND_SESSION_FLOW.md where they disagree.

> **Partly replaced 2026-09-28 by [RARITY_GODLY_ARMOR.md](RARITY_GODLY_ARMOR.md) (user-approved).**
> Rarity now also means a little more power. Chests hold a handful of items (Gold: 30 → 10).
> Upgrade costs, daily-deal prices, the Godly odds and pity, the six Godly weapons, the seven armor
> sets and the twelve pets are all defined there. Pets hatch from a **Pet Egg** (egg merchant, 2026-10-02). Where
> this file disagrees, that one wins.

> **Decision 2026-09-27 (user): keys are dropped. Emeralds are the only currency** for chests,
> skills, classes, deals and bundles, earned in runs and bought with Robux (like Final Swarm /
> Survive the Swarm). Any key amount further down converts at 1 key = 20 emeralds (for example,
> a 15-key Gold Chest = 300 emeralds). Old saves convert the same way. Where paid random items
> are restricted, only emeralds earned in play can open chests (ProfileService tracks Robux
> emeralds as `bought`).

## Goals

- One rule a kid can guess: **emeralds buy everything.**
- Chests work like Clash Royale: every weapon has a fixed rarity, a chest gives many copies of
  commons and a few of the rarer weapons, and copies upgrade a weapon's starting tier.
- ~~Rarity only means *how often it drops*, never *how strong it is*.~~ Replaced 2026-09-28:
  rarer weapons are also a little stronger (Common 100 → Legendary 120 → Godly 160, one per run), see
  RARITY_GODLY_ARMOR.md. Pets are the exception: rarer pets are only flashier.
- A few **Godly** weapons are the long-term chase: very rare, flashy, clearly good, never "game over".
- The store stops looking bland: colour backdrops per category, 3D weapon models, a real
  chest-opening reveal.

## Build order

Each part is built, verified in Studio Play, and shown to the user before the next.

| Part | What | Why first |
|---|---|---|
| 0 | Runs start with the saved loadout weapon at its upgraded tier | Today upgrades never reach a run, so chests have no payoff |
| 1 | Store look and compliance fixes (the emeralds-only switch is already done) | Makes the store clear and appealing |
| 2 | Weapon rarities, chest tiers, chest-opening reveal | The Clash Royale loop |
| 3 | Godly weapons (brainstorm, models, VFX, stats) | New content; needs its own design pass |
| 4 | Armor in the chests (2026-09-30); pets from the egg merchant's Pet Egg (2026-10-02, replaces the Pet Chest) | Same 3-tap template |
| 5 | Polish: featured item of the day, lobby chest room | Nice to have |

## Part 0: upgrades count in runs

- The lobby already stores the chosen class and weapon (`LoadoutClass`/`LoadoutWeapon`, and
  `RunClass`/`RunWeapon` on the queue). At run start the server puts that weapon in slot 1
  at the tier saved in the profile (`ProfileService` weapons `tier`).
- Server checks: the player owns the weapon and the class; otherwise fall back to the class
  signature weapon at Tier I.
- Example: Frying Pan saved at Tier III → the run starts with a Tier III Frying Pan.

## Part 1: currency and store

### The rule

| Currency | Earned from | Spent on |
|---|---|---|
| Emeralds | Runs, daily free emeralds, codes, spare copies, quests, and Robux | Everything: chests, skills, daily deals, classes |

- Every item shows exactly one price.
- Chests are priced in emeralds. Where `ArePaidRandomItemsRestricted` is true, only emeralds
  earned in play can open chests: the server spends earned emeralds only, and the client shows
  `ProfileGemsEarned`. This is already built in ProfileService.
- Robux chest packs remain (flagged `random`, hidden where restricted).
- Daily deals: weapon copies cost 15 emeralds each. Slot 1 is 200 free emeralds.

### Compliance fixes

- Starter Pack contains a chest → mark it `random` (hidden/replaced where restricted).
- VIP daily chest: check `restricted[p]` before granting; restricted VIPs get emeralds instead.

### Look

- Keep the charcoal window, lime corners and stone title plate.
- Offer cards get saturated colour backdrops per category (new tintable nine-slice card art made
  by `ui/build_assets.py`, white base so one image tints to every colour):
  - Chests: amber
  - Emeralds: teal
  - Bundles / Starter Pack: purple
  - VIP / passes: royal blue
  - Godly: crimson
- Chest cards show a "What's inside" list with one bar per rarity (e.g. Common 89% ███▉),
  and "220 more emeralds needed" under the price when short.

## Part 2: rarities, chests and upgrades

### Rarity (fixed per weapon)

Colours belong to rarity. Tier badges become plain numerals (I–IV) with no rarity colour, and the
in-run shop stops calling tiers Common/Uncommon/Rare/Legendary (`EconomyConfig.TIER_NAMES`
becomes `Tier I`–`Tier IV`), so each colour has one meaning.

| Rarity | Colour | Per class | Weapons |
|---|---|---|---|
| Common | light grey | 2 | Frying Pan, Spatula, Glock, Fart Gun, Boomerang, Egg, Boxing Gloves, Rubber Duck, Nail Gun, Shovel, Magic Staff, Crystal Ball |
| Rare | blue | 2 | Nunchucks, Baseball Bat, Shotgun, Draco, Kunai, Steak, Bowling Pin, Yo-Yo, Paint Roller, Power Washer, Medusa's Head, Pandora's Box |
| Epic | purple | 1 | Kusarigama, T-Shirt Cannon, Molotov, Cinder Block, Vacuum Cleaner, Mjolnir |
| Legendary | gold | 1 | Katana, Rocket Launcher, Deck of Cards, Bowling Ball, Wrecking Ball, Excalibur |
| Godly | crimson | — | New weapons from Part 3 |

Every class signature weapon is Common, so starting weapons are easy to upgrade.
The assignment is a first pass; the user can move any weapon.

### Upgrading (copies raise the starting tier)

A weapon's first copy unlocks it at Tier I. Copies are spent to raise its starting tier.
Rarer weapons need fewer copies because they drop less.

| Rarity | I → II | II → III | III → IV | Total |
|---|---:|---:|---:|---:|
| Common | 4 | 10 | 20 | 34 |
| Rare | 2 | 5 | 10 | 17 |
| Epic | 1 | 2 | 4 | 7 |
| Legendary | 1 | 1 | 2 | 4 |
| Godly | 1 | 1 | 1 | 3 |

Copies past Tier IV turn into emeralds.
- Today the code pays a flat 10 per copy (`ChestConfig.OverflowEmeralds`).
- The plan is per rarity: Common 2, Rare 5, Epic 20, Legendary 60, Godly 200.

### Chest tiers (emeralds)

Better chests roll better items (user direction, 2026-09-27: "a legendary in a wooden might be
1%, in magical like 50%, in legendary guaranteed"). Each chest has a fixed number of copies,
a guaranteed number of Rare and Epic copies, and a per-chest chance of a Legendary or Godly
copy. Everything else is Common. All copies of one rarity are one item (Clash Royale style
stacks, e.g. ×12 Frying Pan, ×6 Glock; 1–3 items per rarity until 2026-10-03). The pool is all 36 weapons (plus
Godly); locked-class weapons still drop and show a "Class locked" note.

Current numbers (2026-10-03; source of truth `ChestConfig`, design in RARITY_GODLY_ARMOR.md
section 1, which replaced the bigger 2026-09-27 table):

| Chest | Emeralds | Copies | Rare copies | Epic copies | Legendary | Godly |
|---|---:|---:|---:|---|---:|---:|
| Wooden | free daily | 3 | 25% chance of 1 | 2% | 0.2% | — |
| Silver | 160 | 6 | 1 | 8% | 0.8% | 0.05% |
| Gold | 300 | 10 | 2 | 25% | 3% | 0.2% |
| Magical | 700 | 18 | 4 | 1 | 10% | 0.6% |
| Legendary | Robux / rewards | 20 | 5 | 2 | 100% | 2% |
| Godly (later, not built) | Robux / rewards | 30 | 8 | 4 | 2 | 25% |

Godly also has a visible pity bar (guaranteed after 150 Silver-or-better chests; config value).

Example: a Gold Chest for 300 emeralds gives 30 copies: 24 Common split over three weapons, 5 Rare
split over two, 1 Epic, and a 15% (about 1 in 7) chance that one copy is a Legendary.

Like the reference game, the chest's **[i]** button opens a grid of every weapon it can drop,
tinted by rarity, with that weapon's exact chance per chest (e.g. Frying Pan 9.6%).

The old "every 10th chest lets you pick" is replaced by the Legendary and Godly pity bars.

### Chest looks

Five completely different chests that get grander as they go (user direction 2026-09-27: not
recolours). They share only the finish: chunky, bevelled, baked icon lighting. Built in
`blender-chest-kit/`.

| Chest | Design | Glow |
|---|---|---|
| Wooden | Plank chest, barrel lid, iron straps | Lantern gold |
| Silver | Knight's Vault: octagonal armoured steel strongbox, blue enamel, pyramid lid, shield lock | Rare blue |
| Gold | Royal Treasury: fat bulging walnut chest, tall ribbed dome, lion-paw feet, coins spilling out | Gold |
| Magical | Arcane Reliquary: floating tapered hexagonal reliquary, crystal-spike lid, orbiting shards, runes | Epic purple |
| Legendary | Dragon's Hoard: black lacquer and gold, spined lid, wings, horns, claw feet, sun-gem | Gold-orange |

Each chest glows in the colour of the rarity it's known for, so the chest itself teaches the
colour code. There is no Godly chest: Godly is a rare drop inside other chests, and its
cracked-obsidian, crimson-ember look is saved for the Godly reveal effect.

### Chest screen

Full-screen (reference: user screenshots, 2026-09-27):

- Right: **Your chests** list, one row per tier with owned count; the selected row expands to
  price, ×1/×10 toggle and "What's inside" rarity bars.
- Centre: the chest's 3D model, "10 chests · Ready to open", big **OPEN** and **×10** buttons.

### Opening reveal

1. The chest shakes; its glow colour hints at the best rarity inside.
2. One page per rarity, Common first: heading in the rarity colour ("COMMON"), each weapon as
   a spinning 3D model (existing reviewed models in a ViewportFrame) with a ×N badge, name,
   "WEAPON · COMMON", spare copies, and a NEW! or UPGRADE READY! tag. Page counter "1/3",
   "Tap to continue".
3. Epic and above get a page per weapon, centred and larger, with a sound sting.
4. Godly: screen flash, crimson rays, and a server-wide announcement
   ("EggaRowls found a Godly weapon!").
5. Last page: DONE.

### Built 2026-09-28: chest screen, island and opening

- `ChestConfig` now holds the five tiers, fixed weapon rarities, per-rarity upgrade costs and
  overflow, and the Legendary pity (guaranteed within 50 Silver-or-better chests). Old class chests
  convert to Wooden, the Royal Chest to Legendary (the Robux packs now give Legendary Chests).
- Server actions: `BuyChest(kind, amount)` (emeralds; earned-only where restricted) and
  `OpenChest(kind, amount)` (owned chests only). Amount is 1, 10 or 100; the reply groups every
  copy by weapon.
- **Chest island** (`lobby/InstallChestIsland.luau`): a floating island next to the lobby's east
  island with the five chests on stepped pedestals; each chest has a coloured aura (wisps, seam
  light, sparkles, back glow, ground glow, inner light) and a name / "×3 READY" label.
- **Chest screen** (`ui/ChestScreenUI.luau` + `ChestStage.luau` + `ChestFX.luau`): the camera flies
  from the player to the island and pans between chests. List on the left with owned count,
  price, what's inside by rarity and an [i] odds grid; over the chest: BUY ×n, OPEN ×n and the
  ×1 / ×10 / ×100 amount.
- **Opening:** the camera pushes in; tap 1 and 2 shake the chest and charge the aura (the second
  shake tints it towards the best rarity inside when it is Epic or better); tap 3 bursts the lid
  open with light shafts, sparkles, rings and a flash. Cards fly out of the chest, commons first,
  Epic and Legendary last with their own flash and sting. ×10 and ×100 are one animation with a
  2× / 5× burst and more item icons spraying out. CLAIM or OPEN AGAIN.

## Part 3: Godly weapons

Replaced by RARITY_GODLY_ARMOR.md section 9 (2026-10-01): power 160, one per run, from chests or
the Godly bundles (Blood Phoenix, Shadow Dragon, Godly Starter). The models are in
`weapon-models/godly/`; game code is step 4 and not built yet.

## Part 4: Shop ideas for later (2026-10-01)

The owner compared our store with another Roblox game's shop and called ours too expensive
("no one is spending 10k robux"). Prices were cut to that game's ladder on 2026-10-01 (table
below; source of truth is `MonetizationConfig`).

| Product | Before | After |
|---|---:|---:|
| Legendary Chest ×1 / ×5 / ×12 | 149 / 599 / 1,299 | 49 / 199 / 399 |
| Mega Chest Bundle | 2,999 (15 chests) | 999 (30 chests) |
| Ultimate Chest Bundle (100 chests) | 7,999 | 2,999 |
| Emerald packs | 99 → 9,999 R$, 1 emerald per R$ | 39 → 3,749 R$, ~10 per R$ (+11% to +35%) |
| Starter Pack | 49: 150 emeralds + 1 chest | 49: 1,500 emeralds + 2 chests |
| Arsenal Bundle | 499 | 299 (+1,500 emeralds) |
| Godly Starter / Shadow Dragon / Blood Phoenix | 999 / 1,499 / 2,499 | 799 / 1,199 / 1,799 |
| Class unlock | 149 | 49 |

Highest price anywhere is now 3,749 R$ (about $37). Emeralds at ~10 per Robux put a Gold Chest
(300) near a Legendary Chest's price. Earned income is unchanged, so free players progress at the
same pace.

**VIP: improve soon, not now (owner).** Today: 499 R$ for +25% emeralds, a daily Gold Chest, open
×10 and a VIP tag. The other game's 799 R$ VIP also gives cosmetics people show off. Candidates:
- a VIP weapon aura;
- a VIP crown or helmet cosmetic;
- a better daily chest (Magical instead of Gold).

**Ideas from the other game's shop, not decided:**
- **Limited-time event chest.**
  - A themed chest (theirs: "Inferno") with a countdown, its own 3 / 10 / 25 packs and a big
    bundle with exclusive items.
  - It fits our chest tiers and a Godly-themed season.
- **Faster daily deals.** Their offers refresh hourly with a timer; ours refresh daily.
- **Bonus chests on the biggest currency packs.** Their 30k and 75k key packs add 1–3 Legendary
  Chests and an Epic Chest. We could add chests to Hoard and Treasury the same way.
- **Weapon bundle.** Copies of several weapons at once (theirs: 4 weapons for 599 R$). For us: a
  class's weapons, to raise their tiers.
- **Godly Chest** (user, 2026-10-03). A sixth chest above the Legendary Chest, Robux and rare
  rewards only. Proposal and open questions (price vs the Godly bundles, chance vs guaranteed
  Godly, restricted regions): RARITY_GODLY_ARMOR.md, "Later: the Godly Chest".

## Server rules (all parts)

- Rolls, prices, pity, grants and upgrades happen on the server (`ProfileService`,
  `RogueliteMeta`). The client only requests and draws.
- Odds shown before opening are generated from the same `ChestConfig` table the server rolls.
- Studio keeps in-memory profiles; nothing persists.

## Verification

- Unit tests (Studio command bar): odds tables sum to 100%; grouping never loses copies;
  upgrade costs per rarity; overflow → emeralds; restricted players can open chests only with
  earned emeralds, and cannot buy chest packs or claim paid chest rewards.
- Studio Play: open each chest tier with emeralds, the ×10 flow, the "more emeralds needed" state, the reveal pages,
  an upgrade in the Armory, then start a run and confirm the upgraded tier in slot 1.
- `UILayoutAudit`: 0 problems on the chest screen, reveal and every store tab.
- Not testable in Studio: real Robux receipts, PolicyService-restricted accounts, DataStore
  saving, multiple clients.
