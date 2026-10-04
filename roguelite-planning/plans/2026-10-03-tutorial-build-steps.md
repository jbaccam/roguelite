# Tutorial build steps

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved first-join tutorial ([spec](2026-10-03-tutorial-design.md)): a 3-wave Pine Valley run with the Egg Merchant guide and the gliding arrow, the boss super-jump intro, crystals that fly in, a one-time reward, and the guided lobby steps (chests → Armory upgrade and equip → Starter Pack offer → Play).

**Architecture:**
- **One pure data module, `TutorialConfig`.** It holds every tutorial number and line, and is shared by the server and the client. Tests load it with `loadstring` in Studio Edit.
- **The tutorial is a mode on the real run.** `TutorialDirector` (a server Script) switches it on with the combat attribute `TutorialRun`. It then fills `ShopService.tutorial` (plain data) and sets a few attributes:
  - `HammerBossWave`, `TutorialBossHealth`, `WaveNoRespawn`;
  - `ShardDropService.killValue`.
  
  Shared scripts read these through small, guarded hunks, so a normal run never sees them.
- **Two changes affect every run:** wave-end crystals fly in (`ShardDropService.sweep`; tutorial only since db71be9, 2026-10-03, so other runs fill the crystal bag), and boss crystals fly to the run's players, split round-robin. The boss super-jump intro is also used by every wave boss (`BossService` attributes, `BossIntro.client`).
- **The client guide (`TutorialGuide.client` + `TutorialGuideUI`)** reads only replicated state: the run state, the player's attributes and the open screens. It points at named GUI objects.
  - Lobby progress is saved on the server (`ProfileService.tutorial.step`) and moves forward only (`ProfileAction 'TutorialStep'`).
- **Shared scripts change only through anchored hunks** (`combat/tutorial_hunks.py`, `tools/hunks.py`). They are committed from a private index, as HEAD + our hunks, because other sessions edit the same files.

**Tech stack:**
- Roblox Luau, checked in Studio **Edit** through `execute_luau` (read-only).
- Python 3 for the tools and the arrow PNG; Blender 5.2 for the portrait.

**Ground rules (memory):**
- No Play sessions, and the user does the play-testing.
- No Studio writes or uploads until the user says so (Task 10).
- Stage only our own files, and push with `git push origin main`.
- Paths are relative to `roguelite-planning/studio-prototype/` unless noted.

**Studio note:** in Studio, profiles live in memory and the tutorial would start on every Play. It only runs when **`Workspace.StudioTutorial = true`**. Without it every Studio profile counts as having done the tutorial, so the user's normal play-testing doesn't change.

---

## File map

| File | Responsibility | Change |
|---|---|---|
| `combat/TutorialConfig.luau` | Waves, economy, boss HP, reward, seeded chest, steps, guide lines, asset ids | create |
| `combat/TutorialTests.luau` | Pure checks: shards and levels at each shop, the crystal split, steps | create |
| `combat/TutorialDirector.server.luau` | Lobby → tutorial match routing; switches the run mode on/off; wave ends on all-dead; Studio Combined start | create |
| `ui/TutorialGuideUI.luau` | Egg Merchant text box (portrait, typewriter text, optional button), gliding arrow, VICTORY banner | create |
| `ui/TutorialGuide.client.luau` | The step machine for the run part and the lobby part; reports lobby steps | create |
| `combat/BossIntro.client.luau` | Boss super-jump: shadow, fall, shockwave ring, camera orbit, name card | create |
| `ui/assets/tutorial/make_arrow.py` → `arrow.png` | The white outlined guide arrow | create |
| `../blender-egg-merchant-kit/render_portrait.py` → `previews/merchant-portrait.png` | Transparent bust portrait for the text box | create |
| `../previews/tutorial-guide/guide.html` | HTML mockup of the text box and the gliding arrow (dev server) | create |
| `combat/tutorial_hunks.py` | All anchored edits below + the Studio sync manifest | create |
| Shared (hunks) | ShopService, ShardDropService, EconomyConfig, CharacterService, CombatEffectsService, `combat/bosses/BossService`, `RogueliteZombieChase.server`, ProfileService, RogueliteMeta, `lobby/MatchService`, `ui/LobbyUI`, `ui/RunResultsUI` | modify |
| Docs | the spec (status, Starter Pack correction), `LOBBY_AND_FIRST_RUN.md`, `ui/README.md` | modify |

The Rojo project maps `BossService` to `hammer-boss/`, but `combat/bosses/BossService.luau` is the newer copy (it has the plan L pause and P12 edits). Edit that copy. The sync checks Studio's actual Source before writing.

## Running Luau checks

Start the dev server once, in the background: `python tools/dev_server.py 8934`. Then in Studio Edit:

```lua
local HS=game:GetService('HttpService')
local base='http://127.0.0.1:8934/studio-prototype/'
local function load(p) local src=HS:GetAsync(base..p..'?t='..os.clock(),true):gsub('\r\n','\n');local fn,err=loadstring(src,'='..p);assert(fn,err);return fn() end
local ok,r=pcall(load('combat/TutorialTests.luau'),load('combat/TutorialConfig.luau'),load('combat/EconomyConfig.luau'),load('combat/RunXP.luau'))
return ok and ('PASS '..r..' checks') or ('FAIL '..tostring(r))
```

The compile check is the plan K snippet, run over every touched file.

---

### Task 1: TutorialConfig + tests

- [ ] **Write `combat/TutorialConfig.luau`:**
  - Map `PineValley`, class `Brawler`, weapon `'01'`.
  - `START_SHARDS=0`, `CRYSTAL_VALUE=5`, `BOSS_WAVE=3`, `BOSS_HP=650`, `VICTORY_DELAY=4`, `MAX_WAVE_SECONDS=90`.
  - `Waves`: 1 = 6 `regular-zombie`; 2 = 15 with the map's own mix; 3 = 4 `regular-zombie` + the boss.
  - `Offers`: `[2][1]='weapon_00_1'`, the Glock Tier I in the shop after wave 1.
  - `Reward = {chests={Silver=3}, emeralds=100}`.
  - `SeedChest='Silver'`, `SeedCopies={['01']=2,['Iron.Helmet']=1}`, `SeedArmor='Iron.Helmet'`.
  - `Steps={'Run','Chests','Armory','Equip','Offer','Play','Done'}`, with `canStep(from,to)` (forward only, lobby steps only).
  - `Lines`: every guide line by id.
  - `Asset`: portrait and arrow ids (filled in at Task 10).
  - `shop(E,XP,glockPrice,itemPrice)`: the economy walk (crystals → shards/XP at each shop) used by the tests and the docs.
- [ ] **Write `combat/TutorialTests.luau`** (`return function(T,E,XP)`):
  - Shop 1 has ≥ the Glock price and the player is level 2 with 1 card.
  - Shop 2 has ~95 shards at level 4, with 2 cards.
  - `E.shareIndex` gives 17/17/16 for 50 crystals across 3 players, and 50 for 1 player.
  - Steps only move forward and never back to `Run`.
  - The seed ids are what the chest code expects.
- [ ] **EconomyConfig hunk:** `E.shareIndex(n,count)`, i.e. which of `count` players gets the nth crystal of a shared drop.
- [ ] Run the tests (expect PASS) → commit.

### Task 2: Crystals fly in (every run)

ShardDropService hunks:
- `D.killValue` overrides `E.KILL_SHARDS`, and the designer bonus is kept on top.
- Boss crystals: each one gets a run member (`E.shareIndex`) as its owner and starts its pull right away. The starts are staggered, so the crystals burst out and then fly in. `d.forced` skips the 100-stud and line-of-sight cancels.
- `D.sweep()` credits every drop still on the ground or in flight as a pickup to its owner, else to the nearest living run member. The model is kept for the pull and then destroyed.

ShopService hunk:
- `finishWave` calls `Shards.sweep()` before `Shards.clear(true)`. The phase is still Combat at that point, so pickups count.

Then compile check → commit.

### Task 3: Boss super-jump intro (every wave boss)

- **BossService hunks:** `B.INTRO={drop=1.2,fall=.65,after=3.6}`.
  - A non-practice spawn sets `BossIntroStart/Land/Until`, the Slam clip timed to land on `BossIntroLand`, an anchored root, `s.intro`, and `combat.CinematicUntil`.
  - `B.step` holds him still until `BossIntroUntil`, then frees him.
  - A tutorial run uses `combat.TutorialBossHealth` instead of the scaled health.
- **CombatEffectsService hunk:** `E.hit` deals 0 to a boss before `BossIntroUntil`.
- **CharacterService hunk:** `frozen` is also true before `CinematicUntil`, so players are held and take no damage.
- **RogueliteZombieChase hunk:** enemies are frozen before `CinematicUntil`.
- **`combat/BossIntro.client.luau`:**
  - a dark growing ground shadow and a rumble;
  - the boss drawn falling (local root offset, ease-in);
  - a flat neon shockwave ring and a heavy shake on landing (respects the ScreenShake setting);
  - a ~3 s Scriptable camera orbit with the name card;
  - an ease back to the player camera. It always restores the camera, even if the boss goes away mid-intro.
- Compile check → commit.

### Task 4: TutorialDirector + the run hooks

ShopService hunks (all guarded by `S.tutorial`):
- starting shards;
- forced offer;
- per-wave count and roster;
- a long wave clock (the director ends the wave);
- no shop timer.

Other hunks:
- **CharacterService:** health floor at 1 while `TutorialRun`.
- **RogueliteZombieChase:** no respawn while `WaveNoRespawn`.

**`TutorialDirector.server.luau`:**
- `apply(on)` sets or clears `Shop.tutorial`, `Shards.killValue` and the attributes. It restores the old `HammerBossWave`, and resets shards for players already in a wave-1 shop.
- It counts deaths of `Zombie_nn` enemies. Each wave ends when its quota is dead, when the wave has no enemies left after 6 s, or after `MAX_WAVE_SECONDS`. It ends a wave by setting `WaveEndsAt=now`, so a boss still holds the wave open.
- It switches off once the tutorial is won and nobody is in the run any more.
- **Lobby role:** a player whose `ProfileTutorial` is `Run` is launched into a solo tutorial match (`Match.launch(...,{tutorial=true})`), with one retry.
- **Studio Combined with `Workspace.StudioTutorial`:** it switches the mode on, puts the player in the Pine Valley arena as a Brawler with the pan, and starts wave 1 once they're a run member.

MatchService hunks:
- `launch` writes `tutorial` into the entry;
- `start` sets `TutorialRun` from it.

Then compile check → commit.

### Task 5: Profile, reward, victory

ProfileService hunks:
- `fresh().tutorial={step='Run'}`. A save without it counts as done, and so does Studio without `StudioTutorial`.
- `ProfileTutorial` attribute.
- `P.tutorialReward` (once).
- `P.tutorialStep` (forward only).
- The seeded first Silver Chest in `openChest`.

RogueliteMeta hunks:
- guarded `TutorialConfig` require;
- the first `onWaveCleared` skips map progress, emeralds and quests in a tutorial run;
- a new listener after `afterLeave`: the boss-wave clear pays the reward, sets `TutorialWon`, and finishes everyone as Victory after `VICTORY_DELAY`;
- `RunResult.tutorial`;
- the `ProfileAction 'TutorialStep'` action.

Then compile check → commit.

### Task 6: Results screen + lobby hook

- **RunResultsUI hunks** (only when `r.tutorial`):
  - the emeralds count up;
  - the third tile becomes SILVER CHESTS ×3;
  - the tiles pop in one after another;
  - PLAY AGAIN is hidden and LOBBY is the centred primary button.
- **LobbyUI hunk:** a `GuideOpenWindow` BindableEvent in every build, so the guide can open the Store on the Bundles tab and close it.
- Compile check → commit.

### Task 7: Art: arrow + portrait

- `make_arrow.py`: a chunky white arrow with a black outline and a soft drop shadow, 256×256, pointing up.
- `render_portrait.py`: opens `merchant.blend` (built by `build_merchant.py`) and renders a 3/4 head-and-shoulders bust with a transparent film to `previews/merchant-portrait.png` (512²).
- Look at both images → commit. The PNGs are small, so they're committed.

### Task 8: HTML mockup

- `previews/tutorial-guide/guide.html`:
  - the real `panel.png` nine-slice, the portrait and the arrow;
  - a mock shop with level-up cards and buttons;
  - the arrow gliding between them on a curve, turning, and bobbing at rest;
  - typewriter lines.
- Serve it from the dev server, check it in the browser pane, and send it to the user.

### Task 9: TutorialGuideUI + TutorialGuide.client

- **The UI module:**
  - `new(player)` → `{say(id,text,opts), hide(), point(guiObject or nil), banner(top,big,seconds), destroy()}`;
  - the arrow follows its target every frame. A new target starts an eased 0.55 s curve (quadratic Bézier with a sideways bulge) with the rotation tweened; at rest it bobs 8 px along its pointing axis;
  - the target's layer insets are converted to screen space.
- **The client step machine:**
  - **Run part:** Welcome → Pan → Crystals → LevelUp → Shop (Glock) → ShopGo → Survive → LevelUp2/Shop2 → Boss → RedCircle → BossDown + VICTORY banner → Loot (LOBBY button).
  - **Lobby part:** Chests (Bottom.Chests → Row_Silver → Open → tap → Claim/Again) → Armory (Exit → Bottom.Armory → W_01 → Upgrades → UpgradeBig) → Equip (Tab_Armor → A_Iron.Helmet → Equip) → Offer (Armory Close → Store/Bundles with NO THANKS) → Play (Bottom.Play, 10 s) → Done.
  - During a guided lobby step the other bottom buttons are dimmed and can't be clicked.
- Preview the module in a CoreGui frame (not saved) → compile check → commit.

### Task 10: Studio sync (needs the user's okay)

- Upload `arrow.png` and `merchant-portrait.png` and put the ids in `TutorialConfig.Asset`.
- Run `python combat/tutorial_hunks.py --json`, then `tools/LaunchSync.luau` for the new Scripts/LocalScripts and `tools/SyncPlan.luau` for the modules and hunks. Each is a dry run first, then the real run, all or nothing, guarded on Studio's Source.
- New modules get `Sandboxed=true` plus Capabilities copied from a sibling (`TutorialConfig` from `CharacterStats`).
- Re-check that every written script matches the commit.

### Task 11: Docs + hand-over

- Spec status set to Built.
- `LOBBY_AND_FIRST_RUN.md`.
- `ui/README.md` entry with what was checked.
- Hand-over notes for the user's play-test:
  - `StudioTutorial=true`;
  - what to watch: boss time, arrow smoothness, can't die, crystals flying in, the lobby steps.
