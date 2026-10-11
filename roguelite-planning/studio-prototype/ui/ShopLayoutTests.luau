-- Client Studio layout checks. Uses actual rendered geometry and TextFits.
-- 2026-10-09 roster: weapon offers show the specialty bar (SpecBar), one row per type (TypeChip_ /
-- TypeStep_ / TypeLine_) and the stat lines; the stats column has SETS (pinned or a Sets tab).
local gui=game.Players.LocalPlayer.PlayerGui.RogueliteHUD
local Weapons=require(game.ReplicatedStorage.RogueliteCombat.WeaponCatalog)
local Stats=require(game.ReplicatedStorage.RogueliteCombat.CharacterStats)
local state=game.ReplicatedStorage.RogueliteCombat.PlayerStates:FindFirstChild(tostring(game.Players.LocalPlayer.UserId))
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
  -- The crystal bag beside the crystals (2026-10-03), when it holds some.
  local bag=left:FindFirstChild('Bag')
  if bag then
   assert(disjoint(bag,left.Shards) and disjoint(bag,left.ShopTitle) and disjoint(bag,left.Reroll),'bag overlaps header')
   if left:FindFirstChild('RobuxReroll') then assert(disjoint(bag,left.RobuxReroll),'bag overlaps Robux reroll') end
   local note=left:FindFirstChild('BagNote')
   assert(note,'bag caption missing')
   -- 2026-10-10: the caption sits right beside the bag, centred on it.
   assert(note.AbsolutePosition.X>=right(bag)-1 and note.AbsolutePosition.X<=right(bag)+12,'bag caption not beside the bag')
   assert(math.abs((note.AbsolutePosition.Y+note.AbsoluteSize.Y/2)-(bag.AbsolutePosition.Y+bag.AbsoluteSize.Y/2))<2,'bag caption not centred on the bag')
   if left:FindFirstChild('RerollOdds') then assert(disjoint(note,left.RerollOdds),'bag caption overlaps odds') end
   for i=1,4 do local card=left:FindFirstChild('Offer'..i);if card then assert(disjoint(note,card),'bag caption overlaps offer') end end
  end
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
    -- Weapon cards: the specialty bar, type rows, stat lines and traits never overlap each other or
    -- Buy. Item cards: the "Works with" line clear of the description and Buy.
    if card:FindFirstChild('SpecBar') then
     local pieces={card.SpecBar,card.Attack}
     for _,c in card:GetChildren() do if c.Name:match('^WeaponStat') or c.Name:match('^TypeLine_') or c.Name:match('^TypeChip_') then table.insert(pieces,c) end end
     if card:FindFirstChild('Traits') and card.Traits.Text~='' then table.insert(pieces,card.Traits) end
     for i,a in pieces do
      assert(disjoint(a,card.Buy),'weapon card piece over Buy: '..a.Name)
      for j=i+1,#pieces do local b=pieces[j];if not (a.Name:match('^TypeChip_') and b.Name:match('^TypeChip_')) then assert(disjoint(a,b),'weapon card pieces overlap: '..a.Name..' / '..b.Name) end end
     end
     local w=Weapons.ById[card.SpecBar:GetAttribute('WeaponId')]
     for _,t in w.types do assert(card:FindFirstChild('TypeChip_'..t) and card:FindFirstChild('TypeLine_'..t),'type row for '..t..' on '..w.name) end
    end
    if card:FindFirstChild('WorksWith') then assert(disjoint(card.WorksWith,card.Description) and disjoint(card.WorksWith,card.Buy),'works-with overlap') end
   end
  end
  -- An open weapon detail (select a weapon before running): stat lines and traits never under the
  -- class row, the buttons below it (2026-10-03: Range was hidden behind MAGE · RANGED).
  local details=layout:FindFirstChild('Details')
  if details and details.Body:FindFirstChild('SpecBar') then
   local body=details.Body
   for _,c in body:GetChildren() do
    if c.Name:match('^WeaponStat') or c.Name=='Traits' or c.Name:match('^TypeLine_') then assert(disjoint(c,body.SpecBar),'detail line under the specialty bar') end
    if c.Name:match('^TypeLine_') then assert(body.Combine.AbsolutePosition.Y>=bottom(c),'detail buttons over a type row') end
   end
   assert(body.Combine.AbsolutePosition.Y>=bottom(body.SpecBar),'detail buttons over the specialty bar')
   assert(layout:FindFirstChild('DetailsBacking'),'detail popup has a solid backing')
  end
  for _,label in layout:GetDescendants() do
   -- The specialty bar says which rule applies: your class's weapon, your class's drawback, or none.
   if label.Name=='SpecBar' and label:GetAttribute('WeaponId') and state then
    local w=Weapons.ById[label:GetAttribute('WeaponId')];local class=state:GetAttribute('Class')
    local kind=label:GetAttribute('Kind')
    if w.godly then assert(kind=='godly','Godly spec bar')
    elseif Stats.specialty(w,class)>0 then assert(kind=='specialty','specialty bar on '..w.name)
    else assert(kind=='drawback' or kind=='neutral','off-class bar on '..w.name) end
   end
   if label.Name=='PriceGroup' then
    local center=label.AbsolutePosition.X+label.AbsoluteSize.X/2;local parentCenter=label.Parent.AbsolutePosition.X+label.Parent.AbsoluteSize.X/2
    assert(math.abs(center-parentCenter)<1.5,'price not centered')
    assert(label.AbsoluteSize.X<=label.Parent.AbsoluteSize.X-4,'price outside button')
   end
   if label:IsA('TextLabel') and label.Text~='' then assert(label.TextFits,'text overflow '..label:GetFullName()..' at '..tostring(size)) end
  end
  -- SETS: pinned rows (desktop) or the Sets tab's rows sit inside the stats column, clear of the tabs.
  for _,r in stats:GetDescendants() do
   if r.Name:match('^Set_') and r:IsA('Frame') then
    assert(r:FindFirstAncestor('SetRows')~=nil or (r.AbsolutePosition.Y>=stats.AbsolutePosition.Y and bottom(r)<=bottom(stats)+1),'set row inside the stats column')
    local tab=stats:FindFirstChild('PrimaryTab');if tab and not r:FindFirstAncestor('SetRows') then assert(disjoint(r,tab),'set row over the tabs') end
   end
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
