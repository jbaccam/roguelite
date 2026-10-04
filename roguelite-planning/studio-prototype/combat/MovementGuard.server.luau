-- Server movement check for run members (launch audit C1): blatant speed hacks, teleports, flying
-- and leaving the arena send the player back to their last safe spot. MovementCheck holds the
-- rules; this script samples each member 10 times a second.
-- The server moving a body itself (a revive, a respawn, Play Again, admin travel, a snap-back) sets
-- the root's CFrame from a script, which fires its CFrame signal and starts the check over there.
-- A client moving its own body never fires it on the server (physics replication doesn't). The one
-- client script that moves its own character is the melee dash (RogueliteCombat.client); the server
-- approves each one (DashAt) and this check allows its studs (MovementCheck.allow).
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local SSS=game:GetService('ServerScriptService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Role=require(SSS:WaitForChild('ServerRole'))
if Role.get()=='Lobby' then return end -- lobby servers have no runs
local Shop=require(SSS:WaitForChild('ShopService'))
local Check=require(SSS:WaitForChild('MovementCheck'))
local Maps=require(combat:WaitForChild('MapConfig'))
local Stats=require(combat:WaitForChild('CharacterStats')) -- the air speed bonus (already loaded by ShopService)

-- The arena's walls: the first of these that the active map has, as a box with a 30-stud margin.
-- Measured 2026-10-02: Pine Valley's MapOneBoundary spans 147 studs each way from the middle,
-- Beach Cove's BoundaryWall 109, the other maps' Collision ring 127. No walls: no bounds check.
local WALLS={'MapOneBoundary','BoundaryWall','Collision'}
local MARGIN=30
local boxMap,box
local function arena()
 local id=Role.activeMap();if not Maps.valid(id) then return nil end
 if boxMap==id then return box end
 boxMap,box=id,nil
 for _,name in WALLS do
  local walls=Role.find(name)
  if walls then
   local parts={}
   for _,d in walls:GetDescendants() do if d:IsA('BasePart') and d.CanCollide then table.insert(parts,d) end end
   if walls:IsA('BasePart') then table.insert(parts,walls) end
   box=Check.bounds(parts,MARGIN)
   if box then break end
  end
 end
 return box
end
combat:GetAttributeChangedSignal('RunMap'):Connect(function() boxMap=nil end)

local states={} -- player -> MovementCheck state, while guarded
local watched={} -- player -> the root whose CFrame signal is hooked
local dashSeen={} -- player -> the last DashAt allowed for
local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude;params.RespectCanCollide=true
local function refreshFilter()
 local list={workspace:FindFirstChild('RogueliteEnemies')}
 for _,q in Players:GetPlayers() do if q.Character then table.insert(list,q.Character) end end
 params.FilterDescendantsInstances=list
end
-- Studs from the root down to solid ground (math.huge over nothing within 80 studs).
local function groundGap(root)
 local hit=workspace:Raycast(root.Position,Vector3.new(0,-80,0),params)
 return hit and (root.Position.Y-hit.Position.Y) or math.huge
end
local function hook(p,root)
 if watched[p]==root then return end
 watched[p]=root
 root:GetPropertyChangedSignal('CFrame'):Connect(function()
  local s=states[p];if s and watched[p]==root then Check.reset(s,root.Position,os.clock()) end
 end)
end
-- Checked: members of the run, alive and standing (not down), not frozen by a pause.
local function guarded(p)
 if not Shop.members[p] or p:GetAttribute('RunDown') or p:GetAttribute('LobbyPreviewActive') then return nil end
 if combat:GetAttribute('RunPaused')==true then return nil end
 local character=p.Character;local h=character and character:FindFirstChildOfClass('Humanoid')
 local root=character and character:FindFirstChild('HumanoidRootPart')
 if not h or not root or h.Health<=0 then return nil end
 return character,h,root
end
local function snap(p,character,root,s,why)
 s.snaps+=1
 warn(string.format('MovementGuard: %s (%d) moved back to a safe spot (%s, %d this session)',p.Name,p.UserId,why,s.snaps))
 local safe=s.safe
 root.AssemblyLinearVelocity=Vector3.zero
 character:PivotTo(CFrame.new(safe+Vector3.new(0,.5,0))*root.CFrame.Rotation)
 Check.reset(s,safe,os.clock())
end

local elapsed,sinceFilter=0,1
RunService.Heartbeat:Connect(function(dt)
 elapsed+=dt;if elapsed<.1 then return end;elapsed=0
 sinceFilter+=.1;if sinceFilter>=1 then sinceFilter=0;refreshFilter() end
 local now=os.clock();local walls=arena()
 for _,p in Players:GetPlayers() do
  local character,h,root=guarded(p)
  if not character then states[p]=nil;continue end
  hook(p,root)
  local s=states[p]
  if not s then states[p]=Check.new(root.Position,now);continue end
  -- An approved dash (RogueliteMeta RunAction 'Dash' stamps DashAt, server time): Dash.Allowance
  -- more studs for a moment. Only a fresh stamp counts, once.
  local dashAt=p:GetAttribute('DashAt')
  if dashAt~=dashSeen[p] then
   dashSeen[p]=dashAt
   if type(dashAt)=='number' and workspace:GetServerTimeNow()-dashAt<1 then Check.allow(s,now,Stats.Dash.Allowance) end
  end
  -- Their own top speed: the MoveSpeed stat with the air bonus (their own client applies that, so
  -- the server's WalkSpeed never shows it). Held players keep it: the window still holds the running.
  local speed=math.max(h.WalkSpeed,(character:GetAttribute('Stat_MoveSpeed') or 16)*Stats.Movement.AirSpeedMultiplier)
  local why=Check.step(s,now,root.Position,speed,groundGap(root),root.AssemblyLinearVelocity.Y,Check.inside(walls,root.Position))
  if why then snap(p,character,root,s,why) end
 end
end)
Players.PlayerRemoving:Connect(function(p) states[p]=nil;watched[p]=nil;dashSeen[p]=nil end)
