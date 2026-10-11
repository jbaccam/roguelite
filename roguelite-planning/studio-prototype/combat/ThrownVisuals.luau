-- Trails and landing effects for modeled throws (SpecialWeapons flights).
-- Kept light: short transparent trails, one small signature impact each.
local K=require(script.Parent:WaitForChild('VfxKit'))
local Q=require(script.Parent:WaitForChild('ClientQuality'))
local Motion=require(script.Parent:WaitForChild('SpecialMotion'))
local T={}
-- Molotov fire textures. Flame, Scorch and Ember are the boss kit's painted sprites, already uploaded
-- (BossVfxAssets; LegendaryVisuals uses them too). Pool: weapon-models/assets/14-molotovs/vfx/
-- textures/MolotovFirePool.png; nil until it is uploaded, and the pool is drawn as flat discs meanwhile.
T.FireTextures={Flame='rbxassetid://132081298787809',Scorch='rbxassetid://92423458342016',Ember='rbxassetid://116159534169534',Pool='rbxassetid://121830714730465'} -- Pool: MolotovFirePool.png, uploaded 2026-10-10
-- The flame flipbook's bands, measured from its pixels: rim red, orange, yellow (design sheet:
-- https://claude.ai/artifact/NBgiUUT7Ee3gDMfwWhMEA8).
local POOL_BANDS={{Color3.fromRGB(211,58,34),1,.32},{Color3.fromRGB(247,128,31),.78,.28},{Color3.fromRGB(255,201,63),.52,.22}}
local YOLK=Color3.fromRGB(255,196,64)
local SHELL=Color3.fromRGB(250,244,230)
local GLASS=Color3.fromRGB(176,226,206)
local FLAME={Color3.fromRGB(255,170,64),Color3.fromRGB(214,72,24)}
local PIN_RED=Color3.fromRGB(214,58,52)

local function mainPart(model)
 return model.PrimaryPart or model:FindFirstChildWhichIsA('BasePart',true)
end
function T.decorate(model,id)
 local part=mainPart(model);if not part then return end
 if id=='13' then K.trail(part,.14,.12,K.White,K.White,.3)
 elseif id=='12' then
  -- A ribbon out along one wing sweeps a soft spinning disc as it turns.
  local reach=part.Size.X*.5
  local a0=Instance.new('Attachment');a0.Position=Vector3.new(reach*.35,0,0);a0.Parent=part
  local a1=Instance.new('Attachment');a1.Position=Vector3.new(reach*.95,0,0);a1.Parent=part
  local trail=Instance.new('Trail');trail.Name='FxTrail';trail.Attachment0=a0;trail.Attachment1=a1
  trail.Lifetime=.09;trail.FaceCamera=false;trail.LightEmission=.3;trail.MinLength=.04
  trail.Color=ColorSequence.new(K.White)
  trail.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,.45),NumberSequenceKeypoint.new(1,1)})
  trail.Parent=part
 elseif id=='15' or id=='23' then K.trail(part,.3,.14,K.White,K.White,.55)
 elseif id=='22' then K.trail(part,.5,.12,K.Dust,K.Dust,.7)
 elseif id=='14' then K.trail(part,.38,.2,FLAME[1],FLAME[2],.3)
 elseif id=='31' then K.trail(part,.55,.18,K.Lightning[1],K.Lightning[2],.35)
 elseif id=='37' then require(script.Parent.GodlyVisuals).decorateThrown(model,id)
 end
end
function T.step(folder,r,position)
 if r.id=='22' then
  -- Rolling ball kicks up small dust puffs at intervals.
  if not r.lastDust or (position-r.lastDust).Magnitude>1.4 then
   r.lastDust=position
   if K.near(position,120) then K.cloud(folder,position-Vector3.yAxis*.6,K.Dust,.7,.45,Vector3.yAxis*.5,.45) end
  end
 elseif r.id=='31' then
  -- Thrown Mjolnir crackles with short sparks around its head.
  local now=os.clock()
  if not r.lastCrackle or now-r.lastCrackle>.09 then
   r.lastCrackle=now
   if K.near(position,120) then
    local a=position+Vector3.new(math.random()-.5,math.random()-.5,math.random()-.5)*1.4
    local b=position+Vector3.new(math.random()-.5,math.random()-.5,math.random()-.5)*2.2
    K.strike(folder,a,b,nil,.05,.1)
   end
  end
 end
end
function T.impact(folder,id,position)
 if not K.near(position,140) then return end
 if id=='15' then
  -- Egg: yolk splat with shell bits.
  K.pop(folder,position,YOLK,.4,1.6,.18,.25)
  K.shards(folder,position,SHELL,6,6,.4,.16,Enum.Material.SmoothPlastic,.8)
  K.shards(folder,position,YOLK,4,4,.35,.2,Enum.Material.SmoothPlastic,.6)
 elseif id=='23' then
  K.shards(folder,position,K.White,5,8,.28,.14,nil,.6)
  K.shards(folder,position,PIN_RED,3,6,.28,.12,nil,.6)
  K.cloud(folder,position,K.Dust,.8,.35,Vector3.yAxis*.4,.5)
 elseif id=='22' then
  for i=1,3 do
   local angle=i*2.1
   K.cloud(folder,position+Vector3.new(math.cos(angle),-.4,math.sin(angle))*.8,K.Dust,1.2,.5,Vector3.new(math.cos(angle),.6,math.sin(angle)),.35)
  end
 elseif id=='14' then
  K.shards(folder,position,GLASS,7,8,.35,.14,Enum.Material.Glass,.9)
  K.pop(folder,position,FLAME[1],.5,2.6,.22,.35)
  K.flash(folder,position,FLAME[1],10,2,.3)
 elseif id=='13' then
  K.shards(folder,position,K.White,3,6,.16,.1,nil,.5)
 end
end
-- Molotov fire pool (2026-10-10 rework; SpecialWeaponVisuals 'Zone'). Flat and painted, never a Fire
-- instance or a shaded mesh: a scorch decal at the start size, the painted pool sized to the
-- server's radius every frame (SpecialMotion.zoneRadius, the same curve the damage ticks use), and
-- flipbook flame tongues spawned on its rim and inside, upright billboards, plus a few embers.
-- One emitter of each moves its attachment and Emits, so a fire is 3-5 parts and 2 emitters.
-- Flames per second follow the rim length x ClientQuality effects: about 16 alive at the start on
-- Full, 11 on Balanced, 6 on Low/Lean (phones). Nothing spawns past 160 studs from the camera.
-- On landing: a flat amber-rimmed ring whooshes out to the start radius and the flames burst up.
-- model: the zone's Model (SpecialWeaponVisuals destroys it at ZoneEnd); position: server centre,
-- 0.15 above the ground; born: server time it started.
function T.fireZone(model,position,r0,r1,duration,born,hold)
 local tex=T.FireTextures
 local groundY=position.Y-.15
 local spin=CFrame.Angles(0,math.random()*math.pi*2,0)
 local function flat(y) return CFrame.new(position.X,groundY+y,position.Z)*spin end
 -- 1. Scorch under it all, at the start size; it stays until the fire is out.
 local scorch=K.part(model,'FireScorch',Vector3.new(r0*2.5,.05,r0*2.5),K.White,1)
 scorch.CFrame=flat(.03)
 local scorchDecal=Instance.new('Decal');scorchDecal.Face=Enum.NormalId.Top;scorchDecal.Texture=tex.Scorch;scorchDecal.Transparency=1;scorchDecal.Parent=scorch
 -- 2. The pool: the painted decal, or flat discs in the flipbook's bands until it is uploaded.
 local pool,poolDecal,discs
 if tex.Pool then
  pool=K.part(model,'FirePool',Vector3.new(1,.05,1),K.White,1)
  poolDecal=Instance.new('Decal');poolDecal.Face=Enum.NormalId.Top;poolDecal.Texture=tex.Pool;poolDecal.Transparency=1;poolDecal.Parent=pool
 else
  discs={}
  for i,b in POOL_BANDS do
   discs[i]={part=K.part(model,'FirePoolDisc',Vector3.new(.04,1,1),b[1],1,Enum.Material.Neon,Enum.PartType.Cylinder),scale=b[2],alpha=b[3],lift=.08+i*.012}
  end
 end
 -- 3 and 4. Flame tongues and embers.
 local anchor=K.part(model,'FireAnchor',Vector3.one*.1,K.White,1);anchor.CFrame=CFrame.new(position)
 local at=Instance.new('Attachment');at.Name='FireSpawn';at.Parent=anchor
 local flames=Instance.new('ParticleEmitter');flames.Name='MolotovFlames';flames.Texture=tex.Flame
 flames.FlipbookLayout=Enum.ParticleFlipbookLayout.Grid4x4;flames.FlipbookMode=Enum.ParticleFlipbookMode.OneShot
 flames.Orientation=Enum.ParticleOrientation.FacingCameraWorldUp
 flames.Lifetime=NumberRange.new(.5,.7);flames.Speed=NumberRange.new(.3,.9);flames.SpreadAngle=Vector2.new(10,10)
 flames.EmissionDirection=Enum.NormalId.Top;flames.Acceleration=Vector3.new(0,1.5,0)
 flames.Rotation=NumberRange.new(-6,6);flames.RotSpeed=NumberRange.new(0,0)
 flames.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,.05),NumberSequenceKeypoint.new(.8,.1),NumberSequenceKeypoint.new(1,.5)})
 -- LightInfluence 0: the blue sky fill would turn the orange mustard (game lighting shifts colours).
 flames.LightEmission=.25;flames.LightInfluence=0;flames.ZOffset=.3;flames.Rate=0;flames.Enabled=false;flames.Parent=at
 local embers=Instance.new('ParticleEmitter');embers.Name='MolotovEmbers';embers.Texture=tex.Ember
 embers.Size=NumberSequence.new(.3,0);embers.Lifetime=NumberRange.new(.8,1.2);embers.Speed=NumberRange.new(2,4)
 embers.SpreadAngle=Vector2.new(20,20);embers.EmissionDirection=Enum.NormalId.Top;embers.Acceleration=Vector3.new(0,1,0);embers.Drag=.6
 embers.LightEmission=1;embers.LightInfluence=0;embers.Rate=0;embers.Enabled=false;embers.Parent=at
 local function tongueSize(r) return math.clamp(1.4+.11*r,1.6,2.6) end -- studs: 2.2 at 7.2, 1.8 at 3.6
 local function emitFlames(r,count,inner)
  local s=tongueSize(r)
  flames.Size=NumberSequence.new(s*.8,s)
  for _=1,count do
   local angle=math.random()*math.pi*2
   local distance=inner and r*.7*math.sqrt(math.random()) or r*(.8+math.random()*.17)
   -- The flipbook's flame sits in the lower part of each frame: lift so its base is on the ground.
   at.WorldPosition=Vector3.new(position.X+math.cos(angle)*distance,groundY+s*.3,position.Z+math.sin(angle)*distance)
   flames:Emit(1)
  end
 end
 -- Landing: the ignition ring out to the full start radius and a burst of tongues (when on screen).
 local near=K.near(position,160)
 if near and workspace:GetServerTimeNow()-born<.3 then
  K.ring(model,CFrame.new(position.X,groundY+.08,position.Z),{radius0=r0*.35,radius1=r0,width=.8,color=FLAME[1],rim=K.Amber,bodyAlpha=.5,duration=.38,segments=20})
  emitFlames(r0,math.max(2,math.floor(10*Q.get().effects)),true)
 end
 local spawnFlames,spawnEmbers,lastAge,checkNear=0,0,0,os.clock()+.5
 K.animate(math.max(.1,born+duration-workspace:GetServerTimeNow())+.05,function(_,age)
  if not model.Parent then return true end
  local now=workspace:GetServerTimeNow()
  local life=now-born
  local r=Motion.zoneRadius(r0,r1,life,duration,hold)
  -- Fade in over 0.15 s, out over the last 0.6 s (tongues stop then and finish their flipbook).
  local hidden=math.max(1-math.clamp(life/.15,0,1),math.clamp(1-(born+duration-now)/.6,0,1))
  scorchDecal.Transparency=.15+.85*hidden
  if pool then
   local d=r*2*1.08 -- the painted rim's tongues reach past the hit edge a little, its valleys inside
   pool.Size=Vector3.new(d,.05,d);pool.CFrame=flat(.06);poolDecal.Transparency=.05+.95*hidden
  else
   for _,disc in discs do
    local d=r*2*disc.scale
    disc.part.Size=Vector3.new(.04,d,d);disc.part.CFrame=flat(disc.lift)*CFrame.Angles(0,0,math.pi/2)
    disc.part.Transparency=disc.alpha+(1-disc.alpha)*hidden
   end
  end
  local dt=math.clamp(age-lastAge,0,.1);lastAge=age
  if os.clock()>=checkNear then near=K.near(position,160);checkNear=os.clock()+.5 end
  if near and now<born+duration-.6 then
   local q=Q.get().effects
   local rim,inner=2.6*r,.12*r*r -- per second: 18.7 + 6.2 at 7.2 studs, 9.4 + 1.6 at 3.6
   spawnFlames+=(rim+inner)*q*dt;spawnEmbers+=4*q*dt
   while spawnFlames>=1 do spawnFlames-=1;emitFlames(r,1,math.random()>=rim/(rim+inner)) end
   while spawnEmbers>=1 do
    spawnEmbers-=1
    local angle=math.random()*math.pi*2;local distance=r*.8*math.sqrt(math.random())
    at.WorldPosition=Vector3.new(position.X+math.cos(angle)*distance,groundY+.6,position.Z+math.sin(angle)*distance)
    embers:Emit(1)
   end
  end
 end,function() model:Destroy() end,'fireZone',24)
end
return T
