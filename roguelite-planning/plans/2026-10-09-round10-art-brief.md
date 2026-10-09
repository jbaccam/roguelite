# Round 10 art brief (binding for every Blender agent)

October 9, 2026. Read this whole file before opening Blender. It turns the user's past feedback into hard rules so the first build lands. Gameplay contract: [Round 10 master spec](../ROUND_10_MASTER_SPEC.md). Reference sheets: `art-references/round-10-modeling-pack-2026-10-09/` (01–10 PNGs + `MODELING-GUIDE-AND-PROMPTS.txt`). Art direction: `art-references/ART_DIRECTION_USER_2026-09-17.txt` (read it).

## 1. Style (the user rejects anything else)

- Stylized low-poly painterly, Roblox-friendly: chunky readable silhouettes, soft bevels (never razor 90° edges), visible but gentle faceting, matte surfaces. Never realistic, never smooth Pixar, never flat-shaded toy plastic, never voxel.
- Textures do the richness, geometry does the shape. Broad painterly patches, 2–4 value ranges per material, subtle grunge, occasional highlights. No photo textures, micro-scratches, high-frequency noise, photoreal cracks or heavy PBR. Bake procedural looks into a base-color atlas (one 1024² atlas per character is the default; 2048² only if the character really needs it; props share one atlas per kit).
- Colour: the game runs bright and saturated (Studio ColorCorrection +0.3 saturation, bright sky). Blender renders look dull next to it, so keep hues clean and saturated, don't muddy them. Match the reference sheet palette (bloater mustard-yellow with brown rags; DJ crab coral-red shell, cream belly, charcoal gear with teal trims and tan straps; Warden sand bandages, terracotta-ochre stone mask/fists, teal sash; alpha russet-maroon fur, charcoal mane, cream chest/tail tip, charcoal shorts, brown belt, amber eyes; sandstone coffins beige with terracotta mottling; vent charcoal-plum basalt with orange lava cracks).
- Shapes are designed, not blobs: clear masses, planes and silhouette breaks. Add-ons (cheeks, mane, fists, straps, pustules) are FUSED into the base surface with smooth fillets (voxel-remesh union → smooth → decimate, or modelled continuous), with colour continuous across the join. No visible sheet edges, sawtooth hems, floating cards or gaps between parts that should touch.
- Fur = soft broad clumps, not thin sharp shards (those read as blades/scales); clumps dense on limbs read as rocks, so keep limb fur as gentle layered locks; tufts mainly at silhouette breaks (shoulders, elbows, cheeks, tail).
- Hands are complete: palm, fingers or a solid mitten with a tucked thumb; claws attached; wrists taper into hands (no swallowed hands, no paper-thin fingers, no stacked finger slabs).
- Triangle budget: under 20k triangles per exported mesh object (Roblox limit). Targets: bloater 4–8k total, DJ crab 8–14k, Warden 8–14k, alpha 12–20k, coffin body+lid ≤ 3k, broken kit ≤ 3k, vent ≤ 2k, each debris fragment 30–150.

## 2. Animation quality (the user's hard rules)

"No breaking bones, no ligaments twisting or joints going the wrong way."

- Knees bend forward only, elbows bend backward only, fingers/claws curl the natural way. Write a check: for every frame of every clip, compute each hinge joint's bend angle about its hinge axis and assert it stays inside a natural range (knee/elbow 0°–150°, never negative/hyper-extended past −5°). Log the min/max per joint.
- No candy-wrapper twist: limit forearm/shin twist relative to rest to ±70°; distribute twist; no bone may rotate more than 45° between consecutive 24 fps frames (except an intentional snap, which you must name). Log the worst case.
- Skinned meshes: smooth weight blends at shoulders, elbows, hips, knees, neck; verify no collapsed armpits/pinched knees at extreme frames by measuring mesh volume or cross-section at those joints vs rest (≥ 85% retained). Rigid parts (stone fists, stone mask, speakers, headphones, crab shell plates) weight to ONE bone at 1.0.
- No limb passes through the body or ground in any frame: sample every frame and check that hands/claws/fists don't penetrate the torso mesh, and nothing goes below the ground plane by more than 0.05 (Death included).
- Feet/leg tips planted while in contact: drift ≤ 0.05 units in planted phases (log it). Record `strideLength` and `nominalSpeed` for locomotion loops.
- Loops close exactly (last frame = first frame). Every non-loop attack starts and ends on the Idle start pose.
- Attacks: anticipation (readable windup), acceleration, decisive contact/release, follow-through, recovery; hips/chest/footwork drive the strike, not a waving forearm. Heavy strikes: windup high, big shoulder-driven arc, arm nearly straight (≥ 95% reach) at impact, wrist locked in line with the forearm, elbow pole back/down never sideways, torso and knees commit, speed peaks at contact.
- Author at 24 fps. Clip names exact (below).

## 3. Studio import rules (things that broke earlier imports)

- Apply object transforms before binding. Export copy only; never apply transforms blindly to an already-bound approved rig.
- No mesh object may share a name with any bone (Roblox merges them). Name meshes `<AssetName>_<Section>` (e.g. `DJCrab_Shell`), bones plain (`Body`, `LeftClaw`...).
- Deform bones only in the export, a zero-influence `Root` bone at the origin, no leaf bones, ≤ 4 influences per vertex, normalized weights, no unweighted vertices.
- FBX: `axis_forward='-Z', axis_up='Y', add_leaf_bones=False, use_armature_deform_only=True, bake_anim=False` for the rest file, `path_mode='COPY', embed_textures=True`, and also copy textures next to the FBX. The character faces −Y in Blender, +Z up, its left at −X... check an existing sibling package and match it exactly.
- Glow sections (eyes, lava, speaker LEDs, cracks) are separate mesh objects so Studio can set them Neon.
- Re-import every export into a fresh Blender file and verify mesh counts, bones, weights, UVs, textures and clip motion (see `king-crab-boss/validate_exports.py` and `mob-production/reference-rebuilds/verify_exports.py`).

## 4. Process and limits (usage is limited)

- One focused build pass, then at most ONE fix pass after your own review. No open-ended self-iteration, no big render sets.
- Renders (Blender 5.2 background, EEVEE or Workbench, ≤ 1024 px): `Front.png`, `Back.png`, `Side.png`, `ThreeQuarter.png`, `Hero.png`, plus `previews/GameClips.png` (4–6 frames per clip) and one `previews/Attack_<Clip>.png` strip per attack (windup, impact, recovery, front and side). Never present the AI concept sheet as a render.
- Run Blender only as a separate background process: `& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' -b --threads 4 --python-exit-code 1 --python <script> -- <args>` (or the Blender MCP `execute_blender_code_for_cli`). Never touch the user's open Blender document.
- Write a self-contained generator in your own folder (`build_*.py`), no `exec()` of sibling scripts' source. You may `import` shared helpers by path read-only (e.g. `mob-production/reference-rebuilds/meshlib.py`) or copy what you need.
- Do not edit other assets' folders or any shared pipeline script in a way that changes existing outputs. Do not open or write to Roblox Studio. No Studio Play sessions. Do not `git add` or commit anything (the lead commits).
- Folder shape (match siblings): generator script(s), `<Asset>.blend` source, `exports/` (game package), `textures/`, `previews/`, `validation-report.json` + validator script, `README.md` with provenance (SHA256 of the reference sheet used), triangle counts and an honest "Blender-verified, Studio untested" status.
- Final message to the lead: paths, triangle counts per mesh, bone list, clips with durations and impact/key times, all check results (worst numbers), and known issues. Keep it under 600 words.

## 5. Shared dimensions (authoring units = studs at template scale 1)

- Player avatar ≈ 5.3 tall. Regular zombie ≈ 5.3. Existing regular crab, mummy, werewolf sources: measure them in `mob-production/combat-ready/<id>/Model.blend` for comparison renders.
- Bloater: ≈ 6.0 tall, belly ≈ 4.6 wide.
- DJ crab: shell ≈ 1.5× the regular crab's shell width; total footprint radius ≈ 4.5; speakers top ≈ 4.2 high.
- Tomb Warden: ≈ 8.6 tall standing, fists ≈ 1.6 across each.
- Alpha werewolf: ≈ 1.3× the werewolf source height.
- Sarcophagus (stands UPRIGHT, open face toward −Y): outer ≈ 10.4 tall, 7.4 wide at the shoulders tapering to ≈ 5.4 at the foot, 5.2 deep; walls ≈ 0.55–0.7 thick; cavity ≥ 9.4 tall × 6.2 wide × 4.2 deep. The Warden's Emerge start pose (arms crossed on chest, mummy pose) must fit inside that cavity box with its root at the coffin's floor centre.
- Volcanic vent: ≈ 9 across, ≤ 1.8 tall (a low ring, never a wall), opening ≈ 3.5 across.
- Debris fragments: 0.15–0.5 across.
