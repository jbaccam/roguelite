# Enemy simulation and combat architecture

**Status:** Required direction for future implementation, confirmed by the user on 2026-09-17. Not implemented or performance-verified.

## Authority and presentation

Build the horde as server-owned enemy records with client-only visual models. Each record includes a stable ID and spawn generation, type, position, velocity, health, collision dimensions, target, and behavior state. Ordinary enemies must not require a replicated Humanoid rig or physical assembly per enemy. The existing five server-owned zombie chasers are a movement/art prototype, not the scalable combat foundation.

The server owns enemy movement, ground/wall collision, crowd separation, targeting, attack timing, hit detection, damage, death, drops, and rewards. Use simple logical collision shapes, spatial queries, and bounded world collision checks. Client models are cosmetic and must not physically affect gameplay. Removing a local model cannot remove the corresponding enemy or stop its server attack.

The client owns pooled models, animation, sound, cosmetic projectiles, impacts, and smooth presentation. Preserve the approved native R15 zombie appearance and forward-arm run animation when moving presentation to the client. Weapon code must query enemy records through a common combat interface rather than depend on Workspace NPC parts, Humanoids, or Touched events. Automatic target selection and attack eligibility remain on the server.

Validate input intent, run membership, phase, equipped inventory, cooldowns, range, line of sight where applicable, and finite numeric values. Rate-limit requests. Never accept client claims of damage, kills, rewards, or enemy position. Validate player movement used for combat too: server-owned enemy records alone do not prevent player teleport or movement exploits. This architecture is cheat-resistant, not unhackable.

## Simulation and replication

- Use a central, bounded simulation scheduler with a fixed timestep and capped catch-up work. Separate simulation, target refresh, path planning, and network send cadences; do not create an independent heartbeat/pathfinding loop per enemy.
- Batch nearby enemy snapshots containing IDs, generations, sequence/tick, server time, positions, velocities, and relevant behavior state. Tune send frequency against measured bandwidth and visual error; "a couple of times a second" is a reference example, not an accepted rate.
- Use reliable lifecycle messages for spawn, death/despawn, and critical combat state, plus a baseline/resync mechanism for joining players and interest changes. Disposable movement snapshots may use UnreliableRemoteEvent, subject to current payload limits. Bound batch sizes, discard stale/out-of-order snapshots, and prevent delayed packets from resurrecting a dead or reused ID.
- Interpolate buffered snapshots each render frame. Use bounded extrapolation when updates are late, then reconcile toward authoritative state; snap/reset for teleports or large discontinuities. Visual prediction never determines a hit. Keep attack telegraphs aligned with server timing and account for presentation delay when evaluating combat fairness.
- Pool and cull visual models and effects. Distance-based animation/detail reductions must retain nearby hazards and essential attack telegraphs. Interest filtering must include a margin for incoming threats and preserve lifecycle correctness.

## Targeting and navigation

Use spatial partitioning for nearby target searches, enemy separation, and combat broad-phase queries. Compare squared distances. A first occupied cell does **not** prove the nearest target was found: an adjacent cell may contain a closer candidate. Continue until the minimum possible distance to every unvisited cell exceeds the best candidate distance, or search all cells intersecting the defined acquisition radius. With only a few player targets, a direct scan may be cheaper; measure before adding indexing overhead.

Prefer direct steering where a traversable corridor exists. A visibility ray alone does not prove an enemy body can fit or that the ground is walkable. Reuse a valid route until the target moves meaningfully, the route is blocked, navigation geometry changes, or the enemy becomes stuck.

Share cached routes or flow fields among enemies with compatible navigation constraints and destinations. Validate each enemy's connection to the shared route; do not blindly copy waypoints through walls. Cache by destination region, navigation region, agent dimensions/capabilities, and world revision. Budget and stagger path requests, bound cache lifetime, and apply local obstacle avoidance and separation between route updates. Do not recompute a full path for every enemy every frame.

## Implementation order and acceptance

1. Replace the five-chaser runtime with server records plus client presentation, preserving appearance, chase feel, and the current tuned 13.5 speed. Validate walls, slopes, crowd separation, death/despawn cleanup, late join, and multiplayer target changes before combat depends on it.
2. Build server health/damage and automatic Glock combat against the record/query interface; render bullets and effects locally. Add death, XP collection, and the first stat choice using authoritative results.
3. Profile 25, 50, 75, and 100 enemies with actual attacks, effects, and drops. Then attempt 250 and 500 as stress targets. These counts are aspirations, not supported capacity claims. Set explicit frame-time, memory, bandwidth, and visual-error budgets on named target devices before accepting a production cap.
4. Record server frame time and simulation costs, client frame time, network volume, instance count, pool reuse, memory growth, and path requests. Include sustained runs, representative mobile hardware, multiple real clients, and simulated latency, jitter, and packet loss.
5. Test forged/spammed requests, stale snapshots, ID reuse, resync, disconnects, and local deletion/movement of visual enemies. Verify authoritative health, collision, death, and rewards remain correct. Document tests needing real clients or published access; do not report unperformed tests as passed.

This decision changes planning only. It does not implement combat or alter the current Studio prototype. Keep Studio DataStores disabled by default and synchronize runtime source changes with the separate roguelite place when implementation begins.

## Reference grounding

The user supplied Final Swarm explanations as inspiration. They establish the desired separation of simulation and visuals, not verified benchmarks for this game.

- [Roblox performance guidance](https://create.roblox.com/docs/performance-optimization/improve): reduce unnecessary NPC Humanoid and replication work; create presentation locally where appropriate.
- [Remote events and callbacks](https://create.roblox.com/docs/scripting/events/remote): unreliable events suit disposable updates and trade away ordering and reliability.
- [Client-server boundary validation](https://create.roblox.com/docs/scripting/security/client-server-boundary): validate client requests before changing authoritative state.
- [Security and cheat mitigation](https://create.roblox.com/docs/scripting/security/security-tactics): client control remains a security consideration even with server validation.
