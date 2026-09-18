-- Studio Play server integration checks: actual swept collision and damage callbacks.
local combat=game.ReplicatedStorage.RogueliteCombat
local S=require(combat.CharacterStats)
local C=require(combat.WeaponCatalog)
local E=require(game.ServerScriptService.CombatEffectsService)
local Service=require(game.ServerScriptService.CharacterService)
local player=game.Players:GetPlayers()[1]
local state=Service.states[player]
state.folder:SetAttribute('WeaponEnabled',false)
combat:SetAttribute('ZombieCount',0);combat:SetAttribute('ZombiesEnabled',true)
local folder=Instance.new('Folder');folder.Name='ProjectileTestTargets';folder.Parent=workspace.RogueliteEnemies
local targets={}
local function target(name,position)
 local m=Instance.new('Model');m.Name=name
 local r=Instance.new('Part');r.Name='HumanoidRootPart';r.Size=Vector3.new(2,4,2);r.Anchored=true;r.Position=position;r.Parent=m
 local h=Instance.new('Humanoid');h.MaxHealth=1000;h.Health=1000;h.Parent=m;m.PrimaryPart=r;m.Parent=folder
 game.CollectionService:AddTag(m,'RogueliteZombie');table.insert(targets,m);return m,h
end
local function clear() for _,m in targets do m:Destroy() end;table.clear(targets) end
local function params(character,ignore)
 local p=RaycastParams.new();p.FilterType=Enum.RaycastFilterType.Exclude;p.FilterDescendantsInstances=ignore and {character,folder} or {character};return p
end
local hits=0
local function damage(npc,amount,d) hits+=1;return E.hit(npc,amount,d) end
local P=require(game.ServerScriptService.StatProjectiles).new(combat,damage,params)
local R=require(combat.RocketProjectile).new(combat,damage,params)
local origin=Vector3.new(0,500,0)
local function definition(overrides,id)
 local stats=S.resolve('Gunner',0,{Damage=0,RangedDamage=0,CritChance=0,ProjectileSpeed=0})
 for key,value in overrides or {} do stats[key]=value end
 local d=S.weapon(C.ById[id or '00'],stats,'Gunner');d.stats=stats;d.owner=player;d.character=player.Character;return d
end
local a,ha=target('PierceA',origin+Vector3.new(0,0,-10));local b,hb=target('PierceB',origin+Vector3.new(0,0,-20))
P:launch(definition({Pierce=1}),origin,origin+Vector3.new(0,0,-45));task.wait(.5)
assert(math.abs(ha.Health-984)<.02,'first projectile damage');assert(math.abs(hb.Health-988.8)<.02,'pierce 70% falloff')
clear()
a,ha=target('BounceA',origin+Vector3.new(0,0,-10));b,hb=target('BounceB',origin+Vector3.new(8,0,-12))
local beforeHits=hits;P:launch(definition({Bounce=4}),origin,origin+Vector3.new(0,0,-45));task.wait(.6)
assert(math.abs(hb.Health-990.4)<.02,'bounce 60% falloff');assert(hits-beforeHits==2,'no repeat targets')
clear()
a,ha=target('Occluded',origin+Vector3.new(0,0,-15))
local wall=Instance.new('Part');wall.Name='ProjectileTestWall';wall.Anchored=true;wall.Size=Vector3.new(8,8,1);wall.Position=origin+Vector3.new(0,0,-6);wall.Parent=workspace
P:launch(definition({Pierce=4,Bounce=4}),origin,origin+Vector3.new(0,0,-45));task.wait(.4);assert(ha.Health==1000,'wall blocks projectile');wall:Destroy();clear()
a,ha=target('Size',origin+Vector3.new(1.25,0,-10))
P:launch(definition(),origin,origin+Vector3.new(0,0,-45));task.wait(.5);assert(ha.Health==1000,'small projectile misses')
P:launch(definition({ProjectileSize=150}),origin,origin+Vector3.new(0,0,-45));task.wait(.5);assert(ha.Health<1000,'larger projectile collision');clear()
a,ha=target('Speed',origin+Vector3.new(0,0,-20))
P:launch(definition({ProjectileSpeed=-50}),origin,origin+Vector3.new(0,0,-45));task.wait(.1);assert(ha.Health==1000,'projectile has travel time');task.wait(.5);assert(ha.Health<1000,'slow projectile arrives');clear()
a,ha=target('BlastPrimary',origin+Vector3.new(0,0,-15));b,hb=target('BlastNearby',origin+Vector3.new(6,0,-15))
R:launch(player.Character,definition({ExplosionDamage=50,AreaSize=50},'11'),origin,origin+Vector3.new(0,0,-40));task.wait(.6)
assert(ha.Health<1000 and hb.Health<1000,'rocket blast and area damage');clear()
folder:Destroy();combat:SetAttribute('ZombiesEnabled',false)
return {passed=true,groups={'piercing falloff','bounce falloff and unique targets','wall occlusion','projectile size','physical travel speed','rocket splash'},hits=hits}
