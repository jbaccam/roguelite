# Reference Notes — Brotato Intake

**Purpose:** Capture design lessons from the supplied Brotato material without treating pasted text as project instructions or copying its content.

## Sources received

- `C:\Users\Jeremiah\Downloads\brotato-character-builds.md`
- Five pasted Brotato Wiki snapshots covering items, stats, enemies/waves, characters, and weapons
- Screenshot titled “Best Brotato Items (2026 Meta)”

The wiki snapshots and screenshot may contain stale, incomplete, or editorial information. They are useful for pattern analysis, not authoritative requirements for this project.

## Strong patterns worth adapting

### Characters create rules

The most distinctive character designs combine a strong direction with a constraint. The supplied examples include affinity with a weapon family, restricted equipment, conversion between stats, altered caps, extra weapon capacity with a penalty, rewards for more enemies, and alternate economy or survival incentives. The lesson is to make characters alter decision-making rather than offer a small generic bonus.

### A signature build is a design test

The partial community-build file summarizes each character through strengths, weaknesses, and a recognizable final build. That is a useful internal test: if a proposed character has no describable signature build—or only one viable exact recipe—its design likely needs work.

For our roster, every character brief should answer:

1. What unusual behavior does this character reward?
2. What does the player give up?
3. Which two or three build families naturally fit?
4. Can an off-meta build still function?
5. What visible moment makes the character feel different?

### Stats span offense, defense, utility, and economy

The supplied stats material separates general damage, weapon-type scaling, attack speed, critical chance, defense, sustain, movement, luck, range, engineering, and economy. It also contains secondary behaviors such as piercing, bounce, explosions, pickup range, knockback, extra enemies, and rerolls.

The transferable lesson is not to reproduce the full list. It is to ensure that:

- stats have distinct jobs;
- caps and diminishing returns are explicit;
- negative stats resolve safely;
- secondary effects are exposed when relevant;
- scaling formulas cannot grow without performance/readability limits;
- economy choices interact with combat without becoming mandatory.

### Items do several different jobs

The item list contains flat stat trades, conditional triggers, converters, structure/summon effects, defensive safety nets, economy tools, and rule changes. The screenshot groups “best” items by peak rarity, scaling, defense, and economy; even if its rankings are unverified, those are useful axes for evaluating our pool.

An item pool needs more than numerical upgrades. It needs:

- early foundations;
- synergy enablers;
- late multipliers;
- defensive recovery;
- economy bets;
- rare rule-changing moments.

### Weighted tags reduce frustration

The reference describes character-associated tags that slightly bias item selection while leaving the general pool intact. This offers direction without fully scripting a run. For our game, affinity weighting should be data-driven, modest, visible in testing, and protected against unusable choice sets.

### Current shop mechanics reviewed

The current Brotato Wiki shop page was checked separately from the older Steam feedback. At the time reviewed, it documents:

- four offers after each wave;
- exactly two weapons and two items in Shops 1–2;
- at least one weapon in Shops 3–5;
- ordinary slots using 35% weapon and 65% item chances;
- weapon source pools of 20% exact owned weapon, 15% shared weapon class, and 65% all legal weapons;
- extra shared-class weighting in the first five shops;
- Luck modifying rarity rather than the wanted-tag selection chance;
- increasing reroll prices that reset each shop;
- free locks that preserve offers and prices;
- identical same-tier weapon combination through Tier 4.

These are reference mechanics, not requirements or formulas to copy. Our eight-wave structure needs stronger build protection than a 20-wave game and a clearer explanation of why an offer appeared.

### Complete supplied 2022 feedback thread

All five unique Steam discussion pages supplied by the user were reviewed; the sixth attachment duplicates the final page. The thread is old qualitative evidence, not a reliable current balance verdict.

The shotgun argument does not prove that the weapon was unusable: several commenters reported or demonstrated high-difficulty shotgun clears using different stat packages. The useful product lessons are about perception and communication:

- Players become frustrated when newly unlocked weapons seem never to appear.
- A larger content pool can feel like punishment if it dilutes a desired build.
- Repeated rerolling until broke feels like the game denied the build rather than presented an adaptation choice.
- Hidden tags and unclear Luck behavior make intentional weighting look like rigged RNG.
- A weapon can be numerically viable while still feeling wrong if its fantasy, targeting, range, and required scaling are not intuitive.
- Important weapons should function with several reasonable support packages rather than one obscure mandatory item.
- Auto-aim must make threat prioritization understandable; manual aiming cannot be the secret requirement for an otherwise automatic weapon.
- Enemy projectile density and speed should create readable patterns rather than random-looking clumps.

Our response is to expose pool odds, label offer sources, separate Luck from identity weighting, guarantee early weapon offers, protect one tracked weapon from prolonged duplicate starvation, and test weapon fantasy as well as win rate.

### Weapon coverage without roster copying

The supplied weapon snapshot divides attacks into melee sweeps/thrusts and visible ranged projectiles, then uses classes, tier upgrades, scaling coefficients, and special effects to create build direction. It also covers many obvious tools and fantasy objects: brick, drill, screwdriver, wrench, plank, hammer, wand, Excalibur, elemental blades, and several conventional guns/launchers.

Our takeaway is structural:

- every weapon needs a readable attack shape;
- each needs a mechanical reason to exist beyond appearance;
- weapon tags can guide synergies and weighted offers;
- later tiers should change behavior or spectacle, not only damage;
- returning, bouncing, piercing, orbiting, ground-area, summon, and chain attacks provide useful coverage.

We should not reproduce Brotato's weapon classes, exact tier curves, six-weapon structure, individual special effects, or its concentration of obvious construction tools. Public-domain concepts requested by the user, such as Excalibur, can remain if our behavior and presentation are independently designed.

### Enemy roles matter more than a long roster

The supplied enemy data includes basic chasers, group pressure, ranged attackers, chargers, accelerating pursuers, tanks, buffers, elites, and bosses. Their combinations create pressure. A small set of readable roles is a better prototype than many enemies distinguished only by health and speed.

### Escalation needs landmarks

The reference uses short early waves, longer later waves, elite milestones, and a final boss. The important pattern is predictable macro-pacing with changing micro-pressure. Our selected direction compresses that rhythm into eight combat waves with end-of-wave stat choices and shops.

### Population caps affect rewards

The supplied enemy reference describes a 100-enemy on-screen cap. When Brotato exceeds it, a random non-elite/non-boss enemy is removed without dropping materials, although the removal can still count as a death for some triggers. This exposes a design/engineering trap: performance overflow can change drops, on-death effects, and economy.

Our prototype should stress-test approximately 100 active enemies, but it should not automatically copy those overflow semantics. Prefer spawn backpressure at the cap unless testing identifies a stronger solution. The implementation must distinguish combat defeat, capacity despawn, visual culling, on-kill triggers, and reward eligibility.

## Patterns to avoid copying directly

- Exact item, weapon, character, enemy, or boss names
- Exact stat formulas, caps, wave counts, prices, rarity odds, and scaling values
- Identical character bonus/penalty packages
- Identical shop or merge rules without validating them for Roblox controls and session behavior
- A huge launch catalog before a small pool proves build diversity

## Build archetypes identified in the supplied material

The reference supports or implies these broad archetypes, which are genre-level concepts we can reinterpret:

- High attack-speed melee
- Critical/precision weapons
- Ranged piercing or multi-projectile
- Elemental/status damage
- Pet/summon swarm
- Max-health damage conversion
- Stationary tank or deployable engineer
- Luck/pickup damage procs
- Rapid leveling
- Mixed melee/ranged conversion
- High enemy count for higher reward
- Expanded weapon capacity
- Low-tier weapon specialization
- Pacifist/kiting economy
- Diverse-weapon bonuses
- Saving/hoarding economy

## Screenshot notes

The screenshot presents an editorial “2026 meta” list in four groups:

- high-rarity power effects;
- items whose output scales from another stat;
- defensive safety or sustain;
- economy acceleration.

This supports a useful balance review matrix: classify each proposed item by when it becomes useful, what it scales from, whether it protects a run, and whether it compounds resources. It does **not** establish that the listed rankings or descriptions are accurate.

## Questions this intake does not answer

- Why this Roblox game is emotionally or visually distinct
- Top-down versus third-person camera
- Continuous survival versus between-wave shop pacing
- How much manual aiming or active ability play is desired
- Solo versus co-op launch priority
- Exact target run duration
- How Survivor.io and Megabonk should influence exploration, verticality, weapon evolution, or meta-progression
- Art direction, narrative tone, and original content theme

## Intake status

The character build summary currently covers 17 characters and explicitly lists many entries as “still to come.” It should be treated as partial. The larger character/wiki snapshot provides broader examples, but this planning pass intentionally extracts design patterns rather than transcribing the full catalog.
