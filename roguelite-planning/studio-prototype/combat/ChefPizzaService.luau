-- Chef pizza drops on the server (rules: ReplicatedStorage.RogueliteCombat.ChefPizza). Slices are a
-- variant of HeartDropService's hearts, which attaches this at load: same folder, magnet pull,
-- Recovery-scaled heal on arrival (CharacterService.heal), expiry, pause and clean-up when the run
-- leaves Combat (wave end, run end). This module only decides drops: on each real enemy death
-- (ZombieDeath.onDeath), if the kill credit (LastDamageUserId) is a Chef and the killing weapon
-- (LastWeaponId) is a Chef weapon, it rolls 15% with 1 s spacing, removes his oldest slice past 4
-- and asks HeartDropService for a slice. Server-owned: no remote, no client-supplied amounts.
-- A leaving Chef's slices go with him. Healing is not a persistent reward, so it runs in Studio too.
-- Full Belly (2026-10-10): whoever eats a slice gets a stack (ChefPizza.stacksAfterPickup: up to 5,
-- 10 s from the latest slice, all lost together). Kept here per player and run through
-- CharacterService.setPizzaBuff -> refresh, so weapons, speed and the stat screens use it. Player
-- attributes PizzaStacks and PizzaBuffUntil (server time) are for the HUD only. A paused run holds
-- the timer (like the hearts); stacks clear when the run leaves Combat, on death and on leaving.
-- Studio test hook: ReplicatedStorage.RogueliteCombat attribute TestPizzaChance (0-1), ignored live.
-- Sandboxed ModuleScript in ServerScriptService, like HeartDropService. Never waits on
-- RogueliteRunState: ShopService loads this (through HeartDropService) before it exists.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local RS=game:GetService('ReplicatedStorage')
local combat=RS:WaitForChild('RogueliteCombat')
local Motion=require(combat:WaitForChild('ShardMotion'))
local S={lastDrop={},buffs={}} -- buffs: player -> {stacks, untilTime}
local rng=Random.new()
local function testChance()
 local v=RunService:IsStudio() and combat:GetAttribute('TestPizzaChance')
 return type(v)=='number' and v or nil
end
function S.attach(hearts)
 -- Looked up, not waited on: without the rules module the place keeps hearts only.
 local rulesModule=combat:FindFirstChild('ChefPizza')
 if not rulesModule then warn('ChefPizzaService: RogueliteCombat.ChefPizza is missing; no pizza drops');return end
 local Rules=require(rulesModule)
 local Weapons=require(combat:WaitForChild('WeaponCatalog'))
 local Death=require(combat:WaitForChild('ZombieDeath'))
 local Characters=require(script.Parent:WaitForChild('CharacterService'))
 local function heal(h) return Rules.healBase(h.MaxHealth) end
 local function allow(d,now,distance,radius)
  return Rules.canCollect({exists=d.model.Parent~=nil,taken=d.target~=nil,born=d.born,now=now,
   rest=Motion.REST_SECONDS,alive=true,distance=distance,radius=radius})
 end
 -- Full Belly. Older rules or CharacterService in a place: slices only heal.
 local buffing=type(Rules.stacksAfterPickup)=='function' and type(Characters.setPizzaBuff)=='function'
 local function setBuff(p,b)
  S.buffs[p]=b
  p:SetAttribute('PizzaStacks',b and b.stacks or nil);p:SetAttribute('PizzaBuffUntil',b and b.untilTime or nil)
  Characters.setPizzaBuff(p,Rules.buffBonus(b and b.stacks or 0))
 end
 local function eat(p)
  if not buffing or not p.Parent then return end
  local b=S.buffs[p]
  local stacks,untilTime=Rules.stacksAfterPickup(workspace:GetServerTimeNow(),b and b.stacks,b and b.untilTime)
  if b and b.stacks==stacks then -- at the cap: only the timer moves, no stat refresh
   b.untilTime=untilTime;p:SetAttribute('PizzaBuffUntil',untilTime)
  else setBuff(p,{stacks=stacks,untilTime=untilTime}) end
 end
 local function owned(p)
  local list={}
  for _,d in hearts.drops do if d.kind=='Pizza' and d.owner==p then table.insert(list,d) end end
  return list
 end
 Death.onDeath=function(npc,position)
  if npc:GetAttribute('PracticeTarget') or not Tags:HasTag(npc,'RogueliteZombie') then return end
  local id=npc:GetAttribute('LastDamageUserId')
  local killer=type(id)=='number' and Players:GetPlayerByUserId(id) or nil
  local state=killer and Characters.states[killer]
  if not state then return end
  local weaponId=npc:GetAttribute('LastWeaponId')
  local now=workspace:GetServerTimeNow()
  if not Rules.decide({class=state.class,weapon=Weapons.ById[weaponId],weaponId=weaponId,now=now,
   lastDrop=S.lastDrop[killer],rng=rng,chance=testChance()}) then return end
  local before=owned(killer)
  local d=hearts.spawnAt(position,{kind='Pizza',owner=killer,lifetime=Rules.LIFETIME,heal=heal,allow=allow,arrive=eat})
  if not d then return end -- not in Combat
  S.lastDrop[killer]=now
  local slices={}
  for i,old in before do slices[i]={born=old.born,taken=old.target~=nil,drop=old} end
  for _,s in Rules.evictions(slices) do hearts.removeDrop(s.drop) end
 end
 -- The Full Belly timer, 10 times a second: expiry, pause (the timer moves later by the pause, like
 -- the hearts' ExpiresAt), and clean-up when the run leaves Combat or the eater dies.
 if buffing then
  local pausedAt;local elapsed=0
  RunService.Heartbeat:Connect(function(dt)
   elapsed+=dt;if elapsed<.1 then return end;elapsed=0
   if next(S.buffs)==nil then pausedAt=nil;return end
   local now=workspace:GetServerTimeNow()
   if combat:GetAttribute('RunPaused')==true then pausedAt=pausedAt or now;return end
   if pausedAt then
    local by=now-pausedAt;pausedAt=nil
    for p,b in S.buffs do b.untilTime+=by;p:SetAttribute('PizzaBuffUntil',b.untilTime) end
   end
   local run=RS:FindFirstChild('RogueliteRunState')
   local fighting=run~=nil and run:GetAttribute('Phase')=='Combat'
   for p,b in S.buffs do
    local h=p.Character and p.Character:FindFirstChildOfClass('Humanoid')
    if not fighting or not h or h.Health<=0 or Rules.buffStacks(now,b.stacks,b.untilTime)==0 then setBuff(p,nil) end
   end
  end)
 end
 Players.PlayerRemoving:Connect(function(p)
  S.lastDrop[p]=nil;S.buffs[p]=nil
  for _,d in owned(p) do hearts.removeDrop(d) end
 end)
end
return S
