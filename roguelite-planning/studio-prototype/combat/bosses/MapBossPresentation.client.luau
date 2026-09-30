-- Client: map-boss animation, ground warnings and effects (plan F). Follows the Hammer
-- BossPresentation: sampled Bone.Transform clips with priority Death > attack > Hit > Walk/Idle,
-- and warnings drawn from the server's MapBossAttackData through MapBossShapes, the same shapes
-- the server hit-tests. Effects come from BossVfx/<BossId>. Visual only.
local Tags=game:GetService('CollectionService')
local Run=game:GetService('RunService')
local Players=game:GetService('Players')
local Http=game:GetService('HttpService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local EnemyMotion=require(combat:WaitForChild('EnemyMotion'))
local Shapes=require(combat:WaitForChild('MapBossShapes'))
local Defs=require(combat:WaitForChild('MapBossDefs'))
local animations=combat:WaitForChild('BossAnimations')
local vfxFolder=combat:WaitForChild('BossVfx')
local Common=require(vfxFolder:WaitForChild('Common'))
local player=Players.LocalPlayer
local MAX_GAIT_RATE=1.8 -- Walk clip seconds per real second
local FILL,EDGE=.78,.2
local TINT={KingCrab=Color3.fromRGB(255,120,90),Pharaoh=Color3.fromRGB(255,200,80),FrostCyclops=Color3.fromRGB(140,220,255),Dragon=Color3.fromRGB(255,110,40)}
local tracked,compiled,modules={},{},{}
local function decode(raw) local ok,t=pcall(Http.JSONDecode,Http,raw or '');return ok and type(t)=='table' and t or {} end
local function clipDuration(motion,name) local c=motion.clips[name];return c and c.duration or 1 end
-- EnemyMotion.compile asserts Idle, Move and Attack: alias Walk -> Move and the first attack -> Attack.
local function load(anim)
 if compiled[anim]~=nil then return compiled[anim] or nil end
 local source=animations:FindFirstChild(anim);if not source then return nil end
 local ok,result=pcall(function()
  local raw=require(source);local data=table.clone(raw);data.clips=table.clone(raw.clips)
  data.clips.Move=data.clips.Move or data.clips.Walk;data.clips.Attack=data.clips.Attack or data.clips[Defs.ATTACK_CLIPS[anim][1]]
  return EnemyMotion.compile(data)
 end)
 if not ok then warn('MapBossPresentation: '..anim..' animations failed: '..tostring(result)) end
 compiled[anim]=ok and result or false;return compiled[anim] or nil
end
local function vfxFor(id)
 if modules[id]==nil then
  local m=vfxFolder:FindFirstChild(id);local ok,r=true,Common
  if m then ok,r=pcall(require,m) end
  if not ok then warn('MapBossPresentation: BossVfx.'..id..' failed: '..tostring(r)) end
  modules[id]=ok and r or Common
 end
 return modules[id]
end
-- Effects never break the boss: every hook runs protected.
local function call(state,name,...)
 local f=state.vfx[name] or Common[name];if not f then return end
 local r=table.pack(pcall(f,...))
 if not r[1] then warn('BossVfx.'..state.id..'.'..name..': '..tostring(r[2]));return end
 return table.unpack(r,2,r.n)
end
-- Same windows as MapBossService: the rush is RushStart, travel at speed, then RushEnd.
local function window(a,T,length)
 if not a.clips then return T.attacks and T.attacks[a.clip] end
 local rs,re=T.clips[a.clips[1]] or 0,T.clips[a.clips[3]] or 0;local move=(length or a.length)/a.speed
 return {warnStart=0,impact=rs,activeEnd=rs+move,recoveryEnd=rs+move+re,duration=rs+move+re}
end
local function context(npc,state,kind,a,start,serial)
 local cf=npc:GetAttribute('BossFrame');if typeof(cf)~='CFrame' then return nil end
 local T=state.T;local raw=npc:GetAttribute('MapBossAttackData');local data=decode(raw)
 local ctx={npc=npc,id=state.id,kind=kind,def=a,serial=serial,start=start,cf=cf,groundY=npc:GetAttribute('BossGroundY') or cf.Y-T.rootHeight,
  timing=T,tint=state.tint,raw=raw,data=data,ground=cf*CFrame.new(0,-T.rootHeight,0)}
 local at=window(a,T,data.length);if not at then return nil end
 ctx.attack=at
 function ctx.points(name,t)
  local p=Shapes.sample(at.samples and at.samples[name],t)
  if not p then local fixed=at.points and at.points[name];p=fixed and Vector3.new(table.unpack(fixed.rootAtImpactStudio)) or Vector3.zero end
  return ctx.ground*p
 end
 function ctx.dirAt(name,t)
  local d=Shapes.sample(at.dirs and at.dirs[name],t) or (at.directionAtImpactStudio and Vector3.new(table.unpack(at.directionAtImpactStudio)))
  return d and d.Magnitude>1e-3 and ctx.ground:VectorToWorldSpace(d).Unit or cf.LookVector
 end
 return ctx
end
local function attackClip(ctx,age,motion)
 local a,at=ctx.def,ctx.attack
 if a.shape~='lane' then return a.clip,age end
 if age<at.impact then return a.clips[1],age end
 if age<at.activeEnd then
  -- Loop phase follows the ground covered: one rushStrideLength per RushLoop cycle.
  local travelled=(age-at.impact)*a.speed
  return a.clips[2],travelled/(ctx.timing.rushStrideLength or 2.2)*clipDuration(motion,a.clips[2])
 end
 return a.clips[3],age-at.activeEnd
end

-- Ground warnings: a translucent tinted fill and bright edge segments (the Hammer's parts).
local function slab(w,name,size,cf,tint,transparency,fill)
 local p=Instance.new('Part');p.Name=name;p.Size=size;p.CFrame=cf;p.Anchored=true;p.CanCollide=false;p.CanQuery=false;p.CanTouch=false;p.CastShadow=false
 p.Material=Enum.Material.Neon;p.Color=tint;p.Transparency=transparency;p.Parent=w.folder
 if fill then table.insert(w.fills,p) end
 return p
end
local function drawShape(w,shape,y,tint)
 local function flat(v) return Vector3.new(v.X,y,v.Z) end
 if shape.kind=='circle' then
  local p=slab(w,'WarningFill',Vector3.new(.045,shape.radius*2,shape.radius*2),CFrame.new(flat(shape.center))*CFrame.Angles(0,0,math.pi/2),tint,FILL,true);p.Shape=Enum.PartType.Cylinder
 elseif shape.kind=='line' then
  local mid=flat(shape.origin+shape.direction*shape.length/2)
  slab(w,'WarningFill',Vector3.new(shape.width,.045,shape.length),CFrame.lookAt(mid,mid+shape.direction),tint,FILL,true)
 elseif shape.kind=='cone' or shape.kind=='arc' then
  -- Polar ribbon: angular sectors split into radial bands, each strip as wide as its outer edge.
  local pivot=flat(shape.origin or shape.pivot);local forward=shape.direction or shape.forward
  local from,to=shape.from or -shape.halfAngle,shape.to or shape.halfAngle;local inner,outer=shape.inner or 0,shape.outer or shape.length
  local n=math.max(4,math.ceil((to-from)/math.rad(6)));local bands=math.clamp(math.ceil((outer-inner)/7),1,3);local step=(to-from)/n
  for i=0,n-1 do
   local d=CFrame.Angles(0,from+step*(i+.5),0):VectorToWorldSpace(forward)
   for b=0,bands-1 do
    local r0,r1=inner+(outer-inner)*b/bands,inner+(outer-inner)*(b+1)/bands;local p=pivot+d*(r0+r1)/2
    slab(w,'WarningFill',Vector3.new(math.max(.05,r1*math.abs(step)*1.02),.045,r1-r0),CFrame.lookAt(p,p+d),tint,FILL,true)
   end
  end
 end
 local pts=Shapes.outline(shape,48)
 for i=1,#pts do
  local a,b=flat(pts[i]),flat(pts[i%#pts+1]);local len=(b-a).Magnitude
  if len>.01 then local m=(a+b)/2+Vector3.yAxis*.025;slab(w,'WarningEdge',Vector3.new(.14,.05,len+.06),CFrame.lookAt(m,b+Vector3.yAxis*.025),tint,EDGE,false) end
 end
end
local function buildWarning(ctx)
 local w={folder=Instance.new('Folder'),fills={},raw=ctx.raw,serial=ctx.serial};w.folder.Name='BossWarning';w.folder.Parent=workspace
 local tint=ctx.tint or Color3.fromRGB(224,45,49)
 if ctx.def.shape=='targets' then
  for _,p in ctx.data.points or {} do drawShape(w,{kind='circle',center=Vector3.new(p[1],p[2],p[3]),radius=ctx.def.radius},p[2]+.07,tint) end
 elseif ctx.data.shape then drawShape(w,Shapes.decode(ctx.data.shape),ctx.groundY+.07,tint) end
 return w
end

-- Projectiles: the server's shots replayed from origin, yaws, speed and life (MapBossShapes.shot),
-- stopping where MapBossShotEnds says the server stopped them.
local function launch(state,ctx)
 local d=ctx.data;if not d.yaws or not d.origin then return end
 local B={ctx=ctx,born=ctx.start+ctx.attack.impact,origin=Vector3.new(d.origin[1],d.origin[2],d.origin[3]),list={}}
 for i,yaw in d.yaws do local part,update,finish=call(state,'projectile',ctx,i);table.insert(B.list,{i=i,yaw=yaw,part=part,update=update,finish=finish}) end
 state.shots=state.shots or {};table.insert(state.shots,B)
end
local function stepShots(npc,state,now,dt)
 if not state.shots then return end
 local raw=npc:GetAttribute('MapBossShotEnds');if raw~=state.endsRaw then state.endsRaw=raw;state.ends=decode(raw) end
 for bi=#state.shots,1,-1 do
  local B=state.shots[bi];local d=B.ctx.data;local latest=bi==#state.shots;local alive=false
  for _,s in B.list do
   if s.done then continue end
   local stop=math.min(B.born+d.life,latest and state.ends and state.ends[tostring(s.i)] or math.huge)
   local pos,dir=Shapes.shot(B.origin,s.yaw,d.speed,d.height,math.max(0,math.min(now,stop)-B.born))
   if s.part then s.part.CFrame=CFrame.lookAt(pos,pos+dir) end
   if s.update then pcall(s.update,dt) end
   if now>=stop then
    s.done=true;if s.finish then pcall(s.finish,pos) end;if s.part then s.part:Destroy() end
   else alive=true end
  end
  if not alive then table.remove(state.shots,bi) end
 end
end
local function clear(state)
 if state.warning then state.warning.folder:Destroy();state.warning=nil end
 for _,B in state.shots or {} do for _,s in B.list do if s.part then s.part:Destroy() end end end;state.shots=nil
end

local function track(npc)
 if tracked[npc] then return end
 local state={phase=0};tracked[npc]=state
 task.spawn(function()
  local id=npc:GetAttribute('MapBossId');local def=id and Defs.get(id);local T=id and Defs.timing(id)
  if not def or not T then return end
  -- The animation modules are large; wait for them to replicate.
  local motion;for _=1,40 do motion=load(def.anim);if motion or compiled[def.anim]==false or tracked[npc]~=state then break end;task.wait(.5) end
  if not motion or tracked[npc]~=state then return end
  state.id,state.def,state.T,state.tint,state.vfx,state.joints=id,def,T,TINT[id],vfxFor(id),EnemyMotion.bind(npc)
  state.motion=motion
 end)
end
Tags:GetInstanceAddedSignal('MapBoss'):Connect(track)
for _,npc in Tags:GetTagged('MapBoss') do track(npc) end

local function frame(npc,state,now,dt)
 local h=npc:FindFirstChildOfClass('Humanoid');local root=npc.PrimaryPart;if not h or not root then return end
 if not next(state.joints) then state.joints=EnemyMotion.bind(npc) end
 local motion,T=state.motion,state.T
 local displacement=state.previousPosition and root.Position-state.previousPosition or Vector3.zero
 state.previousPosition=root.Position
 local distance=Vector2.new(displacement.X,displacement.Z).Magnitude
 local start=npc:GetAttribute('BossStart');local kind=npc:GetAttribute('BossAttack');local a=kind and state.def.attacks[kind];local age=start and now-start
 local serial=npc:GetAttribute('BossSerial') or 0
 if a and start and serial~=(state.ctx and state.ctx.serial) then state.ctx=context(npc,state,kind,a,start,serial) end
 local ctx=state.ctx
 if ctx then local raw=npc:GetAttribute('MapBossAttackData');if raw~=ctx.raw then ctx.raw=raw;ctx.data=decode(raw) end end
 local death=npc:GetAttribute('BossDeathStart');local hit=npc:GetAttribute('BossHitStart')
 local attacking=ctx and ctx.serial==serial and npc:GetAttribute('Attacking') and age and age>=0 and age<=(npc:GetAttribute('BossDuration') or ctx.attack.duration)
 local clip,time
 if death then clip,time='Death',now-death
 elseif attacking then clip,time=attackClip(ctx,age,motion)
 elseif hit and now-hit<clipDuration(motion,'Hit') then clip,time='Hit',now-hit
 else
  local v=root.AssemblyLinearVelocity;local moving=Vector2.new(v.X,v.Z).Magnitude>.4
  clip=moving and 'Walk' or 'Idle'
  -- Ground distance, not elapsed time, advances the planted-foot gait; cadence capped.
  state.phase+=moving and math.min(distance/(T.strideLength or 4)*clipDuration(motion,'Walk'),dt*MAX_GAIT_RATE) or dt
  time=state.phase%clipDuration(motion,clip)
 end
 local poses=EnemyMotion.sample(motion,clip,time)
 if state.lastClip~=clip and state.lastPose and clip~='Death' then state.blendFrom=state.lastPose;state.blendStart=now end
 if state.blendFrom then
  local weight=math.clamp((now-state.blendStart)/((clip=='Walk' or clip=='Idle') and .16 or .12),0,1)
  poses=EnemyMotion.blend(state.blendFrom,poses,weight)
  if weight==1 then state.blendFrom=nil end
 end
 state.lastPose=poses;state.lastClip=clip
 local baseline=npc:GetAttribute('EnemyBaselineModelScale')
 EnemyMotion.apply(state.joints,baseline and EnemyMotion.scalePose(poses,npc:GetScale()/baseline) or poses)
 -- Warnings: warnStart to impact (tombs: to their eruption), brightening over the last 0.25 s.
 local at=ctx and ctx.attack
 local warnEnd=at and (ctx.def.shape=='targets' and at.impact+ctx.def.eruptDelay or at.impact)
 if not death and attacking and age>=at.warnStart and age<warnEnd then
  local w=state.warning
  if not w or w.serial~=ctx.serial or w.raw~=ctx.raw then if w then w.folder:Destroy() end;w=buildWarning(ctx);state.warning=w end
  local fill=.55+(FILL-.55)*math.clamp((warnEnd-age)/.25,0,1)
  for _,p in w.fills do p.Transparency=fill end
 elseif state.warning then state.warning.folder:Destroy();state.warning=nil end
 -- Effects: windup once at warnStart, impact once at impact, active every frame in the active window.
 if attacking and not death then
  if not ctx.woundUp and age>=at.warnStart then ctx.woundUp=true;if age<at.impact then call(state,'windup',ctx) end end
  if not ctx.impacted and age>=at.impact then
   ctx.impacted=true;if age<math.max(at.activeEnd,at.impact+.5) then call(state,'impact',ctx) end
   if ctx.def.shape=='projectiles' then launch(state,ctx) end
  end
  if age>=at.impact and age<at.activeEnd then call(state,'active',ctx,age) end
 end
 stepShots(npc,state,now,dt)
end
Run.PreSimulation:Connect(function(dt)
 local now=workspace:GetServerTimeNow()
 for npc,state in tracked do
  if not npc.Parent or not Tags:HasTag(npc,'MapBoss') then clear(state);tracked[npc]=nil;continue end
  if not state.motion then continue end
  local ok,err=pcall(frame,npc,state,now,dt)
  if not ok and not state.warned then state.warned=true;warn('MapBossPresentation: '..tostring(err)) end
 end
end)

-- Knockdown (GroundSlam, FrontStomp): a short fall, thrown away from the impact.
task.spawn(function()
 local knock=combat:WaitForChild('MapBossKnockdown') -- MapBossService creates it on the server
 local token
 knock.OnClientEvent:Connect(function(source,seconds)
  if typeof(source)~='Vector3' or type(seconds)~='number' or seconds~=seconds then return end
  local ch=player.Character;local h=ch and ch:FindFirstChildOfClass('Humanoid');local root=ch and ch:FindFirstChild('HumanoidRootPart')
  if not h or not root or h.Health<=0 then return end
  local away=Shapes.flat(root.Position-source);if away.Magnitude<.1 then away=Shapes.flat(-root.CFrame.LookVector) end
  local mine={};token=mine
  h.PlatformStand=true;root.AssemblyLinearVelocity=away.Unit*28+Vector3.yAxis*22
  task.delay(math.clamp(seconds,0,2),function() if token==mine and h.Parent then h.PlatformStand=false end end)
 end)
end)
