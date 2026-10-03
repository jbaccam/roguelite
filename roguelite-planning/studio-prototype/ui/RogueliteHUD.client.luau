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
-- Roblox's own UI around the HUD (launch audit U2): no health bar (the HUD has its own) and no
-- player list on any device (the party strip and pause screen show the party). SetCoreGuiEnabled
-- can fail until the core scripts load, so each retries.
task.spawn(function()
 for _,kind in {Enum.CoreGuiType.Health,Enum.CoreGuiType.PlayerList} do
  for _=1,10 do
   if pcall(function() StarterGui:SetCoreGuiEnabled(kind,false) end) then break end
   task.wait(0.2)
  end
 end
end)
-- Chat (TextChatService) sits top-left by default: over the health and XP block in a run and the
-- quest tracker in the lobby. With a keyboard it moves to the middle of the left edge in a run
-- (under the health block, clear of the timer and the boss bar) and bottom-left in the lobby (left
-- of the PLAY row). Phones keep Roblox's chat button, whose window only opens when tapped.
task.spawn(function()
 local window=game:GetService('TextChatService'):WaitForChild('ChatWindowConfiguration',10);if not window then return end
 local Input=game:GetService('UserInputService')
 local function place()
  if Input.TouchEnabled and not Input.KeyboardEnabled then return end
  local lobby=player:GetAttribute('LobbyPreviewActive')==true
  pcall(function()
   window.HorizontalAlignment=Enum.HorizontalAlignment.Left
   window.VerticalAlignment=lobby and Enum.VerticalAlignment.Bottom or Enum.VerticalAlignment.Center
   window.WidthScale=.85;window.HeightScale=lobby and .8 or .9
  end)
 end
 place();player:GetAttributeChangedSignal('LobbyPreviewActive'):Connect(place)
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
-- ButtonB closes even when processed: with a menu button selected, the gamepad's GUI navigation
-- marks B as handled, which would otherwise make it never close the menu.
UserInputService.InputBegan:Connect(function(input,processed)
 if input.KeyCode==Enum.KeyCode.ButtonB and not UserInputService:GetFocusedTextBox() then view:Close() return end
 if processed then return end
 if input.KeyCode==Enum.KeyCode.Escape then view:Close() end
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
 -- The tutorial's waves have no clock (they end once cleared): no countdown, BOSS while he's up.
 local combatFolder=ReplicatedStorage:FindFirstChild('RogueliteCombat')
 if state and combatFolder and combatFolder:GetAttribute('TutorialRun')==true then
  remaining=nil;bossLabel=state:GetAttribute('BossHolding')==true and 'BOSS' or nil
 end
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
 -- The nearest living boss in this arena; kiting it across the map keeps the bar up.
 local selected,health;local nearest=600
 if root and activeHumanoid and activeHumanoid.Health>0 then
  for _,tag in {'HammerBoss','MapBoss'} do for _,npc in game:GetService('CollectionService'):GetTagged(tag) do
   local h=npc:FindFirstChildOfClass('Humanoid');local part=npc.PrimaryPart
   if npc:IsDescendantOf(workspace) and h and h.Health>0 and part then
    local distance=(part.Position-root.Position).Magnitude
    if distance<nearest then selected,health,nearest=npc,h,distance end
   end
  end end
 end
 view:SetBossHealth(selected,health and health.Health,health and health.MaxHealth)
end)
-- Frame rate for play-test analytics (RunAnalytics FrameRate / FrameDips): while this player is in a
-- run and a wave is on, count rendered frames; when the wave ends, send the average FPS, how many
-- seconds fell under 30, and the kind of device. Spawned and self-contained, so it can never stall
-- the HUD; an older server without PerfReport just means no reports.
task.spawn(function()
 local combat=ReplicatedStorage:WaitForChild('RogueliteCombat')
 local report=combat:WaitForChild('PerfReport',60)
 if not report then return end
 local function device()
  if UserInputService.GamepadEnabled and not UserInputService.KeyboardEnabled and not UserInputService.TouchEnabled then return 'Console' end
  if UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled then
   local v=workspace.CurrentCamera.ViewportSize
   return math.min(v.X,v.Y)>=700 and 'Tablet' or 'Phone'
  end
  return 'Desktop'
 end
 local frames,time,dips,secondFrames,secondTime=0,0,0,0,0
 local counting=false
 RunService.RenderStepped:Connect(function(dt)
  local state=ReplicatedStorage:FindFirstChild('RogueliteRunState')
  local on=state~=nil and state:GetAttribute('Phase')=='Combat' and player:GetAttribute('RunMember')==true
  if on then
   frames+=1;time+=dt;secondFrames+=1;secondTime+=dt
   if secondTime>=1 then
    if secondFrames/secondTime<30 then dips+=1 end
    secondFrames,secondTime=0,0
   end
  elseif counting then
   -- The wave just ended (or this player left the run): one report for it, if it lasted 5 s.
   if time>=5 then report:FireServer(math.clamp(math.floor(frames/time+.5),1,1000),math.min(dips,3600),device()) end
   frames,time,dips,secondFrames,secondTime=0,0,0,0,0
  end
  counting=on
 end)
end)
