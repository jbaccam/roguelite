-- Client Studio check: every visible text must fit its label and render inside its
-- nearest visual box (panel/button/well or scroll area). Returns a list of problems.
-- Usage (Client command bar during Play): require(path).run(PlayerGui.SomeScreen)
--
-- Every screen size at once: M.sweep(PlayerGui.Armory.Root) resizes the screen's root frame (the
-- Size 1,1 frame every screen lays itself out in) to each size in M.Devices, lets it re-lay out,
-- and reports per size: text that doesn't fit or leaves its box, pieces of different groups that
-- overlap (M.overlaps), pieces off the screen, text drawn smaller than MIN_TEXT px and buttons
-- smaller than MIN_TAP px on phones. The root's size is restored afterwards.
-- Example: require(game.ReplicatedStorage.UILayoutAudit).sweep(game.Players.LocalPlayer.PlayerGui.Armory.Root)
local M={}
M.Devices={
 {'1920x1080',1920,1080},{'1366x768',1366,768},{'1280x720',1280,720},{'1536x864',1536,864},
 {'1440x900',1440,900},{'1280x800',1280,800},{'2560x1440',2560,1440},{'3840x2160',3840,2160},
 {'2560x1080',2560,1080},{'3440x1440',3440,1440},{'1600x1200',1600,1200},{'Studio 1500x750',1500,750},
 {'iPad 1024x768',1024,768},{'iPad Air 1180x820',1180,820},{'iPad Pro 1366x1024',1366,1024},
 {'iPhone 14 750x369',750,369,true},{'iPhone Max 814x409',814,409,true},{'iPhone SE 667x375',667,375,true},
 {'Android 800x360',800,360,true},
}
M.MIN_TEXT=9;M.MIN_TAP=36
local function box(g)
 local p,s=g.AbsolutePosition,g.AbsoluteSize
 return p.X,p.Y,p.X+s.X,p.Y+s.Y
end
local function visible(g)
 local o=g
 while o and o:IsA('GuiObject') do if not o.Visible then return false end;o=o.Parent end
 return not (o and o:IsA('LayerCollector')) or o.Enabled
end
-- Nearest ancestor that draws a visible box.
local function container(g)
 local o=g.Parent
 while o and o:IsA('GuiObject') do
  if o:IsA('ScrollingFrame') or ((o:IsA('ImageLabel') or o:IsA('ImageButton')) and o.Image~='' and o.ImageTransparency<1) or (o:IsA('Frame') and o.BackgroundTransparency<1) then return o end
  o=o.Parent
 end
end
local function name(g) return (g:GetFullName():gsub('^.-PlayerGui%.','')) end
-- Marked AuditIgnore itself or inside something that is (e.g. a pan/zoom board behind the cards).
local function ignored(g)
 local o=g
 while o and o:IsA('GuiObject') do if o:GetAttribute('AuditIgnore') then return true end;o=o.Parent end
 return false
end
-- The on-screen rectangle a text actually covers (its TextBounds placed by its alignment).
local function textRect(t)
 local x0,y0=t.AbsolutePosition.X,t.AbsolutePosition.Y
 local tb=t.TextBounds;local sz=t.AbsoluteSize
 local ax=t.TextXAlignment==Enum.TextXAlignment.Left and 0 or t.TextXAlignment==Enum.TextXAlignment.Right and 1 or .5
 local ay=t.TextYAlignment==Enum.TextYAlignment.Top and 0 or t.TextYAlignment==Enum.TextYAlignment.Bottom and 1 or .5
 local lx=x0+(sz.X-tb.X)*ax;local ly=y0+(sz.Y-tb.Y)*ay
 return lx,ly,lx+tb.X,ly+tb.Y
end
function M.run(root,tolerance)
 tolerance=tolerance or 2
 local problems={}
 for _,t in root:GetDescendants() do
  if (t:IsA('TextLabel') or t:IsA('TextButton')) and t.Text~='' and visible(t) and t.AbsoluteSize.X>0 then
   local n=name(t)
   if not t.TextFits then table.insert(problems,'overflow: '..n..' "'..t.ContentText:sub(1,40)..'"') end
   local c=container(t)
   if c then
    local lx,ly,rx,by=textRect(t)
    local cx0,cy0,cx1,cy1=box(c)
    -- Nine-slice frames draw a thick border; text must stay inside the inner area.
    if (c:IsA('ImageLabel') or c:IsA('ImageButton')) and c.ScaleType==Enum.ScaleType.Slice then cx0+=6;cy0+=5;cx1-=6;cy1-=5 end
    local vertical=not c:IsA('ScrollingFrame') -- scroll content may be scrolled out of view
    if lx<cx0-tolerance or rx>cx1+tolerance or (vertical and (ly<cy0-tolerance or by>cy1+tolerance)) then
     table.insert(problems,'outside '..c.Name..': '..n..' "'..t.ContentText:sub(1,40)..'"')
    end
   end
  end
 end
 return problems
end

-- What a piece draws on screen, or nil: text bounds, images, filled frames. Pieces inside a
-- scrolling list are clipped to the list (scrolled-away content is not "overlapping" anything).
local function drawn(g)
 if not (g:IsA('GuiObject') and visible(g)) or ignored(g) then return nil end
 local x0,y0,x1,y1
 if (g:IsA('TextLabel') or g:IsA('TextButton')) and g.Text~='' and g.TextTransparency<1 then x0,y0,x1,y1=textRect(g)
 elseif ((g:IsA('ImageLabel') or g:IsA('ImageButton')) and g.Image~='' and g.ImageTransparency<1) or g.BackgroundTransparency<1 then x0,y0,x1,y1=box(g)
 else return nil end
 local o=g.Parent
 while o and o:IsA('GuiObject') do
  if o:IsA('ScrollingFrame') or o.ClipsDescendants then
   local a,b,c,d=box(o);x0,y0,x1,y1=math.max(x0,a),math.max(y0,b),math.min(x1,c),math.min(y1,d)
  end
  o=o.Parent
 end
 if x1-x0<1 or y1-y0<1 then return nil end
 return {x0,y0,x1,y1,g}
end
-- Pieces of different top-level groups (direct children of `root`) that overlap by more than
-- `tolerance` px. Pieces inside one group may overlap on purpose (a badge on a card).
function M.overlaps(root,tolerance)
 tolerance=tolerance or 2
 local groups={}
 for _,g in root:GetChildren() do
  if g:IsA('GuiObject') and visible(g) and not g:GetAttribute('AuditIgnore') then
   local rects={};local r=drawn(g);if r then table.insert(rects,r) end
   for _,d in g:GetDescendants() do r=drawn(d);if r then table.insert(rects,r) end end
   if #rects>0 then table.insert(groups,{g,rects}) end
  end
 end
 local problems={}
 for i=1,#groups do for j=i+1,#groups do
  local hit
  for _,a in groups[i][2] do
   for _,b in groups[j][2] do
    if math.min(a[3],b[3])-math.max(a[1],b[1])>tolerance and math.min(a[4],b[4])-math.max(a[2],b[2])>tolerance then hit={a[5],b[5]};break end
   end
   if hit then break end
  end
  if hit then table.insert(problems,'overlap: '..name(hit[1])..' / '..name(hit[2])) end
 end end
 return problems
end
-- Drawn pieces outside `root`'s rectangle, text drawn too small, and (phones) small buttons.
function M.bounds(root,phone)
 local problems={}
 local rx0,ry0,rx1,ry1=box(root)
 for _,d in root:GetDescendants() do
  local r=drawn(d)
  if r and (r[1]<rx0-2 or r[2]<ry0-2 or r[3]>rx1+2 or r[4]>ry1+2) and not d:GetAttribute('AuditOffscreenOk') then
   table.insert(problems,'off screen: '..name(d))
  end
  -- One text line is about 1.15x the font size tall.
  if r and (d:IsA('TextLabel') or d:IsA('TextButton')) and d.TextBounds.Y>0 and d.TextBounds.Y<M.MIN_TEXT*1.15 then
   table.insert(problems,string.format('small text (%.0f px): %s "%s"',d.TextBounds.Y/1.15,name(d),d.ContentText:sub(1,30)))
  end
  if phone and d:IsA('GuiButton') and visible(d) and d.AbsoluteSize.X>0 and not ignored(d)
   and math.min(d.AbsoluteSize.X,d.AbsoluteSize.Y)<M.MIN_TAP and d.Name~='DragArea' then
   table.insert(problems,string.format('small button (%.0fx%.0f): %s',d.AbsoluteSize.X,d.AbsoluteSize.Y,name(d)))
  end
 end
 return problems
end
-- Resize `root` (a screen's Size 1,1 root frame) to every device size and audit it. `groupsRoot`
-- (default: the canvas inside root when there is one, else root) holds the top-level groups.
-- Returns {size name -> problems}; prints a summary. Restores the root's size.
function M.sweep(root,groupsRoot,devices)
 local original=root.Size
 local out={}
 for _,d in devices or M.Devices do
  root.Size=UDim2.fromOffset(d[2],d[3])
  task.wait(.15);task.wait(.15) -- layout, then any redraw it triggers
  local g=groupsRoot or root:FindFirstChild('Canvas') or root
  local list={}
  for _,p in M.run(root) do table.insert(list,p) end
  for _,p in M.overlaps(g) do table.insert(list,p) end
  for _,p in M.bounds(root,d[4]) do table.insert(list,p) end
  out[d[1]]=list
  print(string.format('[UILayoutAudit] %s: %d problem(s)',d[1],#list))
  for i,p in list do if i<=12 then print('   '..p) end end
 end
 root.Size=original
 return out
end
return M
