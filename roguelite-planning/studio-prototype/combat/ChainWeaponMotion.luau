-- Bounded rigid-link FK. Shared attack-clock sampling keeps hit boxes and skin
-- deformation together without simulating free physics or stretching the metal.
local Motion=require(script.Parent:WaitForChild('WeaponMotion'))
local Geometry=require(script.Parent:WaitForChild('ChainWeaponGeometry'))
local C={}
local profiles={
 ['02']={count=5,lag=14,bend=5,delay=.018,open=.99,payload=3},
 ['04']={count=11,lag=18,bend=9,delay=.035,open=.93,payload=4},
 ['25']={count=7,lag=22,bend=7,delay=.045,open=.95,payload=4},
}
local function smooth(t) t=math.clamp(t,0,1);return t*t*(3-2*t) end
local function pulse(age,start,duration)
 local t=(age-start)/duration
 if t<=0 or t>=1 then return 0 end
 return math.sin(t*math.pi)^2
end
function C.bind(model,id)
 local profile=profiles[id];if not profile then return nil end
 local root=model:FindFirstChild('W'..id..'_Handle_ROOT',true)
 local size,center=model:GetAttribute('BoundsSize'),model:GetAttribute('BoundsCenter')
 if not root or not root:IsA('Bone') or not root.Parent:IsA('BasePart')
  or typeof(size)~='Vector3' or typeof(center)~='Vector3' then
  warn('Missing chain rig/bounds for '..id);return nil
 end
 local geometry=Geometry[id];local scale=size.Magnitude
 if scale<=0 or (size/scale-geometry.proportions).Magnitude>.02 then
  warn('Chain geometry proportions changed for '..id);return nil
 end
 local rig={profile=profile,id=id,entries={},mesh=model:GetPivot():ToObjectSpace(root.Parent.CFrame)}
 local chains=0;local payloads=0
 local function visit(bone,parentIndex,parentRest)
  local name=bone.Name:gsub('^W%d+_','')
  local rest=parentRest*bone.CFrame
  local index=tonumber(name:match('^Chain_(%d+)$'))
  local payload=name:match('_END$')~=nil
  local entry={bone=bone,parent=parentIndex,base=bone.CFrame,rest=rest,index=index,payload=payload,
   bendAxis=rest:VectorToObjectSpace(Vector3.zAxis),liftAxis=rest:VectorToObjectSpace(Vector3.xAxis),open=0}
  if index then
   chains+=1
   if index>1 then
    local a,b=parentRest.UpVector,rest.UpVector
    local turn=math.atan2(a:Cross(b).Z,a:Dot(b))
    entry.open=-turn*profile.open
   end
  elseif payload then
   payloads+=1
   -- The second nunchuck baton must also align with the taut chain.
   if id=='02' then
    local a,b=parentRest.UpVector,rest.UpVector
    entry.open=-math.atan2(a:Cross(b).Z,a:Dot(b))*profile.open
   end
  end
  local box=geometry.boxes[name]
  if box then
   entry.hitCF=rest:ToObjectSpace(CFrame.new(center+box.center*scale))
   entry.hitSize=box.size*scale
  end
  table.insert(rig.entries,entry);local ownIndex=#rig.entries
  if index==1 then rig.firstLink=ownIndex end
  if payload then rig.payloadIndex=ownIndex end
  for _,child in bone:GetChildren() do if child:IsA('Bone') then visit(child,ownIndex,rest) end end
 end
 visit(root,nil,rig.mesh)
 if chains~=profile.count or payloads~=1 then warn('Incomplete chain rig for '..id);return nil end
 -- The kusarigama is thrown from its weight; the other two are held by the
 -- grip. Re-anchor the complete FK assembly, preserving every joint length.
 rig.heldIndex=id=='04' and rig.payloadIndex or 1
 rig.heldOffset=id=='04' and rig.entries[rig.heldIndex].hitCF.Position or Vector3.zero
 rig.director=rig.entries[rig.firstLink].rest.UpVector*(id=='04' and -1 or 1)
 -- Put the flat sickle blade in the slash plane, with its hook on the leading
 -- side of the sweep. Do not use the generic sword's +/-Y striking-end guess.
 rig.attackBasis=CFrame.lookAt(Vector3.zero,rig.director,id=='04' and -Vector3.zAxis or Vector3.zAxis):Inverse()
 rig.fullReach=0
 for _,age in {.24,.32,.4,.46} do
  local frames,boxes=C.sample(rig,age)
  local held=frames[rig.heldIndex]:PointToWorldSpace(rig.heldOffset)
  for _,box in boxes do
   local cf,s=box.cf,box.size
   local extent=(math.abs(rig.director:Dot(cf.RightVector))*s.X+math.abs(rig.director:Dot(cf.UpVector))*s.Y+math.abs(rig.director:Dot(cf.LookVector))*s.Z)*.5
   rig.fullReach=math.max(rig.fullReach,(cf.Position-held):Dot(rig.director)+extent)
  end
 end
 return rig
end
local function transform(rig,entry,age)
 -- Identity at both boundaries: no reset pop, accumulated momentum or drift.
 if age<0 or age>=Motion.SwingDuration or (not entry.index and not entry.payload) then return CFrame.identity end
 age=age/Motion.SwingDuration*.58
 local p=rig.profile
 local fraction=entry.payload and 1 or (entry.index-1)/math.max(1,p.count-1)
 if rig.id=='04' then fraction=1-fraction end
 local delay=fraction*p.delay
 local load=pulse(age,delay,.29)
 local catch=pulse(age,.23+delay,.24)
 local nearHeld=entry.index==(rig.id=='04' and p.count or 1)
 local amplitude=entry.payload and p.payload or (nearHeld and p.lag or p.bend/(p.count-1))
 local sign=rig.id=='04' and 1 or -1
 -- Stay almost straight through the striking portion, then fold on recovery.
 local opening=smooth((age-delay)/.105)*(1-smooth((age-.28-delay)/.22))
 local angle=sign*math.rad(amplitude)*(load-.23*catch)+entry.open*opening
 local lift=math.rad(entry.index==1 and 3 or 1/p.count)*pulse(age,delay+.025,.34)
 return CFrame.fromAxisAngle(entry.bendAxis,angle)*CFrame.fromAxisAngle(entry.liftAxis,lift)
end
function C.apply(rig,age)
 if not rig then return end
 for _,entry in rig.entries do entry.bone.Transform=transform(rig,entry,age) end
end
function C.sample(rig,age,pose)
 pose=pose or CFrame.identity
 local frames,boxes={},{}
 for i,entry in rig.entries do
  local parent=entry.parent and frames[entry.parent] or pose*rig.mesh
  local cf=parent*entry.base*transform(rig,entry,age)
  frames[i]=cf
  if entry.hitCF then table.insert(boxes,{cf=cf*entry.hitCF,size=entry.hitSize}) end
 end
 return frames,boxes
end
function C.hitBoxes(rig,pose,age)
 local _,boxes=C.sample(rig,age,pose)
 return boxes
end
-- `visual` (client renderer only) widens the sweep like WeaponMotion.pose.
function C.pose(rig,root,direction,aim,age,reach,style,side,visual)
 local center=root.Position+Vector3.yAxis*.25
 local delta=direction or (aim and aim-center) or root.LookVector
 delta=Vector3.new(delta.X,0,delta.Z)
 if delta.Magnitude<.01 then delta=Motion.frame(root).LookVector end
 local t=math.clamp((age-Motion.SwingHitStart)/(Motion.SwingHitEnd-Motion.SwingHitStart),0,1)
 side=side or 1
 local half=visual and Motion.VisualSweepHalfAngle or 105
 local heading=CFrame.lookAt(center,center+delta.Unit)*CFrame.Angles(0,math.rad((-half+2*half*smooth(t))*side),0)
 local frames=C.sample(rig,age)
 local held=frames[rig.heldIndex]:PointToWorldSpace(rig.heldOffset)
 -- A close target pulls the swing in (2026-10-03: melee reach grew ~17-25%, which moved the grip
 -- 1.5-2 studs farther out, so a mob hugging the player could sit inside it). The head still ends
 -- half the chain past the target and never past reach; a target at full reach swings as before.
 -- Example: Nunchucks (reach 7.5) at a zombie 3 studs off end at 3 + half the chain, not 7.5.
 local want=reach
 if aim then local o=aim-center;want=math.min(reach,Vector3.new(o.X,0,o.Z).Magnitude+rig.fullReach*.5) end
 local distance=math.max(.85,want-rig.fullReach-.12)
 local rotation=heading.Rotation*rig.attackBasis
 local anchor=heading:PointToWorldSpace(Vector3.new(0,.12,-distance))
 if rig.id=='02' and (style=='FigureEight' or style=='Spin') then
  local frame=CFrame.lookAt(center,center+delta.Unit)
  local phase=t*math.pi*2
  local yaw=math.rad(48)*math.cos(phase)*side
  if style=='FigureEight' then
   anchor=frame:PointToWorldSpace(Vector3.new(math.cos(phase)*1.55*side,math.sin(phase*2)*1.1,-distance))
   rotation=frame.Rotation*CFrame.Angles(math.sin(phase*2)*.32,yaw,math.sin(phase)*.2)*rig.attackBasis
  else
   anchor=frame:PointToWorldSpace(Vector3.new(math.cos(phase)*.65*side,math.sin(phase)*.65,-distance))
   rotation=frame.Rotation*CFrame.Angles(0,0,phase*side)*rig.attackBasis
  end
 end
 return CFrame.new(anchor-rotation:VectorToWorldSpace(held))*rotation
end
function C.swingReturn(rig,cut,idle,age,state)
 local alpha=Motion.swingRecovery(age)
 local cutHeading=cut.Rotation*rig.attackBasis:Inverse()
 local cutYaw=math.atan2(-cutHeading.LookVector.X,-cutHeading.LookVector.Z)
 local idleYaw=math.atan2(-idle.LookVector.X,-idle.LookVector.Z)
 local function delta(a,b) return math.atan2(math.sin(a-b),math.cos(a-b)) end
 if not state.lastIdleYaw then state.returnYaw=cutYaw+delta(idleYaw,cutYaw)
 else state.returnYaw+=delta(idleYaw,state.lastIdleYaw) end
 state.lastIdleYaw=idleYaw
 local yaw=cutYaw+(state.returnYaw-cutYaw)*alpha
 local tilt=CFrame.Angles(0,idleYaw,0):ToObjectSpace(idle.Rotation)
 local cutTilt=CFrame.Angles(0,cutYaw,0):ToObjectSpace(cut.Rotation)
 local rotation=CFrame.Angles(0,yaw,0)*cutTilt:Lerp(tilt,alpha)
 return CFrame.new(Motion.returnPosition(cut.Position,idle.Position,age))*rotation
end
return C
