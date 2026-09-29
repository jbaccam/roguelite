-- Run against a fresh WeaponMotion module and the live reviewed templates.
return function(M,templates)
 local checks=0
 local function check(ok,message) checks+=1;assert(ok,message) end
 for _,id in {'03','19','32','01'} do
  local template=templates[id]
  local size,center=template:GetAttribute('BoundsSize'),template:GetAttribute('BoundsCenter')
  for _,yaw in {0,math.pi/2,math.pi,-math.pi/2} do
   local root=CFrame.new(0,4,0)*CFrame.Angles(0,yaw,0)
   local frame=M.frame(root)
   local aim=root.Position+frame.LookVector*4
   local function pose(age) return M.pose(root,4.2,1,aim,0,age,'Melee',id,frame.LookVector,6,size,center) end
   local first,last=pose(0),pose(M.SwingHitEnd)
   if id=='03' then
    local a,b=frame:PointToObjectSpace(first.Position),frame:PointToObjectSpace(last.Position)
    check(a.X>0 and b.X<0 and a.Y>b.Y+2,'Diagonal must descend right to left')
   elseif id=='19' then
    local a,b=frame:PointToObjectSpace(pose(.06).Position),frame:PointToObjectSpace(pose(.2).Position)
    check(b.Z<a.Z-.2 and math.abs(a.X-b.X)<1e-5 and math.abs(a.Y-b.Y)<1e-5,'Thrust must extend straight')
    check(select(2,pose(.03))==false,'Thrust pullback must not damage')
    check(select(2,pose(.14))==true,'Thrust extension must damage')
   else
    check(math.abs(first.Position.Y-last.Position.Y)<1e-5,'Horizontal sweep changed')
    -- Rendered cut: wider and farther out, yet on the target when the hit lands.
    local function rendered(age,target) return M.pose(root,4.2,1,target,0,age,'Melee',id,frame.LookVector,6,size,center,nil,nil,true) end
    local function bearing(cf) local p=frame:PointToObjectSpace(cf.Position);return math.deg(math.atan2(-p.X,-p.Z)) end
    local function out(cf) local p=frame:PointToObjectSpace(cf.Position);return Vector2.new(p.X,p.Z).Magnitude end
    local middle=(M.SwingHitStart+M.SwingHitEnd)/2
    check(math.abs(math.abs(bearing(pose(0)))-105)<.01,'Hit path must keep its 210 degree sweep')
    check(math.abs(math.abs(bearing(rendered(0,aim)))-M.VisualSweepHalfAngle)<.01,'Rendered sweep must start wider')
    check(math.abs(bearing(pose(middle)))<.01 and math.abs(bearing(rendered(middle,aim)))<.01,'Both cuts cross the target mid-sweep')
    local close=root.Position+frame.LookVector*2
    local tip=size.Y*.5+center.Y
    local hit=M.pose(root,4.2,1,close,0,middle,'Melee',id,frame.LookVector,6,size,center)
    local shown=rendered(middle,close)
    check(out(shown)>out(hit)+.5,'Rendered cut sits farther out for close targets')
    check(out(shown)-(size.Y-tip)<=2-size.Y*.2,'Rendered blade still overlaps the close target')
   end
   local idle=M.pose(root,4.2,1,nil,0,1e6,'Melee',id)
   local state={}
   local startReturn=M.swingReturn(last,idle,M.SwingHitEnd,state,id)
   check((startReturn.Position-last.Position).Magnitude<1e-4 and startReturn.UpVector:Dot(last.UpVector)>.9999,'Recovery start discontinuity')
   local previous=startReturn
   for i=1,96 do
    local cf=M.swingReturn(last,idle,M.SwingHitEnd+(M.SwingDuration-M.SwingHitEnd)*i/96,state,id)
    check(cf.UpVector:Dot(previous.UpVector)>.98,'Recovery rotation jump')
    for _,v in {cf:GetComponents()} do check(v==v and math.abs(v)<1e6,'Invalid pose') end
    previous=cf
   end
   check((previous.Position-idle.Position).Magnitude<1e-4 and previous.UpVector:Dot(idle.UpVector)>.9999,'Recovery must reach idle')
  end
 end
 return {checks=checks}
end
