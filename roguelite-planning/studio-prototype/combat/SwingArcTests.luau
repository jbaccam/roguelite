-- Fresh WeaponMotion plus reviewed WeaponTemplates keyed by weapon id. Pure geometry only.
return function(Motion, templates)
	local checks = 0
	local function check(ok, message)
		checks += 1
		assert(ok, message)
	end
	for _, id in { "01", "03", "05", "06", "16", "20", "26", "27", "40" } do
		local template = assert(templates[id], "Missing template " .. id)
		local size, boundsCenter = template:GetAttribute("BoundsSize"), template:GetAttribute("BoundsCenter")
		check(typeof(size) == "Vector3" and typeof(boundsCenter) == "Vector3", "Reviewed bounds " .. id)
		for _, yaw in { 0, math.pi / 2, math.pi, -math.pi / 2 } do
			for _, side in { -1, 1 } do
				for _, distance in { 2, 6, 12 } do
					for _, visual in { false, true } do
						local root = CFrame.new(10, 5, 20) * CFrame.Angles(0, yaw, 0)
						local forward = Motion.frame(root).LookVector
						local center = Motion.combatOrigin(root, 6.2, 1, id, "Melee")
						local frame = CFrame.lookAt(center, center + forward)
						local aim = center + forward * distance
						local reach = 12
						local tip = size.Y * 0.5 + boundsCenter.Y
						local function pose(style, t)
							local age = Motion.SwingHitStart + (Motion.SwingHitEnd - Motion.SwingHitStart) * t
							return Motion.pose(
								root,
								6.2,
								1,
								aim,
								0,
								age,
								"Melee",
								id,
								forward,
								reach,
								size,
								boundsCenter,
								style,
								side,
								visual
							)
						end
						local widths = {}
						for _, style in { "Horizontal", "Diagonal" } do
							local lo, hi = math.huge, -math.huge
							for sample = 0, 64 do
								local cf, active = pose(style, sample / 64)
								local localPoint = frame:PointToObjectSpace(cf.Position)
								lo, hi = math.min(lo, localPoint.X), math.max(hi, localPoint.X)
								local strike = frame:PointToObjectSpace(cf:PointToWorldSpace(Vector3.yAxis * tip))
								check(
									Vector2.new(strike.X, strike.Z).Magnitude <= reach + 0.01,
									"Bounded striking reach " .. id
								)
								check(math.abs(localPoint.Y) <= 1.71, "No oversized swing height " .. id)
								check(active, "Both paths use the authoritative hit window " .. id)
							end
							widths[style] = hi - lo
						end
						check(
							widths.Diagonal >= widths.Horizontal * 0.9 and widths.Diagonal <= widths.Horizontal * 1.1,
							"Slash covers a comparable lateral footprint " .. id
						)
						local first = frame:PointToObjectSpace(pose("Diagonal", 0).Position)
						local last = frame:PointToObjectSpace(pose("Diagonal", 1).Position)
						check(
							first.X * side > 0.1 and last.X * side < -0.1,
							"Slash starts and follows through on opposite sides " .. id
						)
						check(first.Y > last.Y + 2, "Slash descends through its follow-through " .. id)
						check(
							math.abs(frame:PointToObjectSpace(pose("Diagonal", 0.5).Position).X) < 1e-4,
							"Slash crosses the locked aim " .. id
						)
						local horizontal = frame:PointToObjectSpace(pose("Horizontal", 0).Position)
						local bearing = math.abs(math.deg(math.atan2(-horizontal.X, -horizontal.Z)))
						local expected = visual and (id == "03" and 110 or 120) or 105
						check(
							math.abs(bearing - expected) < 0.001,
							"Only Katana's visual horizontal width narrows " .. id
						)
					end
				end
			end
		end
	end
	return { checks = checks }
end
