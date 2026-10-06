# Round 10 events and boss intros

Recorded October 5, 2026. Every map needs a distinctive halfway encounter, and every round 10 event and every boss needs a short, unique introduction matching its theme and design. Hammer Brute is the universal player-facing name. These requirements and the discussion below guide future implementation; this note does not claim the encounters are built.

## Confirmed user direction

- Use **Hammer Brute** universally: cutscene title, boss health bar, Journal, tutorial, admin display labels, encounter messages, and current documentation. Do not show Hammer Zombie or Hammer Zombie Boss as alternate names. Stable internal IDs do not need renaming.
- Every round 10 event gets a little intro/cutscene, including survival events with no single boss.
- Every other boss also gets its own intro, using the existing Hammer Brute introduction as the presentation-quality reference. Each entrance must suit its creature, theme and design, rather than reuse the same hammer-style sky drop.
- Make each event's spawning, objective and completion rule clear to players.
- Multiplayer currently feels too sparse: groups die before a real horde forms. Tune population, refill rate and arrival patterns against actual squad clearing power. The user has not assessed solo pacing. Do not assume solo needs the same increase or solve this only through more enemy health.
- Selected event concepts: exploding zombies in Pine Valley; Crab Rave in Beach Cove, with greater intensity than sideways dancing alone; sarcophagi in Desert Basin; werewolf hunt in Frozen Pass; eruption and splitting slimes in Volcanic Crater.

## Working encounter rules

These preserve the assistant's proposed rules from the discussion. Exact timings, tuning, combat kits and clear conditions remain proposed rather than separately playtested or approved values. Round 10 replaces the ordinary wave; round 20 remains the full map boss.

| Event | Spawn sources and pressure | Objective and clear condition |
| --- | --- | --- |
| Pine Valley: Pop Goes the Zombie | Dense edge-spawned zombie swarm with distinct yellow exploders. They stop, swell, telegraph a radius and detonate; explosions hurt players and enemies and can cause warned chain reactions. | Proposed 60-second survival timer. |
| Beach Cove: Crab Rave | DJ crab with crab reinforcements replacing ordinary spawning. Proposed coordinated rushes, rock bombardments and warned claw-slam rings with gaps. | Kill the DJ crab. |
| Desert Basin: The Tomb Opens | Three sarcophagi replace ordinary edge spawns. Coffins release regular skeletons and mummies in pulses; one releases a single giant mummy once. Each destroyed coffin stops its own future reinforcements. Existing mobs remain. | Destroy all three coffins AND defeat the giant mummy/Tomb Warden. Neither objective alone clears it; no ordinary survival timer auto-clears it. |
| Frozen Pass: Blood Moon Hunt | One alpha plus staggered werewolf packs replace the ordinary mixed wave. Alpha howl buffs nearby wolves; direction-locked charges have warnings and recovery. | Kill the alpha. |
| Volcanic Crater: Eruption | Slime-heavy swarm with Fire Goblins and Ember Spiders. Slimes split within a bounded population budget. Vents stay in place and activate in staggered groups, preserving escape routes. | Proposed 60-second survival timer. Vents are indestructible hazards. |

For tombs, show coffin health, DESTROY TOMBS 0/3, and DEFEAT THE TOMB WARDEN. Automatic targeting must let players deliberately attack a nearby coffin. Proposed coffin pulse interval: 5-7 seconds. The giant mummy's emergence from one coffin is an entrance, not a repeating giant-mummy spawn.

Proposed vent cycle: 1.5-second rumble/orange warning, 8-10 stud damage radius, eruption active for about 2 seconds with damage ticks and a per-player hit cooldown, then safe recovery. Other vent groups charge in sequence. Suggested interaction: geysers also damage enemies so players can lure crowds into them. Damage amount and final timing need tuning. Small debris is cosmetic, short-lived and non-colliding.

Proposed common completion: stop spawning, clear surviving regular enemies without extra kill rewards, then open the shop. Objective/elite events can exceed the normal wave duration. Multiplayer scales supporting crowds and objective/elite durability without changing clear conditions.

## Unique introduction concepts

The requirement for unique intros is confirmed; these specific shots are proposals.

| Encounter | Proposed short entrance |
| --- | --- |
| Pop Goes the Zombie | Camera catches a yellow bloater pushing through zombies, belly swelling with a rising gurgle; reveal the approaching horde and event title. No damaging explosion while controls are taken. |
| Crab Rave | Close on speakers powering up, DJ crab snaps its claws on a bass hit, camera widens to crabs assembling around it. |
| The Tomb Opens | Sand shakes, three coffins rise, one lid crashes down and the stone-fisted mummy steps out. Reveal both objectives. |
| Blood Moon Hunt | Red moon reveal, alpha silhouette howls on the rim, pack answers; alpha lands/steps into the arena and faces the players. |
| Eruption | Low rumble, vent seams brighten in sequence, one preview geyser erupts safely, camera widens to the slime swarm. |
| Hammer Brute | Retain existing hammer-first entrance identity; title must read HAMMER BRUTE. |
| Giant King Crab | Sand/water churns at the rim, enormous claws rise first, then the crab hauls itself into the arena. |
| Pharaoh | Sand spirals around the entrance, Pharaoh rises/reveals with its established model and signature pose; avoid inventing model accessories. |
| Frost Cyclops | Heavy footsteps, camera reveals the club and giant silhouette, followed by a ground strike with a harmless frost preview. Match the established ground-strike kit. |
| Dragon | Shadow sweeps across the arena, dragon descends and lands, then rears its head and roars with a brief fire-breath preview directed away from players. |

## Intro implementation requirements

- Announce the event/boss name and the actual objective before handing back control.
- Suggested initial duration: about 3-5 seconds; tune for repeat play. A shorter repeated/Endless version may be useful, but must retain the boss's unique introduction identity. Skip policy is undecided.
- Include tutorial and Endless boss entry paths in the intro audit. Admin/practice preview behavior needs an explicit implementation decision.
- Keep all players synchronized to server-owned encounter timing. No damage, timer consumption, enemy movement advantage, or lost rewards during a camera takeover. Hold combat safely for all participants; always restore camera and controls, including interruption/death/late-arrival cases.
- Use restrained shake and preserve warning readability. VFX previews in cutscenes must not secretly deal damage.
- Combat, spawning, objective health, damage and rewards stay server validated. Practice and admin fixtures must not award persistent rewards or use production DataStores.

## Art references and latest feedback

Reference folder: [round 10 art sheets](../art-references/round-10-events-2026-10-05/).

- Exploding zombie: latest v3, extremely bloated yellow body with proper hands. Must read as an explosive enemy at gameplay distance.
- DJ crab: v1 accepted.
- Sarcophagus: v1 lid accepted; model body/lid separately.
- Mummy: v2 distinct stone mask, stone fists and teal sash; working name Tomb Warden. The user requested stronger differentiation than size alone.
- Alpha werewolf: v2 russet fur and charcoal mane, distinct from the normal gray wolf.
- Volcanic vent: v1 accepted.
- Debris: latest v3 contains small fragments only. Matchstick was a scale reference and has been removed. Earlier large rocks were not suitable as the desired small eruption debris.
- All sheets have three views; they are concept references, not calibrated geometric blueprints. Preserve game style and reconcile view discrepancies in Blender. Prompt files are stored alongside the sheets.

## Known naming fix and verification status

Observed source mismatch: `studio-prototype/combat/bosses/MapBossDefs.luau` has `name='Hammer Brute'` but `introName='HAMMER ZOMBIE BOSS'`; `studio-prototype/combat/BossIntro.client.luau` also maps the legacy HammerBoss to `HAMMER ZOMBIE BOSS`. Both require correction in the implementation pass, plus a broader player-facing naming audit.

This update changes documentation only. No source combat changes, Rojo build, Studio synchronization or Studio play tests ran for this note-taking request. When implementing, build only the combat overlay specified in AGENTS.md, preserve unrelated map instances, synchronize source and Studio, and record the actual solo/multiplayer and intro test coverage.
