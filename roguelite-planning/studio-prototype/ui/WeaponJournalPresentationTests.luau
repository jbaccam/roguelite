-- Temporary Studio test module; do not ship. run() reads catalogs, never mutates profiles.
local RS = game:GetService("ReplicatedStorage")
local P = require(RS.WeaponJournalPresentation)
local C = RS.RogueliteCombat
local J = require(C.WeaponJournal)
local W = require(C.WeaponCatalog)
local S = require(C.CharacterStats)
local Tests = {}
function Tests.run()
	local checks = 0
	local function check(ok, message)
		checks += 1
		assert(ok, message)
	end
	local neutral = {}
	for _, stat in S.List do
		neutral[stat.id] = stat.base
	end
	local soup = P.compatibility(J.ItemById.soup)
	check(
		#soup.player == 2 and #soup.every == 0 and #soup.specific == 0,
		"soup affects player, never a weapon icon grid"
	)
	for _, id in { "shoes", "cushion", "skates", "gummies", "magnet" } do
		local support = P.compatibility(J.ItemById[id])
		check(
			#support.player > 0 and #support.specific == 0 and #support.every == 0,
			id .. " benefits every player build"
		)
	end
	local alien = P.compatibility(J.ItemById.alien)
	check(#alien.every == 1 and alien.every[1].id == "AttackSpeed", "mixed item retains universal attack speed")
	check(
		#alien.specific == 1 and alien.specific[1].effect.id == "ChainDamage" and alien.specific[1].conditional ~= nil,
		"mixed item explains conditional lightning separately"
	)
	local unsupported = P.compatibility({ modifiers = { UnknownFutureStat = 1 } })
	check(#unsupported.every == 1, "unknown display stat is nil safe")
	for _, item in J.Items do
		local support = P.compatibility(item)
		local effects = P.effects(item)
		check(
			#effects == #support.player + #support.every + #support.specific,
			"every effect displayed exactly once: " .. item.id
		)
		check(
			not (#effects == 0 and item.structure) or support.structure,
			"structure described independently: " .. item.id
		)
		for _, specific in support.specific do
			local seen = {}
			local grouped = {}
			for _, group in specific.groups do
				for _, id in group.ids do
					check(not grouped[id], "no duplicate named weapon")
					grouped[id] = true
				end
			end
			for _, id in specific.ids do
				check(W.ById[id] ~= nil and not seen[id] and grouped[id], "valid unique grouped weapon")
				seen[id] = true
			end
			for _, weapon in W.List do
				local expected = specific.effect.id == "UtilityPower" and weapon.utility == true
					or specific.effect.id ~= "UtilityPower" and S.usesStat(weapon, specific.effect.id, neutral)
				check((seen[weapon.id] == true) == expected, "actual stat policy: " .. item.id .. " / " .. weapon.id)
			end
		end
	end
	local extra = P.compatibility(J.ItemById.straws).specific[1].ids
	check(
		table.find(extra, "00") ~= nil
			and not table.find(extra, "01")
			and not table.find(extra, "12")
			and not table.find(extra, "17"),
		"extra shots: Glock yes, pan/returning boomerang/spray no"
	)
	for _, weapon in W.List do
		for tier = 1, 4 do
			local values = P.weaponStats(weapon, tier)
			check(tonumber(values[1].value) == weapon.tierDamage[tier], "tier damage from catalog")
			check(
				values[2].value == string.format("%.2f s", weapon.cooldown * weapon.tierCooldown[tier]),
				"tier cadence from catalog"
			)
		end
	end
	check(P.number(1234567.8, true) == "1,234,567.8", "damage decimals retained")
	check(P.number(9000000000000) == "9,000,000,000,000", "full bounded lifetime counts")
	check(#P.filter("Weapon", "__no_such_weapon__") == 0, "empty search")
	local recovery = P.filter("Item", "recovery")
	check(#recovery == 1 and recovery[1].id == "soup", "search includes exact effect labels")
	for _, size in
		{
			Vector2.new(2560, 1440),
			Vector2.new(1920, 1080),
			Vector2.new(1366, 768),
			Vector2.new(1024, 768),
			Vector2.new(844, 390),
			Vector2.new(750, 369),
			Vector2.new(667, 375),
			Vector2.new(390, 844),
			Vector2.new(360, 640),
			Vector2.new(320, 568),
		}
	do
		local l = P.layout(size)
		check(l.x >= 0 and l.y >= 0 and l.w <= size.X and l.h <= size.Y, "frame fits viewport")
		check(l.bodyY == l.pad + l.navH + l.gap and l.bodyY + l.bodyH < l.footerY, "compact chrome clears content")
		check(l.nav.Search.w >= 160 and l.nav.Search.w <= 280, "bounded readable search")
		local controls = { l.nav.Weapon, l.nav.Item, l.nav.Collection, l.nav.Search, l.nav.Close }
		for i, a in controls do
			check(a.x >= 0 and a.y >= 0 and a.x + a.w <= l.bodyW and a.y + 44 <= l.navH, "persistent navigation fits")
			for j = 1, i - 1 do
				local b = controls[j]
				check(
					not (a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + 44 and b.y < a.y + 44),
					"navigation has no overlap"
				)
			end
		end
		check(not l.single or l.navH == 44, "desktop chrome is one row")
		check(l.cardW >= 120 and l.cardW <= 190 and l.cardH <= 180, "naturally bounded collection cards")
		check(l.gridX >= 0 and l.gridX + l.gridW <= l.bodyW - l.scrollGutter, "grid clears scrollbar")
		check(l.h - l.footerY - l.footer >= l.pad, "footer clears border")
		check(l.detailW <= 1100 and l.summaryW <= math.max(320, l.detailW), "bounded detail reading area")
		if l.split then
			check(l.summaryW >= 240 and l.summaryW <= 320 and l.articleW >= 460, "balanced detail columns")
		end
		for _, kind in { "Weapon", "Item" } do
			local entries = P.filter(kind, "")
			local rows = math.ceil(#entries / l.columns)
			check(rows * (l.cardH + l.gap) - l.gap + 16 > l.bodyH, "full collection uses vertical scroll")
			check(l.cardH <= l.bodyH, "a full card remains visible")
		end
		for _, count in { 2, 3, 12 } do
			local cards = P.cards(l.articleW, count, 140, 190)
			check(
				cards.w <= 190 and cards.columns * cards.w + (cards.columns - 1) * cards.gap <= l.articleW,
				"stat cards never stretch or overflow"
			)
		end
	end
	return { passed = true, checks = checks, weapons = #W.List, items = #J.Items }
end
return Tests
