-- Client Studio layout check for the run setup's class step (2026-10-09 roster: one starter class
-- per weapon, Chef, specialty and ability rows; tiles from RunSetupRules.starters). Run on the
-- lobby client in Play, like ShopLayoutTests. It builds its own RunSetupUI with a fake Chef
-- profile, opens the class step (Loadout mode) and resizes its root through desktop, tablet and
-- phone sizes (phone sizes as safe areas: an 844x390 iPhone 14 is 750x369). Nothing is sent to the
-- server: CONFIRM is never pressed. Two profiles: 6 Chef weapons (4 owned, 2 not) plus the 6
-- Godlies owned (12 tiles), then the same without Godlies (6 tiles, all entries sharing one size).
-- Checks: no scrolling anywhere around the tiles, every tile inside the tile area and the screen,
-- no tile overlaps another or the class cards, details, heading, Godly note or CLOSE / CONFIRM,
-- every icon at least 48 screen px, starters -> NOT OWNED order, the pick lime and named, class
-- cards in class order with no damage badges, the specialty and ability rows, text fits.
local RS=game.ReplicatedStorage
local player=game.Players.LocalPlayer
assert(workspace:FindFirstChild('RogueliteLobby') and workspace.RogueliteLobby:FindFirstChild('RunSetup'),'run this in the lobby')
local RunSetup=require(RS:WaitForChild('RunSetupUI'))
local Rules=require(RS:WaitForChild('RunSetupRules'))
local Stats=require(RS.RogueliteCombat.CharacterStats)
local Weapons=require(RS.RogueliteCombat.WeaponCatalog)
local CLASS='Chef'
local UNOWNED={['01']=true,['14']=true} -- Frying Pan (the signature, so the pick falls back) and Molotov
local PICK='15' -- Egg
local GODLIES={'36','37','38','39','40','41'}
local classList=Rules.classWeapons(CLASS)
local function makeProfile(withGodlies)
 local weapons={}
 for _,w in classList do if not UNOWNED[w.id] then weapons[w.id]={id=w.id,tier=w.id=='13' and 3 or 1,have=1} end end
 if withGodlies then for _,id in GODLIES do weapons[id]={id=id,tier=1,have=0} end end
 return {classes={Brawler=true,Gunner=true,Mage=true,Chef=true},weapons=weapons,wins={},best={},gems=0}
end
-- The order the tiles must read in: RunSetupRules.starters (owned class weapons, owned Godlies),
-- then the class's NOT OWNED weapons (catalog order each).
local function expected(withGodlies)
 local out={}
 for _,w in Rules.starters(CLASS,makeProfile(withGodlies).weapons) do table.insert(out,w.id) end
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
 assert(#classList==6,'Chef lists 6 weapons: '..#classList)
 local pizza=RS.RogueliteCombat:FindFirstChild('ChefPizza')
 if pizza then RunSetup.Pizza=require(pizza) end
 ui.Open('Loadout')
 local root=ui.Screen:WaitForChild('Root')
 for _,withGodlies in {true,false} do
  profile=makeProfile(withGodlies);ui.Refresh()
  local want=expected(withGodlies)
  for _,size in SIZES do
   root.Size=UDim2.fromOffset(size.X,size.Y);task.wait(.2)
   local at=' at '..tostring(size)..(withGodlies and ' (12 tiles)' or ' (6 tiles)')
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
    assert((c.AbsoluteSize-tiles[1].AbsoluteSize).Magnitude<1,'owned and locked tiles use one size'..at)
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
   for _,name in {'ClassInfo','Back','Primary','WeaponTitle','WeaponName','Step','GodlyNote'} do local o=root:FindFirstChild(name,true);if o then table.insert(others,o) end end
   for _,d in root:GetDescendants() do if d:IsA('GuiButton') and d.Name:match('^Class_') then table.insert(others,d) end end
   for _,o in others do assert(disjoint(grid,o),'tile area overlaps '..o.Name..at) end
   local info=root:FindFirstChild('ClassInfo',true)
   -- Specialty and ability rows (they replaced the class fit chips and the 2 / 4 home rows).
   assert(info:FindFirstChild('Fit_Brawler',true)==nil and info:FindFirstChild('HomeBonus',true)==nil,'no class fit or home rows'..at)
   local spec=info:FindFirstChild('SpecialtyText',true)
   assert(spec and spec.ContentText:find(Stats.specialtyText(CLASS),1,true) and spec.TextFits,'specialty line from CharacterStats fits'..at)
   local ability=info:FindFirstChild('AbilityText',true)
   assert(ability and ability:GetAttribute('Dash')==Stats.dashes(CLASS) and ability.TextFits,'ability row fits'..at)
   assert(ability.ContentText==RunSetup.ability(CLASS).text,'Chef ability is pizza drops'..at)
   -- Class cards: class order, no damage badges.
   local cx=-1
   for _,c in Stats.ClassOrder do
    local card=root:FindFirstChild('Class_'..c,true);assert(card,'class card '..c..at)
    assert(card.AbsolutePosition.X>cx,'class cards follow class order '..c..at);cx=card.AbsolutePosition.X
    assert(card:FindFirstChild('Fit')==nil,'no damage badge on '..c..at)
   end
   local note=root:FindFirstChild('GodlyNote',true);assert(note and note.TextFits and inside(note,root),'Godly note fits'..at)
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
 -- Sparse ownership is the reported regression: one pan must be in the same row as locked
 -- Brawler weapons, and switching classes must not change the tile size for the same count.
 for _,class in {'Brawler','Gunner','Mage','Handyman'} do
  local id=Rules.Signature[class]
  profile={classes={[class]=true,Brawler=true},weapons={[id]={id=id,tier=1,have=1}},wins={},best={},gems=0}
  sel.class=class;sel.weapon=id;ui.Refresh()
  for _,size in SIZES do
   root.Size=UDim2.fromOffset(size.X,size.Y);task.wait(.15)
   local at=' sparse '..class..' at '..tostring(size)
   local grid=root:FindFirstChild('Weapons',true);local tiles={}
   for _,c in grid:GetChildren() do if c:IsA('GuiButton') and c.Name:match('^Weapon_') then table.insert(tiles,c) end end
   assert(#tiles==#Rules.classWeapons(class),'every class starter is shown'..at)
   local ownedTile=grid:FindFirstChild('Weapon_'..id);local neighbour=false
   for _,c in tiles do
    assert((c.AbsoluteSize-ownedTile.AbsoluteSize).Magnitude<1,'uniform footprint'..at)
    assert(inside(c,grid),'starter inside grid'..at)
    if c~=ownedTile and math.abs(c.AbsolutePosition.Y-ownedTile.AbsolutePosition.Y)<1 then neighbour=true end
   end
   assert(neighbour,'owned starter shares its first row with locked starters'..at)
   table.insert(results,tostring(size)..' sparse '..class)
  end
 end
 -- Chef's pizza line reads ChefPizza's numbers: '8% chance (about 1 in 12) on a kill with a Chef
 -- weapon; heals 10% of max health'.
 if RunSetup.Pizza then
  local P=RunSetup.Pizza
  local function num(x) return (string.format('%.1f',x):gsub('%.0$','')) end
  local want=string.format('%s%% chance (about 1 in %d) on a kill with a Chef weapon; heals %s%% of max health',num(P.CHANCE*100),math.floor(1/P.CHANCE+1e-6),num(P.HEAL_FRACTION*100))
  assert(RunSetup.ability('Chef').text==want,'pizza line uses ChefPizza numbers: '..RunSetup.ability('Chef').text)
 end
 -- The explanation follows the gameplay eligibility helper for every class/weapon combination.
 for _,class in Stats.ClassOrder do
  for _,weapon in Weapons.List do
   local enabled,description=RunSetup.dashDescription(class,weapon)
   assert(enabled==(class=='Brawler'),'class-only dash eligibility '..class..' '..weapon.id)
   assert(not string.find(description,'nil',1,true),'dash explanation contains no missing settings')
   if enabled then assert(string.find(description,'Q / controller X / DASH button',1,true),'enabled dash shows all input hints')
   else assert(string.find(description,'NO DASH - Brawler class ability only',1,true),'unavailable dash is explicit') end
  end
 end
end,debug.traceback)
pcall(ui.Close);pcall(function() ui.Screen:Destroy() end)
return {passed=ok,error=ok and '' or err,resolutions=results}
