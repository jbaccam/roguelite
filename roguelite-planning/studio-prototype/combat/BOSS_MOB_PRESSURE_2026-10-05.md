# Room to reach the boss — October 5, 2026

During any live boss encounter, normal numbered regular-enemy slots now cap at **20 / 28 / 36 / 44** for one through four living players. This includes wave 10, wave 20 and Endless bosses. Detection uses the actual live boss model and positive Humanoid health, rather than only the Endless handle or a wave number. A smaller ordinary wave never grows just because a boss appeared. Normal population resumes after the boss dies or leaves.

While the boss lives, 2–4-enemy groups start at most every **0.65 seconds** instead of 0.22, and defeated regular slots wait **1.5 seconds** before rejoining the arrival queue. The full one-second warning remains. Per-slot cooldown timestamps prevent periodic missing-slot repair from bypassing this delay.

On boss arrival, already-existing numbered regular slots above the cap are removed directly with `Destroy`, without lowering health or invoking the death/reward pipeline. They award no drops, XP, kill credit or permanent rewards. Excess queued groups are discarded before warning creation, and in-flight groups still obey the current cap when they attempt to spawn. This opens space promptly instead of waiting for the player to clear 80 excess enemies. Bosses and explicit admin extra spawns are preserved.

Tutorial, fixed-count/no-respawn waves and explicit practice count overrides retain their exact counts and original arrival behavior. Ordinary Admin Jump Wave encounters apply the boss cap unless a count override is deliberately active. Boss-body steering and weapon target selection were not changed in this patch.

## Verification

Official Luau CLI `BossPressureTests.py` passed using extracted production boss-detection, spawn-count and trimming functions: all four player caps, no-reward trimming (all removed mobs retain positive health), preserved admin extras/boss, tutorial/no-respawn/count overrides, live/dead/cosmetic/removed boss transitions, normal count restoration, and empty/small wave bounds.

Expanded `SpawnDirectorTests.py` passed actual director scheduling checks for boss interval, excess queued-slot removal, and respawn cooldown enforcement, along with its previous distribution, generation, warning and pause-recovery cases. Both runtime Luau files compiled successfully. The implementation agent did not run Studio Play; parent integration owns synchronization and live encounter verification.
