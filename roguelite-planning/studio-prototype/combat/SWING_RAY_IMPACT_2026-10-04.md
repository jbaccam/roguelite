# Wider diagonal cuts and Ray Gun impact splash

Integrated verification completed: **170,649** shared swing geometry checks, **452** fresh-source ray checks, and **10** actual Server Play physics checks passed. The physics fixture recorded direct damage 100, near splash 45.0073, far splash 22.5073 and one effect event. All 175 preview presentations, 14 real-frame effect cases and 18,483 cadence checks also passed. No real target health, persistent rewards or player profiles were changed by the fixtures. Source/Studio only, not published live.

The user requested diagonal cuts with starting and finishing points on opposite sides of the wielder, comparable to horizontal cuts. Shared `WeaponMotion` now sweeps the diagonal path through 200 degrees for hit sampling and 216 degrees for presentation, with a restrained descending follow-through. It retains the existing weapon size, resolved reach, hit window, once-per-swing hit tracking, and obstacle authorization. The same path applies to Pan, Katana, Baseball Bat, Shovel, Vampire Blade, and other weapons that select the shared Diagonal style. Existing overhead, thrust, chain, and return profiles are unchanged. Katana's horizontal visual arc is modestly narrower at 220 degrees, with its existing 210-degree hit path preserved. Other horizontal arcs retain their 240-degree presentation.

Ray Gun now splashes on a server-confirmed enemy or wall contact, including nonlethal hits. A range-end miss does not create an explosion. `RayImpact` holds the shared radius and falloff policy; tiers I–IV use radii 6/6/7/9 studs and maximum secondary damage of 60/60/65/75% of the bolt's damage. Falloff is linear to one quarter of that fraction at the edge. AreaSize modifies radius, capped at 12 studs. Each contact can affect up to 12 living, tagged, visible neighbors, nearest first. Practice shots only affect practice targets.

The directly hit enemy receives its normal direct hit and is excluded from splash. Splash victims enter the projectile's existing hit set before the damage callback, so later piercing or bouncing legs cannot damage them again. Secondary damage retains the existing pierce/bounce damage decay and the server's damage authorization. Splash does not recursively trigger another Godly special. The old additional kill-only blast was removed; lethal hit events still produce disintegration.

`StatProjectiles` emits `GodlyFX("RayImpact", ownerId, position, radius)` once per actual contact. `GodlyVisuals` renders the production green shockwave, spheres, sparks, and light with this radius. The showcase uses the same handler and `RayImpact.radius(definition)`, so its demonstration shares the real blast size. `Burst` remains an accepted cosmetic event for compatibility; real Ray kills do not emit an extra Burst.

## Verification

- StyLua parsed the six changed runtime sources. Existing compact formatting was preserved.
- The combat Rojo overlay builds successfully, including the new RayImpact mapping and previously missing GodlyVisuals/GodlyWeapons mappings.
- The coordinating agent ran `SwingArcTests` in actual Studio Play against the synced module and reviewed templates: **170,649 checks passed**. It covers nine weapon models, both sides, four headings, close/medium/far targets, authoritative and rendered paths, comparable lateral footprint, bounded reach, and Katana's narrower horizontal presentation.
- `RayImpactTests.run(read)` exercises the real fresh-source StatProjectiles and RayImpact with dependency-isolated clocks, physics results, and network recording. It covers direct/secondary hit accounting, lethal/nonlethal contacts, decreasing falloff, wall contacts, range misses, practice/dead/untagged/removed/wall exclusions, pierce decay, shared victim history, and nearest-target caps. Its executed Studio result is recorded by the coordinator after integration.
- `RayImpactTests.live()` is a Server Play fixture using the installed production projectile module and actual Spherecast/raycast filters. It creates temporary anchored practice targets far from the map, records damage callbacks without damaging or rewarding anything, and cleans its targets afterward. It leaves an empty projectile heartbeat connection until Stop Play. Its executed result is recorded by the coordinator after integration.
- `CommittedThrowTests` only adds the new dependency stub for its non-Ray cases; committed ordinary throw behavior is unchanged.

Fresh isolated test harness (Studio Edit, HttpService source bridge):

```lua
local H = game:GetService("HttpService")
local base = "http://127.0.0.1:8934/studio-prototype/combat/"
local function read(name) return H:GetAsync(base .. name .. ".luau") end
local T = assert(loadstring(read("RayImpactTests")))()
return T.run(read)
```

For actual physics, install this test source into a temporary ModuleScript on the Play server, require that module and call `T.live()`. Play server loadstring is disabled. No persistent profile services, reward services, or live combat damage callback are used by either test; stopping Play removes its temporary heartbeat and fixtures.
