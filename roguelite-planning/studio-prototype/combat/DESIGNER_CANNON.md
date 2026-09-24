# Designer cannon, shard movement, and mob collisions

Implemented from the September 24 request. Weapon 10 launches an actual rolled cotton tee from its normalized barrel mouth `(0, .302, -1.802)`, with the roll's long axis along flight. Travel speed is 48 studs/second before stat modifiers. It uses the existing server swept-projectile simulation, range, walls, piercing, bouncing, ownership, and target validation. Each projectile has its own visual identity, including multi-projectile volleys. Cannon shots do not display bullet tracers or gun muzzle flashes.

An authoritative positive direct cannon hit sets `DesignerShirt=true` before damage, including lethal hits. Subsequent hits do not stack the mark. Any later killer receives the normal 2 shards plus a fixed 2-shard designer bonus in the existing pickup. Shard value is server-owned; pickups retain normal owner, phase, distance, wall, arrival, and duplicate checks. Practice targets can wear the shirt but grant no currency. Cosmetics are client-only and cannot collide or participate in hit queries.

Crystals retain their bounce/glow and now turn at .65 radians/second with a restrained 3-degree pitch / 2-degree roll sway. Pickup positions are unchanged.

`MobCollision` applies player and mob collision groups to current instances, respawns, newly tagged mobs, and newly added character parts. Players cannot stand on mobs, while both still collide with the world. Existing distance-based enemy attacks continue to work.

## Verification in the connected roguelite Studio place

- Rojo combat overlay built successfully.
- `DesignerShirtTests.luau`: 31 server checks passed, including lethal first-shot bonus, non-stacking marks, another weapon delivering the kill, normal kill value, duplicate reward rejection, practice exclusion, character collision groups, and late-added avatar parts.
- Actual cannon autoattack hit an initially unmarked mutant practice target and set its designer mark. Client rendered the fitted garment. Observed 20 cannon hits in one run.
- Actual client flight sampling observed six rolled projectiles and 162 server flight segments over eight seconds at the final 48 studs/second setting. Initial deferred pose samples had up to .867 studs of normal frame advancement; use `LaunchOrigin` for an exact spawn-origin check rather than sampling an already moving pose.
- Final exact-origin check: five launches, maximum difference between `LaunchOrigin` and the rendered cannon muzzle **0 studs**. Final console had no errors.
- Actual avatar landing test: mob top Y=11.325; avatar fell past it to ground at root Y=5.000. Passed.
- Actual rendered shard sample: .401 radians rotation and .106 studs vertical movement over approximately .6 seconds; aura and point glow both enabled.
- Inspected front-facing shirts on baby, regular, mutant, and hammer boss models in Play. Neckline correction leaves the boss's face exposed. Sleeves and torso follow their respective animated body parts.

Current renderer and performance limitations are in [the asset README](../../rolled-shirt/README.md). Multiple real clients, published DataStores, and dense-horde/mobile performance were not tested. Studio test fixtures are temporary and removed by stopping Play. Only task-owned scripts were synchronized; unrelated map/model content was preserved. Pre-change scripts are backed up in `ServerStorage.BeforeDesignerShirt_20260924`.

Build: `rojo build roguelite-planning/studio-prototype/combat/default.project.json -o build/RogueliteKatanaCombat.rbxlx`. Serve this overlay only; never sync the mixed workspace's Copy The Scene root project into roguelite. `InstallDesignerClothCapabilities.luau` reproduces this place's script capability configuration after a fresh source installation.
