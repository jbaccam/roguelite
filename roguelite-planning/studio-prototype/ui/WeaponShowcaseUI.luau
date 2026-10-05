-- A weapon theatre browser: compact tiers/attacks, a paged collection, and the stage between.
-- All selection is cosmetic. No loadout, profile or gameplay remote is touched.
local RS = game:GetService("ReplicatedStorage")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Input = game:GetService("UserInputService")
local Actions = game:GetService("ContextActionService")
local Prompts = game:GetService("ProximityPromptService")
local GuiService = game:GetService("GuiService")
local T = require(RS:WaitForChild("UITheme"))
local Combat = RS:WaitForChild("RogueliteCombat")
local Catalog = require(Combat:WaitForChild("WeaponCatalog"))
local Data = require(RS:WaitForChild("WeaponShowcaseCatalog"))
local Icons = require(RS:WaitForChild("WeaponInventoryUI")).Icons
local Recipes = Data.build(Catalog)
local UI = {}
local session
local KEY = "WeaponShowcase"
local function box(x, y, w, h)
	return { x = x, y = y, w = w, h = h }
end

-- The rail/dock is laid out in the native core-safe canvas. The stage rectangle is
-- translated to full-render coordinates for the camera, including device cutout offsets.
function UI.layoutFor(width, height, attackCount, hasStyles, insets)
	local fullWidth, fullHeight = math.max(1, width), math.max(1, height)
	insets = insets or {}
	local left, top, right, bottom = insets.left or 0, insets.top or 0, insets.right or 0, insets.bottom or 0
	width = math.max(1, fullWidth - left - right)
	height = math.max(1, fullHeight - top - bottom)
	local side = width >= 900 or (width >= 500 and width > height * 1.25)
	local m = height < 380 and 4 or width < 900 and 8 or math.min(20, math.floor(width * 0.012))
	local gap = height < 380 and 8 or 14
	local panelW = side and math.min(348, math.max(244, math.floor(width * 0.43))) or width - 2 * m
	local panelH = side and math.min(548, height - 2 * m) or math.min(332, math.floor(height * 0.53))
	local rail = side and box(width - m - panelW, (height - panelH) / 2, panelW, panelH)
		or box(m, height - m - panelH, panelW, panelH)
	local stage = side and box(m, m, rail.x - gap - m, height - 2 * m) or box(m, m, width - 2 * m, rail.y - gap - m)
	local tiny = side and panelH < 380
	local compact = not side or panelH < 500
	local x, y = rail.x, rail.y
	local back, icon, title, subtitle, tierLabel, eyebrow, tiersY, tierH, tabsY, tabH, bodyY
	if not side then
		back = box(x + panelW - 74, y + 12, 62, 32)
		icon = box(x + 12, y + 12, 36, 36)
		title = box(x + 56, y + 10, panelW - 138, 40)
		tiersY, tierH, tabsY, tabH, bodyY = y + 58, 34, y + 100, 30, y + 140
	elseif tiny then
		back = box(x + panelW - 70, y + 10, 58, 28)
		eyebrow = box(x + 12, y + 13, panelW - 94, 20)
		icon = box(x + 12, y + 46, 30, 30)
		title = box(x + 50, y + 42, panelW - 62, 38)
		tiersY, tierH, tabsY, tabH, bodyY = y + 86, 30, y + 124, 28, y + 160
	else
		back = box(x + panelW - 84, y + 12, 70, 30)
		eyebrow = box(x + 16, y + 16, panelW - 108, 20)
		local is = compact and 44 or 48
		icon = box(x + 16, y + 52, is, is)
		title = box(x + is + 26, y + 49, panelW - is - 42, 54)
		subtitle = box(x + 18, y + 110, panelW - 36, 18)
		tierLabel = box(x + 18, y + 136, panelW - 36, 18)
		tiersY, tierH, tabsY, tabH, bodyY = y + 160, 36, y + 208, 32, y + 252
		if compact then
			subtitle.y = y + 104
			tierLabel.y = y + 128
			tiersY, tierH, tabsY, tabH, bodyY = y + 150, 34, y + 194, 30, y + 234
		end
	end
	local tierButtons = {}
	local tw = (panelW - 28 - 18) / 4
	for i = 1, 4 do
		tierButtons[i] = box(x + 14 + (i - 1) * (tw + 6), tiersY, tw, tierH)
	end
	local tabW = (panelW - 28 - 8) / 2
	local attackTab = box(x + 14, tabsY, tabW, tabH)
	local browseTab = box(attackTab.x + tabW + 8, tabsY, tabW, tabH)
	local body = box(x + 12, bodyY, panelW - 24, y + panelH - 12 - bodyY)
	local pad = tiny and 8 or compact and 10 or 12
	local playbackH = tiny and 32 or 36
	local playbackW = (body.w - 2 * pad - 8) / 2
	local replay = box(body.x + pad, body.y + body.h - pad - playbackH, playbackW, playbackH)
	local loop = box(replay.x + playbackW + 8, replay.y, playbackW, playbackH)
	local count = math.max(1, attackCount or 1) + (hasStyles and 1 or 0)
	local attacks = {}
	local rowH = compact and 36 or 40
	local rowGap = compact and 6 or 8
	local rowsNeed = pad * 2 + count * rowH + (count - 1) * rowGap + 12 + playbackH
	local dropdown = side and (tiny or rowsNeed > body.h) or (not side and count > 3)
	if dropdown then
		attacks[1] = box(body.x + pad, body.y + pad, body.w - 2 * pad, 34)
	elseif not side then
		local bw = (body.w - 2 * pad - (count - 1) * 6) / count
		for i = 1, count do
			attacks[i] = box(body.x + pad + (i - 1) * (bw + 6), body.y + pad, bw, rowH)
		end
	else
		for i = 1, count do
			attacks[i] = box(body.x + pad, body.y + pad + (i - 1) * (rowH + rowGap), body.w - 2 * pad, rowH)
		end
	end
	local last = attacks[#attacks]
	local descriptionY = last.y + last.h + 8
	local descriptionH = math.min(compact and 44 or 60, replay.y - 12 - descriptionY)
	local condition = descriptionH >= 18 and box(body.x + 20, descriptionY, body.w - 40, descriptionH) or nil
	local pagerH = tiny and 28 or 30
	local pagerY = body.y + body.h - pagerH
	local columns = not side and panelW >= 350 and 3 or 2
	local gridH = pagerY - 8 - body.y
	local rows = math.clamp(math.floor((gridH + 6) / 66), 1, 3)
	local cardH = math.min(90, (gridH - (rows - 1) * 6) / rows)
	local cardW = (body.w - (columns - 1) * 6) / columns
	local cards = {}
	for i = 1, rows * columns do
		local col = (i - 1) % columns
		local row = math.floor((i - 1) / columns)
		cards[i] = box(body.x + col * (cardW + 6), body.y + row * (cardH + 6), cardW, cardH)
	end
	local previous = box(body.x, pagerY, 36, pagerH)
	local nextButton = box(body.x + body.w - 36, pagerY, 36, pagerH)
	return {
		width = width,
		height = height,
		insets = { left = left, top = top, right = right, bottom = bottom },
		mode = side and "side" or "dock",
		compact = compact,
		tiny = tiny,
		margin = m,
		rail = rail,
		header = rail,
		back = back,
		icon = icon,
		title = title,
		subtitle = subtitle,
		eyebrow = eyebrow,
		tierLabel = tierLabel,
		tierButtons = tierButtons,
		attackTab = attackTab,
		browseTab = browseTab,
		controls = body,
		picker = body,
		attacks = attacks,
		attackDropdown = dropdown,
		controlPadding = { x = pad, y = pad, gap = 8 },
		replay = replay,
		loop = loop,
		condition = condition,
		cards = cards,
		pageSize = #cards,
		previous = previous,
		next = nextButton,
		pageLabel = box(body.x + 42, pagerY, body.w - 84, pagerH),
		stage = stage,
		viewportRect = {
			left = (left + stage.x) / fullWidth,
			top = (top + stage.y) / fullHeight,
			right = (left + stage.x + stage.w) / fullWidth,
			bottom = (top + stage.y + stage.h) / fullHeight,
			fullWidth = fullWidth,
			fullHeight = fullHeight,
		},
	}
end

local function screenBounds(viewport)
	-- Both rectangles share the CoreUISafeInsets origin, including on notched phones.
	local full = GuiService:GetInsetArea(Enum.ScreenInsets.None)
	local safe = GuiService:GetInsetArea(Enum.ScreenInsets.CoreUISafeInsets)
	if full.Width > 0 and full.Height > 0 and safe.Width > 0 and safe.Height > 0 then
		return {
			width = full.Width,
			height = full.Height,
			left = safe.Min.X - full.Min.X,
			top = safe.Min.Y - full.Min.Y,
			right = full.Max.X - safe.Max.X,
			bottom = full.Max.Y - safe.Max.Y,
		}
	end
	-- A newly mounted viewport may report zero for its first frame. The next render re-reads it.
	local topLeft, bottomRight = GuiService:GetGuiInset()
	return {
		width = viewport.X,
		height = viewport.Y,
		left = topLeft.X,
		top = topLeft.Y,
		right = bottomRight.X,
		bottom = bottomRight.Y,
	}
end
local function sameBounds(a, b)
	return a
		and b
		and a.width == b.width
		and a.height == b.height
		and a.left == b.left
		and a.top == b.top
		and a.right == b.right
		and a.bottom == b.bottom
end

local function connect(s, signal, fn)
	local c = signal:Connect(fn)
	table.insert(s.connections, c)
	return c
end
local function caption(button, text)
	local c = button and button:FindFirstChild("Caption")
	if c then
		c.Text = text
	end
end
local function styles(entry)
	local out = {}
	for _, v in entry.variants do
		if v.style then
			table.insert(out, v)
		end
	end
	return out
end
local function mainAttacks(entry)
	local out = {}
	for _, v in entry.variants do
		if not v.style then
			table.insert(out, v)
		end
	end
	return out
end
local function prettyStyle(name)
	return name == "FigureEight" and "FIGURE EIGHT" or string.upper(name or "AUTO")
end
local function closePopover(s)
	if s.popover then
		s.popover:Destroy()
		s.popover = nil
	end
end
function UI.swingMenuFor(layout, anchor, count)
	local rowH = layout.tiny and 34 or 38
	local maxRows = math.max(1, math.floor((layout.rail.h - 40) / rowH))
	local columns = math.ceil(count / maxRows)
	local h = math.ceil(count / columns) * rowH + 16
	local w = layout.rail.w - 24
	local y = math.clamp(anchor.y - h - 6, layout.rail.y + 12, layout.rail.y + layout.rail.h - h - 12)
	return box(layout.rail.x + 12, y, w, h), rowH, columns
end

function UI.isOpen()
	return session ~= nil
end
function UI.close(silent)
	local s = session
	if not s then
		return
	end
	session = nil
	for _, c in s.connections do
		c:Disconnect()
	end
	table.clear(s.connections)
	RunService:UnbindFromRenderStep(KEY)
	Actions:UnbindAction(KEY .. "Movement")
	if s.stage then
		s.stage:destroy()
	end
	if s.gui then
		s.gui:Destroy()
	end
	T.hideTouchControls(KEY, false)
	T.cameraRelease(KEY)
	if s.promptsEnabled ~= nil then
		Prompts.Enabled = s.promptsEnabled
	end
	for screen, enabled in s.hiddenScreens or {} do
		if screen.Parent then
			screen.Enabled = enabled
		end
	end
	if not silent and s.onClose then
		task.defer(s.onClose)
	end
end
function UI.debugState()
	if not session then
		return { open = false, connections = 0 }
	end
	local s = session
	local result = s.stage and s.stage:status() or {}
	result.open = true
	result.connections = #s.connections
	result.id = s.id
	result.tier = s.tier
	result.variant = s.variant
	result.loop = s.loop
	result.page = s.page
	result.view = s.view
	result.layoutMode = s.layout and s.layout.mode
	result.compact = s.layout and s.layout.compact
	result.pageSize = s.layout and s.layout.pageSize
	result.viewportRect = s.layout and s.layout.viewportRect
	result.safeBounds = s.bounds
	return result
end
local function fail(s, reason)
	s.failed = true
	s.loop = false
	if s.stage then
		s.stage.autoplay = false
	end
	if s.condition then
		s.condition.Text = "This preview could not load. Choose another weapon to retry."
		s.condition.TextColor3 = T.Color.negative
	end
	if s.loadingText then
		s.loadingText.Text = "Preview unavailable. Choose another weapon to retry."
		s.loadingText.TextColor3 = T.Color.negative
		s.loadingText.Visible = true
	end
	warn("WeaponShowcase: " .. tostring(reason))
end
local renderChrome, selectWeapon, renderPicker
local function button(s, name, text, b, fn, selected)
	local x = T.button(s.chrome, name, text, b.x, b.y, b.w, b.h, fn, not selected)
	x.Caption.TextSize = s.layout.compact and 14 or 17
	return x
end
local function panel(s, name, b, kind)
	return T.panel(s.chrome, name, b.x, b.y, b.w, b.h, kind)
end
local function text(s, name, value, b, size, color)
	local t = T.text(s.chrome, name, value, b.x, b.y, b.w, b.h, size, color)
	-- Supporting text must keep its authored reading size instead of silently shrinking.
	t.TextScaled = false
	t.RichText = false
	return t
end
local function setLoop(s, on)
	s.loop = on
	if s.stage then
		s.stage.autoplay = on
	end
	caption(s.loopButton, on and "LOOP ON" or "LOOP OFF")
	if s.loopButton then
		T.setPrimary(s.loopButton, on)
	end
end
local function replay(s)
	if session ~= s or not s.stage then
		return
	end
	closePopover(s)
	s.failed = false
	if s.loadingText then
		s.loadingText.Text = "Loading effectsâ€¦"
		s.loadingText.TextColor3 = T.Color.cream
		s.loadingText.Visible = true
	end
	local ok, err = pcall(function()
		s.stage:select(s.id, s.tier, s.variant)
		s.stage.autoplay = s.loop
		s.stage:setViewportRect(s.layout.viewportRect)
	end)
	if not ok then
		fail(s, err)
	end
end
local function stylePopover(s, anchor, allAttacks)
	if s.popover then
		closePopover(s)
		return
	end
	local list = {}
	if allAttacks then
		for _, v in mainAttacks(Recipes.ById[s.id]) do
			table.insert(list, {
				key = v.key,
				label = v.key == "Base" and "BASE ATTACK" or "SPECIAL · " .. v.label,
				minTier = v.minTier,
			})
		end
	else
		table.insert(list, { key = "Base", label = "AUTO SWINGS" })
	end
	for _, v in styles(Recipes.ById[s.id]) do
		table.insert(list, { key = v.key, label = (allAttacks and "SWING · " or "") .. prettyStyle(v.style) })
	end
	local shield = T.make("TextButton", s.chrome, {
		Name = "SwingMenu",
		Size = UDim2.fromScale(1, 1),
		BackgroundTransparency = 1,
		Text = "",
		AutoButtonColor = false,
		ZIndex = 30,
	})
	s.popover = shield
	shield.Activated:Connect(function()
		closePopover(s)
	end)
	local menu, rowH, columns = UI.swingMenuFor(s.layout, anchor, #list)
	local p = T.panel(shield, "SwingChoices", menu.x, menu.y, menu.w, menu.h, "panel")
	p.ZIndex = 31
	local cellW = (menu.w - 16 - (columns - 1) * 6) / columns
	for i, v in list do
		local column = (i - 1) % columns
		local row = math.floor((i - 1) / columns)
		local b = T.button(
			p,
			"Swing_" .. v.key,
			v.label,
			8 + column * (cellW + 6),
			8 + row * rowH,
			cellW,
			rowH - 4,
			function()
				selectWeapon(s, s.id, math.max(s.tier, v.minTier or 1), v.key)
			end,
			s.variant ~= v.key
		)
		b.ZIndex = 32
		for _, child in b:GetDescendants() do
			if child:IsA("GuiObject") then
				child.ZIndex = 33
			end
		end
		b.Caption.TextSize = 16
	end
end
function renderPicker(s)
	if s.pickerTiles then
		s.pickerTiles:Destroy()
	end
	local L = s.layout
	local totalPages = math.ceil(#Catalog.List / L.pageSize)
	s.page = math.clamp(s.page or 1, 1, totalPages)
	local group =
		T.make("Frame", s.chrome, { Name = "WeaponTiles", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1) })
	s.pickerTiles = group
	s.weaponButtons = {}
	local first = (s.page - 1) * L.pageSize + 1
	for i, b in L.cards do
		local w = Catalog.List[first + i - 1]
		if w then
			local selected = w.id == s.id
			local tile = T.button(group, "Weapon_" .. w.id, "", b.x, b.y, b.w, b.h, function()
				s.view = "attacks"
				selectWeapon(s, w.id, s.tier, "Base")
			end, not selected)
			tile:SetAttribute("WeaponId", w.id)
			tile:SetAttribute("Selected", selected)
			s.weaponButtons[w.id] = tile
			tile.Caption.Visible = false
			local icon = math.min(42, b.h - 44)
			T.icon(tile, "Icon", (b.w - icon) / 2, 4, icon, Icons[w.id])
			local name = T.label(
				tile,
				"Name",
				w.name,
				6,
				icon + 6,
				b.w - 12,
				b.h - icon - 12,
				14,
				selected and T.Color.white or T.Color.muted
			)

			name.TextStrokeTransparency = 0.18
			name.TextScaled = false
			if selected then
				local mark = T.make("Frame", tile, {
					Name = "Selected",
					Position = UDim2.new(0.18, 0, 1, -4),
					Size = UDim2.new(0.64, 0, 0, 3),
					BackgroundColor3 = T.Color.lime,
					BorderSizePixel = 0,
				})
				mark.ZIndex = 3
			end
		end
	end
	s.pageText.Text = string.format("PAGE %d OF %d", s.page, totalPages)
	s.previous.Interactable = s.page > 1
	s.next.Interactable = s.page < totalPages
end
function renderChrome(s, viewport, keepPage, bounds)
	closePopover(s)
	local attacks = mainAttacks(Recipes.ById[s.id])
	local hasStyles = #styles(Recipes.ById[s.id]) > 1
	bounds = bounds or screenBounds(viewport)
	local L = UI.layoutFor(bounds.width, bounds.height, #attacks, hasStyles, bounds)
	s.layout = L
	s.viewport = viewport
	s.bounds = bounds
	if s.chrome then
		s.chrome:Destroy()
	end
	s.chrome =
		T.make("Frame", s.blocker, { Name = "Browser", Size = UDim2.fromScale(1, 1), BackgroundTransparency = 1 })
	s.loopButton = nil
	s.pickerTiles = nil
	s.condition = nil
	s.variantButtons = {}
	if not keepPage then
		local at = table.find(Catalog.List, Catalog.ById[s.id]) or 1
		s.page = math.ceil(at / L.pageSize)
	end
	local w = Catalog.ById[s.id]
	local variant = Data.variant(Recipes.ById[s.id], s.variant, s.tier)
	panel(s, "ControlPanel", L.rail, "panel")
	button(s, "Close", "BACK", L.back, function()
		UI.close()
	end, false).Caption.TextSize = L.tiny and 14 or 15
	if L.eyebrow then
		text(s, "Eyebrow", "WEAPON PREVIEW", L.eyebrow, 14, T.Color.muted)
	end
	T.icon(s.chrome, "SelectedWeaponIcon", L.icon.x, L.icon.y, L.icon.w, Icons[s.id])
	local title = text(s, "WeaponTitle", w.name, L.title, L.compact and 21 or 25, T.Color.white)
	title.Font = T.Font
	title.TextWrapped = true
	-- Only the selected title may fit its two-line slot, with an explicit readable floor.
	title.TextScaled = true
	title:FindFirstChildOfClass("UITextSizeConstraint").MinTextSize = 14
	if L.subtitle then
		local sub = string.upper(w.rarity) .. "  ·  " .. (w.godly and "EVERY CLASS" or Catalog.classNames(w, " · "))
		local classes = text(s, "Classes", sub, L.subtitle, 14, T.Color.cream)
		classes.TextWrapped = false
		classes.TextTruncate = Enum.TextTruncate.AtEnd
	end
	if L.tierLabel then
		text(s, "TierLabel", "WEAPON TIER", L.tierLabel, 14, T.Color.muted)
	end
	s.tierButtons = {}
	for i, b in L.tierButtons do
		local t = button(s, "Tier" .. i, T.Roman[i], b, function()
			selectWeapon(s, s.id, i, s.variant)
		end, i == s.tier)
		t.Caption.TextSize = L.tiny and 19 or 22
		t:SetAttribute("Selected", i == s.tier)
		t:SetAttribute("WeaponTier", i)
		s.tierButtons[i] = t
		T.make("Frame", t, {
			Name = "TierAccent",
			Position = UDim2.new(0.22, 0, 1, -4),
			Size = UDim2.new(0.56, 0, 0, 2),
			BackgroundColor3 = T.Tier[i],
			BorderSizePixel = 0,
			ZIndex = 3,
		})
	end
	local function tab(view)
		s.view = view
		renderChrome(s, s.viewport, true)
	end
	button(s, "AttacksTab", "ATTACKS", L.attackTab, function()
		tab("attacks")
	end, s.view == "attacks").Caption.TextSize =
		14
	button(s, "WeaponsTab", "WEAPONS · 42", L.browseTab, function()
		tab("weapons")
	end, s.view == "weapons").Caption.TextSize =
		14
	if s.view == "weapons" then
		s.pageText = text(s, "Page", "", L.pageLabel, 12, T.Color.cream)
		s.pageText.TextXAlignment = Enum.TextXAlignment.Center
		s.previous = button(s, "PreviousPage", "‹", L.previous, function()
			s.page -= 1
			closePopover(s)
			renderPicker(s)
		end, false)
		s.next = button(s, "NextPage", "›", L.next, function()
			s.page += 1
			closePopover(s)
			renderPicker(s)
		end, false)
		s.previous.Caption.TextSize = 26
		s.next.Caption.TextSize = 26
		renderPicker(s)
	else
		panel(s, "AttackControls", L.controls, "inset")
		if L.attackDropdown then
			local label = variant.key == "Base" and "BASE ATTACK"
				or variant.style and "SWING · " .. prettyStyle(variant.style)
				or "SPECIAL · " .. variant.label
			local b = button(s, "AttackPicker", label .. "  ▾", L.attacks[1], function()
				stylePopover(s, L.attacks[1], true)
			end, true)
			b:SetAttribute("Variant", variant.key)
			b:SetAttribute("Selected", true)
		else
			for i, v in attacks do
				local requires = v.minTier and s.tier < v.minTier
				local label = v.key == "Base" and "BASE ATTACK"
					or (requires and "TIER IV SPECIAL\n" or "SPECIAL\n") .. v.label
				local selected = v.key == "Base" and (variant.key == "Base" or variant.style ~= nil)
					or variant.key == v.key
				local b = button(s, "Variant_" .. v.key, label, L.attacks[i], function()
					selectWeapon(s, s.id, math.max(s.tier, v.minTier or 1), v.key)
				end, selected)
				b.Caption.TextSize = L.mode == "dock" and 14 or 15
				b:SetAttribute("Variant", v.key)
				b:SetAttribute("Selected", selected)
				b:SetAttribute("MinimumTier", v.minTier or 1)
				if requires then
					b.Caption.TextColor3 = T.Color.gold
				end
				s.variantButtons[v.key] = b
			end
			if hasStyles then
				local b = L.attacks[#attacks + 1]
				button(
					s,
					"SwingPicker",
					"SWING · " .. (variant.style and prettyStyle(variant.style) or "AUTO") .. "  ▾",
					b,
					function()
						stylePopover(s, b)
					end,
					false
				).Caption.TextSize = L.mode
							== "dock"
						and 14
					or 15
			end
		end
		local replayButton = button(s, "Replay", "REPLAY", L.replay, function()
			replay(s)
		end, false)
		replayButton.Caption.TextSize = L.compact and 14 or 16
		replayButton.Caption.TextScaled = false
		s.loopButton = button(s, "Loop", s.loop and "LOOP ON" or "LOOP OFF", L.loop, function()
			setLoop(s, not s.loop)
		end, s.loop)
		s.loopButton.Caption.TextSize = L.compact and 14 or 16
		s.loopButton.Caption.TextScaled = false
		if L.condition then
			local explanation = variant.style
					and "Preview the " .. string.lower(prettyStyle(variant.style)) .. " swing."
				or variant.condition:gsub(" Tier changes use the live weapon stats%.", "")
			s.condition = text(s, "AttackDescription", explanation, L.condition, L.compact and 14 or 16, T.Color.cream)
			s.condition.TextWrapped = true
			s.condition.TextTruncate = Enum.TextTruncate.AtEnd
			s.condition.TextYAlignment = Enum.TextYAlignment.Top
		end
	end
	s.loadingText = text(
		s,
		"LoadingEffects",
		"Loading effects…",
		box(L.stage.x + 8, L.stage.y + 6, math.min(250, L.stage.w - 16), 22),
		14,
		T.Color.cream
	)
	s.loadingText.TextWrapped = false
	s.loadingText.Visible = not s.stage or s.stage:status().loading == true
	if s.stage then
		s.stage:setViewportRect(L.viewportRect)
	end
end

function selectWeapon(s, id, tier, key)
	if session ~= s or not Catalog.ById[id] then
		return
	end
	local changed = id ~= s.id
	s.id = id
	s.tier = math.clamp(math.floor(tonumber(tier) or 1), 1, 4)
	s.variant = Data.variant(Recipes.ById[id], key, s.tier).key
	local camera = workspace.CurrentCamera
	local viewport = camera and camera.ViewportSize or Vector2.new(1280, 720)
	renderChrome(s, viewport, not changed)
	replay(s)
end
function UI.open(player, id, tier, options)
	assert(RunService:IsClient(), "Weapon showcase is client-only")
	assert(player == Players.LocalPlayer, "Showcase must belong to the local player")
	UI.close(true)
	options = options or {}
	if not Catalog.ById[id] then
		id = "01"
	end
	local previewTier = math.clamp(math.floor(tonumber(tier) or 1), 1, 4)
	local s = {
		player = player,
		id = id,
		tier = previewTier,
		variant = Data.variant(Recipes.ById[id], options.variant, previewTier).key,
		view = options.view == "weapons" and "weapons" or "attacks",
		loop = true,
		connections = {},
		onClose = options.onClose,
		hiddenScreens = {},
	}
	session = s
	s.gui = T.make("ScreenGui", player:WaitForChild("PlayerGui"), {
		Name = KEY,
		ResetOnSpawn = false,
		ScreenInsets = Enum.ScreenInsets.CoreUISafeInsets,
		SafeAreaCompatibility = Enum.SafeAreaCompatibility.None,
		ClipToDeviceSafeArea = true,
		DisplayOrder = 240,
		ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	})
	s.promptsEnabled = Prompts.Enabled
	Prompts.Enabled = false
	connect(s, Prompts:GetPropertyChangedSignal("Enabled"), function()
		if session == s and Prompts.Enabled then
			Prompts.Enabled = false
		end
	end)
	local function hideScreen(screen)
		if not screen:IsA("ScreenGui") or screen == s.gui or s.hiddenScreens[screen] ~= nil then
			return
		end
		s.hiddenScreens[screen] = screen.Enabled
		screen.Enabled = false
		connect(s, screen:GetPropertyChangedSignal("Enabled"), function()
			if session == s and screen.Enabled then
				s.hiddenScreens[screen] = true
				screen.Enabled = false
			end
		end)
	end
	for _, screen in player.PlayerGui:GetChildren() do
		hideScreen(screen)
	end
	connect(s, player.PlayerGui.ChildAdded, hideScreen)
	s.blocker = T.make("TextButton", s.gui, {
		Name = "ModalBlocker",
		Size = UDim2.fromScale(1, 1),
		BackgroundTransparency = 1,
		Text = "",
		AutoButtonColor = false,
		Active = true,
		Modal = true,
		Selectable = false,
	})
	local camera = workspace.CurrentCamera
	renderChrome(s, camera and camera.ViewportSize or Vector2.new(1280, 720), false)
	connect(s, Input.InputBegan, function(input, processed)
		if input.KeyCode == Enum.KeyCode.Escape or input.KeyCode == Enum.KeyCode.ButtonB then
			if s.popover then
				closePopover(s)
			else
				UI.close()
			end
			return
		end
		if processed or Input:GetFocusedTextBox() then
			return
		end
		local tiers =
			{ [Enum.KeyCode.One] = 1, [Enum.KeyCode.Two] = 2, [Enum.KeyCode.Three] = 3, [Enum.KeyCode.Four] = 4 }
		if tiers[input.KeyCode] then
			selectWeapon(s, s.id, tiers[input.KeyCode], s.variant)
		elseif input.KeyCode == Enum.KeyCode.R then
			replay(s)
		elseif input.KeyCode == Enum.KeyCode.L then
			setLoop(s, not s.loop)
		elseif input.KeyCode == Enum.KeyCode.PageDown or input.KeyCode == Enum.KeyCode.ButtonR1 then
			s.page = math.min(math.ceil(#Catalog.List / s.layout.pageSize), s.page + 1)
			s.view = "weapons"
			renderChrome(s, s.viewport, true)
		elseif input.KeyCode == Enum.KeyCode.PageUp or input.KeyCode == Enum.KeyCode.ButtonL1 then
			s.page = math.max(1, s.page - 1)
			s.view = "weapons"
			renderChrome(s, s.viewport, true)
		end
	end)
	connect(s, s.gui.Destroying, function()
		if session == s then
			UI.close()
		end
	end)
	connect(s, player:GetAttributeChangedSignal("LobbyQueue"), function()
		if player:GetAttribute("LobbyQueue") then
			UI.close(true)
		end
	end)
	connect(s, player:GetAttributeChangedSignal("LobbyPreviewActive"), function()
		if player:GetAttribute("LobbyPreviewActive") == false then
			UI.close(true)
		end
	end)
	connect(s, player.CharacterRemoving, function()
		UI.close(true)
	end)
	T.hideTouchControls(KEY, true)
	T.cameraTake(KEY, function()
		return session == s and s.gui.Parent ~= nil
	end)
	Actions:BindActionAtPriority(
		KEY .. "Movement",
		function()
			return Enum.ContextActionResult.Sink
		end,
		false,
		Enum.ContextActionPriority.High.Value + 50,
		Enum.PlayerActions.CharacterForward,
		Enum.PlayerActions.CharacterBackward,
		Enum.PlayerActions.CharacterLeft,
		Enum.PlayerActions.CharacterRight,
		Enum.PlayerActions.CharacterJump
	)
	local ok, err = pcall(function()
		s.stage = require(RS:WaitForChild("WeaponShowcaseStage")).new(player)
	end)
	if session ~= s then
		if s.stage then
			s.stage:destroy()
		end
		return UI
	end
	if not ok then
		fail(s, err)
		return UI
	end
	s.stage:setViewportRect(s.layout.viewportRect)
	replay(s)
	RunService:BindToRenderStep(KEY, Enum.RenderPriority.Camera.Value + 5, function(dt)
		if session ~= s then
			return
		end
		local cam = workspace.CurrentCamera
		if cam then
			local bounds = screenBounds(cam.ViewportSize)
			if cam.ViewportSize ~= s.viewport or not sameBounds(bounds, s.bounds) then
				renderChrome(s, cam.ViewportSize, false, bounds)
			end
			if T.cameraOwner() == KEY then
				local cf, fov = s.stage:camera()
				cam.CameraType = Enum.CameraType.Scriptable
				cam.CFrame = cf
				cam.FieldOfView = fov
			end
		end
		if not s.failed then
			local good, message = pcall(function()
				s.stage:step(dt)
			end)
			if not good then
				fail(s, message)
			elseif s.loadingText then
				s.loadingText.Visible = s.stage:status().loading == true
			end
		end
	end)
	return UI
end
return UI
