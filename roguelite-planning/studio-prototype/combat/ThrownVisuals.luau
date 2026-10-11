-- Trails and landing effects for modeled throws (SpecialWeapons flights).
-- Kept light: short transparent trails, one small signature impact each.
local K=require(script.Parent:WaitForChild('VfxKit'))
local Q=require(script.Parent:WaitForChild('ClientQuality'))
local Motion=require(script.Parent:WaitForChild('SpecialMotion'))
local T={}
-- Molotov fire textures, all already uploaded: Flame, Scorch, Ember and Smoke are the boss kit's painted
-- sprites (BossVfxAssets; LegendaryVisuals uses them too), Glow is GodlySoftGlow (white on clear,
-- tinted). Pool (MolotovFirePool.png, uploaded 2026-10-10) is no longer drawn: the opaque pool read
-- as a sticker on uneven ground (play-test, 2026-10-10); kept for reference only.
T.FireTextures={Flame='rbxassetid://132081298787809',Scorch='rbxassetid://92423458342016',Ember='rbxassetid://116159534169534',
 Smoke='rbxassetid://133683398795549',Glow='rbxassetid://119796255132573',Pool='rbxassetid://121830714730465'}
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
-- Molotov fire (2026-10-10 rework; SpecialWeaponVisuals 'Zone'). Play-test of the first version: "fire
-- effects are hella 2D, especially on the floor, and clips hella" (an opaque pool decal lying on
-- uneven grass like a sticker, upright flame cards slicing into the ground). Now it has no flat
-- shape of its own; every piece is a soft sprite placed on its own ground raycast:
--   scorch: 7 small ScorchMark decals, each on its own ground hit and tilted to it, so terrain
--     bumps can't cut one big plate; faint (they are a burn mark, not the fire)
--   heat glow: soft additive glow sprites lying flat (VelocityPerpendicular) on ground hits inside
--     the current radius, short-lived and re-spawned, so the glow flickers and shrinks with the fire
--   flames: the flame flipbook as camera-facing particles (never show an edge), each lifted so its
--     painted base sits just above its ground hit, ZOffset toward the camera so a slope or grass
--     can't slice it, random size and squash per tongue, a glow blob under the base hides its edge
--   height: embers that rise 3-5 studs, heat sparks, and a little grey smoke above
--   light: one warm PointLight per fire, low and shrinking with it, at most 3 fires lit at once
--     (none on Low/Lean, ClientQuality lights)
-- Everything scales with the server's radius every frame (SpecialMotion.zoneRadius, the same curve
-- the damage ticks use) and ClientQuality effects: about 16 tongues alive at the start on Full, 11
-- on Balanced, 6 on Low/Lean (phones). Nothing spawns past 160 studs from the camera.
-- On landing: a flat amber-rimmed ring whooshes out to the start radius and the flames burst up.
-- model: the zone's Model (SpecialWeaponVisuals destroys it at ZoneEnd); position: server centre,
-- 0.15 above the ground; born: server time it started.
local fireLights=0
local FIRE_LIGHT=Color3.fromRGB(255,146,58)
local GLOW={Color3.fromRGB(255,170,64),Color3.fromRGB(226,78,20)}
local SMOKE=Color3.fromRGB(92,84,80)
local function seq(...) local k={};local a={...};for i=1,#a,3 do k[#k+1]=NumberSequenceKeypoint.new(a[i],a[i+1],a[i+2] or 0) end;return NumberSequence.new(k) end
function T.fireZone(model,position,r0,r1,duration,born,hold)
 local tex=T.FireTextures
 local groundY=position.Y-.15
 -- Ground probe: players, enemies and effect folders are not ground.
 local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude;params.IgnoreWater=true
 local exclude={model.Parent or model}
 for _,p in game:GetService('Players'):GetPlayers() do if p.Character then exclude[#exclude+1]=p.Character end end
 local enemies=workspace:FindFirstChild('RogueliteEnemies');if enemies then exclude[#exclude+1]=enemies end
 params.FilterDescendantsInstances=exclude
 -- Ground point and normal under (x, z); falls back to the landing height on a miss.
 local function ground(x,z)
  local hit=workspace:Raycast(Vector3.new(x,groundY+4,z),-Vector3.yAxis*9,params)
  if hit then return hit.Position,hit.Normal end
  return Vector3.new(x,groundY,z),Vector3.yAxis
 end
 local function around(r,inner)
  local angle=math.random()*math.pi*2
  local distance=inner and r*.75*math.sqrt(math.random()) or r*(.8+math.random()*.17)
  return position.X+math.cos(angle)*distance,position.Z+math.sin(angle)*distance
 end
 -- 1. Scorch: small decals, each on its own ground hit and tilted to it.
 local scorches={}
 for i=1,7 do
  local angle=i*2.39996;local distance=i==1 and 0 or r0*.55
  local at,normal=ground(position.X+math.cos(angle)*distance,position.Z+math.sin(angle)*distance)
  local right=normal:Cross(Vector3.new(math.cos(angle*3),0,math.sin(angle*3)));if right.Magnitude<.05 then right=Vector3.xAxis end
  local size=r0*(i==1 and 1.3 or 1.05)
  local plate=K.part(model,'FireScorch',Vector3.new(size,.04,size),K.White,1)
  plate.CFrame=CFrame.fromMatrix(at+normal*.06,right.Unit,normal)
  local d=Instance.new('Decal');d.Face=Enum.NormalId.Top;d.Texture=tex.Scorch;d.Transparency=1;d.Parent=plate
  scorches[i]=d
 end
 -- 2-4. One spawn point, several emitters; each Emit moves the attachment to a ground hit first.
 local anchor=K.part(model,'FireAnchor',Vector3.one*.1,K.White,1);anchor.CFrame=CFrame.new(position)
 local at=Instance.new('Attachment');at.Name='FireSpawn';at.Parent=anchor
 local function emitter(name,texture)
  local e=Instance.new('ParticleEmitter');e.Name=name;e.Texture=texture;e.Rate=0;e.Enabled=false
  e.EmissionDirection=Enum.NormalId.Top;e.LightInfluence=0;e.Parent=at
  return e
 end
 local flames=emitter('MolotovFlames',tex.Flame)
 flames.FlipbookLayout=Enum.ParticleFlipbookLayout.Grid4x4;flames.FlipbookMode=Enum.ParticleFlipbookMode.OneShot
 flames.Orientation=Enum.ParticleOrientation.FacingCamera
 flames.Lifetime=NumberRange.new(.45,.75);flames.Speed=NumberRange.new(.4,1.1);flames.SpreadAngle=Vector2.new(8,8)
 flames.Acceleration=Vector3.new(0,2,0);flames.Rotation=NumberRange.new(-8,8);flames.RotSpeed=NumberRange.new(-10,10)
 -- Flicker: each tongue squashes a little differently as it burns (envelopes randomise per particle).
 flames.Squash=seq(0,0,0, .5,.12,.1, 1,-.08,0)
 flames.Transparency=seq(0,.15,0, .2,0,0, .8,.08,0, 1,.6,0)
 -- Pushed toward the camera so a slope, a bump or grass never slices a tongue.
 flames.LightEmission=.3;flames.ZOffset=1.2
 local glow=emitter('MolotovGlow',tex.Glow)
 glow.Orientation=Enum.ParticleOrientation.VelocityPerpendicular -- lies flat on the ground
 glow.Speed=NumberRange.new(.01);glow.SpreadAngle=Vector2.zero;glow.Lifetime=NumberRange.new(.7,1)
 glow.Color=ColorSequence.new(GLOW[1],GLOW[2]);glow.LightEmission=1;glow.ZOffset=.5
 glow.Transparency=seq(0,1,0, .25,.55,.1, .7,.65,.1, 1,1,0);glow.Rotation=NumberRange.new(0,360)
 local embers=emitter('MolotovEmbers',tex.Ember)
 embers.Size=seq(0,.32,.08, 1,0,0);embers.Lifetime=NumberRange.new(1,1.6);embers.Speed=NumberRange.new(2.5,4.5)
 embers.SpreadAngle=Vector2.new(18,18);embers.Acceleration=Vector3.new(0,.8,0);embers.Drag=.5;embers.LightEmission=1;embers.ZOffset=.8
 local smoke=emitter('MolotovSmoke',tex.Smoke)
 smoke.FlipbookLayout=Enum.ParticleFlipbookLayout.Grid4x4;smoke.FlipbookMode=Enum.ParticleFlipbookMode.OneShot
 smoke.Color=ColorSequence.new(SMOKE);smoke.LightInfluence=.6;smoke.LightEmission=0
 smoke.Lifetime=NumberRange.new(1.2,1.6);smoke.Speed=NumberRange.new(2,3);smoke.SpreadAngle=Vector2.new(12,12)
 smoke.Acceleration=Vector3.new(0,.5,0);smoke.Drag=.4;smoke.Rotation=NumberRange.new(0,360);smoke.RotSpeed=NumberRange.new(-20,20)
 smoke.Transparency=seq(0,1,0, .25,.62,0, 1,1,0)
 local function tongueSize(r) return math.clamp(1.4+.11*r,1.6,2.6) end -- studs: 2.2 at 7.2, 1.8 at 3.6
 -- A tongue: the flipbook's flame fills the lower part of each frame (bottom ~0.4 of its size below
 -- the centre), so lift it that much plus a little; a glow blob sits under its base.
 local function emitFlame(r,inner)
  local s=tongueSize(r)
  flames.Size=seq(0,s*.8,s*.18, 1,s,s*.18)
  local x,z=around(r,inner);local g=ground(x,z)
  at.WorldPosition=g+Vector3.yAxis*(s*.42+.15);flames:Emit(1)
 end
 local function emitGlow(r,x,z)
  local g=ground(x,z);local s=math.clamp(r*.9,2.2,6)
  glow.Size=seq(0,s*.8,s*.15, 1,s,s*.15)
  at.WorldPosition=g+Vector3.yAxis*.12;glow:Emit(1)
 end
 -- 5. The warm light (Balanced and up; at most 3 fires lit at once).
 local light
 if Q.get().lights>0 and fireLights<3 then
  fireLights+=1
  light=Instance.new('PointLight');light.Color=FIRE_LIGHT;light.Shadows=false;light.Brightness=0;light.Range=r0*1.8;light.Parent=anchor
  anchor.CFrame=CFrame.new(position+Vector3.yAxis*1.5)
 end
 local near=K.near(position,160)
 local spawnFlames,spawnGlow,spawnEmbers,spawnSmoke,lastAge,checkNear=0,0,0,0,0,os.clock()+.5
 K.animate(math.max(.1,born+duration-workspace:GetServerTimeNow())+.05,function(_,age)
  if not model.Parent then return true end
  local now=workspace:GetServerTimeNow()
  local life=now-born
  local r=Motion.zoneRadius(r0,r1,life,duration,hold)
  -- Fade in over 0.15 s, out over the last 0.6 s (sprites stop spawning then and finish their life).
  local hidden=math.max(1-math.clamp(life/.15,0,1),math.clamp(1-(born+duration-now)/.6,0,1))
  for _,d in scorches do d.Transparency=.45+.55*hidden end
  if light then
   light.Range=r*1.8+2;light.Brightness=(1-hidden)*(1.1+.25*math.sin(now*17)*math.sin(now*7.3))
  end
  local dt=math.clamp(age-lastAge,0,.1);lastAge=age
  if os.clock()>=checkNear then near=K.near(position,160);checkNear=os.clock()+.5 end
  if near and now<born+duration-.6 then
   local q=Q.get().effects
   local rim,inner=2.6*r,.12*r*r -- per second: 18.7 + 6.2 at 7.2 studs, 9.4 + 1.6 at 3.6
   spawnFlames+=(rim+inner)*q*dt;spawnGlow+=(2+.8*r)*q*dt;spawnEmbers+=6*q*dt;spawnSmoke+=1.6*q*dt
   while spawnFlames>=1 do spawnFlames-=1;emitFlame(r,math.random()>=rim/(rim+inner)) end
   while spawnGlow>=1 do spawnGlow-=1;local x,z=around(r,true);emitGlow(r,x,z) end
   while spawnEmbers>=1 do
    spawnEmbers-=1;local x,z=around(r,true)
    at.WorldPosition=ground(x,z)+Vector3.yAxis*.8;embers:Emit(1)
   end
   while spawnSmoke>=1 do
    spawnSmoke-=1;local x,z=around(r*.6,true)
    local s=math.clamp(r*.5,1.6,3.2);smoke.Size=seq(0,s*.6,0, 1,s*1.4,0)
    at.WorldPosition=ground(x,z)+Vector3.yAxis*(2.2+math.random());smoke:Emit(1)
   end
  end
 end,function()
  if light then fireLights=math.max(0,fireLights-1);light=nil end
  model:Destroy()
 end,'fireZone',24)
 -- Landing (after the cleanup is registered, so a throw here strands nothing): the ignition ring
 -- out to the full start radius and a burst of tongues (when on screen).
 if near and workspace:GetServerTimeNow()-born<.3 then
  K.ring(model,CFrame.new(position.X,groundY+.2,position.Z),{radius0=r0*.35,radius1=r0,width=.8,color=FLAME[1],rim=K.Amber,bodyAlpha=.5,duration=.38,segments=20})
  for _=1,math.max(2,math.floor(10*Q.get().effects)) do emitFlame(r0,true) end
  for _=1,math.max(2,math.floor(5*Q.get().effects)) do local x,z=around(r0,true);emitGlow(r0,x,z) end
 end
end
return T
