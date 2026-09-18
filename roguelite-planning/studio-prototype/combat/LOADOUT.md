# Six weapon slots and Studio inventory

Installed in roguelite, place 107877054949326, on September 17, 2026. This is separate from Copy The Scene.

## Use

Press **I**, click **Inventory [I]**, or choose **Inventory** in the existing UI preview. Select a numbered slot, then a weapon's **Equip** button. A populated slot is replaced; **Remove slot** clears it. Duplicate weapons are allowed. All 36 existing showcase weapons are available, with 3D previews and transparent practice stats. The **Weapons (x/6)** panel also appears in Shop. On desktop it stays visible while the catalog scrolls. **Back to game** restores the normal character camera. Menus do not pause the world.

Start with the katana in slot 1 and five empty slots. **K / Weapons** toggles all six equipped weapons; **Z / Zombies** toggles the practice wave. The inventory does not charge currency, grant rewards, write DataStores, or make purchases. It is a Studio test loadout, not persistent ownership.

## Runtime

- `WeaponCatalog.luau` and `WeaponMotion.luau` map into `ReplicatedStorage.RogueliteCombat`.
- `RogueliteCombat.server.luau` maps to the existing `ServerScriptService.RogueliteCombat`.
- `RogueliteCombat.client.luau` maps to the existing StarterPlayerScripts combat script.
- `../ui/WeaponInventoryUI.luau` maps to `ReplicatedStorage.WeaponInventoryUI`; the existing UI module provides its panel/button art and menu navigation.
- `InstallLoadout.luau` clones the reviewed play-size showcase into `RogueliteCombat.WeaponTemplates`, normalizes only combat copies, and creates EquipWeapon/Shot remotes. The separate displayed rocket specimen is excluded from the launcher. Katana dimensions use the previously measured normalized template.

Each player's replicated state has exactly six slot folders. Clients send only a slot number and catalog ID; the server checks integer range, known ID, template availability, request rate, living character, Studio, and Practice phase (or the prototype's absent run-state). Player identity comes from OnServerEvent. Clients never submit damage, targets, prices, or other players' state. Replacing a weapon resets that slot's attack with a brief equip delay. Respawn cancels attacks, preserves this session's equipped IDs, and reattaches visuals.

Slot anchors follow the character's horizontal orientation at 0, 60, 120, 180, 240, and 300 degrees. A common radius accounts for the largest equipped model and body size. Weapons do not circulate. Each slot independently selects its nearest living tagged enemy with a clear line of sight, aims toward it, and attacks on its own server cooldown. Melee uses sampled visible-model overlap plus distance and obstruction checks; ranged weapons use server rays, shotgun spread uses five rays, and blast weapons use bounded, obstruction-checked splash. Clients render shared poses, recoil, tracers/blasts, and confirmed damage numbers. Empty slots have no model or attack.

These are **practice attack profiles**, not 36 finished unique weapon abilities. Non-gun ranged/magic weapons currently share the ray profile; Molotov blasts still resolve immediately; the rocket launcher now uses the traveling modeled RPG described below. The old KatanaMotion and MotionTests remain as prior katana-only motion studies; the six-slot version uses WeaponMotion. Mesh sizes and showcase displays are preserved.

## Verification performed in actual Studio Play

- Opened Inventory with the I key. Used mouse clicks on slots and Equip cards to populate all six. Server count reached 6/6.
- Verified live rendered models: exactly six equipped models; their idle pivots matched replicated slot origins. Adjacent horizontal slot vectors had dot product 0.5 (60 degrees), with identical radius.
- Equipped katana, Glock, baseball bat, shotgun, rocket launcher, and Mjolnir through the client equip remote. Created six stationary server targets near the individual slots. All six lost health: 9300, 9584, 9375, 8980, 9560, 9375 remaining from 10000 in the sampled observation. This confirms melee, single-shot, spread, and blast paths without asserting a fixed-duration DPS measurement.
- Actual UI Remove cleared slot 6 and changed count to 5/6. Equipped Nail Gun from the scrolled catalog into that slot; count returned to 6/6. The pinned slot panel remained visible while scrolling.
- Seven malformed client requests (0, 7, fractional/NaN/string indices, unknown ID, table ID) did not change the six-slot state. A valid equip during an injected Combat phase was denied.
- Placed world blockers between all six slot origins and isolated targets, reset each to 10000 health, then enabled attacks. After 2.2 seconds all six remained at 10000: no attacks through walls.
- Switched to the existing Shop tab and verified the live Weapons (6/6) title.
- Respawned with a six-weapon loadout: all six IDs persisted, exactly six visual models reattached, camera subject matched the new Humanoid, and the I-key inventory reopened. Final fresh Play console was empty.
- Fresh Play console contained no gameplay errors. An earlier inspection command mistakenly queried a nonexistent ViewportFrame.IsLoaded property; that tool-only error was corrected and was not game code.
- Rojo builds of the combat project and root CopyTheScene project passed. Packaging includes scripts/UI, not the existing Studio world/mesh templates. Do not import the root build into roguelite.

Test fixtures and temporary phase/blocker changes were confined to Play and removed by stopping it. Edit scripts are synchronized to repository source. Studio was then left in a fresh Play session with the mixed six-weapon inventory open for review, without the temporary test fixtures. Previous combat scripts and UI source are backed up under ServerStorage.BeforeSixWeaponSlots.

Multiple real clients, latency, published-server denial of test remotes, mobile/gamepad interaction, every individual weapon's unique animation, and unusual avatar sizes still require testing. No persistence is implemented or tested here. Memory-game scoring/placement are untouched.


## Instant zombie death and hit feedback — September 17, 2026

Removed the old 0.65-second corpse delay. Server damage calls ZombieDeath.finish immediately on a lethal hit; the Died signal also handles other death sources. The idempotent finish method publishes only the last position, removes the enemy tag, and destroys the model synchronously. The chase script schedules its existing 3-second replacement from the actual death destruction, preserving wave-generation cancellation. Resetting/disabling the wave does not create death puffs or replacement timers.

ZombieDeath.luau maps to ReplicatedStorage.RogueliteCombat.ZombieDeath. ZombiePopped is a server-to-client RemoteEvent, also included in the Rojo project and InstallLoadout. Client feedback creates five small white/blue three-lobe cloud clusters, expanding and fading independently of the deleted zombie; all 15 noncolliding parts are removed after 0.38 seconds. Nonlethal hits show opaque white for 0.045 seconds, then fade over 0.09 seconds. A lethal hit never holds the body for a flash animation.

Actual Studio Play checks: three pistol hits against a 48-HP zombie produced a white flash, exactly one death pop, 15 cloud lobes, zero dead-corpse Heartbeat frames, and complete puff cleanup. Direct finish removed the model synchronously and a duplicate finish was harmless. A visual capture confirmed detached white/blue puffs with no corpse. The wave returned to exactly five zombies after 3.4 seconds, and the final console was empty. An initial callback implementation encountered a sandbox permission error on replacement spawning; moving the respawn callback into the chase script resolved it without broadening permissions. Multiplayer timing/latency remains untested.


## Modeled RPG projectile

Rocket Launcher (11) now fires the existing W11_Rocket_Component mesh (rbxassetid://88760761479585), preserving its play-size dimensions. InstallLoadout creates a normalized RocketTemplate with the tip facing forward. The source showcase and its loose rocket remain unchanged. RocketProjectile and RocketVisuals map into ReplicatedStorage.RogueliteCombat along with the server-to-client RocketFX event.

Tuning: 2.8-second cooldown (previously 1.5), 55 studs/second, 70-stud maximum travel, 9-stud explosion radius, up to 70 damage with linear falloff to 35% at the edge. Each living enemy can receive one damage application per blast. The server sweeps the entire traveled segment each frame, checks the path to the muzzle, resolves world/enemy impact, and checks blast line of sight. No Roblox Explosion physics or player damage is used. Rockets fly straight toward the acquired aim, with a visible modeled projectile, exhaust, and impact flash. No damage happens at launch. Misses expire without an impact explosion; wave disable and character removal cancel in-flight rockets.

Studio Play validation: equipped the launcher through the actual client remote and observed the source rocket mesh in flight. Measured 2.8168 seconds between launches and about 0.4335 seconds of travel for the staged target. Target remained at 1000 HP while the rocket was in flight. After impact: primary target 935 HP, nearby splash target 951 HP, protected target behind a wall 1000 HP. Visual capture confirmed forward-facing modeled projectile between barrel and target. Console was empty. All isolated test fixtures were confined to Play. Multi-client/latency behavior remains untested.


## RPG cloud trail

Replaced the bundled particle exhaust with white/gray three-lobe 3D cloud puffs guided by the supplied 11_04_36 PM cloud reference. RocketVisuals samples the traveled path every 1.8 studs, using each sample's emission time rather than frame time. Puffs remain in world space, expand slightly, rise 0.45 studs, and fade oldest-first across a 0.95-second lifetime. They are parented separately from the rocket so impact/removal does not abruptly erase the trail. Parts cannot collide, touch, or participate in raycasts. A 150-stud camera cull and a global 144-cloud cap bound client visual work. No server damage or projectile tuning changed.

Actual Studio Play: 17 clouds sampled in flight; oldest opacity was lower (transparency 0.5726 versus newest 0.06). Screenshot confirmed a spaced cloud trail behind the modeled RPG. Clouds remained after impact and were completely cleaned up within the subsequent 1.1-second observation. Console was empty. Both Rojo packaging builds passed. Multiple-client/performance stress remains untested.


### Cloud variants and tapered transition
The trail now cycles through six original 3D silhouettes: tall billow, wide bank, diagonal plume, round cluster, beaded tail, and split cloud. New clouds are fuller; each continuously shrinks and contracts its lobe spacing using smoothstep interpolation, becoming a smaller, simpler, fainter puff at the oldest end. Lifetime is 1.15 seconds, replacing the previous growing-cloud behavior. Size, shape, and mirroring vary without discrete swaps or pops.

Studio Play visual-preview validation through the RocketFX event showed all six variants simultaneously. Matched shapes measured 0.6058 studs for an older lobe versus 1.1147 studs for a newer lobe. A second observation of the same lobe confirmed continuous shrinking; the complete trail cleaned up afterward. Screenshot confirmed the tapered silhouettes. Console was empty. Studio returned to Edit after verification. Both Rojo builds passed.


### Denser smoke, starting at the muzzle
Cloud samples are now 0.75 studs apart (previously 1.8). Launch packets track the rocket tip starting at the muzzle, so RocketVisuals waits until tip travel reaches RocketTemplate.Length before emitting from the tail. The first emission anchor is therefore at the muzzle, with subsequent anchors outside the barrel; no samples are generated along the rocket body inside the launcher. The distance sampling grid and delayed-frame catch-up both respect this boundary. Shape variation, shrinking, and fade timing are unchanged.

Studio client visual-preview check measured first emission after 2.5266075 studs of tip travel against a 2.5266085-stud rocket, and consecutive spacing of 0.7500029 studs (floating-point tolerance). Console was empty. Both Rojo builds passed.


## Supplied rocket explosion sprites — September 18, 2026

Replaced the large expanding neon sphere with the user's transparent orange/yellow explosion artwork. RocketExplosionVisuals.luau is mounted by RocketVisuals and packaged under ReplicatedStorage.RogueliteCombat. Each server-confirmed impact produces two compact overlapping central bursts and seven smaller satellites. Satellite centers span roughly 42–85% of the current server-supplied damage radius, with varied artwork, rotation, size, and short stagger. Burst lifetime is 0.25–0.4 seconds. Pixel sizing is capped near 150 px for central bursts and 65 px for satellites (brief pop scale can exceed those bases by up to 5%); small viewports reduce the limits further. Billboards respect world occlusion instead of drawing through walls, and have no physics or damage authority. Global active-sprite count is capped at 144. Rocket damage/range/fire rate and smoke behavior are unchanged.

The two unmodified user atlases are in combat/assets. Roblox serves the uploaded textures at 1024px, so runtime ImageRect coordinates use 1024 instead of the source 1254px dimensions. No image generation or pixel edits were needed.

Verification in Studio Play: direct visual test counted two impact and seven scatter sprites, all scatter centers within the 9-stud test radius, with a maximum sampled pop size of 152 px. Sprites were completely removed by the subsequent 0.5-second cleanup check. Visual screenshot confirmed recognizable clean artwork and stronger center emphasis. A real automatically fired RPG also produced exactly nine sprites on impact. Final Play console was empty. Earlier development-only inspection queried a protected ContentImageSize property; this was removed from the workflow. Tests interrupted by Studio returning to Edit were rerun successfully. Multi-client/latency remains untested. Both Rojo packaging builds passed.

## Forward-facing idle weapons
WeaponMotion now uses the character's flattened forward direction for every idle slot instead of the radial direction away from the character. Slot positions and explicit target aiming are preserved. Studio verification passed for 48 poses (eight headings times six slots), including unchanged origins and target aiming. Actual Play with six equipped weapon models confirmed every idle model faced character forward; console was empty. Both Rojo builds passed. Returned Studio to Edit after testing.


## Buoyant weapon movement
Client-only float motion adds a small phased idle bob, movement sway and velocity lag, and a damped vertical spring for jump/landing rebound. Attack motion reduces float strength to 35%; roll preserves the weapon aim axis. Server damage poses remain unchanged. Float state resets with each character and is removed with player state. Spring integration uses 120 Hz substeps with capped frame time and velocity targets.
Verification: simulated 20/30/60/144 FPS movement, jumping, landing and settling preserved aim and stayed below 0.745 studs displacement. Actual Studio Play with six equipped weapons and W/Space/D inputs recorded 307 frames, 16.18 studs/s horizontal and 50.67 studs/s vertical motion, with peak cosmetic displacement 0.517 studs. Console empty; both Rojo builds passed. Multiplayer visual testing remains untested.


Bouncier tuning: walking bob increased from 0.175 to 0.34 studs, sway from 0.075 to 0.16, stronger velocity lag and jump response, damping reduced from 13 to 8 for springier rebound. Cosmetic displacement capped at 1.2 studs after an initial stress check exceeded the intended range. Final 20/30/60/144 FPS checks passed for bounded displacement, settling and unchanged aim. Six weapons equipped and movement/jump inputs exercised in Studio Play. Both Rojo builds passed.


## Bullet contact markers
StatProjectiles marks actual swept contacts on the Shot packet, including walls and each piercing/bouncing contact. Flight segments and range expiry do not create markers; Blast and Lightning keep their existing effects. Client creates one compact sprite per contact, using row 2 with 80% probability and row 4 with 20%, five variants per row. Maximum 52 px, 0.16-0.23 second lifetime, 96 active cap, world occlusion respected. No damage logic changed.
Studio: 500 samples selected 409 row-2 and 91 row-4 markers; cap and cleanup passed. Actual gunfire produced 10 contacts and exactly 10 markers. Asset fetch succeeded and visual crop check confirmed both requested rows. Console empty; both Rojo builds passed. Multiplayer latency untested.


## Draco barrel origin
Draco projectiles now start at its normalized barrel mouth (0, 0.585, -1.385), instead of its magazine-centered slot pivot. A short obstruction ray prevents moving the spawn through nearby geometry. Shot packets identify the owner, slot and first segment so that the initial tracer starts at that rendered weapon's muzzle, including cosmetic bob/sway. Remaining travel and impact stay on the server projectile path. Both Rojo builds passed. Studio live test received 101 first-segment Draco packets; an initial test comparing against the latest shared tracer was invalid for simultaneous six-gun fire, so alignment was checked separately with isolated slot packets.


## Glock and shotgun barrel origins
Extended the shared muzzle map to Glock (0, 0.56, -1.195) and shotgun (0, 0.315, -1.67) using their normalized play-size meshes. Server muzzle placement and client first-tracer alignment now use each weapon's offset. Spread pellets share the central weapon direction when computing their spawn, so all pellets originate at one barrel mouth. Obstruction checking, damage, and impact markers remain intact. Both Rojo builds passed; Studio tested alternating Glock/shotgun slots with 18 isolated tracer packets.


## Cartoon rocket flight
RocketMotion supplies a deterministic varied sideways wobble and rising loop shared by server flight, client mesh heading, and the smoke exhaust. Curvature starts after 3.5 studs of muzzle clearance and smoothly returns to the launch aim line at the original target distance; close shots remain straight. Rockets do not navigate around walls or home on moving targets. Swept collision follows the curved path in segments at most 0.65 forward studs, preserving one server-owned blast and existing damage. Scaled rocket length is respected by its visual pivot and smoke tail.
Validation: 80 seed/distance combinations returned to the aim line, had valid headings and at most 4.212 studs lateral/vertical deviation. A server test placed a wall on the curve and confirmed exactly one impact. Both Rojo packaging builds passed. Multiplayer latency/performance remains untested.


Gentler rocket revision: replaced tight compound oscillation with a broad single sine weave, reduced amplitude to 0.7 studs and frequency to 0.15-0.18 radians per stud, with minimal vertical motion. Across 120 seed/range combinations measured maximum deviation 0.705 studs and heading change 7.20 degrees. Shared server/client path remains intact. Both builds passed; restarted Play with three launchers for review.

