-- Turrets, client (HANDYMAN_TURRET.md). StarterPlayerScripts.HandymanTurret, a LocalScript
-- (unsandboxed, like PetVisuals). Presentation only; the server (HandymanTurretService) decides
-- where turrets stand and what they shoot, and nothing here sends a request.
--  * Every Folder in workspace.RogueliteTurrets (one per turret, named UserId_n; turret items since
--    2026-10-04, any number per player) gets a local copy of its tier's model
--    (RogueliteCombat.HandymanTurrets.T1-T4) on its Position and Yaw. Anchored, no collision.
--  * The head turns toward the replicated Aim (a slow look around when it is idle) and snaps to each
--    nail it fires: the first 'Fly' row of each of its projectiles (id 'Turret', slotIndex 100 +
--    its Index) on the Shot remote. The barrel kicks back, a flat Neon flash shows at the muzzle,
--    and Tier IV's barrel cluster spins up while it fires. Turrets past 250 studs from the camera
--    aren't posed, and idle ones (no shot for 1.5 s) are posed at 20 Hz, so 30 turrets stay cheap.
--  * Each placement (BuiltAt, every wave start) drops it in with a flat lime ground ring and dust;
--    a new tier swaps the model with the same ring.
--  * Follow (2026-10-10, user: "disassemble and reassemble animations ... grey smoke ... come out of
--    the ground ... like it's being assembled"): PackAt folds it into the ground over PACK_TIME
--    (barrel folds, head drops, the pieces shrink and sink; grey smoke puffs and a dust ring at the
--    base); the BuiltAt after it builds it at the new spot over BUILD_TIME (a smoke column billows
--    out of the ground, then the base, the head and the barrel rise one by one with an overshoot
--    and a star spark as each locks, and the head spins round to its aim). Flat painted sprites
--    only (the kit's SmokePuff / DustPuff flipbooks, ShockwaveRing, ImpactStar), counts scaled by
--    ClientQuality, every effect bounded by VfxKit.
-- Turrets can't be destroyed (user, 2026-10-04): no health bar or break effects. BUILD went with
-- turret items (2026-10-04): they are placed for you. Nothing shows until the models are installed.
local RunService=game:GetService('RunService')
local RS=game:GetService('ReplicatedStorage')
local combat=RS:WaitForChild('RogueliteCombat')
local H=require(combat:WaitForChild('HandymanTurret'))
local K=require(combat:WaitForChild('VfxKit'))
local Q=require(combat:WaitForChild('ClientQuality'))
local Wire=require(combat:WaitForChild('ShotBatch'))
local T=require(RS:WaitForChild('UITheme'))
local DRAW_RANGE=250
local LIME=T.Color.lime
local FLASH=Color3.fromRGB(255,236,150)
-- Follow effects: painted textures already in the game (BossVfxAssets, as LegendaryVisuals uses
-- them), white on clear, tinted warm grey (the sky light cools greys, so they start warm).
local TEX={Smoke='rbxassetid://133683398795549',Dust='rbxassetid://108391383565832',Ring='rbxassetid://73745779894728',Star='rbxassetid://132900122818559'}
local SMOKE,SMOKE_LIGHT=Color3.fromRGB(150,144,136),Color3.fromRGB(214,206,194)
local SPARK=Color3.fromRGB(255,214,120)
local TURN=10 -- radians a second the head turns toward its aim
local IDLE_STEP=1/20 -- seconds between poses of a turret that hasn't fired for AIM_IDLE

local holder=Instance.new('Folder');holder.Name='RogueliteTurretsLocal';holder.Parent=workspace
local shown={} -- server Folder -> v
local byKey={} -- 'ownerUserId:index' -> v (which turret fired a nail)

local function template(tier) local f=H.templates(combat);return f and f:FindFirstChild('T'..tier) end
local function clear(v) if v.model then v.model:Destroy();v.model=nil end end
-- A local copy of the tier's model, and where its moving parts sit: the head pivot in the base's
-- space, the head part from its pivot, the barrel pivot (its spin axis) from the head pivot, the
-- barrel part from that, and the optional Glow from whichever it follows.
local function make(v)
 clear(v)
 local src=template(v.tier);if not src then return end
 local m=src:Clone()
 for _,d in m:GetDescendants() do if d:IsA('BasePart') then d.Anchored=true;d.CanCollide=false;d.CanTouch=false;d.CanQuery=false end end
 local pivot=m:GetPivot()
 local head,barrel,glow=m:FindFirstChild('Head'),m:FindFirstChild('Barrel'),m:FindFirstChild('Glow')
 local hp,bp=head:GetPivot(),barrel:GetPivot()
 local rel=pivot:ToObjectSpace(hp)
 v.headRel,v.headRot=rel.Position,rel.Rotation
 v.headPart=hp:ToObjectSpace(head.CFrame)
 v.barrelRel=hp:ToObjectSpace(bp)
 v.barrelPart=bp:ToObjectSpace(barrel.CFrame)
 v.glow=glow and glow:IsA('BasePart') and glow or nil
 if v.glow then
  v.glowFollows=v.glow:GetAttribute('Follows')=='Head' and 'Head' or 'Barrel'
  v.glowRel=(v.glowFollows=='Head' and hp or bp):ToObjectSpace(v.glow.CFrame)
 end
 v.muzzles={}
 for i=1,12 do local a=barrel:FindFirstChild('Muzzle'..i);if not (a and a:IsA('Attachment')) then break end;table.insert(v.muzzles,a) end
 v.spins=m:GetAttribute('Spin')==true
 -- Tier IV's barrels spin: it flashes from their centre (MuzzleCentre, in the Barrel's frame).
 local centre=barrel:GetAttribute('MuzzleCentre')
 v.muzzleCentre=v.spins and typeof(centre)=='Vector3' and centre or nil
 v.model,v.head,v.barrel=m,head,barrel
 -- Follow: the Base from the model pivot, each piece's size and the model's height, so pieces
 -- can sink and shrink on their own tracks and come back exactly.
 local basePart=m:FindFirstChild('Base')
 v.basePart=basePart;v.basePartRel=pivot:ToObjectSpace(basePart.CFrame)
 v.sizes={[basePart]=basePart.Size,[head]=head.Size,[barrel]=barrel.Size}
 if v.glow then v.sizes[v.glow]=v.glow.Size end
 v.height=tonumber(m:GetAttribute('Height')) or 4
 v.lifted,v.scaled=false,false
 v.posedAt=nil
 if v.base then m:PivotTo(v.base) end
 m.Parent=not v.hidden and holder or nil -- packed away (following): stays out until it is rebuilt
end
-- A part offset with its position scaled about its parent's origin (shrinking pieces).
local function scaled(cf,s) if s==1 then return cf end;return cf-cf.Position+cf.Position*s end
-- a (follow, optional): {baseSink, baseScale, headSink, headScale, drop, droop, fold, spin} from
-- packPose / buildPose. The Base sinks and shrinks on its own; the head, barrel and glow on another
-- track (drop and droop lower and tip the head, fold tips the barrel down, spin turns the head).
local function pose(v,now,lift,a)
 local base=v.base
 if a then
  v.basePart.CFrame=base*CFrame.new(0,-a.baseSink,0)*scaled(v.basePartRel,a.baseScale)
  v.basePart.Size=v.sizes[v.basePart]*a.baseScale
  v.lifted,v.scaled=true,true
  base=base*CFrame.new(0,-a.headSink-a.drop,0)
 else
  if v.scaled then v.scaled=false;for part,size in v.sizes do part.Size=size end;v.basePart.CFrame=base*v.basePartRel end
  if lift>0 then base=base+Vector3.yAxis*lift;v.model:PivotTo(base);v.lifted=true
  elseif v.lifted then v.model:PivotTo(base);v.lifted=false end
 end
 local hs=a and a.headScale or 1
 local headCF=base*CFrame.new(v.headRel*hs)*CFrame.Angles(0,v.yaw-v.baseYaw+(a and a.spin or 0),0)*v.headRot
 if a and a.droop~=0 then headCF=headCF*CFrame.Angles(-a.droop,0,0) end
 v.head.CFrame=headCF*scaled(v.headPart,hs)
 local age=now-(v.kick or -1)
 local kick=age<.12 and (v.spins and .08 or .22)*(1-age/.12)^2 or 0
 -- The barrel pitches on its trunnion, recoils along +Z and (Tier IV) spins about its Z.
 local barrelCF=headCF*scaled(v.barrelRel,hs)*CFrame.Angles(v.pitch-(a and a.fold or 0),0,0)*CFrame.new(0,0,kick)*CFrame.Angles(0,0,v.spin)
 v.barrel.CFrame=barrelCF*scaled(v.barrelPart,hs)
 v.barrelCF=barrelCF
 if v.glow then v.glow.CFrame=(v.glowFollows=='Head' and headCF or barrelCF)*scaled(v.glowRel,hs) end
 if a then
  v.head.Size=v.sizes[v.head]*hs;v.barrel.Size=v.sizes[v.barrel]*hs
  if v.glow then v.glow.Size=v.sizes[v.glow]*hs end
 end
end
-- Follow poses. u runs 0 -> 1 over PACK_TIME / BUILD_TIME. Packing: the barrel folds down and the
-- head drops onto the base, then the head and (a little later) the base sink and shrink into the
-- ground. Building: the base, then the head, then the barrel come up with an overshoot (backOut),
-- and the head spins one turn into its aim.
local function span(u,a,b) return math.clamp((u-a)/(b-a),0,1) end
local function backOut(x) x=math.clamp(x,0,1)-1;return 1+x*x*(2.7*x+1.7) end
local function packPose(v,u)
 local fold=K.smooth(span(u,0,.45));local head=span(u,.2,1)^2;local body=span(u,.4,1)^2
 return {fold=fold*1.1,droop=fold*.35,drop=fold*.5,headSink=head*v.height,headScale=1-.45*head,baseSink=body*v.height,baseScale=1-.4*body,spin=0}
end
local function buildPose(v,u)
 local body,head,gun=backOut(span(u,.12,.5)),backOut(span(u,.36,.72)),backOut(span(u,.6,.84))
 return {fold=(1-gun)*1.1,droop=0,drop=0,headSink=(1-head)*v.height,headScale=.55+.45*head,baseSink=(1-body)*v.height,baseScale=.6+.4*body,
  spin=(1-K.smooth(span(u,.55,1)))*math.pi*2}
end
-- Placement pop: a flat lime ring on the ground and a puff of dust bits.
local function ring(position)
 if not K.near(position,160) then return end
 K.ring(holder,CFrame.new(position+Vector3.yAxis*.08),{radius0=.6,radius1=3.4,width=.5,color=LIME,duration=.45,segments=18,bodyAlpha=.3})
 K.shards(holder,position+Vector3.yAxis*.3,K.Dust,8,8,.45,.16,Enum.Material.SmoothPlastic,.7)
end
-- Muzzle flash: three short Neon slivers from the muzzle that fired, gone in 0.07 s.
local function flash(v)
 if (#v.muzzles==0 and not v.muzzleCentre) or not v.barrelCF or not K.near(v.base.Position,160) then return end
 local at=v.muzzleCentre and v.barrelCF:PointToWorldSpace(v.muzzleCentre) or v.muzzles[(v.shots-1)%#v.muzzles+1].WorldPosition
 local frame=CFrame.lookAt(at,at+v.barrelCF.LookVector)
 local roll=math.random()*math.pi*2
 local parts={}
 for i=1,3 do parts[i]=K.part(holder,'TurretFlash',Vector3.new(.08,.08,.5),FLASH,0,Enum.Material.Neon) end
 K.animate(.07,function(t)
  for i,p in parts do
   local length=(i==1 and .6 or .4)*(1-t*.5)
   p.Size=Vector3.new(.08*(1-t*.6),.08*(1-t*.6),length)
   p.CFrame=frame*CFrame.Angles(0,0,roll+i*2.09)*CFrame.Angles(i==1 and 0 or math.rad(30),0,0)*CFrame.new(0,0,-length/2)
   p.Transparency=t
  end
 end,function() for _,p in parts do p:Destroy() end end,'turretFlash',24)
end
-- Follow effects (2026-10-10). Each registers its cleanup with VfxKit before building anything that
-- could throw, so nothing outlives its animation.
local function seq(...) local k={};local a={...};for i=1,#a,2 do k[#k+1]=NumberSequenceKeypoint.new(a[i],a[i+1]) end;return NumberSequence.new(k) end
-- Grey smoke puffs (the SmokePuff or DustPuff flipbook) from a ground point, rising and fading.
-- o: count (x ClientQuality), size0/size1, life, speed {lo,hi}, spread (degrees from straight up),
-- rise (upward pull), texture.
local function puffs(position,o)
 if not K.near(position,140) then return end
 local n=math.floor((o.count or 6)*Q.get().effects+.5);if n<1 then return end
 local host=K.part(holder,'TurretSmoke',Vector3.one*.05,K.White,1)
 host.CFrame=CFrame.new(position)*CFrame.Angles(math.pi/2,0,0) -- LookVector straight up
 K.animate((o.life or .8)+.2,function() end,function() host:Destroy() end,'turretSmoke',12)
 local e=Instance.new('ParticleEmitter');e.Name='TurretSmoke';e.Enabled=false
 e.Texture=o.texture or TEX.Smoke
 e.FlipbookLayout=Enum.ParticleFlipbookLayout.Grid4x4;e.FlipbookMode=Enum.ParticleFlipbookMode.OneShot
 e.Color=ColorSequence.new(SMOKE,SMOKE_LIGHT)
 e.Size=seq(0,o.size0 or 1.2,1,o.size1 or 3)
 e.Transparency=seq(0,.12,.55,.35,1,1)
 local life=o.life or .8
 e.Lifetime=NumberRange.new(life*.7,life);e.Speed=NumberRange.new(o.speed[1],o.speed[2])
 e.SpreadAngle=Vector2.new(o.spread or 45,o.spread or 45);e.Drag=3;e.Acceleration=Vector3.yAxis*(o.rise or 2)
 e.Rotation=NumberRange.new(0,360);e.RotSpeed=NumberRange.new(-50,50)
 e.LightEmission=0;e.LightInfluence=.8;e.EmissionDirection=Enum.NormalId.Front
 e.Parent=host
 e:Emit(n)
end
-- A flat painted dust ring (ShockwaveRing) spreading on the ground.
local function dustRing(position,r0,r1,duration)
 if not K.near(position,140) then return end
 local p=K.part(holder,'TurretDustRing',Vector3.new(r0*2,.05,r0*2),K.White,1)
 p.CFrame=CFrame.new(position+Vector3.yAxis*.06)*CFrame.Angles(0,math.random()*6.28,0)
 local d
 K.animate(duration,function(t)
  if not d then return end
  local r=r0+(r1-r0)*(1-(1-t)^3)
  p.Size=Vector3.new(r*2,.05,r*2);d.Transparency=.3+.7*K.smooth((t-.25)/.75)
 end,function() p:Destroy() end,'turretRing',12)
 d=Instance.new('Decal');d.Face=Enum.NormalId.Top;d.Texture=TEX.Ring;d.Color3=SMOKE_LIGHT;d.Transparency=1;d.Parent=p
end
-- A piece locking in: a warm star sprite snapping open and a few flat Neon sparks.
local function spark(position)
 if not K.near(position,120) then return end
 local host=K.part(holder,'TurretSpark',Vector3.one*.05,K.White,1);host.Position=position
 local g,img
 K.animate(.18,function(t)
  if not g then return end
  local s=.5+1.4*(1-(1-t)^3);g.Size=UDim2.fromScale(s,s);img.ImageTransparency=K.smooth((t-.3)/.7)
 end,function() host:Destroy() end,'turretSpark',16)
 g=Instance.new('BillboardGui');g.Size=UDim2.fromScale(.5,.5);g.LightInfluence=0;g.Brightness=1.6;g.MaxDistance=120;g.Parent=host
 img=Instance.new('ImageLabel');img.BackgroundTransparency=1;img.BorderSizePixel=0;img.Size=UDim2.fromScale(1,1)
 img.Image=TEX.Star;img.ImageColor3=SPARK;img.Rotation=math.random(0,44);img.Parent=g
 K.shards(holder,position,SPARK,4,7,.25,.09,Enum.Material.Neon,.9)
end
-- Cues fired once per pack / build, by progress u: smoke and dust at the start, a second puff as
-- the base goes under (pack), a spark as the head and then the barrel lock (build).
local function packCues(v,u)
 local ground=v.base.Position
 if not v.cue.start then
  v.cue.start=true
  dustRing(ground,.8,4.2,.45)
  puffs(ground+Vector3.yAxis*.4,{count=7,size0=1.2,size1=3.2,life=.7,speed={4,8},spread=75,rise=2.5})
 end
 if u>=.55 and not v.cue.under then
  v.cue.under=true
  puffs(ground+Vector3.yAxis*.2,{count=4,size0=1,size1=2.4,life=.55,speed={2,5},spread=50,rise=3,texture=TEX.Dust})
 end
end
local function buildCues(v,u)
 local ground=v.base.Position
 if not v.cue.start then
  v.cue.start=true
  dustRing(ground,.8,3.8,.5)
  puffs(ground+Vector3.yAxis*.2,{count=9,size0=1.4,size1=3.8,life=.9,speed={6,13},spread=18,rise=3}) -- the column
  puffs(ground+Vector3.yAxis*.3,{count=5,size0=1,size1=2.6,life=.6,speed={3,6},spread=85,rise=1.5,texture=TEX.Dust}) -- the skirt
 end
 if u>=.72 and not v.cue.head then v.cue.head=true;spark(v.base:PointToWorldSpace(v.headRel)) end
 if u>=.84 and not v.cue.gun then
  v.cue.gun=true
  if v.barrelCF then spark(v.barrelCF:PointToWorldSpace(Vector3.new(0,0,-1))) end
 end
end

local function attach(f)
 if shown[f] or not f:IsA('Folder') then return end
 local owner=f:GetAttribute('OwnerUserId');local index=f:GetAttribute('Index')
 local v={folder=f,owner=owner,index=tonumber(index) or 0,tier=H.tier(f:GetAttribute('Tier')),spin=0,spinVel=0,shots=0,yaw=0,baseYaw=0,pitch=0}
 shown[f]=v
 if owner and index then v.key=owner..':'..index;byKey[v.key]=v end
 local function place(pop)
  local position=f:GetAttribute('Position');if typeof(position)~='Vector3' then return end
  v.baseYaw=f:GetAttribute('Yaw') or 0;v.yaw=v.baseYaw;v.pitch=0
  v.base=CFrame.new(position)*CFrame.Angles(0,v.baseYaw,0)
  -- Packed away to follow (PackAt): this BuiltAt is the rebuild, so it builds up out of the ground.
  local packed=v.packAt~=nil or v.hidden==true
  v.packAt=nil
  if v.hidden then v.hidden=false;if v.model then v.model.Parent=holder end end
  if not v.model then make(v) elseif not v.lifted then v.model:PivotTo(v.base) end
  v.posedAt=nil
  if packed and pop then v.buildAt=os.clock();v.popAt=nil;v.cue={}
  elseif pop then v.popAt=os.clock();ring(position) end
 end
 f:GetAttributeChangedSignal('BuiltAt'):Connect(function() place(true) end)
 -- Follow: the server packs it up (no fire) before rebuilding it near its owner.
 f:GetAttributeChangedSignal('PackAt'):Connect(function()
  if type(f:GetAttribute('PackAt'))~='number' or v.packAt or v.hidden then return end
  v.packAt=os.clock();v.buildAt=nil;v.popAt=nil;v.cue={}
 end)
 f:GetAttributeChangedSignal('Tier'):Connect(function()
  local tier=H.tier(f:GetAttribute('Tier'));if tier==v.tier then return end
  v.tier=tier;make(v)
 end)
 -- A new turret arrives with BuiltAt already set: drop it in if it was just placed.
 local built=f:GetAttribute('BuiltAt')
 place(type(built)=='number' and workspace:GetServerTimeNow()-built<1)
 -- Seen mid-move (packed away): hidden until its rebuild.
 if type(f:GetAttribute('PackAt'))=='number' then v.hidden=true;v.popAt=nil;if v.model then v.model.Parent=nil end end
end
local function detach(f)
 local v=shown[f];if not v then return end
 shown[f]=nil
 if v.key and byKey[v.key]==v then byKey[v.key]=nil end
 clear(v)
end
local function hook(folder)
 for _,f in folder:GetChildren() do attach(f) end
 folder.ChildAdded:Connect(attach)
 folder.ChildRemoved:Connect(detach)
end
local existing=workspace:FindFirstChild('RogueliteTurrets')
if existing then hook(existing) end
workspace.ChildAdded:Connect(function(c) if c.Name=='RogueliteTurrets' and c:IsA('Folder') then hook(c) end end)

-- Each turret nail: the first Fly row of each projectile key. slotIndex 100 + Index says which of
-- the owner's turrets fired it. Snap its head to it, kick, flash.
local seen,prunedAt={},os.clock()
local function row(origin,finish,kind,id,_,_,_,_,ownerId,slotIndex,_,_,_,key)
 if kind~='Fly' or id~=H.Id or key==nil or seen[key] then return end
 seen[key]=os.clock()
 if type(slotIndex)~='number' then return end
 local v=byKey[tostring(ownerId)..':'..(slotIndex-100)];if not v or not v.base then return end
 if typeof(origin)=='Vector3' and typeof(finish)=='Vector3' then
  local d=finish-origin
  local flat=Vector3.new(d.X,0,d.Z).Magnitude
  if flat>.05 then v.shotYaw=H.yaw(d);v.yaw=v.shotYaw;v.shotPitch=math.clamp(math.atan2(d.Y,flat),-.45,.45);v.pitch=v.shotPitch end
 end
 v.kick=os.clock();v.shots+=1;v.flash=true
end
combat:WaitForChild('Shot').OnClientEvent:Connect(function(a,b,...)
 if a==Wire.Marker then for _,r in ipairs(b) do row(Wire.unpack(r)) end else row(a,b,...) end
 local now=os.clock()
 if now-prunedAt>2 then prunedAt=now;for k,t in seen do if now-t>2 then seen[k]=nil end end end
end)

RunService.RenderStepped:Connect(function(dt)
 local now=os.clock()
 -- A paused run (RunPaused) freezes the turrets as they are: no turning, spin or idle look-around.
 if combat:GetAttribute('RunPaused')==true then return end
 local camera=workspace.CurrentCamera;local eye=camera and camera.CFrame.Position
 for f,v in shown do
  -- Follow: a finished pack stays out of sight until the rebuild's BuiltAt; a finished build ends
  -- (the pose below then puts every piece back at full size).
  if v.packAt and now-v.packAt>=H.PACK_TIME then v.packAt=nil;v.hidden=true;if v.model then v.model.Parent=nil end end
  if v.buildAt and now-v.buildAt>=H.BUILD_TIME then v.buildAt=nil end
  if v.hidden or not v.model or not v.base then continue end
  if eye and (eye-v.base.Position).Magnitude>DRAW_RANGE then continue end
  local busy=now-(v.kick or -1)<H.AIM_IDLE or v.popAt~=nil or v.spinVel>.05 or v.packAt~=nil or v.buildAt~=nil or v.scaled
  local step=dt
  if not busy then
   -- Idle: the slow look-around at 20 Hz, with the time since its last pose.
   if v.posedAt and now-v.posedAt<IDLE_STEP then continue end
   step=v.posedAt and math.min(now-v.posedAt,.25) or dt
  end
  v.posedAt=now
  -- Head: hold a fired nail's heading a moment, else follow Aim; idle, a slow look around.
  -- The barrel pitches toward its target (up to 26 degrees), level when idle.
  local target,pitch=nil,0
  if v.shotYaw and now-(v.kick or -1)<.15 then target,pitch=v.shotYaw,v.shotPitch or 0
  else
   local aim=f:GetAttribute('Aim')
   if typeof(aim)=='Vector3' then
    local d=aim-v.base:PointToWorldSpace(v.headRel)
    local flat=Vector3.new(d.X,0,d.Z).Magnitude
    if flat>.05 then target=H.yaw(d);pitch=math.clamp(math.atan2(d.Y-1,flat),-.45,.45) end
   end
   target=target or v.baseYaw+math.sin(now*.7+v.index*1.3)*.45 -- each turret out of step
  end
  local diff=(target-v.yaw+math.pi)%(2*math.pi)-math.pi
  v.yaw+=math.clamp(diff,-TURN*step,TURN*step)
  v.pitch+=math.clamp(pitch-v.pitch,-3*step,3*step)
  -- Tier IV: the barrel cluster spins up while it fires and winds down after.
  if v.spins then
   local want=now-(v.kick or -1)<.4 and 22 or 0
   v.spinVel+=(want-v.spinVel)*math.min(1,step*4)
   if v.spinVel<.05 and want==0 then v.spinVel=0 end
   v.spin=(v.spin+v.spinVel*step)%(math.pi*2)
  end
  local lift=0
  if v.popAt then local t=(now-v.popAt)/.24;if t<1 then lift=2.4*(1-t)^2 else v.popAt=nil end end
  local anim
  if v.packAt then local u=(now-v.packAt)/H.PACK_TIME;anim=packPose(v,u);packCues(v,u)
  elseif v.buildAt then anim=buildPose(v,(now-v.buildAt)/H.BUILD_TIME) end
  pose(v,now,lift,anim)
  if v.buildAt then buildCues(v,(now-v.buildAt)/H.BUILD_TIME) end -- after the pose: barrelCF is current
  if v.flash then v.flash=false;flash(v) end
 end
end)

-- Turrets whose model wasn't there to clone yet (installed while running in Studio).
local waited=0
RunService.Heartbeat:Connect(function(dt)
 waited+=dt;if waited<1 then return end;waited=0
 for _,v in shown do if not v.model and v.base and template(v.tier) then make(v) end end
end)
