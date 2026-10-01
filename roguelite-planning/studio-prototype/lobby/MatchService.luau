-- Lobby -> match -> lobby trips (LOBBY_AND_MATCH_SERVERS.md §2 and §5, plan C).
-- Lobby: reserve a private match server, write who is coming and what they play (a MemoryStore
-- entry the clients never see), hand every save over (ProfileService.handOff) and teleport the
-- party. Match: read that entry, load its map, admit only the party, give each member their
-- validated loadout and start wave 1 once everyone is in. Give Up in a match, and anyone who isn't
-- listed, goes back to a public lobby server. Teleports only work in the published game; Studio
-- plays in the Combined role, or as a Match with Workspace.StudioServerRole (ServerRole).
-- Unsandboxed (TeleportService, MemoryStoreService), like ProfileService and RogueliteMeta.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Teleport=game:GetService('TeleportService')
local Memory=game:GetService('MemoryStoreService')
local RS=game:GetService('ReplicatedStorage')
local SSS=game:GetService('ServerScriptService')
local Role=require(SSS:WaitForChild('ServerRole'))
local Profiles=require(SSS:WaitForChild('ProfileService'))
local Shop=require(SSS:WaitForChild('ShopService'))
local Rules=require(RS:WaitForChild('RunSetupRules'))
local combat=RS:WaitForChild('RogueliteCombat')
local M={}
local ENTRY_SECONDS=3600 -- a match entry outlives any trip; the run itself can go on longer
local PARTY_WAIT=30 -- wave 1 waits this long for missing members
local entries=Memory:GetHashMap('RogueliteMatchV1')
local studio=RunService:IsStudio()
local trips={} -- player -> {options, tries}: teleports in flight, for TeleportInitFailed

local function retry(times,fn,...)
 local ok,a,b
 for attempt=1,times do
  ok,a,b=pcall(fn,...)
  if ok then return true,a,b end
  if attempt<times then task.wait(attempt) end
 end
 return false,a
end

-- Failed trip from the lobby (set by RogueliteLobbyPreview to tell the player).
M.onTeleportFailed=nil
local function failed(p,message)
 Profiles.reclaim(p)
 -- A match player who gave up was held dead for the trip; let them respawn and play on.
 p:SetAttribute('HoldRespawn',false)
 if M.onTeleportFailed then M.onTeleportFailed(p,message) end
end
local function go(players,options)
 local ok,err=retry(2,Teleport.TeleportAsync,Teleport,game.PlaceId,players,options)
 if not ok then warn('MatchService: teleport failed',err);return false end
 for _,p in players do trips[p]={options=options,tries=0} end
 return true
end

-- Lobby: send a party to a new match. loadouts: userId -> {class=,weapon=}, already validated.
-- All or nobody: returns true, or false and a message for the players.
function M.launch(players,map,difficulty,loadouts)
 if studio then return false,'Runs start in the published game. Use the combined Studio mode to play here' end
 local ok,code,serverId=retry(2,Teleport.ReserveServer,Teleport,game.PlaceId)
 if not ok then return false,"Couldn't start the run, try again" end
 local members={}
 for _,p in players do members[tostring(p.UserId)]=loadouts[p.UserId] or {} end
 if not retry(2,entries.SetAsync,entries,serverId,{map=map,difficulty=difficulty,members=members},ENTRY_SECONDS) then
  return false,"Couldn't start the run, try again"
 end
 -- Saves first: the match server can only load a save this lobby has released.
 local handed={}
 for _,p in players do
  if p.Parent~=Players or not Profiles.handOff(p) then
   for _,q in handed do Profiles.reclaim(q) end
   return false,"Couldn't save everyone's progress, try again"
  end
  table.insert(handed,p)
 end
 local options=Instance.new('TeleportOptions');options.ReservedServerAccessCode=code
 if not go(handed,options) then
  for _,p in handed do Profiles.reclaim(p) end
  return false,"Couldn't start the run, try again"
 end
 return true
end

-- Match: back to a public lobby server. Returns true when the teleport started.
function M.toLobby(players)
 if studio or Role.get()~='Match' then return false end
 local going={}
 for _,p in players do
  -- A save still loading is released by ProfileService when the player leaves.
  if p.Parent==Players and (not Profiles.get(p) or Profiles.handOff(p)) then table.insert(going,p) end
 end
 if #going==0 then return false end
 if not go(going,nil) then
  for _,p in going do Profiles.reclaim(p) end
  return false
 end
 return true
end

Teleport.TeleportInitFailed:Connect(function(player,result,message)
 local trip=trips[player];if not trip then return end
 warn('MatchService: teleport init failed',player.UserId,result,message)
 if trip.tries<1 then
  trip.tries+=1;task.wait(2)
  if player.Parent==Players and pcall(Teleport.TeleportAsync,Teleport,game.PlaceId,{player},trip.options) then return end
 end
 trips[player]=nil
 failed(player,"Couldn't reach the server, try again")
end)
Players.PlayerRemoving:Connect(function(p) trips[p]=nil end)

-- Match side -------------------------------------------------------------------------------
-- The member's loadout from the entry, checked against their own save once it loads; a locked
-- class or weapon falls back to the class's signature weapon (Brawler if the class is locked).
local function applyLoadout(p,want)
 local started=os.clock()
 while p.Parent==Players and p:GetAttribute('ProfileLoaded')~=true and not p:GetAttribute('ProfileLoadFailed') and os.clock()-started<30 do task.wait(.2) end
 local class=type(want)=='table' and want.class or nil
 local weapon=type(want)=='table' and want.weapon or nil
 if not Rules.validLoadout(p,class,weapon) then
  if type(class)~='string' or not Rules.progress(p).classes[class] or not Rules.Signature[class] then class='Brawler' end
  weapon=Rules.Signature[class]
 end
 p:SetAttribute('RunClass',class);p:SetAttribute('RunWeapon',weapon)
end

local started=false
function M.start()
 if started or Role.get()~='Match' or not RunService:IsRunning() then return end
 started=true
 local entry,bad=nil,false
 local ready={} -- member -> loadout applied
 local firstArrival
 local function admit(p)
  if bad then if not M.toLobby({p}) then p:Kick('This run could not start. Please rejoin.') end;return end
  if not entry then ready[p]=true;firstArrival=firstArrival or os.clock();return end -- Studio stand-in: everyone plays
  local want=entry.members[tostring(p.UserId)]
  if want==nil then
   if not M.toLobby({p}) then p:Kick('This run is private.') end
   return
  end
  firstArrival=firstArrival or os.clock()
  applyLoadout(p,want);ready[p]=true
 end
 task.spawn(function()
  if not studio then
   for attempt=1,5 do
    local ok,value=pcall(entries.GetAsync,entries,game.PrivateServerId)
    if ok and type(value)=='table' then entry=value;break end
    task.wait(attempt)
   end
   if entry and Role.setMap(entry.map) then combat:SetAttribute('RunDifficulty',Rules.DifficultyIndex[entry.difficulty] and entry.difficulty or 'Normal')
   else bad=true;entry=nil;warn('MatchService: no usable match entry for',game.PrivateServerId) end
  end
  Players.PlayerAdded:Connect(admit)
  for _,p in Players:GetPlayers() do task.spawn(admit,p) end
  -- Wave 1 starts once every listed member is in the arena, or PARTY_WAIT after the first one.
  while not bad do
   task.wait(.5)
   local expected,arrived=0,0
   if entry then for id in entry.members do expected+=1;local p=Players:GetPlayerByUserId(tonumber(id));if p and ready[p] and Shop.isMember(p) then arrived+=1 end end
   else for p in ready do if p.Parent==Players then expected+=1;if Shop.isMember(p) then arrived+=1 end end end end
   if arrived>0 and (arrived>=expected or os.clock()-(firstArrival or os.clock())>=PARTY_WAIT) then
    Shop.startFirstWave();break
   end
  end
 end)
end

return M
