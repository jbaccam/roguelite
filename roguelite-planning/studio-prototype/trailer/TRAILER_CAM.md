# TrailerCam

Smooth camera moves for trailer and ad footage, so gameplay shots glide instead of looking like someone flying around with WASD. Only developer accounts can use it (`AdminConfig.UserIds`), in Studio and in the published game. Status (2026-10-03): written and tested in the repo, **not in Studio yet** (needs your okay to push).

## Files

| File | Goes in Studio as | What it does |
|---|---|---|
| `TrailerCam.client.luau` | LocalScript `StarterPlayer.StarterPlayerScripts.TrailerCam` | Keys, modes, hiding the UI |
| `TrailerCamPath.luau` | ModuleScript child of that LocalScript, named `TrailerCamPath` | The curve math |
| `TrailerCamPathTests.luau` | not installed | 17 checks; all pass (run in Edit with loadstring) |

Like every new roguelite ModuleScript, `TrailerCamPath` needs `Sandboxed = true` and the Capabilities copied from a sibling module, or its require fails.

## Keys

Press **F6** to turn it on or off. While it's on, the game's UI is hidden and a small panel in the top-left shows the mode. The panel and the key markers hide while a move plays, so they never end up in a recording.

| Mode | Keys | Use it for |
|---|---|---|
| **Fly** (start mode) | WASD, E/Q up and down, right mouse to look, Shift for 3× speed, scroll for speed, Z/X to zoom | Lining up shots. Moves are smoothed, so even plain keyboard flying glides. Your character stands still and its weapons keep attacking. |
| **Path** | **1** adds a key at the camera, **2** removes the last key, **3** clears them. **G** plays (G again stops), **[ ]** sets the length (2–60 s, default 8), **L** loops | Dolly and crane shots. Two keys make a straight push, and 3–5 keys make a sweep. The camera moves at an even speed through every key and eases in and out. It rests on the first and last key for 0.8 s, which gives clean cut points. |
| **Orbit** | **O** circles the target nearest the middle of the screen. **Tab** picks the next target, scroll changes the radius, Shift+scroll the height, **[ ]** the speed, **R** reverses | Boss attacks, and a player surrounded by a horde. Bosses come first, then players, then enemies. |
| **Follow** | **F** chases the target from behind with a slow, lazy turn. Scroll changes the distance | Following yourself while you play: WASD still moves your character in this mode |
| Any mode | **U** shows or hides the game UI, **B** hides floating labels and damage numbers, **H** hides the panel | |

## Recording a shot (with friends)

1. Join a match with your friends. Use the ADMIN panel (F2) to set up the shot: Jump to wave, Give weapon Tier IV, God mode, Spawn a boss. Any admin action makes that run a test run, so nobody in it earns rewards.
2. Start OBS: Game Capture of the Roblox window, 1920×1080, 60 fps. Set Roblox graphics to 10.
3. Press F6. Fly to the start of the shot and press 1, then fly to the end and press 1 again. Press G to play the move. Record 2–3 takes of each shot.
4. Trim each clip and save it as `roguelite-planning/trailer/clips/<shot id>.mp4`. The shot ids are in `trailer/shots.json`. Then run `python build_trailer.py`.

## Notes

- **Map streaming.** The map streams in around your character, not the camera. Keep the camera within about 150 studs of your body, or parts of the arena go missing.
- **What shows near the camera.** Enemy models show up to 400 studs from the camera, and boss attack effects up to 160 studs. Both distances are measured from the camera, so Orbit and Path see everything as long as the camera stays close enough.
- **Built-in Freecam still works.** Roblox's Freecam (Shift+P) is separate. TrailerCam's Fly mode replaces it for planning shots, and its Path and Orbit modes add moves Freecam can't do.
- **Key conflicts.** While TrailerCam is on, its keys (1–3, G, L, O, F, Tab, [ ], Z, X, H, U, B, R) don't reach the game. In Fly mode, WASD, Q, E and Space don't reach your character either.
