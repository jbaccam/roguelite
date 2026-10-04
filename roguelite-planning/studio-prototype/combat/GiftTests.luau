-- Gifting checks (2026-10-04, MONETIZATION_AND_REWARDS.md "Gifting"): which products can be gifted,
-- who may receive, what an in-server player can't receive, the gift intent (put, bind to a receipt,
-- late and retried receipts, cancel, done, tidy) and the inbox (add once per receipt, full, list,
-- malformed entries, remove). Pure: run in Studio Edit on a fresh MonetizationConfig and get the
-- number of checks back:
--   local Fresh=loadstring(HS:GetAsync(base..'tools/FreshRequire.luau?t='..os.clock(),true))()(base)
--   print(Fresh.require('GiftTests')(Fresh.require('MonetizationConfig')))
return function(M)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	local function copy(v)
		if type(v) ~= "table" then
			return v
		end
		local c = {}
		for k, x in v do
			c[k] = copy(x)
		end
		return c
	end

	-- Giftable: developer products, never the in-run ones or passes.
	for _, key in { "StarterPack", "Emeralds1", "Royal5", "ClassThrower", "GodlyStarter", "BloodPhoenixBundle", "Rerolls5", "MegaBundle" } do
		check(M.giftable(key), key .. " can be gifted")
	end
	for _, key in { "Revive1", "Revive5", "ShopReroll", "UpgradeReroll", "Banish", "VIP", "QuickOpen", "Nope", 5 } do
		check(not M.giftable(key), tostring(key) .. " can't be gifted")
	end
	for key, p in M.Products do
		check(M.giftable(key) == not (p.revive or key == "ShopReroll" or key == "UpgradeReroll" or key == "Banish"), "only in-run products are noGift: " .. key)
	end

	-- Recipients: here or a friend, never yourself (Studio may), real ids only (Studio test ids are negative).
	local ok, why = M.giftRecipientOk({ buyer = 1, to = 2, inServer = true, friends = false })
	check(ok and why == nil, "a player in this server")
	check(M.giftRecipientOk({ buyer = 1, to = 2, inServer = false, friends = true }), "an offline friend")
	ok, why = M.giftRecipientOk({ buyer = 1, to = 2, inServer = false, friends = false })
	check(not ok and why == "You can gift to players here or your friends", "a stranger elsewhere")
	ok, why = M.giftRecipientOk({ buyer = 1, to = 1, inServer = true, friends = false })
	check(not ok and why == "You can't gift to yourself", "yourself")
	check(M.giftRecipientOk({ buyer = 1, to = 1, inServer = true, studio = true }), "yourself in Studio")
	check(not M.giftRecipientOk({ buyer = 1, to = -2, inServer = true }), "a negative id live")
	check(M.giftRecipientOk({ buyer = -1, to = -2, inServer = true, studio = true }), "a Studio test player")
	for _, to in { 0, 2.5, 0 / 0, math.huge, "2", {} } do
		check(not M.giftRecipientOk({ buyer = 1, to = to, inServer = true, friends = true, studio = true }), "bad id " .. tostring(to))
	end
	check(not M.giftRecipientOk({ buyer = 1, inServer = true, friends = true, studio = true }), "no id")

	-- What a player here can't receive as itself.
	local ana = { starterPack = true, classes = { Brawler = true, Thrower = true }, bundles = { GodlyStarter = true } }
	check(M.giftBlocked("StarterPack", ana) == "already has it", "owned Starter Pack")
	check(M.giftBlocked("ClassThrower", ana) == "already unlocked it", "owned class")
	check(M.giftBlocked("ClassJuggler", ana) == nil, "a class they don't have")
	check(M.giftBlocked("GodlyStarter", ana) == "already has it", "owned Godly Starter")
	check(M.giftBlocked("ShadowDragonBundle", ana) == nil, "a Godly bundle they don't have")
	check(M.giftBlocked("Emeralds3", ana) == nil and M.giftBlocked("Royal1", ana) == nil, "repeatable products")
	check(M.giftBlocked("StarterPack", nil) == nil, "unknown owner: allowed (the delivery pays emeralds if needed)")
	check(M.giftBlocked("StarterPack", { starterPack = false, classes = {}, bundles = {} }) == nil, "a new player")

	-- Intents: Ben (buyer) taps GIFT at t=1000; the receipt binds it once.
	local t = 1000
	local intent = { id = "a", to = 2, toName = "Ana", at = t }
	local rec = M.giftIntentPut(nil, "StarterPack", intent, t)
	check(rec.StarterPack.pending == intent, "put sets pending")
	local got, changed = M.giftIntentBind(rec, "StarterPack", "R1", t + 180)
	check(got == intent and changed, "a receipt 3 minutes later binds it")
	check(rec.StarterPack.pending == nil and rec.StarterPack.bound.R1 == intent, "moved to bound")
	got, changed = M.giftIntentBind(rec, "StarterPack", "R1", t + 86400 * 3)
	check(got == intent and not changed, "the same receipt retried days later still finds it, no write")
	got = M.giftIntentBind(rec, "StarterPack", "R2", t + 200)
	check(got == nil, "another receipt of the same product is a normal purchase")
	check(M.giftIntentBind(rec, "Emeralds1", "R1", t) == nil, "another product: nothing")
	check(M.giftIntentDone(rec, "StarterPack", "R1") and rec.StarterPack == nil, "done clears it")
	check(not M.giftIntentDone(rec, "StarterPack", "R1"), "done twice: no change")
	-- Too late: 10 minutes and one second.
	rec = M.giftIntentPut(nil, "StarterPack", { id = "b", to = 2, at = t }, t)
	check(M.giftIntentBind(rec, "StarterPack", "R3", t + M.GiftIntentSeconds + 1) == nil, "a receipt after 10 minutes is the buyer's")
	check(M.giftIntentBind(rec, "StarterPack", "R3", t + M.GiftIntentSeconds) ~= nil, "exactly 10 minutes is still the gift")
	-- A malformed pending intent never binds.
	rec = M.giftIntentPut(nil, "StarterPack", { id = "c", to = "2", at = t }, t)
	check(M.giftIntentBind(rec, "StarterPack", "R4", t) == nil, "recipient must be a number")
	check(M.giftIntentBind(nil, "StarterPack", "R4", t) == nil and M.giftIntentBind({}, "StarterPack", 5, t) == nil, "no record, bad receipt")
	-- A newer GIFT replaces pending; cancel only removes its own id.
	rec = M.giftIntentPut(nil, "Royal1", { id = "x", to = 2, at = t }, t)
	rec = M.giftIntentPut(rec, "Royal1", { id = "y", to = 3, at = t + 5 }, t + 5)
	check(rec.Royal1.pending.id == "y", "the newer GIFT wins")
	check(not M.giftIntentCancel(rec, "Royal1", "x") and rec.Royal1.pending.id == "y", "an old prompt's cancel leaves the new one")
	check(M.giftIntentCancel(rec, "Royal1", "y") and rec.Royal1 == nil, "its own cancel removes it")
	-- Cancel never touches a bound gift.
	rec = M.giftIntentPut(nil, "Royal1", { id = "z", to = 2, at = t }, t)
	M.giftIntentBind(rec, "Royal1", "R5", t + 1)
	check(not M.giftIntentCancel(rec, "Royal1", "z") and rec.Royal1.bound.R5 ~= nil, "a paid gift can't be cancelled")
	-- Tidy on put: stale pending and month-old bindings go; others stay.
	rec = {
		Old = { pending = { id = "o", to = 2, at = t } },
		Paid = { bound = { R6 = { id = "p", to = 2, at = t }, R7 = { id = "q", to = 2, at = t + 40 * 86400 } } },
		Junk = 5,
	}
	rec = M.giftIntentPut(rec, "Emeralds1", { id = "n", to = 2, at = t + 31 * 86400 }, t + 31 * 86400)
	check(rec.Old == nil and rec.Junk == nil, "stale and junk entries tidied")
	check(rec.Paid.bound.R6 == nil and rec.Paid.bound.R7 ~= nil, "a month-old binding goes, a recent one stays")
	check(rec.Emeralds1.pending.id == "n", "the new one is in")

	-- Inbox: once per receipt, oldest first, capped.
	local function gift(receipt, at, key)
		return { from = 1, fromName = "Ben", key = key or "StarterPack", receipt = receipt, at = at, spent = 49 }
	end
	local inbox, status = M.giftInboxAdd(nil, gift("R1", 20), 3)
	check(status == "added" and #inbox.gifts == 1, "first gift added")
	inbox, status = M.giftInboxAdd(inbox, gift("R1", 20), 3)
	check(status == "duplicate" and #inbox.gifts == 1, "a retried receipt isn't added twice")
	M.giftInboxAdd(inbox, gift("R2", 10, "Emeralds1"), 3)
	M.giftInboxAdd(inbox, gift("R3", 30), 3)
	inbox, status = M.giftInboxAdd(inbox, gift("R4", 40), 3)
	check(status == "full" and #inbox.gifts == 3, "full: the receipt waits")
	table.insert(inbox.gifts, { from = "x", receipt = "R9" })
	table.insert(inbox.gifts, 7)
	local list, bad = M.giftList(copy(inbox))
	check(#list == 3 and bad == 2, "three gifts, two malformed")
	check(list[1].receipt == "R2" and list[2].receipt == "R1" and list[3].receipt == "R3", "oldest first")
	check(M.giftValid(gift("R1", 1, "GoneProduct")), "a product no longer sold is still a valid gift (paid as emeralds)")
	check(not M.giftValid(gift("", 1)) and not M.giftValid(gift(string.rep("x", 101), 1)), "receipt id length")
	local g = gift("R5", 1)
	g.pick = "2"
	check(not M.giftValid(g), "pick must be a number")
	-- Remove the delivered ones and the malformed; a gift that arrived meanwhile stays.
	local current = copy(inbox)
	M.giftInboxAdd(current, gift("R8", 50), 10)
	local left, n = M.giftInboxRemove(current, { R1 = true, R2 = true })
	check(n == 4 and #left.gifts == 2, "two delivered and two malformed removed")
	check(left.gifts[1].receipt == "R3" and left.gifts[2].receipt == "R8", "the undelivered and the new one stay")
	left, n = M.giftInboxRemove(nil, {})
	check(n == 0 and #left.gifts == 0, "no inbox")
	list, bad = M.giftList(nil)
	check(#list == 0 and bad == 0, "empty list")
	return checks
end
