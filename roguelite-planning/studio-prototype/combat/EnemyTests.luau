return function(Catalog, Motion, NativeMotion, animationFolder)
	local checks = 0
	local clips = 0
	local samples = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	check(#Catalog.List == 21, "Roster must contain exactly 21 regular enemies")
	check(Catalog.get("HammerBoss") == nil and Catalog.get("pharaoh") == nil, "Bosses must stay excluded")
	check(Catalog.scaled("regular-zombie", 1).health == 3, "Preserve regular starting HP")
	check(Catalog.scaled("baby-zombie", 1).health == 1, "Preserve baby starting HP")
	check(Catalog.scaled("tank-zombie", 8).health == 97, "Preserve wave 8 tank HP")
	check(Catalog.scaled("tank-zombie", 1).health == 80, "Early tanks keep an 80 HP floor")
	check(Catalog.get("Baby").speed == 20 and Catalog.get("Mutant").speed == 12.5, "Native zombies use wave-ready speeds")
	check(Catalog.forSlot(2, 1) == "baby-zombie", "Default Pine Valley roster unchanged")
	check(Catalog.forSlot(1, 1, "bogus,snake,crab") == "snake", "Unknown explicit roster entries ignored")
	check(Catalog.forSlot(3, 1, "snake,crab") == "snake", "Explicit roster cycles")
	check(
		Catalog.get("snake").hitRange < Catalog.get("snake").attackRange,
		"Lunge warning range must not become damage radius"
	)
	-- 2026-10-01 movement pass: only the floating ghost animates by time (snake and slime pace by
	-- the ground), nobody turns off its target to attack, and crabs chase straight.
	check(Catalog.get("snake").gaitStride and Catalog.get("lava-slime").gaitStride, "Snake and slime pace by ground")
	for _, d in Catalog.List do
		check(d.timeBasedMovement == (d.id == "frost-ghost"), "Only the ghost animates by time: " .. d.id)
		check(d.attackFacingYaw == nil and d.leadTime == nil, "Attacks and chases face the target: " .. d.id)
	end
	for _, d in Catalog.List do
		check(d.health > 0 and d.speed > 0 and d.damage >= 0, "Positive bounded tuning: " .. d.id)
		check(
			d.attackImpact > 0 and d.attackImpact < d.attackRecovery and d.attackRecovery < d.attackCooldown,
			"Ordered attack timing: " .. d.id
		)
		check(d.legacy ~= nil or d.balanceStatus == "Provisional playtest baseline", "New balance status explicit")
		if not d.legacy and animationFolder then
			local source = animationFolder:FindFirstChild(d.id)
			check(source ~= nil, "Missing retargeted animation module: " .. d.id)
			local data = Motion.compile(require(source))
			check(data.motion.strideLength > 0, "Positive measured gait stride: " .. d.id)
			local shot = data.projectile and data.projectile.releaseDirectionLocal
			if shot then
				-- Square to the target (square_bow_skeleton.py): the shot leaves within 5 degrees of ahead.
				check((data.projectile.attackFacingYaw or 0) == 0 and -shot[3] > 0.996, "Shot leaves straight ahead: " .. d.id)
			end
			for _, name in { "Idle", "Move", "Attack" } do
				local clip = data.clips[name]
				clips += 1
				for i = 0, 20 do
					local poses = Motion.sample(data, name, clip.duration * i / 20)
					samples += 1
					for bone in data.bones do
						check(poses[bone] ~= nil, "Missing bone " .. bone)
						for _, v in { poses[bone]:GetComponents() } do
							check(v == v and math.abs(v) < 100, "Finite bounded imported pose")
						end
					end
				end
				if clip.loop then
					local a, b = Motion.sample(data, name, 0), Motion.sample(data, name, clip.duration)
					for bone, p in a do
						check(
							(p.Position - b[bone].Position).Magnitude < 1e-6
								and p.LookVector:Dot(b[bone].LookVector) > 0.99999,
							"Loop wrap mismatch"
						)
					end
				end
			end
		end
	end
	for _, kind in { "Regular", "Baby", "Mutant" } do
		local rest = NativeMotion.pose(kind, 0, 0, 0, 0)
		check(select(1, rest.LeftKnee:ToOrientation()) < 0, "Bent idle knee: " .. kind)
		check(select(1, rest.Waist:ToOrientation()) < 0, "Forward combat lean: " .. kind)
		check(select(1, rest.LeftShoulder:ToOrientation()) < math.rad(45), "Relaxed idle arm: " .. kind)
		local a, b = NativeMotion.pose(kind, math.pi / 2, 1, 1, 0), NativeMotion.pose(kind, -math.pi / 2, 1, 1, 0)
		local hip = select(1, a.LeftHip:ToOrientation()) - select(1, b.LeftHip:ToOrientation())
		local shoulder = select(1, a.LeftShoulder:ToOrientation()) - select(1, b.LeftShoulder:ToOrientation())
		check(hip * shoulder < 0, "Same-side limbs must oppose: " .. kind)
	end
	return { checks = checks, regularTypes = #Catalog.List, clips = clips, poseSamples = samples }
end
