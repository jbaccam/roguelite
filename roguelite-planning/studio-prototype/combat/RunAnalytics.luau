-- Gameplay analytics for play-tests (EXECUTION_PLAN_ASTRA.md "Prototype analytics"), sent to the
-- Creator Dashboard through AnalyticsService. Server only; every call is protected, so analytics can
-- never break a run. AnalyticsService only records in published games: in Studio, set the Workspace
-- attribute DebugAnalytics=true to print each event instead.
-- What it answers (Creator Dashboard > Analytics):
--   Funnels > "Run" (one per run): started -> wave 5 -> 10 -> 15 -> 20 (win). Where runs stop.
--   (No progression events: Roblox doesn't chart LogProgressionEvent yet; RunEnd carries the waves.)
--   Custom events: RunStart (value: gear power; fields: map, class, how soon after the last run),
--     RunEnd (value: waves cleared; fields: outcome, map, class), Death (value: wave; fields: cause,
--     map, class), RevivePrompt / Revived (value: revive number in the run), and the emeralds a run pays
--     (economy, source Gameplay).
--   Plan J item 7 (2026-10-02): WeaponDamage (value: damage a weapon dealt in one run; fields:
--     weapon, its share of the run's damage, map), RunDamage (value: the run's total damage),
--     ShopBuy (value: shards paid; fields: item, tier, wave band), ShopReroll (value: shards paid;
--     fields: shop or level-up, how it was paid, wave band), LevelPick (fields: stat, class, wave
--     band), FrameRate (value: a player's average FPS over one wave; fields: device, most enemies
--     alive in that wave, map) and FrameDips (value: seconds under 30 FPS in that wave).
--   TeammateRevive (value: the revived player's teammate revives this run, 1, 2, ...; fields: map,
--     wave band, party size): a teammate held their spot for 5 s (TeammateRevive; free, so it isn't
--     a Revived and never moves the Robux price ladder).
-- Unsandboxed (AnalyticsService), required by RogueliteMeta.
-- Events are queued and sent from this module's own thread. Hooks such as ShopService's and
-- CombatEffectsService's run inside sandboxed scripts, and a function called from there runs with
-- that script's capabilities (create.roblox.com/docs/scripting/capabilities), so they only queue.
local Analytics=game:GetService('AnalyticsService')
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local SSS=game:GetService('ServerScriptService')
local RS=game:GetService('ReplicatedStorage')
local combat=RS:WaitForChild('RogueliteCombat')
local Characters=require(SSS:WaitForChild('CharacterService'))
local Profiles=require(SSS:WaitForChild('ProfileService'))
local Shop=require(SSS:WaitForChild('ShopService')) -- already loaded by RogueliteMeta
local Effects=require(SSS:WaitForChild('CombatEffectsService'))
local Weapons=require(combat:WaitForChild('WeaponCatalog'))
local Catalog=require(combat:WaitForChild('ShopCatalog'))
local Upgrades=require(combat:WaitForChild('LevelUpCatalog'))
local A={}
local studio=RunService:IsStudio()
local F1,F2,F3=Enum.AnalyticsCustomFieldKeys.CustomField01.Name,Enum.AnalyticsCustomFieldKeys.CustomField02.Name,Enum.AnalyticsCustomFieldKeys.CustomField03.Name
local MILESTONES={[5]=2,[10]=3,[15]=4,[20]=5} -- wave cleared -> Run funnel step
local active={} -- player -> {stint,path,map,class,started,funnel}: the run being played
local lastHit={} -- player -> {cause,at}: what last hurt them, for the death cause
local damage={} -- player -> {total=n,by={[sourceId]=n}}: this run's damage, for WeaponDamage

local queue={} -- {method,player,args}, sent by the loop below (or right away when a player leaves)
local QUEUE_MAX=2000
local function send(item)
 local method,player,args=item[1],item[2],item[3]
 local ok,err=pcall(function() Analytics[method](Analytics,player,table.unpack(args,1,args.n)) end)
 if not ok then warn('RunAnalytics:',method,err) end
end
local function log(method,player,...)
 if studio then
  if workspace:GetAttribute('DebugAnalytics') then print('[Analytics]',method,player.Name,...) end
  return
 end
 if #queue<QUEUE_MAX then table.insert(queue,{method,player,table.pack(...)}) end
end
-- Sends everything queued, or only `player`'s events (a leaving player's, before they're gone).
local function flush(player)
 if #queue==0 then return end
 local keep={}
 local list=queue;queue=keep
 for _,item in list do
  if player and item[2]~=player then table.insert(keep,item)
  elseif item[2].Parent==Players or item[2]==player then send(item) end
 end
end
local function fields(a,b,c) return {[F1]=a,[F2]=b,[F3]=c} end
local function classOf(p) local cs=Characters.states[p];return 'Class - '..(cs and cs.class or '?') end
-- Bands keep the number of field values low (the dashboard splits by each distinct value).
local function waveBand(w) w=w or 1;return 'Wave - '..(w<=5 and '1-5' or w<=10 and '6-10' or w<=15 and '11-15' or w<=20 and '16-20' or '21+') end
local function shareBand(x) return x<.1 and '<10%' or x<.25 and '10-25%' or x<.5 and '25-50%' or x<.75 and '50-75%' or '75%+' end
local function enemyBand(n) return n<25 and '0-24' or n<50 and '25-49' or n<75 and '50-74' or n<100 and '75-99' or '100+' end
local TIERS={'I','II','III','IV'}
-- A damage source's name: the weapon, or Armor (set perks), Pet, Other.
local function sourceName(id)
 local w=Weapons.ById[id]
 if w then return w.name end
 return (id=='Armor' or id=='Pet') and id or 'Other'
end

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

-- Damage by weapon: every real hit, status tick, chain and blast, while the player is in a run.
if Effects.listenDamage then
 Effects.listenDamage(function(owner,id,actual)
  local t=active[owner] and damage[owner];if not t then return end
  t.total+=actual;t.by[id]=(t.by[id] or 0)+actual
 end)
end
-- Shop and level-up choices (ShopService hooks; ignored by an older ShopService without them).
Shop.onBuy=function(p,offerId,price)
 local a=active[p];local entry=Catalog.ById[offerId];if not a or not entry then return end
 local what=entry.kind=='Weapon' and ('Weapon - '..entry.name) or ('Item - '..entry.name)
 log('LogCustomEvent',p,'ShopBuy',price or 0,fields(what,'Tier - '..(TIERS[entry.tier] or '?'),waveBand(Shop.wave)))
end
Shop.onReroll=function(p,kind,how,cost)
 if not active[p] then return end
 log('LogCustomEvent',p,'ShopReroll',cost or 0,fields('Kind - '..(kind=='Upgrade' and 'Level-up' or 'Shop'),'Paid - '..tostring(how),waveBand(Shop.wave)))
end
Shop.onLevelPick=function(p,upgradeId)
 local def=Upgrades.ById[upgradeId];if not active[p] or not def then return end
 log('LogCustomEvent',p,'LevelPick',1,fields('Stat - '..def.name,classOf(p),waveBand(Shop.wave)))
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
 damage[p]={total=0,by={}}
 log('LogFunnelStepEvent',p,'Run',stint,1,'Started')
 log('LogCustomEvent',p,'RunStart',power,fields('Map - '..path,classOf(p),again..' · '..(partySize or 1)..'p'))
 log('LogCustomEvent',p,'RunStarter',power,fields('Weapon - '..weapon,classOf(p),'Map - '..path))
end
function A.waveCleared(p,wavesPassed)
 local a=active[p];if not a then return end
 a.cleared=wavesPassed
 local step=MILESTONES[wavesPassed]
 if step then log('LogFunnelStepEvent',p,'Run',a.funnel,step,step==5 and 'Won (wave 20)' or 'Wave '..wavesPassed) end
end
function A.died(p,wave)
 local a=active[p];local hit=lastHit[p]
 local cause=hit and os.clock()-hit.at<5 and hit.cause or 'Unknown'
 log('LogCustomEvent',p,'Death',wave,fields('Cause - '..cause,'Map - '..(a and a.path or '?'),classOf(p)))
end
-- value: which revive of the run (1 = 65 R$, 2 = 130 R$, ... the price doubles).
function A.revivePrompt(p,n) log('LogCustomEvent',p,'RevivePrompt',n or 1) end
function A.revived(p,count) log('LogCustomEvent',p,'Revived',count or 1) end
-- A free teammate revive (RogueliteMeta's TeammateRevive onRevive), logged for the revived player.
-- Counted per run: Ana's second teammate revive this run logs 2. wave: the wave they fell on.
function A.teammateRevived(p,wave)
 local a=active[p];local n=1
 if a then a.teammateRevives=(a.teammateRevives or 0)+1;n=a.teammateRevives end
 log('LogCustomEvent',p,'TeammateRevive',n,fields('Map - '..(a and a.path or '?'),waveBand(wave or Shop.wave),'Party - '..Shop.memberCount()..'p'))
end
-- Emeralds a run paid now (ProfileService.settleRun's return), as an economy source.
function A.earned(p,amount)
 if type(amount)~='number' or amount<=0 then return end
 log('LogEconomyEvent',p,Enum.AnalyticsEconomyFlowType.Source,'Emeralds',amount,p:GetAttribute('ProfileGems') or 0,Enum.AnalyticsEconomyTransactionType.Gameplay.Name,'RunWaves')
end
-- One player's run ended: Victory, Defeat, Left, or Disconnected (closed the game mid-run).
function A.runEnded(p,outcome,map,difficulty,wave,cleared,test)
 local a=active[p];active[p]=nil
 local dealt=damage[p];damage[p]=nil
 if test then return end -- admin test runs aren't play-test data
 Profiles.markRunEnd(p)
 local path=a and a.path or (map..'/'..difficulty)
 local minutes=a and math.floor((os.clock()-a.started)/60+.5) or 0
 log('LogCustomEvent',p,'RunEnd',cleared,fields('Outcome - '..outcome,'Map - '..path,classOf(p)))
 log('LogCustomEvent',p,'RunMinutes',minutes,fields('Outcome - '..outcome,'Map - '..path))
 if dealt and dealt.total>0 then
  log('LogCustomEvent',p,'RunDamage',math.floor(dealt.total+.5),fields('Outcome - '..outcome,'Map - '..path,classOf(p)))
  -- One event per source; two Tier copies of one weapon are one weapon here.
  local byName={}
  for id,n in dealt.by do local name=sourceName(id);byName[name]=(byName[name] or 0)+n end
  for name,n in byName do
   log('LogCustomEvent',p,'WeaponDamage',math.floor(n+.5),fields('Weapon - '..name,'Share - '..shareBand(n/dealt.total),'Map - '..path))
  end
 end
end

-- Frame rate (RogueliteHUD.client reports once per wave): sandboxed like RogueliteMeta's remotes,
-- so a sandboxed client could fire it too. Checked here: whole numbers in range, a known device,
-- one report per 10 s, players in a run only.
local perf=combat:FindFirstChild('PerfReport') or Instance.new('RemoteEvent')
perf.Sandboxed=true
perf.Capabilities=SecurityCapabilities.new(Enum.SecurityCapability.Basic,Enum.SecurityCapability.RemoteEvent)
perf.Name='PerfReport';perf.Parent=combat
local DEVICES={Phone=true,Tablet=true,Desktop=true,Console=true}
local lastPerf={}
local peak,lastPeak=0,0 -- most enemies alive in this wave and in the one before
local function whole(v,lo,hi) return type(v)=='number' and v==v and v%1==0 and v>=lo and v<=hi end
perf.OnServerEvent:Connect(function(p,fps,dips,device)
 local a=active[p];if not a or not DEVICES[device] or not whole(fps,1,1000) or not whole(dips,0,3600) then return end
 if os.clock()-(lastPerf[p] or -1e9)<10 then return end
 lastPerf[p]=os.clock()
 -- The report arrives just after its wave ends: whichever peak is larger is that wave's.
 local f=fields('Device - '..device,'Enemies - '..enemyBand(math.max(peak,lastPeak)),'Map - '..a.path)
 log('LogCustomEvent',p,'FrameRate',fps,f)
 if dips>0 then log('LogCustomEvent',p,'FrameDips',dips,f) end
end)

-- Once a second: count enemies during waves, then send the queue.
task.spawn(function()
 local wasCombat=false
 while true do
  task.wait(1)
  local runState=RS:FindFirstChild('RogueliteRunState')
  local combatNow=runState~=nil and runState:GetAttribute('Phase')=='Combat'
  if combatNow then
   if not wasCombat then peak=0 end
   local n=0
   for _,npc in Tags:GetTagged('RogueliteZombie') do
    if npc:IsDescendantOf(workspace) and not npc:GetAttribute('LobbyDummy') and not npc:GetAttribute('PracticeTarget') then n+=1 end
   end
   if n>peak then peak=n end
  elseif wasCombat then lastPeak=peak;peak=0 end
  wasCombat=combatNow
  flush()
 end
end)
Players.PlayerRemoving:Connect(function(p)
 local a=active[p]
 if a then A.runEnded(p,'Disconnected',a.map,a.difficulty,(a.cleared or 0)+1,a.cleared or 0,false) end
 flush(p) -- while the player can still be named in an event
 active[p]=nil;lastHit[p]=nil;damage[p]=nil;lastPerf[p]=nil
end)
return A
