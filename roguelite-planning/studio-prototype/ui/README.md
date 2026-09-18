# Character stat editor update — September 17, 2026

Stats / Test [P] and the Stats menu tab open the server-owned character editor. It exposes all 45 stat attributes, six classes, suggested weapon builds, healing/damage controls and zombie-count buttons (0–100). The Shop sidebar displays the complete live stat list in a scroll panel. Shop Discount is labeled inactive; non-weapon items and purchasing remain outside this feature. See [implementation and verification](../combat/CHARACTER_STATS.md). Earlier notes about unavailable combat-stat dashes are superseded.

# Live weapon inventory update — September 17, 2026

The Inventory button, I key, and Inventory tab open all 36 reviewed weapon models. Select a numbered slot, then Equip; Remove clears that slot. Weapons (x/6) reflects server state in both Inventory and Shop. Equipping is free, allows duplicate weapons, and is restricted on the server to living players in Studio Practice. The Shop and Upgrades offer cards remain presentation previews. See ../combat/LOADOUT.md for implementation and current test results. WeaponInventoryUI.luau maps to ReplicatedStorage.WeaponInventoryUI. The following notes describe the original HUD/preview slice.

# Roguelite health HUD and UI previews

Targets the separate `roguelite` place 107877054949326. Do not sync the root CopyTheScene Rojo project into this place.

## Runtime mapping

- `RogueliteUI.luau` → `ReplicatedStorage.RogueliteUI` (ModuleScript).
- `RogueliteHUD.client.luau` → `StarterPlayer.StarterPlayerScripts.RogueliteHUD` (LocalScript).

These are first-party presentation scripts. Install through the Studio script editor/tool so normal first-party script capabilities apply; do not create sandboxed script containers lacking the avatar/UI permissions they need.

## Behavior

The HUD binds to the local character's actual Humanoid Health and MaxHealth. HealthChanged, MaxHealth, death, and character lifecycle events update its numeric display, smooth fill, damage trail, and low-health warning. Event connections are removed when the character changes. It neither sets health nor exposes a damage remote. Default Roblox health UI is suppressed to avoid duplication.

XP and gold are intentionally absent. Until a run service exists, the timer displays `--:-- / PRACTICE`. A future server may provide a `ReplicatedStorage.RogueliteRunState` instance with numeric `WaveEndsAt` (server time), numeric `Wave`, and string `Phase` attributes. The HUD computes countdown display from `Workspace:GetServerTimeNow()`; it does not advance waves.

**UI Preview** appears only in Studio. It opens level-up and shop previews. Choose/Inspect provides local selection feedback, Hold keeps shop cards in place during preview rerolls, and reroll rotates sample offers. Back to game closes either menu. No upgrade, item, weapon, currency, XP, or reward is granted. The example values are reference art copy, not approved balance. Stats display actual max HP and movement speed, with unavailable combat stats shown as dashes. Item/weapon slots are empty until authoritative inventory is connected.

Closing a preview hides the overlay, clears controller UI selection, restores the current character Humanoid as camera subject, sets the normal Custom camera, and releases the mouse. The close button is modal only while its menu is visible so first-person players can use the cursor. Menus do not pause multiplayer simulation. Death/respawn closes them.

Layouts respect CoreUISafeInsets and device clipping. Menus reflow from desktop rows to two/single-column scroll layouts; actions remain in a fixed footer. Source images are nine-sliced so borders keep their shape as panels resize. Desktop and mobile test evidence is tracked in `VALIDATION.md`.

## Assets and reproducibility

Run `python build_assets.py` with Pillow to reproduce the editable SVG and PNG artwork. Sources are original vector drawings based on the supplied visual direction. Uploaded image IDs and reference provenance are recorded in `../ASSETS.md`. The local HTTP server used for uploading is not a game dependency.
