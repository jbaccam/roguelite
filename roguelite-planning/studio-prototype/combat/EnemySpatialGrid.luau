-- X/Z broad phase for the existing 4.5-stud separation rule. Rebuilt lazily once per
-- simulation frame. Distances are exact; neighbours are summed in cell order.
-- (Launch audit P9: each call used to copy its neighbours into a new list and sort them back
-- into folder order, only to keep the float sum in the old order. The order changes the result
-- by about 1e-6 of a stud; EnemySpatialGridTests checks it against the old way.)
local Grid = {}
Grid.__index = Grid
local function active(npc, folder)
    return npc.Parent == folder and not (npc.GetAttribute and npc:GetAttribute('DeathPopped'))
end

function Grid.new(folder, radius, clock)
	assert(radius > 0, "Positive radius required")
	return setmetatable({folder = folder, radius = radius, ids = setmetatable({}, {__mode = "k"}), nextId = 0, clock = clock or os.clock, steering = setmetatable({}, {__mode = "k"})}, Grid)
end

function Grid:invalidate()
	self.cells = nil
end

function Grid:rebuild()
	local cells, bosses, entries, maxBody = {}, {}, {}, 1
	for _, npc in self.folder:GetChildren() do
		if not active(npc, self.folder) then continue end
		local root = npc:FindFirstChild("HumanoidRootPart")
		if root and root:IsA("BasePart") then
			local position = root.Position
			local x, z = math.floor(position.X / self.radius), math.floor(position.Z / self.radius)
			local column = cells[x]
			if not column then column = {}; cells[x] = column end
			local cell = column[z]
			if not cell then cell = {}; column[z] = cell end
			if not self.ids[npc] then self.nextId += 1; self.ids[npc] = self.nextId end
            local boss = npc.GetAttribute and npc:GetAttribute('IsBoss') == true
            local body = npc.GetAttribute and npc:GetAttribute('CrowdRadius')
            if not body then
                local torso = npc:FindFirstChild('UpperTorso') or npc:FindFirstChild('Torso') or root
                local size = torso.Size or Vector3.new(3, 3, 3)
                body = math.clamp(math.max(size.X, size.Z) * .5 + .4, boss and 4 or 1.2, boss and 14 or 3.5)
            end
            local entry = {npc = npc, position = position, body = body, id = self.ids[npc], boss = boss}
            entries[npc] = entry
            table.insert(cell, entry)
            if boss then table.insert(bosses, entry) else maxBody = math.max(maxBody, body) end
		end
	end
	self.cells, self.bosses, self.entries, self.maxBody = cells, bosses, entries, maxBody
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

-- Body-aware local steering for normal mobs. Bosses are moving obstacles, not another
-- small point in the 4.5-stud separation radius. No forces/teleports or damage decisions.
function Grid:steer(npc, position, goal, stopRange)
    if not self.cells then self:rebuild() end
    local now = self.clock()
    local state = self.steering[npc]
    if not state or now-state.at>.6 or (position-state.position).Magnitude>12 or (goal-state.goal).Magnitude>30 then
        state = {at=now-.1, position=position, goal=goal, sides=setmetatable({}, {__mode="k"})}
        self.steering[npc]=state
    end
    local elapsed=math.clamp(now-state.at,0,.15)
    state.at, state.position, state.goal=now,position,goal
    local ownId = self.ids[npc] or 1
    local ownBody = self.entries[npc] and self.entries[npc].body or 1.5
    local delta = Vector3.new(goal.X-position.X, 0, goal.Z-position.Z)
    local distance = delta.Magnitude
    -- Ease into attack distance instead of alternating full chase and full stop each think.
    local desired = distance > stopRange and distance > .01 and delta.Unit*math.clamp((distance-stopRange)/2.5,0,1) or Vector3.zero
    local push = Vector3.zero
    local bossBoundaries = {}
    local reach = ownBody + self.maxBody + 1.5
    local x, z = math.floor(position.X/self.radius), math.floor(position.Z/self.radius)
    local span = math.ceil(reach/self.radius)
    for dx=-span,span do
        local column = self.cells[x+dx]
        if not column then continue end
        for dz=-span,span do
            for _, entry in column[z+dz] or {} do
                if entry.npc == npc or entry.boss or not active(entry.npc, self.folder) then continue end
                local away = Vector3.new(position.X-entry.position.X,0,position.Z-entry.position.Z)
                local spacing, clearance = away.Magnitude, ownBody+entry.body+1.5
                if spacing >= clearance then continue end
                if spacing < .01 then
                    -- Equal centers need opposite, stable escape directions, not zero force.
                    local a,b=math.min(ownId,entry.id),math.max(ownId,entry.id)
                    local angle=(a*2.399963+b*.754878)%(math.pi*2)
                    away=Vector3.new(math.cos(angle),0,math.sin(angle))*(ownId<entry.id and 1 or -1)
                else away=away.Unit end
                push += away * ((clearance-spacing)/clearance) * 3
            end
        end
    end
    -- Keep boss silhouette/body clear. Start taking a side before reaching its boundary;
    -- radial repulsion alone creates a stationary pile on the boss's trailing edge.
    for _, boss in self.bosses do
        if boss.npc == npc or not active(boss.npc, self.folder) then continue end
        local away=Vector3.new(position.X-boss.position.X,0,position.Z-boss.position.Z)
        local spacing=away.Magnitude
        local clearance=ownBody+boss.body+1
        if spacing > clearance+12 then state.sides[boss.npc]=nil;continue end
        away=spacing>.01 and away.Unit or Vector3.new(math.cos(ownId*2.399963),0,math.sin(ownId*2.399963))
        local heading=desired.Magnitude>.01 and desired.Unit or Vector3.zero
        local along=-away:Dot(heading)*spacing
        local lateral=math.sqrt(math.max(0,spacing*spacing-along*along))
        local side=state.sides[boss.npc]
        if side and (along < -1 or lateral > clearance+3) then state.sides[boss.npc]=nil;side=nil end
        if desired.Magnitude>.01 and along>0 and lateral<clearance+1 and spacing<clearance+10 then
            local tangent=Vector3.new(-away.Z,0,away.X)
            if not side then
                local toward=tangent:Dot(heading)
                side=(toward<-.05 or math.abs(toward)<=.05 and ownId%2==0) and -1 or 1
                state.sides[boss.npc]=side
            end
            desired=(tangent*side+.55*away).Unit
        elseif side and desired.Magnitude>.01 and along>0 and lateral<clearance+3 then
            -- Wider release band prevents straight/bypass oscillation at the edge of the boss.
            local tangent=Vector3.new(-away.Z,0,away.X)*side
            desired=(tangent+.55*away).Unit
        end
        if spacing<clearance+.8 then
            table.insert(bossBoundaries, {away=away, outward=math.clamp((clearance+.5-spacing)/1.5,0,1)})
        end
    end
    local direction=desired+push
    if direction.Magnitude>1 then direction=direction.Unit end
    -- Bound changes in the actual requested movement, not physics forces. Each mob keeps its
    -- own command history across grid rebuilds; elapsed time makes this independent of tick rate.
    if state.command and direction.Magnitude>.025 then
        local correction=(direction-state.command)*(1-math.exp(-elapsed/.24))
        local limit=3.5*elapsed
        if correction.Magnitude>limit then correction=correction.Unit*limit end
        direction=state.command+correction
    elseif direction.Magnitude<=.025 then direction=Vector3.zero end
    -- Other mobs cannot push this one through the boss body: remove the inward component
    -- after summing crowd pressure, retaining tangential motion around the silhouette.
    for _, boundary in bossBoundaries do
        local radial=direction:Dot(boundary.away)
        if radial<boundary.outward then direction+=boundary.away*(boundary.outward-radial) end
    end
    -- A nearly balanced crowd slows instead of normalizing tiny vectors into full-speed jitter.
    if direction.Magnitude>1 then direction=direction.Unit end
    state.command=direction
    return direction
end

return Grid
