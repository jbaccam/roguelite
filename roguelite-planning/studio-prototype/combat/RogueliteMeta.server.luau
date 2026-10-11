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
local Contribution=require(SSS:WaitForChild('Contribution')) -- pure math: rewards by contribution
-- The first-join tutorial (TutorialConfig), guarded: nil until it is in the place. tutorialEndAt:
-- when (os.clock) the won tutorial run ends for everyone (the clock loop below).
local tutorialModule=combat:FindFirstChild('TutorialConfig')
local Tutorial=tutorialModule and require(tutorialModule)
local function tutorialRun() return Tutorial~=nil and combat:GetAttribute('TutorialRun')==true end
local tutorialEndAt
local function runMap() local id=combat:GetAttribute('RunMap');return RunSetupRules.MapIndex[id] and id or 'PineValley' end
local down,revivesUsed={},{}
local rise -- defined with revive below; downed teammates also rise at a wave's end
-- ShopService (required above) creates this folder, so looking it up here cannot deadlock.
local runState=game.ReplicatedStorage:WaitForChild('RogueliteRunState')
-- Harder difficulties pay more emeralds; wins and best waves are saved per map and difficulty.
local function difficulty() return combat:GetAttribute('RunDifficulty') or 'Normal' end
local function emeraldsFor(wave,map) return RunSetupRules.runEmeralds(RunSetupRules.MapIndex[map or runMap()],difficulty(),wave) end
-- Rewards by contribution (launch audit C1, Contribution.luau). waveWork is this wave's damage and
-- kills per member; at each clear it becomes a multiplier on that wave's share of the emerald
-- block (ledgers, one per stint, so joining late never pays for missed waves). lastHit (os.clock of
-- a member's last damage) gates play minutes. The damage and kill hooks below run inside sandboxed
-- modules, so they only add to these tables; this script's own loops and the wave clear read them.
local waveWork,ledgers,lastHit={},{},{}
local function work(p) local t=waveWork[p];if not t then t={damage=0,kills=0};waveWork[p]=t end;return t end
-- The run emeralds a stint has earned so far, before VIP (completed 5-wave blocks only).
local function owedFor(p,stint) local l=ledgers[p];return l and l.stint==stint and Contribution.owed(l) or 0 end
-- The end of one player's run, for the results screen (RunResultsUI reads the RunResult attribute):
-- outcome Victory (they reached wave 20, Endless included), Defeat or Left. Built before the run
-- resets, so it shows the build they ended with. runInfo keeps what only a wave clear knows: the
-- best wave before this stint (NEW BEST) and a first-win bonus paid during it.
local runInfo={} -- player -> {stint,prevBest,firstWin}
-- Plan M feats: the stint a player last died in (any death, even one a revive or a phoenix
-- undoes) and the last stint that cleared a wave with company. Solo and no-down need neither.
local wentDown,soloBroken={},{}
local RETURN_SECONDS=20 -- Back to Lobby happens on its own after this
local returning={} -- player -> server time of their automatic Back to Lobby
local resultSaves={} -- player -> receipt; keep results visible until this receipt is durable
local function rewardsReady(p)
 local receipt=resultSaves[p]
 return receipt~=nil and receipt.saved and workspace:GetServerTimeNow()>=receipt.reviewAt
end
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
 p:SetAttribute('RunRewardReturnAt',at)
 local firstWin=not test and info and info.firstWin or 0
 local tutorialReward=tutorialRun() and outcome=='Victory' and Tutorial.Reward or nil
 local total=test and 0 or (Profiles.stintPaid(p,stint)+firstWin)
 if tutorialReward and not test then total=tutorialReward.emeralds or 0 end
 local profile=Profiles.get(p)
 local receipt={stint=stint,saved=false,reviewAt=workspace:GetServerTimeNow()+1.5}
 resultSaves[p]=receipt
 p:SetAttribute('RunRewardStatus','Saving')
 p:SetAttribute('RunResult',Http:JSONEncode({run=Shop.runId,outcome=outcome,map=map,
  mapName=RunSetupRules.Maps[RunSetupRules.MapIndex[map] or 1].name,difficulty=difficulty(),waves=cleared,
  level=s and s.level or 1,emeralds=total,firstWin=firstWin,balance=profile and profile.emeralds or 0,reviewAt=receipt.reviewAt,
  newBest=not test and info~=nil and cleared>info.prevBest,best=best,winWave=RunSetupRules.WinWave,
  weapons=weapons,items=items,test=test==true,returnAt=at,
  tutorial=tutorialReward})) -- the tutorial's results (RunResultsUI)
 -- Settlement has already credited the profile, once. Retry only the durable write; never
 -- re-grant rewards on a save retry or a repeated Play Again request.
 task.spawn(function()
  while p.Parent==Players and resultSaves[p]==receipt and p:GetAttribute('RunResult') do
   local ok,saved=pcall(Profiles.save,p)
   if p.Parent~=Players or resultSaves[p]~=receipt or not p:GetAttribute('RunResult') then return end
   if ok and saved then
    receipt.saved=true
    p:SetAttribute('RunRewardStatus',test and 'NoRewards' or studio and 'Studio' or 'Saved')
    returning[p]=math.max(returning[p] or 0,workspace:GetServerTimeNow()+RETURN_SECONDS)
    p:SetAttribute('RunRewardReturnAt',returning[p])
    return
   end
   p:SetAttribute('RunRewardStatus','Retrying')
   task.wait(5)
  end
 end)
end
-- Quest progress (ProfileService). Guarded so this script still runs beside an older ProfileService.
local function questEvent(p,stat,n) if Profiles.questEvent then Profiles.questEvent(p,stat,n) end end
local function questRun(p,stint) if Profiles.questRun then Profiles.questRun(p,stint) end end
-- Plan K quest stats from the run: level-ups, shards picked up and shop buys (ShopService hooks),
-- damage dealt (CombatEffectsService.listenDamage) and minutes of play. The hooks run inside
-- the sandboxed ShopService / CombatEffectsService, so they only add to these tallies; this loop
-- sends them to quests once a second. Members of the run only; questEvent skips test runs.
local questTally={levels={},shards={},buys={},damage={}}
local function tally(stat,p,n) if Shop.members[p] then local t=questTally[stat];t[p]=(t[p] or 0)+n end end
Shop.onLevelUp=function(p,n) tally('levels',p,n) end
Shop.onShards=function(p,n) tally('shards',p,n) end
Shop.onBuy=function(p,id) tally('buys',p,1);if Shop.members[p] then Profiles.recordItemBuy(p,id) end end
Effects.listenDamage(function(owner,id,actual,_,lethal)
 if Shop.members[owner] then Profiles.recordWeaponHit(owner,id,actual,lethal) end
end)
if Effects.listenDamage then Effects.listenDamage(function(owner,_,actual) tally('damage',owner,actual) end) end -- plan J's hook; absent in older copies
-- Minutes count per player, and only while they fight (launch audit C2): alive and not down, in a
-- wave that isn't paused, with a hit of their own in the last 30 s. Idling in the shop or hovering
-- out of reach earns none. Example: 3 waves of 40 s, fighting the whole time -> 2 minutes.
local fightSeconds={}
task.spawn(function()
 while true do
  task.wait(1)
  for stat,t in questTally do
   for p,n in t do t[p]=nil;if Shop.members[p] then questEvent(p,stat,math.floor(n)) end end
  end
  if Shop.phase=='Combat' and combat:GetAttribute('RunPaused')~=true then
   local now=os.clock()
   for p in Shop.members do
    local h=p.Character and p.Character:FindFirstChildOfClass('Humanoid')
    if h and h.Health>0 and not down[p] and now-(lastHit[p] or -1e9)<30 then
     fightSeconds[p]=(fightSeconds[p] or 0)+1
     if fightSeconds[p]>=60 then fightSeconds[p]-=60;questEvent(p,'minutes',1) end
    end
   end
  end
 end
end)
local runKills,runDamage={},{} -- plan L: this stint's kills and damage for the pause screen (the run loop publishes them)
if Effects.listenDamage then Effects.listenDamage(function(owner,_,actual)
 if not Shop.members[owner] then return end
 runDamage[owner]=(runDamage[owner] or 0)+actual
 work(owner).damage+=actual;lastHit[owner]=os.clock() -- contribution (C1) and play minutes (C2)
end) end
-- Each cleared wave saves progress right away, so nothing waits on the death screen's Give Up:
-- the best wave, the win at wave 20 with its first-win bonus, and the run emeralds earned so far
-- (paid as they're reached; ProfileService.settleRun pays each stint's emeralds once). Leaving,
-- disconnecting or a server shutting down then never loses a reward. Each wave's share of the
-- emeralds follows the player's contribution to it (Contribution.luau); downed players are paid
-- for what they did too. Past wave 20 the run keeps going (Endless) and pays the same way.
Shop.onWaveCleared=function(wavesPassed)
 -- The tutorial: no map progress, emeralds or quests. Clearing its boss wave pays its reward once
 -- (ProfileService.tutorialReward) and ends the run as a Victory after VICTORY_DELAY, so the
 -- boss's crystals land first (the clock loop below ends it).
 if tutorialRun() then
  if wavesPassed>=Tutorial.BOSS_WAVE and not tutorialEndAt then
   if Profiles.tutorialReward then for p in Shop.members do Profiles.tutorialReward(p) end end
   runState:SetAttribute('TutorialWon',true);tutorialEndAt=os.clock()+Tutorial.VICTORY_DELAY
  end
  return
 end
 local map=runMap();local index=RunSetupRules.MapIndex[map]
 if Shop.memberCount()>1 then for p,m in Shop.members do soloBroken[p]=m.stint end end -- plan M: not solo
 local key=RunSetupRules.runKey(map,difficulty())
 -- This wave's multipliers over the members still here: someone who left mid-wave takes their
 -- share with them, so the others aren't paid less for it.
 local tallies={};for p in Shop.members do tallies[p]=waveWork[p] or {damage=0,kills=0} end
 local multiplier=Contribution.multipliers(tallies);table.clear(waveWork)
 -- The emeralds this clear completes for a solo player: a block on waves 5, 10, 15 ..., else 0.
 local block=emeraldsFor(Shop.wave,map)-emeraldsFor(Shop.wave-1,map)
 for p,m in Shop.members do
  -- The best wave before this stint is read before this clear can raise it (NEW BEST on results).
  local info=runInfo[p]
  if not info or info.stint~=m.stint then info={stint=m.stint,prevBest=Profiles.bestWave(p,key),firstWin=0};runInfo[p]=info end
  local bonus=Profiles.recordProgress(p,key,wavesPassed,RunSetupRules.firstWinEmeralds(index,difficulty()))
  if bonus>0 then info.firstWin=bonus end
  local l=ledgers[p];if not l or l.stint~=m.stint then l=Contribution.ledger(m.stint);ledgers[p]=l end
  Contribution.addWave(l,multiplier[p] or 0,block)
  Analytics.earned(p,Profiles.settleRun(p,m.stint,key,wavesPassed,Contribution.owed(l)))
  if down[p] then continue end
  if wavesPassed==RunSetupRules.WinWave and not Admin.isTestRun() then
   Shop.publish(p,'VICTORY! Keep going in Endless, or LEAVE RUN to take your rewards')
  end
  -- Quests, for a wave this player fought in (damage or a kill): a wave survived; the stint's first
  -- such wave counts a run; wave 20 is a win.
  if (multiplier[p] or 0)<=0 then continue end
  questRun(p,m.stint);questEvent(p,'waves',1)
  if wavesPassed==RunSetupRules.WinWave then questEvent(p,'wins',1) end
  if wavesPassed==10 then questEvent(p,'deepRuns',1) end -- Reach Wave 10 in One Run
  if wavesPassed==25 then questEvent(p,'wave25Runs',1) end -- plan M: Reach Wave 25 in One Run
  -- Plan M: the win's record for feats and weekly quests. Solo and no-down count from wave 1 only.
  if wavesPassed==RunSetupRules.WinWave and Profiles.questWin then
   local cs=Characters.states[p]
   Profiles.questWin(p,{diff=difficulty(),solo=m.joined==1 and soloBroken[p]~=m.stint,
    flawless=m.joined==1 and wentDown[p]~=m.stint,class=cs and cs.class})
  end
 end
 -- The run is won from here on (the shop's victory banner); Endless keeps the same loop.
 if wavesPassed>=RunSetupRules.WinWave then runState:SetAttribute('Won',true) end
end
-- Quest kills (QuestService), counted like the leaderboard's: real runs in Combat, credited to the
-- last player to hit (LastDamageUserId), never practice targets. A boss counts for every member
-- of the run: a map boss (IsMapBoss) or Pine Valley's Hammer boss (IsHammerBoss, which BossService
-- tags instead), so "Defeat a Map Boss", the Boss Hunter road and the daily streak all see both.
-- Kills with Utility weapons also count toward Handy Work.
local Death=require(combat:WaitForChild('ZombieDeath'))
local Weapons=require(combat:WaitForChild('WeaponCatalog'))
Death.onDeath=function(npc)
 if not Profiles.questEvent then return end
 if Shop.phase~='Combat' or Admin.isTestRun() or npc:GetAttribute('PracticeTarget') or npc:GetAttribute('BossPractice') then return end
 if npc:GetAttribute('IsMapBoss') or npc:GetAttribute('IsHammerBoss') then for p in Shop.members do questEvent(p,'bosses',1) end end
 if not Tags:HasTag(npc,'RogueliteZombie') then return end
 local id=npc:GetAttribute('LastDamageUserId')
 local p=type(id)=='number' and Players:GetPlayerByUserId(id) or nil
 if not p or not Shop.states[p] then return end
 questEvent(p,'kills',1)
 runKills[p]=(runKills[p] or 0)+1 -- plan L: the pause screen's kills this stint
 if Shop.members[p] then work(p).kills+=1 end -- contribution (C1); a pet's kill is its owner's
 local weapon=Weapons.ById[npc:GetAttribute('LastWeaponId')]
 -- The Handyman turret's nails (LastWeaponId 'Turret', HANDYMAN_TURRET.md) are Utility kills too.
 if (weapon and weapon.utility) or npc:GetAttribute('LastWeaponId')=='Turret' then questEvent(p,'utilityKills',1) end
 if weapon then questEvent(p,weapon.kind=='Melee' and 'meleeKills' or 'rangedKills',1) end -- Ranged, Blast and Spread count as ranged
end
local function livingInRun()
 local n=0
 for p in Shop.members do local h=p.Character and p.Character:FindFirstChildOfClass('Humanoid');if h and h.Health>0 and not down[p] then n+=1 end end
 return n
end
-- Teammate revive (TeammateRevive.luau): a living teammate holding a downed member's spot for 5 s
-- revives them there for free, any number of times. It never touches revivesUsed, so the Robux
-- price ladder only counts paid revives. Example: Ben holds Ana's spot for 5 s; Ana stands up there
-- with 50% health and a 3 s shield, and her next REVIVE still costs 65 R$. Made before clearDown,
-- which clears the spot; the service checks holds on its own 10 Hz clock.
local TeammateRevive=require(SSS:WaitForChild('TeammateRevive')) -- unsandboxed, like this script
local teammateRevive=TeammateRevive.new({
 canHelp=function(q) local h=q.Character and q.Character:FindFirstChildOfClass('Humanoid');return q.Parent==Players and Shop.members[q]~=nil and not down[q] and h~=nil and h.Health>0 end,
 isDown=function(q) return down[q]~=nil and not q:GetAttribute('RunReturning') end,
 frozen=function() return combat:GetAttribute('RunPaused')==true end, -- plan L: no reviving while frozen
 onRevive=function(q)
  local d=down[q];if not d then return end
  if Analytics.teammateRevived then Analytics.teammateRevived(q,d.wave) end -- absent in an older RunAnalytics
  rise(q,d.position,Config.ReviveHealth) -- like a paid revive: half health, the shield, the push
 end,
})
local function clearDown(p)
 down[p]=nil;p:SetAttribute('RunDown',nil);p:SetAttribute('DeathInfo',nil)
 teammateRevive.clear(p) -- their revive spot goes too
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
  if p.Parent~=Players or not Shop.states[p] or not Shop.members[p] or down[p] then return end -- left meanwhile (Leave With Party)
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
 wentDown[p]=m.stint -- plan M: before the phoenix check, so a phoenix save still counts
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
 p:SetAttribute('DeathInfo',Http:JSONEncode({wave=Shop.wave,level=s.level,emeralds=Admin.isTestRun() and 0 or owedFor(p,m.stint),map=RunSetupRules.Maps[RunSetupRules.MapIndex[runMap()]].name,
  revive=n,revivePrice=Config.Products[Config.reviveKey(n)].robux,nextRevivePrice=Config.Products[Config.reviveKey(n+1)].robux}))
 p:SetAttribute('RunDown',true)
 teammateRevive.spot(p,down[p].position) -- teammates can hold it for a free revive
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
 table.clear(waveWork) -- and no half-fought wave of the old run counts toward its first clear
end)
local function watch(p)
 p.CharacterAdded:Connect(function(character)
  local h=character:WaitForChild('Humanoid',10)
  if h then h.Died:Connect(function() onDied(p,character) end) end
 end)
end
local respawn=SSS:WaitForChild('AvatarNormalizer'):WaitForChild('RespawnPlayer')
-- No limit per run; each revive costs more (Config.reviveKey).
local rising={}
local function canRevive(p) return down[p]~=nil and not rising[p] and not p:GetAttribute('RunReturning') end
-- The revive shove (TeammateRevive.shovePlan, MonetizationConfig.RevivePush*): regular enemies near the
-- spot slide straight out over RevivePushSeconds, no damage. It was a 14-stud teleport of everything
-- within 22, bosses and round 10 tombs included (dev 2026-10-10: "a knockback on mobs, not an
-- explosion"). Each Heartbeat adds that frame's share to where the body is now, so the chase's steering
-- (Humanoid:Move) and crowd separation keep running underneath. Weapon knockback (CombatEffectsService:
-- an impulse of at most 40 studs/s) moves a walking mob only a couple of studs, too little to clear a
-- spot. Bosses (they never trip or take shoves), anchored bodies (a boss mid-attack, tombs, coffins),
-- event objectives, event-driven rushers and lobby dummies stay put. A wall stops a shove at the wall.
local function shoveAway(at)
 if not TeammateRevive.shovePlan then return end -- an older TeammateRevive in this place
 local mobs={}
 for _,npc in Tags:GetTagged('RogueliteZombie') do
  local root=npc:IsA('Model') and npc.PrimaryPart
  local h=root and npc:FindFirstChildOfClass('Humanoid')
  if h and h.Health>0 and not root.Anchored and npc:IsDescendantOf(workspace) and not npc:GetAttribute('IsBoss') and not npc:GetAttribute('EventObjective')
   and not npc:GetAttribute('EventControlled') and not npc:GetAttribute('LobbyDummy') then
   table.insert(mobs,{npc=npc,root=root,position=root.Position})
  end
 end
 local plans=TeammateRevive.shovePlan(at,mobs,Config.RevivePushRadius,Config.RevivePushDistance,Config.RevivePushMin or 4)
 if #plans==0 then return end
 local ignore={};for _,q in Players:GetPlayers() do if q.Character then table.insert(ignore,q.Character) end end
 local enemies=workspace:FindFirstChild('RogueliteEnemies');if enemies then table.insert(ignore,enemies) end
 local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude;params.FilterDescendantsInstances=ignore;params.RespectCanCollide=true
 for _,plan in plans do
  local body=math.max(1,plan.mob.root.Size.X*.5)
  local wall=workspace:Raycast(plan.mob.position,plan.direction*(plan.distance+body),params)
  if wall then plan.distance=math.max(0,(wall.Position-plan.mob.position).Magnitude-body) end
  plan.done=0
 end
 local seconds=Config.RevivePushSeconds or .25;local started=os.clock();local connection
 connection=RunService.Heartbeat:Connect(function()
  local u=math.min(1,(os.clock()-started)/seconds);local share=TeammateRevive.shoveEase(u)
  for _,plan in plans do
   local npc=plan.mob.npc;local step=plan.distance*share-plan.done
   if step>0 and npc.Parent and not plan.mob.root.Anchored then plan.done+=step;npc:PivotTo(npc:GetPivot()+plan.direction*step) end
  end
  if u>=1 then connection:Disconnect() end
 end)
end
-- Respawn at `at` with `health` (fraction of max), a short shield and nearby zombies pushed back.
-- beforePush(root) runs once the body is placed (the Phoenix blast), before the push.
rise=function(p,at,health,beforePush)
 if rising[p] then return false end
 rising[p]=true;p:SetAttribute('RunReturning',true)
 local d=down[p];local member=Shop.members[p];local succeeded=false
 local ok,err=pcall(function()
  local character=respawn:Invoke(p)
  local function stale()
   if p.Parent==Players and Shop.members[p]==member and (not d or down[p]==d) then return false end
   if character and p.Character==character then p.Character=nil;character:Destroy() end
   return true
  end
  if stale() then return end
  assert(character,'Respawn did not produce a character')
  local h=character:WaitForChild('Humanoid',10);local root=character:WaitForChild('HumanoidRootPart',10)
  assert(h and root,'Respawn body is incomplete')
  -- CharacterService sets full health when its spawn setup finishes (it tags CombatClass);
  -- apply the revive only after that, or it would be overwritten.
  local t0=os.clock()
  while character.Parent and not character:GetAttribute('CombatClass') and os.clock()-t0<5 do task.wait(.05) end
  task.wait(.15)
  assert(character.Parent and h.Health>0,'Respawned character is not alive')
  if stale() then return end
  character:PivotTo(CFrame.new(at+Vector3.new(0,3,0)))
  h.Health=math.max(1,h.MaxHealth*health)
  -- Named, so the SpawnLocation's own spawn shield timer cannot remove it early.
  for _,f in character:GetChildren() do if f:IsA('ForceField') then f:Destroy() end end
  local shield=Instance.new('ForceField');shield.Name='ReviveShield';shield.Parent=character
  task.delay(Config.ReviveInvulnerableSeconds,function() if shield.Parent then shield:Destroy() end end)
  if beforePush then beforePush(root) end
  -- Never fails the rise: the body is already up, so a shove error only warns.
  local shoved,why=pcall(shoveAway,at);if not shoved then warn('Revive shove failed: '..tostring(why)) end
  clearDown(p);p:SetAttribute('HoldRespawn',false);succeeded=true
  local state=Shop.states[p]
  if state then state.ready=false;state.revision+=1;Shop.prepareUpgrades(p);Shop.publish(p,'Back on your feet · choose upgrades and shop') end
 end)
 rising[p]=nil;p:SetAttribute('RunReturning',nil)
 if not ok then warn('Revive failed for '..p.Name..': '..tostring(err)) end
 return ok and succeeded
end
-- Hooks run on ShopService's sandboxed thread: record work only. The owning server script's
-- Heartbeat drains it so avatar loading never inherits a restricted callback's capabilities.
local shopRevives={}
Shop.onWaveCleared=function()
 if Shop.phase~='Shop' then return end
 for p in Shop.members do if down[p] then shopRevives[p]=down[p];p:SetAttribute('RunReturning',true) end end
end
RunService.Heartbeat:Connect(function()
 if next(shopRevives) and Shop.phase=='Shop' then setLastStand(nil);Shop.resume() end
 for p,d in shopRevives do
  shopRevives[p]=nil
  if p.Parent==Players and Shop.members[p] and down[p]==d and Shop.phase=='Shop' then
   task.spawn(function()
    local spawn=Role.playerSpawn()
    for attempt=1,3 do
     if p.Parent~=Players or down[p]~=d or not Shop.members[p] then break end
     if rise(p,spawn and spawn.Position or d.position,1) then break end
     task.wait(attempt)
    end
   end)
  elseif not rising[p] then
   p:SetAttribute('RunReturning',nil)
  end
 end
end)
local function revive(p)
 if not canRevive(p) then return false end
 local at=down[p].position
 if not rise(p,at,Config.ReviveHealth) then return false end
 revivesUsed[p]=(revivesUsed[p] or 0)+1
 Shop.resume()
 if lastStandEnds then setLastStand(nil) end
 Analytics.revived(p,revivesUsed[p])
 return true
end
-- Plan L's pause bookkeeping, needed by finish (2026-10-03): whoever leaves stops counting as
-- paused at once, so a run they froze unfreezes before it resets (it used to wait for the next
-- clock tick, after the reset).
local RunPause=require(SSS:WaitForChild('RunPause'))
local forgetPause -- set with the pause code below
-- One player's run ends (LOBBY_AND_MATCH_SERVERS.md §5): Leave Run (any time, 2026-10-03), Leave
-- With Party, or a Defeat when the last stand runs out. Settles the stint's emeralds up to the
-- wave reached (usually already paid at the last clear), shows the results and takes them out of
-- the run, while anyone else plays on. They stay out of the arena (dead, or with no body after
-- leaving alive, so nothing can reach it) until Back to Lobby (returnToLobby).
local function finish(p,outcome)
 local d=down[p];local m=Shop.members[p]
 local stint=d and d.stint or m and m.stint;if not stint then return false end
 if Match.log then Match.log({p},'run finished',tostring(outcome)..' at wave '..tostring(Shop.wave)) end -- trip log (MatchService)
 local map=d and d.map or runMap();local wave=d and d.wave or Shop.wave
 local test=(d and d.test) or Admin.isTestRun()
 local cleared=math.max(0,wave-1)
 -- The tutorial pays its own reward and keeps no map progress (no Pine Valley best wave).
 if not test and not tutorialRun() then Analytics.earned(p,Profiles.settleRun(p,stint,RunSetupRules.runKey(map,difficulty()),cleared,owedFor(p,stint))) end
 if cleared>=RunSetupRules.WinWave then outcome='Victory' end -- won, then left or fell in Endless
 setResult(p,outcome,map,stint,cleared,test)
 Analytics.runEnded(p,outcome,map,difficulty(),wave,cleared,test)
 clearDown(p);revivesUsed[p]=0;phoenixUsed[p]=nil;p:SetAttribute('PhoenixUsed',nil);prompting[p]=nil
 Shop.leave(p)
 if forgetPause then forgetPause(p) end -- not paused any more: a solo freeze ends here (2026-10-03)
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
-- Leave Run: any time, from the death screen, the shop or the pause menu (RunPause.canLeave). It used
-- to be refused mid-wave without a word while the pause menu had already closed itself, so a paused
-- solo player stayed frozen (2026-10-03). Leaving mid-wave pays what leaving between waves pays:
-- emeralds are settled at each clear. A downed player whose teammates still fight has Left; the
-- last one standing (or solo) is a Defeat. Returns true, or false and why (the menu shows it).
local function alive(p) local h=p.Character and p.Character:FindFirstChildOfClass('Humanoid');return h~=nil and h.Health>0 end
local function leaveRun(p)
 local ok,why=RunPause.canLeave({member=Shop.members[p]~=nil,down=down[p]~=nil,alive=alive(p)})
 if not ok then return false,why end
 if not finish(p,down[p] and livingInRun()==0 and 'Defeat' or 'Left') then return false,"You can't leave right now" end
 afterLeave()
 return true
end
-- Leave With Party (user, 2026-10-03: "option to leave with party as a party leader for private
-- parties, not matches with randoms"): the leader of a Private pad's party (MatchService.partyLeader)
-- ends the run for every party member still in it. Each is settled like their own Leave Run, sees
-- their results (the others with "<leader> ended the run for the party") and all go back to the
-- lobby in one teleport, still a party (MatchService.toLobby, RogueliteLobbyPreview). Open pads have
-- no leader, so nobody there can end anyone else's run.
local partyTrip={} -- player -> {leader=userId,ids={userIds}}: left together, back to the lobby together
local function leaveWithParty(p)
 local leader=Match.partyLeader and Match.partyLeader()
 local ok,why=RunPause.canLeave({member=Shop.members[p]~=nil,down=down[p]~=nil,alive=alive(p),withParty=true,leader=leader~=nil and leader==p.UserId})
 if not ok then return false,why end
 local list={}
 for q in Shop.members do if q==p or Match.inParty(q.UserId) then table.insert(list,q) end end
 local done,ids={},{}
 for _,q in list do if finish(q,'Left') then table.insert(done,q);table.insert(ids,q.UserId) end end
 if #done==0 then return false,"You can't leave right now" end
 -- One clock for all of them, so they go back together (the Heartbeat sends them as one group).
 local group={leader=p.UserId,ids=ids};local at=workspace:GetServerTimeNow()+RETURN_SECONDS
 for _,q in done do
  partyTrip[q]=group;returning[q]=at
  local okInfo,info=pcall(Http.JSONDecode,Http,q:GetAttribute('RunResult') or '')
  if okInfo and type(info)=='table' then
   info.returnAt=at;info.party=true
   if q~=p then info.notice=p.DisplayName..' ended the run for the party' end
   q:SetAttribute('RunResult',Http:JSONEncode(info))
  end
 end
 afterLeave()
 return true
end
-- Back to Lobby (the results screen's button, or RETURN_SECONDS after the results). A match server
-- teleports the group to a public lobby; Studio's Combined role walks them into the lobby here.
-- A Studio Match, or a teleport that can't start, puts them back in the arena instead.
local returnTries={} -- player -> failed Back to Lobby attempts on a live match server
local function returnToLobby(list)
 local blockedGroups={}
 for q,group in partyTrip do if q.Parent==Players and q:GetAttribute('RunResult') and not rewardsReady(q) then blockedGroups[group]=true end end
 local ready={};for _,p in list do if rewardsReady(p) and not blockedGroups[partyTrip[p]] then table.insert(ready,p) end end;list=ready
 for _,p in list do returning[p]=nil end
 if Role.get()=='Match' and not studio then
  -- A party that left together (leaveWithParty) goes in a teleport of its own, carrying the party,
  -- so it lands in one lobby and is put back together there.
  local groups,others={},{}
  for _,p in list do local g=partyTrip[p];if g then groups[g]=groups[g] or {};table.insert(groups[g],p) else table.insert(others,p) end end
  if #others>0 then Match.toLobby(others) end
  for g,members in groups do Match.toLobby(members,nil,{leader=g.leader,ids=g.ids}) end
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
  returnTries[p]=nil;partyTrip[p]=nil
  if p.Parent~=Players then continue end
  resultSaves[p]=nil;p:SetAttribute('RunRewardStatus',nil);p:SetAttribute('RunRewardReturnAt',nil)
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
  resultSaves[p]=nil;p:SetAttribute('RunRewardStatus',nil);p:SetAttribute('RunRewardReturnAt',nil)
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
 if not p:GetAttribute('RunResult') or partyTrip[p] then return end -- a party that left together goes home together
 if on and not rewardsReady(p) then return end
 if on then
  again[p]=true;returning[p]=nil -- waits here instead of going back on its own
  againStatus(p,'Starting...')
 else
  again[p]=nil;p:SetAttribute('PlayAgainStatus',nil)
  -- Cancelled: back to the lobby in 10 s, and the results screen's countdown says so.
  local at=workspace:GetServerTimeNow()+10;returning[p]=at
  p:SetAttribute('RunRewardReturnAt',at)
  local ok,info=pcall(Http.JSONDecode,Http,p:GetAttribute('RunResult') or '')
  if ok and type(info)=='table' then info.returnAt=at;p:SetAttribute('RunResult',Http:JSONEncode(info)) end
 end
 checkAgain()
end
-- Restart (the pause screen's RESTART, plan L; solo only): this run ends as Left (rewards so far
-- kept, as with Leave Run). Show the rewards receipt before the player confirms PLAY AGAIN.
local function restart(p)
 if not Shop.members[p] or Shop.memberCount()~=1 then return false end
 local h=p.Character and p.Character:FindFirstChildOfClass('Humanoid')
 if not down[p] and (not h or h.Health<=0) then return false end
 if not finish(p,'Left') then return false end
 afterLeave()
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
-- Pause (plans/2026-10-02-L-pause.md): RunAction SetPaused. The run freezes only when every living
-- member has paused (RunPause). A freeze holds the wave clock or the shop countdown, switches each
-- member's weapons off (restored after) and sets RogueliteCombat.RunPaused, which the spawner,
-- enemies, bosses, statuses, pets, hearts and CharacterService (hold, no damage) all check.
local pause=RunPause.new() -- RunPause is required above finish
local pausedWeapons={} -- player -> WeaponEnabled before the freeze
local shopLeft -- seconds the shop countdown had left when the run froze in the shop
local lastPauseAction,statStint={},{}
local function pauseLiving()
 local list={}
 for p in Shop.members do local h=p.Character and p.Character:FindFirstChildOfClass('Humanoid');if h and h.Health>0 and not down[p] then table.insert(list,p) end end
 return list
end
local function memberState(p) local f=combat:FindFirstChild('PlayerStates');return f and f:FindFirstChild(tostring(p.UserId)) end
local function applyPause()
 local frozen,count,living=RunPause.evaluate(pause,pauseLiving())
 if combat:GetAttribute('RunPausedCount')~=count then combat:SetAttribute('RunPausedCount',count) end
 if combat:GetAttribute('RunLivingCount')~=living then combat:SetAttribute('RunLivingCount',living) end
 local now=workspace:GetServerTimeNow()
 local change=RunPause.step(pause,frozen,now)
 if change=='freeze' then
  combat:SetAttribute('RunPaused',true)
  for p in Shop.members do local st=memberState(p);if st then pausedWeapons[p]=st:GetAttribute('WeaponEnabled');st:SetAttribute('WeaponEnabled',false) end end
  if Shop.phase=='Combat' then Shop.pause() end
  local ends=runState:GetAttribute('ShopEndsAt')
  if Shop.phase=='Shop' and type(ends)=='number' then shopLeft=math.max(0,ends-now);runState:SetAttribute('ShopEndsAt',nil) end
 elseif change=='unfreeze' then
  combat:SetAttribute('RunPaused',nil)
  for p,was in pausedWeapons do local st=memberState(p);if st and p.Parent then st:SetAttribute('WeaponEnabled',was) end end
  table.clear(pausedWeapons)
  if shopLeft then if Shop.phase=='Shop' then runState:SetAttribute('ShopEndsAt',now+shopLeft) end;shopLeft=nil end
  if livingInRun()>0 and not lastStandEnds then Shop.resume() end
 end
end
local function setPaused(p,on)
 if on and not Shop.members[p] then on=false end
 if RunPause.set(pause,p,on) then p:SetAttribute('Paused',on or nil) end
 applyPause()
end
-- A player whose run just ended (finish): out of the pause count now, and the freeze re-checked.
forgetPause=function(p) RunPause.forget(pause,p);p:SetAttribute('Paused',nil);applyPause() end
-- Melee dash (2026-10-03, RunAction 'Dash'): the player's own client has already moved its body (it
-- owns its physics); this approves the dash and stamps DashAt (server time), which MovementGuard
-- allows for and other screens draw. Approved for a living, standing run member whose class
-- dashes (CharacterStats.dashes: Brawler only), mid-wave or in the sandbox, not paused, held by the shop
-- or in a boss entrance, once per Dash.Cooldown less 0.3 s of network jitter: a dash 2.8 s after
-- the last passes, 2 s after doesn't.
local lastDash=setmetatable({},{__mode='k'})
local function dash(p)
 local s=Characters.states[p];local h=p.Character and p.Character:FindFirstChildOfClass('Humanoid')
 if not s or not Shop.members[p] or down[p] or not h or h.Health<=0 then return end
 if p:GetAttribute('LobbyPreviewActive') or p:GetAttribute('Paused') then return end
 if (Shop.phase~='Combat' and Shop.phase~='Practice') or Characters.frozen(p) or Characters.inShop(p) then return end
 if not Stats.dashes(s.class) then return end
 local now=os.clock();if now-(lastDash[p] or -math.huge)<Stats.Dash.Cooldown-.3 then return end
 lastDash[p]=now;p:SetAttribute('DashAt',workspace:GetServerTimeNow())
end
local lastRunAction={}
local useStored -- defined with the purchase code below
runAction.OnServerEvent:Connect(function(p,action,arg)
 if action=='LeaveRun' or action=='GiveUp' or action=='LeaveParty' then
  -- A refusal says why (2026-10-03): the menu that asked shows it and stays open. arg is the
  -- client's request number, echoed so a late answer can't land on a newer request.
  local ok,why
  if action=='LeaveParty' then ok,why=leaveWithParty(p) else ok,why=leaveRun(p) end
  if not ok then runAction:FireClient(p,'LeaveResult',false,why or "You can't leave right now",type(arg)=='number' and arg or nil) end
 elseif action=='ReturnToLobby' then
  if returning[p] or again[p] then
   again[p]=nil;p:SetAttribute('PlayAgainStatus',nil)
   -- A party that left together: everyone in it still on their results goes too.
   local list={p}
   local g=partyTrip[p];if g then for q,qg in partyTrip do if q~=p and qg==g and returning[q] and q.Parent==Players then table.insert(list,q) end end end
   returnToLobby(list)
  end
 elseif action=='PlayAgain' or action=='Restart' or action=='Rejoin' or action=='RejoinDismiss' then
  if os.clock()-(lastRunAction[p] or 0)<.5 then return end;lastRunAction[p]=os.clock()
  if action=='PlayAgain' then playAgain(p,arg~=false)
  elseif action=='Restart' then if not restart(p) then runAction:FireClient(p,'LeaveResult',false,'Restart is for solo runs') end
  elseif action=='RejoinDismiss' then p:SetAttribute('RejoinOffer',nil);if Match.dismissRejoin then Match.dismissRejoin(p) end
  elseif p:GetAttribute('RejoinOffer') and Match.rejoin then
   local ok,why=Match.rejoin(p)
   if not ok then
    local info=Http:JSONDecode(p:GetAttribute('RejoinOffer'));info.error=why or "Couldn't rejoin"
    p:SetAttribute('RejoinOffer',Http:JSONEncode(info))
   end
  end
 elseif action=='SetPaused' then -- plan L: the pause screen opening (true) or closing (false)
  -- At most one pause per 0.25 s; a resume always applies (RunPause.allow, 2026-10-03: a dropped
  -- resume left a solo run frozen behind a closed menu).
  if not RunPause.allow(pause,p,arg==true,os.clock()) then return end
  setPaused(p,arg==true)
 elseif action=='Dash' then dash(p) -- the melee dash (above)
 elseif action=='UseReroll' or action=='UseBanish' then useStored(p,action,arg)
 -- The loading screen is gone (ReplicatedFirst.LoadingScreen). Only times wave 1 (MatchService,
 -- TutorialDirector), which never waits longer than its own cap for it.
 elseif action=='Loaded' then p:SetAttribute('ClientLoaded',true) end
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
 -- The won tutorial run ends: everyone in it goes to the tutorial results screen (unless the
 -- admin panel ended or restarted the tutorial meanwhile: TutorialWon is cleared then).
 if tutorialEndAt and os.clock()>=tutorialEndAt then
  tutorialEndAt=nil
  if tutorialRun() and runState:GetAttribute('TutorialWon') then
   local list={};for p in Shop.members do table.insert(list,p) end
   for _,p in list do finish(p,'Victory') end
   afterLeave()
  end
 end
 local due={};for p,at in returning do if now>=at then table.insert(due,p) end end
 if #due>0 then returnToLobby(due) end
 checkAgain() -- Play Again starts when the old run is over and everyone on results has decided
 -- Pause (plan L): who must pause changes with deaths, joins and leaves; check four times a second.
 for p in pause.paused do if not Shop.members[p] or down[p] or not p.Parent then RunPause.forget(pause,p);p:SetAttribute('Paused',nil) end end
 applyPause()
 -- Fought in this wave (damage or a kill): LeaderboardService counts a wave toward Highest Wave
 -- only for a player whose ContributedWave is this run's id and wave, e.g. 'a1b2-3c:7'.
 if Shop.phase=='Combat' then
  local tag=Shop.runId..':'..Shop.wave
  for p in Shop.members do local t=waveWork[p];if t and (t.damage>0 or t.kills>0) and p:GetAttribute('ContributedWave')~=tag then p:SetAttribute('ContributedWave',tag) end end
 end
 -- This stint's kills and damage, for the pause screen (RunKills / RunDamage).
 for p,m in Shop.members do
  if statStint[p]~=m.stint then statStint[p]=m.stint;runKills[p]=0;runDamage[p]=0 end
  local k,dmg=runKills[p] or 0,math.floor(runDamage[p] or 0)
  if p:GetAttribute('RunKills')~=k then p:SetAttribute('RunKills',k) end
  if p:GetAttribute('RunDamage')~=dmg then p:SetAttribute('RunDamage',dmg) end
 end
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
-- delivered: true when the product itself was granted (not emeralds instead), so the lobby can play
-- its contents reveal (StoreUI.reveal, 2026-10-03). gift (2026-10-04): {to=name} on the buyer's
-- "Gift sent" (a toast), {from=name, pick?, emeralds?} on a gift arriving (the reveal says GIFT FROM).
local function reply(p,key,ok,message,delivered,gift) purchaseResult:FireClient(p,key,ok,message,delivered,gift) end
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
-- 65 R$ -> 666, 1040 R$ -> 10,666. `spent` is the receipt's CurrencySpent: with regional pricing a
-- player may have paid less than the list price.
local function grantRevive(p,key,spent)
 if revive(p) then return true end
 return Profiles.grant(p,{emeralds=Config.fairEmeralds(spent or Config.Products[key].robux),paid=true})
end
for i=1,Config.ReviveSteps do local key=Config.reviveKey(i);grants[key]=function(p,spent) return grantRevive(p,key,spent) end end
function grants.ShopReroll(p) return Shop.paidReroll(p,'Shop') or Profiles.grant(p,{rerolls=1}) end
function grants.UpgradeReroll(p) return Shop.paidReroll(p,'Upgrade') or Profiles.grant(p,{rerolls=1}) end
-- A bought banish is saved; the player then clicks the card to remove (RunAction UseBanish).
function grants.Banish(p) return Profiles.grant(p,{banishes=1}) end
local function grantProduct(p,key,spent)
 local product=Config.Products[key]
 if grants[key] then return grants[key](p,spent) end
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

-- Gifting (2026-10-04, user: "add gifting to the store, like be able to buy stuff for other people";
-- MONETIZATION_AND_REWARDS.md "Gifting"). Anyone in this server or any Roblox friend, developer
-- products only (MonetizationConfig.giftable). The flow, all on the server:
--  1. GIFT (PurchaseRequest 'GiftRequest', Gift.request below): checks the product, the buyer and
--     the recipient (here, or IsFriendsWith), saves an intent keyed by the buyer, then prompts.
--  2. The receipt (processReceipt): a fresh intent is bound to the PurchaseId (Gift.bind); the buyer
--     gets nothing and the gift goes into the recipient's inbox, keyed by the recipient (Gift.send).
--     Only once that write succeeds is the receipt granted, so Roblox retries anything that failed.
--  3. Delivery (Gift.deliver): on joining, on a MessagingService 'Gift:<userId>' from the buyer's
--     server, or straight away when they're here, once they stand in the lobby (the popup is a lobby
--     screen; a player mid-run gets theirs back in the lobby). Each gift is granted like a purchase
--     (a second Starter Pack pays emeralds, as receipts do), recorded as receipt 'gift:<PurchaseId>'
--     and saved BEFORE it leaves the inbox: a crash in between delivers again, and the record stops a
--     second grant. (Taking the inbox first and granting after would lose gifts in that crash.)
-- Studio keeps intents and inboxes in memory (the same rule as ProfileService),
-- so simulated purchases never persist. MessagingService is pcalled and never blocks a purchase.
-- Example: Ben (lobby A) gifts Ana (lobby B, his friend) a Starter Pack: Ben pays 49 R$ and sees
-- "Gift sent to Ana!"; Ana's server gets the message and she sees GIFT FROM BEN with its contents.
local Gift={due={},busy={},retryAt={},subs={},intents={},friendCache={},last={},window={},
 useStore=not studio, -- Studio never reaches production gift stores
 INTENT='RogueliteGiftIntent_v1',INBOX='RogueliteGiftInbox_v1',memory={}}
Gift.memory[Gift.INTENT]={};Gift.memory[Gift.INBOX]={}
function Gift.copy(v) if type(v)~='table' then return v end;local c={};for k,x in v do c[k]=Gift.copy(x) end;return c end
-- UpdateAsync on one of the two stores (or its in-memory copy in Studio). fn(old) returns the new
-- value, or nil to write nothing; results leave through fn's upvalues. Returns false on an error.
function Gift.update(name,key,fn)
 if Gift.useStore then
  local store=game:GetService('DataStoreService'):GetDataStore(name)
  local ok,err=pcall(store.UpdateAsync,store,key,function(old) return fn(old) end)
  if not ok then warn('RogueliteMeta: gift store',name,key,err) end
  return ok
 end
 local mem=Gift.memory[name];local new=fn(Gift.copy(mem[key]))
 if new~=nil then mem[key]=Gift.copy(new) end
 return true
end
-- One gift for player p, granted like its receipt would be. Returns 'item', or 'emeralds' with the
-- amount and why (owned one-time pack or class, a random item in a restricted region, a product no
-- longer sold: its Robux value in emeralds, e.g. 49 R$ -> 502), or nil when it can't be granted yet
-- (it stays in the inbox).
function Gift.grant(p,g)
 local product=Config.Products[g.key]
 local spent=(tonumber(g.spent) or 0)>0 and g.spent or product and product.robux or 0 -- a test purchase can say 0 R$
 local problem=not product and 'No longer sold' or receiptProblem(p,g.key)
 if problem then
  local n=Config.fairEmeralds(spent)
  if not Profiles.grant(p,{emeralds=n,paid=true}) then return nil end
  return 'emeralds',n,problem
 end
 -- The Godly Starter grants the profile's saved pick: the gift's, just for this grant.
 local d=Profiles.get(p);local keep=d.godlyPick
 if product.godlyPick then local pick=Config.GodlyWeapons[g.pick];if not pick then return nil end;d.godlyPick=pick[1] end
 local ok,granted=pcall(grantProduct,p,g.key,spent)
 d.godlyPick=keep
 if not ok or not granted then return nil end
 return 'item'
end
-- Reads p's inbox, grants what isn't granted yet, saves, then takes the delivered gifts out (and
-- any malformed entry, logged). Shows each popup. Returns false to try again later.
function Gift.claim(p)
 local key='u_'..p.UserId
 local inbox
 if not Gift.update(Gift.INBOX,key,function(old) inbox=old;return nil end) then return false end
 local list,bad=Config.giftList(inbox)
 if bad>0 then warn('RogueliteMeta: skipped',bad,'malformed gift(s) for',p.UserId) end
 local done,shown={},{}
 for _,g in list do
  local id='gift:'..g.receipt
  if Profiles.hasReceipt(p,id) then done[g.receipt]=true;continue end -- granted before; only its removal failed
  local ok,how,n,problem=pcall(Gift.grant,p,g)
  if ok and how then Profiles.addReceipt(p,id);done[g.receipt]=true;table.insert(shown,{g=g,how=how,n=n,problem=problem})
  else warn('RogueliteMeta: gift grant failed',g.key,g.receipt,how) end
 end
 local saved=#shown==0 or Profiles.save(p)
 for _,s in shown do
  local from=type(s.g.fromName)=='string' and #s.g.fromName<=40 and s.g.fromName or 'a friend'
  if s.how=='emeralds' then reply(p,s.g.key,true,'Gift from '..from..': '..s.problem..' · '..s.n..' emeralds instead',false,{from=from,emeralds=s.n})
  else reply(p,s.g.key,true,'Gift from '..from..'!',true,{from=from,pick=s.g.pick}) end
 end
 -- Unsaved: the inbox keeps them, and the receipts recorded above stop a second grant next time.
 if not saved then return false end
 if next(done)~=nil or bad>0 then
  Gift.update(Gift.INBOX,key,function(old) local left,n=Config.giftInboxRemove(old,done);return n>0 and left or nil end)
 end
 return true
end
-- Delivers p's gifts once their save, region answer and lobby are ready; otherwise it stays due and
-- the sweep (below) tries again every 5 s. One at a time with p's receipts.
function Gift.deliver(p)
 Gift.due[p]=true
 if Gift.busy[p] then return end
 Gift.busy[p]=true
 while Gift.due[p] and p.Parent==Players and os.clock()>=(Gift.retryAt[p] or 0) do
  if not Profiles.get(p) or restricted[p]==nil or p:GetAttribute('LobbyPreviewActive')~=true then break end
  Gift.due[p]=nil
  while receiptBusy[p] do task.wait() end
  receiptBusy[p]=true
  local ok,done=pcall(Gift.claim,p)
  receiptBusy[p]=nil
  if not (ok and done) then
   if not ok then warn('RogueliteMeta: gift delivery failed',done) end
   Gift.due[p]=true;Gift.retryAt[p]=os.clock()+30 -- a DataStore hiccup: again in 30 s
  end
 end
 Gift.busy[p]=nil
end
-- The intent this receipt pays for (bound to it), or nil for a normal purchase. wait=true: the store
-- couldn't be read, so the receipt waits; a gift must never become the buyer's purchase by accident.
function Gift.bind(p,key,purchaseId)
 if not Config.giftable(key) then return nil end
 local found
 local ok=Gift.update(Gift.INTENT,'u_'..p.UserId,function(old)
  local intent,changed=Config.giftIntentBind(old,key,purchaseId,os.time())
  found=intent
  return changed and old or nil
 end)
 if not ok then return nil,true end
 local mine=Gift.intents[p];if found and mine and mine[key] and mine[key].id==found.id then mine[key]=nil end
 return found
end
-- Puts the paid gift in the recipient's inbox (once per receipt) and tells their server. Returns
-- false when the write failed or the inbox is full: the receipt is retried.
function Gift.send(p,key,purchaseId,spent,intent)
 local gift={from=p.UserId,fromName=p.DisplayName,key=key,receipt=purchaseId,at=os.time(),pick=intent.pick,spent=spent}
 local status
 local ok=Gift.update(Gift.INBOX,'u_'..intent.to,function(old)
  local inbox;inbox,status=Config.giftInboxAdd(old,gift,Config.GiftInboxMax)
  return status=='added' and inbox or nil
 end)
 if not ok or status=='full' then return false end
 local q=Players:GetPlayerByUserId(intent.to)
 if q then task.spawn(Gift.deliver,q)
 elseif Gift.useStore then
  task.spawn(function()
   local okP,err=pcall(function() game:GetService('MessagingService'):PublishAsync('Gift:'..intent.to,p.UserId) end)
   if not okP then warn('RogueliteMeta: gift message failed (delivered on their next join)',err) end
  end)
 end
 return true
end
-- The receipt is saved: its intent binding goes (a leftover one is harmless and expires).
function Gift.finish(p,key,purchaseId)
 task.spawn(Gift.update,Gift.INTENT,'u_'..p.UserId,function(old) return Config.giftIntentDone(old,key,purchaseId) and old or nil end)
end
-- Forget a pending GIFT (by id): a normal BUY of the same product, or a GIFT prompt closed unpaid.
function Gift.cancel(p,key,id)
 local mine=Gift.intents[p];if mine and mine[key] and mine[key].id==id then mine[key]=nil end
 Gift.update(Gift.INTENT,'u_'..p.UserId,function(old) return Config.giftIntentCancel(old,key,id) and old or nil end)
end

local function processReceipt(p,key,purchaseId,spent)
 -- Wait for the profile and the region answer (retried by Roblox) before deciding anything.
 if not Profiles.get(p) or restricted[p]==nil then return Enum.ProductPurchaseDecision.NotProcessedYet end
 local gifted
 if not Profiles.hasReceipt(p,purchaseId) then
  local product=Config.Products[key]
  -- A gift (2026-10-04): the buyer gets nothing; the receipt is done once the recipient's inbox has it.
  local intent,wait=Gift.bind(p,key,purchaseId)
  if wait then return Enum.ProductPurchaseDecision.NotProcessedYet end
  local problem=not intent and receiptProblem(p,key)
  if intent then
   if not Gift.send(p,key,purchaseId,(spent or 0)>0 and spent or product.robux,intent) then return Enum.ProductPurchaseDecision.NotProcessedYet end
   Profiles.addReceipt(p,purchaseId);gifted=true
   local name=type(intent.toName)=='string' and intent.toName or 'your friend'
   reply(p,key,true,'Gift sent to '..name..'!',false,{to=name})
  elseif problem then
   local n=Config.fairEmeralds(spent or product.robux)
   if not Profiles.grant(p,{emeralds=n,paid=true}) then return Enum.ProductPurchaseDecision.NotProcessedYet end
   Profiles.addReceipt(p,purchaseId)
   reply(p,key,true,problem..' · '..n..' emeralds added instead')
  else
   local ok,granted=pcall(grantProduct,p,key,spent)
   if not ok or not granted then warn('RogueliteMeta: grant failed',key,granted);return Enum.ProductPurchaseDecision.NotProcessedYet end
   Profiles.addReceipt(p,purchaseId)
   reply(p,key,true,product.name..' purchased',true)
  end
 end
 -- Acknowledge only once the grant is saved. A failed save leaves the receipt unprocessed: Roblox
 -- retries it, the remembered PurchaseId stops a second grant here, and another server (which
 -- never saw this grant) grants it once.
 if not Profiles.save(p) then return Enum.ProductPurchaseDecision.NotProcessedYet end
 if gifted then Gift.finish(p,key,purchaseId) end
 return Enum.ProductPurchaseDecision.PurchaseGranted
end
Market.ProcessReceipt=function(info)
 local p=Players:GetPlayerByUserId(info.PlayerId)
 local key=Config.byProductId(info.ProductId)
 if not p or not key or not Profiles.get(p) then return Enum.ProductPurchaseDecision.NotProcessedYet end
 while receiptBusy[p] do task.wait() end
 receiptBusy[p]=true
 local ok,decision=pcall(processReceipt,p,key,info.PurchaseId,tonumber(info.CurrencySpent))
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
-- IsFriendsWith (a web call), remembered for a minute per pair. nil: Roblox didn't answer.
function Gift.isFriend(p,to)
 local cache=Gift.friendCache[p];if not cache then cache={};Gift.friendCache[p]=cache end
 local c=cache[to];if c and os.clock()-c.at<60 then return c.yes end
 local ok,yes=pcall(p.IsFriendsWith,p,to)
 if not ok then return nil end
 cache[to]={yes=yes==true,at=os.clock()};return yes==true
end
-- A display name for "Gift sent to Ana!" (only the buyer sees it).
function Gift.nameOf(id)
 local q=Players:GetPlayerByUserId(id);if q then return q.DisplayName end
 local ok,infos=pcall(function() return game:GetService('UserService'):GetUserInfosByUserIdsAsync({id}) end)
 local info=ok and type(infos)=='table' and infos[1]
 return type(info)=='table' and type(info.DisplayName)=='string' and info.DisplayName or 'your friend'
end
-- PurchaseRequest('GiftRequest', productKey, recipientUserId, pick): the store's GIFT confirm.
-- Everything is checked here (the client only asks), then the intent is saved and the buyer's
-- normal prompt opens. At most one per 2 s and 8 a minute: each can cost a friends check and a
-- DataStore write. Example: Ben gifts Chef to Ana, who has it: "Ana already unlocked it".
function Gift.request(p,key,to,pick)
 if type(key)~='string' then return end
 local product=Config.Products[key]
 if not Config.giftable(key) then return reply(p,key,false,"That can't be gifted") end
 local now=os.clock();local w=Gift.window[p]
 if now-(Gift.last[p] or -1e9)<2 then return reply(p,key,false,'Slow down') end
 if not w or now-w.start>=60 then w={start=now,count=0};Gift.window[p]=w end
 if w.count>=8 then return reply(p,key,false,'Too many gifts. Try again in a minute') end
 w.count+=1;Gift.last[p]=now
 if product.productId<=0 and not studio then return reply(p,key,false,'Not on sale yet') end
 if not Profiles.get(p) then return reply(p,key,false,'Profile still loading') end
 if product.random and restricted[p]~=false then return reply(p,key,false,'Not available in your region') end
 -- Godly products need their weapon in the game; the Godly Starter also its pick (an index).
 local godly=product.godly or product.godlyPick and type(pick)=='number' and Config.GodlyWeapons[pick] and Config.GodlyWeapons[pick][1]
 if product.godlyPick and not godly then return reply(p,key,false,'Pick a Godly weapon first') end
 if godly and not Profiles.weaponIdByName(godly) then return reply(p,key,false,'Coming soon') end
 local q=type(to)=='number' and to==to and to%1==0 and Players:GetPlayerByUserId(to) or nil
 local friends=false
 -- The friends check is a web call: only for a well-formed id that isn't here and isn't the buyer.
 if not q and Config.giftRecipientOk({buyer=p.UserId,to=to,friends=true}) then
  friends=Gift.isFriend(p,to)
  if friends==nil then return reply(p,key,false,"Couldn't check your friends list. Try again") end
 end
 local ok,why=Config.giftRecipientOk({buyer=p.UserId,to=to,inServer=q~=nil,friends=friends,studio=studio})
 if not ok then return reply(p,key,false,why) end
 -- Here we can see what they own (offline friends can't be checked: theirs pays emeralds instead).
 local owns=q and Config.giftBlocked(key,Profiles.get(q))
 if owns then return reply(p,key,false,q.DisplayName..' '..owns) end
 local intent={id=Http:GenerateGUID(false),to=to,toName=Gift.nameOf(to),at=os.time(),pick=product.godlyPick and pick or nil}
 -- Saved before the prompt, so a receipt on another server (or after a crash) still knows it.
 if not Gift.update(Gift.INTENT,'u_'..p.UserId,function(old) return Config.giftIntentPut(old,key,intent,os.time()) end) then
  return reply(p,key,false,"Couldn't start the gift. Try again")
 end
 Gift.intents[p]=Gift.intents[p] or {};Gift.intents[p][key]=intent
 if product.productId>0 then Market:PromptProductPurchase(p,product.productId)
 elseif studio then
  -- Studio only, a product with no ID yet: a simulated receipt through the same gift path.
  task.spawn(function()
   while receiptBusy[p] do task.wait() end
   receiptBusy[p]=true
   local okR,decision=pcall(processReceipt,p,key,'studio-'..Http:GenerateGUID(false),product.robux)
   receiptBusy[p]=nil
   if not okR or decision~=Enum.ProductPurchaseDecision.PurchaseGranted then reply(p,key,false,'Gift failed') end
  end)
 end
end
-- A GIFT prompt closed without buying: its intent goes 20 s later, unless its receipt bound it
-- meanwhile (isPurchased can be wrong; the receipt never is). Example: Ben cancels his gift to Ana
-- and later buys a Starter Pack for himself: it's his.
function Gift.closed(p,key)
 local mine=key and Gift.intents[p] and Gift.intents[p][key];if not mine then return end
 task.delay(20,Gift.cancel,p,key,mine.id)
end
function Gift.subscribe(p)
 if not Gift.useStore or Role.get()=='Match' then return end -- a match never delivers (no lobby); the next lobby does
 local ok,conn=pcall(function()
  return game:GetService('MessagingService'):SubscribeAsync('Gift:'..p.UserId,function() if p.Parent==Players then task.spawn(Gift.deliver,p) end end)
 end)
 if not ok then warn('RogueliteMeta: gift subscribe failed (gifts still arrive on the next join)',conn);return end
 if p.Parent==Players then Gift.subs[p]=conn else conn:Disconnect() end
end
function Gift.forget(p)
 local c=Gift.subs[p];if c then pcall(function() c:Disconnect() end) end
 for _,t in {Gift.due,Gift.busy,Gift.retryAt,Gift.subs,Gift.intents,Gift.friendCache,Gift.last,Gift.window} do t[p]=nil end
end
-- Gifts that couldn't be delivered yet (no save, no region answer, not in the lobby, a DataStore
-- retry) are tried again every 5 s; nothing is read until the player is ready.
task.spawn(function()
 while true do
  task.wait(5)
  local list={};for p in Gift.due do table.insert(list,p) end
  for _,p in list do if p.Parent~=Players then Gift.due[p]=nil elseif not Gift.busy[p] then task.spawn(Gift.deliver,p) end end
 end
end)
-- Admin panel "Simulate gift to me" (AdminService GiftTest, Studio only): a fake Starter Pack gift
-- from "Studio test" goes into this player's in-memory inbox and through the delivery above, so the
-- GIFT FROM popup can be checked without Robux. A second one pays emeralds (already owned).
local giftControl=game:GetService('ServerStorage'):FindFirstChild('GiftControl') or Instance.new('BindableFunction')
giftControl.Name='GiftControl'
giftControl.OnInvoke=function(what,p)
 if what~='Test' or typeof(p)~='Instance' or not p:IsA('Player') then return false,'No player' end
 if not studio or Gift.useStore then return false,'Studio only, with in-memory saves' end
 local gift={from=p.UserId,fromName='Studio test',key='StarterPack',receipt='studio-'..Http:GenerateGUID(false),at=os.time(),spent=Config.Products.StarterPack.robux}
 Gift.update(Gift.INBOX,'u_'..p.UserId,function(old) return (Config.giftInboxAdd(old,gift,Config.GiftInboxMax)) end)
 task.spawn(Gift.deliver,p)
 return true,p:GetAttribute('LobbyPreviewActive')==true and 'Test gift sent' or 'Test gift waiting: it shows in the lobby'
end
giftControl.Parent=game:GetService('ServerStorage')
purchaseRequest.OnServerEvent:Connect(function(p,key,arg,to,pick)
 if type(key)~='string' or not allowRequest(p) then return end
 if key=='GiftRequest' then return Gift.request(p,arg,to,pick) end -- arg: the product key
 local pass=Config.Passes[key]
 if pass then
  local d=Profiles.get(p)
  if d and d[passField[key]] then return reply(p,key,false,'Already owned') end
  if pass.gamePassId>0 then Market:PromptGamePassPurchase(p,pass.gamePassId)
  elseif studio then Profiles.grant(p,passGrant[key]);reply(p,key,true,'Studio test: '..pass.name..' granted (not saved)',true)
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
 -- A normal BUY forgets a pending GIFT of the same product first, so this receipt is the buyer's.
 local gifting=Gift.intents[p] and Gift.intents[p][key]
 if gifting then Gift.cancel(p,key,gifting.id) end
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
  if grantProduct(p,key) then reply(p,key,true,'Studio test: '..product.name..' granted (not saved)',true) else reply(p,key,false,'Grant failed') end
 else reply(p,key,false,'Not on sale yet') end
end)
Market.PromptProductPurchaseFinished:Connect(function(userId,productId,isPurchased)
 local p=Players:GetPlayerByUserId(userId)
 if p and Config.isRevive(Config.byProductId(productId)) then prompting[p]=nil end
 if p and not isPurchased then Gift.closed(p,Config.byProductId(productId)) end -- a GIFT prompt cancelled
end)
Market.PromptGamePassPurchaseFinished:Connect(function(p,id,bought)
 if not bought then return end
 for key,pass in Config.Passes do
  if pass.gamePassId>0 and id==pass.gamePassId then
   -- Saved right away; if the profile isn't loaded, checkPasses grants it on the next join.
   if Profiles.grant(p,passGrant[key]) then task.spawn(Profiles.save,p) end
   reply(p,key,true,pass.name..' unlocked',true)
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
 elseif action=='ClaimWeekly' and Profiles.claimWeekly and type(a)=='number' then ok,message=Profiles.claimWeekly(p,a) -- plan M
 elseif action=='ClaimFeat' and Profiles.claimFeat and type(a)=='string' and #a<=40 then ok,message=Profiles.claimFeat(p,a) -- plan M
 elseif action=='ClaimAll' and Profiles.claimAll and (a=='Daily' or a=='Weekly' or a=='Achievements') then ok,message,results=Profiles.claimAll(p,a) -- one Quests tab's CLAIM ALL (2026-10-03)
 elseif action=='TutorialStep' and Profiles.tutorialStep and type(a)=='string' and #a<=20 then ok,message=Profiles.tutorialStep(p,a) -- the tutorial's lobby steps
 elseif action=='Refresh' then Profiles.publish(p);ok=true;message=''
 elseif action=='SaveSettings' and type(a)=='table' and Profiles.saveSettings then ok,message=Profiles.saveSettings(p,a) -- U1: settings follow the player
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
 Gift.due[p]=true;task.spawn(Gift.subscribe,p) -- gifts waiting in their inbox, and new ones while here
end
Players.PlayerAdded:Connect(added)
for _,p in Players:GetPlayers() do added(p);if p.Character then local h=p.Character:FindFirstChildOfClass('Humanoid');if h then h.Died:Connect(function() onDied(p,p.Character) end) end end end
Players.PlayerRemoving:Connect(function(p)
 if (revivesUsed[p] or 0)>0 or phoenixUsed[p] then reviveCarry[p.UserId]={run=Shop.runId,revives=revivesUsed[p] or 0,phoenix=phoenixUsed[p]} end
 down[p]=nil;revivesUsed[p]=nil;phoenixUsed[p]=nil;restricted[p]=nil;lastRequest[p]=nil;lastAction[p]=nil;pendingArg[p]=nil;lastUse[p]=nil;receiptBusy[p]=nil;requestWindow[p]=nil;lastPickSave[p]=nil
 teammateRevive.clear(p) -- their spot, and their holds on others' spots
 returning[p]=nil;resultSaves[p]=nil;prompting[p]=nil;runInfo[p]=nil;returnTries[p]=nil;again[p]=nil;lastRunAction[p]=nil;partyTrip[p]=nil
 RunPause.forget(pause,p);pausedWeapons[p]=nil;lastPauseAction[p]=nil;runKills[p]=nil;runDamage[p]=nil;statStint[p]=nil -- plan L
 wentDown[p]=nil;soloBroken[p]=nil -- plan M
 waveWork[p]=nil;ledgers[p]=nil;lastHit[p]=nil;fightSeconds[p]=nil -- contribution (C1, C2)
 Gift.forget(p) -- gifting (2026-10-04): its subscription and checks
 -- The last one standing left: the clock loop pauses the wave again for the downed players' last
 -- stand. A last stand already counting down keeps the wave paused.
 if livingInRun()==0 and not lastStandEnds then Shop.resume() end
end)
-- Match servers: read the party's entry, load the map, admit the party, start wave 1.
Match.start()
