# Progression and Session Flow

**Status:** Authoritative progression design  
**Updated:** 2026-09-26  
**Goal:** Every run pays out something, harder maps pay more, and players always have a next thing to chase: a stronger starting weapon, a new armor set, the next map, a longer Endless record, or a specific achievement unlock.

Labels follow the master design: **Confirmed** is the user's direction; **Proposal** is the current recommendation and can change after playtesting.

## Summary

- **Confirmed:** Five maps, each harder than the last and paying better rewards.
- **Confirmed:** Every map is won by surviving to **wave 20**. After the win, the player can keep going in **Endless**.
- **Confirmed:** Rewards are **keys**. Harder maps and more waves survived give more keys.
- **Confirmed:** Keys open **chests**. Chests give copies of weapons (and armor).
- **Confirmed:** Duplicate copies of a weapon raise the tier it **starts** at. A player can enter a run with a Tier II, III, or IV starting weapon instead of Tier I.
- **Confirmed:** Players unlock **armor** as four pieces (helmet, chestplate, leggings, boots) and wear them into each run. Set bonuses at 2 and 4 pieces of one set (decided 2026-09-27).
- **Confirmed:** Achievements and quests give deterministic unlocks, e.g. "Win with 4 Thrower weapons → unlock Molotovs." Some passives are gated this way too.
- **Removed:** Blueprints, Permanent Weapon Levels 1–10, Universal Parts, Weapon Parts, and cases. See [What changed](#what-changed-from-earlier-docs).

## What saves and what resets

| Saved permanently | Resets after every run |
| --- | --- |
| Owned weapons and their copy counts / starting tier | Run level and XP |
| Owned armor and its copy counts / tier | Level-up stat choices |
| Unlocked classes | Weapons bought during the run |
| Map wins and best wave reached on each map | In-run weapon tiers from combining |
| Keys and unopened chests | Passive items |
| Achievement and quest progress | Crystal shards and shard bags |
| Unlocked passives (added to the run shop pool) | Rerolls, locked offers, current health |
| Cosmetics, settings, last-used loadout | |

## The five maps

Each map is its own difficulty step, and each map has three difficulties (below). **Default, 2026-09-27:** winning a map on **Hard** unlocks the next map. This slows the map rush so players stay on a map longer while chest upgrades catch up. It is a one-line rule in `RunSetupRules.mapUnlocked` if Normal should unlock the next map instead.

| # | Map | Boss (wave 20) | Unlocked by | Keys per 5 waves reached — proposal |
| ---: | --- | --- | --- | ---: |
| 1 | Pine Valley | Hammer Zombie Boss | Available after the tutorial | 1 |
| 2 | Beach Cove | Giant King Crab | Win Pine Valley on Hard | 2 |
| 3 | Desert Basin | Pharaoh | Win Beach Cove on Hard | 3 |
| 4 | Frozen Pass | Frost Cyclops | Win Desert Basin on Hard | 4 |
| 5 | Volcanic Crater | Dragon | Win Frozen Pass on Hard | 5 |

### Difficulty tiers

**Confirmed 2026-09-27:** every map has Normal, Hard and Nightmare tabs on the map-select screen. Harder tiers only buff enemies (no new rules) and pay more keys. Starting values:

| Tier | Enemy health | Enemy damage | Keys | Unlocked by |
| --- | ---: | ---: | ---: | --- |
| Normal | ×1 | ×1 | ×1 | The map itself |
| Hard | ×1.6 | ×1.3 | ×1.5 | Winning Normal on that map |
| Nightmare | ×2.5 | ×1.6 | ×2 | Winning Hard on that map |

Example: Pine Valley pays 1 key per 5 waves, so a Normal win pays 4 keys, Hard pays 6 and Nightmare pays 8. The first-win bonus (5 × map number) is paid once per map *and* difficulty and uses the same multiplier (rounded). Wins and best waves are saved per map and difficulty; Normal keeps the plain map id (`PineValley`), harder tiers use `PineValley/Hard`. At 15–20 minutes a run, reaching Volcanic Crater takes at least 8 wins (about 2–2.5 hours) instead of 4.

Mob rosters per map live in [Map Mob Roster](MAP_MOB_ROSTER.md). Castle Fields remains a later-content idea outside these five.

**Proposal: how each map gets harder.** Enemy health, damage and spawn budget rise with the map number; later maps add more ranged and lunging enemies earlier in the run. Difficulty comes from role mix and timing first, raw stat inflation second.

**Built 2026-10-01: regular-enemy stats per map** (`RunSetupRules.Maps`, `R.enemyScale`). The user found late-map mobs dying to one hit from a Tier I pan at base stats. Each map now has three numbers:
- **Extra waves:** health starts that many waves further along its growth.
- **Health multiplier:** applied after the extra waves.
- **Damage multiplier:** applied to each hit.

Difficulty multiplies on top. Map bosses keep their own health.

| Map | Extra waves | Health | Damage | Example at wave 1 → 20, Normal |
| --- | ---: | ---: | ---: | --- |
| Pine Valley | 0 | ×1 | ×1 | Zombie 3 → 41 HP |
| Beach Cove | 4 | ×1.15 | ×1.2 | Crab 14 → 58 HP |
| Desert Basin | 8 | ×1.3 | ×1.4 | Skeleton 26 → 76 HP (2 → 5 pan hits) |
| Frozen Pass | 12 | ×1.45 | ×1.6 | Werewolf 64 → 147 HP |
| Volcanic Crater | 16 | ×1.6 | ×1.8 | Goblin 58 → 119 HP (4 → 8 pan hits) |

Each map's Normal stays a little under the previous map's Hard. The ramp is gentle because runs still start every weapon at Tier I: chest tiers don't carry into runs yet (`ShopService` `newState`).

**Boss health, 2026-10-01:** cut 25%. Hammer 18,000, King Crab 21,000, Pharaoh 24,000, Frost Cyclops 27,000, Dragon 31,500.
- **Why:** a balanced wave-20 build (about 16 level-ups and a few shop items) deals roughly 300–560 DPS. At 24,000 HP that took 60–115 s. It now takes about 45–90 s.
- **Starting kit:** six Tier I weapons at base stats deal only 80–120 DPS (Gunner about 210).

**Proposal: intended power per map.** Map 1 is winnable with a Tier I starter. Map 3 is comfortable around a Tier II starter with armor. Map 5 expects roughly a Tier III starter plus upgraded armor. Skilled players can win below those targets. This is what makes chest upgrades matter: they're the key to pushing into the next map.

## The 20-wave run

**Confirmed:** Wave 20 is the win condition on every map. This replaces the older eight-wave, eight-minute chapter.

| Waves | Proposed length | Role |
| --- | ---: | --- |
| 1–4 | 25–35 s | Learn the starter, pick a direction |
| 5 | 40 s | **Elite wave** |
| 6–9 | 40 s | Second pressure type, build specializes |
| 10 | 45 s | **Horde wave** |
| 11–14 | 50 s | Mixed roles, denser crowds |
| 15 | 55 s | **Stronger elite wave** |
| 16–19 | 55–60 s | Final build checks |
| 20 | Up to 90 s | **Map boss**; the wave ends when the boss dies |

Nineteen intermissions of about 10–15 seconds put a full clear around **15–20 minutes**. Combat stays low-attention enough to play with music or an audiobook. There are still no mid-run checkpoints.

After every wave, as already built in the prototype:

1. Remaining crystals pull in; uncollected value goes into the shard bag.
2. Banked level-ups resolve one at a time: **four** stat cards, reroll costs shards. See [level-up readiness](studio-prototype/combat/LEVEL_UP_READINESS.md).
3. The four-offer shop opens. See [shop readiness](studio-prototype/combat/SHOP_GAMEPLAY_READINESS.md) for the current offer rules.
4. The next wave starts when everyone is ready or the timer ends.

Leveling never pauses combat. Crossing an XP threshold during a wave plays a short sound and adds a pending-choice count to the HUD.

### Endless — wave 21 and beyond

**Confirmed:** After the wave 20 boss dies, the player can keep going for fun and bigger rewards.

- The win screen offers **Cash Out** or **Keep Going**. The map win and wave 20 rewards are saved immediately either way.
- **Proposal:** Enemies keep scaling. An elite or boss returns every five waves.
- Keys keep coming at the same per-five-waves rate for that map.
- Dying in Endless keeps everything earned. The run already counts as a win.
- The game records each player's **best wave per map**. A leaderboard can use it later.
- **Open:** If players find an idle farming trick, add a per-run or daily key cap for Endless only.

## Keys

- **Earning (proposal):** Reaching wave 5, 10, 15, 20, 25, … on a map gives that map's key value. The first win on each map adds a one-time bonus of **5 × map number** keys.
- **A loss still pays.** Dying on wave 12 in Desert Basin passed waves 5 and 10, so it earns 6 keys.
- **Examples:** A Pine Valley win gives 4 keys (+5 the first time). A Volcanic Crater win gives 20 keys (+25 the first time). Pushing Volcanic Crater Endless to wave 30 adds 10 more.
- Quests and some achievements also give keys.
- **Keys are earned only by playing.** They are not sold for Robux. Chests are random, and Roblox's paid-random-item rules also apply to anything Robux can buy that opens a random reward. See [Monetization](MONETIZATION_AND_REWARDS.md).

## Chests

- **Proposal:** A chest costs 3 keys and gives one copy.
- **Proposal: chest types.** A **Class Chest** for each class drops a copy of one of that class's chest-eligible weapons. An **Armor Chest** drops an armor copy. The player picks which chest to open, which lets them aim for the weapon they care about.
- Every chest shows its full contents and odds before opening.
- **Bad-luck protection (proposal):** Every 10th chest of the same type lets the player **pick** the copy.
- **Proposal:** Copies beyond Tier IV convert back into keys at 1 key per 2 extra copies, so late duplicates are never worthless.

## Duplicates → upgrade → starting tier

**Confirmed direction, 2026-09-27 (replaces the automatic copy-count rule):** The first chest drop of a weapon unlocks it at Tier I. Every later drop adds +1 to that weapon's upgrade bar. When the bar is full the player presses **Upgrade**, which spends those duplicates and raises the starting tier. The UI shows only numbers, never the word "copies": e.g. `5 / 2` → Upgrade → `3 / 4`.

| Upgrade | Duplicates spent — proposal |
| --- | ---: |
| Tier I → II | 2 |
| Tier II → III | 4 |
| Tier III → IV | 8 |

- Leftover duplicates carry over after an upgrade (5 held, spend 2 → 3 toward the next).
- **Pacing check needed:** these proposal costs total 14 duplicates to Tier IV, versus 7 under the old "8 total copies" rule. Re-check against the pacing target below before locking values (`L.UpgradeCost` in `studio-prototype/ui/LobbyUI.luau`).
- The saved tier applies to the **one starting weapon** the player brings in. Copies bought from the run shop still start at the shop's tier.
- Tier forms are the same four behavior tiers used in runs. For example, the Glock goes Glock → Extended Clip → Switch → Akimbo Switches.
- A starter already at Tier IV can't combine further, so the run shop stops offering its exact duplicate. This uses the existing "remove capped choices" rule.
- **Balance note:** A Tier IV starter is a big early power jump (prototype damage multipliers are 1, 1.20, 1.45, 1.75, plus the behavior upgrade). The map ladder is tuned around this. Later maps expect upgraded starters.

**Proposal pacing target:** A focused player reaches their first Tier II starter within about an hour, their first Tier IV after roughly 10–15 hours, and a full collection after 100+ hours.

## Weapon ownership

"Blueprint" was the old word for *you own this weapon*. It's gone. Ownership is now just "you have at least one copy".

- An owned weapon can be picked as the starting weapon if it belongs to the selected class.
- Only owned weapons appear in the run shop. Unlocking weapons makes new runs play differently.
- **Proposal:** New accounts own the three starter-class signatures plus about half the roster, so shops feel varied from the first run. Most of the rest drops from Class Chests. A smaller set gets its first copy only from an achievement (see below). After that, their duplicates can drop from chests too.

## Armor

**Confirmed:** Players unlock armor and wear it into each run. This reverses the earlier "no armor equipment system" decision.

- **Confirmed (2026-09-27):** Four armor slots (helmet, chestplate, leggings, boots), shown on the avatar and picked in the Armory. This replaces the earlier one-outfit proposal; the player preferred pieces because collecting a full set keeps players playing longer.
- **Proposal:** Each piece gives part of its set's defensive stat package; 2 pieces of one set give the set bonus and 4 give the set's **signature perk**. Each armor set gives a defensive stat package (Armor, Max HP, contact resistance, dodge, etc.) plus one **signature perk**. Tiers I–IV use the same copy rule as weapons. Higher tiers raise the numbers and strengthen the perk.
- Armor stays comedic everyday gear, not medieval plate. Starting concepts come from the archived sets in [BRAINSTORM_FUNNY_GEAR.md](BRAINSTORM_FUNNY_GEAR.md#armor-set-ideas--stranger-pass) (Wrong Sport, Fridge Raider, Grandma's House, Tiny Car, and others). Pieces layer onto the Roblox avatar (helmet, shoulders, backpack, waist) rather than replacing it.
- **Proposal scope:** 1 free starter set, 2–3 sets in the vertical slice, 6–8 at launch.
- The Armor **stat** still exists. Armor sets, level-up cards and passives can all raise it.
- **Open:** Passive items that appear as hats or glasses (Pot Lid, Safety Helmet, Comically Large Glasses) may overlap armor pieces. They need a rule for which one renders.

## Classes

- New accounts own **Brawler, Gunner, and Mage**. **Thrower, Juggler, and Handyman** unlock through achievements (early purchase is optional; see Monetization).
- A class sets which owned weapons can be the starter, plus its always-active bonuses and home-weapon affinity bonuses. Current values: [Character stats](studio-prototype/combat/CHARACTER_STATS.md).
- Every weapon has **one home class**. There are **6 classes × 6 home weapons = 36 weapons**. Any class can still buy any owned weapon mid-run.
- The prototype has **six weapon slots**. Two equipped home-class weapons activate the class's first affinity bonus, and four activate the stronger one. That leaves two flexible slots for off-class weapons.

## Achievements and quests

**Built 2026-10-02 (plans/2026-10-01-H-store-and-quests.md):**
- 3 daily quests pay emeralds.
- A streak counts days with all 3 daily quests done, with rewards on days 1-30.
- 8 trophy roads have 5 tiers each.
- 5 unlocks give the Thrower, Juggler and Handyman classes, Mjolnir and the Samurai set.
- Achievements that the game can't track yet (loadout-condition wins, passive unlocks) were dropped.

**Confirmed:** Deterministic unlocks tied to achievements, e.g. "Win with 4 Thrower weapons → unlock Molotovs." Some passives are gated this way so new runs feel different.

- **Achievements** are permanent, one-time goals with visible requirements. Their rewards are a *specific* named unlock (class, weapon, passive, armor set) or keys. They're never random.
- **Quests** are rotating daily and weekly goals that pay keys. Missing a day loses nothing permanent.
- The old weapon and class "mastery" tracks are folded into achievements (e.g. "Win 3 maps with the Glock").

**Proposal: example achievements.** Final list and targets to be tuned.

| Achievement | Unlocks |
| --- | --- |
| Reach wave 10 on Pine Valley | Thrower class |
| Win Pine Valley | Juggler class |
| Defeat 1,000 enemies with Construction/Utility weapons | Handyman class |
| Win any map holding 4 Thrower weapons | Molotovs (weapon) |
| Win a map using only Gun-tagged weapons | Rocket Launcher (weapon) |
| Chain lightning 1,000 times | Tinfoil Antlers (passive) |
| Kill 500 burning enemies | Grandma's Oven Mitt (passive) |
| Win with 3 or more projectile weapons | Two Straws, One Juice Box (passive) |
| Defeat 3 different map bosses | Bone Crown (passive) |
| Win Frozen Pass | Mjolnir (weapon) |
| Reach wave 30 in any Endless run | An armor set |

**Proposal:** About 20 of the 37 passives are available from the start. The rest unlock through achievements.

## First-time player flow

Matches [Lobby and first-run flow](LOBBY_AND_FIRST_RUN.md):

1. The first join goes straight into a short guided tutorial as the base avatar with one fixed weapon: three short waves and an easy boss.
2. The result screen explains that the run build resets, then grants enough keys for **one chest**.
3. The first lobby visit introduces Loadout (class → starting weapon → armor) and Play, then guides the first chest opening.
4. Pine Valley is the first real map.

Tutorial replays never farm keys. Studio practice never grants persistent rewards, and DataStores stay disabled in Studio by default.

## Lobby loadout

```text
Loadout: Class → Starting weapon (owned, that class; shows its tier) → Armor
Play:    Map (unlocked only) → solo or party → queue at a portal
```

The last valid loadout is remembered. After a run, the player should be able to open a chest, see what upgraded, and queue again within 30–60 seconds.

## Multiplayer handling

- Each player has a personal level-up and shop screen. Combat resumes when everyone is ready or the timer ends.
- A player who times out keeps unspent shards and gets no automatic purchase. Unresolved stat choices use a safe default so nobody holds the team up.
- Each player earns their own keys from the waves the team reaches.
- **Open:** Party size, and whether a party can enter a map that only the leader has unlocked.

## Result screen

The server writes one idempotent reward receipt per run:

- map, win/loss, best wave reached;
- keys earned (wave milestones, first-win bonus, Endless);
- achievement and quest progress, plus anything newly unlocked;
- run summary stats.

Then: Open Chests, Play Again, or Lobby.

## What changed from earlier docs

| Old system | Now |
| --- | --- |
| Blueprints | Just "you own at least one copy" |
| Permanent Weapon Level 1–10, Universal Parts, Weapon Parts, Coins for upgrades | Copies raise the starting tier (I–IV) |
| Cases and case meter | Chests opened with keys; pick-a-copy every 10th chest |
| Eight waves, ~8 minutes, boss at wave 8 | Twenty waves, ~15–20 minutes, boss at wave 20, then Endless |
| Chapters unlocked by account progress | The next map unlocks by winning the previous map |
| No armor equipment | Four upgradable armor pieces per run, with 2- and 4-piece set bonuses |
| Weapon and class mastery tracks | Folded into achievements |
| Account level and account XP | **Proposal:** Removed. Map wins, achievements and collection are the progress bars. |
| Five weapon slots | Six, matching the working prototype |
| Three level-up cards | Four, matching the working prototype |

## Open decisions

1. Final key values, chest price and pity interval (the numbers above are starting proposals).
2. Which weapons are owned at the start, which drop from chests, and which are achievement-first.
3. The first armor sets (four pieces each), their bonuses and perks, and the passive-accessory overlap rule.
4. Whether Endless needs a key cap.
5. Party size and map access for mixed-progress parties.
6. Whether any Robux product may touch starting tiers (see Monetization). The current default is no.
