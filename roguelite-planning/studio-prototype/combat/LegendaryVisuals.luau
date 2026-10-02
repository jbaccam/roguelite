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
-- Meshes (SlashCore, SlashGlow, ShockRing) are authored in roguelite-planning/blender-legendary-vfx
-- and arrive as MeshData; they are built with EditableMesh, and if that isn't possible every
-- effect still draws with Neon parts. Effects far from the camera are skipped.
-- Sandboxed like the combat client that requires it: no sounds here (RogueliteSounds plays them).
local RunService=game:GetService('RunService')
local Players=game:GetService('Players')
local TweenService=game:GetService('TweenService')
local Assets=game:GetService('AssetService')
local Catalog=require(script.Parent:WaitForChild('WeaponCatalog'))
local K=require(script.Parent:WaitForChild('VfxKit'))
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
-- Floating headline over a point ("ROYAL FLUSH!", "STRIKE!"): slams in, holds, rises and fades.
local function headline(folder,position,text,face,stroke,size,follow)
 local anchor=K.part(folder,'LegendaryHeadline',Vector3.one*.1,K.White,1);anchor.Position=position
 local gui=Instance.new('BillboardGui');gui.Size=UDim2.fromOffset(420,120);gui.AlwaysOnTop=true;gui.MaxDistance=140;gui.LightInfluence=0;gui.Parent=anchor
 local label=Instance.new('TextLabel');label.Size=UDim2.fromScale(1,1);label.BackgroundTransparency=1;label.Text=text
 label.Font=Enum.Font.FredokaOne;label.TextSize=size or 46;label.TextColor3=K.White;label.TextStrokeTransparency=1;label.Parent=gui
 local grad=Instance.new('UIGradient');grad.Rotation=90;grad.Color=ColorSequence.new(face[1],face[2]);grad.Parent=label
 local outline=Instance.new('UIStroke');outline.Color=stroke;outline.Thickness=4;outline.LineJoinMode=Enum.LineJoinMode.Round;outline.Parent=label
 local scale=Instance.new('UIScale');scale.Scale=2.1;scale.Parent=label
 label.Rotation=-9
 TweenService:Create(scale,TweenInfo.new(.28,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Scale=1}):Play()
 TweenService:Create(label,TweenInfo.new(.35,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Rotation=0}):Play()
 K.animate(1.25,function(_,age)
  local base=follow and follow() or position
  anchor.Position=base+Vector3.yAxis*(age>.75 and (age-.75)*4 or 0)
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

-- Meshes from MeshData (blender-legendary-vfx), built once on first need -------------------------
local templates,meshState={},nil
local keepAlive={}
local function linearToColor(v)
 local function s(x) return x<=.0031308 and x*12.92 or 1.055*x^(1/2.4)-.055 end
 return Color3.new(s(v[1]),s(v[2]),s(v[3]))
end
local function buildMeshes()
 if meshState then return end
 meshState='building'
 task.spawn(function()
  local ok,err=pcall(function()
   local data=require(script:WaitForChild('MeshData'))
   for name,r in data do
    local mesh=assert(Assets:CreateEditableMesh(),'no EditableMesh')
    local ids={}
    for i,v in r.v do ids[i]=mesh:AddVertex(Vector3.new(v[1],v[2],v[3])) end
    for i,f in r.f do
     local face=mesh:AddTriangle(ids[f[1]],ids[f[2]],ids[f[3]])
     local color=linearToColor(r.c[i])
     local a1,a2,a3=r.a[f[1]],r.a[f[2]],r.a[f[3]]
     local c1=mesh:AddColor(color,a1)
     local c2=a2==a1 and c1 or mesh:AddColor(color,a2)
     local c3=a3==a1 and c1 or a3==a2 and c2 or mesh:AddColor(color,a3)
     mesh:SetFaceColors(face,{c1,c2,c3})
    end
    local fixed=assert(Assets:CreateEditableMeshAsync(Content.fromObject(mesh),{FixedSize=true}),'no fixed mesh')
    mesh:Destroy();table.insert(keepAlive,fixed)
    local part=Assets:CreateMeshPartAsync(Content.fromObject(fixed))
    part.Name=name;part.Anchored=true;part.CanCollide=false;part.CanTouch=false;part.CanQuery=false;part.CastShadow=false
    part.DoubleSided=true;part.Material=r.glow and Enum.Material.Neon or Enum.Material.SmoothPlastic;part.Color=Color3.new(1,1,1)
    templates[name]={part=part,size=Vector3.new(r.size[1],r.size[2],r.size[3])}
    task.wait()
   end
  end)
  meshState=ok and 'ready' or 'failed'
  if not ok then warn('Legendary meshes: drawing with parts instead ('..tostring(err)..')') end
 end)
end
-- A clone of a built mesh, or nil while building or after a failure (callers fall back to parts).
local function mesh(folder,name)
 local t=templates[name];if not t then return nil end
 local p=t.part:Clone();p.Parent=folder;return p,t.size
end

function V.mount(combat,folder,lookup)
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
  buildMeshes()
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

 -- Slash (Katana) and Beam (Excalibur) ------------------------------------------------------------
 local function crescentParts(color,width)
  -- Fallback crescent: Neon segments in the shape of the mesh (thin edge, wide middle).
  local list={}
  for i=1,11 do
   local th=math.rad(-76+152*(i-1)/10)
   local w=math.cos(th/math.rad(78)*math.pi/2)^1.2
   local p=K.part(folder,'SlashSeg',Vector3.new(.3,.06,.1),color,1,Enum.Material.Neon)
   list[i]={part=p,th=th,w=w}
  end
  return {parts=list,width=width}
 end
 local function placeCrescent(c,cf,radius,alpha)
  for _,s in c.parts do
   local d=Vector3.new(math.sin(s.th),0,-math.cos(s.th))
   s.part.Size=Vector3.new(radius*.3,.06,math.max(.05,radius*.28*s.w))
   s.part.CFrame=cf*CFrame.lookAt(d*radius*(1-.14*s.w)+Vector3.new(0,0,.6*radius),d*radius*2+Vector3.new(0,0,.6*radius))
   s.part.Transparency=alpha
  end
 end
 local function slash(kind,ownerId,start,direction,reach,speed,width,t0)
  if not K.near(start,170) then return end
  buildMeshes()
  local beam=kind=='Beam'
  local coreColor,glowColor=beam and rgb(255,236,170) or STEEL,beam and rgb(255,170,30) or rgb(255,186,84)
  local radius=width*.5
  local duration=math.max(.12,reach/math.max(speed,1))
  local roll=math.rad((math.random()-.5)*(beam and 10 or 26))
  local core,coreSize=mesh(folder,'SlashCore')
  local glow,glowSize=mesh(folder,'SlashGlow')
  local wake,wakeSize=mesh(folder,'SlashGlow')
  local fallback=not core and crescentParts(coreColor,width)
  if core then core.Color=coreColor end
  if glow then glow.Color=glowColor end
  if wake then wake.Color=beam and GOLD or AMBER end
  -- Tips leave thin wind streaks; the core sheds star sparks.
  local carrier=K.part(folder,'SlashCarrier',Vector3.new(radius*1.9,.1,.4),K.White,1)
  local function tip(x)
   local a0=Instance.new('Attachment');a0.Position=Vector3.new(x,.12,0);a0.Parent=carrier
   local a1=Instance.new('Attachment');a1.Position=Vector3.new(x,-.12,0);a1.Parent=carrier
   local t=Instance.new('Trail');t.Attachment0=a0;t.Attachment1=a1;t.Lifetime=beam and .26 or .18;t.MinLength=.05;t.FaceCamera=true
   t.LightEmission=1;t.LightInfluence=0;t.Color=ColorSequence.new(K.White,glowColor);t.Transparency=seq(0,.1,.6,.6,1,1);t.WidthScale=seq(0,1,1,0);t.Parent=carrier
  end
  tip(-radius*.95);tip(radius*.95)
  local sparks=emitter(carrier,{name='SlashSparks',texture=TEX.Star,color=K.White,color2=glowColor,size=seq(0,.32,1,0),alpha=seq(0,0,.7,.3,1,1),
   life=.25,life1=.45,speed=1,speed1=4,spread=50,rate=beam and 60 or 45,direction=Enum.NormalId.Back,light=1,shape=Enum.ParticleEmitterShape.Box,enabled=true})
  local light
  if beam or radius>2.2 then
   light=Instance.new('PointLight');light.Color=beam and GOLD or HOT;light.Range=beam and 13 or 8;light.Brightness=beam and 3.2 or 1.6;light.Shadows=false;light.Parent=carrier
  end
  if beam then
   emitter(carrier,{name='HolyMotes',texture=TEX.Glow,color=HOT,color2=GOLD,size=seq(0,.5,1,0),alpha=seq(0,.2,1,1),life=.5,life1=.8,speed=.5,speed1=2,
    spread=180,rate=26,accel=Vector3.yAxis*5,light=1,shape=Enum.ParticleEmitterShape.Box,enabled=true})
  end
  -- A thin slice line scorched into the ground behind it.
  local y=groundY(start)+.06
  local scar=K.part(folder,'SlashScar',Vector3.new(beam and .32 or .2,.04,.1),beam and GOLD or HOT,1,Enum.Material.Neon)
  K.flash(folder,start,beam and GOLD or HOT,beam and 14 or 9,beam and 4 or 2.5,.25)
  burst(folder,start,{texture=TEX.Slash,color=K.White,color2=glowColor,size=seq(0,radius*.9,.4,radius*1.6,1,radius*1.8),alpha=seq(0,0,.6,.3,1,1),
   life=.14,speed=0,spread=0,light=1,spin=0,facing=Vector3.yAxis:Cross(direction).Unit},1)
  local seen,limit={},{n=10}
  local last=start
  local hold=.22 -- the scar lingers after the slash ends
  K.animate(duration+hold,function(_,age)
   local f=math.min(1,age/duration)
   local position=start+direction*(reach*f)
   local grow=.55+.45*smooth(f/.18)
   local fade=smooth((f-.72)/.28)+(age>duration and 1 or 0)
   local cf=CFrame.lookAt(position,position+direction)*CFrame.Angles(0,0,roll)
   carrier.CFrame=cf
   if core then core.Size=coreSize*radius*grow;core.CFrame=cf;core.Transparency=math.clamp(fade,0,1) end
   if glow then glow.Size=glowSize*radius*grow*1.04;glow.CFrame=cf*CFrame.new(0,-.02,.12*radius);glow.Transparency=.12+.88*math.clamp(fade,0,1) end
   if wake then wake.Size=wakeSize*radius*grow*Vector3.new(1.25,1,1.6);wake.CFrame=cf*CFrame.new(0,-.04,.5*radius);wake.Transparency=.62+.38*math.clamp(fade,0,1) end
   if fallback then placeCrescent(fallback,cf,radius*grow,math.clamp(fade,0,1)) end
   if light then light.Brightness=(beam and 3.2 or 1.6)*(1-math.clamp(fade,0,1)) end
   sparks.Enabled=age<duration
   local length=(position-start).Magnitude
   scar.Size=Vector3.new(scar.Size.X,.04,math.max(.1,length))
   scar.CFrame=CFrame.lookAt(Vector3.new((start.X+position.X)/2,y,(start.Z+position.Z)/2),Vector3.new(position.X,y,position.Z))
   scar.Transparency=age<duration and .25 or .25+.75*smooth((age-duration)/hold)
   if age<duration then
    passing(last,position,radius,seen,limit,function(p) cutFlash(p,direction,glowColor) end)
    last=position
   end
  end,function()
   if K.near(start+direction*reach,150) then
    local endAt=start+direction*reach
    K.shards(folder,endAt,glowColor,6,10,.35,.14)
    burst(folder,endAt,{texture=TEX.Star,color=K.White,color2=glowColor,size=seq(0,.7,1,0),alpha=seq(0,0,1,1),life=.3,speed=5,speed1=9,spread=180,light=1},8)
   end
   for _,p in {core,glow,wake,carrier,scar} do if p then p:Destroy() end end
   if fallback then for _,s in fallback.parts do s.part:Destroy() end end
  end,'legendSlash',14)
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
  local function over() local head=owner and owner.Character and owner.Character:FindFirstChild('Head');return head and head.Position+Vector3.yAxis*3.2 or origin+Vector3.yAxis*4 end
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
  buildMeshes()
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
  -- The dust ring and the amber rim.
  local ring,size=mesh(folder,'ShockRing')
  if ring then
   ring.Color=rgb(255,246,226)
   K.animate(.5,function(t)
    local e=1-(1-t)^3;local r=.4+(radius-.4)*e
    ring.Size=Vector3.new(size.X*r/1.17,size.Y*(1.6-1.1*e),size.Z*r/1.17)
    ring.CFrame=CFrame.new(Vector3.new(ground.X,y+size.Y*(1.6-1.1*e)*.5,ground.Z))
    ring.Transparency=.15+.85*smooth((t-.35)/.65)
   end,function() ring:Destroy() end,'legendRing',8)
  end
  K.ring(folder,CFrame.new(Vector3.new(ground.X,y+.15,ground.Z)),{segments=24,radius0=.6,radius1=radius,width=.8,rim=AMBER,color=rgb(255,226,170),duration=.45,bodyAlpha=.5})
  for i=1,8 do
   local a=i/8*math.pi*2
   task.delay(.04*i/2,function() if folder.Parent then K.cloud(folder,ground+Vector3.new(math.cos(a),0,math.sin(a))*radius*.55+Vector3.yAxis*.5,DUST,1.6,.8,Vector3.yAxis*1.2,.35) end end)
  end
  K.shards(folder,ground+Vector3.yAxis,rgb(250,248,242),10,14,.6,.18,Enum.Material.SmoothPlastic,.8)
  kick(ownerId,.8,.28)
 end

 -- Shockwave (Wrecking Ball) -----------------------------------------------------------------------
 local function shock(ownerId,ground,radius,duration)
  if not K.near(ground,170) then return end
  buildMeshes()
  local y=ground.Y
  local ring,size=mesh(folder,'ShockRing')
  if ring then
   ring.Color=rgb(236,224,204)
   K.animate(duration+.25,function(_,age)
    local t=math.min(1,age/duration);local e=1-(1-t)^2.5;local r=.5+(radius-.5)*e
    local h=1.9-1.3*e
    ring.Size=Vector3.new(size.X*r/1.17,size.Y*h,size.Z*r/1.17)
    ring.CFrame=CFrame.new(Vector3.new(ground.X,y+size.Y*h*.5,ground.Z))
    ring.Transparency=.1+.9*smooth((age-duration*.55)/(duration*.45+.25))
   end,function() ring:Destroy() end,'legendRing',8)
  end
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
  buildMeshes()
  local y=ground.Y
  local wait=math.max(0,strikeAt-workspace:GetServerTimeNow())
  -- A crackling target ring closes in where the bolt will fall.
  decal(folder,Vector3.new(ground.X,y+.05,ground.Z),TEX.Ring,SKY,radius*2.1,math.max(.05,wait*.6),wait*.4+.05,.25,3)
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
   local ring,size=mesh(folder,'ShockRing')
   if ring then
    ring.Color=SKY;ring.Material=Enum.Material.Neon
    K.animate(.4,function(t)
     local e=1-(1-t)^3;local r=.5+(radius-.5)*e
     ring.Size=Vector3.new(size.X*r/1.17,size.Y*(1.1-.7*e),size.Z*r/1.17)
     ring.CFrame=CFrame.new(Vector3.new(ground.X,y+size.Y*(1.1-.7*e)*.5,ground.Z))
     ring.Transparency=.2+.8*smooth((t-.3)/.7)
    end,function() ring:Destroy() end,'legendRing',8)
   end
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

 combat:WaitForChild('LegendaryFX').OnClientEvent:Connect(function(kind,...)
  local a={...}
  if kind=='Slash' or kind=='Beam' then slash(kind,a[2],a[4],a[5],a[6],a[7],a[8],a[9])
  elseif kind=='Flush' then flush(a[1],a[3],a[4],a[5],a[6])
  elseif kind=='Split' then split(a[1],a[3],a[4],a[5],a[6],a[7],a[8],a[9])
  elseif kind=='Strike' then strike(a[1],a[2],a[3],a[4])
  elseif kind=='Shock' then shock(a[1],a[2],a[3],a[4])
  elseif kind=='Thunder' then thunder(a[1],a[2],a[3],a[4]) end
 end)
 return api
end
return V
