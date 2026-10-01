-- Lobby client: keeps combat overlays out of the lobby, holds a queued player on their pad, and
-- (Combined role only) draws the LOBBY / ARENA travel switch (hotkey F8) shown in both areas.
local Input=game:GetService('UserInputService')
local player=game:GetService('Players').LocalPlayer
local gui=player:WaitForChild('PlayerGui')
local T=require(game:GetService('ReplicatedStorage'):WaitForChild('UITheme'))
local hiddenNames={RogueliteHUD=true,LevelUpOffers=true,DamageFeedback=true,RogueliteCombatTestControls=true}
local tracked={}
local function update()
 local active=player:GetAttribute('LobbyPreviewActive')==true
 for screen,entry in tracked do
  if active then
   if entry.previous==nil then entry.previous=screen.Enabled end
   screen.Enabled=false
  elseif entry.previous~=nil then
   local previous=entry.previous;entry.previous=nil;screen.Enabled=previous
  end
 end
end
local function track(screen)
 if not screen:IsA('ScreenGui') or not hiddenNames[screen.Name] or tracked[screen] then return end
 local entry={};tracked[screen]=entry
 entry.connection=screen:GetPropertyChangedSignal('Enabled'):Connect(function()
  if player:GetAttribute('LobbyPreviewActive')==true and screen.Enabled then screen.Enabled=false end
 end)
 update()
end
for _,screen in gui:GetChildren() do track(screen) end
gui.ChildAdded:Connect(track)
gui.ChildRemoved:Connect(function(screen)
 local entry=tracked[screen];if entry then entry.connection:Disconnect();tracked[screen]=nil end
end)
player:GetAttributeChangedSignal('LobbyPreviewActive'):Connect(update)
update()

-- Match servers have no lobby (ServerRole parks it), so no pads or travel switch.
local RS=game:GetService('ReplicatedStorage')
local role=RS:GetAttribute('ServerRole')
while role==nil do RS:GetAttributeChangedSignal('ServerRole'):Wait();role=RS:GetAttribute('ServerRole') end
if role=='Match' then return end

-- Queued on a pad (LobbyQueue = portal id): walk and jump freely inside the ring, but its edge
-- holds like a wall until LEAVE. Runs after physics so the corrected spot is what renders.
local portals=workspace:WaitForChild('RogueliteLobby'):WaitForChild('Portals')
local function padOf(id)
 for _,portal in portals:GetChildren() do
  if portal:GetAttribute('PortalId')==id then return portal:GetAttribute('PadCenter'),portal:GetAttribute('PadRadius') end
 end
end
game:GetService('RunService').PostSimulation:Connect(function()
 local id=player:GetAttribute('LobbyQueue');if id==nil or player:GetAttribute('StudioArea')=='Arena' then return end
 local hrp=player.Character and player.Character:FindFirstChild('HumanoidRootPart');if not hrp then return end
 local center,radius=padOf(id)
 if typeof(center)~='Vector3' or type(radius)~='number' then return end
 local offset=hrp.Position-center
 -- Ignore a just-replicated teleport while the queue-clear attribute catches up.
 if offset.Magnitude>300 then return end
 local flat=Vector3.new(offset.X,0,offset.Z)
 if flat.Magnitude<=radius then return end
 local out=flat.Unit
 hrp.CFrame+=out*(radius-flat.Magnitude)
 local v=hrp.AssemblyLinearVelocity;local away=v:Dot(out)
 if away>0 then hrp.AssemblyLinearVelocity=v-out*away end
end)

-- Travel switch, top-right (free in the lobby HUD, the arena HUD and the shop); the current
-- area is lit. The server moves only the caller.
-- The switch only exists where the lobby and the maps share one server (ServerRole).
if role~='Combined' then return end
-- Developers travel from the ADMIN panel's Travel tab instead (ADMIN_PANEL.md).
if require(RS:WaitForChild('RogueliteCombat'):WaitForChild('AdminConfig')).isAdmin(player) then return end
local travel=workspace:WaitForChild('RogueliteLobby'):WaitForChild('StudioTravel')
local screen=T.make('ScreenGui',gui,{Name='StudioTravel',ResetOnSpawn=false,DisplayOrder=40,ScreenInsets=Enum.ScreenInsets.CoreUISafeInsets})
local frame=T.panel(screen,'Panel',0,0,200,46,'inset');frame.AnchorPoint=Vector2.new(1,0);frame.Position=UDim2.new(1,-12,0,6)
local buttons={}
local function go(area) travel:FireServer(area) end
for i,area in {'Lobby','Arena'} do
 local b=T.button(frame,area,string.upper(area),7+(i-1)*94,6,92,34,function() go(area) end,true)
 b.Caption.TextSize=16;buttons[area]=b
end
local function refresh()
 local here=player:GetAttribute('StudioArea')
 for area,b in buttons do T.setPrimary(b,area==here) end
end
player:GetAttributeChangedSignal('StudioArea'):Connect(refresh);refresh()
Input.InputBegan:Connect(function(input,processed)
 if processed or Input:GetFocusedTextBox() or input.KeyCode~=Enum.KeyCode.F8 then return end
 go(player:GetAttribute('StudioArea')=='Lobby' and 'Arena' or 'Lobby')
end)
