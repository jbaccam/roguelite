# October 4 combat feedback corrections

Source changes below address the squad play-test feedback. The integration report records Studio synchronization and subsequent Play sessions. Verification here includes isolated Studio Edit regressions and the October 4 single-client production-combat fixture below; it is not a four-player balance claim.

- Rocket Launcher: base range 55 → 34 studs, speed 80 → 46, explosion radius 9 → 6. Tier IV mini rockets slow to 42, use radius 4 and 40% damage each. Base rocket damage and cadence remain unchanged.
- Kusarigama: authored damage 17 → 16 and cooldown 1.15 → 1.22 seconds, retaining its reach. Paint Roller now always applies 30% slow for 2 seconds through the existing authoritative status path; its description uses the same values.
- Bowling Ball: range 27 → 36. The first feedback pass raised speed to 46; the follow-up lowers it to **28 studs/s** for a deliberate roll. Shared `GroundContact` probes reject player/enemy bodies and untagged lobby dummies, so the ball cannot ride a dummy's head. Server sweep radius and client model scale use the same template bounds, projectile-size stat and pivot-center offset; rotation follows distance/radius. Spherecast contact positions never move the ball's center into the floor. Enemy contacts continue down the lane; damage falls by 30% per hit to a 20% floor, at most 24 enemies per ball. Walls, missing ground and range still stop the roll. No client hit claims are accepted.
- Thrown accuracy: Bowling Pin speed 24 → 40 and arc height 5 → 2; Molotov speed 28 → 38 and arc height 5 → 3; Egg speed 35 → 40. Existing launch-delay-aware intercept prediction remains in charge. Pandora's speed is 58 with a lower, shorter mortar flight. All Pandora flights keep their launch-time landing point, and straight projectiles (including Medusa) keep their heading when targets move/die/disappear. Ordinary throw visuals use the server path without inventory-slot offset easing. Abrupt movement can still evade a throw. Actual contact ricochets, returning weapons and magical cards retain their intended behavior.
- Vacuum: one stream owns an enemy's bounded pull at a time, while all eligible streams can damage it. This prevents different players overwriting the same enemy's velocity toward opposing points. Hold/escape immunity and boss resistance remain. Pulling stops while paused/downed. `VacuumVisuals` replaces the straight fan lines with a soft tapering funnel: three rotating, incomplete curved wind rings move inward, with twelve motes accelerating into the nozzle. The nine beams and twelve motes are reused; live clients pool at most twelve funnels. The same isolated renderer supports the weapon showcase.
- Egg: the imported chicken model was absent, so successful hatch rolls silently produced nothing. The imported asset remains preferred; a self-contained articulated cream chicken now supplies the six joints expected by the existing waddle/wing/peck animator. It includes feet, wing feathers, comb and a humorous face. Hatch chance remains 1/8 at all tiers, lifetime 8 seconds, per-player limit 3 and server limit 24. Ground probes exclude actors, contact/expiry cannot double hatch, and paused/delayed pecks revalidate ownership and line of sight. See `EGG_CHICKEN.md` for the exact behavior and live-check recipe.
- Rubber Duck fire: one short-lived continuous particle nozzle per owner/slot replaces dozens of moving Parts with individual Fire instances. It follows the moving duck and eases its direction between attacks.
- Yo-Yo: both cancellation and lost terminal messages now send the return visual its terminal transition; timeout also retracts before restoring the resting disc.
- Deck of Cards: authoritative damage keeps its existing projectile cap. Each client draws at most 96 curved projectiles; detailed card clones have a 48 cap for the owner and an 18 threshold for teammates, with simple single-part cards beyond that. Far teammate launches are culled. Detailed trails are omitted from simple cards. Arc launch/redirect traffic uses the existing nearby-recipient policy.
- Turrets: the placement anchor projects an edge/corner player into the arena interior (26 studs of margin) at the map's floor height. Ground checks no longer use the player's jump height. Invalid probes defer placement rather than fabricating a floor at airborne player feet. Mid-wave additions share the same checks.
- Multiplayer pressure: population factors become 1 / 1.9 / 2.7 / 3.4, still capped at 100 enemies. A four-player wave 1 aims for 33 and wave 5 for 82. Replacements wait 0.35 seconds, gather at most 0.65 seconds, then retain the full spawn warning. Swarms alternate through living run members; smaller 12-enemy swarms arrive 0.2 seconds apart.
- Bosses: wave 10 brings the map boss at 35% of its wave-20 health and 75% damage. It is marked `Midboss` and the existing boss hold keeps the wave open. Tutorials keep their own schedule. Hammer Brute slam radius grows 9.5 → 12.5, sweeps 3.2/4 → 4.3/5.2, and cracks cover all four players with a longer 0.95-second warning. The legacy Hammer's shared slam radius is also 12.5. Multiplayer HP scaling is in `RunSetupRules` (integrator-owned).
- Weapon telemetry: actual non-practice damage and kills accrue to the equipped copy's `CopyId`; delayed hits cannot credit a same-ID replacement. Replication batches at four updates a second. `CombatEffectsService.flushWeaponStats()` must run before shop snapshots or inventory mutations; `RunDamage`/`RunKills` follow copies when sold/combined/reset in `ShopService`.

## Verification actually run

Roblox Studio MCP, roguelite place `107877054949326`, **Edit** data model, fresh source over the local HTTP bridge:

- Syntax compilation: all 24 combat-owned changed Luau files passed (initial extra `end` in the new flame effect was fixed before the successful pass).
- `EnemySchedulerTests`: **187,201** checks passed.
- `BulletFlightTests`: **21** checks passed, including cancellation and lost-message terminal transitions.
- `TurretTests`: **2,222** checks passed, including the no-ground rejection and a jumping corner player's ground-level interior anchor.
- `WeaponBalanceTests`: **1,768** checks passed using fresh catalog/stat/turret/shop dependencies.
- `CommittedThrowTests`: **1,714** checks passed in the integrator's fresh Studio Edit harness after the follow-up, covering fixed aim, target loss and server/client path agreement for arcs, ordinary modeled throws and straight projectiles, exactly-once egg landing when contact and range expiry coincide, and no per-heartbeat retry after an injected hatch exception.
- `GroundedWeaponsTests`: **140** checks passed in the integrator's fresh Studio Edit harness. Tests use a fake raycast world and temporary Instances outside the DataModel: dummy rejection, floor/step/cliff rules, actual mesh radius/pivot/scale agreement, complete chicken rig, and pooled curved/inward vacuum visuals.
- `git diff --check` passed for this combat change set.

These Edit checks did not start Play, award rewards, or write DataStores. The later actual Play check is recorded separately below. Sloped terrain, frame time with 24 card weapons, four-player wave density and time-to-kill still need multiplayer measurement.

`CombatFeedbackPlayQA.luau` and `CombatFeedbackCameraQA.luau` are unmapped temporary Play fixtures for the integration pass. The server fixture uses the production throw/chicken/utility factories, an isolated synthetic owner and test damage callback, actual weapon templates and physics, and the existing client's production FX listeners. The three lanes demonstrate an elevated bowling release over an untagged dummy, deterministic egg hatch/walk/peck/expiry, and the suction funnel. It changes no player inventory or persistent rewards. Geometry and camera restore automatically; stop Play afterward to release the factories' normal session-long Heartbeat subscriptions. The file headers contain the exact invocation and measurable attributes. The integration report must record whether these fixtures actually ran.

### Actual single-client Play fixture (October 4 follow-up)

The integrator ran a fresh **55-second** fixture after syncing the final modules, then stopped Play. The fixture used production `SpecialWeapons`, `EggChickens` and `UtilityWeapons`, actual physics/templates and the normal client FX receivers. The first attempt caught `Humanoid.DisplayDistanceType` requiring `AvatarAppearance`; the fallback no longer writes either display-appearance property, and a completed egg now leaves the flight table before optional hatch work. The fresh run reported an empty console and these measurements:

| Measurement | Observed |
|---|---:|
| Bowling launch center above floor | 0.893326 studs |
| Ball collision radius sent to the client | 0.833333 studs |
| Ball hits through the lane | 27 |
| Fallback chicken hatches | 34 |
| Chicken pecks | 185 |
| Maximum chicken travel | 5.19 studs |
| Maximum active chickens for the fixture owner | 3 |
| Vacuum damage ticks landing | 274 |

The ball's center clearance equals its radius plus the intended 0.06-stud floor gap, despite the untagged dummy under its elevated release point. The active-cap, fallback model, walking and pecking paths were observed. At the 52-second sample one chicken remained; the last egg had landed after throws stopped at 45 seconds. Geometry cleanup completed at 55 seconds and Play was stopped. **The last chicken's natural 8-second expiry was not sampled at its deadline**, so cleanup is not claimed as proof of that final natural expiry. The existing server expiry rule remains 8 seconds plus the 0.35-second pop. `WeaponBalanceTests` also passed **1,768** checks against the real synced server modules.

## Suggestions distinguished from existing bugs

The authoritative six-class roster has no Herbalist or raid/clanker mode. No implementation was invented from those isolated names. The concrete masonry concept already exists as Cinder Block. Couch Cushion is currently explicitly an armor/max-health passive (+1 armor, +6 HP); the short “just a shield” note does not define a replacement mechanic. Cursed items likewise need a specific mechanic rather than an unreviewed new economy or mode.
