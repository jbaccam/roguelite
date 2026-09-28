-- ServerRole.detect checks. Run in Studio Edit (plan A, Task 2); Edit mode has no boot side effects.
return function(Role)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	check(Role.detect(true, nil, "", 0) == "Combined", "Studio defaults to Combined")
	check(Role.detect(true, "Lobby", "", 0) == "Lobby", "Studio can force Lobby")
	check(Role.detect(true, "Match", "", 0) == "Match", "Studio can force Match")
	check(Role.detect(true, "Arena", "", 0) == "Combined", "Unknown Studio roles fall back to Combined")
	check(Role.detect(true, "Lobby", "abc", 0) == "Lobby", "Studio ignores server ids")
	check(Role.detect(false, "Match", "", 0) == "Lobby", "Live public servers are lobbies whatever the Studio attribute says")
	check(Role.detect(false, nil, "abc-123", 0) == "Match", "Reserved servers are matches")
	check(Role.detect(false, nil, "abc-123", 99) == "Lobby", "Player-bought VIP servers are lobbies")
	return { passed = checks }
end
