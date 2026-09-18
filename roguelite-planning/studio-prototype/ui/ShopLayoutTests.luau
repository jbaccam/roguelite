-- Client Studio check against rendered AbsolutePosition/AbsoluteSize, not mirrored layout math.
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
 for _,size in {Vector2.new(1920,1080),Vector2.new(1440,900),Vector2.new(1280,720),Vector2.new(1024,768),Vector2.new(800,600),Vector2.new(640,360),Vector2.new(390,844)} do
  root.Size=UDim2.fromOffset(size.X,size.Y);task.wait(.15)
  local menus=root.Menus;local content=menus.Content;local layout=content.Canvas.ShopLayout
  local left=layout.ShopMain;local stats=layout.StatsColumn
  assert(right(left)<stats.AbsolutePosition.X,'left/right gutter '..tostring(size))
  assert(right(stats)<=right(content)+1,'stats exceeds content')
  assert(bottom(stats)<layout.StartWave.AbsolutePosition.Y,'stats/start gutter')
  assert(stats:FindFirstChild('StatRows') and not stats:FindFirstChild('StatScroll'),'stats have no scroll')
  assert(left.Weapons:FindFirstChild('WeaponSlot6') and not left.Weapons:FindFirstChild('WeaponSlot7'),'six slots')
  assert(math.abs(left.Weapons.WeaponSlot1.AbsolutePosition.Y-left.Weapons.WeaponSlot3.AbsolutePosition.Y)<1,'three columns')
  assert(left.Weapons.WeaponSlot4.AbsolutePosition.Y>left.Weapons.WeaponSlot3.AbsolutePosition.Y,'two rows')
  assert(bottom(content)<=menus.Status.AbsolutePosition.Y+1,'status overlaps content')
  assert(bottom(menus.Status)<=menus.Footer.AbsolutePosition.Y+1,'footer overlaps status')
  assert(disjoint(left.Items,left.Weapons),'items/weapons overlap')
  assert(disjoint(left.Weapons,layout.StartWave),'weapon/start overlap')
  assert(disjoint(left.Items,layout.StartWave),'items/start overlap')
  for i=1,4 do
   local card=left['Offer'..i]
   assert(right(card)<=right(left)+1,'card outside left region')
   assert(disjoint(card,left.Items) and disjoint(card,left.Weapons),'offer/loadout overlap')
   assert(disjoint(card.Buy,card.Lock),'buy/lock overlap')
   for j=i+1,4 do assert(disjoint(card,left['Offer'..j]),'offer overlap') end
  end
  table.insert(results,tostring(size))
 end
end,debug.traceback)
root.Size=original
return {passed=ok,error=ok and '' or err,resolutions=results}
