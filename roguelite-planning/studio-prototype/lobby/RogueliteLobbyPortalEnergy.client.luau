-- Animates the lobby portals' energy (exported from Studio 2026-09-28; the installer isn't in the repo): plays the 4 x 4 flipbook slowly
-- (4 frames per second, one 16-frame loop every 4 s), cross-fading each frame into the next so the slow speed
-- stays smooth, and spins it very slowly so it drifts rather than churns. Purely cosmetic and client-side;
-- reads no gameplay state.
local RunService = game:GetService('RunService')
-- Match servers have no lobby (ServerRole).
local RS = game:GetService('ReplicatedStorage')
local role = RS:GetAttribute('ServerRole')
while role == nil do RS:GetAttributeChangedSignal('ServerRole'):Wait(); role = RS:GetAttribute('ServerRole') end
if role == 'Match' then return end
local root = workspace:WaitForChild('RogueliteLobby')
local portals = root:WaitForChild('Portals')

local FPS, FRAMES, CELL, SPIN = 4, 16, 256, 4 -- SPIN in degrees per second
local BASE_TRANSPARENCY = .04

local layers = {}
local function offset(frame)
	return Vector2.new((frame % 4) * CELL, math.floor(frame / 4) * CELL)
end
local function collect()
	table.clear(layers)
	for _, d in portals:GetDescendants() do
		if d:IsA('ImageLabel') and d.Name == 'Energy' and d.Parent and d.Parent.Name == 'PortalEnergy' then
			-- A second copy on top fades in the next frame.
			local blend = d.Parent:FindFirstChild('EnergyBlend')
			if not blend then
				blend = d:Clone(); blend.Name = 'EnergyBlend'; blend.ZIndex = d.ZIndex + 1; blend.Parent = d.Parent
			end
			-- Front and back faces spin opposite ways in screen space, so both read as the same vortex.
			local sign = d.Parent.Face == Enum.NormalId.Left and -1 or 1
			table.insert(layers, { base = d, blend = blend, sign = sign, phase = #layers * 1.7 })
		end
	end
end
collect()
portals.DescendantAdded:Connect(function(d)
	if d:IsA('ImageLabel') and d.Name == 'Energy' then task.defer(collect) end
end)

RunService.RenderStepped:Connect(function()
	local t = os.clock()
	for _, e in layers do
		local f = (t + e.phase) * FPS
		local frame = math.floor(f) % FRAMES
		e.base.ImageRectOffset = offset(frame)
		e.blend.ImageRectOffset = offset((frame + 1) % FRAMES)
		e.blend.ImageTransparency = 1 - (f % 1) * (1 - BASE_TRANSPARENCY)
		local rot = (t * SPIN * e.sign) % 360
		e.base.Rotation = rot; e.blend.Rotation = rot
	end
end)
