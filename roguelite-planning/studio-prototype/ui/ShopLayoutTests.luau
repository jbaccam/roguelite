-- Client Studio layout checks. Uses actual rendered geometry and TextFits.
-- 2026-10-09 roster: weapon offers show the specialty bar (SpecBar), one row per type (TypeChip_ /
-- TypeStep_ / TypeLine_) and the stat lines; the stats column has SETS (pinned or a Sets tab).
-- 2026-10-10: BANISH in the header (run it once normally and once in banish mode; it isn't shown
-- where PaidRandomRestricted is set or in the tutorial).
-- 2026-10-16 phones / tablets (ShopUI `compact`): the offers sit in one sideways-scrolling row
-- (ShopMain.Offers, cards and Lock<n> inside it, Buy and Lock side by side at each card's foot),
-- Items and Weapons are one sideways row each, and short (phone) views need no vertical scroll.
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
  -- 2026-10-12 turret combining (own 2+ of a turret to see it): the hint beside the Items title, and
  -- on each turret tile the tier badge, the lime arrow and the count stay apart and inside the tile.
  local hint=left.Items:FindFirstChild('CombineHint')
  if hint then assert(disjoint(hint,left.Items.Title),'combine hint over the Items title') end
  -- Compact rows scroll sideways: their hint may sit past the row's right edge (scrolled away).
  if hint and not left.Items:IsA('ScrollingFrame') then assert(right(hint)<=right(left.Items)+1,'combine hint past the items edge') end
  for _,tile in left.Items:GetChildren() do
   if tile.Name:match('^ItemSlot') then
    local marks={}
    for _,name in {'TierBadge','CombineBadge','Count'} do local m=tile:FindFirstChild(name);if m then table.insert(marks,m) end end
    for i,a in marks do
     assert(a.AbsolutePosition.X>=tile.AbsolutePosition.X-1 and right(a)<=right(tile)+1 and a.AbsolutePosition.Y>=tile.AbsolutePosition.Y-1 and bottom(a)<=bottom(tile)+1,a.Name..' outside its item tile at '..tostring(size))
     for j=i+1,#marks do assert(disjoint(a,marks[j]),a.Name..' overlaps '..marks[j].Name..' at '..tostring(size)) end
    end
   end
  end
  assert(disjoint(left.Reroll,left.Shards) and disjoint(left.Shards,left.ShopTitle),'header overlaps')
  -- 2026-10-10 Shop Banish: BANISH (CANCEL in banish mode) beside the R$ reroll, or on its own row
  -- under the rerolls when the header is too narrow; never over another header piece or an offer.
  local banish=left:FindFirstChild('Banish') or left:FindFirstChild('CancelBanish')
  if banish then
   for _,name in {'ShopTitle','Shards','Reroll','RobuxReroll','RerollOdds','BanishHint','Bag','BagNote'} do
    local other=left:FindFirstChild(name);if other then assert(disjoint(banish,other),'BANISH overlaps '..name..' at '..tostring(size)) end
   end
   for i=1,4 do local card=left:FindFirstChild('Offer'..i,true);if card then assert(disjoint(banish,card),'BANISH overlaps an offer') end end
   assert(right(banish)<=right(left)+1,'BANISH past the shop edge')
  end
  if left:FindFirstChild('RobuxReroll') then assert(disjoint(left.RobuxReroll,left.Reroll),'R$ reroll overlaps REROLL') end
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
   for i=1,4 do local card=left:FindFirstChild('Offer'..i,true);if card then assert(disjoint(note,card),'bag caption overlaps offer') end end
  end
  for _,v in left.Weapons:GetChildren() do
   if v:IsA('ImageButton') then assert(v:FindFirstChild('WeaponIcon') or v:FindFirstChild('WeaponPreview'),'empty weapon box') end
  end
  local strip=left:FindFirstChild('Offers')
  if strip then
   -- One row: every card at the same height inside the sideways strip, 2 px in from its canvas
   -- edges, the strip inside ShopMain; the strip only scrolls sideways.
   assert(strip:IsA('ScrollingFrame') and strip.ScrollingDirection==Enum.ScrollingDirection.X,'offer row does not scroll sideways at '..tostring(size))
   assert(strip.AbsolutePosition.X>=left.AbsolutePosition.X and right(strip)<=right(left)+1,'offer row outside the shop at '..tostring(size))
   local y0
   for _,card in strip:GetChildren() do
    if card.Name:match('^Offer%d$') then
     y0=y0 or card.AbsolutePosition.Y
     assert(math.abs(card.AbsolutePosition.Y-y0)<1,'offers not in one row at '..tostring(size))
     assert(card.Position.X.Offset>=2 and card.Position.X.Offset+card.Size.X.Offset<=strip.CanvasSize.X.Offset-2+1,'card outside the row canvas at '..tostring(size))
     local bar=strip.ScrollBarThickness*strip.AbsoluteSize.Y/strip.Size.Y.Offset -- the bar's screen px
     assert(bottom(card)<=bottom(strip)-bar+1,'card under the row scroll bar at '..tostring(size))
    end
   end
   for _,name in {'Items','Weapons'} do local r=left[name];assert(r:IsA('ScrollingFrame') and r.ScrollingDirection==Enum.ScrollingDirection.X,name..' row does not scroll sideways') end
   -- Short (phone) views: the whole shop fits, or scrolls at most 24 px (2026-10-16, user: "way too
   -- much scrolling"; 812x375 with two-type weapons and a crystal bag scrolls about 22).
   if size.Y<450 then assert(left.AbsoluteCanvasSize.Y<=left.AbsoluteWindowSize.Y+24,string.format('phone shop scrolls %d px at %s',left.AbsoluteCanvasSize.Y-left.AbsoluteWindowSize.Y,tostring(size))) end
  end
  for i=1,4 do
   local card=left:FindFirstChild('Offer'..i,true)
   local lock=left:FindFirstChild('Lock'..i,true)
   if card and strip then
    -- Compact: Lock beside Buy at the card's foot, both clear of its 12 layout px border ring.
    local ring=12*layout.UIScale.Scale-1
    assert(disjoint(card.Buy,lock) and math.abs(lock.AbsolutePosition.Y-card.Buy.AbsolutePosition.Y)<1,'lock not beside Buy at '..tostring(size))
    assert(right(lock)<=right(card)-ring and bottom(lock)<=bottom(card)-ring and bottom(card.Buy)<=bottom(card)-ring,'lock or Buy on the card border at '..tostring(size))
    for _,c in card:GetChildren() do if (c:IsA('TextLabel') and c.Text~='') or c.Name=='SpecBar' or c.Name:match('^TypeChip_') then assert(disjoint(c,lock),'lock over '..c.Name..' at '..tostring(size)) end end
    local tier=card:GetAttribute('Tier') or 1
    assert(card.Image~='' and ((tier>1)==(card:FindFirstChild('RarityCorners')~=nil)),'rarity frame mismatch')
    assert(disjoint(card,left.Items) and disjoint(card,left.Weapons),'offer/inventory overlap')
   elseif card then
    assert(card.AbsolutePosition.X-2>=left.AbsolutePosition.X,'left border clipped')
    assert(right(card)+2<=right(left),'right border clipped')
    -- Green theme: tier II+ cards carry recoloured RarityCorners (T.setTier); common keeps the lime panel.
    local tier=card:GetAttribute('Tier') or 1
    assert(card.Image~='' and ((tier>1)==(card:FindFirstChild('RarityCorners')~=nil)),'rarity frame mismatch')
    assert(disjoint(card,left.Items) and disjoint(card,left.Weapons),'offer/inventory overlap')
    assert(bottom(card.Buy)<=bottom(card)-8,'price overlaps card border')
    assert(disjoint(card,lock),'lock overlaps card border')
   end
   if card then
    for j=i+1,4 do local other=left:FindFirstChild('Offer'..j,true);if other then assert(disjoint(card,other),'offer overlap') end end
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
     -- Compact cards have one chip per type ('GUN 1→2'); the bonus words are on the Sets tab.
     for _,t in w.types do assert(card:FindFirstChild('TypeChip_'..t) and (strip or card:FindFirstChild('TypeLine_'..t)),'type row for '..t..' on '..w.name) end
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
  -- An open turret item detail (select a turret item before running): Combine between the
  -- description and Cancel (2026-10-12).
  if details and not details.Body:FindFirstChild('SpecBar') and details.Body:FindFirstChild('Combine') then
   local body=details.Body
   assert(body.Combine.AbsolutePosition.Y>=bottom(body.Description),'item Combine over the description')
   assert(bottom(body.Combine)<=body.Cancel.AbsolutePosition.Y,'item Combine over Cancel')
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
  -- SETS: pinned rows (desktop, in the Sets list) or the Sets tab's rows (SetRows) sit inside the
  -- stats column, clear of the tabs. 2026-10-16: the lists themselves are clear of the tabs and the
  -- title; rows never overlap each other; each row's lines sit inside it with 4 px to spare.
  local tab=stats:FindFirstChild('PrimaryTab')
  for _,name in {'Sets','SetRows'} do
   local list=stats:FindFirstChild(name)
   if list then
    assert(list.AbsolutePosition.Y>=stats.AbsolutePosition.Y and bottom(list)<=bottom(stats)+1,name..' outside the stats column at '..tostring(size))
    if tab and name=='Sets' then assert(disjoint(list,tab),'set list over the tabs at '..tostring(size)) end
    if stats:FindFirstChild('SetsNote') then assert(disjoint(list,stats.SetsNote) and disjoint(stats.SetsTitle,stats.SetsNote),'set title / hint overlap') end
    local rows={}
    for _,r in list:GetChildren() do if r.Name:match('^Set_') and r:IsA('Frame') then table.insert(rows,r) end end
    for i,r in rows do
     for j=i+1,#rows do assert(disjoint(r,rows[j]),'set rows overlap: '..r.Name..' / '..rows[j].Name..' at '..tostring(size)) end
     for _,c in r:GetChildren() do
      if c:IsA('TextLabel') then assert(c.AbsolutePosition.Y>=r.AbsolutePosition.Y and bottom(c)<=bottom(r)-4 and right(c)<=right(r)-4,c.Name..' touches the edge of '..r.Name..' at '..tostring(size)) end
     end
    end
   end
  end
  -- Owned tiles (2026-10-16): the icon centred in its tile with even gaps, clear of the frame.
  for _,region in {left.Items,left.Weapons} do
   for _,tile in region:GetChildren() do
    local icon=tile:IsA('ImageButton') and (tile:FindFirstChild('Icon') or tile:FindFirstChild('WeaponIcon') or tile:FindFirstChild('WeaponPreview'))
    if icon then
     local l,t=icon.AbsolutePosition.X-tile.AbsolutePosition.X,icon.AbsolutePosition.Y-tile.AbsolutePosition.Y
     local r,b=right(tile)-right(icon),bottom(tile)-bottom(icon)
     assert(math.abs(l-r)<1.5 and math.abs(t-b)<1.5 and math.min(l,t)>=tile.AbsoluteSize.X*.12,'icon not centred in '..tile.Name..' at '..tostring(size))
    end
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
