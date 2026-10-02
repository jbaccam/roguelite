-- Gameplay analytics for play-tests (EXECUTION_PLAN_ASTRA.md "Prototype analytics"), sent to the
-- Creator Dashboard through AnalyticsService. Server only; every call is protected, so analytics can
-- never break a run. AnalyticsService only records in published games: in Studio, set the Workspace
-- attribute DebugAnalytics=true to print each event instead.
-- What it answers (Creator Dashboard > Analytics):
--   Funnels > "Run" (one per run): started -> wave 5 -> 10 -> 15 -> 20 (win). Where runs stop.
--   Progression, path "<map>/<difficulty>": a level per wave cleared, a fail on the wave of a death.
--   Custom events: RunStart (value: gear power; fields: map, class, how soon after the last run),
--     RunEnd (value: waves cleared; fields: outcome, map, class), Death (value: wave; fields: cause,
--     map, class), RevivePrompt / Revived (value: revive number), and the emeralds a run pays
--     (economy, source Gameplay).
-- Unsandboxed (AnalyticsService), required by RogueliteMeta.
local Analytics=game:GetService('AnalyticsService')
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local SSS=game:GetService('ServerScriptService')
local combat=game:GetService('ReplicatedStorage'):WaitForChild('RogueliteCombat')
local Characters=require(SSS:WaitForChild('CharacterService'))
local Profiles=require(SSS:WaitForChild('ProfileService'))
local A={}
local studio=RunService:IsStudio()
local F1,F2,F3=Enum.AnalyticsCustomFieldKeys.CustomField01.Name,Enum.AnalyticsCustomFieldKeys.CustomField02.Name,Enum.AnalyticsCustomFieldKeys.CustomField03.Name
local MILESTONES={[5]=2,[10]=3,[15]=4,[20]=5} -- wave cleared -> Run funnel step
local active={} -- player -> {stint,path,map,class,started,funnel}: the run being played
local lastHit={} -- player -> {cause,at}: what last hurt them, for the death cause

local function log(method,player,...)
 if studio then
  if workspace:GetAttribute('DebugAnalytics') then print('[Analytics]',method,player.Name,...) end
  return
 end
 local args={...}
 local ok,err=pcall(function() Analytics[method](Analytics,player,table.unpack(args)) end)
 if not ok then warn('RunAnalytics:',method,err) end
end
local function fields(a,b,c) return {[F1]=a,[F2]=b,[F3]=c} end
local function classOf(p) local cs=Characters.states[p];return 'Class - '..(cs and cs.class or '?') end

-- Death cause: the enemy behind the last hit within 5 s (CharacterService passes melee attackers),
-- else a boss attack while a boss is up, else a projectile.
Characters.onDamaged=function(p,_,attacker)
 local cause
 if typeof(attacker)=='Instance' then
  cause=attacker:GetAttribute('MapBossId') or attacker:GetAttribute('EnemyId') or attacker:GetAttribute('ZombieType') or attacker.Name
 else
  local boss=false
  for _,tag in {'HammerBoss','MapBoss'} do if #Tags:GetTagged(tag)>0 then boss=true end end
  cause=boss and 'Boss attack' or 'Projectile'
 end
 lastHit[p]={cause=tostring(cause),at=os.clock()}
end

-- A member's run is under way (RogueliteMeta calls this every tick of combat; it logs once per stint).
function A.runStarted(p,stint,map,difficulty,joinedWave,partySize)
 local a=active[p];if a and a.stint==stint then return end
 local path=map..'/'..difficulty
 local weapon=p:GetAttribute('RunWeapon') or '?'
 local power=Characters.states[p] and Characters.states[p].stats and Characters.states[p].stats.GearPower or 1
 -- How soon after their last run (saved, so it spans servers): "Again" means within 10 minutes.
 local since=Profiles.markRunStart(p)
 local again=since==nil and 'First run' or since<=600 and 'Again <10m' or 'Later'
 active[p]={stint=stint,path=path,map=map,difficulty=difficulty,started=os.clock(),funnel=stint}
 log('LogFunnelStepEvent',p,'Run',stint,1,'Started')
 log('LogProgressionStartEvent',p,path,math.max(1,joinedWave or 1))
 log('LogCustomEvent',p,'RunStart',power,fields('Map - '..path,classOf(p),again..' · '..(partySize or 1)..'p'))
 log('LogCustomEvent',p,'RunStarter',power,fields('Weapon - '..weapon,classOf(p),'Map - '..path))
end
function A.waveCleared(p,wavesPassed)
 local a=active[p];if not a then return end
 log('LogProgressionCompleteEvent',p,a.path,wavesPassed)
 local step=MILESTONES[wavesPassed]
 if step then log('LogFunnelStepEvent',p,'Run',a.funnel,step,step==5 and 'Won (wave 20)' or 'Wave '..wavesPassed) end
end
function A.died(p,wave)
 local a=active[p];local hit=lastHit[p]
 local cause=hit and os.clock()-hit.at<5 and hit.cause or 'Unknown'
 log('LogProgressionFailEvent',p,a and a.path or '?',wave)
 log('LogCustomEvent',p,'Death',wave,fields('Cause - '..cause,'Map - '..(a and a.path or '?'),classOf(p)))
end
function A.revivePrompt(p) log('LogCustomEvent',p,'RevivePrompt',1) end
function A.revived(p,count) log('LogCustomEvent',p,'Revived',count or 1) end
-- Emeralds a run paid now (ProfileService.settleRun's return), as an economy source.
function A.earned(p,amount)
 if type(amount)~='number' or amount<=0 then return end
 log('LogEconomyEvent',p,Enum.AnalyticsEconomyFlowType.Source,'Emeralds',amount,p:GetAttribute('ProfileGems') or 0,Enum.AnalyticsEconomyTransactionType.Gameplay.Name,'RunWaves')
end
-- One player's run ended: Victory, Defeat, Left, or Disconnected (closed the game mid-run).
function A.runEnded(p,outcome,map,difficulty,wave,cleared,test)
 local a=active[p];active[p]=nil
 if test then return end -- admin test runs aren't play-test data
 Profiles.markRunEnd(p)
 local path=a and a.path or (map..'/'..difficulty)
 local minutes=a and math.floor((os.clock()-a.started)/60+.5) or 0
 log('LogCustomEvent',p,'RunEnd',cleared,fields('Outcome - '..outcome,'Map - '..path,classOf(p)))
 log('LogCustomEvent',p,'RunMinutes',minutes,fields('Outcome - '..outcome,'Map - '..path))
end
Players.PlayerRemoving:Connect(function(p)
 local a=active[p]
 if a then A.runEnded(p,'Disconnected',a.map,a.difficulty,0,0,false) end
 active[p]=nil;lastHit[p]=nil
end)
return A
