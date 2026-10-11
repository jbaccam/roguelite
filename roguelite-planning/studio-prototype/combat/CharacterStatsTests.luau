-- Run only in Studio Play server after the local player has spawned.
local combat=game.ReplicatedStorage.RogueliteCombat
local S=require(combat.CharacterStats)
local C=require(combat.WeaponCatalog)
local Service=require(game.ServerScriptService.CharacterService)
local E=require(game.ServerScriptService.CombatEffectsService)
local player=game.Players:GetPlayers()[1]
local state=assert(Service.states[player])
local humanoid=player.Character.Humanoid
local run=game.ReplicatedStorage:FindFirstChild('RogueliteRunState')
local created=not run;if created then run=Instance.new('Folder');run.Name='RogueliteRunState';run.Parent=game.ReplicatedStorage end
local originalPhase=run:GetAttribute('Phase')
-- Build presets are explicitly restricted to Practice; normal startup is now Shop.
run:SetAttribute('Phase','Practice')
local results={};local assertions=0
local function check(ok,message) assertions+=1;assert(ok,message) end
local function equal(a,b,message) check(math.abs(a-b)<.02,(message or 'difference')..': '..tostring(a)..' / '..tostring(b)) end
local function edit(action,key,value) state.lastRequest=-1e6;return Service.request(player,action,key,value) end
combat:SetAttribute('ZombiesEnabled',false);state.folder:SetAttribute('WeaponEnabled',false)
local force=player.Character:FindFirstChildOfClass('ForceField');if force then force:Destroy() end
-- Weapons per class (2026-10-09: one starter class per weapon, Chef replaces Thrower): 37 weapons.
local counts={}
for _,w in C.List do for _,c in w.classes do counts[c]=(counts[c] or 0)+1 end end
-- 2026-10-10: Excalibur moved Mage -> Brawler (Brawler 7, Mage 5).
local WANT={Brawler=7,Gunner=6,Chef=6,Juggler=7,Handyman=6,Mage=5}
for _,class in S.ClassOrder do
 check(counts[class]==WANT[class],'weapons in '..class..': '..tostring(counts[class]))
 -- 2026-10-03 class rework: the starter is one of the class's own weapons, the class panels have
 -- buffs and drawbacks to show, and Gunner's ranged attack speed is real data.
 check(C.ById[S.Signature[class]] and C.ById[S.Signature[class]].home==class and S.inClass(C.ById[S.Signature[class]],class),'starter belongs to '..class)
 local good,bad=S.classLines(class);check(#good>=3 and #bad>=1,'buffs and drawbacks '..class)
 for _,count in {0,2,4,6} do
  local s=S.resolve(class,count)
  for _,d in S.List do check(s[d.id]>=d.min and s[d.id]<=d.max,'bounded '..d.id) end
  for _,w in C.List do local d=S.weapon(w,s,class);check(d.damage>0 and d.cooldown>=.08 and d.range>0,'weapon math '..w.name) end
 end
 -- Specialty (2026-10-09): x1.10 on a weapon of your class, nothing otherwise, never a Godly.
 local s=S.resolve(class,0)
 for _,w in C.List do
  local want=(not w.godly and w.class==class) and 1+S.Specialty/100 or 1
  equal(S.weapon(w,s,class).damage/S.weapon(w,s,nil).damage,want,'specialty '..class..' '..w.name)
 end
 check(edit('Class',class),'class request');check(edit('Build'),'build request')
 local preset=S.typeCounts(S.Classes[class].build)
 for t,n in preset do check(state.typeCounts[t]==n,'build type count '..class..' '..t) end
 equal(humanoid.MaxHealth,state.stats.MaxHP,'avatar health');equal(humanoid.WalkSpeed,state.stats.MoveSpeed,'avatar speed')
 for _,d in S.List do equal(player.Character:GetAttribute('Stat_'..d.id),state.stats[d.id],'avatar '..d.id) end
end
do local s=S.resolve('Gunner',0);check(S.weapon(C.ById['00'],s,'Gunner').cooldown<S.weapon(C.ById['00'],s,'Brawler').cooldown,'Gunner ranged attack speed') end
-- One starter class per weapon (2026-10-09): the Nail Gun is Handyman's only, so a Gunner gets no
-- specialty with it; a Godly gets none with any class.
do
 check(S.specialty(C.ById['24'],'Gunner')==0 and S.specialty(C.ById['24'],'Handyman')==S.Specialty,'Nail Gun: Handyman specialty only')
 check(S.specialty(C.ById['36'],'Gunner')==0 and not S.inClass(C.ById['36'],'Gunner'),'Godly stays class-neutral')
 -- Type sets count copies, live: two Kusarigamas = Blade 2 for any class, +2 crit on them only.
 local saved={};for i=1,6 do saved[i]=state.folder['Slot'..i]:GetAttribute('WeaponId') end
 for i=1,6 do state.folder['Slot'..i]:SetAttribute('WeaponId',i<=2 and '04' or '') end
 for _,class in {'Juggler','Chef','Brawler'} do
  check(edit('Class',class),'class '..class);check(state.typeCounts.Blade==2,'Blade 2 with two copies as '..class)
  local d=S.weapon(C.ById['04'],state.stats,class,1,state.typeCounts)
  check(S.weaponStats(state.stats,d).CritChance==math.min(100,state.stats.CritChance+2),'Blade 2 crit on the Kusarigama as '..class)
 end
 -- Merging or selling (a slot emptied) recounts at once.
 state.folder.Slot2:SetAttribute('WeaponId','');Service.refresh(player);check(state.typeCounts.Blade==1,'emptied slot recounts')
 -- Utility Power follows the authored list: Spatula, Cinder Block and Rocket Launcher keep it.
 check(C.ById['05'].utility and C.ById['20'].utility and C.ById['11'].utility and not C.ById['00'].utility,'authored utility flags')
 for i=1,6 do state.folder['Slot'..i]:SetAttribute('WeaponId',saved[i] or '') end
 Service.refresh(player)
end
table.insert(results,'six classes, 43 weapons with one starter class each, specialty, live type set counts, avatar attributes')
for _,bad in {0/0,math.huge,-math.huge,'100',{},100000} do check(not edit('Stat','Damage',bad),'reject malformed/out of range') end
check(not edit('Stat','DoesNotExist',10),'reject unknown stat')
check(not edit('Stat','Pierce',.5),'reject fractional count')
check(not edit('Class','Admin'),'reject unknown class')
check(not edit('Zombies','',101),'reject over-cap zombies')
check(not edit('Zombies','',-1),'reject negative zombies')
check(not edit('Zombies','',1.5),'reject fractional zombies')
run:SetAttribute('Phase','Combat')
check(edit('Stat','Damage',20),'Studio stat controls remain usable during combat')
check(not edit('Build'),'build preset remains practice only')
run:SetAttribute('Phase','Practice')
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
-- A Culinary weapon's own life steal (its d.stats.LifeSteal, 2026-10-09), with Recovery (+50%) and the cap.
state.overrides.LifeSteal=0;Service.refresh(player);state.leech=0;humanoid.Health=40
Service.leech(player,100);equal(humanoid.Health,40,'no life steal of your own')
Service.leech(player,10,20);equal(humanoid.Health,43,'the hitting weapon heals its own 20% x Recovery')
table.insert(results,'armor, dodge, first-hit block, regeneration, recovery and capped life steal')
local folder=Instance.new('Folder');folder.Name='CharacterStatsTestTargets';folder.Parent=workspace.RogueliteEnemies
local function target(name,position)
 local npc=Instance.new('Model');npc.Name=name;npc:SetAttribute('BaseMoveSpeed',12)
 local root=Instance.new('Part');root.Name='HumanoidRootPart';root.Size=Vector3.new(2,4,2);root.Anchored=true;root.Position=position;root.Parent=npc
 local head=Instance.new('Part');head.Name='Head';head.Size=Vector3.one;head.Anchored=true;head.Position=position+Vector3.yAxis*3;head.Parent=npc
 local h=Instance.new('Humanoid');h.MaxHealth=10000;h.Health=10000;h.WalkSpeed=12;h.Parent=npc;npc.PrimaryPart=root;npc.Parent=folder
 game.CollectionService:AddTag(npc,'RogueliteZombie');return npc,h
end
local npc,h=target('Primary',Vector3.new(0,500,0))
local neutral=S.resolve('Gunner',0,{Damage=0,RangedDamage=0,CritChance=100,CritDamage=200,Knockback=0,BurnChance=0,PoisonChance=0,SlowChance=0,ChainCount=0})
local d=S.weapon(C.ById['00'],neutral,'Gunner');d.stats=neutral;d.owner=player;d.character=player.Character
equal(E.hit(npc,10,d),20,'critical damage')
npc:SetAttribute('IsBoss',true);neutral.BossDamage=50;equal(E.hit(npc,10,d),30,'boss damage');npc:SetAttribute('IsBoss',false)
neutral.CritChance=0;neutral.BurnChance=100;neutral.PoisonChance=100;neutral.SlowChance=100;neutral.SlowStrength=50
E.hit(npc,1,d);task.wait(1.15)
check(h.Health<=9940.01,'status ticks '..h.Health);equal(h.WalkSpeed,npc:GetAttribute('BaseMoveSpeed')*(1-neutral.SlowStrength/100),'slow movement')
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
-- Vacuum / Power Washer stream ticks (2026-10-03) are the weapon's own hits: they crit and proc at
-- their share of an attack (CombatEffectsService.hit's stream). Plain secondary hits and status
-- ticks still don't, and a tick never knocks back.
local uid=tostring(player.UserId)
local wd=S.weapon(C.ById['29'],neutral,'Gunner');wd.stats=neutral;wd.owner=player;wd.character=player.Character
local stream=target('Stream',Vector3.new(60,500,0));local _,hn=target('StreamNear',Vector3.new(64,500,0))
local function slowed() return E.statuses[stream]~=nil and E.statuses[stream][uid..'Slow']~=nil end
neutral.ChainCount=0;neutral.BurnChance=0;neutral.PoisonChance=0;neutral.SlowChance=0;neutral.CritChance=100;neutral.CritDamage=200;neutral.Knockback=20
equal(E.hit(stream,10,wd,true,nil,.5),20,'stream tick crits');equal(E.hit(stream,10,wd,true),10,'plain secondary hit does not crit')
check(E.knockedAt[stream]==nil,'stream tick never knocks back')
neutral.CritChance=0;neutral.Knockback=0;neutral.SlowChance=100
E.hit(stream,1,wd,true);check(not slowed(),'plain secondary hit does not proc')
E.hit(stream,1,wd,true,true);check(not slowed(),'status tick does not proc')
E.hit(stream,1,wd,true,nil,0);check(not slowed(),'proc chance scales with the tick share')
E.hit(stream,1,wd,true,nil,1);check(slowed(),'stream tick procs the slow (Ice Cube)')
neutral.SlowChance=0;neutral.ChainCount=1;neutral.ChainEvery=1;state.hits=0
local nb=hn.Health;E.hit(stream,1,wd,true,nil,.5);equal(hn.Health,nb,'half a hit: no chain yet')
E.hit(stream,1,wd,true,nil,.5);check(hn.Health<nb,'two half-hit ticks chain lightning once')
neutral.ChainCount=0
table.insert(results,'Vacuum / Power Washer stream ticks crit and proc at their share of an attack')
-- Blade set crit (2026-10-09): a weapon's own stats carry it, and only that weapon's hits roll it.
neutral.SlowChance=0;neutral.CritChance=98;neutral.CritDamage=200;neutral.Knockback=0
local kd=S.weapon(C.ById['03'],neutral,'Gunner',1,S.typeCounts({'03','03'}));kd.stats=S.weaponStats(neutral,kd);kd.owner=player;kd.character=player.Character
check(kd.stats.CritChance==100 and neutral.CritChance==98,'Blade 2: +2 crit on the Katana only')
equal(E.hit(stream,10,kd),20,'the Blade set crit lands')
table.insert(results,'per-weapon Blade crit and Culinary life steal')
folder:Destroy()
check(edit('Reset'),'reset');check(edit('Heal'),'heal')
table.insert(results,'reset and heal requests')
if created then run:Destroy() else run:SetAttribute('Phase',originalPhase) end
return {passed=true,assertions=assertions,groups=results}
