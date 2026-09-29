# Roguelite Studio prototype

Updated 2026-09-17. Targets the open `roguelite` place (107877054949326), not Copy The Scene.

## Current behavior

- The health-first UI and Studio-only shop/level-up previews are described in [UI implementation](ui/README.md). Their two source files map to ReplicatedStorage.RogueliteUI and StarterPlayerScripts.RogueliteHUD. XP and gold remain deferred. The art brief and three references are preserved in the master design's confirmed art section.

- The preferred native R15 zombie is the only gameplay enemy template: `ServerStorage.RogueliteNPCs.Zombie_NPC`.
- The old imported Zombie_NPC and Zombie_ImportedSource were removed from Studio.
- `Workspace.Zombie_R15_ProvidedTextures_Studio` remains as one anchored, non-colliding, untagged static display at (70, 5, 410).
- Each Play session spawns five zombies around RogueliteZombieSpawn with ground raycasts. Server-owned chase speed is 13.5 following player feedback that 15.2 felt too fast; player base speed remains 18. Animation cadence follows actual velocity.
- Chase retains nearest living player selection, obstacle pathfinding, and stop behavior. Gentle separation avoids overlapping bodies; zombies do not collide with one another.
- Each client animates the 15 Motor6Ds: forward-reaching arms, alternating running strides, knee bends, and a small torso lean. No uploaded animation is required.
- This remains a movement prototype. Damage, weapons, kills, XP, and persistent rewards are not implemented.

## Source synchronization and reconstruction

The two runtime files exactly mirror ServerScriptService.RogueliteZombieChase and StarterPlayer.StarterPlayerScripts.RogueliteZombieAnimation. Edit those files and sync only those named scripts into the roguelite place. Do not sync the repository's CopyTheScene project into this place.

To reconstruct the character in Edit mode:

1. If missing, run `../zombie-stock-r15-preview/supplied-textures/studio-native/CreateNativeZombie.luau` to create the approved display rig and supplied textures.
2. Run `InstallPreferredZombie.luau` to replace the gameplay template and make the display static.
3. Run `InstallPersistentHead.luau` to replace temporary editable head geometry with persistent asset 78893098815517 and correct its neck attachment orientation. This also disables automatic NPC scaling so Roblox cannot reset the fixed rig at spawn.
4. Install the two runtime scripts at the paths above. Retain the existing map, `Workspace.PineValleyArena.PlayerSpawn` (Beach Cove: `Workspace.BeachCoveExtras.PlayerSpawn`), and RogueliteZombieSpawn marker.

`export_head.py` and `ZombieHead_NativeUV.obj` preserve the unchanged Roblox built-in head geometry with the approved full-head UV projection. The OBJ importer reverses its facing relative to the rig; the install script compensates in both NeckRigAttachment and Neck.C1.

## Verified in Studio

### Shoulder bob follow-up (2026-09-22)

Reviewed consecutive frames from the user's `C:/Users/Jeremiah/Videos/attacks/example swinging.mp4` as a movement reference. The client walk now adds alternating 0.045-stud shoulder lifts, 3.5-degree torso roll, a 0.055-stud twice-per-stride torso bob, and subtle delayed head/elbow motion. The forward-reaching pose is retained. Movement strength follows actual grounded speed and fades when stopped or airborne; spawn phases differ so the group does not step in unison. The combat Rojo project now includes the existing `RogueliteZombieAnimation` LocalScript.

Luau syntax/AST verification and both the combat and root Rojo builds passed. Studio synchronization and visual Play verification are pending: the Studio connector reported no connected instances during this change. Follow-up checks: observe a moving group from front/side at the normal play camera distance, stop the player until enemies settle, and check airborne/death behavior and the console. Multiplayer presentation has not been tested.

Speed-tuning follow-up: lowered zombies from 15.2 to 13.5 (about 11% slower). Fresh Studio Play confirmed all five use 13.5 and chase, the client sees 13.5, player speed remains 18, and arms still reach forward. Returned to Edit mode. The earlier measurements below and validation.json document the original 15.2 test, not this tuned speed.

Final single-client Play test: exactly five live enemies, all using the persistent textured head, with server network ownership and WalkSpeed 15.2. Actual keyboard movement caused every zombie to chase; measured horizontal speeds peaked at 15.20 studs/s. Each left hip alternated through approximately -0.59 to +0.59 radians; hands remained at least 1.76 studs forward of the root. Front-view screenshots confirmed faces point forward after spawn. Static display stayed at (70, 5, 410), all parts anchored, no animation tag. Final runtime console was empty. Returned Studio to Edit mode.

Initial testing exposed non-replicating EditableMesh heads (white cubes), then an importer facing reversal and Humanoid attachment rebuild. Both were fixed before the final test. Raw final measurements are in validation.json.

`rojo build -o build/CopyTheScene.rbxlx` passed as the repository packaging check; that project does not package this separate roguelite Studio place. Multiplayer retargeting, mobile/controller feel, published asset access, prolonged combat/performance tests, and DataStore access have not been tested. This change adds no DataStore use.

## Next milestone

First follow [Enemy simulation and combat architecture](../ENEMY_SIMULATION_ARCHITECTURE.md): migrate the five server-owned chaser rigs to authoritative enemy records with client-only visual rigs, preserving the approved appearance and tuned 13.5 chase speed. Validate simulation, replication, and presentation before making combat depend on them. This migration is planned, not implemented.

Then follow Phase 2 of EXECUTION_PLAN_ASTRA.md: server-owned health/damage, automatic Glock targeting, visible bullets and impact feedback, zombie death, magnetic XP drops, and one temporary level-up choice. Play the complete combat toy for five minutes before expanding enemy counts or content.
