# Armor set brief (read this first, every set agent)

Shared rules for building one armor set in Blender for the roguelite (Roblox). Your own prompt
gives your set's design. Dragon Scale (Legendary) is done: it is the quality bar and the code
you start from.

## 1. Usage comes first (the most important rule)

The owner's usage is limited. Dragon Scale looked great but ran for hours and burned the budget.
Work like a senior artist on a deadline:

- **Don't reinvent the pipeline.** `blender-armor-kit/build_dragon_scale.py` already has the
  full pipeline. Copy these parts into your own self-contained generator, then write only your
  set's piece builders:
  - body proxy loading (`load_obj`, `REST`, `part_pos`, joints);
  - charts and `shell` plates, `rivet`, `horn`, `loft`, `sweep`, `gem`;
  - materials, `finish` and `finish_glow`;
  - the painterly bake (`unwrap`, `bake_all`), export, `clean_mesh` and the install data;
  - the preview scene, `shoot` and `compose`.

  Skim it with grep and targeted reads; don't read all 2,700 lines. Never `exec()` or import
  another kit's file. Your generator must run on its own.
- **Design before you build.** Decide the silhouette, the layers and the palette first.
- **Use cheap checks while shaping.** Use `QUICK=1` runs (flat colours, no bake, seconds) to check
  shapes. Do the **full bake and export once** when the shapes are right, plus **at most one fix
  run**.
- **Bake cheaper than Dragon Scale.** Bake at 1024 directly (no 2048 work size) with 8 samples.
- **Render only these:** `front`, `back`, `side`, `threeq` and `close-helm`, plus one `sheet.png`
  that shows them together. Use Eevee only. Phoenix may add one Cycles `hero`. Don't render pose
  images: run the numeric pose check once (`POSE_IMG=0`) and report its numbers.
- Run Blender with `--threads 2`, because other sets are building at the same time:
  `"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 --python <script>`
- Stay inside the tool-call budget in your prompt. If you're running out, ship the best working
  state and list what's left in your report.

## 2. Read first (skim)

- `roguelite-planning/art-references/ART_DIRECTION_USER_2026-09-17.txt`: the art style.
- `roguelite-planning/RARITY_GODLY_ARMOR.md`, section 10 (the sets) and section 13 (armor rules).
- `blender-armor-kit/README.md`: fit rules, Studio install notes, verification.
- `blender-armor-kit/previews/dragon-scale-sheet.png` and `dragon-scale-beauty-hero.png`: the
  approved quality bar. Match its craft (fit, bevels, painterly bake), not its look.
- `roguelite-planning/weapon-models/Weapon_Overview.jpg`: the game's existing weapon style.

## 3. What the owner wants (his own feedback)

- **Style:** chunky, stylized, cartoon low-poly with painterly textures. Clean faceting, broad
  colour areas, 2–4 values per material.
  - Never realistic.
  - Never noisy micro-detail.
  - Never "Minecraft armor".
- **Not "pajamas."** An early draft was all one colour, made of soft boxes hugging the blocky body
  1:1, with a hood-like helm. He called it "a goofy kid wearing full body pajamas with a hood". So:
  - break the body's box outline with pauldrons, flares, crests and a V-taper;
  - use material contrast: dark against light, metal against cloth or leather;
  - show layers: plates over an undersuit, with gaps showing the darker layer;
  - sculpt the plates with ridges, rolled edges and bevels.
- **Blend add-ons in; never bolt them on.** Fur, cloth, feathers, crests and snouts are thick
  rounded shapes fused into the surface they grow from.
  - No sheet-like fins.
  - No sawtooth or jagged edges.
  - No visible seam where they join.

  A dog model's thin fur shards got "looks like spikes coming off of him" and "a dinosaur's back".
- **Repeated elements go in clean ordered rows** with a consistent flow direction, never random
  crumbs. This covers scales, feathers, lamellar plates and rivets. His words for the first
  Dragon Scale discs: "shitty fish scales".
- **Craft:**
  - Every plate edge gets a bevel: 1 segment on Common, 2 on hero plates for Epic and up.
  - A painted edge highlight on the bevels, and baked AO in every overlap and crevice.
  - A painterly gradient inside each piece.
  - Cool shadows and warm highlights.
  - Gold, bronze and brass get brown shading, never flat yellow.
- **Rarity ladder:**
  - **Common:** simple, clean and sturdy. Not flashy at all.
  - **Rare:** more character, with one accent colour.
  - **Epic:** a strong silhouette and layered detail.
  - **Godly:** spectacular.
- **VFX:** only Phoenix (Godly) has VFX and lighting (particles, lights, Neon glow). Every other
  set: **no Neon glow meshes, no particles, no lights**.

## 4. Fit: the body is fixed

- Every player has the same normalized R15 body (default blocky parts, all scales 1).
- The measured proxy is `blender-armor-kit/r15-proxy/*.obj` (Studio part-local coordinates plus
  `# att` rig attachment lines). Load it the way `build_dragon_scale.py` does.
- The HumanoidRootPart centre is 3 studs above the feet.
- Make one rigid mesh per R15 part a piece covers:
  - **Helmet:** Head.
  - **Chest:** UpperTorso, LowerTorso, Left/RightUpperArm, Left/RightLowerArm.
  - **Legs:** Left/RightUpperLeg, Left/RightLowerLeg.
  - **Boots:** Left/RightFoot, plus an optional cuff on Left/RightLowerLeg.
  - Hands stay bare.
- Follow the clearance and joint rules in README.md ("Fit rules used"):
  - plates 0.028 studs off the body, undersuit 0.012;
  - no thickness beyond the torso side planes;
  - nothing on the inner leg faces;
  - no LowerTorso side plates where the hands swing;
  - the elbow and knee rules;
  - tassets flare 0.07–0.15 studs away from the thighs;
  - pauldrons stay outboard of the arm's inner face.
- **Helmet mode:** set `"helmet"` in the install data to one of:
  - `"open"`: face and hair show (the helmet must leave room for hair);
  - `"hood"`: hides hair and hats, the face shows (an eye slit and similar);
  - `"full"`: hides hair, hats and face.

## 5. Technical

- **Axes:** Studio = (−x, z, y) of Blender. The character faces −y, and its left is +x.
- **Mesh names:** `<Prefix>_<Piece>_<BodyPart>`, for example `Iron_Chest_UpperTorso`. Neon glow
  meshes (Phoenix only) add `_Glow`.
- **Textures:** 1024 atlases (Roblox's cap), with the painted albedo and baked lighting (AO,
  bevel-edge highlight, soft key light) on unique UVs. Studio uses `MeshPart.TextureID`, because
  SurfaceAppearance renders blank in Play.
  - Common: 1–2 atlases.
  - Rare and Epic: 2–4.
  - Godly: up to 5.
- **Triangles:** keep to your prompt's budget. Every single mesh must stay under 20k.
- **Export:**
  - FBX: `axis_forward='-Z'`, `axis_up='Y'`, textures embedded.
  - Also a GLB.
  - Triangulate first, and remove slivers and loose vertices (as `clean_mesh` does).
  - Re-import both and validate. Adapt `validate_exports.py`.
- **Install data:** `studio-install-data.json`, in the same schema as
  `studio-install-data-dragon-scale.json`: `set`, `glow_color_srgb`, and `parts{name:{piece,
  body_part, kind, atlas, offset, size}}`, plus `"helmet"`. Phoenix also adds `"vfx"` (see its
  prompt).

## 6. Your folder and deliverables

Write **only** in `roguelite-planning/blender-armor-kit/<set-id>/`:

- `build_<set-id>.py`: the self-contained generator.
- `<set-id>.blend`.
- `exports/fbx/<set-id>.fbx` and `exports/glb/<set-id>.glb`.
- `textures/<set-id>-*.png`: the 1024 atlases.
- `previews/`: the renders listed in section 1.
- `polygon-report.json`, `studio-install-data.json`, `validate_exports.py` and
  `validation-report.json`.
- `README.md`: short. The design, triangles per piece, and "Blender-verified, Studio untested".

## 7. Don't

- Don't open Roblox Studio.
- Don't use the Blender MCP tools or the user's open Blender window.
- Don't commit to git.
- Don't edit anything outside your folder. That includes `build_dragon_scale.py`, `r15-proxy/`
  and the other sets.

## 8. Report back

Keep it plain and short:
- what you built;
- triangles per piece and in total;
- the path to `previews/sheet.png`;
- the pose-check numbers;
- anything still imperfect.
