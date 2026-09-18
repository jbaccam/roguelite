# Floating weapon presentation



Confirmed by the user on 2026-09-17 after reviewing six supplied Brotato clips (lightning knife, mixed weapons, punching, rocket launcher, slash/thrust and SMG).



Equipped weapons remain visible as floating 3D models arranged around the player's avatar. The avatar holds no weapon and moves normally. Each weapon independently acquires eligible targets, aims, and automatically attacks according to its range and cooldown. Weapon models perform their own recoil, thrust, punch, swing, or other attack motion, then recover to their floating position. Projectiles originate from the weapon, and attack effects reinforce its movement. The player focuses on movement, positioning, and building their loadout.



- Up to five equipped weapon slots are visible in a spaced formation following the avatar. Each slot may contain the weapon's required pieces, such as paired gloves.

- Aim is independent of avatar facing and movement. Weapons may target different directions and attack asynchronously. Exact target priority is weapon-specific and still needs tuning.

- Weapons occupy assigned floating slots. The formation does not spin 360 degrees around the avatar. Any earlier orbital-weapon concepts must be reconciled with this fixed-slot rule before implementation.

- Start with waist-to-chest-height placement, then visually tune spacing, size and camera readability in 3D. Weapons must not obscure the face or enemy tells.

- Floating fists/gloves punch outward and retract; blades thrust or sweep and recover; guns aim, fire from their muzzle and recoil. The launcher stays near the player while its separate rocket travels outward. Lightning or other effects accompany the weapon's visible action.

- The avatar's limbs do not need attack animations. Server-authoritative hit volumes/timing and projectiles must agree with the visible weapon motion; do not rely on client mesh contacts to award damage.

- This supersedes the older effect-only/invisible-weapon presentation. Weapon skins remain outside the current scope; visibility alone does not approve new cosmetic monetization.



Reference review artifacts and clip metadata are in `video-analysis/`. Original user videos remain at `C:/Users/Jeremiah/Videos/attacks/`.



## Implementation order



1. Import the existing 36 weapon families and required independent components into a dedicated Studio showcase for inspection, preserving rigged chains/lid and separate cards/gloves/rocket/yo-yo pieces.

2. Prototype the katana first using the user-resized play-size display model: fixed right-hand-side floating slot, independent auto-targeting, windup/slash/recovery, server damage, and damage numbers.

3. Tune katana reach, cadence, clearance, and hit feedback; then add a ranged weapon and test mixed asynchronous attacks before expanding to the full roster.



The showcase is asset inspection, not implementation of all attacks.



## Confirmed clearance and test controls — 2026-09-17



Weapon geometry must stay outside the avatar throughout idle, aiming, windup, strike, and recovery. A weapon behind or beside the player must never take a shortcut through the avatar to attack an enemy in front. Use an outward route with clearance or skip an unsafe/unreachable target. The katana prototype protects the entire visible mesh with a capsule around the sword and a clearance cylinder around the avatar. It returns to its assigned slot after each slash, rather than orbiting. Server-confirmed hits show the actual damage amount above the enemy.



Studio test buttons/keys: Zombies [Z] removes the active wave and respawns five when re-enabled; Katana [K] hides the weapon and stops attacks. These are separate toggles. Test controls are Studio-only, grant no persistent rewards, and are validated on the server. See studio-prototype/combat/README.md for prototype tuning and validation.


Katana refinement: fixed idle slot, full-direction target acquisition. It quickly turns/flips toward the target directly from the assigned grip slot. Do not move it around the avatar or to the opposite side before swinging. It returns to the same idle slot; no continuous 360-degree orbit.

Latest correction: a rear target is attacked directly from the right-side slot; no front-of-avatar detour and no move to the left side. This supersedes the earlier attack-repositioning arc.

Katana arrow-reference refinement: front/left attacks sweep right-to-left across the front; rear attacks mirror the sweep behind the avatar. Open the blade outward, perform a fast wide horizontal cut with outward reach, then lift clear before retracting. Keep the assigned right-side slot and avoid routing around the body. Prototype cadence is now 0.58 seconds (0.10 windup, 0.10 strike, 0.18 recovery); 25 damage is unchanged. See combat README for verified reach limitations.

