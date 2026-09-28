local RunService=game:GetService('RunService')
local Players=game:GetService('Players')
local Debris=game:GetService('Debris')
local Motion=require(script.Parent.SpecialMotion)
local WeaponMotion=require(script.Parent.WeaponMotion)
local Thrown=require(script.Parent.ThrownVisuals)
local V={}
function V.mount(combat,folder,lookup)
 require(script.Parent.UtilityVisuals).mount(combat,folder,lookup)
 local flights,zones,puffs={},{},{}
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
 combat:WaitForChild('SpecialFX').OnClientEvent:Connect(function(action,key,...)
  local a={...}
  if action=='End' then endFlight(key);return end
  if action=='ZoneEnd' then endZone(key);return end
  if action=='Launch' then
   flights[key]={id=a[1],owner=a[2],slot=a[3],reserve=a[4],origin=a[5],finish=a[6],launchDirection=a[6]-a[5],started=a[7],duration=a[8],height=a[9],created=workspace:GetServerTimeNow()}
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
   local visual=lookup(a[4],a[5]);if visual then origin=visual.model:GetPivot():PointToWorldSpace(Vector3.new(0,.3,-1)) end
   for i=1,10 do
    local spread=Vector3.new(math.sin(i*9),math.cos(i*7)*.5,math.sin(i*5))*.35
    task.delay((i-1)*.018,function() if folder.Parent then puff(origin+direction*.3,false,.35+i*.07,.28+i*.005,(direction+spread*.35)*length*3) end end)
   end
  end
 end)
 RunService.RenderStepped:Connect(function(dt)
  local now=workspace:GetServerTimeNow()
  for key,r in flights do
   if now-r.created>9 then endFlight(key);continue end
   if now<r.started then continue end
   if not r.model then
    local template=combat.WeaponTemplates:FindFirstChild(r.id);if not template then endFlight(key);continue end
    if r.id=='08' then
     r.model=Instance.new('Model');r.model.Name='FlyingPoison';local p=part('CloudCore',r.origin,.65,Color3.fromRGB(128,180,65),.6);p.Parent=r.model;r.model.PrimaryPart=p
    else r.model=template:Clone();r.model.Name='FlyingWeapon_'..r.id;Thrown.decorate(r.model,r.id) end
    for _,p in r.model:GetDescendants() do if p:IsA('BasePart') then p.Anchored=true;p.CanCollide=false;p.CanTouch=false;p.CanQuery=false;p.LocalTransparencyModifier=0 end end
    r.model.Parent=folder
    local visual=lookup(r.owner,r.slot)
    if visual and visual.id==r.id then
     local source=visual.reserves and visual.reserves[r.reserve] or visual.model
     r.offset=source:GetPivot().Position-r.origin
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
   local tangent=r.finish-r.origin
   local rotation=Motion.rotation(r.id,now-r.created,r.id=='31' and r.launchDirection or tangent)
   r.model:PivotTo(CFrame.new(pos)*rotation)
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
 end)
end
return V
