-- Live health presentation. Studio previews never modify gameplay state.
local Players=game:GetService("Players")
local ReplicatedStorage=game:GetService("ReplicatedStorage")
local StarterGui=game:GetService("StarterGui")
local RunService=game:GetService("RunService")
local UserInputService=game:GetService("UserInputService")
local ContentProvider=game:GetService("ContentProvider")
local player=Players.LocalPlayer
local UI=require(ReplicatedStorage:WaitForChild("RogueliteUI"))
local playerGui=player:WaitForChild("PlayerGui")
if playerGui:FindFirstChild("RogueliteHUD") then return end
-- Request every image the shop and weapon inventory may show before the first reroll.
-- Keep this off the main thread so the HUD and character controls appear immediately.
task.spawn(function()
 local seen,images={},{}
 local function add(asset)
  if type(asset)~='string' or asset=='' or seen[asset] then return end
  seen[asset]=true
  local image=Instance.new('ImageLabel')
  image.Image=asset
  table.insert(images,image)
 end
 for _,asset in UI.Assets do add(asset) end
 local catalog=require(ReplicatedStorage:WaitForChild('RogueliteCombat'):WaitForChild('ShopCatalog'))
 for _,entry in catalog.List do
  if not entry.weaponId then add(UI.Assets[entry.icon] or entry.icon) end
 end
 local statIcons=require(ReplicatedStorage.RogueliteCombat.LevelUpCatalog)
 local schema=require(ReplicatedStorage.RogueliteCombat.CharacterStats)
 for _,d in schema.List do add(statIcons.icon(d.id)) end
 add(statIcons.icon('ShardBag'))
 local inventory=require(ReplicatedStorage:WaitForChild('WeaponInventoryUI'))
 for _,asset in inventory.Icons do add(asset) end
 playerGui:SetAttribute('ShopArtTotal',#images)
 local loaded=0
 ContentProvider:PreloadAsync(images,function(_,status)
  if status==Enum.AssetFetchStatus.Success then loaded+=1 end
 end)
 playerGui:SetAttribute('ShopArtLoaded',loaded)
 for _,image in images do image:Destroy() end
end)
local view=UI.mount(playerGui)
-- Match servers never run the lobby HUD, which starts the preloader everywhere else; warm the
-- shop, inventory and chest icons here. Spawned so a missing module can never stall this HUD.
task.spawn(function()
 local role=ReplicatedStorage:GetAttribute("ServerRole")
 while role==nil do ReplicatedStorage:GetAttributeChangedSignal("ServerRole"):Wait();role=ReplicatedStorage:GetAttribute("ServerRole") end
 if role=="Match" then require(ReplicatedStorage:WaitForChild("AssetPreloader")).start(player) end
end)
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
 local remaining=validTime and math.max(0,endsAt-workspace:GetServerTimeNow()) or nil
 -- Time is up but a boss is holding the wave open: the round ends when it falls.
 local bossLabel=remaining==0 and state:GetAttribute("BossHolding")==true and "BOSS" or nil
 -- Sandbox (phase Practice, from the admin panel): no countdown and no wave number.
 local practice=state~=nil and state:GetAttribute("Phase")=="Practice"
 view:SetTimer(not practice and remaining or nil,not practice and validWave and math.floor(wave) or nil,phase,practice and "SANDBOX" or bossLabel)
 -- A run where the admin panel was used pays no rewards (ADMIN_PANEL.md).
 view:SetTestRun(state~=nil and state:GetAttribute("AdminTestRun")==true)
 if activeHumanoid then view:SetStats(activeHumanoid.MaxHealth,activeHumanoid.WalkSpeed) end
 local combat=ReplicatedStorage:FindFirstChild('RogueliteCombat')
 local states=combat and combat:FindFirstChild('PlayerStates')
 local own=states and states:FindFirstChild(tostring(player.UserId))
 view:SetShards(own and own:GetAttribute('Shards') or 0,own and own:GetAttribute('BaggedShards') or 0)
 view:SetXP(own and own:GetAttribute('RunXP'),own and own:GetAttribute('RunXPRequired'),own and own:GetAttribute('RunLevel'))
 local root=player.Character and player.Character:FindFirstChild('HumanoidRootPart')
 local selected,health;local nearest=200
 if root and activeHumanoid and activeHumanoid.Health>0 then
  for _,npc in game:GetService('CollectionService'):GetTagged('HammerBoss') do
   local h=npc:FindFirstChildOfClass('Humanoid');local part=npc.PrimaryPart
   if npc:IsDescendantOf(workspace) and h and h.Health>0 and part then
    local distance=(part.Position-root.Position).Magnitude
    if distance<nearest then selected,health,nearest=npc,h,distance end
   end
  end
 end
 view:SetBossHealth(selected,health and health.Health,health and health.MaxHealth)
end)
