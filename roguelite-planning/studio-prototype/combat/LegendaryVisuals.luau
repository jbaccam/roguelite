-- Legendary weapon presentation (RARITY_GODLY_ARMOR.md §8, plan J item 8). Client only; never
-- affects hits. Every Legendary floats with a faint gold glint; at Tier IV, when its move is live, it
-- wears the full gold aura (haze, star motes, light), which builds as the slot's LegendaryCharge
-- counts toward the move, shimmers when the move is next, and flares when it fires.
-- Server events arrive on LegendaryFX (LegendaryMoves):
--   Slash  Katana: a white crescent with an amber glow flies out and cuts a line of enemies
--   Beam   Excalibur: a broader golden crescent that carries its own light
--   Flush  Deck of Cards: "ROYAL FLUSH!", five gold cards (10 J Q K A of spades) fan out and fly
--   Split  Rocket Launcher: the rocket bursts into three homing mini rockets
--   Strike Bowling Ball: "STRIKE!", ten pins burst out of a dust ring
--   Shock  Wrecking Ball: a dust shockwave with an amber dashed rim rolls over cracked ground
--   Thunder Mjolnir: a target ring charges, then a forked lightning bolt drops on it
--   Roll   Pizza Cutter: a ghost wheel rolls down its lane on its rim, cutting a thin slice line into the ground
-- Drawn in the game's own flat effect language (user, 2026-10-02: no "3d and model heavy" effects):
-- crescents are flat Neon segments with the white/amber dashed rim (VfxKit.ring, like every swing),
-- rings are the painted ShockwaveRing texture on the ground, dust is VfxKit.cloud and the painted
-- flipbooks, sparks and cuts are the painted Star/Slash textures. Real objects an effect throws
-- (cards, the rocket, bowling pins) are props. Effects far from the camera are skipped.
-- Sandboxed like the combat client that requires it: no sounds here (RogueliteSounds plays them).
local RunService=game:GetService('RunService')
local Players=game:GetService('Players')
local TweenService=game:GetService('TweenService')
local Catalog=require(script.Parent:WaitForChild('WeaponCatalog'))
local K=require(script.Parent:WaitForChild('VfxKit'))
local Presentation=require(script.Parent:WaitForChild('CombatPresentationPolicy'))
local V={}
local function rgb(r,g,b) return Color3.fromRGB(r,g,b) end
-- Painted effect textures already in the game (GodlyVisuals, BossVfxAssets); white on clear, tinted here.
local TEX={
 Glow='rbxassetid://119796255132573',Slash='rbxassetid://105397482701607',Lightning='rbxassetid://100197465776159',
 Ring='rbxassetid://73745779894728',Star='rbxassetid://132900122818559',Smoke='rbxassetid://133683398795549',
 Ember='rbxassetid://116159534169534',Dust='rbxassetid://108391383565832',Scorch='rbxassetid://92423458342016',
 Cracks='rbxassetid://79279164324150',
}
V.Textures=TEX
-- Legendary gold (ChestConfig.RarityColor.Legendary) with a white-hot core and a deep amber.
local GOLD,HOT,DEEP,AMBER=rgb(255,196,60),rgb(255,240,190),rgb(170,92,8),K.Amber
local STEEL=rgb(226,240,255) -- the Katana's cutting edge
local SKY,BOLT=rgb(122,196,255),rgb(246,251,255) -- Mjolnir's lightning (VfxKit.Lightning)
local DUST,CRACK=K.Dust,rgb(70,52,36)
V.Gold=GOLD
local smooth=K.smooth
local function seq(...) local k={};local a={...};for i=1,#a,2 do k[#k+1]=NumberSequenceKeypoint.new(a[i],a[i+1]) end;return NumberSequence.new(k) end
local function emitter(parent,o)
 local e=Instance.new('ParticleEmitter');e.Name=o.name or 'LegendaryFx'
 e.Texture=o.texture or TEX.Glow
 e.Color=ColorSequence.new(o.color or K.White,o.color2 or o.color or K.White)
 e.Size=typeof(o.size)=='NumberSequence' and o.size or seq(0,o.size or 1,1,o.size1 or 0)
 e.Transparency=o.alpha or seq(0,.2,.7,.55,1,1)
 e.Lifetime=NumberRange.new(o.life or .6,o.life1 or o.life or .6);e.Speed=NumberRange.new(o.speed or 1,o.speed1 or o.speed or 1)
 e.SpreadAngle=Vector2.new(o.spread or 180,o.spread or 180);e.Rate=o.rate or 0
 e.Acceleration=o.accel or Vector3.zero;e.Drag=o.drag or 0
 e.Rotation=NumberRange.new(0,360);e.RotSpeed=NumberRange.new(-(o.spin or 40),o.spin or 40)
 e.LightEmission=o.light or 1;e.LightInfluence=o.influence or 0;e.ZOffset=o.zoffset or 0
 e.EmissionDirection=o.direction or Enum.NormalId.Top
 if o.shape then e.Shape=o.shape;e.ShapeStyle=Enum.ParticleEmitterShapeStyle.Volume end
 if o.flipbook then e.FlipbookLayout=Enum.ParticleFlipbookLayout.Grid4x4;e.FlipbookMode=Enum.ParticleFlipbookMode.OneShot end
 e.Enabled=o.enabled==true;e.Parent=parent
 return e
end
-- One-shot particle burst at a point; its holder cleans itself up.
local function burst(folder,position,o,count)
 local holder=K.part(folder,'LegendaryBurst',Vector3.one*.05,K.White,1)
 holder.CFrame=CFrame.lookAt(position,position+(o.facing or Vector3.yAxis))
 local e=emitter(holder,o);e.EmissionDirection=Enum.NormalId.Front
 e:Emit(count or 10)
 K.animate((o.life1 or o.life or .6)+.15,function() end,function() holder:Destroy() end,'legendBurst',64)
end
local function groundY(position)
 local exclude={}
 for _,p in Players:GetPlayers() do if p.Character then exclude[#exclude+1]=p.Character end end
 local enemies=workspace:FindFirstChild('RogueliteEnemies');if enemies then exclude[#exclude+1]=enemies end
 return K.groundBelow(position,exclude,position.Y-2.5)
end
-- A flat decal plate on the ground (scorch, cracks, target ring) that fades in, holds, fades out.
local function decal(folder,position,texture,color,size,fadeIn,hold,fadeOut,spin)
 local p=K.part(folder,'LegendaryDecal',Vector3.new(size,.05,size),K.White,1)
 p.CFrame=CFrame.new(position)*CFrame.Angles(0,math.random()*math.pi*2,0)
 local d=Instance.new('Decal');d.Face=Enum.NormalId.Top;d.Texture=texture;d.Color3=color;d.Transparency=1;d.Parent=p
 K.animate(fadeIn+hold+fadeOut,function(_,age)
  d.Transparency=age<fadeIn and 1-age/fadeIn or age<fadeIn+hold and 0 or smooth((age-fadeIn-hold)/fadeOut)
  if spin then p.CFrame*=CFrame.Angles(0,spin/60,0) end
 end,function() p:Destroy() end,'legendDecal',32)
 return p,d
end
-- World headlines stay proportional at distance and within each viewer's viewport cap.
local function headline(folder,position,text,face,stroke,size,follow)
 local anchor=K.part(folder,'LegendaryHeadline',Vector3.one*.1,K.White,1);anchor.Position=position
 local gui=Instance.new('BillboardGui');gui.Name='AttackHeadline';gui.AlwaysOnTop=true;gui.MaxDistance=Presentation.HeadlineDistance;gui.LightInfluence=0;gui.Enabled=false;gui.Parent=anchor
 local label=Instance.new('TextLabel');label.Size=UDim2.fromScale(1,1);label.BackgroundTransparency=1;label.Text=text
 label.Font=Enum.Font.FredokaOne;label.TextScaled=true;label.TextColor3=K.White;label.TextStrokeTransparency=1;label.Parent=gui
 local limit=Instance.new('UITextSizeConstraint');limit.MinTextSize=1;limit.Parent=label
 local grad=Instance.new('UIGradient');grad.Rotation=90;grad.Color=ColorSequence.new(face[1],face[2]);grad.Parent=label
 local outline=Instance.new('UIStroke');outline.Color=stroke;outline.LineJoinMode=Enum.LineJoinMode.Round;outline.Parent=label
 local function layout(age)
  local camera=workspace.CurrentCamera
  if not camera then gui.Enabled=false;return end
  local depth=-camera.CFrame:PointToObjectSpace(anchor.Position).Z
  local d=Presentation.headline(camera.ViewportSize,depth,camera.FieldOfView,size,age)
  gui.Enabled=d.visible;gui.Size=UDim2.fromOffset(d.width,d.height)
  limit.MaxTextSize=d.text;outline.Thickness=d.stroke
 end
 layout(0)
 label.Rotation=-9
 TweenService:Create(label,TweenInfo.new(.35,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Rotation=0}):Play()
 K.animate(1.25,function(_,age)
  if not anchor.Parent then return true end
  local base=follow and follow() or position
  anchor.Position=base+Vector3.yAxis*(age>.75 and (age-.75)*4 or 0)
  layout(age)
  local fade=smooth((age-.85)/.4)
  label.TextTransparency=fade;outline.Transparency=fade
 end,function() anchor:Destroy() end,'legendText',6)
end
local function npcRoot(npc) return npc and npc.Parent and npc:FindFirstChild('HumanoidRootPart') end
local function enemyRoots()
 local list={};local folder=workspace:FindFirstChild('RogueliteEnemies')
 if folder then for _,npc in folder:GetChildren() do local r=npc:FindFirstChild('HumanoidRootPart');if r then list[#list+1]={npc=npc,root=r} end end end
 return list
end
-- Camera kick for big moves, only for the one who made them, off with the Screen shake setting.
local shake={untilT=0,start=0,strength=0,offset=CFrame.identity,camera=nil}
RunService:BindToRenderStep('LegendaryShakeRestore',Enum.RenderPriority.Camera.Value-3,function()
 if shake.camera and shake.camera==workspace.CurrentCamera then shake.camera.CFrame*=shake.offset:Inverse() end
 shake.offset=CFrame.identity;shake.camera=nil
end)
RunService:BindToRenderStep('LegendaryShake',Enum.RenderPriority.Camera.Value+3,function()
 local now=os.clock();local camera=workspace.CurrentCamera
 if now>=shake.untilT or not camera or camera.CameraType==Enum.CameraType.Scriptable then return end
 local age=now-shake.start;local e=math.clamp((shake.untilT-now)/(shake.untilT-shake.start),0,1)^2*shake.strength
 shake.offset=CFrame.new(math.sin(age*97)*.14*e,math.sin(age*121)*.1*e,0)*CFrame.Angles(0,0,math.rad(math.sin(age*79)*.5*e))
 camera.CFrame*=shake.offset;shake.camera=camera
end)
local function kick(ownerId,strength,seconds)
 local me=Players.LocalPlayer
 if ownerId~=me.UserId or me:GetAttribute('Setting_ScreenShake')==false then return end
 local now=os.clock()
 if now<shake.untilT and strength<shake.strength then return end
 shake.start,shake.untilT,shake.strength=now,now+seconds,strength
end

function V.mount(combat,folder,lookup,options)
 options=options or {}
 local stopPreview
 local K=K
 local task=task
 if options.preview then K,stopPreview,task=require(script.Parent:WaitForChild('WeaponShowcaseScope')).new(K,folder) end
 local enemyRoots = options.preview and function()
  local roots={}
  for _,npc in options.targets or {} do local root=npcRoot(npc);if root then roots[#roots+1]={npc=npc,root=root} end end
  return roots
 end or enemyRoots
 local api={}
 -- The gold aura -------------------------------------------------------------------------------
 function api.attach(v,id,template,slot)
  local spec=Catalog.Legendary[id];if not spec then return end
  local g={spec=spec,slot=slot,emitters={},phase=math.random()*6,charge=0,flareAt=-1e6}
  local parts={}
  for _,p in v.model:GetDescendants() do if p:IsA('BasePart') and p.Material~=Enum.Material.Neon then parts[#parts+1]=p end end
  if #parts==0 then return end
  local body=parts[1];g.body=body
  local light=Instance.new('PointLight');light.Color=GOLD;light.Range=7;light.Brightness=0;light.Shadows=false;light.Parent=body;g.light=light
  for _,part in parts do
   g.emitters[#g.emitters+1]={kind='haze',e=emitter(part,{name='LegendaryHaze',texture=TEX.Glow,color=GOLD,color2=DEEP,size=seq(0,.45,.4,1.15,1,1.5),
    alpha=seq(0,1,.25,.74,1,1),life=.7,life1=1.1,speed=.2,speed1=.6,shape=Enum.ParticleEmitterShape.Box,light=1})}
   g.emitters[#g.emitters+1]={kind='motes',e=emitter(part,{name='LegendaryMotes',texture=TEX.Star,color=HOT,color2=GOLD,size=seq(0,.2,.6,.26,1,0),
    alpha=seq(0,.05,.7,.25,1,1),life=.9,life1=1.5,speed=.3,speed1=1,accel=Vector3.yAxis*1.6,shape=Enum.ParticleEmitterShape.Box,light=1,spin=90})}
  end
  g.parts=#parts
  v.legendary=g
 end
 function api.hide(v)
  local g=v.legendary;if not g then return end
  for _,x in g.emitters do x.e.Enabled=false end
  g.light.Enabled=false
 end
 -- frame: {visible,active,age,...} from the combat client's render loop.
 function api.step(v,pivot,frame)
  local g=v.legendary;if not g then return end
  local now=os.clock()
  local tier=g.slot and g.slot:GetAttribute('Tier') or 1
  local live=tier>=4
  local near=frame.visible and K.near(pivot.Position,70)
  -- How close the move is: 0 just after it, 1 when the next attack is the move.
  local every=g.spec.every
  local charge=g.slot and g.slot:GetAttribute('LegendaryCharge') or 0
  if live and every and every>1 and charge<g.charge then g.flareAt=now end -- the count wrapped: the move fired
  g.charge=charge
  local k=(every and every>1) and math.clamp(charge/(every-1),0,1) or .55
  local primed=live and every and every>1 and charge==every-1
  local flare=math.clamp(1-(now-g.flareAt)/.45,0,1)
  local breath=.5+.5*math.sin(now*(primed and 9 or 3.4)+g.phase)
  for _,x in g.emitters do
   local rate=0
   if near then
    if x.kind=='haze' then rate=live and (2.5+6*k+(primed and 4 or 0)+18*flare) or 0
    else rate=live and (1.5+4*k+(primed and 5 or 0)+30*flare) or .7 end -- a faint glint below Tier IV
   end
   rate/=g.parts
   if x.e.Rate~=rate then x.e.Rate=rate end
   local on=rate>0
   if x.e.Enabled~=on then x.e.Enabled=on end
  end
  g.light.Enabled=frame.visible and live
  if live then
   g.light.Brightness=.8+1.2*k+(primed and 1.2*breath or .4*breath)+4*flare
   g.light.Range=6+4*k+6*flare
  end
  if flare>.95 and near and g.flared~=g.flareAt then
   g.flared=g.flareAt
   burst(folder,pivot.Position,{texture=TEX.Star,color=K.White,color2=GOLD,size=seq(0,.9,1,0),alpha=seq(0,0,1,1),life=.35,life1=.5,speed=7,speed1=11,spread=180,light=1},12)
  end
 end

 -- Cut flashes on the enemies a mover passes (visual only; the server decided the hits) ----------
 local function cutFlash(position,direction,color)
  if not K.near(position,140) then return end
  local side=Vector3.yAxis:Cross(direction);if side.Magnitude<.01 then side=Vector3.xAxis end
  burst(folder,position,{texture=TEX.Slash,color=K.White,color2=color,size=seq(0,1.6,.35,2.6,1,2.9),alpha=seq(0,0,.6,.25,1,1),
   life=.16,speed=0,spread=0,light=1,spin=0,facing=side.Unit},1)
  K.shards(folder,position,color,4,9,.3,.12)
 end
 -- Passing-enemy check for a mover from a to b, `half` wide; marks each enemy once.
 local function passing(a,b,half,seen,limit,onEnemy)
  for _,e in enemyRoots() do
   if not seen[e.npc] and limit.n>0 then
    local p=e.root.Position
    local ab=Vector3.new(b.X-a.X,0,b.Z-a.Z);local ap=Vector3.new(p.X-a.X,0,p.Z-a.Z)
    local len2=ab:Dot(ab);local t=len2>1e-6 and math.clamp(ap:Dot(ab)/len2,0,1) or 0
    if (ap-ab*t).Magnitude<=half+1 and math.abs(p.Y-a.Y)<7 then seen[e.npc]=true;limit.n-=1;onEnemy(p) end
   end
  end
 end

 -- A ground shockwave in the Trident's language (GodlyVisuals.shockwave): the painted ShockwaveRing
 -- texture on a flat disc, growing fast and fading.
 local function groundRing(position,color,radius0,radius1,duration,alpha,texture)
  local p=K.part(folder,'LegendaryRing',Vector3.new(.06,1,1),color,1,Enum.Material.SmoothPlastic,Enum.PartType.Cylinder)
  p.CFrame=CFrame.new(position)*CFrame.Angles(0,0,math.pi/2)
  local d=Instance.new('Decal');d.Texture=texture or TEX.Ring;d.Color3=color;d.Transparency=alpha or 0;d.Face=Enum.NormalId.Right;d.Parent=p
  K.animate(duration,function(t)
   local e=1-(1-t)^3;local r=radius0+(radius1-radius0)*e
   p.Size=Vector3.new(.06,r*2,r*2);d.Transparency=(alpha or 0)+(1-(alpha or 0))*smooth((t-.35)/.65)
  end,function() p:Destroy() end,'legendRing',16)
 end
 -- Painted dust kicked up off the ground (BossVfxAssets DustPuff flipbook).
 local function dust(position,size,count)
  burst(folder,position,{texture=TEX.Dust,flipbook=true,color=DUST,color2=rgb(236,228,214),size=seq(0,size*.6,1,size*1.4),alpha=seq(0,.15,.6,.45,1,1),
   life=.55,life1=.8,speed=2,speed1=5,spread=70,accel=Vector3.yAxis*1.5,light=0,influence=.8},count or 3)
 end

 -- Slash (Katana) and Beam (Excalibur) ------------------------------------------------------------
 -- A flying crescent built exactly like every swing's crescent (VfxKit.ring): flat Neon segments,
 -- thick in the middle and pointed at the tips, a white/amber dashed rim on the leading edge, plus a
 -- soft wider glow under it. It flies just off the ground, flat, like the swing it came from.
 local SEGMENTS,HALF=12,math.rad(74)
 local function newCrescent(bodyColor,rimColor,glowColor)
  local list={}
  for i=1,SEGMENTS do
   list[i]={
    glow=K.part(folder,'CrescentGlow',Vector3.new(.1,.04,.1),glowColor,1,Enum.Material.Neon),
    body=K.part(folder,'CrescentBody',Vector3.new(.1,.05,.1),bodyColor,1,Enum.Material.Neon),
    rim=K.part(folder,'CrescentRim',Vector3.new(.1,.06,.1),(i%2==0) and K.White or rimColor,1,Enum.Material.Neon),
   }
  end
  return list
 end
 -- frame: the centre of the crescent's circle, facing the way it flies. fade 0..1.
 local function placeCrescent(list,frame,radius,thickness,fade)
  local span=2*HALF/SEGMENTS
  local chord=2*radius*math.sin(span/2)*1.08
  for i,s in list do
   local angle=-HALF+span*(i-.5)
   local w=math.cos(angle/HALF*math.pi/2)^1.15 -- pointed tips
   local thick=math.max(.06,thickness*w)
   -- The yaw convention matches VfxKit.ring: lookVector=(-sin,0,-cos).
   local direction=Vector3.new(-math.sin(angle),0,-math.cos(angle))
   local mid=math.max(.05,radius-thick*.5)
   s.body.Size=Vector3.new(chord,.05,thick)
   s.body.CFrame=frame*CFrame.lookAt(direction*mid,direction*mid*2)
   s.body.Transparency=.42+.58*fade
   local glowAt=math.max(.05,radius-thick*1.05)
   s.glow.Size=Vector3.new(chord*1.04,.04,thick*2.3)
   s.glow.CFrame=frame*CFrame.lookAt(direction*glowAt,direction*glowAt*2)+Vector3.new(0,-.03,0)
   s.glow.Transparency=.74+.26*fade
   s.rim.Size=Vector3.new(chord,.07,math.max(.12,thick*.3))
   s.rim.CFrame=frame*CFrame.lookAt(direction*(radius+.02),direction*(radius+.02)*2)
   s.rim.Transparency=.06+.94*fade
  end
 end
 local function slash(kind,ownerId,start,direction,reach,speed,width,t0)
  if not K.near(start,170) then return end
  local beam=kind=='Beam'
  -- Katana: a white crescent, amber dashes. Excalibur: pale gold, gold dashes, its own light.
  local bodyColor=beam and rgb(255,236,170) or K.White
  local rimColor=beam and GOLD or AMBER
  local glowColor=beam and GOLD or rgb(255,214,150)
  local radius=width*.5
  local thickness=radius*(beam and .38 or .3)
  local duration=math.max(.12,reach/math.max(speed,1))
  local list=newCrescent(bodyColor,rimColor,glowColor)
  -- Tips leave thin wind streaks; star sparks shed off the edge; Excalibur carries light and motes.
  local carrier=K.part(folder,'SlashCarrier',Vector3.new(radius*1.9,.1,.4),K.White,1)
  local tipZ=radius*(1-math.cos(HALF)) -- the tips sit behind the leading edge
  local function tip(x)
   local a0=Instance.new('Attachment');a0.Position=Vector3.new(x,.1,tipZ);a0.Parent=carrier
   local a1=Instance.new('Attachment');a1.Position=Vector3.new(x,-.1,tipZ);a1.Parent=carrier
   local t=Instance.new('Trail');t.Attachment0=a0;t.Attachment1=a1;t.Lifetime=beam and .24 or .18;t.MinLength=.05;t.FaceCamera=true
   t.LightEmission=.35;t.LightInfluence=.15;t.Color=ColorSequence.new(K.White,glowColor);t.Transparency=seq(0,.18,.45,.5,1,1);t.WidthScale=seq(0,1,1,.25);t.Parent=carrier
  end
  tip(-radius*math.sin(HALF));tip(radius*math.sin(HALF))
  local sparks=emitter(carrier,{name='SlashSparks',texture=TEX.Star,color=K.White,color2=glowColor,size=seq(0,.3,1,0),alpha=seq(0,0,.7,.3,1,1),
   life=.22,life1=.4,speed=1,speed1=4,spread=50,rate=beam and 50 or 36,direction=Enum.NormalId.Back,light=1,shape=Enum.ParticleEmitterShape.Box,enabled=true})
  local light
  if beam then
   light=Instance.new('PointLight');light.Color=GOLD;light.Range=12;light.Brightness=2.6;light.Shadows=false;light.Parent=carrier
   emitter(carrier,{name='HolyMotes',texture=TEX.Glow,color=HOT,color2=GOLD,size=seq(0,.45,1,0),alpha=seq(0,.25,1,1),life=.45,life1=.7,speed=.5,speed1=2,
    spread=180,rate=22,accel=Vector3.yAxis*5,light=1,shape=Enum.ParticleEmitterShape.Box,enabled=true})
  end
  -- It flies just off the ground, flat, like the swing crescents; a thin slice is left behind.
  local floor=groundY(start)
  local y=math.max(floor+.6,math.min(start.Y,floor+1.4))
  local scar=K.part(folder,'SlashScar',Vector3.new(beam and .28 or .18,.04,.1),beam and GOLD or HOT,1,Enum.Material.Neon)
  K.flash(folder,start,beam and GOLD or HOT,beam and 13 or 8,beam and 3.2 or 2,.25)
  burst(folder,start,{texture=TEX.Slash,color=K.White,color2=glowColor,size=seq(0,radius*.9,.4,radius*1.5,1,radius*1.7),alpha=seq(0,0,.6,.3,1,1),
   life=.14,speed=0,spread=0,light=1,spin=0,facing=Vector3.yAxis:Cross(direction).Unit},1)
  local seen,limit={},{n=10}
  local from=Vector3.new(start.X,y,start.Z)
  local last=from
  local hold=.22 -- the slice lingers after the crescent is gone
  K.animate(duration+hold,function(_,age)
   local f=math.min(1,age/duration)
   local position=from+direction*(reach*f)
   local grow=.6+.4*smooth(f/.15) -- it unfolds as it leaves
   local fade=math.clamp(smooth((f-.75)/.25)+(age>duration and 1 or 0),0,1)
   local frame=CFrame.lookAt(position-direction*radius*grow,position)
   placeCrescent(list,frame,radius*grow,thickness*grow,fade)
   carrier.CFrame=frame*CFrame.new(0,0,-radius*grow)
   if light then light.Brightness=2.6*(1-fade) end
   sparks.Enabled=age<duration
   local length=(position-from).Magnitude
   scar.Size=Vector3.new(scar.Size.X,.04,math.max(.1,length))
   scar.CFrame=CFrame.lookAt(Vector3.new((from.X+position.X)/2,floor+.06,(from.Z+position.Z)/2),Vector3.new(position.X,floor+.06,position.Z))
   scar.Transparency=age<duration and .3 or .3+.7*smooth((age-duration)/hold)
   if age<duration then
    passing(last,position,radius,seen,limit,function(p) cutFlash(p,direction,glowColor) end)
    last=position
   end
  end,function()
   local endAt=from+direction*reach
   if K.near(endAt,150) then
    K.shards(folder,endAt,glowColor,5,9,.32,.13)
    burst(folder,endAt,{texture=TEX.Star,color=K.White,color2=glowColor,size=seq(0,.6,1,0),alpha=seq(0,0,1,1),life=.28,speed=4,speed1=8,spread=180,light=1},7)
   end
   for _,s in list do s.glow:Destroy();s.body:Destroy();s.rim:Destroy() end
   carrier:Destroy();scar:Destroy()
  end,'legendSlash',10)
 end

 -- Rolling Slice (Pizza Cutter, 2026-10-09) -------------------------------------------------------
 -- A ghost pizza-cutter wheel stands on its rim and rolls down the lane. All flat Neon pieces: a translucent
 -- pale-steel disc, a rim of dashes (steel white / tomato red) and three spokes that turn with it so the roll reads,
 -- a hub, and behind it three fading rear arcs of the rim (the crescent motion trail). A thin slice line is cut
 -- into the ground behind it and fades. Its size follows the lane: a 3-stud lane gives a 2.5-stud wheel.
 local TOMATO=rgb(232,74,52)
 local DASHES,ARCS,ARC_SEGMENTS=16,3,4
 local function roll(ownerId,start,direction,reach,speed,width,t0)
  if not K.near(start,170) then return end
  local radius=math.clamp(width*.42,1.1,3.4)
  local duration=math.max(.12,reach/math.max(speed,1))
  local floor0,floor1=groundY(start),groundY(start+direction*reach)
  local disc=K.part(folder,'RollingWheelDisc',Vector3.new(.06,1,1),STEEL,1,Enum.Material.Neon,Enum.PartType.Cylinder)
  local hub=K.part(folder,'RollingWheelHub',Vector3.new(.1,1,1),rgb(158,170,186),1,Enum.Material.Neon,Enum.PartType.Cylinder)
  local spokes,dashes,arcs={},{},{}
  for i=1,3 do spokes[i]=K.part(folder,'RollingWheelSpoke',Vector3.new(.08,1,.09),K.White,1,Enum.Material.Neon) end
  for i=1,DASHES do dashes[i]=K.part(folder,'RollingWheelRim',Vector3.new(.1,.1,.1),i%2==0 and TOMATO or K.White,1,Enum.Material.Neon) end
  for k=1,ARCS do
   arcs[k]={}
   for m=1,ARC_SEGMENTS do arcs[k][m]=K.part(folder,'RollingWheelTrail',Vector3.new(.06,.1,.1),k==1 and K.White or STEEL,1,Enum.Material.Neon) end
  end
  local core=K.part(folder,'RollingSlice',Vector3.new(.12,.04,.1),K.White,1,Enum.Material.Neon)
  local glow=K.part(folder,'RollingSliceGlow',Vector3.new(.34,.03,.1),TOMATO,1,Enum.Material.Neon)
  -- Sparks shed where the rim meets the ground.
  local contact=K.part(folder,'RollingWheelContact',Vector3.new(.3,.1,.3),K.White,1)
  local sparks=emitter(contact,{name='RollSparks',texture=TEX.Star,color=K.White,color2=TOMATO,size=seq(0,.28,1,0),alpha=seq(0,0,.7,.3,1,1),
   life=.2,life1=.35,speed=2,speed1=6,spread=40,rate=40,direction=Enum.NormalId.Back,light=1,enabled=true})
  local from=Vector3.new(start.X,floor0,start.Z)
  K.flash(folder,from+Vector3.yAxis*radius,STEEL,8,2,.25)
  burst(folder,from+Vector3.yAxis*radius,{texture=TEX.Slash,color=K.White,color2=TOMATO,size=seq(0,radius*1.2,.4,radius*1.9,1,radius*2.1),alpha=seq(0,0,.6,.3,1,1),
   life=.14,speed=0,spread=0,light=1,spin=0,facing=Vector3.yAxis:Cross(direction).Unit},1)
  dust(from+Vector3.yAxis*.3,1.1,2)
  local seen,limit={},{n=10}
  local last=from
  local hold=.3 -- the slice line lingers after the wheel is gone
  local span=2*math.pi/DASHES
  K.animate(duration+hold,function(_,age)
   local f=math.min(1,age/duration)
   local traveled=reach*f
   local floor=floor0+(floor1-floor0)*f
   local ground=Vector3.new(start.X,floor,start.Z)+direction*traveled
   local grow=.55+.45*smooth(f/.12) -- it pops up as it leaves
   local r=radius*grow
   local fade=math.clamp(smooth((f-.82)/.18)+(age>duration and 1 or 0),0,1)
   local frame=CFrame.lookAt(ground+Vector3.yAxis*(r+.05),ground+Vector3.yAxis*(r+.05)+direction)
   local spin=frame*CFrame.Angles(-traveled/radius,0,0) -- rolls forward: its top moves the way it travels
   disc.Size=Vector3.new(.06,r*2,r*2);disc.CFrame=spin;disc.Transparency=.68+.32*fade
   hub.Size=Vector3.new(.1,r*.45,r*.45);hub.CFrame=spin;hub.Transparency=.3+.7*fade
   for i,s in spokes do
    s.Size=Vector3.new(.08,r*1.75,.09);s.CFrame=spin*CFrame.Angles(i*math.pi/3,0,0);s.Transparency=.45+.55*fade
   end
   local rim=math.max(.1,r*.16);local chord=2*r*math.sin(span/2)*1.08
   for i,s in dashes do
    s.Size=Vector3.new(.1,rim,chord);s.CFrame=spin*CFrame.Angles(span*(i-.5),0,0)*CFrame.new(0,r-rim*.5,0);s.Transparency=.08+.92*fade
   end
   -- The trail: rear arcs of the rim (local +Z is behind), falling back and thinning.
   for k,arc in arcs do
    for m,s in arc do
     local a=math.rad(30+120*(m-.5)/ARC_SEGMENTS)
     s.Size=Vector3.new(.06,math.max(.06,rim*(1-.25*k)),2*r*math.sin(math.rad(60/ARC_SEGMENTS))*1.1)
     s.CFrame=frame*CFrame.new(0,0,k*r*.38)*CFrame.Angles(a,0,0)*CFrame.new(0,r*.98,0)
     local base=.4+.15*k
     s.Transparency=age<duration and base+(1-base)*fade or 1
    end
   end
   contact.CFrame=CFrame.lookAt(ground+Vector3.yAxis*.1,ground+Vector3.yAxis*.1+direction);sparks.Enabled=age<duration
   -- The slice line runs from the start to under the wheel, following a slope between the two ends.
   local a,b=from+Vector3.yAxis*.06,ground+Vector3.yAxis*.06
   local length=math.max(.1,(b-a).Magnitude)
   core.Size=Vector3.new(.12,.04,length);glow.Size=Vector3.new(.34,.03,length)
   core.CFrame=(b-a).Magnitude>.05 and CFrame.lookAt((a+b)/2,b) or CFrame.lookAt(a,a+direction);glow.CFrame=core.CFrame-Vector3.yAxis*.01
   local line=age<duration and 0 or smooth((age-duration)/hold)
   core.Transparency=.15+.85*line;glow.Transparency=.55+.45*line
   if age<duration then
    passing(last,ground,r,seen,limit,function(p) cutFlash(p,direction,TOMATO) end)
    last=ground
   end
  end,function()
   local endAt=Vector3.new(start.X,floor1,start.Z)+direction*reach
   if K.near(endAt,150) then
    K.shards(folder,endAt+Vector3.yAxis*.4,STEEL,5,9,.32,.13)
    burst(folder,endAt+Vector3.yAxis*radius,{texture=TEX.Star,color=K.White,color2=TOMATO,size=seq(0,.6,1,0),alpha=seq(0,0,1,1),life=.28,speed=4,speed1=8,spread=180,light=1},7)
    dust(endAt+Vector3.yAxis*.3,1,2)
   end
   disc:Destroy();hub:Destroy();contact:Destroy();core:Destroy();glow:Destroy()
   for _,s in spokes do s:Destroy() end
   for _,s in dashes do s:Destroy() end
   for _,arc in arcs do for _,s in arc do s:Destroy() end end
  end,'legendRoll',8)
 end

 -- Royal Flush (Deck of Cards) --------------------------------------------------------------------
 local RANKS={'10','J','Q','K','A'}
 local function goldCard(rank)
  local card=K.part(folder,'RoyalCard',Vector3.new(.86,.05,1.2),rgb(255,206,84),0,Enum.Material.SmoothPlastic)
  local edge=K.part(folder,'RoyalCardGlow',Vector3.new(.98,.03,1.32),GOLD,.25,Enum.Material.Neon)
  local gui=Instance.new('SurfaceGui');gui.Face=Enum.NormalId.Top;gui.CanvasSize=Vector2.new(172,240);gui.LightInfluence=0;gui.Brightness=1.4;gui.Parent=card
  local face=Instance.new('Frame');face.Size=UDim2.new(1,-18,1,-18);face.Position=UDim2.fromOffset(9,9);face.BackgroundColor3=rgb(253,244,220);face.BorderSizePixel=0;face.Parent=gui
  local corner=Instance.new('UICorner');corner.CornerRadius=UDim.new(0,14);corner.Parent=face
  local inner=Instance.new('UIStroke');inner.Color=rgb(214,150,30);inner.Thickness=4;inner.Parent=face
  local big=Instance.new('TextLabel');big.BackgroundTransparency=1;big.Size=UDim2.fromScale(1,.62);big.Position=UDim2.fromScale(0,.12)
  big.Font=Enum.Font.FredokaOne;big.Text=rank;big.TextScaled=true;big.TextColor3=rgb(32,24,30);big.Parent=face
  local suit=Instance.new('TextLabel');suit.BackgroundTransparency=1;suit.Size=UDim2.fromScale(1,.3);suit.Position=UDim2.fromScale(0,.66)
  suit.Font=Enum.Font.GothamBold;suit.Text='♠';suit.TextScaled=true;suit.TextColor3=rgb(32,24,30);suit.Parent=face
  local a0=Instance.new('Attachment');a0.Position=Vector3.new(-.4,0,0);a0.Parent=card
  local a1=Instance.new('Attachment');a1.Position=Vector3.new(.4,0,0);a1.Parent=card
  local t=Instance.new('Trail');t.Attachment0=a0;t.Attachment1=a1;t.Lifetime=.22;t.MinLength=.05;t.LightEmission=1;t.LightInfluence=0
  t.Color=ColorSequence.new(HOT,GOLD);t.Transparency=seq(0,.2,.6,.65,1,1);t.WidthScale=seq(0,1,1,.2);t.Parent=card
  local glint=emitter(card,{name='CardGlint',texture=TEX.Star,color=K.White,color2=GOLD,size=seq(0,.35,1,0),alpha=seq(0,0,1,1),life=.3,life1=.5,speed=.5,speed1=2,
   spread=180,rate=18,light=1,enabled=true})
  return {card=card,edge=edge,glint=glint}
 end
 local function flush(ownerId,origin,list,speed,t0)
  if not K.near(origin,170) then return end
  local owner=Players:GetPlayerByUserId(ownerId)
  local function over()
   if options.preview and options.ownerRoot and options.ownerRoot.Parent then return options.ownerRoot.Position+Vector3.yAxis*4.5 end
   local head=owner and owner.Character and owner.Character:FindFirstChild('Head');return head and head.Position+Vector3.yAxis*3.2 or origin+Vector3.yAxis*4
  end
  headline(folder,over(),'ROYAL FLUSH!',{rgb(255,248,200),rgb(255,170,30)},rgb(74,34,6),44,over)
  K.flash(folder,origin,GOLD,14,4,.35)
  burst(folder,origin,{texture=TEX.Star,color=K.White,color2=GOLD,size=seq(0,1.1,1,0),alpha=seq(0,0,1,1),life=.4,speed=6,speed1=12,spread=180,light=1},14)
  local fanTime=.14
  for i,entry in list do
   local direction,reach=entry[2],entry[3]
   local c=goldCard(RANKS[i] or 'A')
   local seen,limit={},{n=8}
   local duration=reach/math.max(speed,1)
   local last=origin
   local fanAngle=math.rad(-24+48*(i-1)/math.max(1,#list-1))
   K.animate(fanTime+duration+.05,function(_,age)
    local cf
    if age<fanTime then
     -- The hand fans open in front of the deck, faces up, before the cards fly.
     local f=smooth(age/fanTime)
     cf=CFrame.new(origin+Vector3.yAxis*(.3+.05*i))*CFrame.Angles(0,math.atan2(-direction.X,-direction.Z)+fanAngle*f*.6,0)*CFrame.new(0,0,-.5*f)
     c.card.Size=Vector3.new(.86,.05,1.2)*(.5+.5*f)
    else
     local f=math.min(1,(age-fanTime)/duration)
     local position=origin+direction*(reach*f)+Vector3.yAxis*(.35+.05*i)
     cf=CFrame.new(position)*CFrame.Angles(0,(age-fanTime)*26,0)
     if age-fanTime<duration then passing(last,position,.8,seen,limit,function(p)
      burst(folder,p,{texture=TEX.Star,color=K.White,color2=GOLD,size=seq(0,1,1,0),alpha=seq(0,0,1,1),life=.22,speed=4,speed1=8,spread=180,light=1},6)
     end) end
     last=position
     local fade=smooth((f-.85)/.15)
     c.card.Transparency=fade;c.edge.Transparency=.25+.75*fade
    end
    c.card.CFrame=cf;c.edge.CFrame=cf*CFrame.new(0,-.03,0)
   end,function()
    local endAt=c.card.Position
    if K.near(endAt,150) then
     burst(folder,endAt,{texture=TEX.Star,color=HOT,color2=GOLD,size=seq(0,.6,1,0),alpha=seq(0,0,1,1),life=.35,speed=3,speed1=7,spread=180,light=1},9)
    end
    c.card:Destroy();c.edge:Destroy()
   end,'legendCard',12)
  end
 end

 -- Split rocket -----------------------------------------------------------------------------------
 local function rocketBody(scale)
  local template=combat:FindFirstChild('RocketTemplate')
  local model
  if template then
   model=template:Clone();model.Name='LegendaryRocket'
   pcall(function() model:ScaleTo(template:GetScale()*scale) end)
   for _,p in model:GetDescendants() do if p:IsA('BasePart') then p.Anchored=true;p.CanCollide=false;p.CanTouch=false;p.CanQuery=false end end
   model.Parent=folder
  end
  local core=K.part(folder,'RocketCore',Vector3.new(.35,.35,1.3)*scale,rgb(98,108,58),model and 1 or 0)
  local flame=K.ball(folder,'RocketFlame',.45*scale,rgb(255,150,40),.1,Enum.Material.Neon)
  local band=K.part(folder,'RocketBand',Vector3.new(.42,.42,.18)*scale,GOLD,model and 1 or 0,Enum.Material.Neon)
  local a0=Instance.new('Attachment');a0.Position=Vector3.new(0,.12,.6*scale);a0.Parent=core
  local a1=Instance.new('Attachment');a1.Position=Vector3.new(0,-.12,.6*scale);a1.Parent=core
  local t=Instance.new('Trail');t.Attachment0=a0;t.Attachment1=a1;t.Lifetime=.35;t.MinLength=.05;t.FaceCamera=true;t.LightEmission=.4;t.LightInfluence=.4
  t.Color=ColorSequence.new(rgb(255,206,120),rgb(220,214,206));t.Transparency=seq(0,.2,.5,.65,1,1);t.WidthScale=seq(0,.6,1,2.2);t.Parent=core
  return {model=model,core=core,flame=flame,band=band,scale=scale}
 end
 local function placeRocket(r,position,look)
  local cf=CFrame.lookAt(position,position+look)
  r.core.CFrame=cf;r.band.CFrame=cf*CFrame.new(0,0,.1*r.scale)
  r.flame.CFrame=cf*CFrame.new(0,0,.8*r.scale);r.flame.Size=Vector3.one*(.45+.15*math.random())*r.scale
  if r.model then pcall(function() r.model:PivotTo(cf) end) end
 end
 local function dropRocket(r) if r.model then r.model:Destroy() end;r.core:Destroy();r.flame:Destroy();r.band:Destroy() end
 local function miniBlast(ownerId,position,radius)
  if not K.near(position,170) then return end
  K.pop(folder,position,rgb(255,186,64),radius*.35,radius*1.15,.32,.25)
  K.pop(folder,position,rgb(255,246,214),radius*.2,radius*.6,.18,.1)
  K.flash(folder,position,rgb(255,170,60),radius*2.4,4,.3)
  K.cloud(folder,position+Vector3.yAxis*.6,rgb(120,112,106),radius*.75,.9,Vector3.yAxis*2.2,.3)
  K.shards(folder,position,GOLD,6,12,.4,.14)
  burst(folder,position,{texture=TEX.Star,color=K.White,color2=GOLD,size=seq(0,radius*.5,1,0),alpha=seq(0,0,1,1),life=.25,speed=0,spread=0,light=1},1)
  local y=groundY(position)
  decal(folder,Vector3.new(position.X,y+.04,position.Z),TEX.Scorch,rgb(40,30,24),radius*1.5,.05,.8,.9)
  K.ring(folder,CFrame.new(Vector3.new(position.X,y+.15,position.Z)),{segments=16,radius0=radius*.3,radius1=radius*1.05,width=.45,rim=AMBER,color=rgb(255,214,140),duration=.32,bodyAlpha=.5})
 end
 local function split(ownerId,start,splitAt,t0,splitTime,minis,radius,spread)
  if not K.near(splitAt,180) then return end
  local carrier=rocketBody(1)
  local look=(splitAt-start).Magnitude>.01 and (splitAt-start).Unit or -Vector3.zAxis
  local side=Vector3.yAxis:Cross(look);side=side.Magnitude>.01 and side.Unit or Vector3.xAxis
  local carryTime=math.max(.05,splitTime-t0)
  local lastPuff=0
  -- The carrier flies to the split point, wobbling as it charges up.
  local now0=workspace:GetServerTimeNow()
  K.animate(math.max(.05,splitTime-now0),function(_,age)
   local f=math.clamp((workspace:GetServerTimeNow()-t0)/carryTime,0,1)
   local position=start:Lerp(splitAt,f)+side*math.sin(age*40)*.06*f
   placeRocket(carrier,position,look)
   carrier.band.Transparency=carrier.model and 1 or .1*(1-math.sin(age*30))
   if age-lastPuff>.035 then lastPuff=age;K.cloud(folder,position-look*.6,rgb(226,220,212),.45,.45,Vector3.yAxis*.6,.4) end
  end,function()
   dropRocket(carrier)
   -- The split: a gold crack of light, a puff, three rockets fan out.
   K.flash(folder,splitAt,GOLD,12,5,.3)
   K.pop(folder,splitAt,HOT,.3,2.2,.22,.15)
   burst(folder,splitAt,{texture=TEX.Star,color=K.White,color2=GOLD,size=seq(0,2.4,1,0),alpha=seq(0,0,1,1),life=.2,speed=0,spread=0,light=1},1)
   K.shards(folder,splitAt,rgb(120,128,80),5,10,.4,.16,Enum.Material.SmoothPlastic)
   for i=1,3 do K.cloud(folder,splitAt+side*(i-2)*.6,rgb(230,224,216),.8,.6,Vector3.yAxis*.8,.35) end
   for i,m in minis do
    local arrive,at,npc=m[1],m[2],m[3] -- the enemy last: it may not exist on this client
    local r=rocketBody(.55)
    local offset=side*spread*.18*(i-(#minis+1)/2)+Vector3.yAxis*(2.2+math.random())
    local control=splitAt+look*3+offset
    local lastP=splitAt;local lastSmoke=0
    local flight=math.max(.05,arrive-splitTime)
    K.animate(math.max(.05,arrive-workspace:GetServerTimeNow()),function(_,age)
     local f=math.clamp((workspace:GetServerTimeNow()-splitTime)/flight,0,1)
     local root=npcRoot(npc);local goal=root and root.Position or at
     local p=(1-f)^2*splitAt+2*(1-f)*f*control+f*f*goal
     local d=p-lastP;placeRocket(r,p,d.Magnitude>.01 and d.Unit or look);lastP=p
     if age-lastSmoke>.045 then lastSmoke=age;K.cloud(folder,p,rgb(232,228,220),.3,.35,Vector3.yAxis*.4,.45) end
    end,function()
     local root=npcRoot(npc);local goal=root and root.Position or at
     dropRocket(r);miniBlast(ownerId,goal,radius)
    end,'legendMini',12)
   end
   kick(ownerId,.35,.2)
  end,'legendCarrier',4)
 end

 -- STRIKE! (Bowling Ball) --------------------------------------------------------------------------
 local function pinModel()
  local template=combat:FindFirstChild('WeaponTemplates') and combat.WeaponTemplates:FindFirstChild('23')
  if template then
   local m=template:Clone()
   for _,p in m:GetDescendants() do if p:IsA('BasePart') then p.Anchored=true;p.CanCollide=false;p.CanTouch=false;p.CanQuery=false;p.CastShadow=false end end
   m.Parent=folder;return m
  end
  local m=Instance.new('Model');m.Name='Pin';m.Parent=folder
  local body=K.part(m,'PinBody',Vector3.new(.5,1.3,.5),rgb(250,248,242),0,Enum.Material.SmoothPlastic,Enum.PartType.Cylinder)
  body.CFrame=CFrame.Angles(0,0,math.pi/2)
  local stripe=K.part(m,'PinStripe',Vector3.new(.16,.54,.54),rgb(214,58,52),0,Enum.Material.SmoothPlastic,Enum.PartType.Cylinder)
  stripe.CFrame=CFrame.new(0,.35,0)*CFrame.Angles(0,0,math.pi/2)
  m.PrimaryPart=body
  return m
 end
 local function strike(ownerId,ground,radius,hits)
  if not K.near(ground,170) then return end
  headline(folder,ground+Vector3.yAxis*5,'STRIKE!',{K.White,rgb(255,214,120)},rgb(196,30,36),58)
  K.flash(folder,ground+Vector3.yAxis*2,HOT,radius*2.4,5,.4)
  burst(folder,ground+Vector3.yAxis*1.5,{texture=TEX.Star,color=K.White,color2=GOLD,size=seq(0,radius*.7,1,0),alpha=seq(0,0,1,1),life=.28,speed=0,spread=0,light=1},1)
  -- Ten pins stand in their triangle for a blink, then blow outward, spinning.
  local pins={}
  local row,col=1,0
  for i=1,10 do
   col+=1;if col>row then row+=1;col=1 end
   local offset=Vector3.new((col-(row+1)/2)*1.1,0,(row-2.5)*1.0)
   local away=Vector3.new(offset.X,0,offset.Z);away=away.Magnitude>.05 and away.Unit or Vector3.new(math.random()-.5,0,math.random()-.5).Unit
   pins[i]={model=pinModel(),offset=offset,velocity=away*(9+math.random()*7)+Vector3.yAxis*(12+math.random()*6),
    spin=Vector3.new(math.random()-.5,math.random()-.5,math.random()-.5)*16}
  end
  local y=ground.Y
  K.animate(1.3,function(t,age)
   for _,p in pins do
    local a=math.max(0,age-.08)
    local pos=ground+p.offset+p.velocity*a+Vector3.yAxis*(.65-22*a*a)
    if pos.Y<y+.4 then pos=Vector3.new(pos.X,y+.4,pos.Z) end
    local cf=CFrame.new(pos)*CFrame.Angles(p.spin.X*a,p.spin.Y*a,p.spin.Z*a)
    pcall(function() p.model:PivotTo(cf) end)
    if t>.7 then for _,part in p.model:GetDescendants() do if part:IsA('BasePart') then part.LocalTransparencyModifier=smooth((t-.7)/.3) end end end
   end
  end,function() for _,p in pins do p.model:Destroy() end end,'legendPins',3)
  -- The painted shockwave on the ground, the amber dashed rim and a ring of dust.
  groundRing(Vector3.new(ground.X,y+.08,ground.Z),rgb(255,240,214),.5,radius*1.05,.5,.1)
  K.ring(folder,CFrame.new(Vector3.new(ground.X,y+.15,ground.Z)),{segments=24,radius0=.6,radius1=radius,width=.8,rim=AMBER,color=rgb(255,226,170),duration=.45,bodyAlpha=.5})
  for i=1,8 do
   local a=i/8*math.pi*2
   task.delay(.04*i/2,function() if folder.Parent then K.cloud(folder,ground+Vector3.new(math.cos(a),0,math.sin(a))*radius*.55+Vector3.yAxis*.5,DUST,1.6,.8,Vector3.yAxis*1.2,.35) end end)
  end
  dust(ground+Vector3.yAxis*.4,1.8,5)
  K.shards(folder,ground+Vector3.yAxis,rgb(250,248,242),10,14,.6,.18,Enum.Material.SmoothPlastic,.8)
  kick(ownerId,.8,.28)
 end

 -- Shockwave (Wrecking Ball) -----------------------------------------------------------------------
 local function shock(ownerId,ground,radius,duration)
  if not K.near(ground,170) then return end
  local y=ground.Y
  groundRing(Vector3.new(ground.X,y+.08,ground.Z),rgb(236,222,198),.5,radius*1.05,duration+.25,.05)
  dust(ground+Vector3.yAxis*.4,1.6,4)
  K.ring(folder,CFrame.new(Vector3.new(ground.X,y+.12,ground.Z)),{segments=28,radius0=.5,radius1=radius,width=.9,rim=AMBER,color=rgb(255,220,160),duration=duration+.12,bodyAlpha=.55})
  decal(folder,Vector3.new(ground.X,y+.04,ground.Z),TEX.Cracks,CRACK,radius*.95,.04,.8,.9)
  K.flash(folder,ground+Vector3.yAxis*1.5,AMBER,radius*1.6,2.6,.3)
  K.shards(folder,ground+Vector3.yAxis*.4,rgb(150,140,128),9,13,.5,.22,Enum.Material.SmoothPlastic,.9)
  for i=1,10 do
   local a=i/10*math.pi*2+math.random()*.3
   task.delay(duration*.75*(i%2==0 and .55 or 1),function()
    if folder.Parent then K.cloud(folder,ground+Vector3.new(math.cos(a),0,math.sin(a))*radius*(.7+.2*math.random())+Vector3.yAxis*.4,DUST,1.3,.7,Vector3.yAxis*1,.35) end
   end)
  end
  kick(ownerId,.55,.22)
 end

 -- Thunder (Mjolnir) -------------------------------------------------------------------------------
 local function thunder(ownerId,ground,radius,strikeAt)
  if not K.near(ground,180) then return end
  local y=ground.Y
  local wait=math.max(0,strikeAt-workspace:GetServerTimeNow())
  -- A crackling target ring closes in where the bolt will fall.
  if Presentation.ownsCue(ownerId,Players.LocalPlayer and Players.LocalPlayer.UserId,options.preview) then
  decal(folder,Vector3.new(ground.X,y+.05,ground.Z),TEX.Ring,SKY,radius*2.1,math.max(.05,wait*.6),wait*.4+.05,.25,3)
  end
  burst(folder,ground+Vector3.yAxis*.5,{texture=TEX.Lightning,color=BOLT,color2=SKY,size=seq(0,.8,1,0),alpha=seq(0,0,1,1),life=.2,life1=.3,speed=4,speed1=8,spread=180,light=1},6)
  task.delay(wait,function()
   if not folder.Parent then return end
   local top=ground+Vector3.new((math.random()-.5)*6,46,(math.random()-.5)*6)
   local rng=Random.new()
   local main=K.newBolt(folder,{BOLT,SKY},.42,true)
   local forks={K.newBolt(folder,{BOLT,SKY},.16,true),K.newBolt(folder,{BOLT,SKY},.16,true),K.newBolt(folder,{BOLT,GOLD},.12,true)}
   local function draw()
    main:draw(top,ground,1.6,rng)
    for i,f in forks do
     local from=top:Lerp(ground,.3+.18*i)+Vector3.new(rng:NextNumber()-.5,0,rng:NextNumber()-.5)*2
     f:draw(from,ground+Vector3.new(rng:NextNumber()-.5,0,rng:NextNumber()-.5)*radius*1.4,.9,rng)
    end
   end
   draw()
   local redraws=0
   K.animate(.42,function(t)
    if t>.18*(redraws+1) and redraws<2 then redraws+=1;draw() end
    local a=smooth((t-.35)/.65)
    main:fade(a);for _,f in forks do f:fade(math.min(1,a+.2)) end
   end,function() main:destroy();for _,f in forks do f:destroy() end end,'legendBolt',6)
   K.flash(folder,ground+Vector3.yAxis*6,BOLT,radius*3.5,9,.45)
   K.pop(folder,ground+Vector3.yAxis*.4,rgb(196,230,255),.6,radius*.9,.25,.2)
   groundRing(Vector3.new(ground.X,y+.08,ground.Z),SKY,.6,radius*1.1,.4,.05)
   K.ring(folder,CFrame.new(Vector3.new(ground.X,y+.14,ground.Z)),{segments=20,radius0=.6,radius1=radius,width=.5,rim=BOLT,color=SKY,duration=.38,bodyAlpha=.55})
   decal(folder,Vector3.new(ground.X,y+.04,ground.Z),TEX.Scorch,rgb(28,30,40),radius*1.4,.03,1,1)
   K.shards(folder,ground+Vector3.yAxis*.5,SKY,12,15,.45,.13,nil,.7)
   burst(folder,ground+Vector3.yAxis,{texture=TEX.Lightning,color=BOLT,color2=SKY,size=seq(0,1.4,1,0),alpha=seq(0,0,1,1),life=.25,life1=.4,speed=8,speed1=16,spread=180,light=1},10)
   -- Small arcs jump to the enemies caught in it.
   local n=0
   for _,e in enemyRoots() do
    if n>=4 then break end
    if (e.root.Position-ground).Magnitude<=radius then n+=1;K.strike(folder,ground+Vector3.yAxis*.5,e.root.Position,{BOLT,SKY},.07,.22) end
   end
   kick(ownerId,.9,.3)
  end)
 end

 local function onFx(kind,...)
  local a={...}
  if kind=='Slash' or kind=='Beam' then slash(kind,a[2],a[4],a[5],a[6],a[7],a[8],a[9])
  elseif kind=='Roll' then roll(a[2],a[4],a[5],a[6],a[7],a[8],a[9]) -- the slash's layout (LegendaryMoves api:swing)
  elseif kind=='Flush' then flush(a[1],a[3],a[4],a[5],a[6])
  elseif kind=='Split' then split(a[1],a[3],a[4],a[5],a[6],a[7],a[8],a[9])
  elseif kind=='Strike' then strike(a[1],a[2],a[3],a[4])
  elseif kind=='Shock' then shock(a[1],a[2],a[3],a[4])
  elseif kind=='Thunder' then thunder(a[1],a[2],a[3],a[4]) end
 end
 -- Spawned: mount() must return at once, or the combat client's render loop would wait on it.
 if options.preview then
  local closed=false
  function api.handle(...) if not closed and folder.Parent then onFx(...) end end
  function api.destroy() closed=true;stopPreview() end
 else
  task.spawn(function()
   local fx=combat:WaitForChild('LegendaryFX',60)
   if fx then fx.OnClientEvent:Connect(onFx) end
  end)
 end
 return api
end
return V
