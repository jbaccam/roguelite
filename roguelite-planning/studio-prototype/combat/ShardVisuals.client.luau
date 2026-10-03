-- Smooth local presentation; never submits pickup or currency requests.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Motion=require(combat:WaitForChild('ShardMotion'))
local Visual=require(combat:WaitForChild('CrystalShardVisual'))
local drops=workspace:WaitForChild('RogueliteShardDrops')
local folder=Instance.new('Folder');folder.Name='LocalCrystalVisuals';folder.Parent=workspace
local template=Visual.create(nil,'CrystalShard',1.5)
-- Keep deep-blue facets readable; only the pale cyan faces emit light.
for _,part in template:GetDescendants() do
 if part:IsA('BasePart') and part.Name=='AzureFacet' and part.Color.G>.7 then
  part.Material=Enum.Material.Neon
  part.Color=part.Color:Lerp(Color3.fromRGB(130,235,255),.3)
 end
end
local glow=Instance.new('PointLight');glow.Name='ShardGlow'
glow.Color=Color3.fromRGB(100,210,255);glow.Brightness=.45;glow.Range=5;glow.Shadows=false
glow.Parent=template.PrimaryPart
local attachment=Instance.new('Attachment');attachment.Name='AuraOrigin';attachment.Parent=template.PrimaryPart
local aura=Instance.new('ParticleEmitter');aura.Name='BlueAura'
aura.Texture='rbxasset://textures/particles/smoke_main.dds'
aura.Color=ColorSequence.new(Color3.fromRGB(115,210,255),Color3.fromRGB(55,150,245))
aura.LightEmission=1;aura.LightInfluence=0;aura.Rate=5
aura.Lifetime=NumberRange.new(.8,1.2);aura.Speed=NumberRange.new(.05,.18)
aura.SpreadAngle=Vector2.new(180,180);aura.Rotation=NumberRange.new(0,360);aura.RotSpeed=NumberRange.new(-18,18)
aura.Size=NumberSequence.new({NumberSequenceKeypoint.new(0,1.35),NumberSequenceKeypoint.new(.5,2.15),NumberSequenceKeypoint.new(1,2.6)})
aura.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,1),NumberSequenceKeypoint.new(.2,.82),NumberSequenceKeypoint.new(.6,.91),NumberSequenceKeypoint.new(1,1)})
aura.LockedToPart=true;aura.Parent=attachment
-- A boss shower's sparkle: one burst of light where the crystals leave him (BurstFrom), once per boss.
local sparkled={}
local function sparkle(at)
 local key=string.format('%.1f,%.1f,%.1f',at.X,at.Y,at.Z);if sparkled[key] then return end;sparkled[key]=true
 local p=Instance.new('Part');p.Name='BossShowerSparkle';p.Anchored=true;p.CanCollide=false;p.CanQuery=false;p.CanTouch=false
 p.Transparency=1;p.Size=Vector3.one;p.CFrame=CFrame.new(at);p.Parent=folder
 local e=Instance.new('ParticleEmitter');e.Texture='rbxasset://textures/particles/sparkles_main.dds'
 e.Color=ColorSequence.new(Color3.fromRGB(170,240,255),Color3.fromRGB(70,170,255));e.LightEmission=1;e.LightInfluence=0
 e.Lifetime=NumberRange.new(.5,.9);e.Speed=NumberRange.new(14,26);e.SpreadAngle=Vector2.new(180,180);e.Drag=4
 e.Size=NumberSequence.new({NumberSequenceKeypoint.new(0,1.6),NumberSequenceKeypoint.new(1,0)})
 e.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,0),NumberSequenceKeypoint.new(1,1)});e.Rate=0;e.Parent=p
 local l=Instance.new('PointLight');l.Color=Color3.fromRGB(120,220,255);l.Brightness=4;l.Range=22;l.Parent=p
 e:Emit(60)
 game:GetService('TweenService'):Create(l,TweenInfo.new(.6),{Brightness=0}):Play()
 task.delay(1.2,function() p:Destroy() end)
end
-- Pickup burst (user, 2026-10-03: "nice blue vfx when collecting crystals ... the more you pick up
-- at once the brighter it gets"). When crystals land on a player (MagnetStart + PULL_SECONDS, the
-- moment RogueliteSounds plays its plop), where they land: little blue and white shards burst out,
-- a thin soft ring eases outwards, a few blue orbs drift up and a gentle glow fades; the local
-- player sees "+N" (it keeps adding while pickups keep coming). It stays where it happened, so a
-- running player leaves it behind. Pickups within BURST_WINDOW are one burst; its size and
-- brightness k run from .25 for one crystal to 1 at 24 or more. Flat effects only (billboard shapes
-- and particles), like the game's other VFX. (A first version flashed a big white star on the
-- player's middle and followed them: "way too forced and bright".)
local TweenService=game:GetService('TweenService')
local BURST_WINDOW=.1
local CYAN,PALE,WHITE=Color3.fromRGB(90,200,255),Color3.fromRGB(190,240,255),Color3.new(1,1,1)
local function tween(obj,seconds,goal,style) local tw=TweenService:Create(obj,TweenInfo.new(seconds,style or Enum.EasingStyle.Quad,Enum.EasingDirection.Out),goal);tw:Play();return tw end
local function circle(parent,name,size,z)
 local f=Instance.new('Frame');f.Name=name;f.AnchorPoint=Vector2.new(.5,.5);f.Position=UDim2.fromScale(.5,.5)
 f.Size=UDim2.fromScale(size,size);f.BackgroundTransparency=1;f.BorderSizePixel=0;f.ZIndex=z or 1;f.Parent=parent
 local c=Instance.new('UICorner');c.CornerRadius=UDim.new(.5,0);c.Parent=f
 return f
end
local shardEmitter,orbEmitter -- templates, cloned per burst
do
 local e=Instance.new('ParticleEmitter');e.Name='PickupShards'
 e.Texture='rbxasset://textures/particles/sparkles_main.dds'
 e.Color=ColorSequence.new(WHITE,CYAN);e.LightEmission=1;e.LightInfluence=0
 e.Lifetime=NumberRange.new(.3,.6);e.Speed=NumberRange.new(10,20);e.SpreadAngle=Vector2.new(180,180);e.Drag=6
 e.Orientation=Enum.ParticleOrientation.VelocityParallel
 e.Squash=NumberSequence.new(-1.4) -- long along the way they fly: shards, not dots
 e.Size=NumberSequence.new({NumberSequenceKeypoint.new(0,.55),NumberSequenceKeypoint.new(1,0)})
 e.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,0),NumberSequenceKeypoint.new(.7,.2),NumberSequenceKeypoint.new(1,1)})
 e.Rate=0;e.Enabled=false
 shardEmitter=e
 local o=Instance.new('ParticleEmitter');o.Name='PickupOrbs'
 o.Texture='rbxasset://textures/particles/sparkles_main.dds'
 o.Color=ColorSequence.new(PALE,CYAN);o.LightEmission=1;o.LightInfluence=0
 o.Lifetime=NumberRange.new(.7,1.1);o.Speed=NumberRange.new(2,5);o.SpreadAngle=Vector2.new(35,35)
 o.EmissionDirection=Enum.NormalId.Top;o.Acceleration=Vector3.new(0,2,0);o.Drag=1.5
 o.Size=NumberSequence.new({NumberSequenceKeypoint.new(0,.25),NumberSequenceKeypoint.new(.3,.4),NumberSequenceKeypoint.new(1,0)})
 o.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,.3),NumberSequenceKeypoint.new(1,1)})
 o.Rate=0;o.Enabled=false
 orbEmitter=o
end
local counter={} -- the local player's "+N": {gui, label, total, untilAt}
local function plus(root,value)
 local now=os.clock()
 if counter.gui and counter.gui.Parent and now<counter.untilAt and counter.root==root then
  counter.total+=value
 else
  if counter.gui then counter.gui:Destroy() end
  local g=Instance.new('BillboardGui');g.Name='CrystalPlus';g.Adornee=root;g.Size=UDim2.fromOffset(160,56)
  g.StudsOffsetWorldSpace=Vector3.new(2.4,2.6,0);g.AlwaysOnTop=true;g.LightInfluence=0;g.ResetOnSpawn=false
  local l=Instance.new('TextLabel');l.BackgroundTransparency=1;l.Size=UDim2.fromScale(1,1);l.Font=Enum.Font.FredokaOne;l.TextScaled=true
  l.TextColor3=Color3.fromRGB(110,225,255);l.TextStrokeColor3=Color3.fromRGB(10,40,80);l.TextStrokeTransparency=.15;l.Parent=g
  local s=Instance.new('UIScale');s.Parent=l
  g.Parent=Players.LocalPlayer:FindFirstChildOfClass('PlayerGui')
  counter={gui=g,label=l,scale=s,total=value,root=root}
 end
 counter.untilAt=now+.7
 counter.label.Text='+'..counter.total;counter.label.TextTransparency=0;counter.label.TextStrokeTransparency=.15
 counter.scale.Scale=1.35;tween(counter.scale,.25,{Scale=1},Enum.EasingStyle.Back)
 counter.gui.StudsOffsetWorldSpace=Vector3.new(2.4,2.6,0)
 local mine=counter
 task.delay(.7,function()
  if counter~=mine or os.clock()<mine.untilAt-.01 then return end
  tween(mine.gui,.45,{StudsOffsetWorldSpace=Vector3.new(2.4,4,0)})
  tween(mine.label,.45,{TextTransparency=1,TextStrokeTransparency=1})
  task.delay(.5,function() if mine.gui then mine.gui:Destroy() end;if counter==mine then counter={} end end)
 end)
end
local function burst(p,n,value)
 local root=p.Character and p.Character:FindFirstChild('HumanoidRootPart');if not root then return end
 local k=math.clamp(math.log(n+1)/math.log(25),.25,1)
 if p~=Players.LocalPlayer then k*=.6 end -- someone else's: smaller, and no number
 -- Where it happened, at the waist; it stays there.
 local anchor=Instance.new('Part');anchor.Name='CrystalPickupFX';anchor.Anchored=true;anchor.CanCollide=false;anchor.CanQuery=false
 anchor.CanTouch=false;anchor.CastShadow=false;anchor.Transparency=1;anchor.Size=Vector3.one*.2
 anchor.CFrame=CFrame.new(root.Position+Vector3.new(0,-.4,0));anchor.Parent=folder
 local a=Instance.new('Attachment');a.Parent=anchor
 -- The shards bursting out (the part the user liked), and the orbs drifting up.
 local e=shardEmitter:Clone();e.Speed=NumberRange.new(8+6*k,14+12*k);e.Parent=a
 e:Emit(math.floor(6+30*k))
 local o=orbEmitter:Clone();o.Parent=a
 o:Emit(math.floor(2+6*k))
 -- A thin soft ring easing outwards and a faint glow behind it (no star, no AlwaysOnTop flash).
 local size=3.5+5*k
 local g=Instance.new('BillboardGui');g.Name='Ring';g.Adornee=anchor;g.Size=UDim2.fromScale(size,size)
 g.LightInfluence=0;g.Brightness=1+.4*k;g.ResetOnSpawn=false;g.Parent=anchor
 local glow=circle(g,'Glow',.25,1);glow.BackgroundColor3=CYAN;glow.BackgroundTransparency=.72
 tween(glow,.55,{Size=UDim2.fromScale(.55,.55),BackgroundTransparency=1},Enum.EasingStyle.Sine)
 for i=1,(k>.6 and 2 or 1) do
  local ring=circle(g,'Ring',.2,2)
  local stroke=Instance.new('UIStroke');stroke.Color=i==1 and PALE or CYAN;stroke.Thickness=1.2+2*k;stroke.Transparency=.25;stroke.Parent=ring
  task.delay((i-1)*.1,function()
   tween(ring,.65,{Size=UDim2.fromScale(1-(i-1)*.18,1-(i-1)*.18)},Enum.EasingStyle.Quint)
   tween(stroke,.65,{Transparency=1,Thickness=.6},Enum.EasingStyle.Sine)
  end)
 end
 local light=Instance.new('PointLight');light.Color=CYAN;light.Brightness=.6+2*k;light.Range=6+8*k;light.Shadows=false;light.Parent=a
 tween(light,.6,{Brightness=0},Enum.EasingStyle.Sine)
 task.delay(1.3,function() anchor:Destroy() end)
 if p==Players.LocalPlayer and value>0 then plus(root,value) end
end
local pending={} -- player -> {n, value}: this burst window's pickups
local function landed(p,value)
 local b=pending[p]
 if b then b.n+=1;b.value+=value;return end
 b={n=1,value=value};pending[p]=b
 task.delay(BURST_WINDOW,function() pending[p]=nil;if p.Parent then burst(p,b.n,b.value) end end)
end
do
 local scheduled={}
 local function check(m)
  local start,id=m:GetAttribute('MagnetStart'),m:GetAttribute('MagnetUserId')
  if type(start)~='number' or type(id)~='number' or scheduled[m]==start then return end
  scheduled[m]=start
  task.delay(math.max(0,start+Motion.PULL_SECONDS-workspace:GetServerTimeNow()),function()
   scheduled[m]=nil
   local p=Players:GetPlayerByUserId(id)
   -- A cancelled pull (its start changed) shows nothing.
   if p and m:GetAttribute('MagnetStart')==start then landed(p,m:GetAttribute('ShardValue') or 0) end
  end)
 end
 local function watch(m)
  m:GetAttributeChangedSignal('MagnetStart'):Connect(function() check(m) end)
  m:GetAttributeChangedSignal('MagnetUserId'):Connect(function() check(m) end)
  check(m)
 end
 for _,m in drops:GetChildren() do watch(m) end
 drops.ChildAdded:Connect(watch)
end
local visuals={}
local refresh=0
-- Drops being pulled first, then nearest. Only the best 128 are drawn and only the first 32 need
-- their rank (glow and aura), so the rest are never sorted.
local entries,list,pass={},{},0 -- entries: drop model -> {model,origin,distance,active,seen}
local function before(a,b) if a.active~=b.active then return a.active end;return a.distance<b.distance end
-- Moves the k best of list[1..n] into list[1..k], unordered (Wirth's FIND, average O(n)).
local function select(n,k)
 local lo,hi=1,n
 while lo<hi do
  local pivot=list[(lo+hi)//2];local i,j=lo,hi
  repeat
   while before(list[i],pivot) do i+=1 end
   while before(pivot,list[j]) do j-=1 end
   if i<=j then list[i],list[j]=list[j],list[i];i+=1;j-=1 end
  until i>j
  if k<=j then hi=j elseif k>=i then lo=i else return end
 end
end
RunService.RenderStepped:Connect(function(dt)
 local now=workspace:GetServerTimeNow();refresh-=dt
 if refresh<=0 then
  refresh=.15
  local position=workspace.CurrentCamera.CFrame.Position
  local root=Players.LocalPlayer.Character and Players.LocalPlayer.Character:FindFirstChild('HumanoidRootPart')
  if root then position=root.Position end
  pass+=1
  local n=0
  for _,m in drops:GetChildren() do
   -- A drop's Origin never changes once it exists, so it is read once.
   local e=entries[m]
   if not e then
    local origin=m:GetAttribute('Origin')
    if typeof(origin)=='Vector3' then e={model=m,origin=origin};entries[m]=e end
   end
   if e then
    e.seen=pass;e.distance=(e.origin-position).Magnitude;e.active=m:GetAttribute('MagnetUserId')~=nil
    n+=1;list[n]=e
   end
  end
  for i=n+1,#list do list[i]=nil end
  for m,e in entries do if e.seen~=pass then entries[m]=nil end end
  local count=math.min(128,n);local ranked=math.min(32,count)
  if n>count then select(n,count) end
  if count>ranked then select(count,ranked) end
  for i=2,ranked do -- insertion sort of the ranked few
   local e=list[i];local j=i-1
   while j>=1 and before(e,list[j]) do list[j+1]=list[j];j-=1 end
   list[j+1]=e
  end
  local wanted={}
  for i=1,count do
   local m=list[i].model;wanted[m]=true
   if not visuals[m] then local v=template:Clone();v.Parent=folder;visuals[m]=v end
   -- Bound translucent overdraw and dynamic lights in dense drop piles.
   local v=visuals[m]
   v.PrimaryPart.ShardGlow.Enabled=i<=12 and list[i].distance<45
   v.PrimaryPart.AuraOrigin.BlueAura.Enabled=i<=32 and list[i].distance<70
  end
  for m,v in visuals do if not wanted[m] then v:Destroy();visuals[m]=nil end end
 end
 for m,v in visuals do
  if not m.Parent then v:Destroy();visuals[m]=nil;continue end
  local origin=m:GetAttribute('Origin');local born=m:GetAttribute('BornAt') or now
  local pos=Motion.idle(origin,born,now)
  local spin=Motion.rotation(born,now)
  -- A boss crystal first bursts out of him and lands (ShardMotion.burst), spinning fast.
  local from=m:GetAttribute('BurstFrom')
  if typeof(from)=='Vector3' then
   sparkle(from)
   local age=now-born-(m:GetAttribute('BurstDelay') or 0)
   local b=Motion.burst(from,origin,age)
   if b then pos=b;spin=CFrame.Angles(age*9,age*13,0) end
  end
  local id=m:GetAttribute('MagnetUserId');local start=m:GetAttribute('MagnetStart')
  local p=id and Players:GetPlayerByUserId(id)
  local r=p and p.Character and p.Character:FindFirstChild('HumanoidRootPart')
  -- A start still ahead (a boss crystal waiting its turn) leaves it where it is until then.
  if r and start and now>=start then pos=Motion.pull(m:GetAttribute('MagnetOrigin') or pos,r.Position,now-start) end
  v:PivotTo(CFrame.new(pos)*spin)
 end
end)
