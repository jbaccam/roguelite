-- Which kind of server this is and which map it plays (LOBBY_AND_MATCH_SERVERS.md §1).
-- Match: a reserved server (TeleportService:ReserveServer). Lobby: every other live server,
-- including player-bought VIP servers. Studio: Workspace.StudioServerRole picks 'Lobby' or
-- 'Match'; anything else is 'Combined' (lobby and maps in one server, the old preview).
-- Areas a role doesn't use wait in ServerStorage.InactiveAreas, so clients never stream them.
-- The active map is the combat attribute RunMap. Only its PlayerSpawn is enabled, because Roblox
-- spawns players at a random enabled SpawnLocation.
local RS=game:GetService('ReplicatedStorage')
local RunService=game:GetService('RunService')
local ServerStorage=game:GetService('ServerStorage')
local combat=RS:WaitForChild('RogueliteCombat')
local Maps=require(combat:WaitForChild('MapConfig'))
local R={}

function R.detect(isStudio,studioRole,privateServerId,privateServerOwnerId)
 if isStudio then return (studioRole=='Lobby' or studioRole=='Match') and studioRole or 'Combined' end
 return (privateServerId~='' and privateServerOwnerId==0) and 'Match' or 'Lobby'
end
local role=R.detect(RunService:IsStudio(),workspace:GetAttribute('StudioServerRole'),game.PrivateServerId,game.PrivateServerOwnerId)
function R.get() return role end
function R.activeMap() local id=combat:GetAttribute('RunMap');return Maps.valid(id) and id or nil end
-- A direct child of the active map's folders: markers, PlayerSpawn, blockers, boundary.
function R.find(name)
 local map=Maps.get(R.activeMap());if not map or type(name)~='string' then return nil end
 for _,folderName in map.folders do
  local folder=workspace:FindFirstChild(folderName);local child=folder and folder:FindFirstChild(name)
  if child then return child end
 end
 return nil
end
function R.marker() return R.find('RogueliteZombieSpawn') end
function R.playerSpawn() return R.find('PlayerSpawn') end

-- Edit mode (tests, command bar): detection only, no side effects.
if not RunService:IsRunning() then return R end

local parked=ServerStorage:FindFirstChild('InactiveAreas') or Instance.new('Folder')
parked.Name='InactiveAreas';parked.Parent=ServerStorage
local function place(name,active)
 local area=workspace:FindFirstChild(name) or parked:FindFirstChild(name)
 if area then area.Parent=active and workspace or parked end
end
local function applyMap()
 local id=R.activeMap();if role=='Lobby' or not id then return end
 for mapId,map in Maps.Maps do
  for _,name in map.folders do
   if role=='Match' then place(name,mapId==id) end
   local area=workspace:FindFirstChild(name) or parked:FindFirstChild(name)
   local spawn=area and area:FindFirstChild('PlayerSpawn')
   if spawn and spawn:IsA('SpawnLocation') then spawn.Enabled=mapId==id end
  end
 end
 combat:SetAttribute('EnemyRoster',Maps.get(id).roster)
end
-- Switch the active map: once per match server, and on each START in Combined Studio.
function R.setMap(id)
 if not Maps.valid(id) then return false end
 if combat:GetAttribute('RunMap')==id then applyMap() else combat:SetAttribute('RunMap',id) end
 return true
end

RS:SetAttribute('ServerRole',role)
if role=='Lobby' then
 for _,map in Maps.Maps do for _,name in map.folders do place(name,false) end end
elseif role=='Match' then
 for _,name in Maps.LobbyFolders do place(name,false) end
 for _,map in Maps.Maps do for _,name in map.folders do place(name,false) end end
end
combat:GetAttributeChangedSignal('RunMap'):Connect(applyMap)
if role=='Combined' then
 R.setMap(R.activeMap() or Maps.Default)
elseif role=='Match' and RunService:IsStudio() then
 -- Studio stand-in for the match entry that live match servers read (plan C).
 local studioMap=workspace:GetAttribute('StudioMatchMap')
 combat:SetAttribute('RunDifficulty',workspace:GetAttribute('StudioMatchDifficulty') or 'Normal')
 R.setMap(Maps.valid(studioMap) and studioMap or Maps.Default)
end
return R
