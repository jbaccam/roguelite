# Armory information-card navigation — October 6, 2026

Armory information arrows previously received raw `WeaponCatalog.List` order, while the visible grid groups Godlies, the selected class, then other classes, with owned weapons first within each class. This caused arrows to jump between unrelated classes and rarities.

Armory now records the exact sequence of weapon tiles as they render and passes that sequence to `ItemCardUI`. Arrows follow the visible grid, respect the current class filter and wrap at its ends. A details item outside the current grid opens as a single-item card. The collection-only rarity-relative footer counter is removed; rarity badges remain. Chest/egg card presentation is unchanged.

## Verification

`ArmoryNavigationTests.py` passed with the official Luau CLI using extracted production selection and arrow logic: mixed-rarity display order, forward/reverse wrapping, filtered lists and non-grid fallback. Edited Luau files compile; whitespace checks passed.

`ArmoryExperienceTests.luau` now independently reads rendered tile positions at desktop and phone sizes, traverses each card in that order, checks both wrap directions, verifies the footer counter is absent and the rarity badge remains. Those new actual-client assertions were added but not executed by the implementation agent. Parent integration owns Studio synchronization and runtime verification.

## Desktop size-jump investigation (recommendation only)

Current shared sizing caps are canvas scale 2, ordinary windows 1.15 and large windows 1.3. Armory uses the shared canvas; its own opening animation slides panels and does not scale the root.

`RunSetupUI.Open` tweens the same layout-owned `UIScale` from 94% to a captured scale over 0.16 seconds. `UITheme.window` similarly tweens its fit-owned scale from 92% over 0.14 seconds. Meanwhile `T.canvas` can initially use camera viewport dimensions before `root.AbsoluteSize` settles, then relayout with actual safe-area dimensions. A live opening tween can subsequently overwrite a newer layout scale with its older target. This is a source-identified race, not a reproduced screenshot diagnosis.

Recommended parent fix: use a separate inner animation scale, or remove the opening scale tween; if retained, cancel it on every relayout. Keep layout scale authoritative. No shared sizing changes were made in this patch.
