# Wavebreaker trailer

A 30-second trailer that you finish by recording gameplay clips. Everything else is already done: the title and end cards, the kinetic text, the map and boss labels, the cut effects, the temp beat, and a vertical version for TikTok.

## What's in the folder

| Path | What it is |
|---|---|
| `build/wavebreaker_trailer_16x9.mp4` | 1920×1080, 60 fps: YouTube, Roblox, Discord |
| `build/wavebreaker_trailer_9x16.mp4` | 1080×1920, 60 fps: TikTok, Shorts, Reels (and for Rokko) |
| `screenshots/` | Graded 1920×1080 PNGs of the lobby, chests, egg merchant and maps, captured from Studio's renderer (not Blender renders) |
| `stills/raw/` | The original Studio captures (1578×845) |
| `clips/` | Put your recorded clips here (empty for now) |
| `shots.json` | The edit: shot order, length in beats, on-screen text, and what to record for each slot |
| `build_trailer.py` | Builds both videos from `shots.json` |
| `temp_beat.py` | Makes the temp music (128 BPM, synthesised, no samples) |

**Right now:** 9 shots use real captures (lobby, portals, chests, Legendary chest, egg merchant, Pine Valley, Beach Cove, plus the title and end cards). The 20 gameplay slots show a card saying exactly what to record.

## Finishing it

1. Record the clips below in a real match with friends. Use the ADMIN panel for setup and TrailerCam for the camera (`studio-prototype/trailer/TRAILER_CAM.md`). Record at 1080p or 1440p, 60 fps.
2. Trim each clip so the best moment starts at 0, and save it as `clips/<shot id>.mp4`. To start later in the clip instead, set `"in": <seconds>` on that shot in `shots.json`.
3. Run:

```bash
python build_trailer.py
```

Any shot with a clip in `clips/` uses it; the rest keep their still or placeholder card, so you can fill the slots in any order. A clip longer than its slot is cut at the slot's length.

4. **Music.** Put a track you have the rights to at `music.wav` and rebuild; it replaces the temp beat. Cuts land on a 128 BPM grid, so a 128 BPM track lines up (or change `"bpm"` in `shots.json`). The temp beat is fine to watch with but not to post. Roblox ads and TikTok both mute or flag copyrighted songs, so use a licensed or royalty-free track.

To check the edit without waiting for the full render:

```bash
python build_trailer.py --frames 3
```

That writes `build/contact_sheet.jpg`, three frames from every shot. `--only 16x9` or `--only 9x16` builds one format, `--screenshots` re-exports the PNGs, and `--nvenc` uses the GPU encoder once the NVIDIA driver is 610 or newer (the current driver is too old).

## Clips to record (20)

| At | Shot | Length | What to record |
|---|---|---|---|
| 0.0s | `G01_horde_incoming` | 1.9s | Pine Valley, admin Waves -> Jump to wave 15. Low camera at knee height in front of your squad, horde running at the lens. TrailerCam: two keys, slow push toward the squad. |
| 1.9s | `G02_squad_shreds` | 1.9s | Same wave. Give yourself Tier IV Godly weapons in all 6 slots (admin Give weapon) and God mode; friends fight next to you. TrailerCam ORBIT on yourself, radius ~30. Your weapons keep firing while you film. |
| 3.8s | `G03_raygun_burst` | 0.9s | Close-up: Ray Gun Tier IV kills disintegrating in a burst. TrailerCam FOLLOW on yourself at distance ~12. |
| 4.7s | `G04_scythe_wraiths` | 0.9s | Close-up: Reaper's Scythe 360 reap raising wraiths. ORBIT radius ~15, fast (press ] twice). |
| 8.4s | `G05_armory_loadout` | 0.9s | Lobby: open the Armory (Weapons tab), click through 3 weapons, then CHANGE CLASS. Screen recording, UI on. |
| 9.4s | `G06_shop_merge` | 1.9s | Between-wave shop: buy a weapon you already hold so two copies MERGE into Tier II, then reroll once. Admin: Waves, Shards Add 1000. |
| 11.2s | `G07_levelup` | 0.9s | Level-up cards appear and you pick one. Admin: Level Add 3 during the shop. |
| 12.2s | `G08_weapon_ring` | 0.9s | Your avatar with 6 Godly/Legendary weapons floating around, slow ORBIT, mobs closing in (Keep 20 alive). |
| 15.0s | `G09_chest_burst` | 1.9s | Chest screen: open a Legendary or Magical chest x1, tap until it bursts, hold on the item card. Best if it rolls a Godly weapon. |
| 17.8s | `G10_egg_hatch` | 0.9s | Egg screen: hatch x3, tap through the cracks to the pet reveal. |
| 20.6s | `G11_map_desert` | 0.5s | Desert Basin mid-wave (skeletons, mummies), wide. |
| 21.1s | `G12_map_frozen` | 0.5s | Frozen Pass mid-wave (ghosts, werewolves), wide. |
| 21.6s | `G13_map_volcano` | 0.9s | Volcanic Crater mid-wave (lava slimes, goblins), wide, lava glow. |
| 22.5s | `G14_boss_hammer` | 0.9s | Mobs -> Spawn Hammer x1, God mode. ORBIT low (Shift+scroll down) as it slams. |
| 23.4s | `G15_boss_crab` | 0.9s | Spawn KingCrab on Beach Cove, catch its signature attack. |
| 24.4s | `G16_boss_pharaoh` | 0.5s | Spawn Pharaoh on Desert Basin, catch its signature attack. |
| 24.8s | `G17_boss_cyclops` | 0.5s | Spawn FrostCyclops on Frozen Pass, catch its signature attack. |
| 25.3s | `G18_boss_dragon` | 0.9s | Spawn Dragon on Volcanic Crater: fire breath across the arena. Wide ORBIT, radius ~60. |
| 26.2s | `G19_skill_tree` | 0.9s | Lobby: open the Skill Tree (K), buy two nodes. |
| 27.2s | `G20_victory` | 0.9s | Results screen VICTORY with your squad (clear wave 20 on any map). |

Map stills S05 and S06 already have real captures. Record them too if you can get mid-wave versions, which look better with mobs on screen.

## Editing it by hand instead

If you'd rather cut it in CapCut or Premiere, use this as the shot list. `build/temp_beat.wav` and the stills work as a starting point there too.
