-- Pure checks for TrailerCamPath. Run in Edit: loadstring this file, call it with the module
-- table, read the returned {pass, fail, lines}. No services, no Studio writes.
return function(P)
 local pass,fail,lines=0,0,{}
 local function check(name,ok,detail)
  if ok then pass+=1 else fail+=1;table.insert(lines,'FAIL '..name..(detail and (': '..detail) or '')) end
 end
 local function near(a,b,eps) return math.abs(a-b)<=(eps or 1e-4) end
 local function cfNear(a,b,eps)
  eps=eps or 1e-3
  if (a.Position-b.Position).Magnitude>eps then return false end
  return a.LookVector:Dot(b.LookVector)>1-eps and a.UpVector:Dot(b.UpVector)>1-eps
 end

 -- 1. Quaternion round trip over many orientations, including the three non-trace branches.
 local rng=Random.new(7)
 local worst=0
 for i=1,400 do
  local cf=CFrame.fromEulerAnglesYXZ(rng:NextNumber(-math.pi,math.pi),rng:NextNumber(-math.pi,math.pi),rng:NextNumber(-math.pi,math.pi))
  if i<=3 then cf=({CFrame.Angles(math.pi,0,0),CFrame.Angles(0,math.pi,0),CFrame.Angles(0,0,math.pi)})[i] end
  local q=P.quat(cf)
  local back=CFrame.new(0,0,0,q[1],q[2],q[3],q[4])
  worst=math.max(worst,1-back.LookVector:Dot(cf.LookVector),1-back.UpVector:Dot(cf.UpVector))
 end
 check('quat round trip',worst<1e-5,tostring(worst))

 -- 2. Ease: ends at 0 and 1, symmetric, monotonic.
 check('smoother ends',near(P.smoother(0),0) and near(P.smoother(1),1))
 check('smoother middle',near(P.smoother(.5),.5))
 local mono=true
 for i=1,100 do if P.smoother(i/100)<P.smoother((i-1)/100) then mono=false end end
 check('smoother monotonic',mono)

 -- 3. A path passes through every key (position, rotation, FOV).
 local keys={
  {cf=CFrame.lookAt(Vector3.new(0,10,0),Vector3.new(50,0,0)),fov=70},
  {cf=CFrame.lookAt(Vector3.new(40,20,30),Vector3.new(50,0,0)),fov=55},
  {cf=CFrame.lookAt(Vector3.new(90,15,10),Vector3.new(50,0,0)),fov=40},
  {cf=CFrame.lookAt(Vector3.new(100,40,-60),Vector3.new(50,0,0)),fov=65},
 }
 local path=P.build(keys)
 check('build',path~=nil and #path.segments==3)
 local cf0,f0=P.sample(path,0)
 local cf1,f1=P.sample(path,1)
 check('starts on key 1',cfNear(cf0,keys[1].cf) and near(f0,70,1e-3))
 check('ends on last key',cfNear(cf1,keys[4].cf) and near(f1,65,1e-3))
 for i=2,3 do
  local u=path.segments[i].from
  local cf,f=P.sample(path,u)
  check('passes key '..i,cfNear(cf,keys[i].cf,2e-3) and near(f,keys[i].fov,1e-2),tostring(cf.Position))
 end

 -- 4. Even speed: with no easing, equal steps of u cover nearly equal distances.
 local steps,prev,dists=300,P.sample(path,0).Position,{}
 for i=1,steps do
  local p=P.sample(path,i/steps).Position
  table.insert(dists,(p-prev).Magnitude);prev=p
 end
 local mean=0;for _,d in dists do mean+=d end;mean/=#dists
 local dev=0;for _,d in dists do dev=math.max(dev,math.abs(d-mean)/mean) end
 check('even speed (max step error < 6%)',dev<.06,string.format('%.3f',dev))

 -- 5. No sudden turn: consecutive frames never rotate more than a few degrees.
 local maxTurn,last=0,P.sample(path,0)
 for i=1,steps do
  local cf=P.sample(path,i/steps)
  maxTurn=math.max(maxTurn,math.deg(math.acos(math.clamp(cf.LookVector:Dot(last.LookVector),-1,1))))
  last=cf
 end
 check('smooth rotation (max step < 2 deg)',maxTurn<2,string.format('%.2f',maxTurn))

 -- 6. A pan in place (same position, different look) still takes time and turns smoothly.
 local pan=P.build({{cf=CFrame.lookAt(Vector3.zero,Vector3.new(1,0,0)),fov=70},{cf=CFrame.lookAt(Vector3.zero,Vector3.new(0,0,1)),fov=70}})
 local mid=P.sample(pan,.5)
 check('pan in place stays put',mid.Position.Magnitude<1e-3)
 check('pan in place turns halfway',math.abs(mid.LookVector:Dot(Vector3.new(1,0,1).Unit)-1)<1e-3,tostring(mid.LookVector))

 -- 7. Keys facing opposite hemispheres don't spin the long way (180-ish yaw through 3 keys).
 local spin=P.build({
  {cf=CFrame.fromEulerAnglesYXZ(0,math.rad(170),0)},{cf=CFrame.fromEulerAnglesYXZ(0,math.rad(-170),0)}})
 local turn=0;last=P.sample(spin,0)
 for i=1,50 do local cf=P.sample(spin,i/50);turn+=math.deg(math.acos(math.clamp(cf.LookVector:Dot(last.LookVector),-1,1)));last=cf end
 check('short way round (20 deg, not 340)',turn<25,string.format('%.1f',turn))

 -- 8. Fewer than 2 keys gives no path.
 check('one key = no path',P.build({keys[1]})==nil)

 -- 9. Orbit looks at the centre from the right radius and height.
 local o=P.orbit(Vector3.new(10,0,10),20,5,0)
 check('orbit radius/height',near((o.Position-Vector3.new(30,5,10)).Magnitude,0,1e-4))
 check('orbit looks at centre',o.LookVector:Dot((Vector3.new(10,0,10)-o.Position).Unit)>.9999)

 return {pass=pass,fail=fail,lines=lines}
end
