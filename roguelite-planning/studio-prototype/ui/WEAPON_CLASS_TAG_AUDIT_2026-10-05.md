# Weapon class tag audit — October 5, 2026

Nail Gun belongs to **Handyman, Gunner**, home first, and remains Handyman's starting weapon. The catalog was correct. ShopUI's narrow-card fallback replaced the full membership list with the player's best-fit class, making a Gunner see only GUNNER. That fallback affected every multi-class weapon.

ShopUI now displays the complete home-first membership list in a measured, wrapping tag. Offer cards place it below the weapon header and reserve its full height before stats; weapon details stack membership and the player-specific damage-fit badge separately. Card height grows with the class row. No class, ownership, loadout eligibility, combat tag, or stat value was changed.

Audited all 36 class weapons plus six unrestricted Godlies against CURRENT_GAME_STRUCTURE.md. All class memberships, home ordering, membership helpers, display labels and class combat tags agree. Updated four stale rows in the older multi-class design table to match the already-approved Brawler/Juggler swap: Kusarigama and Spatula are Juggler home; Boxing Gloves and Cinder Block are Brawler home. Armory, shared item cards, Journal, showcase and starter filtering already consume the complete catalog class list.

Validation actually run:

- `WeaponClassTagTests`: **547 assertions passed** using the actual WeaponCatalog in the Luau CLI, covering all 42 weapons.
- ShopUI and ShopLayoutTests compiled with the Luau compiler; whitespace checks passed.
- Required combat overlay built successfully: `rojo build roguelite-planning/studio-prototype/combat/default.project.json -o build/RogueliteKatanaCombat.rbxlx`.
- Extended ShopLayoutTests to reject omitted classes and overlapping class/stat rows. **These engine layout tests have not run.**
- Studio discovery returned no connected instances. **No Studio source synchronization or Play tests ran.** Only `ReplicatedStorage.ShopUI` needs production source synchronization for this fix; verify its path against the combat project before syncing. Preserve the map and unrelated instances.

Next connected Studio check: show Nail Gun and every multi-class weapon in the shop and weapon detail at desktop and narrow phone sizes; run ShopLayoutTests and inspect actual text wrapping. No production DataStores or rewards are involved.
