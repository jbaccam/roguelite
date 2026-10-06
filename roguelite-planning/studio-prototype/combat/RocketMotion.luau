-- Shared committed firing line. Rockets never weave, home, or redirect after launch.
local M={}
function M.position(origin,direction,distance,targetDistance,seed)
 return origin+direction*distance
end
function M.direction(origin,direction,distance,targetDistance,seed)
 return direction
end
return M
