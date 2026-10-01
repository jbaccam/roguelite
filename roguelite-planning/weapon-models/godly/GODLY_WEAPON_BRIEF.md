# Godly weapon brief (read this first, every Godly weapon agent)

Shared rules for building one **Godly** weapon in Blender for the roguelite (Roblox). Godly is the
top rarity: these are the best weapons in the game and the chase items. The **Reaper's Scythe**
(`weapon-models/godly/reapers-scythe/`) is done and approved: it's the quality bar and the code you
start from. The Dragon Scale and Phoenix armor sets (`blender-armor-kit/`) show the same craft
level on armor.

## 1. Usage comes first

The owner's usage is limited, and a single asset has burned hours before. Work like a senior artist
on a deadline:

- **Start from the working pipeline.** Copy what you need from
  `weapon-models/godly/reapers-scythe/build_reapers_scythe.py` into your own self-contained
  generator:
  - the scene and lighting;
  - tubes, lathes, beziers and bevel helpers;
  - the painterly bake to one 1024 `BaseColor.png`;
  - glow meshes;
  - export, validation and the catalogue-framed renders;
  - the `Compare_Catalog` and `Sheet` composites.

  Skim it with grep and targeted reads. Never `exec()` or import it.
- **Design before you build:** silhouette, palette, signature motif, and where the glow goes.
- **Shape with cheap flat-colour runs**, then do ONE full bake/export plus at most one fix run.
- **Renders:**
  - `Preview` (catalogue 3/4 framing), `Front`, `Back`, `Side`;
  - one Cycles `Hero` on a dark backdrop;
  - `Compare_Catalog` (your weapon beside Excalibur, Mjolnir and Medusa's Head, same framing);
  - `Sheet`.

  Nothing else.
- Run Blender with `--threads 2` when other weapons are building, `--threads 4` when alone:
  `"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 --python <script>`
- Stay inside your prompt's tool-call budget. If you're running out, ship the best working state
  and list what's left.

## 2. Read first (skim)

- `roguelite-planning/art-references/ART_DIRECTION_USER_2026-09-17.txt`: the art style.
- `roguelite-planning/RARITY_GODLY_ARMOR.md`, section 9: the Godly list, what each one does, and
  the rules.
- `weapon-models/Weapon_Overview.jpg`: the whole current catalogue. You must clearly beat it.
- `weapon-models/assets/32-excalibur/Preview.png`, `31-mjolnir`, `34-medusas-head`: the current top
  tier.
- `weapon-models/godly/reapers-scythe/Sheet.png`, `Preview.png` and `Side.png`: the approved
  Godly look.
- `weapon-models/MODELING_BRIEF.md` and `RIGGING_GUIDE.md`: grip, pivot and scale conventions for
  held weapons.
- `blender-armor-kit/phoenix/previews/hero.png`: how much flash a Godly can carry.

## 3. What the owner wants (his own words and verdicts)

- **"These are going to be the godly weapons, the best weapons in the game, they should look cooler
  than every other weapon in my game ... we should mog them."** The catalogue weapons are clean,
  chunky low-poly with flat colours. Godly keeps that family but is obviously a tier above:
  - a bigger, bolder silhouette;
  - layered materials;
  - sculpted hero details;
  - glow.
- **"Still our cartoonish low poly theme but WAY more detailed."** Never realistic, never noisy
  micro-detail.
- **"Make it more poppy and showy and flashy."** The first Phoenix had too little glow ("tiny
  little flames") and plain white plates ("not much detail to the texture"). Every surface needs:
  - an engraved or raised trim;
  - a motif;
  - an enamel/colour inlay or gems;
  - painterly gradients.

  Glow must read from the game camera, about 18 studs behind and above the player.
- **Chunky, not spindly.** The scythe's first draft read as a thin stick next to the catalogue at
  thumbnail size. Shafts, blades and heads need real mass, and the silhouette must read at
  160 px.
- **Blend everything; bolt nothing on.** Pieces flow into each other through collars, sockets,
  wraps and fillets. No floating parts, no hard seams, no thin sheet fins, no jagged edges. His
  words about a pet: "it's like you're not blending or smoothing anything out at all and just
  throwing pieces together".
- **Symmetry and alignment matter.** The approved scythe's only complaint was "from the side you
  can tell the hood is not straight". Check front, back and side for tilt.
- **What he liked:**
  - On the scythe: the hooded skull with glowing eyes, the bone-spike spine along the blade, the
    rune glyphs on the blade, the gold-banded crimson grip wraps, the hanging chain with a little
    lantern, and the crimson crystal pommel.
  - On Phoenix: the big fire wings, the gold-and-enamel plates and the sun core.
- **Craft:**
  - Multi-segment bevels with weighted normals, so every edge catches a highlight.
  - Baked AO in crevices.
  - Cool shadows and warm highlights.
  - Gold gets brown shading, never flat yellow.
  - 2–4 values per material.
- **Real weapons only.** No novelty objects; the design follows the weapon's name and its section 9
  ability.

## 4. Technical

- **Scale:** final size in studs, held by the 5-stud R15 player (see `MODELING_BRIEF.md` /
  `RIGGING_GUIDE.md` for grip and pivot). Render a `Scale` check beside the 5-stud block figure.
- **Triangles:** up to about 15k per weapon (the scythe is about 17k), every mesh under 20k.
- **Textures:** one 1024 `BaseColor.png` atlas with painterly albedo and baked lighting (AO, bevel
  edge highlight, soft key). Studio uses `MeshPart.TextureID`; SurfaceAppearance renders blank in
  Play.
- **Glow:** separate Neon meshes. If the ability has a signature effect (tidal wave, arrow rain,
  lightning chain, red wisps, disintegrate burst), add a short `vfx_notes` list to
  `studio-install-data.json`: colours, where it spawns, and suggested ParticleEmitter values.
- **Export:**
  - FBX: `axis_forward='-Z'`, `axis_up='Y'`, texture embedded.
  - Also a GLB.
  - Clean slivers and loose vertices.
  - Re-import both and validate, writing `validation.json` the way the scythe does.
- **Install data:** `studio-install-data.json` in the scythe's schema (grip, pivot, parts, glow).

## 5. Your folder and deliverables

Write **only** in `roguelite-planning/weapon-models/godly/<weapon-id>/`:

- `build_<weapon_id>.py`: the self-contained generator.
- `Model.blend`, `Model.fbx`, `Model.glb`, `BaseColor.png`.
- `studio-install-data.json`, `validation.json`.
- The renders listed in section 1.
- `README.md`: short. The design, triangles, and "Blender-verified, Studio untested".

## 6. Don't

- Don't open Roblox Studio or start Play (Play takes over the owner's screen).
- Don't use the Blender MCP tools or the owner's open Blender window.
- Don't commit to git. The lead reviews and commits.
- Don't edit anything outside your folder, including the scythe.

## 7. Report back

Keep it plain and short:
- what you built and why it beats the catalogue;
- triangles;
- the path to `Sheet.png` and `Compare_Catalog.png`;
- anything still imperfect.
