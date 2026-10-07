local U={HoldDuration=.85,EscapeDuration=2.4,SafeDistance=7,Slow=.35}
-- Fixed refill remains readable even with high attack speed; damage still scales with cooldown.
U.WashFull=.8
U.WashTrickle=.2
U.WashRefill=.4
U.WashPeriod=U.WashFull+U.WashTrickle+U.WashRefill
U.WashGravity=24
U.WashLife=.48
U.WashDamageScale=U.WashPeriod/(U.WashFull+U.WashTrickle*.5)
function U.washPressure(elapsed)
 local phase=math.max(0,elapsed)%U.WashPeriod
 if phase<U.WashFull then return 1 end
 if phase<U.WashFull+U.WashTrickle then return 1-(phase-U.WashFull)/U.WashTrickle end
 return 0
end
function U.inCone(origin,direction,position,length,width,height)
 local delta=position-origin;local depth=delta:Dot(direction)
 local side=delta-direction*depth
 return depth>=0 and depth<=length and math.abs(side.Y)<=height and Vector3.new(side.X,0,side.Z).Magnitude<=.4+width*depth/length
end
function U.pull(position,playerPosition,direction,safeDistance)
 local flat=Vector3.new(position.X-playerPosition.X,0,position.Z-playerPosition.Z)
 if flat.Magnitude<=safeDistance then return Vector3.zero end
 local goal=playerPosition+direction*safeDistance
 local delta=Vector3.new(goal.X-position.X,0,goal.Z-position.Z)
 return delta.Magnitude>.01 and delta.Unit*math.min(12,delta.Magnitude*3) or Vector3.zero
end
return U
