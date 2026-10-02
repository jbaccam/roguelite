-- Godly weapon presentation (plans/2026-10-01-G-godly-weapons.md). Client only; never affects hits.
--  * every Godly: idle aura haze + motes from its own mesh, a light, breathing Neon, and a
--    two-layer swing trail (hot core + wide glow)
--  * 36 Reaper's Scythe: the Reap disc; wraiths that rise from corpses, hunt, claw and fade
--  * 37 Poseidon's Trident: spray trail on the throw; tidal wave ring, water column and splash
--  * 38 Storm Bow: crackling limbs; the arrow climbs, splits, and lightning arrows strike down
--  * 39 Shadow Daggers: the pair leaves its slot and zips the chain with afterimages and slashes
--  * 40 Vampire Blade: blood drips and crescents; wisps that curve into the wielder and pulse
--  * 41 Ray Gun: green bolts with a muzzle ring; kills dissolve into green pixels and a burst
-- Server events arrive on GodlyFX (GodlyWeapons). Effects far from the camera are skipped.
-- Sandboxed like the combat client that requires it: no sounds here (RogueliteSounds plays them).
local RunService=game:GetService('RunService')
local Players=game:GetService('Players')
local Motion=require(script.Parent:WaitForChild('WeaponMotion'))
local K=require(script.Parent:WaitForChild('VfxKit'))
local V={}
-- Painted for Godlies (weapon-models/godly/vfx) and reused from BossVfxAssets (boss-vfx-kit).
local TEX={
 Glow='rbxassetid://119796255132573',Slash='rbxassetid://105397482701607',Lightning='rbxassetid://100197465776159',
 Wisp='rbxassetid://96655998397870',Skull='rbxassetid://119217505644088',Pixel='rbxassetid://133657841459974',
 Ring='rbxassetid://73745779894728',Star='rbxassetid://132900122818559',Splash='rbxassetid://99255856772433',
 Smoke='rbxassetid://133683398795549',Bubble='rbxassetid://85054572566506',Ember='rbxassetid://116159534169534',
}
V.Textures=TEX
local function rgb(r,g,b) return Color3.fromRGB(r,g,b) end
local STYLE={
 ['36']={glow=rgb(255,22,52),hot=rgb(255,170,150),dark=rgb(46,4,16),mote=TEX.Skull,motes=2.5,moteSize=.38,blade=true},
 ['37']={glow=rgb(0,190,235),hot=rgb(190,255,245),dark=rgb(0,46,80),mote=TEX.Bubble,motes=5,moteSize=.3,blade=true},
 ['38']={glow=rgb(40,125,255),hot=rgb(220,242,255),dark=rgb(8,22,70),mote=TEX.Glow,motes=6,moteSize=.22,sparks=true},
 ['39']={glow=rgb(255,16,34),hot=rgb(255,96,72),dark=rgb(24,0,8),mote=TEX.Ember,motes=4,moteSize=.2,blade=true},
 ['40']={glow=rgb(255,8,40),hot=rgb(255,110,90),dark=rgb(60,0,10),mote=TEX.Ember,motes=3,moteSize=.2,blade=true,drips=true},
 ['41']={glow=rgb(40,255,70),hot=rgb(190,255,160),dark=rgb(6,60,14),mote=TEX.Pixel,motes=5,moteSize=.16},
}
V.Style=STYLE
local smooth=K.smooth
local function seq(...) local k={};local a={...};for i=1,#a,2 do k[#k+1]=NumberSequenceKeypoint.new(a[i],a[i+1]) end;return NumberSequence.new(k) end
-- ParticleEmitter with this file's defaults; o overrides.
local function emitter(parent,o)
 local e=Instance.new('ParticleEmitter');e.Name=o.name or 'GodlyFx'
 e.Texture=o.texture or TEX.Glow
 e.Color=typeof(o.color)=='ColorSequence' and o.color or ColorSequence.new(o.color or K.White,o.color2 or o.color or K.White)
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
 if o.orientation then e.Orientation=o.orientation end
 e.Enabled=o.enabled==true;e.Parent=parent
 return e
end
-- One-shot burst at a point; the holder cleans itself up.
local function burst(folder,position,o,count)
 local holder=K.part(folder,'GodlyBurst',Vector3.one*.05,K.White,1)
 holder.CFrame=CFrame.lookAt(position,position+(o.facing or Vector3.yAxis))
 local e=emitter(holder,o);e.EmissionDirection=Enum.NormalId.Front
 e:Emit(count or 10)
 K.animate((o.life1 or o.life or .6)+.15,function() end,function() holder:Destroy() end,'godlyBurst',60)
 return e
end
local function ground(position)
 local exclude={}
 for _,p in Players:GetPlayers() do if p.Character then exclude[#exclude+1]=p.Character end end
 local enemies=workspace:FindFirstChild('RogueliteEnemies');if enemies then exclude[#exclude+1]=enemies end
 return K.groundBelow(position,exclude,position.Y-2.5)
end
local function npcRoot(npc) return npc and npc.Parent and npc:FindFirstChild('HumanoidRootPart') end
-- Flat disc lying on the ground with a texture on top (shockwave rings).
local function disc(folder,position,texture,color,alpha)
 local p=K.part(folder,'GodlyDisc',Vector3.new(.06,1,1),color,1,Enum.Material.SmoothPlastic,Enum.PartType.Cylinder)
 p.CFrame=CFrame.new(position)*CFrame.Angles(0,0,math.pi/2)
 local d=Instance.new('Decal');d.Texture=texture;d.Color3=color;d.Transparency=alpha or 0;d.Face=Enum.NormalId.Right;d.Parent=p
 return p,d
end
local function shockwave(folder,position,color,radius0,radius1,duration,alpha)
 local p,d=disc(folder,position,TEX.Ring,color,alpha)
 K.animate(duration,function(t)
  local e=1-(1-t)^3;local r=radius0+(radius1-radius0)*e
  p.Size=Vector3.new(.06,r*2,r*2);d.Transparency=(alpha or 0)+(1-(alpha or 0))*smooth((t-.35)/.65)
 end,function() p:Destroy() end,'godlyRing',24)
end
local function slashFlash(folder,position,color,size,facing)
 burst(folder,position,{texture=TEX.Slash,color=K.White,color2=color,size=seq(0,size*.6,.3,size,1,size*1.15),
  alpha=seq(0,0,.6,.2,1,1),life=.16,speed=0,spread=0,light=1,spin=0,facing=facing},1)
end

-- Trident throw: a water ribbon and spray follow the flying spear (ThrownVisuals.decorate).
function V.decorateThrown(model,id)
 if id~='37' then return end
 local body=model:FindFirstChild('PoseidonsTrident');if not body then return end
 local aqua,foam=STYLE['37'].glow,rgb(225,255,250)
 local t=K.trail(body,1.1,.35,foam,aqua,.1,true);t.LightEmission=.8
 emitter(body,{name='TridentSpray',texture=TEX.Bubble,color=foam,color2=aqua,size=seq(0,.35,1,.05),alpha=seq(0,0,1,1),life=.35,life1=.5,speed=1,speed1=3,rate=40,spread=60,
  accel=Vector3.new(0,-18,0),shape=Enum.ParticleEmitterShape.Box,enabled=true})
 local light=Instance.new('PointLight');light.Color=aqua;light.Range=10;light.Brightness=3;light.Shadows=false;light.Parent=body
end

function V.mount(combat,folder,lookup)
 local api={}
 local wraiths={};local bolts={};local afterimages=0
 -- Per rendered weapon --------------------------------------------------------------------------
 function api.attach(v,id,template)
  local style=STYLE[id];if not style then return end
  local g={style=style,glows={},textured={},trails={},emitters={},phase=math.random()*6}
  for _,p in v.model:GetDescendants() do
   if p:IsA('BasePart') then
    if p.Material==Enum.Material.Neon then g.glows[#g.glows+1]={part=p,base=p.Transparency} else g.textured[#g.textured+1]=p end
   end
  end
  local body=g.textured[1];if not body then return end
  g.body=body
  local light=Instance.new('PointLight');light.Color=style.glow;light.Range=9;light.Brightness=1.4;light.Shadows=false;light.Parent=body;g.light=light
  for _,part in g.textured do
   -- Haze and motes come out of the mesh's own volume.
   g.emitters[#g.emitters+1]=emitter(part,{name='GodlyHaze',texture=TEX.Glow,color=style.glow,color2=style.dark,size=seq(0,.5,.4,1.3,1,1.7),
    alpha=seq(0,1,.25,.72,1,1),life=.7,life1=1.1,speed=.2,speed1=.6,rate=7,shape=Enum.ParticleEmitterShape.Box,light=1})
   g.emitters[#g.emitters+1]=emitter(part,{name='GodlyMotes',texture=style.mote,color=style.hot,color2=style.glow,size=seq(0,style.moteSize,.8,style.moteSize*.8,1,0),
    alpha=seq(0,.1,.75,.3,1,1),life=1,life1=1.6,speed=.4,speed1=1.2,rate=style.motes/#g.textured,accel=Vector3.yAxis*1.4,shape=Enum.ParticleEmitterShape.Box,light=.9})
   if style.drips then
    g.emitters[#g.emitters+1]=emitter(part,{name='BloodDrips',texture=TEX.Glow,color=rgb(150,0,16),size=seq(0,.2,1,.12),alpha=seq(0,0,.8,.1,1,1),
     life=.55,speed=0,rate=2.5,accel=Vector3.new(0,-30,0),shape=Enum.ParticleEmitterShape.Box,light=.25,influence=.6})
   end
  end
  if style.blade then
   -- Two-layer ribbon along each blade's length (+Y): a white-hot core and a wide glow.
   local size=template:GetAttribute('BoundsSize') or Vector3.new(1,4,1)
   for _,part in g.textured do
    local half=part.Size.Y*.5
    local function ribbon(name,from,to,lifetime,color,color2,alpha,light)
     local a0=Instance.new('Attachment');a0.Name=name..'A';a0.Position=Vector3.new(0,from,0);a0.Parent=part
     local a1=Instance.new('Attachment');a1.Name=name..'B';a1.Position=Vector3.new(0,to,0);a1.Parent=part
     local t=Instance.new('Trail');t.Name=name;t.Attachment0=a0;t.Attachment1=a1;t.FaceCamera=false
     t.Lifetime=lifetime;t.MinLength=.03;t.LightEmission=light;t.LightInfluence=0;t.Enabled=false
     t.Color=ColorSequence.new(color,color2);t.Transparency=alpha;t.WidthScale=seq(0,1,1,.35);t.Parent=part
     g.trails[#g.trails+1]=t
    end
    ribbon('GodlyCore',half*.15,half*1.02,.16,style.hot,style.glow,seq(0,.05,.5,.45,1,1),1)
    ribbon('GodlyGlow',-half*.1,half*1.12,.3,style.glow,style.dark,seq(0,.35,.6,.75,1,1),1)
   end
   g.tip=Vector3.new(0,size.Y*.5,0)
  end
  v.godly=g
 end
 function api.hide(v)
  local g=v.godly;if not g then return end
  for _,t in g.trails do t.Enabled=false end
  for _,e in g.emitters do e.Enabled=false end
  g.light.Enabled=false
 end
 local function sparkBow(g,pivot)
  local size=Vector3.new(.6,4.8,1.4)
  local function point() return pivot:PointToWorldSpace(Vector3.new(0,(math.random()-.5)*size.Y,(math.random()-.5)*size.Z)) end
  local a=point();local b=a+Vector3.new(math.random()-.5,math.random()-.5,math.random()-.5)*1.8
  K.strike(folder,a,b,{g.style.hot,g.style.glow},.05,.12)
 end
 -- frame: {visible,active,age,start,kind,style,side,attackRoot,direction,range,rate}
 function api.step(v,pivot,frame)
  local g=v.godly;if not g then return end
  local now=os.clock()
  local near=frame.visible and K.near(pivot.Position,70)
  local hidden=g.hiddenUntil and now<g.hiddenUntil
  for _,e in g.emitters do local on=near and not hidden;if e.Enabled~=on then e.Enabled=on end end
  g.light.Enabled=frame.visible and not hidden
  -- Breathing Neon and light; a flare right after an attack.
  local flare=frame.active and math.clamp(1-(frame.age or 0)/.5,0,1) or 0
  local breath=.5+.5*math.sin(now*3.2+g.phase)
  for _,glow in g.glows do glow.part.Transparency=glow.base+.22*breath*(1-flare) end
  g.light.Brightness=1+.8*breath+2.5*flare;g.light.Range=8+5*flare
  local live=frame.visible and frame.active and frame.kind=='Melee' and frame.style~='Chain' and (frame.age or 0)>=Motion.SwingHitStart-.04 and (frame.age or 0)<=Motion.SwingHitEnd+.06
  if live and g.swing~=frame.start then
   g.swing=frame.start
   for _,t in g.trails do t:Clear() end
   local root=frame.attackRoot
   if root and K.near(root.Position,140) then
    local base=Vector3.new(root.Position.X,ground(root.Position)+.12,root.Position.Z)
    local direction=frame.direction or root.LookVector
    direction=Vector3.new(direction.X,0,direction.Z);if direction.Magnitude<.01 then direction=-Vector3.zAxis end
    local reach=frame.range or 8
    if frame.style=='Reap' then
     -- The Reap: a crimson disc sweeps round the ground, skulls fly off the blade, a red flash.
     local frameCF=CFrame.lookAt(base,base+direction.Unit)
     K.ring(folder,frameCF,{segments=24,from=-math.pi*(frame.side or 1),to=math.pi*(frame.side or 1),radius0=reach*.72,radius1=reach*.95,
      width=2.4,rim=g.style.hot,color=g.style.glow,reveal=(Motion.SwingHitEnd-Motion.SwingHitStart)/(frame.rate or 1.8),hold=.08,duration=.6,bodyAlpha=.35})
     shockwave(folder,base+Vector3.yAxis*.05,g.style.glow,reach*.3,reach*1.05,.55,.15)
     K.flash(folder,root.Position,g.style.glow,reach*1.6,4,.4)
     local tip=pivot:PointToWorldSpace(g.tip or Vector3.zero)
     burst(folder,tip,{texture=TEX.Skull,color=g.style.hot,color2=g.style.glow,size=seq(0,.6,1,.1),alpha=seq(0,0,.7,.3,1,1),life=.5,life1=.8,speed=6,speed1=10,spread=180,accel=Vector3.yAxis*3,light=1},7)
    elseif v.id~='39' then
     -- Heavy crescent for the sweeps (Vampire Blade, Trident); a splash ring for the stab.
     local diagonal=frame.style=='Diagonal';local half=math.rad(Motion.VisualSweepHalfAngle-5)
     if frame.style=='Thrust' then
      local tipAt=base+direction.Unit*math.min(reach,9)
      task.delay(.12/(frame.rate or 1.8),function() if folder.Parent then
       burst(folder,tipAt+Vector3.yAxis*.6,{texture=TEX.Splash,flipbook=true,color=g.style.hot,color2=g.style.glow,size=seq(0,1.4,1,3),alpha=seq(0,.1,1,1),life=.45,speed=2,spread=40,light=.6,influence=.3},3)
       shockwave(folder,tipAt,g.style.glow,.5,3,.35,.2)
      end end)
     else
      K.ring(folder,CFrame.lookAt(base,base+direction.Unit),{segments=14,from=(diagonal and -1 or -half)*(frame.side or 1),to=(diagonal and .7 or half)*(frame.side or 1),
       radius0=reach*.78,radius1=reach*1,width=math.clamp(reach*.26,1.2,2.4),rim=g.style.hot,color=g.style.glow,
       reveal=(Motion.SwingHitEnd-Motion.SwingHitStart)/(frame.rate or 1.8),hold=.05,duration=.5,bodyAlpha=.42})
     end
     K.flash(folder,root.Position,g.style.glow,reach*1.2,2.5,.3)
    end
   end
  end
  for _,t in g.trails do if t.Enabled~=live then t.Enabled=live end end
  -- Storm Bow: little arcs crackle along the limbs.
  if g.style.sparks and near and not hidden and now>=(g.nextSpark or 0) then
   g.nextSpark=now+.25+math.random()*.45;sparkBow(g,pivot)
  end
  -- Recoil kick after a shot (bow and gun): a short push back along the aim.
  if g.kick and now-g.kick<.18 then
   local k=1-(now-g.kick)/.18
   v.model:PivotTo(pivot*CFrame.new(0,0,.45*k*k)*CFrame.Angles(math.rad(10)*k*k,0,0))
  end
 end

 -- Wraiths (36) ---------------------------------------------------------------------------------
 local function wraithTemplate()
  local assets=combat:FindFirstChild('GodlyAssets');return assets and assets:FindFirstChild('Wraith')
 end
 local function buildWraith(big)
  local template=wraithTemplate()
  local model
  if template then
   model=template:Clone()
  else
   -- Until the wraith model is installed: a hooded Neon shade, so the special still reads.
   model=Instance.new('Model')
   local body=K.part(model,'Wraith_Body',Vector3.new(1.6,2.6,1.2),rgb(30,4,12),.15,Enum.Material.SmoothPlastic)
   local eyes=K.part(model,'Wraith_Glow',Vector3.new(.9,.2,.1),rgb(255,22,52),0,Enum.Material.Neon)
   eyes.CFrame=CFrame.new(0,.75,-.62);model.PrimaryPart=body
  end
  for _,p in model:GetDescendants() do if p:IsA('BasePart') then p.Anchored=true;p.CanCollide=false;p.CanTouch=false;p.CanQuery=false;p.CastShadow=false end end
  if big then model:ScaleTo(1.5) end
  local pivot=model:GetPivot()
  local w={model=model,parts={},arms={},glow={}}
  for _,p in model:GetDescendants() do
   if p:IsA('BasePart') then
    local rest=pivot:ToObjectSpace(p.CFrame)
    w.parts[#w.parts+1]={part=p,rest=rest,base=p.Transparency}
    local side=p.Name:match('Arm([LR])$')
    if side then
     local shoulder=p:FindFirstChild('Shoulder')
     w.arms[#w.arms+1]={part=p,rest=rest,side=side=='L' and -1 or 1,shoulder=shoulder and rest*CFrame.new(shoulder.Position) or rest}
    end
    if p.Material==Enum.Material.Neon then w.glow[#w.glow+1]=p end
   end
  end
  local body=model:FindFirstChild('Wraith_Body') or model.PrimaryPart
  if body then
   local light=Instance.new('PointLight');light.Color=rgb(255,22,52);light.Range=big and 11 or 8;light.Brightness=2;light.Shadows=false;light.Parent=body
   -- Soul smoke pours off the tattered tail; a ribbon follows the flight.
   local tail=body:FindFirstChild('Tail')
   local holder=tail or body
   w.smoke=emitter(holder,{name='WraithSmoke',texture=TEX.Smoke,flipbook=true,color=rgb(120,6,28),color2=rgb(16,0,6),size=seq(0,.9,1,2.4),
    alpha=seq(0,.35,.6,.6,1,1),life=.55,life1=.8,speed=.6,speed1=1.4,rate=14,spread=35,light=.35,influence=.5,enabled=true})
   w.embers=emitter(body,{name='WraithEmbers',texture=TEX.Ember,color=rgb(255,120,90),color2=rgb(255,22,52),size=seq(0,.22,1,0),
    alpha=seq(0,0,1,1),life=.5,life1=.9,speed=1,speed1=2.5,rate=10,accel=Vector3.yAxis*2,shape=Enum.ParticleEmitterShape.Box,enabled=true})
   local a0=Instance.new('Attachment');a0.Position=Vector3.new(0,.6,0);a0.Parent=body
   local a1=Instance.new('Attachment');a1.Position=Vector3.new(0,-1.1,0);a1.Parent=body
   local trail=Instance.new('Trail');trail.Attachment0=a0;trail.Attachment1=a1;trail.Lifetime=.35;trail.LightEmission=1;trail.FaceCamera=true
   trail.Color=ColorSequence.new(rgb(255,40,70),rgb(40,0,10));trail.Transparency=seq(0,.35,1,1);trail.WidthScale=seq(0,1,1,.2);trail.Parent=body
  end
  return w
 end
 local function rise(key,position,big,life)
  if not K.near(position,160) then return end
  local w=buildWraith(big)
  w.key=key;w.big=big;w.born=os.clock();w.position=position+Vector3.yAxis*1.5;w.velocity=Vector3.zero;w.yaw=math.random()*6.28
  w.ends=w.born+(life or 6)+.5
  w.model.Parent=folder;wraiths[key]=w
  local floor=Vector3.new(position.X,ground(position)+.1,position.Z)
  -- Erupts from the corpse: soul smoke, a skull spray, a red ring and a flash.
  burst(folder,floor+Vector3.yAxis*.6,{texture=TEX.Smoke,flipbook=true,color=rgb(150,10,36),color2=rgb(20,0,6),size=seq(0,1.5,1,4.5),alpha=seq(0,.2,1,1),life=.7,life1=1,speed=2,speed1=5,spread=60,light=.4,influence=.4},8)
  burst(folder,floor+Vector3.yAxis*1,{texture=TEX.Skull,color=rgb(255,190,170),color2=rgb(255,22,52),size=seq(0,.7,1,.1),alpha=seq(0,0,.7,.2,1,1),life=.6,life1=.9,speed=5,speed1=9,spread=50,accel=Vector3.yAxis*4},5)
  shockwave(folder,floor,rgb(255,22,52),.4,big and 5 or 3.5,.45,.1)
  K.flash(folder,floor+Vector3.yAxis*2,rgb(255,22,52),12,5,.45)
 end
 local function fadeWraith(key)
  local w=wraiths[key];if not w then return end
  wraiths[key]=nil
  if w.smoke then w.smoke.Enabled=false end;if w.embers then w.embers.Enabled=false end
  local start=w.model:GetPivot()
  if K.near(start.Position,160) then
   burst(folder,start.Position,{texture=TEX.Smoke,flipbook=true,color=rgb(110,6,26),color2=rgb(14,0,4),size=seq(0,1.2,1,3.4),alpha=seq(0,.3,1,1),life=.6,speed=1.5,spread=180,light=.3,influence=.5},6)
  end
  K.animate(.35,function(t)
   for _,e in w.parts do e.part.Transparency=e.base+(1-e.base)*t end
   w.model:PivotTo(start*CFrame.new(0,t*1.2,0))
  end,function() w.model:Destroy() end,'wraithFade',24)
 end
 local function claw(key,npc)
  local w=wraiths[key];if not w then return end
  w.clawAt=os.clock();w.clawSide=-(w.clawSide or 1)
  local root=npcRoot(npc)
  if root and K.near(root.Position,140) then
   task.delay(.1,function()
    if not folder.Parent then return end
    local at=root.Parent and root.Position or root.Position
    local facing=(workspace.CurrentCamera.CFrame.Position-at).Unit
    slashFlash(folder,at+Vector3.yAxis*.5,rgb(255,22,52),w.big and 6 or 4.2,facing)
    K.shards(folder,at+Vector3.yAxis*.8,rgb(255,40,70),5,9,.35,.16)
   end)
  end
 end
 local function stepWraiths(dt)
  local now=os.clock()
  for key,w in wraiths do
   if now>w.ends then fadeWraith(key);continue end
   local root=npcRoot(w.target)
   local age=now-w.born
   if root then
    local goal=root.Position+Vector3.yAxis*1.2
    local delta=goal-w.position;local distance=delta.Magnitude
    local reach=w.big and 3.6 or 2.6
    if distance>reach then w.position+=delta.Unit*math.min(distance-reach,28*dt) end
    local flat=Vector3.new(delta.X,0,delta.Z)
    if flat.Magnitude>.05 then
     local yaw=math.atan2(-flat.X,-flat.Z)
     w.yaw+=math.atan2(math.sin(yaw-w.yaw),math.cos(yaw-w.yaw))*math.min(1,dt*10)
    end
   end
   -- Rise out of the ground for the first 0.35 s, then hover with a menacing bob and lean.
   local up=age<.35 and -2.6*(1-smooth(age/.35)) or 0
   local bob=math.sin(now*4.2+(w.key%7))*.28
   local clawT=w.clawAt and (now-w.clawAt)/.32 or 2
   local lunge=clawT<1 and math.sin(clawT*math.pi)*1.1 or 0
   local cf=CFrame.new(w.position+Vector3.yAxis*(up+bob))*CFrame.Angles(0,w.yaw,0)*CFrame.new(0,0,-lunge)*CFrame.Angles(math.rad(-12-18*lunge),0,math.sin(now*2.3)*math.rad(5))
   for _,e in w.parts do e.part.CFrame=cf*e.rest end
   -- Arms: an idle claw-flex; on a claw, the leading arm rakes down hard.
   for _,arm in w.arms do
    local swing=math.sin(now*5+arm.side)*math.rad(9)
    if clawT<1 and arm.side==(w.clawSide or 1) then swing+=math.sin(clawT*math.pi)*math.rad(-75) end
    arm.part.CFrame=cf*arm.shoulder*CFrame.Angles(swing,0,arm.side*math.rad(4))*arm.shoulder:Inverse()*arm.rest
   end
   for _,p in w.glow do p.Transparency=.05+.25*(.5+.5*math.sin(now*9+w.key)) end
  end
 end

 -- Trident tidal wave (37) ------------------------------------------------------------------------
 local function wave(position,radius,duration)
  if not K.near(position,170) then return end
  local base=Vector3.new(position.X,ground(position)+.08,position.Z)
  local aqua,foam=STYLE['37'].glow,rgb(225,255,250)
  K.flash(folder,base+Vector3.yAxis*2,aqua,radius*2,5,.5)
  shockwave(folder,base,foam,.5,radius*1.08,duration+.25,.05)
  shockwave(folder,base+Vector3.yAxis*.04,aqua,.5,radius*.85,duration+.45,.35)
  burst(folder,base+Vector3.yAxis*.5,{texture=TEX.Splash,flipbook=true,color=foam,color2=aqua,size=seq(0,2.5,1,6),alpha=seq(0,0,1,1),life=.55,life1=.75,speed=8,speed1=14,spread=30,accel=Vector3.new(0,-30,0),light=.5,influence=.3},10)
  -- A water column punches up and collapses.
  local column=K.part(folder,'WaveColumn',Vector3.new(1,1,1),aqua,.25,Enum.Material.Glass,Enum.PartType.Cylinder)
  local core=K.part(folder,'WaveCore',Vector3.new(1,1,1),foam,.4,Enum.Material.Neon,Enum.PartType.Cylinder)
  K.animate(.6,function(t)
   local h=7*math.sin(math.min(1,t*1.4)*math.pi);local w=2.4*(1-t*.5)
   column.Size=Vector3.new(math.max(.1,h),w,w);column.CFrame=CFrame.new(base+Vector3.yAxis*h/2)*CFrame.Angles(0,0,math.pi/2);column.Transparency=.25+.75*smooth((t-.5)/.5)
   core.Size=Vector3.new(math.max(.1,h*.9),w*.45,w*.45);core.CFrame=column.CFrame;core.Transparency=.35+.65*smooth((t-.4)/.6)
  end,function() column:Destroy();core:Destroy() end,'wave',8)
  -- The wave wall: crests ride outward on the ring, cresting and curling as they go.
  local crests={};local count=math.clamp(math.floor(radius*2.4),14,34)
  for i=1,count do
   crests[i]={body=K.part(folder,'WaveCrest',Vector3.one,aqua,.2,Enum.Material.Glass),lip=K.part(folder,'WaveLip',Vector3.one,foam,.1,Enum.Material.Neon),angle=i/count*math.pi*2}
  end
  K.animate(duration+.3,function(t,age)
   local grow=1-(1-math.min(1,age/duration))^2;local r=.8+(radius-.8)*grow
   local fade=smooth((age-duration*.8)/.4)
   local height=(2.6-1.2*grow)*(1-fade)
   local chord=2*r*math.sin(math.pi/count)*1.15
   for _,c in crests do
    local out=Vector3.new(math.cos(c.angle),0,math.sin(c.angle))
    local at=base+out*r
    local frame=CFrame.lookAt(at,at+out)
    c.body.Size=Vector3.new(chord,math.max(.05,height),.9);c.body.CFrame=frame*CFrame.new(0,height/2,0)*CFrame.Angles(math.rad(-18),0,0)
    c.lip.Size=Vector3.new(chord,.28,.55);c.lip.CFrame=frame*CFrame.new(0,height,-.25)*CFrame.Angles(math.rad(-35),0,0)
    c.body.Transparency=.2+.8*fade;c.lip.Transparency=.1+.9*fade
   end
   if age<duration and math.random()<.5 then
    local c=crests[math.random(1,count)]
    burst(folder,c.lip.Position,{texture=TEX.Bubble,color=foam,color2=aqua,size=seq(0,.35,1,.1),alpha=seq(0,0,1,1),life=.4,speed=3,speed1=6,spread=60,accel=Vector3.new(0,-20,0)},3)
   end
  end,function() for _,c in crests do c.body:Destroy();c.lip:Destroy() end end,'wave',8)
 end

 -- Storm Bow arrow rain (38) ------------------------------------------------------------------------
 local function arrowPart(color,core)
  local p=K.part(folder,'StormArrow',Vector3.new(.16,.16,1.9),core,0,Enum.Material.Neon)
  K.trail(p,.5,.22,core,color,.05,true)
  local light=Instance.new('PointLight');light.Color=color;light.Range=7;light.Brightness=3;light.Shadows=false;light.Parent=p
  return p
 end
 local function rain(ownerId,slot,origin,split,roots,npcs,start,rise)
  local blue,hot=STYLE['38'].glow,STYLE['38'].hot
  local v=lookup(ownerId,slot)
  if v and v.godly then
   v.godly.kick=os.clock()
   local rest=v.model:FindFirstChild('ArrowRest',true);if rest then origin=rest.WorldPosition end
  end
  if not K.near(origin,170) and not K.near(split,170) then return end
  local delay=math.max(0,start-workspace:GetServerTimeNow())
  local arrow=arrowPart(blue,hot)
  K.animate(rise+delay,function(t,age)
   local a=math.clamp((age-delay)/rise,0,1)
   local pos=origin:Lerp(split,a)+Vector3.yAxis*math.sin(a*math.pi)*1.5
   arrow.CFrame=CFrame.lookAt(pos,split+Vector3.yAxis*.01)
  end,function()
   arrow:Destroy()
   if not folder.Parent then return end
   -- The split: a thunderclap star, a flash and a ring of sparks.
   burst(folder,split,{texture=TEX.Star,color=K.White,color2=blue,size=seq(0,2,1,6),alpha=seq(0,0,1,1),life=.25,speed=0,spread=0},2)
   K.flash(folder,split,blue,26,6,.4);K.pop(folder,split,hot,.5,4,.25,.3)
   K.shards(folder,split,hot,8,14,.35,.14)
   for i,at in roots do
    local npc=npcs[i]
    task.delay(.035*(i-1),function()
     if not folder.Parent then return end
     local root=npcRoot(npc);local target=root and root.Position or at
     K.strike(folder,split,target,{hot,blue},.12,.28)
     local bolt=arrowPart(blue,hot)
     K.animate(.16,function(t) local p=split:Lerp(target,t);bolt.CFrame=CFrame.lookAt(p,target+Vector3.yAxis*.01) end,function()
      bolt:Destroy()
      if not folder.Parent then return end
      local floor=Vector3.new(target.X,ground(target)+.1,target.Z)
      burst(folder,target,{texture=TEX.Star,color=K.White,color2=blue,size=seq(0,1.2,1,3.6),alpha=seq(0,0,1,1),life=.2,speed=0,spread=0},1)
      burst(folder,target,{texture=TEX.Lightning,color=hot,color2=blue,size=seq(0,1.5,1,.2),alpha=seq(0,0,1,1),life=.25,speed=6,speed1=12,spread=180,light=1},5)
      shockwave(folder,floor,blue,.3,3.2,.3,.1)
     end,'stormArrow',40)
    end)
   end
  end,'stormArrow',40)
 end

 -- Shadow Daggers chain (39) --------------------------------------------------------------------------
 local function daggerChain(ownerId,slot,origin,points,npcs,start,step)
  local v=lookup(ownerId,slot)
  local crimson,hot=STYLE['39'].glow,STYLE['39'].hot
  local home=v and v.model.Parent and v.model:GetPivot() or CFrame.new(origin)
  if not K.near(home.Position,170) then return end
  -- Fly copies of the two blades; the resting pair hides until they're back.
  local copies={}
  local source=v and v.model or nil
  if source then
   for _,side in {'L','R'} do
    local model=Instance.new('Model');model.Name='FlyingDagger'..side
    for _,p in source:GetChildren() do
     if p:IsA('BasePart') and p.Name:match('^ShadowDaggers_'..side) then local c=p:Clone();c:ClearAllChildren();c.LocalTransparencyModifier=0;c.Parent=model end
    end
    local first=model:FindFirstChildWhichIsA('BasePart')
    if first then
     model.PrimaryPart=first;model.WorldPivot=source:GetPivot();model.Parent=folder
     local t=K.trail(first,.9,.18,hot,crimson,.05,true);t.LightEmission=1
     copies[#copies+1]={model=model,offset=side=='L' and -.7 or .7,lag=side=='L' and .035 or 0}
    else model:Destroy() end
   end
   v.godly=v.godly or {};
   local total=.08+(#points-1)*step+.3
   v.godly.hiddenUntil=os.clock()+total
   v.hide=v.hide or {};for _,p in v.parts do v.hide[p]=(v.hide[p] or 0)+1 end
   task.delay(total,function() if v.hide then for _,p in v.parts do v.hide[p]=math.max(0,(v.hide[p] or 1)-1) end end end)
  end
  local delay=math.max(0,start-workspace:GetServerTimeNow())
  -- Waypoints in time: home -> each hit (at its server time) -> home.
  local times,spots={0},{home.Position}
  for i,p in points do times[#times+1]=delay+.08+(i-1)*step;spots[#spots+1]=p+Vector3.yAxis*1 end
  times[#times+1]=times[#times]+.3;spots[#spots+1]=home.Position
  local lastImage=0;local struck={}
  K.animate(times[#times],function(t,age)
   for _,c in copies do
    local a=math.max(0,age-c.lag)
    local i=1;while i<#times-1 and a>times[i+1] do i+=1 end
    local f=math.clamp((a-times[i])/math.max(.01,times[i+1]-times[i]),0,1)
    local p0,p1=spots[i],spots[i+1];local pos=p0:Lerp(p1,1-(1-f)^2)
    if i>1 and i<#times then local sideways=(p1-p0):Cross(Vector3.yAxis);if sideways.Magnitude>.01 then pos+=sideways.Unit*c.offset*math.sin(f*math.pi) end end
    local look=(p1-p0).Magnitude>.05 and (p1-p0).Unit or -Vector3.zAxis
    -- Blades fly point-first (+Y forward) with a spin around the flight line.
    c.model:PivotTo(CFrame.lookAt(pos,pos+look)*CFrame.Angles(-math.pi/2,age*22,0))
   end
   -- Afterimages: crimson ghosts of the lead blade, fading fast.
   if copies[1] and age-lastImage>.03 and afterimages<40 then
    lastImage=age;afterimages+=1
    local ghost=copies[1].model:Clone();ghost.Name='DaggerAfterimage'
    for _,p in ghost:GetDescendants() do if p:IsA('BasePart') then p.Material=Enum.Material.Neon;p.Color=crimson;p.Transparency=.45;p.TextureID='' elseif not p:IsA('Model') then p:Destroy() end end
    ghost.Parent=folder
    K.animate(.2,function(t) for _,p in ghost:GetDescendants() do if p:IsA('BasePart') then p.Transparency=.45+.55*t end end end,function() ghost:Destroy();afterimages-=1 end,'daggerGhost',40)
   end
   for i=1,#points do
    if not struck[i] and age>=times[i+1] then
     struck[i]=true
     local at=spots[i+1];local camera=workspace.CurrentCamera
     slashFlash(folder,at,crimson,4.8,camera and (camera.CFrame.Position-at).Unit or Vector3.zAxis)
     K.shards(folder,at,hot,5,11,.3,.14);K.flash(folder,at,crimson,10,3,.2)
    end
   end
  end,function() for _,c in copies do c.model:Destroy() end end,'daggerChain',16)
 end

 -- Vampire Blade wisp (40) ------------------------------------------------------------------------------
 local function wisp(ownerId,position)
  local owner=Players:GetPlayerByUserId(ownerId)
  local root=owner and owner.Character and owner.Character:FindFirstChild('HumanoidRootPart')
  if not root or not K.near(position,150) then return end
  local red,hot=STYLE['40'].glow,STYLE['40'].hot
  local orb=K.ball(folder,'BloodWisp',.55,hot,0,Enum.Material.Neon)
  local shell=K.ball(folder,'BloodWispShell',1.1,red,.55,Enum.Material.Neon)
  K.trail(orb,.6,.3,red,rgb(60,0,10),.05,true)
  local light=Instance.new('PointLight');light.Color=red;light.Range=8;light.Brightness=3;light.Shadows=false;light.Parent=orb
  local side=(math.random()<.5 and -1 or 1)*(2+math.random()*2)
  local from=position+Vector3.yAxis*1.2
  K.animate(.5,function(t)
   local to=root.Parent and root.Position or from
   local mid=(from+to)/2+Vector3.yAxis*4+(to-from):Cross(Vector3.yAxis).Unit*side
   local e=t*t*(3-2*t);local a=from:Lerp(mid,e);local b=mid:Lerp(to,e);local p=a:Lerp(b,e)
   orb.Position=p;shell.Position=p;shell.Size=Vector3.one*(1.1+.25*math.sin(t*20))
  end,function()
   orb:Destroy();shell:Destroy()
   if not root.Parent or not folder.Parent then return end
   local feet=Vector3.new(root.Position.X,ground(root.Position)+.1,root.Position.Z)
   shockwave(folder,feet,red,.5,3.4,.4,.15)
   burst(folder,root.Position,{texture=TEX.Glow,color=hot,color2=red,size=seq(0,.5,1,0),alpha=seq(0,0,1,1),life=.5,speed=3,speed1=6,spread=180,accel=Vector3.yAxis*4},10)
   K.flash(folder,root.Position,red,10,3,.3)
  end,'wisp',24)
 end

 -- Ray Gun (41) ----------------------------------------------------------------------------------
 local function greenBurst(position,radius)
  if not K.near(position,160) then return end
  local green,hot=STYLE['41'].glow,STYLE['41'].hot
  K.pop(folder,position,green,.6,radius*2,.32,.35);K.pop(folder,position,hot,.3,radius*.9,.2,.2)
  shockwave(folder,Vector3.new(position.X,ground(position)+.1,position.Z),green,.4,radius*1.1,.38,0)
  burst(folder,position,{texture=TEX.Pixel,color=hot,color2=green,size=seq(0,.45,1,.05),alpha=seq(0,0,1,1),life=.45,life1=.7,speed=8,speed1=15,spread=180,drag=3},16)
  K.flash(folder,position,green,radius*3,5,.3)
 end
 -- A kill by the Ray Gun: the mob's own shape turns green Neon and crumbles upward into pixels.
 function api.hit(npc,lethal,secondary,weaponId,position)
  if weaponId=='40' and not lethal and not secondary and position and K.near(position,90) then
   burst(folder,position,{texture=TEX.Glow,color=rgb(170,0,20),color2=rgb(60,0,8),size=seq(0,.35,1,.1),alpha=seq(0,0,1,1),life=.35,speed=6,speed1=10,spread=70,accel=Vector3.new(0,-28,0),light=.3,influence=.5},6)
   return
  end
  if weaponId~='41' or not lethal or not npc or not npc.Parent or not position or not K.near(position,120) then return end
  local green,hot=STYLE['41'].glow,STYLE['41'].hot
  local pieces={}
  for _,p in npc:GetDescendants() do
   if #pieces>=14 then break end
   if p:IsA('BasePart') and p.Transparency<.9 and p.Name~='HumanoidRootPart' then
    local ok,copy=pcall(function() return p:Clone() end)
    if ok and copy then
     copy:ClearAllChildren();copy.Anchored=true;copy.CanCollide=false;copy.CanTouch=false;copy.CanQuery=false;copy.CastShadow=false
     copy.Material=Enum.Material.Neon;copy.Color=green:Lerp(hot,math.random()*.5);copy.Transparency=.15
     if copy:IsA('MeshPart') then pcall(function() copy.TextureID='' end) end
     copy.Parent=folder;pieces[#pieces+1]={part=copy,cf=p.CFrame,size=copy.Size,drift=Vector3.new(math.random()-.5,1.4+math.random(),math.random()-.5)}
    end
   end
  end
  K.animate(.55,function(t)
   local e=smooth(t)
   for _,s in pieces do
    s.part.Size=s.size*(1-e*.85)
    s.part.CFrame=s.cf+s.drift*e*1.8
    s.part.Transparency=.15+.85*smooth((t-.25)/.75)
   end
  end,function() for _,s in pieces do s.part:Destroy() end end,'dissolve',20)
  burst(folder,position,{texture=TEX.Pixel,color=hot,color2=green,size=seq(0,.35,1,.05),alpha=seq(0,0,1,1),life=.6,life1=.9,speed=2,speed1=5,spread=60,accel=Vector3.yAxis*6,shape=Enum.ParticleEmitterShape.Box},22)
 end
 -- Bolts follow the server's projectile segments; returns true when it drew the shot.
 function api.shot(origin,finish,kind,id,thickness,blastRadius,contact,normal,ownerId,slotIndex,first,mobContact,shotId,projectileId,projectileSpeed,terminal)
  if id~='41' then return false end
  if not K.near(origin,170) and not K.near(finish,170) then return true end
  local green,hot=STYLE['41'].glow,STYLE['41'].hot
  local b=projectileId and bolts[projectileId]
  if first or not b then
   local v=ownerId and lookup(ownerId,slotIndex)
   local muzzle=origin
   if v and v.godly then
    v.godly.kick=os.clock()
    local m=v.model:FindFirstChild('Muzzle',true);if m then muzzle=m.WorldPosition end
   end
   if first then
    local look=(finish-muzzle).Magnitude>.05 and (finish-muzzle).Unit or -Vector3.zAxis
    local ring=K.part(folder,'RayMuzzleRing',Vector3.new(.08,1,1),green,.1,Enum.Material.Neon,Enum.PartType.Cylinder)
    K.animate(.16,function(t) ring.Size=Vector3.new(.08,.4+t*2.2,.4+t*2.2);ring.CFrame=CFrame.lookAt(muzzle,muzzle+look)*CFrame.Angles(0,math.pi/2,0);ring.Transparency=.1+.9*t end,function() ring:Destroy() end,'rayRing',24)
    K.flash(folder,muzzle,green,9,4,.15)
   end
   local core=K.part(folder,'RayBolt',Vector3.new(.22,.22,1.3),hot,0,Enum.Material.Neon)
   local shell=K.part(folder,'RayBoltShell',Vector3.new(.5,.5,1.6),green,.45,Enum.Material.Neon)
   K.trail(core,.45,.16,hot,green,.05,true)
   local light=Instance.new('PointLight');light.Color=green;light.Range=7;light.Brightness=3;light.Shadows=false;light.Parent=core
   b={core=core,shell=shell,from=muzzle,to=finish,t0=os.clock(),speed=math.max(20,projectileSpeed or 150)}
   if projectileId then bolts[projectileId]=b end
  else
   b.from=b.core.Position;b.to=finish;b.t0=os.clock()
  end
  b.terminal=terminal;b.contact=contact
  return true
 end
 local function stepBolts()
  local now=os.clock()
  for id,b in bolts do
   local length=(b.to-b.from).Magnitude
   local f=length<.01 and 1 or math.min(1,(now-b.t0)*b.speed/length)
   local p=b.from:Lerp(b.to,f);local look=length>.01 and (b.to-b.from).Unit or -Vector3.zAxis
   local cf=CFrame.lookAt(p,p+look)
   b.core.CFrame=cf*CFrame.Angles(0,0,now*25);b.shell.CFrame=cf;b.shell.Size=Vector3.new(.5,.5,1.6)*(1+.15*math.sin(now*40))
   if (f>=1 and b.terminal) or now-b.t0>2 then
    bolts[id]=nil;b.core:Destroy();b.shell:Destroy()
    if b.terminal and b.contact and K.near(p,150) then
     burst(folder,p,{texture=TEX.Star,color=STYLE['41'].hot,color2=STYLE['41'].glow,size=seq(0,.8,1,2.4),alpha=seq(0,0,1,1),life=.15,speed=0,spread=0},1)
     K.shards(folder,p,STYLE['41'].glow,4,8,.25,.12)
    end
   end
  end
 end

 combat:WaitForChild('GodlyFX').OnClientEvent:Connect(function(kind,...)
  local a={...}
  if kind=='Rise' then rise(a[1],a[3],a[4],a[5])
  elseif kind=='Chase' then local w=wraiths[a[1]];if w then w.target=a[2] end
  elseif kind=='Claw' then claw(a[1],a[2])
  elseif kind=='Fade' then fadeWraith(a[1])
  elseif kind=='Wave' then wave(a[2],a[3],a[4])
  elseif kind=='Rain' then rain(a[1],a[2],a[3],a[4],a[5],a[6],a[7],a[8])
  elseif kind=='Chain' then daggerChain(a[1],a[2],a[3],a[4],a[5],a[6],a[7])
  elseif kind=='Wisp' then wisp(a[1],a[2])
  elseif kind=='Burst' then greenBurst(a[2],a[3]) end
 end)
 RunService.RenderStepped:Connect(function(dt)
  if next(wraiths) then stepWraiths(math.min(dt,.1)) end
  if next(bolts) then stepBolts() end
 end)
 return api
end
return V
