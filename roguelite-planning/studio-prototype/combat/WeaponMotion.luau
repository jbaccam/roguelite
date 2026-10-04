local M={}
M.SwingReferenceCooldown=.65
M.SwingHitStart=.12
M.SwingHitEnd=.46
M.SwingDuration=.9
-- Rendered horizontal cuts sweep wider than the hit path (+/-105 deg). Both stay
-- centred on the target, so the visible blade crosses it when the hit lands.
M.VisualSweepHalfAngle=120
-- Shared by rendered motion and authoritative hit sampling. Unlisted weapons
-- retain their horizontal cut. Thrust also works with normalized +Y sword tips.
M.MeleeStyles={['03']='Diagonal',['19']='Thrust',['16']='Slap',['20']='Downward',['26']='Downward',['36']='Reap',['37']='Thrust',['39']='Chain'}
M.DownwardWeapons={['01']=true,['05']=true,['06']=true,['20']=true,['26']=true,['27']=true,['31']=true}
function M.meleeStyle(id) return M.MeleeStyles[id] or 'Horizontal' end
-- Reaper's Scythe 'Reap': one full turn around the wielder at full reach. The server hits every
-- enemy in range as the blade's heading passes it (reapFraction), not by box sampling, so the
-- whole disc is covered whatever the nearest target's distance.
function M.reapFraction(age)
 local t=math.clamp((age-M.SwingHitStart)/(M.SwingHitEnd-M.SwingHitStart),0,1)
 return t*t*(3-2*t)
end
-- Where in the turn (0..1) the heading points at `offset`, for a turn that starts behind the
-- cut direction and goes round on `side`. Same rotation as the Reap pose (CFrame.Angles about +Y).
function M.reapFractionOf(direction,offset,side)
 local d=Vector3.new(direction.X,0,direction.Z);local e=Vector3.new(offset.X,0,offset.Z)
 if d.Magnitude<.01 or e.Magnitude<.01 then return .5 end
 local angle=math.atan2(d.Unit:Cross(e.Unit).Y,d.Unit:Dot(e.Unit))
 return (angle*(side or 1)+math.pi)/(2*math.pi)
end
-- Slot spacing is an avatar-scale measurement, never an animated body envelope.
-- Wider ring (2026-10-03, user: "they get placed super close to the player ... more spread out"):
-- radius x1.48 and neighbours 70 degrees apart (was 60), slot order kept. Example, 4 weapons on a
-- standard avatar: ring 7.28 studs (was 4.92), 8.4 studs between neighbours (was 4.9). Melee reach
-- is measured from the player's centre, not the slot, so the ring doesn't change it.
M.BaseRadius=6.2;M.RingGrowth=.36 -- studs added per extra equipped weapon (was 4.2 and .24)
function M.radius(rootSize,equippedCount)
 local count=math.clamp(equippedCount or 1,1,6)
 return (M.BaseRadius+(count-1)*M.RingGrowth)*math.clamp(rootSize.X/2,.5,2)
end
-- Where each slot floats, as data. angle: degrees round the player from its right, through the
-- front (1 right, 2 just right of the front, 3 front-left, 4 behind-left, 5 behind, 6 behind-right).
-- side/depth: the moving formation (floatPose), in ring radii to the right of / behind the player.
-- Example, slot 2 with 4 weapons: 3.6 studs left and 4.8 behind while running (was 1.1 and 3.5).
M.SlotLayout={
 {angle=0,side=.66,depth=.36},
 {angle=70,side=-.5,depth=.66},
 {angle=140,side=.3,depth=.98},
 {angle=210,side=-.78,depth=1.22},
 {angle=280,side=.8,depth=1.42},
 {angle=320,side=-.22,depth=1.66},
}
-- Draco barrel mouth in the normalized play-size model, above its magazine-centered pivot.
M.DracoMuzzle=Vector3.new(0,.585,-1.385)
M.MuzzleOffsets={
 ['00']=Vector3.new(0,.56,-1.195),
 ['07']=M.DracoMuzzle,
 ['09']=Vector3.new(0,.315,-1.67),
 -- Reviewed cannon mouth: native front mapped into the normalized play model.
 ['10']=Vector3.new(0,.302,-1.802),
}
function M.frame(cf)
 local forward=Vector3.new(cf.LookVector.X,0,cf.LookVector.Z)
 return CFrame.lookAt(cf.Position,cf.Position+(forward.Magnitude>.001 and forward.Unit or -Vector3.zAxis))
end
function M.origin(root,radius,slot)
 local layout=M.SlotLayout[slot]
 local angle=layout and math.rad(layout.angle) or (slot-1)*math.pi/3
 return M.frame(root):PointToWorldSpace(Vector3.new(math.cos(angle)*radius,.25,-math.sin(angle)*radius))
end
function M.attackTiming(id,kind,style)
 if kind=='Melee' or id=='32' then return M.SwingHitStart,M.SwingHitEnd,M.SwingDuration end
 return 0,0,.16
end
function M.attackReach(id,style,baseRange)
 -- Every advancing overhead uses the same reach bonus.
 return style=='Downward' and baseRange*1.25 or baseRange
end
function M.combatOrigin(root,radius,slot,id,kind)
 return (kind=='Melee' or id=='32') and root.Position+Vector3.yAxis*.25 or M.origin(root,radius,slot)
end
local function headSign(id)
 -- These assemblies hang their striking mass below the chain/handle.
 return (id=='02' or id=='25') and -1 or 1
end
local function bladeTwist(id)
 -- Katana edge is local -Z at rest. Turning +90 around its length (+Y)
 -- makes that edge lead along -X during the increasing-yaw horizontal cut.
 return id=='03' and math.pi/2 or 0
end
function M.swingRecovery(age)
 local t=math.clamp((age-M.SwingHitEnd)/(M.SwingDuration-M.SwingHitEnd),0,1)
 return t*t*(3-2*t)
end
function M.swingReturn(cut,idle,age,state,id,style)
 local alpha=M.swingRecovery(age)
 local sign=headSign(id)
 local cutYaw=math.atan2(-cut.UpVector.X*sign,-cut.UpVector.Z*sign)
 local idleYaw=math.atan2(-idle.LookVector.X,-idle.LookVector.Z)
 local function angleDelta(a,b) return math.atan2(math.sin(a-b),math.cos(a-b)) end
 if not state.lastIdleYaw then
  state.returnYaw=cutYaw+angleDelta(idleYaw,cutYaw)
 else
  state.returnYaw+=angleDelta(idleYaw,state.lastIdleYaw)
 end
 state.lastIdleYaw=idleYaw
 -- Keep one continuous yaw path, and raise the blade independently. A full
 -- CFrame slerp can switch its shortest-path branch mid-return at 180 degrees.
 local yaw=cutYaw+(state.returnYaw-cutYaw)*alpha
 local idleTilt=CFrame.Angles(0,idleYaw,0):ToObjectSpace(idle.Rotation)
 local rotation=CFrame.Angles(0,yaw,0)*CFrame.Angles(-math.pi/2*sign*(1-alpha),0,0)*CFrame.Angles(0,bladeTwist(id)*(1-alpha),0)*CFrame.identity:Lerp(idleTilt,alpha)
 if (style or M.meleeStyle(id))~='Horizontal' then
  local cutTilt=CFrame.Angles(0,cutYaw,0):ToObjectSpace(cut.Rotation)
  rotation=CFrame.Angles(0,yaw,0)*cutTilt:Lerp(idleTilt,alpha)
 end
 return CFrame.new(M.returnPosition(cut.Position,idle.Position,age))*rotation
end
-- `visual` is set only by the client renderer; server hit sampling omits it.
function M.pose(root,radius,slot,aim,start,now,kind,id,attackDirection,attackRange,boundsSize,boundsCenter,attackStyle,attackSide,visual)
 local origin=M.origin(root,radius,slot)
 -- Every idle weapon faces the character's twelve o'clock, regardless of slot.
 local forward=M.frame(root).LookVector
 local delta=aim and aim-origin or forward
 delta=Vector3.new(delta.X,0,delta.Z)
 if delta.Magnitude<.01 then delta=forward end
 local direction=delta.Unit
 local age=now-start
 local cf=CFrame.lookAt(origin,origin+direction)
 local active=false
 if kind=='Melee' and age>=0 and age<M.SwingDuration then
  -- Build the existing horizontal cut, then specialize the attack path
  -- for weapons with a diagonal or thrust profile.
  local center=M.combatOrigin(root,radius,slot,id,kind)
  local cutDirection=attackDirection or (aim and aim-center or forward)
  cutDirection=Vector3.new(cutDirection.X,0,cutDirection.Z)
  if cutDirection.Magnitude<.01 then cutDirection=forward end
  local t=math.clamp((age-M.SwingHitStart)/(M.SwingHitEnd-M.SwingHitStart),0,1)
  local side=attackSide or 1
  local sweep=t*t*(3-2*t)
  local style=attackStyle or M.meleeStyle(id)
  local wide=visual and style=='Horizontal'
  local reap=style=='Reap'
  local half=reap and 180 or wide and M.VisualSweepHalfAngle or 105
  local heading=CFrame.lookAt(center,center+cutDirection.Unit)*CFrame.Angles(0,math.rad((-half+2*half*sweep)*side),0)
  local sign=headSign(id)
  local reach=attackRange or (id=='32' and 8.5 or 6)
  local tip=boundsSize and boundsSize.Y*.5+(boundsCenter or Vector3.zero).Y*sign or 2.69
  -- Keep the physical weapon size. Move its center far enough that its
  -- striking end reaches the resolved range, including AttackRange bonuses.
  local peak=math.max(.5,reach-tip-.11)
  -- Long melee weapons must not leave a blind spot beside the player.
  -- Pull the cut inward for close targets; distant targets use the full reach.
  if aim and not reap then
   local offset=aim-center
   local distance=Vector3.new(offset.X,0,offset.Z).Magnitude
   -- Rendered: sit farther out, keeping the inner quarter of the blade on the target.
   local length=boundsSize and boundsSize.Y or tip*2
   peak=math.min(peak,math.max(.35,wide and distance+(length-tip)-length*.25 or distance-tip*.65))
  end
  -- A softer rendered pulse keeps the wide arc round instead of pinched at the ends.
  local pulse=math.min(.65*reach/8.5,peak*.25)*(wide and .4 or 1)
  local extension=peak-pulse*(1-math.sin(t*math.pi))
  local cut=heading*CFrame.new(0,.12,-extension)*CFrame.Angles(-math.pi/2*sign,0,0)*CFrame.Angles(0,bladeTwist(id)*side,0)
  local targetFrame=CFrame.lookAt(center,center+cutDirection.Unit)
  if style=='Diagonal' then
   -- Descend from target-relative upper right to lower left. Limit vertical
   -- travel independently of range so range bonuses cannot drive it underground.
   local yaw=math.rad((-55+88*sweep)*side)
   local pitch=math.rad(24-32*sweep)
   local position=Vector3.new((2.8-7*sweep)*math.min(1,extension/3)*side,1.7-2.05*sweep,-extension*(.75+.25*math.sin(t*math.pi)))
   cut=targetFrame*CFrame.new(position)*CFrame.Angles(0,yaw,0)*CFrame.Angles(pitch-math.pi/2,0,0)*CFrame.Angles(0,bladeTwist(id)*side,0)
  elseif style=='Thrust' then
   -- Brief pullback and fast straight extension before returning to idle.
   -- Aim is locked by the server for this attack; no sideways sweep.
   local strike=math.clamp((age-M.SwingHitStart)/.17,0,1)
   strike=1-(1-strike)^3
   local distance=aim and (Vector3.new(aim.X,center.Y,aim.Z)-center).Magnitude or reach
   local guard=tip+1.7
   -- Drive the grip to the target, letting the blade travel through it.
   local endDistance=math.max(guard+.8,math.min(reach,distance)+tip-.35)
   local pull=age<M.SwingHitStart and .35*math.sin(age/M.SwingHitStart*math.pi) or 0
   local depth=guard+(endDistance-guard)*strike-pull
   cut=targetFrame*CFrame.new(0,.12,-depth)*CFrame.Angles(-math.pi/2,0,0)
  elseif style=='Downward' then
   local distance=aim and (Vector3.new(aim.X,center.Y,aim.Z)-center).Magnitude or reach
   local windup=math.clamp(age/M.SwingHitStart,0,1);windup=windup*windup*(3-2*windup)
   local stroke=sweep
   local length=boundsSize and boundsSize.Y or 3
   local grip=Vector3.new(0,(boundsCenter or Vector3.zero).Y-length*.42,0)
   local lever=length*.92
   local finishDepth=math.max(1.8,math.clamp(distance,2,reach)-lever*.8-1.15)+2
   -- Start closer to the wielder and drive toward the target before dropping
   -- through it. Distant targets get a full four-stud grip sweep.
   local startDepth=math.max(.9,finishDepth-4)
   local depth=startDepth+(finishDepth-startDepth)*stroke
   -- Advance the grip while rotating the striking end over it. The head
   -- travels forward through a lever arc; the hand only drops modestly.
   local hand=Vector3.new(side*(.9-.25*stroke),.75+.2*windup+.3*math.sin(math.pi*stroke)-.65*stroke,-depth)
   local pitch=math.rad(-10+45*windup-170*stroke)
   -- Mjolnir's striking faces are local +/-X. Turn around the handle so
   -- an end face, rather than the broad side panel, leads the overhead arc.
   local faceTurn=id=='31' and math.pi/2 or 0
   cut=targetFrame*CFrame.new(hand)*CFrame.Angles(pitch,0,math.rad(-6*side*(1-stroke)))*CFrame.Angles(0,faceTurn,0)*CFrame.new(-grip)
  elseif style=='Slap' then
   local distance=aim and (Vector3.new(aim.X,center.Y,aim.Z)-center).Magnitude or reach
   cut=targetFrame*CFrame.new((2.5-5.3*sweep)*side,.25,-math.min(reach,distance))*CFrame.Angles(0,math.rad((-25+55*sweep)*side),math.rad(65*side))
  end
  if style=='Chain' then cut=cf end
  cf=cut:Lerp(cf,M.swingRecovery(age))
  active=age>=select(1,M.attackTiming(id,kind,style)) and age<=M.SwingHitEnd
 elseif kind~='Melee' and age>=0 and age<.16 then
  cf*=CFrame.new(0,0,.23*(1-age/.16))
 end
 return cf,active
end

function M.attackRoot(root,aim)
 return CFrame.new(root.Position.X,aim.Y-.25,root.Position.Z)*M.frame(root).Rotation
end
function M.chooseStyle(id,count,serial,distance,baseRange)
 if M.DownwardWeapons[id] and distance and distance<3 then return 'Horizontal' end
 -- At the outer edge, use the stroke that can actually reach. Keep the
 -- hammer's existing ranged/melee combo decision, since it can throw.
 if id~='31' and M.DownwardWeapons[id] and distance and baseRange and distance>baseRange then return 'Downward' end
 if id=='32' or id=='36' or id=='39' then return M.meleeStyle(id) end
 -- Trident: a stab at one enemy, a sweep through a crowd (it throws beyond reach).
 if id=='37' then return count>1 and 'Horizontal' or 'Thrust' end
 -- Vampire Blade: alternating wide sweeps.
 if id=='40' then return serial%2==0 and 'Diagonal' or 'Horizontal' end
 if id=='02' then return serial%3==0 and 'Spin' or 'FigureEight' end
 if id=='03' then
  if count>1 then return serial%2==0 and 'Horizontal' or 'Diagonal' end
  return serial%3==0 and 'Thrust' or 'Diagonal'
 end
 if id=='16' then return serial%2==1 and 'Slap' or 'Diagonal' end
 if id=='20' then return ({'Diagonal','Horizontal','Diagonal','Downward'})[(serial-1)%4+1] end
 if id=='26' then return serial%3==0 and 'Diagonal' or 'Downward' end
 if M.DownwardWeapons[id] then
  return count>1 and 'Horizontal' or ({'Horizontal','Diagonal','Downward'})[(serial-1)%3+1]
 end
 return M.meleeStyle(id)
end
function M.chooseSide(serial) return serial%2==1 and 1 or -1 end
function M.entryAlpha(age)
 local t=math.clamp(age/M.SwingHitStart,0,1)
 return t*t*(3-2*t)
end
function M.returnPosition(cut,idle,age)
 local t=math.clamp((age-M.SwingHitEnd)/(M.SwingDuration-M.SwingHitEnd),0,1)
 local alpha=t*t*(3-2*t)
 local delta=idle-cut
 local direction=delta.Magnitude>.001 and delta.Unit or Vector3.yAxis
 -- One bounded elastic rebound. Zero position/velocity disturbance at endpoints.
 local bounce=math.sin(t*math.pi*3)*math.sin(t*math.pi)^2*(1-t)*.25
 local follow=math.sin(math.clamp(t/.3,0,1)*math.pi)^2*math.min(.65,delta.Magnitude*.12)
 return cut:Lerp(idle,alpha)+direction*(bounce-follow)+Vector3.yAxis*(math.sin(t*math.pi)^2*.25)
end
function M.glovePose(root,aim,age,side,reach)
 local center=root.Position+Vector3.yAxis*.25
 local delta=Vector3.new(aim.X-center.X,0,aim.Z-center.Z)
 local direction=delta.Magnitude>.01 and delta.Unit or root.LookVector
 local frame=CFrame.lookAt(center,center+direction)
 local t=math.clamp((age-M.SwingHitStart)/.17,0,1);t=1-(1-t)^3
 local depth=2.25+(math.clamp(delta.Magnitude+.55,3,reach+.55)-2.25)*t
 return frame*CFrame.new(side*(1.05-.65*t),.15,-depth)*CFrame.Angles(-math.pi/2,0,math.rad(side*8*t))
end

-- Cosmetic follow state belongs to a rendered character, never the server hit pose.
function M.newFloat()
 return {moving=0,phase=0,slots={},dt=0}
end
-- Exact underdamped spring driven by a linearly moving target. Integrating the
-- target's travel avoids the extra frame of lag from a constant-target solver.
local function spring(position,velocity,previous,target,dt,omega,damping)
 if dt<=0 then return position,velocity end
 local decay=damping*omega
 local frequency=omega*math.sqrt(1-damping*damping)
 local targetVelocity=(target-previous)/dt
 local shift=targetVelocity*(2*damping/omega)
 local displacement=position-previous+shift
 local relativeVelocity=velocity-targetVelocity
 local sine,cosine=math.sin(frequency*dt),math.cos(frequency*dt)
 local envelope=math.exp(-decay*dt)
 local nextDisplacement=(displacement*cosine+(relativeVelocity+displacement*decay)*(sine/frequency))*envelope
 local nextVelocity=(relativeVelocity*cosine-(relativeVelocity*decay+displacement*omega*omega)*(sine/frequency))*envelope
 return target-shift+nextDisplacement,targetVelocity+nextVelocity
end
function M.stepFloat(state,root,velocity,dt)
 local frame=M.frame(root)
 local yaw=math.atan2(-frame.LookVector.X,-frame.LookVector.Z)
 local reset=not state.lastRoot or dt>.25 or (root.Position-state.lastRoot).Magnitude>32
 dt=math.clamp(dt,0,.25);state.dt=dt
 if reset then
  state.slots={};state.position=root.Position;state.velocity=Vector3.zero
  state.yaw=yaw;state.yawVelocity=0;state.targetYaw=yaw;state.lastYaw=yaw
  state.travelDirection=nil
 else
  -- Unwrap the avatar's heading before smoothing it. Repeated spins retain
  -- their direction across +/-pi instead of flipping the weapon's turn.
  local delta=math.atan2(math.sin(yaw-state.lastYaw),math.cos(yaw-state.lastYaw))
  if math.abs(math.abs(delta)-math.pi)<.0001 and state.turnSign then delta=math.pi*state.turnSign end
  if math.abs(delta)>.001 then state.turnSign=math.sign(delta) end
  local targetYaw=state.targetYaw+delta
  state.yaw,state.yawVelocity=spring(state.yaw,state.yawVelocity,state.targetYaw,targetYaw,dt,16,.8)
  state.targetYaw=targetYaw;state.lastYaw=yaw
  local position,nextVelocity=spring(state.position,state.velocity,state.lastRoot,root.Position,dt,12,.8)
  local y,vy=spring(state.position.Y,state.velocity.Y,state.lastRoot.Y,root.Position.Y,dt,13,.62)
  local lag=position-root.Position
  local horizontal=Vector3.new(lag.X,0,lag.Z)
  if horizontal.Magnitude>4 then
   horizontal=horizontal.Unit*4;nextVelocity=Vector3.new(0,nextVelocity.Y,0)
  end
  local vertical=math.clamp(y-root.Position.Y,-3.5,3.5)
  if vertical~=y-root.Position.Y then vy=0 end
  state.position=root.Position+horizontal+Vector3.yAxis*vertical
  state.velocity=Vector3.new(nextVelocity.X,vy,nextVelocity.Z)
 end
 state.lastRoot=root.Position
 state.frame=CFrame.new(state.position)*CFrame.Angles(0,state.yaw,0)
 local speed=Vector3.new(velocity.X,0,velocity.Z).Magnitude
 if speed>.5 then
  local travel=Vector3.new(velocity.X,0,velocity.Z).Unit
  local previous=state.travelDirection or travel
  local blended=previous:Lerp(travel,1-math.exp(-9*dt))
  -- Retain magnitude while filtering: normalizing every step would lock an
  -- exact left/right reversal onto its previous direction indefinitely.
  state.travelDirection=blended
 end
 state.moving+=(math.clamp(speed/22,0,1)-state.moving)*(1-math.exp(-8*dt))
 state.phase+=dt*(2.1+state.moving*6)
 -- The grip trails behind, but the blade leans slightly FORWARD. Position
 -- lag supplies the drag; a large backward lean must not substitute for it.
 local trail=state.position-root.Position
 trail=Vector3.new(trail.X,0,trail.Z)
 local length=trail.Magnitude
 state.lean=length>.001 and CFrame.fromAxisAngle(Vector3.yAxis:Cross(-trail/length),math.min(math.atan(length/14),math.rad(12))) or CFrame.identity
end
local followRates={10.8,8.4,12.3,7.6,9.3,11.6}
-- During travel these become irregular ranks behind the player, not six
-- points on a rotating circumference. Each rank still has its own momentum.
-- Stagger through the middle as well as both sides. Two outer-only lanes
-- leave a conspicuous empty corridor, even with independent spring motion.
-- The ranks are M.SlotLayout's side/depth (2026-10-03: slots 2 and 3 ran 2 studs apart).
function M.floatPose(pose,root,state,slot,attacking,radius,aiming)
 local anchor=M.origin(root,radius,slot)
 local travel=state.travelDirection or M.frame(root).LookVector
 travel=travel.Magnitude>.01 and travel.Unit or M.frame(root).LookVector
 local right=travel:Cross(Vector3.yAxis)
 local phase=state.phase*(.7+slot*.071)+slot*1.91
 local layout=M.SlotLayout[slot] or {side=1,depth=.5}
 local trail=root.Position+right*(layout.side*radius)-travel*(layout.depth*radius)+Vector3.yAxis*.25
 local freeOffset=right*(math.sin(phase*.61)*.35)+travel*(math.cos(phase*.47)*.45)
 local goal=anchor:Lerp(trail+freeOffset,state.moving)
 local follow=state.slots[slot]
 if not follow then
  follow={position=anchor,velocity=Vector3.zero,target=anchor,yaw=state.targetYaw or 0,yawVelocity=0,targetYaw=state.targetYaw or 0,rotation=pose.Rotation,strength=1}
  state.slots[slot]=follow
 end
 local dt=state.dt
 -- Follow the changing formation in world space. Rest slots return gradually
 -- when slowing down; jump/spin/reversal momentum is never projected onto a ring.
 local rate=followRates[slot] or 12
 local position,velocity=spring(follow.position,follow.velocity,follow.target,goal,dt,rate,.76)
 local y,vy=spring(follow.position.Y,follow.velocity.Y,follow.target.Y,goal.Y,dt,rate,.64)
 local lag=position-goal
 local horizontal=Vector3.new(lag.X,0,lag.Z)
 local maxLag=2*radius+4 -- permit a full reversal without snapping to the new side
 if horizontal.Magnitude>maxLag then horizontal=horizontal.Unit*maxLag;velocity=Vector3.zero end
 local vertical=math.clamp(y-goal.Y,-3.5,3.5)
 if vertical~=y-goal.Y then vy=0 end
 follow.position=goal+horizontal+Vector3.yAxis*vertical
 follow.velocity=Vector3.new(velocity.X,vy,velocity.Z)
 follow.target=goal
 local targetYaw=state.targetYaw or 0
 follow.yaw,follow.yawVelocity=spring(follow.yaw,follow.yawVelocity,follow.targetYaw,targetYaw,dt,rate+3,.8)
 follow.targetYaw=targetYaw
 local idleRotation=(state.lean or CFrame.identity)*CFrame.Angles(0,follow.yaw,0)
 local rotationAlpha=1-math.exp(-(rate+6)*dt)
 if aiming or attacking then follow.rotation=pose.Rotation
 else follow.rotation=follow.rotation:Lerp(idleRotation,rotationAlpha) end
 follow.strength+=((attacking and .45 or 1)-follow.strength)*(1-math.exp(-18*dt))
 local bob=math.sin(phase)*(.12+.22*state.moving)
 local offset=follow.position-anchor+Vector3.yAxis*bob
 local strength=follow.strength
 -- Roll around the aim axis; never yaw the muzzle away from its target.
 local roll=math.sin(phase+.4)*math.rad(1+state.moving)*strength
 return CFrame.new(pose.Position+offset*strength)*follow.rotation*CFrame.Angles(0,0,roll)
end
return M
