local RunService=game:GetService('RunService')
local Players=game:GetService('Players')
local Vacuum=require(game.ReplicatedStorage.RogueliteCombat.VacuumVisuals)
local SPRAY=Color3.fromRGB(214,238,255)
local function mist(parent,rate,size0,size1,lifetime,spread,speed)
 local e=Instance.new('ParticleEmitter');e.Name='WaterMist'
 e.Texture='rbxasset://textures/particles/smoke_main.dds'
 e.Color=ColorSequence.new(SPRAY);e.LightEmission=.2;e.LightInfluence=.6
 e.Size=NumberSequence.new(size0,size1)
 e.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,.62),NumberSequenceKeypoint.new(1,1)})
 e.Lifetime=NumberRange.new(lifetime*.7,lifetime);e.Rate=rate;e.Speed=NumberRange.new(speed*.5,speed)
 e.SpreadAngle=Vector2.new(spread,spread);e.Rotation=NumberRange.new(0,360);e.RotSpeed=NumberRange.new(-30,30)
 e.EmissionDirection=Enum.NormalId.Front;e.Parent=parent;return e
end
local V={}
function V.mount(combat,folder,lookup,options)
 options=options or {}
 local closed=false
 local streams={};local vacuumPool={};local vacuumCount=0
 local function clear(key)
  local s=streams[key];if not s then return end
  if s.vacuum then s.vacuum:hide();table.insert(vacuumPool,s.vacuum) else s.model:Destroy() end
  streams[key]=nil
 end
 local function onFx(action,key,...)
  if closed then return end
  if action=='StreamEnd' then clear(key);return end
  if action~='Stream' then return end
  local id,owner,slot,origin,finish,width,expires,safe=...
  local s=streams[key]
  if s and s.id~=id then clear(key);s=nil end
  if not s then
   if id=='28' then
    local visual=table.remove(vacuumPool)
    if not visual then
     if vacuumCount>=12 then return end -- bounded even with six copies on four players
     visual=Vacuum.new(folder);vacuumCount+=1
    end
    s={id=id,vacuum=visual,model=visual.model};streams[key]=s
   else
   local model=Instance.new('Model');model.Name='WaterStream';model.Parent=folder
   local anchor=Instance.new('Part');anchor.Name='FlowAnchor';anchor.Size=Vector3.one*.1;anchor.Transparency=1;anchor.Anchored=true;anchor.CanCollide=false;anchor.CanQuery=false;anchor.CanTouch=false;anchor.Parent=model
   s={id=id,model=model,anchor=anchor,lines={},drops={}};streams[key]=s
   for i=1,3 do
    local a=Instance.new('Attachment');a.Parent=anchor;local b=Instance.new('Attachment');b.Parent=anchor
    local beam=Instance.new('Beam');beam.Name='WaterJet';beam.Attachment0=a;beam.Attachment1=b;beam.FaceCamera=true;beam.Segments=12
    beam.Width0=i==1 and .25 or .1;beam.Width1=i==1 and .75 or .25
    beam.Color=ColorSequence.new(i==1 and Color3.fromRGB(90,185,241) or Color3.fromRGB(207,240,255))
    beam.Transparency=NumberSequence.new(i==1 and .28 or .4);beam.LightEmission=.15;beam.Parent=anchor
    table.insert(s.lines,{a=a,b=b,beam=beam})
   end
   if id=='29' then
    -- Mist at the nozzle and a splash where the jet actually lands.
    s.nozzle=Instance.new('Attachment');s.nozzle.Name='Nozzle';s.nozzle.Parent=anchor
    mist(s.nozzle,16,.25,1.1,.35,14,3)
    s.contact=Instance.new('Attachment');s.contact.Name='Splash';s.contact.Parent=anchor
    s.splashMist=mist(s.contact,14,.6,1.9,.5,70,2.2)
    s.splash={}
    for i=1,12 do
     local p=Instance.new('Part');p.Name='SplashDroplet';p.Shape=Enum.PartType.Ball;p.Size=Vector3.one*.16
     p.Color=Color3.fromRGB(168,224,255);p.Transparency=1;p.Material=Enum.Material.SmoothPlastic
     p.Anchored=true;p.CanCollide=false;p.CanTouch=false;p.CanQuery=false;p.CastShadow=false;p.Parent=model;s.splash[i]=p
    end
   end
   for i=1,16 do
    local p=Instance.new('Part');p.Name='WaterDroplet';p.Shape=Enum.PartType.Ball;p.Size=Vector3.one*.14
    p.Color=Color3.fromRGB(151,218,255);p.Transparency=.4;p.Material=Enum.Material.SmoothPlastic
    p.Anchored=true;p.CanCollide=false;p.CanTouch=false;p.CanQuery=false;p.CastShadow=false;p.Parent=model;table.insert(s.drops,p)
   end
   end
  end
  s.owner=owner;s.slot=slot;s.origin=origin;s.finish=finish;s.width=width;s.expires=expires;s.safe=safe
 end
 local function step(dt)
  if closed then return end
  local now=workspace:GetServerTimeNow()
  for key,s in streams do
   if now>s.expires or not folder.Parent then clear(key);continue end
   local origin=s.origin;local visual=lookup(s.owner,s.slot)
   if visual and visual.model.Parent then origin=visual.model:GetPivot():PointToWorldSpace(Vector3.new(0,0,-1.1)) end
   s.smoothFinish=s.smoothFinish and s.smoothFinish:Lerp(s.finish,1-math.exp(-18*dt)) or s.finish
   if s.vacuum then s.vacuum:update(origin,s.smoothFinish,s.width,now);continue end
   local delta=s.smoothFinish-origin;if delta.Magnitude<.05 then continue end
   local direction=delta.Unit;local right=direction:Cross(Vector3.yAxis);if right.Magnitude<.01 then right=Vector3.xAxis else right=right.Unit end
   s.anchor.CFrame=CFrame.new(origin)
   for i,line in s.lines do
    local lane=(i-2)*.15
    line.a.WorldPosition=origin+right*lane*.1
    line.b.WorldPosition=s.smoothFinish+right*lane
    line.beam.CurveSize0=math.sin(now*8+i)*.12
    line.beam.CurveSize1=-math.sin(now*9+i)*.2
   end
   if s.splash then
    local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude
    local exclude={folder};for _,player in Players:GetPlayers() do if player.Character then table.insert(exclude,player.Character) end end
    params.FilterDescendantsInstances=exclude
    local hit=workspace:Raycast(origin,delta,params)
    local point=hit and hit.Position or s.finish
    local normal=hit and hit.Normal or -direction
    s.nozzle.WorldCFrame=CFrame.lookAt(origin,origin+direction)
    s.contact.WorldCFrame=CFrame.lookAt(point,point+normal)
    local hasContact=hit~=nil or options.preview==true
    s.splashMist.Enabled=hasContact
    -- Droplets bounce back off the contact point; without contact they fall from the tip.
    local bounce=(normal*.8-direction*.2)
    bounce=bounce.Magnitude>.01 and bounce.Unit or Vector3.yAxis
    local side=bounce:Cross(Vector3.yAxis);side=side.Magnitude>.01 and side.Unit or Vector3.xAxis
    for i,p in s.splash do
     local phase=(now*2.6+i/12)%1
     local lane=math.sin(i*2.71)
     local spread=hasContact and (bounce*3.2+side*lane*2.4) or (direction*1.2+side*lane*.8)
     p.Position=point+spread*phase+Vector3.yAxis*((hasContact and 2.6 or .4)*phase-5*phase*phase)
     p.Transparency=.3+.7*phase
    end
   end
   for i,p in s.drops do
    local t=(now*2.8+i/16)%1
    local lane=math.sin(i*4.13)
    local spread=.16+.25*t
    local spiral=now*5+i*2.17
    p.Position=origin+delta*t+right*(lane*spread)+Vector3.yAxis*(math.cos(spiral)*.2*t)
    p.Transparency=.35
   end
  end
 end
 if options.preview then
  return {handle=onFx,step=step,destroy=function()
   if closed then return end;closed=true
   for key in streams do clear(key) end
   for _,v in vacuumPool do v:destroy() end
   table.clear(vacuumPool)
  end}
 end
 combat.SpecialFX.OnClientEvent:Connect(onFx)
 RunService.RenderStepped:Connect(step)
end
return V
