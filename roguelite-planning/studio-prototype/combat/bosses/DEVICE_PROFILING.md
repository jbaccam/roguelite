# Device profiling: measure before touching lighting or streaming

Lighting (Realistic + PrioritizeLightingQuality) and the Atomic-streamed arenas stay as they are
until a phone or low-end PC capture shows they are the cost. The client code carries
MicroProfiler labels so a spike can be pinned on one system.

## Labels
| Label | Where | What it times |
|---|---|---|
| `Boss:Frame` | MapBossPresentation | one boss's whole client frame (animation, warnings, effects) |
| `Boss:BuildWarning` | MapBossPresentation | building a ground warning (FireBreath ~115 parts, pooled after the first cast) |
| `Boss:PaintWarning` | MapBossPresentation | the per-frame warning repaint |
| `Boss:Vfx:<hook>` | MapBossPresentation `call` | a BossVfx/Common hook: windup, impact, active, projectile, intro, enrage, aftershock |
| `EnemyAnim:Update` | RogueliteZombieAnimation | every ordinary enemy's animation for the frame |
| `EnemyMotion:Decode` / `:Compile` | EnemyMotion.warm | one slice of a new enemy type's clip build (should be short) |

## Capturing
- PC: Ctrl+Alt+F6 opens the MicroProfiler (Ctrl+F6 in Studio). Ctrl+P pauses at a spike;
  Dump > 128 frames writes an HTML file to `%LOCALAPPDATA%\Roblox\logs\microprofile`.
- Phone: in-experience Settings > MicroProfiler on. The device shows an address and port; open it
  in a PC browser on the same Wi-Fi, set 128 frames and press Capture to download the dump.
- Scenario 1, FireBreath: fight the Dragon and start the capture when the cast's warning appears,
  so the 128 frames span wind-up, impact and the breath.
- Scenario 2, crowd: reach wave 15 on a map with a roster (e.g. BeachCove) and capture while the
  full crowd chases you. Take one capture standing still and one while moving through the arena.

## Reading it
Open the dump, sort frames by time and look at the slowest. Note frame ms, the render/GPU share
(Render, Prepare, Shadows, GPU wait) and the script share (the labels above).

## What would justify a change
- Lighting: on the phone, slow frames over 33 ms where render/GPU is over 60% of the frame and
  `Boss:*` + `EnemyAnim:Update` together are under 3 ms. Try PrioritizeLightingQuality off first.
- Streaming: spikes over 10 ms in streaming/replication work (Replicator, deserialize, streaming
  jobs) when entering an arena, or client memory near the device limit (F9 > Memory). Only then
  look at Default (non-atomic) streaming for the 688/681-part arenas.
- Script instead: `EnemyAnim:Update` over 4 ms at wave 15 (next step: update far enemies at half
  rate), `Boss:BuildWarning` over 8 ms after the first cast (split the build over two frames) or
  `Boss:PaintWarning` over 1 ms (fewer edge segments).
