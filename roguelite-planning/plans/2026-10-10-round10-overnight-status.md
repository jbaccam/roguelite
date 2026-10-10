# Round 10: overnight status (2026-10-10)

## Why the models were redone

On 2026-10-09 you said the Bloater looked like a puffer fish (long neck, flat shoulders, ball body) and the coffin looked white, with rows, and nothing like the reference. Both were model problems. The Studio import was exact (0.000002 studs off).

Studio's lighting also changes colours: a strong blue sky ambient plus +0.3 saturation. Mustard skin came out lime green, white teeth came out blue, and pale sandstone came out grey-blue. Every model below was repainted warmer and checked under a sky-fill light that copies the game.

## Art: all done and Blender-verified, none imported yet

Each one was compared side by side with its reference sheet and fixed until it matched.

| Asset | What it is now | Compare |
| --- | --- | --- |
| Bloater | No neck, cheeks on round shoulders, pear belly, small pale blisters, a vest that hugs the body, and rag caps that ride the arms. Every pose the game's walk and swell actually play is swept: nothing clips. | `bloater-zombie/previews/ThreeQuarter.png`, `Lineup.png` |
| Coffin | Warm chipped sandstone, a chunky bevelled rim, a wrapped-mummy lid with wide crossing bandages. Sized around the Warden's real emerge pose, as the spec asks: 13.5 × 8.3 × 6.6. He fits at every height. That makes it stockier than the slender reference. | `round10-props/previews/Compare_Assembly.png` |
| DJ Crab | Crusher claws, low oval shell, big ear cups with an arched band, strapped speakers, stocky legs, a 0.5 s scuttle. Clips land on the 124 BPM beat. | `dj-crab-boss/previews/Reference_Compare.png` |
| Blood Moon Alpha | Layered leaf fur like your regular werewolf, charcoal mane, cream bib and tail tip, smooth limbs with tufts. Helper bones stop the shoulders and knees from pinching. | `alpha-werewolf-boss/previews/Compare_Reference.png` |
| Tomb Warden | A 10.2-tall stone brute: glyph-block mask with one glowing eye, stone fists with fingers, wide crossed wraps, weathered teal sashes. He steps out of the coffin in three footfalls without touching the walls. | `tomb-warden-boss/previews/Comparison_Reference.png` |

The animation checks run on every frame for every clip:
- joints bend only their own way;
- no twisting;
- no bone turns more than 45° in one frame;
- no limb goes through the body;
- planted feet don't slide;
- loops close;
- each package is re-imported fresh and replayed.

## Code: in Studio and committed

- **Leader attack effects:** `BossVfx/DJCrab`, `TombWarden` and `BloodAlpha`.
  - DJ Crab: a bass ring with gaps, falling rocks for the bombard, beat pulses.
  - Tomb Warden: a gold-sand fist slam, the hook crescent, follow-up sand geysers, a roar, the coffin exit.
  - Blood Moon Alpha: breath, howl rings, snow at every footfall while it charges, the claw rake.
- **Wolf howl:** a licensed howl sound (`wolf_howl` in BossVfxAssets). It loads.
- **Chase speeds:** set so each walk can keep its feet planted (the game caps how fast a walk can play, at 2.6×). DJ Crab 7, Tomb Warden 12.
- **Coffin lids:** a fallen lid beds flush into the sand, so the Warden steps out over tomb A's and players don't trip on a ledge.
- **Warden step-out:** he steps out 4.9 studs in front of the coffin (`emergeOut`).
- **Tomb cutscene:** the camera frames the Warden by his height, and dust runs along the fallen lid.
- **Props installer:** re-uses the stored vent and debris imports.
- **New tool:** `tools/Round10AdoptImports.luau` does the whole install in one call. A dry run in Studio found no false matches.
- **Tests:** the boss suites pass (80 / 28 / 29).

## Morning steps

**1. Import (yours).** Use Studio's 3D importer with the same settings as before: skinned, Keep Zero Influence Bones, "insert using scene position" off. The files are in `build/round10-import-2026-10-10/`:

- `BloaterZombie_Import.fbx`
- `Sarcophagus.fbx`
- `SarcophagusBroken.fbx`
- `DJCrab_Studio.fbx`
- `TombWarden_Studio.fbx`
- `AlphaWolf_Studio.fbx`

**2. Install (Claude does this).**
1. Run `Round10AdoptImports`. It installs the Bloater and coffins, files the bosses, and checks their heights and receipts.
2. Run `retarget_boss.py` for each boss.
3. Run `build_boss_modules.py dj-crab tomb-warden alpha-werewolf`.
4. Do a guarded sync of BossAnimations and MapBossTiming.
5. Run `InstallMapBossTemplates` with `ONLY={'DJCrab','TombWarden','BloodAlpha'}`.

**3. Play test (yours).** Admin panel → Waves → Round 10 Start on each map.

**4. Save.** File → Save to Roblox after the syncs.

## Not done

- **Crab Rave music:** `build/round10-audio/feelgood_segment.ogg` still needs uploading by you (licence caveat). Then set `Round10Defs.Music.CrabRave.soundId`. Until then the event plays the normal playlist.
- **Play tests:** none were run.
