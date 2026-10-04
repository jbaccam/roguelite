-- Weapon-specific looks for server swept projectiles (StatProjectiles).
-- Each call is one 60 Hz step of one projectile (RogueliteCombat.client flies
-- the server's legs step by step); steps that share a projectileId are drawn
-- as one travelling head with its own trail. The server path, hits and damage
-- are unchanged.
local RunService=game:GetService('RunService')
local K=require(script.Parent:WaitForChild('VfxKit'))
local V={}
local ARCANE={core=Color3.fromRGB(226,246,255),glow=Color3.fromRGB(96,168,255),halo=Color3.fromRGB(150,112,246)}
local STORM={Color3.fromRGB(248,244,255),Color3.fromRGB(166,128,255)}
local GAZE={core=Color3.fromRGB(168,240,150),stone=Color3.fromRGB(158,156,146)}
local STEEL=Color3.fromRGB(196,201,210)

local function emitter(parent,color,rate,size,lifetime,speed)
 local e=Instance.new('ParticleEmitter');e.Name='Motes'
 e.Texture='rbxasset://textures/particles/sparkles_main.dds'
 e.Color=ColorSequence.new(color);e.LightEmission=1;e.LightInfluence=0
 e.Size=NumberSequence.new({NumberSequenceKeypoint.new(0,size),NumberSequenceKeypoint.new(1,0)})
 e.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,.1),NumberSequenceKeypoint.new(1,1)})
 e.Lifetime=NumberRange.new(lifetime*.7,lifetime);e.Rate=rate;e.Speed=NumberRange.new(speed*.5,speed)
 e.SpreadAngle=Vector2.new(180,180);e.Rotation=NumberRange.new(0,360);e.RotSpeed=NumberRange.new(-90,90)
 e.Parent=parent;return e
end
local function light(parent,color,range,brightness)
 local l=Instance.new('PointLight');l.Color=color;l.Range=range;l.Brightness=brightness;l.Shadows=false;l.Parent=parent;return l
end

local Styles={}
-- Magic Staff: concentrated elemental energy orb that pops on impact.
Styles['30']={
 muzzle=function(v)
  local size=v.model:GetAttribute('BoundsSize') or Vector3.new(.7,5.4,1.1)
  return v.model:GetPivot():PointToWorldSpace(Vector3.new(0,size.Y*.5-.45,-.13))
 end,
 build=function(folder)
  local m=Instance.new('Model');m.Name='StaffEnergyOrb'
  local core=K.ball(m,'Core',.42,ARCANE.core,0,Enum.Material.Neon)
  local glow=K.ball(m,'Glow',.9,ARCANE.glow,.55,Enum.Material.Neon)
  local halo=K.ball(m,'Halo',1.35,ARCANE.halo,.84,Enum.Material.Neon)
  m.PrimaryPart=core
  K.trail(core,.62,.22,ARCANE.glow,ARCANE.halo,.25)
  emitter(core,Color3.fromRGB(170,215,255),22,.3,.35,.8)
  light(core,ARCANE.glow,7,1.1)
  m.Parent=folder
  return m,{glow=glow,halo=halo}
 end,
 update=function(s,cf,age)
  local pulse=1+.12*math.sin(age*32)
  s.parts.glow.Size=Vector3.one*.9*pulse;s.parts.halo.Size=Vector3.one*1.35*(2-pulse)
  s.model:PivotTo(cf)
 end,
 launch=function(folder,point)
  K.pop(folder,point,ARCANE.glow,.3,1.7,.2,.4);K.flash(folder,point,ARCANE.glow,8,1.6,.22)
 end,
 impact=function(folder,point)
  K.pop(folder,point,ARCANE.core,.35,1.6,.16,.2)
  K.pop(folder,point,ARCANE.glow,.6,3.3,.28,.45)
  K.pop(folder,point,ARCANE.halo,.8,4.2,.34,.7)
  K.shards(folder,point,ARCANE.glow,7,9,.36,.18,nil,.5)
  K.flash(folder,point,ARCANE.glow,10,2.2,.26)
 end,
}
-- Crystal Ball: violet lightning racing out and jumping between enemies.
Styles['35']={
 muzzle=function(v)
  local core=v.model:FindFirstChild('W35_Crystal_Core',true)
  return core and core.Position or v.model:GetPivot().Position
 end,
 build=function(folder)
  local m=Instance.new('Model');m.Name='CrystalSpark'
  local core=K.ball(m,'Core',.34,STORM[1],0,Enum.Material.Neon)
  K.ball(m,'Glow',.8,STORM[2],.6,Enum.Material.Neon)
  m.PrimaryPart=core
  light(core,STORM[2],6,1.3)
  m.Parent=folder
  return m,{}
 end,
 lightning=true,
 update=function(s,cf,age,folder)
  s.model:PivotTo(cf)
  if not s.bolt then s.bolt=K.newBolt(folder,STORM,.075,true);s.rng=Random.new() end
  if not s.redrawn or age-s.redrawn>.04 then
   s.redrawn=age
   s.bolt:draw(s.segmentStart or cf.Position,cf.Position,.42,s.rng)
  end
 end,
 contact=function(folder,s,point)
  -- Leave the finished jump behind as a flickering strike, then chain onward.
  K.strike(folder,s.segmentStart or point,point,STORM,.075,.2)
  K.shards(folder,point,STORM[2],5,7,.24,.12,nil,.6)
  s.segmentStart=point;s.redrawn=nil
 end,
 launch=function(folder,point)
  K.pop(folder,point,STORM[2],.9,2.2,.16,.5);K.flash(folder,point,STORM[2],7,1.4,.18)
 end,
 impact=function(folder,point,s)
  K.strike(folder,s.segmentStart or point,point,STORM,.075,.22)
  K.pop(folder,point,STORM[1],.3,1.5,.14,.3)
  K.shards(folder,point,STORM[2],6,8,.28,.13,nil,.6)
  K.flash(folder,point,STORM[2],9,2,.22)
 end,
}
-- Medusa's Head: green gaze bolt that turns to stone dust on contact.
Styles['34']={
 muzzle=function(v) return v.model:GetPivot():PointToWorldSpace(Vector3.new(0,.35,-.45)) end,
 build=function(folder)
  local m=Instance.new('Model');m.Name='MedusaGaze'
  local core=K.ball(m,'Core',.44,GAZE.core,0,Enum.Material.Neon)
  K.ball(m,'Glow',.85,Color3.fromRGB(98,176,96),.66,Enum.Material.Neon)
  m.PrimaryPart=core
  K.trail(core,.45,.24,GAZE.core,GAZE.stone,.3)
  m.Parent=folder
  return m,{}
 end,
 update=function(s,cf) s.model:PivotTo(cf) end,
 launch=function(folder,point) K.pop(folder,point,GAZE.core,.3,1.4,.16,.45) end,
 impact=function(folder,point)
  K.pop(folder,point,GAZE.core,.4,2.1,.2,.5)
  K.cloud(folder,point,GAZE.stone,1.3,.55,Vector3.yAxis*.5,.3)
  K.shards(folder,point,GAZE.stone,6,6,.4,.22,Enum.Material.SmoothPlastic,.7)
 end,
}
-- Nail Gun: a small steel nail with a short bright streak.
Styles['24']={
 build=function(folder)
  local m=Instance.new('Model');m.Name='FlyingNail'
  local shaft=K.part(m,'Shaft',Vector3.new(.07,.07,.5),STEEL,0,Enum.Material.Metal)
  local head=K.part(m,'Head',Vector3.new(.16,.16,.04),STEEL,0,Enum.Material.Metal)
  head.CFrame=CFrame.new(0,0,.25)
  m.PrimaryPart=shaft
  K.trail(shaft,.08,.08,K.White,STEEL,.35)
  m.Parent=folder
  return m,{head=head}
 end,
 update=function(s,cf)
  s.model.PrimaryPart.CFrame=cf;s.parts.head.CFrame=cf*CFrame.new(0,0,.25)
 end,
}
-- The Handyman turret fires the same nails (id 'Turret', HANDYMAN_TURRET.md).
Styles.Turret=Styles['24']
-- Yo-Yo: the disc flies out on a string from its finger loop, then reels back.
Styles['21']={
 build=function(folder,v)
  local template=game.ReplicatedStorage.RogueliteCombat.WeaponTemplates:FindFirstChild('21')
  local disc=template and template:FindFirstChild('W21_Yo_Yo__02',true)
  local m=Instance.new('Model');m.Name='FlyingYoYo'
  local head=disc and disc:Clone() or K.ball(m,'Disc',.9,Color3.fromRGB(214,64,58),0)
  head.Anchored=true;head.CanCollide=false;head.CanTouch=false;head.CanQuery=false;head.Parent=m
  m.PrimaryPart=head
  local a1=Instance.new('Attachment');a1.Name='StringEnd';a1.Parent=head
  local anchor=K.part(m,'StringAnchor',Vector3.one*.05,K.White,1)
  local a0=Instance.new('Attachment');a0.Name='StringStart';a0.Parent=anchor
  local beam=Instance.new('Beam');beam.Name='String';beam.Attachment0=a0;beam.Attachment1=a1
  beam.Width0=.05;beam.Width1=.05;beam.FaceCamera=true;beam.Segments=6;beam.LightInfluence=.6
  beam.Color=ColorSequence.new(Color3.fromRGB(248,244,232));beam.Transparency=NumberSequence.new(.1);beam.Parent=anchor
  K.trail(head,.55,.1,K.White,K.White,.55)
  m.Parent=folder
  local parts={anchor=anchor}
  if v then
   parts.loop=v.model:FindFirstChild('W21_Yo_Yo__01',true)
   parts.disc=v.model:FindFirstChild('W21_Yo_Yo__02',true)
  end
  return m,parts
 end,
 hideDisc=true,
 update=function(s,cf,age)
  local v=s.visual
  local loop=s.parts.loop and s.parts.loop.Parent and s.parts.loop.Position or (v and v.model.Parent and v.model:GetPivot().Position) or s.home
  s.home=loop or s.home
  s.parts.anchor.CFrame=CFrame.new(s.home or cf.Position)
  s.model.PrimaryPart.CFrame=cf*CFrame.Angles(0,0,-age*28)
 end,
 retract=.16,
}
V.Styles=Styles

function V.mount(folder,lookup)
 local shots={}
 local api={}
 local function release(key)
  local s=shots[key];if not s then return end
  shots[key]=nil
  if s.bolt then s.bolt:destroy() end
  if s.visual and s.style.hideDisc and s.visual.hide and s.parts.disc then
   s.visual.hide[s.parts.disc]=math.max(0,(s.visual.hide[s.parts.disc] or 1)-1)
  end
  if s.model then s.model:Destroy() end
 end
 local function finish(key,point,contact)
  local s=shots[key];if not s then return end
  if s.style.impact and contact and s.near then s.style.impact(folder,point,s) end
  if s.style.retract then
   -- Reel the disc back to its loop before restoring the resting yo-yo.
   s.retracting=os.clock();s.retractFrom=s.head or point
   return
  end
  release(key)
 end
 function api.handle(origin,finishPoint,kind,id,thickness,blastRadius,contact,normal,ownerId,slotIndex,first,mobContact,shotId,projectileId,speed,terminal)
  if kind=='Lightning' then
   if K.near(origin) or K.near(finishPoint) then
    K.strike(folder,origin,finishPoint,id=='35' and STORM or K.Lightning,.08,.22)
    K.shards(folder,finishPoint,(id=='35' and STORM or K.Lightning)[2],4,6,.22,.12,nil,.6)
   end
   return true
  end
  local style=Styles[id]
  if not style or kind~='Ranged' or not projectileId then return false end
  local key=tostring(ownerId)..':'..tostring(projectileId)
  local s=shots[key]
  if not s then
   -- `first` is only set for muzzle-mapped guns, so a new id marks the launch.
   local v=lookup(ownerId,slotIndex)
   if v and v.id~=id then v=nil end
   local near=K.near(origin,160)
   local model,parts=nil,{}
   if near then model,parts=style.build(folder,v) end
   local launchPoint=origin
   if v and style.muzzle then launchPoint=style.muzzle(v) end
   s={id=id,style=style,model=model,parts=parts,visual=v,born=os.clock(),head=origin,
    direction=(finishPoint-origin).Magnitude>.01 and (finishPoint-origin).Unit or Vector3.zAxis,
    offset=launchPoint-origin,segmentStart=style.lightning and launchPoint or nil,near=near}
   shots[key]=s
   if near and style.launch then style.launch(folder,launchPoint) end
   if v and style.hideDisc and parts.disc then
    v.hide=v.hide or {};v.hide[parts.disc]=(v.hide[parts.disc] or 0)+1
   end
  end
  if s.retracting then return true end
  local delta=finishPoint-origin
  if delta.Magnitude>.01 then s.direction=delta.Unit end
  s.head=finishPoint;s.last=os.clock();s.speed=speed or 110
  if terminal then finish(key,finishPoint,contact)
  elseif contact and s.style.contact and s.near then s.style.contact(folder,s,finishPoint) end
  return true
 end
 RunService.RenderStepped:Connect(function()
  local now=os.clock()
  for key,s in shots do
   local age=now-s.born
   if age>8 or (not s.retracting and now-(s.last or s.born)>.6) then release(key);continue end
   if not s.model then continue end
   if s.retracting then
    local t=math.clamp((now-s.retracting)/s.style.retract,0,1)
    local home=s.home or s.retractFrom
    local pos=s.retractFrom:Lerp(home,t*t)
    s.style.update(s,CFrame.lookAt(pos,pos+s.direction),age,folder)
    if t>=1 then release(key) end
    continue
   end
   -- Extrapolate between server steps so the head glides rather than stepping.
   local lead=math.min(now-(s.last or now),.05)*(s.speed or 0)
   local pos=s.head+s.direction*lead
   local blend=math.clamp(age/.15,0,1)
   pos+=s.offset*(1-blend)^2
   s.style.update(s,CFrame.lookAt(pos,pos+s.direction),age,folder)
  end
 end)
 return api
end
return V
