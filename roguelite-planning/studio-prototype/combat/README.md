October 6: [Admin difficulty tabs](ADMIN_DIFFICULTY_2026-10-06.md) are available in both Mobs and Waves, synchronized and verified with actual Hard/Nightmare spawns. [Multiplayer pressure and results cursor](COOP_AND_CURSOR_2026-10-06.md) are also applied to Studio. Linear party arrivals/boss HP, scaled arrival throughput and scoped results input; automated and single-client checks passed, real multi-client balance unmeasured.

Mobile/low-spec pass: [adaptive quality, phone settings and exact test coverage](MOBILE_PERFORMANCE_2026-10-05.md). Nine runtime sources synchronized; overlay built. Real-device frame time remains unverified.

October 5 combat feedback: [straight gunfire, reward receipts, swarm density, enemy scaling and white hit flashes](COMBAT_FEEDBACK_2026-10-05.md). Latest follow-up: [approachable Normal, actual crowd steering and Hammer pursuit](NORMAL_CROWD_INTEGRATION_2026-10-05.md). Source is synchronized to Studio; targeted combat Play checks and the required overlay build passed. Full-run balance remains unverified.

October 4 squad feedback: [applied fixes and actual Studio test results](BUGFIX_REPORT_2026-10-04.md). That report records synchronization of the October 4 version; multiplayer limits are recorded there.

# Six-slot weapon practice

October 4 squad feedback corrections: [combat fixes and exact verification](PLAYTEST_COMBAT_FIXES_2026-10-04.md). This supersedes older tuning/placement notes below for rockets, bowling, thrown accuracy, vacuum, duck fire, cards, turret grounding, wave-10 bosses and multiplayer density. Verification includes Studio Edit regressions and the later 55-second single-client bowling/vacuum/chicken Play fixture; four-player balance remains unmeasured.

October 3 play-test round (commits c9e5cde..a1a1f7a; syntax-checked, synced to Studio 2026-10-03 without ee48545, see `../ui/README.md`; not play-tested):
- [Melee vs ranged](WEAPON_BALANCE.md#melee-vs-ranged-2026-10-03): ranged range about −20–25% and cooldown about +12%, melee reach +15–25%, Medusa's Head slows 35% for 2 s, a wider weapon ring.
- [Melee from a jump and after a dash](HIT_FAIRNESS.md#round-4-melee-from-a-jump-and-the-dash-2026-10-03): melee reach is flat within one full jump above or below.
- [Melee dash and turrets](CHARACTER_STATS.md#class-abilities-2026-10-03): Q / gamepad X / DASH; turrets (shop items since 2026-10-04, placed for you each wave) have their own page, [HANDYMAN_TURRET.md](HANDYMAN_TURRET.md).
- [Run shop](SHOP_GAMEPLAY_READINESS.md): every non-Godly weapon offered, "Works with" lines, 7 new player-buff items (44 in all), and the Brotato crystal bag ([SHARD_CURRENCY.md](../../SHARD_CURRENCY.md)).
- Bigger waves that scale with players, in swarms: [REGULAR_ENEMY_READINESS.md](REGULAR_ENEMY_READINESS.md).
- Players no longer collide with each other (`MobCollision`: `RoguelitePlayers` vs itself off), so teammates can't stack into a tower.

October 3 hit fairness: [enemy hits judged from the player's screen](HIT_FAIRNESS.md). The server saw players 220 ms late and players saw enemies 200 ms late, so hits landed after dodges.

September 23 accuracy and utility update: [predictive throws, close melee, vacuum and water streams](TRAVEL_ACCURACY.md).


September 22 zombie expansion: [baby and mutant integration status](ZOMBIE_VARIANTS.md). Movement, stats, hunched poses and server-timed slam code are synchronized; new mesh imports and actual Play validation remain pending.

Current implementation: [LOADOUT.md](LOADOUT.md). Studio now has a live all-weapons inventory, six server-owned slots, and independent auto-targeting. The katana-only notes below record earlier prototype behavior and are not the current six-slot motion implementation.

September 22 update: [curved cards, Pandora mortar, slower zombies and the stationary practice target](CURVED_ATTACKS.md).

# Katana combat prototype

Installed in the roguelite place, 107877054949326. This is independent of the root CopyTheScene game.

## Test

Play in Studio. The katana floats blade-up on the avatar's right and automatically slashes reachable zombies. No weapon is held by the avatar. Existing player movement and zombie chase speed are preserved.

- **Z / Zombies button:** remove the current active wave; re-enable to spawn five fresh zombies. The static reference zombie stays.
- **K / Katana button:** hide/show the weapon and disable/enable its attacks for that player.
- Normal zombies now have 40 health (reduced from the original 100). Initial katana tuning is 25 damage every 0.58 seconds, with 0.10s windup, 0.10s strike, and 0.18s recovery. Each zombie can be damaged once per swing; a slash may hit multiple enemies.
- Killed zombies disappear after 0.65s and are replaced after 3s while zombies remain enabled. Toggle generations prevent old respawn tasks from adding extra enemies.
- Each server-confirmed hit creates a rising damage number displaying actual health lost, a brief hit flash, and a short blade trail during the strike.

These controls are Studio-only. Published-game clients cannot use the test remote. They do not award currency, wins, or persistence. Zombie attacks against the player have not been added in this slice; this implements damage *to* zombies.

## Geometry and targeting

The combat template is cloned from the user's adjusted `Workspace.RogueliteWeaponShowcase_PlaySize.03_Katana`, preserving its mesh dimensions (4.41010 × 4.47601 × 0.84931 studs). Only the combat copy's orientation and pivot are normalized. Native FBX coordinates mirror Blender X; rotate +0.97 radians around Studio Z and use the measured grip position. The blade points along combat-local +Y, with a further user-requested 180-degree facing flip around Y. `katana-geometry.json` records measured normalized bounds from the source vertices; `measure_katana.py` regenerates them.

Each weapon has a fixed idle slot following avatar orientation, with small vertical bobbing and no circulating/orbit motion. The right slot is the grip anchor during attacks as well as idle. The katana turns and slashes directly at its target from that slot. It does not traverse the body perimeter or switch sides to prepare an attack. Only the minimum outward clearance correction is allowed. A capsule enclosing the entire curved mesh is kept outside an avatar clearance cylinder, including character parts/accessories. The weapon aims from its slot, with a minimal outward correction if needed for avatar clearance. The blade hit box excludes the grip. Sudden turns/teleports clear the trail to prevent a visual ribbon through the avatar.

`KatanaMotion.luau` is shared by server and client. Server-owned timing and hit volumes calculate damage; clients cannot submit targets or damage values. Attack samples are substepped to 120 Hz between server frames. Obstacle raycasts block hits through world geometry. Clients render poses and feedback. Independently animated or oversized avatars still need visual review; clearance can make a large avatar's weapon sit farther out.

## Source and installation

- `InstallKatana.luau`: edit-time template, remotes, and state container setup; rejects duplicate installation.
- `KatanaMotion.luau` → `ReplicatedStorage.RogueliteCombat.KatanaMotion`.
- `RogueliteCombat.server.luau` → `ServerScriptService.RogueliteCombat`.
- `RogueliteCombat.client.luau` → `StarterPlayer.StarterPlayerScripts.RogueliteCombat`.
- `../RogueliteZombieChase.server.luau` → existing `ServerScriptService.RogueliteZombieChase`.

Studio installation uses sandboxed scripts with only runtime capabilities needed for this feature. The math module has Basic + RunServerScript + RunClientScript. Combat scripts additionally use CreateInstances, AccessOutsideWrite, Players, Physics, Animation, UI, Input, Environment, RemoteEvent, Logging, and AvatarBehavior. The two RemoteEvents are sandboxed with Basic + RemoteEvent. No asset loading, network, DataStore, or purchase APIs are needed. This matches Roblox's script capability requirements: https://create.roblox.com/docs/scripting/capabilities

After a Rojo install, `ServerScriptService.ServerRole` (from `../lobby/ServerRole.luau`) needs `Sandboxed = true` and `ShopService`'s Capabilities, because the sandboxed `RogueliteCombat` server script requires it. Rojo cannot set either. `ReplicatedStorage.RogueliteCombat.MapConfig` also needs `Sandboxed = true` with `CharacterStats`' Capabilities, because the sandboxed `ServerRole` requires it. `ReplicatedStorage.RogueliteCombat.AdminConfig` needs the same (`Sandboxed = true`, `CharacterStats`' Capabilities), because the sandboxed `CharacterService`, `ShopService` and `RogueliteCombat` scripts require it.

Rojo packaging check: `rojo build roguelite-planning/studio-prototype/combat/default.project.json -o build/RogueliteKatanaCombat.rbxlx`. This packages code, not the existing world/template. The live Studio scripts are updated directly from these files to preserve unrelated work and the user's display edits.

## Validation

- Shared motion tests passed 9,435 poses across all aim angles and three avatar radii; minimum full-weapon clearance 0.2999988 studs, within numerical tolerance of 0.3. Idle horizontal slot remained fixed.
- Actual Studio Play: blade-up idle verified visually after correcting native axes; server hits reduced zombie health; client created damage popups displaying `25`; deaths and replacement spawns observed.
- Actual Z/K keyboard controls verified: zombies off removed all active enemies, re-enable spawned five, weapon off hid its mesh and stopped damage, then combat resumed when enabled.
- Malformed and unknown test requests rejected without changing weapon state.
- The functional test before the final four-direction refinement had no console errors. Packaging checks passed for the combat project and root project.
- Multiple real clients, high-latency conditions, and published-game validation remain untested. No claim of finished multiplayer combat or final balance.

Final four-direction test (fresh isolated wave): front, back, left, and right targets at 4.5 studs each received exactly 75 damage over a 2.4-second test (three 25-damage hits). Fresh runtime motion tests again passed all 9,435 poses after the attack repositioning change. Final console check contained no errors.


Latest correction: a rear target is attacked directly from the right-side slot; no front-of-avatar detour and no move to the left side. This supersedes the earlier attack-repositioning arc.

Direct-swing regression check: rear target received 75 damage in 2.4 seconds in Studio Play. Updated motion tests passed all 9,435 poses and specifically confirmed the rear swing stays on the right side and never detours in front. Earlier four-direction test results describe the superseded repositioning version.


## Mirrored outward slash refinement

The reference arrows define front/left cuts as right-to-left across the front and rear cuts as the mirrored stroke behind the avatar. The windup tips outward, the active cut stays horizontal, and the grip extends toward the target hemisphere. Recovery raises the blade before retracting the grip. The katana stays attached to its right-side combat slot with outward clearance corrections, never taking an orbit to the opposite side.

Fresh-module verification: 9,435 sampled poses passed with minimum clearance 0.2999988 studs; additional checks confirm outward windup, horizontal strike, fixed idle slot, and no rear-to-front detour. Live Play test at 4.5 studs: front 75, rear 100, right 100 damage over 2.4 seconds each. A directly opposite left target received zero: the current right-slot blade cannot reach that target safely across the avatar. These results supersede prior swing-version tests. Left-side reach still requires tuning; do not treat all-direction target acquisition as guaranteed all-direction hit coverage.

Blender comparison scene and rendered preview are in `blender-slash-preview/`. This is a motion study using the actual weapon mesh, not an imported Roblox animation.



## RPG muzzle rendering correction — 2026-09-17

The reviewed launcher mesh now uses `RenderFidelity.Precise` in the combat template and both showcase source models. Automatic LOD was suspected of simplifying the recessed bore, but a controlled comparison has not established it as the cause. Precise on the RPG is a provisional workaround, not a confirmed diagnosis. `FixRocketMuzzle.luau` reapplies the edit-time correction idempotently, and `InstallLoadout.luau` preserves it when rebuilding templates. Mesh 79978356738826, texture 110911562405378, model scale, weapon size and pose are unchanged. A close front view in Studio confirmed the dark recessed interior with precise geometry.


## Weapon render policy — 2026-09-18

Automatic is the default for all weapons and the flying rocket. The W11_Rocket_Launcher mesh alone retains a provisional Precise exception pending a controlled camera/distance comparison. The user rejected a blanket all-Precise change. FixWeaponRendering.luau now restores this targeted policy and InstallLoadout preserves it. No texture, mesh size, pivot or asset ID changes are required.

Read-only audit: 36 live weapon templates / 43 mesh parts had no missing mesh/texture references, exact duplicate overlapping parts, unexpected scripts/constraints, or active collision/query/touch physics. Fresh inspection of 45 GLB exports (including separate components) found UVs, finite geometry, and no exact duplicate or degenerate triangles. Highest export count was 4,068 triangles. This does not rule out near-coplanar intersections or prove movement is artifact-free on every device. See weapon-geometry-audit.json.

## Player damage numbers — 2026-09-22

Live Studio correction: PlayerDamaged must be sandboxed, with Basic/RemoteEvent capabilities, because the combat scripts are sandboxed. The original unsandboxed event threw after health was deducted. Updated the open roguelite Edit data model, runtime creation fallback, and Rojo event declaration. Actual client practice damage reduced health from 125 to 111.57895 and created a red `13` popup. Actual zombie contact subsequently delivered 6.710526 damage and a red `7` popup (RGB 235/72/72). Console output was empty after these checks. Play was stopped afterward; no test state persists. Multi-client behavior remains untested. These checks supersede the earlier forced-event-only verification and pending visual-play-loop note below.

Server-confirmed contact damage now sends the damaged player the actual health lost after armor, blocking, dodging, force fields, and health clamping. That client displays the amount above their avatar in red using the same rise, pop, and fade treatment as the white numbers shown for damage dealt to mobs. Other clients do not receive the private feedback event, and clients cannot submit damage values. Studio practice damage uses the same authoritative contact path. Visual appearance in the actual client play loop still requires Studio verification.


## Diagonal slash and thrust � 2026-09-22

`WeaponMotion.MeleeStyles` now assigns Katana (`03`) a target-relative upper-right to lower-left cut, Boxing Gloves (`19`) a forward punch, and Excalibur (`32`) a forward stab. Unlisted melee weapons retain their horizontal sweep; chain weapons retain their specialized motion. The existing imported glove pair moves together, rather than alternating individual fists. No animation asset upload is required.

Thrusts pull back for 0.06 animation seconds, extend to 0.20, remain active through 0.26, and recover by 0.58. Server overlap sampling starts after the pullback. Diagonal vertical travel is bounded separately from reach. Motion is shared with the server hit boxes; existing range, wall rejection, per-attack hit deduplication, and remote validation remain in effect. Style assignments can be changed in the shared table without modifying hit-detection code.

Validation in the open roguelite Studio place: fresh-module `MeleeMotionTests` passed 20,032 checks covering four headings, diagonal direction, straight thrust extension, inactive pullback, horizontal preservation, finite poses, recovery continuity and exact idle return. Existing `WeaponFollowTests` passed 834 checks at 20/30/60/144 FPS. Both combat and root Rojo packaging passed.

Actual single-client Play: equipped each weapon through the existing client remote, at the stationary practice target four studs ahead. Katana, gloves and Excalibur each registered four additional server-confirmed hits in a 2.5-second observation. Practice damage reflects current practice tuning, not a new balance change. Client pose samples confirmed descending right-to-left katana travel and constant lateral/vertical position during glove extension. Screenshots inspected in the actual client. Invalid slot and unknown weapon requests left the equipped katana unchanged. Console had no gameplay errors (one tool-generated camera-reset notice). Play stopped after testing; temporary camera, UI and player positioning changes were discarded. Source and Edit-mode WeaponMotion are synchronized.

Multiple real clients, latency, moving-target coverage, every range bonus and all avatar sizes remain untested. No persistent rewards or published DataStore tests were involved.


September 23 weapon behavior pass: [motion, modeled throws, returning weapons, fire/poison and validation](WEAPON_BEHAVIOR_PASS.md). This supersedes the September 22 Excalibur-thrust and paired-glove notes.


September 23 spring/combo refinement: [windup, mirrored combinations, overheads, nunchuck routines and rocket-effect details](SPRING_COMBOS.md). Supersedes earlier melee animation speeds and Mjolnir tumbling.
