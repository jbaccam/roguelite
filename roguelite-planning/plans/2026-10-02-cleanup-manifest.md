# Place cleanup manifest (launch audit L3, L4)

Read-only scan of place 107877054949326 in Studio Edit, 2026-10-02. Nothing in the place was changed. The cleanup script is `studio-prototype/tools/CleanupPlace.luau`; its `MANIFEST` matches the tables below.

**The place was changing during the scan.** Another session was polishing the maps: `DesertBasinArena` moved from `ServerStorage.InactiveAreas` into Workspace, `BeachCoveArena` went from 1,413 to 1,408 descendants, and three new backups appeared (`BeforeBiomeFollowup_20261002`, then `BeforeBiomeFollowup`; the first grew from 1,710 to 2,295 objects). So run the dry run right before applying and fix any row it reports as changed.

## Totals

| Group | Targets | Objects | Scripts | Verdict |
|---|---:|---:|---:|---|
| Backups made before today | 88 | 7,824 | 515 | safe |
| Old lobby versions | 10 | 5,961 | 0 | safe |
| Old raw imports and lobby kits | 19 | 1,396 | 0 | safe |
| Workspace test models, strays, empty or inert folders, Baseplate | 11 | 338 | 0 | safe |
| **Default run (`apply=true`)** | **128** | **15,519** | **515** | |
| Today's backups (opt-in) | 10 | about 19,700 and growing | 1 | risky |
| `Workspace.RogueliteEnvironmentAssets` (opt-in) | 1 | 4 | 0 | risky |
| Kept in ServerStorage | 20 | about 9,840 | 14 | keep |

Also in the default run: anchor `Workspace.RogueliteLobby.Scenery.Lantern_Post_41`.

"Objects" counts each root and all of its descendants. "Scripts" counts every Script, LocalScript and ModuleScript inside, including the root. At the last read, ServerStorage had 147 top-level children and 44,853 objects. The audit's figure of about 26,000 predates today's map-polish backups.

## How to run

1. Save an archive copy first (File > Save to File As), as audit L4 says.
2. Start `python roguelite-planning/studio-prototype/tools/dev_server.py`, then in Studio Edit (execute_luau or the command bar):

```lua
local HS=game:GetService('HttpService')
local run=loadstring(HS:GetAsync('http://127.0.0.1:8934/studio-prototype/tools/CleanupPlace.luau?t='..os.clock(),true))()
return run()               -- dry run: verifies every row and check, changes nothing
-- return run({apply=true}) -- removes the safe rows and anchors the lantern
```

Options: `alsoDelete = {ids}` opts into risky rows (the dry run prints the ids); `restoreLantern = true` also puts the lantern back on its spot with a lens; `useOuterRecording = true` is explained below.

How it works: every selected row must match its parent, name, class and descendant count, plus its pivot for the duplicate names. Then 5 checks must pass: no outside object references a target, no new runtime script names one, no runtime script names a tag a Workspace target carries, nothing that matters rests on the Baseplate, and the lantern is where the scan found it. If any of this fails, nothing changes. Removal sets `Parent = nil` rather than calling Destroy, inside one `ChangeHistoryService` recording, so one Undo restores everything until the place is saved and closed. If something fails partway, it puts back what it already removed.

One caveat: during this scan, `ChangeHistoryService:IsRecordingInProgress()` was already true inside an execute_luau call, probably because the MCP tool wraps calls in its own recording. If `TryBeginRecording` returns nil, the script stops. Run it again with `useOuterRecording = true` to work inside the open recording. Undo then belongs to that wrapper.

## Workspace

| Path | Class | Desc. | Where (pivot) | Verdict | Reason |
|---|---|---:|---|---|---|
| `Workspace.ZombieVariantPreviews` | Folder | 120 | 3 rigs at (41,1.8,38.6), (48,4,38.2), (62,6.9,37.9) | safe | Baby, Mutant and HammerBoss preview rigs. They stand on the Baseplate near the world origin. BossService:38 uses `FindFirstChild` (nil is fine). The only thing that breaks is the disposable `hammer-boss/test_client_poses.luau`. |
| `Workspace.Zombie_R15_ProvidedTextures_Studio` | Model | 192 | (35, 3.03, 39) | safe | The display/practice zombie, anchored at the origin. `PracticeTarget` is Studio-only: it waits 10 s, gets nil and exits. RogueliteZombieChase:165,375 use `FindFirstChild` (nil is fine). It is also the dummy for the disposable `combat/ArcAttackTests.luau` (CURVED_ATTACKS.md), which would need another target. |
| `Workspace.Log_Master` | Model | 2 | (162, 0, 118) | safe | Stray (see Duplicate names). |
| `Workspace.Log_Master` | Model | 2 | (-11.75, 0, 25.18) | safe | Stray. |
| `Workspace.Log_Master` | Model | 2 | (0.99, 0, 38) | safe | Stray, tagged `_BrushtoolBrushed`. |
| `Workspace.13_Rock_Cluster` | Model | 2 | (78.07, 0, 48.66) | safe | Stray. |
| `Workspace.LukeSandboxTesting` | Folder | 0 | | safe | Empty, nothing refers to it. |
| `Workspace.RogueliteWeaponShowcase` | Folder | 1 | | safe | Holds only an empty `DisplayBases` folder. RogueliteCombat:106/118 and CardShowcase:4-5 look it up with `FindFirstChild` and skip it when missing. |
| `Workspace.RogueliteWeaponShowcase_PlaySize` | Folder | 1 | | safe | Same as above. |
| `Workspace.Lighting` (a Folder, not the service) | Folder | 4 | | safe | SunRays, DepthOfField, ColorCorrection and Bloom, with values different from `game.Lighting`. Post effects do nothing under Workspace. The client `MapEnvironment` script fills `game.Lighting` from `ReplicatedStorage.MapEnvironments`. No script looks this folder up. |
| `Workspace.Baseplate` | Part | 1 | (0, -8, 0), 2048×16×2048 | safe | Nothing that matters rests on it (see Baseplate). |
| `Workspace.RogueliteEnvironmentAssets` | Folder | 3 | Evergreen_Master at (308, 9, 40) | risky | Not on your list. It holds the master evergreen import (`blender-master-evergreen/studio-organize-import.luau`). It is anchored and will float if the Baseplate goes. Opt-in id: `Workspace/RogueliteEnvironmentAssets`. |

Fix: `Workspace.RogueliteLobby.Scenery.Lantern_Post_41` gets anchored (see Lantern).

## ServerStorage: backups made before today (safe)

| Path | Class | Desc. | Verdict | Reason |
|---|---|---:|---|---|
| `ServerStorage.BeforeShardAura_20260922` | LocalScript | 0 | safe | A loose LocalScript, the pre-shard-aura copy. |
| `ServerStorage.BeforeKatanaCombat` | Folder | 0 | safe | Undo copy (undated). |
| `ServerStorage.BeforeSixWeaponSlots` | Folder | 3 | safe | Undo copy (undated), 2 old scripts. |
| `ServerStorage.MapPBR_Backup_20260920` | Folder | 1 | safe | One old floor Texture. |
| `ServerStorage.BeforeWeaponFollow_20260921` | Folder | 3 | safe | Undo copy (2026-09-21), 3 old scripts. |
| `ServerStorage.BeforeMovementTuning_20260921` | Folder | 2 | safe | Undo copy (2026-09-21), 2 old scripts. |
| `ServerStorage.BeforeDirectionalFollow_20260921` | Folder | 2 | safe | Undo copy (2026-09-21), 2 old scripts. |
| `ServerStorage.BeforeAirSpeedBoost_20260921` | Folder | 2 | safe | Undo copy (2026-09-21), 2 old scripts. |
| `ServerStorage.BeforeKatanaDragCorrection_20260921` | Folder | 3 | safe | Undo copy (2026-09-21), 1 old script. |
| `ServerStorage.BeforeWeaponSpacingOrientation_20260921` | Folder | 15 | safe | Undo copy (2026-09-21), 3 old scripts. |
| `ServerStorage.BeforeIndependentWeaponFollow_20260922` | Folder | 6 | safe | Undo copy (2026-09-22), 2 old scripts. |
| `ServerStorage.BeforeLauncherRearBoreScripts_20260922` | Folder | 1 | safe | Undo copy (2026-09-22), 1 old script. |
| `ServerStorage.BeforeLauncherRearBore_20260922` | Folder | 9 | safe | Undo copy (2026-09-22). |
| `ServerStorage.BeforeExcaliburSwingAndStaggeredFollow_20260922` | Folder | 3 | safe | Undo copy (2026-09-22), 3 old scripts. |
| `ServerStorage.BeforeExcaliburReturnAndReach_20260922` | Folder | 4 | safe | Undo copy (2026-09-22), 4 old scripts. |
| `ServerStorage.BeforeWeaponAttackStagger_20260922` | Folder | 3 | safe | Undo copy (2026-09-22), 3 old scripts. |
| `ServerStorage.BeforeIndependentAttackClocks_20260922` | Folder | 1 | safe | Undo copy (2026-09-22), 1 old script. |
| `ServerStorage.BeforeMirroredExcaliburSwings_20260922` | Folder | 3 | safe | Undo copy (2026-09-22), 3 old scripts. |
| `ServerStorage.BeforeCuratedMobImpactFX_20260922` | Folder | 3 | safe | Undo copy (2026-09-22), 3 old scripts. |
| `ServerStorage.BeforeSeparateVisibleHitImpact_20260922` | Folder | 1 | safe | Undo copy (2026-09-22), 1 old script. |
| `ServerStorage.BeforeStrongerHitImpacts_20260922` | Folder | 1 | safe | Undo copy (2026-09-22), 1 old script. |
| `ServerStorage.BeforeAllMeleeNormalSwings_20260922` | Folder | 4 | safe | Undo copy (2026-09-22), 4 old scripts. |
| `ServerStorage.BeforeKatanaTrailAndTestControls_20260922` | Folder | 7 | safe | Undo copy (2026-09-22), 7 old scripts. |
| `ServerStorage.BeforeKatanaSwingEdge_20260922` | Folder | 1 | safe | Undo copy (2026-09-22), 1 old script. |
| `ServerStorage.BeforeControlledChainSwings_20260922` | Folder | 2 | safe | Undo copy (2026-09-22), 2 old scripts. |
| `ServerStorage.BeforeChainEndDirection_20260922` | Folder | 3 | safe | Undo copy (2026-09-22), 3 old scripts. |
| `ServerStorage.BeforeCrystalShards_20260922` | Folder | 8 | safe | Undo copy (2026-09-22), 8 old scripts. |
| `ServerStorage.BeforeShardMagnet_20260922` | Folder | 5 | safe | Undo copy (2026-09-22), 5 old scripts. |
| `ServerStorage.BeforeCurvedAttacks_20260922` | Folder | 10 | safe | Undo copy (2026-09-22), 10 old scripts. |
| `ServerStorage.BeforeShardXP_20260922` | Folder | 5 | safe | Undo copy (2026-09-22), 5 old scripts. |
| `ServerStorage.BeforeRetarget_20260922` | Folder | 6 | safe | Undo copy (2026-09-22), 6 old scripts. |
| `ServerStorage.BeforeChainReadability` | Folder | 38 | safe | Undo copy (undated). |
| `ServerStorage.BeforeMuzzleFlash_20260922` | Folder | 0 | safe | Empty. Same name as the next row; matched by descendant count. |
| `ServerStorage.BeforeMuzzleFlash_20260922` | Folder | 3 | safe | Same name as the row above; matched by descendant count. |
| `ServerStorage.BeforeWeaponBehaviorPass_20260923` | Folder | 6 | safe | Undo copy (2026-09-23), 6 old scripts. |
| `ServerStorage.BeforeSpringCombos_20260923` | Folder | 7 | safe | Undo copy (2026-09-23), 7 old scripts. |
| `ServerStorage.BeforeGripSwing_20260923` | Folder | 1 | safe | Undo copy (2026-09-23), 1 old script. |
| `ServerStorage.BeforeHammerRock_20260923` | Folder | 3 | safe | Undo copy (2026-09-23), 3 old scripts. |
| `ServerStorage.BeforeOverheadRhythm_20260923` | Folder | 2 | safe | Undo copy (2026-09-23), 2 old scripts. |
| `ServerStorage.BeforeAllOverheadReach_20260923` | Folder | 2 | safe | Undo copy (2026-09-23), 2 old scripts. |
| `ServerStorage.BeforeHammerBossContinuity_20260923` | Folder | 99 | safe | Undo copy (2026-09-23), 10 old scripts. |
| `ServerStorage.BeforeHammerBossSkinGrip_20260923` | Folder | 99 | safe | Undo copy (2026-09-23), 10 old scripts. |
| `ServerStorage.BeforeHammerBoss_20260923` | Folder | 3 | safe | Undo copy (2026-09-23), 3 old scripts. |
| `ServerStorage.BeforeHammerBossTraps_20260923` | Folder | 131 | safe | Undo copy (2026-09-23), 10 old scripts. |
| `ServerStorage.BeforeHammerBossHips_20260923` | Folder | 134 | safe | Undo copy (2026-09-23), 13 old scripts. |
| `ServerStorage.BeforeHammerBossLever_20260923` | Folder | 135 | safe | Undo copy (2026-09-23), 14 old scripts. |
| `ServerStorage.BeforeTravelAccuracy_20260923` | Folder | 12 | safe | Undo copy (2026-09-23), 12 old scripts. |
| `ServerStorage.BeforeHammerBossPolish_20260923` | Folder | 10 | safe | Undo copy (2026-09-23), 10 old scripts. |
| `ServerStorage.BeforeHammerBossWrist_20260923` | Folder | 9 | safe | Undo copy (2026-09-23), 9 old scripts. |
| `ServerStorage.BeforeHammerBossElbowHinge` | Folder | 9 | safe | Undo copy (undated), 9 old scripts. |
| `ServerStorage.BeforeHammerBossArmFlex_20260923` | Folder | 9 | safe | Undo copy (2026-09-23), 9 old scripts. |
| `ServerStorage.BeforeHammerBossExtendedReach` | Folder | 9 | safe | Undo copy (undated), 9 old scripts. |
| `ServerStorage.BeforeHammerBossFaceFollowThrough` | Folder | 9 | safe | Undo copy (undated), 9 old scripts. |
| `ServerStorage.BeforeDesignerShirt_20260924` | Folder | 8 | safe | Undo copy (2026-09-24), 8 old scripts. |
| `ServerStorage.BeforeHammerBossShoulderSweep` | Folder | 9 | safe | Undo copy (undated), 9 old scripts. |
| `ServerStorage.BeforeBossDirectRecovery` | Folder | 10 | safe | Undo copy (undated), 10 old scripts. |
| `ServerStorage.BeforeMobAttacks_20260927` | Folder | 1,241 | safe | Old copies of 123 scripts. |
| `ServerStorage.BeforeGreenThemeHUD_20260927` | Folder | 9 | safe | Undo copy (2026-09-27), 9 old scripts. |
| `ServerStorage.BeforeMonetizationDeath_20260927` | Folder | 7 | safe | Undo copy (2026-09-27), 7 old scripts. |
| `ServerStorage.BeforeQueuePads_20260927` | Folder | 6 | safe | Undo copy (2026-09-27), 3 old scripts. |
| `ServerStorage.BeforeStoreTabs_20260927` | Folder | 7 | safe | Undo copy (2026-09-27), 7 old scripts. |
| `ServerStorage.BeforeRunSetup_20260927` | Folder | 4 | safe | Undo copy (2026-09-27), 4 old scripts. |
| `ServerStorage.BeforeStorePolish_20260927` | Folder | 4 | safe | Undo copy (2026-09-27), 4 old scripts. |
| `ServerStorage.BeforeQueueScreen_20260927` | Folder | 7 | safe | Undo copy (2026-09-27), 7 old scripts. |
| `ServerStorage.BeforeStationFix` | Folder | 130 | safe | Undo copy from FixStations.luau. Also holds Lantern_Post_41's old WarmLens (see Lantern section). |
| `ServerStorage.BeforeArmoryScreen_20260927` | Folder | 4 | safe | Undo copy (2026-09-27), 4 old scripts. |
| `ServerStorage.BeforeLockedMapSilhouette_20260927` | Folder | 3 | safe | Undo copy (2026-09-27), 3 old scripts. |
| `ServerStorage.BeforeMobPicker_20260927` | Folder | 4 | safe | Undo copy (2026-09-27), 4 old scripts. |
| `ServerStorage.BeforeJumpableProps_20260928` | Folder | 135 | safe | Undo copy (2026-09-28). |
| `ServerStorage.BeforeWaveSpeedSpawns_20260928` | Folder | 11 | safe | Undo copy (2026-09-28), 11 old scripts. |
| `ServerStorage.BeforeLoadoutStarter_20260928` | Folder | 9 | safe | Undo copy (2026-09-28), 9 old scripts. |
| `ServerStorage.BeforeSoundEffects_20260928` | Folder | 9 | safe | Undo copy (2026-09-28), 9 old scripts. |
| `ServerStorage.BeforeSoundCueFix_20260928` | Folder | 2 | safe | Undo copy (2026-09-28), 2 old scripts. |
| `ServerStorage.BeforeMusicAndSliders_20260928` | Folder | 4 | safe | Undo copy (2026-09-28), 4 old scripts. |
| `ServerStorage.BeforeThreeArenas_20260930` | Folder | 6 | safe | Undo copy (2026-09-30), 6 old scripts. |
| `ServerStorage.BeforeBossSync_20260930` | Folder | 8 | safe | Undo copy (2026-09-30), 8 old scripts. |
| `ServerStorage.BeforeMapBoss_20260930` | Folder | 405 | safe | Undo copy (2026-09-30). |
| `ServerStorage.BeforeBossBalance_20260930` | Folder | 9 | safe | Undo copy (2026-09-30), 9 old scripts. |
| `ServerStorage.BeforeHammerCharge_20260930` | Folder | 7 | safe | Undo copy (2026-09-30), 7 old scripts. |
| `ServerStorage.BeforeOriginalArenaRefresh_20261001` | Folder | 988 | safe | Undo copy (2026-10-01), 1 old script. |
| `ServerStorage.BeforeGeneratedItemIcons_20261001` | Folder | 7 | safe | Undo copy (2026-10-01), 7 old scripts. |
| `ServerStorage.BeforeTemplateScale_20261001` | Folder | 3,522 | safe | NPC templates before the scale-1 fix; RogueliteNPCs holds the fixed ones. |
| `ServerStorage.Weapon_Material_Correction_Backup` | Folder | 69 | safe | Undo copy from ApplyShowcaseCorrections.luau. |
| `ServerStorage.SkyBackup_BeforeOriginalPaintedClouds` | Folder | 3 | safe | Three old Sky objects. |
| `ServerStorage.GrassPatch_Originals_20260927` | Folder | 33 | safe | Grass patches before the Blender grass swap. |
| `ServerStorage.MapGrouping_20260928` | Folder | 201 | safe | GroupMapAreas.luau undo log (201 ObjectValues). Its UNDO is moot: the maps have since moved to x ≈ ±5000. |
| `ServerStorage.ZombiePreviousDecalHead` | Part | 7 | safe | The zombie head replaced by ApplyFullHeadUV / CreateNativeZombie. |
| `ServerStorage.EggMerchantBackup` | Folder | 1 | safe | Practice_Dummy_86, moved out by InstallEggMerchant. EggMerchantSetup recreates the folder if needed. |

## ServerStorage: old lobby versions (safe)

| Path | Class | Desc. | Verdict | Reason |
|---|---|---:|---|---|
| `ServerStorage.RogueliteLobby_PreV2` | Model | 1,550 | safe | Whole lobby, version 1 (Origin -1400,120,0). |
| `ServerStorage.RogueliteLobby_PreV3` | Model | 1,969 | safe | Whole lobby, version 2. |
| `ServerStorage.LobbyStations_PreV4_20260925_104024` | Folder | 44 | safe | Earlier lobby state. |
| `ServerStorage.LobbyStations_PreV4_20260925_104329` | Folder | 100 | safe | Earlier lobby state. |
| `ServerStorage.QuestBoard_BeforeGuildNotices_20260925_110739` | Folder | 4 | safe | Earlier lobby state. |
| `ServerStorage.Lobby_BeforeCohesionV6_20260925_123925` | Folder | 940 | safe | Lobby before the V6 cohesion pass. |
| `ServerStorage.Islands_BeforeCliffsV7_20260925_203940` | Folder | 19 | safe | Earlier lobby state. |
| `ServerStorage.Islands_BeforeCliffsV8_20260925_211538` | Folder | 29 | safe | Earlier lobby state. |
| `ServerStorage.Lobby_BeforeV9_20260927_170029` | Folder | 1,283 | safe | Lobby before the V9 rebuild. |
| `ServerStorage.Lobby_BeforeLeaderboards_20260930_001400` | Folder | 13 | safe | Earlier lobby state. |

## ServerStorage: old raw imports and kits (safe)

| Path | Class | Desc. | Verdict | Reason |
|---|---|---:|---|---|
| `ServerStorage.Weapon_Import_FirstPass_Backup` | Model | 304 | safe | First weapon FBX import. Weapons ship from ReplicatedStorage. |
| `ServerStorage.Weapon_Import_Rigged_Backup` | Model | 350 | safe | Rigged weapon import kept by ArrangeShowcase.luau. |
| `ServerStorage.Weapon_Import_ExtraMetadata` | Model | 234 | safe | Leftover import shell (ArrangeShowcase.luau). |
| `ServerStorage.ZombieRawImports` | Folder | 32 | safe | Baby/Mutant raw imports; templates are installed in RogueliteNPCs. ZOMBIE_VARIANTS.md asked to keep them; no tool reads this folder. |
| `ServerStorage.HammerBoss_SourceImport` | Model | 16 | safe | Boss now ships from hammer-boss/finished/HammerBoss_NPC.rbxmx via Rojo. |
| `ServerStorage.RegularEnemyRawImportsHistory` | Folder | 177 | safe | werewolf/frozen-knight before their rebuild. |
| `ServerStorage.RogueliteLobbyKit` | Folder | 18 | safe | Superseded lobby kit; the live lobby keeps its own copies. |
| `ServerStorage.RogueliteLobby_ImportedOriginal` | Model | 18 | safe | Superseded lobby import. |
| `ServerStorage.RogueliteLobby_CleanImportedOriginal` | Model | 3 | safe | Superseded lobby import. |
| `ServerStorage.RogueliteLobbyKitV2` | Folder | 35 | safe | Superseded lobby kit; the live lobby keeps its own copies. |
| `ServerStorage.RogueliteLobbyV2_ImportedOriginal` | Model | 34 | safe | Superseded lobby import. |
| `ServerStorage.RogueliteLobbyLanding_ImportedOriginal` | Model | 1 | safe | Superseded lobby import. |
| `ServerStorage.RogueliteLobbyKitV3` | Folder | 42 | safe | Superseded lobby kit; the live lobby keeps its own copies. |
| `ServerStorage.RogueliteLobbyV3_ImportedOriginal` | Model | 42 | safe | Superseded lobby import. |
| `ServerStorage.RogueliteLobbyV3_CapImportedOriginal` | Model | 4 | safe | Superseded lobby import. |
| `ServerStorage.RogueliteStationKitV4` | Folder | 8 | safe | Superseded lobby kit; the live lobby keeps its own copies. |
| `ServerStorage.RogueliteLobbyKitV6` | Folder | 43 | safe | Superseded lobby kit; the live lobby keeps its own copies. |
| `ServerStorage.RogueliteIslandKitV7` | Folder | 8 | safe | Superseded lobby kit; the live lobby keeps its own copies. |
| `ServerStorage.RogueliteIslandKitV8` | Folder | 8 | safe | Superseded lobby kit; the live lobby keeps its own copies. |

## ServerStorage: today's backups (risky, opt-in)

The parallel map session made these today and was still writing them during the scan. They are its only undo. Leave them until that work is accepted, then refresh the counts with a dry run.

| Path | Class | Desc. (last read) | Verdict | Reason |
|---|---|---:|---|---|
| `ServerStorage.BeforeMainPineBeachRefresh_20261002` | Folder | 4,770 | risky | Pine/Beach before today's refresh. Holds 1 MapConfig ModuleScript and a water TerrainRegion. |
| `ServerStorage.BeforeMainDesertRefresh_20261002` | Folder | 1,358 | risky | Desert before today's refresh. |
| `ServerStorage.BeforeBiomePolish_20261002` | Folder | 6,681 | risky | All five maps plus MapEnvironments/EditorLighting before the biome polish. |
| `ServerStorage.BeforePinePlacementPolish_20261002` | Folder | 2,125 | risky | Pine before placement polish. |
| `ServerStorage.PineArchivedDuplicateVisuals_20261002` | Folder | 14 | risky | Duplicate Pine meshes taken out today. |
| `ServerStorage.BeforeBeachPlacementPolish_20261002` | Folder | 1,701 | risky | Beach before placement polish. |
| `ServerStorage.BeforeDesertPolish_20261002` | Folder | 11 | risky | Sphinx pieces. |
| `ServerStorage.PineContactPass2Backup_20261002` | Folder | 2 | risky | One rock filler. |
| `ServerStorage.BeforeBiomeFollowup_20261002` | Folder | 1,718 in the manifest, 2,295 at the last read | risky | Appeared and kept growing during the scan. |
| `ServerStorage.BeforeBiomeFollowup` | Folder | 175 | risky | Appeared during the scan (Pine drape colours). |

## ServerStorage: kept (not in the script)

| Path | Class | Desc. | Verdict | Reason |
|---|---|---:|---|---|
| `ServerStorage.RogueliteNPCs` | Folder | 3,832 | keep | Live: RogueliteZombieChase:41, BossService:175, MapBossService:241 clone templates from it. Rojo maps HammerBoss_NPC. |
| `ServerStorage.InactiveAreas` | Folder | 2,140 | keep | Live: ServerRole:30/51 parks map folders here and moves them into Workspace; AdminService:42. Holds FrozenPassArena and VolcanicCraterArena. |
| `ServerStorage.InstallHammerBoss` | ModuleScript | 0 | keep | Dev tool. |
| `ServerStorage.RegularEnemyQA` | ModuleScript | 0 | keep | Dev tool (combat/RegularEnemyQA.luau). |
| `ServerStorage.EggMerchantSetup` | ModuleScript | 0 | keep | Dev tool (lobby/StageEggMerchantSetup.luau). |
| `ServerStorage.ZombieVariantImportTools` | Folder | 2 | keep | Dev tool (2 modules). |
| `ServerStorage.RogueliteTests` | Folder | 9 | keep | Test modules. |
| `ServerStorage.Brushtool2_Plugin_Storage` | Folder | 112 | keep | Plugin storage (Brushtool). Not on your list. |
| `ServerStorage.RBX_ANIMSAVES` | Model | 3 | keep | Animation Editor autosave (its rig is gone). Not on your list. |
| `ServerStorage.RegularEnemyRawImports` | Folder | 2,208 | keep | Current raw import. InstallRegularEnemyTemplates.luau:6, AdoptRegularEnemyImport.luau:13 and SwapImportedEnemyMeshes.luau:26 read it. |
| `ServerStorage.RegularEnemyProjectiles` | Folder | 4 | keep | InstallRegularEnemyTemplates.luau:184 reads it. |
| `ServerStorage.MapBossRawImports` | Folder | 1,272 | keep | InstallMapBossTemplates.luau:8 and DumpBossReceipt.luau:5 read it. |
| `ServerStorage.PetRawImports` | Folder | 118 | keep | InstallPetTemplates.luau:22 reads it. |
| `ServerStorage.GodlyWeaponImport` | Model | 21 | keep | The godly install_call.luau:28 falls back to it. |
| `ServerStorage.GodlyWraithImport` | Model | 5 | keep | blender-godly-wraith/install_call.luau:18 falls back to it. |
| `ServerStorage.BeachCoveKit` | Folder | 26 | keep | BuildBeachCove.server.luau:21 asserts it exists. |
| `ServerStorage.RogueliteGrassKit` | Folder | 26 | keep | blender-grass-kit/studio-asset-manifest.json studioPath. |
| `ServerStorage.GrassPatch_Blender_Library` | Folder | 10 | keep | The current grass meshes; all 10 MeshIds are used by the maps' GroundPatch models. |
| `ServerStorage.RogueliteLobbyKitV9` | Folder | 30 | keep | Current lobby kit; all 30 meshes are in the live lobby. |
| `ServerStorage.LobbyLeaderboardsKitV1` | Model | 6 | keep | Current leaderboard kit. |

## Duplicate names

- **Log_Master.** 3 copies are direct children of Workspace, near the world origin: (162,0,118), (-11.75,0,25.18) and (0.99,0,38). These are the strays. Nine more sit in `Workspace.PineValleyArena`, which MapConfig lists as Pine Valley's folder, so they belong to the map. The rest are in backups and in Brushtool's storage. The strays sit 330–430 studs from the old Pine Valley centre (56,5,450) used by `GroupMapAreas.luau`. That is outside its 250-stud pickup radius, so the 2026-09-28 grouping left them behind. They stayed at the origin when the maps moved to x ≈ ±5000. One carries `_BrushtoolBrushed`, so it was painted with Brushtool. Note that audit L3 says "around the Pine Valley edge"; Pine Valley is now about 5,000 studs away.
- **13_Rock_Cluster.** 1 stray at the origin. Seventeen sit in PineValleyArena and belong to the map.
- **RogueliteWeaponShowcase / RogueliteWeaponShowcase_PlaySize.** Two folders with different names, not two copies. Each holds one empty `DisplayBases` folder and attributes, so neither is strictly empty. Both are stale.
- **BeforeMuzzleFlash_20260922.** Two ServerStorage folders share this name, one empty and one holding 3 scripts. Both are backups. The script tells them apart by descendant count.
- **Workspace.Lighting.** A Folder that shares its name with the Lighting service. The script only counts lookups that go through Workspace, such as `workspace.Lighting` and `workspace:FindFirstChild('Lighting')`. It ignores `game:GetService('Lighting')`.

## Lookup results

### Place scripts

At scan time the place had 944 scripts: 39 in ServerScriptService, 356 in ReplicatedStorage, 19 in StarterPlayer, 530 in ServerStorage and none in Workspace. Their sources were searched for every target name above.

All 15 lines in runtime scripts that touch ServerStorage reach only 4 names: `RogueliteNPCs`, `InactiveAreas`, `AdminSpawn` (a BindableFunction made at runtime) and `RogueliteAllies` (expected by EggChickens:149, missing, already documented in EGG_CHICKEN.md). None of them is a target.

Runtime hits on target names. Every one copes with the object being gone:

| Script:line | Name | Effect |
|---|---|---|
| ServerScriptService.RogueliteZombieChase:165, 375 | Zombie_R15_ProvidedTextures_Studio | Raycast exclude lists use `FindFirstChild`; nil is skipped |
| ServerScriptService.PracticeTarget:3 | Zombie_R15_ProvidedTextures_Studio | Studio only: `WaitForChild(...,10)` returns nil and the script exits |
| ServerScriptService.BossService:38 | ZombieVariantPreviews | Raycast exclude list uses `FindFirstChild`; nil is skipped |
| ServerScriptService.RogueliteCombat:106 (used at 118) | RogueliteWeaponShowcase, _PlaySize | Name list; `FindFirstChild`, missing ones are skipped |
| StarterPlayer.StarterPlayerScripts.CardShowcase:4-5 | RogueliteWeaponShowcase, _PlaySize | `FindFirstChild`; the `18_Deck_of_Cards` it looks for is already gone |

These are the script's `KNOWN_HITS`. Any other runtime hit makes it stop. There were none for Baseplate, Log_Master, 13_Rock_Cluster, LukeSandboxTesting, the Workspace Lighting folder, Lantern_Post_41, or any ServerStorage target. In the kept ServerStorage tools, only EggMerchantSetup:508, 694, 695 and 720 name `EggMerchantBackup`, and only to create it when it is missing.

- **Object references:** no ObjectValue, joint, weld, constraint, PrimaryPart or Adornee outside a target points into one. Nothing in RogueliteNPCs or InactiveAreas points into another ServerStorage item.
- **Tags:** the Workspace targets carry only `_BrushtoolBrushed`, on 1 stray Log_Master. The ServerStorage targets carry only Brushtool and Assistant plugin tags. No runtime script calls `GetTagged` on any of them.

### Repo (roguelite-planning/**/*.luau and *.lua, 530 files including hammer-boss; *.py and *.json for kit names)

| Name | File:line | Kind | Effect |
|---|---|---|---|
| Zombie_R15_ProvidedTextures_Studio | RogueliteZombieChase.server.luau:165, 375 | shipped | nil-safe |
| | combat/PracticeTarget.server.luau:3 | shipped, Studio-only | exits when missing |
| | combat/ArcAttackTests.luau:6 | disposable Play test | needs another dummy |
| | InstallPreferredZombie.luau:3 | one-off tool | asserts it exists |
| | InstallPersistentHead.luau:4 | one-off tool | nil-safe |
| | regular-zombie-matte/ApplyRegularMatte.luau:5 | one-off tool | would error |
| | zombie-stock-r15-preview/supplied-textures/studio-native/* | the tools that built it | n/a |
| | baby-mutant-zombies/studio-backup/Chase.luau:54 | old backup copy | n/a |
| ZombieVariantPreviews | combat/bosses/BossService.luau:38, hammer-boss/BossService.luau:38 | shipped | nil-safe |
| | hammer-boss/test_client_poses.luau:4 | disposable pose test | would error; clone `RogueliteNPCs.HammerBoss_NPC` instead |
| RogueliteWeaponShowcase(_PlaySize) | combat/RogueliteCombat.server.luau:106, combat/CardShowcase.client.luau:4 | shipped | nil-safe |
| | combat/FixLauncherRearBore, FixRocketMuzzle, FixWeaponRendering, InstallCards | one-off tools | `FindFirstChild`, nil-safe |
| | combat/InstallKatana.luau:4, combat/InstallLoadout.luau:5 | one-off tools | already fail today (the folders are empty) |
| | weapon-models/studio-import/* | the tools that built them | n/a |
| Baseplate | lobby/GroupMapAreas.luau:16, 95 | one-time 09-28 migration | line 95 indexes `workspace.Baseplate`, so a re-run would error |
| Log_Master | ApplyPropCollision.luau:66 | name pattern for props inside map folders | not these strays |
| 13_Rock_Cluster | BuildBeachCove.server.luau:42, 167-168; blender-rounded-lightstone-revision/studio-organize-import.luau:14 | kit asset names | not this instance |
| MapGrouping_20260928 | lobby/GroupMapAreas.luau:18 | one-time migration (its UNDO reads the log) | UNDO is moot |
| BeforeKatanaCombat, BeforeLauncherRearBore_20260922, BeforeChainReadability, BeforeStationFix, Weapon_Import_Rigged_Backup, Weapon_Import_ExtraMetadata, Weapon_Material_Correction_Backup, EggMerchantBackup, ZombiePreviousDecalHead, RegularEnemyRawImportsHistory | InstallKatana:25, FixLauncherRearBore:15, ApplyChainReadability:18, FixStations:19, ArrangeShowcase:8/52, ApplyShowcaseCorrections:4, InstallEggMerchant:203, ApplyFullHeadUV:38 / CreateNativeZombie:94, AdoptRegularEnemyImport:27 | the tools that write these backups | each makes its folder when missing |
| Lobby kits, lobby `_ImportedOriginal`s, `_PreV2/_PreV3`, ZombieRawImports, HammerBoss_SourceImport | none (also none in *.py / *.json) | | ZOMBIE_VARIANTS.md:5 notes the zombie raw imports were kept on purpose |
| LukeSandboxTesting, Workspace.Lighting folder, Lantern_Post_41 | none | | FixStations, ApplyPropCollision and InstallChestIsland match `Lantern_Post` names in general |

## Baseplate

- **The part.** `Workspace.Baseplate` is a Part, 2048×16×2048, centred at (0, -8, 0). It is anchored, has 1 Texture, and its top is at y = 0. It covers x and z from -1024 to 1024.
- **What rests on it.** Only the strays being removed (ZombieVariantPreviews, the R15 zombie, 3 Log_Master, 13_Rock_Cluster) and `RogueliteEnvironmentAssets.Evergreen_Master`. That tree is anchored, so it stays put and floats.
- **No map is inside its x/z square.**

  | Area | x | z |
  |---|---|---|
  | Lobby | -1670 to -1110 (86 studs west of its edge) | |
  | Pine | -6500 to -3500 | |
  | Beach | -5704 to -4060 | 3876 to 5234 |
  | Desert | 3850 to 6150 | |
  | Frozen (parked) | | 4150 to 5850 |
  | Volcanic (parked) | 4150 to 5850 | |

  No SpawnLocation is inside it either.
- **Raycasts.** A 289-point grid over it hits only the Baseplate (no terrain), and below it is empty space. Rays down from each spawn land on the same ground with or without the Baseplate:

  | Spawn | Lands on | y |
  |---|---|---:|
  | Lobby | LobbySpawn | 120.2 |
  | Pine | PlayerSpawn | 3 |
  | Beach | OriginalSandFloorCollision | 1 |
  | Desert | SandFoundation | 0 |

  Rays down from the four lobby edges hit nothing either way.
- **Falling.** `Workspace.FallenPartsDestroyHeight` = -500, and removing the Baseplate does not change it. Players who fall off the lobby are teleported back below y = 70 (RogueliteLobbyPreview:320), or die at -500, the same as now. Players who fall off a map die at -500, the same as now. Only something inside the 2048-stud square would now fall to -500 instead of stopping at y = 0, and today that is only the strays being removed.
- **Edge case.** AvatarNormalizer waits up to 30 s for `ServerRole.ready()` before it loads characters. If a match server never applies its map, no SpawnLocation is enabled and characters spawn at the origin. Today they would stand on the Baseplate among the test models; after removal they would fall and die. Both are broken states, so this is no reason to keep the Baseplate.
- **Verdict: safe.** The script checks again at run time. It stops if a SpawnLocation, a map part or an unanchored part rests on or inside the Baseplate, and it lists anchored props that would lose their floor.

## Lantern_Post_41

- **Where it is.** `Workspace.RogueliteLobby.Scenery.Lantern_Post_41` is a MeshPart (1.52×5.83×1.52). It has Anchored = false and CanCollide = true, no joints, welds, constraints or children. It is its own assembly root and the only unanchored assembly in Workspace. It stands on `WalkableCollision.MainFloor21` at y = 120.
- **It has been moved.** It is at (-1458.58, 122.92, -8.09). Its mirror partner Lantern_Post_48 is at (-1340, -13), and the older backup `Lobby_BeforeCohesionV6_20260925_123925` has Lantern_Post_41 anchored at (-1460, 122.92, -13). So it was pushed about 5.1 studs.
- **It lost its lens.** Every other small post (42, 47, 48) has a `WarmLens` with a PointLight 2.04 studs above it in `RogueliteLobby.Accents`. This post's lens, at (-1460, 124.96, -13), was moved into `ServerStorage.BeforeStationFix` by `FixStations.luau` as an "orphan", because no post stood within 3 studs of it. That backup lens has no PointLight.
- **Anchoring stops it falling or being pushed.** It does not make the lantern look right: the post stays 5 studs off its spot and has no lens. `restoreLantern = true` moves it back to (-1460, 122.917, -13) and copies Lantern_Post_42's lens, PointLight included, to 2.04 studs above it. That does not need `BeforeStationFix`, which the default run removes.

## Other notes

- PineValleyArena holds 25 empty `Evergreen_Master` models (0 descendants each), plus 5 other empty models. This cleanup does not touch them.
- The scan made no edits. It did make one read-only `ChangeHistoryService:IsRecordingInProgress()` call, used `loadstring` to compile `CleanupPlace.luau` without calling it, and read the file from the already-running `dev_server.py`.
- Still needs evidence: the script has not been run, not even as a dry run. The first dry run is its first real test against the place.
