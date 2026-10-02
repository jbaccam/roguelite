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
local Maps=require(combat:WaitForChild('MapConfig'))
local animations=combat:WaitForChild('BossAnimations')
local vfxFolder=combat:WaitForChild('BossVfx')
local Common=require(vfxFolder:WaitForChild('Common'))
local player=Players.LocalPlayer
local MAX_GAIT_RATE=2.6 -- Walk clip seconds per real second (chase speeds outrun the authored walk)
local FILL,EDGE=.78,.2
local TINT={KingCrab=Color3.fromRGB(255,120,90),Pharaoh=Color3.fromRGB(255,200,80),FrostCyclops=Color3.fromRGB(140,220,255),Dragon=Color3.fromRGB(255,110,40)}
local tracked,compiled,modules={},{},{}
local function decode(raw) local ok,t=pcall(Http.JSONDecode,Http,raw or '');return ok and type(t)=='table' and t or {} end
local function clipDuration(motion,name) local c=motion.clips[name];return c and c.duration or 1 end
-- EnemyMotion.compile asserts Idle, Move and Attack: alias Walk -> Move and the first attack -> Attack.
-- compile builds a clip listed under two names once and shares the result.
local function aliased(anim,source)
 local raw=require(source);local data=table.clone(raw);data.clips=table.clone(raw.clips)
 data.clips.Move=data.clips.Move or data.clips.Walk;data.clips.Attack=data.clips.Attack or data.clips[Defs.ATTACK_CLIPS[anim][1]]
 return data
end
local function load(anim)
 if compiled[anim]~=nil then return compiled[anim] or nil end
 local source=animations:FindFirstChild(anim);if not source then return nil end
 local ok,result=pcall(function() return EnemyMotion.compile(aliased(anim,source)) end)
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
-- MicroProfiler labels (DEVICE_PROFILING.md): a throwing body still closes its label.
local function profiled(label,f,...)
 debug.profilebegin(label)
 local r=table.pack(pcall(f,...))
 debug.profileend()
 if not r[1] then error(r[2],0) end
 return table.unpack(r,2,r.n)
end
local vfxLabels=setmetatable({},{__index=function(t,name) local label='Boss:Vfx:'..name;t[name]=label;return label end})
-- Effects never break the boss: every hook runs protected.
local function call(state,name,...)
 local f=state.vfx[name] or Common[name];if not f then return end
 debug.profilebegin(vfxLabels[name])
 local r=table.pack(pcall(f,...))
 debug.profileend()
 if not r[1] then warn('BossVfx.'..state.id..'.'..name..': '..tostring(r[2]));return end
 return table.unpack(r,2,r.n)
end
-- Same windows as MapBossService: the rush is RushStart, travel at speed, then RushEnd. The timing
-- from MapBossDefs.timing is already scaled and rate-adjusted (real seconds, final studs).
local function window(a,T,length)
 if not a.clips then return T.attacks and T.attacks[a.clip] end
 local rate=a.rate or 1;local rs,re=(T.clips[a.clips[1]] or 0)/rate,(T.clips[a.clips[3]] or 0)/rate;local move=(length or a.length)/a.speed
 return {warnStart=0,impact=rs,activeEnd=rs+move,recoveryEnd=rs+move+re,duration=rs+move+re}
end
local function context(npc,state,kind,a,start,serial)
 local cf=npc:GetAttribute('BossFrame');if typeof(cf)~='CFrame' then return nil end
 local T=state.T;local raw=npc:GetAttribute('MapBossAttackData');local data=decode(raw)
 local ctx={npc=npc,id=state.id,kind=kind,def=a,serial=serial,start=start,cf=cf,groundY=npc:GetAttribute('BossGroundY') or cf.Y-T.rootHeight,
  timing=T,tint=state.tint,raw=raw,data=data,ground=cf*CFrame.new(0,-T.rootHeight,0),scale=T.scale or 1,enraged=npc:GetAttribute('BossEnraged')~=nil}
 local at=window(a,T,data.length);if not at then return nil end
 ctx.attack=at
 function ctx.points(name,t)
  local p=Shapes.sample(at.samples and at.samples[name],t)
  if not p then local fixed=at.points and at.points[name];p=fixed and Vector3.new(table.unpack(fixed.rootAtImpactStudio)) or Vector3.zero end
  return ctx.ground*p
 end
 function ctx.dirAt(name,t)
  local d=Shapes.sample(at.dirs and at.dirs[name],t) or (at.directionAtImpactStudio and Vector3.new(table.unpack(at.directionAtImpactStudio)))
  return d and d.Magnitude>1e-3 and ctx.ground:VectorToWorldSpace(d).Unit or ctx.cf.LookVector
 end
 return ctx
end
-- Clip time for an attack at `age` real seconds: the clip plays at the attack's rate.
local function attackClip(ctx,age,motion)
 local a,at=ctx.def,ctx.attack;local rate=a.rate or 1
 if a.shape~='lane' then return a.clip,age*rate end
 if age<at.impact then return a.clips[1],age*rate end
 if age<at.activeEnd then
  -- Loop phase follows the ground covered: one rushStrideLength per RushLoop cycle.
  local travelled=(age-at.impact)*a.speed
  return a.clips[2],travelled/(ctx.timing.rushStrideLength or 2.2)*clipDuration(motion,a.clips[2])
 end
 return a.clips[3],(age-at.activeEnd)*rate
end

-- Ground warnings, three layers per shape: a faint zone fill, a bright edge, and a hotter inner
-- fill that grows out to the edge exactly at impact (circles and cones from their centre, lines
-- from their origin), so the timing reads at a glance. The edge flickers in the last 0.3 s.
local GROW_FILL,EDGE_WIDTH=.42,.24
-- Released warning parts wait unparented for the next cast instead of being rebuilt: a
-- FireBreath warning is ~115 parts. slab resets every property a warning changes.
local pool,POOL_MAX={},256
local function slab(w,name,size,cf,tint,transparency,list)
 local p=table.remove(pool)
 if not p then p=Instance.new('Part');p.Anchored=true;p.CanCollide=false;p.CanQuery=false;p.CanTouch=false;p.CastShadow=false;p.Material=Enum.Material.Neon end
 p.Name=name;p.Shape=Enum.PartType.Block;p.Size=size;p.CFrame=cf
 p.Color=tint;p.Transparency=transparency;p.Parent=w.folder
 table.insert(w.parts,p)
 if list then table.insert(list,p) end
 return p
end
local function release(w)
 for _,p in w.parts do
  -- Only parts still in the folder: one destroyed elsewhere can't be parented again.
  if p.Parent==w.folder and #pool<POOL_MAX then p.Parent=nil;table.insert(pool,p) else p:Destroy() end
 end
 table.clear(w.parts);w.folder:Destroy()
end
-- Fill geometry for one shape into `list`; `grow` also records how each part scales.
local function fillShape(w,shape,y,tint,transparency,list,grow)
 local function flat(v) return Vector3.new(v.X,y,v.Z) end
 if shape.kind=='circle' then
  local c=flat(shape.center);local p=slab(w,'WarningFill',Vector3.new(.045,shape.radius*2,shape.radius*2),CFrame.new(c)*CFrame.Angles(0,0,math.pi/2),tint,transparency,list);p.Shape=Enum.PartType.Cylinder
  if grow then table.insert(grow,{part=p,mode='disc',cf=p.CFrame,size=p.Size}) end
 elseif shape.kind=='line' then
  local o=flat(shape.origin);local mid=o+shape.direction*shape.length/2
  local p=slab(w,'WarningFill',Vector3.new(shape.width,.045,shape.length),CFrame.lookAt(mid,mid+shape.direction),tint,transparency,list)
  if grow then table.insert(grow,{part=p,mode='along',origin=o,dir=shape.direction,size=p.Size}) end
 elseif shape.kind=='cone' or shape.kind=='arc' then
  -- Polar ribbon: angular sectors split into radial bands, each strip as wide as its outer edge.
  local pivot=flat(shape.origin or shape.pivot);local forward=shape.direction or shape.forward
  local from,to=shape.from or -shape.halfAngle,shape.to or shape.halfAngle;local inner,outer=shape.inner or 0,shape.outer or shape.length
  local n=math.max(4,math.ceil((to-from)/math.rad(6)));local bands=math.clamp(math.ceil((outer-inner)/7),1,4);local step=(to-from)/n
  for i=0,n-1 do
   local d=CFrame.Angles(0,from+step*(i+.5),0):VectorToWorldSpace(forward)
   for b=0,bands-1 do
    local r0,r1=inner+(outer-inner)*b/bands,inner+(outer-inner)*(b+1)/bands;local p=pivot+d*(r0+r1)/2
    local part=slab(w,'WarningFill',Vector3.new(math.max(.05,r1*math.abs(step)*1.02),.045,r1-r0),CFrame.lookAt(p,p+d),tint,transparency,list)
    if grow then table.insert(grow,{part=part,mode='radial',pivot=pivot,cf=part.CFrame,size=part.Size}) end
   end
  end
 end
end
local function edgeShape(w,shape,y,tint)
 local function flat(v) return Vector3.new(v.X,y,v.Z) end
 local pts=Shapes.outline(shape,48)
 for i=1,#pts do
  local a,b=flat(pts[i]),flat(pts[i%#pts+1]);local len=(b-a).Magnitude
  if len>.01 then local m=(a+b)/2+Vector3.yAxis*.03;slab(w,'WarningEdge',Vector3.new(EDGE_WIDTH,.06,len+.1),CFrame.lookAt(m,b+Vector3.yAxis*.03),tint,EDGE,w.edges) end
 end
end
local function drawShape(w,shape,y,tint,noGrow)
 fillShape(w,shape,y,tint,FILL,w.fills)
 if not noGrow then fillShape(w,shape,y+.02,tint,1,w.growParts,w.grow) end
 edgeShape(w,shape,y,tint)
end
local function newWarning(serial,raw)
 local w={folder=Instance.new('Folder'),parts={},fills={},edges={},grow={},growParts={},raw=raw,serial=serial};w.folder.Name='BossWarning';w.folder.Parent=workspace
 return w
end
local function buildWarning(ctx)
 local w=newWarning(ctx.serial,ctx.raw)
 local tint=ctx.tint or Color3.fromRGB(224,45,49);local d=ctx.data
 if ctx.def.shape=='targets' then
  for _,p in d.points or {} do drawShape(w,{kind='circle',center=Vector3.new(p[1],p[2],p[3]),radius=ctx.def.radius},p[2]+.07,tint) end
 elseif ctx.def.shape=='projectiles' then
  -- One narrow lane per shot along its level flight, no grow layer: where the volley will go.
  if d.origin and d.yaws then
   local o=Vector3.new(d.origin[1],ctx.groundY,d.origin[3]);local len=math.min((d.speed or 20)*(d.life or 2),38);local width=(d.radius or 1)*2
   for _,yaw in d.yaws do fillShape(w,{kind='line',origin=o,direction=CFrame.Angles(0,yaw,0).LookVector,length=len,width=width},ctx.groundY+.07,tint,.8,w.fills) end
  end
 elseif d.lines then
  for _,line in d.lines do drawShape(w,Shapes.decode(line),ctx.groundY+.07,tint) end
 elseif d.shape then drawShape(w,Shapes.decode(d.shape),ctx.groundY+.07,tint) end
 return w
end
-- k: 0 when the warning appears, 1 at impact. left: seconds to impact.
-- Each layer is only rewritten when its value moved (the edge holds still until the flicker).
local function paintWarning(w,k,left,now)
 debug.profilebegin('Boss:PaintWarning')
 k=math.clamp(k,0,1)
 local e=1-(1-k)^1.6 -- fast start, easing into the edge
 if e~=w.e then
  w.e=e
  for _,g in w.grow do
   local p=g.part
   if g.mode=='disc' then p.Size=Vector3.new(g.size.X,g.size.Y*e,g.size.Z*e)
   elseif g.mode=='along' then local len=g.size.Z*e;local mid=g.origin+g.dir*len/2+Vector3.yAxis*.02;p.Size=Vector3.new(g.size.X,g.size.Y,math.max(.05,len));p.CFrame=CFrame.lookAt(mid,mid+g.dir)
   else p.Size=Vector3.new(g.size.X*e,g.size.Y,g.size.Z*e);p.CFrame=CFrame.new(g.pivot+(g.cf.Position-g.pivot)*e)*g.cf.Rotation end
  end
 end
 local grow=e<.02 and 1 or GROW_FILL-.12*k
 if grow~=w.growT then w.growT=grow;for _,g in w.grow do g.part.Transparency=grow end end
 local flicker=left<.3 and (.5+.5*math.sin(now*48)) or 0
 local fill,edge=FILL-.1*k,EDGE*(1-flicker)
 if fill~=w.fillT then w.fillT=fill;for _,p in w.fills do p.Transparency=fill end end
 if edge~=w.edgeT then w.edgeT=edge;for _,p in w.edges do p.Transparency=edge end end
 debug.profileend()
end

-- Projectiles: the server's shots replayed from origin, yaws, speed and life (MapBossShapes.shot),
-- stopping where MapBossShotEnds says the server stopped them. Only a volley's own ends count
-- (Shapes.shotEnds): the last volley's list can still be here when this one launches.
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
  local B=state.shots[bi];local d=B.ctx.data;local ends=Shapes.shotEnds(state.ends,B.ctx.serial);local alive=false
  for _,s in B.list do
   if s.done then continue end
   local stop=math.min(B.born+d.life,ends and ends[tostring(s.i)] or math.huge)
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
 if state.warning then release(state.warning);state.warning=nil end
 if state.follow then release(state.follow.w) end;state.follow=nil
 for _,B in state.shots or {} do for _,s in B.list do if s.part then s.part:Destroy() end end end;state.shots=nil
 for _,c in state.connections or {} do c:Disconnect() end;state.connections=nil
end

-- Follow-up circles (MapBossService queueFollow): a warning from when the server publishes them to
-- their eruption time, then the boss module's aftershock hook. Only the latest set is shown.
local function stepFollow(npc,state,now,death)
 local raw=npc:GetAttribute('MapBossFollow')
 if raw and raw~=state.followRaw then
  state.followRaw=raw;local d=decode(raw)
  if state.follow then release(state.follow.w);state.follow=nil end
  if type(d.points)=='table' and #d.points>0 and type(d.at)=='number' and d.at>now then
   local F={kind=d.kind,at=d.at,born=now,radius=d.radius or 5,points={},w=newWarning(d.serial,raw)}
   for i,p in d.points do F.points[i]=Vector3.new(p[1],p[2],p[3]) end
   profiled('Boss:BuildWarning',function()
    for _,p in F.points do drawShape(F.w,{kind='circle',center=p,radius=F.radius},p.Y+.07,state.tint or Color3.fromRGB(224,45,49)) end
   end)
   state.follow=F
  end
 end
 local F=state.follow;if not F then return end
 if death then release(F.w);state.follow=nil;return end
 if now>=F.at then
  release(F.w);state.follow=nil
  call(state,'aftershock',{npc=npc,id=state.id,kind=F.kind,points=F.points,radius=F.radius,tint=state.tint,scale=state.T.scale or 1})
  return
 end
 paintWarning(F.w,(now-F.born)/math.max(.05,F.at-F.born),F.at-now,now)
end
-- Once per boss: the spawn intro (only if it spawned in the last 3 s) and the enrage burst.
local function stepMoments(npc,state,now,death)
 if death then return end
 if not state.introDone then
  state.introDone=true;local born=npc:GetAttribute('BossSpawnedAt')
  if type(born)=='number' and now-born<3 then call(state,'intro',{npc=npc,id=state.id,tint=state.tint,scale=state.T.scale or 1}) end
 end
 if not state.enraged and npc:GetAttribute('BossEnraged') then
  state.enraged=true;call(state,'enrage',{npc=npc,id=state.id,tint=state.tint,scale=state.T.scale or 1})
 end
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
  -- Rebind after the rig changes (a streamed-out boss comes back with new Bone/Motor6D
  -- instances), as RogueliteZombieAnimation does; clear() disconnects these.
  local function changed(v)
   if v:IsA('Bone') or v:IsA('Motor6D') or v:IsA('BasePart') or v:IsA('Humanoid') then state.bindingsDirty=true end
  end
  if tracked[npc]~=state then return end -- dropped while the effects module loaded
  state.connections={npc.DescendantAdded:Connect(changed),npc.DescendantRemoving:Connect(changed)}
  state.motion=motion
 end)
end
Tags:GetInstanceAddedSignal('MapBoss'):Connect(track)
for _,npc in Tags:GetTagged('MapBoss') do track(npc) end

-- Ahead of the fight: from two waves before BossEncounter spawns the run map's boss (wave
-- HammerBossWave, default 20) its clips decode and compile one module or clip per frame, instead
-- of all in the spawn frame (King Crab ~120 ms on desktop). Same data as load(); a boss that
-- arrives first (or an admin spawn) still loads synchronously in track, and this stops.
local warming={}
local function warm(anim)
 if warming[anim] or compiled[anim]~=nil then return end
 local source=animations:FindFirstChild(anim);if not source then return end
 warming[anim]=true
 task.spawn(function()
  -- A failure here is reported once, by the synchronous load() at spawn.
  pcall(function()
   local list=source:GetDescendants()
   for i=#list,1,-1 do -- leaves before the clips that join them; require caches each for load()
    if compiled[anim]~=nil then return end
    if list[i]:IsA('ModuleScript') then task.wait();profiled('Boss:Warm',require,list[i]) end
   end
   task.wait();if compiled[anim]~=nil then return end
   local data=profiled('Boss:Warm',aliased,anim,source)
   local motion=EnemyMotion.compile(data,{})
   for name in data.clips do
    task.wait();if compiled[anim]~=nil then return end
    profiled('Boss:Warm',function() return motion.clips[name] end)
   end
   if compiled[anim]==nil then compiled[anim]=motion end
  end)
 end)
end
task.spawn(function()
 -- ShopService creates the run state on match servers only; lobby clients just wait here.
 local run=game.ReplicatedStorage:WaitForChild('RogueliteRunState',math.huge)
 local function check()
  local map=Maps.get(combat:GetAttribute('RunMap'));local def=map and map.boss and Defs.get(map.boss)
  local wave=run:GetAttribute('Wave')
  if def and type(wave)=='number' and wave>=(combat:GetAttribute('HammerBossWave') or 20)-2 then warm(def.anim) end
 end
 run:GetAttributeChangedSignal('Wave'):Connect(check)
 combat:GetAttributeChangedSignal('RunMap'):Connect(check)
 check()
end)

local function frame(npc,state,now,dt)
 local h=npc:FindFirstChildOfClass('Humanoid');local root=npc.PrimaryPart;if not h or not root then return end
 if state.bindingsDirty or not next(state.joints) then state.bindingsDirty=false;state.joints=EnemyMotion.bind(npc) end
 local motion,T=state.motion,state.T
 local displacement=state.previousPosition and root.Position-state.previousPosition or Vector3.zero
 state.previousPosition=root.Position
 local distance=Vector2.new(displacement.X,displacement.Z).Magnitude
 local start=npc:GetAttribute('BossStart');local kind=npc:GetAttribute('BossAttack');local a=kind and state.def.attacks[kind];local age=start and now-start
 local serial=npc:GetAttribute('BossSerial') or 0
 if a and start and serial~=(state.ctx and state.ctx.serial) then state.ctx=context(npc,state,kind,a,start,serial) end
 local ctx=state.ctx
 if ctx then
  local raw=npc:GetAttribute('MapBossAttackData');if raw~=ctx.raw then ctx.raw=raw;ctx.data=decode(raw) end
  -- The breath turns during its active window (MapBossService tracking); follow the new frame.
  local cf=npc:GetAttribute('BossFrame');if typeof(cf)=='CFrame' and cf~=ctx.cf then ctx.cf=cf;ctx.ground=cf*CFrame.new(0,-T.rootHeight,0) end
 end
 local death=npc:GetAttribute('BossDeathStart');local hit=npc:GetAttribute('BossHitStart')
 local attacking=ctx and ctx.serial==serial and npc:GetAttribute('Attacking') and age and age>=0 and age<=(npc:GetAttribute('BossDuration') or ctx.attack.duration)
 local clip,time
 local v=root.AssemblyLinearVelocity;local moving=Vector2.new(v.X,v.Z).Magnitude>.4
 if death then clip,time='Death',now-death
 elseif attacking then clip,time=attackClip(ctx,age,motion)
 -- A flinch never replaces the walk: on the move it would slide the boss along in one pose.
 elseif hit and now-hit<clipDuration(motion,'Hit') and not moving then clip,time='Hit',now-hit
 else
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
 -- Warnings: from the moment the boss commits to impact (tombs: to their eruption); the grow
 -- layer reaches the edge at impact.
 local at=ctx and ctx.attack
 local warnEnd=at and (ctx.def.shape=='targets' and at.impact+ctx.def.eruptDelay or at.impact)
 if not death and attacking and age>=at.warnStart and age<warnEnd then
  local w=state.warning
  if not w or w.serial~=ctx.serial or w.raw~=ctx.raw then if w then release(w) end;w=profiled('Boss:BuildWarning',buildWarning,ctx);state.warning=w end
  paintWarning(w,(age-at.warnStart)/math.max(.05,warnEnd-at.warnStart),warnEnd-age,now)
 elseif state.warning then release(state.warning);state.warning=nil end
 stepFollow(npc,state,now,death)
 stepMoments(npc,state,now,death)
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
  debug.profilebegin('Boss:Frame')
  local ok,err=pcall(frame,npc,state,now,dt)
  debug.profileend()
  if not ok and not state.warned then state.warned=true;warn('MapBossPresentation: '..tostring(err)) end
 end
end)

-- Knockdown (GroundSlam, FrontStomp): a short fall, thrown away from the impact.
task.spawn(function()
 -- MapBossService creates it on the server when it first loads (the first map boss), so this can
 -- wait the whole session; the explicit timeout keeps the infinite-yield warning out of Output.
 local knock=combat:WaitForChild('MapBossKnockdown',math.huge)
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
