-- Shared deterministic flight paths; the server sweeps the same curve clients draw.
local M={CARD_STAGGER=.07,BOX_OPEN=.24}
function M.position(origin,finish,t,side,height,bend)
 t=math.clamp(t,0,1)
 local delta=finish-origin;local flat=Vector3.new(delta.X,0,delta.Z)
 local right=flat.Magnitude>.001 and flat.Unit:Cross(Vector3.yAxis) or Vector3.xAxis
 return origin:Lerp(finish,t)+right*(math.sin(math.pi*t)*(side or 0)+math.sin(2*math.pi*t)*(bend or 0))+Vector3.yAxis*(4*t*(1-t)*(height or 0))
end
function M.duration(id,distance,speed)
 return math.clamp(distance/math.max(1,speed)*(id=='33' and 2.1 or 1.5),id=='33' and .85 or .54,id=='33' and 2.1 or 1.4)
end
function M.shape(id,distance,index,random)
 if id=='33' then return 0,math.clamp(distance*.55,8,23) end
 local width=math.clamp(distance*.34,2,9)
 if random then
  -- Server chooses one stable curve per flight; clients receive its parameters.
  -- Mixed broad hooks and S-curves, with positive lift to avoid ground clipping.
  local side=random:NextNumber(.3,1.15)*width*(random:NextInteger(0,1)==0 and -1 or 1)
  local bend=random:NextNumber(-.85,.85)*width
  return side,random:NextNumber(.8,math.clamp(distance*.2,2,6)),bend
 end
 return ({-1,.18,1})[(index-1)%3+1]*width,1.2+((index-1)%3)*.5,0
end
function M.lid(age)
 if age<0 then return 0 end
 if age<M.BOX_OPEN then local t=age/M.BOX_OPEN;return t*t*(3-2*t) end
 if age<.55 then return 1 end
 return 1-math.clamp((age-.55)/.3,0,1)
end
return M
