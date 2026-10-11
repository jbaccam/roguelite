-- Read-only presentation policy. Counter/storage and combat rules remain in their own modules.
local RS = game:GetService("ReplicatedStorage")
local combat = RS:WaitForChild("RogueliteCombat")
local Weapons = require(combat.WeaponCatalog)
local Stats = require(combat.CharacterStats)
local Journal = require(combat.WeaponJournal)
local P = {}

local PLAYER = {
	MaxHP = true,
	Armor = true,
	Dodge = true,
	Regeneration = true,
	LifeSteal = true,
	LifeStealCap = true,
	Recovery = true,
	MoveSpeed = true,
	PickupRadius = true,
	Luck = true,
	FirstHitBlock = true,
	ContactReduction = true,
	ShopDiscount = true,
	ShopPricePercent = true,
}
local REASONS = {
	ProjectileCount = "Adds projectiles to these weapons' attacks.",
	Pierce = "These projectiles can continue through extra enemies.",
	Bounce = "These projectiles can rebound to extra enemies.",
	ExtraSwings = "These weapons swing, so they can swing again.",
	ExplosionDamage = "These weapons deal explosive damage.",
	AreaSize = "These weapons have an area, puddle, lightning radius or area special to enlarge.",
	ChainBonus = "These weapons already create lightning chains.",
	ChainDamage = "The lightning portion of these attacks receives the bonus.",
	UtilityPower = "These weapons use Utility Power. Placed turrets also receive this bonus.",
	MeleeDamage = "These weapons use the melee damage multiplier.",
	RangedDamage = "These weapons use the ranged damage multiplier.",
	ElementalDamage = "These weapons are elemental. Burn and poison damage also receive this bonus.",
}
local neutral = {}
for _, s in Stats.List do
	neutral[s.id] = s.base
end

function P.number(value, decimal)
	local n = math.max(0, tonumber(value) or 0)
	local raw = string.format(decimal and "%.1f" or "%.0f", decimal and n or math.floor(n))
	local whole, fraction = raw:match("^(%d+)(.*)$")
	repeat
		local nextValue, count = whole:gsub("^(%d+)(%d%d%d)", "%1,%2")
		whole = nextValue
	until count == 0
	return whole .. (fraction == ".0" and "" or fraction)
end

function P.effects(item)
	local out = {}
	for _, source in
		{ { values = item.modifiers or {}, percent = false }, { values = item.percent or {}, percent = true } }
	do
		for id, value in source.values do
			local stat = Stats.ById[id]
			table.insert(out, {
				id = id,
				value = value,
				label = stat and stat.label or id,
				amount = (value >= 0 and "+" or "")
					.. tostring(value)
					.. (source.percent and "%" or stat and stat.unit or ""),
			})
		end
	end
	table.sort(out, function(a, b)
		return a.label < b.label
	end)
	return out
end

local function supports(weapon, stat)
	if stat == "UtilityPower" then
		return weapon.utility == true
	end
	if stat == "MeleeDamage" then
		return weapon.kind == "Melee"
	end
	if stat == "RangedDamage" then
		return weapon.kind ~= "Melee"
	end
	if stat == "ElementalDamage" then
		return weapon.elemental == true
	end
	return Stats.usesStat(weapon, stat, neutral)
end

function P.groups(ids)
	local groups, byClass = {}, {}
	for _, id in ids do
		local weapon = Weapons.ById[id]
		local key = weapon.godly and "Godly" or weapon.home
		if not byClass[key] then
			byClass[key] = {}
		end
		table.insert(byClass[key], id)
	end
	local order = table.clone(Stats.ClassOrder)
	table.insert(order, "Godly")
	for _, key in order do
		local entries = byClass[key]
		if entries then
			table.sort(entries, function(a, b)
				return Weapons.ById[a].name < Weapons.ById[b].name
			end)
			table.insert(groups, { name = key, ids = entries })
		end
	end
	return groups
end

-- Evaluate each effect separately: Alien Battery's global attack speed must never hide its
-- conditional lightning bonus. Never expand a player/global benefit into 42 meaningless icons.
function P.compatibility(item)
	local result = { player = {}, every = {}, specific = {}, structure = false }
	for _, effect in P.effects(item) do
		if PLAYER[effect.id] then
			table.insert(result.player, effect)
		elseif Stats.WeaponStats[effect.id] or REASONS[effect.id] then
			local ids = {}
			for _, weapon in Weapons.List do
				if supports(weapon, effect.id) then
					table.insert(ids, weapon.id)
				end
			end
			local schema = Stats.ById[effect.id]
			local detail = {
				effect = effect,
				ids = ids,
				groups = P.groups(ids),
				reason = REASONS[effect.id] or schema and schema.help or effect.label,
			}
			if effect.id == "ChainBonus" or effect.id == "ChainDamage" then
				detail.conditional =
					"With Battery Pack or the Mage lightning bonus, every weapon's lightning can use this effect."
			elseif effect.id == "AreaSize" then
				detail.conditional =
					"Battery Pack or Mage adds lightning areas to other weapons. Burn spread also uses this radius bonus."
			end
			table.insert(result.specific, detail)
		else
			table.insert(result.every, effect)
		end
	end
	result.structure = item.structure == true and #P.effects(item) == 0
	return result
end

function P.filter(kind, query)
	local result = {}
	query = string.lower(query or "")
	for _, entry in kind == "Item" and Journal.Items or Weapons.List do
		local category = kind == "Weapon" and (entry.godly and "Godly" or Weapons.classNames(entry, " "))
			or table.concat(entry.tags or {}, " ")
		local effectNames = {}
		if kind == "Item" then
			for _, effect in P.effects(entry) do
				table.insert(effectNames, effect.label)
			end
		end
		local hay = (
			entry.name
			.. " "
			.. category
			.. " "
			.. (entry.kind or "")
			.. " "
			.. table.concat(effectNames, " ")
		):lower()
		if query == "" or hay:find(query, 1, true) then
			table.insert(result, entry)
		end
	end
	table.sort(result, function(a, b)
		return a.name < b.name
	end)
	return result
end

-- A compact toolbar and naturally sized cards, in actual viewport pixels.
function P.layout(size)
	local compact = size.X < 600
	local margin = size.Y < 460 and 8 or compact and 10 or 18
	local width = math.min(1240, size.X - margin * 2)
	local height = math.min(920, size.Y - margin * 2)
	local pad = compact and 14 or size.Y < 460 and 16 or 22
	local bodyW = width - pad * 2
	local gap = 12
	local single = bodyW >= 660
	local titleW = bodyW >= 1000 and 172 or 0
	local navH = single and 44 or 96
	local nav = {}
	if single then
		local x = titleW > 0 and titleW + 12 or 0
		nav.Weapon = { x = x, y = 0, w = 104 }
		nav.Item = { x = x + 112, y = 0, w = 88 }
		nav.Collection = { x = x + 208, y = 0, w = 124 }
		nav.Close = { x = bodyW - 44, y = 0, w = 44 }
		nav.Search = { x = x + 344, y = 0, w = math.min(280, bodyW - 44 - 12 - (x + 344)) }
	else
		local weaponW = math.floor((bodyW - 16) * 0.33)
		local itemW = math.floor((bodyW - 16) * 0.27)
		nav.Weapon = { x = 0, y = 0, w = weaponW }
		nav.Item = { x = weaponW + 8, y = 0, w = itemW }
		nav.Collection = { x = weaponW + itemW + 16, y = 0, w = bodyW - weaponW - itemW - 16 }
		nav.Search = { x = 0, y = 52, w = math.min(280, bodyW - 56) }
		nav.Close = { x = bodyW - 44, y = 52, w = 44 }
	end
	local bodyY = pad + navH + gap
	local footer = 22
	local footerY = height - pad - footer
	local bodyH = footerY - 8 - bodyY
	local listPad, scrollGutter = 4, 12
	local available = bodyW - listPad * 2 - scrollGutter
	local columns = math.clamp(math.floor((available + gap) / ((compact and 120 or 148) + gap)), 1, 6)
	local cardW = math.min(190, (available - (columns - 1) * gap) / columns)
	local gridW = columns * cardW + (columns - 1) * gap
	local detailW = math.min(1100, bodyW - scrollGutter - 8)
	local split = detailW >= 740
	local summaryW = split and math.clamp(math.floor(detailW * 0.29), 240, 320) or detailW
	return {
		x = (size.X - width) / 2,
		y = (size.Y - height) / 2,
		w = width,
		h = height,
		pad = pad,
		bodyW = bodyW,
		gap = gap,
		bodyY = bodyY,
		bodyH = bodyH,
		footer = footer,
		footerY = footerY,
		compact = compact,
		short = size.Y < 460,
		nav = nav,
		navH = navH,
		titleW = titleW,
		single = single,
		columns = columns,
		cardW = cardW,
		cardH = compact and 172 or 180,
		listPad = listPad,
		scrollGutter = scrollGutter,
		gridW = gridW,
		gridX = (bodyW - scrollGutter - gridW) / 2,
		detailW = detailW,
		split = split,
		summaryW = summaryW,
		articleW = split and detailW - summaryW - 20 or detailW,
	}
end

function P.cards(width, count, minimum, maximum)
	local gap = 12
	local columns = math.max(1, math.min(count, math.floor((width + gap) / ((minimum or 140) + gap))))
	local w = math.min(maximum or 190, (width - (columns - 1) * gap) / columns)
	return { columns = columns, w = w, gap = gap, rows = math.ceil(count / columns) }
end
function P.weaponStats(weapon, tier)
	tier = math.clamp(math.floor(tonumber(tier) or 1), 1, 4)
	return {
		{ label = "BASE DAMAGE", value = string.format("%g", weapon.tierDamage[tier]) },
		{ label = "ATTACK DELAY", value = string.format("%.2f s", weapon.cooldown * weapon.tierCooldown[tier]) },
		{ label = "BASE RANGE", value = string.format("%g studs", weapon.range) },
	}
end

return P
