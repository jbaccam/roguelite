-- Run with Studio server execute_luau during Play; test fixtures are temporary.
local C=game.ReplicatedStorage.RogueliteCombat
local Effects=require(game.ServerScriptService.CombatEffectsService)
local Drops=require(game.ServerScriptService.ShardDropService)
local Shop=require(game.ServerScriptService.ShopService)
local Ch=require(game.ServerScriptService.CharacterService)
local E=require(C.EconomyConfig)
local Tags=game:GetService('CollectionService')
local p=game.Players:GetPlayers()[1]
local phase=Shop.phase;local enabled=C.PlayerStates[tostring(p.UserId)]:GetAttribute('WeaponEnabled')
C.PlayerStates[tostring(p.UserId)]:SetAttribute('WeaponEnabled',false)
local fixtures=Instance.new('Folder');fixtures.Name='DesignerTests';fixtures.Parent=workspace
local checks=0
local function check(v,msg) checks+=1;assert(v,msg) end
local function mob(practice)
 local m=game.ServerStorage.RogueliteNPCs.Zombie_NPC:Clone();m.Parent=fixtures
 m:PivotTo(CFrame.new(p.Character.HumanoidRootPart.Position+Vector3.new(0,0,-35)))
 for _,x in m:GetDescendants() do if x:IsA('BasePart') then x.Anchored=true end end
 m:SetAttribute('PracticeTarget',practice);Tags:AddTag(m,'RogueliteZombie')
 m.Humanoid.MaxHealth=100;m.Humanoid.Health=100;return m
end
local d={id='10',owner=p,character=p.Character,stats=table.clone(Ch.states[p].stats),damage=1}
d.stats.CritChance=0;d.stats.BurnChance=0;d.stats.PoisonChance=0;d.stats.SlowChance=0;d.stats.ChainCount=0
local spawned={}
local function newest() local x=Drops.drops[#Drops.drops];if x then table.insert(spawned,x) end;return x end
local ok,err=xpcall(function()
 Shop.phase='Combat'
 local m=mob(false);Effects.hit(m,1,d);check(m:GetAttribute('DesignerShirt')==true,'shirt marks living target')
 Effects.hit(m,1,d);check(m:GetAttribute('DesignerShirt')==true,'repeated shirt does not stack')
 local other=table.clone(d);other.id='03';Effects.hit(m,1000,other)
 local drop=newest();check(drop and drop.value==E.KILL_SHARDS+E.DESIGNER_BONUS_SHARDS,'other weapon kill retains fixed bonus')
 check(drop.owner==p,'killer owns bonus');check(drop.model:GetAttribute('ShardValue')==drop.value,'replicated value matches reward')
 local before=#Drops.drops;Drops.spawn(m,p.Character.HumanoidRootPart.Position);check(#Drops.drops==before,'duplicate death does not duplicate reward')
 m=mob(false);Effects.hit(m,1000,d);drop=newest();check(drop.value==4,'lethal first shirt grants bonus')
 m=mob(false);Effects.hit(m,1000,other);drop=newest();check(drop.value==2,'normal kill unchanged')
 m=mob(false);Effects.hit(m,1,d,true);check(not m:GetAttribute('DesignerShirt'),'secondary damage cannot dress a mob')
 m:Destroy()
 before=#Drops.drops;m=mob(true);Effects.hit(m,1000,d);check(m:GetAttribute('DesignerShirt') and m.Parent~=nil,'practice can preview shirt')
 check(#Drops.drops==before,'practice grants no shards')
 local Physics=game:GetService('PhysicsService')
 check(not Physics:CollisionGroupsAreCollidable('RoguelitePlayers','RogueliteZombies'),'players cannot stand on mobs')
 check(Physics:CollisionGroupsAreCollidable('RogueliteZombies','Default'),'mobs retain arena collisions')
 for _,x in p.Character:GetDescendants() do if x:IsA('BasePart') then check(x.CollisionGroup=='RoguelitePlayers','all avatar parts assigned') end end
 local extra=Instance.new('Part');extra.Name='LateAccessoryTest';extra.Parent=p.Character;task.wait()
 check(extra.CollisionGroup=='RoguelitePlayers','late avatar part assigned');extra:Destroy()
end,debug.traceback)
for _,x in spawned do x.model:Destroy() end
fixtures:Destroy();Shop.phase=phase;C.PlayerStates[tostring(p.UserId)]:SetAttribute('WeaponEnabled',enabled)
assert(ok,err)
return {passed=checks,scope='Studio server; no published DataStores or multiple real clients'}
