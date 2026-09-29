-- ADMIN panel server (ADMIN_PANEL.md). Owns the RemoteFunction RogueliteCombat.AdminAction.
-- Each request: developer check by UserId (AdminConfig; everyone else gets no reply), a rate
-- limit, then AdminConfig.check on every argument. The owning service does the work, and a
-- successful action marks the run as a test run (no rewards).
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
local function arenaHasOthers(p)
 for _,q in Players:GetPlayers() do if q~=p and q:GetAttribute('StudioArea')=='Arena' and alive(q) then return true end end
 return false
end
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
 if where=='Lobby' then
  local lobby=workspace:FindFirstChild('RogueliteLobby');local spawn=lobby and lobby:FindFirstChild('LobbySpawn')
  if not spawn then return false,'No lobby on this server' end
  p:SetAttribute('StudioArea','Lobby');char:PivotTo(CFrame.new(spawn.Position+Vector3.new(0,4,0)))
  -- Like the old LOBBY switch: nothing keeps running in an empty arena. A sandbox ends with a new run.
  if not arenaHasOthers(p) then if Shop.phase=='Practice' then Shop.resetRun() else Shop.stopWave() end end
  return true,'Lobby'
 end
 if not Role.setMap(where) then return false,'That map is not available here' end
 local spawn=Role.playerSpawn();if not spawn then return false,'No PlayerSpawn on '..where end
 p:SetAttribute('StudioArea','Arena');char:PivotTo(CFrame.new(spawn.Position+Vector3.new(0,4,0)))
 Shop.setPractice()
 return true,'Sandbox on '..where
end
-- Mobs.
function actions.Spawn(p,id,count)
 local sp=spawner();if not sp then return false,NO_ARENA end
 if combat:GetAttribute('ZombiesEnabled')~=true then return false,'Enemies spawn in Sandbox or during a wave' end
 local _,root=alive(p);if not root then return false,'Respawn first' end
 local made=sp:Invoke('Spawn',id,count,root.Position)
 if made==0 then return false,'No open floor 20-40 studs from you (or no model for that enemy)' end
 return true,'Spawned '..made
end
function actions.KeepAlive(p,n,ids) if not spawner() then return false,NO_ARENA end;return keepAlive(n,ids) end
-- Clear all: every enemy goes now. During a wave, turning Keep N alive off brings the wave's
-- normal count back.
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

local last={}
remote.OnServerInvoke=function(p,action,a,b)
 if not Admin.isAdmin(p) then return nil end -- non-developers get no reply
 if os.clock()-(last[p] or -math.huge)<.15 then return {ok=false,message='Slow down'} end
 last[p]=os.clock()
 if not Admin.check(action,a,b) then return {ok=false,message='Invalid request'} end
 -- Mark first: an action that does part of its work and then errors must still void rewards.
 Admin.markTestRun()
 local ran,ok,message=pcall(actions[action],p,a,b)
 if not ran then warn('AdminService:',action,ok);return {ok=false,message='Server error'} end
 return {ok=ok==true,message=message or ''}
end
Players.PlayerRemoving:Connect(function(p) last[p]=nil end)
