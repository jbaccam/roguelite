# Round 10 encounter specification

Updated October 9, 2026. This is the consolidated design and implementation handoff for the five map-specific round 10 events in Wavebreaker: Survive the Swarm. It includes models, health displays, objectives, animation, cinematics, audio, authoritative gameplay, multiplayer pacing and acceptance tests.

## Status and precedence

Confirmed requirements come from the user's October 5–9 conversation: a distinctive halfway event on every map; the five selected themes; visibly distinct elite designs; complete DJ crab with equipment already fitted; health bars/UI, full animations and unique cinematic introductions; stronger multiplayer horde pressure; Hammer Brute as the universal display name; and Syn Cole — Feel Good as the requested Crab Rave music.

This document consolidates those requirements with the proposed encounter mechanics below. Numerical values, exact shots, attack kits, completion details and display policies are recommended initial specifications, not separately approved tuning or completed implementation. This document takes precedence over older round-10 brainstorms for the consolidated proposal. Current production code and verified reports establish what actually runs. No new model, audio upload, runtime integration or Studio test is claimed by this document.

Round 10 is an event within the selected map/run difficulty, not a separate queue or game mode. Round 20 remains the map's full boss. Do not also spawn the old weaker wave-10 map boss when the replacement event is active.

## Shared encounter contract

| Phase | Required behavior |
| --- | --- |
| Prepare | Resolve selected map/difficulty/party and event assets. Finish previous wave flow; reserve objective/elite entities and spawn capacity; suppress competing ordinary wave spawners. |
| Intro | Brief unique cinematic, name and objective reveal. Hold combat time, movement/attacks and damage safely for all participants while input/camera is taken. |
| Active | Server advances event clock, attacks, objective health, arrivals and clear condition. Clients render matching bars, animations, effects and music. |
| Complete | Latch success once; stop arrivals; cancel warnings/attacks; clear remaining ordinary adds without kill rewards; settle legitimate earned rewards once; show short completion feedback. |
| Shop | Restore normal camera, input, lighting and music; continue existing shard/level-up/shop flow into wave 11. |
| Failed or aborted | Cancel every callback/effect/music instance and restore presentation. No objective success rewards. Use established death/leave settlement rules. |

Use a run/encounter generation ID for every queued arrival, hit, cinematic and delayed callback. An old callback cannot spawn or damage anything in a later wave. Missing critical assets must produce an explicit safe fallback or an actionable failure, never a silently stuck wave. Keep an existing round-10 fallback available until each replacement is validated.

## Event overview

| Map and title | Population | Primary goal | Proposed clear condition |
| --- | --- | --- | --- |
| Pine Valley — Pop Goes the Zombie | Dense zombie arrivals with yellow exploders replacing the ordinary wave profile. | Survive and use warned explosions against crowds. | 60 seconds of active combat. |
| Beach Cove — Crab Rave | One DJ crab plus crab and rock-thrower arrivals; no competing ordinary profile. | Defeat the DJ while dodging coordinated pressure. | DJ health reaches zero. |
| Desert Basin — The Tomb Opens | Three coffins are the only regular spawn sources; one Warden emerges once. | Destroy spawn sources and kill the Warden. | All 3 coffins destroyed AND Warden dead. |
| Frozen Pass — Blood Moon Hunt | One alpha and staggered werewolf packs replacing ordinary mixed spawns. | Defeat the alpha and handle empowered packs. | Alpha health reaches zero. |
| Volcanic Crater — Eruption | Slime-heavy arrivals with Fire Goblins/Ember Spiders; fixed alternating vent hazards. | Survive while routing crowds through eruptions. | 60 seconds of active combat. |

Boss/objective events remain open after the ordinary 40-second wave duration. Survival timers start after the intro and pause with actual combat pauses. Show the real completion condition; no hidden timer clears a tomb or leader encounter.

## Health bars and UI

Every damageable thing must have a truthful health display. The requirement applies to ordinary mobs, exploders, leaders and coffins. Decorative parts and indestructible hazards do not get misleading empty or infinite-health bars.

| Entity | Display |
| --- | --- |
| DJ crab, Tomb Warden, alpha | Persistent top encounter health bar with name, current/max health or readable percentage, and brief delayed damage trail. World bar follows the actor when useful. Hide duplicate world bar when it obscures the same target. |
| Sarcophagi | Each has its own persistent world-space bar and a stable A/B/C identity. HUD shows three compact corresponding status entries plus destroyed count. Visible through presentation only as needed; no false target through walls. |
| Exploding zombies | Compact world health bar while visible/nearby, plus a separate arming countdown/state indicator. Countdown must never replace or masquerade as health. |
| Ordinary adds and slime children | Compact health bars when damaged, targeted or close enough to threaten. Health remains available for each entity; fade full-health distant bars to prevent a wall of UI. |
| Vents | Charge/ACTIVE/cooldown indicator and ground radius. Mark as a hazard; no health bar under the indestructible design. |
| Debris, headphones, speakers, stone mask/fists | Cosmetic components, not separately damageable targets. No independent health bars. |

If destructible vents are chosen later, change gameplay and display contracts together; do not add a bar alone.

Use existing UITheme fonts, spacing, colors and settings. Do not introduce a visually separate UI system for these encounters. Reserve top space below platform safe areas; objective panel must not cover the boss bar, crosshair, team information or mobile controls. Avoid color-only state communication: combine text, icons, fill and shape. Support large text and UI scaling.

Server replicates authoritative health and objective states. Client smoothing is cosmetic and never changes health. Clamp displays to valid values and ignore stale generations. Handle death/removal, reset, reconnect/late join where supported, and simultaneous coffin/leader deaths without ghost bars or briefly resurrected fills. Cull pooled world bars with their entities.

Proposed event text:
- Pine: POP GOES THE ZOMBIE / SURVIVE 01:00. Arming enemy cue: ABOUT TO BURST.
- Beach: CRAB RAVE / DEFEAT THE DJ CRAB, with DJ CRAB health.
- Desert: THE TOMB OPENS / TOMBS DESTROYED 0/3 and WARDEN ALIVE/DEFEATED, with TOMB WARDEN health.
- Frozen: BLOOD MOON HUNT / DEFEAT THE ALPHA, with BLOOD MOON ALPHA health. Buff cue: PACK EMPOWERED.
- Volcanic: ERUPTION / SURVIVE 01:00. Vent cues: CHARGING / ERUPTING / COOLING.
- Completion: EVENT CLEARED, then the existing shop transition. Do not fabricate new persistent prize text.

Show a concise objective reminder after the intro and on late join. Offscreen objective pointers apply to leaders/coffins, not every regular mob.

UI deliverables: intro title/objective card, leader bar, reusable mob bar, coffin status panel, hazard charge indicator, survival timer, completion banner, offscreen objective marker and optional music credit entry.

## Pine Valley specification

### Gameplay and spawning
The threat is crowd density plus explosive enemies that are visually unmistakable. Use the latest yellow bloater with hands. Normal zombies continue as support under this event's own profile; do not stack two independent wave directors.

Proposed encounter curve: opening crowd and a clearly introduced first exploder; increasing mixed waves through the middle; final dense push without spawning unavoidable exploders on top of players. Allocate exploder counts within the same population budget as other enemies.

Exploder lifecycle: Approach -> Arm -> Detonate -> Removed. Once armed, it stops, grows visibly and displays the blast radius. Proposed countdown: 1.5 seconds; initial blast radius: 7-9 studs, tuned against movement speed and crowd space. Direction is irrelevant for a circle, but center locks to the stopped enemy. No invisible radius growth after the warning.

Proposed lethal behavior: lethal damage arms an unarmed exploder instead of immediately removing it; its health bar becomes a clear armed state, it is no longer targetable as living, and a minimum dodge warning remains. An already armed exploder cannot detonate twice. A chain-triggered neighbor receives a readable minimum warning; never instantaneously resolve an entire screen of blasts in one frame. Cap chain work per update. Mark damage ownership and award death/shards once; chain kills must use a defined attribution rule.

Blast damages nearby enemies and players within the authoritative radius, with cover/height rules aligned to existing combat. Friendly enemy damage is intentional. Damage amount, lethal-trigger choice and chain delay remain tuning decisions to validate before implementation is locked.

### Animation and effects
Idle breathing, waddling locomotion with grounded feet, hit flinch, stop/brace, visible inflation, detonation recoil/vanish, and intro performance. Use supported deform-bone motion for inflation; no untested shape-key or bone-scale dependency. Hands remain attached and clear of the belly.

Effects: yellow/amber pulse, readable floor circle, cartoon blast, brief smoke and small particles. Preserve enemy warnings over weapon VFX. Audio: gurgle, rising arming cue, pop and restrained chain variation.

### Cinematic
Proposed 3-4 seconds: low camera finds yellow bloater pushing through ordinary zombies; belly visibly swells and cheeks tense; camera widens to the crowd; title and survive objective appear. Any preview explosion is harmless. Restore control before live arming countdowns begin.

## Beach Cove specification

### Gameplay and spawning
One complete DJ crab with equipment fitted from the modeling pack. Supporting ordinary crabs and rock throwers arrive through an event schedule, maintaining pressure while leaving dodge routes.

Proposed attack rotation:
1. Beat Command: clear claw/conductor windup; selected packs rush along warned lanes. Lock direction before movement; do not home through players.
2. Rock Bombardment: supporting throwers show landing markers before visible rocks arrive. Stagger impacts rather than blanket every escape.
3. Double Claw Bass Slam: raised claws slam the ground; a clearly warned expanding ground ring has navigable gaps. Collision follows the ring front rather than damaging its entire filled interior.
4. Recovery: brief stationary/slow groove window where pushing toward the DJ is rewarded.

Start with one major hazard at a time; increase overlap only if squad play remains readable. Killing the DJ disables new coordinated attacks, completes the event and clears remaining ordinary adds through common cleanup. Headphones and speakers are attached visual parts, not separate damage targets.

### Animation and effects
Idle groove, scuttle, turn, hit flinch, beat command, claw raise/slam/follow-through/recovery, death and intro power-up. Eight walking legs plus two articulated claws; speakers remain securely fitted. No sliding shell with static legs. Sound pulses and decorative lights follow cues without hiding rush markers.

### Cinematic
Proposed 4-5 seconds: close-up on rear speakers powering up, camera arcs to eyes/pincers, claws snap on a musical accent, reveal crab reinforcements; CRAB RAVE and objective appear. Actors remain safe during presentation.

### Requested music
**User-selected track: Syn Cole — Feel Good.**

Supplied file: C:/Users/Jeremiah/Downloads/Syn Cole - Feel Good Future House NCS - Copyright Free Music.mp3
Observed local file size on October 9: 4,371,154 bytes. The filename is the supplied description, not a license verification or Roblox asset ID. The file was identified, not analyzed for exact duration/BPM/cue timings and not uploaded or copied into the repo in this pass.

Implementation:
- Keep the original file untouched. Register source, checksum, chosen usable segment, trim/loop points, Roblox sound asset ID, owning creator/group and required credit in an audio manifest once established.
- Verify applicable usage/credit terms and Roblox availability before upload; do not treat the words Copyright Free in the filename as that verification.
- Audition the actual file before selecting a musical accent. Exact start offset, BPM, beat grid and loop points are TBD; do not guess them from memory.
- Fade ordinary map music down for the intro. Start this track at a measured cue, reveal the DJ on an accent, and continue into active combat.
- Author a beat-offset table referenced to the server encounter start. Gameplay remains server-timed; music playback and visual beat pulses follow that clock. Clients do not submit attacks based on detected bass.
- If the sound is late, muted, unavailable or fails to load, keep encounter timing and warnings correct. Music is not a gameplay dependency.
- Obey the player's music volume/mute. Keep warning effects in the SFX category; no muting music should remove necessary attack cues. Limit screen shake and light flashing.
- On victory use a short fade/sting and return to map/shop music. Death, abort, reset and scene changes cancel it without duplicate tracks. Late clients seek/resume from the shared timeline.
- For a fight longer than the selected audio segment, use a measured clean loop/crossfade without a combat interruption. Do not loop an arbitrary point in the middle of a phrase.
- No audio source file is committed, uploaded or published as part of writing this specification.

## Desert Basin specification

### Gameplay and spawning
Three damageable sarcophagi replace normal perimeter spawns. They release regular skeletons and mummies at their own safe marked exits. One releases the Warden once during the intro/activation sequence. There are no repeating giant-mummy spawns.

Initial spawn-pulse proposal: 5-7 seconds per coffin, staggered between coffins. Spawn placement must keep the exit readable and avoid materializing inside players. Pending spawns are canceled immediately when their source coffin is destroyed. Already living mobs persist until killed or event completion.

Destroying a coffin permanently reduces reinforcement pressure. Killing the Warden alone does not end the wave; destroying all coffins alone does not end it. When both objectives are complete, remaining ordinary adds clear without extra kill rewards and the shop opens.

Provide deliberate automatic targeting for nearby coffins without making all weapons blindly ignore threatening mobs. Coffin obstruction, line of sight, range and targetability must work with the existing targeting interface. Do not let a visible health bar suggest damage can pass through terrain.

Proposed Warden attack: heavy stone-fist ground slam with a clear windup and recovery, plus pursuit. Keep the kit distinct from a regular mummy's hook. Do not introduce an unseen long-range hit simply because its fists are large. Its attacks and coffin spawn pulses share a fair pressure budget.

### Models, animation and effects
Complete Warden character; fitted coffin body/lid; broken replacement pieces derived from final intact geometry. Lid relief is approved. Size cavity around the actual emergence pose.

Warden: idle, heavy locomotion, hit, emergence, fist attack, recovery and death. Coffin: rise, rattle/open, pulse, damage response and destruction. Distinct left/right hand contacts if both fists slam. Sand/dust bursts are effects; airborne broken parts cannot damage players during the intro or block exits accidentally.

### Cinematic
Proposed 4-5 seconds: camera tracks sand ripples as three coffins rise; one lid falls away; Warden emerges and plants stone fists; wide view reveals all three objectives. End with DESTROY THE TOMBS AND DEFEAT THE WARDEN.

## Frozen Pass specification

### Gameplay and spawning
One alpha leads repeating werewolf packs from alternating arena approaches. Standard mixed-map spawns are replaced. Avoid releasing all packs onto a single player just because that player is nearest.

Proposed alpha kit: warned howl granting a bounded temporary buff to nearby pack members; direction-locked charge with visible lane; claw follow-through; recovery. The howl radius is shown, and empowered wolves have a subtle distinct state cue. Buff values/duration are configurable; remove them on expiry/cleanup, and do not stack repeated buffs without an explicit cap.

Charge follows server movement and ground checks; do not teleport the model along an animation-only root path or permit last-frame homing. Leave a punish window after a miss. Killing the alpha ends the event.

### Models, animation and effects
Russet alpha with charcoal mane, pale details and intact hands/feet/tail. Existing gray wolves remain support. Idle, stalk/run, howl, charge-start/loop/end, claw attack, hit and death. Foot plants and charge stops must not slide uncontrollably; mane/tail motion is secondary.

Red moon/sky tint, howl pulse, charge warning, subtle snow spray and pack sounds. Restore normal map lighting after all exit paths. Essential cues remain visible on snow and at reduced effects quality.

### Cinematic
Proposed 3-4 seconds: moon reveal, alpha silhouette on a terrain-safe rim position, howl and answering pack, camera follows the alpha into the arena, title/objective. Do not force an offscreen live charge before input returns.

## Volcanic Crater specification

### Gameplay and spawning
Fixed low vents persist during the event and activate in staggered groups. They do not randomly appear beneath players and vanish immediately. No vent health under the current design.

Proposed cycle: 1.5-second visible orange warning; 8-10 stud radius eruption; about 2 seconds active; cooldown safe period. Define damage tick interval and per-target cooldown in config; no frame-rate-dependent damage. Vent models and indicators must correspond to the same authoritative hazard center/radius.

Slime-heavy arrivals include bounded splitting; reserve child capacity before splitting and cap split generations. Supporting Goblins/Spiders use existing models. Maintain escape corridors between currently active and charging vent circles; do not cover every feasible route.

Suggested interaction: geysers hurt enemies too, allowing crowd baiting. Confirm damage attribution and once-only rewards. Cosmetic debris causes no damage, physics obstruction or persistent clutter. Finish after 60 active seconds, cancel all hazards and clear ordinary survivors through common cleanup.

### Animation and effects
Vent charge glow, eruption plume, active spray and cooling state. Existing slime movement/split animation remains the basis; inspect those animations in dense groups. Small rock fragments tumble and fade on a pooled, bounded budget. Lava jets and telegraphs should remain readable on the lava-colored map.

### Cinematic
Proposed 3-4 seconds: ground-level rumble, several vent cracks brighten, a harmless preview geyser fires, camera rises to reveal the advancing slimes; title and survival goal appear. Transition back before live warnings start.

## Cinematic system and universal boss naming

Each round-10 event needs its own short scene, not a renamed copy of the Hammer sky drop. Use a common controller for camera ownership, synchronization, interruption and cleanup, with per-event shot/cue data.

Every full boss also needs a unique themed intro. Preserve Hammer Brute's hammer-first identity; propose surfacing/claw reveal for Giant King Crab, sand/staff reveal for Pharaoh, heavy ground-strike entrance for Frost Cyclops, and shadow/descent/roar for Dragon. These shots remain proposals based on existing models and attacks.

Name Hammer Brute consistently across intro title, bar, Journal, tutorial, admin display and active documentation. Internal IDs can remain stable. October 9 source inspection still found the stale HAMMER ZOMBIE BOSS introName in MapBossDefs; implementation must fix this and the legacy BossIntro mapping rather than assuming notes changed the game.

Cinematic safety:
- Server owns intro start/end and combat suspension. Timers, spawn warnings, hazards and damage do not progress unfairly during camera takeover.
- Never let a disconnected/late client hold the server forever. Use bounded asset readiness and deterministic fallback presentation.
- Restore camera mode/subject, input, UI, lighting and music after completion, skip, death, abort, reset or error.
- Avoid taking camera during an existing level-up/shop transition. Respect reduced-motion settings; skip/repeat policy remains to be decided.
- Repeat/Endless intros may be shorter but retain unique identity and name. No client skip can bypass authoritative combat scheduling.
- Capture real multiplayer footage to verify everyone sees the same event state.

## Modeling and asset handoff

Canonical pack: [October 9 modeling pack](art-references/round-10-modeling-pack-2026-10-09/index.html).
Download: [ZIP](art-references/round-10-modeling-pack-2026-10-09.zip).
Construction notes and prompts: [modeling guide](art-references/round-10-modeling-pack-2026-10-09/MODELING-GUIDE-AND-PROMPTS.txt).

The pack contains 10 three-view sheets: yellow exploder with hands, complete fitted DJ crab, coffin assembly, Warden, alpha, vent, small volcanic debris, isolated coffin body, isolated lid and broken tomb kit. Some sheets describe components of one asset, not additional enemy types.

Do not make or fit the crab equipment as a separate downstream deliverable. Model it together with the crab; internal material/mesh sections may still be useful for rigging. Other existing normal mobs and full bosses are reused. Smoke, shockwaves, moon tint, geysers and warning circles are Studio effects, not a list of extra detailed Blender sculptures.

Retain chunky forms, softened bevels, gentle facets and matte painterly textures. Use actual gameplay-camera scale comparisons. Images are conceptual views, not calibrated blueprints; reconcile inconsistencies into one geometry. Test deformation before full animation. Validate joints, weights, normals and texture seams through fresh export/reimport and then actual Studio import.

Detailed pipeline: [Blender to Studio implementation plan](plans/2026-10-05-blender-to-studio-event-implementation.md). Stable delivery requires editable blend files, delivery meshes/textures, rig and animation metadata, contact points, imported joint receipts, retarget outputs, previews and validation results.

## Animation and combat synchronization

Use established pipeline conventions rather than inventing a second animation system. Author full anticipation, acceleration, contact/release, follow-through and recovery. Rig every complete limb; no placeholder hand stumps. Feet plant; full-body weight transfer supports each strike. Loops and transitions must not pop.

Per attack store warnStart, directionLock where applicable, impact/release, activeEnd and recoveryEnd in seconds; attach origins to actual hands, claws, mouths or terrain points. Server schedules hit logic from shared timing. Client markers and musical bass detection cannot authorize damage. Moving hit shapes require appropriate sampling; particle appearance cannot be the only authoritative hit definition.

Current pipeline uses imported rest-hierarchy receipts and retargeting; source AnimationData is not automatically the Studio payload. Do not assume animated Blender scale, shape keys or constraints survive the current rigid-transform runtime. Prove the bloater's swelling and every unusual motion in a one-asset round trip first.

## Multiplayer and integration architecture

Current local work has progressed from earlier refill-only ideas to authored arrival timelines and later multiplayer changes. Start from current WaveTimeline, EnemyScheduler and Chase source plus the latest reports. Older numeric counts in brainstorms are historical, not instructions to overwrite newer tuning.

Integrate event profiles into the existing scheduler/phase flow. Only one director owns the wave. Track boss/elite/objective reservations, scheduled adds and slime children under capacity. Preserve spawn clearance, ground validity and readable warnings. Protect objectives and leaders from ordinary population retirement. Do not queue a catch-up burst after pauses.

Test different player counts and alive-member changes without letting players heal a boss by reconnecting. Select and document one health scaling policy at activation; subsequent join/death adjustments require explicit rules. Arrival pacing can follow surviving players, but objectives must not become impossible or instantly trivial through joins/leaves.

The requested crowd feel requires sustained actual enemies reaching players, not just large scheduled totals. Measure weak/typical/strong builds and grouped/scattered squads. Do not multiply density blindly or compensate only with HP. Existing caps do not prove device capacity.

Server validates movement/targets, range, phase, cooldown, health, objectives, spawns, hits, deaths and rewards. Practice/admin fixtures never use production DataStores or award persistent progress. Enemy visual deletion cannot end the encounter. Long-term scalable architecture remains server records with client visuals; any migration is a separately validated workstream.

## Implementation work packages

1. Baseline inventory: current source, active Studio place, existing assets and latest verified multiplayer reports.
2. Shared encounter config/state machine, clear-condition logic, health replication and UI components.
3. Yellow bloater production round trip and Pine event; validate hands, inflation and chain lifecycle.
4. Coffin/Warden models, objective targeting, independent health bars and dual clear condition.
5. Complete DJ crab, coordinated attacks, Feel Good cue manifest and unique intro.
6. Alpha model/animation, howl buffs, pack timing and charge fairness.
7. Vents/slime pressure, charge UI, pooled effects and survival completion.
8. All intros, consistent Hammer Brute naming, sound/UI polish and repeat/Endless handling.
9. Full squad/device regression, source/Studio parity, delivery receipts and release review.

Studio MCP can inspect instances, execute Luau, read/edit source, inspect output and capture tests. Discover the connected place first and select roguelite 107877054949326. Local rigged FBX import may require native 3D Importer or a supported import capability discovered at implementation time; do not claim asset insertion uploads a local rig.

Build only:
`rojo build roguelite-planning/studio-prototype/combat/default.project.json -o build/RogueliteKatanaCombat.rbxlx`

Synchronize mapped combat source/templates while preserving the map and unrelated instances. Retain required capability settings and compare source hashes. Never sync the root Copy The Scene project. Keep concurrent work intact.

## Acceptance checklist

### Art and animation
- All seven new asset families delivered using latest reference choices; coffin component sheets accounted for.
- Clean soft edges, normals, texture seams, proportions and complete limbs in Blender AND Studio.
- Full required clips, usable range, planted feet, clean transitions, correct contact/timing.
- No floating DJ equipment, bending stone fists, disconnected hands, mismatched coffin lid or large debris mistaken for small particles.

### UI and cinematics
- Every damageable entity has correct health display; all three tomb bars are independent.
- Vents show charge/state, not fake health. No decorative component appears targetable.
- Correct objective/timer per event; desktop, controller and mobile-safe layout; damaged mobs remain readable in crowds.
- All five unique event intros and all five full-boss intros verified; Hammer Brute naming consistent.
- Camera/input/lighting/music restore on every exit; muted music does not remove attack cues.
- Feel Good uses the supplied recording only after actual asset/cue/credit setup; no invented BPM or asset ID.

### Gameplay
- Each event starts once and ends only on its stated condition.
- Tomb death cancels its queued spawns; Warden spawns once; both objectives required.
- Exploders detonate once; chain work bounded; reward attribution cannot duplicate.
- DJ rush/ring/bombardment and alpha charges preserve clear warnings/escape options.
- Vent damage equals shown area; slime splitting respects caps.
- No stray hazards/adds/bars/music after cleanup; no cleanup kill rewards.

### Multiplayer, performance and regression
- One through four actual clients, grouped and split parties, strong and weak builds.
- Measure alive counts, time to contact, arrivals, kills/second, cap saturation, deaths, frame time, memory, bandwidth and shard/XP income.
- Named lower-end mobile and desktop targets; reduced effects preserve warnings.
- Test 9->10->11, 19->20->Endless, tutorial intro, pause, death, revive, leave, reset, late join where supported, missing assets and aborted intro.
- Test spoofed objective damage, invalid values, duplicate/stale requests and client visual deletion.
- Record exact Git revision, place, client count, device, steps and evidence. Do not count edit-time checks as a live multiplayer test.

## Source register

| Source | What it supports |
| --- | --- |
| User conversation, October 5–9, 2026 | Event selections, appearance revisions, integrated DJ model, health/UI/animation/cinematic requirements, Hammer Brute name, song choice. |
| [Current game structure](CURRENT_GAME_STRUCTURE.md) | Game identity, round-20 progression, map ladder and existing run systems. |
| [Original consolidated encounter notes](plans/2026-10-05-wave-10-events-and-boss-intros.md) | Prior event rules, intro concepts and art feedback; numerical proposals remain provisional. |
| [Production plan](plans/2026-10-05-blender-to-studio-event-implementation.md) | Modeling, rigs, animation, retargeting, MCP boundary and validation workflow. Historical baseline observations should be rechecked. |
| [Modeling pack and full prompts](art-references/round-10-modeling-pack-2026-10-09/MODELING-GUIDE-AND-PROMPTS.txt) | Latest source images and explicit integrated-crab correction. |
| [User art direction](art-references/ART_DIRECTION_USER_2026-09-17.txt) | Chunky low-poly style, soft bevels, matte painterly surfaces and controlled palette. |
| [Map mob roster](MAP_MOB_ROSTER.md) | Existing map-specific support enemies and full bosses. |
| [Boss package spec](plans/BOSS_GAME_PACKAGE_SPEC.md) | Clip data, attack points, delivery format and validation conventions. |
| [Regular enemy delivery](mob-production/combat-ready/README.md) | Actual import receipts, coordinate conversion and Studio retargeting workflow. |
| [Enemy architecture](ENEMY_SIMULATION_ARCHITECTURE.md) | Server authority and long-term client visual separation; not proof of current migration completion. |
| [Wave timelines](studio-prototype/combat/WAVE_TIMELINES_2026-10-05.md) | Authored arrivals; later corrections within this report supersede its older tables. |
| [Multiplayer arrivals](studio-prototype/combat/MULTIPLAYER_ARRIVALS_2026-10-06.md) | Later party-scaled arrival work and stated verification limits. |
| [Boss mob pressure](studio-prototype/combat/BOSS_MOB_PRESSURE_2026-10-05.md) | Supporting-enemy pressure and protected boss/entity handling. |
| [WaveTimeline source](studio-prototype/combat/WaveTimeline.luau), [EnemyScheduler](studio-prototype/combat/EnemyScheduler.luau), [Chase](studio-prototype/RogueliteZombieChase.server.luau) | Current integration locations; inspect current revisions before changing. |
| [BossIntro](studio-prototype/combat/BossIntro.client.luau), [MapBossDefs](studio-prototype/combat/bosses/MapBossDefs.luau), [UITheme](studio-prototype/ui/UITheme.luau) | Existing camera/title/name hooks and UI design system. |
| User-supplied local MP3 path in Crab Rave section | Exact requested recording; not proof of licensing, upload, duration, BPM or musical cue analysis. |

## Outstanding decisions and verification status

Tune health/damage values, event population curves, lethal exploder behavior, chain delays, vent enemy damage, alpha buff strength, repeat/skip policy and exact audio cues through the first playable slices. The user has selected the themes, visual requirements and song; these tuning details must not be presented as independently approved facts.

This October 9 compilation inspected repo documents/source locations and confirmed the supplied MP3 exists. It changed documentation only. No song upload, Blender modeling, Roblox installation, build, Play test or publication ran.
