-- X/Z broad phase for the existing 4.5-stud separation rule. Rebuilt lazily
-- once per simulation frame; exact distances and original child order are retained.
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
	local entries = {}
	for order, npc in self.folder:GetChildren() do
		local root = npc:FindFirstChild("HumanoidRootPart")
		if root and root:IsA("BasePart") then
			local position = root.Position
			local x, z = math.floor(position.X / self.radius), math.floor(position.Z / self.radius)
			local column = cells[x]
			if not column then column = {}; cells[x] = column end
			local cell = column[z]
			if not cell then cell = {}; column[z] = cell end
			local entry = {npc = npc, position = position, order = order}
			table.insert(cell, entry)
			table.insert(entries, entry)
		end
	end
	self.cells = cells
	self.entries = entries
end

function Grid:separation(npc, position)
	if not self.cells then self:rebuild() end
	local radius = self.radius
	local x, z = math.floor(position.X / radius), math.floor(position.Z / radius)
	local nearby = {}
	for dx = -1, 1 do
		local column = self.cells[x + dx]
		if column then
			for dz = -1, 1 do
				for _, entry in column[z + dz] or {} do
					if entry.npc ~= npc and entry.npc.Parent == self.folder then
						table.insert(nearby, entry)
					end
				end
			end
		end
	end
	-- Keep floating-point accumulation identical to the old folder traversal.
	-- Dense piles get little benefit from a grid. The cached ordered list avoids
	-- sorting a nearly full crowd while still avoiding repeated Instance searches.
	if #nearby > #self.entries / 2 then
		nearby = self.entries
	else
		table.sort(nearby, function(a, b) return a.order < b.order end)
	end
	local separation = Vector3.zero
	local checks = 0
	for _, entry in nearby do
		if entry.npc == npc or entry.npc.Parent ~= self.folder then continue end
		checks += 1
		local delta = position - entry.position
		delta = Vector3.new(delta.X, 0, delta.Z)
		local spacing = delta.Magnitude
		if spacing > 0.01 and spacing < radius then
			separation += delta.Unit * (1 - spacing / radius)
		end
	end
	return separation, checks
end

return Grid
