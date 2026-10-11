-- The in-run kill board (ReplicatedStorage.KillBoard): with 2+ players in the run, everyone's kills
-- this run under the build strip. Its own script, so it can never stall the HUD.
local RS=game:GetService('ReplicatedStorage')
local ok,err=pcall(function() require(RS:WaitForChild('KillBoard')).mount(game:GetService('Players').LocalPlayer) end)
if not ok then warn('KillBoard failed to start:',err) end
