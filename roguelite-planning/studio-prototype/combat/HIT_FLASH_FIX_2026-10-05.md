**Latest correction:** Ordinary enemy death no longer anchors or retains a corpse for the white flash. ZombieDeath destroys the model immediately after the existing death event/reward/tag cleanup; position-based death bursts and damage numbers continue independently. Surviving enemies still flash. Boss death animation timing is unchanged. A fresh-source Studio Edit lifecycle check verified immediate ordinary removal with zero delayed callbacks, idempotent notifications, untouched living/practice targets, and the preserved 2.9-second boss animation callback. This supersedes the ordinary 0.25-second corpse hold described below.

# White hit flashes — October 5, 2026

Every received server-confirmed hit now flashes the struck mob white, including burn/poison/zone ticks. Damage numbers retain their setting and teammate priority; disabling numbers does not disable flashes. Repeated hits reset the same enemy's pulse. The pulse holds solid white for 80 ms, then fades linearly over 100 ms. Frost tint yields to the flash and resumes afterward.

The old pool retained only ten simultaneous flashes, so large same-frame area hits could evict most targets before a rendered frame. The bounded pool now retains 128, enough for 100 active mobs and some corpse turnover, without descendant scans or per-hit tweens. Roblox currently documents a 255-instance client Highlight limit (including disabled instances), not the previous code comment's 31: https://create.roblox.com/docs/effects/highlighting . Other effects retain the remaining headroom. Hits beyond the pool cap reuse the oldest; this is not an unlimited render guarantee.

Ordinary lethal hits formerly lost their target when ZombieDeath immediately destroyed the model. Death now settles rewards and removes the live tag immediately, disables collision/touch/query, anchors the root, releases the numbered spawn name, and keeps the defeated model for 250 ms before destruction. Server health stays zero, and target selection and simulation exclude it. Boss death timing remains unchanged. This window allows the reliable lethal Hit event to flash its actual model; network/render behavior still needs Studio validation. The client animation script untracks tagged dead mobs but does not remove their mesh.

## Validation actually performed

- Official Luau CLI 0.741 compiled HitFeedbackVisuals, HitFeedbackTests, ZombieDeath and RogueliteCombat.client successfully.
- Existing HitFeedbackTests extended and executed offline with engine service stubs: **246 assertions passed**, including 100 distinct same-frame hits, repeat-target reuse, pool bound and white-hold/fade timing.
- Actual ZombieDeath module executed offline with minimal service/model stubs: **6 lifecycle assertions passed** covering immediate rewards/tag removal, inert retained corpse, released spawn name, duplicate-death idempotency and bounded cleanup.
- **No Studio Edit or Play tests ran. No Studio scripts were synchronized in this task because no Studio connection was available.** Render legibility, lethal-event replication ordering, low-end device cost and multi-client 100-mob combat remain unverified.
