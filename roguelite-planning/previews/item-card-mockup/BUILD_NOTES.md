# Item card: how it would be built

These notes go with `index.html` (the mockup). Nothing here has been built yet, and no game code was changed.

## What it is

- Every item cell in the chest odds overlay (`ChestScreenUI.openOdds`) becomes a button.
- The pet cells on the egg card (`EggScreenUI.drawCard`) become buttons too.
- Tapping one opens an **item card** on top. The card shows:
  - the big icon, the rarity and the kind;
  - whether you own it, and at what tier;
  - the chance to get it from that chest or egg;
  - the special in plain words;
  - a table of the numbers at Tier I–IV;
  - what it costs to unlock and upgrade.
- To close it: X, BACK, B / Esc, or a tap outside. The ◀ ▶ buttons (LB / RB on a gamepad) walk through the same list without closing the card.

## Modules

- **New `ui/ItemCardUI.luau` → `ReplicatedStorage.ItemCardUI`**
  - A client presentation module, mapped in `combat/default.project.json` next to `ChestScreenUI`.
  - Before installing, copy ChestScreenUI's `Sandboxed` and Capabilities settings in Studio (the project rule for new modules).
  - API:
    - `ItemCard.open(canvas, L, {id, source = 'chest' | 'egg', chest = 'Legendary', list = {ids in display order}, profile = opts.profile, onClose})`
    - It returns `{Root, Close, Show(id)}`.
  - It draws into the caller's `T.canvas` canvas, so it uses the same single scale as the rest of the screen.
- **New `ui/ItemDetail.luau`: the Armory's detail pieces, moved out of `ArmoryUI.luau` so both screens use one copy.**
  - Pieces moved: `header`, `statRow`, `weaponAt`, `fmtRate`, `describe`, `rarityTag`, `tierGains`, `tick`, `armorView`, `petView`, `setText`.
  - ArmoryUI keeps its layout and only requires them. Its output is unchanged.
  - This is the "reuse the Armory's detail layout" part. The card is a wider Armory detail panel:
    - the same header pieces (icon well, tier badge, name, rarity line);
    - the same stat rows, extended to four tier columns;
    - the same copies bar (`T.upgradeBar`) and the same ChestConfig upgrade costs.
- **`ChestScreenUI.openOdds`**
  - Each cell becomes a `TextButton` (`AutoButtonColor = false`, `Selectable = true`).
  - Each cell gets a 23 px **i** badge in its top-right corner.
  - `Activated` opens the card for the `odds` entry (`{id, rarity, chance}`).
  - The help line reads "Click/Tap any item to see its stats…", switching on `UserInputService.LastInputTypeChanged`.
  - With a gamepad, the help line shows the selected item's name, rarity and chance, with the A / B hints (`SelectionGained` on each cell).
- **`EggScreenUI.drawCard`**: the same button treatment for the pet cells (`source = 'egg'`, chances from `EggConfig.odds()`).

## Numbers are read, never typed

The card only formats what the modules return. The mockup's `data.json` was made by running these exact modules.

| On the card | Read from |
|---|---|
| Chance from this chest (0.2%, 9.1%) | the `odds` entry the cell was drawn from: `ChestConfig.odds(kind)` |
| Pity line | `ChestConfig.GodlyPity` / `LegendaryPity` |
| "only in this chest" | `ArmorCatalog.Sets[].chests` |
| Pet chance and egg price | `EggConfig.odds()`, `EggConfig.Emeralds` |
| Damage / attacks per sec / range by tier | `WeaponCatalog.ById[id]`: `tierDamage[t]`, `1 / (cooldown × tierCooldown[t])`, `range` (the Armory's `weaponAt` and `fmtRate`) |
| Godly special and its per-tier rows | `WeaponCatalog.Godly[id]` (what `GodlyWeapons` runs on), read per tier like `GodlyWeapons.tierValue` |
| Legendary Tier IV move | `WeaponCatalog.Legendary[id]` / `WeaponCatalog.legendaryMove(id, 4)` |
| Armor set bonus text | `CharacterStats.ArmorSets[set].text` |
| Armor bonus by tier | `CharacterStats.armorBonus(wearing, tiers)`, with all four pieces worn at tier t (two pieces for the 2-piece row) |
| Pet ability | `PetConfig.effectText(id, tier)`, `PetConfig.stats(id, tier)`, `PetConfig.damage(id, tier, 1)`, `PetConfig.TierMult` |
| Unlock / upgrade cost | `ChestConfig.upgradeCost(id, tier)`, `ChestConfig.upgradeEmeralds(id, tier)` |
| Colours | `ChestConfig.RarityColor`, `UITheme.Color / Tier / TierFill` |

### Small data additions (pure functions next to the numbers, like `PetConfig.effectText`)

- **`WeaponCatalog.godlyText(id, tier)`** builds the special's sentence from `C.Godly[id]`.
  - Example: Vampire Blade: "Every hit heals you for 8% of its damage. Every kill sends a blood wisp back to you that heals 2 HP."
  - It replaces the hand-typed `GODLY_TEXT` table in ArmoryUI, which has no numbers and can drift from the table.
- **`WeaponCatalog.GodlyRows`** holds the per-tier rows (label, field, format), e.g. `{'Heal per hit', 'leech', 'percent'}`.
- **`WeaponCatalog.legendaryText(id)`** builds the Tier IV move sentence from `C.Legendary[id]`.
- **`CharacterStats.PerkLabels`** gives names for the perk keys (`PhoenixBlast = 'Rise blast damage'`, `RageAttackSpeed`, `FireThorns`, `DodgeCrit`).
  - ArmoryUI's fallback `ARMOR_TEXT` can then be deleted. It is already unused, and its Iron line disagrees with CharacterStats.
- **Tests (in `ChestConfigTests` or a new `ItemCardTests`)**:
  - Every id in `ChestConfig.odds(kind)`, for every chest, and every id in `EggConfig.odds()`, builds a card model with a name, an icon and four values per row.
  - `godlyText` contains its numbers and never "nil".
  - The card's chance equals the odds entry's chance.

The mockup builds these sentences with the same templates in `index.html` (`godlyText`, `moveText`); the build moves them into the modules.

## Ownership and tier

- **Weapons**: `profile.weapons[id]` (the LobbyUI profile parse of `ProfileWeapons`), giving `{tier, have}`. For one-off lookups, `CharacterStats.ownedTier(player:GetAttribute('ProfileWeapons'), id)`.
- **Armor**: `profile.armor[id]` (`ProfileArmor`, `CharacterStats.parseArmorTiers`). "Your set n / 4" counts `profile.armor[set..'.'..slot]`.
- **Pets**: `profile.pets[id]` (`ProfilePets`, `PetConfig.parse`).
- **Redraws**: ChestScreenUI already redraws on `ProfileChests`/`ProfileGems`. The card also redraws on `ProfileWeapons`, `ProfileArmor` and `ProfilePets` (for example, a chest opened in another window).
- **What the card shows**:
  - Owned: "YOU OWN IT · TIER n", the tier badge on the icon, and the owned column outlined in lime with a YOU tag.
  - Below the table, copies toward the next tier: `T.upgradeBar(have, need)` plus the emerald cost.
  - Not owned: "NOT OWNED YET", the padlock, and "1 copy unlocks it" in the table.

## Layout (one canvas, every screen size)

- The card is drawn on the chest/egg screen's canvas (`T.canvas`), above the odds overlay: ZIndex 50+ (the overlay uses 40–45).
- **PC (canvas ≥ 900 tall)**: a 1240 × 800 card, centred.
  - The hero column is 430 wide (icon well 384 tall).
  - The right column holds the special, a 4-tier table with 48 px rows, the copies line, and the ◀ ▶ / BACK row (70 tall).
- **Phones (`L.h < 900`, e.g. 844×390 → 1500×738 at `T.READABLE_SCALE` 0.5)**: a 1440 × (L.h − 12 − top) card.
  - The hero column is 320 wide.
  - The ◀ ▶ buttons move under the hero, and the copies line moves beside BACK.
  - All buttons are `L.tap` (88 canvas = 44 screen px). All text is ≥ 20 canvas px (≥ 10 screen px; the mockup measured a minimum of 10 px).
- The card's top respects the top bar: `top = max(L.top + 40, 60)`, the same rule as the odds panel. Its title plate pokes 34 px above.
- On resize, redraw the card with the same id, the way `relayout()` already reopens the odds overlay from its `Chest` attribute.
- Before landing it, run `UILayoutAudit.sweep(PlayerGui.ChestScreen.Root)` with the card open at every size.

## Input: touch, mouse, gamepad, Back

- **Touch and mouse**:
  - The cell is the tap target (96 canvas px, 48 screen px on phones).
  - Pressed feedback on `InputBegan`/`InputEnded`: `UIScale` 0.93, a brighter fill and a white `UIStroke`.
  - The full-screen shade behind the card is a `TextButton` (`Active = true`, `AuditIgnore`), so a tap outside closes the card and never reaches the overlay.
- **Gamepad**:
  - The odds panel already gets `T.gamepadSelect(p)`.
  - Give each cell a lime selection ring (`SelectionImageObject`: one shared ring frame from UITheme). Roblox's default ring is hard to see on the coloured cells.
  - The ScrollingFrame scrolls to the selected cell by itself.
  - When the card opens, select BACK. **B** closes the card and puts `GuiService.SelectedObject` back on the cell that opened it.
  - **LB / RB** (`ButtonL1` / `ButtonR1`) and the ← / → keys step through the list. The d-pad stays free for moving between BACK and the arrows.
- **Back order** (extends ChestScreenUI's existing Escape/ButtonB handler): card → odds overlay → results → screen. EggScreenUI gets the same "card first" step.

## Icons

- **Hero icon**:
  - Weapons: `WeaponInventoryUI.Icons[id]` (Godly icons come from `IconsByName`).
  - Armor: `Armor.Icons[id]`, falling back to ArmoryUI's `armorView`.
  - Pets: `Pets.Icons[id]`, falling back to `petView`.
- **Stat icons**: `ui/assets/upgrades` (Damage, AttackSpeed, AttackRange, LifeSteal, Regeneration, ElementalDamage, MaxHP) and `hud/revive.png`. They need asset ids in UITheme (the level-up screen already uses them).
- **Missing**: one icon per Legendary Tier IV move (7: flying slash, mini rockets, Royal Flush, STRIKE!, shockwave, beam slash, lightning strike). Until they exist, the card can show the weapon's own icon there.
- **Gamepad glyphs**: from `UserInputService:GetImageForKeyCode`, so the right controller's art shows.

## Checks for the build

- **In Studio Edit, through `tools/FreshRequire`, no Play**:
  - The card model for every odds id of every chest and every pet.
  - `UILayoutAudit` at 1920×1080, 1366×768, 1280×720, 1024×768, 844×390, 667×375 and 750×369.
- **In Play (ask first; the user play-tests himself)**:
  - Open the Legendary Chest odds and tap a Godly, a Legendary, an armor piece and a Common.
  - Check ◀ ▶ / LB RB, B / Esc / X / BACK / tap outside, and that selection returns to the cell.
  - Check that the owned tier updates after opening a chest.
- **Needs a real phone and a controller** (not testable here): touch targets under the thumb, and the selection ring on a real gamepad.
