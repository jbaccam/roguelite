-- Client Studio check: every visible text must fit its label and render inside its
-- nearest visual box (panel/button/well or scroll area). Returns a list of problems.
-- Usage (Client command bar during Play): require(path).run(PlayerGui.SomeScreen)
local M={}
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
function M.run(root,tolerance)
 tolerance=tolerance or 2
 local problems={}
 for _,t in root:GetDescendants() do
  if (t:IsA('TextLabel') or t:IsA('TextButton')) and t.Text~='' and visible(t) and t.AbsoluteSize.X>0 then
   local name=t:GetFullName():gsub('^.-PlayerGui%.','')
   if not t.TextFits then table.insert(problems,'overflow: '..name..' "'..t.ContentText:sub(1,40)..'"') end
   local c=container(t)
   if c then
    local x0,y0=t.AbsolutePosition.X,t.AbsolutePosition.Y
    local tb=t.TextBounds;local sz=t.AbsoluteSize
    local ax=t.TextXAlignment==Enum.TextXAlignment.Left and 0 or t.TextXAlignment==Enum.TextXAlignment.Right and 1 or .5
    local ay=t.TextYAlignment==Enum.TextYAlignment.Top and 0 or t.TextYAlignment==Enum.TextYAlignment.Bottom and 1 or .5
    local lx=x0+(sz.X-tb.X)*ax;local ly=y0+(sz.Y-tb.Y)*ay
    local cx0,cy0,cx1,cy1=box(c)
    -- Nine-slice frames draw a thick border; text must stay inside the inner area.
    if (c:IsA('ImageLabel') or c:IsA('ImageButton')) and c.ScaleType==Enum.ScaleType.Slice then cx0+=6;cy0+=5;cx1-=6;cy1-=5 end
    local vertical=not c:IsA('ScrollingFrame') -- scroll content may be scrolled out of view
    if lx<cx0-tolerance or lx+tb.X>cx1+tolerance or (vertical and (ly<cy0-tolerance or ly+tb.Y>cy1+tolerance)) then
     table.insert(problems,'outside '..c.Name..': '..name..' "'..t.ContentText:sub(1,40)..'"')
    end
   end
  end
 end
 return problems
end
return M
