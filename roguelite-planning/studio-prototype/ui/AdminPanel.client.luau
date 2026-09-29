-- ADMIN panel launcher (ADMIN_PANEL.md). Developers only: adds the ADMIN button to the arena HUD's
-- launcher column and the lobby HUD's right-side buttons, and binds P. Showing it is cosmetic:
-- AdminService checks the developer on every request.
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
Input.InputBegan:Connect(function(input,processed)
 if processed or Input:GetFocusedTextBox() or input.KeyCode~=Enum.KeyCode.P then return end
 panel.Toggle()
end)
-- Studio-only hook so checks can open a tab without keyboard input (like LobbyUI's TestOpenWindow).
if RunService:IsStudio() then
 local hook=Instance.new('BindableEvent');hook.Name='TestShow';hook.Parent=panel.Screen
 hook.Event:Connect(function(tab) if tab then panel.Show(tab) else panel.Close() end end)
end
