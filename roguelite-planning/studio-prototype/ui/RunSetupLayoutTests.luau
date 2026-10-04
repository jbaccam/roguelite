-- Client Studio layout check for the run setup's STARTING WEAPON tiles (2026-10-04: multi-class
-- weapons, then the user's "I don't like scrolling, it should be just smaller boxes"). Run on the
-- lobby client in Play, like ShopLayoutTests. It builds its own RunSetupUI with a fake Thrower
-- profile, opens the class step (Loadout mode) and resizes its root through desktop, tablet and
-- phone sizes (phone sizes as safe areas: an 844x390 iPhone 14 is 750x369). Nothing is sent to the
-- server: CONFIRM is never pressed. Two profiles: 11 Thrower weapons (8 owned, 3 not) plus the 6
-- Godlies owned (17 tiles), then the same without Godlies (11 tiles, NOT OWNED in smaller rows).
-- Checks: no scrolling anywhere around the tiles, every tile inside the tile area and the screen,
-- no tile overlaps another or the class cards, details, heading or CLOSE / CONFIRM, every icon at
-- least 48 screen px, owned -> Godlies -> NOT OWNED order, the pick lime and named, text fits.
local RS=game.ReplicatedStorage
local player=game.Players.LocalPlayer
assert(workspace:FindFirstChild('RogueliteLobby') and workspace.RogueliteLobby:FindFirstChild('RunSetup'),'run this in the lobby')
local RunSetup=require(RS:WaitForChild('RunSetupUI'))
local Rules=require(RS:WaitForChild('RunSetupRules'))
local CLASS='Thrower'
local UNOWNED={['04']=true,['15']=true,['18']=true} -- Kusarigama, Egg, Deck of Cards: catalog order puts one first
local PICK='31' -- Mjolnir (Mage, Thrower), the last owned class weapon
local GODLIES={'36','37','38','39','40','41'}
local classList=Rules.classWeapons(CLASS)
local function makeProfile(withGodlies)
 local weapons={}
 for _,w in classList do if not UNOWNED[w.id] then weapons[w.id]={id=w.id,tier=w.id=='13' and 3 or 1,have=1} end end
 if withGodlies then for _,id in GODLIES do weapons[id]={id=id,tier=1,have=0} end end
 return {classes={Brawler=true,Gunner=true,Mage=true,Thrower=true},weapons=weapons,wins={},best={},gems=0}
end
-- The order the tiles must read in: owned class weapons, owned Godlies, NOT OWNED (catalog order each).
local function expected(withGodlies)
 local out={}
 for _,w in classList do if not UNOWNED[w.id] then table.insert(out,w.id) end end
 if withGodlies then for _,id in GODLIES do table.insert(out,id) end end
 for _,w in classList do if UNOWNED[w.id] then table.insert(out,w.id) end end
 return out
end
local profile=makeProfile(true)
local sel={map=1,class=CLASS,weapon=PICK,difficulty='Normal'}
local ui=RunSetup.new(player,{profile=function() return profile end,need=function() return 2 end,cost=function() end,
 selection=sel,findPortal=function() end,hostMap=function() end})
local results={}
local function right(g) return g.AbsolutePosition.X+g.AbsoluteSize.X end
local function bottom(g) return g.AbsolutePosition.Y+g.AbsoluteSize.Y end
local function disjoint(a,b)
 return right(a)<=b.AbsolutePosition.X+1 or right(b)<=a.AbsolutePosition.X+1 or bottom(a)<=b.AbsolutePosition.Y+1 or bottom(b)<=a.AbsolutePosition.Y+1
end
local function inside(g,box)
 return g.AbsolutePosition.X>=box.AbsolutePosition.X-1 and right(g)<=right(box)+1 and g.AbsolutePosition.Y>=box.AbsolutePosition.Y-1 and bottom(g)<=bottom(box)+1
end
local function textFits(parent,at)
 for _,l in parent:GetDescendants() do if l:IsA('TextLabel') and l.Visible and l.Text~='' then assert(l.TextFits,'text overflow '..l:GetFullName()..at) end end
end
local SIZES={Vector2.new(2560,1440),Vector2.new(1920,1080),Vector2.new(1366,768),Vector2.new(1280,720),Vector2.new(1024,768),Vector2.new(1180,820),Vector2.new(844,390),Vector2.new(750,369),Vector2.new(667,375),Vector2.new(800,360)}
local ok,err=xpcall(function()
 assert(#classList==11,'Thrower lists 11 weapons: '..#classList)
 ui.Open('Loadout')
 local root=ui.Screen:WaitForChild('Root')
 for _,withGodlies in {true,false} do
  profile=makeProfile(withGodlies);ui.Refresh()
  local want=expected(withGodlies)
  for _,size in SIZES do
   root.Size=UDim2.fromOffset(size.X,size.Y);task.wait(.2)
   local at=' at '..tostring(size)..(withGodlies and ' (17 tiles)' or ' (11 tiles)')
   local grid=root:FindFirstChild('Weapons',true);assert(grid,'no weapon tiles'..at)
   -- Never scrolls: the tile area is a plain frame, with no scroll inside it or around it.
   assert(not grid:IsA('ScrollingFrame') and grid:FindFirstAncestorWhichIsA('ScrollingFrame')==nil,'tiles must not scroll'..at)
   for _,d in grid:GetDescendants() do assert(not d:IsA('ScrollingFrame'),'a scroll inside the tiles'..at) end
   assert(inside(grid,root),'tile area on screen'..at)
   local tiles={}
   for _,c in grid:GetChildren() do if c:IsA('GuiButton') and c.Name:match('^Weapon_') then table.insert(tiles,c) end end
   assert(#tiles==#want,#want..' tiles, got '..#tiles..at)
   table.sort(tiles,function(a,b)
    if math.abs(a.AbsolutePosition.Y-b.AbsolutePosition.Y)>1 then return a.AbsolutePosition.Y<b.AbsolutePosition.Y end
    return a.AbsolutePosition.X<b.AbsolutePosition.X
   end)
   for i,c in tiles do
    local id=c.Name:sub(8)
    assert(id==want[i],'reading order: tile '..i..' is '..id..', want '..tostring(want[i])..at)
    assert(c:GetAttribute('Owned')==(not UNOWNED[id]),'owned state '..id..at)
    assert(inside(c,grid),'tile inside the tile area '..id..at)
    for j=i+1,#tiles do assert(disjoint(c,tiles[j]),'tiles overlap '..id..' / '..tiles[j].Name..at) end
    local icon=c:FindFirstChild('Icon');assert(icon,'tile icon '..id..at)
    assert(icon.AbsoluteSize.X>=47.9 and icon.AbsoluteSize.Y>=47.9,string.format('icon %s is %.1f px%s',id,icon.AbsoluteSize.X,at))
    if UNOWNED[id] then assert(c:FindFirstChild('Lock'),'NOT OWNED tile has a padlock '..id..at) end
    -- The pick is the lime (non-neutral) tile; every other owned tile is the plain panel.
    if not UNOWNED[id] then assert((c:GetAttribute('Neutral')==false)==(id==PICK),'only the pick is lime '..id..at) end
   end
   -- Clear of everything else on the class step.
   local others={}
   for _,name in {'ClassInfo','Back','Primary','WeaponTitle','WeaponName','Step'} do local o=root:FindFirstChild(name,true);if o then table.insert(others,o) end end
   for _,d in root:GetDescendants() do if d:IsA('GuiButton') and d.Name:match('^Class_') then table.insert(others,d) end end
   for _,o in others do assert(disjoint(grid,o),'tile area overlaps '..o.Name..at) end
   local info=root:FindFirstChild('ClassInfo',true)
   for _,name in {'WeaponTitle','WeaponName'} do
    local l=root:FindFirstChild(name,true);assert(l and disjoint(l,info),name..' clear of the details'..at)
    for _,o in others do if o:IsA('GuiButton') then assert(disjoint(l,o),name..' overlaps '..o.Name..at) end end
   end
   for _,o in others do if o.Name:match('^Class_') then assert(disjoint(o,info) and inside(o,root),'class card placement '..o.Name..at) end end
   -- The pick's name beside the heading (a tile under a resting mouse may show its own name instead).
   local nameL=root:FindFirstChild('WeaponName',true);assert(nameL.Text~='','a weapon is named beside the heading'..at)
   textFits(grid,at)
   for _,name in {'WeaponTitle','WeaponName'} do local l=root:FindFirstChild(name,true);assert(l.TextFits,'text overflow '..name..at) end
   for _,o in others do if o.Name:match('^Class_') then textFits(o,at) end end
   table.insert(results,tostring(size)..(withGodlies and ' x17' or ' x11'))
  end
 end
end,debug.traceback)
pcall(ui.Close);pcall(function() ui.Screen:Destroy() end)
return {passed=ok,error=ok and '' or err,resolutions=results}
