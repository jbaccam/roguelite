# Straight gunfire correction — October 5, 2026

Gun projectiles commit to one firing line. This covers Glock, Draco, Shotgun, T-Shirt Cannon, Nail Gun/turret, Ray Gun, Rocket Launcher and Fart Gun. Spread still launches separate straight shots; it never bends an individual shot.

## Corrections

- `CharacterStats.StraightGuns` rejects Bounce for guns in both gameplay and the shop's “Works with” filtering. `StatProjectiles` also rejects native gun bounce, so tier data cannot reintroduce ricochets. Existing throw/magic bounce remains available.
- Swept projectiles advance their center by `Spherecast.Distance`, not to `Spherecast.Position` (the contact surface). This prevents grazing contacts from shifting subsequent piercing legs off their original line.
- Client gun tracers retain the server's launch origin. Muzzle flashes still follow the rendered weapon, but the first tracer segment no longer joins a moving client muzzle to a different server path. Ray Gun bolts use the same rule.
- Rocket server/client motion is straight. Rockets no longer weave or redirect/cancel when their original target dies.
- Fart Gun gas projectiles have zero trajectory arc; their poison-zone behavior remains.

## Verification and limits

- `git diff --check` passed for the working tree (only existing line-ending notices).
- Updated `ShopTests` checks gun Bounce incompatibility across every gun ID. Updated `StatProjectileTests` checks no off-axis Glock ricochet, preserves native throwing rebound and verifies every piercing contact/continuation is collinear with its launch.
- **No Studio Play tests ran for this change.** No Studio connection was available during implementation. Integration tests require the parent integration pass in a connected Studio session. Source edits are complete; Studio synchronization and visual verification remain pending.
- No persistent rewards or production DataStores were used.

Suggested Studio review: six mixed guns with high attack speed, Pierce 4 and Bounce 4; walk and turn while shooting close moving targets, including grazing hits. Every individual tracer must remain straight. Separately verify rocket travel after killing its original target and the continued rebound of thrown/magic weapons.
