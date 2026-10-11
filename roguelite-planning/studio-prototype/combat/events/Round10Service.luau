-- Server only (unsandboxed, ServerScriptService): the round 10 event director (ROUND_10_MASTER_SPEC.md).
-- BossEncounter calls S.start at wave 10 in place of the old midboss when S.ready says this place has
-- every piece the map's event needs (Round10Defs needs); otherwise the midboss still comes.
--
-- Lifecycle, one event at a time, keyed by a generation (RogueliteRunState EventGen) that every
-- delayed spawn, hazard and callback checks, so nothing from one event reaches a later wave:
--   Intro    CinematicUntil holds players, enemies and spawning while each client plays the event's
--            own cinematic (Round10Events.client) from the anchors in workspace.Round10Event.
--   Active   this director owns the wave (EventSpawnHold): arrivals, coffins, vents, the leader's
--            event moves (MapBossService hooks), and the clear condition. BossAlive holds the wave open.
--   Complete latched once: arrivals stop, hazards and warnings end, remaining event arrivals are
--            removed (no kill rewards), the clear pays once, EVENT CLEARED shows, and the shop opens
--            Defs.CLEAR_HOLD seconds later (WaveEndsAt).
--   Abort    the wave or run ended some other way (all players down, leave, admin jump): everything
--            is removed and the attributes cleared. No success reward.
-- Survival events count their 60 s on the wave clock itself (WaveEndsAt from the end of the intro), so
-- ShopService's pause/resume (solo death, admin, the pause menu) pauses them exactly.
-- Practice and admin tools never award persistent progress here: rewards are the run's own crystals.
local Players=game:GetService('Players')
local Run=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local Http=game:GetService('HttpService')
local ServerStorage=game:GetService('ServerStorage')
local RS=game:GetService('ReplicatedStorage')
local combat=RS:WaitForChild('RogueliteCombat')
local Defs=require(combat:WaitForChild('Round10Defs'))
local Catalog=require(combat:WaitForChild('EnemyCatalog'))
local Rules=require(RS:WaitForChild('RunSetupRules'))
local Characters=require(script.Parent:WaitForChild('CharacterService'))
local S={}
local current -- the running event (E), or nil
local generation=0
local fx=combat:FindFirstChild('Round10FX') or Instance.new('RemoteEvent')
fx.Name='Round10FX';fx.Parent=combat

local function runState() return RS:FindFirstChild('RogueliteRunState') end
local function now() return workspace:GetServerTimeNow() end
local function flat(v) return Vector3.new(v.X,0,v.Z) end
local function module(parent,name)
 local m=parent and parent:FindFirstChild(name);if not m then return nil end
 local ok,v=pcall(require,m);if not ok then warn('Round10Service: '..name..' failed to load: '..tostring(v)) end
 return ok and v or nil
end
local function spawner() return ServerStorage:FindFirstChild('Round10Spawn') end
local function enemies() return workspace:FindFirstChild('RogueliteEnemies') end
-- Run members alive and up (not downed): the party size every number scales with (1-4).
local function members()
 local list={}
 for _,p in Players:GetPlayers() do
  local h=p.Character and p.Character:FindFirstChildOfClass('Humanoid');local r=p.Character and p.Character:FindFirstChild('HumanoidRootPart')
  if p:GetAttribute('RunMember') and not p:GetAttribute('RunDown') and h and h.Health>0 and r then table.insert(list,{player=p,root=r}) end
 end
 return list
end
local function centroid(list)
 if #list==0 then return nil end
 local sum=Vector3.zero;for _,e in list do sum+=e.root.Position end
 return sum/#list
end
local function paused()
 local run=runState()
 return combat:GetAttribute('RunPaused')==true or (run and (run:GetAttribute('AdminPaused')==true or run:GetAttribute('Paused')==true)) or false
end

-- What the map's event needs here (Round10Defs needs): true, or false and the first missing piece.
function S.ready(map)
 local def=Defs.forMap(map);if not def then return false,'no event for '..tostring(map) end
 if not spawner() then return false,'RogueliteZombieChase has no Round10Spawn (Studio behind the repo)' end
 local templates=ServerStorage:FindFirstChild('RogueliteNPCs')
 for _,name in def.needs.templates or {} do
  if not (templates and templates:FindFirstChild(name)) then return false,'missing template '..name end
 end
 local props=ServerStorage:FindFirstChild('Round10Props')
 for _,name in def.needs.props or {} do
  if not (props and props:FindFirstChild(name)) then return false,'missing prop '..name end
 end
 if def.needs.leader then
  local Defs2=module(combat,'MapBossDefs');local MB=module(script.Parent,'MapBossService')
  local ok,ready=pcall(function() return Defs2.ready(def.needs.leader) end)
  if not (ok and ready) then return false,'leader '..def.needs.leader..' not installed (MapBossDefs.ready)' end
  if not (MB and type(MB.hooks)=='table') then return false,'MapBossService without event hooks' end
 end
 return true
end
function S.active() return current end

-- Attributes every client reads (Round10Events.client, the HUD).
local function publish(E,key,value) local run=runState();if run and E.gen==generation then run:SetAttribute(key,value) end end
local function status(E)
 if not E.tombs then return end
 local list={}
 for i,t in E.tombs do
  local h=t.model and t.model:FindFirstChildOfClass('Humanoid')
  list[i]={letter=t.letter,health=h and math.max(0,math.ceil(h.Health)) or 0,max=h and h.MaxHealth or 1,alive=t.alive}
 end
 -- Wardens (2026-10-10: more than one in a party): alive counts the living plus any still to come.
 local alive,total=0,E.wardenCount or 1
 if E.wardens then for _,npc in E.wardens do local h=npc.Parent and npc:FindFirstChildOfClass('Humanoid');if h and h.Health>0 then alive+=1 end end;alive+=E.wardensPending or 0
 else alive=E.leaderAlive and 1 or 0 end
 publish(E,'EventStatus',Http:JSONEncode({tombs=list,leaderAlive=alive>0,leaderName=E.leaderName,wardens=alive,wardenTotal=total}))
end
-- Living (or still arriving) Tomb Wardens.
local function wardensAlive(E)
 if not E.wardens then return E.leaderAlive and 1 or 0 end
 local n=E.wardensPending or 0
 for _,npc in E.wardens do local h=npc.Parent and npc:FindFirstChildOfClass('Humanoid');if h and h.Health>0 and not npc:GetAttribute('DeathPopped') then n+=1 end end
 return n
end

-- Arrivals: the event's own pulses through Round10Spawn (red X telegraph, cancelled with the event).
local function eventAlive(E)
 local n=0
 for npc in E.adds do
  local h=npc.Parent and npc:FindFirstChildOfClass('Humanoid')
  if h and h.Health>0 then n+=1 else E.adds[npc]=nil end
 end
 return n
end
local function spawnOne(E,id,position,telegraph,attrs,source)
 local bind=spawner();if not bind then return nil end
 E.pending+=1
 local ok,npc=pcall(bind.Invoke,bind,'Spawn',{id=id,position=position,gen=E.gen,telegraph=telegraph,attrs=attrs,source=source})
 E.pending-=1
 if not ok then warn('Round10Service: spawn failed: '..tostring(npc));return nil end
 if npc and E.gen==generation and E.phase~='Done' then E.adds[npc]=true;return npc end
 return nil
end
local function ground(position)
 local bind=spawner();if not bind then return nil end
 local ok,p=pcall(bind.Invoke,bind,'Ground',position);return ok and p or nil
end
local function point(request)
 local bind=spawner();if not bind then return nil end
 local ok,p=pcall(bind.Invoke,bind,'Point',request);return ok and p or nil
end
-- A group of `count` ids around one approach point: the point (Round10Spawn Point near a living
-- member, `band` studs out), then the others on open floor around it.
local function group(E,ids,count,band,anchorRoot,telegraph,attrs)
 local anchor=anchorRoot and anchorRoot.Position or nil
 local base=point({anchor=anchor,band=band or {30,46},minimum=22});if not base then return 0 end
 local spawned=0
 for i=1,count do
  local a=i*2.39996;local r=i==1 and 0 or 2.5+math.sqrt(i)*1.6
  local at=i==1 and base or ground(base+Vector3.new(math.cos(a)*r,0,math.sin(a)*r)) or base
  local id=ids[(E.serial%#ids)+1];E.serial+=1
  task.spawn(spawnOne,E,id,at,telegraph or 1,attrs)
  spawned+=1
 end
 return spawned
end
-- One pulse when due: interval eases early -> late (Defs.interval) over 60 s, capped by Defs.cap.
local function pulse(E,t,spec,list,extra)
 if t<E.nextPulse then return false end
 local k=math.clamp((t-E.activeAt)/60,0,1)
 E.nextPulse=t+Defs.interval(spec,k)
 local n=#list;if n==0 then return false end
 local room=Defs.cap(spec,n)-eventAlive(E)-E.pending
 local count=math.min(Defs.pulseSize(spec,n)+(extra or 0),room)
 if count<=0 then return false end
 E.turn=(E.turn or 0)%n+1
 group(E,spec.fodder,count,{30,46},list[E.turn].root,1)
 return true
end

-- The leader: a MapBossDefs id spawned on MapBossService, its own intro clip timed to land at `land`
-- inside the event intro (BossIntroStyle 'event': no sky-drop camera; the event cinematic films it).
local function spawnLeader(E,cf,land)
 local MB=module(script.Parent,'MapBossService');local BossDefs=module(combat,'MapBossDefs')
 if not MB or not BossDefs then return nil end
 local ok,npc=pcall(MB.spawn,E.def.leader,cf,false,{intro=true,eventIntro={land=land,done=E.introUntil}})
 if not ok or not npc then warn('Round10Service: leader '..tostring(E.def.leader)..' failed to spawn: '..tostring(npc));return nil end
 local d=BossDefs.get(E.def.leader)
 E.leader,E.leaderAlive,E.leaderName=npc,true,d and d.name or E.def.leader
 npc:SetAttribute('EventLeader',true);npc:SetAttribute('EventGen',E.gen)
 -- A leader with event music dances on its beat (MapBossPresentation, def.idleBeats): the grid's
 -- anchor is the drop's first beat in server time.
 local music=E.def.music and Defs.Music and Defs.Music[E.def.music]
 if music and music.bpm then npc:SetAttribute('BeatAnchor',E.introStart+music.accentAtIntro);npc:SetAttribute('BeatPeriod',60/music.bpm) end
 local h=npc:FindFirstChildOfClass('Humanoid')
 if h then h.Died:Connect(function() if E.gen==generation then E.leaderAlive=false;status(E) end end) end
 npc.Destroying:Connect(function() if E.gen==generation then E.leaderAlive=false end end)
 -- Event moves at each attack's impact (MapBossService X hook): the DJ's Beat Command, the howl.
 MB.hooks[npc]=function(kind,A,t) if E.gen==generation and E.onLeader then E.onLeader(E,kind,A,t) end end
 return npc
end

-- The arena's centre and radius (Round10Spawn Arena: the map marker's spawn area).
local function arena()
 local bind=spawner();if not bind then return nil end
 local ok,c,r=pcall(bind.Invoke,bind,'Arena');if ok and typeof(c)=='Vector3' then return c,r or 60 end
 return nil
end
-- The open floor point on a ring around `center` at `radius` studs that is farthest from `from`
-- (a rim spot opposite the players), or the first that works.
local function rimPoint(center,radius,from,tries)
 local best,score
 for i=0,(tries or 16)-1 do
  local a=i/(tries or 16)*math.pi*2
  local p=ground(center+Vector3.new(math.cos(a)*radius,0,math.sin(a)*radius))
  if p then local s=from and flat(p-from).Magnitude or 0;if not best or s>score then best,score=p,s end end
 end
 return best
end

-- ── Per-event behaviour ─────────────────────────────────────────────────────────────────────────
local EVENTS={}

-- Pine Valley: POP GOES THE ZOMBIE. The map's zombies plus Bloaters; survive 60 s.
-- The intro's Bloater (2026-10-10 user: "the cinematic for pop goes the zombie [shows] nothing. spawn a
-- popping zombie or something and make it blow up"): a prop copy of the Bloater template for the
-- cinematic to film, never an enemy: anchored, no collisions or queries, untagged, no scripts, not
-- in RogueliteEnemies, so nothing targets, hurts or pays for it, and its burst deals no damage.
-- It stands walkFrom studs behind `spot` facing the players (PopFrom, PopTo: its start and end
-- pivots); every client walks, arms and pops it locally (Round10Intro). It goes just after the
-- burst, or with the anchor folder (cleanup) on an abort, whichever comes first.
local function introBloater(E,spot,players)
 local pop=E.def.introPop;local entry=Catalog.get(E.def.spawn.exploder)
 local npcs=ServerStorage:FindFirstChild('RogueliteNPCs');local source=npcs and npcs:FindFirstChild(entry and entry.template or 'BloaterZombie_NPC')
 if not pop or not source then return nil end
 local m=source:Clone();m.Name='IntroBloater'
 local all=m:GetDescendants();table.insert(all,m)
 for _,d in all do
  for _,tag in Tags:GetTags(d) do Tags:RemoveTag(d,tag) end
  if d:IsA('BaseScript') or d:IsA('ModuleScript') then d:Destroy()
  elseif d:IsA('BasePart') then d.Anchored=false;d.CanCollide=false;d.CanQuery=false;d.CanTouch=false end
 end
 local root=m:FindFirstChild('HumanoidRootPart') or m.PrimaryPart;if not root then m:Destroy();return nil end
 root.Anchored=true;m.PrimaryPart=root
 local h=m:FindFirstChildOfClass('Humanoid')
 if h then h.DisplayDistanceType=Enum.HumanoidDisplayDistanceType.None;h.HealthDisplayType=Enum.HumanoidHealthDisplayType.AlwaysOff;h.BreakJointsOnDeath=false end
 local back=flat(spot-players);back=back.Magnitude>.5 and back.Unit or Vector3.new(0,0,1)
 local function stand(at)
  -- Feet on the floor at `at`, facing the players.
  m:PivotTo(CFrame.lookAt(at,at-back))
  local box,size=m:GetBoundingBox();return m:GetPivot()+Vector3.yAxis*(at.Y-(box.Position.Y-size.Y/2))
 end
 local to=stand(spot);local start=ground(spot+back*pop.walkFrom) or spot+back*pop.walkFrom;local fromCf=stand(start)
 m:PivotTo(fromCf);m:SetAttribute('IntroProp',true);m:SetAttribute('PopFrom',fromCf);m:SetAttribute('PopTo',to)
 m.Parent=E.anchor
 for _,p in m:GetDescendants() do if p:IsA('BasePart') and p.AssemblyRootPart~=root then p.Anchored=true end end -- loose pieces never fall
 task.delay(math.max(0,E.introStart+pop.burstAt+.6-now()),function() if m.Parent then m:Destroy() end end)
 return m,back
end
EVENTS.PopGoesTheZombie={
 setup=function(E,list,center)
  -- The intro: the prop Bloater (introBloater) waddles out of a held crowd 30 studs off the players
  -- toward the arena centre and pops on camera; the crowd stands behind it, out of the burst.
  local from=centroid(list)
  local dir=flat(center-from);dir=dir.Magnitude>1 and dir.Unit or Vector3.new(0,0,-1)
  local spot=ground(from+dir*30) or point({anchor=from,band={28,34},minimum=22})
  if not spot then return false end
  E.anchor:SetAttribute('Focus',spot)
  local _,back=introBloater(E,spot,from);back=back or dir
  local crowd=spot+back*((E.def.introPop and E.def.introPop.walkFrom or 9)+7)
  for i=1,7 do
   local a=i*.9;local r=4+i*.6
   local p=ground(crowd+Vector3.new(math.cos(a)*r,0,math.sin(a)*r))
   if p then task.spawn(spawnOne,E,E.def.spawn.fodder[(i%3)+1],p,0) end
  end
  return true
 end,
 step=function(E,t,list)
  local spec=E.def.spawn
  local exploders=0;for npc in E.adds do if npc.Parent and npc:GetAttribute('Exploder') and not npc:GetAttribute('Detonated') then exploders+=1 end end
  local exploderCap=spec.exploderCap[1]+spec.exploderCap[2]*math.max(0,#list-1)
  -- The first Bloater after the intro arrives alone and clearly (firstExploder s in).
  if not E.firstExploder and t>=E.activeAt+spec.firstExploder then
   E.firstExploder=true;group(E,{spec.exploder},1,{26,34},list[1] and list[1].root,1.2)
  end
  if pulse(E,t,spec,list) then
   E.pulses=(E.pulses or 0)+1
   if E.pulses%spec.exploderEvery==0 and exploders<exploderCap then
    local n=math.min(spec.exploderPerPlayer*#list,exploderCap-exploders)
    for i=1,n do group(E,{spec.exploder},1,{28,42},list[(i-1)%#list+1].root,1.2) end
   end
  end
 end,
}

-- Beach Cove: CRAB RAVE. The DJ Crab with crab reinforcements; defeat the DJ.
EVENTS.CrabRave={
 setup=function(E,list,center)
  local from=centroid(list)
  local dir=flat(center-from);dir=dir.Magnitude>1 and dir.Unit or Vector3.new(0,0,-1)
  local spot=ground(from+dir*36) or ground(center) or point({anchor=from,band={30,40},minimum=24})
  if not spot then return false end
  local BossDefs=module(combat,'MapBossDefs');local T=BossDefs and BossDefs.timing(E.def.leader)
  local cf=CFrame.lookAt(spot+Vector3.yAxis*((T and T.rootHeight or 2)+.1),Vector3.new(from.X,spot.Y+((T and T.rootHeight) or 2)+.1,from.Z))
  -- The claw snap lands on the intro's accent: 2.0 s in (Round10Events.client times the camera to it).
  local npc=spawnLeader(E,cf,E.introStart+2.0);if not npc then return false end
  E.anchor:SetAttribute('Focus',spot);E.anchor:SetAttribute('FocusFrame',cf)
  local v=Instance.new('ObjectValue');v.Name='Leader';v.Value=npc;v.Parent=E.anchor
  -- Reinforcements gather round it for the reveal.
  for i=1,6 do
   local a=i/6*math.pi*2;local p=ground(spot+Vector3.new(math.cos(a),0,math.sin(a))*9)
   if p then task.spawn(spawnOne,E,E.def.spawn.fodder[(i%#E.def.spawn.fodder)+1],p,0) end
  end
  return true
 end,
 step=function(E,t,list) pulse(E,t,E.def.spawn,list);EVENTS.CrabRave.stepRushes(E,t,list) end,
 -- Beat Command (MapBossService hook at its impact): up to count + perPlayer x players crab adds near
 -- the DJ lock a lane at their nearest player and, after `warn` s, rush straight down it.
 leader=function(E,kind,A,t)
  if kind~='BeatCommand' or E.phase~='Active' then return end
  local spec=E.def.rush;local list=members();if #list==0 then return end
  local leaderRoot=E.leader and E.leader.PrimaryPart;if not leaderRoot then return end
  local picks={}
  for npc in E.adds do
   local r=npc.Parent and npc:FindFirstChild('HumanoidRootPart');local h=npc:FindFirstChildOfClass('Humanoid')
   if r and h and h.Health>0 and not npc:GetAttribute('EventControlled') and (npc:GetAttribute('EnemyId')=='crab' or npc:GetAttribute('EnemyId')=='hermit-crab') and (r.Position-leaderRoot.Position).Magnitude<=spec.range then table.insert(picks,npc) end
  end
  table.sort(picks,function(a,b) return (a.HumanoidRootPart.Position-leaderRoot.Position).Magnitude<(b.HumanoidRootPart.Position-leaderRoot.Position).Magnitude end)
  local count=math.min(#picks,spec.count+spec.perPlayer*#list)
  E.rushes=E.rushes or {}
  for i=1,count do
   local npc=picks[i];local r=npc.HumanoidRootPart
   local target,best=nil,math.huge
   for _,e in list do local d=flat(e.root.Position-r.Position).Magnitude;if d<best then target,best=e,d end end
   local dir=target and flat(target.root.Position-r.Position) or flat(r.CFrame.LookVector)
   dir=dir.Magnitude>.1 and dir.Unit or Vector3.new(0,0,-1)
   local from=Vector3.new(r.Position.X,r.Position.Y,r.Position.Z)
   local skip={enemies()};for _,p in Players:GetPlayers() do if p.Character then table.insert(skip,p.Character) end end
   local wall=workspace:Raycast(from,dir*spec.length,(function() local p=RaycastParams.new();p.FilterType=Enum.RaycastFilterType.Exclude;p.FilterDescendantsInstances=skip;return p end)())
   local length=wall and math.max(0,wall.Distance-2) or spec.length
   npc:SetAttribute('EventControlled',true);npc:SetAttribute('RushFrom',from);npc:SetAttribute('RushDir',dir);npc:SetAttribute('RushSpeed',spec.speed)
   npc:SetAttribute('RushLength',length);npc:SetAttribute('RushWidth',spec.width);npc:SetAttribute('RushAt',t+spec.warn)
   local h=npc:FindFirstChildOfClass('Humanoid');if h then h:Move(Vector3.zero);h:MoveTo(r.Position) end
   -- Held still on its lane start from the order on (2026-10-10), so the lane drawn starts under it.
   r.Anchored=true;r.CFrame=CFrame.lookAt(from,from+dir)
   table.insert(E.rushes,{npc=npc,from=from,dir=dir,length=length,at=t+spec.warn,hits={}})
  end
 end,
 -- 2026-10-10 user: "the crabs that he makes dash outwards are like laggy and not smooth". Cause: the
 -- dash was CFrame steps on an anchored root from the 10 Hz director step (4 studs a step at speed
 -- 40), and an anchored part's CFrame replicates as a plain property set with no interpolation, so
 -- every client saw the crab jump ten times a second. Now the dash is a timeline on the server clock
 -- (RushFrom, RushDir, RushLength, RushSpeed, RushAt): each client draws the crab on it every frame
 -- (Round10World stepRush), the server puts its body on the same timeline every Heartbeat
 -- (moveRushes, so player hits on it agree) and the hit test sweeps the stretch covered since the
 -- last check, against where each player's screen has them (Characters.seen).
 moveRushes=function(E,t)
  local speed=E.def.rush.speed
  for _,R in E.rushes or {} do
   local r=R.npc.Parent and R.npc:FindFirstChild('HumanoidRootPart')
   if r and t>=R.at then local p=R.from+R.dir*math.min(R.length,(t-R.at)*speed);r.CFrame=CFrame.lookAt(p,p+R.dir) end
  end
 end,
 stepRushes=function(E,t,list)
  local spec=E.def.rush
  for i=#(E.rushes or {}),1,-1 do
   local R=E.rushes[i];local npc=R.npc;local r=npc.Parent and npc:FindFirstChild('HumanoidRootPart')
   local h=npc.Parent and npc:FindFirstChildOfClass('Humanoid')
   local over=not r or not h or h.Health<=0
   if not over and t>=R.at then
    local travel=math.min(R.length,(t-R.at)*spec.speed)
    -- The crab's body since the last check: 1.5 studs behind its root to 1.2 ahead.
    local lo,hi=(R.swept or 0)-1.5,travel+1.2;R.swept=travel
    for _,e in list do
     local at=Characters.seen(e.player,e.root) or e.root.Position
     local rel=flat(at-R.from);local along=rel:Dot(R.dir)
     if not R.hits[e.player] and along>=lo and along<=hi and (rel-R.dir*along).Magnitude<=spec.width/2+.8 and math.abs(at.Y-R.from.Y)<=5 then
      R.hits[e.player]=true;Characters.contact(e.player,spec.damage*(E.damageScale or 1),nil,npc)
     end
    end
    over=travel>=R.length
   end
   if over then
    if r then
     if h and h.Health>0 then local p=R.from+R.dir*R.length;r.CFrame=CFrame.lookAt(p,p+R.dir) end -- the lane's end, where clients drew it
     r.Anchored=false;pcall(r.SetNetworkOwner,r,nil)
    end
    if npc.Parent then npc:SetAttribute('EventControlled',nil);npc:SetAttribute('RushAt',nil) end
    table.remove(E.rushes,i)
   end
  end
 end,
 cleanup=function(E)
  for _,R in E.rushes or {} do local r=R.npc.Parent and R.npc:FindFirstChild('HumanoidRootPart');if r then r.Anchored=false end end
  E.rushes=nil
 end,
}

-- Desert Basin: THE TOMB OPENS. Three coffins are the only spawn sources; one releases the Tomb
-- Warden once. Destroy all three AND defeat the Warden.
local LETTERS={'A','B','C','D'}
-- 2026-10-10: the fallen lid's resting frame on the sand under it. open: its swung frame; half: its
-- vertical half-height there; floorY: the coffin's ground height (the fallback). 3 x 3 ground samples
-- across the lid's footprint fit a plane (slope clamped to MAX_TILT); its flat back rises LID_PROUD
-- above the highest sample (at most LID_SPIKE, so one bump never floats it).
local LID_PROUD,MAX_TILT,LID_SPIKE=.1,.25,.6
local function lidBed(open,size,half,floorY)
 local axes={{open.RightVector,size.X},{open.UpVector,size.Y},{open.LookVector,size.Z}}
 table.sort(axes,function(a,b) return math.abs(a[1].Y)<math.abs(b[1].Y) end)
 local U,hu=flat(axes[1][1]),axes[1][2]*.45;local V,hv=flat(axes[2][1]),axes[2][2]*.45
 U=U.Magnitude>.1 and U.Unit or Vector3.xAxis;V=V.Magnitude>.1 and V.Unit or Vector3.zAxis
 local c=Vector3.new(open.X,floorY,open.Z)
 local samples={}
 for _,a in {-1,0,1} do for _,b in {-1,0,1} do
  local p=ground(c+U*a*hu+V*b*hv);if p then table.insert(samples,{u=a*hu,v=b*hv,y=p.Y}) end
 end end
 local my,mu,mv,gu,gv=floorY,0,0,0,0
 if #samples>=4 then
  my=0;for _,s in samples do my+=s.y;mu+=s.u;mv+=s.v end;my/=#samples;mu/=#samples;mv/=#samples
  local su,sv,uu,vv=0,0,0,0
  for _,s in samples do su+=(s.u-mu)*(s.y-my);sv+=(s.v-mv)*(s.y-my);uu+=(s.u-mu)^2;vv+=(s.v-mv)^2 end
  gu=uu>0 and math.clamp(su/uu,-MAX_TILT,MAX_TILT) or 0;gv=vv>0 and math.clamp(sv/vv,-MAX_TILT,MAX_TILT) or 0
 end
 local function plane(u,v) return my+gu*(u-mu)+gv*(v-mv) end
 local over=0;for _,s in samples do over=math.max(over,s.y-plane(s.u,s.v)) end
 local top=plane(0,0)+math.min(over,LID_SPIKE)+LID_PROUD
 local n=(Vector3.yAxis-U*gu-V*gv).Unit;local axis=Vector3.yAxis:Cross(n)
 local tilt=axis.Magnitude>1e-4 and CFrame.fromAxisAngle(axis.Unit,math.asin(math.min(1,axis.Magnitude))) or CFrame.identity
 return CFrame.new(open.X,top-half,open.Z)*tilt*open.Rotation
end
-- 2026-10-10: the coffin's floor height on uneven sand: the lowest of its centre and footprint corners
-- (at most BODY_SINK below the centre), so no corner hangs over a dip; a little sand covers the base.
local BODY_SINK=.35
local function bodyFloor(cf)
 local y=cf.Y
 for _,o in {{-3.8,-3},{3.8,-3},{-3.8,3},{3.8,3}} do local p=ground((cf*CFrame.new(o[1],0,o[2])).Position);if p then y=math.min(y,p.Y) end end
 return math.max(y,cf.Y-BODY_SINK)-.05
end
-- 2026-10-10 user: "you can stand on top of the coffins ... mobs can't hit you up there". Each tomb
-- gets an invisible pillar over the stone's footprint, NO_CLIMB_HEIGHT studs up from its base, in
-- the place's player-only group (ArenaHeightBarrier, the arenas' PlayerHeightBarrier ceiling: players
-- collide with it; the ground, mobs and the Warden never do). Players bump into the coffin where they
-- did and can't land on it or in its cavity; the Warden's Emerge and the skeletons' exits are
-- unchanged (they never touch the group). Unqueryable: shots, hits, the camera and ground checks
-- pass through. Example: the 8.3 x 6.6 stone gets an 8.3 x 40 x 6.6 pillar, gone when the tomb falls.
local NO_CLIMB_GROUP,NO_CLIMB_HEIGHT='ArenaHeightBarrier',40
local function playerOnlyGroup()
 local Physics=game:GetService('PhysicsService')
 if not Physics:IsCollisionGroupRegistered(NO_CLIMB_GROUP) then
  -- A place without the barrier's group: make it (players only). Never fall back to Default, which
  -- would fill tomb A's cavity for the Warden too.
  local ok=pcall(function()
   Physics:RegisterCollisionGroup(NO_CLIMB_GROUP)
   for _,g in {'Default','RogueliteZombies',NO_CLIMB_GROUP} do if Physics:IsCollisionGroupRegistered(g) then Physics:CollisionGroupSetCollidable(NO_CLIMB_GROUP,g,false) end end
  end)
  if not ok then return nil end
 end
 return NO_CLIMB_GROUP
end
local function noClimb(E,model,cf)
 local body=model:FindFirstChild('Sarcophagus_Body',true);local group=playerOnlyGroup()
 if not body or not group or not E.anchor then return nil end
 local folder=E.anchor:FindFirstChild('NoClimb')
 if not folder then folder=Instance.new('Folder');folder.Name='NoClimb';folder.Parent=E.anchor end
 -- The body's box in the tomb's (yaw-only) frame: its footprint, base at cf.
 local rel=cf:ToObjectSpace(body.CFrame);local s=body.Size
 local hx=math.abs(rel.RightVector.X)*s.X/2+math.abs(rel.UpVector.X)*s.Y/2+math.abs(rel.LookVector.X)*s.Z/2
 local hz=math.abs(rel.RightVector.Z)*s.X/2+math.abs(rel.UpVector.Z)*s.Y/2+math.abs(rel.LookVector.Z)*s.Z/2
 local p=Instance.new('Part');p.Name='NoClimb_'..model.Name
 p.Size=Vector3.new(hx*2,NO_CLIMB_HEIGHT,hz*2);p.CFrame=cf*CFrame.new(rel.X,NO_CLIMB_HEIGHT/2,rel.Z)
 p.Anchored=true;p.CanCollide=true;p.CanQuery=false;p.CanTouch=false;p.CastShadow=false;p.Transparency=1
 p.CollisionGroup=group;p.Parent=folder
 return p
end
local function buildTomb(E,index,cf,health)
 local props=ServerStorage:FindFirstChild('Round10Props');local source=props and props:FindFirstChild('Sarcophagus')
 if not source then return nil end
 local model=source:Clone();model.Name='Tomb_'..LETTERS[index]
 -- The prop's pivot is its cavity floor centre, open face along -Z (its LookVector). cf stays the
 -- centre's ground (the Warden's emerge and the exits); the stone sits at bodyFloor (2026-10-10).
 -- Tomb A keeps its stone at ground0: the Warden spawns at ground0 + rootHeight and his Emerge clip starts
 -- with his soles on the cavity floor, so a dropped stone left him hovering up to .35 for ~1 s (2026-10-10).
 local ground0=cf.Y;if index~=1 then cf=cf-Vector3.yAxis*(cf.Y-bodyFloor(cf)) end
 model:PivotTo(cf)
 local size=model:GetExtentsSize()
 local root=Instance.new('Part');root.Name='HumanoidRootPart';root.Transparency=1;root.Anchored=true
 root.CanCollide=false;root.CanQuery=true;root.CanTouch=false;root.Size=Vector3.new(math.max(2,size.X*.8),math.max(2,size.Y*.9),math.max(2,size.Z*.7))
 root.CFrame=cf*CFrame.new(0,size.Y/2,0);root.Parent=model;model.PrimaryPart=root
 for _,p in model:GetDescendants() do
  if p:IsA('BasePart') then p.Anchored=true;p.CanTouch=false;p.CanQuery=true;p.CastShadow=true
   -- The lid lies open on the ground in front (players and arrivals walk over it); the body is solid.
   p.CanCollide=p.Name~='Sarcophagus_Lid' and p~=root and p.Name:find('Lid')==nil
  end
 end
 local lid=model:FindFirstChild('Sarcophagus_Lid',true)
 if lid then
  -- Closed on its hinge in the prop; open = rotated 90 degrees forward about the hinge line at the foot
  -- of the opening (the lid's own pivot, InstallRound10Props). Clients swing it during the intro.
  local hinge=lid:GetAttribute('Hinge')
  local hingeCf=typeof(hinge)=='CFrame' and cf*hinge or lid.CFrame
  local open=hingeCf*CFrame.Angles(-math.rad(90),0,0)*hingeCf:ToObjectSpace(lid.CFrame)
  lid:SetAttribute('ClosedFrame',lid.CFrame);lid:SetAttribute('HingeFrame',hingeCf)
  -- The fallen lid (relief face down, flat back up) sinks into the sand, so the Warden steps out over
  -- tomb A's and players cross it without a ledge. SinkDepth: how far below the swung frame.
  -- 2026-10-10 user: the openings were "glitching in the floor after they open". Its flat back sat
  -- exactly at the coffin centre's ground height: coplanar with the sand (z-fighting), and on the
  -- dunes' slope part of it was buried and part stood out. Now the ground under the whole lid is
  -- sampled (lidBed): the lid tilts to the sand's slope and its back sits LID_PROUD above the highest
  -- sample, so the sand never pokes through and never shares its plane. OpenFrame: that final frame
  -- (Round10Intro settles the swung lid onto it).
  local half=(math.abs(open.RightVector.Y)*lid.Size.X+math.abs(open.UpVector.Y)*lid.Size.Y+math.abs(open.LookVector.Y)*lid.Size.Z)/2
  local bed=lidBed(open,lid.Size,half,ground0)
  lid:SetAttribute('SinkDepth',math.max(0,open.Y-bed.Y));lid:SetAttribute('OpenFrame',bed);lid.CFrame=bed
 end
 local h=Instance.new('Humanoid');h.EvaluateStateMachine=false;h.RequiresNeck=false;h.BreakJointsOnDeath=false
 h.DisplayDistanceType=Enum.HumanoidDisplayDistanceType.None;h.MaxHealth=health;h.Health=health;h.Parent=model
 for key,value in {EventObjective='Tomb',TombLetter=LETTERS[index],IsElite=true,ZombieType='Tomb',EnemyId='',ContactDamage=0,ContactRange=0,BumpDamage=0,BumpRange=0,EventGen=E.gen,CrowdRadius=3.5} do model:SetAttribute(key,value) end
 model:SetAttribute('EnemyId',nil)
 model.Parent=enemies()
 Tags:AddTag(model,'RogueliteZombie');Tags:AddTag(model,'Round10Tomb')
 -- MobCollision puts tagged bodies in the walk-through group; a coffin stays solid stone.
 task.defer(function() for _,p in model:GetDescendants() do if p:IsA('BasePart') and p.CanCollide then p.CollisionGroup='Default' end end end)
 return model,noClimb(E,model,cf)
end
local function breakTomb(E,t,position,cf)
 local props=ServerStorage:FindFirstChild('Round10Props');local kit=props and props:FindFirstChild('SarcophagusBroken')
 fx:FireAllClients('TombBroken',position,t)
 if not kit then return end
 local pieces=kit:Clone();pieces.Name='TombRuins';pieces:PivotTo(cf)
 for _,p in pieces:GetDescendants() do if p:IsA('BasePart') then p.Anchored=true;p.CanCollide=false;p.CanQuery=false;p.CanTouch=false end end
 pieces.Parent=E.anchor
end
-- 2026-10-10 user: in multiplayer "multiple wardens come out". Wardens after the first (Defs.wardens)
-- burst out in front of tombs B / C as the fight starts: never from inside (only tomb A's cavity
-- is staged for his Emerge clip), so no intro clip; a sand burst at the mouth covers the arrival.
-- They count for the clear and the HUD like the first. BossPractice: the extra Wardens pay no boss
-- crystal shower or "defeat a boss" quest credit (ZombieDeath skips their death listeners), so a
-- party's wave 10 pays exactly what one Warden did.
local function wardenSpot(E,T)
 local BossDefs=module(combat,'MapBossDefs');local d=BossDefs and BossDefs.get(E.def.leader)
 local out=T.cf*CFrame.new(0,0,-(((d and d.emergeOut) or 3.5)+1.2))
 return ground(out.Position) or out.Position
end
local function extraWarden(E,T,health)
 local MB=module(script.Parent,'MapBossService');local BossDefs=module(combat,'MapBossDefs')
 local timing=BossDefs and BossDefs.timing(E.def.leader)
 if not MB or not BossDefs then return nil end
 local floor=wardenSpot(E,T)
 local y=floor.Y+((timing and timing.rootHeight) or 3)+.1
 local face=flat(E.center-floor).Magnitude>1 and Vector3.new(E.center.X,y,E.center.Z) or Vector3.new(floor.X,y,floor.Z)+T.cf.LookVector
 local ok,npc=pcall(MB.spawn,E.def.leader,CFrame.lookAt(Vector3.new(floor.X,y,floor.Z),face),false,nil)
 if not ok or not npc then warn('Round10Service: extra Warden failed to spawn: '..tostring(npc));return nil end
 npc:SetAttribute('BossPractice',true);npc:SetAttribute('EventLeader',true);npc:SetAttribute('EventGen',E.gen);npc:SetAttribute('FromTomb',T.letter)
 local h=npc:FindFirstChildOfClass('Humanoid')
 -- (The health cut reads as a hit to MapBossService; clear its flinch.)
 if h then h.MaxHealth=health;h.Health=health;npc:SetAttribute('BossHitStart',nil);h.Died:Connect(function() if E.gen==generation then status(E) end end) end
 return npc
end
EVENTS.TombOpens={
 setup=function(E,list,center)
  local spec=E.def.tombs;local from=centroid(list)
  local away=flat(center-from);away=away.Magnitude>1 and away.Unit or Vector3.new(0,0,-1)
  -- 2026-10-10 user: "they need to be spread apart". A ring at spec.ring of the arena radius (clamped,
  -- and 9 studs inside the edge for the coffin's back), every pair at least minGap apart: with three
  -- tombs on a 36-stud ring they stand 62 studs apart (was 47 on 27, with only 16 enforced).
  local arenaR=E.arenaRadius or 60
  local radius=math.min(math.clamp(arenaR*spec.ring,spec.ringClamp[1],spec.ringClamp[2]),arenaR-9)
  local hpScale,damageScale=Rules.bossScale(combat:GetAttribute('RunDifficulty'),math.max(1,#list),combat:GetAttribute('RunMap'))
  E.tombs={};E.damageScale=damageScale
  local placed={}
  -- Three spots spread round the arena centre, the first on the far side from the players. Each spot
  -- also wants open floor behind the coffin and where its lid falls; a crowded arena relaxes minGap.
  local function pick(base,gap,strict)
   for _,dr in {0,-4,4,-8,-12} do
    for _,jitter in {0,.2,-.2,.4,-.4} do
     local a=base+jitter;local dir=Vector3.new(math.cos(a),0,math.sin(a))
     local spot=ground(center+dir*(radius+dr))
     if spot then for _,o in placed do if flat(o-spot).Magnitude<gap then spot=nil;break end end end
     if spot and strict and not (ground(spot+dir*3.5) and ground(spot-dir*12)) then spot=nil end
     if spot then return spot end
    end
   end
   return nil
  end
  for i=1,spec.count do
   local base=math.atan2(away.Z,away.X)+(i-1)*math.pi*2/spec.count
   local spot=pick(base,spec.minGap,true) or pick(base,spec.minGap,false) or pick(base,spec.minGap*.6,false) or pick(base,16,false)
   if spot then
    table.insert(placed,spot)
    local cf=CFrame.lookAt(spot,Vector3.new(center.X,spot.Y,center.Z))
    local model,pillar=buildTomb(E,i,cf,math.ceil(spec.health*hpScale))
    if model then
     local T={model=model,letter=LETTERS[i],alive=true,cf=cf,exit=cf*CFrame.new(0,0,-4.2),index=i,nextPulse=0,bursts=0,noClimb=pillar}
     table.insert(E.tombs,T)
     local v=Instance.new('ObjectValue');v.Name='Tomb'..LETTERS[i];v.Value=model;v.Parent=E.anchor
     local h=model:FindFirstChildOfClass('Humanoid')
     -- Down once, however it goes (2026-10-10: the wave never ended after the tombs fell). The
     -- tomb's Humanoid runs no state machine, so Died need not fire, and a lethal hit has
     -- ZombieDeath destroy the model at once: health 0, the model leaving, or the step's check
     -- (tombGone) each count, and the ruins still go down where it stood.
     T.down=function()
      if E.gen~=generation or not T.alive then return end
      T.alive=false;if model.Parent then model:SetAttribute('BurstAt',nil) end;breakTomb(E,now(),cf.Position,cf);status(E)
      if T.noClimb then T.noClimb:Destroy();T.noClimb=nil end -- the ruins don't collide: nothing left to climb
     end
     h.Died:Connect(T.down)
     h.HealthChanged:Connect(function(hp) if E.gen==generation then E.statusDirty=true;if hp<=0 then T.down() end end end)
     model.Destroying:Connect(T.down)
    end
   end
  end
  if #E.tombs<spec.count then return false end
  -- The Warden steps out of tomb A (Emerge: from the cavity centre to emergeOut studs in front).
  local A=E.tombs[1]
  local BossDefs=module(combat,'MapBossDefs');local T=BossDefs and BossDefs.timing(E.def.leader)
  local leaderDef=BossDefs and BossDefs.get(E.def.leader)
  local out=A.cf*CFrame.new(0,0,-((leaderDef and leaderDef.emergeOut) or 3.5))
  local cf=CFrame.lookAt(out.Position+Vector3.yAxis*((T and T.rootHeight or 3)+.1),out.Position+Vector3.yAxis*((T and T.rootHeight or 3)+.1)+A.cf.LookVector)
  -- Emerge: coffins rise (0-1.5 s), lid A falls (1.6 s), the Warden plants his fists at 3.7 s.
  local npc=spawnLeader(E,cf,E.introStart+3.7);if not npc then return false end
  local v=Instance.new('ObjectValue');v.Name='Leader';v.Value=npc;v.Parent=E.anchor
  -- More Wardens for a party (Defs.wardens): the party's boss health split between them.
  E.wardenCount=math.min(Defs.wardens(spec,#list),#E.tombs);E.wardens={npc}
  local h=npc:FindFirstChildOfClass('Humanoid')
  E.wardenHealth=h and Defs.wardenHealth(h.MaxHealth,E.wardenCount) or nil
  if h and E.wardenCount>1 then h.MaxHealth=E.wardenHealth;h.Health=E.wardenHealth;npc:SetAttribute('BossHitStart',nil) end
  E.wardensPending=E.wardenCount-1
  E.anchor:SetAttribute('Focus',A.cf.Position);E.anchor:SetAttribute('FocusFrame',A.cf)
  status(E)
  return true
 end,
 step=function(E,t,list)
  local spec=E.def.tombs;local burst=spec.burst
  -- The extra Wardens arrive as the fight starts: the spot bursts (TombWardenBurst), then he is out.
  if (E.wardensPending or 0)>0 and not E.wardensCalled then
   E.wardensCalled=true
   for i=2,E.wardenCount do
    local T=E.tombs[i]
    fx:FireAllClients('TombWardenBurst',wardenSpot(E,T),T.cf.LookVector)
    task.delay(.45,function()
     -- The pending slot is released whatever happens, so a failed or cancelled arrival can't
     -- hold the clear (wardensAlive counts pending Wardens).
     E.wardensPending=math.max(0,(E.wardensPending or 1)-1)
     if E.gen~=generation or E.phase~='Active' then return end
     local ok,npc=pcall(extraWarden,E,T,E.wardenHealth or 6000)
     if not ok then warn('Round10Service: extra Warden failed: '..tostring(npc));npc=nil end
     if npc then
      table.insert(E.wardens,npc)
      local v=Instance.new('ObjectValue');v.Name='Leader'..i;v.Value=npc;v.Parent=E.anchor
     end
     status(E)
    end)
   end
  end
  if E.statusDirty then E.statusDirty=false;status(E) end
  -- 2026-10-10 user: tomb spawning "feels like just another normal round ... it needs to feel more
  -- intense ... something that the tombs do where you wanna destroy them". Each standing tomb now
  -- bursts: BurstAt (its glow, shake and dust on every client, Round10World) `warn` s ahead, then a
  -- stream of skeletons pours out of its mouth `pour` s apart, no red X (the tomb's own pulse is the
  -- warning). Bursts grow and quicken while it stands (Defs.burstSize, Defs.burstInterval); its death
  -- cancels the rest of the pour. Example, solo: every tomb throws 3 every 4.2 s at first, then up to
  -- 6 every 2.6 s; the event's cap (30 solo, +10 a player) holds the crowd.
  local alive=eventAlive(E)+E.pending;local cap=Defs.cap(spec,#list)
  for _,T in E.tombs do
   if T.alive then
    if T.nextPulse==0 then T.nextPulse=E.activeAt+.8+(T.index-1)*burst.stagger end
    -- A pause moved the burst (the Heartbeat shifts nextPulse): the clients' warning follows it.
    if T.warned and T.model:GetAttribute('BurstAt')~=T.nextPulse then T.model:SetAttribute('BurstAt',T.nextPulse) end
    if not T.warned and t>=T.nextPulse-burst.warn then
     if cap-alive<=0 then T.nextPulse=t+burst.warn+1 -- full: try again a second later, no pulse
     else T.warned=true;T.model:SetAttribute('BurstCount',T.bursts+1);T.model:SetAttribute('BurstAt',T.nextPulse) end
    elseif T.warned and t>=T.nextPulse then
     T.warned=false
     local n=math.max(0,math.min(Defs.burstSize(burst,#list,T.bursts),cap-alive))
     T.bursts+=1;T.nextPulse=t+Defs.burstInterval(burst,T.bursts)
     E.pending+=n;alive+=n
     local lanes={}
     for i=1,n do
      local id=spec.fodder[(E.serial%#spec.fodder)+1];E.serial+=1
      -- Out of the mouth in a fan of three, rows further out; never on top of a player.
      local row=(i-1)//3;local col=((i-1)%3)-1
      local at=(T.exit*CFrame.new(col*2.2,0,-row*1.9)).Position
      for _,e in list do if flat(e.root.Position-at).Magnitude<3 then at=(T.exit*CFrame.new(col*2.2+3.5,0,-row*1.9-3)).Position;break end end
      lanes[i]={id=id,at=ground(at) or Vector3.new(at.X,T.cf.Y,at.Z)}
     end
     for i,L in lanes do
      task.delay((i-1)*burst.pour,function()
       E.pending-=1
       if E.gen~=generation or E.phase~='Active' or not T.alive then return end
       spawnOne(E,L.id,L.at,0,{FromTomb=T.letter},T.model)
      end)
     end
    end
   end
  end
 end,
}

-- Frozen Pass: BLOOD MOON HUNT. The alpha on the rim, packs from alternating approaches.
EVENTS.BloodMoonHunt={
 setup=function(E,list,center)
  local from=centroid(list)
  local spot=rimPoint(center,math.min(44,(E.arenaRadius or 60)*.75),from) or ground(center)
  if not spot then return false end
  local BossDefs=module(combat,'MapBossDefs');local T=BossDefs and BossDefs.timing(E.def.leader)
  local y=spot.Y+((T and T.rootHeight) or 3)+.1
  local cf=CFrame.lookAt(Vector3.new(spot.X,y,spot.Z),Vector3.new(from.X,y,from.Z))
  -- The howl's peak at 2.0 s into the intro (the pack answers right after).
  local npc=spawnLeader(E,cf,E.introStart+2.0);if not npc then return false end
  local v=Instance.new('ObjectValue');v.Name='Leader';v.Value=npc;v.Parent=E.anchor
  E.anchor:SetAttribute('Focus',spot);E.anchor:SetAttribute('FocusFrame',cf)
  -- The first pack answers from beside the alpha.
  task.delay(2.2,function()
   if E.gen~=generation then return end
   for i=1,3 do local p=ground(spot+cf.RightVector*(i-2)*4.5-cf.LookVector*3);if p then task.spawn(spawnOne,E,'werewolf',p,0) end end
  end)
  return true
 end,
 step=function(E,t,list)
  local spec=E.def.spawn
  if t>=E.nextPulse then
   local k=math.clamp((t-E.activeAt)/60,0,1);E.nextPulse=t+Defs.interval(spec,k)
   local room=Defs.cap(spec,#list)-eventAlive(E)-E.pending
   local count=math.min(Defs.pulseSize(spec,#list),room)
   if count>0 then
    -- Alternating approaches: left, then right of the party's centre, across the arena.
    E.side=-(E.side or 1)
    local from=centroid(list);local toCenter=flat(E.center-from);toCenter=toCenter.Magnitude>1 and toCenter.Unit or Vector3.new(0,0,-1)
    local side=Vector3.yAxis:Cross(toCenter)*E.side
    local approach=ground(from+side*36+toCenter*6) or point({anchor=from,band={32,44},minimum=24})
    if approach then
     for i=1,count do
      local a=i*2.39996;local r=i==1 and 0 or 2.6+math.sqrt(i)*1.4
      local p=ground(approach+Vector3.new(math.cos(a)*r,0,math.sin(a)*r)) or approach
      task.spawn(spawnOne,E,'werewolf',p,1,{Pack=E.serial})
     end
     E.serial+=1
    end
   end
  end
  -- Howl buffs run out on time (never stacked: a new howl only refreshes the timer).
  for npc in E.adds do
   local untilAt=npc:GetAttribute('PackEmpoweredUntil')
   if type(untilAt)=='number' and t>=untilAt then npc:SetAttribute('PackEmpoweredUntil',nil);npc:SetAttribute('SpeedBuff',nil);npc:SetAttribute('DamageBuff',nil) end
  end
 end,
 -- Howl (MapBossService hook at its peak): wolves within the shown radius are empowered for a while.
 leader=function(E,kind,A,t)
  if kind~='Howl' or E.phase~='Active' then return end
  local spec=E.def.howl;local root=E.leader and E.leader.PrimaryPart;if not root then return end
  fx:FireAllClients('Howl',root.Position,spec.radius,t)
  local n=0
  for npc in E.adds do
   local r=npc.Parent and npc:FindFirstChild('HumanoidRootPart')
   if r and flat(r.Position-root.Position).Magnitude<=spec.radius then
    npc:SetAttribute('SpeedBuff',spec.speed);npc:SetAttribute('DamageBuff',spec.damage);npc:SetAttribute('PackEmpoweredUntil',t+spec.seconds);n+=1
   end
  end
  if n>0 then publish(E,'EventCue',spec.cue..'|'..tostring(t)) end
 end,
}

-- Volcanic Crater: ERUPTION. Vents in groups take turns; survive 60 s. 2026-10-10 user: "spread out more
-- and larger aoe", "they should change locations ... or just have more of them": 8 vents on two rings
-- (was 6 on one), a 12-stud blast (was 9) plus lava splashes thrown out each eruption, and every
-- second eruption a vent moves to a new spot (marked on the ground before it gets there).
-- The splashes and the move target are picked here and published as attributes BEFORE the state
-- that shows them (Splash1..n + SplashRadius before Charging, MoveTo before Moving), so every client
-- draws exactly the discs this tests.
local function ventSplashes(E,V)
 local S=E.def.vents.splash;local out={}
 if not S then return out end
 local base=math.random()*math.pi*2
 for i=1,S.count do
  local a=base+(i-1)/S.count*math.pi*2+(math.random()-.5)*.6
  local d=S.distance[1]+math.random()*(S.distance[2]-S.distance[1])
  local p=ground(V.center+Vector3.new(math.cos(a),0,math.sin(a))*d)
  if p then table.insert(out,p) end
 end
 return out
end
-- A new open spot for V: in the arena's middle band, at least minGap from every other vent (and its
-- own move target), clear of the players; the farthest from other vents of a few tries, or nil.
local function ventMove(E,V,list)
 local R=E.def.vents.relocate;local arenaR=E.arenaRadius or 60
 local best,score
 for _=1,14 do
  local a=math.random()*math.pi*2;local d=arenaR*(.18+math.random()*.6)
  local p=ground(E.center+Vector3.new(math.cos(a),0,math.sin(a))*d)
  if p then
   local near=math.huge
   for _,o in E.vents do if o~=V then near=math.min(near,flat((o.moveTo or o.center)-p).Magnitude) end end
   local ok=near>=R.minGap and flat(p-V.center).Magnitude>=R.minGap*.75
   if ok then for _,e in list do if flat(e.root.Position-p).Magnitude<R.clear then ok=false;break end end end
   if ok then local s=near+math.random()*6;if not best or s>score then best,score=p,s end end
  end
 end
 return best
end
-- Inside V's blast disc or one of its splash discs (the shapes the clients draw).
local function inEruption(V,spec,at)
 if math.abs(at.Y-V.center.Y)<=6 and flat(at-V.center).Magnitude<=spec.blast then return true end
 local r=spec.splash and spec.splash.radius or 0
 for _,s in V.splashes do if math.abs(at.Y-s.Y)<=6 and flat(at-s).Magnitude<=r then return true end end
 return false
end
EVENTS.Eruption={
 setup=function(E,list,center)
  local spec=E.def.vents;local props=ServerStorage:FindFirstChild('Round10Props');local source=props and props:FindFirstChild('VolcanicVent')
  if not source then return false end
  local from=centroid(list)
  local folder=Instance.new('Folder');folder.Name='Vents';folder.Parent=E.anchor
  E.vents={}
  -- Two rings (spec.rings of the arena radius, clamped to spec.radius): odd vents inner, even outer.
  local arenaR=E.arenaRadius or 60
  local start=math.atan2((from-center).Z,(from-center).X)+math.pi/spec.count
  for i=1,spec.count do
   local a=start+(i-1)/spec.count*math.pi*2;local spot
   local radius=math.clamp(arenaR*spec.rings[(i-1)%#spec.rings+1],spec.radius[1],spec.radius[2])
   for _,clear in {spec.blast+3,6} do
    for _,r in {radius,radius-4,radius+4,radius-8} do
     spot=ground(center+Vector3.new(math.cos(a),0,math.sin(a))*r)
     if spot then for _,e in list do if flat(e.root.Position-spot).Magnitude<clear then spot=nil;break end end end
     if spot then break end
    end
    if spot then break end
   end
   if spot then
    local model=source:Clone();model.Name='Vent_'..i;model:PivotTo(CFrame.new(spot)*CFrame.Angles(0,a,0))
    for _,p in model:GetDescendants() do if p:IsA('BasePart') then p.Anchored=true;p.CanTouch=false;p.CanQuery=false;p.CanCollide=false end end
    -- Groups take opposite vents together (i and i + count/2), so an eruption never closes a side.
    local groupIndex=((i-1)%spec.groups)+1
    model:SetAttribute('Group',groupIndex);model:SetAttribute('Radius',spec.blast);model:SetAttribute('SplashRadius',spec.splash and spec.splash.radius or 0)
    model:SetAttribute('State','Idle');model:SetAttribute('Center',spot)
    model.Parent=folder
    table.insert(E.vents,{model=model,center=spot,group=groupIndex,hits={},splashes={},cycle=-1})
   end
  end
  if #E.vents<3 then return false end
  E.anchor:SetAttribute('Focus',E.vents[1].center)
  -- The slime swarm that advances in the reveal.
  local dir=flat(center-from);dir=dir.Magnitude>1 and dir.Unit or Vector3.new(0,0,-1)
  local swarm=ground(from+dir*34)
  if swarm then
   E.anchor:SetAttribute('Swarm',swarm)
   for i=1,6 do local a=i*2.39996;local r=1+math.sqrt(i)*2.2;local p=ground(swarm+Vector3.new(math.cos(a)*r,0,math.sin(a)*r));if p then task.spawn(spawnOne,E,i%3==0 and 'fire-goblin' or 'lava-slime',p,0) end end
  end
  return true
 end,
 step=function(E,t,list)
  pulse(E,t,E.def.spawn,list)
  local spec=E.def.vents;local every=spec.relocate and spec.relocate.every or 0
  -- Group g's cycle starts at activeAt + (g-1) x gap, every groups x gap seconds: charge, erupt, cool,
  -- and on every `every`-th cycle a move (Defs.ventState).
  local period=spec.groups*spec.gap
  local mobs
  for _,V in E.vents do
   local phaseTime=(t-E.activeAt-(V.group-1)*spec.gap)
   local state,untilAt,n='Idle',nil,-1
   if phaseTime>=0 then
    n=phaseTime//period
    local left;state,left=Defs.ventState(spec,phaseTime%period,every>0 and (n+1)%every==0 and V.stuck~=n)
    untilAt=left and t+left or nil
   end
   local was=V.model:GetAttribute('State')
   if was~=state then
    -- Leaving a move: the vent is now at its new spot.
    if was=='Moving' and V.moveTo then
     V.center=V.moveTo;V.moveTo=nil
     V.model:PivotTo(CFrame.new(V.center)*CFrame.Angles(0,math.random()*math.pi*2,0))
     V.model:SetAttribute('Center',V.center);V.model:SetAttribute('MoveTo',nil)
    end
    if state=='Charging' then
     V.splashes=ventSplashes(E,V)
     for i=1,(spec.splash and spec.splash.count or 0) do V.model:SetAttribute('Splash'..i,V.splashes[i]) end
    elseif state=='Moving' then
     V.moveTo=ventMove(E,V,list)
     if not V.moveTo then state,untilAt,V.stuck='Idle',nil,n end -- nowhere open: it stays this cycle
     V.model:SetAttribute('MoveTo',V.moveTo)
    end
    V.model:SetAttribute('State',state);V.model:SetAttribute('StateUntil',untilAt);table.clear(V.hits)
   end
   if state=='Erupting' then
    -- Damage equals the shown discs (the blast and its splashes): every tick s per target, players
    -- (where they see themselves, CharacterService.seen) and enemies alike.
    for _,e in list do
     local at=Characters.seen(e.player,e.root) or e.root.Position
     if t>=(V.hits[e.player] or 0) and inEruption(V,spec,at) then
      V.hits[e.player]=t+spec.tick;Characters.contact(e.player,spec.playerDamage*(E.damageScale or 1))
     end
    end
    if not mobs then local folder=enemies();mobs=folder and folder:GetChildren() or {} end
    for _,npc in mobs do
     local r=npc.Parent and npc:FindFirstChild('HumanoidRootPart');local h=r and npc:FindFirstChildOfClass('Humanoid')
     if h and h.Health>0 and t>=(V.hits[npc] or 0) and not npc:GetAttribute('IsBoss') and not npc:GetAttribute('EventObjective') and Tags:HasTag(npc,'RogueliteZombie') and inEruption(V,spec,r.Position) then
      V.hits[npc]=t+spec.tick;h:TakeDamage(h.MaxHealth*spec.enemyShare)
     end
    end
   end
  end
 end,
 cleanup=function(E) for _,V in E.vents or {} do if V.model.Parent then V.model:SetAttribute('State','Idle');V.model:SetAttribute('MoveTo',nil) end end end,
}

-- ── Lifecycle ───────────────────────────────────────────────────────────────────────────────────
local function cleanup(E,keepHold)
 E.phase='Done'
 local impl=EVENTS[E.def.id];if impl and impl.cleanup then pcall(impl.cleanup,E) end
 -- Event arrivals go without rewards (Destroy never pays; ZombieDeath only pays deaths).
 local folder=enemies()
 for _,npc in folder and folder:GetChildren() or {} do
  if npc:GetAttribute('EventGen')==E.gen and not npc:GetAttribute('DeathPopped') then npc:Destroy() end
 end
 if E.leader and E.leader.Parent and not E.leader:GetAttribute('DeathPopped') then E.leader:Destroy() end
 if E.anchor then E.anchor:Destroy() end
 if not keepHold then combat:SetAttribute('EventSpawnHold',nil) end
end
local function clearRunAttributes()
 local run=runState();if not run then return end
 for _,key in {'EventId','EventGen','EventPhase','EventIntroStart','EventIntroUntil','EventMap','EventStatus','EventClearedAt','EventCue','EventTimerLabel'} do run:SetAttribute(key,nil) end
end
-- The clear's crystal shower where no leader dropped one (the survival events): ShardDropService's
-- boss shower (50 x 4, shared out among the living run members), from a stand-in that never enters
-- the world, so every map's wave 10 pays what the old midboss did.
local function shower(position)
 local Shards=module(script.Parent,'ShardDropService');if not Shards or not Shards.spawn then return end
 local stand=Instance.new('Model');stand.Name='Round10Clear'
 local h=Instance.new('Humanoid');h.Parent=stand;h.Health=0
 stand:SetAttribute('IsMapBoss',true)
 Tags:AddTag(stand,'RogueliteZombie')
 pcall(Shards.spawn,stand,position)
 stand:Destroy()
end
local function complete(E,t)
 if E.phase~='Active' then return end
 E.phase='Complete'
 publish(E,'EventPhase','Complete');publish(E,'EventClearedAt',t);publish(E,'EventTimerLabel','CLEAR')
 local impl=EVENTS[E.def.id];if impl and impl.cleanup then pcall(impl.cleanup,E) end
 -- Remaining arrivals go (no kill rewards); the leader and coffins are already dead.
 local folder=enemies()
 for _,npc in folder and folder:GetChildren() or {} do
  if npc:GetAttribute('EventGen')==E.gen and not npc:GetAttribute('DeathPopped') and not npc:GetAttribute('IsBoss') and not npc:GetAttribute('EventObjective') then npc:Destroy() end
 end
 if E.def.kind=='survive' then local list=members();shower(centroid(list) or E.center) end
 local run=runState()
 if run then run:SetAttribute('WaveEndsAt',t+Defs.CLEAR_HOLD);run:SetAttribute('BossAlive',false) end
end
function S.abort(reason)
 local E=current;if not E then return end
 current=nil;generation+=1
 if (combat:GetAttribute('CinematicUntil') or 0)>now() then combat:SetAttribute('CinematicUntil',nil) end
 cleanup(E,false)
 clearRunAttributes()
 if reason then print('Round10Service: '..E.def.id..' ended: '..reason) end
end
-- Start the map's event for wave `wave` (BossEncounter). True when it started; false keeps the midboss.
function S.start(map,wave)
 if current then S.abort('replaced') end
 local ok,why=S.ready(map);if not ok then warn('Round10Service: '..tostring(map)..' event not ready, midboss instead: '..tostring(why));return false end
 local def=Defs.forMap(map);local run=runState();if not run then return false end
 local list=members();if #list==0 then return false end
 local center,radius=arena();if not center then return false end
 generation+=1
 local t=now()
 local E={def=def,map=map,wave=wave,gen=generation,phase='Intro',introStart=t,introUntil=t+def.intro,adds={},pending=0,serial=0,nextPulse=math.huge,center=center,arenaRadius=radius}
 E.onLeader=EVENTS[def.id] and EVENTS[def.id].leader
 local _,damageScale=Rules.bossScale(combat:GetAttribute('RunDifficulty'),math.max(1,#list),combat:GetAttribute('RunMap'))
 E.damageScale=damageScale
 current=E
 combat:SetAttribute('EventSpawnHold',true)
 combat:SetAttribute('CinematicUntil',E.introUntil)
 run:SetAttribute('BossAlive',true)
 -- The anchors the cinematic films (Round10Events.client).
 local anchor=Instance.new('Folder');anchor.Name='Round10Event'
 anchor:SetAttribute('EventId',def.id);anchor:SetAttribute('Gen',E.gen);anchor:SetAttribute('Center',center)
 anchor:SetAttribute('Players',centroid(list));anchor:SetAttribute('IntroStart',t);anchor:SetAttribute('IntroUntil',E.introUntil)
 anchor.Parent=workspace;E.anchor=anchor
 local okSetup,result=pcall(EVENTS[def.id].setup,E,list,center)
 if not okSetup or result==false then
  warn('Round10Service: '..def.id..' setup failed, midboss instead: '..tostring(okSetup and 'no room' or result))
  current=nil;generation+=1;combat:SetAttribute('CinematicUntil',nil);cleanup(E,false);clearRunAttributes();run:SetAttribute('BossAlive',false)
  return false
 end
 for key,value in {EventId=def.id,EventMap=map,EventGen=E.gen,EventPhase='Intro',EventIntroStart=t,EventIntroUntil=E.introUntil,
  EventTimerLabel=def.kind=='survive' and Defs.clock(def.duration) or (def.kind=='tombs' and 'TOMBS' or 'BOSS')} do run:SetAttribute(key,value) end
 return true
end
-- Admin (Studio test tools): skip the intro now, or clear the event now (no extra rewards beyond
-- what the clear pays; admin runs pay nothing persistent anyway, AdminConfig.markTestRun).
function S.skipIntro() local E=current;if E and E.phase=='Intro' then E.introUntil=now();combat:SetAttribute('CinematicUntil',nil);return true end;return false end
function S.forceClear()
 local E=current;if not E then return false end
 if E.phase=='Intro' then S.skipIntro();E.phase='Active' end
 for _,T in E.tombs or {} do local h=T.model.Parent and T.model:FindFirstChildOfClass('Humanoid');if h then h.Health=0 end end
 local h=E.leader and E.leader.Parent and E.leader:FindFirstChildOfClass('Humanoid');if h then h.Health=0 end
 for _,npc in E.wardens or {} do local wh=npc.Parent and npc:FindFirstChildOfClass('Humanoid');if wh then wh.Health=0 end end;E.wardensPending=0
 complete(E,now());return true
end

-- One step a tenth of a second.
local acc=0
Run.Heartbeat:Connect(function(dt)
 -- Every frame: the DJ's rushers ride their timeline (EVENTS.CrabRave.moveRushes, 2026-10-10).
 local live=current
 if live and live.rushes and live.phase=='Active' and not live.pausedAt and EVENTS[live.def.id].moveRushes then pcall(EVENTS[live.def.id].moveRushes,live,now()) end
 acc+=dt;if acc<.1 then return end;acc=0
 local E=current;if not E then return end
 local run=runState();local t=now()
 -- The wave or the run moved on without us (players all down, leave, admin jump): abort.
 if combat:GetAttribute('ZombiesEnabled')~=true or not run or run:GetAttribute('Wave')~=E.wave then S.abort('wave ended');return end
 if E.phase=='Complete' then return end
 local list=members()
 local held=paused()
 if held then
  -- Paused: arrivals and hazards hold where they are (survival time is the paused wave clock).
  E.pausedAt=E.pausedAt or t;return
 elseif E.pausedAt then
  local gap=t-E.pausedAt;E.pausedAt=nil
  E.nextPulse+=gap;E.activeAt=(E.activeAt or t)+gap
  for _,T in E.tombs or {} do if T.nextPulse>0 then T.nextPulse+=gap end end
  for _,R in E.rushes or {} do R.at+=gap;if R.npc.Parent then R.npc:SetAttribute('RushAt',R.at) end end -- clients draw the dash from RushAt
 end
 if E.phase=='Intro' then
  if t<E.introUntil then return end
  E.phase='Active';E.activeAt=t;E.nextPulse=t+.6
  publish(E,'EventPhase','Active')
  -- Survival: 60 s on the wave clock from now (ShopService ends the wave at it unless held).
  if E.def.kind=='survive' then run:SetAttribute('WaveEndsAt',t+E.def.duration);publish(E,'EventTimerLabel',nil) end
  status(E)
 end
 if #list==0 then return end
 local ok,err=pcall(EVENTS[E.def.id].step,E,t,list)
 if not ok then warn('Round10Service: '..E.def.id..' step failed: '..tostring(err)) end
 -- The clear conditions, exactly as the HUD states them.
 local kind=E.def.kind
 if kind=='survive' then
  local ends=run:GetAttribute('WaveEndsAt')
  if type(ends)=='number' and t>=ends then complete(E,t) end
 elseif kind=='leader' then
  if not E.leaderAlive then complete(E,t) end
 elseif kind=='tombs' then
  local standing=0
  for _,T in E.tombs do
   if T.alive then
    local h=T.model.Parent and T.model:FindFirstChildOfClass('Humanoid')
    if not h or h.Health<=0 then T.down() else standing+=1 end
   end
  end
  if standing==0 and wardensAlive(E)==0 then complete(E,t) end
 end
end)
return S
