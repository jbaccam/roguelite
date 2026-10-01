-- ADMIN panel server (ADMIN_PANEL.md). Owns the RemoteFunction RogueliteCombat.AdminAction.
-- Each request: developer check by UserId (AdminConfig; everyone else gets no reply), a rate
-- limit, AdminConfig.check on every argument, then the shared-run gate (blocked below). Every
-- valid, unblocked request marks the run as a test run (no rewards), even one the owning
-- service then refuses; the owning service does the work.
-- Until plan C's solo test matches, a live server is Combined: one run shared by everyone. So on
-- a live server the panel only works while no other player (non-developer) is in the server,
-- and a developer leaving hands the shared run back (unpaused, unfrozen, normal waves).
-- A non-developer joining a live server mid-test ends the developer's test with a new, rewarding run.
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
function actions.Pause(p,on)
 if not Shop.adminPause(on) then return false,on and 'No wave running' or 'Not paused' end
 return true,on and 'Paused' or 'Resumed'
end
-- Player.
function actions.God(p,on) p:SetAttribute('AdminGod',on or nil);return true,on and 'God mode on' or 'God mode off' end
-- Weapons on/off: the old K test key.
function actions.Weapons(p,on)
 local states=combat:FindFirstChild('PlayerStates');local state=states and states:FindFirstChild(tostring(p.UserId))
 if not state then return false,'No weapon state yet' end
 state:SetAttribute('WeaponEnabled',on);return true,on and 'Weapons on' or 'Weapons off'
end
function actions.GiveItem(p,id) return Shop.adminItem(p,id) end
function actions.Shards(p,mode,n) return Shop.adminShards(p,mode,n) end
function actions.Level(p,mode,n) return Shop.adminLevel(p,mode,n) end
for _,name in Admin.Actions do assert(actions[name],'AdminService has no handler for '..name) end

-- The shared-run gate, checked before anything is marked. A reason string blocks the request.
local function blocked(p,action)
 -- A live server's run is shared (Combined until plan C): never test on other players' run.
 if not RunService:IsStudio() then
  for _,q in Players:GetPlayers() do
   if q~=p and not Admin.isAdmin(q) then return "Other players are in this server. Use the panel when you're alone (solo test matches come with plan C)." end
  end
 end
 -- Travel can't do anything outside Studio's combined server, so it must not mark the run either.
 if action=='Travel' and not (RunService:IsStudio() and Role.get()=='Combined') then return 'Needs lobby/match teleports (plan C)' end
 return nil
end

local last={}
remote.OnServerInvoke=function(p,action,a,b)
 if not Admin.isAdmin(p) then return nil end -- non-developers get no reply
 if os.clock()-(last[p] or -math.huge)<.15 then return {ok=false,message='Slow down'} end
 last[p]=os.clock()
 if not Admin.check(action,a,b) then return {ok=false,message='Invalid request'} end
 local why=blocked(p,action);if why then return {ok=false,message=why} end
 -- Mark first: an action that does part of its work and then errors must still void rewards.
 Admin.markTestRun()
 local ran,ok,message=pcall(actions[action],p,a,b)
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
-- A non-developer joining a live server where a developer has been testing gets a real,
-- rewarding run: the gate kept everyone else out, so this only ends the developer's own test.
local run=RS:WaitForChild('RogueliteRunState')
local function joined(p)
 if RunService:IsStudio() or Admin.isAdmin(p) then return end
 if Admin.isTestRun(run) or run:GetAttribute('AdminPaused') or combat:GetAttribute('AdminFreeze') or Shop.phase=='Practice' then
  handBack('player joined',Shop.resetRun)
 end
end
Players.PlayerAdded:Connect(joined)
for _,p in Players:GetPlayers() do task.spawn(joined,p) end
