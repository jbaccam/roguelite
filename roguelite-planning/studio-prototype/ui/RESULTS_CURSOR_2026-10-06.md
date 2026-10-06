# Cursor ownership when leaving after a boss — October 6, 2026

The reported path was boss completion → Continue → shop → Leave to Lobby. Source inspection found a cursor-ownership gap during the resulting reward screen: the shop and its leave confirmation provide a modal cursor owner, but `RunResultsUI` consisted of Frames and ordinary buttons. Closing the shop assigned `MouseBehavior.Default` only once. The normal first-person/shift-lock camera could recapture it on the next render, leaving result actions inaccessible.

`UITheme.freeMenuCursor` now gives the results ScreenGui a modal cursor owner and enforces a visible, free cursor after the normal camera render while that screen is enabled. Hiding, detaching or destroying the screen releases the render binding and clears only gamepad selection belonging to that screen. Camera healing respects existing stage ownership. It does not permanently disable normal gameplay camera controls.

`RunResultsUI` releases the screen on lobby arrival as well as when `RunResult` clears. `RogueliteUI` closes its shop as soon as run membership ends or lobby preview activates, before consulting potentially stale shop snapshots. Those attributes also trigger the lifecycle refresh. The behavior uses shared UI lifecycle state rather than Studio, map or difficulty checks.

## Verification

- `ResultsCursorTests.py` executed the actual extracted `UITheme.freeMenuCursor` helper with mocked render-order/input events using the official Luau CLI. Passed show/hide/reopen/detach/reparent/destroy, simulated camera recapture, and scoped gamepad-selection cleanup.
- `UITheme`, `RogueliteUI`, `RunResultsUI` and the QA helper compiled with the official Luau compiler.
- The implementation agent did not run Studio Play or a real teleport. Parent integration owns live confirmation.

`ResultsCursorQA.luau` is an unbundled Studio-client helper. Install it temporarily as a ModuleScript and call `require(module)()` from the client. It uses production cursor ownership on a temporary ScreenGui, simulates a camera setting LockCenter every frame, then checks open, close, reopen and destruction. It restores previous mouse/icon/selection/camera settings and sends no remotes or reward requests. A pass confirms cursor ownership and release; it does **not** prove a successful production leave/teleport.

For the full UI route, use a Studio test run with DataStores disabled, clear/jump to a boss encounter, Continue into the shop, then Leave Run and confirm. In first person or shift lock, verify reward-screen buttons remain pointer-accessible, Back to Lobby completes, and no shop returns over the lobby. Real production teleport remains separately unverified.
