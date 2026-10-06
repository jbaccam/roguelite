-- Studio Play server integration checks: actual swept collision and damage callbacks.
local combat=game.ReplicatedStorage.RogueliteCombat
local S=require(combat.CharacterStats)
local C=require(combat.WeaponCatalog)
local E=require(game.ServerScriptService.CombatEffectsService)
local Service=require(game.ServerScriptService.CharacterService)
local player=game.Players:GetPlayers()[1]
local state=Service.states[player]
state.folder:SetAttribute('WeaponEnabled',false)
-- The chase script clears RogueliteEnemies on deferred population/enabled signals.
-- Keep fixtures outside that owned folder and run the executor's practice path.
combat:SetAttribute('ZombiesEnabled',false)
local folder=Instance.new('Folder');folder.Name='ProjectileTestTargets';folder.Parent=workspace
local targets={}
local function target(name,position)
 local m=Instance.new('Model');m.Name=name
 local r=Instance.new('Part');r.Name='HumanoidRootPart';r.Size=Vector3.new(2,4,2);r.Anchored=true;r.Position=position;r.Parent=m
 local h=Instance.new('Humanoid');h.RequiresNeck=false;h.MaxHealth=1000;h.Health=1000;h.Parent=m;m.PrimaryPart=r;m.Parent=folder
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
local function definition(overrides,id,tier)
 local stats=S.resolve('Gunner',0,{Damage=0,RangedDamage=0,CritChance=0,ProjectileSpeed=0})
 for key,value in overrides or {} do stats[key]=value end
 local d=S.weapon(C.ById[id or '00'],stats,'Gunner',tier);d.stats=stats;d.owner=player;d.character=player.Character;d.practiceTarget=true;return d
end
local a,ha=target('PierceA',origin+Vector3.new(0,0,-10));local b,hb=target('PierceB',origin+Vector3.new(0,0,-20))
P:launch(definition({Pierce=1}),origin,origin+Vector3.new(0,0,-45));task.wait(.5)
local baseDamage=definition().damage
assert(math.abs(ha.Health-(1000-baseDamage))<.02,'first projectile damage: actual='..ha.Health..' expected='..(1000-baseDamage)..' callbacks='..hits..' fixtureAlive='..tostring(a:IsDescendantOf(workspace)));assert(math.abs(hb.Health-(1000-baseDamage*.7))<.02,'pierce 70% falloff')
clear()
a,ha=target('BounceA',origin+Vector3.new(0,0,-10));b,hb=target('BounceB',origin+Vector3.new(8,0,-12))
local beforeHits=hits;P:launch(definition({Bounce=4}),origin,origin+Vector3.new(0,0,-45));task.wait(.6)
assert(hb.Health==1000,'gun Bounce stat must never redirect to an off-axis enemy');assert(hits-beforeHits==1,'gun ends on contact without pierce')
clear()
-- Tier traits must reach the actual collision executor even with no item/character bonuses.
a,ha=target('NativePierceA',origin+Vector3.new(0,0,-10));b,hb=target('NativePierceB',origin+Vector3.new(0,0,-20))
local native=definition({Pierce=0,Bounce=0,ProjectileCount=0},'24',2)
P:launch(native,origin,origin+Vector3.new(0,0,-40));task.wait(.5)
assert(math.abs(ha.Health-(1000-native.damage))<.02,'tier nail first hit')
assert(math.abs(hb.Health-(1000-native.damage*.7))<.02,'native tier piercing executes without item')
clear()
a,ha=target('NativeBounceA',origin+Vector3.new(0,0,-10));b,hb=target('NativeBounceB',origin+Vector3.new(8,0,-12))
native=definition({Pierce=0,Bounce=0,ProjectileCount=0},'12',2)
beforeHits=hits;P:launch(native,origin,origin+Vector3.new(0,0,-35));task.wait(.6)
assert(math.abs(hb.Health-(1000-native.damage*.6))<.02,'native tier rebound executes without item')
assert(hits-beforeHits==2,'native bounce does not repeat target');clear()
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
-- Shot rows (launch audit P1): a Fly row per straight leg and a Land row where it stops, not a
-- row every frame. A stand-in combat folder records what clients would get.
local ShotBatch=require(combat.ShotBatch)
local rows={}
local function record(first,...)
 if first==ShotBatch.Marker then for _,row in (...) do table.insert(rows,table.pack(ShotBatch.unpack(row))) end
 else table.insert(rows,table.pack(first,...)) end
end
local stand={Shot={FireAllClients=function(_,...) record(...) end,FireClient=function(_,_,...) record(...) end},GetAttribute=function(_,name) return combat:GetAttribute(name) end}
local W=require(game.ServerScriptService.StatProjectiles).new(stand,damage,params)
local function kinds() local list={};for _,row in rows do table.insert(list,row[3]) end;return table.concat(list,',') end
a,ha=target('RowsA',origin+Vector3.new(0,0,-10));b,hb=target('RowsB',origin+Vector3.new(0,0,-20))
W:launch(definition({Pierce=1}),origin,origin+Vector3.new(0,0,-45));task.wait(.6)
assert(kinds()=='Fly,Land,Fly,Land','pierce rows: '..kinds())
assert(rows[2][7]==true and rows[2][12]==true and rows[2][16]==false,'first enemy: contact row, not terminal')
assert(rows[4][16]==true and math.abs(hb.Health-(1000-baseDamage*.7))<.02,'second enemy ends it, damage unchanged')
local firingOrigin=rows[1][1];local firingDirection=(rows[1][2]-firingOrigin).Unit
for _,row in rows do
 assert((row[1]-firingOrigin):Cross(firingDirection).Magnitude<.001,'pierce contact remains on original firing line')
 if row[3]=='Fly' then assert((row[2]-firingOrigin):Cross(firingDirection).Magnitude<.001,'pierce continuation remains on original firing line') end
end
clear();table.clear(rows)
W:launch(definition(),origin,origin+Vector3.new(0,0,-45));task.wait(1)
assert(kinds()=='Fly,Land' and rows[2][16]==true and rows[2][7]==false,'a miss lands at its range end: '..kinds())
folder:Destroy();combat:SetAttribute('ZombiesEnabled',false)
return {passed=true,groups={'native tier piercing','native tier rebound','piercing falloff','gun bounce disabled','wall occlusion','projectile size','physical travel speed','rocket splash','fly and land rows'},hits=hits}
