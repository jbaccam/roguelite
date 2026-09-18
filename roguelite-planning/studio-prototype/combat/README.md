# Six-slot weapon practice

Current implementation: [LOADOUT.md](LOADOUT.md). Studio now has a live all-weapons inventory, six server-owned slots, and independent auto-targeting. The katana-only notes below record earlier prototype behavior and are not the current six-slot motion implementation.

# Katana combat prototype

Installed in the roguelite place, 107877054949326. This is independent of the root CopyTheScene game.

## Test

Play in Studio. The katana floats blade-up on the avatar's right and automatically slashes reachable zombies. No weapon is held by the avatar. Existing player movement and zombie chase speed are preserved.

- **Z / Zombies button:** remove the current active wave; re-enable to spawn five fresh zombies. The static reference zombie stays.
- **K / Katana button:** hide/show the weapon and disable/enable its attacks for that player.
- Zombies have 100 health. Initial katana tuning is 25 damage every 0.58 seconds, with 0.10s windup, 0.10s strike, and 0.18s recovery. Each zombie can be damaged once per swing; a slash may hit multiple enemies.
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
