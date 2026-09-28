-- Studio lobby preview client: keeps combat overlays out of the lobby, and draws the
-- Studio-only LOBBY / ARENA travel switch (hotkey F8) shown in both areas.
if not game:GetService('RunService'):IsStudio() then return end
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

-- Travel switch, top-right (free in the lobby HUD, the arena HUD and the shop); the current
-- area is lit. The server moves only the caller.
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
