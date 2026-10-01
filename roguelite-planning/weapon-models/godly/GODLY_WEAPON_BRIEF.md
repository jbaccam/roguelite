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

## 8. Round 2 verdicts (2026-09-30): go all out

The owner rejected the first passes of the Shadow Daggers, Trident and Storm Bow.

**His words:**
- On the daggers: "flat and greyish", "doesn't radiate enough aura", "modeling is subpar", "too much flower vibe".
- On the trident: "doesn't look sharp enough and the edges are too smooth".
- On the bow: it "looks like shit".
- On the brief overall: "go all out ... use ALL your tools ... nice curves, good intricacy and detail".

"Clearly beats the catalogue" is no longer the bar. **The bar is the Reaper's Scythe and the owner's reference images.** That overrides section 1's "one bake plus one fix run":
- Budget is about 150 tool calls.
- Up to 3 full bake/render iterations.
- Close-up crops for your own review are allowed (keep them in a `wip/` subfolder or delete them; ship only the section 1 set).

**What makes the scythe work, and what every Godly needs:**
- **Sharp.** Needle points, hooked barbs, spikes and serrations. Every blade or tine tapers to a real point. Edges are crisp: use bevels of 1–2 small segments on hard edges, not big round fillets. Soft blobby edges read as a toy.
- **A focal "character" piece.** On the scythe it's the hooded skull with glowing eyes. Give each weapon one sculpted focal piece: a face, a skull, a beast head, a crystal in claws, or a dial.
- **Contrast.** Rich, saturated darks (near-black with a colour cast, deep navy, deep crimson) against hot glow. Never flat mid-grey, never pastel.
- **Aura.** Add a compositor Glare (Fog Glow/Bloom) pass to every render, because Roblox Neon blooms in game. Glow sits in long lines (edges, veins, fullers, strings), not only in dots.
- **Real modelling, not primitive kits.**
  - Author blade, tine and limb silhouettes as 2D profile polygons. Extrude or solidify them with a ridge so they are diamond or lens-shaped in section, then bevel.
  - Taper everything.
  - Let curves flow: shafts swell into collars, plates overlap like scales or armour.
  - Use bmesh, curves, boolean cut-ins, shrinkwrapped inlays and weighted normals.
- **Texture.** Painterly gradients per part: dark at the base and lighter toward the edges. Add cavity darkening, an edge highlight on every bevel and AO in every crevice. Give each material 2–4 values with hue shifts (cool shadows, warm lights). No uniform fills.
- **Self-review honestly.** Render your Preview beside the scythe's `Preview.png` and beside the reference images. Ask whether a kid would call it "sick" and whether it looks as sharp and as finished as the scythe. If not, iterate.

**Reference images, where the owner supplied them, live in `<weapon>/reference/`.** Match their silhouette language, translated into our chunky stylised low-poly style. Don't copy logos or text, and don't make a 1:1 replica of another game's model.
