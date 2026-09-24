-- Players cannot stand on mobs; mobs still collide with arena geometry.
local Physics=game:GetService('PhysicsService')
local Players=game:GetService('Players')
local Tags=game:GetService('CollectionService')
for _,name in {'RoguelitePlayers','RogueliteZombies'} do
 if not Physics:IsCollisionGroupRegistered(name) then Physics:RegisterCollisionGroup(name) end
end
Physics:CollisionGroupSetCollidable('RoguelitePlayers','RogueliteZombies',false)
Physics:CollisionGroupSetCollidable('RogueliteZombies','RogueliteZombies',false)
local bound=setmetatable({},{__mode='k'})
local function bind(model,group)
 if bound[model] then return end;bound[model]=true
 local function part(p) if p:IsA('BasePart') then p.CollisionGroup=group end end
 for _,p in model:GetDescendants() do part(p) end
 local connection=model.DescendantAdded:Connect(part)
 model.Destroying:Once(function() connection:Disconnect() end)
end
local function player(p)
 p.CharacterAdded:Connect(function(c) bind(c,'RoguelitePlayers') end)
 if p.Character then bind(p.Character,'RoguelitePlayers') end
end
Players.PlayerAdded:Connect(player);for _,p in Players:GetPlayers() do player(p) end
Tags:GetInstanceAddedSignal('RogueliteZombie'):Connect(function(m) bind(m,'RogueliteZombies') end)
for _,m in Tags:GetTagged('RogueliteZombie') do bind(m,'RogueliteZombies') end
