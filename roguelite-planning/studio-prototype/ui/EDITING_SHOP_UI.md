# Edit the shop without writing code

The shop is created by scripts, so its panels are not permanent draggable objects in StarterGui. Use the numeric **Attributes** on `ReplicatedStorage → ShopUI` instead. These are now wired to the layout. You do not need to double-click ShopUI or open its code.

1. Click the **red square Stop button** near Studio's upper-left if the game is running. Changes made to the playtest copy disappear when you stop.
2. Click **Home** at the top, then **Explorer** and **Properties** in that toolbar. These open two panels on the right.
3. In **Explorer**, find **ReplicatedStorage**. Click its small arrow to expand it.
4. **Single-click ShopUI**, directly inside ReplicatedStorage. Do not select RogueliteUI, and do not go into Players or PlayerGui.
5. In the **Properties** panel, clear any text in its search/filter field. Scroll to the bottom and expand **Attributes** using the arrow beside it.
6. Double-click the number beside the setting below, type a new number and press **Enter**.
7. Click the **blue Play triangle** near Studio's upper-left. The shop opens automatically; press **B** to reopen it if closed.
8. To make another permanent adjustment, click **Stop** first and repeat steps 4–7. Save your place through **File** when satisfied. No live publishing is needed to preview changes.

| Attribute | Current value | What to change |
| --- | --- | --- |
| `WeaponsWidth` | `320` | Smaller = narrower Weapons panel. Try 280; desktop minimum is 240. |
| `WeaponsHeight` | `152` | Larger = taller panel and weapon slots. Try 164. |
| `ItemsHeight` | `152` | Larger = taller item panel and slots. |
| `InventoryBottomPadding` | `12` | Smaller = move both bottom inventories down; larger = move them up. |
| `ItemWidthShare` | `0.55` | Larger = wider Items panel. This is a fraction of the region left of stats. |
| `RerollWidth` | `180` | Width of the Reroll button. Try 160 for smaller. |
| `RerollHeight` | `34` | Height of Reroll (28–40 pixels). |
| `HorizontalMargin` | `0.025` | `0.02` means 2% on each side; `0.03` means 3%. |
| `ContentTop` | `64` | Larger = move the cards/top controls down. Keep below the heading. |
| `HeaderTop` | `16` | Position of the shop title relative to the top edge. |
| `SlotGap` | `4` | Spacing between inventory slots. |
| `InventoryGap` | `8` | Minimum separation between inventory panels. |
| `CardHeight` | `248` | Height of the four shop offers; minimum 230. |
| `StatsWidth` | `250` | Maximum width of the stats column. |

Weapons stays six slots in two rows of three. Both inventory heights have a 92-pixel minimum. Smaller screens rearrange the layout to avoid overlap, so the exact requested width is a desktop target rather than a forced overflow.

You can experiment with these Attributes during Play and see the changes immediately, but **write down those values and apply them again after Stop** if you want them saved. Dragging PlayerGui panels also only affects that playtest and is replaced when the UI redraws.

Repository synchronization: Attribute values are saved in `studio-prototype/combat/default.project.json` under `ReplicatedStorage.ShopUI.$attributes`. Fallback defaults are at `M.Layout` near the top of `ui/ShopUI.luau`. Attributes take precedence over those defaults. Before a future Rojo sync, copy your changed Studio Attributes into that project JSON, or ask Codex to read them back into the repository. Do not replace your Studio values with the old defaults.

Verification: seven rendered sizes passed boundary checks, from 1920×1080 through 390×844, including 640×360. A live `WeaponsWidth` Attribute change from 320 to 280 resized the panel and was restored to 320. Both Rojo builds passed. The existing session loadout, items, gold, offers and stat overrides were restored after the UI update.
