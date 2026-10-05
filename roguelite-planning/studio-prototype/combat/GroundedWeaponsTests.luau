-- Studio Edit regression with an isolated raycast world. All test Instances stay outside the
-- DataModel and are destroyed; no remotes, connections, rewards, live enemies or persistent writes.
-- return assert(loadstring(read('GroundedWeaponsTests')))()(read)
return function(read)
 local checks=0;local cleanup={}
 local function check(ok,message) checks+=1;assert(ok,message) end
 local function near(a,b) return (a-b).Magnitude<.001 end
 local function new(class,parent)
  local obj=Instance.new(class);obj.Parent=parent
  if not parent then table.insert(cleanup,obj) end
  return obj
 end
 local function run()
  local dummy=new('Model');local hum=new('Humanoid',dummy);local head=new('Part',dummy)
  local plainDummy=new('Model');plainDummy:SetAttribute('LobbyDummy',true);local dummyPart=new('Part',plainDummy)
  local character=new('Model');local floorPart=new('Part')
  local world={floor=0,normal=Vector3.yAxis,calls=0,blocker=head}
  function world:FindFirstChild() return nil end
  function world:Raycast(origin,direction,params)
   self.calls+=1;self.lastParams=params;self.lastOrigin=origin;self.lastDirection=direction
   if self.blocker and not table.find(params.FilterDescendantsInstances,self.blocker.Parent) then
    return {Instance=self.blocker,Position=Vector3.new(origin.X,5,origin.Z),Normal=Vector3.yAxis}
   end
   if self.floor==nil then return nil end
   return {Instance=floorPart,Position=Vector3.new(origin.X,self.floor,origin.Z),Normal=self.normal}
  end
  local services={Players={GetPlayers=function() return {{Character=character}} end},CollectionService={GetTagged=function() return {} end}}
  local env=setmetatable({workspace=world,game={GetService=function(_,name) return services[name] end}},{__index=getfenv()})
  local function load(name,custom)
   local f,e=loadstring(read(name),name);assert(f,e);if custom then setfenv(f,custom) end;return f()
  end
  local ground=load('GroundContact',env)
  check(ground.actor(head)==dummy,'Untagged Humanoid dummy is rejected as ground')
  check(ground.actor(dummyPart)==plainDummy,'Attribute-only lobby target is rejected as ground')
  check(ground.actor(floorPart)==nil,'Map geometry remains valid ground')
  local probe=ground.new()
  check(near(probe:center(Vector3.new(2,7,-4),.8),Vector3.new(2,.86,-4)),'Ball lands on floor below dummy instead of its head')
  check(world.calls==2,'Probe skips actor and continues to floor')
  check(table.find(world.lastParams.FilterDescendantsInstances,character)~=nil,'All player characters excluded')
  check(world.lastParams.RespectCanCollide,'Noncolliding cosmetic geometry is not ground')
  world.blocker=nil;world.floor=1
  check(near(probe:center(Vector3.new(2,1,-4),.8,0),Vector3.new(2,1.86,-4)),'Small grounded step accepted')
  world.floor=3;check(probe:center(Vector3.zero,.8,0)==nil,'Ball cannot hop onto high wall')
  world.floor=-7;check(probe:center(Vector3.zero,.8,0)==nil,'Ball cannot teleport down a cliff')
  world.floor=0;world.normal=Vector3.xAxis;check(probe:floor(Vector3.zero)==nil,'Vertical wall is not floor')
  world.normal=Vector3.yAxis;world.floor=nil;check(probe:center(Vector3.zero,.8)==nil,'Missing floor cancels ground placement')

  local ball=new('Model');local mesh=new('Part',ball);mesh.Size=Vector3.one*1.6;mesh.CFrame=CFrame.new(10,5,0)
  ball.WorldPivot=CFrame.new(4,2,-3)
  local radius,offset=ground.ballGeometry(ball)
  check(math.abs(radius-.8)<.001 and near(offset,Vector3.new(6,3,3)),'Mesh radius and off-center pivot derived together')
  local display=ball:Clone();table.insert(cleanup,display);local scale=1.7;display:ScaleTo(scale)
  local contact=Vector3.new(-40,radius*scale+ground.Clearance,80)
  local rotation=CFrame.Angles(.7,1.2,-.4)
  display:PivotTo(CFrame.new(contact)*rotation*CFrame.new(-offset*scale))
  check(near(display:GetBoundingBox().Position,contact),'Visual center stays on collision center at any rotation and scale')

  local template=load('ChickenTemplate');local chicken=template.build();table.insert(cleanup,chicken)
  check(chicken.Parent==nil and chicken:GetAttribute('ProceduralChickenFallback'),'Fallback template stays outside the live world')
  local root=chicken:FindFirstChild('HumanoidRootPart');local chickenHumanoid=chicken:FindFirstChildOfClass('Humanoid')
  check(root and chicken.PrimaryPart==root and chickenHumanoid,'Fallback is a server-controllable Humanoid model')
  local joints={};local parts=0;local toes=0
  for _,child in chicken:GetDescendants() do
   if child:IsA('Motor6D') then joints[child.Name]=child;check(child.Part0~=nil and child.Part1~=nil,'Animation joint connects two parts') end
   if child:IsA('BasePart') then
    parts+=1;if child.Name=='Toe' then toes+=1 end
    check(not child.CanQuery and not child.CanTouch,'Chicken never blocks combat queries')
    check(child.CanCollide==(child==root),'Only chicken root collides')
   end
  end
  for _,name in {'Body','Neck','LeftWing','RightWing','LeftHip','RightHip'} do check(joints[name]~=nil,'Existing animator joint '..name) end
  check(toes==6,'Chicken has two three-toed feet')
  check(parts<=48 and parts>=20,'Articulated fallback has bounded detail')
  check(chicken:FindFirstChild('DerpyTongue')~=nil and chicken:FindFirstChild('GooglyEye')~=nil,'Fallback preserves humorous face silhouette')
  local cloned=chicken:Clone();table.insert(cleanup,cloned);check(cloned.PrimaryPart~=root,'Fallback can create independent hatchlings')

  local visuals=load('VacuumVisuals');local stage=new('Folder');local funnel=visuals.new(stage)
  table.insert(cleanup,funnel.model)
  local origin=Vector3.new(350,70,-250);local finish=origin-Vector3.zAxis*12
  funnel:update(origin,finish,4,0)
  local count=#funnel.model:GetDescendants();local beams=0;local motes={}
  for _,child in funnel.model:GetDescendants() do
   if child:IsA('Beam') then beams+=1;check(child.CurveSize0>0 and child.CurveSize1>0,'Wind ribbons are curved arcs, not straight fan lines') end
   if child.Name=='InwardMote' then table.insert(motes,child) end
   if child:IsA('BasePart') then check(child.Anchored and not child.CanCollide and not child.CanQuery,'Funnel is local nonphysical art') end
  end
  check(beams==9 and #motes==12,'Funnel uses fixed bounded visual budget')
  -- Every selected mote is safely away from its recycling boundary; it travels toward the nozzle.
  for i,p in motes do
   if i<10 then
    local before=(p.Position-origin):Dot(-Vector3.zAxis)
    funnel:update(origin,finish,4,.01)
    check((p.Position-origin):Dot(-Vector3.zAxis)<before,'Vacuum mote flows into nozzle')
    funnel:update(origin,finish,4,0)
   end
  end
  for frame=1,300 do funnel:update(origin,finish,4,frame/60) end
  check(#funnel.model:GetDescendants()==count,'Repeated funnel animation allocates no extra Instances')
  funnel:hide();check(funnel.model.Parent==nil,'Inactive funnel returns to pool invisibly')
  funnel:update(origin,finish,4,6);check(funnel.model.Parent==stage,'Pooled funnel can be reused in an isolated showcase')
  funnel:update(origin,origin,4,6);check(funnel.model.Parent==nil,'Zero-length funnel is hidden')
  funnel:destroy()
 end
 local ok,err=xpcall(run,debug.traceback)
 for _,obj in cleanup do obj:Destroy() end
 assert(ok,err)
 return {checks=checks,status='passed',liveWorldModified=false}
end
