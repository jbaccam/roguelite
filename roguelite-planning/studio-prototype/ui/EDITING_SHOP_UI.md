# Shop presentation controls

The shop follows the supplied reference: four tall offers on desktop and two columns (2×2) on medium screens and phones. On short screens (view under 450 px tall) the shop scales down so one whole card plus its lock fits, and every button stays at least 40 px on screen. Price buttons sit inside the cards; locks sit below. Sold offers disappear. Owned item and weapon icons pack into the lower inventory without empty placeholder boxes. Weapon selection dims the shop and anchors a tier-colored detail panel above its icon. Short screens scroll detail contents.

The source of truth is `ShopUI.luau`; `WeaponInventoryUI.luau` contains the shared uploaded artwork mapping, used by both shop and creative inventory. `assets/weapons/provenance.json` records original filenames and Roblox IDs. The supplied set now has all 36 weapon images, including Glock.

Supported layout controls on ReplicatedStorage.ShopUI:

| Attribute | Value | Effect |
| --- | ---: | --- |
| HorizontalMargin | 0.025 | Fractional left/right margin |
| CardHeight | 390 | Maximum offer height; short views fit to available space with a 310-pixel minimum and scrolling |
| StatsWidth | 310 | Maximum stats column width |

Inventory size follows content; columns and detail positions adapt automatically. Older fixed-slot layout attributes are retained for compatibility but no longer control the content-sized inventory. Use Stop/Play after editing source. Edits during Play are temporary; keep permanent Studio changes synchronized with this repository.

See `SHOP_UI_VALIDATION.md` for this revision's validation and remaining limits.

