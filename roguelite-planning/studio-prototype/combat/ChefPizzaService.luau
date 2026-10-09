-- Chef pizza drops on the server (rules: ReplicatedStorage.RogueliteCombat.ChefPizza). Slices are a
-- variant of HeartDropService's hearts, which attaches this at load: same folder, magnet pull,
-- Recovery-scaled heal on arrival (CharacterService.heal), expiry, pause and clean-up when the run
-- leaves Combat (wave end, run end). This module only decides drops: on each real enemy death
-- (ZombieDeath.onDeath), if the kill credit (LastDamageUserId) is a Chef and the killing weapon
-- (LastWeaponId) is a Chef weapon, it rolls 8% with 1.5 s spacing, removes his oldest slice past 4
-- and asks HeartDropService for a slice. Server-owned: no remote, no client-supplied amounts.
-- A leaving Chef's slices go with him. Healing is not a persistent reward, so it runs in Studio too.
-- Studio test hook: ReplicatedStorage.RogueliteCombat attribute TestPizzaChance (0-1), ignored live.
-- Sandboxed ModuleScript in ServerScriptService, like HeartDropService. Never waits on
-- RogueliteRunState: ShopService loads this (through HeartDropService) before it exists.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local RS=game:GetService('ReplicatedStorage')
local combat=RS:WaitForChild('RogueliteCombat')
local Motion=require(combat:WaitForChild('ShardMotion'))
local S={lastDrop={}}
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
  local d=hearts.spawnAt(position,{kind='Pizza',owner=killer,lifetime=Rules.LIFETIME,heal=heal,allow=allow})
  if not d then return end -- not in Combat
  S.lastDrop[killer]=now
  local slices={}
  for i,old in before do slices[i]={born=old.born,taken=old.target~=nil,drop=old} end
  for _,s in Rules.evictions(slices) do hearts.removeDrop(s.drop) end
 end
 Players.PlayerRemoving:Connect(function(p)
  S.lastDrop[p]=nil
  for _,d in owned(p) do hearts.removeDrop(d) end
 end)
end
return S
