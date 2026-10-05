-- Dependency-isolated Studio Edit regression. No Instances, remotes, rewards or live connections.
-- Pass read(name), returning the repo source for combat/name.luau; production modules are loaded
-- with fake clocks/world/targets and their real motion/intercept math. Example over the repo bridge:
-- local H=game:GetService('HttpService');local base='http://127.0.0.1:8934/studio-prototype/combat/'
-- local function read(n) return H:GetAsync(base..n..'.luau') end
-- return assert(loadstring(read('CommittedThrowTests')))()(read)
return function(read)
 local checks=0
 local function check(ok,message) checks+=1;assert(ok,message) end
 local function near(a,b,epsilon) return (a-b).Magnitude<(epsilon or 1e-4) end
 local function signal()
  local s={listeners={}}
  function s:Connect(fn) table.insert(self.listeners,fn);return {Disconnect=function() end} end
  function s:fire(...) for _,fn in self.listeners do fn(...) end end
  return s
 end
 local function setup(id)
  local ctx={now=0,events={},sweeps={},models={},replacementCalls=0,impactPoints={},eggLandings=0}
  local run={Heartbeat=signal(),RenderStepped=signal()}
  local hum={Health=100,WalkSpeed=12,MoveDirection=Vector3.xAxis}
  local npc={};local target={Position=Vector3.new(0,5,-24),AssemblyLinearVelocity=Vector3.new(9,0,0),Anchored=true,Parent=npc}
  function npc:FindFirstChildOfClass() return hum end
  function npc:FindFirstChild(name) return name=='HumanoidRootPart' and target or nil end
  function npc:GetAttribute() return nil end
  function npc:IsDescendantOf() return target.Parent~=nil end
  local character={};local root={Position=Vector3.new(0,5,0),CFrame=CFrame.new(0,5,0)}
  function character:FindFirstChildOfClass() return {Health=100} end
  function character:FindFirstChild(name) return name=='HumanoidRootPart' and root or nil end
  local owner={UserId=1,Character=character}
  local slot={attrs={WeaponId=id}}
  function slot:GetAttribute(k) return self.attrs[k] end
  function slot:SetAttribute(k,v) self.attrs[k]=v end
  local state={}
  function state:GetAttribute(k) return k=='WeaponEnabled' and true or nil end
  function state:FindFirstChild() return slot end
  local event={OnClientEvent=signal()}
  function event:FireAllClients(...) table.insert(ctx.events,table.pack(...)) end
  local combat={PlayerStates={FindFirstChild=function() return state end},ArcShot=event,SpecialFX=event,Shot=event}
  function combat:GetAttribute(k) return k=='ZombiesEnabled' end
  function combat:WaitForChild(k) return self[k] end
  local function model()
   local m={Parent=true,cf=CFrame.identity}
   function m:GetPivot() return self.cf end
   function m:PivotTo(cf) self.cf=cf;self.lastTime=ctx.now end
   function m:GetDescendants() return {} end
   function m:Destroy() self.Parent=nil end
   table.insert(ctx.models,m);return m
  end
  combat.WeaponTemplates={FindFirstChild=function() return {Clone=model} end}
  local tags={GetTagged=function() return {} end,HasTag=function(_,n) return n==npc end}
  local world={}
  function world:GetServerTimeNow() return ctx.now end
  function world:Raycast() return nil end
  function world:Spherecast(from,_,delta)
   table.insert(ctx.sweeps,{from=from,to=from+delta,time=ctx.now})
   local hit=ctx.nextHit;ctx.nextHit=nil;return hit
  end
  local modules={};local refs=setmetatable({},{__index=function(t,k) local v={Name=k};rawset(t,k,v);return v end})
  local players={LocalPlayer=owner,GetPlayerByUserId=function() return nil end}
  local services={RunService=run,CollectionService=tags,ReplicatedStorage={RogueliteCombat=refs},Players=players,Debris={}}
  local fakeGame={ReplicatedStorage=services.ReplicatedStorage,Players=players}
  function fakeGame:GetService(name) return assert(services[name],name) end
  local env=setmetatable({game=fakeGame,workspace=world,script={Parent=refs},require=function(ref) return assert(modules[ref.Name],ref.Name) end},{__index=getfenv()})
  local function load(name)
   local f,e=loadstring(read(name),name);assert(f,e);setfenv(f,env);local value=f();modules[name]=value;return value
  end
  modules.CharacterStats={shotStat=function() return 0 end,mult=function() return 1 end}
  modules.RayImpact={} -- These cases use ordinary throws; RayImpactTests covers Ray Gun contacts.
  modules.WeaponMotion={BaseRadius=4,MuzzleOffsets={},origin=function() return Vector3.new(0,5,0) end}
  modules.ShotBatch={fire=function(remote,_,_,...) remote:FireAllClients(...) end,writer=function(remote)
   return {push=function(_,_,...) remote:FireAllClients(...) end,flush=function() end}
  end}
  modules.UtilityWeapons={new=function() return {} end}
  modules.EggChickens={new=function() return {landed=function(_,d)
   if d.id=='15' then ctx.eggLandings+=1;if ctx.hatchError then error('Injected hatch failure') end end
  end} end}
  modules.UtilityVisuals={mount=function() end}
  modules.GroundContact={Clearance=.06,ballGeometry=function() return .8,Vector3.zero end,new=function() return {center=function(_,p,r) return Vector3.new(p.X,r+.06,p.Z) end} end}
  modules.ThrownVisuals={decorate=function() end,step=function() end,impact=function() end}
  modules.PandoraVisuals={skull=function() return model() end,impact=function(_,point) table.insert(ctx.impactPoints,point) end}
  modules.VfxKit={near=function() return true end}
  local arc=load('ArcMotion');local motion=load('SpecialMotion');local targets=load('ProjectileTarget')
  local replacement=targets.replacement
  targets.replacement=function(...) ctx.replacementCalls+=1;return replacement(...) end
  local folder={Parent=true}
  local visual={id=id,model={Parent=true,GetPivot=function() return CFrame.new(80+ctx.now*40,18,45) end}}
  function ctx:client(name)
   load(name).mount(combat,folder,function() return visual end)
  end
  function ctx:send(row) event.OnClientEvent:fire(table.unpack(row,1,row.n)) end
  function ctx:step(t) self.now=t;run.Heartbeat:fire(1/60);run.RenderStepped:fire(1/60) end
  function ctx:server(name)
   return load(name).new(combat,function() end,function() return {} end)
  end
  ctx.arc=arc;ctx.motion=motion;ctx.targets=targets;ctx.target=target;ctx.hum=hum;ctx.npc=npc
  ctx.def={id=id,kind='Ranged',owner=owner,character=character,slotIndex=1,projectileSpeed=id=='33' and 58 or 40,
   range=40,damage=25,blastRadius=7,projectileRadius=.4,nativePierce=0,nativeBounce=0,stats={},arcTarget=target}
  return ctx
 end

 -- Pandora: the real production lifecycle keeps its launch endpoint and produces the committed
 -- blast after the target moves, dies, or is removed. No replacement query or Redirect event.
 for _,change in {'move','dead','removed'} do
  local c=setup('33');c:client('ArcVisuals');local server=c:server('ArcProjectiles')
  server:launch(c.def,Vector3.new(0,5,0),c.target.Position)
  local launch=c.events[1];check(launch[1]=='Launch','Pandora launched')
  local from,finish,started,duration=launch[7],launch[8],launch[9],launch[10]
  check(finish.X>1,'Pandora aims ahead of a moving enemy')
  check(launch[13]==nil,'Pandora does not send a homing target')
  c:send(launch)
  local initial=c.target.Position;local velocity=c.target.AssemblyLinearVelocity
  check(near(finish,initial+velocity*(started+duration),.002),'Pandora lead matches opening delay plus flight time')
  for frame=0,80 do
   if frame==6 then
    c.target.Position=Vector3.new(-60,5,40);c.target.AssemblyLinearVelocity=Vector3.new(-30,0,0)
    if change=='dead' then c.hum.Health=0 elseif change=='removed' then c.target.Parent=nil end
   end
   local now=started+duration*frame/80;c:step(now)
   local drawn=c.models[1]
   check(drawn~=nil,'Pandora visual exists')
   check(near(drawn:GetPivot().Position,c.arc.position(from,finish,frame/80,launch[11],launch[12],launch[14])),'Pandora visual stays on committed arc')
   local sweep=c.sweeps[#c.sweeps]
   if frame>0 then check(sweep and near(sweep.to,drawn:GetPivot().Position),'Pandora visible and authoritative positions agree') end
  end
  c:step(started+duration+.02)
  check(c.replacementCalls==0,'Pandora never searches for a midair replacement')
  local ended=0
  for _,row in c.events do
   check(row[1]~='Redirect','Pandora never redirects')
   if row[1]=='End' then ended+=1;check(near(row[3],finish),'Pandora detonates at committed landing point') end
  end
  check(ended==1,'Pandora completes exactly one impact even after target removal')
 end

 -- Pins, eggs, molotovs and kunai: server launch lead and client path remain constant while the
 -- target and displayed weapon slot move wildly. No artificial slot-to-path easing is allowed.
 for _,id in {'23','15','14','13'} do
  local c=setup(id);c:client('SpecialWeaponVisuals');local server=c:server('SpecialWeapons')
  server:launch(c.def,Vector3.new(0,5,0),c.target.Position)
  local launch=c.events[1];check(launch[1]=='Launch','ordinary throw launched '..id)
  local from,finish,started,duration,height=launch[7],launch[8],launch[9],launch[10],launch[11]
  check(finish.X>1,'ordinary throw aims ahead '..id)
  check(near(finish,c.target.Position+c.target.AssemblyLinearVelocity*(started+duration),.002),'ordinary lead matches flight time '..id)
  c:send(launch)
  for frame=0,79 do
   if frame==5 then c.target.Position=Vector3.new(-55,9,22);c.hum.Health=0;c.target.Parent=nil end
   c:step(started+duration*frame/80)
   local drawn=c.models[1];local expected=c.motion.position(from,finish,frame/80,height)
   check(drawn and near(drawn:GetPivot().Position,expected),'ordinary visual follows exact committed path '..id)
   if frame>0 then check(near(c.sweeps[#c.sweeps].to,expected),'ordinary server/client flight agrees '..id) end
  end
  check(c.replacementCalls==0,'ordinary throw never searches without a contact '..id)
  for _,row in c.events do check(row[1]~='Segment','ordinary throw never changes direction before contact '..id) end
 end
 -- The common straight-shot engine (including Medusa's Head) must obey the same commitment.
 -- Its launch aim is normally solved by RogueliteCombat; use the actual predictor here too.
 for _,id in {'00','21','34','35'} do
  local c=setup(id);local server=c:server('StatProjectiles');local from=Vector3.new(0,5,0)
  local aim=c.targets.predict(c.target,from,function(distance) return distance/c.def.projectileSpeed end,0,c.def.range,function() return {} end,c.def.character)
  local heading=(aim-from).Unit
  check(aim.X>1,'straight shot leads before release '..id)
  server:launch(c.def,from,aim)
  for frame=1,70 do
   if frame==4 then c.target.Position=Vector3.new(-50,12,15);c.hum.Health=0;c.target.Parent=nil end
   c:step(frame/60)
   local sweep=c.sweeps[#c.sweeps]
   if sweep then
    local displacement=sweep.to-from
    check((displacement-heading*displacement:Dot(heading)).Magnitude<1e-4,'straight projectile keeps launch heading '..id)
   end
  end
  local launches,terminals=0,0
  for _,row in c.events do
   if row[3]=='Fly' then launches+=1 end
   if row[3]=='Land' and row[16]==true then terminals+=1;check(near(row[1],from+heading*c.def.range,.002),'straight shot reaches full committed range '..id) end
   check(row[3]~='Drop','target death does not cancel a straight shot '..id)
  end
  check(launches==1 and terminals==1 and c.replacementCalls==0,'one uninterrupted straight leg then terminal '..id)
 end
 -- If contact and the distance limit happen in one substep, exactly one egg landing occurs.
 do
  local c=setup('15');local server=c:server('SpecialWeapons')
  c.def.arcTarget=nil;c.def.range=.01
  server:launch(c.def,Vector3.new(0,5,0),Vector3.new(0,5,-24))
  c.nextHit={Instance={FindFirstAncestorOfClass=function() return c.npc end},Position=Vector3.new(0,5,-.5)}
  c:step(.02);c:step(1)
  check(c.eggLandings==1,'An egg hatches at most once when contact and range expiry coincide')
  local ends=0;for _,row in c.events do if row[1]=='End' then ends+=1 end end
  check(ends==1,'An egg ends exactly once')
 end
 do
  local c=setup('15');local server=c:server('SpecialWeapons')
  c.def.arcTarget=nil;c.def.range=.01;c.hatchError=true
  server:launch(c.def,Vector3.new(0,5,0),Vector3.new(0,5,-24))
  local first=pcall(function() c:step(.02) end)
  check(not first and c.eggLandings==1,'Injected optional hatch failure is exercised once')
  check(pcall(function() c:step(1) end),'Failed hatch leaves no active egg to retry next heartbeat')
  check(c.eggLandings==1,'Failed hatch is never duplicated')
 end
 return {passed=true,checks=checks,scenarios={'Pandora moving/dead/removed targets','Pins/Eggs/Molotov/Kunai committed aim','Server/client path agreement','Moving source visual cannot bend throws','Straight shots including Medusa ignore target death','Egg contact and expiry deduplicated'}}
end
