# Pets (gameplay, step 6)

Design: `roguelite-planning/RARITY_GODLY_ARMOR.md` sections 11 and 13. One pet slot. Copies level a
pet from Tier I to IV, like weapons. Rarity only means rarer and flashier, never stronger: every
pet's Tier I is tuned to about the same power. Pets follow you everywhere (lobby, shop, combat);
their abilities run only in combat.

**Status: Studio-untested.** The code is written and packages (`rojo build`), but nothing here has
run in Studio yet.

## Numbers (first pass; all in `PetConfig.luau`, the `PETS` table)

Tier values are I / II / III / IV. Damage is `(base + perWave × (wave − 1)) × tierMult`, with
tierMult 1 / 1.15 / 1.3 / 1.5. Example: the Fox at wave 3, Tier II does (10 + 2.5 × 2) × 1.15 = 17.25,
times your Damage stat.

| Pet | Rarity | What it does |
|---|---|---|
| Golden Retriever | Common | Every 3 / 2.6 / 2.2 / 1.8 s fetches the nearest crystal you may collect, up to 45 studs from you |
| Bunny | Common | Every 10 s a carrot heals the most hurt run player within 40 studs (you included) for 12 / 14 / 16 / 18 HP, times their Recovery. Skips when nobody is hurt |
| Frog | Common | Every 6 s slams the densest group within 20 studs: radius 8 / 9 / 10 / 11, knockback 35 (bosses ×0.25), damage 6 + 1.5 per wave |
| Penguin | Common | Every 7 s slides 16 studs at the nearest enemy; enemies within 3 studs of the line are slowed 30 / 34 / 38 / 42% for 2.5 s and take 3 + wave |
| Fox | Rare | Every 3 s pounces on the nearest enemy within 22 studs: 10 + 2.5 per wave, times your Damage stat |
| Bee | Rare | +8 / 10 / 12 / 15% PoisonChance. Every 4 s stings the nearest enemy within 18 studs: one poison stack |
| Turtle | Rare | Every 15 / 13.5 / 12 / 10.5 s gives a shell (blocks one hit, lasts 15 s) to the most hurt run player within 40 studs, preferring players without one |
| Monkey | Rare | +6 / 7 / 8 / 10% AttackSpeed |
| Lucky Cat | Epic | +8 / 10 / 12 / 15 Luck |
| Owl | Epic | Every 4 s marks the toughest enemy within 50 studs (bosses first, then most max health) for 5 s: your hits on it do +20 / 23 / 26 / 30% |
| Cheetah Cub | Epic | +1.5 / 2 / 2.5 / 3 MoveSpeed. After you take damage: +6 MoveSpeed for 2 s (6 s cooldown) |
| Baby Dragon | Legendary | +5 / 6 / 7 / 8% BurnChance. Every 5 s flies at the nearest enemy within 14 studs and breathes an 8-stud, 25° cone: burn + (4 + wave) damage |

Upgrade copies and emeralds use the weapon tables in `ChestConfig` by the pet's rarity. Pets are
never in weapon or armor chests. **The Pet Chest itself is not built yet**: Studio profiles get all
12 pets at Tier I (`PetConfig.StudioGrant`); live profiles have no way to get a pet yet.

## Files

| Repo file | Studio | Sandboxed |
|---|---|---|
| `combat/PetConfig.luau` (new) | `RS.RogueliteCombat.PetConfig` (ModuleScript) | **Yes**, caps from CharacterStats |
| `combat/PetRigs.luau` (other agent; pure data) | `RS.RogueliteCombat.PetRigs` (ModuleScript) | Yes (works either way) |
| `combat/PetService.server.luau` (new) | `SSS.PetService` (Script) | **Yes**, caps from `SSS.RogueliteCombat` |
| `combat/PetVisuals.client.luau` (new) | `SPS.PetVisuals` (LocalScript) | No |
| `combat/PetConfigTests.luau` (new) | `ServerStorage.RogueliteTests.PetConfigTests` | No |
| `combat/SyncPetRuntime.luau` (new) | paste into execute_luau (Edit) | - |
| (created at runtime) | `RS.RogueliteCombat.PetFX` (RemoteEvent) | **Yes**, Basic + RemoteEvent |
| `combat/ProfileService.luau` | `pets`, `pet`, `ProfilePets` / `ProfilePet`, Studio grant, `equipPet`, pets in `addCopies` / `upgrade` | No |
| `combat/ChestConfig.luau` | pet rarities in `RarityOf`, `isPet`; never in `Pool` | No |
| `combat/RogueliteMeta.server.luau` | `ProfileAction('EquipPet', id or nil)` | No |
| `combat/CharacterService.luau` | pet stat source in `refresh`, `petTemp`, pet shell (checked before FirstHitBlock), `onDamaged`, `onPetShieldPop` | Yes (existing) |
| `combat/CombatEffectsService.luau` | `E.status` export, Owl mark multiplier in `E.hit` | Yes (existing) |
| `combat/ShardDropService.luau` | `D.fetch` (no radius / line of sight; same owner, phase and rest rules) | Yes (existing) |
| `ui/ArmoryUI.luau`, `ui/LobbyUI.luau` | Pets tab, pet slot, pet detail; `L.profile` parses pets | No |

Sandboxing rule: a sandboxed script can only require sandboxed modules, so all pet data that
CharacterService or PetService reads lives in the sandboxed `PetConfig`. Nothing here waits on
`RogueliteRunState` at load (it is looked up with `FindFirstChild`).

How it fits: ProfileService publishes `ProfilePet` / `ProfilePets`. CharacterService adds the pet's
flat stat. PetService keeps `workspace.RoguelitePets.<UserId>` (attributes `PetId`, `Tier`,
`OwnerUserId`), runs the abilities on Heartbeat with server cooldowns, and fires
`PetFX(ownerUserId, kind, data)` to all clients. Kinds: Fetch, Carrot, Slam, Slide, Pounce, Sting,
Shield, ShieldPop, Mark, Burst, Breath. PetVisuals draws a CFrame-driven follower per folder from
`RS.PetModels.<Id>` + `PetRigs`, and the effects.

Server checks: abilities only in the Combat phase with `ZombiesEnabled`, only for players in the
run (ShopService) who are alive, not downed and not in the lobby preview; never practice dummies;
cooldowns on the server; `EquipPet` is type-checked and ownership-checked.

## How to test in Studio

1. Sync: serve `roguelite-planning/` on 8765 (and HEAD copies on 8791 for the shared-file check),
   paste `combat/SyncPetRuntime.luau` into execute_luau in Edit. Read its WARNING block and diff the
   shared files it pushed. It also runs `PetConfigTests` (expect `PASS`).
2. Confirm `RS.PetModels` has all 12 models (the sync prints the count).
3. Play (ask first; the user play-tests). Armory → Pets: 12 cards, all owned at Tier I in Studio.
   EQUIP a pet: toast, sound, tick on the card, the slot shows it, and the pet follows you in the
   lobby. UNEQUIP removes it.
4. Stats: equip Monkey / Lucky Cat / Bee / Cheetah Cub / Baby Dragon and check the stat panel.
5. Start a run and check each pet's ability and effect, e.g.: Fox damage numbers every 3 s; Frog
   knockback ring; Penguin slow (enemy `StatusSlowStrength`); Bee poison (`PoisonUntil`); Owl reticle
   and `PetMark_<UserId>` on the target; Turtle shell bubble that pops on the next hit; Cheetah burst
   after a hit (WalkSpeed +6 for 2 s); Golden Retriever crystals flying in from far away; Bunny heal
   when hurt; Baby Dragon fire cone with burns.
6. Practice dummies and the lobby: no ability ever fires there.

**Needs real clients (not testable alone in Studio):** Bunny and Turtle helping another player,
two players' pets and effects at once, and a pet on a separate match server. Never claim these
passed without evidence.

## Unfinished

- The Pet Chest (price, odds, chest screen) is a separate task.
- PetVisuals picks a dash per ability with the pet's one `action` clip; named clips like `glide`
  and `head_turn` are not used yet.
