-- Curated sprites from the user's sheets. White rays and red droplets have
-- separate motion/lifetimes; the effect is not a mixed confetti emitter.
local RunService=game:GetService('RunService')
local ContentProvider=game:GetService('ContentProvider')
local V={}
local WHITE='rbxassetid://90006993019437'
local RED='rbxassetid://106280569442353'
local atlasScale=1024/1254
local whites={
 {30,542,94,75,143.624},
 {794,1094,41,115,94.212},
 {714,1079,44,144,88.304},
}
local reds={{47,57,91,88},{542,78,62,62},{885,68,75,73},{835,182,169,156}}
local TAU=math.pi*2
local span=8
local hitBudget,deathBudget=20,28

function V.mount(visuals)
 local active={};local rng=Random.new()
 local lastHit=setmetatable({},{__mode='k'})
 task.spawn(function() pcall(function() ContentProvider:PreloadAsync({WHITE,RED}) end) end)

 -- Finished bursts are kept and reused, sprites and all: a burst was a part, a BillboardGui and
 -- up to 19 ImageLabels built and destroyed per hit or death. At most the two budgets are kept.
 local spare={}
 local function remove(index)
  local e=table.remove(active,index)
  e.gui.Enabled=false
  for _,p in e.particles do p.picture.Visible=false end
  if #spare<hitBudget+deathBudget then table.insert(spare,e) else e.anchor:Destroy() end
 end
 local function create(position,death,npc)
  local camera=workspace.CurrentCamera
  if not camera or (position-camera.CFrame.Position).Magnitude>120 then return end
  -- Separate budgets: a busy death burst cannot suppress surviving-hit feedback.
  local count,oldest=0,nil
  for i,e in active do
   if e.death==death then count+=1;oldest=oldest or i end
  end
  if count>=(death and deathBudget or hitBudget) then remove(oldest) end
  local old=table.remove(spare)
  local anchor,gui,pictures
  if old then anchor,gui,pictures=old.anchor,old.gui,old.pictures
  else
   anchor=Instance.new('Part');anchor.Size=Vector3.one*.05;anchor.Transparency=1;anchor.Anchored=true
   anchor.CanCollide=false;anchor.CanTouch=false;anchor.CanQuery=false;anchor.CastShadow=false
   gui=Instance.new('BillboardGui');gui.Name='RadialSprites';gui.Adornee=anchor
   gui.AlwaysOnTop=false;gui.LightInfluence=0;gui.MaxDistance=120
   gui.Size=UDim2.fromOffset(1,1);gui.ClipsDescendants=false;gui.Parent=anchor
   pictures={}
  end
  anchor.Name=death and 'MobDeathBurst' or 'MobHitBurst'
  anchor.Position=position+Vector3.yAxis*.35;anchor.Parent=visuals;gui.Enabled=true
  local e={anchor=anchor,gui=gui,pictures=pictures,born=os.clock(),particles={},duration=0,death=death,position=anchor.Position}
  if not death and npc and npc.Parent then
   local root=npc:FindFirstChild('HumanoidRootPart')
   if root then
    local bounds,size=npc:GetBoundingBox()
    e.root=root;e.localPosition=root.CFrame:PointToObjectSpace(e.position)
    e.boundsOffset=root.CFrame:ToObjectSpace(bounds);e.boundsSize=size
   end
  end
  table.insert(active,e)
  return e
 end
 local function particle(e,white,angle,r0,r1,length,delay,lifetime,irregular)
  local rect=white and whites[rng:NextInteger(1,#whites)]
   or reds[irregular and 4 or rng:NextInteger(1,3)]
  -- This burst's next kept sprite, or a new one. Every property set below is reset on reuse.
  local picture=e.pictures[#e.particles+1]
  if not picture then
   picture=Instance.new('ImageLabel');picture.BackgroundTransparency=1;picture.AnchorPoint=Vector2.new(.5,.5)
   picture.ScaleType=Enum.ScaleType.Fit;e.pictures[#e.particles+1]=picture
  end
  picture.Name=white and 'OutwardStreak' or 'RoundSplat'
  picture.Image=white and WHITE or RED;picture.ImageTransparency=0
  picture.ImageRectOffset=Vector2.new(math.round(rect[1]*atlasScale),math.round(rect[2]*atlasScale))
  picture.ImageRectSize=Vector2.new(math.round(rect[3]*atlasScale),math.round(rect[4]*atlasScale))
  picture.ImageColor3=white and Color3.new(1,1,1) or Color3.fromRGB(205,210,210)
  picture.ZIndex=white and 2 or 1;picture.Visible=false;picture.Parent=e.gui
  local p={picture=picture,white=white,dir=Vector2.new(math.cos(angle),math.sin(angle)),
   r0=r0,r1=r1,length=length,delay=delay,lifetime=lifetime,
   aspect=Vector2.new(rect[3],rect[4])/math.max(rect[3],rect[4]),
   rotation=white and math.deg(angle)-rect[5] or rng:NextNumber(-180,180)}
  table.insert(e.particles,p);e.duration=math.max(e.duration,delay+lifetime)
 end
 local function rays(e,count,death)
  local phase=rng:NextNumber(0,TAU)
  for i=1,count do
   local angle=phase+(i-1)*TAU/count+rng:NextNumber(-.22,.22)
   particle(e,true,angle,death and rng:NextNumber(.35,.65) or rng:NextNumber(.55,.85),
    death and rng:NextNumber(2.0,2.75) or rng:NextNumber(2.0,2.7),
    death and rng:NextNumber(.8,1.35) or rng:NextNumber(1.25,1.75),
    rng:NextNumber(0,.012),death and rng:NextNumber(.12,.18) or rng:NextNumber(.24,.3),false)
  end
 end
 local function splats(e,count,death)
  local phase=rng:NextNumber(0,TAU)
  for i=1,count do
   -- Stratified angles with irregular radii leave an uneven round perimeter,
   -- rather than an even geometric ring or a spray of long red slashes.
   local angle=phase+(i-1)*TAU/count+rng:NextNumber(-.2,.2)
   particle(e,false,angle,death and rng:NextNumber(.55,1.05) or rng:NextNumber(.3,.55),
    death and rng:NextNumber(1.7,2.5) or rng:NextNumber(.85,1.45),
    death and rng:NextNumber(.32,.64) or rng:NextNumber(.2,.38),
    rng:NextNumber(.025,.065),death and rng:NextNumber(.29,.43) or rng:NextNumber(.22,.32),
    rng:NextNumber()<.2)
  end
 end
 local connection
 connection=RunService.RenderStepped:Connect(function()
  if not visuals.Parent then
   for i=#active,1,-1 do remove(i) end
   for _,e in spare do e.anchor:Destroy() end;table.clear(spare)
   connection:Disconnect()
   return
  end
  local camera=workspace.CurrentCamera;if not camera then return end
  local focal=camera.ViewportSize.Y/(2*math.tan(math.rad(camera.FieldOfView)/2))
  local now=os.clock()
  for i=#active,1,-1 do
   local e=active[i];local age=now-e.born
   if age>=e.duration then remove(i)
   else
    if not e.death and e.root and e.root.Parent then
     e.position=e.root.CFrame:PointToWorldSpace(e.localPosition)
     local bounds=e.root.CFrame*e.boundsOffset
     local toward=camera.CFrame.Position-e.position
     toward=toward.Magnitude>.01 and toward.Unit or -camera.CFrame.LookVector
     local half=e.boundsSize*.5
     local surface=math.abs(toward:Dot(bounds.RightVector))*half.X
      +math.abs(toward:Dot(bounds.UpVector))*half.Y
      +math.abs(toward:Dot(bounds.LookVector))*half.Z
      +(bounds.Position-e.position):Dot(toward)
     -- Place the billboard just ahead of the living body's camera-facing
     -- surface. Keep normal world occlusion, rather than drawing through walls.
     e.anchor.Position=e.position+toward*math.max(.15,surface+.15)
    end
    local depth=(e.anchor.Position-camera.CFrame.Position):Dot(camera.CFrame.LookVector)
    e.gui.Enabled=depth>.1
    local pixels=math.min(420,span*focal/math.max(depth,.5))
    e.gui.Size=UDim2.fromOffset(pixels,pixels)
    for _,p in e.particles do
     local t=(age-p.delay)/p.lifetime
     p.picture.Visible=t>=0 and t<1
     if t>=0 and t<1 then
      local travel=1-(1-t)^3
      local radius=p.r0+(p.r1-p.r0)*travel
      p.picture.Position=UDim2.fromScale(.5+p.dir.X*radius/span,.5+p.dir.Y*radius/span)
      -- The rotation uses the very same radial vector as the position.
      -- Correcting the sprite's native axis keeps its point outward at every angle.
      p.picture.Rotation=p.rotation
      local size=p.length*(p.white and (1-(e.death and .45 or .25)*t) or (.8+.2*math.min(t/.12,1))*(1-.3*t))
      p.picture.Size=UDim2.fromScale(size*p.aspect.X/span,size*p.aspect.Y/span)
      local hold=e.death and .12 or .5
      p.picture.ImageTransparency=p.white and math.clamp((t-hold)/(1-hold),0,1) or math.clamp((t-.55)/.45,0,1)
     end
    end
   end
  end
 end)
 local effect={}
 function effect.hit(position,npc,secondary)
  local now=os.clock()
  if npc then
   if now-(lastHit[npc] or -1e6)<.07 then return end
   lastHit[npc]=now
  end
  local e=create(position,false,npc);if not e then return end
  -- A dedicated white impact for surviving damage. Red rings belong to death;
  -- damage-over-time gets a smaller guaranteed impact, not a random no-op.
  rays(e,secondary and 3 or rng:NextInteger(6,8),false)
 end
 function effect.death(position)
  local e=create(position,true);if not e then return end
  rays(e,rng:NextInteger(5,7),true)
  splats(e,rng:NextInteger(9,12),true)
 end
 return effect
end
return V
