-- Compact collection and details. Reads server-published counters; never edits gameplay or profiles.
local RS = game:GetService("ReplicatedStorage")
local Http = game:GetService("HttpService")
local Input = game:GetService("UserInputService")
local TextService = game:GetService("TextService")
local T = require(RS:WaitForChild("UITheme"))
local P = require(RS:WaitForChild("WeaponJournalPresentation"))
local combat = RS:WaitForChild("RogueliteCombat")
local Journal = require(combat.WeaponJournal)
local Weapons = require(combat.WeaponCatalog)
local Icons = require(RS:WaitForChild("WeaponInventoryUI")).Icons
local C = T.Color
local J = {}
local active
local function decode(player)
	local ok, data = pcall(Http.JSONDecode, Http, player:GetAttribute("ProfileJournal") or "{}")
	return Journal.clean(ok and data or nil)
end
local function owned(player)
	local out = {}
	for row in (player:GetAttribute("ProfileWeapons") or ""):gmatch("[^,]+") do
		local id, tier = row:match("^([^:]+):(%d+)")
		if id then
			out[id] = math.clamp(tonumber(tier), 1, 4)
		end
	end
	return out
end
local function clear(parent)
	for _, child in parent:GetChildren() do
		child:Destroy()
	end
end
local function measure(value, size, width, font)
	return math.ceil(TextService:GetTextSize(value, size, font or T.Body, Vector2.new(math.max(1, width), 10000)).Y) + 4
end
-- Fixed-size type: no TextScaled fallback that silently turns important labels into 9px text.
local function text(parent, name, value, x, y, w, h, size, color, font)
	local label = T.make(
		"TextLabel",
		parent,
		{
			Name = name,
			Position = UDim2.fromOffset(x, y),
			Size = UDim2.fromOffset(w, h),
			BackgroundTransparency = 1,
			BorderSizePixel = 0,
			Text = value,
			Font = font or T.Body,
			TextSize = size,
			TextScaled = false,
			TextWrapped = true,
			RichText = false,
			TextColor3 = color or C.white,
			TextXAlignment = Enum.TextXAlignment.Left,
			TextYAlignment = Enum.TextYAlignment.Center,
			TextStrokeColor3 = C.shade,
			TextStrokeTransparency = 0.8,
		}
	)
	label:SetAttribute("JournalMinimumTextSize", size)
	return label
end
local function button(parent, name, value, x, y, w, h, callback, neutral, size)
	local b = T.button(parent, name, value, x, y, w, h, callback, neutral)
	local caption = b.Caption
	for _, c in caption:GetChildren() do
		if c:IsA("UITextSizeConstraint") then
			c:Destroy()
		end
	end
	caption.Position = UDim2.fromOffset(6, 4)
	caption.Size = UDim2.new(1, -12, 1, -8)
	caption.TextScaled = false
	caption.TextWrapped = false
	caption.TextSize = size or 18
	caption:SetAttribute("JournalMinimumTextSize", size or 18)
	return b
end
local function icon(kind, entry)
	return kind == "Weapon" and Icons[entry.id] or entry.icon
end
local function entryFor(kind, id)
	return kind == "Weapon" and Weapons.ById[id] or kind == "Item" and Journal.ItemById[id]
end
local function metric(parent, name, label, value, x, y, w, color)
	local card = T.panel(parent, name, x, y, w, 86, "inset")
	card:SetAttribute("JournalMetric", true)
	text(card, "Label", label, 14, 10, w - 28, 22, 16, C.muted)
	local size = 28
	while size > 20 and TextService:GetTextSize(value, size, T.Body, Vector2.new(10000, 100)).X > w - 28 do
		size -= 1
	end
	local v = text(card, "Value", value, 14, 38, w - 28, 34, size, color or C.lime)
	v.TextWrapped = false
	return card
end
function J.close()
	if active then
		active.Close()
	end
end
function J.open(player, kind, id)
	J.close()
	local mode = kind == "Item" and "Item" or "Weapon"
	local selected = id and entryFor(mode, id) and id or nil
	local data, ownership = decode(player), owned(player)
	local query, tier = "", selected and ownership[selected] or 1
	local history = {}
	local collectionScroll = { Weapon = 0, Item = 0 }
	local screen = T.make(
		"ScreenGui",
		player:WaitForChild("PlayerGui"),
		{
			Name = "WeaponJournal",
			ResetOnSpawn = false,
			DisplayOrder = 90,
			ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
			ScreenInsets = Enum.ScreenInsets.CoreUISafeInsets,
			SafeAreaCompatibility = Enum.SafeAreaCompatibility.None,
			ClipToDeviceSafeArea = true,
		}
	)
	local root = T.make(
		"TextButton",
		screen,
		{
			Name = "JournalRoot",
			Size = UDim2.fromScale(1, 1),
			Text = "",
			AutoButtonColor = false,
			BackgroundColor3 = C.shade,
			BackgroundTransparency = 0.15,
			BorderSizePixel = 0,
			Modal = true,
			Active = true,
			Selectable = false,
		}
	)
	local self = { Screen = screen, Root = root, HandlesBack = true }
	local connections = {}
	local closed = false
	local suppressSearch = false
	local panel, body, footer, search, tabs, collectionButton, layout
	local draw, rebuild
	function self.Close()
		if closed then
			return
		end
		closed = true
		for _, c in connections do
			c:Disconnect()
		end
		T.hideTouchControls("WeaponJournal", false)
		screen:Destroy()
		if active == self then
			active = nil
		end
	end
	active = self
	T.hideTouchControls("WeaponJournal", true)
	local function back()
		if #history > 0 then
			local prev = table.remove(history)
			mode, selected, tier, query = prev.mode, prev.id, prev.tier, prev.query
		elseif selected then
			selected = nil
		else
			self.Close()
			return
		end
		draw()
	end
	self.Back = back
	local function selectEntry(nextKind, nextId, remember)
		if not entryFor(nextKind, nextId) then
			return
		end
		if remember and selected then
			table.insert(history, { mode = mode, id = selected, tier = tier, query = query })
		end
		if nextKind ~= mode then
			query = ""
		end
		mode, selected = nextKind, nextId
		tier = mode == "Weapon" and ownership[nextId] or 1
		tier = tier or 1
		draw()
	end
	self.Select = function(nextKind, nextId)
		history = {}
		selectEntry(nextKind, nextId, false)
	end
	self.SetTier = function(value)
		tier = math.clamp(math.floor(value), 1, 4)
		draw(true)
	end
	self.ShowCollection = function(nextKind)
		if nextKind and nextKind ~= mode then
			mode = nextKind == "Item" and "Item" or "Weapon"
			query = ""
		end
		selected = nil
		history = {}
		draw()
	end
	local function drawCollection()
		local entries = P.filter(mode, query)
		local scroll = T.scroll(body, "CollectionList", 0, 0, layout.bodyW, layout.bodyH)
		scroll.ClipsDescendants = true
		scroll.VerticalScrollBarInset = Enum.ScrollBarInset.None
		scroll.ScrollBarThickness = 5
		local w, h, gap = layout.cardW, layout.cardH, layout.gap
		local rows = math.ceil(#entries / layout.columns)
		local height = math.max(0, rows * (h + gap) - gap)
		local grid = T.frame(scroll, "CollectionGrid", layout.gridX, 6, layout.gridW, height)
		for i, entry in entries do
			local col, row = (i - 1) % layout.columns, math.floor((i - 1) / layout.columns)
			local tile = button(grid, "Entry_" .. entry.id, "", col * (w + gap), row * (h + gap), w, h, function()
				selectEntry(mode, entry.id, false)
			end, true)
			local imageSize = layout.compact and 70 or 78
			T.icon(tile, "Icon", (w - imageSize) / 2, 12, imageSize, icon(mode, entry))
			local name =
				text(tile, "Name", entry.name, 10, h - 76, w - 20, 44, layout.compact and 16 or 18, C.white, T.Font)
			name.TextXAlignment = Enum.TextXAlignment.Center
			local caption, color
			if mode == "Weapon" then
				caption = ownership[entry.id] and "OWNED · " .. T.Roman[ownership[entry.id]] or "NOT OWNED"
				color = ownership[entry.id] and C.lime or C.dim
			else
				caption = P.number(data.items[entry.id]) .. " BOUGHT"
				color = C.muted
			end
			local status = text(tile, "Status", caption, 10, h - 30, w - 20, 18, 14, color)
			status.TextXAlignment = Enum.TextXAlignment.Center
			tile.SelectionGained:Connect(function()
				local top = tile.Position.Y.Offset + 6
				local bottom = top + h
				if top < scroll.CanvasPosition.Y + 6 then
					scroll.CanvasPosition = Vector2.new(0, math.max(0, top - 6))
				elseif bottom > scroll.CanvasPosition.Y + scroll.AbsoluteWindowSize.Y - 6 then
					scroll.CanvasPosition = Vector2.new(0, bottom - scroll.AbsoluteWindowSize.Y + 6)
				end
			end)
		end
		if #entries == 0 then
			height = 110
			grid.Size = UDim2.fromOffset(layout.gridW, height)
			text(grid, "NoResults", "NO MATCHES", 12, 12, layout.gridW - 24, 32, 24, C.white, T.Font)
			text(grid, "SearchHint", "Try another name, class or effect.", 12, 52, layout.gridW - 24, 48, 18, C.muted)
		end
		scroll.CanvasSize = UDim2.fromOffset(0, height + 16)
		scroll.CanvasPosition =
			Vector2.new(0, math.clamp(collectionScroll[mode], 0, math.max(0, height + 16 - layout.bodyH)))
		local listKind = mode
		scroll:GetPropertyChangedSignal("CanvasPosition"):Connect(function()
			collectionScroll[listKind] = scroll.CanvasPosition.Y
		end)
		local category = mode == "Item" and (#entries == 1 and "ITEM" or "ITEMS")
			or (#entries == 1 and "WEAPON" or "WEAPONS")
		text(footer, "CollectionCount", #entries .. " " .. category, 0, 0, layout.bodyW * 0.45, 22, 14, C.muted)
		local hint = text(
			footer,
			"ScrollHint",
			height + 16 > layout.bodyH and "SCROLL TO EXPLORE" or "",
			layout.bodyW * 0.5,
			0,
			layout.bodyW * 0.5,
			22,
			14,
			C.dim
		)
		hint.TextXAlignment = Enum.TextXAlignment.Right
	end
	local function drawDetails()
		local entry = entryFor(mode, selected)
		if not entry then
			selected = nil
			drawCollection()
			return
		end
		local scroll = T.scroll(body, "DetailContent", 0, 0, layout.bodyW, layout.bodyH)
		scroll.ClipsDescendants = true
		scroll.VerticalScrollBarInset = Enum.ScrollBarInset.None
		scroll.ScrollBarThickness = 5
		local content = T.frame(
			scroll,
			"DetailColumns",
			(layout.bodyW - layout.scrollGutter - layout.detailW) / 2,
			4,
			layout.detailW,
			0
		)
		local function column(name, x, width)
			local c = { frame = T.frame(content, name, x, 0, width, 0), w = width, y = 0 }
			function c.para(name, value, color, size)
				if not value or value == "" then
					return
				end
				size = size or 19
				local h = measure(value, size, c.w)
				local label = text(c.frame, name, value, 0, c.y, c.w, h, size, color)
				label.TextYAlignment = Enum.TextYAlignment.Top
				c.y += h + 10
				return label
			end
			function c.section(name, value, color)
				local h = measure(value, 21, c.w, T.Font)
				text(c.frame, name, value, 0, c.y, c.w, h, 21, color or C.cream, T.Font)
				c.y += h + 10
			end
			function c.note(name, title, value, color)
				local titleH = measure(title, 19, c.w - 32, T.Font)
				local valueH = measure(value, 19, c.w - 32)
				local h = 16 + titleH + 8 + valueH + 16
				local card = T.panel(c.frame, name, 0, c.y, c.w, h, "inset")
				text(card, "Title", title, 16, 12, c.w - 32, titleH, 19, color or C.lime, T.Font)
				local label = text(card, "Explanation", value, 16, 16 + titleH + 8, c.w - 32, valueH, 19, C.white)
				label.TextYAlignment = Enum.TextYAlignment.Top
				c.y += h + 14
				return card
			end
			return c
		end
		local summary = column("Summary", 0, layout.summaryW)
		local article = column("Article", layout.split and layout.summaryW + 20 or 0, layout.articleW)
		local function hero()
			local w = summary.w
			local vertical = layout.split
			local imageSize = vertical and 104 or 72
			local nameX = vertical and 16 or imageSize + 24
			local nameW = vertical and w - 32 or w - nameX - 12
			local nameH = measure(entry.name, 24, nameW, T.Font)
			-- Starter class and weapon types (2026-10-09): "CHEF STARTER · BLADE · CULINARY".
			local types = mode == "Weapon" and #(entry.types or {}) > 0 and ("  ·  " .. string.upper(table.concat(entry.types, " · "))) or ""
			local class = mode == "Weapon" and ((entry.godly and "GODLY · ANY CLASS" or (string.upper(entry.class or "") .. " STARTER")) .. types)
				or (entry.kind == "Turret" and "STRUCTURE" or "PASSIVE ITEM") .. " · MAX " .. entry.cap
			local classH = measure(class, 16, nameW)
			local nameY = vertical and imageSize + 24 or 12
			local h = math.max(imageSize + 24, nameY + nameH + 8 + classH + 16)
			local card = T.panel(summary.frame, "Hero", 0, summary.y, w, h, "inset")
			T.icon(card, "Icon", vertical and (w - imageSize) / 2 or 12, 12, imageSize, icon(mode, entry))
			text(card, "Name", entry.name, nameX, nameY, nameW, nameH, 24, C.white, T.Font)
			text(card, "Classification", class, nameX, nameY + nameH + 8, nameW, classH, 16, C.cream)
			summary.y += h + 14
		end
		if #history > 0 then
			button(summary.frame, "ReturnToItem", "BACK TO ITEM", 0, 0, summary.w, 44, back, true, 17)
			summary.y = 56
		end
		hero()
		if mode == "Weapon" then
			local owner = ownership[entry.id]
			summary.para(
				"Ownership",
				owner and "OWNED · TIER " .. T.Roman[owner] or "NOT OWNED · PREVIEW AVAILABLE",
				owner and C.lime or C.muted,
				16
			)
			summary.para("TierPrompt", "PREVIEW TIER", C.cream, 16)
			local actionW = math.min(summary.w, 320)
			local tabW = (actionW - 18) / 4
			for t = 1, 4 do
				button(summary.frame, "Tier_" .. t, T.Roman[t], (t - 1) * (tabW + 6), summary.y, tabW, 44, function()
					tier = t
					draw(true)
				end, t ~= tier, 19)
			end
			summary.y += 56
			local watch = button(summary.frame, "Watch", "WATCH ATTACKS", 0, summary.y, actionW, 44, function()
				local module = RS:FindFirstChild("WeaponShowcaseUI")
				if not module then
					T.toast(screen, "Attack preview is loading", C.muted)
					return
				end
				local wid, previewTier = entry.id, tier
				self.Close()
				require(module).open(player, wid, previewTier)
			end, false, 18)
			watch:SetAttribute("PreviewTier", tier)
			summary.y += 58
			local stats = P.weaponStats(entry, tier)
			local cells = P.cards(article.w, #stats, 140, 190)
			for i, value in stats do
				metric(
					article.frame,
					"BaseStat" .. i,
					value.label,
					value.value,
					((i - 1) % cells.columns) * (cells.w + 12),
					math.floor((i - 1) / cells.columns) * 98,
					cells.w,
					C.white
				)
			end
			article.y = cells.rows * 98
			article.para("BaseNote", "Base values before class, gear and run upgrades.", C.dim, 15)
			article.section("AttackTitle", "HOW IT ATTACKS")
			article.para("Description", Weapons.describe(entry))
			local special = Weapons.godlyText(entry.id, tier)
			if special then
				article.note("Signature", "SIGNATURE · TIER " .. T.Roman[tier], special, C.cyan)
			end
			local legendary = Weapons.legendaryText(entry.id)
			if legendary then
				article.note(
					"TierFour",
					tier == 4 and "TIER IV MOVE · ACTIVE" or "UNLOCKS AT TIER IV",
					legendary,
					tier == 4 and C.lime or C.gold
				)
			end
			local upgrade = Weapons.godlyUpgradeText(entry.id)
			if upgrade then
				article.note("GodlyUpgrade", "TIER IV UPGRADE", upgrade, C.gold)
			end
			article.section("RecordsTitle", "LIFETIME RECORDS")
			local record = data.weapons[entry.id] or {}
			local records = {
				{ name = "Kills", label = "MOBS DEFEATED", value = P.number(record.kills) },
				{ name = "Damage", label = "DAMAGE DEALT", value = P.number(record.damage, true) },
			}
			local recordCells = P.cards(article.w, 2, 220, 260)
			for i, r in records do
				metric(
					article.frame,
					r.name,
					r.label,
					r.value,
					((i - 1) % recordCells.columns) * (recordCells.w + 12),
					article.y + math.floor((i - 1) / recordCells.columns) * 98,
					recordCells.w
				)
			end
			article.y += recordCells.rows * 98
			article.para(
				"CreditNote",
				"Includes this weapon's credited status effects and special attacks.",
				C.muted,
				15
			)
		else
			summary.para("Description", entry.description, C.white, 18)
			summary.section("EffectsTitle", "EFFECT PER COPY")
			local effectW = math.min(summary.w, 360)
			for _, effect in P.effects(entry) do
				local card = T.panel(summary.frame, "Effect_" .. effect.id, 0, summary.y, effectW, 68, "inset")
				text(card, "Label", effect.label, 14, 10, effectW * 0.6 - 20, 48, 18, C.white)
				local amount = text(
					card,
					"Amount",
					effect.amount,
					effectW * 0.6,
					10,
					effectW * 0.4 - 14,
					48,
					20,
					effect.value < 0 and C.negative or C.lime
				)
				amount.TextXAlignment = Enum.TextXAlignment.Right
				summary.y += 78
			end
			if #P.effects(entry) == 0 then
				summary.para("StructureEffect", "Creates its own structure.", C.muted, 17)
			end
			metric(
				summary.frame,
				"Purchases",
				"SHOP PURCHASES",
				P.number(data.items[entry.id]),
				0,
				summary.y,
				math.min(summary.w, 320)
			)
			summary.y += 100
			summary.para("PurchaseNote", "Free starters and admin grants do not count.", C.dim, 15)
			article.section("CompatibilityTitle", "WORKS WITH")
			local support = P.compatibility(entry)
			-- Restricted interactions lead, so the named supported weapons never hide beneath generic bonuses.
			for _, specific in support.specific do
				article.para("Compatibility_" .. specific.effect.id, specific.reason, C.cyan)
				for _, group in specific.groups do
					article.para("Group_" .. specific.effect.id .. "_" .. group.name, group.name:upper(), C.cream, 17)
					local cells = P.cards(article.w, #group.ids, 220, 300)
					for i, wid in group.ids do
						local x = ((i - 1) % cells.columns) * (cells.w + 12)
						local y = article.y + math.floor((i - 1) / cells.columns) * 64
						local b = button(
							article.frame,
							"Supported_" .. specific.effect.id .. "_" .. wid,
							"",
							x,
							y,
							cells.w,
							54,
							function()
								selectEntry("Weapon", wid, true)
							end,
							true
						)
						T.icon(b, "Icon", 10, 11, 32, Icons[wid])
						text(b, "Name", Weapons.ById[wid].name, 52, 6, cells.w - 66, 42, 17, C.white)
					end
					article.y += cells.rows * 64 + 8
				end
				if specific.conditional then
					article.para("Condition_" .. specific.effect.id, specific.conditional, C.gold, 18)
				end
				article.para(
					"GroupNote_" .. specific.effect.id,
					"Grouped by primary class. Your chosen class does not restrict these effects.",
					C.dim,
					15
				)
			end
			if #support.player > 0 then
				local penalty = false
				for _, effect in support.player do
					if effect.value < 0 then
						penalty = true
					end
				end
				article.note(
					"PlayerBenefit",
					penalty and "PLAYER EFFECT · ALL BUILDS" or "PLAYER BENEFIT · ALL BUILDS",
					penalty and "Changes your player stats regardless of equipped weapons. No weapon requirement."
						or "Benefits your player regardless of equipped weapons. No weapon requirement."
				)
			end
			if #support.every > 0 then
				local labels = {}
				for _, effect in support.every do
					table.insert(labels, effect.label)
				end
				article.note(
					"EveryWeapon",
					"ALL " .. #Weapons.List .. " WEAPONS",
					table.concat(labels, " · ") .. " applies with any weapon, on any class."
				)
			end
			if support.structure then
				article.note(
					"StructureBenefit",
					"INDEPENDENT STRUCTURE",
					"Works alongside any weapon loadout. Creates its own turret rather than modifying weapon attacks."
				)
			end
		end
		article.para(
			"Since",
			"Records began "
				.. Journal.Since
				.. ". Earlier sessions, practice, previews and admin test runs are excluded.",
			C.dim,
			15
		)
		if game:GetService("RunService"):IsStudio() then
			article.para("StudioNote", "STUDIO SESSION · Records are not saved.", C.gold, 15)
		end
		summary.frame.Size = UDim2.fromOffset(summary.w, summary.y)
		article.frame.Size = UDim2.fromOffset(article.w, article.y)
		if not layout.split then
			article.frame.Position = UDim2.fromOffset(0, summary.y + 12)
		end
		local height = layout.split and math.max(summary.y, article.y) or summary.y + 12 + article.y
		content.Size = UDim2.fromOffset(layout.detailW, height)
		scroll.CanvasSize = UDim2.fromOffset(0, height + 16)
		text(footer, "RecordSince", "Records since " .. Journal.Since, 0, 0, layout.bodyW, 22, 14, C.muted)
	end
	draw = function(preserveScroll)
		if closed or not body then
			return
		end
		local selectedPath = T.selectionPath(root)
		local old = body:FindFirstChild("DetailContent")
		local position = preserveScroll and old and old.CanvasPosition
		clear(body)
		clear(footer)
		for kind, tab in tabs do
			tab:SetAttribute("Neutral", kind ~= mode)
		end
		collectionButton:SetAttribute("Neutral", selected ~= nil)
		if search.Text ~= query then
			suppressSearch = true
			search.Text = query
			suppressSearch = false
		end
		if selected then
			drawDetails()
		else
			drawCollection()
		end
		local detail = body:FindFirstChild("DetailContent")
		if detail and position then
			detail.CanvasPosition = position
		end
		T.restoreSelection(root, selectedPath)
	end
	rebuild = function()
		if closed then
			return
		end
		local size = root.AbsoluteSize
		if size.X < 2 or size.Y < 2 then
			return
		end
		layout = P.layout(size)
		if panel then
			panel:Destroy()
		end
		panel = T.panel(root, "JournalPanel", layout.x, layout.y, layout.w, layout.h, "panel")
		panel.Active = true
		if layout.titleW > 0 then
			text(panel, "Title", "JOURNAL", layout.pad, layout.pad, layout.titleW, 44, 26, C.white, T.Font)
		end
		tabs = {}
		for _, kind in { "Weapon", "Item" } do
			local n = layout.nav[kind]
			tabs[kind] = button(
				panel,
				kind .. "Tab",
				kind == "Weapon" and "WEAPONS" or "ITEMS",
				layout.pad + n.x,
				layout.pad + n.y,
				n.w,
				44,
				function()
					mode = kind
					selected = nil
					history = {}
					query = ""
					collectionScroll[kind] = 0
					draw()
				end,
				kind ~= mode,
				layout.single and 18 or 16
			)
		end
		local nav = layout.nav.Collection
		collectionButton = button(
			panel,
			"Collection",
			"COLLECTION",
			layout.pad + nav.x,
			layout.pad + nav.y,
			nav.w,
			44,
			function()
				self.ShowCollection()
			end,
			selected ~= nil,
			layout.single and 18 or 16
		)
		nav = layout.nav.Close
		button(panel, "Close", "X", layout.pad + nav.x, layout.pad + nav.y, nav.w, 44, self.Close, true, 22)
		nav = layout.nav.Search
		search = T.make(
			"TextBox",
			panel,
			{
				Name = "Search",
				Position = UDim2.fromOffset(layout.pad + nav.x, layout.pad + nav.y),
				Size = UDim2.fromOffset(nav.w, 44),
				Text = query,
				PlaceholderText = "Search collection",
				ClearTextOnFocus = false,
				BackgroundColor3 = C.well,
				BorderSizePixel = 0,
				TextColor3 = C.white,
				PlaceholderColor3 = C.muted,
				Font = T.Body,
				TextSize = 18,
				TextXAlignment = Enum.TextXAlignment.Left,
			}
		)
		T.make("UICorner", search, { CornerRadius = UDim.new(0, 7) })
		T.make("UIPadding", search, { PaddingLeft = UDim.new(0, 12), PaddingRight = UDim.new(0, 12) })
		search:GetPropertyChangedSignal("Text"):Connect(function()
			if suppressSearch then
				return
			end
			query = search.Text
			selected = nil
			history = {}
			collectionScroll[mode] = 0
			draw()
		end)
		body = T.frame(panel, "Body", layout.pad, layout.bodyY, layout.bodyW, layout.bodyH)
		footer = T.frame(panel, "Footer", layout.pad, layout.footerY, layout.bodyW, layout.footer)
		draw()
	end
	table.insert(connections, root:GetPropertyChangedSignal("AbsoluteSize"):Connect(rebuild))
	local queued = false
	local function changed()
		if queued then
			return
		end
		queued = true
		task.defer(function()
			queued = false
			if closed then
				return
			end
			data, ownership = decode(player), owned(player)
			draw(true)
		end)
	end
	for _, attr in { "ProfileJournal", "ProfileWeapons" } do
		table.insert(connections, player:GetAttributeChangedSignal(attr):Connect(changed))
	end
	table.insert(
		connections,
		Input.InputBegan:Connect(function(input, processed)
			if
				not processed
				and not Input:GetFocusedTextBox()
				and (input.KeyCode == Enum.KeyCode.Escape or input.KeyCode == Enum.KeyCode.ButtonB)
			then
				back()
			end
		end)
	)
	table.insert(
		connections,
		player:GetAttributeChangedSignal("LobbyPreviewActive"):Connect(function()
			if player:GetAttribute("LobbyPreviewActive") == false then
				self.Close()
			end
		end)
	)
	rebuild()
	T.gamepadSelect(root)
	return self
end
return J
