local Tags=game:GetService('CollectionService')
local Run=game:GetService('RunService')
local Debris=game:GetService('Debris')
local Motion=require(game.ReplicatedStorage:WaitForChild('RogueliteCombat'):WaitForChild('BossMotion'))
local tracked={}
local BOSS_MAX_GAIT_RATE=1.8 -- Walk clip seconds per real second
local red=Color3.fromRGB(224,45,49)
local function part(parent,name,size,cf,transparency)
 local p=Instance.new('Part');p.Name=name;p.Size=size;p.CFrame=cf;p.Anchored=true;p.CanCollide=false;p.CanQuery=false;p.CanTouch=false;p.CastShadow=false
 p.Material=Enum.Material.Neon;p.Color=red;p.Transparency=transparency or .68;p.Parent=parent;return p
end
local function disc(parent,center,radius)
 local p=part(parent,'WarningCircle',Vector3.new(.045,radius*2,radius*2),CFrame.new(center)*CFrame.Angles(0,0,math.pi/2),.76);p.Shape=Enum.PartType.Cylinder
 for i=1,64 do
  local a=i*math.pi/32;local pt=center+Vector3.new(math.sin(a)*radius,.025,math.cos(a)*radius)
  part(parent,'WarningEdge',Vector3.new(.09,.04,radius*math.pi/32+ .04),CFrame.new(pt)*CFrame.Angles(0,a-math.pi/2,0),.2)
 end
end
local function warning(npc,kind)
 local folder=Instance.new('Folder');folder.Name='BossWarning';folder.Parent=workspace
 local cf=npc:GetAttribute('BossFrame');local y=(npc:GetAttribute('BossGroundY') or cf.Y-Motion.RootHeight)+.065
 local points,radius=Motion.warning(cf,kind)
 if kind=='Slam' then disc(folder,Vector3.new(points[1].X,y,points[1].Z),radius)
 elseif kind=='Spin' then
  local reach=0;for _,p in points do local d=p-cf.Position;reach=math.max(reach,Vector2.new(d.X,d.Z).Magnitude+radius) end
  disc(folder,Vector3.new(cf.X,y,cf.Z),reach)
 else
  -- Polar ribbon of the true projected hammer path, filled in to the boss: the server hits
  -- anyone between the boss and the hammer (BossMotion.sweeps), so the warning shows that too.
  for i=0,95 do
   local angle=i*math.pi/48;local direction=Vector3.new(math.sin(angle),0,math.cos(angle));local near,far=math.huge,0
   for _,point in points do
    local d=Vector3.new(point.X-cf.X,0,point.Z-cf.Z);local along=d:Dot(direction);local cross2=d:Dot(d)-along*along
    if along>0 and cross2<=radius*radius then local half=math.sqrt(radius*radius-cross2);near=math.min(near,math.max(0,along-half));far=math.max(far,along+half) end
   end
   if far>near then
    near=0
    local mid=(near+far)/2;local p=Vector3.new(cf.X,y,cf.Z)+direction*mid
    part(folder,'FrontalArc',Vector3.new(math.max(.05,mid*math.pi/48),.045,far-near),CFrame.lookAt(p,p+direction),.64)
   end
  end
 end
 return folder
end
local function impact(npc,kind)
 if kind~='Slam' then return end
 local cf=npc:GetAttribute('BossFrame');if not cf then return end
 local pos=Motion.head(cf,'Slam',Motion.Attacks.Slam.active).Position
 pos=Vector3.new(pos.X,(npc:GetAttribute('BossGroundY') or pos.Y)+.10,pos.Z)
 local host=part(workspace,'BossImpact',Vector3.new(.1,.1,.1),CFrame.new(pos),1)
 local e=Instance.new('ParticleEmitter');e.Texture='rbxasset://textures/particles/smoke_main.dds';e.Color=ColorSequence.new(Color3.fromRGB(152,134,107));e.Rate=0
 e.Lifetime=NumberRange.new(.35,.75);e.Speed=NumberRange.new(8,14);e.SpreadAngle=Vector2.new(85,85);e.Size=NumberSequence.new({NumberSequenceKeypoint.new(0,.5),NumberSequenceKeypoint.new(1,2.2)})
 e.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,.30),NumberSequenceKeypoint.new(1,1)});e.Parent=host;e:Emit(22)
 local s=Instance.new('Sound');s.SoundId='rbxasset://sounds/impact_explosion_03.mp3';s.Volume=.55;s.PlaybackSpeed=.7;s.RollOffMaxDistance=75;s.Parent=host;s:Play()
 local radius=Motion.Attacks.Slam.radius*.85
 for i=1,12 do local angle=i*math.pi/6;local p=part(host,'ImpactChip',Vector3.new(.25,.14,.45),CFrame.new(pos+Vector3.new(math.sin(angle)*radius,.03,math.cos(angle)*radius))*CFrame.Angles(0,angle,0),.12);p.Material=Enum.Material.Slate;p.Color=Color3.fromRGB(137,125,100) end
 Debris:AddItem(host,1.0)
end
local function track(npc)
 if not tracked[npc] then tracked[npc]={phase=0,lastSerial=-1} end
end
Tags:GetInstanceAddedSignal('HammerBoss'):Connect(track)
for _,npc in Tags:GetTagged('HammerBoss') do track(npc) end
Run.PreSimulation:Connect(function(dt)
 local now=workspace:GetServerTimeNow()
 for npc,state in tracked do
  if not npc.Parent or not Tags:HasTag(npc,'HammerBoss') then if state.warning then state.warning:Destroy() end;tracked[npc]=nil;continue end
  local h=npc:FindFirstChildOfClass('Humanoid');local root=npc.PrimaryPart;if not h or not root then continue end
  local displacement=state.previousPosition and root.Position-state.previousPosition or Vector3.zero
  state.previousPosition=root.Position
  local distance=Vector2.new(displacement.X,displacement.Z).Magnitude
  local start=npc:GetAttribute('BossStart');local kind=npc:GetAttribute('BossAttack');local a=kind and Motion.Attacks[kind];local age=start and now-start
  local death=npc:GetAttribute('BossDeathStart');local hit=npc:GetAttribute('BossHitStart');local clip,time
  if death then clip,time='Death',now-death
  elseif a and age and age>=0 and age<=a.duration and npc:GetAttribute('Attacking') then clip,time=kind,age
  elseif hit and now-hit<Motion.duration('Hit') then clip,time='Hit',now-hit
  else
   local v=root.AssemblyLinearVelocity;local moving=Vector2.new(v.X,v.Z).Magnitude>.4
   clip=moving and 'Walk' or 'Idle'
   -- Ground distance, not elapsed time, advances the planted-foot gait.
   -- Chase speed outpaces the authored stride; cap cadence so the heavy gait stays weighty.
   state.phase+=moving and math.min(distance/(Motion.Data.walkSpeed or 4.5),dt*BOSS_MAX_GAIT_RATE) or dt
   time=state.phase%Motion.duration(clip)
  end
  local poses=Motion.sample(clip,time)
  if state.lastClip~=clip and state.lastPose and clip~='Death' then state.blendFrom=state.lastPose;state.blendStart=now end
  -- Ease out of the heavy walk during the attack's initial windup only.
  -- All contact frames still use the exact authoritative pose.
  if state.blendFrom then
   local duration=(clip=='Walk' or clip=='Idle') and .16 or .12
   local weight=math.clamp((now-state.blendStart)/duration,0,1)
   poses=Motion.blend(state.blendFrom,poses,weight)
   if weight==1 then state.blendFrom=nil end
  end
  Motion.apply(npc,poses);state.lastPose=poses;state.lastClip=clip
  local warn=not death and npc:GetAttribute('Attacking') and a and age and age>=a.anticipation and age<a.active
  if warn and not state.warning then state.warning=warning(npc,kind) end
  if not warn and state.warning then state.warning:Destroy();state.warning=nil end
  local serial=npc:GetAttribute('BossSerial') or 0
  if not death and age and a and age>=a.active and age<a.duration and serial~=state.lastSerial then state.lastSerial=serial;impact(npc,kind) end
 end
end)
