-- MapConfig data checks. Run in Studio Edit (plan A, Task 1).
return function(Maps, EnemyCatalog, Rules)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	check(Maps.valid(Maps.Default), "Default map must exist")
	check(not Maps.valid("Nope") and not Maps.valid(nil) and not Maps.valid(5), "Unknown ids are invalid")
	check(Maps.get("Nope") == nil, "get() returns nil for unknown ids")
	check(Maps.get(Maps.Default) == Maps.Maps[Maps.Default], "get() returns the map entry")
	local seenFolders = {}
	for _, name in Maps.LobbyFolders do
		seenFolders[name] = "lobby"
	end
	for id, map in Maps.Maps do
		local index = Rules.MapIndex[id]
		check(index ~= nil, id .. " must be a RunSetupRules map")
		check(#map.folders > 0, id .. " needs at least one folder")
		for _, name in map.folders do
			check(type(name) == "string" and seenFolders[name] == nil, id .. " folder " .. tostring(name) .. " is shared")
			seenFolders[name] = id
		end
		check(map.boss == nil or map.boss == "Hammer", id .. " boss must be Hammer or nil")
		if map.roster ~= nil then
			local count = 0
			for enemyId in map.roster:gmatch("[^,%s]+") do
				local enemy = EnemyCatalog.ById[enemyId]
				check(enemy ~= nil, id .. " roster has unknown enemy " .. enemyId)
				check(enemy.map == Rules.Maps[index].name, enemyId .. " belongs to " .. tostring(enemy.map))
				count += 1
			end
			check(count > 0, id .. " roster must not be empty")
			local listed = {}
			for enemyId in map.roster:gmatch("[^,%s]+") do
				listed[enemyId] = true
			end
			for _, enemy in EnemyCatalog.List do
				if enemy.map == Rules.Maps[index].name then
					check(listed[enemy.id], id .. " roster is missing " .. tostring(enemy.id))
				end
			end
		end
	end
	check(Maps.Maps.PineValley.boss == "Hammer" and Maps.Maps.PineValley.roster == nil, "Pine Valley keeps its zombies and Hammer boss")
	check(Maps.Maps.BeachCove.boss == nil, "Beach Cove is won by clearing wave 20")
	return { passed = checks }
end
