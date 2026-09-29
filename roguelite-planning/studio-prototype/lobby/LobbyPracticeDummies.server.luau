-- The lobby's practice dummies become harmless targets at runtime: equipped weapons
-- auto-attack them (each player can switch that off with T / the ATTACKS button),
-- hits show damage numbers, and they never die, move or pay out (ZombieDeath.isPractice).
-- The authored mesh keeps its place and collision; only its parent changes in play.
local Tags=game:GetService('CollectionService')
local lobby=workspace:WaitForChild('RogueliteLobby',30)
local scenery=lobby and lobby:WaitForChild('Scenery',30)
if not scenery then return end
local function wrap(mesh)
 if not mesh:IsA('BasePart') or mesh:GetAttribute('Asset')~='Practice_Dummy' then return end
 if mesh.Parent:GetAttribute('LobbyDummy') then return end
 local model=Instance.new('Model');model.Name=mesh.Name
 -- Invisible target volume: weapons aim at its centre and melee boxes overlap it.
 local root=Instance.new('Part');root.Name='HumanoidRootPart';root.Size=mesh.Size;root.CFrame=mesh.CFrame
 root.Anchored=true;root.CanCollide=false;root.CanTouch=false;root.CanQuery=true;root.Transparency=1;root.Parent=model
 -- No part is named Head, so Roblox draws no name or health bar over it.
 local h=Instance.new('Humanoid');h.EvaluateStateMachine=false;h.RequiresNeck=false;h.BreakJointsOnDeath=false
 -- Practice hits never drop health below 1, so any large pool reads as endless.
 h.MaxHealth=1e6;h.Health=1e6;h.WalkSpeed=0;h.Parent=model
 model.PrimaryPart=root
 model:SetAttribute('PracticeTarget',true);model:SetAttribute('LobbyDummy',true)
 model:SetAttribute('PracticeHits',0);model:SetAttribute('PracticeDamage',0)
 model.Parent=scenery
 mesh.Parent=model
 -- Attributes first: MobCollision and the client read them when the tags arrive.
 Tags:AddTag(model,'LobbyPracticeDummy')
 Tags:AddTag(model,'RogueliteZombie')
end
for _,child in scenery:GetChildren() do wrap(child) end
scenery.ChildAdded:Connect(wrap)
