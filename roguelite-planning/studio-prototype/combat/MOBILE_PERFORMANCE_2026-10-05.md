# Mobile and low-spec presentation pass

Implemented and source-synchronized to Wavebreaker place **107877054949326**. Nine manifest destinations match disk after line-ending normalization. Existing map/assets retained. Studio stopped and device simulator reset to the default viewport. No publishing or production DataStore access.

## Changes

- `ClientQuality`: Auto starts Low on every device (supersedes the original touch/desktop startup policy). After a five-second startup grace, three seconds below 40 FPS reduces one detail level; fifteen seconds above 55 FPS restores one. A deadband and ignored long stalls prevent rapid switching. These are policy thresholds, not measured capacity guarantees.
- Settings: Auto / Low / Full selection, validated by the server and saved through existing profile settings. Invalid strings and numbers are rejected. Auto's effective level is local and never written into a profile.
- Low removes client shadows and authored bloom, sun rays and depth of field. Map atmosphere and color grading remain. Leaving Low restores authored effect states. Balanced and Full retain authored lighting.
- Shared weapon effects: smaller category limits, fewer cloud lobes/debris/particles/ring segments, no Low flash lights, distance checks before allocating decorative effects. The shared effect callback disconnects when empty and reconnects on demand.
- Crystals: same 128-visible-crystal policy, ownership colors and pickup rules. Low disables crystal lights/auras and updates idle motion at 20 Hz; Balanced uses 30 Hz. Magnet pulls and boss burst presentation remain frame-driven. Newly selected crystals receive a pose immediately.
- Weapon rendering caches card parts/SurfaceGuis and reserve membership instead of scanning model descendants/ancestors each frame.
- Settings use a narrow stacked phone layout and scrolling, with a readable scale floor and larger controls. Other windows keep their previous scale policy.
- The combat overlay now includes ClientQuality and the existing MapEnvironment client source so the lighting policy travels with this overlay.

Enemy projectiles, spawn warnings, boss warnings, hit detection, server AI, weapon stats, spawn counts, rewards and collection authority were not reduced or moved to the client. This pass does not complete the planned enemy-record/client-model architecture migration.

## Verification actually performed

- Required `rojo build roguelite-planning/studio-prototype/combat/default.project.json -o build/RogueliteKatanaCombat.rbxlx` passed after final changes.
- All nine runtime destinations parsed during FeatureSync and matched source at final verification. Source backups are in the local dev server's temporary dump directory (`mobile-performance-before-*` and follow-up names).
- `ClientQualityTests` passed 16 checks in Studio Edit: touch startup, grace period, downgrade, gradual recovery, deadband, invalid/long frame samples and profile bounds.
- Actual Studio Client: switched Full and Low in a fixed lobby camera view. Full reported **281 total draw calls / 2,082,501 triangles**; Low **108 / 531,059**. Opaque geometry stayed **75 draws / 529,483 triangles**. Full's shadow pass was 173 draws / 1,551,454 triangles; Low had no shadow pass. These totals include shadows and are a single-view rendering-work comparison, not an FPS or device-capacity benchmark.
- Actual Studio Client effect fixture: 100 clouds, 100 flashes and 100 debris bursts created **1,080 simultaneous BaseParts in Full versus 121 in Low**. Both returned to **zero fixture parts** after 0.5 seconds. Later bursts worked after the idle callback disconnected. Equivalent reproducible fixture is `ClientPerformanceQA.luau` (not shipped).
- Actual Studio Server, in-memory profile: Low, Full and Auto accepted; `invalid` and `99` left the previous valid value unchanged. Cross-server persistence was not exercised.
- Galaxy A06 device simulator (800x360 preset): Settings inspected in landscape (reported viewport 705x338) and portrait (359x718). Initial scaled buttons were 40.7x24.2 pixels; revised quality buttons were **71.1x46.8 pixels** in both orientations. Controls and help were visible with scrolling. Game orientation is `Sensor`; the QA ScreenGui used `DeviceSafeInsets`. The test mounted the production settings factory in a temporary ScreenGui, not the normal menu click path.
- Six Tier IV card weapons were requested through the existing admin remote; console inspection afterward was empty. The subsequent eight-second dummy damage observation was interrupted when Studio returned to Edit (`Target is closed`), so combat hits and six-weapon correctness are **not recorded as passed**.
- One earlier console entry was `SignalBehavior is not a valid member of Workspace`, from `AssistantCommand`, and a later entry was the assistant camera-reset diagnostic. Subsequent inspected output contained no game-script errors.
- Final footer-space and crystal initial-pose/cadence refinements were parsed, built and synchronized, but did not receive another Play pass.

## Remaining acceptance work

No actual phone/low-spec-PC frame-time, thermal, memory-growth, four-player, packet-loss or complete 20-wave run benchmark ran. Device emulation does not simulate slow hardware. No supported enemy-count or 60 FPS claim follows from these results.

Before calling the game fully optimized, measure 25/50/75/100 enemies with six weapons and drops, sustained runs and four real clients. Record median/p95/p99 client frame time, server simulation time, memory after cleanup, network rate and attack-warning visibility on named devices. A sensible initial acceptance target is stable 30 FPS on the chosen low-end phone and 60 FPS on the chosen PC, subject to measurement. Profile CPU-heavy AI and replicated rigs before undertaking the broader enemy architecture migration; do not hide dangerous enemies to meet a rendering budget.


## Vista removal experiment â€” October 5 follow-up

Inspected `Workspace.PineValleyArena.ForestVista`: 304 MeshParts, 304 SurfaceAppearances, nine nested Models; no colliding parts. Bounds are approximately 3000 x 623 x 3000 studs centered at (-5000, 311, 0).

A temporary client-only Low visibility implementation passed actual Full -> Low -> Full restoration (0 -> 304 -> 0 hidden parts), five synthetic late-arrival/removal/cleanup checks, and server verification that all 304 original parts remained visible. It was **reverted**, including its newly created Studio module, after rendering measurements showed a regression.

Actual single-client Studio Play: camera held each render frame at (-5000,145,0), looking toward (-4100,250,0). Both variants used Low lighting/shadows. Two alternating pairs reproduced the same opaque results:

| Vista | Opaque draw calls | Opaque triangles |
| --- | ---: | ---: |
| Visible | 11 | 261,198 |
| Hidden | 106 | 1,089,023 |

An earlier uncontrolled sample was excluded from the conclusion; the repeated samples above used a render-step camera lock and checked its reported position. Other passes varied with ambient animation. The results suggest the vista occludes much more expensive distant scenery. No FPS gain/loss was measured, and this one direction does not establish all-view performance.

Decision: retain the existing vistas in Low. A reduced-detail replacement that preserves useful occlusion, or measured culling of inactive arenas, needs a separate implementation and camera sweep. Simply making these meshes transparent is not an accepted optimization. Original source policy restored and synchronized, required combat overlay rebuilt, Studio stopped. No publication, persistent rewards or production DataStore use.


## Conservative automatic startup follow-up

Auto remains the default for players without an explicit saved override. Every device now begins at Low; input type is no longer used as a hardware-strength estimate. Following five seconds of startup grace, fifteen healthy seconds above 55 FPS earns Balanced, then another fifteen earns Full. Three slow seconds below 40 FPS lowers one level. No startup hardware benchmark or player action is required. This controls Wavebreaker presentation; it does not change Roblox's own graphics slider.

Explicit saved Low/Full choices remain respected. Manual modes no longer accumulate Auto calibration; returning to Auto resets to Low and measures again. The selected mode alone is saved, so an automatically learned Full level does not follow the account to another device.

Verification: required combat overlay build passed; ClientQuality synchronized to Studio with source equality checked by FeatureSync. Updated policy tests passed 19 checks, including conservative startup, upgrade timing, sustained slow-frame downgrades, recovery and invalid/stall samples. Actual fresh single-client Studio Play reported initial Low with no saved override, manual Full, then immediate Low with shadows disabled after selecting Auto. Synthetic frame samples verify timing; a sustained real-device performance trial has not run. Studio stopped after this check; no production DataStores or rewards used.
