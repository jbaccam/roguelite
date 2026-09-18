# Editing the shop in Roblox Studio

The shop is built by scripts when the game runs. Its permanent layout controls are in **ReplicatedStorage → ShopUI**, near the top under `LAYOUT SETTINGS`. Dragging the generated panels under a player's PlayerGui only changes that running session.

1. Click the **red square Stop button** near Studio's upper-left corner if the game is running.
2. Click the **Home** tab at the top, then **Explorer** in its toolbar. Explorer is the tree of game objects, normally on the right.
3. In Explorer, find **ReplicatedStorage**. Click the small arrow beside it to expand it.
4. Find **ShopUI directly inside ReplicatedStorage** and double-click it. Do not open the separate RogueliteCombat folder for this edit.
5. Press **Ctrl+F**, type `LAYOUT SETTINGS`, and press Enter. Press Escape to close Find.
6. Change only the number beside the setting you want. Keep the comma at the end of the line. For example, change `WeaponsHeight=112,` to `WeaponsHeight=100,` to make only the shop's weapons panel shorter.
7. Click the **blue triangle Play button** near the upper-left. The shop opens at the beginning of a test; **B** opens it again if closed.
8. Inspect the result. Click **Stop** before adjusting the numbers again. Use **Ctrl+Z** in the script editor if you need to undo your edit.
9. Save your place using Studio's **File** menu when satisfied. Saving and publishing a live update are separate actions; testing this layout does not require publishing.

| Setting | Current value | What it changes |
| --- | --- | --- |
| `WeaponsHeight` | `112` | Shop weapons panel height in pixels. Six slots remain two rows of three. |
| `ItemsHeight` | `112` | Item panel height, independently of Weapons. |
| `HorizontalMargin` | `0.025` | Margin on each side. `0.02` = 2%; `0.03` = 3%. |
| `HeaderTop` | `16` | Distance between the top edge and the shop heading. |
| `ContentTop` | `64` | Top position of the gold/reroll row and stats column. Keep it below the heading. |
| `SlotGap` | `4` | Spacing between inventory slots, in pixels. |
| `InventoryGap` | `8` | Gap between the Items and Weapons panels. |
| `InventoryTitleHeight` | `26` | Space above the slots reserved for each panel title. |
| `ItemWidthShare` | `0.55` | Fraction of the lower-left region used by Items. Weapons uses the remainder. |
| `CardHeight` | `248` | Height of each of the four shop offer cards. |
| `StatsWidth` | `250` | Maximum width of the right stats column. |

Panel heights have a 92-pixel minimum, and cards a 230-pixel minimum, to keep their controls usable. Use small changes, such as 8–16 pixels at a time. These settings affect the shop, not the separate creative weapon catalog.

Source of truth: `roguelite-planning/studio-prototype/ui/ShopUI.luau`. Studio-only script edits must be copied back to this repository file before a future Rojo sync, or the repository version will replace them. If working through Codex, ask it to read your edited Studio settings back into the source rather than resetting your values.

`RogueliteUI` owns the outer menu, header, status area and footer. `ShopUI` owns the offer cards, stat tabs, Items, Weapons and Start Wave, and exposes the shared layout settings used by both modules.

Verification for this revision: the rendered layout passed boundary checks at 1920×1080, 1440×900, 1280×720, 1024×768, 800×600, 640×360 and 390×844. Both Rojo projects package successfully. The change does not alter purchases, the six-weapon limit, creative equipping, or weapon textures.
