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
local StatPlates = require(RS:WaitForChild("StatPlates")) -- damage, health and Power under the dais (plan K)
local Card = require(RS:WaitForChild("ItemCardUI"))
local combat = RS:WaitForChild("RogueliteCombat")
local Weapons = require(combat:WaitForChild("WeaponCatalog"))
local Stats = require(combat:WaitForChild("CharacterStats"))
local Chests = require(combat:WaitForChild("ChestConfig"))
local Armor = require(combat:WaitForChild("ArmorCatalog"))
local Pets = require(combat:WaitForChild("PetConfig"))
local WeaponIcons = require(RS:WaitForChild("WeaponInventoryUI")).Icons
local C = T.Color
local A = {}

-- Layout is in design pixels on a canvas the size of the screen (T.canvas: one scale for
-- everything, 1920x1080 on a 16:9 monitor, about 1690x780 on a phone). Side panels hug the canvas
-- edges; the loadout slots fill the gap between them, centred on the avatar and sized to fit.
-- Nothing is placed by independent per-group scales, so pieces cannot drift into each other when
-- the screen's shape changes.
local MARGIN = 24
local LEFT_H = 900 -- tallest the side panels get; shorter canvases shrink them and lists scroll
local RIGHT_W, RIGHT_H = 500, 810
local UPGRADE_H = 600 -- right panel height in the upgrade view
local CARD, CARD_H, GAP = 164, 206, 14
local function leftWidth(cols)
	-- 22 px border on each side, cards and gaps, and room for the scroll bar.
	return 22 + cols * CARD + (cols - 1) * GAP + 14 + 22
end
-- Loadout slots: SLOT squares with a caption under each; the stat plate below them.
local SLOT, SLOT_ROW = 124, 156
local RING_H = 720
-- Half-width of the avatar on screen at 1080 px tall, from the hero camera (20.5 studs, 30° FOV:
-- 98 px per stud, R15 avatar about 4 studs wide) plus a little air.
local AVATAR_HALF = 210
local TOP_H = 150 -- the name and emerald pill at the top centre
local BOTTOM_H = 86 + 18 -- CLOSE / BACK

local TRAITS = {
	pellets = "Fires a spread of pellets.",
	pierce = "Shots pierce through enemies.",
	bounce = "Bounces between enemies.",
	cards = "Throws a three-card volley.",
	shots = "Fires a burst of shots.",
}

-- Player attributes this screen shows: the LobbyUI.profile fields it reads (connected, gems,
-- classes, weapons, armor, wearing, pets, pet) and the loadout preference. ProfileService.publish
-- sets about 24 attributes in a row; the others (ProfileDaily, ProfileBestWaves...) change nothing here.
local REDRAW_ON = {
	ProfileLoaded = true,
	ProfileGems = true,
	ProfileClasses = true,
	ProfileWeapons = true,
	ProfileArmor = true,
	ProfileWearing = true,
	ProfilePets = true,
	ProfilePet = true,
	LoadoutClass = true,
	LoadoutWeapon = true,
}

-- Armor is worn as four pieces (ArmorCatalog); pieces come from chests, and 2 or 4 of a set give
-- its bonuses. The Armor tab lists every set, owned first, unowned pieces locked (like Pets).
-- Pets (PetConfig) hatch from Pet Eggs (the egg merchant); one follows you (EQUIP / UNEQUIP).
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
	local asset = Armor.Icons[Armor.pieceId(setId, slot)]
	if asset then
		return T.icon(parent, "ArmorView", x, y, size, asset)
	end
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

-- A 3D view of one pet: ReplicatedStorage.PetModels[id] at rest, framed from the front-left.
-- Without the model (not installed yet) it shows a rarity-coloured disc with the pet's name.
local function petView(parent, id, x, y, size)
	local asset = Pets.Icons[id]
	if asset then
		return T.icon(parent, "PetView", x, y, size, asset)
	end
	local vp = T.make("ViewportFrame", parent, {
		Name = "PetView",
		BackgroundTransparency = 1,
		Position = UDim2.fromOffset(x, y),
		Size = UDim2.fromOffset(size, size),
		Ambient = Color3.fromRGB(200, 200, 200),
		LightColor = Color3.fromRGB(255, 250, 240),
		LightDirection = Vector3.new(-0.3, -1, 0.5),
	})
	local models = RS:FindFirstChild("PetModels")
	local template = models and models:FindFirstChild(id)
	local pet = Pets.ById[id]
	if not template then
		local disc = T.make("Frame", vp, {
			Name = "Fallback",
			Position = UDim2.fromScale(0.1, 0.1),
			Size = UDim2.fromScale(0.8, 0.8),
			BackgroundColor3 = pet and Chests.RarityColor[pet.rarity] or C.dim,
			BackgroundTransparency = 0.55,
			BorderSizePixel = 0,
		})
		T.make("UICorner", disc, { CornerRadius = UDim.new(0.5, 0) })
		local l = T.label(disc, "Name", pet and string.upper(pet.name) or id, 0, 0, 0, 0, math.max(12, math.floor(size / 7)))
		l.Size = UDim2.fromScale(1, 1)
		return vp
	end
	local m = template:Clone()
	m.Parent = vp
	local box, extent = m:GetBoundingBox()
	local cam = Instance.new("Camera")
	cam.FieldOfView = 30
	-- The pet faces -Z: look from in front, a little left and above.
	cam.CFrame = CFrame.lookAt(
		box.Position + Vector3.new(-0.55, 0.35, -1).Unit * (extent.Magnitude / 2) / math.sin(math.rad(15)),
		box.Position
	)
	cam.Parent = vp
	vp.CurrentCamera = cam
	return vp
end

local function weaponAt(w, tier)
	tier = math.clamp(tier or 1, 1, 4)
	local cd = w.cooldown * (w.tierCooldown[tier] or 1)
	return { damage = w.tierDamage[tier] or w.damage, rate = 1 / cd, range = w.range }
end

-- Godly specials in a sentence each (WeaponCatalog.Godly; plans/2026-10-01-G).
local GODLY_TEXT = {
	["36"] = "Spins a full circle. 1 in 3 kills rise as crimson wraiths that hunt for you (up to 4).",
	["37"] = "Stabs up close and throws at range. Where it lands, a tidal wave washes enemies away.",
	["38"] = "Each arrow splits in the sky and rains lightning arrows on 5 enemies.",
	["39"] = "The twin daggers zip from enemy to enemy, hitting up to 5 in a chain.",
	["40"] = "Every hit heals you, and kills send blood wisps back into you.",
	["41"] = "Zappy green blasts. Kills disintegrate in a burst that hits the enemies nearby.",
}
local function describe(w)
	if w.godly then
		return (GODLY_TEXT[w.id] or "") .. " One Godly per run; it's never sold in the run shop."
	end
	-- The starter class, types and attack have their own rows now (2026-10-09); this is what it does.
	local out = {}
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
		-- With its numbers (WeaponCatalog.slowText, 2026-10-03): "Slows enemies 35% for 2 s."
		table.insert(out, Weapons.slowText and Weapons.slowText(w) or "Slows enemies down.")
	end
	if w.lightning then
		table.insert(out, "Lightning chains to nearby enemies.")
	end
	if w.blastRadius then
		table.insert(out, "Explodes on impact.")
	end
	local move = Weapons.legendaryText and Weapons.legendaryText(w.id)
	if move then
		table.insert(out, "Tier IV: " .. move)
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
		-- Full screen, minus phone notches and rounded corners. The shade may reach under them.
		ScreenInsets = Enum.ScreenInsets.DeviceSafeInsets,
		ClipToDeviceSafeArea = false,
		ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
		Enabled = false,
	})
	self.Screen = screen
	local fallback -- blur + shade when the hall is not installed
	local root, profile, draw
	-- armorSlot: the Armor tab's slot filter (nil = every slot).
	local state = { tab = "Weapons", mine = false, item = nil, kind = "weapon", mode = "main", armorSlot = nil }
	local itemCard
	local weaponInfoEntries = {} -- exact rendered grid order, including class/filter/ownership ordering
	-- Panels slide in only when the screen opens or switches between main and upgrade views;
	-- a plain redraw (selecting an item, a profile update) must not move anything.
	local animate = false
	local justOpened = false -- the next draw is the first since Open (gamepad selection starts there)
	local scroll = {} -- tab -> grid scroll position, kept across redraws
	-- Slides a panel in from `dx` canvas pixels to the side of where it was placed.
	local function slideIn(frame, dx)
		if not animate then
			return
		end
		local to = frame.Position
		frame.Position = to + UDim2.fromOffset(dx, 0)
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
		-- An owned Godly starts a run with any class, any other weapon with the class anywhere in its
		-- list (RunSetupRules.validLoadout, 2026-10-04).
		if not w or (not Weapons.inClass(w, class) and not w.godly) or not profile.weapons[weapon] then
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
	-- Pets: owned record (LobbyUI parses ProfilePets) and whether its upgrade is ready.
	local function petRec(id)
		return profile.pets and profile.pets[id]
	end
	local function petReady(id)
		local rec = petRec(id)
		return rec ~= nil
			and rec.tier < 4
			and rec.have >= Chests.upgradeCost(id, rec.tier)
			and profile.gems >= Chests.upgradeEmeralds(id, rec.tier)
	end

	-- Layout ---------------------------------------------------------------------
	-- L: where every piece goes on the current canvas, in canvas pixels. Recomputed (and the
	-- screen redrawn) when the screen changes size.
	-- Example, 1920x1080: panels 580 and 500 wide, slots 316 px either side of the avatar at full
	-- size. 844x390 phone: canvas 1688x780, 2-column list, slots about 70% size.
	local L, canvas
	local function plan(c)
		local l = table.clone(c)
		-- Side panels sit under Roblox's top-bar buttons (the title plate pokes 34 px above them).
		local bandTop = math.max(c.top, 14) + 34 + 10
		local bandBottom = c.h - MARGIN
		-- The avatar is drawn by the 3D camera: its size follows the screen height (or the width on
		-- screens narrower than 16:9, see ArmoryStage.FieldOfView), not this canvas.
		local vx, vy = c.w * c.s, c.h * c.s
		local avatarHalf = AVATAR_HALF * math.min(vy, vx * 9 / 16) / 1080 / c.s
		local function ring(leftW)
			local free = math.min(c.w / 2 - MARGIN - leftW, c.w / 2 - MARGIN - RIGHT_W) - 16
			local innerMin = avatarHalf + 16
			local inner = math.clamp(free - SLOT - 8, innerMin, math.max(innerMin, 316 * avatarHalf / AVATAR_HALF))
			local top, bottom = TOP_H, c.h - BOTTOM_H - 12
			local k = math.min(1, (free - inner) / (SLOT + 8), (bottom - top) / RING_H)
			-- Hidden when the slots would be smaller than a comfortable tap (44 screen px).
			if k * SLOT * c.s < 44 then
				return nil
			end
			local cy = math.clamp(c.h / 2 + 10, top + RING_H * k / 2, bottom - RING_H * k / 2)
			return { k = k, inner = inner / k, x = c.w / 2, y = cy }
		end
		l.cols = 3
		l.ring = ring(leftWidth(3))
		if not l.ring then
			l.cols = 2
			l.ring = ring(leftWidth(2))
		end
		l.leftW = leftWidth(l.cols)
		-- The name and emeralds use the gap between the panels; if that's too narrow for the emerald
		-- pill, the panels start below them instead.
		l.topW = math.min(700, c.w - 2 * (MARGIN + math.max(l.leftW, RIGHT_W) + 16))
		if l.topW < 260 then
			l.topW = math.min(700, c.w - 2 * MARGIN)
			bandTop = math.max(bandTop, TOP_H + 34 + 10)
		end
		local band = bandBottom - bandTop
		l.leftH = math.min(LEFT_H, band)
		l.leftY = bandTop + (band - l.leftH) / 2
		l.rightH = math.min(RIGHT_H, band)
		l.rightY = bandTop + (band - l.rightH) / 2
		l.upgradeH = math.min(UPGRADE_H, band)
		l.upgradeY = bandTop + (band - l.upgradeH) / 2
		return l
	end
	local function group(name, x, y, w, h)
		return T.frame(canvas, name, x, y, w, h)
	end
	-- Content taller than its panel scrolls inside it (short phone screens); otherwise it is drawn
	-- straight onto the panel. Returns the frame to draw the content into.
	local function body(panel, contentH)
		if panel.Size.Y.Offset >= contentH then
			return panel
		end
		local sc = T.scroll(panel, "Body", 0, 8, 0, 0)
		sc.Size = UDim2.new(1, -8, 1, -16)
		sc.CanvasSize = UDim2.fromOffset(0, contentH)
		return sc
	end

	-- Pieces --------------------------------------------------------------------
	local function currencyPill(parent, name, x, asset, value, color)
		local row = T.panel(parent, name, x, 0, 200, 56, "inset")
		T.icon(row, "Icon", 8, 6, 44, asset)
		local v = T.label(row, "Value", value, 58, 6, 130, 44, 28, color)
		v.TextXAlignment = Enum.TextXAlignment.Left
		return row
	end

	local function drawTop()
		local tw = L.topW
		local top = group("Top", (L.w - tw) / 2, 14, tw, 150)
		local name = centred(T.label(top, "PlayerName", player.DisplayName, 0, 0, tw, 56, 48))
		name.TextWrapped = false
		local fmt = function(n)
			n = tonumber(n) or 0
			return n >= 1e4 and string.format("%.1fK", n / 1e3) or tostring(n)
		end
		-- Emeralds are the only currency (keys were dropped); one pill, centred under the name.
		currencyPill(top, "Emeralds", 0, "emerald", fmt(profile.gems), C.emerald)
		top.Emeralds.Position = UDim2.fromOffset((tw - 200) / 2, 64)
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
			chip.Position = UDim2.fromOffset(tw / 2, 124)
		end
	end

	local function select(kind, id)
		if state.kind == kind and state.item == id then
			return
		end
		state.kind, state.item = kind, id
		draw()
	end

	local function closeInfo()
		if itemCard then itemCard.Close(true); itemCard = nil end
	end
	local function showInfo(id)
		closeInfo()
		local entries = state.tab == "Weapons" and table.clone(weaponInfoEntries) or {}
		local visible = false
		for _, entry in entries do if entry.id == id then visible = true;break end end
		-- A details/upgrade entry outside the visible filter is a single-item view, not a jump
		-- into hidden classes or an unrelated raw catalog ordering.
		if not visible then entries = { { id = id, rarity = Chests.RarityOf[id] or "Common" } } end
		itemCard = Card.open(canvas, L, {
			list = entries, id = id, source = "collection", profile = opts.profile,
			onClose = function() itemCard = nil end,
		})
		return itemCard
	end
	self.ShowInfo = showInfo -- also used by the Studio interaction check

	local function watchAttacks(id, tier)
		local module = RS:FindFirstChild("WeaponShowcaseUI")
		if not module then T.toast(screen, "Attack preview is loading", C.muted); return end
		local ok, preview = pcall(require, module)
		if not ok then T.toast(screen, "Attack preview is unavailable", C.negative); return end
		local tab = state.tab
		self.Close()
		preview.open(player, id, tier, { onClose = function()
			if player:GetAttribute("LobbyPreviewActive") == true and not player:GetAttribute("LobbyQueue") then
				opts.openWindow("Armory", { tab = tab, kind = "weapon", id = id })
			end
		end })
	end

	-- A square collection card: tier corners, icon, name and have/need bar.
	local function weaponCard(parent, w, x, y)
		table.insert(weaponInfoEntries, { id = w.id, rarity = Chests.RarityOf[w.id] or "Common" })
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
		Card.infoButton(card, CARD - 42, 10, 32, function() showInfo(w.id) end)
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
				tick(card, CARD - 38, 82, 28)
			end
			if ready(w.id) then
				upArrow(card, CARD - 44, 46, 34)
			end
		else
			RunSetup.lock(card, 12, 12, 26)
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
			RunSetup.lock(card, 12, 12, 26)
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

	-- A pet card: 3D view, name, rarity (or PET EGG while not owned), tier, tick when following you.
	local function petCard(parent, pet, x, y)
		local rec = petRec(pet.id)
		local chosen = state.kind == "pet" and state.item == pet.id
		local card = T.button(parent, "P_" .. pet.id, "", x, y, CARD, CARD_H, function()
			select("pet", pet.id)
		end, not chosen)
		card.Caption.Visible = false
		if rec and not chosen then
			T.setTier(card, rec.tier)
		end
		local view = petView(card, pet.id, (CARD - 124) / 2, 6, 124)
		view.ImageTransparency = rec and 0 or 0.62
		local n = centred(T.label(card, "Name", pet.name, 6, 132, CARD - 12, 30, 20, rec and C.white or C.dim))
		n.TextWrapped = false
		n.TextScaled = true
		T.make("UITextSizeConstraint", n, { MaxTextSize = 20, MinTextSize = 12 })
		local k = centred(
			T.text(card, "Rarity", rec and string.upper(pet.rarity) or "PET EGG", 6, 164, CARD - 12, 22, 16, rec and Chests.RarityColor[pet.rarity] or C.dim)
		)
		if rec then
			T.tierBadge(card, rec.tier, 10, 10)
			if profile.pet == pet.id then
				tick(card, CARD - 38, 10, 28)
			end
			if petReady(pet.id) then
				upArrow(card, CARD - 44, 34, 34)
			end
		else
			RunSetup.lock(card, 12, 12, 26)
		end
		if chosen then
			n.TextColor3, k.TextColor3 = C.ink, C.ink
			n.TextStrokeTransparency, k.TextStrokeTransparency = 1, 1
		end
		return card
	end

	-- Equip a pet (id) or put it away (nil). ProfileService checks ownership; the follower appears
	-- from the server's workspace.RoguelitePets folder (PetVisuals).
	local function equipPet(id)
		local r = combat.ProfileAction:InvokeServer("EquipPet", id)
		T.toast(screen, r.message or "", r.ok and C.lime or C.negative)
		if r.ok then
			T.sound("ui_equip")
		end
	end

	-- "Coming" panel for tabs whose items are not in the game yet: a title, one line, a few facts.
	local function comingPanel(parent, title, body, lines)
		local h = 118 + #lines * 44
		local lw = L.leftW
		local box = T.panel(parent, "Coming", 0, 0, lw - 60, h, "inset")
		local t = T.label(box, "Title", title, 20, 18, lw - 100, 40, 30)
		t.TextXAlignment = Enum.TextXAlignment.Left
		local b = T.text(box, "Body", body, 20, 62, lw - 100, 30, 18, C.muted)
		b.TextYAlignment = Enum.TextYAlignment.Top
		for i, line in lines do
			local row = T.panel(box, "Row" .. i, 20, 104 + (i - 1) * 44, lw - 100, 38, "panel")
			local l = T.label(row, "Text", line, 16, 2, lw - 132, 34, 20, C.cream)
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
		local lw, lh = L.leftW, L.leftH
		local left = group("Left", MARGIN, L.leftY, lw, lh)
		local panel = T.panel(left, "Panel", 0, 0, lw, lh, "panel")
		plate(left, "ARMORY", 20, -34)
		local tabs = T.tabs(panel, 22, 44, lw - 44, 52, { "Classes", "Weapons", "Armor", "Pets" }, state.tab, function(id)
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
			b.Caption.TextSize = 18
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
			local cbW = math.min(300, lw - 44 - 140)
			checkbox(panel, "MyClass", "MY CLASS · " .. string.upper(class), 22, y0, cbW, state.mine, function()
				state.mine = not state.mine
				draw()
			end)
			local owned, total = 0, 0
			for _, w in Weapons.List do
				-- Every catalog weapon is browsable, including unowned Godlies.
				total += 1
				if profile.weapons[w.id] then owned += 1 end
			end
			local count =
				T.label(panel, "Owned", owned .. " / " .. total .. " OWNED", 30 + cbW, y0, lw - 52 - cbW, 50, 18, C.muted)
			count.TextXAlignment = Enum.TextXAlignment.Right
			y0 += 64
		end
		-- Every armor set whose meshes are installed: sets with an owned piece first, then the rest
		-- in catalog order. Only listing owned sets left a player with no armor on the old
		-- "Armor is coming" panel (user, 2026-10-03).
		local armorSets, unowned = {}, {}
		for _, set in Armor.Sets do
			local owns = false
			for _, sl in Armor.Slots do
				owns = owns or profile.armor[Armor.pieceId(set.id, sl)] ~= nil
			end
			if armorModel(set.id) then
				table.insert(owns and armorSets or unowned, set)
			end
		end
		table.move(unowned, 1, #unowned, #armorSets + 1, armorSets)
		if state.tab == "Armor" and #armorSets > 0 then
			local filters = { "All" }
			for _, sl in Armor.Slots do
				table.insert(filters, sl)
			end
			T.tabs(panel, 22, y0, lw - 44, 44, filters, state.armorSlot or "All", function(id)
				state.armorSlot = id ~= "All" and id or nil
				state.kind, state.item = nil, nil
				draw()
			end)
			y0 += 58
		end
		local grid = T.scroll(panel, "Grid", 22, y0, lw - 36, lh - y0 - 22)
		local tab = state.tab
		grid:GetPropertyChangedSignal("CanvasPosition"):Connect(function()
			scroll[tab] = grid.CanvasPosition
		end)
		local cols = L.cols
		local function cell(i)
			return ((i - 1) % cols) * (CARD + GAP), math.floor((i - 1) / cols) * (CARD_H + GAP)
		end
		local y = 0
		if state.tab == "Classes" then
			if not state.item then state.kind, state.item = "class", class end
			for i, name in Stats.ClassOrder do
				local x, dy = cell(i)
				local owned = profile.classes[name] == true
				local b = T.button(grid, "Class_" .. name, "", x, dy, CARD, CARD_H, function() select("class", name) end, state.item ~= name)
				b.Caption.Visible = false
				local icon = T.icon(b, "Icon", 26, 12, 112, WeaponIcons[Rules.Signature[name]])
				icon.ImageTransparency = owned and 0 or 0.5
				T.label(b, "Name", name, 6, 124, CARD - 12, 30, 22)
				T.label(b, "Status", name == class and "EQUIPPED" or owned and "CHOOSE CLASS" or "LOCKED", 6, 164, CARD - 12, 24, 15, name == class and C.lime or C.muted)
				if not owned then RunSetup.lock(b, 10, 10, 26) end
			end
			y = math.ceil(#Stats.ClassOrder / cols) * (CARD_H + GAP)
		elseif state.tab == "Weapons" then
			weaponInfoEntries = {}
			-- Current class first; owned weapons first inside each class.
			local classes = { class }
			if not state.mine then
				for _, c in Stats.ClassOrder do
					if c ~= class then
						table.insert(classes, c)
					end
				end
			end
			-- Godlies sit above every class: owning one permits any class to start with it.
			local godlies = {}
			for _, w in Weapons.List do
				if w.godly then
					table.insert(godlies, w)
				end
			end
			if #godlies > 0 then
				local h = T.label(grid, "Header_Godly", "GODLY", 4, y, lw - 60, 32, 22, Chests.RarityColor.Godly)
				h.TextXAlignment = Enum.TextXAlignment.Left
				y += 38
				for i, w in godlies do
					local x, dy = cell(i)
					weaponCard(grid, w, x, y + dy)
				end
				y += math.ceil(#godlies / cols) * (CARD_H + GAP) + 8
			end
			-- Each weapon once, under its one starter class (2026-10-09): your class first, then the
			-- others in class order (Brawler, Gunner, Chef, Juggler, Handyman, Mage).
			for _, c in classes do
				local list = table.clone(Rules.classWeapons(c))
				if #list == 0 then
					continue
				end
				table.sort(list, function(a, b)
					local ra, rb = profile.weapons[a.id], profile.weapons[b.id]
					if (ra ~= nil) ~= (rb ~= nil) then
						return ra ~= nil
					end
					return a.id < b.id
				end)
				if not state.mine or c == class then
					-- Your class says what it gets: "CHEF  your class · +10% damage with these".
					local head = string.upper(c) .. (profile.classes[c] and "" or "  ·  LOCKED")
					local note = c == class and ("your class · +" .. Stats.Specialty .. (L.s < 0.75 and "% dmg" or "% damage with these")) or nil
					local hw = note and math.ceil(game:GetService("TextService"):GetTextSize(head, 22, T.Font, Vector2.new(1000, 100)).X * 1.12) + 8 or lw - 60
					local h = T.label(grid, "Header_" .. c, head, 4, y, hw, 32, 22, profile.classes[c] and C.lime or C.dim)
					h.TextXAlignment = Enum.TextXAlignment.Left
					if note then
						T.text(grid, "Header_" .. c .. "Note", note, 4 + hw + 6, y + 4, lw - 60 - hw - 6, 26, L.s < 0.75 and 18 or 16, C.cream)
					end
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
			-- All 12 pets: owned first, then by rarity (PetConfig order); one follows you at a time.
			local list, owned = table.clone(Pets.List), 0
			table.sort(list, function(a, b)
				local ra, rb = petRec(a.id), petRec(b.id)
				if (ra ~= nil) ~= (rb ~= nil) then
					return ra ~= nil
				end
				return a.order < b.order
			end)
			for _, pet in list do
				owned += petRec(pet.id) and 1 or 0
			end
			local h = T.label(grid, "Header_Pets", "PETS · " .. owned .. " / " .. #list .. " OWNED", 4, y, lw - 60, 32, 22, C.lime)
			h.TextXAlignment = Enum.TextXAlignment.Left
			y += 38
			for i, pet in list do
				local x, dy = cell(i)
				petCard(grid, pet, x, y + dy)
			end
			y += math.ceil(#list / cols) * (CARD_H + GAP) + 8
			if not state.item then
				state.kind, state.item = "pet", (profile.pet and petRec(profile.pet)) and profile.pet or list[1].id
			end
		elseif #armorSets > 0 then
			-- Each set (owned first): its pieces in the filtered slot(s), unowned ones locked.
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
						lw - 60,
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
			-- Only when no set's meshes have arrived yet (ReplicatedStorage.ArmorSets).
			y = comingPanel(grid, "Armor is loading", "Reopen the Armory in a moment. Armor pieces come from chests.", {
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
		slideIn(left, -40)
	end

	-- Centre: loadout slots around the avatar -------------------------------------
	local function slot(parent, name, caption, x, y, callback, fill)
		local b = T.button(parent, name, "", x, y, SLOT, SLOT, callback, true)
		b.Caption.Visible = false
		local cap = centred(T.label(parent, name .. "Caption", caption, x - 20, y + SLOT + 2, SLOT + 40, 26, 20))
		cap.TextWrapped = false
		fill(b)
		return b
	end
	local function emptySlot(b, chosen)
		-- Dark text on the lime "selected" fill; grey on the charcoal one. "EMPTY", never "SOON":
		-- pets and armor are in the game (user, 2026-10-03: "why does pet say soon").
		local ink = chosen and C.ink or C.dim
		local plus = centred(T.label(b, "Plus", "+", 0, 14, SLOT, 70, 64, ink))
		plus.Size = UDim2.new(1, 0, 0, 80)
		local soon = centred(T.text(b, "Soon", "EMPTY", 10, SLOT - 34, SLOT - 20, 22, 15, ink))
		if chosen then
			plus.TextStrokeTransparency, soon.TextStrokeTransparency = 1, 1
			T.setPrimary(b, true)
		end
	end

	local function drawSlots()
		local r = L.ring
		if not r then
			return -- screen too narrow for the slots (small phones): the avatar still wears it all
		end
		local class, weapon = loadout()
		-- Two columns `inner` px either side of the avatar's centre, scaled by k to fit the gap.
		local gw = 2 * (r.inner + SLOT + 20)
		local mid = T.frame(canvas, "Slots", r.x, r.y, gw, RING_H)
		mid.AnchorPoint = Vector2.new(0.5, 0.5)
		T.make("UIScale", mid, { Scale = r.k })
		local LX, RX = gw / 2 - r.inner - SLOT, gw / 2 + r.inner
		local rowY = function(i)
			return 8 + (i - 1) * SLOT_ROW
		end
		-- Left column: the four armor pieces.
		for i, piece in ARMOR_PIECES do
			local setId = profile.wearing[piece.id]
			setId = setId and armorModel(setId) and setId or nil
			local id = setId and Armor.pieceId(setId, piece.id) or piece.id
			slot(mid, piece.id .. "Slot", piece.label, LX, rowY(i), function()
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
					emptySlot(b, state.kind == "armor" and state.item == id)
				end
			end)
		end
		-- Right column: starting weapon, pet, class, centred against the four armor slots. There is no
		-- "ready upgrades" slot any more: it opened the first upgradable item, whatever it was, and
		-- players spent emeralds on gear they didn't care about (user, 2026-10-03). The starting
		-- weapon still shows its own upgrade arrow.
		local rec = profile.weapons[weapon]
		slot(mid, "WeaponSlot", "WEAPON", RX, rowY(1.5), function()
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
		-- The equipped pet: its 3D view and tier, its name as the caption.
		local petId = profile.pet and petRec(profile.pet) and profile.pet or nil
		slot(mid, "PetSlot", petId and string.upper(Pets.ById[petId].name) or "PET", RX, rowY(2.5), function()
			state.tab = "Pets"
			state.kind, state.item = "pet", petId
			draw()
		end, function(b)
			if petId then
				petView(b, petId, 4, 4, SLOT - 8)
				T.tierBadge(b, petRec(petId).tier, 8, 8)
				if state.kind == "pet" and state.item == petId then
					T.setPrimary(b, true)
				end
			else
				emptySlot(b, state.kind == "pet")
			end
		end)
		slot(mid, "ClassSlot", "CLASS", RX, rowY(3.5), function()
			select("class", class)
		end, function(b)
			local icon = T.icon(b, "Icon", 22, 8, SLOT - 44, WeaponIcons[Rules.Signature[class]])
			icon.ImageTransparency = 0.25
			centred(T.label(b, "Name", string.upper(class), 4, SLOT - 34, SLOT - 8, 28, 20, C.lime))
			if state.kind == "class" then
				T.setPrimary(b, true)
			end
		end)
		-- Stat plates under the dais (ui/StatPlates.luau, plan K): the starter's damage at its tier,
		-- class health, and gear power with its ? card.
		local hp = Stats.resolve(class, 0).MaxHP
		local w = Weapons.ById[weapon]
		local dmg = w and weaponAt(w, rec and rec.tier or 1).damage or 0
		StatPlates.draw(mid, gw / 2, 640, math.min(StatPlates.WIDTH, gw - 16), {
			damage = dmg,
			health = math.floor(hp + 0.5),
			weaponIcon = WeaponIcons[weapon],
			weaponName = w and w.name or "Starter",
			parts = Rules.powerParts(player, weapon),
			maps = Rules.Maps,
		})
	end

	-- Right: details ---------------------------------------------------------------------
	local function statRow(parent, y, label, value, delta)
		-- Label | value | gain for the next tier (right column, blank when there is none).
		local l = T.label(parent, "Stat_" .. label, label, 24, y, RIGHT_W - 292, 40, 24, C.muted)
		l.TextXAlignment = Enum.TextXAlignment.Left
		local v = T.label(parent, "Value_" .. label, value, RIGHT_W - 260, y, 130, 40, 28)
		v.TextXAlignment = Enum.TextXAlignment.Right
		if delta then
			local d = T.label(parent, "Delta_" .. label, delta, RIGHT_W - 124, y, 100, 40, 24, C.lime)
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
		local before = profile.weapons[id] or profile.armor[id] or petRec(id)
		local r = combat.ProfileAction:InvokeServer("Upgrade", id)
		T.toast(screen, r.message or "", r.ok and C.lime or C.negative)
		if r.ok then
			-- ProfileWeapons changes and redraws; celebrate in the new tier's colour.
			T.sound("ui_upgrade")
			Stage.Burst(T.Tier[math.min(4, (before and before.tier or 1) + 1)])
		end
	end

	-- Weapon details (2026-10-09 roster mockup): the header (icon, name, rarity and attack, type chips
	-- with literal icons), then rows for STARTER CLASS, ATTACK (what its damage scales with) and
	-- SPECIALTY (what the +10% means for your class), then what it does, its stats, copies and
	-- buttons. Drawn top-down into `panel`; returns the height used (drawDetail scrolls taller ones).
	local function drawWeaponDetail(panel, w)
		local rec = profile.weapons[w.id]
		local tier = rec and rec.tier or 1
		local class, equipped = loadout()
		local TS = game:GetService("TextService")
		-- Phone canvases (scale .5) get bigger chips and row text: text can't draw under 9 screen px.
		local big, ph = L.s < 0.62, L.s < 0.75
		local F = big and { chipH = 40, chip = 21, lab = 21, row = 23, youH = 34, labW = 190 }
			or { chipH = ph and 36 or 32, chip = ph and 18 or 16, lab = ph and 18 or 16, row = ph and 19 or 17, youH = ph and 30 or 24, labW = ph and 170 or 150 }
		local PW = RIGHT_W - 48
		local BH = big and 70 or 58 -- big buttons: a 35 px tap at scale .5
		local word, list = Card.attack(w)
		local name, kind = header(panel, WeaponIcons[w.id], rec and tier, w.name, rarityTag(w.id) .. "  ·  " .. string.upper(word) .. " WEAPON", rec and T.Tier[tier] or C.white)
		name.Position, name.Size = UDim2.fromOffset(170, 24), UDim2.fromOffset(RIGHT_W - 190, 52)
		kind.Position = UDim2.fromOffset(172, 78)
		Card.infoButton(panel.IconWell, 92, 8, 34, function() showInfo(w.id) end)
		local _, chipsH = Card.typeChips(panel, "Types", 170, 110, RIGHT_W - 190, w.types or {}, { h = F.chipH, size = F.chip })
		local y = math.max(166, 110 + chipsH + 12)
		-- Rows: a cream label column, then the content.
		local rowsBox = T.panel(panel, "WeaponInfo", 24, y, PW, 0, "inset")
		local cy = 6
		local cw = PW - F.labW - 12
		local function row(key, label, h, fill)
			if cy > 6 then
				T.make("Frame", rowsBox, { Name = key .. "Divider", Position = UDim2.fromOffset(10, cy - 1), Size = UDim2.fromOffset(PW - 20, 2), BackgroundColor3 = Color3.new(0, 0, 0), BackgroundTransparency = 0.45, BorderSizePixel = 0 })
			end
			local l = T.label(rowsBox, key .. "Label", label, 14, cy + (h - F.lab - 6) / 2, F.labW - 14, F.lab + 6, F.lab, C.cream)
			l.TextXAlignment = Enum.TextXAlignment.Left
			l.TextStrokeTransparency = 0.5
			fill(F.labW, cy, h)
			cy += h
		end
		local function textRow(key, label, text)
			local th = math.ceil(TS:GetTextSize((text:gsub("<[^>]->", "")), F.row, T.Body, Vector2.new(cw * 0.94, 1000)).Y) + 2
			local h = math.max(44, th + 14)
			row(key, label, h, function(x, ry)
				local t = T.text(rowsBox, key .. "Text", text, x, ry + (h - th) / 2, cw, th, F.row, C.white)
				t.TextYAlignment = Enum.TextYAlignment.Top
			end)
		end
		row("Starter", "STARTER CLASS", math.max(44, F.youH + 16), function(x, ry, h)
			local chipH = F.youH + 4
			local chip, chipW = Card.classChip(rowsBox, "ClassChip", w, x, ry + (h - chipH) / 2, { h = chipH, size = F.chip, maxW = cw })
			chip:SetAttribute("WeaponId", w.id)
			if not w.godly and w.class == class then
				local you = T.tag(rowsBox, "YourClass", "YOUR CLASS", x + chipW + 8, ry + (h - F.youH) / 2, { h = F.youH, size = F.youH - 10, color = C.lime, textColor = C.ink, maxW = cw - chipW - 8 })
				you.Text.TextStrokeTransparency = 1
			end
		end)
		textRow("Attack", "ATTACK", '<font color="' .. T.hex(C.cream) .. '">' .. word .. "</font> · scales with " .. list)
		textRow("Specialty", "SPECIALTY", Card.specialtyLine(w, class))
		rowsBox.Size = UDim2.fromOffset(PW, cy + 6)
		y += cy + 6 + 10
		local about = describe(w)
		if about ~= "" then
			local dh = math.ceil(TS:GetTextSize(about, 18, T.Body, Vector2.new(PW * 0.88, 1000)).Y) + 6
			local desc = T.text(panel, "Description", about, 24, y, PW, dh, 18, C.muted)
			desc.TextYAlignment = Enum.TextYAlignment.Top
			y += dh + 8
		end
		local st = weaponAt(w, tier)
		T.label(panel, "StatsTitle", "STATS", 24, y, 200, 32, 26).TextXAlignment = Enum.TextXAlignment.Left
		y += 34
		statRow(panel, y, "Damage", tostring(st.damage))
		statRow(panel, y + 34, "Attacks / sec", fmtRate(st.rate))
		statRow(panel, y + 68, "Range", tostring(st.range))
		y += 110
		if rec then
			local need = opts.need(rec)
			local ct = T.label(panel, "CopiesTitle", "COPIES", 24, y, 200, 30, 22, C.muted)
			ct.TextXAlignment = Enum.TextXAlignment.Left
			local nt = T.label(panel, "TierText", need and ("TIER " .. T.Roman[tier] .. "  →  " .. T.Roman[tier + 1]) or "MAX TIER", 220, y, RIGHT_W - 244, 30, 20, T.Tier[math.min(4, tier + 1)])
			nt.TextXAlignment = Enum.TextXAlignment.Right
			T.upgradeBar(panel, "Copies", 24, y + 36, PW, 30, rec.have, need)
			y += 80
			-- EQUIP (2026-10-09): your class keeps it when it is one of your class's weapons or a Godly;
			-- any other weapon switches you to its starter class, if you own that class.
			local startClass = (w.godly or w.class == class) and class or (profile.classes[w.class] and w.class) or nil
			local label = equipped == w.id and "EQUIPPED"
				or startClass == class and "EQUIP AS STARTER"
				or startClass and ("EQUIP AS " .. string.upper(startClass))
				or (string.upper(w.class or "") .. " LOCKED")
			local eq = T.button(panel, "Equip", label, 24, y, PW, BH, function()
				if not startClass then
					return
				end
				sel.class, sel.weapon = startClass, w.id
				-- Only the server-confirmed attributes change the equipped marker and stage.
				local lobby = workspace:FindFirstChild("RogueliteLobby")
				local setup = lobby and lobby:FindFirstChild("RunSetup")
				if setup then
					setup:FireServer("Loadout", startClass, w.id)
				end
			end, true)
			eq.Caption.TextSize = 28
			eq.Interactable = equipped ~= w.id and startClass ~= nil and player:GetAttribute("LobbyLockedIn") ~= true
			y += BH + 8
			local isReady = ready(w.id)
			local up = T.button(panel, "Upgrades", isReady and "UPGRADE READY" or "VIEW UPGRADES", 24, y, PW, BH, function()
				state.mode = "upgrade"
				animate = true
				draw()
			end, not isReady)
			up.Caption.TextSize = 28
			if isReady then
				up.Caption.TextColor3 = C.ink
				up.Caption.TextStrokeTransparency = 1
				local sc = T.make("UIScale", up, { Scale = 1 })
				TweenService:Create(sc, TweenInfo.new(0.7, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut, -1, true), { Scale = 1.03 }):Play()
			end
			y += BH + 12
		else
			local lk = T.label(panel, "NotOwned", "NOT OWNED", 24, y, 300, 34, 28, C.dim)
			lk.TextXAlignment = Enum.TextXAlignment.Left
			local rarity = Chests.RarityOf[w.id] or "Common"
			local how = "One copy from a chest unlocks it. "
				.. (rarity == "Common" and "Every chest has Common weapons." or ("Better chests find " .. rarity .. " weapons more often."))
			local hh = math.ceil(TS:GetTextSize(how, 18, T.Body, Vector2.new(PW * 0.94, 1000)).Y) + 4
			T.text(panel, "How", how, 24, y + 40, PW, hh, 18, C.muted)
			y += 40 + hh + 10
			local b = T.button(panel, "GoChests", "OPEN CHESTS", 24, y, PW, BH, function()
				opts.openWindow("Chests")
			end)
			b.Caption.TextSize = 28
			y += BH + 12
		end
		local preview = T.button(panel, "WatchAttacks", "WATCH ATTACKS", 24, y, 244, 54, function() watchAttacks(w.id, tier) end, true)
		preview.Caption.TextSize = 21
		local journal = T.button(panel, "Journal", "JOURNAL", 280, y, RIGHT_W - 304, 54, function() opts.openWindow("Journal", w.id) end, true)
		journal.Caption.TextSize = 21
		return y + 54 + 10
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

	-- A pet: rarity and strong suit, what it does at this tier and the next, UPGRADE (copies +
	-- emeralds, like weapons) and EQUIP / UNEQUIP.
	local function drawPetDetail(panel, id)
		local pet = Pets.ById[id]
		local rec = petRec(id)
		local equipped = profile.pet == id
		header(
			panel,
			nil,
			rec and rec.tier,
			string.upper(pet.name),
			'<font color="'
				.. T.hex(Chests.RarityColor[pet.rarity])
				.. '">'
				.. string.upper(pet.rarity)
				.. "</font>  ·  PET  ·  "
				.. string.upper(pet.suit),
			rec and T.Tier[rec.tier] or C.white
		)
		petView(panel.IconWell, id, 6, 6, 120)
		local tier = rec and rec.tier or 1
		local text = '<font color="#91EF14">TIER ' .. T.Roman[tier] .. "</font>  " .. Pets.effectText(id, tier)
		if tier < 4 then
			text ..= '\n\n<font color="' .. T.hex(C.muted) .. '">NEXT · TIER ' .. T.Roman[tier + 1] .. "</font>  " .. Pets.effectText(id, tier + 1)
		end
		local d = T.text(panel, "Effect", text, 24, 166, RIGHT_W - 48, 200, 19, C.cream)
		d.TextYAlignment = Enum.TextYAlignment.Top
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
		else
			centred(T.text(panel, "Need", "Hatch it from a Pet Egg (egg merchant)", 24, 420, RIGHT_W - 48, 24, 18, C.muted))
		end
		local eq = T.button(
			panel,
			"Equip",
			equipped and "UNEQUIP" or (rec and "EQUIP" or "NOT OWNED"),
			24,
			530,
			RIGHT_W - 48,
			62,
			function()
				equipPet((not equipped) and id or nil)
			end,
			equipped or not rec
		)
		eq.Caption.TextSize = 26
		eq.Interactable = rec ~= nil
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
		local d = T.text(panel, "Description", c.description, 24, 166, RIGHT_W - 48, 48, 18, C.muted)
		d.TextYAlignment = Enum.TextYAlignment.Top
		-- Always on (buffs | drawbacks), then the specialty and ability rows (2026-10-09, shared with
		-- the class screen: RunSetupUI.perkRows). Phones (canvas scale under .62) get bigger text and
		-- the panel scrolls: text can't draw smaller than 9-12 screen px, so at scale .5 it needs ~24
		-- design px.
		local big = L.s ~= nil and L.s < 0.62
		local sz = big and { sect = 26, stat = 24, perk = 22 } or { sect = 20, stat = 19, perk = 18 }
		local y = 220
		y += T.section(panel, "AlwaysOnTitle", "ALWAYS ON", 24, y, RIGHT_W - 48, sz.sect) + 6
		local good, bad = Stats.classLines(class)
		local _, h = T.statColumns(panel, "AlwaysOn", 24, y, RIGHT_W - 48, good, bad, { size = sz.stat, stack = big })
		y += h + 10
		y += T.section(panel, "PerksTitle", "SPECIALTY & ABILITY", 24, y, RIGHT_W - 48, sz.sect) + 6
		_, h = RunSetup.perkRows(panel, "Perks", 24, y, RIGHT_W - 48, class, { size = sz.perk, labelW = big and 170 or 140, stack = big })
		y += h + 10
		y += 12
		local go = T.button(panel, "ChangeClass", profile.classes[class] and "CHOOSE CLASS & STARTER" or "VIEW CLASS UNLOCK", 24, math.max(y, 640), RIGHT_W - 48, 70, function()
			if opts.chooseClass then opts.chooseClass(class) else opts.openWindow("ClassPicker", class) end
		end, true)
		go.Caption.TextSize = 25
		go.Interactable = player:GetAttribute("LobbyLockedIn") ~= true
		if panel:IsA("ScrollingFrame") then
			panel.CanvasSize = UDim2.fromOffset(0, math.max(panel.CanvasSize.Y.Offset, math.max(y, 640) + 70 + 16))
		end
	end

	local function drawDetail()
		local right = group("Right", L.w - MARGIN - RIGHT_W, L.rightY, RIGHT_W, L.rightH)
		local frame = T.panel(right, "Panel", 0, 0, RIGHT_W, L.rightH, "panel")
		local isWeapon = state.kind == "weapon" and Weapons.ById[state.item or ""] ~= nil
		local panel = not isWeapon and body(frame, RIGHT_H - 24) or nil
		if isWeapon then
			local w = Weapons.ById[state.item]
			local rec = profile.weapons[w.id]
			if rec and rec.tier > 1 then
				T.setTier(frame, rec.tier)
			end
			-- Drawn into a holder first; taller than the panel (phones, long rows) moves it into a scroll.
			local content = T.frame(frame, "Content", 0, 0, RIGHT_W, 0)
			local h = drawWeaponDetail(content, w)
			content.Size = UDim2.fromOffset(RIGHT_W, h)
			if h > L.rightH then
				local sc = T.scroll(frame, "Body", 0, 8, 0, 0)
				sc.Size = UDim2.new(1, -8, 1, -16)
				sc.CanvasSize = UDim2.fromOffset(0, h)
				content.Parent = sc
			end
		elseif state.kind == "class" then
			drawClassDetail(panel, state.item or loadout())
		elseif state.kind == "pet" and Pets.ById[state.item or ""] then
			local rec = petRec(state.item)
			if rec and rec.tier > 1 then
				T.setTier(frame, rec.tier)
			end
			drawPetDetail(panel, state.item)
		elseif state.kind == "pet" then
			drawComingDetail(
				panel,
				"chest",
				"PET",
				"EMPTY SLOT  ·  HATCH PETS FROM EGGS",
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
		slideIn(right, 40)
	end

	-- Upgrade view ----------------------------------------------------------------------
	local function drawUpgrade()
		local w = Weapons.ById[state.item]
		local rec = profile.weapons[w.id]
		local tier = rec and rec.tier or 0
		local need = rec and opts.need(rec)
		-- Full width here: the loadout slots are hidden in this view. Shorter screens scroll the tiers.
		local LEFT_W = leftWidth(3)
		local left = group("Left", MARGIN, L.leftY, LEFT_W, L.leftH)
		local panel = T.panel(left, "Panel", 0, 0, LEFT_W, L.leftH, "panel")
		plate(left, "UPGRADES", 20, -34)
		local rowH = 190
		local tiers = body(panel, 50 + 4 * (rowH + 14) + 12)
		for t = 1, 4 do
			local y = 50 + (t - 1) * (rowH + 14)
			local done = rec and t < tier
			local now = rec and t == tier
			local nextUp = rec and t == tier + 1
			local card = T.panel(tiers, "Tier" .. t, 22, y, LEFT_W - 44, rowH, (now or nextUp) and "panel" or "inset")
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
			-- Attach the current-tier check to the measured title instead of a fixed card X.
			-- This keeps the longer III/IV titles and the mark apart at every window scale.
			if now then
				local row = T.frame(card, "TierHeading", 24, 14, LEFT_W - 250, 44)
				T.make("UIListLayout", row, { FillDirection = Enum.FillDirection.Horizontal, VerticalAlignment = Enum.VerticalAlignment.Center, Padding = UDim.new(0, 12), SortOrder = Enum.SortOrder.LayoutOrder })
				title.Parent = row
				title.Position = UDim2.new()
				title.TextScaled = false
				title.TextWrapped = false
				title.AutomaticSize = Enum.AutomaticSize.X
				title.Size = UDim2.fromOffset(0, 44)
				title.LayoutOrder = 1
				local check = T.check(row, 0, 0, 26)
				check.LayoutOrder = 2
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
		slideIn(left, -40)

		local right = group("Right", L.w - MARGIN - RIGHT_W, L.upgradeY, RIGHT_W, L.upgradeH)
		local rpanel = T.panel(right, "Panel", 0, 0, RIGHT_W, L.upgradeH, "panel")
		if tier > 1 then
			T.setTier(rpanel, tier)
		end
		local rp = body(rpanel, UPGRADE_H)
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
		slideIn(right, 40)
		Stage.SetView("upgrade", w.id, T.Tier[math.max(tier, 1)])
	end

	-- Bottom: CLOSE / BACK ---------------------------------------------------------------
	local function drawBottom()
		local bottom = group("Bottom", (L.w - 360) / 2, L.h - BOTTOM_H, 360, 86)
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
		local drag = T.make("TextButton", canvas, {
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
		if not (canvas and L) then
			return
		end
		local showingInfo = itemCard and itemCard.Id()
		closeInfo()
		-- Every redraw rebuilds the buttons; a controller keeps its place (or lands on the first one).
		local selected = T.selectionPath(canvas)
		for _, c in canvas:GetChildren() do
			if not c:IsA("UIScale") then
				c:Destroy()
			end
		end
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
		if showingInfo then showInfo(showingInfo) end
		animate = false
		if justOpened then
			justOpened = false
			T.gamepadSelect(canvas:FindFirstChild("Left") or canvas)
		else
			T.restoreSelection(canvas, selected)
		end
	end

	local profileConn
	local pendingDraw = false
	-- tab: Classes | Weapons | Armor | Pets, or {tab, kind, id} when returning from an attack preview.
	function self.Open(tab)
		if root then
			self.Close()
		end
		local focus = type(tab) == "table" and tab or nil
		state.tab = (focus and (focus.tab or "Weapons") or tab) or state.tab or "Weapons"
		state.mode, state.kind, state.item = "main", focus and focus.kind, focus and focus.id
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
					Position = UDim2.fromOffset(-100, -100),
					Size = UDim2.new(1, 200, 1, 200),
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
		T.hideTouchControls("Armory", true)
		-- One upgrade changes several of these at once (weapons, gems): redraw once, after the last.
		-- draw() itself returns if the screen was closed meanwhile.
		profileConn = player.AttributeChanged:Connect(function(name)
			if REDRAW_ON[name] and not pendingDraw then
				pendingDraw = true
				task.defer(function()
					pendingDraw = false
					draw()
				end)
			end
		end)
		-- Draws now, and again whenever the screen changes size (window resize, phone rotation).
		canvas, L = nil, nil
		justOpened = true
		T.canvas(root, function(c, cv)
			canvas = cv
			L = plan(c)
			draw()
		end)
		return { Root = root, Close = self.Close, HandlesBack = true }
	end

	function self.Close()
		if not root then
			return
		end
		closeInfo()
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
		T.hideTouchControls("Armory", false)
		if opts.onVisible then
			opts.onVisible(true)
		end
	end

	Input.InputBegan:Connect(function(input, processed)
		if not root or Input:GetFocusedTextBox() or game:GetService("GuiService").MenuIsOpen then return end
		local key = input.KeyCode
		if processed and key ~= Enum.KeyCode.ButtonB then return end
		if key == Enum.KeyCode.Escape or key == Enum.KeyCode.ButtonB then
			if itemCard then closeInfo()
			elseif state.mode == "upgrade" then state.mode = "main"; draw()
			else self.Close() end
		elseif itemCard and (key == Enum.KeyCode.Left or key == Enum.KeyCode.ButtonL1) then itemCard.Step(-1)
		elseif itemCard and (key == Enum.KeyCode.Right or key == Enum.KeyCode.ButtonR1) then itemCard.Step(1) end
	end)

	-- Leaving the lobby or respawning closes the Armory and returns the camera.
	player.CharacterRemoving:Connect(function()
		self.Close()
	end)
	return self
end

return A
