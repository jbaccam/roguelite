# Pet brief (read this first, every pet agent)

Shared rules for building one pet in Blender for the roguelite (Roblox). Your own prompt names your
pet. The Golden Retriever (`golden-retriever/`) is done and approved: it is the quality bar and the
code you start from.

## 1. Usage comes first

The owner's usage is limited, and a single asset has burned hours before. Work like a senior artist
on a deadline:

- **Start from the working pipeline.** Copy the parts of
  `blender-pet-kit/golden-retriever/build_golden_retriever.py` you need into your own
  self-contained generator:
  - the fused-surface method (voxel-remesh union → smooth → decimate);
  - the painted-by-position colour;
  - the face painting;
  - the bake, export, install data, preview scene and contact sheet.

  Skim it with grep and targeted reads. Never `exec()` or import it.
- **Design before you build:** silhouette, proportions, palette and the role prop.
- **Shape with `QUICK` flat-colour runs**, then do ONE full bake/export plus at most one fix run.
- **Renders:** `front`, `side`, `threeq`, `back`, `face-closeup`, a `pose-check` and `sheet.png`.
  Use Eevee only. A Legendary pet may add one Cycles `hero`.
- Run Blender with `--threads 2` when other pets are building, `--threads 4` when alone:
  `"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 --python <script>`
- Stay inside your prompt's tool-call budget. If you're running out, ship the best working state
  and list what's left.

## 2. Read first (skim)

- `roguelite-planning/art-references/ART_DIRECTION_USER_2026-09-17.txt`: the art style.
- `roguelite-planning/RARITY_GODLY_ARMOR.md`, section 11: the pets, their rarity and strong suit.
- `blender-pet-kit/golden-retriever/README.md`: the parts, pivots, face method and Studio notes.
- `golden-retriever/previews/golden-retriever-sheet.png` and `side.png`: the approved look.
- `roguelite-planning/weapon-models/Weapon_Overview.jpg`: the game's existing asset style.

## 3. What the owner wants (his feedback on the dog)

- **Style:** stylized, chunky, cartoon low-poly with painterly textures.
  - Chibi proportions: a big round head, big glossy eyes with two catchlights, short chunky limbs.
  - Cute and readable at game distance.
  - Never realistic.
- **Blend everything; bolt nothing on.** This was his biggest complaint. The first dog had thin fur
  shards and a sawtooth tail plate:
  - "looks like spikes coming off of him";
  - "something a dinosaur would have on their back";
  - "its like your not blending or smoothing anything out at all and just throwing pieces together".

  So:
  - Fur, manes, ruffs, cheeks, feathering, fins and crests are ONE surface with the body part they
    grow from. Fuse them with smooth fillets (voxel remesh union), with soft rounded hems or a few
    broad waves.
  - No thin sheets, spikes, sawtooth edges or visible seams.
  - The colour is continuous across every join.
- **Snouts, beaks and muzzles flow out of the head** with a gentle stop. The dog's first muzzle
  was called a "beak / snout" stuck on.
- **Faces:** paint the eyes, brows and mouth lines over shallow relief. Deep modelled eye sockets
  read as sunglasses. Noses and tongues can be modelled.
- **Rarity only means rarer and flashier, never stronger:**
  - **Common:** no glow, just a great model.
  - **Rare:** one small painted accent or charm.
  - **Epic:** a subtle Neon accent (a gem, a marking) plus a trail/sparkle spec.
  - **Legendary:** Neon accents plus a particle spec. The Baby Dragon gets fire breath and embers.
- **Role prop:** each pet carries a small prop that shows its strong suit, like the dog's loot
  satchel and crystal tag. Keep it small and part of the character.

## 4. Technical

- **Units:** 1 Blender unit = 1 stud. Model at final size, standing on z = 0. Aim for about 2–2.6
  studs tall; a player is about 5 studs. Import 1:1.
- **Axes:** Studio = (−x, z, y) of Blender. The pet faces Blender −Y (Studio −Z), and its left is
  Blender +X.
- **Rig:** rigid mesh parts, each with its origin at its joint pivot, rotation 0 and scale 1:
  - body as the root;
  - head;
  - ears, legs, tail, wings and fins as needed;
  - dangling props as their own part.

  Never fuse geometry across parts. Joints must show no gaps when rotated.
- **Budget:**
  - Common and Rare: about 6–10k triangles.
  - Epic: about 8–12k.
  - Legendary: about 10–15k.
  - Every mesh under 20k.
- **Textures:** one 1024 atlas (a Legendary may use 2), with the painted albedo and baked icon
  lighting (AO, soft key light, cool rim). Studio uses `MeshPart.TextureID`; SurfaceAppearance
  renders blank in Play.
- **Glow:** Neon glow parts (Epic and Legendary only) are separate meshes named `_Glow`.
- **Export:**
  - FBX: `axis_forward='-Z'`, `axis_up='Y'`, texture embedded.
  - Also a GLB.
  - Clean slivers and loose vertices.
  - Re-import both and validate (adapt the dog's `validate_exports.py`).
- **Install data:** `studio-install-data.json`, in the dog's schema: the parts, pivots in Studio
  axes, the parent joint, rest rotation and ground point. Epic and Legendary pets add `"vfx"`
  entries: kind, part, position, colour, and suggested ParticleEmitter values.
- **Pose check:** rotate the legs (trot ±28°), the head (tilt and turn), the tail (wag) and any
  wings (flap) through their pivots. Render one small `pose-check.png` to confirm no gaps.

## 5. Your folder and deliverables

Write **only** in `roguelite-planning/blender-pet-kit/<pet-id>/`:

- `build_<pet_id>.py`: the self-contained generator.
- `<pet-id>.blend`.
- `exports/fbx/<pet-id>.fbx` and `exports/glb/<pet-id>.glb`.
- `textures/<pet-id>.png`.
- `previews/`: the renders listed in section 1.
- `polygon-report.json`, `studio-install-data.json`, `validate_exports.py` and
  `validation-report.json`.
- `README.md`: short. The design, parts and pivots table, triangles, and "Blender-verified, Studio
  untested".

## 6. Don't

- Don't open Roblox Studio or start Play (Play takes over the owner's screen).
- Don't use the Blender MCP tools or the user's open Blender window.
- Don't commit to git.
- Don't edit anything outside your folder, including the Golden Retriever.

## 7. Report back

Keep it plain and short:
- what you built;
- triangles per part and in total;
- the path to `previews/sheet.png`;
- the pose-check result;
- anything still imperfect.
