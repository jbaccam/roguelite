-- Full-screen Armory: the player's avatar on the dais of the armory hall (ArmoryStage), the
-- collection on the left (weapons, armor pieces, pets), loadout slots around the avatar (helmet,
-- chestplate, leggings, boots, weapon, pet, class, upgrades) and details on the right. UPGRADES swaps
-- to the tier ladder with the weapon spinning over the dais. Green theme (UITheme).
-- Presentation and requests only: upgrades go through ProfileAction('Upgrade', id) and are
-- validated by ProfileService; EQUIP sets the same LoadoutClass/LoadoutWeapon preference as the
-- Loadout screen and sends it to the lobby server, which checks it (RunSetupRules.validLoadout).
local RS = game:GetService("ReplicatedStorage")
local Lighting = game:GetService("Lighting")
local Input = game:GetService("UserInputService")
local TweenService = game:GetService("TweenService")
local T = require(RS:WaitForChild("UITheme"))
local Stage = require(RS:WaitForChild("ArmoryStage"))
local Rules = require(RS:WaitForChild("RunSetupRules"))
local RunSetup = require(RS:WaitForChild("RunSetupUI"))
local combat = RS:WaitForChild("RogueliteCombat")
local Weapons = require(combat:WaitForChild("WeaponCatalog"))
local Stats = require(combat:WaitForChild("CharacterStats"))
local Chests = require(combat:WaitForChild("ChestConfig"))
local Armor = require(combat:WaitForChild("ArmorCatalog"))
local WeaponIcons = require(RS:WaitForChild("WeaponInventoryUI")).Icons
local C = T.Color
local A = {}

-- Layout is authored at 1920x1080 and scaled to the viewport. Side panels hug the screen edges,
-- the slots stay centred on the avatar.
local DW, DH = 1920, 1080
local LEFT_W, LEFT_H = 600, 900
local RIGHT_W, RIGHT_H = 540, 760
local CARD, CARD_H, GAP = 170, 206, 14

local TRAITS = {
	pellets = "Fires a spread of pellets.",
	pierce = "Shots pierce through enemies.",
	bounce = "Bounces between enemies.",
	cards = "Throws a three-card volley.",
	shots = "Fires a burst of shots.",
}

-- Armor is worn as four pieces (ArmorCatalog; cosmetic until armor chests and set bonuses exist).
-- Pets come from the Pet Chest (pets only) and don't exist yet, so their slot and tab say so.
local ARMOR_PIECES = {
	{ id = "Helmet", label = "HELMET", plural = "HELMETS" },
	{ id = "Chest", label = "CHEST", plural = "CHESTPLATES" },
	{ id = "Legs", label = "LEGS", plural = "LEGGINGS" },
	{ id = "Boots", label = "BOOTS", plural = "BOOTS" },
}

-- A 3D view of one armor piece: its meshes from ReplicatedStorage.ArmorSets at their rest
-- positions around the body (the installer's `Rest` attribute), framed from the front-left.
local function armorModel(setId)
	local sets = RS:FindFirstChild("ArmorSets")
	return sets and Armor.ById[setId] and sets:FindFirstChild(Armor.ById[setId].model)
end

local function armorView(parent, setId, slot, x, y, size)
	local vp = T.make("ViewportFrame", parent, {
		Name = "ArmorView",
		BackgroundTransparency = 1,
		Position = UDim2.fromOffset(x, y),
		Size = UDim2.fromOffset(size, size),
		Ambient = Color3.fromRGB(200, 200, 200),
		LightColor = Color3.fromRGB(255, 250, 240),
		LightDirection = Vector3.new(-0.3, -1, 0.5),
	})
	local template = armorModel(setId)
	if not template then
		return vp
	end
	local lo, hi = Vector3.one * math.huge, -Vector3.one * math.huge
	for _, src in template:GetChildren() do
		if src:IsA("BasePart") and src:GetAttribute("Piece") == slot then
			local rest = src:GetAttribute("Rest") or CFrame.new()
			local p = src:Clone()
			p.Anchored = true
			p.CFrame = rest
			p.Parent = vp
			lo, hi = lo:Min(rest.Position - p.Size / 2), hi:Max(rest.Position + p.Size / 2)
		end
	end
	if lo.X == math.huge then
		return vp
	end
	local cam = Instance.new("Camera")
	cam.FieldOfView = 30
	local centre, radius = (lo + hi) / 2, (hi - lo).Magnitude / 2
	-- The body faces -Z: look from in front, a little left and above.
	cam.CFrame = CFrame.lookAt(centre + Vector3.new(-0.5, 0.3, -1).Unit * radius / math.sin(math.rad(15)), centre)
	cam.Parent = vp
	vp.CurrentCamera = cam
	return vp
end

local function weaponAt(w, tier)
	tier = math.clamp(tier or 1, 1, 4)
	local cd = w.cooldown * (w.tierCooldown[tier] or 1)
	return { damage = w.tierDamage[tier] or w.damage, rate = 1 / cd, range = w.range }
end

local function describe(w)
	local out = { "Home weapon of the " .. w.home .. " class." }
	if TRAITS[w.trait] then
		table.insert(out, TRAITS[w.trait])
	end
	if w.burn > 0 then
		table.insert(out, "Sets enemies on fire.")
	end
	if w.poison > 0 then
		table.insert(out, "Poisons what it hits.")
	end
	if w.slow > 0 then
		table.insert(out, "Slows enemies down.")
	end
	if w.lightning then
		table.insert(out, "Lightning chains to nearby enemies.")
	end
	if w.blastRadius then
		table.insert(out, "Explodes on impact.")
	end
	return table.concat(out, " ")
end

-- "RARE" in its rarity colour (ChestConfig.RarityColor), for RichText labels.
local function rarityTag(id)
	local rarity = Chests.RarityOf[id] or "Common"
	return '<font color="' .. T.hex(Chests.RarityColor[rarity]) .. '">' .. string.upper(rarity) .. "</font>"
end

-- What each tier adds over the one before, from the catalogue's per-tier tables.
local function tierGains(w, tier)
	if tier <= 1 then
		return { "The weapon itself" }
	end
	local out = {}
	local d = math.floor((w.tierDamage[tier] / w.tierDamage[tier - 1] - 1) * 100 + 0.5)
	local s = math.floor((w.tierCooldown[tier - 1] / w.tierCooldown[tier] - 1) * 100 + 0.5)
	if d > 0 then
		table.insert(out, "+" .. d .. "% Damage")
	end
	if s > 0 then
		table.insert(out, "+" .. s .. "% Attack speed")
	end
	return out
end

-- Check mark and up arrow drawn from frames (FredokaOne has no check glyph).
local function tick(parent, x, y, size, color)
	local g = T.make("Frame", parent, {
		Name = "Check",
		BackgroundColor3 = color or C.lime,
		Position = UDim2.fromOffset(x, y),
		Size = UDim2.fromOffset(size, size),
		BorderSizePixel = 0,
		ZIndex = 6,
	})
	T.make("UICorner", g, { CornerRadius = UDim.new(1, 0) })
	T.make("UIStroke", g, { Color = Color3.fromRGB(8, 10, 11), Thickness = 2 })
	local w = math.max(2, math.floor(size * 0.14))
	local a = T.make("Frame", g, {
		BackgroundColor3 = C.ink,
		BorderSizePixel = 0,
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.36, 0.58),
		Size = UDim2.fromOffset(w, size * 0.3),
		Rotation = -45,
		ZIndex = 7,
	})
	local b = T.make("Frame", g, {
		BackgroundColor3 = C.ink,
		BorderSizePixel = 0,
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.58, 0.46),
		Size = UDim2.fromOffset(w, size * 0.56),
		Rotation = 40,
		ZIndex = 7,
	})
	return g, a, b
end

local function upArrow(parent, x, y, size, color)
	local g = T.make("Frame", parent, {
		Name = "UpgradeReady",
		BackgroundTransparency = 1,
		Position = UDim2.fromOffset(x, y),
		Size = UDim2.fromOffset(size, size),
		ZIndex = 8,
	})
	for i, dy in { 0, 0.34 } do
		for _, s in { -1, 1 } do
			local bar = T.make("Frame", g, {
				BackgroundColor3 = color or C.gold,
				BorderSizePixel = 0,
				AnchorPoint = Vector2.new(0.5, 0.5),
				Position = UDim2.fromScale(0.5 + s * 0.17, 0.36 + dy),
				Size = UDim2.fromOffset(size * 0.16, size * 0.52),
				Rotation = s * 45,
				ZIndex = 8 + i,
			})
			T.make("UIStroke", bar, { Color = Color3.fromRGB(8, 10, 11), Thickness = 2 })
			T.make("UICorner", bar, { CornerRadius = UDim.new(0, 3) })
		end
	end
	-- Gentle bob so ready upgrades catch the eye.
	TweenService:Create(
		g,
		TweenInfo.new(0.55, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut, -1, true),
		{ Position = UDim2.fromOffset(x, y - 5) }
	):Play()
	return g
end

-- Title plate with stone caps sitting on a panel's top edge.
local function plate(parent, text, x, y, size)
	size = size or 38
	local w = game:GetService("TextService"):GetTextSize(text, size, T.Font, Vector2.new(2000, 100)).X + 90
	local p = T.panel(parent, "TitlePlate", x, y, w, 64, "panel")
	T.caps(p, 44)
	local l = T.label(p, "Title", text, 0, 0, 0, 0, size)
	l.Size = UDim2.fromScale(1, 1)
	return p
end

local function centred(l)
	l.TextXAlignment = Enum.TextXAlignment.Center
	return l
end

-- opts: profile() -> LobbyUI profile, need(rec) -> copies for the next tier, selection (shared
-- with the lobby: class, weapon), openWindow(name, arg), onVisible(bool).
function A.new(player, opts)
	local self = {}
	local sel = opts.selection
	local screen = T.make("ScreenGui", player:WaitForChild("PlayerGui"), {
		Name = "Armory",
		ResetOnSpawn = false,
		DisplayOrder = 58,
		IgnoreGuiInset = true,
		ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
		Enabled = false,
	})
	self.Screen = screen
	local fallback -- blur + shade when the hall is not installed
	local root, profile, draw
	-- armorSlot: the Armor tab's slot filter (nil = every slot).
	local state = { tab = "Weapons", mine = true, item = nil, kind = "weapon", mode = "main", armorSlot = nil }
	-- Panels slide in only when the screen opens or switches between main and upgrade views;
	-- a plain redraw (selecting an item, a profile update) must not move anything.
	local animate = false
	local scroll = {} -- tab -> grid scroll position, kept across redraws
	local function slideIn(frame, from, to)
		if not animate then
			frame.Position = to
			return
		end
		frame.Position = from
		TweenService
			:Create(frame, TweenInfo.new(0.22, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), { Position = to })
			:Play()
	end

	local function loadout()
		local class = player:GetAttribute("LoadoutClass") or sel.class or "Brawler"
		if not profile.classes[class] then
			class = "Brawler"
		end
		local weapon = player:GetAttribute("LoadoutWeapon") or sel.weapon
		local w = weapon and Weapons.ById[weapon]
		if not w or w.home ~= class or not profile.weapons[weapon] then
			weapon = Rules.Signature[class]
		end
		return class, weapon
	end
	-- Ready to upgrade: enough copies AND emeralds (ChestConfig.upgradeEmeralds, tripling per tier).
	local function ready(id)
		local rec = profile.weapons[id]
		local need = rec and opts.need(rec)
		return need ~= nil and rec.have >= need and profile.gems >= (Chests.upgradeEmeralds(id, rec.tier) or 0)
	end

	-- Scaled groups ------------------------------------------------------------
	local groups = {}
	local function group(name, anchor, pos, w, h)
		local f = T.frame(root, name, 0, 0, w, h)
		f.AnchorPoint = anchor
		f.Position = pos
		groups[f] = T.make("UIScale", f, { Scale = 1 })
		return f
	end
	local function fit()
		local v = workspace.CurrentCamera.ViewportSize
		if v.X <= 0 then
			return
		end
		local s = math.clamp(math.min(v.X / DW, v.Y / DH), 0.4, 1.25)
		for _, sc in groups do
			sc.Scale = s
		end
	end
	workspace.CurrentCamera:GetPropertyChangedSignal("ViewportSize"):Connect(fit)

	-- Pieces --------------------------------------------------------------------
	local function currencyPill(parent, name, x, asset, value, color)
		local row = T.panel(parent, name, x, 0, 200, 56, "inset")
		T.icon(row, "Icon", 8, 6, 44, asset)
		local v = T.label(row, "Value", value, 58, 6, 130, 44, 28, color)
		v.TextXAlignment = Enum.TextXAlignment.Left
		return row
	end

	local function drawTop()
		local top = group("Top", Vector2.new(0.5, 0), UDim2.new(0.5, 0, 0, 14), 700, 130)
		local name = centred(T.label(top, "PlayerName", player.DisplayName, 0, 0, 700, 56, 48))
		name.TextWrapped = false
		local fmt = function(n)
			n = tonumber(n) or 0
			return n >= 1e4 and string.format("%.1fK", n / 1e3) or tostring(n)
		end
		-- Emeralds are the only currency (keys were dropped); one pill, centred under the name.
		currencyPill(top, "Emeralds", 250, "emerald", fmt(profile.gems), C.emerald)
		top.Emeralds.Position = UDim2.fromOffset(250, 64)
		if not profile.connected or game:GetService("RunService"):IsStudio() then
			local chip = T.chip(
				top,
				"PreviewChip",
				profile.connected and "STUDIO TEST · NOT SAVED" or "PROFILE LOADING",
				0,
				124,
				Color3.fromRGB(58, 48, 20),
				C.gold
			)
			chip.AnchorPoint = Vector2.new(0.5, 0)
			chip.Position = UDim2.fromOffset(350, 124)
		end
	end

	local function select(kind, id)
		if state.kind == kind and state.item == id then
			return
		end
		state.kind, state.item = kind, id
		draw()
	end

	-- A square collection card: tier corners, icon, name and have/need bar.
	local function weaponCard(parent, w, x, y)
		local rec = profile.weapons[w.id]
		local chosen = state.kind == "weapon" and state.item == w.id
		local card = T.button(parent, "W_" .. w.id, "", x, y, CARD, CARD_H, function()
			select("weapon", w.id)
		end, not chosen)
		card.Caption.Visible = false
		if rec and not chosen then
			T.setTier(card, rec.tier)
		end
		local art = T.icon(card, "Icon", (CARD - 104) / 2, 18, 104, WeaponIcons[w.id])
		art.ImageTransparency = rec and 0 or 0.62
		local n = centred(T.label(card, "Name", w.name, 6, 122, CARD - 12, 30, 20, rec and C.white or C.dim))
		n.TextWrapped = false
		n.TextScaled = true
		T.make("UITextSizeConstraint", n, { MaxTextSize = 20, MinTextSize = 12 })
		if rec then
			T.tierBadge(card, rec.tier, 10, 10)
			T.upgradeBar(card, "Upgrade", 12, CARD_H - 40, CARD - 24, 22, rec.have, opts.need(rec))
			local _, equipped = loadout()
			if equipped == w.id then
				tick(card, CARD - 38, 10, 28)
			end
			if ready(w.id) then
				upArrow(card, CARD - 44, 34, 34)
			end
		else
			RunSetup.lock(card, CARD - 40, 12, 26)
			local locked = centred(T.text(card, "Locked", "NOT OWNED", 12, CARD_H - 38, CARD - 24, 20, 15, C.dim))
			if chosen then
				-- Dark text on the lime "selected" fill; grey would disappear into it.
				n.TextColor3, locked.TextColor3 = C.ink, C.ink
				n.TextStrokeTransparency, locked.TextStrokeTransparency = 1, 1
				art.ImageTransparency = 0.3
			end
		end
		return card
	end

	-- An armor piece card: 3D view, set name, slot in the rarity colour, tick when worn.
	local function armorCard(parent, setId, slot, x, y)
		local id = Armor.pieceId(setId, slot)
		local set = Armor.ById[setId]
		local rec = profile.armor[id]
		local chosen = state.kind == "armor" and state.item == id
		local card = T.button(parent, "A_" .. id, "", x, y, CARD, CARD_H, function()
			select("armor", id)
		end, not chosen)
		card.Caption.Visible = false
		local view = armorView(card, setId, slot, (CARD - 124) / 2, 6, 124)
		view.ImageTransparency = rec and 0 or 0.62
		local n = centred(T.label(card, "Name", set.name, 6, 132, CARD - 12, 30, 20, rec and C.white or C.dim))
		n.TextWrapped = false
		n.TextScaled = true
		T.make("UITextSizeConstraint", n, { MaxTextSize = 20, MinTextSize = 12 })
		local k = centred(T.text(card, "Slot", string.upper(slot), 6, 164, CARD - 12, 22, 16, Chests.RarityColor[set.rarity]))
		if profile.wearing[slot] == setId then
			tick(card, CARD - 38, 10, 28)
		end
		if not rec then
			RunSetup.lock(card, CARD - 40, 12, 26)
		end
		if chosen then
			n.TextColor3, k.TextColor3 = C.ink, C.ink
			n.TextStrokeTransparency, k.TextStrokeTransparency = 1, 1
		end
		return card
	end

	-- Wear or take off armor (slot or 'All'). The server re-dresses the character; the dais copy
	-- is rebuilt once the character carries the new ProfileWearing.
	local function wear(slot, setId)
		local before = player:GetAttribute("ProfileWearing")
		local r = combat.ProfileAction:InvokeServer("WearArmor", slot, setId)
		T.toast(screen, r.message or "", r.ok and C.lime or C.negative)
		if not r.ok then
			return
		end
		T.sound("ui_equip")
		task.spawn(function()
			local t0 = os.clock()
			while os.clock() - t0 < 3 do
				local now = player:GetAttribute("ProfileWearing")
				local ch = player.Character
				if now ~= before and ch and ch:GetAttribute("ArmorWorn") == now then
					break
				end
				task.wait(0.05)
			end
			Stage.RefreshAvatar()
		end)
	end

	-- "Coming" panel for tabs whose items are not in the game yet: a title, one line, a few facts.
	local function comingPanel(parent, title, body, lines)
		local h = 118 + #lines * 44
		local box = T.panel(parent, "Coming", 0, 0, LEFT_W - 60, h, "inset")
		local t = T.label(box, "Title", title, 20, 18, LEFT_W - 100, 40, 30)
		t.TextXAlignment = Enum.TextXAlignment.Left
		local b = T.text(box, "Body", body, 20, 62, LEFT_W - 100, 30, 18, C.muted)
		b.TextYAlignment = Enum.TextYAlignment.Top
		for i, line in lines do
			local row = T.panel(box, "Row" .. i, 20, 104 + (i - 1) * 44, LEFT_W - 100, 38, "panel")
			local l = T.label(row, "Text", line, 16, 2, LEFT_W - 132, 34, 20, C.cream)
			l.TextXAlignment = Enum.TextXAlignment.Left
		end
		return h
	end

	local function checkbox(parent, name, text, x, y, w, on, callback)
		local b = T.button(parent, name, "", x, y, w, 50, callback, true)
		b.Caption.Visible = false
		local box = T.make("Frame", b, {
			Name = "Box",
			Position = UDim2.fromOffset(12, 11),
			Size = UDim2.fromOffset(28, 28),
			BackgroundColor3 = on and C.lime or C.track,
			BorderSizePixel = 0,
			ZIndex = 3,
		})
		T.make("UICorner", box, { CornerRadius = UDim.new(0, 6) })
		T.make("UIStroke", box, { Color = Color3.fromRGB(8, 10, 11), Thickness = 2 })
		if on then
			local g = tick(box, 0, 0, 28, C.lime)
			g.Size = UDim2.fromScale(1, 1)
			g:FindFirstChildOfClass("UIStroke"):Destroy()
		end
		local l = T.label(b, "Text", text, 50, 4, w - 58, 42, 20)
		l.TextXAlignment = Enum.TextXAlignment.Left
		return b
	end

	-- Left: the collection -------------------------------------------------------
	local function drawCollection()
		local left = group("Left", Vector2.new(0, 0.5), UDim2.new(0, 24, 0.5, 30), LEFT_W, LEFT_H)
		local panel = T.panel(left, "Panel", 0, 0, LEFT_W, LEFT_H, "panel")
		plate(left, "ARMORY", 20, -34)
		local tabs = T.tabs(panel, 22, 44, LEFT_W - 44, 52, { "Weapons", "Armor", "Pets" }, state.tab, function(id)
			if id == state.tab then
				return
			end
			state.tab = id
			state.kind, state.item = nil, nil
			state.armorSlot = nil
			draw()
		end)
		for id, b in tabs do
			b.Caption.Text = string.upper(id)
		end
		local readyCount = 0
		for _, w in Weapons.List do
			if ready(w.id) then
				readyCount += 1
			end
		end
		T.badge(tabs.Weapons, readyCount > 0 and tostring(readyCount) or nil)
		local class = loadout()
		local y0 = 110
		if state.tab == "Weapons" then
			checkbox(panel, "MyClass", "MY CLASS · " .. string.upper(class), 22, y0, 300, state.mine, function()
				state.mine = not state.mine
				draw()
			end)
			local owned, total = 0, 0
			for _, w in Weapons.List do
				total += 1
				if profile.weapons[w.id] then
					owned += 1
				end
			end
			local count =
				T.label(panel, "Owned", owned .. " / " .. total .. " OWNED", 330, y0, LEFT_W - 352, 50, 18, C.muted)
			count.TextXAlignment = Enum.TextXAlignment.Right
			y0 += 64
		end
		-- Armor sets whose meshes are installed and that own at least one piece.
		local armorSets = {}
		for _, set in Armor.Sets do
			local owns = false
			for _, sl in Armor.Slots do
				owns = owns or profile.armor[Armor.pieceId(set.id, sl)] ~= nil
			end
			if owns and armorModel(set.id) then
				table.insert(armorSets, set)
			end
		end
		if state.tab == "Armor" and #armorSets > 0 then
			local filters = { "All" }
			for _, sl in Armor.Slots do
				table.insert(filters, sl)
			end
			T.tabs(panel, 22, y0, LEFT_W - 44, 44, filters, state.armorSlot or "All", function(id)
				state.armorSlot = id ~= "All" and id or nil
				state.kind, state.item = nil, nil
				draw()
			end)
			y0 += 58
		end
		local grid = T.scroll(panel, "Grid", 22, y0, LEFT_W - 36, LEFT_H - y0 - 22)
		local tab = state.tab
		grid:GetPropertyChangedSignal("CanvasPosition"):Connect(function()
			scroll[tab] = grid.CanvasPosition
		end)
		local cols = 3
		local function cell(i)
			return ((i - 1) % cols) * (CARD + GAP), math.floor((i - 1) / cols) * (CARD_H + GAP)
		end
		local y = 0
		if state.tab == "Weapons" then
			-- Current class first; owned weapons first inside each class.
			local classes = { class }
			if not state.mine then
				for _, c in Stats.ClassOrder do
					if c ~= class then
						table.insert(classes, c)
					end
				end
			end
			for _, c in classes do
				local list = Rules.homeWeapons(c)
				table.sort(list, function(a, b)
					local ra, rb = profile.weapons[a.id], profile.weapons[b.id]
					if (ra ~= nil) ~= (rb ~= nil) then
						return ra ~= nil
					end
					return a.id < b.id
				end)
				if not state.mine then
					local h = T.label(
						grid,
						"Header_" .. c,
						string.upper(c) .. (profile.classes[c] and "" or "  ·  LOCKED"),
						4,
						y,
						LEFT_W - 60,
						32,
						22,
						profile.classes[c] and C.lime or C.dim
					)
					h.TextXAlignment = Enum.TextXAlignment.Left
					y += 38
				end
				for i, w in list do
					local x, dy = cell(i)
					weaponCard(grid, w, x, y + dy)
				end
				y += math.ceil(#list / cols) * (CARD_H + GAP) + 8
			end
			if not state.item then
				local _, weapon = loadout()
				state.kind, state.item = "weapon", weapon
			end
		elseif state.tab == "Pets" then
			y = comingPanel(grid, "Pets are coming", "Pets come from the Pet Chest and follow you into runs.", {
				"Each pet has its own strong suit",
				"One pet follows you at a time",
				"Copies level it up, like weapons",
			}) + 10
			if not state.item then
				state.kind, state.item = "pet", "Pet"
			end
		elseif #armorSets > 0 then
			-- Each set with an owned piece: its pieces in the filtered slot(s), unowned ones locked.
			local slots = state.armorSlot and { state.armorSlot } or Armor.Slots
			local first
			for _, set in armorSets do
				do
					local h = T.label(
						grid,
						"Header_" .. set.id,
						string.upper(set.name) .. "  ·  " .. string.upper(set.rarity),
						4,
						y,
						LEFT_W - 60,
						32,
						22,
						Chests.RarityColor[set.rarity]
					)
					h.TextXAlignment = Enum.TextXAlignment.Left
					y += 38
					for i, sl in slots do
						local x, dy = cell(i)
						armorCard(grid, set.id, sl, x, y + dy)
						local id = Armor.pieceId(set.id, sl)
						if profile.wearing[sl] == set.id and profile.armor[id] then
							first = first or id
						end
					end
					y += math.ceil(#slots / cols) * (CARD_H + GAP) + 8
					first = first or Armor.pieceId(set.id, slots[1])
				end
			end
			if not state.item then
				state.kind, state.item = "armor", first
			end
		else
			y = comingPanel(grid, "Armor is coming", "Armor pieces come from armor chests.", {
				"Helmet, chestplate, leggings and boots",
				"2 pieces of one set: a set bonus",
				"All 4 pieces: the set's special perk",
			}) + 10
			if not state.item then
				state.kind, state.item = "armor", "Helmet"
			end
		end
		grid.CanvasSize = UDim2.fromOffset(0, y)
		if scroll[tab] then
			grid.CanvasPosition = scroll[tab]
		end
		slideIn(left, UDim2.new(0, -40, 0.5, 30), UDim2.new(0, 24, 0.5, 30))
	end

	-- Centre: loadout slots around the avatar -------------------------------------
	local SLOT = 124
	local function slot(parent, name, caption, x, y, callback, fill)
		local b = T.button(parent, name, "", x, y, SLOT, SLOT, callback, true)
		b.Caption.Visible = false
		local cap = centred(T.label(parent, name .. "Caption", caption, x - 20, y + SLOT + 2, SLOT + 40, 26, 20))
		cap.TextWrapped = false
		fill(b)
		return b
	end
	local function emptySlot(b, chosen, text)
		-- Dark text on the lime "selected" fill; grey on the charcoal one.
		local ink = chosen and C.ink or C.dim
		local plus = centred(T.label(b, "Plus", "+", 0, 14, SLOT, 70, 64, ink))
		plus.Size = UDim2.new(1, 0, 0, 80)
		local soon = centred(T.text(b, "Soon", text or "SOON", 10, SLOT - 34, SLOT - 20, 22, 15, ink))
		if chosen then
			plus.TextStrokeTransparency, soon.TextStrokeTransparency = 1, 1
			T.setPrimary(b, true)
		end
	end

	local function drawSlots()
		local class, weapon = loadout()
		local mid = group("Slots", Vector2.new(0.5, 0.5), UDim2.new(0.5, 0, 0.5, 10), 1000, 720)
		local rowY = function(i)
			return 8 + (i - 1) * 156
		end
		-- Left column: the four armor pieces.
		for i, piece in ARMOR_PIECES do
			local setId = profile.wearing[piece.id]
			setId = setId and armorModel(setId) and setId or nil
			local id = setId and Armor.pieceId(setId, piece.id) or piece.id
			slot(mid, piece.id .. "Slot", piece.label, 60, rowY(i), function()
				state.tab = "Armor"
				state.armorSlot = piece.id
				state.kind, state.item = "armor", id
				draw()
			end, function(b)
				if setId then
					armorView(b, setId, piece.id, 4, 4, SLOT - 8)
					if state.kind == "armor" and state.item == id then
						T.setPrimary(b, true)
					end
				else
					emptySlot(b, state.kind == "armor" and state.item == id, next(profile.armor) and "EMPTY" or nil)
				end
			end)
		end
		-- Right column: starting weapon, pet, class, ready upgrades.
		local rec = profile.weapons[weapon]
		local RX = 1000 - 60 - SLOT
		slot(mid, "WeaponSlot", "WEAPON", RX, rowY(1), function()
			state.tab = "Weapons"
			select("weapon", weapon)
		end, function(b)
			T.icon(b, "Icon", 14, 12, SLOT - 28, WeaponIcons[weapon])
			if rec then
				T.tierBadge(b, rec.tier, 8, 8)
				T.setTier(b, rec.tier)
			end
			if ready(weapon) then
				upArrow(b, SLOT - 40, 8, 30)
			end
		end)
		slot(mid, "PetSlot", "PET", RX, rowY(2), function()
			state.tab = "Pets"
			select("pet", "Pet")
		end, function(b)
			emptySlot(b, state.kind == "pet")
		end)
		slot(mid, "ClassSlot", "CLASS", RX, rowY(3), function()
			select("class", class)
		end, function(b)
			local icon = T.icon(b, "Icon", 22, 8, SLOT - 44, WeaponIcons[Rules.Signature[class]])
			icon.ImageTransparency = 0.25
			centred(T.label(b, "Name", string.upper(class), 4, SLOT - 34, SLOT - 8, 28, 20, C.lime))
			if state.kind == "class" then
				T.setPrimary(b, true)
			end
		end)
		local readyList = {}
		for _, w in Weapons.List do
			if ready(w.id) then
				table.insert(readyList, w.id)
			end
		end
		slot(mid, "ReadySlot", "UPGRADES", RX, rowY(4), function()
			if readyList[1] then
				state.tab = "Weapons"
				state.mine = false
				state.kind, state.item = "weapon", readyList[1]
				state.mode = "upgrade"
				animate = true
				draw()
			else
				T.toast(screen, "Open chests to collect copies for upgrades", C.muted)
			end
		end, function(b)
			if #readyList > 0 then
				upArrow(b, (SLOT - 44) / 2, 12, 44)
				centred(T.label(b, "Count", #readyList .. " READY", 0, SLOT - 44, SLOT, 36, 24, C.gold)).Size =
					UDim2.new(1, 0, 0, 36)
			else
				centred(T.label(b, "Count", "NONE\nREADY", 0, 20, SLOT, 80, 22, C.dim)).Size = UDim2.new(1, 0, 0, 80)
			end
		end)
		-- Stat plate under the dais: class health and the starter's damage at its tier.
		local hp = Stats.resolve(class, 0).MaxHP
		local w = Weapons.ById[weapon]
		local dmg = w and weaponAt(w, rec and rec.tier or 1).damage or 0
		local plateRow = T.frame(mid, "StatPlate", 250, 640, 500, 70)
		local a = T.panel(plateRow, "Damage", 0, 0, 240, 66, "panel")
		T.icon(a, "Icon", 14, 6, 54, WeaponIcons[weapon])
		local al = T.label(a, "Value", dmg .. " DMG", 70, 6, 160, 54, 30)
		al.TextXAlignment = Enum.TextXAlignment.Left
		local h = T.panel(plateRow, "Health", 260, 0, 240, 66, "panel")
		T.icon(h, "Icon", 14, 8, 50, "heart")
		local hl = T.label(h, "Value", math.floor(hp + 0.5) .. " HP", 72, 6, 160, 54, 30)
		hl.TextXAlignment = Enum.TextXAlignment.Left
	end

	-- Right: details ---------------------------------------------------------------------
	local function statRow(parent, y, label, value, delta)
		local l = T.label(parent, "Stat_" .. label, label, 24, y, 260, 40, 24, C.muted)
		l.TextXAlignment = Enum.TextXAlignment.Left
		local v = T.label(parent, "Value_" .. label, value, 280, y, 130, 40, 28)
		v.TextXAlignment = Enum.TextXAlignment.Right
		if delta then
			local d = T.label(parent, "Delta_" .. label, delta, 414, y, 100, 40, 24, C.lime)
			d.TextXAlignment = Enum.TextXAlignment.Right
		end
	end
	local function fmtRate(r)
		local text = string.format("%.2f", r):gsub("0$", "")
		return text
	end
	local function header(panel, icon, tier, name, sub, nameColor)
		local well = T.panel(panel, "IconWell", 22, 22, 132, 132, "inset")
		T.icon(well, "Icon", 10, 10, 112, icon)
		if tier then
			T.tierBadge(well, tier, 6, 6)
		end
		local n = T.label(panel, "Name", name, 170, 30, RIGHT_W - 190, 60, 36, nameColor)
		n.TextXAlignment = Enum.TextXAlignment.Left
		local s = T.text(panel, "Kind", sub, 172, 94, RIGHT_W - 194, 26, 18, C.cream)
		return n, s
	end

	local function upgrade(id)
		local before = profile.weapons[id] or profile.armor[id]
		local r = combat.ProfileAction:InvokeServer("Upgrade", id)
		T.toast(screen, r.message or "", r.ok and C.lime or C.negative)
		if r.ok then
			-- ProfileWeapons changes and redraws; celebrate in the new tier's colour.
			Stage.Burst(T.Tier[math.min(4, (before and before.tier or 1) + 1)])
		end
	end

	local function drawWeaponDetail(panel, w)
		local rec = profile.weapons[w.id]
		local tier = rec and rec.tier or 1
		header(
			panel,
			WeaponIcons[w.id],
			rec and tier,
			w.name,
			rarityTag(w.id) .. "  ·  " .. string.upper(w.home) .. "  ·  " .. string.upper(w.kind),
			rec and T.Tier[tier] or C.white
		)
		local desc = T.text(panel, "Description", describe(w), 24, 168, RIGHT_W - 48, 66, 19, C.muted)
		desc.TextYAlignment = Enum.TextYAlignment.Top
		local st = weaponAt(w, tier)
		T.label(panel, "StatsTitle", "STATS", 24, 240, 200, 34, 26).TextXAlignment = Enum.TextXAlignment.Left
		statRow(panel, 278, "Damage", tostring(st.damage))
		statRow(panel, 318, "Attacks / sec", fmtRate(st.rate))
		statRow(panel, 358, "Range", tostring(st.range))
		local class = loadout()
		local _, equipped = loadout()
		if rec then
			local need = opts.need(rec)
			local ct = T.label(panel, "CopiesTitle", "COPIES", 24, 410, 200, 30, 22, C.muted)
			ct.TextXAlignment = Enum.TextXAlignment.Left
			local nt = T.label(
				panel,
				"TierText",
				need and ("TIER " .. T.Roman[tier] .. "  →  " .. T.Roman[tier + 1]) or "MAX TIER",
				220,
				410,
				RIGHT_W - 244,
				30,
				20,
				T.Tier[math.min(4, tier + 1)]
			)
			nt.TextXAlignment = Enum.TextXAlignment.Right
			T.upgradeBar(panel, "Copies", 24, 446, RIGHT_W - 48, 30, rec.have, need)
			local homeOwned = profile.classes[w.home] == true
			local eq = T.button(
				panel,
				"Equip",
				equipped == w.id and "EQUIPPED" or (homeOwned and "EQUIP AS STARTER" or "CLASS LOCKED"),
				24,
				500,
				RIGHT_W - 48,
				70,
				function()
					sel.class, sel.weapon = w.home, w.id
					player:SetAttribute("LoadoutClass", w.home)
					player:SetAttribute("LoadoutWeapon", w.id)
					-- The lobby server validates it and swaps the weapon on the player's ring.
					local lobby = workspace:FindFirstChild("RogueliteLobby")
					local setup = lobby and lobby:FindFirstChild("RunSetup")
					if setup then
						setup:FireServer("Loadout", w.home, w.id)
					end
					T.toast(screen, w.name .. " is your " .. w.home .. " starter", C.lime)
					draw()
				end,
				true
			)
			eq.Caption.TextSize = 28
			eq.Interactable = equipped ~= w.id and homeOwned
			local isReady = ready(w.id)
			local up = T.button(
				panel,
				"Upgrades",
				isReady and "UPGRADE READY" or "VIEW UPGRADES",
				24,
				584,
				RIGHT_W - 48,
				70,
				function()
					state.mode = "upgrade"
					animate = true
					draw()
				end,
				not isReady
			)
			up.Caption.TextSize = 28
			if isReady then
				up.Caption.TextColor3 = C.ink
				up.Caption.TextStrokeTransparency = 1
				local sc = T.make("UIScale", up, { Scale = 1 })
				TweenService:Create(
					sc,
					TweenInfo.new(0.7, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut, -1, true),
					{ Scale = 1.03 }
				):Play()
			end
			if class ~= w.home then
				T.text(
					panel,
					"Note",
					"Starts runs only as a " .. w.home .. ". Any class can buy it in the run shop.",
					24,
					668,
					RIGHT_W - 48,
					44,
					16,
					C.dim
				)
			end
		else
			local lk = T.label(panel, "NotOwned", "NOT OWNED", 24, 410, 300, 34, 28, C.dim)
			lk.TextXAlignment = Enum.TextXAlignment.Left
			local rarity = Chests.RarityOf[w.id] or "Common"
			T.text(
				panel,
				"How",
				"One copy from a chest unlocks it. "
					.. (
						rarity == "Common" and "Every chest has Common weapons."
						or ("Better chests find " .. rarity .. " weapons more often.")
					),
				24,
				448,
				RIGHT_W - 48,
				50,
				18,
				C.muted
			)
			local b = T.button(panel, "GoChests", "OPEN CHESTS", 24, 530, RIGHT_W - 48, 70, function()
				opts.openWindow("Chests")
			end)
			b.Caption.TextSize = 28
		end
	end

	-- Empty armor/pet slot: what fills it and one thing the left panel doesn't already say.
	local function drawComingDetail(panel, icon, title, sub, body)
		header(panel, icon, nil, title, sub, C.white)
		local b = T.text(panel, "Body", body, 24, 168, RIGHT_W - 48, 90, 19, C.muted)
		b.TextYAlignment = Enum.TextYAlignment.Top
	end

	-- A worn or owned armor piece: EQUIP / TAKE OFF this piece, or the whole set.
	-- Set bonus lines (the approved step 5 table). CharacterStats.ArmorSets carries the same text
	-- once the combat side lands; this is the fallback.
	local ARMOR_TEXT = {
		Iron = { "+2 Armor", "10% less damage from zombie hits" },
		Ninja = { "+8% Dodge", "After a dodge, your next hit crits" },
		Viking = { "+12% Melee damage", "Below half HP: +25% Attack speed" },
		Samurai = { "+8% Crit chance", "+40% Crit damage" },
		Spartan = { "+3 Armor", "Blocks the first hit every wave" },
		DragonScale = { "+25 Max health", "20% burn chance, and 25% to burn zombies that hit you" },
		Phoenix = { "+2 HP/s Regeneration", "Once per run: rise at 50% HP in a fire blast" },
	}
	local function setText(setId)
		local t = Stats.ArmorSets and Stats.ArmorSets[setId] and Stats.ArmorSets[setId].text
		local f = ARMOR_TEXT[setId] or { "", "" }
		return t and t.two or f[1], t and t.four or f[2]
	end

	-- An armor piece: tier, set bonuses, the set's pieces, UPGRADE (copies + emeralds), EQUIP /
	-- TAKE OFF this piece or the whole set.
	local function drawArmorDetail(panel, id)
		local setId, slot = Armor.split(id)
		local set = Armor.ById[setId]
		local rec = profile.armor[id]
		local worn = profile.wearing[slot] == setId
		header(
			panel,
			nil,
			rec and rec.tier,
			string.upper(set.name),
			'<font color="'
				.. T.hex(Chests.RarityColor[set.rarity])
				.. '">'
				.. string.upper(set.rarity)
				.. "</font>  ·  ARMOR  ·  "
				.. string.upper(slot),
			rec and T.Tier[rec.tier] or C.white
		)
		armorView(panel.IconWell, setId, slot, 6, 6, 120)
		local two, four = setText(setId)
		local d = T.text(
			panel,
			"Bonuses",
			'<font color="#91EF14">2 PIECES</font>  ' .. two .. '\n<font color="#91EF14">4 PIECES</font>  ' .. four,
			24,
			166,
			RIGHT_W - 48,
			56,
			19,
			C.cream
		)
		d.RichText = true
		d.TextYAlignment = Enum.TextYAlignment.Top
		T.label(panel, "PiecesTitle", "SET PIECES", 24, 228, 300, 32, 24).TextXAlignment = Enum.TextXAlignment.Left
		local owned, wornAll = 0, true
		for i, sl in Armor.Slots do
			local r = profile.armor[Armor.pieceId(setId, sl)]
			local on = profile.wearing[sl] == setId
			owned += r and 1 or 0
			wornAll = wornAll and (on or not r)
			statRow(
				panel,
				262 + (i - 1) * 34,
				sl,
				r and ((on and "WORN" or "OWNED") .. "  " .. T.Roman[r.tier]) or "NOT OWNED"
			)
		end
		-- Upgrade: copies of this piece + emeralds (ChestConfig, tripling each tier).
		if rec then
			local need = rec.tier < 4 and Chests.upgradeCost(id, rec.tier) or nil
			local gems = need and Chests.upgradeEmeralds(id, rec.tier)
			T.upgradeBar(panel, "Copies", 24, 408, RIGHT_W - 48, 26, rec.have, need)
			local ok = need ~= nil and rec.have >= need and profile.gems >= gems
			local up = T.button(
				panel,
				"Upgrade",
				need and ("UPGRADE  ·  " .. gems .. " EMERALDS") or "MAX TIER",
				24,
				444,
				RIGHT_W - 48,
				62,
				function()
					upgrade(id)
				end,
				not ok
			)
			up.Caption.TextSize = 24
			up.Interactable = ok
			if need and rec.have < need then
				centred(T.text(panel, "Need", "Need " .. (need - rec.have) .. " more copies", 24, 506, RIGHT_W - 48, 20, 16, C.muted))
			elseif need and profile.gems < gems then
				centred(T.text(panel, "Need", "Need " .. (gems - profile.gems) .. " more emeralds", 24, 506, RIGHT_W - 48, 20, 16, C.negative))
			end
		end
		local eq = T.button(
			panel,
			"Equip",
			worn and "TAKE OFF" or (rec and "EQUIP" or "NOT OWNED"),
			24,
			530,
			RIGHT_W - 48,
			62,
			function()
				wear(slot, (not worn) and setId or nil)
			end,
			true
		)
		eq.Caption.TextSize = 26
		eq.Interactable = rec ~= nil
		local all = T.button(
			panel,
			"EquipSet",
			wornAll and "TAKE OFF SET" or "EQUIP FULL SET",
			24,
			604,
			RIGHT_W - 48,
			62,
			function()
				wear("All", (not wornAll) and setId or nil)
			end,
			wornAll
		)
		all.Caption.TextSize = 26
		all.Interactable = owned > 0
	end

	local function drawClassDetail(panel, class)
		local c = Stats.Classes[class]
		header(
			panel,
			WeaponIcons[Rules.Signature[class]],
			nil,
			string.upper(class),
			"CLASS  ·  STARTER " .. string.upper(Weapons.ById[Rules.Signature[class]].name),
			C.lime
		)
		local d = T.text(panel, "Description", c.description, 24, 168, RIGHT_W - 48, 60, 19, C.muted)
		d.TextYAlignment = Enum.TextYAlignment.Top
		local lines = {}
		for _, sd in Stats.List do
			local v = c.buffs[sd.id]
			if v then
				table.insert(
					lines,
					'<font color="'
						.. T.hex(v > 0 and C.lime or C.negative)
						.. '">'
						.. (v > 0 and "+" or "")
						.. v
						.. sd.unit
						.. "</font>  "
						.. sd.label
				)
			end
		end
		T.label(panel, "BuffsTitle", "CLASS BUFFS", 24, 236, 300, 34, 26).TextXAlignment = Enum.TextXAlignment.Left
		local b = T.text(panel, "Buffs", table.concat(lines, "\n"), 24, 274, RIGHT_W - 48, 210, 22)
		b.TextYAlignment = Enum.TextYAlignment.Top
		T.text(
			panel,
			"Affinity",
			"Equip 2 home weapons in a run for the first class bonus, 4 for the stronger one.",
			24,
			496,
			RIGHT_W - 48,
			44,
			17,
			C.cream
		)
		local go = T.button(panel, "ChangeClass", "CHANGE CLASS", 24, 584, RIGHT_W - 48, 70, function()
			opts.openWindow("Loadout")
		end, true)
		go.Caption.TextSize = 28
	end

	local function drawDetail()
		local right = group("Right", Vector2.new(1, 0.5), UDim2.new(1, -24, 0.5, 30), RIGHT_W, RIGHT_H)
		local panel = T.panel(right, "Panel", 0, 0, RIGHT_W, RIGHT_H, "panel")
		if state.kind == "weapon" and Weapons.ById[state.item or ""] then
			local w = Weapons.ById[state.item]
			local rec = profile.weapons[w.id]
			if rec and rec.tier > 1 then
				T.setTier(panel, rec.tier)
			end
			drawWeaponDetail(panel, w)
		elseif state.kind == "class" then
			drawClassDetail(panel, state.item or loadout())
		elseif state.kind == "pet" then
			drawComingDetail(
				panel,
				"chest",
				"PET",
				"EMPTY SLOT  ·  FROM THE PET CHEST",
				"Every pet helps in its own way: one fetches crystals, one heals you and your team, others knock enemies back or slow them down."
			)
		elseif Armor.valid(state.item) then
			drawArmorDetail(panel, state.item)
		else
			local piece = ARMOR_PIECES[1]
			for _, p in ARMOR_PIECES do
				if p.id == state.item then
					piece = p
				end
			end
			drawComingDetail(
				panel,
				"shoulders",
				piece.label,
				next(profile.armor) and "EMPTY SLOT" or "EMPTY SLOT  ·  FROM ARMOR CHESTS",
				next(profile.armor) and "Pick an armor piece on the left to wear it here."
					or "Copies upgrade a piece from Tier I to Tier IV, like weapons. The rarer the set, the cooler it looks."
			)
		end
		slideIn(right, UDim2.new(1, 16, 0.5, 30), UDim2.new(1, -24, 0.5, 30))
	end

	-- Upgrade view ----------------------------------------------------------------------
	local function drawUpgrade()
		local w = Weapons.ById[state.item]
		local rec = profile.weapons[w.id]
		local tier = rec and rec.tier or 0
		local need = rec and opts.need(rec)
		local left = group("Left", Vector2.new(0, 0.5), UDim2.new(0, 24, 0.5, 30), LEFT_W, LEFT_H)
		local panel = T.panel(left, "Panel", 0, 0, LEFT_W, LEFT_H, "panel")
		plate(left, "UPGRADES", 20, -34)
		local rowH = 190
		for t = 1, 4 do
			local y = 50 + (t - 1) * (rowH + 14)
			local done = rec and t < tier
			local now = rec and t == tier
			local nextUp = rec and t == tier + 1
			local card = T.panel(panel, "Tier" .. t, 22, y, LEFT_W - 44, rowH, (now or nextUp) and "panel" or "inset")
			if now and t > 1 then
				T.setTier(card, t)
			end
			local title = T.label(
				card,
				"Title",
				"TIER " .. T.Roman[t],
				24,
				14,
				300,
				44,
				34,
				(done or now or nextUp) and T.Tier[t] or C.dim
			)
			title.TextXAlignment = Enum.TextXAlignment.Left
			if done then
				tick(card, 190, 24, 26)
			end
			local tag = now and "NOW" or nextUp and "NEXT" or nil
			if tag then
				local tg = T.label(card, "Tag", tag, LEFT_W - 190, 18, 120, 34, 22, now and C.cream or C.lime)
				tg.TextXAlignment = Enum.TextXAlignment.Right
			end
			local gains = tierGains(w, t)
			local body = T.text(
				card,
				"Gains",
				table.concat(gains, "\n"),
				26,
				60,
				LEFT_W - 100,
				56,
				24,
				(done or now or nextUp) and C.white or C.dim
			)
			body.TextYAlignment = Enum.TextYAlignment.Top
			if t > 1 then
				local cost = T.text(
					card,
					"Cost",
					"Uses "
						.. Chests.upgradeCost(w.id, t - 1)
						.. " copies + "
						.. Chests.upgradeEmeralds(w.id, t - 1)
						.. " emeralds  ·  starts runs at Tier "
						.. T.Roman[t],
					26,
					120,
					LEFT_W - 100,
					24,
					17,
					C.muted
				)
				cost.TextYAlignment = Enum.TextYAlignment.Top
			end
			if nextUp then
				body.Size = UDim2.fromOffset(300, 56)
				local b = T.button(card, "Upgrade", "UPGRADE", LEFT_W - 250, 64, 180, 64, function()
					upgrade(w.id)
				end, not ready(w.id))
				b.Caption.TextSize = 26
				b.Interactable = ready(w.id)
			end
		end
		slideIn(left, UDim2.new(0, -40, 0.5, 30), UDim2.new(0, 24, 0.5, 30))

		local right = group("Right", Vector2.new(1, 0.5), UDim2.new(1, -24, 0.5, 30), RIGHT_W, 600)
		local rp = T.panel(right, "Panel", 0, 0, RIGHT_W, 600, "panel")
		if tier > 1 then
			T.setTier(rp, tier)
		end
		header(
			rp,
			WeaponIcons[w.id],
			rec and tier,
			w.name,
			rarityTag(w.id) .. "  ·  TIER " .. (rec and (tier .. " / 4") or "NOT OWNED"),
			rec and T.Tier[tier] or C.white
		)
		local st = weaponAt(w, math.max(tier, 1))
		local nx = need and weaponAt(w, tier + 1)
		statRow(
			rp,
			180,
			"Damage",
			tostring(st.damage),
			nx and nx.damage > st.damage and ("+" .. (nx.damage - st.damage)) or nil
		)
		local rateGain = nx and nx.rate - st.rate
		statRow(
			rp,
			222,
			"Attacks / sec",
			fmtRate(st.rate),
			rateGain and rateGain > 0.005 and ("+" .. fmtRate(rateGain)) or nil
		)
		statRow(rp, 264, "Range", tostring(st.range))
		if rec then
			local ct = T.label(rp, "CopiesTitle", "COPIES", 24, 320, 200, 30, 22, C.muted)
			ct.TextXAlignment = Enum.TextXAlignment.Left
			T.upgradeBar(rp, "Copies", 24, 356, RIGHT_W - 48, 30, rec.have, need)
			local gems = need and Chests.upgradeEmeralds(w.id, rec.tier)
			if need and rec.have >= need and profile.gems < gems then
				centred(T.label(rp, "Need", "NEED " .. (gems - profile.gems) .. " MORE EMERALDS", 24, 398, RIGHT_W - 48, 34, 22, C.negative))
			elseif need and rec.have < need then
				centred(
					T.label(
						rp,
						"Need",
						"NEED " .. (need - rec.have) .. " MORE " .. (need - rec.have == 1 and "COPY" or "COPIES"),
						24,
						398,
						RIGHT_W - 48,
						34,
						22,
						C.negative
					)
				)
			elseif not need then
				centred(T.label(rp, "Max", "FULLY UPGRADED", 24, 398, RIGHT_W - 48, 34, 24, C.gold))
			end
			local b = T.button(rp, "UpgradeBig", need and ("UPGRADE  ·  " .. gems .. " EMERALDS") or "MAX TIER", 24, 452, RIGHT_W - 48, 92, function()
				upgrade(w.id)
			end, not ready(w.id))
			b.Caption.TextSize = need and 30 or 40
			b.Interactable = ready(w.id)
			if ready(w.id) then
				b.Caption.TextColor3 = C.ink
				b.Caption.TextStrokeTransparency = 1
			end
		else
			T.text(
				rp,
				"How",
				"You don't own this weapon yet. It drops from chests as a " .. (Chests.RarityOf[w.id] or "Common") .. " weapon.",
				24,
				330,
				RIGHT_W - 48,
				60,
				19,
				C.muted
			)
		end
		slideIn(right, UDim2.new(1, 16, 0.5, 30), UDim2.new(1, -24, 0.5, 30))
		Stage.SetView("upgrade", w.id, T.Tier[math.max(tier, 1)])
	end

	-- Bottom: CLOSE / BACK ---------------------------------------------------------------
	local function drawBottom()
		local bottom = group("Bottom", Vector2.new(0.5, 1), UDim2.new(0.5, 0, 1, -18), 360, 86)
		local upgradeMode = state.mode == "upgrade"
		local b = T.button(bottom, "Close", upgradeMode and "BACK" or "CLOSE", 0, 0, 360, 86, function()
			if state.mode == "upgrade" then
				state.mode = "main"
				Stage.SetView("hero")
				animate = true
				draw()
			else
				self.Close()
			end
		end, true)
		T.setTier(b, 4)
		b.Caption.TextSize = 46
	end

	-- Drag on the empty middle of the screen to turn the avatar.
	local function drawDrag()
		local drag = T.make("TextButton", root, {
			Name = "DragArea",
			Text = "",
			BackgroundTransparency = 1,
			Size = UDim2.fromScale(1, 1),
			AutoButtonColor = false,
			Selectable = false,
			ZIndex = 0,
		})
		local last
		drag.InputBegan:Connect(function(input)
			if
				input.UserInputType == Enum.UserInputType.MouseButton1
				or input.UserInputType == Enum.UserInputType.Touch
			then
				last = input.Position
			end
		end)
		drag.InputEnded:Connect(function(input)
			if
				input.UserInputType == Enum.UserInputType.MouseButton1
				or input.UserInputType == Enum.UserInputType.Touch
			then
				last = nil
			end
		end)
		drag.InputChanged:Connect(function(input)
			if
				last
				and (
					input.UserInputType == Enum.UserInputType.MouseMovement
					or input.UserInputType == Enum.UserInputType.Touch
				)
			then
				Stage.Turn((input.Position.X - last.X) * 0.012)
				last = input.Position
			end
		end)
	end

	draw = function()
		if not root then
			return
		end
		profile = opts.profile()
		for _, c in root:GetChildren() do
			c:Destroy()
		end
		table.clear(groups)
		drawDrag()
		drawTop()
		if state.mode == "upgrade" and state.item and Weapons.ById[state.item] then
			drawUpgrade()
		else
			state.mode = "main"
			drawCollection()
			drawSlots()
			drawDetail()
			local _, weapon = loadout()
			Stage.SetStarter(weapon)
			Stage.SetView("hero")
		end
		drawBottom()
		fit()
		animate = false
	end

	local profileConn
	-- tab: 'Weapons' | 'Armor' | 'Pets'. Returns {Root, Close} for the lobby's window stack.
	function self.Open(tab)
		if root then
			self.Close()
		end
		state.tab = tab or state.tab or "Weapons"
		state.mode, state.kind, state.item = "main", nil, nil
		animate = true
		table.clear(scroll)
		profile = opts.profile()
		root = T.frame(screen, "Root", 0, 0, 0, 0)
		root.Size = UDim2.fromScale(1, 1)
		screen.Enabled = true
		local _, weapon = loadout()
		if not Stage.Show(weapon) then
			fallback = {
				blur = T.make("BlurEffect", Lighting, { Name = "ArmoryBlur", Size = 16 }),
				shade = T.make("Frame", screen, {
					Name = "Shade",
					Size = UDim2.fromScale(1, 1),
					BackgroundColor3 = C.shade,
					BackgroundTransparency = 0.3,
					BorderSizePixel = 0,
					ZIndex = 0,
				}),
			}
			fallback.shade.LayoutOrder = -1
		end
		if opts.onVisible then
			opts.onVisible(false)
		end
		profileConn = player.AttributeChanged:Connect(function(name)
			if string.sub(name, 1, 7) == "Profile" or name == "LoadoutClass" or name == "LoadoutWeapon" then
				draw()
			end
		end)
		draw()
		return { Root = root, Close = self.Close }
	end

	function self.Close()
		if not root then
			return
		end
		if profileConn then
			profileConn:Disconnect()
			profileConn = nil
		end
		local r = root
		root = nil
		r:Destroy()
		screen.Enabled = false
		if fallback then
			fallback.blur:Destroy()
			fallback.shade:Destroy()
			fallback = nil
		end
		Stage.Hide()
		if opts.onVisible then
			opts.onVisible(true)
		end
	end

	-- Leaving the lobby or respawning closes the Armory and returns the camera.
	player.CharacterRemoving:Connect(function()
		self.Close()
	end)
	return self
end

return A
