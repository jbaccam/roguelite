-- Shared floor probes for rolling weapons and hatchlings. A character/dummy is never ground,
-- including untagged lobby rigs outside RogueliteEnemies. All returned points are world-space.
local Players=game:GetService('Players')
local Tags=game:GetService('CollectionService')
local G={Clearance=.06,MaxStep=1.25,MaxDrop=6}
local FOLDERS={'RogueliteEnemies','RogueliteChickens','RogueliteTurrets','RogueliteWeaponShowcase','RogueliteWeaponShowcase_PlaySize','ZombieVariantPreviews','Zombie_R15_ProvidedTextures_Studio'}
function G.actor(part)
 local at=part
 while at and at~=workspace do
  if at:IsA('Model') and (at:FindFirstChildOfClass('Humanoid') or at:GetAttribute('PracticeTarget') or at:GetAttribute('LobbyDummy')) then return at end
  at=at.Parent
 end
end
-- Use the reviewed mesh's actual bounds, not a second guessed radius. The center offset matters:
-- the source pivot need not be the ball's center. Server sweep and client ScaleTo share this data.
function G.ballGeometry(template)
 if not template then return .8,Vector3.zero end
 local cf,size=template:GetBoundingBox()
 return math.max(.1,math.max(size.X,size.Y,size.Z)*.5),template:GetPivot():PointToObjectSpace(cf.Position)
end
function G.new(extras)
 local cachedAt=-math.huge;local params
 local probe={}
 local function refresh()
  local now=os.clock();if params and now-cachedAt<.25 then return end;cachedAt=now
  local filter={};for _,v in extras or {} do if v then table.insert(filter,v) end end
  for _,name in FOLDERS do local f=workspace:FindFirstChild(name);if f then table.insert(filter,f) end end
  for _,p in Players:GetPlayers() do if p.Character then table.insert(filter,p.Character) end end
  for _,tag in {'RogueliteZombie','RogueliteChicken'} do for _,npc in Tags:GetTagged(tag) do table.insert(filter,npc) end end
  params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude;params.FilterDescendantsInstances=filter;params.RespectCanCollide=true
 end
 function probe:floor(point,previousFloor)
  refresh()
  local start=Vector3.new(point.X,previousFloor and previousFloor+G.MaxStep+1 or point.Y+4,point.Z)
  local length=previousFloor and G.MaxStep+G.MaxDrop+1 or 100
  -- An untagged rig can appear between cache refreshes; reject it and continue to the floor.
  for _=1,8 do
   local hit=workspace:Raycast(start,-Vector3.yAxis*length,params)
   if not hit then return nil end
   local actor=G.actor(hit.Instance)
   if actor then local list=params.FilterDescendantsInstances;table.insert(list,actor);params.FilterDescendantsInstances=list
   else
    if hit.Normal.Y<.65 then return nil end
    if previousFloor and (hit.Position.Y-previousFloor>G.MaxStep or previousFloor-hit.Position.Y>G.MaxDrop) then return nil end
    return hit.Position
   end
  end
  return nil
 end
 function probe:center(point,radius,previousFloor)
  local floor=self:floor(point,previousFloor)
  return floor and floor+Vector3.yAxis*(radius+G.Clearance) or nil
 end
 return probe
end
return G
