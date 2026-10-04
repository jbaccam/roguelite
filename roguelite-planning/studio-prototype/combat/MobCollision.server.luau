-- Players cannot stand on mobs or on each other; mobs still collide with arena geometry.
local Physics=game:GetService('PhysicsService')
local Players=game:GetService('Players')
local Tags=game:GetService('CollectionService')
for _,name in {'RoguelitePlayers','RogueliteZombies'} do
 if not Physics:IsCollisionGroupRegistered(name) then Physics:RegisterCollisionGroup(name) end
end
Physics:CollisionGroupSetCollidable('RoguelitePlayers','RogueliteZombies',false)
Physics:CollisionGroupSetCollidable('RogueliteZombies','RogueliteZombies',false)
-- Players stacked on each other's heads into a "tower" in the 2026-10-03 friends play-test; teammates
-- now pass through each other (still solid against the arena, scenery and lobby dummies).
Physics:CollisionGroupSetCollidable('RoguelitePlayers','RoguelitePlayers',false)
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
-- Lobby practice dummies are solid scenery; players must not walk through them.
local function mob(m) if not m:GetAttribute('LobbyDummy') then bind(m,'RogueliteZombies') end end
Tags:GetInstanceAddedSignal('RogueliteZombie'):Connect(mob)
for _,m in Tags:GetTagged('RogueliteZombie') do mob(m) end
