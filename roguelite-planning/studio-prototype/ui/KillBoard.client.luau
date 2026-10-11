-- The in-run kill board (ReplicatedStorage.KillBoard): everyone's kills this run (solo: just yours),
-- unless Settings > Kill board is OFF. Its own script, so it can never stall the HUD.
local RS=game:GetService('ReplicatedStorage')
local ok,err=pcall(function() require(RS:WaitForChild('KillBoard')).mount(game:GetService('Players').LocalPlayer) end)
if not ok then warn('KillBoard failed to start:',err) end
