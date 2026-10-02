-- Local presentation of server enemy shots and spawn warnings; never decides a hit.
-- Shots: EnemyAttacks flies and hit-tests each one and sends a Launch (and an End when it stops
-- early). This draws it by server time, so a late Launch still shows the shot where it is now.
-- Spawn warnings: RogueliteZombieChase places static red crosses; this pulses them.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local TweenService=game:GetService('TweenService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Visuals=require(combat:WaitForChild('EnemyProjectileVisuals'))
local folder=Instance.new('Folder');folder.Name='LocalEnemyShots';folder.Parent=workspace
local CULL=400 -- no model for a shot this far from the camera (the radius ShotBatch sends arena events to)
local shots={}
local held=nil -- server time shots in flight stopped at while the run is paused (plan L)
local function remove(id)
 local s=shots[id];if s then shots[id]=nil;if s.model then s.model:Destroy() end end
end
-- Where it would hit the map, so it doesn't fly into a wall while the End is on its way. Only
-- collidable parts count: the server stops at those too (plus a few non-collidable ones, which the
-- End covers), and the client's own cosmetic parts never cut a shot short.
local function wallTime(origin,velocity,lifetime)
 local exclude={folder}
 local enemies=workspace:FindFirstChild('RogueliteEnemies');if enemies then table.insert(exclude,enemies) end
 for _,p in Players:GetPlayers() do if p.Character then table.insert(exclude,p.Character) end end
 local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude
 params.FilterDescendantsInstances=exclude;params.RespectCanCollide=true
 local hit=workspace:Raycast(origin,velocity*lifetime,params)
 return hit and (hit.Position-origin).Magnitude/velocity.Magnitude or lifetime
end
-- ('Launch',id,kind,origin,velocity,started,lifetime), ('End',id), ('Hold',at), ('Resume',frozenSeconds).
local function onShot(action,a,kind,origin,velocity,started,lifetime)
 if action=='Launch' then
  if typeof(origin)~='Vector3' or typeof(velocity)~='Vector3' or velocity.Magnitude<.01 then return end
  remove(a)
  shots[a]={kind=kind,origin=origin,velocity=velocity,started=started,stopAt=wallTime(origin,velocity,lifetime)}
 elseif action=='End' then remove(a)
 elseif action=='Hold' then held=a
 elseif action=='Resume' then
  -- Paused shots carry on from where they hung: they start later by the frozen time.
  for _,s in shots do s.started+=a end
  held=nil
 end
end
local function hook(child) if child.Name=='EnemyShot' and child:IsA('RemoteEvent') then child.OnClientEvent:Connect(onShot) end end
-- EnemyAttacks makes the remote on match servers only (lobbies run no waves), so no WaitForChild.
combat.ChildAdded:Connect(hook)
for _,child in combat:GetChildren() do hook(child) end
RunService.RenderStepped:Connect(function()
 if not next(shots) then return end
 local now=workspace:GetServerTimeNow();local camera=workspace.CurrentCamera
 for id,s in shots do
  local flown=Visuals.flown(s.started,now,held)
  if flown>=s.stopAt then remove(id);continue end
  local frame=Visuals.shotFrame(s.origin,s.velocity,flown)
  if not s.model then
   if camera and (camera.CFrame.Position-frame.Position).Magnitude>CULL then continue end
   s.model=Visuals.shot(s.kind,combat:FindFirstChild('EnemyProjectileTemplates'));s.model.Parent=folder
  end
  s.model:PivotTo(frame)
 end
end)
-- Spawn warnings: the same pulse the server's tweens had, 0.1 -> 0.55 transparency and back every
-- 0.25 s, started as each bar arrives. Streaming can bring bars in late or take them away.
local PULSE=TweenInfo.new(.25,Enum.EasingStyle.Sine,Enum.EasingDirection.InOut,-1,true)
local function pulse(bar)
 if bar.Name~='WarningBar' or not bar:IsA('BasePart') then return end
 local tween=TweenService:Create(bar,PULSE,{Transparency=.55});tween:Play()
 bar.AncestryChanged:Connect(function() if not bar:IsDescendantOf(workspace) then tween:Cancel() end end)
end
local function watch(child)
 if child.Name~='RogueliteSpawnWarnings' then return end
 child.DescendantAdded:Connect(pulse)
 for _,d in child:GetDescendants() do pulse(d) end
end
workspace.ChildAdded:Connect(watch)
for _,child in workspace:GetChildren() do watch(child) end
