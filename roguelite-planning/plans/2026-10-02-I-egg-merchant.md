# Plan I: the egg merchant (pets hatch from eggs)

Status: built 2026-10-02 overnight from the user's request ("instead of the test dummy … a pedestal
that holds an egg, next to it an NPC you can talk to, the merchant … buy an egg, pan to the large egg
like the chests, crack it open by clicking like the chests, receive a random pet"). Reference:
`art-references/egg-merchant/egg-merchant-concept-v1.png`, minus the egg in his hood and minus the
belt/paw medallion on the big egg.

## Decisions (asked before building)

| Question | Answer |
|---|---|
| Price | **250 emeralds** per egg (between a Silver Chest, 160, and a Gold Chest, 300) |
| Odds | "Generous": Common / Rare / Epic / Legendary **50 / 30 / 15 / 5**. Inside a rarity every pet is equally likely, e.g. each Common is 12.5%, the Baby Dragon (only Legendary) 5%. Pets are tuned so rarer is flashier, not stronger; if one turns out stronger, make it rarer. |
| Amounts | Buy and hatch **×1 / ×3 / ×10**; ×3 and ×10 are one bigger hatch animation, like chests |
| Studio | The user okayed Studio writes and the 3D import for the night; no Play sessions |

The planned Pet Chest is dropped: pets come from the egg only.

## How it plays

1. The egg sits on a wooden nest pedestal where the quest-board island's practice dummy stood; the
   merchant stands beside it (to its right as you come up the path). He looks at you, waves and says
   hi when you walk up, and tosses his little egg now and then.
2. Step on the lime ring in front of him (like every lobby stand: no E prompt). The camera flies to
   the egg, the merchant gestures at it and talks. Left: the egg card with every pet's chance.
   Right: BUY ×n, HATCH ×n and the amount (×1 → ×3 → ×10).
3. HATCH: the camera pushes in. Tap 1 wobbles the egg and a glowing crack appears; tap 2 wobbles
   harder, more cracks, the aura tints toward the best rarity inside; tap 3 the top shell bursts
   off in pieces, light shoots out and the best pet pops out of the egg and hovers there. Cards for
   every pet fly out (NEW!, or the upgrade bar). The merchant cheers for Epic/Legendary.
4. CLAIM puts the egg back together; HATCH AGAIN goes straight into the next one.

## Where things are

| Piece | File |
|---|---|
| Odds, price, amounts | `studio-prototype/combat/EggConfig.luau` (RS.RogueliteCombat.EggConfig, unsandboxed) |
| Buy / hatch (server) | `ProfileService.buyEgg` / `openEgg`, actions `BuyEgg` / `OpenEgg` in RogueliteMeta |
| Egg screen | `studio-prototype/ui/EggScreenUI.luau` (opened as LobbyUI window `Eggs`) |
| Egg stage (camera, cracks, shards, pet pop) | `studio-prototype/ui/EggStage.luau` |
| Merchant NPC (pose, look, wave, bubble) | `studio-prototype/ui/EggMerchant.luau` |
| Walk-up ring | `StationApproach` stand `Eggs` (Workspace.RogueliteLobby.Stations.Eggs) |
| Models | `blender-egg-merchant-kit/` (egg + nest pedestal, merchant) |
| Studio install | `studio-prototype/lobby/InstallEggMerchant.luau` (after one 3D Import of `exports/fbx/egg-merchant-studio.fbx`) |
| Script sync | `studio-prototype/lobby/SyncEggMerchant.luau` + `egg_merchant_hunks.py` (anchored inserts into shared scripts) |
| Tests | `studio-prototype/combat/EggTests.luau` (odds, rolls, amounts, buy/hatch/rejections against the real ProfileService) |

The practice dummy that stood there is in `ServerStorage.EggMerchantBackup` (drag it back to
`Workspace.RogueliteLobby.Scenery` to restore it).

## Studio status (2026-10-02, about 1 AM)

- **In Studio:** all scripts (synced, compile-checked), the egg texture, merchant texture and egg
  icon uploads, and `ServerStorage.EggMerchantSetup` (the installer with its data baked in).
- **Not in Studio yet: the models.** The 3D Import needs one click in Studio's Import Preview, and
  the PC's display was off overnight, so that window couldn't be seen or clicked reliably. The dummy
  is still standing; nothing on the island changed.
- **To finish (one click):** Studio > Import (Ctrl+M) >
  `roguelite-planning\blender-egg-merchant-kit\exports\fbx\egg-merchant-studio.fbx` > Import
  (default settings). A watcher in the Studio MCP plugin installs it on its own as soon as the
  import lands. If Studio was restarted in between, run in the command bar:
  `require(game.ServerStorage.EggMerchantSetup)()`

## Verified / not verified

- **EggTests in Studio Edit** (200,073 checks): odds sum to 100, Baby Dragon 5%, 200k rolls within
  0.5 points of the odds, bad amounts rejected, not-enough-emeralds and region-restricted buys
  rejected with nothing spent, hatching more than owned hatches what you own, results rarest
  first, copies land in the profile.
- **Installer** on stand-in parts laid out like an import (100x, turned -90 degrees): every part
  found, scale and turn recovered with zero fit error, egg on the ground at the dummy's spot facing
  the path, merchant beside it, joints and attributes set, walk-up stand created.
- **Egg stage in Edit:** tap 1 lights crack 1 only, tap 2 adds crack 2, the burst throws and fades
  the five shards, hides the cracks, lights the inside, and the pet pops out at 1.55x on the break
  line; Settle puts every shard back exactly.
- **Merchant poses in Edit:** idle, present, wave, cheer and nod all run; reset returns every part
  to the installed pose.
- **Blender:** both kits re-import clean from FBX and GLB (names, counts, UVs, transforms); renders in
  `blender-egg-merchant-kit/previews/`.
- **Not verified:** anything in Play (no Play session was started; the user play-tests), the real
  meshes in Studio (not imported yet), camera framing of the egg screen, and how the baked colours
  look under Studio's lighting.
