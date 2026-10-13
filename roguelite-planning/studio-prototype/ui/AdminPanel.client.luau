-- ADMIN panel launcher (ADMIN_PANEL.md). Developers only: adds the ADMIN button to the arena HUD's
-- launcher column and the lobby HUD's right-side buttons, binds P, and closes on Escape / gamepad B.
-- Developers also get the admin chat commands (below) and the ';' command bar with Tab completion.
-- Showing it is cosmetic: AdminService checks the developer on every request.
local Players=game:GetService('Players')
local RS=game:GetService('ReplicatedStorage')
local RunService=game:GetService('RunService')
local Input=game:GetService('UserInputService')
local player=Players.LocalPlayer
local Admin=require(RS:WaitForChild('RogueliteCombat'):WaitForChild('AdminConfig'))
if not Admin.isAdmin(player) then return end
local T=require(RS:WaitForChild('UITheme'))
local panel=require(RS:WaitForChild('AdminPanelUI')).new(player)
local gui=player:WaitForChild('PlayerGui')
-- The spot in each HUD: RogueliteUI 'Menu' at LayoutOrder 5, right after SETTINGS; LobbyUI 'Right'
-- at LayoutOrder 6, after SETTINGS and the practice-dummy ATTACKS switch.
local SPOTS={RogueliteHUD={path={'SafeArea','HUD','Menu'},size=58,order=5},RogueliteLobbyHUD={path={'HUD','Right'},size=64,order=6}}
local function mount(screen)
 local spot=SPOTS[screen.Name];if not spot then return end
 local parent=screen
 for _,name in spot.path do parent=parent:WaitForChild(name,10);if not parent then return end end
 if parent:FindFirstChild('AdminButton') then return end
 local b=T.iconButton(parent,'AdminButton','profile','ADMIN',spot.size,panel.Toggle);b.LayoutOrder=spot.order
end
for _,screen in gui:GetChildren() do task.spawn(mount,screen) end
gui.ChildAdded:Connect(mount)
-- Escape in a number box ends the typing; that same press must not also close the panel.
local released=-1
Input.TextBoxFocusReleased:Connect(function() released=os.clock() end)
Input.InputBegan:Connect(function(input,processed)
 -- Escape and gamepad B close the panel, like the lobby windows (even when the game saw the key).
 if input.KeyCode==Enum.KeyCode.Escape or input.KeyCode==Enum.KeyCode.ButtonB then
  if not Input:GetFocusedTextBox() and os.clock()-released>.1 then panel.Close() end
  return
 end
 if processed or Input:GetFocusedTextBox() then return end
 -- ';' opens the admin command bar (2026-10-13): Tab-completes players, items, sets, slots and tiers.
 if input.KeyCode==Enum.KeyCode.Semicolon then panel.OpenBar();return end
 -- F2 (P was it until plan L made P the pause key for everyone).
 if input.KeyCode~=Enum.KeyCode.F2 then return end
 panel.Toggle()
end)
-- Chat commands (2026-10-12, AdminCommands: /tempgive, /give, /god, /pause, /admin). Made here, on
-- a developer's own client, so nobody else sees them in chat autocomplete; typing one sends its text
-- to AdminService (the Command action), which parses and checks it again. The reply shows as a
-- toast and as a system line in chat only this developer sees.
local TextChat=game:GetService('TextChatService')
local Commands=require(RS.RogueliteCombat:WaitForChild('AdminCommands'))
local function escape(text) return (string.gsub(string.gsub(string.gsub(text,'&','&amp;'),'<','&lt;'),'>','&gt;')) end
local function command(text)
 local good,message=panel.Command(text)
 local channels=TextChat:FindFirstChild('TextChannels');local general=channels and channels:FindFirstChild('RBXGeneral')
 if general and message~='' then
  pcall(general.DisplaySystemMessage,general,'<font color="'..(good and '#91EF14' or '#FF6969')..'">[Admin] '..escape(message)..'</font>')
 end
end
if TextChat.ChatVersion==Enum.ChatVersion.TextChatService then
 local holder=TextChat:FindFirstChild('TextChatCommands') or TextChat
 for _,name in Commands.Names do
  local c=Instance.new('TextChatCommand');c.Name='RogueliteAdmin_'..name;c.PrimaryAlias='/'..name
  c.Triggered:Connect(function(source,text) if source.UserId==player.UserId then task.spawn(command,text) end end)
  c.Parent=holder
 end
end
-- Studio-only hook so checks can open a tab without keyboard input (like LobbyUI's TestOpenWindow).
if RunService:IsStudio() then
 local hook=Instance.new('BindableEvent');hook.Name='TestShow';hook.Parent=panel.Screen
 hook.Event:Connect(function(tab) if tab then panel.Show(tab) else panel.Close() end end)
end
