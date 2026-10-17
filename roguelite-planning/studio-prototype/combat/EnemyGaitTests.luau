-- NativeEnemyFeet.gait: when a regular enemy counts as walking (RogueliteZombieAnimation's Move vs
-- Idle). Pure numbers; run by run_enemy_gait_tests.py.
return function(Feet)
	local checks = 0
	local function check(condition, message)
		checks += 1
		assert(condition, message)
	end
	local frame = 1 / 60
	-- A zombie (catalog 16 studs/s) running flat: 0.27 studs in one frame.
	local distance, speed, walking = Feet.gait(0.27, 0, 0, frame, frame, 16, false)
	check(math.abs(distance - 0.27) < 1e-9 and math.abs(speed - 16.2) < 1e-6 and walking, "a flat run walks")
	-- The 2026-10-03 slide: FloorMaterial left at Air after a stall hop while it runs on the flat.
	_, _, walking = Feet.gait(0.27, 0, 0, frame, frame, 16, true)
	check(walking, "a stale Air FloorMaterial on flat ground still walks")
	-- Up a 25-degree slope at full speed: 7.5 studs/s vertical, under the 8 studs/s cutoff.
	_, _, walking = Feet.gait(0.25, 0.125, 0, frame, frame, 16, true)
	check(walking, "a slope under 8 studs/s vertical still walks with Air")
	-- Really airborne (a hop rises at 50 studs/s): not walking while FloorMaterial is Air...
	_, _, walking = Feet.gait(0.27, 50 * frame, 0, frame, frame, 16, true)
	check(not walking, "a hop in the air is not a walk")
	-- ...but the Humanoid saying it is on a floor wins over the vertical speed.
	_, _, walking = Feet.gait(0.27, 50 * frame, 0, frame, frame, 16, false)
	check(walking, "on a floor, vertical motion doesn't stop the walk")
	-- Standing still (or crowd jitter under 0.2 studs/s) idles.
	_, speed, walking = Feet.gait(0, 0, 0, frame, frame, 16, false)
	check(speed == 0 and not walking, "standing idles")
	_, _, walking = Feet.gait(0.002, 0, 0, frame, frame, 16, false)
	check(not walking, "0.12 studs/s jitter idles")
	-- Teleports and hitches reset instead of spinning a gait.
	distance, _, walking = Feet.gait(12, 0, 0, frame, frame, 16, false)
	check(distance == 0 and not walking, "a 12-stud jump in one frame is a teleport")
	distance = Feet.gait(0.27, 0, 0, frame, 0.3, 16, false)
	check(distance == 0, "a frame over 0.25 s resets")
	distance = Feet.gait(0.27, 0, 0, 0, frame, 16, false)
	check(distance == 0, "a zero step resets")
	-- A mid-range mob posed every 3rd frame (0.05 s) at a 2x speed buff: 1.6 studs, under the 4-stud floor.
	distance, speed, walking = Feet.gait(1.6, 0, 0, 0.05, frame, 16, false)
	check(distance == 1.6 and math.abs(speed - 32) < 1e-6 and walking, "a buffed every-3rd-frame pose walks")
	-- A catalog speed missing never throws.
	_, _, walking = Feet.gait(0.27, 0, 0, frame, frame, nil, false)
	check(walking, "no catalog speed still measures")
	return checks
end
