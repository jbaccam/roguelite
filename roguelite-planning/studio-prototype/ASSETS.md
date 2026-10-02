# Zombie asset provenance

## Supplied shard HUD icon and XP bar — September 22, 2026

User originals `C:/Users/Jeremiah/Downloads/ChatGPT Image Sep 22, 2026, 12_05_21 PM (1).png` and `(2).png` are copied unchanged to `ui/assets/shard-hud-reference.png` and `ui/assets/xp-hud-reference.png`. Uploaded for the requested HUD: shard `rbxassetid://119781825571908`, XP bar `rbxassetid://101475186887359`. Originals are transparent 1254×1254 and 2172×724 PNGs; Roblox readback is 1024×1024 and 1023×341. RogueliteUI and ShopUI crop these original textures at runtime. The XP bar preserves the provided frame, potion and faceted green artwork, masks baked sample text, and overlays live XP/level values. No new AI artwork or Creator Store assets were used. Prior Studio source backup: `ServerStorage.BeforeShardXP_20260922`.

- Body: Roblox native stock R15 geometry from Players:CreateHumanoidModelFromDescriptionAsync; approved supplied zombie textures, with atlas IDs and preparation files under ../zombie-stock-r15-preview/supplied-textures/studio-native.
- Head source: Roblox built-in `rbxasset://avatar/heads/head.mesh`, 517 source vertices and 846 triangles. Geometry unchanged; custom UVs follow ApplyFullHeadUV.luau and the original supplied head image.
- Persistent head mesh: `rbxassetid://78893098815517`, uploaded through Studio's 3D importer on 2026-09-17 as ZombieHead_NativeUV. Source export: ZombieHead_NativeUV.obj, reproducible using export_head.py. Original head texture: `rbxassetid://117306049770322`.
- Only static mesh data was imported. No imported scripts, behavior, accessories, or external animation assets were added.
- Runtime scripts are repository-authored. Animation is procedural per client; movement and targeting remain server-owned.

## Roguelite UI — 2026-09-17

The supplied generated references are preserved under `../art-references/` (HUD, level-up, shop). The UI uses original repository-authored vector artwork inspired by those references, not flattened screenshots or third-party Creator Store code. `ui/build_assets.py` writes the editable SVGs and supersampled PNGs in `ui/assets/`. Uploaded through Studio for this implementation:

| Asset | Roblox image ID |
| --- | --- |
| panel | 116439058081230 |
| inset | 82653359149627 |
| button | 72732018694626 |
| stone | 107387940957948 |
| heart | 101432943753406 |
| gem (reserved) | 102213113777434 |
| bag | 82818131570338 |
| teeth | 113971691535704 |
| shoulders | 103758481309908 |
| pan | 120727496371371 |
| duck | 72853007735977 |
| staff | 102427273904664 |

No imported scripts, plugins, or executable content accompany these images. In-session image loading is checked in Studio; published-client asset permissions need separate verification.


## Six-slot practice inventory — 2026-09-17

WeaponTemplates 00–35 are static clones of the existing reviewed Workspace.RogueliteWeaponShowcase_PlaySize models, with model provenance retained in each SourceDisplay attribute. No external assets were imported for this change. The katana reuses RogueliteCombat.KatanaTemplate and its measured geometry. The rocket launcher omits the loose showcase rocket specimen. Viewport previews use these same clones; the inventory reuses the existing RogueliteUI panel/button assets. User-supplied Brotato screenshots and the multi-weapon MP4 guided slot layout and automatic targeting only; no game artwork was copied. InstallLoadout.luau records the cloning/normalization steps.


### Zombie pop clouds
The supplied ChatGPT Image Sep 17, 2026, 10_47_33 PM.png is a visual reference for white/blue cloud puffs. Effects use original code-created clusters of Roblox sphere parts; no image extraction, upload, or external model is required.


### RPG projectile
RocketTemplate reuses Workspace.RogueliteWeaponShowcase_PlaySize.11_Rocket_Launcher.W11_Rocket_Component (mesh 88760761479585) without resizing the source. The projectile is centered and oriented to combat-local -Z; its SourceDisplay attribute retains provenance. Exhaust uses the bundled Roblox smoke texture rbxasset://textures/particles/smoke_main.dds. No new third-party asset was imported.


### RPG cloud trail refinement
ChatGPT Image Sep 17, 2026, 11_04_36 PM.png is a style reference for the white/gray cloud silhouette. RocketVisuals now creates original three-sphere cloud clusters in code; this replaces the earlier bundled smoke texture exhaust. No reference image pixels or new external assets are used.


### Rocket explosion artwork — September 18, 2026
User-supplied ChatGPT Image Sep 18, 2026, 12_09_04 AM (1).png and (3).png are copied unchanged into combat/assets/rocket-explosion-small-atlas.png and rocket-explosion-large-atlas.png. Both originals are 1254×1254 RGBA. Uploaded for this requested Roblox effect: small atlas rbxassetid://99550847281506, large atlas rbxassetid://120401440349556. RocketExplosionVisuals selects sprites using ImageRect on the Roblox-served 1024px textures. No external Creator Store asset or generated replacement was used.
# Weapon presentation update — September 22, 2026

The reviewed baseball bat combat copy is straightened from its baked display angle; geometry dimensions are measured from the existing GLB. Rocket launcher mesh `79978356738826` and texture `110911562405378` are retained. Its combat copy gains one code-created, untextured dark `StableBoreBackstop` Part recessed behind the muzzle, to obscure the unstable interior. This makes the visible cavity shallower; it does not change the exterior or projectile origin. No new mesh asset was uploaded. `combat/WeaponPresentation.luau` reproduces the adjustments; original showcase assets remain intact.

### Rear bore correction replacing the earlier backstop — September 22, 2026

The previous backstop was placed at the opposite end and did not address the reported green flicker. Actual GLB inspection found eight green and eight dark triangles sharing original X=-2.55, native mesh X=214.5, at the rear opening. `combat/launcher-rear-cap-audit.json` records the geometry and sampled atlas colors. `WeaponPresentation.stabilizeLauncher` version 2 removes the old `StableBoreBackstop`, adds a recessed dark native cylinder at native X=218.5 and a separate olive inset at X=221.5, in front of both conflicting imported disks. Colors (14,15,18) and (102,113,56) are sampled from the existing atlas. The parts are noncolliding, untextured and move with their model. The original mesh, texture, outer dimensions and projectile origin are retained. `FixLauncherRearBore.luau` updates the combat template and both reviewed showcase copies, backing them up first in ServerStorage. Source Blender/GLB/FBX rear-cap geometry is also separated for future imports. No Creator Store asset or replacement mesh upload is involved; live visual playtesting is left to the user.

## Curated mob impact/death sprites — September 22, 2026

User-supplied `C:/Users/Jeremiah/Downloads/ChatGPT Image Sep 21, 2026, 11_22_13 PM (1).png` and `(3).png` are copied unchanged into `combat/assets/mob-white-streaks-atlas.png` and `combat/assets/mob-red-splats-atlas.png`. Original sheets are 1254×1254 RGBA. Uploaded for the requested effects: white `rbxassetid://90006993019437`, red `rbxassetid://106280569442353`. EditableImage readback confirms both Roblox-served textures are 1024×1024; ImageRect coordinates account for that scaling. SHA-256: white `dcc39123d7baa37cd5c394ad5d426d4ada956fc8ccc7406aa116f8f4551f8255`, red `f92e74637a83c8f0b5e5dd5cb113fa58b19815dff3b4499b8a3473f28b2ba55a`.

Only three isolated white needles, three round red droplets and one irregular red splat are selected. `combat/assets/mob-fx-selection.json` records source rectangles and measured white sprite axes. The gold sheet and the second white sheet were not imported or used. No replacement artwork or external Creator Store model was used.

`MobImpactVisuals.luau` renders short radial white streaks and randomized round red particles; death red particles occupy an uneven expanding perimeter. White rotation is radial angle minus the sprite's native longitudinal axis, so movement and orientation remain aligned. This replaces the previous blue/white procedural death clouds. Backups: `ServerStorage.BeforeCuratedMobImpactFX_20260922`. Scripts/asset selection are recorded locally; uploaded image assets are referenced by ID. Module load and both Rojo builds passed; no live visual/playtest was performed.

## Playing-card backs and independent cards — September 22, 2026

`combat/CardPresentation.luau` adds original crimson diamond-lattice backs, cream borders and center seals as native Parts/SurfaceGui frames. No external art or asset upload. Original reviewed face meshes are retained. Each deck assembly now contains independent Deck, HeartCard, SpadeCard and DiamondCard models; cards have individual mesh pivots and ProjectileCard/CardIndex metadata for future launch behavior. The deck remains an organizational parent, not a rigid joint. `InstallCards.luau` applies the change to both showcases and WeaponTemplates.18 and copies the existing combat module capability policy.

`CardShowcase.client.luau` and the equipped combat renderer use phase-offset bob, drift and small flutter on each card. Existing attack/damage behavior is unchanged; projectile launch integration is future work. Source scripts synced to Studio. Edit viewport visually checked from the previously blank back side. Actual Studio client: all three display cards moved independently over 0.65 seconds (0.053/0.066/0.082 studs), deck displacement was zero, and client error log was empty after startup fixes. Equipped deck clone and relative card motion also checked. Both Rojo projects packaged successfully. Multiplayer and published sessions were not tested.


## Gun muzzle flash artwork � September 22, 2026

The user's `ChatGPT Image Sep 18, 2026, 12_09_04 AM (2).png` is byte-identical to `combat/assets/bullet-impact-atlas.png` (SHA-256 dd541d9aa1dd19e4668e225e3a25cc1653bebba697465f0b34f77663d3157269). Muzzle flashes reuse existing uploaded image `rbxassetid://131707953627421`, selecting three top-row stars via ImageRect. Impacts retain separate row 2/4 selections. `combat/assets/muzzle-fx-selection.json` records rectangles and 1254-to-1024 texture scaling. No pixels were edited, no new artwork generated, and no new asset uploaded.

## Shop weapon icons — September 22, 2026

35 user-supplied PNGs from `C:/Users/Jeremiah/Downloads/weapon icons` are copied unchanged into `ui/assets/weapons/`. Original filenames, weapon IDs and uploaded Roblox image IDs are recorded in `ui/assets/weapons/provenance.json`. Images were visually matched to the weapon catalogue and uploaded for shop, owned inventory, and creative inventory presentation. No executable content is imported. Glock (00) was not supplied and retains its reviewed 3D model preview. Crystal currency reuses the existing approved shard image `119781825571908` and crop. Other item illustrations retain the existing icon library; no new item artwork was supplied.

### Glock icon follow-up

User supplied `C:/Users/Jeremiah/Downloads/ChatGPT Image Sep 22, 2026, 10_24_04 PM.png`; copied unchanged to `ui/assets/weapons/00.png` and uploaded as `rbxassetid://71681559132362`. The shared shop/inventory icon map now covers all 36 weapons.


## Weapon behavior pass � September 23, 2026

Modeled kunai, boomerang, Molotov, eggs, bowling ball/pins and Mjolnir projectiles reuse the existing reviewed `WeaponTemplates` static meshes. Egg and pin reserve groups are runtime copies, not new imports. Gloves retain the existing two independently posed meshes. Steak wobble is procedural; no skeletal asset or image generation was required. Poison fields use Roblox's bundled `rbxasset://textures/particles/smoke_main.dds`, tinted green; fire uses native Roblox Fire visuals. Small tail puffs are original code-created parts. No new third-party models, external images, asset uploads or imported scripts were used. See `combat/WEAPON_BEHAVIOR_PASS.md` for behavior and test details.

## HUD and lobby icons - September 27, 2026

Ten user-generated icons from `C:/Users/Jeremiah/.codex/generated_images/01a0d65c-b68c-7d70-b869-e5efdcdbf661` (play portal, chest, anvil, loadout case, shop bag, quest scroll, achievement clipboard, profile card, party, settings gear) were trimmed to their alpha bounds, padded 4% and resized to 256x256 in `ui/assets/hud/`, then uploaded through Studio. Source filenames and Roblox image IDs are in `ui/assets/hud/asset-ids.json`; `ui/UITheme.luau` references them. The two grass textures and two lobby concept renders in the same folder were not used for UI. No key icon was supplied, so key balances use the chest icon; the existing reserved gem art (102213113777434) marks Gems.

Rarity card frame `ui/assets/rarity.png` (2026-09-27): original art from `ui/build_assets.py` (same octagon as `panel`, white ring and corners for tinting), uploaded as rbxassetid://83616445506728.

User-supplied emerald and crystal-bag images (2026-09-27, from chat) trimmed to 256x256 in `ui/assets/hud/emerald.png` (rbxassetid://107205947937384) and `shard-bag.png` (rbxassetid://129322350142524). `ui/assets/panelplain.png` (105310886449973) and `corners.png` (122511819290059) are original art from `ui/build_assets.py`; they replace the earlier `rarity.png`.

Store effect textures (2026-09-27): `ui/assets/sunburst.png` (rbxassetid://75268019571051) and `ui/assets/glow.png` (rbxassetid://101092695897243), original, generated by `ui/build_assets.py`.

Queue-pad light column texture (2026-09-27): `lobby/assets/pad-light-column.png` (rbxassetid://81762721388354). It is original and generated by `lobby/build_pad_light.py`: a white horizontal alpha fade used as Beam.Texture, clear at both edges because beams wrap textures. Two earlier versions are unused. rbxassetid://135008682861366 mapped the wrong way. rbxassetid://126394008370824 had a solid bottom edge that wrapped into a bright line along the column's top.

## Skill Tree - September 27, 2026

Skill Tree star icon `ui/assets/skills/skill-tree.png` (rbxassetid://85339341316383): original art generated by `ui/assets/skills/make_skill_icon.py` (faceted low-poly lime sparkle with two gold twinkles, ink outline to match the stat icons). Node icons reuse the level-up stat icons (`LevelUpCatalog.IconIds`).

Skill Tree sounds from the Roblox-licensed ProSoundEffects library (free, Creator Store): open whoosh 9120733055 "Whoosh Rising Swish Airy Various Pitches 1 (SFX)", purchase chime 9116394545 "Magic Glows Soft Clusters Of Chiming Hits 1 (SFX)". Only the audio is used; ids live in `combat/SkillTreeConfig.luau` (`Sounds`).

Lobby SKILLS button icon `ui/assets/hud/skill-tree.png` (rbxassetid://70956867630986): user-supplied rune stone (`Downloads/ChatGPT Image Sep 27, 2026, 09_20_46 PM.png`, 2026-09-27), trimmed to alpha bounds and resized to 256x256. The green star above stays as the tree's centre node.

Padlock icon `ui/assets/lock.png` (2026-09-27): original art from `ui/build_assets.py` (steel shackle, brass body), uploaded as rbxassetid://89513131203273. Replaces the frame-drawn padlock in RunSetupUI/ArmoryUI and the big lock on locked maps.

## Chest screen, chest island and opening VFX — 2026-09-28

- **Chest models:** repository-authored in `../blender-chest-kit/` (one Blender file per tier). `package_studio.py` joins all five into `exports/fbx/chest-kit-studio.fbx` for one Studio 3D Import; `studio-install-chests.luau` turns the import into `ReplicatedStorage.ChestModels.<Tier>` (TextureID baked atlases, Neon glow parts, lid hinge attributes). No Creator Store geometry.
- **Chest icons** (UI, rendered by `package_studio.py` from the same meshes, `../blender-chest-kit/previews/icon-<tier>.png`): Wooden 107136053285951, Silver 103320236733137, Gold 88627612681717, Magical 92681366357642, Legendary 81753880209961.
- **VFX textures** (repository-authored by `ui/assets/chest-vfx/make_chest_vfx.py`, white on transparent, tinted in engine): glow 82171749127523, star 119142062258395, streak 95826913551457, wisp 98763107983691, ring 112313196019616, rays 95423827430619, shaft 81309750877710, mote 88119068890270. Ids also in `ui/assets/chest-vfx/asset-ids.json`.
- **Chest island** (`lobby/InstallChestIsland.luau`): built only from clones of the lobby's own reviewed meshes (South island top/cliff, portal pads, a boulder, broadleaf trees, lanterns, shrubs, ferns, flowers, grass tufts).
- **Sounds** (audio only, ids in `ui/ChestFX.luau` `Sounds`): ProSoundEffects library (Roblox-licensed, free): shakes 9119127069 "Shutter Bangs Rattle Shaking Wood Hits 11 (SFX)" and 9119126475 "... Wood Hits 4 (SFX)", charge 9120733055 "Whoosh Rising Swish Airy Various Pitches 1 (SFX)", lid 9120873380 "Wooden Chest Open Close Cedar Box 1 (SFX)", reveal chime 9116394545 "Magic Glows Soft Clusters Of Chiming Hits 1 (SFX)". Creator Store (free, third-party, not auditioned yet): burst 119620526223720 "Explosion Prize" (bmxcre), Legendary sting 128460880879263 "Rare Achievement" (pasha323434). Swap either in `ChestFX.Sounds` if they sound wrong.

## Game sound effects (2026-09-28)

User-picked audio for weapons, mob hits, UI and the player, processed by `audio/process_audio.py` (trimmed to start instantly, tails shortened, levelled, limited to -1 dBFS) and uploaded to EggaRowls (user 341854066) through the Creator Hub bulk uploader. Slot → id map: `audio/uploaded_ids.json`; the originals are kept unchanged in `audio/source/`. `StarterPlayerScripts.RogueliteSounds` (`audio/RogueliteSounds.client.luau`) plays them all. UI modules cue sounds through UITheme's `T.sound`, which fires `ReplicatedStorage.RogueliteSoundCue`; that BindableEvent is saved in the place and must be sandboxed with UITheme's capabilities (`audio/InstallSoundCue.luau`), or sandboxed callers cannot fire it.

- **Pixabay** (Pixabay Content License, free commercial use, no credit required; the file name is uploader-title-id): `floraphonic-swing-whoosh-5-198498` → swing_light, `floraphonic-swing-whoosh-weapon-1-189819` → swing_blade, `freesound_gamestudio-attack-match-1-394505` → hit_thud, `dragon-studio-electric-discharge-386160` → zap, `freesound_community-gooey-squish-14820` → mob_goo, `soundshelfstudio-ui-error-pop-515668` → ui_error, `apebble-fart-4-228244` → shot_fart 137155830413625 (Fart Gun; 0.78 s of leading silence and the tail trimmed), `freesound_community-wood-crack-1-105890` → chest_shake_1/2 (split in two, pitched up 1.25×, bass boost, splinter tail cut; Gold chest only via `ChestFX.Sounds.GoldShake1/2`).
- **User-supplied, source unknown** (the user renamed or downloaded these and does not know where they came from; confirm licences before a public release): `pan` → swing_pan, `heavy swoosh 1/2` → swing_heavy/swing_heaviest, `quick soft swoosh` → swing_soft, `blunt attack` → hit_blunt, `bodyShotOomph_C.ogg` → hit_punch, `pistol` → shot_pistol, `draco` → shot_draco, `shotgun_shoot_B.ogg` → shot_shotgun, `rocket_shoot_B.ogg` → shot_rocket, `icegun_shoot_A/B/C.ogg` → shot_magic_a/b/c, `zombies-slimes-spiders` → mob_zombie, `crabs-and-scorpions` → mob_crab, `skeeltons` → mob_skeleton, `ghost-mummies-shaman` → mob_ghost, `ui click.ogg` → ui_click, `equip` → ui_equip, `ingame-purchase` → ui_purchase, `upgrade` → ui_upgrade, `player damage` → player_damage, `player death` → player_death.
- **Power Washer loop** `washer_loop` 131922039707440 (uploaded 2026-09-28): user-supplied `water.mp3`, source unknown. `process_audio.py` `LOOPS` cuts 3.4 s of steady spray, crossfades 0.4 s of its tail into its head (equal-power) so it loops seamlessly, and writes three copies; `RogueliteSounds` plays it with `LoopRegion` = 3.4-6.8 s while the washer keeps firing.
- **Crystal pickup** `crystal_pickup` 119199604552182: user-supplied `pick up.mp3` (source unknown). `process_audio.py` `SPRITES` cut its 12 plops apart, dropped a -29 dB blip and the odd last plop, levelled the other 11 and packed them low-to-high pitch into one file (slices in `audio/sprites.json`); `RogueliteSounds` plays one slice per crystal as the pull lands, climbing the ladder on quick pickups.
- Processed but not uploaded (not used yet): `chest opened` (the current chest open sounds stay), `freesound_gamestudio-material-gold-394476` (Pixabay).

## Music (2026-09-28)

Sixteen user-picked Pixabay tracks (Pixabay Content License; file names are uploader-title-id), loudness-matched to -16 LUFS by `audio/music/process_music.py` and uploaded to EggaRowls. Ids and source names: `audio/music/music_ids.json`; the audio itself is git-ignored (`audio/music/.gitignore`). `StarterPlayerScripts.RogueliteMusic` (`audio/music/RogueliteMusic.client.luau`) plays them: regular playlist in runs, boss playlist for bosses and intense Endless moments, silent lobby. Roblox moderation rejected four uploads, which are left out of the playlists: alexgrohl-retro-electronic-535019, jonasblakewood-retro-lightning-350632, joyinsound-valley-of-silicon-403396 and tunetank-intense-cyberpunk-techno-music-348920.
Added the same day as replacements (both passed moderation and load): echoes_of_lumen-techno-music-energetic-electro-583432 (regular_12, 131272353616369) and alex-morgan-phonk-brazilian-phonk-phonk-music-545509 (boss_06, 89877873691224).

## Map-boss VFX kit and sounds (plan F) — 2026-09-30

- **Boss models** (King Crab, Frost Cyclops, Pharaoh, Inferno Dragon): repository-authored in `../king-crab-boss/`, `../frost-cyclops-boss/`, `../pharaoh-boss/`, `../dragon-boss/` (`exports/game/<Boss>_Studio.fbx`, Studio 3D Importer). `combat/bosses/InstallMapBossTemplates.luau` turns the raw imports (`ServerStorage.MapBossRawImports`) into `ServerStorage.RogueliteNPCs.<Id>_NPC` with the importer's textures as `MeshPart.TextureID`; the glow sections (`EyeGlow`, `LavaGlow`) are untextured Neon. No Creator Store geometry.
- **Effect meshes**: repository-authored in `../boss-vfx-kit/` (`exports/fbx/AllMeshes.fbx`), installed as the children of `ReplicatedStorage.RogueliteCombat.BossVfxAssets`. Their atlases came in with the import: IceSpikes_BaseColor 91357789960141, MoltenRock_BaseColor 139356687572385, Obelisk_BaseColor 114053127280741, ShellChip_BaseColor 118642052631884.
- **Effect textures** (repository-authored, `../boss-vfx-kit/textures/<name>.png`, uploaded through the Studio MCP; ids in `combat/bosses/BossVfxAssets.luau`): ShockwaveRing 73745779894728, ImpactStar 132900122818559, DustPuff_Flipbook4x4 108391383565832, WaterSplash_Flipbook4x4 99255856772433, Bubble 85054572566506, SandSpray_Flipbook4x4 102816833190885, HieroglyphCircle 91511521884695, Hieroglyphs_Flipbook4x4 101187847335243, SandBurst_Flipbook4x4 139727948521833, CurseOrb 74654623742949, FrostFloor 123297047697784, FrostRing 113178010280765, FrostMist_Flipbook4x4 107929552453550, SnowSparkle 131064842159851, LavaCracks 79279164324150, ScorchMark 92423458342016, Flame_Flipbook4x4 132081298787809, Ember 116159534169534, SmokePuff_Flipbook4x4 133683398795549, MoltenRock_EmissiveMask 85870086290990.
- **Sounds** (audio only; cue → id in `combat/bosses/BossVfxAssets.luau` `Sounds`). All are Creator Store (free, third-party), creator ProSoundEffects ("Courtesy of Pro Sound Effects"), played through the `RogueliteSFX` SoundGroup:
  - King Crab: crab_windup 9114493410 "Floor Creaks 3 (SFX)", crab_slam 9113469292 "Body Fall 1 (SFX)", crab_scuttle 9125917343 "Scrolling Graphic Clicks Small Chattering Me (SFX)", bubbles 9120309620 "Underwater Bubbles Deeper Med 6 (SFX)".
  - Pharaoh: pharaoh_windup 9116394545 "Magic Glows Soft Clusters Of Chiming Hits 1 (SFX)", pharaoh_charge 9120733055 "Whoosh Rising Swish Airy Various Pitches 1 (SFX)" (both already used by the chest screen), pharaoh_bolt 9114157695 "Doppler Whooshes Crackly Airy Bursts 2 (SFX)", stone_rumble 9118692384 "Rocks Movement 5 (SFX)", sand_burst 9118597967 "Rock Hit Dirt Impact 10 (SFX)".
  - Frost Cyclops: ice_windup 9119628762 "Steam Whoosh Phased 1 (SFX)", ice_slam 9118585250 "Rock Cracks Big Boulder Hits 4 (SFX)", ice_crack 9119311395 "Snowball Hit Vehicle Window 1 (SFX)", ice_wave 9118588626 "Rock Drops 10 Ft High Onto Rocks Dirt 6 (SFX)".
  - Inferno Dragon: dragon_windup 9113971433 "Creature Growls Lion 2 (SFX)", dragon_inhale 9126102843 "Time Warp Searing Build Up Large Suck Rumble (SFX)", fire_breath 9117987723 "Pyro Fire Ball Burst 15 (SFX)", tail_whoosh 9120727859 "Whoosh Giant Swish By 8 (SFX)", ground_quake 9125484359 "Deep Hits Big Reverberant Booms Rumbling Tai (SFX)", lava_hiss 9125579324 "Giant Steam Chuff Air Burst Through The Tube (SFX)", wing_flap 9120771885 "Wing Flaps 29 (SFX)".
  - The Toolbox had no free, first-party ice or magic-hum recordings, so the ice cues are rock/glass/snow hits and the Pharaoh charge is an airy riser; the effects modules pitch them. Swap an id in `BossVfxAssets.Sounds` if one sounds wrong.

## Godly weapons (plans/2026-10-01-G-godly-weapons.md), 2026-10-01

- **Models:** `WeaponTemplates.36`–`41` are the six Blender-built Godly weapons (`weapon-models/godly/<weapon>/`).
  - They were imported together as `weapon-models/godly/studio-import/Godly_Weapons.fbx`.
  - Their BaseColor atlases were uploaded as Images and set as `MeshPart.TextureID`. The ids are in `weapon-models/godly/studio-import/studio-asset-ids.json`.
- **Icons:** `ui/assets/weapons/36.png`–`41.png`. These are the user's own OpenAI Astra renders, sent in chat and converted from webp to png unchanged.
  - Uploaded as `rbxassetid://107381256092734` (Scythe), `111945334431090` (Trident), `86787843399026` (Storm Bow), `112261102861999` (Daggers), `90868128996170` (Vampire Blade) and `74294498569772` (Ray Gun).
  - Provenance is in `ui/assets/weapons/provenance.json`.
- **VFX textures:** original, painted by `weapon-models/godly/vfx/paint_godly_vfx.py` (white on transparent, tinted in game):
  - GodlySoftGlow `119796255132573`
  - GodlySlash `105397482701607`
  - GodlyLightning `100197465776159`
  - GodlyWisp `96655998397870`
  - GodlySkull `119217505644088`
  - GodlyPixel `133657841459974`

  Also reused from BossVfxAssets: ShockwaveRing, ImpactStar, the WaterSplash and SmokePuff flipbooks, Bubble and Ember.
- **Sounds:** no new uploads. The Godly weapons reuse the kit in `RogueliteSounds` (pitched), plus three Roblox library sounds the map bosses already use:
  - `water_bubbles` 9120309620 (Underwater Bubbles);
  - `thunder_crack` 9114157695 (Doppler Whooshes Crackly Airy Bursts);
  - `ghost_rise` 9120733055 (Whoosh Rising Swish Airy).

## Egg merchant, egg pedestal and egg hatch — 2026-10-02

- **Models:** repository-authored in `../blender-egg-merchant-kit/` (`build_egg.py`, `build_merchant.py`), from the user's concept `../art-references/egg-merchant/egg-merchant-concept-v1.png` (without the egg in the hood and the belt on the big egg). `package_studio.py` joins both into `exports/fbx/egg-merchant-studio.fbx` for one Studio 3D Import; `lobby/InstallEggMerchant.luau` places them on the quest-board island. No Creator Store geometry.
- **Textures** (baked atlases, set as MeshPart.TextureID by the installer): egg kit `rbxassetid://140294240008480` (`textures/egg-kit-baked.png`), merchant `rbxassetid://130996618550776` (`textures/merchant-baked.png`).
- **Egg icon** (UI, `previews/icon-egg.png`): `rbxassetid://117887028525234` (EggConfig.Icon, the EGGS stand label).
- **Sounds:** no new uploads. The hatch reuses ChestFX sounds: the Gold chest's wood-crack taps for the two cracks, Charge, Burst, Chime and the Legendary sting.
