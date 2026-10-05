-- Smooth local presentation; never submits pickup or currency requests.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Motion=require(combat:WaitForChild('ShardMotion'))
local Visual=require(combat:WaitForChild('CrystalShardVisual'))
local drops=workspace:WaitForChild('RogueliteShardDrops')
local folder=Instance.new('Folder');folder.Name='LocalCrystalVisuals';folder.Parent=workspace
-- One crystal template per colour. tint nil = today's blue; a tint (ShardMotion.CRYSTAL_COLORS)
-- maps each facet from its deep (dark) to its pale (light) end by how bright the blue facet was,
-- and its glow, aura and neon faces follow (2026-10-03).
local function build(tint)
 local template=Visual.create(nil,'CrystalShard',1.5)
 -- Keep deep-blue facets readable; only the pale cyan faces emit light.
 for _,part in template:GetDescendants() do
  if part:IsA('BasePart') and part.Name=='AzureFacet' then
   local neon=part.Color.G>.7
   if tint then part.Color=tint.dark:Lerp(tint.light,math.clamp((part.Color.G*255-92)/125,0,1)) end
   if neon then
    part.Material=Enum.Material.Neon
    part.Color=part.Color:Lerp(tint and tint.glow or Color3.fromRGB(130,235,255),.3)
   end
  end
 end
 local glow=Instance.new('PointLight');glow.Name='ShardGlow'
 glow.Color=tint and tint.glow or Color3.fromRGB(100,210,255);glow.Brightness=.45;glow.Range=5;glow.Shadows=false
 glow.Parent=template.PrimaryPart
 local attachment=Instance.new('Attachment');attachment.Name='AuraOrigin';attachment.Parent=template.PrimaryPart
 local aura=Instance.new('ParticleEmitter');aura.Name='BlueAura'
 aura.Texture='rbxasset://textures/particles/smoke_main.dds'
 aura.Color=tint and ColorSequence.new(tint.glow,tint.dark:Lerp(tint.glow,.4)) or ColorSequence.new(Color3.fromRGB(115,210,255),Color3.fromRGB(55,150,245))
 aura.LightEmission=1;aura.LightInfluence=0;aura.Rate=5
 aura.Lifetime=NumberRange.new(.8,1.2);aura.Speed=NumberRange.new(.05,.18)
 aura.SpreadAngle=Vector2.new(180,180);aura.Rotation=NumberRange.new(0,360);aura.RotSpeed=NumberRange.new(-18,18)
 aura.Size=NumberSequence.new({NumberSequenceKeypoint.new(0,1.35),NumberSequenceKeypoint.new(.5,2.15),NumberSequenceKeypoint.new(1,2.6)})
 aura.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,1),NumberSequenceKeypoint.new(.2,.82),NumberSequenceKeypoint.new(.6,.91),NumberSequenceKeypoint.new(1,1)})
 aura.LockedToPart=true;aura.Parent=attachment
 return template
end
-- Keys: 1-4 (ShardMotion.colorIndex; 1 is today's blue) and 'public'. Built on first use.
local templates={[1]=build(nil)}
local function templateFor(key)
 local t=templates[key]
 if not t then t=build(key=='public' and Motion.PUBLIC_COLOR or Motion.CRYSTAL_COLORS[key]);templates[key]=t end
 return t
end
-- Colour per killer (user, 2026-10-03: "different color crystals for diff people who killed"):
-- with 2+ players in the run (RunMember), a crystal wears its owner's CrystalSlot colour (the
-- killer's, from ShardDropService), a public one is white, and pickup bursts take the collector's.
-- Solo keeps today's blue everywhere. slotOf: userId -> CrystalSlot, kept by the watchers below.
local slotOf,multi={},false
local function colorKey(owner)
 if not multi then return 1 end
 local slot=owner~=0 and slotOf[owner]
 return slot and Motion.colorIndex(slot) or 'public'
end
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
-- at once the brighter it gets"; then, after two rounds: like the reference, a star that "starts
-- small gets larger and pops", "clean and nonchalant and smooth", never stamped on the player's
-- middle, and no "+5" numbers). When crystals land on a player (MagnetStart + PULL_SECONDS, the
-- moment RogueliteSounds plays its plop):
--   a star at hip height on the side they came from, a little in front of the body: it grows from
--   small, swells a touch and pops (one or two tiny twinkles with it for a bigger haul);
--   at the pop, the blue and white shards burst out and a faint thin ring spreads around the hips.
-- The star's spot and the shards ride along with the player (the shards following them looked
-- good); nothing lights the body. Pickups within BURST_WINDOW are one burst; its size k runs from
-- .25 for one crystal to 1 at 24 or more. Flat effects only, like the game's other VFX.
local TweenService=game:GetService('TweenService')
local BURST_WINDOW=.1
local CYAN,PALE,WHITE=Color3.fromRGB(90,200,255),Color3.fromRGB(190,240,255),Color3.new(1,1,1)
local function tween(obj,seconds,goal,style,direction) local tw=TweenService:Create(obj,TweenInfo.new(seconds,style or Enum.EasingStyle.Sine,direction or Enum.EasingDirection.Out),goal);tw:Play();return tw end
local function circle(parent,name,size,z)
 local f=Instance.new('Frame');f.Name=name;f.AnchorPoint=Vector2.new(.5,.5);f.Position=UDim2.fromScale(.5,.5)
 f.Size=UDim2.fromScale(size,size);f.BackgroundTransparency=1;f.BorderSizePixel=0;f.ZIndex=z or 1;f.Parent=parent
 local c=Instance.new('UICorner');c.CornerRadius=UDim.new(.5,0);c.Parent=f
 return f
end
-- One ray of a star: a thin bar, bright in the middle and fading to fine tips.
local function ray(parent,length,width,angle)
 local f=Instance.new('Frame');f.Name='Ray';f.AnchorPoint=Vector2.new(.5,.5);f.Position=UDim2.fromScale(.5,.5)
 f.Size=UDim2.fromScale(length,width);f.Rotation=angle;f.BackgroundColor3=WHITE;f.BorderSizePixel=0;f.ZIndex=3;f.Parent=parent
 local g=Instance.new('UIGradient')
 g.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,1),NumberSequenceKeypoint.new(.4,.35),NumberSequenceKeypoint.new(.5,0),NumberSequenceKeypoint.new(.6,.35),NumberSequenceKeypoint.new(1,1)})
 g.Parent=f
 local c=Instance.new('UICorner');c.CornerRadius=UDim.new(.5,0);c.Parent=f
end
-- A star that grows, swells and pops: `size` studs across at full size, starting after `delay`.
local function star(adornee,size,delay,offset,pale)
 local g=Instance.new('BillboardGui');g.Name='PickupStar';g.Adornee=adornee;g.Size=UDim2.fromScale(size,size)
 g.StudsOffset=offset -- toward the camera, so the body never hides it
 g.LightInfluence=0;g.Brightness=1.15;g.ResetOnSpawn=false;g.Parent=adornee
 local body=Instance.new('Frame');body.Name='Body';body.AnchorPoint=Vector2.new(.5,.5);body.Position=UDim2.fromScale(.5,.5)
 body.Size=UDim2.fromScale(1,1);body.BackgroundTransparency=1;body.Rotation=math.random(-20,20);body.Parent=g
 local scale=Instance.new('UIScale');scale.Scale=.12;scale.Parent=body
 local glow=circle(body,'Glow',.42,1);glow.BackgroundColor3=pale or PALE;glow.BackgroundTransparency=.62
 ray(body,1,.06,0);ray(body,1,.06,90);ray(body,.5,.04,45);ray(body,.5,.04,-45)
 task.delay(delay,function()
  if not g.Parent then return end
  tween(body,.36,{Rotation=body.Rotation+18})
  tween(scale,.15,{Scale=1}) -- grows
  task.wait(.15)
  tween(scale,.06,{Scale=1.12}) -- a touch more
  task.wait(.06)
  tween(scale,.12,{Scale=0},Enum.EasingStyle.Quad,Enum.EasingDirection.In) -- and pops
  tween(glow,.12,{BackgroundTransparency=1})
  task.wait(.13);g:Destroy()
 end)
end
local shardEmitter -- template, cloned per burst
do
 local e=Instance.new('ParticleEmitter');e.Name='PickupShards'
 e.Texture='rbxasset://textures/particles/sparkles_main.dds'
 e.Color=ColorSequence.new(WHITE,CYAN);e.LightEmission=1;e.LightInfluence=0
 e.Lifetime=NumberRange.new(.3,.55);e.Speed=NumberRange.new(10,20);e.SpreadAngle=Vector2.new(180,180);e.Drag=6
 e.Orientation=Enum.ParticleOrientation.VelocityParallel
 e.Squash=NumberSequence.new(-1.4) -- long along the way they fly: shards, not dots
 e.Size=NumberSequence.new({NumberSequenceKeypoint.new(0,.45),NumberSequenceKeypoint.new(1,0)})
 e.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,0),NumberSequenceKeypoint.new(.7,.25),NumberSequenceKeypoint.new(1,1)})
 e.Rate=0;e.Enabled=false
 shardEmitter=e
end
local POP=.21 -- seconds from the burst to the star's pop
local function burst(p,n,froms)
 local root=p.Character and p.Character:FindFirstChild('HumanoidRootPart');if not root then return end
 local k=math.clamp(math.log(n+1)/math.log(25),.25,1)
 if p~=Players.LocalPlayer then k*=.6 end -- someone else's: smaller
 -- The collector's crystal colour with 2+ in the run; slot 1 and solo keep today's blue.
 local slot=multi and slotOf[p.UserId]
 local tint=slot and Motion.colorIndex(slot)~=1 and Motion.slotColor(slot) or nil
 local pale,cyan=tint and tint.light or PALE,tint and tint.glow or CYAN
 -- The side they came from (their average direction), else the camera's right.
 local side=Vector3.zero
 for _,from in froms do local d=from-root.Position;d=Vector3.new(d.X,0,d.Z);if d.Magnitude>.1 then side+=d.Unit end end
 if side.Magnitude<.1 then local r=workspace.CurrentCamera.CFrame.RightVector;side=Vector3.new(r.X,0,r.Z) end
 side=side.Magnitude>.01 and side.Unit or Vector3.xAxis
 local at=Instance.new('Attachment');at.Name='CrystalPickupFX'
 at.Position=root.CFrame:VectorToObjectSpace(side*.9)+Vector3.new(0,-.5,0);at.Parent=root
 star(at,1.3+1.5*k,0,Vector3.new(0,0,1.4),pale)
 for i=1,(k>.7 and 2 or k>.4 and 1 or 0) do
  local jitter=Vector3.new(math.random()*1.2-.6,math.random()*1.2-.4,1.6)
  star(at,.55+.3*k,.05+.05*i,jitter,pale)
 end
 task.delay(POP,function()
  if not at.Parent then return end
  local e=shardEmitter:Clone();e.Speed=NumberRange.new(7+5*k,12+10*k);e.Parent=at
  if tint then e.Color=ColorSequence.new(WHITE,cyan) end
  e:Emit(math.floor(5+25*k))
  -- A faint thin ring around the hips, easing outwards.
  local g=Instance.new('BillboardGui');g.Name='PickupRing';g.Adornee=root;g.Size=UDim2.fromScale(4.5+2.5*k,4.5+2.5*k)
  g.StudsOffset=Vector3.new(0,-.5,0);g.LightInfluence=0;g.ResetOnSpawn=false;g.Parent=at
  local ring=circle(g,'Ring',.5,1)
  local stroke=Instance.new('UIStroke');stroke.Color=pale;stroke.Thickness=1.6;stroke.Transparency=.5;stroke.Parent=ring
  tween(ring,.5,{Size=UDim2.fromScale(1,1)},Enum.EasingStyle.Quint)
  tween(stroke,.5,{Transparency=1,Thickness=.5})
 end)
 task.delay(1.1,function() at:Destroy() end)
end
local pending={} -- player -> {n, froms}: this burst window's pickups
local function landed(p,from)
 local b=pending[p]
 if not b then
  b={n=0,froms={}};pending[p]=b
  task.delay(BURST_WINDOW,function() pending[p]=nil;if p.Parent then burst(p,b.n,b.froms) end end)
 end
 b.n+=1;if typeof(from)=='Vector3' then table.insert(b.froms,from) end
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
   if p and m:GetAttribute('MagnetStart')==start then landed(p,m:GetAttribute('MagnetOrigin') or m:GetAttribute('Origin')) end
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
-- Whose colour is whose: with 2+ players in the run, a small diamond in each teammate's colour
-- floats over their name (yours is on the HUD's shard counter, RogueliteUI). Solo shows none.
local marks={} -- player -> BillboardGui
local markGui=Players.LocalPlayer:WaitForChild('PlayerGui')
local function mark(p)
 local slot=slotOf[p.UserId]
 local head=multi and slot and p~=Players.LocalPlayer and p:GetAttribute('RunMember') and p.Character and p.Character:FindFirstChild('Head')
 local b=marks[p]
 if not head then if b then b:Destroy();marks[p]=nil end;return end
 if not b then
  b=Instance.new('BillboardGui');b.Name='CrystalColorMark';b.Size=UDim2.fromOffset(18,18)
  b.StudsOffsetWorldSpace=Vector3.new(0,3.6,0) -- above the Roblox name over the head
  b.AlwaysOnTop=true;b.LightInfluence=0;b.MaxDistance=70;b.ResetOnSpawn=false
  local d=Instance.new('Frame');d.Name='Diamond';d.AnchorPoint=Vector2.new(.5,.5);d.Position=UDim2.fromScale(.5,.5)
  d.Size=UDim2.fromScale(.7,.7);d.Rotation=45;d.BorderSizePixel=0;d.Parent=b
  local s=Instance.new('UIStroke');s.Color=Color3.fromRGB(8,10,11);s.Thickness=2;s.Parent=d
  b.Parent=markGui;marks[p]=b
 end
 b.Adornee=head;b.Diamond.BackgroundColor3=Motion.slotColor(slot).mark
end
local function recount()
 local n=0;for _,p in Players:GetPlayers() do if p:GetAttribute('RunMember') then n+=1 end end
 multi=n>=2
 for _,p in Players:GetPlayers() do mark(p) end
end
local function watchPlayer(p)
 slotOf[p.UserId]=p:GetAttribute('CrystalSlot')
 p:GetAttributeChangedSignal('CrystalSlot'):Connect(function() slotOf[p.UserId]=p:GetAttribute('CrystalSlot');recount() end)
 p:GetAttributeChangedSignal('RunMember'):Connect(recount)
 p.CharacterAdded:Connect(function(c) c:WaitForChild('Head',10);if p.Parent then mark(p) end end)
end
for _,p in Players:GetPlayers() do watchPlayer(p) end
Players.PlayerAdded:Connect(function(p) watchPlayer(p);recount() end)
Players.PlayerRemoving:Connect(function(p)
 slotOf[p.UserId]=nil
 local b=marks[p];if b then b:Destroy();marks[p]=nil end
 task.defer(recount)
end)
recount()
local visuals={}
local shownKey={} -- drop model -> the colour key its visual was built with
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
   -- Capped drops can be reused at a new death. Refresh their origin before ranking them.
   local e=entries[m]
   if not e then
    local origin=m:GetAttribute('Origin')
    -- Its owner (the killer; 0 = public) never changes either.
    if typeof(origin)=='Vector3' then e={model=m,origin=origin,owner=m:GetAttribute('OwnerUserId') or 0};entries[m]=e end
   end
   if e then
    local origin=m:GetAttribute('Origin');if typeof(origin)=='Vector3' then e.origin=origin end
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
   -- Rebuilt in the right colour when it changes (a second player joining the run, say).
   local key=colorKey(list[i].owner)
   if visuals[m] and shownKey[m]~=key then visuals[m]:Destroy();visuals[m]=nil end
   if not visuals[m] then local v=templateFor(key):Clone();v.Parent=folder;visuals[m]=v;shownKey[m]=key end
   -- Bound translucent overdraw and dynamic lights in dense drop piles.
   local v=visuals[m]
   v.PrimaryPart.ShardGlow.Enabled=i<=12 and list[i].distance<45
   v.PrimaryPart.AuraOrigin.BlueAura.Enabled=i<=32 and list[i].distance<70
  end
  for m,v in visuals do if not wanted[m] then v:Destroy();visuals[m]=nil;shownKey[m]=nil end end
 end
 for m,v in visuals do
  if not m.Parent then v:Destroy();visuals[m]=nil;shownKey[m]=nil;continue end
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
