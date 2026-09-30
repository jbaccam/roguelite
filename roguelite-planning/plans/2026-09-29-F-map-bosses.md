# Plan F: Map Bosses (King Crab, Frost Cyclops, Pharaoh, Dragon)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put the four Blender-built bosses into the roguelite place as fightable bosses: animated skinned models, server-owned attacks with ground warnings and hit shapes, polished client VFX, the HUD boss bar, the admin spawner and Beach Cove's wave-20 trigger. The Hammer boss must keep working exactly as it does now.

**Architecture:**
- The Hammer boss stays on its own code (`BossService`, `BossMotion`, `BossPresentation`).
- The four new bosses share one data-driven runtime:
  - `MapBossDefs`: per-boss numbers and attack list.
  - `MapBossTiming`: generated clip timings and sampled gameplay points.
  - `MapBossShapes`: shared hit/warning geometry.
  - `MapBossService`: the server state machine.
  - `MapBossPresentation.client`: animation, warnings and VFX dispatch.
  - `BossVfx/<Boss>`: client-only effects.
- Models come through Studio's 3D Importer, the same as the regular mobs.
- Animations are sampled `Bone.Transform` modules built by a Python pipeline adapted from the regular-mob one.
- Effects are client-only and never affect hits.

**Tech stack:**
- Roblox Luau.
- Roblox Studio via the Studio MCP: `execute_luau`, `upload_image`, `search_asset`/`insert_asset` (toolbox sounds), `get_console_output`, and plain `screen_capture` only.
- Windows-MCP for driving Studio's 3D Importer dialog.
- Python 3 with numpy for the build pipeline, Blender 5.2 headless for the asset side, and the local file server for syncing.

**Spec:** approved by the user on 2026-09-29 in chat, recorded in `MAP_MOB_ROSTER.md` "Boss direction". The Blender deliverables are defined in `plans/BOSS_GAME_PACKAGE_SPEC.md`, and the VFX asset kit is in `boss-vfx-kit/`.

---

## Conventions (read before any task)

Everything in Plan D's "Conventions" section applies unchanged (`plans/2026-09-28-D-admin-panel.md`, lines 24–140). That covers the paths table style, the Studio MCP rules, the local file server, the Edit helper (`pull`, `sync`, `create`, `fresh`), Play checks, and `serverCheck`.

Two rules from memory are repeated here:
- The user play-tests; don't start your own Play sessions except for the Play checks listed in this plan. Check `list_sessions` and `get_studio_state` before any `start_stop_play`. Another session ("Roguelite leaderboard shops") shares this Studio.
- Never leave Studio broken between tasks. Every task ends with the place in a working state, and the Hammer boss still spawnable.

**New instances and their sandbox kind.** None of the new code is required by sandboxed code, so everything new is **unsandboxed** (plain `create(...)` without `capsFrom`).

| Repo file | Studio instance |
|---|---|
| `studio-prototype/combat/bosses/MapBossShapes.luau` (new) | `RS.RogueliteCombat.MapBossShapes` (ModuleScript) |
| `studio-prototype/combat/bosses/MapBossShapesTests.luau` (new) | `SS.RogueliteTests.MapBossShapesTests` |
| `studio-prototype/combat/bosses/MapBossDefs.luau` (new) | `RS.RogueliteCombat.MapBossDefs` |
| `studio-prototype/combat/bosses/MapBossTiming.luau` (generated) | `RS.RogueliteCombat.MapBossTiming` |
| `studio-prototype/combat/bosses/BossAnimations/<id>/…` (generated) | `RS.RogueliteCombat.BossAnimations.<id>` |
| `studio-prototype/combat/bosses/MapBossService.luau` (new) | `SSS.MapBossService` (ModuleScript) |
| `studio-prototype/combat/bosses/MapBossPresentation.client.luau` (new) | `SPS.MapBossPresentation` (LocalScript) |
| `studio-prototype/combat/bosses/BossVfx/*.luau` (new) | `RS.RogueliteCombat.BossVfx.<Name>` |
| `studio-prototype/combat/bosses/BossVfxAssets.luau` (new) | `RS.RogueliteCombat.BossVfxAssets` (ids table; meshes live under it as children) |
| `studio-prototype/combat/bosses/InstallMapBossTemplates.luau` (new, run once per import) | not installed; run via `execute_luau` |
| `studio-prototype/combat/bosses/DumpBossReceipt.luau` (new) | not installed; run via `execute_luau` |
| `studio-prototype/combat/bosses/retarget_boss.py`, `build_boss_modules.py` (new) | none (build pipeline) |
| `hammer-boss/BossEncounter.server.luau` (modify) | `SSS.BossEncounter` |
| `studio-prototype/combat/ZombieDeath.luau`, `ShardDropService.luau`, `MapConfig.luau`, `AdminConfig.luau`, `AdminService.server.luau` (modify) | same names |
| `studio-prototype/RogueliteZombieChase.server.luau`, `ui/RogueliteHUD.client.luau`, `ui/AdminPanelUI.luau` (modify) | same names |

`ZombieDeath`, `ShardDropService`, `MapConfig` and `AdminConfig` are sandboxed. The edits below only change attribute checks and constants inside them; they add **no** new requires.

**Coordinates.**
- Blender assets use Z up and face −Y. Studio uses Y up and faces −Z.
- The confirmed import mapping is **Studio = (−Bx, Bz, By)**. It's a proper rotation (determinant +1), so yaw sense is preserved.
- All gameplay points in `MapBossTiming` are in the boss's **ground frame**: `groundCF = root.CFrame * CFrame.new(0, -rootHeight, 0)`, in Studio axes, with forward = −Z.
- Angles are signed yaw about +Y. Positive turns toward −X, the boss's left, which matches `CFrame.Angles(0, θ, 0)`.

**Boss ids.**

| Id | Template | Display name |
|---|---|---|
| `KingCrab` | `KingCrab_NPC` | GIANT KING CRAB |
| `FrostCyclops` | `FrostCyclops_NPC` | FROST CYCLOPS |
| `Pharaoh` | `Pharaoh_NPC` | THE PHARAOH |
| `Dragon` | `Dragon_NPC` | INFERNO DRAGON |

Asset folders: `king-crab-boss`, `frost-cyclops-boss`, `pharaoh-boss`, `dragon-boss`. Animation ids: `king-crab`, `frost-cyclops`, `pharaoh`, `dragon`.

---

## Phase 1 — Import

### Task 1: Import the five FBX files into Studio

**Precondition:** every boss folder has `exports/game/<Boss>_Studio.fbx` and `AnimationData.json`, and `boss-vfx-kit/exports/fbx/AllMeshes.fbx` exists.

**Files:** none in the repo. Creates `ServerStorage.MapBossRawImports.<Id>` and `ServerStorage.MapBossRawImports.VfxKit`.

- [ ] **Step 1: Check Studio is idle.** Run `list_roblox_studios`, `get_studio_state` (Edit) and `list_sessions`. If another session is mid-Play, wait.
- [ ] **Step 2: Import each FBX with Studio's 3D Importer**, driven through Windows-MCP.
  1. Bring Studio to the foreground and choose File → Import 3D.
  2. Paste the absolute FBX path into the file dialog.
  3. In the importer, keep **Rig General / skinned**, turn **Upload to Roblox on** and **Insert using scene position off**, then click Import.
  4. After each import, move the inserted Model: `ServerStorage.MapBossRawImports.<Id>` in Edit.

  If the importer UI can't be driven reliably, stop and ask the user to do these five imports by hand, and give them the five paths.
- [ ] **Step 3: Normalise the scale.** For each raw boss import, run `if not m:GetAttribute('ImportBaselineScale') then m:ScaleTo(0.01); m:SetAttribute('ImportBaselineScale', 0.01) end`. Expect the bounding-box height to be within 5% of the manifest's `height`. Also normalise the VfxKit import, and check that `IceSpike_E` is about 13 studs tall.
- [ ] **Step 4: Dump the receipts.** Run `DumpBossReceipt.luau` (Task 2) for each boss and write the output to `studio-prototype/combat/bosses/receipts/<id>-receipt.json`. Expect: every deform bone name from `AnimationData.json` is present, one MeshPart per section, and every MeshId and TextureID starts with `rbxassetid://`.
- [ ] **Step 5: Commit** the receipts (`git add studio-prototype/combat/bosses/receipts`).

### Task 2: `DumpBossReceipt.luau`

**Files:** Create `studio-prototype/combat/bosses/DumpBossReceipt.luau`. Its receipt schema is identical to the one in `mob-production/studio-import/*-receipt.json`, so `retarget_boss.py` can reuse the regular-mob math.

- [ ] **Step 1: Write the dumper.**

```lua
-- Edit-mode only. Returns a JSON receipt of one raw boss import (bones, meshes, scale),
-- in the regular-mob receipt schema. Run: loadstring-free, paste into execute_luau with ID set.
local ID=... or 'KingCrab'
local Http=game:GetService('HttpService')
local raw=game.ServerStorage.MapBossRawImports:FindFirstChild(ID);assert(raw,'missing raw import '..ID)
local function cf(c) local t={c:GetComponents()};for i,v in t do t[i]=math.round(v*1e7)/1e7 end;return t end
local rootPart=raw:FindFirstChild('RootPart') or raw.PrimaryPart
local bones,meshes={}, {}
for _,d in raw:GetDescendants() do
 if d:IsA('Bone') then
  local parent=d.Parent:IsA('Bone') and d.Parent.Name or 'RootPart'
  table.insert(bones,{name=d.Name,parent=parent,cframe=cf(d.CFrame)})
 elseif d:IsA('MeshPart') then
  table.insert(meshes,{name=d.Name,meshId=d.MeshId,textureId=d.TextureID,cframe=cf(rootPart.CFrame:ToObjectSpace(d.CFrame)),size={d.Size.X,d.Size.Y,d.Size.Z}})
 end
end
return Http:JSONEncode({id=ID,scale=raw:GetScale(),pivot=cf(raw:GetPivot()),rootPartCFrame=cf(rootPart.CFrame),bones=bones,meshes=meshes})
```

- [ ] **Step 2: Run it for one boss.** Expect a JSON string whose `bones` count equals the boss's deform bone count from `manifest.json`.
- [ ] **Step 3: Commit.**

### Task 3: Retarget and build the animation modules

**Files:**
- Create `studio-prototype/combat/bosses/retarget_boss.py`.
- Create `studio-prototype/combat/bosses/build_boss_modules.py`.
- These generate `studio-prototype/combat/bosses/BossAnimations/<id>/…` and `studio-prototype/combat/bosses/MapBossTiming.luau`.

- [ ] **Step 1: Write `retarget_boss.py`.** Copy `mob-production/combat-ready/retarget_studio.py` and change three things:
  1. It takes `<asset-folder> <id>` and reads `<asset-folder>/exports/game/AnimationData.json` plus `studio-prototype/combat/bosses/receipts/<id>-receipt.json`.
  2. It writes `<asset-folder>/exports/game/StudioAnimationData.json` and `StudioRetargetChecks.json`.
  3. It **fails** (non-zero exit) when the maximum retarget error is ≥ 2e-5, instead of only recording it.

  The Bone-mode math (`reflect = diag(-1,1,1,1)` and the `desired`/`local_inv` chain) stays unchanged.
- [ ] **Step 2: Run it** for all four bosses. Expected: each prints `max error < 2e-5` and writes both files.
- [ ] **Step 3: Write `build_boss_modules.py`.** Base it on `studio-prototype/combat/build_enemy_animation_modules.py`, with the same 190,000-character chunking and `Frames` sub-modules. It differs in these ways:
  - It reads each `<asset-folder>/exports/game/StudioAnimationData.json` and writes to `studio-prototype/combat/bosses/BossAnimations/<id>/`.
  - It requires the clips `Idle`, `Walk`, `Hit`, `Death` and every attack clip listed for that boss in `MapBossDefs.ATTACK_CLIPS`. That list is mirrored in the script as the dict `ATTACKS`:

    ```python
    ATTACKS = {
        'king-crab': ['ClawCrush', 'RushStart', 'RushLoop', 'RushEnd', 'BubbleBarrage'],
        'frost-cyclops': ['GroundSlam', 'Stomp'],
        'pharaoh': ['CursedBolts', 'TombEruption'],
        'dragon': ['FireBreath', 'TailWhip', 'FrontStomp'],
    }
    ```

  - It writes `MapBossTiming.luau`, which returns `{[id] = {rootHeight, height, footprintRadius, strideLength, rushStrideLength?, clips = {[clip] = duration}, attacks = {...}}}`. Each attack comes from `BossGameData.json` with its times kept as they are. Every named point is **re-sampled every 1/24 s from `warnStart` to `recoveryEnd`** by forward kinematics over the *original* AnimationData bones, then mapped to Studio axes with `(-x, z, y)`. The sample-point entries are:

    ```python
    def worlds(bones, transforms):  # same as retarget_studio.worlds, in the Y/Z-swapped basis
        ...
    def sample_point(data, clip, bone, offset, t):
        frames = data['clips'][clip]['frames']; i = min(int(round(t * 24)), len(frames) - 1)
        w = worlds(data['bones'], frames[i]['transforms'])[bone]
        # offset is Blender bone-local (x,y,z); the basis swap makes it (x,z,y) in this space
        p = w @ np.array([offset[0], offset[2], offset[1], 1.0])
        return [-p[0], p[1], p[2]]          # Studio ground frame (-X, Z, Y) after the swap
    ```

    The output entry is `samples = {pointName = {{t, x, y, z}, ...}}`.
  - Dragon `TailWhip`: also sample `Tail_5` as the point `TailMid`, so a capsule can be built.
  - Pharaoh `CursedBolts`, Dragon `FireBreath` and Crab `BubbleBarrage`: also store each point's forward direction per sample. That is the bone's local −Y axis after the same swap and flip.
- [ ] **Step 4: Run it.** Expected: it prints each id with a byte count, and every module under 190,000 characters. Check the vertical coordinates by hand: `MapBossTiming['frost-cyclops'].attacks.GroundSlam.samples.ClubImpact` at `impact` should have y ≈ 0 (±0.15) and z < 0 (in front of the boss).
- [ ] **Step 5: Commit.**

### Task 4: Assemble the boss templates

**Files:** Create `studio-prototype/combat/bosses/InstallMapBossTemplates.luau`.

- [ ] **Step 1: Write the installer.** It follows `InstallRegularEnemyTemplates.luau`. For each id in `{'KingCrab','FrostCyclops','Pharaoh','Dragon'}` it does the following:
  1. Clone `SS.MapBossRawImports[id]` into a template named `<id>_NPC`. Keep the raw import untouched.
  2. Destroy the importer's `AnimationController`.
  3. Add an invisible `HumanoidRootPart`:
     - Size `(footprint, rootHeight*2, footprint)`, where footprint = `min(8, footprintRadius)`.
     - Placed at the armature origin + `(0, rootHeight, 0)`. The armature origin is `RootPart.CFrame` projected to the lowest mesh Y.
     - `CanCollide=true`, `Massless=false`.
     - Set it as `PrimaryPart`.
  4. Weld every MeshPart that isn't a `Motor6D.Part1` to the HRP with a `WeldConstraint "EnemyRootWeld"`. Every MeshPart gets `CanCollide=false`, `CanQuery=true`, `CanTouch=false`.
  5. Add a Humanoid with these settings:
     - RigType R15, `RequiresNeck=false`, `BreakJointsOnDeath=false`.
     - `HipHeight = rootHeight - HRP.Size.Y/2` (clamped ≥ 0), and `MaxHealth = Health = MapBossDefs[id].health`.
     - `DisplayDistanceType=None`.
     - Add an Animator.
  6. Textures:
     - Every section MeshPart gets `TextureID` = the importer's texture, plus `RenderFidelity=Precise`.
     - Remove any importer `SurfaceAppearance`. (Memory: MCP-uploaded images on a SurfaceAppearance render blank in Play; TextureID is safe.)
     - Sections named `EyeGlow` or `LavaGlow` get `Material=Neon`, `TextureID=''` and `Color` = defs `glowColor`.
  7. Set these attributes: `IsBoss=true`, `IsMapBoss=true`, `MapBossId=id`, `BossName=defs.name`, `EnemyBaselineModelScale=0.01`, `MapBossRootHeight=rootHeight`, `ContactDamage=0`, `ContactRange=0`, `BaseMoveSpeed=defs.chaseSpeed`, and `SourceAsset=<asset-folder>/exports/game/<Boss>_Studio.fbx`.
  8. Parent the template to `SS.RogueliteNPCs`, replacing any older `<id>_NPC`, which is backed up to `SS.BeforeMapBoss_<yyyymmdd>`.

  Then, for the VFX kit, clone `SS.MapBossRawImports.VfxKit`'s MeshParts into `RS.RogueliteCombat.BossVfxAssets` as child templates named after each asset. Set them Anchored, with CanCollide, CanQuery and CanTouch false and CastShadow false.
- [ ] **Step 2: Run it.** Expected output: `INSTALLED KingCrab|FrostCyclops|Pharaoh|Dragon`, with each template's bone count, HRP height and `HipHeight`, plus `VFX_MESHES n`.
- [ ] **Step 3: Visual check.** In Edit, clone each template into `workspace.MapBossPreview`, spaced 40 studs apart on the Beach Cove floor, and take one plain `screen_capture`. Expected: all four stand on the ground, textured, at their authored sizes (crab spikes about 10 studs, Cyclops about 13). Delete the preview folder afterwards.
- [ ] **Step 4: Commit.**

---

## Phase 2 — Shared runtime

### Task 5: `MapBossShapes` + tests

**Files:**
- Create `studio-prototype/combat/bosses/MapBossShapes.luau`.
- Create `studio-prototype/combat/bosses/MapBossShapesTests.luau`.

- [ ] **Step 1: Write the failing tests.**

```lua
-- MapBossShapesTests: run with fresh(require) in Edit; returns PASS/FAIL lines.
local S=require(game.ReplicatedStorage.RogueliteCombat.MapBossShapes)
local r={};local function add(ok,m) table.insert(r,(ok and 'PASS ' or 'FAIL ')..m) end
local F=Vector3.new(0,0,-1)
add(S.contains({kind='circle',center=Vector3.zero,radius=5},Vector3.new(4.9,0,0)),'circle inside edge')
add(not S.contains({kind='circle',center=Vector3.zero,radius=5},Vector3.new(5.1,0,0)),'circle outside edge')
add(S.contains({kind='line',origin=Vector3.zero,direction=F,length=20,width=4},Vector3.new(1.9,0,-19)),'line inside far corner')
add(not S.contains({kind='line',origin=Vector3.zero,direction=F,length=20,width=4},Vector3.new(0,0,1)),'line excludes behind origin')
add(S.contains({kind='cone',origin=Vector3.zero,direction=F,halfAngle=math.rad(25),length=18},Vector3.new(-3,0,-10)),'cone inside')
add(not S.contains({kind='cone',origin=Vector3.zero,direction=F,halfAngle=math.rad(25),length=18},Vector3.new(-8,0,-8)),'cone excludes 45 degrees')
add(math.abs(S.yaw(F,Vector3.new(-1,0,0))-math.pi/2)<1e-6,'yaw +90 is the left (-X)')
add(S.contains({kind='arc',pivot=Vector3.zero,forward=Vector3.new(0,0,1),from=math.rad(-100),to=math.rad(100),inner=4,outer=18},Vector3.new(0,0,10)),'arc behind boss inside')
add(not S.contains({kind='arc',pivot=Vector3.zero,forward=Vector3.new(0,0,1),from=math.rad(-100),to=math.rad(100),inner=4,outer=18},Vector3.new(0,0,-10)),'arc excludes the front')
add(S.contains({kind='circle',center=Vector3.zero,radius=5},Vector3.new(0,3.9,0)),'height band inside')
add(not S.contains({kind='circle',center=Vector3.zero,radius=5},Vector3.new(0,6,0)),'height band excludes a jumper above 5.5')
local segs=S.outline({kind='cone',origin=Vector3.zero,direction=F,halfAngle=math.rad(25),length=18},24)
add(#segs>=24,'cone outline has segments')
return table.concat(r,'\n')
```

- [ ] **Step 2: Run the tests.** Expected: an error saying the module `MapBossShapes` is missing.
- [ ] **Step 3: Write the module.**

```lua
-- Shared boss hit and warning geometry. The server's hit tests and the client's ground
-- warnings read the same shape tables, so a warning is exactly where damage lands.
-- Shapes are flat on the ground; `contains` also requires the point within a height band.
local S={}
S.HEIGHT_BELOW,S.HEIGHT_ABOVE=2,5.5 -- players jumping over a low wave clear it
local function flat(v) return Vector3.new(v.X,0,v.Z) end
S.flat=flat
-- Signed yaw from a to b about +Y; positive turns toward -X for a -Z forward (CFrame.Angles).
function S.yaw(a,b) a,b=flat(a),flat(b);return math.atan2(a:Cross(b).Y,a:Dot(b)) end
local function band(shape,point)
 local base=(shape.center or shape.origin or shape.pivot).Y
 return point.Y>=base-S.HEIGHT_BELOW and point.Y<=base+S.HEIGHT_ABOVE
end
function S.contains(shape,point)
 if not band(shape,point) then return false end
 local k=shape.kind
 if k=='circle' then return flat(point-shape.center).Magnitude<=shape.radius end
 if k=='line' then
  local d=flat(point-shape.origin);local along=d:Dot(shape.direction)
  return along>=0 and along<=shape.length and (d-shape.direction*along).Magnitude<=shape.width/2
 end
 if k=='cone' then
  local d=flat(point-shape.origin);local dist=d.Magnitude
  return dist<=shape.length and (dist<1e-3 or math.abs(S.yaw(shape.direction,d))<=shape.halfAngle)
 end
 if k=='arc' then
  local d=flat(point-shape.pivot);local dist=d.Magnitude
  if dist<shape.inner or dist>shape.outer then return false end
  local a=S.yaw(shape.forward,d);return a>=shape.from and a<=shape.to
 end
 if k=='capsule' then
  local ab=flat(shape.b-shape.a);local ap=flat(point-shape.a);local t=math.clamp(ap:Dot(ab)/math.max(ab:Dot(ab),1e-6),0,1)
  return (ap-ab*t).Magnitude<=shape.radius
 end
 return false
end
-- Outline points (world, flat) for a warning renderer: a closed polygon.
function S.outline(shape,n)
 n=n or 32;local pts={}
 local function rot(v,a) return CFrame.Angles(0,a,0):VectorToWorldSpace(v) end
 if shape.kind=='circle' then
  for i=0,n-1 do local a=i/n*math.pi*2;table.insert(pts,shape.center+Vector3.new(math.sin(a),0,math.cos(a))*shape.radius) end
 elseif shape.kind=='line' then
  local side=Vector3.new(-shape.direction.Z,0,shape.direction.X)*shape.width/2;local far=shape.origin+shape.direction*shape.length
  pts={shape.origin+side,far+side,far-side,shape.origin-side}
 elseif shape.kind=='cone' then
  table.insert(pts,shape.origin)
  for i=0,n do local a=-shape.halfAngle+2*shape.halfAngle*i/n;table.insert(pts,shape.origin+rot(shape.direction,a)*shape.length) end
 elseif shape.kind=='arc' then
  for i=0,n do local a=shape.from+(shape.to-shape.from)*i/n;table.insert(pts,shape.pivot+rot(shape.forward,a)*shape.outer) end
  for i=n,0,-1 do local a=shape.from+(shape.to-shape.from)*i/n;table.insert(pts,shape.pivot+rot(shape.forward,a)*shape.inner) end
 end
 return pts
end
return S
```

- [ ] **Step 4: Sync and run the tests.** Use `create('ModuleScript','MapBossShapes',RS.RogueliteCombat,'studio-prototype/combat/bosses/MapBossShapes.luau')`, then run the tests module with `fresh`. Expected: every line `PASS`.
- [ ] **Step 5: Commit.**

### Task 6: `MapBossDefs`

**Files:** Create `studio-prototype/combat/bosses/MapBossDefs.luau`.

The numbers below are starting values for the user to tune in play-testing. Health climbs with the map ladder from the Hammer boss's 1,800.

- [ ] **Step 1: Write the defs.**

```lua
-- Per-boss gameplay numbers for the map-boss runtime (plan F). Clip timings and sampled
-- points come from the generated MapBossTiming; this file owns health, speed, damage,
-- ranges, cooldowns and attack order. Every value is a starting point for play-testing.
local Timing=require(script.Parent:WaitForChild('MapBossTiming'))
local D={}
D.Order={'KingCrab','Pharaoh','FrostCyclops','Dragon'}
D.KingCrab={anim='king-crab',name='Giant King Crab',health=2400,chaseSpeed=13,glowColor=nil,deathSeconds=nil,
 attacks={
  ClawCrush={clip='ClawCrush',range={0,11},cooldown=2.6,damage=28,shape='circle',point='ClawImpact',radius=6.5},
  SidewaysRush={clips={'RushStart','RushLoop','RushEnd'},range={6,40},cooldown=4.5,damage=24,shape='lane',length=38,width=9,speed=30},
  BubbleBarrage={clip='BubbleBarrage',range={8,34},cooldown=4,damage=10,shape='projectiles',point='BubbleOrigin',count=9,spread=math.rad(38),speed=22,radius=1.5,life=2.6,perPlayer=2},
 },order={'ClawCrush','BubbleBarrage','ClawCrush','SidewaysRush'}}
D.Pharaoh={anim='pharaoh',name='The Pharaoh',health=3000,chaseSpeed=12,glowColor=Color3.fromRGB(120,235,255),
 attacks={
  CursedBolts={clip='CursedBolts',range={8,44},cooldown=2.8,damage=22,shape='projectiles',point='BoltOrigin',count=3,spread=math.rad(18),speed=34,radius=1.2,life=2.2,perPlayer=1},
  TombEruption={clip='TombEruption',range={0,60},cooldown=5,damage=30,shape='targets',radius=4.5,maxTargets=5,eruptDelay=0.9},
 },order={'CursedBolts','CursedBolts','TombEruption'}}
D.FrostCyclops={anim='frost-cyclops',name='Frost Cyclops',health=3600,chaseSpeed=11,glowColor=nil,
 attacks={
  GroundSlam={clip='GroundSlam',range={0,10},cooldown=3,damage=32,shape='circle',point='ClubImpact',radius=11,knockdown=0.7},
  Stomp={clip='Stomp',range={6,26},cooldown=4.2,damage=30,shape='wave',point='StompImpact',length=26,width=5,travel=40},
 },order={'GroundSlam','Stomp','GroundSlam','Stomp','Stomp'}}
D.Dragon={anim='dragon',name='Inferno Dragon',health=4500,chaseSpeed=12,glowColor=Color3.fromRGB(255,150,40),
 attacks={
  FireBreath={clip='FireBreath',range={4,20},cooldown=4,damage=12,shape='breath',point='FireOrigin',halfAngle=math.rad(22),length=20,tick=0.4},
  TailWhip={clip='TailWhip',range={0,17},cooldown=3.4,damage=34,shape='sweep',point='SpadeTip',mid='TailMid',radius=3},
  FrontStomp={clip='FrontStomp',range={0,11},cooldown=3.6,damage=38,shape='circle',point='StompCenter',radius=10,knockdown=0.8},
 },order={'FireBreath','FrontStomp','TailWhip','FireBreath','TailWhip'}}
D.ATTACK_CLIPS={['king-crab']={'ClawCrush','RushStart','RushLoop','RushEnd','BubbleBarrage'},['frost-cyclops']={'GroundSlam','Stomp'},['pharaoh']={'CursedBolts','TombEruption'},['dragon']={'FireBreath','TailWhip','FrontStomp'}}
function D.get(id) return D[id] and type(D[id])=='table' and D[id].anim and D[id] or nil end
function D.timing(id) local d=D.get(id);return d and Timing[d.anim] end
function D.isBoss(id) return D.get(id)~=nil end
return D
```

  The Dragon's `FrontStomp` point `StompCenter` is the midpoint of `LeftFrontImpact` and `RightFrontImpact`. `build_boss_modules.py` must emit it: add a derived point that averages the two samples at each time.
- [ ] **Step 2: Sync.** Use `create(...)` into `RS.RogueliteCombat`, together with the generated `MapBossTiming` and the `BossAnimations` folder.

  For the folder, create `RS.RogueliteCombat.BossAnimations` as a Folder. Write each `<id>/init.luau` as a ModuleScript named `<id>`, and each clip module as its child. Each chunked clip becomes a ModuleScript with `FramesNN` children.

  Then `fresh(require)` `MapBossDefs` and check `D.timing('frost-cyclops').attacks.GroundSlam.impact > 0`.
- [ ] **Step 3: Commit.**

### Task 7: `MapBossService`, the server

**Files:** Create `studio-prototype/combat/bosses/MapBossService.luau`, installed as `SSS.MapBossService` (ModuleScript, unsandboxed).

**Responsibilities.** These mirror `hammer-boss/BossService.luau`; read it first.

`M.spawn(id, cf, practice)`:
- Clones `SS.RogueliteNPCs[<id>_NPC]`, sets `BossPractice`, and sets WalkSpeed to `chaseSpeed`.
- Puts it in `workspace.RogueliteEnemies` with the server as network owner.
- Tags it `RogueliteZombie` and `MapBoss`, and connects `Died` → `ZombieDeath.finish`.
- Sets the attribute `BossHitStart` on damage outside attacks, the same as the Hammer boss.

`M.step`, run every Heartbeat for each boss:
- **Target:** the nearest living player.
- **Picking an attack:** walk `order` from `s.index` and pick the first attack whose `range` contains the flat distance and whose cooldown has expired. If none fits, chase with `h:MoveTo(target.Position)`. Keep `ZombiesEnabled`, `AdminFreeze` and `BossManual` behaviour identical to BossService lines 132–153.
- **Starting an attack:**
  1. Face the target and anchor the root.
  2. Record `s.attack = {kind, start = now, cf = root.CFrame, ground = <ground raycast Y>, hits = {}, ticks = {}}`.
  3. Set the attributes `BossAttack`, `BossStart`, `BossFrame`, `BossGroundY`, `Attacking = true`, and increment `BossSerial`.
  4. Store attack-specific data as JSON in the attribute `MapBossAttackData` (below).
- **Per-shape data and hit tests.** Build every shape in world space from `cf` and the sampled points. `ground = cf * CFrame.new(0, -rootHeight, 0)`, and a point's world position is `ground * Vector3.new(x, y, z)`.

  | Shape | Hit test |
  |---|---|
  | `circle` | Circle at the attack point's sample at `impact`. Tested once at `impact`. |
  | `wave` | Line from the point at `impact` along the attack's `directionAtImpactStudio` (fall back to −Z of `cf`), of `length` and `width`. A player at along-distance `d` is tested at time `impact + d / travel`. |
  | `lane` (crab) | Picked at start. Direction = ±X of `cf`, whichever side the target is on; length is clamped by a raycast at body height. Data: `{dir = {x, z}, length}`. Server-side root motion: after `RushStart`'s duration, move `root.CFrame` along the lane at `speed` for `length / speed` seconds. Each Heartbeat, test a capsule from the previous body position to the current one with radius `width / 2`. Then play `RushEnd`. Total duration = `RushStart + length / speed + RushEnd`. |
  | `projectiles` | At `impact`, spawn `count` server projectiles. Origin = the point's sample at `impact`; the directions are spread evenly across `±spread/2` about the flat direction to the target (Crab: about the mouth direction). They move straight at `speed` for `life` seconds and stop on world geometry (a raycast every step). They hit a player root within `radius + 1.2`, at most `perPlayer` hits per player. Data: `{origin, yaws}`, plus the attribute `MapBossShotEnds` (a JSON map index → end time) whenever one stops. |
  | `targets` (tomb) | At `warnStart`, snapshot up to `maxTargets` living players within `range[2]`, as ground positions. Data: `{points = {{x, y, z}, …}}`. Each circle erupts at `impact + eruptDelay`. |
  | `breath` | Every 1/30 s from `impact` to `activeEnd`, build a cone from the point's sample and direction at that time, with `halfAngle` and `length`. Deal `damage` to a player at most once per `tick`. |
  | `sweep` | Every 1/60 s from `impact` to `activeEnd`, build a capsule from `TailMid` to `SpadeTip` at that time, with `radius`. One hit per player. |

  Every hit also needs the line-of-sight raycast from BossService line 120. Damage goes through `Characters.contact(p, damage)`.

  `knockdown` attacks also fire the RemoteEvent `RS.RogueliteCombat.MapBossKnockdown` to the hit player, with `(sourcePos, seconds)`. Create it in `M` if it's missing (unsandboxed).
- **Ending an attack:** when `age >= duration`, unanchor the root, clear `Attacking`, and set the cooldown `s.next = now + cooldown`.

`M.practice(player, id)` is used by the admin spawner and is the same as `B.practice` in BossService. It spawns 20 studs ahead on open ground.

- [ ] **Step 1: Write the module.** It's about 350 lines, following the table above and the BossService patterns (exclusion raycast params, pinned `root.CFrame` during attacks, sub-stepped sampling bounded to the active window).
- [ ] **Step 2: Write `studio-prototype/combat/bosses/MapBossServiceTests.luau`.** It's a pure-function test of the `wave`, `lane` and `sweep` shape builders, which the module exports as `M._shapes` for testing. Assert these three things:
  1. A player 12 studs ahead on a Stomp wave is hit at `impact + 12/40`, not before.
  2. The lane direction points toward the target's side.
  3. The TailWhip capsule at `impact` contains the sampled `SpadeTip` position.

  Expected: all `PASS`.
- [ ] **Step 3: Sync and do a server Play check.** This is an allowed Play check; see Conventions. `serverCheck` spawns each boss with `M.spawn(id, cf, true)` 30 studs from the test player. Force each attack with `M._force(npc, kind)`, which is exported for tests. Check that each attack sets `Attacking`, ends by its `duration + 0.5`, and never deals damage before `impact`. Expected: every line `PASS`. Stop Play afterwards.
- [ ] **Step 4: Commit.**

### Task 8: Wire the runtime into the existing game

**Files:** Modify these:
- `hammer-boss/BossEncounter.server.luau` (lines 15–22)
- `studio-prototype/combat/ZombieDeath.luau` (line 20)
- `studio-prototype/combat/ShardDropService.luau` (line 87)
- `studio-prototype/combat/MapConfig.luau` (line 12)
- `studio-prototype/combat/AdminConfig.luau` (lines 14, 54)
- `studio-prototype/combat/AdminService.server.luau` (lines 92–101)
- `studio-prototype/ui/AdminPanelUI.luau` (lines 75–100)
- `studio-prototype/RogueliteZombieChase.server.luau` (lines 498, 527–545)
- `studio-prototype/ui/RogueliteHUD.client.luau` (line 118)

- [ ] **Step 1: `ZombieDeath` (line 20).** Change `if npc:GetAttribute('IsHammerBoss') then` to `if npc:GetAttribute('IsHammerBoss') or npc:GetAttribute('IsMapBoss') then`. Also change the destroy delay to `task.delay(npc:GetAttribute('BossDeathSeconds') or 2.9, ...)`. `InstallMapBossTemplates` sets `BossDeathSeconds` to the Death clip's duration + 0.6.
- [ ] **Step 2: `ShardDropService` (line 87).** Change `IsHammerBoss` to `IsHammerBoss or IsMapBoss`, so a map boss drops the boss loot.
- [ ] **Step 3: `MapConfig`.** Change BeachCove to `boss='KingCrab'` and update the comment: `boss: 'Hammer' or a MapBossDefs id`.
- [ ] **Step 4: `BossEncounter`.** Replace line 17 with:

```lua
 local map=Maps.get(Role.activeMap());if not map or not map.boss then return end
```

  and replace the spawn on line 22 with:

```lua
 if map.boss=='Hammer' then current=B.spawn(CFrame.new(ground.Position+Vector3.yAxis*(Motion.RootHeight+.1)),false)
 else
  local MB=require(script.Parent:WaitForChild('MapBossService'));local T=require(combat:WaitForChild('MapBossDefs')).timing(map.boss)
  current=T and MB.spawn(map.boss,CFrame.new(ground.Position+Vector3.yAxis*(T.rootHeight+.1)),false)
 end
```

- [ ] **Step 5: `AdminConfig`.**
  - Replace `BossId='Hammer'` with `BossId='Hammer',BossIds=table.freeze({'Hammer','KingCrab','Pharaoh','FrostCyclops','Dragon'})`.
  - On line 54, replace `if a==A.BossId then` with `if table.find(A.BossIds,a) then`.
  - `AdminService`: count bosses as `npc:GetAttribute('IsBoss') and npc:GetAttribute('AdminSpawn')`, and replace `id==Admin.BossId` with `table.find(Admin.BossIds,id)`.
  - `AdminPanelUI`: add the four options after the Hammer boss, `{id='KingCrab',name='King Crab boss'}` and so on. Replace `o.id==Admin.BossId` and `id==Admin.BossId` with `table.find(Admin.BossIds, …)`.
- [ ] **Step 6: `RogueliteZombieChase`.**
  - Line 498: `local keep = npc:GetAttribute('IsBoss') or npc:GetAttribute('AdminSpawn')`.
  - In `adminSpawn`, change the boss cap to `table.find(BossIds, id) and 5 or 50`. For ids other than `'Hammer'` in that list, call `require(script.Parent.MapBossService).spawn(id, CFrame.lookAt(at, …), true)`, where `at = point + Vector3.yAxis*(timing.rootHeight + 0.1)`. Then set `AdminSpawn` the same way as for the Hammer boss.
- [ ] **Step 7: `RogueliteHUD` (line 118).** Loop over both tags:

```lua
  for _,tag in {'HammerBoss','MapBoss'} do for _,npc in game:GetService('CollectionService'):GetTagged(tag) do
   ...same body...
  end end
```

- [ ] **Step 8: Verify.** Sync all nine files, then run an Edit parse check: `pcall(fresh, …)` on every modified ModuleScript. Expected: no errors.

  Then run the regression Play check: spawn the **Hammer** boss from `ServerStorage.AdminSpawn:Invoke('Spawn','Hammer',1,pos)`. Expected: `1`, the HUD bar reads HAMMER BRUTE, and `ClearMobs` removes it.

  Then spawn `KingCrab` the same way. Expected: `1`, and the HUD bar reads GIANT KING CRAB. Stop Play.
- [ ] **Step 9: Commit.**

### Task 9: `MapBossPresentation.client`: animation and warnings

**Files:** Create `studio-prototype/combat/bosses/MapBossPresentation.client.luau` (`SPS`, LocalScript, unsandboxed).

It follows `hammer-boss/BossPresentation.client.luau` with these changes:
- **Animation:**
  - It tracks the tag `MapBoss`.
  - It loads animation data via `EnemyMotion.compile(require(BossAnimations[anim]))`. `compile` asserts `Idle`, `Move` and `Attack`, so alias `Walk` → `Move` and the first attack → `Attack` before compiling, or add an `opts.requireBasic=false` flag to `EnemyMotion.compile`. Pick the alias; don't change EnemyMotion.
  - It uses `EnemyMotion.sample`, `blend`, `bind` and `apply` on the Bone hierarchy.
- **Clip priority:** Death > attack > Hit > Walk/Idle, exactly as BossPresentation lines 72–83. Walk phase comes from distance / `strideLength`, capped at `dt * 1.8`.
- **Crab rush:** plays `RushStart` for its duration. `RushLoop` phase = distance travelled / `rushStrideLength`. `RushEnd` plays once the server clears the lane motion, which is when `age >= RushStart + length/speed`.
- **Warnings:** from `warnStart` to `impact`, draw each attack's shape from `MapBossShapes.outline` on the ground (`BossGroundY + 0.07`).
  - Style: a translucent tinted fill (0.78 transparency) and bright edge segments (0.2 transparency), the same parts technique as BossPresentation `disc`.
  - Each boss tints its warnings to its theme:

    | Boss | Tint |
    |---|---|
    | Crab | coral `(255,120,90)` |
    | Pharaoh | gold `(255,200,80)` |
    | Cyclops | ice `(140,220,255)` |
    | Dragon | ember `(255,110,40)` |

  - The warning's fill brightens (fill transparency 0.78 → 0.55) over the last 0.25 s before impact.
  - Tomb targets draw once per point, starting from `MapBossAttackData`. Stomp and lane warnings are rectangles, the breath warning is the cone at its first sample, and the sweep warning is the arc built from the `SpadeTip` samples' min and max yaw.
- **VFX dispatch:** keep `lastSerial` like BossPresentation. Call `BossVfx[BossId].windup(ctx)` once at `warnStart`, `impact(ctx)` once at `impact`, and `active(ctx, age)` every frame while `impact <= age < activeEnd`. `ctx` holds `{npc, kind, start, cf, groundY, data, timing, attack, points(name, t) -> world Vector3, dirAt(name, t)}`.
- **Knockdown:** listen to `MapBossKnockdown` for the local player. Set `Humanoid.PlatformStand = true` for the given seconds, and apply an outward `AssemblyLinearVelocity` of 28 horizontal + 22 up, away from `sourcePos`. Then clear `PlatformStand`. Skip it if the character is dead.
- **Projectiles:** render the server's shots client-side from `MapBossAttackData.origin`, `yaws`, `speed` and `life`, stopping at `MapBossShotEnds[i]`. Visuals come from `BossVfx[id].projectile(ctx, i)`, which returns a part and a per-frame `update(dt)`.

- [ ] **Step 1: Write the script**, plus a minimal `BossVfx/Common.luau` (Task 10, Step 1) so it runs.
- [ ] **Step 2: Sync.** Do a Client Play check: spawn each boss with the admin spawner, force each attack from a `serverCheck`, and in the Client datamodel assert that a `BossWarning` folder exists between `warnStart` and `impact` for every attack. Expected: all `PASS`. Take one plain `screen_capture` of the Stomp warning and one of TailWhip, then stop Play.
- [ ] **Step 3: Commit.**

---

## Phase 3 — VFX

**VFX rules for every attack**, from `WEAPON_VFX.md`, `COMBAT_FEEL_AUDIO_VFX.md` and the art direction:
- Effects are client-only and never change hits.
- Cull beyond 160 studs, except camera shake, which uses a 60-stud falloff.
- Every attack has an audible windup cue.
- Impacts stay within their budget and are cleaned up by `VfxKit.animate` or `Debris`.
- Keep the painterly low-poly look: chunky shapes, no realistic smoke walls.
- Sounds come from the Toolbox via `search_asset` (`AssetType=Audio`), free Roblox-licensed/ProSoundEffects-style entries only. Record each in `studio-prototype/ASSETS.md` in its format (id, title, creator, the "Creator Store (free, third-party)" wording), and play them through the `RogueliteSFX` SoundGroup.

### Task 10: `BossVfx/Common` and `BossVfxAssets`

**Files:**
- Create `studio-prototype/combat/bosses/BossVfx/Common.luau`.
- Create `studio-prototype/combat/bosses/BossVfxAssets.luau`.

- [ ] **Step 1: Write `Common.luau`.** It wraps `VfxKit` and adds these helpers:
  - `C.shake(pos, strength, seconds)`: local camera shake that honours the `Setting_ScreenShake` player attribute (same as `RogueliteCombat.client.luau` lines 274–293), scaled by `1 - dist/60`.
  - `C.decal(pos, textureId, size, color, fadeIn, hold, fadeOut, rotation)`: a flat 0.05-thick anchored part with a top-face `Decal`, animated by transparency.
  - `C.emitter(host, props)`: builds a `ParticleEmitter` from a props table, including flipbook layout and `Emit(count)`.
  - `C.mesh(name, cf, scale)`: clones a `BossVfxAssets` template.
  - `C.grow(part, fromScale, toScale, seconds, ease)`: animates `Size` with the given easing.
  - `C.sound(id, pos, volume, pitch)`: a positional Sound in `RogueliteSFX`, cleaned up after it ends.
  - `C.light(pos, color, range, brightness, seconds)`, which forwards to `VfxKit.flash`.
- [ ] **Step 2: Upload the textures.** Upload every PNG listed in `boss-vfx-kit/manifest.json` with the Studio MCP `upload_image`. Write `BossVfxAssets.luau`, which returns `{Textures = {[name] = 'rbxassetid://…'}, Flipbook = {[name] = '4x4'}}`. Add an `ASSETS.md` section "Boss VFX kit — 2026-09-29" listing every id and its source PNG. They are all authored in `boss-vfx-kit/`, with no Creator Store assets.
- [ ] **Step 3: Search and insert the sounds.** Use `search_asset` for each cue below, audition it with a short Edit-mode `Sound:Play()` check that it loads (`IsLoaded`), and record the id in `BossVfxAssets.Sounds` and `ASSETS.md`:
  - `crab_slam` (heavy sand thud), `crab_scuttle` (fast clicking), `bubbles` (bubble stream)
  - `pharaoh_charge` (magic hum), `pharaoh_bolt` (arcane whoosh), `stone_rumble`, `sand_burst`
  - `ice_slam` (heavy ice impact), `ice_crack`, `ice_wave` (rolling ice eruption)
  - `dragon_inhale`, `fire_breath`, `tail_whoosh`, `ground_quake`, `lava_hiss`
  - one windup cue per boss (`*_windup`)
- [ ] **Step 4: Commit.**

### Tasks 11–14: One effects module per boss

**Files:** Create `studio-prototype/combat/bosses/BossVfx/{KingCrab,Pharaoh,FrostCyclops,Dragon}.luau`. Each exports `windup(ctx)`, `impact(ctx)`, `active(ctx, age)` and (where used) `projectile(ctx, i)`.

Each task follows the same steps:
- [ ] **Step 1:** Write the module to the timeline below.
- [ ] **Step 2:** Sync it. In a Client Play check, force every attack twice and assert that no error is logged. Assert that `workspace` has no leftover effect parts 3 seconds after `recoveryEnd`, by counting parts named `BossVfx*` under the effects parent. Expected: `PASS`.
- [ ] **Step 3:** Take one plain `screen_capture` at each attack's impact. Send them to the user for review; the user judges the look.
- [ ] **Step 4:** Commit.

**Task 11: King Crab**
- **ClawCrush**
  - Windup: shell creaks (`crab_windup`), and small sand trickles off the claw (a SandSpray flipbook at the claw point, rate 20).
  - Impact at `ClawImpact`:
    - `ShockwaveRing` decal expanding from 1 to 14 studs over 0.45 s, coral-tinted.
    - A WaterSplash flipbook burst (22 particles, speed 18–28, cone 70° up).
    - SandSpray (30 particles).
    - Three `ShellChip` meshes flung, via `VfxKit.shards` using the mesh templates.
    - `C.shake(pos, 0.8, 0.35)`, the `crab_slam` sound and a 0.2 s `ImpactStar` flash.
- **SidewaysRush**
  - Windup: the lane warning, plus dust puffs at the feet.
  - Active: a SandSpray emitter at each foot group (rate 60 while moving), and a `crab_scuttle` loop (pitch 1.1).
  - Afterwards, a sand-furrow decal is laid along the lane and fades over 1.5 s.
  - Impact (the skid at RushEnd): a sand burst.
- **BubbleBarrage**
  - Windup: mouth foam (Bubble particles, rate 30, small).
  - Projectile: a translucent sphere (the `Bubble.png` decal on all faces, or a ball with Glass material, transparency 0.35) of radius 1.5 that wobbles its scale ±8% at 6 Hz, with a trailing mini-bubble emitter.
  - On stop: a pop with a WaterSplash burst of 10 and the `bubbles` pop sound.

**Task 12: Pharaoh**
- **CursedBolts**
  - Windup: in the crook hook (`BoltOrigin`), a cyan-gold `CurseOrb` sprite grows over 0.6 s, with a `PointLight` ramp, orbiting `Hieroglyphs` particles (rate 25, `RotSpeed`) and the `pharaoh_charge` sound.
  - Impact: a muzzle flash (`ImpactStar`, gold) and the `pharaoh_bolt` sound.
  - Projectile: a neon cyan core ball (0.9) inside a gold rim ball (1.4, transparency 0.6). It carries a `Trail` (cyan → gold, lifetime 0.35), a `Hieroglyphs` particle trail (rate 18, lifetime 0.8, drifting up) and a small `PointLight`.
  - On stop: a sand burst (`SandBurst` flipbook, 16 particles) plus a cyan pop.
- **TombEruption**
  - Windup, when the staff raises: gold dust spirals up the staff.
  - At each target: the `HieroglyphCircle` decal fades in and rotates slowly (20°/s), gold, lasting from `warnStart` to eruption. Its ring edge pulses in the final 0.3 s.
  - Impact (when the staff hits the ground): a gold ground-ring shockwave from `StaffImpact` (1 to 8 studs) and the `stone_rumble` sound.
  - Eruption at each target, at `impact + eruptDelay`:
    - An `Obelisk_A/B/C` mesh (random) grows up from underground over 0.18 s, overshoots 10%, holds 0.9 s, then sinks over 0.4 s.
    - A `SandBurst` geyser column (40 particles, speed 30–45 up, spread 12°).
    - Sandstone rubble shards, `sand_burst` sound and a small shake.

**Task 13: Frost Cyclops**
- **GroundSlam**
  - Windup: frost mist gathers on the club head (a FrostMist flipbook at the club, rate 30), plus the `ice_windup` cue and the ice-tinted circle warning.
  - Impact at `ClubImpact`:
    - `FrostRing` decal expanding 1 → 22 studs over 0.5 s, plus a second, slower ring.
    - A `FrostFloor` decal of 16 studs that fades over 3 s.
    - About eight `IceShard` meshes flung outward.
    - A snow burst (`SnowSparkle` + FrostMist, 40 particles, 360° spread).
    - `C.shake(pos, 1.3, 0.5)`, the `ice_slam` sound and a pale-blue flash.
- **Stomp → Ice Wave (Todoroki-style)**
  - Windup, during the slow leg raise: the frost path line warning, plus frost crystals creeping along the path (a `FrostFloor` decal strip that fades in progressively along its length) and the `ice_windup` cue.
  - Impact at `StompImpact`: a frost ring 1 → 7 studs, snow burst and shake 1.0.
  - Then the **wave**: `IceSpike` clusters spawn along the line, one every 2.2 studs.
    - Each cluster erupts at time `d / travel` after impact.
    - Size grows with distance: variant A near the foot, rising to E at the far end.
    - Each grows from 0.2 to 1.0 scale over 0.12 s with an 8% overshoot, with random yaw and a slight outward lean, and its own snow puff, `IceShard` debris and an `ice_crack` sound (throttled to one every 3 spikes).
    - The wall holds for 1.1 s, then each cluster shatters: it's replaced by 4 `IceShard` shards plus a mist puff, with a fading `FrostFloor` decal left behind.
    - One `ice_wave` sound plays for the whole run.

**Task 14: Dragon**
- **FireBreath**
  - Windup, during the inhale: the throat and jaw glow (the `LavaGlow` section brightens via its `Color` ramp), embers get sucked toward the mouth (`Ember` particles with negative speed), and the `dragon_inhale` sound plays.
  - Active: a flame cone emitter at `FireOrigin`, aimed by the per-sample direction.
    - `Flame` flipbook: rate 90, speed 26–34, spread 18°, size 2 → 7, lifetime 0.55–0.7, color orange-yellow → red.
    - Inner core: a second emitter, smaller and brighter yellow, `LightEmission` 1.
    - `Ember` sparks at rate 40 and `SmokePuff` at rate 15 along the cone's far end.
    - A `PointLight` of range 24 at the cone midpoint.
    - `ScorchMark` decals left every 0.25 s along the ground at the cone's far point, fading over 4 s.
    - A `fire_breath` loop sound.
- **TailWhip**
  - Windup, as he coils: a dust puff under his hind feet and the `dragon_windup` cue.
  - Active: an ember-tinted `Trail` on the spade (attachments at `SpadeTip` and `TailMid`, lifetime 0.25), dust kicks where the tip passes near the ground, and a crescent `VfxKit.ring` along the swept arc (inner 6 → outer 19).
  - Impact: the `tail_whoosh` sound and shake 0.7.
- **FrontStomp**
  - Windup, as he rears: a wing flap gust of dust, plus the `dragon_windup` roar.
  - Impact at `StompCenter`:
    - A `LavaCracks` decal of 20 studs that glows then cools over 3 s (Color from orange-yellow → dark red, then transparency out).
    - A ring of 6 `MoltenRock` meshes bursting up and falling.
    - An ember burst (60 particles), a `SmokePuff` ring and a flash.
    - The `ground_quake` and `lava_hiss` sounds, and shake 1.4.

---

## Phase 4 — Hand-over

### Task 15: Hand the bosses to the user

- [ ] **Step 1: Studio state.** Confirm Studio is in Edit, the Hammer boss is still spawnable, and there are no errors in `get_console_output` from the last check.
- [ ] **Step 2: Documentation.** Update `MAP_MOB_ROSTER.md` "Boss direction" with the final numbers. Add `studio-prototype/combat/bosses/README.md`, covering:
  - what's installed and where;
  - how to rebuild (the pipeline order: Blender package → import → receipt → `retarget_boss.py` → `build_boss_modules.py` → installer → sync);
  - what has been verified, and what hasn't: multi-client, published servers, balance.
- [ ] **Step 3: Commit and push**, staging only this plan's files.
- [ ] **Step 4: Hand over.** Tell the user what to try: Admin (P) → Mobs → pick each boss → Spawn, then watch each attack. Beach Cove wave 20 spawns the King Crab. The user does the play-testing.
