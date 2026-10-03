-- X/Z broad phase for the existing 4.5-stud separation rule. Rebuilt lazily once per
-- simulation frame. Distances are exact; neighbours are summed in cell order.
-- (Launch audit P9: each call used to copy its neighbours into a new list and sort them back
-- into folder order, only to keep the float sum in the old order. The order changes the result
-- by about 1e-6 of a stud; EnemySpatialGridTests checks it against the old way.)
local Grid = {}
Grid.__index = Grid

function Grid.new(folder, radius)
	assert(radius > 0, "Positive radius required")
	return setmetatable({folder = folder, radius = radius}, Grid)
end

function Grid:invalidate()
	self.cells = nil
end

function Grid:rebuild()
	local cells = {}
	for _, npc in self.folder:GetChildren() do
		local root = npc:FindFirstChild("HumanoidRootPart")
		if root and root:IsA("BasePart") then
			local position = root.Position
			local x, z = math.floor(position.X / self.radius), math.floor(position.Z / self.radius)
			local column = cells[x]
			if not column then column = {}; cells[x] = column end
			local cell = column[z]
			if not cell then cell = {}; column[z] = cell end
			table.insert(cell, {npc = npc, position = position})
		end
	end
	self.cells = cells
end

-- The push away from neighbours closer than the radius, and how many neighbours were measured.
function Grid:separation(npc, position)
	if not self.cells then self:rebuild() end
	local radius, folder = self.radius, self.folder
	local x, z = math.floor(position.X / radius), math.floor(position.Z / radius)
	local separation = Vector3.zero
	local checks = 0
	for dx = -1, 1 do
		local column = self.cells[x + dx]
		if column then
			for dz = -1, 1 do
				local cell = column[z + dz]
				if cell then
					for _, entry in cell do
						if entry.npc ~= npc and entry.npc.Parent == folder then
							checks += 1
							local delta = position - entry.position
							delta = Vector3.new(delta.X, 0, delta.Z)
							local spacing = delta.Magnitude
							if spacing > 0.01 and spacing < radius then
								separation += delta.Unit * (1 - spacing / radius)
							end
						end
					end
				end
			end
		end
	end
	return separation, checks
end

return Grid
