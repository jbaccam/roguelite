# Larger, sustained swarms — October 5, 2026

Requested normal-wave occupancy is doubled (`EnemyScheduler.SWARM` 1.2 → 2.4). The existing 100 regular-slot ceiling and ten-slot Endless boss reservation remain. This is a bounded increase for the current replicated Humanoid implementation, not a claim of measured capacity above 100.

| Wave | Previous solo target | New solo target | New four-player target |
| --- | ---: | ---: | ---: |
| 1 | 10 | 19 | 65 |
| 5 | 24 | 48 | 100 |
| 10 | 42 | 84 | 100 |
| 20 | 78 | 100 | 100 |

The server spawn director now forms groups of 6–8 instead of 4–6, in rotating swarms of approximately 24 instead of 12. Groups stagger by 0.12 seconds instead of 0.2, with 0.12-second gaps between swarm headings. Spawn centers prefer 28–52 studs from a living player instead of 28–70, allowing more mobs to reach the fight before being cleared. Existing player clearance, arena floor and obstacle checks remain.

Dead regular slots wait 0.15 seconds rather than 0.35, then gather for at most 0.35 seconds rather than 0.65 before the full one-second spawn telegraph. A gathered batch of six begins after 0.12 seconds. Existing queued-slot deduplication, generation checks and alive-player scaling remain authoritative. The once-per-second population check also repairs absent normal-wave slots after a failed or interrupted spawn, rather than only reacting to increases in requested count. Tutorial and fixed-count no-respawn waves skip this repair; tutorial counts, group sizes, preferred distance and staggering remain unchanged. Explicit practice population overrides retain their exact requested counts.

This changes count and arrival cadence only. Health/damage scaling is maintained separately. Existing enemy body collision/contact rules provide crowd pressure; no artificial player slowdown was added. Higher kill throughput can increase temporary shard/XP income, so full-run economy and six-weapon build tuning still need playtesting.

## Verification

- Updated existing `EnemySchedulerTests` population expectations, multiplayer monotonicity sample and boss reservation checks for the new target curve.
- `git diff --check` passed for this edit (a separate concurrent file emitted only a CRLF normalization warning).
- StyLua parsed all three edited Luau files without parse errors; its check returned existing formatting differences. Independently calculated wave 1/5/10/20 targets for one through four players: `19/36/52/65`, `48/91/100/100`, `84/100/100/100`, `100/100/100/100`.
- No Studio Play test was run by the swarm implementation agent. Parent integration owns Studio synchronization, runtime tests and the final combat-overlay build. Actual multiplayer, mobile frame time, combat pressure and full-run economy are not yet verified by this change.
