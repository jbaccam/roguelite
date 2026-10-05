local RunService=game:GetService('RunService')
local Players=game:GetService('Players')
local Debris=game:GetService('Debris')
local Motion=require(script.Parent.SpecialMotion)
local WeaponMotion=require(script.Parent.WeaponMotion)
local Thrown=require(script.Parent.ThrownVisuals)
local Ground=require(script.Parent.GroundContact)
local V={}
function V.mount(combat,folder,lookup,options)
 options=options or {}
 local closed=false
 local utility=require(script.Parent.UtilityVisuals).mount(combat,folder,lookup,options)
 local flights,zones,puffs,sprays={},{},{},{}
 local ground=Ground.new({folder})
 local function part(name,position,size,color,alpha)
  local p=Instance.new('Part');p.Name=name;p.Shape=Enum.PartType.Ball;p.Size=Vector3.one*size;p.Position=position
  p.Anchored=true;p.CanCollide=false;p.CanQuery=false;p.CanTouch=false;p.CastShadow=false;p.Material=Enum.Material.SmoothPlastic;p.Color=color;p.Transparency=alpha;p.Parent=folder;return p
 end
 local function puff(position,green,size,duration,velocity)
  if #puffs>=180 then table.remove(puffs,1).part:Destroy() end
  local p=part(green and 'PoisonPuff' or 'DuckFlame',position,size,green and Color3.fromRGB(112,171,58) or Color3.fromRGB(255,157,35),green and .5 or .15)
  if not green then
   p.Transparency=.8
   local flame=Instance.new('Fire');flame.Size=1.2;flame.Heat=1;flame.Color=Color3.fromRGB(255,170,45);flame.SecondaryColor=Color3.fromRGB(225,67,15);flame.Parent=p
  end
  table.insert(puffs,{part=p,born=os.clock(),duration=duration,size=size,position=position,velocity=velocity or Vector3.yAxis*.5,green=green})
 end
 local function release(r)
  if r.visual and r.visual.flying then r.visual.flying[r.reserve]=math.max(0,(r.visual.flying[r.reserve] or 1)-1) end
  if r.model then r.model:Destroy() end
 end
 local function endFlight(key)
  local r=flights[key];if not r then return end
  -- Returning weapons land back in their slot; everything else gets a small impact.
  if r.model and not r.returning then Thrown.impact(folder,r.id,r.model:GetPivot().Position) end
  release(r);flights[key]=nil
 end
 local function endZone(key) local z=zones[key];if z then z.model:Destroy();zones[key]=nil end end
 local function onFx(action,key,...)
  if closed then return end
  if utility then utility.handle(action,key,...) end
  local a={...}
  if action=='End' then endFlight(key);return end
  if action=='ZoneEnd' then endZone(key);return end
  if action=='Launch' then
   flights[key]={id=a[1],owner=a[2],slot=a[3],reserve=a[4],origin=a[5],finish=a[6],launchDirection=a[6]-a[5],started=a[7],duration=a[8],height=a[9],rollRadius=a[10],created=workspace:GetServerTimeNow()}
  elseif action=='Segment' then
   local r=flights[key];if r then r.origin=a[1];r.finish=a[2];r.started=a[3];r.duration=a[4];r.height=a[5];r.returning=a[6];r.offset=Vector3.zero end
  elseif action=='Zone' then
   local model=Instance.new('Model');model.Name=a[1]..'Zone';model.Parent=folder
   local green=a[1]=='Poison';local radius=a[3]
   local z={model=model,position=a[2],radius=radius,ends=workspace:GetServerTimeNow()+a[4],green=green,parts={}}
   for i=1,7 do
    local angle=i*2.39996;local distance=i==1 and 0 or radius*.5
    local size=green and radius*1.15 or radius*.55
    local pos=a[2]+Vector3.new(math.cos(angle)*distance,green and math.sin(i)*radius*.1 or 0,math.sin(angle)*distance)
    local p=part(green and 'LingeringPoison' or 'LingeringFire',pos,size,green and Color3.fromRGB(90+i*5,140+i*4,48) or Color3.fromRGB(255,90+i*10,20),green and .63 or .4)
    p.Parent=model
    if green then
     p.Transparency=1
     local smoke=Instance.new('ParticleEmitter');smoke.Name='SoftPoison';smoke.Texture='rbxasset://textures/particles/smoke_main.dds'
     smoke.Color=ColorSequence.new(Color3.fromRGB(105,158,61),Color3.fromRGB(76,119,50))
     smoke.Size=NumberSequence.new({NumberSequenceKeypoint.new(0,size*.65),NumberSequenceKeypoint.new(1,size)})
     smoke.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,1),NumberSequenceKeypoint.new(.2,.68),NumberSequenceKeypoint.new(.7,.76),NumberSequenceKeypoint.new(1,1)})
     smoke.Lifetime=NumberRange.new(1,1.6);smoke.Rate=8;smoke.Speed=NumberRange.new(.2,.6);smoke.SpreadAngle=Vector2.new(180,180)
     smoke.Rotation=NumberRange.new(0,360);smoke.RotSpeed=NumberRange.new(-15,15);smoke.LightInfluence=.5;smoke.Parent=p;smoke:Emit(5)
    else
     p.Material=Enum.Material.Neon;p.Size=Vector3.new(size,.12,size)
     local flame=Instance.new('Fire');flame.Size=math.min(6,radius*.7);flame.Heat=3;flame.Color=Color3.fromRGB(255,156,35);flame.SecondaryColor=Color3.fromRGB(190,51,12);flame.Parent=p
    end
    table.insert(z.parts,{part=p,position=pos,size=p.Size})
   end
   zones[key]=z
  elseif action=='Spray' then
   local origin,direction,length=a[1],a[2],a[3]
   local streamKey=a[4]..':'..a[5];local s=sprays[streamKey]
   if not s then
    local anchor=part('DuckFlameNozzle',origin,.1,Color3.new(1,1,1),1)
    local flame=Instance.new('ParticleEmitter');flame.Name='ContinuousFlame';flame.Texture='rbxasset://textures/particles/fire_main.dds'
    flame.Color=ColorSequence.new({ColorSequenceKeypoint.new(0,Color3.fromRGB(255,241,157)),ColorSequenceKeypoint.new(.45,Color3.fromRGB(255,163,45)),ColorSequenceKeypoint.new(1,Color3.fromRGB(231,65,17))})
    flame.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,.15),NumberSequenceKeypoint.new(.6,.35),NumberSequenceKeypoint.new(1,1)})
    flame.Size=NumberSequence.new({NumberSequenceKeypoint.new(0,.35),NumberSequenceKeypoint.new(.6,1.8),NumberSequenceKeypoint.new(1,2.6)})
    flame.Lifetime=NumberRange.new(.2,.28);flame.Rate=40;flame.SpreadAngle=Vector2.new(12,12)
    flame.EmissionDirection=Enum.NormalId.Front;flame.LightEmission=.65;flame.LightInfluence=0;flame.Rotation=NumberRange.new(0,360);flame.RotSpeed=NumberRange.new(-45,45);flame.Parent=anchor
    s={anchor=anchor,flame=flame,owner=a[4],slot=a[5],direction=direction};sprays[streamKey]=s
   end
   s.origin=origin;s.aim=direction;s.length=length;s.expires=workspace:GetServerTimeNow()+(a[6] or .42)
   s.flame.Speed=NumberRange.new(length/ .28,length/ .22);s.flame.Enabled=true
  end
 end
 local function step(dt)
  if closed then return end
  if utility then utility.step(dt) end
  local now=workspace:GetServerTimeNow()
  for key,s in sprays do
   if now>s.expires+.3 then s.anchor:Destroy();sprays[key]=nil;continue end
   s.flame.Enabled=now<s.expires
   local visual=lookup(s.owner,s.slot)
   local origin=visual and visual.model.Parent and visual.model:GetPivot():PointToWorldSpace(Vector3.new(0,.3,-1)) or s.origin
   s.direction=s.direction:Lerp(s.aim,1-math.exp(-20*dt))
   if s.direction.Magnitude>.01 then s.anchor.CFrame=CFrame.lookAt(origin,origin+s.direction) end
  end
  for key,r in flights do
   if now-r.created>9 then endFlight(key);continue end
   if now<r.started then continue end
   if not r.model then
    local template=combat.WeaponTemplates:FindFirstChild(r.id);if not template then endFlight(key);continue end
    if r.id=='08' then
     r.model=Instance.new('Model');r.model.Name='FlyingPoison';local p=part('CloudCore',r.origin,.65,Color3.fromRGB(128,180,65),.6);p.Parent=r.model;r.model.PrimaryPart=p
    else
     r.model=template:Clone();r.model.Name='FlyingWeapon_'..r.id
     if r.id=='22' then
      local nativeRadius,center=Ground.ballGeometry(template)
      r.rollRadius=r.rollRadius or nativeRadius;local scale=r.rollRadius/nativeRadius
      r.model:ScaleTo(r.model:GetScale()*scale);r.ballCenter=center*scale
     end
     Thrown.decorate(r.model,r.id)
    end
    for _,p in r.model:GetDescendants() do if p:IsA('BasePart') then p.Anchored=true;p.CanCollide=false;p.CanTouch=false;p.CanQuery=false;p.LocalTransparencyModifier=0 end end
    r.model.Parent=folder
    local visual=lookup(r.owner,r.slot)
    if visual and visual.id==r.id then
     local source=visual.reserves and visual.reserves[r.reserve] or visual.model
     -- Ordinary throws start on the server's fixed path. Catching up from a moving inventory
     -- slot with an easing offset looked like steering in mid-air (especially Bowling Pins).
     r.offset=Motion.profiles[r.id].returns and source:GetPivot().Position-r.origin or Vector3.zero
     if r.id~='08' then visual.flying=visual.flying or {};visual.flying[r.reserve]=(visual.flying[r.reserve] or 0)+1;r.visual=visual end
    else r.offset=Vector3.zero end
   end
   if r.returning then
    local owner=Players:GetPlayerByUserId(r.owner);local root=owner and owner.Character and owner.Character:FindFirstChild('HumanoidRootPart')
    if r.visual and r.visual.model.Parent then r.finish=r.visual.model:GetPivot().Position
    elseif root then r.finish=WeaponMotion.origin(root.CFrame,WeaponMotion.BaseRadius,r.slot) end
   end
   local t=math.clamp((now-r.started)/r.duration,0,1)
   local pos=Motion.position(r.origin,r.finish,t,r.height)+(r.offset or Vector3.zero)*math.max(0,1-(now-r.started)/.16)^2
   if r.id=='22' then
    -- Same probe, radius and center offset as the server: a dummy's head is never floor.
    local previousFloor=r.lastGround or r.origin.Y-r.rollRadius-Ground.Clearance
    local center=ground:center(pos,r.rollRadius,previousFloor)
    if center then pos=center;r.lastGround=center.Y-r.rollRadius-Ground.Clearance;r.model.Parent=folder
    else r.model.Parent=nil;continue end
   end
   local tangent=r.finish-r.origin
   local rotation=Motion.rotation(r.id,now-r.created,r.id=='31' and r.launchDirection or tangent)
   if r.id=='22' then
    local distance=(Vector3.new(pos.X,0,pos.Z)-Vector3.new(r.origin.X,0,r.origin.Z)).Magnitude
    rotation=CFrame.lookAt(Vector3.zero,Vector3.new(tangent.X,0,tangent.Z))*CFrame.Angles(-distance/r.rollRadius,0,0)
   end
   r.model:PivotTo(CFrame.new(pos)*rotation*CFrame.new(-(r.ballCenter or Vector3.zero)))
   Thrown.step(folder,r,pos)
   if r.id=='08' and (not r.lastPuff or (pos-r.lastPuff).Magnitude>.7) then puff(pos,true,.6,.4);r.lastPuff=pos end
  end
  for key,z in zones do
   if now>=z.ends then endZone(key)
   else
    for i,e in z.parts do
     if z.green then e.part.Position=e.position+Vector3.new(math.sin(now+i)*.2,math.cos(now*1.3+i)*.18,0) end
     if z.green then e.part.SoftPoison.Enabled=z.ends-now>.6
     else e.part.Transparency=.4+math.clamp(1-(z.ends-now)/.5,0,1)*.35 end
    end
   end
  end
  for i=#puffs,1,-1 do local p=puffs[i];local age=os.clock()-p.born;local t=age/p.duration
   if t>=1 then p.part:Destroy();table.remove(puffs,i)
   else p.part.Position=p.position+p.velocity*age;p.part.Size=Vector3.one*p.size*(1+t*1.7);p.part.Transparency=(p.green and .5 or .8)+t*(p.green and .5 or .2) end
  end
 end
 if options.preview then
  return {handle=onFx,step=step,destroy=function()
   if closed then return end;closed=true
   if utility then utility.destroy() end
   for _,r in flights do release(r) end;table.clear(flights)
   for key in zones do endZone(key) end
   for _,p in puffs do p.part:Destroy() end;table.clear(puffs)
   for _,s in sprays do s.anchor:Destroy() end;table.clear(sprays)
  end}
 end
 combat:WaitForChild('SpecialFX').OnClientEvent:Connect(onFx)
 RunService.RenderStepped:Connect(step)
end
return V
