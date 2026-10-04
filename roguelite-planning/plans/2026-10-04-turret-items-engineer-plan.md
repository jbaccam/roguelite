# Turret items and the Engineer Handyman: implementation plan

Spec: [2026-10-04-turret-items-engineer-design.md](2026-10-04-turret-items-engineer-design.md), including the same-day update (turrets can't be destroyed, Spare Parts and Duct Tape dropped, no new models).

**Goal:** turrets come from shop items, any class can own up to 10, and they are placed automatically on a ring at every wave start. The Handyman is Brotato's Engineer.

**Architecture:** `HandymanTurret.luau` stays the one pure rules module: items, Brotato stat rule, ring maths, caps, Scrap Magnet counting and the Engineer rules. `ShopCatalog` builds the 6 shop entries from it. `ShopService` gets small hooks for prices, offers, caps, the free turret and crystal counts. `HandymanTurretService` turns each player's items into turrets at wave start and fires them at 10 Hz. The client draws any number of turrets per player. No new remotes or modules.

**Rules for this build:** repo only, no Studio, no Play, no git staging. Another agent is editing `CharacterStats`, `ShopService`, `ShopUI`, `CharacterService` and `WeaponCatalog` at the same time, so I use small exact-string Edits only in the first three, and I don't touch the other two. Parse-check every Luau file with `~/.rokit/bin/stylua - < path > /dev/null` from `roguelite-planning/studio-prototype`.

## Tasks

### 1. Rules: `combat/HandymanTurret.luau` (rewrite)
- Keep: `Id`, `Base` (the Nail Gun-like bullet entry, so `CharacterStats.usesStat` applies Two Straws, Pierce and Bounce), `Burst`, `cadence`, `baseDps`, `yaw`, `Icons`, `templates`.
- Remove: BUILD (`Keys`, `BUILD_*`, `canBuild`), upgrades (`UPGRADE_BASE`, `upgradePrice`, `canUpgrade`, `offer`), and all of 9f6e956's health/break/target layer (`HEALTH*`, `maxHealth`, `damageTaken`, `takeHit`, `rebuildAt`, `posts`, `newPost`, `nearer`, `BODY`).
- Add:
  - `Items` / `ItemTier` for the 4 items, plus `SCRAP_MAGNET` and `TOOLBELT`.
  - `MAX_OWNED` 10, `MAX_SERVER` 30.
  - `owned(items)` and `tiers(items)`.
  - `weapon(tier, stats)`: base × (1 + Utility Power), fixed cooldown, range and speed.
  - `turretStats(stats)`: the owner's stats with Damage, Ranged, Attack speed, CDR, Crit, Life steal, Knockback, Range and projectile speed/size zeroed.
  - `band(class)`, `ring(n, band, rng)`, `spot(center, angle, radius, probe)` (fallback: half radius, then the player's position), `spaced(points, min)`.
  - `share(wants, budget)`: round-robin for the 30 cap.
  - `scrapBuilds(crystals, copies, built)`.
  - `Engineer` (class, ring, discount, free item), `priceFactor(class, entry)`, `offerable(entry, owned)`, `favoured(class, carried)`, `describe(tier)`.

### 2. Shop entries: `combat/ShopCatalog.luau`
- Add `turret_nail`, `turret_twin`, `turret_quad` and `turret_gatling`: kind `Turret`, cap 10, `turret=tier`, `structure=true`, `HandymanTurret.Icons[tier]`, prices 24 / 46 / 85 / 150.
- Add `scrap_magnet` (tier 2, 40, the Fridge Magnet icon) and `toolbelt` (tier 1, 18, `{UtilityPower=6}`, the Utility Power level-up icon).
- Tag all six `Structure`.
- Load `HandymanTurret` through `pcall`, so a place without it still loads the catalog.

### 3. Engineer stats: `combat/CharacterStats.luau` (Edit only)
- Handyman entry: drop `Damage=5`, use the new description, and add `gain={UtilityPower=1.25,Damage=.5}`.
- `resolve`: a class `gain` multiplies the positive part of what sets, items, level-ups, skills, armour and pets add to a stat. It does not multiply the base or the class's own buffs.

### 4. Shop hooks: `combat/ShopService.luau` (Edit only)
- Add `offerPrice(p, entry)`: the Engineer's 20% off on structure items. Use it in the forced roll, the normal roll and `reprice`.
- In `fill`, use `HandymanTurret.offerable`: no turret items at 10 owned.
- Add the structure weighting: 15% + `classBonus` for a Handyman, or for a player carrying a Handyman-class weapon.
- In Buy and `adminItem`, refuse at 10 turrets.
- Free Nail Turret: added in `newState` for a Handyman, and kept in step with class changes before wave 1 (onStatsChanged).
- `onShards(p, total, crystals)`: add the crystal count for Scrap Magnet.
- Ignore `UpgradeTurret` quietly, and drop the snapshot's `turret` row.

### 5. Server: `combat/HandymanTurretService.server.luau` (rewrite)
- At each wave key (run:wave:phase), place every player's turrets:
  - share out the 30 cap;
  - reuse the Folders `UserId_n`;
  - ground rays only when placing.
- Mid-wave: add turrets the admin gave, and Scrap Magnet temps at free ring spots. Temps go at the wave's end.
- Fire at 10 Hz from one TargetGrid snapshot, with the Brotato definition (`structure=true`, `slotIndex` 100+n so clients know which turret fired).
- Admin: `Give n` (adds the item through `Shop.adminItem`) and `Clear`. Remove the `BuildTurret` listener.

### 6. Damage path: `combat/CombatEffectsService.luau` (2 one-line hooks)
- A `d.structure` hit never takes the Ninja dodge crit and never life-steals.

### 7. Client: `combat/HandymanTurret.client.luau` (rewrite)
- Draw any number of turrets per owner, matched to their nails by `slotIndex`.
- Remove BUILD (button, keys, layout), the HP bar, the hit flash and the break burst.

### 8. Take 9f6e956's mob hooks back out (Edit only)
- `RogueliteZombieChase.server.luau`: the `Turret` lookup and the `Turret.nearer` line.
- `combat/EnemyAttacks.luau`: `hitTurret`, the melee turret block, the shot's `post`, and the update's `post` branch.
- `combat/ZombieAttacks.luau`: the lookup, the slam loop and the post branch.
- `audio/RogueliteSounds.client.luau`: the break crunch.

### 9. Admin and shop UI
- `AdminConfig`: `Turret` takes `Give` with 1–4, or `Clear`.
- `AdminPanelUI`: Give Nail / Twin / Quad / Gatling and Clear turrets.
- `AdminConfigTests`: add Turret cases.
- `ShopUI`: remove UPGRADE TURRET (Edit only).

### 10. Tests
- `TurretTests(H, TargetGrid, WeaponCatalog, CharacterStats, EconomyConfig, ShopCatalog)` (pure, Studio Edit) covers:
  - item stats and Utility Power scaling;
  - the Brotato rule;
  - the ring: bands, 5-stud spacing for 1–10 turrets, fallback;
  - the 10 / 30 caps and `share`;
  - Scrap Magnet counting;
  - Handyman × 1.25 / × 0.5 and his price;
  - catalog entries;
  - targeting through TargetGrid.
- `ShopTests` (temporary server Script in Play) covers turret items being offered, priced, discounted for a Handyman, capped at 10, the free turret, and the quiet `UpgradeTurret`.

### 11. Docs
- Rewrite `combat/HANDYMAN_TURRET.md` for this version.
- Update the Handyman row in `combat/CHARACTER_STATS.md`.
