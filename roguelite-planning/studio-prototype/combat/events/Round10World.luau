-- Client only: the round 10 events' world presentation. Everything here is drawn from replicated
-- server state (attributes on the enemies, the vents, Round10FX events) and never decides a hit:
-- every warning is the exact shape the server tests (ExploderService disc, vent disc, rush lane).
--   Bloaters  armed (FuseUntil): the burst disc on the ground filling to the edge at the burst, an
--             ABOUT TO BURST tag with a countdown bar (its own state, never its health bar), and the
--             belly swelling (UpperTorso and its joints, locally). Burst: a flat cartoon pop.
--   Vents     CHARGING (orange disc filling, seams brightening), ERUPTING (the disc held hot, a lava
--             plume and small debris), COOLING (steam, the disc fading). A tag says which.
--   Rushes    the DJ's Beat Command: each rusher's lane, filling until it goes.
--   Howl      the alpha's howl ring at its radius; empowered wolves glow red until it runs out.
--   Tombs     a destroyed coffin's sand burst and stone chunks.
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
   if root then
    local gui,label,plate=tag(root,'ABOUT TO BURST',T.Color.gold,Vector3.new(0,5.2,0))
    local fill=T.bar(plate,'Fuse',10,30,150,6,ARM_COLOR);plate.Size=UDim2.fromOffset(170,40)
    B.tag,B.fuseFill=gui,fill
   end
   B.scale=scaleRig(npc)
   Common.cue('dragon_inhale',center,.45,1.9)
  end
  B.warn:paint(k,fuse-now)
  if B.fuseFill then T.setBar(B.fuseFill,1-k) end
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
local vents={}
local VENT_WARN=Color3.fromRGB(255,140,40)
local VENT_HOT=Color3.fromRGB(255,72,36)
local LABEL={Charging='CHARGING',Erupting='ERUPTING',Cooling='COOLING'}
local function trackVent(v)
 if vents[v] then return end
 local V={model=v,glows={}};vents[v]=V
 for _,p in v:GetDescendants() do if p:IsA('BasePart') and p.Name:find('Glow') then p.Material=Enum.Material.Neon;table.insert(V.glows,{part=p,base=p.Color}) end end
 local center=v:GetAttribute('Center') or v:GetPivot().Position
 local radius=v:GetAttribute('Radius') or 9
 V.host=Common.part('Round10Vent',Vector3.one*.05,CFrame.new(center+up*.5),K.White,1)
 local function setState()
  local state=v:GetAttribute('State');local untilAt=v:GetAttribute('StateUntil')
  if V.label then V.label:Destroy();V.label=nil end
  if V.plume then for _,e in V.plume do e.Enabled=false;task.delay(2,function() e:Destroy() end) end;V.plume=nil end
  V.state,V.untilAt,V.from=state,untilAt,workspace:GetServerTimeNow()
  if LABEL[state] then local g=tag(V.host,LABEL[state],state=='Erupting' and VENT_HOT or state=='Charging' and T.Color.gold or T.Color.muted,Vector3.new(0,4.5,0));V.label=g end
  if state=='Charging' then
   if V.warn then V.warn:done() end
   V.warn=disc(center,radius,VENT_WARN)
   Common.cue('stone_rumble',center,.5,.8)
  elseif state=='Erupting' then
   if not V.warn then V.warn=disc(center,radius,VENT_HOT) end
   V.warn:color(VENT_HOT)
   local host=V.host
   V.plume={
    Common.fx(host,'Flame',{Rate=34,Speed={30,46},SpreadAngle=10,Lifetime={.6,1},Size=Common.ns({0,2.6},{1,5.5}),Color=Color3.fromRGB(255,160,60),Transparency=Common.ns({0,.05},{.7,.35},{1,1}),LightEmission=.6,Drag=1.4,Rotation={0,360},EmissionDirection=Enum.NormalId.Top}),
    Common.fx(host,'SmokePuff',{Rate=8,Speed={14,24},SpreadAngle=16,Lifetime={1.2,1.8},Size=Common.ns({0,3},{1,8}),Color=Color3.fromRGB(64,52,54),Transparency=Common.ns({0,.25},{1,1}),Drag=1.1,Rotation={0,360},EmissionDirection=Enum.NormalId.Top}),
    Common.fx(host,'Ember',{Rate=26,Speed={18,32},SpreadAngle=28,Lifetime={.8,1.4},Size=Common.ns({0,.45},{1,.1}),Color=Color3.fromRGB(255,190,90),LightEmission=1,Acceleration=Vector3.new(0,-30,0),EmissionDirection=Enum.NormalId.Top}),
   }
   Common.cue('lava_hiss',center,.75,1);Common.shake(center,.25,.4);Common.light(center+up*4,Color3.fromRGB(255,130,50),radius*2.4,3.5,(untilAt or 2)-workspace:GetServerTimeNow())
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
  else
   if V.warn then V.warn:done();V.warn=nil end
  end
 end
 v:GetAttributeChangedSignal('State'):Connect(setState)
 setState()
 function V.step(now)
  if not v.Parent then return end
  local s,untilAt=V.state,V.untilAt or now
  local span=math.max(.1,untilAt-V.from);local k=math.clamp((now-V.from)/span,0,1)
  local heat=s=='Charging' and k or s=='Erupting' and 1 or s=='Cooling' and 1-k or 0
  for _,g in V.glows do if g.part.Parent then g.part.Color=g.base:Lerp(Color3.fromRGB(255,214,120),heat) end end
  if V.warn then
   if s=='Charging' then V.warn:paint(k,untilAt-now)
   elseif s=='Erupting' then V.warn:paint(1,nil,true)
   elseif s=='Cooling' then V.warn:fade(k) end
  end
 end
 function V.done()
  if V.warn then V.warn:done() end;if V.label then V.label:Destroy() end;if V.host then V.host:Destroy() end
  vents[v]=nil
 end
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
  R={at=at,born=now,lane=lane(from,dir,npc:GetAttribute('RushLength') or 30,npc:GetAttribute('RushWidth') or 4.5,RUSH)}
  rushes[npc]=R
  Common.cue('crab_scuttle',from,.35,1.2)
 end
 R.lane:paint((now-R.born)/math.max(.1,R.at-R.born))
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
    if kind=='Blast' then W.blast(a,b) elseif kind=='Howl' then W.howl(a,b) elseif kind=='TombBroken' then W.tombBroken(a) end
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
