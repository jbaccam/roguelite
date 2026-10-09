# Creator Hub: developer products and passes

Images: `make_product_images.py` (512×512, game icons on store-coloured tiles). For every product:
**Item for sale ON**, **Managed pricing OFF** (the game's buttons show these exact prices; with it on,
Roblox changes the price per region and runs price tests, so buttons and checkout would disagree).
After saving, copy the Product / Pass ID into `combat/MonetizationConfig.luau` (`productId=` / `gamePassId=`).

Thrower became Chef (2026-10-09): product 29 keeps its config key `ClassThrower` and its product ID (3716086758), so
old receipts still map. Only rename it on the dashboard: name, description and image from row 29 below.

Folder: `C:\Users\Jeremiah\Documents\ChatGPT\Roblox\roguelite-planning\studio-prototype\ui\assets\store-products`

## Developer products (Monetization → Developer Products → Create)

| # | Config key | Image | Name | Description | Price |
|---|---|---|---|---|---|
| 1 | Revive1 | 01-Revive1.png | Revive (1st) | Get back up where you fell with half health and a 3 second shield. Each revive in the same run costs more. | 65 |
| 2 | Revive2 | 02-Revive2.png | Revive (2nd) | Get back up where you fell with half health and a 3 second shield. Each revive in the same run costs more. | 130 |
| 3 | Revive3 | 03-Revive3.png | Revive (3rd) | Get back up where you fell with half health and a 3 second shield. Each revive in the same run costs more. | 260 |
| 4 | Revive4 | 04-Revive4.png | Revive (4th) | Get back up where you fell with half health and a 3 second shield. Each revive in the same run costs more. | 520 |
| 5 | Revive5 | 05-Revive5.png | Revive (5th+) | Get back up where you fell with half health and a 3 second shield. Every revive after the 4th in a run costs this. | 1040 |
| 6 | ShopReroll | 06-ShopReroll.png | Shop Reroll | New random offers in the run shop. If you're not in a shop, it's saved for later. | 15 |
| 7 | UpgradeReroll | 07-UpgradeReroll.png | Level-Up Reroll | New random level-up cards. If you're not choosing one, it's saved for later. | 15 |
| 8 | Banish | 08-Banish.png | Banish | Removes one level-up card for the rest of the run and replaces it with a random one. Saved until you use it. | 19 |
| 9 | Rerolls5 | 09-Rerolls5.png | 5 Rerolls | 5 rerolls saved to your account. Use them on run shop offers or level-up cards. Results are random. | 59 |
| 10 | Rerolls15 | 10-Rerolls15.png | 15 Rerolls | 15 rerolls saved to your account. Use them on run shop offers or level-up cards. Results are random. | 149 |
| 11 | Banishes5 | 11-Banishes5.png | 5 Banishes | 5 banishes saved to your account. Each removes one level-up card for the run. | 79 |
| 12 | Banishes15 | 12-Banishes15.png | 15 Banishes | 15 banishes saved to your account. Each removes one level-up card for the run. | 199 |
| 13 | Emeralds1 | 13-Emeralds1.png | Pouch of Emeralds | 400 emeralds for chests, eggs, upgrades and classes. | 39 |
| 14 | Emeralds2 | 14-Emeralds2.png | Stack of Emeralds | 1,700 emeralds for chests, eggs, upgrades and classes. | 149 |
| 15 | Emeralds3 | 15-Emeralds3.png | Crate of Emeralds | 4,200 emeralds for chests, eggs, upgrades and classes. | 339 |
| 16 | Emeralds4 | 16-Emeralds4.png | Vault of Emeralds | 10,500 emeralds for chests, eggs, upgrades and classes. | 799 |
| 17 | Emeralds5 | 17-Emeralds5.png | Hoard of Emeralds | 22,000 emeralds for chests, eggs, upgrades and classes. | 1649 |
| 18 | Emeralds6 | 18-Emeralds6.png | Treasury of Emeralds | 52,000 emeralds for chests, eggs, upgrades and classes. | 3749 |
| 19 | Royal1 | 19-Royal1.png | 1 Legendary Chest | 1 Legendary Chest with at least one Legendary item. Items are random; the odds are shown in the game. | 49 |
| 20 | Royal5 | 20-Royal5.png | 5 Legendary Chests | 5 Legendary Chests, each with at least one Legendary item. Items are random; the odds are shown in the game. | 199 |
| 21 | Royal12 | 21-Royal12.png | 12 Legendary Chests | 12 Legendary Chests, each with at least one Legendary item. Items are random; the odds are shown in the game. | 399 |
| 22 | StarterPack | 22-StarterPack.png | Starter Pack | One time only: 1,500 emeralds, 2 Legendary Chests and 5 rerolls. Chest items are random; the odds are shown in the game. | 49 |
| 23 | ArsenalBundle | 23-ArsenalBundle.png | Arsenal Bundle | +3 upgrades to every class's starter weapon, plus 1,500 emeralds. | 299 |
| 24 | MegaBundle | 24-MegaBundle.png | Mega Chest Bundle | 30 Legendary Chests, 3,000 emeralds, 25 rerolls and 10 banishes. Chest items are random; the odds are shown in the game. | 999 |
| 25 | UltimateBundle | 25-UltimateBundle.png | Ultimate Chest Bundle | 100 Legendary Chests, 5,000 emeralds, 50 rerolls and 25 banishes. Chest items are random; the odds are shown in the game. | 2999 |
| 26 | BloodPhoenixBundle | 26-BloodPhoenixBundle.png | Blood Phoenix Bundle | One time only: the Vampire Blade, the full Phoenix armor set and 3,000 emeralds. | 1799 |
| 27 | ShadowDragonBundle | 27-ShadowDragonBundle.png | Shadow Dragon Bundle | One time only: the Shadow Daggers, the full Dragon Scale armor set and 1,500 emeralds. | 1199 |
| 28 | GodlyStarter | 28-GodlyStarter.png | Godly Starter | One time only: pick one Godly weapon, plus 3 Legendary Chests. Chest items are random; the odds are shown in the game. | 799 |
| 29 | ClassThrower | 29-ClassThrower.png | Chef Class | Unlock the Chef class now. It can also be unlocked by playing or with 400 emeralds. | 49 |
| 30 | ClassJuggler | 30-ClassJuggler.png | Juggler Class | Unlock the Juggler class now. It can also be unlocked by playing or with 400 emeralds. | 49 |
| 31 | ClassHandyman | 31-ClassHandyman.png | Handyman Class | Unlock the Handyman class now. It can also be unlocked by playing or with 400 emeralds. | 49 |

## Game passes (Monetization → Passes → Create a Pass, then open it → Sales → Item for Sale + price)

| # | Config key | Image | Name | Description | Price |
|---|---|---|---|---|---|
| 32 | VIP | 32-PassVIP.png | VIP | +25% emeralds from every run, a free Gold Chest every day, and open chests 10 or 100 at a time. | 499 |
| 33 | QuickOpen | 33-PassQuickOpen.png | Quick Open | Open chests 10 or 100 at a time instead of one by one. | 149 |
