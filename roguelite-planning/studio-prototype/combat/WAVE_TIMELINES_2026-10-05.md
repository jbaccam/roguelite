# Authored arrival timelines — October 5, 2026

## Boss cadence correction after player feedback

Boss adds now schedule **six every three seconds**, replacing four every eight seconds on all maps. This is four times the sustained arrival rate, with 84 scheduled solo arrivals in the first 40 seconds before capacity/placement limits. Individual scattered warnings and the concurrent 20/28/36/44 boss-add caps remain. No enemy HP or movement changes are included in this correction. Earlier cadence figures below describe the prior version.

Applied to Studio: one changed module, source equality verified. Studio Edit execution of the installed module confirmed amount 6, interval 3 and 84 scheduled arrivals in 40 seconds. WaveTimelineTests passed 13,939 assertions and the combat Rojo build passed. The active Play session was stopped to apply the edit; no subsequent live fight was run for this correction.

Ordinary timed combat waves now use authored group arrivals instead of immediately replacing each killed enemy. The design takes inspiration from the requested wave-timeline structure; these counts, compositions and pacing are this game's own 40-second-wave adaptation.

## Pacing and composition

`WaveTimeline.Profiles` authors all twenty waves. Opening arrivals begin at active time zero, then repeat every 4–6 seconds. Solo examples:

| Wave | Ordinary arrival interval | Enemies per arrival | Scheduled total in 40 seconds |
| --- | ---: | ---: | ---: |
| 1 | 6 s | 6 | 42 |
| 5 | 5 s | 9 | 72 |
| 10, if no boss | 4 s | 12 | 120 |
| 20, if no boss | 4 s | 18 | 180 |
| Active boss encounter | 8 s | 4 | 20 |

Actual wave-10 and wave-20 bosses select the small boss-add schedule. It continues every eight active seconds after forty seconds while the boss keeps the wave open. Concurrent ordinary boss adds remain capped at **20 / 28 / 36 / 44** for one through four players. Ordinary arrival amounts scale by **1 / 1.5 / 2 / 2.5**, with the global living-enemy limit still **100**. These are budgets, not guaranteed occupied counts: deaths leave space until the next scheduled group.

Wave 1 starts with basic enemies. Fast-role frequency increases through the early waves; heavy-role slots begin at wave 8. Heavy shares increase modestly later. Roles select only enemies from the active map's existing roster, preserving repeated roster entries as weighting. Within a role, selection cycles through its available roster members; ranged and other ordinary types participate in the basic pool. Missing roles fall back within that map. Invalid explicit rosters produce no foreign-map fallback. Pine Valley's absent explicit roster retains its existing regular/baby/tank set; this change does not add its currently unlisted Spitter to natural spawns.

All five map rosters are exercised across twenty waves by the regression suite: every existing roster member appears and no foreign-map enemy appears. Endless reuses the wave-20 schedule with the existing Endless stat scaling, tough-type substitutions and random boss encounters.

## Safe arrivals and capacity

- Each timed arrival has individual locations separated by the existing ten-stud spawn-point spacing, distributed around living players. It no longer packs a whole group into one small ring.
- Every position receives its red X for a full second of active warning time. Pauses, admin freeze and boss cinematics freeze the warning and arrival clocks. If a player enters any marked location, the group retries at fresh locations with another full warning. Invalid ground has no unmarked fallback.
- A small dispatcher reserves at most three upcoming warnings per quarter second. A hitch emits at most one overdue timeline pulse per step, and the existing warning-start stream prevents a mass spawn burst.
- When capacity is full, the oldest eligible ordinary enemy is removed to make room for a scheduled arrival. This is deterministic retirement chosen for this game, not a claim about another game's exact removal algorithm. It calls `Destroy`, not lethal damage or `Death.finish`, and gives no death reward, shards, XP, split children or kill credit.
- Bosses, elites and explicit admin extras count toward the global cap and are protected from retirement. If protected rigs exhaust capacity, ordinary arrivals defer. The actual regular-enemy spawn entry also checks capacity, so splitter children cannot bypass it.
- A boss appearing mid-wave cancels pending ordinary arrivals and switches to the smaller add schedule, trimming excess ordinary mobs without kill rewards. Boss departure does not replay a backlog of missed regular pulses.

Tutorial/fixed-count waves, explicit “Keep N alive” overrides and sandbox practice retain their existing exact-count/respawn paths. Ordinary timeline enemies do not trigger death-driven, one-second repair or resume refills. Normal's shared 0.85 enemy-speed multiplier is applied to every regular enemy type before the existing Endless adjustment; boss motion has its own tuning.

## Splitter lifecycle

Lava Slime splitting now uses one shared synchronous `Death.onDeath` listener and a per-model dispatch table. The callback clears its entry before spawning children. It therefore works before immediate corpse removal, runs once, respects spawn capacity, survives a same-wave boss transition, and never triggers from population retirement. The Humanoid death event still calls the common death lifecycle.

## Economy and validation

Per-enemy shard/XP amounts are unchanged. Total wave rewards can change: the previous refill system had a kill-rate-dependent, effectively unbounded spawn budget; the new ordinary waves have authored finite totals. Actual income and difficulty require play measurement against these schedules rather than assuming the old economy is preserved.

Completed offline verification:

- **WaveTimelineTests: 13,939 assertions**: deterministic totals at different clock steps; pause/hitch behavior; boss transitions and held-wave continuation; composition gates; all five map rosters; capacity and protected retirement; safe locations and full active warning time.
- **SpawnDirectorTests**: executes the actual extracted warning/queue functions, including timed scattered placement, missing-ground retry, full-warning relocation, generation cancellation, paused tutorial recovery, ordinary/practice cadence and boss capacity.
- **BossPressureTests**: actual boss detection/count/trim functions; 20/28/36/44 limits; tutorials and overrides; no damage on retirement.
- **TimelineLifecycleTests**: actual capacity-removal and synchronous splitter hooks; protected rigs; pending reservations; no reward-producing death on retirement; exactly-once children; old-wave rejection and same-wave boss transitions.
- Official Luau compiler accepted the edited Chase script and new WaveTimeline module.

This subagent did not run Studio Play. Parent integration owns Studio synchronization and the forty-second wave, all-map, warning and boss-add play tests; those results should be recorded in the parent integration report.
