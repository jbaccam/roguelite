-- Client only: the round 10 events' world presentation. Everything here is drawn from replicated
-- server state (attributes on the enemies, the vents, Round10FX events) and never decides a hit:
-- every warning is the exact shape the server tests (ExploderService disc, vent disc, rush lane).
--   Bloaters  armed (FuseUntil): the burst disc on the ground filling to the edge at the burst, a
--             small fuse ring over the head (a 26 px charcoal badge, an orange ring draining with the
--             fuse, a pulsing '!'; its health bar hides while armed), and the belly swelling
--             (UpperTorso and its joints, locally). Burst: a flat cartoon pop. 2026-10-10: the old
--             170x40 ABOUT TO BURST panel was too large and overlapped the health bar ("the pop
--             above a popping zombie is too large and too overlapping"), so it became this ring.
--   Vents     no text tags (2026-10-10 user: the CHARGING / ERUPTING / COOLING labels were "way too
--             large and ugly"). The vent says it: seams dim at rest; CHARGING pulses orange ever
--             faster with a flashing light while its blast disc and splash discs fill; ERUPTING
--             flashes white-yellow (plume, debris, splash pops); COOLING sinks to dark red with
--             steam. MOVING: smoke at the old spot and a dim disc where it will rise next.
--   Rushes    the DJ's Beat Command: each rusher's lane, filling until it goes.
--   Howl      the alpha's howl ring at its radius; empowered wolves glow red until it runs out.
--   Tombs     before each skeleton burst (BurstAt) the coffin glows amber and quickens, sand trickles
--             from its mouth, then the mouth blasts sand as they pour out (stronger with each burst);
--             an extra Warden's sand burst; a destroyed coffin's sand burst and stone chunks.
-- Effects use the game's flat language (boss warnings' Neon fills and edges, painted flipbooks,
-- ground plates) through BossVfx Common, and respect ClientQuality's effect budgets.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local RS=game:GetService('ReplicatedStorage')
local T=require(RS:WaitForChild('UITheme'))
local combat=RS:WaitForChild('RogueliteCombat')
local Common=require(combat:WaitForChild('BossVfx'):WaitForChild('Common'))
local Types=require(combat:WaitForChild('ZombieTypes'))
local K=Common.K
local W={}
local up=Vector3.yAxis
local function smooth(x) x=math.clamp(x,0,1);return x*x*(3-2*x) end
local function flat(v) return Vector3.new(v.X,0,v.Z) end
local folder
local function fxFolder()
 if folder and folder.Parent then return folder end
 folder=Instance.new('Folder');folder.Name='Round10Fx';folder.Parent=workspace;return folder
end
local function slab(parent,name,size,cf,color,transparency,shape)
 local p=Instance.new('Part');p.Name=name;p.Anchored=true;p.CanCollide=false;p.CanQuery=false;p.CanTouch=false;p.CastShadow=false
 p.Material=Enum.Material.Neon;p.Size=size;p.CFrame=cf;p.Color=color;p.Transparency=transparency;if shape then p.Shape=shape end;p.Parent=parent
 return p
end
local FILL,EDGE,GROW=.78,.2,.42

-- A ground warning disc in the boss warnings' language: faint fill, bright edge and a hotter fill
-- that grows from the centre to the edge exactly at k = 1. :paint(k, left) each frame; :done().
local function disc(center,radius,color)
 local m=Instance.new('Model');m.Name='Round10Warning';m.Parent=fxFolder()
 local y=center.Y+.07
 local function cyl(name,r,t) return slab(m,name,Vector3.new(.045,r*2,r*2),CFrame.new(center.X,y,center.Z)*CFrame.Angles(0,0,math.pi/2),color,t,Enum.PartType.Cylinder) end
 local fill=cyl('Fill',radius,FILL);local grow=cyl('Grow',.05,1);grow.CFrame+=up*.02
 local edges={};local n=40
 for i=1,n do
  local a0,a1=i/n*math.pi*2,(i+1)/n*math.pi*2
  local p0=Vector3.new(center.X+math.cos(a0)*radius,y+.03,center.Z+math.sin(a0)*radius);local p1=Vector3.new(center.X+math.cos(a1)*radius,y+.03,center.Z+math.sin(a1)*radius)
  edges[i]=slab(m,'Edge',Vector3.new(.24,.06,(p1-p0).Magnitude+.1),CFrame.lookAt((p0+p1)/2,p1),color,EDGE)
 end
 local o={model=m}
 function o:paint(k,left,hold)
  k=math.clamp(k,0,1);local e=1-(1-k)^1.6
  grow.Size=Vector3.new(.045,math.max(.05,radius*2*e),math.max(.05,radius*2*e));grow.Transparency=e<.02 and 1 or GROW-.12*k
  fill.Transparency=hold and .6 or FILL-.1*k
  local flicker=left and left<.3 and (.5+.5*math.sin(os.clock()*48)) or 0
  for _,p in edges do p.Transparency=EDGE+(1-EDGE)*flicker*.8 end
 end
 function o:color(c) fill.Color=c;grow.Color=c;for _,p in edges do p.Color=c end end
 function o:fade(a) fill.Transparency=FILL+(1-FILL)*a;grow.Transparency=1;for _,p in edges do p.Transparency=EDGE+(1-EDGE)*a end end
 function o:done() m:Destroy() end
 return o
end
-- A ground lane warning (the DJ's rushers): from origin along dir, length x width, filling along it.
local function lane(origin,dir,length,width,color)
 local m=Instance.new('Model');m.Name='Round10Lane';m.Parent=fxFolder()
 local y=origin.Y-1.5
 local g=workspace:Raycast(origin+up*2,-up*12,(function() local p=RaycastParams.new();p.FilterType=Enum.RaycastFilterType.Exclude;p.FilterDescendantsInstances={fxFolder(),workspace:FindFirstChild('RogueliteEnemies')};return p end)())
 if g then y=g.Position.Y end
 y+=.07
 local o0=Vector3.new(origin.X,y,origin.Z);local mid=o0+dir*length/2
 local fill=slab(m,'Fill',Vector3.new(width,.045,length),CFrame.lookAt(mid,mid+dir),color,FILL)
 local grow=slab(m,'Grow',Vector3.new(width,.05,.05),CFrame.lookAt(o0,o0+dir),color,1)
 local side=Vector3.new(-dir.Z,0,dir.X)*width/2
 for _,s in {side,-side} do local a=o0+s;local b=a+dir*length;slab(m,'Edge',Vector3.new(.24,.06,length),CFrame.lookAt((a+b)/2+up*.03,b+up*.03),color,EDGE) end
 local o={model=m}
 function o:paint(k)
  k=math.clamp(k,0,1);local len=math.max(.05,length*(1-(1-k)^1.6));local c=o0+dir*len/2+up*.02
  grow.Size=Vector3.new(width,.05,len);grow.CFrame=CFrame.lookAt(c,c+dir);grow.Transparency=GROW-.12*k;fill.Transparency=FILL-.1*k
 end
 function o:done() m:Destroy() end
 return o
end
-- A small world tag (BillboardGui) in the theme: text on a panel.
local function tag(host,text,color,offset)
 local g=T.make('BillboardGui',host,{Name='Round10Tag',Size=UDim2.fromOffset(170,40),StudsOffsetWorldSpace=offset or Vector3.new(0,5,0),AlwaysOnTop=true,MaxDistance=140,LightInfluence=0})
 local p=T.panel(g,'Plate',0,0,170,40,'panel')
 local l=T.label(p,'Text',text,8,3,154,34,18,color or T.Color.white);l.TextStrokeTransparency=0
 return g,l,p
end

-- A compact fuse ring (BillboardGui): a charcoal badge, a ring that drains clockwise from 12 o'clock
-- as :set(k) goes 0 -> 1 and a '!' that pulses faster near the burst. Two clipped halves each hold
-- the whole ring; a hard-edged UIGradient on its stroke shows an arc of `Rotation` degrees per half.
local function fuseRing(host,color,offset)
 local S,TH=26,3
 local g=T.make('BillboardGui',host,{Name='Round10Fuse',Size=UDim2.fromOffset(S,S),StudsOffsetWorldSpace=offset,AlwaysOnTop=true,MaxDistance=90,LightInfluence=0})
 local root=T.make('Frame',g,{Name='Badge',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.5),Size=UDim2.fromScale(1,1),BackgroundTransparency=1})
 local scale=T.make('UIScale',root,{})
 local disk=T.make('Frame',root,{Name='Disk',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.5),Size=UDim2.fromOffset(S-2,S-2),BackgroundColor3=T.Color.track,BackgroundTransparency=.1,BorderSizePixel=0})
 T.make('UICorner',disk,{CornerRadius=UDim.new(1,0)})
 T.make('UIStroke',disk,{Color=Color3.fromRGB(8,10,11),Thickness=1,Transparency=.2})
 local halves={}
 for i,side in {0,1} do
  local clip=T.make('Frame',root,{Name='Half'..i,BackgroundTransparency=1,ClipsDescendants=true,Position=UDim2.fromScale(side*.5,0),Size=UDim2.fromScale(.5,1)})
  local ring=T.make('Frame',clip,{Name='Ring',BackgroundTransparency=1,Position=UDim2.new(-side,TH+1,0,TH+1),Size=UDim2.new(2,-(TH+1)*2,1,-(TH+1)*2)})
  T.make('UICorner',ring,{CornerRadius=UDim.new(1,0)})
  local st=T.make('UIStroke',ring,{Color=color,Thickness=TH})
  halves[side]=T.make('UIGradient',st,{Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,0),NumberSequenceKeypoint.new(.499,0),NumberSequenceKeypoint.new(.5,1),NumberSequenceKeypoint.new(1,1)})})
 end
 local mark=T.label(root,'Mark','!',0,1,S,S-2,16,T.Color.gold);mark.TextScaled=false;mark.TextStrokeTransparency=.4
 local o={gui=g}
 function o:set(k,now)
  local a=math.clamp(1-k,0,1)*360
  halves[1].Rotation=math.clamp(a,0,180);halves[0].Rotation=180+math.clamp(a-180,0,180)
  scale.Scale=1+.12*k*math.max(0,math.sin(now*(8+16*k)))
 end
 o:set(0,0)
 return o
end

-- ── Bloaters ────────────────────────────────────────────────────────────────────────────────────
local Blast=Types.Blast
local bloaters={}
local ARM_COLOR=Color3.fromRGB(255,150,40)
local function scaleRig(npc)
 -- The belly (UpperTorso) and its joints, so arms and head ride out with the swell.
 local torso=npc:FindFirstChild('UpperTorso');local head=npc:FindFirstChild('Head')
 if not torso then return nil end
 local joints={}
 for _,m in npc:GetDescendants() do
  if m:IsA('Motor6D') then
   if m.Part0==torso then table.insert(joints,{m=m,key='C0',base=m.C0}) end
   if m.Part1==torso then table.insert(joints,{m=m,key='C1',base=m.C1}) end
  end
 end
 local base,headBase=torso.Size,head and head.Size
 return function(s)
  if not torso.Parent then return end
  torso.Size=base*s;if head then head.Size=headBase*(1+(s-1)*.25) end
  for _,j in joints do local c=j.base;j.m[j.key]=CFrame.new(c.Position*s)*c.Rotation end
 end
end
local function trackBloater(npc)
 if bloaters[npc] then return end
 local B={npc=npc};bloaters[npc]=B
 local tint={}
 for _,p in npc:GetDescendants() do if p:IsA('BasePart') and p.Name~='HumanoidRootPart' then tint[p]=p.Color end end
 function B.step(now)
  local fuse=npc:GetAttribute('FuseUntil');local center=npc:GetAttribute('FuseCenter')
  if type(fuse)~='number' or typeof(center)~='Vector3' or npc:GetAttribute('Detonated') then return end
  local armed=npc:GetAttribute('EnemyAttackStart') or fuse-Blast.fuse
  local span=math.max(.2,fuse-armed);local k=math.clamp((now-armed)/span,0,1)
  if not B.warn then
   local radius=Blast.radius*(npc:GetScale()/(npc:GetAttribute('EnemyBaselineModelScale') or 1))
   local g=workspace:Raycast(center+up,-up*10,(function() local p=RaycastParams.new();p.FilterType=Enum.RaycastFilterType.Exclude;p.FilterDescendantsInstances={workspace:FindFirstChild('RogueliteEnemies'),fxFolder()};return p end)())
   B.warn=disc(Vector3.new(center.X,g and g.Position.Y or center.Y-3,center.Z),radius,ARM_COLOR)
   local root=npc:FindFirstChild('HumanoidRootPart')
   if root then B.ring=fuseRing(root,ARM_COLOR,Vector3.new(0,npc:GetExtentsSize().Y*.5+1.2,0));B.tag=B.ring.gui end
   B.scale=scaleRig(npc)
   Common.cue('dragon_inhale',center,.45,1.9)
  end
  B.warn:paint(k,fuse-now)
  if B.ring then B.ring:set(k,now) end
  -- Swell (up to Blast.inflate) with a quickening pulse; the body warms to amber.
  local pulse=math.sin(now*(10+18*k))*.035*k
  if B.scale then B.scale(1+(Blast.inflate-1)*smooth(k)+pulse) end
  local warm=smooth(k)*(.55+.45*math.abs(math.sin(now*(6+14*k))))
  for p,c in tint do if p.Parent then p.Color=c:Lerp(Color3.fromRGB(255,200,90),warm*.6) end end
 end
 function B.done()
  if B.warn then B.warn:done();B.warn=nil end
  if B.tag then B.tag:Destroy();B.tag=nil end
  bloaters[npc]=nil
 end
end
-- The burst (Round10FX 'Blast'): a flat cartoon pop where the server's disc was.
-- Round10Intro's harmless intro Bloater (2026-10-10) gets the real armed warning, swell and tint: it
-- sets FuseUntil, FuseCenter and EnemyAttackStart on its local prop and Detonated at the pop.
W.previewBloater=trackBloater
function W.blast(center,radius)
 if not Common.near(center,40) then return end
 local g=workspace:Raycast(center+up,-up*10,(function() local p=RaycastParams.new();p.FilterType=Enum.RaycastFilterType.Exclude;p.FilterDescendantsInstances={workspace:FindFirstChild('RogueliteEnemies'),fxFolder()};return p end)())
 local floor=g and g.Position or center-up*3
 Common.ring(floor+up*.08,'ShockwaveRing',2,radius*2.3,.45,Color3.fromRGB(255,214,90),.1,1.6)
 Common.stain(floor+up*.05,'ScorchMark',radius*1.4,Color3.fromRGB(150,120,40),.05,.8,.8,.35)
 Common.star(center+up*1.5,Color3.fromRGB(255,236,120),radius*1.6,.22)
 Common.emit(center,up,'DustPuff',{emit=18,Speed={10,22},SpreadAngle=180,Drag=4,Lifetime={.5,.9},Size=Common.ns({0,2},{1,5}),Color=Color3.fromRGB(226,206,70),Transparency=Common.ns({0,.1},{.6,.35},{1,1}),LightInfluence=.6,Rotation={0,360},RotSpeed={-60,60}})
 Common.emit(center+up,up,'SmokePuff',{emit=8,Speed={4,9},SpreadAngle=70,Drag=2,Lifetime={.9,1.4},Size=Common.ns({0,3},{1,7}),Color=Color3.fromRGB(120,112,60),Transparency=Common.ns({0,.35},{1,1}),Rotation={0,360}})
 Common.chunks(center+up,floor.Y,{'Round10NoMesh'},{count=7,speed={10,18},up={10,18},scale={.5,.9},life=1.1,fallback={Color3.fromRGB(214,184,46),Enum.Material.SmoothPlastic}})
 Common.light(center+up*2,Color3.fromRGB(255,210,90),radius*2.5,4,.5)
 Common.shake(center,.55,.35)
 Common.cue('hammer_boom',center,.65,1.45)
end

-- ── Vents ───────────────────────────────────────────────────────────────────────────────────────
-- 2026-10-10: no text tags; the vent's seams (Neon), a light on it and its ground discs carry the
-- state. Discs: the blast (Radius) and the splashes (Splash1..n, SplashRadius), the server's exact
-- hit shapes. Moving: a dim disc at MoveTo; the vent pops up there (Center) in smoke.
local vents={}
local VENT_DIM=Color3.fromRGB(96,30,18)
local VENT_WARN=Color3.fromRGB(255,128,32)
local VENT_FLASH=Color3.fromRGB(255,246,205)
local VENT_HOT=Color3.fromRGB(255,190,70)
local VENT_COOL=Color3.fromRGB(150,30,18)
local DISC_WARN=Color3.fromRGB(255,120,36)
local DISC_HOT=Color3.fromRGB(255,72,36)
local DISC_MOVE=Color3.fromRGB(150,70,40)
local function trackVent(v)
 if vents[v] then return end
 local V={model=v,glows={},splash={}};vents[v]=V
 for _,p in v:GetDescendants() do if p:IsA('BasePart') and p.Name:find('Glow') then p.Material=Enum.Material.Neon;table.insert(V.glows,{part=p}) end end
 V.center=v:GetAttribute('Center') or v:GetPivot().Position
 V.radius=v:GetAttribute('Radius') or 12
 V.host=Common.part('Round10Vent',Vector3.one*.05,CFrame.new(V.center+up*.5),K.White,1)
 V.light=Instance.new('PointLight');V.light.Shadows=false;V.light.Brightness=0;V.light.Range=V.radius;V.light.Color=VENT_WARN;V.light.Parent=V.host
 local function clearDiscs()
  if V.warn then V.warn:done();V.warn=nil end
  for _,d in V.splash do d:done() end;table.clear(V.splash)
 end
 local function splashPoints()
  local list={};local i=1
  while typeof(v:GetAttribute('Splash'..i))=='Vector3' do table.insert(list,v:GetAttribute('Splash'..i));i+=1 end
  return list
 end
 local function drawDiscs(color)
  clearDiscs()
  V.warn=disc(V.center,V.radius,color)
  local r=v:GetAttribute('SplashRadius') or 0
  if r>0 then for _,p in splashPoints() do table.insert(V.splash,disc(p,r,color)) end end
 end
 local function eachDisc(fn) if V.warn then fn(V.warn) end;for _,d in V.splash do fn(d) end end
 local function setState()
  local state=v:GetAttribute('State');local untilAt=v:GetAttribute('StateUntil')
  if V.plume then for _,e in V.plume do e.Enabled=false;task.delay(2,function() e:Destroy() end) end;V.plume=nil end
  if V.moveDisc and state~='Moving' then V.moveDisc:done();V.moveDisc=nil end
  V.state,V.untilAt,V.from=state,untilAt,workspace:GetServerTimeNow()
  local center=V.center
  if state=='Charging' then
   drawDiscs(DISC_WARN)
   Common.cue('stone_rumble',center,.5,.8)
  elseif state=='Erupting' then
   if not V.warn then drawDiscs(DISC_HOT) end
   eachDisc(function(d) d:color(DISC_HOT) end)
   local host=V.host
   V.plume={
    Common.fx(host,'Flame',{Rate=40,Speed={34,50},SpreadAngle=12,Lifetime={.6,1},Size=Common.ns({0,3},{1,6.5}),Color=Color3.fromRGB(255,160,60),Transparency=Common.ns({0,.05},{.7,.35},{1,1}),LightEmission=.6,Drag=1.4,Rotation={0,360},EmissionDirection=Enum.NormalId.Top}),
    Common.fx(host,'SmokePuff',{Rate=8,Speed={14,24},SpreadAngle=16,Lifetime={1.2,1.8},Size=Common.ns({0,3},{1,8}),Color=Color3.fromRGB(64,52,54),Transparency=Common.ns({0,.25},{1,1}),Drag=1.1,Rotation={0,360},EmissionDirection=Enum.NormalId.Top}),
    Common.fx(host,'Ember',{Rate=30,Speed={18,34},SpreadAngle=32,Lifetime={.8,1.4},Size=Common.ns({0,.45},{1,.1}),Color=Color3.fromRGB(255,190,90),LightEmission=1,Acceleration=Vector3.new(0,-30,0),EmissionDirection=Enum.NormalId.Top}),
   }
   Common.cue('lava_hiss',center,.75,1);Common.shake(center,.3,.4)
   -- The eruption's flash: a white-yellow pop of light and a flat shock ring out to the blast edge.
   Common.light(center+up*4,VENT_FLASH,V.radius*2.6,5,.35)
   Common.ring(center+up*.1,'ShockwaveRing',2,V.radius*2,.45,Color3.fromRGB(255,200,90),.15,1.6)
   -- Each splash: a lava pop and a scorch where its disc is.
   local r=v:GetAttribute('SplashRadius') or 0
   for _,p in splashPoints() do
    Common.emit(p+up*.4,up,'Flame',{emit=12,Speed={12,22},SpreadAngle=30,Lifetime={.5,.9},Size=Common.ns({0,2},{1,4.5}),Color=Color3.fromRGB(255,160,60),Transparency=Common.ns({0,.05},{.7,.35},{1,1}),LightEmission=.6,Drag=2,Rotation={0,360}})
    Common.stain(p+up*.06,'ScorchMark',r*1.7,Color3.fromRGB(120,40,20),.08,(untilAt or 2)-workspace:GetServerTimeNow(),.6,.35)
    Common.light(p+up*2,VENT_HOT,r*2.2,2.5,.4)
   end
   -- Small cosmetic debris (never collides, never hurts): the kit's fragments when installed.
   local names={};local assets=combat:FindFirstChild('Round10Assets');local debris=assets and assets:FindFirstChild('VolcanicDebris')
   if debris then for _,c in debris:GetChildren() do if c:IsA('BasePart') then table.insert(names,c) end end end
   if #names>0 then
    for i=1,5 do
     local src=names[(i%#names)+1]:Clone();src.Anchored=true;src.CanCollide=false;src.CanQuery=false;src.CanTouch=false;src.Parent=fxFolder()
     local a=math.random()*math.pi*2;local vel=Vector3.new(math.cos(a)*math.random(4,9),math.random(24,34),math.sin(a)*math.random(4,9));local pos=center+up;local rot=CFrame.Angles(math.random()*6,math.random()*6,0)
     K.animate(1.4,function(t,age) local p=pos+vel*age-up*35*age*age;if p.Y<center.Y then p=Vector3.new(p.X,center.Y,p.Z) end;src.CFrame=CFrame.new(p)*rot*CFrame.Angles(age*7,age*5,0);src.Transparency=smooth((t-.75)/.25) end,function() src:Destroy() end,'r10Debris',30)
    end
   else Common.chunks(center+up,center.Y,{'Round10NoMesh'},{count=5,speed={4,9},up={22,30},scale={.35,.6},life=1.3,fallback={Color3.fromRGB(58,46,50),Enum.Material.SmoothPlastic}}) end
  elseif state=='Cooling' then
   Common.emit(center+up*.6,up,'SmokePuff',{emit=10,Speed={4,8},SpreadAngle=30,Lifetime={1.2,1.8},Size=Common.ns({0,2},{1,6}),Color=Color3.fromRGB(220,220,220),Transparency=Common.ns({0,.4},{1,1}),Drag=1,Rotation={0,360}})
  elseif state=='Moving' then
   clearDiscs()
   Common.emit(center+up*.6,up,'SmokePuff',{emit=14,Speed={5,10},SpreadAngle=35,Lifetime={1.2,1.8},Size=Common.ns({0,2.5},{1,7}),Color=Color3.fromRGB(70,58,58),Transparency=Common.ns({0,.25},{1,1}),Drag=1,Rotation={0,360}})
   Common.cue('stone_rumble',center,.55,.7)
   local to=v:GetAttribute('MoveTo');if typeof(to)=='Vector3' then V.moveDisc=disc(to,V.radius,DISC_MOVE) end
  else
   clearDiscs()
  end
 end
 v:GetAttributeChangedSignal('State'):Connect(setState)
 -- A splash list or move target that lands after its state still draws (redrawn next frame).
 v.AttributeChanged:Connect(function(name)
  if name:match('^Splash%d') and V.state=='Charging' then V.dirty=true end
  if name=='MoveTo' and V.state=='Moving' and not V.moveDisc and typeof(v:GetAttribute('MoveTo'))=='Vector3' then V.moveDisc=disc(v:GetAttribute('MoveTo'),V.radius,DISC_MOVE) end
 end)
 -- Arrived at a new spot: the light and plume follow; it rises in smoke and dust.
 v:GetAttributeChangedSignal('Center'):Connect(function()
  local c=v:GetAttribute('Center');if typeof(c)~='Vector3' then return end
  V.center=c;V.host.CFrame=CFrame.new(c+up*.5)
  Common.emit(c+up*.5,up,'SmokePuff',{emit=12,Speed={6,12},SpreadAngle=40,Lifetime={1,1.6},Size=Common.ns({0,2.5},{1,6}),Color=Color3.fromRGB(70,58,58),Transparency=Common.ns({0,.25},{1,1}),Drag=1.2,Rotation={0,360}})
  Common.dustRing(c,2.5,10,Color3.fromRGB(90,74,70),14,3);Common.cue('stone_rumble',c,.6,1.1);Common.shake(c,.2,.3)
 end)
 setState()
 function V.step(now)
  if not v.Parent then return end
  local s,untilAt=V.state,V.untilAt or now
  local span=math.max(.1,untilAt-V.from);local k=math.clamp((now-V.from)/span,0,1);local age=now-V.from
  if V.dirty then V.dirty=false;if s=='Charging' then drawDiscs(DISC_WARN) end end
  local color,bright,lc,range
  if s=='Charging' then
   -- Pulses quicken from 1.5 to 6 a second and brighten toward the eruption; the light flashes with them.
   local beat=.5+.5*math.sin(now*math.pi*2*(1.5+4.5*k))
   color=VENT_DIM:Lerp(VENT_WARN,(.3+.7*k)*(.4+.6*beat));bright=(.6+3.4*k)*beat;lc=VENT_WARN;range=V.radius*1.3
  elseif s=='Erupting' then
   local flash=math.clamp(1-age/.3,0,1);local flick=.85+.15*math.sin(now*40)
   color=VENT_HOT:Lerp(VENT_FLASH,flash);bright=(3.5+4*flash)*flick;lc=VENT_HOT:Lerp(VENT_FLASH,flash);range=V.radius*(1.8+.6*flash)
  elseif s=='Cooling' then color=VENT_COOL:Lerp(VENT_DIM,k);bright=1.6*(1-k);lc=VENT_COOL;range=V.radius
  elseif s=='Moving' then color=VENT_DIM:Lerp(VENT_COOL,.5+.5*math.sin(now*8));bright=.5;lc=VENT_COOL;range=V.radius*.8
   if V.moveDisc then V.moveDisc:paint(k*.7) end
  end
  -- At rest the seams go dim once (and the intro's own glow sweep may run over them).
  if color then V.idle=false;for _,g in V.glows do if g.part.Parent then g.part.Color=color end end
  elseif not V.idle then V.idle=true;bright=0;for _,g in V.glows do if g.part.Parent then g.part.Color=VENT_DIM end end end
  if bright then V.light.Brightness=bright end;if lc then V.light.Color=lc end;if range then V.light.Range=range end
  if s=='Charging' then eachDisc(function(d) d:paint(k,untilAt-now) end)
  elseif s=='Erupting' then eachDisc(function(d) d:paint(1,nil,true) end)
  elseif s=='Cooling' then eachDisc(function(d) d:fade(k) end) end
 end
 function V.done()
  clearDiscs();if V.moveDisc then V.moveDisc:done() end;if V.host then V.host:Destroy() end
  vents[v]=nil
 end
end

-- ── Tombs: the burst warning (2026-10-10) ───────────────────────────────────────────────────────
-- BurstAt (Round10Service): the coffin's amber glow pulses faster for the warning, sand trickles from
-- its mouth, then the mouth blasts sand as skeletons pour out. Each burst is a little stronger
-- (BurstCount), as the server's are bigger. Flat pieces only: a Highlight tint, flipbooks, a light.
local tombs={}
local TOMB_GLOW=Color3.fromRGB(255,176,64)
local SAND=Color3.fromRGB(226,200,160)
local function trackTomb(m)
 if tombs[m] then return end
 local B={model=m,half=m:GetExtentsSize().Y/2};tombs[m]=B
 local function frames()
  local root=m:FindFirstChild('HumanoidRootPart');local p=root and root.CFrame or m:GetPivot()
  return p*CFrame.new(0,-math.min(B.half,6.75)+3.4,-3.4),p*CFrame.new(0,-math.min(B.half,6.75),-4.6),p
 end
 local function onBurst()
  local at=m:GetAttribute('BurstAt');if type(at)~='number' then return end
  B.at,B.from,B.count,B.fired,B.fadeFrom=at,workspace:GetServerTimeNow(),m:GetAttribute('BurstCount') or 1,false,nil
  if not B.hl then
   local h=Instance.new('Highlight');h.Name='Round10TombPulse';h.FillColor=TOMB_GLOW;h.OutlineColor=Color3.fromRGB(255,222,140);h.FillTransparency=1;h.OutlineTransparency=1
   h.DepthMode=Enum.HighlightDepthMode.Occluded;h.Adornee=m;h.Parent=m;B.hl=h
  end
  local mouth=frames()
  Common.emit(mouth.Position,up,'DustPuff',{emit=6,Speed={2,5},SpreadAngle=50,Lifetime={.6,1},Size=Common.ns({0,1},{1,2.5}),Color=SAND,Transparency=Common.ns({0,.3},{1,1}),LightInfluence=.8,Rotation={0,360}})
  Common.cue('stone_rumble',mouth.Position,.3+.05*math.min(B.count,6),1.25)
 end
 m:GetAttributeChangedSignal('BurstAt'):Connect(onBurst)
 function B.step(now)
  if not B.at then return end
  local power=math.min(1,.55+.08*B.count)
  if not B.fired and now<B.at then
   local k=math.clamp((now-B.from)/math.max(.1,B.at-B.from),0,1)
   local beat=.5+.5*math.sin(now*math.pi*2*(2+6*k))
   if B.hl then B.hl.FillTransparency=1-(.2+.45*k)*power*beat;B.hl.OutlineTransparency=1-(.35+.6*k)*power end
  elseif not B.fired then
   B.fired,B.fadeFrom=true,now
   local mouth,floor,p=frames()
   Common.emit(mouth.Position,(p.LookVector+up*.35).Unit,'SandBurst',{emit=8+2*math.min(B.count,6),Speed={10,18},SpreadAngle=35,Lifetime={.6,1},Size=Common.ns({0,2},{1,5}),Color=Color3.fromRGB(226,196,150),Transparency=Common.ns({0,.1},{1,1}),Drag=2.4,LightInfluence=.8,Rotation={0,360}})
   Common.dustRing(floor.Position,1.5,8,SAND,12,3)
   Common.light(mouth.Position,TOMB_GLOW,16,3*power,.35)
   Common.shake(mouth.Position,.25*power,.3);Common.cue('sand_burst',mouth.Position,.5,1.1)
  end
  if B.fired and B.hl then
   local f=math.clamp((now-B.fadeFrom)/.5,0,1)
   B.hl.FillTransparency=1-.6*power*(1-f);B.hl.OutlineTransparency=1-.9*power*(1-f)
   if f>=1 then B.at=nil end
  end
 end
 function B.done() if B.hl then B.hl:Destroy() end;tombs[m]=nil end
 onBurst()
end
-- An extra Tomb Warden's arrival (Round10FX 'TombWardenBurst'): the sand bursts where he appears.
function W.wardenBurst(position,look)
 look=typeof(look)=='Vector3' and look or up
 Common.emit(position+up*1.5,up,'SandBurst',{emit=22,Speed={12,24},SpreadAngle=60,Lifetime={.8,1.3},Size=Common.ns({0,3},{1,8}),Color=Color3.fromRGB(226,196,150),Transparency=Common.ns({0,.1},{1,1}),Drag=2.2,LightInfluence=.8,Rotation={0,360}})
 Common.dustRing(position,3,14,SAND,18,4)
 Common.light(position+up*3,TOMB_GLOW,24,3.5,.5)
 Common.shake(position,.6,.45);Common.cue('sand_burst',position,.9,.85);Common.cue('stone_rumble',position,.7,.9)
end

-- ── Rushes, howl, empowered wolves ──────────────────────────────────────────────────────────────
local rushes={}
local RUSH=Color3.fromRGB(255,90,140)
local function stepRush(npc,now)
 local at=npc:GetAttribute('RushAt');local R=rushes[npc]
 if type(at)~='number' or not npc:GetAttribute('EventControlled') then if R then R.lane:done();rushes[npc]=nil end;return end
 if not R or R.at~=at then
  if R then R.lane:done() end
  local from,dir=npc:GetAttribute('RushFrom'),npc:GetAttribute('RushDir')
  if typeof(from)~='Vector3' or typeof(dir)~='Vector3' then return end
  local length=npc:GetAttribute('RushLength') or 30
  R={at=at,born=now,from=from,dir=dir,length=length,lane=lane(from,dir,length,npc:GetAttribute('RushWidth') or 4.5,RUSH)}
  rushes[npc]=R
  Common.cue('crab_scuttle',from,.35,1.2)
 end
 R.lane:paint((now-R.born)/math.max(.1,R.at-R.born))
 -- The dash itself (2026-10-10, it stuttered at the server's 10 Hz steps): drawn on the server's
 -- timeline every frame. The root is anchored for the rush, so this local placement wins each frame
 -- over the server's late copies; Round10Service moveRushes keeps the server body on the same line.
 local speed=npc:GetAttribute('RushSpeed');local root=npc:FindFirstChild('HumanoidRootPart')
 if type(speed)=='number' and root and root.Anchored and now>=at then
  local p=R.from+R.dir*math.min(R.length,(now-at)*speed);root.CFrame=CFrame.lookAt(p,p+R.dir)
 end
end
local glowing={}
local function stepWolf(npc,now)
 local untilAt=npc:GetAttribute('PackEmpoweredUntil');local on=type(untilAt)=='number' and untilAt>now
 local h=glowing[npc]
 if on and not h then
  h=Instance.new('Highlight');h.Name='Round10Empowered';h.FillColor=Color3.fromRGB(255,40,40);h.OutlineColor=Color3.fromRGB(255,90,70);h.FillTransparency=.82;h.OutlineTransparency=.1
  h.DepthMode=Enum.HighlightDepthMode.Occluded;h.Adornee=npc;h.Parent=npc;glowing[npc]=h
 elseif not on and h then h:Destroy();glowing[npc]=nil end
end
function W.howl(position,radius)
 local g=workspace:Raycast(position+up,-up*14,(function() local p=RaycastParams.new();p.FilterType=Enum.RaycastFilterType.Exclude;p.FilterDescendantsInstances={workspace:FindFirstChild('RogueliteEnemies'),fxFolder()};return p end)())
 local floor=g and g.Position or position-up*4
 Common.ring(floor+up*.08,'ShockwaveRing',4,radius*2,.9,Color3.fromRGB(255,70,70),.25,1.4)
 -- The buff's reach, held a moment so it can be read: an edge ring at exactly `radius`.
 local d=disc(floor,radius,Color3.fromRGB(255,60,60))
 K.animate(1.2,function(t) d:fade(smooth(t)) end,function() d:done() end,'r10Howl',4)
 Common.light(position+up*3,Color3.fromRGB(255,60,60),radius,2.5,.8)
end
function W.tombBroken(position)
 Common.emit(position+up*1.5,up,'SandBurst',{emit=16,Speed={10,20},SpreadAngle=70,Lifetime={.8,1.3},Size=Common.ns({0,3},{1,7}),Color=Color3.fromRGB(226,196,150),Transparency=Common.ns({0,.1},{1,1}),Drag=2.2,LightInfluence=.8,Rotation={0,360}})
 Common.dustRing(position,3,12,Color3.fromRGB(226,200,160),16,3.5)
 Common.chunks(position+up*3,position.Y,{'Round10NoMesh'},{count=6,speed={8,14},up={10,16},scale={.8,1.4},life=1.4,fallback={Color3.fromRGB(214,170,120),Enum.Material.SmoothPlastic}})
 Common.shake(position,.6,.4);Common.cue('sand_burst',position,.9,.9);Common.cue('stone_rumble',position,.6,1.1)
end

-- ── Wiring ──────────────────────────────────────────────────────────────────────────────────────
local enemies
local function considerEnemy(npc)
 if npc:GetAttribute('Exploder') then trackBloater(npc) end
 if npc:GetAttribute('EventObjective')=='Tomb' then trackTomb(npc) end
end
function W.start()
 enemies=workspace:WaitForChild('RogueliteEnemies',30)
 if enemies then
  enemies.ChildAdded:Connect(considerEnemy)
  for _,npc in enemies:GetChildren() do considerEnemy(npc) end
 end
 local fx=combat:WaitForChild('Round10FX',60)
 if fx then
  fx.OnClientEvent:Connect(function(kind,a,b)
   local ok,err=pcall(function()
    if kind=='Blast' then W.blast(a,b) elseif kind=='Howl' then W.howl(a,b) elseif kind=='TombBroken' then W.tombBroken(a) elseif kind=='TombWardenBurst' then W.wardenBurst(a,b) end
   end)
   if not ok then warn('Round10World: '..tostring(kind)..' failed: '..tostring(err)) end
  end)
 end
 RunService.RenderStepped:Connect(function()
  local now=workspace:GetServerTimeNow()
  for npc,B in bloaters do
   if not npc.Parent or npc:GetAttribute('Detonated') then B.done() else local ok,err=pcall(B.step,now);if not ok then warn('Round10World bloater: '..tostring(err));B.done() end end
  end
  for v,V in vents do if not v.Parent then V.done() else pcall(V.step,now) end end
  for m,B in tombs do local h=m.Parent and m:FindFirstChildOfClass('Humanoid');if not h or h.Health<=0 then B.done() else pcall(B.step,now) end end
  local event=workspace:FindFirstChild('Round10Event')
  local vf=event and event:FindFirstChild('Vents')
  if vf then for _,v in vf:GetChildren() do if not vents[v] then trackVent(v) end end end
  if enemies then
   for _,npc in enemies:GetChildren() do
    if npc:GetAttribute('RushAt') or rushes[npc] then stepRush(npc,now) end
    if npc:GetAttribute('PackEmpoweredUntil') or glowing[npc] then stepWolf(npc,now) end
   end
  end
  for npc,R in rushes do if not npc.Parent then R.lane:done();rushes[npc]=nil end end
  for npc,h in glowing do if not npc.Parent then h:Destroy();glowing[npc]=nil end end
 end)
end
return W
