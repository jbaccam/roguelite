-- Run only in Studio Play server after the local player has spawned.
local combat=game.ReplicatedStorage.RogueliteCombat
local S=require(combat.CharacterStats)
local C=require(combat.WeaponCatalog)
local Service=require(game.ServerScriptService.CharacterService)
local E=require(game.ServerScriptService.CombatEffectsService)
local player=game.Players:GetPlayers()[1]
local state=assert(Service.states[player])
local humanoid=player.Character.Humanoid
local results={};local assertions=0
local function check(ok,message) assertions+=1;assert(ok,message) end
local function equal(a,b,message) check(math.abs(a-b)<.02,(message or 'difference')..': '..tostring(a)..' / '..tostring(b)) end
local function edit(action,key,value) state.lastRequest=-1e6;return Service.request(player,action,key,value) end
combat:SetAttribute('ZombiesEnabled',false);state.folder:SetAttribute('WeaponEnabled',false)
local force=player.Character:FindFirstChildOfClass('ForceField');if force then force:Destroy() end
local counts={}
for _,w in C.List do counts[w.home]=(counts[w.home] or 0)+1 end
for _,class in S.ClassOrder do
 check(counts[class]==6,'six home weapons '..class)
 for _,count in {0,2,4,6} do
  local s=S.resolve(class,count)
  for _,d in S.List do check(s[d.id]>=d.min and s[d.id]<=d.max,'bounded '..d.id) end
  for _,w in C.List do local d=S.weapon(w,s,class);check(d.damage>0 and d.cooldown>=.08 and d.range>0,'weapon math '..w.name) end
 end
 check(edit('Class',class),'class request');check(edit('Build'),'build request')
 check(state.folder:GetAttribute('AffinityCount')>=3,'build affinity')
 equal(humanoid.MaxHealth,state.stats.MaxHP,'avatar health');equal(humanoid.WalkSpeed,state.stats.MoveSpeed,'avatar speed')
 for _,d in S.List do equal(player.Character:GetAttribute('Stat_'..d.id),state.stats[d.id],'avatar '..d.id) end
end
table.insert(results,'six classes, 36 weapons, avatar attributes and affinity calculations')
for _,bad in {0/0,math.huge,-math.huge,'100',{},100000} do check(not edit('Stat','Damage',bad),'reject malformed/out of range') end
check(not edit('Stat','DoesNotExist',10),'reject unknown stat')
check(not edit('Stat','Pierce',.5),'reject fractional count')
check(not edit('Class','Admin'),'reject unknown class')
check(not edit('Zombies','',101),'reject over-cap zombies')
check(not edit('Zombies','',-1),'reject negative zombies')
check(not edit('Zombies','',1.5),'reject fractional zombies')
local run=game.ReplicatedStorage:FindFirstChild('RogueliteRunState')
local created=not run;if created then run=Instance.new('Folder');run.Name='RogueliteRunState';run.Parent=game.ReplicatedStorage end
local phase=run:GetAttribute('Phase');run:SetAttribute('Phase','Combat')
check(not edit('Stat','Damage',20),'reject non-practice edits')
if created then run:Destroy() else run:SetAttribute('Phase',phase) end
check(edit('Class','Brawler'),'reset class')
check(not Service.request(player,'Heal'),'rate limit')
table.insert(results,'malformed, nonfinite, fractional, phase and rate-limit rejection')
state.overrides={Armor=15,Dodge=0,ContactReduction=0,Regeneration=0,Recovery=0};Service.refresh(player);humanoid.Health=humanoid.MaxHealth
equal(Service.contact(player,20,1),10,'armor mitigation')
state.overrides.Dodge=60;Service.refresh(player);equal(Service.contact(player,20,0),0,'dodge')
state.overrides.FirstHitBlock=1;state.blocks=1;Service.refresh(player);equal(Service.contact(player,20,1),0,'first block')
check(state.blocks==0,'block consumed')
state.overrides.FirstHitBlock=0;state.overrides.Regeneration=2;state.overrides.Recovery=50;Service.refresh(player)
humanoid.Health=50;task.wait(1.2);check(humanoid.Health>53 and humanoid.Health<55,'regeneration and recovery')
state.overrides.Regeneration=0;state.overrides.LifeSteal=30;state.overrides.LifeStealCap=5;Service.refresh(player)
state.leech=0;humanoid.Health=40;Service.leech(player,100);Service.leech(player,100);equal(humanoid.Health,45,'life steal per-second cap')
table.insert(results,'armor, dodge, first-hit block, regeneration, recovery and capped life steal')
local folder=Instance.new('Folder');folder.Name='CharacterStatsTestTargets';folder.Parent=workspace.RogueliteEnemies
local function target(name,position)
 local npc=Instance.new('Model');npc.Name=name
 local root=Instance.new('Part');root.Name='HumanoidRootPart';root.Size=Vector3.new(2,4,2);root.Anchored=true;root.Position=position;root.Parent=npc
 local head=Instance.new('Part');head.Name='Head';head.Size=Vector3.one;head.Anchored=true;head.Position=position+Vector3.yAxis*3;head.Parent=npc
 local h=Instance.new('Humanoid');h.MaxHealth=10000;h.Health=10000;h.Parent=npc;npc.PrimaryPart=root;npc.Parent=folder
 game.CollectionService:AddTag(npc,'RogueliteZombie');return npc,h
end
local npc,h=target('Primary',Vector3.new(0,500,0))
local neutral=S.resolve('Gunner',0,{Damage=0,RangedDamage=0,CritChance=100,CritDamage=200,Knockback=0,BurnChance=0,PoisonChance=0,SlowChance=0,ChainCount=0})
local d=S.weapon(C.ById['00'],neutral,'Gunner');d.stats=neutral;d.owner=player;d.character=player.Character
equal(E.hit(npc,10,d),20,'critical damage')
npc:SetAttribute('IsBoss',true);neutral.BossDamage=50;equal(E.hit(npc,10,d),30,'boss damage');npc:SetAttribute('IsBoss',false)
neutral.CritChance=0;neutral.BurnChance=100;neutral.PoisonChance=100;neutral.SlowChance=100;neutral.SlowStrength=50
E.hit(npc,1,d);task.wait(1.15)
check(h.Health<=9940.01,'status ticks '..h.Health);equal(h.WalkSpeed,6.75,'slow movement')
check(npc:GetAttribute('BurnUntil')~=nil and npc:GetAttribute('PoisonUntil')~=nil,'status applied')
for _=1,12 do E.hit(npc,1,d) end
local poison=E.statuses[npc][tostring(player.UserId)..'Poison'];check(poison.stacks==neutral.PoisonStacks,'poison stack cap')
local second,h2=target('Secondary',Vector3.new(5,500,0))
neutral.ChainCount=1;neutral.ChainEvery=1;neutral.BurnChance=0;neutral.PoisonChance=0;neutral.SlowChance=0
local before=h2.Health;E.hit(npc,1,d);check(h2.Health<before,'lightning chain');check(h.Health>0,'no recursive chain')
neutral.BurnSpread=1
E.statuses[npc][tostring(player.UserId)..'Burn'].spread=true
E.hit(npc,20000,d,true);check(E.statuses[second]~=nil,'burn spread');check(not E.statuses[second][tostring(player.UserId)..'Burn'].spread,'spread cannot recurse')
table.insert(results,'critical/boss damage, burn, slow, poison caps, chains and bounded burn spread')
folder:Destroy()
check(edit('Reset'),'reset');check(edit('Heal'),'heal')
table.insert(results,'reset and heal requests')
return {passed=true,assertions=assertions,groups=results}
