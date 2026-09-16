# Combat Feel, Audio, and VFX Direction

**Status:** Core experience requirement  
**Goal:** Farming a dense enemy group and vacuuming up its rewards should feel satisfying every time without becoming exhausting, muddy, or unreadable.

## The feedback loop

```text
Attack cue → clean hit → enemy reaction → satisfying defeat burst
           → reward scatters → magnetic pull → pickup chain → level/reward payoff
```

Every stage needs its own feedback. If enemies simply lose health and vanish, the main loop will feel hollow regardless of how good the progression system is.

## Hit feedback

A hit can combine several small layers:

- a weapon-specific attack sound;
- a short impact transient;
- a brief enemy flash, squash, recoil, or hit-stop effect;
- a compact damage number when enabled;
- a stronger accent for critical hits, heavy attacks, and armor breaks.

Do not make every layer equally strong. A normal rapid hit should be light. A Frying Pan critical hit should produce a sharp metallic clang and a larger visual ring. A Bowling Ball impact should feel heavy and low. A Katana slash should sound thin, fast, and clean.

### Dense-hit handling

Rapid hits and deaths should create a satisfying cascade. The client should:

- limit simultaneous voices by feedback category;
- vary pitch and sample choice within a narrow range;
- preserve special sounds for critical hits, armor breaks, elites, and bosses;
- prevent rapid weapons from restarting the same sample every frame.

Every defeated enemy still emits an individual short death-feedback event. Voice limits may steal the quietest or oldest sound if many occur on the exact same audio frame, but the system must not synthesize or substitute one generic “multikill” sound for the individual cascade.

## Enemy defeat bursts

Enemies should not silently disappear. A normal defeat sequence should complete quickly:

1. Very short squash, recoil, or freeze at the killing impact.
2. Clear burst, collapse, dissolve, or fragment animation matching the creature.
3. Distinct defeat sound layered with the killing weapon's impact.
4. XP/coin/loot pieces eject in a controlled readable pattern.
5. Corpse visuals clear quickly enough to preserve performance and visibility.

### Creature-specific character

- Slimes can squash and pop into droplets.
- Skeletons can separate into a few recognizable bones.
- Ghosts can stretch and dissolve with a soft vacuum-like sound.
- Ogres should land with a heavier collapse than common mobs.
- Crabs can flip briefly before bursting or fading.

These differences need only one or two cheap signature elements. Do not build long death cinematics for ordinary enemies.

### Mass-defeat behavior

When many enemies die together:

- individual bursts may be visually simplified;
- every enemy triggers its own short death sound, producing a fast layered pop/crunch sequence;
- samples and pitch vary slightly so the sequence does not sound like one file restarting;
- reward pieces remain visibly numerous enough to produce the desired magnetic stream;
- visual tokens may consolidate only at extreme density or in reduced-effects mode, while preserving the apparent volume and collection cadence;
- elite and boss defeat effects remain distinct and are never swallowed by the cluster system.

## Magnetic reward collection

XP, coins, and loot should exist visibly in the world long enough for the player to anticipate collecting them.

### Motion

- Drops eject a short distance from the defeated enemy.
- Inside pickup range, they hesitate only briefly and then accelerate toward the avatar.
- The path curves slightly rather than snapping in a perfectly straight line.
- A small stretch/trail communicates speed near the end of the pull.
- Large collection effects spiral or stream into the avatar instead of teleporting.
- Increased pickup range should be visibly noticeable.

The server owns the reward. The client may animate predicted tokens, but it cannot declare XP, currency, loot, or collection outcomes.

### Pickup audio

Ordinary pickups use short, soft sounds that can form a pleasant sequence. Rapid collection should climb slightly in pitch or move through a small musical pattern, then reset after a short gap.

Avoid unlimited pitch climbing. Each collected token may trigger a very short tick, with strict sample length and controlled polyphony so a large vacuum event produces a continuous sparkling stream instead of one replacement sound.

Recommended hierarchy:

| Reward | Audio/visual treatment |
| --- | --- |
| Ordinary XP | Small color-consistent token and light tick |
| Coin/run currency | Brighter glint and slightly weightier chime |
| Healing | Soft restorative pulse distinct from currency |
| Level gained | Strong but short flourish and HUD response |
| Rare loot | Unique color, beam/glow, anticipation sound, and collection accent |
| Boss reward | Deliberate burst and reward presentation after danger has ended |

Exact drop types remain a design decision. Their feedback language should be planned before final art and audio production.

## Attack animation clarity

The attack effect is more important than literal avatar limb contact.

### Melee

- Slash arcs show direction and effective area.
- Thrust lines show length and width.
- Orbitals show their path without leaving opaque rings across the screen.
- Heavy attacks use a brief anticipation followed by a crisp impact.
- Active and inactive frames should be visually understandable.
- Held weapons may remain mostly static while the clean effect delivers the attack.

### Projectiles

- Every ranged attack has a visible projectile or an unmistakable beam/travel cue.
- Projectile silhouette and color identify the weapon family.
- Trails are shorter and more transparent than the projectile head.
- Piercing, bouncing, returning, and homing should be visible from motion.
- Friendly projectiles remain less visually dominant than hostile projectiles and boss attacks.

### Visual hierarchy

From highest to lowest priority:

1. Enemy and boss attacks that can hurt the player
2. Player health/damage state
3. Elite/boss position and vulnerability
4. Player weapon attack areas
5. XP, coins, and important loot
6. Damage numbers and decorative particles

If a lower-priority effect hides a higher-priority one, the lower-priority effect must become smaller, dimmer, shorter, or disappear.

## Screen-space budget

Use practical limits rather than allowing every upgrade to scale effects indefinitely:

- Area-size upgrades increase gameplay hit areas more aggressively than opaque visual coverage.
- Most friendly effects use transparent edges and short lifetimes.
- Large attacks should contain gaps so the environment and enemies remain visible.
- Damage numbers aggregate or cull during very dense combat.
- Four players' ordinary effects must not tint or cover the entire play space.
- A low-effects mode reduces trails, fragments, secondary particles, persistent ground decoration, and other nonessential presentation.

Avoid full-screen flashes for ordinary attacks. Reserve broad screen treatment for a level-up, boss defeat, or exceptionally rare payoff and keep it brief.

## Audio mix priority

From highest to lowest priority:

1. Imminent boss/enemy danger cue
2. Player taking damage or reaching low health
3. Major attack, critical, elite break, or large multi-kill
4. Rare loot and level-up
5. Ordinary weapon impacts and defeats
6. XP/coin pickup chains
7. Ambience and decorative world sounds

Lower-priority layers should duck slightly when a danger cue or critical health warning plays. Music should not need to be loud for attacks to feel satisfying, since many players may listen to their own music or an audiobook.

## Weapon sound identity examples

| Weapon | Sound identity |
| --- | --- |
| Fart Gun | Compressed puff on fire, soft gas burst on impact; avoid excessively long gross sounds |
| Frying Pan | Sharp metallic clang with a stronger critical resonance |
| Nunchucks | Fast whooshes and light wooden cracks |
| Katana | Thin unsheath/slash transient with minimal reverb |
| Bowling Ball | Rolling rumble, heavy impact, and rare pin-strike accent |
| Rubber Ducks | Small squeaks, aggressively voice-limited during rapid orbit hits |
| Cinder Blocks | Low concrete thud with dust burst |
| Nail Gun | Mechanical pop with a short impact tick |
| Eggs | Light throw followed by a wet crack/pop |
| Mjölnir | Heavy return whoosh, thunder impact, and controlled lightning crack |

## Boss feedback

- Every dangerous attack has an anticipation sound that remains audible over farming noise.
- Boss phases have distinct audio signatures rather than relying only on music.
- Successful dodges, armor breaks, and vulnerability windows receive clear confirmation.
- Boss defeat briefly reduces ordinary noise, then delivers the largest controlled burst of the chapter.
- Reward collection begins after the final defeat cue so the two payoffs do not compete.

## Performance implementation requirements

- Pool common projectiles, particles, drop visuals, and reusable enemy fragments.
- Support dense streams of individual drop visuals. Consolidate only beyond the tested rendering budget or in reduced-effects mode, without changing the reward amount or making the stream feel empty.
- Limit active sound voices by category and distance.
- Cull or simplify distant friendly effects before enemy danger cues.
- Provide effect-detail tiers for low-end mobile devices.
- Test the densest minute, multi-kill burst, magnetic pickup event, and boss attack simultaneously.
- Clean every temporary sound, attachment, trail, emitter, and token when a chapter ends.

Performance optimization must preserve the reward. A lower-end device may show fewer droplets or fragments, but the hit, defeat, magnet pull, and pickup confirmation still need to feel complete.

## Accessibility and player controls

Provide settings for:

- screen shake strength or off;
- damage numbers full, combined, or off;
- friendly effect intensity;
- hit flash intensity;
- critical flash reduction;
- colorblind-safe danger colors;
- master, music, effects, interface, and ambience volume;
- reduced repetitive high-frequency pickup sounds.

## Prototype acceptance test

Before expanding the weapon and mob catalog, one five-minute graybox should prove:

- a ten-plus-enemy simultaneous defeat produces a crisp sequence of individual death sounds without clipping or being replaced by a generic multikill sound;
- slime, skeleton, and ogre defeats feel different with inexpensive effects;
- a large XP pile streams magnetically into the player without stuttering;
- the pickup sequence clearly ends in a level-up payoff;
- Katana, Bowling Ball, and Fart Gun attacks are identifiable with effects only;
- enemy projectiles and boss telegraphs remain visible through the strongest player build;
- the same sequence remains satisfying in reduced-effects mobile mode.
