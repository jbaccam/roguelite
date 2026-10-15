-- ADMIN panel server (ADMIN_PANEL.md). Owns the RemoteFunction RogueliteCombat.AdminAction.
-- Each request: developer check by UserId (AdminConfig; everyone else gets no reply), a rate
-- limit, AdminConfig.check on every argument, then the shared-run gate (blocked below). Every
-- valid, unblocked request marks the run as a test run (no rewards), even one the owning
-- service then refuses; the owning service does the work.
-- Until plan C's solo test matches, a live server is Combined: one run shared by everyone. Since
-- 2026-10-12 (user: "these commands are what i need to use in arenas so i can give my friends
-- loadouts, pause the game ... prep making my trailer") the panel and the chat commands work with
-- other players in the server: the first request marks the shared run a test run, so nobody in it
-- earns run rewards. A developer leaving hands the shared run back (unpaused, unfrozen, normal
-- waves). Someone joining a test run while no developer is in the server gets a new, rewarding run.
-- Targets (2026-10-12): AdminConfig.Targeted actions act on the request's target (a UserId in the
-- server; nil = the developer). Chat commands (AdminCommands) arrive as one Command request with the
-- typed text, parsed and checked here again.
-- Unsandboxed Script: it uses sandboxed modules (AdminConfig, MapConfig, ServerRole, ShopService)
-- and the spawner's ServerStorage.AdminSpawn bindable (RogueliteZombieChase, unsandboxed).
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local RS=game:GetService('ReplicatedStorage')
local SS=game:GetService('ServerStorage')
local SSS=game:GetService('ServerScriptService')
local combat=RS:WaitForChild('RogueliteCombat')
local Admin=require(combat:WaitForChild('AdminConfig'))
local Maps=require(combat:WaitForChild('MapConfig'))
local Role=require(SSS:WaitForChild('ServerRole'))
local Shop=require(SSS:WaitForChild('ShopService'))
local Commands=require(combat:WaitForChild('AdminCommands'))
-- Permanent gives (Give, /give) need the save; looked up when used so the panel loads without it.
local function profiles()
 local m=SSS:FindFirstChild('ProfileService')
 local ok,P=pcall(function() return m and require(m) end)
 return ok and P or nil
end
local remote=combat:FindFirstChild('AdminAction') or Instance.new('RemoteFunction')
remote.Name='AdminAction';remote.Parent=combat
local NO_ARENA='No arena on this server'

local function alive(p)
 local char=p.Character;local h=char and char:FindFirstChildOfClass('Humanoid');local root=char and char:FindFirstChild('HumanoidRootPart')
 if h and root and h.Health>0 then return char,root end
end
-- The spawner exists wherever enemies can: not on lobby servers (RogueliteZombieChase).
local function spawner() return SS:FindFirstChild('AdminSpawn') end
-- Other players in the arena, downed teammates (death screen) included.
local function arenaHasOthers(p)
 for _,q in Players:GetPlayers() do if q~=p and q:GetAttribute('StudioArea')=='Arena' and (alive(q) or q:GetAttribute('RunDown')) then return true end end
 return false
end
-- A direct child PlayerSpawn in one of the map's Workspace folders (MapConfig), checked before
-- Role.setMap so a failed Travel leaves the active map alone.
local function hasPlayerSpawn(id)
 local map=Maps.get(id);if not map then return false end
 for _,name in map.folders do
  local parked=SS:FindFirstChild('InactiveAreas')
  local folder=workspace:FindFirstChild(name) or (parked and parked:FindFirstChild(name))
  if folder and folder:FindFirstChild('PlayerSpawn') then return true end
 end
 return false
end
local MAX_EXTRAS,MAX_BOSSES=100,5
-- Keep N alive (the old Z-mode plus mob picker): n enemies of the picked EnemyCatalog ids
-- ('' = the map's own mix), respawning as they die. 0 turns it off and brings back the map's
-- mix and the phase's normal count.
local function keepAlive(n,ids)
 local map=Maps.get(Role.activeMap())
 if n==0 then
  combat:SetAttribute('TestZombieCountOverride',nil);combat:SetAttribute('EnemyRoster',map and map.roster)
  combat:SetAttribute('ZombieCount',Shop.phase=='Combat' and Shop.waveEnemyCount() or 0)
  return true,'Keep alive off'
 end
 local list={};for id in ids:gmatch('[^,%s]+') do table.insert(list,id) end
 combat:SetAttribute('TestZombieCountOverride',n);combat:SetAttribute('EnemyRoster',#list>0 and table.concat(list,',') or (map and map.roster))
 combat:SetAttribute('ZombieCount',n)
 return true,'Keeping '..n..' alive'
end

local actions={}
-- One shared test difficulty for manual mobs, Keep N alive and scheduled waves.
-- Existing rigs retain their spawn stats; changing this never heals a live enemy.
function actions.Difficulty(p,id)
 if not spawner() then return false,NO_ARENA end
 if combat:GetAttribute('TutorialRun')==true then return false,'End the tutorial before changing difficulty' end
 combat:SetAttribute('RunDifficulty',id)
 -- 2026-10-10: the explicit pick. Admin-spawned map bosses use Normal unless this still matches
 -- RunDifficulty (MapBossDefs.spawnDifficulty), so a lobby queue's Hard doesn't leak into a test spawn.
 combat:SetAttribute('AdminDifficulty',id)
 return true,id..' difficulty · applies to new enemies and waves'
end
-- Travel: instant in Studio's combined server. Published servers need plan C's teleports.
function actions.Travel(p,where)
 if not (RunService:IsStudio() and Role.get()=='Combined') then return false,'Needs lobby/match teleports (plan C)' end
 local char=alive(p);if not char then return false,'Respawn first' end
 if p:GetAttribute('LobbyQueue')~=nil then return false,'Leave the queue before travelling' end
 if where=='Lobby' then
  local lobby=workspace:FindFirstChild('RogueliteLobby');local spawn=lobby and lobby:FindFirstChild('LobbySpawn')
  if not spawn then return false,'No lobby on this server' end
  p:SetAttribute('StudioArea','Lobby');char:PivotTo(CFrame.new(spawn.Position+Vector3.new(0,4,0)))
  -- Like the old LOBBY switch: nothing keeps running in an empty arena. A sandbox ends with a new run.
  if not arenaHasOthers(p) then if Shop.phase=='Practice' then Shop.resetRun() else Shop.stopWave() end end
  return true,'Lobby'
 end
 -- The arena is shared: never pull other players' map out from under them.
 if arenaHasOthers(p) and where~=Role.activeMap() then return false,'Other players are on '..tostring(Role.activeMap()) end
 if not hasPlayerSpawn(where) then return false,'No PlayerSpawn on '..where end
 if not Role.setMap(where) then return false,'That map is not available here' end
 local spawn=Role.playerSpawn();if not spawn then return false,'No PlayerSpawn on '..where end
 p:SetAttribute('MapTravelPending',true)
 if workspace.StreamingEnabled then
  local ok=pcall(p.RequestStreamAroundAsync,p,spawn.Position,5)
  if not ok then p:SetAttribute('MapTravelPending',nil);return false,'Arena loading failed; retry Travel' end
 end
 if p.Character~=char or not char.Parent then p:SetAttribute('MapTravelPending',nil);return false,'Respawn first' end
 p:SetAttribute('StudioArea','Arena');char:PivotTo(CFrame.new(spawn.Position+Vector3.new(0,4,0)))
 p:SetAttribute('MapTravelPending',nil)
 Shop.setPractice()
 return true,'Sandbox on '..where
end
-- Mobs.
function actions.Spawn(p,id,count)
 local sp=spawner();if not sp then return false,NO_ARENA end
 if combat:GetAttribute('ZombiesEnabled')~=true then return false,'Enemies spawn in Sandbox or during a wave' end
 local _,root=alive(p);if not root then return false,'Respawn first' end
 -- Caps on what's alive: extras are named Admin_nn (split children too); admin bosses are
 -- boss models (IsBoss) the spawner tags AdminSpawn.
 local extras,bosses=0,0
 local folder=workspace:FindFirstChild('RogueliteEnemies')
 for _,npc in folder and folder:GetChildren() or {} do
  if npc.Name:sub(1,6)=='Admin_' then extras+=1 end
  local h=npc:FindFirstChildOfClass('Humanoid')
  if npc:GetAttribute('IsBoss') and npc:GetAttribute('AdminSpawn') and h and h.Health>0 then bosses+=1 end
 end
 if table.find(Admin.BossIds,id) then
  if bosses+count>MAX_BOSSES then return false,'Too many bosses ('..MAX_BOSSES..'). Clear first' end
 elseif extras+count>MAX_EXTRAS then return false,'Too many spawned enemies ('..MAX_EXTRAS..'). Clear first' end
 local made=sp:Invoke('Spawn',id,count,root.Position)
 if made==0 then return false,'No open floor 20-40 studs from you (or no model for that enemy)' end
 return true,'Spawned '..made
end
function actions.KeepAlive(p,n,ids) if not spawner() then return false,NO_ARENA end;return keepAlive(n,ids) end
-- Clear all: every enemy goes now, and Keep N alive turns off. During a wave with Keep N alive
-- on, turning it off brings the wave's normal count back. During a wave without it, the wave
-- stays empty until the next wave (cleared enemies don't respawn).
function actions.ClearMobs(p)
 local sp=spawner();if not sp then return false,NO_ARENA end
 sp:Invoke('Clear');keepAlive(0,'')
 return true,'Cleared'
end
function actions.Freeze(p,on)
 local sp=spawner();if not sp then return false,NO_ARENA end
 sp:Invoke('Freeze',on);return true,on and 'Enemies frozen' or 'Enemies unfrozen'
end
-- Waves.
function actions.Sandbox(p) if not spawner() then return false,NO_ARENA end;Shop.setPractice();return true,'Sandbox · no waves' end
function actions.Waves(p)
 if not spawner() then return false,NO_ARENA end
 if not Shop.setWaves() then return false,'Waves are already running' end
 return true,'Waves from wave 1'
end
function actions.JumpWave(p,n) if not spawner() then return false,NO_ARENA end;Shop.jumpToWave(n);return true,'Wave '..n end
function actions.EndWave(p) if not Shop.endWave() then return false,'No wave running' end;return true,'Wave ended' end
-- Endless boss (2026-10-03): the spawner picks and scales it as Endless does (RogueliteZombieChase).
function actions.EndlessBoss(p)
 local sp=spawner();if not sp then return false,NO_ARENA end
 local ok,message=sp:Invoke('EndlessBoss')
 return ok==true,type(message)=='string' and message or 'No Endless boss'
end
-- Round 10 events (Round10Service, ROUND_10_MASTER_SPEC.md): wave 10 now (this map's event, or the
-- midboss when the event's assets aren't installed: the reason is in the reply), skip its intro, or
-- clear it now (the clear's normal crystals; admin runs pay nothing persistent).
local function round10()
 local m=game:GetService('ServerScriptService'):FindFirstChild('Round10Service')
 local ok,R=pcall(function() return m and require(m) end)
 return ok and R or nil
end
function actions.Round10Start(p)
 if not spawner() then return false,NO_ARENA end
 local R=round10();local map=combat:GetAttribute('RunMap')
 local ready,why=false,'Round10Service not installed'
 if R then ready,why=R.ready(map) end
 Shop.jumpToWave(10)
 return true,ready and 'Wave 10: round 10 event' or ('Wave 10: midboss (event not ready: '..tostring(why)..')')
end
function actions.Round10Skip(p)
 local R=round10();if not (R and R.skipIntro and R.skipIntro()) then return false,'No event intro playing' end
 return true,'Event intro skipped'
end
function actions.Round10Clear(p)
 local R=round10();if not (R and R.forceClear and R.forceClear()) then return false,'No round 10 event running' end
 return true,'Event cleared'
end
function actions.Pause(p,on)
 if not Shop.adminPause(on) then return false,on and 'No wave running' or 'Not paused' end
 return true,on and 'Paused' or 'Resumed'
end
-- Player.
-- on nil toggles (/god).
function actions.God(p,on)
 if on==nil then on=p:GetAttribute('AdminGod')~=true end
 p:SetAttribute('AdminGod',on or nil);return true,on and 'God mode on' or 'God mode off'
end
-- Ghost (/ghost, 2026-10-14, user: "when i go to shift p my character is still in there how can i
-- make him invis or despawn so mobs dont chase him"): AdminGhost makes them invisible (ghostLook,
-- below), no enemy or boss targets them (RogueliteZombieChase, BossService, MapBossService,
-- Round10Service), nothing hits them (EnemyAttacks, CharacterService.contact) and their weapons
-- are off. on nil toggles. Off, or a new run (CharacterService.clearAdmin), puts it all back.
function actions.Ghost(p,on)
 if on==nil then on=p:GetAttribute('AdminGhost')~=true end
 p:SetAttribute('AdminGhost',on or nil)
 local states=combat:FindFirstChild('PlayerStates');local state=states and states:FindFirstChild(tostring(p.UserId))
 if state then state:SetAttribute('WeaponEnabled',not on) end
 return true,on and 'Ghost on: invisible, enemies ignore you' or 'Ghost off'
end
-- Weapons on/off: the old K test key.
function actions.Weapons(p,on)
 local states=combat:FindFirstChild('PlayerStates');local state=states and states:FindFirstChild(tostring(p.UserId))
 if not state then return false,'No weapon state yet' end
 state:SetAttribute('WeaponEnabled',on);return true,on and 'Weapons on' or 'Weapons off'
end
function actions.GiveItem(p,id) return Shop.adminItem(p,id) end
function actions.Shards(p,mode,n) return Shop.adminShards(p,mode,n) end
function actions.Level(p,mode,n) return Shop.adminLevel(p,mode,n) end
-- Turrets: HandymanTurretService puts its handler on ShopService (Shop.turretAdmin): Give n (a
-- turret item, n = 1-4) or Clear (2026-10-04).
function actions.Turret(p,mode,n)
 local handler=Shop.turretAdmin
 if type(handler)~='function' then return false,'Turrets are not running (HandymanTurretService)' end
 return handler(p,mode,n)
end
-- The Give tab's catalog (AdminCommands.entries) from the same modules the client uses.
local catalog
local function entries()
 if catalog then return catalog end
 local Stats=require(combat:WaitForChild('CharacterStats'))
 local okInv,Inventory=pcall(function() return require(RS:WaitForChild('WeaponInventoryUI',5)) end)
 catalog=Commands.entries({Weapons=require(combat:WaitForChild('WeaponCatalog')),Items=require(combat:WaitForChild('ShopCatalog')),
  Armor=require(combat:WaitForChild('ArmorCatalog')),Pets=require(combat:WaitForChild('PetConfig')),
  Classes=Stats.ClassOrder,Signature=Stats.Signature,WeaponIcons=okInv and type(Inventory)=='table' and Inventory.Icons or {}})
 return catalog
end
local function entryByKey(key) for _,e in entries() do if e.key==key then return e end end end
-- TempGive (/tempgive, the Give tab): this run only. A weapon goes in weapon slot `slot` (1-6,
-- replacing what is there) or the next free one (slot 0) at `tier` (ShopService.adminWeapon, since
-- 2026-10-13; was copies). A run item or turret is one more copy (ShopService.adminItem, so its copy
-- cap, the 16 item rows and the 10 turrets hold).
function actions.TempGive(p,key,slot,tier)
 local e=entryByKey(key);if not e or not e.temp then return false,'Not a run item' end
 if not Shop.states[p] then return false,p.Name..' has no run yet' end
 if e.kind=='Weapon' then
  local ok,text=Shop.adminWeapon(p,e.id,tier,slot)
  return ok,p.Name..': '..tostring(text)
 end
 local ok,text=Shop.adminItem(p,e.id)
 return ok,p.Name..': '..tostring(text)
end
-- Armor (/armor, 2026-10-13, user: "sets the users armor set for that round ... make sure we dont
-- wipe their existing gear. it should all be reverted when they go back to the lobby"): the player
-- attribute RunArmor = 'Set' or 'Set:tier' (CharacterStats.runArmor). ArmorService dresses them in
-- the whole set and CharacterService gives its set bonus and gear power; their saved armor is never
-- written. '' takes it off now; leaving the run (the lobby) or a new run clears it too (below, and
-- CharacterService.clearAdmin). Example: Armor('DragonScale', 4) -> Dragon Scale Tier IV this run.
function actions.Armor(p,set,tier)
 if set=='' then p:SetAttribute('RunArmor',nil);return true,p.Name..': run armor off (saved armor back)' end
 local Armor=require(combat:WaitForChild('ArmorCatalog'))
 local d=Armor.ById[set];if not d then return false,'Unknown armor set' end
 if not Shop.members[p] then return false,p.Name..' is not in the run' end
 p:SetAttribute('RunArmor',set..(tier and ':'..tier or ''))
 return true,p.Name..': '..d.name..' set'..(tier and ' Tier '..tier or '')..' for this run'
end
-- Give (/give, the Give tab's Saved mode): for good, through ProfileService. Weapons, armor pieces
-- and pets unlock at `tier` (or gain a copy when owned and no tier is given), a set gives all four
-- pieces, a class unlocks with its weapon. Studio's profiles are in memory; a live server writes
-- the real save, which is what the user asked for (friends' trailer loadouts).
function actions.Give(p,key,tier)
 local e=entryByKey(key);if not e or not e.perm then return false,'Not a saved item' end
 local P=profiles();if not P then return false,'ProfileService is not running' end
 local ok,text
 if e.kind=='Class' then ok,text=P.adminClass(p,e.id)
 elseif e.set then
  local Armor=require(combat:WaitForChild('ArmorCatalog'))
  for _,slot in Armor.Slots do ok,text=P.adminGive(p,Armor.pieceId(e.id,slot),tier);if not ok then break end end
 else ok,text=P.adminGive(p,e.id,tier) end
 return ok==true,p.Name..': '..e.name..' '..tostring(text)
end
-- PauseAll (/pause, 2026-10-12): the wave clock and spawns (Pause) and every enemy (Freeze) together.
-- nil toggles: paused when either is on. Between waves only the freeze applies.
function actions.PauseAll(p,on)
 local sp=spawner()
 if on==nil then on=not (RS:WaitForChild('RogueliteRunState'):GetAttribute('AdminPaused')==true or combat:GetAttribute('AdminFreeze')==true) end
 if on then
  local paused=Shop.adminPause(true)
  if sp then sp:Invoke('Freeze',true) end
  return true,paused and 'Wave paused · enemies frozen' or 'Enemies frozen (no wave clock to pause)'
 end
 Shop.adminPause(false)
 if sp then sp:Invoke('Freeze',false) end
 return true,'Resumed'
end
-- Chat commands (AdminCommands). The text is parsed again here; each part goes through the same
-- rules (AdminConfig.check) and handlers as a panel request. Several players: one line each.
local function playerList()
 local list={};for _,q in Players:GetPlayers() do table.insert(list,{name=q.Name,display=q.DisplayName,userId=q.UserId,player=q}) end
 return list
end
function actions.Command(p,text)
 local cmd,why=Commands.parse(text);if not cmd then return false,why end
 if cmd.name=='admin' then return true,Commands.HELP end
 if cmd.name=='pause' then return actions.PauseAll(p,true) end
 if cmd.name=='resume' then return actions.PauseAll(p,false) end
 -- /wave n: that wave starts now. Paused before (/pause): paused again at once, so the new wave's
 -- clock and spawns wait for /resume while everyone sets up.
 if cmd.name=='wave' then
  local was=RS:WaitForChild('RogueliteRunState'):GetAttribute('AdminPaused')==true or combat:GetAttribute('AdminFreeze')==true
  local ok,message=actions.JumpWave(p,cmd.wave)
  if ok and was then actions.PauseAll(p,true);message=message..' · still paused (/resume)' end
  return ok,message
 end
 local targets,whyNot=Commands.players(cmd.player,playerList(),p.UserId)
 if not targets then return false,whyNot end
 if #targets==0 then return false,'Nobody else is here' end
 local action,a,b,c
 if cmd.name=='god' then action,a='God',cmd.on
 elseif cmd.name=='ghost' then action,a='Ghost',cmd.on
 elseif cmd.name=='armor' then
  if cmd.off then action,a='Armor',''
  else
   local e,missing=Commands.find(entries(),cmd.item,'armor');if not e then return false,missing end
   action,a,b='Armor',e.id,cmd.tier
  end
 elseif cmd.name=='tempgive' then
  -- Weapons: [slot] [tier]. Run items and turrets have no slot, so a lone number is the tier
  -- ("/tempgive me turret 4" -> a Gatling Rig).
  local e,missing=Commands.find(entries(),cmd.item,'temp',cmd.tier);if not e then return false,missing end
  if e.kind=='Weapon' then action,a,b,c='TempGive',e.key,cmd.slot or 0,cmd.tier or 1
  else
   local tier=cmd.tier or cmd.slot
   if tier and tier>4 then return false,'Tier must be 1-4' end
   if tier and e.kind=='Turret' then e=Commands.find(entries(),cmd.item,'temp',tier) or e end
   action,a,b,c='TempGive',e.key,0,tier or 1
  end
 else
  local e,missing=Commands.find(entries(),cmd.item,'perm',cmd.tier);if not e then return false,missing end
  action,a,b='Give',e.key,cmd.tier
 end
 if not Admin.check(action,a,b,c) then return false,'Invalid request' end
 local lines,any={},false
 for _,t in targets do
  local ran,ok,message=pcall(actions[action],t.player,a,b,c)
  if not ran then warn('AdminService command:',action,ok);ok,message=false,'Server error' end
  any=any or ok==true
  table.insert(lines,((action=='God' or action=='Ghost') and (t.player.Name..': ') or '')..tostring(message))
 end
 return any,table.concat(lines,' · ')
end
-- Tutorial (plans/2026-10-03-tutorial-design.md): TutorialDirector's ServerStorage.TutorialControl
-- does the work. Start: the run from the top. Lobby: the reward now, then the lobby steps. End:
-- back to normal play. Each starts a fresh run, which also clears the test-run mark.
local function tutorial(p,what)
 local control=SS:FindFirstChild('TutorialControl');if not control then return false,'Tutorial not installed' end
 return control:Invoke(what,p)
end
function actions.TutorialStart(p) return tutorial(p,'Start') end
function actions.TutorialLobby(p) return tutorial(p,'Lobby') end
function actions.TutorialEnd(p) return tutorial(p,'End') end
-- Simulate gift to me (2026-10-04): RogueliteMeta's ServerStorage.GiftControl puts a fake Starter
-- Pack gift from "Studio test" in this developer's in-memory inbox and runs the real delivery, so
-- the GIFT FROM popup shows without Robux (a second one pays emeralds: already owned).
function actions.GiftTest(p)
 local control=SS:FindFirstChild('GiftControl');if not control then return false,'Gifting not installed' end
 return control:Invoke('Test',p)
end
for _,name in Admin.Actions do assert(actions[name],'AdminService has no handler for '..name) end

-- The shared-run gate, checked before anything is marked. A reason string blocks the request.
local function blocked(p,action)
 -- Travel can't do anything outside Studio's combined server, so it must not mark the run either.
 if action=='Travel' and not (RunService:IsStudio() and Role.get()=='Combined') then return 'Needs lobby/match teleports (plan C)' end
 -- The tutorial buttons too: Studio profiles live in memory, so its reward can be paid again there.
 if string.sub(action,1,8)=='Tutorial' and not (RunService:IsStudio() and Role.get()=='Combined') then return 'Studio only: the live tutorial starts on first join' end
 -- A fake gift is a free Starter Pack: never on a live server (real gifts come from Robux).
 if action=='GiftTest' and not RunService:IsStudio() then return 'Studio only: real gifts come from Robux' end
 return nil
end

local last={}
remote.OnServerInvoke=function(p,action,a,b,c,target)
 if not Admin.isAdmin(p) then return nil end -- non-developers get no reply
 if os.clock()-(last[p] or -math.huge)<.15 then return {ok=false,message='Slow down'} end
 last[p]=os.clock()
 if not Admin.check(action,a,b,c,target) then return {ok=false,message='Invalid request'} end
 local why=blocked(p,action);if why then return {ok=false,message=why} end
 -- Targeted actions: the named player, who must be in this server.
 local who=p
 if target~=nil then who=Players:GetPlayerByUserId(target);if not who then return {ok=false,message='That player left'} end end
 -- Mark first: an action that does part of its work and then errors must still void rewards.
 Admin.markTestRun()
 local ran,ok,message=pcall(actions[action],who,a,b,c)
 if not ran then warn('AdminService:',action,ok);return {ok=false,message='Server error'} end
 return {ok=ok==true,message=message or ''}
end
-- Hand the shared run back: no admin Pause, Freeze or Keep N alive; after() finishes the job
-- (normal waves, or a new run). Errors only warn.
local function handBack(why,after)
 local ok,err=pcall(function()
  Shop.adminPause(false) -- false when it wasn't paused; nothing to do then
  local sp=spawner()
  if sp then sp:Invoke('Freeze',false);keepAlive(0,'') end -- no spawner: neither can be on
  after()
 end)
 if not ok then warn('AdminService: hand back ('..why..') failed:',err) end
end
-- A developer leaving while others stay: the run goes back to normal waves (Sandbox ends). It
-- stays a test run (AdminTestRun is untouched). When nobody stays, ShopService resets the run anyway.
Players.PlayerRemoving:Connect(function(p)
 last[p]=nil
 if not Admin.isAdmin(p) then return end
 for _,q in Players:GetPlayers() do
  if q~=p then
   handBack('developer left',function() if Shop.phase=='Practice' then Shop.setWaves() end end)
   return
  end
 end
end)
-- A non-developer joining a live server where a developer has been testing, with no developer
-- left in it, gets a real, rewarding run. While a developer is here (a trailer session with
-- friends, 2026-10-12) the test run carries on: a friend rejoining must not wipe the setup.
local run=RS:WaitForChild('RogueliteRunState')
-- A ghost's look: every part and decal of the character invisible (the old values kept in a
-- GhostBase attribute and put back after), the name hidden, and anything added while a ghost
-- (armor re-dress, accessories) hidden too.
local ghostAdds={}
local function ghostPart(d,on)
 if not (d:IsA('BasePart') or d:IsA('Decal')) then return end
 local base=d:GetAttribute('GhostBase')
 if on then
  if base==nil then d:SetAttribute('GhostBase',d.Transparency) end
  d.Transparency=1
 elseif base~=nil then d.Transparency=base;d:SetAttribute('GhostBase',nil) end
end
local function ghostLook(p)
 local c=p.Character;if not c then return end
 local on=p:GetAttribute('AdminGhost')==true
 for _,d in c:GetDescendants() do ghostPart(d,on) end
 local h=c:FindFirstChildOfClass('Humanoid')
 if h then h.DisplayDistanceType=on and Enum.HumanoidDisplayDistanceType.None or Enum.HumanoidDisplayDistanceType.Viewer end
 if ghostAdds[p] then ghostAdds[p]:Disconnect();ghostAdds[p]=nil end
 if on then ghostAdds[p]=c.DescendantAdded:Connect(function(d) task.defer(ghostPart,d,true) end) end
end
local function watchGhost(p)
 p:GetAttributeChangedSignal('AdminGhost'):Connect(function() ghostLook(p) end)
 p.CharacterAdded:Connect(function() task.defer(ghostLook,p) end)
end
Players.PlayerAdded:Connect(watchGhost)
for _,p in Players:GetPlayers() do watchGhost(p) end
Players.PlayerRemoving:Connect(function(p) if ghostAdds[p] then ghostAdds[p]:Disconnect();ghostAdds[p]=nil end end)
-- Run armor (/armor) goes when its player leaves the run: back in the lobby, or out of the server.
local function watchRunArmor(p)
 p:GetAttributeChangedSignal('RunMember'):Connect(function() if p:GetAttribute('RunMember')~=true then p:SetAttribute('RunArmor',nil) end end)
 p:GetAttributeChangedSignal('LobbyPreviewActive'):Connect(function() if p:GetAttribute('LobbyPreviewActive')==true then p:SetAttribute('RunArmor',nil) end end)
end
Players.PlayerAdded:Connect(watchRunArmor)
for _,p in Players:GetPlayers() do watchRunArmor(p) end
local function joined(p)
 if RunService:IsStudio() or Admin.isAdmin(p) then return end
 for _,q in Players:GetPlayers() do if Admin.isAdmin(q) then return end end
 if Admin.isTestRun(run) or run:GetAttribute('AdminPaused') or combat:GetAttribute('AdminFreeze') or Shop.phase=='Practice' then
  handBack('player joined',Shop.resetRun)
 end
end
Players.PlayerAdded:Connect(joined)
for _,p in Players:GetPlayers() do task.spawn(joined,p) end
