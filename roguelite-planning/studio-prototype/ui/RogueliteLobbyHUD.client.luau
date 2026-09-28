-- Lobby HUD entry point. Shows only while the server marks this player as in the lobby
-- (LobbyPreviewActive). Replaces the earlier text-only RogueliteLobbyNavigation menu.
local Players=game:GetService('Players')
local ReplicatedStorage=game:GetService('ReplicatedStorage')
local player=Players.LocalPlayer
-- Match servers have no lobby (ServerRole sets this attribute before players join).
local role=ReplicatedStorage:GetAttribute('ServerRole')
while role==nil do ReplicatedStorage:GetAttributeChangedSignal('ServerRole'):Wait();role=ReplicatedStorage:GetAttribute('ServerRole') end
if role=='Match' then return end
if player:WaitForChild('PlayerGui'):FindFirstChild('RogueliteLobbyHUD') then return end
local Lobby=require(ReplicatedStorage:WaitForChild('LobbyUI'))
Lobby.mount(player)
-- After the HUD is up: load every UI image and the map-select islands in the background.
require(ReplicatedStorage:WaitForChild('AssetPreloader')).start(player)
