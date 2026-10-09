-- Chef pizza slices on this screen (rules: RogueliteCombat.ChefPizza). The server keeps them in
-- workspace.RogueliteHeartDrops with Kind 'Pizza' (HeartDropService variant); HeartVisuals skips
-- those and still shows the "+N HP" pop when one heals you, and RogueliteSounds plays the bite.
-- Presentation only: never requests pickups or healing.
-- Model: ReplicatedStorage.RogueliteCombat.PickupTemplates.PizzaSlice (a Model or a MeshPart),
-- authored lying flat, toppings up (+Y). It is scaled to ChefPizza.WIDTH studs across and spun
-- about its middle. Until it is imported, the heart pickup model stands in.
-- Look: the slice bobs and spins, tilted so the toppings read; under it a flat painted glow and
-- ring on the ground (decals, no shaded effect meshes). It blinks through its last 3 s.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Rules=require(combat:WaitForChild('ChefPizza'))
local Motion=require(combat:WaitForChild('ShardMotion'))
local HeartVisual=require(combat:WaitForChild('HeartPickupVisual'))
local drops=workspace:WaitForChild('RogueliteHeartDrops')
local folder=Instance.new('Folder');folder.Name='LocalPizzaVisuals';folder.Parent=workspace
-- Painted textures already in the game (GodlyVisuals / LegendaryVisuals TEX).
local GLOW,RING='rbxassetid://119796255132573','rbxassetid://73745779894728'
local CHEESE,TOMATO=Color3.fromRGB(255,206,84),Color3.fromRGB(255,112,52)
local HOVER=1.6 -- HeartDropService puts Origin 1.6 studs above the ground it hit
local TILT=CFrame.Angles(math.rad(Rules.TILT),0,0)

local function quiet(m)
 for _,d in m:GetDescendants() do
  if d:IsA('BasePart') then d.Anchored=true;d.CanCollide=false;d.CanTouch=false;d.CanQuery=false;d.CastShadow=false
  elseif d:IsA('BaseScript') then d:Destroy() end
 end
end
-- The prepared template (built once; rebuilt once the real model shows up after the stand-in).
local cached,cachedReal
local function template()
 local templates=combat:FindFirstChild('PickupTemplates')
 local source=templates and templates:FindFirstChild('PizzaSlice')
 if cached and (cachedReal or not source) then return cached,cachedReal end
 local m
 if source and source:IsA('Model') then m=source:Clone()
 elseif source and source:IsA('BasePart') then m=Instance.new('Model');local p=source:Clone();p.Parent=m;m.PrimaryPart=p end
 if m then
  m.Name='PizzaSlice';quiet(m)
  local _,size=m:GetBoundingBox();local big=math.max(size.X,size.Y,size.Z)
  if big>0 then pcall(function() m:ScaleTo(m:GetScale()*Rules.WIDTH/big) end) end
  m.WorldPivot=(m:GetBoundingBox()) -- spin about its middle
  if cached then cached:Destroy() end
  cached,cachedReal=m,true
 else
  cached,cachedReal=HeartVisual.create(nil,'PizzaSlice',1.8),false
 end
 return cached,cachedReal
end
-- A flat disc lying on the ground with a painted texture on top (GodlyVisuals' shockwave disc).
local function disc(name,texture,color,diameter,alpha)
 local p=Instance.new('Part');p.Name=name;p.Shape=Enum.PartType.Cylinder;p.Size=Vector3.new(.05,diameter,diameter)
 p.Transparency=1;p.Anchored=true;p.CanCollide=false;p.CanTouch=false;p.CanQuery=false;p.CastShadow=false
 local d=Instance.new('Decal');d.Texture=texture;d.Color3=color;d.Transparency=alpha;d.Face=Enum.NormalId.Right;d.Parent=p
 p.Parent=folder
 return p,d
end

local views={}
local function track(m)
 if views[m] or not m:IsA('Model') or m:GetAttribute('Kind')~='Pizza' then return end
 local t,real=template()
 local model=t:Clone();model.Parent=folder
 local glow,glowDecal=disc('PizzaGlow',GLOW,CHEESE,4.2,.45)
 local ring,ringDecal=disc('PizzaRing',RING,TOMATO,3.2,.15)
 views[m]={model=model,real=real,glow=glow,ring=ring,decals={glowDecal,ringDecal},alpha={.45,.15}}
end
local function untrack(m)
 local v=views[m];views[m]=nil
 if v then v.model:Destroy();v.glow:Destroy();v.ring:Destroy() end
end
drops.ChildAdded:Connect(track)
drops.ChildRemoved:Connect(untrack)
for _,m in drops:GetChildren() do track(m) end

local UP=CFrame.Angles(0,0,math.pi/2) -- the disc's top face (Right) points up
RunService.RenderStepped:Connect(function()
 local now=workspace:GetServerTimeNow()
 for m,v in views do
  local origin=m:GetAttribute('Origin')
  if typeof(origin)~='Vector3' then continue end
  local born=m:GetAttribute('BornAt') or now
  local bob,spin=Rules.pose(born,now)
  local pos=origin+Vector3.new(0,bob,0)
  local start=m:GetAttribute('MagnetStart')
  local id=m:GetAttribute('MagnetUserId')
  local p=id and Players:GetPlayerByUserId(id)
  local r=p and p.Character and p.Character:FindFirstChild('HumanoidRootPart')
  if r and start then
   -- Fly from where it was bobbing when the pull began (no snap), like the hearts.
   local bobAt=Rules.pose(born,start)
   pos=Motion.pull(origin+Vector3.new(0,bobAt,0),r.Position,now-start)
  end
  v.model:PivotTo(CFrame.new(pos)*CFrame.Angles(0,spin,0)*(v.real and TILT or CFrame.identity))
  local floor=origin-Vector3.new(0,HOVER-.06,0)
  v.glow.CFrame=CFrame.new(floor)*UP
  v.ring.CFrame=CFrame.new(floor+Vector3.new(0,.02,0))*CFrame.Angles(0,-spin*.5,0)*UP
  local hidden=Rules.hidden(now,m:GetAttribute('ExpiresAt') or math.huge,start~=nil)
  local groundOff=hidden or start~=nil -- the ground marks go as soon as it flies to someone
  if v.hidden~=hidden or v.groundOff~=groundOff then
   v.hidden,v.groundOff=hidden,groundOff
   -- (a part's decals follow its LocalTransparencyModifier)
   for _,d in v.model:GetDescendants() do if d:IsA('BasePart') then d.LocalTransparencyModifier=hidden and 1 or 0 end end
   for i,d in v.decals do d.Transparency=groundOff and 1 or v.alpha[i] end
  end
 end
end)
