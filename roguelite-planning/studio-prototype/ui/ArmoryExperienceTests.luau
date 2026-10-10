-- Temporary lobby Play CLIENT module. No remotes, purchases, inventory or persistent writes.
-- Close existing lobby windows first; require a fresh copy. Exercises actual Armory layouts and
-- ItemCardUI at desktop/phone sizes, plus geometric starter clearance at every turntable angle.
-- 2026-10-09 roster: class groups (your class, then class order), the weapon card's type chips and
-- STARTER CLASS / ATTACK / SPECIALTY rows, the class details' specialty and ability rows, and the
-- item card's TYPES section (no class fit anywhere).
local RS=game:GetService('ReplicatedStorage')
local player=game.Players.LocalPlayer
local Armory=require(RS.ArmoryUI)
local Stage=require(RS.ArmoryStage)
local Lobby=require(RS.LobbyUI)
local Rules=require(RS.RunSetupRules)
local Weapons=require(RS.RogueliteCombat.WeaponCatalog)
local Stats=require(RS.RogueliteCombat.CharacterStats)
local profile=Lobby.profile(player)
local ui=Armory.new(player,{profile=function() return profile end,need=Lobby.need,
 selection={class=player:GetAttribute('LoadoutClass') or 'Brawler',weapon=player:GetAttribute('LoadoutWeapon') or '01'},
 openWindow=function() end,chooseClass=function() end})
local assertions=0
local function check(ok,message) assertions+=1;assert(ok,message) end
local function hasText(root,text)
 for _,d in root:GetDescendants() do if d:IsA('TextLabel') and d.Text==text then return true end end
 return false
end
local ok,err=xpcall(function()
 for _,body in {Vector3.new(4,5.5,2),Vector3.new(5,6.5,3),Vector3.new(2.5,4,1.5)} do
  for _,weapon in {Vector3.new(.7,1.2,1.7),Vector3.new(.4,2.9,.25),Vector3.new(1.7,1,.5)} do
   for degrees=0,355,5 do
    local yaw=math.rad(degrees);local centre=Vector3.new(.15,body.Y/2,.1)
    local pose=Stage.StarterPose(weapon,body,centre,yaw,degrees/7)
    local half=Stage.ProjectedHalf(weapon,pose.Rotation)
    local turn=CFrame.Angles(0,yaw,0)
    local bodyHalf=Stage.ProjectedHalf(body,turn)
    local left=turn:VectorToWorldSpace(centre).X-bodyHalf.X
    check(pose.Position.X+half.X<=left-.44,'starter clears body silhouette at '..degrees)
    check(pose.Position.Y-half.Y>.1,'starter stays above floor')
   end
  end
 end
 for _,size in {Vector2.new(1920,1080),Vector2.new(1366,768),Vector2.new(750,369)} do
  local win=ui.Open('Weapons');win.Root.Size=UDim2.fromOffset(size.X,size.Y);task.wait(.2)
  local grid=win.Root:FindFirstChild('Grid',true);local count=0
  for _,w in Weapons.List do
   local tile=grid:FindFirstChild('W_'..w.id)
   check(tile~=nil,'all weapons browsable: '..w.id)
   check(tile:FindFirstChild('Info')~=nil,'weapon info affordance: '..w.id)
   count+=1
  end
  check(count==#Weapons.List,'whole catalog shown')
  -- Read the actual rendered grid, not a second copy of the class ordering algorithm.
  local tiles={}
  for _,tile in grid:GetChildren() do if tile.Name:match('^W_') then table.insert(tiles,tile) end end
  table.sort(tiles,function(a,b)
   if a.Position.Y.Offset~=b.Position.Y.Offset then return a.Position.Y.Offset<b.Position.Y.Offset end
   return a.Position.X.Offset<b.Position.X.Offset
  end)
  local browser=ui.ShowInfo(tiles[1].Name:sub(3))
  for i,tile in tiles do
   check(browser.Id()==tile.Name:sub(3),'info arrow follows rendered grid at '..i)
   -- The footer is Card.Count. Copies.Count inside the upgrade-progress bar is legitimate.
   local panel=browser.Root:FindFirstChild('Card')
   check(panel~=nil and panel:FindFirstChild('Count')==nil,'collection omits rarity-relative footer count')
   check(browser.Root:FindFirstChild('Rarity',true)~=nil,'rarity badge stays visible')
   browser.Step(1)
  end
  check(browser.Id()==tiles[1].Name:sub(3),'forward wraps to first visible tile')
  browser.Step(-1)
  check(browser.Id()==tiles[#tiles].Name:sub(3),'backward wraps to last visible tile')
  browser.Close(true)
  -- Class groups: your class first, then the rest in class order; each weapon under its one class.
  local class=player:GetAttribute('LoadoutClass') or 'Brawler'
  if not profile.classes[class] then class='Brawler' end
  local want={class};for _,c in Stats.ClassOrder do if c~=class then table.insert(want,c) end end
  local lastY=-1
  for _,c in want do
   local h=grid:FindFirstChild('Header_'..c);check(h~=nil,'class group header '..c)
   check(h.Position.Y.Offset>lastY,'class groups follow class order: '..c);lastY=h.Position.Y.Offset
  end
  check(grid:FindFirstChild('Header_'..class..'Note')~=nil,'your class says what the specialty gives')
  -- The weapon card: type chips (literal icons) and the three rows.
  local info=win.Root:FindFirstChild('WeaponInfo',true);check(info~=nil,'weapon info rows')
  for _,name in {'StarterLabel','AttackText','SpecialtyText','ClassChip'} do check(info:FindFirstChild(name)~=nil,'weapon row '..name) end
  local shown=Weapons.ById[info.ClassChip:GetAttribute('WeaponId')]
  local types=win.Root:FindFirstChild('Types',true)
  for _,t in shown.types do check(types:FindFirstChild('Type_'..t)~=nil and types['Type_'..t]:FindFirstChild('Icon')~=nil,'type chip with icon '..t) end
  check(info.SpecialtyText.TextFits and info.AttackText.TextFits,'weapon rows fit')
  check(win.Root:FindFirstChild('WatchAttacks',true)~=nil,'attack preview entry')
  check(win.Root:FindFirstChild('Journal',true)~=nil,'journal entry')
  ui.ShowInfo('18');task.wait(.1)
  local card=win.Root:FindFirstChild('ItemCard',true)
  check(card~=nil,'shared weapon card opens')
  check(card:FindFirstChild('CollectionSource',true)~=nil and card:FindFirstChild('Chance',true)==nil,'collection has no invented chest odds')
  check(hasText(card,Weapons.legendaryText('18')),'Tier IV move uses catalog description')
  check(card:FindFirstChild('TypesTitle',true)~=nil and card:FindFirstChild('WeaponFit',true)==nil,'item card shows types, not class fit')
  ui.Close()
  win=ui.Open('Classes');win.Root.Size=UDim2.fromOffset(size.X,size.Y);task.wait(.2)
  for _,class in Rules.classOrder(profile.classes) do
   check(win.Root:FindFirstChild('Class_'..class,true)~=nil,'class browsable: '..class)
  end
  check(win.Root:FindFirstChild('ChangeClass',true)~=nil,'saved class chooser reachable')
  check(win.Root:FindFirstChild('Perks',true)~=nil and win.Root:FindFirstChild('HomeBonus',true)==nil and win.Root:FindFirstChild('FitTitle',true)==nil,'class details: specialty and ability rows')
  ui.Close()
 end
end,debug.traceback)
pcall(ui.Close);ui.Screen:Destroy()
return {passed=ok,assertions=assertions,error=ok and '' or err}
