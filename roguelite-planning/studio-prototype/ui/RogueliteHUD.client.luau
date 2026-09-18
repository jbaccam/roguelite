-- Live health presentation. Studio previews never modify gameplay state.
local Players=game:GetService("Players")
local ReplicatedStorage=game:GetService("ReplicatedStorage")
local StarterGui=game:GetService("StarterGui")
local RunService=game:GetService("RunService")
local UserInputService=game:GetService("UserInputService")
local player=Players.LocalPlayer
local UI=require(ReplicatedStorage:WaitForChild("RogueliteUI"))
local playerGui=player:WaitForChild("PlayerGui")
if playerGui:FindFirstChild("RogueliteHUD") then return end
local view=UI.mount(playerGui,RunService:IsStudio())
task.spawn(function()
 for _=1,10 do
  if pcall(function() StarterGui:SetCoreGuiEnabled(Enum.CoreGuiType.Health,false) end) then break end
  task.wait(0.2)
 end
end)
local connections={}
local generation=0
local activeHumanoid=nil
local function disconnect()
 for _,c in connections do c:Disconnect() end
 table.clear(connections);activeHumanoid=nil
end
local function bindCharacter(character)
 generation+=1;local ownGeneration=generation
 disconnect();view:SetHealth(0,0,true)
 local humanoid=character:WaitForChild("Humanoid",15)
 if not humanoid or ownGeneration~=generation or character~=player.Character then return end
 activeHumanoid=humanoid
 local function update(immediate)
  view:SetHealth(humanoid.Health,humanoid.MaxHealth,immediate)
  view:SetStats(humanoid.MaxHealth,humanoid.WalkSpeed)
 end
 table.insert(connections,humanoid.HealthChanged:Connect(function() update(false) end))
 table.insert(connections,humanoid:GetPropertyChangedSignal("MaxHealth"):Connect(function() update(false) end))
 table.insert(connections,humanoid:GetPropertyChangedSignal("WalkSpeed"):Connect(function() view:SetStats(humanoid.MaxHealth,humanoid.WalkSpeed) end))
 table.insert(connections,humanoid.Died:Connect(function() view:SetHealth(0,humanoid.MaxHealth,false);view:Close() end))
 update(true)
end
player.CharacterAdded:Connect(bindCharacter)
player.CharacterRemoving:Connect(function()
 generation+=1;disconnect();view:SetHealth(0,0,true);view:Close()
end)
if player.Character then task.spawn(bindCharacter,player.Character) end
UserInputService.InputBegan:Connect(function(input,processed)
 if processed then return end
 if input.KeyCode==Enum.KeyCode.Escape or input.KeyCode==Enum.KeyCode.ButtonB then view:Close() end
end)
-- Future run service may publish these attributes on ReplicatedStorage.RogueliteRunState.
-- No fabricated wave countdown or progression in the five-chaser practice scene.
local elapsed=0
RunService.Heartbeat:Connect(function(dt)
 elapsed+=dt;if elapsed<0.1 then return end;elapsed=0
 local state=ReplicatedStorage:FindFirstChild("RogueliteRunState")
 local endsAt=state and state:GetAttribute("WaveEndsAt")
 local wave=state and state:GetAttribute("Wave")
 local phase=state and state:GetAttribute("Phase")
 if type(phase)~="string" then phase="Practice" end
 local validTime=type(endsAt)=="number" and endsAt==endsAt and math.abs(endsAt)<1e12
 local validWave=type(wave)=="number" and wave==wave and wave>=1 and wave<1e6
 view:SetTimer(validTime and math.max(0,endsAt-workspace:GetServerTimeNow()) or nil,validWave and math.floor(wave) or nil,phase)
 if activeHumanoid then view:SetStats(activeHumanoid.MaxHealth,activeHumanoid.WalkSpeed) end
end)
