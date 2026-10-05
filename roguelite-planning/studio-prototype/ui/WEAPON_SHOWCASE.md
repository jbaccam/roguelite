# Automated weapon showcase

Updated October 4, 2026 after the compact-menu and missing-effect feedback. The right-panel layout below supersedes the previous full-width bars.

Current menu: a right panel at most 348px wide and 548px tall contains identity, I–IV tiers and persistent ATTACKS / WEAPONS navigation. Attacks holds the base/special/swing choices and playback; Weapons holds a compact paged collection in the same panel. Switching views preserves the current take. Portrait uses a bottom dock. Supporting labels are fixed at 14px, desktop descriptions and playback at 16px, with padded wrapping; compact overflow uses an explicit ellipsis. `open` additionally accepts cosmetic `options.view='weapons'`.

Glock, Draco, Nail Gun and Magic Staff use one target. Rocket flight mounts the production smoke/explosion renderer via an isolated handle/step/destroy adapter. Poison uses production cloud flight and lingering smoke. Base eggs demonstrate one hatch per eight throws, first on throw three; Hatch starts immediately, without changing gameplay probability. Ray Gun uses shared RayImpact radius/effects on bolt arrival; the lethal variant adds disintegration without another blast. The copied island's existing foliage/rocks now frame the open lane, with a lower camera.

Latest verification: **161,610** layout assertions across **1,008** layouts; **1,552** mounted checks; **2,478** text checks across 42 names; all **175** presentations, **14** real-frame effect cases and **18,483** cadence checks passed. UI screenshots were reviewed. Occluded Studio omitted the 3D world, so the new scene composition has functional verification but no visual signoff. [Current report](../combat/BUGFIX_REPORT_2026-10-04.md).

The remaining sections retain implementation context and results from the earlier redesign; current layout and effects are described above.

The Armory and Journal's **WATCH ATTACKS** action opens an automated fullscreen viewer for all 42 weapons, including unowned ones. It cannot equip, unlock or award anything. `WeaponShowcaseScene` clones the actual player's avatar, the actual lobby practice-dummy mesh and the actual lobby **ChestIsland**. Only the local island copy loses its chest/reward stations and small props in the attack lane; the original lobby is untouched. There are no substitute block people, target boards, neon plinth or fabricated fallback island. Missing source assets produce a loading failure message instead of an unrelated scene. See [scene contract](WEAPON_SHOWCASE_SCENE.md).

## Controls and layout

`WeaponShowcaseUI.open(player, weaponId, tier, {variant = optionalVariant, onClose = callback})` opens the viewer; `.close()` closes it. An unavailable/unknown variant falls back to Base without bypassing its tier requirement. Visible controls are **BACK**, four **I–IV** tier segments, **BASE ATTACK**, named specials, an optional **SWING** menu, **REPLAY**, and **LOOP ON/OFF**. A bounded page of three to eight weapon cards sits below the stage. There is no scrolling sidebar or stat table. Armory releases its camera before entry and can return to the selected weapon after close.

The ScreenGui uses `CoreUISafeInsets`, without hiding Roblox CoreGui. Layout reads the live core-safe and full-screen rectangles, accounting for the topbar, cutouts and inset changes. The stage receives the exact uncovered rectangle normalized to the full rendered screen, including its full dimensions for perspective fitting. Actor and weapon bounds determine framing; melee sweep space, the bowling lane and bow height receive additional room. Target arrangements depend on the attack: close targets for melee, a spaced line for bowling, and separated rows for ranged/area effects. Attack descriptions occupy a separate row with 24px side insets, an 8px gap below buttons and 12px bottom clearance. The swing menu clears the entire control panel by 8px.

Escape/controller B and BACK share cleanup. Queue entry, lobby exit and character removal close silently so ready/class selection retains control. The viewer temporarily hides sibling ScreenGuis and disables world station prompts, restoring their previous states when closed. It never relocates the real character.

## Attack presentation

Base attacks use actual weapon templates and neutral-class tier stats, `WeaponMotion`, `ChainWeaponMotion`, `CardPresentation`, swing ribbons, projectile style builders, committed thrown motion and Pandora skulls. Returning throws, yo-yo retraction, ground rolling, pellet/card counts, lightning chains and slows have dedicated recipes. Bowling follows the cloned island's real grass surface with the production mesh radius/pivot correction. Cards restore their face GUIs on every flying copy, including the fourth card reusing a hidden reserve.

Playback keeps the same take alive and attacks continuously at the production cooldown/motion interval. Returning weapons wait for retrieval; Legendary prerequisites retain normal cadence. Vacuum dummies replenish while the channel stays active. Loop OFF finishes the current demonstration and stops initiating attacks; Loop ON resumes without reloading the take. See [continuous cadence and verification](WEAPON_SHOWCASE_CADENCE.md).

Flame, water, vacuum and fire/poison zones call the **production SpecialWeaponVisuals and UtilityVisuals renderers** through isolated preview adapters. The water endpoint uses a local cosmetic contact because dummies are deliberately nonqueryable. Eggs use `ChickenTemplate`, the same articulated fallback used by live EggChickens, with cosmetic hatch/peck motion. Production muzzle flashes use a unique take binding.

Tier IV exposes all seven Legendary moves: flying slash, split rockets, Royal Flush, bowling STRIKE, wrecking-ball shockwave, Excalibur beam and Mjolnir thunder. Prerequisite attacks and charge auras precede the production special renderer. Godly previews include wraiths, trident waves, splitting arrow rain, both daggers' chain, healing wisps and ray disintegration. Preview-local hit targets provide production impact effects; they never query real enemies. The single selected preview bypasses gameplay distance culling, which previously suppressed its charge aura when the fitted camera exceeded 70 studs. Normal combat culling is unchanged. Royal Flush/Strike use the shared capped, distance-aware text policy.

## Isolation and lifetime

One client-local folder at `(2600, 420, -16000)` owns the scene and one replaceable take. The actual avatar retains its inert Humanoid for clothing. Scripts, gameplay attributes/tags, interactions and joints are removed. Roblox can initialize torso collision and regenerated avatar constraints on parenting; a second pass normalizes those states while retaining appearance. Every part is anchored, nontouching and noncolliding. Only the real grass top permits cosmetic ground queries. Dummies have no Humanoid or practice gameplay state.

Each take has at most 40 local movers, seven reusable dummies, one weapon with its authored reserves and bounded production effects. Selection, replay and close cancel owned work and destroy the take. Preview adapters have no gameplay RemoteEvent or permanent render subscription; ordinary mount calls retain their existing combat behavior. The UI releases its camera/input/touch leases and connections on close. Viewer and Journal presentation code never sends inventory, reward, profile or DataStore mutations.

## Verification actually run

The latest scrolling/padding/cadence pass passed **112,402 browser assertions** over **1,008 layouts**, **1,239 mounted lifecycle checks**, **18,483 cadence assertions**, all **175** tier/variant presentations and all **11** frame-driven effect cases. Real Magic Staff playback fired seven times over 8.5 seconds without the old long pause; a five-second vacuum sample had zero channel gaps while targets reset. The current Journal scrolls; the paged Journal below describes the previous visual-review pass. See the [latest integrated report](../combat/BUGFIX_REPORT_2026-10-04.md).

Additional scene and presentation verification from the preceding redesign:

- Scene: **74** detached checks and **1,300** actual-client checks, including original asset preservation, avatar appearance, grounding and physical state across real frames.
- Browser: **88,984** checks covering **882** layouts (42 weapons × 21 viewport/inset combinations); **1,190** mounted lifecycle checks covering seven entries, special/tier fallback, actual safe bounds, HUD/prompt restoration and zero surviving session connections.
- Catalog: **1,142** assertions. All **175** tier/attack presentations passed actual-client timeline, camera projection, isolation, mover-budget and cleanup smoke checks, with at most eight local movers.
- Frame-driven production effects: all **11** representative cases passed—vacuum, water, fire, Royal Flush, Strike, hatchling, arrow rain, twin daggers, wraith, tidal throw and ray burst. These inspect effect creation/active emitters and headline caps while actual render frames run; they are not a GPU benchmark or a claim that every frame was visually reviewed.
- Idle clearance: **997** oriented weapon-part/dummy-bound pairs across 42 weapons × four tiers, with **zero overlaps**. Royal Flush/Strike remained readable and inside their text caps in seven representative desktop/phone camera fits.
- Screenshot review confirmed the real avatar and lobby dummy artwork, cleaned chest-island scenery, clearer browser controls, paged Journal and named item compatibility. Later checks used source/MCP only after the user requested no foreground/mouse control. An occluded Studio window can return blank 3D captures; those captures are not visual evidence.

Temporary `*Tests.luau` fixtures remain source-only and excluded from the overlay. Tests do not award persistent rewards. This is single-client Studio verification, not a four-client network or low-end device performance test. Changes are not published live.
