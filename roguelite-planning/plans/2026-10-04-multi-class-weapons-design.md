# Weapons belong to one or more classes: design

Approved 2026-10-04 in chat. The user: "make sure every weapon belongs to classes ... weapons can belong to many classes if it makes sense, just like Brotato. We shouldn't limit it to just 6 starting weapons."

## 1. Class list per weapon

Each non-Godly weapon gets `classes`, a list whose first entry is today's `home`. `home` stays as an alias of `classes[1]` for old code.

| Weapon | Classes |
|---|---|
| Glock | Gunner |
| Frying Pan | Brawler |
| Nunchucks | Brawler |
| Katana | Brawler |
| Kusarigama | Brawler, Thrower |
| Spatula | Brawler, Handyman |
| Baseball Bat | Brawler |
| Draco | Gunner |
| Fart Gun | Gunner, Mage |
| Shotgun | Gunner |
| T-Shirt Cannon | Gunner, Thrower |
| Rocket Launcher | Gunner, Handyman |
| Boomerang | Thrower, Juggler |
| Kunai | Thrower |
| Molotov | Thrower, Mage |
| Egg | Thrower, Juggler |
| Steak | Thrower |
| Rubber Duck | Juggler, Thrower |
| Deck of Cards | Thrower, Juggler |
| Boxing Gloves | Juggler, Brawler |
| Cinder Block | Juggler, Handyman |
| Yo-Yo | Juggler |
| Bowling Ball | Juggler, Thrower |
| Bowling Pin | Juggler, Brawler |
| Nail Gun | Handyman, Gunner |
| Wrecking Ball | Handyman |
| Shovel | Handyman, Brawler |
| Paint Roller | Handyman |
| Vacuum Cleaner | Handyman |
| Power Washer | Handyman |
| Magic Staff | Mage |
| Mjolnir | Mage, Thrower |
| Excalibur | Mage, Brawler |
| Pandora's Box | Mage |
| Medusa's Head | Mage |
| Crystal Ball | Mage |

Class totals:

| Class | Weapons |
|---|---|
| Brawler | 10 |
| Gunner | 7 |
| Thrower | 11 |
| Juggler | 9 |
| Handyman | 9 |
| Mage | 8 |

Godly weapons (Reaper's Scythe, Poseidon's Trident, Storm Bow, Shadow Daggers, Vampire Blade, Ray Gun) stay class-neutral, as today ("Godly: no change").

## 2. Rules

- **Class fit** (the +15% / 0 / −5 / −10 / −15 damage badges, `CharacterStats.ClassFit`): a weapon uses the best fit among its classes for your class. Example: a Gunner with the Nail Gun (Handyman, Gunner) gets +15%, where today it's 0.
- **Set bonuses** ("2 / 4 home weapons"): a weapon counts for every class in its list.
- **Class-specific stats:** stats that check a weapon's class, such as Utility Power and the "utility" flag (the `utilityKills` quest), apply when the class is anywhere in the list. Example: Spatula and Cinder Block now take Utility Power.
- **Starting weapon:** a class may start with any weapon the player owns whose list includes that class. There is no cap of 6. Godly starters keep today's rules. A saved starter that no longer fits the chosen class falls back to the class's signature weapon.
- **Shop weighting:** the "same class" weighting matches a weapon that shares any class with the player's.
- **Class unlocks, tutorial and analytics:** unchanged unless they key off `home`. Where they do, check whether the list is the right rule.

## 3. UI

- **Class select (`RunSetupUI`):**
  - The STARTING WEAPON grid lists every weapon in the class: owned ones first, then NOT OWNED.
  - It scrolls when it has more than 6 entries, on every screen size including phones.
  - The "WEAPON DAMAGE AS A GUNNER" chips are unchanged.
- **Weapon cards:**
  - The shop detail popup, Armory and item cards show every class, e.g. "THROWER · JUGGLER · RANGED".
  - The fit badge uses the best fit.
- **Armory class filter (MY CLASS):** matches any class in the list.

## 4. Tests

- `WeaponBalanceTests` / `CharacterStatsTests`:
  - every non-Godly weapon has 1–3 classes, and `classes[1]` equals the old home
  - the best-fit rule
  - set counting with multi-class weapons
- `ShopTests`: same-class weighting by any shared class.
- A RunSetupUI layout check that the starting grid scrolls with 11 entries.
