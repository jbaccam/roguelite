-- Lobby -> match -> lobby trips (LOBBY_AND_MATCH_SERVERS.md §2 and §5, plan C).
-- Lobby: reserve a private match server, write who is coming and what they play (a MemoryStore
-- entry the clients never see), hand every save over (ProfileService.handOff) and teleport the
-- party. Match: read that entry, load its map, admit only the party, give each member their
-- validated loadout and start wave 1 once everyone is in and past the loading screen. Give Up in
-- a match, and anyone who isn't listed, goes back to a public lobby server. Teleports only work
-- in the published game; Studio plays in the Combined role, or as a Match with
-- Workspace.StudioServerRole (ServerRole).
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
local Tutorial=require(combat:WaitForChild('TutorialConfig'))
local M={}
local ENTRY_SECONDS=3600 -- a match entry outlives any trip; the run itself can go on longer
local PARTY_WAIT=30 -- wave 1 waits this long for missing members
-- ...and this long for members already here whose loading screen is still up. Their screen is
-- gone by ~33 s (LoadingScreen MAX_SECONDS 30 + the fade), so only a client that never reports
-- waits the full time.
local LOAD_WAIT=45
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
-- The loading screen (ReplicatedFirst.LoadingScreen) shows where a player is going: TravelTo brings
-- it up before the teleport, and the `loading` teleport data picks the art on arrival. Cosmetic only;
-- the match still reads its own entry.
local function setTravel(players,travel)
 for _,p in players do
  if p.Parent==Players then p:SetAttribute('TravelTo',travel and travel.map);p:SetAttribute('TravelDifficulty',travel and travel.difficulty) end
 end
end
local function failed(p,message)
 Profiles.reclaim(p)
 setTravel({p},nil)
 -- A match player who gave up was held dead for the trip; let them respawn and play on.
 p:SetAttribute('HoldRespawn',false)
 if M.onTeleportFailed then M.onTeleportFailed(p,message) end
end
local function go(players,options,travel)
 options=options or Instance.new('TeleportOptions')
 options:SetTeleportData({loading=travel})
 setTravel(players,travel)
 task.wait(.3) -- lets TravelTo reach the clients first, so their screen is set as the teleport GUI
 local ok,err=retry(2,Teleport.TeleportAsync,Teleport,game.PlaceId,players,options)
 if not ok then warn('MatchService: teleport failed',err);setTravel(players,nil);return false end
 for _,p in players do trips[p]={options=options,tries=0} end
 return true
end

-- Lobby: send a party to a new match. loadouts: userId -> {class=,weapon=}, already validated.
-- All or nobody: returns true, or false and a message for the players.
-- extra (optional): {tutorial=true} makes it the first-join tutorial run (TutorialDirector).
function M.launch(players,map,difficulty,loadouts,extra)
 if studio then return false,'Runs start in the published game. Use the combined Studio mode to play here' end
 local ok,code,serverId=retry(2,Teleport.ReserveServer,Teleport,game.PlaceId)
 if not ok then return false,"Couldn't start the run, try again" end
 local members={}
 for _,p in players do members[tostring(p.UserId)]=loadouts[p.UserId] or {} end
 -- code: the server's own access code, so it can send a dropped player back (rejoin, below).
 local tutorial=type(extra)=='table' and extra.tutorial==true or nil
 if not retry(2,entries.SetAsync,entries,serverId,{map=map,difficulty=difficulty,members=members,code=code,tutorial=tutorial},ENTRY_SECONDS) then
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
 if not go(handed,options,{map=map,difficulty=difficulty}) then
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
 if not go(going,nil,{map='Lobby'}) then
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
-- Rejoin (plan J item 9) -------------------------------------------------------------------
-- A member who disconnects mid-run leaves their build on the match server (ShopService.stashFor).
-- The match server writes a record under their user id with its access code, and refreshes it
-- while it is running and the build is kept; a lobby that finds a fresh record offers REJOIN RUN.
-- A record older than REJOIN_FRESH means that server is gone, so it isn't offered.
local rejoins=Memory:GetHashMap('RogueliteRejoinV1')
local REJOIN_FRESH=150
local offered={} -- match: userId -> {at=os.time() last written}
local function writeRejoin(userId)
 local rec={code=M.code,server=game.PrivateServerId,map=combat:GetAttribute('RunMap'),difficulty=combat:GetAttribute('RunDifficulty'),
  wave=Shop.wave,at=os.time()}
 if retry(2,rejoins.SetAsync,rejoins,tostring(userId),rec,Shop.REJOIN_SECONDS or 600) then offered[userId]={at=rec.at} end
end
local function clearRejoin(userId)
 offered[userId]=nil
 task.spawn(function() retry(2,rejoins.RemoveAsync,rejoins,tostring(userId)) end)
end
-- Lobby: the run this player dropped out of, if its server still runs it; nil otherwise.
function M.rejoinOffer(p)
 if studio or Role.get()~='Lobby' then return nil end
 local ok,rec=retry(2,rejoins.GetAsync,rejoins,tostring(p.UserId))
 if not ok or type(rec)~='table' or type(rec.code)~='string' or os.time()-(tonumber(rec.at) or 0)>REJOIN_FRESH then return nil end
 return rec
end
-- Lobby: back into that run. Returns true when the teleport started, or false and a message.
function M.rejoin(p)
 local rec=M.rejoinOffer(p);if not rec then return false,'That run has ended' end
 if not Profiles.handOff(p) then return false,"Couldn't save your progress, try again" end
 local options=Instance.new('TeleportOptions');options.ReservedServerAccessCode=rec.code
 if not go({p},options,{map=rec.map,difficulty=rec.difficulty}) then Profiles.reclaim(p);return false,"Couldn't reach the run, try again" end
 return true
end
function M.dismissRejoin(p) if not studio then clearRejoin(p.UserId) end end
Players.PlayerRemoving:Connect(function(p)
 trips[p]=nil
 if studio or Role.get()~='Match' or not M.code then return end
 -- Deferred, so ShopService's own PlayerRemoving (which keeps the build) has run by then.
 local userId=p.UserId
 task.defer(function() if Shop.stashFor and Shop.stashFor(userId) then writeRejoin(userId) end end)
end)
-- Match: keep fresh records fresh, and drop any whose build is no longer kept (expired, or the run
-- reset) so nobody is sent into a run they can't get back.
task.spawn(function()
 while true do
  task.wait(15)
  for userId,o in offered do
   if not (Shop.stashFor and Shop.stashFor(userId)) or Players:GetPlayerByUserId(userId) then clearRejoin(userId)
   elseif os.time()-o.at>=60 then task.spawn(writeRejoin,userId) end
  end
 end
end)

-- Match side -------------------------------------------------------------------------------
-- The member's loadout from the entry, checked against their own save once it loads; a locked
-- class or weapon falls back to the class's signature weapon (Brawler if the class is locked).
local function applyLoadout(p,want)
 local started=os.clock()
 -- A DataStore outage is retried for about a minute (ProfileLock.ERROR_SECONDS) before the player
 -- is asked to rejoin, so wait that long too rather than hand out a default loadout at 30 s.
 while p.Parent==Players and p:GetAttribute('ProfileLoaded')~=true and not p:GetAttribute('ProfileLoadFailed') and os.clock()-started<75 do task.wait(.2) end
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
  if offered[p.UserId] then clearRejoin(p.UserId) end -- back in: the way back isn't needed now
  applyLoadout(p,want);ready[p]=true
 end
 task.spawn(function()
  if not studio then
   for attempt=1,5 do
    local ok,value=pcall(entries.GetAsync,entries,game.PrivateServerId)
    if ok and type(value)=='table' then entry=value;break end
    task.wait(attempt)
   end
   if entry and Role.setMap(entry.map) then
    combat:SetAttribute('RunDifficulty',Rules.DifficultyIndex[entry.difficulty] and entry.difficulty or 'Normal')
    if entry.tutorial==true then combat:SetAttribute('TutorialRun',true) end -- TutorialDirector runs it
    M.code=type(entry.code)=='string' and entry.code or nil -- for rejoin records
   else bad=true;entry=nil;warn('MatchService: no usable match entry for',game.PrivateServerId) end
  end
  Players.PlayerAdded:Connect(admit)
  for _,p in Players:GetPlayers() do task.spawn(admit,p) end
  -- Wave 1 starts once every listed member is in the arena with their loading screen gone
  -- (ClientLoaded, from the client's RunAction 'Loaded'). After PARTY_WAIT it stops waiting for
  -- members who never arrived, but still waits (up to LOAD_WAIT) for those here whose screen is
  -- up. A run member is in the arena as soon as their character spawns, which is up to ~15 s
  -- before their screen clears: zombies used to reach them behind it (2026-10-03). The tutorial
  -- then gives Eggbert's welcome line WELCOME_SECONDS before the zombies come.
  while not bad do
   task.wait(.5)
   local expected,arrived,loaded=0,0,0
   local function count(p) if Shop.isMember(p) then arrived+=1;if p:GetAttribute('ClientLoaded')==true then loaded+=1 end end end
   if entry then for id in entry.members do expected+=1;local p=Players:GetPlayerByUserId(tonumber(id));if p and ready[p] then count(p) end end
   else for p in ready do if p.Parent==Players then expected+=1;count(p) end end end
   local waited=os.clock()-(firstArrival or os.clock())
   if arrived>0 and (loaded>=expected or waited>=PARTY_WAIT and loaded>=arrived or waited>=LOAD_WAIT) then
    if combat:GetAttribute('TutorialRun')==true then task.wait(Tutorial.WELCOME_SECONDS) end
    Shop.startFirstWave();break
   end
  end
 end)
end

return M
