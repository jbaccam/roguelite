-- Shared deterministic flight path: clients and server follow the same bends.
local M={}
function M.position(origin,direction,distance,targetDistance,seed)
 local base=origin+direction*distance
 local start=3.5 -- Clear the launcher before beginning the antics.
 local span=targetDistance-start
 if span<3 or distance<=start or distance>=targetDistance then return base end
 local u=(distance-start)/span
 local envelope=math.sin(math.pi*u)^2
 local axis=math.abs(direction.Y)>.95 and Vector3.xAxis or Vector3.yAxis
 local right=direction:Cross(axis).Unit;local up=right:Cross(direction).Unit
 local phase=seed*2.399963
 -- Broad, shallow weaving: small nose corrections rather than tight loops.
 local amplitude=math.min(.7,span*.035)
 local angle=(distance-start)*(.15+(seed%3)*.015)+phase
 local side=math.sin(angle)
 local lift=.12*math.sin(angle*.8)
 return base+(right*side+up*lift)*amplitude*envelope
end
function M.direction(origin,direction,distance,targetDistance,seed)
 local delta=M.position(origin,direction,distance+.04,targetDistance,seed)-M.position(origin,direction,math.max(0,distance-.04),targetDistance,seed)
 return delta.Magnitude>.001 and delta.Unit or direction
end
return M
