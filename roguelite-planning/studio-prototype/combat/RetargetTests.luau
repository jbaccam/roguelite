-- Disposable sandboxed Studio Script. Isolated combat folder and hit callback.
assert(game:GetService('RunService'):IsStudio())
local RS=game.ReplicatedStorage;local real=RS.RogueliteCombat
local p=game.Players:GetPlayers()[1];local Tags=game:GetService('CollectionService')
local Targets=require(real.ProjectileTarget)
local c=Instance.new('Folder');c.Name='RetargetTest';c:SetAttribute('ZombiesEnabled',true);c.Parent=RS
for _,name in {'ArcShot','Shot','RocketFX'} do local e=Instance.new('RemoteEvent');e.Name=name;e.Parent=c end
local states=Instance.new('Folder');states.Name='PlayerStates';states.Parent=c
local state=Instance.new('Folder');state.Name=tostring(p.UserId);state:SetAttribute('WeaponEnabled',true);state.Parent=states
for i=1,2 do local slot=Instance.new('Folder');slot.Name='Slot'..i;slot.Parent=state end
local fixtures=Instance.new('Folder');fixtures.Name='RetargetFixtures';fixtures.Parent=workspace
local function params(_,ignoreEnemies)
 local r=RaycastParams.new();r.FilterType=Enum.RaycastFilterType.Include
 r.FilterDescendantsInstances=ignoreEnemies and {} or {fixtures};return r
end
local hits={};local passed=0
local function check(ok,label) assert(ok,label);passed+=1 end
local function damage(npc,amount)
 hits[npc.Name]=(hits[npc.Name] or 0)+1
 npc.Humanoid.Health-=amount
 if npc.Humanoid.Health<=0 then Tags:RemoveTag(npc,'RogueliteZombie');npc:Destroy() end
end
local arcs=require(game.ServerScriptService.ArcProjectiles).new(c,damage,params)
local bullets=require(game.ServerScriptService.StatProjectiles).new(c,damage,params)
local rockets=require(real.RocketProjectile).new(c,damage,params)
local origin=Vector3.new(1000,100,1000)
local function mob(name,offset,hp)
 local m=Instance.new('Model');m.Name=name
 local r=Instance.new('Part');r.Name='HumanoidRootPart';r.Anchored=true;r.Size=Vector3.new(3,5,3);r.Position=origin+offset;r.Parent=m
 local h=Instance.new('Humanoid');h.MaxHealth=hp;h.Health=hp;h.Parent=m;m.PrimaryPart=r;m.Parent=fixtures
 Tags:AddTag(m,'RogueliteZombie');return m,r
end
local function def(id,target,slot)
 state['Slot'..slot]:SetAttribute('WeaponId',id)
 return {id=id,owner=p,character=p.Character,slotIndex=slot,arcTarget=target,kind=id=='33' and 'Blast' or 'Ranged',damage=30,range=45,projectileSpeed=30,projectileRadius=.3,blastRadius=7,stats={ProjectileCount=0,Pierce=0,Bounce=0}}
end
local function clear() for _,m in fixtures:GetChildren() do Tags:RemoveTag(m,'RogueliteZombie');m:Destroy() end;hits={} end
-- The first of six cards kills A; remaining cards must hit B, not A's old location.
local a,ar=mob('A',Vector3.new(0,0,-18),1);local b,br=mob('B',Vector3.new(7,0,-21),1000)
arcs:launch(def('18',ar,1),origin,ar.Position);arcs:launch(def('18',ar,2),origin+Vector3.xAxis,ar.Position)
task.wait(3)
check(hits.A==1,'one card kills original mob');check((hits.B or 0)>=3,'multiple decks redirect remaining cards')
clear()
for _,id in {'18','33','00','11'} do
 a,ar=mob('A',Vector3.new(0,0,-18),100);b,br=mob('B',Vector3.new(7,0,-21),1000)
 local d=def(id,ar,1)
 if id=='18' or id=='33' then arcs:launch(d,origin,ar.Position)
 elseif id=='11' then rockets:launch(p.Character,d,origin,ar.Position)
 else bullets:launch(d,origin,ar.Position) end
 task.wait(.08);a.Humanoid.Health=0;Tags:RemoveTag(a,'RogueliteZombie');a:Destroy()
 task.wait(2.7)
 if id=='00' or id=='11' then
  check((hits.B or 0)==0,'gun keeps launch heading after target dies '..id)
 else
  check((hits.B or 0)>0,'external kill retarget '..id)
 end
 check(not hits.A,'no corpse hits '..id)
 clear()
end
-- Removed/detagged, zero-health, prior hits, range and LOS cannot be reacquired.
local m,r=mob('Policy',Vector3.new(0,0,-10),100);local d=def('18',r,1)
check(Targets.alive(r),'live root accepted')
check(Targets.replacement(origin,d,{},45,origin,params)==r,'replacement found')
check(Targets.replacement(origin,d,{[m]=true},45,origin,params)==nil,'prior hit excluded')
check(Targets.replacement(origin,d,{},5,origin,params)==nil,'remaining range enforced')
local wall=Instance.new('Part');wall.Size=Vector3.new(20,20,2);wall.Position=origin+Vector3.new(0,0,-5);wall.Anchored=true;wall.Parent=fixtures
local function blocked() local r=RaycastParams.new();r.FilterType=Enum.RaycastFilterType.Include;r.FilterDescendantsInstances={wall};return r end
check(Targets.replacement(origin,d,{},45,origin,blocked)==nil,'walls block replacement')
m.Humanoid.Health=0;check(not Targets.alive(r),'dead root rejected');clear()
check(Targets.replacement(origin,d,{},45,origin,params)==nil,'no nearby replacement')
for _,id in {'18','33','00','11'} do
 a,ar=mob('A',Vector3.new(0,0,-18),100);d=def(id,ar,1)
 if id=='18' or id=='33' then arcs:launch(d,origin,ar.Position) elseif id=='11' then rockets:launch(p.Character,d,origin,ar.Position) else bullets:launch(d,origin,ar.Position) end
 task.wait(.08);a.Humanoid.Health=0;Tags:RemoveTag(a,'RogueliteZombie');a:Destroy();task.wait(.3)
 check(next(hits)==nil,'no-target cancellation '..id)
end
fixtures:Destroy()
script:SetAttribute('Results',game:GetService('HttpService'):JSONEncode({passed=passed,multipleDecks=true,families=4}))
