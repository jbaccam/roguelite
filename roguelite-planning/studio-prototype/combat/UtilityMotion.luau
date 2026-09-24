local U={HoldDuration=.85,EscapeDuration=2.4,SafeDistance=7,Slow=.35}
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
