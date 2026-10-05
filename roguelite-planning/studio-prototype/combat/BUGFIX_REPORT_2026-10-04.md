# Squad feedback fixes — October 4, 2026

Applied to source and the open Wavebreaker Studio place **107877054949326** through Roblox Studio MCP. The existing map, imported models and unrelated instances were preserved. The root Copy The Scene project was not synced. The combat overlay builds to `build/RogueliteKatanaCombat.rbxlx`. Studio was stopped and temporary QA instances were removed afterward. These changes have **not been published to live servers**.

## Compact menus, complete effects and combat follow-through — latest feedback

- **Journal:** one compact persistent toolbar holds Weapons, Items, Collection and search capped at 280px. Desktop details place identity/actions beside descriptions/records, stacking on narrow screens. Readable stat labels sit above values. The scrolling collection uses balanced compact cards and retains position.
- **Preview menu:** a right panel, at most 348px wide, groups identity, tiers, Attacks/Weapons navigation, attack choices and playback. The stage occupies the left side; portrait uses a bottom dock. Labels are 14px, desktop descriptions/playback 16px. Menu navigation does not restart attacks.
- **Effects:** rockets use the production smoke/explosion renderer; Fart Gun uses the real travelling poison cloud and lingering smoke. Base eggs now include an illustrative hatch once per eight throws, starting on throw three; the dedicated hatch starts immediately. Gameplay probability is unchanged. Ray Gun preview uses the same impact radius and renderer as combat.
- **Scene and targets:** the chest-island copy's existing trees, shrubs, flowers and boulders frame the clear lane, with a lower three-quarter camera. Glock, Draco, Nail Gun and Magic Staff show one correctly aimed-at dummy. Crowd attacks retain groups. The original lobby stays intact.
- **Card corners:** Armory weapon info buttons are top-right; locked weapon/armor/pet/class cards use top-left locks. Starting-weapon locks also move left. Owned weapon checks and upgrade markers clear the info button.
- **Swings:** diagonal cuts start and finish on opposite sides, with lateral coverage comparable to horizontal and unchanged reach/hit timing. Pan, Katana, Bat, Shovel and Vampire Blade share the correction. Katana's horizontal visual arc is modestly narrower.
- **Ray Gun:** enemy and wall contacts splash even without a kill. Tier I–IV radii are 6/6/7/9 studs; maximum secondary damage is 60/60/65/75%, falling to one quarter of that factor at the edge. AreaSize caps at 12 studs and each contact affects at most 12 neighbors. The direct victim is excluded; pierce/bounce shares hit history and wall/server checks. Kills still disintegrate without a second blast. [Combat details](SWING_RAY_IMPACT_2026-10-04.md).

Actual Studio MCP verification, without foreground activation or desktop input:

| Check | Result |
| --- | --- |
| Journal | 1,255 data assertions; 39,038 mounted checks across eight sizes, all 42 weapons/50 items, actual TextBounds, navigation and scroll reachability |
| Preview UI | 161,610 checks across 1,008 layouts; 1,552 mounted checks over 14 presentations; 2,478 typography checks covering all 42 names |
| Preview recipes/effects | All 175 tier/variant presentations passed, at most eight movers; all 14 real-frame effect cases passed, including base rocket smoke, poison flight and base egg hatch |
| Continuous playback | 18,483 cadence/cleanup checks passed again |
| Scene | 1,336 actual-client asset, grounding, inert-state and preservation checks; Nail Gun probe confirmed one target and exact aim alignment |
| Card corners | All 42 info buttons top-right; all 39 currently locked cards top-left; existing 1,587 Armory checks passed |
| Swing geometry | 170,649 checks over nine templates, four facings, both sides, three distances and visual/server paths; comparable diagonal width with bounded reach |
| Ray impact | 452 isolated source checks for falloff, walls, misses, caps, exclusions and repeat hits; 10 Server Play physics checks recorded direct damage 100, nearby splash 45.0073, farther splash 22.5073, one impact event |

Screenshots verified the Journal collection, Molotov details and final panel typography. Background Studio omitted the 3D world from MCP captures, so this pass's island/attack appearance is functionally checked but not visually signed off. No desktop control was used to work around that limitation. Real-device frame time and four-player balance remain unmeasured.

Two Journal fixture assumptions were corrected: resize can replace cached panels, and unequal detail columns reach their final paragraphs at different scroll offsets. The diagnostic confirmed reachability; the full suite then passed. An old Edit require cache caused an initial panel-test mismatch; fresh source/fresh Play passed. Final console output contained only Studio Assistant camera-restoration notices, with no game errors.

All **16 runtime sources** match Studio. **25 runtime/test Luau files** parsed, whitespace checks passed, and the required Rojo overlay rebuilt, including RayImpact and the Godly mappings. Play is stopped and temporary fixtures are absent. Backups: `build/showcase-polish-backup-2026-10-04`. **Source/Studio only, not published live**; no persistent rewards awarded.

## Continuous attacks, scrolling Journal and spacing — previous pass

The Journal collection is now one continuous vertical list of cards. Weapons/Items tabs, search and the count footer remain fixed; there are no page buttons. Opening an entry and returning restores the collection position. Desktop, portrait and short-screen layouts use shared inner margins, a separate scrollbar gutter and a reserved footer row. Search text, card labels and bottom controls have explicit padding. The preview attack description now occupies its own row, with 24px side insets, an 8px gap below the buttons and 12px bottom clearance; the Swing popup clears the taller control panel.

Preview attacks now repeat using the production weapon cooldown and motion gate at the selected tier, with neutral class stats. The old two-shot/fixed-cycle pause and repeated take rebuild are gone. Returning throws still finish their return before firing again. Legendary prerequisites run at the same normal cadence. Vacuum targets fade back to their starting positions while suction remains active. These are presentation changes, not changes to live weapon balance. [Cadence details](../ui/WEAPON_SHOWCASE_CADENCE.md).

Verification actually run through Studio MCP, with no foreground, mouse or keyboard control:

| Check | Result |
| --- | --- |
| Journal data/layout | 1,040 pure assertions and 17,216 mounted assertions across seven sizes; all 42 weapons/50 items, bottom-row reachability, scroll restoration, filtering and measured padding |
| Preview controls | 112,402 assertions over 1,008 layouts (42 weapons × 24 viewport/inset cases), plus 1,239 mounted lifecycle assertions across seven entries |
| Continuous cadence | 18,483 assertions over 14 representative attack modes; persistent take, exact Legendary counts, bounded effects, continuous utility channels at all eight supported tiers, Loop OFF/resume |
| Actual Magic Staff playback | Seven shots during 8.5 seconds; six observed gaps from 1.3327 to 1.3343 seconds versus a nominal neutral interval of 1.3 seconds; no two-shot pause |
| Actual vacuum playback | Five seconds at tier IV, zero channel-gap frames and two sampled target-reset fades while the stream remained active |
| All previews and production effects | All 175 tier/variant presentations passed again, at most eight local movers; all 11 actual frame-driven effect cases passed again |

Studio captures verified the Journal and attack-control spacing. The occluded Studio window omitted the 3D world in these captures, so they establish UI layout only. Frame-driven checks verify active effects, not every visual frame or low-end GPU performance. The final console contained only Studio Assistant camera-restoration notices, with no game errors.

All four changed runtime modules match Studio source exactly. Eight runtime/test Luau files parsed, whitespace checks passed, and the required Rojo overlay rebuilt successfully. Play is stopped and the temporary test modules/local stage are absent from Edit. Source backups are in `build/journal-cadence-backup-2026-10-04`. Changes remain **source/Studio only, not published live**; no persistent rewards were awarded.

## Preview and Journal redesign — previous pass

This supersedes the first showcase's Pine Valley thumbnail, substitute figures, scrolling selector and Journal table below.

- **Actual game assets:** the preview now uses the current player's real avatar and the lobby's real textured practice dummies on a local copy of the actual chest island. Chests, reward/pedestal stations and small lane obstructions are removed only from that copy. The source lobby stays intact. Targets are arranged for each attack, and the camera fits the weapon, avatar, targets and effect space.
- **Clear controls:** four I–IV segments, Base Attack, named specials, optional Swing choices, Replay and Loop. A small paged weapon strip replaces the left sidebar. Controls respect the Roblox topbar and phone cutouts without hiding CoreGui. Closing restores the previous HUD, prompts and camera ownership.
- **Production VFX:** fire, water, suction and ground zones now use their normal game renderers through isolated local adapters. Fixed missing charge auras caused by the preview camera exceeding gameplay's distance cull, hidden card faces on repeated volleys, inactive targets in boomerang routes, ungrounded special impact origins and water contact feedback. Eggs show the same articulated chicken fallback used in combat. Royal Flush/Strike keep the capped text rules from the previous fix.
- **Journal:** fixed Weapons/Items tabs and search, paged collection cards, one focused entry, selected-tier stat cards and Watch Attacks. Item effects list exact supported weapon names and explain conditions. Player-wide benefits such as Chicken Soup say so directly; no wall of every weapon icon. Mixed items separate their universal and conditional effects. Named Antlers compatibility is visible on the first desktop detail screen.

Verification actually run in Studio:

| Check | Result |
| --- | --- |
| Real scene/assets/avatar | 74 detached checks; 1,300 actual-client checks, including preservation, grounding and inert state over real frames |
| Responsive browser | 88,984 assertions over 882 layouts: 42 weapons × 21 viewport/inset combinations |
| Mounted browser and cleanup | 1,190 checks across seven entries, including tier/variant fallback and actual safe-area bounds |
| All weapon recipes | 1,142 data assertions; all 175 tier/attack presentations passed camera, instance, timeline and cleanup checks; at most eight scheduled local movers |
| Actual frame-driven effects | All 11 cases passed: vacuum, water, fire, Royal Flush, Strike, hatch, bow rain, twin daggers, wraith, trident wave and ray burst; active emitters/headlines were verified |
| Resting weapon/dummy overlap | Zero overlaps in 997 oriented mesh-bound pairs covering all 42 weapons at all four tiers |
| Headline framing | Royal Flush and Strike remained readable and capped in seven representative desktop/phone camera fits |
| Journal data/layout | 3,109 compatibility/data checks for all 50 items; 1,461 mounted checks across seven sizes, including visible named Antlers support |

Screenshot review confirmed the actual avatar/dummies/chest-island artwork, clearer browser and paged Journal/compatibility screens. Subsequent work respected the user's request to stop foreground/mouse control and used source plus Studio MCP. Occluded Studio captures can omit the 3D world, so blank captures were not counted as visual verification. Automated frame checks establish that effects execute; they do not establish low-end GPU performance or replace visual review of every attack frame.

Initial fixtures exposed engine-regenerated avatar joints and torso collisions after parenting; the scene now normalizes both while preserving clothing. Other fixture-only corrections used the actual authored pin/dagger names and tested the headline's text constraint rather than its padded container height. The final Play console was empty.

Final integration: all **11 runtime sources in this redesign manifest matched Studio exactly**, all **17 related runtime/test Luau sources parsed and verified**, whitespace checks passed, and the required Rojo build succeeded. The earlier combined pass audited 53 runtime sources. Play is stopped, temporary fixtures are absent from Edit, and backups are in `build/showcase-redesign-backup-2026-10-04`. No live publication or persistent rewards occurred. Four-client networking, other avatar proportions and low-end/mobile frame time still need real-device testing. [Implementation and scene details](../ui/WEAPON_SHOWCASE.md).

## Attack text and private targeting follow-up

Royal Flush and Strike now share viewport-, field-of-view- and distance-aware text sizing for every viewer. The previous fixed-pixel labels opened with a **2.1×** scale tween; distant teammates still saw that large screen-space label. The pop now happens inside the size calculation, before a screen-size cap, with proportional outlines and a 140-stud visibility limit. There is no child UIScale that can exceed the cap. Both the regular combat listener and the Armory showcase use this renderer.

Owl mark crosshairs now require the viewing player's UserId to match the pet owner. Mjolnir's pre-strike target ring uses the same ownership rule. Shared pet animations, lightning impacts and enemy danger warnings remain visible. The isolated weapon showcase explicitly permits its scripted target ring. Damage, target selection, server validation and saved data are unchanged.

Verification actually run through Roblox Studio MCP:

- **36,785 pure assertions** across five viewports (including portrait phone and 4K), three FOVs, six distances, both headline sizes and 51 animation samples: no pop exceeds the cap, distance never increases text size, and behind-camera/distant text is culled.
- **Actual single-client Play with real RemoteEvents and production effect listeners:** one own Owl crosshair, zero foreign crosshairs; one own Mjolnir targeting ring, zero foreign targeting rings; the foreign lightning impact still rendered. Royal Flush and Strike had zero cap violations across 38 sampled label frames, with maximum constraints of 34 and 42 pixels at the tested camera. Both expired cleanly. The own crosshair also expired, and the isolated preview retained its target ring.
- An initial fixture omitted dummy Humanoids, so the existing dead/invalid-target cleanup correctly removed the own crosshair. Adding live Humanoids to the test targets produced the passing fresh Play run above; gameplay code was not changed for that fixture issue. The final console was empty.
- All **three affected runtime sources** matched Studio exactly; the new policy inherited the existing combat module's sandbox/capabilities. Four Luau files parsed, the required Rojo overlay rebuilt successfully, and stopping Play removed all temporary fixtures. Backups are in `build/presentation-backup-2026-10-04`.

This checks owner/foreign event payloads on one real client, not a four-client network session. Changes remain **source/Studio only, not published live**.

## Armory, showcase and combat follow-up

The second feedback pass adds a weapon showcase and collection journal, makes Armory the main loadout entry, and corrects the remaining vacuum, bowling and egg behavior. This section supersedes the first pass's bowling speed and vacuum description below. These changes are still **Studio/source only, not published**.

| Area | Current behavior |
| --- | --- |
| Vacuum | A tapering suction funnel replaces the straight fan lines. Three incomplete curved rings spin and travel toward the nozzle, with twelve inward-moving motes. Its nine curved beams and motes are pooled, with at most twelve live funnels. Damage and pull remain server-owned. |
| Bowling | Base speed is now **28 studs/s**, down from the first pass's 46, with 36-stud travel. Floor probes reject every Humanoid rig, including untagged practice dummies. Server collision and client rolling use the same real mesh radius and pivot offset; the ball no longer treats a head as the floor. Small terrain steps are allowed, cliffs/walls terminate it. |
| Eggs | The imported chicken template was missing. A self-contained articulated cream chicken is now used when that asset is unavailable; the imported asset still takes priority. Chance remains **1 in 8** per landing at every tier, life **8 seconds**, at most **3 per player / 24 total**. Chickens chase at 22 studs/s and peck for 40% weapon damage every 0.7 seconds. Landing is consumed once even if a hatch fails. |
| Class picker | Owned and locked starter weapons share one consistent grid, including the Brawler's Pan. The old separate sparse owned row caused its odd placement. |
| Armory | Classes, Weapons, Armor and Pets share the main screen. All 42 weapons can be browsed, including locked ones. Floating starter weapons use real model bounds and avatar clearance rather than fixed oversized shoulder offsets. The same info card used by chests shows descriptions and Tier IV moves, with collection context instead of chest drop odds. |
| Navigation | The redundant bottom Loadout button is now **Journal**. Armory's Classes tab is the main class/loadout entry; old loadout shortcuts still route there. Queueing still brings up the class/starter screen to reconfirm. |
| Weapon showcase | **WATCH ATTACKS** in Armory and Journal opens an automated Pine Valley presentation. Browse all 42 weapons, tiers I-IV, base attacks and specific alternate/special attacks: Royal Flush, Strike, swing variants, chicken hatch, Mjolnir/Trident throws and Godly effects. Replay/autoplay controls are view-only. Actual weapon templates, combat motion helpers and production legendary/Godly effect handlers are reused. Closing/switching clears owned jobs and geometry; queue entry dismisses it so ready-up cannot be covered. See [showcase implementation](../ui/WEAPON_SHOWCASE.md). |
| Journal | A searchable weapon/item encyclopedia with all **42 weapons and 50 passive items**. Weapon entries show lifetime actual damage and kills, tiers, descriptions and special moves. Items show exact effects, compatible weapons and purchase counts. Compatibility uses the same policy as the shop. Counters start with this version; historic kills cannot be reconstructed. |
| Journal integrity | Hits and purchases are recorded by server-confirmed hooks into the existing saved profile. Overkill, repeated dead-target hits, practice/showcase targets and admin test runs do not inflate totals. Journal updates are batched instead of replicated on every hit. Studio remains in-memory only. Existing in-run per-copy shop damage/kill counters are retained separately. |
| Queue handoff | Every member independently confirms after map selection. Two additional missed-prompt cases were fixed: a recent failed Start cannot suppress a subsequent party prompt, and joining before LobbyUI finishes loading still opens the current selection. |

Readiness rules remain: every member must qualify for the selected map and difficulty; no host force-start or timeout fallback. All-ready begins a **3-second** countdown for full/private groups, **10 seconds** for a partially filled open portal. A late join, Unready, or loadout change cancels that countdown. Changing class, weapon, armor or pet requires withdrawing readiness. Server validation repeats at launch and on match arrival.

### Follow-up verification actually run

- Studio Edit: grounded weapon/funnel/chicken rig tests **140**; committed projectile and exactly-once landing tests **1,714**. The exception regression verifies that failed optional hatch work cannot retry the same egg every heartbeat.
- Journal clean/migration/compatibility tests: **1,937** checks. Actual single-client Play with server damage/profile hooks: **10** checks, including 100 HP of actual damage plus one kill after an overkill, practice/admin exclusion and in-memory profile save. Weapon and item journal pages were visually reviewed.
- Actual single-client UI Play: Armory **1,587** assertions; class/starter picker **60** profile/resolution combinations. The Armory background initially appeared blank in MCP captures while Studio was occluded; activating Studio restored the 3D world without any game code change.
- Showcase data: **1,142** checks over all 42 weapons. Client stage cycling: **175** tier/variant presentations, zero errors, maximum ten concurrent authored movers during the fast-step harness, and successful repeated cleanup. These are functional checks, not a low-end FPS benchmark.
- Actual production combat factories in a temporary three-lane Play fixture: bowling released above an untagged dummy stayed at the mesh radius plus 0.06 studs of floor clearance; **27** bowling hits and **274** vacuum hits were recorded. Forced QA hatch rolls produced the fallback chickens: **34** hatches, **185** pecks, **5.19 studs** of observed walking and a peak of **3** active chickens. Hatch probability was forced only inside this isolated fixture; gameplay remains 1 in 8. A sample at 52 seconds had one late hatch still alive; the fixture cleaned at 55 seconds, so this run does not independently prove the final natural-expiry count.
- Fresh normal server Script in Play: weapon balance regression **1,768** assertions passed. An earlier Edit invocation encountered stale required-module cache values; the fresh Play invocation used the integrated runtime sources.
- The first fallback hatch run exposed a restricted Humanoid nameplate-property write. That write was removed, no capabilities were broadened, and the rerun's console was empty.

Final integration: **53 runtime sources matched Studio exactly**, all **75 changed/new Luau files parsed**, whitespace checks passed, and the required Rojo build succeeded. The final showcase pass repeated all **175** presentations with camera projection checks and no errors. Screenshots verified the authored Pine Valley backdrop, visible weapon/targets, inward vacuum rings and selected-weapon scrolling. The two foreground trees and obstructing log are removed only from the local showcase clone. A queue-entry lifecycle check restored the HUD and ProximityPromptService, reported zero preview connections, and left no showcase stage. Studio Play was stopped and the temporary Play fixtures were discarded. Four actual clients, live teleports/purchase receipts, all terrain variants and low-end/mobile frame time still need testing. No persistent rewards were awarded by the temporary fixtures.

## Fixed behavior from the first pass

| Report | Applied correction |
| --- | --- |
| Shop cannot select items/weapons or combine | `ShopUI.drawRoster` required unsandboxed `StoreFX` from a sandboxed render. A ready portrait threw before inventory detail controls were built. The roster now uses the sandbox-safe `UITheme.check`. Actual clicks on weapons, Combine and items were tested. |
| Who is ready; cannot unready | Named player portraits and checks reflect server readiness. Explicit Unready can withdraw immediately even from a stale UI snapshot; repeated no-op requests do not republish or bypass throttling. |
| Host force-starts; party skips class selection; locked difficulty admits members | Every queued player must confirm a valid owned loadout. No ready timeout fallback. Unready/new members cancel countdown. Every party member must qualify before the whole party launches. See [queue details](../lobby/READY_UP_FIXES_2026-10-04.md). |
| Starter returns to Frying Pan | Clicking the already-selected class preserves its chosen starter. The server acknowledges and saves a validated loadout; picks during profile loading are rejected rather than silently lost. An open class screen refreshes when loading completes. |
| Dead player stuck in upgrade/shop | Wave-clear revival is independent of reward settlement. The shop waits for all members' bodies to return. Respawns run from the owning server script, with duplicate guards and cleanup, preserving banked upgrades/builds. A cleared wave cancels the old last-stand timer. Failed paid revives do not count as successful. |
| Daily quests stay expanded | Tracker collapses when all listed daily quests are complete, retaining a claim action; new unfinished quests expand it again. |
| Green tier check drifts | Current-tier check follows the title layout instead of fixed text coordinates. |
| Reward claims unclear; unlocks buried | Unlock achievements appear first. Reward effects show separate chest copies and exact chest/emerald quantities. |
| Paid reroll unclear | Shop and level-up paid/token rerolls have explicit confirmation, with consumption explained before submission. Server receipts remain authoritative. |
| Chicken Soup/cushion and other generic art | Seven distinct transparent item icons were generated, uploaded and mapped without changing IDs or effects. Soup is a bowl, cushion is upholstered fabric. [Assets and exact prompts](../ui/assets/passives-2026-10-04/asset-ids.json). Built-in imagegen was used. |
| Melee/Explosive mistaken for classes | Item/weapon attack tags are labeled separately from the six selectable classes. |
| Weapon performance in inventory | Server-owned damage/kills per weapon copy, batched at 4 Hz. Shop snapshots flush totals; combining adds both copies, selling/reset clears them, and delayed damage cannot credit a replacement copy. |
| Crystals stop appearing | At the ground cap, value was invisibly added to old distant piles. A capped marker now moves to the latest death, its spatial index follows, value is conserved, and rapid kills cannot restart pickup immunity. Cap is 96 with bounded client visuals. |
| Four crystal colors | Existing blue/orange/pink/yellow ownership colors were verified by runtime tests. No duplicate color system added. |
| Rockets wipe distant crowds; Kusarigama too strong | Shorter/slower rockets with smaller explosions; modest Kusarigama damage/cadence reduction. |
| Bowling floats, stops early, too slow/short | Ground-following rolling lane, faster/farther travel, bounded diminishing passthrough damage, and no early pierce-budget pop. |
| Pandora/pins/Molotov miss or steer unnaturally | Faster lower arcs retain authoritative aim prediction before launch. Pandora, ordinary throws and straight projectiles (including Medusa) keep their committed paths when targets move, die or disappear. Removed client slot-offset easing that bent pins visually. Actual contact ricochets, returning weapons and magical cards retain their intended behavior. |
| Vacuum bugs/VFX; duck fire; extended yo-yo | Single-owner vacuum pull prevents opposing velocity writes; smoother visible suction and continuous flame emitter; cancellation/timeouts retract yo-yo visuals. |
| Card projectile overload | Bounded detailed/simple card visuals, distant teammate culling, and nearby-only projectile traffic. Damage remains authoritative. |
| Turrets spawn airborne or at bad corners | Ground-validated interior placement independent of player jump height; failed probes defer placement instead of using airborne feet. |
| Multiplayer crowds too sparse; bosses melt; wave 10; small Hammer AOE | Faster distributed swarm refill; population factors 1/1.9/2.7/3.4 capped at 100; boss HP +1.35 per additional player; wave-10 midboss; larger Hammer attacks with warnings. |
| Paint Roller should slow | Applies 30% slow for two seconds through the existing server status path. |
| Medusa/slow frost visual errors found during Play | Sandboxed hit feedback could not read `Humanoid.HipHeight`. Frost effects now use briefly cached floor raycasts, excluding enemies and players, without requiring that capability. |

Combat numbers and implementation details: [combat corrections](PLAYTEST_COMBAT_FIXES_2026-10-04.md).

## Verification actually run

**Studio Edit:** queue state **37** checks; mixed-progress/loadout validation **17**; enemy scheduler **187,201**; bullet-flight lifecycle **21**; turret placement **2,222**; weapon balance **1,768**; committed projectile paths **1,709**. The last harness runs real production flight/render modules with isolated clocks/worlds to check target movement/death/removal, aim prediction, full straight-shot range, and matching client/server paths. Fresh source compiled before application. Local StyLua parsed **54** changed/new Luau sources, whitespace checks passed, and the required Rojo overlay build succeeded.

**Actual single-client Studio Play:**

- UI regression: **25** checks at 1600×850, 1024×640 and 750×311. Includes the previously crashing ready portrait, usable combine/details, damage/kills, Unready label, daily collapse, and two Silver Chests plus 100 emeralds receipt.
- Normal server Script regression: **1,342 shop assertions** on the final rerun, including immediate/stale Unready and no-op replay throttling; **50 crystal assertions**, including cap value conservation, moved-pile indexing, pickup eligibility and four colors. The shop fixture requires an alive, joined run member; initial reruns in the lobby correctly rejected economy requests before that setup was supplied.
- Mounted lobby class screen: client-local `ProfileLoaded=false` disabled Confirm; restoring `true` refreshed the already-open screen and enabled it without reopening or sending remotes.
- Actual Roblox MCP mouse clicks: opened a weapon, clicked Combine, then opened Chicken Soup. Server result: two Tier I Glocks became one Tier II; damage 1234 + 56 = **1290**, kills 12 + 3 = **15**, consumed slot empty/reset. Soup's dedicated image and unchanged +6 HP/+15% recovery rendered correctly.
- Death/intermission regression: **9 checks**, full health, weapon preserved, two banked level-ups/four choices preserved, no stuck down/return flags, and still in the run **11 seconds after revival** (past the old last-stand timeout). The test source is [IntermissionReviveTests.server.luau](IntermissionReviveTests.server.luau); it is excluded from production packaging.
- Wave 10 actually spawned a Hammer midboss at **6,300 HP**, `Midboss=true`, damage multiplier **0.75** in the solo Normal test.
- Six-weapon combat smoke with a 75-enemy override: Bowling Ball, Yo-Yo, Pandora, Rubber Duck, Vacuum and Deck of Cards all registered damage and kills over 16 seconds. Player remained an active run member; 56 enemies were alive at the sample. This verifies execution, not final balance or frame-rate targets.
- Committed-throw Play smoke: 18 Pandora launches produced **zero Redirect events**; 27 Pin launches were observed. The run revealed the frost `HipHeight` capability error above. After fixing it, a fresh 18-second Play run registered damage/kills from Pins, Pandora and Medusa, rendered frost patches, retained run membership, and had an **empty console**.
- Direct MCP `require` attempts earlier hit plugin-capability errors in the test harness; rerunning through ordinary server Scripts passed. No claim is made that those failed harness attempts were gameplay failures.

Studio profiles, gift stores and leaderboard stores are now always in memory, even if an old place carries `EnableStudioDataStores=true`. Test actions used no production DataStores or persistent rewards.

## Limits and suggestions

Four real clients, network latency, published teleports, real purchase receipts, low-end/mobile frame time, every map's terrain and final boss time-to-kill were **not** tested. Combat tuning still needs a squad playthrough.

“Cursed items,” “raid / clanker raid,” and “Herbalist plant class” are feature suggestions with no defined mechanics in this report; they were not invented or presented as completed bug fixes. Concrete Masonry Unit already corresponds to Cinder Block. Couch Cushion remains its specified +1 armor/+6 HP passive, now with correct art. The vague “takes too long” note did not identify a particular duration; combat's existing 40-second wave and shop timeout were retained while ready-state failures were fixed.
