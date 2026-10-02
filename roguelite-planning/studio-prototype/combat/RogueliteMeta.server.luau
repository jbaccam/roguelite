-- Robux purchases, saved profile actions and the run death flow (revive / give up).
-- Server authority only: clients request; receipts, eligibility and grants are checked here.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Market=game:GetService('MarketplaceService')
local Policy=game:GetService('PolicyService')
local Tags=game:GetService('CollectionService')
local Http=game:GetService('HttpService')
local SSS=game:GetService('ServerScriptService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Config=require(combat:WaitForChild('MonetizationConfig'))
local Chests=require(combat:WaitForChild('ChestConfig'))
local Profiles=require(SSS:WaitForChild('ProfileService'))
local Shop=require(SSS:WaitForChild('ShopService'))
local Characters=require(SSS:WaitForChild('CharacterService'))
local Effects=require(SSS:WaitForChild('CombatEffectsService'))
local Stats=require(combat:WaitForChild('CharacterStats'))
local Admin=require(combat:WaitForChild('AdminConfig'))
local Role=require(SSS:WaitForChild('ServerRole'))
local Match=require(SSS:WaitForChild('MatchService'))
local studio=RunService:IsStudio()
-- Admin panel emeralds (developers only): add or set. CharacterService checks the developer and
-- the numbers. In Studio the profile is in memory; on a live server this is a real, saved change
-- to the developer's own account. Grants count as earned; Robux emeralds are clamped to the balance.
Characters.onPracticeEmeralds=function(p,mode,amount)
 local d=Admin.isAdmin(p) and Profiles.get(p);if not d then return false end
 -- Add never cuts a balance already above 1e7 (from Robux) down to the cap; Set stays 0..1e7.
 if mode=='Set' then d.emeralds=math.clamp(amount,0,1e7)
 else d.emeralds=math.clamp(d.emeralds+amount,0,math.max(1e7,d.emeralds)) end
 d.bought=math.min(d.bought or 0,d.emeralds)
 Profiles.publish(p);return true
end

-- Remote events are sandboxed so the sandboxed in-run UI (ShopUI, LevelUpUI) can use them.
local function remote(name,class)
 local r=combat:FindFirstChild(name) or Instance.new(class)
 if r:IsA('RemoteEvent') then
  r.Sandboxed=true
  r.Capabilities=SecurityCapabilities.new(Enum.SecurityCapability.Basic,Enum.SecurityCapability.RemoteEvent)
 end
 r.Name=name;r.Parent=combat;return r
end
local purchaseRequest=remote('PurchaseRequest','RemoteEvent')
local purchaseResult=remote('PurchaseResult','RemoteEvent')
local runAction=remote('RunAction','RemoteEvent')
local profileAction=remote('ProfileAction','RemoteFunction')

-- Paid random items (rerolls, emeralds spent on chests) are hidden where restricted.
-- nil until PolicyService answers; callers treat nil as restricted (restricted[p]~=false), so
-- nothing random can be bought in the moment between joining and the answer.
local restricted={}
local function checkPolicy(p)
 local ok,info=pcall(Policy.GetPolicyInfoForPlayerAsync,Policy,p)
 restricted[p]=not ok or info.ArePaidRandomItemsRestricted==true
 p:SetAttribute('PaidRandomRestricted',restricted[p])
end

-- Death flow ----------------------------------------------------------------------
-- The run's map is the combat attribute RunMap (Pine Valley when unset or unknown).
-- Required before runMap: a local declared after it would be a nil global inside it.
local RunSetupRules=require(game.ReplicatedStorage:WaitForChild('RunSetupRules'))
local Analytics=require(SSS:WaitForChild('RunAnalytics')) -- unsandboxed, like this script
local function runMap() local id=combat:GetAttribute('RunMap');return RunSetupRules.MapIndex[id] and id or 'PineValley' end
local down,revivesUsed={},{}
local rise -- defined with revive below; downed teammates also rise at a wave's end
-- ShopService (required above) creates this folder, so looking it up here cannot deadlock.
local runState=game.ReplicatedStorage:WaitForChild('RogueliteRunState')
-- Harder difficulties pay more emeralds; wins and best waves are saved per map and difficulty.
local function difficulty() return combat:GetAttribute('RunDifficulty') or 'Normal' end
local function emeraldsFor(wave,map) return RunSetupRules.runEmeralds(RunSetupRules.MapIndex[map or runMap()],difficulty(),wave) end
-- What one stint of a run has earned while playing `wave`: the run's payout so far minus what it
-- already stood at when the player joined, so joining a run late never pays for missed waves.
local function stintEmeralds(map,joined,wave) return math.max(0,emeraldsFor(wave,map)-emeraldsFor(joined or 1,map)) end
-- The end of one player's run, for the results screen (RunResultsUI reads the RunResult attribute):
-- outcome Victory (they reached wave 20, Endless included), Defeat or Left. Built before the run
-- resets, so it shows the build they ended with. runInfo keeps what only a wave clear knows: the
-- best wave before this stint (NEW BEST) and a first-win bonus paid during it.
local runInfo={} -- player -> {stint,prevBest,firstWin}
local RETURN_SECONDS=20 -- Back to Lobby happens on its own after this
local returning={} -- player -> server time of their automatic Back to Lobby
local function setResult(p,outcome,map,stint,cleared,test)
 local key=RunSetupRules.runKey(map,difficulty())
 local info=runInfo[p];if info and info.stint~=stint then info=nil end
 local best=Profiles.bestWave(p,key)
 local s=Shop.states[p];local cs=Characters.states[p]
 local weapons,items={},{}
 if cs then for i=1,6 do local f=cs.folder:FindFirstChild('Slot'..i);local id=f and f:GetAttribute('WeaponId') or ''
  if id~='' then table.insert(weapons,{id=id,tier=f:GetAttribute('Tier') or 1}) end end end
 for _,it in s and s.items or {} do table.insert(items,{id=it.id,count=it.count}) end
 local at=workspace:GetServerTimeNow()+RETURN_SECONDS;returning[p]=at
 p:SetAttribute('RunResult',Http:JSONEncode({run=Shop.runId,outcome=outcome,map=map,
  mapName=RunSetupRules.Maps[RunSetupRules.MapIndex[map] or 1].name,difficulty=difficulty(),waves=cleared,
  level=s and s.level or 1,emeralds=test and 0 or Profiles.stintPaid(p,stint),firstWin=not test and info and info.firstWin or 0,
  newBest=not test and info~=nil and cleared>info.prevBest,best=best,winWave=RunSetupRules.WinWave,
  weapons=weapons,items=items,test=test==true,returnAt=at}))
end
-- Quest progress (ProfileService). Guarded so this script still runs beside an older ProfileService.
local function questEvent(p,stat,n) if Profiles.questEvent then Profiles.questEvent(p,stat,n) end end
local function questRun(p,stint) if Profiles.questRun then Profiles.questRun(p,stint) end end
-- Plan K quest stats from the run: level-ups, shards picked up and shop buys (ShopService hooks),
-- damage dealt (CombatEffectsService.listenDamage) and each minute in a run. The hooks run inside
-- the sandboxed ShopService / CombatEffectsService, so they only add to these tallies; this loop
-- sends them to quests once a second. Members of the run only; questEvent skips test runs.
local questTally={levels={},shards={},buys={},damage={}}
local function tally(stat,p,n) if Shop.members[p] then local t=questTally[stat];t[p]=(t[p] or 0)+n end end
Shop.onLevelUp=function(p,n) tally('levels',p,n) end
Shop.onShards=function(p,n) tally('shards',p,n) end
Shop.onBuy=function(p) tally('buys',p,1) end
if Effects.listenDamage then Effects.listenDamage(function(owner,_,actual) tally('damage',owner,actual) end) end -- plan J's hook; absent in older copies
task.spawn(function()
 local minuteAt=os.clock()+60
 while true do
  task.wait(1)
  for stat,t in questTally do
   for p,n in t do t[p]=nil;if Shop.members[p] then questEvent(p,stat,math.floor(n)) end end
  end
  if os.clock()>=minuteAt then minuteAt+=60;if combat:GetAttribute('RunPaused')~=true then for p in Shop.members do questEvent(p,'minutes',1) end end end -- plan L: paused minutes don't count
 end
end)
-- Plan K quest stats from the run: level-ups, shards picked up and shop buys (ShopService hooks),
-- damage dealt (CombatEffectsService.listenDamage) and each minute in a run. The hooks run inside
-- the sandboxed ShopService / CombatEffectsService, so they only add to these tallies; this loop
-- sends them to quests once a second. Members of the run only; questEvent skips test runs.
local questTally={levels={},shards={},buys={},damage={}}
local function tally(stat,p,n) if Shop.members[p] then local t=questTally[stat];t[p]=(t[p] or 0)+n end end
Shop.onLevelUp=function(p,n) tally('levels',p,n) end
Shop.onShards=function(p,n) tally('shards',p,n) end
Shop.onBuy=function(p) tally('buys',p,1) end
if Effects.listenDamage then Effects.listenDamage(function(owner,_,actual) tally('damage',owner,actual) end) end -- plan J's hook; absent in older copies
task.spawn(function()
 local minuteAt=os.clock()+60
 while true do
  task.wait(1)
  for stat,t in questTally do
   for p,n in t do t[p]=nil;if Shop.members[p] then questEvent(p,stat,math.floor(n)) end end
  end
  if os.clock()>=minuteAt then minuteAt+=60;for p in Shop.members do questEvent(p,'minutes',1) end end
 end
end)
-- Each cleared wave saves progress right away, so nothing waits on the death screen's Give Up:
-- the best wave, the win at wave 20 with its first-win bonus, and the run emeralds earned so far
-- (paid as they're reached; ProfileService.settleRun pays each stint's emeralds once). Leaving,
-- disconnecting or a server shutting down then never loses a reward. Downed players are paid up
-- to the wave they fell on when they give up. Past wave 20 the run keeps going (Endless).
Shop.onWaveCleared=function(wavesPassed)
 local map=runMap();local index=RunSetupRules.MapIndex[map]
 local key=RunSetupRules.runKey(map,difficulty())
 for p,m in Shop.members do
  -- The best wave before this stint is read before this clear can raise it (NEW BEST on results).
  local info=runInfo[p]
  if not info or info.stint~=m.stint then info={stint=m.stint,prevBest=Profiles.bestWave(p,key),firstWin=0};runInfo[p]=info end
  local bonus=Profiles.recordProgress(p,key,wavesPassed,RunSetupRules.firstWinEmeralds(index,difficulty()))
  if bonus>0 then info.firstWin=bonus end
  if down[p] then continue end
  -- Quests: a wave survived; the stint's first cleared wave counts a run; wave 20 is a win.
  questRun(p,m.stint);questEvent(p,'waves',1)
  if wavesPassed==RunSetupRules.WinWave then questEvent(p,'wins',1) end
  if wavesPassed==10 then questEvent(p,'deepRuns',1) end -- Reach Wave 10 in One Run
  local earned=stintEmeralds(map,m.joined,Shop.wave)
  Analytics.earned(p,Profiles.settleRun(p,m.stint,key,wavesPassed,earned))
  if wavesPassed==RunSetupRules.WinWave and not Admin.isTestRun() then
   Shop.publish(p,'VICTORY! Keep going in Endless, or LEAVE RUN to take your rewards')
  end
 end
 -- The run is won from here on (the shop's victory banner); Endless keeps the same loop.
 if wavesPassed>=RunSetupRules.WinWave then runState:SetAttribute('Won',true) end
 -- Downed teammates come back for the shop with their build, at the map's spawn and full health
 -- (LOBBY_AND_MATCH_SERVERS.md §4). Spawned: respawning yields, and this runs inside finishWave.
 local spawn=Role.playerSpawn();local list={}
 for p in Shop.members do if down[p] then table.insert(list,p) end end
 for _,p in list do task.spawn(rise,p,spawn and spawn.Position or down[p].position,1) end
end
-- Quest kills (QuestService), counted like the leaderboard's: real runs in Combat, credited to the
-- last player to hit (LastDamageUserId), never practice targets. A map boss counts for every
-- member of the run. Kills with Utility weapons also count toward Handy Work.
local Death=require(combat:WaitForChild('ZombieDeath'))
local Weapons=require(combat:WaitForChild('WeaponCatalog'))
Death.onDeath=function(npc)
 if not Profiles.questEvent then return end
 if Shop.phase~='Combat' or Admin.isTestRun() or npc:GetAttribute('PracticeTarget') or npc:GetAttribute('BossPractice') then return end
 if npc:GetAttribute('IsMapBoss') then for p in Shop.members do questEvent(p,'bosses',1) end end
 if not Tags:HasTag(npc,'RogueliteZombie') then return end
 local id=npc:GetAttribute('LastDamageUserId')
 local p=type(id)=='number' and Players:GetPlayerByUserId(id) or nil
 if not p or not Shop.states[p] then return end
 questEvent(p,'kills',1)
 local weapon=Weapons.ById[npc:GetAttribute('LastWeaponId')]
 if weapon and weapon.utility then questEvent(p,'utilityKills',1) end
 if weapon then questEvent(p,weapon.kind=='Melee' and 'meleeKills' or 'rangedKills',1) end -- Ranged, Blast and Spread count as ranged
end
local function livingInRun()
 local n=0
 for p in Shop.members do local h=p.Character and p.Character:FindFirstChildOfClass('Humanoid');if h and h.Health>0 and not down[p] then n+=1 end end
 return n
end
local function clearDown(p)
 down[p]=nil;p:SetAttribute('RunDown',nil);p:SetAttribute('DeathInfo',nil)
end
-- Everyone in the run is down (LOBBY_AND_MATCH_SERVERS.md §4): the wave stays paused and there are
-- LAST_STAND seconds to revive before the run ends as a Defeat. Solo players reach it on death. An
-- open Revive purchase prompt holds the clock at 5 s or more (prompting).
local LAST_STAND=10
local lastStandEnds -- server time, while everyone is down
local prompting={} -- player -> server time their Revive purchase prompt opened, while it is open
local function setLastStand(ends)
 lastStandEnds=ends;runState:SetAttribute('LastStandEndsAt',ends)
end
-- Phoenix 4-piece (armor set perk, CharacterStats.ArmorSets): once per run the first death rises
-- right away at the death spot with half health and a fire blast; no death screen, and the paid
-- revive stays unused for a later death. phoenixUsed resets with the run (giveUp, wave 1).
local phoenixUsed={}
local function phoenix(p,at)
 local cs=Characters.states[p];local blast=cs and cs.perks and cs.perks.PhoenixBlast
 if not blast or phoenixUsed[p] or p:GetAttribute('LobbyPreviewActive') then return false end
 phoenixUsed[p]=true;p:SetAttribute('PhoenixUsed',true)
 p:SetAttribute('HoldRespawn',true) -- keep AvatarNormalizer's normal respawn away
 task.delay(.6,function()
  if p.Parent~=Players or not Shop.states[p] or down[p] then return end
  rise(p,at,Stats.ArmorPerks.PhoenixHealth,function(root)
   Effects.armorBlast(p,root.Position,Stats.ArmorPerks.PhoenixRadius,blast)
  end)
 end)
 return true
end
local function onDied(p,character)
 -- Only run members go down; a lobby fall just respawns.
 local m=Shop.members[p]
 if not m or not Shop.states[p] or down[p] then return end
 local root=character:FindFirstChild('HumanoidRootPart')
 if phoenix(p,root and root.Position or Vector3.zero) then return end
 local s=Shop.states[p]
 -- test: this player went down during a test run. It stays true even if resetRun clears the run flag
 -- before they give up, so a later give-up still pays nothing. The stint is kept so a give-up
 -- after the run was reset still settles the run they fell in.
 down[p]={position=root and root.Position or Vector3.zero,wave=Shop.wave,map=runMap(),test=Admin.isTestRun(),stint=m.stint,joined=m.joined}
 p:SetAttribute('HoldRespawn',true)
 -- A test run (the admin panel was used) pays nothing, so the death screen shows 0 emeralds.
 -- revive: which revive of this run REVIVE would buy; its price and the one after (prices double).
 local n=(revivesUsed[p] or 0)+1
 p:SetAttribute('DeathInfo',Http:JSONEncode({wave=Shop.wave,level=s.level,emeralds=Admin.isTestRun() and 0 or stintEmeralds(runMap(),m.joined,Shop.wave),map=RunSetupRules.Maps[RunSetupRules.MapIndex[runMap()]].name,
  revive=n,revivePrice=Config.Products[Config.reviveKey(n)].robux,nextRevivePrice=Config.Products[Config.reviveKey(n+1)].robux}))
 p:SetAttribute('RunDown',true)
 Analytics.died(p,Shop.wave)
 if livingInRun()==0 then Shop.pause();if not lastStandEnds and Shop.phase=='Combat' then setLastStand(workspace:GetServerTimeNow()+LAST_STAND) end end
end
-- The flag can be set after a player went down: their death screen shows 0 and their give-up pays nothing.
runState:GetAttributeChangedSignal('AdminTestRun'):Connect(function()
 if runState:GetAttribute('AdminTestRun')~=true then return end
 for p,d in down do
  d.test=true
  local ok,info=pcall(function() return Http:JSONDecode(p:GetAttribute('DeathInfo')) end)
  if ok and type(info)=='table' then info.emeralds=0;p:SetAttribute('DeathInfo',Http:JSONEncode(info)) end
 end
end)
-- A new run (the wave counter goes back to 1) gets its Phoenix rise back.
runState:GetAttributeChangedSignal('Wave'):Connect(function()
 if runState:GetAttribute('Wave')~=1 then return end
 for q in phoenixUsed do if not down[q] then phoenixUsed[q]=nil;q:SetAttribute('PhoenixUsed',nil) end end
 for q in revivesUsed do if not down[q] then revivesUsed[q]=0 end end -- and revives start at 65 R$ again
 runState:SetAttribute('Won',nil) -- and isn't won yet
end)
local function watch(p)
 p.CharacterAdded:Connect(function(character)
  local h=character:WaitForChild('Humanoid',10)
  if h then h.Died:Connect(function() onDied(p,character) end) end
 end)
end
local respawn=SSS:WaitForChild('AvatarNormalizer'):WaitForChild('RespawnPlayer')
-- No limit per run; each revive costs more (Config.reviveKey).
local function canRevive(p) return down[p]~=nil end
-- Respawn at `at` with `health` (fraction of max), a short shield and nearby zombies pushed back.
-- beforePush(root) runs once the body is placed (the Phoenix blast), before the push.
rise=function(p,at,health,beforePush)
 local d=down[p]
 local character=respawn:Invoke(p)
 -- Their run ended while the body loaded (Leave Run, or the last stand ran out): they're on the
 -- results screen, so the new body goes again and the respawn hold stays.
 if d and down[p]~=d then
  if character and p.Character==character then p.Character=nil;character:Destroy() end
  return
 end
 clearDown(p);p:SetAttribute('HoldRespawn',false)
 task.spawn(function()
  if not character then return end
  local h=character:WaitForChild('Humanoid',10);local root=character:WaitForChild('HumanoidRootPart',10)
  if not h or not root then return end
  -- CharacterService sets full health when its spawn setup finishes (it tags CombatClass);
  -- apply the revive only after that, or it would be overwritten.
  local t0=os.clock()
  while character.Parent and not character:GetAttribute('CombatClass') and os.clock()-t0<5 do task.wait(.05) end
  task.wait(.15)
  if not character.Parent or h.Health<=0 then return end
  character:PivotTo(CFrame.new(at+Vector3.new(0,3,0)))
  h.Health=math.max(1,h.MaxHealth*health)
  -- Named, so the SpawnLocation's own spawn shield timer cannot remove it early.
  for _,f in character:GetChildren() do if f:IsA('ForceField') then f:Destroy() end end
  local shield=Instance.new('ForceField');shield.Name='ReviveShield';shield.Parent=character
  task.delay(Config.ReviveInvulnerableSeconds,function() if shield.Parent then shield:Destroy() end end)
  if beforePush then beforePush(root) end
  for _,npc in Tags:GetTagged('RogueliteZombie') do
   local part=npc:IsA('Model') and npc.PrimaryPart
   if part and npc:IsDescendantOf(workspace) and not npc:GetAttribute('LobbyDummy') then
    local offset=part.Position-at;offset=Vector3.new(offset.X,0,offset.Z)
    if offset.Magnitude<Config.RevivePushRadius then
     local dir=offset.Magnitude>.1 and offset.Unit or Vector3.new(1,0,0)
     npc:PivotTo(npc:GetPivot()+dir*Config.RevivePushDistance)
    end
   end
  end
 end)
end
local function revive(p)
 if not canRevive(p) then return false end
 local at=down[p].position;revivesUsed[p]=(revivesUsed[p] or 0)+1
 rise(p,at,Config.ReviveHealth)
 Shop.resume()
 if lastStandEnds then setLastStand(nil) end
 Analytics.revived(p,revivesUsed[p])
 return true
end
-- One player's run ends (LOBBY_AND_MATCH_SERVERS.md §5): Leave Run (between waves, or from the
-- death screen) or a Defeat when the last stand runs out. Settles the stint's emeralds up to the
-- wave reached (usually already paid at the last clear), shows the results and takes them out of
-- the run, while anyone else plays on. They stay out of the arena (dead, or with no body after
-- leaving between waves, so nothing can reach it) until Back to Lobby (returnToLobby).
local function finish(p,outcome)
 local d=down[p];local m=Shop.members[p]
 local stint=d and d.stint or m and m.stint;if not stint then return false end
 local map=d and d.map or runMap();local wave=d and d.wave or Shop.wave
 local test=(d and d.test) or Admin.isTestRun()
 local cleared=math.max(0,wave-1)
 if not test then Analytics.earned(p,Profiles.settleRun(p,stint,RunSetupRules.runKey(map,difficulty()),cleared,stintEmeralds(map,d and d.joined or m.joined,wave))) end
 if cleared>=RunSetupRules.WinWave then outcome='Victory' end -- won, then left or fell in Endless
 setResult(p,outcome,map,stint,cleared,test)
 Analytics.runEnded(p,outcome,map,difficulty(),wave,cleared,test)
 clearDown(p);revivesUsed[p]=0;phoenixUsed[p]=nil;p:SetAttribute('PhoenixUsed',nil);prompting[p]=nil
 Shop.leave(p)
 p:SetAttribute('HoldRespawn',true)
 local character=p.Character;local h=character and character:FindFirstChildOfClass('Humanoid')
 if h and h.Health>0 then p.Character=nil;character:Destroy() end
 return true
end
-- After players leave: an empty run starts over (a fresh wave 1 for whoever comes next); a run
-- whose only members are down goes into its last stand.
local function afterLeave()
 if next(Shop.members)==nil then
  setLastStand(nil);Shop.resetRun();for q in revivesUsed do revivesUsed[q]=0 end
  for q in phoenixUsed do phoenixUsed[q]=nil;q:SetAttribute('PhoenixUsed',nil) end
 elseif livingInRun()==0 and next(down)~=nil and not lastStandEnds and Shop.phase=='Combat' then
  Shop.pause();setLastStand(workspace:GetServerTimeNow()+LAST_STAND)
 end
end
-- Leave Run: from the death screen any time, or alive between waves (not mid-wave). A downed
-- player whose teammates still fight has Left; the last one standing (or solo) is a Defeat.
local function leaveRun(p)
 if down[p] then finish(p,livingInRun()>0 and 'Left' or 'Defeat')
 elseif Shop.members[p] and Shop.phase=='Shop' then
  local h=p.Character and p.Character:FindFirstChildOfClass('Humanoid')
  if not h or h.Health<=0 then return false end
  finish(p,'Left')
 else return false end
 afterLeave()
 return true
end
-- Back to Lobby (the results screen's button, or RETURN_SECONDS after the results). A match server
-- teleports the group to a public lobby; Studio's Combined role walks them into the lobby here.
-- A Studio Match, or a teleport that can't start, puts them back in the arena instead.
local returnTries={} -- player -> failed Back to Lobby attempts on a live match server
local function returnToLobby(list)
 for _,p in list do returning[p]=nil end
 if Role.get()=='Match' and not studio then
  Match.toLobby(list)
  -- Anyone whose save couldn't be handed over (or whose teleport couldn't start) is still loaded
  -- here: try again in 5 s, and after three tries play on in this match instead.
  local stay={}
  for _,p in list do
   if p.Parent==Players and Profiles.get(p) then
    returnTries[p]=(returnTries[p] or 0)+1
    if returnTries[p]<3 then returning[p]=workspace:GetServerTimeNow()+5 else table.insert(stay,p) end
   else returnTries[p]=nil end
  end
  list=stay
 end
 for _,p in list do
  returnTries[p]=nil
  if p.Parent~=Players then continue end
  p:SetAttribute('RunResult',nil)
  if Role.get()~='Match' then p:SetAttribute('StudioArea','Lobby') end -- the lobby's spawn handler places them
  p:SetAttribute('HoldRespawn',false) -- a body that fell respawns through AvatarNormalizer
  if not (p.Character and p.Character:FindFirstChildOfClass('Humanoid')) then respawn:Invoke(p) end
 end
end
-- A teleport that failed after it started (MatchService): back into this match.
if Role.get()=='Match' then
 Match.onTeleportFailed=function(p)
  p:SetAttribute('RunResult',nil)
  if not (p.Character and p.Character:FindFirstChildOfClass('Humanoid')) then respawn:Invoke(p) end
 end
end
-- Play Again (plan J item 9): the results screen's PLAY AGAIN. Everyone who presses it goes back
-- into a fresh run on this server together: same map, difficulty and loadouts, wave 1. It starts
-- once nobody is still playing the old run and everyone else on results has decided (pressed it,
-- or gone back to the lobby, which their 20 s clock does on its own). PlayAgainStatus tells the
-- waiting screen why it waits. Example: Ana presses it while Ben still reads his results; Ana sees
-- "Waiting for Ben"; Ben presses it too (or leaves) and both are back at the spawn for wave 1.
local again={} -- player -> true: pressed PLAY AGAIN and waiting
local function againStatus(p,text) if p:GetAttribute('PlayAgainStatus')~=text then p:SetAttribute('PlayAgainStatus',text) end end
local function startAgain()
 local list={}
 for p in again do if p.Parent==Players then table.insert(list,p) end end
 table.clear(again)
 -- Always a clean run: the old one may have emptied through a disconnect, which doesn't reset it.
 setLastStand(nil);Shop.resetRun()
 for q in revivesUsed do revivesUsed[q]=0 end
 for q in phoenixUsed do phoenixUsed[q]=nil;q:SetAttribute('PhoenixUsed',nil) end
 for _,p in list do
  returning[p]=nil;returnTries[p]=nil
  p:SetAttribute('PlayAgainStatus',nil);p:SetAttribute('RunResult',nil)
  if Role.get()~='Match' then p:SetAttribute('StudioArea','Arena') end
  p:SetAttribute('HoldRespawn',false)
 end
 -- Fresh bodies at the map's spawn (respawning yields), then wave 1 once all of them are in the
 -- run, or after 15 s.
 task.spawn(function()
  local spawn=Role.playerSpawn()
  for _,p in list do
   if p.Parent~=Players then continue end
   local character=respawn:Invoke(p)
   if character and spawn then character:PivotTo(CFrame.new(spawn.Position+Vector3.new((math.random()-.5)*6,4,(math.random()-.5)*6))) end
  end
  local t0=os.clock()
  while os.clock()-t0<15 do
   local total,inRun=0,0
   for _,p in list do if p.Parent==Players then total+=1;if Shop.isMember(p) then inRun+=1 end end end
   if total==0 then return end
   if inRun>=total then break end
   task.wait(.25)
  end
  Shop.startFirstWave()
 end)
end
local function checkAgain()
 for p in again do if p.Parent~=Players or not p:GetAttribute('RunResult') then again[p]=nil end end
 if next(again)==nil then return end
 if next(Shop.members)~=nil then
  for p in again do againStatus(p,'Waiting for the run to end') end
  return
 end
 local undecided={}
 for _,q in Players:GetPlayers() do if not again[q] and q:GetAttribute('RunResult') then table.insert(undecided,q.DisplayName) end end
 if #undecided>0 then
  for p in again do againStatus(p,'Waiting for '..table.concat(undecided,', ')) end
  return
 end
 startAgain()
end
local function playAgain(p,on)
 if not p:GetAttribute('RunResult') then return end
 if on then
  again[p]=true;returning[p]=nil -- waits here instead of going back on its own
  againStatus(p,'Starting...')
 else
  again[p]=nil;p:SetAttribute('PlayAgainStatus',nil)
  -- Cancelled: back to the lobby in 10 s, and the results screen's countdown says so.
  local at=workspace:GetServerTimeNow()+10;returning[p]=at
  local ok,info=pcall(Http.JSONDecode,Http,p:GetAttribute('RunResult') or '')
  if ok and type(info)=='table' then info.returnAt=at;p:SetAttribute('RunResult',Http:JSONEncode(info)) end
 end
 checkAgain()
end
-- Restart (the pause screen's RESTART, plan L; solo only): this run ends as Left (rewards so far
-- kept, as with Leave Run) and the player goes straight into Play Again, with no results screen.
local function restart(p)
 if not Shop.members[p] or Shop.memberCount()~=1 then return false end
 local h=p.Character and p.Character:FindFirstChildOfClass('Humanoid')
 if not down[p] and (not h or h.Health<=0) then return false end
 if not finish(p,'Left') then return false end
 afterLeave()
 again[p]=true;returning[p]=nil
 checkAgain()
 return true
end
-- Rejoin, lobby side (plan J item 9): a run this player dropped out of that is still going shows
-- on their screen as RejoinOffer (RunResultsUI); REJOIN sends them back to it (MatchService).
local function offerRejoin(p)
 if Role.get()~='Lobby' then return end
 local rec=Match.rejoinOffer and Match.rejoinOffer(p)
 if not rec or p.Parent~=Players then return end
 local index=RunSetupRules.MapIndex[rec.map]
 p:SetAttribute('RejoinOffer',Http:JSONEncode({mapName=index and RunSetupRules.Maps[index].name or 'your run',difficulty=rec.difficulty or 'Normal',wave=rec.wave or 1}))
end
local lastRunAction={}
local useStored -- defined with the purchase code below
runAction.OnServerEvent:Connect(function(p,action,arg)
 if action=='LeaveRun' or action=='GiveUp' then leaveRun(p)
 elseif action=='ReturnToLobby' then if returning[p] or again[p] then again[p]=nil;p:SetAttribute('PlayAgainStatus',nil);returnToLobby({p}) end
 elseif action=='PlayAgain' or action=='Restart' or action=='Rejoin' or action=='RejoinDismiss' then
  if os.clock()-(lastRunAction[p] or 0)<.5 then return end;lastRunAction[p]=os.clock()
  if action=='PlayAgain' then playAgain(p,arg~=false)
  elseif action=='Restart' then restart(p)
  elseif action=='RejoinDismiss' then p:SetAttribute('RejoinOffer',nil);if Match.dismissRejoin then Match.dismissRejoin(p) end
  elseif p:GetAttribute('RejoinOffer') and Match.rejoin then
   local ok,why=Match.rejoin(p)
   if not ok then
    local info=Http:JSONDecode(p:GetAttribute('RejoinOffer'));info.error=why or "Couldn't rejoin"
    p:SetAttribute('RejoinOffer',Http:JSONEncode(info))
   end
  end
 elseif action=='UseReroll' or action=='UseBanish' then useStored(p,action,arg) end
end)
-- The run's clocks: the last stand, automatic Back to Lobby, the shop's "keep N emeralds".
local sinceClock=0
game:GetService('RunService').Heartbeat:Connect(function(dt)
 sinceClock+=dt;if sinceClock<.25 then return end;sinceClock=0
 local now=workspace:GetServerTimeNow()
 -- Everyone still in the run is down, however it happened (a death, or the last one standing
 -- leaving or disconnecting): the last stand.
 if not lastStandEnds and next(down)~=nil and livingInRun()==0 and Shop.phase=='Combat' then Shop.pause();setLastStand(now+LAST_STAND) end
 -- A Revive prompt left open for a minute stops holding the clock.
 for q,at in prompting do if now-at>60 then prompting[q]=nil end end
 if lastStandEnds then
  -- Someone is standing again (a Phoenix rise, a late joiner) or nobody is left down: the wave
  -- clock runs again.
  if livingInRun()>0 or next(down)==nil then setLastStand(nil);Shop.resume()
  elseif next(prompting) then
   -- A Revive prompt is open: the clock waits, with 5 s left once it closes.
   if lastStandEnds<now+5 then setLastStand(now+5) end
  elseif now>=lastStandEnds then
   setLastStand(nil)
   local list={};for p in Shop.members do if down[p] then table.insert(list,p) end end
   for _,p in list do finish(p,'Defeat') end
   afterLeave()
  end
 end
 local due={};for p,at in returning do if now>=at then table.insert(due,p) end end
 if #due>0 then returnToLobby(due) end
 checkAgain() -- Play Again starts when the old run is over and everyone on results has decided
 for p,m in Shop.members do
  local paid=Admin.isTestRun() and 0 or Profiles.stintPaid(p,m.stint)
  if p:GetAttribute('RunEmeralds')~=paid then p:SetAttribute('RunEmeralds',paid) end
  -- A stint is a run for analytics once its first wave is under way.
  if Shop.phase=='Combat' then Analytics.runStarted(p,m.stint,runMap(),difficulty(),m.joined,Shop.memberCount()) end
 end
end)
-- Wave clears for analytics (the progression funnel), after the rewards above.
Shop.onWaveCleared=function(wavesPassed)
 for p in Shop.members do if not down[p] then Analytics.waveCleared(p,wavesPassed) end end
end

-- Purchases -----------------------------------------------------------------------
local lastRequest={}
local pendingArg={} -- e.g. which level-up card a bought Banish targets
local function reply(p,key,ok,message) purchaseResult:FireClient(p,key,ok,message) end
-- Returns true when the product can be bought right now (checked before prompting).
local function eligible(p,key,arg)
 local product=Config.Products[key];local d=Profiles.get(p)
 if not product then return false,'Unknown product' end
 if not d then return false,'Profile still loading' end
 if product.random and restricted[p]~=false then return false,'Not available in your region' end
 if product.revive then return canRevive(p),'No revive available right now' end
 if key=='ShopReroll' or key=='UpgradeReroll' then return Shop.states[p]~=nil,'Only during a run' end
 if product.oneTime and d[product.oneTime] then return false,'Already purchased' end
 if product.class and d.classes[product.class] then return false,'Already unlocked' end
 if product.godly then
  if d.bundles[key] then return false,'Already purchased' end
  if not Profiles.weaponIdByName(product.godly) then return false,'Coming soon' end
 end
 if product.godlyPick then
  if d.bundles[key] then return false,'Already purchased' end
  local pick=arg and Config.GodlyWeapons[arg]
  if not pick then return false,'Pick a Godly weapon first' end
  if not Profiles.weaponIdByName(pick[1]) then return false,'Coming soon' end
 end
 return true
end
-- Grants run inside ProcessReceipt (or a Studio simulation). Return true only when delivered.
-- In-run products that can no longer be used are kept as stored rerolls/banishes (or emeralds).
local grants={}
-- Every price step grants the same revive. One that can't be used any more (the wave ended and
-- teammates raised the player, or the run is over) is paid back at its Robux value in emeralds:
-- 65 R$ -> 666, 1040 R$ -> 10,666.
local function grantRevive(p,key)
 if revive(p) then return true end
 return Profiles.grant(p,{emeralds=Config.fairEmeralds(Config.Products[key].robux),paid=true})
end
for i=1,Config.ReviveSteps do local key=Config.reviveKey(i);grants[key]=function(p) return grantRevive(p,key) end end
function grants.ShopReroll(p) return Shop.paidReroll(p,'Shop') or Profiles.grant(p,{rerolls=1}) end
function grants.UpgradeReroll(p) return Shop.paidReroll(p,'Upgrade') or Profiles.grant(p,{rerolls=1}) end
-- A bought banish is saved; the player then clicks the card to remove (RunAction UseBanish).
function grants.Banish(p) return Profiles.grant(p,{banishes=1}) end
local function grantProduct(p,key)
 local product=Config.Products[key]
 if grants[key] then return grants[key](p) end
 -- Godly bundle / Godly Starter: never deliver without its weapon (the receipt stays unprocessed
 -- and retries). The Starter's weapon is the pick saved on the profile before the prompt.
 local godlyName=product.godly or product.godlyPick and Profiles.get(p).godlyPick
 local weapon=godlyName and Profiles.weaponIdByName(godlyName)
 if godlyName and not weapon then return false end
 -- paid: Robux emeralds, which regions that restrict paid random items cannot spend on chests.
 return Profiles.grant(p,{emeralds=product.emeralds,paid=true,chests=product.chests,class=product.class,rerolls=product.rerolls,banishes=product.banishes,
  signatureUpgrades=product.signatureUpgrades,starterPack=product.oneTime=='starterPack',
  weapon=weapon,armorSet=product.armorSet,bundle=godlyName and key})
end
-- The rules are checked again when the receipt arrives: product IDs are public and a client can
-- prompt any of them itself, skipping PurchaseRequest. A product that can't be delivered as
-- itself (a second Starter Pack, an owned class, a cheaper revive step than this run's, a random
-- item in a restricted region) is paid out at its Robux value in emeralds instead.
local function receiptProblem(p,key)
 local product=Config.Products[key];local d=Profiles.get(p)
 if product.random and restricted[p] then return 'Not available in your region' end
 if product.oneTime and d[product.oneTime] then return 'Already bought' end
 if product.class and d.classes[product.class] then return 'Already unlocked' end
 if (product.godly or product.godlyPick) and d.bundles[key] then return 'Already bought' end
 if product.revive then
  local step=tonumber(string.match(key,'%d+')) or 1
  if step<math.min((revivesUsed[p] or 0)+1,Config.ReviveSteps) then return 'That revive price has passed' end
 end
 return nil
end
-- One receipt at a time per player, so a grant and its save never interleave with another one.
local receiptBusy={}
local function processReceipt(p,key,purchaseId)
 -- Wait for the profile and the region answer (retried by Roblox) before deciding anything.
 if not Profiles.get(p) or restricted[p]==nil then return Enum.ProductPurchaseDecision.NotProcessedYet end
 if not Profiles.hasReceipt(p,purchaseId) then
  local product=Config.Products[key]
  local problem=receiptProblem(p,key)
  if problem then
   local n=Config.fairEmeralds(product.robux)
   if not Profiles.grant(p,{emeralds=n,paid=true}) then return Enum.ProductPurchaseDecision.NotProcessedYet end
   Profiles.addReceipt(p,purchaseId)
   reply(p,key,true,problem..' · '..n..' emeralds added instead')
  else
   local ok,granted=pcall(grantProduct,p,key)
   if not ok or not granted then warn('RogueliteMeta: grant failed',key,granted);return Enum.ProductPurchaseDecision.NotProcessedYet end
   Profiles.addReceipt(p,purchaseId)
   reply(p,key,true,product.name..' purchased')
  end
 end
 -- Acknowledge only once the grant is saved. A failed save leaves the receipt unprocessed: Roblox
 -- retries it, the remembered PurchaseId stops a second grant here, and another server (which
 -- never saw this grant) grants it once.
 if not Profiles.save(p) then return Enum.ProductPurchaseDecision.NotProcessedYet end
 return Enum.ProductPurchaseDecision.PurchaseGranted
end
Market.ProcessReceipt=function(info)
 local p=Players:GetPlayerByUserId(info.PlayerId)
 local key=Config.byProductId(info.ProductId)
 if not p or not key or not Profiles.get(p) then return Enum.ProductPurchaseDecision.NotProcessedYet end
 while receiptBusy[p] do task.wait() end
 receiptBusy[p]=true
 local ok,decision=pcall(processReceipt,p,key,info.PurchaseId)
 receiptBusy[p]=nil
 if not ok then warn('RogueliteMeta: receipt failed',decision);return Enum.ProductPurchaseDecision.NotProcessedYet end
 return decision
end
local passGrant={VIP={vip=true},QuickOpen={quickOpen=true}}
local passField={VIP='vip',QuickOpen='quickOpen'}
-- Rate limit: one request per 0.5 s and at most 20 a minute per player, so a looping client
-- can't spam prompts, analytics events or the revive hold.
local requestWindow={}
local function allowRequest(p)
 local now=os.clock()
 if now-(lastRequest[p] or -1e9)<.5 then return false end
 local w=requestWindow[p]
 if not w or now-w.start>=60 then w={start=now,count=0};requestWindow[p]=w end
 if w.count>=20 then return false end
 w.count+=1;lastRequest[p]=now
 return true
end
-- The Godly Starter pick is saved so a receipt that arrives after a rejoin still knows it, but
-- at most once per 10 s per player: a looping client can't drain the DataStore budget.
local lastPickSave,pickSaveQueued={},{}
local function savePick(p)
 if pickSaveQueued[p] then return end
 pickSaveQueued[p]=true
 task.delay(math.max(0,10-(os.clock()-(lastPickSave[p] or -1e9))),function()
  pickSaveQueued[p]=nil
  if Profiles.get(p) then lastPickSave[p]=os.clock();Profiles.save(p) end
 end)
end
purchaseRequest.OnServerEvent:Connect(function(p,key,arg)
 if type(key)~='string' or not allowRequest(p) then return end
 local pass=Config.Passes[key]
 if pass then
  local d=Profiles.get(p)
  if d and d[passField[key]] then return reply(p,key,false,'Already owned') end
  if pass.gamePassId>0 then Market:PromptGamePassPurchase(p,pass.gamePassId)
  elseif studio then Profiles.grant(p,passGrant[key]);reply(p,key,true,'Studio test: '..pass.name..' granted (not saved)')
  else reply(p,key,false,'Not on sale yet') end
  return
 end
 if type(arg)~='number' then arg=nil end
 -- Revive: the client asks for 'Revive' and the server picks this run's price step, so nobody
 -- can ask for a cheaper one.
 if key=='Revive' or Config.isRevive(key) then key=Config.reviveKey((revivesUsed[p] or 0)+1) end
 local product=Config.Products[key]
 -- Not on sale yet (no product ID) outside Studio: answer before anything else happens.
 if product and product.productId<=0 and not studio then return reply(p,key,false,'Not on sale yet') end
 local ok,why=eligible(p,key,arg)
 if not ok then return reply(p,key,false,why) end
 pendingArg[p]=pendingArg[p] or {};pendingArg[p][key]=arg
 if product.godlyPick then
  local d=Profiles.get(p);local pick=Config.GodlyWeapons[arg][1]
  if d.godlyPick~=pick then d.godlyPick=pick;savePick(p) end
 end
 -- An open Revive prompt holds the last stand's clock (prompting). Asking again while one is
 -- already open neither logs nor refreshes the hold, so re-asking can't stall the run.
 if product.revive and not prompting[p] then
  Analytics.revivePrompt(p,(revivesUsed[p] or 0)+1)
  if product.productId>0 then prompting[p]=workspace:GetServerTimeNow() end
 end
 if product.productId>0 then Market:PromptProductPurchase(p,product.productId)
 elseif studio then
  -- Studio only: simulate a successful receipt so flows can be tested. In-memory, never saved.
  if grantProduct(p,key) then reply(p,key,true,'Studio test: '..product.name..' granted (not saved)') else reply(p,key,false,'Grant failed') end
 else reply(p,key,false,'Not on sale yet') end
end)
Market.PromptProductPurchaseFinished:Connect(function(userId,productId)
 local p=Players:GetPlayerByUserId(userId)
 if p and Config.isRevive(Config.byProductId(productId)) then prompting[p]=nil end
end)
Market.PromptGamePassPurchaseFinished:Connect(function(p,id,bought)
 if not bought then return end
 for key,pass in Config.Passes do
  if pass.gamePassId>0 and id==pass.gamePassId then
   -- Saved right away; if the profile isn't loaded, checkPasses grants it on the next join.
   if Profiles.grant(p,passGrant[key]) then task.spawn(Profiles.save,p) end
   reply(p,key,true,pass.name..' unlocked')
  end
 end
end)
-- Passes bought anywhere (the website too) are checked at join, once the profile has loaded: a
-- grant before that would be dropped. Whatever is granted is saved straight away.
local function checkPasses(p)
 for _=1,120 do if Profiles.get(p) or p.Parent~=Players then break end;task.wait(.5) end
 local d=Profiles.get(p);if not d then return end
 local granted=false
 for key,pass in Config.Passes do
  if pass.gamePassId>0 and not d[passField[key]] then
   local ok,owns=pcall(Market.UserOwnsGamePassAsync,Market,p.UserId,pass.gamePassId)
   if ok and owns and Profiles.grant(p,passGrant[key]) then granted=true end
  end
 end
 if granted then Profiles.save(p) end
end

-- Stored rerolls / banishes used during a run (no Robux prompt).
local lastUse={}
useStored=function(p,action,arg)
 if os.clock()-(lastUse[p] or 0)<.3 then return end;lastUse[p]=os.clock()
 local d=Profiles.get(p);if not d or restricted[p]~=false then return end
 if action=='UseReroll' and (arg=='Shop' or arg=='Upgrade') and Shop.states[p] then
  if d.rerolls>0 and Profiles.spend(p,'rerolls') then Shop.paidReroll(p,arg) end
 elseif action=='UseBanish' and Shop.canBanish(p,arg) then
  if d.banishes>0 and Profiles.spend(p,'banishes') then Shop.banish(p,arg) end
 end
end

-- Profile actions (lobby) ---------------------------------------------------------
local lastAction={}
profileAction.OnServerInvoke=function(p,action,a,b,c)
 if type(action)~='string' or os.clock()-(lastAction[p] or 0)<.25 then return {ok=false,message='Slow down'} end
 lastAction[p]=os.clock()
 if not Profiles.get(p) then return {ok=false,message='Profile still loading'} end
 local ok,message,results
 if action=='OpenChest' and type(a)=='string' and type(b)=='number' then ok,message,results=Profiles.openChest(p,a,b)
 elseif action=='BuyChest' and type(a)=='string' and type(b)=='number' then ok,message=Profiles.buyChest(p,a,b,restricted[p]~=false)
 elseif action=='BuyEgg' and type(a)=='number' then ok,message=Profiles.buyEgg(p,a,restricted[p]~=false)
 elseif action=='OpenEgg' and type(a)=='number' then ok,message,results=Profiles.openEgg(p,a)
 elseif action=='Upgrade' and type(a)=='string' then ok,message=Profiles.upgrade(p,a)
 elseif action=='WearArmor' and type(a)=='string' and (b==nil or type(b)=='string') then ok,message=Profiles.wear(p,a,b)
 elseif action=='EquipPet' and (a==nil or (type(a)=='string' and #a<=40)) then ok,message=Profiles.equipPet(p,a) -- nil = put the pet away
 elseif action=='BuySkill' and type(a)=='string' and #a<=40 then ok,message=Profiles.buySkill(p,a)
 elseif action=='BuyClass' and type(a)=='string' then ok,message=Profiles.buyClass(p,a,Config.ClassEmeraldPrice)
 elseif action=='BuyDeal' and type(a)=='number' then ok,message,results=Profiles.buyDeal(p,a)
 elseif action=='ClaimVipChest' then ok,message=Profiles.claimVipChest(p,restricted[p]~=false)
 elseif action=='Redeem' and type(a)=='string' then ok,message=Profiles.redeem(p,a)
 elseif action=='ClaimQuest' and Profiles.claimQuest and type(a)=='number' then ok,message=Profiles.claimQuest(p,a)
 elseif action=='ClaimStreak' and Profiles.claimStreak and type(a)=='number' then ok,message=Profiles.claimStreak(p,a)
 elseif action=='ClaimRoad' and Profiles.claimRoad and type(a)=='string' and #a<=40 then ok,message=Profiles.claimRoad(p,a)
 elseif action=='ClaimUnlock' and Profiles.claimUnlock and type(a)=='string' and #a<=40 then ok,message=Profiles.claimUnlock(p,a)
 elseif action=='Refresh' then Profiles.publish(p);ok=true;message=''
 elseif action=='DevEmeralds' and studio then ok=Profiles.grant(p,{emeralds=200});message='Studio test: +200 emeralds (not saved)'
 elseif action=='DevResetSkills' and studio then ok,message=Profiles.resetSkills(p)
 else return {ok=false,message='Unknown action'} end
 return {ok=ok==true,message=message,results=results}
end

-- Rejoining the same run (plan J item 9) keeps its revive count and Phoenix rise, so dropping out
-- and back in can't reset the revive price to 65 R$.
local reviveCarry={} -- userId -> {run,revives,phoenix}
local function added(p)
 local c=reviveCarry[p.UserId];reviveCarry[p.UserId]=nil
 if c and c.run==Shop.runId then
  revivesUsed[p]=c.revives
  if c.phoenix then phoenixUsed[p]=true;p:SetAttribute('PhoenixUsed',true) end
 end
 watch(p);task.spawn(checkPolicy,p);task.spawn(checkPasses,p)
 task.delay(3,offerRejoin,p) -- a lobby offers the way back into a run they dropped out of
end
Players.PlayerAdded:Connect(added)
for _,p in Players:GetPlayers() do added(p);if p.Character then local h=p.Character:FindFirstChildOfClass('Humanoid');if h then h.Died:Connect(function() onDied(p,p.Character) end) end end end
Players.PlayerRemoving:Connect(function(p)
 if (revivesUsed[p] or 0)>0 or phoenixUsed[p] then reviveCarry[p.UserId]={run=Shop.runId,revives=revivesUsed[p] or 0,phoenix=phoenixUsed[p]} end
 down[p]=nil;revivesUsed[p]=nil;phoenixUsed[p]=nil;restricted[p]=nil;lastRequest[p]=nil;lastAction[p]=nil;pendingArg[p]=nil;lastUse[p]=nil;receiptBusy[p]=nil;requestWindow[p]=nil;lastPickSave[p]=nil
 returning[p]=nil;prompting[p]=nil;runInfo[p]=nil;returnTries[p]=nil;again[p]=nil;lastRunAction[p]=nil
 -- The last one standing left: the clock loop pauses the wave again for the downed players' last
 -- stand. A last stand already counting down keeps the wave paused.
 if livingInRun()==0 and not lastStandEnds then Shop.resume() end
end)
-- Match servers: read the party's entry, load the map, admit the party, start wave 1.
Match.start()
