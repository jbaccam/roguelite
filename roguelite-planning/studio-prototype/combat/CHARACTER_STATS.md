# Character stats and Studio practice editor

Implemented September 17, 2026. This is the authoritative prototype stat/class implementation; numeric values remain balance tuning. Non-weapon shop passives and purchases are outside this change.

## Controls

- **Stats / Test [P]** opens the character editor; the Stats tab is also available from Inventory and Shop.
- Select one of six classes. Class selection clears manual overrides. Equip class build fills four slots with a suggested loadout; other weapons still work.
- Edit effective stat values with minus/plus or type a value and press Enter. An asterisk marks an override. Reset stat edits restores class and affinity values. Heal and Test 20 contact damage exercise sustain and defenses.
- Zombie buttons change the shared practice target by 1 or 10, from 0 to 100. Z toggles spawning. Changing target replaces the wave; killed enemies return after three seconds. Zero clears it without stale replacements.
- Changes are server validated, rate limited, living-player and Studio Practice only. Nothing awards persistent currency or wins.

## Stats and weapon integration

CharacterStats.luau now defines 46 visible attributes with defaults, caps, descriptions and calculation rules. Shop Discount and Shop Price Modifier are active in the server-owned economy. Purchased passive/utility items contribute bonuses and penalties before debug overrides and safety caps. See the SHOP / ECONOMY SYSTEM section in the master design document.

CharacterService mirrors effective values as `Stat_<id>` on the avatar and its replicated player-state folder. Humanoid MaxHealth and WalkSpeed receive actual values. Armor/contact reduction/dodge/first-hit blocking modify incoming zombie attacks. An empty StarterCharacterScripts.Health prevents Roblox default regeneration from bypassing our regeneration and Recovery rules. Life steal uses actual damage and a per-second healing cap.

All 36 weapons consume general damage, compatible melee/ranged/elemental/utility damage, critical chance/multiplier, attack cadence and range. Elemental and Utility tags come from WeaponCatalog. Projectiles use server swept collision and bounded travel, size, extra shot counts, unique-target piercing and bounces. Added piercing hits multiply damage by 0.7; bounces multiply it by 0.6. Explosives use area and explosion bonuses; piercing/bounce do not apply to explosions. Lightning never recursively triggers itself. Burn/poison/slow have bounded durations and stacking; burn spreading cannot propagate a second generation. Boss/elite damage requires the relevant enemy attribute. Slow and knockback have reduced boss effects.

**Which weapons use the weapon-only stats (2026-10-03).** One rule, `CharacterStats.usesStat`, answers this for the server's launchers (through `CharacterStats.shotStat`), the run shop's offers and the cards' "Works with" line, so they can't disagree.
- Extra shots: guns, staffs, cards, throws that don't come back, rockets, Pandora's Box and the Storm Bow.
- Pierce and bounce: bullets, cards, and throws that aren't fire or gas (Boomerang, Mjolnir and the Trident included).
- None of them: melee swings, the Rubber Duck's spray, the Vacuum and the Power Washer.
- Example: Two Straws gives a Glock 2 bullets and a Frying Pan nothing.
- Lightning and area stats also count your own sources: with Battery Pack, every weapon chains lightning, so Tinfoil Antlers helps them all.

Attack range moves melee reach without rescaling the equipped mesh. Authored model sizes, including the katana scale 0.013698526658117772, are preserved. Projectile Size changes projectile collision/visuals, not the equipped weapon model.

Pickup Radius and Luck apply to rare heart drops (`HeartDropService`, retuned 2026-09-29): 1% per real kill plus Luck × 0.02%, capped at 3%; a heart heals 15 HP before Recovery, is pulled by any living player within max(4, Pickup Radius) (wasted at full health), and expires after 10 s. (The original 15%/8 HP green orb was removed on 2026-09-22.) XP, currency, shop odds and purchases remain deferred. Utility Power applies to existing Handyman weapons. (This change added no summon; since 2026-10-03 the Handyman builds a turret, see Class abilities below.)

## Normalized avatars

`AvatarNormalizer.server.luau` (September 27, 2026) turns off `CharacterAutoLoads` and spawns every character from a sanitized copy of the player's HumanoidDescription. Height, width, depth and head scale are set to 1, and body type and proportion to 0. Body-part meshes are set to 0, so the rig uses classic R15 limbs, with no Rthro, dynamic-head or custom body shapes. Animation-pack IDs are also set to 0, so the default R15 animations play. Layered clothing is removed. Up to four rigid hat, hair or face accessories are kept, along with body colours, classic shirt/pants/T-shirt and face. This keeps armor, shirts, floating weapons and animations on the body proportions they were authored for.

The script also handles respawns after death, using `Players.RespawnTime`. Any character loaded another way (for example a plain `LoadCharacter` in a test) is replaced with a normalized one. Game Settings > Avatar should stay on R15; the script warns if a spawn comes out R6. Studio Play check: no reload loop, H=1, BodyType=0, height 5.5 studs, stats still applied, and correct on first spawn, after a foreign reload and after death. Several different real avatars in a live server have not been tested.

## Classes

Every class retains access to every weapon. Six home weapons belong to each class. Two/four home weapons grant additive affinity bonuses, subject to caps. Duplicate home weapons count toward affinity.

Rebalanced 2026-10-03 so no class is plainly worse: each has 3–4 buffs and 1–3 drawbacks, and a drawback never weakens the class's own weapons (Thrower lost −10% attack speed, Juggler's damage penalty went from −15% to −10%, Handyman lost −2 speed and −5 crit). Gunner's faster ranged attacks are data now (`rangedAttackSpeed`) and shown with its buffs.

| Class | Base buffs | Base drawbacks | 2 home weapons | 4 home weapons (additional) |
| --- | --- | --- | --- | --- |
| Brawler | +25 HP, +3 Armor, +20% melee, +8 knockback | −2 movement speed, −15% ranged | +15% melee, +2 Armor | 5% life steal |
| Gunner | +20% ranged, +35% projectile speed, +5 critical points, +10% ranged attack speed | −15 HP, −15% melee | +1 pierce | +1 projectile |
| Thrower | +25% range, +1 bounce, +15% ranged | −2 Armor, −10% melee | +15% ranged | +1 projectile |
| Juggler | +3 movement speed, +15% attack speed, +12 knockback | −10% general damage | +15% range, +5 knockback | +1 bounce, +15% attack speed |
| Handyman | +5% damage, +15% utility, +20% area, +1 HP/s regeneration | −10 HP | 10% cooldown reduction | +20% utility |
| Mage | +25% elemental, +30% duration, 15% burn chance, +1 chain target | −20 HP, −2 Armor, −10% melee | +15% elemental | +1 burn-spread target |

**Class weapon fit (2026-10-03).** On top of the table, every equipped weapon gets its own damage change from how close its home class is to yours: own class **+15%**, then one number per pair of classes (the same both ways). Godly weapons are unchanged. It stacks with the class stats. Values: `CharacterStats.ClassFit`.

| Your class → weapon's class | Brawler | Gunner | Thrower | Juggler | Handyman | Mage |
| --- | --- | --- | --- | --- | --- | --- |
| Brawler | **+15** | −15 | −5 | −5 | 0 | −10 |
| Gunner | −15 | **+15** | 0 | −5 | 0 | −5 |
| Thrower | −5 | 0 | **+15** | 0 | 0 | −5 |
| Juggler | −5 | −5 | 0 | **+15** | 0 | −5 |
| Handyman | 0 | 0 | 0 | 0 | **+15** | −5 |
| Mage | −10 | −5 | −5 | −5 | −5 | **+15** |

Why: Handyman is handy with anything (0 with everyone but Mage, and everyone can use its tools). Gunner, Thrower and Juggler all fire or toss things. Fists vs guns is the one opposite pair. Mage weapons are the strongest and most specialised, so Mage pays the most outside its own class. Example: a Brawler's Glock takes −15% and the Brawler's −15% ranged, about −28% in total (Brotato's Brawler is −50 ranged, so this is gentler). Where players see it (2026-10-03, shared pieces in `UITheme`: `statColumns`, `homeRows`, `fitTiles`, `fitBadge`, `tag`, `section`):

- **Armory, class details:** Always on (buffs | drawbacks), the 2 / 4 home weapon bonuses, and the class's row as six tiles (each class's starter icon and number, own class framed in lime).
- **Run setup, choosing a class:** the details panel shows buffs | drawbacks and the home weapon bonuses; every class card gets a badge with the number for the picked class. Cards are 140 tall (were 150) so the 470 × 380 panel fits every class without scrolling.
- **Item card (chest odds):** class and type tags under the image, and a "Damage by class" strip (the weapon's column, the loadout's class tagged YOU).
- **Run shop:** the class tag under the name, and a fit bar ("−15%  ·  OFF-CLASS"). Narrow phone cards step down: class only, then an icon tag with the class in the bar.
- Colours everywhere: lime = your class, cream = 0%, reds for −5 / −10 / −15.

Layout checks (Studio Edit, UILayoutAudit, no Play): the item card at 7 screen sizes; the Armory and run-setup panels for all six classes at 1080p, 768p and phone scale; the shop tag and bar at card widths 156–300 and scales 1 / .7 / .55. The full Armory, run-setup and shop screens were not opened in Play. Studio sync, 2026-10-03: CharacterStats, WeaponCatalog, ProfileService, RunSetupRules, RogueliteLobbyPreview (server), UITheme, ArmoryUI, ItemCardUI, RunSetupUI and ShopUI written from commit 0b2b759, each only after checking Studio still held the expected earlier version. No Play test has run on it yet.

These prototype choices supersede the older proposal that classes need no drawbacks. Distinct orbital/return animations and deployables remain separate weapon-kit work; this change applies class statistics to the existing attack styles.

## Class abilities (2026-10-03)

Two classes got an ability from the play-test round. Repo only, syntax-checked: not yet in Studio, not play-tested.

**Melee dash** (play-test: "dash for melee based characters", so melee builds can close in).
- **Who:** Brawlers always; any other class only when its starting weapon is melee, e.g. a Mage who starts with Excalibur (`CharacterStats.dashes`).
- **How:** Q, gamepad X, or the DASH button (bottom right on keyboard and gamepad; beside the jump button on touch). It works on the ground and in the air.
- **Numbers** (`CharacterStats.Dash`): 20 studs in 0.18 s (111 studs/s), then 3 s cooldown. No damage and no invulnerability.
- **Server checks:** the client moves its own body and sends `RunAction 'Dash'`. `RogueliteMeta` approves it (class or starter, cooldown, mid-wave or sandbox, not paused, not held) and stamps `DashAt`. `MovementGuard` then allows 26 extra studs for 1.5 s. For 0.6 s after a dash, enemy hits use the player's seen position up to 20 studs ahead ([HIT_FAIRNESS.md](HIT_FAIRNESS.md#round-4-melee-from-a-jump-and-the-dash-2026-10-03)).

**Handyman turret.** The Handyman builds a nail turret it can upgrade in the run shop (Tier I–IV). B, R1 or the BUILD button moves it. It stays off until its templates are installed. Rules and numbers: [HANDYMAN_TURRET.md](HANDYMAN_TURRET.md). Art: `roguelite-planning/blender-handyman-turret/`. The Handyman's class description now starts "Builds a nail turret you can upgrade."

## Verification

- CharacterStatsTests.luau: **2,283 assertions passed** in an actual server Script during Studio Play, covering all classes/weapons, avatar application, affinity calculations, invalid/nonfinite/fractional inputs, phase and rate rejection, defenses, regeneration, Recovery, life-steal caps, critical/boss damage, status ticks, poison caps, chains, burn spread, reset and healing.
- StatProjectileTests.luau: actual swept-projectile tests passed for piercing and bounce falloff, unique targets, wall occlusion, projectile size, travel speed and rocket splash.
- Actual client controls: class selection changed Gunner HP to 85 and ranged bonus to 20%; Damage plus updated the UI and avatar attribute to 10. A client remote set Damage to 40; malformed requests were exercised separately.
- Zombie target 25 produced 25 enemies; zero cleared them and remained empty after replacement delay.
- Practice health-drop checks passed for Recovery healing and in-range/out-of-range pickup behavior.
- Authored katana scale verified after removing an erroneous ScaleTo call. RPG render fidelity is handled separately by FixRocketMuzzle.luau.
- Rojo combat and root packaging passed. Studio source and repository are synchronized.

Tests execute in the normal server Script context. Requiring stateful modules directly from the Studio assistant execution context gives a separate module cache and cannot inspect the live CharacterService state. Initial test-harness failures were corrected (a status threshold and a test-target folder outside the normal enemy occlusion exclusion).

Multiple real clients, published-game access restrictions, high-latency stress, final class balance, and maximum-population device performance remain unverified. Studio testing does not demonstrate those passed.
