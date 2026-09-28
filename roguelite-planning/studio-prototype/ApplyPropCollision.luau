-- Makes solid-looking props solid. Run in Studio Edit (command bar or MCP); safe to re-run.
-- Most imported visuals were set CanCollide=false on purpose (their meshes make poor
-- colliders), but only the first arena's trees and cliffs received replacement collision.
--
--   Lobby       scenery props collide with their own mesh (precise shapes for trees, arches and
--               benches, so players walk under canopies). Fences use a Box: their mesh is posts
--               plus one knee-high rail, which characters step straight over. The stands are skipped:
--               each already has an invisible Collision folder (FixStations.luau keeps it
--               aligned with the visuals).
--   Arenas      rocks and logs no taller than JUMPABLE collide with their own mesh, so players
--               jump over them or stand on them. Taller ones follow MapOneNoClimb's convention:
--               an invisible, unqueryable 130.5-stud box on the prop's footprint, so they
--               block but cannot be climbed (no camping on high ground) and do not stop
--               bullets. The cliffs and trees keep MapOneNoClimb's own boxes. Palms collide
--               with their own mesh (trunk + high fronds), because a footprint box would fill
--               the shade under the fronds.
--   Walk-through (unchanged): grass, flowers, ferns, shrubs, pebbles, path stones, ground
--               patches, tide pools, planks, backdrop, floors (they have separate collision).
--
-- Each changed part stores its original values in CollisionBefore; boxes carry
-- AddedBy=ApplyPropCollision and are rebuilt on each run. Pass revert=true to undo.
local revert=false

local TAG='ApplyPropCollision'
local out={}
local function remember(p)
 if p:GetAttribute('CollisionBefore')==nil then
  p:SetAttribute('CollisionBefore',string.format('%s|%s|%s',tostring(p.CanCollide),tostring(p.CanQuery),p:IsA('MeshPart') and p.CollisionFidelity.Name or ''))
 end
end
local function restore(p)
 local before=p:GetAttribute('CollisionBefore');if not before then return end
 local c,q,f=string.match(before,'^(%a+)|(%a+)|(%a*)$')
 p.CanCollide=c=='true';p.CanQuery=q=='true'
 if f~='' and p:IsA('MeshPart') then p.CollisionFidelity=Enum.CollisionFidelity[f] end
 p:SetAttribute('CollisionBefore',nil)
end
local function makeSolid(p,precise)
 remember(p)
 if p:IsA('MeshPart') then p.CollisionFidelity=precise and Enum.CollisionFidelity.PreciseConvexDecomposition or Enum.CollisionFidelity.Default end
 p.CanCollide=true;p.CanQuery=true;p.CanTouch=false
end
local function matches(name,list) for _,pat in list do if string.find(name,pat) then return true end end return false end

-- Lobby ------------------------------------------------------------------------------
local LOBBY_PRECISE={'Broadleaf_Tree','Portal%d_Arch','^Bench_'}
local LOBBY_BOX={'^Fence_'}
local LOBBY_SOLID={'^Boulder','Lantern_Post','^Crate_','Practice_Dummy','Fallen_Log','Log_Stool','Campfire'}
local lobby=workspace:FindFirstChild('RogueliteLobby')
local lobbyCount=0
if lobby then
 for _,folder in {lobby:FindFirstChild('Scenery')} do
  if folder then for _,p in folder:GetDescendants() do
   if p:IsA('BasePart') and p.Transparency<1 then
    if revert then restore(p)
    elseif matches(p.Name,LOBBY_PRECISE) then makeSolid(p,true);lobbyCount+=1
    elseif matches(p.Name,LOBBY_BOX) then makeSolid(p,false);p.CollisionFidelity=Enum.CollisionFidelity.Box;lobbyCount+=1
    elseif matches(p.Name,LOBBY_SOLID) then makeSolid(p,false);lobbyCount+=1 end
   end
  end end
 end
end
table.insert(out,(revert and 'lobby restored' or 'lobby solid parts: '..lobbyCount))

-- Arenas -----------------------------------------------------------------------------
local ARENA_BOXED={'Boulder','Rock_Cluster','Standing_Rock','Shore_Rock','Bare_Low_Filler','Log_Master','Driftwood_Log'}
-- Studs above the floor a prop may reach and still be jumped onto (StarterPlayer JumpHeight 9.5).
local JUMPABLE=8
local function bounds(prop)
 local cf,size
 if prop:IsA('Model') then cf,size=prop:GetBoundingBox() else cf,size=prop.CFrame,prop.Size end
 local corners={}
 for _,sx in {-1,1} do for _,sy in {-1,1} do for _,sz in {-1,1} do table.insert(corners,cf*Vector3.new(sx*size.X/2,sy*size.Y/2,sz*size.Z/2)) end end end
 return cf,corners
end
local function jumpable(prop,floorY)
 local _,corners=bounds(prop);local top=-math.huge
 for _,c in corners do top=math.max(top,c.Y) end
 return top-floorY<=JUMPABLE
end
local function visibleParts(prop)
 local list=prop:IsA('BasePart') and {prop} or {}
 for _,d in prop:GetDescendants() do if d:IsA('BasePart') then table.insert(list,d) end end
 local shown={}
 for _,p in list do if p.Transparency<1 then table.insert(shown,p) end end
 return shown
end
local function footprintBox(folder,prop,bottomY)
 -- Yaw-only footprint of the (possibly tilted) bounding box.
 local cf,corners=bounds(prop)
 local look=cf.LookVector;look=Vector3.new(look.X,0,look.Z)
 if look.Magnitude<.1 then look=Vector3.new(0,0,-1) end
 local yaw=CFrame.lookAt(Vector3.zero,look.Unit)
 local minX,maxX,minZ,maxZ=math.huge,-math.huge,math.huge,-math.huge
 for _,c in corners do local l=yaw:PointToObjectSpace(c);minX=math.min(minX,l.X);maxX=math.max(maxX,l.X);minZ=math.min(minZ,l.Z);maxZ=math.max(maxZ,l.Z) end
 local mid=yaw*Vector3.new((minX+maxX)/2,0,(minZ+maxZ)/2)
 local height=130.5
 local box=Instance.new('Part');box.Name='NoClimb_'..prop.Name
 box.Size=Vector3.new(math.max(2,maxX-minX+1),height,math.max(2,maxZ-minZ+1))
 box.CFrame=CFrame.new(mid.X,bottomY+height/2,mid.Z)*yaw.Rotation
 box.Anchored=true;box.CanCollide=true;box.CanQuery=false;box.CanTouch=false;box.CastShadow=false;box.Transparency=1
 box:SetAttribute('AddedBy',TAG);box.Parent=folder
 return box
end
local function clearAdded(folder) if folder then for _,c in folder:GetChildren() do if c:GetAttribute('AddedBy')==TAG then c:Destroy() end end end end

-- First arena (Pine Valley): props in Workspace.PineValleyArena on the grass, x < 400, above y = -60.
local pineArea=workspace:FindFirstChild('PineValleyArena') or workspace
local mapOne=pineArea:FindFirstChild('MapOneNoClimb')
clearAdded(mapOne)
if mapOne then
 -- Only MapOneNoClimb's own (cliff and tree) blocks count here; the added boxes were just cleared.
 local blocks={}
 for _,b in mapOne:GetChildren() do if b:IsA('BasePart') then table.insert(blocks,b) end end
 local function covered(pos)
  for _,b in blocks do local l=b.CFrame:PointToObjectSpace(pos);if math.abs(l.X)<=b.Size.X/2+1 and math.abs(l.Z)<=b.Size.Z/2+1 then return true end end
  return false
 end
 local added,solid=0,0
 for _,c in pineArea:GetChildren() do
  if (c:IsA('Model') or c:IsA('MeshPart')) and matches(c.Name,ARENA_BOXED) then
   local p=c:GetPivot().Position
   if revert then for _,part in visibleParts(c) do restore(part) end
   elseif p.Y>-60 and p.X<400 and not covered(p) then
    if jumpable(c,2) then for _,part in visibleParts(c) do makeSolid(part,false) end;solid+=1
    else footprintBox(mapOne,c,2);added+=1 end
   end
  end
 end
 table.insert(out,revert and 'Pine Valley restored' or ('Pine Valley boxes added: '..added..', jumpable props solid: '..solid))
end

-- Beach Cove: props inside the boundary ring.
local beach=workspace:FindFirstChild('BeachCoveArena')
if beach then
 local center=Vector3.new(beach.SandFloor.Position.X,0,beach.SandFloor.Position.Z)
 local radius=0
 for _,w in beach.BoundaryWall:GetChildren() do if w:IsA('BasePart') then radius=math.max(radius,(Vector3.new(w.Position.X,0,w.Position.Z)-center).Magnitude) end end
 local floorTop=beach.SandFloor.Position.Y+beach.SandFloor.Size.X/2 -- the floor is a cylinder lying on its side
 local folder=beach:FindFirstChild('NoClimb')
 if not folder and not revert then folder=Instance.new('Folder');folder.Name='NoClimb';folder.Parent=beach end
 clearAdded(folder)
 local function inside(part) local d=Vector3.new(part.Position.X,0,part.Position.Z)-center;return d.Magnitude<radius-2 end
 local boxes,palms,solid=0,0,0
 local candidates={}
 for _,d in beach.Scenery:GetDescendants() do if d:IsA('BasePart') then table.insert(candidates,d) end end
 -- Hand-placed props sit in BeachCoveExtras.Props (GroupMapAreas), outside the rebuilt arena folder.
 local extras=workspace:FindFirstChild('BeachCoveExtras');local looseProps=extras and extras:FindFirstChild('Props')
 for _,c in (looseProps or workspace):GetChildren() do if c:IsA('MeshPart') then table.insert(candidates,c) end end
 for _,p in candidates do
  if p.Transparency<1 and inside(p) then
   if p.Name=='FixedPalm' or string.find(p.Name,'Palm') then if revert then restore(p) else makeSolid(p,true);palms+=1 end
   elseif matches(p.Name,ARENA_BOXED) then
    if revert then restore(p)
    elseif jumpable(p,floorTop) then makeSolid(p,false);solid+=1
    else footprintBox(folder,p,floorTop);boxes+=1 end
   end
  end
 end
 if revert and folder and #folder:GetChildren()==0 then folder:Destroy() end
 table.insert(out,revert and 'Beach Cove restored' or ('Beach Cove boxes added: '..boxes..', palms solid: '..palms..', jumpable props solid: '..solid))
end
return table.concat(out,' | ')
