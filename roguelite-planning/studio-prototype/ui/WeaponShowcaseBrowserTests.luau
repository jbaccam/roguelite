-- Read-only geometry checks and optional client-only cosmetic UI checks.
-- No synthesized input, gameplay remotes, rewards, or profile writes.
local Tests = {}
local function inside(a, b)
	return a.x >= b.x - 0.01 and a.y >= b.y - 0.01 and a.x + a.w <= b.x + b.w + 0.01 and a.y + a.h <= b.y + b.h + 0.01
end
local function separate(a, b)
	return a.x + a.w <= b.x + 0.01 or b.x + b.w <= a.x + 0.01 or a.y + a.h <= b.y + 0.01 or b.y + b.h <= a.y + 0.01
end
function Tests.run(UI, Catalog, Data)
	local passed, layouts = 0, 0
	local context = ""
	local function check(ok, why)
		assert(ok, context .. ": " .. why)
		passed += 1
	end
	local sizes = {
		{ 2560, 1440 },
		{ 1920, 1080 },
		{ 1891, 793 },
		{ 1440, 900 },
		{ 1366, 768 },
		{ 1024, 768 },
		{ 820, 1180 },
		{ 768, 1024 },
		{ 750, 369 },
		{ 667, 375 },
		{ 620, 540 },
		{ 620, 580 },
		{ 390, 680 },
		{ 390, 679 },
		{ 390, 844 },
		{ 360, 640 },
		{ 320, 568 },
		{ 1891, 793, { top = 58 } },
		{ 1891, 793, { top = 36 } },
		{ 851, 392, { left = 59, top = 58, right = 59, bottom = 21 } },
		{ 390, 844, { top = 58, bottom = 34 } },
		{ 667, 375, { top = 58 } },
		{ 640, 360, { left = 32, top = 58, right = 32, bottom = 21 } },
		{ 320, 568, { top = 58 } },
	}
	local recipes = Data.build(Catalog)
	for _, size in sizes do
		for _, weapon in Catalog.List do
			context = string.format("%dx%d weapon %s", size[1], size[2], weapon.id)
			local attacks, styles = 0, 0
			for _, v in recipes.ById[weapon.id].variants do
				if v.style then
					styles += 1
				else
					attacks += 1
				end
			end
			local inset = size[3] or {}
			local L = UI.layoutFor(size[1], size[2], attacks, styles > 1, inset)
			layouts += 1
			local screen = { x = 0, y = 0, w = L.width, h = L.height }
			check(
				L.width == size[1] - (inset.left or 0) - (inset.right or 0)
					and L.height == size[2] - (inset.top or 0) - (inset.bottom or 0),
				"Exact native safe-area canvas"
			)
			check(
				inside(L.rail, screen) and inside(L.stage, screen) and separate(L.rail, L.stage),
				"Panel never intrudes into the stage"
			)
			if L.mode == "side" then
				check(
					L.rail.w <= 348 and L.stage.w >= L.width * 0.42,
					"Compact right rail leaves the majority of width for the scene"
				)
				check(L.stage.h >= L.height * 0.90, "Uninterrupted full-height desktop scene")
			else
				check(L.stage.h >= L.height * 0.37, "Portrait dock preserves useful stage height")
			end
			local common = { L.back, L.icon, L.title, L.attackTab, L.browseTab }
			for _, r in L.tierButtons do
				table.insert(common, r)
			end
			for _, name in { "subtitle", "eyebrow", "tierLabel" } do
				if L[name] then
					table.insert(common, L[name])
				end
			end
			for i, r in common do
				check(r.w > 0 and r.h > 0 and inside(r, L.rail), "Common control fits inside the rail")
				check(separate(r, L.controls), "Identity and navigation stay clear of both content views")
				for j = 1, i - 1 do
					check(separate(r, common[j]), "Common controls never overlap")
				end
			end
			for _, r in L.tierButtons do
				check(r.w >= 40 and r.h >= 30, "All four tiers retain usable targets")
			end
			local controls = table.clone(L.attacks)
			table.insert(controls, L.replay)
			table.insert(controls, L.loop)
			for i, r in controls do
				check(
					r.w >= 60 and r.h >= 32 and inside(r, L.controls),
					"Attack and playback controls fit at readable sizes"
				)
				check(
					r.x - L.controls.x >= 8 - 0.01 and L.controls.x + L.controls.w - r.x - r.w >= 8 - 0.01,
					"Controls have real horizontal padding"
				)
				for j = 1, i - 1 do
					check(separate(r, controls[j]), "Attack controls never collide with playback")
				end
			end
			if L.condition then
				check(inside(L.condition, L.controls) and L.condition.h >= 18, "Description has a readable row")
				check(
					L.condition.x - L.controls.x >= 20
						and L.controls.x + L.controls.w - L.condition.x - L.condition.w >= 20,
					"Description stays inside the bevels"
				)
				check(L.replay.y - L.condition.y - L.condition.h >= 12 - 0.01, "Description clears playback controls")
				for _, r in L.attacks do
					check(L.condition.y - r.y - r.h >= 8 - 0.01, "Description clears attack buttons")
				end
			end
			check(L.pageSize >= 2 and L.pageSize <= 6, "Collection uses a compact bounded page")
			check(
				inside(L.previous, L.picker) and inside(L.next, L.picker) and inside(L.pageLabel, L.picker),
				"Pager stays inside collection"
			)
			for i, r in L.cards do
				check(
					r.w >= 80 and r.h >= 60 and inside(r, L.picker),
					"Weapon tiles preserve space for icons and names"
				)
				check(
					separate(r, L.previous) and separate(r, L.next) and separate(r, L.pageLabel),
					"Tiles stay clear of pagination"
				)
				for j = 1, i - 1 do
					check(separate(r, L.cards[j]), "Weapon tiles never overlap")
				end
			end
			local seen = {}
			for page = 1, math.ceil(#Catalog.List / L.pageSize) do
				for offset = 1, L.pageSize do
					local index = (page - 1) * L.pageSize + offset
					if Catalog.List[index] then
						check(not seen[index], "No repeated weapon in page partition")
						seen[index] = true
					end
				end
			end
			check(#seen == #Catalog.List, "All weapons reachable")
			local at = table.find(Catalog.List, weapon)
			local page = math.ceil(at / L.pageSize)
			check(
				at > (page - 1) * L.pageSize and at <= page * L.pageSize,
				"Direct entry displays selected weapon page"
			)
			local rect = L.viewportRect
			check(
				rect.left >= 0
					and rect.right <= 1
					and rect.top >= 0
					and rect.bottom <= 1
					and rect.left < rect.right
					and rect.top < rect.bottom,
				"Valid full-screen camera rectangle"
			)
			check(
				math.abs(rect.left * size[1] - L.stage.x - (inset.left or 0)) < 0.01
					and math.abs(rect.bottom * size[2] - L.stage.y - L.stage.h - (inset.top or 0)) < 0.01,
				"Camera rectangle matches the actual clear stage"
			)
			check(rect.fullWidth == size[1] and rect.fullHeight == size[2], "Camera uses full render dimensions")
			if styles > 1 or L.attackDropdown then
				local count = L.attackDropdown and #recipes.ById[weapon.id].variants or styles + 1
				local menu = UI.swingMenuFor(L, L.attacks[#L.attacks], count)
				check(
					inside(menu, L.rail) and separate(menu, L.stage),
					"Temporary choice menu stays within the rail, never covering the scene"
				)
			end
		end
	end
	return { passed = passed, layouts = layouts, weapons = #Catalog.List, viewports = #sizes }
end
local function visibleWithin(label, root)
	local at = label
	while at and at ~= root do
		if at:IsA("GuiObject") and not at.Visible then
			return false
		end
		at = at.Parent
	end
	return true
end
local function inspectText(gui, check, compact)
	for _, label in gui:GetDescendants() do
		if label:IsA("TextLabel") and label.Text ~= "" and visibleWithin(label, gui) then
			local minimum
			if
				label.Name == "Eyebrow"
				or label.Name == "Classes"
				or label.Name == "TierLabel"
				or label.Name == "Name"
			then
				minimum = 14
			elseif label.Name == "AttackDescription" then
				minimum = compact and 14 or 16
			elseif label.Name == "Caption" and (label.Parent.Name == "Replay" or label.Parent.Name == "Loop") then
				minimum = compact and 14 or 16
			elseif label.Name == "Page" then
				minimum = 12
			end
			if minimum then
				check(
					not label.TextScaled and label.TextSize >= minimum,
					"Supporting text keeps its readable authored size: " .. label:GetFullName()
				)
				check(
					label.TextBounds.Y >= minimum * 0.65,
					"Supporting text has a measured readable glyph height: " .. label:GetFullName()
				)
			end
			if label.Name == "WeaponTitle" then
				check(
					label:FindFirstChildOfClass("UITextSizeConstraint").MinTextSize >= 14,
					"Fitted title has a readable lower bound"
				)
			end
		end
		if
			label:IsA("TextLabel")
			and label.Text ~= ""
			and visibleWithin(label, gui)
			and label.TextTruncate == Enum.TextTruncate.None
		then
			local size, bounds = label.AbsoluteSize, label.TextBounds
			check(
				size.X > 0 and size.Y > 0 and bounds.X > 0 and bounds.Y > 0,
				"Visible text has measured bounds: " .. label:GetFullName()
			)
			check(
				bounds.X <= size.X + 1 and bounds.Y <= size.Y + 1,
				"Rendered text fits without clipping: " .. label:GetFullName()
			)
		end
	end
end
function Tests.client(UI, player)
	assert(game:GetService("RunService"):IsClient(), "Mounted checks are client-only")
	assert(not UI.isOpen(), "Close existing preview before lifecycle tests")
	local pg = player.PlayerGui
	local prompts = game:GetService("ProximityPromptService")
	local before = prompts.Enabled
	local prior = {}
	for _, gui in pg:GetChildren() do
		if gui:IsA("ScreenGui") then
			prior[gui] = gui.Enabled
		end
	end
	local passed, presentations = 0, 0
	local function check(ok, why)
		assert(ok, why)
		passed += 1
	end
	local ok, reason = pcall(function()
		for _, case in
			{
				{ "18", 1 },
				{ "18", 4 },
				{ "28", 2 },
				{ "36", 4 },
				{ "18", 4, "Flush", "Flush" },
				{ "18", 1, "Flush", "Base" },
				{ "18", 4, "Unknown", "Base" },
			}
		do
			for _, view in { "attacks", "weapons" } do
				UI.open(player, case[1], case[2], { variant = case[3], view = view })
				game:GetService("RunService").RenderStepped:Wait()
				game:GetService("RunService").RenderStepped:Wait()
				presentations += 1
				local state = UI.debugState()
				local gui = pg:FindFirstChild("WeaponShowcase")
				local browser = gui.ModalBlocker.Browser
				check(
					state.id == case[1]
						and state.tier == case[2]
						and state.variant == (case[4] or "Base")
						and state.view == view,
					"Validated selection and view preserved"
				)
				check(not prompts.Enabled, "World stations cannot steal camera")
				check(
					gui.ScreenInsets == Enum.ScreenInsets.CoreUISafeInsets
						and gui.SafeAreaCompatibility == Enum.SafeAreaCompatibility.None,
					"Native safe-area behavior retained"
				)
				local service = game:GetService("GuiService")
				local safe = service:GetInsetArea(Enum.ScreenInsets.CoreUISafeInsets)
				local full = service:GetInsetArea(Enum.ScreenInsets.None)
				check(
					math.abs(browser.AbsoluteSize.X - safe.Width) < 1
						and math.abs(browser.AbsoluteSize.Y - safe.Height) < 1,
					"Mounted canvas matches safe area"
				)
				check(
					browser.Close.Caption.Text == "BACK" and browser.Close.AbsolutePosition.Y >= safe.Min.Y,
					"Return control clears topbar"
				)
				check(
					state.viewportRect.fullWidth == full.Width and state.viewportRect.fullHeight == full.Height,
					"Full-screen camera size retained"
				)
				local selectedTiers = 0
				for tier = 1, 4 do
					local segment = browser:FindFirstChild("Tier" .. tier)
					check(segment and segment.Interactable, "All tiers selectable")
					if segment:GetAttribute("Selected") then
						selectedTiers += 1
						check(tier == case[2], "Requested tier visibly selected")
					end
				end
				check(selectedTiers == 1, "Exactly one tier selected")
				if view == "weapons" then
					local tile = browser.WeaponTiles:FindFirstChild("Weapon_" .. case[1])
					check(tile and tile:GetAttribute("Selected"), "Selected weapon appears on its collection page")
					check(#browser.WeaponTiles:GetChildren() <= 6, "Only a small page mounted")
					check(not browser:FindFirstChild("AttackControls"), "Collection does not overlap attack controls")
				else
					check(browser.Replay and browser.Loop.Caption.Text == "LOOP ON", "Replay and Loop are explicit")
					local selected = browser:FindFirstChild("Variant_" .. (case[4] or "Base"))
						or browser:FindFirstChild("AttackPicker")
					check(selected and selected:GetAttribute("Selected"), "Requested attack visibly selected")
					check(not browser:FindFirstChild("WeaponTiles"), "Attack controls do not overlap collection")
					local description = browser:FindFirstChild("AttackDescription")
					if description then
						local p, ps = browser.AttackControls.AbsolutePosition, browser.AttackControls.AbsoluteSize
						local d, ds = description.AbsolutePosition, description.AbsoluteSize
						check(
							d.X - p.X >= 20 - 0.1 and p.X + ps.X - d.X - ds.X >= 20 - 0.1,
							"Actual description clears both side bevels"
						)
						check(
							browser.Replay.AbsolutePosition.Y - d.Y - ds.Y >= 12 - 0.1,
							"Actual description clears playback row"
						)
						for _, control in browser:GetChildren() do
							if
								control:IsA("GuiButton")
								and (
									string.sub(control.Name, 1, 8) == "Variant_"
									or control.Name == "SwingPicker"
									or control.Name == "AttackPicker"
								)
							then
								check(
									d.Y - control.AbsolutePosition.Y - control.AbsoluteSize.Y >= 8 - 0.1,
									"Actual description clears attack rows"
								)
							end
						end
					end
				end
				inspectText(gui, check, state.compact)
				for screen in prior do
					if screen.Parent then
						check(not screen.Enabled, "Lobby stays hidden")
					end
				end
				UI.close(true)
				check(
					not UI.isOpen() and UI.debugState().connections == 0 and not pg:FindFirstChild("WeaponShowcase"),
					"Close releases UI and session connections"
				)
				check(prompts.Enabled == before, "Prompt state restored")
				for screen, enabled in prior do
					if screen.Parent then
						check(screen.Enabled == enabled, "Prior screen state restored")
					end
				end
			end
		end
	end)
	UI.close(true)
	assert(ok, reason)
	return { passed = passed, presentations = presentations }
end
-- All catalog names measured in actual mounted TextLabels at the current client viewport.
function Tests.text(UI, player, Catalog)
	assert(not UI.isOpen(), "Close existing preview before catalog text checks")
	local passed = 0
	local function check(ok, why)
		assert(ok, why)
		passed += 1
	end
	local ok, reason = pcall(function()
		for _, weapon in Catalog.List do
			UI.open(player, weapon.id, 4, { view = "weapons" })
			game:GetService("RunService").RenderStepped:Wait()
			game:GetService("RunService").RenderStepped:Wait()
			inspectText(player.PlayerGui.WeaponShowcase, check, UI.debugState().compact)
			UI.close(true)
		end
	end)
	UI.close(true)
	assert(ok, reason)
	return { passed = passed, weapons = #Catalog.List }
end
return Tests
