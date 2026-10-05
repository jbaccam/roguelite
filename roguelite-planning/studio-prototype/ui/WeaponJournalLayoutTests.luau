-- Temporary Play CLIENT fixture. Fresh require(...).run(); no remotes or profile writes.
local RS = game:GetService("ReplicatedStorage")
local UI = require(RS.WeaponJournalUI)
local P = require(RS.WeaponJournalPresentation)
local J = require(RS.RogueliteCombat.WeaponJournal)
local W = require(RS.RogueliteCombat.WeaponCatalog)
local TextService = game:GetService("TextService")
local Tests = {}
function Tests.run()
	local checks = 0
	local win
	local panel, body, footer
	local replacedPanels = 0
	local function check(ok, message)
		checks += 1
		assert(ok, message)
	end
	local function inside(a, b)
		local p, s = a.AbsolutePosition, a.AbsoluteSize
		local q, t = b.AbsolutePosition, b.AbsoluteSize
		return p.X >= q.X - 1 and p.Y >= q.Y - 1 and p.X + s.X <= q.X + t.X + 1 and p.Y + s.Y <= q.Y + t.Y + 1
	end
	local function overlap(a, b)
		local p, s = a.AbsolutePosition, a.AbsoluteSize
		local q, t = b.AbsolutePosition, b.AbsoluteSize
		return p.X < q.X + t.X - 0.5 and q.X < p.X + s.X - 0.5 and p.Y < q.Y + t.Y - 0.5 and q.Y < p.Y + s.Y - 0.5
	end
	local function settled()
		-- AbsoluteSize is resolved with GUI layout, after Heartbeat. A resize may rebuild the
		-- panel on a later rendered frame; never retain its destroyed Body in the fixture.
		local run = game:GetService("RunService")
		for _ = 1, 3 do
			run.RenderStepped:Wait()
			run.Heartbeat:Wait()
		end
		if win and win.Root.Parent then
			local current = win.Root:FindFirstChild("JournalPanel")
			if current then
				if panel and panel ~= current then
					replacedPanels += 1
				end
				panel, body, footer = current, current:FindFirstChild("Body"), current:FindFirstChild("Footer")
			end
		end
	end
	local function find(root, name)
		return root:FindFirstChild(name, true)
	end
	local function readable(root)
		for _, label in root:GetDescendants() do
			if label:IsA("TextLabel") and label.Text ~= "" then
				local bounds, size = label.TextBounds, label.AbsoluteSize
				check(not label.TextScaled, "important type never silently shrinks: " .. label:GetFullName())
				check(
					label.TextSize >= (label:GetAttribute("JournalMinimumTextSize") or 14),
					"readable font floor: " .. label.Name
				)
				check(bounds.X > 0 and bounds.Y > 0, "renderer measured text: " .. label.Name)
				check(
					bounds.X <= size.X + 1 and bounds.Y <= size.Y + 1,
					"rendered text fits: "
						.. label:GetFullName()
						.. " / "
						.. label.Text
						.. " "
						.. tostring(bounds)
						.. " in "
						.. tostring(size)
				)
			end
		end
	end
	local function metrics(root)
		for _, card in root:GetDescendants() do
			if card:GetAttribute("JournalMetric") then
				local label, value = card.Label, card.Value
				check(label.TextSize >= 16 and value.TextSize >= 20, "metric type readable")
				check(
					inside(label, card) and inside(value, card) and not overlap(label, value),
					"metric labels and values have separate padded rows"
				)
				check(
					label.Position.Y.Offset >= 10
						and value.Position.Y.Offset + value.Size.Y.Offset <= card.Size.Y.Offset - 12,
					"metric content clears borders"
				)
				if card.Name:match("^BaseStat") then
					check(card.Size.X.Offset <= 190, "base stat cards naturally bounded")
				end
			end
		end
	end
	local function navigation(panel, layout)
		local controls = { panel.WeaponTab, panel.ItemTab, panel.Collection, panel.Search, panel.Close }
		for i, a in controls do
			check(a.Visible and inside(a, panel) and not overlap(a, panel.Body), "navigation persists outside content")
			for j = 1, i - 1 do
				check(not overlap(a, controls[j]), "navigation controls do not overlap")
			end
		end
		check(panel.Search.Size.X.Offset <= 280, "search is bounded")
		check(
			not layout.single or panel.Collection.Position.Y.Offset == panel.Search.Position.Y.Offset,
			"Collection stays on desktop navigation row"
		)
	end
	local ok, err = xpcall(function()
		win = UI.open(game.Players.LocalPlayer)
		check(win.HandlesBack and win.Root and win.Close, "lobby handle contract")
		for _, size in
			{
				Vector2.new(1920, 1080),
				Vector2.new(1891, 721),
				Vector2.new(1366, 768),
				Vector2.new(844, 390),
				Vector2.new(667, 375),
				Vector2.new(390, 844),
				Vector2.new(360, 640),
				Vector2.new(320, 568),
			}
		do
			win.Root.Size = UDim2.fromOffset(size.X, size.Y)
			settled()
			local layout = P.layout(size)
			check(panel and body and footer and panel.Parent == win.Root, "current mounted layout after resize")
			navigation(panel, layout)
			check(inside(body, panel) and inside(footer, panel), "content and footer inside panel")
			for _, kind in { "Weapon", "Item" } do
				win.ShowCollection(kind)
				settled()
				local list = body:FindFirstChild("CollectionList")
				check(
					list ~= nil,
					"ShowCollection must create CollectionList in the current mounted Body: "
						.. tostring(size)
						.. " / "
						.. kind
						.. " / body parent "
						.. tostring(body.Parent)
				)
				local grid = list.CollectionGrid
				local entries = P.filter(kind, "")
				check(#grid:GetChildren() == #entries, "every catalog entry loaded")
				check(list.ScrollingDirection == Enum.ScrollingDirection.Y, "vertical collection scroll retained")
				local tiles = {}
				for _, tile in grid:GetChildren() do
					check(inside(tile, grid), "every tile fits its canvas")
					check(tile.Size.X.Offset <= 190 and tile.Size.Y.Offset <= 180, "collection tiles do not stretch")
					check(not overlap(tile.Icon, tile:FindFirstChild("Name")), "art clears readable name")
					check(
						inside(tile.Status, tile)
							and tile.Status.Position.Y.Offset + tile.Status.Size.Y.Offset <= tile.Size.Y.Offset - 10,
						"status is padded above border"
					)
					for _, prior in tiles do
						check(not overlap(tile, prior), "grid never overlaps")
					end
					table.insert(tiles, tile)
				end
				readable(panel)
				list.CanvasPosition = Vector2.new(0, 99999)
				settled()
				check(inside(grid:FindFirstChild("Entry_" .. entries[#entries].id), list), "last full entry reachable")
				local previous = list.CanvasPosition.Y
				win.Select(kind, entries[#entries].id)
				settled()
				navigation(panel, layout)
				win.Back()
				settled()
				check(math.abs(body.CollectionList.CanvasPosition.Y - previous) < 2, "collection scroll restored")
			end
			panel.Search.Text = "chicken soup"
			settled()
			check(
				#body.CollectionList.CollectionGrid:GetChildren() == 1 and footer.CollectionCount.Text == "1 ITEM",
				"search and count remain functional"
			)
			panel.Search.Text = "__no_matches__"
			settled()
			check(find(body, "NoResults") ~= nil, "empty search explained")
			readable(panel)
			panel.Search.Text = ""
			settled()
			for _, id in { "soup", "antlers", "straws", "alien" } do
				win.Select("Item", id)
				settled()
				navigation(panel, layout)
				local detail = body.DetailContent
				readable(panel)
				metrics(detail)
				check(detail:FindFirstChild("DetailColumns") ~= nil, "one detail canvas")
				if id == "soup" then
					check(
						find(detail, "PlayerBenefit") ~= nil and find(detail, "EveryWeapon") == nil,
						"soup explains player benefit"
					)
					for _, d in detail:GetDescendants() do
						check(not d.Name:match("^Supported_"), "no meaningless soup weapon wall")
					end
				elseif id == "antlers" and layout.split then
					for _, wid in { "31", "35" } do
						local named = find(detail, "Supported_ChainBonus_" .. wid)
						check(named and inside(named, detail), "named compatibility visible immediately")
					end
				elseif id == "straws" then
					check(
						find(detail, "Supported_ProjectileCount_00") ~= nil
							and find(detail, "Supported_ProjectileCount_01") == nil,
						"exact projectile compatibility"
					)
				end
				local columns = detail.DetailColumns
				local summary, article = columns.Summary, columns.Article
				check(not overlap(summary, article), "detail columns never overlap")
				check(
					not layout.split or summary.Position.Y.Offset == article.Position.Y.Offset,
					"desktop article begins beside identity"
				)
				-- One canvas contains two unequal columns. The shorter column's final paragraph
				-- can be above the viewport at the absolute bottom; reveal it at its own offset.
				local lastArticle = find(article, "StudioNote") or find(article, "Since")
				local lastSummary = find(summary, "PurchaseNote")
				local tails = { lastArticle, lastSummary }
				local lowest, lowestBottom = nil, -math.huge
				for _, last in tails do
					local offset = last.AbsolutePosition.Y - detail.AbsolutePosition.Y + detail.CanvasPosition.Y
					local bottom = offset + last.AbsoluteSize.Y
					if bottom > lowestBottom then
						lowest, lowestBottom = last, bottom
					end
					local maxScroll = math.max(0, detail.CanvasSize.Y.Offset - detail.AbsoluteWindowSize.Y)
					detail.CanvasPosition = Vector2.new(0, math.clamp(offset - 4, 0, maxScroll))
					settled()
					check(
						inside(last, detail),
						string.format(
							"detail tail reachable: %s / %s / %s; offset %.1f, canvas %.1f, viewport %.1f, scroll %.1f, summary %.1f, article %.1f",
							tostring(size),
							id,
							last.Name,
							offset,
							detail.CanvasSize.Y.Offset,
							detail.AbsoluteWindowSize.Y,
							detail.CanvasPosition.Y,
							summary.Size.Y.Offset,
							article.Size.Y.Offset
						)
					)
				end
				detail.CanvasPosition = Vector2.new(0, 99999)
				settled()
				check(
					inside(lowest, detail),
					"true lowest content reachable at canvas end: " .. tostring(size) .. " / " .. id
				)
			end
			win.Select("Weapon", "18")
			settled()
			win.SetTier(4)
			settled()
			local detail = body.DetailContent
			readable(panel)
			metrics(detail)
			check(
				find(detail, "TierFour").Explanation.Text == W.legendaryText("18"),
				"actual Tier IV catalog description"
			)
			check(find(detail, "Watch"):GetAttribute("PreviewTier") == 4, "watch uses selected tier")
			check(
				find(detail, "BaseStat1").Value.Text == P.weaponStats(W.ById["18"], 4)[1].value,
				"stat value matches selected tier"
			)
			check(panel.Collection.Visible, "Collection remains visible in weapon details")
			win.ShowCollection()
			settled()
			check(body:FindFirstChild("CollectionList") ~= nil, "persistent Collection returns to list")
		end
		-- Catalog descriptions and long Godly names also use actual rendered bounds at desktop width.
		win.Root.Size = UDim2.fromOffset(1366, 768)
		settled()
		for _, weapon in W.List do
			win.Select("Weapon", weapon.id)
			win.SetTier(4)
			settled()
			readable(win.Root.JournalPanel)
			metrics(win.Root.JournalPanel)
		end
		-- The largest persisted count still fits the minimum supported record width at readable type.
		check(
			TextService:GetTextSize("9,000,000,000,000", 20, Enum.Font.SourceSansBold, Vector2.new(10000, 100)).X <= 224,
			"full lifetime counter fits smallest record card"
		)
	end, debug.traceback)
	if win then
		win.Close()
	end
	return {
		passed = ok,
		checks = checks,
		error = ok and "" or err,
		items = #J.Items,
		weapons = #W.List,
		replacedPanels = replacedPanels,
	}
end

-- Focused geometry probe for the first short landscape case. Always closes its temporary UI.
function Tests.diagnose(width, height, id)
	local win = UI.open(game.Players.LocalPlayer, "Item", id or "soup")
	local function render()
		for _ = 1, 3 do
			game:GetService("RunService").RenderStepped:Wait()
			game:GetService("RunService").Heartbeat:Wait()
		end
	end
	local ok, result = xpcall(function()
		win.Root.Size = UDim2.fromOffset(width or 844, height or 390)
		render()
		local detail = win.Root.JournalPanel.Body.DetailContent
		local summary, article = detail.DetailColumns.Summary, detail.DetailColumns.Article
		local last = article:FindFirstChild("StudioNote") or article:FindFirstChild("Since")
		detail.CanvasPosition = Vector2.new(0, 99999)
		render()
		local offset = last.AbsolutePosition.Y - detail.AbsolutePosition.Y + detail.CanvasPosition.Y
		local data = {
			id = id or "soup",
			root = tostring(win.Root.AbsoluteSize),
			window = tostring(detail.AbsoluteWindowSize),
			canvas = detail.CanvasSize.Y.Offset,
			summaryHeight = summary.Size.Y.Offset,
			articleHeight = article.Size.Y.Offset,
			tail = last.Name,
			tailOffset = offset,
			tailHeight = last.AbsoluteSize.Y,
			bottomScroll = detail.CanvasPosition.Y,
			tailAtBottomY = last.AbsolutePosition.Y - detail.AbsolutePosition.Y,
		}
		detail.CanvasPosition = Vector2.new(
			0,
			math.clamp(offset - 4, 0, math.max(0, detail.CanvasSize.Y.Offset - detail.AbsoluteWindowSize.Y))
		)
		render()
		data.revealScroll = detail.CanvasPosition.Y
		data.revealedTailY = last.AbsolutePosition.Y - detail.AbsolutePosition.Y
		data.revealed = data.revealedTailY >= -1
			and data.revealedTailY + last.AbsoluteSize.Y <= detail.AbsoluteWindowSize.Y + 1
		return data
	end, debug.traceback)
	win.Close()
	return ok and result or { error = result }
end
return Tests
