-- Re-aligns the lobby stands after their visuals were moved or rotated by hand. Run in Studio
-- Edit (command bar or MCP); safe to re-run. Replaced/removed parts go to
-- ServerStorage.BeforeStationFix so nothing is lost.
--
-- 1. Rig follows visuals: a stand's Collision parts, StationName sign, Interaction and
--    StationPivot are turned about the pivot until the rig's front (-StationPivot.LookVector)
--    matches the visual front (LookVector of the largest Visuals mesh).
-- 2. Interaction (the E prompt and the walk-up auto-open point) sits front and centre on the
--    counter's front edge at chest height, so the prompt floats between the player and the
--    counter instead of inside the player's body.
-- 3. Lantern lenses: each WarmLens (and its LanternPostCollision) snaps onto its nearest
--    lantern post; a lens with no post nearby is moved to the backup folder.
local OPEN_GAP=.5 -- studs past the foundation's front edge
local PROMPT_HEIGHT=3.5
local LENS_ABOVE_POST=2 -- station lantern: lens centre above the post centre
local COLLISION_BELOW_POST=.6

local SS=game:GetService('ServerStorage')
local backup=SS:FindFirstChild('BeforeStationFix') or Instance.new('Folder')
backup.Name='BeforeStationFix';backup.Parent=SS
local lobby=workspace.RogueliteLobby
local out={}
local function flat(v) v=Vector3.new(v.X,0,v.Z);return v.Magnitude>1e-3 and v.Unit or Vector3.zero end
local function yawBetween(a,b) return math.atan2(a:Cross(b).Y,a:Dot(b)) end

for _,stand in lobby.Stations:GetChildren() do
 local pivotPart=stand:FindFirstChild('StationPivot');local visuals=stand:FindFirstChild('Visuals')
 if not pivotPart or not visuals then continue end
 if not backup:FindFirstChild(stand.Name) then stand:Clone().Parent=backup end
 local main;for _,m in visuals:GetChildren() do if m:IsA('BasePart') and (not main or m.Size.Magnitude>main.Size.Magnitude) then main=m end end
 local front=flat(main.CFrame.LookVector)
 local rigFront=flat(-pivotPart.CFrame.LookVector)
 local delta=yawBetween(rigFront,front)
 local origin=pivotPart.Position
 if math.abs(delta)>math.rad(1) then
  local turn=CFrame.new(origin)*CFrame.Angles(0,delta,0)*CFrame.new(-origin)
  for _,d in stand:GetDescendants() do
   if d:IsA('BasePart') and not d:IsDescendantOf(visuals) then d.CFrame=turn*d.CFrame end
  end
 end
 -- Front and centre, just past the foundation's front edge.
 local inter=stand:FindFirstChild('Interaction',true)
 local foundation=stand:FindFirstChild('Foundation_1',true)
 local halfDepth=foundation and foundation.Size.Z/2 or 3
 if inter then
  local pos=origin+front*(halfDepth+OPEN_GAP)+Vector3.new(0,PROMPT_HEIGHT,0)
  inter.CFrame=CFrame.lookAt(pos,pos+front)
 end
 table.insert(out,string.format('%s turned %.0f deg, open point %.1f studs in front of centre',stand.Name,math.deg(delta),halfDepth+OPEN_GAP))
 -- Station lanterns: pair each lens (and its collision stick) with a post.
 local extras=stand:FindFirstChild('Extras')
 if extras then
  local posts,lenses,sticks={}, {}, {}
  for _,d in extras:GetChildren() do
   if d.Name:find('^Lantern_Post') then table.insert(posts,d) elseif d.Name=='WarmLens' then table.insert(lenses,d) elseif d.Name=='LanternPostCollision' then table.insert(sticks,d) end
  end
  local function claim(list,taken,post)
   local best,bd
   for _,x in list do if not taken[x] then local dd=Vector3.new(x.Position.X-post.Position.X,0,x.Position.Z-post.Position.Z).Magnitude;if not bd or dd<bd then best,bd=x,dd end end end
   if best then taken[best]=true end
   return best
  end
  -- Exact matches first, so a lens already on its post keeps it.
  table.sort(posts,function(a,b)
   local function nearest(p) local m=math.huge;for _,l in lenses do m=math.min(m,Vector3.new(l.Position.X-p.Position.X,0,l.Position.Z-p.Position.Z).Magnitude) end;return m end
   return nearest(a)<nearest(b)
  end)
  local takenL,takenS={}, {}
  local moved=0
  for _,post in posts do
   local lens=claim(lenses,takenL,post);local stick=claim(sticks,takenS,post)
   local top=post.Position
   if lens and (Vector3.new(lens.Position.X-top.X,0,lens.Position.Z-top.Z)).Magnitude>.3 then lens.CFrame=CFrame.new(top+Vector3.new(0,LENS_ABOVE_POST,0))*lens.CFrame.Rotation;moved+=1 end
   if stick then stick.CFrame=CFrame.new(top-Vector3.new(0,COLLISION_BELOW_POST,0))*stick.CFrame.Rotation end
  end
  for _,l in lenses do if not takenL[l] then l.Parent=backup;moved+=1 end end
  for _,s in sticks do if not takenS[s] then s.Parent=backup end end
  if moved>0 then table.insert(out,'  '..stand.Name..' lanterns fixed: '..moved) end
 end
end

-- Lobby lantern lenses (Accents) with no Scenery post nearby.
local posts={}
for _,d in lobby.Scenery:GetDescendants() do if d:IsA('BasePart') and d.Name:find('^Lantern_Post') then table.insert(posts,d) end end
local orphans=0
for _,l in lobby.Accents:GetChildren() do
 if l.Name=='WarmLens' then
  local near=false
  for _,p in posts do if Vector3.new(p.Position.X-l.Position.X,0,p.Position.Z-l.Position.Z).Magnitude<3 then near=true;break end end
  if not near then l.Parent=backup;orphans+=1 end
 end
end
table.insert(out,'orphan lobby lenses moved to backup: '..orphans)
return table.concat(out,'\n')
