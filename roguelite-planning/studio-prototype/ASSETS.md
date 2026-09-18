# Zombie asset provenance

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

## Bullet impact artwork

User-supplied `ChatGPT Image Sep 18, 2026, 12_09_04 AM (2).png` is retained unchanged at `combat/assets/bullet-impact-atlas.png`. Roblox image: `rbxassetid://131707953627421`. Only rows 2 and 4 are used, at 80%/20% frequency. Runtime coordinates scale from the 1254px source to the 1024px uploaded texture.
