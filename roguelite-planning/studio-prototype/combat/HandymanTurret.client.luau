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
-- Turrets can't be destroyed (user, 2026-10-04): no health bar or break effects. BUILD went with
-- turret items (2026-10-04): they are placed for you. Nothing shows until the models are installed.
local RunService=game:GetService('RunService')
local RS=game:GetService('ReplicatedStorage')
local combat=RS:WaitForChild('RogueliteCombat')
local H=require(combat:WaitForChild('HandymanTurret'))
local K=require(combat:WaitForChild('VfxKit'))
local Wire=require(combat:WaitForChild('ShotBatch'))
local T=require(RS:WaitForChild('UITheme'))
local DRAW_RANGE=250
local LIME=T.Color.lime
local FLASH=Color3.fromRGB(255,236,150)
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
 v.posedAt=nil
 if v.base then m:PivotTo(v.base) end
 m.Parent=holder
end
local function pose(v,now,lift)
 local base=v.base
 if lift>0 then base=base+Vector3.yAxis*lift;v.model:PivotTo(base);v.lifted=true
 elseif v.lifted then v.model:PivotTo(base);v.lifted=false end
 local headCF=base*CFrame.new(v.headRel)*CFrame.Angles(0,v.yaw-v.baseYaw,0)*v.headRot
 v.head.CFrame=headCF*v.headPart
 local age=now-(v.kick or -1)
 local kick=age<.12 and (v.spins and .08 or .22)*(1-age/.12)^2 or 0
 -- The barrel pitches on its trunnion, recoils along +Z and (Tier IV) spins about its Z.
 local barrelCF=headCF*v.barrelRel*CFrame.Angles(v.pitch,0,0)*CFrame.new(0,0,kick)*CFrame.Angles(0,0,v.spin)
 v.barrel.CFrame=barrelCF*v.barrelPart
 v.barrelCF=barrelCF
 if v.glow then v.glow.CFrame=(v.glowFollows=='Head' and headCF or barrelCF)*v.glowRel end
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
  if not v.model then make(v) elseif not v.lifted then v.model:PivotTo(v.base) end
  v.posedAt=nil
  if pop then v.popAt=os.clock();ring(position) end
 end
 f:GetAttributeChangedSignal('BuiltAt'):Connect(function() place(true) end)
 f:GetAttributeChangedSignal('Tier'):Connect(function()
  local tier=H.tier(f:GetAttribute('Tier'));if tier==v.tier then return end
  v.tier=tier;make(v)
 end)
 -- A new turret arrives with BuiltAt already set: drop it in if it was just placed.
 local built=f:GetAttribute('BuiltAt')
 place(type(built)=='number' and workspace:GetServerTimeNow()-built<1)
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
  if not v.model or not v.base then continue end
  if eye and (eye-v.base.Position).Magnitude>DRAW_RANGE then continue end
  local busy=now-(v.kick or -1)<H.AIM_IDLE or v.popAt~=nil or v.spinVel>.05
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
  pose(v,now,lift)
  if v.flash then v.flash=false;flash(v) end
 end
end)

-- Turrets whose model wasn't there to clone yet (installed while running in Studio).
local waited=0
RunService.Heartbeat:Connect(function(dt)
 waited+=dt;if waited<1 then return end;waited=0
 for _,v in shown do if not v.model and v.base and template(v.tier) then make(v) end end
end)
