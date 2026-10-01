-- Client Studio layout checks. Uses actual rendered geometry and TextFits.
local gui=game.Players.LocalPlayer.PlayerGui.RogueliteHUD
local root=gui.SafeArea
local original=root.Size
local results={}
local function right(g) return g.AbsolutePosition.X+g.AbsoluteSize.X end
local function bottom(g) return g.AbsolutePosition.Y+g.AbsoluteSize.Y end
local function disjoint(a,b)
 return right(a)<=b.AbsolutePosition.X+1 or right(b)<=a.AbsolutePosition.X+1 or bottom(a)<=b.AbsolutePosition.Y+1 or bottom(b)<=a.AbsolutePosition.Y+1
end
local ok,err=xpcall(function()
 for _,size in {Vector2.new(1920,1080),Vector2.new(1440,900),Vector2.new(1280,720),Vector2.new(1024,768),Vector2.new(800,600),Vector2.new(640,360),Vector2.new(390,844),Vector2.new(750,311),Vector2.new(667,317),Vector2.new(800,302)} do
  root.Size=UDim2.fromOffset(size.X,size.Y);task.wait(.2)
  local menus=root.Menus;local content=menus.Content;local layout=content.Canvas.ShopLayout
  local left=layout.ShopMain;local stats=layout.StatsColumn
  assert(right(left)<stats.AbsolutePosition.X,'left/right gutter '..tostring(size))
  assert(right(stats)<=right(content)+1,'stats exceeds content')
  assert(bottom(stats)<layout.StartWave.AbsolutePosition.Y,'stats/start gutter')
  assert(disjoint(left.Items,left.Weapons),'items/weapons overlap')
  assert(disjoint(left.Reroll,left.Shards) and disjoint(left.Shards,left.ShopTitle),'header overlaps')
  for _,v in left.Weapons:GetChildren() do
   if v:IsA('ImageButton') then assert(v:FindFirstChild('WeaponIcon') or v:FindFirstChild('WeaponPreview'),'empty weapon box') end
  end
  for i=1,4 do
   local card=left:FindFirstChild('Offer'..i)
   if card then
    assert(card.AbsolutePosition.X-2>=left.AbsolutePosition.X,'left border clipped')
    assert(right(card)+2<=right(left),'right border clipped')
    -- Green theme: tier II+ cards carry recoloured RarityCorners (T.setTier); common keeps the lime panel.
    local tier=card:GetAttribute('Tier') or 1
    assert(card.Image~='' and ((tier>1)==(card:FindFirstChild('RarityCorners')~=nil)),'rarity frame mismatch')
    assert(disjoint(card,left.Items) and disjoint(card,left.Weapons),'offer/inventory overlap')
    assert(bottom(card.Buy)<=bottom(card)-8,'price overlaps card border')
    assert(disjoint(card,left['Lock'..i]),'lock overlaps card border')
    for j=i+1,4 do local other=left:FindFirstChild('Offer'..j);if other then assert(disjoint(card,other),'offer overlap') end end
   end
  end
  for _,label in layout:GetDescendants() do
   if label.Name=='PriceGroup' then
    local center=label.AbsolutePosition.X+label.AbsoluteSize.X/2;local parentCenter=label.Parent.AbsolutePosition.X+label.Parent.AbsoluteSize.X/2
    assert(math.abs(center-parentCenter)<1.5,'price not centered')
    assert(label.AbsoluteSize.X<=label.Parent.AbsoluteSize.X-4,'price outside button')
   end
   if label:IsA('TextLabel') and label.Text~='' then assert(label.TextFits,'text overflow '..label:GetFullName()..' at '..tostring(size)) end
  end
  -- Phone-height views (the HUD root of a 844x390 iPhone is 750x311): every button is a 40 px tap.
  if size.Y<450 then
   for _,b in layout:GetDescendants() do
    if b:IsA('GuiButton') and b.Name~='FocusBackdrop' and b.Visible then
     assert(b.AbsoluteSize.X>=39.5 and b.AbsoluteSize.Y>=39.5,'small tap target '..b:GetFullName()..' at '..tostring(size))
    end
   end
  end
  table.insert(results,tostring(size))
 end
end,debug.traceback)
root.Size=original
return {passed=ok,error=ok and '' or err,resolutions=results}
