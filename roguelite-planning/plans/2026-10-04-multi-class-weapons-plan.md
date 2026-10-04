# Multi-class weapons: implementation plan

> For agentic workers: execute task by task (superpowers:executing-plans). Repo only: no Studio, no Play, no git add/commit. The coordinator tests, syncs Studio and commits.

**Goal:** every non-Godly weapon lists 1-3 classes (spec: `2026-10-04-multi-class-weapons-design.md`); fit, set bonuses, class flags, starters and shop weighting read the list; the UI shows every class.

**Architecture:** `WeaponCatalog` owns the data (`d.classes`, with `d.home = d.classes[1]` kept as the alias for untouched code) and two helpers, `C.inClass(w, class)` and `C.classNames(w)`. `CharacterStats.classFit` takes the best fit over the list (it also accepts a bare `{home=}` table, which the class screens pass). `RunSetupRules.classWeapons(class)` replaces `homeWeapons` for starters, and `validLoadout` (the one server check every lobby/match path calls) uses `inClass`. No new remotes or runtime modules.

**Tech:** Luau, Rojo overlay `combat/default.project.json`. Syntax check per file: from `roguelite-planning/studio-prototype`, `~/.rokit/bin/stylua - < path > /dev/null`.

**Shared files (another agent builds turret items now):** `CharacterStats`, `ShopService`, `ShopUI` (and to be safe `CharacterService`, `ui/README.md`): small exact-string Edits only, re-read and retry on a failed Edit.

---

## Class table deviation (decided before Task 1)

The spec's rule is "`classes[1]` is today's home", but four rows of its table use the homes from before the 2026-10-03 Brawler <-> Juggler swap (Boxing Gloves <-> Spatula, Cinder Block <-> Kusarigama). Today: Kusarigama and Spatula are Juggler, Boxing Gloves and Cinder Block are Brawler. Apply the same swap to those four rows so `classes[1]` stays today's home:

| Weapon | Spec row | Built |
|---|---|---|
| Kusarigama | Brawler, Thrower | Juggler, Thrower |
| Spatula | Brawler, Handyman | Juggler, Handyman |
| Boxing Gloves | Juggler, Brawler | Brawler, Juggler |
| Cinder Block | Juggler, Handyman | Brawler, Handyman |

Totals become Brawler 9, Gunner 7, Thrower 11, Juggler 10, Handyman 9, Mage 8 (spec: Brawler 10, Juggler 9). The largest list is still 11 (Thrower).

## Task 1: WeaponCatalog data and helpers

**Files:** modify `studio-prototype/combat/WeaponCatalog.luau` (home derivation ~line 222, flags ~240, `describe` ~188).

- [ ] Add `C.ClassesById` (id -> list) for the 30 multi/single rows above; set `d.classes = C.ClassesById[d.id] or {d.home}` after `HOME_MOVED`, assert `d.classes[1] == d.home`, then `d.home = d.classes[1]`. Godly: `d.classes = {}`, `home = 'Godly'` as today.
- [ ] `function C.inClass(w, class)`: true when `class` is in `w.classes or {w.home}`; Godly never.
- [ ] `function C.classNames(w, sep)`: `'Thrower and Juggler'` (or joined by `sep`).
- [ ] `d.elemental = C.inClass(d,'Mage') or ...`, `d.utility = C.inClass(d,'Handyman')`; tags get every class.
- [ ] `describe`: "Home weapon of the Thrower and Juggler classes."
- [ ] stylua parse check.

## Task 2: CharacterStats fit rule (shared file: Edit only)

**Files:** `studio-prototype/combat/CharacterStats.luau` `S.classFit` (~line 100) and its comment.

- [ ] Loop `base.classes or {base.home}`, own class = `S.ClassFit.Own`, else `row[c]`; keep the best. Return `fit, pct, via` (via = the class that gave it; callers ignore the third value). Unknown class keeps today's `'similar', 0`.
- [ ] Add `S.inClass(base, class)` with the same list fallback, for CharacterService (it needs no catalog lookup for `{home=}` tables).
- [ ] Example in the comment: a Gunner with the Nail Gun (Handyman, Gunner) gets +15%, was 0.

## Task 3: Server rules

**Files:** `lobby/RunSetupRules.luau` (`homeWeapons` line 111, `validLoadout` line 134), `combat/CharacterService.luau` line 120, `combat/ShopService.luau` `choose()` lines 155-166.

- [ ] `R.classWeapons(class)`: every weapon with the class anywhere in its list. Keep `R.homeWeapons` as an alias (old callers, `SyncGodlyRuntime` patches).
- [ ] `validLoadout`: `if not w or (not Weapons.inClass(w,class) and not w.godly) ...`. Every lobby/match fallback already calls it, so a saved starter that no longer fits drops to the signature.
- [ ] CharacterService set count: `Stats.inClass(d, s.class)`.
- [ ] ShopService: collect the classes of every carried weapon; `sameClass` = pool weapons sharing any of them.

## Task 4: Run setup UI

**Files:** `ui/RunSetupUI.luau` (`drawClass`, lines 232-374).

- [ ] List = class weapons, owned first (catalog order), then owned Godlies, then NOT OWNED.
- [ ] `pick`: `sel.weapon` only if it is owned and in the list (or an owned Godly), else the signature.
- [ ] Desktop grid always goes into a `Weapons` column (scroll when rows > 2); compact already does. Rows = ceil(n / cols).
- [ ] Layout test `ui/RunSetupLayoutTests.luau` (client, like `ShopLayoutTests`): own RunSetupUI instance, a fake profile owning Thrower and 7 of its 11 weapons, Loadout mode, sizes 2560x1440 .. 667x375 by resizing `RunSetup.Root`; checks the grid scrolls, holds 11 cells, owned before NOT OWNED, and is disjoint from ClassInfo, Back, Primary.

## Task 5: Armory, item card, shop label

**Files:** `ui/ArmoryUI.luau` (describe ~200, `loadout()` ~373, weapon grid ~774-828, detail ~1074/1103-1163), `ui/ItemCardUI.luau` (~376-474), `ui/ShopUI.luau` `classFitRow` (~326-341, Edit only), `ui/LobbyUI.luau` line 88.

- [ ] Armory MY CLASS: every weapon in the class list. All classes: your class first, then each weapon once under its first class.
- [ ] Armory detail sub line `RARE · THROWER · JUGGLER · RANGED`; EQUIP keeps your class when it is in the list, else the first owned class in the list; note "Starts runs as a Thrower or Juggler."
- [ ] ItemCard: one class tag with every class (first class's icon); fit tiles `own` = in the list.
- [ ] ShopUI: tag `THROWER · JUGGLER · RANGED`, steps down to classes only, then the best-fit class, then icon only; icon = best-fit class's starter.

## Task 6: Tests

- [ ] `CharacterStatsTests`: class totals table (9/7/11/10/9/8), signature in its class, fit = best over the list (symmetric pair check per listed class), Nail Gun as Gunner = +15%, set count with multi-class weapons (Kusarigama counts for Juggler and Thrower: `Service.refresh` AffinityCount).
- [ ] `WeaponBalanceTests`: every non-Godly weapon has 1-3 distinct known classes, `classes[1] == home`, old-home table (`OLD_HOME`) matches, Godly have none; utility = Handyman in list (Spatula, Cinder Block, Rocket).
- [ ] `ShopTests`: with only a Kusarigama carried, the `sameClass` pool includes a Thrower-only weapon (Kunai) and a Juggler-only one (Yo-Yo), not a Mage-only one; exposed as `Shop.sameClassPool` (test hook like `offerableWeapons`).

## Task 7: Docs

- [ ] `combat/CHARACTER_STATS.md`: class section (counts, list rule, fit = best match) and the table note.
- [ ] `CURRENT_GAME_STRUCTURE.md` §4: classes list weapons, any owned weapon in the list can start, the table.
- [ ] `ui/README.md`: a short dated 2026-10-04 note.

## Verification (coordinator, Studio)

Run `WeaponBalanceTests` (Edit), `CharacterStatsTests` and `ShopTests` (Play server Script), `RunSetupLayoutTests` (Play client, lobby). Play-test checklist in the hand-off.
