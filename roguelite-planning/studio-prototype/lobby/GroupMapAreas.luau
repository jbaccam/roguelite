-- One-time Edit migration (LOBBY_AND_MATCH_SERVERS.md §9). Gathers Pine Valley's loose Workspace
-- parts into Workspace.PineValleyArena and Beach Cove's hand-placed props into
-- Workspace.BeachCoveExtras.Props, then gives each map a PlayerSpawn and a RogueliteZombieSpawn.
-- Positions never change. Every move and every new instance is recorded in
-- ServerStorage.MapGrouping_20260928; set UNDO=true and run again to reverse it. Running it
-- twice is safe: it only picks up what is still loose.
-- UNDO is safe to re-run. It skips anything moved or deleted since the migration and keeps
-- folders that still hold other content. Before undoing, revert and sync the code that expects
-- the folders (RogueliteZombieChase, BossEncounter, RogueliteCombat, RogueliteLobbyPreview and
-- ApplyPropCollision); otherwise the spawner finds no marker.
local UNDO=false
local PINE_CENTER=Vector3.new(56,5,450) -- Pine Valley's zombie spawn marker
local PINE_RADIUS=250
local BEACH_CENTER=Vector3.new(700,0,300) -- BeachCoveArena.SandFloor
local BEACH_RADIUS=190
local KEEP={Baseplate=true,RogueliteLobby=true,BeachCoveArena=true,BeachCoveExtras=true,PineValleyArena=true}
local SS=game:GetService('ServerStorage')
local log=SS:FindFirstChild('MapGrouping_20260928') or Instance.new('Folder')
log.Name='MapGrouping_20260928';log.Parent=SS
local function record(kind,inst) local v=Instance.new('ObjectValue');v.Name=kind;v.Value=inst;v.Parent=log end

if UNDO then
 -- Undo only what is still where this migration put it; leave anything moved or deleted since.
 local pine=workspace:FindFirstChild('PineValleyArena');local ex=workspace:FindFirstChild('BeachCoveExtras')
 local props=ex and ex:FindFirstChild('Props')
 local restored,removed,skipped,kept=0,0,{},{}
 local function unmark(inst)
  local o=inst:GetAttribute('OriginalName');if o then inst.Name=o;inst:SetAttribute('OriginalName',nil) end
  if inst:GetAttribute('AddedSpawnBoundaryModel') and inst:GetAttribute('SpawnBoundaryModel')=='MapOneBoundary' then
   inst:SetAttribute('SpawnBoundaryModel',nil);inst:SetAttribute('AddedSpawnBoundaryModel',nil) end
 end
 for _,v in log:GetChildren() do local inst=v.Value
  if v.Name=='moved' and inst and inst.Parent then
   if (inst.Parent==pine or inst.Parent==props) and pcall(function() inst.Parent=workspace end) then unmark(inst);restored+=1;v:Destroy()
   else table.insert(skipped,inst:GetFullName()) end
  elseif v.Name=='moved' then v:Destroy() end -- deleted since: leave it deleted
 end
 local created={};for _,v in log:GetChildren() do if v.Name=='created' then table.insert(created,v) end end
 for i=#created,1,-1 do local v=created[i];local inst=v.Value -- children before parents
  if inst and inst.Parent and inst:IsA('Folder') and #inst:GetChildren()>0 then table.insert(kept,inst:GetFullName())
  else if inst and inst.Parent then inst:Destroy();removed+=1 end;v:Destroy() end
 end
 if #log:GetChildren()==0 then log:Destroy() end
 return ('Undone: %d moved back, %d removed. Skipped (moved/deleted since): %s. Kept non-empty: %s'):format(
  restored,removed,table.concat(skipped,', '),table.concat(kept,', '))
end

local function flat(p) return Vector3.new(p.X,0,p.Z) end
local function where(inst)
 if inst:IsA('BasePart') then return inst.Position end
 if inst:IsA('Model') then return inst:GetPivot().Position end
 local sum,n=Vector3.zero,0
 for _,d in inst:GetDescendants() do if d:IsA('BasePart') then sum+=d.Position;n+=1 end end
 return n>0 and sum/n or nil
end
local function folder(parent,name)
 local f=parent:FindFirstChild(name)
 if not f then f=Instance.new('Folder');f.Name=name;f.Parent=parent;record('created',f) end
 return f
end
local function move(inst,into) record('moved',inst);inst.Parent=into end

local pine=folder(workspace,'PineValleyArena')
local extras=folder(workspace,'BeachCoveExtras')
local props=folder(extras,'Props')
local movedPine,movedBeach=0,0
for _,c in workspace:GetChildren() do
 if KEEP[c.Name] or c:IsA('Terrain') or c:IsA('Camera') or game:GetService('Players'):GetPlayerFromCharacter(c) then continue end
 local p=where(c);if not p then continue end
 if (p-PINE_CENTER).Magnitude<PINE_RADIUS then move(c,pine);movedPine+=1
 elseif (c:IsA('BasePart') or c:IsA('Model')) and (flat(p)-flat(BEACH_CENTER)).Magnitude<BEACH_RADIUS then move(c,props);movedBeach+=1 end
end

-- Pine Valley: its SpawnLocation becomes PlayerSpawn; its marker names its boundary explicitly.
local pineSpawn=pine:FindFirstChild('SpawnLocation')
if pineSpawn then pineSpawn:SetAttribute('OriginalName',pineSpawn.Name);pineSpawn.Name='PlayerSpawn' end
pineSpawn=pine:FindFirstChild('PlayerSpawn')
local pineMarker=pine:FindFirstChild('RogueliteZombieSpawn')
if pineMarker and pineMarker:GetAttribute('SpawnBoundaryModel')==nil then
 pineMarker:SetAttribute('SpawnBoundaryModel','MapOneBoundary');pineMarker:SetAttribute('AddedSpawnBoundaryModel',true)
end

-- Beach Cove: markers beside the rebuilt arena (MapConfig note).
local arena=workspace.BeachCoveArena
local sand=arena.SandFloor
local floorTop=sand.Position.Y+sand.Size.X/2 -- a cylinder lying on its side (ApplyPropCollision)
local center=Vector3.new(sand.Position.X,floorTop,sand.Position.Z)
local ring=0
for _,w in arena.BoundaryWall:GetDescendants() do
 if w:IsA('BasePart') and w.Name:match('^Wall') then ring=math.max(ring,(flat(w.Position)-flat(center)).Magnitude) end
end
assert(ring>20,'BeachCoveArena.BoundaryWall has no Wall parts; cannot size the spawn area')
local function clearSpot()
 local params=OverlapParams.new();params.FilterType=Enum.RaycastFilterType.Exclude
 params.FilterDescendantsInstances={sand,arena.BoundaryWall,workspace.Baseplate}
 for radius=0,60,6 do
  for step=0,(radius==0 and 0 or 11) do
   local a=step*math.pi/6
   local p=center+Vector3.new(math.cos(a)*radius,0,math.sin(a)*radius)
   if #workspace:GetPartBoundsInBox(CFrame.new(p+Vector3.new(0,4,0)),Vector3.new(12,7,12),params)==0 then return p end
  end
 end
 return center
end
if not extras:FindFirstChild('PlayerSpawn') then
 local s=Instance.new('SpawnLocation');s.Name='PlayerSpawn'
 s.Anchored=true;s.Size=Vector3.new(12,1,12);s.Transparency=1;s.CanCollide=false;s.CanQuery=false
 s.Enabled=false -- ServerRole enables the active map's spawn
 s.Duration=pineSpawn and pineSpawn.Duration or 10
 s.Position=clearSpot()+Vector3.new(0,.5,0)
 for _,d in s:GetChildren() do d:Destroy() end
 s.Parent=extras;record('created',s)
end
if not extras:FindFirstChild('RogueliteZombieSpawn') then
 local m=Instance.new('Part');m.Name='RogueliteZombieSpawn'
 m.Anchored=true;m.Size=Vector3.new(1,1,1);m.Transparency=1;m.CanCollide=false;m.CanTouch=false
 m.CanQuery=false -- invisible to raycasts, so ray filters needn't exclude it
 m.Position=center+Vector3.new(0,.5,0)
 m:SetAttribute('SpawnAreaCenter',center);m:SetAttribute('SpawnAreaRadius',math.floor(ring-11))
 m:SetAttribute('SpawnBlockerFolder','NoClimb');m:SetAttribute('SpawnBoundaryModel','BoundaryWall')
 m.Parent=extras;record('created',m)
end
return ('Pine Valley: %d moved. Beach Cove: %d props moved, wall ring %.1f, spawn radius %d, PlayerSpawn at %s'):format(
 movedPine,movedBeach,ring,extras.RogueliteZombieSpawn:GetAttribute('SpawnAreaRadius'),tostring(extras.PlayerSpawn.Position))
