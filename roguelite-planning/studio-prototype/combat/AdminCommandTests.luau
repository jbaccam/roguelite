-- Admin chat command checks (AdminCommands, 2026-10-12). Pure: no Instances, no Play. Outside
-- Studio: python run_admin_command_tests.py <luau.exe>. In Studio's command bar:
--   local C = game.ReplicatedStorage.RogueliteCombat
--   print(require(<this module>)(require(C.AdminCommands), require(C.WeaponCatalog), require(C.ShopCatalog)))
-- Covers parsing (defaults, trailing copies and tier, tier words, refusals), the Give catalog (one
-- key per entry, every kind), the item search (whole words before prefixes, turrets by tier, run vs
-- saved items) and the player search. Returns the number of checks.
-- Stats (optional, 2026-10-13): CharacterStats, for run armor (/armor): RunArmor wins over the saved
-- armor and never touches it.
return function(C, Weapons, Items, Stats)
	local checks = 0
	local function check(ok, message)
		checks += 1
		assert(ok, message)
	end
	local function same(a, b)
		for k, v in a do
			if b[k] ~= v then
				return false
			end
		end
		for k in b do
			if a[k] == nil then
				return false
			end
		end
		return true
	end
	local function parsed(text, want)
		local cmd, why = C.parse(text)
		check(cmd ~= nil, text .. " parses (" .. tostring(why) .. ")")
		check(same(cmd, want), text .. " -> the right fields")
	end
	-- Parsing.
	-- 2026-10-13: slot, not copies. No slot: the next free one (AdminService); no tier: Tier I.
	parsed("/tempgive bob katana", { name = "tempgive", player = "bob", item = "katana" })
	parsed("/tempgive bob katana 3", { name = "tempgive", player = "bob", item = "katana", slot = 3 })
	parsed("/tempgive bob katana 2 4", { name = "tempgive", player = "bob", item = "katana", slot = 2, tier = 4 })
	parsed("/tempgive all frying pan 6 3", { name = "tempgive", player = "all", item = "frying pan", slot = 6, tier = 3 })
	parsed("/tempgive me ray gun iii", { name = "tempgive", player = "me", item = "ray gun", tier = 3 })
	parsed("/tempgive me ray gun 5 t2", { name = "tempgive", player = "me", item = "ray gun", slot = 5, tier = 2 })
	parsed("/tempgive me turret 4", { name = "tempgive", player = "me", item = "turret", slot = 4 })
	parsed("/TEMPGIVE Bob Katana", { name = "tempgive", player = "Bob", item = "Katana" })
	parsed("/armor bob dragon scale", { name = "armor", player = "bob", item = "dragon scale" })
	parsed("/armor bob iron 4", { name = "armor", player = "bob", item = "iron", tier = 4 })
	parsed("/armor all off", { name = "armor", player = "all", off = true })
	parsed("/give bob katana", { name = "give", player = "bob", item = "katana" })
	parsed("/give bob katana 4", { name = "give", player = "bob", item = "katana", tier = 4 })
	parsed("/give others iron set", { name = "give", player = "others", item = "iron set" })
	parsed("/god", { name = "god", player = "me" })
	parsed("/god bob", { name = "god", player = "bob" })
	parsed("/god bob off", { name = "god", player = "bob", on = false })
	parsed("/god on", { name = "god", player = "me", on = true })
	parsed("/pause", { name = "pause" })
	parsed("/pause off", { name = "pause", on = false })
	parsed("/admin", { name = "admin" })
	for _, bad in { "/tempgive", "/tempgive bob", "/tempgive bob katana 7", "/tempgive bob katana 0", "/tempgive bob katana 2 5", "/give bob katana 5", "/armor bob", "/armor bob iron 5", "/pause now", "/god a b c", "/kick bob", "", "/give bob" } do
		check(C.parse(bad) == nil, bad .. " is refused")
	end
	check(C.parse(string.rep("a", C.MAX_TEXT + 1)) == nil, "Long text refused")
	check(C.parse(42) == nil, "Not text refused")
	check(#C.Names == 6 and table.find(C.Names, "tempgive") ~= nil and table.find(C.Names, "armor") ~= nil and table.find(C.Names, "pause") ~= nil, "Six commands")

	-- The catalog and item search, with the real weapons and shop items.
	local armor = { Slots = { "Helmet", "Chest", "Legs", "Boots" }, Sets = { { id = "Iron", name = "Iron" }, { id = "DragonScale", name = "Dragon Scale" } }, Icons = {} }
	local pets = { List = { { id = "Fox", name = "Fox" }, { id = "BabyDragon", name = "Baby Dragon" } }, Icons = {} }
	local entries = C.entries({ Weapons = Weapons, Items = Items, Armor = armor, Pets = pets, Classes = { "Brawler", "Chef" }, Signature = { Brawler = "06", Chef = "01" }, WeaponIcons = {} })
	local keys = {}
	for _, e in entries do
		check(keys[e.key] == nil, "Unique key " .. e.key)
		keys[e.key] = true
		check(e.temp or e.perm, e.key .. " can be given somehow")
		check(table.find(C.Kinds, e.kind) ~= nil, e.key .. " has a known kind")
	end
	local function weaponKey(name)
		for _, w in Weapons.List do
			if w.name == name then
				return "w:" .. w.id
			end
		end
	end
	local katana, pan = weaponKey("Katana"), weaponKey("Frying Pan")
	check(keys[katana] and keys["i:protein"] and keys["i:turret_nail"] and keys["a:Iron.Helmet"] and keys["s:Iron"] and keys["p:Fox"] and keys["c:Chef"], "Every kind is in the catalog")
	local function found(query, mode, key, tier)
		local e, why = C.find(entries, query, mode, tier)
		check(e ~= nil and e.key == key, string.format("%q (%s) -> %s, got %s", query, tostring(mode), key, e and e.key or tostring(why)))
	end
	found("katana", "temp", katana)
	found("KATANA", "perm", katana)
	found("frying pan", "temp", pan)
	found("fryingpan", "temp", pan)
	found("pan", "temp", pan) -- a whole word wins over Pandora's Box starting with "pan"
	found("protein", "temp", "i:protein")
	found("Protein Shake", "temp", "i:protein")
	found("turret", "temp", "i:turret_twin", 2)
	found("turret", "temp", "i:turret_gatling", 4)
	found("gatling", "temp", "i:turret_gatling")
	found("iron", "perm", "s:Iron")
	found("iron helmet", "perm", "a:Iron.Helmet")
	found("fox", "perm", "p:Fox")
	found("chef", "perm", "c:Chef")
	found("iron", "armor", "s:Iron")
	found("dragon scale", "armor", "s:DragonScale")
	found("dragon", "armor", "s:DragonScale")
	check(C.find(entries, "katana", "armor") == nil, "/armor takes sets only")
	check(C.find(entries, "protein", "perm") == nil, "Run items can't be saved")
	check(C.find(entries, "fox", "temp") == nil, "Pets aren't run items")
	check(C.find(entries, "zzzz", "temp") == nil, "Nothing found")
	local none, why = C.find(entries, "k", "temp")
	check(none == nil and string.find(why, "Did you mean") ~= nil, "Too many: a short list")

	-- Players.
	local list = { { name = "EggaRowls", display = "Egga", userId = 1 }, { name = "Bob", display = "Bobby", userId = 2 }, { name = "Bonnie", display = "Bon", userId = 3 } }
	local function names(out)
		local t = {}
		for i, p in out or {} do
			t[i] = p.name
		end
		return table.concat(t, ",")
	end
	check(names(C.players("me", list, 1)) == "EggaRowls", "me")
	check(names(C.players("all", list, 1)) == "EggaRowls,Bob,Bonnie", "all")
	check(names(C.players("others", list, 1)) == "Bob,Bonnie", "others")
	check(names(C.players("bob", list, 1)) == "Bob", "Exact name wins over Bobby/Bonnie prefixes")
	check(names(C.players("BONN", list, 1)) == "Bonnie", "Unique prefix, any case")
	check(names(C.players("egga", list, 1)) == "EggaRowls", "Display name")
	check(C.players("bo", list, 1) == nil, "Two fit: refused")
	check(C.players("zed", list, 1) == nil, "Nobody")
	-- Run armor (/armor): CharacterStats.runArmor / wornArmor / gearPower.
	if Stats then
		local function get(attrs)
			return function(name)
				return attrs[name]
			end
		end
		local saved = { ProfileWearing = "Helmet:Iron", ProfileArmor = "Iron.Helmet:2:0,DragonScale.Chest:3:0", ProfileWeapons = "01:1:0" }
		local w, tiers = Stats.wornArmor(get(saved))
		check(w == "Helmet:Iron" and tiers == saved.ProfileArmor, "No run armor: the saved armor")
		local run = table.clone(saved)
		run.RunArmor = "DragonScale"
		w, tiers = Stats.wornArmor(get(run))
		check(w == "Helmet:DragonScale,Chest:DragonScale,Legs:DragonScale,Boots:DragonScale", "Run armor: all four pieces")
		check(Stats.parseArmorTiers(tiers)["DragonScale.Chest"] == 3 and Stats.parseArmorTiers(tiers)["DragonScale.Helmet"] == 1, "No tier: owned tiers, else I")
		run.RunArmor = "DragonScale:4"
		w, tiers = Stats.wornArmor(get(run))
		check(Stats.parseArmorTiers(tiers)["DragonScale.Helmet"] == 4, "A tier sets all four")
		check(Stats.gearPower(get(run), "01") == 1 + 16 and Stats.gearPower(get(saved), "01") == 1 + 2, "Gear power follows the run armor, then the saved armor again")
		check(run.ProfileWearing == "Helmet:Iron" and run.ProfileArmor == saved.ProfileArmor, "Saved armor untouched")
		check(Stats.runArmor("Nope") == nil and Stats.runArmor("Iron:5") == nil and Stats.runArmor(nil) == nil, "Bad run armor is ignored")
	end
	return checks
end
