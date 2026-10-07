# Rubber Duck fuel bursts � October 6, 2026

Rubber Duck now commits to a heading and emits three short flame pulses, 0.12 seconds apart. Each emits for 0.11 seconds. The minimum burst cycle is 0.78 seconds, so attack-speed upgrades cannot remove the pause. The ordinary scheduler uses the existing SpecialWeapons busy check; the server also independently rejects another launch during the same burst cycle. Each delayed pulse revalidates alive/active/not paused/not downed and the exact equipped copy before damage.

The nominal cycle is max(0.78, 3 � calculated attack cooldown). Each pulse deals normal attack damage � cycle / (3 � cooldown), preserving approximate prior sustained damage against an enemy that remains in the cone. Burst commitment now allows targets to move out of the heading. At high attack speeds fewer, larger damage pulses mean fewer independent proc opportunities than the old sustained cadence. Following a severe server stall, pulses are spaced instead of replayed simultaneously; pulses that no longer fit the burst cycle are dropped.

Client fire uses one ParticleEmitter per owner/slot, with a fixed 0.24-second lifetime, unlocked world-space particles, no inherited nozzle velocity, and mild downward acceleration for the burning fuel. Stopping emissions never clears living particles: the oldest disappear first. The last pulse drains completely before the next burst. No per-particle Parts, loops, or connections are added. The Armory showcase uses the same shared burst timing.

## Files

- `SpecialMotion.luau`: shared timing and nominal damage compensation.
- `SpecialWeapons.luau`: server-owned burst lifecycle, damage pulses, busy guard and delayed action validation.
- `SpecialWeaponVisuals.luau`: brief particle emission, gravity and age-based drain.
- `../ui/WeaponShowcaseStage.luau`: actual burst cadence in the preview (shared with washer changes).
- `DuckBurstTests.luau`: isolated timing and client renderer regression fixture.

## Verification

- Luau CLI: 40 assertions over cooldowns 0.03�2 seconds passed (three pulses, minimum pause, nominal DPS, fully dark interval).
- All four changed production modules and the test module compile.
- Studio integration and Play checks are performed and recorded by the parent integration task; this agent did not synchronize Studio or claim a live combat test.
- Client test entrypoint after installing a temporary `ReplicatedStorage.DuckBurstTests`: `require(game.ReplicatedStorage.DuckBurstTests)()`. It mounts the real isolated renderer, checks emission, uniform lifetime, gravity, disabled emission with still-live particles, destruction after drain, and per-slot independence; cleans up the fixture.

## Parent integration status

Seven runtime sources synchronized to roguelite Studio place 107877054949326; a second source-sync pass reported zero differences. Required combat Rojo build passed. Studio Play-start and subsequent state requests stopped responding, so client visual fixtures have not yet run. Temporary DuckBurstTests and WasherBurstTests ModuleScripts remain installed for validation; neither is in the production Rojo build. No purchase, reward, or production DataStore action was used.
