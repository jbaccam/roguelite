--!nonstrict
-- A GUI tree as JSON for tools/gui_view.html (plan K): one entry per visible GuiObject in draw
-- order, positions relative to `root`, with what the viewer needs to redraw it (colours, corners,
-- strokes, gradients, images and 9-slices, text, clipping). Usage (execute_luau):
--   local dump=loadstring(Fresh.source('tools/GuiDump.luau'))()
--   HS:PostAsync('http://127.0.0.1:8934/dump/quests-daily',HS:JSONEncode(dump(root)))
return function(root)
	local out = {}
	local origin = root.AbsolutePosition
	local function rgb(c)
		return { math.round(c.R * 255), math.round(c.G * 255), math.round(c.B * 255) }
	end
	local function walk(g, clip)
		if not g:IsA("GuiObject") or not g.Visible then
			return
		end
		local p, s = g.AbsolutePosition - origin, g.AbsoluteSize
		local e = { n = g.Name, x = p.X, y = p.Y, w = s.X, h = s.Y, r = g.AbsoluteRotation, cl = clip }
		if g.BackgroundTransparency < 1 and not g:IsA("ScrollingFrame") then
			e.bg = rgb(g.BackgroundColor3)
			e.bt = g.BackgroundTransparency
		end
		local isText = g:IsA("TextLabel") or g:IsA("TextButton") or g:IsA("TextBox")
		for _, c in g:GetChildren() do
			if c:IsA("UICorner") then
				e.cr = c.CornerRadius.Scale * math.min(s.X, s.Y) + c.CornerRadius.Offset
			elseif c:IsA("UIStroke") and c.Enabled then
				local onText = isText and c.ApplyStrokeMode == Enum.ApplyStrokeMode.Contextual
				e[onText and "ts" or "bs"] = { rgb(c.Color), c.Thickness, c.Transparency }
			elseif c:IsA("UIGradient") and c.Enabled then
				local k = c.Color.Keypoints
				e.gr = { rgb(k[1].Value), rgb(k[#k].Value), c.Rotation, #k > 2 and rgb(k[2].Value) or nil }
				local t = c.Transparency.Keypoints
				e.gt = { t[1].Value, t[#t].Value }
			end
		end
		if (g:IsA("ImageLabel") or g:IsA("ImageButton")) and g.Image ~= "" and g.ImageTransparency < 1 then
			e.img = g.Image
			e.ic = rgb(g.ImageColor3)
			e.it = g.ImageTransparency
			if g.ScaleType == Enum.ScaleType.Slice then
				e.sl = { g.SliceCenter.Min.X, g.SliceScale }
			end
		end
		if isText and g.Text ~= "" and g.TextTransparency < 1 then
			e.t = g.ContentText
			e.tc = rgb(g.TextColor3)
			e.tt = g.TextTransparency
			e.tb = { g.TextBounds.X, g.TextBounds.Y }
			e.xa = g.TextXAlignment.Name
			e.ya = g.TextYAlignment.Name
			e.f = g.Font.Name
			if g.TextStrokeTransparency < 1 then
				e.tst = g.TextStrokeTransparency
			end
		end
		table.insert(out, e)
		if g.ClipsDescendants then
			local x0, y0, x1, y1 = p.X, p.Y, p.X + s.X, p.Y + s.Y
			if clip then
				x0, y0 = math.max(x0, clip[1]), math.max(y0, clip[2])
				x1, y1 = math.min(x1, clip[1] + clip[3]), math.min(y1, clip[2] + clip[4])
			end
			clip = { x0, y0, math.max(0, x1 - x0), math.max(0, y1 - y0) }
		end
		-- Sibling ZIndexBehavior: higher ZIndex draws later; ties keep creation order.
		local kids = {}
		for i, c in g:GetChildren() do
			if c:IsA("GuiObject") then
				table.insert(kids, { c, i })
			end
		end
		table.sort(kids, function(a, b)
			if a[1].ZIndex ~= b[1].ZIndex then
				return a[1].ZIndex < b[1].ZIndex
			end
			return a[2] < b[2]
		end)
		for _, k in kids do
			walk(k[1], clip)
		end
	end
	walk(root, nil)
	return out
end
