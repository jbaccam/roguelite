# Armory backdrop (the hall behind the Armory screen)

The 3D stage for the lobby's full-screen Armory (`studio-prototype/ui/ArmoryUI.luau` + `ArmoryStage.luau`). It is an open-front timber armory hall in the lobby kiosk's language: warm wood planks and posts, a light-stone footing, a slate-blue shingle overhang and slate cloth, restrained lime accents. The player's avatar stands on a round flagstone dais with a glowing lime ring. Behind the avatar hangs a large round armory crest (slate face, lime ring, cream star, brass boss) standing off the wall on a post, flanked by two hanging lanterns. The side bays hold a standing rack, a pegged wall display and a shelf, plus an anvil on a stump, a barrel and crates.

**The weapons are the game's real models.** This kit builds only the holders. `ArmoryStage.luau` clones `RogueliteCombat.WeaponTemplates` onto them at runtime (`DISPLAY` in `build_armory.py`, written to `armory-report.json` as `weapon_slots_studio` and copied into `ArmoryStage.Display`): Katana and Baseball Bat crossed behind the crest, Excalibur / Magic Staff / Shovel in the rack, Rocket Launcher on pegs, Frying Pan hanging by its handle, Boomerang on pegs, Crystal Ball and Pandora's Box on the shelf, a bat and a katana in the barrel, Mjolnir on the anvil. Each model is scaled by its true bounds (`BoundsSize`) and turned so its long axis follows the slot direction with its flat side to the camera. A layout check in Studio confirmed every model sits between its holder and the wall; which way up the non-normalized models (launcher, box, ball, Mjolnir) face still needs a look in game. If you move a holder, change `DISPLAY`, rebuild, and regenerate the table. The project's evergreen master peeks over the roof.

The composition follows the Armory screen: the side panels and slot cards cover the outer thirds, so the dais, the crest halo around the avatar and the top band (beam, lanterns, pine tops) carry the look. The front faces the lobby sun (-Z in Studio), and the roof is a short overhang so the avatar stays sunlit.

## Build

```
blender --background --factory-startup --python build_armory.py
```

Self-contained apart from two project inputs: `../blender-map-mini-islands/island_lib.py` (imported as a module for the painterly ramp materials, atlas bake, preview rig and export, the same way the island builders use it) and `../blender-master-evergreen/Evergreen_Master.glb`. No Creator Store content and no user-supplied images.

- 1 unit = 1 stud. Origin = dais top centre (the avatar's feet); floor at z = -0.9.
- `box_tmp` scales before bevelling, so chamfers are absolute studs (the island helper bevels a unit cube first, which stretches chamfers on long planks into points).
- Outputs: `exports/fbx|glb/armory-backdrop.*` with `Armory_Room` (floor, walls, roof, dais, ground; 2048 atlas), `Armory_Props` (crest, racks, pegs, lanterns, props; 2048 atlas), `Armory_Trees` (evergreen master texture), and flat-colour `Armory_GlowLime` / `Armory_GlowWarm` (set to Neon by the installer; the bake is diffuse-only).
- `armory-report.json`: triangle counts and the camera presets. Room 16.5k, props 2.5k, trees 30.0k (12 evergreen instances), glow 0.2k triangles.
- `bounds.py` prints each export's bounding box in Studio axes; `studio-install-armory.luau` uses them.
- `previews/`: real Blender renders at the Studio cameras (`armory-hero.png`, `armory-upgrade.png`) and a wide overview. The holders are empty there because the weapon models are placed in Studio. Blender colours read duller than Studio, which adds saturation; judge colour in Studio.

## Studio install

1. File > Import 3D `exports/fbx/armory-backdrop.fbx` at default settings (it lands as `workspace['armory-backdrop']`).
2. Run `studio-install-armory.luau` in the command bar. It restores stud scale, pivots the model on the dais top centre, anchors everything and turns off collision and queries, turns the glow meshes Neon, moves any importer SurfaceAppearance onto `TextureID` (SurfaceAppearance renders blank in Play), adds the lantern, fill and dais lights, and stores the hall as `ReplicatedStorage.ArmoryBackdrop`. It refuses to overwrite an installed hall.

`ArmoryStage` clones it into the camera at (1600, 420, -14000), beside the map-select islands, and works without it (the Armory screen then falls back to a blurred, dimmed lobby).

**Installed and checked in Play, 2026-09-27:** imported at default settings (stud scale, atlases on `TextureID`, no SurfaceAppearance) and installed as `ReplicatedStorage.ArmoryBackdrop`. Every mesh landed where `bounds.py` predicted, confirming the 180° importer turn. In a Play client, opening the Armory put the hall, the avatar on the dais and all 13 real weapon models in place, and captures confirmed each weapon's orientation (crest katana and bat, rack, launcher on its pegs, hanging pan, boomerang, ball and box on the shelf, barrel, Mjolnir on the anvil). Fixes from that check: the rack moved clear of the timber post at x = -6.4 (Excalibur's blade was hidden inside it), the launcher shortened so it clears the pan, flat sides now face the camera with their +axis (single-sided blades), the hero camera pulled back to 20.5 studs, and the lantern glass switched from Neon to warm SmoothPlastic because Neon blew out under the lobby bloom. The lobby's own ARMORY button was not clicked in that run: the place's server scripts were failing to load because of other sessions' in-progress work, so the screen was opened directly from the client.
