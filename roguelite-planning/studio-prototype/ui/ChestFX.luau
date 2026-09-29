-- Chest auras and chest-opening effects. Client-only presentation: every instance made here is
-- created on the client (never replicated), and the chest models are only moved locally.
--
-- A chest model (installed by blender-chest-kit/studio-install-chests.luau) is a Model whose pivot
-- is the ground centre with the front facing the pivot's LookVector. Parts carry a `Kind`
-- attribute (textured | glow | floor | accent); parts that swing with the lid have `Lid = true`.
-- The model's `Hinge` attribute is the lid hinge CFrame in pivot space and `OpenDeg` its angle.
--
-- FX.aura(model, colors) -> aura: coloured wisps rising around the chest, light leaking out of the
-- lid seam, sparkles, a back glow with slow rays, a ground glow and a light inside the chest.
-- aura:SetLevel(0..3) charges it up (each click of the opening), aura:Burst(scale, colors) is the
-- explosion when the lid flies open.
local TweenService=game:GetService('TweenService')
local RunService=game:GetService('RunService')
local FX={}

FX.Tex={
 glow='rbxassetid://82171749127523',star='rbxassetid://119142062258395',streak='rbxassetid://95826913551457',
 wisp='rbxassetid://98763107983691',ring='rbxassetid://112313196019616',rays='rbxassetid://95423827430619',
 shaft='rbxassetid://81309750877710',mote='rbxassetid://88119068890270',
}
-- ProSoundEffects library sounds (free, Roblox-licensed) plus two Creator Store stingers.
-- Plain numbers so AssetPreloader (which preloads rbxassetid strings as images) skips them.
FX.Sounds={
 Shake1=9119127069, -- Shutter Bangs Rattle Shaking Wood Hits 11
 Shake2=9119126475, -- Shutter Bangs Rattle Shaking Wood Hits 4
 Charge=9120733055, -- Whoosh Rising Swish Airy
 Open=9120873380,   -- Wooden Chest Open Close Cedar Box 1
 Chime=9116394545,  -- Magic Glows Soft Clusters Of Chiming Hits 1
 Burst=119620526223720, -- "Explosion Prize" (Creator Store)
 Legendary=128460880879263, -- "Rare Achievement" (Creator Store)
 -- Wood-crack taps for the two shakes, trialled on the Gold (VIP free daily) chest only.
 -- User-supplied Pixabay file split and made cartoony by audio/process_audio.py.
 GoldShake1=135215998961802,GoldShake2=117464991289206,
}

local WHITE=Color3.new(1,1,1)
local function lighten(c,t) return c:Lerp(WHITE,t) end
local function seq(...) local k={};local a={...};for i=1,#a,2 do table.insert(k,NumberSequenceKeypoint.new(a[i],a[i+1])) end;return NumberSequence.new(k) end
local function tween(obj,time,props,style,dir)
 local tw=TweenService:Create(obj,TweenInfo.new(time,style or Enum.EasingStyle.Quad,dir or Enum.EasingDirection.Out),props);tw:Play();return tw
end

function FX.play(id,volume,pitch)
 if not id then return end
 local s=Instance.new('Sound');s.SoundId='rbxassetid://'..id;s.Volume=volume or .5;s.PlaybackSpeed=pitch or 1
 s.SoundGroup=game:GetService('SoundService'):FindFirstChild('RogueliteSFX') -- Settings SFX slider
 s.Parent=game:GetService('SoundService');game:GetService('SoundService'):PlayLocalSound(s)
 task.delay(6,function() s:Destroy() end)
end

local localFolder
function FX.folder()
 if localFolder and localFolder.Parent then return localFolder end
 localFolder=Instance.new('Folder');localFolder.Name='ChestFXLocal';localFolder.Parent=workspace
 return localFolder
end
local function anchor(name,cf,size,parent)
 local p=Instance.new('Part');p.Name=name;p.Anchored=true;p.CanCollide=false;p.CanQuery=false;p.CanTouch=false
 p.CastShadow=false;p.Transparency=1;p.Size=size;p.CFrame=cf;p.Parent=parent or FX.folder()
 return p
end
local function emitter(parent,props)
 local e=Instance.new('ParticleEmitter')
 e.LightInfluence=0;e.LightEmission=1;e.Rate=0
 for k,v in props do e[k]=v end
 e.Parent=parent;return e
end

-- Geometry helpers -------------------------------------------------------------------------
function FX.bounds(model)
 local cf,size=model:GetBoundingBox()
 return cf,size
end
function FX.parts(model,kind)
 local out={}
 for _,d in model:GetDescendants() do
  if d:IsA('BasePart') and (kind==nil or d:GetAttribute('Kind')==kind) then table.insert(out,d) end
 end
 return out
end
-- The seam: where light leaks out between body and lid (the Chest_Glow part's box, or the
-- hinge height across the chest when a model has none).
local function seamBox(model)
 local glow=FX.parts(model,'glow')[1]
 local pivot=model:GetPivot()
 if glow then return glow.CFrame,glow.Size end
 local _,size=model:GetBoundingBox()
 local hinge=model:GetAttribute('Hinge') or CFrame.new(0,size.Y*.55,0)
 return pivot*CFrame.new(0,hinge.Y,0),Vector3.new(size.X*.9,.3,size.Z*.8)
end

-- Remembers every part's CFrame so shakes and the lid can be animated and undone exactly.
local rest=setmetatable({},{__mode='k'})
function FX.rest(model)
 local r=rest[model]
 if not r then
  r={pivot=model:GetPivot(),parts={}}
  for _,p in FX.parts(model) do r.parts[p]=r.pivot:ToObjectSpace(p.CFrame) end
  rest[model]=r
 end
 return r
end
-- Place the chest at `offset` (relative to its resting pivot) with the lid at `lidDeg`.
function FX.pose(model,offset,lidDeg)
 local r=FX.rest(model)
 local pivot=r.pivot*(offset or CFrame.identity)
 local hinge=model:GetAttribute('Hinge')
 local lid=hinge and lidDeg and lidDeg~=0 and hinge*CFrame.Angles(math.rad(lidDeg),0,0)*hinge:Inverse() or nil
 for p,rel in r.parts do
  if p.Parent then
   if lid and p:GetAttribute('Lid') then p.CFrame=pivot*lid*rel else p.CFrame=pivot*rel end
  end
 end
end
local lidState=setmetatable({},{__mode='k'})
local lidToken=setmetatable({},{__mode='k'})
function FX.reset(model)
 lidToken[model]=nil;lidState[model]=nil
 if rest[model] then FX.pose(model,nil,0);rest[model]=nil end
end

-- Aura ----------------------------------------------------------------------------------------
-- colors: {aura=Color3, glow=Color3?, accent=Color3?}
function FX.aura(model,colors)
 local folder=Instance.new('Folder');folder.Name='Aura_'..model.Name;folder.Parent=FX.folder()
 local cf,size=model:GetBoundingBox()
 local pivot=model:GetPivot()
 local base=math.max(size.X,size.Z)
 local scale=base/7 -- effects were tuned on the 7-stud Gold chest
 local aura=colors.aura;local glowColor=colors.glow or aura
 local self={Model=model,Folder=folder,Level=0,Color=aura,Scale=scale}

 -- Core volume: the chest's footprint, wisps and sparkles rise out of it.
 local core=anchor('Core',CFrame.new(cf.Position),Vector3.new(size.X*.95,size.Y*.6,size.Z*.95),folder)
 local wisps=emitter(core,{Name='Wisps',Texture=FX.Tex.wisp,Color=ColorSequence.new(lighten(aura,.15),aura),
  Size=seq(0,1.3*scale,.4,2.6*scale,1,.4*scale),Transparency=seq(0,1,.2,.55,.7,.7,1,1),
  Lifetime=NumberRange.new(1.4,2.4),Speed=NumberRange.new(1.2*scale,2.4*scale),Acceleration=Vector3.new(0,1.2,0),
  Rotation=NumberRange.new(-25,25),RotSpeed=NumberRange.new(-15,15),EmissionDirection=Enum.NormalId.Top,
  SpreadAngle=Vector2.new(12,12),LightEmission=.85,ZOffset=-.5})
 wisps.Shape=Enum.ParticleEmitterShape.Box;wisps.ShapeInOut=Enum.ParticleEmitterShapeInOut.Outward;wisps.ShapeStyle=Enum.ParticleEmitterShapeStyle.Volume
 local sparkles=emitter(core,{Name='Sparkles',Texture=FX.Tex.star,Color=ColorSequence.new(WHITE,lighten(aura,.35)),
  Size=seq(0,0,.2,.55*scale,1,0),Transparency=seq(0,0,.8,.2,1,1),Lifetime=NumberRange.new(.9,1.7),
  Speed=NumberRange.new(.8,2.2),SpreadAngle=Vector2.new(180,180),Acceleration=Vector3.new(0,1.5,0),
  Rotation=NumberRange.new(0,360),RotSpeed=NumberRange.new(-90,90)})
 sparkles.Shape=Enum.ParticleEmitterShape.Box
 local motes=emitter(core,{Name='Motes',Texture=FX.Tex.mote,Color=ColorSequence.new(lighten(aura,.4)),
  Size=seq(0,.18*scale,1,0),Transparency=seq(0,.1,1,1),Lifetime=NumberRange.new(1.5,2.8),
  Speed=NumberRange.new(.5,1.4),SpreadAngle=Vector2.new(60,60),Acceleration=Vector3.new(0,.8,0)})
 motes.Shape=Enum.ParticleEmitterShape.Box
 -- Light leaking out of the lid seam: short upright streaks all along it, and a light inside.
 local seamCf,seamSize=seamBox(model)
 local seam=anchor('Seam',CFrame.new(seamCf.Position)*(pivot-pivot.Position),Vector3.new(seamSize.X*.92,.2,math.max(seamSize.Z*.9,.4)),folder)
 local streaks=emitter(seam,{Name='Streaks',Texture=FX.Tex.streak,Color=ColorSequence.new(lighten(glowColor,.5),glowColor),
  Size=seq(0,.45*scale,1,.1*scale),Transparency=seq(0,.15,.6,.3,1,1),Lifetime=NumberRange.new(.25,.5),
  Speed=NumberRange.new(2.5,4.5),EmissionDirection=Enum.NormalId.Top,SpreadAngle=Vector2.new(8,8),
  Orientation=Enum.ParticleOrientation.VelocityParallel,Squash=seq(0,1.2,1,1.8)})
 streaks.Shape=Enum.ParticleEmitterShape.Box
 local light=Instance.new('PointLight');light.Color=glowColor;light.Range=base*1.5;light.Brightness=1.4;light.Shadows=false;light.Parent=seam
 -- Back glow and slow rays, billboarded just behind the chest (the chest hides their centre).
 local back=pivot.LookVector*-(size.Z*.35)
 local halo=Instance.new('BillboardGui');halo.Name='Halo';halo.Adornee=core;halo.LightInfluence=0;halo.AlwaysOnTop=false
 halo.Size=UDim2.fromScale(base*2.3,base*2.3);halo.StudsOffsetWorldSpace=back+Vector3.new(0,size.Y*.1,0);halo.MaxDistance=450;halo.Parent=core
 local haloGlow=Instance.new('ImageLabel');haloGlow.Name='Glow';haloGlow.BackgroundTransparency=1;haloGlow.Image=FX.Tex.glow;haloGlow.ImageColor3=aura
 haloGlow.ImageTransparency=.5;haloGlow.AnchorPoint=Vector2.new(.5,.5);haloGlow.Position=UDim2.fromScale(.5,.5);haloGlow.Size=UDim2.fromScale(1,1);haloGlow.Parent=halo
 local haloRays=Instance.new('ImageLabel');haloRays.Name='Rays';haloRays.BackgroundTransparency=1;haloRays.Image=FX.Tex.rays;haloRays.ImageColor3=lighten(aura,.25)
 haloRays.ImageTransparency=.72;haloRays.AnchorPoint=Vector2.new(.5,.5);haloRays.Position=UDim2.fromScale(.5,.5);haloRays.Size=UDim2.fromScale(1.15,1.15);haloRays.Parent=halo
 -- Ground glow under the chest.
 local ground=anchor('Ground',pivot*CFrame.new(0,.06,0),Vector3.new(base*2.2,.05,base*2.2),folder)
 local decal=Instance.new('Decal');decal.Face=Enum.NormalId.Top;decal.Texture=FX.Tex.glow;decal.Color3=aura;decal.Transparency=.35;decal.Parent=ground
 -- Neon parts on the chest (seam glow, open floor): tinted to the chest glow.
 local neons={}
 for _,p in FX.parts(model) do
  local k=p:GetAttribute('Kind')
  if k=='glow' or k=='floor' then p.Color=glowColor;table.insert(neons,p) end
 end

 self.Core,self.Seam,self.Light,self.Halo=core,seam,light,halo
 self.Emitters={wisps=wisps,sparkles=sparkles,motes=motes,streaks=streaks}
 -- Level targets: idle, click 1, click 2, about to burst.
 local LEVELS={
  {rate={wisps=7,sparkles=5,motes=8,streaks=16},light=2,halo=1.1,haloT=.38,raysT=.6,decalT=.28,spin=8},
  {rate={wisps=9,sparkles=8,motes=10,streaks=26},light=3,halo=1.2,haloT=.38,raysT=.55,decalT=.25,spin=18},
  {rate={wisps=16,sparkles=16,motes=18,streaks=48},light=5,halo=1.45,haloT=.25,raysT=.4,decalT=.15,spin=40},
  {rate={wisps=28,sparkles=30,motes=30,streaks=80},light=8,halo=1.75,haloT=.12,raysT=.25,decalT=.05,spin=90},
 }
 local cur={light=2,halo=1.1,haloT=.38,raysT=.6,decalT=.28,spin=8}
 local target=LEVELS[1]
 local t0=os.clock()
 local conn=RunService.RenderStepped:Connect(function(dt)
  local k=1-math.exp(-dt*6)
  for key in cur do cur[key]+=(target[key]-cur[key])*k end
  local wob=1+math.sin((os.clock()-t0)*2.2)*.06
  light.Brightness=cur.light*wob
  halo.Size=UDim2.fromScale(base*2.3*cur.halo*wob,base*2.3*cur.halo*wob)
  haloGlow.ImageTransparency=cur.haloT;haloRays.ImageTransparency=cur.raysT;decal.Transparency=cur.decalT
  haloRays.Rotation=(haloRays.Rotation+cur.spin*dt)%360
  for _,p in neons do p.Transparency=.08+.12*(1-wob)/.06*.5 end
 end)
 function self:SetLevel(level)
  self.Level=math.clamp(level,0,3)
  target=LEVELS[self.Level+1]
  for name,e in self.Emitters do e.Rate=target.rate[name] end
 end
 -- Tint the whole aura (e.g. to hint at the best rarity inside while charging).
 function self:SetColor(c,glow)
  self.Color=c;glow=glow or c
  wisps.Color=ColorSequence.new(lighten(c,.15),c);sparkles.Color=ColorSequence.new(WHITE,lighten(c,.35))
  motes.Color=ColorSequence.new(lighten(c,.4));streaks.Color=ColorSequence.new(lighten(glow,.5),glow)
  light.Color=glow;haloGlow.ImageColor3=c;haloRays.ImageColor3=lighten(c,.25);decal.Color3=c
  for _,p in neons do p.Color=glow end
 end
 -- Short puff at a click: a ring of sparkles and streaks, light kick.
 function self:Pulse(strength)
  strength=strength or 1
  sparkles:Emit(math.floor(14*strength));streaks:Emit(math.floor(24*strength));motes:Emit(math.floor(10*strength))
  light.Brightness+=6*strength
  FX.ring(pivot*CFrame.new(0,.15,0),self.Color,base*.8,base*(1.6+strength*.6),.45)
 end
 function self:Hide(hidden)
  for _,e in self.Emitters do e.Enabled=not hidden end
  halo.Enabled=not hidden;light.Enabled=not hidden;decal.Transparency=hidden and 1 or cur.decalT
 end
 function self:Destroy()
  conn:Disconnect();folder:Destroy()
 end
 self:SetLevel(0)
 return self
end

-- One-shot effects ----------------------------------------------------------------------------
-- Flat expanding ring on the ground (shockwave).
function FX.ring(cf,color,from,to,duration)
 local p=anchor('Ring',cf,Vector3.new(from,.05,from))
 local d=Instance.new('Decal');d.Face=Enum.NormalId.Top;d.Texture=FX.Tex.ring;d.Color3=lighten(color,.2);d.Transparency=.05;d.Parent=p
 tween(p,duration,{Size=Vector3.new(to,.05,to)},Enum.EasingStyle.Quart)
 tween(d,duration,{Transparency=1},Enum.EasingStyle.Quad,Enum.EasingDirection.In)
 task.delay(duration+.05,function() p:Destroy() end)
end

-- The lid bursting open. scale: 1 for one chest, bigger for ×10 / ×100 (more of everything).
-- colors: {aura, best} where best is the best rarity colour inside.
function FX.burst(aura,scale,best)
 local model=aura.Model
 local pivot=FX.rest(model).pivot
 local cf,size=model:GetBoundingBox()
 local base=math.max(size.X,size.Z)
 local color=best or aura.Color
 local mouth=pivot*CFrame.new(0,(model:GetAttribute('Hinge') or CFrame.new(0,size.Y*.55,0)).Y,0)
 local burst=anchor('Burst',mouth,Vector3.new(size.X*.7,.3,size.Z*.6))
 -- Sparkle and mote fountain out of the chest.
 local stars=emitter(burst,{Texture=FX.Tex.star,Color=ColorSequence.new(WHITE,lighten(color,.3)),Size=seq(0,.9,.3,.7,1,0),
  Transparency=seq(0,0,.8,.1,1,1),Lifetime=NumberRange.new(1,2),Speed=NumberRange.new(10,22),SpreadAngle=Vector2.new(40,40),
  EmissionDirection=Enum.NormalId.Top,Acceleration=Vector3.new(0,-18,0),Drag=1.5,Rotation=NumberRange.new(0,360),RotSpeed=NumberRange.new(-180,180)})
 local motes=emitter(burst,{Texture=FX.Tex.mote,Color=ColorSequence.new(lighten(color,.2),color),Size=seq(0,.45,1,0),
  Transparency=seq(0,0,1,.6),Lifetime=NumberRange.new(1.2,2.4),Speed=NumberRange.new(8,26),SpreadAngle=Vector2.new(55,55),
  EmissionDirection=Enum.NormalId.Top,Acceleration=Vector3.new(0,-14,0),Drag=1})
 local puff=emitter(burst,{Texture=FX.Tex.wisp,Color=ColorSequence.new(lighten(color,.35),color),Size=seq(0,2,1,7),
  Transparency=seq(0,.25,1,1),Lifetime=NumberRange.new(.6,1),Speed=NumberRange.new(6,12),SpreadAngle=Vector2.new(70,70),
  EmissionDirection=Enum.NormalId.Top,Drag=4,Rotation=NumberRange.new(0,360),LightEmission=.9})
 local k=math.clamp(scale,1,5)
 stars:Emit(math.floor(40*k));motes:Emit(math.floor(60*k));puff:Emit(math.floor(10+4*k))
 -- Light shafts rising out of the chest (god rays), more for bigger openings.
 local shafts={}
 for i=1,math.floor(4+k*1.6) do
  local a0=Instance.new('Attachment');a0.Position=Vector3.new((math.random()-.5)*size.X*.5,0,(math.random()-.5)*size.Z*.4);a0.Parent=burst
  local a1=Instance.new('Attachment');a1.Position=a0.Position+Vector3.new((math.random()-.5)*6,18+math.random()*14,(math.random()-.5)*6);a1.Parent=burst
  local b=Instance.new('Beam');b.Attachment0=a0;b.Attachment1=a1;b.Texture=FX.Tex.shaft;b.TextureMode=Enum.TextureMode.Stretch
  b.FaceCamera=true;b.LightEmission=1;b.LightInfluence=0;b.Color=ColorSequence.new(lighten(color,.4),color)
  local w=(1.2+math.random()*1.8)*base/7;b.Width0=w;b.Width1=w*2.4;b.Transparency=NumberSequence.new(1);b.Parent=burst
  table.insert(shafts,b)
 end
 -- Big glow flash at the mouth.
 local flash=Instance.new('BillboardGui');flash.Adornee=burst;flash.LightInfluence=0;flash.AlwaysOnTop=false;flash.Size=UDim2.fromScale(base,base);flash.Parent=burst
 local fg=Instance.new('ImageLabel');fg.BackgroundTransparency=1;fg.Image=FX.Tex.glow;fg.ImageColor3=lighten(color,.5);fg.Size=UDim2.fromScale(1,1);fg.Parent=flash
 local fr=Instance.new('ImageLabel');fr.BackgroundTransparency=1;fr.Image=FX.Tex.rays;fr.ImageColor3=lighten(color,.3);fr.AnchorPoint=Vector2.new(.5,.5)
 fr.Position=UDim2.fromScale(.5,.5);fr.Size=UDim2.fromScale(1.3,1.3);fr.Parent=flash
 tween(flash,.35,{Size=UDim2.fromScale(base*(3.2+k*.5),base*(3.2+k*.5))},Enum.EasingStyle.Back)
 tween(fg,1.1,{ImageTransparency=1},Enum.EasingStyle.Quad,Enum.EasingDirection.In)
 tween(fr,1.6,{ImageTransparency=1,Rotation=70},Enum.EasingStyle.Quad,Enum.EasingDirection.In)
 local start=os.clock()
 local conn;conn=RunService.RenderStepped:Connect(function()
  local t=os.clock()-start
  for i,b in shafts do
   local a=math.clamp(t/.25,0,1)*(1-math.clamp((t-.9-i*.05)/1.2,0,1))
   b.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,1-.75*a),NumberSequenceKeypoint.new(1,1)})
  end
  if t>3 then conn:Disconnect() end
 end)
 FX.ring(pivot*CFrame.new(0,.15,0),color,base,base*(4+k),.7)
 FX.ring(pivot*CFrame.new(0,.2,0),lighten(color,.4),base*.6,base*(2.6+k*.6),.5)
 aura.Light.Brightness=14+k*2
 aura:Pulse(1.5)
 task.delay(3.4,function() burst:Destroy() end)
end

-- Shake: a decaying rattle with a hop. strength 1 (first click) .. 2 (second click).
function FX.shake(model,strength,duration)
 duration=duration or .55
 local start=os.clock()
 local conn;conn=RunService.RenderStepped:Connect(function()
  local t=os.clock()-start
  if t>=duration then conn:Disconnect();FX.pose(model,nil,lidState[model] or 0);return end
  local decay=(1-t/duration)^1.6
  local wob=math.sin(t*38)*decay
  local hop=math.max(0,math.sin(math.min(t/.22,1)*math.pi))*.35*strength
  FX.pose(model,CFrame.new(math.sin(t*29)*.08*strength*decay,hop,0)*CFrame.Angles(math.rad(wob*2.5*strength),0,math.rad(wob*5*strength)),lidState[model] or 0)
 end)
 return conn
end

-- Lid: animate from its current angle to `deg` over `time`. Returns immediately.
function FX.lid(model,deg,time,style)
 local from=lidState[model] or 0
 local start=os.clock()
 local mine={};lidToken[model]=mine -- a newer lid animation cancels this one
 local c;c=RunService.RenderStepped:Connect(function()
  if lidToken[model]~=mine then c:Disconnect();return end
  local a=math.clamp((os.clock()-start)/time,0,1)
  local e=TweenService:GetValue(a,style or Enum.EasingStyle.Back,Enum.EasingDirection.Out)
  local d=from+(deg-from)*e
  lidState[model]=d
  FX.pose(model,nil,d)
  if a>=1 then c:Disconnect() end
 end)
end
function FX.lidAngle(model) return lidState[model] or 0 end

return FX
